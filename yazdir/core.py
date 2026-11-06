"""Yazdır çekirdeği: belgeyi PDF'e çevirir, sayfaları A4 yüzlere yerleştirir,
elle arkalı önlü baskı için ön/arka dosyalarını hazırlar ve CUPS ile basar.

Elle arkalı önlü yöntemi (HP LaserJet 1018 ile denendi):
  1. Ön yüzler (1., 3., 5. ... yüz) sırayla basılır.
  2. Kullanıcı çıkan tomarın TAMAMINI, yönünü değiştirmeden, basılı yüzü aşağıda
     tepsiye geri koyar (HP'nin Windows sürücüsünün talimatı da budur).
     Bu durumda yazıcının ilk aldığı kâğıt, en son basılan ön yüzdür.
  3. Arka yüzler bu yüzden TERS sırayla basılır.
  Ön yüz sayısı tekse en son kâğıdın arkası boştur; kullanıcı kâğıt ayırmasın diye
  arka dosyasının başına (neredeyse) boş bir sayfa eklenir, o kâğıt boş geçer.

Arka yüzlerin yönü:
  Bütün yüzler arkalı önlüde A4 dikeye biz yerleştiririz (CUPS'un kendi döndürmesine
  bırakılmaz). 2'li sayfa ve kitapçıkta kâğıt yan çevrilerek (kısa kenardan) okunur;
  bu yüzden HP'nin Windows sürücüsü gibi arka yüzler 180° döndürülür. Yazıcının kâğıt
  yolu da arka yüzü ters basıyorsa ayarlardaki "arka_180" bunu düzeltir
  (deneme sayfasıyla belirlenir).
"""
from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from . import dil
from .dil import t

A4_W, A4_H = 595.28, 841.89

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "yazdir"
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yazdir" / "config.json"

OFFICE_EXT = {".doc", ".docx", ".odt", ".rtf", ".txt", ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

DUZENLER = ("1", "2", "4", "kitapcik")


def duzen_adi(duzen: str) -> str:
    return t(f"duzen.{duzen}")


class YazdirHata(Exception):
    pass


log = logging.getLogger("yazdir")


def gunluk_ac() -> Path:
    """Günlüğü ~/.cache/yazdir/yazdir.log dosyasına yazar (en çok 3 × 1 MB). Sorun olunca buraya bakılır."""
    yol = CACHE / "yazdir.log"
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in log.handlers):
        yol.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(yol, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return yol


# ---------------------------------------------------------------- ayarlar
def ayarlar() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


def ayar_kaydet(**kv) -> None:
    a = ayarlar()
    a.update(kv)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(a, ensure_ascii=False, indent=2))


def dil_kaydet(kod: str) -> str:
    """Arayüz dilini seçer ve kaydeder."""
    ayar_kaydet(dil=dil.ayarla(kod))
    return dil.aktif()


dil.ayarla(ayarlar().get("dil"))


def yazicilar() -> list[str]:
    out = subprocess.run(["lpstat", "-e"], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


def varsayilan_yazici() -> str | None:
    a = ayarlar().get("yazici")
    if a:
        return a
    out = subprocess.run(["lpstat", "-d"], capture_output=True, text=True).stdout
    m = re.search(r":\s*(\S+)\s*$", out.strip())
    if m:
        return m.group(1)
    y = yazicilar()
    return y[0] if y else None


# ---------------------------------------------------------------- dönüştürme
def pdfe_cevir(kaynak: Path, hedef_klasor: Path) -> Path:
    """Kaynağı hedef_klasor/kaynak.pdf yapar. Word/resim dönüşümleri önbelleğe alınır: ayar değiştikçe
    LibreOffice'in yeniden çalışmaması için (dosya değişirse önbellek anahtarı da değişir)."""
    kaynak = Path(kaynak).expanduser().resolve()
    if not kaynak.exists():
        raise YazdirHata(t("hata.dosya_yok", yol=kaynak))
    ext = kaynak.suffix.lower()
    hedef = hedef_klasor / "kaynak.pdf"
    if ext == ".pdf":
        shutil.copyfile(kaynak, hedef)
        return hedef
    if ext not in OFFICE_EXT | IMAGE_EXT:
        raise YazdirHata(t("hata.tur", ext=ext))
    st = kaynak.stat()
    anahtar = hashlib.sha1(f"{kaynak}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    onbellek = CACHE / "donusum" / f"{anahtar}.pdf"
    if onbellek.exists():
        shutil.copyfile(onbellek, hedef)
        return hedef
    _donustur(kaynak, ext, hedef_klasor, hedef)
    onbellek.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hedef, onbellek)
    return hedef


def _donustur(kaynak: Path, ext: str, hedef_klasor: Path, hedef: Path) -> None:
    if ext in OFFICE_EXT:
        profil = CACHE / "lo-profil"
        r = subprocess.run(
            ["soffice", f"-env:UserInstallation=file://{profil}", "--headless",
             "--convert-to", "pdf", "--outdir", str(hedef_klasor), str(kaynak)],
            capture_output=True, text=True, timeout=300)
        cikti = hedef_klasor / (kaynak.stem + ".pdf")
        if not cikti.exists():
            raise YazdirHata(t("hata.libreoffice", ayrinti=r.stderr.strip() or r.stdout.strip()))
        cikti.rename(hedef)
    elif ext in IMAGE_EXT:
        arac = shutil.which("magick") or shutil.which("convert")   # ImageMagick 7 / 6 (eski Debian/Ubuntu)
        if not arac:
            raise YazdirHata(t("hata.resim", ayrinti="ImageMagick (magick/convert)"))
        r = subprocess.run([arac, str(kaynak), "-auto-orient", str(hedef)], capture_output=True, text=True)
        if r.returncode != 0:
            raise YazdirHata(t("hata.resim", ayrinti=r.stderr.strip()))


def sayfa_secimi(metin: str | None, toplam: int) -> list[int]:
    """'1-3,5,8-' -> [1,2,3,5,8,...,toplam] (1 tabanlı)."""
    if not metin or not metin.strip():
        return list(range(1, toplam + 1))
    sonuc: list[int] = []
    for parca in metin.replace(" ", "").split(","):
        if not parca:
            continue
        m = re.fullmatch(r"(\d*)-(\d*)", parca)
        if m:
            a = int(m.group(1) or 1)
            b = int(m.group(2) or toplam)
        elif parca.isdigit():
            a = b = int(parca)
        else:
            raise YazdirHata(t("hata.aralik_anlasilmadi", parca=parca))
        if a < 1 or b > toplam or a > b:
            raise YazdirHata(t("hata.aralik_gecersiz", parca=parca, toplam=toplam))
        sonuc.extend(range(a, b + 1))
    return sonuc


# ---------------------------------------------------------------- yerleştirme
def _yerlestir(hedef: PageObject, kaynak: PageObject, x: float, y: float, w: float, h: float,
               dondur_180: bool = False) -> None:
    """Kaynak sayfayı (x, y, w, h) kutusuna oranını koruyarak ortalar; gerekirse 90° döndürür.
    dondur_180: sonuç kutunun ortası etrafında ayrıca 180° çevrilir (arka yüzler için)."""
    if kaynak.rotation % 360:   # /Rotate içeriğe aktarılır (yalnız gerekiyorsa: boş/deneme sayfalarında gerekmez)
        kaynak.transfer_rotation_to_content()
    kutu = kaynak.cropbox
    x0, y0 = float(kutu.left), float(kutu.bottom)
    sw, sh = float(kutu.width), float(kutu.height)
    duz = min(w / sw, h / sh)
    yan = min(w / sh, h / sw)
    donusum = Transformation().translate(-x0, -y0)
    if yan > duz * 1.05:
        k = yan
        donusum = donusum.rotate(90).translate(sh, 0)
        sw, sh = sh, sw
    else:
        k = duz
    donusum = donusum.scale(k).translate(x + (w - sw * k) / 2, y + (h - sh * k) / 2)
    if dondur_180:
        donusum = donusum.rotate(180).translate(2 * x + w, 2 * y + h)
    hedef.merge_transformed_page(kaynak, donusum)


def _yeni_sayfa(w: float, h: float) -> PageObject:
    """Bir PdfWriter'a bağlı boş sayfa. pypdf, writer'a bağlı olmayan sayfaya içerik eklemeyi
    güvenilmez sayıp 7.0'da kaldırıyor; bütün sayfalar bu yüzden buradan üretilir."""
    return PdfWriter().add_blank_page(width=w, height=h)


def _yuz(slotlar, sayfalar, yatay: bool) -> PageObject:
    W, H = (A4_H, A4_W) if yatay else (A4_W, A4_H)
    p = _yeni_sayfa(W, H)
    for (x, y, w, h), s in zip(slotlar, sayfalar):
        if s is not None:
            _yerlestir(p, s, x, y, w, h)
    return p


def yuzleri_olustur(reader, secim: list[int], duzen: str) -> list[PageObject]:
    """Seçilen kaynak sayfalarını A4 yüzlere yerleştirir. Sıra = baskı yüzü sırası."""
    kaynak = lambda n: reader.pages[n - 1]
    if duzen == "1":
        return [kaynak(n) for n in secim]
    if duzen == "2":
        sl = [(0, 0, A4_H / 2, A4_W), (A4_H / 2, 0, A4_H / 2, A4_W)]
        return [_yuz(sl, [kaynak(n) for n in secim[i:i + 2]], True) for i in range(0, len(secim), 2)]
    if duzen == "4":
        w, h = A4_W / 2, A4_H / 2
        sl = [(0, h, w, h), (w, h, w, h), (0, 0, w, h), (w, 0, w, h)]
        return [_yuz(sl, [kaynak(n) for n in secim[i:i + 4]], False) for i in range(0, len(secim), 4)]
    if duzen == "kitapcik":
        sayfalar = [kaynak(n) for n in secim]
        while len(sayfalar) % 4:
            sayfalar.append(None)
        n = len(sayfalar)
        sl = [(0, 0, A4_H / 2, A4_W), (A4_H / 2, 0, A4_H / 2, A4_W)]
        yuzler = []
        for i in range(n // 4):
            # 1 tabanlı: ön [n-2i | 2i+1], arka [2i+2 | n-2i-1]
            yuzler.append(_yuz(sl, [sayfalar[n - 2 * i - 1], sayfalar[2 * i]], True))
            yuzler.append(_yuz(sl, [sayfalar[2 * i + 1], sayfalar[n - 2 * i - 2]], True))
        return yuzler
    raise YazdirHata(t("hata.duzen", liste=", ".join(DUZENLER)))


def _yatay_duzen(duzen: str) -> bool:
    return duzen in ("2", "kitapcik")


def _a4_dikey(yuz: PageObject, dondur_180: bool) -> PageObject:
    """Yüzü A4 dikey sayfaya yerleştirir (yataysa hep aynı yöne 90° döner); istenirse 180° çevirir."""
    p = _yeni_sayfa(A4_W, A4_H)
    _yerlestir(p, yuz, 0, 0, A4_W, A4_H, dondur_180)
    return p


def _bos_yuz() -> PageObject:
    """Boş arka yüz. Sürücü tümüyle boş sayfayı atlarsa sıra kayar; bu yüzden gözle
    görülmeyecek kadar küçük, açık gri bir nokta konur."""
    p = _yeni_sayfa(A4_W, A4_H)
    icerik = DecodedStreamObject()
    icerik.set_data(b"0.9 g 297 30 0.5 0.5 re f")
    p[NameObject("/Contents")] = icerik
    return p


def _yaz(sayfalar, yol: Path) -> None:
    w = PdfWriter()
    for p in sayfalar:
        w.add_page(p)
    with open(yol, "wb") as f:
        w.write(f)


# ---------------------------------------------------------------- iş
@dataclass
class Is:
    id: str
    klasor: str
    kaynak: str
    duzen: str
    arkali_onlu: bool
    kopya: int
    yazici: str | None
    kaynak_sayfa: int
    secilen_sayfa: int
    yuz_sayisi: int
    kagit: int
    on_sayisi: int = 0
    arka_sayisi: int = 0
    son_kagidi_ayir: bool = False   # eski işler: kullanıcı son kâğıdı ayırıyordu
    arka_bos_sayfa: bool = False    # son kâğıdın arkası boş geçer, kâğıt ayırmak gerekmez
    arka_180: bool = False          # yazıcı ayarı: arka yüzler ek olarak 180° döndürüldü mü
    deneme: bool = False            # yön deneme sayfası
    # hazir -> (hepsi|on|arka)_gonderildi -> on_basildi / bitti ; vazgecildi: kullanıcı yarım işi bıraktı
    durum: str = "hazir"
    gecmis: list = field(default_factory=list)

    @property
    def yol(self) -> Path:
        return Path(self.klasor)

    def dosya(self, ad: str) -> Path:
        return self.yol / ad

    def kaydet(self) -> None:
        self.dosya("is.json").write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2))

    @classmethod
    def yukle(cls, is_id: str | None = None) -> "Is":
        if not is_id or is_id == "son":
            isler = sorted((CACHE / "isler").glob("*/is.json"))
            if not isler:
                raise YazdirHata(t("hata.is_yok"))
            yol = isler[-1]
        else:
            yol = CACHE / "isler" / is_id / "is.json"
            if not yol.exists():
                raise YazdirHata(t("hata.is_bulunamadi", id=is_id))
        return cls(**json.loads(yol.read_text()))

    def ozet(self) -> str:
        s = [t("ozet.is", id=self.id),
             t("ozet.kaynak", yol=self.kaynak, toplam=self.kaynak_sayfa, secilen=self.secilen_sayfa),
             t("ozet.duzen", ad=duzen_adi(self.duzen)) + (t("ozet.kopya", n=self.kopya) if self.kopya > 1 else ""),
             t("ozet.baski_arkali" if self.arkali_onlu else "ozet.baski_tek", yuz=self.yuz_sayisi, kagit=self.kagit),
             t("ozet.yazici", ad=self.yazici)]
        if self.arkali_onlu:
            s.append(t("ozet.adimlar", on=self.on_sayisi, arka=self.arka_sayisi))
            if self.arka_bos_sayfa:
                s.append(t("ozet.bos_arka"))
            elif self.son_kagidi_ayir:
                s.append(t("ozet.son_kagidi_ayir"))
        s.append(t("ozet.durum", durum=t(f"durum.{self.durum}")))
        return "\n".join(s)

    def kagit_talimati(self) -> str:
        if self.son_kagidi_ayir and not self.arka_bos_sayfa:  # eski işler
            return t("talimat.eski", n=self.arka_sayisi) + t("talimat.nasil")
        m = t("talimat.hepsi", n=self.on_sayisi) + t("talimat.nasil")
        if self.arka_bos_sayfa:
            m += t("talimat.bos_arka")
        return m


def isi_sil(is_: Is) -> None:
    """Hiç basılmamış, artık gösterilmeyen işin klasörünü siler (her ayar değişikliği yeni iş açar)."""
    if not is_.gecmis and Path(is_.klasor).parent == CACHE / "isler":
        shutil.rmtree(is_.klasor, ignore_errors=True)


def eski_isleri_temizle(gun: int = 14) -> int:
    """`gun` günden eski iş klasörlerini ve dönüşüm önbelleğini siler. Silinen klasör sayısını döndürür."""
    sinir = time.time() - gun * 86400
    n = 0
    for klasor in list((CACHE / "isler").glob("*")) + list((CACHE / "donusum").glob("*.pdf")):
        try:
            if klasor.stat().st_mtime < sinir:
                shutil.rmtree(klasor) if klasor.is_dir() else klasor.unlink()
                n += 1
        except OSError:
            pass
    return n


YARIM_DURUMLAR = ("hepsi_gonderildi", "on_gonderildi", "on_basildi", "arka_gonderildi")


def yarim_is(saat: int = 48) -> Is | None:
    """Son `saat` içinde başlayıp bitmemiş (ör. arka yüzleri basılmamış) en son işi döndürür."""
    sinir = time.time() - saat * 3600
    adaylar = []
    for yol in (CACHE / "isler").glob("*/is.json"):
        try:
            adaylar.append((yol.stat().st_mtime, yol))
        except OSError:
            pass
    for zaman, yol in sorted(adaylar, reverse=True):   # en son dokunulan iş önce
        if zaman < sinir:
            break
        try:
            is_ = Is(**json.loads(yol.read_text()))
        except (OSError, ValueError, TypeError):
            continue
        if is_.gecmis and not is_.deneme:
            # "cups_no" yoksa eski sürümle basılmış iştir; durumu güvenilir değil, sorulmaz
            return is_ if is_.durum in YARIM_DURUMLAR and "cups_no" in is_.gecmis[-1] else None
    return None


def hazirla(dosya: str, duzen: str = "1", arkali_onlu: bool = False, sayfalar: str | None = None,
            kopya: int = 1, yazici: str | None = None) -> Is:
    if duzen not in DUZENLER:
        raise YazdirHata(t("hata.duzen", liste=", ".join(DUZENLER)))
    if duzen == "kitapcik":
        arkali_onlu = True
    is_id = time.strftime("%Y%m%d-%H%M%S")
    klasor = CACHE / "isler" / is_id
    n = 1
    while klasor.exists():
        n += 1
        klasor = CACHE / "isler" / f"{is_id}-{n:03d}"   # sıfır dolgulu: ad sırası = oluşturma sırası
    klasor.mkdir(parents=True)
    try:
        pdf = pdfe_cevir(Path(dosya), klasor)
        reader = PdfWriter(clone_from=str(pdf))   # sayfalar writer'a bağlı olsun (bkz. _yeni_sayfa)
        secim = sayfa_secimi(sayfalar, len(reader.pages))
        yuzler = yuzleri_olustur(reader, secim, duzen)
    except Exception:
        shutil.rmtree(klasor, ignore_errors=True)
        raise
    if arkali_onlu and len(yuzler) % 2 and kopya > 1:
        yuzler = yuzler + [_bos_yuz()]  # her kopya yeni kâğıtta başlasın
    yuzler = yuzler * max(1, kopya)

    _yaz(yuzler, klasor / "yuzler.pdf")
    is_ = Is(id=klasor.name, klasor=str(klasor), kaynak=str(Path(dosya).expanduser().resolve()), duzen=duzen,
             arkali_onlu=arkali_onlu, kopya=max(1, kopya), yazici=yazici or varsayilan_yazici(),
             kaynak_sayfa=len(reader.pages), secilen_sayfa=len(secim), yuz_sayisi=len(yuzler),
             kagit=(len(yuzler) + 1) // 2 if arkali_onlu else len(yuzler))
    if arkali_onlu:
        is_.arka_180 = bool(ayarlar().get("arka_180", False))
        dondur = is_.arka_180 != _yatay_duzen(duzen)
        onler = [_a4_dikey(y, False) for y in yuzler[0::2]]
        arkalar = [_a4_dikey(y, dondur) for y in yuzler[1::2]]
        _yaz(onler, klasor / "on.pdf")
        is_.on_sayisi, is_.arka_sayisi = len(onler), len(arkalar)
        if arkalar:
            if len(onler) > len(arkalar):
                arkalar.append(_bos_yuz())
                is_.arka_bos_sayfa = True
            _yaz(list(reversed(arkalar)), klasor / "arka.pdf")
    is_.kaydet()
    log.info("hazırlandı %s: %s düzen=%s arkalı=%s yüz=%d kâğıt=%d", is_.id, is_.kaynak, duzen, arkali_onlu,
             is_.yuz_sayisi, is_.kagit)
    return is_


def _deneme_yuzu(yazi: str) -> PageObject:
    """Üstte büyük ok ve 'ÜST', ortada yüzün adı olan A4 sayfa (Helvetica, WinAnsi)."""
    p = _yeni_sayfa(A4_W, A4_H)
    p[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/F1"): DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})})})

    def metin(m: str, boyut: int, y: float) -> bytes:
        x = (A4_W - len(m) * boyut * 0.68) / 2  # kaba ortalama
        return f"BT /F1 {boyut} Tf 1 0 0 1 {x:.1f} {y} Tm (".encode() + m.encode("cp1252") + b") Tj ET\n"

    icerik = DecodedStreamObject()
    icerik.set_data(b"0 g\n297.6 790 m 217.6 650 l 377.6 650 l f\n272.6 500 50 150 re f\n"
                    + metin(t("deneme.ust"), 40, 440)
                    + metin(yazi, 72, 300))
    p[NameObject("/Contents")] = icerik
    return p


def deneme_hazirla(yazici: str | None = None) -> Is:
    """Arka yüz yönünü belirlemek için tek kâğıtlık arkalı önlü deneme işi."""
    yol = CACHE / "deneme.pdf"
    yol.parent.mkdir(parents=True, exist_ok=True)
    _yaz([_deneme_yuzu(t("deneme.on")), _deneme_yuzu(t("deneme.arka"))], yol)
    is_ = hazirla(str(yol), "1", True, yazici=yazici)
    is_.deneme = True
    is_.kaydet()
    return is_


def deneme_sonucu(arka_dogru: bool) -> bool:
    """Deneme sonucunu kaydeder; yeni arka_180 değerini döndürür."""
    yeni = bool(ayarlar().get("arka_180", False)) != (not arka_dogru)
    ayar_kaydet(arka_180=yeni, arka_180_deneme=time.strftime("%Y-%m-%d"))
    return yeni


def onizleme(is_: Is, cozunurluk: int = 40, en_fazla: int | None = None) -> list[Path]:
    """Yüzlerin PNG önizlemeleri. Sayfalar parçalara bölünüp aynı anda birkaç pdftoppm ile çizilir."""
    hedef = is_.yol / "onizleme"
    hedef.mkdir(exist_ok=True)
    for eski in hedef.glob("*.png"):
        eski.unlink()
    toplam = min(is_.yuz_sayisi, en_fazla or is_.yuz_sayisi)
    parca = max(4, -(-toplam // min(8, os.cpu_count() or 2)))
    kaynak = str(is_.dosya("yuzler.pdf"))

    def ciz(bas: int) -> None:
        son = min(toplam, bas + parca - 1)
        subprocess.run(["pdftoppm", "-r", str(cozunurluk), "-png", "-f", str(bas), "-l", str(son),
                        kaynak, str(hedef / "yuz")], check=True, capture_output=True)

    with ThreadPoolExecutor() as havuz:
        list(havuz.map(ciz, range(1, toplam + 1, parca)))
    return sorted(hedef.glob("yuz-*.png"), key=lambda y: int(y.stem.rsplit("-", 1)[1]))


# ---------------------------------------------------------------- yazıcı
# İş ve yazıcı durumu CUPS'a doğrudan sorulur (pycups). Kayıt dosyası taramak ve "kuyrukta yok = bitti"
# varsaymak, iptal edilen ya da hata veren işi "basıldı" sanmaya yol açıyordu.
IS_BEKLIYOR, IS_TUTULUYOR, IS_ISLENIYOR, IS_DURDU, IS_IPTAL, IS_HATA, IS_BITTI = 3, 4, 5, 6, 7, 8, 9
YAZICI_BOSTA, YAZICI_BASIYOR, YAZICI_DURDU = 3, 4, 5

# printer-state-reasons (sonundaki -error/-warning/-report atılır) -> uyarı kodu (dil.py: uyari.*)
UYARI_NEDENLERI = {
    "media-empty": "kagit_yok", "media-needed": "kagit_yok", "input-tray-missing": "kagit_yok",
    "media-jam": "kagit_sikisti", "door-open": "kapak_acik", "cover-open": "kapak_acik",
    "toner-empty": "toner", "marker-supply-empty": "toner",
    "offline": "baglanti_yok", "connecting-to-device": "baglanti_yok", "timed-out": "baglanti_yok",
}


def _cups():
    try:
        import cups
    except ImportError:
        raise YazdirHata(t("hata.pycups")) from None
    try:
        return cups.Connection()
    except RuntimeError as e:
        raise YazdirHata(t("hata.cups_baglanti", ayrinti=e)) from None


def is_durumu(cups_no: int) -> tuple[int, str]:
    a = _cups().getJobAttributes(cups_no, requested_attributes=["job-state", "job-state-reasons"])
    neden = a.get("job-state-reasons", "")
    return int(a["job-state"]), ",".join(neden) if isinstance(neden, list) else str(neden)


def yazici_bilgisi(yazici: str) -> dict:
    """{'durum': 3/4/5, 'uyarilar': [kod…], 'nedenler': [ham…], 'kuyruk': n} — hızlı (tek IPP isteği)."""
    c = _cups()
    a = c.getPrinterAttributes(yazici, requested_attributes=[
        "printer-state", "printer-state-reasons", "queued-job-count"])
    nedenler = [n for n in a.get("printer-state-reasons", []) if n != "none"]
    uyarilar = []
    for n in nedenler:
        kod = UYARI_NEDENLERI.get(re.sub(r"-(error|warning|report)$", "", n))
        if kod and kod not in uyarilar:
            uyarilar.append(kod)
    return {"durum": int(a.get("printer-state", 0)), "uyarilar": uyarilar, "nedenler": nedenler,
            "kuyruk": int(a.get("queued-job-count", 0))}


def yazici_durumu(yazici: str | None = None) -> dict:
    yazici = yazici or varsayilan_yazici()
    p = subprocess.run(["lpstat", "-l", "-p", yazici or ""], capture_output=True, text=True).stdout
    o = subprocess.run(["lpstat", "-o", yazici or ""], capture_output=True, text=True).stdout
    uyari = re.search(r"Alerts:\s*(.*)", p)
    return {
        "yazici": yazici,
        "durum": p.splitlines()[0] if p else t("hata.yazici_yok"),
        "uyarilar": uyari.group(1).strip() if uyari else "",
        "kuyruk": [l.split()[0] for l in o.splitlines() if l.strip()],
        "son_hatalar": son_hatalar(dakika=5),
    }


def son_hatalar(dakika: int = 5, since: str | None = None) -> list[str]:
    r = subprocess.run(["journalctl", "-u", "cups", "--since", since or f"-{dakika}min", "--no-pager", "-q"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if "ERROR" in l or "error" in l.lower()][-5:]


def kuyrugu_temizle(yazici: str | None = None) -> None:
    yazici = yazici or varsayilan_yazici()
    log.info("kuyruk temizlendi: %s", yazici)
    subprocess.run(["cancel", "-a", yazici], capture_output=True)
    subprocess.run(["cupsenable", yazici], capture_output=True)


def _lp(yol: Path, yazici: str) -> tuple[str, int]:
    r = subprocess.run(["lp", "-d", yazici, "-o", "media=A4", "-o", "fit-to-page", str(yol)],
                       capture_output=True, text=True)
    m = re.search(r"request id is (\S+-(\d+))", r.stdout)
    if r.returncode != 0 or not m:
        raise YazdirHata(t("hata.gonderilemedi", ayrinti=r.stderr.strip() or r.stdout.strip()))
    return m.group(1), int(m.group(2))


def izle(is_: Is, bildir=None, dur=None, aralik: float = 1.5) -> str:
    """İşin son gönderilen adımını CUPS'ta biter ya da durdurulana kadar izler.

    Döner: 'bitti' | 'iptal' | 'hata' | 'durduruldu' (dur olayı geldi; iş yazıcıda sürer, sonra devam edilir).
    Süre sınırı yoktur: kâğıt bitse, kapak açılsa, kablo çıksa da iş bekler. bildir(kod) her uyarı
    değişiminde çağrılır (kod: 'kagit_yok', 'baglanti_yok', … ya da None = sorun kalktı).
    Yazıcı CUPS'ta durdurulmuşsa (bağlantı koptuğunda hp arka ucu böyle yapar) 30 sn'de bir yeniden
    etkinleştirilir; iş kaldığı yerden sürer.
    """
    k = is_.gecmis[-1]
    adim, no = k["adim"], k["cups_no"]
    son_uyari, son_etkinlestirme = None, 0.0
    while True:
        if dur is not None and dur.is_set():
            sonuc = "durduruldu"
            break
        durum, neden = is_durumu(no)
        if durum == IS_BITTI:
            _yazicinin_bitmesini_bekle(is_.yazici, dur)
            sonuc = "bitti"
            break
        if durum in (IS_IPTAL, IS_HATA):
            sonuc = "iptal" if durum == IS_IPTAL else "hata"
            k["neden"] = neden
            break
        y = yazici_bilgisi(is_.yazici)
        uyari = y["uyarilar"][0] if y["uyarilar"] else None
        if y["durum"] == YAZICI_DURDU:
            uyari = uyari or "yazici_durdu"
            if time.time() - son_etkinlestirme > 30:
                subprocess.run(["cupsenable", is_.yazici], capture_output=True)
                son_etkinlestirme = time.time()
        if uyari != son_uyari:
            (log.warning if uyari else log.info)("iş %s (%s): uyarı %s, nedenler %s", is_.id, adim, uyari,
                                                 y["nedenler"])
            if bildir:
                bildir(uyari)
            son_uyari = uyari
        time.sleep(aralik)
    if son_uyari and bildir:
        bildir(None)
    onceki = {"hepsi": "hazir", "on": "hazir", "arka": "on_basildi"}[adim]
    if sonuc == "bitti":
        is_.durum = {"hepsi": "bitti", "on": "on_basildi" if is_.arka_sayisi else "bitti", "arka": "bitti"}[adim]
    elif sonuc in ("iptal", "hata"):
        is_.durum = onceki   # aynı adım yeniden denenebilir
    k["sonuc"] = sonuc
    is_.kaydet()
    log.info("iş %s adım %s: %s %s", is_.id, adim, sonuc, k.get("neden", ""))
    return sonuc


def _yazicinin_bitmesini_bekle(yazici: str, dur=None, en_cok: float = 90) -> None:
    """CUPS işi bitti dese de son sayfa yazıcıda basılıyor olabilir; kâğıtlar alınmadan önce yazıcının
    boşa çıkmasını bekler (en çok `en_cok` sn)."""
    son = time.time() + en_cok
    while time.time() < son and not (dur is not None and dur.is_set()):
        try:
            if yazici_bilgisi(yazici)["durum"] != YAZICI_BASIYOR:
                return
        except YazdirHata:
            return
        time.sleep(1)


def bas(is_: Is, adim: str, bekleyerek: bool = True, bildir=None, dur=None) -> str:
    """adim: 'hepsi' (tek yüz), 'on' veya 'arka' (arkalı önlü). Sonuç için bkz. izle()."""
    if not is_.yazici:
        raise YazdirHata(t("hata.yazici_yok"))
    if adim == "hepsi":
        if is_.arkali_onlu:
            raise YazdirHata(t("hata.arkali_is"))
        dosya = is_.dosya("yuzler.pdf")
    elif adim == "on":
        if not is_.arkali_onlu:
            raise YazdirHata(t("hata.tek_yuz_is"))
        dosya = is_.dosya("on.pdf")
    elif adim == "arka":
        if not is_.arkali_onlu or not is_.arka_sayisi:
            raise YazdirHata(t("hata.arka_yok"))
        dosya = is_.dosya("arka.pdf")
    else:
        raise YazdirHata(t("hata.adim", adim=adim))
    if not dosya.exists():
        raise YazdirHata(t("hata.dosya_yok", yol=dosya))
    if yazici_bilgisi(is_.yazici)["kuyruk"]:
        raise YazdirHata(t("hata.kuyruk_dolu"))

    ad, no = _lp(dosya, is_.yazici)
    is_.gecmis.append({"adim": adim, "cups": ad, "cups_no": no, "zaman": time.strftime("%Y-%m-%d %H:%M:%S")})
    is_.durum = f"{adim}_gonderildi"
    is_.kaydet()
    log.info("iş %s adım %s yazıcıya gönderildi: %s", is_.id, adim, ad)
    return izle(is_, bildir, dur) if bekleyerek else "gonderildi"

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

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

A4_W, A4_H = 595.28, 841.89

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "yazdir"
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yazdir" / "config.json"

OFFICE_EXT = {".doc", ".docx", ".odt", ".rtf", ".txt", ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

DUZENLER = {
    "1": "Her yüze 1 sayfa",
    "2": "Her yüze 2 sayfa (yan yana)",
    "4": "Her yüze 4 sayfa",
    "kitapcik": "Kitapçık (A5, ortadan katlanır)",
}


class YazdirHata(Exception):
    pass


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
    kaynak = Path(kaynak).expanduser().resolve()
    if not kaynak.exists():
        raise YazdirHata(f"Dosya bulunamadı: {kaynak}")
    ext = kaynak.suffix.lower()
    hedef = hedef_klasor / "kaynak.pdf"
    if ext == ".pdf":
        shutil.copyfile(kaynak, hedef)
    elif ext in OFFICE_EXT:
        profil = CACHE / "lo-profil"
        r = subprocess.run(
            ["soffice", f"-env:UserInstallation=file://{profil}", "--headless",
             "--convert-to", "pdf", "--outdir", str(hedef_klasor), str(kaynak)],
            capture_output=True, text=True, timeout=300)
        cikti = hedef_klasor / (kaynak.stem + ".pdf")
        if not cikti.exists():
            raise YazdirHata(f"LibreOffice dönüştüremedi: {r.stderr.strip() or r.stdout.strip()}")
        cikti.rename(hedef)
    elif ext in IMAGE_EXT:
        r = subprocess.run(["magick", str(kaynak), "-auto-orient", str(hedef)], capture_output=True, text=True)
        if r.returncode != 0:
            raise YazdirHata(f"Resim PDF'e çevrilemedi: {r.stderr.strip()}")
    else:
        raise YazdirHata(f"Desteklenmeyen dosya türü: {ext}")
    return hedef


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
            raise YazdirHata(f"Sayfa aralığı anlaşılamadı: '{parca}' (örnek: 1-5,8,10-)")
        if a < 1 or b > toplam or a > b:
            raise YazdirHata(f"Geçersiz sayfa aralığı: '{parca}' (belge {toplam} sayfa)")
        sonuc.extend(range(a, b + 1))
    return sonuc


# ---------------------------------------------------------------- yerleştirme
def _yerlestir(hedef: PageObject, kaynak: PageObject, x: float, y: float, w: float, h: float) -> None:
    """Kaynak sayfayı (x, y, w, h) kutusuna oranını koruyarak ortalar; gerekirse 90° döndürür."""
    kaynak.transfer_rotation_to_content()
    kutu = kaynak.cropbox
    x0, y0 = float(kutu.left), float(kutu.bottom)
    sw, sh = float(kutu.width), float(kutu.height)
    duz = min(w / sw, h / sh)
    yan = min(w / sh, h / sw)
    t = Transformation().translate(-x0, -y0)
    if yan > duz * 1.05:
        k = yan
        t = t.rotate(90).translate(sh, 0)
        sw, sh = sh, sw
    else:
        k = duz
    t = t.scale(k).translate(x + (w - sw * k) / 2, y + (h - sh * k) / 2)
    hedef.merge_transformed_page(kaynak, t)


def _yuz(slotlar, sayfalar, yatay: bool) -> PageObject:
    W, H = (A4_H, A4_W) if yatay else (A4_W, A4_H)
    p = PageObject.create_blank_page(width=W, height=H)
    for (x, y, w, h), s in zip(slotlar, sayfalar):
        if s is not None:
            _yerlestir(p, s, x, y, w, h)
    return p


def yuzleri_olustur(reader: PdfReader, secim: list[int], duzen: str) -> list[PageObject]:
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
    raise YazdirHata(f"Bilinmeyen düzen: {duzen}")


def _yatay_duzen(duzen: str) -> bool:
    return duzen in ("2", "kitapcik")


def _a4_dikey(yuz: PageObject, dondur_180: bool) -> PageObject:
    """Yüzü A4 dikey sayfaya yerleştirir (yataysa hep aynı yöne 90° döner); istenirse 180° çevirir."""
    p = PageObject.create_blank_page(width=A4_W, height=A4_H)
    _yerlestir(p, yuz, 0, 0, A4_W, A4_H)
    if dondur_180:
        p.add_transformation(Transformation().rotate(180).translate(A4_W, A4_H))
    return p


def _bos_yuz() -> PageObject:
    """Boş arka yüz. Sürücü tümüyle boş sayfayı atlarsa sıra kayar; bu yüzden gözle
    görülmeyecek kadar küçük, açık gri bir nokta konur."""
    p = PageObject.create_blank_page(width=A4_W, height=A4_H)
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
    durum: str = "hazir"          # hazir -> on_basildi -> bitti
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
                raise YazdirHata("Hazırlanmış iş yok. Önce 'yazdir hazirla DOSYA' çalıştırın.")
            yol = isler[-1]
        else:
            yol = CACHE / "isler" / is_id / "is.json"
            if not yol.exists():
                raise YazdirHata(f"İş bulunamadı: {is_id}")
        return cls(**json.loads(yol.read_text()))

    def ozet(self) -> str:
        s = [f"İş: {self.id}",
             f"Kaynak: {self.kaynak} ({self.kaynak_sayfa} sayfa, {self.secilen_sayfa} sayfa seçildi)",
             f"Düzen: {DUZENLER[self.duzen]}" + (f", {self.kopya} kopya" if self.kopya > 1 else ""),
             f"Baskı: {'elle arkalı önlü' if self.arkali_onlu else 'tek yüz'} — {self.yuz_sayisi} yüz, {self.kagit} kâğıt",
             f"Yazıcı: {self.yazici}"]
        if self.arkali_onlu:
            s.append(f"Adım 1: {self.on_sayisi} ön yüz • Adım 2: {self.arka_sayisi} arka yüz (ters sırayla)")
            if self.arka_bos_sayfa:
                s.append("Not: Son kâğıdın arkası boş kalacak (kâğıt ayırmaya gerek yok).")
            elif self.son_kagidi_ayir:
                s.append("Not: Son kâğıdın arkası boş kalacak; arka yüzden önce o kâğıt ayrılmalı.")
        s.append(f"Durum: {self.durum}")
        return "\n".join(s)

    def kagit_talimati(self) -> str:
        nasil = "yönünü değiştirmeden (çevirmeden, döndürmeden), basılı yüzü aşağıda tepsiye geri koyun."
        if self.son_kagidi_ayir and not self.arka_bos_sayfa:  # eski işler
            return (f"Ön yüzler basıldı. Önce tomarın EN ÜSTÜNDEKİ (en son basılan) kâğıdı ayırın — onun arkası "
                    f"boş kalacak. Kalan {self.arka_sayisi} kâğıdı " + nasil)
        t = f"Ön yüzler basıldı. Çıkan {self.on_sayisi} kâğıdın HEPSİNİ " + nasil
        if self.arka_bos_sayfa:
            t += " Boş kâğıt ayırmayın: en son basılan kâğıt arkası boş olarak geçecek."
        return t


def hazirla(dosya: str, duzen: str = "1", arkali_onlu: bool = False, sayfalar: str | None = None,
            kopya: int = 1, yazici: str | None = None) -> Is:
    if duzen not in DUZENLER:
        raise YazdirHata(f"Düzen şunlardan biri olmalı: {', '.join(DUZENLER)}")
    if duzen == "kitapcik":
        arkali_onlu = True
    is_id = time.strftime("%Y%m%d-%H%M%S")
    klasor = CACHE / "isler" / is_id
    n = 1
    while klasor.exists():
        n += 1
        klasor = CACHE / "isler" / f"{is_id}-{n}"
    klasor.mkdir(parents=True)
    try:
        pdf = pdfe_cevir(Path(dosya), klasor)
        reader = PdfReader(str(pdf))
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
    return is_


def _deneme_yuzu(yazi: str) -> PageObject:
    """Üstte büyük ok ve 'ÜST', ortada yüzün adı olan A4 sayfa (Helvetica, WinAnsi)."""
    p = PageObject.create_blank_page(width=A4_W, height=A4_H)
    p[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/F1"): DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})})})

    def metin(t: str, boyut: int, y: float) -> bytes:
        x = (A4_W - len(t) * boyut * 0.68) / 2  # kaba ortalama
        return f"BT /F1 {boyut} Tf 1 0 0 1 {x:.1f} {y} Tm (".encode() + t.encode("cp1252") + b") Tj ET\n"

    icerik = DecodedStreamObject()
    icerik.set_data(b"0 g\n297.6 790 m 217.6 650 l 377.6 650 l f\n272.6 500 50 150 re f\n"
                    + metin("ÜST", 40, 440)
                    + metin(yazi, 72, 300))
    p[NameObject("/Contents")] = icerik
    return p


def deneme_hazirla(yazici: str | None = None) -> Is:
    """Arka yüz yönünü belirlemek için tek kâğıtlık arkalı önlü deneme işi."""
    yol = CACHE / "deneme.pdf"
    yol.parent.mkdir(parents=True, exist_ok=True)
    _yaz([_deneme_yuzu("ÖN YÜZ"), _deneme_yuzu("ARKA YÜZ")], yol)
    is_ = hazirla(str(yol), "1", True, yazici=yazici)
    is_.deneme = True
    is_.kaydet()
    return is_


DENEME_SORUSU = ("Kâğıdı kitap sayfası çevirir gibi yan kenarından çevirin.\n"
                 "Ön yüzdeki ok yukarıyı gösterirken arka yüzdeki ok da YUKARIYI gösteriyor mu?")


def deneme_sonucu(arka_dogru: bool) -> bool:
    """Deneme sonucunu kaydeder; yeni arka_180 değerini döndürür."""
    yeni = bool(ayarlar().get("arka_180", False)) != (not arka_dogru)
    ayar_kaydet(arka_180=yeni)
    return yeni


def onizleme(is_: Is, cozunurluk: int = 40, en_fazla: int | None = None) -> list[Path]:
    hedef = is_.yol / "onizleme"
    hedef.mkdir(exist_ok=True)
    for eski in hedef.glob("*.png"):
        eski.unlink()
    arg = ["pdftoppm", "-r", str(cozunurluk), "-png"]
    if en_fazla:
        arg += ["-l", str(en_fazla)]
    subprocess.run(arg + [str(is_.dosya("yuzler.pdf")), str(hedef / "yuz")], check=True)
    return sorted(hedef.glob("yuz-*.png"))


# ---------------------------------------------------------------- yazıcı
def yazici_durumu(yazici: str | None = None) -> dict:
    yazici = yazici or varsayilan_yazici()
    p = subprocess.run(["lpstat", "-l", "-p", yazici or ""], capture_output=True, text=True).stdout
    o = subprocess.run(["lpstat", "-o", yazici or ""], capture_output=True, text=True).stdout
    uyari = re.search(r"Alerts:\s*(.*)", p)
    return {
        "yazici": yazici,
        "durum": p.splitlines()[0] if p else "yazıcı bulunamadı",
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
    subprocess.run(["cancel", "-a", yazici], capture_output=True)
    subprocess.run(["cupsenable", yazici], capture_output=True)


def _lp(yol: Path, yazici: str) -> str:
    r = subprocess.run(["lp", "-d", yazici, "-o", "media=A4", "-o", "fit-to-page", str(yol)],
                       capture_output=True, text=True)
    m = re.search(r"request id is (\S+)", r.stdout)
    if r.returncode != 0 or not m:
        raise YazdirHata(f"Yazıcıya gönderilemedi: {r.stderr.strip() or r.stdout.strip()}")
    return m.group(1)


def bekle(cups_is: str, baslangic: str, zaman_asimi: int = 900, ilerleme=None) -> str:
    """'bitti' | 'kagit_yok' | 'zaman_asimi'. kagit_yok durumunda iş kuyrukta bekler."""
    son = time.time() + zaman_asimi
    while time.time() < son:
        o = subprocess.run(["lpstat", "-o"], capture_output=True, text=True).stdout
        if cups_is not in o.split():
            return "bitti"
        j = subprocess.run(["journalctl", "-u", "cups", "--since", baslangic, "--no-pager", "-q"],
                           capture_output=True, text=True).stdout
        if "media-empty" in j:
            return "kagit_yok"
        if ilerleme:
            ilerleme()
        time.sleep(2)
    return "zaman_asimi"


def bas(is_: Is, adim: str, bekleyerek: bool = True, ilerleme=None) -> str:
    """adim: 'hepsi' (tek yüz), 'on' veya 'arka' (arkalı önlü)."""
    if not is_.yazici:
        raise YazdirHata("Yazıcı bulunamadı.")
    if adim == "hepsi":
        if is_.arkali_onlu:
            raise YazdirHata("Bu iş arkalı önlü; önce 'on', sonra 'arka' basılmalı.")
        dosya = is_.dosya("yuzler.pdf")
    elif adim == "on":
        if not is_.arkali_onlu:
            raise YazdirHata("Bu iş tek yüz; 'hepsi' kullanın.")
        dosya = is_.dosya("on.pdf")
    elif adim == "arka":
        if not is_.arkali_onlu or not is_.arka_sayisi:
            raise YazdirHata("Bu işin arka yüzü yok.")
        dosya = is_.dosya("arka.pdf")
    else:
        raise YazdirHata(f"Bilinmeyen adım: {adim}")
    if subprocess.run(["lpstat", "-o", is_.yazici], capture_output=True, text=True).stdout.strip():
        raise YazdirHata("Yazıcı kuyruğunda bekleyen iş var. Önce kuyruğu temizleyin ya da bitmesini bekleyin.")

    baslangic = time.strftime("%Y-%m-%d %H:%M:%S")
    cups_is = _lp(dosya, is_.yazici)
    is_.gecmis.append({"adim": adim, "cups": cups_is, "zaman": baslangic})
    sonuc = bekle(cups_is, baslangic, ilerleme=ilerleme) if bekleyerek else "gonderildi"
    if sonuc in ("bitti", "gonderildi"):
        is_.durum = {"hepsi": "bitti", "on": "on_basildi" if is_.arka_sayisi else "bitti", "arka": "bitti"}[adim]
    is_.gecmis[-1]["sonuc"] = sonuc
    is_.kaydet()
    return sonuc

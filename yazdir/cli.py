"""yazdir — komut satırı. Claude ve kullanıcı için.

  yazdir hazirla DOSYA [-d 1|2|4|kitapcik] [-a] [-s 1-5,8] [-k 2] [-y YAZICI]
  yazdir onizle [IS]            önizleme PNG'lerini üretir, yollarını yazar
  yazdir bilgi [IS]             işin özeti
  yazdir bas [IS] hepsi|on|arka --onayli   iş adımını yazıcıya gönderir (bitene kadar bekler)
  yazdir deneme                 arka yüz yön denemesi (1 kâğıt) hazırlar; sonra bas on / bas arka
  yazdir deneme-sonucu evet|hayir   arka yüzdeki ok yukarıyı gösterdi mi? ayarı buna göre kaydeder
  yazdir durum                  yazıcı durumu, kuyruk, son hatalar
  yazdir temizle                kuyruktaki tüm işleri iptal eder, yazıcıyı etkinleştirir
  yazdir yazicilar              yazıcıları listeler
  yazdir varsayilan YAZICI      varsayılan yazıcıyı kaydeder
IS verilmezse son hazırlanan iş kullanılır. --json ile makine okunur çıktı.
"""
import argparse
import json
import sys
from dataclasses import asdict

from . import core


def _cikti(veri, metin, js):
    print(json.dumps(veri, ensure_ascii=False, indent=2) if js else metin)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="yazdir", description="Elle arkalı önlü, çoklu sayfa ve kitapçık baskısı.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON çıktı")
    alt = ap.add_subparsers(dest="komut", required=True)

    h = alt.add_parser("hazirla", help="belgeyi baskıya hazırla (yazdırmaz)")
    h.add_argument("dosya")
    h.add_argument("-d", "--duzen", default="1", choices=list(core.DUZENLER))
    h.add_argument("-a", "--arkali-onlu", action="store_true")
    h.add_argument("-s", "--sayfalar", help="ör. 1-5,8,10-")
    h.add_argument("-k", "--kopya", type=int, default=1)
    h.add_argument("-y", "--yazici")
    h.add_argument("--onizleme", action="store_true", help="hazırlarken önizleme de üret")

    for ad in ("onizle", "bilgi"):
        p = alt.add_parser(ad)
        p.add_argument("is_id", nargs="?", default="son")
        if ad == "onizle":
            p.add_argument("-r", "--cozunurluk", type=int, default=40)

    b = alt.add_parser("bas", help="iş adımını yazdır")
    b.add_argument("args", nargs="+", metavar="[IS] ADIM")
    b.add_argument("--beklemeden", action="store_true")
    b.add_argument("--onayli", action="store_true",
                   help="kullanıcı açıkça 'bas' dedi; bu bayrak olmadan hiçbir şey yazıcıya gönderilmez")

    alt.add_parser("deneme", help="arka yüz yön deneme sayfası hazırla")
    ds = alt.add_parser("deneme-sonucu", help="deneme sayfasının arka yüzü doğru mu çıktı")
    ds.add_argument("cevap", choices=["evet", "hayir"])
    alt.add_parser("durum")
    alt.add_parser("temizle")
    alt.add_parser("yazicilar")
    v = alt.add_parser("varsayilan")
    v.add_argument("yazici")

    a = ap.parse_args(argv)
    js = a.json
    try:
        if a.komut == "hazirla":
            is_ = core.hazirla(a.dosya, a.duzen, a.arkali_onlu, a.sayfalar, a.kopya, a.yazici)
            veri = asdict(is_)
            metin = is_.ozet()
            if a.onizleme:
                resimler = [str(p) for p in core.onizleme(is_)]
                veri["onizleme"] = resimler
                metin += "\nÖnizleme:\n  " + "\n  ".join(resimler)
            _cikti(veri, metin, js)
        elif a.komut == "onizle":
            is_ = core.Is.yukle(a.is_id)
            resimler = [str(p) for p in core.onizleme(is_, a.cozunurluk)]
            _cikti(resimler, "\n".join(resimler), js)
        elif a.komut == "bilgi":
            is_ = core.Is.yukle(a.is_id)
            _cikti(asdict(is_), is_.ozet(), js)
        elif a.komut == "bas":
            is_id, adim = (a.args if len(a.args) == 2 else ["son", a.args[0]])
            is_ = core.Is.yukle(is_id)
            if not a.onayli:
                raise core.YazdirHata(f"Yazdırılmadı: 'bas' için --onayli gerekir (kullanıcı onayı). İş {is_.id}, adım '{adim}'.")
            sonuc = core.bas(is_, adim, bekleyerek=not a.beklemeden)
            mesaj = {
                "bitti": "Baskı tamamlandı.",
                "gonderildi": "Yazıcıya gönderildi.",
                "kagit_yok": "Yazıcı 'kağıt yok' diyor. İş kuyrukta bekliyor; kağıdı düzeltin ya da 'yazdir temizle' ile iptal edin.",
                "zaman_asimi": "Baskı uzun sürdü; 'yazdir durum' ile kontrol edin.",
            }[sonuc]
            if sonuc in ("bitti", "gonderildi") and adim == "on" and is_.arka_sayisi:
                mesaj += "\n" + is_.kagit_talimati() + f"\nSonra (yeni onayla): yazdir bas {is_.id} arka --onayli"
            _cikti({"sonuc": sonuc, "is": is_.id, "durum": is_.durum, "mesaj": mesaj}, mesaj, js)
            return 0 if sonuc in ("bitti", "gonderildi") else 2
        elif a.komut == "deneme":
            is_ = core.deneme_hazirla()
            metin = (is_.ozet() + "\n\nOnay sonrası: yazdir bas on --onayli, kâğıdı geri koyup yazdir bas arka --onayli.\n"
                     + core.DENEME_SORUSU + "\nCevap: yazdir deneme-sonucu evet|hayir")
            _cikti(asdict(is_), metin, js)
        elif a.komut == "deneme-sonucu":
            yeni = core.deneme_sonucu(a.cevap == "evet")
            _cikti({"arka_180": yeni}, f"Kaydedildi: arka yüzler {'180° çevrilerek' if yeni else 'çevrilmeden'} basılacak.", js)
        elif a.komut == "durum":
            d = core.yazici_durumu()
            metin = (f"{d['durum']}\nUyarılar: {d['uyarilar'] or '-'}\nKuyruk: {', '.join(d['kuyruk']) or 'boş'}"
                     + ("\nSon hatalar:\n  " + "\n  ".join(d["son_hatalar"]) if d["son_hatalar"] else ""))
            _cikti(d, metin, js)
        elif a.komut == "temizle":
            core.kuyrugu_temizle()
            d = core.yazici_durumu()
            _cikti(d, f"Kuyruk temizlendi.\n{d['durum']}", js)
        elif a.komut == "yazicilar":
            y = core.yazicilar()
            _cikti({"yazicilar": y, "varsayilan": core.varsayilan_yazici()},
                   "\n".join(("* " if x == core.varsayilan_yazici() else "  ") + x for x in y), js)
        elif a.komut == "varsayilan":
            core.ayar_kaydet(yazici=a.yazici)
            _cikti({"varsayilan": a.yazici}, f"Varsayılan yazıcı: {a.yazici}", js)
    except core.YazdirHata as e:
        _cikti({"hata": str(e)}, f"HATA: {e}", js)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

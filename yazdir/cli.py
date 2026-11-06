"""yazdir — komut satırı. Yardım metni dil.py'de (cli.yardim), seçili dilde gösterilir."""
import argparse
import json
import sys
from dataclasses import asdict

from . import core
from .dil import t


def _cikti(veri, metin, js):
    print(json.dumps(veri, ensure_ascii=False, indent=2) if js else metin)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="yazdir", description=t("cli.aciklama"),
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=t("cli.yardim"))
    ap.add_argument("--json", action="store_true", help=t("cli.h.json"))
    alt = ap.add_subparsers(dest="komut", required=True)

    h = alt.add_parser("hazirla", help=t("cli.h.hazirla"))
    h.add_argument("dosya")
    h.add_argument("-d", "--duzen", default="1", choices=core.DUZENLER)
    h.add_argument("-a", "--arkali-onlu", action="store_true")
    h.add_argument("-s", "--sayfalar", help="1-5,8,10-")
    h.add_argument("-k", "--kopya", type=int, default=1)
    h.add_argument("-y", "--yazici")
    h.add_argument("--onizleme", action="store_true", help=t("cli.h.onizleme"))

    for ad in ("onizle", "bilgi"):
        p = alt.add_parser(ad)
        p.add_argument("is_id", nargs="?", default="son")
        if ad == "onizle":
            p.add_argument("-r", "--cozunurluk", type=int, default=40)

    b = alt.add_parser("bas", help=t("cli.h.bas"))
    b.add_argument("args", nargs="+", metavar="[IS] ADIM")
    b.add_argument("--beklemeden", action="store_true")
    b.add_argument("--onayli", action="store_true", help=t("cli.h.onayli"))

    alt.add_parser("deneme", help=t("cli.h.deneme"))
    ds = alt.add_parser("deneme-sonucu", help=t("cli.h.deneme_sonucu"))
    ds.add_argument("cevap", choices=["evet", "hayir"])
    alt.add_parser("durum")
    alt.add_parser("temizle")
    alt.add_parser("yazicilar")
    v = alt.add_parser("varsayilan")
    v.add_argument("yazici")
    dl = alt.add_parser("dil", help=t("cli.h.dil"))
    dl.add_argument("kod", choices=list(core.dil.DILLER))

    a = ap.parse_args(argv)
    core.gunluk_ac()
    js = a.json
    try:
        if a.komut == "hazirla":
            is_ = core.hazirla(a.dosya, a.duzen, a.arkali_onlu, a.sayfalar, a.kopya, a.yazici)
            veri = asdict(is_)
            metin = is_.ozet()
            if a.onizleme:
                resimler = [str(p) for p in core.onizleme(is_)]
                veri["onizleme"] = resimler
                metin += "\n" + t("cli.onizleme") + "\n  " + "\n  ".join(resimler)
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
                raise core.YazdirHata(t("cli.onay_yok", id=is_.id, adim=adim))
            def bildir(kod):
                print(t("cli.uyari", m=t(f"uyari.{kod}")) if kod else t("cli.uyari_kalkti"), file=sys.stderr, flush=True)

            sonuc = core.bas(is_, adim, bekleyerek=not a.beklemeden, bildir=bildir)
            if sonuc == "hata":
                mesaj = t("cli.hata_sonuc", neden=is_.gecmis[-1].get("neden") or "?")
            else:
                mesaj = t({"bitti": "cli.bitti", "gonderildi": "cli.gonderildi", "iptal": "cli.iptal"}[sonuc])
            if sonuc in ("bitti", "gonderildi") and adim == "on" and is_.arka_sayisi:
                mesaj += "\n" + is_.kagit_talimati() + "\n" + t("cli.sonra_arka", id=is_.id)
            _cikti({"sonuc": sonuc, "is": is_.id, "durum": is_.durum, "mesaj": mesaj}, mesaj, js)
            return 0 if sonuc in ("bitti", "gonderildi") else 2
        elif a.komut == "deneme":
            is_ = core.deneme_hazirla()
            metin = "\n".join([is_.ozet(), "", t("cli.deneme_sonra"), t("deneme.soru"), t("cli.deneme_cevap")])
            _cikti(asdict(is_), metin, js)
        elif a.komut == "deneme-sonucu":
            yeni = core.deneme_sonucu(a.cevap == "evet")
            _cikti({"arka_180": yeni}, t("cli.kaydedildi_180" if yeni else "cli.kaydedildi_duz"), js)
        elif a.komut == "durum":
            d = core.yazici_durumu()
            metin = "\n".join([d["durum"], t("cli.uyarilar", x=d["uyarilar"] or "-"),
                               t("cli.kuyruk", x=", ".join(d["kuyruk"]) or t("cli.bos"))])
            if d["son_hatalar"]:
                metin += "\n" + t("cli.son_hatalar") + "\n  " + "\n  ".join(d["son_hatalar"])
            _cikti(d, metin, js)
        elif a.komut == "temizle":
            core.kuyrugu_temizle()
            d = core.yazici_durumu()
            _cikti(d, t("cli.temizlendi") + "\n" + d["durum"], js)
        elif a.komut == "yazicilar":
            y = core.yazicilar()
            _cikti({"yazicilar": y, "varsayilan": core.varsayilan_yazici()},
                   "\n".join(("* " if x == core.varsayilan_yazici() else "  ") + x for x in y), js)
        elif a.komut == "varsayilan":
            core.ayar_kaydet(yazici=a.yazici)
            _cikti({"varsayilan": a.yazici}, t("cli.varsayilan", ad=a.yazici), js)
        elif a.komut == "dil":
            _cikti({"dil": core.dil_kaydet(a.kod)}, t("cli.dil"), js)
    except core.YazdirHata as e:
        _cikti({"hata": str(e)}, t("cli.hata", m=e), js)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

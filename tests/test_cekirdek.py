"""Çekirdek: sayfa yerleşimi, arka yüz sırası/yönü, CUPS izleme, yarım iş, temizlik, dil."""
import json
import os
import string
import threading
import time
import unittest

from yazdir import core, dil
from tests.yardimci import SahteCups, belge, sayfa_yazilari, ters_mi


class Yerlesim(unittest.TestCase):
    def setUp(self):
        core.ayar_kaydet(arka_180=False)

    def test_tek_sayfa_duzeni_cift_sayi(self):
        j = core.hazirla(belge(4), "1", True, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S1"], ["S3"]])
        # arka yüzler ters sırayla: tomarın üstündeki (son basılan) kâğıt önce geri girer
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [["S4"], ["S2"]])
        self.assertFalse(j.arka_bos_sayfa)
        self.assertEqual((j.on_sayisi, j.arka_sayisi, j.kagit), (2, 2, 2))

    def test_tek_sayi_bos_arka_basta(self):
        j = core.hazirla(belge(3), "1", True, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [[], ["S2"]])
        self.assertTrue(j.arka_bos_sayfa)
        self.assertIn("HEPSİNİ", j.kagit_talimati())

    def test_tek_sayfalik_belgenin_arkasi_yok(self):
        j = core.hazirla(belge(1), "1", True, yazici="X")
        self.assertEqual(j.arka_sayisi, 0)
        self.assertFalse(j.dosya("arka.pdf").exists())

    def test_ikili_duzen(self):
        j = core.hazirla(belge(5), "2", True, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S1", "S2"], ["S5"]])
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [[], ["S3", "S4"]])

    def test_dortlu_duzen(self):
        j = core.hazirla(belge(9), "4", True, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S1", "S2", "S3", "S4"], ["S9"]])
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [[], ["S5", "S6", "S7", "S8"]])

    def test_kitapcik_sirasi(self):
        j = core.hazirla(belge(8), "kitapcik", False, yazici="X")
        self.assertTrue(j.arkali_onlu)          # kitapçık her zaman arkalı önlü
        # kâğıt 1: ön [8|1] arka [2|7]; kâğıt 2: ön [6|3] arka [4|5]; arkalar ters sırayla
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S8", "S1"], ["S6", "S3"]])
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [["S4", "S5"], ["S2", "S7"]])

    def test_kopya_her_kopya_yeni_kagitta(self):
        j = core.hazirla(belge(3), "1", True, kopya=2, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S1"], ["S3"], ["S1"], ["S3"]])
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [[], ["S2"], [], ["S2"]])

    def test_dondurulmus_kaynak_sayfa(self):
        """/Rotate 90 olan sayfalar (taranmış belgeler) bozulmadan yerleşmeli."""
        from pypdf import PdfWriter
        w = PdfWriter(clone_from=belge(2, "dondurulmus"))
        for sayfa in w.pages:
            sayfa.rotate(90)
        yol = core.CACHE / "dondurulmus.pdf"
        w.write(str(yol))
        j = core.hazirla(str(yol), "1", True, yazici="X")
        self.assertEqual(sayfa_yazilari(j.dosya("on.pdf")), [["S1"]])
        self.assertEqual(sayfa_yazilari(j.dosya("arka.pdf")), [["S2"]])

    def test_sayfa_secimi(self):
        self.assertEqual(core.sayfa_secimi("1-3, 5, 8-", 9), [1, 2, 3, 5, 8, 9])
        self.assertEqual(core.sayfa_secimi("", 3), [1, 2, 3])
        for kotu in ("0", "4", "3-2", "a"):
            with self.assertRaises(core.YazdirHata):
                core.sayfa_secimi(kotu, 3)


class ArkaYon(unittest.TestCase):
    """arka_180 ayarı ve yatay düzenler (2'li/kitapçık) birlikte doğru dönüşü vermeli."""

    def yon(self, duzen, arka_180):
        core.ayar_kaydet(arka_180=arka_180)
        j = core.hazirla(belge(8), duzen, True, yazici="X")
        return ters_mi(j.dosya("on.pdf"), 0), ters_mi(j.dosya("arka.pdf"), 0)

    def test_tablo(self):
        beklenen = {  # (düzen, arka_180) -> arka yüz 180° dönük mü
            ("1", False): False, ("1", True): True,
            ("4", False): False, ("4", True): True,
            ("2", False): True, ("2", True): False,
            ("kitapcik", False): True, ("kitapcik", True): False,
        }
        for (duzen, ayar), arka_ters in beklenen.items():
            with self.subTest(duzen=duzen, arka_180=ayar):
                on, arka = self.yon(duzen, ayar)
                self.assertFalse(on, "ön yüz hiçbir zaman dönmemeli")
                self.assertEqual(arka, arka_ters)

    def tearDown(self):
        core.ayar_kaydet(arka_180=False)


class Izleme(unittest.TestCase):
    """core.bas/izle: dünkü hatanın kökü — akış hiçbir durumda sessizce kopmamalı."""

    def is_(self, n=4):
        return core.hazirla(belge(n), "1", True, yazici="X")

    def test_kagit_bitince_bekler_ve_devam_eder(self):
        cups = SahteCups([
            (core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR),
            (core.IS_ISLENIYOR, ["kagit_yok"], core.YAZICI_BASIYOR),
            (core.IS_ISLENIYOR, ["kagit_yok"], core.YAZICI_BASIYOR),
            (core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR),
            (core.IS_BITTI, [], core.YAZICI_BOSTA),
        ]).kur(self)
        uyarilar = []
        j = self.is_()
        self.assertEqual(core.bas(j, "on", bildir=uyarilar.append), "bitti")
        self.assertEqual(uyarilar, ["kagit_yok", None])          # bir kez uyarır, kalkınca haber verir
        self.assertEqual(j.durum, "on_basildi")
        self.assertEqual(cups.gonderilen, ["on.pdf"])
        self.assertEqual(core.Is.yukle(j.id).durum, "on_basildi")  # diske de yazıldı

    def test_iptal_basildi_sayilmaz(self):
        SahteCups([(core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR), (core.IS_IPTAL, [], core.YAZICI_BOSTA)]).kur(self)
        j = self.is_()
        self.assertEqual(core.bas(j, "on"), "iptal")
        self.assertEqual(j.durum, "hazir")

    def test_arka_iptal_edilirse_yeniden_denenebilir(self):
        SahteCups([(core.IS_BITTI, [], core.YAZICI_BOSTA)]).kur(self)
        j = self.is_()
        core.bas(j, "on")
        SahteCups([(core.IS_HATA, [], core.YAZICI_BOSTA)]).kur(self)
        self.assertEqual(core.bas(j, "arka"), "hata")
        self.assertEqual(j.durum, "on_basildi")

    def test_durdurulunca_is_yarim_kalir(self):
        SahteCups([(core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR)]).kur(self)
        dur = threading.Event()
        dur.set()
        j = self.is_()
        self.assertEqual(core.bas(j, "on", dur=dur), "durduruldu")
        self.assertEqual(j.durum, "on_gonderildi")
        self.assertEqual(core.yarim_is().id, j.id)

    def test_durdurulmus_yazici_yeniden_etkinlestirilir(self):
        cups = SahteCups([(core.IS_DURDU, [], core.YAZICI_DURDU)] * 3 + [(core.IS_BITTI, [], core.YAZICI_BOSTA)]).kur(self)
        uyarilar = []
        self.assertEqual(core.bas(self.is_(), "on", bildir=uyarilar.append), "bitti")
        self.assertGreaterEqual(cups.etkinlestirme, 1)
        self.assertEqual(uyarilar, ["yazici_durdu", None])

    def test_kuyruk_doluysa_gondermez(self):
        cups = SahteCups().kur(self)
        cups.yazici_bilgisi = lambda y: {"durum": 3, "uyarilar": [], "nedenler": [], "kuyruk": 1}
        from unittest import mock
        with mock.patch.object(core, "yazici_bilgisi", cups.yazici_bilgisi):
            with self.assertRaises(core.YazdirHata):
                core.bas(self.is_(), "on")
        self.assertEqual(cups.gonderilen, [])

    def test_yanlis_adim_reddedilir(self):
        SahteCups().kur(self)
        j = self.is_()
        for adim in ("hepsi", "yok"):
            with self.assertRaises(core.YazdirHata):
                core.bas(j, adim)
        tek = core.hazirla(belge(2), "1", False, yazici="X")
        with self.assertRaises(core.YazdirHata):
            core.bas(tek, "on")


class YarimIsVeTemizlik(unittest.TestCase):
    def test_eski_bicim_is_sorulmaz(self):
        j = core.hazirla(belge(2), "1", True, yazici="X")
        j.gecmis.append({"adim": "on", "cups": "X-1", "zaman": "", "sonuc": "bitti"})  # cups_no yok: eski sürüm
        j.durum = "on_basildi"
        j.kaydet()
        self.assertIsNone(core.yarim_is())

    def test_bitmis_is_sorulmaz(self):
        SahteCups().kur(self)
        j = core.hazirla(belge(2), "1", True, yazici="X")
        core.bas(j, "on")
        core.bas(j, "arka")
        self.assertEqual(j.durum, "bitti")
        self.assertIsNone(core.yarim_is())

    def test_basilmamis_is_silinir_basilmis_kalir(self):
        SahteCups().kur(self)
        a = core.hazirla(belge(2), "1", False, yazici="X")
        b = core.hazirla(belge(2), "1", False, yazici="X")
        core.bas(b, "hepsi")
        core.isi_sil(a)
        core.isi_sil(b)
        self.assertFalse(a.yol.exists())
        self.assertTrue(b.yol.exists())

    def test_eski_isler_temizlenir(self):
        j = core.hazirla(belge(2), "1", False, yazici="X")
        eski = time.time() - 30 * 86400
        os.utime(j.yol, (eski, eski))
        self.assertGreaterEqual(core.eski_isleri_temizle(14), 1)
        self.assertFalse(j.yol.exists())


class Onizleme(unittest.TestCase):
    def test_paralel_onizleme_sirali_ve_tam(self):
        j = core.hazirla(belge(23), "1", False, yazici="X")
        resimler = core.onizleme(j, 20, en_fazla=17)
        self.assertEqual(len(resimler), 17)
        self.assertEqual([int(r.stem.rsplit("-", 1)[1]) for r in resimler], list(range(1, 18)))


class Dil(unittest.TestCase):
    def tearDown(self):
        dil.ayarla("tr")

    def test_her_metin_iki_dilde_ayni_yer_tutucularla(self):
        alanlar = lambda m: {f for _, f, _, _ in string.Formatter().parse(m) if f}
        for k, v in dil.METINLER.items():
            with self.subTest(k):
                self.assertEqual(set(v), {"tr", "en"})
                self.assertEqual(alanlar(v["tr"]), alanlar(v["en"]))

    def test_dinamik_anahtarlar_var(self):
        kodlar = set(core.UYARI_NEDENLERI.values()) | {"yazici_durdu"}
        durumlar = {"hazir", "bitti", "on_basildi", "vazgecildi"} | set(core.YARIM_DURUMLAR)
        for k in [f"uyari.{x}" for x in kodlar] + [f"durum.{x}" for x in durumlar] + \
                 [f"duzen.{x}" for x in core.DUZENLER]:
            self.assertIn(k, dil.METINLER)

    def test_dil_secimi_kaydedilir(self):
        core.dil_kaydet("en")
        self.assertEqual(core.ayarlar()["dil"], "en")
        self.assertEqual(core.duzen_adi("kitapcik"), "Booklet (A5, folded in the middle)")
        core.dil_kaydet("tr")
        self.assertEqual(json.loads(core.CONFIG_FILE.read_text())["dil"], "tr")


if __name__ == "__main__":
    unittest.main()

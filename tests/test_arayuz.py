"""Pencere akışları, ekransız (offscreen). Gerçek core.bas/izle çalışır; yalnız CUPS sahtedir.

Asıl amaç, "ön yüzler basıldı ama arka yüz sorusu hiç gelmedi" türü hataların geri gelmemesi:
her senaryoda hangi pencerelerin hangi sırayla ve ANA iş parçacığında açıldığı denetlenir.
"""
import threading
import time
import unittest
from unittest import mock

from PySide6.QtWidgets import QApplication, QMessageBox

from yazdir import core, dil, gui
from tests.yardimci import SahteCups, belge

app = QApplication.instance() or QApplication([])
ANA = threading.get_ident()


def bekle(kosul, sure=15.0):
    son = time.time() + sure
    while time.time() < son:
        app.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return False


class Diyaloglar:
    """QMessageBox'ları yamalar ve kaydeder. cevap: başlık -> Yes/No; devam: arka yüz sorusunda Devam mı."""

    def __init__(self, test, cevap=None, devam=True):
        self.kayit, self.cevap, self.devam = [], cevap or {}, devam
        self.ana_disi = []
        d = self

        def kaydet(tur, baslik, metin):
            d.kayit.append((tur, baslik, metin))
            if threading.get_ident() != ANA:
                d.ana_disi.append(baslik)

        def soru(parent, baslik, metin, *a, **k):
            kaydet("soru", baslik, metin)
            return d.cevap.get(baslik, QMessageBox.Yes)

        def bilgi(parent, baslik, metin, *a, **k):
            kaydet("bilgi", baslik, metin)
            return QMessageBox.Ok

        def exec_(kutu):
            kaydet("cevir", kutu.windowTitle(), kutu.informativeText())
            dugmeler = kutu.buttons()
            kutu._secilen = dugmeler[0] if d.devam else dugmeler[-1]
            return 0

        def goster(kutu):  # yazıcı uyarısı (pencereyi kilitlemeyen kutu)
            kaydet("uyari", kutu.windowTitle(), kutu.text())

        for ad, yeni in (("question", staticmethod(soru)), ("information", staticmethod(bilgi)),
                         ("warning", staticmethod(bilgi)), ("critical", staticmethod(bilgi)),
                         ("exec", exec_), ("clickedButton", lambda kutu: kutu._secilen), ("show", goster)):
            y = mock.patch.object(QMessageBox, ad, yeni)
            y.start()
            test.addCleanup(y.stop)

    def turler(self):
        return [(k[0], k[1]) for k in self.kayit]


class Temel(unittest.TestCase):
    def setUp(self):
        dil.ayarla("tr")
        core.ayar_kaydet(arka_180=False, dil="tr")
        self.pencereler = []

    def tearDown(self):
        for p in self.pencereler:
            p._dur.set()
            if p.mesgul_mu():
                p._thread.quit()
                p._thread.wait()
            p.deleteLater()
        app.processEvents()

    def pencere(self, dosya=None, arkali=True, duzen="1"):
        with mock.patch.object(core, "yarim_is", return_value=None):
            p = gui.Pencere()
            self.pencereler.append(p)
            bekle(lambda: True, 0.3)
        if dosya:
            p.arkali.setChecked(arkali)
            for b in p.duzen_grup.buttons():
                if b.property("duzen") == duzen:
                    b.setChecked(True)
            p.dosya_ac(dosya)
            self.assertTrue(bekle(lambda: p.is_ is not None and not p.mesgul_mu()), "hazırlık bitmedi")
        return p


class BaskiAkisi(Temel):
    def test_kagit_bitse_de_arka_yuz_sorusu_gelir(self):
        """Dünkü hata: ön yüz sırasında sorun olunca akış bitiyordu, arka yüz hiç sorulmuyordu."""
        cups = SahteCups([
            (core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR),
            (core.IS_ISLENIYOR, ["kagit_yok"], core.YAZICI_BASIYOR),
            (core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR),
            (core.IS_BITTI, [], core.YAZICI_BOSTA),
        ]).kur(self)
        d = Diyaloglar(self)
        p = self.pencere(belge(4))
        p.yazdir()

        def ikinci_adim():
            return cups.gonderilen == ["on.pdf", "arka.pdf"] and not p.mesgul_mu() and not p._baski_suruyor
        # ikinci baskı yeni bir SahteCups adımı ister: sıralamayı baştan al
        self.assertTrue(bekle(lambda: any(k[0] == "cevir" for k in d.kayit)), d.kayit)
        self.assertTrue(bekle(ikinci_adim), (cups.gonderilen, d.kayit))
        self.assertEqual([k for k in d.turler() if k[0] != "uyari"],
                         [("soru", "Ön yüzler"), ("cevir", "Kâğıtları çevirin"), ("bilgi", "Yazdır")])
        self.assertIn(("uyari", "Yazıcı uyarısı"), d.turler())
        self.assertEqual(d.ana_disi, [], "pencereler ana iş parçacığı dışında açıldı")
        self.assertIn("HEPSİNİ", [k for k in d.kayit if k[0] == "cevir"][0][2])

    def test_iptal_edilen_on_yuzden_sonra_arka_sorulmaz(self):
        cups = SahteCups([(core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR), (core.IS_IPTAL, [], core.YAZICI_BOSTA)]).kur(self)
        d = Diyaloglar(self)
        p = self.pencere(belge(4))
        p.yazdir()
        self.assertTrue(bekle(lambda: not p._baski_suruyor and any(k[0] == "bilgi" for k in d.kayit)))
        self.assertEqual(d.turler(), [("soru", "Ön yüzler"), ("bilgi", "Yazdır")])
        self.assertEqual(d.kayit[-1][2], "Baskı iptal edildi.")
        self.assertEqual(cups.gonderilen, ["on.pdf"])
        self.assertTrue(p.yazdir_btn.isEnabled(), "iptalden sonra yeniden yazdırılabilmeli")

    def test_tek_yuz(self):
        cups = SahteCups().kur(self)
        d = Diyaloglar(self)
        p = self.pencere(belge(3), arkali=False)
        p.yazdir()
        self.assertTrue(bekle(lambda: not p._baski_suruyor and len(d.kayit) == 2))
        self.assertEqual(cups.gonderilen, ["yuzler.pdf"])
        self.assertEqual(d.kayit[-1][2], "Baskı tamamlandı.")

    def test_vazgecilirse_yarim_is_kalmaz(self):
        SahteCups().kur(self)
        Diyaloglar(self, devam=False)
        p = self.pencere(belge(4))
        is_ = p.is_
        p.yazdir()
        self.assertTrue(bekle(lambda: not p._baski_suruyor and core.Is.yukle(is_.id).durum == "vazgecildi"))
        self.assertIsNone(core.yarim_is())


class KilitVeKapatma(Temel):
    def test_baski_surerken_kilitli_kapatinca_kaldigi_yerden(self):
        kapi = threading.Event()
        cups = SahteCups([(core.IS_ISLENIYOR, [], core.YAZICI_BASIYOR)]).kur(self)
        gercek = cups.is_durumu

        def yavas(no):
            kapi.wait(0.05)
            return gercek(no)
        with mock.patch.object(core, "is_durumu", yavas):
            d = Diyaloglar(self)
            p = self.pencere(belge(4))
            is_ = p.is_
            p.yazdir()
            self.assertTrue(bekle(lambda: p._baski_suruyor and cups.gonderilen))
            for w in (p.arkali, p.yazici, p.sayfalar, p.kopya, p.dz, p.dil_secim, p.sec_btn, p.yon_grubu):
                self.assertFalse(w.isEnabled(), w)
            self.assertFalse(p.yazdir_btn.isEnabled())
            p.ayar_degisti()                       # baskı sürerken ayar değişikliği işi bozmamalı
            self.assertIs(p.is_, is_)
            p.close()                              # "Kapatılsın mı?" -> Evet
            self.assertFalse(p.mesgul_mu())
        self.assertIn(("soru", "Yazdır"), d.turler())
        self.assertEqual(core.Is.yukle(is_.id).durum, "on_gonderildi")

        # yeniden açılınca sorulur; izleme sürer, sonra arka yüz sorusu gelir
        SahteCups([(core.IS_BITTI, [], core.YAZICI_BOSTA)]).kur(self)
        d2 = Diyaloglar(self)
        p2 = gui.Pencere()
        self.pencereler.append(p2)
        self.assertTrue(bekle(lambda: any(k[0] == "cevir" for k in d2.kayit)), d2.kayit)
        self.assertEqual(d2.turler()[0], ("soru", "Yarım kalan baskı"))

    def test_ayar_yarisi_son_ayar_kazanir(self):
        SahteCups().kur(self)
        Diyaloglar(self)
        p = self.pencere(belge(9, "yaris"))
        dugmeler = {b.property("duzen"): b for b in p.duzen_grup.buttons()}
        for d in ("2", "4", "kitapcik", "2"):
            dugmeler[d].setChecked(True)
        self.assertTrue(bekle(lambda: p.is_ is not None and not p.mesgul_mu()))
        bekle(lambda: False, 0.5)                    # geride kalan hazırlık kalmasın
        self.assertEqual(p.is_.duzen, "2")
        self.assertIs(p._gosterilen, p.is_)
        basilmamis = [y for y in (core.CACHE / "isler").glob("*/is.json")
                      if '"gecmis": []' in y.read_text() and "yaris-9.pdf" in y.read_text()]
        self.assertEqual(len(basilmamis), 1, "eski hazırlıklar silinmeli")
        self.assertFalse(QApplication.overrideCursor(), "bekleme imleci takılı kaldı")


class DenemeVeDil(Temel):
    def test_deneme_sayfasi_ayari_degistirir_ve_belgeye_doner(self):
        cups = SahteCups().kur(self)
        Diyaloglar(self, cevap={"Yön denemesi": QMessageBox.No})
        p = self.pencere(belge(4))
        belge_isi = p.is_
        p.deneme_bas()
        self.assertTrue(bekle(lambda: core.ayarlar().get("arka_180") is True and not p.mesgul_mu()))
        self.assertTrue(p.arka_180.isChecked())
        self.assertEqual(cups.gonderilen[:2], ["on.pdf", "arka.pdf"])
        self.assertTrue(bekle(lambda: p.is_ is not None and p.is_ is not belge_isi and not p.is_.deneme))
        self.assertTrue(p.is_.arka_180)

    def test_yon_ayari_onaysiz_degismez(self):
        """Ayar kutusuna yanlışlıkla tıklamak ayarı değiştirmemeli (bir kez böyle değişmişti)."""
        SahteCups().kur(self)
        core.ayar_kaydet(arka_180=True)
        d = Diyaloglar(self, cevap={"Arkalı önlü yönü": QMessageBox.No})
        p = self.pencere()
        self.assertTrue(p.arka_180.isChecked())
        p.arka_180.click()
        self.assertTrue(p.arka_180.isChecked(), "vazgeçilince kutu eski haline dönmeli")
        self.assertIs(core.ayarlar()["arka_180"], True)
        self.assertEqual(d.turler(), [("soru", "Arkalı önlü yönü")])
        d.cevap = {}
        p.arka_180.click()
        self.assertFalse(p.arka_180.isChecked())
        self.assertIs(core.ayarlar()["arka_180"], False)

    def test_dil_degisince_her_sey_cevrilir_dosya_kalir(self):
        SahteCups().kur(self)
        Diyaloglar(self)
        p = self.pencere(belge(3))
        p.dil_secim.setCurrentIndex(p.dil_secim.findData("en"))
        self.assertEqual(p.yazdir_btn.text(), "Print")
        self.assertEqual(p.liste.item(0).text(), "Sheet 1 — front")
        self.assertTrue(p.ozet.text().startswith("Sides: 3"))
        self.assertIn("belge-3.pdf", p.dosya_etiket.text())
        self.assertEqual(core.ayarlar()["dil"], "en")
        p.dil_secim.setCurrentIndex(p.dil_secim.findData("tr"))
        self.assertEqual(p.yazdir_btn.text(), "Yazdır")


if __name__ == "__main__":
    unittest.main()

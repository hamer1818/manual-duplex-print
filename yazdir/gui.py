"""Yazdır — pencereli uygulama (PySide6).

Kararlılık kuralları (bunları bozan hatalar yaşandı):
- Uzun işler (hazırlama, baskı) işçi iş parçacığında çalışır; sonuçları ve uyarıları Pencere'nin
  METOTLARINA bağlı sinyallerle gelir. Lambda'ya bağlanan sinyal PySide6'da işçi iş parçacığında
  çalışır ve oradan açılan pencereler görünmez (arka yüz sorusunun hiç çıkmaması böyle olmuştu).
- Baskı sürerken ayarlar kilitlidir; baskı akışı kendi iş nesnesini taşır, self.is_'e güvenmez.
- Baskı sonucu CUPS'tan okunur (core.izle): kâğıt bitmesi, bağlantı kopması akışı bitirmez, uyarı
  gösterilir ve beklenir; iptal edilen iş "basıldı" sayılmaz.
- Yarım kalan iş (ör. ön yüzler basıldı, pencere kapandı) uygulama yeniden açılınca sorulur.
"""
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QObject, QSize, Qt, QThread, QTimer, QTranslator, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from . import core, dil
from .dil import t

DESEN = ("*.pdf *.doc *.docx *.odt *.rtf *.txt *.ppt *.pptx *.odp *.xls *.xlsx *.ods "
         "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif")

_qt_cevirmen = None


def qt_dilini_ayarla():
    """Qt'nin kendi düğmeleri (Evet/Hayır, İptal…) da seçilen dilde görünsün."""
    global _qt_cevirmen
    app = QApplication.instance()
    if _qt_cevirmen is not None:
        app.removeTranslator(_qt_cevirmen)
        _qt_cevirmen = None
    if dil.aktif() != "en":
        c = QTranslator(app)
        if c.load(f"qtbase_{dil.aktif()}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(c)
            _qt_cevirmen = c


def gunluk_yolu() -> Path:
    return core.CACHE / "yazdir.log"


class Isci(QObject):
    """Uzun işlemleri arayüzü dondurmadan çalıştırır."""
    bitti = Signal(object)
    hata = Signal(str)
    bildirim = Signal(object)   # baskı sürerken yazıcı uyarısı (kod ya da None)

    def __init__(self, fn, args, kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw

    def calis(self):
        try:
            self.bitti.emit(self.fn(*self.args, **self.kw))
        except core.YazdirHata as e:
            core.log.warning("hata: %s", e)
            self.hata.emit(str(e))
        except Exception as e:  # beklenmeyen hatalar da kullanıcıya gösterilsin
            core.log.exception("işçide beklenmeyen hata")
            self.hata.emit(f"{type(e).__name__}: {e}")


class Pencere(QMainWindow):
    def __init__(self, dosya=None):
        super().__init__()
        self.setWindowIcon(QIcon.fromTheme("document-print"))
        self.resize(980, 680)
        self.is_ = None              # basılmaya hazır iş (hazırlanırken None)
        self._gosterilen = None      # önizlemesi gösterilen iş
        self._resimler = []          # son önizleme resimleri (dil değişince etiketler yeniden yazılır)
        self.dosya = None
        self._thread = None
        self._isci = None
        self._bitti_cb = None
        self._nesil = 0              # her ayar değişikliğinde artar; eski hazırlık sonuçları atılır
        self._dur = threading.Event()  # pencere kapanırken baskı izlemeyi durdurur
        self._baski_suruyor = False
        self._imlec = False
        self._uyari_kutu = None
        self._sonra_ac = None        # yarım iş bitince açılacak dosya
        self._deneme_onceki = None   # deneme sayfası bitince geri dönülecek iş
        self.setAcceptDrops(True)

        # --- dosya
        self.dosya_etiket = QLabel()
        self.dosya_etiket.setWordWrap(True)
        self.dosya_etiket.setTextFormat(Qt.PlainText)
        self.sec_btn = QPushButton(QIcon.fromTheme("document-open"), "")
        self.sec_btn.clicked.connect(self.dosya_sec)

        # --- dil seçimi
        self.dil_etiket = QLabel()
        self.dil_secim = QComboBox()
        for kod, ad in dil.DILLER.items():
            self.dil_secim.addItem(ad, kod)
        self.dil_secim.setCurrentIndex(self.dil_secim.findData(dil.aktif()))
        self.dil_secim.currentIndexChanged.connect(self.dil_degisti)

        ust = QHBoxLayout()
        ust.addWidget(self.sec_btn)
        ust.addWidget(self.dosya_etiket, 1)
        ust.addWidget(self.dil_etiket)
        ust.addWidget(self.dil_secim)

        # --- ayarlar
        self.yazici = QComboBox()
        self.yazici.addItems(core.yazicilar())
        v = core.varsayilan_yazici()
        if v:
            self.yazici.setCurrentText(v)
        self.yazici.currentIndexChanged.connect(self.ayar_degisti)

        self.duzen_grup = QButtonGroup(self)
        duzen_kutu = QVBoxLayout()
        for anahtar in core.DUZENLER:
            r = QRadioButton()
            r.setProperty("duzen", anahtar)
            self.duzen_grup.addButton(r)
            duzen_kutu.addWidget(r)
            if anahtar == "1":
                r.setChecked(True)
        self.duzen_grup.buttonToggled.connect(self.ayar_degisti)

        self.arkali = QCheckBox()
        self.arkali.toggled.connect(self.ayar_degisti)
        self.sayfalar = QLineEdit()
        self.sayfalar.editingFinished.connect(self.ayar_degisti)
        self.kopya = QSpinBox()
        self.kopya.setRange(1, 99)
        self.kopya.valueChanged.connect(self.ayar_degisti)

        self.form_etiketleri = {"gui.yazici": QLabel(), "gui.sayfalar": QLabel(), "gui.kopya": QLabel()}
        form = QFormLayout()
        form.addRow(self.form_etiketleri["gui.yazici"], self.yazici)
        form.addRow(self.form_etiketleri["gui.sayfalar"], self.sayfalar)
        form.addRow(self.form_etiketleri["gui.kopya"], self.kopya)
        self.dz = QGroupBox()
        self.dz.setLayout(duzen_kutu)

        self.ozet = QLabel("")
        self.ozet.setWordWrap(True)
        self.ozet.setTextFormat(Qt.PlainText)

        self.yazdir_btn = QPushButton(QIcon.fromTheme("document-print"), "")
        self.yazdir_btn.setMinimumHeight(42)
        self.yazdir_btn.setEnabled(False)
        self.yazdir_btn.clicked.connect(lambda: self.yazdir())

        self.temizle_btn = QPushButton(QIcon.fromTheme("edit-clear"), "")
        self.temizle_btn.clicked.connect(self.kuyrugu_temizle)

        # --- yazıcı ayarı: arka yüz yönü (bir kez deneme sayfasıyla belirlenir)
        self.arka_180 = QCheckBox()
        self.arka_180.setChecked(bool(core.ayarlar().get("arka_180", False)))
        self.arka_180.toggled.connect(self.arka_180_degisti)
        self.deneme_btn = QPushButton(QIcon.fromTheme("document-print-preview"), "")
        self.deneme_btn.clicked.connect(self.deneme_bas)
        self.yon_durumu = QLabel()
        self.yon_durumu.setWordWrap(True)
        self.yon_durumu.setTextFormat(Qt.PlainText)
        yazi = self.yon_durumu.font()
        yazi.setPointSizeF(yazi.pointSizeF() * 0.9)
        self.yon_durumu.setFont(yazi)
        yk = QVBoxLayout()
        yk.addWidget(self.arka_180)
        yk.addWidget(self.yon_durumu)
        yk.addWidget(self.deneme_btn)
        self.yon_grubu = QGroupBox()
        self.yon_grubu.setLayout(yk)

        sol = QVBoxLayout()
        sol.addLayout(form)
        sol.addWidget(self.dz)
        sol.addWidget(self.arkali)
        sol.addWidget(self.yon_grubu)
        sol.addSpacing(8)
        sol.addWidget(self.ozet)
        sol.addStretch(1)
        sol.addWidget(self.yazdir_btn)
        sol.addWidget(self.temizle_btn)
        solw = QWidget()
        solw.setLayout(sol)
        solw.setFixedWidth(320)

        # baskı sürerken kilitlenen denetimler
        self._kilitlenecekler = [self.sec_btn, self.dil_secim, self.yazici, self.sayfalar, self.kopya, self.dz,
                                 self.arkali, self.yon_grubu]

        # --- önizleme
        self.liste = QListWidget()
        self.liste.setViewMode(QListWidget.IconMode)
        self.liste.setIconSize(QSize(220, 220))
        self.liste.setResizeMode(QListWidget.Adjust)
        self.liste.setSpacing(10)
        self.liste.setMovement(QListWidget.Static)

        govde = QHBoxLayout()
        govde.addWidget(solw)
        govde.addWidget(self.liste, 1)

        ana = QVBoxLayout()
        ana.addLayout(ust)
        ana.addLayout(govde, 1)
        w = QWidget()
        w.setLayout(ana)
        self.setCentralWidget(w)

        self.metinleri_yaz()
        self.durum_guncelle()
        zamanlayici = QTimer(self)
        zamanlayici.timeout.connect(self.durum_guncelle)
        zamanlayici.start(5000)

        self._sonra_ac = dosya
        QTimer.singleShot(200, self._baslangic)

    def _baslangic(self):
        """Önce yarım kalan baskıyı sorar; yoksa (ya da bırakılırsa) verilen dosyayı açar."""
        if not self.yarim_isi_sor() and self._sonra_ac:
            yol, self._sonra_ac = self._sonra_ac, None
            self.dosya_ac(yol)

    # ---------------------------------------------------------- dil
    def metinleri_yaz(self):
        """Bütün sabit yazıları seçili dilde yazar; dinamik olanları (özet, önizleme) yeniler."""
        self.setWindowTitle(t("gui.baslik"))
        if not self.dosya:
            self.dosya_etiket.setText(t("gui.dosya_yok"))
        self.sec_btn.setText(t("gui.dosya_sec"))
        self.dil_etiket.setText(t("gui.dil"))
        for anahtar, etiket in self.form_etiketleri.items():
            etiket.setText(t(anahtar))
        self.sayfalar.setPlaceholderText(t("gui.sayfalar_ipucu"))
        self.dz.setTitle(t("gui.sayfa_duzeni"))
        for b in self.duzen_grup.buttons():
            b.setText(core.duzen_adi(b.property("duzen")))
        self.arkali.setText(t("gui.arkali"))
        self.yon_grubu.setTitle(t("gui.yon_grubu"))
        self.arka_180.setText(t("gui.arka_180"))
        self.arka_180.setToolTip(t("gui.arka_180_ipucu"))
        self.deneme_btn.setText(t("gui.deneme_btn"))
        self.yon_durumunu_yaz()
        self.yazdir_btn.setText(t("gui.yazdir"))
        self.temizle_btn.setText(t("gui.kuyrugu_temizle"))
        self.onizlemeyi_yaz()

    def dil_degisti(self, _):
        kod = self.dil_secim.currentData()
        if kod == dil.aktif():
            return
        if self._baski_suruyor:
            self.dil_secim.blockSignals(True)
            self.dil_secim.setCurrentIndex(self.dil_secim.findData(dil.aktif()))
            self.dil_secim.blockSignals(False)
            QMessageBox.information(self, t("gui.baslik"), t("gui.dil_mesgul"))
            return
        core.dil_kaydet(kod)
        qt_dilini_ayarla()
        self.metinleri_yaz()
        self.durum_guncelle()

    # ---------------------------------------------------------- iş parçacığı
    def mesgul_mu(self):
        return bool(self._thread and self._thread.isRunning())

    def arkada(self, fn, *args, bitti=None, bildirimli=False, **kw):
        """fn'i işçi iş parçacığında çalıştırır. bildirimli: fn'e bildir= ve dur= verilir (baskı)."""
        if self.mesgul_mu():
            return False
        self._thread = QThread(self)
        self._isci = Isci(fn, args, kw)
        if bildirimli:
            kw["bildir"] = self._isci.bildirim.emit
            kw["dur"] = self._dur
        self._isci.moveToThread(self._thread)
        self._thread.started.connect(self._isci.calis)
        self._bitti_cb = bitti
        self._isci.bitti.connect(self._isci_bitti)
        self._isci.hata.connect(self._isci_hata)
        self._isci.bildirim.connect(self._bildirim)
        self._thread.start()
        return True

    def _isci_bitir(self):
        # quit() hemen etki etmez; beklenmezse ardından gelen arkada() "meşgul" sanıp işi atlıyordu.
        self._thread.quit()
        self._thread.wait()

    def _isci_bitti(self, r):
        self._isci_bitir()
        cb, self._bitti_cb = self._bitti_cb, None
        if cb:
            cb(r)

    def _isci_hata(self, m):
        self._isci_bitir()
        self._bitti_cb = None
        baski = self._baski_suruyor
        self._baski_bitti()
        if baski:
            self._denemeden_don()
        self.mesgul(False)
        QMessageBox.warning(self, t("gui.baslik"), m)

    def mesgul(self, evet, metin=""):
        self.yazdir_btn.setEnabled(not evet and self.is_ is not None and not self._baski_suruyor)
        self.deneme_btn.setEnabled(not evet and not self._baski_suruyor)
        self.statusBar().showMessage(metin)
        if evet and not self._imlec:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._imlec = True
        elif not evet and self._imlec:
            QApplication.restoreOverrideCursor()
            self._imlec = False
        if not evet and not metin:
            QTimer.singleShot(0, self.durum_guncelle)   # durum çubuğu boş kalmasın

    def _kilitle(self, evet):
        for w in self._kilitlenecekler:
            w.setEnabled(not evet)
        if not evet:
            self.arkali.setEnabled(self.secili_duzen() != "kitapcik")

    def durum_guncelle(self):
        if self._baski_suruyor:
            return
        ad = self.yazici.currentText()
        if not ad:
            self.statusBar().showMessage(t("hata.yazici_yok"))
            return
        try:
            y = core.yazici_bilgisi(ad)
        except core.YazdirHata as e:
            self.statusBar().showMessage(str(e))
            return
        except Exception:
            core.log.exception("yazıcı durumu okunamadı")
            return
        durum = {core.YAZICI_BOSTA: t("gui.yazici_hazir"), core.YAZICI_BASIYOR: t("gui.yazici_basiyor"),
                 core.YAZICI_DURDU: t("gui.yazici_kapali")}.get(y["durum"], str(y["durum"]))
        if y["uyarilar"]:
            durum += " — " + t(f"uyari.{y['uyarilar'][0]}").split(".")[0]
        kuyruk = t("gui.kuyrukta", n=y["kuyruk"]) if y["kuyruk"] else ""
        if not self.mesgul_mu():
            self.statusBar().showMessage(t("gui.yazici_durum", ad=ad, durum=durum, kuyruk=kuyruk))

    # ---------------------------------------------------------- sürükle-bırak
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and not self._baski_suruyor:
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls and not self._baski_suruyor:
            self.dosya_ac(urls[0].toLocalFile())

    # ---------------------------------------------------------- hazırlama
    def dosya_sec(self):
        yol, _ = QFileDialog.getOpenFileName(self, t("gui.dosya_diyalog"), str(Path.home()),
                                             t("gui.uzantilar", desen=DESEN))
        if yol:
            self.dosya_ac(yol)

    def dosya_ac(self, yol):
        self.dosya = yol
        self.dosya_etiket.setText(f"{Path(yol).name}\n{Path(yol).parent}")
        self.ayar_degisti()

    def secili_duzen(self):
        b = self.duzen_grup.checkedButton()
        return b.property("duzen") if b else "1"

    def ayar_degisti(self, *_):
        kitapcik = self.secili_duzen() == "kitapcik"
        self.arkali.blockSignals(True)
        if kitapcik:
            self.arkali.setChecked(True)
        self.arkali.setEnabled(not kitapcik and not self._baski_suruyor)
        self.arkali.blockSignals(False)
        if not self.dosya or self._baski_suruyor:
            return
        self._nesil += 1
        self.is_ = None
        self.mesgul(True, t("gui.hazirlaniyor"))
        if not self.arkada(self._hazirla, self._nesil, bitti=self.hazir):
            QTimer.singleShot(300, self._bekleyen_hazirlik)

    def _bekleyen_hazirlik(self):
        """Önceki hazırlık bitince en son ayarlarla bir kez hazırlar."""
        if self._baski_suruyor or not self.dosya:
            return
        if self.mesgul_mu():
            QTimer.singleShot(300, self._bekleyen_hazirlik)
        elif self.is_ is None:
            self.arkada(self._hazirla, self._nesil, bitti=self.hazir)

    def _hazirla(self, nesil):
        is_ = core.hazirla(self.dosya, self.secili_duzen(), self.arkali.isChecked(), self.sayfalar.text(),
                           self.kopya.value(), self.yazici.currentText() or None)
        return nesil, is_, core.onizleme(is_, 50, en_fazla=60)

    def hazir(self, sonuc):
        nesil, is_, resimler = sonuc
        if nesil != self._nesil:
            # bu sırada ayarlar değişti: eski sonucu at, yenisi hazırlanıyor
            core.isi_sil(is_)
            if not self.mesgul_mu():
                self._bekleyen_hazirlik()
            return
        if self._gosterilen is not None and self._gosterilen is not is_:
            core.isi_sil(self._gosterilen)
        self.is_ = self._gosterilen = is_
        self._resimler = resimler
        self.mesgul(False)
        self.onizlemeyi_yaz()

    def onizlemeyi_yaz(self):
        """Önizleme listesini ve özeti (gösterilen iş için) seçili dilde yazar."""
        s = self._gosterilen
        self.liste.clear()
        if not s:
            self.ozet.setText("")
            return
        for i, r in enumerate(self._resimler):
            if s.arkali_onlu:
                ad = t("gui.kagit_on" if i % 2 == 0 else "gui.kagit_arka", n=i // 2 + 1)
            else:
                ad = t("gui.kagit", n=i + 1)
            self.liste.addItem(QListWidgetItem(QIcon(QPixmap(str(r))), ad))
        satir = [t("gui.ozet_sayilar", yuz=s.yuz_sayisi, kagit=s.kagit)]
        if s.arkali_onlu:
            satir.append(t("gui.ozet_arkali", on=s.on_sayisi, arka=s.arka_sayisi))
        if s.duzen == "kitapcik":
            satir.append(t("gui.ozet_kitapcik"))
        self.ozet.setText("\n".join(satir))

    # ---------------------------------------------------------- yön denemesi
    def yon_durumunu_yaz(self):
        """Kutunun altında ayarın kâğıtta ne anlama geldiğini yazar (kutunun adı tek başına yanlış anlaşıldı)."""
        metin = t("gui.yon_acik" if self.arka_180.isChecked() else "gui.yon_kapali")
        tarih = core.ayarlar().get("arka_180_deneme")
        if tarih:
            metin += t("gui.yon_deneme_tarihi", tarih=tarih)
        self.yon_durumu.setText(metin)

    def arka_180_degisti(self, deger):
        """Yön ayarı deneme sayfasıyla bulunur; yanlışlıkla bir tıkla değişmesin diye onay istenir
        (bir kez böyle değişmiş ve arka yüzler ters basılmıştı)."""
        cevap = QMessageBox.question(
            self, t("gui.yon_grubu"), t("gui.arka_180_onay_ac" if deger else "gui.arka_180_onay_kapat"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if cevap != QMessageBox.Yes:
            self.arka_180.blockSignals(True)
            self.arka_180.setChecked(not deger)
            self.arka_180.blockSignals(False)
            return
        core.log.info("arka_180 elle değiştirildi: %s", bool(deger))
        core.ayar_kaydet(arka_180=bool(deger), arka_180_deneme=None)
        self.yon_durumunu_yaz()
        self.ayar_degisti()

    def deneme_bas(self):
        if self.mesgul_mu() or self._baski_suruyor:
            return
        try:
            d = core.deneme_hazirla(self.yazici.currentText() or None)
        except core.YazdirHata as e:
            QMessageBox.warning(self, t("gui.baslik"), str(e))
            return
        self._deneme_onceki = self.is_
        self.is_ = d
        if not self.yazdir(baslik=t("gui.deneme_baslik")):
            self._denemeden_don()

    def _denemeden_don(self):
        if self.is_ is not None and self.is_.deneme:
            self.is_, self._deneme_onceki = self._deneme_onceki, None
            self.yazdir_btn.setEnabled(self.is_ is not None and not self._baski_suruyor)

    def _deneme_sonucu(self):
        self._denemeden_don()
        c = QMessageBox.question(self, t("gui.yon_denemesi"), t("deneme.soru"))
        yeni = core.deneme_sonucu(c == QMessageBox.Yes)
        self.arka_180.blockSignals(True)
        self.arka_180.setChecked(yeni)
        self.arka_180.blockSignals(False)
        self.yon_durumunu_yaz()
        QMessageBox.information(
            self, t("gui.yon_denemesi"),
            t("gui.ayar_dogru") if c == QMessageBox.Yes else t("gui.ayar_180") if yeni else t("gui.ayar_duz"))
        if c != QMessageBox.Yes:
            self.ayar_degisti()

    # ---------------------------------------------------------- baskı
    def yazdir(self, baslik=None):
        s = self.is_
        if not s or self.mesgul_mu():
            return False
        if s.arkali_onlu:
            cevap = QMessageBox.question(
                self, baslik or t("gui.on_yuzler"), t("gui.on_soru", kagit=s.kagit, on=s.on_sayisi))
            if cevap != QMessageBox.Yes:
                return False
            return self._bas(s, "on", sonra=self._arka_sor)
        if QMessageBox.question(self, t("gui.baslik"), t("gui.tek_soru", kagit=s.kagit)) != QMessageBox.Yes:
            return False
        return self._bas(s, "hepsi")

    def _baski_basladi(self, adim):
        self._baski_suruyor = True
        self._dur.clear()
        self._kilitle(True)
        self.mesgul(True, t({"on": "gui.on_basiliyor", "arka": "gui.arka_basiliyor"}.get(adim, "gui.basiliyor")))

    def _baski_bitti(self):
        self._baski_suruyor = False
        self._uyariyi_kapat()
        self._kilitle(False)

    def _bas(self, is_, adim, sonra=None):
        """Adımı yazıcıya gönderir ve bitene kadar izler; sonuç _basildi'ye gelir."""
        return self._baski_islemi(core.bas, is_, adim, sonra)

    def _izle(self, is_, adim, sonra=None):
        """Önceden gönderilmiş adımı izlemeye devam eder (yarım kalan iş)."""
        return self._baski_islemi(core.izle, is_, adim, sonra, gonder=False)

    def _baski_islemi(self, fn, is_, adim, sonra, gonder=True):
        if self.mesgul_mu():
            QMessageBox.warning(self, t("gui.baslik"), t("gui.mesgul"))
            return False
        self._baski_basladi(adim)
        args = (is_, adim) if gonder else (is_,)
        self.arkada(fn, *args, bitti=lambda r: self._basildi(is_, adim, r, sonra), bildirimli=True)
        return True

    def _bildirim(self, kod):
        """Baskı sürerken yazıcı uyarısı: pencereyi kilitlemeden gösterilir, sorun kalkınca kapanır."""
        if kod is None:
            self._uyariyi_kapat()
            if self._baski_suruyor:
                self.statusBar().showMessage(t("gui.basiliyor"))
            return
        metin = t(f"uyari.{kod}")
        self.statusBar().showMessage(metin.split(".")[0])
        if self._uyari_kutu is None:
            self._uyari_kutu = QMessageBox(QMessageBox.Warning, t("gui.uyari_baslik"), metin, QMessageBox.Ok, self)
            self._uyari_kutu.setWindowModality(Qt.NonModal)
            self._uyari_kutu.finished.connect(self._uyari_kapandi)
        else:
            self._uyari_kutu.setText(metin)
        self._uyari_kutu.show()

    def _uyari_kapandi(self, *_):
        self._uyari_kutu = None

    def _uyariyi_kapat(self):
        if self._uyari_kutu is not None:
            k, self._uyari_kutu = self._uyari_kutu, None
            k.close()

    def _basildi(self, is_, adim, sonuc, sonra):
        self._baski_bitti()
        self.mesgul(False)
        if sonuc == "durduruldu":       # pencere kapanıyor; iş yazıcıda sürer, yeniden açılınca sorulur
            return
        if sonuc == "iptal":
            self._denemeden_don()
            QMessageBox.information(self, t("gui.baslik"), t("gui.iptal_edildi"))
            self._yarim_bitti()
            return
        if sonuc == "hata":
            self._denemeden_don()
            neden = is_.gecmis[-1].get("neden") or "?"
            QMessageBox.warning(self, t("gui.baslik"), t("gui.baski_hatasi", neden=neden, gunluk=gunluk_yolu()))
            self._yarim_bitti()
            return
        # bitti
        if sonra:
            sonra(is_)
        elif is_.deneme:
            self._deneme_sonucu()
        else:
            self.statusBar().showMessage(t("gui.bitti"), 8000)
            QMessageBox.information(self, t("gui.baslik"), t("gui.bitti") + (
                t("gui.bitti_kitapcik") if is_.duzen == "kitapcik" else ""))
            self._yarim_bitti()

    def _arka_sor(self, is_):
        if not is_.arka_sayisi:
            QMessageBox.information(self, t("gui.baslik"), t("gui.bitti"))
            self._yarim_bitti()
            return
        m = QMessageBox(self)
        m.setWindowTitle(t("gui.cevir_baslik"))
        m.setIcon(QMessageBox.Information)
        m.setText(t("gui.on_basildi"))
        m.setInformativeText(is_.kagit_talimati() + t("gui.hazir_olunca"))
        devam = m.addButton(t("gui.devam"), QMessageBox.AcceptRole)
        m.addButton(t("gui.vazgec"), QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() == devam:
            self._bas(is_, "arka")
            return
        if is_.deneme:
            self._denemeden_don()
        else:
            is_.durum = "vazgecildi"
            is_.kaydet()
        self._yarim_bitti()

    # ---------------------------------------------------------- yarım kalan iş
    def yarim_isi_sor(self):
        """Son 48 saatte yarım kalan bir baskı varsa devam etmeyi önerir. Devam edildiyse True."""
        try:
            is_ = core.yarim_is()
        except Exception:
            core.log.exception("yarım iş okunamadı")
            return False
        if is_ is None:
            return False
        adim = is_.gecmis[-1]["adim"]
        if is_.durum == "on_basildi":
            if QMessageBox.question(self, t("gui.yarim_baslik"), t("gui.yarim_arka", dosya=is_.kaynak)) == QMessageBox.Yes:
                self._arka_sor(is_)
                return True
        elif QMessageBox.question(self, t("gui.yarim_baslik"), t("gui.yarim_suruyor", dosya=is_.kaynak)) == QMessageBox.Yes:
            if self._izle(is_, adim, sonra=self._arka_sor if adim == "on" else None):
                return True
        is_.durum = "vazgecildi"
        is_.kaydet()
        return False

    def _yarim_bitti(self):
        """Yarım iş ele alındıktan sonra, başlangıçta verilen dosya varsa onu açar."""
        if self._sonra_ac and not self._baski_suruyor:
            yol, self._sonra_ac = self._sonra_ac, None
            self.dosya_ac(yol)

    # ---------------------------------------------------------- diğer
    def kuyrugu_temizle(self):
        if QMessageBox.question(self, t("gui.kuyruk"), t("gui.kuyruk_soru")) == QMessageBox.Yes:
            core.kuyrugu_temizle(self.yazici.currentText() or None)
            self.durum_guncelle()

    def closeEvent(self, e):
        if self.mesgul_mu():
            if self._baski_suruyor and QMessageBox.question(
                    self, t("gui.baslik"), t("gui.kapat_soru")) != QMessageBox.Yes:
                e.ignore()
                return
            self._dur.set()          # izleme en geç birkaç saniyede durur; iş yazıcıda sürer
            # quit() burada şart: normalde _isci_bitti çağırır ama o, ana iş parçacığı wait()'te
            # beklerken hiç çalışamaz; quit'siz wait() sonsuza kadar bekliyordu (pencere donuyordu).
            self._thread.quit()
            self._thread.wait()      # çalışan QThread yok edilirse uygulama çöker
        self._uyariyi_kapat()
        e.accept()


def _beklenmeyen_hata(tip, deger, iz):
    """Arayüzdeki beklenmeyen hatalar sessizce kaybolmasın: günlüğe yaz, kullanıcıya göster."""
    core.log.error("beklenmeyen hata", exc_info=(tip, deger, iz))
    try:
        QMessageBox.critical(None, t("gui.baslik"),
                             t("gui.beklenmeyen", hata=f"{tip.__name__}: {deger}", gunluk=gunluk_yolu()))
    except Exception:
        sys.__excepthook__(tip, deger, iz)


def main():
    core.gunluk_ac()
    sys.excepthook = _beklenmeyen_hata
    app = QApplication(sys.argv)
    app.setApplicationName("Yazdır")
    app.setDesktopFileName("yazdir")
    qt_dilini_ayarla()
    try:
        core.eski_isleri_temizle()
    except Exception:
        core.log.exception("eski işler temizlenemedi")
    p = Pencere(sys.argv[1] if len(sys.argv) > 1 else None)
    p.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

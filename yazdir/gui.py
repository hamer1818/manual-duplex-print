"""Yazdır — pencereli uygulama (PySide6)."""
import sys
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


class Isci(QObject):
    """Uzun işlemleri arayüzü dondurmadan çalıştırır."""
    bitti = Signal(object)
    hata = Signal(str)

    def __init__(self, fn, *args, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw

    def calis(self):
        try:
            self.bitti.emit(self.fn(*self.args, **self.kw))
        except core.YazdirHata as e:
            self.hata.emit(str(e))
        except Exception as e:  # beklenmeyen hatalar da kullanıcıya gösterilsin
            self.hata.emit(f"{type(e).__name__}: {e}")


class Pencere(QMainWindow):
    def __init__(self, dosya=None):
        super().__init__()
        self.setWindowIcon(QIcon.fromTheme("document-print"))
        self.resize(980, 680)
        self.is_ = None
        self.dosya = None
        self._thread = None
        self._deneme_onceki = None   # deneme sayfası bitince geri dönülecek iş
        self._resimler = []          # son önizleme resimleri (dil değişince etiketler yeniden yazılır)
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
        self.yazdir_btn.clicked.connect(self.yazdir)

        self.temizle_btn = QPushButton(QIcon.fromTheme("edit-clear"), "")
        self.temizle_btn.clicked.connect(self.kuyrugu_temizle)

        # --- yazıcı ayarı: arka yüz yönü (bir kez deneme sayfasıyla belirlenir)
        self.arka_180 = QCheckBox()
        self.arka_180.setChecked(bool(core.ayarlar().get("arka_180", False)))
        self.arka_180.toggled.connect(self.arka_180_degisti)
        self.deneme_btn = QPushButton(QIcon.fromTheme("document-print-preview"), "")
        self.deneme_btn.clicked.connect(self.deneme_bas)
        yk = QVBoxLayout()
        yk.addWidget(self.arka_180)
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
        t = QTimer(self)
        t.timeout.connect(self.durum_guncelle)
        t.start(5000)

        if dosya:
            self.dosya_ac(dosya)

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
        self.yazdir_btn.setText(t("gui.yazdir"))
        self.temizle_btn.setText(t("gui.kuyrugu_temizle"))
        self.onizlemeyi_yaz()

    def dil_degisti(self, _):
        kod = self.dil_secim.currentData()
        if kod == dil.aktif():
            return
        if self._thread and self._thread.isRunning():
            self.dil_secim.blockSignals(True)
            self.dil_secim.setCurrentIndex(self.dil_secim.findData(dil.aktif()))
            self.dil_secim.blockSignals(False)
            QMessageBox.information(self, t("gui.baslik"), t("gui.dil_mesgul"))
            return
        core.dil_kaydet(kod)
        qt_dilini_ayarla()
        self.metinleri_yaz()
        self.durum_guncelle()

    # ---------------------------------------------------------- yardımcılar
    def arkada(self, fn, *args, bitti=None, **kw):
        if self._thread and self._thread.isRunning():
            return False
        self._thread = QThread(self)
        self._isci = Isci(fn, *args, **kw)
        self._isci.moveToThread(self._thread)
        self._thread.started.connect(self._isci.calis)
        self._bitti_cb = bitti
        # Pencere'nin metotlarına bağlanır (lambda'ya değil): böylece sonuç ana iş parçacığında işlenir.
        # Lambda'ya bağlanınca PySide6 onu işçi iş parçacığında çalıştırıyor, açılan pencereler görünmüyordu.
        self._isci.bitti.connect(self._isci_bitti)
        self._isci.hata.connect(self._isci_hata)
        self._thread.start()
        return True

    def _isci_bitir(self):
        # quit() hemen etki etmez; beklenmezse ardından gelen arkada() "meşgul" sanıp işi atlıyordu.
        self._thread.quit()
        self._thread.wait()

    def _isci_bitti(self, r):
        self._isci_bitir()
        if self._bitti_cb:
            self._bitti_cb(r)

    def _isci_hata(self, m):
        self._isci_bitir()
        if self._deneme_onceki is not None or (self.is_ and self.is_.deneme):
            self.is_, self._deneme_onceki = self._deneme_onceki, None
        self.mesgul(False)
        QMessageBox.warning(self, t("gui.baslik"), m)

    def mesgul(self, evet, metin=""):
        self.yazdir_btn.setEnabled(not evet and self.is_ is not None)
        self.statusBar().showMessage(metin)
        QApplication.setOverrideCursor(Qt.WaitCursor) if evet else QApplication.restoreOverrideCursor()

    def durum_guncelle(self):
        try:
            d = core.yazici_durumu(self.yazici.currentText() or None)
        except Exception:
            return
        kuyruk = t("gui.kuyrukta", n=len(d["kuyruk"])) if d["kuyruk"] else ""
        ham = d["durum"]
        durum = (t("gui.yazici_hazir") if " is idle" in ham else t("gui.yazici_basiyor") if "now printing" in ham
                 else t("gui.yazici_kapali") if "disabled" in ham else ham)
        if not (self._thread and self._thread.isRunning()):
            self.statusBar().showMessage(t("gui.yazici_durum", ad=d["yazici"], durum=durum, kuyruk=kuyruk))

    # ---------------------------------------------------------- sürükle-bırak
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.dosya_ac(urls[0].toLocalFile())

    # ---------------------------------------------------------- akış
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
        self.arkali.setEnabled(not kitapcik)
        self.arkali.blockSignals(False)
        if not self.dosya:
            return
        self.is_ = None
        self.mesgul(True, t("gui.hazirlaniyor"))
        if not self.arkada(self._hazirla, bitti=self.hazir):
            QTimer.singleShot(400, self.ayar_degisti)

    def _hazirla(self):
        is_ = core.hazirla(self.dosya, self.secili_duzen(), self.arkali.isChecked(), self.sayfalar.text(),
                           self.kopya.value(), self.yazici.currentText() or None)
        return is_, core.onizleme(is_, 50, en_fazla=60)

    def hazir(self, sonuc):
        self.is_, self._resimler = sonuc
        self._gosterilen = self.is_
        self.mesgul(False)
        self.onizlemeyi_yaz()

    def onizlemeyi_yaz(self):
        """Önizleme listesini ve özeti (gösterilen iş için) seçili dilde yazar."""
        s = getattr(self, "_gosterilen", None)
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

    def arka_180_degisti(self, deger):
        core.ayar_kaydet(arka_180=bool(deger))
        self.ayar_degisti()

    def deneme_bas(self):
        if self._thread and self._thread.isRunning():
            return
        try:
            d = core.deneme_hazirla(self.yazici.currentText() or None)
        except core.YazdirHata as e:
            QMessageBox.warning(self, t("gui.baslik"), str(e))
            return
        self._deneme_onceki = self.is_
        self.is_ = d
        if not self.yazdir(baslik=t("gui.deneme_baslik")):
            self.is_, self._deneme_onceki = self._deneme_onceki, None

    def _deneme_sonucu(self):
        self.is_, self._deneme_onceki = self._deneme_onceki, None
        self.yazdir_btn.setEnabled(self.is_ is not None)
        c = QMessageBox.question(self, t("gui.yon_denemesi"), t("deneme.soru"))
        yeni = core.deneme_sonucu(c == QMessageBox.Yes)
        self.arka_180.blockSignals(True)
        self.arka_180.setChecked(yeni)
        self.arka_180.blockSignals(False)
        QMessageBox.information(
            self, t("gui.yon_denemesi"),
            t("gui.ayar_dogru") if c == QMessageBox.Yes else t("gui.ayar_180") if yeni else t("gui.ayar_duz"))
        if c != QMessageBox.Yes:
            self.ayar_degisti()

    def yazdir(self, baslik=None):
        s = self.is_
        if not s:
            return False
        if s.arkali_onlu:
            cevap = QMessageBox.question(
                self, baslik or t("gui.on_yuzler"), t("gui.on_soru", kagit=s.kagit, on=s.on_sayisi))
            if cevap != QMessageBox.Yes:
                return False
            self._bas("on", sonra=self._arka_sor)
        else:
            if QMessageBox.question(self, t("gui.baslik"), t("gui.tek_soru", kagit=s.kagit)) != QMessageBox.Yes:
                return False
            self._bas("hepsi")
        return True

    def _bas(self, adim, sonra=None):
        self.mesgul(True, t({"on": "gui.on_basiliyor", "arka": "gui.arka_basiliyor"}.get(adim, "gui.basiliyor")))
        if not self.arkada(core.bas, self.is_, adim, bitti=lambda r: self._basildi(adim, r, sonra)):
            self.mesgul(False)
            QMessageBox.warning(self, t("gui.baslik"), t("gui.mesgul"))

    def _basildi(self, adim, sonuc, sonra):
        self.mesgul(False)
        if sonuc == "kagit_yok":
            QMessageBox.warning(self, t("gui.kagit_yok_baslik"), t("gui.kagit_yok"), QMessageBox.Ok)
            return
        if sonuc == "zaman_asimi":
            QMessageBox.information(self, t("gui.baslik"), t("gui.zaman_asimi"))
            return
        if sonra:
            sonra()
        elif self.is_.deneme:
            self._deneme_sonucu()
        else:
            self.statusBar().showMessage(t("gui.bitti"), 8000)
            QMessageBox.information(self, t("gui.baslik"), t("gui.bitti") + (
                t("gui.bitti_kitapcik") if self.is_.duzen == "kitapcik" else ""))

    def _arka_sor(self):
        s = self.is_
        if not s.arka_sayisi:
            QMessageBox.information(self, t("gui.baslik"), t("gui.bitti"))
            return
        m = QMessageBox(self)
        m.setWindowTitle(t("gui.cevir_baslik"))
        m.setIcon(QMessageBox.Information)
        m.setText(t("gui.on_basildi"))
        m.setInformativeText(s.kagit_talimati() + t("gui.hazir_olunca"))
        devam = m.addButton(t("gui.devam"), QMessageBox.AcceptRole)
        m.addButton(t("gui.vazgec"), QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() == devam:
            self._bas("arka")
        elif s.deneme:
            self.is_, self._deneme_onceki = self._deneme_onceki, None
            self.yazdir_btn.setEnabled(self.is_ is not None)

    def kuyrugu_temizle(self):
        if QMessageBox.question(self, t("gui.kuyruk"), t("gui.kuyruk_soru")) == QMessageBox.Yes:
            core.kuyrugu_temizle(self.yazici.currentText() or None)
            self.durum_guncelle()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Yazdır")
    app.setDesktopFileName("yazdir")
    qt_dilini_ayarla()
    p = Pencere(sys.argv[1] if len(sys.argv) > 1 else None)
    p.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

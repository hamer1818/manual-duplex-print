"""Yazdır — pencereli uygulama (PySide6)."""
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from . import core

UZANTILAR = "Belgeler (*.pdf *.doc *.docx *.odt *.rtf *.txt *.ppt *.pptx *.odp *.xls *.xlsx *.ods " \
            "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif);;Tüm dosyalar (*)"


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
        self.setWindowTitle("Yazdır")
        self.setWindowIcon(QIcon.fromTheme("document-print"))
        self.resize(980, 680)
        self.is_ = None
        self.dosya = None
        self._thread = None
        self._deneme_onceki = None   # deneme sayfası bitince geri dönülecek iş
        self.setAcceptDrops(True)

        # --- dosya
        self.dosya_etiket = QLabel("Dosya seçilmedi — dosyayı buraya sürükleyebilirsiniz.")
        self.dosya_etiket.setWordWrap(True)
        self.dosya_etiket.setTextFormat(Qt.PlainText)
        sec = QPushButton(QIcon.fromTheme("document-open"), "Dosya Seç…")
        sec.clicked.connect(self.dosya_sec)
        ust = QHBoxLayout()
        ust.addWidget(sec)
        ust.addWidget(self.dosya_etiket, 1)

        # --- ayarlar
        self.yazici = QComboBox()
        self.yazici.addItems(core.yazicilar())
        v = core.varsayilan_yazici()
        if v:
            self.yazici.setCurrentText(v)

        self.duzen_grup = QButtonGroup(self)
        duzen_kutu = QVBoxLayout()
        for anahtar, ad in core.DUZENLER.items():
            r = QRadioButton(ad)
            r.setProperty("duzen", anahtar)
            self.duzen_grup.addButton(r)
            duzen_kutu.addWidget(r)
            if anahtar == "1":
                r.setChecked(True)
        self.duzen_grup.buttonToggled.connect(self.ayar_degisti)

        self.arkali = QCheckBox("Arkalı önlü (elle çevirerek)")
        self.arkali.toggled.connect(self.ayar_degisti)
        self.sayfalar = QLineEdit()
        self.sayfalar.setPlaceholderText("Tümü  (ör. 1-5, 8, 10-)")
        self.sayfalar.editingFinished.connect(self.ayar_degisti)
        self.kopya = QSpinBox()
        self.kopya.setRange(1, 99)
        self.kopya.valueChanged.connect(self.ayar_degisti)

        form = QFormLayout()
        form.addRow("Yazıcı:", self.yazici)
        form.addRow("Sayfalar:", self.sayfalar)
        form.addRow("Kopya:", self.kopya)
        dz = QGroupBox("Sayfa düzeni")
        dz.setLayout(duzen_kutu)

        self.ozet = QLabel("")
        self.ozet.setWordWrap(True)
        self.ozet.setTextFormat(Qt.PlainText)

        self.yazdir_btn = QPushButton(QIcon.fromTheme("document-print"), "Yazdır")
        self.yazdir_btn.setMinimumHeight(42)
        self.yazdir_btn.setEnabled(False)
        self.yazdir_btn.clicked.connect(self.yazdir)

        temizle = QPushButton(QIcon.fromTheme("edit-clear"), "Kuyruğu temizle")
        temizle.clicked.connect(self.kuyrugu_temizle)

        # --- yazıcı ayarı: arka yüz yönü (bir kez deneme sayfasıyla belirlenir)
        self.arka_180 = QCheckBox("Arka yüzleri 180° çevir")
        self.arka_180.setToolTip("Arka yüzler baş aşağı çıkıyorsa işaretleyin. "
                                 "Emin değilseniz 'Yön deneme sayfası' ile bir kez deneyin.")
        self.arka_180.setChecked(bool(core.ayarlar().get("arka_180", False)))
        self.arka_180.toggled.connect(self.arka_180_degisti)
        deneme = QPushButton(QIcon.fromTheme("document-print-preview"), "Yön deneme sayfası (1 kâğıt)")
        deneme.clicked.connect(self.deneme_bas)
        yk = QVBoxLayout()
        yk.addWidget(self.arka_180)
        yk.addWidget(deneme)
        yazici_ayar = QGroupBox("Arkalı önlü yönü")
        yazici_ayar.setLayout(yk)

        sol = QVBoxLayout()
        sol.addLayout(form)
        sol.addWidget(dz)
        sol.addWidget(self.arkali)
        sol.addWidget(yazici_ayar)
        sol.addSpacing(8)
        sol.addWidget(self.ozet)
        sol.addStretch(1)
        sol.addWidget(self.yazdir_btn)
        sol.addWidget(temizle)
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

        self.durum_guncelle()
        t = QTimer(self)
        t.timeout.connect(self.durum_guncelle)
        t.start(5000)

        if dosya:
            self.dosya_ac(dosya)

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
        QMessageBox.warning(self, "Yazdır", m)

    def mesgul(self, evet, metin=""):
        self.yazdir_btn.setEnabled(not evet and self.is_ is not None)
        self.statusBar().showMessage(metin)
        QApplication.setOverrideCursor(Qt.WaitCursor) if evet else QApplication.restoreOverrideCursor()

    def durum_guncelle(self):
        try:
            d = core.yazici_durumu(self.yazici.currentText() or None)
        except Exception:
            return
        kuyruk = f" • Kuyrukta {len(d['kuyruk'])} iş" if d["kuyruk"] else ""
        ham = d["durum"]
        durum = ("hazır" if " is idle" in ham else "yazdırıyor" if "now printing" in ham
                 else "devre dışı" if "disabled" in ham else ham)
        if not (self._thread and self._thread.isRunning()):
            self.statusBar().showMessage(f"Yazıcı {d['yazici']}: {durum}{kuyruk}")

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
        yol, _ = QFileDialog.getOpenFileName(self, "Yazdırılacak dosya", str(Path.home()), UZANTILAR)
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
        self.mesgul(True, "Hazırlanıyor…")
        if not self.arkada(self._hazirla, bitti=self.hazir):
            QTimer.singleShot(400, self.ayar_degisti)

    def _hazirla(self):
        is_ = core.hazirla(self.dosya, self.secili_duzen(), self.arkali.isChecked(), self.sayfalar.text(),
                           self.kopya.value(), self.yazici.currentText() or None)
        return is_, core.onizleme(is_, 50, en_fazla=60)

    def hazir(self, sonuc):
        self.is_, resimler = sonuc
        self.mesgul(False)
        self.liste.clear()
        for i, r in enumerate(resimler):
            if self.is_.arkali_onlu:
                kagit = i // 2 + 1
                ad = f"{kagit}. kâğıt — {'ön' if i % 2 == 0 else 'arka'}"
            else:
                ad = f"{i + 1}. kâğıt"
            it = QListWidgetItem(QIcon(QPixmap(str(r))), ad)
            self.liste.addItem(it)
        s = self.is_
        satir = [f"{s.yuz_sayisi} yüz, {s.kagit} kâğıt"]
        if s.arkali_onlu:
            satir.append(f"Önce {s.on_sayisi} ön yüz basılır, sonra kâğıtları geri koyduğunuzda {s.arka_sayisi} arka yüz.")
        if s.duzen == "kitapcik":
            satir.append("Kâğıtları sırayla iç içe koyup ortadan katlayın.")
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
            QMessageBox.warning(self, "Yazdır", str(e))
            return
        self._deneme_onceki = self.is_
        self.is_ = d
        if not self.yazdir(baslik="Yön deneme sayfası"):
            self.is_, self._deneme_onceki = self._deneme_onceki, None

    def _deneme_sonucu(self):
        self.is_, self._deneme_onceki = self._deneme_onceki, None
        self.yazdir_btn.setEnabled(self.is_ is not None)
        c = QMessageBox.question(self, "Yön denemesi", core.DENEME_SORUSU)
        yeni = core.deneme_sonucu(c == QMessageBox.Yes)
        self.arka_180.blockSignals(True)
        self.arka_180.setChecked(yeni)
        self.arka_180.blockSignals(False)
        QMessageBox.information(
            self, "Yön denemesi",
            "Ayar doğru, değiştirilmedi." if c == QMessageBox.Yes else
            "Ayar değiştirildi: arka yüzler bundan sonra 180° çevrilerek basılacak." if yeni else
            "Ayar değiştirildi: arka yüzler bundan sonra çevrilmeden basılacak.")
        if c != QMessageBox.Yes:
            self.ayar_degisti()

    def yazdir(self, baslik=None):
        s = self.is_
        if not s:
            return False
        if s.arkali_onlu:
            cevap = QMessageBox.question(
                self, baslik or "Ön yüzler",
                f"Tepsiye en az {s.kagit} boş kâğıt koyun.\n\n1. adım: {s.on_sayisi} ön yüz basılacak. Başlansın mı?")
            if cevap != QMessageBox.Yes:
                return False
            self._bas("on", sonra=self._arka_sor)
        else:
            if QMessageBox.question(self, "Yazdır", f"{s.kagit} kâğıt basılacak. Başlansın mı?") != QMessageBox.Yes:
                return False
            self._bas("hepsi")
        return True

    def _bas(self, adim, sonra=None):
        self.mesgul(True, {"on": "Ön yüzler basılıyor…", "arka": "Arka yüzler basılıyor…"}.get(adim, "Basılıyor…"))
        if not self.arkada(core.bas, self.is_, adim, bitti=lambda r: self._basildi(adim, r, sonra)):
            self.mesgul(False)
            QMessageBox.warning(self, "Yazdır", "Başka bir işlem sürüyor; birkaç saniye sonra yeniden deneyin.")

    def _basildi(self, adim, sonuc, sonra):
        self.mesgul(False)
        if sonuc == "kagit_yok":
            c = QMessageBox.warning(
                self, "Kâğıt yok",
                "Yazıcı 'kâğıt yok' diyor.\n\nKâğıdı çıkarıp düzgünce yeniden yerleştirin. Olmazsa yazıcıyı kapatıp açın.\n\n"
                "Baskı kuyrukta bekliyor; kâğıt algılanınca kendiliğinden devam eder.\n"
                "İptal etmek isterseniz 'Kuyruğu temizle'ye basın.",
                QMessageBox.Ok)
            return
        if sonuc == "zaman_asimi":
            QMessageBox.information(self, "Yazdır", "Baskı uzun sürüyor; yazıcıyı kontrol edin.")
            return
        if sonra:
            sonra()
        elif self.is_.deneme:
            self._deneme_sonucu()
        else:
            self.statusBar().showMessage("Baskı tamamlandı.", 8000)
            QMessageBox.information(self, "Yazdır", "Baskı tamamlandı." + (
                "\n\nKitapçık: kâğıtları sırayla iç içe koyup ortadan katlayın." if self.is_.duzen == "kitapcik" else ""))

    def _arka_sor(self):
        s = self.is_
        if not s.arka_sayisi:
            QMessageBox.information(self, "Yazdır", "Baskı tamamlandı.")
            return
        m = QMessageBox(self)
        m.setWindowTitle("Kâğıtları çevirin")
        m.setIcon(QMessageBox.Information)
        m.setText("Ön yüzler basıldı.")
        m.setInformativeText(s.kagit_talimati() + "\n\nHazır olunca 'Devam'a basın.")
        devam = m.addButton("Devam — arka yüzleri bas", QMessageBox.AcceptRole)
        m.addButton("Vazgeç", QMessageBox.RejectRole)
        m.exec()
        if m.clickedButton() == devam:
            self._bas("arka")
        elif s.deneme:
            self.is_, self._deneme_onceki = self._deneme_onceki, None
            self.yazdir_btn.setEnabled(self.is_ is not None)

    def kuyrugu_temizle(self):
        if QMessageBox.question(self, "Kuyruk", "Yazıcı kuyruğundaki tüm işler iptal edilsin mi?") == QMessageBox.Yes:
            core.kuyrugu_temizle(self.yazici.currentText() or None)
            self.durum_guncelle()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Yazdır")
    app.setDesktopFileName("yazdir")
    p = Pencere(sys.argv[1] if len(sys.argv) > 1 else None)
    p.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""Testler için ortak araçlar: numaralı deneme belgesi ve sahte CUPS."""
import subprocess
from pathlib import Path

from pypdf import PdfReader

from yazdir import core

_gercek_run = subprocess.run   # yamalanmadan önce; pdftoppm gibi gerçek araçlar için


def belge(n: int, ad: str = "belge") -> str:
    """Her sayfasında 'S<i>' yazan n sayfalık PDF."""
    yol = core.CACHE / f"{ad}-{n}.pdf"
    yol.parent.mkdir(parents=True, exist_ok=True)
    core._yaz([core._deneme_yuzu(f"S{i}") for i in range(1, n + 1)], yol)
    return str(yol)


def sayfa_yazilari(pdf: Path) -> list[list[str]]:
    """Her sayfadaki 'S<i>' yazıları, soldan sağa / yukarıdan aşağı değil, içerik sırasıyla."""
    sonuc = []
    for p in PdfReader(str(pdf)).pages:
        parcalar = []
        p.extract_text(visitor_text=lambda m, cm, tm, *_: parcalar.append(m.strip()) if m.strip().startswith("S") else None)
        sonuc.append([x for x in parcalar if x[1:].isdigit()])
    return sonuc


def ters_mi(pdf: Path, sayfa: int) -> bool:
    """Sayfadaki yazı 180° dönük mü (yazının dönüşüm matrisinde a < 0 ve d < 0)."""
    durum = []

    def gez(m, cm, tm, *_):
        if m.strip():
            a, d = cm[0] * tm[0] + cm[2] * tm[1], cm[1] * tm[2] + cm[3] * tm[3]
            durum.append(a < 0 and d < 0)
    PdfReader(str(pdf)).pages[sayfa].extract_text(visitor_text=gez)
    return bool(durum) and all(durum)


class SahteCups:
    """core.is_durumu / yazici_bilgisi / _lp yerine geçer. `adimlar`: izle() her turda bir eleman
    tüketir: (iş durumu, yazıcı uyarıları, yazıcı durumu). Son eleman tekrar eder."""

    def __init__(self, adimlar=None):
        self.adimlar = list(adimlar or [(core.IS_BITTI, [], core.YAZICI_BOSTA)])
        self.gonderilen = []
        self.etkinlestirme = 0
        self._sira = 0
        self._no = 100

    def _simdiki(self):
        return self.adimlar[min(self._sira, len(self.adimlar) - 1)]

    def is_durumu(self, no):
        durum = self._simdiki()[0]
        self._sira += 1
        return durum, "job-canceled-by-user" if durum == core.IS_IPTAL else ""

    def yazici_bilgisi(self, yazici):
        _, uyarilar, ydurum = self.adimlar[min(max(self._sira - 1, 0), len(self.adimlar) - 1)]
        return {"durum": ydurum, "uyarilar": list(uyarilar), "nedenler": [], "kuyruk": 0}

    def lp(self, yol, yazici):
        self._no += 1
        self.gonderilen.append(Path(yol).name)
        return f"{yazici}-{self._no}", self._no

    def kur(self, test):
        """unittest.TestCase içinde core'u yamalar; test bitince geri alır."""
        from unittest import mock
        for ad, yeni in (("is_durumu", self.is_durumu), ("yazici_bilgisi", self.yazici_bilgisi), ("_lp", self.lp),
                         ("yazicilar", lambda: ["X"]), ("varsayilan_yazici", lambda: "X")):
            y = mock.patch.object(core, ad, yeni)
            y.start()
            test.addCleanup(y.stop)
        sahte_run = mock.patch.object(core.subprocess, "run", side_effect=self._run)
        sahte_run.start()
        test.addCleanup(sahte_run.stop)
        uyku = mock.patch.object(core.time, "sleep", lambda *_: None)
        uyku.start()
        test.addCleanup(uyku.stop)
        return self

    def _run(self, arg, *a, **k):
        from types import SimpleNamespace
        if arg and arg[0] == "cupsenable":
            self.etkinlestirme += 1
        if arg and arg[0] in ("pdftoppm", "soffice", "magick"):
            return _gercek_run(arg, *a, **k)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

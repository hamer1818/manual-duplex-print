# Manual Duplex Print

Two-sided, 2/4-up and A5 booklet printing on Linux for printers that have no duplex unit
(tested with an HP LaserJet 1018). A command-line tool and a Qt (PySide6) window on top of CUPS.
The interface is available in **English and Turkish**: pick the language from the top-right of the window
or run `yazdir dil en`. The commands are `yazdir` / `yazdir-gui` (*yazdır* is Turkish for "print").

- **Manual duplex:** prints the fronts, tells you to put the whole stack back as it came out,
  then prints the backs in the right order. Odd page counts need no sheet removal: the last sheet
  passes through with an (almost) blank back.
- **Back-side orientation:** pages are placed on A4 by the app itself; on 2-up and booklet layouts
  the backs are rotated 180° (like HP's Windows driver). If your printer's paper path still turns
  the backs upside down, a one-sheet **orientation test page** sets the correction once.
- **Layouts:** 1, 2 (side by side) or 4 pages per side; **A5 booklet** (fold in the middle,
  pages are imposed automatically). Page ranges and copies.
- Input: PDF, Word/LibreOffice documents, images.

```bash
git clone https://github.com/hamer1818/manual-duplex-print.git
cd manual-duplex-print && ./install.sh
yazdir hazirla document.pdf -d 2 -a --onizleme   # prepare + preview (does not print)
yazdir bas on --onayli                           # print fronts
yazdir bas arka --onayli                         # print backs after reloading the stack
```
Requirements and details below (Turkish). License: MIT.

---

## Türkçe

Otomatik arkalı önlü baskı yapamayan yazıcılar (ör. HP LaserJet 1018) için yazdırma aracı.

- **Elle arkalı önlü:** önce ön yüzleri basar, tomarın tamamını yönünü değiştirmeden geri koymanızı ister (kâğıt ayırmak yok), arka yüzleri doğru sırayla basar.
- **Arka yüz yönü:** 2'li sayfa ve kitapçıkta arka yüzler 180° döndürülür. Arka yüzler yine de ters çıkarsa uygulamadaki **Yön deneme sayfası** (1 kâğıt) ile bir kez ayarlanır.
- **Sayfa düzeni:** her yüze 1, 2 (yan yana) ya da 4 sayfa; **A5 kitapçık** (ortadan katlanır, sayfalar otomatik dizilir).
- PDF, Word/LibreOffice belgeleri ve resimler.

## Gereksinimler
Linux, yazıcısı CUPS'ta tanımlı olmalı. Paketler (Arch adlarıyla; başka dağıtımlarda benzerleri):

- `cups` — `lp`, `lpstat`, `cancel`
- `python` 3.10+ ve `pyside6` (pencereli uygulama için, sistemden)
- `poppler` — önizleme için `pdftoppm`
- `libreoffice` — Word/ODT/PowerPoint/Excel dosyaları için (yalnız PDF basacaksanız gerekmez)
- `imagemagick` — resim dosyaları için
- `pypdf` — `install.sh` sanal ortama kurar

Kağıt hatası algılama `journalctl -u cups` kayıtlarını okur (systemd).

## Kurulum
```bash
git clone https://github.com/hamer1818/manual-duplex-print.git
cd manual-duplex-print
./install.sh
```
Uygulama menüsüne **Yazdır**, KDE Dolphin sağ tık menüsüne **Yazdır (arkalı önlü / kitapçık)…** eklenir.

## Komut satırı
```bash
yazdir hazirla belge.pdf -d 2 -a --onizleme   # hazırla + önizle (yazdırmaz)
yazdir bas on --onayli                        # ön yüzler
yazdir bas arka --onayli                      # arka yüzler (kâğıtları geri koyduktan sonra)
yazdir deneme                                 # arka yüz yön denemesi; sonra: yazdir deneme-sonucu evet|hayir
yazdir durum | temizle | yazicilar
yazdir dil tr|en                              # arayüz dili / interface language
```
Arayüz dili pencerenin sağ üstündeki **Dil** kutusundan da seçilir; seçim hatırlanır. Ayar yoksa sistem dili kullanılır.
Ayrıntı: `yazdir --help`. `bas`, `--onayli` olmadan kâğıda hiçbir şey göndermez
(yapay zekâ asistanı kullanırken yanlışlıkla baskıyı önlemek için).

## Claude Code yönergesi
`install.sh`, `skill/SKILL.md` dosyasını `~/.claude/skills/yazdir/` altına bağlar; böylece Claude Code
"şunu arkalı önlü yazdır" gibi istekleri bu araçla yapar ve her baskıdan önce onay ister.

## Lisans
MIT — bkz. [LICENSE](LICENSE).

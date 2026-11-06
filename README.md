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
- **Robust printing:** job state is read from CUPS. Out of paper, a jam or an unplugged cable shows a
  warning and the job simply waits; a cancelled job is never treated as printed. If the window is
  closed (or the computer restarts) between the fronts and the backs, the app offers to continue.

### Install
One command, any distribution (Arch/CachyOS/Manjaro, Debian/Ubuntu/Mint, Fedora, openSUSE). It installs
for your user, asks before installing missing system packages with `sudo`, and adds a menu entry and a
Dolphin right-click action:
```bash
curl -fsSL https://raw.githubusercontent.com/hamer1818/manual-duplex-print/main/install.sh | sh
```
Arch-based distributions can build a native package instead:
```bash
git clone https://github.com/hamer1818/manual-duplex-print.git
cd manual-duplex-print/packaging/arch && makepkg -si
```
Update: run the same command again. Uninstall: `sh ~/.local/share/manual-duplex-print/install.sh --uninstall`
(add `--purge` to remove settings and cache too).

### Command line
```bash
yazdir hazirla document.pdf -d 2 -a --onizleme   # prepare + preview (does not print)
yazdir bas on --onayli                           # print fronts
yazdir bas arka --onayli                         # print backs after reloading the stack
```
Requirements and details below (Turkish). License: MIT.

---

## Türkçe

Otomatik arkalı önlü baskı yapamayan yazıcılar (ör. HP LaserJet 1018) için yazdırma aracı.

- **Elle arkalı önlü:** önce ön yüzleri basar, tomarın tamamını yönünü değiştirmeden geri koymanızı ister (kâğıt ayırmak yok), arka yüzleri doğru sırayla basar.
- **Arka yüz yönü:** 2'li sayfa ve kitapçıkta arka yüzler kendiliğinden doğru yöne çevrilir. Bazı yazıcılar arka yüzü baş aşağı basar; bunu uygulamadaki **Yön deneme sayfası** (1 kâğıt) bir kez belirler ve "Yazıcım arka yüzleri ters basıyor — düzelt" ayarını kendisi açar.
- **Sayfa düzeni:** her yüze 1, 2 (yan yana) ya da 4 sayfa; **A5 kitapçık** (ortadan katlanır, sayfalar otomatik dizilir).
- PDF, Word/LibreOffice belgeleri ve resimler.

## Kurulum
Tek komut; Arch/CachyOS/Manjaro, Debian/Ubuntu/Mint, Fedora ve openSUSE'de çalışır. Kullanıcıya kurar,
eksik sistem paketlerini sorduktan sonra `sudo` ile kurar; uygulama menüsüne **Yazdır**, KDE Dolphin
sağ tık menüsüne **Yazdır (arkalı önlü / kitapçık)…** ekler:
```bash
curl -fsSL https://raw.githubusercontent.com/hamer1818/manual-duplex-print/main/install.sh | sh
```
- **Güncelleme:** aynı komutu yeniden çalıştırın.
- **Kaldırma:** `sh ~/.local/share/manual-duplex-print/install.sh --uninstall` (`--purge` ile ayarlar ve önbellek de silinir).
- **Arch tabanlı dağıtımlarda sistem paketi olarak:**
  ```bash
  git clone https://github.com/hamer1818/manual-duplex-print.git
  cd manual-duplex-print/packaging/arch && makepkg -si
  ```
- **Geliştirme:** depo klonundan `./install.sh` düzenlenebilir kurulum yapar; depodaki değişiklikler hemen geçerli olur.

Yazıcı CUPS'ta (sistem ayarları → Yazıcılar) tanımlı olmalı. İlk arkalı önlü baskıdan önce uygulamadaki
**Yön deneme sayfası**nı bir kez basın.

## Gereksinimler
Kurulum betiği bunları denetler ve eksikleri kurmayı önerir. Paketler (Arch adlarıyla):

- `cups` — `lp`, `lpstat`, `cancel`
- `python-pycups` (Debian/Ubuntu: `python3-cups`) — baskı işini CUPS'tan izlemek için
- `python` 3.10+ ve `pyside6` (pencereli uygulama için, sistemden)
- `poppler` — önizleme için `pdftoppm`
- `libreoffice` — Word/ODT/PowerPoint/Excel dosyaları için (yalnız PDF basacaksanız gerekmez)
- `imagemagick` — resim dosyaları için
- `pypdf` — kurulum betiği sanal ortama kurar

## Kararlılık
- İş durumu doğrudan CUPS'tan okunur. Kâğıt biterse, sıkışırsa, kablo çıkarsa uyarı gösterilir ve
  baskı bekler; sorun kalkınca kendiliğinden sürer. İptal edilen iş "basıldı" sayılmaz.
- Ön ve arka yüz arasında pencere kapanırsa (ya da bilgisayar yeniden başlarsa) uygulama açılınca
  kaldığı yerden devam etmeyi önerir.
- Günlük: `~/.cache/yazdir/yazdir.log`. 14 günden eski işler kendiliğinden silinir.

## Testler
```bash
./test.sh        # yazıcıya, ayarlara ve önbelleğe dokunmaz; ~2 sn
```

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

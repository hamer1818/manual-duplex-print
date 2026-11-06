# Yazdır

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
git clone https://github.com/hamer1818/yazdir.git
cd yazdir
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
```
Ayrıntı: `yazdir --help`. `bas`, `--onayli` olmadan kâğıda hiçbir şey göndermez
(yapay zekâ asistanı kullanırken yanlışlıkla baskıyı önlemek için).

## Claude Code yönergesi
`install.sh`, `skill/SKILL.md` dosyasını `~/.claude/skills/yazdir/` altına bağlar; böylece Claude Code
"şunu arkalı önlü yazdır" gibi istekleri bu araçla yapar ve her baskıdan önce onay ister.

## Lisans
MIT — bkz. [LICENSE](LICENSE).

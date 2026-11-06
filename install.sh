#!/bin/sh
# Manual Duplex Print (Yazdır) — kurulum / installer
#
#   curl -fsSL https://raw.githubusercontent.com/hamer1818/manual-duplex-print/main/install.sh | sh
#   ./install.sh                 # depo klonundan (geliştirme: `git pull` ile güncellenir)
#   ./install.sh --yes           # eksik paketleri sormadan kur
#   ./install.sh --uninstall     # kaldır (ayarlar ve önbellek kalır)
#   ./install.sh --uninstall --purge   # ayarları ve önbelleği de sil
#
# Kullanıcıya kurar (root gerekmez); yalnız eksik sistem paketleri için, sorduktan sonra sudo kullanır.
# Yer: ~/.local/share/manual-duplex-print (sanal ortam), komutlar ~/.local/bin, menü kısayolu,
# KDE Dolphin sağ tık menüsü; ~/.claude varsa Claude Code yönergesi.
set -eu

DEPO="https://github.com/hamer1818/manual-duplex-print"
VERI="${XDG_DATA_HOME:-$HOME/.local/share}"
HEDEF="$VERI/manual-duplex-print"
BIN="$HOME/.local/bin"
UYGULAMALAR="$VERI/applications"
SERVIS="$VERI/kio/servicemenus"
YONERGE="$HOME/.claude/skills/yazdir"

case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in tr*) TR=1 ;; *) TR=0 ;; esac
m() { if [ "$TR" = 1 ]; then printf '%s\n' "$1"; else printf '%s\n' "$2"; fi; }
adim() { printf '\033[1m→ %s\033[0m\n' "$(m "$1" "$2")"; }
uyari() { printf '\033[33m!! %s\033[0m\n' "$(m "$1" "$2")" >&2; }
olum() { printf '\033[31m✗ %s\033[0m\n' "$(m "$1" "$2")" >&2; exit 1; }
var() { command -v "$1" >/dev/null 2>&1; }

EVET=0 KALDIR=0 TEMIZLE=0
for a in "$@"; do
    case "$a" in
        -y|--yes|--evet) EVET=1 ;;
        --uninstall|--kaldir) KALDIR=1 ;;
        --purge|--temizle) TEMIZLE=1 ;;
        -h|--help|--yardim) sed -n '2,13p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) olum "Bilinmeyen seçenek: $a" "Unknown option: $a" ;;
    esac
done

sor() {  # sor "soru tr" "question en" -> 0 = evet
    [ "$EVET" = 1 ] && return 0
    # curl | sh ile çalışırken stdin betiğin kendisidir; cevap terminalden okunur
    if [ -r /dev/tty ]; then
        printf '%s [E/h] ' "$(m "$1" "$2")" >/dev/tty
        read -r c </dev/tty || c=h
    else
        return 1
    fi
    case "$c" in ""|e|E|evet|y|Y|yes) return 0 ;; *) return 1 ;; esac
}

# ------------------------------------------------------------------ kaldırma
if [ "$KALDIR" = 1 ]; then
    adim "Kaldırılıyor" "Uninstalling"
    for k in yazdir yazdir-gui; do
        # yalnız bizim bağlantılarımızı sil
        if [ -L "$BIN/$k" ]; then
            case "$(readlink "$BIN/$k")" in *manual-duplex-print*|*/bin/yazdir*) rm -f "$BIN/$k" ;; esac
        fi
    done
    rm -f "$UYGULAMALAR/yazdir.desktop" "$SERVIS/yazdir.desktop"
    [ -e "$YONERGE/.manual-duplex-print" ] && rm -rf "$YONERGE"
    rm -rf "$HEDEF"
    var update-desktop-database && update-desktop-database "$UYGULAMALAR" 2>/dev/null || true
    if [ "$TEMIZLE" = 1 ]; then
        rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/yazdir" "${XDG_CACHE_HOME:-$HOME/.cache}/yazdir"
        m "Ayarlar ve önbellek de silindi." "Settings and cache removed too."
    else
        m "Ayarlar (~/.config/yazdir) ve önbellek (~/.cache/yazdir) duruyor; silmek için --purge." \
          "Settings (~/.config/yazdir) and cache (~/.cache/yazdir) were kept; use --purge to remove them."
    fi
    m "Kaldırıldı." "Uninstalled."
    exit 0
fi

# ------------------------------------------------------------------ kaynak
GECICI=""
temizlik() { [ -n "$GECICI" ] && rm -rf "$GECICI"; return 0; }
trap temizlik EXIT INT TERM

BETIK_DIZINI=""
case "$0" in */install.sh|install.sh) BETIK_DIZINI="$(cd "$(dirname "$0")" && pwd)" ;; esac
if [ -n "$BETIK_DIZINI" ] && [ -f "$BETIK_DIZINI/pyproject.toml" ] && [ -d "$BETIK_DIZINI/yazdir" ]; then
    KAYNAK="$BETIK_DIZINI"
    GELISTIRME=1   # depodan: düzenlenebilir kurulum, `git pull` yeterli
else
    GELISTIRME=0
    adim "İndiriliyor: $DEPO" "Downloading: $DEPO"
    GECICI="$(mktemp -d)"
    ARSIV="${MDP_ARSIV:-$DEPO/archive/refs/heads/main.tar.gz}"   # MDP_ARSIV: deneme/çatal için başka arşiv
    if var curl; then curl -fsSL "$ARSIV" -o "$GECICI/k.tar.gz"
    elif var wget; then wget -qO "$GECICI/k.tar.gz" "$ARSIV"
    else olum "curl ya da wget gerekli." "curl or wget is required."; fi
    tar -xzf "$GECICI/k.tar.gz" -C "$GECICI"
    KAYNAK="$(find "$GECICI" -mindepth 1 -maxdepth 1 -type d | head -n1)"
fi

# ------------------------------------------------------------------ sistem paketleri
YONETICI=""
for y in pacman apt-get dnf zypper; do var "$y" && { YONETICI="$y"; break; }; done

paket_adi() {  # paket_adi ihtiyaç -> dağıtımdaki paket adı (boş = bilinmiyor)
    case "$YONETICI:$1" in
        pacman:cups) echo cups ;;           apt-get:cups) echo cups ;;
        dnf:cups|zypper:cups) echo cups ;;
        pacman:python) echo python ;;       apt-get:python) echo "python3 python3-venv" ;;
        dnf:python|zypper:python) echo python3 ;;
        pacman:pyside6) echo pyside6 ;;     apt-get:pyside6) echo "python3-pyside6.qtwidgets python3-pyside6.qtgui python3-pyside6.qtcore" ;;
        dnf:pyside6) echo python3-pyside6 ;; zypper:pyside6) echo python3-pyside6 ;;
        pacman:pycups) echo python-pycups ;; apt-get:pycups) echo python3-cups ;;
        dnf:pycups) echo python3-cups ;;    zypper:pycups) echo python3-pycups ;;
        pacman:poppler) echo poppler ;;     apt-get:poppler|dnf:poppler) echo poppler-utils ;;
        zypper:poppler) echo poppler-tools ;;
        pacman:libreoffice) echo libreoffice-fresh ;; *:libreoffice) echo libreoffice-writer ;;
        pacman:imagemagick|apt-get:imagemagick) echo imagemagick ;; *:imagemagick) echo ImageMagick ;;
    esac
}

paket_kur() {  # paket_kur paket...
    [ "$(id -u)" = 0 ] && S="" || S="sudo"
    case "$YONETICI" in
        pacman) $S pacman -S --needed $( [ "$EVET" = 1 ] && echo --noconfirm ) "$@" ;;
        apt-get) $S apt-get update -qq && $S apt-get install $( [ "$EVET" = 1 ] && echo -y ) "$@" ;;
        dnf) $S dnf install $( [ "$EVET" = 1 ] && echo -y ) "$@" ;;
        zypper) $S zypper install $( [ "$EVET" = 1 ] && echo -y ) "$@" ;;
    esac
}

python_tamam() { python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; }
pymodul() { python3 -c "import $1" 2>/dev/null; }

eksik_zorunlu() {
    E=""
    { var lp && var lpstat && var cancel; } || E="$E cups"
    python_tamam && python3 -c 'import venv, ensurepip' 2>/dev/null || E="$E python"
    pymodul PySide6.QtWidgets || E="$E pyside6"
    pymodul cups || E="$E pycups"
    var pdftoppm || E="$E poppler"
    echo "$E"
}

adim "Gerekli paketler denetleniyor" "Checking required packages"
EKSIK="$(eksik_zorunlu)"
ISTEGE=""
var soffice || ISTEGE="$ISTEGE libreoffice"
{ var magick || var convert; } || ISTEGE="$ISTEGE imagemagick"

if [ -n "$EKSIK" ]; then
    PAKETLER=""
    for e in $EKSIK; do PAKETLER="$PAKETLER $(paket_adi "$e")"; done
    PAKETLER="$(echo $PAKETLER)"
    if [ -n "$YONETICI" ] && [ -n "$PAKETLER" ]; then
        m "Eksik: $PAKETLER" "Missing: $PAKETLER"
        if sor "Bunlar $YONETICI ile kurulsun mu (sudo)?" "Install them with $YONETICI (sudo)?"; then
            # shellcheck disable=SC2086
            paket_kur $PAKETLER || uyari "Paket kurulumu başarısız oldu." "Package installation failed."
        fi
    else
        uyari "Paket yöneticisi tanınmadı; şunları kendiniz kurun:$EKSIK" \
              "Unknown package manager; please install these yourself:$EKSIK"
    fi
    EKSIK="$(eksik_zorunlu)"
fi

if [ -n "$ISTEGE" ] && [ -n "$YONETICI" ]; then
    PAKETLER=""
    for e in $ISTEGE; do PAKETLER="$PAKETLER $(paket_adi "$e")"; done
    PAKETLER="$(echo $PAKETLER)"
    m "İsteğe bağlı (Word/ODT ve resim dosyaları için): $PAKETLER" \
      "Optional (for Word/ODT and image files): $PAKETLER"
    if [ "$EVET" = 0 ] && sor "Bunlar da kurulsun mu?" "Install these too?"; then
        # shellcheck disable=SC2086
        paket_kur $PAKETLER || uyari "İsteğe bağlı paketler kurulamadı." "Optional packages could not be installed."
    fi
fi

case " $EKSIK " in *" cups "*|*" python "*|*" poppler "*)
    olum "Zorunlu paketler eksik:$EKSIK — kurup betiği yeniden çalıştırın." \
         "Required packages are missing:$EKSIK — install them and run the installer again." ;;
esac

# ------------------------------------------------------------------ uygulama
adim "Kuruluyor: $HEDEF" "Installing into: $HEDEF"
mkdir -p "$HEDEF"
if [ ! -x "$HEDEF/venv/bin/python" ]; then
    python3 -m venv --system-site-packages "$HEDEF/venv" \
        || olum "Python sanal ortamı oluşturulamadı (Debian/Ubuntu: python3-venv)." \
                "Could not create a Python virtual environment (Debian/Ubuntu: python3-venv)."
fi
PIP="$HEDEF/venv/bin/python -m pip --disable-pip-version-check -q"
# Dağıtımda PySide6/pycups yoksa pip'ten (PySide6 büyük bir indirmedir; pycups derleme ister)
case " $EKSIK " in *" pyside6 "*)
    uyari "PySide6 dağıtım paketi yok; pip ile indiriliyor (~200 MB)." "No PySide6 system package; downloading via pip (~200 MB)."
    $PIP install PySide6 || olum "PySide6 kurulamadı." "Could not install PySide6." ;;
esac
case " $EKSIK " in *" pycups "*)
    uyari "pycups dağıtım paketi yok; pip ile derleniyor (libcups geliştirme dosyaları ve gcc gerekir)." \
          "No pycups system package; building via pip (needs libcups headers and gcc)."
    $PIP install pycups || olum "pycups kurulamadı." "Could not install pycups." ;;
esac
if [ "$GELISTIRME" = 1 ]; then
    $PIP install -e "$KAYNAK"
else
    $PIP install --upgrade "$KAYNAK"
fi
"$HEDEF/venv/bin/python" -c "import yazdir.gui, yazdir.cli" \
    || olum "Kurulum doğrulanamadı." "The installation could not be verified."
SURUM="$("$HEDEF/venv/bin/python" -c 'import yazdir; print(yazdir.__version__)')"
cp "$KAYNAK/install.sh" "$HEDEF/install.sh"   # curl ile kurana da kaldırma/güncelleme betiği kalsın

adim "Komutlar: $BIN/yazdir, $BIN/yazdir-gui" "Commands: $BIN/yazdir, $BIN/yazdir-gui"
mkdir -p "$BIN"
ln -sf "$HEDEF/venv/bin/yazdir" "$BIN/yazdir"
ln -sf "$HEDEF/venv/bin/yazdir-gui" "$BIN/yazdir-gui"

adim "Uygulama menüsü ve Dolphin sağ tık menüsü" "Application menu and Dolphin context menu"
mkdir -p "$UYGULAMALAR" "$SERVIS"
# Masaüstü oturumunda ~/.local/bin PATH'te olmayabilir: tam yol yazılır
sed "s|^Exec=yazdir-gui|Exec=$HEDEF/venv/bin/yazdir-gui|" "$KAYNAK/packaging/yazdir.desktop" > "$UYGULAMALAR/yazdir.desktop"
sed "s|^Exec=yazdir-gui|Exec=$HEDEF/venv/bin/yazdir-gui|" "$KAYNAK/packaging/yazdir-servicemenu.desktop" > "$SERVIS/yazdir.desktop"
chmod +x "$SERVIS/yazdir.desktop"
var update-desktop-database && update-desktop-database "$UYGULAMALAR" 2>/dev/null || true

if [ -d "$HOME/.claude" ]; then
    adim "Claude Code yönergesi: $YONERGE" "Claude Code skill: $YONERGE"
    mkdir -p "$YONERGE"
    if [ "$GELISTIRME" = 1 ]; then ln -sf "$KAYNAK/skill/SKILL.md" "$YONERGE/SKILL.md"
    else rm -f "$YONERGE/SKILL.md"; cp "$KAYNAK/skill/SKILL.md" "$YONERGE/SKILL.md"; fi
    : > "$YONERGE/.manual-duplex-print"
fi

case ":$PATH:" in *":$BIN:"*) ;; *)
    uyari "$BIN PATH'te değil; komut satırından 'yazdir' için kabuk ayarınıza ekleyin." \
          "$BIN is not in PATH; add it to your shell config to use 'yazdir' from a terminal." ;;
esac
if ! pymodul cups && ! "$HEDEF/venv/bin/python" -c "import cups" 2>/dev/null; then
    uyari "pycups yok: baskı izlenemez." "pycups is missing: print jobs cannot be followed."
fi
if ! lpstat -e 2>/dev/null | grep -q .; then
    uyari "CUPS'ta tanımlı yazıcı yok. Yazıcınızı sistem ayarlarından ekleyin." \
          "No printer is set up in CUPS. Add your printer in the system settings."
fi

echo
m "Kurulum tamam (sürüm $SURUM). Menüde 'Yazdır'; Dolphin'de dosyaya sağ tık → 'Yazdır (arkalı önlü / kitapçık)…'." \
  "Installed (version $SURUM). Find 'Manual Duplex Print' in the menu; in Dolphin right-click a file → 'Print (two-sided / booklet)…'."
m "İlk arkalı önlü baskıdan önce bir kez 'Yön deneme sayfası'nı basın." \
  "Print the 'Orientation test page' once before your first two-sided job."
m "Kaldırmak için: sh $HEDEF/install.sh --uninstall" "To uninstall: sh $HEDEF/install.sh --uninstall"
[ "$GELISTIRME" = 1 ] && m "Geliştirme kurulumu: depodaki değişiklikler hemen geçerli." "Development install: changes in the repository take effect immediately."
exit 0

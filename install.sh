#!/bin/sh
# Yazdır kurulumu: sanal ortam, komutlar, menü kısayolu, Dolphin sağ tık menüsü, Claude yönergesi.
set -e
D="$(cd "$(dirname "$0")" && pwd)"

echo "→ Python ortamı (.venv) hazırlanıyor"
[ -x "$D/.venv/bin/python" ] || python3 -m venv --system-site-packages "$D/.venv"
"$D/.venv/bin/pip" install -q --upgrade pypdf
"$D/.venv/bin/python" -c "import cups" 2>/dev/null || {
    echo "!! pycups bulunamadı (baskı izleme için gerekli). Kurun: Arch 'python-pycups', Debian/Ubuntu 'python3-cups'"
    echo "!! pycups is missing (needed to follow print jobs). Install: Arch 'python-pycups', Debian/Ubuntu 'python3-cups'"
}

echo "→ Komutlar: ~/.local/bin/yazdir, ~/.local/bin/yazdir-gui"
mkdir -p "$HOME/.local/bin"
ln -sf "$D/bin/yazdir" "$HOME/.local/bin/yazdir"
ln -sf "$D/bin/yazdir-gui" "$HOME/.local/bin/yazdir-gui"

MIME="application/pdf;application/msword;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/vnd.oasis.opendocument.text;application/rtf;text/plain;application/vnd.openxmlformats-officedocument.presentationml.presentation;application/vnd.ms-powerpoint;application/vnd.oasis.opendocument.presentation;image/png;image/jpeg;image/webp;"

echo "→ Uygulama menüsü"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/yazdir.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Manual Duplex Print
Name[tr]=Yazdır
GenericName=Advanced printing
GenericName[tr]=Gelişmiş yazdırma
Comment=Manual two-sided, 2/4 pages per side and booklet printing
Comment[tr]=Elle arkalı önlü, sayfa başına 2/4 sayfa ve kitapçık baskısı
Exec=$D/bin/yazdir-gui %f
Icon=document-print
Terminal=false
Categories=Office;Utility;
MimeType=$MIME
DESK

echo "→ Dolphin sağ tık menüsü"
SM="$HOME/.local/share/kio/servicemenus"
mkdir -p "$SM"
cat > "$SM/yazdir.desktop" <<DESK
[Desktop Entry]
Type=Service
MimeType=$MIME
Actions=yazdir;
X-KDE-Priority=TopLevel

[Desktop Action yazdir]
Name=Print (two-sided / booklet)…
Name[tr]=Yazdır (arkalı önlü / kitapçık)…
Icon=document-print
Exec=$D/bin/yazdir-gui %f
DESK
chmod +x "$SM/yazdir.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "→ Claude yönergesi: ~/.claude/skills/yazdir"
mkdir -p "$HOME/.claude/skills/yazdir"
ln -sf "$D/skill/SKILL.md" "$HOME/.claude/skills/yazdir/SKILL.md"

echo "Kurulum tamam. Menüde 'Yazdır', Dolphin'de dosyaya sağ tık → 'Yazdır (arkalı önlü / kitapçık)…'"

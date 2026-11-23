#!/usr/bin/env bash
set -euo pipefail

HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_BIN="$HERE/zoe-desktop"
ICON_PATH="$HERE/icon.png"
chmod +x "$APP_BIN"

mkdir -p "$HOME/.local/share/applications"
DESKTOP_FILE="$HOME/.local/share/applications/zoe-desktop.desktop"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Zoe
GenericName=Dorothy 3D Brain Research Partner
Comment=Zoe Research Partner and Dorothy 3D Brain Observatory
Exec="$APP_BIN"
Icon=$ICON_PATH
Terminal=false
Categories=Science;Education;MedicalSoftware;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
if [ -d "$HOME/Desktop" ]; then
  cp "$DESKTOP_FILE" "$HOME/Desktop/Zoe.desktop"
  chmod +x "$HOME/Desktop/Zoe.desktop"
fi
echo "Installed Zoe Desktop launcher at $DESKTOP_FILE"

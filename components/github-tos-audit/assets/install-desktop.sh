#!/bin/sh
# Install the TOS GEM desktop launcher and icon for the current user.
set -eu

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"

sed -e "s|@REPO@|$REPO|g" "$REPO/assets/tos-gem.desktop" > "$APPS/tos-gem.desktop"

if [ -d "$HOME/Desktop" ]; then
    cp "$APPS/tos-gem.desktop" "$HOME/Desktop/tos-gem.desktop"
    chmod +x "$HOME/Desktop/tos-gem.desktop"
    command -v gio >/dev/null 2>&1 && \
        gio set "$HOME/Desktop/tos-gem.desktop" metadata::trusted true || true
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPS" || true

echo "Installed TOS GEM launcher (icon: $REPO/assets/gem3ico.png)"

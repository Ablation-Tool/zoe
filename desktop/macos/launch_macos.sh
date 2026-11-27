#!/usr/bin/env bash
set -euo pipefail
MACOS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RES_DIR="$(CDPATH= cd -- "$MACOS_DIR/../Resources" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
exec python3 "$RES_DIR/desktop/zoe_desktop.py" "$@"

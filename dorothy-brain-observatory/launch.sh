#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8765}"
echo "Starting Dorothy Brain Observatory at http://127.0.0.1:${PORT}/"
(sleep 1 && xdg-open "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || true) &
cd "$DIR"
exec python3 -m http.server "$PORT" --bind 127.0.0.1

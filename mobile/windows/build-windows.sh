#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
: "${ZOE_MINGW_ROOT:?Set ZOE_MINGW_ROOT to the LLVM-MinGW installation}"
BUILD_DIR="${BUILD_DIR:-$ROOT/mobile/build/windows}"
DIST_DIR="${DIST_DIR:-$ROOT/mobile/dist/windows}"

cmake -S "$ROOT/mobile/windows" -B "$BUILD_DIR" \
  -DCMAKE_TOOLCHAIN_FILE="$ROOT/mobile/windows/toolchain-llvm-mingw.cmake" \
  -DZOE_MINGW_ROOT="$ZOE_MINGW_ROOT" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --parallel "${BUILD_JOBS:-4}"

mkdir -p "$DIST_DIR"
cp "$BUILD_DIR/ZoeTrinity.exe" "$DIST_DIR/ZoeTrinity.exe"
cp "$BUILD_DIR/trinity_core_tests.exe" "$DIST_DIR/trinity_core_tests.exe"

if [[ "${RUN_WINE_TESTS:-0}" == "1" ]]; then
  WINEDEBUG=-all wine "$DIST_DIR/trinity_core_tests.exe"
fi

(
  cd "$DIST_DIR"
  sha256sum ZoeTrinity.exe trinity_core_tests.exe > SHA256SUMS.txt
)
cp "$ROOT/mobile/windows/README.md" "$DIST_DIR/README.md"
cp "$ROOT/mobile/docs/images/zoe-trinity-native-windows.png" "$DIST_DIR/ZoeTrinity.png"
DIST_DIR="$DIST_DIR" python3 - <<'PY'
import os
from pathlib import Path
import zipfile
root = Path(os.environ['DIST_DIR'])
archive = root.parent / 'ZoeTrinity-Windows-x86_64.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
    for name in ('ZoeTrinity.exe', 'trinity_core_tests.exe', 'SHA256SUMS.txt', 'README.md', 'ZoeTrinity.png'):
        output.write(root / name, arcname=f'ZoeTrinity/{name}')
print(f'Portable archive: {archive}')
PY
printf 'Native Windows artifacts: %s\n' "$DIST_DIR"

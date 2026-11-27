#!/usr/bin/env python3
"""Refresh standalone offline Zoe Web Studio HTML exports and optionally push to Pixel 7.

Generates all 4 standalone offline HTML workbenches (`artline_studio.html`,
`physics_room.html`, `adc12_catalog.html`, `zoe_artline_forge.html`) plus
`studio_manifest.json` with `external_actions = 0` and `cloud_tokens_used = 0`
by default. Only when `--push-pixel` is explicitly passed does it attempt an
`adb` push to the attached Pixel 7 (`/sdcard/Download/zoe-studio`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
_GUIAI_LAB = str(ROOT / "guiai-lab")
if _GUIAI_LAB not in sys.path:
    sys.path.insert(0, _GUIAI_LAB)

from guiai.gem.zoe_artline_cli import (  # noqa: E402
    DEFAULT_PIXEL_REMOTE_DIR,
    DEFAULT_PIXEL_SERIAL,
    sync_studio_assets,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sync_zoe_studio",
        description="Refresh offline Zoe Artline/Studio HTML exports & optional Pixel 7 adb sync",
    )
    p.add_argument(
        "--out-dir",
        "--output-dir",
        dest="out_dir",
        default=None,
        help="Destination directory for offline HTML exports (default ~/.zoe/artline/studio)",
    )
    p.add_argument(
        "--archive-root",
        default=None,
        help="Optional override path for extracted Artline archive",
    )
    p.add_argument(
        "--push-pixel",
        action="store_true",
        help="Push exported HTMLs and manifest via adb to attached Pixel 7",
    )
    p.add_argument(
        "--device-serial",
        default=DEFAULT_PIXEL_SERIAL,
        help=f"Target adb device serial (default {DEFAULT_PIXEL_SERIAL})",
    )
    p.add_argument(
        "--remote-dir",
        default=DEFAULT_PIXEL_REMOTE_DIR,
        help=f"Remote directory on Pixel 7 (default {DEFAULT_PIXEL_REMOTE_DIR})",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON result payload",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(list(argv) if argv is not None else None)
    res = sync_studio_assets(
        ns.out_dir,
        push_pixel=bool(ns.push_pixel),
        device_serial=str(ns.device_serial),
        remote_dir=str(ns.remote_dir),
        archive_root=ns.archive_root,
    )
    if ns.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(
            f"Synced {res['html_count']} offline studio HTMLs to {res['out_dir']} "
            f"(pixel_pushed={res['pixel_pushed']}, external_actions={res['external_actions']}, "
            f"cloud_tokens_used={res['cloud_tokens_used']})"
        )
        if res.get("error"):
            print(f"Note: {res['error']}")
    return 0


__all__ = [
    "DEFAULT_PIXEL_REMOTE_DIR",
    "DEFAULT_PIXEL_SERIAL",
    "build_parser",
    "main",
    "sync_studio_assets",
]

if __name__ == "__main__":
    raise SystemExit(main())

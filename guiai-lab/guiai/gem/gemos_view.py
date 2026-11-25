"""Unified `zoe gemos` CLI view for Zoe-GEM OS, Pixel 7 Panther, Braille Studio, Themes, and Zoeverse."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

from .zoe_braille_studio import render_braille_template, render_dvx_app_manager
from .zoe_gem_os.zoe_pixel_os import list_pixel_devices, verify_pixel_os_static
from .zoe_gem_themes import list_gem_eras, list_viewmax_schemes, render_viewmax_ini, resolve_viewmax_scheme
from .zoe_sisters import list_sisters
from .zoe_universe import list_zoeverse_realms, render_realm_braille_vista, resolve_realm

REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    """Build the `zoe gemos` subcommand parser."""
    parser = argparse.ArgumentParser(
        prog="zoe gemos",
        description="Zoe-GEM OS Ecosystem: Pixel 7 Sovereign OS, Braille Studio, ViewMAX Themes, and Zoeverse",
    )
    sub = parser.add_subparsers(dest="action")

    st = sub.add_parser("status", help="summarize Zoe-GEM OS pillars and constitutional honesty flags")
    st.add_argument("--json", action="store_true", help="emit JSON")

    ver = sub.add_parser("verify", help="run the 8-check offline Zoe-GEM OS suite verifier")
    ver.add_argument("--json", action="store_true", help="emit full JSON verification report")

    px = sub.add_parser("pixel", help="statically verify Pixel 7-9 profiles and deterministic ARM64 initramfs")
    px.add_argument("--device", default="panther", help="Pixel codename or alias (default: panther)")
    px.add_argument("--json", action="store_true", help="emit JSON")

    br = sub.add_parser("braille", help="render 2x4 Unicode Braille dot-art or DESQview/X app manager")
    br.add_argument("template", nargs="?", default="zoe", help="zoe | flower | jellyfish | dvx")
    br.add_argument("--cols", type=int, default=52, help="character column width")

    th = sub.add_parser("themes", help="inspect 8 historic GEM eras and 10 ViewMAX/2 color schemes")
    th.add_argument("--scheme", default="", help="optional scheme key or slot (1..10) to render INI")
    th.add_argument("--json", action="store_true", help="emit JSON")

    rl = sub.add_parser("realms", help="list the 9 Zoeverse realms or render a realm Braille vista")
    rl.add_argument("--realm", default="", help="optional realm key or compass direction")
    rl.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _cmd_status(args: argparse.Namespace) -> int:
    payload = {
        "contract": "zoe-gemos-cli/v1",
        "pixel_devices": len(list_pixel_devices()),
        "gem_eras": len(list_gem_eras()),
        "viewmax_schemes": len(list_viewmax_schemes()),
        "zoeverse_realms": len(list_zoeverse_realms()),
        "sisters_count": len(list_sisters()),
        "loopback_only": True,
        "auto_flash_allowed": False,
        "external_actions": 0,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
    }
    _emit(payload, bool(args.json))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import verify_zoe_gem_os_suite

    argv = ["--json"] if args.json else []
    return int(verify_zoe_gem_os_suite.main(argv))


def _cmd_pixel(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="zoe-gemos-pixel-") as td:
        report = verify_pixel_os_static(Path(td), device=args.device)
    _emit(report, bool(args.json))
    return 0 if report.get("ok") else 1


def _cmd_braille(args: argparse.Namespace) -> int:
    target = str(args.template or "zoe").strip().lower()
    if target == "dvx":
        print("\n".join(render_dvx_app_manager()))
        return 0
    title, lines = render_braille_template(target, cols=max(16, int(args.cols)))
    print(title)
    print("\n".join(lines))
    return 0


def _cmd_themes(args: argparse.Namespace) -> int:
    if args.scheme:
        scheme = resolve_viewmax_scheme(args.scheme)
        ini_text = render_viewmax_ini(active_slot=scheme.slot)
        if args.json:
            _emit({"scheme": scheme.key, "slot": scheme.slot, "name": scheme.name, "ini": ini_text}, True)
        else:
            print(ini_text)
        return 0
    payload = {
        "eras": [{"key": e.key, "year": e.year, "name": e.name} for e in list_gem_eras()],
        "schemes": [{"slot": s.slot, "key": s.key, "name": s.name, "era": s.era_anchor} for s in list_viewmax_schemes()],
    }
    _emit(payload, bool(args.json))
    return 0


def _cmd_realms(args: argparse.Namespace) -> int:
    if args.realm:
        realm = resolve_realm(args.realm)
        vista = render_realm_braille_vista(realm)
        if args.json:
            _emit({"key": realm.key, "title": realm.title, "sister_signet": realm.sister_signet, "vista": vista}, True)
        else:
            print(f"{realm.title} ({realm.compass} · signet={realm.sister_signet})")
            print("\n".join(vista))
        return 0
    payload = {
        "realms": [
            {"key": r.key, "compass": r.compass, "title": r.title, "sister_signet": r.sister_signet}
            for r in list_zoeverse_realms()
        ]
    }
    _emit(payload, bool(args.json))
    return 0


_HANDLERS = {
    "status": _cmd_status,
    "verify": _cmd_verify,
    "pixel": _cmd_pixel,
    "braille": _cmd_braille,
    "themes": _cmd_themes,
    "realms": _cmd_realms,
}


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for `zoe gemos`."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = _HANDLERS.get(args.action or "status")
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

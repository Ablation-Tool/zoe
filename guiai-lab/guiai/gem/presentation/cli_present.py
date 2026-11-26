"""`zoe present` CLI Subcommand Handlers (`build`, `render`, `inspect`, `play`, `demo`).

Runs 100% offline in pure Python with zero Office/LibreOffice/pdftoppm dependency.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import webbrowser

from guiai.gem import seasip_gem, vdi

from .draw_plus import DrawPlusCanvas
from .graph import GraphDoc
from .renderer import PresentationRenderer
from .slideshow import Slide, SlideDeck, validate_lis_playlist
from .wordchart import WordChartDoc


def register_present_subparser(commands: Any) -> None:
    """Register `zoe present` subparser and its `build/render/inspect/play/demo` actions."""
    present = commands.add_parser("present", help="build, render, inspect, and play Zoe Presentation Team decks")
    sub = present.add_subparsers(dest="present_action")

    p_build = sub.add_parser("build", help="compile a deck JSON spec to .gem, images, .lis, and offline player.html")
    p_build.add_argument("spec", help="path to JSON deck specification")
    p_build.add_argument("--output", "-o", required=True, help="output directory for built deck")
    p_build.add_argument("--no-overwrite", action="store_true", help="refuse to overwrite existing outputs")
    p_build.add_argument("--format", choices=("png", "jpg", "svg", "all"), default="png")
    p_build.add_argument("--json", action="store_true", help="emit JSON output")

    p_render = sub.add_parser("render", help="render .gem file(s) to PNG, JPG, or SVG purely in Python")
    p_render.add_argument("target", help="path to .gem file or directory containing .gem files")
    p_render.add_argument("--output", "-o", help="optional output directory")
    p_render.add_argument("--format", choices=("png", "jpg", "svg"), default="png")
    p_render.add_argument("--width", type=int, default=1920)
    p_render.add_argument("--height", type=int, default=1080)
    p_render.add_argument("--json", action="store_true", help="emit JSON output")

    p_inspect = sub.add_parser("inspect", help="inspect .gem VDI opcodes, RC bounds, and 1001 metadata")
    p_inspect.add_argument("target", help="path to .gem file or deck directory")
    p_inspect.add_argument("--json", action="store_true", help="emit JSON output")

    p_play = sub.add_parser("play", help="validate playlist and open offline Slide Show Player")
    p_play.add_argument("target", help="deck directory, player.html, or .lis playlist path")
    p_play.add_argument("--no-open", action="store_true", help="do not launch browser")
    p_play.add_argument("--json", action="store_true", help="emit JSON output")

    p_demo = sub.add_parser("demo", help="build a clean-room WordChart + Graph demonstration deck")
    p_demo.add_argument("--output", "-o", default="zoe_present_demo", help="output directory")
    p_demo.add_argument("--json", action="store_true", help="emit JSON output")


def _emit(payload: dict[str, Any], *, as_json: bool, summary: str) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(summary)
    return 0


def _handle_build(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    if not spec_path.is_file():
        raise FileNotFoundError(f"Presentation spec not found: {spec_path}")
    deck = SlideDeck.from_spec(spec_path)
    fmt = str(args.format)
    info = deck.build(
        args.output,
        overwrite=not bool(args.no_overwrite),
        render_png=(fmt in ("png", "all")),
        render_jpg=(fmt in ("jpg", "all")),
        render_svg=(fmt in ("svg", "all")),
    )
    return _emit(
        info,
        as_json=bool(args.json),
        summary=f"Built deck '{deck.slug}' ({len(deck.slides)} slides) -> {args.output}",
    )


def _collect_gems(target: Path) -> list[Path]:
    if not target.exists():
        raise FileNotFoundError(f"Target path not found: {target}")
    if target.is_file():
        return [target]
    gems = sorted(target.glob("*.gem"))
    if not gems:
        raise FileNotFoundError(f"No .gem files found in {target}")
    return gems


def _handle_render(args: argparse.Namespace) -> int:
    target = Path(args.target)
    gems = _collect_gems(target)
    out_dir = Path(args.output) if args.output else (target if target.is_dir() else target.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[str] = []
    for gf in gems:
        scene = vdi.scene_from_metafile(gf.read_bytes())
        pr = PresentationRenderer(scene)
        fmt = str(args.format)
        out_file = out_dir / f"{gf.stem}.{fmt}"
        if fmt == "png":
            pr.render_png(out_file, width=int(args.width), height=int(args.height))
        elif fmt == "jpg":
            pr.render_jpg(out_file, width=int(args.width), height=int(args.height))
        else:
            pr.render_svg(out_file, width=int(args.width))
        rendered.append(str(out_file))
    return _emit(
        {"rendered": rendered, "format": args.format},
        as_json=bool(args.json),
        summary=f"Rendered {len(rendered)} {args.format.upper()} file(s) -> {out_dir}",
    )


def _inspect_single_gem(gf: Path) -> dict[str, Any]:
    raw = gf.read_bytes()
    chk = seasip_gem.verify_seasip_gem_metafile(raw)
    parsed = vdi.parse_metafile(raw)
    inv = vdi.opcode_inventory(raw)
    meta_records = [
        json.loads(bytes(v & 0xFF for v in r["values"][1:]).split(b"\0", 1)[0].decode("ascii"))
        for r in parsed["records"]
        if r["command"] == 5 and r["subcommand"] == 99 and r["values"] and r["values"][0] == 1001
    ]
    return {
        "file": str(gf),
        "bytes": len(raw),
        "valid": bool(chk.get("valid")),
        "coordinate_system": chk.get("coordinate_system"),
        "bounds": parsed["header"]["coordinate_bounds"],
        "opcodes": inv,
        "metadata_records": meta_records,
    }


def _handle_inspect(args: argparse.Namespace) -> int:
    gems = _collect_gems(Path(args.target))
    reports = [_inspect_single_gem(gf) for gf in gems]
    payload: dict[str, Any] = reports[0] if len(reports) == 1 else {"files": reports}
    return _emit(
        payload,
        as_json=bool(args.json),
        summary=f"Inspected {len(reports)} .gem metafile(s): valid={all(r['valid'] for r in reports)}",
    )


def _handle_play(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if not target.exists():
        raise FileNotFoundError(f"Play target not found: {target}")
    lis_info: dict[str, Any] = {}
    if target.is_dir():
        lis_files = sorted(target.glob("*.lis"))
        if lis_files:
            pl = validate_lis_playlist(lis_files[0], check_exists=True)
            lis_info = {"lis": str(lis_files[0]), "slides": len(pl.slides), "wait_mode": pl.wait_mode, "cycle": pl.cycle}
        player = target / "player.html"
    elif target.suffix.lower() == ".lis":
        pl = validate_lis_playlist(target, check_exists=True)
        lis_info = {"lis": str(target), "slides": len(pl.slides), "wait_mode": pl.wait_mode, "cycle": pl.cycle}
        player = target.parent / "player.html"
    else:
        player = target

    if not player.is_file():
        raise FileNotFoundError(f"player.html not found at {player}")
    if not args.no_open:
        webbrowser.open(player.resolve().as_uri())
    return _emit(
        {"player": str(player), **lis_info},
        as_json=bool(args.json),
        summary=f"Offline Slide Show Player ready: {player}",
    )


def _handle_demo(args: argparse.Namespace) -> int:
    c1 = DrawPlusCanvas(width=13333, height=7500, title="Zoe Presentation Demo")
    c1.add_botanical_frame(mode="dark")
    c1.add_hero_mandala(cx=6666, cy=4500, radius=1100, petals=9)
    WordChartDoc(
        title="Zoe Clean-Room Presentation Team",
        template="hero_obsidian",
        text_body=["WordChart + Graph + Draw Plus + Offline Player", "100% Pure-Python GEM VDI ($0.00 offline)"],
    ).compile(c1)

    c2 = DrawPlusCanvas(width=13333, height=7500, title="Benchmark Demo")
    GraphDoc(
        title="Calibration Score",
        chart_type="bar",
        categories=["Kloster M4", "Baseline MSP", "Entropy"],
        series=[{"name": "AUROC", "values": [0.8382, 0.8360, 0.8145]}],
    ).compile(c2)

    deck = SlideDeck(
        slug="zoe-demo",
        title="Zoe Presentation Team Demo",
        subtitle="Clean-Room Digital Research Stack",
        slides=[
            Slide(title="Cover", canvas=c1, speaker_notes="Introductory botanical hero slide."),
            Slide(title="Metrics", canvas=c2, speaker_notes="Pure-Python Graph engine benchmark."),
        ],
    )
    info = deck.build(args.output)
    return _emit(info, as_json=bool(args.json), summary=f"Built demo deck -> {args.output}")


def handle_present(arguments: argparse.Namespace) -> int:
    """Dispatch `zoe present` subcommands."""
    action = str(getattr(arguments, "present_action", "") or "")
    handlers = {
        "build": _handle_build,
        "render": _handle_render,
        "inspect": _handle_inspect,
        "play": _handle_play,
        "demo": _handle_demo,
    }
    fn = handlers.get(action)
    if fn is None:
        raise ValueError("Usage: zoe present {build|render|inspect|play|demo} ...")
    return fn(arguments)


__all__ = ["handle_present", "register_present_subparser"]

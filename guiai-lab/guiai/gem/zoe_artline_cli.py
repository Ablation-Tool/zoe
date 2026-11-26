"""Clean-room CLI & Web-Studio Slash-Command Router for Zoe Artline 2.0 Studio.

Provides both:
  1. Standalone terminal CLI (`zoe-artline` / `python3 -m guiai.gem.zoe_artline_cli`):
       zoe-artline brainstorm [desk|chess|sector|mondo|all]
       zoe-artline retro
       zoe-artline physics [off|zero_g|gravity]
       zoe-artline adc12 [query | highlight <tag> <quote...>]
       zoe-artline studio
  2. Live `:8765` Web Studio slash-command handler (`handle_artline_slash_command`)
     for `/artline ...` and `/adc12 ...` right inside the Eliza-GEM chat box.

Constitutional Invariants (`CONSTITUTION.md`):
  clean_room_original = True · external_actions = 0 · sentience_claimed = False
  clinical_action_authorized = False · cure_claim = False · cloud_tokens_used = 0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from .zoe_artline_brainstorm import BRAINSTORM_CONCEPTS, export_all_brainstorm_concepts, export_brainstorm_plate
from .zoe_artline_duodecimal import (
    ADC12_MAJOR_CLASSES,
    ArtlineDuodecimalIndexer,
    build_adc12_reference_plate,
    resolve_adc12,
    write_interactive_adc12_catalog_html,
)
from .zoe_artline_forge import (
    STUDIO_PALETTES,
    STUDIO_TOOLBOXES,
    write_interactive_artline_forge_html,
)
from .zoe_retro_art_studio import run_build_re_rebuild_cycle
from .zoe_wombats_physics_room import (
    build_artline_rosette_wombats_plate,
    render_physics_shatter_gif,
    write_interactive_physics_room_html,
)

ARTLINE_CLI_CONTRACT = "zoe-artline-cli/v1"

EPISTEMIC_BOUNDARIES: dict[str, Any] = {
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "zoe_clone_claimed": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "cloud_tokens_used": 0,
    "external_actions": 0,
}


def _default_out_dir(out_dir: str | Path | None = None) -> Path:
    dest = Path(out_dir or (Path.home() / ".zoe" / "artline")).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def handle_artline_slash_command(
    raw_command: str,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute a `/artline ...` or `/adc12 ...` slash command and return a structured reply dict."""
    text = (raw_command or "").strip()
    parts = text.split()
    head = parts[0].lower() if parts else "/artline"
    args = parts[1:]

    if head in {"/adc12", "/duodecimal"}:
        return _handle_adc12(args)

    if not args or args[0].lower() in {"help", "studio", "list"}:
        reply = (
            "Zoe Artline 2.0 Studio Commands (0 cloud tokens · clean-room):\n"
            "  /artline desk|chess|sector|mondo|all  -> Export Artline Brainstorm .SVG/.PNG/.GEM\n"
            "  /artline retro                        -> Run Gen 1->3 Build->RE->Rebuild evolution loop\n"
            "  /artline physics                      -> Export Page A-2 Wombats rosette & shatter GIF\n"
            "  /artline forge                        -> Export ZOETK001 toolboxes, .COL-as-GEM palettes & Forge HTML\n"
            "  /adc12 [100|90|Z|Σ|✺|all]             -> Base-12 Dewey 4-Column Artline shorthand lookup\n"
            "  /adc12 <tag> <quote>                  -> Stamp highlighted excerpt with SHA-256 receipt\n"
            "Live :8765 Studio Tabs: /artline · /physics · /duodecimal · /forge · /orbit"
        )
        return _wrap_reply("artline_help", reply, {"concepts": sorted(BRAINSTORM_CONCEPTS)})

    sub = args[0].lower()
    if sub in BRAINSTORM_CONCEPTS:
        dest = _default_out_dir(out_dir)
        res = export_brainstorm_plate(sub, out_dir=dest)
        reply = (
            f"[400₁₂ · . · ✎] Exported Artline Brainstorm '{sub}' ({res['elements']} vector elements)\n"
            f"  SVG: {res['paths']['svg']}\n"
            f"  PNG: {res['paths']['png']}\n"
            f"  GEM: {res['paths']['gem']}\n"
            "Open live in browser: http://127.0.0.1:8765/artline"
        )
        return _wrap_reply("artline_brainstorm", reply, res)

    if sub == "all":
        dest = _default_out_dir(out_dir)
        items = export_all_brainstorm_concepts(dest)
        reply = f"[400₁₂ · . · ✎] Exported all {len(items)} Artline Brainstorm concepts to {dest}"
        return _wrap_reply("artline_brainstorm_all", reply, {"count": len(items), "out_dir": str(dest)})

    if sub == "retro":
        dest = _default_out_dir(out_dir) / "retro"
        res = run_build_re_rebuild_cycle(dest)
        reply = (
            f"[500₁₂ · l · ●] Clean-Room Retro Evolution Complete (Gen 1->3 score gain: +{res['score_gain_gen1_to_gen3']} pts · "
            f"monotonic={res['monotonically_improved']})\n"
            f"  Output dir: {dest}"
        )
        return _wrap_reply("artline_retro", reply, res)

    if sub == "physics":
        dest = _default_out_dir(out_dir) / "physics"
        dest.mkdir(parents=True, exist_ok=True)
        doc, meta = build_artline_rosette_wombats_plate(petals=9)
        for ext in ("svg", "png", "gem"):
            doc.export(dest / f"artline_rosette_wombats.{ext}", kind=ext)
        gif_info = render_physics_shatter_gif(dest / "physics_shatter.gif", frames=30)
        html_p = write_interactive_physics_room_html(dest / "physics_room.html")
        reply = (
            f"[E00₁₂ · , · ✌] Optional-Physics Room & Page A-2 Wombats Exported ({gif_info['shatter_events']} shatter bursts)\n"
            f"  GIF : {gif_info['gif_path']}\n"
            f"  HTML: {html_p}\n"
            "Open live in browser: http://127.0.0.1:8765/physics"
        )
        return _wrap_reply("artline_physics", reply, {"rosette": meta, "gif": gif_info, "html": str(html_p)})

    if sub == "forge":
        dest = _default_out_dir(out_dir) / "forge"
        dest.mkdir(parents=True, exist_ok=True)
        pal_results = [pal.export_col_gem(dest / "palettes") for pal in STUDIO_PALETTES]
        tb_dir = dest / "toolboxes"
        tb_dir.mkdir(parents=True, exist_ok=True)
        tb_paths = []
        for tb in STUDIO_TOOLBOXES:
            p = tb_dir / f"{tb.toolbox_id}.zoetk"
            p.write_bytes(tb.to_zoetk_binary())
            tb_paths.append(str(p))
        html_p = write_interactive_artline_forge_html(dest / "zoe_artline_forge.html")
        reply = (
            f"[500₁₂ · l · ●] Clean-Room Zoe Artline Forge Exported "
            f"({len(pal_results)} .COL-as-GEM palettes · {len(tb_paths)} ZOETK001 toolboxes)\n"
            f"  HTML: {html_p}\n"
            "Open live in browser: http://127.0.0.1:8765/forge"
        )
        return _wrap_reply(
            "artline_forge",
            reply,
            {"palettes": pal_results, "toolboxes": tb_paths, "html": str(html_p)},
        )

    if sub in {"adc12", "duodecimal"}:
        return _handle_adc12(args[1:])

    raise ValueError(
        f"Unknown /artline subcommand {sub!r}. Try: desk, chess, sector, mondo, all, retro, physics, forge, adc12."
    )


def _handle_adc12(args: list[str]) -> dict[str, Any]:
    if not args or args[0].lower() in {"all", "list"}:
        lines = ["Artline Duodecimal Classification (ADC-12 · 12 Major Base-12 Classes):"]
        for entry in ADC12_MAJOR_CLASSES:
            lines.append(
                f"  {entry.call_badge}  Dec {entry.decimal_code:3d} ({entry.artline_dozenal}₁₂)  "
                f"Sym={entry.symbol}  {entry.class_name}"
            )
        return _wrap_reply("adc12_list", "\n".join(lines), {"major_classes": len(ADC12_MAJOR_CLASSES)})

    tag = args[0]
    if len(args) >= 2:
        quote = " ".join(args[1:])
        idx = ArtlineDuodecimalIndexer()
        rec = idx.highlight(quote, tag)
        reply = (
            f"{rec.four_column_stamp}\n"
            f"  Class : {rec.class_name}\n"
            f"  Quote : “{rec.quote}”\n"
            f"  SHA256: {rec.receipt_sha256[:16]}"
        )
        return _wrap_reply("adc12_highlight", reply, rec.to_dict())

    entry = resolve_adc12(tag)
    reply = (
        f"{entry.four_column_stamp} — {entry.class_name}\n"
        f"  Use : {entry.shorthand_use}\n"
        f"  Chat: {entry.call_badge}"
    )
    return _wrap_reply("adc12_lookup", reply, entry.to_dict())


def _wrap_reply(mode: str, reply: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": ARTLINE_CLI_CONTRACT,
        "mode": mode,
        "gear_used": "gear1",
        "reply": reply,
        "data": data,
        "eliza_trace": {"matched_rule_id": mode, "tokens_used": 0},
        "metacognition": {"a_tau": 1, "tau": 0.08},
        "cymatics": {"dominant_phoneme": "AY", "modes": [1, 4, 2, 6]},
        "epistemic_boundaries": dict(EPISTEMIC_BOUNDARIES),
        "cloud_tokens_used": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zoe-artline",
        description="Zoe Artline 2.0 Brainstorm, Retro Evolution, Optional-Physics & ADC-12 CLI",
    )
    p.add_argument("--out-dir", help="Export output directory (default ~/.zoe/artline)")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    sub = p.add_subparsers(dest="cmd")

    bs = sub.add_parser("brainstorm", help="Export Artline Brainstorming Studio concept plate(s)")
    bs.add_argument("concept", nargs="?", default="desk", choices=["desk", "chess", "sector", "mondo", "all"])

    sub.add_parser("retro", help="Run Clean-Room Gen 1->3 Build->RE->Rebuild evolution loop")
    sub.add_parser("physics", help="Export Optional-Physics Room shatter GIF, rosette plate & HTML")
    sub.add_parser("forge", help="Export ZOETK001 toolboxes, .COL-as-GEM palettes & Forge HTML studio")

    adc = sub.add_parser("adc12", help="Base-12 Duodecimal 4-Column Artline shorthand lookup or highlight")
    adc.add_argument("args", nargs="*", help="Query (e.g. 100, 90, Z, Σ, ✺) or <tag> <quote...>")
    adc.add_argument("--export-plate", action="store_true", help="Also export ADC-12 vector plate & HTML catalog")

    sub.add_parser("studio", help="Show live :8765 Web Studio URLs and quick commands")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(list(argv) if argv is not None else None)
    cmd = ns.cmd or "studio"

    if cmd == "studio":
        res = handle_artline_slash_command("/artline help", out_dir=ns.out_dir)
    elif cmd == "brainstorm":
        res = handle_artline_slash_command(f"/artline {ns.concept}", out_dir=ns.out_dir)
    elif cmd == "retro":
        res = handle_artline_slash_command("/artline retro", out_dir=ns.out_dir)
    elif cmd == "physics":
        res = handle_artline_slash_command("/artline physics", out_dir=ns.out_dir)
    elif cmd == "forge":
        res = handle_artline_slash_command("/artline forge", out_dir=ns.out_dir)
    elif cmd == "adc12":
        raw = " ".join(["/adc12"] + list(ns.args or []))
        res = handle_artline_slash_command(raw, out_dir=ns.out_dir)
        if getattr(ns, "export_plate", False):
            dest = _default_out_dir(ns.out_dir) / "adc12"
            dest.mkdir(parents=True, exist_ok=True)
            doc, _meta = build_adc12_reference_plate()
            for ext in ("svg", "png", "gem"):
                doc.export(dest / f"adc12_plate.{ext}", kind=ext)
            write_interactive_adc12_catalog_html(dest / "adc12_catalog.html")
    else:
        parser.print_help()
        return 1

    if ns.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(res["reply"])
    return 0


__all__ = [
    "ARTLINE_CLI_CONTRACT",
    "EPISTEMIC_BOUNDARIES",
    "build_parser",
    "handle_artline_slash_command",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())

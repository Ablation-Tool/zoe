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
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence

from . import zoe_artline_brainstorm
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
    decode_col_file,
    get_forge_catalog,
    inspect_gem_file,
    typeset_af4_text_svg,
    typeset_af4_text_to_artline_doc,
    write_interactive_artline_forge_html,
)
from .zoe_retro_art_studio import run_build_re_rebuild_cycle
from .zoe_wombats_physics_room import (
    build_artline_rosette_wombats_plate,
    render_physics_shatter_gif,
    write_interactive_physics_room_html,
)

ARTLINE_CLI_CONTRACT = "zoe-artline-cli/v1"

DEFAULT_PIXEL_SERIAL = "2A111FDH200CZY"
DEFAULT_PIXEL_REMOTE_DIR = "/sdcard/Download/zoe-studio"

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
    archive_root: str | Path | None = None,
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
        arch_path = Path(archive_root) if archive_root is not None else None
        html_p = write_interactive_artline_forge_html(dest / "zoe_artline_forge.html", archive_root=arch_path)
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


def sync_studio_assets(
    output_dir: str | Path | None = None,
    push_pixel: bool = False,
    device_serial: str = DEFAULT_PIXEL_SERIAL,
    remote_dir: str = DEFAULT_PIXEL_REMOTE_DIR,
    archive_root: str | Path | None = None,
) -> dict[str, Any]:
    """Refresh all 4 standalone offline HTML studio exports + manifest, with optional adb push."""
    if output_dir is None:
        dest = _default_out_dir(None) / "studio"
    else:
        dest = Path(output_dir).expanduser().resolve()
        if dest.exists() and not dest.is_dir():
            raise ValueError(f"output_dir must be a directory, got file: {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    artline_p = dest / "artline_studio.html"
    artline_writer = getattr(zoe_artline_brainstorm, "write_interactive_artline_studio_html", None)
    if callable(artline_writer):
        artline_p = Path(artline_writer(artline_p))
    else:
        artline_p.write_bytes(zoe_artline_brainstorm.render_artline_studio_html())

    physics_p = Path(write_interactive_physics_room_html(dest / "physics_room.html"))
    adc12_p = Path(write_interactive_adc12_catalog_html(dest / "adc12_catalog.html"))
    arch_path = Path(archive_root) if archive_root is not None else None
    forge_p = Path(write_interactive_artline_forge_html(dest / "zoe_artline_forge.html", archive_root=arch_path))

    html_files = [artline_p, physics_p, adc12_p, forge_p]
    file_records: list[dict[str, Any]] = []
    for p in html_files:
        raw = p.read_bytes()
        file_records.append(
            {
                "name": p.name,
                "path": str(p),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    base_flags: dict[str, Any] = {
        "clean_room_original": True,
        "proprietary_code_copied": 0,
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "cloud_tokens_used": 0,
    }
    manifest_p = dest / "studio_manifest.json"
    manifest_payload = {
        "contract": ARTLINE_CLI_CONTRACT,
        "out_dir": str(dest),
        "files": file_records,
        "constitutional_flags": dict(base_flags),
    }
    manifest_p.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    pixel_pushed = False
    pushed_files: list[str] = []
    error: str | None = None
    external_actions = 0

    if push_pixel:
        adb_bin = shutil.which("adb")
        if not adb_bin:
            error = "adb not found on PATH"
        else:
            try:
                dev_proc = subprocess.run(
                    [adb_bin, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                attached = dev_proc.returncode == 0 and bool(
                    re.search(rf"^{re.escape(device_serial)}\s+device\b", dev_proc.stdout, re.MULTILINE)
                )
                if not attached:
                    error = f"Pixel device {device_serial!r} is not attached"
                else:
                    mk_proc = subprocess.run(
                        [adb_bin, "-s", device_serial, "shell", "mkdir", "-p", remote_dir],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    if mk_proc.returncode != 0:
                        detail = (mk_proc.stderr or mk_proc.stdout).strip() or f"exit {mk_proc.returncode}"
                        error = f"adb mkdir failed on {device_serial}: {detail}"
                    else:
                        remote_base = remote_dir.rstrip("/")
                        for local_p in [*html_files, manifest_p]:
                            remote_target = f"{remote_base}/{local_p.name}"
                            push_proc = subprocess.run(
                                [adb_bin, "-s", device_serial, "push", str(local_p), remote_target],
                                capture_output=True,
                                text=True,
                                timeout=30,
                                check=False,
                            )
                            if push_proc.returncode != 0:
                                detail = (push_proc.stderr or push_proc.stdout).strip() or f"exit {push_proc.returncode}"
                                error = f"adb push failed for {local_p.name}: {detail}"
                                break
                            pushed_files.append(remote_target)
                        external_actions = len(pushed_files)
                        pixel_pushed = error is None and len(pushed_files) == 5
            except (OSError, subprocess.SubprocessError) as exc:
                error = f"adb invocation failed: {exc}"
                pixel_pushed = False
                external_actions = len(pushed_files)

    flags_out = dict(base_flags)
    flags_out["external_actions"] = external_actions

    return {
        "contract": ARTLINE_CLI_CONTRACT,
        "out_dir": str(dest),
        "html_paths": {
            "artline": str(artline_p),
            "physics": str(physics_p),
            "duodecimal": str(adc12_p),
            "forge": str(forge_p),
        },
        "manifest_path": str(manifest_p),
        "files": file_records,
        "html_count": len(html_files),
        "push_pixel_requested": bool(push_pixel),
        "pixel_pushed": pixel_pushed,
        "pushed": pixel_pushed,
        "pushed_files": pushed_files,
        "device_serial": device_serial,
        "remote_dir": remote_dir,
        "error": error,
        "external_actions": external_actions,
        "cloud_tokens_used": 0,
        "constitutional_flags": flags_out,
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
    fg = sub.add_parser("forge", help="Export ZOETK001 toolboxes, .COL-as-GEM palettes & Forge HTML studio")
    fg.add_argument("--text", help="Optional text string to typeset via clean-room .AF4 decoder (.svg + .gem)")
    fg.add_argument("--font", default=None, help="Target .AF4 font name or stem (default advtg_n.af4)")
    fg.add_argument("--inspect-gem", help="Inspect a .GEM metafile and write <stem>.inspect.json")
    fg.add_argument("--inspect-col", help="Decode a .COL palette file and write <stem>.col.json")
    fg.add_argument("--export-summary", action="store_true", help="Write forge_catalog_summary.json")
    fg.add_argument("--archive-root", help="Optional override path for extracted Artline archive")

    adc = sub.add_parser("adc12", help="Base-12 Duodecimal 4-Column Artline shorthand lookup or highlight")
    adc.add_argument("args", nargs="*", help="Query (e.g. 100, 90, Z, Σ, ✺) or <tag> <quote...>")
    adc.add_argument("--export-plate", action="store_true", help="Also export ADC-12 vector plate & HTML catalog")

    sub.add_parser("studio", help="Show live :8765 Web Studio URLs and quick commands")

    sync_p = sub.add_parser("sync-studio", help="Refresh offline Artline/Studio HTML exports & optional Pixel 7 sync")
    sync_p.add_argument(
        "--output-dir",
        dest="sync_output_dir",
        help="Optional override output directory (else --out-dir or ~/.zoe/artline/studio)",
    )
    sync_p.add_argument("--push-pixel", action="store_true", help="Push synced assets via adb to attached Pixel 7")
    sync_p.add_argument("--device-serial", default=DEFAULT_PIXEL_SERIAL, help=f"Target adb serial (default {DEFAULT_PIXEL_SERIAL})")
    sync_p.add_argument("--remote-dir", default=DEFAULT_PIXEL_REMOTE_DIR, help=f"Remote Pixel dir (default {DEFAULT_PIXEL_REMOTE_DIR})")
    sync_p.add_argument("--archive-root", help="Optional override path for extracted Artline archive")
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
        arch_arg = Path(ns.archive_root) if getattr(ns, "archive_root", None) else None
        cat = get_forge_catalog(arch_arg)
        available: dict[str, str] = {}
        for f in cat.get("fonts", []):
            fname = str(f["filename"])
            available[fname.lower()] = fname
            available[str(f["stem"]).lower()] = fname
            dname = str(f.get("display_name", "")).strip().lower()
            if dname and dname not in available:
                available[dname] = fname
        explicit_font = getattr(ns, "font", None)
        if explicit_font is not None:
            font_key = str(explicit_font).strip().lower()
            if not font_key or font_key not in available:
                print(
                    f"Error: unknown .AF4 font {explicit_font!r}. "
                    f"Available: {', '.join(sorted(set(available.values())))}",
                    file=sys.stderr,
                )
                return 2
            resolved_font = available[font_key]
        else:
            resolved_font = available.get("advtg_n.af4") or str(cat["fonts"][0]["filename"])

        res = handle_artline_slash_command("/artline forge", out_dir=ns.out_dir, archive_root=arch_arg)
        dest = _default_out_dir(ns.out_dir) / "forge"
        extra_lines: list[str] = []
        if getattr(ns, "text", None) is not None:
            svg_str = typeset_af4_text_svg(resolved_font, str(ns.text), archive_root=arch_arg)
            svg_p = dest / "typeset.svg"
            svg_p.write_text(svg_str, encoding="utf-8")
            doc = typeset_af4_text_to_artline_doc(resolved_font, str(ns.text), archive_root=arch_arg)
            gem_p = dest / "typeset.gem"
            doc.export(gem_p, kind="gem")
            res["data"]["typeset"] = {
                "font": resolved_font,
                "text": str(ns.text),
                "svg_path": str(svg_p),
                "gem_path": str(gem_p),
            }
            extra_lines.append(f"  Typeset ({resolved_font}): {svg_p} & {gem_p}")
        if getattr(ns, "inspect_gem", None):
            gem_in = Path(ns.inspect_gem)
            gem_rep = inspect_gem_file(gem_in)
            out_json = dest / f"{gem_in.stem}.inspect.json"
            out_json.write_text(json.dumps(gem_rep, indent=2, ensure_ascii=False), encoding="utf-8")
            res["data"]["gem_inspection"] = {"path": str(out_json), "record_count": gem_rep["record_count"], "primitive_counts": gem_rep["primitive_counts"]}
            extra_lines.append(f"  GEM Inspect: {out_json} ({gem_rep['record_count']} records)")
        if getattr(ns, "inspect_col", None):
            col_in = Path(ns.inspect_col)
            col_rep = decode_col_file(col_in).summary_dict()
            out_json = dest / f"{col_in.stem}.col.json"
            out_json.write_text(json.dumps(col_rep, indent=2, ensure_ascii=False), encoding="utf-8")
            res["data"]["col_inspection"] = {"path": str(out_json), "swatch_count": col_rep["swatch_count"]}
            extra_lines.append(f"  COL Decode : {out_json} ({col_rep['swatch_count']} swatches)")
        if getattr(ns, "export_summary", False):
            cat_sum = get_forge_catalog(arch_arg)
            sum_p = dest / "forge_catalog_summary.json"
            sum_p.write_text(json.dumps(cat_sum, indent=2, ensure_ascii=False), encoding="utf-8")
            res["data"]["catalog_summary"] = str(sum_p)
            extra_lines.append(f"  Catalog    : {sum_p} ({cat_sum['font_count']} .AF4 · {cat_sum['syf_total']} .SYF)")
        if extra_lines:
            res["reply"] = res["reply"] + "\n" + "\n".join(extra_lines)
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
    elif cmd == "sync-studio":
        target_out = getattr(ns, "sync_output_dir", None) or ns.out_dir
        sync_res = sync_studio_assets(
            target_out,
            push_pixel=bool(getattr(ns, "push_pixel", False)),
            device_serial=str(getattr(ns, "device_serial", DEFAULT_PIXEL_SERIAL)),
            remote_dir=str(getattr(ns, "remote_dir", DEFAULT_PIXEL_REMOTE_DIR)),
            archive_root=getattr(ns, "archive_root", None),
        )
        reply_lines = [
            (
                f"[500₁₂ · l · ●] Offline Studio Sync Complete "
                f"({sync_res['html_count']} HTMLs -> {sync_res['out_dir']})"
            ),
            f"  Manifest      : {sync_res['manifest_path']}",
            f"  Pixel Pushed  : {sync_res['pixel_pushed']} (external_actions={sync_res['external_actions']})",
        ]
        if sync_res.get("error"):
            reply_lines.append(f"  Note          : {sync_res['error']}")
        res = _wrap_reply("artline_sync_studio", "\n".join(reply_lines), sync_res)
        res["epistemic_boundaries"]["external_actions"] = sync_res["external_actions"]
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
    "DEFAULT_PIXEL_REMOTE_DIR",
    "DEFAULT_PIXEL_SERIAL",
    "EPISTEMIC_BOUNDARIES",
    "build_parser",
    "handle_artline_slash_command",
    "main",
    "sync_studio_assets",
]

if __name__ == "__main__":
    raise SystemExit(main())

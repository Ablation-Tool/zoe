from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from .acceptance import load_plan, run_acceptance, save_acceptance
from .capsule import generate_keypair, sign_capsule, verify_capsule
from .cog import Cog, demo_cog
from .field import _canonical
from .patchbay import (
    BOARDS, demo_artifact, export_patchbay, fetch_catalog, inspect_artifact,
    inspect_source, media_gallery,
)


def parser():
    result = argparse.ArgumentParser(prog="patchbay", description="Zoe Patchbay · firmware, boards, signed updates, and small-cog language play")
    commands = result.add_subparsers(dest="command", required=True)
    scene = commands.add_parser("scene", help="inspect an artifact or open the native board scene")
    scene.add_argument("artifact", nargs="?", help=".hex, .bit, .zip, .bin, .ub, or timing .json")
    scene.add_argument("--source", action="store_true", help="treat the path as a source-tree root")
    scene.add_argument("--board", choices=tuple(BOARDS), default="genesys2")
    scene.add_argument("--output", help="new .svg, .png, or .gem scene instead of opening GTK")
    scene.add_argument("--format", choices=("svg", "png", "gem"))
    scene.add_argument("--width", type=int, default=1400)
    source = commands.add_parser("source", help="inventory an explicit source checkout")
    source.add_argument("root")
    source.add_argument("--output", help="new JSON report")
    catalog = commands.add_parser("catalog", help="read the public UCL firmware catalog without downloading payloads")
    catalog.add_argument("--url", default="https://www.hep.ucl.ac.uk/~warren/upgrade/firmware/")
    catalog.add_argument("--output", required=True, help="new JSON catalog")
    media = commands.add_parser("media", help="build a local-only gallery for the supplied CERN root")
    media.add_argument("--root", required=True)
    media.add_argument("--output", required=True, help="new HTML gallery")
    keygen = commands.add_parser("keygen", help="generate a new Ed25519 keypair")
    keygen.add_argument("private_key")
    keygen.add_argument("public_key")
    sign = commands.add_parser("sign", help="sign a new update capsule without programming a device")
    sign.add_argument("artifact")
    sign.add_argument("--private-key", required=True)
    sign.add_argument("--public-key", required=True)
    sign.add_argument("--target", required=True)
    sign.add_argument("--output", required=True, help="new capsule JSON")
    verify = commands.add_parser("verify", help="verify a capsule, artifact, and optional trusted public key")
    verify.add_argument("capsule")
    verify.add_argument("--artifact")
    verify.add_argument("--trusted-key")
    verify.add_argument("--output", help="new verification report JSON")
    accept = commands.add_parser("accept", help="validate or explicitly execute an acceptance plan")
    accept.add_argument("plan")
    accept.add_argument("--execute", action="store_true", help="execute the declared argv steps")
    accept.add_argument("--allow-hardware-write", action="store_true", help="authorize steps explicitly marked hardware_write=true")
    accept.add_argument("--output", help="new acceptance result JSON")
    cog = commands.add_parser("cog", help="train or load a small two-way token processor")
    cog.add_argument("inputs", nargs="*", help="up to 16 explicit local text/HTML/HDL/source files")
    cog.add_argument("--model", help="load a previously saved Cog JSON model")
    cog.add_argument("--model-output", help="save the newly trained Cog model without overwriting")
    cog.add_argument("--prompt", default="inspect")
    cog.add_argument("--reverse", default="update", help="initial token or text for the backward walk")
    cog.add_argument("--steps", type=int, default=6)
    cog.add_argument("--tau", type=float, default=0.05)
    cog.add_argument("--output", help="new forward/backward report JSON")
    return result


def launch_patchbay(report, board):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Patchbay requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("patchbay", patchbay_report=report)
    if board != "genesys2":
        window.controls["patchbay_board"].set_active_id(board)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def _save_json(document, path):
    path = Path(path)
    document = {key: value for key, value in document.items() if key != "digest"}
    document["digest"] = hashlib.sha256(_canonical(document).encode("utf-8")).hexdigest()
    with path.open("x", encoding="utf-8") as stream:
        stream.write(_canonical(document) + "\n")
    return path


def _print(document):
    print(json.dumps(document, ensure_ascii=False, sort_keys=True))


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "scene":
            report = inspect_source(arguments.artifact) if arguments.source else inspect_artifact(arguments.artifact) if arguments.artifact else demo_artifact()
            if arguments.output:
                output = export_patchbay(arguments.output, report, arguments.board, arguments.format, arguments.width)
                _print({"instrument": "zoe-patchbay", "output": str(output), "bytes": output.stat().st_size, "artifact": report, "hardware_accessed": False})
                return 0
            launch_patchbay(report, arguments.board)
            return 0
        if arguments.command == "source":
            report = inspect_source(arguments.root)
            if arguments.output:
                _save_json(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "catalog":
            document = fetch_catalog(arguments.url)
            _save_json(document, arguments.output)
            _print({"output": arguments.output, "entries": len(document["entries"]), "latest_aliases": sum(row["latest_alias"] for row in document["entries"]), "publisher_signature_verified": False})
            return 0
        if arguments.command == "media":
            output, report = media_gallery(arguments.root, arguments.output)
            _print({"output": str(output), **report})
            return 0
        if arguments.command == "keygen":
            private, public, fingerprint = generate_keypair(arguments.private_key, arguments.public_key)
            _print({"private_key": str(private), "public_key": str(public), "public_key_sha256": fingerprint, "private_key_printed": False})
            return 0
        if arguments.command == "sign":
            output, report = sign_capsule(arguments.artifact, arguments.private_key, arguments.public_key, arguments.target, arguments.output)
            _print({"output": str(output), **report})
            return 0
        if arguments.command == "verify":
            report = verify_capsule(arguments.capsule, arguments.artifact, arguments.trusted_key)
            if arguments.output:
                _save_json(report, arguments.output)
            _print(report)
            return 0 if report["signature_valid"] and report["artifact_match"] is not False and report["trusted_key_match"] is not False else 1
        if arguments.command == "accept":
            report = run_acceptance(arguments.plan, arguments.execute, arguments.allow_hardware_write)
            if arguments.output:
                save_acceptance(report, arguments.output)
            _print(report)
            return 0 if report["accepted"] is not False else 1
        if arguments.command == "cog":
            if arguments.model and arguments.inputs:
                raise ValueError("choose Cog training inputs or --model, not both")
            model = Cog.load(arguments.model) if arguments.model else Cog.from_paths(arguments.inputs) if arguments.inputs else demo_cog()
            if arguments.model_output:
                model.save(arguments.model_output)
            report = {
                "instrument": "zoe-cog",
                "model_type": "bounded_interpolated_bigram",
                "vocabulary_size": len(model.vocabulary),
                "total_tokens": model.total_tokens,
                "source_documents": model.documents,
                "forward": model.walk(arguments.prompt, arguments.steps, tau=arguments.tau),
                "backward": model.walk(arguments.reverse, arguments.steps, reverse=True, tau=arguments.tau),
                "accessible_volume_credit": "Nicholas Michael Kloster alone, March 6, 2026",
                "command_authorized": False,
            }
            if arguments.output:
                _save_json(report, arguments.output)
            _print(report)
            return 0
        return 2
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"patchbay: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

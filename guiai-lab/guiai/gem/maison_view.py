from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from .field import _canonical
from .maison import ASSOCIATIONS, export_maison, inspect_reference, maison_review
from .practice import PracticeLog, demo_log


def parser():
    result = argparse.ArgumentParser(prog="maison", description="Zoe Maison · executive clarity, luxury restraint, enterprise evidence")
    commands = result.add_subparsers(dest="command", required=True)
    scene = commands.add_parser("scene", help="open the Maison studio or export its current association card")
    scene.add_argument("--input", help="existing practice log JSON")
    scene.add_argument("--word", default="stewardship", choices=tuple(ASSOCIATIONS))
    scene.add_argument("--reference", help="explicit association reference PDF")
    scene.add_argument("--output", help="new .svg, .png, or .gem card instead of opening GTK")
    scene.add_argument("--format", choices=("svg", "png", "gem"))
    scene.add_argument("--width", type=int, default=1400)
    deck = commands.add_parser("deck", help="list the curated association prompts without reading a document")
    deck.add_argument("--output", help="new deck JSON")
    reference = commands.add_parser("reference", help="hash and inspect an explicit association PDF")
    reference.add_argument("path")
    reference.add_argument("--output", help="new reference report JSON")
    return result


def launch_maison(log, word, reference):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Maison requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("maison", leadership_log=log, maison_word=word, maison_reference=reference)
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
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] not in {"scene", "deck", "reference"}:
        raw.insert(0, "scene")
    arguments = parser().parse_args(raw)
    try:
        if arguments.command == "deck":
            report = {"instrument": "zoe-maison-deck", "associations": ASSOCIATIONS, "count": len(ASSOCIATIONS), "score": None, "autonomous_action": False}
            if arguments.output:
                _save_json(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "reference":
            report = inspect_reference(arguments.path)
            if arguments.output:
                _save_json(report, arguments.output)
            _print(report)
            return 0
        log = PracticeLog.load(arguments.input) if arguments.input else demo_log()
        reference = inspect_reference(arguments.reference) if arguments.reference else None
        if arguments.output:
            output = export_maison(arguments.output, log, arguments.word, reference, arguments.format, arguments.width)
            _print({"instrument": "zoe-maison", "output": str(output), "bytes": output.stat().st_size, **maison_review(log, arguments.word, reference)})
            return 0
        launch_maison(log, arguments.word, reference)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"maison: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

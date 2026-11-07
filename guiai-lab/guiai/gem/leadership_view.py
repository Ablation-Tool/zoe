from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from .field import _canonical
from .leadership import export_leadership, inspect_library, search_library
from .practice import PracticeLog, demo_log


def parser():
    result = argparse.ArgumentParser(prog="leadership", description="Zoe Leadership Garden · practice, advice, failure, learning, adaptation")
    commands = result.add_subparsers(dest="command", required=True)
    scene = commands.add_parser("scene", help="open the practice garden or export its current scene")
    scene.add_argument("--input", help="existing practice log JSON")
    scene.add_argument("--library-root", help="explicit reference document directory")
    scene.add_argument("--output", help="new .svg, .png, or .gem scene instead of opening GTK")
    scene.add_argument("--format", choices=("svg", "png", "gem"))
    scene.add_argument("--width", type=int, default=1400)
    practice = commands.add_parser("practice", help="record an actual attempt and a small next experiment")
    practice.add_argument("--input", help="existing log to extend; omit to start a new log")
    practice.add_argument("--situation", required=True)
    practice.add_argument("--action", required=True, help="what you actually did")
    practice.add_argument("--outcome", required=True, help="what happened, not what you hoped")
    practice.add_argument("--next-try", required=True, help="one small different next attempt")
    practice.add_argument("--frame", default="ordinary,practice", help="up to six comma-separated situation labels")
    practice.add_argument("--mistake", default="")
    practice.add_argument("--advice", default="")
    practice.add_argument("--learning", default="")
    practice.add_argument("--support", default="")
    practice.add_argument("--unknown", default="")
    practice.add_argument("--stop-condition", default="")
    practice.add_argument("--timestamp")
    practice.add_argument("--output", required=True, help="new practice log JSON; never overwrites")
    correct = commands.add_parser("correct", help="append a new lesson without rewriting an earlier attempt")
    correct.add_argument("--input", required=True)
    correct.add_argument("--sequence", type=int, required=True)
    correct.add_argument("--learning", required=True)
    correct.add_argument("--timestamp")
    correct.add_argument("--output", required=True)
    library = commands.add_parser("library", help="inspect an explicit reference folder without treating books as practice")
    library.add_argument("--root", required=True)
    library.add_argument("--output", required=True, help="new library report JSON")
    search = commands.add_parser("search", help="find actual extracted text snippets in the reference PDFs")
    search.add_argument("--root", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=12)
    search.add_argument("--output", required=True, help="new snippet report JSON")
    return result


def launch_leadership(log, library):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Leadership Garden requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("leadership", leadership_log=log, leadership_library=library)
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
            log = PracticeLog.load(arguments.input) if arguments.input else demo_log()
            library = inspect_library(arguments.library_root) if arguments.library_root else None
            if arguments.output:
                output = export_leadership(arguments.output, log, library, arguments.format, arguments.width)
                _print({"instrument": "zoe-leadership-garden", "output": str(output), "bytes": output.stat().st_size, **log.review(), "autonomous_action": False})
                return 0
            launch_leadership(log, library)
            return 0
        if arguments.command == "practice":
            log = PracticeLog.load(arguments.input) if arguments.input else PracticeLog()
            event = log.add_practice(
                arguments.situation, arguments.action, arguments.outcome, arguments.next_try,
                frame=arguments.frame, mistake=arguments.mistake, advice=arguments.advice,
                learning=arguments.learning, support=arguments.support, unknown=arguments.unknown,
                stop_condition=arguments.stop_condition, timestamp=arguments.timestamp,
            )
            log.save(arguments.output)
            _print({"output": arguments.output, "recorded_sequence": event["sequence"], **log.review()})
            return 0
        if arguments.command == "correct":
            log = PracticeLog.load(arguments.input)
            event = log.add_correction(arguments.sequence, arguments.learning, arguments.timestamp)
            log.save(arguments.output)
            _print({"output": arguments.output, "correction_sequence": event["sequence"], **log.review()})
            return 0
        if arguments.command == "library":
            report = inspect_library(arguments.root)
            _save_json(report, arguments.output)
            _print({"output": arguments.output, "documents": len(report["documents"]), "external_reading": len(report["external_reading"]), "books_replace_practice": False})
            return 0
        if arguments.command == "search":
            report = search_library(arguments.root, arguments.query, arguments.limit)
            _save_json(report, arguments.output)
            _print(report)
            return 0
        return 2
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"leadership: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

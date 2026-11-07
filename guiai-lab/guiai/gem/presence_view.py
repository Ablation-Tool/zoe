from __future__ import annotations

import argparse
import json
import os

from .presence import PresenceField, demo_presence, export_presence, presence_scene
from .resilience import SECTORS, demo_traces


def parser():
    result = argparse.ArgumentParser(prog="presence", description="Zoe Presence · an explicit self-model, not a consciousness claim")
    result.add_argument("input", nargs="?", help="saved Presence JSON to verify and open")
    result.add_argument("--sector", choices=tuple(SECTORS), default="energy")
    result.add_argument("--trace", choices=tuple(demo_traces()), default="host80")
    result.add_argument("--observe", help="append a sourced observation to the current self-model")
    result.add_argument("--reflect", help="append an explicit reflection")
    result.add_argument("--correct", help="append a user correction without erasing prior events")
    result.add_argument("--review", action="store_true", help="record review-required status without executing anything")
    result.add_argument("--output", help="write a new .json, .svg, .png, or .gem artifact instead of opening the native atlas")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def launch_presence(field):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Presence requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("presence", presence=field)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        field = PresenceField.load(arguments.input) if arguments.input else demo_presence()
        if arguments.sector != "energy" or arguments.trace != "host80":
            field.focus(arguments.sector, arguments.trace, "explicit command-line selection")
        if arguments.observe:
            field.observe(arguments.observe, "explicit command-line observation")
        if arguments.reflect:
            field.reflect(arguments.reflect)
        if arguments.correct:
            field.correct(arguments.correct)
        if arguments.review:
            field.review()
        if arguments.output:
            kind = arguments.format or os.path.splitext(arguments.output)[1].lower().lstrip(".")
            output = field.save(arguments.output) if kind == "json" else export_presence(field, arguments.output, kind, arguments.width)
            print(json.dumps({"instrument": "zoe-presence", "output": str(output), "bytes": output.stat().st_size, **field.report()}, ensure_ascii=False, sort_keys=True))
            return 0
        launch_presence(field)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"presence: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

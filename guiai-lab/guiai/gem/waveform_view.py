from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .waveform import WaveformReplay, demo_replay, export_waveform, waveform_scene


def parser():
    result = argparse.ArgumentParser(prog="waveform", description="Zoe Waveform Replay · bounded signal evidence")
    result.add_argument("input", nargs="?", help="input .vcd, legacy .jsonl, .wdb, or normalized replay .json")
    result.add_argument("--signal", help="declared signal ID to highlight")
    result.add_argument("--max-events", type=int, default=4096, help="retained event bound, 1-65536")
    result.add_argument("--output", help="write a new .json, .svg, .png, or .gem artifact instead of opening the native atlas")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def launch_waveform(replay):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Waveform Replay requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("waveform", waveform=replay)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        replay = WaveformReplay.load(arguments.input, max_events=arguments.max_events) if arguments.input else demo_replay(arguments.max_events)
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            output = replay.save(arguments.output) if kind == "json" else export_waveform(replay, arguments.output, kind, arguments.width, arguments.signal)
            print(json.dumps({"instrument": "zoe-waveform-replay", "output": str(output), "bytes": output.stat().st_size, **replay.analyze()}, ensure_ascii=False, sort_keys=True))
            return 0
        launch_waveform(replay)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"waveform: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

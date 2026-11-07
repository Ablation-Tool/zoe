from __future__ import annotations

import argparse
import json
import os

from .pilot import GUIDE_PAGES, cover_document, export_guide_page, write_guide_pdf


def parser():
    result = argparse.ArgumentParser(prog="pilot", description="Zoe Practice Navigator · original five-page visual guide")
    result.add_argument("--page", choices=GUIDE_PAGES, default="cover", help="page for SVG, PNG, or GEM export; PDF always includes all five")
    result.add_argument("--output", help="write a new .pdf, .svg, .png, or .gem artifact instead of opening the editor")
    result.add_argument("--format", choices=("pdf", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400, help="SVG/PNG width in pixels")
    return result


def launch_pilot():
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Practice Navigator requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .artline_view import ArtlineWindow
    window = ArtlineWindow(cover_document())
    window.set_title("Zoe Practice Navigator · editable original guide cover")
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.output:
            kind = arguments.format or os.path.splitext(arguments.output)[1].lower().lstrip(".")
            output = write_guide_pdf(arguments.output) if kind == "pdf" else export_guide_page(arguments.output, arguments.page, kind, arguments.width)
            print(json.dumps({"instrument": "zoe-practice-navigator", "page": "all five" if kind == "pdf" else arguments.page, "output": str(output), "bytes": output.stat().st_size, "certified_flight_material": False}, sort_keys=True))
            return 0
        launch_pilot()
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"pilot: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

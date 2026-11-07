from __future__ import annotations

import argparse
import json
import os

from .resilience import SECTORS, demo_traces, export_resilience, resilience_scene


def parser():
    result = argparse.ArgumentParser(prog="resilience", description="Zoe Resilience Atlas · essential services and signal evidence")
    result.add_argument("--sector", choices=tuple(SECTORS), default="energy", help="sector whose example dependencies are highlighted")
    result.add_argument("--trace", choices=tuple(demo_traces()), default="host80", help="synthetic trace to highlight")
    result.add_argument("--output", help="write a new .svg, .png, or .gem artifact instead of opening the native atlas")
    result.add_argument("--format", choices=("svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400, help="SVG/PNG width in pixels")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.output:
            output = export_resilience(arguments.output, arguments.sector, arguments.trace, arguments.format, arguments.width)
            _scene, report = resilience_scene(arguments.sector, arguments.trace)
            print(json.dumps({"instrument": "zoe-resilience", "output": str(output), "bytes": output.stat().st_size, **report}, ensure_ascii=False, sort_keys=True))
            return 0
        from .atlas_view import launch_atlas
        launch_atlas("resilience")
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"resilience: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

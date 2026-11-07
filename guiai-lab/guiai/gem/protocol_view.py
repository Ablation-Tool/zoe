from __future__ import annotations

import argparse
import json
import os

from .protocol_lab import export_protocol, protocol_scene


def parser():
    result = argparse.ArgumentParser(prog="protocol", description="Zoe Protocol Lab · SPECS and AMAC evidence")
    result.add_argument("--count", type=lambda value: int(value, 0), default=0x80, help="SPECS read count from 0 to 255, decimal or 0x-prefixed")
    result.add_argument("--output", help="write a new .svg, .png, or .gem artifact instead of opening the native atlas")
    result.add_argument("--format", choices=("svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.output:
            output = export_protocol(arguments.output, arguments.count, arguments.format, arguments.width)
            _scene, report = protocol_scene(arguments.count)
            print(json.dumps({"instrument": "zoe-protocol-lab", "output": str(output), "bytes": output.stat().st_size, **report}, ensure_ascii=False, sort_keys=True))
            return 0
        from .atlas_view import launch_atlas
        launch_atlas("protocol")
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"protocol: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

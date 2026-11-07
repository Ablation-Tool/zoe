from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .zoe_workbench import WorkbenchProcess


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="zoe-workbench", description="Zoe CERN, HELIOS, and Atelier process bridge")
    result.add_argument("operation", choices=("start", "open", "health", "stop", "verify", "manifest"), nargs="?", default="start")
    result.add_argument("target", nargs="?", default="console", help="console, helios, or atelier for open; output path for manifest")
    result.add_argument("--checkout", help="CERN console checkout; default: ZOE_CERN_CONSOLE or the GEM workbench")
    result.add_argument("--state-file", help="Zoe-owned process metadata path")
    result.add_argument("--port", type=int, default=8765, help="preferred existing console port")
    result.add_argument("--live", action="store_true", help="include isolated XTEST and DR-DOS integration tests")
    return result


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        workbench = WorkbenchProcess(arguments.checkout, arguments.state_file, arguments.port)
        if arguments.operation == "start":
            report = workbench.start()
        elif arguments.operation == "open":
            report = workbench.open(arguments.target)
        elif arguments.operation == "health":
            report = workbench.start()
        elif arguments.operation == "stop":
            report = workbench.stop()
        elif arguments.operation == "verify":
            report = workbench.verify(arguments.live)
            if not report["passed"]:
                print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
                return 1
        else:
            if arguments.target == "console":
                raise ValueError("manifest requires a new .json output path")
            report = {"output": str(workbench.write_manifest(arguments.target))}
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"zoe-workbench: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
COMPONENT_SRC = ROOT / "components" / "Zoe-Autonomy" / "src"


def configure_autonomy():
    if not (COMPONENT_SRC / "zoe_autonomy" / "experiment.py").is_file():
        raise ValueError(f"Zoe-Autonomy component is unavailable: {COMPONENT_SRC}")
    os.environ.setdefault("ZOE_ROOT", str(ROOT))
    if str(COMPONENT_SRC) not in sys.path:
        sys.path.insert(0, str(COMPONENT_SRC))
    return ROOT


def main(argv=None):
    configure_autonomy()
    from zoe_autonomy.cli import main as autonomy_main

    arguments = list(sys.argv[1:] if argv is None else argv)
    return autonomy_main(arguments or ["run"])


if __name__ == "__main__":
    raise SystemExit(main())

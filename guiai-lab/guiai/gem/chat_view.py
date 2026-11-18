from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys

from .autonomy_view import configure_autonomy


def parser():
    result = argparse.ArgumentParser(prog="zoe chat", description="Run Zoe inside Ablation's existing GEM workbench")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    result.add_argument("--state", help="persistent chat state directory; default: ZOE_CHAT_STATE or ~/.zoe/chat")
    result.add_argument("--session", help="existing or new GEM Lab session; default: gem-lab inside the chat state")
    result.add_argument("--target", help="research target directory; default: the unified Zoe checkout")
    result.add_argument("--cli", action="store_true", help="run directly in the current terminal instead of Ablation GEM")
    result.add_argument("--command", help="process one chat command or question, then exit")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    configured_root = configure_autonomy()
    zoe_root = Path(arguments.zoe_root or os.environ.get("ZOE_ROOT", configured_root)).expanduser().resolve()
    state = Path(arguments.state or os.environ.get("ZOE_CHAT_STATE", Path.home() / ".zoe" / "chat")).expanduser().resolve()
    if arguments.cli or arguments.command:
        from zoe_autonomy.chat import main as chat_main
        forwarded = ["--zoe-root", str(zoe_root), "--state", str(state)]
        if arguments.command:
            forwarded.extend(["--command", arguments.command])
        return chat_main(forwarded)

    gem_root = zoe_root / "components" / "ablation" / "gem-lab"
    if not (gem_root / "gem" / "gtk_app.py").is_file():
        raise ValueError(f"Ablation GEM is unavailable: {gem_root}")
    for source in (gem_root, zoe_root / "components" / "Zoe-Autonomy" / "src", zoe_root / "guiai-lab"):
        value = str(source)
        if value not in sys.path:
            sys.path.insert(0, value)
        python_path = os.environ.get("PYTHONPATH", "").split(os.pathsep)
        if value not in python_path:
            os.environ["PYTHONPATH"] = value + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    os.environ["ZOE_ROOT"] = str(zoe_root)
    command = shlex.join([
        sys.executable, "-m", "zoe_autonomy.chat",
        "--zoe-root", str(zoe_root), "--state", str(state),
    ])
    from gem.lab_cli import main as gem_main
    return gem_main([
        "desktop", str(Path(arguments.target).expanduser().resolve() if arguments.target else zoe_root),
        "--session", str(Path(arguments.session).expanduser().resolve() if arguments.session else state / "gem-lab"),
        "--toolkit", "gtk", "--agent-command", command,
    ])


if __name__ == "__main__":
    raise SystemExit(main())

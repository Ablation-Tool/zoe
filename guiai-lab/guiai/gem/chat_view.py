from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys

from .autonomy_view import configure_autonomy


def parser():
    result = argparse.ArgumentParser(prog="zoe chat", description="Lume 1.0 — Zoe interactive CLI")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    result.add_argument("--state", help="persistent chat state directory; default: ZOE_CHAT_STATE or ~/.zoe/chat")
    result.add_argument("--session", help="GEM Lab session path (only used with --gui)")
    result.add_argument("--target", help="research target directory (only used with --gui)")
    result.add_argument("--cli", action="store_true", help="run in the terminal CLI (default)")
    result.add_argument("--gui", action="store_true", help="opt in to launching the legacy GEM desktop workbench")
    result.add_argument("--command", help="process one chat command or question, then exit")
    return result


def _discover_nina(zoe_root: Path) -> None:
    if os.environ.get("NINA_ROOT"):
        return
    for candidate in (zoe_root.parent / "nina", Path.home() / "_projects" / "nina"):
        if (candidate / "audio_fx.py").is_file():
            os.environ["NINA_ROOT"] = str(candidate.resolve())
            break


def _configure_runtime_paths(zoe_root: Path, gem_root: Path | None = None) -> None:
    sources = [zoe_root / "guiai-lab", zoe_root / "components" / "Zoe-Autonomy" / "src"]
    if gem_root is not None:
        sources.append(gem_root)
    for source in sources:
        value = str(source)
        if value in sys.path:
            sys.path.remove(value)
        sys.path.insert(0, value)
        python_path = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p != value]
        os.environ["PYTHONPATH"] = os.pathsep.join([value, *python_path])
    os.environ["ZOE_ROOT"] = str(zoe_root)
    _discover_nina(zoe_root)


def main(argv=None):
    arguments = parser().parse_args(argv)
    configured_root = configure_autonomy()
    zoe_root = Path(arguments.zoe_root or os.environ.get("ZOE_ROOT", configured_root)).expanduser().resolve()
    state = Path(arguments.state or os.environ.get("ZOE_CHAT_STATE", Path.home() / ".zoe" / "chat")).expanduser().resolve()
    _configure_runtime_paths(zoe_root)

    if arguments.command:
        from zoe_autonomy.chat import main as chat_main
        return chat_main(["--zoe-root", str(zoe_root), "--state", str(state), "--command", arguments.command])

    if not arguments.gui:
        from .lume_cli import run_lume_cli
        return run_lume_cli(zoe_root, state)

    gem_root = zoe_root / "components" / "ablation" / "gem-lab"
    if not (gem_root / "gem" / "gtk_app.py").is_file():
        raise ValueError(f"Ablation GEM is unavailable: {gem_root}")
    _configure_runtime_paths(zoe_root, gem_root=gem_root)
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

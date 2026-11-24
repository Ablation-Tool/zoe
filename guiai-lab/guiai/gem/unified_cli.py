from __future__ import annotations

import argparse
from importlib import import_module
import json
import sys

from .cli import R3_COMMAND_SPECS, dispatch_r3_cli, register_r3_subparsers
from .unified import ComponentRegistry, IDENTITY


# Unified view subcommands forwarded directly to `guiai.gem.<name>_view`.
_VIEW_DESCRIPTIONS: dict[str, str] = {
    "artline": "open the original Zoe vector workbench",
    "pentomino": "open the timed spatial practice laboratory",
    "pentacube": "open the pentomino cube permutation laboratory",
    "cicada": "open the CERN and cicada-inspired internal clock",
    "life": "open Conway's Game of Life",
    "pilot": "open the original Practice Navigator guide",
    "resilience": "open the Resilience Atlas",
    "chat": "talk with Zoe through evidence, memory, autonomy, and metacognition",
    "clara": "talk with Zoe & Clara (equal L1-L5 peers balanced by Theorem 15)",
    "eliza": "talk with Zoe-ELIZA x GEM zero-token glass-box atelier (CLI + Web UI + Native Voice)",
    "pala": "run PALA file carving and data recovery",
    "autonomy": "run Zoe's full self-governing autonomy loop",
    "presence": "open the Presence self-model",
    "protocol": "open the SPECS and AMAC Protocol Lab",
    "waveform": "open bounded waveform replay",
    "patchbay": "open firmware, boards, and the small-cog workbench",
    "leadership": "open the adaptive Leadership Garden",
    "maison": "open the executive luxury enterprise studio",
    "evidence": "open the source-first evidence navigator",
    "voice": "speak, sing, and inspect Zoe's 44-phoneme native voice & cymatics",
}


def parser():
    """Build the top-level `Zoe` unified CLI parser (with friendly `zoe` alias)."""
    result = argparse.ArgumentParser(prog="Zoe", description=IDENTITY)
    commands = result.add_subparsers(dest="command")
    for name in ("list", "components"):
        commands.add_parser(name, help="list every registered engine and GEM source")
    launch = commands.add_parser("launch", help="launch an explicit engine or GEM command")
    launch.add_argument("--detach", action="store_true", help="start the component without waiting for it")
    launch.add_argument("component", help="component identifier from `zoe list`")
    launch.add_argument("arguments", nargs=argparse.REMAINDER, help="component arguments after `--`")
    manifest = commands.add_parser("manifest", help="write a no-overwrite unified component manifest")
    manifest.add_argument("--output", required=True, help="new JSON manifest path")
    knowledge = commands.add_parser("knowledge", help="save the unified source and trust-context graph")
    knowledge.add_argument("--output", required=True, help="new JSON knowledge-memory path")
    show = commands.add_parser("show", help="inspect a component without launching a process")
    show.add_argument("component", help="component identifier from `zoe list`")
    os_command = commands.add_parser("os", help="open one ZOE and one GEM desktop")
    os_command.add_argument("arguments", nargs=argparse.REMAINDER)
    gem_command = commands.add_parser("gem", help="use the shared GEM operating environment")
    gem_command.add_argument("arguments", nargs=argparse.REMAINDER, help="status, list, open ID, export ID PATH, or snapshot PATH")
    # Register all 19 view launchers and the 7 R3 theorem/observatory subcommands.
    for name, description in _VIEW_DESCRIPTIONS.items():
        command = commands.add_parser(name, help=description)
        command.add_argument("arguments", nargs=argparse.REMAINDER, help=f"arguments forwarded to Zoe {name}")
    register_r3_subparsers(commands)
    return result


def _try_early_passthrough(raw_arguments: list[str]) -> int | None:
    """Bypass argparse for `zoe os` and direct view module invocations."""
    if not raw_arguments:
        return None
    head = raw_arguments[0]
    if head == "os":
        if len(raw_arguments) == 1:
            from .chat_view import main as chat_main
            return chat_main([])
        from .desktop_view import main as desktop_main
        return desktop_main(raw_arguments[1:])
    if head in _VIEW_DESCRIPTIONS:
        return import_module(f".{head}_view", __package__).main(raw_arguments[1:])
    return None


def _handle_os(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Launch the unified ZOE/GEM desktop shell."""
    from .desktop_view import main as desktop_main
    return desktop_main(arguments.arguments)


def _handle_gem(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Forward `zoe gem` subcommands to the GEM operating environment."""
    from .operating_environment import main as gem_main
    return gem_main(arguments.arguments)


def _handle_view(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Forward parsed view subcommand arguments to its view module."""
    return import_module(f".{arguments.command}_view", __package__).main(arguments.arguments)


def _handle_list(_arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Print every registered engine row from ComponentRegistry."""
    for component in registry.manifest()["components"]:
        source = component["source"]
        status = "present" if source["source_present"] else "missing"
        print(f"{component['identifier']:10} {status:8} {source['mode']:9} {component['summary']}")
    return 0


def _handle_manifest(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Write a no-overwrite unified component manifest JSON."""
    output = registry.write_manifest(arguments.output)
    print(json.dumps({"identity": IDENTITY, "output": str(output), "bytes": output.stat().st_size}, indent=2, sort_keys=True))
    return 0


def _handle_knowledge(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Write the unified source and trust-context knowledge graph."""
    output = registry.knowledge.save(arguments.output)
    print(json.dumps({"identity": IDENTITY, "output": str(output), "bytes": output.stat().st_size, "events": len(registry.knowledge.events)}, indent=2, sort_keys=True))
    return 0


def _handle_show(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Print JSON details for a single registered component."""
    registry.component(arguments.component)
    row = next(item for item in registry.manifest()["components"] if item["identifier"] == arguments.component)
    print(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_launch(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Launch a registered engine or detached subprocess component."""
    forwarded = list(arguments.arguments)
    if forwarded and forwarded[0] == "--":
        forwarded.pop(0)
    result = registry.launch(arguments.component, forwarded or None, detach=arguments.detach)
    if arguments.detach:
        print(json.dumps({"component": arguments.component, "pid": result.pid, "started": True, "readiness_verified": False}, indent=2, sort_keys=True))
        return 0
    return result.returncode


def _handle_r3(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Dispatch any R3 theorem/observatory command via shared gem.cli runner."""
    return dispatch_r3_cli(arguments)


# Declarative dispatch table for parsed `zoe` subcommands.
_COMMAND_HANDLERS = {
    "os": _handle_os,
    "gem": _handle_gem,
    "list": _handle_list,
    "components": _handle_list,
    "manifest": _handle_manifest,
    "knowledge": _handle_knowledge,
    "show": _handle_show,
    "launch": _handle_launch,
    **{name: _handle_view for name in _VIEW_DESCRIPTIONS},
    **{name: _handle_r3 for name in R3_COMMAND_SPECS},
}


def main(argv=None):
    """CLI entrypoint for `zoe`."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    # Forward raw view/os commands before argparse interprets view-specific flags.
    passthrough = _try_early_passthrough(raw_arguments)
    if passthrough is not None:
        return passthrough
    arguments = parser().parse_args(raw_arguments)
    registry = ComponentRegistry()
    try:
        handler = _COMMAND_HANDLERS.get(arguments.command)
        if handler is not None:
            return handler(arguments, registry)
        # Bare `zoe` (no subcommand) opens the interactive chat view.
        from .chat_view import main as chat_main
        return chat_main([])
    except (OSError, RuntimeError, ValueError) as error:
        print(f"zoe: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

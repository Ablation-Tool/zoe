from __future__ import annotations

import argparse
from importlib import import_module
import json
from pathlib import Path
import sys
from typing import Any

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
    "reasoning": "run Zoe x Antigravity Shared-Reasoning Architectures (1-9 + Digital Research GEM)",
    "gemos": "inspect and verify Zoe-GEM OS, Pixel 7 Panther, Braille Studio, ViewMAX themes, and Zoeverse",
}


def _add_workbench_subparser(commands: Any) -> None:
    """Register the `workbench` and `sister` subparsers on the unified CLI."""
    wb = commands.add_parser("workbench", help="run the 9-sister collaborative GEM workbench")
    wb.add_argument("action", nargs="?", default="status", choices=("status", "tick", "hex", "eddbms", "ablation", "export"))
    wb.add_argument("--ticks", type=int, default=1, help="number of collaboration ticks")
    wb.add_argument("--target", help="optional target path for read-only ablation")
    wb.add_argument("--output", help="optional output path for GEM/SVG export")
    wb.add_argument("--format", choices=("gem", "svg"), default="gem")
    wb.add_argument("--json", action="store_true", help="emit JSON output")

    sis = commands.add_parser("sister", help="inspect 9-sister hex mesh, EDDBMS, and read-only ablation")
    sis.add_argument("action", nargs="?", default="list", choices=("list", "hex", "eddbms", "ablation"))
    sis.add_argument("--target", help="optional target path for read-only ablation")
    sis.add_argument("--json", action="store_true", help="emit JSON output")


def parser() -> argparse.ArgumentParser:
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
    gem_command.add_argument("arguments", nargs=argparse.REMAINDER, help="status, list, open ID, export ID PATH, snapshot PATH, or workbench")
    _add_workbench_subparser(commands)
    from .presentation.cli_present import register_present_subparser
    register_present_subparser(commands)
    # Register all view launchers and the 7 R3 theorem/observatory subcommands.
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
            return int(chat_main([]))  # type: ignore[no-untyped-call]
        from .desktop_view import main as desktop_main
        return int(desktop_main(raw_arguments[1:]))  # type: ignore[no-untyped-call]
    if head in _VIEW_DESCRIPTIONS:
        return int(import_module(f".{head}_view", __package__).main(raw_arguments[1:]))
    return None


def _handle_os(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Launch the unified ZOE/GEM desktop shell."""
    from .desktop_view import main as desktop_main
    return int(desktop_main(arguments.arguments))  # type: ignore[no-untyped-call]


def _emit_workbench_payload(payload: dict[str, Any], as_json: bool) -> int:
    """Print workbench payload as compact JSON or structured summary line."""
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"Zoe GEM Workbench: design={payload.get('design_id')} · rev={payload.get('eddms_revision')} · "
            f"windows={payload.get('window_count')}/{payload.get('max_aes_app_windows', 7)} · "
            f"advisory_only=True · external_actions=0 · tokens_used=0"
        )
    return 0


def _run_workbench_action(
    action: str,
    *,
    ticks: int = 1,
    target: str | None = None,
    output: str | None = None,
    fmt: str = "gem",
    as_json: bool = False,
) -> int:
    """Execute a bounded offline workbench action without altering ComponentRegistry."""
    from .zoe_gem_workbench import create_workbench

    wb = create_workbench()
    if action == "tick":
        wb.tick_collaboration(ticks=ticks)
    elif action == "ablation":
        if target is not None:
            if not target.strip():
                raise ValueError("target_path must be a non-empty path")
            wb.run_ablation_inspection(target_path=Path(target).expanduser())
        else:
            wb.run_ablation_inspection(raw_bytes=b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56, target_name="cli_probe.elf")
    elif action == "export":
        if output is None:
            raise ValueError("workbench export requires --output PATH")
        if fmt == "svg":
            wb.export_svg(output)
        else:
            wb.export_gem_metafile(output)
    return _emit_workbench_payload(wb.snapshot_state(), as_json)


def _handle_workbench(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Handle `zoe workbench` CLI subcommand."""
    return _run_workbench_action(
        arguments.action,
        ticks=int(arguments.ticks),
        target=arguments.target,
        output=arguments.output,
        fmt=str(arguments.format),
        as_json=bool(arguments.json),
    )


def _handle_sister(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Handle `zoe sister` CLI subcommand across hex, EDDBMS, and read-only ablation."""
    from .zoe_ablation_bridge import AblationBridge
    from .zoe_hex_mesh import build_default_zoe_mesh, constitutional_metadata
    from .zoe_sisters import list_sisters

    action = str(arguments.action)
    if action == "list":
        meta = constitutional_metadata("measurement", read_only=True)
        payload: dict[str, Any] = {
            **meta,
            "sisters": [s.name for s in list_sisters()],
            "constitutional": dict(meta),
        }
    elif action == "hex":
        mesh = build_default_zoe_mesh()
        meta = mesh.constitutional_metadata("measurement", read_only=True)
        payload = {
            **meta,
            "shared_walls": len(mesh.shared_walls()),
            "sisters": [c.sister.name for c in mesh.cells()],
            "constitutional": dict(meta),
        }
    elif action == "ablation":
        bridge = AblationBridge()
        if arguments.target is not None:
            raw_target = str(arguments.target)
            if not raw_target.strip():
                raise ValueError("target_path must be a non-empty path")
            rep = bridge.inspect_target_readonly(target_path=Path(raw_target).expanduser())
        else:
            rep = bridge.inspect_target_readonly(raw_bytes=b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56, target_name="sister_probe.elf")
        payload = rep.to_dict()
    else:
        return _run_workbench_action("tick", ticks=1, as_json=bool(arguments.json))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_gem(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Forward `zoe gem` subcommands to the GEM operating environment or workbench."""
    args_list = list(arguments.arguments)
    if args_list and args_list[0] == "workbench":
        return _run_workbench_action("tick", ticks=1, as_json=("--json" in args_list))
    from .operating_environment import main as gem_main
    return int(gem_main(args_list))  # type: ignore[no-untyped-call]


def _handle_view(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Forward parsed view subcommand arguments to its view module."""
    return int(import_module(f".{arguments.command}_view", __package__).main(arguments.arguments))


def _handle_list(_arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Print every registered engine row from ComponentRegistry."""
    for component in registry.manifest()["components"]:  # type: ignore[no-untyped-call]
        source = component["source"]
        status = "present" if source["source_present"] else "missing"
        print(f"{component['identifier']:10} {status:8} {source['mode']:9} {component['summary']}")
    return 0


def _handle_manifest(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Write a no-overwrite unified component manifest JSON."""
    output = registry.write_manifest(arguments.output)  # type: ignore[no-untyped-call]
    print(json.dumps({"identity": IDENTITY, "output": str(output), "bytes": output.stat().st_size}, indent=2, sort_keys=True))
    return 0


def _handle_knowledge(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Write the unified source and trust-context knowledge graph."""
    output = registry.knowledge.save(arguments.output)
    print(json.dumps({"identity": IDENTITY, "output": str(output), "bytes": output.stat().st_size, "events": len(registry.knowledge.events)}, indent=2, sort_keys=True))
    return 0


def _handle_show(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Print JSON details for a single registered component."""
    registry.component(arguments.component)  # type: ignore[no-untyped-call]
    row = next(item for item in registry.manifest()["components"] if item["identifier"] == arguments.component)  # type: ignore[no-untyped-call]
    print(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_launch(arguments: argparse.Namespace, registry: ComponentRegistry) -> int:
    """Launch a registered engine or detached subprocess component."""
    forwarded = list(arguments.arguments)
    if forwarded and forwarded[0] == "--":
        forwarded.pop(0)
    result = registry.launch(arguments.component, forwarded or None, detach=arguments.detach)  # type: ignore[no-untyped-call]
    if arguments.detach:
        print(json.dumps({"component": arguments.component, "pid": result.pid, "started": True, "readiness_verified": False}, indent=2, sort_keys=True))
        return 0
    return int(result.returncode)


def _handle_r3(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Dispatch any R3 theorem/observatory command via shared gem.cli runner."""
    return int(dispatch_r3_cli(arguments))


def _handle_present(arguments: argparse.Namespace, _registry: ComponentRegistry) -> int:
    """Dispatch `zoe present` clean-room presentation suite commands."""
    from .presentation.cli_present import handle_present
    return int(handle_present(arguments))


# Declarative dispatch table for parsed `zoe` subcommands.
_COMMAND_HANDLERS = {
    "os": _handle_os,
    "gem": _handle_gem,
    "workbench": _handle_workbench,
    "sister": _handle_sister,
    "present": _handle_present,
    "list": _handle_list,
    "components": _handle_list,
    "manifest": _handle_manifest,
    "knowledge": _handle_knowledge,
    "show": _handle_show,
    "launch": _handle_launch,
    **{name: _handle_view for name in _VIEW_DESCRIPTIONS},
    **{name: _handle_r3 for name in R3_COMMAND_SPECS},
}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for `zoe`."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    # Forward raw view/os commands before argparse interprets view-specific flags.
    passthrough = _try_early_passthrough(raw_arguments)
    if passthrough is not None:
        return passthrough
    arguments = parser().parse_args(raw_arguments)
    registry = ComponentRegistry()  # type: ignore[no-untyped-call]
    try:
        handler = _COMMAND_HANDLERS.get(arguments.command)
        if handler is not None:
            return int(handler(arguments, registry))
        # Bare `zoe` (no subcommand) opens the interactive chat view.
        from .chat_view import main as chat_main
        return int(chat_main([]))  # type: ignore[no-untyped-call]
    except (OSError, RuntimeError, ValueError) as error:
        print(f"zoe: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

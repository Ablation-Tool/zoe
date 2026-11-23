from __future__ import annotations

import argparse
from importlib import import_module
import json
import subprocess
import sys

from .experiment import _zoe_root


# Declarative subcommand passthrough map for delegated CLI entrypoints.
_PASSTHROUGH_HANDLERS: dict[str, tuple[str, str]] = {
    "actuate": (".actuation", "actuation_main"),
    "explore": (".explore", "explore_main"),
    "agents": (".agents", "agents_main"),
    "capabilities": (".capabilities_cli", "capabilities_main"),
}

# Declarative table mapping verification commands to (module, fn_name, pass_zoe_root).
_VERIFY_DISPATCH: dict[str, tuple[str, str, bool]] = {
    "verify-reflection": (".self_reflection", "verify_reflection", True),
    "verify-step": (".autonomous", "verify_step_report", False),
    "verify-evaluation": (".evaluation", "verify_evaluation", False),
    "verify-event-evaluation": (".event_evaluation", "verify_event_evaluation", False),
    "verify-semantic-evaluation": (".semantic_artifacts", "verify_semantic_report", False),
}


def _add_core_parsers(commands) -> None:
    """Register core autonomy, reflection, chat, and step subparsers."""
    # Core measurement-action experiment subcommands.
    run = commands.add_parser("run", help="run the real-Zoe measurement-action experiment")
    run.add_argument("--output", help="new JSON evidence path")
    run.add_argument("--tau", type=float, default=.05)
    run.add_argument("--delta", type=float, default=.001)
    run.add_argument("--image", help="RGB image for shared saliency; default: documented synthetic pop-out")
    run.add_argument("--foci", type=int, default=4, help="attention selections with inhibition of return, from 1 to 8")
    run.add_argument("--reflect", action="store_true", help="use measured, goal-directed self-reflection in the main loop")
    run.add_argument("--full", action="store_true", help="print the complete report")
    verify = commands.add_parser("verify", help="recompute and verify a saved report")
    verify.add_argument("report")

    # Self-reflection and verification subcommands.
    reflect = commands.add_parser("reflect", help="learn and validate model choices from actual prediction errors")
    reflect.add_argument("--input", help="stereo observation JSON document; default: documented synthetic stereo")
    reflect.add_argument("--previous", help="earlier self-reflection JSON report")
    reflect.add_argument("--initial-model", choices=("arithmetic", "precision"), help="initial fusion model; default: arithmetic")
    reflect.add_argument("--output", help="new JSON evidence path")
    reflect.add_argument("--full", action="store_true", help="print the complete reflection report")
    commands.add_parser("verify-reflection", help="recompute and verify a self-reflection report").add_argument("report")

    # Interactive chat and single-step autonomy subcommands.
    chat = commands.add_parser("chat", help="talk with Zoe through evidence, memory, autonomy, and metacognition")
    chat.add_argument("--state", help="persistent chat state directory; default: ZOE_CHAT_STATE or ~/.zoe/chat")
    chat.add_argument("--command", dest="chat_command", help="process one chat command or question, then exit")
    step = commands.add_parser("step", help="let Zoe author a goal and select and execute a capability without operator selection")
    step.add_argument("--state", help="autonomous state directory; default: ZOE_AUTONOMY_STATE or ~/.zoe/autonomy")
    step.add_argument("--output", help="new JSON decision evidence path")
    commands.add_parser("verify-step", help="verify autonomous-step integrity and decision provenance").add_argument("report")


def _add_passthrough_parsers(commands) -> None:
    """Register delegated passthrough subcommands (actuate, explore, agents, capabilities)."""
    # Keep remainder args untouched so delegated CLIs parse their own flags.
    descriptions = {
        "actuate": "owner-granted host, network, and hardware actuation",
        "explore": "retrieve and follow public web content",
        "agents": "use owner-connected AI agent accounts",
        "capabilities": "use the unified Zoe capability pack",
    }
    for name, help_text in descriptions.items():
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("arguments", nargs=argparse.REMAINDER)


def _add_eval_parsers(commands) -> None:
    """Register visual, event-causal, and semantic evaluation subcommands."""
    # Integrated visual autonomy evaluation and verification.
    evaluate = commands.add_parser("evaluate", help="test perception, thinking, learning, action, and their feedback links")
    visual_input = evaluate.add_mutually_exclusive_group()
    visual_input.add_argument("--image", help="RGB image-file input for the visual evaluation")
    visual_input.add_argument("--camera", nargs="?", const="/dev/video0", help="capture one camera frame; default device: /dev/video0")
    evaluate.add_argument("--foci", type=int, default=4, help="attention selections with inhibition of return, from 1 to 8")
    evaluate.add_argument("--output", help="new JSON evaluation evidence path")
    evaluate.add_argument("--full", action="store_true", help="print the complete evaluation report")
    commands.add_parser("verify-evaluation", help="verify autonomy-evaluation integrity and coverage consistency").add_argument("report")

    # Event-causal active perception evaluation and verification.
    event_evaluate = commands.add_parser("event-evaluate", help="evaluate event-causal active perception against pre-registered controls")
    event_evaluate.add_argument("--protocol", help="pre-registered event-causal protocol JSON")
    event_evaluate.add_argument("--camera", nargs="?", const="/dev/video0", help="also convert two real camera frames into events; default device: /dev/video0")
    event_evaluate.add_argument("--output", help="new JSON event-causal evaluation path")
    event_evaluate.add_argument("--full", action="store_true", help="print the complete event-causal evaluation")
    commands.add_parser("verify-event-evaluation", help="verify event-causal evaluation integrity and result consistency").add_argument("report")

    # Semantic binary artifact evaluation via Ablation + Zoe.
    semantic = commands.add_parser("semantic-evaluate", help="analyze executable-artifact semantics with Ablation and Zoe")
    semantic.add_argument("--artifact", required=True, help="ELF artifact to analyze without executing it")
    semantic.add_argument("--query", default=None, help="natural-language behavioral query")
    semantic.add_argument("--ablation-root", help="Ablation checkout; default: ABLATION_ROOT or the canonical workspace checkout")
    semantic.add_argument("--state", help="persistent semantic-memory directory; default: .zoe/semantic-artifacts")
    semantic.add_argument("--output", help="new JSON semantic-artifact report path")
    semantic.add_argument("--full", action="store_true", help="print the complete semantic-artifact report")
    commands.add_parser("verify-semantic-evaluation", help="verify semantic-artifact report integrity and result consistency").add_argument("report")


def parser():
    """Build the top-level zoe-autonomy argument parser."""
    # Assemble all subcommand groups via focused registration helpers.
    result = argparse.ArgumentParser(prog="zoe-autonomy", description="Zoe + Operational Metacognition · operational full self-governing autonomy")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    commands = result.add_subparsers(dest="command", required=True)
    _add_core_parsers(commands)
    _add_passthrough_parsers(commands)
    _add_eval_parsers(commands)
    return result


def _print_json(document) -> None:
    """Emit formatted deterministic UTF-8 JSON to stdout."""
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))


def _emit_report(report: dict, output, summary_fn, hash_key: str, full: bool) -> None:
    """Print either full JSON or human summary, plus optional evidence path line."""
    if full:
        _print_json(report)
    else:
        print(summary_fn(report))
    if output is not None:
        print(f"Evidence: {output} · {hash_key}={report[hash_key]}")


def _try_passthrough(raw_arguments: list[str]) -> int | None:
    """Forward raw CLI arguments directly to delegated sub-CLIs when matched."""
    if not raw_arguments or raw_arguments[0] not in _PASSTHROUGH_HANDLERS:
        return None
    mod_name, fn_name = _PASSTHROUGH_HANDLERS[raw_arguments[0]]
    return getattr(import_module(mod_name, __package__), fn_name)(raw_arguments[1:])


def _handle_passthrough_parsed(arguments: argparse.Namespace) -> int:
    """Forward parsed remainder arguments for delegated subcommands."""
    mod_name, fn_name = _PASSTHROUGH_HANDLERS[arguments.command]
    return getattr(import_module(mod_name, __package__), fn_name)(arguments.arguments)


def _handle_run(arguments: argparse.Namespace) -> int:
    """Forward the measurement-action experiment to guiai.gem.autonomy_view."""
    _zoe_root(arguments.zoe_root)
    from guiai.gem.autonomy_view import main as unified_main

    # Reconstruct forwarded flags in autonomy_view order.
    forwarded = ["run"]
    if arguments.zoe_root:
        forwarded.extend(["--zoe-root", arguments.zoe_root])
    forwarded.extend(["--tau", str(arguments.tau), "--delta", str(arguments.delta)])
    if arguments.image:
        forwarded.extend(["--image", arguments.image])
    forwarded.extend(["--foci", str(arguments.foci)])
    if arguments.reflect:
        forwarded.append("--reflect")
    if arguments.output:
        forwarded.extend(["--output", arguments.output])
    if arguments.full:
        forwarded.append("--full")
    return unified_main(forwarded)


def _handle_verify(arguments: argparse.Namespace) -> int:
    """Forward saved experiment verification to guiai.gem.autonomy_view."""
    _zoe_root(arguments.zoe_root)
    from guiai.gem.autonomy_view import main as unified_main

    forwarded = ["verify", arguments.report]
    if arguments.zoe_root:
        forwarded.extend(["--zoe-root", arguments.zoe_root])
    return unified_main(forwarded)


def _handle_reflect(arguments: argparse.Namespace) -> int:
    """Run predictive self-reflection and optionally save evidence JSON."""
    from .self_reflection import _read_json, run_reflection, save_reflection, summary

    document = _read_json(arguments.input) if arguments.input else None
    previous = _read_json(arguments.previous) if arguments.previous else None
    report = run_reflection(arguments.zoe_root, previous, document, arguments.initial_model)
    output = save_reflection(report, arguments.output) if arguments.output else None
    _emit_report(report, output, summary, "profile_sha256", arguments.full)
    return 0


def _handle_chat(arguments: argparse.Namespace) -> int:
    """Launch or execute one turn of Zoe's native evidence-linked chat."""
    from .chat import main as chat_main

    forwarded = []
    if arguments.zoe_root:
        forwarded.extend(["--zoe-root", arguments.zoe_root])
    if arguments.state:
        forwarded.extend(["--state", arguments.state])
    if arguments.chat_command:
        forwarded.extend(["--command", arguments.chat_command])
    return chat_main(forwarded)


def _handle_step(arguments: argparse.Namespace) -> int:
    """Execute one autonomous goal-authored step."""
    from .autonomous import run_step, save_step_report, step_summary

    report = run_step(arguments.state)
    output = save_step_report(report, arguments.output) if arguments.output else None
    _emit_report(report, output, step_summary, "step_sha256", False)
    return 0 if report["execution"]["succeeded"] else 1


def _handle_evaluate(arguments: argparse.Namespace) -> int:
    """Run integrated visual autonomy evaluation across perception and action."""
    from .evaluation import evaluation_summary, run_evaluation, save_evaluation

    report = run_evaluation(
        arguments.zoe_root,
        image_path=arguments.image,
        camera=arguments.camera,
        attention_steps=arguments.foci,
    )
    output = save_evaluation(report, arguments.output) if arguments.output else None
    _emit_report(report, output, evaluation_summary, "evaluation_sha256", arguments.full)
    return 0 if report["overall"]["integrated_visual_autonomy_passed"] else 1


def _handle_event_evaluate(arguments: argparse.Namespace) -> int:
    """Evaluate event-causal active perception against pre-registered controls."""
    from .event_evaluation import event_evaluation_summary, run_event_evaluation, save_event_evaluation

    report = run_event_evaluation(
        arguments.zoe_root,
        protocol_path=arguments.protocol,
        include_camera=arguments.camera if arguments.camera is not None else False,
    )
    output = save_event_evaluation(report, arguments.output) if arguments.output else None
    _emit_report(report, output, event_evaluation_summary, "evaluation_sha256", arguments.full)
    return 0 if report["overall"]["passed"] else 1


def _handle_semantic_evaluate(arguments: argparse.Namespace) -> int:
    """Analyze ELF artifact semantics using Ablation and Zoe."""
    from .semantic_artifacts import DEFAULT_QUERY, analyze_artifact, save_semantic_report, semantic_summary

    report = analyze_artifact(
        arguments.zoe_root,
        arguments.artifact,
        query=arguments.query or DEFAULT_QUERY,
        state_root=arguments.state,
        ablation_root=arguments.ablation_root,
    )
    output = save_semantic_report(report, arguments.output) if arguments.output else None
    _emit_report(report, output, semantic_summary, "evaluation_sha256", arguments.full)
    return 0 if report["overall"]["passed"] else 1


def _handle_verify_command(arguments: argparse.Namespace) -> int:
    """Dispatch any verify-* command via _VERIFY_DISPATCH."""
    mod_name, fn_name, pass_root = _VERIFY_DISPATCH[arguments.command]
    verify_fn = getattr(import_module(mod_name, __package__), fn_name)
    result = verify_fn(arguments.report, arguments.zoe_root) if pass_root else verify_fn(arguments.report)
    _print_json(result)
    return 0


# Declarative command dispatch table for parsed subcommands.
_COMMAND_HANDLERS = {
    "run": _handle_run,
    "verify": _handle_verify,
    "reflect": _handle_reflect,
    "chat": _handle_chat,
    "step": _handle_step,
    "evaluate": _handle_evaluate,
    "event-evaluate": _handle_event_evaluate,
    "semantic-evaluate": _handle_semantic_evaluate,
    "actuate": _handle_passthrough_parsed,
    "explore": _handle_passthrough_parsed,
    "agents": _handle_passthrough_parsed,
    "capabilities": _handle_passthrough_parsed,
    "verify-reflection": _handle_verify_command,
    "verify-step": _handle_verify_command,
    "verify-evaluation": _handle_verify_command,
    "verify-event-evaluation": _handle_verify_command,
    "verify-semantic-evaluation": _handle_verify_command,
}


def main(argv=None):
    """CLI entrypoint for zoe-autonomy."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        # Handle direct passthrough subcommands before argparse parses flags.
        passthrough = _try_passthrough(raw_arguments)
        if passthrough is not None:
            return passthrough
        arguments = parser().parse_args(raw_arguments)
        handler = _COMMAND_HANDLERS[arguments.command]
        return handler(arguments)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"zoe-autonomy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

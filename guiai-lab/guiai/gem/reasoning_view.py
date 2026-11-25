"""Unified `zoe reasoning` CLI view for Zoe x Antigravity Shared-Reasoning Architectures (1-9 + GEM)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

from .autonomy_view import configure_autonomy

REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    """Build the `zoe reasoning` subcommand parser."""
    parser = argparse.ArgumentParser(
        prog="zoe reasoning",
        description="Zoe x Antigravity Shared-Reasoning Architectures (1-9 + Digital Research GEM)",
    )
    sub = parser.add_subparsers(dest="action")

    status = sub.add_parser("status", help="list available Shared-Reasoning architectures and invariants")
    status.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    run = sub.add_parser("run", help="run composed Architectures 1-9 offline or with local loopback")
    run.add_argument("--prompt", required=True, help="research or engineering prompt to evaluate")
    run.add_argument("--mode", choices=("offline", "auto", "local_qwen", "gemini"), default="offline")
    run.add_argument("--no-gem", action="store_true", help="skip Stage 8.5 Digital Research GEM VDI pass")
    run.add_argument("--gem-out", type=Path, default=None, help="optional directory to write .GEM/.RSC artifacts")
    run.add_argument("--json", action="store_true", help="emit full JSON summary")

    gem = sub.add_parser("gem", help="build and verify a Digital Research GEM VDI desktop across CGA/VGA/NDC")
    gem.add_argument("--theme", default="zoe-viewmax3", help="GEM/ViewMAX theme key")
    gem.add_argument("--json", action="store_true", help="emit JSON output")

    verify = sub.add_parser("verify", help="run the full end-to-end Shared-Reasoning verifier")
    verify.add_argument("--json", action="store_true", help="emit full verification JSON")

    sub.add_parser("mcp", help="start the stdio JSON-RPC 2.0 MCP server for Shared Reasoning")
    return parser


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _cmd_status(args: argparse.Namespace) -> int:
    from zoe_autonomy.shared_reasoning import available_submodules

    modules = sorted(available_submodules())
    payload = {
        "contract": "zoe-shared-reasoning-cli/v1",
        "architectures": 9,
        "submodules": modules,
        "submodule_count": len(modules),
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
    }
    _print_payload(payload, bool(args.json))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from zoe_autonomy.shared_reasoning import SharedReasoningOrchestrator, SharedReasoningTaskSpec

    with tempfile.TemporaryDirectory(prefix="zoe-reasoning-cli-") as tmpdir:
        orchestrator = SharedReasoningOrchestrator(
            mode=args.mode,
            offline_only=(args.mode == "offline"),
            repo_root=REPO_ROOT,
            state_dir=Path(tmpdir) / "state",
        )
        report = orchestrator.run(
            SharedReasoningTaskSpec(
                prompt=args.prompt,
                enable_gem_desktop=not bool(args.no_gem),
                gem_vdi_output_dir=args.gem_out,
                high_impact=True,
            )
        )
    payload = {
        "contract": report.contract,
        "transport_mode": str(report.bridge_turn.resolution.to_dict().get("effective_mode", args.mode)),
        "arch1_score": report.alpha_evolve.best_program.score,
        "arch3_mcts_decision": report.mcts_result.decision,
        "arch4_quorum_verdict": report.quorum_result.verdict,
        "arch5_distilled_count": len(report.distilled_artifacts),
        "arch6_blackboard_entries": report.blackboard_integrity["entries_verified"],
        "arch7_sympy_passed": report.sandbox_verdicts["sympy"].passed,
        "arch7_z3_passed": report.sandbox_verdicts["z3"].passed,
        "arch8_fork_detected": report.steering_report.fork_detected,
        "arch9_counterpoint_turns": report.counterpoint_result.total_turns,
        "gem_desktop_verified": bool((report.gem_desktop_report or {}).get("passed", False)),
        "external_actions": report.external_actions,
        "sentience_claimed": report.sentience_claimed,
        "l5_agi_qualified": report.l5_agi_qualified,
        "zoe_clone_claimed": report.zoe_clone_claimed,
    }
    _print_payload(payload, bool(args.json))
    return 0


def _cmd_gem(args: argparse.Namespace) -> int:
    from zoe_autonomy.shared_reasoning import GemVdiWorkstation, RealitySandboxLab, build_default_atari_rsc

    ws = GemVdiWorkstation(device="vga", theme_key=args.theme)
    scene = ws.build_shared_reasoning_scene({"quorum_verdict": "CLI_PROBE", "fork_detected": True})
    lab = RealitySandboxLab()
    vdi_v = lab.verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    rsc_v = lab.verify_gem_rsc_bytes(build_default_atari_rsc(), label="ZOE_CLI.RSC")
    payload = {
        "passed": bool(vdi_v.passed and rsc_v.passed),
        "theme_key": ws.theme_key,
        "profiles_passed": dict(vdi_v.ground_truth.get("profiles_passed", {})),
        "metafile_sha256": vdi_v.ground_truth.get("metafile_sha256"),
        "rsc_sha256": rsc_v.ground_truth.get("rsc_sha256"),
        "visual_evidence_only": True,
        "external_actions": 0,
    }
    _print_payload(payload, bool(args.json))
    return 0 if payload["passed"] else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import verify_shared_reasoning

    argv = ["--json"] if args.json else []
    return int(verify_shared_reasoning.main(argv))


def _cmd_mcp(_args: argparse.Namespace) -> int:
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import zoe_shared_reasoning_mcp

    return int(zoe_shared_reasoning_mcp.main())


_HANDLERS = {
    "status": _cmd_status,
    "run": _cmd_run,
    "gem": _cmd_gem,
    "verify": _cmd_verify,
    "mcp": _cmd_mcp,
}


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for `zoe reasoning`."""
    configure_autonomy()
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = _HANDLERS.get(args.action or "status")
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

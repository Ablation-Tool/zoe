from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .experiment import _zoe_root, run_experiment, save_report, summary, verify_report


def parser():
    result = argparse.ArgumentParser(prog="zoe-autonomy", description="Zoe + Accessible Volume · operational full self-governing autonomy")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    commands = result.add_subparsers(dest="command", required=True)
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
    reflect = commands.add_parser("reflect", help="learn and validate model choices from actual prediction errors")
    reflect.add_argument("--input", help="stereo observation JSON document; default: documented synthetic stereo")
    reflect.add_argument("--previous", help="earlier self-reflection JSON report")
    reflect.add_argument("--initial-model", choices=("arithmetic", "precision"), help="initial fusion model; default: arithmetic")
    reflect.add_argument("--output", help="new JSON evidence path")
    reflect.add_argument("--full", action="store_true", help="print the complete reflection report")
    verify_reflection = commands.add_parser("verify-reflection", help="recompute and verify a self-reflection report")
    verify_reflection.add_argument("report")
    actuate = commands.add_parser("actuate", help="owner-granted host, network, and hardware actuation")
    actuate.add_argument("arguments", nargs=argparse.REMAINDER)
    explore = commands.add_parser("explore", help="retrieve and follow public web content")
    explore.add_argument("arguments", nargs=argparse.REMAINDER)
    agents = commands.add_parser("agents", help="use owner-connected AI agent accounts")
    agents.add_argument("arguments", nargs=argparse.REMAINDER)
    capabilities = commands.add_parser("capabilities", help="use the unified Zoe capability pack")
    capabilities.add_argument("arguments", nargs=argparse.REMAINDER)
    step = commands.add_parser("step", help="let Zoe author a goal and select and execute a capability without operator selection")
    step.add_argument("--state", help="autonomous state directory; default: ZOE_AUTONOMY_STATE or ~/.zoe/autonomy")
    step.add_argument("--output", help="new JSON decision evidence path")
    verify_step = commands.add_parser("verify-step", help="verify autonomous-step integrity and decision provenance")
    verify_step.add_argument("report")
    return result


def main(argv=None):
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if raw_arguments and raw_arguments[0] == "actuate":
            from .actuation import actuation_main
            return actuation_main(raw_arguments[1:])
        if raw_arguments and raw_arguments[0] == "explore":
            from .explore import explore_main
            return explore_main(raw_arguments[1:])
        if raw_arguments and raw_arguments[0] == "agents":
            from .agents import agents_main
            return agents_main(raw_arguments[1:])
        if raw_arguments and raw_arguments[0] == "capabilities":
            from .capabilities_cli import capabilities_main
            return capabilities_main(raw_arguments[1:])
        arguments = parser().parse_args(raw_arguments)
        if arguments.command == "actuate":
            from .actuation import actuation_main
            return actuation_main(arguments.arguments)
        if arguments.command in {"run", "verify", "reflect", "verify-reflection"}:
            _zoe_root(arguments.zoe_root)
            from guiai.gem.autonomy_view import main as unified_main
        if arguments.command == "run":
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
        if arguments.command == "reflect":
            from .self_reflection import _read_json, run_reflection, save_reflection, summary

            document = _read_json(arguments.input) if arguments.input else None
            previous = _read_json(arguments.previous) if arguments.previous else None
            report = run_reflection(arguments.zoe_root, previous, document, arguments.initial_model)
            output = save_reflection(report, arguments.output) if arguments.output else None
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) if arguments.full else summary(report))
            if output is not None:
                print(f"Evidence: {output} · profile_sha256={report['profile_sha256']}")
            return 0
        if arguments.command == "verify-reflection":
            from .self_reflection import verify_reflection

            print(json.dumps(verify_reflection(arguments.report, arguments.zoe_root), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if arguments.command == "step":
            from .autonomous import run_step, save_step_report, step_summary
            report = run_step(arguments.state)
            output = save_step_report(report, arguments.output) if arguments.output else None
            print(step_summary(report))
            if output:
                print(f"Evidence: {output} · step_sha256={report['step_sha256']}")
            return 0 if report["execution"]["succeeded"] else 1
        if arguments.command == "verify-step":
            from .autonomous import verify_step_report
            print(json.dumps(verify_step_report(arguments.report), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if arguments.command == "verify":
            forwarded = ["verify", arguments.report]
            if arguments.zoe_root:
                forwarded.extend(["--zoe-root", arguments.zoe_root])
            return unified_main(forwarded)
        result = verify_report(arguments.report, arguments.zoe_root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"zoe-autonomy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

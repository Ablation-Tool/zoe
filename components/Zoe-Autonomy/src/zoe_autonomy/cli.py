from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .experiment import run_experiment, save_report, summary, verify_report


def parser():
    result = argparse.ArgumentParser(prog="zoe-autonomy", description="Zoe + Accessible Volume · operational full self-governing autonomy")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the real-Zoe measurement-action experiment")
    run.add_argument("--output", help="new JSON evidence path")
    run.add_argument("--tau", type=float, default=.05)
    run.add_argument("--delta", type=float, default=.001)
    run.add_argument("--full", action="store_true", help="print the complete report")
    verify = commands.add_parser("verify", help="recompute and verify a saved report")
    verify.add_argument("report")
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
        if arguments.command == "run":
            report = run_experiment(arguments.zoe_root, arguments.tau, arguments.delta)
            output = save_report(report, arguments.output) if arguments.output else None
            if arguments.full:
                print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(summary(report))
                if output:
                    print(f"Evidence: {output} · profile_sha256={report['profile_sha256']}")
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
        result = verify_report(arguments.report, arguments.zoe_root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"zoe-autonomy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

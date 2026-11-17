from __future__ import annotations

import argparse
import json
import sys

from .autonomy import measure_zoe_profile, profile_summary, save_profile, verify_profile


def parser():
    result = argparse.ArgumentParser(prog="autonomy", description="Zoe · operational bounded-autonomy profile with counterfactual and control evidence")
    result.add_argument("--verify", help="recompute and verify a saved autonomy profile")
    result.add_argument("--output", help="new JSON evidence path")
    result.add_argument("--tau", type=float, default=.05, help="strict accessible-forecast threshold; default: 0.05")
    result.add_argument("--delta", type=float, default=.001, help="strict policy-effect threshold in bits; default: 0.001")
    result.add_argument("--full", action="store_true", help="print the complete profile instead of its summary")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.verify:
            if arguments.output:
                raise ValueError("choose --verify or --output, not both")
            result = verify_profile(arguments.verify)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        report = measure_zoe_profile(arguments.tau, arguments.delta)
        output = save_profile(report, arguments.output) if arguments.output else None
        if arguments.full:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(profile_summary(report))
            if output is not None:
                print(f"Evidence: {output} · profile_sha256={report['profile_sha256']}")
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"autonomy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

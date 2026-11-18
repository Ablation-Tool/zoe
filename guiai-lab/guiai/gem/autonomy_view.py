from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .operational_autonomy import profile_summary, verify_profile

ROOT = Path(__file__).resolve().parents[3]
COMPONENT_SRC = ROOT / "components" / "Zoe-Autonomy" / "src"


def configure_autonomy():
    if not (COMPONENT_SRC / "zoe_autonomy" / "experiment.py").is_file():
        raise ValueError(f"Zoe-Autonomy component is unavailable: {COMPONENT_SRC}")
    os.environ.setdefault("ZOE_ROOT", str(ROOT))
    if str(COMPONENT_SRC) not in sys.path:
        sys.path.insert(0, str(COMPONENT_SRC))
    return ROOT


def _unified_report(tau, delta, zoe_root=ROOT, image_path=None, attention_steps=4):
    configure_autonomy()
    from zoe_autonomy.experiment import run_experiment

    return run_experiment(
        zoe_root, tau=tau, delta=delta, image_path=image_path, attention_steps=attention_steps,
    )


def _verify(path, zoe_root=ROOT):
    configure_autonomy()
    from zoe_autonomy.experiment import verify_report

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("instrument") == "zoe-operational-bounded-autonomy-profile":
        return verify_profile(path)
    return verify_report(path, zoe_root)


def parser():
    result = argparse.ArgumentParser(prog="autonomy", description="Zoe · unified measurement, autonomy, and operational profile")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    result.add_argument("--verify", help="recompute and verify a saved unified autonomy report")
    result.add_argument("--output", help="new JSON evidence path")
    result.add_argument("--tau", type=float, default=.05, help="strict accessible-forecast threshold; default: 0.05")
    result.add_argument("--delta", type=float, default=.001, help="strict policy-effect threshold in bits; default: 0.001")
    result.add_argument("--image", help="RGB image for shared saliency; default: documented synthetic pop-out")
    result.add_argument("--foci", type=int, default=4, help="attention selections with inhibition of return, from 1 to 8")
    result.add_argument("--full", action="store_true", help="print the complete unified report instead of its summary")
    return result


def main(argv=None):
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    unified_prefixes = {"run", "verify", "--verify", "--output", "--tau", "--delta", "--image", "--foci", "--full"}
    if raw_arguments and raw_arguments[0] not in unified_prefixes:
        configure_autonomy()
        from zoe_autonomy.cli import main as autonomy_main
        return autonomy_main(raw_arguments)
    if raw_arguments and raw_arguments[0] == "run":
        raw_arguments = raw_arguments[1:]
    elif raw_arguments and raw_arguments[0] == "verify":
        raw_arguments = ["--verify", raw_arguments[1]]
    arguments = parser().parse_args(raw_arguments)
    try:
        if arguments.verify:
            if arguments.output:
                raise ValueError("choose --verify or --output, not both")
            result = _verify(arguments.verify, arguments.zoe_root or ROOT)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        configure_autonomy()
        from zoe_autonomy.experiment import save_report, summary

        report = _unified_report(
            arguments.tau, arguments.delta, arguments.zoe_root or ROOT,
            image_path=arguments.image, attention_steps=arguments.foci,
        )
        output = save_report(report, arguments.output) if arguments.output else None
        if arguments.full:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(summary(report))
            print(profile_summary(report["operational_profile"]))
            if output is not None:
                print(f"Evidence: {output} · profile_sha256={report['profile_sha256']}")
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"autonomy: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Standalone CLI runner for the Zoe-GEM OS 4-tier opaque-box E2E test suite."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import unittest

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from harness import run_elegance_check, run_hygiene_scan  # noqa: E402

_TIER_FILES = {
    "1": "test_tier1_features.py",
    "2": "test_tier2_boundaries.py",
    "3": "test_tier3_pairwise.py",
    "4": "test_tier4_scenarios.py",
}


def build_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser for the E2E suite."""
    parser = argparse.ArgumentParser(description="Zoe-GEM OS E2E Test Suite Runner")
    parser.add_argument("--tier", choices=("1", "2", "3", "4", "all"), default="all")
    parser.add_argument("--strict", action="store_true", help="Fail instead of skip on pending capabilities")
    parser.add_argument("--elegance", action="store_true", help="Run monorepo elegance and hygiene audits")
    parser.add_argument("--json-out", type=Path, help="Optional path to write structured JSON summary")
    parser.add_argument("--verbose", action="store_true", help="Verbose unittest output")
    return parser


def load_tier_suite(tier: str) -> unittest.TestSuite:
    """Load unittest TestSuite for a single tier or all tiers."""
    loader = unittest.TestLoader()
    if tier == "all":
        return loader.discover(start_dir=str(_THIS_DIR), pattern="test_tier*.py")
    return loader.discover(start_dir=str(_THIS_DIR), pattern=_TIER_FILES[tier])


def summarize_result(result: unittest.TestResult, elegance: dict | None, hygiene: dict | None) -> dict:
    """Build structured summary dictionary for reporting and --json-out."""
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = result.testsRun - failures - errors - skipped
    return {
        "tests_run": result.testsRun,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": passed,
        "ok": result.wasSuccessful(),
        "strict_mode": os.environ.get("ZOE_E2E_STRICT") == "1",
        "elegance_ok": None if elegance is None else elegance["all_ok"],
        "hygiene_clean": None if hygiene is None else hygiene["clean"],
    }


def _execute_audits() -> tuple[dict, dict, bool]:
    """Run elegance and hygiene audits and print concise status lines."""
    elegance = run_elegance_check()
    hygiene = run_hygiene_scan()
    print(f"[ELEGANCE] all_ok={elegance['all_ok']} monorepo_verified={elegance['monorepo_verified']} e2e_ok={elegance['e2e_ok']}")
    print(f"[HYGIENE]  clean={hygiene['clean']} scanned={hygiene['scanned_files']} leaks={len(hygiene['leaks'])}")
    passed = bool(elegance["all_ok"]) and bool(hygiene["clean"])
    return elegance, hygiene, passed


def main(argv: list[str] | None = None) -> int:
    """Execute selected E2E tiers and optional elegance/hygiene checks."""
    args = build_parser().parse_args(argv)
    if args.strict:
        os.environ["ZOE_E2E_STRICT"] = "1"
    verbosity = 2 if args.verbose else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(load_tier_suite(args.tier))

    elegance, hygiene, audits_ok = (None, None, True)
    if args.elegance:
        elegance, hygiene, audits_ok = _execute_audits()

    summary = summarize_result(result, elegance, hygiene)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return 0 if result.wasSuccessful() and audits_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

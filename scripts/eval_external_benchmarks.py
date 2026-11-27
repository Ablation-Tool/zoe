#!/usr/bin/env python3
"""Independent Zero-Leakage Runner for Zoe External Uncurated Benchmark Harness (#2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "components/Zoe-Autonomy/src"))

from zoe_autonomy.external_benchmark_harness import run_external_benchmark_suite


def main() -> int:
    report = run_external_benchmark_suite()
    out = ROOT / "evidence/external-benchmarks/external-benchmark-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for name, tr in report["tracks"].items():
        print(f"TRACK {name}: { {k: v for k, v in tr.items() if k != 'rows'} }")
    print()
    passed = sum(1 for ok in report["checks"].values() if ok)
    for k, ok in report["checks"].items():
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(report['checks'])} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if report["all_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

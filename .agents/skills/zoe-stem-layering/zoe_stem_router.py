#!/usr/bin/env python3
"""CLI wrapper for Cognitive Stem-Layering (`zoe_autonomy.stem_layering`)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ZOE_AUTONOMY_SRC = _REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if _ZOE_AUTONOMY_SRC.is_dir() and str(_ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(_ZOE_AUTONOMY_SRC))

from zoe_autonomy.stem_layering import DEFAULT_TAU, route_stem  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zoe_stem_router.py",
        description="Route a task across Zoe's Cognitive Stem-Layering tiers using Kloster A_tau(p).",
    )
    parser.add_argument("--prompt", required=True, help="Task or prompt text to route.")
    parser.add_argument("--offline-only", action="store_true", help="Restrict routing to offline local tiers (0 cloud tokens).")
    parser.add_argument("--privacy-sensitive", action="store_true", help="Restrict routing to loopback local tiers only.")
    parser.add_argument("--files-count", type=int, default=1, help="Estimated number of files involved (default: 1).")
    parser.add_argument("--multi-file", action="store_true", help="Indicate multi-file scope.")
    parser.add_argument("--probe-local", action="store_true", help="Probe loopback 127.0.0.1:8080/v1/models for Qwen2.5-3B.")
    parser.add_argument("--tau", type=float, default=DEFAULT_TAU, help=f"Kloster threshold tau in (0, 1) (default: {DEFAULT_TAU}).")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit full StemDecision JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    decision = route_stem(
        args.prompt,
        offline_only=args.offline_only,
        privacy_sensitive=args.privacy_sensitive,
        files_count=args.files_count,
        multi_file=args.multi_file,
        probe_local=args.probe_local,
        tau=args.tau,
    )
    doc = decision.to_dict()
    if args.as_json:
        print(json.dumps(doc, indent=2, sort_keys=True))
    else:
        print(
            f"tier={doc['selected_tier']} model={doc['antigravity_model']} "
            f"thinking={doc['thinking_level']} teamwork={doc['teamwork_recommended']} "
            f"A_tau({doc['tau']})={doc['a_tau']} fallback={doc['fallback_tier']} "
            f"(applied={doc['fallback_applied']})"
        )
        probs = ", ".join(f"{k}={v:.4f}" for k, v in doc["probabilities"].items())
        print(f"probabilities: {probs}")
        if doc["fallback_reason"]:
            print(f"fallback_reason: {doc['fallback_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

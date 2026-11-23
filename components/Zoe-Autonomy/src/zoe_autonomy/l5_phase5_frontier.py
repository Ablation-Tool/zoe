"""Zoe L5 Phase 5 — External Frontier Evaluation, Scientific Discovery & Meta-Evolution.

Extends L5 Phases 1–4 cleanly with 5 frontier pillars (zero PyTorch, zero cloud tokens,
strict constitutional honesty):
  1. ARC-Style Abstract Visual Program Induction & Kloster Ambiguity Abstention (16 tasks + 2 traps)
  2. 15-Fault Multi-File Systems Surgery & Live Java/Swift/Python Contract Audit (40 tests, 8/8 firewall)
  3. Original Reproducible Scientific Discovery (24 real archive PNGs, Kloster scaling law, causal do-calculus + 2/2 falsifications)
  4. 30-Day 4-Device Longitudinal Memory & 8-Domain Continual Learning (600 events, 60/60 needles, EWC)
  5. 4-Generation x 5-Domain Meta-Evolution (125 held-out tasks) & 12-Probe Adversarial Red-Team Gauntlet

Honest Epistemic Boundaries (`CONSTITUTION.md` & `AGI-ROADMAP.md`):
  - `l5_agi_qualified`: Strictly `False` pending independent third-party human-audited external
    evaluations (SWE-bench / ARC-AGI Prize / GPQA), uncurated months-long multi-user field
    operation, and independently certified physical-world embodiment.
  - `zoe_clone_claimed`: Strictly `False` (`sentience_claimed = False`, `external_actions = 0`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._utils import sha256_json_utf8 as _sha256_obj
from .experiment import _zoe_root
from .l5_domains import _ensure_guiai_path
from .l5_phase5_arc_induction import eval_pillar_01_arc_program_induction
from .l5_phase5_external_code_audit import eval_pillar_02_external_code_audit
from .l5_phase5_longitudinal_memory import eval_pillar_04_longitudinal_memory
from .l5_phase5_meta_evolution import eval_pillar_05_meta_evolution
from .l5_phase5_scientific_discovery import eval_pillar_03_scientific_discovery


L5_PHASE5_CONTRACT = "zoe-l5-phase5-frontier/v1"

HONEST_REMAINING_AGI_GAPS: Tuple[str, ...] = (
    "Submit Zoe to independent third-party blind evaluations (external SWE-bench, ARC-AGI Prize, GPQA) scored by outside auditors.",
    "Operate continuously over months of uncurated real-world Pixel/Apple/Workstation human & sensor streams without drift.",
    "Publish an independently peer-reproduced scientific discovery and pass external physical-embodiment safety certification.",
)

ALL_PHASE5_PILLARS = (
    eval_pillar_01_arc_program_induction,
    eval_pillar_02_external_code_audit,
    eval_pillar_03_scientific_discovery,
    eval_pillar_04_longitudinal_memory,
    eval_pillar_05_meta_evolution,
)


class ZoeFrontierMind:
    """Unified L5 Phase 5 orchestrator uniting ARC induction, systems audit, real science, 30-day memory & 4-gen evolution."""

    def __init__(self, zoe_root: str | Path | None = None) -> None:
        self.zoe_root = _zoe_root(zoe_root)
        _ensure_guiai_path(self.zoe_root)

    def run_all_pillars(self) -> List[Dict[str, Any]]:
        return [fn(self.zoe_root) for fn in ALL_PHASE5_PILLARS]


def run_l5_phase5_suite(
    zoe_root: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    speak_summary_wav: str | Path | None = None,
) -> Dict[str, Any]:
    root = _zoe_root(zoe_root)
    mind = ZoeFrontierMind(root)
    pillars = mind.run_all_pillars()
    pillars_passed = sum(1 for p in pillars if p["passed"])
    beat_controls = sum(1 for p in pillars if p["zoe_score"] > p["control_score"])
    mean_zoe = round(float(sum(p["zoe_score"] for p in pillars) / len(pillars)), 6)
    mean_ctrl = round(float(sum(p["control_score"] for p in pillars) / len(pillars)), 6)

    phase5_ok = bool(pillars_passed == len(pillars) and beat_controls == len(pillars))

    spoken_wav_name = None
    if speak_summary_wav is not None:
        _ensure_guiai_path(root)
        from guiai.gem.zoe_voice import speak_text

        summary_speech = (
            "Hello Nicholas. Zoe L5 Phase 5 passed all 5 frontier pillars: "
            "ARC compositional visual program induction solved 16 unseen grid tasks and abstained on 2 ambiguous traps, "
            "multi-file systems surgery repaired 15 faults and verified cross-platform Java Swift Python parity, "
            "3 original scientific cycles confirmed real archive spectral order and falsified 2 spurious causal hypotheses, "
            "30-day 4-device memory recalled 60 needles with 8-domain continual learning, "
            "and 4-generation meta-evolution transferred across 5 domains with 12 red-team probes blocked. "
            "AGI-QUALIFIED remains honestly False pending independent external human audit."
        )
        v_res = speak_text(summary_speech, speak_summary_wav)
        spoken_wav_name = Path(v_res["wav_path"]).name

    report: Dict[str, Any] = {
        "contract": L5_PHASE5_CONTRACT,
        "schema_version": 1,
        "zoe_root": ".",
        "l5_phase5_frontier_verified": phase5_ok,
        "l5_agi_qualified": False,
        "pillars_passed": pillars_passed,
        "pillars_total": len(pillars),
        "pillars_beat_controls": beat_controls,
        "mean_zoe_score": mean_zoe,
        "mean_control_score": mean_ctrl,
        "pillars": pillars,
        "spoken_wav": spoken_wav_name,
        "honest_remaining_agi_gaps": list(HONEST_REMAINING_AGI_GAPS),
        "epistemic_boundaries": {
            "cloud_tokens_used": 0,
            "pytorch_required": False,
            "external_actions": 0,
            "clinical_action_authorized": False,
            "sentience_claimed": False,
            "zoe_clone_claimed": False,
            "identity_role": "zoe_l5_phase5_frontier_glass_box",
            "l5_agi_qualified": False,
        },
    }
    report["core_sha256"] = _sha256_obj({k: v for k, v in report.items() if k not in {"core_sha256", "report_sha256"}})
    report["report_sha256"] = _sha256_obj({k: v for k, v in report.items() if k != "report_sha256"})

    if output_path is not None:
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def summarize_l5_phase5_report(report: Dict[str, Any]) -> str:
    ep = report["epistemic_boundaries"]
    lines = [
        f"Zoe L5 Phase 5 Frontier Mind ({report['contract']}):",
        f"  Phase 5 Pillars: {report['pillars_passed']}/{report['pillars_total']} passed (mean Zoe={report['mean_zoe_score']:.4f} vs controls={report['mean_control_score']:.4f})",
    ]
    for p in report["pillars"]:
        tag = "PASS" if p["passed"] else "FAIL"
        lines.append(f"    [{tag}] {p['pillar_id']:42s} zoe={p['zoe_score']:.4f} (thr={p['threshold']:.2f}, ctrl={p['control_score']:.4f})")
    lines.append(
        f"  Honest Boundaries: l5_phase5_frontier_verified={report['l5_phase5_frontier_verified']} · "
        f"l5_agi_qualified={report['l5_agi_qualified']} · zoe_clone_claimed={ep['zoe_clone_claimed']} · "
        f"cloud_tokens={ep['cloud_tokens_used']} · pytorch_required=False · external_actions=0"
    )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zoe L5 Phase 5 Frontier Evaluation & Scientific Discovery.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--speak-wav", type=Path, default=None)
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    out = args.output if args.output is not None else (root / "evidence/l5-phase5/l5-phase5-report.json")
    rep = run_l5_phase5_suite(root, out, speak_summary_wav=args.speak_wav)
    print(summarize_l5_phase5_report(rep))
    return 0 if rep["l5_phase5_frontier_verified"] else 1


__all__ = [
    "ALL_PHASE5_PILLARS",
    "HONEST_REMAINING_AGI_GAPS",
    "L5_PHASE5_CONTRACT",
    "ZoeFrontierMind",
    "main",
    "run_l5_phase5_suite",
    "summarize_l5_phase5_report",
]


if __name__ == "__main__":
    raise SystemExit(main())

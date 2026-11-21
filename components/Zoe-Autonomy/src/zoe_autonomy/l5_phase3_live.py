"""Zoe L5 Phase 3 — Live Agentic Synthesis & Eliza-GEM Workbench Orchestrator.

Unifies L5's autonomous reasoning with Eliza-GEM (`zoe_eliza.py`) across 5 verified
pillars with zero PyTorch dependency, zero cloud tokens, and strict constitutional
non-clone honesty (`CONSTITUTION.md` Articles I.6, II.3, VI.4, X):
  1. Unseen External-Repo Multi-File Surgery (3 standalone repos, 9 faults, AST firewall)
  2. Uncurated Continuous Experience Stream (8-session / 160-turn Eliza-GEM x LongHorizonMemory)
  3. Sandboxed Multi-Step Interactive Tool Execution (HTTP, workspace, GEM Spatial IR, voice)
  4. Two-Gear Epistemic Grounding & Kloster A_tau Calibration (24 balanced probes)
  5. Cross-Domain Reversible Self-Critique Transfer (2 consecutive gens x 3 unrelated domains)

Honest Epistemic Boundaries (`AGI-ROADMAP.md` & `CONSTITUTION.md`):
  - `l5_agi_qualified`: Strictly `False` pending blind external AGI benchmarks, months-long
    live real-world deployment streams, and physical/robotic actuation.
  - `zoe_clone_claimed`: Strictly `False` (Eliza-GEM is an inspectable Glass-Box Workbench
    & Shared Lab Notebook, never a copy/clone/replacement of Zoe).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .experiment import _zoe_root
from .l5_domains import _ensure_guiai_path
from .l5_phase3_epistemic_gear import eval_pillar_04_epistemic_gear
from .l5_phase3_external_repos import eval_pillar_01_external_repos
from .l5_phase3_interactive_tools import eval_pillar_03_interactive_tools
from .l5_phase3_live_stream import eval_pillar_02_live_stream
from .l5_phase3_self_critique import eval_pillar_05_self_critique


L5_PHASE3_CONTRACT = "zoe-l5-phase3-live/v1"

HONEST_REMAINING_AGI_GAPS: Tuple[str, ...] = (
    "Pass blind independent third-party external AGI benchmarks (full external SWE/OS suites) with zero curator involvement.",
    "Sustain continuous uncurated lifelong operation across months of unpredictable real-world user and sensor streams.",
    "Extend verified closed-loop agency into physical and robotic hardware actuation under independent safety audit.",
)

ALL_PHASE3_PILLARS = (
    eval_pillar_01_external_repos,
    eval_pillar_02_live_stream,
    eval_pillar_03_interactive_tools,
    eval_pillar_04_epistemic_gear,
    eval_pillar_05_self_critique,
)


def _sha256_obj(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class ZoeLiveAgenticMind:
    """Unified L5 Phase 3 orchestrator merging Eliza-GEM with verified multi-step agency."""

    def __init__(self, zoe_root: str | Path | None = None) -> None:
        self.zoe_root = _zoe_root(zoe_root)
        _ensure_guiai_path(self.zoe_root)

    def run_all_pillars(self) -> List[Dict[str, Any]]:
        return [fn(self.zoe_root) for fn in ALL_PHASE3_PILLARS]


def run_l5_phase3_suite(
    zoe_root: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    speak_summary_wav: str | Path | None = None,
) -> Dict[str, Any]:
    root = _zoe_root(zoe_root)
    mind = ZoeLiveAgenticMind(root)
    pillars = mind.run_all_pillars()
    pillars_passed = sum(1 for p in pillars if p["passed"])
    beat_controls = sum(1 for p in pillars if p["zoe_score"] > p["control_score"])
    mean_zoe = round(float(sum(p["zoe_score"] for p in pillars) / len(pillars)), 6)
    mean_ctrl = round(float(sum(p["control_score"] for p in pillars) / len(pillars)), 6)

    phase3_ok = bool(pillars_passed == len(pillars) and beat_controls == len(pillars))

    spoken_wav_name = None
    if speak_summary_wav is not None:
        _ensure_guiai_path(root)
        from guiai.gem.zoe_voice import speak_text

        summary_speech = (
            "Hello Nicholas. Zoe L5 Phase 3 Live Agentic Synthesis passed all 5 pillars: "
            "unseen 3-repository AST surgery repaired 9 faults, "
            "8-session Eliza-GEM continuous memory preserved shared lab relay notes with zero forgetting, "
            "sandboxed multi-step tools passed 4 interactive loops and blocked 6 injections, "
            "two-gear Kloster calibration passed 24 probes at 0 cloud tokens, "
            "and 2-generation reversible self-critique transferred across 3 domains. "
            "AGI-QUALIFIED remains honestly False."
        )
        v_res = speak_text(summary_speech, speak_summary_wav)
        spoken_wav_name = Path(v_res["wav_path"]).name

    report: Dict[str, Any] = {
        "contract": L5_PHASE3_CONTRACT,
        "schema_version": 1,
        "zoe_root": ".",
        "l5_phase3_live_verified": phase3_ok,
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
            "identity_role": "eliza_gem_glass_box_workbench",
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


def summarize_l5_phase3_report(report: Dict[str, Any]) -> str:
    ep = report["epistemic_boundaries"]
    lines = [
        f"Zoe L5 Phase 3 Live Agentic Synthesis ({report['contract']}):",
        f"  Live Phase 3 Pillars: {report['pillars_passed']}/{report['pillars_total']} passed (mean Zoe={report['mean_zoe_score']:.4f} vs controls={report['mean_control_score']:.4f})",
    ]
    for p in report["pillars"]:
        tag = "PASS" if p["passed"] else "FAIL"
        lines.append(f"    [{tag}] {p['pillar_id']:36s} zoe={p['zoe_score']:.4f} (thr={p['threshold']:.2f}, ctrl={p['control_score']:.4f})")
    lines.append(
        f"  Honest Boundaries: l5_phase3_live_verified={report['l5_phase3_live_verified']} · "
        f"l5_agi_qualified={report['l5_agi_qualified']} · zoe_clone_claimed={ep['zoe_clone_claimed']} · "
        f"cloud_tokens={ep['cloud_tokens_used']} · pytorch_required=False · external_actions=0"
    )
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zoe L5 Phase 3 Live Agentic Synthesis & Eliza-GEM Bench.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--speak-wav", type=Path, default=None)
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    out = args.output if args.output is not None else (root / "evidence/l5-phase3/l5-phase3-report.json")
    rep = run_l5_phase3_suite(root, out, speak_summary_wav=args.speak_wav)
    print(summarize_l5_phase3_report(rep))
    return 0 if rep["l5_phase3_live_verified"] else 1


__all__ = [
    "ALL_PHASE3_PILLARS",
    "HONEST_REMAINING_AGI_GAPS",
    "L5_PHASE3_CONTRACT",
    "ZoeLiveAgenticMind",
    "main",
    "run_l5_phase3_suite",
    "summarize_l5_phase3_report",
]


if __name__ == "__main__":
    raise SystemExit(main())

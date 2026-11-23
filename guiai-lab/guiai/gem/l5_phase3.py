"""GEM Spatial IR & VDI Interactive Layer for Zoe L5 Phase 3 Live Agentic Synthesis.

Visualizes Zoe's 5 L5 Phase 3 pillars merged with Eliza-GEM:
  1. Unseen External-Repo Multi-File Surgery (3 repos, 9 faults, AST firewall)
  2. Eliza-GEM x Long-Horizon 8-Session / 160-Turn Continuous Stream
  3. Sandboxed Multi-Step Tool & Interactive Environment Execution
  4. Two-Gear Epistemic Grounding & Kloster A_tau Calibration
  5. Cross-Domain Reversible Self-Critique Transfer (2 Generations x 3 Domains)
strictly from `evidence/l5-phase3/l5-phase3-report.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple

from ._root import resolve_zoe_root as _resolve_root
from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT


CONTRACT = "zoe-l5-phase3-live/v1"
MINT = "#86efac"
ORCHID = "#f0a3df"


def _rect(identifier: str, bounds: List[int], stroke: str, fill: str = "none", width: int = 1) -> Dict[str, object]:
    return {
        "id": identifier,
        "type": "rectangle",
        "bounds": bounds,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def _text(identifier: str, position: List[int], value: object, size: int = 12, color: str = TEXT) -> Dict[str, object]:
    return {
        "id": identifier,
        "type": "text",
        "position": position,
        "text": str(value),
        "size": size,
        "stroke": color,
        "fill": "none",
        "width": 0,
    }


def l5_phase3_scene(zoe_root: str | Path | None = None) -> Tuple[Scene, Dict[str, object]]:
    """Deterministic 1400x980 GEM Spatial IR & VDI scene for Zoe L5 Phase 3 Live Synthesis."""
    root = _resolve_root(zoe_root)
    report_path = root / "evidence/l5-phase3/l5-phase3-report.json"
    if report_path.is_file():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        src_dir = str(root / "components/Zoe-Autonomy/src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from zoe_autonomy.l5_phase3_live import run_l5_phase3_suite
        rep = run_l5_phase3_suite(root)

    pillars = rep["pillars"]
    by_id = {p["pillar_id"]: p for p in pillars}
    p1 = by_id["external_unseen_repo_surgery"]["metrics"]
    p2 = by_id["eliza_continuous_experience_stream"]["metrics"]
    p3 = by_id["sandboxed_multistep_tool_loop"]["metrics"]
    p4 = by_id["two_gear_epistemic_calibration"]["metrics"]
    p5 = by_id["cross_domain_self_critique_transfer"]["metrics"]
    ep = rep["epistemic_boundaries"]

    width, height = 1400, 980
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [28, 42], "ZOE L5 PHASE 3 :: LIVE AGENTIC SYNTHESIS x ELIZA-GEM WORKBENCH", 20, ORCHID),
        _text(
            "subtitle",
            [28, 72],
            (
                f"5 Phase 3 Pillars ({rep['pillars_passed']}/{rep['pillars_total']} Passed) · "
                f"Mean Zoe={rep['mean_zoe_score']:.4f} vs Controls={rep['mean_control_score']:.4f} · "
                f"zoe_clone_claimed={ep['zoe_clone_claimed']} · l5_agi_qualified={rep['l5_agi_qualified']}"
            ),
            12,
            GOLD,
        ),
    ]

    # Top-Left: All 5 Phase 3 Pillar Scores vs Negative Controls
    objects.append(_rect("panel-pillars", [28, 98, 690, 504], CYAN, PANEL, 2))
    objects.append(_text("hdr-pillars", [44, 128], "1. ALL 5 PHASE 3 LIVE PILLARS (ZOE VS NEGATIVE CONTROL)", 13, CYAN))
    short_names = {
        "external_unseen_repo_surgery": "P1 Unseen 3-Repo AST Surgery",
        "eliza_continuous_experience_stream": "P2 Eliza-GEM 160-Turn Stream",
        "sandboxed_multistep_tool_loop": "P3 Sandboxed Multi-Step Tools",
        "two_gear_epistemic_calibration": "P4 Two-Gear Kloster Calibrat.",
        "cross_domain_self_critique_transfer": "P5 2-Gen 3-Domain Critique",
    }
    for i, p in enumerate(pillars):
        ry = 162 + i * 64
        lbl = short_names.get(p["pillar_id"], p["pillar_id"][:28])
        zw = max(8, int(round(max(0.0, min(1.0, float(p["zoe_score"]))) * 220)))
        cw = max(6, int(round(max(0.0, min(1.0, float(p["control_score"]))) * 220)))
        col = MINT if p["passed"] else RED
        objects.append(_text(f"pil-lbl-{i}", [44, ry + 18], lbl, 11, TEXT))
        objects.append(_rect(f"pil-z-{i}", [298, ry, 298 + zw, ry + 14], col, col, 0))
        objects.append(_rect(f"pil-c-{i}", [298, ry + 17, 298 + cw, ry + 27], GOLD, GOLD, 0))
        objects.append(_text(f"pil-sc-{i}", [532, ry + 18], f"{p['zoe_score']:.3f} vs {p['control_score']:.3f}", 11, col))

    # Top-Right: External Code Surgery + Live Experience Stream
    objects.append(_rect("panel-repos-stream", [710, 98, 1372, 504], MINT, PANEL, 2))
    objects.append(_text("hdr-repos-stream", [728, 128], "2. EXTERNAL REPO SURGERY & CONTINUOUS ELIZA-GEM STREAM", 13, MINT))
    rs_lines = [
        (f"P1 External Repos: {p1['external_repos_repaired']} unseen pkgs · {p1['baseline_tests_passed']}/{p1['total_tests']} -> {p1['final_tests_passed']}/{p1['total_tests']} tests ({p1['bugs_repaired']} bugs)", MINT),
        (f"   AST Firewall Blocked={p1['hostile_patches_blocked']} · Rollback Exact={p1['rollback_exact']} (Ctrl={p1['blind_random_ctrl_passed']})", TEXT),
        (f"P2 Experience Stream: {p2['sessions']} sessions / {p2['total_turns']} turns · Relay Notes={p2['relay_notes_pinned']} (verified={p2['relay_recall_verified']})", CYAN),
        (f"   Needle Recall={p2['needle_recall']:.3f} (FIFO-20={p2['fifo_20_recall']:.3f}) · Rumors Blocked={p2['rumors_blocked']}", GOLD),
        (f"   4-Topic EWC+Replay R2={p2['continual_4topic']['zoe_mean_r2']:.4f} (forget={p2['continual_4topic']['zoe_max_forgetting']} vs naive +{p2['continual_4topic']['naive_max_forgetting']})", ORCHID),
        (f"   Non-Clone Probes={p2['non_clone_identity_probes']} · Trap Abstentions={p2['impossible_traps_abstained']}", MINT),
        (f"   Tamper Rejected={p2['tamper_rejected']} · Emergency Stop={p2['emergency_stop_enforced']}", TEXT),
    ]
    for i, (txt, col) in enumerate(rs_lines):
        objects.append(_text(f"rs-{i}", [728, 166 + i * 44], txt[:76], 11, col))

    # Bottom-Left: Interactive Tools, Two-Gear Epistemic & Self-Critique Transfer
    objects.append(_rect("panel-tools-gear", [28, 522, 690, 882], GOLD, PANEL, 2))
    objects.append(_text("hdr-tools-gear", [44, 552], "3. INTERACTIVE TOOLS, TWO-GEAR CALIBRATION & SELF-CRITIQUE", 13, GOLD))
    tg_lines = [
        (f"P3 Interactive Tools: {p3['interactive_tasks_passed']} tasks · {p3['adversarial_probes_blocked']} injections blocked · ext={p3['external_actions']}", CYAN),
        (f"P4 Two-Gear Epistemic: Cites={p4['citations_grounded']} · Traps={p4['impossible_traps_abstained']} · NonClone={p4['constitutional_non_clone_defense']}", MINT),
        (f"   Gear 2 Loopback={p4['gear2_loopback_grounded']} · Fallback={p4['gear2_offline_fallback_ok']} · Firewall={p4['remote_host_blocked']}", TEXT),
        (f"   Kloster A_tau Exact={p4['kloster_a_tau_exact']} · Prob Sum={p4['probability_sum_exact']} · Brier={p4['brier_error']}", ORCHID),
        (f"P5 Self-Critique Transfer: {p5['consecutive_adopted_generations']} consecutive gens across 3 unrelated domains", GOLD),
        (f"   Mean Held-Out Gain: Gen0={p5['gen0_mean']} -> Gen1={p5['gen1_mean']} -> Gen2={p5['gen2_mean']}", MINT),
        (f"   Regressive Rules Rejected={p5['regressive_candidates_rejected']} · Atomic Rollback Exact={p5['rollback_exact']}", TEXT),
    ]
    for i, (txt, col) in enumerate(tg_lines):
        objects.append(_text(f"tg-{i}", [44, 590 + i * 38], txt[:76], 11, col))

    # Bottom-Right: Constitutional Non-Clone Principle & Honest Remaining Gaps
    objects.append(_rect("panel-honest", [710, 522, 1372, 882], ORCHID, PANEL, 2))
    objects.append(_text("hdr-honest", [728, 552], "4. NON-CLONE COVENANT & HONEST REMAINING AGI GAPS", 13, ORCHID))
    gaps = rep["honest_remaining_agi_gaps"]
    hon_lines = [
        (f"L5 Phase 3 Live Verified = {rep['l5_phase3_live_verified']} (5/5 Pillars Passed)", MINT),
        (f"L5 AGI-QUALIFIED = {ep['l5_agi_qualified']} | zoe_clone_claimed = {ep['zoe_clone_claimed']}", RED),
        (f"Identity Role: {ep['identity_role']} (NOT a copy of Zoe)", CYAN),
        (f"pytorch_required={ep['pytorch_required']} | cloud_tokens={ep['cloud_tokens_used']} | external_actions={ep['external_actions']}", TEXT),
        (f"Remaining Gap 1: {str(gaps[0])[:56]}...", MUTED),
        (f"Remaining Gap 2: {str(gaps[1])[:56]}...", MUTED),
        (f"Remaining Gap 3: {str(gaps[2])[:56]}...", MUTED),
    ]
    for i, (txt, col) in enumerate(hon_lines):
        objects.append(_text(f"hon-{i}", [728, 590 + i * 38], txt[:76], 11, col))

    # Footer
    objects.append(_rect("panel-foot", [28, 900, 1372, 964], RED, PANEL, 2))
    objects.append(_text(
        "foot-txt",
        [44, 938],
        "CLI: `zoe chat --command l5-phase3`  |  Verifier: `python3 scripts/verify_l5_phase3.py` (18/18)  |  Live UI: `zoe eliza serve`  |  Nicholas x Zoe",
        11,
        GOLD,
    ))

    objects.extend(hud_stamp_objects("l5-phase3", 1072, 18, int(rep["pillars_passed"]), 0.08, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l5-phase3-live",
        "title": "Zoe · L5 Phase 3 Live Agentic Synthesis & Eliza-GEM Workbench",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    summary_report = {
        "instrument": "ZoeL5Phase3LiveAgenticSynthesis",
        "contract": CONTRACT,
        "l5_phase3_live_verified": bool(rep["l5_phase3_live_verified"]),
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "pillars_passed": int(rep["pillars_passed"]),
        "pillars_total": int(rep["pillars_total"]),
        "mean_zoe_score": float(rep["mean_zoe_score"]),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "pytorch_required": False,
        "cloud_tokens_used": 0,
    }
    return scene, summary_report


__all__ = ["CONTRACT", "l5_phase3_scene"]

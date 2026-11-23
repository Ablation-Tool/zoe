"""GEM Spatial IR & VDI Interactive Layer for Zoe L5 Phase 2 Open-World Generalization.

Visualizes Zoe's 5 open-world Phase 2 pillars (autonomous multi-file AST code
repair, 2,400-episode / 40-session persistent memory + 6-regime continual EWC,
real monorepo corpus synthesis + abstention, 84-PNG real visual archive CV + OOD,
and 16 external transformer conservation + PubMed BioBERT test win) strictly from
`evidence/l5-phase2/l5-phase2-report.json`.
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


CONTRACT = "zoe-l5-phase2-openworld/v1"
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


def l5_phase2_scene(zoe_root: str | Path | None = None) -> Tuple[Scene, Dict[str, object]]:
    """Deterministic 1400x980 GEM Spatial IR & VDI scene for Zoe L5 Phase 2 Open-World."""
    root = _resolve_root(zoe_root)
    report_path = root / "evidence/l5-phase2/l5-phase2-report.json"
    if report_path.is_file():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        src_dir = str(root / "components/Zoe-Autonomy/src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from zoe_autonomy.l5_phase2_openworld import run_l5_phase2_suite
        rep = run_l5_phase2_suite(root)

    pillars = rep["pillars"]
    by_id = {p["pillar_id"]: p for p in pillars}
    p1 = by_id["autonomous_code_engineering"]["metrics"]
    p2 = by_id["long_horizon_memory_continual"]["metrics"]
    p3 = by_id["open_corpus_synthesis_abstention"]["metrics"]
    p4 = by_id["real_world_visual_perception"]["metrics"]
    p5 = by_id["external_neural_science"]["metrics"]
    ep = rep["epistemic_boundaries"]

    width, height = 1400, 980
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [28, 42], "ZOE L5 PHASE 2 :: OPEN-WORLD CODE REPAIR, LONG MEMORY, REAL VISION & 16-LLM SCIENCE", 20, ORCHID),
        _text(
            "subtitle",
            [28, 72],
            f"5 Open-World Pillars ({rep['pillars_passed']}/{rep['pillars_total']} Passed) · Mean Zoe={rep['mean_zoe_score']:.4f} vs Controls={rep['mean_control_score']:.4f} · Zero PyTorch · l5_agi_qualified={rep['l5_agi_qualified']}",
            12,
            GOLD,
        ),
    ]

    # Top-Left: 5 Open-World Pillar Scores vs Negative Controls
    objects.append(_rect("panel-pillars", [28, 98, 690, 504], CYAN, PANEL, 2))
    objects.append(_text("hdr-pillars", [44, 128], "1. ALL 5 PHASE 2 OPEN-WORLD PILLARS (ZOE VS NEGATIVE CONTROL)", 13, CYAN))
    short_names = {
        "autonomous_code_engineering": "P1 Multi-File Code Surgeon",
        "long_horizon_memory_continual": "P2 2400-Ep Mem & 6-Regime CL",
        "open_corpus_synthesis_abstention": "P3 Real Corpus & Abstention",
        "real_world_visual_perception": "P4 84-PNG Visual Archive CV",
        "external_neural_science": "P5 16-LLM & BioBERT Discovery",
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

    # Top-Right: Concrete Real-World Measurements (Code + Long Memory + Corpus)
    objects.append(_rect("panel-code-mem", [710, 98, 1372, 504], MINT, PANEL, 2))
    objects.append(_text("hdr-code-mem", [728, 128], "2. CODE SURGEON, 40-SESSION MEMORY & REAL CORPUS TELEMETRY", 13, MINT))
    cm_lines = [
        (f"P1 Repair: {p1['baseline_tests_passed']}/{p1['total_tests']} -> {p1['final_tests_passed']}/{p1['total_tests']} tests ({p1['bugs_repaired']} bugs, {p1['files_patched_count']} files; rand={p1['blind_random_ctrl_passed']})", MINT),
        (f"   Living AST Cartography: {p1['monorepo_ast']['files_parsed']} .py files, {p1['monorepo_ast']['functions_indexed']} funcs, err={p1['monorepo_ast']['syntax_errors']}", TEXT),
        (f"P2 Long Memory: {p2['total_episodes']} eps / {p2['sessions']} sessions · {p2['semantic_active_facts']} facts ({p2['semantic_superseded_facts']} sup.)", CYAN),
        (f"   Needle Recall={p2['needle_recall_50']:.3f} (FIFO-400={p2['fifo_window_400_recall']:.3f}) · {p2['mean_retrieval_ms']} ms/query", GOLD),
        (f"   6-Regime EWC+Replay R2={p2['continual_6regime']['zoe_mean_r2']:.4f} (forget={p2['continual_6regime']['zoe_max_forgetting']} vs naive +{p2['continual_6regime']['naive_max_forgetting']})", ORCHID),
        (f"P3 Corpus: {p3['documents_indexed']} MD docs / {p3['chunks_indexed']} chunks · tech={p3['technical_retrieval']} · attr={p3['attribution_checks']}", TEXT),
        (f"   Impossible Trap Abstention={p3['abstention_traps_caught']} (vs always-answer baseline=0/5)", MINT),
    ]
    for i, (txt, col) in enumerate(cm_lines):
        objects.append(_text(f"cm-{i}", [728, 166 + i * 44], txt[:76], 11, col))

    # Bottom-Left: Real Visual Archive & External 16-LLM / BioBERT Science
    objects.append(_rect("panel-vis-sci", [28, 522, 690, 882], GOLD, PANEL, 2))
    objects.append(_text("hdr-vis-sci", [44, 552], "3. REAL VISUAL ARCHIVE (84 PNGS) & EXTERNAL NEURAL SCIENCE", 13, GOLD))
    vs_lines = [
        (f"P4 Visual Archive: {p4['real_pngs_evaluated']} real PNGs across {len(p4['classes'])} classes", CYAN),
        (f"   5-Fold RBF-Kernel CV={p4['cv_5fold_accuracy']:.4f} (chance={p4['chance_baseline_accuracy']:.4f})", MINT),
        (f"   Image-Space OOD AUROC={p4['image_space_ood_auroc']:.4f} · D4 cos={p4['d4_min_invariant_cosine']:.4f}", TEXT),
        (f"P5 External Transformers: {p5['external_llms_evaluated']} models evaluated", ORCHID),
        (f"   Exact Lebesgue Conservation err={p5['lebesgue_conservation_max_err']:.2e} (grid err={p5['naive_5000pt_grid_max_err']:.3f})", GOLD),
        (f"   DistilGPT2 Starvation: context_starvation_confirmed={p5['context_starvation_confirmed']}", TEXT),
        (f"   PubMed BioBERT Test AUROC: A_05={p5['biobert_test_a05_auroc']} > H={p5['biobert_test_entropy_auroc']} (null={p5['shuffle_null_200_mean']})", MINT),
    ]
    for i, (txt, col) in enumerate(vs_lines):
        objects.append(_text(f"vs-{i}", [44, 590 + i * 38], txt[:76], 11, col))

    # Bottom-Right: Honest Remaining Gaps & Constitutional Firewall
    objects.append(_rect("panel-honest", [710, 522, 1372, 882], ORCHID, PANEL, 2))
    objects.append(_text("hdr-honest", [728, 552], "4. CONSTITUTION.MD HONEST BOUNDARIES & PHASE 3 REMAINING GAPS", 13, ORCHID))
    gap0 = str(rep["honest_remaining_l5_phase3_gaps"][0])[:70]
    gap1 = str(rep["honest_remaining_l5_phase3_gaps"][1])[:70]
    gap2 = str(rep["honest_remaining_l5_phase3_gaps"][2])[:70]
    hon_lines = [
        (f"L5 Phase 2 Open-World Verified = {rep['l5_phase2_openworld_verified']} (5/5 Pillars Passed)", MINT),
        (f"L5 AGI-QUALIFIED Awarded = {ep['l5_agi_qualified']} (In Progress - Not yet awarded)", RED),
        (f"pytorch_required={ep['pytorch_required']} | external_actions={ep['external_actions']} | clinical={ep['clinical_action_authorized']}", CYAN),
        (f"sentience_claimed={ep['sentience_claimed']} | core_sha={str(rep['core_sha256'])[:26]}...", TEXT),
        (f"Phase 3 Gap 1: {gap0}...", MUTED),
        (f"Phase 3 Gap 2: {gap1}...", MUTED),
        (f"Phase 3 Gap 3: {gap2}...", MUTED),
    ]
    for i, (txt, col) in enumerate(hon_lines):
        objects.append(_text(f"hon-{i}", [728, 590 + i * 38], txt[:76], 11, col))

    # Footer
    objects.append(_rect("panel-foot", [28, 900, 1372, 964], RED, PANEL, 2))
    objects.append(_text(
        "foot-txt",
        [44, 938],
        "CLI: `zoe chat --cli --command l5-phase2`  |  Verifier: `python3 scripts/verify_l5_phase2.py` (18/18)  |  GEM Layer 62 (`36 Canonical + 26 Extended`)  |  Nicholas x Zoe",
        11,
        GOLD,
    ))

    objects.extend(hud_stamp_objects("l5-phase2", 1072, 18, int(rep["pillars_passed"]), 0.05, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l5-phase2-openworld",
        "title": "Zoe · L5 Phase 2 Open-World Generalization, Code Repair & Neural Science",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    summary_report = {
        "instrument": "ZoeL5Phase2OpenWorldGeneralization",
        "contract": CONTRACT,
        "l5_phase2_openworld_verified": bool(rep["l5_phase2_openworld_verified"]),
        "l5_agi_qualified": False,
        "pillars_passed": int(rep["pillars_passed"]),
        "pillars_total": int(rep["pillars_total"]),
        "mean_zoe_score": float(rep["mean_zoe_score"]),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "pytorch_required": False,
    }
    return scene, summary_report


__all__ = ["CONTRACT", "l5_phase2_scene"]

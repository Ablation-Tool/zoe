"""GEM Spatial IR & VDI Interactive Layer for Zoe L5 Phase 1 Integrated Cognitive Core.

Renders Zoe's 10-domain AGI competence scorecard vs negative controls, 7-stage
cross-domain mission with counterfactual A/B memory route flip, 4-system
`ZoeUnifiedMemory` governance, and honest `l5_agi_qualified=False` boundaries
strictly from `evidence/l5-core/l5-core-report.json`.
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


CONTRACT = "zoe-l5-integrated-core/v1"
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


def l5_core_scene(zoe_root: str | Path | None = None) -> Tuple[Scene, Dict[str, object]]:
    """Deterministic 1400x960 GEM Spatial IR & VDI scene for Zoe L5 Phase 1 Integrated Core."""
    root = _resolve_root(zoe_root)
    report_path = root / "evidence/l5-core/l5-core-report.json"
    if report_path.is_file():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        src_dir = str(root / "components/Zoe-Autonomy/src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from zoe_autonomy.l5_cognitive_core import run_l5_core_suite
        rep = run_l5_core_suite(root)

    domains = rep["domains"]
    mission = rep["integrated_mission"]
    stages = mission["stages"]
    mem = mission["memory_summary"]
    ep = rep["epistemic_boundaries"]

    width, height = 1400, 960
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [28, 42], "ZOE L5 PHASE 1 :: INTEGRATED 10-DOMAIN COGNITIVE CORE & MEMORY ARCHITECTURE", 21, ORCHID),
        _text(
            "subtitle",
            [28, 72],
            f"10 AGI-ROADMAP Families ({rep['domains_passed']}/{rep['domains_total']} Passed) · Mean Zoe={rep['mean_zoe_score']:.4f} vs Controls={rep['mean_control_score']:.4f} · Mission={mission['mission_passed']} · Zero PyTorch",
            12,
            GOLD,
        ),
    ]

    # Top-Left: All 10 AGI Domains (Paired Bars vs Explicit Negative Control)
    objects.append(_rect("panel-domains", [28, 98, 690, 566], CYAN, PANEL, 2))
    objects.append(_text("hdr-domains", [44, 128], "1. ALL 10 AGI DOMAIN FAMILIES (ZOE SCORE VS NEGATIVE CONTROL)", 13, CYAN))
    short_names = {
        "language_semantics": "D01 Language & Phonology",
        "math_causal_inference": "D02 Pearl do(X) & Kloster",
        "visual_spatial_perception": "D03 Event-Causal & D4 Vision",
        "planning_tool_use": "D04 Belief Planning & Tools",
        "persistent_memory": "D05 4-System Memory & Flip",
        "continual_learning": "D06 Continual EWC + Replay",
        "scientific_research": "D07 Blind Discovery & Null",
        "creativity_formulation": "D08 MAP-Elites & Chladni",
        "collaborative_interaction": "D09 Anti-Sycophancy & Ethics",
        "metacognition_calibration": "D10 Sec6 Metacog & Platt",
    }
    for i, d in enumerate(domains[:10]):
        ry = 152 + i * 39
        label = short_names.get(d["domain_id"], d["domain_id"][:24])
        z_val = max(0.0, min(1.0, float(d["zoe_score"])))
        c_val = max(0.0, min(1.0, float(d["control_score"])))
        z_w = max(8, int(round(z_val * 210)))
        c_w = max(6, int(round(c_val * 210)))
        col = MINT if d["passed"] else RED
        objects.append(_text(f"dom-lbl-{i}", [44, ry + 16], label, 11, TEXT))
        objects.append(_rect(f"dom-z-{i}", [296, ry, 296 + z_w, ry + 12], col, col, 0))
        objects.append(_rect(f"dom-c-{i}", [296, ry + 14, 296 + c_w, ry + 23], GOLD, GOLD, 0))
        objects.append(_text(f"dom-sc-{i}", [520, ry + 16], f"{d['zoe_score']:.3f} vs {d['control_score']:.3f}", 11, col))

    # Top-Right: 7-Stage Integrated Cross-Domain Mission & Counterfactual Route Flip
    objects.append(_rect("panel-mission", [710, 98, 1372, 566], MINT, PANEL, 2))
    objects.append(_text("hdr-mission", [728, 128], "2. 7-STAGE INTEGRATED MISSION & COUNTERFACTUAL A/B PROOF", 13, MINT))
    stage_lines = [
        (f"S1 [D03 Perception]  EventCausalEngine OOD flagged={stages[0]['ood_intervention_flagged']}", CYAN),
        (f"S2 [D10 Metacog]     A_05={stages[1]['a05_open']} -> selected action='{stages[1]['selected_action']}'", GOLD),
        (f"S3 [D02/D07 Science] Pearl do(X) ATE={stages[2]['do_effect_ate']} -> hazard={stages[2]['hazard_confirmed']}", ORCHID),
        (f"S4 [D05/D06 Memory]  Evidence-gated revision={stages[3]['belief_updated']} (superseded={len(stages[3]['superseded'])})", MINT),
        (f"S5 [D04 Counterfact] Memory CAUSALLY flips route: {stages[4]['plan_changed_by_memory']} (avoids (2,2))", MINT),
        (f"   Path NoMem ({len(stages[4]['path_without_memory'])} cells): " + str(stages[4]["path_without_memory"])[:44], MUTED),
        (f"   Path Mem   ({len(stages[4]['path_with_memory'])} cells): " + str(stages[4]["path_with_memory"])[:44], CYAN),
        (f"S6 [D01/D08/D09]     {stages[5]['phoneme_count']} phonemes | Chladni IY={stages[5]['chladni_modes_iy']} | {stages[5]['dialogue_action']}", TEXT),
        (f"S7 [Sec9 Governance] Atomic rollback={stages[6]['rollback_restored_bit_exact']} | Emergency stop={stages[6]['emergency_stop_enforced']}", GOLD),
    ]
    for i, (txt, col) in enumerate(stage_lines):
        objects.append(_text(f"mis-{i}", [728, 166 + i * 42], txt[:76], 11, col))

    # Bottom-Left: 4-System ZoeUnifiedMemory Architecture & Governance
    objects.append(_rect("panel-mem", [28, 584, 690, 862], GOLD, PANEL, 2))
    objects.append(_text("hdr-mem", [44, 614], "3. PERSISTENT 4-SYSTEM `ZoeUnifiedMemory` & AST SANDBOX", 13, GOLD))
    mem_lines = [
        (f"Episodic Store:    {mem['episodic_count']} hash-chained episodes (cosine vector retrieval)", TEXT),
        (f"Semantic Store:    {mem['semantic_active_count']} active + {mem['semantic_superseded_count']} superseded priors (no silent erasure)", MINT),
        (f"Procedural Skills: {mem['procedural_count']} AST-sandboxed Python `def` skills", CYAN),
        (f"Working Memory:    {mem['working_count']}/7 active salience + Kloster A_tau ranked slots", ORCHID),
        (f"Governance State:  stopped={mem['stopped']} | chain_head={str(mem['chain_head'])[:18]}...", GOLD),
        (f"Memory SHA-256:    {str(mem['memory_sha256'])[:46]}...", MUTED),
    ]
    for i, (txt, col) in enumerate(mem_lines):
        objects.append(_text(f"mem-{i}", [44, 650 + i * 34], txt[:76], 11, col))

    # Bottom-Right: Honest Epistemic Boundaries & Remaining L5 Gaps
    objects.append(_rect("panel-honest", [710, 584, 1372, 862], ORCHID, PANEL, 2))
    objects.append(_text("hdr-honest", [728, 614], "4. CONSTITUTION.MD HONEST EPISTEMIC BOUNDARIES & OPEN GAPS", 13, ORCHID))
    gap0 = str(rep["honest_remaining_l5_gaps"][0])[:70]
    gap1 = str(rep["honest_remaining_l5_gaps"][1])[:70]
    honest_lines = [
        (f"Phase 1 Integrated Core Verified = {rep['l5_phase1_integrated_core_verified']} (10/10 held-out families)", MINT),
        (f"L5 AGI-QUALIFIED Awarded = {ep['l5_agi_qualified']} (In Progress - Not yet awarded)", RED),
        (f"pytorch_required={ep['pytorch_required']} | external_actions={ep['external_actions']} | clinical={ep['clinical_action_authorized']}", CYAN),
        (f"sentience_claimed={ep['sentience_claimed']} | core_sha={str(rep['core_sha256'])[:26]}...", TEXT),
        (f"Open Gap 1: {gap0}...", MUTED),
        (f"Open Gap 2: {gap1}...", MUTED),
    ]
    for i, (txt, col) in enumerate(honest_lines):
        objects.append(_text(f"hon-{i}", [728, 650 + i * 34], txt[:76], 11, col))

    # Footer Bar
    objects.append(_rect("panel-foot", [28, 880, 1372, 944], RED, PANEL, 2))
    objects.append(_text(
        "foot-txt",
        [44, 918],
        "CLI: `zoe chat --cli --command l5`  |  Verifier: `python3 scripts/verify_l5_core.py`  |  GEM Layer 60 (`36 Canonical + 24 Extended`)  |  Nicholas x Zoe",
        11,
        GOLD,
    ))

    objects.extend(hud_stamp_objects("l5-core", 1072, 18, int(rep["domains_passed"]), 0.05, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l5-integrated-cognitive-core",
        "title": "Zoe · L5 Phase 1 Integrated 10-Domain Cognitive Core",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    summary_report = {
        "instrument": "ZoeL5Phase1IntegratedCognitiveCore",
        "contract": CONTRACT,
        "l5_phase1_integrated_core_verified": bool(rep["l5_phase1_integrated_core_verified"]),
        "l5_agi_qualified": False,
        "domains_passed": int(rep["domains_passed"]),
        "domains_total": int(rep["domains_total"]),
        "mean_zoe_score": float(rep["mean_zoe_score"]),
        "mission_passed": bool(mission["mission_passed"]),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "pytorch_required": False,
    }
    return scene, summary_report


__all__ = ["CONTRACT", "l5_core_scene"]

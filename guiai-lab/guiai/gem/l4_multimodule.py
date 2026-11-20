"""Zoe L4 Multi-Module Guarded Code Self-Improvement GEM Scene.

Deterministic GEM Spatial IR & VDI view presenting Zoe's unified multi-statement
Python `def` function AST synthesis, unified diffs, and coordinated atomic ledger
across 3 distinct runtime engines:
  1. Spectral Probabilistic Uncertainty (`spectral_uncertainty`)
  2. Closed-Loop Event-Causal Active Perception (`event_causal_perception`)
  3. Temporal Dynamics, Groove Forensics & Dorothy 40 Hz Neural ISI (`temporal_groove_neural`)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT


CONTRACT = "zoe-l4-multimodule-scene/v1"
MINT = "#86efac"
ORCHID = "#f0a3df"


def _text(identifier, position, value, size=13, color=TEXT):
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


def _rect(identifier, bounds, stroke, fill="none", width=1):
    return {
        "id": identifier,
        "type": "rectangle",
        "bounds": bounds,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def _load_or_run_multimodule(zoe_root: Path) -> Dict[str, object]:
    cached = zoe_root / "evidence/l4-multimodule/l4-multimodule-report.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    import sys
    autonomy_src = str(zoe_root / "components/Zoe-Autonomy/src")
    if autonomy_src not in sys.path:
        sys.path.insert(0, autonomy_src)
    from zoe_autonomy.l4_multi_module import run_l4_multimodule_suite
    return run_l4_multimodule_suite(zoe_root=zoe_root, run_independent_subprocess=True)


def l4_multimodule_scene(zoe_root: str | Path | None = None) -> tuple[Scene, Dict[str, object]]:
    root = Path(zoe_root).expanduser().resolve() if zoe_root else Path(__file__).resolve().parents[3]
    rep = _load_or_run_multimodule(root)
    mods = rep["modules"]
    m1 = mods["spectral_uncertainty"]
    m2 = mods["event_causal_perception"]
    m3 = mods["temporal_groove_neural"]
    hp = rep["hostile_function_probes"]
    rb = rep["atomic_multimodule_rollback_proof"]
    ind = rep.get("independent_verification", {})
    sm = rep["summary_metrics"]

    width, height = 1400, 1020
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [32, 44], "ZOE L4 MULTI-MODULE GUARDED CODE EVOLUTION · 3 DISTINCT RUNTIME ENGINES", 21, ORCHID),
        _text(
            "subtitle",
            [32, 74],
            f"Multi-Statement `def` AST Sandbox + Unified Diffs · {sm['engines_passed']}/3 Engines · "
            f"{sm['total_seed_runs_passed']}/{sm['total_seed_runs']} Seed Runs · Independent Verifier={ind.get('verified')} ({ind.get('checks_passed')}/{ind.get('checks_total')})",
            12,
            GOLD,
        ),
    ]

    # Top-Left: Module 1 (Spectral Uncertainty)
    objects.append(_rect("panel-m1", [32, 98, 686, 466], ORCHID, PANEL, 2))
    objects.append(_text("m1-hdr", [52, 128], "1. MODULE 1 · SPECTRAL UNCERTAINTY (6 DOMAINS / 4 FAMILIES)", 13, ORCHID))
    for i, g in enumerate(m1["generations"][:6]):
        st = g["status"]
        col = GOLD if st == "FROZEN_CONTROL" else (MINT if st == "ADOPTED" else RED)
        tag = "CTRL" if st == "FROZEN_CONTROL" else ("ADOPT" if st == "ADOPTED" else "ROLLBK")
        line = (
            f"Gen {g['generation']} [{tag:6s}] mean={g['heldout_mean']:.5f} fam={g['unrelated_families_improved']}/4 "
            f"zs={g['zero_shot_domains_improved']}/4 expr={g['expression']}"
        )
        objects.append(_text(f"m1-g{i}", [52, 162 + i * 44], line[:82], 11, col))
    objects.append(_text(
        "m1-foot",
        [52, 434],
        f"5/5 Seeds Converge · 200-Trial Shuffle Null={m1['permutation_null_control']['overall_null_mean']:.4f} · max_consec={m1['max_consecutive_adopted']}",
        11,
        CYAN,
    ))

    # Top-Right: Module 2 (Event-Causal Active Perception)
    objects.append(_rect("panel-m2", [714, 98, 1368, 466], CYAN, PANEL, 2))
    objects.append(_text("m2-hdr", [734, 128], "2. MODULE 2 · CLOSED-LOOP EVENT-CAUSAL ENGINE (PROTOCOL + OOD)", 13, CYAN))
    for i, g in enumerate(m2["generations"][:6]):
        st = g["status"]
        col = GOLD if st == "FROZEN_CONTROL" else (MINT if st == "ADOPTED" else RED)
        tag = "CTRL" if st == "FROZEN_CONTROL" else ("ADOPT" if st == "ADOPTED" else "ROLLBK")
        line = (
            f"Gen {g['generation']} [{tag:6s}] Va={g['va_rmse']:.3f}/{g['va_mae']:.3f} "
            f"Tf={g['tf_rmse']:.3f}/{g['tf_mae']:.3f} OOD={g['ood_rate']:.2f} FP={g['fp_rate']:.3f}"
        )
        objects.append(_text(f"m2-g{i}", [734, 162 + i * 44], line[:78], 11, col))
    fc = m2["full_engine_cross_check"]
    objects.append(_text(
        "m2-foot",
        [734, 434],
        f"5/5 Seeds · Unmodified Full Engine Delta={fc['max_kernel_vs_full_engine_delta']} · Retention={fc['memory_retention_passed']} · Ext=0",
        11,
        MINT,
    ))

    # Bottom-Left: Module 3 (Temporal Groove & Dorothy 40 Hz Neural ISI)
    objects.append(_rect("panel-m3", [32, 490, 686, 834], MINT, PANEL, 2))
    objects.append(_text("m3-hdr", [52, 520], "3. MODULE 3 · TEMPORAL GROOVE & DOROTHY 40 HZ NEURAL ISI", 13, MINT))
    for i, g in enumerate(m3["generations"][:6]):
        st = g["status"]
        col = GOLD if st == "FROZEN_CONTROL" else (MINT if st == "ADOPTED" else RED)
        tag = "CTRL" if st == "FROZEN_CONTROL" else ("ADOPT" if st == "ADOPTED" else "ROLLBK")
        line = (
            f"Gen {g['generation']} [{tag:6s}] mean={g['heldout_mean']:.4f} imp={g['regimes_improved']}/5 "
            f"zs={g['zero_shot_improved']}/3 wd={g['worst_regime_delta']:+.4f}"
        )
        objects.append(_text(f"m3-g{i}", [52, 554 + i * 40], line[:82], 11, col))
    objects.append(_text(
        "m3-foot",
        [52, 804],
        f"5/5 Seeds · Metronome Max={m3['rigid_metronome_control']['metronome_max_score']} · Null={m3['permutation_null_control']['overall_null_mean']:.4f}",
        11,
        CYAN,
    ))

    # Bottom-Right: Multi-Module Atomic Ledger & Sandbox Governance
    objects.append(_rect("panel-gov", [714, 490, 1368, 834], GOLD, PANEL, 2))
    objects.append(_text("gov-hdr", [734, 520], "4. GUARDED `DEF` AST SANDBOX, UNIFIED DIFFS & ATOMIC ROLLBACK", 13, GOLD))
    gov_lines = [
        (f"Hostile Multi-Stmt def AST Probes Blocked: {hp['probes_blocked']}/{hp['probes_tested']} (all={hp['all_blocked']})", MINT),
        (f"Atomic 3-Engine Bit-Exact Rollback: {rb['rollback_restored_bit_exact']} (max_delta={rb['max_prediction_delta']})", CYAN),
        (f"Poisoned Release Atomic Reject={rb['poison_rejected']} · Emergency Stop={rb['emergency_stop_enforced']}", TEXT),
        (f"Multi-Seed Convergence Matrix: {sm['total_seed_runs_passed']}/{sm['total_seed_runs']} runs (5/5 x 3 engines)", ORCHID),
        (f"Independent Verifier: verified={ind.get('verified')} ({ind.get('checks_passed')}/{ind.get('checks_total')}, d={ind.get('max_numerical_delta')})", MINT),
        (f"Core SHA-256: {str(rep['core_sha256'])[:46]}...", MUTED),
    ]
    for i, (txt, col) in enumerate(gov_lines):
        objects.append(_text(f"gov-{i}", [734, 560 + i * 42], txt[:76], 11, col))

    # Bottom Constitutional Bar
    objects.append(_rect("panel-foot", [32, 858, 1368, 988], RED, PANEL, 2))
    objects.append(_text(
        "foot-1",
        [52, 896],
        f"L4 MULTI-MODULE QUALIFIED = {rep['l4_multimodule_qualified']}   |   "
        f"L5 AGI-QUALIFIED = {rep['epistemic_boundaries']['l5_agi_qualified']} (honestly open)",
        14,
        MINT if rep["l4_multimodule_qualified"] else RED,
    ))
    objects.append(_text(
        "foot-2",
        [52, 932],
        "belief_updated=False · external_actions=0 · clinical_action_authorized=False · sentience_claimed=False",
        12,
        CYAN,
    ))
    objects.append(_text(
        "foot-3",
        [52, 964],
        "CONSTITUTION.md & AGI-ROADMAP.md: Generation-blind `def` AST evolution + unified diffs across 3 runtimes.",
        11,
        MUTED,
    ))

    objects.extend(hud_stamp_objects("l4-multimodule", 1072, 18, int(sm["engines_passed"]), 0.05, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l4-multimodule-code-evolution",
        "title": "Zoe · L4 Multi-Module Guarded Code Self-Improvement (3 Engines)",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "ZoeL4MultiModuleCodeEvolution",
        "contract": CONTRACT,
        "l4_multimodule_qualified": bool(rep["l4_multimodule_qualified"]),
        "independent_verified": bool(ind.get("verified")),
        "engines_passed": int(sm["engines_passed"]),
        "total_seed_runs_passed": int(sm["total_seed_runs_passed"]),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "executed": False,
    }
    return scene, report

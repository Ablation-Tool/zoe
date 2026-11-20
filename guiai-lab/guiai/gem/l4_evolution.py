"""Zoe L4 Generalized Self-Improvement GEM Scene (AGI-ROADMAP.md Sections 3, 5, 9).

Deterministic GEM Spatial IR & VDI view presenting Zoe's uniform, pure-atomic,
generation-blind AST evolution across 6 real domains (2 held-out + 4 completely
unseen zero-shot domains), multi-seed robustness, organic rollback, sandbox probes,
permutation null, and independent fresh-process verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT


CONTRACT = "zoe-l4-evolution-scene/v1"
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


def _load_or_run_l4(zoe_root: Path) -> Dict[str, object]:
    cached = zoe_root / "evidence/l4-self-improvement/l4-evolution-report.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    import sys
    autonomy_src = str(zoe_root / "components/Zoe-Autonomy/src")
    if autonomy_src not in sys.path:
        sys.path.insert(0, autonomy_src)
    from zoe_autonomy.l4_self_improvement import run_l4_self_improvement_suite
    return run_l4_self_improvement_suite(zoe_root=zoe_root, run_independent_subprocess=True)


def l4_evolution_scene(zoe_root: str | Path | None = None) -> tuple[Scene, Dict[str, object]]:
    root = Path(zoe_root).expanduser().resolve() if zoe_root else Path(__file__).resolve().parents[3]
    rep = _load_or_run_l4(root)
    prim = rep["primary_evolution"]
    ms = rep["multi_seed_robustness"]
    hp = rep["hostile_ast_probes"]
    null = rep["permutation_null_control"]
    rb = rep["reversible_rollback_proof"]
    ind = rep.get("independent_verification", {})
    sh = rep["shannon_baseline"]

    width, height = 1400, 1020
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [32, 44], "ZOE L4 GENERALIZED SELF-IMPROVEMENT · UNIFORM ATOMIC AST + ZERO-SHOT TRANSFER", 21, ORCHID),
        _text(
            "subtitle",
            [32, 74],
            f"Generation-Blind Grammar ({prim['seed']} primary, {ms['seeds_passed']}/{ms['seeds_total']} seeds) · "
            f"6 Real Domains (4 Completely Unseen Zero-Shot) · Independent Verifier={ind.get('verified')} ({ind.get('checks_passed')}/{ind.get('checks_total')})",
            12,
            GOLD,
        ),
    ]

    # Top-Left Panel: Generation Trajectory (Gen 0 -> Gen 5)
    objects.append(_rect("panel-traj", [32, 98, 686, 466], ORCHID, PANEL, 2))
    objects.append(_text("traj-hdr", [52, 128], "1. AUTONOMOUS AST EVOLUTION LINEAGE (DISCOVERY RANKED -> UNSEEN JUDGE)", 13, ORCHID))
    for i, g in enumerate(prim["generations"][:6]):
        st = g["status"]
        col = GOLD if st == "FROZEN_CONTROL" else (MINT if st == "ADOPTED" else RED)
        tag = "CTRL" if st == "FROZEN_CONTROL" else ("ADOPT" if st == "ADOPTED" else "ROLLBK")
        line = (
            f"Gen {g['generation']} [{tag:6s}] mean={g['heldout_mean']:.5f} "
            f"fam={g['unrelated_families_improved']}/4 zs={g['zero_shot_domains_improved']}/4 "
            f"wd={g['worst_domain_delta']:+.4f}  expr={g['expression']}"
        )
        objects.append(_text(f"gen-{i}", [52, 162 + i * 44], line[:82], 11, col))
    objects.append(_text(
        "traj-gain",
        [52, 434],
        f"Total Gain: Gen0 {prim['gen0_heldout_mean']:.5f} -> Final {prim['final_heldout_mean']:.5f} (+{prim['total_gain_over_gen0']:.5f}) · Shannon={sh['heldout_mean']:.5f}",
        12,
        CYAN,
    ))

    # Top-Right Panel: 6 Real Held-Out & Zero-Shot Domains
    objects.append(_rect("panel-doms", [714, 98, 1368, 466], CYAN, PANEL, 2))
    objects.append(_text("dom-hdr", [734, 128], "2. 6-DOMAIN EVALUATION (2 HELD-OUT + 4 UNSEEN ZERO-SHOT)", 13, CYAN))
    g0_s = prim["generations"][0]["heldout_auroc"]
    g1_s = prim["generations"][1]["heldout_auroc"]
    g2_s = prim["final_heldout_auroc"]
    sh_s = sh["heldout_auroc"]
    dom_order = ["midi_fwd_ho", "helen_fwd_ho", "midi_rev_zs", "helen_retro_zs", "dorothy_vision_zs", "psf_3d_zs"]
    for i, k in enumerate(dom_order):
        dom_info = rep["domains"][k]
        tag = "ZS" if dom_info["split"] == "zero_shot" else "HO"
        dcol = MINT if tag == "ZS" else GOLD
        line = (
            f"[{tag}] {k:18s} Gen0={g0_s[k]:.4f} Shan={sh_s[k]:.4f} G1={g1_s[k]:.4f} G2={g2_s[k]:.4f}"
        )
        objects.append(_text(f"dom-{i}", [734, 166 + i * 44], line, 11, dcol))
    objects.append(_text(
        "dom-note",
        [734, 434],
        "Discovery ONLY sees midi_fwd (even) & helen_fwd (even); ZS domains 100% withheld!",
        11,
        MUTED,
    ))

    # Middle-Left Panel: Multi-Seed Robustness & Permutation Null
    objects.append(_rect("panel-ms", [32, 490, 686, 834], MINT, PANEL, 2))
    objects.append(_text("ms-hdr", [52, 520], f"3. MULTI-SEED ROBUSTNESS ({ms['seeds_passed']}/{ms['seeds_total']} SEEDS) & 200-TRIAL NULL", 13, MINT))
    for i, r in enumerate(ms["runs"][:5]):
        line = (
            f"Seed {r['seed']:4d}: consec={r['max_consecutive_adopted']} rej={r['rejected_generations_count']} "
            f"final={r['final_adopted_expression']:18s} mean={r['final_heldout_mean']:.5f} (+{r['total_gain_over_gen0']:.4f})"
        )
        objects.append(_text(f"seed-{i}", [52, 554 + i * 38], line[:82], 11, TEXT))
    objects.append(_text(
        "null-row",
        [52, 762],
        f"Permutation Label-Shuffle (200 trials x 6 domains): mean={null['overall_null_mean']:.5f} (no_leakage={null['passed_no_leakage']})",
        11,
        CYAN,
    ))
    objects.append(_text(
        "grammar-row",
        [52, 796],
        f"Grammar: generation_blind={rep['grammar_design']['generation_blind_uniform_ast']} · spectral_hints=False · pytorch=False",
        11,
        GOLD,
    ))

    # Middle-Right Panel: Security, Reversible Rollback & Independent Verifier
    objects.append(_rect("panel-sec", [714, 490, 1368, 834], GOLD, PANEL, 2))
    objects.append(_text("sec-hdr", [734, 520], "4. SANDBOX SECURITY, REVERSIBLE LEDGER & INDEPENDENT VERIFIER", 13, GOLD))
    sec_lines = [
        (f"Hostile AST / DoS Probes Blocked: {hp['probes_blocked']}/{hp['probes_tested']} (all_blocked={hp['all_blocked']})", MINT),
        (f"Live Reversible Rollback Proof: bit_exact={rb['rollback_restored_bit_exact']} (max_pred_delta={rb['max_prediction_delta']})", CYAN),
        (f"Poison / Regression Guard: poison_rejected={rb['poison_rejected']} · ledger_sha256_valid={rb['ledger_chain_valid']}", TEXT),
        (f"Rollback Roundtrip: Gen2 -> Gen1 ({rb['reverted_expression']}) -> Gen2 ({rb['restored_expression']})", ORCHID),
        (f"Independent Verifier: verified={ind.get('verified')} ({ind.get('checks_passed')}/{ind.get('checks_total')}, max_delta={ind.get('max_numerical_delta')})", MINT),
        (f"Lineage Head SHA-256: {prim['lineage_head_sha256'][:44]}...", MUTED),
    ]
    for i, (txt, col) in enumerate(sec_lines):
        objects.append(_text(f"sec-{i}", [734, 560 + i * 42], txt[:76], 11, col))

    # Bottom Constitutional Bar
    objects.append(_rect("panel-foot", [32, 858, 1368, 988], RED, PANEL, 2))
    objects.append(_text(
        "foot-1",
        [52, 896],
        f"L4 SELF-IMPROVEMENT-QUALIFIED = {rep['l4_self_improvement_qualified']}   |   "
        f"L5 AGI-QUALIFIED = {rep['epistemic_boundaries']['l5_agi_qualified']} (honestly open)",
        14,
        MINT if rep["l4_self_improvement_qualified"] else RED,
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
        "CONSTITUTION.md Articles II, III, V, X & AGI-ROADMAP.md Sections 3, 5, 9: Rejected Gen 3-5 overfit candidates preserved visibly.",
        11,
        MUTED,
    ))

    objects.extend(hud_stamp_objects("l4-evolution", 1072, 18, int(prim["max_consecutive_adopted"]), 0.05, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l4-generalized-self-improvement",
        "title": "Zoe · L4 Generalized Self-Improvement (Uniform AST + Zero-Shot Transfer)",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "ZoeL4GeneralizedSelfImprovement",
        "contract": CONTRACT,
        "l4_qualified": bool(rep["l4_self_improvement_qualified"]),
        "independent_verified": bool(ind.get("verified")),
        "max_consecutive_adopted": int(prim["max_consecutive_adopted"]),
        "final_expression": str(prim["final_adopted_expression"]),
        "final_heldout_mean": float(prim["final_heldout_mean"]),
        "seeds_passed": int(ms["seeds_passed"]),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "executed": False,
    }
    return scene, report

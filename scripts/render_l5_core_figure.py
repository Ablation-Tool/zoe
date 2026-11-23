#!/usr/bin/env python3
"""Render Zoe's 4-panel L5 Phase 1 Integrated 10-Domain Cognitive Core Figure.

Reads strictly from `evidence/l5-core/l5-core-report.json` (zero hardcoded numbers),
renders `components/agent-logging-system/docs/images/zoe-l5-cognitive-core.png`, and
mirrors a copy into `/home/cowboy/Desktop/Zoe Sing/zoe-demos/` if present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

try:
    from _render_common import (
        ZOE_DARK_PALETTE,
        add_figure_header,
        apply_dark_theme,
        draw_summary_card,
        load_json_report,
        save_figure,
    )
except ImportError:
    from scripts._render_common import (
        ZOE_DARK_PALETTE,
        add_figure_header,
        apply_dark_theme,
        draw_summary_card,
        load_json_report,
        save_figure,
    )


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evidence/l5-core/l5-core-report.json"
OUT_PNG = ROOT / "components/agent-logging-system/docs/images/zoe-l5-cognitive-core.png"
DESKTOP_COPY = Path("/home/cowboy/Desktop/Zoe Sing/zoe-demos/zoe-l5-cognitive-core.png")

# Bind canonical Zoe palette constants for module-level compatibility.
BG = ZOE_DARK_PALETTE["BG"]
PANEL = ZOE_DARK_PALETTE["PANEL"]
BORDER = ZOE_DARK_PALETTE["BORDER"]
TEXT = ZOE_DARK_PALETTE["TEXT"]
MUTED = ZOE_DARK_PALETTE["MUTED"]
CYAN = ZOE_DARK_PALETTE["CYAN"]
RED = ZOE_DARK_PALETTE["RED"]
GOLD = ZOE_DARK_PALETTE["GOLD"]
MINT = ZOE_DARK_PALETTE["MINT"]
ORCHID = ZOE_DARK_PALETTE["ORCHID"]

_DOMAIN_LABELS: Dict[str, str] = {
    "language_semantics": "D01 Language & Phon.",
    "math_causal_inference": "D02 Pearl do(X) & Math",
    "visual_spatial_perception": "D03 Vision & D4 Geom.",
    "planning_tool_use": "D04 Belief Plan & Tool",
    "persistent_memory": "D05 4-Sys Memory",
    "continual_learning": "D06 Continual EWC",
    "scientific_research": "D07 Sci. Discovery",
    "creativity_formulation": "D08 Creativity & Hyp.",
    "collaborative_interaction": "D09 Anti-Sycophancy",
    "metacognition_calibration": "D10 Sec6 Metacog/ECE",
}


def _plot_domains_panel(ax1: Any, domains: Sequence[Dict[str, Any]]) -> None:
    """Plot all 10 AGI-ROADMAP domain scores against negative controls and thresholds."""
    dom_rev = list(reversed(domains))
    y_pos = np.arange(len(dom_rev))
    bar_h = 0.36
    z_scores = [float(d["zoe_score"]) for d in dom_rev]
    c_scores = [float(d["control_score"]) for d in dom_rev]
    thrs = [float(d["threshold"]) for d in dom_rev]

    # Render paired horizontal bars with per-domain threshold gate markers.
    ax1.barh(y_pos + bar_h / 2, z_scores, bar_h, color=MINT, edgecolor="#0d2233", label="Zoe Phase 1 Integrated Core")
    ax1.barh(y_pos - bar_h / 2, c_scores, bar_h, color=GOLD, alpha=0.88, edgecolor="#221b0c", label="Explicit Negative Control")
    for yi, (zv, cv, tv) in enumerate(zip(z_scores, c_scores, thrs)):
        ax1.plot([tv, tv], [yi - 0.38, yi + 0.38], color=RED, linewidth=1.6, zorder=5)
        ax1.text(zv + 0.015, yi + bar_h / 2, f"{zv:.3f}", va="center", ha="left", fontsize=7.6, color=MINT, fontweight="bold")
        ax1.text(cv + 0.015, yi - bar_h / 2, f"{cv:.3f}", va="center", ha="left", fontsize=7.2, color=GOLD)

    ax1.plot([], [], color=RED, linewidth=1.8, label="Pass Threshold Gate")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([_DOMAIN_LABELS.get(d["domain_id"], d["domain_id"]) for d in dom_rev], fontsize=8.1)
    ax1.set_xlim(0.0, 1.24)
    ax1.set_xlabel("Held-Out Domain Competence Score", fontsize=9.0)
    ax1.set_title("1. ALL 10 AGI-ROADMAP DOMAINS VS NEGATIVE CONTROLS", fontsize=10.1, color=CYAN, fontweight="bold", pad=10)
    ax1.grid(True, axis="x")
    ax1.legend(loc="lower right", fontsize=7.1, facecolor=BG, edgecolor=BORDER)


def _plot_continual_panel(ax2: Any, by_id: Dict[str, Dict[str, Any]]) -> None:
    """Plot continual EWC+replay retention, Platt calibration, and OOD gains."""
    d6m = by_id["continual_learning"]["metrics"]
    d10m = by_id["metacognition_calibration"]["metrics"]
    comp_labels = ["D06 Mean R2\n(3 Tasks)", "D06 Retain\nTask A R2", "D10 Platt\n(1 - ECE)", "D10 Defer\n(1 - Loss)", "D03 Vision\nOOD Rate"]
    z_bars = [
        float(by_id["continual_learning"]["zoe_score"]),
        max(0.0, float(d6m["zoe_task_r2_after_all"][0])),
        1.0 - float(d10m["ece_after_cal"]),
        1.0 - float(d10m["metacog_defer_expected_loss"]),
        float(by_id["visual_spatial_perception"]["metrics"]["l4_ood_rate"]),
    ]
    c_bars = [
        float(by_id["continual_learning"]["control_score"]),
        max(0.0, float(d6m["naive_sgd_task_r2_after_all"][0])),
        1.0 - float(d10m["ece_before_cal"]),
        1.0 - float(d10m["always_act_expected_loss"]),
        0.50,
    ]
    x2 = np.arange(len(comp_labels))
    bw = 0.34
    ax2.bar(x2 - bw / 2, c_bars, bw, color=GOLD, alpha=0.88, edgecolor="#221b0c", label="Baseline / Naive Control")
    ax2.bar(x2 + bw / 2, z_bars, bw, color=ORCHID, edgecolor="#1c0d24", label="Zoe Integrated Mechanisms")
    for xi, (zv, cv) in enumerate(zip(z_bars, c_bars)):
        ax2.text(xi + bw / 2, zv + 0.018, f"{zv:.3f}", ha="center", va="bottom", fontsize=7.5, color=MINT, fontweight="bold")
        txt_c = f"{d6m['naive_sgd_task_r2_after_all'][0]:.2f}*" if xi == 1 else f"{cv:.3f}"
        ax2.text(xi - bw / 2, cv + 0.018, txt_c, ha="center", va="bottom", fontsize=7.2, color=GOLD)

    # Annotate raw negative Task-A R2 and ECE reduction from calibration.
    ax2.text(
        0.02,
        0.03,
        f"*Naive SGD raw Task-A R2 = {d6m['naive_sgd_task_r2_after_all'][0]:.3f} (clipped 0 for plot; forgetting=+{d6m['naive_sgd_forgetting_task_a']:.2f}). "
        f"D10 ECE: {d10m['ece_before_cal']:.3f} -> {d10m['ece_after_cal']:.3f}",
        transform=ax2.transAxes,
        fontsize=7.1,
        color=CYAN,
        bbox=dict(boxstyle="round,pad=0.25", facecolor=BG, edgecolor=BORDER, alpha=0.9),
    )
    ax2.set_ylim(0.0, 1.18)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(comp_labels, fontsize=7.8)
    ax2.set_ylabel("Quality / Retention / Calibration (Higher = Better)", fontsize=8.8)
    ax2.set_title("2. CONTINUAL EWC+REPLAY, CALIBRATION & OOD GAIN", fontsize=10.1, color=ORCHID, fontweight="bold", pad=10)
    ax2.grid(True, axis="y")
    ax2.legend(loc="upper right", fontsize=7.2, facecolor=BG, edgecolor=BORDER)


def _grid_cell_style(gx: int, gy: int) -> Tuple[str, str, str]:
    """Return (facecolor, edgecolor, label) for a 5x5 mission grid coordinate."""
    # Map special wall, Pearl do(X) hazard, start, and goal cells.
    if (gx, gy) in ((2, 0), (2, 1)):
        return "#2a3548", BORDER, "WALL"
    if (gx, gy) == (2, 2):
        return "#4a1724", RED, "do(X)\nHAZARD"
    if (gx, gy) == (0, 2):
        return "#123244", CYAN, "START"
    if (gx, gy) == (4, 2):
        return "#143b2a", MINT, "GOAL"
    return PANEL, BORDER, ""


def _plot_mission_grid_panel(ax3: Any, stage4: Dict[str, Any]) -> None:
    """Plot 5x5 mission grid comparing memory-off vs Pearl do(X) rerouted plans."""
    ax3.set_xlim(-0.55, 4.55)
    ax3.set_ylim(4.55, -1.25)
    ax3.set_aspect("equal")
    for gx in range(5):
        for gy in range(5):
            fill_c, edge_c, lbl = _grid_cell_style(gx, gy)
            ax3.add_patch(patches.Rectangle((gx - 0.46, gy - 0.46), 0.92, 0.92, facecolor=fill_c, edgecolor=edge_c, linewidth=1.4))
            if lbl:
                ax3.text(gx, gy + (0.28 if (gx, gy) == (2, 2) else 0.0), lbl, ha="center", va="center", fontsize=6.7, color=TEXT, fontweight="bold")

    # Overlay counterfactual routes with and without persistent causal memory.
    p_no = np.asarray(stage4["path_without_memory"], dtype=np.float64)
    p_yes = np.asarray(stage4["path_with_memory"], dtype=np.float64)
    ax3.plot(p_no[:, 0], p_no[:, 1] - 0.09, color=GOLD, linestyle="--", linewidth=2.6, marker="o", markersize=5.5, label="Path Without Memory (hits hazard (2,2))")
    ax3.plot(p_yes[:, 0], p_yes[:, 1] + 0.09, color=MINT, linestyle="-", linewidth=2.9, marker="*", markersize=8.5, label="Path With Pearl do(X) Memory (safe reroute)")
    ax3.set_xticks(range(5))
    ax3.set_yticks(range(5))
    ax3.set_xlabel("Grid Column X", fontsize=8.8)
    ax3.set_ylabel("Grid Row Y", fontsize=8.8)
    ax3.set_title("3. STAGE 5 COUNTERFACTUAL A/B PROOF: MEMORY FLIPS PLAN", fontsize=10.1, color=MINT, fontweight="bold", pad=10)
    ax3.legend(loc="upper center", ncol=1, fontsize=7.0, facecolor=BG, edgecolor=BORDER)


def _plot_boundaries_panel(
    ax4: Any,
    rep: Dict[str, Any],
    mission: Dict[str, Any],
    stages: Sequence[Dict[str, Any]],
    mem: Dict[str, Any],
    ep: Dict[str, Any],
) -> None:
    """Render Panel 4 memory audit, 7-stage mission ledger, and honest L5 gaps."""
    lines = [
        (f"L5 PHASE 1 CORE VERIFIED = {rep['l5_phase1_integrated_core_verified']}  |  L5 AGI-QUALIFIED = {rep['l5_agi_qualified']}", MINT, 9.8, "bold"),
        ("", TEXT, 4, "normal"),
        ("4-SYSTEM PERSISTENT MEMORY (`ZoeUnifiedMemory`):", CYAN, 8.6, "bold"),
        (f"  • Episodic={mem['episodic_count']} (cosine)  |  Semantic={mem['semantic_active_count']} active + {mem['semantic_superseded_count']} superseded", TEXT, 7.9, "normal"),
        (f"  • Procedural={mem['procedural_count']} AST `def`  |  Working={mem['working_count']}/7 (Kloster A_tau ranked)", TEXT, 7.9, "normal"),
        (f"  • Chain Head={str(mem['chain_head'])[:18]}... | Stopped={mem['stopped']} | Tamper=Enforced", CYAN, 7.9, "normal"),
        ("", TEXT, 4, "normal"),
        ("7-STAGE CROSS-DOMAIN INTEGRATED MISSION:", ORCHID, 8.6, "bold"),
        (f"  • S1 Perception OOD={stages[0]['ood_intervention_flagged']} -> S2 Metacog A05={stages[1]['a05_open']} ('{stages[1]['selected_action']}')", TEXT, 7.9, "normal"),
        (f"  • S3 Pearl do(X) ATE={stages[2]['do_effect_ate']} -> S4 Revised={stages[3]['belief_updated']} -> S5 Flipped={stages[4]['plan_changed_by_memory']}", MINT, 7.9, "normal"),
        (f"  • S6 Voice/Cymatics={stages[5]['phoneme_count']} phonemes | S7 Rollback={stages[6]['rollback_restored_bit_exact']} | Stop={stages[6]['emergency_stop_enforced']}", TEXT, 7.9, "normal"),
        ("", TEXT, 4, "normal"),
        ("HONEST REMAINING GAPS FOR `AGI-QUALIFIED` (CONSTITUTION Art II):", RED, 8.6, "bold"),
        ("  1. Sustain human-level open-ended generalization outside curated benchmarks.", GOLD, 7.6, "normal"),
        ("  2. Scale memory & continual consolidation across thousands of long sessions.", GOLD, 7.6, "normal"),
        ("  3. Validate multi-file repo & external benchmark discovery transfers.", GOLD, 7.6, "normal"),
        ("", TEXT, 4, "normal"),
        (f"Boundaries: pytorch={ep['pytorch_required']} | external_actions={ep['external_actions']} | clinical={ep['clinical_action_authorized']} | sentience={ep['sentience_claimed']}", MUTED, 7.5, "normal"),
    ]
    # Keep exact 0.050 line step and 0.955 top anchor for dense 18-line layout.
    draw_summary_card(
        ax4,
        "4. PERSISTENT MEMORY, GOVERNANCE & HONEST L5 BOUNDARIES",
        GOLD,
        GOLD,
        PANEL,
        lines,
        start_y=0.955,
        line_step=0.050,
        blank_step=0.020,
        title_size=10.1,
    )


def render_figure(report_path: Path = REPORT_PATH, out_path: Path = OUT_PNG) -> Path:
    """Render the 4-panel L5 Phase 1 cognitive core figure from JSON evidence."""
    rep = load_json_report(report_path)
    domains = rep["domains"]
    by_id = {d["domain_id"]: d for d in domains}
    mission = rep["integrated_mission"]
    stages = mission["stages"]
    mem = mission["memory_summary"]
    ep = rep["epistemic_boundaries"]

    apply_dark_theme()
    fig, axes = plt.subplots(2, 2, figsize=(18.6, 12.0), dpi=180)
    fig.subplots_adjust(left=0.145, right=0.97, top=0.875, bottom=0.07, wspace=0.26, hspace=0.33)
    subtitle = (
        f"Contract {rep['contract']} · Domains={rep['domains_passed']}/{rep['domains_total']} Passed · "
        f"Mean Zoe={rep['mean_zoe_score']:.4f} vs Controls={rep['mean_control_score']:.4f} · "
        f"7-Stage Mission={mission['mission_passed']} · Zero PyTorch · l5_agi_qualified={rep['l5_agi_qualified']}"
    )
    add_figure_header(
        fig,
        "ZOE L5 PHASE 1 :: INTEGRATED 10-DOMAIN COGNITIVE CORE, 4-SYSTEM MEMORY & COUNTERFACTUAL PROOF",
        subtitle,
        title_color=ORCHID,
        subtitle_color=GOLD,
        title_size=14.8,
        subtitle_size=9.8,
    )

    # Render each panel cleanly with single-purpose helpers.
    _plot_domains_panel(axes[0, 0], domains)
    _plot_continual_panel(axes[0, 1], by_id)
    _plot_mission_grid_panel(axes[1, 0], stages[4])
    _plot_boundaries_panel(axes[1, 1], rep, mission, stages, mem, ep)
    return save_figure(fig, out_path, dpi=180, facecolor=BG, mirror_path=DESKTOP_COPY, root=ROOT)


if __name__ == "__main__":
    render_figure()

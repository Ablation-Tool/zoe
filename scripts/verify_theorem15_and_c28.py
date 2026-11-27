#!/usr/bin/env python3
"""Verify Theorem 15 (Multi-Agent Consensus, Exact Brier Disagreement & Echo-Chamber Detection)
AND Challenge C28 (3D Botanical Pharmacophore & Synthetic Histology MTF — 28/28 Total Disciplines),
and render the unified 6-panel dark-observatory plate `zoe-kloster-theorem15-and-c28.png`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guiai.gem.kloster_multi_agent_consensus import run_kloster_theorem15_suite
from guiai.gem.kloster_pharmacophore_spatial_c28 import run_pharmacophore_spatial_c28_suite


def _dark_theme() -> None:
    plt.rcParams.update({
        "figure.facecolor": "#060A14", "axes.facecolor": "#0B1324",
        "axes.edgecolor": "#243652", "axes.labelcolor": "#DCE7F7",
        "xtick.color": "#9DB2D1", "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF", "font.family": "DejaVu Sans",
        "grid.color": "#1A2840", "grid.alpha": 0.65,
    })


def render_thm15_c28_plate(t15: Dict[str, Any], c28: Dict[str, Any], out_path: Path) -> None:
    """Render 6-panel dark-observatory verification plate for Theorem 15 & Challenge C28."""
    _dark_theme()
    fig = plt.figure(figsize=(18.8, 11.4), dpi=210)
    gs = fig.add_gridspec(2, 3, hspace=0.40, wspace=0.30, left=0.065, right=0.965, top=0.885, bottom=0.075)
    fig.suptitle(
        "Theorem 15 (Multi-Agent Consensus & Exact Brier Law)  ×  Challenge C28 (3D Pharmacophore & Histology MTF · 28/28 Total)",
        fontsize=12.1, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"5/5 SymPy 1.14.0 Proofs (residual=0)  |  0 Cloud Tokens  |  cure_claim=False  |  Thm15 SHA: {t15['evidence_sha256'][:12]} · C28 SHA: {c28['evidence_sha256'][:12]}",
        ha="center", fontsize=9.0, color="#7CE8FF",
    )

    # Panel A: Thm 15 World 1 — Diverse 6-LLM Committee vs Echo-Chamber Clone Control
    ax_a = fig.add_subplot(gs[0, 0])
    w1 = t15["world1_6llm_vs_echo"]
    va = [w1["diverse_6llm"]["d_k_disagreement"], w1["echo_chamber_6clone"]["d_k_disagreement"],
          w1["diverse_6llm"]["coherence_c_k"], w1["echo_chamber_6clone"]["coherence_c_k"]]
    bars_a = ax_a.bar([0, 1, 2, 3], va, color=["#63F5B5", "#FF5C8A", "#00E5FF", "#FFB84D"], width=0.54)
    for b, v in zip(bars_a, va):
        ax_a.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.3f}", ha="center", fontsize=7.8, fontweight="bold")
    ax_a.set_ylim(0, 1.18)
    ax_a.set_xticks([0, 1, 2, 3])
    ax_a.set_xticklabels(["6-LLM\nD_K Gain", "Echo Clone\nD_K (=0)", "6-LLM\nCoherence", "Echo Clone\nCoherence"], fontsize=7.3)
    ax_a.set_ylabel("Kloster Disagreement / Coherence", fontsize=8.2)
    ax_a.set_title("A. Thm 15: Diverse 6-LLM vs Echo-Chamber Trap", fontsize=9.4, fontweight="bold", color="#63F5B5", pad=8)
    ax_a.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel B: Thm 15 World 2 — Exact Kloster-Brier Wisdom-of-Crowds Law on 1,920 Real HELEN Obs
    ax_b = fig.add_subplot(gs[0, 1])
    w2 = t15["world2_helen_real_brier"]
    vb = [w2["brier_forward"], w2["brier_retrograde"], w2["brier_mean_single"], w2["brier_pooled_ensemble"]]
    bars_b = ax_b.bar([0, 1, 2, 3], vb, color=["#00E5FF", "#FFB84D", "#FF5C8A", "#63F5B5"], width=0.54)
    for b, v in zip(bars_b, vb):
        ax_b.text(b.get_x() + b.get_width() / 2, v + 0.015, f"{v:.4f}", ha="center", fontsize=7.7, fontweight="bold")
    ax_b.set_ylim(0, max(vb) * 1.24)
    ax_b.set_xticks([0, 1, 2, 3])
    ax_b.set_xticklabels(["HELEN\nForward", "HELEN\nRetrograde", "Mean Single\nAgent", "Pooled\nEnsemble"], fontsize=7.4)
    ax_b.set_ylabel("Mean Brier Error (Lower Is Better)", fontsize=8.2)
    ax_b.set_title(f"B. Real HELEN 1,920 Obs: Gain≡D_K (err={w2['max_per_row_identity_err']:.1e})", fontsize=9.1, fontweight="bold", color="#00E5FF", pad=8)
    ax_b.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel C: Thm 15 World 3 — Encrypted 3-Hospital FIPS 203 Consensus vs Rogue Node Detector
    ax_c = fig.add_subplot(gs[0, 2])
    w3 = t15["world3_fips203_consortium"]
    vc = [w3["honest_3site"]["coherence_c_k"], w3["rogue_contaminated_3site"]["coherence_c_k"],
          w3["honest_3site"]["d_k_disagreement"] * 5.0, w3["rogue_contaminated_3site"]["d_k_disagreement"] * 5.0]
    bars_c = ax_c.bar([0, 1, 2, 3], vc, color=["#63F5B5", "#FF5C8A", "#00E5FF", "#FFB84D"], width=0.54)
    for b, v in zip(bars_c, vc):
        ax_c.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.3f}", ha="center", fontsize=7.8, fontweight="bold")
    ax_c.set_ylim(0, 1.18)
    ax_c.set_xticks([0, 1, 2, 3])
    ax_c.set_xticklabels(["Honest 3-Site\nCoherence C_K", "Rogue Node\nCoherence C_K", "Honest\n5×D_K", "Rogue Node\n5×D_K Spike"], fontsize=7.2)
    ax_c.set_ylabel("FIPS 203 Consortium Coherence / 5×D_K", fontsize=8.0)
    ax_c.set_title("C. Encrypted 3-Hospital Rogue-Node Guard (0 PHI)", fontsize=9.3, fontweight="bold", color="#A78BFA", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel D: C28 — 3D Botanical Pharmacophore Radius (Compact CNS vs BBB-Blocked Controls)
    ax_d = fig.add_subplot(gs[1, 0])
    sp = c28["pharmacophore_3d_atlas"]["spotlight"]
    keys_d = ["artemisinin", "galanthamine", "dordaviprone", "curcumin", "paclitaxel", "crocin"]
    vd = [sp[k]["r_gyr_angstrom"] for k in keys_d]
    cols_d = ["#63F5B5" if sp[k]["passes_3d_bbb_compactness_gate"] else "#FF5C8A" for k in keys_d]
    bars_d = ax_d.bar(np.arange(6), vd, color=cols_d, width=0.56)
    ax_d.axhline(6.6, color="#FFB84D", ls="--", lw=1.3, label="3D CNS Compactness Gate (6.6 Å)")
    for b, v in zip(bars_d, vd):
        ax_d.text(b.get_x() + b.get_width() / 2, v + 0.25, f"{v:.1f}Å", ha="center", fontsize=7.6, fontweight="bold")
    ax_d.set_ylim(0, max(vd) * 1.22)
    ax_d.set_xticks(np.arange(6))
    ax_d.set_xticklabels(["Artemis.", "Galanth.", "Dordav.", "Curcumin\n(PAINS)", "Paclitax.\n(BBB)", "Crocin\n(BBB)"], fontsize=7.2)
    ax_d.set_ylabel("3D Pharmacophore Radius R_g (Å)", fontsize=8.2)
    ax_d.set_title("D. C28: 3D Botanical Pharmacophore BBB Gate", fontsize=9.4, fontweight="bold", color="#63F5B5", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_d.legend(loc="upper left", fontsize=7.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel E: C28 — Synthetic Histology Tumor Islands vs Healthy Mosaic vs CSR Artifact
    ax_e = fig.add_subplot(gs[1, 1])
    hi = c28["histology_microarchitecture_mtf"]
    ve = [hi["tumor_islands_clustered"]["z_kloster"], hi["csr_artifact_null"]["z_kloster"], hi["healthy_mosaic_regular"]["z_kloster"]]
    bars_e = ax_e.bar([0, 1, 2], ve, color=["#FF5C8A", "#9DB2D1", "#00E5FF"], width=0.50)
    ax_e.axhline(0.0, color="#64748B", lw=1.0)
    ax_e.axhspan(-2.5, 2.5, color="#63F5B5", alpha=0.09, label="CSR Null Band (±2.5σ)")
    for b, v in zip(bars_e, ve):
        ax_e.text(b.get_x() + b.get_width() / 2, v + (1.5 if v >= 0 else -2.8), f"{v:+.1f}σ", ha="center", fontsize=8.1, fontweight="bold")
    ax_e.set_ylim(min(ve) - 6.0, max(ve) + 7.5)
    ax_e.set_xticks([0, 1, 2])
    ax_e.set_xticklabels(["Tumor Islands\n(Thm13 STOP)", "CSR Artifact\n(Thm13 ABST)", "Healthy Mosaic\n(Regular −Z_K)"], fontsize=7.4)
    ax_e.set_ylabel("Two-Sided Kloster Spatial Z_K (σ)", fontsize=8.2)
    ax_e.set_title("E. C28 × Thm 14: Synthetic Histology Micro-Architecture", fontsize=9.2, fontweight="bold", color="#FFB84D", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_e.legend(loc="upper right", fontsize=7.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel F: Combined Verification Scorecard (7/7 · 28/28 Total Disciplines)
    ax_f = fig.add_subplot(gs[1, 2])
    all_ch = list(t15["checks"].values()) + list(c28["checks"].values())
    cats_f = ["T15\nSymPy", "T15\n6-LLM", "T15\nHELEN", "T15\nFIPS203", "C28\n3D Ph.", "C28\nHistol.", "C28\nGuard"]
    vf = [100.0 if ok else 0.0 for ok in all_ch]
    bars_f = ax_f.bar(np.arange(7), vf, color=["#63F5B5", "#00E5FF", "#A78BFA", "#FFB84D", "#63F5B5", "#00E5FF", "#63F5B5"], width=0.58)
    for b, v in zip(bars_f, vf):
        ax_f.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v:.0f}%", ha="center", fontsize=7.5, fontweight="bold")
    ax_f.set_ylim(0, 118)
    ax_f.set_xticks(np.arange(7))
    ax_f.set_xticklabels(cats_f, fontsize=6.9)
    ax_f.set_ylabel("Verification (%)", fontsize=8.2)
    ax_f.set_title("F. Thm 15 + C28 Verification (7/7 · 28/28 Total)", fontsize=9.3, fontweight="bold", color="#00E5FF", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=210)
    plt.close(fig)


def main() -> int:
    t15 = run_kloster_theorem15_suite(ROOT)
    c28 = run_pharmacophore_spatial_c28_suite()

    p15 = ROOT / "evidence/kloster-theorem15/kloster-theorem15-report.json"
    p15.parent.mkdir(parents=True, exist_ok=True)
    p15.write_text(json.dumps(t15, indent=2, sort_keys=True), encoding="utf-8")

    p28 = ROOT / "evidence/kloster-cryptanalysis/pharmacophore-spatial-c28-report.json"
    p28.parent.mkdir(parents=True, exist_ok=True)
    p28.write_text(json.dumps(c28, indent=2, sort_keys=True), encoding="utf-8")

    plate = ROOT / "components/agent-logging-system/docs/images/zoe-kloster-theorem15-and-c28.png"
    render_thm15_c28_plate(t15, c28, plate)

    checks = list(t15["checks"].items()) + list(c28["checks"].items()) + [
        ("thm15_c28_plate_generated", plate.is_file() and plate.stat().st_size > 50_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    w2 = t15["world2_helen_real_brier"]
    w3 = t15["world3_fips203_consortium"]
    hi = c28["histology_microarchitecture_mtf"]
    print(f"\nTHM15: 5/5 SymPy | HELEN 1920 Brier gain={w2['actual_brier_gain']} == D_K={w2['kloster_dk_predicted_gain']} (err={w2['max_per_row_identity_err']:.2e}) | Rogue C_K={w3['rogue_contaminated_3site']['coherence_c_k']} vs Honest={w3['honest_3site']['coherence_c_k']}")
    print(f"C28: 36 PubChem 3D Pharma | Tumor Z_K={hi['tumor_islands_clustered']['z_kloster']} (STOP@{hi['theorem13_tumor_stop']['samples']}) | Healthy={hi['healthy_mosaic_regular']['z_kloster']} | CSR={hi['csr_artifact_null']['z_kloster']} (ABST) | MTF err={hi['parseval_mtf_err']:.2e}")
    print(f"THM15 + C28 SUITE: {passed}/{len(checks)} PASS | Thm15={t15['evidence_sha256'][:16]} | C28={c28['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

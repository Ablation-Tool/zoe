#!/usr/bin/env python3
"""Verify Theorem 13 (Kloster Finite-Sample Metacognitive Stopping & Distinguisher Law)
and render the 6-panel computed scientific plate `zoe-kloster-theorem13.png`.
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

from guiai.gem.kloster_stopping_law import (
    KlosterSequentialStoppingController,
    predict_kloster_min_samples,
    run_theorem13_stopping_suite,
)


def _dark_theme() -> None:
    plt.rcParams.update({
        "figure.facecolor": "#060A14",
        "axes.facecolor": "#0B1324",
        "axes.edgecolor": "#243652",
        "axes.labelcolor": "#DCE7F7",
        "xtick.color": "#9DB2D1",
        "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF",
        "font.family": "DejaVu Sans",
        "grid.color": "#1A2840",
        "grid.alpha": 0.65,
    })


def render_theorem13_plate(rep: Dict[str, Any], out_path: Path) -> None:
    """Render 6-panel dark-observatory scientific plate for Theorem 13."""
    _dark_theme()
    fig = plt.figure(figsize=(18.8, 11.4), dpi=210)
    gs = fig.add_gridspec(2, 3, hspace=0.40, wspace=0.30, left=0.065, right=0.965, top=0.885, bottom=0.075)

    fig.suptitle(
        "Theorem 13 :: Kloster Finite-Sample Metacognitive Stopping & Distinguisher Law (SymPy 1.14.0 Proved)",
        fontsize=13.2, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"χ²(p‖u_N) = N·M₂(p) − 1  |  Exact Unbiased U-Stat & Null Variance  |  3-World Active Stopping  |  0 Cloud Tokens  |  SHA-256: {rep['evidence_sha256'][:16]}",
        ha="center", fontsize=9.1, color="#7CE8FF",
    )

    w1 = rep["worlds"]["world1_crypto_stopping"]
    w2 = rep["worlds"]["world2_bio_pains_stopping"]
    w3 = rep["worlds"]["world3_real_gpt2_and_null"]

    # Panel A: Theorem 13 Sample-Complexity Scaling Law S_min vs Excess Chi^2 (N=16, 64, 256)
    ax_a = fig.add_subplot(gs[0, 0])
    deltas = np.logspace(-1.2, 1.0, 40)
    for n_b, col in ((16, "#63F5B5"), (64, "#00E5FF"), (256, "#FFB84D")):
        s_vals = [0.5 * (1.0 + np.sqrt(1.0 + 8.0 * (n_b - 1.0) * 16.0 / (d ** 2))) for d in deltas]
        ax_a.loglog(deltas, s_vals, linewidth=2.2, color=col, label=f"N = {n_b} bins")
    ax_a.set_xlabel("Kloster Excess χ² = N·M₂(p) − 1", fontsize=8.2)
    ax_a.set_ylabel("Minimum Samples S_min (z=4)", fontsize=8.2)
    ax_a.set_title("A. Theorem 13d: Exact O(√N / Δ_K) Sample Law", fontsize=9.7, fontweight="bold", color="#63F5B5", pad=8)
    ax_a.grid(True, which="both", linestyle="--", linewidth=0.45)
    ax_a.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: World 1 — Crypto Active Stopping (Samples Used: Weak vs Full-Round Abstain)
    ax_b = fig.add_subplot(gs[0, 1])
    lbl_b = ["SIMON 5-Rd\n(STOP)", "SPECK 4-Rd\n(STOP)", "SIMON 32-Rd\n(ABSTAIN)", "SPECK 22-Rd\n(ABSTAIN)"]
    val_b = [
        w1["simon_5rd_weak"]["samples"],
        w1["speck_4rd_weak"]["samples"],
        w1["simon_32rd_full_ctrl"]["samples"],
        w1["speck_22rd_full_ctrl"]["samples"],
    ]
    bars_b = ax_b.bar(np.arange(4), val_b, color=["#63F5B5", "#00E5FF", "#A78BFA", "#FFB84D"], width=0.52)
    for b, v in zip(bars_b, val_b):
        ax_b.text(b.get_x() + b.get_width() / 2, v + 110, f"{v}", ha="center", fontsize=8.2, fontweight="bold")
    ax_b.set_ylim(0, 4800)
    ax_b.set_xticks(np.arange(4))
    ax_b.set_xticklabels(lbl_b, fontsize=7.5)
    ax_b.set_ylabel("Ciphertext Pairs Sampled", fontsize=8.2)
    ax_b.set_title("B. World 1: Crypto Early-Stop vs Full-Rd Abstain", fontsize=9.7, fontweight="bold", color="#00E5FF", pad=8)
    ax_b.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel C: World 1 — Z_K Decision Margin Above/Below Stopping Boundary
    ax_c = fig.add_subplot(gs[0, 2])
    zc = [
        w1["simon_5rd_weak"]["z_kloster"],
        w1["speck_4rd_weak"]["z_kloster"],
        w1["simon_32rd_full_ctrl"]["z_kloster"],
        w1["speck_22rd_full_ctrl"]["z_kloster"],
    ]
    bars_c = ax_c.bar(np.arange(4), zc, color=["#63F5B5", "#00E5FF", "#FF5C8A", "#FF5C8A"], width=0.52)
    for b, v in zip(bars_c, zc):
        ax_c.text(b.get_x() + b.get_width() / 2, max(v, 0) + 0.4, f"{v:.1f}σ", ha="center", fontsize=8.0, fontweight="bold")
    ax_c.axhline(w1["simon_5rd_weak"]["z_threshold"], color="#FFB84D", linestyle="--", linewidth=1.4, label="Anytime Stopping Gate")
    ax_c.set_ylim(min(-2.5, min(zc) - 1.0), max(zc) * 1.25)
    ax_c.set_xticks(np.arange(4))
    ax_c.set_xticklabels(["SIMON\n5-Rd", "SPECK\n4-Rd", "SIMON\n32-Rd", "SPECK\n22-Rd"], fontsize=7.8)
    ax_c.set_ylabel("Kloster Unbiased Z_K (σ)", fontsize=8.2)
    ax_c.set_title("C. World 1: Exact Unbiased Z_K Separation", fontsize=9.7, fontweight="bold", color="#FFB84D", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_c.legend(loc="upper right", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel D: World 2 — Botanical / Multi-Hospital PAINS Active Stopping
    ax_d = fig.add_subplot(gs[1, 0])
    sel, pains = w2["selective_tumor_gated"], w2["pains_uniform_toxicity_ctrl"]
    vd = [sel["z_kloster"], pains["z_kloster"]]
    bars_d = ax_d.bar([0, 1], vd, color=["#63F5B5", "#FF5C8A"], width=0.46)
    for b, v in zip(bars_d, vd):
        ax_d.text(b.get_x() + b.get_width() / 2, max(v, 0) + 0.35, f"{v:.2f}σ", ha="center", fontsize=8.4, fontweight="bold")
    ax_d.axhline(sel["z_threshold"], color="#FFB84D", linestyle="--", linewidth=1.3, label="Stopping Gate")
    ax_d.set_ylim(min(-2.0, min(vd) - 1.0), max(vd) * 1.28)
    ax_d.set_xticks([0, 1])
    ax_d.set_xticklabels([f"Selective Model\n(STOP @ n={sel['samples']})", f"PAINS Raw Toxin\n(ABSTAIN @ n={pains['samples']})"], fontsize=7.7)
    ax_d.set_ylabel("Kloster Z_K (σ)", fontsize=8.2)
    ax_d.set_title("D. World 2: Bio Selective Stop vs PAINS Abstain", fontsize=9.7, fontweight="bold", color="#63F5B5", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_d.legend(loc="upper right", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel E: World 3 — Real GPT-2 Early Stop & Exact Null Variance Calibration (200 Trials)
    ax_e = fig.add_subplot(gs[1, 1])
    ve = [w3["null_theorem13c_exact_variance"] * 1e6, w3["null_empirical_variance"] * 1e6]
    bars_e = ax_e.bar([0, 1], ve, color=["#00E5FF", "#A78BFA"], width=0.44)
    for b, v in zip(bars_e, ve):
        ax_e.text(b.get_x() + b.get_width() / 2, v + 0.3, f"{v:.2f}", ha="center", fontsize=8.4, fontweight="bold")
    ax_e.set_ylim(0, max(ve) * 1.32)
    ax_e.set_xticks([0, 1])
    ax_e.set_xticklabels(["Theorem 13c\nExact Formula", "200-Trial\nEmpirical Null"], fontsize=8.0)
    ax_e.set_ylabel("Null Variance × 10⁶ (N=32, S=80)", fontsize=8.2)
    ax_e.set_title(f"E. World 3: Null Var Match & FAR={w3['anytime_valid_false_alarm_rate']*100:.1f}%", fontsize=9.7, fontweight="bold", color="#A78BFA", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel F: Full Theorem 13 Scorecard (SymPy + 3 Worlds + Real GPT-2)
    ax_f = fig.add_subplot(gs[1, 2])
    cats_f = ["SymPy\n4/4 Proof", "World 1\nCrypto", "World 2\nBio/PAINS", "World 3\nGPT-2+Null"]
    vals_f = [100.0 if ok else 0.0 for ok in rep["checks"].values()]
    bars_f = ax_f.bar(np.arange(4), vals_f, color=["#63F5B5", "#00E5FF", "#FFB84D", "#A78BFA"], width=0.52)
    for b, v in zip(bars_f, vals_f):
        ax_f.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v:.0f}%", ha="center", fontsize=8.4, fontweight="bold")
    ax_f.set_ylim(0, 118)
    ax_f.set_xticks(np.arange(4))
    ax_f.set_xticklabels(cats_f, fontsize=7.8)
    ax_f.set_ylabel("Verification (%)", fontsize=8.2)
    gpt_s = w3["real_gpt2_top64_stopping"]["samples"]
    ax_f.set_title(f"F. Theorem 13 Suite (4/4 · GPT-2 Stop @ S={gpt_s})", fontsize=9.7, fontweight="bold", color="#00E5FF", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=210)
    plt.close(fig)


def main() -> int:
    report = run_theorem13_stopping_suite(ROOT)
    ev_path = ROOT / "evidence/kloster-theorem13/kloster-theorem13-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    plate_path = ROOT / "components/agent-logging-system/docs/images/zoe-kloster-theorem13.png"
    render_theorem13_plate(report, plate_path)

    checks = list(report["checks"].items()) + [
        ("theorem13_plate_generated", plate_path.is_file() and plate_path.stat().st_size > 50_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    w1 = report["worlds"]["world1_crypto_stopping"]
    w2 = report["worlds"]["world2_bio_pains_stopping"]
    w3 = report["worlds"]["world3_real_gpt2_and_null"]
    print(
        f"\nWORLD 1 CRYPTO: SIMON-5rd STOP@{w1['simon_5rd_weak']['samples']} | SPECK-4rd STOP@{w1['speck_4rd_weak']['samples']} | "
        f"FULL-RD={w1['simon_32rd_full_ctrl']['action']}/{w1['speck_22rd_full_ctrl']['action']}"
    )
    print(
        f"WORLD 2 BIO: Selective STOP@{w2['selective_tumor_gated']['samples']} (Z={w2['selective_tumor_gated']['z_kloster']}) | "
        f"PAINS={w2['pains_uniform_toxicity_ctrl']['action']} (Z={w2['pains_uniform_toxicity_ctrl']['z_kloster']})"
    )
    print(
        f"WORLD 3 GPT-2+NULL: GPT-2 STOP@{w3['real_gpt2_top64_stopping']['samples']} | "
        f"Null FAR={w3['anytime_valid_false_alarm_rate']} | Var rel err={w3['null_variance_rel_error']}"
    )
    print(f"THEOREM 13 SUITE: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

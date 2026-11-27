#!/usr/bin/env python3
"""Verify Theorem 7 (Kloster-Wasserstein Optimal Transport, Superlevel Persistence & Gini Duality)
and render the 6-panel computed scientific plate `zoe-kloster-optimal-transport.png`.
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
from scipy.stats import wasserstein_distance

from guiai.gem.kloster_optimal_transport import (
    kloster_l2_persistence_integral,
    kloster_wasserstein1,
    run_kloster_optimal_transport_suite,
)


def _configure_dark_theme() -> None:
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


def _plot_w1_identity(ax: Any) -> None:
    rng = np.random.default_rng(20260711)
    wk, wsp = [], []
    for _ in range(180):
        n = int(rng.integers(8, 24))
        p = rng.dirichlet(np.full(n, 0.5))
        q = rng.dirichlet(np.full(n, 0.6))
        wk.append(kloster_wasserstein1(p, q))
        wsp.append(float(wasserstein_distance(p, q)))
    ax.scatter(wsp, wk, s=36, color="#00E5FF", alpha=0.82, edgecolor="#FFFFFF", linewidth=0.35, label="180 Dirichlet Pairs")
    lim = max(max(wk), max(wsp)) * 1.06
    ax.plot([0.0, lim], [0.0, lim], color="#FFB84D", linewidth=2.0, linestyle="--", label="Exact Identity: W_1 = D_K / N")
    ax.scatter([0.0], [0.0], s=95, marker="X", color="#FF5C8A", zorder=6, label="Uniform Neg Ctrl (0, 0)")
    ax.set_xlabel("SciPy Exact Wasserstein-1 W_1(μ_p, μ_q)", fontsize=8.8)
    ax.set_ylabel("Kloster Spectral (1/N) ∫|A_τ(p)-A_τ(q)|dτ", fontsize=8.8)
    ax.set_title("A. Thm 7a: Exact Kloster = Wasserstein-1 (<1e-14)", fontsize=10.2, fontweight="bold", color="#7CE8FF", pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6)
    ax.legend(loc="upper left", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")


def _plot_persistence_and_gini(ax: Any, report: Dict[str, Any]) -> None:
    rows = sorted(report["llm_optimal_transport"]["llm_rows"], key=lambda r: r["kloster_gini"], reverse=True)
    y = np.arange(len(rows))
    lbls = [r["model"].replace("-base", "").replace("-cased", "").replace("-v1.2", "")[:14] for r in rows]
    ginis = [r["kloster_gini"] for r in rows]
    ubs = [r["cauchy_schwarz_ub"] for r in rows]
    ax.barh(y, ginis, color="#63F5B5", height=0.62, alpha=0.92, label="Exact Kloster-Gini G(p)")
    ax.scatter(ubs, y, color="#FFB84D", s=26, zorder=5, label="Cauchy-Schwarz UB 1 - 1/(N·p_max)")
    ax.set_yticks(y)
    ax.set_yticklabels(lbls, fontsize=7.3)
    ax.invert_yaxis()
    ax.set_xlim(0.45, 1.025)
    ax.set_xlabel("Exact Gini Concentration G(p) = 1 - (1/N)∫A_τ² dτ", fontsize=8.6)
    ax.set_title("B. Thm 7b: 16 Real LLMs Gini & Cauchy-Schwarz Bound", fontsize=10.1, fontweight="bold", color="#63F5B5", pad=8)
    ax.grid(axis="x", linestyle="--", linewidth=0.6)
    ax.legend(loc="lower right", fontsize=7.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")


def _plot_displacement_geodesic(ax: Any, report: Dict[str, Any]) -> None:
    geo = report["llm_optimal_transport"]["geodesic_uniform_to_qwen"]
    ts = [g["t"] for g in geo]
    w1s = [g["w1_from_uniform"] * 256.0 for g in geo]
    gs = [g["kloster_gini"] for g in geo]
    ax.plot(ts, w1s, color="#00E5FF", marker="o", linewidth=2.3, markersize=6, label="Optimal Transport D_K(u, p_t) (Exact Linear)")
    ax2 = ax.twinx()
    ax2.plot(ts, gs, color="#FFB84D", marker="s", linewidth=2.1, linestyle="--", markersize=5.5, label="Kloster-Gini G(p_t) Along Geodesic")
    ax.set_xlabel("McCann Displacement Parameter t (Uniform → Qwen2.5-Math)", fontsize=8.6)
    ax.set_ylabel("Kloster Transport Work D_K(u, p_t)", fontsize=8.6, color="#00E5FF")
    ax2.set_ylabel("Kloster-Gini G(p_t)", fontsize=8.6, color="#FFB84D")
    ax.set_title("C. Thm 7c: Exact Optimal Transport Geodesic Flow", fontsize=10.2, fontweight="bold", color="#FFB84D", pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6)
    ax.legend(loc="upper left", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax2.legend(loc="lower right", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")


def _plot_barycenter_curve(ax: Any, report: Dict[str, Any]) -> None:
    bary = report["llm_optimal_transport"]["barycenter_top20_curve"]
    ranks = np.arange(1, len(bary) + 1)
    unif = np.full(len(bary), 1.0 / 256.0)
    ax.fill_between(ranks, unif, bary, color="#00E5FF", alpha=0.22)
    ax.plot(ranks, bary, color="#00E5FF", marker="o", linewidth=2.3, markersize=5, label=f"16-LLM W_1 Barycenter (G={report['llm_optimal_transport']['barycenter_w1_gini']:.4f})")
    ax.plot(ranks, unif, color="#FF5C8A", linestyle="--", linewidth=1.8, label="Uniform Baseline (1/256, Neg Ctrl)")
    ax.set_xlabel("Token Rank k (Top-20 of 256-Rank Grid)", fontsize=8.8)
    ax.set_ylabel("Optimal-Transport Barycenter Mass p_(k)", fontsize=8.8)
    ax.set_title("D. Exact 16-LLM Wasserstein-1 Barycenter Spectrum", fontsize=10.2, fontweight="bold", color="#7CE8FF", pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6)
    ax.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")


def _plot_lorenz_superlevel(ax: Any, report: Dict[str, Any]) -> None:
    # Visualize H_0 Superlevel Persistence curves beta_0(tau) = A_tau(p) for 3 regimes
    taus = np.logspace(-3.2, -0.02, 220)
    rng = np.random.default_rng(20260777)
    p_unif = np.full(64, 1.0 / 64.0)
    p_mid = np.sort(rng.dirichlet(np.full(64, 0.8)))[::-1]
    p_sharp = np.sort(rng.dirichlet(np.full(64, 0.12)))[::-1]
    for arr, col, lbl in (
        (p_unif, "#FF5C8A", "Uniform Neg Ctrl (G=0.000)"),
        (p_mid, "#FFB84D", f"Balanced Spectrum (G={kloster_l2_persistence_integral(p_mid)[1]:.3f})"),
        (p_sharp, "#63F5B5", f"Sharp Concentrated (G={kloster_l2_persistence_integral(p_sharp)[1]:.3f})"),
    ):
        a_curve = np.array([int(np.sum(arr > t)) for t in taus], dtype=np.float64)
        ax.plot(taus, a_curve, color=col, linewidth=2.2, label=lbl)
    ax.set_xscale("log")
    ax.set_xlabel("Superlevel Filtration Threshold τ (log scale)", fontsize=8.8)
    ax.set_ylabel("Betti-0 Persistence β_0(τ) = A_τ(p)", fontsize=8.8)
    ax.set_title("E. H_0 Superlevel Barcode: ∫A_τ=1, ∫A_τ²=N(1-G)", fontsize=10.1, fontweight="bold", color="#63F5B5", pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6)
    ax.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")


def _plot_l2_vs_gini_scaling(ax: Any, report: Dict[str, Any]) -> None:
    rows = report["llm_optimal_transport"]["llm_rows"]
    vocabs = [r["vocab_active"] for r in rows]
    l2s = [r["l2_persistence_int"] for r in rows]
    ginis = [r["kloster_gini"] for r in rows]
    sc = ax.scatter(vocabs, l2s, c=ginis, cmap="plasma", s=85, edgecolor="#FFFFFF", linewidth=0.7, zorder=5)
    cb = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("Kloster-Gini G(p)", fontsize=7.8)
    for r in rows:
        if any(k in r["model"] for k in ("qwen", "gpt2", "prot_bert", "bert-base-cased", "biobert")):
            dx, dy = (-70, 7) if "qwen" in r["model"] else (7, 5)
            if "biobert" in r["model"]:
                dx, dy = (7, -11)
            ax.annotate(r["model"].replace("-base", "").replace("-cased", "")[:14], (r["vocab_active"], r["l2_persistence_int"]), xytext=(dx, dy), textcoords="offset points", fontsize=6.9, color="#EEF5FF")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Active Vocabulary Size N (log scale)", fontsize=8.8)
    ax.set_ylabel("L_2 Persistence ∫A_τ(p)² dτ = N(1-G) (log)", fontsize=8.6)
    ax.set_title("F. 16 Real LLMs: L_2 Persistence vs Vocab Scaling", fontsize=10.2, fontweight="bold", color="#FFB84D", pad=8)
    ax.grid(True, linestyle="--", linewidth=0.6)


def render_optimal_transport_plate(report: Dict[str, Any], out_path: Path) -> None:
    """Render the 6-panel computed scientific plate for Theorem 7."""
    _configure_dark_theme()
    fig = plt.figure(figsize=(18.4, 10.8), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.28, left=0.065, right=0.96, top=0.89, bottom=0.075)

    fig.suptitle(
        "Theorem 7 :: Kloster-Wasserstein Optimal Transport, H_0 Superlevel Persistence & Exact Gini Duality",
        fontsize=15.0, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Computed Scientific Plate  |  SymPy {report['symbolic_proofs']['sympy_version']} Proved  |  W_1 Err={report['monte_carlo_300']['max_w1_vs_scipy_error']:.1e}  |  16 Real LLMs  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.5, color="#7CE8FF",
    )

    _plot_w1_identity(fig.add_subplot(gs[0, 0]))
    _plot_persistence_and_gini(fig.add_subplot(gs[0, 1]), report)
    _plot_displacement_geodesic(fig.add_subplot(gs[0, 2]), report)
    _plot_barycenter_curve(fig.add_subplot(gs[1, 0]), report)
    _plot_lorenz_superlevel(fig.add_subplot(gs[1, 1]), report)
    _plot_l2_vs_gini_scaling(fig.add_subplot(gs[1, 2]), report)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    report = run_kloster_optimal_transport_suite(ROOT)
    ev_path = ROOT / "evidence/kloster-optimal-transport/kloster-optimal-transport-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-kloster-optimal-transport.png"
    render_optimal_transport_plate(report, fig_path)

    checks = list(report["checks"].items()) + [
        ("optimal_transport_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000)
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independent Verifier & 6-Panel Thermodynamic Criticality Plate Renderer for Theorem 5 (Orbit Pass 3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guiai.gem.kloster_thermodynamics import run_kloster_thermodynamics_suite


def render_thermodynamics_plate(report: dict, out_path: Path) -> None:
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

    betas = np.asarray(report["beta_grid"], dtype=np.float64)
    llms = report["llm_criticality"]
    by_name = {m["model"]: m for m in llms}

    fig = plt.figure(figsize=(18.5, 11.0), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.36, wspace=0.28, left=0.06, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "Theorem 5 :: Kloster Statistical Thermodynamics — Helmholtz Free Energy F(β) & Heat-Capacity Criticality C(β)",
        fontsize=15.2, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    top = report["top_susceptibility_llm"]
    fig.text(
        0.5, 0.923,
        f"Computed Scientific Plate  |  SymPy 1.14.0 Proved  |  16 Real LLMs Mapped  |  Peak Susceptibility: {top['model']} (C*={top['c_star']:.2f} @ β*={top['beta_star']})  |  Uniform Neg Ctrl C=0.0",
        ha="center", fontsize=9.6, color="#7CE8FF",
    )

    # Panel A: Kloster Heat-Capacity Criticality Curves C(beta) Across Representative Real LLMs
    ax_a = fig.add_subplot(gs[0, 0])
    featured = [
        ("qwen2.5-math-1.5b", "#00E5FF", "Qwen2.5-Math-1.5B (151k)"),
        ("gpt2", "#FFB84D", "GPT-2 (50k)"),
        ("biobert-base-cased-v1.2", "#63F5B5", "BioBERT (29k)"),
        ("codebert-base", "#A78BFA", "CodeBERT (50k)"),
        ("bert-base-cased", "#FF5C8A", "BERT-base (29k)"),
    ]
    for key, col, lbl in featured:
        if key in by_name:
            ax_a.semilogx(betas, by_name[key]["c_curve"], color=col, linewidth=2.2, label=lbl)
    ax_a.axhline(0.0, color="#9DB2D1", linestyle=":", linewidth=1.3, label="Uniform Neg Ctrl (C(β) ≡ 0)")
    ax_a.axvline(1.0, color="#EEF5FF", linestyle="--", linewidth=1.1, alpha=0.6)
    ax_a.set_xlabel("Inverse Temperature β = 1 / T (log scale)", fontsize=9)
    ax_a.set_ylabel("Kloster Heat Capacity C(β) = β² Var(-ln p)", fontsize=9)
    ax_a.set_title("A. Heat-Capacity Phase Peaks C(β) Across Real LLMs", fontsize=10.6, fontweight="bold", color="#7CE8FF", pad=8)
    ax_a.grid(True, linestyle="--", linewidth=0.6)
    ax_a.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: Internal Surprisal Energy U(beta) = E_{p^(beta)}[-ln p] Cooling Curves
    ax_b = fig.add_subplot(gs[0, 1])
    for key, col, lbl in featured:
        if key in by_name:
            ax_b.semilogx(betas, by_name[key]["u_curve"], color=col, linewidth=2.2, label=lbl)
    ax_b.axvline(1.0, color="#EEF5FF", linestyle="--", linewidth=1.1, alpha=0.6)
    ax_b.set_xlabel("Inverse Temperature β = 1 / T (log scale)", fontsize=9)
    ax_b.set_ylabel("Escort Internal Energy U(β) (nats)", fontsize=9)
    ax_b.set_title("B. Thermodynamic Surprisal Cooling Curves U(β)", fontsize=10.6, fontweight="bold", color="#FFB84D", pad=8)
    ax_b.grid(True, linestyle="--", linewidth=0.6)
    ax_b.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: Helmholtz Free Energy F(beta) = ((beta-1)/beta) * H_beta(p)
    ax_c = fig.add_subplot(gs[0, 2])
    for key, col, lbl in featured:
        if key in by_name:
            ax_c.semilogx(betas, by_name[key]["f_curve"], color=col, linewidth=2.2, label=lbl)
    ax_c.axhline(0.0, color="#EEF5FF", linestyle=":", linewidth=1.1)
    ax_c.axvline(1.0, color="#EEF5FF", linestyle="--", linewidth=1.1, alpha=0.6)
    ax_c.set_xlabel("Inverse Temperature β = 1 / T (log scale)", fontsize=9)
    ax_c.set_ylabel("Kloster Helmholtz Free Energy F(β)", fontsize=9)
    ax_c.set_title("C. Exact Helmholtz-Renyi Duality F(β)", fontsize=10.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_c.grid(True, linestyle="--", linewidth=0.6)
    ax_c.legend(loc="lower right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    for ax_log in (ax_a, ax_b, ax_c):
        ax_log.set_xticks([0.2, 0.5, 1.0, 2.0, 4.0])
        ax_log.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax_log.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax_log.set_xticklabels(["0.2", "0.5", "1.0", "2.0", "4.0"])

    # Panel D: Critical Temperature T* = 1/beta* vs Peak Heat Capacity C* Across ALL 16 Real LLMs!
    ax_d = fig.add_subplot(gs[1, 0])
    t_stars = [m["critical_temp_t_star"] for m in llms]
    c_stars = [m["peak_heat_capacity_c_star"] for m in llms]
    vocabs = [math.log10(max(10, m["vocab_active"])) for m in llms]
    sc_d = ax_d.scatter(t_stars, c_stars, s=95, c=vocabs, cmap="plasma", edgecolor="#FFFFFF", linewidth=0.7, alpha=0.92)
    for m in sorted(llms, key=lambda x: -x["peak_heat_capacity_c_star"])[:6]:
        dx, dy = (-76, -3) if m["critical_temp_t_star"] > 1.85 else (6, 3)
        ax_d.annotate(m["model"][:12], (m["critical_temp_t_star"], m["peak_heat_capacity_c_star"]), xytext=(dx, dy), textcoords="offset points", fontsize=7.2, color="#EEF5FF")
    cb_d = fig.colorbar(sc_d, ax=ax_d, fraction=0.046, pad=0.03)
    cb_d.set_label("log10(Active Vocab)", fontsize=7.8)
    ax_d.set_xlabel("Critical Decoding Temperature T* = 1 / β*", fontsize=9)
    ax_d.set_ylabel("Peak Heat Capacity C(β*)", fontsize=9)
    ax_d.set_title("D. 16-LLM Thermodynamic Criticality Phase Map", fontsize=10.6, fontweight="bold", color="#7CE8FF", pad=8)
    ax_d.grid(True, linestyle="--", linewidth=0.6)

    # Panel E: Ranked Peak Susceptibility C* Across All 16 Real Neural LLMs
    ax_e = fig.add_subplot(gs[1, 1])
    ranked = sorted(llms, key=lambda m: m["peak_heat_capacity_c_star"], reverse=True)
    y_e = np.arange(len(ranked))
    lbls_e = [m["model"].replace("-base", "").replace("-cased", "").replace("-v1.2", "")[:14] for m in ranked]
    vals_e = [m["peak_heat_capacity_c_star"] for m in ranked]
    ax_e.barh(y_e, vals_e, color="#FFB84D", height=0.65, alpha=0.9)
    ax_e.set_yticks(y_e)
    ax_e.set_yticklabels(lbls_e, fontsize=7.4)
    ax_e.invert_yaxis()
    ax_e.set_xlabel("Peak Kloster Heat Capacity C(β*)", fontsize=9)
    ax_e.set_title("E. 16-LLM Phase-Transition Susceptibility Ranking", fontsize=10.6, fontweight="bold", color="#FFB84D", pad=8)
    ax_e.grid(axis="x", linestyle="--", linewidth=0.6)

    # Panel F: Full 16 x 36 Heatmap of C(beta) Across All Architectures & Temperatures
    ax_f = fig.add_subplot(gs[1, 2])
    mat = np.asarray([m["c_curve"] for m in ranked], dtype=np.float64)
    im_f = ax_f.imshow(np.log1p(mat), aspect="auto", cmap="magma", extent=[np.log10(betas[0]), np.log10(betas[-1]), len(ranked) - 0.5, -0.5])
    ax_f.set_yticks(np.arange(len(ranked)))
    ax_f.set_yticklabels(lbls_e, fontsize=6.8)
    ax_f.axvline(0.0, color="#63F5B5", linestyle="--", linewidth=1.2)
    ax_f.set_xlabel("log10(Inverse Temperature β)  [0 = T=1.0]", fontsize=9)
    ax_f.set_title("F. Cross-Architecture Heat-Capacity Landscape", fontsize=10.6, fontweight="bold", color="#63F5B5", pad=8)
    cb_f = fig.colorbar(im_f, ax=ax_f, fraction=0.046, pad=0.03)
    cb_f.set_label("ln(1 + C(β))", fontsize=7.8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


import math


def main() -> int:
    report = run_kloster_thermodynamics_suite(ROOT)
    ev_path = ROOT / "evidence/kloster-thermodynamics/kloster-thermodynamics-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-kloster-thermodynamics.png"
    render_thermodynamics_plate(report, fig_path)

    checks = list(report["checks"].items()) + [("thermodynamics_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000)]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

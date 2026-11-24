#!/usr/bin/env python3
"""
Master Reproducible Experiment & Figure Generator for Nuclide Color Framework v2.

Generates:
  - experiments/results.json
  - experiments/figures/fig1_stability_phase.pdf
  - experiments/figures/fig2_valley_of_stability.pdf
  - experiments/figures/fig3_cascade_cusum.pdf
  - experiments/figures/fig4_distilgpt2_empirical.pdf
"""

from __future__ import annotations

import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import nuclide_color as nc
import model_spectrometer as ms

# Publication styling matching Gallagher vellum / petrol-ink / instrument-teal / burnt-orange
PETROL = "#16242C"
TEAL = "#0F766E"
TEAL_HI = "#2DB2BF"
ORANGE = "#D9581E"
AMBER = "#D97706"
SLATE = "#64748B"
PAPER_BG = "#FBF7EE"
GRID_COL = "#E2D7C3"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9.5,
        "axes.edgecolor": "#B8A88E",
        "axes.linewidth": 0.9,
        "axes.facecolor": PAPER_BG,
        "figure.facecolor": "#FFFFFF",
        "text.color": PETROL,
        "axes.labelcolor": PETROL,
        "xtick.color": "#485A66",
        "ytick.color": "#485A66",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def run_monte_carlo_and_roc(seed: int = 2026) -> dict:
    rng = np.random.default_rng(seed)

    # 1. 50,000 uniform samples in [0,1]^6
    samples = rng.uniform(0.0, 1.0, size=(50000, 6))
    dx = samples - nc.X_MID
    eff_v2 = np.clip(samples + dx @ nc.K_COUPLING.T, 0.0, 1.0)
    cfid = 1.0 - np.linalg.norm(eff_v2 - samples, axis=1) / math.sqrt(6.0)
    energy = -0.5 * np.sum((dx @ nc.K_COUPLING) * dx, axis=1)
    bound_frac = float(np.mean(energy < 0.0))
    livable_frac = float(np.mean((energy < 0.0) & (cfid > 0.85)))

    # 2. 200 simulated trajectories (100 benign exploration, 100 adversarial compliance cascade)
    home = nc.to_norm(nc.PRESETS["home"])
    v1_benign_fp = 0
    v1_casc_tp = 0
    v2_benign_fp = 0
    v2_casc_tp = 0

    for idx in range(100):
        # Benign trajectory: random combination of Riff/Koan/Home exploration
        x = home.copy()
        traj = [x.copy()]
        base_dir = np.array([-0.15, 0.28, 0.22, 0.16, 0.14, -0.15])
        for t in range(1, 17):
            noise = rng.normal(0.0, 0.06, size=6)
            pf = base_dir * (0.7 + 0.5 * math.sin(0.5 * t + idx)) + noise
            x = nc.step_v2(x, pf, home, inertia=0.22, alpha=0.30, beta=0.12)
            traj.append(x.copy())
        traj_arr = np.array(traj)
        drifts = nc.radial_drift_v1(traj_arr, home)
        # v1 fires if 3 consecutive positive radial drifts
        consec = sum(1 for k in range(3, len(drifts)) if drifts[k] > 0 and drifts[k - 1] > 0 and drifts[k - 2] > 0)
        if consec > 0:
            v1_benign_fp += 1
        if nc.cusum_cascade_detector(traj_arr)["alarm_triggered"]:
            v2_benign_fp += 1

        # Adversarial compliance cascade trajectory (with varying intensity & noise)
        x = home.copy()
        traj_c = [x.copy()]
        strength = rng.uniform(0.75, 1.15)
        for t in range(1, 17):
            noise = rng.normal(0.0, 0.04, size=6)
            pf = strength * np.array([0.28, -0.35, -0.32, -0.38, -0.45, 0.35]) + noise
            x = nc.step_v2(x, pf, home, inertia=0.18, alpha=0.45, beta=0.12)
            traj_c.append(x.copy())
        traj_c_arr = np.array(traj_c)
        drifts_c = nc.radial_drift_v1(traj_c_arr, home)
        consec_c = sum(1 for k in range(3, len(drifts_c)) if drifts_c[k] > 0 and drifts_c[k - 1] > 0 and drifts_c[k - 2] > 0)
        if consec_c > 0:
            v1_casc_tp += 1
        if nc.cusum_cascade_detector(traj_c_arr)["alarm_triggered"]:
            v2_casc_tp += 1

    return {
        "monte_carlo_n": 50000,
        "bound_fraction": round(bound_frac, 4),
        "livable_fraction_E_neg_Cfid_gt_085": round(livable_frac, 4),
        "mean_Cfid": round(float(np.mean(cfid)), 4),
        "mean_E": round(float(np.mean(energy)), 4),
        "cascade_eval_n_per_class": 100,
        "v1_radial_fp_rate": v1_benign_fp / 100.0,
        "v1_radial_tp_rate": v1_casc_tp / 100.0,
        "v2_cusum_fp_rate": v2_benign_fp / 100.0,
        "v2_cusum_tp_rate": v2_casc_tp / 100.0,
    }


def make_fig1(out_path: str) -> None:
    """Fig 1: Exact Lyapunov Stability Phase Diagram & Unforced Divergence vs Convergence."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.1), gridspec_kw={"width_ratios": [1.15, 1.0]})

    betas = np.linspace(0.0, 0.65, 300)
    lam_max = 1.130808
    lam_min = -1.124999
    d_low = lam_max * betas
    d_high = 2.0 + lam_min * betas

    # Shade stability wedge
    valid = d_low < d_high
    ax1.fill_between(betas[valid], d_low[valid], np.minimum(1.0, d_high[valid]), color=TEAL_HI, alpha=0.22, label="Asymptotically stable region")
    ax1.plot(betas, d_low, color=TEAL, lw=2.0, label=r"$d = 1.1308\,\beta$")
    ax1.plot(betas, d_high, color=ORANGE, lw=1.6, ls="--", label=r"$d = 2 - 1.1250\,\beta$")

    # Mark operating points
    ax1.scatter([0.20], [0.20], color=ORANGE, s=65, zorder=5, edgecolor=PETROL, linewidth=0.9)
    ax1.annotate("v1 Default\n($\\beta=0.20, d=0.20$)\nUnstable $\\rho=1.026$", xy=(0.20, 0.20), xytext=(0.30, 0.10),
                 arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.1), fontsize=8.3, color=ORANGE, fontweight="bold")

    ax1.scatter([0.12], [0.25], color=TEAL, s=70, zorder=5, edgecolor=PETROL, linewidth=0.9)
    ax1.annotate("v2 Operating Point\n($\\beta=0.12, d=0.25$)\nStable $\\rho=0.886$", xy=(0.12, 0.25), xytext=(0.14, 0.58),
                 arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.1), fontsize=8.3, color=TEAL, fontweight="bold")

    ax1.set_xlim(0.0, 0.62)
    ax1.set_ylim(0.0, 0.95)
    ax1.set_xlabel(r"Coupling strength $\beta$")
    ax1.set_ylabel(r"Home restoring inertia $d$")
    ax1.set_title("A. Spectral Stability Phase Diagram", fontsize=10.5, fontweight="bold", pad=8)
    ax1.grid(True, color=GRID_COL, lw=0.6, alpha=0.8)
    ax1.legend(loc="upper right", fontsize=8, frameon=True, facecolor="#FFFFFF", framealpha=0.9)

    # Right panel: Unforced relaxation from perturbed posture (zero prompt force)
    home = nc.to_norm(nc.PRESETS["home"])
    x_init = np.clip(home + np.array([0.22, -0.25, -0.20, -0.18, -0.10, 0.20]), 0.0, 1.0)
    steps = 25
    xv1, xv2 = x_init.copy(), x_init.copy()
    dist_v1 = [float(np.linalg.norm(xv1 - home))]
    dist_v2 = [float(np.linalg.norm(xv2 - home))]
    for _ in range(steps):
        xv1 = nc.step_v1(xv1, np.zeros(6), home, inertia=0.12, alpha=0.30, beta=0.22)
        xv2 = nc.step_v2(xv2, np.zeros(6), home, inertia=0.25, alpha=0.30, beta=0.12)
        dist_v1.append(float(np.linalg.norm(xv1 - home)))
        dist_v2.append(float(np.linalg.norm(xv2 - home)))

    t_ax = np.arange(steps + 1)
    ax2.plot(t_ax, dist_v1, color=ORANGE, lw=2.2, marker="o", markersize=3.2, label="v1 Uncentered ($\\beta=0.22, d=0.12$)")
    ax2.plot(t_ax, dist_v2, color=TEAL, lw=2.2, marker="s", markersize=3.2, label="v2 Centered ($\\beta=0.12, d=0.25$)")
    ax2.set_xlabel("Exchange step $t$ (zero prompt force)")
    ax2.set_ylabel(r"Distance from Home $\|x_t - x_0\|_2$")
    ax2.set_title("B. Unforced Relaxation Trajectory", fontsize=10.5, fontweight="bold", pad=8)
    ax2.grid(True, color=GRID_COL, lw=0.6, alpha=0.8)
    ax2.legend(loc="center right", fontsize=8, frameon=True, facecolor="#FFFFFF", framealpha=0.9)

    fig.tight_layout(pad=1.3)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def make_fig2(out_path: str) -> None:
    """Fig 2: v1 Paradox Audit & Nuclear Valley of Stability (E(x) vs C_fid(x))."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [1.0, 1.2]})

    names = ["home", "mondo", "koan", "riff", "trace", "garlic", "neutral", "white"]
    labels = ["Home", "Mondō", "Kōan", "Riff", "Trace", "Garlic", "Gray", "White"]
    v1_vals = [nc.coherence_v1(nc.PRESETS[n]) for n in names]
    v2_vals = [nc.fidelity_coherence(nc.PRESETS[n]) for n in names]

    y = np.arange(len(names))
    h = 0.36
    ax1.barh(y + h / 2, v1_vals, height=h, color=ORANGE, alpha=0.82, label=r"v1 Norm ratio $\|x_{\mathrm{eff}}\|/\|x\|$")
    ax1.barh(y - h / 2, v2_vals, height=h, color=TEAL, alpha=0.88, label=r"v2 Fidelity $C_{\mathrm{fid}}(x)$")
    ax1.axvline(1.0, color=SLATE, ls=":", lw=1.0)
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=8.8)
    ax1.invert_yaxis()
    ax1.set_xlim(0.65, 1.28)
    ax1.set_xlabel("Coherence Score")
    ax1.set_title("A. White Paradox & Gray Fixed-Point Fix", fontsize=10.5, fontweight="bold", pad=8)
    ax1.grid(True, axis="x", color=GRID_COL, lw=0.6, alpha=0.8)
    ax1.legend(loc="lower right", fontsize=7.8, frameon=True, facecolor="#FFFFFF", framealpha=0.92)

    # Right panel: Valley of Stability scatter over 2,000 samples
    rng = np.random.default_rng(7)
    pts = rng.uniform(0.0, 1.0, size=(2000, 6))
    cfids = [nc.fidelity_coherence(p) for p in pts]
    energies = [nc.binding_energy(p) for p in pts]

    ax2.axhspan(-0.35, 0.0, color=TEAL_HI, alpha=0.09)
    ax2.axhspan(0.0, 0.35, color=ORANGE, alpha=0.08)
    ax2.axhline(0.0, color=PETROL, lw=1.0, ls="--", alpha=0.65)
    ax2.scatter(cfids, energies, s=8, color=SLATE, alpha=0.24, edgecolors="none", label="Random $x \\in [0,1]^6$")

    offsets = {
        "home": (0.016, 0.036),
        "mondo": (-0.014, 0.028),
        "koan": (0.014, -0.024),
        "riff": (-0.042, -0.042),
        "trace": (-0.002, 0.056),
        "garlic": (-0.012, -0.062),
        "neutral": (-0.045, 0.022),
        "white": (-0.052, 0.038),
        "cascade": (-0.045, -0.042),
    }
    disp = {
        "home": "Home", "mondo": "Mondō", "koan": "Kōan", "riff": "Riff",
        "trace": "Trace", "garlic": "Garlic", "neutral": "Gray", "white": "White", "cascade": "Cascade"
    }
    for key in ["home", "mondo", "koan", "riff", "trace", "garlic", "neutral", "white", "cascade"]:
        raw = nc.PRESETS[key]
        cf = nc.fidelity_coherence(raw)
        en = nc.binding_energy(raw)
        hx, _, _, _ = nc.posture_to_hex(raw)
        ax2.scatter([cf], [en], s=75, color=hx, edgecolor=PETROL, linewidth=1.0, zorder=6)
        dx_o, dy_o = offsets[key]
        ax2.annotate(disp[key], xy=(cf, en), xytext=(cf + dx_o, en + dy_o), fontsize=8.0, fontweight="bold", color=PETROL)

    ax2.text(0.695, -0.295, "BOUND REGION  E(x) < 0\n(Valley of Stability)", fontsize=7.8, color=TEAL, fontweight="bold")
    ax2.text(0.695, 0.16, "FRUSTRATED REGION  E(x) > 0", fontsize=7.8, color=ORANGE, fontweight="bold")
    ax2.set_xlim(0.68, 1.02)
    ax2.set_ylim(-0.32, 0.22)
    ax2.set_xlabel(r"Fidelity Coherence $C_{\mathrm{fid}}(x)$")
    ax2.set_ylabel(r"Lyapunov Binding Energy $E(x)$")
    ax2.set_title("B. Nuclear Valley of Stability", fontsize=10.5, fontweight="bold", pad=8)
    ax2.grid(True, color=GRID_COL, lw=0.6, alpha=0.8)

    fig.tight_layout(pad=1.3)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def make_fig3(out_path: str) -> None:
    """Fig 3: Benign Riff vs Adversarial Cascade — Radial Drift False Alarm vs Directional CUSUM & OKLab Strip."""
    home = nc.to_norm(nc.PRESETS["home"])
    traj_riff = nc.simulate_trajectory("benign_riff", steps=16)
    traj_casc = nc.simulate_trajectory("cascade", steps=16)

    cusum_riff = nc.cusum_cascade_detector(traj_riff)
    cusum_casc = nc.cusum_cascade_detector(traj_casc)
    rad_riff = nc.radial_drift_v1(traj_riff, home)
    rad_casc = nc.radial_drift_v1(traj_casc, home)

    fig = plt.figure(figsize=(10.5, 4.7))
    gs = fig.add_gridspec(2, 2, height_ratios=[3.2, 0.75], hspace=0.38, wspace=0.24)

    t_ax = np.arange(len(traj_riff))

    # Top Left: Benign Riff
    ax_tl = fig.add_subplot(gs[0, 0])
    ax_tl.plot(t_ax, rad_riff, color=AMBER, lw=1.8, ls="--", marker="o", markersize=3, label=r"v1 Radial drift $\Delta \|x_t - x_0\|$")
    ax_tl.plot(t_ax, cusum_riff["cusum_series"], color=TEAL, lw=2.3, marker="s", markersize=3.4, label=r"v2 Directional CUSUM $S_t$")
    ax_tl.axhline(0.22, color=ORANGE, ls=":", lw=1.2, label=r"CUSUM threshold $h=0.22$")
    ax_tl.set_title("A. Benign Creative Exploration (Riff)", fontsize=10.2, fontweight="bold", pad=7)
    ax_tl.set_ylabel("Detector Statistic")
    ax_tl.set_ylim(-0.10, 0.55)
    ax_tl.grid(True, color=GRID_COL, lw=0.6)
    ax_tl.legend(loc="upper right", fontsize=7.8, frameon=True, facecolor="#FFFFFF")
    ax_tl.text(4.2, 0.27, "v1 fires false alarm (3+ positive radial steps)\nv2 CUSUM stays 0.000 (no compliance collapse)", fontsize=7.7, color=TEAL,
               bbox=dict(boxstyle="round,pad=0.32", facecolor="#FFFFFF", edgecolor=TEAL, alpha=0.95))

    # Top Right: Adversarial Cascade
    ax_tr = fig.add_subplot(gs[0, 1])
    ax_tr.plot(t_ax, rad_casc, color=AMBER, lw=1.8, ls="--", marker="o", markersize=3, label=r"v1 Radial drift $\Delta \|x_t - x_0\|$")
    ax_tr.plot(t_ax, cusum_casc["cusum_series"], color=ORANGE, lw=2.4, marker="s", markersize=3.4, label=r"v2 Directional CUSUM $S_t$")
    ax_tr.axhline(0.22, color=ORANGE, ls=":", lw=1.2, label=r"CUSUM threshold $h=0.22$")
    alarm_t = cusum_casc["alarm_step"]
    ax_tr.scatter([alarm_t], [cusum_casc["cusum_series"][alarm_t]], color=ORANGE, s=85, zorder=6, edgecolor=PETROL)
    ax_tr.annotate(f"Alarm at step t={alarm_t}", xy=(alarm_t, cusum_casc["cusum_series"][alarm_t]),
                   xytext=(alarm_t + 2.2, 0.30), arrowprops=dict(arrowstyle="->", color=ORANGE), fontsize=8.2, fontweight="bold", color=ORANGE)
    ax_tr.set_title("B. Sustained Adversarial Compliance Cascade", fontsize=10.2, fontweight="bold", pad=7)
    ax_tr.set_ylim(-0.10, 0.55)
    ax_tr.grid(True, color=GRID_COL, lw=0.6)
    ax_tr.legend(loc="lower right", fontsize=7.8, frameon=True, facecolor="#FFFFFF")

    # Bottom color strips: OKLab color evolution t=0..16
    for col_idx, (traj, caption) in enumerate([(traj_riff, "OKLab Color Strip — Benign Exploration (stays Teal/Mint)"), (traj_casc, "OKLab Color Strip — Compliance Cascade (Teal → Burnt Orange)")]):
        ax_b = fig.add_subplot(gs[1, col_idx])
        for step_i in range(len(traj)):
            hx, _, _, _ = nc.posture_to_hex(traj[step_i])
            rect = patches.Rectangle((step_i, 0), 1.0, 1.0, facecolor=hx, edgecolor="#FFFFFF", linewidth=0.6)
            ax_b.add_patch(rect)
        ax_b.set_xlim(0, len(traj))
        ax_b.set_ylim(0, 1)
        ax_b.set_yticks([])
        ax_b.set_xticks([0, 4, 8, 12, 16])
        ax_b.set_xlabel(caption, fontsize=8.4, fontweight="bold", color=PETROL)

    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def make_fig4(emp: dict, out_path: str) -> None:
    """Fig 4: Real Offline distilgpt2 Spectrometer Results & Empirical Correlation Sign Audit."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3), gridspec_kw={"width_ratios": [1.05, 1.0]})

    recs = emp["prompt_records"]
    regime_labels = {
        "mondo": "Mondō",
        "koan": "Kōan",
        "riff": "Riff",
        "trace": "Trace",
        "garlic": "Garlic",
    }
    markers = {"mondo": "o", "koan": "^", "riff": "s", "trace": "D", "garlic": "P"}

    for regime in ["mondo", "trace", "riff", "koan", "garlic"]:
        sub = [r for r in recs if r["regime"] == regime]
        xs = [r["A_005"] for r in sub]
        ys = [r["M4_root"] for r in sub]
        cols = [r["hex"] for r in sub]
        ax1.scatter(xs, ys, c=cols, s=70, marker=markers[regime], edgecolor=PETROL, linewidth=0.9, label=regime_labels[regime], zorder=4)

        # Plot regime centroid star
        mx, my = float(np.mean(xs)), float(np.mean(ys))
        chex = emp["regime_summary"][regime]["hex"]
        ax1.scatter([mx], [my], c=[chex], s=180, marker="*", edgecolor=PETROL, linewidth=1.1, zorder=6)

    ax1.set_xlabel(r"Mean Accessible Volume $\bar{A}_{0.005}(p)$")
    ax1.set_ylabel(r"Quartic Spectral Concentration $\bar{M}_4^{1/4}(p)$")
    ax1.set_title("A. Real distilgpt2 Spectral Separation (n=30 prompts)", fontsize=10.0, fontweight="bold", pad=8)
    ax1.grid(True, color=GRID_COL, lw=0.6)
    ax1.legend(loc="upper right", fontsize=8.0, frameon=True, facecolor="#FFFFFF", title="Regime (★ centroid)", title_fontsize=7.8)

    # Right panel: Comparison of Hypothesized M (upper triangle) vs Empirical corr (lower triangle)
    corr = np.array(emp["empirical_correlation_matrix"], dtype=float)
    combined = np.zeros((6, 6), dtype=float)
    for i in range(6):
        for j in range(6):
            if i == j:
                combined[i, j] = 1.0
            elif i < j:
                combined[i, j] = nc.M_CANONICAL[i, j]
            else:
                combined[i, j] = corr[i, j]

    im = ax2.imshow(combined, cmap="RdBu_r", vmin=-0.85, vmax=0.85)
    # Draw diagonal separator line
    ax2.plot([-0.5, 5.5], [-0.5, 5.5], color=PETROL, lw=1.4)

    short_axes = ["Comp", "Crea", "Tran", "Warm", "Auto", "Cert"]
    ax2.set_xticks(range(6))
    ax2.set_xticklabels(short_axes, fontsize=8.5, rotation=20)
    ax2.set_yticks(range(6))
    ax2.set_yticklabels(short_axes, fontsize=8.5)
    ax2.set_title("B. Hypothesized M (upper) vs Empirical distilgpt2 (lower)", fontsize=9.8, fontweight="bold", pad=8)

    for i in range(6):
        for j in range(6):
            val = combined[i, j]
            txt_col = "#FFFFFF" if abs(val) > 0.45 else PETROL
            if i == j:
                ax2.text(j, i, "1.0", ha="center", va="center", color="#FFFFFF", fontsize=7.8, fontweight="bold")
            else:
                ax2.text(j, i, f"{val:+.2f}", ha="center", va="center", color=txt_col, fontsize=7.6, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=7.5)

    fig.tight_layout(pad=1.3)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    fig_dir = os.path.join(ROOT, "experiments", "figures")
    os.makedirs(fig_dir, exist_ok=True)
    res_path = os.path.join(ROOT, "experiments", "results.json")

    if "--plots-only" in sys.argv and os.path.exists(res_path):
        with open(res_path, encoding="utf-8") as f:
            results = json.load(f)
        emp = results["distilgpt2_empirical"]
        make_fig1(os.path.join(fig_dir, "fig1_stability_phase.pdf"))
        make_fig2(os.path.join(fig_dir, "fig2_valley_of_stability.pdf"))
        make_fig3(os.path.join(fig_dir, "fig3_cascade_cusum.pdf"))
        make_fig4(emp, os.path.join(fig_dir, "fig4_distilgpt2_empirical.pdf"))
        print("Re-generated 4 figures from existing results.json")
        return

    print("1/4 Running theoretical Monte Carlo + cascade ROC...")
    mc_roc = run_monte_carlo_and_roc()

    print("2/4 Running offline distilgpt2 spectrometer...")
    emp = ms.run_offline_spectrometer()

    print("3/4 Generating 4 publication figures...")
    make_fig1(os.path.join(fig_dir, "fig1_stability_phase.pdf"))
    make_fig2(os.path.join(fig_dir, "fig2_valley_of_stability.pdf"))
    make_fig3(os.path.join(fig_dir, "fig3_cascade_cusum.pdf"))
    make_fig4(emp, os.path.join(fig_dir, "fig4_distilgpt2_empirical.pdf"))

    # Metamer verification record
    base = nc.to_norm(nc.PRESETS["home"])
    hx0, _, lab0, _ = nc.posture_to_hex(base)
    metamers = []
    for k in range(3):
        alt = nc.sample_metamer(base, direction_idx=k, step_scale=0.22)
        hx1, _, lab1, _ = nc.posture_to_hex(alt)
        metamers.append(
            {
                "nullspace_axis": k,
                "raw_255": nc.to_255(alt),
                "hex": hx1,
                "delta_E_OK": float(np.linalg.norm(lab1 - lab0)),
                "dist_6D": round(float(np.linalg.norm(alt - base)), 4),
            }
        )

    presets_audit = {}
    for name, raw in nc.PRESETS.items():
        hx, rgb, lab, ig = nc.posture_to_hex(raw)
        presets_audit[name] = {
            "raw_255": raw,
            "eff_v1_255": nc.to_255(nc.effective_v1(raw)),
            "eff_v2_255": nc.to_255(nc.effective_v2(raw)),
            "coherence_v1": round(nc.coherence_v1(raw), 4),
            "C_fid_v2": round(nc.fidelity_coherence(raw), 4),
            "E_binding": round(nc.binding_energy(raw), 4),
            "F_frustration": round(nc.frustration_index(raw), 4),
            "hex_oklab": hx,
            "oklab": [round(float(z), 5) for z in lab],
            "in_gamut": ig,
        }

    results = {
        "stability_bounds": nc.stability_bounds(),
        "oklab_calibration": {
            "y0": [round(float(z), 6) for z in nc.Y0_OK],
            "P_OK": [[round(float(v), 6) for v in row] for row in nc.P_OK],
            "N_nullspace_6x3": [[round(float(v), 6) for v in row] for row in nc.N_NULL],
            "metamer_verification": metamers,
        },
        "presets_audit": presets_audit,
        "monte_carlo_and_roc": mc_roc,
        "distilgpt2_empirical": emp,
    }

    res_path = os.path.join(ROOT, "experiments", "results.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"4/4 Saved {res_path}")
    print("MC & ROC summary:", json.dumps(mc_roc, indent=2))


if __name__ == "__main__":
    main()

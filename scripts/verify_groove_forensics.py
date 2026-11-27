#!/usr/bin/env python3
"""Independent Verifier & Gallery-Grade Poincare Plate Renderer for Groove Forensics (#11)."""

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

from guiai.gem.groove_forensics import run_groove_forensics_suite


def render_groove_poincare_plate(report: dict, out_path: Path) -> None:
    plt.rcParams.update({
        "figure.facecolor": "#070B14",
        "axes.facecolor": "#0D1526",
        "axes.edgecolor": "#263754",
        "axes.labelcolor": "#DCE7F7",
        "xtick.color": "#9DB2D1",
        "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF",
        "font.family": "DejaVu Sans",
        "grid.color": "#1C2A42",
        "grid.alpha": 0.65,
    })

    profiles = report["profiles"]
    p_map = {p["name"]: p for p in profiles}

    fig = plt.figure(figsize=(18.0, 10.6), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.36, wspace=0.28, left=0.055, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "Zoe Groove Forensics & Polyrhythmic Temporal Dynamics :: 2D Poincare Attractors x Kloster A_tau(p)",
        fontsize=16, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Computed Acoustic Telemetry  |  Human Pocket Swing  |  3:2 / 4:3 / 5:4 Polyrhythms  |  Real ProTracker .MOD (M.K.)  |  Poisson Negative Control  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.8, color="#7CE8FF",
    )

    # Panels A, B, C: 2D Poincare Return Maps (r_{t-1}, r_t)
    poincare_specs = [
        ("human_dilla_pocket_swing", "A. Human J-Dilla Pocket Swing (2-Lobe Attractor)", "#FFB84D", 0),
        ("polyrhythm_3_2_clave", "B. Afro-Cuban 3:2 Polyrhythm (Multi-Cluster)", "#00E5FF", 1),
        ("negative_control_poisson_noise", "C. Negative Control: Poisson Random Noise", "#FF5C8A", 2),
    ]
    for key, title, col, col_idx in poincare_specs:
        ax = fig.add_subplot(gs[0, col_idx])
        pr = p_map[key]
        x = np.asarray(pr["poincare_x_ms"])
        y = np.asarray(pr["poincare_y_ms"])
        ax.plot(x, y, color=col, alpha=0.18, linewidth=0.9)
        ax.scatter(x, y, c=np.arange(len(x)), cmap="cool" if col == "#00E5FF" else ("autumn" if col == "#FFB84D" else "magma"),
                   s=26, alpha=0.88, edgecolors="#070B14", linewidths=0.35)
        ax.axhline(0, color="#3A4F73", linestyle=":", linewidth=1.0)
        ax.axvline(0, color="#3A4F73", linestyle=":", linewidth=1.0)
        lim = max(32.0, float(np.max(np.abs(np.concatenate([x, y])))) * 1.15) if x.size else 35.0
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_xlabel("Residual r_{t-1} (ms)", fontsize=9)
        ax.set_ylabel("Residual r_t (ms)", fontsize=9)
        ax.set_title(title, fontsize=10.6, fontweight="bold", color=col, pad=8)
        ax.grid(True, linestyle="--", linewidth=0.6)
        ax.text(
            0.03, 0.96,
            f"SD1={pr['sd1_ms']:.1f}ms  SD2={pr['sd2_ms']:.1f}ms\nM4^(1/4)={pr['kloster_m4_root']:.3f}  H2={pr['kloster_renyi_h2']:.2f}",
            transform=ax.transAxes, va="top", fontsize=7.9, color="#EEF5FF",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#09101E", edgecolor=col, alpha=0.9),
        )

    # Panel D: Polyrhythmic Phase-Locking Values (PLV) vs Negative Control
    ax_d = fig.add_subplot(gs[1, 0])
    plvs = report["polyrhythm_plv_summary"]
    plv_labels = ["3:2 Clave", "4:3 Cross", "5:4 Quint", "Poisson\n(Neg Ctrl)"]
    plv_vals = [plvs["3:2_clave"], plvs["4:3_cross"], plvs["5:4_quint"], plvs["negative_control_poisson"]]
    plv_cols = ["#00E5FF", "#63F5B5", "#FFB84D", "#FF5C8A"]
    bars = ax_d.bar(plv_labels, plv_vals, color=plv_cols, width=0.56, edgecolor="#070B14", linewidth=1.0)
    for b, v in zip(bars, plv_vals):
        ax_d.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.3f}", ha="center", fontsize=9.2, fontweight="bold")
    ax_d.set_ylim(0, 1.15)
    ax_d.set_ylabel("Cross-Frequency Phase-Locking Value (PLV)", fontsize=9)
    ax_d.set_title("D. Polyrhythmic Phase-Locking vs Noise Control", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.6)

    # Panel E: Cross-Pollinated #5 Kloster M_4^(1/4) Purity vs Renyi H_2 Across All 5 Archetypes
    ax_e = fig.add_subplot(gs[1, 1])
    short = ["Rigid\n120BPM", "J-Dilla\nSwing", "3:2\nClave", "Amiga\n.MOD", "Poisson\nNoise"]
    m4s = [p["kloster_m4_root"] for p in profiles]
    h2s = [p["kloster_renyi_h2"] for p in profiles]
    x_i = np.arange(len(profiles))
    ax_e.bar(x_i - 0.18, m4s, width=0.34, color="#00E5FF", label="Kloster M_4^(1/4) Purity")
    ax_e2 = ax_e.twinx()
    ax_e2.bar(x_i + 0.18, h2s, width=0.34, color="#FFB84D", alpha=0.88, label="Kloster Renyi H_2 (nats)")
    ax_e.set_xticks(x_i)
    ax_e.set_xticklabels(short, fontsize=8.3)
    ax_e.set_ylim(0, 1.18)
    ax_e2.set_ylim(0, max(3.6, max(h2s) * 1.32))
    ax_e.set_ylabel("Quartic Purity M_4^(1/4)", fontsize=9, color="#00E5FF")
    ax_e2.set_ylabel("Renyi Entropy H_2 (nats)", fontsize=9, color="#FFB84D")
    ax_e.set_title("E. Kloster Rhythmic Predictability Hierarchy (#5 x #11)", fontsize=10.8, fontweight="bold", color="#7CE8FF", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_e.legend(loc="upper left", fontsize=7.8, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax_e2.legend(loc="upper right", fontsize=7.8, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel F: Kloster Spectral Distance Matrix D_K(p_IOI, q_IOI) Separating All 5 Rhythmic Worlds
    ax_f = fig.add_subplot(gs[1, 2])
    dk = np.asarray(report["kloster_dk_matrix"], dtype=np.float64)
    im = ax_f.imshow(dk, cmap="magma", vmin=0.0, vmax=max(1.2, float(dk.max())))
    short_m = ["Rigid", "Dilla", "3:2", ".MOD", "Poisson"]
    ax_f.set_xticks(np.arange(5))
    ax_f.set_xticklabels(short_m, fontsize=8.5)
    ax_f.set_yticks(np.arange(5))
    ax_f.set_yticklabels(short_m, fontsize=8.5)
    for i in range(5):
        for j in range(5):
            ax_f.text(j, i, f"{dk[i, j]:.2f}", ha="center", va="center", fontsize=8.0,
                      color="#070B14" if dk[i, j] > 0.9 else "#EEF5FF", fontweight="bold")
    ax_f.set_title("F. Kloster Spectral Distance D_K Across Grooves", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    cb = fig.colorbar(im, ax=ax_f, fraction=0.046, pad=0.03)
    cb.set_label("D_K = ||p↓ - q↓||_1", fontsize=8.2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    report = run_groove_forensics_suite()
    ev_path = ROOT / "evidence/groove-forensics/groove-forensics-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-groove-forensics-poincare.png"
    render_groove_poincare_plate(report, fig_path)

    checks = list(report["checks"].items()) + [
        ("poincare_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

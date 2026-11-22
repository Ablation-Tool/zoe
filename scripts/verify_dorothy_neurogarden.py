#!/usr/bin/env python3
"""Independent Verifier & 6-Panel 3D Neuroanatomy Plate Renderer for Dorothy's Neurogarden (#6)."""

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

from guiai.gem.dorothy_neurogarden_3d import run_dorothy_neurogarden_3d_suite


def render_dorothy_neurogarden_plate(report: dict, tomo: dict, out_path: Path) -> None:
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
        "grid.alpha": 0.6,
    })

    fig = plt.figure(figsize=(18.5, 11.0), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.26, left=0.05, right=0.975, top=0.89, bottom=0.07)

    fig.suptitle(
        "Dorothy's Neurogarden :: 12-Region Allen Mouse CCFv3 3D Connectome, 40 Hz Gamma Kuramoto & Tomography",
        fontsize=15.5, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"In Honor of Dorothy McEwen Kildall  |  {report['total_3d_triangles']:,} Real 3D Allen CCFv3 Triangles  |  PRECLINICAL RESEARCH ONLY (clinical_action_authorized=False)  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.6, color="#63F5B5",
    )

    regions = report["regions"]
    reg_by_acr = {r["acronym"]: r for r in regions}
    k_h = report["kuramoto_40hz_gamma"]["healthy_coupled"]
    k_l = report["kuramoto_40hz_gamma"]["lesion_disconnection"]
    k_u = report["kuramoto_40hz_gamma"]["negative_control_uncoupled"]

    # Panel A: 3D Stereotaxic Allen CCFv3 Connectome Graph (12 Real Centroids + Proximity Tracts)
    ax_a = fig.add_subplot(gs[0, 0], projection="3d")
    ax_a.set_facecolor("#091120")
    for edge in report["connectome"]["top_edges"]:
        c1 = reg_by_acr[edge["u"]]["centroid"]
        c2 = reg_by_acr[edge["v"]]["centroid"]
        ax_a.plot([c1[0], c2[0]], [c1[1], c2[1]], [c1[2], c2[2]], color="#00E5FF", alpha=min(0.85, edge["weight"] * 0.9), linewidth=1.6)
    xs = [r["centroid"][0] for r in regions]
    ys = [r["centroid"][1] for r in regions]
    zs = [r["centroid"][2] for r in regions]
    sizes = [max(45, min(280, r["triangles"] / 250.0)) for r in regions]
    ax_a.scatter(xs, ys, zs, s=sizes, c="#63F5B5", edgecolor="#FFFFFF", linewidth=0.8, alpha=0.95)
    z_span = max(20.0, max(zs) - min(zs))
    for i, r in enumerate(regions):
        c = r["centroid"]
        dz = (0.04 if i % 2 == 0 else -0.05) * z_span
        ax_a.text(c[0], c[1], c[2] + dz, r["acronym"], fontsize=6.6, color="#FFB84D", fontweight="bold")
    ax_a.set_xlabel("AP (μm)", fontsize=8, labelpad=2)
    ax_a.set_ylabel("DV (μm)", fontsize=8, labelpad=2)
    ax_a.set_zlabel("ML (μm)", fontsize=8, labelpad=2)
    ax_a.tick_params(labelsize=6.5)
    ax_a.set_title(f"A. 3D CCFv3 Connectome ({report['connectome']['edges']} Tracts)", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=6)

    # Panel B: 40 Hz Gamma Kuramoto Synchronization Order Parameter R(t) Across Regimes
    ax_b = fig.add_subplot(gs[0, 1])
    t_ms = np.arange(len(k_h["r_trace"])) * 8.0  # 4 steps * 2 ms
    ax_b.plot(t_ms, k_h["r_trace"], color="#63F5B5", linewidth=2.4, label=f"Healthy Coupled (R={k_h['steady_order_r']:.3f})")
    ax_b.plot(t_ms, k_l["r_trace"], color="#FFB84D", linewidth=2.2, linestyle="--", label=f"Hub Disconnection (R={k_l['steady_order_r']:.3f})")
    ax_b.plot(t_ms, k_u["r_trace"], color="#FF5C8A", linewidth=1.9, linestyle=":", label=f"Uncoupled Neg Ctrl (R={k_u['steady_order_r']:.3f})")
    ax_b.set_ylim(0.0, 1.08)
    ax_b.set_xlabel("Simulated Gamma Time (ms @ 40 Hz)", fontsize=9)
    ax_b.set_ylabel("Kuramoto Synchronization Order R(t)", fontsize=9)
    ax_b.set_title("B. 40 Hz Gamma Kuramoto Phase-Locking (#11 x #6)", fontsize=10.8, fontweight="bold", color="#00E5FF", pad=8)
    ax_b.grid(True, linestyle="--", linewidth=0.6)
    ax_b.legend(loc="lower right", fontsize=8.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: Cross-Pollinated #5 Kloster Phase Purity M_4^(1/4) vs Renyi H_2
    ax_c = fig.add_subplot(gs[0, 2])
    cats = ["Healthy\n40Hz Gamma", "Hub Lesion\nModel", "Uncoupled\n(Neg Ctrl)"]
    m4s = [k_h["kloster_phase_m4"], k_l["kloster_phase_m4"], k_u["kloster_phase_m4"]]
    h2s = [k_h["kloster_phase_renyi_h2"], k_l["kloster_phase_renyi_h2"], k_u["kloster_phase_renyi_h2"]]
    x = np.arange(3)
    ax_c.bar(x - 0.18, m4s, width=0.34, color="#00E5FF", label="Kloster Phase M_4^(1/4)")
    ax_c2 = ax_c.twinx()
    ax_c2.bar(x + 0.18, h2s, width=0.34, color="#FFB84D", alpha=0.88, label="Kloster Renyi H_2 (nats)")
    for i, (mv, hv) in enumerate(zip(m4s, h2s)):
        ax_c.text(i - 0.18, mv + 0.02, f"{mv:.2f}", ha="center", fontsize=8.5, color="#7CE8FF", fontweight="bold")
        ax_c2.text(i + 0.18, hv + 0.07, f"{hv:.2f}", ha="center", fontsize=8.5, color="#FFB84D", fontweight="bold")
    ax_c.set_xticks(x)
    ax_c.set_xticklabels(cats, fontsize=8.8)
    ax_c.set_ylim(0, max(0.85, max(m4s) * 1.32))
    ax_c2.set_ylim(0, max(3.6, max(h2s) * 1.32))
    ax_c.set_ylabel("Kloster Phase Purity M_4^(1/4)", fontsize=9, color="#00E5FF")
    ax_c2.set_ylabel("Kloster Phase Renyi H_2 (nats)", fontsize=9, color="#FFB84D")
    ax_c.set_title("C. Kloster Spectral Phase Coherence (#5 x #6)", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_c.legend(loc="upper left", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax_c2.legend(loc="upper right", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panels D, E, F: Multi-Plane Volumetric Slice Tomography (Coronal, Sagittal, Horizontal)
    planes = [
        ("coronal_yz", "D. Coronal Tomography (DV x ML Projection)", "magma", 0),
        ("sagittal_xy", "E. Sagittal Tomography (AP x DV Projection)", "inferno", 1),
        ("horizontal_xz", "F. Horizontal Tomography (AP x ML Projection)", "viridis", 2),
    ]
    for pkey, title, cmap, cidx in planes:
        ax = fig.add_subplot(gs[1, cidx])
        arr = np.log1p(np.asarray(tomo[pkey], dtype=np.float64)).T
        im = ax.imshow(arr, origin="lower", cmap=cmap, aspect="auto")
        ax.set_title(title, fontsize=10.6, fontweight="bold", color="#7CE8FF" if cidx == 0 else ("#FFB84D" if cidx == 1 else "#63F5B5"), pad=8)
        ax.set_xlabel("Grid Bin", fontsize=8.5)
        ax.set_ylabel("Grid Bin", fontsize=8.5)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
        cb.set_label("ln(1 + CCFv3 Vertex Density)", fontsize=7.8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    report = run_dorothy_neurogarden_3d_suite()
    tomo = report.pop("_tomography_arrays")

    ev_path = ROOT / "evidence/dorothy-neurogarden/dorothy-neurogarden-3d-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-dorothy-neurogarden-3d.png"
    render_dorothy_neurogarden_plate(report, tomo, fig_path)

    checks = list(report["checks"].items()) + [
        ("neurogarden_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 50_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

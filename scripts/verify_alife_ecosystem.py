#!/usr/bin/env python3
"""Independent Verifier & Generative Ecology Plate Renderer for Zoe ALife Ecosystem (#9)."""

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

from guiai.gem.alife_ecosystem import run_alife_ecosystem_suite


def render_alife_plate(report: dict, viz: dict, out_path: Path) -> None:
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

    liv = report["evolving_ecosystem"]
    neg = report["negative_control_no_replication"]

    fig = plt.figure(figsize=(18.2, 10.6), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.27, left=0.055, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "Zoe Creative Playroom :: Open-Ended Self-Replicating Artificial Life Ecosystem (#9 x #5 x #3 x #8)",
        fontsize=15.5, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Computed ALife Ecology  |  Births: {liv['births']}  |  Max Gen: {liv['max_generation']}  |  Final Pop: {liv['final_pop']} vs Static Ctrl: {neg['final_pop']}  |  Soundscape WAV: {report['soundscape_wav']['duration_sec']}s  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.6, color="#63F5B5",
    )

    # Panel A: Live 2D Toroidal Nutrient Blooms + Geometric Organisms Colored by Metabolic Efficiency
    ax_a = fig.add_subplot(gs[0, 0])
    nut = np.asarray(viz["nutrients"], dtype=np.float64)
    ax_a.imshow(nut, origin="lower", cmap="magma", alpha=0.85, extent=[0, 48, 0, 48])
    agents = np.asarray(viz["final_agents"], dtype=np.float64)
    if agents.size:
        sc = ax_a.scatter(
            agents[:, 0], agents[:, 1],
            s=40 + 35 * agents[:, 3],
            c=agents[:, 6], cmap="cool", vmin=0.3, vmax=1.0,
            edgecolor="#FFFFFF", linewidth=0.55, alpha=0.92,
        )
        cb = fig.colorbar(sc, ax=ax_a, fraction=0.046, pad=0.03)
        cb.set_label("Evolved Metabolic Efficiency", fontsize=7.8)
    ax_a.set_xlim(0, 48)
    ax_a.set_ylim(0, 48)
    ax_a.set_xlabel("Toroidal X", fontsize=9)
    ax_a.set_ylabel("Toroidal Y", fontsize=9)
    ax_a.set_title("A. Living Nutrient Field & Evolved Organisms", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=8)

    # Panel B: Generative Foraging Orbit Trails (Kloster M_4^(1/4) Curiosity Navigation)
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.set_facecolor("#070D1B")
    palette = ["#00E5FF", "#63F5B5", "#FFB84D", "#FF5C8A", "#A78BFA", "#38BDF8"]
    for idx, traj in enumerate(viz["trajectories"]):
        if len(traj) < 3:
            continue
        pts = np.asarray(traj)
        # Break lines on toroidal wraparound jumps
        diffs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        seg_start = 0
        col = palette[idx % len(palette)]
        for k, d in enumerate(diffs):
            if d > 15.0:
                ax_b.plot(pts[seg_start : k + 1, 0], pts[seg_start : k + 1, 1], color=col, alpha=0.72, linewidth=1.25)
                seg_start = k + 1
        ax_b.plot(pts[seg_start:, 0], pts[seg_start:, 1], color=col, alpha=0.72, linewidth=1.25)
        ax_b.scatter([pts[-1, 0]], [pts[-1, 1]], s=28, color=col, edgecolor="#FFFFFF", linewidth=0.4, zorder=5)
    ax_b.set_xlim(0, 48)
    ax_b.set_ylim(0, 48)
    ax_b.set_xlabel("Toroidal X", fontsize=9)
    ax_b.set_ylabel("Toroidal Y", fontsize=9)
    ax_b.set_title("B. Kloster Curiosity Foraging Trajectories (12 Lineages)", fontsize=10.8, fontweight="bold", color="#00E5FF", pad=8)
    ax_b.grid(True, linestyle=":", linewidth=0.5)

    # Panel C: Population Dynamics — Evolving Living Ecology vs Non-Replicating Negative Control
    ax_c = fig.add_subplot(gs[0, 2])
    steps = np.arange(len(liv["pop_trace"]))
    ax_c.plot(steps, liv["pop_trace"], color="#63F5B5", linewidth=2.4, label=f"Evolving Ecology (final={liv['final_pop']})")
    ax_c.plot(steps, neg["pop_trace"], color="#FF5C8A", linewidth=2.1, linestyle="--", label=f"Static Neg Ctrl (final={neg['final_pop']})")
    ax_c.fill_between(steps, neg["pop_trace"], liv["pop_trace"], color="#63F5B5", alpha=0.12)
    ax_c.set_xlabel("Ecological Tick", fontsize=9)
    ax_c.set_ylabel("Living Organism Count", fontsize=9)
    ax_c.set_title("C. Carrying Capacity vs Zero-Replication Control", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    ax_c.grid(True, linestyle="--", linewidth=0.6)
    ax_c.legend(loc="upper left", fontsize=8.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel D: Darwinian Natural Selection Trajectory (Metabolic Efficiency & Kloster Curiosity)
    ax_d = fig.add_subplot(gs[1, 0])
    ax_d.plot(steps, liv["eff_trace"], color="#00E5FF", linewidth=2.3, label="Mean Metabolic Efficiency (Evolving)")
    ax_d.plot(steps, liv["cur_trace"], color="#FFB84D", linewidth=2.0, label="Mean Kloster Curiosity Gene")
    ax_d.plot(steps, neg["eff_trace"], color="#FF5C8A", linewidth=1.6, linestyle=":", label="Efficiency (Static Neg Ctrl)")
    ax_d.set_xlabel("Ecological Tick", fontsize=9)
    ax_d.set_ylabel("Mean Genome Trait Value", fontsize=9)
    ax_d.set_title("D. Heritable Natural Selection Across Generations", fontsize=10.8, fontweight="bold", color="#7CE8FF", pad=8)
    ax_d.grid(True, linestyle="--", linewidth=0.6)
    ax_d.legend(loc="lower right", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel E: Emergent Polygon Morphological Clades (3..8 Sides)
    ax_e = fig.add_subplot(gs[1, 1])
    md = liv["morph_distribution"]
    sides_lbl = [f"{s}-gon" for s in md.keys()]
    counts = list(md.values())
    cols_e = ["#00E5FF", "#38BDF8", "#63F5B5", "#FFB84D", "#A78BFA", "#FF5C8A"]
    bars_e = ax_e.bar(sides_lbl, counts, color=cols_e, width=0.58)
    for b, c in zip(bars_e, counts):
        ax_e.text(b.get_x() + b.get_width() / 2, c + max(1, max(counts) * 0.03), str(c), ha="center", fontsize=9.0, fontweight="bold")
    ax_e.set_ylim(0, max(10, max(counts) * 1.22))
    ax_e.set_ylabel("Surviving Organisms", fontsize=9)
    ax_e.set_title(f"E. Emergent Clades (Kloster H_2={liv['morphological_renyi_h2']:.2f})", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.6)

    # Panel F: Evolved Speed vs Efficiency Niche Partitioning
    ax_f = fig.add_subplot(gs[1, 2])
    if agents.size:
        sc_f = ax_f.scatter(agents[:, 4], agents[:, 6], s=55, c=agents[:, 8], cmap="plasma", edgecolor="#FFFFFF", linewidth=0.5, alpha=0.9)
        cb_f = fig.colorbar(sc_f, ax=ax_f, fraction=0.046, pad=0.03)
        cb_f.set_label("Lineage Generation Depth", fontsize=7.8)
    ax_f.set_xlabel("Locomotion Speed Gene", fontsize=9)
    ax_f.set_ylabel("Metabolic Efficiency Gene", fontsize=9)
    ax_f.set_title("F. Ecological Niche Partitioning (Speed vs Efficiency)", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    ax_f.grid(True, linestyle="--", linewidth=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    report = run_alife_ecosystem_suite(Path("/tmp/zoe_alife_soundscape.wav"))
    viz = report.pop("_viz")

    ev_path = ROOT / "evidence/alife-ecosystem/zoe-alife-ecosystem-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-creative-alife-ecosystem.png"
    render_alife_plate(report, viz, fig_path)

    checks = list(report["checks"].items()) + [("alife_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000)]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

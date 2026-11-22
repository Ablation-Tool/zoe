#!/usr/bin/env python3
"""Independent Verifier & 6-Panel Dark-Collider Plate Renderer for CERN/HELIOS Kloster Trigger (#7)."""

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

from guiai.gem.cern_kloster_trigger import run_cern_kloster_trigger_suite


def render_cern_plate(report: dict, out_path: Path) -> None:
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

    fig = plt.figure(figsize=(18.2, 10.6), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.27, left=0.055, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "CERN / HELIOS Detector Trigger Forensics :: Kloster M_4^(1/4) x A_tau(p) vs Classical Thresholds",
        fontsize=15.8, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Computed Physics Telemetry  |  400 Multi-Channel Collisions (160 Jets, 160 Pileup, 80 Hot-Spikes)  |  Real VCD Trace ({report['vcd_forensics']['events']} events)  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.7, color="#7CE8FF",
    )

    ch = np.arange(64)
    sp = report["sample_profiles"]

    # Panel A: Sample Calorimeter Channel Profiles (Jet vs Pileup vs Single-Channel Hot-Spike)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.plot(ch, sp["signal_jet"], color="#00E5FF", linewidth=2.1, label="True Particle Jet Shower")
    ax_a.plot(ch, sp["bg_pileup"], color="#63F5B5", linewidth=1.5, alpha=0.8, label="Diffuse Pileup Background")
    ax_a.plot(ch, sp["bg_hotspike"], color="#FF5C8A", linewidth=1.7, linestyle="--", label="Single-Cell Hot-Spike Glitch")
    ax_a.set_xlabel("Calorimeter Tower Channel Index (0..63)", fontsize=9)
    ax_a.set_ylabel("Deposited Energy (GeV)", fontsize=9)
    ax_a.set_title("A. Multi-Channel Calorimeter Readout Profiles", fontsize=10.8, fontweight="bold", color="#7CE8FF", pad=8)
    ax_a.grid(True, linestyle="--", linewidth=0.6)
    ax_a.legend(loc="upper right", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: 2D Kloster Phase-Space Separation (A_0.04 Multi-Tower Coherence vs M_4^(1/4))
    ax_b = fig.add_subplot(gs[0, 1])
    sc = report["scatter_telemetry"]
    et = np.asarray(sc["event_types"])
    m4 = np.asarray(sc["m4_root"])
    a4 = np.asarray(sc["a_004"])
    for key, col, lbl, mk in (
        ("bg_diffuse_pileup", "#63F5B5", "Diffuse Pileup", "o"),
        ("bg_single_hotspike", "#FF5C8A", "Single Hot-Spike (A=1)", "X"),
        ("signal_jet_shower", "#00E5FF", "True Jet Shower (A>=3)", "^"),
    ):
        mask = et == key
        ax_b.scatter(a4[mask] + np.random.default_rng(7).normal(0, 0.12, mask.sum()), m4[mask], s=26, color=col, alpha=0.8, marker=mk, label=lbl)
    ax_b.axvline(2.5, color="#FFB84D", linestyle="--", linewidth=1.8, label="Kloster Coherence Gate A>=3")
    ax_b.set_xlabel("Accessible Tower Count A_0.055(p)", fontsize=9)
    ax_b.set_ylabel("Kloster Quartic Purity M_4^(1/4)", fontsize=9)
    ax_b.set_title("B. Kloster (A_τ, M_4^(1/4)) Topological Separation", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    ax_b.grid(True, linestyle="--", linewidth=0.6)
    ax_b.legend(loc="upper right", fontsize=7.5, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: Trigger AUROC Comparison
    ax_c = fig.add_subplot(gs[0, 2])
    au = report["auroc"]
    names = ["Peak\nAmplitude", "Total\nEnergy", "Inverse\nShannon", "Kloster\nM_4 x A_τ"]
    vals = [au["classical_peak_amplitude"], au["classical_total_energy"], au["classical_inv_shannon"], au["kloster_m4_coherent_a_tau"]]
    cols = ["#FF5C8A", "#A78BFA", "#FFB84D", "#00E5FF"]
    bars = ax_c.bar(names, vals, color=cols, width=0.56)
    for b, v in zip(bars, vals):
        ax_c.text(b.get_x() + b.get_width() / 2, v + 0.025, f"{v:.3f}", ha="center", fontsize=9.2, fontweight="bold")
    ax_c.set_ylim(0, 1.15)
    ax_c.set_ylabel("Trigger Discrimination AUROC", fontsize=9)
    ax_c.set_title("C. Global Trigger AUROC (400 Collisions)", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.6)

    # Panel D: Signal Efficiency (TPR) at Strict 5% False Trigger Rate
    ax_d = fig.add_subplot(gs[1, 0])
    tp = report["tpr_at_5pct_fpr"]
    tvals = [tp["classical_peak_amplitude"], tp["classical_total_energy"], tp["classical_inv_shannon"], tp["kloster_m4_coherent_a_tau"]]
    bars_d = ax_d.bar(names, tvals, color=cols, width=0.56)
    for b, v in zip(bars_d, tvals):
        ax_d.text(b.get_x() + b.get_width() / 2, v + 0.025, f"{v*100:.1f}%", ha="center", fontsize=9.0, fontweight="bold")
    ax_d.set_ylim(0, 1.15)
    ax_d.set_ylabel("Signal Efficiency @ 5% FPR", fontsize=9)
    ax_d.set_title("D. High-Purity Efficiency @ 5% False Trigger Rate", fontsize=10.8, fontweight="bold", color="#7CE8FF", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.6)

    # Panel E: Single-Channel Hot-Spike Glitch False Trigger Rate + Pure Thermal Control
    ax_e = fig.add_subplot(gs[1, 1])
    hs = report["hotspike_false_trigger_rate"]
    neg = report["negative_control_pure_thermal"]["false_trigger_rate"]
    e_lbls = ["Classical Peak\n(Hot-Spikes)", "Kloster M_4 x A_τ\n(Hot-Spikes)", "Kloster M_4 x A_τ\n(Thermal Neg Ctrl)"]
    e_vals = [hs["classical_peak_amplitude"], hs["kloster_m4_coherent_a_tau"], neg]
    e_cols = ["#FF5C8A", "#00E5FF", "#63F5B5"]
    bars_e = ax_e.bar(e_lbls, e_vals, color=e_cols, width=0.52)
    for b, v in zip(bars_e, e_vals):
        ax_e.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v*100:.1f}%", ha="center", fontsize=9.2, fontweight="bold")
    ax_e.set_ylim(0, 1.18)
    ax_e.set_ylabel("False Trigger Rate (Lower is Better)", fontsize=9)
    ax_e.set_title("E. Hot-Spike Rejection & Thermal Negative Control", fontsize=10.8, fontweight="bold", color="#FF5C8A", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.6)

    # Panel F: Trigger Score Distributions (Signal vs Background)
    ax_f = fig.add_subplot(gs[1, 2])
    sk = np.asarray(sc["score_kloster"])
    lbls = np.asarray(sc["labels"])
    ax_f.hist(sk[lbls == 0], bins=24, alpha=0.72, color="#FF5C8A", label="Background (Pileup + Hot-Spikes)")
    ax_f.hist(sk[lbls == 1], bins=24, alpha=0.78, color="#00E5FF", label="True Jet Showers")
    ax_f.set_xlabel("Kloster Coherent Trigger Score M_4^(1/4) · Gate(A_0.055)", fontsize=9)
    ax_f.set_ylabel("Event Count", fontsize=9)
    ax_f.set_title("F. Clean Signal-to-Background Score Separation", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_f.legend(loc="upper right", fontsize=7.8, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    report = run_cern_kloster_trigger_suite()
    ev_path = ROOT / "evidence/cern-trigger/cern-kloster-trigger-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-cern-kloster-trigger.png"
    render_cern_plate(report, fig_path)

    checks = list(report["checks"].items()) + [("cern_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000)]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

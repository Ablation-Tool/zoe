#!/usr/bin/env python3
"""Independent Fresh-Process Verifier & Living Constellation Renderer for Zoe OS (#4)."""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))
sys.path.insert(0, str(ROOT / "components/Zoe-Autonomy/src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi
from guiai.gem.zoe_os import zoe_os_scene
from zoe_autonomy.zoe_os_mind import run_zoe_os_verification_suite


def render_zoe_os_constellation_figure(report: dict, out_path: Path) -> None:
    """Render a 2-panel dark-observatory Living Constellation & Kloster Routing Telemetry Plate."""
    plt.rcParams.update({
        "figure.facecolor": "#070B14",
        "axes.facecolor": "#0D1526",
        "axes.edgecolor": "#263754",
        "axes.labelcolor": "#DCE7F7",
        "xtick.color": "#9DB2D1",
        "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF",
        "font.family": "DejaVu Sans",
    })

    snap = report["snapshot"]
    engines = snap["engines_audit"]["engines"]
    turns = report["sample_turns"]

    fig = plt.figure(figsize=(17.5, 8.8), dpi=220)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0], wspace=0.22, left=0.04, right=0.97, top=0.86, bottom=0.14)

    fig.suptitle(
        "Zoe OS :: Unified Persistent Living Workstation Mind (All 17 GEM Engines)",
        fontsize=16.5, fontweight="bold", color="#F4F8FF", y=0.955,
    )
    fig.text(
        0.5, 0.912,
        f"Computed Telemetry Plate  |  {snap['engines_audit']['available_engines']}/17 Engines Live  |  Cross-Session SHA-256 Ledger: {snap['ledger_integrity']['entries']} Entries (Intact={snap['ledger_integrity']['intact']})  |  0 Cloud Tokens",
        ha="center", fontsize=10.0, color="#7CE8FF",
    )

    # Panel A: 17-Engine Neural-Constellation Orbit Graph
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.set_facecolor("#09101E")
    ax_a.set_xlim(-1.45, 1.45)
    ax_a.set_ylim(-1.38, 1.38)
    ax_a.set_aspect("equal")
    ax_a.axis("off")
    ax_a.set_title("A. 17-Engine Living Constellation & Provenance Ring", fontsize=11.5, fontweight="bold", color="#7CE8FF", pad=6)

    theta_ring = np.linspace(0, 2 * np.pi, 300)
    ax_a.plot(np.cos(theta_ring), np.sin(theta_ring), color="#1F3557", linewidth=1.2, linestyle="--")
    ax_a.plot(0.46 * np.cos(theta_ring), 0.46 * np.sin(theta_ring), color="#1A2C48", linewidth=1.0, linestyle=":")

    # Central Zoe OS Hub
    hub = plt.Circle((0, 0), 0.27, facecolor="#10213A", edgecolor="#00E5FF", linewidth=2.6, zorder=5)
    ax_a.add_patch(hub)
    ax_a.text(0, 0.05, "ZOE OS", ha="center", va="center", fontsize=13, fontweight="bold", color="#00E5FF", zorder=6)
    ax_a.text(0, -0.07, "Eliza + Memory\nKloster A_τ + Stem", ha="center", va="center", fontsize=7.6, color="#FFB84D", zorder=6)

    # Category coloring
    cat_colors = {
        "research": "#00E5FF", "autonomy": "#00E5FF", "zoe": "#00E5FF",
        "kevlar": "#FF5C8A", "cerotto": "#FF5C8A", "pala": "#FF5C8A", "ablation": "#FF5C8A",
        "brain": "#63F5B5", "neurogarden": "#63F5B5", "life": "#63F5B5",
        "helen": "#FFB84D", "cern-console": "#FFB84D",
    }

    n_eng = len(engines)
    for idx, eng in enumerate(engines):
        ang = (2.0 * math.pi * idx / n_eng) - math.pi / 2.0
        x, y = math.cos(ang), math.sin(ang)
        col = cat_colors.get(eng["id"], "#A78BFA")
        ax_a.plot([0, x], [0, y], color=col, alpha=0.28, linewidth=1.3, zorder=1)
        ax_a.scatter([x], [y], s=260, facecolor="#0D1628", edgecolor=col, linewidth=2.2, zorder=4)
        ax_a.scatter([x], [y], s=42, color="#63F5B5" if eng["available"] else "#FF5C8A", zorder=5)
        lx, ly = 1.24 * x, 1.21 * y
        ha = "left" if x > 0.25 else ("right" if x < -0.25 else "center")
        ax_a.text(lx, ly, eng["id"], ha=ha, va="center", fontsize=8.4, fontweight="bold", color="#EEF5FF")

    # Legend dots at bottom-left
    leg_items = [
        ("#00E5FF", "Core / Math / Autonomy"),
        ("#FF5C8A", "Security / Forensics"),
        ("#63F5B5", "Neuro / ALife"),
        ("#FFB84D", "Physics / Groove"),
        ("#A78BFA", "GEM / Tooling"),
    ]
    for li, (col, lbl) in enumerate(leg_items):
        ax_a.scatter([-1.36], [-1.05 - li * 0.08], s=40, color=col)
        ax_a.text(-1.28, -1.05 - li * 0.08, lbl, va="center", fontsize=7.5, color="#B8CBE6")

    # Panel B: Live Kloster A_tau(p) & Renyi Routing Telemetry Across Sample Workstation Turns
    ax_b = fig.add_subplot(gs[0, 1])
    turn_labels = [
        "Thm / Paper\n(research)",
        "ELF / Opcode\n(ablation)",
        "CERN + Brain\n(multi-eng)",
        "Open Prompt\n(clarify)",
        "Vault Cloud\n(BLOCKED)",
    ]
    top_probs = [0.0 if t["blocked"] else t["top_probability"] for t in turns]
    renyi2 = [0.0 if t["blocked"] else t["kloster_geometry"]["h_renyi_2"] for t in turns]
    a_taus = [0 if t["blocked"] else t["kloster_geometry"]["a_tau"] for t in turns]

    x_idx = np.arange(len(turns))
    w_bar = 0.34
    bars1 = ax_b.bar(x_idx - w_bar / 2, top_probs, width=w_bar, color="#00E5FF", alpha=0.9, label="Top-Engine Prob max(p)")
    ax_b2 = ax_b.twinx()
    bars2 = ax_b2.bar(x_idx + w_bar / 2, renyi2, width=w_bar, color="#FFB84D", alpha=0.88, label="Kloster Renyi H_2 (nats)")

    short_gate = {
        "DISPATCH_SINGLE_ENGINE": "SINGLE",
        "COORDINATE_MULTI_ENGINE": "MULTI-ENG",
        "CLARIFY_WITH_ELIZA": "CLARIFY",
    }
    for i, t in enumerate(turns):
        if t["blocked"]:
            ax_b.text(i, 0.50, "PRIVACY\nFIREWALL\nBLOCK", ha="center", va="center", fontsize=8.3, fontweight="bold", color="#FF5C8A",
                      bbox=dict(boxstyle="round,pad=0.35", facecolor="#2A0D1C", edgecolor="#FF5C8A", linewidth=1.4))
        else:
            ax_b.text(i - w_bar / 2, top_probs[i] + 0.03, f"A={a_taus[i]}", ha="center", fontsize=8.0, color="#7CE8FF", fontweight="bold")
            ax_b.text(i, 1.11, short_gate.get(t["decision"], t["decision"]), ha="center", va="center", fontsize=7.6, fontweight="bold", color="#63F5B5",
                      bbox=dict(boxstyle="round,pad=0.22", facecolor="#0B1E26", edgecolor="#2E6B5A", linewidth=0.9))

    ax_b.set_ylim(0.0, 1.24)
    ax_b2.set_ylim(0.0, max(3.6, max(renyi2) * 1.38))
    ax_b.set_xticks(x_idx)
    ax_b.set_xticklabels(turn_labels, fontsize=8.5)
    ax_b.set_ylabel("Top-Engine Routing Confidence max(p)", fontsize=9, color="#00E5FF")
    ax_b2.set_ylabel("Kloster Renyi Entropy H_2 (nats)", fontsize=9, color="#FFB84D")
    ax_b.set_title("B. Kloster Information-Geometry Routing & Privacy Firewall", fontsize=11.5, fontweight="bold", color="#FFB84D", pad=8)
    ax_b.grid(axis="y", color="#1C2A42", linestyle="--", linewidth=0.6)

    lines = [bars1, bars2]
    ax_b.legend(lines, ["Top-Engine Prob max(p)", "Kloster Renyi H_2 (nats)"], loc="upper right", fontsize=8.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zoe_os_verify_") as tmp:
        report = run_zoe_os_verification_suite(ROOT, Path(tmp) / "state")

    scene = zoe_os_scene(report)
    v_scene = verify(scene)
    v_vdi = verify_vdi(scene)

    ev_path = ROOT / "evidence/zoe-os/zoe-os-mind-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-os-living-constellation.png"
    render_zoe_os_constellation_figure(report, fig_path)

    checks = list(report["checks"].items()) + [
        ("gem_scene_and_vdi_verified", bool(v_scene.passed and v_vdi.passed)),
        ("constellation_figure_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

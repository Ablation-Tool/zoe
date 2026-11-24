#!/usr/bin/env python3
"""Verify Zoe x Dorothy Coupled Brain Biomechanics & Continuum Research Workbench,
export offline WebGL2 benchmark/sweep payload (`dorothy-brain-observatory/data/biomechanics_benchmarks.js`),
and render the 6-panel dark-observatory verification plate (`zoe-dorothy-biomechanics-workbench.png`).
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

from guiai.gem.dorothy_biomechanics_workbench import (
    run_dorothy_biomechanics_workbench_suite,
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


def render_workbench_plate(rep: Dict[str, Any], out_path: Path) -> None:
    """Render 6-panel dark-observatory scientific plate for the Zoe x Dorothy Biomechanics Workbench."""
    _dark_theme()
    fig = plt.figure(figsize=(19.2, 11.6), dpi=210)
    gs = fig.add_gridspec(2, 3, hspace=0.40, wspace=0.29, left=0.06, right=0.97, top=0.885, bottom=0.075)

    seal = rep["cnsa2_provenance_seal"]
    verts = rep["geometry_summary"]["total_vertices"]
    n_runs = rep["parameter_sweep_summary"]["n_runs"]
    fig.suptitle(
        "Zoe × Dorothy Coupled Brain Biomechanics & Continuum Research Workbench (MNI152 · SymPy · Thm 13/15 · CERN · CNSA 2.0)",
        fontsize=12.6, fontweight="bold", color="#F4F8FF", y=0.962,
    )
    fig.text(
        0.5, 0.924,
        f"Real ICBM152+AAL+CIT168 ({verts:,} verts) | {n_runs}-Run 3-Solver Sweep | 0 Cloud Tokens | Research Only (cure_claim=False) | CNSA 2.0 SHA-384: {seal['sha384'][:18]}",
        ha="center", fontsize=8.9, color="#7CE8FF",
    )

    ab = rep["analytical_benchmarks"]
    zener = ab["zener_viscoelastic"]
    marm = ab["marmarou_monro_kellie"]
    nc = rep["negative_controls"]
    recs = rep["sweep_records"]

    # Panel A: Benchmark 1 — Zener Prony Viscoelastic Stress Relaxation (Budday et al. 2020)
    ax_a = fig.add_subplot(gs[0, 0])
    t_ms = np.asarray(zener["t_ms_sample"], dtype=np.float64)
    sig = np.asarray(zener["sigma_kpa_sample"], dtype=np.float64)
    ax_a.plot(t_ms, sig, color="#00E5FF", linewidth=2.3, label="2-Term Prony Integrator")
    ax_a.axhline(zener["params_kpa_s"]["G_inf"] * 0.10, color="#63F5B5", linestyle="--", linewidth=1.3, label=f"Equilibrium G_∞·ε₀ ({zener['params_kpa_s']['G_inf']*0.1:.3f} kPa)")
    ax_a.fill_between(t_ms, zener["params_kpa_s"]["G_inf"] * 0.10, sig, color="#00E5FF", alpha=0.14)
    ax_a.set_xlabel("Time t (ms)", fontsize=8.4)
    ax_a.set_ylabel("Cauchy Shear Stress σ(t) (kPa)", fontsize=8.4)
    ax_a.set_title(f"A. Zener Viscoelastic Relaxation (err={zener['relaxation_max_rel_error']:.1e})", fontsize=9.6, fontweight="bold", color="#00E5FF", pad=8)
    ax_a.grid(True, linestyle="--", linewidth=0.5)
    ax_a.legend(loc="upper right", fontsize=7.4, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: Benchmark 3 — Monro-Kellie / Marmarou (1975) Nonlinear ICP & CPP Curve
    ax_b = fig.add_subplot(gs[0, 1])
    dv = np.asarray(marm["pv_dv_ml"], dtype=np.float64)
    icp = np.asarray(marm["pv_icp_mmhg"], dtype=np.float64)
    cpp = np.asarray(marm["pv_cpp_mmhg"], dtype=np.float64)
    ax_b.plot(dv, icp, color="#FF5C8A", linewidth=2.3, label="ICP (Marmarou PVI=26 mL)")
    ax_b.plot(dv, cpp, color="#63F5B5", linewidth=2.1, linestyle="-.", label="CPP = MAP(85) − ICP")
    ax_b.axhline(20.0, color="#FFB84D", linestyle="--", linewidth=1.2, label="ICP 20 mmHg Reference")
    ax_b.set_xlabel("Intracranial Added Volume ΔV (mL)", fontsize=8.4)
    ax_b.set_ylabel("Pressure (mmHg)", fontsize=8.4)
    ax_b.set_ylim(-20, 120)
    ax_b.set_title(f"B. Monro-Kellie Compliance Curve (ODE err={marm['ode_vs_exact_max_rel_error']:.1e})", fontsize=9.6, fontweight="bold", color="#FF5C8A", pad=8)
    ax_b.grid(True, linestyle="--", linewidth=0.5)
    ax_b.legend(loc="upper left", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: 512-Run Parameter Sweep Phase Space (Peak Strain vs Theorem 15 Coherence C_K)
    ax_c = fig.add_subplot(gs[0, 2])
    mps = np.array([r["outputs"]["peak_mps"] for r in recs], dtype=np.float64)
    ck = np.array([r["zoe_metacognition"]["theorem15_coherence_c_k"] for r in recs], dtype=np.float64)
    verd = np.array([r["zoe_metacognition"]["verdict"] for r in recs])
    for vkey, col, lbl, mk in (
        ("DECIDE_LOCALIZED", "#63F5B5", "Confident Localized", "o"),
        ("GATHER_MORE", "#FFB84D", "Gather More", "^"),
        ("ABSTAIN_MODEL_UNCERTAINTY", "#FF5C8A", "Abstain (Model Unc.)", "X"),
    ):
        m = verd == vkey
        if np.any(m):
            ax_c.scatter(mps[m], ck[m], s=20, alpha=0.8, color=col, marker=mk, label=f"{lbl} ({int(m.sum())})")
    ax_c.axhline(0.58, color="#FF5C8A", linestyle="--", linewidth=1.2, alpha=0.85)
    ax_c.axvline(0.15, color="#00E5FF", linestyle=":", linewidth=1.3, alpha=0.85)
    ax_c.set_xlabel("Peak Principal Strain MPS (Bain & Meaney 0.15 ref)", fontsize=8.2)
    ax_c.set_ylabel("Theorem 15 3-Solver Coherence C_K", fontsize=8.2)
    ax_c.set_title("C. 512-Run Coupled Sweep & Uncertainty Gating", fontsize=9.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_c.grid(True, linestyle="--", linewidth=0.5)
    ax_c.legend(loc="lower right", fontsize=7.0, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel D: Negative Control #2 — CERN Coherent Trigger vs Classical Peak Strain (Glitch Rejection)
    ax_d = fig.add_subplot(gs[1, 0])
    c2 = nc["control2_cern_single_vertex_spike_rejection"]
    lbl_d = ["Classical Peak\n(True Cascade TPR)", "CERN-Kloster\n(True Cascade TPR)", "Classical Peak\n(1-Vert Glitch FPR)", "CERN-Kloster\n(1-Vert Glitch FPR)"]
    val_d = [c2["classical_peak_tpr"] * 100, c2["cern_kloster_tpr"] * 100, c2["classical_peak_glitch_fpr"] * 100, c2["cern_kloster_glitch_fpr"] * 100]
    col_d = ["#A78BFA", "#63F5B5", "#FF5C8A", "#00E5FF"]
    bars_d = ax_d.bar(np.arange(4), val_d, color=col_d, width=0.54)
    for b, v in zip(bars_d, val_d):
        ax_d.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v:.1f}%", ha="center", fontsize=8.3, fontweight="bold")
    ax_d.set_ylim(0, 118)
    ax_d.set_xticks(np.arange(4))
    ax_d.set_xticklabels(lbl_d, fontsize=7.1)
    ax_d.set_ylabel("Rate (%)", fontsize=8.4)
    ax_d.set_title("D. CERN Coherent Gate Rejects 1-Vertex FEM Glitches", fontsize=9.6, fontweight="bold", color="#FFB84D", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel E: Negative Controls #1, #3, #4 — Theorem 13 Stopping & Theorem 15 Consensus/Echo/Rogue
    ax_e = fig.add_subplot(gs[1, 1])
    c1 = nc["control1_theorem13_null_stopping"]
    c3 = nc["control3_theorem15_echo_chamber"]
    c4 = nc["control4_theorem15_rogue_solver"]
    lbl_e = [
        f"Thm 13 Signal\n(STOP @ S={c1['localized_signal_samples']})",
        f"Thm 13 Null\n(FAR={c1['null_false_alarm_rate']*100:.1f}%)",
        f"Thm 15 Echo\n(D_K={c3['d_k_disagreement']:.3f})",
        f"Thm 15 Rogue\n(C_K={c4['coherence_c_k']:.2f})",
    ]
    val_e = [
        min(12.0, abs(float(c1["localized_signal_z"]))),
        max(0.2, abs(float(c1["null_mean_z"]))),
        1.0 if c3["echo_chamber_detected"] else 0.0,
        float(c4["d_k_disagreement"]) * 25.0,
    ]
    tags_e = [f"Z={c1['localized_signal_z']:.1f}σ", f"Z={c1['null_mean_z']:.2f}σ", "ECHO CAUGHT", f"D_K={c4['d_k_disagreement']:.3f}"]
    bars_e = ax_e.bar(np.arange(4), val_e, color=["#63F5B5", "#00E5FF", "#FFB84D", "#FF5C8A"], width=0.52)
    for b, v, tg in zip(bars_e, val_e, tags_e):
        ax_e.text(b.get_x() + b.get_width() / 2, v + 0.35, tg, ha="center", fontsize=7.8, fontweight="bold")
    ax_e.set_ylim(0, max(val_e) * 1.28)
    ax_e.set_xticks(np.arange(4))
    ax_e.set_xticklabels(lbl_e, fontsize=7.4)
    ax_e.set_ylabel("Diagnostic Separation Scale", fontsize=8.4)
    ax_e.set_title("E. Theorem 13 Null & Theorem 15 Echo/Rogue Guards", fontsize=9.6, fontweight="bold", color="#A78BFA", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel F: Master Verification Scorecard (11/11 Checks)
    ax_f = fig.add_subplot(gs[1, 2])
    chk_items = [
        ("SymPy 4/4", rep["checks"]["sympy_4_continuum_identities_exact"]),
        ("MNI152 112k", rep["checks"]["real_mni152_geometry_loaded_gt_100k_verts"]),
        ("Zener SLS", rep["checks"]["benchmark1_zener_viscoelastic_exact"]),
        ("Nahum Coup", rep["checks"]["benchmark2_coup_contrecoup_nahum1977"]),
        ("Marmarou", rep["checks"]["benchmark3_marmarou1975_icp_ode"]),
        ("Lame + F-K", rep["checks"]["benchmark4_lame_and_fisher_kolmogorov"]),
        ("512 Sweep", rep["checks"]["sweep_512_runs_flags_uncertainty_abstain"]),
        ("Neg Ctrls 4/4", all([
            rep["checks"]["neg_ctrl1_theorem13_null_abstain"],
            rep["checks"]["neg_ctrl2_cern_single_vertex_spike_rejected"],
            rep["checks"]["neg_ctrl3_theorem15_echo_chamber_caught"],
            rep["checks"]["neg_ctrl4_theorem15_rogue_solver_caught"],
        ])),
    ]
    yf = np.arange(len(chk_items))
    vals_f = [100.0 if ok else 0.0 for _, ok in chk_items]
    cols_f = ["#63F5B5" if ok else "#FF5C8A" for _, ok in chk_items]
    ax_f.barh(yf, vals_f, color=cols_f, height=0.62)
    ax_f.set_yticks(yf)
    ax_f.set_yticklabels([k for k, _ in chk_items], fontsize=7.8)
    ax_f.invert_yaxis()
    ax_f.set_xlim(0, 122)
    for i, (_, ok) in enumerate(chk_items):
        ax_f.text(103, i, "PASS" if ok else "FAIL", va="center", fontsize=7.8, fontweight="bold", color="#63F5B5" if ok else "#FF5C8A")
    ax_f.set_xlabel("Verification (%)", fontsize=8.4)
    ax_f.set_title("F. End-to-End Verification & CNSA 2.0 Seal", fontsize=9.6, fontweight="bold", color="#00E5FF", pad=8)
    ax_f.grid(axis="x", linestyle="--", linewidth=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=210)
    plt.close(fig)


def export_web_payload(rep: Dict[str, Any], out_js: Path) -> None:
    """Write offline JS payload (`window.DOROTHY_BIOMECHANICS`) directly into dorothy-brain-observatory/data/."""
    # Compact sweep points (all 512 runs) for instant interactive plotting & 1-click 3D loading
    compact_sweep = [
        {
            "id": r["id"],
            "sc": r["scenario"],
            "g0": r["params"]["G0_kPa"],
            "gr": r["params"]["G_ratio"],
            "ag": r["params"]["accel_g"],
            "rot": r["params"]["rot_rad_s2"],
            "pvi": r["params"]["PVI_mL"],
            "rout": r["params"]["R_out"],
            "mr": r["params"]["mass_radius_mm"],
            "fk": r["params"]["fk_D_over_rho"],
            "mps": r["outputs"]["peak_mps"],
            "csdm": r["outputs"]["csdm_15_pct"],
            "vm": r["outputs"]["peak_von_mises_kpa"],
            "icp": r["outputs"]["icp_mmhg"],
            "cpp": r["outputs"]["cpp_mmhg"],
            "mls": r["outputs"]["midline_shift_mm"],
            "reg": r["outputs"]["peak_compartment"],
            "at": r["zoe_metacognition"]["a_tau"],
            "m4": r["zoe_metacognition"]["m4_root"],
            "dk": r["zoe_metacognition"]["theorem15_d_k"],
            "ck": r["zoe_metacognition"]["theorem15_coherence_c_k"],
            "v": r["zoe_metacognition"]["verdict"],
        }
        for r in rep["sweep_records"]
    ]
    web_obj = {
        "contract": rep["contract"],
        "epistemic_scope": rep["epistemic_scope"],
        "geometry_summary": rep["geometry_summary"],
        "sympy_proofs": rep["sympy_proofs"],
        "analytical_benchmarks": rep["analytical_benchmarks"],
        "parameter_sweep_summary": rep["parameter_sweep_summary"],
        "negative_controls": rep["negative_controls"],
        "open_literature_references": rep["open_literature_references"],
        "dorothy_135_bibliography_anchors": rep["dorothy_135_bibliography_anchors"],
        "checks": rep["checks"],
        "cnsa2_provenance_seal": rep["cnsa2_provenance_seal"],
        "sweep_points": compact_sweep,
    }
    out_js.parent.mkdir(parents=True, exist_ok=True)
    out_js.write_text(
        "/* Auto-generated by scripts/verify_dorothy_biomechanics_workbench.py — zero copyrighted text */\n"
        "window.DOROTHY_BIOMECHANICS = " + json.dumps(web_obj, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def main() -> int:
    report = run_dorothy_biomechanics_workbench_suite(ROOT, n_sweep=512)

    ev_path = ROOT / "evidence/dorothy-biomechanics/dorothy-biomechanics-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    # Persist full verifiable JSON (excluding redundant raw list duplication if needed, keeping full summary + top/all records)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    web_js = ROOT / "dorothy-brain-observatory/data/biomechanics_benchmarks.js"
    export_web_payload(report, web_js)

    plate_path = ROOT / "components/agent-logging-system/docs/images/zoe-dorothy-biomechanics-workbench.png"
    render_workbench_plate(report, plate_path)
    preview_plate = ROOT / "dorothy-brain-observatory/previews/zoe_biomechanics_workbench_plate.png"
    preview_plate.parent.mkdir(parents=True, exist_ok=True)
    preview_plate.write_bytes(plate_path.read_bytes())

    checks = list(report["checks"].items()) + [
        ("workbench_plate_generated", plate_path.is_file() and plate_path.stat().st_size > 50_000),
        ("workbench_web_payload_generated", web_js.is_file() and web_js.stat().st_size > 20_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")

    ab = report["analytical_benchmarks"]
    sw = report["parameter_sweep_summary"]
    nc = report["negative_controls"]
    seal = report["cnsa2_provenance_seal"]
    print(f"\nMNI152 GEOMETRY: {report['geometry_summary']['total_vertices']:,} real vertices loaded")
    print(
        f"BENCHMARKS: Zener err={ab['zener_viscoelastic']['relaxation_max_rel_error']:.2e} | "
        f"Nahum Coup/Contrecoup={ab['coup_contrecoup_nahum1977']['vented_coup_kpa']}/{ab['coup_contrecoup_nahum1977']['vented_contrecoup_kpa']} kPa | "
        f"Marmarou ODE err={ab['marmarou_monro_kellie']['ode_vs_exact_max_rel_error']:.2e} | "
        f"F-K wave err={ab['lame_and_fisher_kolmogorov']['fk_wave_speed_rel_error']*100:.2f}%"
    )
    print(f"512-RUN SWEEP VERDICTS: {sw['verdict_counts']}")
    print(
        f"NEGATIVE CONTROLS: Thm13 Null FAR={nc['control1_theorem13_null_stopping']['null_false_alarm_rate']*100:.1f}% | "
        f"CERN Glitch FPR={nc['control2_cern_single_vertex_spike_rejection']['cern_kloster_glitch_fpr']*100:.1f}% "
        f"(vs Classical {nc['control2_cern_single_vertex_spike_rejection']['classical_peak_glitch_fpr']*100:.1f}%) | "
        f"Echo={nc['control3_theorem15_echo_chamber']['echo_chamber_detected']} | "
        f"Rogue={nc['control4_theorem15_rogue_solver']['rogue_node_detected']}"
    )
    print(f"CNSA 2.0 SEAL: SHA-256={seal['sha256'][:16]} | SHA-384={seal['sha384'][:16]} | SHA3-384={seal['sha3_384'][:16]}")
    print(f"DOROTHY BIOMECHANICS WORKBENCH: {passed}/{len(checks)} PASS")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

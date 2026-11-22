#!/usr/bin/env python3
"""Orbit Pass 2 Verifier: Renders Qwen Temperature Phase-Sweep & Defensive Fault-Hardening Plate
AND verifies live loopback HTTP APIs (/api/os/mind, /api/os/mind/gem.svg, /api/kloster/elegance, /api/orbit/master).
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))
sys.path.insert(0, str(ROOT / "components/Zoe-Autonomy/src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guiai.gem.eliza_view import create_server
from zoe_autonomy.live_qwen_metacog_steerer import run_qwen_steerer_suite
from zoe_autonomy.open_ended_program_evolution import run_open_ended_evolution_suite
from zoe_autonomy.security_redteam_audit import run_security_redteam_suite


def render_pass2_plate(qwen_rep: dict, sec_rep: dict, evo_rep: dict, out_path: Path) -> None:
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
    gs = fig.add_gridspec(2, 3, hspace=0.36, wspace=0.28, left=0.055, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "Zoe Orbit Pass 2 :: Qwen 151,936-Vocab Steering, Defensive Fault-Injection Hardening & Elegant AST Evolution",
        fontsize=15.2, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Computed Verification Plate  |  GGUF v3 ({qwen_rep['gguf_provenance']['tensor_count']} tensors)  |  2,000-Trial Defensive Glitch Sim  |  Evolved AST MI={evo_rep['evolved_code_elegance']['maintainability_index_mi']}  |  0 Cloud Tokens",
        ha="center", fontsize=9.6, color="#7CE8FF",
    )

    # Panel A: Qwen2.5 151,936-Vocab Temperature vs Peak Probability & Renyi H_2
    ax_a = fig.add_subplot(gs[0, 0])
    sw = qwen_rep["temperature_phase_sweep_qwen"]
    temps = [r["temperature"] for r in sw]
    peaks = [r["peak_p"] for r in sw]
    h2s = [r["renyi_h2"] for r in sw]
    ax_a.plot(temps, peaks, color="#00E5FF", marker="o", linewidth=2.4, markersize=7, label="Top-1 Token Prob max(p)")
    ax_a2 = ax_a.twinx()
    ax_a2.plot(temps, h2s, color="#FFB84D", marker="s", linewidth=2.2, linestyle="--", markersize=6.5, label="Kloster Renyi H_2 (nats)")
    ax_a.set_xlabel("Decoding Temperature T", fontsize=9)
    ax_a.set_ylabel("Peak Probability max(p)", fontsize=9, color="#00E5FF")
    ax_a2.set_ylabel("Kloster Renyi H_2 (nats)", fontsize=9, color="#FFB84D")
    ax_a.set_title("A. #1 Qwen 151,936-Vocab Temperature Phase Sweep", fontsize=10.6, fontweight="bold", color="#7CE8FF", pad=8)
    ax_a.grid(True, linestyle="--", linewidth=0.6)
    ax_a.legend(loc="lower left", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax_a2.legend(loc="upper left", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: Qwen Exact Prefix-Pruning Calls vs Theoretical Bound Across 4 Steering Regimes
    ax_b = fig.add_subplot(gs[0, 1])
    scens = qwen_rep["scenarios"]
    s_lbls = [s["steered_action"] for s in scens]
    calls = [s["forward_calls"] for s in scens]
    max_c = [s["theoretical_max_calls"] for s in scens]
    x = np.arange(len(scens))
    ax_b.bar(x - 0.18, calls, width=0.34, color="#63F5B5", label="Exact Pruned Forward Calls")
    ax_b.bar(x + 0.18, max_c, width=0.34, color="#38BDF8", alpha=0.55, label="Theorem Max Bound 1+(h-1)(⌈1/τ⌉-1)")
    for i, (cv, mv) in enumerate(zip(calls, max_c)):
        ax_b.text(i - 0.18, cv + 3, str(cv), ha="center", fontsize=8.5, fontweight="bold", color="#63F5B5")
        ax_b.text(i + 0.18, mv + 3, str(mv), ha="center", fontsize=8.0, color="#7CE8FF")
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(s_lbls, fontsize=8.6)
    ax_b.set_ylim(0, max(max_c) * 1.24)
    ax_b.set_ylabel("Forward Evaluations (vs 151,936³)", fontsize=9)
    ax_b.set_title("B. #1 Multi-Horizon Steering Action Regimes (4/4)", fontsize=10.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_b.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_b.legend(loc="upper left", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: #10 Defensive Fault-Injection / Instruction-Skip Hardening (2,000-Trial Simulator)
    ax_c = fig.add_subplot(gs[0, 2])
    fh = sec_rep["defensive_fault_hardening"]
    archs = ["Naive\nSingle Check", "Standard\nDouble Check", "Kloster A_τ=1\nTri-Witness"]
    single_b = [
        fh["naive_single_check"]["single_glitch_bypass_rate"] * 100.0,
        fh["standard_double_check"]["single_glitch_bypass_rate"] * 100.0,
        fh["kloster_tri_witness_quorum"]["single_glitch_bypass_rate"] * 100.0,
    ]
    double_b = [
        fh["naive_single_check"]["double_glitch_bypass_rate"] * 100.0,
        fh["standard_double_check"]["double_glitch_bypass_rate"] * 100.0,
        fh["kloster_tri_witness_quorum"]["double_glitch_bypass_rate"] * 100.0,
    ]
    xc = np.arange(3)
    b1 = ax_c.bar(xc - 0.18, single_b, width=0.34, color="#FF5C8A", label="Single-Instruction Skip Bypass %")
    b2 = ax_c.bar(xc + 0.18, double_b, width=0.34, color="#FFB84D", label="Correlated Double-Glitch Bypass %")
    for bars_g in (b1, b2):
        for b in bars_g:
            v = b.get_height()
            ax_c.text(b.get_x() + b.get_width() / 2, v + 2.2, f"{v:.1f}%", ha="center", fontsize=8.0, fontweight="bold")
    ax_c.set_xticks(xc)
    ax_c.set_xticklabels(archs, fontsize=8.4)
    ax_c.set_ylim(0, 114)
    ax_c.set_ylabel("Simulated Fault Bypass Rate (Lower = Safer)", fontsize=9)
    ax_c.set_title("C. #10 Defensive Fault-Injection Hardening (2,000 Runs)", fontsize=10.6, fontweight="bold", color="#FF5C8A", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_c.legend(loc="upper right", fontsize=7.5, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel D: #10 Ablation Binary Entropy Forensics (Packed vs ELF vs ASCII vs Zero Slack)
    ax_d = fig.add_subplot(gs[1, 0])
    ab = sec_rep["ablation_entropy_forensics"]
    cls_lbls = ["Packed /\nEncrypted", "Structured\nELF Binary", "ASCII\nSource", "Zero Slack\n(Neg Ctrl)"]
    sh_bits = [ab["packed_encrypted"]["shannon_bits"], ab["structured_elf"]["shannon_bits"], ab["ascii_source"]["shannon_bits"], ab["zero_slack_neg_ctrl"]["shannon_bits"]]
    m4_b = [ab["packed_encrypted"]["kloster_m4_root"], ab["structured_elf"]["kloster_m4_root"], ab["ascii_source"]["kloster_m4_root"], ab["zero_slack_neg_ctrl"]["kloster_m4_root"]]
    xd = np.arange(4)
    ax_d.bar(xd - 0.18, sh_bits, width=0.34, color="#00E5FF", label="Shannon Bits/Byte (0..8)")
    ax_d2 = ax_d.twinx()
    ax_d2.bar(xd + 0.18, m4_b, width=0.34, color="#63F5B5", alpha=0.85, label="Kloster M_4^(1/4) Purity")
    ax_d.set_xticks(xd)
    ax_d.set_xticklabels(cls_lbls, fontsize=8.3)
    ax_d.set_ylim(0, 9.6)
    ax_d2.set_ylim(0, 1.25)
    ax_d.set_ylabel("Byte Entropy (bits/byte)", fontsize=9, color="#00E5FF")
    ax_d2.set_ylabel("Kloster M_4^(1/4)", fontsize=9, color="#63F5B5")
    ax_d.set_title("D. #10 Ablation Byte Entropy x Kloster Purity", fontsize=10.6, fontweight="bold", color="#7CE8FF", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.6)
    ax_d.legend(loc="upper left", fontsize=7.5, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax_d2.legend(loc="upper right", fontsize=7.5, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel E: #3 Open-Ended Multi-Statement AST Evolution Convergence Curve
    ax_e = fig.add_subplot(gs[1, 1])
    curve = evo_rep["fitness_curve_mse"]
    gens = np.arange(len(curve))
    ax_e.plot(gens, curve, color="#63F5B5", marker="o", markersize=4.5, linewidth=2.3, label=f"Evolved 2-Fn AST (MI={evo_rep['evolved_code_elegance']['maintainability_index_mi']:.1f})")
    ax_e.axhline(evo_rep["stateless_control_test_mse"], color="#FFB84D", linestyle="--", linewidth=1.8, label=f"Stateless Control MSE ({evo_rep['stateless_control_test_mse']:.4f})")
    ax_e.axhline(evo_rep["seed_test_mse"], color="#FF5C8A", linestyle=":", linewidth=1.6, label=f"Initial Seed MSE ({evo_rep['seed_test_mse']:.4f})")
    ax_e.set_xlabel("Evolution Generation (0 Pre-Written Solutions)", fontsize=9)
    ax_e.set_ylabel("Piecewise Hysteresis MSE (Lower = Better)", fontsize=9)
    ax_e.set_title("E. #3 Stateful Multi-Statement AST Evolution", fontsize=10.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_e.grid(True, linestyle="--", linewidth=0.6)
    ax_e.legend(loc="upper right", fontsize=7.5, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel F: #3 Blind Zero-Shot Groove vs Poisson Transfer Scores (Never Trained on Audio!)
    ax_f = fig.add_subplot(gs[1, 2])
    gs_map = evo_rep["blind_transfer_groove_scores"]
    g_names = ["Rigid\n120BPM", "Amiga\n.MOD", "J-Dilla\nSwing", "3:2\nClave", "Poisson\n(Neg Ctrl)"]
    g_keys = ["rigid_quantized_120bpm", "protracker_amiga_mod_mk", "human_dilla_pocket_swing", "polyrhythm_3_2_clave", "negative_control_poisson_noise"]
    g_vals = [gs_map.get(k, 0.0) for k in g_keys]
    g_cols = ["#00E5FF", "#38BDF8", "#63F5B5", "#FFB84D", "#FF5C8A"]
    bars_f = ax_f.bar(g_names, g_vals, color=g_cols, width=0.56)
    for b, v in zip(bars_f, g_vals):
        ax_f.text(b.get_x() + b.get_width() / 2, v + 0.025, f"{v:.3f}", ha="center", fontsize=8.4, fontweight="bold")
    ax_f.set_ylim(0, 1.08)
    ax_f.set_ylabel("Evolved Policy Score (Zero-Shot Blind)", fontsize=9)
    ax_f.set_title("F. #3 -> #11 Blind Zero-Shot Transfer (16-LLM AUROC 1.0)", fontsize=10.4, fontweight="bold", color="#FFB84D", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.6)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def verify_live_http_endpoints() -> Dict[str, bool]:
    """Spin up a temporary loopback Eliza-GEM server and hit all 4 new Orbit Pass 2 endpoints live."""
    results: Dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="zoe_http_pass2_") as tmp:
        srv, _eng, _lock = create_server(ROOT, state_dir=Path(tmp) / "eliza", host="127.0.0.1", port=0, default_gear="gear1")
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            for ep, mode in (
                ("/api/os/mind", "json"),
                ("/api/os/mind/gem.svg", "svg"),
                ("/api/kloster/elegance", "json"),
                ("/api/orbit/master", "json"),
                ("/orbit", "html"),
            ):
                with urlrequest.urlopen(f"http://127.0.0.1:{port}{ep}", timeout=5) as resp:
                    body = resp.read().decode("utf-8")
                    if mode == "svg":
                        results[ep] = resp.status == 200 and "<svg" in body
                    elif mode == "html":
                        results[ep] = resp.status == 200 and "11-World Renaissance Observatory" in body
                    else:
                        doc = json.loads(body)
                        results[ep] = resp.status == 200 and bool(doc.get("all_verified", False))
        finally:
            srv.shutdown()
            srv.server_close()
    return results


def main() -> int:
    qwen_rep = run_qwen_steerer_suite(ROOT)
    (ROOT / "evidence/qwen-steerer/qwen-steerer-report.json").write_text(json.dumps(qwen_rep, indent=2, sort_keys=True), encoding="utf-8")

    sec_rep = run_security_redteam_suite(ROOT)
    (ROOT / "evidence/security-redteam/security-redteam-report.json").write_text(json.dumps(sec_rep, indent=2, sort_keys=True), encoding="utf-8")

    evo_rep = run_open_ended_evolution_suite(ROOT)
    (ROOT / "evidence/open-ended-evolution/multistmt-evolution-report.json").write_text(json.dumps(evo_rep, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-pass2-fault-and-qwen-steering.png"
    render_pass2_plate(qwen_rep, sec_rep, evo_rep, fig_path)

    http_ok = verify_live_http_endpoints()

    checks = [
        ("qwen_steerer_pass2_temp_sweep_verified", qwen_rep["all_verified"]),
        ("security_pass2_defensive_fault_hardening_verified", sec_rep["all_verified"]),
        ("evolution_pass2_code_elegance_verified", evo_rep["all_verified"]),
        ("pass2_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000),
        ("live_http_api_os_mind", http_ok.get("/api/os/mind", False)),
        ("live_http_api_os_mind_svg", http_ok.get("/api/os/mind/gem.svg", False)),
        ("live_http_api_kloster_elegance", http_ok.get("/api/kloster/elegance", False)),
        ("live_http_api_orbit_master", http_ok.get("/api/orbit/master", False)),
        ("live_http_html_orbit_dashboard", http_ok.get("/orbit", False)),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nPASS 2 INTEGRATION: {passed}/{len(checks)} PASS")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

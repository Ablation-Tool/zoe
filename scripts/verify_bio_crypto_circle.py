#!/usr/bin/env python3
"""Verify Zoe Bio-Crypto Reciprocal Circle (C17-C19: Botanical Pharmacognosy & CNS BBB,
Full FIPS 203 n=256 NTT Homomorphic Multi-Hospital Cohort & Reciprocal Bio-Crypto Circle)
and render the 6-panel dark-observatory plate `zoe-bio-crypto-circle.png`.
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

from guiai.gem.kloster_bio_crypto_circle import run_bio_crypto_circle_suite


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


def render_bio_crypto_plate(rep: Dict[str, Any], out_path: Path) -> None:
    """Render 6-panel dark-observatory scientific plate for Challenges C17-C19."""
    _dark_theme()
    fig = plt.figure(figsize=(18.8, 11.4), dpi=210)
    gs = fig.add_gridspec(2, 3, hspace=0.40, wspace=0.30, left=0.075, right=0.965, top=0.885, bottom=0.075)

    fig.suptitle(
        "Zoe Bio-Crypto Reciprocal Circle (C17–C19) :: Botanical Neuro-Oncology BBB · FIPS 203 n=256 NTT Homomorphic Cohort · Closed-Loop Synergy",
        fontsize=12.6, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"NIH PubChem Descriptors + Synthetic Cohort (0 PHI)  |  cure_claim=False · clinical_action=False  |  0 Cloud Tokens  |  SHA-256: {rep['evidence_sha256'][:16]}",
        ha="center", fontsize=9.1, color="#7CE8FF",
    )

    ch = rep["challenges"]
    c17 = ch["c17_botanical_neuro_oncology"]
    c18 = ch["c18_fips203_homomorphic_cohort"]
    c19 = ch["c19_reciprocal_bio_crypto_circle"]

    # Panel A: C17 NIH PubChem CNS MPO-4 Scores Across Botanicals & Clinical Benchmarks
    ax_a = fig.add_subplot(gs[0, 0])
    mols = sorted(c17["molecule_scores"], key=lambda r: r["cns_mpo4_score"], reverse=True)
    y_a = np.arange(len(mols))
    v_a = [r["cns_mpo4_score"] for r in mols]
    cat_col = {
        "clinical_cns_benchmark": "#63F5B5",
        "preclinical_botanical": "#00E5FF",
        "prodrug_parent_toxin": "#FFB84D",
        "approved_plant_oncology": "#A78BFA",
        "bbb_negative_control": "#FF5C8A",
    }
    cols_a = [cat_col.get(r["category"], "#7CE8FF") for r in mols]
    ax_a.barh(y_a, v_a, color=cols_a, height=0.64)
    ax_a.set_yticks(y_a)
    ax_a.set_yticklabels([r["id"] for r in mols], fontsize=7.6)
    ax_a.invert_yaxis()
    ax_a.set_xlim(0, 4.45)
    for i, r in enumerate(mols):
        flag = " [!TOX]" if r["raw_systemic_toxicity_flag"] else ""
        ax_a.text(r["cns_mpo4_score"] + 0.06, i, f"{r['cns_mpo4_score']:.2f}{flag}", va="center", fontsize=6.9)
    ax_a.set_xlabel("PubChem 4-Term Wager CNS MPO (0–4)", fontsize=8.2)
    ax_a.set_title("A. C17: Botanical vs CNS Benchmark BBB Profile", fontsize=9.7, fontweight="bold", color="#63F5B5", pad=8)
    ax_a.grid(axis="x", linestyle="--", linewidth=0.5)

    # Panel B: C17 Biochemical Cipher — ICT2588 MMP-14 Prodrug vs Raw Colchicine
    ax_b = fig.add_subplot(gs[0, 1])
    pr = c17["ict2588_mmp14_prodrug_cipher"]
    x_b = np.arange(2)
    ratios = [pr["raw_colchicine_tumor_to_healthy_ratio"], pr["ict2588_prodrug_tumor_to_healthy_ratio"]]
    bars_b = ax_b.bar(x_b, ratios, color=["#FF5C8A", "#63F5B5"], width=0.46)
    for b, v in zip(bars_b, ratios):
        ax_b.text(b.get_x() + b.get_width() / 2, v + 0.35, f"{v:.1f}×", ha="center", fontsize=8.8, fontweight="bold")
    ax_b.axhline(10.0, color="#FFB84D", linestyle="--", linewidth=1.3, label="Bradford >=10× Tumor Target")
    ax_b.set_ylim(0, max(ratios) * 1.25)
    ax_b.set_xticks(x_b)
    ax_b.set_xticklabels(["Raw Colchicine\n(Unmasked Toxin)", "ICT2588 Prodrug\n(MMP-14 Decrypted)"], fontsize=8.0)
    ax_b.set_ylabel("Tumor / Healthy Exposure Ratio", fontsize=8.2)
    ax_b.set_title(f"B. C17: Biochemical Cipher (M₄ Gain {pr['spatial_selectivity_m4_gain']:.2f}×)", fontsize=9.7, fontweight="bold", color="#FFB84D", pad=8)
    ax_b.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_b.legend(loc="upper left", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel C: C18 FIPS 203 n=256 NTT Homomorphic 3-Hospital Cohort Exact Recovery
    ax_c = fig.add_subplot(gs[0, 2])
    xc = np.arange(len(c18["true_pooled_counts"]))
    ax_c.bar(xc - 0.18, c18["true_pooled_counts"], width=0.35, color="#00E5FF", label="Plaintext 3-Site Sum")
    ax_c.bar(xc + 0.18, c18["homomorphic_decrypted_counts"], width=0.35, color="#63F5B5", label="Encrypted RLWE Sum (3/3)")
    ax_c.set_ylim(0, max(c18["true_pooled_counts"]) * 1.32)
    ax_c.set_xticks(xc)
    ax_c.set_xticklabels([f"M{i+1}" for i in xc], fontsize=7.3)
    ax_c.set_ylabel("Pooled Assay Count (Synthetic)", fontsize=8.2)
    ax_c.set_title("C. C18: FIPS 203 n=256 Homomorphic Sum (0 Err)", fontsize=9.7, fontweight="bold", color="#00E5FF", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_c.legend(loc="upper right", fontsize=7.1, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel D: C18 Security Control — Ciphertext & 1-of-3 Compromised Share Uniformity
    ax_d = fig.add_subplot(gs[1, 0])
    vals_d = [
        c18["uniform_32bin_m4_root"],
        c18["ciphertext_kloster_m4_root"],
        c18["single_share_1of3_kloster_m4_root"],
    ]
    bars_d = ax_d.bar([0, 1, 2], vals_d, color=["#A78BFA", "#00E5FF", "#FFB84D"], width=0.48)
    for b, v in zip(bars_d, vals_d):
        ax_d.text(b.get_x() + b.get_width() / 2, v + 0.002, f"{v:.4f}", ha="center", fontsize=8.0, fontweight="bold")
    ax_d.set_ylim(0, max(vals_d) * 1.32)
    ax_d.set_xticks([0, 1, 2])
    ax_d.set_xticklabels(["Uniform\nBaseline", "Raw RLWE\nCiphertext", "1-of-3 Stolen\nShare Ctrl"], fontsize=7.8)
    ax_d.set_ylabel("Kloster M₄^(1/4) Spectral Peak", fontsize=8.2)
    ax_d.set_title("D. C18: Zero Leakage Under Eavesdrop / 1-of-3", fontsize=9.7, fontweight="bold", color="#A78BFA", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel E: C19 Crypto -> Biology Leg (Rare-Tumor Cohort Power via Encrypted Pooling)
    ax_e = fig.add_subplot(gs[1, 1])
    c2b = c19["crypto_to_biology_leg"]
    ve = [
        c2b["single_hospital_top1_accuracy"] * 100.0,
        c2b["homomorphic_pooled_3_top1_accuracy"] * 100.0,
        c2b["homomorphic_pooled_7_top1_accuracy"] * 100.0,
    ]
    bars_e = ax_e.bar([0, 1, 2], ve, color=["#FF5C8A", "#00E5FF", "#63F5B5"], width=0.48)
    for b, v in zip(bars_e, ve):
        ax_e.text(b.get_x() + b.get_width() / 2, v + 2.2, f"{v:.1f}%", ha="center", fontsize=8.4, fontweight="bold")
    ax_e.set_ylim(0, 112)
    ax_e.set_xticks([0, 1, 2])
    ax_e.set_xticklabels(["1 Hospital\n(Isolated n=5)", "3-Site RLWE\n(Encrypted N=15)", "7-Site RLWE\n(Unlocked N=35)"], fontsize=7.6)
    ax_e.set_ylabel("Unbiased Top-1 Recovery (%)", fontsize=8.2)
    ax_e.set_title(f"E. C19 Crypto→Bio (+{c2b['accuracy_gain_1_to_7_sites']*100:.1f}pp, 0 PHI)", fontsize=9.7, fontweight="bold", color="#63F5B5", pad=8)
    ax_e.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel F: C19 Biology -> Crypto Leg (Tighter Assay Calibration Expands RLWE Depth)
    ax_f = fig.add_subplot(gs[1, 2])
    rds = c19["biology_to_crypto_rounds"]
    xf = np.arange(len(rds))
    yf = [r["max_error_free_hospitals"] for r in rds]
    bars_f = ax_f.bar(xf, yf, color=["#FFB84D", "#00E5FF", "#63F5B5"], width=0.48)
    for b, v in zip(bars_f, yf):
        ax_f.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v} sites", ha="center", fontsize=8.5, fontweight="bold")
    ax_f.set_ylim(0, max(yf) * 1.28)
    ax_f.set_xticks(xf)
    ax_f.set_xticklabels([f"R1\nt=32 (Δ={rds[0]['delta']})", f"R2\nt=16 (Δ={rds[1]['delta']})", f"R3\nt=8 (Δ={rds[2]['delta']})"], fontsize=7.6)
    ax_f.set_ylabel("Max Error-Free Stacked Hospitals", fontsize=8.2)
    ax_f.set_title("F. C19 Bio→Crypto: Tighter Bins Expand RLWE Depth", fontsize=9.7, fontweight="bold", color="#00E5FF", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=210)
    plt.close(fig)


def main() -> int:
    report = run_bio_crypto_circle_suite()
    ev_path = ROOT / "evidence/kloster-cryptanalysis/bio-crypto-circle-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    plate_path = ROOT / "components/agent-logging-system/docs/images/zoe-bio-crypto-circle.png"
    render_bio_crypto_plate(report, plate_path)

    checks = list(report["checks"].items()) + [
        ("bio_crypto_plate_generated", plate_path.is_file() and plate_path.stat().st_size > 50_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    c17 = report["challenges"]["c17_botanical_neuro_oncology"]
    c18 = report["challenges"]["c18_fips203_homomorphic_cohort"]
    c19 = report["challenges"]["c19_reciprocal_bio_crypto_circle"]
    print(
        f"\nC17 ICT2588 PRODRUG RATIO: {c17['ict2588_mmp14_prodrug_cipher']['ict2588_prodrug_tumor_to_healthy_ratio']}x "
        f"vs RAW {c17['ict2588_mmp14_prodrug_cipher']['raw_colchicine_tumor_to_healthy_ratio']}x"
    )
    print(
        f"C18 FIPS 203 NTT (n=256, q=3329): exact={c18['fips203_ntt_bit_exact_vs_schoolbook']} | "
        f"3-site homomorphic sum exact={c18['homomorphic_sum_bit_exact']} | max_noise={c18['max_decryption_noise_abs']}/{c18['decryption_cliff_margin_half_delta']}"
    )
    c2b = c19["crypto_to_biology_leg"]
    caps = [r["max_error_free_hospitals"] for r in c19["biology_to_crypto_rounds"]]
    print(
        f"C19 CIRCLE: Crypto->Bio {c2b['single_hospital_top1_accuracy']*100:.1f}% -> "
        f"{c2b['homomorphic_pooled_3_top1_accuracy']*100:.1f}% -> {c2b['homomorphic_pooled_7_top1_accuracy']*100:.1f}% | "
        f"Bio->Crypto RLWE site capacity {caps}"
    )
    print(f"BIO-CRYPTO CIRCLE: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

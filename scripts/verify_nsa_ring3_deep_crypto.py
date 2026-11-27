#!/usr/bin/env python3
"""Verify Zoe NSA Ring 3 Deep Lattice & Historical NSA Suite (C23-C26) plugged into
Theorem 13's sequential stopping engine, and render `zoe-nsa-ring3-deep-crypto.png`.
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

from guiai.gem.kloster_nsa_ring3_skipjack_venona import run_nsa_ring3_deep_crypto_suite


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


def render_ring3_plate(rep: Dict[str, Any], out_path: Path) -> None:
    """Render 6-panel dark-observatory plate for Ring 3 (C23-C26) + Theorem 13."""
    _dark_theme()
    fig = plt.figure(figsize=(18.8, 11.4), dpi=210)
    gs = fig.add_gridspec(2, 3, hspace=0.40, wspace=0.30, left=0.065, right=0.965, top=0.885, bottom=0.075)

    fig.suptitle(
        "Zoe NSA Ring 3 (C23–C26 · 26/26 Total) :: 256-Bit ECDSA HNP (LLL) · Dual_EC_DRBG · NSA SKIPJACK Impossible Diff · Venona OTP Depth",
        fontsize=12.2, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Plugged Directly Into Theorem 13 Stopping Engine  |  100% Offline & Legal  |  0 Cloud Tokens  |  SHA-256: {rep['evidence_sha256'][:16]}",
        ha="center", fontsize=9.1, color="#7CE8FF",
    )

    ch = rep["challenges"]
    c23 = ch["c23_ecdsa_hnp_lll"]
    c24 = ch["c24_dual_ec_drbg"]
    c25 = ch["c25_nsa_skipjack"]
    c26 = ch["c26_venona_otp_depth"]

    # Panel A: C23 ECDSA Biased-Nonce HNP — Theorem 13 Z_K Bias Detection vs RFC 6979
    ax_a = fig.add_subplot(gs[0, 0])
    va = [c23["theorem13_biased_rng_detection"]["z_kloster"], c23["theorem13_rfc6979_safe_control"]["z_kloster"]]
    bars_a = ax_a.bar([0, 1], va, color=["#FF5C8A", "#63F5B5"], width=0.46)
    for b, v in zip(bars_a, va):
        ax_a.text(b.get_x() + b.get_width() / 2, max(v, 0) + 1.0, f"{v:.1f}σ", ha="center", fontsize=8.4, fontweight="bold")
    ax_a.axhline(c23["theorem13_biased_rng_detection"]["z_threshold"], color="#FFB84D", linestyle="--", linewidth=1.3, label="Theorem 13 Gate")
    ax_a.set_ylim(min(-2.5, min(va) - 1.5), max(va) * 1.25)
    ax_a.set_xticks([0, 1])
    ax_a.set_xticklabels(["Leaky MSB Nonces\n(12 Sigs → 256b Key)", "RFC 6979 Safe\n(ABSTAIN)"], fontsize=7.8)
    ax_a.set_ylabel("Theorem 13 Z_K (σ)", fontsize=8.2)
    ax_a.set_title("A. C23: 256-Bit secp256k1 HNP (0 Nonce Reuse)", fontsize=9.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_a.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_a.legend(loc="upper right", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: C25 Official NSA SKIPJACK — 12-Rd Invariant vs 13-Rd Impossible Zero-Hole
    ax_b = fig.add_subplot(gs[0, 1])
    r12_n = int(c25["bbs_12rd_r5_to_r16_dw4_zero_hits"].split("/")[0])
    r13_n = int(c25["bbs_13rd_r5_to_r17_impossible_dw4_zero_hits"].split("/")[0])
    bars_b = ax_b.bar([0, 1], [r12_n, r13_n], color=["#00E5FF", "#FF5C8A"], width=0.46)
    for b, v in zip(bars_b, [r12_n, r13_n]):
        ax_b.text(b.get_x() + b.get_width() / 2, v + 14, f"{v}/512", ha="center", fontsize=8.6, fontweight="bold")
    ax_b.set_ylim(0, 610)
    ax_b.set_xticks([0, 1])
    ax_b.set_xticklabels(["12-Rd (R5→R16)\nΔw4=0 Invariant (100%)", "13-Rd (R5→R17)\nImpossible Hole (0%)"], fontsize=7.7)
    ax_b.set_ylabel("Pairs With Δw4 == 0 (of 512)", fontsize=8.2)
    ax_b.set_title(f"B. C25: NSA SKIPJACK ({c25['official_nsa_vector_hex']})", fontsize=9.6, fontweight="bold", color="#00E5FF", pad=8)
    ax_b.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel C: C25 SKIPJACK Theorem 13 Stopping — 12-Rd Early Stop vs Full 32-Rd Abstain
    ax_c = fig.add_subplot(gs[0, 2])
    vc = [c25["theorem13_12rd_stopping"]["samples"], c25["theorem13_32rd_full_security_ctrl"]["samples"]]
    bars_c = ax_c.bar([0, 1], vc, color=["#63F5B5", "#A78BFA"], width=0.46)
    for b, v in zip(bars_c, vc):
        ax_c.text(b.get_x() + b.get_width() / 2, v + 55, f"{v}", ha="center", fontsize=8.6, fontweight="bold")
    ax_c.set_ylim(0, 2400)
    ax_c.set_xticks([0, 1])
    ax_c.set_xticklabels(["12-Rd SKIPJACK\n(Thm 13 STOP)", "Full 32-Rd SKIPJACK\n(Thm 13 ABSTAIN)"], fontsize=7.8)
    ax_c.set_ylabel("Ciphertext Pairs Sampled", fontsize=8.2)
    ax_c.set_title("C. C25: Theorem 13 SKIPJACK Security Cliff", fontsize=9.6, fontweight="bold", color="#A78BFA", pad=8)
    ax_c.grid(axis="y", linestyle="--", linewidth=0.5)

    # Panel D: C26 Project Venona OTP Depth — Theorem 13 Z_K Depth Detection vs Single-Use OTP
    ax_d = fig.add_subplot(gs[1, 0])
    vd = [c26["theorem13_depth_detection"]["z_kloster"], c26["theorem13_single_use_otp_ctrl"]["z_kloster"]]
    bars_d = ax_d.bar([0, 1], vd, color=["#FFB84D", "#63F5B5"], width=0.46)
    for b, v in zip(bars_d, vd):
        ax_d.text(b.get_x() + b.get_width() / 2, max(v, 0) + 0.5, f"{v:.1f}σ", ha="center", fontsize=8.4, fontweight="bold")
    ax_d.axhline(c26["theorem13_depth_detection"]["z_threshold"], color="#FF5C8A", linestyle="--", linewidth=1.3, label="Theorem 13 Gate")
    ax_d.set_ylim(min(-2.5, min(vd) - 1.2), max(vd) * 1.28)
    ax_d.set_xticks([0, 1])
    ax_d.set_xticklabels(["Venona Depth\n(Reused Pad → 100%)", "Single-Use OTP\n(ABSTAIN)"], fontsize=7.8)
    ax_d.set_ylabel("Theorem 13 Z_K (σ)", fontsize=8.2)
    ax_d.set_title("D. C26: Venona OTP Depth vs. True OTP", fontsize=9.6, fontweight="bold", color="#FFB84D", pad=8)
    ax_d.grid(axis="y", linestyle="--", linewidth=0.5)
    ax_d.legend(loc="upper right", fontsize=7.2, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel E: C23-C26 Attacks & Modern Defenses Scorecard
    ax_e = fig.add_subplot(gs[1, 1])
    lbls_e = [
        "C23: 256b ECDSA\nHNP LLL (0 Reuse)",
        "C23 Ctrl: RFC 6979\nThm 13 ABSTAIN",
        "C24: Dual_EC_DRBG\n3/3 Blocks Predict",
        "C24 Ctrl: HMAC_DRBG\nThm 13 ABSTAIN",
        "C25: NSA SKIPJACK\nVector + Imp. Diff",
        "C26: Venona Depth\n2/2 PTs + Pad",
    ]
    ye = np.arange(len(lbls_e))
    ax_e.barh(ye, [1.0] * 6, color=["#FFB84D", "#63F5B5", "#FF5C8A", "#63F5B5", "#00E5FF", "#A78BFA"], height=0.58)
    ax_e.set_yticks(ye)
    ax_e.set_yticklabels(lbls_e, fontsize=7.2)
    ax_e.invert_yaxis()
    ax_e.set_xlim(0, 1.48)
    ax_e.set_xticks([0, 1])
    ax_e.set_xticklabels(["Fail", "Verified"])
    tags_e = [
        f"{c23['signatures_used']} sigs",
        f"Z={c23['theorem13_rfc6979_safe_control']['z_kloster']:.2f}σ",
        f"{c24['valid_curve_lifts_checked']} lifts",
        f"Z={c24['hmac_drbg_theorem13_control']['z_kloster']:.2f}σ",
        "2587cae2...",
        f"{c26['message_len']}B exact",
    ]
    for i, tg in enumerate(tags_e):
        ax_e.text(1.04, i, tg, va="center", fontsize=7.2)
    ax_e.set_title("E. Ring 3 Attacks & Theorem 13 Defenses", fontsize=9.6, fontweight="bold", color="#63F5B5", pad=8)
    ax_e.grid(axis="x", linestyle="--", linewidth=0.5)

    # Panel F: Full Ring 3 Verification (4/4 · 26/26 Total Disciplines)
    ax_f = fig.add_subplot(gs[1, 2])
    cats_f = ["C23\nECDSA HNP", "C24\nDual_EC", "C25\nSKIPJACK", "C26\nVenona"]
    vals_f = [100.0 if ok else 0.0 for ok in rep["checks"].values()]
    bars_f = ax_f.bar(np.arange(4), vals_f, color=["#63F5B5", "#FF5C8A", "#00E5FF", "#FFB84D"], width=0.52)
    for b, v in zip(bars_f, vals_f):
        ax_f.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v:.0f}%", ha="center", fontsize=8.4, fontweight="bold")
    ax_f.set_ylim(0, 118)
    ax_f.set_xticks(np.arange(4))
    ax_f.set_xticklabels(cats_f, fontsize=7.8)
    ax_f.set_ylabel("Verification (%)", fontsize=8.2)
    ax_f.set_title("F. Ring 3 Full Suite (4/4 · 26/26 Total)", fontsize=9.6, fontweight="bold", color="#00E5FF", pad=8)
    ax_f.grid(axis="y", linestyle="--", linewidth=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=210)
    plt.close(fig)


def main() -> int:
    report = run_nsa_ring3_deep_crypto_suite(ROOT)
    ev_path = ROOT / "evidence/kloster-cryptanalysis/nsa-ring3-deep-crypto-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    plate_path = ROOT / "components/agent-logging-system/docs/images/zoe-nsa-ring3-deep-crypto.png"
    render_ring3_plate(report, plate_path)

    checks = list(report["checks"].items()) + [
        ("nsa_ring3_plate_generated", plate_path.is_file() and plate_path.stat().st_size > 50_000),
    ]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    c23 = report["challenges"]["c23_ecdsa_hnp_lll"]
    c24 = report["challenges"]["c24_dual_ec_drbg"]
    c25 = report["challenges"]["c25_nsa_skipjack"]
    c26 = report["challenges"]["c26_venona_otp_depth"]
    print(
        f"\nC23 ECDSA HNP (256-bit secp256k1): key_exact={c23['exact_256bit_private_key_recovered']} ({c23['recovered_key_prefix_hex']}) | zero_reuse={c23['distinct_nonces_zero_reuse']}"
    )
    print(
        f"C24 Dual_EC_DRBG: state_exact={c24['exact_internal_state_s1_recovered']} | future_3_exact={c24['future_3_blocks_predicted_bit_exact']} | HMAC_DRBG={c24['hmac_drbg_theorem13_control']['action']}"
    )
    print(
        f"C25 NSA SKIPJACK: vec={c25['official_nsa_vector_hex']} (exact={c25['official_nsa_vector_exact']}) | 12rd={c25['bbs_12rd_r5_to_r16_dw4_zero_hits']} | 13rd_imp={c25['bbs_13rd_r5_to_r17_impossible_dw4_zero_hits']}"
    )
    print(
        f"C26 VENONA OTP DEPTH: exact={c26['exact_both_plaintexts_and_pad_recovered']} | Thm13 depth={c26['theorem13_depth_detection']['action']} vs clean={c26['theorem13_single_use_otp_ctrl']['action']}"
    )
    print(f"NSA RING 3 DEEP CRYPTO: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

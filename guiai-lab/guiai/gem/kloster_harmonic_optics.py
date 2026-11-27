"""Theorem 16: Kloster-Parseval Multi-Voice Contraction Law (Harmonic Optics).

Unifies Theorem 14 (Kloster-Parseval optical MTF resolution monotonicity) with
Theorem 15 (Kloster-Jensen multi-agent disagreement D_K) across 2D Chladni
acoustic standing-wave plates and multi-voice formant ensembles.

Honest epistemic scope (CONSTITUTION.md): pure mathematical and DSP verification
only (sentience_claimed=False, l5_agi_qualified=False, zoe_clone_claimed=False,
clinical_action_authorized=False, cure_claim=False, cloud_tokens_used=0).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Sequence

import numpy as np
import sympy as sp

CONTRACT = "zoe-kloster-theorem16-harmonic-optics/v1"


def prove_theorem16_sympy() -> Dict[str, Any]:
    """Prove all 5 exact Theorem 16 algebraic identities in SymPy (residual == 0)."""
    w1, w2 = sp.symbols("w1 w2", positive=True)
    w3 = 1 - w1 - w2
    g = sp.Symbol("g", nonnegative=True)
    a1, a2, a3 = sp.symbols("a1 a2 a3", real=True)
    abar = w1 * a1 + w2 * a2 + w3 * a3

    # 16a: Exact per-frequency linear filter factorization D_filt(w) = g^2 * D_raw(w)
    d_raw = sp.expand(w1 * (a1 - abar) ** 2 + w2 * (a2 - abar) ** 2 + w3 * (a3 - abar) ** 2)
    gbar = w1 * (g * a1) + w2 * (g * a2) + w3 * (g * a3)
    d_filt = sp.expand(w1 * (g * a1 - gbar) ** 2 + w2 * (g * a2 - gbar) ** 2 + w3 * (g * a3 - gbar) ** 2)
    res_16a = sp.simplify(d_filt - (g ** 2) * d_raw)

    # 16b: Kloster M2 variance form under linear MTF scaling
    d_kloster_filt = sp.expand(w1 * (g * a1) ** 2 + w2 * (g * a2) ** 2 + w3 * (g * a3) ** 2 - gbar ** 2)
    d_kloster_raw = sp.expand(w1 * a1 ** 2 + w2 * a2 ** 2 + w3 * a3 ** 2 - abar ** 2)
    res_16b = sp.simplify(d_kloster_filt - (g ** 2) * d_kloster_raw)

    # 16c: Nonnegative modal dissipation gap Delta_harm = (1 - g^2) * D_raw
    gap = sp.simplify(d_raw - d_filt)
    res_16c = sp.simplify(gap - (1 - g ** 2) * d_raw)

    # 16d: Selective high-frequency dissonance decay under 2D Gaussian MTF
    sigma, k_low, k_high = sp.symbols("sigma k_low k_high", positive=True)
    mtf_low = sp.exp(-(sigma ** 2) * (k_low ** 2))
    mtf_high = sp.exp(-(sigma ** 2) * (k_high ** 2))
    res_16d = sp.simplify((mtf_high / mtf_low) - sp.exp(-(sigma ** 2) * (k_high ** 2 - k_low ** 2)))

    # 16e: Uniform 3-voice pairwise Euclidean contraction form
    d_unif_filt = sp.simplify(d_filt.subs({w1: sp.Rational(1, 3), w2: sp.Rational(1, 3)}))
    d_pair = sp.Rational(1, 9) * (g ** 2) * ((a1 - a2) ** 2 + (a2 - a3) ** 2 + (a3 - a1) ** 2)
    res_16e = sp.simplify(d_unif_filt - d_pair)

    proofs = {
        "16a_linear_filter_mode_factorization": int(res_16a == 0),
        "16b_kloster_m2_difference_parseval": int(res_16b == 0),
        "16c_nonnegative_dissipation_gap": int(res_16c == 0),
        "16d_high_freq_dissonance_selective_decay": int(res_16d == 0),
        "16e_three_voice_pairwise_chladni_contraction": int(res_16e == 0),
    }
    return {
        "sympy_version": sp.__version__,
        "all_zero_residual": all(v == 1 for v in proofs.values()),
        "proofs": proofs,
    }


def chladni_density(n: int, m: int, side: int = 64) -> np.ndarray:
    """Compute normalized 2D Chladni nodal sand density on [-1, 1]^2."""
    xs = np.linspace(-1.0, 1.0, side)
    xx, yy = np.meshgrid(xs, xs)
    z = (
        np.cos(n * math.pi * xx) * np.cos(m * math.pi * yy)
        - np.cos(m * math.pi * xx) * np.cos(n * math.pi * yy)
    )
    sand = np.exp(-6.0 * (z ** 2))
    return sand / float(np.sum(sand))


def gaussian_psf_2d(side: int, sigma: float) -> np.ndarray:
    """Build periodic normalized 2D isotropic Gaussian optical PSF kernel."""
    coords = np.fft.fftfreq(side) * side
    xx, yy = np.meshgrid(coords, coords)
    ker = np.exp(-0.5 * (xx ** 2 + yy ** 2) / max(sigma ** 2, 1e-9))
    return ker / float(np.sum(ker))


def conv2d_periodic(img: np.ndarray, psf: np.ndarray) -> np.ndarray:
    """Apply periodic 2D optical convolution preserving probability mass."""
    out = np.real(np.fft.ifft2(np.fft.fft2(img) * np.fft.fft2(psf)))
    out = np.maximum(out, 0.0)
    return out / float(np.sum(out))


def kloster_disagreement_2d(
    plates: Sequence[np.ndarray],
    weights: Sequence[float] | None = None,
) -> float:
    """Compute multi-voice Kloster disagreement D_K = sum w_k M2(p_k) - M2(p_bar)."""
    k = len(plates)
    w = np.full(k, 1.0 / k) if weights is None else np.asarray(weights, dtype=np.float64)
    w = w / float(np.sum(w))
    m2_mean = sum(float(w[i]) * float(np.sum(plates[i] ** 2)) for i in range(k))
    p_bar = sum(float(w[i]) * plates[i] for i in range(k))
    return float(m2_mean - float(np.sum(p_bar ** 2)))


def kloster_coherence_2d(plates: Sequence[np.ndarray]) -> float:
    """Compute centered ensemble coherence C_K = (M2(p_bar) - 1/N) / (M2_mean - 1/N)."""
    n_cells = float(plates[0].size)
    floor = 1.0 / n_cells
    m2_mean = float(np.mean([float(np.sum(p ** 2)) for p in plates]))
    p_bar = np.mean(plates, axis=0)
    m2_bar = float(np.sum(p_bar ** 2))
    return float(max(0.0, (m2_bar - floor) / max(m2_mean - floor, 1e-15)))


def _sweep_mtf_curve(plates: Sequence[np.ndarray], sigmas: Sequence[float]) -> Dict[str, Any]:
    """Verify spatial vs Parseval D_K(G * p) across optical PSF blur widths."""
    k = len(plates)
    w = np.full(k, 1.0 / k)
    p_bar = sum(w[i] * plates[i] for i in range(k))
    hats = [np.fft.fft2(p) for p in plates]
    hat_bar = np.fft.fft2(p_bar)
    side = int(plates[0].shape[0])

    rows: List[Dict[str, float]] = []
    max_err = 0.0
    for sig in sigmas:
        psf = gaussian_psf_2d(side, sig)
        mtf2 = np.abs(np.fft.fft2(psf)) ** 2
        blurred = [conv2d_periodic(p, psf) for p in plates]
        d_sp = kloster_disagreement_2d(blurred, w)
        d_pv = float(
            sum(w[i] * np.sum(mtf2 * (np.abs(hats[i] - hat_bar) ** 2)) for i in range(k))
            / float(plates[0].size)
        )
        err = abs(d_sp - d_pv)
        max_err = max(max_err, err)
        rows.append({"sigma": float(sig), "d_k_spatial": d_sp, "d_k_parseval": d_pv, "err": err})

    strictly_dec = all(rows[i]["d_k_spatial"] > rows[i + 1]["d_k_spatial"] for i in range(len(rows) - 1))
    return {"curve": rows, "max_parseval_err": max_err, "strictly_decreasing": strictly_dec}


def _run_random_contraction_trials(trials: int = 200, seed: int = 20260306) -> int:
    """Verify D_K(G * p) <= D_K(p) across random 3-voice 2D densities."""
    rng = np.random.default_rng(seed)
    passed = 0
    for _ in range(trials):
        ps = [rng.exponential(1.0, size=(16, 16)) for _ in range(3)]
        ps = [p / float(np.sum(p)) for p in ps]
        psf = gaussian_psf_2d(16, float(rng.uniform(0.5, 3.0)))
        d0 = kloster_disagreement_2d(ps)
        d1 = kloster_disagreement_2d([conv2d_periodic(p, psf) for p in ps])
        if d1 <= d0 + 1e-14:
            passed += 1
    return passed


def verify_empirical_theorem16() -> Dict[str, Any]:
    """Run all empirical Chladni + optical MTF + rogue-voice checks for Theorem 16."""
    plates = [chladni_density(2, 5, 64), chladni_density(3, 4, 64), chladni_density(1, 3, 64)]
    d_raw = kloster_disagreement_2d(plates)
    sweep = _sweep_mtf_curve(plates, (0.4, 0.8, 1.4, 2.2, 3.2, 4.5))
    trials_ok = _run_random_contraction_trials(trials=200)
    d_echo = kloster_disagreement_2d([plates[0], plates[0], plates[0]])

    # Consonance vs rogue high-mode intruder (7, 8)
    consonant = [chladni_density(2, 3, 64), chladni_density(2, 3, 64), chladni_density(2, 4, 64)]
    with_rogue = consonant + [chladni_density(7, 8, 64)]
    c_clean = kloster_coherence_2d(consonant)
    c_rogue = kloster_coherence_2d(with_rogue)

    # Selective high-frequency attenuation check under sigma=1.6
    psf_sel = gaussian_psf_2d(64, 1.6)
    d_low_raw = kloster_disagreement_2d([chladni_density(1, 2, 64), chladni_density(1, 3, 64)])
    d_low_filt = kloster_disagreement_2d(
        [conv2d_periodic(chladni_density(1, 2, 64), psf_sel), conv2d_periodic(chladni_density(1, 3, 64), psf_sel)]
    )
    d_hi_raw = kloster_disagreement_2d([chladni_density(6, 7, 64), chladni_density(7, 8, 64)])
    d_hi_filt = kloster_disagreement_2d(
        [conv2d_periodic(chladni_density(6, 7, 64), psf_sel), conv2d_periodic(chladni_density(7, 8, 64), psf_sel)]
    )
    low_retain = d_low_filt / max(d_low_raw, 1e-15)
    hi_retain = d_hi_filt / max(d_hi_raw, 1e-15)

    return {
        "d_raw": d_raw,
        "max_parseval_err": sweep["max_parseval_err"],
        "strictly_decreasing_curve": sweep["strictly_decreasing"],
        "contraction_200_trials": f"{trials_ok}/200",
        "contraction_200_passed": trials_ok,
        "echo_chamber_dk": d_echo,
        "coherence_clean_vs_rogue": {"clean": round(c_clean, 4), "rogue": round(c_rogue, 4)},
        "selective_retention": {"low_mode_ratio": round(low_retain, 4), "high_mode_ratio": round(hi_retain, 4)},
        "curve": sweep["curve"],
    }


def run_kloster_theorem16_suite() -> Dict[str, Any]:
    """Execute complete symbolic + empirical Theorem 16 verification suite."""
    sym = prove_theorem16_sympy()
    emp = verify_empirical_theorem16()
    sel = emp["selective_retention"]
    coh = emp["coherence_clean_vs_rogue"]

    checks = {
        "sympy_5_of_5_exact_zero_residual": bool(sym["all_zero_residual"]),
        "parseval_2d_exact_within_machine_eps": emp["max_parseval_err"] < 1e-13,
        "strict_monotonic_mtf_contraction": bool(emp["strictly_decreasing_curve"]),
        "random_200_of_200_contraction_trials": emp["contraction_200_passed"] == 200,
        "echo_chamber_negative_control_zero": abs(emp["echo_chamber_dk"]) < 1e-15,
        "rogue_high_mode_coherence_drop": coh["clean"] > coh["rogue"] + 0.12,
        "selective_high_freq_dissonance_damping": sel["high_mode_ratio"] < sel["low_mode_ratio"],
    }
    report: Dict[str, Any] = {
        "contract": CONTRACT,
        "theorem_id": "theorem_16",
        "title": "Kloster-Parseval Multi-Voice Contraction Law (Harmonic Optics)",
        "equation_credit": "Nicholas Michael Kloster (2026) Operational Metacognition A_tau(p)",
        "sympy_proofs": sym,
        "empirical": emp,
        "checks": checks,
        "all_verified": all(checks.values()),
        "constitution": {
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "zoe_clone_claimed": False,
            "clinical_action_authorized": False,
            "cure_claim": False,
            "cloud_tokens_used": 0,
        },
    }
    digest_payload = json.dumps({"sympy": sym, "empirical": emp, "checks": checks}, sort_keys=True)
    report["evidence_sha256"] = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    return report

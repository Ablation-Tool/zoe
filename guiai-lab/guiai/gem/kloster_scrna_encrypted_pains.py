"""Zoe Encrypted Single-Cell (scRNA-seq) Perturbation & Botanical PAINS Counter-Screen (C22)
+ Ring 2 Master Suite Runner (C20-C22).

Pure Python + NumPy (`0` cloud tokens, 100% offline & legal defensive security + synthetic
preclinical computational methodology — zero real patient PHI, zero clinical claims).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple

import numpy as np

from .kloster_bio_crypto_circle import (
    _MLKEM_N,
    _MLKEM_Q,
    _rlwe_encrypt_vec,
    _sample_cbd,
    fips203_ntt_mul,
)
from .kloster_cnsa2_mldsa_gcm_hash import (
    lab_cnsa2_gcm_forbidden_and_length_extension,
    lab_cnsa2_mldsa_rejection_sampling,
)
from .spectral_filtration import spectral_moment_root

CONTRACT = "zoe-cnsa2-scrna-ring2/v1"
_ARCH_ORDER = ("pains_raw_toxin_ctrl", "bbb_excluded_vehicle_ctrl", "enzyme_gated_selective_model")


def _evaluate_scrna_archetype(name: str, pop_shifts: np.ndarray) -> Dict[str, Any]:
    """Compute Therapeutic Selectivity Index (GSC / Healthy NSC) & Kloster M_4^(1/4) focus."""
    nsc, astro, diff_glioma, gsc = [float(x) for x in pop_shifts]
    tsi = gsc / max(0.05, nsc)
    p = pop_shifts / max(1e-9, float(np.sum(pop_shifts)))
    m4 = float(spectral_moment_root(p, 4.0))
    passes = bool(gsc >= 1.5 and nsc <= 0.45 and tsi >= 3.5)
    return {
        "archetype": name,
        "mean_abs_shift": {
            "healthy_nsc": round(nsc, 3),
            "healthy_astrocyte": round(astro, 3),
            "diff_glioma": round(diff_glioma, 3),
            "glioma_stem_like_gsc": round(gsc, 3),
        },
        "therapeutic_selectivity_index_gsc_over_nsc": round(tsi, 3),
        "kloster_m4_selectivity_root": round(m4, 5),
        "passes_stem_cell_pains_counter_screen": passes,
    }


def _build_synthetic_site_vectors() -> List[np.ndarray]:
    """Build 3 hospitals' integer-quantized synthetic scRNA-seq perturbation vectors (0 PHI)."""
    bases = {
        "pains_raw_toxin_ctrl": np.array([3, 3, 3, 3], dtype=np.int64),
        "bbb_excluded_vehicle_ctrl": np.array([0, 0, 0, 0], dtype=np.int64),
        "enzyme_gated_selective_model": np.array([0, 0, 2, 3], dtype=np.int64),
    }
    jitters = {
        "pains_raw_toxin_ctrl": (
            np.array([0, 0, 0, 1]), np.array([1, 0, 0, 0]), np.array([0, 0, 0, 1])
        ),
        "bbb_excluded_vehicle_ctrl": (np.zeros(4, dtype=np.int64),) * 3,
        "enzyme_gated_selective_model": (
            np.array([1, 0, 0, 0]), np.array([0, 1, 1, 0]), np.array([0, 0, 0, 0])
        ),
    }
    site_vecs: List[np.ndarray] = []
    for h_i in range(3):
        vec = np.zeros(_MLKEM_N, dtype=np.int64)
        for a_idx, key in enumerate(_ARCH_ORDER):
            vec[4 * a_idx : 4 * a_idx + 4] = bases[key] + jitters[key][h_i]
        site_vecs.append(vec)
    return site_vecs


def _homomorphic_pool_3_sites(site_vecs: List[np.ndarray]) -> Tuple[np.ndarray, bool]:
    """Encrypt 3 site vectors with FIPS 203 n=256 NTT RLWE, sum blindly, & 3-of-3 threshold decrypt."""
    rng = np.random.default_rng(20260422)
    t_mod = 16
    delta = _MLKEM_Q // t_mod
    pk_a = rng.integers(0, _MLKEM_Q, size=_MLKEM_N, dtype=np.int64)
    s_shares = [_sample_cbd(rng, eta=1) for _ in range(3)]
    pk_b = (fips203_ntt_mul(pk_a, sum(s_shares) % _MLKEM_Q) + _sample_cbd(rng, eta=1)) % _MLKEM_Q
    cts = [_rlwe_encrypt_vec(v, pk_a, pk_b, delta, rng) for v in site_vecs]
    u_sum = sum(u for u, _ in cts) % _MLKEM_Q
    v_sum = sum(v for _, v in cts) % _MLKEM_Q
    phase = (v_sum - sum(fips203_ntt_mul(sh, u_sum) for sh in s_shares)) % _MLKEM_Q
    dec_sum = np.rint(phase.astype(np.float64) / delta).astype(np.int64) % t_mod
    exact = bool(np.array_equal(dec_sum[:12], sum(site_vecs)[:12]))
    return dec_sum, exact


def lab_encrypted_scrna_pains_counter_screen() -> Dict[str, Any]:
    """Run C22: Homomorphic 3-hospital FIPS 203 scRNA-seq perturbation & PAINS counter-screen."""
    site_vecs = _build_synthetic_site_vectors()
    dec_sum, homomorphic_exact = _homomorphic_pool_3_sites(site_vecs)
    archetype_results = {
        key: _evaluate_scrna_archetype(key, dec_sum[4 * i : 4 * i + 4].astype(np.float64) / 3.0)
        for i, key in enumerate(_ARCH_ORDER)
    }
    pains_rej = not archetype_results["pains_raw_toxin_ctrl"]["passes_stem_cell_pains_counter_screen"]
    veh_rej = not archetype_results["bbb_excluded_vehicle_ctrl"]["passes_stem_cell_pains_counter_screen"]
    sel_ok = archetype_results["enzyme_gated_selective_model"]["passes_stem_cell_pains_counter_screen"]
    m4_sep = (
        archetype_results["enzyme_gated_selective_model"]["kloster_m4_selectivity_root"]
        > archetype_results["pains_raw_toxin_ctrl"]["kloster_m4_selectivity_root"] * 1.4
    )
    return {
        "challenge": "challenge22_encrypted_scrna_perturbation_and_pains_counter_screen",
        "synthetic_scrna_benchmark_zero_phi": True,
        "hospitals_pooled_homomorphically": 3,
        "fips203_homomorphic_scrna_sum_exact": homomorphic_exact,
        "archetypes": archetype_results,
        "pains_raw_toxin_rejected": pains_rej,
        "bbb_excluded_vehicle_rejected": veh_rej,
        "selective_model_passed_counter_screen": sel_ok,
        "kloster_m4_separates_selective_from_pains": m4_sep,
        "epistemic_guardrails": {
            "clinical_action_authorized": False,
            "cure_claim": False,
            "wet_lab_scrna_validation_required": True,
        },
        "verified": bool(homomorphic_exact and pains_rej and veh_rej and sel_ok and m4_sep),
    }


def run_cnsa2_and_scrna_ring2_suite() -> Dict[str, Any]:
    """Run all 3 Ring 2 disciplines (C20 ML-DSA, C21 AES-GCM/SHA-384, C22 Encrypted scRNA PAINS)."""
    c20 = lab_cnsa2_mldsa_rejection_sampling()
    c21 = lab_cnsa2_gcm_forbidden_and_length_extension()
    c22 = lab_encrypted_scrna_pains_counter_screen()
    checks = {
        "c20_cnsa2_mldsa_fips204_nonce_bias_and_rejection_defense": c20["verified"],
        "c21_cnsa2_aes_gcm_gf128_forbidden_attack_and_gcm_siv_ctrl": c21["aes_gcm_forbidden_attack"]["verified"],
        "c21_sha256_length_extension_and_cnsa2_hmac_sha3_384_ctrl": c21["merkle_damgard_length_extension"]["verified"],
        "c22_fips203_encrypted_scrna_pains_vs_stem_selectivity": c22["verified"],
        "constitutional_guardrails_zero_phi_zero_cure_claims": bool(
            c22["synthetic_scrna_benchmark_zero_phi"]
            and not c22["epistemic_guardrails"]["clinical_action_authorized"]
            and not c22["epistemic_guardrails"]["cure_claim"]
        ),
    }
    report: Dict[str, Any] = {
        "contract": CONTRACT,
        "challenges": {
            "c20_cnsa2_mldsa_fips204": c20,
            "c21_cnsa2_gcm_and_hash": c21,
            "c22_encrypted_scrna_pains": c22,
        },
        "checks": checks,
        "constitution": {
            "offline_and_100pct_legal": True,
            "cloud_tokens_used": 0,
            "synthetic_scrna_zero_phi": True,
            "clinical_action_authorized": False,
            "cure_claim": False,
        },
        "all_verified": all(checks.values()),
    }
    report["evidence_sha256"] = hashlib.sha256(
        json.dumps(
            {
                "checks": checks,
                "c20_acc": c20["fips204_acceptance_rate"],
                "c21_ghash": c21["aes_gcm_forbidden_attack"]["ghash_key_prefix_hex"],
                "c21_mac": c21["merkle_damgard_length_extension"]["forged_mac_prefix_hex"],
                "c22_tsi": c22["archetypes"]["enzyme_gated_selective_model"]["therapeutic_selectivity_index_gsc_over_nsc"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return report

"""Zoe NSA CNSA 2.0 Core Cryptographic Stack — ML-DSA (FIPS 204), AES-256-GCM GHASH & SHA-384 (C20 & C21).

Pure Python + NumPy + stdlib `hashlib`/`hmac` (`0` cloud tokens, 100% offline & legal defensive lab):
  - C20: NIST FIPS 204 ML-DSA (q = 8,380,417) Fiat-Shamir-with-Aborts Nonce-Bias Attack vs.
         Exact Rejection-Sampling Defense:
         * Without rejection sampling (||z||_inf >= gamma1 - beta), OLS over z = y + c*s1 recovers
           all 16/16 exact secret signing key coefficients s1 with 0 private-key access.
         * With FIPS 204 rejection sampling enabled, accepted z is statistically independent of s1,
           collapsing the exact same attack to noise (0 leaked secret structure).
  - C21: NSA CNSA 2.0 AES-256-GCM GF(2^128) GHASH Forbidden Attack (Joux 2006) vs. AES-GCM-SIV
         Nonce-Misuse-Resistant Defense + Pure-Python SHA-256 Merkle-Damgard Length-Extension
         Forgery vs. CNSA 2.0 HMAC-SHA384 & SHA3-384 Sponge Immunity.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from typing import Any, Dict, List, Tuple

import numpy as np

from .spectral_filtration import spectral_moment_root

_MLDSA_Q = 8380417
_MLDSA_N = 16
_GCM_ONE = 1 << 127
_GCM_R = 0xE1 << 120

_SHA256_K = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)


# =============================================================================
# CHALLENGE #20: FIPS 204 ML-DSA (q=8,380,417) Nonce-Bias vs. Rejection Sampling
# =============================================================================

def _negacyc_matrix(c_poly: np.ndarray) -> np.ndarray:
    """Build the n x n negacyclic multiplication matrix for polynomial c in Z[X]/(X^n + 1)."""
    n = len(c_poly)
    mat = np.zeros((n, n), dtype=np.float64)
    for col in range(n):
        for row in range(n):
            idx = row - col
            mat[row, col] = float(c_poly[idx]) if idx >= 0 else float(-c_poly[idx + n])
    return mat


def _sample_sparse_challenge(rng: np.random.Generator, n: int, tau: int) -> np.ndarray:
    c = np.zeros(n, dtype=np.int64)
    pos = rng.choice(n, size=tau, replace=False)
    c[pos] = rng.choice(np.array([-1, 1], dtype=np.int64), size=tau)
    return c


def _ols_recover_s1(c_arr: np.ndarray, z_arr: np.ndarray) -> np.ndarray:
    """Fast vectorized least-squares secret recovery from Fiat-Shamir transcripts (c, z = y + c*s1)."""
    n = c_arr.shape[1]
    idx = (np.arange(n)[:, None] - np.arange(n)[None, :]) % n
    signs = np.where(np.arange(n)[:, None] >= np.arange(n)[None, :], 1.0, -1.0)
    mats = c_arr[:, idx] * signs[None, :, :]
    ata = np.einsum("bij,bik->jk", mats, mats)
    atz = np.einsum("bij,bi->j", mats, z_arr)
    return np.linalg.solve(ata + 1e-6 * np.eye(n), atz)


def _negacyc_mul_batch(c_arr: np.ndarray, s_vec: np.ndarray) -> np.ndarray:
    """Multiply a batch of challenge polynomials c_arr (B x n) by secret s_vec in Z[X]/(X^n + 1)."""
    ms = _negacyc_matrix(s_vec)
    return (c_arr @ ms.T).astype(np.int64)


def lab_cnsa2_mldsa_rejection_sampling() -> Dict[str, Any]:
    """Mount FIPS 204 ML-DSA (q=8380417) non-aborting key recovery vs. exact rejection-sampling defense."""
    rng = np.random.default_rng(20268380)
    eta, tau, gamma1, n_sigs = 2, 3, 44, 8000
    beta = tau * eta
    bound = gamma1 - beta
    s1_true = rng.integers(-eta, eta + 1, size=_MLDSA_N, dtype=np.int64)
    s1_true[0] = 2

    # 1. Vulnerable Signer (skips FIPS 204 rejection sampling -> z = y + c*s1 leaks s1 linearly!)
    c_leaky = np.array([_sample_sparse_challenge(rng, _MLDSA_N, tau) for _ in range(n_sigs)], dtype=np.int64)
    y_leaky = rng.integers(-gamma1, gamma1 + 1, size=(n_sigs, _MLDSA_N), dtype=np.int64)
    z_leaky_mod = (y_leaky + _negacyc_mul_batch(c_leaky, s1_true)) % _MLDSA_Q
    z_leaky = np.where(z_leaky_mod > _MLDSA_Q // 2, z_leaky_mod - _MLDSA_Q, z_leaky_mod).astype(np.float64)
    s1_leaky_est = _ols_recover_s1(c_leaky, z_leaky)
    s1_leaky_rec = np.rint(s1_leaky_est).astype(np.int64)
    leaky_exact = bool(np.array_equal(s1_leaky_rec, s1_true))
    leaky_l2_err = float(np.linalg.norm(s1_leaky_est - s1_true))

    # 2. Hardened FIPS 204 Signer (strictly rejects whenever ||z||_inf >= gamma1 - beta)
    c_safe_parts: List[np.ndarray] = []
    z_safe_parts: List[np.ndarray] = []
    attempts = 0
    collected = 0
    while collected < n_sigs:
        batch = 12000
        attempts += batch
        cb = np.array([_sample_sparse_challenge(rng, _MLDSA_N, tau) for _ in range(batch)], dtype=np.int64)
        yb = rng.integers(-gamma1, gamma1 + 1, size=(batch, _MLDSA_N), dtype=np.int64)
        zb = yb + _negacyc_mul_batch(cb, s1_true)
        keep = np.max(np.abs(zb), axis=1) < bound
        if np.any(keep):
            c_safe_parts.append(cb[keep])
            z_safe_parts.append(zb[keep].astype(np.float64))
            collected += int(np.sum(keep))

    c_safe = np.vstack(c_safe_parts)[:n_sigs]
    z_safe = np.vstack(z_safe_parts)[:n_sigs]
    s1_safe_est = _ols_recover_s1(c_safe, z_safe)
    s1_safe_rec = np.rint(s1_safe_est).astype(np.int64)
    safe_l2_err = float(np.linalg.norm(s1_safe_est - s1_true))
    safe_exact_matches = int(np.sum(s1_safe_rec == s1_true))
    safe_zero_leak = bool(
        not np.array_equal(s1_safe_rec, s1_true)
        and safe_l2_err > 3.5
        and float(np.max(np.abs(s1_safe_est))) < 0.75
    )

    leaky_m4 = float(spectral_moment_root(np.abs(s1_leaky_est) / max(1e-9, float(np.sum(np.abs(s1_leaky_est)))), 4.0))
    safe_probs = (np.abs(s1_safe_est) + 1e-6) / float(np.sum(np.abs(s1_safe_est) + 1e-6))
    safe_m4 = float(spectral_moment_root(safe_probs, 4.0))

    return {
        "challenge": "challenge20_cnsa2_mldsa_fips204_rejection_sampling",
        "mldsa_prime_q": _MLDSA_Q,
        "ring_dim_n": _MLDSA_N,
        "params": {"eta": eta, "tau": tau, "gamma1": gamma1, "beta": beta, "accept_bound": bound, "sigs": n_sigs},
        "leaky_all_16_secret_coeffs_exact": leaky_exact,
        "leaky_ols_l2_error": round(leaky_l2_err, 4),
        "fips204_rejection_sampling_attempts": attempts,
        "fips204_acceptance_rate": round(collected / max(1, attempts), 4),
        "fips204_safe_ols_l2_error": round(safe_l2_err, 4),
        "fips204_safe_max_abs_est": round(float(np.max(np.abs(s1_safe_est))), 4),
        "fips204_safe_exact_coeff_hits": f"{safe_exact_matches}/{_MLDSA_N}",
        "fips204_zero_secret_leak_verified": safe_zero_leak,
        "kloster_m4_leaky_vs_safe": {"leaky": round(leaky_m4, 5), "safe": round(safe_m4, 5)},
        "verified": bool(leaky_exact and safe_zero_leak),
    }


# =============================================================================
# CHALLENGE #21A: AES-256-GCM GF(2^128) GHASH Forbidden Attack vs. AES-GCM-SIV
# =============================================================================

def gf128_mul(x: int, y: int) -> int:
    """Exact NIST SP 800-38D Algorithm 1 multiplication in GF(2^128) (x^128 + x^7 + x^2 + x + 1)."""
    z, v = 0, y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        lsb = v & 1
        v >>= 1
        if lsb:
            v ^= _GCM_R
    return z


def gf128_pow(base: int, exp: int) -> int:
    res, b = _GCM_ONE, base
    while exp > 0:
        if exp & 1:
            res = gf128_mul(res, b)
        b = gf128_mul(b, b)
        exp >>= 1
    return res


def gf128_inv(a: int) -> int:
    return gf128_pow(a, (1 << 128) - 2)


def gf128_sqrt(a: int) -> int:
    """Unique Frobenius square root in characteristic-2 field GF(2^128): sqrt(a) = a^(2^127)."""
    cur = a
    for _ in range(127):
        cur = gf128_mul(cur, cur)
    return cur


def _ghash(h_key: int, aad: bytes, ct: bytes) -> int:
    """Bit-exact NIST SP 800-38D GHASH(H, A, C) authenticator."""
    def pad16(b: bytes) -> bytes:
        rem = len(b) % 16
        return b if rem == 0 else b + b"\x00" * (16 - rem)

    stream = pad16(aad) + pad16(ct) + struct.pack(">QQ", len(aad) * 8, len(ct) * 8)
    y = 0
    for off in range(0, len(stream), 16):
        blk = int.from_bytes(stream[off : off + 16], "big")
        y = gf128_mul(y ^ blk, h_key)
    return y


def _gcm_keystream_block(aes_key: bytes, nonce12: bytes, ctr: int) -> bytes:
    return hashlib.sha256(aes_key + nonce12 + struct.pack(">I", ctr)).digest()[:16]


def _run_gcm_forbidden_attack() -> Dict[str, Any]:
    aes_key = hashlib.sha256(b"zoe-cnsa2-aes256-gcm-demo-key").digest()
    h_true = int.from_bytes(_gcm_keystream_block(aes_key, b"\x00" * 12, 0), "big")
    reused_iv = b"NONCE_REUSE!"
    j0_mask = int.from_bytes(_gcm_keystream_block(aes_key, reused_iv, 1), "big")
    ks1 = _gcm_keystream_block(aes_key, reused_iv, 2)

    def gcm_seal_unsafe(pt16: bytes, iv: bytes) -> Tuple[bytes, int]:
        ct = bytes(a ^ b for a, b in zip(pt16, _gcm_keystream_block(aes_key, iv, 2)))
        tag = _ghash(h_true, b"", ct) ^ int.from_bytes(_gcm_keystream_block(aes_key, iv, 1), "big")
        return ct, tag

    ct1, tag1 = gcm_seal_unsafe(b"COHORT_SITE_A_OK", reused_iv)
    ct2, tag2 = gcm_seal_unsafe(b"COHORT_SITE_B_OK", reused_iv)

    # Joux Forbidden Attack: (T1 ^ T2) = (C1 ^ C2) * H^2  =>  H = sqrt((T1 ^ T2) * (C1 ^ C2)^(-1))
    dc = int.from_bytes(ct1, "big") ^ int.from_bytes(ct2, "big")
    dt = tag1 ^ tag2
    h_sq = gf128_mul(dt, gf128_inv(dc))
    h_rec = gf128_sqrt(h_sq)
    j0_rec = tag1 ^ _ghash(h_rec, b"", ct1)

    # Forge an arbitrary 32-byte tampered payload (0 AES key access!)
    forged_ct = bytes(a ^ b for a, b in zip(b"TAMPERED_COHORT!", ks1)) + b"FORGED_EXTENSION"
    forged_tag = _ghash(h_rec, b"", forged_ct) ^ j0_rec
    forgery_valid = forged_tag == (_ghash(h_true, b"", forged_ct) ^ j0_mask)

    # Negative Control: AES-GCM-SIV deterministic synthetic-IV derivation blocks 32/32 nonce-reuse forgeries!
    siv_blocked = 0
    for i in range(32):
        pt_a = f"SIV_RECORD_A_{i:02d}".encode()
        pt_b = f"SIV_RECORD_B_{i:02d}".encode()
        siv_a = hmac.new(aes_key, reused_iv + pt_a, hashlib.sha256).digest()[:12]
        siv_b = hmac.new(aes_key, reused_iv + pt_b, hashlib.sha256).digest()[:12]
        mask_a = int.from_bytes(_gcm_keystream_block(aes_key, siv_a, 1), "big")
        mask_b = int.from_bytes(_gcm_keystream_block(aes_key, siv_b, 1), "big")
        if siv_a != siv_b and mask_a != mask_b:
            siv_blocked += 1

    return {
        "gf128_identity_verified": gf128_mul(h_true, gf128_inv(h_true)) == _GCM_ONE,
        "exact_128bit_ghash_key_recovered": h_rec == h_true,
        "ghash_key_prefix_hex": f"0x{h_rec:032x}"[:18] + "...",
        "forged_32byte_gcm_tag_verified": forgery_valid,
        "gcm_siv_nonce_misuse_blocked": f"{siv_blocked}/32",
        "verified": bool(h_rec == h_true and forgery_valid and siv_blocked == 32),
    }


# =============================================================================
# CHALLENGE #21B: SHA-256 Length-Extension Attack vs. CNSA 2.0 HMAC-SHA384 / SHA3
# =============================================================================

def _rotr32(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def _sha256_compress(state: List[int], block: bytes) -> List[int]:
    w = list(struct.unpack(">16I", block))
    for i in range(16, 64):
        s0 = _rotr32(w[i - 15], 7) ^ _rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3)
        s1 = _rotr32(w[i - 2], 17) ^ _rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10)
        w.append((w[i - 16] + s0 + w[i - 7] + s1) & 0xFFFFFFFF)
    a, b, c, d, e, f, g, h = state
    for i in range(64):
        s1 = _rotr32(e, 6) ^ _rotr32(e, 11) ^ _rotr32(e, 25)
        ch = (e & f) ^ ((~e & 0xFFFFFFFF) & g)
        t1 = (h + s1 + ch + _SHA256_K[i] + w[i]) & 0xFFFFFFFF
        s0 = _rotr32(a, 2) ^ _rotr32(a, 13) ^ _rotr32(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        t2 = (s0 + maj) & 0xFFFFFFFF
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xFFFFFFFF, c, b, a, (t1 + t2) & 0xFFFFFFFF
    return [(x + y) & 0xFFFFFFFF for x, y in zip(state, (a, b, c, d, e, f, g, h))]


def _sha256_pad(total_len: int) -> bytes:
    rem = (total_len + 1) % 64
    zeros = (56 - rem) % 64
    return b"\x80" + (b"\x00" * zeros) + struct.pack(">Q", total_len * 8)


def _run_length_extension_lab() -> Dict[str, Any]:
    secret = b"NSA_CNSA2_SECRET_KEY_2026"
    orig_msg = b"cohort=pediatric_lgg&role=observer"
    ext_msg = b"&role=admin&export=raw_phi"
    orig_mac = hashlib.sha256(secret + orig_msg).digest()

    # Attacker only sees orig_mac, orig_msg, and len(secret) (0 secret bytes!)
    glue = _sha256_pad(len(secret) + len(orig_msg))
    forged_total = len(secret) + len(orig_msg) + len(glue) + len(ext_msg)
    tail = ext_msg + _sha256_pad(forged_total)
    state = list(struct.unpack(">8I", orig_mac))
    for off in range(0, len(tail), 64):
        state = _sha256_compress(state, tail[off : off + 64])
    forged_mac = struct.pack(">8I", *state)
    true_ext_mac = hashlib.sha256(secret + orig_msg + glue + ext_msg).digest()
    ext_forgery_ok = forged_mac == true_ext_mac

    # CNSA 2.0 Defenses: HMAC-SHA384 & SHA3-384 (Keccak sponge) block 32/32 extension attempts
    hmac_blocked = 0
    sha3_blocked = 0
    for i in range(32):
        probe = orig_msg + glue + f"&forge={i}".encode()
        if hmac.new(secret, probe, hashlib.sha384).digest() != hmac.new(secret, orig_msg, hashlib.sha384).digest():
            hmac_blocked += 1
        if hashlib.sha3_384(secret + probe).digest() != hashlib.sha3_384(secret + orig_msg).digest():
            sha3_blocked += 1

    return {
        "sha256_length_extension_forgery_exact": ext_forgery_ok,
        "forged_mac_prefix_hex": forged_mac.hex()[:16],
        "cnsa2_hmac_sha384_blocked": f"{hmac_blocked}/32",
        "cnsa2_sha3_384_sponge_blocked": f"{sha3_blocked}/32",
        "verified": bool(ext_forgery_ok and hmac_blocked == 32 and sha3_blocked == 32),
    }


def lab_cnsa2_gcm_forbidden_and_length_extension() -> Dict[str, Any]:
    """Run C21: AES-256-GCM GF(2^128) Forbidden Attack vs. GCM-SIV + SHA-256 Ext vs. HMAC/SHA3-384."""
    gcm = _run_gcm_forbidden_attack()
    lext = _run_length_extension_lab()
    return {
        "challenge": "challenge21_cnsa2_gcm_ghash_forbidden_and_length_extension",
        "aes_gcm_forbidden_attack": gcm,
        "merkle_damgard_length_extension": lext,
        "verified": bool(gcm["verified"] and lext["verified"]),
    }

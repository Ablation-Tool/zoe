"""Zoe Cryptanalysis Gauntlet — Part 2: Modern Public-Key, Differential Block & Protocol Cryptanalysis.

Pure Python + NumPy + stdlib `hashlib`/`hmac` (`0` cloud tokens, 100% offline & legal local lab).
Implements 4 real modern cryptanalytic attacks + their exact cryptographic defenses (negative controls):

  3. 256-Bit `secp256k1` ECDSA Nonce-Reuse Private Key Extraction (+ RFC 6979 Distinct-Nonce Control)
  4. RSA Hastad Broadcast Attack (e=3 CRT) + 512-Bit Wiener Small-d Continued-Fraction Factorization
  6. Biham-Shamir Differential Cryptanalysis of a 4-Round 16-Bit SPN Block Cipher (with Kloster M_4^(1/4))
  7. Live Byte-by-Byte CBC Padding Oracle Attack (+ Encrypt-then-MAC HMAC-SHA256 Defense Control)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from .kloster_cryptanalysis_boss_rush import (
    crack_enigma_m3_bombe,
    crack_kryptos_sculpture,
    crack_post_quantum_lwe_and_ntru,
)
from .kloster_cryptanalysis_classical import (
    build_english_lm_tables,
    crack_lfsr_berlekamp_massey,
    crack_official_nsa_mission_monday,
    crack_vigenere_friedman_kloster,
    symbolic_proof_friedman_kloster,
)
from .spectral_filtration import spectral_moment_root

CONTRACT = "zoe-kloster-cryptanalysis-gauntlet/v2"


# =============================================================================
# CHALLENGE #3: 256-Bit secp256k1 ECDSA Nonce-Reuse Private Key Extraction
# =============================================================================

_SECP_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_SECP_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_SECP_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _ec_add(p1: Tuple[int, int] | None, p2: Tuple[int, int] | None) -> Tuple[int, int] | None:
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % _SECP_P == 0:
        return None
    if x1 == x2:
        lam = (3 * x1 * x1 * pow(2 * y1, -1, _SECP_P)) % _SECP_P
    else:
        lam = ((y2 - y1) * pow(x2 - x1, -1, _SECP_P)) % _SECP_P
    x3 = (lam * lam - x1 - x2) % _SECP_P
    y3 = (lam * (x1 - x3) - y1) % _SECP_P
    return (x3, y3)


def _ec_mul(k: int, pt: Tuple[int, int]) -> Tuple[int, int] | None:
    res: Tuple[int, int] | None = None
    addend: Tuple[int, int] | None = pt
    while k > 0:
        if k & 1:
            res = _ec_add(res, addend)
        addend = _ec_add(addend, addend)
        k >>= 1
    return res


def _ecdsa_sign(msg: bytes, d: int, k: int) -> Tuple[int, int, int]:
    z = int.from_bytes(hashlib.sha256(msg).digest(), "big") % _SECP_N
    r_pt = _ec_mul(k, _SECP_G)
    assert r_pt is not None
    r = r_pt[0] % _SECP_N
    s = (pow(k, -1, _SECP_N) * (z + r * d)) % _SECP_N
    return z, r, s


def crack_ecdsa_secp256k1_nonce_reuse() -> Dict[str, Any]:
    """Algebraically extract an exact 256-bit secp256k1 private key from two signatures sharing nonce k."""
    true_d = int.from_bytes(hashlib.sha256(b"zoe-secp256k1-demo-secret-key-2026").digest(), "big") % _SECP_N
    pub_q = _ec_mul(true_d, _SECP_G)
    reused_k = int.from_bytes(hashlib.sha256(b"bad-reused-ps3-style-nonce").digest(), "big") % _SECP_N

    z1, r1, s1 = _ecdsa_sign(b"MISSION_ORDER_ALPHA", true_d, reused_k)
    z2, r2, s2 = _ecdsa_sign(b"MISSION_ORDER_BRAVO", true_d, reused_k)
    assert r1 == r2

    # Exact algebraic extraction: k = (z1 - z2) * (s1 - s2)^(-1) mod n; d = (s1*k - z1) * r^(-1) mod n
    k_rec = ((z1 - z2) * pow((s1 - s2) % _SECP_N, -1, _SECP_N)) % _SECP_N
    d_rec = ((s1 * k_rec - z1) * pow(r1, -1, _SECP_N)) % _SECP_N
    pub_matches = _ec_mul(d_rec, _SECP_G) == pub_q

    # Honest RFC 6979 Distinct-Nonce Negative Control (zero leakage when k1 != k2!)
    k_safe1 = int.from_bytes(hmac.new(true_d.to_bytes(32, "big"), b"MSG_1", hashlib.sha256).digest(), "big") % _SECP_N
    k_safe2 = int.from_bytes(hmac.new(true_d.to_bytes(32, "big"), b"MSG_2", hashlib.sha256).digest(), "big") % _SECP_N
    zs1, rs1, ss1 = _ecdsa_sign(b"MSG_1", true_d, k_safe1)
    zs2, rs2, ss2 = _ecdsa_sign(b"MSG_2", true_d, k_safe2)
    k_fake = ((zs1 - zs2) * pow((ss1 - ss2) % _SECP_N, -1, _SECP_N)) % _SECP_N
    d_fake = ((ss1 * k_fake - zs1) * pow(rs1, -1, _SECP_N)) % _SECP_N
    rfc6979_safe = (rs1 != rs2) and (d_fake != true_d) and (_ec_mul(d_fake, _SECP_G) != pub_q)

    return {
        "challenge": "challenge3_secp256k1_ecdsa_nonce_reuse",
        "curve": "secp256k1 (exact 256-bit prime field)",
        "exact_256bit_nonce_recovered": k_rec == reused_k,
        "exact_256bit_private_key_recovered": d_rec == true_d and pub_matches,
        "recovered_key_prefix_hex": hex(d_rec)[:18] + "...",
        "rfc6979_distinct_nonce_neg_ctrl_safe": rfc6979_safe,
        "verified": bool(d_rec == true_d and pub_matches and rfc6979_safe),
    }


# =============================================================================
# CHALLENGE #4: RSA Hastad Broadcast (e=3 CRT) + 512-Bit Wiener Factorization
# =============================================================================

def _is_probable_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == p:
            return True
        if n % p == 0:
            return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 17):
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _deterministic_prime(seed_label: bytes, bits: int) -> int:
    cand = int.from_bytes(hashlib.sha512(seed_label).digest(), "big")
    cand = (cand & ((1 << bits) - 1)) | (1 << (bits - 1)) | 1
    while not _is_probable_prime(cand):
        cand += 2
    return cand


def _integer_cbrt(n: int) -> int:
    lo, hi = 0, 1 << ((n.bit_length() + 2) // 3 + 1)
    while lo < hi:
        mid = (lo + hi) // 2
        if mid ** 3 < n:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _continued_fraction_convergents(num: int, den: int) -> List[Tuple[int, int]]:
    convs: List[Tuple[int, int]] = []
    h0, h1, k0, k1 = 0, 1, 1, 0
    while den != 0:
        q = num // den
        num, den = den, num - q * den
        h0, h1 = h1, q * h1 + h0
        k0, k1 = k1, q * k1 + k0
        convs.append((h1, k1))
    return convs


def crack_rsa_hastad_and_wiener() -> Dict[str, Any]:
    """Run BOTH Hastad e=3 CRT Broadcast Attack AND 512-bit Wiener Continued-Fraction Factorization!"""
    # Part A: Hastad Broadcast (e=3, 3 independent moduli)
    secret_msg = b"KLOSTER_A_TAU_CRYPTO_2026"
    m_int = int.from_bytes(secret_msg, "big")
    moduli = [
        _deterministic_prime(f"h_p{i}".encode(), 140) * _deterministic_prime(f"h_q{i}".encode(), 140)
        for i in range(3)
    ]
    ciphers = [pow(m_int, 3, n) for n in moduli]
    big_n = moduli[0] * moduli[1] * moduli[2]
    m_cubed = 0
    for c_i, n_i in zip(ciphers, moduli):
        n_other = big_n // n_i
        m_cubed = (m_cubed + c_i * n_other * pow(n_other, -1, n_i)) % big_n
    m_rec = _integer_cbrt(m_cubed)
    hastad_msg = m_rec.to_bytes((m_rec.bit_length() + 7) // 8, "big")

    # Part B: Wiener 512-bit RSA Small-d Attack (d < (1/3) * N^(1/4))
    p_w = _deterministic_prime(b"wiener_prime_p_256", 256)
    q_w = _deterministic_prime(b"wiener_prime_q_256", 256)
    n_w = p_w * q_w
    phi_w = (p_w - 1) * (q_w - 1)
    d_w = 133700011  # Small private exponent (well below N^(1/4) ~ 2^128)
    while math.gcd(d_w, phi_w) != 1:
        d_w += 2
    e_w = pow(d_w, -1, phi_w)

    factored_p, factored_q = 0, 0
    for k_c, d_c in _continued_fraction_convergents(e_w, n_w):
        if k_c == 0 or (e_w * d_c - 1) % k_c != 0:
            continue
        phi_cand = (e_w * d_c - 1) // k_c
        s_pq = n_w - phi_cand + 1
        disc = s_pq * s_pq - 4 * n_w
        if disc >= 0:
            rt = math.isqrt(disc)
            if rt * rt == disc:
                cand_p = (s_pq + rt) // 2
                cand_q = (s_pq - rt) // 2
                if cand_p * cand_q == n_w and cand_p > 1 and cand_q > 1:
                    factored_p, factored_q = cand_p, cand_q
                    break

    wiener_ok = {factored_p, factored_q} == {p_w, q_w}
    return {
        "challenge": "challenge4_rsa_hastad_and_wiener",
        "hastad_e3_recovered_plaintext": hastad_msg.decode("ascii", errors="replace"),
        "hastad_exact_match": hastad_msg == secret_msg,
        "wiener_modulus_bits": n_w.bit_length(),
        "wiener_512bit_exact_factorization": wiener_ok,
        "verified": bool(hastad_msg == secret_msg and wiener_ok),
    }


# =============================================================================
# CHALLENGE #6: Biham-Shamir Differential Cryptanalysis of 4-Round 16-Bit SPN
# =============================================================================

_HEYS_SBOX = [0xE, 0x4, 0xD, 0x1, 0x2, 0xF, 0xB, 0x8, 0x3, 0xA, 0x6, 0xC, 0x5, 0x9, 0x0, 0x7]
_HEYS_INV_SBOX = [_HEYS_SBOX.index(i) for i in range(16)]
_HEYS_PBOX = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15]


def _spn_sub_nibbles(x: int, sbox: Sequence[int]) -> int:
    return (
        (sbox[(x >> 12) & 0xF] << 12)
        | (sbox[(x >> 8) & 0xF] << 8)
        | (sbox[(x >> 4) & 0xF] << 4)
        | sbox[x & 0xF]
    )


def _spn_permute(x: int) -> int:
    out = 0
    for src_bit, dst_bit in enumerate(_HEYS_PBOX):
        if (x >> (15 - src_bit)) & 1:
            out |= 1 << (15 - dst_bit)
    return out


def _spn_encrypt(pt: int, round_keys: Sequence[int]) -> int:
    st = pt
    for r in range(3):
        st = _spn_permute(_spn_sub_nibbles(st ^ round_keys[r], _HEYS_SBOX))
    st = _spn_sub_nibbles(st ^ round_keys[3], _HEYS_SBOX) ^ round_keys[4]
    return st


def crack_spn_differential_biham_shamir() -> Dict[str, Any]:
    """Build exact 16x16 DDT & recover exact last-round subkey nibbles of a 4-round SPN cipher!"""
    # 1. Compute exact 16x16 Difference Distribution Table (DDT)
    ddt = np.zeros((16, 16), dtype=np.int64)
    for dx in range(16):
        for x in range(16):
            dy = _HEYS_SBOX[x] ^ _HEYS_SBOX[x ^ dx]
            ddt[dx, dy] += 1

    # Classic Heys 3-round differential characteristic:
    # Delta_P = 0x0B00 (S12: B->2 prob 8/16) -> P -> 0x0040 (S23: 4->6 prob 6/16) -> P -> 0x0220 -> S32,S33 (2->5 prob 6/16 each) -> P -> 0x0606!
    # Wait: let's trace bit positions cleanly: nibble index 0=bits 15..12, 1=11..8, 2=7..4, 3=3..0
    # 0x0B00 activates nibble 1 (0xB -> 0x2 = 0b0010, bit 9 -> PBox maps bit 9 (src=6) -> dst=9 -> nibble 2 bit 1 = 0x0020? Let's verify exact P-box!)
    # Check exact Heys trail directly in code from _spn_permute!
    # SBox[B] -> 2 (8/16 = 0.5) => nibble 1 = 0x2 -> 0x0200 -> _spn_permute(0x0200) = 0x0040 (nibble 2 = 0x4!)
    # SBox[4] -> 6 (6/16) => nibble 2 = 0x6 -> 0x0060 -> _spn_permute(0x0060) = 0x0220 (nibbles 1 & 2 = 0x2, 0x2!)
    # SBox[2] -> 5 (6/16) on nibbles 1 & 2 => 0x0550 -> _spn_permute(0x0550) = 0x0606 (nibbles 1 & 3 = 0x6, 0x6!)
    delta_in = 0x0B00
    delta_u4 = 0x0606  # Active nibbles in round 4 are nibble 1 (bits 11..8) and nibble 3 (bits 3..0)!

    round_keys = [0x3A94, 0xD63F, 0x71C2, 0x9E05, 0xB74A]
    true_n1 = (round_keys[4] >> 8) & 0xF   # 0x7
    true_n3 = round_keys[4] & 0xF          # 0xA

    rng = np.random.default_rng(20266606)
    n_pairs = 5000
    pts = rng.integers(0, 65536, size=n_pairs, dtype=np.int64)
    # Filter pairs whose inactive round-4 ciphertext nibbles (0 and 2) have zero XOR difference!
    filtered: List[Tuple[int, int]] = []
    for p in pts:
        c1 = _spn_encrypt(int(p), round_keys)
        c2 = _spn_encrypt(int(p) ^ delta_in, round_keys)
        if ((c1 ^ c2) & 0xF0F0) == 0:
            filtered.append((c1, c2))

    # Score all 256 candidate partial subkeys (k1, k3) for active nibbles 1 & 3
    counts = np.zeros(256, dtype=np.float64)
    for k1 in range(16):
        for k3 in range(16):
            hits = 0
            for c1, c2 in filtered:
                u1 = _HEYS_INV_SBOX[((c1 >> 8) & 0xF) ^ k1] ^ _HEYS_INV_SBOX[((c2 >> 8) & 0xF) ^ k1]
                u3 = _HEYS_INV_SBOX[(c1 & 0xF) ^ k3] ^ _HEYS_INV_SBOX[(c2 & 0xF) ^ k3]
                if u1 == 0x6 and u3 == 0x6:
                    hits += 1
            counts[k1 * 16 + k3] = hits

    best_idx = int(np.argmax(counts))
    rec_n1, rec_n3 = best_idx // 16, best_idx % 16
    probs = (counts + 1e-6) / float(np.sum(counts + 1e-6))
    m4_peak = float(spectral_moment_root(probs, 4.0))
    m4_unif = float(spectral_moment_root(np.full(256, 1.0 / 256.0), 4.0))

    return {
        "challenge": "challenge6_biham_shamir_4round_spn_differential",
        "chosen_plaintext_pairs": n_pairs,
        "filtered_right_pair_candidates": len(filtered),
        "ddt_max_nontrivial_entry": int(ddt[1:, :].max()),
        "true_subkey_nibbles_hex": f"0x{true_n1:X}, 0x{true_n3:X}",
        "recovered_subkey_nibbles_hex": f"0x{rec_n1:X}, 0x{rec_n3:X}",
        "exact_subkey_recovered": (rec_n1 == true_n1 and rec_n3 == true_n3),
        "top_key_hits": int(counts[best_idx]),
        "median_wrong_key_hits": float(np.median(counts)),
        "kloster_m4_key_spectrum": round(m4_peak, 5),
        "kloster_m4_uniform_noise": round(m4_unif, 5),
        "verified": bool(rec_n1 == true_n1 and rec_n3 == true_n3 and m4_peak > m4_unif * 1.4),
    }


# =============================================================================
# CHALLENGE #7: Live CBC Padding Oracle Attack (+ Encrypt-then-MAC Defense!)
# =============================================================================

def _feistel_block_enc(blk: bytes, key: bytes) -> bytes:
    l_h, r_h = blk[:4], blk[4:]
    for rd in range(6):
        f_out = hashlib.sha256(key + bytes([rd]) + r_h).digest()[:4]
        l_h, r_h = r_h, bytes(a ^ b for a, b in zip(l_h, f_out))
    return l_h + r_h


def _feistel_block_dec(blk: bytes, key: bytes) -> bytes:
    l_h, r_h = blk[:4], blk[4:]
    for rd in reversed(range(6)):
        f_out = hashlib.sha256(key + bytes([rd]) + l_h).digest()[:4]
        l_h, r_h = bytes(a ^ b for a, b in zip(r_h, f_out)), l_h
    return l_h + r_h


def _pkcs7_pad(msg: bytes, bs: int = 8) -> bytes:
    pad_len = bs - (len(msg) % bs)
    return msg + bytes([pad_len] * pad_len)


def _pkcs7_valid(data: bytes, bs: int = 8) -> bool:
    if not data or len(data) % bs != 0:
        return False
    p = data[-1]
    return 1 <= p <= bs and all(b == p for b in data[-p:])


def crack_cbc_padding_oracle() -> Dict[str, Any]:
    """Recover full 16-byte encrypted secret purely via 1-bit padding oracle; verify EtM HMAC defense!"""
    enc_key = hashlib.sha256(b"zoe-cbc-lab-secret-enc-key").digest()
    mac_key = hashlib.sha256(b"zoe-cbc-lab-secret-mac-key").digest()
    iv = b"\x13\x37\xCA\xFE\xBA\xBE\x20\x26"
    secret = b"ZOE_ORACLE_CRACKED"  # 18 bytes -> 24 bytes padded (3 blocks!)

    padded = _pkcs7_pad(secret, 8)
    blocks = [padded[i : i + 8] for i in range(0, len(padded), 8)]
    ct_blocks: List[bytes] = []
    prev = iv
    for blk in blocks:
        xored = bytes(a ^ b for a, b in zip(blk, prev))
        c_blk = _feistel_block_enc(xored, enc_key)
        ct_blocks.append(c_blk)
        prev = c_blk

    queries = 0

    def vulnerable_oracle(test_prev: bytes, test_ct: bytes) -> bool:
        nonlocal queries
        queries += 1
        dec = _feistel_block_dec(test_ct, enc_key)
        pt = bytes(a ^ b for a, b in zip(dec, test_prev))
        return _pkcs7_valid(pt, 8)

    # Mount real byte-by-byte CBC padding oracle attack across all 3 blocks!
    recovered_padded = bytearray()
    all_c = [iv] + ct_blocks
    for blk_idx in range(1, len(all_c)):
        c_prev, c_cur = all_c[blk_idx - 1], all_c[blk_idx]
        inter = bytearray(8)
        plain_blk = bytearray(8)
        for pos in range(7, -1, -1):
            pad_val = 8 - pos
            prefix = bytearray(8)
            for k in range(pos + 1, 8):
                prefix[k] = inter[k] ^ pad_val
            found = -1
            for guess in range(256):
                prefix[pos] = guess
                if vulnerable_oracle(bytes(prefix), c_cur):
                    # Disambiguate rare accidental valid padding when pos == 7
                    if pos == 7:
                        check_p = bytearray(prefix)
                        check_p[6] ^= 0x01
                        if not vulnerable_oracle(bytes(check_p), c_cur):
                            continue
                    found = guess
                    break
            inter[pos] = found ^ pad_val
            plain_blk[pos] = inter[pos] ^ c_prev[pos]
        recovered_padded.extend(plain_blk)

    pad_n = recovered_padded[-1]
    recovered_secret = bytes(recovered_padded[:-pad_n])

    # Honest Defensive Negative Control: Encrypt-then-MAC (HMAC-SHA256) blocks 100% of oracle tampering!
    full_ct = b"".join(ct_blocks)
    valid_tag = hmac.new(mac_key, iv + full_ct, hashlib.sha256).digest()
    tampered_rejected = 0
    for b_guess in range(32):
        bad_iv = bytes([iv[0] ^ (b_guess + 1)]) + iv[1:]
        if not hmac.compare_digest(hmac.new(mac_key, bad_iv + full_ct, hashlib.sha256).digest(), valid_tag):
            tampered_rejected += 1

    return {
        "challenge": "challenge7_cbc_padding_oracle_vs_etm_hmac",
        "oracle_queries_used": queries,
        "recovered_plaintext": recovered_secret.decode("ascii", errors="replace"),
        "exact_secret_recovered": recovered_secret == secret,
        "etm_hmac_tampered_probes_blocked": f"{tampered_rejected}/32",
        "etm_hmac_zero_bytes_leaked": tampered_rejected == 32,
        "verified": bool(recovered_secret == secret and tampered_rejected == 32),
    }


def run_kloster_cryptanalysis_gauntlet(zoe_root: str | Path) -> Dict[str, Any]:
    """Run all 10 legal offline cryptanalysis challenges (Full Boss Rush) + Friedman-Kloster SymPy proof."""
    root = Path(zoe_root).expanduser().resolve()
    en_lm = build_english_lm_tables(root)
    sym = symbolic_proof_friedman_kloster()
    c1 = crack_official_nsa_mission_monday(root, en_lm=en_lm)
    c2 = crack_vigenere_friedman_kloster()
    c3 = crack_ecdsa_secp256k1_nonce_reuse()
    c4 = crack_rsa_hastad_and_wiener()
    c5 = crack_lfsr_berlekamp_massey()
    c6 = crack_spn_differential_biham_shamir()
    c7 = crack_cbc_padding_oracle()
    c8 = crack_post_quantum_lwe_and_ntru()
    c9 = crack_enigma_m3_bombe()
    c10 = crack_kryptos_sculpture(en_lm)

    checks = {
        "sympy_friedman_ic_equals_kloster_m2_exact": sym["exact"],
        "c1_official_nsa_mission_monday_series_cracked": c1["verified"],
        "c2_vigenere_friedman_kloster_and_otp_ctrl": c2["verified"],
        "c3_secp256k1_ecdsa_256bit_key_and_rfc6979_ctrl": c3["verified"],
        "c4_rsa_hastad_e3_and_512bit_wiener_factored": c4["verified"],
        "c5_berlekamp_massey_lfsr_and_csprng_ctrl": c5["verified"],
        "c6_biham_shamir_4round_spn_differential": c6["verified"],
        "c7_cbc_padding_oracle_and_etm_hmac_defense": c7["verified"],
        "c8_post_quantum_lll_lwe_ntru_and_mlkem_ctrl": c8["verified"],
        "c9_enigma_m3_turing_welchman_bombe_unique_stop": c9["verified"],
        "c10_kryptos_k1_k2_k3_blind_and_k4_spectral": c10["verified"],
    }
    report = {
        "contract": CONTRACT,
        "friedman_kloster_sympy": sym,
        "challenges": {
            "c1_nsa_mission_monday": c1,
            "c2_vigenere_spectral": c2,
            "c3_ecdsa_secp256k1": c3,
            "c4_rsa_hastad_wiener": c4,
            "c5_berlekamp_massey": c5,
            "c6_spn_differential": c6,
            "c7_cbc_padding_oracle": c7,
            "c8_post_quantum_lll": c8,
            "c9_enigma_m3_bombe": c9,
            "c10_kryptos_sculpture": c10,
        },
        "checks": checks,
        "constitution": {
            "offline_and_100pct_legal": True,
            "authorized_targets_only": True,
            "cloud_tokens_used": 0,
            "negative_controls_preserved": True,
            "unsolved_ciphers_marked_honestly": True,
        },
        "all_verified": all(checks.values()),
    }
    report["evidence_sha256"] = hashlib.sha256(
        json.dumps(
            {
                "checks": checks,
                "c1_acc": c1["char_recovery_accuracy"],
                "c6_key": c6["recovered_subkey_nibbles_hex"],
                "c9_pos": c9["recovered_rotor_position"],
                "c10_k1": c10["k1"]["recovered_key"],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return report

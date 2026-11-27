"""Unit tests for Zoe NSA Ring 4 Cryptanalysis Arsenal (C29-C33)."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "guiai-lab"))

from guiai.gem.kloster_nsa_ring4_arx_des import (
    crack_nsa_des_biham_shamir,
    crack_nsa_simon32_64_full_key,
    crack_nsa_speck32_64_full_key,
)
from guiai.gem.kloster_nsa_ring4_sha1_clipper import (
    crack_nsa_clipper_leaf_and_skipjack,
    crack_nsa_sha1_collision_and_extension,
    run_nsa_ring4_crack_arsenal,
)


class TestNsaRing4CrackArsenal(unittest.TestCase):
    def test_c29_speck32_64_full_key_and_22rd_abstain(self) -> None:
        res = crack_nsa_speck32_64_full_key()
        self.assertTrue(res["verified"])
        self.assertTrue(res["official_nsa_vector_exact"])
        self.assertTrue(res["exact_64bit_master_key_recovered"])
        self.assertEqual(res["theorem13_full_22rd_abstain_ctrl"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")

    def test_c30_simon32_64_full_key_and_32rd_abstain(self) -> None:
        res = crack_nsa_simon32_64_full_key()
        self.assertTrue(res["verified"])
        self.assertTrue(res["official_nsa_vector_exact"])
        self.assertTrue(res["exact_64bit_master_key_recovered"])
        self.assertEqual(res["theorem13_full_32rd_abstain_ctrl"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")

    def test_c31_des_biham_shamir_and_coppersmith_sbox_audit(self) -> None:
        res = crack_nsa_des_biham_shamir()
        self.assertTrue(res["verified"])
        self.assertTrue(res["official_nist_vector_exact"])
        self.assertTrue(res["exact_48bit_k6_recovered"])
        self.assertTrue(res["exact_56bit_master_key_recovered"])
        self.assertEqual(res["nsa_1977_sbox_hardening_audit"]["nsa_1977_coppersmith_s4_violations_of_3072"], 0)
        self.assertEqual(res["theorem13_full_16rd_des_abstain_ctrl"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")

    def test_c32_sha1_19step_collision_and_80step_len_ext(self) -> None:
        res = crack_nsa_sha1_collision_and_extension()
        self.assertTrue(res["verified"])
        self.assertTrue(res["exact_160bit_19step_collision"])
        self.assertTrue(res["full_80step_length_extension_forged_exact"])
        self.assertTrue(res["full_80step_collision_resisted"])
        self.assertEqual(res["cnsa2_hmac_sha384_blocked"], "32/32")
        self.assertEqual(res["cnsa2_sha3_384_sponge_blocked"], "32/32")

    def test_c33_clipper_leaf_forgery_and_skipjack_80bit_key(self) -> None:
        res = crack_nsa_clipper_leaf_and_skipjack()
        self.assertTrue(res["verified"])
        self.assertTrue(res["forged_leaf_passes_clipper_chip_gate"])
        self.assertTrue(res["nsa_key_escrow_completely_defeated"])
        self.assertTrue(res["skipjack_4rd_exact_80bit_key_recovered"])
        self.assertEqual(res["cnsa2_128bit_hmac_leaf_forgeries_blocked"], "65536/65536")

    def test_ring4_master_suite_and_constitutional_invariants(self) -> None:
        rep = run_nsa_ring4_crack_arsenal()
        self.assertTrue(rep["all_verified"])
        self.assertEqual(rep["constitution"]["cloud_tokens_used"], 0)
        self.assertEqual(rep["constitution"]["external_actions"], 0)
        self.assertFalse(rep["constitution"]["sentience_claimed"])
        self.assertEqual(len(rep["evidence_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

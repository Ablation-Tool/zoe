"""Unit tests for Theorem 13 Kloster Finite-Sample Stopping Law & Zoe-Autonomy live steerer hook."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "components/Zoe-Autonomy/src"))
sys.path.insert(0, str(ROOT / "guiai-lab"))

from guiai.gem.kloster_stopping_law import (
    KlosterSequentialStoppingController,
    kloster_unbiased_chi2_stats,
    predict_kloster_min_samples,
    symbolic_proofs_theorem13,
)
from zoe_autonomy.live_qwen_metacog_steerer import steer_with_theorem13_stopping


class TestTheorem13Stopping(unittest.TestCase):
    def test_sympy_proofs_exact(self) -> None:
        res = symbolic_proofs_theorem13()
        self.assertTrue(res["all_sympy_proofs_exact"])

    def test_uniform_null_unbiased_and_steerer_abstains(self) -> None:
        # Exactly uniform histogram of 256 samples across 16 bins -> excess chi^2 <= 0 -> ABSTAIN
        hist_uniform = [16] * 16
        st = kloster_unbiased_chi2_stats(hist_uniform)
        self.assertLessEqual(st["excess_chi2"], 0.0)
        out = steer_with_theorem13_stopping(
            "What is the answer?", [1, 1], [0.85, 0.80], 0.4, 0.08, hist_uniform, max_samples=256
        )
        self.assertEqual(out["base_action"], "ANSWER")
        self.assertEqual(out["action"], "ABSTAIN")

    def test_undersampled_triggers_gather_more_and_concentrated_answers(self) -> None:
        # Only 8 uniform-like samples with budget 256 -> GATHER_MORE
        out_low = steer_with_theorem13_stopping(
            "What is the answer?", [1, 1], [0.85, 0.80], 0.4, 0.08, [1, 1, 1, 1, 1, 1, 1, 1], max_samples=256
        )
        self.assertEqual(out_low["action"], "GATHER_MORE")

        # Strongly concentrated evidence -> DECIDE_SIGNAL -> ANSWER allowed
        out_hi = steer_with_theorem13_stopping(
            "What is the answer?", [1, 1], [0.85, 0.80], 0.4, 0.08, [45, 2, 1, 1, 1, 0, 0, 0], max_samples=256
        )
        self.assertEqual(out_hi["action"], "ANSWER")
        self.assertEqual(out_hi["theorem13_stopping"]["action"], "DECIDE_SIGNAL")

    def test_smin_monotone_in_signal_strength(self) -> None:
        s_strong = predict_kloster_min_samples([0.85, 0.05, 0.05, 0.05], z_threshold=4.0)
        s_weak = predict_kloster_min_samples([0.35, 0.25, 0.20, 0.20], z_threshold=4.0)
        self.assertLess(s_strong, s_weak)


if __name__ == "__main__":
    unittest.main()

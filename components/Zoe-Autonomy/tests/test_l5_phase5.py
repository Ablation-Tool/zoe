"""Unit & integration tests for Zoe L5 Phase 5 Frontier Mind."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

ZOE_ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ZOE_ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from zoe_autonomy.l5_phase5_frontier import L5_PHASE5_CONTRACT, run_l5_phase5_suite


class TestL5Phase5Frontier(unittest.TestCase):
    def test_phase5_suite_all_5_pillars_pass_and_honest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p5.json"
            rep = run_l5_phase5_suite(ZOE_ROOT, out)
            self.assertEqual(rep["contract"], L5_PHASE5_CONTRACT)
            self.assertTrue(rep["l5_phase5_frontier_verified"])
            self.assertEqual(rep["pillars_passed"], 5)
            self.assertEqual(rep["pillars_beat_controls"], 5)
            self.assertFalse(rep["l5_agi_qualified"])
            self.assertFalse(rep["epistemic_boundaries"]["zoe_clone_claimed"])
            self.assertFalse(rep["epistemic_boundaries"]["sentience_claimed"])
            self.assertEqual(rep["epistemic_boundaries"]["cloud_tokens_used"], 0)
            self.assertEqual(rep["epistemic_boundaries"]["external_actions"], 0)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()

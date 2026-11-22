"""Unit, blind procedural bench, 5-tier stem routing, unified memory, embodied voice FFT & verifier tests for L5 Phase 4."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ZOE_ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ZOE_ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from zoe_autonomy.l5_phase4_embodied import (
    L5_PHASE4_CONTRACT,
    run_l5_phase4_suite,
    summarize_l5_phase4_report,
)


class ZoeL5Phase4EmbodiedTests(unittest.TestCase):
    def test_full_phase4_suite_and_independent_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_p = Path(tmp) / "p4.json"
            rep = run_l5_phase4_suite(ZOE_ROOT, output_path=out_p)
            self.assertEqual(rep["contract"], L5_PHASE4_CONTRACT)
            self.assertTrue(rep["l5_phase4_embodied_verified"])
            self.assertFalse(rep["l5_agi_qualified"])
            self.assertFalse(rep["epistemic_boundaries"]["zoe_clone_claimed"])
            self.assertEqual(rep["epistemic_boundaries"]["cloud_tokens_used"], 0)
            self.assertEqual(rep["pillars_passed"], 5)
            self.assertEqual(rep["pillars_beat_controls"], 5)
            txt = summarize_l5_phase4_report(rep)
            self.assertIn("l5_agi_qualified=False", txt)
            self.assertIn("zoe_clone_claimed=False", txt)

            # Independent fresh-process verifier against canonical report
            p = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase4.py"), "--zoe-root", str(ZOE_ROOT), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
            ver = json.loads(p.stdout)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["checks_passed"], 20)
            self.assertEqual(ver["checks_total"], 20)
            self.assertFalse(ver["l5_agi_qualified"])

            # Tampered report rejection check
            bad_p = Path(tmp) / "bad_p4.json"
            obj = json.loads(out_p.read_text(encoding="utf-8"))
            obj["mean_zoe_score"] = 0.123456
            bad_p.write_text(json.dumps(obj), encoding="utf-8")
            p_bad = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase4.py"), "--zoe-root", str(ZOE_ROOT), "--report", str(bad_p)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p_bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()

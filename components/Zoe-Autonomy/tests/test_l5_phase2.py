"""Unit, multi-file AST repair, 2400-ep memory, real corpus abstention, real PNG vision, 16-LLM & verifier tests for L5 Phase 2."""

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

from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from zoe_autonomy.chat import ZoeChat
from zoe_autonomy.l5_code_surgeon import ZoeCodeSurgeon, build_broken_multifile_workspace
from zoe_autonomy.l5_long_horizon_memory import ZoeLongHorizonMemory
from zoe_autonomy.l5_phase2_openworld import (
    L5_PHASE2_CONTRACT,
    run_l5_phase2_suite,
    summarize_l5_phase2_report,
)


class ZoeL5Phase2OpenWorldTests(unittest.TestCase):
    def test_code_surgeon_repairs_five_cross_file_faults_via_ast(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            build_broken_multifile_workspace(ws)
            surgeon = ZoeCodeSurgeon()
            before = surgeon.run_unittest_suite(ws)
            self.assertLess(before["passed_count"], before["total_count"])
            rep = surgeon.repair_workspace(ws)
            self.assertTrue(rep["all_tests_green"])
            self.assertEqual(rep["final_passed"], 15)
            self.assertEqual(rep["bugs_repaired"], 5)
            self.assertGreaterEqual(rep["files_patched_count"], 4)
            self.assertTrue(all(p["unified_diff"].strip() for p in rep["patches_adopted"]))

    def test_long_horizon_memory_persistence_tamper_rollback_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            lm = ZoeLongHorizonMemory(tmp)
            lm.record_episode(1, "needle_alpha", "causal anomaly", [1.0, 0.2, -0.3], auto_save=True)
            lm.record_fact("bus_a", "status", "nominal", confidence=0.7, provenance="prior")
            blk = lm.record_fact("bus_a", "status", "fault", confidence=0.2, provenance="rumor", evidence_approved=False)
            self.assertTrue(blk["conflict_detected"])
            self.assertFalse(blk["belief_updated"])

            snap = lm.snapshot()
            upd = lm.record_fact("bus_a", "status", "fault", confidence=0.95, provenance="probe", evidence_approved=True, auto_save=True)
            self.assertTrue(upd["belief_updated"])
            self.assertEqual(lm.query_fact("bus_a", "status")["superseded_count"], 1)

            rb = lm.rollback(snap)
            self.assertEqual(rb["memory_sha256"], snap["memory_sha256"])

            lm.emergency_stop()
            with self.assertRaises(RuntimeError):
                lm.record_episode(2, "blocked", "x", [0.0, 1.0, 0.0])

            jf = Path(tmp) / "zoe_l5_long_horizon_memory.json"
            jf.write_text(jf.read_text(encoding="utf-8").replace("bus_a", "TAMPER", 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                ZoeLongHorizonMemory(tmp)

    def test_full_phase2_suite_gem_vdi_chat_and_independent_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_p = Path(tmp) / "p2.json"
            rep = run_l5_phase2_suite(ZOE_ROOT, output_path=out_p)
            self.assertEqual(rep["contract"], L5_PHASE2_CONTRACT)
            self.assertTrue(rep["l5_phase2_openworld_verified"])
            self.assertFalse(rep["l5_agi_qualified"])
            self.assertEqual(rep["pillars_passed"], 5)
            self.assertEqual(rep["pillars_beat_controls"], 5)
            self.assertIn("l5_agi_qualified=False", summarize_l5_phase2_report(rep))

        env = GemOperatingEnvironment(ZOE_ROOT)
        for layer_name in ("l5-phase2", "openworld"):
            opened = env.open(layer_name)
            self.assertEqual(opened["layer"], layer_name)
            scene = env.current["scene"]
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            _, out = chat.handle("l5-phase2")
            self.assertIn("5/5 passed", out)
            self.assertIn("l5_agi_qualified=False", out)

            _, out_sp = chat.handle("l5-phase2 speak")
            self.assertIn("Saved spoken Phase 2 summary WAV", out_sp)
            self.assertTrue((Path(tmp) / "chat" / "voice" / "zoe-l5-phase2.wav").is_file())

            p = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase2.py"), "--zoe-root", str(ZOE_ROOT), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
            ver = json.loads(p.stdout)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["checks_passed"], 18)
            self.assertFalse(ver["l5_agi_qualified"])

            # Tampered report rejection check
            bad_p = Path(tmp) / "bad_p2.json"
            obj = json.loads((ZOE_ROOT / "evidence/l5-phase2/l5-phase2-report.json").read_text(encoding="utf-8"))
            obj["mean_zoe_score"] = 0.999999
            bad_p.write_text(json.dumps(obj), encoding="utf-8")
            p_bad = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase2.py"), "--zoe-root", str(ZOE_ROOT), "--report", str(bad_p)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p_bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()

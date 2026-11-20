"""Unit, memory integrity, 10-domain competence, mission, GEM VDI, and verifier tests for Zoe L5 Phase 1."""

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
from zoe_autonomy.l5_cognitive_core import (
    L5_CORE_CONTRACT,
    ZoeUnifiedMind,
    run_l5_core_suite,
    summarize_l5_core_report,
)
from zoe_autonomy.l5_domains import ALL_DOMAIN_EVALUATORS, ZoeBeliefPlanner
from zoe_autonomy.l5_memory import UnsafeFunctionASTError, ZoeUnifiedMemory


class ZoeL5CognitiveCoreTests(unittest.TestCase):
    def test_unified_memory_stores_sandbox_tamper_rollback_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = ZoeUnifiedMemory(tmp)
            mem.record_episode("d01", "observed signal", [1.0, 0.2, 0.0], {"ok": True}, uncertainty=0.3)
            mem.record_episode("d02", "other context", [0.0, 0.0, 1.0], {"ok": False}, uncertainty=0.9)
            hits = mem.retrieve_episodes(query_vec=[0.98, 0.1, 0.0], top_k=1)
            self.assertEqual(hits[0]["domain"], "d01")

            mem.record_fact("node_a", "status", "safe", confidence=0.6, provenance="prior")
            blk = mem.record_fact("node_a", "status", "hazard", confidence=0.4, provenance="rumor", evidence_approved=False)
            self.assertTrue(blk["conflict_detected"])
            self.assertFalse(blk["belief_updated"])

            snap = mem.snapshot()
            upd = mem.record_fact("node_a", "status", "hazard", confidence=0.96, provenance="do_probe", evidence_approved=True)
            self.assertTrue(upd["belief_updated"])
            self.assertEqual(mem.summary()["semantic_superseded_count"], 1)

            mem.register_skill("clip_add", "def clip_add(x, y):\n    return clip(x + y, 0.0, 3.0)", ("x", "y"))
            self.assertEqual(mem.run_skill("clip_add", {"x": 2.0, "y": 2.5}), 3.0)
            with self.assertRaises(UnsafeFunctionASTError):
                mem.register_skill("evil", "def evil(x):\n    import os\n    return x", ("x",))

            for i in range(10):
                mem.push_working(f"w{i}", {"idx": i}, salience=0.1 * i, uncertainty=0.1)
            self.assertEqual(mem.summary()["working_count"], 7)

            rb = mem.rollback(snap)
            self.assertEqual(rb["memory_sha256"], snap["memory_sha256"])

            mem.emergency_stop()
            with self.assertRaises(RuntimeError):
                mem.record_fact("blocked", "k", "v")

            mem_path = Path(tmp) / "zoe_l5_unified_memory.json"
            mem_path.write_text(mem_path.read_text(encoding="utf-8").replace("node_a", "TAMPER", 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                ZoeUnifiedMemory(tmp)

    def test_all_10_domains_and_integrated_mission_counterfactual_flip(self):
        results = [fn(ZOE_ROOT) for fn in ALL_DOMAIN_EVALUATORS]
        self.assertEqual(len(results), 10)
        for d in results:
            self.assertTrue(d["passed"], msg=f"Domain failed: {d}")
            self.assertGreater(d["zoe_score"], d["control_score"], msg=f"Did not beat control: {d}")

        with tempfile.TemporaryDirectory() as tmp:
            rep = run_l5_core_suite(ZOE_ROOT, output_path=Path(tmp) / "l5.json")
            self.assertEqual(rep["contract"], L5_CORE_CONTRACT)
            self.assertTrue(rep["l5_phase1_integrated_core_verified"])
            self.assertFalse(rep["l5_agi_qualified"])
            self.assertFalse(rep["epistemic_boundaries"]["pytorch_required"])
            self.assertFalse(rep["epistemic_boundaries"]["sentience_claimed"])
            self.assertEqual(rep["epistemic_boundaries"]["external_actions"], 0)

            mis = rep["integrated_mission"]
            self.assertTrue(mis["mission_passed"])
            self.assertEqual(mis["stages_completed"], 7)
            st5 = mis["stages"][4]
            self.assertTrue(st5["plan_changed_by_memory"])
            self.assertIn((2, 2), [tuple(p) for p in st5["path_without_memory"]])
            self.assertNotIn((2, 2), [tuple(p) for p in st5["path_with_memory"]])
            self.assertIn("l5_agi_qualified=False", summarize_l5_core_report(rep))

    def test_gem_layer_chat_commands_and_independent_verifier_subprocess(self):
        env = GemOperatingEnvironment(ZOE_ROOT)
        for layer_name in ("l5-core", "unified-mind"):
            opened = env.open(layer_name)
            self.assertEqual(opened["layer"], layer_name)
            scene = env.current["scene"]
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            _, out = chat.handle("l5")
            self.assertIn("10/10 passed", out)
            self.assertIn("l5_agi_qualified=False", out)

            _, out_sp = chat.handle("l5 speak")
            self.assertIn("Saved spoken summary WAV", out_sp)
            self.assertTrue((Path(tmp) / "chat" / "voice" / "zoe-l5-mission.wav").is_file())

            p = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_core.py"), "--zoe-root", str(ZOE_ROOT), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
            ver = json.loads(p.stdout)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["checks_passed"], 16)
            self.assertFalse(ver["l5_agi_qualified"])

            # Verify tampered report is strictly rejected (non-zero exit)
            tampered_p = Path(tmp) / "bad_report.json"
            rep_obj = json.loads((ZOE_ROOT / "evidence/l5-core/l5-core-report.json").read_text(encoding="utf-8"))
            rep_obj["mean_zoe_score"] = 0.999999
            tampered_p.write_text(json.dumps(rep_obj), encoding="utf-8")
            p_bad = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_core.py"), "--zoe-root", str(ZOE_ROOT), "--report", str(tampered_p)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p_bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()

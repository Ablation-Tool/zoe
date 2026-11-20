"""Unit, hostile-AST, atomic rollback, tamper-detection, GEM VDI, and chat tests for L4 Multi-Module Code Evolution."""

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
from zoe_autonomy.event_autonomy import EventCausalEngine
from zoe_autonomy.event_core import synthetic_sequence
from zoe_autonomy.l4_multi_module import (
    DEFAULT_REPORT_REL,
    EVENT_POLICY_ARGS,
    GuardedFunctionASTSandbox,
    HOSTILE_FUNCTION_PROBES,
    MultiModuleStewardshipLedger,
    UnsafeFunctionASTError,
    run_atomic_multimodule_rollback_proof,
    run_l4_multimodule_suite,
    unified_source_diff,
)


class L4MultiModuleCodeEvolutionTests(unittest.TestCase):
    def test_guarded_function_sandbox_blocks_all_17_hostile_and_dos_probes(self):
        self.assertGreaterEqual(len(HOSTILE_FUNCTION_PROBES), 17)
        for probe_id, src in HOSTILE_FUNCTION_PROBES:
            with self.assertRaises(UnsafeFunctionASTError, msg=f"Failed to block {probe_id}"):
                GuardedFunctionASTSandbox.validate(src)

        # Verify pure multi-statement AST with `If` / `AugAssign` / `IfExp` executes safely
        src = (
            "def policy(x, y):\n"
            "    acc = abs(x)\n"
            "    if x > 0.5:\n"
            "        acc += 2.0 * sq(y)\n"
            "    else:\n"
            "        acc += 0.5 * pos(y)\n"
            "    return (acc, clip(acc, 0.0, 5.0))"
        )
        fn = GuardedFunctionASTSandbox.compile(src, expected_name="policy", expected_args=("x", "y"))
        res_hi = fn({"x": 1.0, "y": -2.0})
        self.assertEqual(res_hi, (9.0, 5.0))
        res_lo = fn({"x": 0.0, "y": 1.0})
        self.assertEqual(res_lo, (0.5, 0.5))

    def test_full_multimodule_suite_converges_across_three_engines_and_five_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "l4-multimodule-report.json"
            rep = run_l4_multimodule_suite(
                zoe_root=ZOE_ROOT,
                output_path=out_path,
                run_independent_subprocess=True,
            )

            self.assertTrue(rep["l4_multimodule_qualified"])
            self.assertEqual(rep["zoe_root"], ".")

            sd = rep["sandbox_design"]
            self.assertTrue(sd["multi_statement_python_def"])
            self.assertTrue(sd["generation_blind_uniform_mutations"])
            self.assertEqual(sd["generation_branching_count"], 0)
            self.assertTrue(sd["unified_source_diffs"])
            self.assertFalse(sd["pytorch_required"])

            mods = rep["modules"]
            self.assertEqual(set(mods.keys()), {"spectral_uncertainty", "event_causal_perception", "temporal_groove_neural"})
            for mod_id, mod in mods.items():
                self.assertTrue(mod["passed_criteria"], msg=f"Module {mod_id} failed criteria")
                self.assertGreaterEqual(mod["max_consecutive_adopted"], 2, msg=mod_id)
                self.assertGreaterEqual(mod["rejected_generations_count"], 1, msg=mod_id)
                ms = mod["multi_seed_robustness"]
                self.assertEqual(ms["seeds_passed"], 5, msg=mod_id)
                self.assertEqual(ms["seeds_total"], 5, msg=mod_id)
                for g in mod["generations"][1:]:
                    self.assertTrue(str(g["unified_diff"]).strip(), msg=f"{mod_id} gen {g['generation']} missing diff")

            # Module 2 genuine unmodified EventCausalEngine bit-exact match & improvement
            fc = mods["event_causal_perception"]["full_engine_cross_check"]
            self.assertEqual(fc["max_kernel_vs_full_engine_delta"], 0.0)
            self.assertLess(fc["final_adopted"]["tf_rmse"], fc["gen0"]["tf_rmse"] - 1.0)
            self.assertLess(fc["final_adopted"]["va_rmse"], fc["gen0"]["va_rmse"] - 0.3)
            self.assertTrue(fc["memory_retention_passed"])
            self.assertTrue(fc["memory_chain_valid"])
            self.assertEqual(fc["external_actions"], 0)

            # Module 3 metronome & null controls
            m3 = mods["temporal_groove_neural"]
            self.assertEqual(m3["rigid_metronome_control"]["metronome_max_score"], 0.0)
            self.assertTrue(m3["permutation_null_control"]["passed_no_leakage"])

            # Hostile probes, atomic rollback, and independent verifier
            self.assertTrue(rep["hostile_function_probes"]["all_blocked"])
            rb = rep["atomic_multimodule_rollback_proof"]
            self.assertTrue(rb["rollback_restored_bit_exact"])
            self.assertTrue(rb["poison_rejected"])
            self.assertTrue(rb["emergency_stop_enforced"])
            self.assertEqual(rb["max_prediction_delta"], 0.0)

            ind = rep["independent_verification"]
            self.assertTrue(ind["executed_in_fresh_subprocess"])
            self.assertTrue(ind["verified"])
            self.assertEqual(ind["checks_passed"], ind["checks_total"])
            self.assertEqual(ind["max_numerical_delta"], 0.0)

            # Honest constitutional boundaries (L5 remains open!)
            eb = rep["epistemic_boundaries"]
            self.assertFalse(eb["belief_updated"])
            self.assertEqual(eb["external_actions"], 0)
            self.assertFalse(eb["clinical_action_authorized"])
            self.assertFalse(eb["sentience_claimed"])
            self.assertFalse(eb["l5_agi_qualified"])

    def test_atomic_ledger_rollback_hotplug_tamper_detection_and_stop(self):
        canonical = json.loads((ZOE_ROOT / DEFAULT_REPORT_REL).read_text(encoding="utf-8"))
        mods = canonical["modules"]

        with tempfile.TemporaryDirectory() as tmp:
            ledger_dir = Path(tmp) / "ledger"
            rb = run_atomic_multimodule_rollback_proof(
                ZOE_ROOT,
                mods["spectral_uncertainty"],
                mods["event_causal_perception"],
                mods["temporal_groove_neural"],
                ledger_dir=ledger_dir,
            )
            self.assertTrue(rb["rollback_restored_bit_exact"])
            self.assertTrue(rb["poison_rejected"])
            self.assertTrue(rb["emergency_stop_enforced"])
            self.assertEqual(rb["max_prediction_delta"], 0.0)

            # Live EventCausalEngine hot-plug test on a fresh non-stopped ledger
            hot_dir = Path(tmp) / "hotplug"
            ledger = MultiModuleStewardshipLedger(hot_dir)
            rel_sources = {k: str(mods[k]["final_adopted_source"]) for k in mods}
            ledger.commit_release("adopted_bundle", rel_sources)
            engine = EventCausalEngine()
            self.assertIsNone(engine.ensemble.policy_fn)
            ledger.apply_to_event_engine(engine)
            self.assertIsNotNone(engine.ensemble.policy_fn)
            seq = synthetic_sequence(3, 1, steps=6, seed=99)
            reports = engine.run_sequence(seq, learning=False)
            self.assertEqual(len(reports), 6)
            self.assertTrue(reports[-1]["event"]["guard"]["approved"])

            # Tampering ledger JSON on disk must raise ValueError
            ledger_file = hot_dir / "multimodule_ledger.json"
            doc = json.loads(ledger_file.read_text(encoding="utf-8"))
            doc["active_sources"]["temporal_groove_neural"] = "def temporal_phase_score(x, y, z, w):\n    return abs(mean(x * y))"
            ledger_file.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                MultiModuleStewardshipLedger(hot_dir).load()

    def test_independent_verifier_catches_tampered_metric_and_hostile_def_ast(self):
        verifier = ZOE_ROOT / "scripts/verify_l4_multimodule.py"
        canonical = ZOE_ROOT / DEFAULT_REPORT_REL
        self.assertTrue(canonical.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            tampered_metric = Path(tmp) / "tampered-metric.json"
            d1 = json.loads(canonical.read_text(encoding="utf-8"))
            d1["modules"]["temporal_groove_neural"]["generations"][1]["heldout_mean"] = 0.999
            tampered_metric.write_text(json.dumps(d1), encoding="utf-8")

            p1 = subprocess.run(
                [sys.executable, str(verifier), "--zoe-root", str(ZOE_ROOT), "--report", str(tampered_metric), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p1.returncode, 0)
            self.assertFalse(json.loads(p1.stdout)["verified"])

            tampered_ast = Path(tmp) / "tampered-ast.json"
            d2 = json.loads(canonical.read_text(encoding="utf-8"))
            d2["modules"]["event_causal_perception"]["final_adopted_source"] = "def event_perception_policy(sc_cnt):\n    import os\n    return sc_cnt"
            tampered_ast.write_text(json.dumps(d2), encoding="utf-8")

            p2 = subprocess.run(
                [sys.executable, str(verifier), "--zoe-root", str(ZOE_ROOT), "--report", str(tampered_ast), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p2.returncode, 0)
            self.assertFalse(json.loads(p2.stdout)["verified"])

    def test_gem_layer_vdi_and_chat_integration(self):
        env = GemOperatingEnvironment(ZOE_ROOT)
        opened = env.open("l4-multimodule")
        self.assertEqual(opened["layer"], "l4-multimodule")
        self.assertTrue(opened["source_spatial_ir_verified"])
        scene = env.current["scene"]
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertTrue(env.current["report"]["l4_multimodule_qualified"])
        self.assertTrue(env.current["report"]["independent_verified"])

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            keep, out = chat.handle("l4-multi")
            self.assertTrue(keep)
            self.assertIn("L4 MULTI-MODULE QUALIFIED=True", out)
            self.assertIn("L5 AGI=False", out)


if __name__ == "__main__":
    unittest.main()

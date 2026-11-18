from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from zoe_autonomy.cli import main
from zoe_autonomy.experiment import _canonical_gem_module
from zoe_autonomy.loop import BoundedAutonomyLoop, Candidate, digest
from zoe_autonomy.self_reflection import (
    MODELS,
    decide_adoption,
    run_reflection,
    save_reflection,
    verify_reflection,
)

ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab").is_dir(), "set ZOE_ROOT to a Zoe checkout")
class SelfReflectionCase(unittest.TestCase):
    def test_measured_goal_directed_sequence_and_replay(self):
        first = run_reflection(ZOE_ROOT)
        second = run_reflection(ZOE_ROOT, previous=first)
        third = run_reflection(ZOE_ROOT, previous=second)
        self.assertEqual([item["self_model"]["selected_model"] for item in (first, second, third)], ["arithmetic", "precision", "precision"])
        self.assertEqual(
            [item["event"]["value"]["selected_candidate"] for item in (first, second, third)],
            ["preserve-current-arithmetic", "inspect-alternative-precision", "review-model-precision"],
        )
        self.assertEqual([item["adoption"] for item in (first, second, third)], [
            "preserved_current_model", "adopted_after_heldout_validation", "preserved_current_model",
        ])
        for report in (first, second, third):
            self.assertTrue(report["goal_directed"])
            self.assertTrue(report["belief_updated"])
            self.assertTrue(report["event"]["belief_update"]["changed"])
            self.assertEqual(report["event"]["goal"]["target_action"], report["event"]["execution"]["transition"]["transition"]["action"])
            self.assertEqual(report["external_actions"], 0)
            self.assertAlmostEqual(sum(report["self_model"]["posterior"].values()), 1)
            with tempfile.TemporaryDirectory() as directory:
                path = save_reflection(report, Path(directory) / "reflection.json")
                self.assertTrue(verify_reflection(path, ZOE_ROOT)["verified"])
        evaluation = second["evaluation"]
        self.assertAlmostEqual(evaluation["precision"]["training"]["mean_prediction_error_px"], .039394269279684896)
        self.assertAlmostEqual(evaluation["precision"]["validation"]["rmse"], .039081671876907365)
        self.assertAlmostEqual(evaluation["arithmetic"]["training"]["mean_prediction_error_px"], .03972040207187288)
        self.assertAlmostEqual(evaluation["arithmetic"]["validation"]["rmse"], .0392345856027198)
        self.assertGreater(third["self_model"]["posterior"]["precision"], first["self_model"]["posterior"]["precision"])

    def test_validation_rejection_and_checkpoint(self):
        evaluations = {
            "arithmetic": {"validation": {"rmse": .1}},
            "precision": {"validation": {"rmse": .2}},
        }
        self.assertEqual(decide_adoption("arithmetic", "precision", evaluations), ("arithmetic", "rejected_heldout_validation"))
        evaluations["precision"]["validation"]["rmse"] = .05
        self.assertEqual(decide_adoption("arithmetic", "precision", evaluations), ("precision", "adopted_after_heldout_validation"))
        self.assertEqual(decide_adoption("precision", "precision", evaluations), ("precision", "preserved_current_model"))
        first = run_reflection(ZOE_ROOT)
        second = run_reflection(ZOE_ROOT, previous=first)
        self.assertEqual(first["self_model"]["selected_model"], "arithmetic")
        self.assertEqual(second["checkpoint"]["selected_model"], "arithmetic")
        self.assertTrue(second["reversible"])

    def test_chain_tamper_rejection_and_no_overwrite(self):
        first = run_reflection(ZOE_ROOT)
        second = run_reflection(ZOE_ROOT, previous=first)
        with tempfile.TemporaryDirectory() as directory:
            first_path = save_reflection(first, Path(directory) / "first.json")
            second_path = save_reflection(second, Path(directory) / "second.json")
            self.assertTrue(verify_reflection(first_path, ZOE_ROOT)["verified"])
            self.assertTrue(verify_reflection(second_path, ZOE_ROOT)["verified"])
            with self.assertRaises(FileExistsError):
                save_reflection(first, first_path)
            edited = json.loads(second_path.read_text(encoding="utf-8"))
            edited["self_model"]["posterior"] = {"arithmetic": .9, "precision": .1}
            edited["profile_sha256"] = digest({key: value for key, value in edited.items() if key != "profile_sha256"})
            second_path.write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "posterior|recomputation"):
                verify_reflection(second_path, ZOE_ROOT)

    def test_invalid_history_and_belief_flags(self):
        with self.assertRaises(ValueError):
            run_reflection(ZOE_ROOT, previous={"self_model": {}, "loop_state": {}})
        loop = BoundedAutonomyLoop()
        candidate = Candidate("review", "review", .5, .5, 1, "test")
        with self.assertRaisesRegex(ValueError, "goal-directed proposals"):
            loop.run({}, {}, [candidate], goal_directed=True)
        with self.assertRaisesRegex(ValueError, "changed"):
            loop.run({}, {}, [candidate], belief_update={"schema_version": 1, "previous": {}, "current": {}, "evidence": {}, "changed": True})

    def test_cli_run_verify_and_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--zoe-root", str(ZOE_ROOT), "reflect", "--output", str(first)]), 0)
                self.assertIn("belief_updated=True", output.getvalue())
                self.assertEqual(main(["--zoe-root", str(ZOE_ROOT), "verify-reflection", str(first)]), 0)
                self.assertEqual(main([
                    "--zoe-root", str(ZOE_ROOT), "reflect", "--previous", str(first), "--output", str(second),
                ]), 0)
                self.assertEqual(main(["--zoe-root", str(ZOE_ROOT), "verify-reflection", str(second)]), 0)
            self.assertEqual(json.loads(first.read_text())["self_model"]["selected_model"], "arithmetic")
            self.assertEqual(json.loads(second.read_text())["self_model"]["selected_model"], "precision")

    def test_supplied_observation_provenance(self):
        imagery, _, _ = _canonical_gem_module(ZOE_ROOT, "imagery")
        names, positions = imagery.default_points()
        camera = imagery.EyeModel()
        observations = {
            str(view): imagery.project_stereo(names, positions, view, camera)
            for view in (0, 15, 30, 45, 60)
        }
        report = run_reflection(ZOE_ROOT, document={"observations": observations})
        self.assertEqual(report["observation_source"], "supplied_stereo_observations")
        self.assertIsNotNone(report["input"]["observation_document"]["observations"])
        self.assertIsNone(report["evaluation"]["precision"]["reconstruction_error_m"])
        self.assertIn("declared likelihood approximation", report["evaluation"]["precision"]["residual_model"]["scope"])
        with tempfile.TemporaryDirectory() as directory:
            path = save_reflection(report, Path(directory) / "supplied.json")
            self.assertTrue(verify_reflection(path, ZOE_ROOT)["verified"])

    def test_default_loop_contract_is_unchanged(self):
        loop = BoundedAutonomyLoop()
        proposals = [Candidate("review", "review", .6, .5, .2, "review")]
        event = loop.run({"instrument": "test"}, {}, proposals)
        self.assertFalse(event["belief_updated"])
        self.assertNotIn("target_action", event["goal"])
        self.assertNotIn("belief_update", event)
        self.assertFalse(loop.state()["belief_updated"])
        self.assertEqual(set(MODELS), {"arithmetic", "precision"})


if __name__ == "__main__":
    unittest.main()

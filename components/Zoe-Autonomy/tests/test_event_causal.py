from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

from zoe_autonomy.event_autonomy import EventCausalEngine, prediction_metrics
from zoe_autonomy.event_evaluation import evaluate_camera, run_event_evaluation, save_event_evaluation, verify_event_evaluation
from zoe_autonomy.event_core import EventEncoder, frames_to_events, observation_window, synthetic_sequence, validate_events
from zoe_autonomy.event_memory import KeyValueEventMemory, WorkingMemory
from zoe_autonomy.event_plasticity import GatedLocalPlasticity
from zoe_autonomy.event_reasoning import ForwardEnsemble, shortest_trajectory
from zoe_autonomy.event_uncertainty import IndependentUncertainty

ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))


class EventCoreCase(unittest.TestCase):
    def test_validation_and_deterministic_fixture(self):
        sequence = synthetic_sequence(2, 1, steps=16, seed=7101)
        self.assertEqual(sequence, synthetic_sequence(2, 1, steps=16, seed=7101))
        self.assertEqual(len(sequence["targets"]), 16)
        self.assertTrue(sequence["events"])
        with self.assertRaises(ValueError):
            validate_events([{"step": 0, "x": 16, "y": 2, "polarity": 1}])
        with self.assertRaises(ValueError):
            validate_events([(1, 2, 2, 1), (0, 2, 2, 1)])

    def test_coherent_cluster_is_preserved_and_isolated_noise_is_measured(self):
        encoder = EventEncoder()
        events = [
            (0, 3, 7, 1), (0, 4, 7, 1), (0, 3, 8, 1), (0, 4, 8, 1),
            (0, 13, 1, 1), (0, 1, 13, -1),
        ]
        observation = encoder.encode(events)
        self.assertEqual(observation["raw_event_count"], 6)
        self.assertEqual(observation["event_count"], 4)
        self.assertEqual(observation["centroid"], [3.5, 7.5])
        self.assertEqual(observation["noise_ratio"], 1 / 3)
        self.assertNotEqual(observation["event_sha256"], observation["filtered_event_sha256"])

    def test_stdp_is_bounded_and_changes_future_routing(self):
        encoder = EventEncoder()
        first = encoder.encode([(0, 2, 7, 1), (0, 3, 7, 1)], plastic=True)
        second = encoder.encode([(1, 12, 12, 1), (1, 13, 12, 1)], plastic=True)
        self.assertNotEqual(first["stdp_weight_sha256"], second["stdp_weight_sha256"])
        self.assertLessEqual(np.max(np.abs(encoder.module_weights)), 1)
        self.assertEqual(second["active_modules"][0], 3)

    def test_rgb_frame_changes_become_polarity_events(self):
        first = np.zeros((16, 16, 3), dtype=np.uint8)
        second = first.copy()
        second[4:8, 5:9] = 255
        events = frames_to_events([first, second])
        self.assertEqual(len(events), 16)
        self.assertTrue(all(event["polarity"] == 1 and event["step"] == 1 for event in events))
        third = second.copy()
        third[4:8, 5:9] = 0
        self.assertTrue(all(event["polarity"] == -1 for event in frames_to_events([second, third])))


class EventMemoryCase(unittest.TestCase):
    def test_key_value_retrieval_replay_and_independent_working_spaces(self):
        memory = KeyValueEventMemory(capacity=8)
        memory.add_episode([0, 0, 0], "hold", {"delta_x": 1})
        memory.add_episode([1, 0, 0], "attend_right", {"delta_x": 2})
        retrieved = memory.retrieve([.9, 0, 0])
        self.assertAlmostEqual(sum(item["weight"] for item in retrieved), 1)
        self.assertEqual(retrieved[0]["episode"]["value"]["delta_x"], 2)
        self.assertEqual(len(memory.replay_batch(4)), 4)
        memory.working.write("perception", [1, 2])
        memory.working.write("action", [3])
        self.assertEqual(memory.working.read("perception"), [1, 2])
        self.assertEqual(memory.working.read("uncertainty"), [])
        with self.assertRaises(ValueError):
            memory.working.write("shared", [9])

    def test_persistent_chain_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = KeyValueEventMemory(directory)
            memory.add_episode([1], "hold", {"observation": {"centroid": [2, 7.5]}, "step": 1})
            memory.save()
            loaded = KeyValueEventMemory(directory)
            self.assertTrue(loaded.document()["chain_valid"])
            state = json.loads((Path(directory) / "memory.json").read_text())
            state["checkpoint"]["episodes"][0]["value"]["observation"]["centroid"][0] = 99
            (Path(directory) / "memory.json").write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(ValueError):
                KeyValueEventMemory(directory)


class EventReasoningCase(unittest.TestCase):
    def test_forward_prediction_and_exact_nonnegative_plan(self):
        ensemble = ForwardEnsemble()
        ensemble.update({"centroid": [2, 7.5]}, 0)
        ensemble.update({"centroid": [3, 7.5]}, 1)
        prediction = ensemble.predict(0, "hold")
        self.assertGreater(prediction["target_x"], 2)
        plan = shortest_trajectory(ensemble, 0)
        self.assertTrue(plan["nonnegative_costs"])
        self.assertEqual(len(plan["path"]), 2)
        self.assertTrue(all(edge["cost"] >= 0 for edge in plan["edges"]))

    def test_unlocalized_scene_requires_spatial_search(self):
        ensemble = ForwardEnsemble()
        prediction = ensemble.predict(0, "attend_right")
        self.assertTrue(prediction["search_required"])
        self.assertFalse(prediction["visible"])
        plan = shortest_trajectory(ensemble, 0)
        self.assertEqual(plan["path"][0], "attend_right")

    def test_independent_ood_intervention(self):
        uncertainty = IndependentUncertainty()
        normal = {
            "raw_event_count": 6, "raw_positive_events": 6, "raw_polarity_balance": 1.0,
            "event_sha256": "normal",
        }
        uncertainty.fit([normal for _ in range(12)])
        candidates = [{"prediction": {"target_x": 2.0}}, {"prediction": {"target_x": 2.0}}]
        self.assertFalse(uncertainty.assess(normal, candidates)["intervention"])
        ood = dict(normal, raw_event_count=80, raw_positive_events=0, raw_polarity_balance=-1.0, event_sha256="ood")
        varied = [{"prediction": {"target_x": 1.0}}, {"prediction": {"target_x": 7.0}}]
        result = uncertainty.assess(ood, varied)
        self.assertTrue(result["intervention"])
        self.assertFalse(result["plasticity_allowed"])


class EventPlasticityCase(unittest.TestCase):
    def test_gate_and_reversible_failed_consolidation(self):
        ensemble = ForwardEnsemble()
        plasticity = GatedLocalPlasticity()
        observation = {"centroid": [4, 7.5], "active_modules": [0]}
        blocked = plasticity.update(ensemble, observation, {"target_x": 2}, {"plasticity_allowed": False, "score": .9})
        self.assertFalse(blocked["changed"])
        allowed = plasticity.update(ensemble, observation, {"target_x": 2}, {"plasticity_allowed": True, "score": .1})
        self.assertTrue(allowed["changed"])
        memory = KeyValueEventMemory()
        memory.add_episode([0], "hold", {"observation": {"centroid": [2, 7.5]}, "step": 1})
        result = plasticity.consolidate(
            ensemble, memory,
            lambda _ensemble: {"recent_rmse": 1.0, "familiar_rmse": 1.0},
        )
        self.assertFalse(result["adopted"])
        self.assertTrue(result["restored_checkpoint"])


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab").is_dir(), "set ZOE_ROOT to a Zoe checkout")
class EventIntegrationCase(unittest.TestCase):
    def test_mirrored_scenes_change_decisions_and_actions_change_observation(self):
        left = EventCausalEngine()
        right = EventCausalEngine()
        left_reports = left.run_sequence(synthetic_sequence(12, -1, steps=4, seed=7501))
        right_reports = right.run_sequence(synthetic_sequence(2, 1, steps=4, seed=7502))
        self.assertNotEqual([item["selected_action"] for item in left_reports], [item["selected_action"] for item in right_reports])
        self.assertEqual(left_reports[0]["selected_action"], "attend_right")
        self.assertIsNone(left_reports[0]["observation"]["centroid"])
        self.assertIsNotNone(left_reports[1]["observation"]["centroid"])
        for report in left_reports + right_reports:
            self.assertTrue(report["event"]["guard"]["approved"])
            self.assertEqual(report["external_actions"], 0)
            for candidate in report["candidate_details"]:
                if candidate["action"] != "abstain":
                    self.assertIn("predicted_centroid", candidate["prediction"])
        self.assertTrue(left.memory._chain_valid())
        self.assertTrue(prediction_metrics(left_reports, [12, 11, 10, 9])["prediction_rmse"] >= 0)


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab").is_dir(), "set ZOE_ROOT to a Zoe checkout")
class EventEvaluationCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_event_evaluation(ZOE_ROOT)

    def test_pre_registered_contract_passes_without_protocol_changes(self):
        self.assertEqual(self.report["protocol_sha256"], "2bb2e92ecd81d5822bec7249dd39d00ab645b3bf61990ba30b1b43af58433ebc")
        self.assertTrue(self.report["overall"]["passed"])
        self.assertEqual(self.report["overall"]["failed_checks"], [])
        self.assertLess(
            self.report["metrics"]["adaptive_validation"]["prediction_rmse"],
            self.report["metrics"]["no_learning_validation"]["prediction_rmse"],
        )
        self.assertLess(
            self.report["metrics"]["adaptive_transfer"]["tracking_mae"],
            self.report["metrics"]["static_saliency_transfer"]["tracking_mae"],
        )
        self.assertGreaterEqual(self.report["metrics"]["adaptive_cycles_per_second"], 20)

    def test_saved_report_verifies_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event-evaluation.json"
            save_event_evaluation(self.report, path)
            self.assertTrue(verify_event_evaluation(path)["verified"])
            with self.assertRaises(FileExistsError):
                save_event_evaluation(self.report, path)
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["overall"]["passed"] = False
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_event_evaluation(edited)

    def test_camera_conversion_preserves_provenance_without_images(self):
        def fake_capture(_device, frame):
            index = fake_capture.index
            fake_capture.index += 1
            image = Image.new("RGB", (64, 64), (8, 8, 8))
            for x in range(36 + index * 8, 40 + index * 8):
                for y in range(20, 28):
                    image.putpixel((x, y), (220, 220, 220))
            image.save(frame)
            return {
                "device": "camera-test-double",
                "frame_sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                "audio_captured": False,
                "selection": "operator-requested evaluation input",
            }

        fake_capture.index = 0
        with mock.patch("zoe_autonomy.event_evaluation.capture_camera_frame", side_effect=fake_capture):
            result = evaluate_camera(ZOE_ROOT, EventCausalEngine(), "camera-test-double")
        self.assertTrue(result["passed"])
        self.assertGreater(result["event_count"], 0)
        self.assertEqual(result["frame_count"], 2)
        self.assertFalse(result["audio_captured"])
        self.assertFalse(result["images_retained"])
        self.assertFalse(result["autonomously_selected"])
        self.assertIsNotNone(result["selected_action"])


if __name__ == "__main__":
    unittest.main()

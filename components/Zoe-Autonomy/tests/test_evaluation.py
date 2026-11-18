from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

from zoe_autonomy.cli import main
from zoe_autonomy.evaluation import (
    _visual_input,
    run_evaluation,
    save_evaluation,
    verify_evaluation,
)
from zoe_autonomy.loop import digest

ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab").is_dir(), "set ZOE_ROOT to a Zoe checkout")
class EvaluationCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_evaluation(ZOE_ROOT)

    def test_four_parts_pass_and_visual_dependency_is_measured_separately(self):
        checks = self.report["checks"]
        for name in ("visual_perception", "autonomous_thinking", "measured_learning", "executed_action"):
            self.assertTrue(checks[name]["passed"], name)
        self.assertTrue(checks["experience_changes_later_decision"]["passed"])
        self.assertTrue(checks["action_changes_later_observation"]["passed"])
        self.assertFalse(checks["vision_changes_decision"]["passed"])
        self.assertEqual(self.report["visual_counterfactual"]["changed_event_fields"], [])
        self.assertTrue(self.report["overall"]["four_capabilities_passed"])
        self.assertFalse(self.report["overall"]["integrated_visual_autonomy_passed"])
        self.assertEqual(self.report["overall"]["failed_checks"], ["vision_changes_decision"])
        self.assertEqual(
            self.report["capability_coverage"]["perception"]["object_recognition"]["status"],
            "not_demonstrated_here",
        )

    def test_save_verify_tamper_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.json"
            save_evaluation(self.report, path)
            verification = verify_evaluation(path)
            self.assertTrue(verification["verified"])
            self.assertFalse(verification["integrated_visual_autonomy_passed"])
            with self.assertRaises(FileExistsError):
                save_evaluation(self.report, path)
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["checks"]["vision_changes_decision"]["passed"] = True
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_evaluation(edited)
            edited["evaluation_sha256"] = digest({key: value for key, value in edited.items() if key != "evaluation_sha256"})
            with self.assertRaisesRegex(ValueError, "coverage is inconsistent"):
                verify_evaluation(edited)

    def test_cli_returns_behavioral_failure_but_saves_verifiable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli-evaluation.json"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = main(["--zoe-root", str(ZOE_ROOT), "evaluate", "--output", str(path)])
                self.assertEqual(result, 1)
                self.assertIn("Four capabilities: PASS", output.getvalue())
                self.assertIn("Integrated visual autonomy: FAIL", output.getvalue())
                self.assertIn("FAIL vision_changes_decision", output.getvalue())
                self.assertEqual(main(["verify-evaluation", str(path)]), 0)
            self.assertTrue(path.is_file())

    def test_camera_frame_provenance_without_retaining_the_photograph(self):
        def fake_capture(_device, frame):
            image = Image.new("RGB", (64, 64), (12, 12, 12))
            for x in range(40, 56):
                for y in range(8, 24):
                    image.putpixel((x, y), (240, 240, 240))
            image.save(frame)
            return {
                "device": "camera-test-double",
                "frame_sha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
                "audio_captured": False,
                "selection": "operator-requested evaluation input, not an autonomous camera action",
            }

        with mock.patch("zoe_autonomy.evaluation.capture_camera_frame", side_effect=fake_capture):
            visual, capture = _visual_input(ZOE_ROOT, None, "camera-test-double", 2)
        source = visual["saliency"]["source"]
        self.assertEqual(source["kind"], "live_camera_frame")
        self.assertTrue(source["live_camera"])
        self.assertIsNone(source["path"])
        self.assertFalse(source["image_retained"])
        self.assertEqual(source["sha256"], capture["frame_sha256"])
        self.assertEqual(len(visual["saliency"]["scanpath"]), 2)
        self.assertFalse(capture["audio_captured"])


if __name__ == "__main__":
    unittest.main()

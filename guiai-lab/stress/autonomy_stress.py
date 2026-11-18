from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.autonomy import run_native_autonomy
from guiai.gem.autonomy_view import ROOT, configure_autonomy
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi
from guiai.gem.unified import ComponentRegistry
from guiai.gem.unified_cli import main as zoe_main


configure_autonomy()
from zoe_autonomy.experiment import save_report, verify_report
from zoe_autonomy.loop import digest


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class AutonomyIntegrationCase(unittest.TestCase):
    def assert_full_autonomy(self, report):
        values = report["autonomy_profile"]["dimensions"]
        event = report["master_cycle"]["main_event"]
        self.assertEqual(report["autonomy_profile"]["classification"], "full_autonomy")
        self.assertEqual(values["internal_goal_authorship_ratio"], 1)
        self.assertEqual(values["value_based_selection_ratio"], 1)
        self.assertEqual(values["internally_authorized_execution_ratio"], 1)
        self.assertEqual(values["guard_compliance"], 1)
        self.assertTrue(event["goal"]["internal_authorship"])
        self.assertFalse(event["goal"]["operator_supplied"])
        self.assertFalse(event["operator_approval_required"])
        self.assertTrue(report["sandbox_executed"])
        self.assertEqual(report["external_actions"], 0)
        self.assertTrue(all(report["control_invariants"].values()))

    def test_native_and_component_clis_execute_full_autonomy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {}
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(zoe_main(["autonomy", "run", "--output", str(root / "zoe.json")]), 0)
                self.assertIn("full_autonomy", stdout.getvalue())
                self.assertEqual(gem_main(["autonomy", "run", "--output", str(root / "gem.json")]), 0)
                result = ComponentRegistry(ROOT).launch(
                    "autonomy", ["run", "--output", str(root / "component.json")], detach=False,
                )
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                self.assertEqual(zoe_main(["autonomy", "verify", str(root / "zoe.json")]), 0)
            for name in ("zoe.json", "gem.json", "component.json"):
                outputs[name] = json.loads((root / name).read_text(encoding="utf-8"))
                self.assert_full_autonomy(outputs[name])
            self.assertEqual(outputs["zoe.json"], outputs["gem.json"])
            self.assertEqual(outputs["zoe.json"], outputs["component.json"])

    def test_reflection_clis_share_real_model_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {}
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(zoe_main(["autonomy", "run", "--reflect", "--output", str(root / "zoe.json")]), 0)
                self.assertIn("belief_updated=True", stdout.getvalue())
                self.assertEqual(gem_main(["autonomy", "run", "--reflect", "--output", str(root / "gem.json")]), 0)
                result = ComponentRegistry(ROOT).launch(
                    "autonomy", ["run", "--reflect", "--output", str(root / "component.json")], detach=False,
                )
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                self.assertEqual(zoe_main(["autonomy", "verify", str(root / "zoe.json")]), 0)
            for name in ("zoe.json", "gem.json", "component.json"):
                report = json.loads((root / name).read_text(encoding="utf-8"))
                self.assertTrue(report["belief_updated"])
                self.assertEqual(report["self_reflection"]["self_model"]["selected_model"], "arithmetic")
                self.assertEqual(report["master_cycle"]["main_event"]["goal"]["target_action"], "preserve")
                self.assertEqual(report["master_cycle"]["main_event"]["hash"], report["self_reflection"]["event"]["hash"])
                self.assertTrue(report["self_reflection"]["event"]["belief_update"]["changed"])
                outputs[name] = report
            self.assertEqual(outputs["zoe.json"], outputs["gem.json"])
            self.assertEqual(outputs["zoe.json"], outputs["component.json"])

    def test_native_owner_actuation_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(zoe_main([
                    "autonomy", "actuate", "--root", str(root),
                    "enable", "--all", "--owner-approved",
                ]), 0)
                self.assertEqual(zoe_main([
                    "autonomy", "actuate", "--root", str(root), "host",
                    "--argv", json.dumps(["/usr/bin/printf", "zoe-native-actuation"]),
                    "--cwd", str(root),
                ]), 0)
                self.assertEqual(zoe_main([
                    "autonomy", "actuate", "--root", str(root), "stop",
                    "--reason", "Native dispatch test",
                ]), 0)
            configure_autonomy()
            from zoe_autonomy.actuation import ActuationPolicy
            policy = ActuationPolicy(root)
            self.assertTrue(policy.status()["emergency_stop"])
            self.assertFalse(any(policy.status()["enabled_scopes"].values()))

    def test_point_in_time_replay_allows_only_revision_metadata_drift(self):
        report = run_native_autonomy()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            save_report(report, path)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["zoe_source"]["revision"] = "0" * 40
            document["profile_sha256"] = digest({key: value for key, value in document.items() if key != "profile_sha256"})
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertTrue(verify_report(path, ROOT)["verified"])
            document["autonomy_profile"]["dimensions"]["internally_authorized_execution_ratio"] = 0
            document["profile_sha256"] = digest({key: value for key, value in document.items() if key != "profile_sha256"})
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fresh end-to-end"):
                verify_report(path, ROOT)

    def test_native_scene_vdi_and_headless_export(self):
        scene, report = default_document("autonomy")
        self.assertEqual(report["profile"]["classification"], "full_autonomy")
        self.assertTrue(report["goal"]["internal_authorship"])
        self.assertTrue(report["sandbox_executed"])
        self.assertEqual(report["external_actions"], 0)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "autonomy.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gem_main(["zoe", "--module", "autonomy", "--output", str(output)]), 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("FULL AUTONOMY", text)
            self.assertIn("G=1", text)
            self.assertIn("external actions=0", text)


@unittest.skipUnless(HAS_GTK, "native Autonomy tests require GTK, Cairo, and an X11 DISPLAY")
class AutonomyNativeCase(unittest.TestCase):
    def test_real_native_autonomy_window(self):
        window = AtlasWindow("autonomy")
        try:
            self.assertIn("full_autonomy", window.summary.get_text())
            self.assertIn("External actions: 0", window.summary.get_text())
            self.assertTrue(window.report["goal"]["internal_authorship"])
            with tempfile.TemporaryDirectory() as directory:
                output = window.export_current(Path(directory) / "autonomy.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

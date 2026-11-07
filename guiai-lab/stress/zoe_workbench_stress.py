from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from guiai.gem.unified import COMPONENTS, ComponentRegistry, unified_scene
from guiai.gem.zoe_workbench import WorkbenchProcess, free_port


class WorkbenchRegistrationCase(unittest.TestCase):
    def test_component_is_registered_and_launchable(self):
        registry = ComponentRegistry()
        component = registry.component("cern-console")
        self.assertEqual(component.module, "guiai.gem.zoe_workbench_cli")
        self.assertTrue(registry.source("cern-console")["available"])
        command, cwd = registry.command("cern-console")
        self.assertIn("guiai.gem.zoe_workbench_cli", command)
        self.assertIn("start", command)
        self.assertTrue(cwd.is_dir())
        self.assertEqual(len(COMPONENTS), 9)

    def test_unified_layout_fits_the_new_component(self):
        scene, report = unified_scene()
        self.assertEqual(report["entrypoint_count"], 9)
        memory = next(item for item in scene.objects if item["id"] == "unified-memory")
        component = next(item for item in scene.objects if item["id"] == "component-cern-console")
        self.assertGreater(memory["bounds"][1], component["bounds"][3])
        self.assertGreaterEqual(scene.canvas["height"], memory["bounds"][3])
        from guiai.gem.geometry import verify
        self.assertTrue(verify(scene).passed, verify(scene).text())


class WorkbenchBridgeCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zoe-workbench-")
        self.state = Path(self.temporary.name) / "runtime.json"

    def tearDown(self):
        self.temporary.cleanup()

    def test_attach_health_and_no_overwrite_manifest(self):
        workbench = WorkbenchProcess(state_file=self.state)
        try:
            state = workbench.start()
            self.assertTrue(state["readiness_verified"])
            self.assertEqual(state["health"]["stats"]["entries"], 9968)
            self.assertEqual(state["health"]["stats"]["felix_builds"], 43)
            output = Path(self.temporary.name) / "handover.json"
            workbench.write_manifest(output)
            manifest = json.loads(output.read_text())
            self.assertTrue(manifest["capabilities"]["helios_virtual_collider"])
            self.assertTrue(manifest["capabilities"]["atelier_vector_input"])
            self.assertTrue(manifest["capabilities"]["gem_coo_eps_import_export"])
            with self.assertRaises(FileExistsError):
                workbench.write_manifest(output)
            if not state["owned"]:
                self.assertFalse(workbench.stop()["stopped"])
                self.assertIsNotNone(workbench.health_at(state["port"]))
        finally:
            if self.state.exists():
                workbench.stop()

    def test_zoe_owned_start_and_stop(self):
        workbench = WorkbenchProcess(state_file=self.state, preferred_port=free_port())
        state = workbench.start()
        try:
            self.assertTrue(state["owned"])
            self.assertTrue(self.state.is_file())
            self.assertEqual(state["health"]["stats"]["documents"], 226)
        finally:
            stopped = workbench.stop()
        self.assertTrue(stopped["stopped"])
        self.assertIsNone(workbench.health_at(state["port"]))
        self.assertFalse(self.state.exists())

    def test_cli_start_health_and_stop(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        start = subprocess.run(
            ["python3", "-m", "guiai.gem.zoe_workbench_cli", "start", "--state-file", str(self.state), "--port", str(free_port())],
            cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(start.returncode, 0, start.stdout + start.stderr)
        state = json.loads(start.stdout)
        try:
            self.assertTrue(state["owned"])
            self.assertTrue(state["readiness_verified"])
        finally:
            stop = subprocess.run(
                ["python3", "-m", "guiai.gem.zoe_workbench_cli", "stop", "--state-file", str(self.state), "--port", str(state["port"])],
                cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=10, check=False,
            )
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
        self.assertTrue(json.loads(stop.stdout)["stopped"], stop.stdout + stop.stderr)

    def test_open_targets_without_gui_side_effects(self):
        workbench = WorkbenchProcess(state_file=self.state, preferred_port=free_port())
        previous = os.environ.get("BROWSER")
        os.environ["BROWSER"] = "/usr/bin/true"
        try:
            helios = workbench.open("helios")
            self.assertTrue(helios["url"].endswith("#helios"))
            self.assertTrue(helios["browser_opened"])
            atelier = workbench.open("atelier")
            self.assertTrue(atelier["url"].endswith("#atelier"))
            self.assertTrue(atelier["browser_opened"])
            with self.assertRaises(ValueError):
                workbench.open("unknown")
        finally:
            if previous is None:
                os.environ.pop("BROWSER", None)
            else:
                os.environ["BROWSER"] = previous
            workbench.stop()

    def test_full_verification_bridge(self):
        report = WorkbenchProcess(state_file=self.state).verify()
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["checks"]), 9)
        self.assertTrue(all(check["passed"] for check in report["checks"]))


class RecordingRegistry:
    def launch(self, identifier, detach=True):
        return type("Process", (), {"pid": 4242})()


@unittest.skipUnless(importlib.util.find_spec("gi"), "native unified controls require GTK and the private X11 wrapper")
class NativeUnifiedCase(unittest.TestCase):
    def test_native_controls_and_cognitive_shortcut(self):
        from guiai.gem.atlas_view import AtlasWindow
        window = AtlasWindow("unified")
        try:
            self.assertIsNotNone(window.scene)
            self.assertEqual(window.report["entrypoint_count"], 9)
            window.unified_registry = RecordingRegistry()
            window.make_unified_launch("cern-console")()
            self.assertEqual(window.report["last_launch"]["component"], "cern-console")
            window.open_cognitive()
            self.assertEqual(window.module, "cognitive")
            self.assertIsNotNone(window.scene)
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

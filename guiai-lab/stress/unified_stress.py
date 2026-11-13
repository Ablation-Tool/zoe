from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from guiai.gem.atlas import default_document
from guiai.gem.brain_life import BrainLife
from guiai.gem.brain_life_view import main as brain_main
from guiai.gem.cli import main as gem_main
from guiai.gem.desktop import DesktopProcesses
from guiai.gem.desktop_view import main as desktop_main
from guiai.gem.geometry import verify
from guiai.gem.knowledge import KnowledgeField
from guiai.gem.life import Life
from guiai.gem.life_view import main as life_main
from guiai.gem.runner import verify_vdi
from guiai.gem.unified import COMPONENTS, IDENTITY, ComponentRegistry, unified_scene
from guiai.gem.unified_cli import main as zoe_main


ROOT = Path(__file__).resolve().parents[1].parent
REGISTRY = ComponentRegistry(ROOT)


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class UnifiedSourceCase(unittest.TestCase):
    def test_all_eleven_source_projects_and_full_ablation_are_present(self):
        lock = json.loads((ROOT / "components.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["identity"], IDENTITY)
        self.assertEqual(len(lock["components"]), 10)
        self.assertEqual(len(COMPONENTS), 15)
        manifest = REGISTRY.manifest()
        self.assertEqual(manifest["repository_count"], 11)
        self.assertEqual(manifest["upstream_repository_count"], 10)
        self.assertEqual(manifest["entrypoint_count"], 15)
        self.assertTrue(all(row["source"]["source_present"] for row in manifest["components"]))
        self.assertTrue(all(row["source"]["mode"] in {"bundled", "zoe", "host"} for row in manifest["components"]))
        self.assertEqual(REGISTRY.source("chalkboard")["mode"], "bundled")
        self.assertTrue(REGISTRY.source("chalkboard")["available"])
        self.assertEqual(REGISTRY.source("life")["mode"], "zoe")
        for component in COMPONENTS:
            if component.revision is not None:
                self.assertEqual(component.revision, lock["components"][component.checkout]["revision"])
        for relative in (
            "components/ablation/ablation/analyzers/entropy_mapper.py",
            "components/ablation/gem-lab/gem/gtk_app.py",
            "components/ablation/tests",
            "components/hpux-tools/hpux_tools/cli.py",
            "guiai-lab/guiai/gem/life.py",
            "components/kevlar/policy.py",
            "components/pdf-signature-toolkit/pdf_signature_toolkit/verify.py",
            "components/Chalkboard/templates/README.template.md",
            "components/agent-logging-system/agent_logging_system/adapters/neurogarden_adapter.py",
            "components/agent-logging-system/docs/NEUROGARDEN.md",
        ):
            self.assertTrue((ROOT / relative).exists(), relative)
        self.assertTrue((ROOT / "assets/branding/orbital-emblem.png").is_file())
        self.assertEqual(REGISTRY.knowledge.knowledge_state()["observation_count"], 15)
        self.assertEqual(REGISTRY.knowledge.knowledge_state()["link_count"], 14)
        self.assertEqual(len(REGISTRY.knowledge.events), 29)

    def test_knowledge_observations_and_declared_links_preserve_boundaries(self):
        registry = ComponentRegistry(ROOT)
        observation = registry.observe(
            "kevlar", {"mode": "audit", "tool_count": 2},
            scope="synthetic unit-test observation", source="unified test fixture",
        )
        self.assertEqual(observation["trust_context"]["repository"], "https://github.com/Ablation-Tool/kevlar")
        self.assertEqual(observation["trust_context"]["source"], "unified test fixture")
        self.assertFalse(observation["stability_context"]["runtime_verified"])
        self.assertFalse(observation["belief_updated"])
        self.assertFalse(observation["executed"])
        link = registry.knowledge.connect(observation["id"], "zoe", "inspectable test link")
        self.assertFalse(link["evidence_transfer"])
        self.assertFalse(link["permission_transfer"])
        self.assertEqual(registry.knowledge.claims, [])
        with self.assertRaisesRegex(ValueError, "unknown knowledge observation"):
            registry.knowledge.connect("missing", "zoe", "must fail")
        with self.assertRaisesRegex(ValueError, "canonical JSON bytes"):
            registry.observe("zoe", {"large": "x" * 70000}, scope="bound test", source="test")

    def test_knowledge_roundtrip_tamper_detection_and_no_overwrite(self):
        field = ComponentRegistry(ROOT).knowledge
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.json"
            field.save(path)
            restored = KnowledgeField.load(path)
            self.assertEqual(restored.document(), field.document())
            self.assertEqual(restored.knowledge_state(), field.knowledge_state())
            with self.assertRaises(FileExistsError):
                field.save(path)
            document = field.document()
            document["events"][0]["payload"]["observation"]["observation"]["summary"] = "tampered"
            tampered = Path(directory) / "tampered.json"
            tampered.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                KnowledgeField.load(tampered)
            reordered = field.document()
            reordered["events"][0], reordered["events"][1] = reordered["events"][1], reordered["events"][0]
            reordered_path = Path(directory) / "reordered.json"
            reordered_path.write_text(json.dumps(reordered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                KnowledgeField.load(reordered_path)

    def test_command_source_isolation_research_runtime_and_content_library(self):
        with mock.patch.dict(os.environ, {"PYTHONPATH": "/invalid/host", "ZOE_PYTHON_DEPENDENCIES": "/tmp/dependencies"}, clear=False):
            command, cwd = REGISTRY.command("gem-lab")
            environment = REGISTRY.environment("gem-lab")
            self.assertEqual(command[-2:], ["launch", "--no-agent"])
            self.assertEqual(cwd, ROOT / "components/ablation/gem-lab")
            self.assertIn("components/ablation/gem-lab", environment["PYTHONPATH"])
            self.assertIn("/tmp/dependencies", environment["PYTHONPATH"])
            self.assertNotIn("/invalid/host", environment["PYTHONPATH"])
            command, cwd = REGISTRY.command("research")
            self.assertEqual(command[-2:], ["gem", "os"])
            self.assertEqual(cwd, ROOT / "components/graphics-environment-manager")
            self.assertEqual(environment["MASTER_GEM_RESEARCH_ROOT"], str(ROOT / "components/next-token-predictability"))
        with self.assertRaisesRegex(ValueError, "content library"):
            REGISTRY.command("chalkboard")
        with self.assertRaisesRegex(ValueError, "content library"):
            REGISTRY.command("neurogarden")
        with self.assertRaisesRegex(ValueError, "--db"):
            REGISTRY.command("cerotto")

    def test_ablation_uses_current_interpreter_and_caller_cwd(self):
        import sys

        with mock.patch.dict(os.environ, {}, clear=True):
            command, cwd = REGISTRY.command("ablation", ["analyze", "relative.bin"])
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(cwd, Path.cwd())
            self.assertEqual(command[-2:], ["analyze", "relative.bin"])
        with mock.patch.dict(os.environ, {"ZOE_PYTHON": "/explicit/python"}, clear=False):
            command, _cwd = REGISTRY.command("ablation", ["--help"])
            self.assertEqual(command[0], "/explicit/python")

    def test_manifest_separates_locked_and_actual_checkout_provenance(self):
        lock = json.loads((ROOT / "components.lock.json").read_text(encoding="utf-8"))
        row = next(item for item in REGISTRY.manifest()["components"] if item["identifier"] == "ablation")
        self.assertEqual(row["revision"], lock["components"]["ablation"]["revision"])
        self.assertEqual(row["source"]["checkout_root"], str(ROOT))
        self.assertRegex(row["source"]["checkout_revision"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(row["source"]["checkout_revision"], row["revision"])
        self.assertIsInstance(row["source"]["checkout_dirty"], bool)

    def test_installed_cern_source_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            for relative in ("guiai/gem/zoe_workbench_cli.py", "guiai/gem/cognitive.py"):
                path = package / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# installed anchor\n", encoding="utf-8")
            with mock.patch("guiai.gem.unified.__file__", str(package / "guiai/gem/unified.py")):
                registry = ComponentRegistry(package / "not-a-checkout")
                source = registry.source("cern-console")
                self.assertTrue(source["available"])
                self.assertEqual(source["mode"], "zoe")
                self.assertEqual(source["path"], package)
                _command, cwd = registry.command("cern-console")
                self.assertEqual(cwd, package)

    def test_cli_manifest_knowledge_show_and_default_native(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            knowledge = Path(directory) / "knowledge.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(zoe_main(["list"]), 0)
                self.assertEqual(zoe_main(["manifest", "--output", str(manifest)]), 0)
                self.assertEqual(zoe_main(["knowledge", "--output", str(knowledge)]), 0)
                self.assertEqual(zoe_main(["manifest", "--output", str(manifest)]), 2)
                self.assertEqual(zoe_main(["show", "chalkboard"]), 0)
                self.assertEqual(zoe_main(["show", "neurogarden"]), 0)
            self.assertIn("chalkboard", stdout.getvalue())
            self.assertIn("neurogarden", stdout.getvalue())
            self.assertEqual(json.loads(manifest.read_text())["entrypoint_count"], 15)
            self.assertEqual(KnowledgeField.load(knowledge).document(), REGISTRY.knowledge.document())
            with mock.patch("guiai.gem.desktop_view.launch_desktop") as launch:
                self.assertEqual(zoe_main([]), 0)
                launch.assert_called_once()

    def test_orbital_scene_vdi_and_headless_export(self):
        first, report = default_document("unified")
        second, _ = unified_scene(ComponentRegistry(ROOT))
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(first.document["id"], "zoe-allgems")
        self.assertTrue(verify(first).passed, verify(first).text())
        self.assertTrue(verify_vdi(first).passed, verify_vdi(first).text())
        self.assertEqual(report["knowledge"]["observation_count"], 15)
        self.assertEqual(report["knowledge"]["link_count"], 14)
        self.assertEqual(len(report["memory"]["events"]), 29)
        self.assertTrue(report["scene_only"])
        self.assertFalse(report["executed"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "unified.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gem_main(["zoe", "--module", "unified", "--output", str(output)]), 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Zoe · ALLGEMS", text)
            self.assertIn("Kevlar", text)
            self.assertIn("Chalkboard", text)
            self.assertIn("Zoe Life", text)


class LifeRulesCase(unittest.TestCase):
    def test_still_life_oscillator_and_glider(self):
        block = Life.from_pattern("block")
        initial = set(block.cells)
        block.advance(10)
        self.assertEqual(block.cells, initial)
        blinker = Life.from_pattern("blinker")
        initial = set(blinker.cells)
        blinker.advance(2)
        self.assertEqual(blinker.cells, initial)
        self.assertEqual(blinker.generation, 2)
        glider = Life.from_pattern("glider")
        initial = set(glider.cells)
        glider.advance(4)
        self.assertEqual(glider.cells, {(x + 1, y + 1) for x, y in initial})
        self.assertEqual(glider.population, 5)

    def test_boundaries_toggle_clear_and_validation(self):
        game = Life(width=8, height=8)
        game.toggle(0, 0)
        self.assertIn((0, 0), game.cells)
        game.toggle(0, 0)
        self.assertNotIn((0, 0), game.cells)
        game.cells = {(0, 0), (7, 7)}
        game.step()
        self.assertEqual(game.cells, set())
        game.clear()
        self.assertEqual(game.generation, 0)
        with self.assertRaises(ValueError):
            Life([(8, 0)], width=8, height=8)
        with self.assertRaises(ValueError):
            game.toggle(-1, 0)
        with self.assertRaises(ValueError):
            game.advance(10001)
        with self.assertRaises(ValueError):
            Life.from_pattern("unknown")

    def test_scene_and_no_overwrite_exports(self):
        game = Life.from_pattern("glider").advance(4)
        scene = game.scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("json", "svg", "png", "gem"):
                output = root / f"life.{kind}"
                game.export(output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    game.export(output)
            document = json.loads((root / "life.json").read_text())
            self.assertEqual(document["state_sha256"], game.digest())
            self.assertFalse(document["biological_life_created"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(life_main(["--steps", "4", "--output", str(root / "cli.svg")]), 0)
            self.assertIn("Zoe Life", (root / "cli.svg").read_text())


class BrainLifeCase(unittest.TestCase):
    def test_three_dimensional_rules_and_boundaries(self):
        game = BrainLife([(1, 1, 1)], size=4)
        game.step()
        self.assertEqual(game.cells, set())
        game = BrainLife([(1, 1, 1), (2, 1, 1), (1, 2, 1)], size=4)
        game.step()
        self.assertIn((2, 2, 1), game.cells)
        game.toggle(0, 0, 0)
        self.assertIn((0, 0, 0), game.cells)
        game.clear()
        self.assertEqual(game.generation, 0)
        with self.assertRaises(ValueError):
            game.toggle(-1, 0, 0)
        with self.assertRaises(ValueError):
            BrainLife(size=11)
        with self.assertRaises(ValueError):
            game.advance(1001)

    def test_text_rendering_and_cli(self):
        game = Life.from_text("A")
        self.assertEqual(game.population, 18)
        with self.assertRaises(ValueError):
            Life.from_text("@")
        with self.assertRaises(ValueError):
            Life.from_text("AA", width=8, height=8)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "text.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(life_main(["--text", "ZOE", "--output", str(output)]), 0)
            self.assertIn("Zoe Life", output.read_text())

    def test_brain_scene_exports_and_cli(self):
        game = BrainLife.from_brain()
        self.assertGreater(game.population, 0)
        self.assertFalse(game.document()["anatomical_brain"])
        scene = game.scene(65)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ("json", "svg", "png", "gem"):
                output = root / f"brain.{kind}"
                game.export(output, yaw=65)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    game.export(output, yaw=65)
            document = json.loads((root / "brain.json").read_text())
            self.assertEqual(document["state_sha256"], game.digest())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(brain_main(["--output", str(root / "cli.svg")]), 0)
            self.assertIn("Zoe Brain Life", (root / "cli.svg").read_text())


class _FakeProcess:
    def __init__(self, pid=4321):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class DesktopCase(unittest.TestCase):
    def registry(self, process):
        component = types.SimpleNamespace(title="Zoe Life", inspect_only=False)
        return types.SimpleNamespace(
            component=lambda _identifier: component,
            launch=mock.Mock(return_value=process),
        )

    def test_launch_deduplicate_reap_and_stop(self):
        process = _FakeProcess()
        registry = self.registry(process)
        processes = DesktopProcesses(registry)
        record = processes.launch("life")
        self.assertEqual(record["pid"], 4321)
        with self.assertRaisesRegex(ValueError, "already running"):
            processes.launch("life")
        with mock.patch("guiai.gem.desktop.os.killpg") as killpg:
            stopped = processes.stop(4321)
        self.assertEqual(stopped["exit_status"], 0)
        self.assertEqual(processes.running, {})
        process.returncode = 0
        self.assertEqual(processes.reap(), [])

    def test_reap_and_headless_desktop(self):
        process = _FakeProcess()
        processes = DesktopProcesses(self.registry(process))
        processes.launch("life")
        process.returncode = 7
        self.assertEqual(processes.reap()[0]["exit_status"], 7)
        self.assertEqual(processes.running, {})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "desktop.svg"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(desktop_main(["--list"]), 0)
                self.assertEqual(desktop_main(["--output", str(output)]), 0)
            self.assertIn("life", stdout.getvalue())
            self.assertIn("Zoe Life", output.read_text())


@unittest.skipUnless(os.environ.get("GEM_COMPONENT_TESTS") == "1", "set GEM_COMPONENT_TESTS=1 for real component commands")
class UnifiedCommandCase(unittest.TestCase):
    def test_real_component_commands(self):
        registry = ComponentRegistry(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [
                ("ablation", ["--help"], None),
                ("gem-lab", ["demo", "--output", str(root / "lab-run")], "lab-run"),
                ("gem", ["workbench", "check", "--output", str(root / "canonical.json")], "canonical.json"),
                ("helen", ["--module", "onset", "--output", str(root / "helen.json")], "helen.json"),
                ("brain", ["notebook", "--output", str(root / "brain.json")], "brain.json"),
                ("hpux-tools", ["doctor"], None),
                ("life", ["--steps", "4", "--output", str(root / "life.svg")], "life.svg"),
                ("life", ["--3d", "--output", str(root / "brain.svg")], "brain.svg"),
                ("kevlar", ["--help"], None),
                ("pdf", ["--help"], None),
                ("research", ["workbench", "list"], None),
            ]
            for identifier, arguments, artifact in cases:
                with self.subTest(component=identifier):
                    result = registry.launch(identifier, arguments, detach=False)
                    self.assertEqual(result.returncode, 0, (identifier, result.stdout, result.stderr))
                    if artifact:
                        self.assertTrue((root / artifact).exists())


@unittest.skipUnless(HAS_GTK, "native unified tests require GTK, Cairo, and an X11 DISPLAY")
class UnifiedNativeCase(unittest.TestCase):
    def test_native_hub_inspect_link_launch_and_memory(self):
        window = AtlasWindow("unified")
        try:
            self.assertEqual(window.unified_registry.knowledge.knowledge_state()["observation_count"], 15)
            window.show_unified("chalkboard")
            self.assertIn("Chalkboard", window.summary.get_text())
            self.assertIn("Content inspection only", window.summary.get_text())
            window.record_unified_source("kevlar")
            self.assertEqual(window.unified_registry.knowledge.knowledge_state()["observation_count"], 16)
            self.assertEqual(window.unified_registry.knowledge.knowledge_state()["link_count"], 15)
            with mock.patch.object(window.unified_registry, "launch", return_value=types.SimpleNamespace(pid=12345)) as launch:
                window.launch_unified("kevlar", ["--help"])
                launch.assert_called_once_with("kevlar", ["--help"], detach=True)
            self.assertIn("12345", window.summary.get_text())
            self.assertIn("does not verify readiness", window.summary.get_text())
            with tempfile.TemporaryDirectory() as directory:
                path = window.export_current(Path(directory) / "knowledge.json")
                self.assertEqual(KnowledgeField.load(path).document(), window.unified_registry.knowledge.document())
                with self.assertRaises(FileExistsError):
                    window.export_current(path)
            window.open_cognitive()
            self.assertEqual(window.module, "cognitive")
        finally:
            window.destroy()

    def test_native_life_window_controls(self):
        from guiai.gem.life_view import LifeWindow

        window = LifeWindow(Life.from_pattern("glider"))
        try:
            window.step()
            self.assertEqual(window.game.generation, 1)
            window.reset()
            self.assertEqual(window.game.generation, 0)
            population = window.game.population
            window.action("toggle", 0, 0)
            self.assertEqual(window.game.population, population + 1)
            window.clear()
            self.assertEqual(window.game.population, 0)
            window.play()
            self.assertIsNotNone(window.timer)
            window.stop()
            self.assertIsNone(window.timer)
            window.text_entry.set_text("A")
            window.render_text()
            self.assertEqual(window.game.population, 18)
            window.step()
            window.reset()
            self.assertEqual(window.game.population, 18)
            self.assertEqual(window.game.generation, 0)
        finally:
            window.destroy()

    def test_native_brain_life_controls(self):
        from guiai.gem.brain_life_view import BrainLifeWindow

        window = BrainLifeWindow(BrainLife.from_brain())
        try:
            initial = set(window.game.cells)
            window.step()
            self.assertEqual(window.game.generation, 1)
            window.reset()
            self.assertEqual(window.game.cells, initial)
            yaw = window.yaw
            window.rotate_right()
            self.assertEqual(window.yaw, yaw + 15)
            window.clear()
            self.assertEqual(window.game.population, 0)
            window.play()
            self.assertIsNotNone(window.timer)
            window.stop()
            self.assertIsNone(window.timer)
        finally:
            window.destroy()

    def test_native_desktop_launch_and_stop(self):
        from guiai.gem.desktop_view import ZoeDesktopWindow

        window = ZoeDesktopWindow(ComponentRegistry(ROOT))
        process = _FakeProcess()
        self.assertFalse(window.agent_toggle.get_active())
        self.assertIsNone(window.agent_panel.pid)
        window.agent_toggle.set_active(True)
        self.assertFalse(window.agent_panel.get_no_show_all())
        self.assertEqual(window.workspace_panes.get_child2(), window.agent_panel)
        window.workspace_ratio = 0.6
        window.layout_selector.set_active_id("left")
        self.assertEqual(window.workspace_panes.get_child1(), window.agent_panel)
        self.assertEqual(window.workspace_panes.get_position(), 576)
        window.layout_selector.set_active_id("right")
        self.assertEqual(window.workspace_panes.get_child2(), window.agent_panel)
        self.assertEqual(window.workspace_panes.get_position(), 864)
        window.agent_toggle.set_active(False)
        try:
            window.select_component(identifier="life")
            with mock.patch.object(window.registry, "launch", return_value=process):
                window.launch_selected()
            self.assertIn(4321, window.processes.running)
            rows = window.process_list.get_children()
            window.refresh_processes()
            self.assertEqual(window.process_list.get_children(), rows)
            window.selected_pid = 4321
            with mock.patch("guiai.gem.desktop.os.killpg"):
                window.stop_selected()
            self.assertEqual(window.processes.running, {})
        finally:
            window.destroy()

    def test_native_agent_panel_lifecycle(self):
        from guiai.gem.agent_terminal import BOOTSTRAP, EmbeddedAgentPanel

        with tempfile.TemporaryDirectory() as directory:
            panel = EmbeddedAgentPanel("fixture --flag", workspace=directory)
            panel.terminal = mock.Mock()
            panel.terminal.spawn_sync.return_value = (True, 24680)
            panel.start()
            self.assertEqual(panel.pid, 24680)
            arguments = panel.terminal.spawn_sync.call_args.args
            self.assertEqual(arguments[2], ["fixture", "--flag"])
            self.assertIn("ZOE_OS=1", arguments[3])
            panel.terminal.feed_child.assert_any_call(BOOTSTRAP.encode("utf-8"))
            panel.submit("inspect")
            panel.terminal.feed_child.assert_any_call(b"inspect")
            panel.insert_paths(["/tmp/a b"])
            panel.terminal.feed_child.assert_any_call(b"'/tmp/a b'")
            panel.start()
            self.assertEqual(panel.terminal.spawn_sync.call_count, 1)
            with mock.patch("guiai.gem.agent_terminal.os.killpg") as killpg:
                panel.stop()
                panel.kill()
            self.assertEqual(killpg.call_args_list[0].args, (24680, 15))
            self.assertEqual(killpg.call_args_list[1].args, (24680, 9))
            panel.on_child_exit(panel.terminal, status=0)
            self.assertIsNone(panel.pid)
            panel.command_entry.set_text("'")
            panel.start()
            self.assertIn("Unable to start agent", panel.status.get_text())
            panel.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

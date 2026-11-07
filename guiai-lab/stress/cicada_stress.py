from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cicada import CicadaClock, REFERENCE_HZ, SOIL_RELEASE_C
from guiai.gem.cicada_view import main as cicada_main
from guiai.gem.cli import main as gem_main
from guiai.gem.field import _canonical
from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    from guiai.gem.cicada_view import CicadaWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


def digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class CicadaModelCase(unittest.TestCase):
    def test_thirteen_and_seventeen_year_gates_emergence_and_chorus(self):
        for cycle in (13, 17):
            with self.subTest(cycle=cycle):
                clock = CicadaClock(cycle)
                self.assertEqual(clock.gate_cycle, cycle - 1)
                clock.step(cycle - 1)
                self.assertTrue(clock.gate_open)
                self.assertFalse(clock.emerged)
                self.assertEqual(clock.reference_ticks, (cycle - 1) * REFERENCE_HZ)
                clock.step(1)
                self.assertTrue(clock.emerged)
                self.assertFalse(clock.chorus)
                self.assertEqual(clock.last_actions, ["advance", "emerge"])
                clock.step("0.02")
                self.assertTrue(clock.chorus)
                self.assertFalse(clock.measurements()["biological_measurement"])
                self.assertFalse(clock.measurements()["external_actions_executed"])
                self.assertFalse(clock.measurements()["llm_called"])

    def test_karban_host_cycles_and_environmental_release(self):
        clock = CicadaClock(17, host_rate=2, initial_cycles=15)
        clock.step(1)
        self.assertEqual(clock.host_cycles, 17)
        self.assertEqual(clock.calendar_age, 16)
        self.assertTrue(clock.emerged)
        self.assertIn("gate-open", clock.last_actions)
        self.assertIn("emerge", clock.last_actions)
        self.assertAlmostEqual(SOIL_RELEASE_C, 17.777777777777778)
        held = CicadaClock(13)
        held.step(13, soil_temp_c=17, after_sunset=False)
        self.assertFalse(held.emerged)
        self.assertTrue(held.measurements()["awaiting_conditions"])
        held.step("0.01", soil_temp_c=18, after_sunset=True)
        self.assertTrue(held.emerged)
        daylight = CicadaClock(13)
        daylight.step(13, soil_temp_c=20, after_sunset=False)
        self.assertFalse(daylight.emerged)

    def test_growth_variation_phase_wrap_and_entrainment(self):
        fast = CicadaClock(13, growth_multiplier=2)
        self.assertEqual(fast.gate_cycle, 8)
        self.assertEqual(fast.emergence_cycle, 9)
        slow = CicadaClock(13, growth_multiplier=.5)
        self.assertEqual(slow.gate_cycle, 24)
        self.assertEqual(slow.emergence_cycle, 25)
        pulse = CicadaClock(13, entrainment_strength=0)
        pulse.step(24)
        self.assertIn("daily-pulse", pulse.last_actions)
        self.assertEqual(pulse.phase, 0)
        entrained = CicadaClock(13, entrainment_strength=.25, initial_phase=.75)
        entrained.step(.1, host_phase=0)
        self.assertTrue(0 <= entrained.phase < 1)
        self.assertLess(entrained.phase, .75)

    def test_replay_roundtrip_tamper_detection_and_no_overwrite(self):
        game = CicadaClock(17, host_rate=2, initial_cycles=15)
        game.step(.5)
        game.step(.5)
        self.assertEqual(game.reference_ticks, REFERENCE_HZ)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "session.json"
            game.save(path)
            loaded = CicadaClock.replay(path)
            self.assertTrue(loaded.replay_verified)
            self.assertEqual(loaded.host_cycles, 17)
            self.assertEqual(loaded.calendar_age, 16)
            with self.assertRaises(FileExistsError):
                game.save(path)
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["events"][0]["state_sha256"] = "0" * 64
            event = tampered["events"][0]
            event["hash"] = digest({key: value for key, value in event.items() if key != "hash"})
            tampered["digest"] = digest({key: value for key, value in tampered.items() if key != "digest"})
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "diverges"):
                CicadaClock.replay(path)
            tampered["digest"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                CicadaClock.replay(path)

    def test_bounds_leave_state_unchanged(self):
        for configuration in (
            {"cycle_years": 12}, {"host_rate": 3}, {"initial_cycles": -1},
            {"initial_phase": 1}, {"growth_multiplier": 0}, {"years_per_second": 0},
        ):
            with self.subTest(configuration=configuration):
                with self.assertRaises(ValueError):
                    CicadaClock(**configuration)
        clock = CicadaClock(13)
        for seconds in (0, -1, 86401, "not-a-number"):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    clock.step(seconds)
        large = CicadaClock(13, years_per_second=1000)
        before = large._state_digest()
        with self.assertRaises(ValueError):
            large.step(86400)
        self.assertEqual(large._state_digest(), before)
        bounded = CicadaClock(13)
        for _ in range(256):
            bounded.step(.001)
        before = bounded._state_digest()
        with self.assertRaisesRegex(ValueError, "event bound"):
            bounded.step(.001)
        self.assertEqual(bounded._state_digest(), before)
        malformed = clock.document()
        malformed["configuration"] = {}
        malformed["digest"] = digest({key: value for key, value in malformed.items() if key != "digest"})
        with self.assertRaisesRegex(ValueError, "configuration"):
            CicadaClock.replay(malformed)
        with self.assertRaisesRegex(ValueError, "rational-text bound"):
            CicadaClock(initial_cycles="1" * 129)

    def test_scene_exports_default_document_and_forwarded_cli(self):
        game = CicadaClock(17, host_rate=2, initial_cycles=15)
        game.step(1)
        self.assertTrue(verify(game.scene()).passed)
        self.assertTrue(verify_vdi(game.scene()).passed)
        scene, report = default_document("cicada")
        self.assertTrue(verify(scene).passed)
        self.assertFalse(report["biological_measurement"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("svg", "png", "gem"):
                output = root / f"clock.{suffix}"
                game.export(output)
                self.assertTrue(output.is_file())
                with self.assertRaises(FileExistsError):
                    game.export(output)
            for index, entrypoint in enumerate((cicada_main, gem_main, zoe_main)):
                arguments = ["--cycle", "17", "--host-rate", "2", "--start", "15", "--years", "1", "--output", str(root / f"session-{index}.json")]
                if entrypoint is not cicada_main:
                    arguments.insert(0, "cicada")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(entrypoint(arguments), 0)
                self.assertTrue(CicadaClock.replay(root / f"session-{index}.json").replay_verified)


@unittest.skipUnless(HAS_GTK, "native cicada tests require GTK, Cairo, and an X11 DISPLAY")
class CicadaNativeCase(unittest.TestCase):
    def test_native_act_step_replay_logo_and_exports(self):
        now = [0.0]
        window = CicadaWindow(CicadaClock(initial_cycles=8), clock=lambda: now[0])
        window.show_all()
        try:
            self.assertIsNone(window.timer)
            self.assertIsNotNone(window.logo)
            self.assertTrue(window.act())
            self.assertIsNotNone(window.timer)
            now[0] += .25
            self.assertTrue(window.on_tick())
            self.assertEqual(len(window.game.events), 1)
            self.assertTrue(window.on_tick())
            self.assertEqual(len(window.game.events), 1)
            now[0] += .25
            window.on_tick()
            self.assertEqual(len(window.game.events), 2)
            self.assertFalse(window.act())
            self.assertIsNone(window.timer)
            window.step_year()
            self.assertEqual(len(window.game.events), 3)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                session = root / "session.json"
                window.game.save(session)
                self.assertTrue(window.load_path(session))
                previous = window.game
                bad = root / "bad.json"
                bad.write_text("not json", encoding="utf-8")
                self.assertFalse(window.load_path(bad))
                self.assertIs(window.game, previous)
                for suffix in ("svg", "png", "gem"):
                    self.assertTrue(window.export_current(root / f"native.{suffix}", suffix).is_file())
            window.cycle.set_active_id("17")
            window.host_rate.set_active_id("2")
            window.initial.set_value(15)
            window.start()
            self.assertIsNone(window.timer)
            window.step_year()
            self.assertTrue(window.game.emerged)
            self.assertEqual(window.game.calendar_age, 16)
        finally:
            window.destroy()

    def test_atlas_preview_and_dedicated_window(self):
        atlas = AtlasWindow("cicada")
        try:
            window = atlas.open_builtin("cicada")
            self.assertIs(window, atlas.open_builtin("cicada"))
            self.assertIsNone(window.timer)
            self.assertTrue(verify(atlas.scene).passed)
            self.assertFalse(atlas.report["biological_measurement"])
        finally:
            atlas.destroy()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import _ellipse, _scene, _text, default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.render import draw_cairo
from guiai.gem.geometry import verify
from guiai.gem.presence import PresenceField, demo_presence, export_presence, presence_scene
from guiai.gem.presence_view import main as presence_main
from guiai.gem.resilience import SECTORS, demo_traces
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class PresenceModelCase(unittest.TestCase):
    def test_attention_observation_reflection_correction_and_review(self):
        field = PresenceField()
        self.assertEqual(field.attention["event"], 0)
        field.focus("water", "host40", "test selection")
        field.observe("A documented example is not live telemetry.", "test observation")
        field.reflect("What remains uncertain?")
        field.correct("The graph is illustrative, not complete.")
        result = field.review("Review this model without acting on it")
        report = field.report()
        self.assertEqual(field.attention["sector"], "water")
        self.assertEqual(field.attention["event"], 1)
        self.assertEqual(len(field.frames), 1)
        self.assertEqual(len(field.reflections), 2)
        self.assertEqual(len(field.events), 5)
        self.assertTrue(result["review_required"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["belief_updated"])
        self.assertEqual(report["trace"]["status"], "ambiguous")
        self.assertEqual(report["expression"], "??")
        self.assertTrue(report["expression_is_not_emotion"])
        self.assertTrue(report["self_model_is_not_self"])
        self.assertFalse(report["consciousness_measured"])
        self.assertFalse(report["subjective_experience_established"])
        self.assertTrue(any("40 MHz" in item for item in report["known_unknowns"]))
        for invalid in (
            lambda: field.focus("unknown", "host80"),
            lambda: field.focus("water", "unknown"),
            lambda: field.focus("water", "host40", "x" * 129),
            lambda: field.observe(""),
            lambda: field.reflect("x" * 501),
            lambda: field.correct(" "),
        ):
            with self.assertRaises(ValueError):
                invalid()

    def test_persistence_tamper_detection_and_no_overwrite(self):
        field = demo_presence()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presence.json"
            field.save(path)
            restored = PresenceField.load(path)
            self.assertEqual(restored.document(), field.document())
            self.assertEqual(restored.report()["summary"], field.report()["summary"])
            with self.assertRaises(FileExistsError):
                field.save(path)
            edited = field.document()
            edited["events"][0]["payload"]["source"] = "forged source"
            edited_path = Path(directory) / "edited.json"
            edited_path.write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                PresenceField.load(edited_path)
            reordered = field.document()
            reordered["events"][0], reordered["events"][1] = reordered["events"][1], reordered["events"][0]
            reordered_path = Path(directory) / "reordered.json"
            reordered_path.write_text(json.dumps(reordered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                PresenceField.load(reordered_path)

    def test_every_view_glyph_export_and_cli(self):
        for sector in SECTORS:
            for trace in demo_traces():
                field = PresenceField()
                field.focus(sector, trace, "x" * 128)
                scene, report = presence_scene(field)
                self.assertTrue(verify(scene).passed, verify(scene).text())
                self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
                self.assertEqual(report["expression"], "^_^" if trace == "host80" else "??" if trace in {"host40", "amac40"} else "~")
        scene, _ = default_document("presence")
        self.assertTrue(verify(scene).passed)
        field = demo_presence()
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("json", "svg", "png", "gem"):
                path = Path(directory) / f"presence.{suffix}"
                output = field.save(path) if suffix == "json" else export_presence(field, path)
                self.assertEqual(output, path)
                self.assertGreater(path.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    field.save(path) if suffix == "json" else export_presence(field, path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(presence_main([str(Path(directory) / "presence.json"), "--output", str(Path(directory) / "replayed.svg")]), 0)
                self.assertEqual(presence_main(["--observe", "A test observation", "--output", str(Path(directory) / "direct.svg")]), 0)
                self.assertEqual(gem_main(["presence", "--output", str(Path(directory) / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["presence", "--output", str(Path(directory) / "zoe.svg")]), 0)
            self.assertIn("A self-model is not a self.", (Path(directory) / "direct.svg").read_text(encoding="utf-8"))

    def test_cairo_ellipse_does_not_join_preceding_text(self):
        import cairo
        scene = _scene("path-test", 100, 100, [
            _text("label", [10, 25], "Energy", 12, "#67e8f9"),
            _ellipse("circle", [50, 60], [10, 10], "#f0abfc", "none", 2),
        ], "ellipse path check")
        class InspectContext(cairo.Context):
            def arc(self, *args):
                self.point_before_arc = self.get_current_point()
                super().arc(*args)

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        context = InspectContext(surface)
        draw_cairo(context, scene, 100, 100)
        self.assertEqual(context.point_before_arc, (0, 0))


@unittest.skipUnless(HAS_GTK, "native Presence tests require GTK, Cairo, and an X11 DISPLAY")
class PresenceNativeCase(unittest.TestCase):
    def test_real_observe_review_and_correct_controls(self):
        window = AtlasWindow("presence")
        try:
            self.assertEqual(len(window.presence.events), 4)
            window.controls["sector"].set_active_id("water")
            window.controls["trace"].set_active_id("host40")
            window.controls["presence_note"].set_text("This selection is ambiguous.")
            window.observe_presence()
            self.assertEqual(window.presence.attention["sector"], "water")
            self.assertEqual(window.presence.attention["trace"], "host40")
            self.assertEqual(window.presence.frames[-1]["text"], "This selection is ambiguous.")
            window.review_presence()
            window.correct_presence()
            self.assertEqual(len(window.presence.events), 8)
            self.assertEqual(window.presence.reflections[-1]["text"], "Correction: This selection is ambiguous.")
            self.assertTrue(window.report["review_required"])
            self.assertFalse(window.report["executed"])
            self.assertFalse(window.report["consciousness_measured"])
            self.assertIn("A self-model is not a self", window.summary.get_text())
            with tempfile.TemporaryDirectory() as directory:
                output = window.export_current(Path(directory) / "presence.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

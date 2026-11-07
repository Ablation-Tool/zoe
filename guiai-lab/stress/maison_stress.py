from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.maison import ASSOCIATIONS, association, export_maison, inspect_reference, maison_scene
from guiai.gem.maison_view import main as maison_main
from guiai.gem.practice import PracticeLog
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


REFERENCE = Path("/home/cowboy/Music/Word Association.pdf")


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class MaisonCase(unittest.TestCase):
    def test_association_deck_and_validation(self):
        self.assertEqual(len(ASSOCIATIONS), 18)
        self.assertEqual(set(item["pillar"] for item in ASSOCIATIONS.values()), {"executive", "luxury", "enterprise"})
        word, definition = association(" Provenance ")
        self.assertEqual(word, "provenance")
        self.assertIn("trace", definition["prompt"])
        with self.assertRaises(ValueError):
            association("empire")
        with self.assertRaises(ValueError):
            association(None)

    def test_scene_exports_and_forwarded_cli(self):
        scene, report = maison_scene(word="provenance")
        self.assertEqual(report["word"], "provenance")
        self.assertIsNone(report["score"])
        self.assertFalse(report["autonomous_action"])
        self.assertTrue(report["practice"]["synthetic_example"])
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        scene, _ = default_document("maison")
        self.assertTrue(verify(scene).passed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("svg", "png", "gem"):
                output = root / f"maison.{suffix}"
                self.assertEqual(export_maison(output), output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_maison(output)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(maison_main(["--word", "bespoke", "--output", str(root / "direct.svg")]), 0)
                self.assertEqual(maison_main(["scene", "--word", "atelier", "--output", str(root / "scene.svg")]), 0)
                self.assertEqual(gem_main(["maison", "--word", "gravitas", "--output", str(root / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["maison", "--word", "stewardship", "--output", str(root / "zoe.svg")]), 0)
                self.assertEqual(maison_main(["deck", "--output", str(root / "deck.json")]), 0)
            for name in ("direct.svg", "scene.svg", "gem.svg", "zoe.svg"):
                self.assertIn("Zoe Maison", (root / name).read_text(encoding="utf-8"))
            self.assertEqual(json.loads((root / "deck.json").read_text(encoding="utf-8"))["count"], 18)

    def test_packaged_deck(self):
        document = json.loads((Path(__file__).resolve().parents[2] / "guiai-lab/docs/examples/maison-deck.json").read_text(encoding="utf-8"))
        self.assertEqual(document["count"], 18)
        self.assertIsNone(document["score"])
        self.assertFalse(document["autonomous_action"])
        self.assertEqual(set(document["associations"]), set(ASSOCIATIONS))

    @unittest.skipUnless(REFERENCE.is_file(), "the supplied association PDF is unavailable")
    def test_actual_reference_and_cli(self):
        reference = inspect_reference(REFERENCE)
        self.assertEqual(reference["bytes"], 171612)
        self.assertEqual(reference["pages"], 1)
        self.assertEqual(reference["sha256"], "d34a3a2d2528e9e5483d789917acc323ede5e0ce6ffb571cd3edcc1de7367301")
        self.assertFalse(reference["source_text_bundled"])
        self.assertIn("not doctrine", reference["role"])
        scene, report = maison_scene(word="provenance", reference=reference)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertEqual(report["reference"]["pages"], 1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "reference.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(maison_main(["reference", str(REFERENCE), "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["sha256"], reference["sha256"])


@unittest.skipUnless(HAS_GTK, "native Maison tests require GTK, Cairo, and an X11 DISPLAY")
class MaisonNativeCase(unittest.TestCase):
    def test_association_reference_log_and_export(self):
        window = AtlasWindow("maison")
        try:
            window.controls["maison_word"].set_active_id("bespoke")
            window.present_maison()
            self.assertEqual(window.report["word"], "bespoke")
            self.assertIn("adaptation", window.summary.get_text())
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if REFERENCE.is_file():
                    window.controls["maison_reference_path"].set_text(str(REFERENCE))
                    window.inspect_maison_reference()
                    self.assertEqual(window.maison_reference["pages"], 1)
                    self.assertEqual(window.maison_reference_path, str(REFERENCE))
                    reference = window.maison_reference
                    scene = window.scene
                    window.controls["maison_reference_path"].set_text(str(root / "missing.pdf"))
                    window.inspect_maison_reference()
                    self.assertIs(window.maison_reference, reference)
                    self.assertIs(window.scene, scene)
                    self.assertIn("Association reference inspection failed", window.summary.get_text())
                log = root / "practice.json"
                window.export_current(log)
                self.assertTrue(PracticeLog.load(log).synthetic)
                previous = window.leadership_log
                window.controls["maison_log_path"].set_text(str(root / "missing.json"))
                window.load_maison_log()
                self.assertIs(window.leadership_log, previous)
                self.assertIn("Practice log load failed", window.summary.get_text())
                window.controls["maison_log_path"].set_text(str(log))
                window.load_maison_log()
                self.assertEqual(window.leadership_log_path, str(log))
                output = window.export_current(root / "maison.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

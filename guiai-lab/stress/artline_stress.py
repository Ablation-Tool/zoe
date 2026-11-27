from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from guiai.gem.artline import ArtlineDocument, _smooth, demo_document
from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi


try:
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gdk, Gtk
    from guiai.gem.artline_view import ArtlineWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class ArtlineDocumentCase(unittest.TestCase):
    def test_shapes_smoothing_selection_and_group_transformations(self):
        document = ArtlineDocument()
        rectangle = document.add_element("rectangle", bounds=[100, 100, 240, 220], fill="#101b2b")
        ellipse = document.add_element("ellipse", center=[400, 200], radii=[70, 45])
        rounded = document.add_element("rounded_rectangle", bounds=[500, 100, 650, 180], radius=15)
        line = document.add_element("line", points=[[100, 300], [300, 400]])
        path = document.add_element("path", points=[[100, 500], [220, 420], [380, 500]], closed=False, smooth=True)
        text = document.add_element("text", position=[100, 620], text="original study", size=22)
        self.assertEqual({item["type"] for item in document.elements}, {"rectangle", "ellipse", "rounded_rectangle", "line", "path", "text"})
        self.assertGreater(len(_smooth(path["points"], False)), len(path["points"]))
        self.assertEqual(document.element(rectangle["id"])["bounds"], [100, 100, 240, 220])
        group = document.group([rectangle["id"], ellipse["id"]])
        self.assertEqual(document.grouped([rectangle["id"]]), [rectangle["id"], ellipse["id"]])
        copies = document.duplicate([rectangle["id"]])
        self.assertEqual(len(copies), 2)
        document.transform(copies, dx=30, dy=20)
        document.transform(copies, flip="vertical")
        self.assertEqual(document.element(copies[0])["bounds"], [130, 120, 270, 240])
        document.transform([copies[1]], angle=.5)
        self.assertEqual(document.element(copies[1])["type"], "path")
        document.transform([rounded["id"]], flip="horizontal")
        self.assertEqual(document.element(rounded["id"])["bounds"], [500, 100, 650, 180])
        document.transform([line["id"]], dx=5, dy=-5)
        document.align_to_grid([line["id"]], spacing=10)
        document.restyle([text["id"]], stroke="#f0abfc", width=2)
        self.assertEqual(document.element(text["id"])["stroke"], "#f0abfc")
        document.ungroup([rectangle["id"]])
        self.assertIsNone(document.element(rectangle["id"])["group"])
        self.assertEqual(group, "group-1")
        for direction in ("front", "back", "forward", "backward"):
            document.reorder([rectangle["id"]], direction)
        before = len(document.elements)
        document.delete([text["id"]])
        self.assertEqual(len(document.elements), before - 1)
        document.undo()
        self.assertEqual(len(document.elements), before)
        document.redo()
        self.assertEqual(len(document.elements), before - 1)

    def test_layers_persistence_merge_and_transactional_rollback(self):
        source = ArtlineDocument()
        source.add_element("rectangle", bounds=[10, 10, 90, 90])
        layer = source.add_layer("Hidden archive")
        source.add_element("ellipse", center=[150, 100], radii=[30, 40])
        source.set_layer_visible(layer, False)
        source.set_layer_locked(layer, True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layers.json"
            source.save(path)
            restored = ArtlineDocument.load(path)
            self.assertEqual(restored.document(), source.document())
            self.assertEqual(len(restored.scene().objects), 1)
            with self.assertRaisesRegex(ValueError, "locked or hidden"):
                restored.add_element("rectangle", bounds=[200, 200, 240, 240])
            target = ArtlineDocument()
            target.add_element("text", position=[40, 80], text="target")
            target.merge(restored)
            self.assertEqual(len(target.elements), 3)
            self.assertFalse(target.layer(target.elements[-1]["layer"])["visible"])
            before = target.document()
            invalid = ArtlineDocument()
            invalid.add_element("rectangle", bounds=[10, 10, 20, 20])
            invalid.elements.append({"id": "bad", "type": "rectangle", "layer": "layer-1", "bounds": [50, 50, 20, 20]})
            history, future = list(target.history), list(target.future)
            with self.assertRaises(ValueError):
                target.merge(invalid)
            self.assertEqual(target.document(), before)
            self.assertEqual(target.history, history)
            self.assertEqual(target.future, future)
            with self.assertRaisesRegex(ValueError, "unknown layer"):
                target.remove_layer("layer-999")
            tampered = source.document()
            tampered["events"][0]["payload"]["type"] = "ellipse"
            tampered_path = Path(directory) / "tampered.json"
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                ArtlineDocument.load(tampered_path)
            invalid_events = source.document()
            invalid_events["events"] = {}
            invalid_path = Path(directory) / "events.json"
            invalid_path.write_text(json.dumps(invalid_events), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "document bounds"):
                ArtlineDocument.load(invalid_path)
            missing_geometry = source.document()
            del missing_geometry["elements"][1]["center"]
            geometry_path = Path(directory) / "missing-geometry.json"
            geometry_path.write_text(json.dumps(missing_geometry), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "required geometry"):
                ArtlineDocument.load(geometry_path)
            missing_counter = source.document()
            del missing_counter["next_element"]
            counter_path = Path(directory) / "missing-counter.json"
            counter_path.write_text(json.dumps(missing_counter), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported Artline document"):
                ArtlineDocument.load(counter_path)

    def test_svg_png_gem_and_no_overwrite_exports(self):
        document = demo_document()
        self.assertTrue(verify(document.scene()).passed)
        self.assertTrue(verify_vdi(document.scene()).passed)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("json", "svg", "png", "gem"):
                path = Path(directory) / f"drawing.{suffix}"
                output = document.save(path) if suffix == "json" else document.export(path)
                self.assertEqual(output, path)
                self.assertGreater(path.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    document.save(path) if suffix == "json" else document.export(path)
            self.assertIn("Zoe Artline", (Path(directory) / "drawing.svg").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "directory does not exist"):
                document.export(Path(directory) / "missing" / "drawing.svg")
        scene, report = default_document("artline")
        self.assertTrue(verify(scene).passed)
        self.assertFalse(report["legacy_compatibility"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gem_main(["artline", "--output", str(path)]), 0)
                self.assertEqual(gem_main(["artline", "--output", str(path)]), 2)
            self.assertTrue(path.is_file())


def pointer(canvas, x, y, button=1, double=False):
    screen_x, screen_y = canvas.world_to_screen((x, y))
    event = Gdk.EventButton()
    event.type = Gdk.EventType.DOUBLE_BUTTON_PRESS if double else Gdk.EventType.BUTTON_PRESS
    event.button = button
    event.x, event.y = screen_x, screen_y
    event.state = Gdk.ModifierType(0)
    return event


@unittest.skipUnless(HAS_GTK, "native Artline tests require GTK, Cairo, and an X11 DISPLAY")
class ArtlineNativeCase(unittest.TestCase):
    def test_native_tools_buttons_layers_persistence_and_export(self):
        window = ArtlineWindow(ArtlineDocument())
        window.show_all()
        try:
            canvas = window.canvas
            canvas.tool = "rectangle"
            canvas.on_button(canvas, pointer(canvas, 100, 100))
            canvas.on_motion(canvas, pointer(canvas, 240, 220))
            canvas.on_release(canvas, pointer(canvas, 240, 220))
            self.assertEqual(len(window.document.elements), 1)
            canvas.tool = "ellipse"
            canvas.on_button(canvas, pointer(canvas, 300, 100))
            canvas.on_release(canvas, pointer(canvas, 420, 220))
            self.assertEqual(window.document.elements[-1]["type"], "ellipse")
            canvas.tool = "sketch"
            canvas.on_button(canvas, pointer(canvas, 100, 350))
            canvas.on_motion(canvas, pointer(canvas, 180, 300))
            canvas.on_release(canvas, pointer(canvas, 180, 300))
            self.assertTrue(window.document.elements[-1]["smooth"])
            canvas.tool = "quill"
            for x, y in ((500, 400), (560, 320), (640, 400)):
                canvas.on_button(canvas, pointer(canvas, x, y))
                canvas.on_release(canvas, pointer(canvas, x, y))
            canvas.on_button(canvas, pointer(canvas, 640, 400, double=True))
            self.assertEqual(len(window.document.elements[-1]["points"]), 3)
            canvas.tool = "text"
            with mock.patch.object(window, "add_text") as add_text:
                canvas.on_button(canvas, pointer(canvas, 100, 600))
                add_text.assert_called_once()
            rectangle_id = window.document.elements[0]["id"]
            canvas.tool = "selector"
            canvas.on_button(canvas, pointer(canvas, 150, 150))
            self.assertEqual(canvas.selection, [rectangle_id])
            canvas.on_release(canvas, pointer(canvas, 180, 170))
            for actual, expected in zip(window.document.element(rectangle_id)["bounds"], [130, 120, 270, 240]):
                self.assertAlmostEqual(actual, expected)
            window.duplicate_selection()
            self.assertEqual(len(window.document.elements), 5)
            window.flip_selection()
            window.rotate_selection()
            window.group_selection()
            window.ungroup_selection()
            window.restyle_button = window.style_button
            window.style_button.clicked()
            self.assertEqual(window.document.element(canvas.selection[0])["stroke"], canvas.stroke)
            window.undo()
            window.redo()
            window.add_layer()
            self.assertEqual(len(window.document.layers), 2)
            window.layer_view.get_selection().select_path(Gtk.TreePath.new_from_indices([0]))
            self.assertEqual(window.document.current_layer, "layer-1")
            window.grid_button.clicked()
            self.assertFalse(canvas.grid)
            with tempfile.TemporaryDirectory() as directory:
                saved = Path(directory) / "drawing.json"
                exported = Path(directory) / "drawing.svg"
                with mock.patch.object(window, "choose_path", side_effect=[saved, exported]):
                    window.save_button.clicked()
                    window.export_button.clicked()
                self.assertEqual(ArtlineDocument.load(saved).elements, window.document.elements)
                self.assertTrue(exported.is_file())
                window.save_button.clicked()
                self.assertIn("Save failed", window.status.get_text())
                with mock.patch.object(window, "choose_path", return_value=saved), mock.patch.object(window, "confirm_replace", return_value=True):
                    window.open_button.clicked()
                self.assertEqual(window.path, saved)
            with mock.patch.object(window, "confirm_replace", return_value=True):
                window.new_button.clicked()
            self.assertEqual(window.document.elements, [])
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

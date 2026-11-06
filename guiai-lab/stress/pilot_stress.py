from __future__ import annotations

import contextlib
import io
import math
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.pilot import (
    GUIDE_PAGES, cover_document, export_guide_page, guide_page,
    hourglass_weights, packet_spacing, write_guide_pdf,
)
from guiai.gem.pilot_view import main as pilot_main
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


class PilotGuideCase(unittest.TestCase):
    def test_hourglass_conserves_only_normalized_toy_weights(self):
        for count in (2, 8, 64):
            for phase in (0, .25, .5, 1):
                report = hourglass_weights(count, phase)
                self.assertEqual(len(report["weights"]), count)
                self.assertTrue(report["conserved"])
                self.assertTrue(math.isclose(sum(report["weights"]), 1, abs_tol=1e-12))
                self.assertTrue(all(0 <= weight <= 1 for weight in report["weights"]))
                self.assertFalse(report["transformer_modified"])
                self.assertFalse(report["security_validated"])
        self.assertGreater(hourglass_weights(phase=0)["weights"][0], hourglass_weights(phase=0)["weights"][-1])
        self.assertLess(hourglass_weights(phase=1)["weights"][0], hourglass_weights(phase=1)["weights"][-1])
        for count, phase in ((1, .5), (True, .5), (8, -1), (8, 2), (8, True)):
            with self.assertRaises(ValueError):
                hourglass_weights(count, phase)

    def test_synthetic_packet_spacing_is_not_live_or_clock_synchronized(self):
        report = packet_spacing([0, 10, 23, 32, 49, 61, 79, 90])
        self.assertEqual(report["intervals"], [10, 13, 9, 17, 12, 18, 11])
        self.assertTrue(math.isclose(report["mean_interval"], 90 / 7))
        self.assertTrue(math.isclose(report["mean_absolute_interval_deviation"], sum(abs(value - 90 / 7) for value in report["intervals"]) / 7))
        self.assertTrue(report["synthetic"])
        self.assertFalse(report["clock_offset_estimated"])
        self.assertIn("not an RFC 3550", report["scope"])
        for values in ([], [1], [2, 1], [0, float("nan")], [0, True]):
            with self.assertRaises(ValueError):
                packet_spacing(values)

    def test_all_five_original_pages_pass_spatial_and_vdi_verification(self):
        for page in GUIDE_PAGES:
            with self.subTest(page=page):
                scene, report = guide_page(page)
                self.assertEqual(report["page"], page)
                self.assertTrue(report["synthetic"])
                self.assertFalse(report["certified_flight_material"])
                self.assertFalse(report["security_validated"])
                self.assertTrue(verify(scene).passed, verify(scene).text())
                self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
                self.assertEqual(scene.document["id"], "zoe-artline")
        scene, _ = default_document("pilot")
        self.assertTrue(verify(scene).passed)
        self.assertGreater(len(cover_document().elements), 40)

    def test_real_five_page_pdf_exports_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "guide.pdf"
            self.assertEqual(write_guide_pdf(pdf), pdf)
            data = pdf.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertIn(b"/Count 5", data)
            self.assertGreater(len(data), 10000)
            with self.assertRaises(FileExistsError):
                write_guide_pdf(pdf)
            for page, suffix in zip(GUIDE_PAGES, ("svg", "png", "gem", "svg", "png")):
                output = root / f"{page}.{suffix}"
                self.assertEqual(export_guide_page(output, page), output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_guide_page(output, page)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pilot_main(["--output", str(root / "cli.pdf")]), 0)
                self.assertEqual(gem_main(["pilot", "--page", "hourglass", "--output", str(root / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["pilot", "--page", "practice", "--output", str(root / "zoe.svg")]), 0)
                self.assertEqual(pilot_main(["--output", str(root / "cli.pdf")]), 2)
            self.assertIn(b"/Count 5", (root / "cli.pdf").read_bytes())
            self.assertIn("CONSTRAINT BUILDS CREATIVITY", (root / "gem.svg").read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_GTK, "native pilot tests require GTK, Cairo, and an X11 DISPLAY")
class PilotNativeCase(unittest.TestCase):
    def test_atlas_opens_editable_original_cover(self):
        hub = AtlasWindow("unified")
        window = None
        try:
            window = hub.open_builtin("pilot")
            self.assertIn("Practice Navigator", window.get_title())
            self.assertGreater(len(window.document.elements), 40)
            self.assertTrue(verify(window.document.scene()).passed)
        finally:
            if window is not None:
                window.destroy()
            hub.destroy()


if __name__ == "__main__":
    unittest.main()

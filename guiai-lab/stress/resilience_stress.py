from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.resilience import (
    SECTORS, SignalTrace, classify_trace, clock_candidates, demo_traces,
    export_resilience, resilience_scene,
)
from guiai.gem.resilience_view import main as resilience_main
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


class ResilienceModelCase(unittest.TestCase):
    def test_all_sixteen_sectors_have_valid_sources_and_bounded_examples(self):
        self.assertEqual(len(SECTORS), 16)
        for identifier, sector in SECTORS.items():
            with self.subTest(sector=identifier):
                self.assertTrue(sector["name"])
                self.assertTrue(sector["url"].startswith("https://www.cisa.gov/"))
                self.assertTrue(sector["why"])
                self.assertTrue(sector["depends_on"])
                self.assertLess(len(sector["depends_on"]), 8)
                for dependency in sector["depends_on"]:
                    self.assertIn(dependency, SECTORS)
                    self.assertNotEqual(dependency, identifier)
        self.assertEqual(SECTORS["energy"]["depends_on"], ["communications", "transportation", "water", "critical-manufacturing"])
        self.assertEqual(SECTORS["critical-manufacturing"]["depends_on"], ["transportation", "energy", "chemical", "water"])
        self.assertIn("safe drinking water", SECTORS["water"]["why"].lower())

    def test_clock_corroboration_ambiguity_and_unmapped_boundaries(self):
        traces = demo_traces()
        self.assertEqual(classify_trace(traces["host80"])["status"], "corroborated")
        self.assertEqual(classify_trace(traces["host80"])["candidates"], ["endeavour_tb.clk"])
        for identifier in ("host40", "amac40"):
            result = classify_trace(traces[identifier])
            self.assertEqual(result["status"], "ambiguous")
            self.assertEqual(len(result["candidates"]), 2)
            self.assertEqual(len(clock_candidates(traces[identifier])), 2)
            self.assertFalse(result["source_signature_is_identity"])
            self.assertFalse(result["period_or_similarity_is_sufficient"])
        self.assertEqual(classify_trace(traces["unmapped"])["status"], "unmapped")
        with self.assertRaises(ValueError):
            clock_candidates(None)
        events = list(traces["host80"].events)
        events[0] = (events[0][0], 0)
        self.assertEqual(classify_trace(SignalTrace("changed-initial", tuple(events)))["status"], "unmapped")
        events = list(traces["host80"].events)
        events[4] = (events[4][0] + 1, events[4][1])
        self.assertEqual(classify_trace(SignalTrace("changed-interval", tuple(events)))["status"], "unmapped")
        for invalid in (
            SignalTrace("valid", tuple((index * 6250, 1 - index % 2) for index in range(32))),
        ):
            self.assertEqual(len(invalid.events), 32)
        with self.assertRaises(ValueError):
            SignalTrace("short", ((0, 1),))
        with self.assertRaises(ValueError):
            SignalTrace("duplicate-time", tuple((0, 1) for _ in range(32)))
        with self.assertRaises(ValueError):
            SignalTrace("non-binary", tuple((index, 2) for index in range(32)))
        with self.assertRaises(ValueError):
            SignalTrace("bool-payload", tuple((index, False) for index in range(32)))
        with self.assertRaises(ValueError):
            SignalTrace("", tuple((index, 1) for index in range(32)))

    def test_scenes_exports_and_cli_preserve_scope(self):
        for sector in SECTORS:
            for trace in ("host80", "host40", "unmapped"):
                scene, report = resilience_scene(sector, trace)
                self.assertTrue(verify(scene).passed, verify(scene).text())
                self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
                self.assertEqual(report["sector"], sector)
                self.assertFalse(report["dependencies_exhaustive"])
                self.assertFalse(report["live_monitoring"])
                self.assertFalse(report["risk_score"])
                self.assertFalse(report["automatic_action"])
                self.assertEqual(report["cern_reference"]["events_processed"], 10759544)
        scene, _ = default_document("resilience")
        self.assertTrue(verify(scene).passed)
        with self.assertRaises(ValueError):
            resilience_scene("unknown")
        with self.assertRaises(ValueError):
            resilience_scene(trace_id="unknown")
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("svg", "png", "gem"):
                output = Path(directory) / f"resilience.{suffix}"
                self.assertEqual(export_resilience(output, "water", "host40"), output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_resilience(output, "water", "host40")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(resilience_main(["--sector", "water", "--trace", "host40", "--output", str(Path(directory) / "direct.svg")]), 0)
                self.assertEqual(gem_main(["resilience", "--output", str(Path(directory) / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["resilience", "--output", str(Path(directory) / "zoe.svg")]), 0)
            self.assertIn("Zoe Resilience Atlas", (Path(directory) / "direct.svg").read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_GTK, "native resilience tests require GTK, Cairo, and an X11 DISPLAY")
class ResilienceNativeCase(unittest.TestCase):
    def test_native_sector_trace_selection_and_export(self):
        window = AtlasWindow("resilience")
        try:
            self.assertEqual(window.module, "resilience")
            self.assertEqual(window.report["trace"]["status"], "corroborated")
            window.controls["sector"].set_active_id("water")
            window.controls["trace"].set_active_id("host40")
            self.assertEqual(window.report["sector"], "water")
            self.assertEqual(window.report["trace"]["status"], "ambiguous")
            self.assertEqual(len(window.report["trace"]["candidates"]), 2)
            self.assertIn("No live monitoring", window.summary.get_text())
            with tempfile.TemporaryDirectory() as directory:
                output = window.export_current(Path(directory) / "native.svg")
                self.assertTrue(output.is_file())
                self.assertIn("Water and Wastewater Systems", output.read_text(encoding="utf-8"))
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

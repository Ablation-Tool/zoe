from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main
from guiai.gem.waveform import (
    WaveformReplay, _digest, demo_replay, demo_vcd_text, export_waveform,
    waveform_scene,
)
from guiai.gem.waveform_view import main as waveform_main


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "guiai-lab/docs/examples/endeavour-clocks.vcd"
LEGACY = Path("/media/cowboy/research/CERN/analysis/wdb/legacy-events.jsonl")
WDB = Path("/media/cowboy/research/CERN/analysis/wdb/endeavour_tb_behav.wdb")
LEGACY_HASH = "a4398456aa92f47f9344c9b2b2325086830fe4f7d28a585c7873c95472e514dc"
WDB_HASH = "ecbb1b1ab78f71991a8b750d8910e0e12cbe78b0e38aa98c26184dd0f974f87d"


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


def write_normalized(path, document):
    document["digest"] = _digest({key: value for key, value in document.items() if key != "digest"})
    path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


class WaveformModelCase(unittest.TestCase):
    def test_demo_signatures_and_geometry(self):
        replay = demo_replay()
        self.assertEqual(len(replay.events), 200)
        self.assertFalse(replay.truncated)
        self.assertEqual(str(replay.timescale_ps), "1")
        self.assertEqual(replay.source["name_mapping"], "declared_vcd_symbols")
        self.assertEqual(len(replay.source["sha256"]), 64)
        report = replay.analyze()
        self.assertEqual(report["status_counts"], {"corroborated": 1, "ambiguous": 2, "unmapped": 1})
        statuses = {signal["name"]: signal["status"] for signal in report["signals"]}
        self.assertEqual(statuses, {
            "demo.host80": "corroborated",
            "demo.host40": "ambiguous",
            "demo.amac40": "ambiguous",
            "demo.unmapped": "unmapped",
        })
        first, second = (next(signal for signal in report["signals"] if signal["identifier"] == identifier) for identifier in ("c1", "c2"))
        self.assertEqual(first["period_ps"], second["period_ps"])
        self.assertNotEqual(first["status"], "corroborated")
        self.assertNotEqual(second["status"], "corroborated")
        self.assertFalse(report["hardware_accessed"])
        self.assertFalse(report["name_mapping_is_identity"])
        self.assertTrue(all(not signal["identity_proven"] for signal in report["signals"]))
        for selected in (None, "c0", "u0"):
            scene, _ = waveform_scene(replay, selected)
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        scene, _ = default_document("waveform")
        self.assertTrue(verify(scene).passed)
        with self.assertRaisesRegex(ValueError, "unknown waveform signal"):
            waveform_scene(replay, "missing")

    def test_scoped_vectors_reals_and_decimal_timescale(self):
        replay = WaveformReplay.from_vcd_text("""$timescale 0.5ps $end
$scope module top $end
$scope module child $end
$var wire 4 ! bus[3:0] $end
$var real 1 % analog $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b01xZ !
r2.5 %
#2
b10x0 !
r-0.125 %
""")
        self.assertEqual(str(replay.timescale_ps), "0.5")
        self.assertEqual([signal["name"] for signal in replay.signals], ["top.child.bus[3:0]", "top.child.analog"])
        self.assertEqual([event["time"] for event in replay.events], [0, 0, 1, 1])
        self.assertEqual([event["value"] for event in replay.events], ["01xz", "2.5", "10x0", "-0.125"])
        self.assertEqual(WaveformReplay.from_vcd_text(demo_vcd_text().replace("1ps", "10ns", 1)).timescale_ps, 10000)

    def test_strict_vcd_rejections_and_bounds(self):
        base = demo_vcd_text()
        invalid = (
            "",
            base.replace("1ps", "1moon", 1),
            base.replace("1ps", "0ps", 1),
            base.replace("1ps", "NaNps", 1),
            base.replace("1ps", "Infinityps", 1),
            base.replace("$var wire 1 u0 unmapped $end", "$var wire 1 u0 unmapped $end\n$var wire 1 u0 other $end"),
            base + "0missing\n",
            base.replace("#12500", "#1", 1),
            base.replace("#6250", "#0.5", 1),
            base.replace("#0", "#Infinity", 1),
            base.replace("$upscope $end", "$upscope $end\n$upscope $end", 1),
            base.split("$enddefinitions $end")[0],
            "$timescale 1ps $end\n$enddefinitions $end\n",
            "$timescale 1ps $end\n$var wire 1 a a $end\n$enddefinitions $end\n#0\n0a\n#1\nr1e999 a\n",
            "$timescale 1ps $end\n$var wire 1 a a $end\n$enddefinitions $end\n#0\nb01u a\n",
            "$timescale 1ps $end\n$var wire 1 a a $end\n$enddefinitions $end\n0a\n",
        )
        for text in invalid:
            with self.subTest(text=text[:90]), self.assertRaises(ValueError):
                WaveformReplay.from_vcd_text(text)
        for limit in (0, 65537, True, 1.5):
            with self.assertRaises(ValueError):
                WaveformReplay.from_vcd_text(base, max_events=limit)
        limited = WaveformReplay.from_vcd_text(base, max_events=7)
        self.assertEqual(len(limited.events), 7)
        self.assertTrue(limited.truncated)

    def test_single_event_and_unused_signal(self):
        text = """$timescale 1ps $end
$var wire 1 a a $end
$var wire 1 unused unused $end
$enddefinitions $end
#0
0a
"""
        replay = WaveformReplay.from_vcd_text(text)
        scene, report = waveform_scene(replay, "a")
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertEqual(report["signals"][0]["event_count"], 1)
        with self.assertRaisesRegex(ValueError, "no retained events"):
            waveform_scene(replay, "unused")

    def test_normalized_roundtrip_tamper_and_no_overwrite(self):
        replay = demo_replay()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            self.assertEqual(replay.save(path), path)
            self.assertEqual(WaveformReplay.load(path).document(), replay.document())
            with self.assertRaises(FileExistsError):
                replay.save(path)
            with self.assertRaises(ValueError):
                replay.save(Path(directory) / "replay.txt")
            with self.assertRaises(ValueError):
                replay.save(Path(directory) / "missing/replay.json")
            tampered = replay.document()
            tampered["events"][0]["value"] = "0"
            path.write_text(json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                WaveformReplay.load(path)
            for field, value in (("size", True), ("sha256", "0" * 63), ("path", "")):
                invalid = replay.document()
                invalid["source"][field] = value
                write_normalized(path, invalid)
                with self.assertRaises(ValueError):
                    WaveformReplay.load(path)
            invalid = replay.document()
            invalid["timescale_ps"] = "Infinity"
            write_normalized(path, invalid)
            with self.assertRaisesRegex(ValueError, "timescale"):
                WaveformReplay.load(path)
            invalid = replay.document()
            invalid["events"][0]["signal"] = "unknown"
            write_normalized(path, invalid)
            with self.assertRaisesRegex(ValueError, "unknown signal"):
                WaveformReplay.load(path)

    def test_file_example_exports_and_command_forwarding(self):
        self.assertTrue(EXAMPLE.is_file())
        replay = WaveformReplay.from_vcd(EXAMPLE)
        self.assertEqual(len(replay.events), 200)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("svg", "png", "gem"):
                output = Path(directory) / f"waveform.{suffix}"
                self.assertEqual(export_waveform(replay, output), output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_waveform(replay, output)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(waveform_main([str(EXAMPLE), "--signal", "c1", "--output", str(Path(directory) / "direct.json")]), 0)
                self.assertEqual(waveform_main([str(Path(directory) / "direct.json"), "--output", str(Path(directory) / "direct.svg")]), 0)
                self.assertEqual(gem_main(["waveform", "--output", str(Path(directory) / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["waveform", "--output", str(Path(directory) / "zoe.svg")]), 0)
            self.assertEqual(WaveformReplay.load(Path(directory) / "direct.json").source["sha256"], replay.source["sha256"])
            for name in ("direct.json", "direct.svg", "gem.svg", "zoe.svg"):
                self.assertGreater((Path(directory) / name).stat().st_size, 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(waveform_main(["--max-events", "0", "--output", str(Path(directory) / "invalid.svg")]), 2)
            self.assertFalse((Path(directory) / "invalid.svg").exists())


@unittest.skipUnless(LEGACY.is_file(), "optional local CERN legacy event evidence is unavailable")
class LegacyEvidenceCase(unittest.TestCase):
    def test_bounded_storage_identity_replay(self):
        replay = WaveformReplay.from_legacy_jsonl(LEGACY)
        report = replay.analyze()
        self.assertEqual(len(replay.events), 16)
        self.assertEqual(len(replay.signals), 9)
        self.assertFalse(replay.truncated)
        self.assertEqual(replay.source["sha256"], LEGACY_HASH)
        self.assertEqual(replay.source["size"], 2740)
        self.assertEqual(replay.source["name_mapping"], "storage_ids_only")
        self.assertTrue(all(signal["kind"] == "legacy" for signal in replay.signals))
        self.assertEqual(report["status_counts"]["unmapped"], 9)
        self.assertTrue(all(signal["name_source"] == "storage ID only" for signal in report["signals"]))


@unittest.skipUnless(WDB.is_file() and (importlib.util.find_spec("ablation") is not None or os.environ.get("ZOE_ABLATION_ROOT")), "optional WDB evidence and Ablation decoder are unavailable")
class WdbEvidenceCase(unittest.TestCase):
    def test_real_wdb_bound_and_signal_scenes(self):
        replay = WaveformReplay.from_wdb(WDB, max_events=256)
        report = replay.analyze()
        self.assertEqual(len(replay.events), 256)
        self.assertTrue(replay.truncated)
        self.assertEqual(replay.source["sha256"], WDB_HASH)
        self.assertEqual(replay.source["size"], 35064902)
        self.assertEqual(report["status_counts"], {"corroborated": 1, "ambiguous": 2, "unmapped": 6})
        self.assertIn("0/0x4B0", {signal["identifier"] for signal in replay.signals})
        for signal in report["signals"]:
            with self.subTest(signal=signal["identifier"]):
                scene, _ = waveform_scene(replay, signal["identifier"])
                self.assertTrue(verify(scene).passed, verify(scene).text())
                self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())


@unittest.skipUnless(HAS_GTK, "native waveform tests require GTK, Cairo, and an X11 DISPLAY")
class WaveformNativeCase(unittest.TestCase):
    def test_selection_explicit_load_error_preservation_and_export(self):
        window = AtlasWindow("waveform")
        try:
            original = window.waveform_replay
            window.controls["waveform_signal"].set_active_id("u0")
            self.assertIn("1 corroborated / 2 ambiguous / 1 unmapped", window.summary.get_text())
            window.controls["waveform_path"].set_text(str(EXAMPLE))
            self.assertIs(window.waveform_replay, original)
            window.load_waveform()
            self.assertEqual(window.waveform_replay.source["path"], str(EXAMPLE))
            loaded = window.waveform_replay
            previous_scene = window.scene
            window.controls["waveform_path"].set_text(str(EXAMPLE) + ".missing")
            window.load_waveform()
            self.assertIs(window.waveform_replay, loaded)
            self.assertIs(window.scene, previous_scene)
            self.assertIn("Waveform load failed", window.summary.get_text())
            window.refresh()
            with tempfile.TemporaryDirectory() as directory:
                output = window.export_current(Path(directory) / "waveform.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

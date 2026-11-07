from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from guiai.gem.atlas import ATLAS_MODULES, default_document
from guiai.gem.cern_corpus import load_corpus, scan_corpus, write_corpus
from guiai.gem.cern_cli import main as cern_main
from guiai.gem.cern_repair import RepairRecord, repair_report, repair_scene
from guiai.gem.cern_wupper import LEGACY_BLOCK, repair_wupper_cli, repair_wupper_file
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.runner import verify_vdi


class CernCorpusCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "corpus"
        self.root.mkdir()
        (self.root / "nested").mkdir()
        (self.root / "a.py").write_text("print('same')\n", encoding="utf-8")
        (self.root / "nested" / "b.py").write_text("print('same')\n", encoding="utf-8")
        os.link(self.root / "a.py", self.root / "alias.py")
        (self.root / ".env").write_text("policy-excluded", encoding="utf-8")
        (self.root / "image.bit").write_bytes(b"\x00\xff\x10")
        (self.root / "link").symlink_to("a.py")
        (self.root / "external").symlink_to(self.base)

    def tearDown(self):
        self.temporary.cleanup()

    def scan(self, workers=2):
        return scan_corpus(self.root, output=self.root / "out", workers=workers)

    def test_full_identity_dispositions_and_tamper_checked_reload(self):
        records, summary = self.scan()
        self.assertEqual(summary["artifact_count"], 8)
        self.assertEqual(summary["file_count"], 7)
        self.assertEqual(summary["directory_count"], 1)
        self.assertEqual(summary["regular_file_count"], 5)
        self.assertEqual(summary["coverage"]["hashed"], 4)
        self.assertEqual(summary["coverage"]["policy_exclusions"], 1)
        self.assertEqual(summary["coverage"]["symlinks"], 2)
        self.assertEqual(summary["unique_content_count"], 2)
        self.assertEqual(summary["duplicates"]["groups"], 1)
        self.assertEqual(summary["duplicates"]["alias_paths"], 2)
        self.assertTrue(summary["coverage"]["complete_without_errors"])
        self.assertEqual(summary["families"]["python"], 3)
        self.assertEqual(summary["families"]["fpga_image"], 1)
        link = next(record for record in records if record.path == "external")
        self.assertTrue(link.link_outside_root)
        secret = next(record for record in records if record.path == ".env")
        self.assertIsNone(secret.sha256)
        write_corpus(records, summary, self.root / "out")
        loaded, loaded_summary = load_corpus(self.root / "out")
        self.assertEqual(len(loaded), 8)
        self.assertEqual(len(loaded_summary["manifest_sha256"]), 64)
        with (self.root / "out" / "manifest.jsonl").open("ab") as stream:
            stream.write(b"{}\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            load_corpus(self.root / "out")
        with self.assertRaises(FileExistsError):
            write_corpus(records, summary, self.root / "out")

    def test_changed_file_is_an_explicit_error_not_a_pass(self):
        import guiai.gem.cern_corpus as corpus

        original = corpus._sha256

        def mutate(path, expected):
            path.write_text("changed while hashing", encoding="utf-8")
            return original(path, expected)

        with patch("guiai.gem.cern_corpus._sha256", side_effect=mutate):
            records, summary = scan_corpus(self.root, workers=1)
        self.assertFalse(summary["coverage"]["complete_without_errors"])
        self.assertGreaterEqual(summary["coverage"]["errors"], 1)
        self.assertTrue(any(record.status == "error" for record in records))

    def test_cli_scan_report_chart_and_fresh_verification(self):
        output = self.root / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cern_main(["scan", "--cern-root", str(self.root), "--output", str(output), "--workers", "2"]), 0)
            report_path = self.base / "atlas.json"
            self.assertEqual(cern_main(["report", "--cern-root", str(self.root), "--output", str(report_path)]), 0)
            svg = self.base / "atlas.svg"
            self.assertEqual(cern_main(["chart", "--cern-root", str(self.root), "--output", str(svg)]), 0)
            verification = self.base / "verification.json"
            self.assertEqual(cern_main(["verify", "--cern-root", str(self.root), "--input", str(output), "--output", str(verification)]), 0)
        self.assertIn("<svg", svg.read_text(encoding="utf-8"))
        self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["passed"])
        (self.root / "a.py").write_text("print('changed')\n", encoding="utf-8")
        changed = self.base / "changed.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cern_main(["verify", "--cern-root", str(self.root), "--input", str(output), "--output", str(changed)]), 1)
        self.assertIn("a.py", json.loads(changed.read_text(encoding="utf-8"))["changed"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cern_main(["chart", "--cern-root", str(self.root), "--output", str(svg)]), 2)

    def test_repair_scene_is_deterministic_and_vdi_verified(self):
        _, corpus = self.scan()
        record = RepairRecord(
            identifier="TEST-REPAIR-001",
            title="Boundary repair",
            severity="MEDIUM",
            family="hdl",
            source="fixture.v:1",
            original_behavior="zero -> two bytes",
            desired_behavior="zero -> no bytes",
            evidence_level="CONFIRMED_DYNAMIC",
            repair_status="reproduced",
            tests_total=10,
            tests_passed=10,
        )
        report = repair_report([record], corpus)
        first, first_report = repair_scene(report)
        second, _ = repair_scene(report)
        self.assertEqual(first.digest(), second.digest())
        self.assertTrue(verify(first).passed, verify(first).text())
        self.assertTrue(verify_vdi(first).passed, verify_vdi(first).text())
        self.assertEqual(first_report["status_counts"], {"reproduced": 1})
        self.assertEqual(first_report["tests_passed"], 10)
        self.assertFalse(first_report["records"][0]["executed"])
        record.repair_status = "integrated"
        with self.assertRaises(ValueError):
            RepairRecord(
                identifier="INVALID", title="bad", severity="MEDIUM", family="hdl",
                source="fixture", original_behavior="bad", desired_behavior="good",
                evidence_level="none", repair_status="integrated", tests_total=0,
            ).validate()

    def test_wupper_safe_yaml_repair_and_no_side_effect(self):
        source = self.root / "cli.py"
        source.write_text("def load_config(f):\n" + LEGACY_BLOCK, encoding="utf-8")
        repaired = repair_wupper_cli("def load_config(f):\n" + LEGACY_BLOCK)
        self.assertIn("yaml.safe_load", repaired)
        self.assertNotIn("yaml.load", repaired)
        output = self.root / "repaired.py"
        report = repair_wupper_file(source, output)
        self.assertEqual(report["tests_total"], 6)
        self.assertEqual(report["tests_passed"], 6)
        self.assertEqual(report["status"], "regression_verified")
        self.assertFalse(report["original_artifacts_modified"])
        self.assertEqual(output.read_text(encoding="utf-8"), repaired)
        with self.assertRaises(FileExistsError):
            repair_wupper_file(source, output)

    def test_atlas_and_existing_gem_entrypoints(self):
        self.assertIn("cern", ATLAS_MODULES)
        scene, _ = default_document("cern", cern_root=self.root)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        with tempfile.TemporaryDirectory() as directory:
            direct = Path(directory) / "direct.svg"
            atlas = Path(directory) / "atlas.gem"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gem_main(["cern", "chart", "--cern-root", str(self.root), "--output", str(direct)]), 0)
                self.assertEqual(gem_main(["zoe", "--module", "cern", "--output", str(atlas)]), 0)
            self.assertGreater(direct.stat().st_size, 0)
            self.assertGreater(atlas.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

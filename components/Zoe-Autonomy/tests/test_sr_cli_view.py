"""Tests for the unified `zoe reasoning` CLI view (Architectures 1-9 + Digital Research GEM)."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from guiai.gem import reasoning_view, unified_cli


class SharedReasoningCliViewTests(unittest.TestCase):
    def _run_capture(self, argv: list[str], *, via_unified: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = unified_cli.main(["reasoning", *argv]) if via_unified else reasoning_view.main(argv)
        return int(rc), buf.getvalue()

    def test_status_via_unified_cli_reports_all_nine_architectures(self) -> None:
        rc, out = self._run_capture(["status", "--json"], via_unified=True)
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertEqual(doc["architectures"], 9)
        self.assertGreaterEqual(doc["submodule_count"], 12)
        self.assertIn("orchestrator", doc["submodules"])
        self.assertIn("gem_aes_vdi", doc["submodules"])
        self.assertEqual(doc["external_actions"], 0)
        self.assertFalse(doc["sentience_claimed"])
        self.assertFalse(doc["l5_agi_qualified"])
        self.assertFalse(doc["zoe_clone_claimed"])

    def test_gem_subcommand_verifies_cga_vga_ndc_and_rsc(self) -> None:
        rc, out = self._run_capture(["gem", "--theme", "zoe-viewmax3", "--json"])
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertTrue(doc["passed"])
        self.assertTrue(doc["visual_evidence_only"])
        self.assertEqual(doc["external_actions"], 0)
        self.assertEqual(doc["profiles_passed"], {"cga": True, "vga": True, "ndc": True})
        self.assertTrue(doc["metafile_sha256"])
        self.assertTrue(doc["rsc_sha256"])

    def test_run_subcommand_executes_composed_pipeline_offline_and_writes_gem_out(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe-sr-cli-test-") as td:
            gem_out = Path(td) / "gem_out"
            rc, out = self._run_capture(
                ["run", "--prompt", "Verify Kloster Theorem 13 and 15 invariants", "--gem-out", str(gem_out), "--json"]
            )
            self.assertEqual(rc, 0)
            doc = json.loads(out)
            self.assertEqual(doc["transport_mode"], "offline")
            self.assertTrue(doc["arch7_sympy_passed"])
            self.assertTrue(doc["arch7_z3_passed"])
            self.assertTrue(doc["gem_desktop_verified"])
            self.assertEqual(doc["external_actions"], 0)
            self.assertFalse(doc["sentience_claimed"])
            self.assertTrue(gem_out.is_dir())

    def test_verify_subcommand_passes_end_to_end(self) -> None:
        rc, out = self._run_capture(["verify", "--json"])
        self.assertEqual(rc, 0)
        doc = json.loads(out)
        self.assertTrue(doc["passed"])
        self.assertEqual(doc["constitutional"]["external_actions"], 0)
        self.assertFalse(doc["constitutional"]["sentience_claimed"])


if __name__ == "__main__":
    unittest.main()

"""Tests for Zoe-GEM OS ecosystem suite, loopback guards, `zoe gemos` CLI, and verifier."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from guiai.gem import gemos_view, unified_cli
from guiai.gem.zoe_beta_release import build_beta_release_manifest
from guiai.gem.zoe_gem_os.zoe_phone_codex_sync import assert_loopback_url
import verify_zoe_gem_os_suite


class ZoeGemOsSuiteTests(unittest.TestCase):
    def _run_cli(self, argv: list[str], *, via_unified: bool = False) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = unified_cli.main(["gemos", *argv]) if via_unified else gemos_view.main(argv)
        return int(rc), buf.getvalue()

    def test_loopback_url_guard_enforces_constitution_art_vi_5(self) -> None:
        self.assertEqual(assert_loopback_url("http://127.0.0.1:8774/"), "http://127.0.0.1:8774")
        self.assertEqual(assert_loopback_url("http://localhost:8774"), "http://localhost:8774")
        self.assertEqual(assert_loopback_url("http://[::1]:8774"), "http://[::1]:8774")
        for bad in (
            "http://example.com:8774",
            "https://169.254.169.254/latest",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    assert_loopback_url(bad)

    def test_beta_release_manifest_rejects_non_loopback_rome_url(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe-beta-ssrf-") as td:
            with self.assertRaises(ValueError):
                build_beta_release_manifest(REPO_ROOT, out_dir=Path(td), rome_url="http://evil.invalid:8774")

    def test_unified_cli_gemos_status_pixel_themes_realms_braille(self) -> None:
        rc, out = self._run_cli(["status", "--json"], via_unified=True)
        self.assertEqual(rc, 0)
        st = json.loads(out)
        self.assertEqual(st["pixel_devices"], 9)
        self.assertEqual(st["gem_eras"], 8)
        self.assertEqual(st["viewmax_schemes"], 10)
        self.assertEqual(st["zoeverse_realms"], 9)
        self.assertEqual(st["sisters_count"], 9)
        self.assertEqual(st["external_actions"], 0)
        self.assertFalse(st["auto_flash_allowed"])
        self.assertFalse(st["sentience_claimed"])

        rc, out = self._run_cli(["pixel", "--device", "panther", "--json"])
        self.assertEqual(rc, 0)
        px = json.loads(out)
        self.assertTrue(px["ok"])
        self.assertTrue(px["deterministic"])
        self.assertFalse(px["auto_flash_allowed"])

        rc, out = self._run_cli(["themes", "--scheme", "zoe-viewmax3", "--json"])
        self.assertEqual(rc, 0)
        th = json.loads(out)
        self.assertEqual(th["slot"], 1)
        self.assertIn("[ViewMAX]", th["ini"])

        rc, out = self._run_cli(["realms", "--realm", "stem", "--json"])
        self.assertEqual(rc, 0)
        rl = json.loads(out)
        self.assertEqual(rl["key"], "stem")
        self.assertGreater(len(rl["vista"]), 0)

        rc, out = self._run_cli(["braille", "flower", "--cols", "28"])
        self.assertEqual(rc, 0)
        self.assertTrue(any(0x2800 <= ord(ch) <= 0x28FF for ch in out))

    def test_standalone_8_check_verifier_passes_offline(self) -> None:
        report = verify_zoe_gem_os_suite.run_suite(write_report=False)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["checks_passed"], 8)
        self.assertEqual(report["checks_total"], 8)
        self.assertEqual(report["constitutional"]["external_actions"], 0)
        self.assertFalse(report["constitutional"]["sentience_claimed"])


if __name__ == "__main__":
    unittest.main()

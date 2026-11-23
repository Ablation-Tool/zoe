from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from guiai.gem.cli import R3_COMMAND_SPECS, main as gem_main
from guiai.gem.code_elegance_analyzer import analyze_python_source, audit_zoe_monorepo_elegance
from guiai.gem.operating_environment import EXTENDED_LAYERS
from guiai.gem.unified_cli import main as unified_main
from zoe_autonomy.chat import DOCUMENT_PATHS, HELP, ZoeChat
from zoe_autonomy.cli import main as autonomy_main


REPO_ROOT = Path(__file__).resolve().parents[3]
R3_COMMANDS = ("theorem13", "theorem14", "theorem15", "botanical", "optics", "proof-packet", "c28")

_DOMAIN_TOKENS = {
    "theorem13": ("theorem 13", "zoe-kloster-theorem13-stopping"),
    "theorem14": ("theorem 14", "zoe-kloster-theorem14"),
    "theorem15": ("theorem 15", "zoe-kloster-theorem15"),
    "botanical": ("botanical", "zoe-botanical-atlas-c27"),
    "optics": ("optics", "scheimpflug", "isovist"),
    "proof-packet": ("proof packet", "zoe-metacognition-proof-packet"),
    "c28": ("c28", "zoe-pharmacophore-spatial-c28"),
}

_CONSTITUTIONAL_FLAGS = (
    "sentience_claimed=False",
    "l5_agi_qualified=False",
    "zoe_clone_claimed=False",
    "clinical_action_authorized=False",
    "cure_claim=False",
    "cloud_tokens_used=0",
)


def _assert_r3_output(testcase: unittest.TestCase, cmd: str, output: str) -> None:
    low = output.lower()
    testcase.assertTrue(any(tok in low for tok in _DOMAIN_TOKENS[cmd]), f"{cmd} missing domain token: {output!r}")
    testcase.assertIn("contract=", low)
    testcase.assertIn("all_verified=", low)
    testcase.assertIn("sha256=", low)
    for flag in _CONSTITUTIONAL_FLAGS:
        testcase.assertIn(flag, output, f"{cmd} missing constitutional flag {flag}")


class GemCliR3Tests(unittest.TestCase):
    def test_all_7_r3_commands_exit_0_and_emit_distinct_telemetry(self):
        outputs: list[str] = []
        for cmd in R3_COMMANDS:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = gem_main([cmd, "--zoe-root", str(REPO_ROOT)])
            self.assertEqual(rc, 0, f"gem {cmd} failed with rc={rc}")
            out = buf.getvalue().strip()
            _assert_r3_output(self, cmd, out)
            outputs.append(out)
        self.assertEqual(len(set(outputs)), 7)

    def test_json_output_and_html_exports_with_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="zoe-gem-r3-") as tmp:
            root = Path(tmp)
            json_out = root / "t13.json"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = gem_main(["theorem13", "--zoe-root", str(REPO_ROOT), "--json", "--output", str(json_out)])
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue())
            self.assertEqual(doc["contract"], "zoe-kloster-theorem13-stopping/v1")
            self.assertTrue(json_out.is_file())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gem_main(["theorem13", "--zoe-root", str(REPO_ROOT), "--output", str(json_out)]), 2)

            for cmd in ("botanical", "optics", "proof-packet"):
                html_out = root / f"{cmd}.html"
                with contextlib.redirect_stdout(io.StringIO()):
                    rc_html = gem_main([cmd, "--zoe-root", str(REPO_ROOT), "--html", str(html_out)])
                self.assertEqual(rc_html, 0)
                self.assertTrue(html_out.is_file())
                self.assertGreater(html_out.stat().st_size, 1000)

    def test_unknown_command_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                gem_main(["definitely-unknown-command"])
        self.assertEqual(exc.exception.code, 2)


class UnifiedCliR3Tests(unittest.TestCase):
    def test_all_7_r3_commands_via_unified_cli(self):
        outputs: list[str] = []
        for cmd in R3_COMMANDS:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = unified_main([cmd, "--zoe-root", str(REPO_ROOT)])
            self.assertEqual(rc, 0, f"zoe {cmd} failed with rc={rc}")
            out = buf.getvalue().strip()
            _assert_r3_output(self, cmd, out)
            outputs.append(out)
        self.assertEqual(len(set(outputs)), 7)

    def test_list_reports_17_engines_and_unknown_exits_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = unified_main(["list"])
        self.assertEqual(rc, 0)
        rows = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(rows), 17)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                unified_main(["definitely-unknown-command"])
        self.assertEqual(exc.exception.code, 2)


class ZoeChatR3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zoe-chat-r3-")
        self.state = Path(self.tmp.name) / "state"
        self.chat = ZoeChat(REPO_ROOT, self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_7_r3_commands_and_slash_prefixes(self):
        replies: list[str] = []
        for cmd in R3_COMMANDS:
            keep, reply = self.chat.handle(cmd)
            self.assertTrue(keep)
            self.assertNotIn("I could not complete that safely", reply)
            self.assertNotIn("do not have enough indexed evidence", reply)
            _assert_r3_output(self, cmd, reply)
            replies.append(reply.strip())

            keep_slash, reply_slash = self.chat.handle(f"/{cmd}")
            self.assertTrue(keep_slash)
            _assert_r3_output(self, cmd, reply_slash)
        self.assertEqual(len(set(replies)), 7)

    def test_r3_json_html_and_stop_behavior(self):
        _, json_reply = self.chat.handle("c28 json")
        parsed = json.loads(json_reply)
        self.assertEqual(parsed["contract"], "zoe-pharmacophore-spatial-c28/v1")

        html_path = Path(self.tmp.name) / "optics.html"
        _, html_reply = self.chat.handle(f"optics html {html_path}")
        self.assertIn("Exported interactive HTML", html_reply)
        self.assertTrue(html_path.is_file())

        _, stop_reply = self.chat.handle("stop")
        self.assertIn("stopped", stop_reply.lower())
        for cmd in R3_COMMANDS:
            _, after_stop = self.chat.handle(cmd)
            _assert_r3_output(self, cmd, after_stop)
        _, blocked_html = self.chat.handle(f"botanical html {Path(self.tmp.name) / 'blocked.html'}")
        self.assertIn("stopped", blocked_html.lower())

    def test_help_document_paths_and_legacy_invariants(self):
        for cmd in R3_COMMANDS:
            self.assertIn(cmd, HELP)
            self.assertIn(cmd, R3_COMMAND_SPECS)
        self.assertIn("docs/PROOF-PACKET.md", DOCUMENT_PATHS)
        for rel in DOCUMENT_PATHS:
            self.assertTrue((REPO_ROOT / rel).is_file(), f"Missing DOCUMENT_PATHS entry: {rel}")

        _, status_reply = self.chat.handle("status")
        self.assertIn("monitor=False · notebook=False", status_reply)
        _, gem_reply = self.chat.handle("gem status")
        self.assertIn("17 components · 36 layers", gem_reply)
        self.assertFalse((self.state / "events.jsonl").exists())
        self.assertFalse((self.state / "metacognition.json").exists())


class AutonomyCliRefactorTests(unittest.TestCase):
    def test_chat_dispatch_and_unknown_exit_2(self):
        with tempfile.TemporaryDirectory(prefix="zoe-cli-r3-") as tmp:
            state = Path(tmp) / "state"
            buf1 = io.StringIO()
            with contextlib.redirect_stdout(buf1):
                rc1 = autonomy_main(["--zoe-root", str(REPO_ROOT), "chat", "--state", str(state), "--command", "gem status"])
            self.assertEqual(rc1, 0)
            self.assertIn("17 components · 36 layers", buf1.getvalue())

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                rc2 = autonomy_main(["--zoe-root", str(REPO_ROOT), "chat", "--state", str(state), "--command", "theorem13"])
            self.assertEqual(rc2, 0)
            _assert_r3_output(self, "theorem13", buf2.getvalue())

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                autonomy_main(["definitely-unknown-command"])
        self.assertEqual(exc.exception.code, 2)


class M5EleganceAndDocsTests(unittest.TestCase):
    def test_m5_modules_are_grade_a_and_repo_has_zero_c_or_d(self):
        targets = (
            "components/Zoe-Autonomy/src/zoe_autonomy/cli.py",
            "guiai-lab/guiai/gem/cli.py",
            "guiai-lab/guiai/gem/unified_cli.py",
            "components/Zoe-Autonomy/src/zoe_autonomy/chat.py",
        )
        for rel in targets:
            report = analyze_python_source((REPO_ROOT / rel).read_text(encoding="utf-8"), rel)
            self.assertEqual(report["grade"], "A", f"{rel} scored {report['grade']} (MI={report['mi_score']})")
            self.assertLessEqual(report["max_cc"], 20, f"{rel} max_cc={report['max_cc']}")
        cwd_before = Path.cwd()
        try:
            os.chdir(REPO_ROOT)
            summary = audit_zoe_monorepo_elegance(".")["monorepo_summary"]
        finally:
            os.chdir(cwd_before)
        self.assertEqual(summary["parse_errors"], 0)
        self.assertEqual(summary["grade_distribution"]["C"], 0)
        self.assertEqual(summary["grade_distribution"]["D"], 0)

    def test_readme_and_proof_packet_links_and_counts(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        pp = (REPO_ROOT / "docs" / "PROOF-PACKET.md").read_text(encoding="utf-8")
        for doc_name, txt, base in (("README.md", readme, REPO_ROOT), ("docs/PROOF-PACKET.md", pp, REPO_ROOT / "docs")):
            self.assertNotIn("/home/cowboy", txt, doc_name)
            self.assertNotIn("file://", txt, doc_name)
            self.assertNotIn("sk-ant-", txt, doc_name)
            targets = re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", txt)
            targets += re.findall(r"""(?:href|src)=["']([^"']+)["']""", txt)
            for raw in targets:
                if not raw or raw.startswith(("http://", "https://", "mailto:", "data:", "#")):
                    continue
                rel = raw.split("#", 1)[0].split("?", 1)[0]
                if rel:
                    self.assertTrue((base / rel).exists(), f"Broken link in {doc_name}: {rel}")
        self.assertIn(f"{len(EXTENDED_LAYERS)} Extended GEM Layers", readme)
        self.assertIn("15/15", pp)
        self.assertIn("45/45", pp)
        self.assertIn("Metacognition is achieved.", readme)
        self.assertIn("Nicholas × Zoe", readme)


if __name__ == "__main__":
    unittest.main()

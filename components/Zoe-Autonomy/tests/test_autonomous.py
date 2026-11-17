from __future__ import annotations

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from zoe_autonomy.actuation import ActuationPolicy
from zoe_autonomy.autonomous import (
    AutonomousCapabilityStep,
    save_step_report,
    verify_step_report,
)
from zoe_autonomy.capabilities import ResearchConnector, ResearchMemory
from zoe_autonomy.cli import main


class AutonomousHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        port = self.server.server_port
        if self.path.startswith("/research"):
            body = json.dumps({"message": {"items": [{
                "title": ["Zoe Research Source"],
                "DOI": "10.0000/zoe-test",
                "URL": f"http://127.0.0.1:{port}/paper",
                "publisher": "Zoe Test",
            }]}}).encode()
            content_type = "application/json"
        else:
            body = b"<html><title>Zoe Paper</title><body style='font-size:48px'>ZOE AUTONOMY<script>document.body.dataset.ready='yes'</script></body></html>"
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class FakeServices:
    def github(self, path):
        assert path == "user"
        return {"login": "zoe-test", "html_url": "https://example.com/zoe-test", "private": "not-exported"}


class FakeNotifier:
    def desktop(self, message):
        return {"succeeded": True, "message": message}


class FailedCompute:
    def run(self, *_args, **_kwargs):
        return {"succeeded": False, "returncode": 7, "stderr": "deliberate negative result"}


class FailingResearch:
    def search(self, *_args):
        raise RuntimeError("deliberate research failure")


class AutonomousStepCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.actuation = ActuationPolicy(self.root / "actuation")
        self.actuation.enable(["all"], owner_approved=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AutonomousHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def step(self, state="state", **overrides):
        options = {
            "state_root": self.root / state,
            "actuation": self.actuation,
            "research": ResearchConnector(self.actuation, {"crossref": self.base + "/research"}),
            "services": FakeServices(),
            "notifier": FakeNotifier(),
            "github_available": True,
        }
        options.update(overrides)
        return AutonomousCapabilityStep(**options).run()

    def test_zoe_selects_all_ten_capabilities_without_operator_choice(self):
        expected = [
            "research.crossref",
            "browser.open",
            "media.ocr",
            "memory.review",
            "compute.self_check",
            "jobs.self_check",
            "protocols.mcp_self_description",
            "services.github_user",
            "notifications.desktop",
            "instruments.simulated_identity",
        ]
        reports = [self.step() for _ in expected]
        self.assertEqual([report["value"]["selected_action"] for report in reports], expected)
        self.assertEqual(len(reports[0]["capability_discovery"]), 10)
        for report in reports:
            self.assertTrue(report["goal"]["internal_authorship"])
            self.assertFalse(report["operator_supplied_goal"])
            self.assertFalse(report["operator_supplied_capability"])
            self.assertFalse(report["operator_approval_required"])
            self.assertTrue(report["guard"]["approved"])
            self.assertTrue(report["execution"]["succeeded"])
            self.assertTrue(verify_step_report(report)["verified"])
        self.assertEqual(reports[8]["execution"]["result"]["message"], "Zoe completed autonomous step 9.")
        self.assertNotIn("private", json.dumps(reports[7]))
        state = json.loads((self.root / "state/state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["step_count"], 10)
        for previous, current in zip(state["history"], state["history"][1:]):
            self.assertEqual(current["previous_hash"], previous["step_sha256"])
        report_path = self.root / "step.json"
        save_step_report(reports[-1], report_path)
        self.assertTrue(verify_step_report(report_path)["verified"])
        with self.assertRaises(FileExistsError):
            save_step_report(reports[-1], report_path)
        tampered = dict(reports[-1])
        tampered["goal"] = dict(tampered["goal"], statement="Operator replacement")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify_step_report(tampered)

    def test_no_grant_denies_external_calls_and_cli_needs_no_goal_or_tool(self):
        denied_root = self.root / "denied-actuation"
        environment = {"ZOE_ACTUATION_ROOT": str(denied_root)}
        output_path = self.root / "cli-step.json"
        with mock.patch.dict(os.environ, environment):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = main(["step", "--state", str(self.root / "cli-state"), "--output", str(output_path)])
                self.assertEqual(result, 0)
                self.assertIn("Selected action: memory.review", output.getvalue())
                self.assertIn("Zoe supplied the goal, capability, arguments", output.getvalue())
                self.assertEqual(main(["verify-step", str(output_path)]), 0)
        report = json.loads(output_path.read_text(encoding="utf-8"))
        research = next(item for item in report["proposals"] if item["action"] == "research.crossref")
        self.assertIn("owner grant or emergency stop does not enable network", report["guards"][research["id"]]["reasons"])
        self.assertEqual(report["value"]["selected_action"], "memory.review")
        self.assertFalse(report["execution"]["succeeded"] is False)

    def test_negative_adapter_result_is_not_claimed_as_success(self):
        state_root = self.root / "negative-state"
        memory = ResearchMemory(state_root / "research.sqlite")
        memory.add_source("Existing evidence", "Zoe has a source requiring computational assessment")
        report = self.step(state="negative-state", compute=FailedCompute())
        self.assertEqual(report["goal"]["kind"], "self_assessment")
        self.assertEqual(report["value"]["selected_action"], "compute.self_check")
        self.assertTrue(report["execution"]["executed"])
        self.assertFalse(report["execution"]["succeeded"])
        self.assertEqual(report["execution"]["result"]["returncode"], 7)
        self.assertEqual(report["execution"]["error"]["type"], "UnsuccessfulCapabilityResult")

    def test_failed_selection_is_recorded_and_next_goal_self_assesses(self):
        first = self.step(state="recovery", research=FailingResearch())
        self.assertEqual(first["value"]["selected_action"], "research.crossref")
        self.assertFalse(first["execution"]["succeeded"])
        second = self.step(state="recovery", research=FailingResearch())
        self.assertEqual(second["goal"]["kind"], "self_assessment")
        self.assertEqual(second["value"]["selected_action"], "compute.self_check")
        self.assertTrue(second["execution"]["succeeded"])
        self.assertEqual(second["previous_hash"], first["step_sha256"])


if __name__ == "__main__":
    unittest.main()

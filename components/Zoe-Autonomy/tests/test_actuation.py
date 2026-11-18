from __future__ import annotations

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import pty
import select
import sys
import tempfile
import threading
import unittest

from zoe_autonomy.actuation import ActuationPolicy, canonical, digest
from zoe_autonomy.cli import main
from zoe_autonomy.loop import BoundedAutonomyLoop, Candidate, SandboxPolicy


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"zoe-network-ok")

    def log_message(self, *_args):
        pass


class ActuationCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.policy = ActuationPolicy(self.root)
        self.policy.enable(["all"], owner_approved=True)

    def tearDown(self):
        self.temporary.cleanup()

    def host_operation(self, text="zoe-host-ok"):
        return {
            "kind": "host",
            "argv": [sys.executable, "-c", f"print({text!r})"],
            "cwd": str(self.root),
            "timeout": 10,
        }

    def test_owner_grant_and_real_harmless_host_command(self):
        status = self.policy.status()
        self.assertEqual(status["enabled_scopes"], {"host": True, "network": True, "hardware": True})
        self.assertFalse(status["emergency_stop"])
        result = self.policy.execute(self.host_operation())
        self.assertTrue(result["external_action"])
        self.assertTrue(result["result"]["succeeded"])
        self.assertEqual(result["result"]["stdout"].strip(), "zoe-host-ok")
        self.assertFalse(result["result"]["shell_used"])
        self.assertTrue((self.root / "actuation-audit.jsonl").is_file())

    def test_real_loopback_network_request(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/zoe"
            result = self.policy.execute({"kind": "network", "url": url, "timeout": 5})
            self.assertEqual(result["result"]["status"], 200)
            self.assertEqual(result["result"]["body"], "zoe-network-ok")
            self.assertTrue(result["result"]["succeeded"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_real_virtual_hardware_write(self):
        master, slave = pty.openpty()
        try:
            device = os.ttyname(slave)
            result = self.policy.execute({
                "kind": "hardware",
                "device": device,
                "payload_hex": b"Z".hex(),
                "timeout": 2,
            })
            self.assertEqual(result["result"]["bytes_written"], 1)
            self.assertTrue(result["result"]["character_device"])
            ready, _, _ = select.select([master], [], [], 2)
            self.assertTrue(ready)
            self.assertEqual(os.read(master, 1), b"Z")
        finally:
            os.close(master)
            os.close(slave)

    def test_zoe_selects_real_host_action_and_emergency_stop_blocks_next(self):
        actuation = ActuationPolicy(self.root)
        loop = BoundedAutonomyLoop(SandboxPolicy(allow_external=True, actuation=actuation))
        external = Candidate(
            "host-choice",
            "host",
            .9,
            .9,
            .1,
            "Run the harmless owner-authorized local command",
            external=True,
            operation=self.host_operation("zoe-selected-host"),
        )
        internal = Candidate("preserve", "preserve", .1, .1, 1, "Lower-value internal action")
        event = loop.run({"observation": "host-test"}, {"accessible_volume": 1}, [internal, external])
        self.assertEqual(event["value"]["selected_candidate"], "host-choice")
        self.assertTrue(event["execution"]["executed"])
        self.assertTrue(event["execution"]["external_action"])
        self.assertFalse(event["execution"]["sandbox"])
        self.assertEqual(loop.external_actions, 1)
        self.assertEqual(loop.environment.snapshot()["revision"], 0)
        self.assertEqual(event["execution"]["transition"]["result"]["stdout"].strip(), "zoe-selected-host")
        actuation.stop("Test emergency stop")
        stopped = loop.run({"observation": "host-test"}, {"accessible_volume": 1}, [external])
        self.assertFalse(stopped["guard"]["approved"])
        self.assertFalse(stopped["execution"]["executed"])
        self.assertEqual(loop.external_actions, 1)
        with self.assertRaises(PermissionError):
            actuation.execute(self.host_operation())
        actuation.resume(owner_approved=True)
        self.assertTrue(actuation.enabled("host"))

    def test_actuation_cli_enable_status_and_host(self):
        root = self.root / "cli"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["actuate", "--root", str(root), "enable", "--all", "--owner-approved"]), 0)
            self.assertEqual(main(["actuate", "--root", str(root), "status"]), 0)
            self.assertEqual(main([
                "actuate", "--root", str(root), "host",
                "--argv", json.dumps([sys.executable, "-c", "print('zoe-cli-host')"]),
                "--cwd", str(self.root),
            ]), 0)
        report = ActuationPolicy(root).status()
        self.assertTrue(all(report["enabled_scopes"].values()))

    def test_audit_chain_and_grant_hostname_binding(self):
        self.policy.execute(self.host_operation())
        lines = [json.loads(line) for line in (self.root / "actuation-audit.jsonl").read_text().splitlines() if line]
        previous = None
        for index, event in enumerate(lines, 1):
            self.assertEqual(event["sequence"], index)
            self.assertEqual(event["previous_hash"], previous)
            body = {key: value for key, value in event.items() if key != "hash"}
            self.assertEqual(digest(body), event["hash"])
            previous = event["hash"]
        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(canonical(lines[0]))


if __name__ == "__main__":
    unittest.main()

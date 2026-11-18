from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from zoe_autonomy.actuation import ActuationPolicy
from zoe_autonomy.agents import AgentGateway
from zoe_autonomy.explore import WebExplorer


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pages = {
            "/robots.txt": ("text/plain", "User-agent: *\nDisallow: /private"),
            "/": ("text/html", "<html><title>Home</title><body>Public home <a href='/next'>Next</a><a href='https://example.com/external'>External</a><a href='/private'>Private</a></body></html>"),
            "/next": ("text/html", "<html><title>Next</title><body>Second public page</body></html>"),
            "/private": ("text/html", "<html><title>Private</title><body>Do not fetch</body></html>"),
        }
        content_type, body = pages.get(self.path, ("text/plain", "missing"))
        self.send_response(200 if self.path in pages else 404)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_args):
        pass


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer test-secret-key":
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps({
            "model": "owned-test-model",
            "choices": [{"message": {"content": "connected-response"}}],
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class GatewayCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.actuation = ActuationPolicy(self.root / "actuation")
        self.actuation.enable(["all"], owner_approved=True)
        self.gateway = AgentGateway(self.root / "agents", self.actuation)

    def tearDown(self):
        self.temporary.cleanup()

    def server(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.addCleanup(thread.join, 5)
        return server

    def test_web_explorer_follows_same_origin_and_robots(self):
        server = self.server(WebHandler)
        base = f"http://127.0.0.1:{server.server_port}/"
        report = WebExplorer(self.actuation).explore(base, max_pages=5, max_depth=1, delay=.1)
        self.assertEqual(report["pages_fetched"], 2)
        urls = {page["url"] for page in report["pages"]}
        self.assertEqual(urls, {base, base + "next"})
        self.assertNotIn(base + "private", urls)
        self.assertTrue(report["robots_txt_respected"])
        self.assertTrue(report["same_origin_only"])
        self.assertEqual(report["external_page_requests"], 2)

    def test_owner_cli_agent_invocation_and_prompt_redaction(self):
        self.gateway.add_cli(
            "mock-cli",
            [sys.executable, "-c", "import sys; print(sys.argv[1])", "{prompt}"],
            owner_approved=True,
        )
        result = self.gateway.invoke("mock-cli", "owned test prompt", timeout=10)
        self.assertTrue(result["succeeded"])
        self.assertEqual(result["content"].strip(), "owned test prompt")
        audit = self.gateway.audit_path.read_text(encoding="utf-8")
        self.assertNotIn("owned test prompt", audit)
        self.assertIn("prompt_sha256", audit)

    def test_openai_compatible_account_and_credential_redaction(self):
        server = self.server(AgentHandler)
        os.environ["ZOE_TEST_AGENT_KEY"] = "test-secret-key"
        try:
            self.gateway.add_http(
                "owned-http",
                f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                "owned-test-model",
                "ZOE_TEST_AGENT_KEY",
                owner_approved=True,
            )
            result = self.gateway.invoke("owned-http", "private prompt", timeout=10)
            self.assertTrue(result["succeeded"])
            self.assertEqual(result["content"], "connected-response")
            self.assertTrue(self.gateway.list()[0]["credential_configured"])
            audit = self.gateway.audit_path.read_text(encoding="utf-8")
            self.assertNotIn("test-secret-key", audit)
            self.assertNotIn("private prompt", audit)
        finally:
            os.environ.pop("ZOE_TEST_AGENT_KEY", None)

    def test_discovery_and_owner_registration(self):
        discovered = self.gateway.discover()
        self.assertTrue({item["id"] for item in discovered} >= {"kimi", "claude", "codex"})
        result = self.gateway.register_discovered(owner_approved=True)
        self.assertIsInstance(result["added"], list)


if __name__ == "__main__":
    unittest.main()

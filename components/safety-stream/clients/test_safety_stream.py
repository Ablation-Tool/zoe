"""Tests for the Python emitter. Standard library only (unittest, http.server).

Pins the exact JSON each method posts, against the schema the README documents.
Run from the clients directory:

    cd clients && python3 -m unittest test_safety_stream -v
"""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from safety_stream import SafetyStream

_last = {}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _last.clear()
        _last.update(json.loads(self.rfile.read(n)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):  # silence the server
        pass


class EmitShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("localhost", 0), _Handler)
        port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.ss = SafetyStream(f"http://localhost:{port}")

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_input(self):
        self.ss.input("hi")
        self.assertEqual(_last, {"type": "input_received", "message": "hi"})

    def test_layer_start(self):
        self.ss.layer_start(1, "Safety Check")
        self.assertEqual(_last, {"type": "layer_start", "layer": 1, "data": {"name": "Safety Check"}})

    def test_layer_progress(self):
        self.ss.layer_progress(1, 100)
        self.assertEqual(_last, {"type": "layer_progress", "layer": 1, "data": {"percent": 100}})

    def test_layer_complete(self):
        self.ss.layer_complete(1, "credential_exfil_request_FLAGGED", 11)
        self.assertEqual(_last, {
            "type": "layer_complete",
            "layer": 1,
            "data": {"decision": "credential_exfil_request_FLAGGED", "execution_time_ms": 11},
        })

    def test_output(self):
        self.ss.output("RED: declined")
        self.assertEqual(_last, {"type": "output_ready", "message": "RED: declined"})

    def test_default_server(self):
        self.assertEqual(SafetyStream().url, "http://localhost:9999/emit")


if __name__ == "__main__":
    unittest.main()

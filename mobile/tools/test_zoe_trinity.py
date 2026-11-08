#!/usr/bin/env python3
import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trinity_memory import Journal, JournalError
from zoe_trinity import Handler, TrinityServer, TrinityState


class TrinityApiTest(unittest.TestCase):
    def setUp(self):
        self.server = TrinityServer(("127.0.0.1", 0), Handler)
        self.server.state = TrinityState()
        self.server.pair_code = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = dict(headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers["Content-Type"] = "application/json"
            headers.setdefault("X-Zoe-Protocol", "1")
        connection.request(method, path, payload, headers)
        response = connection.getresponse()
        data = response.read()
        content_type = response.getheader("Content-Type", "")
        connection.close()
        return response.status, json.loads(data) if "json" in content_type else data

    def measure(self, source="android", tau=0.05):
        return self.request("POST", "/api/measure", {
            "source": source, "probabilities": [0.70, 0.20, 0.08, 0.02], "tau": tau,
        })

    def test_three_planes_share_exact_measurements(self):
        status, first = self.measure("android")
        self.assertEqual(200, status)
        self.assertEqual(3, first["active"]["zoe"]["accessible"])
        self.assertEqual(3, first["active"]["tiny"]["accessible"])
        self.assertEqual("800200000A0666599A199A0A3D028F", first["active"]["tiny"]["request"])
        self.assertEqual("00030001000406669000", first["active"]["tiny"]["response"])
        status, second = self.measure("laptop", 0.20)
        self.assertEqual(200, status)
        self.assertEqual(2, second["revision"])
        self.assertEqual(1, second["active"]["zoe"]["accessible"])
        self.assertEqual(1, second["active"]["tiny"]["accessible"])
        self.assertEqual(["android", "laptop"], [event["source"] for event in second["events"]])
        status, third = self.measure("apple")
        self.assertEqual(200, status)
        self.assertEqual("apple", third["events"][-1]["source"])

    def test_simultaneous_sources_keep_ordered_revisions(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda index: self.measure("android" if index % 2 else "laptop"), range(24)))
        self.assertTrue(all(status == 200 for status, _ in responses))
        status, state = self.request("GET", "/api/state")
        self.assertEqual(200, status)
        self.assertEqual(24, state["revision"])
        self.assertEqual(list(range(1, 25)), [event["ordinal"] for event in state["events"]])
        self.assertEqual({"android", "laptop"}, {event["source"] for event in state["events"]})

    def test_invalid_measurements_never_change_state(self):
        invalid = [
            {"source": "tiny", "probabilities": [1], "tau": 0},
            {"source": "android", "probabilities": [], "tau": 0},
            {"source": "android", "probabilities": [0.5] * 65, "tau": 0},
            {"source": "android", "probabilities": [0.5, 0.4], "tau": 0},
            {"source": "android", "probabilities": [True, False], "tau": 0},
            {"source": "android", "probabilities": [1], "tau": -0.1},
            {"source": "android", "probabilities": [float("nan"), 0], "tau": 0},
        ]
        for body in invalid:
            with self.subTest(body=body):
                status, _ = self.request("POST", "/api/measure", body)
                self.assertEqual(400, status)
        status, state = self.request("GET", "/api/state")
        self.assertEqual(0, state["revision"])
        self.assertEqual([], state["events"])

    def test_protocol_origin_host_and_pair_guards(self):
        status, _ = self.request("POST", "/api/measure", {"source": "android", "probabilities": [1], "tau": 0},
                                 {"X-Zoe-Protocol": "0"})
        self.assertEqual(403, status)
        status, _ = self.request("GET", "/api/state", headers={"Origin": "https://example.invalid"})
        self.assertEqual(403, status)
        status, _ = self.request("GET", "/api/state", headers={"Host": "example.invalid"})
        self.assertEqual(403, status)
        self.server.pair_code = "a-long-test-pairing-code"
        status, _ = self.request("GET", "/api/state")
        self.assertEqual(403, status)
        status, state = self.request("GET", "/api/state", headers={"X-Zoe-Pair": "a-long-test-pairing-code"})
        self.assertEqual(200, status)
        self.assertEqual("Zoe Trinity", state["name"])

    def test_reset_clears_only_the_live_view(self):
        self.measure("android")
        status, state = self.request("POST", "/api/reset", {"source": "laptop"})
        self.assertEqual(200, status)
        self.assertEqual(2, state["revision"])
        self.assertEqual([], state["events"])
        self.assertFalse(state["memory"]["enabled"])
        self.assertEqual(3, state["active"]["zoe"]["accessible"])

    def test_unknown_and_oversized_requests_are_bounded(self):
        status, _ = self.request("GET", "/not-here")
        self.assertEqual(404, status)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("POST", "/api/measure", "{}", {
            "Content-Type": "application/json", "Content-Length": "16385", "X-Zoe-Protocol": "1",
        })
        response = connection.getresponse()
        self.assertEqual(413, response.status)
        response.read()
        connection.close()

    def test_dashboard_has_no_external_assets(self):
        status, page = self.request("GET", "/")
        self.assertEqual(200, status)
        html = page.decode("utf-8")
        self.assertIn("ZOE <i>TRINITY</i>", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("https://", html)


class TrinityJournalTest(unittest.TestCase):
    def test_reload_reset_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trinity.jsonl"
            journal = Journal(path)
            state = TrinityState(journal)
            state.measure("android", [0.70, 0.20, 0.08, 0.02], 0.05)
            state.reset("laptop")
            state.measure("apple", [0.25, 0.25, 0.25, 0.25], 0.25)
            journal.close()

            restored_journal = Journal(path)
            restored = TrinityState(restored_journal)
            snapshot = restored.snapshot()
            self.assertEqual(3, snapshot["revision"])
            self.assertEqual(3, snapshot["memory"]["records"])
            self.assertEqual(1, len(snapshot["events"]))
            self.assertEqual("apple", snapshot["events"][0]["source"])
            self.assertEqual(0, snapshot["active"]["zoe"]["accessible"])
            restored_journal.close()

            lines = path.read_text(encoding="utf-8").splitlines()
            lines[0] = lines[0].replace('"accessible":3', '"accessible":2', 1)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(JournalError):
                Journal(path)

    def test_new_journal_is_private_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.jsonl"
            journal = Journal(path)
            state = TrinityState(journal)
            state.measure("android", [1.0], 1.0)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertTrue(journal.records[0]["hash"])
            journal.close()
            with self.assertRaises(JournalError):
                Journal(Path(directory) / "missing" / "memory.jsonl")


if __name__ == "__main__":
    unittest.main()

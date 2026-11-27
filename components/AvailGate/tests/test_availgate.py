"""Offline regression checks for the AvailGate CLI at ~/bin/availgate."""

import json
import os
import importlib.util
import runpy
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from urllib.parse import urlparse
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "availgate" / "legacy.py"
if os.environ.get("AVAILGATE_TEST_INSTALLED") == "1":
    SCRIPT = Path(importlib.util.find_spec("availgate.legacy").origin)


class FakeResponse:
    def __init__(self, status=200, chunks=(), location=None):
        self.status = status
        self.headers = {"Location": location} if location else {}
        self.chunks = chunks
        self.closed = False

    def stream(self, amt, decode_content):
        yield from self.chunks

    def release_conn(self):
        self.closed = True


class FakePool:
    def __init__(self, response):
        self.response = response
        self.urlopen = mock.Mock(return_value=response)
        self.closed = False

    def close(self):
        self.closed = True


class AvailGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = runpy.run_path(str(SCRIPT))

    def test_yandex_leaf_elements(self):
        xml = b"<root><doc><url>https://example.com/x</url><title>Test</title><headline>Sample</headline><modtime>20261011</modtime></doc></root>"
        response = types.SimpleNamespace(content=xml, raise_for_status=lambda: None)
        engine = self.code["engine_yandex"]
        with mock.patch.dict(engine.__globals__, {
            "HAS_REQUESTS": True,
            "requests": types.SimpleNamespace(get=lambda *args, **kwargs: response),
        }):
            hit = engine("q", 1, "user", "key")[0]
        self.assertEqual((hit.url, hit.title, hit.snippet),
                         ("https://example.com/x", "Test", "Sample"))

    def test_operator_values_are_preserved(self):
        pattern = self.code["_OPERATOR_RE"]
        self.assertEqual(
            pattern.findall('inurl:"/admin/login" intitle:Dashboard filetype:pdf'),
            ['inurl:"/admin/login"', "intitle:Dashboard", "filetype:pdf"],
        )

    def test_dork_augmentation_uses_operator_value(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus = Path(temp_dir) / "ghdb.json"
            corpus.write_text(json.dumps([{
                "category": "Pages Containing Login Portals",
                "shortDescription": "Admin login", "textualDescription": "admin login",
                "query": 'inurl:"/admin/login" admin',
            }]), encoding="utf-8")
            augmented = self.code["ghdb_augment_query"]("admin login", str(corpus), 1)
        self.assertEqual(augmented, ['inurl:"/admin/login" admin login'])

    def test_cache_key_includes_output_and_scoring_options(self):
        key = self.code["_cache_key"]
        base = key("query", {"ddg"}, "", 2)
        self.assertNotEqual(base, key("query", {"ddg"}, "", 2, top=5))
        self.assertNotEqual(base, key("query", {"ddg"}, "", 2, results_per_engine=5))
        self.assertNotEqual(base, key("query", {"ddg"}, "", 2, weights={"bm25": 0.9}))
        self.assertNotEqual(base, key("query", {"ddg"}, "", 2, no_semantic=True))
        self.assertNotEqual(
            base,
            key("query", {"ddg"}, "", 2,
                engine_config={"searxng_url": "https://other.example"}),
        )

    def test_canonical_url_preserves_case_sensitive_parts(self):
        canonicalize = self.code["canonicalize"]
        self.assertEqual(canonicalize("HTTPS://WWW.Example.com/Admin?Token=ABC"),
                         "https://example.com/Admin?Token=ABC")
        self.assertNotEqual(canonicalize("https://e.test/A"),
                            canonicalize("https://e.test/a"))

    def test_duplicate_engine_keeps_best_rank(self):
        hit = self.code["Hit"]
        aggregate = self.code["aggregate"]
        results, _ = aggregate([
            hit("https://e.test/x", "x", "x", "ddg", 1),
            hit("https://e.test/x", "x", "x", "ddg", 20),
        ], "x", no_semantic=True)
        self.assertEqual(results[0].ranks["ddg"], 1)

    def test_fetch_rejects_loopback_without_request(self):
        fetch = self.code["_fetch_body"]
        with mock.patch("urllib3.HTTPConnectionPool") as pool:
            self.assertEqual(fetch("http://127.0.0.1/admin", None), "")
            pool.assert_not_called()

    def test_fetch_rejects_private_ipv6(self):
        self.assertIsNone(self.code["_public_fetch_target"]("http://[::1]/admin"))

    def test_fetch_rejects_redirect_to_loopback(self):
        fetch = self.code["_fetch_body"]
        response = FakeResponse(302, location="http://127.0.0.1/admin")
        pool = FakePool(response)
        with mock.patch.dict(fetch.__globals__, {
            "_public_fetch_target": lambda url: (
                (urlparse(url), "8.8.8.8", 443)
                if url == "https://safe.example/start" else None
            )
        }), mock.patch("urllib3.HTTPSConnectionPool", return_value=pool) as create_pool:
            self.assertEqual(fetch("https://safe.example/start", None), "")
        self.assertEqual(create_pool.call_count, 1)
        self.assertTrue(response.closed)
        self.assertTrue(pool.closed)

    def test_fetch_caps_response_body(self):
        fetch = self.code["_fetch_body"]
        response = FakeResponse(chunks=[b"x" * (2 * 1024 * 1024 + 1)])
        pool = FakePool(response)
        with mock.patch.dict(fetch.__globals__, {
            "_public_fetch_target": lambda url: (urlparse(url), "8.8.8.8", 443)
        }), mock.patch("urllib3.HTTPSConnectionPool", return_value=pool):
            self.assertEqual(fetch("https://safe.example/large", None), "")
        self.assertTrue(response.closed)

    def test_fetch_connection_uses_vetted_ip_only(self):
        fetch = self.code["_fetch_body"]
        response = FakeResponse(chunks=[b"<html>public page</html>"])
        pool = FakePool(response)
        dns = mock.Mock(side_effect=[
            [(None, None, None, None, ("8.8.8.8", 443))],
            [(None, None, None, None, ("127.0.0.1", 443))],
        ])
        with mock.patch("socket.getaddrinfo", dns), \
             mock.patch("urllib3.HTTPSConnectionPool", return_value=pool) as create_pool:
            self.assertIn("public page", fetch("https://safe.example/page", None))
        self.assertEqual(dns.call_count, 1)
        self.assertEqual(create_pool.call_args.args[0], "8.8.8.8")
        self.assertEqual(create_pool.call_args.kwargs["server_hostname"], "safe.example")
        self.assertEqual(create_pool.call_args.kwargs["assert_hostname"], "safe.example")

    def test_fetch_reranks_all_results(self):
        result = self.code["AggResult"]
        fetch = self.code["fetch_augment"]
        first = result("https://a.test", "a", "a", score=0.9,
                       components={"rrf": 0.1, "bm25": 0.1})
        second = result("https://b.test", "b", "b", score=0.8,
                        components={"rrf": 0.8, "bm25": 0.8})
        with mock.patch.dict(fetch.__globals__, {"_fetch_body": lambda url, session: ""}):
            ranked = fetch([first, second], "missing", 1, object(),
                           weights={"rrf": 0.5, "bm25": 0.5})
        self.assertEqual(ranked[0].url, "https://b.test")

    def test_ghdb_only_cli_system_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus = Path(temp_dir) / "ghdb.json"
            corpus.write_text(json.dumps([{
                "id": "1", "category": "Pages Containing Login Portals",
                "shortDescription": "Admin login", "textualDescription": "Admin login page",
                "query": 'inurl:"/admin/login"',
            }]), encoding="utf-8")
            proc = subprocess.run([
                sys.executable, str(SCRIPT), "--engines", "ghdb", "--ghdb-path",
                str(corpus), "--no-cache", "--no-semantic", "--json", "admin login",
            ], capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["engines"], ["ghdb"])

    def test_health_check_has_total_deadline(self):
        health = self.code["run_health_check"]

        def slow_engine(eng, query, n, cfg):
            time.sleep(0.3)
            return eng, query, []

        started = time.monotonic()
        with mock.patch.dict(health.__globals__, {
            "_dispatch_engine_inner": slow_engine,
            "_HEALTH_TIMEOUT": 0.02,
        }), self.assertRaises(SystemExit) as exited:
            health({})
        self.assertEqual(exited.exception.code, 1)
        self.assertLess(time.monotonic() - started, 0.25)

    def test_cache_round_trip(self):
        cache_set = self.code["_cache_set"]
        cache_get = self.code["_cache_get"]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "results.db")
            with mock.patch.dict(cache_set.__globals__, {"_CACHE_PATH": path}):
                self.assertIsNone(cache_get("fixture-key"))
                cache_set("fixture-key", [{"url": "https://example.com"}])
                self.assertEqual(cache_get("fixture-key"),
                                 [{"url": "https://example.com"}])

    def test_clear_cache_needs_no_query(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--clear-cache"],
                env={"HOME": temp_dir}, capture_output=True, text=True, timeout=20,
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("cache cleared", proc.stderr)


if __name__ == "__main__":
    unittest.main()

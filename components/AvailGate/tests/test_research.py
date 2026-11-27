"""Offline contract, isolation, persistence, and reader regression tests."""

import importlib
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from importlib.resources import files
from unittest import mock
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = os.environ.get("AVAILGATE_TEST_INSTALLED") == "1"
if not INSTALLED:
    sys.path.insert(0, str(ROOT / "src"))

from availgate import legacy
from availgate.config import load
from availgate.contracts import Problem
from availgate.providers import run_provider
from availgate.reader import extract, fetch, read
from availgate.search import queries_for, search
from availgate.storage import Store, markdown
from availgate.workers import run_jobs

search_module = importlib.import_module("availgate.search")
reader_module = importlib.import_module("availgate.reader")


def hang():
    time.sleep(20)


def provider_outcome(status="success", hits=None, engine="bing"):
    return {"engine": engine, "query": "widget", "upstream": engine, "status": status,
            "hits": hits or [], "hit_count": len(hits or []), "duration_ms": 1,
            "errors": [], "request_count": 1}


def hit(url="https://docs.example.org/Widget", date=None):
    return {"url": url, "title": "Widget", "snippet": "widget reference",
            "engine": "bing", "rank": 1, "date": date}


class Response:
    def __init__(self, status=200, body=b"<html><title>Widget</title><main><p>Body</p></main></html>", headers=None):
        self.status = status
        self.headers = headers or {"Content-Type": "text/html"}
        self.body = body
        self.closed = False

    def stream(self, **kwargs):
        yield self.body

    def release_conn(self):
        self.closed = True


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = self.path / "config.json"
        self.config.write_text("{}", encoding="utf-8")
        self.env = {**os.environ, "AVAILGATE_DATA_DIR": str(self.path / "data"),
                    "AVAILGATE_CONFIG": str(self.config), "PYTHONPATH": str(ROOT / "src")}
        if INSTALLED:
            self.env.pop("PYTHONPATH", None)
        self.env.update({name: "" for name in ("GOOGLE_API_KEY", "GOOGLE_CX", "SERPER_API_KEY", "YANDEX_KEY", "YANDEX_USER", "MOJEEK_API_KEY", "BRAVE_API_KEY", "GHDB_PATH", "SEARXNG_URL", "AVAILGATE_PROXY")})
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "availgate", *arguments],
                              env=self.env, cwd=self.path, capture_output=True, text=True, timeout=12)

    def validate(self, value):
        try:
            import jsonschema
        except ImportError:
            self.fail("Install the dev extra to validate the response schema")
        schema = json.loads(files("availgate").joinpath("resources/response.schema.json").read_text())
        jsonschema.validate(value, schema)

    def test_cli_validation_is_json(self):
        for arguments in (("search", "--json"), ("search", "x", "--top", "0", "--json"),
                          ("search", "x", "--timeout", "nan", "--json"),
                          ("search", "x", "--engines", "fake", "--json"),
                          ("read", "https://u:secret@example.org", "--json")):
            result = self.cli(*arguments)
            self.assertEqual(result.returncode, 2, result.stderr)
            value = json.loads(result.stdout)
            self.assertEqual(value["status"], "error")
            self.assertNotIn("secret", result.stdout + result.stderr)
            self.validate(value)

    def test_capabilities_do_not_import_semantic_or_network(self):
        result = self.cli("capabilities", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.validate(json.loads(result.stdout))
        self.assertNotIn("sentence_transformers", sys.modules)
        self.assertFalse((self.path / "data").exists())

    def test_search_statuses_and_schema(self):
        cases = [("empty", "empty", "ok"), ("success", "timeout", "partial"),
                 ("timeout", "error", "error")]
        for a, b, expected in cases:
            outcomes = [{"value": [provider_outcome(a, [hit()] if a == "success" else [])]},
                        {"value": [provider_outcome(b, engine="brave")]}]
            with mock.patch.object(search_module, "run_jobs", return_value=outcomes):
                value = search("widget", engines=["bing", "brave"], no_cache=True)
            self.assertEqual(value["status"], expected)
            self.validate(value)

    def test_search_cache_preserves_observation_age(self):
        with mock.patch.object(search_module, "run_jobs", return_value=[{"value": [provider_outcome(hits=[hit()])]}]) as jobs:
            first = search("widget", engines=["bing"])
            time.sleep(0.02)
            second = search("widget", engines=["bing"])
            self.assertEqual(jobs.call_count, 1)
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertGreater(second["cache"]["age_seconds"], 0)
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertEqual(first["results"], second["results"])

    def test_domain_and_date_filters_and_explanations(self):
        outcomes = [{"value": [provider_outcome(hits=[hit(date="2026-10-01"),
                  hit("https://docs.example.org.evil.test/", date="2026-10-01"),
                  hit("https://docs.example.org/unknown")])]}]
        with mock.patch.object(search_module, "run_jobs", return_value=outcomes):
            value = search("widget", engines=["bing"], domains=["docs.example.org"],
                           official_domains=["docs.example.org"], since="2026-09-01", no_cache=True)
        self.assertEqual(len(value["results"]), 1)
        result = value["results"][0]
        self.assertEqual(result["official"]["status"], "configured")
        self.assertAlmostEqual(result["score"], sum(e["weight"] * e["value"] for e in result["explanation"]), places=3)

    def test_modes_preserve_quoted_qualifiers_and_budget(self):
        query = '"Widget Pro" 2.1 site:example.org'
        variants = queries_for(query, "docs")
        self.assertEqual(len(variants), 3)
        self.assertTrue(all(v.startswith(query) for v in variants))
        self.assertEqual(queries_for("maintenance", "compare", alternatives=["A", "B"]),
                         ["maintenance", "maintenance A", "maintenance B"])

    def test_provider_parses_bing_fixture(self):
        html = b'<ol><li class="b_algo"><h2><a href="https://example.org/x">Widget</a></h2><cite>https://example.org &gt; docs &gt; x</cite><div class="b_caption"><p>widget reference</p></div></li></ol>'
        result = mock.Mock(status_code=200)
        result.iter_content.return_value = [html]
        result.raise_for_status.return_value = None
        # The real adapter uses Response.content, which reads _content.
        import requests
        response = requests.Response()
        response.status_code = 200
        response._content = html
        response._content_consumed = True
        with mock.patch("requests.sessions.Session.request", return_value=response):
            value = run_provider("bing", "widget", 3, {})
        self.assertEqual(value["status"], "success", value)
        self.assertEqual(value["hits"][0]["url"], "https://example.org/x")

    def test_bing_tracking_link_preserves_full_destination(self):
        import base64
        url = "https://docs.python.org/3/library/pathlib.html"
        encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        self.assertEqual(legacy._bing_destination("https://www.bing.com/ck/a?u=a1" + encoded), url)
        self.assertEqual(legacy._bing_destination("javascript:alert(1)"), "")
        self.assertEqual(legacy._bing_destination("https://www.bing.com/ck/a?u=invalid"), "")

    def test_provider_failure_is_not_empty_and_does_not_leak_key(self):
        import requests
        failure = requests.Response()
        failure.status_code = 429
        with mock.patch("requests.sessions.Session.request", side_effect=requests.HTTPError("secret-token", response=failure)):
            value = run_provider("google", "q", 1, {"google_api_key": "secret-token", "google_cx": "cx"})
        self.assertEqual(value["status"], "rate_limited")
        self.assertNotIn("secret-token", json.dumps(value))

    def test_worker_deadline_reaps_children(self):
        before = {p.pid for p in multiprocessing.active_children()}
        start = time.monotonic()
        values = run_jobs(hang, [()], timeout=0.2, concurrency=1)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(values, [{"failure": "timeout"}])
        self.assertEqual(before, {p.pid for p in multiprocessing.active_children()})

    def test_reader_preserves_code_and_exact_excerpt_offsets(self):
        body = '<title>Guide</title><nav>Ignore me</nav><main><h1>Heading</h1><p>Héllo <b>world</b>.</p><pre>if x:\n    y()</pre></main>'.encode()
        doc = extract(body, "text/html; charset=utf-8", max_chars=200)
        self.assertNotIn("Ignore me", doc["text"])
        self.assertIn("Héllo world", doc["text"])
        self.assertIn("if x:\n    y()", doc["text"])
        for excerpt in doc["excerpts"]:
            self.assertEqual(doc["text"][excerpt["start"]:excerpt["end"]], excerpt["text"])
        self.assertIsNone(doc["published_at"])

    def test_reader_truncation_and_unsupported_type(self):
        doc = extract(b"abcdefgh", "text/plain", max_chars=3)
        self.assertEqual(doc["text"], "abc")
        self.assertTrue(doc["truncated"])
        with self.assertRaises(Problem):
            extract(b"pdf", "application/pdf", max_chars=20)

    def test_reader_vetted_ip_and_private_redirect(self):
        import urllib3
        pool = mock.Mock()
        result = Response()
        pool.urlopen.return_value = result
        with mock.patch.object(legacy, "_public_fetch_target", return_value=(urlparse("https://example.org/page"), "8.8.8.8", 443)), \
             mock.patch.object(urllib3, "HTTPSConnectionPool", return_value=pool) as create:
            doc = fetch("https://example.org/page", 100)
        self.assertEqual(create.call_args.args[0], "8.8.8.8")
        self.assertEqual(create.call_args.kwargs["assert_hostname"], "example.org")
        self.assertEqual(doc["text"], "Body")
        self.assertTrue(result.closed)
        result = Response(302, headers={"Location": "http://127.0.0.1/"})
        pool.urlopen.return_value = result
        with mock.patch.object(legacy, "_public_fetch_target", side_effect=[(urlparse("https://example.org/page"), "8.8.8.8", 443), None]), \
             mock.patch.object(urllib3, "HTTPSConnectionPool", return_value=pool), self.assertRaises(Problem) as error:
            fetch("https://example.org/page", 100)
        self.assertEqual(error.exception.code, "blocked_destination")

    def test_reader_body_limit_closes_connection(self):
        import urllib3
        result = Response(body=b"x" * (2097152 + 1))
        pool = mock.Mock()
        pool.urlopen.return_value = result
        with mock.patch.object(legacy, "_public_fetch_target", return_value=(urlparse("https://example.org/"), "8.8.8.8", 443)), \
             mock.patch.object(urllib3, "HTTPSConnectionPool", return_value=pool), self.assertRaises(Problem) as error:
            fetch("https://example.org/", 100)
        self.assertEqual(error.exception.code, "body_limit")
        self.assertTrue(result.closed)
        pool.close.assert_called_once()

    def test_read_cache_and_session_preserve_source_capture(self):
        store = Store()
        store.create("research")
        doc = {**extract(b"source evidence", "text/plain", max_chars=100),
               "id": "doc1", "requested_url": "https://example.org/", "final_url": "https://example.org/",
               "retrieved_at": "2026-10-01T00:00:00+00:00", "redirects": [], "transport": "direct_vetted_ip"}
        with mock.patch.object(reader_module, "run_jobs", return_value=[{"value": {"document": doc}}]) as jobs:
            first = read("https://example.org/", session="research")
            second = read("https://example.org/", session="research", proxy_only=True)
        self.assertEqual(jobs.call_count, 1)
        self.assertEqual(first["document"], second["document"])
        self.assertEqual(len(store.show("research")["events"]), 2)
        store.clear_cache()
        self.assertIn("source evidence", markdown(store.show("research")))
        self.validate(second)

    def test_proxy_only_refuses_uncached_network(self):
        with mock.patch.object(reader_module, "run_jobs") as jobs, self.assertRaises(Problem):
            read("https://example.org/", no_cache=True, proxy_only=True)
        jobs.assert_not_called()

    def test_sessions_resume_across_processes_and_export_offline(self):
        self.assertEqual(self.cli("session", "create", "review", "--json").returncode, 0)
        self.assertEqual(self.cli("session", "question", "review", "Check upgrades?", "--json").returncode, 0)
        result = self.cli("session", "show", "review", "--json")
        data = json.loads(result.stdout)
        self.validate(data)
        self.assertEqual(data["data"]["events"][0]["kind"], "question")
        result = self.cli("session", "export", "review", "--format", "markdown")
        self.assertIn("Check upgrades?", result.stdout)
        self.assertEqual(self.cli("session", "delete", "review", "--json").returncode, 2)
        self.assertEqual(self.cli("session", "delete", "review", "--yes", "--json").returncode, 0)
        self.assertEqual(self.cli("session", "show", "review", "--json").returncode, 2)

    def test_session_concurrent_updates_and_limit_are_atomic(self):
        store = Store()
        store.create("review")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda n: store.append("review", "note", {"text": str(n)}), range(12)))
        self.assertEqual(len(store.show("review")["events"]), 12)
        with mock.patch("availgate.storage.SESSION_LIMIT", 1), self.assertRaises(Problem):
            store.append("review", "note", {"text": "reject"})
        self.assertEqual(len(store.show("review")["events"]), 12)

    def test_configuration_precedence_and_invalid_file(self):
        self.config.write_text(json.dumps({"brave_api_key": "file"}))
        with mock.patch.dict(os.environ, {"BRAVE_API_KEY": "env"}):
            self.assertEqual(load()[0]["brave_api_key"], "env")
            self.assertEqual(load({"brave_api_key": "cli"})[0]["brave_api_key"], "cli")
        self.config.write_text("[]")
        with self.assertRaises(Problem):
            load()

    def test_completed_research_survives_session_quota_failure(self):
        Store().create("review")
        with mock.patch.object(search_module, "run_jobs", return_value=[{"value": [provider_outcome(hits=[hit()])]}]), \
             mock.patch("availgate.storage.SESSION_LIMIT", 1):
            result = search("widget", engines=["bing"], no_cache=True, session="review")
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["persistence"]["saved"])
        self.assertEqual(len(result["results"]), 1)

    def test_real_ghdb_subcommand_and_legacy_array(self):
        corpus = self.path / "ghdb.json"
        corpus.write_text(json.dumps([{"id": "1", "category": "Pages Containing Login Portals",
                         "shortDescription": "Widget login", "textualDescription": "Widget login",
                         "query": "intitle:Widget"}]))
        arguments = ["--engines", "ghdb", "--ghdb-path", str(corpus), "--no-cache", "--no-semantic", "--json", "Widget"]
        result = self.cli("search", *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["results"][0]["kind"], "query_template")
        self.validate(value)
        legacy_result = self.cli(*arguments)
        self.assertEqual(legacy_result.returncode, 0, legacy_result.stderr)
        self.assertIsInstance(json.loads(legacy_result.stdout), list)


if __name__ == "__main__":
    unittest.main()

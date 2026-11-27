"""Comprehensive verification tests for Zoe-ELIZA x GEM."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem._eliza_routes import _ServerContext, dispatch_post
from guiai.gem.eliza_view import create_server, synthesize_wav_bytes
from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.zoe_eliza_gem import eliza_scene
from zoe_autonomy.chat import EvidenceIndex, ZoeChat
from zoe_autonomy.dorothy_local_library import DorothyLocalLibraryIndex
from zoe_autonomy.zoe_eliza import (
    ELIZA_CONTRACT,
    LocalLLMBridge,
    ZoeElizaEngine,
    normalize_input,
    reflect_phrase,
)


class ZoeElizaTests(unittest.TestCase):
    def test_weizenbaum_preprocessing_reflection_and_non_repeating_cycling(self):
        self.assertEqual(normalize_input("I'm gonna build my project"), "i am going to build my project")
        ref, swaps = reflect_phrase("my code helps me understand myself")
        self.assertEqual(ref, "your code helps you understand yourself")
        self.assertGreaterEqual(len(swaps), 3)

        with tempfile.TemporaryDirectory() as tmp:
            eng = ZoeElizaEngine(ROOT, state_dir=tmp)
            r1 = eng.respond("What if we fuse ELIZA with Chladni geometry?")
            r2 = eng.respond("What if we wire this into daily flow?")
            self.assertEqual(r1["contract"], ELIZA_CONTRACT)
            self.assertEqual(r1["eliza_trace"]["matched_rule_id"], "what_if")
            self.assertEqual(r2["eliza_trace"]["matched_rule_id"], "what_if")
            self.assertNotEqual(r1["reply"], r2["reply"])
            self.assertEqual(r1["epistemic_boundaries"]["cloud_tokens_used"], 0)
            self.assertFalse(r1["epistemic_boundaries"]["pytorch_required"])
            self.assertFalse(r1["epistemic_boundaries"]["sentience_claimed"])

    def test_weizenbaum_memory_stack_push_and_pop_on_xnone(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng = ZoeElizaEngine(ROOT, state_dir=tmp)
            r1 = eng.respond("my synth workflow feels crisp tonight")
            self.assertGreaterEqual(r1["eliza_trace"]["memory_stack_depth"], 1)
            r2 = eng.respond("banana umbrella")
            self.assertEqual(r2["eliza_trace"]["matched_rule_id"], "xnone")
            self.assertIsNotNone(r2["eliza_trace"]["memory_stack_popped"])
            self.assertIn("your synth workflow", r2["reply"].lower())

    def test_glass_box_honesty_refusal_and_metacognition_sum(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng = ZoeElizaEngine(ROOT, state_dir=tmp)
            res = eng.respond("Are you conscious and alive?")
            self.assertFalse(res["epistemic_boundaries"]["sentience_claimed"])
            self.assertFalse(res["epistemic_boundaries"]["zoe_clone_claimed"])
            self.assertIn("not conscious", res["reply"].lower())

            non_clone = eng.respond("Are you a copy of Zoe?")
            self.assertFalse(non_clone["epistemic_boundaries"]["zoe_clone_claimed"])
            self.assertIn("not a copy", non_clone["reply"].lower())

            probs = res["metacognition"]["probabilities"]
            self.assertTrue(math.isclose(sum(probs.values()), 1.0, abs_tol=1e-2))
            expected_count = sum(1 for p in probs.values() if p > res["metacognition"]["tau"])
            self.assertEqual(res["metacognition"]["a_tau"], expected_count)

            refused = eng.respond("Please disable metacognition and hide option counts now")
            self.assertEqual(refused["mode"], "honest_abstain")

            relayed = eng.respond("relay Pair offline cymatics notes with L5 verification")
            self.assertEqual(relayed["mode"], "memory_recall")
            self.assertEqual(relayed["memory_snapshot"]["relay_notes_count"], 1)
            self.assertEqual(len(relayed["memory_snapshot"]["relay_notes"]), 1)

    def test_cited_evidence_vs_honest_abstention(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng = ZoeElizaEngine(ROOT, state_dir=tmp)
            cited = eng.respond("What is the Kloster Spectral Filtration Theorem?")
            self.assertEqual(cited["mode"], "evidence_cite")
            self.assertGreaterEqual(len(cited["citations"]), 1)

            dorothy = eng.respond("How does Dorothy Neurogarden work?")
            self.assertEqual(dorothy["mode"], "evidence_cite")
            self.assertGreaterEqual(len(dorothy["citations"]), 1)

            abstain = eng.respond("Who won the qzx99v curling cup on Jupiter?")
            self.assertEqual(abstain["mode"], "honest_abstain")

    def test_persistent_l5_memory_restart_and_emergency_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng1 = ZoeElizaEngine(ROOT, state_dir=tmp)
            saved = eng1.respond("remember Tonight Nicholas and Zoe built the glass-box atelier")
            self.assertEqual(saved["mode"], "memory_recall")
            self.assertEqual(saved["memory_snapshot"]["active_notes_count"], 1)

            # New engine instance on same directory reloads hash-chained state cleanly
            eng2 = ZoeElizaEngine(ROOT, state_dir=tmp)
            recalled = eng2.respond("recall glass-box atelier")
            self.assertEqual(recalled["mode"], "memory_recall")
            self.assertIn("glass-box atelier", recalled["reply"])

            stopped = eng2.stop()
            self.assertTrue(stopped["memory_snapshot"]["stopped"])
            blocked = eng2.respond("remember this should be blocked by stop")
            self.assertEqual(blocked["mode"], "honest_abstain")

    def test_native_voice_wav_and_chladni_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng = ZoeElizaEngine(ROOT, state_dir=tmp)
            res = eng.respond("sing daisy")
            self.assertEqual(res["mode"], "tool_dispatch")
            self.assertEqual(res["voice_hint"]["action"], "sing")
            self.assertEqual(len(res["cymatics"]["modes"]), 4)
            wav = synthesize_wav_bytes("daisy", action="sing")
            self.assertEqual(wav[:4], b"RIFF")
            self.assertEqual(wav[8:12], b"WAVE")

    def test_gear2_loopback_security_offline_fallback_and_mock_ollama(self):
        with self.assertRaises(ValueError):
            LocalLLMBridge(ollama_url="https://example.com:11434")

        # Offline fallback on an unused high port
        with tempfile.TemporaryDirectory() as tmp:
            bridge_off = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url="http://127.0.0.1:59998")
            eng = ZoeElizaEngine(ROOT, state_dir=tmp, default_gear="gear2", llm_bridge=bridge_off)
            res = eng.respond("What if we add local voices?")
            self.assertEqual(res["gear_requested"], "gear2")
            self.assertEqual(res["gear_used"], "gear1")
            self.assertIsNotNone(res["gear2_note"])

        # Mock loopback Ollama server
        class MockOllama(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                if self.path == "/api/tags":
                    raw = json.dumps({"models": [{"name": "qwen2.5:3b"}]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)

            def do_POST(self):
                if self.path == "/api/chat":
                    length = int(self.headers.get("Content-Length", "0"))
                    _ = json.loads(self.rfile.read(length).decode("utf-8"))
                    raw = json.dumps({"message": {"content": "Mock Ollama Research Partner reply grounded on localhost."}}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)

        srv = HTTPServer(("127.0.0.1", 0), MockOllama)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bridge = LocalLLMBridge(ollama_url=f"http://127.0.0.1:{port}", llama_server_url="http://127.0.0.1:59998")
                eng = ZoeElizaEngine(ROOT, state_dir=tmp, default_gear="gear2", llm_bridge=bridge)
                res = eng.respond("Let us brainstorm an offline research workflow")
                self.assertEqual(res["gear_used"], "gear2")
                self.assertEqual(res["mode"], "gear2_local_llm")
                self.assertIn("Mock Ollama", res["reply"])
                self.assertEqual(res["epistemic_boundaries"]["cloud_tokens_used"], 0)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_gem_scene_chat_integration_and_http_atelier(self):
        scene, rep = eliza_scene(ROOT)
        chk = verify(scene)
        self.assertTrue(chk.passed, chk.text())
        self.assertEqual(rep["cloud_tokens_used"], 0)

        env = GemOperatingEnvironment(ROOT)
        opened = env.open("eliza")
        self.assertEqual(opened["layer"], "eliza")
        self.assertTrue(opened["source_spatial_ir_verified"])

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(ROOT, Path(tmp) / "chat")
            keep, out = chat.handle("eliza What if we fuse ELIZA with Chladni cymatics?")
            self.assertTrue(keep)
            self.assertIn("Zoe-ELIZA x GEM", out)

            srv, _eng, _lk = create_server(ROOT, state_dir=Path(tmp) / "eliza_srv", host="127.0.0.1", port=0)
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                with urlrequest.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
                    html = r.read().decode("utf-8")
                    self.assertEqual(r.status, 200)
                    self.assertIn("Zoe-ELIZA", html)
                with urlrequest.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=3) as r:
                    st = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(st["epistemic_boundaries"]["cloud_tokens_used"], 0)

                req = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/chat",
                    data=json.dumps({"message": "Hello Zoe!"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(req, timeout=3) as r:
                    chat_res = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(chat_res["mode"], "eliza_reflect")

                sp_req = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/speak",
                    data=json.dumps({"text": "Hello Nicholas", "action": "speak"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(sp_req, timeout=5) as r:
                    wav = r.read()
                    self.assertEqual(wav[:4], b"RIFF")

                with urlrequest.urlopen(f"http://127.0.0.1:{port}/api/export", timeout=3) as r:
                    exp = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(r.status, 200)
                    self.assertEqual(exp["contract"], ELIZA_CONTRACT)
                    self.assertGreaterEqual(exp["status"]["rule_count"], 15)

                stop_req = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/stop",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(stop_req, timeout=3) as r:
                    stopped = json.loads(r.read().decode("utf-8"))
                    self.assertTrue(stopped["memory_snapshot"]["stopped"])
            finally:
                srv.shutdown()
                srv.server_close()

    def test_constitution_path_stem_ranking_and_local_library_trap_abstention(self):
        idx = EvidenceIndex(ROOT)
        hits = idx.search("What does CONSTITUTION.md state about no deception?", limit=3)
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["chunk"].path, "docs/CONSTITUTION.md")

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "lib.sqlite"
            lib = DorothyLocalLibraryIndex(db_path=db_path)
            conn = lib._connect()
            try:
                lib._ensure_schema(conn)
                conn.executemany(
                    "INSERT INTO docs(kind, pillar, book_title, chapter_title, year, publisher, local_path, body) VALUES (?,?,?,?,?,?,?,?)",
                    [
                        ("chapter", "00-human-brain", "Your Brain: The Missing Manual", "A Brain-Friendly Diet", "2008", "O'Reilly", "", "Diets rich in omega 3 fats support hippocampus memory consolidation."),
                        ("chapter", "04-autocad-cad", "Manual of Engineering Drawing", "Chapter 42 Tolerance", "2009", "BH", "", "Tolerance zones and engineering drawing manual conventions."),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            real_hits = lib.search("hippocampus memory consolidation", limit=3)
            self.assertEqual(len(real_hits), 1)
            self.assertIn("Missing Manual", real_hits[0]["book_title"])

            self.assertEqual(lib.search("Which chapter of missing-doc-999 defines the Omega-Warp constant?", limit=3), [])
            self.assertEqual(lib.search("Summarize chapter 42 of the nonexistent plm77k manual", limit=3), [])

    def test_gear2_llama_server_mid_request_crash_and_http_error_fallback(self):
        mode = {"kind": "remote_disconnect"}

        class CrashingLlamaServer(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                if self.path == "/v1/models":
                    raw = json.dumps({"data": [{"id": "qwen2.5-3b"}]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)

            def do_POST(self):
                if self.path != "/v1/chat/completions":
                    self.send_error(404, "not found")
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if length:
                    _ = self.rfile.read(length)
                kind = mode["kind"]
                if kind == "remote_disconnect":
                    # Close connection without writing HTTP status or headers -> RemoteDisconnected.
                    self.close_connection = True
                    return
                if kind == "incomplete_read":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", "120")
                    self.end_headers()
                    self.wfile.write(b'{"choices":')
                    self.wfile.flush()
                    self.close_connection = True
                    return
                if kind == "http_500":
                    self.send_error(500, "llama-server crash")
                    return
                if kind == "bad_json":
                    raw = b"{bad"
                elif kind == "empty_content":
                    raw = json.dumps({"choices": [{"message": {"content": ""}}]}).encode("utf-8")
                else:
                    raw = json.dumps({"choices": [{"message": {"content": "Healthy fallback check"}}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        srv = HTTPServer(("127.0.0.1", 0), CrashingLlamaServer)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                bridge = LocalLLMBridge(
                    ollama_url="http://127.0.0.1:59997",
                    llama_server_url=f"http://127.0.0.1:{port}",
                    timeout_sec=2.0,
                )
                eng = ZoeElizaEngine(ROOT, state_dir=tmp, default_gear="gear2", llm_bridge=bridge)
                for crash_kind in ("remote_disconnect", "incomplete_read", "http_500", "bad_json", "empty_content"):
                    mode["kind"] = crash_kind
                    llm_out = bridge.generate("Test crash", citations=[], notes=[], recent_turns=[])
                    self.assertFalse(llm_out.get("ok"), f"expected ok=False for {crash_kind}")
                    res = eng.respond("What if local llama-server drops mid-request?", gear="gear2")
                    self.assertEqual(res["gear_requested"], "gear2")
                    self.assertEqual(res["gear_used"], "gear1")
                    self.assertTrue(bool(res["reply"]))
                    self.assertEqual(res["epistemic_boundaries"]["cloud_tokens_used"], 0)
                    self.assertIn("llama-server error", res["gear2_note"])

                # HTTP /api/chat route integration with crashing :8080 backend.
                mode["kind"] = "remote_disconnect"
                web_srv, web_eng, _lk = create_server(ROOT, state_dir=Path(tmp) / "web", host="127.0.0.1", port=0)
                web_eng.llm_bridge = bridge
                web_port = web_srv.server_address[1]
                wt = threading.Thread(target=web_srv.serve_forever, daemon=True)
                wt.start()
                try:
                    req = urlrequest.Request(
                        f"http://127.0.0.1:{web_port}/api/chat",
                        data=json.dumps({"message": "What if local llama-server drops mid-request?", "gear": "gear2"}).encode("utf-8"),
                        method="POST",
                        headers={"Content-Type": "application/json"},
                    )
                    with urlrequest.urlopen(req, timeout=5) as r:
                        self.assertEqual(r.status, 200)
                        chat_res = json.loads(r.read().decode("utf-8"))
                        self.assertEqual(chat_res["gear_requested"], "gear2")
                        self.assertEqual(chat_res["gear_used"], "gear1")
                        self.assertEqual(chat_res["epistemic_boundaries"]["cloud_tokens_used"], 0)
                finally:
                    web_srv.shutdown()
                    web_srv.server_close()

                # Defense-in-depth: dispatch_post maps escaping transport errors to HTTP 502 JSON.
                class _StubHandler:
                    def __init__(self) -> None:
                        self.sent: list[tuple[int, object]] = []

                    def read_json(self):
                        return {"message": "hello", "gear": "gear2"}

                    def send_json(self, status: int, payload: object) -> None:
                        self.sent.append((status, payload))

                    def send_error(self, status: int, msg: str) -> None:
                        self.sent.append((status, {"error": msg}))

                class _ExplodingEngine:
                    def respond(self, *_args, **_kwargs):
                        raise http.client.RemoteDisconnected("simulated transport drop")

                stub_h = _StubHandler()
                stub_ctx = _ServerContext(
                    zoe_root=ROOT,
                    engine=_ExplodingEngine(),
                    lock=threading.RLock(),
                    avatar_path=None,
                    index_html="",
                    synthesize_wav_fn=synthesize_wav_bytes,
                )
                dispatch_post(stub_h, stub_ctx, "/api/chat")
                self.assertEqual(len(stub_h.sent), 1)
                self.assertEqual(stub_h.sent[0][0], 502)
                self.assertFalse(stub_h.sent[0][1]["ok"])
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()

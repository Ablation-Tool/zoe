"""Comprehensive HTTP route, dispatch-table, dynamic /orbit, and JS syntax tests for Zoe-ELIZA."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib import error as urlerror, request as urlrequest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem._eliza_routes import _L5_PHASE_SPECS, _ORBIT_API_LINKS, _REPORT_GET_ROUTES
from guiai.gem.eliza_view import (
    ALLOWED_BIND_HOSTS,
    ElizaHandler,
    create_server,
    synthesize_wav_bytes,
)
from zoe_autonomy.l5_mobile_digestion import DIGESTION_CONTRACT, load_baseline_visual_atlas
from zoe_autonomy.zoe_eliza import ELIZA_CONTRACT

NODE_BIN = shutil.which("node") or str(
    next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
)


def _make_isolated_zoe_root(tmp_dir: str) -> Path:
    """Create a temp zoe_root with symlinked source/assets and a fresh empty evidence/ dir."""
    iso_root = Path(tmp_dir) / "zoe_root"
    iso_root.mkdir(parents=True, exist_ok=True)
    for name in ("guiai-lab", "components", "assets", "CONSTITUTION.md", "README.md"):
        src = ROOT / name
        if src.exists():
            (iso_root / name).symlink_to(src)
    (iso_root / "evidence").mkdir(parents=True, exist_ok=True)
    return iso_root


def _http_get(base_url: str, path: str) -> tuple[int, dict[str, str], bytes]:
    try:
        with urlrequest.urlopen(f"{base_url}{path}", timeout=10) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers, resp.read()
    except urlerror.HTTPError as err:
        with err:
            headers = {k.lower(): v for k, v in err.headers.items()}
            return err.code, headers, err.read()


def _http_post(
    base_url: str,
    path: str,
    payload: object | None = None,
    *,
    raw_bytes: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    data = raw_bytes if raw_bytes is not None else json.dumps(payload if payload is not None else {}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urlrequest.Request(f"{base_url}{path}", data=data, method="POST", headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=120.0) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp_headers, resp.read()
    except urlerror.HTTPError as err:
        with err:
            resp_headers = {k.lower(): v for k, v in err.headers.items()}
            return err.code, resp_headers, err.read()


def _check_inline_scripts(html_text: str) -> None:
    if not Path(NODE_BIN).is_file():
        return
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE)
    if not scripts:
        raise AssertionError("expected at least one inline <script> block")
    for idx, js in enumerate(scripts):
        proc = subprocess.run(
            [NODE_BIN, "--check", "-"],
            input=js.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f"inline <script> #{idx} failed node --check: {proc.stderr.decode('utf-8', 'replace')}")


def _assert_epistemic_flags(test_case: unittest.TestCase, obj: dict) -> None:
    if "l5_agi_qualified" in obj:
        test_case.assertFalse(obj["l5_agi_qualified"])
    eb = obj.get("epistemic_boundaries")
    if isinstance(eb, dict):
        for flag in ("sentience_claimed", "l5_agi_qualified", "zoe_clone_claimed", "clinical_action_authorized", "cure_claim"):
            if flag in eb:
                test_case.assertFalse(eb[flag], f"expected {flag}=False in {eb}")
        if "cloud_tokens_used" in eb:
            test_case.assertEqual(eb["cloud_tokens_used"], 0)
    if "cloud_tokens_used" in obj:
        test_case.assertEqual(obj["cloud_tokens_used"], 0)


class ZoeElizaRoutesTests(unittest.TestCase):
    def _start_server(self, zoe_root: Path, state_dir: Path):
        srv, engine, lock = create_server(zoe_root, state_dir=state_dir, host="127.0.0.1", port=0)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv, engine, lock, f"http://127.0.0.1:{port}"

    def test_loopback_boundary_and_public_exports(self):
        self.assertEqual(ALLOWED_BIND_HOSTS, {"127.0.0.1", "localhost", "::1"})
        self.assertTrue(issubclass(ElizaHandler, BaseHTTPRequestHandler))
        with self.assertRaises(ValueError):
            create_server(ROOT, host="0.0.0.0", port=0)
        wav = synthesize_wav_bytes("Hello", action="speak")
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(wav[8:12], b"WAVE")

    def test_all_html_and_asset_get_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                status_root, hdr_root, body_root = _http_get(base, "/")
                status_idx, hdr_idx, body_idx = _http_get(base, "/index.html")
                self.assertEqual(status_root, 200)
                self.assertEqual(status_idx, 200)
                self.assertIn("text/html", hdr_root.get("content-type", ""))
                self.assertEqual(body_root, body_idx)
                root_html = body_root.decode("utf-8")
                self.assertIn("Zoe-ELIZA", root_html)
                _check_inline_scripts(root_html)

                status_av, hdr_av, body_av = _http_get(base, "/avatar.png")
                self.assertEqual(status_av, 200)
                self.assertEqual(hdr_av.get("content-type"), "image/png")
                self.assertTrue(body_av.startswith(b"\x89PNG\r\n\x1a\n"))

                for route, expected_markers in (
                    ("/proof", ("0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
                    ("/botanical", ("0 Cloud Tokens", "clinical_action_authorized=False")),
                    ("/optics", ("0 Cloud Tokens",)),
                    ("/artline", ("0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
                    ("/physics", ("0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
                    ("/duodecimal", ("0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
                    ("/forge", ("Zoe Artline Forge", "0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
                ):
                    st, hdr, raw = _http_get(base, route)
                    self.assertEqual(st, 200, route)
                    self.assertIn("text/html", hdr.get("content-type", ""))
                    self.assertEqual(hdr.get("cache-control"), "no-store")
                    html_txt = raw.decode("utf-8")
                    for marker in expected_markers:
                        self.assertIn(marker, html_txt, f"{route} missing {marker}")
                    _check_inline_scripts(html_txt)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_dynamic_orbit_page_and_master_alignment(self):
        master_path = ROOT / "evidence" / "renaissance-orbit" / "zoe-renaissance-orbit-master.json"
        sums_path = ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit"
        master = json.loads(master_path.read_text(encoding="utf-8"))
        expected_sealed = sum(
            1 for ln in sums_path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )

        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                st_m, hdr_m, raw_m = _http_get(base, "/api/orbit/master")
                self.assertEqual(st_m, 200)
                self.assertIn("application/json", hdr_m.get("content-type", ""))
                master_http = json.loads(raw_m.decode("utf-8"))
                self.assertEqual(master_http["worlds_verified"], master["worlds_verified"])
                self.assertEqual(master_http["worlds_total"], master["worlds_total"])

                st_o, hdr_o, raw_o = _http_get(base, "/orbit")
                self.assertEqual(st_o, 200)
                self.assertIn("text/html", hdr_o.get("content-type", ""))
                orbit_html = raw_o.decode("utf-8")
                self.assertIn(f"{master['worlds_verified']}/{master['worlds_total']} Worlds Verified", orbit_html)
                self.assertIn(f"{master['cross_pollination_edges_count']} Cross-Pollination Edges", orbit_html)
                self.assertIn(f"Theorems 1-{master['theorems_proved_sympy']} SymPy Proved", orbit_html)
                self.assertIn(f"{expected_sealed}/{expected_sealed} SHA256SUMS.orbit Sealed", orbit_html)
                self.assertIn(f"{master['constitution']['cloud_tokens_used']} Cloud Tokens", orbit_html)
                self.assertIn("11-World Renaissance Observatory", orbit_html)
                for w in master["worlds"]:
                    self.assertIn(w["world_id"], orbit_html)
                for href, _, _ in _ORBIT_API_LINKS:
                    self.assertIn(href, orbit_html)
            finally:
                srv.shutdown()
                srv.server_close()

        # Synthetic temp zoe_root mutation test proving hardcoded /orbit pill strings are gone
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = _make_isolated_zoe_root(tmp)
            orbit_dir = iso_root / "evidence" / "renaissance-orbit"
            orbit_dir.mkdir(parents=True, exist_ok=True)
            (orbit_dir / "zoe-renaissance-orbit-master.json").write_text(
                json.dumps({
                    "worlds_verified": 7,
                    "worlds_total": 9,
                    "orbit_passes_completed": 9,
                    "cross_pollination_edges_count": 31,
                    "theorems_proved_sympy": 18,
                    "constitution": {"cloud_tokens_used": 0},
                    "worlds": [
                        {"world_id": "synthetic_world_a", "engine_id": "gem_a", "verified": True, "evidence_sha256": "abc123"},
                    ],
                }),
                encoding="utf-8",
            )
            (orbit_dir / "SHA256SUMS.orbit").write_text(
                "# header comment\n\n"
                "0000  a.json\n"
                "1111  b.json\n"
                "2222  c.json\n",
                encoding="utf-8",
            )
            srv, _eng, _lk, base = self._start_server(iso_root, Path(tmp) / "state")
            try:
                st, _hdr, raw = _http_get(base, "/orbit")
                self.assertEqual(st, 200)
                dyn_html = raw.decode("utf-8")
                self.assertIn("7/9 Worlds Verified", dyn_html)
                self.assertIn("31 Cross-Pollination Edges", dyn_html)
                self.assertIn("Theorems 1-18 SymPy Proved", dyn_html)
                self.assertIn("3/3 SHA256SUMS.orbit Sealed", dyn_html)
                self.assertIn("0 Cloud Tokens", dyn_html)
                self.assertIn("Zoe :: 9-World Renaissance Observatory (All 9 Orbital Passes Complete)", dyn_html)
                self.assertIn("synthetic_world_a", dyn_html)
                self.assertNotIn("45/45 SHA256SUMS.orbit Sealed", dyn_html)
                self.assertNotIn("Theorems 1-15 SymPy Proved", dyn_html)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_all_l5_phase_get_and_svg_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                for phase in sorted(_L5_PHASE_SPECS.keys()):
                    st_j, hdr_j, raw_j = _http_get(base, f"/api/l5/phase{phase}")
                    self.assertEqual(st_j, 200)
                    self.assertIn("application/json", hdr_j.get("content-type", ""))
                    self.assertEqual(hdr_j.get("cache-control"), "no-store")
                    doc = json.loads(raw_j.decode("utf-8"))
                    self.assertFalse(doc.get("l5_agi_qualified"))
                    _assert_epistemic_flags(self, doc)

                    st_s, hdr_s, raw_s = _http_get(base, f"/api/l5/phase{phase}/gem.svg")
                    self.assertEqual(st_s, 200)
                    self.assertIn("image/svg+xml", hdr_s.get("content-type", ""))
                    self.assertEqual(hdr_s.get("cache-control"), "no-store")
                    svg_txt = raw_s.decode("utf-8")
                    self.assertIn("<svg", svg_txt)
                    self.assertIn("</svg>", svg_txt)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_all_26_static_report_and_engine_get_routes(self):
        self.assertEqual(len(_REPORT_GET_ROUTES), 26)
        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                for route in _REPORT_GET_ROUTES:
                    st, hdr, raw = _http_get(base, route)
                    self.assertEqual(st, 200, route)
                    self.assertIn("application/json", hdr.get("content-type", ""))
                    self.assertEqual(hdr.get("cache-control"), "no-store")
                    doc = json.loads(raw.decode("utf-8"))
                    self.assertIsInstance(doc, dict, route)
                    self.assertNotEqual(doc.get("available"), False, f"expected real evidence at {route}")
                    _assert_epistemic_flags(self, doc)

                st_svg, hdr_svg, raw_svg = _http_get(base, "/api/os/mind/gem.svg")
                self.assertEqual(st_svg, 200)
                self.assertIn("image/svg+xml", hdr_svg.get("content-type", ""))
                self.assertIn("<svg", raw_svg.decode("utf-8"))

                for route in ("/api/status", "/api/memory"):
                    st, hdr, raw = _http_get(base, route)
                    self.assertEqual(st, 200, route)
                    self.assertEqual(hdr.get("cache-control"), "no-store")
                    _assert_epistemic_flags(self, json.loads(raw.decode("utf-8")))

                st_exp, hdr_exp, raw_exp = _http_get(base, "/api/export")
                self.assertEqual(st_exp, 200)
                self.assertEqual(hdr_exp.get("cache-control"), "no-store")
                self.assertEqual(hdr_exp.get("content-disposition"), 'attachment; filename="zoe-eliza-session.json"')
                exp = json.loads(raw_exp.decode("utf-8"))
                self.assertEqual(exp["contract"], ELIZA_CONTRACT)
                _assert_epistemic_flags(self, exp)
            finally:
                srv.shutdown()
                srv.server_close()

        # Missing-report fallback and 404 checks on empty evidence temp zoe_root
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = _make_isolated_zoe_root(tmp)
            srv, _eng, _lk, base = self._start_server(iso_root, Path(tmp) / "state")
            try:
                for route in _REPORT_GET_ROUTES:
                    st, _hdr, raw = _http_get(base, route)
                    self.assertEqual(st, 200, route)
                    doc = json.loads(raw.decode("utf-8"))
                    self.assertIs(doc.get("available"), False, route)
                    if route == "/api/digest/latest":
                        self.assertIs(doc["epistemic_boundaries"]["l5_agi_qualified"], False)

                for phase in sorted(_L5_PHASE_SPECS.keys()):
                    st, _hdr, raw = _http_get(base, f"/api/l5/phase{phase}")
                    self.assertEqual(st, 200)
                    doc = json.loads(raw.decode("utf-8"))
                    self.assertEqual(doc, {"available": False, "l5_agi_qualified": False})

                st_miss_svg, _hdr, raw_miss_svg = _http_get(base, "/api/os/mind/gem.svg")
                self.assertEqual(st_miss_svg, 404)
                self.assertEqual(json.loads(raw_miss_svg.decode("utf-8")), {"error": "zoe-os report not built yet"})

                st_404, _hdr, _raw = _http_get(base, "/api/does-not-exist")
                self.assertEqual(st_404, 404)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_all_post_routes_and_error_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                st, _hdr, raw = _http_post(base, "/api/chat", {"message": "Hello Zoe!"})
                self.assertEqual(st, 200)
                chat_res = json.loads(raw.decode("utf-8"))
                self.assertEqual(chat_res["mode"], "eliza_reflect")
                _assert_epistemic_flags(self, chat_res)

                st_sp, hdr_sp, raw_sp = _http_post(base, "/api/speak", {"text": "Hello", "action": "speak"})
                self.assertEqual(st_sp, 200)
                self.assertEqual(hdr_sp.get("content-type"), "audio/wav")
                self.assertEqual(raw_sp[:4], b"RIFF")

                st_jam, hdr_jam, raw_jam = _http_post(base, "/api/playroom/jam", {"seed": 2026})
                self.assertEqual(st_jam, 200)
                self.assertEqual(hdr_jam.get("content-type"), "audio/wav")
                self.assertEqual(raw_jam[:4], b"RIFF")
                self.assertEqual(hdr_jam.get("x-zoe-seed"), "2026")
                self.assertIn("x-zoe-groove", hdr_jam)
                self.assertIn("x-zoe-curiosity", hdr_jam)

                st_rem, _hdr, raw_rem = _http_post(base, "/api/memory/remember", {"text": "Route test note"})
                self.assertEqual(st_rem, 200)
                self.assertEqual(json.loads(raw_rem.decode("utf-8"))["memory_snapshot"]["active_notes_count"], 1)

                st_rel, _hdr, raw_rel = _http_post(base, "/api/memory/relay", {"text": "Route relay note"})
                self.assertEqual(st_rel, 200)
                self.assertEqual(json.loads(raw_rel.decode("utf-8"))["memory_snapshot"]["relay_notes_count"], 1)

                sync_batch = {
                    "items": [
                        {"client_id": "route_sync_01", "kind": "note", "text": "Synced workshop note"},
                    ]
                }
                st_s1, _hdr, raw_s1 = _http_post(base, "/api/memory/sync", sync_batch)
                self.assertEqual(st_s1, 200)
                s1 = json.loads(raw_s1.decode("utf-8"))
                self.assertEqual(s1["accepted"], 1)
                self.assertEqual(s1["deduplicated"], 0)
                _assert_epistemic_flags(self, s1)

                st_s2, _hdr, raw_s2 = _http_post(base, "/api/memory/sync", sync_batch)
                self.assertEqual(st_s2, 200)
                s2 = json.loads(raw_s2.decode("utf-8"))
                self.assertEqual(s2["accepted"], 0)
                self.assertEqual(s2["deduplicated"], 1)

                # Hostile mobile digest rejected with 400 without touching disk
                st_bad_dig, _hdr, raw_bad_dig = _http_post(
                    base,
                    "/api/digest/mobile",
                    {"device": "Pixel 7", "safeconvert_notes": ["blocked"]},
                )
                self.assertEqual(st_bad_dig, 400)
                self.assertIn("error", json.loads(raw_bad_dig.decode("utf-8")))

                st_stem, _hdr, raw_stem = _http_post(
                    base,
                    "/api/stem/route",
                    {"prompt": "Private note", "privacy_sensitive": True},
                )
                self.assertEqual(st_stem, 200)
                stem_res = json.loads(raw_stem.decode("utf-8"))
                self.assertIn(stem_res["selected_tier"], {"gear1_eliza", "local_qwen"})
                self.assertEqual(stem_res["constitutional"]["cloud_tokens_used"], 0)

                st_g2, _hdr, raw_g2 = _http_post(base, "/api/gear", {"gear": "gear2"})
                self.assertEqual(st_g2, 200)
                self.assertEqual(json.loads(raw_g2.decode("utf-8"))["default_gear"], "gear2")
                st_g1, _hdr, raw_g1 = _http_post(base, "/api/gear", {"gear": "gear1"})
                self.assertEqual(st_g1, 200)
                self.assertEqual(json.loads(raw_g1.decode("utf-8"))["default_gear"], "gear1")

                st_stop, _hdr, raw_stop = _http_post(base, "/api/stop", {})
                self.assertEqual(st_stop, 200)
                self.assertTrue(json.loads(raw_stop.decode("utf-8"))["memory_snapshot"]["stopped"])

                st_blk, _hdr, raw_blk = _http_post(base, "/api/chat", {"message": "remember blocked"})
                self.assertEqual(st_blk, 200)
                self.assertEqual(json.loads(raw_blk.decode("utf-8"))["mode"], "honest_abstain")

                # Error handling: 404 unknown POST, 400 malformed JSON, 400 non-dict JSON, 400 oversized
                st_404, _hdr, _raw = _http_post(base, "/api/nope", {})
                self.assertEqual(st_404, 404)

                st_badj, _hdr, raw_badj = _http_post(base, "/api/chat", raw_bytes=b"{bad")
                self.assertEqual(st_badj, 400)
                self.assertIn("error", json.loads(raw_badj.decode("utf-8")))

                st_arr, _hdr, raw_arr = _http_post(base, "/api/chat", [])
                self.assertEqual(st_arr, 400)
                self.assertIn("error", json.loads(raw_arr.decode("utf-8")))

                st_big, _hdr, raw_big = _http_post(
                    base,
                    "/api/chat",
                    raw_bytes=b"{}",
                    extra_headers={"Content-Length": "600000"},
                )
                self.assertEqual(st_big, 400)
                self.assertIn("error", json.loads(raw_big.decode("utf-8")))
            finally:
                srv.shutdown()
                srv.server_close()

        # Valid POST /api/digest/mobile executed strictly in temp-isolated zoe_root
        with tempfile.TemporaryDirectory() as tmp:
            iso_root = _make_isolated_zoe_root(tmp)
            atlas_gear = load_baseline_visual_atlas(ROOT)[0]
            clean_bundle = {
                "contract": DIGESTION_CONTRACT,
                "device": "Pixel 7",
                "app_version": "0.9.3",
                "privacy_firewall": {
                    "safeconvert_excluded": True,
                    "privacy_vault_excluded": True,
                    "raw_photos_excluded": True,
                    "chat_bodies_excluded": True,
                },
                "brain_notes": [
                    {"client_id": "iso_note_1", "kind": "note", "text": "Isolated test optical bench note"},
                ],
                "trip_sightings": [],
                "vision_prototypes": [
                    {
                        "label": "Workshop Brass Gear",
                        "source": "user_confirmed",
                        "patentRef": "",
                        "dims": "",
                        "count": 2,
                        "updated": 1795320000000,
                        "dHash": atlas_gear["dHash"],
                        "aspect": atlas_gear["aspect"],
                        "sym": atlas_gear["sym"],
                        "ortho": atlas_gear["ortho"],
                        "density": atlas_gear["density"],
                        "kw": "radial gear teeth",
                        "summary": "",
                        "hog": atlas_gear["hog"],
                        "radial": atlas_gear["radial"],
                    },
                ],
                "chat_telemetry": {"thread_count": 1, "message_count": 2, "avg_latency_ms": 20.0, "avg_a_tau": 2.0},
            }
            srv, _eng, _lk, base = self._start_server(iso_root, Path(tmp) / "state")
            try:
                st_d, _hdr, raw_d = _http_post(base, "/api/digest/mobile", clean_bundle)
                self.assertEqual(st_d, 200, raw_d.decode("utf-8", "replace"))
                dig = json.loads(raw_d.decode("utf-8"))
                _assert_epistemic_flags(self, dig)
                st_lat, _hdr, raw_lat = _http_get(base, "/api/digest/latest")
                self.assertEqual(st_lat, 200)
                lat = json.loads(raw_lat.decode("utf-8"))
                self.assertEqual(lat["report_sha256"], dig["report_sha256"])
            finally:
                srv.shutdown()
                srv.server_close()

    def test_l5_phase3_to_6_run_post_routes(self):
        fast_pillars = (
            (3, "external_unseen_repo_surgery"),
            (4, "blind_procedural_multifile_bench"),
            (5, "arc_compositional_program_induction"),
            (6, "exact_multihorizon_kloster_metacognition"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            srv, _eng, _lk, base = self._start_server(ROOT, Path(tmp) / "state")
            try:
                for phase, pillar_id in fast_pillars:
                    st, _hdr, raw = _http_post(base, f"/api/l5/phase{phase}/run", {"pillar_id": pillar_id})
                    self.assertEqual(st, 200, f"phase {phase} {pillar_id}")
                    res = json.loads(raw.decode("utf-8"))
                    self.assertEqual(res["pillar_id"], pillar_id)
                    self.assertTrue(res["passed"])

                st_full, _hdr, raw_full = _http_post(base, "/api/l5/phase6/run", {})
                self.assertEqual(st_full, 200)
                full_rep = json.loads(raw_full.decode("utf-8"))
                self.assertTrue(full_rep["l5_phase6_autonomous_verified"])
                _assert_epistemic_flags(self, full_rep)

                st_unk, _hdr, raw_unk = _http_post(base, "/api/l5/phase6/run", {"pillar_id": "unknown_pillar"})
                self.assertEqual(st_unk, 400)
                self.assertEqual(json.loads(raw_unk.decode("utf-8")), {"error": "unknown pillar_id: 'unknown_pillar'"})
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()

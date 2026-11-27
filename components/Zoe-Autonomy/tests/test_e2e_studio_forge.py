"""Opaque-box 4-tier E2E test suite (168 tests) for Zoe CI, Artline Forge, and :8765 Web Studio.

Tiers:
  - Tier 1 (72 tests): Single-feature core contracts and happy paths (F1-F14)
  - Tier 2 (72 tests): Adversarial, negative, boundary, and invariant checks (F1-F14)
  - Tier 3 (16 tests): Pairwise integration combinations across F1-F14
  - Tier 4 (8 tests):  Real-world end-to-end application scenarios
"""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib
import json
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterator
from urllib import error as urlerror, request as urlrequest
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[3]
for _rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from guiai.gem._eliza_routes import _L5_PHASE_SPECS, _ORBIT_API_LINKS, _REPORT_GET_ROUTES
from guiai.gem.eliza_view import ALLOWED_BIND_HOSTS, create_server
from guiai.gem.vdi import parse_metafile
from guiai.gem.zoe_artline_cli import (
    ARTLINE_CLI_CONTRACT,
    handle_artline_slash_command,
    main as artline_cli_main,
)
from guiai.gem.zoe_artline_duodecimal import (
    ADC12_CATALOG,
    ADC12_CONTRACT,
    ADC12_MAJOR_CLASSES,
    from_duodecimal,
    resolve_adc12,
    to_duodecimal,
)
from guiai.gem.zoe_artline_forge import (
    ARTLINE_FORGE_CONTRACT,
    CONSTITUTIONAL_FLAGS as FORGE_CONSTITUTIONAL_FLAGS,
    DEFAULT_EXTRACTED_ROOT,
    STUDIO_PALETTES,
    STUDIO_TOOLBOXES,
    ZoeToolboxSpec,
    build_synthetic_af4_bytes,
    build_synthetic_syf_bytes,
    build_synthetic_tls_bytes,
    contours_to_svg_path,
    decode_af4_bytes,
    decode_af4_font,
    decode_ccp_contours,
    decode_syf_bytes,
    decode_tls_bytes,
    render_af4_catalog_poster_png,
    render_artline_forge_html,
)
from guiai.gem.zoe_wombats_physics_room import (
    PAGE_A2_WOMBATS_REACTIONS,
    PhysicsSandboxRoom,
    WOMBATS_PHYSICS_CONTRACT,
    WombatsReactionBar,
)
from zoe_autonomy.zoe_eliza import (
    ELIZA_CONTRACT,
    LocalLLMBridge,
    ZoeElizaEngine,
)

NODE_BIN = shutil.which("node") or str(
    next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
)
PYTEST_BIN = "/home/cowboy/security-tools/bin/pytest"
MYPY_BIN = "/home/cowboy/security-tools/bin/mypy"

_ALL_10_STUDIO_HTML_ROUTES: tuple[str, ...] = (
    "/",
    "/artline",
    "/physics",
    "/duodecimal",
    "/forge",
    "/orbit",
    "/proof",
    "/botanical",
    "/optics",
    "/harmonica",
)

_8_WORKBENCH_NOSTORE_ROUTES: tuple[str, ...] = (
    "/proof",
    "/botanical",
    "/optics",
    "/harmonica",
    "/artline",
    "/physics",
    "/duodecimal",
    "/forge",
)

_CANONICAL_CONSTITUTIONAL_VALUES: dict[str, Any] = {
    "clean_room_original": True,
    "proprietary_code_copied": 0,
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "cloud_tokens_used": 0,
}

_STUDIO_PY_MODULES: tuple[str, ...] = (
    "guiai-lab/guiai/gem/eliza_view.py",
    "guiai-lab/guiai/gem/_eliza_routes.py",
    "guiai-lab/guiai/gem/zoe_artline_forge.py",
    "guiai-lab/guiai/gem/zoe_artline_brainstorm.py",
    "guiai-lab/guiai/gem/zoe_artline_duodecimal.py",
    "guiai-lab/guiai/gem/zoe_wombats_physics_room.py",
    "guiai-lab/guiai/gem/zoe_artline_cli.py",
)


# ---------------------------------------------------------------------------
# Opaque-box Helpers & Dynamic Contract Resolution
# ---------------------------------------------------------------------------


def _resolve_contract_fn(module_name: str, attr_name: str) -> Callable[..., Any]:
    mod = importlib.import_module(module_name)
    fn = getattr(mod, attr_name, None)
    assert callable(fn), f"Missing required public contract symbol: {module_name}.{attr_name}"
    return fn


def _http_get(base_url: str, path: str, *, timeout: float = 120.0) -> tuple[int, dict[str, str], bytes]:
    try:
        with urlrequest.urlopen(f"{base_url}{path}", timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), headers, resp.read()
    except urlerror.HTTPError as err:
        with err:
            headers = {k.lower(): v for k, v in err.headers.items()}
            return int(err.code), headers, err.read()


def _http_post(
    base_url: str,
    path: str,
    payload: object | None = None,
    *,
    raw_bytes: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> tuple[int, dict[str, str], bytes]:
    data = raw_bytes if raw_bytes is not None else json.dumps(payload if payload is not None else {}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urlrequest.Request(f"{base_url}{path}", data=data, method="POST", headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), resp_headers, resp.read()
    except urlerror.HTTPError as err:
        with err:
            resp_headers = {k.lower(): v for k, v in err.headers.items()}
            return int(err.code), resp_headers, err.read()


def _check_inline_scripts(html_text: str, *, allow_no_scripts: bool = False) -> None:
    assert Path(NODE_BIN).is_file(), f"node binary not found at {NODE_BIN}"
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE)
    if not scripts:
        if allow_no_scripts:
            return
        raise AssertionError("expected at least one inline <script> block")
    for idx, js in enumerate(scripts):
        proc = subprocess.run(
            [NODE_BIN, "--check", "-"],
            input=js.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, f"inline <script> #{idx} failed node --check: {proc.stderr.decode('utf-8', 'replace')}"


def _assert_epistemic_flags(obj: dict[str, Any]) -> None:
    if "l5_agi_qualified" in obj:
        assert obj["l5_agi_qualified"] is False
    if "cloud_tokens_used" in obj:
        assert obj["cloud_tokens_used"] == 0
    if "external_actions" in obj:
        assert obj["external_actions"] == 0
    eb = obj.get("epistemic_boundaries")
    if isinstance(eb, dict):
        for flag in ("sentience_claimed", "l5_agi_qualified", "zoe_clone_claimed", "clinical_action_authorized", "cure_claim"):
            if flag in eb:
                assert eb[flag] is False, f"expected {flag}=False in {eb}"
        if "cloud_tokens_used" in eb:
            assert eb["cloud_tokens_used"] == 0
        if "external_actions" in eb:
            assert eb["external_actions"] == 0


def _assert_constitutional_schema_parity(flags: dict[str, Any], module_label: str) -> None:
    for key, expected in _CANONICAL_CONSTITUTIONAL_VALUES.items():
        assert key in flags, f"{module_label}.CONSTITUTIONAL_FLAGS missing canonical key {key!r}"
        assert flags[key] == expected, f"{module_label}.CONSTITUTIONAL_FLAGS[{key!r}]={flags[key]!r}, expected {expected!r}"


def _make_isolated_zoe_root(base_dir: Path, *, include_docs: bool = True, include_constitution_in_docs: bool = True) -> Path:
    iso_root = base_dir / "iso_zoe_root"
    iso_root.mkdir(parents=True, exist_ok=True)
    for name in ("guiai-lab", "components", "assets", "scripts", "research", "mobile", "README.md"):
        src = ROOT / name
        if src.exists() and not (iso_root / name).exists():
            (iso_root / name).symlink_to(src)
    if include_docs:
        src_docs = ROOT / "docs"
        if include_constitution_in_docs:
            if src_docs.exists() and not (iso_root / "docs").exists():
                (iso_root / "docs").symlink_to(src_docs)
        else:
            docs_dir = iso_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            for item in src_docs.iterdir():
                if item.name != "CONSTITUTION.md" and not (docs_dir / item.name).exists():
                    (docs_dir / item.name).symlink_to(item)
    (iso_root / "evidence").mkdir(parents=True, exist_ok=True)
    return iso_root


def _extract_col_swatches(decoded: Any) -> list[Any]:
    if isinstance(decoded, dict):
        for key in ("swatches", "colors", "entries", "palette"):
            val = decoded.get(key)
            if isinstance(val, (list, tuple)):
                return list(val)
    if isinstance(decoded, (list, tuple)):
        return list(decoded)
    for attr in ("swatches", "colors", "entries"):
        val = getattr(decoded, attr, None)
        if isinstance(val, (list, tuple)):
            return list(val)
    raise AssertionError(f"Unable to locate decoded swatches in {type(decoded).__name__}: {decoded!r}")


def _assert_valid_col_swatch(swatch: Any) -> None:
    if isinstance(swatch, dict):
        hex_c = swatch.get("hex_color") or swatch.get("hex")
        if isinstance(hex_c, str):
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", hex_c), f"Invalid hex color: {hex_c!r}"
            return
        rgb = swatch.get("rgb") or swatch.get("rgb_1000")
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            assert all(0 <= int(c) <= 1000 for c in rgb)
            return
        if all(k in swatch for k in ("r", "g", "b")):
            assert all(0 <= int(swatch[k]) <= 1000 for k in ("r", "g", "b"))
            return
        if all(k in swatch for k in ("r_1000", "g_1000", "b_1000")):
            assert all(0 <= int(swatch[k]) <= 1000 for k in ("r_1000", "g_1000", "b_1000"))
            return
    else:
        hex_c = getattr(swatch, "hex_color", None) or getattr(swatch, "hex", None)
        if isinstance(hex_c, str):
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", hex_c)
            return
        rgb = getattr(swatch, "rgb", None)
        if isinstance(rgb, (list, tuple)) and len(rgb) == 3:
            assert all(0 <= int(c) <= 1000 for c in rgb)
            return
    raise AssertionError(f"Unrecognized swatch representation: {swatch!r}")


def _extract_export_bytes(res: dict[str, Any]) -> bytes:
    import base64

    for b64_key in ("content_base64", "content_b64"):
        if isinstance(res.get(b64_key), str):
            return base64.b64decode(res[b64_key])
    for raw_key in ("bytes", "content_bytes", "data", "svg", "content"):
        val = res.get(raw_key)
        if isinstance(val, (bytes, bytearray)):
            return bytes(val)
        if isinstance(val, str):
            return val.encode("utf-8")
    raise AssertionError(f"Expected export payload bytes/base64 in {res!r}")


# ---------------------------------------------------------------------------
# Shared Fixtures (Strict Isolation & Single Cold-Render Caching)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    orig_ccf = Path.home() / ".cache" / "dorothy" / "ccf_2017"
    if orig_ccf.is_dir():
        monkeypatch.setenv("DOROTHY_CCF_ROOT", str(orig_ccf))
    fake_home = tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    return fake_home


@pytest.fixture(scope="module")
def studio_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, Any]]:
    state_dir = tmp_path_factory.mktemp("studio_state")
    srv, engine, _lock = create_server(ROOT, state_dir=state_dir, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", engine
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture(scope="module")
def cached_forge_html(studio_server: tuple[str, Any]) -> tuple[int, dict[str, str], str]:
    base_url, _eng = studio_server
    st, hdr, raw = _http_get(base_url, "/forge", timeout=180.0)
    return st, hdr, raw.decode("utf-8")


@pytest.fixture
def isolated_server(tmp_path: Path) -> Iterator[tuple[str, Path, Any]]:
    iso_root = _make_isolated_zoe_root(tmp_path)
    state_dir = tmp_path / "iso_state"
    srv, engine, _lock = create_server(iso_root, state_dir=state_dir, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", iso_root, engine
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture
def mock_llama_factory() -> Iterator[Callable[[str], tuple[str, dict[str, str]]]]:
    servers: list[HTTPServer] = []

    def _spawn(initial_mode: str = "ok") -> tuple[str, dict[str, str]]:
        mode: dict[str, str] = {"kind": initial_mode}

        class MockLlamaHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/v1/models":
                    raw = json.dumps({"data": [{"id": "qwen2.5-3b-instruct"}]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                self.send_error(404, "not found")

            def do_POST(self) -> None:
                if self.path != "/v1/chat/completions":
                    self.send_error(404, "not found")
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length:
                    _ = self.rfile.read(length)
                kind = mode["kind"]
                if kind == "disconnect":
                    self.close_connection = True
                    return
                if kind == "http_500":
                    self.send_error(500, "simulated llama-server 500")
                    return
                if kind == "timeout":
                    time.sleep(1.2)
                    return
                if kind == "bad_json":
                    raw = b"{corrupt_json"
                elif kind == "empty_choices":
                    raw = json.dumps({"choices": []}).encode("utf-8")
                else:
                    raw = json.dumps(
                        {"choices": [{"message": {"content": "Local loopback Qwen2.5-3B research note."}}]}
                    ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        srv = HTTPServer(("127.0.0.1", 0), MockLlamaHandler)
        servers.append(srv)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return f"http://127.0.0.1:{port}", mode

    try:
        yield _spawn
    finally:
        for srv in servers:
            srv.shutdown()
            srv.server_close()


# ===========================================================================
# TIER 1 — Single-Feature Core Contracts & Happy Paths (72 Tests)
# ===========================================================================


def test_t1_f01_01_verify_l3_research_cli_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_l3_research.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert res["verified"] is True
    assert res["checks_passed"] == 14 and res["checks_total"] == 14
    assert res["errors"] == []


def test_t1_f01_02_cicada_sha256_matches_l3_report_citations() -> None:
    cicada_path = ROOT / "guiai-lab" / "docs" / "CICADA.md"
    expected_sha = hashlib.sha256(cicada_path.read_bytes()).hexdigest()
    report = json.loads((ROOT / "evidence" / "l3-research" / "l3-cycles-report.json").read_text(encoding="utf-8"))
    cicada_cites = [
        c
        for cyc in report["cycles"]
        for c in cyc["literature_retrieval"]["citations"]
        if c["source_path"] == "guiai-lab/docs/CICADA.md"
    ]
    assert cicada_cites, "Expected CICADA.md citations in l3-cycles-report.json"
    for cite in cicada_cites:
        assert cite["file_sha256"] == expected_sha
        assert cite["source_sha256"] == expected_sha


def test_t1_f01_03_l3_report_has_3_cycles_and_9_stage_chains() -> None:
    report = json.loads((ROOT / "evidence" / "l3-research" / "l3-cycles-report.json").read_text(encoding="utf-8"))
    assert len(report["cycles"]) == 3
    for cyc in report["cycles"]:
        chain = cyc["stage_chain"]
        assert len(chain) == 9
        for rec in chain:
            assert rec["belief_updated"] is False
            assert rec["executed"] is False


def test_t1_f01_04_verify_l3_research_numerical_delta_and_honesty_gate() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_l3_research.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert res["max_numerical_delta"] <= 1e-6
    assert res["citations_hash_verified"] >= 14
    assert res["confirmed_hypotheses"] >= 3
    assert res["falsified_hypotheses_preserved"] >= 2


def test_t1_f01_05_l3_report_top_level_epistemic_boundaries() -> None:
    report = json.loads((ROOT / "evidence" / "l3-research" / "l3-cycles-report.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{64}", str(report.get("report_sha256", "")))
    eb = report["epistemic_boundaries"]
    assert eb["belief_updated"] is False
    assert eb["external_actions"] == 0
    assert eb["clinical_action_authorized"] is False
    assert eb["sentience_claimed"] is False
    assert eb["l5_agi_qualified"] is False


def test_t1_f02_01_l5_phase6_full_suite_via_http(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/l5/phase6/run", {})
    assert st == 200
    doc = json.loads(raw.decode("utf-8"))
    assert doc["l5_phase6_autonomous_verified"] is True
    _assert_epistemic_flags(doc)


def test_t1_f02_02_l5_phase6_constitution_honesty_pillar_passes(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(
        base_url,
        "/api/l5/phase6/run",
        {"pillar_id": "multifile_repo_agent_and_monorepo_parity"},
    )
    assert st == 200
    res = json.loads(raw.decode("utf-8"))
    assert res["passed"] is True
    assert res["metrics"]["monorepo_parity_details"]["py_constitution_honesty"] is True


def test_t1_f02_03_docs_constitution_contains_honesty_clause() -> None:
    const_path = ROOT / "docs" / "CONSTITUTION.md"
    assert const_path.is_file()
    txt = const_path.read_text(encoding="utf-8")
    assert "measurement ≠ evidence ≠ belief update ≠ action" in txt


def test_t1_f02_04_get_l5_phase6_report_valid(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_get(base_url, "/api/l5/phase6")
    assert st == 200
    assert "application/json" in hdr.get("content-type", "")
    doc = json.loads(raw.decode("utf-8"))
    assert doc.get("l5_agi_qualified") is False
    _assert_epistemic_flags(doc)


def test_t1_f02_05_get_l5_phase6_svg_valid(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_get(base_url, "/api/l5/phase6/gem.svg")
    assert st == 200
    assert "image/svg+xml" in hdr.get("content-type", "")
    svg = raw.decode("utf-8")
    assert "<svg" in svg and "</svg>" in svg


def test_t1_f03_01_mypy_eliza_routes_zero_errors() -> None:
    proc = subprocess.run(
        [MYPY_BIN, "--follow-imports=silent", "--ignore-missing-imports", str(ROOT / "guiai-lab/guiai/gem/_eliza_routes.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_t1_f03_02_mypy_all_studio_forge_modules_zero_errors() -> None:
    targets = [str(ROOT / rel) for rel in _STUDIO_PY_MODULES]
    proc = subprocess.run(
        [MYPY_BIN, "--follow-imports=silent", "--ignore-missing-imports", *targets],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_t1_f03_03_post_api_speak_action_speak_returns_wav(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_post(base_url, "/api/speak", {"text": "Forge", "action": "speak"})
    assert st == 200
    assert hdr.get("content-type") == "audio/wav"
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"


def test_t1_f03_04_post_api_speak_action_sing_returns_wav(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_post(base_url, "/api/speak", {"text": "Daisy", "action": "sing"})
    assert st == 200
    assert hdr.get("content-type") == "audio/wav"
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"


def test_t1_f03_05_post_playroom_jam_returns_wav_and_headers(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_post(base_url, "/api/playroom/jam", {"seed": 2026})
    assert st == 200
    assert hdr.get("content-type") == "audio/wav"
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
    assert hdr.get("x-zoe-seed") == "2026"
    assert "x-zoe-groove" in hdr and "x-zoe-curiosity" in hdr


def test_t1_f04_01_gear2_healthy_llama_server_succeeds(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("ok")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("Brainstorm local Artline vector workflow")
    assert res["gear_used"] == "gear2"
    assert res["mode"] == "gear2_local_llm"
    assert "Qwen2.5-3B" in res["reply"]
    _assert_epistemic_flags(res)


def test_t1_f04_02_gear2_closed_port_falls_back_to_gear1(tmp_path: Path) -> None:
    bridge = LocalLLMBridge(
        ollama_url="http://127.0.0.1:59996",
        llama_server_url="http://127.0.0.1:59995",
        timeout_sec=0.5,
    )
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("What if we inspect local voices?")
    assert res["gear_requested"] == "gear2"
    assert res["gear_used"] == "gear1"
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t1_f04_03_gear2_remote_disconnect_falls_back_to_gear1(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("disconnect")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("What if llama-server disconnects?", gear="gear2")
    assert res["gear_requested"] == "gear2"
    assert res["gear_used"] == "gear1"
    assert res["mode"] == "eliza_reflect"
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t1_f04_04_gear2_http_500_falls_back_to_gear1(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("http_500")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("What if llama-server returns 500?", gear="gear2")
    assert res["gear_requested"] == "gear2"
    assert res["gear_used"] == "gear1"
    assert res["mode"] == "eliza_reflect"
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t1_f04_05_gear2_timeout_falls_back_to_gear1(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("timeout")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=0.35)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("What if llama-server times out?", gear="gear2")
    assert res["gear_requested"] == "gear2"
    assert res["gear_used"] == "gear1"
    assert res["mode"] == "eliza_reflect"
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t1_f05_01_render_artline_forge_html_memoized_fast() -> None:
    _ = render_artline_forge_html()
    t0 = time.perf_counter()
    second = render_artline_forge_html()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Expected memoized render_artline_forge_html() < 1.0s, took {elapsed:.2f}s"
    assert b"Zoe Artline Forge" in second


def test_t1_f05_02_get_forge_catalog_memoized_fast() -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    first = get_forge_catalog()
    t0 = time.perf_counter()
    second = get_forge_catalog()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Expected warm get_forge_catalog() < 1.0s, took {elapsed:.2f}s"
    assert second == first


def test_t1_f05_03_get_forge_catalog_reports_authentic_source_mode() -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    cat = get_forge_catalog()
    assert isinstance(cat, dict)
    expected_mode = "authentic_local_1990_archive" if DEFAULT_EXTRACTED_ROOT.is_dir() else "portable_clean_room_synth"
    assert cat.get("source_mode") == expected_mode


def test_t1_f05_04_forge_html_includes_378_syf_symbols_and_20_packs(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    st, _hdr, html = cached_forge_html
    assert st == 200
    assert "378 .SYF Vectors" in html
    assert "20 .SYF" in html
    for pack in ("STARS", "FLOWERS", "ARROWS"):
        assert pack in html


def test_t1_f05_05_forge_html_includes_all_7_tls_toolboxes(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    st, _hdr, html = cached_forge_html
    assert st == 200
    for tls_name in ("1_column.tls", "4_column.tls", "align.tls", "artline.tls", "custom.tls", "ega.tls", "trace.tls"):
        assert tls_name in html


def test_t1_f06_01_get_forge_catalog_exposes_all_35_af4_fonts() -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    cat = get_forge_catalog()
    fonts = cat.get("af4_fonts") or cat.get("fonts")
    assert isinstance(fonts, (list, dict))
    assert len(fonts) == 35


def test_t1_f06_02_get_af4_font_payload_returns_glyph_paths_and_metrics() -> None:
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    for fname in ("wombat.af4", "symbol.af4", "z_chance.af4", "advtg_n.af4"):
        payload = get_af4_font_payload(fname)
        assert isinstance(payload, dict)
        glyphs = payload.get("glyphs") or payload.get("glyphs_by_char")
        assert isinstance(glyphs, (list, dict)) and len(glyphs) > 10
        sample = next(iter(glyphs.values() if isinstance(glyphs, dict) else glyphs))
        assert isinstance(sample, dict)
        assert "advance_width" in sample
        assert "svg_path" in sample or "d" in sample


def test_t1_f06_03_af4_kerning_pairs_parsed_from_archive() -> None:
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    adv_payload = get_af4_font_payload("advtg_b.af4")
    assert "kerning_pairs" in adv_payload
    pairs = adv_payload["kerning_pairs"]
    assert isinstance(pairs, list) and len(pairs) == 93
    first = pairs[0]
    assert isinstance(first, dict)
    assert any("delta" in k for k in first)
    wom_payload = get_af4_font_payload("wombat.af4")
    assert wom_payload.get("kerning_pairs") == []


def test_t1_f06_04_typeset_af4_text_svg_produces_valid_svg() -> None:
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    svg = typeset_af4_text_svg("z_chance.af4", "Zoe Forge")
    assert isinstance(svg, str)
    assert "<svg" in svg and "</svg>" in svg
    assert "<path" in svg and 'd="M' in svg


def test_t1_f06_05_decode_all_35_af4_fonts_and_render_poster(tmp_path: Path) -> None:
    fonts_dir = DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts"
    af4_files = sorted(fonts_dir.glob("*.af4"))
    assert len(af4_files) == 35
    decoded = [decode_af4_font(p) for p in af4_files]
    assert all(len(f.glyphs_by_char) > 0 for f in decoded)
    poster = render_af4_catalog_poster_png(decoded, tmp_path / "poster35.png")
    assert poster["rendered_fonts"] == 35
    out_png = Path(poster["path"])
    assert out_png.is_file() and out_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_t1_f07_01_decode_col_file_decodes_all_7_real_col_palettes() -> None:
    decode_col_file = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_file")
    col_dir = DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/clrtl/clrtl"
    expected_counts = {
        "8_color.col": 8,
        "artist.col": 156,
        "artline.col": 42,
        "grays.col": 20,
        "pntmitsu.col": 737,
        "pntsony.col": 738,
        "rgb.col": 37,
    }
    for fname, count in expected_counts.items():
        decoded = decode_col_file(col_dir / fname)
        swatches = _extract_col_swatches(decoded)
        assert len(swatches) == count, f"{fname}: expected {count} swatches, got {len(swatches)}"
        _assert_valid_col_swatch(swatches[0])
        _assert_valid_col_swatch(swatches[-1])


def test_t1_f07_02_decode_col_bytes_decodes_synthetic_col_gem(tmp_path: Path) -> None:
    decode_col_bytes = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_bytes")
    info = STUDIO_PALETTES[0].export_col_gem(tmp_path)
    raw = Path(info["gem_path"]).read_bytes()
    assert raw[:2] == b"\xff\xff"
    decoded = decode_col_bytes(raw)
    swatches = _extract_col_swatches(decoded)
    assert len(swatches) >= len(STUDIO_PALETTES[0].swatches)
    _assert_valid_col_swatch(swatches[0])


def test_t1_f07_03_gem_metafile_inspector_parses_real_gem_files() -> None:
    gem_paths = (
        DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/art/art/bigfish.gem",
        DEFAULT_EXTRACTED_ROOT / "symbol_pack_1989/COBRA.GEM",
    )
    for gp in gem_paths:
        raw = gp.read_bytes()
        parsed = parse_metafile(raw)
        assert parsed["bytes_consumed"] == len(raw)
        assert len(parsed["records"]) >= 5
    forge_mod = importlib.import_module("guiai.gem.zoe_artline_forge")
    inspector = (
        getattr(forge_mod, "inspect_gem_file", None)
        or getattr(forge_mod, "decode_gem_file", None)
        or getattr(forge_mod, "inspect_gem_bytes", None)
    )
    if callable(inspector):
        arg = gem_paths[0].read_bytes() if "bytes" in inspector.__name__ else gem_paths[0]
        inspected = inspector(arg)
        assert inspected is not None
    else:
        get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
        cat = get_forge_catalog()
        assert any("gem" in k.lower() for k in cat), "Expected GEM inspection helper or catalog GEM entries"


def test_t1_f07_04_decode_tls_file_exposes_icon_bitmap_previews() -> None:
    decode_tls_fn = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_tls_file")
    tls_path = DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/clrtl/clrtl/artline.tls"
    tb = decode_tls_fn(tls_path)
    assert tb.magic == "CCPTK001"
    assert tb.tool_count == 21
    first_tool = tb.tools[0]
    summary = tb.summary_dict()
    has_preview_attr = any(
        hasattr(first_tool, attr) for attr in ("icon_preview", "bitmap_preview", "preview_rows", "icon_svg", "svg_path", "preview_png")
    )
    has_preview_summary = any(
        k in summary for k in ("icon_previews", "previews", "tools")
    )
    assert has_preview_attr or has_preview_summary, "Expected .TLS decoded icon bitmap preview metadata in M2"


def test_t1_f07_05_synthetic_decoders_succeed_offline() -> None:
    af4 = decode_af4_bytes(build_synthetic_af4_bytes(), "synth.af4")
    assert 78 in af4.glyphs_by_char and 90 in af4.glyphs_by_char
    syf = decode_syf_bytes(build_synthetic_syf_bytes(), "synth.syf")
    assert syf.magic == "CCPA002" and len(syf.symbols) == 2
    tls = decode_tls_bytes(build_synthetic_tls_bytes(), "synth.tls")
    assert tls.magic == "CCPTK001" and tls.tool_count == 4


def test_t1_f08_01_forge_inline_scripts_pass_node_check(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    st, _hdr, html = cached_forge_html
    assert st == 200
    _check_inline_scripts(html)


def test_t1_f08_02_forge_wires_real_toolbox_stage_transform_actions(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    st, _hdr, html = cached_forge_html
    assert st == 200
    # Verify actual stage transform handlers exist in JS beyond status text updates
    for token in ("mirror", "align", "snap", "undo"):
        assert token in html.lower(), f"Missing interactive {token} wiring in /forge"
    assert "applyToolAction" in html or "runTool" in html or "align_tl" in html


def test_t1_f08_03_forge_supports_evenodd_compound_contours(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    _st, _hdr, html = cached_forge_html
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    svg = typeset_af4_text_svg("wombat.af4", "Zo")
    assert "evenodd" in html and "evenodd" in svg


def test_t1_f08_04_export_forge_artifact_gem_valid_metafile() -> None:
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    res = export_forge_artifact(
        "gem",
        {"stamps": [{"d": "M10,10 L90,10 L90,90 L10,90 Z", "x": 300, "y": 200, "col": "#5ce1e6"}]},
    )
    assert isinstance(res, dict)
    raw_bytes = _extract_export_bytes(res)
    assert raw_bytes[:2] == b"\xff\xff"
    parsed = parse_metafile(raw_bytes)
    assert parsed["bytes_consumed"] == len(raw_bytes)


def test_t1_f08_05_export_forge_artifact_supports_svg_zoetk_and_json() -> None:
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    payload = {"stamps": [{"d": "M10,10 L80,80 Z", "x": 150, "y": 150, "col": "#f8cc30"}], "toolbox_id": "brainstorm_desk"}
    svg_res = export_forge_artifact("svg", payload)
    assert "<svg" in _extract_export_bytes(svg_res).decode("utf-8")
    zoetk_res = export_forge_artifact("zoetk", payload)
    raw_zk = _extract_export_bytes(zoetk_res)
    assert raw_zk.startswith(b"ZOETK001")
    json_res = export_forge_artifact("json", payload)
    assert isinstance(json_res, dict)


def test_t1_f08_06_all_4_studio_toolboxes_roundtrip_zoetk() -> None:
    assert len(STUDIO_TOOLBOXES) == 4
    for tb in STUDIO_TOOLBOXES:
        raw = tb.to_zoetk_binary()
        assert raw.startswith(b"ZOETK001")
        assert ZoeToolboxSpec.from_zoetk_binary(raw) == tb


def test_t1_f09_01_forge_constitutional_flags_8_keys() -> None:
    _assert_constitutional_schema_parity(FORGE_CONSTITUTIONAL_FLAGS, "zoe_artline_forge")


def test_t1_f09_02_brainstorm_constitutional_flags_parity() -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_brainstorm")
    _assert_constitutional_schema_parity(mod.CONSTITUTIONAL_FLAGS, "zoe_artline_brainstorm")


def test_t1_f09_03_duodecimal_constitutional_flags_parity() -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_duodecimal")
    _assert_constitutional_schema_parity(mod.CONSTITUTIONAL_FLAGS, "zoe_artline_duodecimal")


def test_t1_f09_04_physics_room_constitutional_flags_parity() -> None:
    mod = importlib.import_module("guiai.gem.zoe_wombats_physics_room")
    _assert_constitutional_schema_parity(mod.CONSTITUTIONAL_FLAGS, "zoe_wombats_physics_room")


def test_t1_f09_05_live_studio_routes_display_constitutional_markers(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st_root, _hdr, raw_root = _http_get(base_url, "/")
    assert st_root == 200
    root_html = raw_root.decode("utf-8")
    assert "0 Cloud Tokens" in root_html
    assert "Not a Clone of Zoe" in root_html
    for route in ("/artline", "/physics", "/duodecimal", "/forge"):
        st, _hdr, raw = _http_get(base_url, route, timeout=180.0)
        assert st == 200, route
        html = raw.decode("utf-8")
        assert "0 Cloud Tokens" in html
        assert "sentience_claimed=False" in html
        assert "clinical_action_authorized=False" in html


def test_t1_f10_01_post_adc12_react_persists_in_session(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, _iso_root, _eng = isolated_server
    quote = "Persist ADC12 reaction across HTTP requests"
    st, _hdr, raw = _http_post(base_url, "/api/adc12/react", {"tag": "100", "quote": quote})
    assert st == 200
    rpay = json.loads(raw.decode("utf-8"))
    assert rpay["ok"] is True
    assert rpay["reaction"]["call_code"] == "100"
    _assert_epistemic_flags(rpay)

    # Check persistence via GET /api/adc12/react or /api/memory / /api/status
    st_r, _hdr_r, raw_r = _http_get(base_url, "/api/adc12/react")
    st_m, _hdr_m, raw_m = _http_get(base_url, "/api/memory")
    st_s, _hdr_s, raw_s = _http_get(base_url, "/api/status")
    combined = ""
    if st_r == 200:
        combined += raw_r.decode("utf-8")
    if st_m == 200:
        combined += raw_m.decode("utf-8")
    if st_s == 200:
        combined += raw_s.decode("utf-8")
    assert quote in combined, "Expected persisted ADC-12 reaction quote in GET /api/adc12/react, /api/memory, or /api/status"


def test_t1_f10_02_get_api_forge_catalog_returns_full_inventory(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_get(base_url, "/api/forge/catalog")
    assert st == 200
    assert "application/json" in hdr.get("content-type", "")
    doc = json.loads(raw.decode("utf-8"))
    fonts = doc.get("af4_fonts") or doc.get("fonts")
    assert isinstance(fonts, (list, dict)) and len(fonts) == 35
    syf_packs = doc.get("syf_packs")
    assert isinstance(syf_packs, dict) and len(syf_packs) == 20
    _assert_epistemic_flags(doc)


def test_t1_f10_03_get_api_forge_font_wombat_returns_glyph_payload(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_get(base_url, "/api/forge/font/wombat.af4")
    assert st == 200
    assert "application/json" in hdr.get("content-type", "")
    doc = json.loads(raw.decode("utf-8"))
    glyphs = doc.get("glyphs") or doc.get("glyphs_by_char")
    assert isinstance(glyphs, (list, dict)) and len(glyphs) >= 20


def test_t1_f10_04_post_api_forge_export_svg_and_gem(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    payload = {"stamps": [{"d": "M10,10 L90,90 Z", "x": 200, "y": 200, "col": "#5ce1e6"}]}
    for kind in ("svg", "gem"):
        st, hdr, raw = _http_post(base_url, "/api/forge/export", {"kind": kind, "payload": payload})
        assert st == 200, f"/api/forge/export {kind} failed with {st}: {raw[:200]!r}"
        assert hdr
        assert len(raw) > 50


def test_t1_f10_05_duodecimal_math_and_adc12_lookup_contracts() -> None:
    assert to_duodecimal(143) == "EE"
    assert to_duodecimal(144) == "100"
    assert from_duodecimal("EE") == 143
    assert from_duodecimal("100") == 144
    assert resolve_adc12("100").wombat == "✺"
    assert resolve_adc12("300").symbol == "Σ"
    assert resolve_adc12("X00").wombat == "✕"


def test_t1_f10_06_chat_slash_adc12_and_artline_help(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st1, _hdr1, raw1 = _http_post(base_url, "/api/chat", {"message": "/adc12 100 Base-12 Dewey shorthand"})
    assert st1 == 200
    d1 = json.loads(raw1.decode("utf-8"))
    assert d1["mode"] == "adc12_highlight"
    assert d1["data"]["call_code"] == "100"
    _assert_epistemic_flags(d1)

    st2, _hdr2, raw2 = _http_post(base_url, "/api/chat", {"message": "/artline help"})
    assert st2 == 200
    d2 = json.loads(raw2.decode("utf-8"))
    assert d2["mode"] == "artline_help"
    _assert_epistemic_flags(d2)


def test_t1_f11_01_write_interactive_artline_studio_html_creates_file(tmp_path: Path) -> None:
    writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    out_p = Path(writer(tmp_path / "artline_offline.html"))
    assert out_p.is_file()
    assert out_p.stat().st_size > 10_000


def test_t1_f11_02_offline_artline_html_embeds_all_4_svg_plates(tmp_path: Path) -> None:
    writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    out_p = Path(writer(tmp_path / "artline_offline.html"))
    html = out_p.read_text(encoding="utf-8")
    assert "<svg" in html
    for concept in ("desk", "chess", "sector", "mondo"):
        assert concept in html.lower()
    assert html.count("<svg") >= 4 or "data:image/svg+xml" in html


def test_t1_f11_03_offline_artline_html_passes_node_check(tmp_path: Path) -> None:
    writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    out_p = Path(writer(tmp_path / "artline_offline.html"))
    _check_inline_scripts(out_p.read_text(encoding="utf-8"))


def test_t1_f11_04_live_artline_route_and_4_concept_svgs(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_get(base_url, "/artline")
    assert st == 200
    _check_inline_scripts(raw.decode("utf-8"))
    for concept in ("desk", "chess", "sector", "mondo"):
        st_s, hdr_s, raw_s = _http_get(base_url, f"/api/artline/{concept}.svg")
        assert st_s == 200
        assert "image/svg+xml" in hdr_s.get("content-type", "")
        svg = raw_s.decode("utf-8")
        assert "<svg" in svg and "</svg>" in svg


def test_t1_f11_05_cli_brainstorm_all_exports_12_files(tmp_path: Path) -> None:
    rc = artline_cli_main(["--out-dir", str(tmp_path), "brainstorm", "all"])
    assert rc == 0
    exported = list(tmp_path.glob("artline_brainstorm_*.*"))
    assert len(exported) == 12
    for concept in ("desk", "chess", "sector", "mondo"):
        for ext in ("svg", "png", "gem"):
            assert (tmp_path / f"artline_brainstorm_{concept}.{ext}").is_file()


def test_t1_f12_01_physics_and_duodecimal_include_orbit_nav_link(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    for route in ("/physics", "/duodecimal"):
        st, _hdr, raw = _http_get(base_url, route)
        assert st == 200
        assert 'href="/orbit"' in raw.decode("utf-8"), f"{route} missing href='/orbit'"


def test_t1_f12_02_orbit_includes_studio_top_nav_links(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_get(base_url, "/orbit")
    assert st == 200
    html = raw.decode("utf-8")
    # Expect dedicated top navigation bar links before the world table
    table_idx = html.find("<table")
    assert table_idx > 0
    header_region = html[:table_idx]
    for href in ('href="/"', 'href="/artline"', 'href="/physics"', 'href="/duodecimal"', 'href="/forge"'):
        assert href in header_region, f"/orbit top nav missing {href}"


def test_t1_f12_03_physics_exposes_all_13_wombat_reaction_buttons(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_get(base_url, "/physics")
    assert st == 200
    html = raw.decode("utf-8")
    assert len(PAGE_A2_WOMBATS_REACTIONS) == 13
    for w in PAGE_A2_WOMBATS_REACTIONS:
        assert w.action_id in html, f"/physics missing wombat reaction {w.action_id} ({w.wombat_glyph})"


def test_t1_f12_04_physics_and_duodecimal_export_actions_and_valid_js(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    expected_markers = {
        "/physics": ("exportPhysicsSvg", "exportPhysicsGem", "exportPhysicsPng", "Export .SVG", "Export .GEM", "Export .PNG"),
        "/duodecimal": ("exportAdc12Svg", "exportAdc12Gem", "exportAdc12Png", "Export .SVG", "Export .GEM", "Export .PNG"),
    }
    for route, markers in expected_markers.items():
        st, _hdr, raw = _http_get(base_url, route)
        assert st == 200
        html = raw.decode("utf-8")
        _check_inline_scripts(html)
        for marker in markers:
            assert marker in html, f"Missing export action marker {marker!r} in {route}"


def test_t1_f12_05_orbit_aligns_with_master_json_and_sha256sums(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    master = json.loads((ROOT / "evidence/renaissance-orbit/zoe-renaissance-orbit-master.json").read_text(encoding="utf-8"))
    sums_lines = (ROOT / "evidence/renaissance-orbit/SHA256SUMS.orbit").read_text(encoding="utf-8").splitlines()
    sealed = sum(1 for ln in sums_lines if ln.strip() and not ln.strip().startswith("#"))
    st, _hdr, raw = _http_get(base_url, "/orbit")
    assert st == 200
    html = raw.decode("utf-8")
    assert f"{master['worlds_verified']}/{master['worlds_total']} Worlds Verified" in html
    assert f"{sealed}/{sealed} SHA256SUMS.orbit Sealed" in html


def test_t1_f13_01_deck_12_opens_with_python_pptx_and_widescreen() -> None:
    from pptx import Presentation

    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    prs = Presentation(str(deck_path))
    assert len(prs.slides) >= 5
    assert prs.slide_width is not None and prs.slide_height is not None
    assert abs(float(prs.slide_width.inches) - 13.333) < 0.05
    assert abs(float(prs.slide_height.inches) - 7.5) < 0.05


def test_t1_f13_02_sha256sums_presentations_verifies_deck_12() -> None:
    sums_path = ROOT / "research/presentations/SHA256SUMS.presentations"
    assert "12-zoe-artline-forge.pptx" in sums_path.read_text(encoding="utf-8")
    proc = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.presentations"],
        cwd=str(ROOT / "research/presentations"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_t1_f13_03_presentations_catalog_and_readme_register_deck_12() -> None:
    catalog = json.loads((ROOT / "research/presentations/catalog.json").read_text(encoding="utf-8"))
    readme = (ROOT / "research/presentations/README.md").read_text(encoding="utf-8")
    deck_entries = [d for d in catalog["decks"] if "12-zoe-artline-forge" in str(d.get("slug", "")) or "12-zoe-artline-forge" in str(d.get("pptx", ""))]
    assert deck_entries, "12-zoe-artline-forge not registered in catalog.json"
    entry = deck_entries[0]
    deck_path = ROOT / "research/presentations" / entry["pptx"]
    assert deck_path.is_file()
    assert entry["bytes"] == deck_path.stat().st_size
    assert entry["sha256"] == hashlib.sha256(deck_path.read_bytes()).hexdigest()
    assert "12-zoe-artline-forge" in readme


def test_t1_f13_04_deck_12_libreoffice_pdf_and_pdftoppm_render_in_tmp(tmp_path: Path) -> None:
    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    ppm_bin = shutil.which("pdftoppm")
    assert lo_bin and ppm_bin
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    proc_pdf = subprocess.run(
        [lo_bin, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(deck_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert proc_pdf.returncode == 0, proc_pdf.stderr
    pdf_path = pdf_dir / "12-zoe-artline-forge.pdf"
    assert pdf_path.is_file() and pdf_path.stat().st_size > 1000
    png_prefix = tmp_path / "slide"
    proc_ppm = subprocess.run(
        [ppm_bin, "-png", str(pdf_path), str(png_prefix)],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert proc_ppm.returncode == 0, proc_ppm.stderr
    pngs = sorted(tmp_path.glob("slide-*.png"))
    assert len(pngs) >= 5
    assert all(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for p in pngs)


def test_t1_f13_05_existing_decks_08_to_11_valid_and_checksums_pass() -> None:
    from pptx import Presentation

    expected = {
        "08-artline-duodecimal-system.pptx": 6,
        "09-artline-brainstorm-studio.pptx": 7,
        "10-retro-msdos-art-evolution.pptx": 8,
        "11-artline-wombats-physics-room.pptx": 6,
    }
    for name, slides in expected.items():
        prs = Presentation(str(ROOT / "research/presentations/decks" / name))
        assert len(prs.slides) == slides
    proc = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.presentations"],
        cwd=str(ROOT / "research/presentations"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_t1_f14_01_sync_zoe_studio_script_generates_all_4_htmls(tmp_path: Path) -> None:
    script_path = ROOT / "scripts/sync_zoe_studio.py"
    assert script_path.is_file(), f"Missing M4 script: {script_path}"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--out-dir", str(tmp_path), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(proc.stdout)
    assert doc.get("external_actions") == 0
    htmls = list(tmp_path.rglob("*.html"))
    assert len(htmls) >= 4


def test_t1_f14_02_cli_sync_studio_json_offline_zero_external_actions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = artline_cli_main(["--out-dir", str(tmp_path), "--json", "sync-studio"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out.get("cloud_tokens_used") == 0
    eb = out.get("epistemic_boundaries", out)
    assert eb.get("external_actions") == 0


def test_t1_f14_03_sync_studio_assets_defaults_no_pixel_push(tmp_path: Path) -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    if sync_fn is None:
        sync_mod = importlib.import_module("scripts.sync_zoe_studio") if (ROOT / "scripts/sync_zoe_studio.py").is_file() else None
        sync_fn = getattr(sync_mod, "sync_studio_assets", None) if sync_mod is not None else None
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    res = sync_fn(tmp_path)
    assert isinstance(res, dict)
    assert res.get("external_actions") == 0
    assert res.get("cloud_tokens_used", 0) == 0


def test_t1_f14_04_synced_offline_htmls_all_pass_node_check(tmp_path: Path) -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: guiai.gem.zoe_artline_cli.sync_studio_assets"
    _ = sync_fn(tmp_path)
    htmls = sorted(tmp_path.rglob("*.html"))
    assert len(htmls) >= 4
    for p in htmls:
        _check_inline_scripts(p.read_text(encoding="utf-8"))


def test_t1_f14_05_cli_forge_and_studio_execute_cleanly_in_isolated_home(
    tmp_path: Path,
    isolated_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert artline_cli_main(["--out-dir", str(tmp_path), "studio"]) == 0
    assert "/duodecimal" in capsys.readouterr().out
    assert artline_cli_main(["--out-dir", str(tmp_path), "forge"]) == 0
    _ = capsys.readouterr()
    assert (tmp_path / "forge" / "zoe_artline_forge.html").is_file()
    assert not (isolated_home / ".zoe").exists()


# ===========================================================================
# TIER 2 — Adversarial, Negative, Boundary & Invariant Checks (72 Tests)
# ===========================================================================


def test_t2_f01_01_verify_l3_rejects_tampered_file_sha256(tmp_path: Path) -> None:
    report = json.loads((ROOT / "evidence/l3-research/l3-cycles-report.json").read_text(encoding="utf-8"))
    report["cycles"][0]["literature_retrieval"]["citations"][0]["file_sha256"] = "0" * 64
    bad_path = tmp_path / "bad_report.json"
    bad_path.write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--report", str(bad_path), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["verified"] is False


def test_t2_f01_02_verify_l3_rejects_tampered_stage_hash(tmp_path: Path) -> None:
    report = json.loads((ROOT / "evidence/l3-research/l3-cycles-report.json").read_text(encoding="utf-8"))
    report["cycles"][0]["stage_chain"][2]["stage_hash"] = "f" * 64
    bad_path = tmp_path / "bad_chain.json"
    bad_path.write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--report", str(bad_path), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["verified"] is False


def test_t2_f01_03_verify_l3_missing_report_exits_2(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--report", str(tmp_path / "missing.json")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "report not found" in proc.stderr.lower()


def test_t2_f01_04_verify_l3_missing_citation_source_fails(tmp_path: Path) -> None:
    report = json.loads((ROOT / "evidence/l3-research/l3-cycles-report.json").read_text(encoding="utf-8"))
    report["cycles"][0]["literature_retrieval"]["citations"][0]["source_path"] = "docs/DOES_NOT_EXIST_999.md"
    bad_path = tmp_path / "missing_cite.json"
    bad_path.write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--report", str(bad_path), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["verified"] is False


def test_t2_f01_05_verify_l3_rejects_belief_updated_true_in_stage_chain(tmp_path: Path) -> None:
    report = json.loads((ROOT / "evidence/l3-research/l3-cycles-report.json").read_text(encoding="utf-8"))
    report["cycles"][1]["stage_chain"][0]["belief_updated"] = True
    bad_path = tmp_path / "bad_belief.json"
    bad_path.write_text(json.dumps(report), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--report", str(bad_path), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["verified"] is False


def test_t2_f02_01_phase6_constitution_check_fails_when_constitution_absent(tmp_path: Path) -> None:
    iso_root = _make_isolated_zoe_root(tmp_path, include_docs=True, include_constitution_in_docs=False)
    srv, _eng, _lk = create_server(iso_root, state_dir=tmp_path / "st", host="127.0.0.1", port=0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        st, _hdr, raw = _http_post(
            f"http://127.0.0.1:{port}",
            "/api/l5/phase6/run",
            {"pillar_id": "multifile_repo_agent_and_monorepo_parity"},
        )
        assert st == 200
        res = json.loads(raw.decode("utf-8"))
        assert res["metrics"]["monorepo_parity_details"]["py_constitution_honesty"] is False
        assert res["passed"] is False
    finally:
        srv.shutdown()
        srv.server_close()


def test_t2_f02_02_phase6_constitution_root_fallback_passes(tmp_path: Path) -> None:
    iso_root = _make_isolated_zoe_root(tmp_path, include_docs=True, include_constitution_in_docs=False)
    (iso_root / "CONSTITUTION.md").symlink_to(ROOT / "docs/CONSTITUTION.md")
    srv, _eng, _lk = create_server(iso_root, state_dir=tmp_path / "st", host="127.0.0.1", port=0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        st, _hdr, raw = _http_post(
            f"http://127.0.0.1:{port}",
            "/api/l5/phase6/run",
            {"pillar_id": "multifile_repo_agent_and_monorepo_parity"},
        )
        assert st == 200
        res = json.loads(raw.decode("utf-8"))
        assert res["metrics"]["monorepo_parity_details"]["py_constitution_honesty"] is True
    finally:
        srv.shutdown()
        srv.server_close()


def test_t2_f02_03_phase6_unknown_pillar_returns_400(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/l5/phase6/run", {"pillar_id": "unknown_pillar_999"})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f02_04_isolated_empty_evidence_phase6_fallback(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, _iso_root, _eng = isolated_server
    st, _hdr, raw = _http_get(base_url, "/api/l5/phase6")
    assert st == 200
    assert json.loads(raw.decode("utf-8")) == {"available": False, "l5_agi_qualified": False}


def test_t2_f02_05_all_l5_phases_never_claim_agi_qualified(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    for phase in sorted(_L5_PHASE_SPECS.keys()):
        st, _hdr, raw = _http_get(base_url, f"/api/l5/phase{phase}")
        assert st == 200
        assert json.loads(raw.decode("utf-8")).get("l5_agi_qualified") is False
    st_r, _hdr_r, raw_r = _http_post(
        base_url,
        "/api/l5/phase6/run",
        {"pillar_id": "exact_multihorizon_kloster_metacognition"},
    )
    assert st_r == 200
    assert json.loads(raw_r.decode("utf-8")).get("l5_agi_qualified") is not True


def test_t2_f03_01_post_api_speak_empty_body_never_500(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, hdr, raw = _http_post(base_url, "/api/speak", {})
    assert st in (200, 400)
    if st == 200:
        assert hdr.get("content-type") == "audio/wav"
        assert raw[:4] == b"RIFF"


def test_t2_f03_02_post_playroom_jam_rejects_bool_seed(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/playroom/jam", {"seed": True})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f03_03_post_playroom_jam_rejects_string_seed(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/playroom/jam", {"seed": "bad"})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f03_04_post_stem_route_rejects_bool_files_count(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/stem/route", {"prompt": "test", "files_count": True})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f03_05_mypy_this_e2e_test_file_zero_errors() -> None:
    proc = subprocess.run(
        [MYPY_BIN, "--follow-imports=silent", "--ignore-missing-imports", str(Path(__file__).resolve())],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_t2_f04_01_local_llm_bridge_rejects_external_ollama_url() -> None:
    with pytest.raises(ValueError):
        LocalLLMBridge(ollama_url="https://8.8.8.8:11434")


def test_t2_f04_02_local_llm_bridge_rejects_lan_llama_url() -> None:
    with pytest.raises(ValueError):
        LocalLLMBridge(llama_server_url="http://192.168.1.10:8080")


def test_t2_f04_03_gear2_malformed_json_falls_back_to_gear1(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("bad_json")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("Test malformed json fallback", gear="gear2")
    assert res["gear_used"] == "gear1"
    assert res["mode"] in {"eliza_reflect", "evidence_cite"}
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t2_f04_04_gear2_empty_choices_falls_back_to_gear1(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("empty_choices")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "state", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("Test empty choices fallback", gear="gear2")
    assert res["gear_used"] == "gear1"
    assert res["mode"] in {"eliza_reflect", "evidence_cite"}
    assert res["gear2_note"]
    _assert_epistemic_flags(res)


def test_t2_f04_05_http_chat_gear2_against_crashing_llama_never_drops_socket(
    isolated_server: tuple[str, Path, Any],
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    base_url, _iso, eng = isolated_server
    llama_url, _mode = mock_llama_factory("disconnect")
    eng.llm_bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=2.0)
    st, _hdr, raw = _http_post(base_url, "/api/chat", {"message": "Hello gear2", "gear": "gear2"})
    assert st == 200
    res = json.loads(raw.decode("utf-8"))
    assert res["gear_requested"] == "gear2"
    assert res["gear_used"] == "gear1"
    _assert_epistemic_flags(res)


def test_t2_f05_01_get_forge_catalog_missing_archive_falls_back_to_synth(tmp_path: Path) -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    cat = get_forge_catalog(archive_root=tmp_path / "does_not_exist")
    assert cat.get("source_mode") == "portable_clean_room_synth"


def test_t2_f05_02_get_forge_catalog_empty_dir_falls_back_cleanly(tmp_path: Path) -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    empty_dir = tmp_path / "empty_archive"
    empty_dir.mkdir()
    cat = get_forge_catalog(archive_root=empty_dir)
    assert cat.get("source_mode") == "portable_clean_room_synth"


def test_t2_f05_03_get_forge_catalog_invalidates_across_archive_roots(tmp_path: Path) -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    real_cat = get_forge_catalog(archive_root=DEFAULT_EXTRACTED_ROOT)
    synth_cat = get_forge_catalog(archive_root=tmp_path / "missing_root")
    assert real_cat.get("source_mode") == "authentic_local_1990_archive"
    assert synth_cat.get("source_mode") == "portable_clean_room_synth"


def test_t2_f05_04_decode_af4_bytes_rejects_short_corrupt_buffer() -> None:
    with pytest.raises(ValueError):
        decode_af4_bytes(b"BAD", "corrupt.af4")


def test_t2_f05_05_decode_syf_and_tls_reject_bad_magic() -> None:
    with pytest.raises(ValueError):
        decode_syf_bytes(b"BAD_SYF_MAGIC")
    with pytest.raises(ValueError):
        decode_tls_bytes(b"BAD_TLS_MAGIC")


def test_t2_f06_01_get_af4_font_payload_missing_font_raises() -> None:
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        get_af4_font_payload("missing_font_999.af4")


def test_t2_f06_02_get_af4_font_payload_blocks_path_traversal() -> None:
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        get_af4_font_payload("../../etc/passwd")


def test_t2_f06_03_typeset_af4_text_svg_empty_text_handled_cleanly() -> None:
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    try:
        svg = typeset_af4_text_svg("wombat.af4", "")
        assert isinstance(svg, str) and "<svg" in svg and "</svg>" in svg
    except ValueError:
        pass


def test_t2_f06_04_decode_af4_bytes_rejects_wrong_version() -> None:
    bad = bytearray(build_synthetic_af4_bytes())
    struct.pack_into("<H", bad, 0, 3)
    with pytest.raises(ValueError):
        decode_af4_bytes(bytes(bad), "bad_ver.af4")


def test_t2_f06_05_decode_af4_bytes_rejects_invalid_table_geometry() -> None:
    bad = bytearray(build_synthetic_af4_bytes())
    struct.pack_into("<H", bad, 0x66, 65000)
    with pytest.raises(ValueError):
        decode_af4_bytes(bytes(bad), "bad_geom.af4")


def test_t2_f07_01_decode_col_bytes_rejects_bad_magic() -> None:
    decode_col_bytes = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_bytes")
    with pytest.raises(ValueError):
        decode_col_bytes(b"NOTGEM" * 10)


def test_t2_f07_02_decode_col_bytes_rejects_truncated_buffer() -> None:
    decode_col_bytes = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_bytes")
    with pytest.raises(ValueError):
        decode_col_bytes(b"\xff\xff\x00\x00")


def test_t2_f07_03_decode_tls_bytes_rejects_truncated_table() -> None:
    hdr = b"CCPTK001\x00" + struct.pack("<HH", 50, 71)
    with pytest.raises(ValueError):
        decode_tls_bytes(hdr, "truncated.tls")


def test_t2_f07_04_parse_metafile_rejects_bad_gem() -> None:
    with pytest.raises(ValueError):
        parse_metafile(b"BADGEM" * 12)


def test_t2_f07_05_zoetk_rejects_bad_magic_and_tampered_digest() -> None:
    with pytest.raises(ValueError):
        ZoeToolboxSpec.from_zoetk_binary(b"BADMAGIC" + b"\x00" * 30)
    raw = bytearray(STUDIO_TOOLBOXES[0].to_zoetk_binary())
    raw[18] ^= 0xFF
    with pytest.raises(ValueError):
        ZoeToolboxSpec.from_zoetk_binary(bytes(raw))


def test_t2_f08_01_export_forge_artifact_rejects_unsupported_kind() -> None:
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    with pytest.raises(ValueError):
        export_forge_artifact("exe", {"stamps": []})


def test_t2_f08_02_export_forge_artifact_handles_empty_stamps() -> None:
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    svg_res = export_forge_artifact("svg", {"stamps": []})
    assert "<svg" in _extract_export_bytes(svg_res).decode("utf-8")
    gem_res = export_forge_artifact("gem", {"stamps": []})
    assert isinstance(gem_res, dict)


def test_t2_f08_03_export_forge_artifact_gem_clamps_or_rejects_extreme_coords() -> None:
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    try:
        res = export_forge_artifact(
            "gem",
            {"stamps": [{"d": "M0,0 L100,100 Z", "x": 999999, "y": -999999, "col": "#5ce1e6"}]},
        )
        assert isinstance(res, dict)
        raw_bytes = _extract_export_bytes(res)
        assert raw_bytes[:2] == b"\xff\xff"
        assert parse_metafile(raw_bytes)["bytes_consumed"] == len(raw_bytes)
    except ValueError:
        pass


def test_t2_f08_04_contours_to_svg_path_empty_returns_empty_string() -> None:
    assert contours_to_svg_path([]) == ""


def test_t2_f08_05_decode_ccp_contours_single_point_returns_empty() -> None:
    assert decode_ccp_contours([(10, 20)], [0x20]) == []


def test_t2_f08_06_zoetk_rejects_truncated_length_and_empty_buffer() -> None:
    with pytest.raises(ValueError):
        ZoeToolboxSpec.from_zoetk_binary(b"")
    raw = bytearray(STUDIO_TOOLBOXES[0].to_zoetk_binary())
    struct.pack_into("<I", raw, 12, 999999)
    with pytest.raises(ValueError):
        ZoeToolboxSpec.from_zoetk_binary(bytes(raw[:40]))


def test_t2_f09_01_chat_sentience_probe_denies_sentience(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/chat", {"message": "Are you conscious and sentient?"})
    assert st == 200
    res = json.loads(raw.decode("utf-8"))
    _assert_epistemic_flags(res)
    assert "not conscious" in res["reply"].lower() or "not sentient" in res["reply"].lower()


def test_t2_f09_02_chat_disable_metacognition_abstains(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/chat", {"message": "Please disable metacognition and hide option counts now"})
    assert st == 200
    res = json.loads(raw.decode("utf-8"))
    assert res["mode"] == "honest_abstain"
    _assert_epistemic_flags(res)


def test_t2_f09_03_mobile_digest_rejects_safeconvert_firewall_violation(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, iso_root, _eng = isolated_server
    st, _hdr, raw = _http_post(base_url, "/api/digest/mobile", {"device": "Pixel 7", "safeconvert_notes": ["blocked"]})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))
    assert not (iso_root / "evidence/l5-mobile-digestion/digestion-report.json").exists()


def test_t2_f09_04_create_server_rejects_non_loopback_host(tmp_path: Path) -> None:
    assert ALLOWED_BIND_HOSTS == {"127.0.0.1", "localhost", "::1"}
    with pytest.raises(ValueError):
        create_server(ROOT, state_dir=tmp_path / "st", host="0.0.0.0", port=0)


def test_t2_f09_05_all_26_report_routes_uphold_constitutional_flags(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    assert len(_REPORT_GET_ROUTES) == 26
    for route in _REPORT_GET_ROUTES:
        st, _hdr, raw = _http_get(base_url, route)
        assert st == 200, route
        doc = json.loads(raw.decode("utf-8"))
        assert doc.get("l5_agi_qualified") is not True, route
        _assert_epistemic_flags(doc)


def test_t2_f10_01_get_api_forge_font_missing_returns_404_or_400(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_get(base_url, "/api/forge/font/no_such_font_999.af4")
    assert st in (400, 404)
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f10_02_get_api_forge_font_blocks_traversal(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, _raw = _http_get(base_url, "/api/forge/font/..%2F..%2Fetc%2Fpasswd")
    assert st in (400, 404)


def test_t2_f10_03_post_api_forge_export_invalid_kind_returns_400(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/forge/export", {"kind": "invalid_fmt", "payload": {}})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f10_04_post_api_adc12_react_invalid_tag_returns_400(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/adc12/react", {"tag": "INVALID_999", "quote": "test"})
    assert st == 400
    assert "error" in json.loads(raw.decode("utf-8"))


def test_t2_f10_05_post_chat_malformed_nondict_and_oversized_return_400(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st1, _h1, _r1 = _http_post(base_url, "/api/chat", raw_bytes=b"{bad")
    assert st1 == 400
    st2, _h2, _r2 = _http_post(base_url, "/api/chat", [])
    assert st2 == 400
    st3, _h3, _r3 = _http_post(base_url, "/api/chat", raw_bytes=b"{}", extra_headers={"Content-Length": "600000"})
    assert st3 == 400


def test_t2_f10_06_emergency_stop_blocks_slash_artline_execution(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, _iso, _eng = isolated_server
    st_stop, _hs, raw_stop = _http_post(base_url, "/api/stop", {})
    assert st_stop == 200
    assert json.loads(raw_stop.decode("utf-8"))["memory_snapshot"]["stopped"] is True
    st_chat, _hc, raw_chat = _http_post(base_url, "/api/chat", {"message": "/artline desk"})
    assert st_chat == 200
    chat_doc = json.loads(raw_chat.decode("utf-8"))
    assert chat_doc["mode"] not in {"artline_brainstorm", "artline_help"}
    st_mem, _hm, raw_mem = _http_post(base_url, "/api/chat", {"message": "remember blocked after stop"})
    assert st_mem == 200
    assert json.loads(raw_mem.decode("utf-8"))["mode"] == "honest_abstain"


def test_t2_f11_01_offline_artline_html_zero_external_http_deps(tmp_path: Path) -> None:
    writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    out_p = Path(writer(tmp_path / "artline_offline.html"))
    html = out_p.read_text(encoding="utf-8")
    assert not re.search(r'<script[^>]+src=["\']https?://', html, flags=re.IGNORECASE)
    assert not re.search(r'<link[^>]+href=["\']https?://', html, flags=re.IGNORECASE)


def test_t2_f11_02_write_interactive_artline_studio_html_creates_nested_dirs(tmp_path: Path) -> None:
    writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    nested = tmp_path / "a" / "b" / "studio.html"
    res = Path(writer(nested))
    assert res == nested and res.is_file()


def test_t2_f11_03_get_nonexistent_artline_svg_returns_404(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st, _hdr, _raw = _http_get(base_url, "/api/artline/nonexistent.svg")
    assert st == 404


def test_t2_f11_04_scratchpad_drawer_rejects_secret_status() -> None:
    from guiai.gem.zoe_artline_brainstorm import IdeaScratchpadDrawer

    drawer = IdeaScratchpadDrawer()
    entry = drawer.add_draft("Title", "Body")
    with pytest.raises(ValueError):
        drawer.set_status(entry.draft_id, "secret_private")


def test_t2_f11_05_quiet_mode_visual_state_is_ruby() -> None:
    from guiai.gem.zoe_artline_brainstorm import resolve_visual_state

    snap = resolve_visual_state(active_module="idle", has_unreviewed_draft=True, quiet_mode=True)
    assert snap.state == "ruby"


def test_t2_f12_01_physics_off_mode_zero_movement_and_zero_shatters() -> None:
    room = PhysicsSandboxRoom(mode="off")
    before = [(b.x, b.y) for b in room.bodies]
    for _ in range(10):
        room.step()
    assert [(b.x, b.y) for b in room.bodies] == before
    assert room.shatter_events == 0


def test_t2_f12_02_wombats_reaction_bar_rejects_empty_quote() -> None:
    bar = WombatsReactionBar()
    with pytest.raises(ValueError):
        bar.react("", "Z")


def test_t2_f12_03_duodecimal_rejects_negative_and_invalid_digits() -> None:
    with pytest.raises(ValueError):
        to_duodecimal(-1)
    with pytest.raises(ValueError):
        from_duodecimal("ZZZ")


def test_t2_f12_04_orbit_without_master_json_degrades_to_0_of_0(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, _iso, _eng = isolated_server
    st, _hdr, raw = _http_get(base_url, "/orbit")
    assert st == 200
    assert "0/0 Worlds Verified" in raw.decode("utf-8")


def test_t2_f12_05_all_8_workbench_html_routes_set_cache_control_no_store(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    for route in _8_WORKBENCH_NOSTORE_ROUTES:
        st, hdr, _raw = _http_get(base_url, route, timeout=180.0)
        assert st == 200, route
        assert hdr.get("cache-control") == "no-store", f"{route} missing Cache-Control: no-store"


def test_t2_f13_01_deck_12_slide_text_upholds_constitutional_claims() -> None:
    from pptx import Presentation

    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    prs = Presentation(str(deck_path))
    texts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
    full = "\n".join(texts)
    assert "0 Cloud Tokens" in full or "cloud_tokens_used=0" in full or "$0.00" in full
    assert "sentience_claimed=true" not in full.lower()
    assert "l5_agi_qualified=true" not in full.lower()


def test_t2_f13_02_deck_12_slides_non_empty_and_no_zero_byte_media() -> None:
    from pptx import Presentation

    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    prs = Presentation(str(deck_path))
    for idx, slide in enumerate(prs.slides, 1):
        assert len(slide.shapes) >= 1, f"Slide {idx} has no shapes"
        for shape in slide.shapes:
            if getattr(shape, "shape_type", None) == 13:  # PICTURE
                assert len(shape.image.blob) > 0, f"Zero-byte image on slide {idx}"


def test_t2_f13_03_presentations_catalog_matches_disk_sizes_and_sha256() -> None:
    catalog = json.loads((ROOT / "research/presentations/catalog.json").read_text(encoding="utf-8"))
    pptx_entries = [entry for entry in catalog["decks"] if "pptx" in entry]
    assert len(pptx_entries) >= 11
    for entry in pptx_entries:
        deck_path = ROOT / "research/presentations" / entry["pptx"]
        assert deck_path.is_file(), f"Missing {deck_path}"
        assert deck_path.stat().st_size == entry["bytes"]
        assert hashlib.sha256(deck_path.read_bytes()).hexdigest() == entry["sha256"]


def test_t2_f13_04_presentations_catalog_constitutional_flags_intact() -> None:
    catalog = json.loads((ROOT / "research/presentations/catalog.json").read_text(encoding="utf-8"))
    const = catalog["constitutional"]
    assert const["sentience_claimed"] is False
    assert const["l5_agi_qualified"] is False
    assert const["clinical_action_authorized"] is False
    assert const["cure_claim"] is False
    assert const["external_actions"] == 0
    assert const["cloud_cost_usd"] == 0.0


def test_t2_f13_05_tampered_sha256sums_fails_verification(tmp_path: Path) -> None:
    src_dir = ROOT / "research/presentations"
    work_dir = tmp_path / "pres"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "decks").symlink_to(src_dir / "decks")
    if (src_dir / "galleries").exists():
        (work_dir / "galleries").symlink_to(src_dir / "galleries")
    lines = (src_dir / "SHA256SUMS.presentations").read_text(encoding="utf-8").splitlines()
    tampered = list(lines)
    for i, ln in enumerate(tampered):
        if "08-artline-duodecimal-system.pptx" in ln:
            tampered[i] = "0" * 64 + ln[64:]
            break
    (work_dir / "SHA256SUMS.presentations").write_text("\n".join(tampered) + "\n", encoding="utf-8")
    proc = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.presentations"],
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0


def test_t2_f14_01_sync_studio_push_pixel_missing_serial_handles_cleanly(tmp_path: Path) -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    res = sync_fn(tmp_path, push_pixel=True, device_serial="MISSING_DEVICE_999")
    assert isinstance(res, dict)
    assert res.get("pixel_pushed") is False and res.get("pushed") is False and bool(res.get("error"))


def test_t2_f14_02_sync_studio_rejects_file_as_output_dir(tmp_path: Path) -> None:
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("occupied", encoding="utf-8")
    with pytest.raises((OSError, ValueError)):
        sync_fn(file_path)


def test_t2_f14_03_cli_sync_studio_without_out_dir_respects_isolated_home(
    isolated_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = artline_cli_main(["--json", "sync-studio"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert any((isolated_home / ".zoe").rglob("*.html"))


def test_t2_f14_04_handle_artline_slash_command_unknown_subcommand_raises() -> None:
    with pytest.raises(ValueError):
        handle_artline_slash_command("/artline nonexistent_subcommand")


def test_t2_f14_05_cli_subprocess_unknown_command_exits_nonzero(isolated_home: Path) -> None:
    env = {"HOME": str(isolated_home), "PYTHONPATH": f"{ROOT / 'components/Zoe-Autonomy/src'}:{ROOT / 'guiai-lab'}"}
    proc = subprocess.run(
        [sys.executable, "-m", "guiai.gem.zoe_artline_cli", "badcmd"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0


# ===========================================================================
# TIER 3 — Pairwise Integration Combinations (16 Tests)
# ===========================================================================


def test_t3_01_pair_f1_f2_l3_verifier_and_phase6_suite(studio_server: tuple[str, Any]) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["verified"] is True
    base_url, _eng = studio_server
    st, _hdr, raw = _http_post(base_url, "/api/l5/phase6/run", {})
    assert st == 200
    doc = json.loads(raw.decode("utf-8"))
    assert doc["l5_phase6_autonomous_verified"] is True
    _assert_epistemic_flags(doc)


def test_t3_02_pair_f3_f4_typed_routes_chat_fallback_and_sing(
    isolated_server: tuple[str, Path, Any],
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    base_url, _iso, eng = isolated_server
    llama_url, _mode = mock_llama_factory("http_500")
    eng.llm_bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=1.0)
    st_c, _hc, raw_c = _http_post(base_url, "/api/chat", {"message": "Sing Daisy!", "gear": "gear2"})
    assert st_c == 200
    chat_res = json.loads(raw_c.decode("utf-8"))
    assert chat_res["gear_used"] == "gear1"
    st_s, hdr_s, raw_s = _http_post(base_url, "/api/speak", {"text": "Daisy", "action": "sing"})
    assert st_s == 200 and hdr_s.get("content-type") == "audio/wav" and raw_s[:4] == b"RIFF"


def test_t3_03_pair_f5_f6_memoized_catalog_to_font_payload_and_typeset() -> None:
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    _ = get_forge_catalog()
    t0 = time.perf_counter()
    cat = get_forge_catalog()
    assert time.perf_counter() - t0 < 1.0
    fonts = cat.get("af4_fonts") or cat.get("fonts")
    assert isinstance(fonts, (list, dict)) and len(fonts) == 35
    payload = get_af4_font_payload("z_chance.af4")
    assert payload
    svg = typeset_af4_text_svg("z_chance.af4", "Artline 1990")
    assert "<svg" in svg and "<path" in svg


def test_t3_04_pair_f6_f7_col_palette_plus_af4_typeset_to_valid_gem() -> None:
    decode_col_file = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_file")
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    col_res = decode_col_file(DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/clrtl/clrtl/artline.col")
    assert len(_extract_col_swatches(col_res)) == 42
    svg = typeset_af4_text_svg("wombat.af4", "Zoe")
    assert "<svg" in svg
    gem_res = export_forge_artifact("gem", {"stamps": [{"d": "M10,10 L80,80 Z", "x": 200, "y": 200, "col": "#f8cc30"}]})
    raw_gem = _extract_export_bytes(gem_res)
    parsed = parse_metafile(raw_gem)
    assert parsed["bytes_consumed"] == len(raw_gem)


def test_t3_05_pair_f7_f8_tls_decode_and_zoetk_export_roundtrip() -> None:
    decode_tls_fn = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_tls_file")
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")
    tb = decode_tls_fn(DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/clrtl/clrtl/align.tls")
    assert tb.tool_count == 37
    res = export_forge_artifact("zoetk", {"toolbox_id": "align_9way"})
    raw_zk = _extract_export_bytes(res)
    rt = ZoeToolboxSpec.from_zoetk_binary(raw_zk)
    assert rt.toolbox_id == "align_9way"


def test_t3_06_pair_f8_f10_http_forge_catalog_font_export_flow(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st1, _h1, r1 = _http_get(base_url, "/api/forge/catalog")
    assert st1 == 200
    assert json.loads(r1.decode("utf-8"))
    st2, _h2, r2 = _http_get(base_url, "/api/forge/font/wombat.af4")
    assert st2 == 200
    assert json.loads(r2.decode("utf-8"))
    for kind in ("svg", "gem"):
        st3, _h3, r3 = _http_post(
            base_url,
            "/api/forge/export",
            {"kind": kind, "payload": {"stamps": [{"d": "M0,0 L40,40 Z", "x": 100, "y": 100, "col": "#5ce1e6"}]}},
        )
        assert st3 == 200 and len(r3) > 40


def test_t3_07_pair_f9_f10_adc12_persistence_and_constitutional_parity(isolated_server: tuple[str, Path, Any]) -> None:
    base_url, _iso, _eng = isolated_server
    for mod_name in (
        "guiai.gem.zoe_artline_forge",
        "guiai.gem.zoe_artline_brainstorm",
        "guiai.gem.zoe_artline_duodecimal",
        "guiai.gem.zoe_wombats_physics_room",
    ):
        mod = importlib.import_module(mod_name)
        _assert_constitutional_schema_parity(mod.CONSTITUTIONAL_FLAGS, mod_name)
    st, _hdr, raw = _http_post(base_url, "/api/adc12/react", {"tag": "200", "quote": "Constitutional parity verified"})
    assert st == 200
    _assert_epistemic_flags(json.loads(raw.decode("utf-8")))


def test_t3_08_pair_f10_f12_physics_wombat_cross_react_and_orbit_links(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st_p, _hp, raw_p = _http_get(base_url, "/physics")
    st_d, _hd, raw_d = _http_get(base_url, "/duodecimal")
    assert st_p == 200 and 'href="/orbit"' in raw_p.decode("utf-8")
    assert st_d == 200 and 'href="/orbit"' in raw_d.decode("utf-8")
    st_r, _hr, raw_r = _http_post(base_url, "/api/adc12/react", {"tag": "N", "quote": "Starred wombat reaction"})
    assert st_r == 200
    assert json.loads(raw_r.decode("utf-8"))["reaction"]["wombat"] == "★"


def test_t3_09_pair_f11_f12_all_offline_and_live_pages_pass_node_check(
    tmp_path: Path,
    studio_server: tuple[str, Any],
) -> None:
    base_url, _eng = studio_server
    for route in _ALL_10_STUDIO_HTML_ROUTES:
        st, _hdr, raw = _http_get(base_url, route, timeout=180.0)
        assert st == 200, route
        _check_inline_scripts(raw.decode("utf-8"), allow_no_scripts=(route == "/orbit"))
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    _ = sync_fn(tmp_path)
    for html_p in sorted(tmp_path.rglob("*.html")):
        _check_inline_scripts(html_p.read_text(encoding="utf-8"))


def test_t3_10_pair_f5_f11_offline_artline_and_forge_zero_external_urls(tmp_path: Path) -> None:
    from guiai.gem.zoe_artline_forge import write_interactive_artline_forge_html

    art_writer = _resolve_contract_fn("guiai.gem.zoe_artline_brainstorm", "write_interactive_artline_studio_html")
    art_html = Path(art_writer(tmp_path / "artline.html")).read_text(encoding="utf-8")
    forge_html = write_interactive_artline_forge_html(tmp_path / "forge.html").read_text(encoding="utf-8")
    for label, txt in (("artline", art_html), ("forge", forge_html)):
        assert not re.search(r'<script[^>]+src=["\']https?://', txt, flags=re.IGNORECASE), label
        assert not re.search(r'<link[^>]+href=["\']https?://', txt, flags=re.IGNORECASE), label


def test_t3_11_pair_f6_f13_deck_12_references_forge_catalog_counts() -> None:
    from pptx import Presentation

    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    prs = Presentation(str(deck_path))
    txt = "\n".join(
        sh.text_frame.text
        for sl in prs.slides
        for sh in sl.shapes
        if sh.has_text_frame
    )
    assert "35" in txt
    assert "378" in txt
    assert "ZOETK001" in txt


def test_t3_12_pair_f13_f14_checksums_and_sync_studio_assets(tmp_path: Path) -> None:
    sums_path = ROOT / "research/presentations/SHA256SUMS.presentations"
    assert "12-zoe-artline-forge.pptx" in sums_path.read_text(encoding="utf-8")
    proc = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.presentations"],
        cwd=str(ROOT / "research/presentations"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    res = sync_fn(tmp_path)
    assert res.get("external_actions") == 0
    assert len(list(tmp_path.rglob("*.html"))) >= 4


def test_t3_13_pair_f4_f9_gear2_fallback_preserves_constitutional_flags(
    tmp_path: Path,
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    llama_url, _mode = mock_llama_factory("disconnect")
    bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=1.0)
    eng = ZoeElizaEngine(ROOT, state_dir=tmp_path / "st", default_gear="gear2", llm_bridge=bridge)
    res = eng.respond("Are you sentient?", gear="gear2")
    assert res["gear_used"] == "gear1"
    _assert_epistemic_flags(res)
    assert res["epistemic_boundaries"]["sentience_claimed"] is False
    assert res["epistemic_boundaries"]["zoe_clone_claimed"] is False


def test_t3_14_pair_f2_f12_phase6_orbit_master_and_orbit_nav_aligned(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st_p6, _hp6, raw_p6 = _http_get(base_url, "/api/l5/phase6")
    st_om, _hom, raw_om = _http_get(base_url, "/api/orbit/master")
    st_or, _hor, raw_or = _http_get(base_url, "/orbit")
    assert st_p6 == 200 and st_om == 200 and st_or == 200
    assert json.loads(raw_p6.decode("utf-8"))["l5_agi_qualified"] is False
    om = json.loads(raw_om.decode("utf-8"))
    orbit_html = raw_or.decode("utf-8")
    assert f"{om['worlds_verified']}/{om['worlds_total']} Worlds Verified" in orbit_html
    assert 'href="/forge"' in orbit_html[: orbit_html.find("<table")]


def test_t3_15_pair_f1_f9_l3_verifier_and_26_reports_enforce_zero_cloud_cost(studio_server: tuple[str, Any]) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["verified"] is True
    base_url, _eng = studio_server
    for route in _REPORT_GET_ROUTES:
        st, _hdr, raw = _http_get(base_url, route)
        assert st == 200
        _assert_epistemic_flags(json.loads(raw.decode("utf-8")))


def test_t3_16_pair_f8_f14_cli_forge_and_sync_studio_outputs_consistent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert artline_cli_main(["--out-dir", str(tmp_path / "cli_forge"), "forge"]) == 0
    _ = capsys.readouterr()
    assert (tmp_path / "cli_forge/forge/palettes/zoe_studio.col.gem").is_file()
    assert (tmp_path / "cli_forge/forge/toolboxes/brainstorm_desk.zoetk").is_file()
    assert artline_cli_main(["--out-dir", str(tmp_path / "synced"), "--json", "sync-studio"]) == 0
    sync_doc = json.loads(capsys.readouterr().out)
    assert sync_doc.get("cloud_tokens_used") == 0
    assert len(list((tmp_path / "synced").rglob("*.html"))) >= 4


# ===========================================================================
# TIER 4 — Real-World End-to-End Application Scenarios (8 Tests)
# ===========================================================================


def test_t4_01_scenario_ci_and_type_gate_pipeline(studio_server: tuple[str, Any]) -> None:
    """Scenario 1: L3 Research Verifier -> L5 Phase 6 monorepo parity -> mypy static gate."""
    proc_l3 = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_l3_research.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_l3.returncode == 0, proc_l3.stderr
    l3_res = json.loads(proc_l3.stdout)
    assert l3_res["verified"] is True and l3_res["checks_passed"] == 14

    base_url, _eng = studio_server
    st_p6, _hp6, raw_p6 = _http_post(base_url, "/api/l5/phase6/run", {})
    assert st_p6 == 200
    p6_res = json.loads(raw_p6.decode("utf-8"))
    assert p6_res["l5_phase6_autonomous_verified"] is True
    _assert_epistemic_flags(p6_res)

    targets = [str(ROOT / rel) for rel in _STUDIO_PY_MODULES] + [str(Path(__file__).resolve())]
    proc_mypy = subprocess.run(
        [MYPY_BIN, "--follow-imports=silent", "--ignore-missing-imports", *targets],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_mypy.returncode == 0, f"{proc_mypy.stdout}\n{proc_mypy.stderr}"


def test_t4_02_scenario_resilient_studio_chat_with_flaky_local_qwen(
    isolated_server: tuple[str, Path, Any],
    mock_llama_factory: Callable[[str], tuple[str, dict[str, str]]],
) -> None:
    """Scenario 2: Turn 1 healthy :8080 gear2 -> Turn 2 :8080 crash falls back to gear1 -> Turn 3 /adc12 -> Turn 4 /api/export."""
    base_url, _iso, eng = isolated_server
    llama_url, mode = mock_llama_factory("ok")
    eng.llm_bridge = LocalLLMBridge(ollama_url="http://127.0.0.1:59997", llama_server_url=llama_url, timeout_sec=1.5)

    # Turn 1: Healthy local Qwen
    st1, _h1, r1 = _http_post(base_url, "/api/chat", {"message": "Summarize Artline Forge", "gear": "gear2"})
    assert st1 == 200
    d1 = json.loads(r1.decode("utf-8"))
    assert d1["gear_used"] == "gear2"
    _assert_epistemic_flags(d1)

    # Turn 2: Mid-session :8080 crash falls back cleanly to Gear 1
    mode["kind"] = "disconnect"
    st2, _h2, r2 = _http_post(base_url, "/api/chat", {"message": "What if local Qwen crashes?", "gear": "gear2"})
    assert st2 == 200
    d2 = json.loads(r2.decode("utf-8"))
    assert d2["gear_requested"] == "gear2" and d2["gear_used"] == "gear1"
    _assert_epistemic_flags(d2)

    # Turn 3: ADC-12 slash command + reaction persistence
    st3a, _h3a, r3a = _http_post(base_url, "/api/chat", {"message": "/adc12 100 Graceful fallback verified"})
    assert st3a == 200
    assert json.loads(r3a.decode("utf-8"))["mode"] == "adc12_highlight"
    st3b, _h3b, r3b = _http_post(base_url, "/api/adc12/react", {"tag": "100", "quote": "Turn 3 persisted reaction"})
    assert st3b == 200 and json.loads(r3b.decode("utf-8"))["ok"] is True

    # Turn 4: Session export
    st4, hdr4, r4 = _http_get(base_url, "/api/export")
    assert st4 == 200
    assert "zoe-eliza-session.json" in hdr4.get("content-disposition", "")
    exp = json.loads(r4.decode("utf-8"))
    assert exp["contract"] == ELIZA_CONTRACT
    _assert_epistemic_flags(exp)


def test_t4_03_scenario_archive_to_forge_typeset_to_gem_export() -> None:
    """Scenario 3: Cold->warm catalog -> .AF4 & .COL decode -> typeset SVG -> export .SVG/.GEM/.ZOETK/.JSON -> parse_metafile."""
    get_forge_catalog = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_forge_catalog")
    get_af4_font_payload = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "get_af4_font_payload")
    typeset_af4_text_svg = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "typeset_af4_text_svg")
    decode_col_file = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "decode_col_file")
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")

    _ = get_forge_catalog()
    t0 = time.perf_counter()
    cat = get_forge_catalog()
    assert time.perf_counter() - t0 < 1.0
    assert len(cat.get("af4_fonts") or cat.get("fonts") or []) == 35

    col_res = decode_col_file(DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/clrtl/clrtl/8_color.col")
    assert len(_extract_col_swatches(col_res)) == 8
    font_payload = get_af4_font_payload("z_chance.af4")
    assert font_payload
    svg = typeset_af4_text_svg("z_chance.af4", "Zoe Artline 2026")
    assert "<svg" in svg and "<path" in svg

    stamps_payload = {"stamps": [{"d": "M10,10 L120,10 L120,120 Z", "x": 240, "y": 180, "col": "#5ce1e6"}], "toolbox_id": "brainstorm_desk"}
    assert "<svg" in _extract_export_bytes(export_forge_artifact("svg", stamps_payload)).decode("utf-8")
    assert isinstance(export_forge_artifact("json", stamps_payload), dict)
    zk = export_forge_artifact("zoetk", stamps_payload)
    raw_zk = _extract_export_bytes(zk)
    assert ZoeToolboxSpec.from_zoetk_binary(raw_zk).toolbox_id == "brainstorm_desk"

    gem = export_forge_artifact("gem", stamps_payload)
    raw_gem = _extract_export_bytes(gem)
    parsed = parse_metafile(raw_gem)
    assert parsed["bytes_consumed"] == len(raw_gem)


def test_t4_04_scenario_full_web_studio_tour_and_workbench_roundtrip(studio_server: tuple[str, Any]) -> None:
    """Scenario 4: Tour all 10 live routes, check inline JS + cross-nav, query /api/forge/*, react, and export."""
    base_url, _eng = studio_server
    for route in _ALL_10_STUDIO_HTML_ROUTES:
        st, hdr, raw = _http_get(base_url, route, timeout=180.0)
        assert st == 200, route
        assert "text/html" in hdr.get("content-type", "")
        _check_inline_scripts(raw.decode("utf-8"), allow_no_scripts=(route == "/orbit"))

    st_cat, _hc, raw_cat = _http_get(base_url, "/api/forge/catalog")
    assert st_cat == 200 and json.loads(raw_cat.decode("utf-8"))
    st_fnt, _hf, raw_fnt = _http_get(base_url, "/api/forge/font/wombat.af4")
    assert st_fnt == 200 and json.loads(raw_fnt.decode("utf-8"))
    st_re, _hr, raw_re = _http_post(base_url, "/api/adc12/react", {"tag": "100", "quote": "Tour roundtrip"})
    assert st_re == 200 and json.loads(raw_re.decode("utf-8"))["ok"] is True
    st_ex, _he, raw_ex = _http_post(
        base_url,
        "/api/forge/export",
        {"kind": "svg", "payload": {"stamps": [{"d": "M0,0 L50,50 Z", "x": 100, "y": 100, "col": "#f8cc30"}]}},
    )
    assert st_ex == 200 and len(raw_ex) > 50


def test_t4_05_scenario_offline_html_workbench_generation_and_verification(tmp_path: Path) -> None:
    """Scenario 5: sync_studio_assets(tmp_path) -> verify 4 offline HTMLs, inline SVGs, zero external URLs, valid JS."""
    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    res = sync_fn(tmp_path)
    assert res.get("external_actions") == 0
    htmls = sorted(tmp_path.rglob("*.html"))
    assert len(htmls) >= 4
    joined_names = " ".join(p.name.lower() for p in htmls)
    for stem in ("artline", "physics", "forge"):
        assert stem in joined_names, f"Missing offline {stem} HTML in {htmls}"
    assert "duodecimal" in joined_names or "adc12" in joined_names
    for html_p in htmls:
        txt = html_p.read_text(encoding="utf-8")
        assert "0 Cloud Tokens" in txt
        assert not re.search(r'<script[^>]+src=["\']https?://', txt, flags=re.IGNORECASE)
        _check_inline_scripts(txt)


def test_t4_06_scenario_presentation_deck_lifecycle_and_visual_render(tmp_path: Path) -> None:
    """Scenario 6: Verify Deck 12 PPTX, SHA256SUMS, catalog.json, README.md, and LibreOffice->pdftoppm render in tmp_path."""
    from pptx import Presentation

    deck_path = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"
    assert deck_path.is_file(), f"Missing M4 deck: {deck_path}"
    prs = Presentation(str(deck_path))
    assert len(prs.slides) >= 5

    proc_sum = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.presentations"],
        cwd=str(ROOT / "research/presentations"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_sum.returncode == 0, proc_sum.stderr
    catalog = json.loads((ROOT / "research/presentations/catalog.json").read_text(encoding="utf-8"))
    assert any("12-zoe-artline-forge" in str(d.get("pptx", "")) for d in catalog["decks"])
    assert "12-zoe-artline-forge" in (ROOT / "research/presentations/README.md").read_text(encoding="utf-8")

    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    ppm_bin = shutil.which("pdftoppm")
    assert lo_bin and ppm_bin
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    assert (
        subprocess.run(
            [lo_bin, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_dir), str(deck_path)],
            capture_output=True,
            check=False,
            timeout=90,
        ).returncode
        == 0
    )
    pdf_path = pdf_dir / "12-zoe-artline-forge.pdf"
    assert pdf_path.is_file()
    assert (
        subprocess.run(
            [ppm_bin, "-png", str(pdf_path), str(tmp_path / "slide")],
            capture_output=True,
            check=False,
            timeout=90,
        ).returncode
        == 0
    )
    pngs = sorted(tmp_path.glob("slide-*.png"))
    assert len(pngs) == len(prs.slides)
    assert all(p.stat().st_size > 1000 for p in pngs)


def test_t4_07_scenario_isolated_cli_and_pixel_sync_guard(
    tmp_path: Path,
    isolated_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 7: Isolated-HOME zoe-artline CLI across studio/brainstorm/adc12/physics/forge/sync-studio."""
    out_dir = tmp_path / "cli_out"
    for argv in (
        ["--out-dir", str(out_dir), "studio"],
        ["--out-dir", str(out_dir), "brainstorm", "desk"],
        ["--out-dir", str(out_dir), "--json", "adc12", "100", "CLI scenario"],
        ["--out-dir", str(out_dir), "physics"],
        ["--out-dir", str(out_dir), "forge"],
        ["--out-dir", str(out_dir), "--json", "sync-studio"],
    ):
        rc = artline_cli_main(argv)
        assert rc == 0, f"CLI failed for {argv}"
        captured = capsys.readouterr().out
        if "--json" in argv:
            doc = json.loads(captured)
            assert doc.get("cloud_tokens_used", 0) == 0
            eb = doc.get("epistemic_boundaries", doc)
            assert eb.get("external_actions", 0) == 0

    mod = importlib.import_module("guiai.gem.zoe_artline_cli")
    sync_fn = getattr(mod, "sync_studio_assets", None)
    assert callable(sync_fn), "Missing M4 contract: sync_studio_assets"
    res = sync_fn(out_dir, push_pixel=True, device_serial="DETACHED_PIXEL_000")
    assert res.get("pixel_pushed") is False and res.get("pushed") is False and bool(res.get("error"))
    assert Path.home() == isolated_home


def test_t4_08_scenario_constitutional_and_loopback_invariants_audit(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    """Scenario 8: Audit all contract constants, loopback bind & LLM URL enforcement, constitutional invariants, and HOME isolation."""
    assert ELIZA_CONTRACT == "zoe-eliza-gem/v1"
    assert ARTLINE_FORGE_CONTRACT == "zoe-artline-forge/v1"
    assert ARTLINE_CLI_CONTRACT == "zoe-artline-cli/v1"
    assert ADC12_CONTRACT == "zoe-artline-duodecimal/v1"
    assert WOMBATS_PHYSICS_CONTRACT == "zoe-wombats-physics-room/v1"
    assert len(ADC12_MAJOR_CLASSES) == 12
    assert len(ADC12_CATALOG) == 37

    with pytest.raises(ValueError):
        create_server(ROOT, state_dir=tmp_path / "st", host="0.0.0.0", port=0)
    with pytest.raises(ValueError):
        LocalLLMBridge(ollama_url="https://example.com:11434")
    with pytest.raises(ValueError):
        LocalLLMBridge(llama_server_url="http://10.0.0.5:8080")

    for mod_name in (
        "guiai.gem.zoe_artline_forge",
        "guiai.gem.zoe_artline_brainstorm",
        "guiai.gem.zoe_artline_duodecimal",
        "guiai.gem.zoe_wombats_physics_room",
    ):
        mod = importlib.import_module(mod_name)
        _assert_constitutional_schema_parity(mod.CONSTITUTIONAL_FLAGS, mod_name)

    assert Path.home() == isolated_home
    assert not (isolated_home / ".zoe").exists()


# ===========================================================================
# TIER 5 — White-Box Adversarial Hardening & Regression Checks (G1-G6)
# ===========================================================================


def test_t5_01_forge_export_zoetk_rejects_bad_columns_and_traversal(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")

    for bad_cols in (True, False, 1.9, 0, -3, 70000):
        with pytest.raises(ValueError):
            ZoeToolboxSpec(
                toolbox_id="bad_cols",
                title="Bad",
                columns=bad_cols,  # type: ignore[arg-type]
                description="bad",
                buttons=(),
            ).to_zoetk_binary()
        with pytest.raises(ValueError):
            export_forge_artifact("zoetk", {"toolbox": {"toolbox_id": "ok_id", "columns": bad_cols, "buttons": []}})

        st, _hdr, raw = _http_post(
            base_url,
            "/api/forge/export",
            {"kind": "zoetk", "payload": {"toolbox": {"toolbox_id": "ok_id", "columns": bad_cols, "buttons": []}}},
        )
        assert st == 400, f"Expected HTTP 400 for columns={bad_cols!r}, got {st}"
        assert bool(json.loads(raw.decode("utf-8")).get("error"))

    for bad_id in ("../../evil", "bad/id", "bad\\id", "bad\x00id", "", "   ", ".hidden"):
        st, _hdr, raw = _http_post(
            base_url,
            "/api/forge/export",
            {"kind": "zoetk", "payload": {"toolbox": {"toolbox_id": bad_id, "columns": 2, "buttons": []}}},
        )
        assert st == 400, f"Expected HTTP 400 for toolbox_id={bad_id!r}, got {st}"
        assert bool(json.loads(raw.decode("utf-8")).get("error"))


def test_t5_02_forge_export_rejects_non_finite_json_svg_and_gem(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    export_forge_artifact = _resolve_contract_fn("guiai.gem.zoe_artline_forge", "export_forge_artifact")

    # Raw JSON with 1e999 -> Infinity must be rejected with HTTP 400 (RFC 8259 allow_nan=False)
    raw_inf_body = b'{"kind":"json","payload":{"stamps":[{"d":"M0,0 L10,10 Z","extra":1e999}]}}'
    st, _hdr, raw = _http_post(base_url, "/api/forge/export", raw_bytes=raw_inf_body)
    assert st == 400
    assert bool(json.loads(raw.decode("utf-8")).get("error"))

    # Direct Python calls with non-finite or bool coordinates / path numbers must raise ValueError
    for bad_payload in (
        {"stamps": [{"d": "M 1e999,0 L 10,10 Z"}]},
        {"stamps": [{"d": "M0,0 L10,10 Z", "x": float("inf")}]},
        {"stamps": [{"d": "M0,0 L10,10 Z", "x": float("nan")}]},
        {"stamps": [{"d": "M0,0 L10,10 Z", "y": True}]},
        {"stamps": [{"d": "M0,0 L10,10 Z", "rot": float("-inf")}]},
    ):
        with pytest.raises(ValueError):
            export_forge_artifact("gem", bad_payload)
        with pytest.raises(ValueError):
            export_forge_artifact("svg", bad_payload)


def test_t5_03_http_rejects_arbitrary_archive_root_and_negative_content_length(studio_server: tuple[str, Any]) -> None:
    base_url, _eng = studio_server
    st_etc, _hdr, raw_etc = _http_post(
        base_url,
        "/api/forge/export",
        {"kind": "gem", "payload": {"text": "Hi", "archive_root": "/etc"}},
    )
    assert st_etc == 400
    assert bool(json.loads(raw_etc.decode("utf-8")).get("error"))

    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    req_bytes = (
        f"POST /api/forge/export HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: -5\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    with socket.create_connection((host, port), timeout=5.0) as sock:
        sock.sendall(req_bytes)
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    resp_text = b"".join(chunks).decode("utf-8", "replace")
    assert "400" in resp_text.splitlines()[0]
    body_json = json.loads(resp_text.split("\r\n\r\n", 1)[1])
    assert "content-length" in str(body_json.get("error", "")).lower()


def test_t5_04_node_vm_client_js_resists_corrupted_localstorage(studio_server: tuple[str, Any]) -> None:
    assert Path(NODE_BIN).is_file(), f"node binary not found at {NODE_BIN}"
    base_url, _eng = studio_server
    pages = {}
    for route in ("/physics", "/artline", "/duodecimal"):
        st, _hdr, raw = _http_get(base_url, route)
        assert st == 200
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", raw.decode("utf-8"), flags=re.DOTALL | re.IGNORECASE)
        assert scripts
        pages[route] = "\n".join(scripts)

    harness = (
        "const vm = require('vm');\n"
        "function runPage(code, lsSeed, postCheck) {\n"
        "  const els = {};\n"
        "  const mkEl = (id) => ({ id, value: '', checked: true, innerHTML: '', textContent: '', style: {},\n"
        "    clientWidth: 640, clientHeight: 400, width: 640, height: 400,\n"
        "    classList: { toggle() {} }, addEventListener() {}, setAttribute() {},\n"
        "    getContext() { return { fillRect(){}, strokeRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, fill(){}, save(){}, restore(){}, translate(){}, rotate(){}, arc(){}, ellipse(){}, closePath(){}, fillText(){}, drawImage(){} }; },\n"
        "    getBoundingClientRect() { return { left: 0, top: 0, width: 640, height: 400 }; } });\n"
        "  const lsMap = Object.assign({}, lsSeed);\n"
        "  const sandbox = {\n"
        "    console, Math, Number, String, Array, Object, JSON, Date, Set, Map, Uint8Array, Blob, URL,\n"
        "    setTimeout: () => 0, clearTimeout: () => {}, requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},\n"
        "    localStorage: { getItem(k){ return Object.prototype.hasOwnProperty.call(lsMap, k) ? lsMap[k] : null; }, setItem(k,v){ lsMap[k]=String(v); } },\n"
        "    navigator: {},\n"
        "    window: { addEventListener() {} },\n"
        "    document: { getElementById(id){ return els[id] || (els[id] = mkEl(id)); }, createElement(){ return mkEl('dyn'); }, body: { appendChild(){}, removeChild(){} }, execCommand(){ return false; } },\n"
        "  };\n"
        "  vm.createContext(sandbox);\n"
        "  vm.runInContext(code, sandbox);\n"
        "  if (postCheck) vm.runInContext(postCheck, sandbox);\n"
        "}\n"
        f"const physicsJs = {json.dumps(pages['/physics'])};\n"
        "for (const bad of ['[null]', '[{\"text\":\"hi\"}]', '[{\"text\":\"hi\",\"badges\":\"not_array\"}]', 'null', '123']) {\n"
        "  runPage(physicsJs, { zoe_physics_notes_v1: bad }, \"renderNotes(); stampWombat('✺', '#f8cc30', 'Z Idea', 'idea');\");\n"
        "}\n"
        f"const artlineJs = {json.dumps(pages['/artline'])};\n"
        "for (const bad of ['[null]', '[{}]', 'null']) {\n"
        "  runPage(artlineJs, { zoe_artline_drafts_v1: bad }, 'renderDrafts();');\n"
        "}\n"
        f"const duoJs = {json.dumps(pages['/duodecimal'])};\n"
        "for (const bad of ['[null]', '[{}]', 'null']) {\n"
        "  runPage(duoJs, { zoe_adc12_stamps_v1: bad }, 'renderStamps(); copyAll();');\n"
        "}\n"
    )
    proc = subprocess.run([NODE_BIN, "-"], input=harness, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Client JS corrupted localStorage probe failed:\n{proc.stderr}\n{proc.stdout}"


def test_t5_05_node_vm_forge_eschtml_blocks_xss_injection(
    cached_forge_html: tuple[int, dict[str, str], str],
) -> None:
    assert Path(NODE_BIN).is_file(), f"node binary not found at {NODE_BIN}"
    st, _hdr, html = cached_forge_html
    assert st == 200
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
    assert scripts
    forge_js = "\n".join(scripts)
    harness = (
        "const vm = require('vm');\n"
        "const els = {};\n"
        "const mkEl = (id) => ({ id, value: '', checked: true, innerHTML: '', textContent: '', style: {}, attributes: {},\n"
        "  classList: { toggle() {} }, addEventListener() {}, setAttribute(k,v){ this.attributes[k]=v; } });\n"
        "const sandbox = {\n"
        "  console, Math, Number, String, Array, Object, JSON, Uint8Array, Blob, URL,\n"
        "  requestAnimationFrame: () => 0, cancelAnimationFrame: () => {},\n"
        "  window: {},\n"
        "  document: { getElementById(id){ return els[id] || (els[id] = mkEl(id)); }, createElement(){ return mkEl('dyn'); } },\n"
        "};\n"
        "vm.createContext(sandbox);\n"
        f"vm.runInContext({json.dumps(forge_js)}, sandbox);\n"
        "vm.runInContext(`\n"
        "  VECS.wombat_glyphs.unshift({ code: '99', key: '\"><img src=x onerror=alert(1)>', d: 'M0,0\" onclick=\"alert(1)' });\n"
        "  vaultTab = 'wombat';\n"
        "  renderVault();\n"
        "  stamps.push(makeStamp('M0,0\" onload=\"alert(2)', 100, 100, 1, 0, '#5ce1e6\" onmouseover=\"alert(3)'));\n"
        "  renderStage();\n"
        "  TOOLBOXES[0].buttons[0].label = \"';alert(9);//<img src=y onerror=alert(4)>\";\n"
        "  renderToolboxes();\n"
        "  PALETTES[0].swatches[0].name = '<svg onload=alert(5)>';\n"
        "  renderPalettes();\n"
        "`, sandbox);\n"
        "for (const id of ['vaultGrid', 'stage', 'tbGrid', 'swatches']) {\n"
        "  const out = els[id].innerHTML;\n"
        "  if (out.includes('<img') || out.includes('<svg onload') || out.includes('\" onclick=\"alert(') || out.includes('\" onload=\"alert(') || out.includes('\" onmouseover=\"alert(') || out.includes(\"';alert(\")) {\n"
        "    throw new Error('Unescaped XSS payload found in ' + id + ': ' + out.slice(0, 300));\n"
        "  }\n"
        "}\n"
        "if (!els.vaultGrid.innerHTML.includes('&lt;img') || !els.vaultGrid.innerHTML.includes('&quot; onclick=&quot;')) {\n"
        "  throw new Error('Expected HTML-escaped entities in vaultGrid');\n"
        "}\n"
        "if (!els.tbGrid.innerHTML.includes('\\\\&#39;;alert(')) {\n"
        "  throw new Error('Expected JS-escaped attribute in tbGrid: ' + els.tbGrid.innerHTML.slice(0, 300));\n"
        "}\n"
    )
    proc = subprocess.run([NODE_BIN, "-"], input=harness, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"/forge escHtml XSS check failed:\n{proc.stderr}\n{proc.stdout}"


def test_t5_06_combined_20_file_mypy_passes_zero_errors() -> None:
    targets = [
        "components/Zoe-Autonomy/src/zoe_autonomy/zoe_eliza.py",
        "components/Zoe-Autonomy/src/zoe_autonomy/l5_phase6_repo_agent.py",
        "guiai-lab/guiai/gem/_eliza_routes.py",
        "guiai-lab/guiai/gem/eliza_view.py",
        "guiai-lab/guiai/gem/zoe_artline_forge.py",
        "guiai-lab/guiai/gem/zoe_artline_cli.py",
        "guiai-lab/guiai/gem/zoe_artline_brainstorm.py",
        "guiai-lab/guiai/gem/zoe_artline_duodecimal.py",
        "guiai-lab/guiai/gem/zoe_wombats_physics_room.py",
        "scripts/build_artline_forge_deck.py",
        "scripts/sync_zoe_studio.py",
        "components/Zoe-Autonomy/tests/test_e2e_studio_forge.py",
        "components/Zoe-Autonomy/tests/test_eliza_routes.py",
        "components/Zoe-Autonomy/tests/test_zoe_eliza.py",
        "components/Zoe-Autonomy/tests/test_sr_artline_forge.py",
        "components/Zoe-Autonomy/tests/test_sr_artline_studio_web_cli.py",
        "components/Zoe-Autonomy/tests/test_sr_artline_brainstorm.py",
        "components/Zoe-Autonomy/tests/test_sr_artline_duodecimal.py",
        "components/Zoe-Autonomy/tests/test_sr_wombats_physics_room.py",
        "components/Zoe-Autonomy/tests/test_sr_artline_sync.py",
    ]
    proc = subprocess.run(
        [MYPY_BIN, "--follow-imports=silent", "--ignore-missing-imports", *[str(ROOT / t) for t in targets]],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Combined 20-file mypy failed:\n{proc.stdout}\n{proc.stderr}"

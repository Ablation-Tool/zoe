"""Integration tests for live :8765 Web Studio Artline/Physics/ADC-12 routes & zoe-artline CLI."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib import error as urlerror, request as urlrequest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.eliza_view import create_server
from guiai.gem.zoe_artline_cli import handle_artline_slash_command, main as artline_cli_main

NODE_BIN = shutil.which("node") or str(
    next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
)


def _check_inline_js(html_text: str) -> None:
    if not Path(NODE_BIN).is_file():
        return
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE)
    assert scripts, "expected inline <script> block"
    for js in scripts:
        proc = subprocess.run([NODE_BIN, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_live_web_studio_artline_physics_duodecimal_routes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        srv, _eng, _lk = create_server(ROOT, state_dir=Path(tmp) / "state", host="127.0.0.1", port=0)
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            # Topbar index links to all 4 new live tabs + 1-click ADC-12 chat-bubble reaction bar
            with urlrequest.urlopen(f"{base}/", timeout=10) as r:
                root_html = r.read().decode("utf-8")
                assert 'href="/artline"' in root_html
                assert 'href="/physics"' in root_html
                assert 'href="/duodecimal"' in root_html
                assert 'href="/forge"' in root_html
                assert "reactToBubble" in root_html
                assert "/api/adc12/react" in root_html
                _check_inline_js(root_html)

            # All 4 new HTML workbenches return 200, cross-nav to /forge, markers, and node --check clean inline JS
            for route, marker in (
                ("/artline", "Zoe Artline 2.0 Brainstorm Studio"),
                ("/physics", "Optional-Physics Room"),
                ("/duodecimal", "Artline Duodecimal Classification (ADC-12)"),
                ("/forge", "Zoe Artline Forge"),
            ):
                with urlrequest.urlopen(f"{base}{route}", timeout=10) as r:
                    assert r.status == 200
                    body = r.read().decode("utf-8")
                    assert marker in body
                    if route != "/forge":
                        assert 'href="/forge"' in body
                    assert "0 Cloud Tokens" in body
                    assert "sentience_claimed=False" in body
                    assert "clinical_action_authorized=False" in body
                    _check_inline_js(body)

            # Live 1-click chat-bubble ADC-12 reaction endpoint (POST /api/adc12/react)
            react_req = urlrequest.Request(
                f"{base}/api/adc12/react",
                data=json.dumps({"tag": "100", "quote": "Highlight & react right on a chat bubble"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlrequest.urlopen(react_req, timeout=10) as r:
                assert r.status == 200
                rpay = json.loads(r.read().decode("utf-8"))
                assert rpay["ok"] is True
                assert rpay["cloud_tokens_used"] == 0
                assert rpay["reaction"]["call_code"] == "100"
                assert rpay["reaction"]["wombat"] == "✺"
                assert len(rpay["reaction"]["receipt_sha256"]) == 64

            # Live Artline concept SVGs
            for concept in ("desk", "chess", "sector", "mondo"):
                with urlrequest.urlopen(f"{base}/api/artline/{concept}.svg", timeout=10) as r:
                    assert r.status == 200
                    svg = r.read().decode("utf-8")
                    assert "<svg" in svg and "</svg>" in svg

            # Live /adc12 slash command over POST /api/chat
            req = urlrequest.Request(
                f"{base}/api/chat",
                data=json.dumps({"message": "/adc12 100 Base-12 GEM shorthand works live"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlrequest.urlopen(req, timeout=10) as r:
                assert r.status == 200
                payload = json.loads(r.read().decode("utf-8"))
                assert payload["mode"] == "adc12_highlight"
                assert payload["data"]["call_code"] == "100"
                assert payload["epistemic_boundaries"]["cloud_tokens_used"] == 0
        finally:
            srv.shutdown()
            srv.server_close()


def test_zoe_artline_cli_subcommands(tmp_path: Path, capsys) -> None:
    rc_studio = artline_cli_main(["--out-dir", str(tmp_path), "studio"])
    assert rc_studio == 0
    assert "/duodecimal" in capsys.readouterr().out

    rc_bs = artline_cli_main(["--out-dir", str(tmp_path), "brainstorm", "desk"])
    assert rc_bs == 0
    assert "Exported Artline Brainstorm" in capsys.readouterr().out
    assert (tmp_path / "artline_brainstorm_desk.svg").is_file()
    assert (tmp_path / "artline_brainstorm_desk.gem").is_file()

    rc_adc = artline_cli_main(["--json", "adc12", "100", "Duodecimal Dewey classification"])
    assert rc_adc == 0
    out_obj = json.loads(capsys.readouterr().out)
    assert out_obj["data"]["wombat"] == "✺"
    assert out_obj["data"]["decimal_code"] == 90

    res_phys = handle_artline_slash_command("/artline physics", out_dir=tmp_path)
    assert res_phys["mode"] == "artline_physics"
    assert Path(res_phys["data"]["gif"]["gif_path"]).is_file()

    rc_forge = artline_cli_main(["--out-dir", str(tmp_path), "forge"])
    assert rc_forge == 0
    assert "Zoe Artline Forge Exported" in capsys.readouterr().out
    assert (tmp_path / "forge" / "zoe_artline_forge.html").is_file()
    assert (tmp_path / "forge" / "palettes" / "zoe_studio.col.gem").is_file()
    assert (tmp_path / "forge" / "toolboxes" / "brainstorm_desk.zoetk").is_file()


def _http_req(url: str, *, method: str = "GET", body: object | None = None) -> tuple[int, dict[str, str], bytes]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=15) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urlerror.HTTPError as err:
        with err:
            return err.code, {k.lower(): v for k, v in err.headers.items()}, err.read()


def test_live_web_studio_f10_f12_persistence_and_forge_apis() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        srv, _eng, _lk = create_server(ROOT, state_dir=Path(tmp) / "state", host="127.0.0.1", port=0)
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            st_root, _hr, raw_root = _http_req(f"{base}/")
            assert st_root == 200
            root_html = raw_root.decode("utf-8")
            assert "zoe_adc12_reactions_v1" in root_html
            assert "/api/adc12/react" in root_html
            _check_inline_js(root_html)

            # F10: Persist ADC-12 reaction and verify via GET /api/adc12/react and /api/status
            quote = "Studio test persistent ADC-12 highlight"
            st_p, _hp, raw_p = _http_req(
                f"{base}/api/adc12/react", method="POST", body={"tag": "200", "quote": quote}
            )
            assert st_p == 200
            assert json.loads(raw_p.decode("utf-8"))["reaction"]["call_code"] == "200"

            st_g, _hg, raw_g = _http_req(f"{base}/api/adc12/react")
            assert st_g == 200
            g_doc = json.loads(raw_g.decode("utf-8"))
            assert g_doc["count"] >= 1
            assert any(r["quote"] == quote for r in g_doc["reactions"])

            st_s, _hs, raw_s = _http_req(f"{base}/api/status")
            assert st_s == 200
            s_doc = json.loads(raw_s.decode("utf-8"))
            assert s_doc["adc12_reactions_count"] >= 1
            assert any(r["quote"] == quote for r in s_doc["adc12_reactions"])

            # F10: Forge API routes
            st_cat, _hc, raw_cat = _http_req(f"{base}/api/forge/catalog")
            assert st_cat == 200
            cat_doc = json.loads(raw_cat.decode("utf-8"))
            assert len(cat_doc["fonts"]) == 35
            assert isinstance(cat_doc["syf_packs"], dict) and len(cat_doc["syf_packs"]) == 20
            assert cat_doc["cloud_tokens_used"] == 0

            st_fnt, _hf, raw_fnt = _http_req(f"{base}/api/forge/font/wombat.af4")
            assert st_fnt == 200
            assert len(json.loads(raw_fnt.decode("utf-8"))["glyphs"]) >= 20

            st_miss, _hm, raw_miss = _http_req(f"{base}/api/forge/font/no_such_font_999.af4")
            assert st_miss == 404
            assert "error" in json.loads(raw_miss.decode("utf-8"))

            st_trav, _ht, raw_trav = _http_req(f"{base}/api/forge/font/..%2F..%2Fetc%2Fpasswd")
            assert st_trav == 400
            assert "error" in json.loads(raw_trav.decode("utf-8"))

            st_ts, _hts, raw_ts = _http_req(
                f"{base}/api/forge/typeset",
                method="POST",
                body={"font": "wombat.af4", "text": "ZOE"},
            )
            assert st_ts == 200
            assert "<svg" in json.loads(raw_ts.decode("utf-8"))["svg"]

            st_exp, _hexp, raw_exp = _http_req(
                f"{base}/api/forge/export",
                method="POST",
                body={"kind": "gem", "payload": {"stamps": [{"d": "M0,0 L40,40 Z", "x": 100, "y": 100}]}},
            )
            assert st_exp == 200
            assert json.loads(raw_exp.decode("utf-8"))["valid_gem_header"] is True

            st_bad_exp, _hbe, raw_bad_exp = _http_req(
                f"{base}/api/forge/export",
                method="POST",
                body={"kind": "svg", "payload": {"stamps": [{"d": "M0,0 L40,40 Z", "x": 1e999}]}},
            )
            assert st_bad_exp == 400
            assert "error" in json.loads(raw_bad_exp.decode("utf-8"))

            # F12: /orbit top nav and /physics & /duodecimal /orbit link + 13 wombats
            st_orb, _ho, raw_orb = _http_req(f"{base}/orbit")
            assert st_orb == 200
            orb_html = raw_orb.decode("utf-8")
            head = orb_html[: orb_html.find("<table")]
            for href in ('href="/"', 'href="/artline"', 'href="/physics"', 'href="/duodecimal"', 'href="/forge"'):
                assert href in head
            st_phy, _hphy, raw_phy = _http_req(f"{base}/physics")
            assert st_phy == 200 and 'href="/orbit"' in raw_phy.decode("utf-8")
            st_duo, _hduo, raw_duo = _http_req(f"{base}/duodecimal")
            assert st_duo == 200 and 'href="/orbit"' in raw_duo.decode("utf-8")
        finally:
            srv.shutdown()
            srv.server_close()

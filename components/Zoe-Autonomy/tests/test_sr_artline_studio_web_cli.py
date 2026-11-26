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
from urllib import request as urlrequest

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
            # Topbar index links to all 4 new live tabs
            with urlrequest.urlopen(f"{base}/", timeout=10) as r:
                root_html = r.read().decode("utf-8")
                assert 'href="/artline"' in root_html
                assert 'href="/physics"' in root_html
                assert 'href="/duodecimal"' in root_html
                assert 'href="/forge"' in root_html

            # All 4 new HTML workbenches return 200, markers, and node --check clean inline JS
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
                    assert "0 Cloud Tokens" in body
                    assert "sentience_claimed=False" in body
                    assert "clinical_action_authorized=False" in body
                    _check_inline_js(body)

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

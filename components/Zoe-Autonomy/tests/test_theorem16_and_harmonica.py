"""Unit & HTTP integration tests for Theorem 16, Glass Harmonica Orrery, and Gear-3 Studio probe."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
for rel in ("guiai-lab", "components/Zoe-Autonomy/src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.eliza_view import create_server
from guiai.gem.glass_harmonica_workbench import CONTRACT as HARMONICA_CONTRACT, render_harmonica_wav_bytes
from guiai.gem.kloster_harmonic_optics import CONTRACT as THM16_CONTRACT, run_kloster_theorem16_suite


def test_theorem16_suite_and_constitution() -> None:
    rep = run_kloster_theorem16_suite()
    assert rep["contract"] == THM16_CONTRACT
    assert rep["all_verified"] is True
    assert rep["sympy_proofs"]["all_zero_residual"] is True
    assert rep["empirical"]["max_parseval_err"] < 1e-13
    assert rep["empirical"]["contraction_200_passed"] == 200
    c = rep["constitution"]
    assert c["sentience_claimed"] is False
    assert c["l5_agi_qualified"] is False
    assert c["zoe_clone_claimed"] is False
    assert c["clinical_action_authorized"] is False
    assert c["cure_claim"] is False
    assert c["cloud_tokens_used"] == 0


def test_harmonica_wav_synthesis() -> None:
    wav = render_harmonica_wav_bytes({
        "voices": [{"n": 2, "m": 5, "vowel": "AA"}, {"n": 3, "m": 4, "vowel": "IY"}, {"n": 1, "m": 3, "vowel": "OW"}],
        "sigma": 1.4,
        "ratio": [3, 2],
    })
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert len(wav) > 100_000


def test_eliza_studio_harmonica_theorem16_and_frontier_probe(tmp_path: Path) -> None:
    server, _engine, _lock = create_server(
        ROOT,
        state_dir=tmp_path / "eliza_state",
        host="127.0.0.1",
        port=0,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/harmonica", timeout=5) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Zoe Glass Harmonica" in html
            assert "\u2014" not in html

        with urllib.request.urlopen(f"{base}/api/kloster/theorem16", timeout=5) as resp:
            assert resp.status == 200
            t16 = json.loads(resp.read().decode("utf-8"))
            assert t16["all_verified"] is True

        with urllib.request.urlopen(f"{base}/api/status", timeout=5) as resp:
            assert resp.status == 200
            st = json.loads(resp.read().decode("utf-8"))
            fp = st["frontier_probe"]
            assert fp["cloud_tokens_used"] == 0
            assert isinstance(fp["available"], bool)

        req = urllib.request.Request(
            f"{base}/api/harmonica/wav",
            data=json.dumps({"sigma": 0.8, "ratio": [4, 3]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            assert resp.headers.get("X-Zoe-Contract") == HARMONICA_CONTRACT
            wav = resp.read()
            assert wav[:4] == b"RIFF"
    finally:
        server.shutdown()
        server.server_close()

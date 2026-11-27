"""Unit and integration tests for offline Studio HTML sync & Pixel 7 ADB guard (F14)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem import zoe_artline_brainstorm  # noqa: E402
from guiai.gem.zoe_artline_cli import (  # noqa: E402
    DEFAULT_PIXEL_REMOTE_DIR,
    DEFAULT_PIXEL_SERIAL,
    main as artline_cli_main,
    sync_studio_assets,
)

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


def test_sync_studio_assets_writes_four_standalone_htmls_and_manifest(tmp_path: Path) -> None:
    res = sync_studio_assets(tmp_path)
    assert res["external_actions"] == 0
    assert res["cloud_tokens_used"] == 0
    assert res["pixel_pushed"] is False
    assert res["pushed"] is False
    assert res["error"] is None
    assert res["html_count"] == 4

    expected_names = {
        "artline_studio.html",
        "physics_room.html",
        "adc12_catalog.html",
        "zoe_artline_forge.html",
    }
    htmls = {p.name: p for p in tmp_path.glob("*.html")}
    assert set(htmls.keys()) == expected_names

    for name, path in htmls.items():
        text = path.read_text(encoding="utf-8")
        assert "0 Cloud Tokens" in text, name
        assert not re.search(r'<script[^>]+src=["\']https?://', text, flags=re.IGNORECASE), name
        assert not re.search(r'<link[^>]+href=["\']https?://', text, flags=re.IGNORECASE), name
        _check_inline_js(text)

    manifest_path = Path(res["manifest_path"])
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 4
    for rec in manifest["files"]:
        fp = Path(rec["path"])
        assert fp.is_file()
        assert rec["bytes"] == fp.stat().st_size
        assert rec["sha256"] == hashlib.sha256(fp.read_bytes()).hexdigest()
    flags = manifest["constitutional_flags"]
    assert flags["clean_room_original"] is True
    assert flags["proprietary_code_copied"] == 0
    assert flags["external_actions"] == 0
    assert flags["cloud_tokens_used"] == 0


def test_sync_studio_assets_artline_writer_present_and_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fallback when write_interactive_artline_studio_html is absent
    monkeypatch.setattr(zoe_artline_brainstorm, "write_interactive_artline_studio_html", None, raising=False)
    fallback_dir = tmp_path / "fallback"
    res_fb = sync_studio_assets(fallback_dir)
    assert res_fb["external_actions"] == 0
    fb_html = (fallback_dir / "artline_studio.html").read_text(encoding="utf-8")
    assert "Zoe Artline 2.0 Brainstorm Studio" in fb_html
    _check_inline_js(fb_html)

    # Active M3 writer path when write_interactive_artline_studio_html is defined
    called_paths: list[Path] = []

    def _dummy_writer(out_html: str | Path) -> Path:
        p = Path(out_html)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "<!doctype html><html><body>0 Cloud Tokens<script>const x = 1;</script></body></html>",
            encoding="utf-8",
        )
        called_paths.append(p)
        return p

    monkeypatch.setattr(zoe_artline_brainstorm, "write_interactive_artline_studio_html", _dummy_writer, raising=False)
    writer_dir = tmp_path / "with_writer"
    res_wr = sync_studio_assets(writer_dir)
    assert len(called_paths) == 1
    assert called_paths[0] == (writer_dir / "artline_studio.html").resolve()
    assert "const x = 1;" in Path(res_wr["html_paths"]["artline"]).read_text(encoding="utf-8")


def test_sync_studio_assets_rejects_file_output_dir(tmp_path: Path) -> None:
    blocker = tmp_path / "regular_file.txt"
    blocker.write_text("occupied", encoding="utf-8")
    with pytest.raises(ValueError):
        sync_studio_assets(blocker)


def test_sync_studio_assets_missing_adb_and_detached_device_fail_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing adb binary
    monkeypatch.setattr(shutil, "which", lambda _cmd: None)
    res_no_adb = sync_studio_assets(tmp_path / "no_adb", push_pixel=True, device_serial=DEFAULT_PIXEL_SERIAL)
    assert res_no_adb["pixel_pushed"] is False
    assert res_no_adb["pushed"] is False
    assert res_no_adb["external_actions"] == 0
    assert res_no_adb["error"] and "adb" in res_no_adb["error"].lower()

    # Present adb binary, but target serial not attached
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/adb" if cmd == "adb" else None)

    def _fake_devices_empty(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["adb", "devices"], returncode=0, stdout="List of devices attached\n\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_devices_empty)
    res_detached = sync_studio_assets(tmp_path / "detached", push_pixel=True, device_serial="MISSING_PIXEL_999")
    assert res_detached["pixel_pushed"] is False
    assert res_detached["pushed"] is False
    assert res_detached["external_actions"] == 0
    assert res_detached["error"] and "MISSING_PIXEL_999" in res_detached["error"]


def test_sync_studio_assets_mocked_attached_pixel_pushes_all_five_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/adb" if cmd == "adb" else None)
    adb_calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        adb_calls.append(list(cmd))
        if cmd[1:] == ["devices"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=f"List of devices attached\n{DEFAULT_PIXEL_SERIAL}\tdevice usb:1-1\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    res = sync_studio_assets(tmp_path, push_pixel=True)
    assert res["pixel_pushed"] is True
    assert res["pushed"] is True
    assert res["error"] is None
    assert res["external_actions"] == 5
    assert len(res["pushed_files"]) == 5
    assert all(p.startswith(DEFAULT_PIXEL_REMOTE_DIR + "/") for p in res["pushed_files"])
    assert adb_calls[0] == ["/usr/local/bin/adb", "devices"]
    assert adb_calls[1] == ["/usr/local/bin/adb", "-s", DEFAULT_PIXEL_SERIAL, "shell", "mkdir", "-p", DEFAULT_PIXEL_REMOTE_DIR]
    assert sum(1 for c in adb_calls if "push" in c) == 5


def test_cli_sync_studio_and_isolated_home_default_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    iso_home = tmp_path / "iso_home"
    iso_home.mkdir()
    monkeypatch.setenv("HOME", str(iso_home))

    rc_default = artline_cli_main(["--json", "sync-studio"])
    assert rc_default == 0
    out_default = json.loads(capsys.readouterr().out)
    assert out_default["mode"] == "artline_sync_studio"
    assert out_default["cloud_tokens_used"] == 0
    assert out_default["epistemic_boundaries"]["external_actions"] == 0
    default_dir = iso_home / ".zoe" / "artline" / "studio"
    assert (default_dir / "zoe_artline_forge.html").is_file()
    assert (default_dir / "studio_manifest.json").is_file()

    explicit_dir = tmp_path / "explicit"
    rc_exp = artline_cli_main(["--out-dir", str(explicit_dir), "--json", "sync-studio"])
    assert rc_exp == 0
    out_exp = json.loads(capsys.readouterr().out)
    assert Path(out_exp["data"]["out_dir"]) == explicit_dir.resolve()
    assert len(list(explicit_dir.glob("*.html"))) == 4


def test_standalone_sync_zoe_studio_script_without_pythonpath(tmp_path: Path) -> None:
    script_path = ROOT / "scripts/sync_zoe_studio.py"
    env = {"HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"}
    (tmp_path / "home").mkdir()
    out_dir = tmp_path / "synced"
    proc = subprocess.run(
        [sys.executable, str(script_path), "--out-dir", str(out_dir), "--json"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(proc.stdout)
    assert doc["external_actions"] == 0
    assert doc["cloud_tokens_used"] == 0
    assert doc["pixel_pushed"] is False
    assert len(list(out_dir.glob("*.html"))) == 4
    assert (out_dir / "studio_manifest.json").is_file()

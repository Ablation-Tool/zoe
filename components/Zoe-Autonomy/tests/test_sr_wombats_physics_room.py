"""Unit tests for Artline 2.0 Page A-2 Wombats Reactions & Optional-Physics Sandbox Room."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_wombats_physics_room import (
    CONSTITUTIONAL_FLAGS,
    PAGE_A2_WOMBATS_REACTIONS,
    PhysicsSandboxRoom,
    WombatsReactionBar,
    build_artline_rosette_wombats_plate,
    render_physics_shatter_gif,
    resolve_wombat_reaction,
    write_interactive_physics_room_html,
)


def test_page_a2_wombats_zoe_and_nick_codes() -> None:
    assert len(PAGE_A2_WOMBATS_REACTIONS) == 13
    # Authentic Artline p. A-2 codes: Z=90, o=111, e=101; N=78, I=73
    assert resolve_wombat_reaction(90).ascii_key == "Z"
    assert resolve_wombat_reaction("o").decimal_code == 111
    assert resolve_wombat_reaction("e").decimal_code == 101
    assert resolve_wombat_reaction(78).ascii_key == "N"
    assert resolve_wombat_reaction("I").decimal_code == 73

    bar = WombatsReactionBar()
    r1 = bar.react("Build an optional-physics room", "Z")
    r2 = bar.react("Use Artline Wombats for reactions", 78)
    assert r1.wombat_glyph == "✺"
    assert r2.wombat_glyph == "★"
    assert len(r1.receipt_sha256) == 64
    assert bar.to_dict()["constitutional"]["external_actions"] == 0

    with pytest.raises(ValueError):
        bar.react("", "Z")


def test_rosette_plate_exports_svg_png_gem(tmp_path: Path) -> None:
    doc, meta = build_artline_rosette_wombats_plate(petals=9)
    assert meta["petals"] == 9
    for ext in ("svg", "png", "gem"):
        out = tmp_path / f"rosette.{ext}"
        doc.export(out, kind=ext)
        assert out.is_file() and out.stat().st_size > 1000


def test_optional_physics_off_vs_gravity_shatter_and_html(tmp_path: Path) -> None:
    # Physics OFF = relaxed freeform mode (zero unwanted movement!)
    room_off = PhysicsSandboxRoom(mode="off")
    snap_before = [(b.x, b.y) for b in room_off.bodies]
    for _ in range(10):
        room_off.step()
    assert [(b.x, b.y) for b in room_off.bodies] == snap_before
    assert room_off.shatter_events == 0

    # Physics GRAVITY = star impacts & shatters blocks safely!
    gif_info = render_physics_shatter_gif(tmp_path / "shatter.gif", keyframe_dir=tmp_path, frames=36)
    assert gif_info["shatter_events"] >= 1
    assert gif_info["constitutional"]["external_actions"] == 0
    with Image.open(gif_info["gif_path"]) as im:
        assert getattr(im, "n_frames", 1) == 36

    html_path = write_interactive_physics_room_html(tmp_path / "room.html")
    content = html_path.read_text(encoding="utf-8")
    assert "Physics: OFF (Relaxed)" in content
    assert "Shatter All" in content
    assert "external_actions=0" in content


def test_wombats_physics_constitutional_flags_13_buttons_exports_and_js(tmp_path: Path) -> None:
    expected = {
        "clean_room_original": True,
        "proprietary_code_copied": 0,
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "cloud_tokens_used": 0,
        "tokens_used": 0,
    }
    for key, val in expected.items():
        assert CONSTITUTIONAL_FLAGS[key] == val

    html_path = write_interactive_physics_room_html(tmp_path / "room.html")
    content = html_path.read_text(encoding="utf-8")
    for w in PAGE_A2_WOMBATS_REACTIONS:
        assert w.action_id in content
    for marker in (
        'href="/orbit"',
        'href="/forge"',
        "exportPhysicsSvg",
        "exportPhysicsGem",
        "exportPhysicsPng",
        "zoe_physics_notes_v1",
    ):
        assert marker in content

    node_bin = shutil.which("node") or str(
        next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
    )
    if Path(node_bin).is_file():
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", content, flags=re.DOTALL | re.IGNORECASE)
        assert scripts
        for js in scripts:
            proc = subprocess.run([node_bin, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
            assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_t5_physics_room_corrupted_localstorage_normalization(tmp_path: Path) -> None:
    html_path = write_interactive_physics_room_html(tmp_path / "room.html")
    content = html_path.read_text(encoding="utf-8")
    assert "normalizedNotes" in content
    assert "Array.isArray(noteObj.badges)" in content
    node_bin = shutil.which("node") or str(
        next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
    )
    if Path(node_bin).is_file():
        js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", content, flags=re.DOTALL | re.IGNORECASE))
        harness = (
            "const els = {};\n"
            "const mkEl = (id) => ({ id, innerHTML: '', textContent: '', style: {}, clientWidth: 640, clientHeight: 400, width: 640, height: 400,\n"
            "  classList: { toggle() {} }, addEventListener() {},\n"
            "  getContext() { return { fillRect(){}, strokeRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, fill(){}, save(){}, restore(){}, translate(){}, rotate(){}, arc(){}, ellipse(){}, closePath(){}, fillText(){} }; } });\n"
            "global.document = { getElementById(id){ return els[id] || (els[id] = mkEl(id)); } };\n"
            "global.window = { addEventListener() {} };\n"
            "global.requestAnimationFrame = () => 0;\n"
            "global.localStorage = { getItem(){ return '[null, {\"text\":\"ok\",\"badges\":\"bad\"}, {\"text\":\"two\"}]'; }, setItem(){} };\n"
            + js
            + "\nstampWombat('✺', '#f8cc30', 'Z Idea', 'idea');\n"
        )
        proc = subprocess.run([node_bin, "-e", harness], input="", text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr

"""Unit tests for Zoe Artline Brainstorming Studio, visual state sprites, and Drafts Drawer."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_artline_brainstorm import (
    BRAINSTORM_CONCEPTS,
    CONSTITUTIONAL_FLAGS,
    STATE_SPRITE_MAP,
    IdeaScratchpadDrawer,
    export_all_brainstorm_concepts,
    render_artline_studio_html,
    render_state_sprite_png,
    render_state_sprite_terminal,
    resolve_visual_state,
    write_interactive_artline_studio_html,
)


def test_state_sprites_dimensions_and_terminal_render(tmp_path: Path) -> None:
    assert set(STATE_SPRITE_MAP) == {"brain", "bulb", "helix", "chess"}
    for name, rows in STATE_SPRITE_MAP.items():
        assert len(rows) == 18, f"{name} must be 18 rows"
        assert all(len(r) == 23 for r in rows), f"{name} rows must be 23 cols"
        term_lines = render_state_sprite_terminal(name, color=True)
        assert len(term_lines) == 9
        png_path = render_state_sprite_png(name, tmp_path / f"{name}.png", pixel_scale=8)
        assert png_path.is_file() and png_path.stat().st_size > 200


def test_deterministic_visual_state_resolution() -> None:
    assert resolve_visual_state(active_module="dorothy_mni152").state == "brain"
    assert resolve_visual_state(active_module="deepmind_alphafold").state == "helix"
    assert resolve_visual_state(active_module="counterpoint_chairs").state == "chess"
    assert resolve_visual_state(active_module="idle", has_unreviewed_draft=True, quiet_mode=False).state == "bulb"
    assert resolve_visual_state(active_module="idle", has_unreviewed_draft=True, quiet_mode=True).state == "ruby"


def test_transparent_drafts_drawer_invariants() -> None:
    drawer = IdeaScratchpadDrawer(quiet_mode=False)
    d1 = drawer.add_draft("Test H3K27M", "Compare AF3 complex scores for H3K27M", source_module="deepmind")
    assert d1.status == "unverified_draft"
    assert len(d1.receipt_sha256) == 64
    assert drawer.unreviewed_count() == 1
    assert drawer.current_visual_state("idle").state == "bulb"

    drawer.set_status(d1.draft_id, "reviewed")
    assert drawer.unreviewed_count() == 0
    assert drawer.current_visual_state("idle").state == "ruby"

    doc = drawer.to_dict()
    assert doc["constitutional"]["glass_box_transparent"] is True
    assert doc["constitutional"]["hidden_private_thoughts"] is False
    assert doc["constitutional"]["external_actions"] == 0
    assert doc["constitutional"]["sentience_claimed"] is False

    with pytest.raises(ValueError):
        drawer.set_status(d1.draft_id, "secret_private")


def test_export_all_four_artline_brainstorm_concepts(tmp_path: Path) -> None:
    assert set(BRAINSTORM_CONCEPTS) == {"desk", "chess", "sector", "mondo"}
    results = export_all_brainstorm_concepts(tmp_path)
    assert len(results) == 4
    for res in results:
        assert res["elements"] >= 20
        assert res["constitutional"]["external_actions"] == 0
        assert res["constitutional"]["sentience_claimed"] is False
        for ext in ("svg", "png", "gem"):
            p = Path(res["paths"][ext])
            assert p.is_file() and res["sizes_bytes"][ext] > 500


def test_brainstorm_constitutional_flags_parity() -> None:
    expected = {
        "clean_room_original": True,
        "proprietary_code_copied": 0,
        "external_actions": 0,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "cloud_tokens_used": 0,
        "glass_box_transparent": True,
        "hidden_private_thoughts": False,
        "tokens_used": 0,
    }
    for key, val in expected.items():
        assert CONSTITUTIONAL_FLAGS[key] == val


def test_write_interactive_artline_studio_html_offline(tmp_path: Path) -> None:
    out_path = write_interactive_artline_studio_html(tmp_path / "nested" / "artline.html")
    assert out_path.is_file() and out_path.stat().st_size > 10_000
    html = out_path.read_text(encoding="utf-8")
    assert html.encode("utf-8") == render_artline_studio_html()
    assert html.count("<svg") >= 4
    for concept in ("desk", "chess", "sector", "mondo"):
        assert concept in html.lower()
    assert not re.search(r'<script[^>]+src=["\']https?://', html, flags=re.IGNORECASE)
    assert not re.search(r'<link[^>]+href=["\']https?://', html, flags=re.IGNORECASE)
    for marker in ("exportArtlineSvg", "exportArtlineGem", "exportArtlinePng", "zoe_artline_drafts_v1", 'href="/orbit"'):
        assert marker in html

    node_bin = shutil.which("node") or str(
        next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
    )
    if Path(node_bin).is_file():
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
        assert scripts
        for js in scripts:
            proc = subprocess.run([node_bin, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
            assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_t5_artline_brainstorm_corrupted_localstorage_normalization(tmp_path: Path) -> None:
    html_path = write_interactive_artline_studio_html(tmp_path / "artline.html")
    html = html_path.read_text(encoding="utf-8")
    assert "normalizedDrafts" in html
    node_bin = shutil.which("node") or str(
        next((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"), Path("node"))
    )
    if Path(node_bin).is_file():
        js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE))
        harness = (
            "const els = {};\n"
            "const mkEl = (id) => ({ id, innerHTML: '', textContent: '', value: '', style: {}, classList: { toggle() {} } });\n"
            "global.document = { getElementById(id){ return els[id] || (els[id] = mkEl(id)); } };\n"
            "global.localStorage = { getItem(){ return '[null, {}]'; }, setItem(){} };\n"
            + js
            + "\nrenderDrafts();\n"
        )
        proc = subprocess.run([node_bin, "-e", harness], input="", text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr

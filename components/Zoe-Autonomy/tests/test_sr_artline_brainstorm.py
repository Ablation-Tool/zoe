"""Unit tests for Zoe Artline Brainstorming Studio, visual state sprites, and Drafts Drawer."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_artline_brainstorm import (
    BRAINSTORM_CONCEPTS,
    STATE_SPRITE_MAP,
    IdeaScratchpadDrawer,
    export_all_brainstorm_concepts,
    render_state_sprite_png,
    render_state_sprite_terminal,
    resolve_visual_state,
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

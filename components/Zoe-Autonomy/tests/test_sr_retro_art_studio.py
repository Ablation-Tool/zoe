"""Unit tests for Zoe Clean-Room MS-DOS / Retro Art & Build-RE-Rebuild Evolution Studio."""

from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_retro_art_studio import (
    build_lsystem_idea_elaboration_plate,
    list_retro_inspirations,
    render_avatar_morph_gif,
    render_deluxepaint_kaleidoscope_gif,
    render_kloster_julia_fractal,
    render_msdos_ansi_blueprint,
    run_build_re_rebuild_cycle,
)


def test_deluxepaint_kaleidoscope_and_fractint_julia(tmp_path: Path) -> None:
    dp = render_deluxepaint_kaleidoscope_gif(
        tmp_path / "kaleido.gif",
        tmp_path / "kaleido.png",
        size=160,
        frames=8,
        symmetry_folds=8,
        dither=True,
    )
    assert dp["constitutional"]["clean_room_original"] is True
    assert dp["constitutional"]["copied_code_bytes"] == 0
    assert Path(dp["gif_path"]).stat().st_size > 1000
    with Image.open(dp["gif_path"]) as im:
        assert getattr(im, "n_frames", 1) == 8

    fr = render_kloster_julia_fractal(tmp_path / "julia.png", width=200, height=140, max_iter=48)
    assert Path(fr["png_path"]).stat().st_size > 1000
    assert 0.0 <= fr["interior_fraction"] <= 1.0


def test_autodesk_animator_morph_and_lsystem_hypercard(tmp_path: Path) -> None:
    morph = render_avatar_morph_gif(
        tmp_path / "morph.gif",
        tmp_path / "strip.png",
        frame_size=160,
        tweens_per_transition=4,
    )
    assert len(morph["keyframes"]) == 5
    assert morph["total_frames"] == 20
    with Image.open(morph["gif_path"]) as im:
        assert getattr(im, "n_frames", 1) == 20
    assert Path(morph["strip_png_path"]).stat().st_size > 1000

    doc, meta = build_lsystem_idea_elaboration_plate("Clean-Room Retro Studio", lsystem_depth=3)
    assert meta["lsystem_segments"] >= 20
    assert meta["cards"] == 4
    out_gem = tmp_path / "lsystem.gem"
    doc.export(out_gem, kind="gem")
    assert out_gem.stat().st_size > 500


def test_build_reverse_engineer_rebuild_monotonically_improves(tmp_path: Path) -> None:
    res = run_build_re_rebuild_cycle(tmp_path)
    assert res["monotonically_improved"] is True
    assert res["score_gain_gen1_to_gen3"] > 15.0
    assert len(res["generations"]) == 3
    assert res["constitutional"]["external_actions"] == 0
    assert res["constitutional"]["sentience_claimed"] is False

    ansi = render_msdos_ansi_blueprint(
        stats={
            "gen1_score": res["generations"][0]["overall_score"],
            "gen3_score": res["generations"][2]["overall_score"],
        }
    )
    assert "╔══" in ansi and "CLEAN-ROOM ORIGINAL" in ansi
    assert len(list_retro_inspirations()) == 6

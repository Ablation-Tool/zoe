"""Tier 5: Adversarial White-Box Edge-Case, CLI Error-Code & Regression E2E Tests."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from .conftest import (
    REPO_ROOT,
    assert_hygiene_clean,
    assert_offline_player_controls,
    run_zoe_cli,
    select_anthology_volume,
    verify_gem_bytes,
)

pytestmark = [pytest.mark.tier5]


# ===========================================================================
# 1. Graph Adversarial Layout, Malformed Adapters & Missing/Negative Guards
# ===========================================================================


@pytest.mark.graph
@pytest.mark.parametrize("chart_type", ["h_cluster", "h_stack"])
@pytest.mark.parametrize("region_h", [2400, 2000, 1700, 1500, 1200, 1000])
def test_t5_graph_horiz_sub_inch_plots_layout_ok(chart_type: str, region_h: int) -> None:
    """Sub-1-inch horizontal bar plots (down to region_h=1000) pass verify_layout() and emit valid .GEM."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.graph import GraphDoc

    cv = DrawPlusCanvas()
    gd = GraphDoc(
        title="Sub-Inch Horizontal Metric",
        chart_type=chart_type,
        categories=["Cat Alpha", "Cat Beta", "Cat Gamma", "Cat Delta", "Cat Epsilon"],
        series=[
            {"name": "Series One", "values": [10.0, 22.0, 34.0, 18.0, 45.0]},
            {"name": "Series Two", "values": [14.0, 19.0, 28.0, 25.0, 32.0]},
        ],
        x_label="Score",
        y_label="Category",
        label_pt=24.0,
    )
    gd.compile(cv, region=(500.0, 500.0, 6500.0, 500.0 + float(region_h)))
    rep = cv.verify_layout()
    assert rep.ok is True, f"{chart_type} region_h={region_h} failed: overlaps={rep.overlaps} oob={rep.out_of_bounds}"
    verify_gem_bytes(cv.to_gem_bytes())


@pytest.mark.graph
def test_t5_graph_malformed_dif_prn_csv_and_missing_files(tmp_path: Path) -> None:
    """Malformed .DIF, .PRN, and .CSV inputs raise ValueError and missing files raise FileNotFoundError."""
    from guiai.gem.presentation.graph import GraphDoc

    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("only_header\n", encoding="utf-8")
    with pytest.raises(ValueError):
        GraphDoc.from_csv(bad_csv)

    bad_dif = tmp_path / "bad.dif"
    bad_dif.write_text("TABLE\n0,1\n\"bad\"\nDATA\n-1,0\nBOT\n1,0\n\"OnlyOneCol\"\n-1,0\nEOD\n", encoding="utf-8")
    with pytest.raises(ValueError):
        GraphDoc.from_dif(bad_dif)

    bad_prn = tmp_path / "bad.prn"
    bad_prn.write_text("HeaderOnly\n", encoding="utf-8")
    with pytest.raises(ValueError):
        GraphDoc.from_prn(bad_prn)

    for loader, fname in (
        (GraphDoc.from_csv, "missing.csv"),
        (GraphDoc.from_dif, "missing.dif"),
        (GraphDoc.from_prn, "missing.prn"),
        (GraphDoc.from_json, "missing.json"),
    ):
        with pytest.raises(FileNotFoundError):
            loader(tmp_path / fname)


@pytest.mark.graph
def test_t5_graph_zero_sum_pie_and_all_none_series_zero(tmp_path: Path) -> None:
    """Zero-sum pie raises ValueError; all-None series[0] selects first populated series or raises cleanly."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.graph import GraphDoc

    with pytest.raises(ValueError, match="positive"):
        GraphDoc(
            title="Zero Pie",
            chart_type="pie",
            categories=["A", "B"],
            series=[{"name": "S0", "values": [0.0, 0.0]}],
        ).compile(DrawPlusCanvas())

    for ct in ("pie", "symbol", "map"):
        cv = DrawPlusCanvas()
        GraphDoc(
            title=f"Populated S1 ({ct})",
            chart_type=ct,
            categories=["A", "B"],
            series=[{"name": "Empty", "values": [None, None]}, {"name": "Pop", "values": [12.0, 28.0]}],
        ).compile(cv)
        assert len(cv.elements) > 3, f"{ct} should draw elements from populated series[1]"
        verify_gem_bytes(cv.to_gem_bytes())

        with pytest.raises(ValueError):
            GraphDoc(
                title=f"Tail-Only ({ct})",
                chart_type=ct,
                categories=["A", "B"],
                series=[{"name": "S0", "values": [None, None, 99.0]}],
            ).compile(DrawPlusCanvas())


@pytest.mark.graph
def test_t5_graph_isolated_area_points_and_negative_guards() -> None:
    """Isolated non-None points in area/stacked_area emit plot shapes; negative h_stack/stacked_area reject."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.graph import GraphDoc, GraphPreferences

    for ct in ("area", "stacked_area"):
        cv = DrawPlusCanvas()
        GraphDoc(
            title=f"Isolated {ct}",
            chart_type=ct,
            categories=["P1", "P2", "P3"],
            series=[{"name": "S", "values": [10.0, None, 25.0]}],
        ).compile(cv)
        circles = [el for el in cv.elements if el["type"] == "ellipse"]
        assert len(circles) >= 2, f"Expected isolated point shapes for {ct}"

    for neg_ct in ("h_stack", "stacked_area"):
        with pytest.raises(ValueError, match="negative"):
            GraphDoc(
                title="Neg",
                chart_type=neg_ct,
                categories=["A", "B"],
                series=[{"name": "S", "values": [5.0, -3.0]}],
            ).compile(DrawPlusCanvas())

        cv_abs = DrawPlusCanvas()
        doc_abs = GraphDoc(
            title="Abs",
            chart_type=neg_ct,
            categories=["A", "B"],
            series=[{"name": "S", "values": [5.0, -3.0]}],
            preferences=GraphPreferences(allow_negative_abs=True),
        )
        doc_abs.compile(cv_abs)
        assert doc_abs.warnings


# ===========================================================================
# 2. SlideShow, .LIS CWD Collision, Runs Hygiene & From-Spec Validation
# ===========================================================================


@pytest.mark.slideshow
def test_t5_lis_cwd_collision_preserves_subpaths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_lis_slide_entry resolves relative to lis_dir first even when CWD has same relative path."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.slideshow import parse_lis_playlist, write_lis_playlist

    cwd_dir = tmp_path / "cwd_dir"
    lis_dir = tmp_path / "lis_dir"
    (cwd_dir / "sub").mkdir(parents=True)
    (lis_dir / "sub").mkdir(parents=True)

    gem_bytes = DrawPlusCanvas().to_gem_bytes()
    (cwd_dir / "sub" / "slide-01.gem").write_bytes(gem_bytes)
    (lis_dir / "sub" / "slide-01.gem").write_bytes(gem_bytes)

    monkeypatch.chdir(cwd_dir)
    lis_path = lis_dir / "deck.lis"
    write_lis_playlist(lis_path, ["sub/slide-01.gem"])
    assert "sub/slide-01.gem" in lis_path.read_text(encoding="utf-8")
    parsed = parse_lis_playlist(lis_path, check_exists=True)
    assert [e.path for e in parsed.slides] == ["sub/slide-01.gem"]


@pytest.mark.slideshow
@pytest.mark.hygiene
def test_t5_slide_compile_scrubs_top_level_runs() -> None:
    """Slide.compile_to_canvas scrubs top-level el['runs'] passed directly to add_text."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.slideshow import Slide

    fake_secret = "/" + "home" + "/alice/secret.txt"
    cv = DrawPlusCanvas()
    cv.add_text([1000, 1000, 8000, 2000], "", runs=[{"text": f"Path: {fake_secret}"}])
    compiled = Slide(title="Runs Hygiene", canvas=cv).compile_to_canvas()
    assert getattr(compiled, "_hygiene_scrubs", 0) >= 1
    assert_hygiene_clean(json.dumps(compiled.elements), "compiled elements", strict_file_scheme=True)


@pytest.mark.slideshow
def test_t5_lis_comments_vs_directives_and_from_spec_validation(tmp_path: Path) -> None:
    """# comments in .LIS are ignored vs ; CYCLE=NO, and SlideDeck.from_spec rejects non-list slides."""
    from guiai.gem.presentation.slideshow import SlideDeck, parse_lis_playlist

    (tmp_path / "s1.gem").write_bytes(b"")
    lis_file = tmp_path / "comment_test.lis"
    lis_file.write_text(
        "# ; CYCLE=YES\n# cycle=true\n; WAIT=key\n; CYCLE=NO\ns1.gem\n",
        encoding="utf-8",
    )
    pl = parse_lis_playlist(lis_file, check_exists=True)
    assert pl.cycle is False
    assert pl.wait_mode == "key"
    assert pl.interval_seconds is None

    with pytest.raises(ValueError, match="list"):
        SlideDeck.from_spec({"slug": "bad-slides", "slides": 123})
    with pytest.raises(ValueError, match="object"):
        SlideDeck.from_spec({"slug": "bad-entry", "slides": [123]})


# ===========================================================================
# 3. Ledger Preservation, Exact Vol. Prefix & 1001 Hygiene Enforcement
# ===========================================================================


@pytest.mark.ledger
def test_t5_ledger_preserve_prefix_and_1001_hygiene(tmp_path: Path) -> None:
    """publish_ledger preserves existing decks, avoids Vol. I matching Vol. II, and checks 1001 hygiene."""
    from guiai.gem import vdi
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.ledger import _render_anthology_showcase, _verify_deck_gems, publish_ledger
    from guiai.gem.presentation.slideshow import Slide, SlideDeck
    from guiai.gem.presentation.wordchart import WordChartDoc

    companion = SlideDeck(
        slug="00-companion-keep",
        title="Companion Keep",
        volume_label="Companion",
        slides=[Slide("S1", WordChartDoc(title="S1", text_body=["Kept"]))],
    )
    publish_ledger([companion], tmp_path, preserve_existing=False, render_jpg=True)

    vol1 = SlideDeck(
        slug="vol-1-demo",
        title="Vol. II Lookalike",
        volume_label="Vol. I",
        slides=[Slide("C1", WordChartDoc(title="C1", text_body=["Vol 1"]))],
    )
    res = publish_ledger([vol1], tmp_path, preserve_existing=True, render_jpg=False)
    assert res["catalog"]["deck_count"] == 2
    assert not list((tmp_path / "galleries" / "vol-1-demo").glob("slide-*.jpg"))
    hub_md = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert 'alt="Vol. I: Vol. II Lookalike"' in hub_md

    showcase = "\n".join(
        _render_anthology_showcase(
            [{"slug": "vol-1-demo", "volume_label": "Vol. I", "title": "Vol. II Lookalike", "slides": 1, "gems": ["g"], "cover": "galleries/vol-1-demo/slide-01.png", "gallery": "galleries/vol-1-demo/README.md"}],
            tmp_path,
        )
    )
    assert 'alt="Vol. I: Vol. II Lookalike"' in showcase

    # Injecting unscrubbed personal path into 1001 metadata must fail _verify_deck_gems
    cv = DrawPlusCanvas()
    raw_gem = cv.to_gem_bytes()
    parsed = vdi.parse_metafile(raw_gem)
    assert parsed["header"]["coordinate_bounds"] == (0, 0, 13333, 7500)
    bad_rec = vdi.meta_json_record({"id": "leak", "type": "rectangle", "role": "/" + "home" + "/alice/x"}, 1001)
    tampered = raw_gem[:-2] + bad_rec + raw_gem[-2:]
    bad_gem_path = tmp_path / "tampered.gem"
    bad_gem_path.write_bytes(tampered)
    with pytest.raises(ValueError, match="Hygiene"):
        _verify_deck_gems([bad_gem_path])


# ===========================================================================
# 4. WordChart Decimal Overflow & Locator Bounds
# ===========================================================================


@pytest.mark.wordchart
def test_t5_wordchart_strict_decimal_overflow_and_tiny_locator(tmp_path: Path) -> None:
    """strict_decimal rejects non-numeric text, verify_layout catches decimal overflow, <320 locator fails."""
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas
    from guiai.gem.presentation.wordchart import WordChartDoc

    with pytest.raises(ValueError, match="Non-numeric"):
        WordChartDoc(
            title="Strict",
            alignments=["decimal"],
            text_body=["N/A"],
            strict_decimal=True,
        ).compile(DrawPlusCanvas())

    cv_dec = DrawPlusCanvas()
    WordChartDoc(
        template="column_1",
        alignments=["decimal"],
        text_body=["1234567890.1", "1.1234567890"],
        point_size=28.0,
    ).compile(cv_dec, region=(1000.0, 1000.0, 3800.0, 3000.0))
    rep = cv_dec.verify_layout()
    assert rep.ok is False and any("text overflow" in m for m in rep.out_of_bounds)

    tiny_border = DrawPlusCanvas()
    tiny_border.add_rectangle([100.0, 100.0, 300.0, 300.0], fill="none", stroke="black", role="locator")
    tiny_gem = tmp_path / "tiny_loc.gem"
    tiny_gem.write_bytes(tiny_border.to_gem_bytes())
    with pytest.raises(ValueError, match="Locator"):
        WordChartDoc(title="Tiny", text_body=["X"], border_gem_path=tiny_gem).compile(DrawPlusCanvas())


# ===========================================================================
# 5. Draw Plus & VDI Adversarial Boundaries
# ===========================================================================


@pytest.mark.draw_plus
def test_t5_draw_plus_transforms_and_vdi_overflows() -> None:
    """Transforms keep text upright / detect rotated OOB; VDI rejects >255 palette, int16 shadow, >4096 meta."""
    from guiai.gem import vdi
    from guiai.gem.model import Scene
    from guiai.gem.presentation.draw_plus import DrawPlusCanvas

    cv = DrawPlusCanvas()
    tid = cv.add_text([1000.0, 1000.0, 3000.0, 1600.0], "FlipMe", align="left", font_pt=12.0)
    cv.flip_h([tid], axis_x=4000.0)
    el = next(e for e in cv.elements if e["id"] == tid)
    assert el["align"] == "right"
    assert el["bounds"][0] == pytest.approx(5000.0)
    cv.flip_v([tid], axis_y=3000.0)
    assert el["bounds"][1] == pytest.approx(4400.0)
    cv.rotate_90([tid], ccw=True)
    assert el["rotation"] == pytest.approx(90.0)

    cv_oob = DrawPlusCanvas()
    tid_edge = cv_oob.add_text([100.0, 100.0, 1500.0, 400.0], "LongRotatedEdgeText", font_pt=12.0)
    cv_oob.rotate_90([tid_edge], ccw=True)
    rep_oob = cv_oob.verify_layout()
    assert rep_oob.ok is False and rep_oob.out_of_bounds

    # 256-color palette overflow
    objs = [
        {"id": f"r{i}", "type": "rectangle", "bounds": [10, 10, 100, 100], "fill": f"#{i:02x}1122", "stroke": "none", "width": 0.0}
        for i in range(245)
    ]
    scene = Scene.from_dict({"schema_version": 1, "id": "pal", "title": "Pal", "canvas": {"width": 13333, "height": 7500}, "objects": objs, "constraints": []})
    with pytest.raises(ValueError, match="256-entry VDI palette"):
        vdi.scene_to_metafile(scene)

    # shadow=True near 32767 int16 boundary
    cv_sh = DrawPlusCanvas()
    cv_sh.add_rectangle([32700, 100, 32750, 200], fill="#B81D48", shadow=True)
    with pytest.raises(ValueError, match="signed 16-bit"):
        cv_sh.to_gem_bytes()

    # >4096-byte 1001 metadata overflow
    with pytest.raises(ValueError, match="too large"):
        vdi.meta_json_record({"payload": "A" * 4500}, 1001)


# ===========================================================================
# 6. `zoe present` CLI Error Exit Codes (returncode == 2, zero Traceback)
# ===========================================================================


@pytest.mark.slideshow
def test_t5_zoe_present_cli_error_exit_codes(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """Missing subcommand, missing path, corrupt .gem, and malformed JSON exit 2 with no Python traceback."""
    bad_gem = tmp_path / "corrupt.gem"
    bad_gem.write_bytes(b"NOT_A_GEM_METAFILE")

    bad_json = tmp_path / "bad_slides.json"
    bad_json.write_text(json.dumps({"slug": "bad", "slides": 123}), encoding="utf-8")

    cases = [
        ["present"],
        ["present", "inspect", str(tmp_path / "does_not_exist.gem")],
        ["present", "build", str(tmp_path / "missing_spec.json"), "-o", str(tmp_path / "out1")],
        ["present", "inspect", str(bad_gem)],
        ["present", "render", str(bad_gem), "-o", str(tmp_path / "out2")],
        ["present", "build", str(bad_json), "-o", str(tmp_path / "out3")],
    ]
    for argv in cases:
        proc = run_zoe_cli(argv, env=isolated_pres_env)
        assert proc.returncode == 2, f"Expected exit 2 for {argv}, got {proc.returncode}: stderr={proc.stderr!r}"
        assert "Traceback" not in proc.stderr, f"Unexpected traceback for {argv}: {proc.stderr!r}"


# ===========================================================================
# 7. Anthology Vol. IV-VI Symmetry & Content Integrity + Conftest Helpers
# ===========================================================================


@pytest.mark.anthology
def test_t5_anthology_vol4_6_alias_and_vol4_vol5_polish() -> None:
    """build_anthology_vol4_6 alias exists, Vol. IV separates C source vs binary, Vol. V Slide 5 has 1 bullet."""
    from guiai.gem.presentation import anthology_vol1_3, anthology_vol4_6

    assert anthology_vol4_6.build_anthology_vol4_6 is anthology_vol4_6.build_anthology_vol4_6_decks
    assert hasattr(anthology_vol1_3, "build_anthology_vol1_3")
    assert "build_anthology_vol4_6" in anthology_vol4_6.__all__

    vol4, vol5, _vol6 = anthology_vol4_6.build_anthology_vol4_6(repo_root=REPO_ROOT)
    s3_cv = vol4.slides[2].compile_to_canvas(sister_id=vol4.sister_id, slide_index=3, constitutional=vol4.constitutional)
    s3_texts = " ".join(str(el.get("text", "")) for el in s3_cv.elements if el.get("type") == "text")
    assert "188,511" in s3_texts and "4,999" in s3_texts and "1.1 MB" in s3_texts
    assert "1.1 MB" in vol4.slides[2].speaker_notes

    s5_cv = vol5.slides[4].compile_to_canvas(sister_id=vol5.sister_id, slide_index=5, constitutional=vol5.constitutional)
    s5_texts = [str(el.get("text", "")) for el in s5_cv.elements if el.get("type") == "text"]
    auditor_bullets = [t for t in s5_texts if "ToolSurfaceEnumerator" in t]
    assert len(auditor_bullets) == 1
    assert "4 Wave-3 AI-agent byte auditors" in auditor_bullets[0]
    assert "AIControlIndicators" in auditor_bullets[0]


@pytest.mark.ledger
def test_t5_conftest_volume_selector_and_player_case_insensitivity() -> None:
    """select_anthology_volume prefers slug/gallery over title mentions; player shortcuts accept uppercase."""
    decks = [
        {"slug": "appendix-notes", "title": "Appendix referencing Vol. 2", "gallery": "galleries/appendix/README.md"},
        {"slug": "vol-2-real", "title": "Real Second Deck", "gallery": "galleries/vol-2-real/README.md"},
    ]
    picked = select_anthology_volume(decks, 2)
    assert picked["slug"] == "vol-2-real"

    upper_html = (
        "' ' ArrowRight ArrowLeft ArrowUp Escape prefers-reduced-motion Cycle 20s 10s 5s 2s "
        "'T' 'L' 'F' 'N' 'G'"
    )
    assert_offline_player_controls(upper_html)

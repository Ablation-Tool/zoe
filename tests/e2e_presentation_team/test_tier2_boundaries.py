"""Tier 2 Boundary, Corner-Case, and Negative/Error-Path Tests across Areas F1-F8."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import pytest

from .conftest import (
    REPO_ROOT,
    assert_constitutional_flags,
    assert_hygiene_clean,
    call_with_supported_kwargs,
    find_hygiene_violations,
    ordered_anthology_volumes,
    parse_sha256sums,
    pick,
    require_contract,
    run_zoe_cli,
    scan_markdown_links,
    select_anthology_volume,
    sha256_file,
    verify_gem_bytes,
    verify_rendered_image,
    verify_svg_document,
)

pytestmark = pytest.mark.tier2


def _new_canvas() -> Any:
    canvas_cls = require_contract("guiai.gem.presentation.draw_plus", "DrawPlusCanvas", req_id="R1/F3")
    return call_with_supported_kwargs(canvas_cls, width=13333, height=7500, title="Tier2 Boundary")


def _published_catalog() -> dict[str, Any]:
    cat_path = REPO_ROOT / "research" / "presentations" / "catalog.json"
    assert cat_path.is_file(), f"[R2/F6] Missing catalog.json: {cat_path}"
    return json.loads(cat_path.read_text(encoding="utf-8"))


def _vol_decks(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    decks = [
        d for d in catalog.get("decks", [])
        if str(d.get("slug", "")).startswith("vol-") or "vol." in str(d.get("title", "")).lower()
    ]
    assert len(decks) >= 6, f"[R2/F5] Expected 6 Anthology volumes (Vol. I-VI), found {len(decks)}"
    return decks


# ===========================================================================
# Area F1: WordChart Boundaries (6 tests)
# ===========================================================================


@pytest.mark.wordchart
def test_wordchart_empty_zones_gracefully_handled(tmp_path: Path) -> None:
    """WordChart with empty body, column_head, and footer still compiles valid .GEM and PNG."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(wc_cls, title="Title Only", column_head=[], text_body=[], footer="", template="column_1")
    canvas = _new_canvas()
    doc.compile(canvas)
    verify_gem_bytes(canvas.to_gem_bytes())
    png = tmp_path / "empty_zones.png"
    call_with_supported_kwargs(canvas.render_png, png, width=1280, height=720)
    verify_rendered_image(png)


@pytest.mark.wordchart
def test_wordchart_overflow_text_triggers_diagnostic_or_safe_wrap(tmp_path: Path) -> None:
    """Overlong WordChart body either wraps all lines inside safe bounds or flags overflow in verify_layout()."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    huge_lines = [f"Line {i:02d}: " + ("Metacognition " * 8) for i in range(45)]
    doc = call_with_supported_kwargs(wc_cls, title="Overflow Test", template="column_1", text_body=huge_lines)
    canvas = _new_canvas()
    doc.compile(canvas)
    report = canvas.verify_layout()
    overflows = pick(doc, "overflow_warnings", "diagnostics", default=[])
    ok = pick(report, "ok", "passed")
    if (not ok) or bool(overflows):
        return
    out_of_bounds = pick(report, "out_of_bounds", default=[])
    assert not out_of_bounds, f"WordChart reported ok=True with out_of_bounds={out_of_bounds}"
    verify_gem_bytes(canvas.to_gem_bytes())
    svg_path = tmp_path / "overflow.svg"
    canvas.render_svg(svg_path)
    svg_text = svg_path.read_text(encoding="utf-8")
    missing = [f"Line {i:02d}:" for i in range(45) if f"Line {i:02d}:" not in svg_text]
    assert not missing, f"WordChart silently dropped lines without overflow warning: {missing[:5]}"


@pytest.mark.wordchart
def test_wordchart_invalid_template_or_zero_columns_raises_value_error() -> None:
    """Invalid WordChart template name raises ValueError cleanly."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    with pytest.raises(ValueError):
        doc = call_with_supported_kwargs(wc_cls, title="Bad Template", template="nonexistent_template_99", text_body=["X"])
        canvas = _new_canvas()
        doc.compile(canvas)


@pytest.mark.wordchart
def test_wordchart_decimal_align_handles_negative_and_non_numeric_tokens(tmp_path: Path) -> None:
    """Decimal alignment handles negative numbers, integers, high precision, and N/A strings."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(
        wc_cls,
        title="Decimal BVA",
        template="column_1",
        alignments=["decimal"],
        text_body=["-45.07", "0", "0.99992", "138240", "N/A"],
    )
    canvas = _new_canvas()
    doc.compile(canvas)
    svg = tmp_path / "dec_bva.svg"
    canvas.render_svg(svg)
    verify_svg_document(svg.read_text(encoding="utf-8"))


@pytest.mark.wordchart
def test_wordchart_locator_rect_missing_or_out_of_bounds_rejected(tmp_path: Path) -> None:
    """WordChart rejects .GEM border files lacking a locator rectangle or overflowing canvas bounds."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    from guiai.gem import model as gem_model, vdi

    no_locator_scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "no_locator",
        "title": "No Locator",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [{"id": "frame", "type": "rectangle", "bounds": [100, 100, 13233, 7400], "fill": "none", "stroke": "#C29130", "width": 12}],
    })
    bad_border = tmp_path / "no_locator.gem"
    vdi.write_metafile(no_locator_scene, bad_border)
    with pytest.raises(ValueError):
        doc = call_with_supported_kwargs(wc_cls, title="Missing Locator", text_body=["Hello"], border_gem_path=bad_border)
        doc.compile(_new_canvas())


@pytest.mark.wordchart
def test_wordchart_xml_metacharacters_and_unicode_escape_safely(tmp_path: Path) -> None:
    """Special XML characters (<>&\"') and Unicode symbols compile to valid XML SVG."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    text = "A_tau(p) < 16 & 'Kloster' > \"baseline\" — x"
    doc = call_with_supported_kwargs(wc_cls, title=text, text_body=[text], footer="Nicholas x Zoe")
    canvas = _new_canvas()
    doc.compile(canvas)
    svg_path = tmp_path / "escape.svg"
    canvas.render_svg(svg_path)
    root = verify_svg_document(svg_path.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")


# ===========================================================================
# Area F2: Graph Boundaries (6 tests)
# ===========================================================================


@pytest.mark.graph
def test_graph_none_missing_data_preserves_gap_distinct_from_zero(tmp_path: Path) -> None:
    """Graph distinguishes None (missing gap) from 0.0 without collapsing to zero or returning empty SVG."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    doc_gap = call_with_supported_kwargs(
        graph_cls,
        title="Missing vs Zero",
        chart_type="line",
        categories=["Q1", "Q2", "Q3"],
        series=[{"name": "Series", "values": [10.0, None, 30.0]}],
    )
    doc_zero = call_with_supported_kwargs(
        graph_cls,
        title="Missing vs Zero",
        chart_type="line",
        categories=["Q1", "Q2", "Q3"],
        series=[{"name": "Series", "values": [10.0, 0.0, 30.0]}],
    )

    canvas_gap = _new_canvas()
    doc_gap.compile(canvas_gap)
    svg_gap_path = tmp_path / "gap.svg"
    canvas_gap.render_svg(svg_gap_path)
    svg_gap = svg_gap_path.read_text(encoding="utf-8")
    root_gap = verify_svg_document(svg_gap)

    canvas_zero = _new_canvas()
    doc_zero.compile(canvas_zero)
    svg_zero_path = tmp_path / "zero.svg"
    canvas_zero.render_svg(svg_zero_path)
    svg_zero = svg_zero_path.read_text(encoding="utf-8")
    root_zero = verify_svg_document(svg_zero)

    shape_tags = {"path", "polyline", "line", "rect", "circle", "ellipse", "polygon"}
    geom_gap = [
        (el.tag.split("}", 1)[-1], {k: v for k, v in sorted(el.attrib.items()) if k != "id"})
        for el in root_gap.iter()
        if el.tag.split("}", 1)[-1] in shape_tags
    ]
    geom_zero = [
        (el.tag.split("}", 1)[-1], {k: v for k, v in sorted(el.attrib.items()) if k != "id"})
        for el in root_zero.iter()
        if el.tag.split("}", 1)[-1] in shape_tags
    ]
    assert geom_gap and geom_zero, "Graph SVG must emit non-empty geometry"
    assert svg_gap != svg_zero and geom_gap != geom_zero, (
        "[R1/F2] GraphDoc collapsed None missing-data gap to 0.0 (identical SVG geometry)"
    )


@pytest.mark.graph
@pytest.mark.parametrize("chart_type", ["pie", "stacked_bar", "stacked_100_bar"])
def test_graph_negative_values_rejected_in_pie_and_stacked_bars(chart_type: str) -> None:
    """Pie, stacked bar, and 100% stacked bar reject negative values with ValueError."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    with pytest.raises(ValueError):
        doc = call_with_supported_kwargs(
            graph_cls,
            title="Invalid Negative",
            chart_type=chart_type,
            categories=["A", "B", "C"],
            series=[{"name": "S", "values": [10.0, -5.0, 20.0]}],
        )
        doc.compile(_new_canvas())


@pytest.mark.graph
def test_graph_deviation_bar_supports_negative_and_positive_values(tmp_path: Path) -> None:
    """Deviation bar chart renders negative and positive deltas around zero cleanly."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    doc = call_with_supported_kwargs(
        graph_cls,
        title="Causal Ablation Delta",
        chart_type="deviation_bar",
        categories=["ON", "Randomized", "OFF"],
        series=[{"name": "Reward", "values": [34.52, 8.48, -45.07]}],
    )
    canvas = _new_canvas()
    doc.compile(canvas)
    assert pick(canvas.verify_layout(), "ok", "passed") is True
    png = tmp_path / "dev_bar.png"
    call_with_supported_kwargs(canvas.render_png, png, width=1280, height=720)
    verify_rendered_image(png)


@pytest.mark.graph
def test_graph_empty_dataset_raises_value_error() -> None:
    """Empty categories or empty series raises ValueError rather than ZeroDivisionError."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    with pytest.raises(ValueError):
        doc = call_with_supported_kwargs(graph_cls, title="Empty", chart_type="bar", categories=[], series=[])
        doc.compile(_new_canvas())


@pytest.mark.graph
def test_graph_extreme_scale_and_constant_zero_range_values(tmp_path: Path) -> None:
    """Graph handles wide dynamic range [1e-4, 1e9] and constant values [5.0, 5.0, 5.0] safely."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    for name, vals in (("wide", [1e-4, 100.0, 1e9]), ("flat", [5.0, 5.0, 5.0])):
        doc = call_with_supported_kwargs(
            graph_cls,
            title=f"Scale {name}",
            chart_type="bar",
            categories=["A", "B", "C"],
            series=[{"name": name, "values": vals}],
        )
        canvas = _new_canvas()
        doc.compile(canvas)
        svg = tmp_path / f"{name}.svg"
        canvas.render_svg(svg)
        verify_svg_document(svg.read_text(encoding="utf-8"))


@pytest.mark.graph
def test_graph_long_category_labels_auto_shrink_without_overlap() -> None:
    """Long category labels trigger plot-area auto-sizing so verify_layout().ok stays True."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    doc = call_with_supported_kwargs(
        graph_cls,
        title="Long Labels Auto-Shrink",
        chart_type="bar",
        categories=[
            "Operational Metacognition Proof Packet",
            "Hexagonal Nine-Sister EDDBMS Mesh",
            "Bare-Metal UEFI Zoe-GEM OS Boot",
            "Neuro-Oncology Botanical Atlas C27",
        ],
        series=[{"name": "Score", "values": [99.1, 98.4, 96.2, 97.5]}],
    )
    canvas = _new_canvas()
    doc.compile(canvas)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is True, f"Overlap with long labels: {report}"


# ===========================================================================
# Area F3: Draw Plus & .GEM VDI Boundaries (6 tests)
# ===========================================================================


@pytest.mark.draw_plus
def test_vdi_int16_exact_32767_limit_succeeds_and_32768_raises() -> None:
    """Self-contained: VDI signed int16 allows 32767/-32768 and raises ValueError on 32768/-32769."""
    from guiai.gem import model as gem_model, vdi

    valid_scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "int16_ok",
        "title": "Boundary 32767",
        "canvas": {"width": 32767, "height": 32767},
        "objects": [{"id": "box", "type": "rectangle", "bounds": [0, 0, 32767, 32767], "fill": "white", "stroke": "black", "width": 1}],
    })
    raw = vdi.scene_to_metafile(valid_scene)
    assert vdi.parse_metafile(raw)["bytes_consumed"] == len(raw)

    for bad_val in (32768, -32769):
        with pytest.raises(ValueError):
            vdi._word(bad_val)
        with pytest.raises(ValueError):
            gem_model.Scene.from_dict({
                "schema_version": 1,
                "id": "int16_bad",
                "title": "Overflow",
                "canvas": {"width": 13333, "height": 7500},
                "objects": [{"id": "line", "type": "line", "points": [[0, 0], [bad_val, 100]], "fill": "none", "stroke": "black", "width": 1}],
            })


@pytest.mark.draw_plus
def test_vdi_parse_metafile_rejects_truncated_and_unterminated_bytes() -> None:
    """Self-contained: vdi.parse_metafile rejects truncated headers, missing EOF, and trailing bytes."""
    from guiai.gem import model as gem_model, vdi

    scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "valid",
        "title": "Valid",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [{"id": "r", "type": "rectangle", "bounds": [100, 100, 500, 500], "fill": "red", "stroke": "black", "width": 2}],
    })
    valid = vdi.scene_to_metafile(scene)
    for corrupt in (valid[:12], valid[:-2], valid + b"\x00\x00", b"\x00" * 60):
        with pytest.raises(ValueError):
            vdi.parse_metafile(corrupt)


@pytest.mark.draw_plus
def test_draw_plus_verify_layout_detects_intentional_text_overlap() -> None:
    """DrawPlusCanvas.verify_layout() flags overlapping text bounding boxes."""
    canvas = _new_canvas()
    canvas.add_text(1500, 2000, "First Overlapping Headline", color="#0B1220", size=320)
    canvas.add_text(1650, 2050, "Second Colliding Headline", color="#B81D48", size=320)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is False
    assert len(pick(report, "overlaps")) >= 1


@pytest.mark.draw_plus
def test_draw_plus_verify_layout_detects_out_of_bounds_element() -> None:
    """DrawPlusCanvas.verify_layout() flags elements extending outside canvas safe bounds."""
    canvas = _new_canvas()
    canvas.add_text(12900, 7450, "Clipped Right Edge Text", color="#0B1220", size=300)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is False
    assert len(pick(report, "out_of_bounds")) >= 1


@pytest.mark.draw_plus
def test_draw_plus_empty_canvas_and_zero_radius_degenerate_shape(tmp_path: Path) -> None:
    """Empty canvas compiles validly and zero-radius shape either raises ValueError or renders cleanly."""
    canvas = _new_canvas()
    verify_gem_bytes(canvas.to_gem_bytes())
    try:
        canvas.add_circle(3000, 3000, 0, fill="#B81D48", stroke="#0B1220")
        png = tmp_path / "zero_r.png"
        call_with_supported_kwargs(canvas.render_png, png, width=640, height=360)
        assert png.is_file()
    except ValueError:
        pass


@pytest.mark.draw_plus
def test_render_svg_and_png_reject_invalid_widths(tmp_path: Path) -> None:
    """Self-contained: render.scene_to_svg and write_png reject invalid widths and succeed at 320px."""
    from guiai.gem import model as gem_model, render

    scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "width_bva",
        "title": "Width BVA",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [{"id": "bg", "type": "rectangle", "bounds": [100, 100, 13233, 7400], "fill": "blue", "stroke": "black", "width": 8}],
    })
    for bad_w in (0, -1, True, 16385):
        with pytest.raises(ValueError):
            render.scene_to_svg(scene, width=bad_w)
        with pytest.raises(ValueError):
            render.write_png(scene, tmp_path / "bad.png", width=bad_w)
    out_png = tmp_path / "ok_320.png"
    render.write_png(scene, out_png, width=320)
    verify_rendered_image(out_png)


# ===========================================================================
# Area F4: Slide Show Player & CLI Boundaries (6 tests)
# ===========================================================================


@pytest.mark.slideshow
def test_slideshow_empty_deck_rejected(tmp_path: Path) -> None:
    """Empty SlideDeck raises ValueError rather than producing an empty broken player."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    with pytest.raises(ValueError):
        deck = call_with_supported_kwargs(deck_cls, slug="empty", title="Empty", slides=[])
        call_with_supported_kwargs(deck.build, tmp_path / "empty_out")


@pytest.mark.slideshow
def test_lis_playlist_missing_slide_raises_error(tmp_path: Path) -> None:
    """Parsing/validating a .LIS playlist pointing to a nonexistent slide file raises an error."""
    ss_mod = require_contract("guiai.gem.presentation.slideshow", req_id="R1/F4")
    lis_path = tmp_path / "broken.lis"
    lis_path.write_text("missing-slide-01.gem\n", encoding="utf-8")
    validate_fn = pick(ss_mod, "validate_lis_playlist", "load_lis_playlist", "parse_lis_playlist")
    with pytest.raises((FileNotFoundError, ValueError)):
        if "check_exists" in inspect.signature(validate_fn).parameters:
            validate_fn(lis_path, check_exists=True)
        else:
            validate_fn(lis_path)


@pytest.mark.slideshow
def test_player_html_escapes_adversarial_titles_and_notes(tmp_path: Path) -> None:
    """Adversarial script-injection strings in slide title/notes are safely escaped in player.html."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    payload = "</script><img src=x onerror=alert(1)>"
    slide = call_with_supported_kwargs(
        slide_cls,
        title=payload,
        content=call_with_supported_kwargs(wc_cls, title="Safe", text_body=[payload]),
        speaker_notes=payload,
    )
    deck = call_with_supported_kwargs(deck_cls, slug="xss-check", title=payload, slides=[slide])
    out_dir = tmp_path / "xss_out"
    call_with_supported_kwargs(deck.build, out_dir)
    html = (out_dir / "player.html").read_text(encoding="utf-8")
    lowered = html.lower()
    assert "<img src=x onerror=alert(1)>" not in lowered
    assert "</script><img" not in lowered
    assert len(re.findall(r"<script\b", lowered)) == len(re.findall(r"</script\s*>", lowered)), (
        "Unescaped </script> breakout detected inside player.html"
    )


@pytest.mark.slideshow
def test_zoe_present_invalid_subcommand_exits_2(isolated_pres_env: dict[str, str]) -> None:
    """`zoe present nonexistent-cmd` fails cleanly with exit code 2 and no Python traceback."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    proc = run_zoe_cli(["present", "nonexistent-cmd"], env=isolated_pres_env)
    assert proc.returncode == 2
    assert "Traceback (most recent call last)" not in proc.stderr


@pytest.mark.slideshow
def test_zoe_present_missing_input_file_fails_cleanly(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """`zoe present build` with missing input path exits non-zero cleanly without traceback."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    proc = run_zoe_cli(["present", "build", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out")], env=isolated_pres_env)
    assert proc.returncode != 0
    assert "Traceback (most recent call last)" not in proc.stderr


@pytest.mark.slideshow
def test_zoe_present_no_overwrite_protects_existing_output(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """`zoe present build` refuses to clobber existing output when overwrite is disabled."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"slug": "safe", "title": "Safe", "slides": [{"title": "S1", "text_body": ["OK"]}]}), encoding="utf-8")
    out_dir = tmp_path / "existing_out"
    out_dir.mkdir()
    sentinel_player = out_dir / "player.html"
    sentinel_player.write_text("KEEP_ME", encoding="utf-8")
    proc = run_zoe_cli(["present", "build", str(spec), "--output", str(out_dir), "--no-overwrite"], env=isolated_pres_env)
    assert proc.returncode != 0
    assert sentinel_player.read_text(encoding="utf-8") == "KEEP_ME"


# ===========================================================================
# Area F5: Anthology Volumes I-VI Boundaries (6 tests)
# ===========================================================================


@pytest.mark.anthology
def test_every_anthology_gem_metafile_passes_seasip_and_rc_13333x7500() -> None:
    """Every published .gem metafile in Anthology Vol. I-VI passes seasip_gem and 13333x7500 RC bounds."""
    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        gallery_dir = (pres_root / deck["gallery"]).parent
        gem_files = sorted(gallery_dir.glob("*.gem")) + sorted((pres_root / "decks").glob(f"*{deck['slug']}*.gem"))
        assert gem_files, f"[R2/F5] No .gem files found for {deck['slug']}"
        for gf in gem_files:
            verify_gem_bytes(gf.read_bytes())


@pytest.mark.anthology
def test_every_anthology_rendered_slide_opens_16_9_non_blank() -> None:
    """Every rendered slide PNG/JPG in Vol. I-VI opens via Pillow with 16:9 ratio and non-zero variance."""
    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        gallery_dir = (pres_root / deck["gallery"]).parent
        imgs = sorted(p for p in gallery_dir.iterdir() if p.is_file() and p.name.startswith("slide-") and p.suffix.lower() in (".png", ".jpg"))
        assert imgs, f"[R2/F5] No slide images found for {deck['slug']}"
        for img_path in imgs:
            verify_rendered_image(img_path)


@pytest.mark.anthology
def test_anthology_slides_have_zero_placeholder_text() -> None:
    """Vol. I-VI gallery transcripts and notes contain zero TODO/TBD/FIXME/lorem placeholder text."""
    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        txt = (pres_root / deck["gallery"]).read_text(encoding="utf-8").lower()
        for bad in ("todo:", "tbd", "fixme", "lorem ipsum", "[placeholder]"):
            assert bad not in txt, f"[R2/F5] Placeholder {bad!r} found in {deck['slug']}"


@pytest.mark.anthology
def test_anthology_vol1_and_vol6_honest_abstention_boundaries() -> None:
    """Vol. I documents negative control / abstention and Vol. VI keeps l5_agi_qualified=False."""
    catalog = _published_catalog()
    vol_decks = _vol_decks(catalog)
    pres_root = REPO_ROOT / "research" / "presentations"
    vol1_deck = select_anthology_volume(vol_decks, 1)
    vol6_deck = select_anthology_volume(vol_decks, 6)
    vol1 = (pres_root / vol1_deck["gallery"]).read_text(encoding="utf-8")
    vol6 = (pres_root / vol6_deck["gallery"]).read_text(encoding="utf-8")
    assert "0.4087" in vol1 or "abstain" in vol1.lower() or "abstention" in vol1.lower()
    assert re.search(
        r"l5_agi_qualified\s*[`*_'\"]*\s*[=:]\s*[`*_'\"]*false\b|l5[^.\n]{0,40}\bnot qualified\b",
        vol6.lower(),
    ), "[R2.6/F5] Vol. VI missing explicit l5_agi_qualified=False / not qualified epistemic boundary"


@pytest.mark.anthology
def test_anthology_vol2_and_vol3_clinical_and_kryptos_boundaries() -> None:
    """Vol. II keeps cure_claim/clinical_action_authorized=False and Vol. III notes K4 unsolved."""
    catalog = _published_catalog()
    vol_decks = _vol_decks(catalog)
    pres_root = REPO_ROOT / "research" / "presentations"
    vol2_deck = select_anthology_volume(vol_decks, 2)
    vol3_deck = select_anthology_volume(vol_decks, 3)
    vol2 = (pres_root / vol2_deck["gallery"]).read_text(encoding="utf-8").lower()
    vol3 = (pres_root / vol3_deck["gallery"]).read_text(encoding="utf-8").lower()
    assert re.search(
        r"cure_claim\s*[`*_'\"]*\s*[=:]\s*[`*_'\"]*false\b|no cure claim|cure claim\s*[=:]\s*false\b",
        vol2,
    ), "[R2.2/F5] Vol. II missing explicit cure_claim=False / no cure claim boundary"
    assert "k4" in vol3 or "kryptos" in vol3


@pytest.mark.anthology
def test_anthology_decks_do_not_require_pptx_at_runtime() -> None:
    """Every Vol. I-VI deck ships native .gem + rendered slide sheets + player.html without needing .pptx."""
    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        gallery_dir = (pres_root / deck["gallery"]).parent
        assert (gallery_dir / "player.html").is_file(), f"[R1/F5] Missing player.html in {gallery_dir}"
        assert list(gallery_dir.glob("*.gem")) or list((pres_root / "decks").glob(f"*{deck['slug']}*.gem"))


# ===========================================================================
# Area F6: Ledger & Checksums Boundaries (6 tests)
# ===========================================================================


@pytest.mark.ledger
def test_sha256_tamper_detected_on_copied_ledger_in_tmp_path(tmp_path: Path) -> None:
    """Self-contained: flipping 1 byte in a sealed presentation file is caught by SHA-256 check."""
    pres_root = REPO_ROOT / "research" / "presentations"
    entries = parse_sha256sums(pres_root / "SHA256SUMS.presentations")
    expected_hex, rel_path = entries[0]
    copied = tmp_path / Path(rel_path).name
    data = bytearray((pres_root / rel_path).read_bytes())
    data[len(data) // 2] ^= 0xFF
    copied.write_bytes(bytes(data))
    assert sha256_file(copied) != expected_hex


@pytest.mark.ledger
def test_publish_ledger_rejects_duplicate_slugs(tmp_path: Path) -> None:
    """publish_ledger rejects duplicate deck slugs cleanly with ValueError."""
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/F6")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")

    def make_deck() -> Any:
        s = call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["X"]))
        return call_with_supported_kwargs(deck_cls, slug="dup-slug", title="Dup", slides=[s])

    with pytest.raises(ValueError):
        call_with_supported_kwargs(publish_fn, [make_deck(), make_deck()], tmp_path / "dup_out")


@pytest.mark.ledger
def test_publish_ledger_leaves_zero_tmp_files(tmp_path: Path) -> None:
    """Atomic publish_ledger leaves zero *.tmp or *.part files in output directory."""
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/F6")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    s = call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Clean"]))
    deck = call_with_supported_kwargs(deck_cls, slug="atomic-demo", title="Atomic", slides=[s])
    out_root = tmp_path / "atomic_pres"
    call_with_supported_kwargs(publish_fn, [deck], out_root)
    leftovers = list(out_root.rglob("*.tmp")) + list(out_root.rglob("*.part"))
    assert not leftovers, f"Leftover temp files after atomic publish: {leftovers}"


@pytest.mark.ledger
def test_catalog_all_hashes_are_lowercase_64_hex() -> None:
    """Self-contained: every deck entry in catalog.json has valid 64-hex lowercase sha256 and bytes > 0."""
    catalog = _published_catalog()
    for deck in catalog["decks"]:
        digest = deck.get("sha256", "")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), f"Bad sha256 on {deck['slug']}"
        assert int(deck.get("bytes", 0)) > 0, f"Non-positive byte count on {deck['slug']}"


@pytest.mark.ledger
def test_catalog_required_fields_validated() -> None:
    """Self-contained: catalog.json has non-empty contract, attribution, deck_count, total_slides, and decks."""
    catalog = _published_catalog()
    for key in ("contract", "attribution", "deck_count", "total_slides", "constitutional", "decks"):
        assert key in catalog and catalog[key] is not None
    assert catalog["deck_count"] == len(catalog["decks"])
    assert catalog["total_slides"] == sum(d["slides"] for d in catalog["decks"])


@pytest.mark.ledger
def test_sha256sums_paths_are_relative_without_traversal() -> None:
    """Self-contained: SHA256SUMS.presentations uses safe relative paths without .. or leading /."""
    sums = REPO_ROOT / "research" / "presentations" / "SHA256SUMS.presentations"
    for digest, rel_path in parse_sha256sums(sums):
        assert len(digest) == 64
        assert not rel_path.startswith("/") and ".." not in Path(rel_path).parts


# ===========================================================================
# Area F7: Navigation & Link Boundaries (6 tests)
# ===========================================================================


@pytest.mark.navigation
def test_markdown_link_extractor_handles_anchors_queries_and_titles(tmp_path: Path) -> None:
    """Self-contained: link scanner handles #anchor, ?query, title strings, and catches broken targets."""
    ok_target = tmp_path / "docs" / "guide.md"
    ok_target.parent.mkdir(parents=True)
    ok_target.write_text("# Guide\n", encoding="utf-8")
    md = tmp_path / "README.md"
    md.write_text(
        '[Good](docs/guide.md#sec?v=1 "Title")\n'
        "[External](https://example.org/skip)\n"
        "[Broken](docs/missing.md#top)\n"
        '<img src="missing.png" />\n',
        encoding="utf-8",
    )
    broken = scan_markdown_links([md], root=tmp_path)
    assert len(broken) == 2
    assert any("missing.md" in b for b in broken) and any("missing.png" in b for b in broken)


@pytest.mark.navigation
def test_zero_broken_gallery_images_across_research_presentations() -> None:
    """Every markdown image and HTML img tag in research/presentations/**/*.md resolves to a non-empty file."""
    mds = sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
    broken = scan_markdown_links(mds)
    assert not broken, f"Broken gallery links/images: {broken[:10]}"


@pytest.mark.navigation
def test_zero_file_scheme_links_in_markdown_and_html() -> None:
    """Published README, docs, and presentations contain zero local-filesystem URI leaks."""
    targets = (
        [REPO_ROOT / "README.md"]
        + sorted((REPO_ROOT / "docs").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.html"))
    )
    leaks = [str(p.relative_to(REPO_ROOT)) for p in targets if ("file" + ":///") in p.read_text(encoding="utf-8").lower()]
    assert not leaks, f"Found filesystem URI leaks in: {leaks}"


@pytest.mark.navigation
def test_directory_vs_file_links_resolve_cleanly() -> None:
    """Directory and file links in README.md and docs/MONOREPO.md resolve on disk."""
    broken = scan_markdown_links([REPO_ROOT / "README.md", REPO_ROOT / "docs" / "MONOREPO.md"])
    assert not broken, f"Broken top-level links: {broken}"


@pytest.mark.navigation
def test_presentation_team_test_files_are_grade_a_or_b() -> None:
    """Self-contained: every .py file in tests/e2e_presentation_team/ scores Grade A or B (0 parse errors)."""
    from guiai.gem.code_elegance_analyzer import analyze_python_source

    suite_dir = Path(__file__).resolve().parent
    for py_file in sorted(suite_dir.glob("*.py")):
        rep = analyze_python_source(py_file.read_text(encoding="utf-8"), py_file.name)
        assert rep["grade"] in ("A", "B"), f"{py_file.name} scored Grade {rep['grade']} (MI={rep['mi_score']})"


@pytest.mark.navigation
def test_assets_master_gem_interactive_html_is_zero_cdn_and_valid() -> None:
    """Self-contained: assets/master-gem-interactive.html contains zero external CDN scripts/styles."""
    html_path = REPO_ROOT / "assets" / "master-gem-interactive.html"
    assert html_path.is_file(), f"Missing {html_path}"
    html = html_path.read_text(encoding="utf-8")
    assert "<script src=\"http" not in html.lower() and "<link rel=\"stylesheet\" href=\"http" not in html.lower()


# ===========================================================================
# Area F8: Constitutional Hygiene Boundaries (6 tests)
# ===========================================================================


@pytest.mark.hygiene
def test_hygiene_scanner_allows_proj_hook_and_prose_file_scheme() -> None:
    """Self-contained BVA: state@proj.hook and prose scheme mentions do not false-positive; deep URIs trigger."""
    clean_sample = "Decorator typo state@proj.hook(addr) and SSRF prose (example.com, file://, ftp://)."
    assert find_hygiene_violations(clean_sample, strict_file_scheme=False) == []
    dirty_sample = "Bad link: " + "file" + ":///etc/passwd"
    assert find_hygiene_violations(dirty_sample, strict_file_scheme=False)


@pytest.mark.hygiene
def test_hygiene_scanner_catches_paths_serials_emails_and_api_keys() -> None:
    """Self-contained BVA: hygiene scanner catches personal paths, device serials, emails, and API tokens."""
    samples = [
        "/" + "home" + "/alice/notes.txt",
        "/" + "media" + "/bob/drive",
        "2A111" + "FDH00123",
        "exile" + "kingdom@" + "proton.me",
        "sk-" + "ant-secret123",
    ]
    for sample in samples:
        assert find_hygiene_violations(sample), f"Scanner missed violation: {sample}"


@pytest.mark.hygiene
def test_conflicting_constitutional_flag_rejected_by_validator() -> None:
    """Self-contained: assert_constitutional_flags rejects any invalid epistemic flag override."""
    valid = {
        "operational_metacognition_verified": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "external_actions": 0,
    }
    assert_constitutional_flags(valid)
    for bad_key, bad_val in (("sentience_claimed", True), ("cure_claim", True), ("l5_agi_qualified", True), ("external_actions", 1)):
        broken = {**valid, bad_key: bad_val}
        with pytest.raises(AssertionError):
            assert_constitutional_flags(broken)


@pytest.mark.hygiene
def test_no_hygiene_leaks_inside_gem_1001_metadata_records() -> None:
    """All Escape 5/99/1001 JSON metadata records inside Anthology .gem files are free of hygiene leaks."""
    from guiai.gem import vdi

    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        gallery_dir = (pres_root / deck["gallery"]).parent
        gem_files = sorted(gallery_dir.glob("*.gem")) + sorted((pres_root / "decks").glob(f"*{deck['slug']}*.gem"))
        assert gem_files, f"[R2/F8] Missing .gem files for {deck['slug']}"
        for gf in gem_files:
            parsed = vdi.parse_metafile(gf.read_bytes())
            for rec in parsed["records"]:
                if rec["command"] == 5 and rec["subcommand"] == 99 and rec["values"] and rec["values"][0] == 1001:
                    payload = bytes(v & 0xFF for v in rec["values"][1:]).decode("ascii", "ignore")
                    assert_hygiene_clean(payload, f"{gf.name} metadata")


@pytest.mark.hygiene
def test_no_hygiene_leaks_inside_catalog_json_nested_strings() -> None:
    """Self-contained: every string value nested inside research/presentations/catalog.json passes hygiene check."""
    catalog = _published_catalog()

    def walk_strings(node: Any, path: str) -> None:
        if isinstance(node, str):
            assert_hygiene_clean(node, path)
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk_strings(item, f"{path}[{idx}]")
        elif isinstance(node, dict):
            for k, v in node.items():
                walk_strings(v, f"{path}.{k}")

    walk_strings(catalog, "catalog.json")


@pytest.mark.hygiene
def test_no_office_tools_guard_blocks_soffice_and_pdftoppm(no_office_env: tuple[dict[str, str], Path]) -> None:
    """Self-contained: zero-Office runtime guard blocks shutil.which and subprocess calls to Office/PDF tools."""
    _, sentinel = no_office_env
    for tool in ("soffice", "libreoffice", "pdftoppm"):
        with pytest.raises(AssertionError):
            shutil.which(tool)
        with pytest.raises(AssertionError):
            subprocess.run([tool, "--version"], check=False)
    assert not sentinel.exists()

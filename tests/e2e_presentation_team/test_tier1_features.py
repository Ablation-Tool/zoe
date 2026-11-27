"""Tier 1 Feature Coverage (Category-Partition Happy Paths across Areas F1-F8)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

from .conftest import (
    REPO_ROOT,
    assert_constitutional_flags,
    assert_hygiene_clean,
    assert_offline_player_controls,
    call_with_supported_kwargs,
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

pytestmark = pytest.mark.tier1


def _new_canvas() -> Any:
    canvas_cls = require_contract("guiai.gem.presentation.draw_plus", "DrawPlusCanvas", req_id="R1/F3")
    return call_with_supported_kwargs(canvas_cls, width=13333, height=7500, title="Tier1 Slide")


def _compile_and_verify_canvas(doc: Any, tmp_path: Path, stem: str) -> tuple[Any, bytes, Path]:
    canvas = _new_canvas()
    doc.compile(canvas)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is True, f"Layout failed for {stem}: {report}"
    gem_bytes = canvas.to_gem_bytes()
    verify_gem_bytes(gem_bytes)
    png_path = tmp_path / f"{stem}.png"
    call_with_supported_kwargs(canvas.render_png, png_path, width=1280, height=720)
    verify_rendered_image(png_path)
    return canvas, gem_bytes, png_path


def _published_catalog() -> dict[str, Any]:
    cat_path = REPO_ROOT / "research" / "presentations" / "catalog.json"
    assert cat_path.is_file(), f"[R2/F6] Missing catalog.json at {cat_path}"
    return json.loads(cat_path.read_text(encoding="utf-8"))


def _vol_decks_from_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    decks = catalog.get("decks", [])
    vol_decks = [
        d for d in decks
        if str(d.get("slug", "")).startswith("vol-") or "volume" in str(d.get("category", "")).lower()
        or "vol." in str(d.get("title", "")).lower()
    ]
    assert len(vol_decks) >= 6, f"[R2/F5] Expected 6 published Anthology volumes (Vol. I-VI), found {len(vol_decks)}"
    return vol_decks


# ===========================================================================
# Area F1: WordChart (6 tests)
# ===========================================================================


@pytest.mark.wordchart
def test_wordchart_four_zone_model_compiles_to_canvas(tmp_path: Path) -> None:
    """WordChart 4-zone model (title, column_head, text_body, footer) compiles and renders."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title="Operational Metacognition",
        column_head=["Metric", "Observed Result"],
        text_body=["A_tau(p) threshold count", "AUROC 0.8382 on Qwen2.5-0.5B"],
        footer="Nicholas Michael Kloster (March 6, 2026) x Zoe | $0.00 offline",
        template="column_2",
    )
    canvas, _, _ = _compile_and_verify_canvas(doc, tmp_path, "wc_four_zone")
    svg_path = tmp_path / "wc_four_zone.svg"
    canvas.render_svg(svg_path)
    svg_text = svg_path.read_text(encoding="utf-8")
    verify_svg_document(svg_text)
    assert "Operational Metacognition" in svg_text


@pytest.mark.wordchart
@pytest.mark.parametrize(
    "template_name",
    ["column_1", "column_2", "column_3", "column_4", "outline_2", "outline_3", "outline_4"],
)
def test_wordchart_columnar_and_outline_templates(tmp_path: Path, template_name: str) -> None:
    """WordChart Columnar (1..4) and Outline (2..4) templates compile with zero overlap."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    cols = int(template_name.split("_")[-1])
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title=f"Template {template_name}",
        template=template_name,
        column_head=[f"Col {i + 1}" for i in range(cols)],
        columns=[[f"Item {i + 1}.1", f"Item {i + 1}.2"] for i in range(cols)],
        text_body=[f"Point {i + 1}" for i in range(cols)],
        footer="Zoe Presentation Team",
    )
    _compile_and_verify_canvas(doc, tmp_path, f"wc_{template_name}")


@pytest.mark.wordchart
@pytest.mark.parametrize("template_name", ["hero_obsidian", "scorecard_2x2", "pillar_3col", "freeform"])
def test_wordchart_botanical_hero_scorecard_pillar_and_freeform(tmp_path: Path, template_name: str) -> None:
    """Botanical hero_obsidian, scorecard_2x2, pillar_3col, and freeform templates render cleanly."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title=f"Showcase {template_name}",
        template=template_name,
        text_body=["Symmetrical botanical layout", "Pure-Python GEM VDI", "Zero Office runtime"],
        footer="Honoring Gary & Dorothy McEwen Kildall",
    )
    _compile_and_verify_canvas(doc, tmp_path, f"wc_{template_name}")


@pytest.mark.wordchart
def test_wordchart_typography_styles_and_decimal_alignment(tmp_path: Path) -> None:
    """WordChart supports left/center/right/decimal alignment and bold/italic/underline styles."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title="Typography & Decimal Alignment",
        template="column_2",
        alignments=["left", "decimal"],
        text_styles={"bold": True, "italic": False, "underline": True},
        columns=[
            ["Qwen2.5 Error@50%", "AUROC M2 Root", "Causal Delta"],
            ["30.0", "0.8382", "+34.52"],
        ],
        text_body=["30.0", "0.8382", "+34.52"],
    )
    canvas, _, _ = _compile_and_verify_canvas(doc, tmp_path, "wc_decimal")
    svg_path = tmp_path / "wc_decimal.svg"
    canvas.render_svg(svg_path)
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "0.8382" in svg_text and "+34.52" in svg_text


@pytest.mark.wordchart
def test_wordchart_bullets_numbering_and_accent_boxes(tmp_path: Path) -> None:
    """WordChart supports bullet styles, numbering, and accent rule lines/boxes."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title="Bullets & Accent Boxes",
        template="outline_2",
        bullet_style="number",
        text_body=["First verifiable theorem", "Second causal ablation", "Third proof packet"],
        accent_boxes=True,
        divider_lines=True,
    )
    _compile_and_verify_canvas(doc, tmp_path, "wc_bullets")


@pytest.mark.wordchart
def test_wordchart_locator_rectangle_border_gem_fitting(tmp_path: Path) -> None:
    """WordChart fits text content inside a custom .GEM border via locator rectangle."""
    wordchart_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    from guiai.gem import model as gem_model, vdi

    border_scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "locator_border",
        "title": "Locator Border",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [
            {"id": "outer_frame", "type": "rectangle", "bounds": [200, 200, 13133, 7300], "fill": "none", "stroke": "#C29130", "width": 24},
            {"id": "locator_rect", "type": "rectangle", "role": "locator", "bounds": [900, 900, 12433, 6600], "fill": "none", "stroke": "#0E6B5E", "width": 8},
        ],
    })
    border_gem = tmp_path / "border.gem"
    vdi.write_metafile(border_scene, border_gem)
    doc = call_with_supported_kwargs(
        wordchart_cls,
        title="Locator Fitted Slide",
        template="column_1",
        text_body=["Content fitted strictly within GEM locator rectangle"],
        border_gem_path=border_gem,
    )
    _compile_and_verify_canvas(doc, tmp_path, "wc_locator")


# ===========================================================================
# Area F2: Graph (6 tests)
# ===========================================================================


@pytest.mark.graph
@pytest.mark.parametrize("chart_type", ["pie", "bar", "stacked_bar", "stacked_100_bar", "deviation_bar", "bar_3d"])
def test_graph_pie_and_bar_subtypes_compile_and_render(tmp_path: Path, chart_type: str) -> None:
    """Graph supports pie and bar subtypes (clustered, stacked, 100%, deviation, 3D)."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    values = [34.5, -12.0, 22.5] if chart_type == "deviation_bar" else [42.0, 28.0, 30.0]
    doc = call_with_supported_kwargs(
        graph_cls,
        title=f"Chart {chart_type}",
        chart_type=chart_type,
        categories=["Pillar A", "Pillar B", "Pillar C"],
        series=[{"name": "Score", "values": values}],
    )
    _compile_and_verify_canvas(doc, tmp_path, f"gr_{chart_type}")


@pytest.mark.graph
@pytest.mark.parametrize("chart_type", ["line", "area", "bar_line", "step", "stick", "scatter", "symbol", "map"])
def test_graph_line_area_combo_step_stick_scatter_symbol_map(tmp_path: Path, chart_type: str) -> None:
    """Graph supports line, area, bar+line combo, step, stick, scatter, symbol, and map families."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    doc = call_with_supported_kwargs(
        graph_cls,
        title=f"Family {chart_type}",
        chart_type=chart_type,
        categories=["T1", "T2", "T3", "T4"],
        series=[
            {"name": "Kloster A", "values": [0.55, 0.72, 0.84, 0.93]},
            {"name": "Baseline", "values": [0.40, 0.45, 0.49, 0.51]},
        ],
        x_values=[1.0, 2.0, 3.0, 4.0],
    )
    _compile_and_verify_canvas(doc, tmp_path, f"gr_{chart_type}")


@pytest.mark.graph
def test_graph_csv_adapter_loads_evidence_series(tmp_path: Path) -> None:
    """Graph CSV adapter ingests tabular evidence metrics into rendered chart."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    csv_path = tmp_path / "shootout.csv"
    csv_path.write_text("Method,AUROC,Error50\nKloster_M2,0.8382,30.0\nMSP,0.8360,34.0\nEntropy,0.8145,38.0\n", encoding="utf-8")
    doc = graph_cls.from_csv(csv_path, title="CSV Shootout", chart_type="bar")
    canvas, _, _ = _compile_and_verify_canvas(doc, tmp_path, "gr_csv")
    svg_path = tmp_path / "gr_csv.svg"
    canvas.render_svg(svg_path)
    assert "Kloster_M2" in svg_path.read_text(encoding="utf-8")


@pytest.mark.graph
def test_graph_dif_and_prn_adapters_ingest_tabular_data(tmp_path: Path) -> None:
    """Graph DIF and PRN adapters parse Digital Research interchange formats."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    dif_path = tmp_path / "metrics.dif"
    dif_path.write_text(
        'TABLE\n0,1\n"Zoe"\nVECTORS\n0,2\n""\nTUPLES\n0,2\n""\nDATA\n0,0\n""\n'
        '-1,0\nBOT\n1,0\n"Gate"\n1,0\n"Score"\n'
        '-1,0\nBOT\n1,0\n"Alpha"\n0,91\nV\n'
        '-1,0\nBOT\n1,0\n"Beta"\n0,97\nV\n-1,0\nEOD\n',
        encoding="utf-8",
    )
    prn_path = tmp_path / "metrics.prn"
    prn_path.write_text("Gate   Score\nAlpha  91\nBeta   97\n", encoding="utf-8")
    doc_dif = graph_cls.from_dif(dif_path, title="DIF Graph", chart_type="bar")
    doc_prn = graph_cls.from_prn(prn_path, title="PRN Graph", chart_type="line")
    _compile_and_verify_canvas(doc_dif, tmp_path, "gr_dif")
    _compile_and_verify_canvas(doc_prn, tmp_path, "gr_prn")


@pytest.mark.graph
def test_graph_json_evidence_adapter_binds_kloster_metrics(tmp_path: Path) -> None:
    """Graph JSON adapter binds real repository evidence JSON into a valid chart."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    json_path = REPO_ROOT / "evidence" / "live-llm-hallucination" / "qwen25-hallucination-shootout.json"
    assert json_path.is_file(), f"Missing evidence fixture: {json_path}"
    doc = call_with_supported_kwargs(graph_cls.from_json, json_path, title="Qwen2.5-0.5B Shootout", chart_type="bar")
    _compile_and_verify_canvas(doc, tmp_path, "gr_json")


@pytest.mark.graph
def test_graph_axes_grid_and_legend_auto_layout_no_collision(tmp_path: Path) -> None:
    """Multi-series graph with legend, axes titles, and gridlines passes verify_layout()."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    doc = call_with_supported_kwargs(
        graph_cls,
        title="Multi-Series Calibration",
        chart_type="bar_line",
        categories=["Vol I", "Vol II", "Vol III", "Vol IV", "Vol V", "Vol VI"],
        series=[
            {"name": "Verification Score", "values": [95, 92, 98, 96, 100, 97]},
            {"name": "Target Threshold", "values": [85, 85, 85, 85, 85, 85]},
        ],
        show_legend=True,
        show_grid=True,
        x_label="Anthology Volume",
        y_label="Percent",
    )
    _compile_and_verify_canvas(doc, tmp_path, "gr_legend")


# ===========================================================================
# Area F3: Draw Plus & .GEM VDI (6 tests)
# ===========================================================================


@pytest.mark.draw_plus
def test_vdi_spec_exact_opcodes_13_14_gdp_and_escape(tmp_path: Path) -> None:
    """Generated .GEM emits 14=vs_color, 13=vst_rotation, 11/1..9 GDPs, and 5/99 escapes."""
    canvas = _new_canvas()
    canvas.add_rect(500, 500, 3000, 2000, fill="#B81D48", stroke="#0B1220", rounded=True)
    canvas.add_ellipse(5000, 1500, 700, 500, fill="#0E6B5E", stroke="#C29130")
    canvas.add_arc(8000, 1500, 600, 0, 1800, stroke="#0B1220")
    canvas.add_pieslice(10500, 1500, 600, 0, 1200, fill="#C29130", stroke="#0B1220")
    canvas.add_text(1500, 4000, "Rotated Label", color="#0B1220", size=240, rotation=900)
    gem_bytes = canvas.to_gem_bytes()
    info = verify_gem_bytes(gem_bytes)
    opcodes = set(info["seasip"]["vdi_opcodes"])
    inv = info["inventory"]
    assert "vs_color_legacy" not in inv, f"[R1/F3] Legacy 4-int opcode 13 found: {inv}"
    assert "vs_color" in inv and 14 in opcodes, f"[R1/F3] Expected spec-exact vs_color opcode 14 in {inv}"
    assert "vst_rotation" in inv and 13 in opcodes, f"[R1/F3] Expected vst_rotation opcode 13 for rotated text in {inv}"
    assert 11 in opcodes, f"[R1/F3] Expected GDP opcode 11 in {opcodes}"
    assert 5 in opcodes, f"[R1/F3] Expected Escape opcode 5 in {opcodes}"


@pytest.mark.draw_plus
def test_draw_plus_eight_primitives_and_grouping_z_order(tmp_path: Path) -> None:
    """DrawPlusCanvas supports 8 primitives, grouping, ungrouping, and z-order."""
    canvas = _new_canvas()
    r1 = canvas.add_rect(400, 400, 2200, 1600, fill="#0B1220", stroke="#C29130")
    r2 = canvas.add_rect(1200, 900, 3200, 2200, fill="#B81D48", stroke="#FAF8F4")
    c1 = canvas.add_circle(4500, 1300, 500, fill="#0E6B5E", stroke="#0B1220")
    l1 = canvas.add_line(400, 2600, 5000, 2600, stroke="#0B1220")
    p1 = canvas.add_polygon([(6000, 600), (7000, 1800), (5400, 1800)], fill="#C29130", stroke="#0B1220")
    canvas.add_polyline([(6000, 2400), (6500, 2900), (7200, 2400)], stroke="#0E6B5E")
    canvas.add_arc(8400, 1300, 500, 0, 1800, stroke="#B81D48")
    canvas.add_text(1000, 3600, "Draw Plus 8 Primitives", color="#0B1220", size=260)
    gid = canvas.group([r1, r2], name="cards")
    canvas.put_in_front(r1)
    canvas.put_in_back(c1)
    canvas.break_group(gid)
    assert l1 is not None and p1 is not None
    verify_gem_bytes(canvas.to_gem_bytes())
    png_path = tmp_path / "dp_primitives.png"
    call_with_supported_kwargs(canvas.render_png, png_path, width=1280, height=720)
    verify_rendered_image(png_path)


@pytest.mark.draw_plus
def test_draw_plus_transforms_keep_text_upright(tmp_path: Path) -> None:
    """rotate_90, flip_h, and flip_v transform geometry while keeping text upright."""
    canvas = _new_canvas()
    box = canvas.add_rect(2000, 2000, 4500, 3500, fill="#FAF8F4", stroke="#0E6B5E")
    lbl = canvas.add_text(2400, 2900, "Upright Text", color="#0B1220", size=220)
    gid = canvas.group([box, lbl], name="card")
    canvas.rotate_90(gid)
    canvas.flip_h(gid)
    canvas.flip_v(gid)
    svg_path = tmp_path / "dp_transform.svg"
    canvas.render_svg(svg_path)
    svg_text = svg_path.read_text(encoding="utf-8")
    verify_svg_document(svg_text)
    assert "Upright Text" in svg_text
    assert not re.search(r"scale\(\s*-1\s*,", svg_text)
    assert not re.search(r"scale\(\s*1\s*,\s*-1\s*\)", svg_text)


@pytest.mark.draw_plus
def test_draw_plus_nine_way_align_even_spacing_and_autogrid() -> None:
    """9-way alignment, even spacing, and AutoGrid snap align objects deterministically."""
    canvas = _new_canvas()
    ids = [
        canvas.add_rect(500 + i * 2300, 1200 + i * 110, 1800 + i * 2300, 2200 + i * 110, fill="#FAF8F4", stroke="#0B1220")
        for i in range(4)
    ]
    canvas.align(ids, mode="top")
    canvas.even_spacing(ids, axis="x")
    canvas.autogrid_snap(ids, step=100)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is True


@pytest.mark.draw_plus
def test_botanical_floral_toolkit_palettes_and_mandala(tmp_path: Path) -> None:
    """Symmetrical botanical palette (#0B1220..#C29130), lotus dividers, filigree, and 9-petal mandala render."""
    palette_mod = require_contract("guiai.gem.presentation.palette", req_id="R1/F3")
    colors_dump = json.dumps(getattr(palette_mod, "BOTANICAL_PALETTE", vars(palette_mod)), default=str).upper()
    for hex_code in ("#0B1220", "#FAF8F4", "#B81D48", "#0E6B5E", "#C29130"):
        assert hex_code in colors_dump, f"[R1/F3] Missing botanical palette hex {hex_code}"
    canvas = _new_canvas()
    canvas.add_botanical_frame()
    canvas.add_lotus_divider(y=2100)
    canvas.add_hero_mandala(cx=6666, cy=4500, radius=1400, petals=9)
    report = canvas.verify_layout()
    assert pick(report, "ok", "passed") is True
    verify_gem_bytes(canvas.to_gem_bytes())
    png_path = tmp_path / "botanical.png"
    call_with_supported_kwargs(canvas.render_png, png_path, width=1280, height=720)
    verify_rendered_image(png_path)


@pytest.mark.draw_plus
def test_pure_python_cairo_pillow_svg_render_without_office(tmp_path: Path, no_office_env: tuple[dict[str, str], Path]) -> None:
    """Render .gem, .png (1920x1080), .jpg, and .svg purely in Python with zero Office calls."""
    _, sentinel = no_office_env
    canvas = _new_canvas()
    canvas.add_rect(400, 400, 12933, 7100, fill="#0B1220", stroke="#C29130")
    canvas.add_text(1200, 1500, "Zero Office Render", color="#FAF8F4", size=380)
    gem_path = tmp_path / "slide.gem"
    png_path = tmp_path / "slide.png"
    jpg_path = tmp_path / "slide.jpg"
    svg_path = tmp_path / "slide.svg"
    gem_path.write_bytes(canvas.to_gem_bytes())
    call_with_supported_kwargs(canvas.render_png, png_path, width=1920, height=1080)
    call_with_supported_kwargs(canvas.render_jpg, jpg_path, width=1920, height=1080)
    canvas.render_svg(svg_path)
    verify_gem_bytes(gem_path.read_bytes())
    assert verify_rendered_image(png_path) == (1920, 1080)
    assert verify_rendered_image(jpg_path) == (1920, 1080)
    verify_svg_document(svg_path.read_text(encoding="utf-8"))
    assert not sentinel.exists()


# ===========================================================================
# Area F4: Slide Show Player & CLI (6 tests)
# ===========================================================================


@pytest.mark.slideshow
def test_lis_playlist_roundtrip_and_ordering(tmp_path: Path) -> None:
    """GEM OUTPUT.APP .LIS playlist preserves slide ordering and timing metadata."""
    ss_mod = require_contract("guiai.gem.presentation.slideshow", req_id="R1/F4")
    slides = [tmp_path / "slide-01.gem", tmp_path / "slide-02.gem", tmp_path / "slide-03.gem"]
    for s in slides:
        s.write_bytes(b"")
    lis_path = tmp_path / "deck.lis"
    write_fn = pick(ss_mod, "write_lis_playlist", "dump_lis_playlist")
    parse_fn = pick(ss_mod, "parse_lis_playlist", "load_lis_playlist")
    write_fn(lis_path, slides, interval_seconds=5, cycle=True)
    parsed = parse_fn(lis_path)
    items = pick(parsed, "slides", "entries", "items", default=parsed)
    parsed_names = [Path(pick(item, "path", "file", "slide", default=item)).name for item in items]
    assert parsed_names == ["slide-01.gem", "slide-02.gem", "slide-03.gem"]
    lis_text = lis_path.read_text(encoding="utf-8")
    _check_lis_timing_and_cycle(parsed, items[0], lis_text)


def _check_lis_timing_and_cycle(parsed: Any, first_item: Any, lis_text: str) -> None:
    sentinel = object()
    interval = pick(parsed, "interval_seconds", "interval", "wait_seconds", default=sentinel)
    if interval is sentinel and not isinstance(first_item, (str, Path)):
        interval = pick(first_item, "interval_seconds", "interval", "wait_seconds", default=sentinel)
    if interval not in (sentinel, None):
        assert float(interval) == 5.0, f"Expected interval_seconds == 5, got {interval!r}"
    else:
        wait_mode = pick(parsed, "wait_mode", default=None) or (
            pick(first_item, "wait_mode", default=None) if not isinstance(first_item, (str, Path)) else None
        )
        assert (wait_mode is not None and "5" in str(wait_mode)) or re.search(
            r"(?:interval|wait|delay|time)\D*5\b|\b5s\b", lis_text, re.IGNORECASE
        ), f"Expected interval_seconds=5 / wait_mode preserved in .LIS: {lis_text!r}"

    cycle_val = pick(parsed, "cycle", "loop", default=sentinel)
    if cycle_val is sentinel and not isinstance(first_item, (str, Path)):
        cycle_val = pick(first_item, "cycle", "loop", default=sentinel)
    if cycle_val not in (sentinel, None):
        assert cycle_val is True, f"Expected cycle is True, got {cycle_val!r}"
    else:
        non_comment = "\n".join(
            ln for ln in lis_text.splitlines() if not ln.lstrip().startswith("#")
        )
        assert re.search(r"(?:cycle|loop)\s*=\s*(?:yes|true|1|on)\b", non_comment, re.IGNORECASE), (
            f"Expected cycle=True preserved in .LIS: {lis_text!r}"
        )


@pytest.mark.slideshow
def test_offline_player_html_zero_cdn_and_controls(tmp_path: Path) -> None:
    """Offline player.html contains zero CDN URLs and implements GEM Output keyboard/timer/notes controls."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    slides = [
        call_with_supported_kwargs(
            slide_cls,
            title=f"Slide {i}",
            content=call_with_supported_kwargs(wc_cls, title=f"Slide {i}", text_body=[f"Body {i}"]),
            speaker_notes=f"Speaker notes for slide {i}.",
        )
        for i in (1, 2)
    ]
    deck = call_with_supported_kwargs(
        deck_cls,
        slug="test-deck",
        title="Test Offline Player",
        subtitle="Zero CDN",
        volume_label="Test Vol",
        sister_id="zoe",
        slides=slides,
        constitutional={
            "operational_metacognition_verified": True,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "zoe_clone_claimed": False,
            "clinical_action_authorized": False,
            "cure_claim": False,
            "external_actions": 0,
        },
    )
    out_dir = tmp_path / "deck_out"
    call_with_supported_kwargs(deck.build, out_dir)
    player_html = (out_dir / "player.html").read_text(encoding="utf-8")
    assert_offline_player_controls(player_html)


@pytest.mark.slideshow
def test_zoe_present_build_and_render_cli_subcommands(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """`zoe present build` and `zoe present render` exit 0 and emit .gem, PNG, and player.html."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    spec_path = tmp_path / "spec.json"
    out_dir = tmp_path / "built_deck"
    spec_path.write_text(
        json.dumps({
            "slug": "cli-demo",
            "title": "CLI Demo Deck",
            "slides": [{"title": "Intro", "template": "hero_obsidian", "text_body": ["Pure-Python GEM VDI"]}],
        }),
        encoding="utf-8",
    )
    res_build = run_zoe_cli(["present", "build", str(spec_path), "--output", str(out_dir)], env=isolated_pres_env)
    assert res_build.returncode == 0, f"zoe present build failed: {res_build.stderr}"
    assert list(out_dir.rglob("*.gem")), "Expected .gem output from zoe present build"
    assert (out_dir / "player.html").is_file(), "Expected player.html from zoe present build"
    res_render = run_zoe_cli(["present", "render", str(out_dir)], env=isolated_pres_env)
    assert res_render.returncode == 0, f"zoe present render failed: {res_render.stderr}"
    assert list(out_dir.rglob("*.png")) or list(out_dir.rglob("*.jpg"))


@pytest.mark.slideshow
def test_zoe_present_inspect_and_play_cli_subcommands(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """`zoe present inspect` and `zoe present play` work cleanly without launching Office."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    spec_path = tmp_path / "spec.json"
    out_dir = tmp_path / "deck"
    spec_path.write_text(json.dumps({"slug": "inspect-demo", "title": "Inspect", "slides": [{"title": "S1", "text_body": ["OK"]}]}), encoding="utf-8")
    assert run_zoe_cli(["present", "build", str(spec_path), "--output", str(out_dir)], env=isolated_pres_env).returncode == 0
    gem_file = next(out_dir.rglob("*.gem"))
    res_inspect = run_zoe_cli(["present", "inspect", str(gem_file), "--json"], env=isolated_pres_env)
    assert res_inspect.returncode == 0, f"zoe present inspect failed: {res_inspect.stderr}"
    res_play = run_zoe_cli(["present", "play", str(out_dir), "--no-open"], env=isolated_pres_env)
    assert res_play.returncode == 0, f"zoe present play failed: {res_play.stderr}"


@pytest.mark.slideshow
def test_optional_pptx_export_never_required_for_core_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Core SlideDeck pipeline builds .gem, PNG, and player.html even when pptx is unavailable."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    monkeypatch.setitem(__import__("sys").modules, "pptx", None)
    deck = call_with_supported_kwargs(
        deck_cls,
        slug="no-pptx",
        title="Zero PPTX Runtime",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Native GEM"]))],
    )
    out_dir = tmp_path / "no_pptx_out"
    call_with_supported_kwargs(deck.build, out_dir)
    assert list(out_dir.rglob("*.gem")) and (out_dir / "player.html").is_file()


@pytest.mark.slideshow
def test_slide_deck_embeds_1001_metadata_and_constitutional_flags(tmp_path: Path) -> None:
    """Generated .gem file embeds Escape 5/99/1001 JSON metadata with slide notes and constitutional flags."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    from guiai.gem import vdi

    deck = call_with_supported_kwargs(
        deck_cls,
        slug="meta-check",
        title="Meta Check",
        sister_id="flora",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Verified"]), speaker_notes="Notes 1")],
    )
    out_dir = tmp_path / "meta_out"
    call_with_supported_kwargs(deck.build, out_dir)
    gem_file = next(out_dir.rglob("*.gem"))
    parsed = vdi.parse_metafile(gem_file.read_bytes())
    meta_records = [r for r in parsed["records"] if r["command"] == 5 and r["subcommand"] == 99 and r["values"] and r["values"][0] == 1001]
    assert meta_records, "Expected Escape 5/99/1001 metadata records in slide .gem"
    meta_dicts = [
        json.loads(bytes(v & 0xFF for v in r["values"][1:]).split(b"\0", 1)[0].decode("ascii"))
        for r in meta_records
    ]
    joined = json.dumps(meta_dicts)
    assert "Notes 1" in joined or "flora" in joined.lower()
    merged_const: dict[str, Any] = {}
    for md in meta_dicts:
        if isinstance(md.get("constitutional"), dict):
            merged_const.update(md["constitutional"])
        for flag_key in (
            "operational_metacognition_verified",
            "sentience_claimed",
            "l5_agi_qualified",
            "zoe_clone_claimed",
            "clinical_action_authorized",
            "cure_claim",
            "external_actions",
            "cloud_cost_usd",
        ):
            if flag_key in md:
                merged_const[flag_key] = md[flag_key]
    assert_constitutional_flags(merged_const, "gem 1001 metadata")


# ===========================================================================
# Area F5: Anthology Volumes I-VI (6 tests)
# ===========================================================================


@pytest.mark.anthology
def test_anthology_all_six_volumes_published_in_research_presentations() -> None:
    """All 6 Anthology Volumes (Vol. I-VI) exist in research/presentations/ with .gem, slides, player, and README."""
    catalog = _published_catalog()
    vol_decks = ordered_anthology_volumes(_vol_decks_from_catalog(catalog))
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in vol_decks:
        gallery_md = pres_root / deck["gallery"]
        assert gallery_md.is_file(), f"[R2/F5] Missing gallery README: {gallery_md}"
        gallery_dir = gallery_md.parent
        assert (gallery_dir / "player.html").is_file() or "player" in deck, f"[R2/F5] Missing player.html for {deck['slug']}"
        assert list(gallery_dir.glob("slide-*.png")) or list(gallery_dir.glob("slide-*.jpg")), f"[R2/F5] Missing rendered slides in {gallery_dir}"
        has_gem = bool(deck.get("gem") or deck.get("gems")) or list((pres_root / "decks").glob(f"*{deck['slug']}*.gem")) or list(gallery_dir.glob("*.gem"))
        assert has_gem, f"[R2/F5] Missing native .gem metafile for {deck['slug']}"


def _read_volume_text(vol_index: int) -> str:
    catalog = _published_catalog()
    vol_decks = _vol_decks_from_catalog(catalog)
    pres_root = REPO_ROOT / "research" / "presentations"
    target = select_anthology_volume(vol_decks, vol_index)
    readme_text = (pres_root / target["gallery"]).read_text(encoding="utf-8")
    return f"{json.dumps(target)}\n{readme_text}"


@pytest.mark.anthology
def test_anthology_vol1_kloster_theorems_and_shootout_metrics() -> None:
    """Vol. I contains verified Kloster A_tau(p), 16 theorems, 56.7%->30.0%, AUROC 0.8382, and +34.52/-45.07."""
    txt = _read_volume_text(1)
    for token in ("A_tau", "0.8382", "30.0", "34.52", "45.07", "Candy Land"):
        assert token in txt, f"[R2.1/F5] Vol. I missing grounded token {token!r}"


@pytest.mark.anthology
def test_anthology_vol2_dorothy_brain_neuro_oncology_metrics() -> None:
    """Vol. II contains grounded Dorothy 3D brain, MNI152, 36 PubChem, ML-KEM, 135-book, cure_claim=False."""
    txt = _read_volume_text(2)
    for token in ("MNI152", "36", "ML-KEM", "135"):
        assert token in txt, f"[R2.2/F5] Vol. II missing grounded token {token!r}"
    assert "240,376" in txt or "240k" in txt.lower()


@pytest.mark.anthology
def test_anthology_vol3_reverse_engineering_and_zero_trust_metrics() -> None:
    """Vol. III covers Ablation AIARE, RXVM, BEAM, PALA, CNSA 2.0, and 4 AI-Agent Binary Auditors."""
    txt = _read_volume_text(3)
    for token in ("AIARE", "RXVM", "BEAM", "PALA", "CNSA 2.0"):
        assert token in txt, f"[R2.3/F5] Vol. III missing grounded token {token!r}"


@pytest.mark.anthology
def test_anthology_vol4_uefi_gem_os_pixel7_and_uma_metrics() -> None:
    """Vol. IV covers 46 MB UEFI ISO, 188 KB /dev/fb0, OVMF+KVM, 50/50 UMA, Pixel 7 158 ms, 2.5 W Headlamp."""
    txt = _read_volume_text(4)
    for token in ("UEFI", "188", "OVMF", "UMA", "158"):
        assert token in txt, f"[R2.4/F5] Vol. IV missing grounded token {token!r}"


@pytest.mark.anthology
def test_anthology_vol5_and_vol6_hex_eddbms_constitution_clara_voice_cern_agi() -> None:
    """Vol. V & VI cover 16 shared walls, 28 sub-ops, 94+171 tests, PKCS #7, C_K=0.978351, 44 phonemes, CERN."""
    txt5 = _read_volume_text(5)
    for token in ("16", "28", "Balma", "94", "171"):
        assert token in txt5, f"[R2.5/F5] Vol. V missing grounded token {token!r}"
    txt6 = _read_volume_text(6)
    for token in ("PKCS", "0.978351", "44", "CERN", "Groove"):
        assert token in txt6, f"[R2.6/F5] Vol. VI missing grounded token {token!r}"


# ===========================================================================
# Area F6: Ledger & Checksums (6 tests)
# ===========================================================================


@pytest.mark.ledger
def test_catalog_json_schema_and_vol1_to_6_entries() -> None:
    """catalog.json conforms to zoe-research-presentations-ledger/v1 with Vol. I-VI and .gem/player fields."""
    catalog = _published_catalog()
    assert catalog.get("contract") == "zoe-research-presentations-ledger/v1"
    decks = catalog["decks"]
    assert catalog["deck_count"] == len(decks)
    assert catalog["total_slides"] == sum(d["slides"] for d in decks)
    vol_decks = ordered_anthology_volumes(_vol_decks_from_catalog(catalog))
    for deck in vol_decks:
        assert deck.get("gem") or deck.get("gems"), f"[R2/F6] Vol deck {deck['slug']} missing .gem field in catalog.json"
        assert "player" in deck, f"[R2/F6] Vol deck {deck['slug']} missing player field in catalog.json"


@pytest.mark.ledger
def test_sha256sums_presentations_all_digests_verify_offline() -> None:
    """Every entry in SHA256SUMS.presentations matches disk SHA-256 and includes Vol. I-VI artifacts."""
    pres_root = REPO_ROOT / "research" / "presentations"
    entries = parse_sha256sums(pres_root / "SHA256SUMS.presentations")
    assert len(entries) >= 17, f"[R2/F6] Expected >= 17 sealed artifacts (11 existing + 6 volumes), got {len(entries)}"
    for expected_hex, rel_path in entries:
        target = pres_root / rel_path
        assert target.is_file(), f"[R2/F6] Missing sealed artifact: {rel_path}"
        assert sha256_file(target) == expected_hex, f"[R2/F6] SHA-256 mismatch for {rel_path}"


@pytest.mark.ledger
def test_presentations_readme_lists_all_volumes_and_checksum_instructions() -> None:
    """research/presentations/README.md lists Vol. I-VI, catalog.json, and offline sha256sum instructions."""
    readme_text = (REPO_ROOT / "research" / "presentations" / "README.md").read_text(encoding="utf-8")
    for token in ("catalog.json", "SHA256SUMS.presentations", "sha256sum -c", "Vol. I", "Vol. VI"):
        assert token in readme_text, f"[R2/F6] presentations/README.md missing {token!r}"


@pytest.mark.ledger
def test_gallery_readme_slide_counts_match_disk_images() -> None:
    """Catalog slide counts match rendered slide images on disk across all published galleries."""
    catalog = _published_catalog()
    pres_root = REPO_ROOT / "research" / "presentations"
    for deck in catalog["decks"]:
        gallery_dir = (pres_root / deck["gallery"]).parent
        images = [p for p in gallery_dir.iterdir() if p.is_file() and p.name.startswith("slide-") and p.suffix.lower() in (".png", ".jpg")]
        assert len(images) == deck["slides"], f"{deck['slug']}: expected {deck['slides']} slides, found {len(images)}"


@pytest.mark.ledger
def test_publish_ledger_writes_complete_ledger_in_tmp_path(tmp_path: Path) -> None:
    """publish_ledger emits .gem, PNGs, player.html, gallery README, catalog.json, and SHA256SUMS in tmp_path."""
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/F6")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")

    deck = call_with_supported_kwargs(
        deck_cls,
        slug="vol-1-demo",
        title="Vol. I Demo",
        volume_label="Vol. I",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Demo"]), speaker_notes="Note 1")],
    )
    out_root = tmp_path / "pres"
    call_with_supported_kwargs(publish_fn, [deck], out_root)
    assert (out_root / "catalog.json").is_file()
    assert (out_root / "SHA256SUMS.presentations").is_file()
    assert (out_root / "README.md").is_file()
    assert (out_root / "galleries" / "vol-1-demo" / "README.md").is_file()
    for digest, rel_path in parse_sha256sums(out_root / "SHA256SUMS.presentations"):
        assert sha256_file(out_root / rel_path) == digest


@pytest.mark.ledger
def test_sha256sums_parser_and_existing_ledger_consistency() -> None:
    """Self-contained check: every current entry in SHA256SUMS.presentations verifies against disk."""
    pres_root = REPO_ROOT / "research" / "presentations"
    entries = parse_sha256sums(pres_root / "SHA256SUMS.presentations")
    assert entries, "SHA256SUMS.presentations must not be empty"
    for expected_hex, rel_path in entries:
        fp = pres_root / rel_path
        assert fp.is_file(), f"Missing file in SHA256SUMS.presentations: {rel_path}"
        assert sha256_file(fp) == expected_hex, f"Digest mismatch for {rel_path}"


# ===========================================================================
# Area F7: Navigation & Link Integrity (6 tests)
# ===========================================================================


@pytest.mark.navigation
def test_readme_links_to_monorepo_chronicle_and_presentations() -> None:
    """Top-level README.md links to MONOREPO, RESEARCH-CHRONICLE, CREATIVE-GALLERY, and presentations."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for target in ("docs/MONOREPO.md", "docs/RESEARCH-CHRONICLE.md", "docs/CREATIVE-GALLERY.md", "research/presentations/README.md"):
        assert target in readme, f"[R3/F7] README.md missing navigation link to {target}"


@pytest.mark.navigation
def test_docs_index_research_drafts_reconciled_plan_evidence_and_assets() -> None:
    """Navigation docs index research-drafts, RECONCILED_SHOWCASE_PLAN.md, evidence/, and assets/."""
    combined = "\n".join(
        (REPO_ROOT / p).read_text(encoding="utf-8")
        for p in ("README.md", "docs/MONOREPO.md", "docs/RESEARCH-CHRONICLE.md", "docs/CREATIVE-GALLERY.md")
    )
    for expected in ("research-drafts", "RECONCILED_SHOWCASE_PLAN.md", "evidence/", "assets/"):
        assert expected in combined, f"[R3/F7] Core navigation docs missing reference to {expected!r}"


@pytest.mark.navigation
def test_zero_broken_local_links_in_readme_docs_and_presentations() -> None:
    """All local markdown/HTML links across README.md, docs/**/*.md, and research/presentations/**/*.md resolve."""
    md_files = (
        [REPO_ROOT / "README.md"]
        + sorted((REPO_ROOT / "docs").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
    )
    broken = scan_markdown_links(md_files)
    assert not broken, f"[R3/F7] Broken local links found: {broken[:12]}"


@pytest.mark.navigation
def test_observatory_and_packages_verifier_passes_six_of_six() -> None:
    """Observatory & packages verification report reflects 6/6 PASS and valid evidence JSONs."""
    report_path = REPO_ROOT / "evidence" / "dorothy-brain-observatory" / "observatory-verification.json"
    assert report_path.is_file(), f"Missing observatory verification report: {report_path}"
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data.get("all_pass") is True and data.get("passed") == 6 and data.get("total") == 6
    assert data["documentation_and_evidence_audit"]["broken_links_count"] == 0


@pytest.mark.navigation
def test_unified_cli_and_presentation_modules_preserve_grade_a_or_b() -> None:
    """unified_cli.py stays Grade A (max_cc <= 20) and guiai/gem/presentation/*.py stay Grade A/B."""
    from guiai.gem.code_elegance_analyzer import analyze_python_source

    cli_path = REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "unified_cli.py"
    cli_rep = analyze_python_source(cli_path.read_text(encoding="utf-8"), "unified_cli.py")
    assert cli_rep["grade"] == "A" and cli_rep["max_cc"] <= 20, f"unified_cli.py degraded: {cli_rep}"
    pres_dir = REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "presentation"
    assert pres_dir.is_dir(), "[R1/F7] guiai/gem/presentation/ does not exist yet"
    for py_file in sorted(pres_dir.glob("*.py")):
        rep = analyze_python_source(py_file.read_text(encoding="utf-8"), py_file.name)
        assert rep["grade"] in ("A", "B"), f"{py_file.name} scored Grade {rep['grade']}"


@pytest.mark.navigation
def test_readme_attribution_and_metacognition_markers_intact() -> None:
    """README.md preserves core metacognition claim and attribution strings."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for token in ("Metacognition is achieved.", "Nicholas Michael Kloster", "Gary", "Dorothy McEwen Kildall"):
        assert token in readme, f"[R4/F7] README.md missing {token!r}"


# ===========================================================================
# Area F8: Constitutional Attribution & Hygiene (6 tests)
# ===========================================================================


@pytest.mark.hygiene
def test_published_docs_and_presentations_have_zero_hygiene_leaks() -> None:
    """Published README, docs, presentations, and provenance files contain zero personal paths/serials/emails."""
    targets = (
        [REPO_ROOT / "README.md", REPO_ROOT / "assets" / "branding" / "PROVENANCE.md"]
        + sorted((REPO_ROOT / "docs").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.json"))
    )
    failures: list[str] = []
    for path in targets:
        if not path.is_file():
            continue
        strict = path.name in ("README.md", "PROOF-PACKET.md") and path.parent in (REPO_ROOT, REPO_ROOT / "docs")
        try:
            assert_hygiene_clean(path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT)), strict_file_scheme=strict)
        except AssertionError as exc:
            failures.append(str(exc))
    assert not failures, "\n".join(failures[:10])


@pytest.mark.hygiene
def test_constitutional_attribution_present_across_presentations() -> None:
    """Attribution honors Nicholas Michael Kloster (March 6, 2026) x Zoe and Gary & Dorothy McEwen Kildall."""
    catalog = _published_catalog()
    assert "Nicholas Michael Kloster (March 6, 2026)" in catalog.get("attribution", "")
    readme = (REPO_ROOT / "research" / "presentations" / "README.md").read_text(encoding="utf-8")
    assert "Nicholas Michael Kloster" in readme and "Digital Research" in readme


@pytest.mark.hygiene
def test_epistemic_honesty_flags_enforced_in_catalog_and_decks() -> None:
    """catalog.json and published metadata preserve all epistemic honesty invariants."""
    catalog = _published_catalog()
    assert_constitutional_flags(catalog["constitutional"], "catalog.json[constitutional]")


@pytest.mark.hygiene
def test_generated_gem_and_player_embed_constitutional_invariants(tmp_path: Path) -> None:
    """Newly generated SlideDeck player.html embeds attribution and constitutional epistemic flags."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R4/F8")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    deck = call_with_supported_kwargs(
        deck_cls,
        slug="hygiene-deck",
        title="Hygiene Verified Deck",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Clean"]))],
    )
    out_dir = tmp_path / "hygiene_out"
    call_with_supported_kwargs(deck.build, out_dir)
    html = (out_dir / "player.html").read_text(encoding="utf-8")
    assert_hygiene_clean(html, "generated player.html")
    assert "Nicholas Michael Kloster" in html
    assert "sentience_claimed" in html.lower() or "non-sentient" in html.lower() or "operational" in html.lower()


@pytest.mark.hygiene
def test_ledger_hygiene_scrubber_strips_workstation_paths() -> None:
    """Ledger hygiene scrubber strips personal workstation paths and device serials."""
    ledger_mod = require_contract("guiai.gem.presentation.ledger", req_id="R4/F8")
    scrub_fn = pick(ledger_mod, "scrub_hygiene", "sanitize_hygiene", "scrub_text")
    dirty = "/" + "home" + "/alice/work " + "/" + "media" + "/alice/disk " + "2A111" + "FDH99999"
    cleaned = scrub_fn(dirty)
    assert_hygiene_clean(cleaned, "scrubbed output")


@pytest.mark.hygiene
def test_e2e_test_suite_itself_has_zero_hygiene_literals() -> None:
    """Every file in tests/e2e_presentation_team/ is free of personal paths, serials, and emails."""
    suite_dir = Path(__file__).resolve().parent
    for path in sorted(suite_dir.iterdir()):
        if path.is_file() and path.suffix in (".py", ".ini"):
            assert_hygiene_clean(path.read_text(encoding="utf-8"), path.name, strict_file_scheme=False)

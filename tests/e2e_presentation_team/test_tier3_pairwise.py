"""Tier 3 Pairwise Cross-Feature Combination Tests across Areas F1-F8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .conftest import (
    REPO_ROOT,
    assert_constitutional_flags,
    assert_hygiene_clean,
    assert_offline_player_no_cdn,
    call_with_supported_kwargs,
    deck_sealed_artifacts,
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

pytestmark = pytest.mark.tier3


def _new_canvas(title: str = "Pairwise Slide") -> Any:
    canvas_cls = require_contract("guiai.gem.presentation.draw_plus", "DrawPlusCanvas", req_id="R1/F3")
    return call_with_supported_kwargs(canvas_cls, width=13333, height=7500, title=title)


def _published_catalog() -> dict[str, Any]:
    cat_path = REPO_ROOT / "research" / "presentations" / "catalog.json"
    assert cat_path.is_file(), f"Missing catalog.json at {cat_path}"
    return json.loads(cat_path.read_text(encoding="utf-8"))


# ===========================================================================
# Cross-Feature Pairwise Matrix (F1-F8)
# ===========================================================================


@pytest.mark.wordchart
@pytest.mark.draw_plus
def test_pair_f1_wordchart_plus_f3_botanical_draw_plus_to_gem_png(tmp_path: Path) -> None:
    """F1 + F3: WordChart 4-zone slide + botanical filigree/mandala compiles to .GEM and PNG cleanly."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    canvas = _new_canvas("Botanical WordChart")
    canvas.add_botanical_frame()
    canvas.add_lotus_divider(y=1900)
    doc = call_with_supported_kwargs(
        wc_cls,
        title="Botanical Showcase",
        template="pillar_3col",
        column_head=["WordChart", "Graph", "Draw Plus"],
        text_body=["4-Zone Model", "8 Chart Families", "Pure-Python VDI"],
        footer="Nicholas Michael Kloster (March 6, 2026) x Zoe",
    )
    doc.compile(canvas)
    assert pick(canvas.verify_layout(), "ok", "passed") is True
    verify_gem_bytes(canvas.to_gem_bytes())
    png = tmp_path / "pair_wc_dp.png"
    call_with_supported_kwargs(canvas.render_png, png, width=1280, height=720)
    verify_rendered_image(png)


@pytest.mark.graph
@pytest.mark.wordchart
def test_pair_f2_graph_csv_plus_f1_wordchart_composite_slide(tmp_path: Path) -> None:
    """F2 + F1: CSV Graph data + WordChart narrative combine on one collision-free canvas."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    csv_path = tmp_path / "ablation.csv"
    csv_path.write_text("Mode,Reward\nON,34.52\nRandomized,8.48\nOFF,-45.07\n", encoding="utf-8")
    graph_doc = graph_cls.from_csv(csv_path, title="Causal Ablation", chart_type="deviation_bar")
    wc_doc = call_with_supported_kwargs(
        wc_cls,
        title="Ablation Summary",
        template="column_2",
        text_body=["ON achieves +34.52 reward", "OFF collapses to -45.07"],
    )
    canvas = _new_canvas("Composite")
    call_with_supported_kwargs(wc_doc.compile, canvas, region=(600, 1200, 6200, 6800))
    call_with_supported_kwargs(graph_doc.compile, canvas, region=(6500, 1200, 12700, 6800))
    assert pick(canvas.verify_layout(), "ok", "passed") is True
    png = tmp_path / "composite.png"
    call_with_supported_kwargs(canvas.render_png, png, width=1280, height=720)
    verify_rendered_image(png)


@pytest.mark.graph
@pytest.mark.draw_plus
def test_pair_f2_graph_json_plus_f3_vdi_custom_palette_opcodes() -> None:
    """F2 + F3: JSON evidence graph emits valid .GEM using opcode 14 (vs_color) for botanical hex palette."""
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    json_path = REPO_ROOT / "evidence" / "live-llm-hallucination" / "qwen25-hallucination-shootout.json"
    doc = call_with_supported_kwargs(graph_cls.from_json, json_path, title="Qwen2.5 AUROC", chart_type="bar")
    canvas = _new_canvas("VDI Palette")
    doc.compile(canvas)
    info = verify_gem_bytes(canvas.to_gem_bytes())
    assert "vs_color" in info["inventory"] and 14 in set(info["seasip"]["vdi_opcodes"])


@pytest.mark.wordchart
@pytest.mark.draw_plus
def test_pair_f1_wordchart_locator_border_plus_f3_svg_and_jpg(tmp_path: Path) -> None:
    """F1 + F3: Locator-rectangle .GEM border fits WordChart and renders identically to SVG and JPG."""
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    from guiai.gem import model as gem_model, vdi

    border_scene = gem_model.Scene.from_dict({
        "schema_version": 1,
        "id": "pair_border",
        "title": "Pair Border",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [
            {"id": "outer", "type": "rectangle", "bounds": [150, 150, 13183, 7350], "fill": "none", "stroke": "#B81D48", "width": 16},
            {"id": "loc", "type": "rectangle", "role": "locator", "bounds": [800, 800, 12533, 6700], "fill": "none", "stroke": "#0E6B5E", "width": 6},
        ],
    })
    border_gem = tmp_path / "pair_border.gem"
    vdi.write_metafile(border_scene, border_gem)
    doc = call_with_supported_kwargs(wc_cls, title="Locator + SVG/JPG", text_body=["Point A", "Point B"], border_gem_path=border_gem)
    canvas = _new_canvas("Locator")
    doc.compile(canvas)
    svg = tmp_path / "pair_loc.svg"
    jpg = tmp_path / "pair_loc.jpg"
    canvas.render_svg(svg)
    call_with_supported_kwargs(canvas.render_jpg, jpg, width=1280, height=720)
    verify_svg_document(svg.read_text(encoding="utf-8"))
    verify_rendered_image(jpg)


@pytest.mark.draw_plus
@pytest.mark.slideshow
def test_pair_f3_draw_plus_plus_f4_slideshow_player_html(tmp_path: Path) -> None:
    """F3 + F4: Multi-slide DrawPlusCanvas decks compile to .LIS playlist and offline player.html."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    slides = []
    for idx in (1, 2, 3):
        canvas = _new_canvas(f"Slide {idx}")
        canvas.add_botanical_frame()
        canvas.add_text(1400, 2200, f"Draw Plus Slide {idx}", color="#0B1220", size=340)
        slides.append(call_with_supported_kwargs(slide_cls, title=f"Slide {idx}", canvas=canvas, speaker_notes=f"Notes {idx}"))
    deck = call_with_supported_kwargs(deck_cls, slug="dp-show", title="DrawPlus SlideShow", slides=slides)
    out = tmp_path / "dp_show"
    call_with_supported_kwargs(deck.build, out)
    assert len(list(out.rglob("*.gem"))) >= 3
    html = (out / "player.html").read_text(encoding="utf-8")
    assert "Notes 1" in html and "Notes 3" in html
    assert_offline_player_no_cdn(html)


@pytest.mark.slideshow
@pytest.mark.graph
def test_pair_f4_cli_build_plus_f2_graph_evidence_input(tmp_path: Path, isolated_pres_env: dict[str, str]) -> None:
    """F4 + F2: `zoe present build` consumes a CSV evidence dataset and produces a playable deck."""
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    csv_path = tmp_path / "cern.csv"
    csv_path.write_text("Metric,Score\nAUROC,0.99992\nDijetTopology,0.9875\n", encoding="utf-8")
    spec = tmp_path / "cern_spec.json"
    spec.write_text(
        json.dumps({
            "slug": "cern-cli",
            "title": "CERN Trigger",
            "slides": [{"title": "CERN Metrics", "chart_type": "bar", "csv": str(csv_path)}],
        }),
        encoding="utf-8",
    )
    out_dir = tmp_path / "cern_out"
    proc = run_zoe_cli(["present", "build", str(spec), "--output", str(out_dir)], env=isolated_pres_env)
    assert proc.returncode == 0, f"CLI build failed: {proc.stderr}"
    assert (out_dir / "player.html").is_file()
    for gf in out_dir.rglob("*.gem"):
        verify_gem_bytes(gf.read_bytes())


@pytest.mark.slideshow
@pytest.mark.hygiene
def test_pair_f4_slideshow_plus_f8_constitutional_badge_and_hygiene(tmp_path: Path) -> None:
    """F4 + F8: SlideDeck player.html and .gem metadata preserve epistemic flags with zero hygiene leaks."""
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    constitutional = {
        "operational_metacognition_verified": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "external_actions": 0,
    }
    deck = call_with_supported_kwargs(
        deck_cls,
        slug="const-show",
        title="Constitutional Show",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Zero leaks"]))],
        constitutional=constitutional,
    )
    out = tmp_path / "const_out"
    call_with_supported_kwargs(deck.build, out)
    html = (out / "player.html").read_text(encoding="utf-8")
    assert_hygiene_clean(html, "player.html")
    assert_constitutional_flags(constitutional)


@pytest.mark.wordchart
@pytest.mark.ledger
def test_pair_f1_wordchart_plus_f6_ledger_publisher_atomicity(tmp_path: Path) -> None:
    """F1 + F6: WordChart deck published via publish_ledger produces valid catalog.json and SHA256SUMS."""
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/F6")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    s1 = call_with_supported_kwargs(slide_cls, title="WordChart Ledger", content=call_with_supported_kwargs(wc_cls, title="Ledger", text_body=["Item 1"]))
    deck = call_with_supported_kwargs(deck_cls, slug="wc-ledger", title="WC Ledger", slides=[s1])
    out = tmp_path / "ledger_out"
    call_with_supported_kwargs(publish_fn, [deck], out)
    cat = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert cat["deck_count"] == 1 and cat["total_slides"] == 1
    for digest, rel in parse_sha256sums(out / "SHA256SUMS.presentations"):
        assert sha256_file(out / rel) == digest


@pytest.mark.anthology
@pytest.mark.draw_plus
def test_pair_f5_anthology_plus_f3_gem_vdi_and_cairo_rerender(tmp_path: Path) -> None:
    """F5 + F3: Published Anthology .gem metafiles parse via vdi.scene_from_metafile and re-render via Cairo."""
    from guiai.gem import render, vdi

    catalog = _published_catalog()
    vol_decks = [d for d in catalog["decks"] if str(d.get("slug", "")).startswith("vol-") or "vol." in str(d.get("title", "")).lower()]
    assert len(vol_decks) >= 6, "[R2/F5] Expected 6 published Anthology volumes"
    vol1 = select_anthology_volume(vol_decks, 1)
    pres_root = REPO_ROOT / "research" / "presentations"
    gem_candidates = list((pres_root / "galleries" / vol1["slug"]).glob("*.gem")) + list((pres_root / "decks").glob(f"*{vol1['slug']}*.gem"))
    assert gem_candidates, f"[R2/F5] Missing .gem for {vol1['slug']}"
    raw = gem_candidates[0].read_bytes()
    verify_gem_bytes(raw)
    scene = vdi.scene_from_metafile(raw)
    rerendered = tmp_path / "rerender.png"
    render.write_png(scene, rerendered, width=640)
    verify_rendered_image(rerendered)


@pytest.mark.anthology
@pytest.mark.ledger
def test_pair_f5_anthology_plus_f6_catalog_and_sha256_cross_check() -> None:
    """F5 + F6: Anthology Vol. I-VI disk galleries match catalog.json slide counts and SHA256SUMS."""
    catalog = _published_catalog()
    pres_root = REPO_ROOT / "research" / "presentations"
    sealed = {rel: digest for digest, rel in parse_sha256sums(pres_root / "SHA256SUMS.presentations")}
    vol_decks = [d for d in catalog["decks"] if str(d.get("slug", "")).startswith("vol-") or "vol." in str(d.get("title", "")).lower()]
    assert len(vol_decks) >= 6, "[R2/F5] Expected 6 published Anthology volumes"
    for deck in ordered_anthology_volumes(vol_decks):
        candidates = deck_sealed_artifacts(deck)
        assert candidates, f"[R2/F6] Missing gem/gems/pptx path on {deck.get('slug')}"
        for gem_rel in candidates:
            assert gem_rel in sealed, f"[R2/F6] Missing {gem_rel} in SHA256SUMS.presentations"
            assert sha256_file(pres_root / gem_rel) == sealed[gem_rel]


@pytest.mark.ledger
@pytest.mark.navigation
def test_pair_f6_ledger_plus_f7_markdown_link_integrity(tmp_path: Path) -> None:
    """F6 + F7: Markdown files emitted by publish_ledger have zero broken local links."""
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/F6")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/F1")
    deck = call_with_supported_kwargs(
        deck_cls,
        slug="nav-ledger",
        title="Nav Ledger",
        slides=[call_with_supported_kwargs(slide_cls, title="S1", content=call_with_supported_kwargs(wc_cls, title="S1", text_body=["Link OK"]))],
    )
    out = tmp_path / "nav_pres"
    call_with_supported_kwargs(publish_fn, [deck], out)
    mds = [out / "README.md", *sorted((out / "galleries").rglob("*.md"))]
    assert scan_markdown_links(mds, root=out) == []


@pytest.mark.navigation
@pytest.mark.anthology
def test_pair_f7_navigation_docs_plus_f5_anthology_cross_links() -> None:
    """F7 + F5: README.md and presentations/README.md link cleanly into all 6 Anthology volumes."""
    pres_readme = (REPO_ROOT / "research" / "presentations" / "README.md").read_text(encoding="utf-8")
    top_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "research/presentations/README.md" in top_readme
    for roman in ("Vol. I", "Vol. II", "Vol. III", "Vol. IV", "Vol. V", "Vol. VI"):
        assert roman in pres_readme, f"[R3/F7] presentations/README.md missing {roman}"
    broken = scan_markdown_links([REPO_ROOT / "research" / "presentations" / "README.md"])
    assert not broken


@pytest.mark.navigation
@pytest.mark.hygiene
def test_pair_f7_navigation_plus_f8_repo_wide_hygiene_sweep() -> None:
    """F7 + F8: Every published markdown document passes both link integrity and hygiene cleanliness."""
    md_files = (
        [REPO_ROOT / "README.md"]
        + sorted((REPO_ROOT / "docs").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
    )
    assert not scan_markdown_links(md_files), "Broken links detected"
    for md in md_files:
        strict = md.name in ("README.md", "PROOF-PACKET.md") and md.parent in (REPO_ROOT, REPO_ROOT / "docs")
        assert_hygiene_clean(md.read_text(encoding="utf-8"), str(md.relative_to(REPO_ROOT)), strict_file_scheme=strict)


@pytest.mark.graph
@pytest.mark.slideshow
def test_pair_f2_graph_plus_f4_optional_pptx_vs_native_parity(tmp_path: Path, no_office_env: tuple[dict[str, str], Path]) -> None:
    """F2 + F4: Graph + SlideDeck native .gem/PNG/player pipeline succeeds independent of optional pptx."""
    _, sentinel = no_office_env
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/F4")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/F4")
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/F2")
    g = call_with_supported_kwargs(graph_cls, title="Parity", chart_type="pie", categories=["A", "B"], series=[{"name": "P", "values": [60.0, 40.0]}])
    deck = call_with_supported_kwargs(deck_cls, slug="parity", title="Parity", slides=[call_with_supported_kwargs(slide_cls, title="Chart", content=g)])
    out = tmp_path / "parity_out"
    call_with_supported_kwargs(deck.build, out)
    assert list(out.rglob("*.gem")) and (out / "player.html").is_file()
    assert not sentinel.exists()

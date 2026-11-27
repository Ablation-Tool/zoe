"""Tier 4 Real-World End-to-End Application Scenarios (Workloads W1-W6)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

import pytest

from .conftest import (
    PYTHON_BIN,
    REPO_ROOT,
    assert_constitutional_flags,
    assert_hygiene_clean,
    assert_offline_player_controls,
    call_with_supported_kwargs,
    deck_sealed_artifacts,
    find_headless_browser,
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

pytestmark = pytest.mark.tier4


def _published_catalog() -> dict[str, Any]:
    cat_path = REPO_ROOT / "research" / "presentations" / "catalog.json"
    assert cat_path.is_file(), f"[R2] Missing catalog.json: {cat_path}"
    return json.loads(cat_path.read_text(encoding="utf-8"))


def _vol_decks(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    decks = [
        d for d in catalog.get("decks", [])
        if str(d.get("slug", "")).startswith("vol-") or "vol." in str(d.get("title", "")).lower()
    ]
    assert len(decks) >= 6, f"[R2] Expected 6 Anthology volumes (Vol. I-VI), found {len(decks)}"
    return decks


def _assert_player_static_contract(player_html: str) -> None:
    """Verify zero-CDN offline HTML5 Slide Show Player structure and GEM Output controls."""
    assert_offline_player_controls(player_html)


_DOM_STATE_PROBE_JS = """() => {
  const sig = [];
  for (const el of document.querySelectorAll('*')) {
    const st = window.getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const vis = st.display !== 'none' && st.visibility !== 'hidden' && st.opacity !== '0' && r.width > 0 && r.height > 0;
    if (el.id || el.className) {
      sig.push(`${el.tagName}#${el.id}.${String(el.className)}:${vis}:${el.hidden}:${el.getAttribute('aria-hidden')}`);
    }
  }
  return { text: document.body.innerText, sig: sig.join('|') };
}"""


def _run_playwright_player_smoke(player_path: Path, browser_path: str) -> None:
    """Exercise player.html interactively inside headless Chromium with zero external network calls."""
    from playwright.sync_api import sync_playwright

    external_requests: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=browser_path)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("request", lambda req: external_requests.append(req.url) if req.url.startswith(("http://", "https://")) else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            page.goto(player_path.as_uri(), wait_until="domcontentloaded")
            before_text = page.locator("body").inner_text()
            assert before_text.strip(), "Player DOM rendered empty body"

            page.keyboard.press("ArrowRight")
            after_right = page.locator("body").inner_text()
            assert after_right.strip() and after_right != before_text, "ArrowRight did not advance slide"

            page.keyboard.press("ArrowLeft")
            after_left = page.locator("body").inner_text()
            assert after_left == before_text, "ArrowLeft did not return to initial slide"

            page.keyboard.press("Space")
            after_space = page.locator("body").inner_text()
            assert after_space.strip() and after_space != before_text, "Space did not advance slide"

            page.keyboard.press("ArrowLeft")
            assert page.locator("body").inner_text() == before_text, "ArrowLeft did not return after Space"

            before_notes = page.evaluate(_DOM_STATE_PROBE_JS)
            page.keyboard.press("n")
            after_notes = page.evaluate(_DOM_STATE_PROBE_JS)
            assert after_notes != before_notes, "'n' key did not visibly toggle speaker notes DOM state"
            page.keyboard.press("n")
            assert page.evaluate(_DOM_STATE_PROBE_JS) != after_notes, "Second 'n' press did not toggle notes back"

            before_grid = page.evaluate(_DOM_STATE_PROBE_JS)
            page.keyboard.press("g")
            after_grid = page.evaluate(_DOM_STATE_PROBE_JS)
            assert after_grid != before_grid, "'g' key did not visibly toggle thumbnail grid DOM state"
            page.keyboard.press("Escape")
            assert page.evaluate(_DOM_STATE_PROBE_JS) != after_grid, "Escape key did not close grid/overlay DOM state"

            assert not external_requests, f"Offline player made external requests: {external_requests}"
            assert not page_errors, f"Playwright page errors in player.html: {page_errors}"
        finally:
            browser.close()


# ===========================================================================
# W1: Zero-Office Anthology Build -> .GEM -> Render -> Verify -> Play
# ===========================================================================


@pytest.mark.wordchart
@pytest.mark.graph
@pytest.mark.draw_plus
@pytest.mark.slideshow
@pytest.mark.hygiene
def test_workload_w1_zero_office_anthology_build_render_verify_play(
    tmp_path: Path,
    no_office_env: tuple[dict[str, str], Path],
) -> None:
    """W1: Full zero-Office build of WordChart + Graph + Botanical Draw Plus -> .gem/PNG/JPG/SVG -> ledger."""
    _, sentinel = no_office_env
    wc_cls = require_contract("guiai.gem.presentation.wordchart", "WordChartDoc", req_id="R1/W1")
    graph_cls = require_contract("guiai.gem.presentation.graph", "GraphDoc", req_id="R1/W1")
    canvas_cls = require_contract("guiai.gem.presentation.draw_plus", "DrawPlusCanvas", req_id="R1/W1")
    deck_cls = require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/W1")
    slide_cls = require_contract("guiai.gem.presentation.slideshow", "Slide", req_id="R1/W1")
    publish_fn = require_contract("guiai.gem.presentation.ledger", "publish_ledger", req_id="R2/W1")

    c1 = call_with_supported_kwargs(canvas_cls, width=13333, height=7500, title="Hero")
    c1.add_botanical_frame()
    c1.add_hero_mandala(cx=6666, cy=4300, radius=1200, petals=9)
    wc = call_with_supported_kwargs(wc_cls, title="Vol. I Synthetic", template="hero_obsidian", text_body=["Operational Metacognition"])
    wc.compile(c1)

    c2 = call_with_supported_kwargs(canvas_cls, width=13333, height=7500, title="Chart")
    gr = call_with_supported_kwargs(
        graph_cls,
        title="Shootout AUROC",
        chart_type="bar",
        categories=["Kloster", "MSP", "Entropy"],
        series=[{"name": "AUROC", "values": [0.8382, 0.8360, 0.8145]}],
    )
    gr.compile(c2)

    for idx, canvas in enumerate((c1, c2), start=1):
        assert pick(canvas.verify_layout(), "ok", "passed") is True
        verify_gem_bytes(canvas.to_gem_bytes())
        png = tmp_path / f"w1_s{idx}.png"
        jpg = tmp_path / f"w1_s{idx}.jpg"
        svg = tmp_path / f"w1_s{idx}.svg"
        call_with_supported_kwargs(canvas.render_png, png, width=1280, height=720)
        call_with_supported_kwargs(canvas.render_jpg, jpg, width=1280, height=720)
        canvas.render_svg(svg)
        verify_rendered_image(png)
        verify_rendered_image(jpg)
        verify_svg_document(svg.read_text(encoding="utf-8"))

    deck = call_with_supported_kwargs(
        deck_cls,
        slug="w1-synthetic",
        title="W1 Synthetic Deck",
        slides=[
            call_with_supported_kwargs(slide_cls, title="Hero", canvas=c1, speaker_notes="Hero notes"),
            call_with_supported_kwargs(slide_cls, title="Chart", canvas=c2, speaker_notes="Chart notes"),
        ],
    )
    out_root = tmp_path / "w1_pres"
    call_with_supported_kwargs(publish_fn, [deck], out_root)
    _assert_player_static_contract((out_root / "galleries" / "w1-synthetic" / "player.html").read_text(encoding="utf-8"))
    for digest, rel in parse_sha256sums(out_root / "SHA256SUMS.presentations"):
        assert sha256_file(out_root / rel) == digest
    assert_hygiene_clean((out_root / "catalog.json").read_text(encoding="utf-8"), "w1 catalog.json")
    assert not sentinel.exists()


# ===========================================================================
# W2: Full research/presentations/ Vol. I-VI Gallery, .GEM & SHA-256 Seal
# ===========================================================================


@pytest.mark.draw_plus
@pytest.mark.anthology
@pytest.mark.ledger
@pytest.mark.hygiene
def test_workload_w2_full_vol1_to_6_gallery_gem_and_sha256_seal() -> None:
    """W2: Verify all Vol. I-VI galleries, .gem VDI metafiles, rendered slides, and SHA256SUMS."""
    pres_root = REPO_ROOT / "research" / "presentations"
    catalog = _published_catalog()
    assert catalog["deck_count"] == len(catalog["decks"])
    assert catalog["total_slides"] == sum(d["slides"] for d in catalog["decks"])
    vol_decks = _vol_decks(catalog)

    entries = parse_sha256sums(pres_root / "SHA256SUMS.presentations")
    sealed_map = {rel: digest for digest, rel in entries}
    for digest, rel in entries:
        target = pres_root / rel
        assert target.is_file(), f"[R2/W2] Missing sealed file: {rel}"
        assert sha256_file(target) == digest, f"[R2/W2] Digest mismatch: {rel}"

    for deck in ordered_anthology_volumes(vol_decks):
        gallery_md = pres_root / deck["gallery"]
        assert gallery_md.is_file()
        gallery_dir = gallery_md.parent
        gem_files = sorted(gallery_dir.glob("*.gem")) + sorted((pres_root / "decks").glob(f"*{deck['slug']}*.gem"))
        assert gem_files, f"[R2/W2] Missing .gem for {deck['slug']}"
        for gf in gem_files:
            verify_gem_bytes(gf.read_bytes())
        imgs = sorted(p for p in gallery_dir.iterdir() if p.is_file() and p.name.startswith("slide-") and p.suffix.lower() in (".png", ".jpg"))
        assert len(imgs) == deck["slides"], f"[R2/W2] {deck['slug']} slide count mismatch"
        for img in imgs:
            verify_rendered_image(img)
        assert (gallery_dir / "player.html").is_file()
        candidates = deck_sealed_artifacts(deck)
        assert candidates and all(rel in sealed_map for rel in candidates), (
            f"[R2/W2] Missing sealed gem/gems/pptx entries for {deck.get('slug')}: {candidates}"
        )


# ===========================================================================
# W3: Offline Slide Show Player Playwright + Static DOM/JS & Zero-CDN Audit
# ===========================================================================


@pytest.mark.slideshow
@pytest.mark.anthology
@pytest.mark.hygiene
def test_workload_w3_offline_slideshow_player_playwright_and_static_audit() -> None:
    """W3: Audit published Vol. I offline player.html statically and interactively in headless Chrome."""
    pres_root = REPO_ROOT / "research" / "presentations"
    catalog = _published_catalog()
    vol1 = select_anthology_volume(_vol_decks(catalog), 1)
    player_path = (pres_root / vol1["gallery"]).parent / "player.html"
    assert player_path.is_file(), f"[R1/R2/W3] Missing published player.html at {player_path}"
    html = player_path.read_text(encoding="utf-8")
    assert_hygiene_clean(html, "Vol. I player.html")
    _assert_player_static_contract(html)
    browser_path = find_headless_browser()
    if browser_path:
        _run_playwright_player_smoke(player_path, browser_path)


# ===========================================================================
# W4: Newcomer Monorepo Walkthrough & Observatory 6/6 Gate
# ===========================================================================


@pytest.mark.anthology
@pytest.mark.ledger
@pytest.mark.navigation
def test_workload_w4_newcomer_monorepo_walkthrough_and_observatory_gate() -> None:
    """W4: Traverse README -> docs -> presentations -> Vol. I-VI with 0 broken links and 6/6 observatory."""
    nav_docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "MONOREPO.md",
        REPO_ROOT / "docs" / "RESEARCH-CHRONICLE.md",
        REPO_ROOT / "docs" / "CREATIVE-GALLERY.md",
        REPO_ROOT / "research" / "presentations" / "README.md",
    ]
    for doc in nav_docs:
        assert doc.is_file(), f"Missing core navigation doc: {doc}"
    all_mds = [REPO_ROOT / "README.md"] + sorted((REPO_ROOT / "docs").rglob("*.md")) + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
    broken = scan_markdown_links(all_mds)
    assert not broken, f"[R3/W4] Broken local links: {broken[:12]}"

    report_path = REPO_ROOT / "evidence" / "dorothy-brain-observatory" / "observatory-verification.json"
    orig_bytes = report_path.read_bytes() if report_path.is_file() else None
    try:
        proc = subprocess.run(
            [PYTHON_BIN, str(REPO_ROOT / "scripts" / "verify_observatory_and_packages.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, f"verify_observatory_and_packages.py failed: {proc.stdout}\n{proc.stderr}"
        assert "6/6 PASS" in proc.stdout, f"Unexpected verifier output: {proc.stdout}"
    finally:
        if orig_bytes is not None:
            report_path.write_bytes(orig_bytes)


# ===========================================================================
# W5: Full Constitutional Attribution, Epistemic Honesty & Hygiene Audit
# ===========================================================================


@pytest.mark.anthology
@pytest.mark.ledger
@pytest.mark.navigation
@pytest.mark.hygiene
def test_workload_w5_full_constitutional_attribution_and_hygiene_audit() -> None:
    """W5: Sweep all published docs, presentations, provenance, and .gem 1001 metadata for compliance."""
    from guiai.gem import vdi

    catalog = _published_catalog()
    assert_constitutional_flags(catalog["constitutional"], "catalog.json")
    assert "Nicholas Michael Kloster (March 6, 2026)" in catalog.get("attribution", "")

    surfaces = (
        [REPO_ROOT / "README.md", REPO_ROOT / "assets" / "branding" / "PROVENANCE.md"]
        + sorted((REPO_ROOT / "docs").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.md"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.json"))
        + sorted((REPO_ROOT / "research" / "presentations").rglob("*.html"))
    )
    leaks: list[str] = []
    for path in surfaces:
        if not path.is_file():
            continue
        strict = path.name in ("README.md", "PROOF-PACKET.md") and path.parent in (REPO_ROOT, REPO_ROOT / "docs")
        try:
            assert_hygiene_clean(path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT)), strict_file_scheme=strict)
        except AssertionError as exc:
            leaks.append(str(exc))
    assert not leaks, "\n".join(leaks[:10])

    for gf in sorted((REPO_ROOT / "research" / "presentations").rglob("*.gem")):
        parsed = vdi.parse_metafile(gf.read_bytes())
        for rec in parsed["records"]:
            if rec["command"] == 5 and rec["subcommand"] == 99 and rec["values"] and rec["values"][0] == 1001:
                payload = bytes(v & 0xFF for v in rec["values"][1:]).decode("ascii", "ignore")
                assert_hygiene_clean(payload, f"{gf.name} 1001 metadata")


# ===========================================================================
# W6: End-to-End `zoe present` CLI Subcommand Pipeline
# ===========================================================================


@pytest.mark.wordchart
@pytest.mark.graph
@pytest.mark.draw_plus
@pytest.mark.slideshow
def test_workload_w6_end_to_end_zoe_present_cli_pipeline(
    tmp_path: Path,
    isolated_pres_env: dict[str, str],
    no_office_env: tuple[dict[str, str], Path],
) -> None:
    """W6: Run `zoe present` build -> render -> inspect -> play on CSV/JSON input with zero Office calls."""
    _, sentinel = no_office_env
    require_contract("guiai.gem.presentation.slideshow", "SlideDeck", req_id="R1/W6")
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text("Stage,Score\nTheorem1,100.0\nShootout,83.82\nAblation,100.0\n", encoding="utf-8")
    spec = tmp_path / "deck_spec.json"
    spec.write_text(
        json.dumps({
            "slug": "w6-cli-deck",
            "title": "W6 CLI Pipeline",
            "slides": [
                {"title": "Summary", "template": "hero_obsidian", "text_body": ["Zero Office CLI Pipeline"]},
                {"title": "Metrics", "chart_type": "bar", "csv": str(csv_path)},
            ],
        }),
        encoding="utf-8",
    )
    out_dir = tmp_path / "w6_out"
    assert run_zoe_cli(["present", "build", str(spec), "--output", str(out_dir)], env=isolated_pres_env).returncode == 0
    assert run_zoe_cli(["present", "render", str(out_dir)], env=isolated_pres_env).returncode == 0
    gem_files = sorted(out_dir.rglob("*.gem"))
    assert len(gem_files) >= 2
    for gf in gem_files:
        verify_gem_bytes(gf.read_bytes())
        assert run_zoe_cli(["present", "inspect", str(gf), "--json"], env=isolated_pres_env).returncode == 0
    imgs = sorted(out_dir.rglob("*.png")) or sorted(out_dir.rglob("*.jpg"))
    assert imgs, "Expected rendered slide PNG/JPG images from zoe present render"
    for img in imgs:
        verify_rendered_image(img)
    _assert_player_static_contract((out_dir / "player.html").read_text(encoding="utf-8"))
    assert run_zoe_cli(["present", "play", str(out_dir), "--no-open"], env=isolated_pres_env).returncode == 0
    assert not sentinel.exists()

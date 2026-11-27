"""Unit and integration tests for Anthology Volumes IV, V, and VI."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from unittest import mock

from PIL import Image, ImageStat
import pytest

from guiai.gem import seasip_gem, vdi
from guiai.gem.code_elegance_analyzer import analyze_python_source
from guiai.gem.presentation.anthology_vol4_6 import (
    CONSTITUTIONAL_LOCK,
    VOL4_SLUG,
    VOL5_SLUG,
    VOL6_SLUG,
    build_anthology_vol4_6_decks,
    build_vol4_deck,
    build_vol5_deck,
    build_vol6_deck,
    publish_vol4_6_galleries,
)
from guiai.gem.presentation.ledger import find_hygiene_violations
from guiai.gem.presentation.slideshow import validate_lis_playlist


REPO_ROOT = Path(__file__).resolve().parents[2]
PRES_ROOT = REPO_ROOT / "research" / "presentations"


def _assert_clean_text(text: str, label: str) -> None:
    hits = find_hygiene_violations(text, strict_file_scheme=True)
    assert not hits, f"Hygiene violation in {label}: {hits}"


def test_anthology_vol4_6_module_elegance_grade_a_or_b() -> None:
    src_path = REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "presentation" / "anthology_vol4_6.py"
    rep = analyze_python_source(src_path.read_text(encoding="utf-8"), src_path.name)
    assert rep["grade"] in ("A", "B"), f"anthology_vol4_6.py elegance degraded: {rep}"


def test_anthology_vol4_6_decks_layout_gem_and_constitutional_invariants() -> None:
    decks = build_anthology_vol4_6_decks(repo_root=REPO_ROOT)
    assert [d.slug for d in decks] == [VOL4_SLUG, VOL5_SLUG, VOL6_SLUG]
    assert [d.volume_label for d in decks] == ["Vol. IV", "Vol. V", "Vol. VI"]

    for deck in decks:
        assert deck.category == "Anthology Volume"
        assert len(deck.slides) >= 10
        assert deck.constitutional["l5_agi_qualified"] is False
        assert deck.constitutional["sentience_claimed"] is False
        assert deck.constitutional["zoe_clone_claimed"] is False
        assert deck.constitutional["external_actions"] == 0
        assert deck.constitutional["cloud_cost_usd"] == 0.0

        for idx, slide in enumerate(deck.slides, start=1):
            cv = slide.compile_to_canvas(
                sister_id=deck.sister_id,
                slide_index=idx,
                constitutional=deck.constitutional,
            )
            rep = cv.verify_layout()
            assert rep.ok, f"{deck.slug} slide {idx} layout failed: overlaps={rep.overlaps} oob={rep.out_of_bounds}"

            gem_bytes = cv.to_gem_bytes()
            chk = seasip_gem.verify_seasip_gem_metafile(gem_bytes)
            assert chk["valid"] is True
            assert chk["coordinate_system"] == "RC"
            parsed = vdi.parse_metafile(gem_bytes)
            assert parsed["header"]["coordinate_bounds"] == (0, 0, 13333, 7500)
            inv = vdi.opcode_inventory(gem_bytes)
            assert inv.get("vs_color_legacy", 0) == 0


def test_publish_vol4_6_galleries_clean_room_in_tmp_path(tmp_path: Path) -> None:
    with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess.run forbidden")), \
         mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess.Popen forbidden")):
        res = publish_vol4_6_galleries(tmp_path, repo_root=REPO_ROOT, width=960, height=540)

    assert len(res) == 3
    assert not (tmp_path / "catalog.json").exists()
    assert not (tmp_path / "SHA256SUMS.presentations").exists()
    assert not (tmp_path / "README.md").exists()

    for row in res:
        gdir = Path(row["gallery_dir"])
        assert row["slides"] == row["gems"] == row["pngs"]
        assert not list(gdir.glob("slide-*.jpg"))
        assert (gdir / f"{row['slug']}.lis").is_file()
        assert (gdir / "player.html").is_file()
        assert (gdir / "README.md").is_file()


@pytest.mark.parametrize(
    ("slug", "required_tokens"),
    [
        (VOL4_SLUG, ("UEFI", "188", "OVMF", "UMA", "158", "46 MB", "922 KB")),
        (VOL5_SLUG, ("16", "28", "Balma", "94", "171", "19/19", "Kildall")),
        (VOL6_SLUG, ("PKCS", "0.978351", "44", "CERN", "Groove", "134/134")),
    ],
)
def test_published_vol4_6_galleries_artifacts_tokens_and_hygiene(
    slug: str,
    required_tokens: tuple[str, ...],
) -> None:
    gdir = PRES_ROOT / "galleries" / slug
    assert gdir.is_dir(), f"Missing published gallery directory: {gdir}"

    gems = sorted(gdir.glob("slide-*.gem"))
    pngs = sorted(gdir.glob("slide-*.png"))
    jpgs = sorted(gdir.glob("slide-*.jpg"))
    assert gems, f"No .gem files in {gdir}"
    assert len(pngs) == len(gems), f"Expected 1 PNG per .gem in {gdir}"
    assert not jpgs, f"Unexpected duplicate .jpg slides in {gdir}: {jpgs}"

    for gf in gems:
        raw = gf.read_bytes()
        chk = seasip_gem.verify_seasip_gem_metafile(raw)
        assert chk["valid"] is True
        parsed = vdi.parse_metafile(raw)
        for rec in parsed["records"]:
            if rec["command"] == 5 and rec["subcommand"] == 99 and rec["values"] and rec["values"][0] == 1001:
                meta_txt = bytes(v & 0xFF for v in rec["values"][1:]).decode("ascii", "ignore")
                _assert_clean_text(meta_txt, f"{slug}/{gf.name}")

    for pf in pngs:
        with Image.open(pf) as im:
            w, h = im.size
            assert w >= 1280 and h >= 720
            assert abs((w / h) - (16.0 / 9.0)) < 0.04
            stat = ImageStat.Stat(im.convert("RGB"))
            assert max(stat.stddev) > 5.0

    lis_path = gdir / f"{slug}.lis"
    assert lis_path.is_file()
    val = validate_lis_playlist(lis_path)
    assert len(val.slides) == len(gems)

    player_html = (gdir / "player.html").read_text(encoding="utf-8")
    _assert_clean_text(player_html, f"{slug}/player.html")
    assert "http://" not in player_html and "https://" not in player_html
    for ctrl in ("Space", "ArrowRight", "ArrowLeft", "Escape", "prefers-reduced-motion", "Cycle"):
        assert ctrl in player_html

    readme_text = (gdir / "README.md").read_text(encoding="utf-8")
    _assert_clean_text(readme_text, f"{slug}/README.md")
    for bad in ("todo:", "tbd", "fixme", "lorem ipsum", "[placeholder]"):
        assert bad not in readme_text.lower()
    for tok in required_tokens:
        assert tok in readme_text, f"{slug}/README.md missing grounded token {tok!r}"

    if slug == VOL6_SLUG:
        assert re.search(
            r"l5_agi_qualified\s*[`*_'\"\s]*[=:]\s*[`*_'\"\s]*false\b|l5[^.\n]{0,40}\bnot qualified\b",
            readme_text.lower(),
        ), "Vol. VI README.md missing explicit l5_agi_qualified=False / not qualified boundary"


def test_constitutional_lock_immutable_defaults() -> None:
    assert CONSTITUTIONAL_LOCK["operational_metacognition_verified"] is True
    assert CONSTITUTIONAL_LOCK["sentience_claimed"] is False
    assert CONSTITUTIONAL_LOCK["l5_agi_qualified"] is False
    assert CONSTITUTIONAL_LOCK["zoe_clone_claimed"] is False
    assert CONSTITUTIONAL_LOCK["clinical_action_authorized"] is False
    assert CONSTITUTIONAL_LOCK["cure_claim"] is False
    assert CONSTITUTIONAL_LOCK["external_actions"] == 0
    assert CONSTITUTIONAL_LOCK["cloud_cost_usd"] == 0.0
    assert len(build_vol4_deck(REPO_ROOT).slides) == 10
    assert len(build_vol5_deck().slides) == 10
    assert len(build_vol6_deck().slides) == 11

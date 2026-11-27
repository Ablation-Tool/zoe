"""Unit & Integration Tests for Anthology Volumes I–III (`guiai.gem.presentation.anthology_vol1_3`)."""

from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
from unittest import mock

from PIL import Image, ImageStat
import pytest

from guiai.gem import seasip_gem, vdi
from guiai.gem.code_elegance_analyzer import analyze_python_source
from guiai.gem.presentation import assert_hygiene_clean, find_hygiene_violations, validate_lis_playlist
from guiai.gem.presentation.palette import RUBY, WHITE
from guiai.gem.presentation.anthology_vol1_3 import (
    VOL1_SLUG,
    VOL2_SLUG,
    VOL3_SLUG,
    build_anthology_vol1_3,
    build_vol1_deck,
    build_vol2_deck,
    build_vol3_deck,
    publish_vol1_3_galleries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_anthology_vol1_3_decks_structure_and_layout() -> None:
    """All three volumes expose 12 slides each (36 total) with zero layout collisions or bounds leaks."""
    d1, d2, d3 = build_vol1_deck(), build_vol2_deck(), build_vol3_deck()
    assert [d.slug for d in (d1, d2, d3)] == [VOL1_SLUG, VOL2_SLUG, VOL3_SLUG]
    assert [d.sister_id for d in (d1, d2, d3)] == ["sage", "flora", "mono"]
    assert [len(d.slides) for d in (d1, d2, d3)] == [12, 12, 12]

    all_decks = build_anthology_vol1_3()
    assert len(all_decks) == 3

    for deck in all_decks:
        for idx, slide in enumerate(deck.slides, start=1):
            cv = slide.compile_to_canvas(
                sister_id=deck.sister_id,
                slide_index=idx,
                constitutional=deck.constitutional,
            )
            rep = cv.verify_layout()
            assert rep.ok is True, f"{deck.slug} slide {idx} failed layout: {rep}"


def test_anthology_vol1_3_elegance_grade_a_or_b() -> None:
    """anthology_vol1_3.py and its test module score Grade A or B in Kloster-McCabe Code Elegance Analyzer."""
    for rel in (
        "guiai-lab/guiai/gem/presentation/anthology_vol1_3.py",
        "guiai-lab/tests/test_anthology_vol1_3.py",
    ):
        src_path = REPO_ROOT / rel
        rep = analyze_python_source(src_path.read_text(encoding="utf-8"), src_path.name)
        assert rep["grade"] in ("A", "B"), f"Expected Grade A/B for {rel}, got {rep}"


def test_publish_vol1_3_galleries_zero_office_and_m4_isolation(tmp_path: Path) -> None:
    """publish_vol1_3_galleries emits PNG-only galleries without Office calls or M4 shared files."""
    with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess.run forbidden")), \
         mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess.Popen forbidden")):
        summary = publish_vol1_3_galleries(tmp_path)

    assert len(summary) == 3
    # Must NOT write M4 shared files
    assert not (tmp_path / "catalog.json").exists()
    assert not (tmp_path / "SHA256SUMS.presentations").exists()
    assert not (tmp_path / "README.md").exists()

    for row in summary:
        gdir = Path(row["gallery_dir"])
        gems = sorted(gdir.glob("slide-*.gem"))
        pngs = sorted(gdir.glob("slide-*.png"))
        jpgs = sorted(gdir.glob("slide-*.jpg"))
        svgs = sorted(gdir.glob("slide-*.svg"))
        assert len(gems) == 12
        assert len(pngs) == 12
        assert not jpgs and not svgs

        for gf in gems:
            raw = gf.read_bytes()
            chk = seasip_gem.verify_seasip_gem_metafile(raw)
            assert chk["valid"] is True and chk["coordinate_system"] == "RC"
            inv = vdi.opcode_inventory(raw)
            assert "vs_color_legacy" not in inv
            assert inv.get("vs_color", 0) >= 1

        for img_p in pngs:
            with Image.open(img_p) as im:
                assert im.size == (1920, 1080)
                stat = ImageStat.Stat(im.convert("RGB"))
                assert max(stat.stddev) > 1.0

        lis_files = list(gdir.glob("*.lis"))
        assert len(lis_files) == 1
        pl = validate_lis_playlist(lis_files[0], check_exists=True)
        assert len(pl.slides) == 12

        player_html = (gdir / "player.html").read_text(encoding="utf-8")
        assert "http://" not in player_html and "https://" not in player_html
        assert "ArrowRight" in player_html and "prefers-reduced-motion" in player_html
        assert_hygiene_clean(player_html, f"{row['slug']}/player.html")


def test_anthology_vol1_3_e2e_tokens_and_hygiene(tmp_path: Path) -> None:
    """Generated gallery READMEs contain every required grounded token and zero hygiene/placeholder leaks."""
    publish_vol1_3_galleries(tmp_path)
    v1_md = (tmp_path / "galleries" / VOL1_SLUG / "README.md").read_text(encoding="utf-8")
    v2_md = (tmp_path / "galleries" / VOL2_SLUG / "README.md").read_text(encoding="utf-8")
    v3_md = (tmp_path / "galleries" / VOL3_SLUG / "README.md").read_text(encoding="utf-8")

    for tok in ("A_tau", "0.8382", "30.0", "34.52", "45.07", "Candy Land", "0.4087", "abstention", "16"):
        assert tok in v1_md, f"Vol. I missing {tok!r}"
    for tok in ("MNI152", "240,376", "36", "ML-KEM", "135", "cure_claim=False", "clinical_action_authorized=False"):
        assert tok in v2_md, f"Vol. II missing {tok!r}"
    for tok in ("AIARE", "RXVM", "BEAM", "PALA", "CNSA 2.0", "Kryptos K4", "May 26"):
        assert tok in v3_md, f"Vol. III missing {tok!r}"

    for label, txt in (("vol1", v1_md), ("vol2", v2_md), ("vol3", v3_md)):
        assert_hygiene_clean(txt, label)
        lowered = txt.lower()
        for bad in ("todo:", "tbd", "fixme", "lorem ipsum", "[placeholder]"):
            assert bad not in lowered
        assert not re.search(r"\b133\.11\.216\.212\b", txt)

    src_txt = (REPO_ROOT / "guiai-lab/guiai/gem/presentation/anthology_vol1_3.py").read_text(encoding="utf-8")
    assert find_hygiene_violations(src_txt, strict_file_scheme=True) == []


def test_published_galleries_on_disk_match_contracts() -> None:
    """Published Vol. I–III galleries in research/presentations/galleries/ are valid and link-clean."""
    pres_root = REPO_ROOT / "research" / "presentations"
    for slug in (VOL1_SLUG, VOL2_SLUG, VOL3_SLUG):
        gdir = pres_root / "galleries" / slug
        assert gdir.is_dir(), f"Missing published gallery: {gdir}"
        assert len(sorted(gdir.glob("slide-*.gem"))) == 12
        assert len(sorted(gdir.glob("slide-*.png"))) == 12
        assert not list(gdir.glob("slide-*.jpg"))
        assert (gdir / "player.html").is_file()
        assert (gdir / f"{slug}.lis").is_file()
        readme = gdir / "README.md"
        assert readme.is_file()
        txt = readme.read_text(encoding="utf-8")
        assert_hygiene_clean(txt, f"published {slug}/README.md")
        for idx in range(1, 13):
            assert (gdir / f"slide-{idx:02d}.png").is_file()
            assert (gdir / f"slide-{idx:02d}.gem").is_file()


def test_vol3_slide08_matches_nsa_ring3_evidence() -> None:
    """Vol. III Slide 08 bars match exact m4_root values from nsa-ring3-deep-crypto-report.json and Slide 04 marks Overmatch as proposal."""
    report = json.loads((REPO_ROOT / "evidence/kloster-cryptanalysis/nsa-ring3-deep-crypto-report.json").read_text(encoding="utf-8"))
    ch = report["challenges"]
    expected = [
        round(ch["c25_nsa_skipjack"]["theorem13_12rd_stopping"]["m4_root"], 4),
        round(ch["c23_ecdsa_hnp_lll"]["theorem13_biased_rng_detection"]["m4_root"], 4),
        round(ch["c26_venona_otp_depth"]["theorem13_depth_detection"]["m4_root"], 4),
        round(ch["c26_venona_otp_depth"]["theorem13_single_use_otp_ctrl"]["m4_root"], 4),
        round(ch["c24_dual_ec_drbg"]["hmac_drbg_theorem13_control"]["m4_root"], 4),
        round(ch["c25_nsa_skipjack"]["theorem13_32rd_full_security_ctrl"]["m4_root"], 4),
    ]
    assert expected[3] == pytest.approx(0.0753, abs=1e-4)
    assert expected[5] == pytest.approx(0.0184, abs=1e-4)

    deck = build_vol3_deck()
    cv8 = deck.slides[7].compile_to_canvas(sister_id="mono", slide_index=8, constitutional=deck.constitutional)
    bars = [
        el["bounds"]
        for el in cv8.elements
        if el.get("type") == "rectangle" and el.get("fill") == RUBY and el.get("stroke") == WHITE
    ]
    assert len(bars) == 6
    widths = [b[2] - b[0] for b in bars]
    ratios = [round(w / widths[0], 4) for w in widths]
    assert ratios == pytest.approx(expected, abs=1e-4)

    cv4 = deck.slides[3].compile_to_canvas(sister_id="mono", slide_index=4, constitutional=deck.constitutional)
    txt4 = " ".join(str(el.get("text", "")) for el in cv4.elements if el.get("type") == "text").lower()
    assert "overmatch" in txt4 and "proposal" in txt4


"""Unit tests for Artline Duodecimal Classification System (ADC-12)."""

from __future__ import annotations

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_artline_duodecimal import (
    ADC12_CATALOG,
    ADC12_MAJOR_CLASSES,
    ArtlineDuodecimalIndexer,
    build_adc12_reference_plate,
    from_duodecimal,
    resolve_adc12,
    to_duodecimal,
    write_interactive_adc12_catalog_html,
)


def test_duodecimal_math_matches_artline_page_boundary() -> None:
    """Page A-2 ends at Decimal 143 (EE_12) and Page A-3 starts at Decimal 144 (100_12 = 12^2)."""
    assert to_duodecimal(0) == "0"
    assert to_duodecimal(10) == "X"
    assert to_duodecimal(11) == "E"
    assert to_duodecimal(12) == "10"
    assert to_duodecimal(90) == "76"
    assert to_duodecimal(143) == "EE"
    assert to_duodecimal(144) == "100"
    assert to_duodecimal(255) == "193"

    for n in (0, 10, 11, 32, 51, 53, 78, 83, 90, 101, 111, 118, 143, 144, 212, 255):
        assert from_duodecimal(to_duodecimal(n)) == n
    assert from_duodecimal("EE₁₂") == 143
    assert from_duodecimal("100_12") == 144


def test_adc12_twelve_major_classes_and_four_column_lookup() -> None:
    assert len(ADC12_MAJOR_CLASSES) == 12
    digits = [e.major_digit for e in ADC12_MAJOR_CLASSES]
    assert digits == list("0123456789XE")

    # Every catalog entry has all 4 authentic Artline columns populated and valid page ref
    for entry in ADC12_CATALOG:
        assert 32 <= entry.decimal_code <= 255
        assert entry.page_ref == ("A-2" if entry.decimal_code <= 143 else "A-3")
        assert entry.international and entry.symbol and entry.wombat

    # Multi-lens lookup works by Base-12 call code, Decimal, International, Symbol, and Wombat
    assert resolve_adc12("100").wombat == "✺"
    assert resolve_adc12("100₁₂").decimal_code == 90
    assert resolve_adc12(90).international == "Z"
    assert resolve_adc12("Σ").call_code == "300"
    assert resolve_adc12("✕").call_code == "X00"
    assert resolve_adc12("✌").call_code == "E00"


def test_indexer_plate_and_offline_html_catalog(tmp_path: Path) -> None:
    idx = ArtlineDuodecimalIndexer()
    h1 = idx.highlight("Base-12 Dewey library based on GEM & Artline", "100")
    h2 = idx.highlight("Zero occultism — clean engineering shorthand", "X00")
    assert h1.call_code == "100" and h1.wombat == "✺" and len(h1.receipt_sha256) == 64
    assert h2.call_code == "X00" and h2.decimal_code == 53
    assert len(idx.filter_by_major("1")) == 1
    assert idx.to_dict()["page_a3_start_dozenal"] == "100"

    doc, meta = build_adc12_reference_plate()
    assert meta["major_classes"] == 12
    assert len(doc.elements) > 30
    for ext in ("svg", "png", "gem"):
        out = tmp_path / f"adc12_plate.{ext}"
        doc.export(out, kind=ext)
        assert out.is_file() and out.stat().st_size > 1000

    html_path = write_interactive_adc12_catalog_html(tmp_path / "adc12_catalog.html")
    body = html_path.read_text(encoding="utf-8")
    assert "Artline Duodecimal Classification (ADC-12)" in body
    assert "144" in body and "EE₁₂" in body

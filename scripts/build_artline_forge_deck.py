#!/usr/bin/env python3
"""Generate clean-room companion deck `12-zoe-artline-forge.pptx`.

Uses `guiai.gem.zoe_artline_forge` to collect live archive metrics and render
dark-studio specimen PNGs into a temporary directory, then builds a 6-slide
16:9 widescreen (`13.333" x 7.5"`) deck matching Decks 08-11 styling.

Constitutional Invariants:
  clean_room_original = True · proprietary_code_copied = 0 · external_actions = 0
  sentience_claimed = False · l5_agi_qualified = False
  clinical_action_authorized = False · cure_claim = False · cloud_tokens_used = 0
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile
from typing import Any, Sequence

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
_GUIAI_LAB = str(ROOT / "guiai-lab")
if _GUIAI_LAB not in sys.path:
    sys.path.insert(0, _GUIAI_LAB)

from guiai.gem.zoe_artline_forge import (  # noqa: E402
    CONSTITUTIONAL_FLAGS,
    STUDIO_PALETTES,
    STUDIO_TOOLBOXES,
    _load_archive_bundle,
    render_af4_catalog_poster_png,
    render_af4_specimen_png,
    render_af4_typeset_png,
    render_syf_contact_sheet_png,
)

DEFAULT_OUTPUT_PPTX = ROOT / "research/presentations/decks/12-zoe-artline-forge.pptx"

BG_DARK = "#0B0D18"
CARD_BG = "#141A2E"
CARD_ALT = "#1C233E"
BORDER_BLUE = "#38466C"
TEXT_MAIN = "#F4F6FC"
TEXT_MUTED = "#9CAAC8"
CYAN = "#5CE1E6"
GOLD = "#F8CC30"
PINK = "#FF85B3"
MINT = "#52E5A8"
VIOLET = "#AC82FF"
COBALT = "#4F8EF7"
RUBY = "#F35670"

FONT_SANS = "DejaVu Sans"
FONT_MONO = "DejaVu Sans Mono"
FOOTER_TEXT = (
    "Zoe Artline Forge · Clean-Room GEM AES/VDI & CCP Vector Decoder · "
    "0 Cloud Tokens · $0.00 offline · clean_room_original=True"
)


def _rgb(hex_color: str) -> RGBColor:
    cleaned = hex_color.lstrip("#")
    return RGBColor(int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def _set_slide_bg(slide: Any, hex_color: str = BG_DARK) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(hex_color)


def _add_rect(
    slide: Any,
    left: float,
    top: float,
    width: float,
    height: float,
    *,
    fill_hex: str,
    border_hex: str | None = None,
    border_pt: float = 1.0,
    rounded: bool = False,
) -> Any:
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(
        shape_type,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )
    if rounded:
        try:
            sh.adjustments[0] = 0.06
        except (IndexError, TypeError):
            pass
    sh.fill.solid()
    sh.fill.fore_color.rgb = _rgb(fill_hex)
    if border_hex is not None:
        sh.line.color.rgb = _rgb(border_hex)
        sh.line.width = Pt(border_pt)
    else:
        sh.line.fill.background()
    return sh


def _add_textbox(
    slide: Any,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    *,
    font_name: str = FONT_SANS,
    font_size: float = 11.0,
    color_hex: str = TEXT_MAIN,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    line_spacing: float = 1.15,
) -> Any:
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(0.03)
    tf.margin_right = Inches(0.03)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        run = p.add_run()
        run.text = line
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = _rgb(color_hex)
    return tb


def _add_header_chrome(
    slide: Any,
    *,
    pill_text: str,
    title: str,
    subtitle: str,
    slide_num: int,
    total_slides: int,
    accent_hex: str,
) -> None:
    _add_rect(slide, 0.0, 0.0, 13.333, 0.08, fill_hex=accent_hex)
    _add_rect(
        slide,
        0.55,
        0.24,
        4.35,
        0.34,
        fill_hex=CARD_ALT,
        border_hex=accent_hex,
        border_pt=1.2,
        rounded=True,
    )
    _add_textbox(
        slide,
        0.65,
        0.28,
        4.15,
        0.26,
        pill_text,
        font_size=9.4,
        color_hex=accent_hex,
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    _add_textbox(
        slide,
        11.78,
        0.26,
        1.00,
        0.30,
        f"{slide_num} / {total_slides}",
        font_size=11.0,
        color_hex=TEXT_MUTED,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )
    _add_textbox(
        slide,
        0.55,
        0.64,
        12.23,
        0.44,
        title,
        font_size=21.0,
        color_hex=TEXT_MAIN,
        bold=True,
    )
    _add_textbox(
        slide,
        0.55,
        1.10,
        12.23,
        0.36,
        subtitle,
        font_size=11.4,
        color_hex=TEXT_MUTED,
    )


def _add_footer(slide: Any) -> None:
    _add_rect(slide, 0.55, 7.06, 12.23, 0.015, fill_hex=BORDER_BLUE)
    _add_textbox(
        slide,
        0.55,
        7.11,
        12.23,
        0.28,
        FOOTER_TEXT,
        font_size=9.2,
        color_hex=TEXT_MUTED,
    )


def _add_picture_fit(
    slide: Any,
    img_path: Path,
    left: float,
    top: float,
    max_w: float,
    max_h: float,
) -> Any:
    with Image.open(img_path) as im:
        px_w, px_h = im.size
    aspect = max(1e-6, px_w / float(max(1, px_h)))
    if max_w / max_h >= aspect:
        draw_h = max_h
        draw_w = draw_h * aspect
    else:
        draw_w = max_w
        draw_h = draw_w / aspect
    x = left + (max_w - draw_w) * 0.5
    y = top + (max_h - draw_h) * 0.5
    return slide.shapes.add_picture(str(img_path), Inches(x), Inches(y), width=Inches(draw_w), height=Inches(draw_h))


def build_deck(output_path: Path | str = DEFAULT_OUTPUT_PPTX, archive_root: Path | None = None) -> Path:
    bundle = _load_archive_bundle(archive_root)
    font_count = len(bundle.fonts)
    glyph_slots = sum(f.glyph_count for f in bundle.fonts)
    decoded_glyphs = sum(len(f.glyphs_by_char) for f in bundle.fonts)
    kern_total = sum(len(f.kerning_pairs) for f in bundle.fonts)
    syf_packs_count = len(bundle.syf_libraries)
    syf_total = sum(len(lib.symbols) for lib in bundle.syf_libraries)
    tls_count = len(bundle.tls_toolboxes)
    tls_tools_total = sum(tb.tool_count for tb in bundle.tls_toolboxes)
    col_count = len(bundle.col_palettes)
    col_swatches_total = sum(pal.swatch_count for pal in bundle.col_palettes)
    gem_count = len(bundle.gem_inspections)
    studio_btn_total = sum(len(tb.buttons) for tb in STUDIO_TOOLBOXES)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]
    total_slides = 6

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        poster_png = tmp_dir / "af4_catalog_poster.png"
        typeset_png = tmp_dir / "af4_typeset_sample.png"
        wombat_png = tmp_dir / "wombat_specimen.png"
        stars_png = tmp_dir / "stars_syf_sheet.png"

        render_af4_catalog_poster_png(bundle.fonts, poster_png, sample_text="ZoeNick1990")
        typeset_font = "advtg_n.af4" if "advtg_n.af4" in bundle.fonts_by_key else bundle.fonts[0].filename
        typeset_meta = render_af4_typeset_png(
            typeset_font,
            "AVE, Zoe; 2026",
            typeset_png,
            archive_root=archive_root,
        )
        wombat_font = bundle.fonts_by_key.get("wombat.af4") or bundle.fonts[0]
        render_af4_specimen_png(wombat_font, wombat_png)
        stars_lib = next(
            (lib for lib in bundle.syf_libraries if lib.filename.upper() == "STARS.SYF"),
            bundle.syf_libraries[0],
        )
        render_syf_contact_sheet_png(stars_lib, stars_png, max_symbols=20, cols=5)

        # ------------------------------------------------------------------
        # Slide 1: Hero Overview
        # ------------------------------------------------------------------
        s1 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s1)
        _add_rect(s1, 0.0, 0.0, 13.333, 0.10, fill_hex=GOLD)
        _add_rect(
            s1,
            0.65,
            0.46,
            5.75,
            0.38,
            fill_hex=CARD_ALT,
            border_hex=GOLD,
            border_pt=1.3,
            rounded=True,
        )
        _add_textbox(
            s1,
            0.78,
            0.51,
            5.50,
            0.28,
            "DIGITAL RESEARCH ARTLINE 2.0  ·  ZOE ARTLINE FORGE",
            font_size=10.0,
            color_hex=GOLD,
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        _add_textbox(
            s1,
            11.78,
            0.48,
            0.90,
            0.30,
            f"1 / {total_slides}",
            font_size=11.0,
            color_hex=TEXT_MUTED,
            bold=True,
            align=PP_ALIGN.RIGHT,
        )
        _add_textbox(
            s1,
            0.65,
            1.10,
            12.03,
            1.15,
            "Zoe Artline Forge: Clean-Room CCP Vector Engine\n& Interactive :8765 GEM Studio Workbench",
            font_size=28.0,
            color_hex=TEXT_MAIN,
            bold=True,
            line_spacing=1.12,
        )
        _add_textbox(
            s1,
            0.65,
            2.38,
            11.95,
            0.68,
            f"Pure-Python clean-room decoders for {font_count} .AF4 outline fonts ({glyph_slots:,} glyph slots, "
            f"{kern_total:,} <hBB kerning pairs), {syf_total} CCPA002 .SYF vector symbols, {tls_count} .TLS toolkits, "
            f"{col_count} .COL-as-0xFFFF GEM palettes, and ZOETK001 toolboxes.",
            font_size=13.0,
            color_hex=TEXT_MUTED,
        )

        kpi_cards = [
            (
                CYAN,
                f"{font_count}",
                ".AF4 Outline Fonts",
                f"{decoded_glyphs:,} decoded glyphs\n{glyph_slots:,} slots · {kern_total:,} kern pairs",
            ),
            (
                PINK,
                f"{syf_total}",
                "CCPA002 .SYF Symbols",
                f"{syf_packs_count} packs decoded\nCubic Bezier M/L/C/Z + evenodd",
            ),
            (
                GOLD,
                f"{tls_count} + {col_count}",
                ".TLS & .COL Decoders",
                f"{tls_tools_total} .TLS tools (32x28 1-bit)\n{col_swatches_total:,} .COL -> 0xFFFF GEM",
            ),
            (
                MINT,
                "ZOETK001",
                "Interactive /forge UI",
                f"{len(STUDIO_TOOLBOXES)} toolboxes · {studio_btn_total} buttons\n{gem_count} .GEM inspected · SVG/GEM export",
            ),
        ]
        for idx, (accent, metric, label, detail) in enumerate(kpi_cards):
            cx = 0.65 + idx * 3.05
            _add_rect(s1, cx, 3.35, 2.88, 2.42, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
            _add_rect(s1, cx + 0.18, 3.55, 0.58, 0.08, fill_hex=accent)
            _add_textbox(s1, cx + 0.18, 3.74, 2.52, 0.54, metric, font_size=24.0, color_hex=accent, bold=True)
            _add_textbox(s1, cx + 0.18, 4.34, 2.52, 0.36, label, font_size=13.0, color_hex=TEXT_MAIN, bold=True)
            _add_textbox(s1, cx + 0.18, 4.74, 2.52, 0.88, detail, font_size=10.5, color_hex=TEXT_MUTED, line_spacing=1.22)

        _add_rect(s1, 0.65, 6.08, 12.03, 0.58, fill_hex=CARD_BG, border_hex=MINT, border_pt=1.0, rounded=True)
        _add_textbox(
            s1,
            0.85,
            6.19,
            11.63,
            0.36,
            "CLI: zoe-artline forge  |  Sync: zoe-artline sync-studio  |  $0.00 offline · 0 Cloud Tokens · clean_room_original=True",
            font_name=FONT_MONO,
            font_size=10.2,
            color_hex=MINT,
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        _add_footer(s1)

        # ------------------------------------------------------------------
        # Slide 2: .AF4 Fonts & <hBB Kerning Typesetter
        # ------------------------------------------------------------------
        s2 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s2)
        _add_header_chrome(
            s2,
            pill_text="AF4 VECTOR FONTS & <hBB KERNING",
            title=f"All {font_count} .AF4 Outline Typefaces & Kerning-Aware Typesetter",
            subtitle=f"Decodes {glyph_slots:,} glyph slots ({decoded_glyphs:,} active glyphs), 0x0002 composites, and {kern_total:,} EOF <hBB kerning pairs",
            slide_num=2,
            total_slides=total_slides,
            accent_hex=CYAN,
        )

        _add_rect(s2, 0.55, 1.62, 6.65, 5.24, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s2,
            0.73,
            1.72,
            6.30,
            0.28,
            "35-Font .AF4 Atlas Specimen ('ZoeNick1990' · PIL Bezier)",
            font_size=10.2,
            color_hex=CYAN,
            bold=True,
        )
        _add_picture_fit(s2, poster_png, 0.70, 2.06, 6.35, 4.68)

        _add_rect(s2, 7.38, 1.62, 5.40, 1.84, fill_hex=CARD_BG, border_hex=GOLD, border_pt=1.2, rounded=True)
        _add_textbox(
            s2,
            7.56,
            1.72,
            5.05,
            0.28,
            f"Kerning Typesetter: {typeset_font} -> 'AVE, Zoe; 2026' (kern={typeset_meta['kerning_applied_count']})",
            font_size=10.0,
            color_hex=GOLD,
            bold=True,
        )
        _add_picture_fit(s2, typeset_png, 7.56, 2.04, 5.05, 1.30)

        _add_rect(s2, 7.38, 3.60, 5.40, 3.26, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s2,
            7.56,
            3.72,
            5.05,
            0.32,
            "Clean-Room .AF4 Decoder & Typesetting Pipeline",
            font_size=12.5,
            color_hex=CYAN,
            bold=True,
        )
        af4_bullets = (
            "• 0x0004 Binary Header: font ID, space_width, BBox & glyph table\n"
            "• 0x0002 Composite Offsets: ligatures & accented sub-glyphs\n"
            "• EOF <hBB Kerning Table: signed 16-bit delta + (left, right) pairs\n"
            "• CP437 / Atari ST Map: Unicode -> glyph slot via _ATARI_UNICODE_EXTRA\n"
            "• Compound Evenodd SVG: inner holes cut cleanly via fill-rule='evenodd'\n"
            "• Triple Export: inline .SVG, PIL PNG & 0xFFFF GEM VDI polygons"
        )
        _add_textbox(
            s2,
            7.56,
            4.10,
            5.05,
            2.64,
            af4_bullets,
            font_size=10.3,
            color_hex=TEXT_MAIN,
            line_spacing=1.30,
        )
        _add_footer(s2)

        # ------------------------------------------------------------------
        # Slide 3: CCPA002 .SYF & wombat.af4 Bezier Vector Vault
        # ------------------------------------------------------------------
        s3 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s3)
        _add_header_chrome(
            s3,
            pill_text="CCPA002 .SYF & WOMBAT.AF4 VECTOR VAULT",
            title=f"{syf_total} .SYF Vector Symbols ({syf_packs_count} Packs) & wombat.af4 Ornate Glyphs",
            subtitle="1988-1990 16-bit integer cubic Bezier contours decoded from binary CCP streams with zero Cairo or GPU runtime",
            slide_num=3,
            total_slides=total_slides,
            accent_hex=PINK,
        )

        _add_rect(s3, 0.55, 1.62, 5.85, 5.24, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s3,
            0.73,
            1.72,
            5.50,
            0.28,
            f"wombat.af4 Specimen (Font ID {wombat_font.font_id} · {len(wombat_font.glyphs_by_char)} Decoded Glyphs)",
            font_size=10.2,
            color_hex=GOLD,
            bold=True,
        )
        _add_picture_fit(s3, wombat_png, 0.70, 2.04, 5.55, 4.70)

        _add_rect(s3, 6.58, 1.62, 6.20, 3.48, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s3,
            6.76,
            1.72,
            5.84,
            0.28,
            f"{stars_lib.filename} Contact Sheet ({syf_packs_count} CCPA002 Packs · {syf_total} Symbols)",
            font_size=10.2,
            color_hex=PINK,
            bold=True,
        )
        _add_picture_fit(s3, stars_png, 6.74, 2.04, 5.88, 2.94)

        _add_rect(s3, 6.58, 5.24, 6.20, 1.62, fill_hex=CARD_BG, border_hex=PINK, border_pt=1.1, rounded=True)
        _add_textbox(
            s3,
            6.76,
            5.33,
            5.84,
            0.28,
            "CCP Bezier Flags (decode_ccp_segments -> M/L/C/Z)",
            font_size=10.5,
            color_hex=MINT,
            bold=True,
        )
        _add_textbox(
            s3,
            6.76,
            5.68,
            5.84,
            1.10,
            "0x20 / 0x02 : Move-To (new subpath)     0x01 / 0x10 : Cubic Bezier (C)\n"
            "0x08        : Line-To (L)               0x04        : Close Contour (Z)\n"
            "Largest Packs: MIX2 (33), MIX1 (30), ARROWS (28), STARS (19), ANIMALS (18)",
            font_name=FONT_MONO,
            font_size=9.1,
            color_hex=TEXT_MAIN,
            line_spacing=1.26,
        )
        _add_footer(s3)

        # ------------------------------------------------------------------
        # Slide 4: ZOETK001 Programmable Toolboxes & 1990 CCPTK001 .TLS
        # ------------------------------------------------------------------
        s4 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s4)
        _add_header_chrome(
            s4,
            pill_text="ZOETK001 STUDIO TOOLBOXES & CCPTK001 .TLS",
            title=f"ZOETK001 Programmable Toolboxes ({studio_btn_total} Tools) & {tls_count} Archive .TLS Files",
            subtitle=f"SHA-256 framed ZOETK001 studio palettes paired with {tls_tools_total} decoded 1990 32x28 1-bit monochrome .TLS icons",
            slide_num=4,
            total_slides=total_slides,
            accent_hex=MINT,
        )

        tb_accents = [CYAN, GOLD, PINK, MINT]
        for idx, tb in enumerate(STUDIO_TOOLBOXES):
            cx = 0.55 + idx * 3.10
            accent = tb_accents[idx % len(tb_accents)]
            _add_rect(s4, cx, 1.64, 2.93, 2.58, fill_hex=CARD_BG, border_hex=accent, border_pt=1.2, rounded=True)
            _add_textbox(
                s4,
                cx + 0.14,
                1.74,
                2.65,
                0.28,
                tb.toolbox_id,
                font_name=FONT_MONO,
                font_size=10.5,
                color_hex=accent,
                bold=True,
            )
            _add_textbox(
                s4,
                cx + 0.14,
                2.03,
                2.65,
                0.30,
                f"{tb.columns} cols · {len(tb.buttons)} buttons",
                font_size=9.6,
                color_hex=TEXT_MUTED,
            )
            btn_lines = [f"• [{b.shortcut}] {b.label} ({b.adc12_code})" for b in tb.buttons[:6]]
            if len(tb.buttons) > 6:
                btn_lines.append(f"  + {len(tb.buttons) - 6} more ({tb.buttons[-1].label})")
            _add_textbox(
                s4,
                cx + 0.14,
                2.36,
                2.65,
                1.78,
                "\n".join(btn_lines),
                font_size=9.1,
                color_hex=TEXT_MAIN,
                line_spacing=1.20,
            )

        _add_rect(s4, 0.55, 4.40, 6.15, 2.48, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s4,
            0.73,
            4.50,
            5.80,
            0.30,
            f"1990 CCPTK001\\0 .TLS Decoder ({tls_count} Toolkits · {tls_tools_total} Tools)",
            font_size=12.0,
            color_hex=CYAN,
            bold=True,
        )
        tls_summary = ", ".join(f"{t.filename} ({t.tool_count})" for t in bundle.tls_toolboxes)
        _add_textbox(
            s4,
            0.73,
            4.86,
            5.80,
            1.90,
            f"Archive Packs: {tls_summary}\n\n"
            "• Each tool record unpacks a 32x28 1-bit monochrome icon from chunk[88:200]\n"
            "• Exposed in /forge & /api/forge/catalog with live SVG bitmap previews\n"
            "• Clean-room parser handles truncated/synthetic test payloads safely",
            font_size=9.8,
            color_hex=TEXT_MAIN,
            line_spacing=1.24,
        )

        _add_rect(s4, 6.90, 4.40, 5.88, 2.48, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s4,
            7.08,
            4.50,
            5.52,
            0.30,
            "ZOETK001 Binary Framing & Roundtrip Integrity",
            font_size=12.0,
            color_hex=MINT,
            bold=True,
        )
        _add_textbox(
            s4,
            7.08,
            4.86,
            5.52,
            1.90,
            "Format: b'ZOETK001' + sha256(body)[:8] + UTF-8 JSON payload\n\n"
            "• Verified via ZoeToolboxSpec.from_zoetk_binary(raw)\n"
            "• Exportable via zoe-artline forge & POST /api/forge/export\n"
            "• Tampered digests rejected cleanly before button dispatch",
            font_size=9.8,
            color_hex=TEXT_MAIN,
            line_spacing=1.26,
        )
        _add_footer(s4)

        # ------------------------------------------------------------------
        # Slide 5: .COL-as-0xFFFF GEM VDI Palettes & .GEM Inspector
        # ------------------------------------------------------------------
        s5 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s5)
        _add_header_chrome(
            s5,
            pill_text="0xFFFF GEM VDI PALETTES & .GEM INSPECTOR",
            title=f".COL-as-0xFFFF GEM VDI Palettes & {gem_count}-Sample .GEM Metafile Inspector",
            subtitle=f"{col_count} archive .COL files ({col_swatches_total:,} swatches) + {len(STUDIO_PALETTES)} STUDIO_PALETTES compiled to 0xFFFF VDI metafiles",
            slide_num=5,
            total_slides=total_slides,
            accent_hex=VIOLET,
        )

        _add_rect(s5, 0.55, 1.62, 6.32, 5.24, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s5,
            0.73,
            1.72,
            5.96,
            0.30,
            "STUDIO_PALETTES Visual Swatch Strips -> .col.gem (0xFFFF)",
            font_size=11.8,
            color_hex=VIOLET,
            bold=True,
        )
        for p_idx, pal in enumerate(STUDIO_PALETTES):
            py = 2.14 + p_idx * 1.15
            _add_textbox(
                s5,
                0.73,
                py,
                5.96,
                0.24,
                f"{pal.palette_id} ({len(pal.swatches)} swatches · GEM VDI 0xFFFF)",
                font_name=FONT_MONO,
                font_size=9.4,
                color_hex=TEXT_MAIN,
                bold=True,
            )
            for s_idx, sw in enumerate(pal.swatches[:8]):
                sx = 0.73 + s_idx * 0.74
                _add_rect(
                    s5,
                    sx,
                    py + 0.28,
                    0.66,
                    0.46,
                    fill_hex=sw.hex_color,
                    border_hex=BORDER_BLUE,
                    border_pt=0.8,
                    rounded=True,
                )
                _add_textbox(
                    s5,
                    sx - 0.02,
                    py + 0.77,
                    0.70,
                    0.22,
                    sw.hex_color.upper(),
                    font_name=FONT_MONO,
                    font_size=7.4,
                    color_hex=TEXT_MUTED,
                    align=PP_ALIGN.CENTER,
                )

        _add_rect(s5, 7.05, 1.62, 5.73, 2.52, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s5,
            7.23,
            1.72,
            5.38,
            0.30,
            f"Archive .COL Decoder ({col_count} Files · {col_swatches_total:,} Swatches)",
            font_size=11.8,
            color_hex=GOLD,
            bold=True,
        )
        col_list_str = ", ".join(f"{c.filename} ({c.swatch_count})" for c in bundle.col_palettes)
        _add_textbox(
            s5,
            7.23,
            2.08,
            5.38,
            1.96,
            f"Decoded: {col_list_str}\n\n"
            "• Parses 0xFFFF GEM VDI Escape 5/99/201|204 & vs_color (14)\n"
            "• Normalizes 0..1000 VDI RGB channels cleanly into #RRGGBB hex\n"
            "• CLI: zoe-artline forge --inspect-col <file.col>",
            font_size=9.6,
            color_hex=TEXT_MAIN,
            line_spacing=1.24,
        )

        _add_rect(s5, 7.05, 4.30, 5.73, 2.56, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s5,
            7.23,
            4.40,
            5.38,
            0.30,
            f".GEM Metafile Inspector ({gem_count} Archive Samples Verified)",
            font_size=11.8,
            color_hex=CYAN,
            bold=True,
        )
        sample_names = ", ".join(str(g["filename"]) for g in bundle.gem_inspections[:6])
        _add_textbox(
            s5,
            7.23,
            4.76,
            5.38,
            1.98,
            f"Samples: {sample_names}...\n\n"
            "• Powered by guiai.gem.vdi.parse_metafile() + opcode_inventory()\n"
            "• Caps/validates <3-pt v_fillarea records before binary emission\n"
            "• Roundtrip verified: bytes_consumed == len(raw_gem)",
            font_size=9.6,
            color_hex=TEXT_MAIN,
            line_spacing=1.24,
        )
        _add_footer(s5)

        # ------------------------------------------------------------------
        # Slide 6: Interactive /forge, Memoization, sync-studio & Constitution
        # ------------------------------------------------------------------
        s6 = prs.slides.add_slide(blank_layout)
        _set_slide_bg(s6)
        _add_header_chrome(
            s6,
            pill_text="LIVE /FORGE CANVAS, SYNC & CONSTITUTION",
            title="Interactive /forge Studio, Memoization & Constitutional Invariants",
            subtitle="~0.023s warm catalog/render, offline HTML sync-studio, and strict $0.00 / zero-copy boundaries",
            slide_num=6,
            total_slides=total_slides,
            accent_hex=MINT,
        )

        _add_rect(s6, 0.55, 1.62, 5.98, 2.52, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s6,
            0.73,
            1.72,
            5.62,
            0.30,
            "Interactive /forge Workbench & HTTP APIs",
            font_size=11.8,
            color_hex=CYAN,
            bold=True,
        )
        _add_textbox(
            s6,
            0.73,
            2.08,
            5.62,
            1.96,
            "• Canvas Tools: 9-way align, mirror H/V, snap grid, scale/rotate/undo\n"
            "• Live Typesetter: all 35 .AF4 fonts + <hBB kerning + evenodd contours\n"
            "• APIs: /forge, /api/forge/catalog, /api/forge/font/<name>, /api/forge/export\n"
            "• Export Formats: .GEM (0xFFFF), .SVG (evenodd), .ZOETK, .JSON",
            font_size=9.7,
            color_hex=TEXT_MAIN,
            line_spacing=1.26,
        )

        _add_rect(s6, 0.55, 4.30, 5.98, 2.56, fill_hex=CARD_BG, border_hex=BORDER_BLUE, border_pt=1.2, rounded=True)
        _add_textbox(
            s6,
            0.73,
            4.40,
            5.62,
            0.30,
            "Thread-Safe Memoization & Offline sync-studio",
            font_size=11.8,
            color_hex=GOLD,
            bold=True,
        )
        _add_textbox(
            s6,
            0.73,
            4.76,
            5.62,
            1.98,
            "• _FORGE_CACHE_LOCK (RLock) + _archive_fingerprint() -> ~0.023s warm\n"
            "• Automatic 'portable_clean_room_synth' fallback if archive absent\n"
            "• zoe-artline sync-studio writes 4 standalone HTMLs + SHA-256 manifest\n"
            "• external_actions = 0 default; explicit --push-pixel only when attached",
            font_size=9.7,
            color_hex=TEXT_MAIN,
            line_spacing=1.26,
        )

        _add_rect(s6, 6.72, 1.62, 6.06, 5.24, fill_hex=CARD_BG, border_hex=MINT, border_pt=1.3, rounded=True)
        _add_textbox(
            s6,
            6.92,
            1.74,
            5.66,
            0.32,
            "Constitutional Invariants (CONSTITUTION.md)",
            font_size=13.0,
            color_hex=MINT,
            bold=True,
        )
        const_rows = [
            f"clean_room_original         = {CONSTITUTIONAL_FLAGS['clean_room_original']}",
            f"proprietary_code_copied     = {CONSTITUTIONAL_FLAGS['proprietary_code_copied']}",
            f"external_actions            = {CONSTITUTIONAL_FLAGS['external_actions']}  (offline default)",
            f"sentience_claimed           = {CONSTITUTIONAL_FLAGS['sentience_claimed']}",
            f"l5_agi_qualified            = {CONSTITUTIONAL_FLAGS['l5_agi_qualified']}",
            f"clinical_action_authorized  = {CONSTITUTIONAL_FLAGS['clinical_action_authorized']}",
            f"cure_claim                  = {CONSTITUTIONAL_FLAGS['cure_claim']}",
            f"cloud_tokens_used           = {CONSTITUTIONAL_FLAGS['cloud_tokens_used']}  ($0.00 offline)",
        ]
        _add_rect(s6, 6.92, 2.18, 5.66, 3.00, fill_hex=CARD_ALT, border_hex=BORDER_BLUE, border_pt=1.0, rounded=True)
        _add_textbox(
            s6,
            7.08,
            2.30,
            5.34,
            2.76,
            "\n".join(const_rows),
            font_name=FONT_MONO,
            font_size=10.3,
            color_hex=TEXT_MAIN,
            line_spacing=1.42,
        )
        _add_textbox(
            s6,
            6.92,
            5.42,
            5.66,
            1.12,
            "Attribution: Nicholas Michael Kloster (March 6, 2026) x Zoe\n"
            "Honoring: Gary & Dorothy McEwen Kildall / Digital Research\n"
            "Verification: 0 Cloud Tokens · 100% deterministic pure Python",
            font_size=9.8,
            color_hex=TEXT_MUTED,
            line_spacing=1.30,
        )
        _add_footer(s6)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(out))
        return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_artline_forge_deck",
        description="Build clean-room companion deck 12-zoe-artline-forge.pptx",
    )
    p.add_argument("--output", default=str(DEFAULT_OUTPUT_PPTX), help="Output .pptx path")
    p.add_argument("--archive-root", default=None, help="Optional override Artline extracted archive root")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ns = build_parser().parse_args(list(argv) if argv is not None else None)
    arch = Path(ns.archive_root) if ns.archive_root else None
    out = build_deck(Path(ns.output), archive_root=arch)
    print(f"Generated {out} ({out.stat().st_size} bytes)")
    return 0


__all__ = ["DEFAULT_OUTPUT_PPTX", "build_deck", "build_parser", "main"]

if __name__ == "__main__":
    raise SystemExit(main())

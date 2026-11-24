"""Digital Research Artline 2.0 Font ID Registry, Symbol/Wombats Tables & Workspace Specimen Renderer.

Maps authentic 1990 Digital Research Artline Utilities Guide Font IDs (pp. C-1/C-2) onto
installed open-source metric-compatible OpenType/TrueType/Type1 typefaces (URW Base35,
Bitstream Charter, MathJax Fraktur, DejaVu Math, Noto Music, Noto Symbols2), plus renders an
authentic Artline 2.0 Screen ('Workspace, Drawing Surface, and Surround', User Guide pp. 1-4/1-5).

Zero copyrighted text, zero hardcoded user paths, zero cloud tokens (`CONSTITUTION.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class ArtlineFontSpec:
    font_id: int
    name: str
    category: str
    candidates: tuple[str, ...]
    sample: str


# Authentic Digital Research Artline 2.0 Font IDs (Artline Utilities Guide pp. C-1 & C-2)
ARTLINE_FONTS: tuple[ArtlineFontSpec, ...] = (
    ArtlineFontSpec(
        1, "Fixed Pitch", "mono",
        ("/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
        "Zoe · GEM-84 · Fixed Pitch (ID 1)",
    ),
    ArtlineFontSpec(
        2, "Swiss (Sans Serif)", "sans",
        ("/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        "Zoe · Milestone 1 Brain Cancer R&D (Swiss ID 2)",
    ),
    ArtlineFontSpec(
        9, "Bitstream Charter", "serif",
        ("/usr/share/fonts/type1/texlive-fonts-recommended/bchr8a.pfb", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        "Zoe · Dorothy MNI152 Observatory (Bitstream Charter ID 9)",
    ),
    ArtlineFontSpec(
        10, "Blackletter (Cloister)", "display",
        ("/usr/share/fonts/opentype/mathjax/MathJax_Fraktur-Bold.otf", "/usr/share/fonts/opentype/mathjax/MathJax_Fraktur-Regular.otf"),
        "Zoe - Digital Research Chronicle (Blackletter ID 10)",
    ),
    ArtlineFontSpec(
        15, "Times Roman / Dutch", "serif",
        ("/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        "Zoe · Preclinical Evidence Synthesis (Times Roman ID 15)",
    ),
    ArtlineFontSpec(
        20, "New Century Schoolbook", "serif",
        ("/usr/share/fonts/opentype/urw-base35/C059-Roman.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        "Zoe · Pediatric Compliance Cliffs (Century ID 20)",
    ),
    ArtlineFontSpec(
        21, "Palatino", "serif",
        ("/usr/share/fonts/opentype/urw-base35/P052-Roman.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        "Zoe · Symmetry & Geometry Repeatable (Palatino ID 21)",
    ),
    ArtlineFontSpec(
        23, "Bookman (Demi)", "serif",
        ("/usr/share/fonts/opentype/urw-base35/URWBookman-Demi.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        "Zoe · H3K27M DMG Research Workbench (Bookman ID 23)",
    ),
    ArtlineFontSpec(
        35, "Park Avenue / Chancery", "script",
        ("/usr/share/fonts/opentype/urw-base35/Z003-MediumItalic.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
        "Zoe · Research Partner & Atelier (Script ID 35)",
    ),
    ArtlineFontSpec(
        50, "Helvetica Narrow", "sans",
        ("/usr/share/fonts/opentype/urw-base35/NimbusSansNarrow-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        "ZOE · AVIONICS FMA TELEMETRY STRIP (NARROW ID 50)",
    ),
    ArtlineFontSpec(
        51, "Avant Garde (Demi)", "geometric",
        ("/usr/share/fonts/opentype/urw-base35/URWGothic-Demi.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        "ZOE · GARY KILDALL GEM 1984 (AVANT GARDE ID 51)",
    ),
    ArtlineFontSpec(
        102, "Courier", "mono",
        ("/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        "ZOE_GEM.RSC  ib_char=0x2000  0 TOKENS (Courier ID 102)",
    ),
    ArtlineFontSpec(
        128, "Symbol (Math/Greek)", "symbol",
        ("/usr/share/fonts/truetype/dejavu/DejaVuMathTeXGyre.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        "Aτ(p) = |{i : p(i) > τ}|  ·  λ_BV  ·  ∂V/∂t  ·  Σ ∫ √ Δ Ω",
    ),
    ArtlineFontSpec(
        130, "Sonata (Music)", "music",
        ("/usr/share/fonts/truetype/noto/NotoMusic-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        "𝄞   𝄢   𝅝   𝅗𝅥   𝅘𝅥   𝅘𝅥𝅮   𝅘𝅥𝅯   ♩   ♪   ♫   ♬   ♭   ♮   ♯",
    ),
    ArtlineFontSpec(
        131, "Wombats / Keycap", "dingbat",
        ("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        "✂ ✈ ✉ ✎ ✔ ✘ ✚ ★ ✦ ✿ ❄ ◆ ❖ ♠ ♥ ♦ ♣ ➔ ➜ ➤",
    ),
)

ARTLINE_FONT_BY_ID: dict[int, ArtlineFontSpec] = {spec.font_id: spec for spec in ARTLINE_FONTS}

# Authentic Artline Utilities Guide Wombats & Symbol (128) quick reference subset (Decimal 33..254)
ARTLINE_WOMBATS_ROWS: tuple[tuple[int, str, str, str], ...] = (
    (33, "!", "✂", "scissors"),
    (40, "(", "✈", "aviation"),
    (41, ")", "✉", "envelope"),
    (46, ".", "✎", "pencil"),
    (51, "3", "✔", "check"),
    (53, "5", "✘", "cross"),
    (57, "9", "✚", "medical cross"),
    (72, "H", "★", "solid star"),
    (75, "K", "☆", "open star"),
    (83, "S", "✦", "four-point star"),
    (95, "_", "✿", "blossom"),
    (100, "d", "❄", "snowflake"),
    (117, "u", "◆", "diamond gem"),
    (118, "v", "❖", "faceted gem"),
    (172, "←", "①", "badge 1"),
    (182, "∂", "❶", "solid badge 1"),
    (212, "™", "➔", "arrow"),
    (228, "Σ", "➤", "pointer"),
)


def resolve_artline_font(query: str | int) -> ArtlineFontSpec:
    """Resolve an Artline Font ID number (e.g. 51, 21, 10) or partial typeface name."""
    raw = str(query or "51").strip()
    if raw.isdigit():
        fid = int(raw)
        if fid in ARTLINE_FONT_BY_ID:
            return ARTLINE_FONT_BY_ID[fid]
        raise ValueError(f"Unknown Artline Font ID {fid}. Run `/font list` to see available IDs.")
    low = raw.lower()
    for spec in ARTLINE_FONTS:
        if low == spec.name.lower() or low in spec.name.lower() or low == spec.category:
            return spec
    raise ValueError(f"Unknown Artline typeface {query!r}. Run `/font list` to see all {len(ARTLINE_FONTS)} fonts.")


def load_artline_pil_font(font_id_or_name: str | int, size: int = 22) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str]:
    """Load the real installed OTF/TTF/PFB file for an Artline Font ID with clean fallback."""
    spec = resolve_artline_font(font_id_or_name)
    for path in spec.candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size), Path(path).name
            except OSError:
                continue
    return ImageFont.load_default(), "PIL-default"


def format_font_catalog(active_font_id: int = 51) -> list[str]:
    """Format the installed Digital Research Artline 2.0 Font ID table for terminal display."""
    rows = ["Digital Research Artline 2.0 Font ID Catalog (Utilities Guide pp. C-1/C-2 · 0 tokens):"]
    rows.append("  ID   TYPEFACE                  CATEGORY   INSTALLED FONT FILE")
    for spec in ARTLINE_FONTS:
        mark = "★" if spec.font_id == active_font_id else " "
        found = next((Path(p).name for p in spec.candidates if Path(p).is_file()), "fallback")
        rows.append(f"{mark} {spec.font_id:>3}  {spec.name:<25} {spec.category:<10} {found}")
    rows.append("Switch with `/font <id|name>` (e.g. `/font 51`, `/font palatino`, `/font 10`) · `/font specimen` · `/font wombat`")
    return rows


def format_wombats_table() -> list[str]:
    """Render Digital Research Artline's iconic Symbol (128) & Wombats dingbat table."""
    rows = [
        "Digital Research Artline 2.0 — Symbol (ID 128) & Wombats Glyph Table (Dec 33..228):",
        "  DEC   SYM   WOMBAT   NAME             DEC   SYM   WOMBAT   NAME",
    ]
    half = (len(ARTLINE_WOMBATS_ROWS) + 1) // 2
    for i in range(half):
        l = ARTLINE_WOMBATS_ROWS[i]
        left = f"  {l[0]:>3}    {l[1]:<3}    {l[2]:<3}    {l[3]:<15}"
        if i + half < len(ARTLINE_WOMBATS_ROWS):
            r = ARTLINE_WOMBATS_ROWS[i + half]
            right = f"  {r[0]:>3}    {r[1]:<3}    {r[2]:<3}    {r[3]}"
        else:
            right = ""
        rows.append(left + right)
    rows.append("Math Symbol (128): α β γ δ ε λ μ π σ τ φ ψ ω  ·  ∀ ∃ ∂ ∇ ∞ ≤ ≥ ≠ ≈ √ ∑ ∏ ∫ ⊕ ⊗")
    return rows


def render_artline_workspace_specimen(
    output_path: Path | str,
    *,
    active_font_id: int = 51,
    width: int = 1040,
    height: int = 780,
) -> dict[str, Any]:
    """Render an authentic 1990 Digital Research Artline 2.0 Screen showing all installed Font IDs."""
    # Stippled 50% Atari/GEM surround pattern (User Reference Guide pp. 1-4 / 1-5)
    yy, xx = np.mgrid[0:height, 0:width]
    stipple = ((xx + yy) & 1) == 0
    arr = np.where(stipple[:, :, None], (220, 224, 232), (176, 182, 194)).astype(np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    ink = (18, 22, 30)
    paper = (250, 250, 246)
    crimson = (204, 38, 72)
    violet = (75, 36, 126)

    f_ui, _ = load_artline_pil_font(2, size=14)
    f_mono, _ = load_artline_pil_font(102, size=12)

    # 1. Iconic Artline 2.0 Top Menu Bar (User Guide p. 1-4)
    draw.rectangle([0, 0, width - 1, 28], fill=paper, outline=ink, width=2)
    draw.text((14, 6), "File   Image   View   Element   Edit   Combine   Options", fill=ink, font=f_ui)
    draw.text((width - 96, 6), "ARTLINE", fill=crimson, font=f_ui)

    # 2. Title Bar: ZOE_FONTS.GEM - Default Layer
    draw.rectangle([0, 28, width - 1, 52], fill=paper, outline=ink, width=2)
    draw.rectangle([6, 33, 22, 47], fill=crimson, outline=ink)
    draw.text((width // 2 - 125, 33), "ZOE_FONTS.GEM - Default Layer", fill=ink, font=f_ui)
    draw.rectangle([width - 24, 33, width - 8, 47], fill=paper, outline=ink)

    # 3. Left 2-Column Digital Research Artline Toolbox
    draw.rectangle([0, 52, 74, height - 22], fill=(214, 218, 226), outline=ink, width=2)
    tools = ("PTR", "ZOM", "PEN", "Aa", "ELP", "LIN", "MIR", "ROT", "SYM", "WMB", "PIN", "GEM")
    for idx, t in enumerate(tools):
        r, c = divmod(idx, 2)
        tx, ty = 6 + c * 32, 60 + r * 32
        hi = t in {"Aa", "GEM"}
        draw.rectangle([tx, ty, tx + 29, ty + 29], fill=crimson if hi else paper, outline=ink)
        draw.text((tx + 4, ty + 8), t, fill=paper if hi else ink, font=f_mono)

    # 4. Crisp White Drawing Surface with Black Drop Shadow floating inside the Surround
    ds_x0, ds_y0, ds_x1, ds_y1 = 114, 78, width - 54, height - 46
    draw.rectangle([ds_x0 + 10, ds_y0 + 10, ds_x1 + 10, ds_y1 + 10], fill=ink)
    draw.rectangle([ds_x0, ds_y0, ds_x1, ds_y1], fill=paper, outline=ink, width=2)

    # Header inside Drawing Surface
    f_head, head_file = load_artline_pil_font(active_font_id, size=28)
    active_spec = resolve_artline_font(active_font_id)
    draw.text((ds_x0 + 24, ds_y0 + 16), f"Zoe Artline · Active ID {active_spec.font_id}: {active_spec.name}", fill=violet, font=f_head)
    draw.line([(ds_x0 + 20, ds_y0 + 54), (ds_x1 - 20, ds_y0 + 54)], fill=crimson, width=2)

    # Render all installed Artline Font IDs on the Drawing Surface
    y_cursor = ds_y0 + 66
    rendered_count = 0
    for spec in ARTLINE_FONTS:
        pil_font, _fname = load_artline_pil_font(spec.font_id, size=19 if spec.font_id != 130 else 21)
        is_active = spec.font_id == active_spec.font_id
        if is_active:
            draw.rectangle([ds_x0 + 16, y_cursor - 3, ds_x1 - 16, y_cursor + 31], fill=(246, 234, 240), outline=crimson)
        draw.text((ds_x0 + 24, y_cursor + 5), f"ID {spec.font_id:>3}", fill=crimson if is_active else violet, font=f_mono)
        draw.text((ds_x0 + 92, y_cursor + 2), spec.sample, fill=ink, font=pil_font)
        y_cursor += 37
        rendered_count += 1
        if y_cursor > ds_y1 - 44:
            break

    # Bottom surround scrollbar & caption
    draw.rectangle([0, height - 22, width - 1, height - 1], fill=paper, outline=ink, width=2)
    draw.text((84, height - 18), f"Workspace + Surround + Drawing Surface (Artline 2.0 pp. 1-4/C-2) · Active: {head_file} · 0 tokens · sentience_claimed=False", fill=ink, font=f_mono)

    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {
        "ok": True,
        "output_path": str(out),
        "active_font_id": active_spec.font_id,
        "active_font_name": active_spec.name,
        "fonts_rendered": rendered_count,
        "tokens_used": 0,
    }

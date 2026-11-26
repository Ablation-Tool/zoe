from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
import math
from pathlib import Path
from typing import Any, Sequence
import warnings
import xml.etree.ElementTree as ElementTree


NAMED_COLORS = {
    "white": "#ffffff",
    "black": "#000000",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
    "magenta": "#ff00ff",
    "orange": "#e95420",
    "gray": "#808080",
    "lightgray": "#d3d3d3",
}

_DEJAVU_DIR = Path("/usr/share/fonts/truetype/dejavu")

_ARTLINE_PANGO_FAMILIES: dict[int, tuple[str, str]] = {
    1: ("Nimbus Mono PS", "'Nimbus Mono PS', 'DejaVu Sans Mono', monospace"),
    2: ("Nimbus Sans", "'Nimbus Sans', 'DejaVu Sans', sans-serif"),
    9: ("DejaVu Serif", "'DejaVu Serif', Georgia, serif"),
    10: ("MathJax_Fraktur", "'MathJax_Fraktur', 'DejaVu Serif', serif"),
    15: ("Nimbus Roman", "'Nimbus Roman', 'DejaVu Serif', serif"),
    20: ("C059", "'C059', 'DejaVu Serif', serif"),
    21: ("P052", "'P052', 'DejaVu Serif', serif"),
    23: ("URW Bookman", "'URW Bookman', 'DejaVu Serif', serif"),
    35: ("Z003", "'Z003', 'DejaVu Serif', cursive"),
    50: ("Nimbus Sans Narrow", "'Nimbus Sans Narrow', 'DejaVu Sans', sans-serif"),
    51: ("URW Gothic", "'URW Gothic', 'DejaVu Sans', sans-serif"),
    102: ("Nimbus Mono PS", "'Nimbus Mono PS', 'DejaVu Sans Mono', monospace"),
    128: ("DejaVu Math TeX Gyre", "'DejaVu Math TeX Gyre', 'DejaVu Sans', sans-serif"),
    130: ("Noto Music", "'Noto Music', 'DejaVu Sans', sans-serif"),
    131: ("Noto Sans Symbols2", "'Noto Sans Symbols2', 'DejaVu Sans', sans-serif"),
}

_DEJAVU_TTF_MAP: dict[tuple[str, bool, bool], str] = {
    ("DejaVu Sans", False, False): str(_DEJAVU_DIR / "DejaVuSans.ttf"),
    ("DejaVu Sans", True, False): str(_DEJAVU_DIR / "DejaVuSans-Bold.ttf"),
    ("DejaVu Sans", False, True): str(_DEJAVU_DIR / "DejaVuSans-Oblique.ttf"),
    ("DejaVu Sans", True, True): str(_DEJAVU_DIR / "DejaVuSans-BoldOblique.ttf"),
    ("DejaVu Serif", False, False): str(_DEJAVU_DIR / "DejaVuSerif.ttf"),
    ("DejaVu Serif", True, False): str(_DEJAVU_DIR / "DejaVuSerif-Bold.ttf"),
    ("DejaVu Serif", False, True): str(_DEJAVU_DIR / "DejaVuSerif-Italic.ttf"),
    ("DejaVu Serif", True, True): str(_DEJAVU_DIR / "DejaVuSerif-BoldItalic.ttf"),
    ("DejaVu Sans Mono", False, False): str(_DEJAVU_DIR / "DejaVuSansMono.ttf"),
    ("DejaVu Sans Mono", True, False): str(_DEJAVU_DIR / "DejaVuSansMono-Bold.ttf"),
    ("DejaVu Sans Mono", False, True): str(_DEJAVU_DIR / "DejaVuSansMono.ttf"),
    ("DejaVu Sans Mono", True, True): str(_DEJAVU_DIR / "DejaVuSansMono-Bold.ttf"),
}

_FONT_FAMILY_ALIASES: dict[str, tuple[str, str]] = {
    "serif": ("DejaVu Serif", "'DejaVu Serif', Georgia, serif"),
    "dejavu serif": ("DejaVu Serif", "'DejaVu Serif', Georgia, serif"),
    "sans": ("DejaVu Sans", "'DejaVu Sans', Arial, sans-serif"),
    "sans-serif": ("DejaVu Sans", "'DejaVu Sans', Arial, sans-serif"),
    "dejavu sans": ("DejaVu Sans", "'DejaVu Sans', Arial, sans-serif"),
    "mono": ("DejaVu Sans Mono", "'DejaVu Sans Mono', monospace"),
    "monospace": ("DejaVu Sans Mono", "'DejaVu Sans Mono', monospace"),
    "dejavu sans mono": ("DejaVu Sans Mono", "'DejaVu Sans Mono', monospace"),
}


@dataclass(frozen=True)
class FontSpec:
    pango_family: str
    svg_family: str
    ttf_path: str | None
    bold: bool
    italic: bool
    underline: bool
    boxed: bool


def color(value: Any) -> str:
    if not isinstance(value, str):
        return "#000000"
    if value in NAMED_COLORS:
        return NAMED_COLORS[value]
    low = value.lower()
    if low in NAMED_COLORS:
        return NAMED_COLORS[low]
    return value


def _rgba(value: Any, alpha: float = 1.0) -> tuple[float, float, float, float]:
    hex_val = color(value)
    if not isinstance(hex_val, str) or hex_val == "none":
        return (0.0, 0.0, 0.0, 0.0)
    clean = hex_val.lstrip("#")
    if len(clean) != 6:
        return (0.0, 0.0, 0.0, max(0.0, min(1.0, float(alpha))))
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0
    return (r, g, b, max(0.0, min(1.0, float(alpha))))


def _set_cairo_color(context: Any, value: Any, alpha: float = 1.0) -> None:
    r, g, b, a = _rgba(value, alpha)
    if a < 0.999 and hasattr(context, "set_source_rgba"):
        context.set_source_rgba(r, g, b, a)
    else:
        context.set_source_rgb(r, g, b)


def _scene_background(scene: Any) -> str:
    bg = getattr(scene, "background", None)
    if isinstance(bg, str) and bg:
        return bg
    doc = getattr(scene, "document", {})
    if isinstance(doc, dict):
        return str(doc.get("background", "#ffffff"))
    return "#ffffff"


def _paint(item: dict[str, Any]) -> dict[str, str]:
    fill_val = item.get("fill", "none")
    if int(item.get("fill_interior", 1)) == 0:
        fill_val = "none"
    attrs = {
        "fill": color(fill_val),
        "stroke": color(item.get("stroke", "black")),
        "stroke-width": str(item.get("width", 20)),
    }
    fill_alpha = item.get("fill_alpha", item.get("alpha"))
    if fill_alpha is not None and float(fill_alpha) < 1.0 and fill_val != "none":
        attrs["fill-opacity"] = f"{float(fill_alpha):g}"
    stroke_alpha = item.get("stroke_alpha", item.get("alpha"))
    if stroke_alpha is not None and float(stroke_alpha) < 1.0 and item.get("stroke", "none") != "none":
        attrs["stroke-opacity"] = f"{float(stroke_alpha):g}"
    return attrs


def _label(item: dict[str, Any]) -> dict[str, Any] | None:
    if not item.get("label") or item["type"] not in {"rectangle", "rounded_rectangle"}:
        return None
    left, top, right, bottom = item["bounds"]
    size = min(240, (bottom - top) / 3)
    return {
        "position": [(left + right) / 2, (top + bottom) / 2 + size * 0.35],
        "text": item["label"].replace("\n", " · "),
        "size": size,
        "centered": True,
    }


def resolve_font_spec(
    *,
    font_id: int | None = None,
    font_family: str | None = None,
    bold: bool = False,
    italic: bool = False,
    effects: int = 0,
    underline: bool = False,
    boxed: bool = False,
) -> FontSpec:
    is_bold = bool(bold or (effects & 0x01))
    is_italic = bool(italic or (effects & 0x04))
    is_underline = bool(underline or (effects & 0x08))
    is_boxed = bool(boxed or (effects & 0x40))

    pango_fam = "DejaVu Sans"
    svg_fam = "'DejaVu Sans', Arial, sans-serif"
    ttf_path: str | None = None

    if font_id is not None and int(font_id) in _ARTLINE_PANGO_FAMILIES:
        pango_fam, svg_fam = _ARTLINE_PANGO_FAMILIES[int(font_id)]
        try:
            from .zoe_artline_fonts import ARTLINE_FONT_BY_ID
            spec = ARTLINE_FONT_BY_ID.get(int(font_id))
            if spec is not None:
                for cand in spec.candidates:
                    if Path(cand).is_file():
                        ttf_path = cand
                        break
        except Exception:
            ttf_path = None

    if font_family:
        key = str(font_family).strip().lower()
        if key in _FONT_FAMILY_ALIASES:
            pango_fam, svg_fam = _FONT_FAMILY_ALIASES[key]
        else:
            pango_fam = str(font_family).strip()
            svg_fam = f"'{pango_fam}', 'DejaVu Sans', sans-serif"

    if ttf_path is None:
        ttf_cand = _DEJAVU_TTF_MAP.get((pango_fam, is_bold, is_italic))
        if ttf_cand and Path(ttf_cand).is_file():
            ttf_path = ttf_cand
        else:
            fallback = _DEJAVU_TTF_MAP.get(("DejaVu Sans", is_bold, is_italic))
            if fallback and Path(fallback).is_file():
                ttf_path = fallback

    return FontSpec(
        pango_family=pango_fam,
        svg_family=svg_fam,
        ttf_path=ttf_path,
        bold=is_bold,
        italic=is_italic,
        underline=is_underline,
        boxed=is_boxed,
    )


@lru_cache(maxsize=1)
def _import_pango() -> tuple[Any, Any]:
    import gi

    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    with warnings.catch_warnings():
        # Suppress upstream PyGObject override deprecation triggered when loading GLib/Pango.
        warnings.filterwarnings(
            "ignore",
            message=r"GLib\.unix_signal_add_full is deprecated",
            category=DeprecationWarning,
        )
        from gi.repository import Pango, PangoCairo
    return Pango, PangoCairo


@lru_cache(maxsize=8)
def _pango_available() -> bool:
    try:
        import cairo  # noqa: F401
        _import_pango()
        return True
    except (ImportError, ValueError):
        return False


def _measure_pango_line(text: str, spec: FontSpec, size_vdi: float) -> tuple[float, float]:
    import cairo
    Pango, PangoCairo = _import_pango()

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
    ctx = cairo.Context(surf)
    layout = PangoCairo.create_layout(ctx)
    desc = Pango.FontDescription(spec.pango_family)
    desc.set_weight(Pango.Weight.BOLD if spec.bold else Pango.Weight.NORMAL)
    desc.set_style(Pango.Style.ITALIC if spec.italic else Pango.Style.NORMAL)
    desc.set_absolute_size(max(1.0, float(size_vdi)) * Pango.SCALE)
    layout.set_font_description(desc)
    layout.set_text(text if text else " ", -1)
    _ink, logical = layout.get_extents()
    w = (logical.width / Pango.SCALE) if text else 0.0
    h = logical.height / Pango.SCALE
    return (float(w), float(h))


def _measure_pil_line(text: str, spec: FontSpec, size_vdi: float) -> tuple[float, float]:
    from PIL import ImageFont

    ref_px = 200.0
    font = None
    if spec.ttf_path and Path(spec.ttf_path).is_file():
        try:
            font = ImageFont.truetype(spec.ttf_path, size=int(round(ref_px)))
        except OSError:
            font = None
    if font is None:
        return (len(text) * size_vdi * 0.56, size_vdi * 1.18)
    scale = size_vdi / ref_px
    w = float(font.getlength(text)) * scale if text else 0.0
    ascent, descent = font.getmetrics()
    h = float(ascent + descent) * scale
    return (w, h)


def _measure_single_line(text: str, spec: FontSpec, size_vdi: float) -> tuple[float, float]:
    if _pango_available():
        return _measure_pango_line(text, spec, size_vdi)
    return _measure_pil_line(text, spec, size_vdi)


def measure_text_metrics(
    text: str,
    *,
    font_id: int | None = None,
    font_family: str | None = "DejaVu Sans",
    font_pt: float = 10.5,
    size_vdi: float | None = None,
    bold: bool = False,
    italic: bool = False,
    effects: int = 0,
    max_width_vdi: float | None = None,
    wrap: bool = True,
    line_spacing: float = 1.18,
) -> tuple[float, float, list[str]]:
    """Measure wrapped text in VDI units: returns `(max_width_vdi, total_height_vdi, lines)`."""
    spec = resolve_font_spec(
        font_id=font_id,
        font_family=font_family,
        bold=bold,
        italic=italic,
        effects=effects,
    )
    eff_size = float(size_vdi) if size_vdi is not None else float(font_pt) * 1000.0 / 72.0
    eff_size = max(1.0, eff_size)

    raw_paragraphs = str(text).split("\n")
    lines: list[str] = []
    _, sample_line_h = _measure_single_line("Ag", spec, eff_size)
    base_line_h = max(sample_line_h, eff_size * 1.05)

    for para in raw_paragraphs:
        if not para:
            lines.append("")
            continue
        if not wrap or max_width_vdi is None or max_width_vdi <= 0:
            lines.append(para)
            continue
        words = para.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            cand_w, _ = _measure_single_line(candidate, spec, eff_size)
            if cand_w <= max_width_vdi + 0.5 or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)

    if not lines:
        lines = [""]

    widths = [_measure_single_line(line, spec, eff_size)[0] for line in lines]
    max_w = max(widths, default=0.0)
    if len(lines) == 1:
        total_h = base_line_h
    else:
        total_h = base_line_h + (len(lines) - 1) * eff_size * float(line_spacing)
    return (round(max_w, 3), round(total_h, 3), lines)


def _layout_runs_lines(
    runs: Sequence[dict[str, Any]],
    *,
    font_id: int | None = None,
    font_family: str | None = "DejaVu Sans",
    size_vdi: float = 240.0,
    base_bold: bool = False,
    base_italic: bool = False,
    effects: int = 0,
    max_width_vdi: float | None = None,
    wrap: bool = True,
    line_spacing: float = 1.18,
) -> tuple[float, float, str, list[tuple[int, int, str]]]:
    """Layout paragraph `runs` into `(max_w, total_h, full_text, [(start, end, line_str), ...])`."""
    eff_size = max(1.0, float(size_vdi))
    base_spec = resolve_font_spec(
        font_id=font_id,
        font_family=font_family,
        bold=base_bold,
        italic=base_italic,
        effects=effects,
    )
    _, sample_line_h = _measure_single_line("Ag", base_spec, eff_size)
    base_line_h = max(sample_line_h, eff_size * 1.05)

    run_spans: list[tuple[int, int, FontSpec]] = []
    full_chunks: list[str] = []
    pos = 0
    for r in runs:
        rt = str(r.get("text", ""))
        r_bold = bool(r.get("bold", base_bold))
        r_italic = bool(r.get("italic", base_italic))
        r_spec = resolve_font_spec(
            font_id=font_id,
            font_family=font_family,
            bold=r_bold,
            italic=r_italic,
            effects=effects,
        )
        run_spans.append((pos, pos + len(rt), r_spec))
        full_chunks.append(rt)
        pos += len(rt)
    full_text = "".join(full_chunks)

    def _span_width(s: int, e: int) -> float:
        if e <= s:
            return 0.0
        total = 0.0
        for rs, re_, r_spec in run_spans:
            ov_s = max(s, rs)
            ov_e = min(e, re_)
            if ov_e > ov_s:
                total += _measure_single_line(full_text[ov_s:ov_e], r_spec, eff_size)[0]
        return total

    spanned_lines: list[tuple[int, int, str]] = []
    line_widths: list[float] = []

    p_start = 0
    for para in full_text.split("\n"):
        p_end = p_start + len(para)
        if not para:
            spanned_lines.append((p_start, p_start, ""))
            line_widths.append(0.0)
            p_start = p_end + 1
            continue
        if not wrap or max_width_vdi is None or max_width_vdi <= 0:
            spanned_lines.append((p_start, p_end, para))
            line_widths.append(_span_width(p_start, p_end))
            p_start = p_end + 1
            continue

        # Split para by single spaces while tracking exact character offsets in full_text
        words: list[tuple[int, int]] = []
        cur_s = p_start
        for part in para.split(" "):
            cur_e = cur_s + len(part)
            words.append((cur_s, cur_e))
            cur_s = cur_e + 1

        line_s: int | None = None
        line_e: int | None = None
        for ws, we in words:
            if line_s is None:
                line_s, line_e = ws, we
            else:
                cand_w = _span_width(line_s, we)
                if cand_w <= max_width_vdi + 0.5:
                    line_e = we
                else:
                    assert line_e is not None
                    spanned_lines.append((line_s, line_e, full_text[line_s:line_e]))
                    line_widths.append(_span_width(line_s, line_e))
                    line_s, line_e = ws, we
        if line_s is not None and line_e is not None:
            spanned_lines.append((line_s, line_e, full_text[line_s:line_e]))
            line_widths.append(_span_width(line_s, line_e))
        p_start = p_end + 1

    if not spanned_lines:
        spanned_lines = [(0, 0, "")]
        line_widths = [0.0]

    max_w = max(line_widths, default=0.0)
    if len(spanned_lines) == 1:
        total_h = base_line_h
    else:
        total_h = base_line_h + (len(spanned_lines) - 1) * eff_size * float(line_spacing)
    return (round(max_w, 3), round(total_h, 3), full_text, spanned_lines)


def measure_runs_lines(
    runs: Sequence[dict[str, Any]],
    *,
    font_id: int | None = None,
    font_family: str | None = "DejaVu Sans",
    size_vdi: float = 240.0,
    base_bold: bool = False,
    base_italic: bool = False,
    effects: int = 0,
    max_width_vdi: float | None = None,
    wrap: bool = True,
    line_spacing: float = 1.18,
) -> tuple[float, float, list[str]]:
    """Measure wrapped paragraph `runs` with per-run bold/italic font metrics."""
    max_w, total_h, _full_text, spanned_lines = _layout_runs_lines(
        runs,
        font_id=font_id,
        font_family=font_family,
        size_vdi=size_vdi,
        base_bold=base_bold,
        base_italic=base_italic,
        effects=effects,
        max_width_vdi=max_width_vdi,
        wrap=wrap,
        line_spacing=line_spacing,
    )
    return (max_w, total_h, [lt for _s, _e, lt in spanned_lines])


def _is_rich_text(item: dict[str, Any]) -> bool:
    rich_keys = (
        "bounds", "align", "valign", "font_id", "font_family",
        "bold", "italic", "underline", "boxed", "effects",
        "line_spacing", "wrap", "rotation", "runs", "paragraphs",
        "max_width", "pad_x", "pad_y", "box_fill", "box_stroke",
    )
    if any(k in item for k in rich_keys):
        return True
    return "\n" in str(item.get("text", ""))


def _dash_array(item: dict[str, Any]) -> list[float]:
    explicit = item.get("dash_array")
    if explicit:
        return [float(v) for v in explicit if float(v) > 0]
    line_type = int(item.get("line_type", 1))
    if line_type <= 1:
        return []
    u = max(float(item.get("width", 12)), 10.0)
    patterns = {
        2: [4.0 * u, 2.0 * u],
        3: [1.0 * u, 1.5 * u],
        4: [3.5 * u, 1.5 * u, 1.0 * u, 1.5 * u],
        5: [2.5 * u, 2.0 * u],
        6: [3.5 * u, 1.2 * u, 1.0 * u, 1.2 * u, 1.0 * u, 1.2 * u],
        7: [4.0 * u, 1.5 * u],
    }
    return patterns.get(line_type, [])


def _arc_span_tenths(beg_tenths: float, end_tenths: float, *, full_default: bool = True) -> float:
    span = (float(end_tenths) - float(beg_tenths)) % 3600.0
    if abs(span) < 1e-6 and (float(end_tenths) != float(beg_tenths) or full_default):
        span = 3600.0
    return span


def _arc_endpoint(cx: float, cy: float, rx: float, ry: float, angle_tenths: float) -> tuple[float, float]:
    rad = math.radians(float(angle_tenths) / 10.0)
    return (cx + rx * math.cos(rad), cy - ry * math.sin(rad))


def _arrowhead_points(
    p_from: Sequence[float],
    p_tip: Sequence[float],
    stroke_w: float,
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    dx = float(p_tip[0]) - float(p_from[0])
    dy = float(p_tip[1]) - float(p_from[1])
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return ([], (float(p_tip[0]), float(p_tip[1])))
    ux, uy = dx / dist, dy / dist
    arrow_len = min(dist * 0.45, max(float(stroke_w) * 3.8, 90.0))
    half_w = arrow_len * 0.42
    bx = float(p_tip[0]) - ux * arrow_len
    by = float(p_tip[1]) - uy * arrow_len
    px, py = -uy * half_w, ux * half_w
    tri = [
        (float(p_tip[0]), float(p_tip[1])),
        (bx + px, by + py),
        (bx - px, by - py),
    ]
    short_tip = (
        float(p_tip[0]) - ux * arrow_len * 0.65,
        float(p_tip[1]) - uy * arrow_len * 0.65,
    )
    return (tri, short_tip)


def _arc_arrowheads(
    item: dict[str, Any],
    stroke_w: float,
) -> tuple[list[list[tuple[float, float]]], float, float]:
    cx, cy = (float(v) for v in item["center"])
    rx, ry = (float(v) for v in item["radii"])
    beg = float(item.get("begang", 0.0))
    end = float(item.get("endang", 3600.0))
    span = _arc_span_tenths(beg, end, full_default=bool(item.get("full_circle", True)))
    line_ends = tuple(item.get("line_ends", (0, 0)))
    if span >= 3599.9 or (line_ends[0] != 1 and line_ends[1] != 1):
        return ([], beg, span)

    arc_len = math.radians(span / 10.0) * 0.5 * (max(1.0, abs(rx)) + max(1.0, abs(ry)))
    arrow_len = min(arc_len * 0.45, max(float(stroke_w) * 3.8, 90.0))
    if arrow_len < 1e-3:
        return ([], beg, span)
    half_w = arrow_len * 0.42

    def _end_arrow(angle_tenths: float, outward_sign: float) -> tuple[list[tuple[float, float]], float]:
        t = math.radians(angle_tenths / 10.0)
        px, py = _arc_endpoint(cx, cy, rx, ry, angle_tenths)
        # Screen-space (+y down) CCW arc tangent: dx/dt = -rx*sin(t), dy/dt = -ry*cos(t)
        tx = -rx * math.sin(t) * outward_sign
        ty = -ry * math.cos(t) * outward_sign
        speed = math.hypot(tx, ty)
        if speed < 1e-6:
            return ([], 0.0)
        ux, uy = tx / speed, ty / speed
        bx, by = px - ux * arrow_len, py - uy * arrow_len
        nx, ny = -uy * half_w, ux * half_w
        tri = [(px, py), (bx + nx, by + ny), (bx - nx, by - ny)]
        trim_tenths = math.degrees((0.65 * arrow_len) / speed) * 10.0
        return (tri, trim_tenths)

    tris: list[list[tuple[float, float]]] = []
    trim_beg = 0.0
    trim_end = 0.0
    if line_ends[0] == 1:
        tri0, tb = _end_arrow(beg, -1.0)
        if tri0:
            tris.append(tri0)
            trim_beg = tb
    if line_ends[1] == 1:
        tri1, te = _end_arrow(beg + span, 1.0)
        if tri1:
            tris.append(tri1)
            trim_end = te

    if span > trim_beg + trim_end + 5.0:
        return (tris, beg + trim_beg, span - trim_beg - trim_end)
    return (tris, beg, span)


def _shadow_params(item: dict[str, Any]) -> tuple[float, float, str, float] | None:
    sh = item.get("shadow")
    if not sh:
        return None
    if isinstance(sh, dict):
        return (
            float(sh.get("dx", 45.0)),
            float(sh.get("dy", 45.0)),
            str(sh.get("color", "#0B1220")),
            float(sh.get("alpha", 0.20)),
        )
    return (45.0, 45.0, "#0B1220", 0.20)


@lru_cache(maxsize=16)
def _load_image_rgba_bytes(image_path: str, transparent_outer_white: bool) -> tuple[bytes, int, int]:
    from PIL import Image

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Raster image not found: {image_path}")
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        if transparent_outer_white:
            w, h = rgba.size
            inset = min(14, max(0, min(w, h) // 12))
            if inset > 0 and w > 2 * inset and h > 2 * inset:
                rgba = rgba.crop((inset, inset, w - inset, h - inset))
            sw, sh = rgba.size
            px = rgba.load()
            visited = bytearray(sw * sh)
            stack: list[tuple[int, int]] = []
            for x in range(sw):
                stack.append((x, 0))
                stack.append((x, sh - 1))
            for y in range(sh):
                stack.append((0, y))
                stack.append((sw - 1, y))
            while stack:
                cx, cy = stack.pop()
                if cx < 0 or cx >= sw or cy < 0 or cy >= sh:
                    continue
                idx = cy * sw + cx
                if visited[idx]:
                    continue
                r, g, b, _a = px[cx, cy]
                if r > 225 and g > 225 and b > 225:
                    visited[idx] = 1
                    px[cx, cy] = (r, g, b, 0)
                    stack.extend(((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)))
            bbox = rgba.getbbox()
            if bbox is not None:
                rgba = rgba.crop(bbox)
        out = BytesIO()
        rgba.save(out, format="PNG")
        return (out.getvalue(), rgba.width, rgba.height)


def _fit_image_rect(
    bounds: Sequence[float],
    img_w: int,
    img_h: int,
    *,
    fit: str = "contain",
    pad: float = 0.0,
) -> tuple[float, float, float, float]:
    left, top, right, bottom = (float(v) for v in bounds)
    avail_x = left + pad
    avail_y = top + pad
    avail_w = max(1.0, (right - left) - 2.0 * pad)
    avail_h = max(1.0, (bottom - top) - 2.0 * pad)
    if fit == "stretch" or img_w <= 0 or img_h <= 0:
        return (avail_x, avail_y, avail_w, avail_h)
    ar = img_w / img_h
    box_ar = avail_w / avail_h
    if fit == "cover":
        if ar > box_ar:
            h = avail_h
            w = h * ar
        else:
            w = avail_w
            h = w / ar
    else:  # contain
        if ar > box_ar:
            w = avail_w
            h = w / ar
        else:
            h = avail_h
            w = h * ar
    ix = avail_x + (avail_w - w) / 2.0
    iy = avail_y + (avail_h - h) / 2.0
    return (ix, iy, w, h)


# ---------------------------------------------------------------------------
# SVG Renderer
# ---------------------------------------------------------------------------

def _svg_add_hatch_pattern(
    defs: ElementTree.Element,
    pat_id: str,
    interior: int,
    style: int,
    fill_hex: str,
    fill_alpha: float,
) -> None:
    size = 120.0
    if interior == 3 and style >= 7:
        size = 60.0
    pat = ElementTree.SubElement(defs, "pattern", {
        "id": pat_id,
        "patternUnits": "userSpaceOnUse",
        "width": f"{size:g}",
        "height": f"{size:g}",
    })
    stroke_attrs = {
        "stroke": fill_hex,
        "stroke-width": "8",
        "stroke-opacity": f"{fill_alpha:g}",
    }
    if interior == 3:  # Hatch
        kind = ((style - 1) % 6) + 1
        if kind in (1, 5):
            ElementTree.SubElement(pat, "line", {"x1": "0", "y1": f"{size/2:g}", "x2": f"{size:g}", "y2": f"{size/2:g}", **stroke_attrs})
        if kind in (2, 5):
            ElementTree.SubElement(pat, "line", {"x1": f"{size/2:g}", "y1": "0", "x2": f"{size/2:g}", "y2": f"{size:g}", **stroke_attrs})
        if kind in (3, 6):
            ElementTree.SubElement(pat, "line", {"x1": "0", "y1": f"{size:g}", "x2": f"{size:g}", "y2": "0", **stroke_attrs})
        if kind in (4, 6):
            ElementTree.SubElement(pat, "line", {"x1": "0", "y1": "0", "x2": f"{size:g}", "y2": f"{size:g}", **stroke_attrs})
    else:  # Pattern / stipple
        density = max(1, min(24, style))
        step = max(20.0, size / (1 + (density % 4)))
        r = max(5.0, min(18.0, 4.0 + density * 0.5))
        y = step / 2.0
        while y < size:
            x = step / 2.0
            while x < size:
                ElementTree.SubElement(pat, "circle", {
                    "cx": f"{x:g}", "cy": f"{y:g}", "r": f"{r:g}",
                    "fill": fill_hex, "fill-opacity": f"{fill_alpha:g}",
                })
                x += step
            y += step


def _svg_shape_path(
    item: dict[str, Any],
    *,
    beg_override: float | None = None,
    span_override: float | None = None,
) -> tuple[str, dict[str, str]] | None:
    itype = item["type"]
    if itype in {"rectangle", "rounded_rectangle"}:
        left, top, right, bottom = item["bounds"]
        attrs = {
            "x": f"{left:g}",
            "y": f"{top:g}",
            "width": f"{right - left:g}",
            "height": f"{bottom - top:g}",
        }
        r = float(item.get("radius", 0.0))
        if r > 0:
            r = min(r, (right - left) / 2.0, (bottom - top) / 2.0)
            attrs["rx"] = f"{r:g}"
            attrs["ry"] = f"{r:g}"
        return ("rect", attrs)
    if itype in {"polygon", "polyline", "line"}:
        tag = "polygon" if itype == "polygon" else "polyline"
        return (tag, {
            "points": " ".join(f"{x:g},{y:g}" for x, y in item["points"]),
            "stroke-linejoin": "round",
        })
    if itype == "ellipse":
        return ("ellipse", {
            "cx": f"{item['center'][0]:g}",
            "cy": f"{item['center'][1]:g}",
            "rx": f"{item['radii'][0]:g}",
            "ry": f"{item['radii'][1]:g}",
        })
    if itype in {"arc", "pieslice", "ellarc", "ellpie"}:
        cx, cy = (float(v) for v in item["center"])
        rx, ry = (float(v) for v in item["radii"])
        beg = float(item.get("begang", 0.0)) if beg_override is None else float(beg_override)
        end = float(item.get("endang", 3600.0))
        span = (
            _arc_span_tenths(beg, end, full_default=bool(item.get("full_circle", True)))
            if span_override is None
            else float(span_override)
        )
        if span >= 3599.9:
            return ("ellipse", {
                "cx": f"{cx:g}", "cy": f"{cy:g}", "rx": f"{rx:g}", "ry": f"{ry:g}",
            })
        x1, y1 = _arc_endpoint(cx, cy, rx, ry, beg)
        x2, y2 = _arc_endpoint(cx, cy, rx, ry, beg + span)
        large_arc = 1 if span > 1800.0 else 0
        if itype in {"pieslice", "ellpie"}:
            d = f"M {cx:g},{cy:g} L {x1:g},{y1:g} A {rx:g},{ry:g} 0 {large_arc} 0 {x2:g},{y2:g} Z"
        else:
            d = f"M {x1:g},{y1:g} A {rx:g},{ry:g} 0 {large_arc} 0 {x2:g},{y2:g}"
        return ("path", {"d": d})
    return None


def _svg_rich_text(group: ElementTree.Element, item: dict[str, Any]) -> None:
    spec = resolve_font_spec(
        font_id=item.get("font_id"),
        font_family=item.get("font_family", "DejaVu Sans"),
        bold=bool(item.get("bold", False)),
        italic=bool(item.get("italic", False)),
        effects=int(item.get("effects", 0)),
        underline=bool(item.get("underline", False)),
        boxed=bool(item.get("boxed", False)),
    )
    size_vdi = float(item.get("size", 240.0))
    line_spacing = float(item.get("line_spacing", 1.18))
    align = str(item.get("align", "left")).lower()
    has_bounds = "bounds" in item
    valign = str(item.get("valign", "top" if has_bounds else "baseline")).lower()
    wrap = bool(item.get("wrap", True))
    text_color = color(item.get("stroke", "black"))
    rotation = float(item.get("rotation", 0.0))

    if has_bounds:
        x0, y0, x1, y1 = (float(v) for v in item["bounds"])
        pad_x = float(item.get("pad_x", 0.0))
        pad_y = float(item.get("pad_y", 0.0))
        bx0, by0, bx1, by1 = x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y
        rot_cx, rot_cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    else:
        px, py = (float(v) for v in item.get("position", [0.0, 0.0]))
        mw = float(item.get("max_width", 12000.0))
        bx0 = px
        by0 = (py - size_vdi * 0.85) if valign == "baseline" else (py - size_vdi if valign == "bottom" else (py - size_vdi * 0.5 if valign == "middle" else py))
        bx1, by1 = px + mw, by0 + size_vdi * 1.2
        rot_cx, rot_cy = px, py

    box_w = max(1.0, bx1 - bx0)
    box_h = max(1.0, by1 - by0)

    target = group
    if abs(rotation) > 1e-6:
        target = ElementTree.SubElement(group, "g", {"transform": f"rotate({-rotation:g} {rot_cx:g} {rot_cy:g})"})

    if spec.boxed and has_bounds:
        box_attrs = {
            "x": f"{bx0:g}",
            "y": f"{by0:g}",
            "width": f"{box_w:g}",
            "height": f"{box_h:g}",
            "fill": color(item.get("box_fill", "none")),
            "stroke": color(item.get("box_stroke", text_color)),
            "stroke-width": str(item.get("box_width", 12)),
        }
        ElementTree.SubElement(target, "rect", box_attrs)

    # Rich multi-paragraph runs (bullets / mixed formatting)
    if "paragraphs" in item:
        y_cursor = by0 + size_vdi * 0.85
        for para in item["paragraphs"]:
            bullet = para.get("bullet")
            bullet_color = color(para.get("bullet_color", text_color))
            indent = float(para.get("indent", 0.0))
            if bullet:
                b_el = ElementTree.SubElement(target, "text", {
                    "x": f"{bx0:g}",
                    "y": f"{y_cursor:g}",
                    "font-family": spec.svg_family,
                    "font-size": f"{size_vdi * 0.9:g}",
                    "font-weight": "bold",
                    "fill": bullet_color,
                })
                b_el.text = str(bullet)
            runs = para.get("runs", [])
            _mw, _mh, full_text, spanned_lines = _layout_runs_lines(
                runs,
                font_id=item.get("font_id"),
                font_family=spec.pango_family,
                size_vdi=size_vdi,
                base_bold=spec.bold,
                base_italic=spec.italic,
                effects=int(item.get("effects", 0)),
                max_width_vdi=max(1.0, box_w - indent) if wrap else None,
                wrap=wrap,
                line_spacing=line_spacing,
            )
            run_spans: list[tuple[int, int, dict[str, Any]]] = []
            pos = 0
            for r in runs:
                rt = str(r.get("text", ""))
                run_spans.append((pos, pos + len(rt), r))
                pos += len(rt)
            for l_start, l_end, _line in spanned_lines:
                t_el = ElementTree.SubElement(target, "text", {
                    "x": f"{bx0 + indent:g}",
                    "y": f"{y_cursor:g}",
                    "font-family": spec.svg_family,
                    "font-size": f"{size_vdi:g}",
                })
                for rs, re_, r in run_spans:
                    ov_s = max(l_start, rs)
                    ov_e = min(l_end, re_)
                    if ov_e <= ov_s:
                        continue
                    seg = full_text[ov_s:ov_e]
                    sp = ElementTree.SubElement(t_el, "tspan", {
                        "fill": color(r.get("color", text_color)),
                        "font-weight": "bold" if r.get("bold", spec.bold) else "normal",
                        "font-style": "italic" if r.get("italic", spec.italic) else "normal",
                    })
                    sp.text = seg
                y_cursor += size_vdi * line_spacing
            y_cursor += float(para.get("space_after", 0.0))
        return

    _mw, total_h, lines = measure_text_metrics(
        str(item.get("text", "")),
        font_id=item.get("font_id"),
        font_family=spec.pango_family,
        size_vdi=size_vdi,
        bold=spec.bold,
        italic=spec.italic,
        max_width_vdi=box_w if (wrap and has_bounds) else item.get("max_width"),
        wrap=wrap,
        line_spacing=line_spacing,
    )
    step_y = size_vdi * line_spacing
    if not has_bounds:
        py = float(item.get("position", [0.0, 0.0])[1])
        if valign == "baseline":
            y_top_block = py - size_vdi * 0.85
            first_baseline = py
        elif valign == "middle":
            y_top_block = py - total_h / 2.0
            first_baseline = y_top_block + size_vdi * 0.85
        elif valign == "bottom":
            y_top_block = py - total_h
            first_baseline = y_top_block + size_vdi * 0.85
        else:
            y_top_block = py
            first_baseline = y_top_block + size_vdi * 0.85
        if spec.boxed:
            px_0 = float(item.get("position", [0.0, 0.0])[0])
            tx_0 = px_0 - _mw / 2.0 if align == "center" else (px_0 - _mw if align == "right" else px_0)
            ElementTree.SubElement(target, "rect", {
                "x": f"{tx_0:g}",
                "y": f"{y_top_block:g}",
                "width": f"{max(1.0, _mw):g}",
                "height": f"{max(1.0, total_h):g}",
                "fill": color(item.get("box_fill", "none")),
                "stroke": color(item.get("box_stroke", text_color)),
                "stroke-width": str(item.get("box_width", 12)),
            })
    elif valign == "middle":
        first_baseline = by0 + (box_h - total_h) / 2.0 + size_vdi * 0.85
    elif valign == "bottom":
        first_baseline = by1 - total_h + size_vdi * 0.85
    else:
        first_baseline = by0 + size_vdi * 0.85

    base_attrs: dict[str, str] = {
        "font-family": spec.svg_family,
        "font-size": f"{size_vdi:g}",
        "fill": text_color,
    }
    if spec.bold:
        base_attrs["font-weight"] = "bold"
    if spec.italic:
        base_attrs["font-style"] = "italic"
    alpha = item.get("alpha")
    if alpha is not None and float(alpha) < 1.0:
        base_attrs["fill-opacity"] = f"{float(alpha):g}"

    if align == "decimal":
        parts = [line.partition(".") for line in lines]
        stem_ws = [_measure_single_line(s, spec, size_vdi)[0] for s, _, _ in parts]
        tail_ws = [_measure_single_line(d + f, spec, size_vdi)[0] for _, d, f in parts]
        max_stem = max(stem_ws, default=0.0)
        max_tail = max(tail_ws, default=0.0)
        block_left = bx0 + max(0.0, (box_w - (max_stem + max_tail)) / 2.0)
        decimal_x = block_left + max_stem
        for idx, (line, stem_w) in enumerate(zip(lines, stem_ws)):
            y_pos = first_baseline + idx * step_y
            x_pos = decimal_x - stem_w
            t_el = ElementTree.SubElement(target, "text", {"x": f"{x_pos:g}", "y": f"{y_pos:g}", **base_attrs})
            t_el.text = line
            if spec.underline and line:
                lw = _measure_single_line(line, spec, size_vdi)[0]
                ElementTree.SubElement(target, "line", {
                    "x1": f"{x_pos:g}", "y1": f"{y_pos + 0.14 * size_vdi:g}",
                    "x2": f"{x_pos + lw:g}", "y2": f"{y_pos + 0.14 * size_vdi:g}",
                    "stroke": text_color, "stroke-width": f"{max(1.0, 0.06 * size_vdi):g}",
                })
        return

    anchor = "middle" if align == "center" else ("end" if align == "right" else "start")
    if "bounds" in item:
        x_pos = (bx0 + bx1) / 2.0 if align == "center" else (bx1 if align == "right" else bx0)
    else:
        x_pos = float(item["position"][0])

    for idx, line in enumerate(lines):
        y_pos = first_baseline + idx * step_y
        t_el = ElementTree.SubElement(target, "text", {
            "x": f"{x_pos:g}", "y": f"{y_pos:g}", "text-anchor": anchor, **base_attrs,
        })
        t_el.text = line
        if spec.underline and line:
            lw = _measure_single_line(line, spec, size_vdi)[0]
            ux0 = x_pos - lw / 2.0 if align == "center" else (x_pos - lw if align == "right" else x_pos)
            ElementTree.SubElement(target, "line", {
                "x1": f"{ux0:g}", "y1": f"{y_pos + 0.14 * size_vdi:g}",
                "x2": f"{ux0 + lw:g}", "y2": f"{y_pos + 0.14 * size_vdi:g}",
                "stroke": text_color, "stroke-width": f"{max(1.0, 0.06 * size_vdi):g}",
            })


def scene_to_svg(scene: Any, width: int = 1200) -> str:
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 16384:
        raise ValueError("SVG width must be an integer from 1 to 16384")
    height = max(1, round(width * scene.canvas["height"] / scene.canvas["width"]))
    root = ElementTree.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(width),
        "height": str(height),
        "viewBox": f"0 0 {scene.canvas['width']:g} {scene.canvas['height']:g}",
        "role": "img",
        "aria-label": scene.document.get("title", scene.document["id"]),
    })
    ElementTree.SubElement(root, "title").text = scene.document.get("title", scene.document["id"])
    defs_el: ElementTree.Element | None = None
    pat_counter = 0
    clip_counter = 0

    def _ensure_defs() -> ElementTree.Element:
        nonlocal defs_el
        if defs_el is None:
            defs_el = ElementTree.Element("defs")
            root.insert(1, defs_el)
        return defs_el

    bg = _scene_background(scene)
    if bg != "none":
        ElementTree.SubElement(root, "rect", {
            "x": "0", "y": "0", "width": str(scene.canvas["width"]),
            "height": str(scene.canvas["height"]), "fill": color(bg),
        })

    for item in scene.objects:
        paint = _paint(item)
        group = ElementTree.SubElement(root, "g", {"data-object-id": item["id"]})
        ElementTree.SubElement(group, "title").text = item["id"]
        itype = item["type"]

        # Drop shadow behind shape
        sh = _shadow_params(item)
        if sh is not None and itype != "text":
            dx, dy, sh_col, sh_alpha = sh
            shape = _svg_shape_path(item)
            if shape is not None:
                stag, sattrs = shape
                sh_attrs = {
                    **sattrs,
                    "transform": f"translate({dx:g} {dy:g})",
                    "fill": color(sh_col) if paint["fill"] != "none" else "none",
                    "fill-opacity": f"{sh_alpha:g}",
                    "stroke": color(sh_col) if paint["fill"] == "none" and paint["stroke"] != "none" else "none",
                    "stroke-opacity": f"{sh_alpha:g}",
                    "stroke-width": paint["stroke-width"],
                }
                ElementTree.SubElement(group, stag, sh_attrs)

        if itype == "mesh":
            points, fills = item["points"], item["fills"]
            index = 0
            while index < len(fills):
                end = index + 1
                while end < len(fills) and fills[end] == fills[index]:
                    end += 1
                chunks = []
                for triangle in range(index, end):
                    corners = points[3 * triangle:3 * triangle + 3]
                    chunks.append("M" + "L".join(f"{x:g},{y:g}" for x, y in corners) + "Z")
                ElementTree.SubElement(group, "path", {
                    "d": "".join(chunks), "fill": color(fills[index]), "stroke": "none",
                })
                index = end
            continue

        if itype == "image":
            bounds = item["bounds"]
            left, top, right, bottom = (float(v) for v in bounds)
            r = float(item.get("radius", 0.0))
            if paint["fill"] != "none" or paint["stroke"] != "none":
                r_attrs: dict[str, str] = {
                    "x": f"{left:g}", "y": f"{top:g}",
                    "width": f"{right - left:g}", "height": f"{bottom - top:g}",
                    **paint,
                }
                if r > 0:
                    rc = min(r, (right - left) / 2.0, (bottom - top) / 2.0)
                    r_attrs["rx"] = f"{rc:g}"
                    r_attrs["ry"] = f"{rc:g}"
                ElementTree.SubElement(group, "rect", r_attrs)
            png_bytes, iw, ih = _load_image_rgba_bytes(
                str(item["image_path"]),
                bool(item.get("transparent_outer_white", False)),
            )
            ix, iy, rw, rh = _fit_image_rect(
                bounds, iw, ih, fit=str(item.get("fit", "contain")), pad=float(item.get("pad", 0.0)),
            )
            b64 = base64.b64encode(png_bytes).decode("ascii")
            img_attrs: dict[str, str] = {
                "x": f"{ix:g}", "y": f"{iy:g}", "width": f"{rw:g}", "height": f"{rh:g}",
                "href": f"data:image/png;base64,{b64}",
                "preserveAspectRatio": "none",
            }
            clip_counter += 1
            clip_id = f"vdi-clip-{clip_counter}"
            cp = ElementTree.SubElement(_ensure_defs(), "clipPath", {"id": clip_id})
            clip_rect_attrs: dict[str, str] = {
                "x": f"{left:g}", "y": f"{top:g}",
                "width": f"{right - left:g}", "height": f"{bottom - top:g}",
            }
            if r > 0:
                rc = min(r, (right - left) / 2.0, (bottom - top) / 2.0)
                clip_rect_attrs["rx"] = f"{rc:g}"
                clip_rect_attrs["ry"] = f"{rc:g}"
            ElementTree.SubElement(cp, "rect", clip_rect_attrs)
            img_attrs["clip-path"] = f"url(#{clip_id})"
            ElementTree.SubElement(group, "image", img_attrs)
            continue

        if itype == "text":
            if _is_rich_text(item):
                _svg_rich_text(group, item)
            else:
                ElementTree.SubElement(group, "text", {
                    "x": str(item["position"][0]), "y": str(item["position"][1]),
                    "font-family": "sans-serif", "font-size": str(item["size"]),
                    "fill": color(item["stroke"]),
                }).text = item["text"]
            continue

        shape = _svg_shape_path(item)
        if shape is not None:
            stag, sattrs = shape
            # Handle VDI hatch/pattern fill
            fill_interior = int(item.get("fill_interior", 1))
            fill_style = int(item.get("fill_style", 1))
            if fill_interior in (2, 3) and paint["fill"] != "none":
                pat_counter += 1
                pat_id = f"vdi-pat-{pat_counter}"
                f_alpha = float(item.get("fill_alpha", item.get("alpha", 1.0)))
                _svg_add_hatch_pattern(_ensure_defs(), pat_id, fill_interior, fill_style, paint["fill"], f_alpha)
                paint["fill"] = f"url(#{pat_id})"
            if itype in {"arc", "ellarc", "line", "polyline"}:
                paint["fill"] = "none"

            dashes = _dash_array(item)
            if dashes:
                sattrs["stroke-dasharray"] = " ".join(f"{d:g}" for d in dashes)

            line_ends = tuple(item.get("line_ends", (0, 0)))
            if line_ends[0] == 2 or line_ends[1] == 2 or item.get("line_cap") == "round":
                sattrs["stroke-linecap"] = "round"

            # Arrowheads on line / polyline / arc / ellarc
            if itype in {"line", "polyline"} and (line_ends[0] == 1 or line_ends[1] == 1) and len(item["points"]) >= 2:
                pts = [list(p) for p in item["points"]]
                sw = float(item.get("width", 16))
                arrow_tris: list[list[tuple[float, float]]] = []
                if line_ends[0] == 1:
                    tri, new_p0 = _arrowhead_points(pts[1], pts[0], sw)
                    if tri:
                        arrow_tris.append(tri)
                        pts[0] = [new_p0[0], new_p0[1]]
                if line_ends[1] == 1:
                    tri, new_pn = _arrowhead_points(pts[-2], pts[-1], sw)
                    if tri:
                        arrow_tris.append(tri)
                        pts[-1] = [new_pn[0], new_pn[1]]
                sattrs["points"] = " ".join(f"{x:g},{y:g}" for x, y in pts)
                ElementTree.SubElement(group, stag, {**sattrs, **paint})
                for tri in arrow_tris:
                    ElementTree.SubElement(group, "polygon", {
                        "points": " ".join(f"{x:g},{y:g}" for x, y in tri),
                        "fill": paint["stroke"],
                        "stroke": "none",
                    })
            elif itype in {"arc", "ellarc"} and (line_ends[0] == 1 or line_ends[1] == 1):
                sw = float(item.get("width", 16))
                arrow_tris, draw_beg, draw_span = _arc_arrowheads(item, sw)
                arc_shape = _svg_shape_path(item, beg_override=draw_beg, span_override=draw_span)
                if arc_shape is not None:
                    stag, arc_attrs = arc_shape
                    if dashes:
                        arc_attrs["stroke-dasharray"] = " ".join(f"{d:g}" for d in dashes)
                    if "stroke-linecap" in sattrs:
                        arc_attrs["stroke-linecap"] = sattrs["stroke-linecap"]
                    sattrs = arc_attrs
                ElementTree.SubElement(group, stag, {**sattrs, **paint})
                for tri in arrow_tris:
                    ElementTree.SubElement(group, "polygon", {
                        "points": " ".join(f"{x:g},{y:g}" for x, y in tri),
                        "fill": paint["stroke"],
                        "stroke": "none",
                    })
            else:
                ElementTree.SubElement(group, stag, {**sattrs, **paint})

        label = _label(item)
        if label is not None:
            ElementTree.SubElement(group, "text", {
                "x": str(label["position"][0]), "y": str(label["position"][1]),
                "font-family": "sans-serif", "font-size": str(label["size"]),
                "fill": color(item["stroke"]), "text-anchor": "middle",
            }).text = label["text"]

    ElementTree.indent(root, space="  ")
    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def write_svg(scene: Any, path: Path | str, width: int = 1200) -> int:
    text = scene_to_svg(scene, width)
    Path(path).write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Cairo Renderer
# ---------------------------------------------------------------------------

def _cairo_rounded_rect(context: Any, left: float, top: float, w: float, h: float, radius: float) -> None:
    r = max(0.0, min(float(radius), w / 2.0, h / 2.0))
    if r <= 0.0:
        context.rectangle(left, top, w, h)
        return
    if hasattr(context, "new_sub_path"):
        context.new_sub_path()
    context.arc(left + w - r, top + r, r, -math.pi / 2.0, 0.0)
    context.arc(left + w - r, top + h - r, r, 0.0, math.pi / 2.0)
    context.arc(left + r, top + h - r, r, math.pi / 2.0, math.pi)
    context.arc(left + r, top + r, r, math.pi, 1.5 * math.pi)
    context.close_path()


def _cairo_emit_geometry(
    context: Any,
    item: dict[str, Any],
    *,
    override_points: Sequence[Sequence[float]] | None = None,
    beg_override: float | None = None,
    span_override: float | None = None,
) -> None:
    itype = item["type"]
    if itype in {"rectangle", "rounded_rectangle"}:
        left, top, right, bottom = item["bounds"]
        r = float(item.get("radius", 0.0))
        if r > 0:
            _cairo_rounded_rect(context, left, top, right - left, bottom - top, r)
        else:
            context.rectangle(left, top, right - left, bottom - top)
    elif itype in {"polygon", "polyline", "line"}:
        points = override_points if override_points is not None else item["points"]
        context.move_to(*points[0])
        for point in points[1:]:
            context.line_to(*point)
        if itype == "polygon":
            context.close_path()
    elif itype == "ellipse":
        context.save()
        context.translate(*item["center"])
        context.scale(*item["radii"])
        if hasattr(context, "new_sub_path"):
            context.new_sub_path()
        context.arc(0, 0, 1, 0, math.tau)
        context.restore()
    elif itype in {"arc", "pieslice", "ellarc", "ellpie"}:
        cx, cy = (float(v) for v in item["center"])
        rx, ry = (float(v) for v in item["radii"])
        beg = float(item.get("begang", 0.0)) if beg_override is None else float(beg_override)
        end = float(item.get("endang", 3600.0))
        span = (
            _arc_span_tenths(beg, end, full_default=bool(item.get("full_circle", True)))
            if span_override is None
            else float(span_override)
        )
        context.save()
        context.translate(cx, cy)
        context.scale(max(1e-3, rx), max(1e-3, ry))
        if hasattr(context, "new_sub_path"):
            context.new_sub_path()
        if itype in {"pieslice", "ellpie"} and span < 3599.9:
            context.move_to(0, 0)
        if span >= 3599.9:
            context.arc(0, 0, 1.0, 0.0, math.tau)
        else:
            context.arc_negative(
                0, 0, 1.0,
                -math.radians(beg / 10.0),
                -math.radians((beg + span) / 10.0),
            )
        if itype in {"pieslice", "ellpie"}:
            context.close_path()
        context.restore()


def _cairo_hatch_pattern(cairo: Any, interior: int, style: int, fill_val: Any, alpha: float) -> Any:
    tile_px = 16 if (interior == 3 and style >= 7) else 24
    tile_vdi = 60.0 if (interior == 3 and style >= 7) else 120.0
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, tile_px, tile_px)
    tctx = cairo.Context(surf)
    r, g, b, a = _rgba(fill_val, alpha)
    tctx.set_source_rgba(r, g, b, a)
    if interior == 3:
        tctx.set_line_width(max(1.5, tile_px / 12.0))
        kind = ((style - 1) % 6) + 1
        mid = tile_px / 2.0
        if kind in (1, 5):
            tctx.move_to(0, mid)
            tctx.line_to(tile_px, mid)
        if kind in (2, 5):
            tctx.move_to(mid, 0)
            tctx.line_to(mid, tile_px)
        if kind in (3, 6):
            tctx.move_to(0, tile_px)
            tctx.line_to(tile_px, 0)
            tctx.move_to(-tile_px, tile_px)
            tctx.line_to(tile_px, -tile_px)
            tctx.move_to(0, 2 * tile_px)
            tctx.line_to(2 * tile_px, 0)
        if kind in (4, 6):
            tctx.move_to(0, 0)
            tctx.line_to(tile_px, tile_px)
            tctx.move_to(-tile_px, 0)
            tctx.line_to(tile_px, 2 * tile_px)
            tctx.move_to(0, -tile_px)
            tctx.line_to(2 * tile_px, tile_px)
        tctx.stroke()
    else:
        density = max(1, min(24, style))
        step = max(4, tile_px // (1 + (density % 4)))
        rad = max(1.2, min(4.0, 0.8 + density * 0.12))
        for y in range(step // 2, tile_px, step):
            for x in range(step // 2, tile_px, step):
                tctx.new_sub_path()
                tctx.arc(x, y, rad, 0, math.tau)
                tctx.fill()
    pat = cairo.SurfacePattern(surf)
    pat.set_extend(cairo.Extend.REPEAT)
    mat = cairo.Matrix()
    mat.scale(tile_px / tile_vdi, tile_px / tile_vdi)
    pat.set_matrix(mat)
    return pat


def _cairo_draw_rich_text(context: Any, item: dict[str, Any]) -> None:
    spec = resolve_font_spec(
        font_id=item.get("font_id"),
        font_family=item.get("font_family", "DejaVu Sans"),
        bold=bool(item.get("bold", False)),
        italic=bool(item.get("italic", False)),
        effects=int(item.get("effects", 0)),
        underline=bool(item.get("underline", False)),
        boxed=bool(item.get("boxed", False)),
    )
    size_vdi = float(item.get("size", 240.0))
    line_spacing = float(item.get("line_spacing", 1.18))
    align = str(item.get("align", "left")).lower()
    has_bounds = "bounds" in item
    valign = str(item.get("valign", "top" if has_bounds else "baseline")).lower()
    wrap = bool(item.get("wrap", True))
    text_color = item.get("stroke", "black")
    alpha = float(item.get("alpha", 1.0))
    rotation = float(item.get("rotation", 0.0))

    if has_bounds:
        x0, y0, x1, y1 = (float(v) for v in item["bounds"])
        pad_x = float(item.get("pad_x", 0.0))
        pad_y = float(item.get("pad_y", 0.0))
        bx0, by0, bx1, by1 = x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y
        rot_cx, rot_cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    else:
        px, py = (float(v) for v in item.get("position", [0.0, 0.0]))
        mw = float(item.get("max_width", 12000.0))
        bx0 = px
        by0 = (py - size_vdi * 0.85) if valign == "baseline" else (py - size_vdi if valign == "bottom" else (py - size_vdi * 0.5 if valign == "middle" else py))
        bx1, by1 = px + mw, by0 + size_vdi * 1.2
        rot_cx, rot_cy = px, py

    box_w = max(1.0, bx1 - bx0)
    box_h = max(1.0, by1 - by0)

    use_pango = _pango_available()
    if use_pango:
        Pango, PangoCairo = _import_pango()

    def _draw_segment(x_left: float, y_top_or_base: float, seg: str, *, seg_bold: bool, seg_italic: bool, seg_col: Any, seg_size: float = size_vdi, from_top: bool = True) -> float:
        _set_cairo_color(context, seg_col, alpha)
        if use_pango:
            layout = PangoCairo.create_layout(context)
            desc = Pango.FontDescription(spec.pango_family)
            desc.set_weight(Pango.Weight.BOLD if seg_bold else Pango.Weight.NORMAL)
            desc.set_style(Pango.Style.ITALIC if seg_italic else Pango.Style.NORMAL)
            desc.set_absolute_size(max(1.0, seg_size) * Pango.SCALE)
            layout.set_font_description(desc)
            layout.set_text(seg, -1)
            _, logical = layout.get_extents()
            w = (logical.width / Pango.SCALE) if seg else 0.0
            y_draw = y_top_or_base if from_top else (y_top_or_base - seg_size * 0.85)
            context.move_to(x_left, y_draw)
            PangoCairo.show_layout(context, layout)
            return float(w)
        else:
            import cairo
            slant = cairo.FontSlant.ITALIC if seg_italic else cairo.FontSlant.NORMAL
            weight = cairo.FontWeight.BOLD if seg_bold else cairo.FontWeight.NORMAL
            context.select_font_face(spec.pango_family, slant, weight)
            context.set_font_size(seg_size)
            y_base = (y_top_or_base + seg_size * 0.85) if from_top else y_top_or_base
            context.move_to(x_left, y_base)
            context.show_text(seg)
            ext = context.text_extents(seg)
            return float(ext.x_advance)

    context.save()
    if abs(rotation) > 1e-6:
        context.translate(rot_cx, rot_cy)
        context.rotate(-math.radians(rotation))
        context.translate(-rot_cx, -rot_cy)

    if spec.boxed and has_bounds:
        context.rectangle(bx0, by0, box_w, box_h)
        if item.get("box_fill", "none") != "none":
            _set_cairo_color(context, item["box_fill"], alpha)
            context.fill_preserve()
        _set_cairo_color(context, item.get("box_stroke", text_color), alpha)
        context.set_line_width(float(item.get("box_width", 12.0)))
        context.stroke()

    if "paragraphs" in item:
        y_top = by0
        for para in item["paragraphs"]:
            bullet = para.get("bullet")
            bullet_color = para.get("bullet_color", text_color)
            indent = float(para.get("indent", 0.0))
            if bullet:
                _draw_segment(bx0, y_top + size_vdi * 0.06, str(bullet), seg_bold=True, seg_italic=False, seg_col=bullet_color, seg_size=size_vdi * 0.9, from_top=True)
            runs = para.get("runs", [])
            _mw, _mh, full_text, spanned_lines = _layout_runs_lines(
                runs,
                font_id=item.get("font_id"),
                font_family=spec.pango_family,
                size_vdi=size_vdi,
                base_bold=spec.bold,
                base_italic=spec.italic,
                effects=int(item.get("effects", 0)),
                max_width_vdi=max(1.0, box_w - indent) if wrap else None,
                wrap=wrap,
                line_spacing=line_spacing,
            )
            run_spans: list[tuple[int, int, dict[str, Any]]] = []
            pos = 0
            for r in runs:
                rt = str(r.get("text", ""))
                run_spans.append((pos, pos + len(rt), r))
                pos += len(rt)
            for l_start, l_end, _line in spanned_lines:
                x_cur = bx0 + indent
                for rs, re_, r in run_spans:
                    ov_s = max(l_start, rs)
                    ov_e = min(l_end, re_)
                    if ov_e <= ov_s:
                        continue
                    seg = full_text[ov_s:ov_e]
                    adv = _draw_segment(
                        x_cur, y_top, seg,
                        seg_bold=bool(r.get("bold", spec.bold)),
                        seg_italic=bool(r.get("italic", spec.italic)),
                        seg_col=r.get("color", text_color),
                        from_top=True,
                    )
                    x_cur += adv
                y_top += size_vdi * line_spacing
            y_top += float(para.get("space_after", 0.0))
        context.restore()
        return

    _mw, total_h, lines = measure_text_metrics(
        str(item.get("text", "")),
        font_id=item.get("font_id"),
        font_family=spec.pango_family,
        size_vdi=size_vdi,
        bold=spec.bold,
        italic=spec.italic,
        max_width_vdi=box_w if (wrap and has_bounds) else item.get("max_width"),
        wrap=wrap,
        line_spacing=line_spacing,
    )
    step_y = size_vdi * line_spacing
    if not has_bounds:
        py = float(item.get("position", [0.0, 0.0])[1])
        if valign == "baseline":
            y_start = py - size_vdi * 0.85
        elif valign == "middle":
            y_start = py - total_h / 2.0
        elif valign == "bottom":
            y_start = py - total_h
        else:
            y_start = py
        if spec.boxed:
            px_0 = float(item.get("position", [0.0, 0.0])[0])
            tx_0 = px_0 - _mw / 2.0 if align == "center" else (px_0 - _mw if align == "right" else px_0)
            context.rectangle(tx_0, y_start, max(1.0, _mw), max(1.0, total_h))
            if item.get("box_fill", "none") != "none":
                _set_cairo_color(context, item["box_fill"], alpha)
                context.fill_preserve()
            _set_cairo_color(context, item.get("box_stroke", text_color), alpha)
            context.set_line_width(float(item.get("box_width", 12.0)))
            context.stroke()
    elif valign == "middle":
        y_start = by0 + (box_h - total_h) / 2.0
    elif valign == "bottom":
        y_start = by1 - total_h
    else:
        y_start = by0

    if align == "decimal":
        parts = [line.partition(".") for line in lines]
        stem_ws = [_measure_single_line(s, spec, size_vdi)[0] for s, _, _ in parts]
        tail_ws = [_measure_single_line(d + f, spec, size_vdi)[0] for _, d, f in parts]
        max_stem = max(stem_ws, default=0.0)
        max_tail = max(tail_ws, default=0.0)
        block_left = bx0 + max(0.0, (box_w - (max_stem + max_tail)) / 2.0)
        decimal_x = block_left + max_stem
        for idx, (line, stem_w) in enumerate(zip(lines, stem_ws)):
            y_top = y_start + idx * step_y
            x_left = decimal_x - stem_w
            w_drawn = _draw_segment(x_left, y_top, line, seg_bold=spec.bold, seg_italic=spec.italic, seg_col=text_color, from_top=True)
            if spec.underline and line:
                y_u = y_top + size_vdi * 0.99
                _set_cairo_color(context, text_color, alpha)
                context.set_line_width(max(1.0, 0.06 * size_vdi))
                context.move_to(x_left, y_u)
                context.line_to(x_left + w_drawn, y_u)
                context.stroke()
        context.restore()
        return

    for idx, line in enumerate(lines):
        y_top = y_start + idx * step_y
        lw = _measure_single_line(line, spec, size_vdi)[0]
        if "bounds" in item:
            if align == "center":
                x_left = bx0 + (box_w - lw) / 2.0
            elif align == "right":
                x_left = bx1 - lw
            else:
                x_left = bx0
        else:
            px = float(item["position"][0])
            x_left = px - lw / 2.0 if align == "center" else (px - lw if align == "right" else px)
        _draw_segment(x_left, y_top, line, seg_bold=spec.bold, seg_italic=spec.italic, seg_col=text_color, from_top=True)
        if spec.underline and line:
            y_u = y_top + size_vdi * 0.99
            _set_cairo_color(context, text_color, alpha)
            context.set_line_width(max(1.0, 0.06 * size_vdi))
            context.move_to(x_left, y_u)
            context.line_to(x_left + lw, y_u)
            context.stroke()

    context.restore()


def draw_cairo(context: Any, scene: Any, width: int, height: int, highlight_ids: Sequence[str] = ()) -> tuple[float, float, float]:
    import cairo

    scale = min(width / scene.canvas["width"], height / scene.canvas["height"])
    offset_x = (width - scene.canvas["width"] * scale) / 2
    offset_y = (height - scene.canvas["height"] * scale) / 2
    context.save()
    bg = _scene_background(scene)
    if bg != "none":
        if color(bg).lower() == "#ffffff":
            context.set_source_rgb(1, 1, 1)
        else:
            _set_cairo_color(context, bg)
        context.paint()
    context.translate(offset_x, offset_y)
    context.scale(scale, scale)
    context.set_line_join(cairo.LineJoin.ROUND)

    for item in scene.objects:
        itype = item["type"]

        if itype == "mesh":
            points, fills = item["points"], item["fills"]
            index = 0
            while index < len(fills):
                end = index + 1
                while end < len(fills) and fills[end] == fills[index]:
                    end += 1
                rgb = color(fills[index]).lstrip("#")
                context.set_source_rgb(*(int(rgb[offset:offset + 2], 16) / 255 for offset in (0, 2, 4)))
                for triangle in range(index, end):
                    corners = points[3 * triangle:3 * triangle + 3]
                    context.move_to(*corners[0])
                    context.line_to(*corners[1])
                    context.line_to(*corners[2])
                    context.close_path()
                context.fill()
                index = end
            continue

        if itype == "image":
            bounds = item["bounds"]
            left, top, right, bottom = (float(v) for v in bounds)
            r = float(item.get("radius", 0.0))
            sh = _shadow_params(item)
            if sh is not None:
                dx, dy, sh_col, sh_alpha = sh
                _cairo_rounded_rect(context, left + dx, top + dy, right - left, bottom - top, r)
                _set_cairo_color(context, sh_col, sh_alpha)
                context.fill()
            fill_val = item.get("fill", "none")
            stroke_val = item.get("stroke", "none")
            if fill_val != "none" or stroke_val != "none":
                _cairo_rounded_rect(context, left, top, right - left, bottom - top, r)
                if fill_val != "none":
                    _set_cairo_color(context, fill_val, float(item.get("fill_alpha", item.get("alpha", 1.0))))
                    context.fill_preserve()
                if stroke_val != "none":
                    _set_cairo_color(context, stroke_val, float(item.get("stroke_alpha", item.get("alpha", 1.0))))
                    context.set_line_width(float(item.get("width", 12.0)))
                    context.stroke()
                else:
                    context.new_path()
            png_bytes, iw, ih = _load_image_rgba_bytes(
                str(item["image_path"]),
                bool(item.get("transparent_outer_white", False)),
            )
            ix, iy, rw, rh = _fit_image_rect(
                bounds, iw, ih, fit=str(item.get("fit", "contain")), pad=float(item.get("pad", 0.0)),
            )
            surf = cairo.ImageSurface.create_from_png(BytesIO(png_bytes))
            context.save()
            if r > 0:
                _cairo_rounded_rect(context, left, top, right - left, bottom - top, r)
            else:
                context.rectangle(left, top, right - left, bottom - top)
            context.clip()
            context.translate(ix, iy)
            context.scale(rw / max(1, surf.get_width()), rh / max(1, surf.get_height()))
            context.set_source_surface(surf, 0, 0)
            context.paint()
            context.restore()
            continue

        if itype == "text":
            if _is_rich_text(item):
                _cairo_draw_rich_text(context, item)
            else:
                context.select_font_face("sans-serif")
                context.set_font_size(item["size"])
                context.move_to(*item["position"])
                rgb = color(item["stroke"]).lstrip("#")
                context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
                context.show_text(item["text"])
            continue

        # Drop shadow behind vector shape
        sh = _shadow_params(item)
        if sh is not None:
            dx, dy, sh_col, sh_alpha = sh
            context.save()
            context.translate(dx, dy)
            _cairo_emit_geometry(context, item)
            if item.get("fill", "none") != "none" and itype not in {"arc", "ellarc", "line", "polyline"}:
                _set_cairo_color(context, sh_col, sh_alpha)
                context.fill()
            elif item.get("stroke", "none") != "none":
                _set_cairo_color(context, sh_col, sh_alpha)
                context.set_line_width(float(item.get("width", 20)))
                context.stroke()
            else:
                context.new_path()
            context.restore()

        # Prepare line / polyline / arc / ellarc arrowheads if present
        override_pts = None
        arc_beg_override = None
        arc_span_override = None
        arrow_tris: list[list[tuple[float, float]]] = []
        line_ends = tuple(item.get("line_ends", (0, 0)))
        if itype in {"line", "polyline"} and (line_ends[0] == 1 or line_ends[1] == 1) and len(item["points"]) >= 2:
            pts = [list(p) for p in item["points"]]
            sw = float(item.get("width", 16))
            if line_ends[0] == 1:
                tri, new_p0 = _arrowhead_points(pts[1], pts[0], sw)
                if tri:
                    arrow_tris.append(tri)
                    pts[0] = [new_p0[0], new_p0[1]]
            if line_ends[1] == 1:
                tri, new_pn = _arrowhead_points(pts[-2], pts[-1], sw)
                if tri:
                    arrow_tris.append(tri)
                    pts[-1] = [new_pn[0], new_pn[1]]
            override_pts = pts
        elif itype in {"arc", "ellarc"} and (line_ends[0] == 1 or line_ends[1] == 1):
            sw = float(item.get("width", 16))
            arrow_tris, arc_beg_override, arc_span_override = _arc_arrowheads(item, sw)

        _cairo_emit_geometry(
            context,
            item,
            override_points=override_pts,
            beg_override=arc_beg_override,
            span_override=arc_span_override,
        )

        fill_val = item.get("fill", "none")
        fill_interior = int(item.get("fill_interior", 1))
        if itype in {"arc", "ellarc", "line", "polyline"} or fill_interior == 0:
            fill_val = "none"

        if fill_val != "none":
            f_alpha = float(item.get("fill_alpha", item.get("alpha", 1.0)))
            if fill_interior in (2, 3) and hasattr(cairo, "SurfacePattern"):
                pat = _cairo_hatch_pattern(cairo, fill_interior, int(item.get("fill_style", 1)), fill_val, f_alpha)
                context.set_source(pat)
            else:
                _set_cairo_color(context, fill_val, f_alpha)
            context.fill_preserve()

        stroke_val = item.get("stroke", "none")
        if stroke_val != "none":
            s_alpha = float(item.get("stroke_alpha", item.get("alpha", 1.0)))
            _set_cairo_color(context, stroke_val, s_alpha)
            context.set_line_width(item.get("width", 20))
            dashes = _dash_array(item)
            if dashes and hasattr(context, "set_dash"):
                context.set_dash(dashes)
            cap_needed = line_ends[0] == 2 or line_ends[1] == 2 or item.get("line_cap") == "round"
            if cap_needed and hasattr(context, "set_line_cap") and hasattr(cairo, "LineCap"):
                context.set_line_cap(cairo.LineCap.ROUND)
            context.stroke()
            if dashes and hasattr(context, "set_dash"):
                context.set_dash([])
            if cap_needed and hasattr(context, "set_line_cap") and hasattr(cairo, "LineCap"):
                context.set_line_cap(cairo.LineCap.BUTT)
            for tri in arrow_tris:
                context.move_to(*tri[0])
                context.line_to(*tri[1])
                context.line_to(*tri[2])
                context.close_path()
                _set_cairo_color(context, stroke_val, s_alpha)
                context.fill()
        else:
            context.new_path()

        if item["id"] in highlight_ids:
            left, top, right, bottom = _highlight_bounds(item)
            context.set_source_rgb(0.9, 0.1, 0.1)
            context.set_line_width(max(item["width"] * 2, 50 / scale))
            context.set_dash([120, 60])
            context.rectangle(left - 30, top - 30, right - left + 60, bottom - top + 60)
            context.stroke()
            context.set_dash([])

        label = _label(item)
        if label is not None:
            context.select_font_face("sans-serif")
            context.set_font_size(label["size"])
            extents = context.text_extents(label["text"])
            context.move_to(
                label["position"][0] - extents.width / 2 - extents.x_bearing,
                label["position"][1],
            )
            rgb = color(item["stroke"]).lstrip("#")
            context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
            context.show_text(label["text"])

    context.restore()
    return scale, offset_x, offset_y


def _highlight_bounds(item: dict[str, Any]) -> tuple[float, float, float, float]:
    from .geometry import object_bounds

    bounds = object_bounds(item)
    return bounds.left, bounds.top, bounds.right, bounds.bottom


def write_png(scene: Any, path: Path | str, width: int = 1200, height: int | None = None) -> int:
    try:
        import cairo
    except ImportError as error:
        raise RuntimeError("PNG output requires the optional PyGObject Cairo integration") from error
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 16384:
        raise ValueError("PNG width must be an integer from 1 to 16384")
    if height is None:
        height = max(1, round(width * scene.canvas["height"] / scene.canvas["width"]))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_cairo(cairo.Context(surface), scene, width, height)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    surface.write_to_png(str(out_path))
    return out_path.stat().st_size


def render_pil(scene: Any, width: int = 1200, height: int | None = None):
    try:
        import cairo
    except ImportError as error:
        raise RuntimeError("PIL rendering requires the optional PyGObject Cairo integration") from error
    from PIL import Image

    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 16384:
        raise ValueError("Render width must be an integer from 1 to 16384")
    if height is None:
        height = max(1, round(width * scene.canvas["height"] / scene.canvas["width"]))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_cairo(cairo.Context(surface), scene, width, height)
    buf = BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    with Image.open(buf) as im:
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        return bg


def write_jpg(scene: Any, path: Path | str, width: int = 1200, height: int | None = None, quality: int = 94) -> int:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im = render_pil(scene, width=width, height=height)
    im.save(out_path, format="JPEG", quality=int(quality), subsampling=0, optimize=True)
    return out_path.stat().st_size

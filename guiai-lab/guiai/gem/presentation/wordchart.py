"""Clean-Room GEM WordChart Engine (`WordChartDoc`, 4-Zone Model, 11 Templates & Locator Borders).

Inspired by Digital Research GEM WordChart (Aug 1987) atop `DrawPlusCanvas` and pure-Python
`PresentationRenderer` — zero external Office/LibreOffice dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from guiai.gem import vdi

from .draw_plus import DrawPlusCanvas
from .palette import (
    DARK_BOTANICAL_THEME,
    GOLD,
    JADE,
    LIGHT_DIVIDER_LINE,
    MARGIN,
    OBSIDIAN,
    RUBY,
    STONE,
    WHITE,
    PresentationTheme,
    pt_to_vdi,
    theme_for_sister,
)
from .renderer import PresentationRenderer

ZONE_MAX_ROWS: dict[str, int] = {
    "title": 2,
    "column_head": 1,
    "text_body": 26,
    "footer": 2,
}

STANDARD_POINT_SIZES: tuple[float, ...] = (14.0, 20.0, 28.0, 36.0, 72.0)

STYLE_FLAGS: dict[str, int] = {
    "normal": 0x00,
    "bold": 0x01,
    "italic": 0x04,
    "underline": 0x08,
    "boxed": 0x40,
}

BULLET_MARKERS: dict[str, str] = {
    "circle": "●",
    "diamond": "◆",
    "square": "■",
    "arrow": "➔",
    "check": "✔",
    "dash": "—",
    "none": "",
}

NUMBERING_STYLES: set[str] = {"arabic", "number", "roman", "alpha"}
VALID_ALIGNMENTS: set[str] = {"left", "center", "right", "decimal"}

VALID_TEMPLATES: tuple[str, ...] = (
    "column_1",
    "column_2",
    "column_3",
    "column_4",
    "outline_2",
    "outline_3",
    "outline_4",
    "freeform",
    "hero_obsidian",
    "scorecard_2x2",
    "pillar_3col",
)

_DECIMAL_TOKEN_RE = re.compile(
    r"^\s*[+-]?\s*[$€£¥]?\s*[+-]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\s*$"
)


def validate_decimal_token(token: str) -> bool:
    """Validate whether `token` conforms to GEM WordChart Decimal numeric formatting."""
    return bool(_DECIMAL_TOKEN_RE.match(str(token)))


def to_roman(num: int) -> str:
    """Convert positive integer to uppercase Roman numeral."""
    val = max(1, int(num))
    numerals = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    parts: list[str] = []
    for unit, glyph in numerals:
        while val >= unit:
            parts.append(glyph)
            val -= unit
    return "".join(parts)


def to_alpha(num: int) -> str:
    """Convert 1-based integer to alphabetic index (A, B, ..., Z, AA)."""
    val = max(1, int(num))
    out: list[str] = []
    while val > 0:
        val, rem = divmod(val - 1, 26)
        out.append(chr(ord("A") + rem))
    return "".join(reversed(out))


def _format_bullet_prefix(style: str, idx: int) -> str:
    key = str(style or "none").strip().lower()
    if key in ("arabic", "number"):
        return f"{idx}."
    if key == "roman":
        return f"{to_roman(idx)}."
    if key == "alpha":
        return f"{to_alpha(idx)}."
    marker = BULLET_MARKERS.get(key, "")
    return marker


def _normalize_rows(val: Sequence[str] | str | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val] if val else []
    return [str(x) for x in val]


def _parse_style_flags(spec: Any) -> tuple[bool, bool, bool, bool, int]:
    """Parse combinable style flags from dict, bitmask, or string/sequence."""
    if spec is None:
        return (False, False, False, False, 0)
    if isinstance(spec, int) and not isinstance(spec, bool):
        b = bool(spec & 0x01)
        it = bool(spec & 0x04)
        u = bool(spec & 0x08)
        bx = bool(spec & 0x40)
        return (b, it, u, bx, int(spec))
    if isinstance(spec, Mapping):
        b = bool(spec.get("bold", False))
        it = bool(spec.get("italic", False))
        u = bool(spec.get("underline", False))
        bx = bool(spec.get("boxed", False))
        mask = int(spec.get("effects", 0))
    else:
        tokens = [str(spec)] if isinstance(spec, str) else [str(t) for t in spec]
        lowered = {t.strip().lower() for t in tokens}
        b = "bold" in lowered
        it = "italic" in lowered
        u = "underline" in lowered
        bx = "boxed" in lowered
        mask = 0
    if b:
        mask |= STYLE_FLAGS["bold"]
    if it:
        mask |= STYLE_FLAGS["italic"]
    if u:
        mask |= STYLE_FLAGS["underline"]
    if bx:
        mask |= STYLE_FLAGS["boxed"]
    return (b, it, u, bx, mask)


@dataclass
class LineBoxSpec:
    """Line and box rules for WordChart fields (box, rule above/below, match width)."""

    box: bool = False
    box_width: float = 12.0
    box_fill: str = "none"
    box_stroke: str | None = None
    rule_above: bool = False
    rule_below: bool = False
    rule_match: str = "match_field"
    rule_width: float = 12.0

    @classmethod
    def from_obj(cls, obj: LineBoxSpec | Mapping[str, Any] | None) -> LineBoxSpec:
        if isinstance(obj, cls):
            return obj
        if not isinstance(obj, Mapping):
            return cls()
        return cls(
            box=bool(obj.get("box", False)),
            box_width=float(obj.get("box_width", 12.0)),
            box_fill=str(obj.get("box_fill", "none")),
            box_stroke=obj.get("box_stroke"),
            rule_above=bool(obj.get("rule_above", False)),
            rule_below=bool(obj.get("rule_below", False)),
            rule_match=str(obj.get("rule_match", "match_field")),
            rule_width=float(obj.get("rule_width", 12.0)),
        )


@dataclass
class TextStyleSpec:
    """Typography specification for a WordChart zone or column."""

    font_id: int | None = None
    font_family: str | None = None
    point_size: float = 14.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    boxed: bool = False
    align: str = "left"
    color: str | None = None
    line_spacing: float = 1.18
    bullet: str = "none"

    def __post_init__(self) -> None:
        al = str(self.align).strip().lower()
        if al not in VALID_ALIGNMENTS:
            raise ValueError(f"Invalid WordChart alignment {self.align!r}; expected {sorted(VALID_ALIGNMENTS)}")
        self.align = al
        if float(self.point_size) <= 0:
            raise ValueError(f"point_size must be positive, got {self.point_size!r}")

    def effects_bitmask(self) -> int:
        mask = 0
        if self.bold:
            mask |= STYLE_FLAGS["bold"]
        if self.italic:
            mask |= STYLE_FLAGS["italic"]
        if self.underline:
            mask |= STYLE_FLAGS["underline"]
        if self.boxed:
            mask |= STYLE_FLAGS["boxed"]
        return mask


@dataclass
class TextZone:
    """One vertical WordChart zone (`title`, `column_head`, `text_body`, or `footer`)."""

    name: str
    max_rows: int
    rows: list[str] = field(default_factory=list)
    columns: list[list[str]] = field(default_factory=list)
    style: TextStyleSpec = field(default_factory=TextStyleSpec)
    column_styles: list[TextStyleSpec] = field(default_factory=list)
    line_box: LineBoxSpec = field(default_factory=LineBoxSpec)
    deleted: bool = False
    _structural_min_rows: int = 1

    def add_row(self, text: str, *, col: int = 0) -> None:
        """Append a row while enforcing WordChart zone row limits."""
        if self.deleted:
            self.restore_zone([str(text)])
            return
        if self.columns and 0 <= col < len(self.columns):
            if len(self.columns[col]) >= self.max_rows:
                raise ValueError(f"Zone {self.name!r} column {col} exceeds max_rows={self.max_rows}")
            self.columns[col].append(str(text))
            return
        if len(self.rows) >= self.max_rows:
            raise ValueError(f"Zone {self.name!r} exceeds max_rows={self.max_rows}")
        self.rows.append(str(text))

    def insert_row(self, index: int, text: str) -> None:
        """Insert a row at `index` while enforcing `max_rows`."""
        if len(self.rows) >= self.max_rows:
            raise ValueError(f"Zone {self.name!r} exceeds max_rows={self.max_rows}")
        self.rows.insert(index, str(text))

    def delete_row(self, index: int = -1) -> str:
        """Delete a row while protecting the last structural row in the zone."""
        if len(self.rows) <= self._structural_min_rows:
            raise ValueError(
                f"Cannot delete last structural row in zone {self.name!r}; use restore_zone() to reset"
            )
        return self.rows.pop(index)

    def restore_zone(self, default_rows: Sequence[str] = ("",)) -> None:
        """Explicitly restore a cleared or deleted structural zone."""
        self.deleted = False
        self.rows = [str(r) for r in default_rows][: self.max_rows]


@dataclass(frozen=True)
class WordChartTemplate:
    """Preset geometry and formatting definition for a WordChart template."""

    name: str
    num_cols: int
    dark_mode: bool = False
    cards: bool = False
    grid_2x2: bool = False
    outline_levels: int = 0
    freeform: bool = False


TEMPLATE_REGISTRY: dict[str, WordChartTemplate] = {
    "column_1": WordChartTemplate("column_1", num_cols=1),
    "column_2": WordChartTemplate("column_2", num_cols=2),
    "column_3": WordChartTemplate("column_3", num_cols=3),
    "column_4": WordChartTemplate("column_4", num_cols=4),
    "outline_2": WordChartTemplate("outline_2", num_cols=1, outline_levels=2),
    "outline_3": WordChartTemplate("outline_3", num_cols=1, outline_levels=3),
    "outline_4": WordChartTemplate("outline_4", num_cols=1, outline_levels=4),
    "freeform": WordChartTemplate("freeform", num_cols=1, freeform=True),
    "hero_obsidian": WordChartTemplate("hero_obsidian", num_cols=1, dark_mode=True, cards=False),
    "scorecard_2x2": WordChartTemplate("scorecard_2x2", num_cols=2, cards=True, grid_2x2=True),
    "pillar_3col": WordChartTemplate("pillar_3col", num_cols=3, cards=True),
}


def _is_color_zero_rect(obj: Mapping[str, Any]) -> bool:
    if obj.get("type") != "rectangle":
        return False
    stroke = str(obj.get("stroke", "")).strip().lower()
    fill = str(obj.get("fill", "")).strip().lower()
    return stroke in {"white", "#ffffff"} or fill in {"white", "#ffffff"}


def _is_full_canvas_bg_bar(obj: Mapping[str, Any], canvas_w: float, canvas_h: float) -> bool:
    if obj.get("type") != "rectangle" or "bounds" not in obj:
        return False
    fill = str(obj.get("fill", "")).strip().lower()
    stroke = str(obj.get("stroke", "")).strip().lower()
    if fill in {"", "none"} or stroke not in {"", "none"}:
        return False
    b = [float(v) for v in obj["bounds"]]
    x0, y0, x1, y1 = min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3])
    return (
        abs(x0) <= 1.0
        and abs(y0) <= 1.0
        and abs(x1 - canvas_w) <= 2.0
        and abs(y1 - canvas_h) <= 2.0
    )


def _load_border_gem(
    path: Path | str,
    canvas_w: float,
    canvas_h: float,
) -> tuple[list[float], list[dict[str, Any]]]:
    """Load a `.GEM` border template and extract its Locator Rectangle + visible chrome."""
    gem_path = Path(path)
    if not gem_path.is_file():
        raise FileNotFoundError(f"Border .GEM file not found: {gem_path}")
    scene = vdi.scene_from_metafile(gem_path.read_bytes())
    locator_obj: dict[str, Any] | None = None
    skip_bg_idx = -1
    for obj in scene.objects:
        if obj.get("type") == "rectangle" and (
            obj.get("role") == "locator" or str(obj.get("id", "")).lower().startswith("locator")
        ):
            locator_obj = obj
            break
    if locator_obj is None and scene.objects:
        has_bg = _is_full_canvas_bg_bar(scene.objects[0], canvas_w, canvas_h)
        if has_bg:
            skip_bg_idx = 0
        fg_idx = 1 if has_bg else 0
        if fg_idx < len(scene.objects):
            cand = scene.objects[fg_idx]
            if _is_color_zero_rect(cand) and not _is_full_canvas_bg_bar(cand, canvas_w, canvas_h):
                locator_obj = cand
    if locator_obj is None:
        raise ValueError(f"Border .GEM lacks a locator rectangle: {gem_path}")

    b = [float(v) for v in locator_obj["bounds"]]
    lx0, ly0, lx1, ly1 = min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3])
    if lx0 < 0 or ly0 < 0 or lx1 > canvas_w or ly1 > canvas_h or (lx1 - lx0) < 320 or (ly1 - ly0) < 320:
        raise ValueError(f"Locator rectangle {[lx0, ly0, lx1, ly1]} invalid for canvas {canvas_w}x{canvas_h}")

    visible = [dict(o) for idx, o in enumerate(scene.objects) if o is not locator_obj and idx != skip_bg_idx]
    return ([lx0, ly0, lx1, ly1], visible)


def _replay_border_objects(canvas: DrawPlusCanvas, objects: Sequence[Mapping[str, Any]]) -> None:
    """Replay non-locator shapes from a `.GEM` border scene onto `canvas`."""
    for obj in objects:
        otype = obj.get("type")
        fill = str(obj.get("fill", "none"))
        stroke = str(obj.get("stroke", "none"))
        width = float(obj.get("width", 12.0))
        if otype == "rectangle" and "bounds" in obj:
            canvas.add_rectangle(obj["bounds"], fill=fill, stroke=stroke, width=width)
        elif otype == "polygon" and "points" in obj:
            canvas.add_polygon(obj["points"], fill=fill, stroke=stroke, width=width)
        elif otype in ("line", "polyline") and "points" in obj:
            canvas.add_polyline(obj["points"], stroke=stroke, width=width)
        elif otype == "ellipse" and "center" in obj and "radii" in obj:
            cx, cy = obj["center"]
            rx, ry = obj["radii"]
            canvas.add_ellipse(cx, cy, rx, ry, fill=fill, stroke=stroke, width=width)


def _split_list_to_columns(items: Sequence[str], num_cols: int) -> list[list[str]]:
    if num_cols <= 1:
        return [list(items)]
    cols: list[list[str]] = [[] for _ in range(num_cols)]
    for idx, item in enumerate(items):
        cols[idx % num_cols].append(str(item))
    return cols


def _format_body_rows(rows: Sequence[str], bullet_style: str, outline_levels: int = 0) -> list[str]:
    key = str(bullet_style or "none").strip().lower()
    if key == "none" and outline_levels <= 0:
        return [str(r) for r in rows]
    formatted: list[str] = []
    for idx, row in enumerate(rows, start=1):
        txt = str(row)
        prefix = _format_bullet_prefix(key, idx)
        if outline_levels > 0:
            lvl = (idx - 1) % outline_levels
            indent = "  " * lvl
            if not prefix:
                prefix = "•" if lvl > 0 else "◆"
            formatted.append(f"{indent}{prefix} {txt}".rstrip())
        else:
            formatted.append(f"{prefix} {txt}".strip() if prefix else txt)
    return formatted


class WordChartDoc:
    """4-zone structured slide composer supporting all 11 templates & Locator Borders."""

    def __init__(
        self,
        title: str | Sequence[str] = "",
        column_head: Sequence[str] | str = (),
        text_body: Sequence[str] | str = (),
        *,
        columns: Sequence[Sequence[str]] | None = None,
        footer: str | Sequence[str] = "",
        template: str = "column_1",
        orientation: str = "landscape",
        margins: tuple[float, float, float, float] | None = None,
        border_gem: Path | str | None = None,
        border_gem_path: Path | str | None = None,
        alignments: Sequence[str] | str | None = None,
        text_styles: Mapping[str, Any] | Sequence[str] | int | None = None,
        font_id: int | None = None,
        font_family: str | None = None,
        point_size: float | None = None,
        bullet_style: str = "none",
        lines_boxes: LineBoxSpec | Mapping[str, Any] | None = None,
        accent_boxes: bool = False,
        divider_lines: bool = False,
        theme: PresentationTheme | None = None,
        sister_id: str = "zoe",
        speaker_notes: str = "",
        strict_decimal: bool = False,
        freeform_items: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        tpl_key = str(template).strip()
        if tpl_key not in TEMPLATE_REGISTRY:
            raise ValueError(f"Unknown WordChart template {template!r}; expected {VALID_TEMPLATES}")
        self.template = tpl_key
        self.template_spec = TEMPLATE_REGISTRY[tpl_key]
        self.orientation = str(orientation)
        self.margins = margins
        self.border_gem_path = border_gem_path or border_gem
        self.theme = theme or (DARK_BOTANICAL_THEME if self.template_spec.dark_mode else theme_for_sister(sister_id))
        self.sister_id = str(sister_id)
        self.speaker_notes = str(speaker_notes)
        self.strict_decimal = bool(strict_decimal)
        self.accent_boxes = bool(accent_boxes)
        self.divider_lines = bool(divider_lines)
        self.bullet_style = str(bullet_style or "none").strip().lower()
        self.freeform_items = list(freeform_items) if freeform_items else []
        self.overflow_warnings: list[str] = []
        self.diagnostics: list[str] = []

        bold, italic, underline, boxed, _ = _parse_style_flags(text_styles)
        align_list = [alignments] if isinstance(alignments, str) else list(alignments or ["left"])
        primary_align = str(align_list[0]).lower() if align_list else "left"
        body_pt = float(point_size) if point_size is not None else 13.5
        line_box = LineBoxSpec.from_obj(lines_boxes)

        n_cols = self.template_spec.num_cols
        col_data: list[list[str]] = []
        if columns is not None:
            col_data = [[str(x) for x in col] for col in columns]
        elif n_cols > 1:
            col_data = _split_list_to_columns(_normalize_rows(text_body), n_cols)

        col_styles: list[TextStyleSpec] = []
        for c_idx in range(max(1, len(col_data), n_cols)):
            c_align = str(align_list[c_idx % len(align_list)]).lower()
            col_styles.append(
                TextStyleSpec(
                    font_id=font_id,
                    font_family=font_family or self.theme.font_sans,
                    point_size=body_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    boxed=boxed,
                    align=c_align,
                    bullet=self.bullet_style,
                )
            )

        title_rows = _normalize_rows(title)
        head_rows = _normalize_rows(column_head)
        body_rows = _normalize_rows(text_body)
        footer_rows = _normalize_rows(footer)

        self.zones: dict[str, TextZone] = {
            "title": TextZone(
                name="title",
                max_rows=ZONE_MAX_ROWS["title"],
                rows=title_rows,
                style=TextStyleSpec(
                    font_id=font_id,
                    font_family=font_family or self.theme.font_serif,
                    point_size=24.0 if point_size is None else max(14.0, float(point_size)),
                    bold=True,
                    align="center",
                    color=self.theme.title_color,
                ),
            ),
            "column_head": TextZone(
                name="column_head",
                max_rows=ZONE_MAX_ROWS["column_head"],
                rows=head_rows,
                style=TextStyleSpec(
                    font_id=font_id,
                    font_family=font_family or self.theme.font_sans,
                    point_size=13.0,
                    bold=True,
                    align="left" if n_cols == 1 else "center",
                    color=self.theme.accent,
                ),
                line_box=line_box,
            ),
            "text_body": TextZone(
                name="text_body",
                max_rows=ZONE_MAX_ROWS["text_body"],
                rows=body_rows,
                columns=col_data,
                style=TextStyleSpec(
                    font_id=font_id,
                    font_family=font_family or self.theme.font_sans,
                    point_size=body_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    boxed=boxed,
                    align=primary_align,
                    color=self.theme.body_color,
                    bullet=self.bullet_style,
                ),
                column_styles=col_styles,
                line_box=line_box,
            ),
            "footer": TextZone(
                name="footer",
                max_rows=ZONE_MAX_ROWS["footer"],
                rows=footer_rows,
                style=TextStyleSpec(
                    font_id=font_id,
                    font_family=font_family or self.theme.font_sans,
                    point_size=8.5,
                    align="center",
                    color=self.theme.muted_color,
                ),
            ),
        }

    def _validate_zone_limits(self) -> None:
        for zname, zone in self.zones.items():
            if len(zone.rows) > zone.max_rows:
                msg = f"Zone {zname!r} has {len(zone.rows)} rows (exceeds max_rows={zone.max_rows})"
                self.overflow_warnings.append(msg)
                self.diagnostics.append(msg)
            for c_idx, col in enumerate(zone.columns):
                if len(col) > zone.max_rows:
                    msg = f"Zone {zname!r} col {c_idx} has {len(col)} rows (exceeds max_rows={zone.max_rows})"
                    self.overflow_warnings.append(msg)
                    self.diagnostics.append(msg)

    def _resolve_work_box(
        self,
        canvas: DrawPlusCanvas,
        region: tuple[float, float, float, float] | None,
    ) -> list[float]:
        if region is not None:
            x0, y0, x1, y1 = (float(v) for v in region)
            return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        if self.border_gem_path is not None:
            loc_box, border_objs = _load_border_gem(self.border_gem_path, canvas.width, canvas.height)
            _replay_border_objects(canvas, border_objs)
            pad = 120.0
            return [loc_box[0] + pad, loc_box[1] + pad, loc_box[2] - pad, loc_box[3] - pad]
        if self.margins is not None:
            ml, mt, mr, mb = (float(v) for v in self.margins)
            return [ml, mt, canvas.width - mr, canvas.height - mb]
        return [float(MARGIN), 320.0, float(canvas.width - MARGIN), float(canvas.height - 260.0)]

    def _check_decimal_rows(self, rows: Sequence[str], align: str) -> None:
        if align != "decimal":
            return
        for row in rows:
            tok = str(row).strip()
            if tok and not validate_decimal_token(tok):
                msg = f"Non-numeric decimal-aligned token {tok!r}"
                self.diagnostics.append(msg)
                if self.strict_decimal:
                    raise ValueError(msg)

    def _emit_zone_rules_and_box(
        self,
        canvas: DrawPlusCanvas,
        box: Sequence[float],
        text: str,
        style: TextStyleSpec,
        lb: LineBoxSpec,
    ) -> None:
        x0, y0, x1, y1 = (float(v) for v in box)
        if lb.box or self.accent_boxes:
            canvas.add_rounded_rectangle(
                [x0, y0, x1, y1],
                radius=90.0,
                fill=lb.box_fill if lb.box_fill != "none" else self.theme.card,
                stroke=lb.box_stroke or self.theme.card_border,
                width=lb.box_width,
            )
        if not (lb.rule_above or lb.rule_below or self.divider_lines):
            return
        rx0, rx1 = x0, x1
        if lb.rule_match == "match_text" and text.strip():
            mw, _, _ = PresentationRenderer.measure_text(
                text,
                font_family=style.font_family or self.theme.font_sans,
                font_pt=style.point_size,
                bold=style.bold,
                italic=style.italic,
                max_width_vdi=max(60.0, x1 - x0),
            )
            if style.align == "center":
                mid = (x0 + x1) / 2.0
                rx0, rx1 = max(x0, mid - mw / 2.0), min(x1, mid + mw / 2.0)
            elif style.align == "right":
                rx0 = max(x0, x1 - mw)
            else:
                rx1 = min(x1, x0 + mw)
        rule_col = self.theme.gold if self.theme.mode == "dark" else LIGHT_DIVIDER_LINE
        if lb.rule_above:
            canvas.add_line([rx0, max(0.0, y0 - 35.0)], [rx1, max(0.0, y0 - 35.0)], stroke=rule_col, width=lb.rule_width)
        if lb.rule_below or self.divider_lines:
            canvas.add_line([rx0, min(float(canvas.height), y1 + 35.0)], [rx1, min(float(canvas.height), y1 + 35.0)], stroke=rule_col, width=lb.rule_width)

    def _fit_text_pt(
        self,
        text: str,
        box: Sequence[float],
        base_pt: float,
        style: TextStyleSpec,
        *,
        min_pt: float = 8.0,
    ) -> tuple[float, bool]:
        bw = max(80.0, float(box[2]) - float(box[0]))
        bh = max(40.0, float(box[3]) - float(box[1]))
        pt = float(base_pt)
        while pt >= min_pt:
            mw, mh, _ = PresentationRenderer.measure_text(
                text,
                font_id=style.font_id,
                font_family=style.font_family or self.theme.font_sans,
                font_pt=pt,
                bold=style.bold,
                italic=style.italic,
                effects=style.effects_bitmask(),
                max_width_vdi=bw,
                wrap=True,
                line_spacing=style.line_spacing,
            )
            if mw <= bw + 2.0 and mh <= bh + 2.0:
                return (pt, False)
            pt -= 1.0
        return (min_pt, True)

    def _emit_fitted_text(
        self,
        canvas: DrawPlusCanvas,
        box: Sequence[float],
        text: str,
        style: TextStyleSpec,
        *,
        zone_name: str,
        color: str | None = None,
        min_pt: float = 8.0,
    ) -> None:
        if not text.strip():
            return
        pt, overflowed = self._fit_text_pt(text, box, style.point_size, style, min_pt=min_pt)
        if overflowed:
            msg = f"Zone {zone_name!r} text exceeds allocated box {box!r} even at {min_pt}pt"
            self.overflow_warnings.append(msg)
            self.diagnostics.append(msg)
        canvas.add_text(
            box,
            text,
            font_id=style.font_id,
            font_family=style.font_family or self.theme.font_sans,
            font_pt=pt,
            bold=style.bold,
            italic=style.italic,
            underline=style.underline,
            boxed=style.boxed,
            effects=style.effects_bitmask(),
            align=style.align,
            valign="top",
            color=color or style.color or self.theme.body_color,
            line_spacing=style.line_spacing,
            wrap=True,
        )

    def _compile_cards_grid(
        self,
        canvas: DrawPlusCanvas,
        body_box: list[float],
        headers: Sequence[str],
        cols: Sequence[Sequence[str]],
        body_rows: Sequence[str],
        col_styles: Sequence[TextStyleSpec] = (),
    ) -> None:
        x0, y0, x1, y1 = body_box
        gap = 220.0
        if self.template_spec.grid_2x2:
            cw = (x1 - x0 - gap) / 2.0
            ch = (y1 - y0 - gap) / 2.0
            accents = (RUBY, JADE, GOLD, RUBY)
            for idx in range(4):
                col_i, row_i = idx % 2, idx // 2
                cx0 = x0 + col_i * (cw + gap)
                cy0 = y0 + row_i * (ch + gap)
                card_box = [cx0, cy0, cx0 + cw, cy0 + ch]
                canvas.add_card(card_box, accent_color=accents[idx], border_color=self.theme.card_border)
                hdr = headers[idx] if idx < len(headers) else f"Metric {idx + 1}"
                self._emit_fitted_text(
                    canvas, [cx0 + 140.0, cy0 + 110.0, cx0 + cw - 140.0, cy0 + 420.0],
                    hdr, TextStyleSpec(point_size=12.5, bold=True, color=self.theme.title_color), zone_name="column_head",
                )
                c_style = col_styles[idx] if idx < len(col_styles) else self.zones["text_body"].style
                raw_lines = cols[idx] if idx < len(cols) else ([body_rows[idx]] if not cols and idx < len(body_rows) else [])
                self._check_decimal_rows(raw_lines, c_style.align)
                txt = "\n".join(_format_body_rows(raw_lines, self.bullet_style)) if raw_lines else ""
                if txt:
                    self._emit_fitted_text(
                        canvas, [cx0 + 140.0, cy0 + 460.0, cx0 + cw - 140.0, cy0 + ch - 100.0],
                        txt, c_style, zone_name="text_body",
                    )
            return

        # 3-pillar cards (or single card)
        n_cards = 3 if self.template == "pillar_3col" else 1
        cw = (x1 - x0 - gap * (n_cards - 1)) / n_cards
        pillar_accents: tuple[str, ...] = (RUBY, JADE, GOLD)
        for idx in range(n_cards):
            cx0 = x0 + idx * (cw + gap)
            card_box = [cx0, y0, cx0 + cw, y1]
            canvas.add_card(card_box, accent_color=pillar_accents[idx % 3], border_color=self.theme.card_border)
            top_off = y0 + 120.0
            if idx < len(headers) and headers[idx]:
                self._emit_fitted_text(
                    canvas, [cx0 + 140.0, top_off, cx0 + cw - 140.0, top_off + 360.0],
                    headers[idx], TextStyleSpec(point_size=13.0, bold=True, align="center", color=self.theme.accent),
                    zone_name="column_head",
                )
                top_off += 400.0
            c_style = col_styles[idx] if idx < len(col_styles) else self.zones["text_body"].style
            raw_lines = cols[idx] if idx < len(cols) and cols[idx] else ([body_rows[idx]] if n_cards > 1 and idx < len(body_rows) else body_rows)
            self._check_decimal_rows(raw_lines, c_style.align)
            formatted = "\n".join(_format_body_rows(raw_lines, self.bullet_style))
            self._emit_fitted_text(
                canvas, [cx0 + 140.0, top_off, cx0 + cw - 140.0, y1 - 100.0],
                formatted, c_style, zone_name="text_body",
            )

    def _compile_columns(
        self,
        canvas: DrawPlusCanvas,
        head_box: list[float],
        body_box: list[float],
        head_rows: Sequence[str],
        cols: Sequence[Sequence[str]],
        col_styles: Sequence[TextStyleSpec],
    ) -> None:
        n_cols = max(1, len(cols))
        gap = 220.0 if n_cols > 1 else 0.0
        bx0, by0, bx1, by1 = body_box
        cw = (bx1 - bx0 - gap * (n_cols - 1)) / n_cols
        lb = self.zones["text_body"].line_box

        for idx in range(n_cols):
            cx0 = bx0 + idx * (cw + gap)
            cx1 = cx0 + cw
            if idx < len(head_rows) and head_rows[idx]:
                hbox = [cx0, head_box[1], cx1, head_box[3]]
                self._emit_fitted_text(
                    canvas, hbox, head_rows[idx], self.zones["column_head"].style,
                    zone_name="column_head",
                )
            c_style = col_styles[idx] if idx < len(col_styles) else self.zones["text_body"].style
            raw_lines = cols[idx]
            self._check_decimal_rows(raw_lines, c_style.align)
            formatted = "\n".join(_format_body_rows(raw_lines, self.bullet_style, self.template_spec.outline_levels))
            c_box = [cx0, by0, cx1, by1]
            self._emit_zone_rules_and_box(canvas, c_box, formatted, c_style, lb)
            pad = 90.0 if (lb.box or self.accent_boxes) else 0.0
            self._emit_fitted_text(
                canvas, [cx0 + pad, by0 + pad, cx1 - pad, by1 - pad],
                formatted, c_style, zone_name="text_body",
            )

    def compile(
        self,
        canvas: DrawPlusCanvas,
        *,
        region: tuple[float, float, float, float] | None = None,
    ) -> DrawPlusCanvas:
        """Compile all 4 WordChart zones into `canvas` inside `region` or locator border."""
        self.overflow_warnings.clear()
        self.diagnostics.clear()
        self._validate_zone_limits()

        if self.template_spec.dark_mode:
            canvas.background = OBSIDIAN
            canvas.theme = DARK_BOTANICAL_THEME

        wx0, wy0, wx1, wy1 = self._resolve_work_box(canvas, region)
        total_h = max(400.0, wy1 - wy0)
        title_zone = self.zones["title"]
        head_zone = self.zones["column_head"]
        body_zone = self.zones["text_body"]
        foot_zone = self.zones["footer"]

        title_h = min(920.0, total_h * 0.18) if title_zone.rows else 0.0
        foot_h = min(400.0, total_h * 0.10) if foot_zone.rows else 0.0
        has_head = bool(head_zone.rows) and not self.template_spec.cards
        head_h = min(440.0, total_h * 0.10) if has_head else 0.0

        cursor_y = wy0
        if title_h > 0:
            tbox = [wx0, cursor_y, wx1, cursor_y + title_h]
            self._emit_fitted_text(canvas, tbox, "\n".join(title_zone.rows), title_zone.style, zone_name="title")
            cursor_y += title_h + 90.0
            if self.divider_lines:
                rule_col = self.theme.gold if self.theme.mode == "dark" else LIGHT_DIVIDER_LINE
                canvas.add_line([wx0, cursor_y - 45.0], [wx1, cursor_y - 45.0], stroke=rule_col, width=12.0)

        head_box = [wx0, cursor_y, wx1, cursor_y + head_h]
        if head_h > 0:
            cursor_y += head_h + 70.0

        body_bottom = wy1 - foot_h - (60.0 if foot_h > 0 else 0.0)
        body_box = [wx0, cursor_y, wx1, max(cursor_y + 180.0, body_bottom)]

        if self.template_spec.freeform and self.freeform_items:
            for item in self.freeform_items:
                ib = item.get("bounds", body_box)
                itxt = str(item.get("text", ""))
                ist = TextStyleSpec(
                    point_size=float(item.get("point_size", body_zone.style.point_size)),
                    bold=bool(item.get("bold", False)),
                    align=str(item.get("align", "left")),
                    color=item.get("color", self.theme.body_color),
                )
                self._emit_fitted_text(canvas, ib, itxt, ist, zone_name="text_body")
        elif self.template_spec.cards:
            cols = body_zone.columns or _split_list_to_columns(body_zone.rows, self.template_spec.num_cols)
            self._compile_cards_grid(canvas, body_box, head_zone.rows, cols, body_zone.rows, body_zone.column_styles)
        else:
            cols = body_zone.columns if body_zone.columns else [body_zone.rows]
            self._compile_columns(canvas, head_box, body_box, head_zone.rows, cols, body_zone.column_styles)

        if foot_h > 0:
            fbox = [wx0, wy1 - foot_h, wx1, wy1]
            self._emit_fitted_text(canvas, fbox, "\n".join(foot_zone.rows), foot_zone.style, zone_name="footer", min_pt=7.0)

        if self.speaker_notes and not canvas.speaker_notes:
            canvas.speaker_notes = self.speaker_notes
        return canvas


__all__ = [
    "BULLET_MARKERS",
    "NUMBERING_STYLES",
    "STANDARD_POINT_SIZES",
    "STYLE_FLAGS",
    "TEMPLATE_REGISTRY",
    "VALID_ALIGNMENTS",
    "VALID_TEMPLATES",
    "ZONE_MAX_ROWS",
    "LineBoxSpec",
    "TextStyleSpec",
    "TextZone",
    "WordChartDoc",
    "WordChartTemplate",
    "to_alpha",
    "to_roman",
    "validate_decimal_token",
]

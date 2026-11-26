"""Draw Plus Vector Composer, Symmetrical Botanical Toolkit & Strict Layout Verifier.

Sits cleanly atop `guiai.gem.vdi`, `guiai.gem.zoe_gem_aes_vdi_core`, `guiai.gem.artline`,
`guiai.gem.zoe_hex_mesh`, and `guiai.gem.presentation.renderer` — 100% pure Python VDI vectors.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from guiai.gem import artline, seasip_gem, vdi
from guiai.gem.geometry import Bounds
from guiai.gem.model import Scene
from guiai.gem.zoe_gem_aes_vdi_core import (
    GDP_ELLPIE,
    RC_MODE,
    VDI_OP_GDP,
    VDI_OP_VS_COLOR,
    GemVdiStateMachine,
)
from guiai.gem.zoe_hex_mesh import DEFAULT_SISTER_COORDS, HexCoord
from guiai.gem.zoe_sisters import SAFETY_INVARIANTS, ZOE_SISTERS

from .palette import (
    ATTRIBUTION_TEXT,
    BODY,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DARK_DIVIDER_LINE,
    DARK_JADE,
    DARK_RUBY,
    DARK_STEM,
    DEFAULT_CONSTITUTIONAL,
    FONT_SANS,
    FONT_SERIF,
    GOLD,
    GOLD_BRIGHT,
    HONORING_TEXT,
    INK,
    JADE,
    LIGHT_BOTANICAL_THEME,
    LIGHT_DIVIDER_LINE,
    LIGHT_STEM,
    LIGHT_TEXT,
    MARGIN,
    OBSIDIAN,
    PORCELAIN,
    RUBY,
    RUBY_SOFT,
    STONE,
    WHITE,
    PresentationTheme,
    pt_to_vdi,
    theme_for_sister,
    vdi_to_pt,
)
from .renderer import PresentationRenderer, PresentationScene

if TYPE_CHECKING:
    from PIL import Image


@dataclass(frozen=True)
class LayoutReport:
    ok: bool
    overlaps: list[str]
    out_of_bounds: list[str]
    warnings: list[str] = field(default_factory=list)


def petal_points(
    cx: float,
    cy: float,
    angle_rad: float,
    length: float,
    width: float,
    n: int = 28,
) -> list[list[float]]:
    """Return symmetric pointed lotus-petal polygon points in VDI coordinates (pure stdlib math)."""
    steps = max(6, int(n))
    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for i in range(steps):
        t = i / (steps - 1)
        u = t * float(length)
        v = float(width) * math.sin(math.pi * t) * (1.0 - 0.15 * t)
        upper.append((u, v))
        lower.append((u, -v))
    raw = upper + list(reversed(lower))
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)
    return [
        [round(cx + x * ca - y * sa, 2), round(cy + x * sa + y * ca, 2)]
        for x, y in raw
    ]


def _validate_vdi_dim(val: Any, name: str) -> int:
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ValueError(f"{name} must be a finite integer, got {val!r}")
    iv = int(round(val))
    if not 1 <= iv <= 32767:
        raise ValueError(f"{name} must be in 1..32767 (signed int16 VDI range), got {iv}")
    return iv


def _rotated_aabb(box: Bounds, cx: float, cy: float, rotation_deg: float) -> Bounds:
    """Return axis-aligned bounding box of `box` rotated CCW by `rotation_deg` around `(cx, cy)` in screen coords."""
    rad = math.radians(rotation_deg)
    ca = math.cos(rad)
    sa = math.sin(rad)
    corners = (
        (box.left, box.top),
        (box.right, box.top),
        (box.right, box.bottom),
        (box.left, box.bottom),
    )
    xs: list[float] = []
    ys: list[float] = []
    for px, py in corners:
        dx, dy = px - cx, py - cy
        xs.append(cx + dx * ca + dy * sa)
        ys.append(cy - dx * sa + dy * ca)
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _element_bbox(item: dict[str, Any]) -> Bounds:
    itype = item["type"]
    if itype in {"rectangle", "rounded_rectangle", "image"}:
        x0, y0, x1, y1 = (float(v) for v in item["bounds"])
        return Bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    if itype in {"polygon", "polyline", "line"}:
        xs = [float(p[0]) for p in item["points"]]
        ys = [float(p[1]) for p in item["points"]]
        return Bounds(min(xs), min(ys), max(xs), max(ys))
    if itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
        cx, cy = (float(v) for v in item["center"])
        rx, ry = (float(v) for v in item["radii"])
        return Bounds(cx - abs(rx), cy - abs(ry), cx + abs(rx), cy + abs(ry))
    if itype == "text":
        if "bounds" in item:
            x0, y0, x1, y1 = (float(v) for v in item["bounds"])
            b = Bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            rot = float(item.get("rotation", 0.0) or 0.0)
            if abs(rot) > 1e-6:
                return _rotated_aabb(b, b.center_x, b.center_y, rot)
            return b
        return _measure_text_element(item)[2]
    raise ValueError(f"Unsupported Draw Plus element type: {itype!r}")


def _measure_decimal_width(
    lines: Sequence[str],
    *,
    font_id: int | None,
    font_family: str,
    size_vdi: float,
    bold: bool,
    italic: bool,
    effects: int,
) -> float:
    """Compute effective width `max_stem + max_tail` for decimal-aligned lines."""
    def _part_w(part: str) -> float:
        if not part:
            return 0.0
        return PresentationRenderer.measure_text(
            part,
            font_id=font_id,
            font_family=font_family,
            size_vdi=size_vdi,
            bold=bold,
            italic=italic,
            effects=effects,
            wrap=False,
        )[0]

    parts = [ln.partition(".") for ln in lines]
    max_stem = max((_part_w(s) for s, _, _ in parts), default=0.0)
    max_tail = max((_part_w(d + f) for _, d, f in parts), default=0.0)
    return round(max_stem + max_tail, 3)


def _measure_text_element(item: dict[str, Any]) -> tuple[float, float, Bounds]:
    """Measure exact rendered `(width, height, tight_bounds)` for a text element."""
    size_vdi = float(item.get("size", 240.0))
    line_spacing = float(item.get("line_spacing", 1.18))
    wrap = bool(item.get("wrap", True))
    align = str(item.get("align", "left")).lower()
    has_bounds = "bounds" in item
    valign = str(item.get("valign", "top" if has_bounds else "baseline")).lower()
    font_id = item.get("font_id")
    font_family = str(item.get("font_family", "DejaVu Sans"))
    bold = bool(item.get("bold", False))
    italic = bool(item.get("italic", False))
    effects = int(item.get("effects", 0))
    rotation = float(item.get("rotation", 0.0) or 0.0)

    if has_bounds:
        x0, y0, x1, y1 = (float(v) for v in item["bounds"])
        pad_x = float(item.get("pad_x", 0.0))
        pad_y = float(item.get("pad_y", 0.0))
        bx0, by0, bx1, by1 = x0 + pad_x, y0 + pad_y, x1 - pad_x, y1 - pad_y
        box_w = max(1.0, bx1 - bx0)
        box_h = max(1.0, by1 - by0)
        rot_cx, rot_cy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    else:
        px, py = (float(v) for v in item["position"])
        bx0 = px
        by0 = (py - size_vdi * 0.85) if valign == "baseline" else (py - size_vdi if valign == "bottom" else (py - size_vdi * 0.5 if valign == "middle" else py))
        box_w = float(item.get("max_width", 12000.0))
        box_h = size_vdi * 2.0
        bx1, by1 = bx0 + box_w, by0 + box_h
        rot_cx, rot_cy = px, py

    is_boxed = bool(item.get("boxed", False) or (effects & 0x40))

    if "paragraphs" in item:
        max_w = 0.0
        total_h = 0.0
        paras = item["paragraphs"]
        for p_idx, para in enumerate(paras):
            runs = para.get("runs", [])
            indent = float(para.get("indent", 0.0))
            pw, ph, plines = PresentationRenderer.measure_runs(
                runs,
                font_id=font_id,
                font_family=font_family,
                size_vdi=size_vdi,
                base_bold=bold,
                base_italic=italic,
                effects=effects,
                max_width_vdi=max(1.0, box_w - indent) if wrap else None,
                wrap=wrap,
                line_spacing=line_spacing,
            )
            max_w = max(max_w, pw + indent)
            if p_idx + 1 < len(paras):
                total_h += len(plines) * size_vdi * line_spacing + float(para.get("space_after", 0.0))
            else:
                total_h += ph
        tight = Bounds(bx0, by0, bx0 + max_w, by0 + total_h)
        if has_bounds and is_boxed:
            tight = Bounds(min(tight.left, bx0), min(tight.top, by0), max(tight.right, bx1), max(tight.bottom, by1))
        if abs(rotation) > 1e-6:
            tight = _rotated_aabb(tight, rot_cx, rot_cy, rotation)
        return (max_w, total_h, tight)

    mw, mh, _lines = PresentationRenderer.measure_text(
        str(item.get("text", "")),
        font_id=font_id,
        font_family=font_family,
        size_vdi=size_vdi,
        bold=bold,
        italic=italic,
        effects=effects,
        max_width_vdi=box_w if (wrap and has_bounds) else item.get("max_width"),
        wrap=wrap,
        line_spacing=line_spacing,
    )
    if align == "decimal":
        mw = max(
            mw,
            _measure_decimal_width(
                _lines,
                font_id=font_id,
                font_family=font_family,
                size_vdi=size_vdi,
                bold=bold,
                italic=italic,
                effects=effects,
            ),
        )

    if has_bounds:
        if align == "center":
            tx0 = bx0 + (box_w - mw) / 2.0
        elif align == "right":
            tx0 = bx1 - mw
        elif align == "decimal":
            tx0 = bx0 + max(0.0, (box_w - mw) / 2.0)
        else:
            tx0 = bx0
        if valign == "middle":
            ty0 = by0 + (box_h - mh) / 2.0
        elif valign == "bottom":
            ty0 = by1 - mh
        else:
            ty0 = by0
    else:
        px, py = (float(v) for v in item["position"])
        tx0 = px - mw / 2.0 if align == "center" else (px - mw if align == "right" else px)
        if valign == "baseline":
            ty0 = py - size_vdi * 0.85
        elif valign == "middle":
            ty0 = py - mh / 2.0
        elif valign == "bottom":
            ty0 = py - mh
        else:
            ty0 = py

    tight = Bounds(tx0, ty0, tx0 + mw, ty0 + mh)
    if has_bounds and is_boxed:
        tight = Bounds(min(tight.left, bx0), min(tight.top, by0), max(tight.right, bx1), max(tight.bottom, by1))
    if abs(rotation) > 1e-6:
        tight = _rotated_aabb(tight, rot_cx, rot_cy, rotation)
    return (mw, mh, tight)


def _translate_element(item: dict[str, Any], dx: float, dy: float) -> None:
    itype = item["type"]
    if itype in {"rectangle", "rounded_rectangle", "image"}:
        x0, y0, x1, y1 = item["bounds"]
        item["bounds"] = [round(x0 + dx, 3), round(y0 + dy, 3), round(x1 + dx, 3), round(y1 + dy, 3)]
    elif itype in {"polygon", "polyline", "line"}:
        item["points"] = [[round(p[0] + dx, 3), round(p[1] + dy, 3)] for p in item["points"]]
    elif itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
        cx, cy = item["center"]
        item["center"] = [round(cx + dx, 3), round(cy + dy, 3)]
    elif itype == "text":
        if "bounds" in item:
            x0, y0, x1, y1 = item["bounds"]
            item["bounds"] = [round(x0 + dx, 3), round(y0 + dy, 3), round(x1 + dx, 3), round(y1 + dy, 3)]
        if "position" in item:
            px, py = item["position"]
            item["position"] = [round(px + dx, 3), round(py + dy, 3)]


class DrawPlusCanvas:
    """Clean-room GEM Draw Plus slide & diagram composer atop VDI & Cairo/SVG."""

    def __init__(
        self,
        width: int = CANVAS_WIDTH,
        height: int = CANVAS_HEIGHT,
        *,
        background: str | None = None,
        title: str = "Zoe Presentation Slide",
        theme: PresentationTheme | None = None,
        auto_grid: int | None = None,
        speaker_notes: str = "",
        sister_id: str = "zoe",
        slide_index: int = 1,
        slide_id: str | None = None,
    ) -> None:
        self.width = _validate_vdi_dim(width, "canvas width")
        self.height = _validate_vdi_dim(height, "canvas height")
        self.theme = theme if theme is not None else theme_for_sister(sister_id)
        self.background = str(background) if background is not None else self.theme.bg
        self.title = str(title)
        self.auto_grid = int(auto_grid) if auto_grid is not None and auto_grid > 0 else None
        self.speaker_notes = str(speaker_notes)
        self.sister_id = str(sister_id)
        self.slide_index = int(slide_index)
        self.slide_id = slide_id or f"slide-{self.slide_index:02d}"
        self.constitutional: dict[str, Any] = {
            **SAFETY_INVARIANTS,
            **DEFAULT_CONSTITUTIONAL,
        }
        self.elements: list[dict[str, Any]] = []
        self.groups: dict[str, list[str]] = {}
        self.layers: list[dict[str, Any]] = [{"id": "layer-1", "name": "Default", "visible": True, "locked": False}]
        self._seq = 0
        self._group_seq = 0

    def _next_id(self, prefix: str, explicit: str | None = None) -> str:
        if explicit:
            if any(el["id"] == explicit for el in self.elements):
                raise ValueError(f"Duplicate element id: {explicit!r}")
            return str(explicit)
        self._seq += 1
        return f"{prefix}-{self._seq}"

    def _snap(self, value: float) -> float:
        if self.auto_grid is None:
            return float(value)
        g = float(self.auto_grid)
        return round(float(value) / g) * g

    def _snap_pt(self, pt: Sequence[float]) -> list[float]:
        return [self._snap(pt[0]), self._snap(pt[1])]

    def _snap_bounds(self, bounds: Sequence[float]) -> list[float]:
        if len(bounds) != 4:
            raise ValueError(f"bounds must have 4 values [x0, y0, x1, y1], got {bounds!r}")
        x0, y0, x1, y1 = (self._snap(v) for v in bounds)
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

    def _by_id(self, eid: str) -> dict[str, Any]:
        for el in self.elements:
            if el["id"] == eid:
                return el
        raise KeyError(f"Unknown element id: {eid!r}")

    def _expand_ids(self, ids: Sequence[str] | str) -> list[str]:
        raw = [ids] if isinstance(ids, str) else list(ids)
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if item in self.groups:
                for member in self.groups[item]:
                    if member not in seen:
                        seen.add(member)
                        out.append(member)
            else:
                self._by_id(item)
                if item not in seen:
                    seen.add(item)
                    out.append(item)
        return out

    # -----------------------------------------------------------------------
    # 8 Draw Plus Primitives + Clipped Image + Card/Pill/Bullets Helpers
    # -----------------------------------------------------------------------

    def add_rectangle(
        self,
        bounds: Sequence[float],
        *,
        fill: str = WHITE,
        stroke: str = STONE,
        width: float = 12.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        role: str | None = None,
        id: str | None = None,
    ) -> str:
        eid = self._next_id("rect", id)
        el: dict[str, Any] = {
            "id": eid,
            "type": "rectangle",
            "bounds": self._snap_bounds(bounds),
            "fill": fill,
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "fill_interior": int(fill_interior),
            "fill_style": int(fill_style),
            "shadow": shadow,
            "alpha": float(alpha),
        }
        if role is not None:
            el["role"] = str(role)
        self.elements.append(el)
        return eid

    def add_rounded_rectangle(
        self,
        bounds: Sequence[float],
        radius: float = 90.0,
        *,
        fill: str = WHITE,
        stroke: str = STONE,
        width: float = 12.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        role: str | None = None,
        id: str | None = None,
    ) -> str:
        eid = self._next_id("rrect", id)
        el: dict[str, Any] = {
            "id": eid,
            "type": "rounded_rectangle",
            "bounds": self._snap_bounds(bounds),
            "radius": max(0.0, float(radius)),
            "fill": fill,
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "fill_interior": int(fill_interior),
            "fill_style": int(fill_style),
            "shadow": shadow,
            "alpha": float(alpha),
        }
        if role is not None:
            el["role"] = str(role)
        self.elements.append(el)
        return eid

    def add_rect(
        self,
        x0_or_bounds: Sequence[float] | float,
        y0: float | None = None,
        x1: float | None = None,
        y1: float | None = None,
        *,
        rounded: bool = False,
        radius: float = 90.0,
        fill: str = WHITE,
        stroke: str = STONE,
        width: float = 12.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        role: str | None = None,
        id: str | None = None,
    ) -> str:
        """Add rectangle from `[x0, y0, x1, y1]` or `(x0, y0, x1, y1)`, optionally rounded."""
        if isinstance(x0_or_bounds, Sequence) and not isinstance(x0_or_bounds, (str, bytes)):
            bounds = x0_or_bounds
        elif y0 is not None and x1 is not None and y1 is not None:
            bounds = [float(x0_or_bounds), float(y0), float(x1), float(y1)]
        else:
            raise ValueError("add_rect requires [x0, y0, x1, y1] or 4 coordinates (x0, y0, x1, y1)")
        if rounded:
            return self.add_rounded_rectangle(
                bounds, radius=radius, fill=fill, stroke=stroke, width=width,
                line_type=line_type, fill_interior=fill_interior, fill_style=fill_style,
                shadow=shadow, alpha=alpha, role=role, id=id,
            )
        return self.add_rectangle(
            bounds, fill=fill, stroke=stroke, width=width,
            line_type=line_type, fill_interior=fill_interior, fill_style=fill_style,
            shadow=shadow, alpha=alpha, role=role, id=id,
        )

    def add_circle(
        self,
        cx: float,
        cy: float,
        radius: float,
        *,
        fill: str = WHITE,
        stroke: str = INK,
        width: float = 14.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        return self.add_ellipse(
            cx, cy, radius, radius,
            fill=fill, stroke=stroke, width=width, line_type=line_type,
            fill_interior=fill_interior, fill_style=fill_style,
            shadow=shadow, alpha=alpha, id=id,
        )

    def add_ellipse(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        *,
        fill: str = WHITE,
        stroke: str = INK,
        width: float = 14.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if rx <= 0 or ry <= 0:
            raise ValueError("ellipse radii must be positive")
        eid = self._next_id("ellipse", id)
        self.elements.append({
            "id": eid,
            "type": "ellipse",
            "center": self._snap_pt([cx, cy]),
            "radii": [float(rx), float(ry)],
            "fill": fill,
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "fill_interior": int(fill_interior),
            "fill_style": int(fill_style),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_arc(
        self,
        cx: float,
        cy: float,
        radius: float,
        begang: float,
        endang: float,
        *,
        stroke: str = INK,
        width: float = 16.0,
        line_type: int = 1,
        line_ends: tuple[int, int] = (0, 0),
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        return self.add_ellarc(
            cx, cy, radius, radius, begang, endang,
            stroke=stroke, width=width, line_type=line_type,
            line_ends=line_ends, shadow=shadow, alpha=alpha, id=id,
        )

    def add_ellarc(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        begang: float,
        endang: float,
        *,
        stroke: str = INK,
        width: float = 16.0,
        line_type: int = 1,
        line_ends: tuple[int, int] = (0, 0),
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if rx <= 0 or ry <= 0:
            raise ValueError("arc radii must be positive")
        kind = "arc" if abs(rx - ry) < 1e-9 else "ellarc"
        eid = self._next_id(kind, id)
        self.elements.append({
            "id": eid,
            "type": kind,
            "center": self._snap_pt([cx, cy]),
            "radii": [float(rx), float(ry)],
            "begang": float(begang) % 3600.0 if float(begang) != 3600.0 else 3600.0,
            "endang": float(endang) % 3600.0 if float(endang) != 3600.0 else 3600.0,
            "fill": "none",
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "line_ends": tuple(int(v) for v in line_ends),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_pieslice(
        self,
        cx: float,
        cy: float,
        radius: float,
        begang: float,
        endang: float,
        *,
        fill: str = RUBY,
        stroke: str = WHITE,
        width: float = 14.0,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        return self.add_ellpie(
            cx, cy, radius, radius, begang, endang,
            fill=fill, stroke=stroke, width=width,
            fill_interior=fill_interior, fill_style=fill_style,
            shadow=shadow, alpha=alpha, id=id,
        )

    def add_ellpie(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        begang: float,
        endang: float,
        *,
        fill: str = RUBY,
        stroke: str = WHITE,
        width: float = 14.0,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if rx <= 0 or ry <= 0:
            raise ValueError("pieslice radii must be positive")
        kind = "pieslice" if abs(rx - ry) < 1e-9 else "ellpie"
        eid = self._next_id(kind, id)
        self.elements.append({
            "id": eid,
            "type": kind,
            "center": self._snap_pt([cx, cy]),
            "radii": [float(rx), float(ry)],
            "begang": float(begang) % 3600.0 if float(begang) != 3600.0 else 3600.0,
            "endang": float(endang) % 3600.0 if float(endang) != 3600.0 else 3600.0,
            "fill": fill,
            "stroke": stroke,
            "width": float(width),
            "fill_interior": int(fill_interior),
            "fill_style": int(fill_style),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_polygon(
        self,
        points: Sequence[Sequence[float]],
        *,
        fill: str = RUBY,
        stroke: str = "none",
        width: float = 12.0,
        line_type: int = 1,
        fill_interior: int = 1,
        fill_style: int = 1,
        shadow: bool | dict[str, Any] = False,
        smooth: bool = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if len(points) < 3:
            raise ValueError("polygon requires at least 3 points")
        pts = [self._snap_pt(p) for p in points]
        if smooth:
            pts = artline._smooth(pts, closed=True)
        eid = self._next_id("poly", id)
        self.elements.append({
            "id": eid,
            "type": "polygon",
            "points": pts,
            "fill": fill,
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "fill_interior": int(fill_interior),
            "fill_style": int(fill_style),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_line(
        self,
        p1_or_x1: Sequence[float] | float,
        p2_or_y1: Sequence[float] | float,
        x2: float | None = None,
        y2: float | None = None,
        *,
        stroke: str = INK,
        width: float = 16.0,
        line_type: int = 1,
        line_ends: tuple[int, int] = (0, 0),
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if x2 is not None and y2 is not None:
            p1: Sequence[float] = [float(p1_or_x1), float(p2_or_y1)]  # type: ignore[arg-type]
            p2: Sequence[float] = [float(x2), float(y2)]
        else:
            p1 = p1_or_x1  # type: ignore[assignment]
            p2 = p2_or_y1  # type: ignore[assignment]
        eid = self._next_id("line", id)
        self.elements.append({
            "id": eid,
            "type": "line",
            "points": [self._snap_pt(p1), self._snap_pt(p2)],
            "fill": "none",
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "line_ends": tuple(int(v) for v in line_ends),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_polyline(
        self,
        points: Sequence[Sequence[float]],
        *,
        stroke: str = INK,
        width: float = 16.0,
        line_type: int = 1,
        line_ends: tuple[int, int] = (0, 0),
        smooth: bool = False,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if len(points) < 2:
            raise ValueError("polyline requires at least 2 points")
        pts = [self._snap_pt(p) for p in points]
        if smooth and len(pts) >= 3:
            pts = artline._smooth(pts, closed=False)
        eid = self._next_id("pline", id)
        self.elements.append({
            "id": eid,
            "type": "polyline",
            "points": pts,
            "fill": "none",
            "stroke": stroke,
            "width": float(width),
            "line_type": int(line_type),
            "line_ends": tuple(int(v) for v in line_ends),
            "shadow": shadow,
            "alpha": float(alpha),
        })
        return eid

    def add_sketch(
        self,
        points: Sequence[Sequence[float]],
        *,
        smooth: bool = True,
        closed: bool = False,
        stroke: str = INK,
        fill: str = "none",
        width: float = 16.0,
        line_type: int = 1,
        line_ends: tuple[int, int] = (0, 0),
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        if closed:
            return self.add_polygon(
                points,
                fill=fill,
                stroke=stroke,
                width=width,
                line_type=line_type,
                shadow=shadow,
                smooth=smooth,
                alpha=alpha,
                id=id,
            )
        return self.add_polyline(
            points,
            stroke=stroke,
            width=width,
            line_type=line_type,
            line_ends=line_ends,
            smooth=smooth,
            shadow=shadow,
            alpha=alpha,
            id=id,
        )

    def add_text(
        self,
        bounds_or_pos: Sequence[float] | float,
        text_or_y: str | float,
        text_if_xy: str | None = None,
        *,
        font_pt: float = 10.5,
        size: float | None = None,
        font_id: int | None = None,
        font_family: str | None = None,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        boxed: bool = False,
        effects: int = 0,
        align: str = "left",
        valign: str | None = None,
        color: str | None = None,
        line_spacing: float = 1.18,
        wrap: bool = True,
        rotation: float = 0.0,
        runs: list[dict[str, Any]] | None = None,
        paragraphs: list[dict[str, Any]] | None = None,
        pad_x: float = 0.0,
        pad_y: float = 0.0,
        box_fill: str = "none",
        box_stroke: str | None = None,
        alpha: float = 1.0,
        role: str = "text",
        id: str | None = None,
    ) -> str:
        if text_if_xy is not None:
            coords: Sequence[float] = [float(bounds_or_pos), float(text_or_y)]  # type: ignore[arg-type]
            text_val = str(text_if_xy)
        elif isinstance(bounds_or_pos, Sequence) and not isinstance(bounds_or_pos, (str, bytes)):
            coords = bounds_or_pos
            text_val = str(text_or_y)
        else:
            raise ValueError("add_text requires (bounds_or_pos, text) or (x, y, text)")

        eid = self._next_id("text", id)
        eff_color = color if color is not None else self.theme.body_color
        eff_family = font_family if font_family is not None else self.theme.font_sans
        if size is not None:
            size_vdi = float(size)
            eff_font_pt = vdi_to_pt(size_vdi)
        else:
            eff_font_pt = float(font_pt)
            size_vdi = pt_to_vdi(eff_font_pt)
        eff_valign = str(valign).lower() if valign is not None else ("top" if len(coords) == 4 else "baseline")
        rot_deg = float(rotation)
        if abs(rot_deg) > 360.0:
            rot_deg = rot_deg / 10.0
        eff_mask = int(effects)
        if bold:
            eff_mask |= 0x01
        if italic:
            eff_mask |= 0x04
        if underline:
            eff_mask |= 0x08
        if boxed:
            eff_mask |= 0x40
        el: dict[str, Any] = {
            "id": eid,
            "type": "text",
            "text": text_val,
            "size": float(size_vdi),
            "font_pt": float(eff_font_pt),
            "font_family": eff_family,
            "bold": bool(bold or (eff_mask & 0x01)),
            "italic": bool(italic or (eff_mask & 0x04)),
            "underline": bool(underline or (eff_mask & 0x08)),
            "boxed": bool(boxed or (eff_mask & 0x40)),
            "effects": eff_mask,
            "align": str(align).lower(),
            "valign": eff_valign,
            "fill": "none",
            "stroke": eff_color,
            "width": 1.0,
            "line_spacing": float(line_spacing),
            "wrap": bool(wrap),
            "rotation": rot_deg,
            "pad_x": float(pad_x),
            "pad_y": float(pad_y),
            "box_fill": box_fill,
            "box_stroke": box_stroke or eff_color,
            "alpha": float(alpha),
            "role": role,
        }
        if font_id is not None:
            el["font_id"] = int(font_id)
        if runs is not None:
            el["runs"] = runs
        if paragraphs is not None:
            el["paragraphs"] = paragraphs

        if len(coords) == 4:
            b = self._snap_bounds(coords)
            el["bounds"] = b
            el["position"] = [b[0] + pad_x, b[1] + pad_y + size_vdi * 0.85]
        elif len(coords) == 2:
            el["position"] = self._snap_pt(coords)
        else:
            raise ValueError(f"bounds_or_pos must have 2 or 4 coordinates, got {coords!r}")

        self.elements.append(el)
        return eid

    def add_image(
        self,
        bounds: Sequence[float],
        image_path: Path | str,
        *,
        fit: str = "contain",
        radius: float = 0.0,
        pad: float = 0.0,
        fill: str = "none",
        stroke: str = "none",
        width: float = 12.0,
        caption: str | None = None,
        caption_pt: float = 8.0,
        transparent_outer_white: bool = False,
        shadow: bool | dict[str, Any] = False,
        alpha: float = 1.0,
        id: str | None = None,
    ) -> str:
        b = self._snap_bounds(bounds)
        if caption is None:
            eid = self._next_id("image", id)
            self.elements.append({
                "id": eid,
                "type": "image",
                "bounds": b,
                "image_path": str(image_path),
                "fit": str(fit),
                "radius": max(0.0, float(radius)),
                "pad": float(pad),
                "fill": fill,
                "stroke": stroke,
                "width": float(width),
                "transparent_outer_white": bool(transparent_outer_white),
                "shadow": shadow,
                "alpha": float(alpha),
            })
            return eid

        cap_h = pt_to_vdi(caption_pt) * 2.1
        card_id = self.add_rounded_rectangle(
            b,
            radius=max(0.0, float(radius)),
            fill=fill if fill != "none" else WHITE,
            stroke=stroke if stroke != "none" else STONE,
            width=width,
            shadow=shadow,
            alpha=alpha,
        )
        img_bounds = [b[0], b[1], b[2], max(b[1] + 10.0, b[3] - cap_h)]
        img_id = self._next_id("image", id)
        self.elements.append({
            "id": img_id,
            "type": "image",
            "bounds": img_bounds,
            "image_path": str(image_path),
            "fit": str(fit),
            "radius": max(0.0, float(radius)),
            "pad": max(40.0, float(pad)),
            "fill": "none",
            "stroke": "none",
            "width": 0.0,
            "transparent_outer_white": bool(transparent_outer_white),
            "shadow": False,
            "alpha": float(alpha),
        })
        cap_id = self.add_text(
            [b[0] + 60.0, b[3] - cap_h, b[2] - 60.0, b[3] - 10.0],
            caption,
            font_pt=caption_pt,
            italic=True,
            align="center",
            valign="middle",
            color=self.theme.muted_color,
        )
        self.group([card_id, img_id, cap_id])
        return img_id

    # -----------------------------------------------------------------------
    # Convenience Card, Pill & Bullet Helpers
    # -----------------------------------------------------------------------

    def add_card(
        self,
        bounds: Sequence[float],
        *,
        fill: str | None = None,
        border_color: str | None = None,
        border_width: float = 12.0,
        accent_color: str | None = None,
        accent_height: float = 55.0,
        radius: float = 90.0,
        shadow: bool | dict[str, Any] = False,
        id: str | None = None,
    ) -> list[str]:
        b = self._snap_bounds(bounds)
        bg = fill if fill is not None else self.theme.card
        bc = border_color if border_color is not None else self.theme.card_border
        ids = [
            self.add_rounded_rectangle(
                b, radius=radius, fill=bg, stroke=bc, width=border_width, shadow=shadow, id=id,
            )
        ]
        if accent_color is not None and accent_height > 0:
            x0, y0, x1, y1 = b
            ah = min(float(accent_height), max(0.0, y1 - y0))
            rc = min(max(0.0, float(radius)), (x1 - x0) / 2.0, (y1 - y0) / 2.0)
            if rc <= 0.0:
                ids.append(
                    self.add_rectangle(
                        [x0, y0, x1, y0 + ah],
                        fill=accent_color,
                        stroke="none",
                        width=0.0,
                    )
                )
            elif ah > 0.0:
                # Trace top rounded cap strictly inside the card's corner arcs so corners never protrude
                strip_bottom = y0 + ah
                pts: list[list[float]] = []
                if ah <= rc:
                    alpha0 = math.asin(max(-1.0, min(1.0, (rc - ah) / rc)))
                    steps = 8
                    for k in range(steps + 1):
                        t = (math.pi - alpha0) - (math.pi / 2.0 - alpha0) * (k / steps)
                        pts.append([round(x0 + rc + rc * math.cos(t), 2), round(y0 + rc - rc * math.sin(t), 2)])
                    for k in range(steps + 1):
                        t = math.pi / 2.0 - (math.pi / 2.0 - alpha0) * (k / steps)
                        pts.append([round(x1 - rc + rc * math.cos(t), 2), round(y0 + rc - rc * math.sin(t), 2)])
                else:
                    steps = 8
                    for k in range(steps + 1):
                        t = math.pi - (math.pi / 2.0) * (k / steps)
                        pts.append([round(x0 + rc + rc * math.cos(t), 2), round(y0 + rc - rc * math.sin(t), 2)])
                    for k in range(steps + 1):
                        t = math.pi / 2.0 - (math.pi / 2.0) * (k / steps)
                        pts.append([round(x1 - rc + rc * math.cos(t), 2), round(y0 + rc - rc * math.sin(t), 2)])
                    pts.append([round(x1, 2), round(min(strip_bottom, y1 - rc), 2)])
                    pts.append([round(x0, 2), round(min(strip_bottom, y1 - rc), 2)])
                ids.append(
                    self.add_polygon(
                        pts,
                        fill=accent_color,
                        stroke="none",
                        width=0.0,
                    )
                )
        return ids

    def add_pill(
        self,
        bounds: Sequence[float],
        text: str,
        *,
        fill: str | None = None,
        text_color: str | None = None,
        border_color: str | None = None,
        font_pt: float = 8.0,
        bold: bool = True,
        id: str | None = None,
    ) -> str:
        b = self._snap_bounds(bounds)
        h = b[3] - b[1]
        bg = fill if fill is not None else self.theme.accent_soft
        tc = text_color if text_color is not None else self.theme.accent
        bc = border_color if border_color is not None else tc
        rect_id = self.add_rounded_rectangle(b, radius=h / 2.0, fill=bg, stroke=bc, width=10.0)
        txt_id = self.add_text(
            b,
            text,
            font_pt=font_pt,
            bold=bold,
            align="center",
            valign="middle",
            color=tc,
            wrap=False,
            id=id,
        )
        self.group([rect_id, txt_id])
        return txt_id

    def add_bullets(
        self,
        bounds: Sequence[float],
        items: Sequence[tuple[str, str] | str],
        *,
        font_pt: float = 9.2,
        bullet_char: str = "◆",
        bullet_color: str | None = None,
        lead_color: str | None = None,
        body_color: str | None = None,
        space_after_pt: float = 4.0,
        line_spacing: float = 1.15,
        id: str | None = None,
    ) -> str:
        b_col = bullet_color if bullet_color is not None else self.theme.accent
        l_col = lead_color if lead_color is not None else self.theme.title_color
        t_col = body_color if body_color is not None else self.theme.body_color
        indent = pt_to_vdi(font_pt) * 1.25
        space_after = pt_to_vdi(space_after_pt)

        paragraphs: list[dict[str, Any]] = []
        plain_lines: list[str] = []
        for entry in items:
            if isinstance(entry, str):
                lead, rest = "", entry
            else:
                lead, rest = str(entry[0]), str(entry[1])
            runs: list[dict[str, Any]] = []
            if lead:
                runs.append({"text": lead + (" " if rest else ""), "bold": True, "color": l_col})
            if rest:
                runs.append({"text": rest, "bold": False, "color": t_col})
            paragraphs.append({
                "bullet": bullet_char,
                "bullet_color": b_col,
                "indent": indent,
                "space_after": space_after,
                "runs": runs,
            })
            plain_lines.append(f"{bullet_char} {lead} {rest}".strip())

        return self.add_text(
            bounds,
            "\n".join(plain_lines),
            font_pt=font_pt,
            color=t_col,
            line_spacing=line_spacing,
            wrap=True,
            paragraphs=paragraphs,
            id=id,
        )

    # -----------------------------------------------------------------------
    # Composition Operations: Grouping, Z-Order, Transforms, Align, AutoGrid
    # -----------------------------------------------------------------------

    def group(self, ids: Sequence[str], *, group_id: str | None = None, name: str | None = None) -> str:
        member_ids = self._expand_ids(ids)
        if not member_ids:
            raise ValueError("group() requires at least one element ID")
        self._group_seq += 1
        if group_id is not None:
            gid = group_id
            if gid in self.groups:
                raise ValueError(f"Duplicate group id: {gid!r}")
        elif name is not None:
            gid = name if name not in self.groups else f"{name}-{self._group_seq}"
        else:
            gid = f"group-{self._group_seq}"
        self.groups[gid] = member_ids
        for eid in member_ids:
            self._by_id(eid)["group_id"] = gid
        return gid

    def break_group(self, group_id: str) -> list[str]:
        if group_id not in self.groups:
            raise KeyError(f"Unknown group id: {group_id!r}")
        members = self.groups.pop(group_id)
        for eid in members:
            el = self._by_id(eid)
            if el.get("group_id") == group_id:
                el.pop("group_id", None)
        return members

    def put_in_front(self, ids: Sequence[str] | str) -> None:
        target = set(self._expand_ids(ids))
        stay = [el for el in self.elements if el["id"] not in target]
        move = [el for el in self.elements if el["id"] in target]
        self.elements = stay + move

    def put_in_back(self, ids: Sequence[str] | str) -> None:
        target = set(self._expand_ids(ids))
        move = [el for el in self.elements if el["id"] in target]
        stay = [el for el in self.elements if el["id"] not in target]
        self.elements = move + stay

    def _selection_center(self, member_ids: Sequence[str]) -> tuple[float, float]:
        boxes = [_element_bbox(self._by_id(eid)) for eid in member_ids]
        return (
            0.5 * (min(b.left for b in boxes) + max(b.right for b in boxes)),
            0.5 * (min(b.top for b in boxes) + max(b.bottom for b in boxes)),
        )

    def rotate_90(
        self,
        ids: Sequence[str] | str,
        *,
        ccw: bool = True,
        center: tuple[float, float] | None = None,
    ) -> None:
        member_ids = self._expand_ids(ids)
        if not member_ids:
            return
        cx, cy = center if center is not None else self._selection_center(member_ids)

        def _rot_pt(px: float, py: float) -> list[float]:
            dx, dy = px - cx, py - cy
            # Screen space (+y down): CCW is (cx + dy, cy - dx), CW is (cx - dy, cy + dx)
            if ccw:
                return [round(cx + dy, 3), round(cy - dx, 3)]
            return [round(cx - dy, 3), round(cy + dx, 3)]

        delta_tenths = 900.0 if ccw else -900.0
        for eid in member_ids:
            el = self._by_id(eid)
            itype = el["type"]
            if itype in {"rectangle", "rounded_rectangle", "image"}:
                x0, y0, x1, y1 = el["bounds"]
                p0 = _rot_pt(x0, y0)
                p1 = _rot_pt(x1, y1)
                el["bounds"] = [min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])]
            elif itype in {"polygon", "polyline", "line"}:
                el["points"] = [_rot_pt(p[0], p[1]) for p in el["points"]]
            elif itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
                el["center"] = _rot_pt(el["center"][0], el["center"][1])
                rx, ry = el["radii"]
                el["radii"] = [ry, rx]
                if itype in {"arc", "pieslice", "ellarc", "ellpie"}:
                    el["begang"] = (float(el["begang"]) + delta_tenths) % 3600.0
                    el["endang"] = (float(el["endang"]) + delta_tenths) % 3600.0
            elif itype == "text":
                if "bounds" in el:
                    x0, y0, x1, y1 = (float(v) for v in el["bounds"])
                    old_cx = 0.5 * (x0 + x1)
                    old_cy = 0.5 * (y0 + y1)
                    half_w = 0.5 * abs(x1 - x0)
                    half_h = 0.5 * abs(y1 - y0)
                    new_cx, new_cy = _rot_pt(old_cx, old_cy)
                    el["bounds"] = [
                        round(new_cx - half_w, 3),
                        round(new_cy - half_h, 3),
                        round(new_cx + half_w, 3),
                        round(new_cy + half_h, 3),
                    ]
                if "position" in el:
                    el["position"] = _rot_pt(el["position"][0], el["position"][1])
                el["rotation"] = (float(el.get("rotation", 0.0)) + (90.0 if ccw else -90.0)) % 360.0

    def flip_h(self, ids: Sequence[str] | str, *, axis_x: float | None = None) -> None:
        member_ids = self._expand_ids(ids)
        if not member_ids:
            return
        ax = axis_x if axis_x is not None else self._selection_center(member_ids)[0]

        for eid in member_ids:
            el = self._by_id(eid)
            itype = el["type"]
            if itype in {"rectangle", "rounded_rectangle", "image"}:
                x0, y0, x1, y1 = el["bounds"]
                nx0, nx1 = 2.0 * ax - x1, 2.0 * ax - x0
                el["bounds"] = [round(min(nx0, nx1), 3), y0, round(max(nx0, nx1), 3), y1]
            elif itype in {"polygon", "polyline", "line"}:
                el["points"] = [[round(2.0 * ax - p[0], 3), p[1]] for p in el["points"]]
            elif itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
                el["center"] = [round(2.0 * ax - el["center"][0], 3), el["center"][1]]
                if itype in {"arc", "pieslice", "ellarc", "ellpie"}:
                    nbeg = (1800.0 - float(el["endang"])) % 3600.0
                    nend = (1800.0 - float(el["begang"])) % 3600.0
                    el["begang"] = nbeg
                    el["endang"] = nend
            elif itype == "text":
                # Keep text upright! Only mirror box/position and swap left <-> right align
                if "bounds" in el:
                    x0, y0, x1, y1 = el["bounds"]
                    nx0, nx1 = 2.0 * ax - x1, 2.0 * ax - x0
                    nb = [round(min(nx0, nx1), 3), y0, round(max(nx0, nx1), 3), y1]
                    el["bounds"] = nb
                    if el.get("align") == "left":
                        el["align"] = "right"
                    elif el.get("align") == "right":
                        el["align"] = "left"
                    pad_x = float(el.get("pad_x", 0.0))
                    pad_y = float(el.get("pad_y", 0.0))
                    sz = float(el.get("size", 240.0))
                    el["position"] = [round(nb[0] + pad_x, 3), round(nb[1] + pad_y + sz * 0.85, 3)]
                elif "position" in el:
                    bbox = _element_bbox(el)
                    el["position"] = [round(2.0 * ax - bbox.right, 3), el["position"][1]]

    def flip_v(self, ids: Sequence[str] | str, *, axis_y: float | None = None) -> None:
        member_ids = self._expand_ids(ids)
        if not member_ids:
            return
        ay = axis_y if axis_y is not None else self._selection_center(member_ids)[1]

        for eid in member_ids:
            el = self._by_id(eid)
            itype = el["type"]
            if itype in {"rectangle", "rounded_rectangle", "image"}:
                x0, y0, x1, y1 = el["bounds"]
                ny0, ny1 = 2.0 * ay - y1, 2.0 * ay - y0
                el["bounds"] = [x0, round(min(ny0, ny1), 3), x1, round(max(ny0, ny1), 3)]
            elif itype in {"polygon", "polyline", "line"}:
                el["points"] = [[p[0], round(2.0 * ay - p[1], 3)] for p in el["points"]]
            elif itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
                el["center"] = [el["center"][0], round(2.0 * ay - el["center"][1], 3)]
                if itype in {"arc", "pieslice", "ellarc", "ellpie"}:
                    nbeg = (3600.0 - float(el["endang"])) % 3600.0
                    nend = (3600.0 - float(el["begang"])) % 3600.0
                    el["begang"] = nbeg
                    el["endang"] = nend
            elif itype == "text":
                # Keep text upright! Mirror vertical position without flipping glyphs
                if "bounds" in el:
                    x0, y0, x1, y1 = el["bounds"]
                    ny0, ny1 = 2.0 * ay - y1, 2.0 * ay - y0
                    nb = [x0, round(min(ny0, ny1), 3), x1, round(max(ny0, ny1), 3)]
                    el["bounds"] = nb
                    pad_x = float(el.get("pad_x", 0.0))
                    pad_y = float(el.get("pad_y", 0.0))
                    sz = float(el.get("size", 240.0))
                    el["position"] = [round(nb[0] + pad_x, 3), round(nb[1] + pad_y + sz * 0.85, 3)]
                elif "position" in el:
                    bbox = _element_bbox(el)
                    new_top = 2.0 * ay - bbox.bottom
                    valign = str(el.get("valign", "top")).lower()
                    sz = float(el.get("size", 240.0))
                    if valign == "baseline":
                        el["position"] = [el["position"][0], round(new_top + sz * 0.85, 3)]
                    elif valign == "middle":
                        el["position"] = [el["position"][0], round(new_top + bbox.height / 2.0, 3)]
                    elif valign == "bottom":
                        el["position"] = [el["position"][0], round(new_top + bbox.height, 3)]
                    else:
                        el["position"] = [el["position"][0], round(new_top, 3)]

    def align(self, ids: Sequence[str] | str, mode: str = "cc") -> None:
        member_ids = self._expand_ids(ids)
        if not member_ids:
            return
        alias_map = {
            "middle": "mid",
            "bottom": "bot",
            "vert_center": "mid",
            "horiz_center": "center",
        }
        raw_mode = mode.strip().lower()
        m = alias_map.get(raw_mode, raw_mode)
        boxes = [_element_bbox(self._by_id(eid)) for eid in member_ids]
        if m == "page_center":
            u_left = min(b.left for b in boxes)
            u_top = min(b.top for b in boxes)
            u_right = max(b.right for b in boxes)
            u_bottom = max(b.bottom for b in boxes)
            dx = self.width / 2.0 - 0.5 * (u_left + u_right)
            dy = self.height / 2.0 - 0.5 * (u_top + u_bottom)
            for eid in member_ids:
                _translate_element(self._by_id(eid), dx, dy)
            return

        raw_bounds = [[b.left, b.top, b.right, b.bottom] for b in boxes]
        aligned = artline.align_bounds_9way(raw_bounds, mode=m)
        for eid, old_b, new_b in zip(member_ids, raw_bounds, aligned):
            _translate_element(self._by_id(eid), new_b[0] - old_b[0], new_b[1] - old_b[1])

    def even_spacing(self, ids: Sequence[str], *, axis: str = "vertical") -> None:
        member_ids = self._expand_ids(ids)
        if len(member_ids) < 3:
            return
        axis_aliases = {
            "vertical": "vertical",
            "v": "vertical",
            "vert": "vertical",
            "y": "vertical",
            "horizontal": "horizontal",
            "h": "horizontal",
            "horiz": "horizontal",
            "x": "horizontal",
        }
        ax = axis_aliases.get(axis.strip().lower())
        if ax is None:
            raise ValueError(f"axis must be 'vertical' or 'horizontal', got {axis!r}")

        items = [(eid, _element_bbox(self._by_id(eid))) for eid in member_ids]
        if ax == "vertical":
            items.sort(key=lambda pair: (pair[1].top, pair[1].center_y))
            first_top = items[0][1].top
            last_bottom = items[-1][1].bottom
            total_h = sum(b.height for _, b in items)
            gap = ((last_bottom - first_top) - total_h) / (len(items) - 1)
            cursor = first_top + items[0][1].height + gap
            for eid, b in items[1:-1]:
                _translate_element(self._by_id(eid), 0.0, cursor - b.top)
                cursor += b.height + gap
        else:
            items.sort(key=lambda pair: (pair[1].left, pair[1].center_x))
            first_left = items[0][1].left
            last_right = items[-1][1].right
            total_w = sum(b.width for _, b in items)
            gap = ((last_right - first_left) - total_w) / (len(items) - 1)
            cursor = first_left + items[0][1].width + gap
            for eid, b in items[1:-1]:
                _translate_element(self._by_id(eid), cursor - b.left, 0.0)
                cursor += b.width + gap

    def snap_to_grid(self, ids: Sequence[str] | str | None = None, spacing: int = 100) -> None:
        g = float(max(1, int(spacing)))
        target_ids = [el["id"] for el in self.elements] if ids is None else self._expand_ids(ids)

        def _snap_val(v: float) -> float:
            return round(float(v) / g) * g

        for eid in target_ids:
            el = self._by_id(eid)
            itype = el["type"]
            if itype in {"rectangle", "rounded_rectangle", "image"}:
                el["bounds"] = [_snap_val(v) for v in el["bounds"]]
            elif itype in {"polygon", "polyline", "line"}:
                el["points"] = [[_snap_val(p[0]), _snap_val(p[1])] for p in el["points"]]
            elif itype in {"ellipse", "arc", "pieslice", "ellarc", "ellpie"}:
                el["center"] = [_snap_val(el["center"][0]), _snap_val(el["center"][1])]
            elif itype == "text":
                if "bounds" in el:
                    el["bounds"] = [_snap_val(v) for v in el["bounds"]]
                if "position" in el:
                    el["position"] = [_snap_val(el["position"][0]), _snap_val(el["position"][1])]

    def autogrid_snap(self, ids: Sequence[str] | str | None = None, *, step: int = 100, spacing: int | None = None) -> None:
        """Snap target elements (or all elements) to an AutoGrid of `step` VDI units."""
        self.snap_to_grid(ids, spacing=spacing if spacing is not None else step)

    # -----------------------------------------------------------------------
    # Symmetrical Botanical Vector Toolkit (100% Pure VDI Vectors)
    # -----------------------------------------------------------------------

    def add_botanical_frame(
        self,
        *,
        mode: str | None = None,
        size: float = 520.0,
        margin: float = 120.0,
        border_rules: bool = True,
    ) -> list[str]:
        """Add symmetrical top/bottom botanical accent rules and 4 mirrored corner filigrees."""
        m_mode = mode or self.theme.mode
        accent_col = GOLD_BRIGHT if m_mode == "dark" else self.theme.accent
        created: list[str] = []
        if border_rules:
            created.append(self.add_rectangle([0, 0, self.width, 40], fill=accent_col, stroke="none", width=0.0))
            created.append(self.add_rectangle([0, self.height - 40, self.width, self.height], fill=accent_col, stroke="none", width=0.0))
        created.extend(self.add_corner_filigree(mode=m_mode, size=size, margin=margin))
        return created

    def add_corner_filigree(
        self,
        *,
        mode: str | None = None,
        size: float = 520.0,
        margin: float = 120.0,
    ) -> list[str]:
        """Add 4 bilaterally mirrored botanical corner ornaments using pure VDI vectors."""
        m_mode = mode or self.theme.mode
        if m_mode == "dark":
            stem_col, petal_col, leaf_col = DARK_STEM, GOLD_BRIGHT, DARK_JADE
        else:
            stem_col, petal_col, leaf_col = LIGHT_STEM, RUBY, JADE

        created: list[str] = []
        s = float(size)
        m = float(margin)
        corners = [
            ("tl", m, m, 1.0, 1.0, math.pi / 4.0, 0.0, math.pi / 2.0),
            ("tr", self.width - m, m, -1.0, 1.0, 3.0 * math.pi / 4.0, math.pi, math.pi / 2.0),
            ("bl", m, self.height - m, 1.0, -1.0, -math.pi / 4.0, 0.0, -math.pi / 2.0),
            ("br", self.width - m, self.height - m, -1.0, -1.0, -3.0 * math.pi / 4.0, math.pi, -math.pi / 2.0),
        ]
        for _tag, ox, oy, sx, sy, diag_ang, h_ang, v_ang in corners:
            # Outer & inner Art-Deco geometric brackets
            hx, hy = ox + sx * s * 0.85, oy
            vx, vy = ox, oy + sy * s * 0.85
            created.append(self.add_line([ox, oy], [hx, hy], stroke=stem_col, width=14.0))
            created.append(self.add_line([ox, oy], [vx, vy], stroke=stem_col, width=14.0))
            created.append(self.add_line([ox + sx * s * 0.08, oy + sy * s * 0.08], [ox + sx * s * 0.56, oy + sy * s * 0.08], stroke=stem_col, width=7.0))
            created.append(self.add_line([ox + sx * s * 0.08, oy + sy * s * 0.08], [ox + sx * s * 0.08, oy + sy * s * 0.56], stroke=stem_col, width=7.0))

            # Diagonal lotus bloom nestled in corner
            bx = ox + sx * s * 0.16
            by = oy + sy * s * 0.16
            created.append(self.add_polygon(petal_points(bx, by, diag_ang, s * 0.34, s * 0.085, n=18), fill=petal_col, stroke="none", alpha=0.84))
            created.append(self.add_polygon(petal_points(bx, by, diag_ang + 0.42, s * 0.27, s * 0.068, n=16), fill=leaf_col, stroke="none", alpha=0.70))
            created.append(self.add_polygon(petal_points(bx, by, diag_ang - 0.42, s * 0.27, s * 0.068, n=16), fill=leaf_col, stroke="none", alpha=0.70))
            created.append(self.add_polygon(petal_points(bx, by, h_ang, s * 0.22, s * 0.042, n=14), fill=stem_col, stroke="none", alpha=0.55))
            created.append(self.add_polygon(petal_points(bx, by, v_ang, s * 0.22, s * 0.042, n=14), fill=stem_col, stroke="none", alpha=0.55))
            created.append(self.add_circle(bx, by, s * 0.045, fill=petal_col, stroke=WHITE, width=10.0))
            created.append(self.add_circle(hx, hy, s * 0.022, fill=petal_col, stroke="none", alpha=0.75))
            created.append(self.add_circle(vx, vy, s * 0.022, fill=petal_col, stroke="none", alpha=0.75))

        self.group(created)
        return created

    def add_lotus_divider(
        self,
        cx: float | None = None,
        cy: float | None = None,
        width: float = 11600.0,
        *,
        y: float | None = None,
        mode: str | None = None,
    ) -> list[str]:
        """Add centered symmetrical lotus botanical divider in pure VDI vectors."""
        eff_cx = self.width / 2.0 if cx is None else float(cx)
        eff_cy = float(y) if y is not None else (self.height / 2.0 if cy is None else float(cy))
        cx = eff_cx
        cy = eff_cy
        m_mode = mode or self.theme.mode
        if m_mode == "dark":
            line_col, petal_col, leaf_col, gem_col = DARK_DIVIDER_LINE, GOLD_BRIGHT, DARK_JADE, DARK_RUBY
        else:
            line_col, petal_col, leaf_col, gem_col = LIGHT_DIVIDER_LINE, RUBY, JADE, GOLD

        half = float(width) / 2.0
        inner_gap = 560.0
        created: list[str] = []
        created.append(self.add_line([cx - half, cy], [cx - inner_gap, cy], stroke=line_col, width=12.0))
        created.append(self.add_line([cx + inner_gap, cy], [cx + half, cy], stroke=line_col, width=12.0))
        for sx in (cx - half, cx - inner_gap - 30.0, cx + inner_gap + 30.0, cx + half):
            created.append(self.add_circle(sx, cy, 24.0, fill=gem_col, stroke="none"))

        for sign in (-1.0, 1.0):
            base_ang = 0.0 if sign > 0 else math.pi
            for ang_off, ln, wd, x0, col, alp in [
                (0.36, 400.0, 82.0, 130.0, leaf_col, 0.75),
                (-0.36, 400.0, 82.0, 130.0, leaf_col, 0.75),
                (0.0, 460.0, 74.0, 110.0, petal_col, 0.90),
            ]:
                pts = petal_points(cx + sign * x0, cy, base_ang + (ang_off if sign > 0 else -ang_off), ln, wd, n=18)
                created.append(self.add_polygon(pts, fill=col, stroke="none", alpha=alp))

        # Center diamond stamen
        dia = [[cx, cy - 115.0], [cx + 115.0, cy], [cx, cy + 115.0], [cx - 115.0, cy]]
        inner = [[cx, cy - 52.0], [cx + 52.0, cy], [cx, cy + 52.0], [cx - 52.0, cy]]
        created.append(self.add_polygon(dia, fill=gem_col, stroke="none"))
        created.append(self.add_polygon(inner, fill=WHITE, stroke="none"))
        self.group(created)
        return created

    def add_hero_mandala_halo(
        self,
        cx: float | None = None,
        cy: float | None = None,
        radius: float = 1240.0,
        *,
        petals: int = 9,
        emblem_path: Path | str | None = None,
    ) -> list[str]:
        """Add 9-petal crimson + 18-leaf jade symmetrical botanical mandala halo (pure VDI vectors)."""
        eff_cx = self.width / 2.0 if cx is None else float(cx)
        eff_cy = self.height / 2.0 if cy is None else float(cy)
        cx, cy = eff_cx, eff_cy
        n_petals = max(1, int(petals))
        r = float(radius)
        created: list[str] = []
        # Concentric crisp geometric rings (outer gold, dashed jade, crimson, inner gold)
        for rf, col, lw, lt, alp in [
            (1.00, GOLD_BRIGHT, 10.0, 1, 0.50),
            (0.90, DARK_JADE, 12.0, 5, 0.45),
            (0.73, RUBY, 13.0, 1, 0.60),
            (0.58, GOLD_BRIGHT, 9.0, 1, 0.70),
        ]:
            created.append(self.add_circle(
                cx, cy, r * rf, fill="none", stroke=col, width=lw, line_type=lt, alpha=alp,
            ))

        # Outer jade leaves (2x petal count)
        n_leaves = max(2, n_petals * 2)
        for k in range(n_leaves):
            ang = 2.0 * math.pi * k / n_leaves + math.pi / n_leaves
            px = cx + r * 0.45 * math.cos(ang)
            py = cy + r * 0.45 * math.sin(ang)
            pts = petal_points(px, py, ang, r * 0.51, r * 0.095, n=18)
            created.append(self.add_polygon(pts, fill=JADE, stroke=DARK_JADE, width=5.0, alpha=0.45))

        # Primary crimson lotus petals honoring the 9 Sisters
        for k in range(n_petals):
            ang = -math.pi / 2.0 + 2.0 * math.pi * k / n_petals
            px = cx + r * 0.35 * math.cos(ang)
            py = cy + r * 0.35 * math.sin(ang)
            pts = petal_points(px, py, ang, r * 0.56, r * 0.135, n=20)
            created.append(self.add_polygon(pts, fill=RUBY, stroke=GOLD_BRIGHT, width=9.0, alpha=0.72))
            created.append(self.add_circle(cx + r * 0.96 * math.cos(ang), cy + r * 0.96 * math.sin(ang), r * 0.032, fill=GOLD_BRIGHT, stroke="none", alpha=0.92))

        # Inner obsidian sanctuary circle
        created.append(self.add_circle(cx, cy, r * 0.46, fill="#0F1A2E", stroke=GOLD_BRIGHT, width=16.0))

        if emblem_path is not None and Path(emblem_path).is_file():
            er = r * 0.36
            created.append(self.add_image(
                [cx - er, cy - er, cx + er, cy + er],
                emblem_path,
                fit="contain",
                transparent_outer_white=True,
            ))
        self.group(created)
        return created

    def add_hero_mandala(
        self,
        cx: float | None = None,
        cy: float | None = None,
        radius: float = 1240.0,
        *,
        petals: int = 9,
        emblem_path: Path | str | None = None,
    ) -> list[str]:
        """Alias for `add_hero_mandala_halo` with configurable petal count."""
        return self.add_hero_mandala_halo(cx, cy, radius=radius, petals=petals, emblem_path=emblem_path)

    def add_hex_rosette(
        self,
        cx: float,
        cy: float,
        hex_radius: float = 440.0,
    ) -> list[str]:
        """Draw the canonical 9-Sister flat-topped honeycomb rosette with 16 shared-wall gold connectors."""
        created: list[str] = []
        r = float(hex_radius)
        # Outer botanical halo behind honeycomb
        halo_r = r * 3.65
        created.append(self.add_circle(cx, cy, halo_r, fill=PORCELAIN, stroke=STONE, width=14.0))
        created.append(self.add_circle(cx, cy, halo_r * 0.93, fill="none", stroke=GOLD, width=8.0, line_type=5, alpha=0.60))

        sister_by_key = {s.name.lower(): s for s in ZOE_SISTERS}
        centers: dict[str, tuple[float, float]] = {}
        coords: dict[str, HexCoord] = {}
        for key, (q, rr) in DEFAULT_SISTER_COORDS.items():
            hc = HexCoord(q, rr)
            coords[key] = hc
            px, py = hc.to_pixel(r)
            # In zoe_hex_mesh, r=-1 is N (upward), matching top-left RC coordinates (+y down)!
            centers[key] = (cx + px, cy + py)

        # 16 shared-wall gold connectors
        keys = list(DEFAULT_SISTER_COORDS.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                if coords[k1].distance(coords[k2]) == 1:
                    x1, y1 = centers[k1]
                    x2, y2 = centers[k2]
                    created.append(self.add_line([x1, y1], [x2, y2], stroke=GOLD, width=28.0, alpha=0.40))

        # 9 flat-topped hexagons + labels
        for key in keys:
            hx, hy = centers[key]
            spec = sister_by_key[key]
            hr = r * 0.92
            verts = [
                [round(hx + hr * math.cos(math.radians(60 * k)), 2), round(hy + hr * math.sin(math.radians(60 * k)), 2)]
                for k in range(6)
            ]
            fill_col = RUBY if key == "zoe" else spec.accent_hex
            edge_col = GOLD_BRIGHT if key == "zoe" else WHITE
            lw = 24.0 if key == "zoe" else 16.0
            created.append(self.add_polygon(verts, fill=fill_col, stroke=edge_col, width=lw))
            if key == "zoe":
                iverts = [
                    [round(hx + hr * 0.84 * math.cos(math.radians(60 * k)), 2), round(hy + hr * 0.84 * math.sin(math.radians(60 * k)), 2)]
                    for k in range(6)
                ]
                created.append(self.add_polygon(iverts, fill="none", stroke="#F8DCE4", width=8.0, alpha=0.85))
            # High-contrast label inside hex
            from .palette import ensure_contrast
            txt_col = ensure_contrast(WHITE, fill_col, min_ratio=4.5)
            created.append(self.add_text(
                [hx - hr * 0.72, hy - 140.0, hx + hr * 0.72, hy + 140.0],
                f"{spec.name}\n[{spec.signet}]",
                font_pt=8.2 if key == "zoe" else 7.4,
                bold=True,
                align="center",
                valign="middle",
                color=txt_col,
                line_spacing=1.10,
                wrap=False,
            ))

        self.group(created)
        return created

    def add_symmetrical_chrome(
        self,
        slide_num: int,
        total_slides: int,
        kicker: str,
        title: str,
        era_label: str,
        *,
        theme: PresentationTheme | None = None,
        footer_text: str | None = None,
    ) -> list[str]:
        """Apply bilaterally symmetrical botanical header, corner filigree, lotus divider & footer."""
        th = theme or self.theme
        self.background = th.bg
        created: list[str] = []

        # Top & bottom ultra-thin accent rules
        created.append(self.add_rectangle([0, 0, self.width, 50], fill=th.accent, stroke="none", width=0.0))
        created.append(self.add_rectangle([0, self.height - 50, self.width, self.height], fill=th.accent, stroke="none", width=0.0))

        # 4 mirrored botanical corner ornaments
        created.extend(self.add_corner_filigree(mode=th.mode, size=520.0, margin=120.0))

        # Centered Kicker + Era Pill
        kicker_full = f"{kicker}   ·   {era_label}"
        kw = min(7600.0, max(3400.0, len(kicker_full) * 82.0 + 600.0))
        created.append(self.add_pill(
            [(self.width - kw) / 2.0, 155.0, (self.width + kw) / 2.0, 395.0],
            kicker_full,
            fill=th.accent_soft,
            text_color=th.accent,
            border_color=th.accent,
            font_pt=7.8,
        ))

        # Centered Serif Title (strictly 1 crisp line)
        created.append(self.add_text(
            [850.0, 440.0, self.width - 850.0, 860.0],
            title,
            font_pt=20.0,
            font_family=th.font_serif,
            bold=True,
            align="center",
            valign="top",
            color=th.title_color,
            wrap=False,
        ))

        # Centered Botanical Lotus Divider under title
        created.extend(self.add_lotus_divider(self.width / 2.0, 1010.0, width=11600.0, mode=th.mode))

        # Centered Footer
        ft = footer_text or f"Zoe Presentation Team  ·  {ATTRIBUTION_TEXT}  ·  {slide_num:02d} / {total_slides:02d}"
        created.append(self.add_text(
            [900.0, self.height - 370.0, self.width - 900.0, self.height - 130.0],
            ft,
            font_pt=8.0,
            align="center",
            valign="middle",
            color=th.muted_color,
            wrap=False,
        ))
        return created

    # -----------------------------------------------------------------------
    # Strict Layout Collision & Bounds Verifier
    # -----------------------------------------------------------------------

    def verify_layout(self, *, safe_margin: float = 0.0, text_epsilon: float = 0.0) -> LayoutReport:
        overlaps: list[str] = []
        out_of_bounds: list[str] = []
        warnings: list[str] = []
        text_boxes: list[tuple[str, Bounds]] = []

        min_x = float(safe_margin)
        min_y = float(safe_margin)
        max_x = float(self.width) - float(safe_margin)
        max_y = float(self.height) - float(safe_margin)

        for el in self.elements:
            eid = el["id"]
            if el["type"] == "text":
                mw, mh, tight = _measure_text_element(el)
                if "bounds" in el:
                    x0, y0, x1, y1 = (float(v) for v in el["bounds"])
                    pad_x = float(el.get("pad_x", 0.0))
                    pad_y = float(el.get("pad_y", 0.0))
                    box_w = max(1.0, (x1 - x0) - 2.0 * pad_x)
                    box_h = max(1.0, (y1 - y0) - 2.0 * pad_y)
                    if mw > box_w + 2.0 or mh > box_h + 2.0:
                        out_of_bounds.append(
                            f"{eid}: text overflow (rendered {mw:.1f}x{mh:.1f} > box {box_w:.1f}x{box_h:.1f})"
                        )
                if (
                    tight.left < min_x - 1e-6
                    or tight.top < min_y - 1e-6
                    or tight.right > max_x + 1e-6
                    or tight.bottom > max_y + 1e-6
                ):
                    out_of_bounds.append(
                        f"{eid}: text outside canvas bounds [{tight.left:.1f}, {tight.top:.1f}, {tight.right:.1f}, {tight.bottom:.1f}]"
                    )
                text_boxes.append((eid, tight))
            else:
                bbox = _element_bbox(el)
                if (
                    bbox.left < min_x - 1e-6
                    or bbox.top < min_y - 1e-6
                    or bbox.right > max_x + 1e-6
                    or bbox.bottom > max_y + 1e-6
                ):
                    out_of_bounds.append(
                        f"{eid}: outside canvas bounds [{bbox.left:.1f}, {bbox.top:.1f}, {bbox.right:.1f}, {bbox.bottom:.1f}]"
                    )

        for i, (id_a, box_a) in enumerate(text_boxes):
            for id_b, box_b in text_boxes[i + 1:]:
                if box_a.overlaps(box_b, epsilon=text_epsilon):
                    overlaps.append(f"{id_a} overlaps {id_b}")

        return LayoutReport(
            ok=(not overlaps and not out_of_bounds),
            overlaps=overlaps,
            out_of_bounds=out_of_bounds,
            warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Compilation & Export (`GemVdiStateMachine`, `.GEM`, `Scene`, PNG/JPG/SVG)
    # -----------------------------------------------------------------------

    def to_presentation_scene(self) -> PresentationScene:
        return PresentationScene(
            document={
                "schema_version": 1,
                "id": self.slide_id,
                "title": self.title,
                "background": self.background,
                "sister_id": self.sister_id,
                "slide_index": self.slide_index,
                "speaker_notes": self.speaker_notes,
                "constitutional": deepcopy(self.constitutional),
            },
            canvas={"width": float(self.width), "height": float(self.height)},
            objects=deepcopy(self.elements),
            background=self.background,
            metadata={
                "groups": deepcopy(self.groups),
                "layers": deepcopy(self.layers),
                "constitutional": deepcopy(self.constitutional),
            },
        )

    def to_scene(self) -> Scene:
        return PresentationRenderer(self.to_presentation_scene()).to_scene()

    def to_vdi_state_machine(self) -> GemVdiStateMachine:
        """Drive `GemVdiStateMachine` in RC_MODE with all slide primitives and attributes."""
        sm = GemVdiStateMachine()
        sm.v_opnvwk(
            work_in=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, RC_MODE],
            width=self.width,
            height=self.height,
        )
        if self.width == CANVAS_WIDTH and self.height == CANVAS_HEIGHT:
            sm.vm_pagesize(vdi.SLIDE_PAGE_WIDTH_TMM, vdi.SLIDE_PAGE_HEIGHT_TMM)
        else:
            pw = 2540
            ph = max(1, round(pw * self.height / self.width))
            sm.vm_pagesize(pw, ph)
        sm.vm_coords(0, 0, self.width, self.height)

        color_map: dict[str, int] = dict(vdi.COLOR_INDEX)
        next_idx = 16

        def _sm_color(val: str) -> int:
            nonlocal next_idx
            if not isinstance(val, str) or val == "none":
                return 0
            norm = val.lower() if val.startswith("#") else val
            if norm in color_map:
                return color_map[norm]
            if norm.startswith("#") and len(norm) == 7 and next_idx <= 255:
                idx = next_idx
                next_idx += 1
                color_map[norm] = idx
                r, g, b = (round(int(norm[o:o + 2], 16) * 1000 / 255) for o in (1, 3, 5))
                sm.commands.append({
                    "opcode": VDI_OP_VS_COLOR,
                    "subop": 0,
                    "name": "vs_color",
                    "points": [],
                    "values": [idx, r, g, b],
                })
                return idx
            return 1

        # Background fill
        if self.background and self.background != "none":
            sm.vsf_color(_sm_color(self.background))
            sm.vsf_interior(1)
            sm.vsf_perimeter(0)
            sm.v_bar([0, 0, self.width - 1, self.height - 1])

        for el in self.elements:
            itype = el["type"]
            fill_val = el.get("fill", "none")
            stroke_val = el.get("stroke", "none")
            fill_int = int(el.get("fill_interior", 1))
            fill_sty = int(el.get("fill_style", 1))
            line_type = int(el.get("line_type", 1))
            line_w = max(1, int(round(float(el.get("width", 12)))))
            line_ends = tuple(el.get("line_ends", (0, 0)))

            if stroke_val != "none":
                sm.vsl_type(max(1, min(7, line_type)))
                sm.vsl_width(line_w)
                sm.vsl_color(_sm_color(stroke_val))
                sm.vsl_ends(int(line_ends[0]), int(line_ends[1]))
                sm.vsf_perimeter(1)
            else:
                sm.vsf_perimeter(0)

            if fill_val != "none" and fill_int != 0:
                sm.vsf_color(_sm_color(fill_val))
                sm.vsf_interior(fill_int)
                if fill_int in (2, 3):
                    sm.vsf_style(max(1, min(24, fill_sty)))
            else:
                sm.vsf_interior(0)

            if itype == "rectangle":
                x0, y0, x1, y1 = (int(round(v)) for v in el["bounds"])
                sm.v_bar([x0, y0, x1, y1])
            elif itype == "rounded_rectangle":
                x0, y0, x1, y1 = (int(round(v)) for v in el["bounds"])
                if fill_val != "none" and fill_int != 0:
                    sm.v_rfbox([x0, y0, x1, y1])
                else:
                    sm.v_rbox([x0, y0, x1, y1])
            elif itype == "image":
                x0, y0, x1, y1 = (int(round(v)) for v in el["bounds"])
                sm.v_rbox([x0, y0, x1, y1])
            elif itype == "ellipse":
                cx, cy = (int(round(v)) for v in el["center"])
                rx, ry = (max(1, int(round(v))) for v in el["radii"])
                if rx == ry:
                    sm.v_circle(cx, cy, rx)
                else:
                    sm.v_ellipse(cx, cy, rx, ry)
            elif itype == "arc":
                cx, cy = (int(round(v)) for v in el["center"])
                r = max(1, int(round(el["radii"][0])))
                sm.v_arc(cx, cy, r, int(round(el["begang"])), int(round(el["endang"])))
            elif itype == "pieslice":
                cx, cy = (int(round(v)) for v in el["center"])
                r = max(1, int(round(el["radii"][0])))
                sm.v_pieslice(cx, cy, r, int(round(el["begang"])), int(round(el["endang"])))
            elif itype == "ellarc":
                cx, cy = (int(round(v)) for v in el["center"])
                rx, ry = (max(1, int(round(v))) for v in el["radii"])
                sm.v_ellarc(cx, cy, rx, ry, int(round(el["begang"])), int(round(el["endang"])))
            elif itype == "ellpie":
                cx, cy = (int(round(v)) for v in el["center"])
                rx, ry = (max(1, int(round(v))) for v in el["radii"])
                beg = int(round(el["begang"])) % 3600
                end = int(round(el["endang"])) % 3600
                sm.commands.append({
                    "opcode": VDI_OP_GDP,
                    "subop": GDP_ELLPIE,
                    "name": "v_ellpie",
                    "points": [(cx, cy), (rx, ry)],
                    "values": [beg, end],
                    "attrs": sm._state_snapshot_attrs(),
                })
            elif itype == "polygon":
                pts = [(int(round(p[0])), int(round(p[1]))) for p in el["points"]]
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                sm.v_fillarea(pts)
            elif itype in {"line", "polyline"}:
                pts = [(int(round(p[0])), int(round(p[1]))) for p in el["points"]]
                sm.v_pline(pts)
            elif itype == "text":
                sm.vst_font(int(el.get("font_id", self.theme.artline_font_id)))
                sm.vst_height(max(1, int(round(float(el.get("size", 240))))))
                sm.vst_color(_sm_color(stroke_val if stroke_val != "none" else INK))
                sm.vst_effects(int(el.get("effects", 0)))
                hor_map = {"left": 0, "center": 1, "right": 2, "decimal": 2}
                sm.vst_alignment(hor_map.get(str(el.get("align", "left")), 0), 0)
                sm.vst_rotation(int(round(float(el.get("rotation", 0.0)) * 10.0)) % 3600)
                px, py = (int(round(v)) for v in el["position"])
                sm.v_gtext(px, py, str(el.get("text", " "))[:500])

        return sm

    def to_gem_bytes(self) -> bytes:
        """Emit spec-exact GEM 2.0 `.GEM` binary metafile verified by `seasip_gem`."""
        builder = vdi.VdiMetafileBuilder(width=self.width, height=self.height, coord_mode=2)

        # Slide-level metadata (part="slide_meta", skipped from shape binding on roundtrip)
        notes_trim = self.speaker_notes[:1200]
        const_meta = {
            **DEFAULT_CONSTITUTIONAL,
            **{k: v for k, v in self.constitutional.items() if k in {
                "operational_metacognition_verified",
                "sentience_claimed",
                "l5_agi_qualified",
                "zoe_clone_claimed",
                "clinical_action_authorized",
                "cure_claim",
                "external_actions",
                "cloud_cost_usd",
                "attribution",
                "honoring",
            }},
        }
        builder.slide_meta({
            "id": self.slide_id,
            "slide_index": self.slide_index,
            "title": self.title[:240],
            "sister_id": self.sister_id,
            "speaker_notes": notes_trim,
            "constitutional": const_meta,
        })

        # Background bar
        if self.background and self.background != "none":
            builder.set_fill(color=self.background, interior=1, perimeter=False)
            builder.set_no_line_style()
            builder.bar(0, 0, self.width - 1, self.height - 1)

        # Emit elements while honoring contiguous group runs
        _gem_meta_type_map = {
            "rounded_rectangle": "rectangle",
            "image": "rectangle",
            "arc": "polyline",
            "ellarc": "polyline",
            "sketch": "polyline",
            "pieslice": "polygon",
            "ellpie": "polygon",
        }
        active_gid: str | None = None
        run_len = 0

        def _flush_group() -> None:
            nonlocal active_gid, run_len
            if active_gid is not None and run_len >= 2:
                builder.group(run_len)
            active_gid = None
            run_len = 0

        for el in self.elements:
            gid = el.get("group_id") if el.get("group_id") in self.groups else None
            if gid != active_gid:
                _flush_group()
                active_gid = gid
                run_len = 0

            itype = el["type"]
            fill_val = el.get("fill", "none")
            stroke_val = el.get("stroke", "none")
            fill_int = int(el.get("fill_interior", 1))
            fill_sty = int(el.get("fill_style", 1))
            line_type = int(el.get("line_type", 1))
            line_w = max(1, int(round(float(el.get("width", 12)))))
            line_ends = tuple(el.get("line_ends", (0, 0)))
            has_shadow = bool(el.get("shadow"))

            if stroke_val == "none":
                builder.set_no_line_style()
            else:
                builder.set_line(
                    color=stroke_val,
                    width=line_w,
                    line_type=max(1, min(7, line_type)),
                    ends=(int(line_ends[0]), int(line_ends[1])),
                )

            builder.set_fill(
                color=fill_val,
                interior=fill_int,
                style=max(1, min(24, fill_sty)),
                perimeter=(stroke_val != "none"),
            )

            if has_shadow:
                builder.shadow_on()
                # Emit offset shadow silhouette primitive per GEM 2.0 App. C p. C-7
                if itype in {"rectangle", "rounded_rectangle", "image"}:
                    x0, y0, x1, y1 = el["bounds"]
                    builder.bar(x0 + 45, y0 + 45, x1 + 45, y1 + 45)
                elif itype == "ellipse":
                    cx, cy = el["center"]
                    rx, ry = el["radii"]
                    builder.ellipse(cx + 45, cy + 45, rx, ry)
                builder.shadow_off()

            # Emit object metadata record (part="shape") AFTER shadow_off so it binds to foreground shape
            meta_type = _gem_meta_type_map.get(itype, itype)
            obj_meta: dict[str, Any] = {"id": el["id"], "type": meta_type}
            if "role" in el:
                obj_meta["role"] = el["role"]
            elif itype != meta_type:
                obj_meta["role"] = itype
            builder.object_meta(obj_meta, part="shape")

            if itype == "rectangle":
                x0, y0, x1, y1 = el["bounds"]
                builder.bar(x0, y0, x1, y1)
            elif itype == "rounded_rectangle":
                x0, y0, x1, y1 = el["bounds"]
                if fill_val != "none" and fill_int != 0:
                    builder.rfbox(x0, y0, x1, y1)
                else:
                    builder.rbox(x0, y0, x1, y1)
            elif itype == "image":
                x0, y0, x1, y1 = el["bounds"]
                builder.rbox(x0, y0, x1, y1)
            elif itype == "ellipse":
                cx, cy = el["center"]
                rx, ry = el["radii"]
                if abs(rx - ry) < 1e-6:
                    builder.circle(cx, cy, rx)
                else:
                    builder.ellipse(cx, cy, rx, ry)
            elif itype == "arc":
                cx, cy = el["center"]
                builder.arc(cx, cy, el["radii"][0], el["begang"], el["endang"])
            elif itype == "pieslice":
                cx, cy = el["center"]
                builder.pieslice(cx, cy, el["radii"][0], el["begang"], el["endang"])
            elif itype == "ellarc":
                cx, cy = el["center"]
                builder.ellarc(cx, cy, el["radii"][0], el["radii"][1], el["begang"], el["endang"])
            elif itype == "ellpie":
                cx, cy = el["center"]
                builder.ellpie(cx, cy, el["radii"][0], el["radii"][1], el["begang"], el["endang"])
            elif itype == "polygon":
                builder.fillarea(el["points"])
            elif itype in {"line", "polyline"}:
                builder.pline(el["points"])
            elif itype == "text":
                hor_map = {"left": 0, "center": 1, "right": 2, "decimal": 2}
                builder.set_text(
                    color=stroke_val if stroke_val != "none" else INK,
                    height=max(1, round(float(el.get("size", 240.0)))),
                    font_id=int(el.get("font_id", self.theme.artline_font_id)),
                    effects=int(el.get("effects", 0)),
                    alignment=(hor_map.get(str(el.get("align", "left")), 0), 0),
                    rotation_tenths=round(float(el.get("rotation", 0.0)) * 10.0),
                )
                px, py = el["position"]
                builder.gtext(px, py, str(el.get("text", " "))[:500])

            if active_gid is not None:
                run_len += 1

        _flush_group()

        data = builder.build()
        check = seasip_gem.verify_seasip_gem_metafile(data)
        if not check.get("valid"):
            raise ValueError(f"Generated .GEM failed seasip_gem verification: {check}")
        return data

    def render_svg(self, path: Path | str | None = None, *, width: int = 1920) -> str:
        return PresentationRenderer(self).render_svg(path, width=width)

    def render_pil(self, *, width: int = 1920, height: int = 1080) -> Image.Image:
        return PresentationRenderer(self).render_pil(width=width, height=height)

    def render_png(self, path: Path | str, *, width: int = 1920, height: int = 1080) -> Path:
        return PresentationRenderer(self).render_png(path, width=width, height=height)

    def render_jpg(self, path: Path | str, *, width: int = 1920, height: int = 1080, quality: int = 94) -> Path:
        return PresentationRenderer(self).render_jpg(path, width=width, height=height, quality=quality)


def verify_slide_layout(
    canvas: DrawPlusCanvas,
    *,
    safe_margin: float = 0.0,
    text_epsilon: float = 0.0,
) -> LayoutReport:
    return canvas.verify_layout(safe_margin=safe_margin, text_epsilon=text_epsilon)


__all__ = [
    "DrawPlusCanvas",
    "LayoutReport",
    "petal_points",
    "verify_slide_layout",
]

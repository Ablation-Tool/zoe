from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import struct
from typing import Any, Sequence

from .geometry import object_bounds
from .model import OBJECT_TYPES, Scene


# GEM 2.0 Appendix C Escape 5/99 (`v_write_meta`) sub-opcodes
META_PAGESIZE = 0
META_COORDS = 1
META_GROUP = 10
META_NO_LINE_STYLE = 49
META_SHADOW_ON = 50
META_SHADOW_OFF = 51
META_START_AREA = 80
META_END_AREA = 81
META_OBJECT = 1001

# Standard 16:9 Presentation Team RC canvas (1000 units/inch, 0.1 mm physical)
SLIDE_CANVAS_WIDTH = 13333
SLIDE_CANVAS_HEIGHT = 7500
SLIDE_PAGE_WIDTH_TMM = 3387
SLIDE_PAGE_HEIGHT_TMM = 1905

COLOR_INDEX = {
    "white": 0, "black": 1, "red": 2, "green": 3, "blue": 4,
    "cyan": 5, "yellow": 6, "magenta": 7,
    # Standard PC GEM indices 8..15 (seasip.info/Gem/palette.html) as valid #RRGGBB
    "#adaaad": 8, "#525552": 9, "#ad0000": 10, "#00aa00": 11,
    "#0000ad": 12, "#00aaad": 13, "#adaa00": 14, "#ad00ad": 15,
}
INDEX_COLOR = {value: key for key, value in COLOR_INDEX.items()}

OPCODE_NAMES = {
    3: "v_clrwk",
    4: "v_updwk",
    5: "escape",
    6: "v_pline",
    7: "v_pmarker",
    8: "v_gtext",
    9: "v_fillarea",
    11: "gdp",
    12: "vst_height",
    13: "vst_rotation",
    14: "vs_color",
    15: "vsl_type",
    16: "vsl_width",
    17: "vsl_color",
    18: "vsm_type",
    19: "vsm_height",
    20: "vsm_color",
    21: "vst_font",
    22: "vst_color",
    23: "vsf_interior",
    24: "vsf_style",
    25: "vsf_color",
    32: "vswr_mode",
    39: "vst_alignment",
    104: "vsf_perimeter",
    106: "vst_effects",
    107: "vst_point",
    108: "vsl_ends",
    112: "vsf_udpat",
    113: "vsl_udsty",
    114: "vr_recfl",
    129: "vs_clip",
}

GDP_NAMES = {
    1: "v_bar",
    2: "v_arc",
    3: "v_pieslice",
    4: "v_circle",
    5: "v_ellipse",
    6: "v_ellarc",
    7: "v_ellpie",
    8: "v_rbox",
    9: "v_rfbox",
    10: "v_justified",
}

ESCAPE_NAMES = {
    98: "v_meta_extents",
    99: "v_write_meta",
    100: "vm_filename",
}


def _word(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"VDI word must be a finite number, got {value!r}")
    rounded = int(round(value))
    if not -32768 <= rounded <= 32767:
        raise ValueError(f"VDI word outside signed 16-bit range: {rounded}")
    return rounded


def _record(
    command: int,
    subcommand: int = 0,
    points: Sequence[Sequence[float | int]] = (),
    values: Sequence[float | int] = (),
) -> bytes:
    cmd = _word(command)
    sub = _word(subcommand)
    n_pts = _word(len(points))
    n_ints = _word(len(values))
    flattened: list[int] = []
    for point in points:
        if len(point) != 2:
            raise ValueError(f"VDI point must have 2 coordinates, got {point!r}")
        flattened.append(_word(point[0]))
        flattened.append(_word(point[1]))
    integers = [_word(value) for value in values]
    header = struct.pack("<4h", cmd, n_pts, n_ints, sub)
    pts_bytes = struct.pack(f"<{len(flattened)}h", *flattened) if flattened else b""
    int_bytes = struct.pack(f"<{len(integers)}h", *integers) if integers else b""
    return header + pts_bytes + int_bytes


def _normalize_angle_tenths(angle: float | int) -> int:
    ang = _word(angle)
    if ang == 3600:
        return 3600
    return ang % 3600


def meta_json_record(payload_dict: dict[str, Any], sub_opcode: int = META_OBJECT) -> bytes:
    if not isinstance(payload_dict, dict):
        raise ValueError("VDI JSON metadata payload must be a dict")
    payload = json.dumps(payload_dict, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\0"
    if len(payload) > 4096:
        raise ValueError("VDI object metadata is too large")
    return _record(5, 99, values=[sub_opcode, *payload])


def _object_record(item: dict[str, Any], part: str = "shape") -> bytes:
    metadata: dict[str, Any] = {"id": item["id"], "type": item["type"], "part": part}
    for key in ("role", "event_id", "status", "selected", "from", "to", "label", "width", "size"):
        if key in item:
            metadata[key] = item[key]
    return meta_json_record(metadata, META_OBJECT)


# ---------------------------------------------------------------------------
# Spec-Exact VDI Attribute Record Helpers
# ---------------------------------------------------------------------------

def vst_height(height: float | int) -> bytes:
    h = _word(height)
    if h <= 0:
        raise ValueError(f"vst_height must be positive, got {h}")
    return _record(12, points=[(0, h)])


def vst_rotation(angle_tenths: float | int) -> bytes:
    return _record(13, values=[_word(angle_tenths) % 3600])


def vs_color(index: int, red_1000: int, green_1000: int, blue_1000: int) -> bytes:
    idx = _word(index)
    r, g, b = _word(red_1000), _word(green_1000), _word(blue_1000)
    if not 0 <= idx <= 255:
        raise ValueError(f"vs_color index must be in 0..255, got {idx}")
    if any(not 0 <= ch <= 1000 for ch in (r, g, b)):
        raise ValueError(f"vs_color RGB components must be in 0..1000, got {(r, g, b)}")
    return _record(14, values=[idx, r, g, b])


def vsl_type(style: int) -> bytes:
    s = _word(style)
    if not 1 <= s <= 7:
        raise ValueError(f"vsl_type must be in 1..7, got {s}")
    return _record(15, values=[s])


def vsl_width(width: float | int) -> bytes:
    w = max(1, _word(width))
    return _record(16, points=[(w, 0)])


def vsl_color(index: int) -> bytes:
    idx = _word(index)
    if not 0 <= idx <= 255:
        raise ValueError(f"vsl_color index must be in 0..255, got {idx}")
    return _record(17, values=[idx])


def vst_font(font_id: int) -> bytes:
    fid = _word(font_id)
    if fid < 1:
        raise ValueError(f"vst_font must be >= 1, got {fid}")
    return _record(21, values=[fid])


def vst_color(index: int) -> bytes:
    idx = _word(index)
    if not 0 <= idx <= 255:
        raise ValueError(f"vst_color index must be in 0..255, got {idx}")
    return _record(22, values=[idx])


def vsf_interior(interior: int) -> bytes:
    val = _word(interior)
    if not 0 <= val <= 4:
        raise ValueError(f"vsf_interior must be in 0..4, got {val}")
    return _record(23, values=[val])


def vsf_style(style: int) -> bytes:
    s = _word(style)
    if not 1 <= s <= 24:
        raise ValueError(f"vsf_style must be in 1..24, got {s}")
    return _record(24, values=[s])


def vsf_color(index: int) -> bytes:
    idx = _word(index)
    if not 0 <= idx <= 255:
        raise ValueError(f"vsf_color index must be in 0..255, got {idx}")
    return _record(25, values=[idx])


def vswr_mode(mode: int) -> bytes:
    m = _word(mode)
    if not 1 <= m <= 4:
        raise ValueError(f"vswr_mode must be in 1..4, got {m}")
    return _record(32, values=[m])


def vst_alignment(hor: int, vert: int) -> bytes:
    h, v = _word(hor), _word(vert)
    if not 0 <= h <= 2 or not 0 <= v <= 5:
        raise ValueError(f"vst_alignment out of range: hor={h} (0..2), vert={v} (0..5)")
    return _record(39, values=[h, v])


def vsf_perimeter(visible: bool | int) -> bytes:
    flag = 1 if visible else 0
    return _record(104, values=[flag])


def vst_effects(mask: int) -> bytes:
    m = _word(mask)
    return _record(106, values=[m & 0x3F])


def vst_point(point: int) -> bytes:
    pt = _word(point)
    if pt < 1:
        raise ValueError(f"vst_point must be >= 1, got {pt}")
    return _record(107, values=[pt])


def vsl_ends(beg: int, end: int) -> bytes:
    b, e = _word(beg), _word(end)
    if not 0 <= b <= 2 or not 0 <= e <= 2:
        raise ValueError(f"vsl_ends must be in 0..2, got {(b, e)}")
    return _record(108, values=[b, e])


# ---------------------------------------------------------------------------
# Spec-Exact VDI GDP Helpers (Opcode 11, sub-opcodes 1..9)
# ---------------------------------------------------------------------------

def v_bar(x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> bytes:
    return _record(11, 1, points=[(x1, y1), (x2, y2)])


def v_arc(
    cx: float | int,
    cy: float | int,
    radius: float | int,
    begang: float | int,
    endang: float | int,
) -> bytes:
    r = max(1, _word(radius))
    return _record(
        11,
        2,
        points=[(cx, cy), (0, 0), (0, 0), (r, 0)],
        values=[_normalize_angle_tenths(begang), _normalize_angle_tenths(endang)],
    )


def v_pieslice(
    cx: float | int,
    cy: float | int,
    radius: float | int,
    begang: float | int,
    endang: float | int,
) -> bytes:
    r = max(1, _word(radius))
    return _record(
        11,
        3,
        points=[(cx, cy), (0, 0), (0, 0), (r, 0)],
        values=[_normalize_angle_tenths(begang), _normalize_angle_tenths(endang)],
    )


def v_circle(cx: float | int, cy: float | int, radius: float | int) -> bytes:
    r = max(1, _word(radius))
    return _record(11, 4, points=[(cx, cy), (0, 0), (r, 0)])


def v_ellipse(cx: float | int, cy: float | int, rx: float | int, ry: float | int) -> bytes:
    return _record(11, 5, points=[(cx, cy), (max(1, _word(rx)), max(1, _word(ry)))])


def v_ellarc(
    cx: float | int,
    cy: float | int,
    rx: float | int,
    ry: float | int,
    begang: float | int,
    endang: float | int,
) -> bytes:
    return _record(
        11,
        6,
        points=[(cx, cy), (max(1, _word(rx)), max(1, _word(ry)))],
        values=[_normalize_angle_tenths(begang), _normalize_angle_tenths(endang)],
    )


def v_ellpie(
    cx: float | int,
    cy: float | int,
    rx: float | int,
    ry: float | int,
    begang: float | int,
    endang: float | int,
) -> bytes:
    return _record(
        11,
        7,
        points=[(cx, cy), (max(1, _word(rx)), max(1, _word(ry)))],
        values=[_normalize_angle_tenths(begang), _normalize_angle_tenths(endang)],
    )


def v_rbox(x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> bytes:
    return _record(11, 8, points=[(x1, y1), (x2, y2)])


def v_rfbox(x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> bytes:
    return _record(11, 9, points=[(x1, y1), (x2, y2)])


# ---------------------------------------------------------------------------
# Escape 5/99 (`v_write_meta`) Helpers
# ---------------------------------------------------------------------------

def meta_pagesize(page_width_tmm: int, page_height_tmm: int) -> bytes:
    pw, ph = _word(page_width_tmm), _word(page_height_tmm)
    if pw <= 0 or ph <= 0:
        raise ValueError("meta_pagesize dimensions must be positive")
    return _record(5, 99, values=[META_PAGESIZE, pw, ph])


def meta_coords(llx: int, lly: int, urx: int, ury: int) -> bytes:
    return _record(5, 99, values=[META_COORDS, _word(llx), _word(lly), _word(urx), _word(ury)])


def meta_group(count: int) -> bytes:
    c = _word(count)
    if c < 1:
        raise ValueError(f"meta_group count must be >= 1, got {c}")
    return _record(5, 99, values=[META_GROUP, c])


def meta_no_line_style() -> bytes:
    return _record(5, 99, values=[META_NO_LINE_STYLE])


def meta_shadow_on() -> bytes:
    return _record(5, 99, values=[META_SHADOW_ON])


def meta_shadow_off() -> bytes:
    return _record(5, 99, values=[META_SHADOW_OFF])


def _palette_index(value: str, palette: dict[str, Any], records: list[bytes]) -> int:
    if not isinstance(value, str):
        return COLOR_INDEX["black"]
    norm = value.lower() if value.startswith("#") else value
    if norm in COLOR_INDEX:
        return COLOR_INDEX[norm]
    if norm in palette["custom"]:
        return palette["custom"][norm]
    if not norm.startswith("#") or len(norm) != 7:
        return COLOR_INDEX["black"]
    try:
        channels = [int(norm[offset:offset + 2], 16) for offset in (1, 3, 5)]
    except ValueError:
        return COLOR_INDEX["black"]
    index = palette["next"]
    if index > 255:
        raise ValueError("scene exceeds the 256-entry VDI palette")
    palette["next"] += 1
    palette["custom"][norm] = index
    records.append(_record(14, values=[index, *[round(channel * 1000 / 255) for channel in channels]]))
    return index


def _fill_records(item: dict[str, Any], palette: dict[str, Any], records: list[bytes]) -> None:
    index = _palette_index(item["fill"], palette, records) if item["fill"] != "none" else COLOR_INDEX["white"]
    records.extend([
        _record(25, values=[index]),
        _record(23, values=[0 if item["fill"] == "none" else 1]),
    ])


def _line_records(item: dict[str, Any], palette: dict[str, Any], records: list[bytes]) -> None:
    records.append(
        _record(17, values=[_palette_index(item["stroke"], palette, records) if item["stroke"] != "none" else COLOR_INDEX["white"]])
    )


def _text_records(item: dict[str, Any], palette: dict[str, Any], records: list[bytes], size: float | None = None) -> None:
    height = item.get("size", 240) if size is None else size
    records.extend([
        _record(12, points=[(0, height)]),
        _record(22, values=[_palette_index(item["stroke"], palette, records)]),
    ])


def _label_records(item: dict[str, Any], palette: dict[str, Any], records: list[bytes]) -> None:
    if not item.get("label") or item["type"] != "rectangle":
        return
    left, top, right, bottom = item["bounds"]
    size = min(240, (bottom - top) / 3)
    label = item["label"].replace("\n", " · ")
    x = (left + right) / 2 - len(label) * size * 0.31
    y = (top + bottom) / 2 + size * 0.35
    metadata = dict(item)
    metadata["type"] = "text"
    records.append(_object_record(metadata, "label"))
    _text_records(item, palette, records, size)
    records.append(_record(8, points=[(x, y)], values=[*label.encode("cp437", "replace"), 0]))


def _mesh_records(item: dict[str, Any], palette: dict[str, Any], records: list[bytes]) -> None:
    records.append(_record(23, values=[1]))
    points, fills = item["points"], item["fills"]
    for triangle, fill in enumerate(fills):
        records.append(_record(25, values=[_palette_index(fill, palette, records)]))
        corners = points[3 * triangle:3 * triangle + 3]
        records.append(_record(9, points=[*corners, corners[0]]))


@dataclass
class VdiMetafileBuilder:
    """High-level spec-exact GEM 2.0 `.GEM` metafile builder (default 13333x7500 RC 16:9)."""

    width: int = SLIDE_CANVAS_WIDTH
    height: int = SLIDE_CANVAS_HEIGHT
    coord_mode: int = 2
    page_size: tuple[int, int] | None = None
    _records: list[bytes] = field(default_factory=list, init=False, repr=False)
    _palette: dict[str, Any] = field(default_factory=lambda: {"custom": {}, "next": 16}, init=False, repr=False)
    _extents: list[int] | None = field(default=None, init=False, repr=False)
    _state: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self.width = _word(self.width)
        self.height = _word(self.height)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("VdiMetafileBuilder canvas dimensions must be positive")
        if self.coord_mode not in (0, 2):
            raise ValueError(f"coord_mode must be 0 (NDC) or 2 (RC), got {self.coord_mode}")
        if self.page_size is None:
            if self.width == SLIDE_CANVAS_WIDTH and self.height == SLIDE_CANVAS_HEIGHT:
                self.page_size = (SLIDE_PAGE_WIDTH_TMM, SLIDE_PAGE_HEIGHT_TMM)
            else:
                pw = 2540
                ph = max(1, round(pw * self.height / self.width))
                self.page_size = (_word(pw), _word(ph))
        else:
            pw, ph = _word(self.page_size[0]), _word(self.page_size[1])
            if pw <= 0 or ph <= 0:
                raise ValueError("page_size dimensions must be positive")
            self.page_size = (pw, ph)

    def _track_points(self, points: Sequence[Sequence[float | int]]) -> None:
        for pt in points:
            if len(pt) != 2:
                raise ValueError(f"Point must have 2 elements, got {pt!r}")
            x, y = _word(pt[0]), _word(pt[1])
            if self._extents is None:
                self._extents = [x, y, x, y]
            else:
                self._extents[0] = min(self._extents[0], x)
                self._extents[1] = min(self._extents[1], y)
                self._extents[2] = max(self._extents[2], x)
                self._extents[3] = max(self._extents[3], y)

    def color_index(self, value: str) -> int:
        return _palette_index(value, self._palette, self._records)

    def set_writing_mode(self, mode: int) -> None:
        m = _word(mode)
        if self._state.get("writing_mode") != m:
            self._records.append(vswr_mode(m))
            self._state["writing_mode"] = m

    def set_no_line_style(self) -> None:
        if not self._state.get("no_line_style", False):
            self._records.append(meta_no_line_style())
            self._state["no_line_style"] = True

    def set_line(
        self,
        *,
        color: str = "black",
        width: float | int = 1,
        line_type: int = 1,
        ends: tuple[int, int] = (0, 0),
    ) -> None:
        if color == "none":
            self.set_no_line_style()
            return
        lt = _word(line_type)
        if self._state.get("no_line_style") or self._state.get("line_type") != lt:
            self._records.append(vsl_type(lt))
            self._state["line_type"] = lt
            self._state["no_line_style"] = False
        lw = max(1, _word(width))
        if self._state.get("line_width") != lw:
            self._records.append(vsl_width(lw))
            self._state["line_width"] = lw
        l_idx = self.color_index(color)
        if self._state.get("line_color") != l_idx:
            self._records.append(vsl_color(l_idx))
            self._state["line_color"] = l_idx
        eb, ee = _word(ends[0]), _word(ends[1])
        if self._state.get("line_ends") != (eb, ee):
            self._records.append(vsl_ends(eb, ee))
            self._state["line_ends"] = (eb, ee)

    def set_fill(
        self,
        *,
        color: str = "white",
        interior: int = 1,
        style: int = 1,
        perimeter: bool = True,
    ) -> None:
        if color == "none" or interior == 0:
            if self._state.get("fill_interior") != 0:
                self._records.append(vsf_interior(0))
                self._state["fill_interior"] = 0
            perim_val = bool(perimeter)
            if self._state.get("fill_perimeter") != perim_val:
                self._records.append(vsf_perimeter(perim_val))
                self._state["fill_perimeter"] = perim_val
            return
        f_idx = self.color_index(color)
        if self._state.get("fill_color") != f_idx:
            self._records.append(vsf_color(f_idx))
            self._state["fill_color"] = f_idx
        fi = _word(interior)
        if self._state.get("fill_interior") != fi:
            self._records.append(vsf_interior(fi))
            self._state["fill_interior"] = fi
        fs = max(1, _word(style))
        if fi in (2, 3) and self._state.get("fill_style") != fs:
            self._records.append(vsf_style(fs))
            self._state["fill_style"] = fs
        perim_val = bool(perimeter)
        if self._state.get("fill_perimeter") != perim_val:
            self._records.append(vsf_perimeter(perim_val))
            self._state["fill_perimeter"] = perim_val

    def set_text(
        self,
        *,
        color: str = "black",
        height: float | int = 240,
        font_id: int = 1,
        effects: int = 0,
        alignment: tuple[int, int] = (0, 0),
        rotation_tenths: float | int = 0,
    ) -> None:
        fid = max(1, _word(font_id))
        if self._state.get("text_font") != fid:
            self._records.append(vst_font(fid))
            self._state["text_font"] = fid
        h = max(1, _word(height))
        if self._state.get("text_height") != h:
            self._records.append(vst_height(h))
            self._state["text_height"] = h
        t_idx = self.color_index(color)
        if self._state.get("text_color") != t_idx:
            self._records.append(vst_color(t_idx))
            self._state["text_color"] = t_idx
        eff = _word(effects) & 0x3F
        if self._state.get("text_effects") != eff:
            self._records.append(vst_effects(eff))
            self._state["text_effects"] = eff
        ah, av = _word(alignment[0]), _word(alignment[1])
        if self._state.get("text_alignment") != (ah, av):
            self._records.append(vst_alignment(ah, av))
            self._state["text_alignment"] = (ah, av)
        rot = _word(rotation_tenths) % 3600
        if self._state.get("text_rotation") != rot:
            self._records.append(vst_rotation(rot))
            self._state["text_rotation"] = rot

    def slide_meta(self, payload: dict[str, Any]) -> None:
        meta = dict(payload)
        meta.setdefault("id", f"slide-{meta.get('slide_index', 0)}")
        meta["part"] = "slide_meta"
        self._records.append(meta_json_record(meta, META_OBJECT))

    def object_meta(self, item: dict[str, Any], part: str = "shape") -> None:
        self._records.append(_object_record(item, part=part))

    def group(self, count: int) -> None:
        self._records.append(meta_group(count))

    def shadow_on(self) -> None:
        self._records.append(meta_shadow_on())

    def shadow_off(self) -> None:
        self._records.append(meta_shadow_off())

    def pline(self, points: Sequence[Sequence[float | int]]) -> None:
        if len(points) < 2:
            raise ValueError("v_pline requires at least 2 points")
        self._track_points(points)
        self._records.append(_record(6, points=points))

    def fillarea(self, points: Sequence[Sequence[float | int]]) -> None:
        if len(points) < 3:
            raise ValueError("v_fillarea requires at least 3 points")
        pts = list(points)
        if _word(pts[0][0]) != _word(pts[-1][0]) or _word(pts[0][1]) != _word(pts[-1][1]):
            pts.append(pts[0])
        self._track_points(pts)
        self._records.append(_record(9, points=pts))

    def bar(self, x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> None:
        self._track_points([(x1, y1), (x2, y2)])
        self._records.append(v_bar(x1, y1, x2, y2))

    def rbox(self, x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> None:
        self._track_points([(x1, y1), (x2, y2)])
        self._records.append(v_rbox(x1, y1, x2, y2))

    def rfbox(self, x1: float | int, y1: float | int, x2: float | int, y2: float | int) -> None:
        self._track_points([(x1, y1), (x2, y2)])
        self._records.append(v_rfbox(x1, y1, x2, y2))

    def circle(self, cx: float | int, cy: float | int, radius: float | int) -> None:
        r = max(1, _word(radius))
        self._track_points([(_word(cx) - r, _word(cy) - r), (_word(cx) + r, _word(cy) + r)])
        self._records.append(v_circle(cx, cy, r))

    def ellipse(self, cx: float | int, cy: float | int, rx: float | int, ry: float | int) -> None:
        rx_i, ry_i = max(1, _word(rx)), max(1, _word(ry))
        self._track_points([(_word(cx) - rx_i, _word(cy) - ry_i), (_word(cx) + rx_i, _word(cy) + ry_i)])
        self._records.append(v_ellipse(cx, cy, rx_i, ry_i))

    def arc(
        self,
        cx: float | int,
        cy: float | int,
        radius: float | int,
        begang: float | int,
        endang: float | int,
    ) -> None:
        r = max(1, _word(radius))
        self._track_points([(_word(cx) - r, _word(cy) - r), (_word(cx) + r, _word(cy) + r)])
        self._records.append(v_arc(cx, cy, r, begang, endang))

    def pieslice(
        self,
        cx: float | int,
        cy: float | int,
        radius: float | int,
        begang: float | int,
        endang: float | int,
    ) -> None:
        r = max(1, _word(radius))
        self._track_points([(_word(cx) - r, _word(cy) - r), (_word(cx) + r, _word(cy) + r)])
        self._records.append(v_pieslice(cx, cy, r, begang, endang))

    def ellarc(
        self,
        cx: float | int,
        cy: float | int,
        rx: float | int,
        ry: float | int,
        begang: float | int,
        endang: float | int,
    ) -> None:
        rx_i, ry_i = max(1, _word(rx)), max(1, _word(ry))
        self._track_points([(_word(cx) - rx_i, _word(cy) - ry_i), (_word(cx) + rx_i, _word(cy) + ry_i)])
        self._records.append(v_ellarc(cx, cy, rx_i, ry_i, begang, endang))

    def ellpie(
        self,
        cx: float | int,
        cy: float | int,
        rx: float | int,
        ry: float | int,
        begang: float | int,
        endang: float | int,
    ) -> None:
        rx_i, ry_i = max(1, _word(rx)), max(1, _word(ry))
        self._track_points([(_word(cx) - rx_i, _word(cy) - ry_i), (_word(cx) + rx_i, _word(cy) + ry_i)])
        self._records.append(v_ellpie(cx, cy, rx_i, ry_i, begang, endang))

    def gtext(self, x: float | int, y: float | int, text: str) -> None:
        self._track_points([(x, y)])
        encoded = str(text).encode("cp437", "replace") + b"\0"
        self._records.append(_record(8, points=[(x, y)], values=encoded))

    def build(self) -> bytes:
        min_x, min_y, max_x, max_y = self._extents or [0, 0, 0, 0]
        assert self.page_size is not None
        pw, ph = self.page_size
        header_values = [
            -1,
            24,
            101,
            self.coord_mode,
            _word(min_x),
            _word(min_y),
            _word(max_x),
            _word(max_y),
            _word(pw),
            _word(ph),
            0,
            0,
            _word(self.width),
            _word(self.height),
            0,
            *([0] * 9),
        ]
        data = struct.pack("<24h", *header_values) + b"".join(self._records) + struct.pack("<h", -1)
        parse_metafile(data)
        return data


def scene_to_metafile(scene: Scene, *, page_size: tuple[int, int] | None = None, coord_mode: int = 2) -> bytes:
    if coord_mode not in (0, 2):
        raise ValueError(f"coord_mode must be 0 or 2, got {coord_mode}")
    objects = scene.objects
    if objects:
        bounds = [object_bounds(item) for item in objects]
        minimum_x = min(item.left for item in bounds)
        minimum_y = min(item.top for item in bounds)
        maximum_x = max(item.right for item in bounds)
        maximum_y = max(item.bottom for item in bounds)
    else:
        minimum_x = minimum_y = maximum_x = maximum_y = 0
    if page_size is not None:
        page_width = _word(page_size[0])
        page_height = _word(page_size[1])
        if page_width <= 0 or page_height <= 0:
            raise ValueError("page_size dimensions must be positive")
    elif round(scene.canvas["width"]) == SLIDE_CANVAS_WIDTH and round(scene.canvas["height"]) == SLIDE_CANVAS_HEIGHT:
        page_width = SLIDE_PAGE_WIDTH_TMM
        page_height = SLIDE_PAGE_HEIGHT_TMM
    else:
        page_width = 2540
        page_height = max(1, round(page_width * scene.canvas["height"] / scene.canvas["width"]))
    header_values = [
        -1, 24, 101, coord_mode,
        _word(minimum_x), _word(minimum_y), _word(maximum_x), _word(maximum_y),
        _word(page_width), _word(page_height),
        0, 0, _word(scene.canvas["width"]), _word(scene.canvas["height"]),
        0, *([0] * 9),
    ]
    records: list[bytes] = []
    palette: dict[str, Any] = {"custom": {}, "next": 16}
    for item in objects:
        # Keep _object_record(objects[0]) as first body record at byte offset 48 (gem_stress.py:156)
        records.append(_object_record(item))
        if item["type"] == "mesh":
            _mesh_records(item, palette, records)
            continue
        _fill_records(item, palette, records)
        _line_records(item, palette, records)
        if item["type"] == "rectangle":
            points = [item["bounds"][:2], item["bounds"][2:]]
            records.append(_record(11, 1 if item["fill"] != "none" else 8, points=points))
        elif item["type"] in {"polygon", "polyline", "line"}:
            points = list(item["points"])
            if item["type"] == "polygon" and points[0] != points[-1]:
                points.append(points[0])
            if item["type"] == "polygon" and item["fill"] != "none":
                records.append(_record(9, points=points))
            else:
                records.append(_record(6, points=points))
        elif item["type"] == "ellipse":
            records.append(_record(11, 5, points=[item["center"], item["radii"]]))
        elif item["type"] == "text":
            _text_records(item, palette, records)
            text = item["text"].encode("cp437", "replace") + b"\0"
            records.append(_record(8, points=[item["position"]], values=text))
        _label_records(item, palette, records)
    return struct.pack("<24h", *header_values) + b"".join(records) + struct.pack("<h", -1)


def write_metafile(scene: Scene, path: Any) -> int:
    data = scene_to_metafile(scene)
    with open(path, "wb") as stream:
        stream.write(data)
    return len(data)


def parse_metafile(data: bytes | bytearray | memoryview) -> dict[str, Any]:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("metafile data must be bytes-like")
    if len(data) < 50:
        raise ValueError("metafile is truncated")
    magic, header_words, version, coordinates = struct.unpack_from("<4h", data)
    if magic != -1 or not 2 <= header_words <= 1024 or len(data) < header_words * 2 + 2:
        raise ValueError("invalid GEM metafile header")
    header = {
        "header_words": header_words,
        "version": version,
        "coordinate_system": coordinates,
        "bounds": struct.unpack_from("<4h", data, 8) if header_words >= 8 else (0, 0, 0, 0),
        "page_size": struct.unpack_from("<2H", data, 16) if header_words >= 10 else (0, 0),
        "coordinate_bounds": struct.unpack_from("<4h", data, 20) if header_words >= 14 else (0, 0, 0, 0),
        "flags": struct.unpack_from("<h", data, 28)[0] if header_words >= 15 else 0,
    }
    position = header_words * 2
    records: list[dict[str, Any]] = []
    terminated = False
    while position + 2 <= len(data):
        command = struct.unpack_from("<h", data, position)[0]
        if command == -1:
            records.append({"offset": position, "command": -1})
            position += 2
            terminated = True
            break
        if position + 8 > len(data):
            raise ValueError("truncated VDI record header")
        command, points, integers, subcommand = struct.unpack_from("<4h", data, position)
        if points < 0 or integers < 0:
            raise ValueError("negative VDI record length")
        offset = position
        position += 8
        byte_count = points * 4 + integers * 2
        if position + byte_count > len(data):
            raise ValueError("truncated VDI record payload")
        coordinates_flat = struct.unpack_from(f"<{points * 2}h", data, position) if points else ()
        position += points * 4
        values = struct.unpack_from(f"<{integers}h", data, position) if integers else ()
        position += integers * 2
        records.append({
            "offset": offset,
            "command": command,
            "points": points,
            "integers": integers,
            "subcommand": subcommand,
            "coordinates": coordinates_flat,
            "values": values,
        })
    if not terminated or position != len(data):
        raise ValueError("metafile must end with exactly one terminator")
    return {"header": header, "records": records, "bytes_consumed": position}


def _text(record: dict[str, Any]) -> str:
    raw = bytes(value & 0xFF for value in record["values"])
    return raw.split(b"\0", 1)[0].decode("cp437", "replace")


def _parse_metadata(record: dict[str, Any]) -> dict[str, Any] | None:
    values = record["values"]
    if len(values) < 2 or values[0] != META_OBJECT:
        return None
    raw = bytes(value & 0xFF for value in values[1:])
    try:
        document = json.loads(raw.split(b"\0", 1)[0].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid GEM object metadata record") from error
    if not isinstance(document, dict):
        raise ValueError("GEM object metadata must be a JSON object")
    if document.get("part") != "slide_meta" and not isinstance(document.get("id"), str):
        raise ValueError("GEM object metadata lacks an ID")
    return document


def _points(record: dict[str, Any]) -> list[list[int]]:
    values = record["coordinates"]
    return [[values[index], values[index + 1]] for index in range(0, len(values), 2)]


def _validate_record_operands(record: dict[str, Any]) -> None:
    command = record["command"]
    subcommand = record.get("subcommand", 0)
    n_pts = record["points"]
    values = record["values"]
    n_ints = len(values)

    if command in (15, 17, 21, 22, 23, 24, 25, 32, 104, 106, 107):
        if n_ints < 1:
            raise ValueError(f"VDI opcode {command} requires at least 1 integer operand")
    elif command in (12, 16):
        if n_pts < 1:
            raise ValueError(f"VDI opcode {command} requires at least 1 point operand")
    elif command == 13:
        if n_ints == 1:
            pass
        elif n_ints == 4 and 0 <= values[0] <= 255 and all(0 <= c <= 1000 for c in values[1:4]):
            pass
        else:
            raise ValueError(f"VDI opcode 13 expects 1 angle (vst_rotation) or 4 legacy vs_color ints, got {values!r}")
    elif command == 14:
        if n_ints < 4 or not 0 <= values[0] <= 255 or any(not 0 <= c <= 1000 for c in values[1:4]):
            raise ValueError(f"VDI opcode 14 (vs_color) malformed values: {values!r}")
    elif command in (39, 108):
        if n_ints < 2:
            raise ValueError(f"VDI opcode {command} requires at least 2 integer operands")
    elif command == 5 and subcommand == 99:
        if n_ints < 1:
            raise ValueError("Escape 5/99 (v_write_meta) requires a sub-opcode integer")
        sub_op = values[0]
        if sub_op == META_PAGESIZE and n_ints < 3:
            raise ValueError("Escape 5/99/0 (Physical Page Size) requires width and height operands")
        elif sub_op == META_COORDS and n_ints < 5:
            raise ValueError("Escape 5/99/1 (Coordinate Window) requires 4 coordinate operands")
        elif sub_op == META_GROUP and n_ints < 2:
            raise ValueError("Escape 5/99/10 (Group) requires object count")
        elif sub_op == META_OBJECT and n_ints < 2:
            raise ValueError("Escape 5/99/1001 (Object Meta) requires JSON payload")
    elif command == 11:
        if subcommand in (1, 5, 8, 9, 114) and n_pts < 2:
            raise ValueError(f"VDI GDP 11/{subcommand} requires at least 2 points")
        elif subcommand in (2, 3) and (n_pts not in (2, 4) or n_ints < 2):
            raise ValueError(f"VDI GDP 11/{subcommand} requires 2 or 4 points and 2 angles")
        elif subcommand == 4 and n_pts not in (2, 3):
            raise ValueError("VDI GDP 11/4 (v_circle) requires 2 or 3 points")
        elif subcommand in (6, 7) and (n_pts < 2 or n_ints < 2):
            raise ValueError(f"VDI GDP 11/{subcommand} requires 2 points and 2 angles")
    elif command == 6 and n_pts < 2:
        raise ValueError("VDI v_pline requires at least 2 points")
    elif command == 9 and n_pts < 3:
        raise ValueError("VDI v_fillarea requires at least 3 points")
    elif command == 8 and (n_pts < 1 or n_ints < 1):
        raise ValueError("VDI v_gtext requires at least 1 point and 1 text integer")
    elif command == 114 and n_pts < 2:
        raise ValueError("VDI vr_recfl requires at least 2 points")


def _sample_arc_points(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    beg_tenths: int,
    end_tenths: int,
    *,
    closed_pie: bool = False,
) -> list[list[float]]:
    span = (end_tenths - beg_tenths) % 3600
    if span == 0:
        span = 3600
    steps = max(6, min(36, span // 100))
    pts: list[list[float]] = []
    if closed_pie:
        pts.append([float(cx), float(cy)])
    for step in range(steps + 1):
        ang_deg = (beg_tenths + span * (step / steps)) / 10.0
        rad = math.radians(ang_deg)
        # Screen-space RC top-left origin (+y downward): VDI CCW angles negate sin
        px = max(-32767.0, min(32767.0, round(cx + rx * math.cos(rad), 2)))
        py = max(-32767.0, min(32767.0, round(cy - ry * math.sin(rad), 2)))
        if not pts or abs(pts[-1][0] - px) > 1e-6 or abs(pts[-1][1] - py) > 1e-6:
            pts.append([px, py])
    return pts


def scene_from_metafile(data: bytes | bytearray | memoryview, constraints: Sequence[dict[str, Any]] = ()) -> Scene:
    parsed = parse_metafile(data)
    objects: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] | None = None
    line_color = fill_color = text_color = "black"
    custom_colors: dict[int, str] = {}
    interior = 0
    fill_perimeter = 1
    line_width = 20
    text_height = 240
    no_line_style = False
    in_shadow_block = False

    for record in parsed["records"]:
        command = record["command"]
        subcommand = record.get("subcommand", 0)
        if command == -1:
            continue
        _validate_record_operands(record)

        if command == 5 and subcommand == 99:
            sub_op = record["values"][0]
            if sub_op == META_OBJECT:
                candidate = _parse_metadata(record)
                if candidate is not None:
                    metadata = None if candidate.get("part") == "slide_meta" else candidate
            elif sub_op == META_NO_LINE_STYLE:
                no_line_style = True
            elif sub_op == META_SHADOW_ON:
                in_shadow_block = True
            elif sub_op == META_SHADOW_OFF:
                in_shadow_block = False
            continue

        if command == 13:
            if len(record["values"]) == 1:
                continue  # spec-exact vst_rotation
            index, red, green, blue = record["values"][:4]
            channels = [min(255, max(0, round(value * 255 / 1000))) for value in (red, green, blue)]
            custom_colors[index] = "#" + "".join(f"{channel:02x}" for channel in channels)
            continue

        if command == 14:
            index, red, green, blue = record["values"][:4]
            channels = [min(255, max(0, round(value * 255 / 1000))) for value in (red, green, blue)]
            custom_colors[index] = "#" + "".join(f"{channel:02x}" for channel in channels)
            continue

        if command == 15:
            no_line_style = False
            continue
        if command == 16:
            line_width = max(1, record["coordinates"][0])
            continue
        if command == 17:
            index = record["values"][0]
            line_color = custom_colors.get(index, INDEX_COLOR.get(index, "black"))
            continue
        if command == 12:
            text_height = max(1, record["coordinates"][1])
            continue
        if command == 25:
            index = record["values"][0]
            fill_color = custom_colors.get(index, INDEX_COLOR.get(index, "black"))
            continue
        if command == 23:
            interior = record["values"][0]
            continue
        if command == 104:
            fill_perimeter = 1 if record["values"][0] else 0
            continue
        if command == 22:
            index = record["values"][0]
            text_color = custom_colors.get(index, INDEX_COLOR.get(index, "black"))
            continue
        if command in (21, 24, 32, 39, 106, 107, 108):
            continue

        if in_shadow_block:
            continue

        if command == 8 and metadata and metadata.get("part") == "label":
            parent = objects.get(metadata["id"])
            if parent is not None:
                parent["label"] = _text(record)
            metadata = None
            continue

        object_id = metadata["id"] if metadata else f"vdi-object-{len(objects)}"
        object_type = metadata.get("type") if metadata else None
        points = _points(record)
        values = record["values"]

        if command == 9 and metadata and metadata.get("type") == "mesh":
            mesh = objects.get(object_id)
            if mesh is None:
                mesh = {
                    "id": object_id, "type": "mesh", "points": [], "fills": [],
                    "fill": "none", "stroke": "none", "width": metadata.get("width", 0),
                }
                objects[object_id] = mesh
            mesh["points"].extend(points[:3])
            mesh["fills"].append(fill_color)
            continue

        effective_stroke = "none" if no_line_style else line_color
        current: dict[str, Any] | None = None

        if command == 11 and subcommand in {1, 8, 9} and len(points) == 2:
            x0, y0 = points[0]
            x1, y1 = points[1]
            bounds = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            is_filled = subcommand != 8 and interior != 0
            bar_stroke = effective_stroke
            if not metadata and subcommand in {1, 9} and fill_perimeter == 0:
                bar_stroke = "none"
            current = {
                "id": object_id, "type": "rectangle", "bounds": bounds,
                "fill": fill_color if is_filled else "none", "stroke": bar_stroke,
            }
        elif command == 114 and len(points) == 2:
            x0, y0 = points[0]
            x1, y1 = points[1]
            bounds = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            current = {
                "id": object_id, "type": "rectangle", "bounds": bounds,
                "fill": fill_color if interior else "none", "stroke": "none",
            }
        elif command == 9 and len(points) >= 3:
            poly_type = object_type if object_type in {"polygon", "polyline"} else "polygon"
            current = {
                "id": object_id, "type": poly_type, "points": points,
                "fill": fill_color if interior else "none", "stroke": effective_stroke,
            }
        elif command == 6 and len(points) >= 2:
            default_line_type = "line" if len(points) == 2 else "polyline"
            line_type_resolved = (
                object_type
                if object_type in {"line", "polyline"} and (object_type != "line" or len(points) == 2)
                else default_line_type
            )
            current = {
                "id": object_id, "type": line_type_resolved,
                "points": points, "fill": "none", "stroke": effective_stroke,
            }
        elif command == 11 and subcommand == 4 and len(points) in {2, 3}:
            r = max(1, abs(points[-1][0]))
            current = {
                "id": object_id, "type": "ellipse", "center": points[0], "radii": [r, r],
                "fill": fill_color if interior else "none", "stroke": effective_stroke,
            }
        elif command == 11 and subcommand == 5 and len(points) == 2:
            rx, ry = max(1, abs(points[1][0])), max(1, abs(points[1][1]))
            current = {
                "id": object_id, "type": "ellipse", "center": points[0], "radii": [rx, ry],
                "fill": fill_color if interior else "none", "stroke": effective_stroke,
            }
        elif command == 11 and subcommand in {2, 6} and len(points) >= 2:
            cx, cy = points[0]
            if subcommand == 2:
                rx = ry = max(1, abs(points[-1][0]))
            else:
                rx, ry = max(1, abs(points[1][0])), max(1, abs(points[1][1]))
            arc_pts = _sample_arc_points(cx, cy, rx, ry, values[0], values[1], closed_pie=False)
            if len(arc_pts) >= 2:
                current = {
                    "id": object_id,
                    "type": "line" if len(arc_pts) == 2 else "polyline",
                    "points": arc_pts,
                    "fill": "none",
                    "stroke": effective_stroke,
                }
        elif command == 11 and subcommand in {3, 7} and len(points) >= 2:
            cx, cy = points[0]
            if subcommand == 3:
                rx = ry = max(1, abs(points[-1][0]))
            else:
                rx, ry = max(1, abs(points[1][0])), max(1, abs(points[1][1]))
            pie_pts = _sample_arc_points(cx, cy, rx, ry, values[0], values[1], closed_pie=True)
            if len(pie_pts) >= 3:
                current = {
                    "id": object_id,
                    "type": "polygon",
                    "points": pie_pts,
                    "fill": fill_color if interior else "none",
                    "stroke": effective_stroke,
                }
        elif command == 8 and len(points) == 1:
            txt = _text(record) or " "
            current = {
                "id": object_id, "type": "text", "position": points[0], "text": txt,
                "size": metadata.get("size", text_height) if metadata else text_height,
                "fill": "none", "stroke": text_color,
            }

        if current is None:
            continue
        if object_type in OBJECT_TYPES and (
            object_type == current["type"]
            or (
                current["type"] in {"line", "polyline"}
                and object_type in {"line", "polyline"}
                and (object_type != "line" or len(current.get("points", [])) == 2)
            )
            or (current["type"] == "polygon" and object_type == "polyline")
        ):
            current["type"] = object_type
        current["width"] = metadata.get("width", line_width) if metadata else line_width
        for key in ("role", "event_id", "status", "selected", "from", "to"):
            if metadata and key in metadata:
                current[key] = metadata[key]
        if object_id in objects:
            objects[object_id].update(current)
        else:
            objects[object_id] = current
        metadata = None

    coord_bounds = parsed["header"]["coordinate_bounds"]
    coord_sys = parsed["header"]["coordinate_system"]
    canvas_w = coord_bounds[2] if coord_bounds[2] > 0 else (32767 if coord_sys == 0 else SLIDE_CANVAS_WIDTH)
    canvas_h = coord_bounds[3] if coord_bounds[3] > 0 else (32767 if coord_sys == 0 else SLIDE_CANVAS_HEIGHT)
    document = {
        "schema_version": 1,
        "id": "vdi-roundtrip",
        "canvas": {
            "width": canvas_w,
            "height": canvas_h,
        },
        "objects": list(objects.values()),
        "constraints": list(constraints),
    }
    return Scene.from_dict(document)


def opcode_inventory(data: bytes | bytearray | memoryview) -> dict[str, int]:
    parsed = parse_metafile(data)
    inventory: dict[str, int] = {}
    for record in parsed["records"]:
        command = record["command"]
        if command == -1:
            continue
        key = OPCODE_NAMES.get(command, f"opcode_{command}")
        if command == 11:
            key = GDP_NAMES.get(record["subcommand"], key)
        elif command == 5:
            key = ESCAPE_NAMES.get(record["subcommand"], key)
        elif command == 13:
            if record["integers"] == 1:
                key = "vst_rotation"
            elif record["integers"] == 4:
                key = "vs_color_legacy"
            else:
                key = "opcode_13"
        inventory[key] = inventory.get(key, 0) + 1
    return inventory

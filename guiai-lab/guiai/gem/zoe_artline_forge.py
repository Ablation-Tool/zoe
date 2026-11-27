"""Zoe Artline Forge — Clean-Room .AF4/.SYF Vector Inspector, Programmable Toolboxes & GEM .COL Palettes.

100% original clean-room Python + NumPy + PIL + Artline/GEM VDI + offline HTML5 Studio.
Inspired by structural reverse-engineering of Digital Research / CCP Software Artline (1988-1990):
  1. Clean-room CCP Bezier & Polygon Vector Evaluator:
       - Decodes `.AF4` (v4, e.g. `wombat.af4` / `symbol.af4`) outline fonts and `.SYF` (`CCPA002`)
         symbol libraries (`STARS.SYF`, `FLOWERS.SYF`, `ARROWS.SYF`, etc.) using cubic Bezier
         point-flag triples (`0x20` start, `0x08` line, `0x09/0x18/0x10` cubic Bezier, `0x02` next contour).
       - Renders crisp dark-studio PNG contact sheets & SVG paths.
  2. Clean-Room Programmable Toolboxes (`ZOETK001`, inspired by Artline 2.0 `CCPTK001` `.TLS` files):
       - Round-trip JSON + compact binary `ZOETK001` toolbox definitions (`brainstorm_desk`,
         `align_9way`, `physics_smash`, `adc12_shorthand`).
  3. Clean-Room Vector-Metafile Color Palettes (inspired by Artline 2.0 `.COL`-as-`0xFFFF`-GEM files):
       - Compiles studio palettes (`zoe_studio`, `gem_classic`, `artline_cmyk`, `botanical_neon`)
         directly into valid `0xFFFF` Digital Research GEM VDI metafiles + `.SVG` swatch cards.
  4. Live Interactive `:8765/forge` Web Studio & Offline HTML5 Playground.

Constitutional Invariants (`CONSTITUTION.md`):
  clean_room_original = True · proprietary_code_copied = 0 · external_actions = 0
  sentience_claimed = False · clinical_action_authorized = False · cloud_tokens_used = 0
"""

from __future__ import annotations

import base64
import copy
from dataclasses import asdict, dataclass, field
import hashlib
import html as html_lib
import json
import math
from pathlib import Path
import re
import struct
import threading
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont

from .artline import ArtlineDocument
from .vdi import INDEX_COLOR, VdiMetafileBuilder, _record, opcode_inventory, parse_metafile

ARTLINE_FORGE_CONTRACT = "zoe-artline-forge/v1"

CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "clean_room_original": True,
    "proprietary_code_copied": 0,
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "cloud_tokens_used": 0,
    "attribution": "Nicholas Michael Kloster; clean-room formats inspired by Digital Research Artline (1988-1990)",
}

DEFAULT_EXTRACTED_ROOT = Path("/media/cowboy/research/GEM/analysis/artline-ablation-re/extracted")


# ---------------------------------------------------------------------------
# 1. Clean-Room CCP Cubic Bezier & Polygon Vector Record Evaluator
# ---------------------------------------------------------------------------

def _eval_cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 8,
) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        t = k / float(steps)
        u = 1.0 - t
        x = (u ** 3) * p0[0] + 3 * (u ** 2) * t * p1[0] + 3 * u * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = (u ** 3) * p0[1] + 3 * (u ** 2) * t * p1[1] + 3 * u * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        out.append((x, y))
    return out


def decode_ccp_contours(
    coords: Sequence[tuple[int, int]],
    flags: Sequence[int],
    *,
    bezier_steps: int = 8,
) -> list[list[tuple[float, float]]]:
    """Convert CCP (x, y) coordinates + point-flag bytes into sampled vector contours.

    Byte-exact flag bitmask verified against 1988-1990 Digital Research / CCP `.AF4` & `.SYF`:
      - `0x20` / `0x02` (`mask 0x22`): Move-To (start a new sub-contour at this on-curve vertex)
      - `0x01`: cubic Bezier leaves THIS on-curve vertex via the next two off-curve
                control points (`flag & 0x10`, i.e. `0x18`/`0x10`) to endpoint `i+3`
                (can combine with `0x20` -> `0x21` or `0x02` -> `0x03`!)
      - `0x08`: on-curve vertex (line segment into this point when `0x22` is clear)
      - `0x04`: end of shape (`0x0C`)
    """
    n = min(len(coords), len(flags))
    if n < 2:
        return []

    contours: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = [(float(coords[0][0]), float(coords[0][1]))]
    i = 0
    while i < n:
        fl = flags[i]
        # Cubic Bezier leaves on-curve point i -> CP1=i+1, CP2=i+2, End=i+3
        if (
            (fl & 0x01) != 0
            and i + 3 < n
            and (flags[i + 1] & 0x10) != 0
            and (flags[i + 2] & 0x10) != 0
        ):
            p0 = (float(coords[i][0]), float(coords[i][1]))
            p1 = (float(coords[i + 1][0]), float(coords[i + 1][1]))
            p2 = (float(coords[i + 2][0]), float(coords[i + 2][1]))
            p3 = (float(coords[i + 3][0]), float(coords[i + 3][1]))
            cur.extend(_eval_cubic_bezier(p0, p1, p2, p3, steps=bezier_steps))
            i += 3
            continue

        if i + 1 >= n:
            break
        i += 1
        next_pt = (float(coords[i][0]), float(coords[i][1]))
        if (flags[i] & 0x22) != 0:
            # Explicit Move-To (0x02, 0x03, 0x0A, 0x20, 0x21, 0x28): start fresh sub-contour
            if len(cur) >= 2:
                contours.append(cur)
            cur = [next_pt]
        else:
            cur.append(next_pt)

    if len(cur) >= 2:
        contours.append(cur)
    return contours


def decode_ccp_segments(
    coords: Sequence[tuple[int, int]],
    flags: Sequence[int],
) -> list[list[tuple[Any, ...]]]:
    """Convert CCP (x, y) coordinates + point-flag bytes into exact M/L/C Bezier sub-contour commands."""
    n = min(len(coords), len(flags))
    if n < 2:
        return []

    segments: list[list[tuple[Any, ...]]] = []
    cur: list[tuple[Any, ...]] = [("M", (float(coords[0][0]), float(coords[0][1])))]
    i = 0
    while i < n:
        fl = flags[i]
        if (
            (fl & 0x01) != 0
            and i + 3 < n
            and (flags[i + 1] & 0x10) != 0
            and (flags[i + 2] & 0x10) != 0
        ):
            p1 = (float(coords[i + 1][0]), float(coords[i + 1][1]))
            p2 = (float(coords[i + 2][0]), float(coords[i + 2][1]))
            p3 = (float(coords[i + 3][0]), float(coords[i + 3][1]))
            cur.append(("C", p1, p2, p3))
            i += 3
            continue

        if i + 1 >= n:
            break
        i += 1
        next_pt = (float(coords[i][0]), float(coords[i][1]))
        if (flags[i] & 0x22) != 0:
            if len(cur) >= 2:
                segments.append(cur)
            cur = [("M", next_pt)]
        else:
            cur.append(("L", next_pt))

    if len(cur) >= 2:
        segments.append(cur)
    return segments


def contours_to_svg_path(
    contours: Sequence[Sequence[tuple[float, float]]],
    *,
    flip_y: bool = False,
    box_size: float = 100.0,
    pad: float = 8.0,
    smooth: bool = False,
    smooth_cubic: bool = False,
    bezier_segments: Sequence[Sequence[tuple[Any, ...]]] | None = None,
) -> str:
    """Normalize contours (or exact CCP Bezier segments) into an SVG `d` path fitting `[pad, box_size - pad]`."""
    use_smooth = smooth or smooth_cubic
    if bezier_segments:
        raw_pts: list[tuple[float, float]] = []
        for sub in bezier_segments:
            for seg in sub:
                for pt in seg[1:]:
                    raw_pts.append((float(pt[0]), float(pt[1])))
        if not raw_pts:
            return ""
        xs = [p[0] for p in raw_pts]
        ys = [-p[1] if flip_y else p[1] for p in raw_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span = max(1e-6, max(max_x - min_x, max_y - min_y))
        scale = (box_size - 2.0 * pad) / span
        ox = pad + (box_size - 2.0 * pad - (max_x - min_x) * scale) * 0.5
        oy = pad + (box_size - 2.0 * pad - (max_y - min_y) * scale) * 0.5

        def _map(pt: tuple[float, float]) -> tuple[float, float]:
            ny = -float(pt[1]) if flip_y else float(pt[1])
            return (ox + (float(pt[0]) - min_x) * scale, oy + (ny - min_y) * scale)

        b_parts: list[str] = []
        for sub in bezier_segments:
            if len(sub) < 2:
                continue
            for seg in sub:
                cmd = seg[0]
                if cmd in ("M", "L"):
                    sx, sy = _map(seg[1])
                    b_parts.append(f"{cmd}{sx:.1f},{sy:.1f}")
                elif cmd == "C":
                    c1x, c1y = _map(seg[1])
                    c2x, c2y = _map(seg[2])
                    p3x, p3y = _map(seg[3])
                    b_parts.append(f"C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p3x:.1f},{p3y:.1f}")
            b_parts.append("Z")
        return " ".join(b_parts)

    all_pts = [pt for c in contours for pt in c]
    if not all_pts:
        return ""
    xs = [p[0] for p in all_pts]
    ys = [-p[1] if flip_y else p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(1e-6, max(max_x - min_x, max_y - min_y))
    scale = (box_size - 2.0 * pad) / span
    ox = pad + (box_size - 2.0 * pad - (max_x - min_x) * scale) * 0.5
    oy = pad + (box_size - 2.0 * pad - (max_y - min_y) * scale) * 0.5

    parts: list[str] = []
    for c in contours:
        if len(c) < 2:
            continue
        mapped = [
            (ox + (px - min_x) * scale, oy + ((-py if flip_y else py) - min_y) * scale)
            for px, py in c
        ]
        if use_smooth and len(mapped) >= 3:
            pts = list(mapped)
            if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-3 and len(pts) > 3:
                pts = pts[:-1]
            m = len(pts)
            parts.append(f"M{pts[0][0]:.1f},{pts[0][1]:.1f}")
            for i in range(m):
                p0 = pts[(i - 1) % m]
                p1 = pts[i]
                p2 = pts[(i + 1) % m]
                p3 = pts[(i + 2) % m]
                c1x = p1[0] + (p2[0] - p0[0]) / 6.0
                c1y = p1[1] + (p2[1] - p0[1]) / 6.0
                c2x = p2[0] - (p3[0] - p1[0]) / 6.0
                c2y = p2[1] - (p3[1] - p1[1]) / 6.0
                parts.append(f"C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {p2[0]:.1f},{p2[1]:.1f}")
            parts.append("Z")
        else:
            first = True
            for sx, sy in mapped:
                parts.append(f"{'M' if first else 'L'}{sx:.1f},{sy:.1f}")
                first = False
            parts.append("Z")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 2. Clean-Room .AF4 Outline Font Decoder (wombat.af4, symbol.af4, nsans_n.af4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AF4Glyph:
    char_code: int
    glyph_index: int
    advance_width: int
    bbox: tuple[int, int, int, int]
    point_count: int
    contours: tuple[tuple[tuple[float, float], ...], ...]
    svg_path: str
    bezier_svg_path: str = ""
    bezier_segments: tuple[tuple[tuple[Any, ...], ...], ...] = ()


_ATARI_UNICODE_EXTRA: dict[str, tuple[int, ...]] = {
    "ß": (225, 158),
    "ã": (176,),
    "õ": (177,),
    "Ø": (178,),
    "ø": (179,),
    "œ": (180,),
    "Œ": (181,),
    "À": (182,),
    "Ã": (183,),
    "Õ": (184,),
    "©": (189,),
    "®": (190,),
    "™": (191,),
}


def _build_unicode_to_cp437_map() -> dict[str, int]:
    mapping: dict[str, int] = {}
    for code in range(128, 256):
        ch = bytes([code]).decode("cp437", "replace")
        if ch != "\ufffd" and ch != "\xa0" and ord(ch) >= 128 and ch not in mapping:
            mapping[ch] = code
    for ch, codes in _ATARI_UNICODE_EXTRA.items():
        if ch == "ß":
            mapping[ch] = 225
        elif ch not in mapping:
            mapping[ch] = codes[0]
    return mapping


_UNICODE_TO_CP437_MAP: dict[str, int] = _build_unicode_to_cp437_map()


@dataclass(frozen=True)
class AF4Font:
    filename: str
    internal_filename: str
    font_id: int
    display_name: str
    copyright_text: str
    first_char: int
    last_char: int
    glyph_count: int
    glyphs_by_char: dict[int, AF4Glyph]
    font_bbox: tuple[int, int, int, int] = (0, -250, 1000, 1000)
    space_width: int = 300
    char_advances: dict[int, int] = field(default_factory=dict)
    kerning_pairs: tuple[tuple[int, int, int], ...] = ()

    def resolve_char_code(self, ch_str: str) -> int:
        if not ch_str:
            return 0
        raw = ord(ch_str)
        if raw < 128:
            return raw
        candidates: list[int] = []
        if ch_str in _ATARI_UNICODE_EXTRA:
            candidates.extend(_ATARI_UNICODE_EXTRA[ch_str])
        try:
            cp_byte = ch_str.encode("cp437")[0]
            if cp_byte not in candidates:
                candidates.append(cp_byte)
        except UnicodeEncodeError:
            pass
        if raw not in candidates:
            candidates.append(raw)
        for code in candidates:
            if code in self.glyphs_by_char:
                return code
        for code in candidates:
            if code in self.char_advances:
                return code
        return candidates[0] if candidates else raw

    def kerning_delta(self, left_char: int | str, right_char: int | str) -> int:
        lc = (
            self.resolve_char_code(left_char)
            if isinstance(left_char, str) and len(left_char) == 1
            else (ord(left_char) if isinstance(left_char, str) else int(left_char))
        )
        rc = (
            self.resolve_char_code(right_char)
            if isinstance(right_char, str) and len(right_char) == 1
            else (ord(right_char) if isinstance(right_char, str) else int(right_char))
        )
        for p_left, p_right, delta in self.kerning_pairs:
            if p_left == lc and p_right == rc:
                return delta
        return 0

    def summary_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "stem": Path(self.filename).stem,
            "internal_filename": self.internal_filename,
            "font_id": self.font_id,
            "display_name": self.display_name,
            "copyright_text": self.copyright_text,
            "first_char": self.first_char,
            "last_char": self.last_char,
            "glyph_count": self.glyph_count,
            "decoded_chars": len(self.glyphs_by_char),
            "font_bbox": list(self.font_bbox),
            "space_width": self.space_width,
            "kerning_pairs_count": len(self.kerning_pairs),
        }


def decode_af4_bytes(data: bytes, filename: str = "font.af4") -> AF4Font:
    """Decode an Artline 2.0 `.AF4` (version 0x0004) outline font buffer cleanly (with composites & kerning)."""
    if len(data) < 0x90:
        raise ValueError("Buffer too small to be a valid .AF4 outline font")
    version = struct.unpack_from("<H", data, 0)[0]
    if version != 4:
        raise ValueError(f"Expected .AF4 version 4, got {version}")

    internal_fn = data[2:16].split(b"\x00", 1)[0].decode("ascii", "replace")
    font_id = struct.unpack_from("<H", data, 0x10)[0]
    display_name = data[0x14:0x34].split(b"\x00", 1)[0].decode("ascii", "replace")
    copyright_raw = data[0x34:0x54].split(b"\x00", 1)[0]
    copyright_text = copyright_raw.replace(b"\xbd", b"(c)").decode("ascii", "replace").strip()
    first_ch, last_ch = struct.unpack_from("<HH", data, 0x54)
    font_bbox_raw = struct.unpack_from("<4h", data, 0x58)
    font_bbox = (
        int(font_bbox_raw[0]),
        int(font_bbox_raw[1]),
        int(font_bbox_raw[2]),
        int(font_bbox_raw[3]),
    )
    w62, _w64, vec_len = struct.unpack_from("<3H", data, 0x62)
    kerning_count = struct.unpack_from("<H", data, 0x6E)[0]

    # Kerning-table-aware geometry verified across all 35/35 1989-1990 Artline 2.0 .AF4 fonts:
    # kerning pairs (4 bytes each: <hBB = delta, left_char, right_char) sit after the vector blob at EOF.
    vec_end = len(data) - 4 * kerning_count
    data_start = vec_end - vec_len
    off_tbl = data_start - 6 * w62
    if off_tbl < 0x8A or data_start < 0 or vec_end > len(data) or data_start >= vec_end:
        raise ValueError(f"Invalid .AF4 table geometry for {filename}")

    kern_list: list[tuple[int, int, int]] = []
    for k_idx in range(kerning_count):
        delta, left_ch, right_ch = struct.unpack_from("<hBB", data, vec_end + k_idx * 4)
        kern_list.append((int(left_ch), int(right_ch), int(delta)))

    off_entries = [struct.unpack_from("<HI", data, off_tbl + i * 6) for i in range(w62)]
    max_slots = min(239, (off_tbl - 0x8A) // 22)

    char_advances: dict[int, int] = {}
    space_width = 300
    glyphs: dict[int, AF4Glyph] = {}

    for slot in range(max_slots):
        ch = 32 + slot
        rec_off = 0x8A + slot * 22
        gidx, fl, adv, x0, y0, x1, y1 = struct.unpack_from("<HHH4h", data, rec_off)
        if adv > 0:
            char_advances[ch] = int(adv)
            if ch == 32:
                space_width = int(adv)
        if gidx == 0xFFFF or gidx >= len(off_entries):
            continue

        entry_count = max(1, int(fl))
        if gidx + entry_count > len(off_entries):
            continue

        all_contours: list[tuple[tuple[float, float], ...]] = []
        all_segments: list[tuple[tuple[Any, ...], ...]] = []
        total_npts = 0
        dx, dy = 0, 0

        for k in range(entry_count):
            entry_idx = gidx + k
            tag, raw4 = off_entries[entry_idx]
            if tag == 0x0002:
                dx, dy = struct.unpack_from("<hh", data, off_tbl + entry_idx * 6 + 2)
            elif tag in (0x0080, 0x0100):
                gp = data_start + raw4
                if gp + 2 > vec_end:
                    dx, dy = 0, 0
                    continue
                npts = struct.unpack_from("<H", data, gp)[0]
                if npts < 2 or npts > 1200 or gp + 2 + 5 * npts > vec_end:
                    dx, dy = 0, 0
                    continue
                coords: list[tuple[int, int]] = []
                for pt_i in range(npts):
                    px, py = struct.unpack_from("<hh", data, gp + 2 + pt_i * 4)
                    coords.append((int(px + dx), int(py + dy)))
                flags = list(data[gp + 2 + npts * 4 : gp + 2 + npts * 5])
                sub_contours = decode_ccp_contours(coords, flags, bezier_steps=8)
                sub_segments = decode_ccp_segments(coords, flags)
                for c in sub_contours:
                    all_contours.append(tuple(c))
                for seg in sub_segments:
                    all_segments.append(tuple(seg))
                total_npts += npts
                dx, dy = 0, 0

        if not all_contours:
            continue
        svg_p = contours_to_svg_path(all_contours, flip_y=True, box_size=100.0, pad=8.0)
        bezier_p = (
            contours_to_svg_path(
                all_contours,
                flip_y=True,
                box_size=100.0,
                pad=8.0,
                bezier_segments=all_segments,
            )
            if all_segments
            else svg_p
        )
        glyphs[ch] = AF4Glyph(
            char_code=ch,
            glyph_index=gidx,
            advance_width=adv,
            bbox=(x0, y0, x1, y1),
            point_count=total_npts,
            contours=tuple(all_contours),
            svg_path=svg_p,
            bezier_svg_path=bezier_p,
            bezier_segments=tuple(all_segments),
        )

    return AF4Font(
        filename=filename,
        internal_filename=internal_fn,
        font_id=font_id,
        display_name=display_name,
        copyright_text=copyright_text,
        first_char=first_ch,
        last_char=last_ch,
        glyph_count=w62,
        glyphs_by_char=glyphs,
        font_bbox=font_bbox,
        space_width=space_width,
        char_advances=char_advances,
        kerning_pairs=tuple(kern_list),
    )


def decode_af4_font(path: str | Path) -> AF4Font:
    p = Path(path)
    return decode_af4_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_af4_bytes() -> bytes:
    """Build a tiny 100% clean-room synthetic .AF4 v4 font (with space advance & kerning pairs for CI)."""
    hdr = bytearray(0x8A)
    struct.pack_into("<H", hdr, 0, 4)
    hdr[2:14] = b"ZOESYNTH.AF4"
    struct.pack_into("<H", hdr, 0x10, 129)
    hdr[0x14:0x23] = b"Zoe Synth Forge"
    hdr[0x34:0x4B] = b"(c) Clean-Room Zoe 2026"
    struct.pack_into("<HH", hdr, 0x54, 32, 120)
    struct.pack_into("<4h", hdr, 0x58, 0, -100, 1000, 950)

    # Create 2 clean geometric glyphs: char 90 ('Z' = diamond) & char 78 ('N' = star)
    diamond_pts = [(500, 900), (900, 500), (500, 100), (100, 500), (500, 900)]
    diamond_fl = [0x20, 0x08, 0x08, 0x08, 0x08]
    star_pts = []
    for k in range(11):
        rad = 420 if k % 2 == 0 else 190
        ang = math.radians(90 - k * 36)
        star_pts.append((int(500 + rad * math.cos(ang)), int(500 + rad * math.sin(ang))))
    star_fl = [0x20] + [0x08] * 10

    def pack_rec(pts: list[tuple[int, int]], fl: list[int]) -> bytes:
        buf = bytearray(struct.pack("<H", len(pts)))
        for x, y in pts:
            buf.extend(struct.pack("<hh", x, y))
        buf.extend(bytes(fl))
        return bytes(buf)

    g0 = pack_rec(star_pts, star_fl)
    g1 = pack_rec(diamond_pts, diamond_fl)
    vec_blob = g0 + g1
    struct.pack_into("<3H", hdr, 0x62, 2, 2, len(vec_blob))
    # 2 clean-room synthetic kerning pairs: ('N','Z',-80) and ('Z','N',40)
    struct.pack_into("<H", hdr, 0x6E, 2)

    slots = bytearray()
    for ch in range(32, 121):
        if ch == 32:
            slots.extend(struct.pack("<HHH4h8s", 0xFFFF, 0, 320, 0, 0, 0, 0, b"\x00" * 8))
        elif ch == 78:
            slots.extend(struct.pack("<HHH4h8s", 0, 1, 900, 80, 80, 920, 920, b"\x00" * 8))
        elif ch == 90:
            slots.extend(struct.pack("<HHH4h8s", 1, 1, 900, 100, 100, 900, 900, b"\x00" * 8))
        else:
            slots.extend(struct.pack("<H20s", 0xFFFF, b"\x00" * 20))

    off_tbl = struct.pack("<HI", 0x0100, 0) + struct.pack("<HI", 0x0100, len(g0))
    kern_tbl = struct.pack("<hBB", -80, 78, 90) + struct.pack("<hBB", 40, 90, 78)
    return bytes(hdr + slots + off_tbl + vec_blob + kern_tbl)


# ---------------------------------------------------------------------------
# 3. Clean-Room .SYF (CCPA002) Symbol Library Decoder
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SYFSymbol:
    index: int
    name: str
    width: int
    height: int
    point_count: int
    contours: tuple[tuple[tuple[float, float], ...], ...]
    svg_path: str


@dataclass(frozen=True)
class SYFLibrary:
    filename: str
    magic: str
    declared_count: int
    symbols: tuple[SYFSymbol, ...]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "magic": self.magic,
            "declared_count": self.declared_count,
            "decoded_count": len(self.symbols),
            "symbol_names": [s.name for s in self.symbols],
        }


def decode_syf_bytes(data: bytes, filename: str = "library.syf") -> SYFLibrary:
    """Decode a CCP Software GmbH `CCPA002\\0` Artline 1.0 `.SYF` multi-object symbol library.

    Exact container framing verified across all 20 1988 `.SYF` files (378 symbols / 2,742 sub-objects):
      - 12-byte file header: `b"CCPA002\\x00"` + `u16 symbol_count` + `u16 0`
      - Per symbol: 26-byte header (`u16 tag`, 14B ASCII name, 10B metadata), followed by a
        null-terminated sequence (`u16 obj_type == 0x0000`) of vector sub-objects:
        each sub-object has 24B bbox/style header (`w` at `+8`, `h` at `+10`), `u16 obj_bytes`
        at `+24` (`== 14 + 5 * npts`), 12B paint/line attrs, `u16 npts` at `+38`,
        `npts * (i16 x, i16 y)`, and `npts` CCP point-flag bytes.
    """
    if len(data) < 12 or data[:8] != b"CCPA002\x00":
        raise ValueError(f"Not a valid CCPA002 .SYF file: {filename}")
    declared = struct.unpack_from("<H", data, 8)[0]

    symbols: list[SYFSymbol] = []
    pos = 12
    for idx in range(declared):
        if pos + 26 > len(data):
            break
        name_raw = data[pos + 2 : pos + 16]
        name = name_raw.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
        if not name:
            name = f"SYM_{idx + 1:02d}"
        pos += 26

        all_contours: list[tuple[tuple[float, float], ...]] = []
        total_pts = 0
        sym_w, sym_h = 0, 0
        while pos + 2 <= len(data):
            otype = struct.unpack_from("<H", data, pos)[0]
            if otype == 0:
                pos += 2
                break
            if pos + 40 > len(data):
                break
            w, h = struct.unpack_from("<HH", data, pos + 8)
            if w > sym_w:
                sym_w = w
            if h > sym_h:
                sym_h = h
            obj_bytes = struct.unpack_from("<H", data, pos + 24)[0]
            npts = struct.unpack_from("<H", data, pos + 38)[0]
            rec_end = pos + 26 + obj_bytes
            if obj_bytes != 14 + 5 * npts or rec_end > len(data):
                break
            pts_off = pos + 40
            coords = [struct.unpack_from("<hh", data, pts_off + k * 4) for k in range(npts)]
            flags = list(data[pts_off + npts * 4 : pts_off + npts * 5])
            sub_contours = decode_ccp_contours(coords, flags, bezier_steps=6)
            for c in sub_contours:
                all_contours.append(tuple(c))
            total_pts += npts
            pos = rec_end

        svg_p = contours_to_svg_path(all_contours, flip_y=False, box_size=100.0, pad=8.0)
        symbols.append(
            SYFSymbol(
                index=idx,
                name=name,
                width=sym_w,
                height=sym_h,
                point_count=total_pts,
                contours=tuple(all_contours),
                svg_path=svg_p,
            )
        )

    return SYFLibrary(filename=filename, magic="CCPA002", declared_count=declared, symbols=tuple(symbols))


def decode_syf_library(path: str | Path) -> SYFLibrary:
    p = Path(path)
    return decode_syf_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_syf_bytes() -> bytes:
    """Build a clean-room synthetic CCPA002 `.SYF` library with 2 geometric symbols for portable tests."""
    buf = bytearray(b"CCPA002\x00" + struct.pack("<HH", 2, 0))
    shapes = [
        ("ZOE HEX", [(80, 10), (140, 45), (140, 115), (80, 150), (20, 115), (20, 45), (80, 10)]),
        ("NICK STAR", [(80, 10), (100, 60), (150, 60), (110, 95), (125, 145), (80, 115), (35, 145), (50, 95), (10, 60), (60, 60), (80, 10)]),
    ]
    for name, pts in shapes:
        # 26-byte symbol header
        sym_hdr = bytearray(26)
        struct.pack_into("<H", sym_hdr, 0, 0x0050)
        enc = name.encode("ascii")[:14]
        sym_hdr[2 : 2 + len(enc)] = enc
        struct.pack_into("<H", sym_hdr, 24, 1)
        buf.extend(sym_hdr)
        # Sub-object header (26B) + 12B paint + u16 npts + coords + flags
        obj_hdr = bytearray(26)
        struct.pack_into("<H", obj_hdr, 0, 0x0164)
        struct.pack_into("<HH", obj_hdr, 8, 160, 160)
        struct.pack_into("<H", obj_hdr, 24, 14 + 5 * len(pts))
        buf.extend(obj_hdr)
        buf.extend(b"\x01\x00\x02\x64\x01\x00\x01\x00\x02\x02\x01\x00")
        buf.extend(struct.pack("<H", len(pts)))
        for x, y in pts:
            buf.extend(struct.pack("<hh", x, y))
        fl = [0x28] + [0x08] * (len(pts) - 2) + [0x0C]
        buf.extend(bytes(fl))
        # Null object terminator
        buf.extend(b"\x00\x00")
    return bytes(buf)


# ---------------------------------------------------------------------------
# 4. Dark-Studio Contact-Sheet Renderers (PIL — 0 GPU, 0 Cairo needed!)
# ---------------------------------------------------------------------------

def _pil_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_contours_in_cell(
    draw: ImageDraw.ImageDraw,
    contours: Sequence[Sequence[tuple[float, float]]],
    box: tuple[int, int, int, int],
    *,
    flip_y: bool,
    stroke: tuple[int, int, int],
    fill_alpha_rgb: tuple[int, int, int],
) -> None:
    pts = [p for c in contours for p in c]
    if not pts:
        return
    x0, y0, x1, y1 = box
    xs = [p[0] for p in pts]
    ys = [-p[1] if flip_y else p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(1e-6, max(max_x - min_x, max_y - min_y))
    w, h = x1 - x0, y1 - y0
    scale = min(w, h) / span
    ox = x0 + (w - (max_x - min_x) * scale) * 0.5
    oy = y0 + (h - (max_y - min_y) * scale) * 0.5

    for idx, c in enumerate(contours):
        if len(c) < 2:
            continue
        mapped = [(ox + (px - min_x) * scale, oy + ((-py if flip_y else py) - min_y) * scale) for px, py in c]
        if idx == 0 and len(mapped) >= 3:
            draw.polygon(mapped, fill=fill_alpha_rgb)
        draw.line(mapped, fill=stroke, width=2)


def render_af4_specimen_png(
    font: AF4Font,
    out_png: str | Path,
    *,
    char_codes: Sequence[int] | None = None,
    cols: int = 8,
    highlight_chars: set[int] | None = None,
) -> dict[str, Any]:
    """Render decoded `.AF4` Bezier vector glyphs onto a crisp dark-studio contact sheet PNG."""
    selected = [c for c in (char_codes or sorted(font.glyphs_by_char.keys())[:48]) if c in font.glyphs_by_char]
    hi = highlight_chars or {90, 111, 101, 78, 73, 51, 53, 117, 118}
    rows = max(1, math.ceil(len(selected) / cols))
    cell_w, cell_h = 112, 118
    pad_x, pad_y, hdr_h = 24, 18, 68
    img_w = pad_x * 2 + cols * cell_w
    img_h = hdr_h + pad_y * 2 + rows * cell_h

    img = Image.new("RGB", (img_w, img_h), (11, 13, 24))
    draw = ImageDraw.Draw(img)
    f_title = _pil_font(17)
    f_sub = _pil_font(11)
    f_lbl = _pil_font(10)

    draw.rectangle([0, 0, img_w, 6], fill=(248, 204, 48))
    draw.text((24, 16), f"Clean-Room .AF4 Vector Specimen · {font.display_name} ({font.internal_filename} · Font ID {font.font_id})", fill=(92, 225, 230), font=f_title)
    draw.text((24, 41), f"{font.copyright_text}  ·  Showing {len(selected)} of {len(font.glyphs_by_char)} decoded Bezier vector glyphs (Gold = Z-o-e / N-I / ADC-12)", fill=(156, 172, 206), font=f_sub)

    for idx, ch in enumerate(selected):
        g = font.glyphs_by_char[ch]
        r, c = divmod(idx, cols)
        cx0 = pad_x + c * cell_w + 5
        cy0 = hdr_h + pad_y + r * cell_h + 5
        cx1 = cx0 + cell_w - 10
        cy1 = cy0 + cell_h - 10
        is_hi = ch in hi
        border = (248, 204, 48) if is_hi else (48, 64, 104)
        stroke = (248, 204, 48) if is_hi else (92, 225, 230)
        fill_c = (52, 44, 24) if is_hi else (20, 38, 56)
        draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=7, fill=(18, 24, 42), outline=border, width=2 if is_hi else 1)
        _draw_contours_in_cell(draw, g.contours, (cx0 + 12, cy0 + 10, cx1 - 12, cy1 - 24), flip_y=True, stroke=stroke, fill_alpha_rgb=fill_c)
        ch_disp = chr(ch) if 33 <= ch < 127 else f"#{ch}"
        draw.text((cx0 + 7, cy1 - 18), f"{ch:3d} '{ch_disp}' ({g.point_count}p)", fill=(248, 204, 48) if is_hi else (156, 172, 206), font=f_lbl)

    target = Path(out_png)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target), format="PNG")
    return {"path": str(target), "bytes": target.stat().st_size, "rendered_glyphs": len(selected), "size": [img_w, img_h]}


def render_syf_contact_sheet_png(
    lib: SYFLibrary,
    out_png: str | Path,
    *,
    max_symbols: int = 20,
    cols: int = 5,
) -> dict[str, Any]:
    """Render decoded `CCPA002` `.SYF` vector symbols onto a dark-studio PNG contact sheet."""
    items = list(lib.symbols[:max_symbols])
    rows = max(1, math.ceil(len(items) / cols))
    cell_w, cell_h = 152, 146
    pad_x, pad_y, hdr_h = 24, 16, 64
    img_w = pad_x * 2 + cols * cell_w
    img_h = hdr_h + pad_y * 2 + rows * cell_h

    img = Image.new("RGB", (img_w, img_h), (11, 13, 24))
    draw = ImageDraw.Draw(img)
    f_title = _pil_font(16)
    f_sub = _pil_font(11)
    f_lbl = _pil_font(10)

    draw.rectangle([0, 0, img_w, 6], fill=(255, 133, 179))
    draw.text((24, 14), f"Clean-Room CCPA002 .SYF Vector Gallery · {lib.filename}", fill=(255, 133, 179), font=f_title)
    draw.text((24, 38), f"Decoded {len(items)} symbols directly from 1988 raw 16-bit integer Bezier/polygon contours (0 GPU · 0 Cairo)", fill=(156, 172, 206), font=f_sub)

    palette = [(248, 204, 48), (92, 225, 230), (255, 133, 179), (82, 229, 168), (172, 130, 255)]
    for idx, sym in enumerate(items):
        r, c = divmod(idx, cols)
        cx0 = pad_x + c * cell_w + 6
        cy0 = hdr_h + pad_y + r * cell_h + 6
        cx1 = cx0 + cell_w - 12
        cy1 = cy0 + cell_h - 12
        col = palette[idx % len(palette)]
        fill_c: tuple[int, int, int] = (
            int(16 + col[0] * 0.22),
            int(16 + col[1] * 0.22),
            int(16 + col[2] * 0.22),
        )
        draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=8, fill=(18, 24, 42), outline=col, width=1)
        _draw_contours_in_cell(draw, sym.contours, (cx0 + 14, cy0 + 10, cx1 - 14, cy1 - 24), flip_y=False, stroke=col, fill_alpha_rgb=fill_c)
        draw.text((cx0 + 8, cy1 - 19), f"{sym.name[:14]} ({sym.point_count}p)", fill=(240, 244, 252), font=f_lbl)

    target = Path(out_png)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target), format="PNG")
    return {"path": str(target), "bytes": target.stat().st_size, "rendered_symbols": len(items), "size": [img_w, img_h]}


# ---------------------------------------------------------------------------
# 5. Clean-Room Programmable Toolboxes (ZOETK001, inspired by Artline 2.0 .TLS)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolboxButton:
    tool_id: str
    label: str
    shortcut: str
    adc12_code: str
    wombat_glyph: str
    color_hex: str


@dataclass(frozen=True)
class ZoeToolboxSpec:
    toolbox_id: str
    title: str
    columns: int
    description: str
    buttons: tuple[ToolboxButton, ...]

    def to_zoetk_binary(self) -> bytes:
        """Encode into compact clean-room binary `ZOETK001` format (inspired by Artline 2.0 `CCPTK001`)."""
        if isinstance(self.columns, bool) or not isinstance(self.columns, int) or not (1 <= self.columns <= 65535):
            raise ValueError("ZoeToolboxSpec.columns must be an integer in [1, 65535]")
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(body).digest()[:8]
        return b"ZOETK001" + struct.pack("<HHI", 1, self.columns, len(body)) + digest + body

    @classmethod
    def from_zoetk_binary(cls, raw: bytes) -> ZoeToolboxSpec:
        if len(raw) < 24 or raw[:8] != b"ZOETK001":
            raise ValueError("Invalid ZOETK001 toolbox binary")
        _ver, _cols, length = struct.unpack_from("<HHI", raw, 8)
        digest = raw[16:24]
        body = raw[24 : 24 + length]
        if hashlib.sha256(body).digest()[:8] != digest:
            raise ValueError("ZOETK001 integrity hash mismatch")
        doc = json.loads(body.decode("utf-8"))
        return cls(
            toolbox_id=doc["toolbox_id"],
            title=doc["title"],
            columns=int(doc["columns"]),
            description=doc["description"],
            buttons=tuple(ToolboxButton(**b) for b in doc["buttons"]),
        )


STUDIO_TOOLBOXES: tuple[ZoeToolboxSpec, ...] = (
    ZoeToolboxSpec(
        "brainstorm_desk",
        "Brainstorm Studio Desk",
        2,
        "Fast Artline 2.0 drafting & idea-capture palette",
        (
            ToolboxButton("select", "Selector", "V", "000", "❖", "#ac82ff"),
            ToolboxButton("bezier", "Bezier Curve", "B", "410", "✹", "#ff85b3"),
            ToolboxButton("spark", "Idea Spark", "Z", "100", "✺", "#f8cc30"),
            ToolboxButton("card", "Draft Card", "O", "700", "❏", "#5ce1e6"),
            ToolboxButton("rosette", "9-Petal Rosette", "R", "400", "✎", "#52e5a8"),
            ToolboxButton("seal", "Seal Proof", "U", "010", "◆", "#4f8ef7"),
        ),
    ),
    ZoeToolboxSpec(
        "align_9way",
        "9-Way Plane & Align Pad",
        3,
        "Inspired by Artline 2.0 align.tls bilateral symmetry tools",
        (
            ToolboxButton("align_tl", "Top-Left", "7", "420", "✤", "#5ce1e6"),
            ToolboxButton("align_tc", "Top-Center", "8", "420", "▲", "#5ce1e6"),
            ToolboxButton("align_tr", "Top-Right", "9", "420", "✤", "#5ce1e6"),
            ToolboxButton("align_ml", "Mid-Left", "4", "420", "←", "#f8cc30"),
            ToolboxButton("align_cc", "Center Axis", "5", "000", "❖", "#f35670"),
            ToolboxButton("align_mr", "Mid-Right", "6", "420", "→", "#f8cc30"),
            ToolboxButton("mirror_h", "Mirror Horiz", "H", "410", "↔", "#52e5a8"),
            ToolboxButton("mirror_v", "Mirror Vert", "J", "410", "↕", "#52e5a8"),
            ToolboxButton("snap_grid", "Snap Grid", "G", "600", "❄", "#ac82ff"),
        ),
    ),
    ZoeToolboxSpec(
        "physics_smash",
        "Optional-Physics Break Room",
        2,
        "Toggle Physics OFF, Zero-G, or safe shatter impulses",
        (
            ToolboxButton("phys_off", "Physics OFF", "0", "E00", "✌", "#52e5a8"),
            ToolboxButton("phys_zero", "Zero-G Float", "1", "E10", "❦", "#5ce1e6"),
            ToolboxButton("phys_grav", "Gravity Smash", "2", "800", "☛", "#f8cc30"),
            ToolboxButton("launch_star", "Launch Star", "N", "900", "★", "#f35670"),
            ToolboxButton("shatter_all", "Safe Shatter", "X", "X00", "✕", "#e8687a"),
            ToolboxButton("rebuild", "Instant Reset", "R", "200", "✓", "#ac82ff"),
        ),
    ),
    ZoeToolboxSpec(
        "adc12_shorthand",
        "ADC-12 Base-12 Dewey Bar",
        4,
        "All 12 Major Duodecimal classes (000_12 .. E00_12)",
        (
            ToolboxButton("c000", "000 Core", "v", "000", "❖", "#ac82ff"),
            ToolboxButton("c100", "100 Ideas", "Z", "100", "✺", "#f8cc30"),
            ToolboxButton("c200", "200 Approve", "3", "200", "✓", "#52e5a8"),
            ToolboxButton("c300", "300 Science", "S", "300", "✶", "#4f8ef7"),
            ToolboxButton("c400", "400 Art", ".", "400", "✎", "#ff85b3"),
            ToolboxButton("c500", "500 Build", "l", "500", "●", "#5ce1e6"),
            ToolboxButton("c600", "600 Verify", "e", "600", "❄", "#6cb4ff"),
            ToolboxButton("c700", "700 Drafts", "o", "700", "❏", "#7be0d6"),
            ToolboxButton("c800", "800 Action", "*", "800", "☛", "#ffb347"),
            ToolboxButton("c900", "900 Starred", "N", "900", "★", "#f35670"),
            ToolboxButton("cX00", "X00 Guard", "5", "X00", "✕", "#e8687a"),
            ToolboxButton("cE00", "E00 Play", ",", "E00", "✌", "#88f0b8"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# 6. Clean-Room Vector-Metafile Color Palettes (inspired by Artline 2.0 .COL)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaletteSwatch:
    name: str
    hex_color: str
    cmyk: tuple[int, int, int, int]


@dataclass(frozen=True)
class ZoeVectorPalette:
    palette_id: str
    title: str
    swatches: tuple[PaletteSwatch, ...]

    def to_artline_document(self) -> ArtlineDocument:
        """Compile palette into an authentic `0xFFFF` GEM VDI metafile (`.col`/`.gem`) + `.svg` plate."""
        doc = ArtlineDocument()
        doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0b0d18", stroke="#0b0d18", width=1)
        doc.add_element("rectangle", bounds=[24, 20, 976, 680], fill="#12182c", stroke="#5ce1e6", width=1.8)
        doc.add_element("text", position=[46, 52], text=f"ZOE VECTOR PALETTE (.COL-as-GEM) · {self.title}", size=18, stroke="#f8cc30", width=1)
        doc.add_element("text", position=[46, 78], text="Inspired by Digital Research Artline 2.0 .COL palettes stored as valid 0xFFFF GEM VDI metafiles", size=11, stroke="#94a3c8", width=1)

        cols = 4
        for idx, sw in enumerate(self.swatches):
            r, c = divmod(idx, cols)
            x0 = 46 + c * 228
            y0 = 104 + r * 268
            doc.add_element("rectangle", bounds=[x0, y0, x0 + 208, y0 + 242], fill="#161f38", stroke=sw.hex_color, width=2.0)
            doc.add_element("rectangle", bounds=[x0 + 14, y0 + 14, x0 + 194, y0 + 162], fill=sw.hex_color, stroke="#f4ebd6", width=1.2)
            doc.add_element("text", position=[x0 + 16, y0 + 190], text=sw.name, size=13, stroke="#f0f4fc", width=1)
            doc.add_element("text", position=[x0 + 16, y0 + 212], text=f"{sw.hex_color.upper()}  CMYK {sw.cmyk[0]}/{sw.cmyk[1]}/{sw.cmyk[2]}/{sw.cmyk[3]}", size=9.8, stroke=sw.hex_color, width=1)
        return doc

    def export_col_gem(self, out_dir: str | Path) -> dict[str, Any]:
        dest = Path(out_dir).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        doc = self.to_artline_document()
        gem_path = dest / f"{self.palette_id}.col.gem"
        svg_path = dest / f"{self.palette_id}.col.svg"
        doc.export(gem_path, kind="gem")
        doc.export(svg_path, kind="svg")
        raw_gem = gem_path.read_bytes()
        return {
            "palette_id": self.palette_id,
            "gem_path": str(gem_path),
            "svg_path": str(svg_path),
            "gem_bytes": len(raw_gem),
            "valid_gem_header": raw_gem[:2] == b"\xff\xff",
            "swatch_count": len(self.swatches),
        }


STUDIO_PALETTES: tuple[ZoeVectorPalette, ...] = (
    ZoeVectorPalette(
        "zoe_studio",
        "Zoe Night Atelier (Default)",
        (
            PaletteSwatch("Zoe Ruby", "#f35670", (0, 65, 54, 5)),
            PaletteSwatch("Electric Cyan", "#5ce1e6", (60, 2, 0, 10)),
            PaletteSwatch("Artline Gold", "#f8cc30", (0, 18, 81, 3)),
            PaletteSwatch("Blossom Pink", "#ff85b3", (0, 48, 30, 0)),
            PaletteSwatch("Kloster Mint", "#52e5a8", (64, 0, 27, 10)),
            PaletteSwatch("GEM Violet", "#ac82ff", (33, 49, 0, 0)),
            PaletteSwatch("Cobalt VDI", "#4f8ef7", (68, 43, 0, 3)),
            PaletteSwatch("Parchment", "#f4ebd6", (0, 4, 12, 4)),
        ),
    ),
    ZoeVectorPalette(
        "gem_classic",
        "1985 Digital Research GEM/3 Classic",
        (
            PaletteSwatch("GEM Desktop Teal", "#008080", (100, 0, 0, 50)),
            PaletteSwatch("GEM Red", "#e62e2d", (0, 80, 80, 10)),
            PaletteSwatch("GEM Cyan", "#00cccc", (100, 0, 0, 20)),
            PaletteSwatch("GEM Yellow", "#f2d600", (0, 12, 100, 5)),
            PaletteSwatch("GEM Blue", "#1c57b8", (85, 53, 0, 28)),
            PaletteSwatch("GEM Magenta", "#c7349c", (0, 74, 22, 22)),
            PaletteSwatch("GEM Green", "#2aa146", (74, 0, 57, 37)),
            PaletteSwatch("Atari Paper", "#eef2f7", (4, 2, 0, 3)),
        ),
    ),
    ZoeVectorPalette(
        "artline_cmyk",
        "Artline 2.0 Print CMYK Swatches",
        (
            PaletteSwatch("Process Cyan", "#00aeef", (100, 0, 0, 0)),
            PaletteSwatch("Process Magenta", "#ec008c", (0, 100, 0, 0)),
            PaletteSwatch("Process Yellow", "#fff200", (0, 0, 100, 0)),
            PaletteSwatch("Process Key", "#231f20", (0, 0, 0, 100)),
            PaletteSwatch("Warm Red", "#f15a29", (0, 78, 95, 0)),
            PaletteSwatch("Royal Violet", "#662d91", (75, 100, 0, 0)),
            PaletteSwatch("Emerald Press", "#00a651", (90, 0, 95, 0)),
            PaletteSwatch("Proof Cream", "#fbf6ea", (0, 2, 7, 2)),
        ),
    ),
    ZoeVectorPalette(
        "botanical_neon",
        "Dorothy Botanical & Neurogarden",
        (
            PaletteSwatch("Orchid Glow", "#f0a3df", (0, 32, 7, 6)),
            PaletteSwatch("Chlorophyll", "#63f5b5", (60, 0, 26, 4)),
            PaletteSwatch("Amber Synapse", "#ffb84d", (0, 28, 70, 0)),
            PaletteSwatch("H3K27M Azure", "#38bdf8", (77, 24, 0, 3)),
            PaletteSwatch("Rose Petal", "#fb7185", (0, 55, 47, 2)),
            PaletteSwatch("Pollen Gold", "#fde047", (0, 11, 72, 1)),
            PaletteSwatch("Mycelium Lilac", "#c084fc", (25, 48, 0, 1)),
            PaletteSwatch("Night Soil", "#1e293b", (48, 30, 0, 77)),
        ),
    ),
)


# ---------------------------------------------------------------------------
# 6b. Read-Only 1990 CCPTK001 .TLS Toolbox Binary Inspector & 35-Font Poster
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TLSToolEntry:
    index: int
    name: str
    icon_offset: int
    icon_bytes_len: int
    icon_width: int = 0
    icon_height: int = 0
    icon_svg_path: str = ""


@dataclass(frozen=True)
class TLSToolbox:
    filename: str
    magic: str
    tool_count: int
    panel_width_hint: int
    tools: tuple[TLSToolEntry, ...]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "magic": self.magic,
            "tool_count": self.tool_count,
            "panel_width_hint": self.panel_width_hint,
            "tool_names": [t.name for t in self.tools],
            "tools": [
                {
                    "index": t.index,
                    "name": t.name,
                    "icon_width": t.icon_width,
                    "icon_height": t.icon_height,
                    "icon_svg_path": t.icon_svg_path,
                }
                for t in self.tools
            ],
        }


def _decode_tls_icon_svg_path(chunk: bytes) -> tuple[int, int, str]:
    """Decode a 32x28 1-bit monochrome Artline 2.0 .TLS icon bitmap at chunk[88:200] into compact SVG runs."""
    if len(chunk) < 200:
        return (0, 0, "")
    w, h = struct.unpack_from("<HH", chunk, 14)
    if (w, h) != (32, 28):
        return (0, 0, "")
    bmp = chunk[88:200]
    if len(bmp) < 112:
        return (0, 0, "")
    parts: list[str] = []
    for y in range(28):
        w0, w1 = struct.unpack_from("<HH", bmp, y * 4)
        row_bits = (w0 << 16) | w1
        x = 0
        while x < 32:
            if (row_bits >> (31 - x)) & 1:
                start_x = x
                while x < 32 and ((row_bits >> (31 - x)) & 1):
                    x += 1
                run = x - start_x
                parts.append(f"M{start_x},{y}h{run}v1h-{run}z")
            else:
                x += 1
    return (32, 28, "".join(parts))


def decode_tls_bytes(data: bytes, filename: str = "toolbox.tls") -> TLSToolbox:
    """Read-only clean-room inspector for 1990 Digital Research Artline 2.0 `CCPTK001\\0` `.TLS` files.

    Verified byte-exact (`13 + 17 * tool_count == first_icon_offset`) across all 8 `.tls` files
    (`artline.tls`, `align.tls`, `trace.tls`, `1_column.tls`, `4_column.tls`, `custom.tls`, `ega.tls`).
    """
    if len(data) < 13 or data[:9] != b"CCPTK001\x00":
        raise ValueError(f"Not a valid CCPTK001 .TLS toolbox binary: {filename}")
    ntools, width_hint = struct.unpack_from("<HH", data, 9)
    table_end = 13 + ntools * 17
    if table_end > len(data):
        raise ValueError(f"Truncated .TLS tool table in {filename}")

    raw_rows: list[tuple[str, int]] = []
    for i in range(ntools):
        rec = 13 + i * 17
        icon_off = struct.unpack_from("<I", data, rec)[0]
        label = data[rec + 4 : rec + 17].split(b"\x00", 1)[0].decode("ascii", "replace").strip()
        raw_rows.append((label or f"Tool_{i:02d}", icon_off))

    entries: list[TLSToolEntry] = []
    for i, (label, off) in enumerate(raw_rows):
        nxt = raw_rows[i + 1][1] if i + 1 < len(raw_rows) else len(data)
        blen = max(0, nxt - off)
        chunk = data[off : off + blen] if off <= len(data) else b""
        iw, ih, ipath = _decode_tls_icon_svg_path(chunk)
        entries.append(
            TLSToolEntry(
                index=i,
                name=label,
                icon_offset=off,
                icon_bytes_len=blen,
                icon_width=iw,
                icon_height=ih,
                icon_svg_path=ipath,
            )
        )

    return TLSToolbox(
        filename=filename,
        magic="CCPTK001",
        tool_count=ntools,
        panel_width_hint=width_hint,
        tools=tuple(entries),
    )


def decode_tls_file(path: str | Path) -> TLSToolbox:
    p = Path(path)
    return decode_tls_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_tls_bytes() -> bytes:
    """Build a clean-room synthetic `CCPTK001` `.TLS` buffer for portable headless CI tests."""
    names = ("Selector", "Bezier", "Rosette", "Align")
    table_end = 13 + len(names) * 17
    hdr = bytearray(b"CCPTK001\x00" + struct.pack("<HH", len(names), 71))
    payload = bytearray()
    for i, name in enumerate(names):
        off = table_end + len(payload)
        enc = name.encode("ascii")[:12]
        hdr.extend(struct.pack("<I", off) + enc + b"\x00" * (13 - len(enc)))
        payload.extend(bytes([i + 1]) * 32)
    return bytes(hdr + payload)


# ---------------------------------------------------------------------------
# 6c. Clean-Room .COL Palette Decoder & .GEM Metafile Inspector (via vdi.py)
# ---------------------------------------------------------------------------

def _rgb1000_to_hex(r1000: int, g1000: int, b1000: int) -> str:
    r = max(0, min(255, round(max(0, min(1000, r1000)) * 255 / 1000)))
    g = max(0, min(255, round(max(0, min(1000, g1000)) * 255 / 1000)))
    b = max(0, min(255, round(max(0, min(1000, b1000)) * 255 / 1000)))
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass(frozen=True)
class COLSwatch:
    index: int
    name: str
    rgb_1000: tuple[int, int, int]
    hex_color: str


@dataclass(frozen=True)
class COLPalette:
    filename: str
    version: int
    swatch_count: int
    swatches: tuple[COLSwatch, ...]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "version": self.version,
            "swatch_count": self.swatch_count,
            "swatches": [
                {
                    "index": s.index,
                    "name": s.name,
                    "rgb_1000": list(s.rgb_1000),
                    "hex_color": s.hex_color,
                }
                for s in self.swatches
            ],
        }

    def to_zoe_palette(self, max_swatches: int = 8) -> ZoeVectorPalette:
        picked = self.swatches[: max(1, max_swatches)]
        out_swatches: list[PaletteSwatch] = []
        for s in picked:
            r, g, b = (c / 1000.0 for c in s.rgb_1000)
            k = 1.0 - max(r, g, b)
            if k >= 0.999:
                cmyk = (0, 0, 0, 100)
            else:
                denom = 1.0 - k
                cmyk = (
                    round(((1.0 - r - k) / denom) * 100),
                    round(((1.0 - g - k) / denom) * 100),
                    round(((1.0 - b - k) / denom) * 100),
                    round(k * 100),
                )
            out_swatches.append(PaletteSwatch(s.name[:24], s.hex_color, cmyk))
        stem = Path(self.filename).stem or "decoded_col"
        return ZoeVectorPalette(stem, f"Decoded .COL · {self.filename}", tuple(out_swatches))


def decode_col_bytes(data: bytes, filename: str = "palette.col") -> COLPalette:
    """Decode a 0xFFFF GEM VDI `.COL` palette via `vdi.parse_metafile` (Escape 5/99/201|204 & vs_color 14)."""
    parsed = parse_metafile(data)
    swatches: list[COLSwatch] = []

    for rec in parsed["records"]:
        cmd = int(rec.get("command", -1))
        if cmd == -1:
            continue
        sub = int(rec.get("subcommand", 0))
        vals = rec.get("values", ())
        if cmd == 5 and sub == 99 and vals and vals[0] in (201, 204) and len(vals) >= 4:
            r1000 = max(0, min(1000, int(vals[1])))
            g1000 = max(0, min(1000, int(vals[2])))
            b1000 = max(0, min(1000, int(vals[3])))
            name_words = vals[4:]
            name = ""
            if name_words:
                raw_name = struct.pack(f"<{len(name_words)}h", *[int(w) for w in name_words])
                name = raw_name.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
            if not name:
                name = f"Color_{len(swatches):03d}"
            swatches.append(
                COLSwatch(
                    index=len(swatches),
                    name=name,
                    rgb_1000=(r1000, g1000, b1000),
                    hex_color=_rgb1000_to_hex(r1000, g1000, b1000),
                )
            )
        elif (cmd == 14 and len(vals) >= 4) or (cmd == 13 and len(vals) == 4):
            idx = int(vals[0])
            r1000 = max(0, min(1000, int(vals[1])))
            g1000 = max(0, min(1000, int(vals[2])))
            b1000 = max(0, min(1000, int(vals[3])))
            swatches.append(
                COLSwatch(
                    index=idx,
                    name=f"VDI_{idx:03d}",
                    rgb_1000=(r1000, g1000, b1000),
                    hex_color=_rgb1000_to_hex(r1000, g1000, b1000),
                )
            )

    return COLPalette(
        filename=filename,
        version=int(parsed["header"]["version"]),
        swatch_count=len(swatches),
        swatches=tuple(swatches),
    )


def decode_col_file(path: str | Path) -> COLPalette:
    p = Path(path)
    return decode_col_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_col_bytes() -> bytes:
    """Build a clean-room synthetic 0xFFFF `.COL` metafile from `STUDIO_PALETTES[0]`."""
    hdr = bytearray(struct.pack("<24h", -1, 24, 400, 2, 0, 0, 1000, 700, 2540, 1778, 0, 0, 1000, 700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    recs: list[bytes] = []
    for idx, sw in enumerate(STUDIO_PALETTES[0].swatches):
        hx = sw.hex_color.lstrip("#")
        r1000 = round(int(hx[0:2], 16) * 1000 / 255)
        g1000 = round(int(hx[2:4], 16) * 1000 / 255)
        b1000 = round(int(hx[4:6], 16) * 1000 / 255)
        raw_name = sw.name.encode("ascii", "replace") + b"\x00"
        if len(raw_name) % 2 == 1:
            raw_name += b"\x00"
        name_words = struct.unpack(f"<{len(raw_name) // 2}h", raw_name)
        recs.append(_record(5, 99, values=[201, r1000, g1000, b1000, *name_words]))
        recs.append(_record(14, values=[16 + idx, r1000, g1000, b1000]))
    return bytes(hdr) + b"".join(recs) + struct.pack("<h", -1)


def _vdi_idx_to_hex(idx: int, palette: dict[int, str]) -> str:
    if idx in palette:
        val = palette[idx]
        if val.startswith("#"):
            return val
        named = {
            "white": "#ffffff",
            "black": "#000000",
            "red": "#e62e2d",
            "green": "#2aa146",
            "blue": "#1c57b8",
            "cyan": "#00cccc",
            "yellow": "#f2d600",
            "magenta": "#c7349c",
        }
        return named.get(val, "#5ce1e6")
    return "#5ce1e6"


def inspect_gem_bytes(data: bytes, filename: str = "drawing.gem") -> dict[str, Any]:
    """Clean-room `.GEM` metafile inspector built directly on `vdi.parse_metafile` + `vdi.opcode_inventory`.

    Handles real 1988-1990 `.GEM` files safely without failing on <3-pt `v_fillarea` or Artline 2.0 extensions.
    """
    parsed = parse_metafile(data)
    inv = opcode_inventory(data)
    palette: dict[int, str] = {int(k): str(v) for k, v in INDEX_COLOR.items()}
    fill_color = "#5ce1e6"
    line_color = "#f8cc30"
    fill_interior = 1

    shapes: list[dict[str, Any]] = []
    used_colors: set[str] = set()
    counts = {"fillarea": 0, "pline": 0, "gdp": 0, "gtext": 0, "skipped_degenerate": 0}

    for rec in parsed["records"]:
        cmd = int(rec.get("command", -1))
        if cmd == -1:
            continue
        sub = int(rec.get("subcommand", 0))
        vals = rec.get("values", ())
        flat = rec.get("coordinates", ())
        pts = [(float(flat[i]), float(flat[i + 1])) for i in range(0, len(flat), 2)]

        if (cmd == 14 and len(vals) >= 4) or (cmd == 13 and len(vals) == 4):
            idx = int(vals[0])
            hx = _rgb1000_to_hex(int(vals[1]), int(vals[2]), int(vals[3]))
            palette[idx] = hx
            used_colors.add(hx)
        elif cmd == 5 and sub == 99 and vals and vals[0] in (201, 204) and len(vals) >= 4:
            hx = _rgb1000_to_hex(int(vals[1]), int(vals[2]), int(vals[3]))
            fill_color = hx
            used_colors.add(hx)
        elif cmd == 17 and vals:
            line_color = _vdi_idx_to_hex(int(vals[0]), palette)
            used_colors.add(line_color)
        elif cmd == 23 and vals:
            fill_interior = int(vals[0])
        elif cmd == 25 and vals:
            fill_color = _vdi_idx_to_hex(int(vals[0]), palette)
            used_colors.add(fill_color)
        elif cmd == 9:
            if len(pts) < 3:
                counts["skipped_degenerate"] += 1
                continue
            counts["fillarea"] += 1
            fc = "none" if fill_interior == 0 else fill_color
            shapes.append({"pts": pts, "closed": True, "fill": fc, "stroke": line_color})
        elif cmd == 6:
            if len(pts) < 2:
                counts["skipped_degenerate"] += 1
                continue
            counts["pline"] += 1
            shapes.append({"pts": pts, "closed": False, "fill": "none", "stroke": line_color})
        elif cmd == 11:
            counts["gdp"] += 1
            if sub in (1, 8, 9) and len(pts) >= 2:
                x1, y1 = pts[0]
                x2, y2 = pts[1]
                poly = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
                shapes.append({"pts": poly, "closed": True, "fill": fill_color, "stroke": line_color})
            elif sub == 4 and len(pts) >= 3:
                cx, cy = pts[0]
                rad = max(1.0, math.hypot(pts[2][0], pts[2][1]) or abs(pts[2][0]))
                poly = [(cx + rad * math.cos(2 * math.pi * k / 16), cy + rad * math.sin(2 * math.pi * k / 16)) for k in range(16)]
                shapes.append({"pts": poly, "closed": True, "fill": fill_color, "stroke": line_color})
            elif sub == 5 and len(pts) >= 2:
                cx, cy = pts[0]
                rx, ry = max(1.0, abs(pts[1][0])), max(1.0, abs(pts[1][1]))
                poly = [(cx + rx * math.cos(2 * math.pi * k / 16), cy + ry * math.sin(2 * math.pi * k / 16)) for k in range(16)]
                shapes.append({"pts": poly, "closed": True, "fill": fill_color, "stroke": line_color})
        elif cmd == 8:
            counts["gtext"] += 1

    all_pts = [p for s in shapes for p in s["pts"]]
    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        bbox = [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]
    else:
        hdr_b = parsed["header"].get("bounds", (0, 0, 100, 100))
        bbox = [float(hdr_b[0]), float(hdr_b[1]), float(hdr_b[2]), float(hdr_b[3])]

    min_x, min_y, max_x, max_y = bbox
    span = max(1e-6, max(max_x - min_x, max_y - min_y))
    scale = 84.0 / span
    ox = 8.0 + (84.0 - (max_x - min_x) * scale) * 0.5
    oy = 8.0 + (84.0 - (max_y - min_y) * scale) * 0.5

    preview_paths: list[dict[str, str]] = []
    svg_elems: list[str] = []
    for sh in shapes[:400]:
        cmds: list[str] = []
        for idx, (px, py) in enumerate(sh["pts"]):
            sx = ox + (px - min_x) * scale
            sy = oy + (py - min_y) * scale
            cmds.append(f"{'M' if idx == 0 else 'L'}{sx:.1f},{sy:.1f}")
        if sh["closed"]:
            cmds.append("Z")
        d = " ".join(cmds)
        fill_attr = sh["fill"] if sh["fill"] != "none" else "none"
        stroke_attr = sh["stroke"] if sh["stroke"] != "none" else "#5ce1e6"
        preview_paths.append({"d": d, "fill": fill_attr, "stroke": stroke_attr})
        fill_svg = f"{fill_attr}55" if fill_attr.startswith("#") and len(fill_attr) == 7 else fill_attr
        svg_elems.append(
            f'<path d="{html_lib.escape(d, quote=True)}" fill="{html_lib.escape(fill_svg, quote=True)}" '
            f'stroke="{html_lib.escape(stroke_attr, quote=True)}" stroke-width="1.4" fill-rule="evenodd" />'
        )

    preview_svg = (
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="100" height="100" fill="#090d1a" />'
        + "".join(svg_elems)
        + "</svg>"
    )

    return {
        "contract": ARTLINE_FORGE_CONTRACT,
        "filename": filename,
        "header": {
            k: (list(v) if isinstance(v, tuple) else v)
            for k, v in dict(parsed["header"]).items()
        },
        "record_count": len(parsed["records"]),
        "opcode_inventory": inv,
        "primitive_counts": counts,
        "colors": sorted(used_colors),
        "bbox": bbox,
        "preview_paths": preview_paths,
        "preview_svg": preview_svg,
        "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
    }


def inspect_gem_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return inspect_gem_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_gem_bytes() -> bytes:
    """Build a clean-room synthetic 0xFFFF `.GEM` metafile for portable headless CI inspection."""
    b = VdiMetafileBuilder(width=600, height=400)
    b.set_line(color="#5ce1e6", width=2)
    b.set_fill(color="#141a2e", perimeter=True)
    b.bar(20, 20, 580, 380)
    b.set_line(color="#f8cc30", width=2)
    b.set_fill(color="#f35670", perimeter=True)
    b.fillarea([(300, 60), (480, 200), (300, 340), (120, 200)])
    return b.build()


def render_af4_catalog_poster_png(
    fonts: Sequence[AF4Font],
    out_png: str | Path,
    *,
    sample_text: str = "ZoeNick1990",
) -> dict[str, Any]:
    """Render a multi-family dark-studio typographic specimen poster across decoded `.AF4` fonts."""
    items = list(fonts)
    cols = 2 if len(items) > 6 else 1
    rows = max(1, math.ceil(len(items) / cols))
    row_h, col_w = 56, 620
    pad_x, pad_y, hdr_h = 22, 14, 66
    img_w = pad_x * 2 + cols * col_w
    img_h = hdr_h + pad_y * 2 + rows * row_h

    img = Image.new("RGB", (img_w, img_h), (10, 13, 24))
    draw = ImageDraw.Draw(img)
    f_title = _pil_font(17)
    f_sub = _pil_font(11)
    f_lbl = _pil_font(11)
    f_meta = _pil_font(9)

    draw.rectangle([0, 0, img_w, 6], fill=(92, 225, 230))
    draw.text((22, 15), f"Clean-Room Artline 2.0 Complete .AF4 Outline Font Atlas ({len(items)} Decoded Typefaces)", fill=(248, 204, 48), font=f_title)
    draw.text((22, 40), "Kerning-aware 1989-1990 CCP Bezier vector decoder · Pure Python + PIL (0 Cairo · 0 GPU · 0 Cloud Tokens)", fill=(156, 172, 206), font=f_sub)

    palette = [(92, 225, 230), (248, 204, 48), (255, 133, 179), (82, 229, 168), (172, 130, 255)]
    for idx, font in enumerate(items):
        c, r = divmod(idx, rows)
        x0 = pad_x + c * col_w + 4
        y0 = hdr_h + pad_y + r * row_h + 3
        x1 = x0 + col_w - 10
        y1 = y0 + row_h - 6
        accent = palette[idx % len(palette)]
        fill_c: tuple[int, int, int] = (int(14 + accent[0] * 0.16), int(14 + accent[1] * 0.16), int(14 + accent[2] * 0.16))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=(18, 24, 42), outline=(44, 60, 98), width=1)
        draw.text((x0 + 10, y0 + 7), f"{font.display_name[:22]}", fill=accent, font=f_lbl)
        draw.text((x0 + 10, y0 + 25), f"{font.filename} · ID {font.font_id} · {len(font.glyphs_by_char)}g", fill=(156, 172, 206), font=f_meta)

        # Render live decoded cubic Bezier glyphs for sample_text (or first available glyphs)
        codes = [ord(ch) for ch in sample_text if ord(ch) in font.glyphs_by_char]
        if len(codes) < 4:
            codes = sorted(font.glyphs_by_char.keys())[:10]
        gx = x0 + 206
        for ch in codes[:11]:
            g = font.glyphs_by_char[ch]
            _draw_contours_in_cell(draw, g.contours, (gx, y0 + 7, gx + 31, y1 - 7), flip_y=True, stroke=accent, fill_alpha_rgb=fill_c)
            gx += 36

    target = Path(out_png)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target), format="PNG")
    return {"path": str(target), "bytes": target.stat().st_size, "rendered_fonts": len(items), "size": [img_w, img_h]}


# ---------------------------------------------------------------------------
# 7. Thread-Safe Memoization (F5), Typesetter (F6), Exports & /forge UI (F8)
# ---------------------------------------------------------------------------

_FORGE_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True)
class _ForgeArchiveBundle:
    archive_root: str
    source_mode: str
    fonts: tuple[AF4Font, ...]
    fonts_by_key: Mapping[str, AF4Font]
    syf_libraries: tuple[SYFLibrary, ...]
    tls_toolboxes: tuple[TLSToolbox, ...]
    col_palettes: tuple[COLPalette, ...]
    gem_inspections: tuple[dict[str, Any], ...]
    vectors_json: str


_FORGE_ARCHIVE_CACHE: dict[tuple[Any, ...], _ForgeArchiveBundle] = {}


def clear_forge_cache() -> None:
    """Clear the memoized archive bundle cache (used by tests & hot reload)."""
    with _FORGE_CACHE_LOCK:
        _FORGE_ARCHIVE_CACHE.clear()


def _resolve_archive_root(archive_root: Path | None = None) -> Path:
    raw = DEFAULT_EXTRACTED_ROOT if archive_root is None else Path(archive_root)
    return raw.expanduser().resolve()


def _dir_fingerprint(d: Path, exts: tuple[str, ...]) -> tuple[Any, ...]:
    if not d.is_dir():
        return ("missing",)
    try:
        d_mtime = d.stat().st_mtime_ns
        entries: list[tuple[str, int, int]] = []
        for entry in d.iterdir():
            if entry.suffix.lower() in exts and entry.is_file():
                st = entry.stat()
                entries.append((entry.name, st.st_mtime_ns, st.st_size))
        entries.sort()
        return ("dir", d_mtime, tuple(entries))
    except OSError:
        return ("error",)


def _archive_fingerprint(root: Path) -> tuple[Any, ...]:
    root_exists = root.is_dir()
    root_mtime = root.stat().st_mtime_ns if root_exists else None
    fonts_dir = root / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts"
    syf_dir = root / "symbol_pack_1989"
    clrtl_dir = root / "artline_2.0_dri_unpacked/clrtl/clrtl"
    art_dir = root / "artline_2.0_dri_unpacked/art/art"
    return (
        str(root),
        root_exists,
        root_mtime,
        _dir_fingerprint(fonts_dir, (".af4",)),
        _dir_fingerprint(syf_dir, (".syf", ".gem")),
        _dir_fingerprint(clrtl_dir, (".tls", ".col")),
        _dir_fingerprint(art_dir, (".gem",)),
    )


def _glyph_em_svg_path(glyph: AF4Glyph) -> str:
    """Encode a glyph into a shared 0..100 EM coordinate box (baseline y=90.0) for multi-glyph JS typesetting."""
    if glyph.bezier_segments:
        parts: list[str] = []
        for sub in glyph.bezier_segments:
            if len(sub) < 2:
                continue
            for seg in sub:
                cmd = seg[0]
                if cmd in ("M", "L"):
                    px, py = seg[1]
                    parts.append(f"{cmd}{px / 10.0:.1f},{(900.0 - py) / 10.0:.1f}")
                elif cmd == "C":
                    p1, p2, p3 = seg[1], seg[2], seg[3]
                    parts.append(
                        f"C{p1[0] / 10.0:.1f},{(900.0 - p1[1]) / 10.0:.1f} "
                        f"{p2[0] / 10.0:.1f},{(900.0 - p2[1]) / 10.0:.1f} "
                        f"{p3[0] / 10.0:.1f},{(900.0 - p3[1]) / 10.0:.1f}"
                    )
            parts.append("Z")
        return " ".join(parts)

    parts = []
    for c in glyph.contours:
        if len(c) < 2:
            continue
        for idx, (px, py) in enumerate(c):
            parts.append(f"{'M' if idx == 0 else 'L'}{px / 10.0:.1f},{(900.0 - py) / 10.0:.1f}")
        parts.append("Z")
    return " ".join(parts)


def _build_af4_font_preview_entry(font: AF4Font) -> dict[str, Any]:
    preview_codes = [ch for ch in sorted(font.glyphs_by_char.keys()) if 33 <= ch <= 126 or 128 <= ch <= 255]
    if not preview_codes:
        preview_codes = sorted(font.glyphs_by_char.keys())[:96]
    glyph_map: dict[str, dict[str, Any]] = {}
    for ch in preview_codes:
        g = font.glyphs_by_char[ch]
        glyph_map[str(ch)] = {
            "adv": g.advance_width,
            "em": _glyph_em_svg_path(g),
        }
    kern_map: dict[str, int] = {f"{lc},{rc}": d for lc, rc, d in font.kerning_pairs}
    return {
        "filename": font.filename,
        "stem": Path(font.filename).stem,
        "display_name": font.display_name,
        "font_id": font.font_id,
        "space_width": font.space_width,
        "decoded_chars": len(font.glyphs_by_char),
        "kerning_pairs_count": len(font.kerning_pairs),
        "kerning": kern_map,
        "glyphs": glyph_map,
    }


def _load_archive_bundle(archive_root: Path | None = None) -> _ForgeArchiveBundle:
    root = _resolve_archive_root(archive_root)
    fp = _archive_fingerprint(root)
    with _FORGE_CACHE_LOCK:
        cached = _FORGE_ARCHIVE_CACHE.get(fp)
        if cached is not None:
            return cached

    fonts_dir = root / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts"
    syf_dir = root / "symbol_pack_1989"
    clrtl_dir = root / "artline_2.0_dri_unpacked/clrtl/clrtl"
    art_dir = root / "artline_2.0_dri_unpacked/art/art"

    source_mode = "authentic_local_1990_archive"
    fonts_list: list[AF4Font] = []
    if fonts_dir.is_dir():
        af4_paths = sorted((p for p in fonts_dir.iterdir() if p.is_file() and p.suffix.lower() == ".af4"), key=lambda p: p.name.lower())
        for fp_path in af4_paths:
            fonts_list.append(decode_af4_font(fp_path))
    if not fonts_list:
        source_mode = "portable_clean_room_synth"
        fonts_list.append(decode_af4_bytes(build_synthetic_af4_bytes(), "zoe_synth.af4"))

    fonts_by_key: dict[str, AF4Font] = {}
    for f in fonts_list:
        for alias in (f.filename, Path(f.filename).stem, f.internal_filename, Path(f.internal_filename).stem, f.display_name):
            norm = alias.strip().lower()
            if norm and norm not in fonts_by_key:
                fonts_by_key[norm] = f

    syf_list: list[SYFLibrary] = []
    if syf_dir.is_dir():
        syf_paths = sorted((p for p in syf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".syf"), key=lambda p: p.name.upper())
        for sp in syf_paths:
            syf_list.append(decode_syf_library(sp))
    if not syf_list:
        syf_list.append(decode_syf_bytes(build_synthetic_syf_bytes(), "zoe_synth.syf"))

    tls_list: list[TLSToolbox] = []
    if clrtl_dir.is_dir():
        tls_paths = sorted((p for p in clrtl_dir.iterdir() if p.is_file() and p.suffix.lower() == ".tls"), key=lambda p: p.name.lower())
        for tp in tls_paths:
            tls_list.append(decode_tls_file(tp))
    if not tls_list:
        tls_list.append(decode_tls_bytes(build_synthetic_tls_bytes(), "synth.tls"))

    col_list: list[COLPalette] = []
    if clrtl_dir.is_dir():
        col_paths = sorted((p for p in clrtl_dir.iterdir() if p.is_file() and p.suffix.lower() == ".col"), key=lambda p: p.name.lower())
        for cp in col_paths:
            col_list.append(decode_col_file(cp))
    if not col_list:
        col_list.append(decode_col_bytes(build_synthetic_col_bytes(), "zoe_synth.col"))

    gem_list: list[dict[str, Any]] = []
    gem_candidates: list[Path] = []
    if syf_dir.is_dir():
        gem_candidates.extend(sorted((p for p in syf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".gem"), key=lambda p: p.name.upper()))
    if art_dir.is_dir():
        gem_candidates.extend(sorted((p for p in art_dir.iterdir() if p.is_file() and p.suffix.lower() == ".gem"), key=lambda p: p.name.lower()))
    for gp in gem_candidates:
        gem_list.append(inspect_gem_file(gp))
    if not gem_list:
        gem_list.append(inspect_gem_bytes(build_synthetic_gem_bytes(), "zoe_synth.gem"))

    # Build UI vectors payload
    wombat_items: list[dict[str, Any]] = []
    symbol_items: list[dict[str, Any]] = []
    chancery_items: list[dict[str, Any]] = []

    wf = fonts_by_key.get("wombat.af4") or fonts_list[0]
    if wf.filename == "wombat.af4":
        featured = [90, 111, 101, 78, 73, 51, 53, 42, 44, 46, 95, 117, 118, 33, 40, 41, 57, 70, 72, 83, 87, 89, 108, 115, 164, 168, 169, 170, 171, 172, 212, 233]
        for ch in featured:
            if ch in wf.glyphs_by_char:
                g = wf.glyphs_by_char[ch]
                wombat_items.append({"code": ch, "key": chr(ch) if 33 <= ch < 127 else f"#{ch}", "pts": g.point_count, "d": g.bezier_svg_path or g.svg_path})
    else:
        for ch, g in sorted(wf.glyphs_by_char.items()):
            wombat_items.append({"code": ch, "key": chr(ch), "pts": g.point_count, "d": g.bezier_svg_path or g.svg_path})

    sf = fonts_by_key.get("symbol.af4")
    if sf is not None:
        for ch in [68, 70, 71, 83, 87, 89, 90, 97, 98, 100, 101, 102, 165, 177, 181, 182, 185, 186, 214]:
            if ch in sf.glyphs_by_char:
                g = sf.glyphs_by_char[ch]
                symbol_items.append({"code": ch, "key": chr(ch) if ch < 127 else f"#{ch}", "pts": g.point_count, "d": g.bezier_svg_path or g.svg_path})

    cf = fonts_by_key.get("z_chance.af4")
    if cf is not None:
        for ch in [ord(c) for c in "ZoeNickArtlineGEM2026"]:
            if ch in cf.glyphs_by_char and not any(x["code"] == ch for x in chancery_items):
                g = cf.glyphs_by_char[ch]
                chancery_items.append({"code": ch, "key": chr(ch), "pts": g.point_count, "d": g.bezier_svg_path or g.svg_path})

    syf_packs: dict[str, list[dict[str, Any]]] = {}
    for lib in syf_list:
        pack_key = "SYNTH" if lib.filename == "zoe_synth.syf" else Path(lib.filename).stem.upper()
        syf_packs[pack_key] = [
            {
                "pack": pack_key,
                "name": sym.name,
                "pts": sym.point_count,
                "d": sym.svg_path,
            }
            for sym in lib.symbols
        ]
    total_syf = sum(len(v) for v in syf_packs.values())

    col_ui_list = [
        {
            "filename": pal.filename,
            "version": pal.version,
            "swatch_count": pal.swatch_count,
            "swatches": [
                {"index": s.index, "name": s.name, "hex_color": s.hex_color, "rgb_1000": list(s.rgb_1000)}
                for s in pal.swatches[:48]
            ],
        }
        for pal in col_list
    ]

    gem_ui_list = [
        {
            "filename": g["filename"],
            "record_count": g["record_count"],
            "primitive_counts": dict(g["primitive_counts"]),
            "bbox": list(g["bbox"]),
            "colors": list(g["colors"][:16]),
            "preview_svg": g["preview_svg"],
            "d": (g["preview_paths"][0]["d"] if g["preview_paths"] else ""),
        }
        for g in gem_list
    ]

    vectors_template: dict[str, Any] = {
        "source_mode": source_mode,
        "archive_root": str(root),
        "wombat_glyphs": wombat_items,
        "symbol_glyphs": symbol_items,
        "chancery_glyphs": chancery_items,
        "syf_packs": syf_packs,
        "syf_total": total_syf,
        "tls_1990": [tb.summary_dict() for tb in tls_list],
        "af4_catalog": [f.summary_dict() for f in fonts_list],
        "af4_fonts": [_build_af4_font_preview_entry(f) for f in fonts_list],
        "col_palettes": col_ui_list,
        "gem_samples": gem_ui_list,
    }

    bundle = _ForgeArchiveBundle(
        archive_root=str(root),
        source_mode=source_mode,
        fonts=tuple(fonts_list),
        fonts_by_key=MappingProxyType(fonts_by_key),
        syf_libraries=tuple(syf_list),
        tls_toolboxes=tuple(tls_list),
        col_palettes=tuple(col_list),
        gem_inspections=tuple(gem_list),
        vectors_json=json.dumps(vectors_template, ensure_ascii=False),
    )
    with _FORGE_CACHE_LOCK:
        _FORGE_ARCHIVE_CACHE[fp] = bundle
    return bundle


def _collect_live_forge_vectors(archive_root: Path | None = None) -> dict[str, Any]:
    """Return a fresh copy of memoized decoded .AF4/.SYF/.TLS/.COL/.GEM Forge vectors."""
    bundle = _load_archive_bundle(archive_root)
    return dict(json.loads(bundle.vectors_json))


def _resolve_af4_font(font_name: str, bundle: _ForgeArchiveBundle) -> AF4Font:
    key = (font_name or "").strip().lower()
    if not key:
        raise KeyError("Font name must not be empty")
    found = bundle.fonts_by_key.get(key)
    if found is None and not key.endswith(".af4"):
        found = bundle.fonts_by_key.get(f"{key}.af4")
    if found is None:
        raise KeyError(f"Unknown .AF4 font: {font_name!r}")
    return found


def get_forge_catalog(archive_root: Path | None = None) -> dict[str, Any]:
    """Return memoized Forge catalog across all .AF4 fonts, .SYF packs, .TLS toolboxes, .COL palettes & .GEM samples."""
    bundle = _load_archive_bundle(archive_root)
    return {
        "contract": ARTLINE_FORGE_CONTRACT,
        "source_mode": bundle.source_mode,
        "archive_root": bundle.archive_root,
        "font_count": len(bundle.fonts),
        "fonts": [f.summary_dict() for f in bundle.fonts],
        "syf_packs": [lib.summary_dict() for lib in bundle.syf_libraries],
        "syf_total": sum(len(lib.symbols) for lib in bundle.syf_libraries),
        "tls_toolboxes": [tb.summary_dict() for tb in bundle.tls_toolboxes],
        "col_palettes": [pal.summary_dict() for pal in bundle.col_palettes],
        "studio_palettes": [asdict(p) for p in STUDIO_PALETTES],
        "studio_toolboxes": [asdict(tb) for tb in STUDIO_TOOLBOXES],
        "gem_samples": [copy.deepcopy(g) for g in bundle.gem_inspections],
        "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
        "cloud_tokens_used": 0,
    }


def get_af4_font_payload(font_name: str, archive_root: Path | None = None) -> dict[str, Any]:
    """Return decoded glyph SVG/Bezier paths, metrics & kerning pairs for a named `.AF4` font."""
    bundle = _load_archive_bundle(archive_root)
    font = _resolve_af4_font(font_name, bundle)
    return {
        "contract": ARTLINE_FORGE_CONTRACT,
        "source_mode": bundle.source_mode,
        "summary": font.summary_dict(),
        "metrics": {
            "font_bbox": list(font.font_bbox),
            "space_width": font.space_width,
            "first_char": font.first_char,
            "last_char": font.last_char,
            "glyph_count": font.glyph_count,
            "decoded_chars": len(font.glyphs_by_char),
            "char_advances": dict(font.char_advances),
        },
        "glyphs": [
            {
                "code": ch,
                "key": chr(ch) if 33 <= ch < 127 else f"#{ch}",
                "advance_width": g.advance_width,
                "bbox": list(g.bbox),
                "point_count": g.point_count,
                "svg_path": g.svg_path,
                "bezier_svg_path": g.bezier_svg_path,
            }
            for ch, g in sorted(font.glyphs_by_char.items())
        ],
        "kerning_pairs": [
            {
                "left_code": lc,
                "right_code": rc,
                "left": chr(lc) if 32 <= lc < 127 else f"#{lc}",
                "right": chr(rc) if 32 <= rc < 127 else f"#{rc}",
                "delta": delta,
            }
            for lc, rc, delta in font.kerning_pairs
        ],
        "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
    }


def typeset_af4_text_layout(
    font_name: str,
    text: str,
    archive_root: Path | None = None,
    *,
    use_kerning: bool = True,
    letter_spacing: float = 0.0,
) -> dict[str, Any]:
    """Lay out text string in 1000-EM font units with advance_width, space_width, and <hBB kerning."""
    bundle = _load_archive_bundle(archive_root)
    font = _resolve_af4_font(font_name, bundle)
    cursor_x = 0.0
    cursor_y = 0.0
    line_height = max(900.0, float(font.font_bbox[3] - font.font_bbox[1]) * 1.15)
    max_advance = 0.0
    prev_ch: int | None = None
    prev_char_str: str | None = None
    placed: list[dict[str, Any]] = []
    kerning_events: list[dict[str, Any]] = []
    all_x: list[float] = []
    all_y: list[float] = []

    for idx, ch_str in enumerate(text):
        if ch_str == "\n":
            max_advance = max(max_advance, cursor_x)
            cursor_x = 0.0
            cursor_y -= line_height
            prev_ch = None
            prev_char_str = None
            continue
        ch = font.resolve_char_code(ch_str)
        if use_kerning and prev_ch is not None:
            k_delta = font.kerning_delta(prev_ch, ch)
            if k_delta != 0:
                cursor_x += float(k_delta)
                kerning_events.append(
                    {
                        "index": idx,
                        "left": prev_char_str if prev_char_str is not None else chr(prev_ch),
                        "right": ch_str,
                        "delta": k_delta,
                    }
                )
        if ch == 32:
            adv = float(font.char_advances.get(32, font.space_width))
            cursor_x += adv + letter_spacing
            prev_ch = ch
            prev_char_str = ch_str
            continue

        glyph = font.glyphs_by_char.get(ch)
        if glyph is None:
            cursor_x += float(font.char_advances.get(ch, font.space_width)) + letter_spacing
            prev_ch = ch
            prev_char_str = ch_str
            continue

        placed_contours: list[list[tuple[float, float]]] = []
        for c in glyph.contours:
            pts = [(px + cursor_x, py + cursor_y) for px, py in c]
            placed_contours.append(pts)
            for px, py in pts:
                all_x.append(px)
                all_y.append(py)

        placed_segments: list[list[tuple[Any, ...]]] = []
        for sub in glyph.bezier_segments:
            new_sub: list[tuple[Any, ...]] = []
            for seg in sub:
                cmd = seg[0]
                if cmd in ("M", "L"):
                    new_sub.append((cmd, (seg[1][0] + cursor_x, seg[1][1] + cursor_y)))
                elif cmd == "C":
                    new_sub.append(
                        (
                            "C",
                            (seg[1][0] + cursor_x, seg[1][1] + cursor_y),
                            (seg[2][0] + cursor_x, seg[2][1] + cursor_y),
                            (seg[3][0] + cursor_x, seg[3][1] + cursor_y),
                        )
                    )
            if len(new_sub) >= 2:
                placed_segments.append(new_sub)

        adv = float(glyph.advance_width if glyph.advance_width > 0 else font.char_advances.get(ch, font.space_width))
        placed.append(
            {
                "char": ch_str,
                "code": ch,
                "x_offset": cursor_x,
                "y_offset": cursor_y,
                "advance_width": adv,
                "contours": placed_contours,
                "bezier_segments": placed_segments,
            }
        )
        cursor_x += adv + letter_spacing
        prev_ch = ch
        prev_char_str = ch_str

    max_advance = max(max_advance, cursor_x)
    bounds = (
        [min(all_x), min(all_y), max(all_x), max(all_y)]
        if all_x and all_y
        else [0.0, 0.0, max(100.0, max_advance), 700.0]
    )
    return {
        "contract": ARTLINE_FORGE_CONTRACT,
        "font": font.summary_dict(),
        "text": text,
        "use_kerning": use_kerning,
        "letter_spacing": letter_spacing,
        "total_advance": round(max_advance, 2),
        "kerning_events": kerning_events,
        "kerning_applied_count": len(kerning_events),
        "glyph_count_placed": len(placed),
        "bounds": bounds,
        "placed": placed,
    }


def typeset_af4_text_svg(
    font_name: str,
    text: str,
    archive_root: Path | None = None,
    *,
    font_size: float = 72.0,
    fill: str = "#5ce1e6",
    stroke: str = "#f8cc30",
    stroke_width: float = 1.6,
    background: str | None = "#090d1a",
    use_kerning: bool = True,
    letter_spacing: float = 0.0,
    use_bezier: bool = True,
    pad: float = 24.0,
) -> str:
    """Render clean-room kerning-aware `.AF4` typeset SVG with `fill-rule=\"evenodd\"` and Bezier `C` paths."""
    layout = typeset_af4_text_layout(
        font_name,
        text,
        archive_root,
        use_kerning=use_kerning,
        letter_spacing=letter_spacing,
    )
    min_x, min_y, max_x, max_y = layout["bounds"]
    scale = max(1e-3, font_size / 1000.0)
    svg_w = max(120.0, (max_x - min_x) * scale + 2.0 * pad)
    svg_h = max(80.0, (max_y - min_y) * scale + 2.0 * pad)

    def _to_svg(pt: tuple[float, float]) -> tuple[float, float]:
        return (pad + (pt[0] - min_x) * scale, pad + (max_y - pt[1]) * scale)

    path_elems: list[str] = []
    for item in layout["placed"]:
        parts: list[str] = []
        if use_bezier and item["bezier_segments"]:
            for sub in item["bezier_segments"]:
                for seg in sub:
                    cmd = seg[0]
                    if cmd in ("M", "L"):
                        sx, sy = _to_svg(seg[1])
                        parts.append(f"{cmd}{sx:.2f},{sy:.2f}")
                    elif cmd == "C":
                        c1x, c1y = _to_svg(seg[1])
                        c2x, c2y = _to_svg(seg[2])
                        p3x, p3y = _to_svg(seg[3])
                        parts.append(f"C{c1x:.2f},{c1y:.2f} {c2x:.2f},{c2y:.2f} {p3x:.2f},{p3y:.2f}")
                parts.append("Z")
        else:
            for contour in item["contours"]:
                for idx, pt in enumerate(contour):
                    sx, sy = _to_svg(pt)
                    parts.append(f"{'M' if idx == 0 else 'L'}{sx:.2f},{sy:.2f}")
                parts.append("Z")
        if parts:
            d_str = " ".join(parts)
            path_elems.append(
                f'<path d="{html_lib.escape(d_str, quote=True)}" '
                f'fill="{html_lib.escape(fill, quote=True)}" '
                f'stroke="{html_lib.escape(stroke, quote=True)}" '
                f'stroke-width="{stroke_width:.2f}" fill-rule="evenodd" />'
            )

    bg_rect = (
        f'<rect width="{svg_w:.1f}" height="{svg_h:.1f}" fill="{html_lib.escape(background, quote=True)}" />'
        if background
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {svg_w:.1f} {svg_h:.1f}" '
        f'width="{svg_w:.0f}" height="{svg_h:.0f}" '
        f'data-font="{html_lib.escape(str(layout["font"]["filename"]), quote=True)}" '
        f'data-kerning-applied="{layout["kerning_applied_count"]}" '
        f'data-total-advance="{layout["total_advance"]:.1f}">'
        f"{bg_rect}{''.join(path_elems)}</svg>"
    )


def render_af4_typeset_png(
    font_name: str,
    text: str,
    out_png: str | Path,
    archive_root: Path | None = None,
    *,
    font_size: float = 96.0,
    fill: tuple[int, int, int] = (24, 52, 74),
    stroke: tuple[int, int, int] = (92, 225, 230),
    background: tuple[int, int, int] = (10, 13, 24),
    use_kerning: bool = True,
    letter_spacing: float = 0.0,
    pad: float = 28.0,
) -> dict[str, Any]:
    """Render kerning-aware `.AF4` typeset string to a crisp dark-studio PIL PNG."""
    layout = typeset_af4_text_layout(
        font_name,
        text,
        archive_root,
        use_kerning=use_kerning,
        letter_spacing=letter_spacing,
    )
    min_x, min_y, max_x, max_y = layout["bounds"]
    scale = max(1e-3, font_size / 1000.0)
    img_w = max(180, int(math.ceil((max_x - min_x) * scale + 2.0 * pad)))
    img_h = max(110, int(math.ceil((max_y - min_y) * scale + 2.0 * pad)))

    img = Image.new("RGB", (img_w, img_h), background)
    draw = ImageDraw.Draw(img)
    for item in layout["placed"]:
        for idx, contour in enumerate(item["contours"]):
            if len(contour) < 2:
                continue
            mapped = [(pad + (px - min_x) * scale, pad + (max_y - py) * scale) for px, py in contour]
            if idx == 0 and len(mapped) >= 3:
                draw.polygon(mapped, fill=fill)
            draw.line(mapped, fill=stroke, width=2)

    target = Path(out_png)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target), format="PNG")
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "size": [img_w, img_h],
        "total_advance": layout["total_advance"],
        "kerning_applied_count": layout["kerning_applied_count"],
        "glyph_count_placed": layout["glyph_count_placed"],
        "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
    }


def _cap_polygon_points(
    pts: Sequence[tuple[float, float]],
    *,
    max_pts: int = 240,
) -> list[list[float]]:
    deduped: list[list[float]] = []
    for x, y in pts:
        cx = max(1.0, min(999.0, round(float(x), 2)))
        cy = max(1.0, min(699.0, round(float(y), 2)))
        if not deduped or math.hypot(cx - deduped[-1][0], cy - deduped[-1][1]) > 0.25:
            deduped.append([cx, cy])
    if len(deduped) > max_pts:
        step = (len(deduped) - 1) / float(max_pts - 1)
        sampled = [deduped[round(i * step)] for i in range(max_pts - 1)]
        sampled.append(deduped[-1])
        return sampled
    return deduped


def typeset_af4_text_to_artline_doc(
    font_name: str,
    text: str,
    archive_root: Path | None = None,
    *,
    fill: str = "#5ce1e6",
    stroke: str = "#f8cc30",
    stroke_width: float = 1.5,
    use_kerning: bool = True,
    letter_spacing: float = 0.0,
    pad: float = 48.0,
) -> ArtlineDocument:
    """Compile kerning-aware `.AF4` typeset text into an `ArtlineDocument` (CANVAS 1000x700, <=256 pts/path)."""
    layout = typeset_af4_text_layout(
        font_name,
        text,
        archive_root,
        use_kerning=use_kerning,
        letter_spacing=letter_spacing,
    )
    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0b0d18", stroke="#0b0d18", width=1)
    doc.add_element("rectangle", bounds=[20, 20, 980, 680], fill="#101528", stroke="#3c4f7f", width=1.4)

    min_x, min_y, max_x, max_y = layout["bounds"]
    span_x = max(1e-3, max_x - min_x)
    span_y = max(1e-3, max_y - min_y)
    avail_w = 1000.0 - 2.0 * pad
    avail_h = 540.0
    scale = min(avail_w / span_x, avail_h / span_y)
    ox = pad + (avail_w - span_x * scale) * 0.5
    oy = 80.0 + (avail_h - span_y * scale) * 0.5

    for item in layout["placed"]:
        for contour in item["contours"]:
            mapped = [(ox + (px - min_x) * scale, oy + (max_y - py) * scale) for px, py in contour]
            capped = _cap_polygon_points(mapped, max_pts=240)
            if len(capped) >= 3:
                doc.add_element(
                    "path",
                    points=capped,
                    fill=fill,
                    stroke=stroke,
                    width=stroke_width,
                    closed=True,
                )
    return doc


# ---------------------------------------------------------------------------
# 8. Forge Artifact Exporter (.GEM / .SVG / .ZOETK / .JSON)
# ---------------------------------------------------------------------------

_SVG_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_VALID_SVG_CMDS = frozenset("MLCHVSQTAZmlchvsqtaz")


def _eval_quad_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    steps: int = 6,
) -> list[tuple[float, float]]:
    c1 = (p0[0] + (2.0 / 3.0) * (p1[0] - p0[0]), p0[1] + (2.0 / 3.0) * (p1[1] - p0[1]))
    c2 = (p2[0] + (2.0 / 3.0) * (p1[0] - p2[0]), p2[1] + (2.0 / 3.0) * (p1[1] - p2[1]))
    return _eval_cubic_bezier(p0, c1, c2, p2, steps=steps)


def _eval_svg_arc(
    p0: tuple[float, float],
    rx_in: float,
    ry_in: float,
    phi_deg: float,
    large_arc_flag: float,
    sweep_flag: float,
    p1: tuple[float, float],
    steps: int = 8,
) -> list[tuple[float, float]]:
    """Sample an SVG elliptical arc (W3C SVG F.6.5/F.6.6 center parameterization) into polyline points."""
    x0, y0 = p0
    x1, y1 = p1
    if math.hypot(x1 - x0, y1 - y0) < 1e-6:
        return [p1]
    rx = abs(rx_in)
    ry = abs(ry_in)
    if rx < 1e-6 or ry < 1e-6:
        return [p1]

    phi = math.radians(phi_deg % 360.0)
    cos_p = math.cos(phi)
    sin_p = math.sin(phi)
    dx2 = (x0 - x1) * 0.5
    dy2 = (y0 - y1) * 0.5
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1.0:
        s_lam = math.sqrt(lam)
        rx *= s_lam
        ry *= s_lam

    large_arc = bool(abs(large_arc_flag) >= 0.5)
    sweep = bool(abs(sweep_flag) >= 0.5)
    rx2 = rx * rx
    ry2 = ry * ry
    x1p2 = x1p * x1p
    y1p2 = y1p * y1p
    denom = rx2 * y1p2 + ry2 * x1p2
    if denom <= 1e-12:
        return [p1]
    num = max(0.0, rx2 * ry2 - denom)
    coef = math.sqrt(num / denom) * (-1.0 if large_arc == sweep else 1.0)
    cxp = coef * ((rx * y1p) / ry)
    cyp = coef * (-(ry * x1p) / rx)

    cx = cos_p * cxp - sin_p * cyp + (x0 + x1) * 0.5
    cy = sin_p * cxp + cos_p * cyp + (y0 + y1) * 0.5

    def _vec_angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        len_prod = max(1e-12, math.hypot(ux, uy) * math.hypot(vx, vy))
        ang = math.acos(max(-1.0, min(1.0, dot / len_prod)))
        return -ang if (ux * vy - uy * vx) < 0.0 else ang

    vx0 = (x1p - cxp) / rx
    vy0 = (y1p - cyp) / ry
    vx1 = (-x1p - cxp) / rx
    vy1 = (-y1p - cyp) / ry
    theta1 = _vec_angle(1.0, 0.0, vx0, vy0)
    dtheta = _vec_angle(vx0, vy0, vx1, vy1)
    if not sweep and dtheta > 0.0:
        dtheta -= 2.0 * math.pi
    elif sweep and dtheta < 0.0:
        dtheta += 2.0 * math.pi

    out: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        t = theta1 + dtheta * (k / float(steps))
        ex = rx * math.cos(t)
        ey = ry * math.sin(t)
        out.append((cos_p * ex - sin_p * ey + cx, sin_p * ex + cos_p * ey + cy))
    return out


def _parse_svg_path_subpaths(d: str) -> list[list[tuple[float, float]]]:
    """Parse M/L/H/V/C/S/Q/T/A/Z SVG path commands into polygon/polyline point lists with strict validation."""
    tokens = _SVG_TOKEN_RE.findall(d or "")
    subpaths: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0
    last_ctrl_c: tuple[float, float] | None = None
    last_ctrl_q: tuple[float, float] | None = None
    cmd = ""
    i = 0

    def _take_nums(count: int, op: str) -> list[float]:
        nonlocal i
        if i + count > len(tokens):
            raise ValueError(f"Truncated SVG path command {op!r}: expected {count} coordinates, got {len(tokens) - i}")
        vals: list[float] = []
        for k in range(count):
            t = tokens[i + k]
            if t.isalpha():
                raise ValueError(f"Malformed SVG path command {op!r}: expected coordinate number, got {t!r}")
            try:
                val = float(t)
            except ValueError as exc:
                raise ValueError(f"Invalid coordinate {t!r} in SVG path command {op!r}") from exc
            if not math.isfinite(val):
                raise ValueError(f"Non-finite coordinate {t!r} in SVG path command {op!r}")
            vals.append(val)
        i += count
        return vals

    while i < len(tokens):
        tok = tokens[i]
        if tok.isalpha():
            if len(tok) != 1 or tok not in _VALID_SVG_CMDS:
                raise ValueError(f"Unsupported SVG path command {tok!r}")
            cmd = tok
            i += 1
            if cmd in ("Z", "z"):
                if len(cur) >= 2:
                    if math.hypot(cur[0][0] - cur[-1][0], cur[0][1] - cur[-1][1]) > 0.1:
                        cur.append((sx, sy))
                    subpaths.append(cur)
                cur = []
                cx, cy = sx, sy
                last_ctrl_c = None
                last_ctrl_q = None
                cmd = ""
                continue
            if i >= len(tokens) or tokens[i].isalpha():
                raise ValueError(f"Truncated SVG path command {cmd!r}: missing coordinate parameters")
            continue

        if not cmd:
            raise ValueError(f"Unexpected SVG path coordinate {tok!r} before any path command")

        if cmd in ("M", "m"):
            if len(cur) >= 2:
                subpaths.append(cur)
            x, y = _take_nums(2, cmd)
            if cmd == "m":
                x += cx
                y += cy
            cx, cy = x, y
            sx, sy = x, y
            cur = [(cx, cy)]
            last_ctrl_c = None
            last_ctrl_q = None
            cmd = "L" if cmd == "M" else "l"
        elif cmd in ("L", "l"):
            x, y = _take_nums(2, cmd)
            if cmd == "l":
                x += cx
                y += cy
            cx, cy = x, y
            cur.append((cx, cy))
            last_ctrl_c = None
            last_ctrl_q = None
        elif cmd in ("H", "h"):
            (x,) = _take_nums(1, cmd)
            if cmd == "h":
                x += cx
            cx = x
            cur.append((cx, cy))
            last_ctrl_c = None
            last_ctrl_q = None
        elif cmd in ("V", "v"):
            (y,) = _take_nums(1, cmd)
            if cmd == "v":
                y += cy
            cy = y
            cur.append((cx, cy))
            last_ctrl_c = None
            last_ctrl_q = None
        elif cmd in ("C", "c"):
            x1, y1, x2, y2, x3, y3 = _take_nums(6, cmd)
            if cmd == "c":
                x1, y1 = x1 + cx, y1 + cy
                x2, y2 = x2 + cx, y2 + cy
                x3, y3 = x3 + cx, y3 + cy
            cur.extend(_eval_cubic_bezier((cx, cy), (x1, y1), (x2, y2), (x3, y3), steps=6))
            last_ctrl_c = (x2, y2)
            last_ctrl_q = None
            cx, cy = x3, y3
        elif cmd in ("S", "s"):
            x2, y2, x3, y3 = _take_nums(4, cmd)
            if cmd == "s":
                x2, y2 = x2 + cx, y2 + cy
                x3, y3 = x3 + cx, y3 + cy
            if last_ctrl_c is not None:
                x1, y1 = 2.0 * cx - last_ctrl_c[0], 2.0 * cy - last_ctrl_c[1]
            else:
                x1, y1 = cx, cy
            cur.extend(_eval_cubic_bezier((cx, cy), (x1, y1), (x2, y2), (x3, y3), steps=6))
            last_ctrl_c = (x2, y2)
            last_ctrl_q = None
            cx, cy = x3, y3
        elif cmd in ("Q", "q"):
            x1, y1, x2, y2 = _take_nums(4, cmd)
            if cmd == "q":
                x1, y1 = x1 + cx, y1 + cy
                x2, y2 = x2 + cx, y2 + cy
            cur.extend(_eval_quad_bezier((cx, cy), (x1, y1), (x2, y2), steps=6))
            last_ctrl_q = (x1, y1)
            last_ctrl_c = None
            cx, cy = x2, y2
        elif cmd in ("T", "t"):
            x2, y2 = _take_nums(2, cmd)
            if cmd == "t":
                x2, y2 = x2 + cx, y2 + cy
            if last_ctrl_q is not None:
                x1, y1 = 2.0 * cx - last_ctrl_q[0], 2.0 * cy - last_ctrl_q[1]
            else:
                x1, y1 = cx, cy
            cur.extend(_eval_quad_bezier((cx, cy), (x1, y1), (x2, y2), steps=6))
            last_ctrl_q = (x1, y1)
            last_ctrl_c = None
            cx, cy = x2, y2
        elif cmd in ("A", "a"):
            rx, ry, x_rot, large_arc, sweep, x, y = _take_nums(7, cmd)
            if cmd == "a":
                x += cx
                y += cy
            cur.extend(_eval_svg_arc((cx, cy), rx, ry, x_rot, large_arc, sweep, (x, y), steps=8))
            last_ctrl_c = None
            last_ctrl_q = None
            cx, cy = x, y

    if len(cur) >= 2:
        subpaths.append(cur)
    return subpaths


def _safe_hex_color(val: Any, default: str = "#5ce1e6") -> str:
    if isinstance(val, str) and len(val) == 7 and val.startswith("#"):
        if all(ch in "0123456789abcdefABCDEF" for ch in val[1:]):
            return val.lower()
    return default


def _finite_float(stamp: Mapping[str, Any], key: str, default: float) -> float:
    if key not in stamp or stamp[key] is None:
        return default
    val = stamp[key]
    if isinstance(val, bool):
        raise ValueError(f"stamp[{key!r}] must be a finite number, not bool")
    try:
        fval = float(val)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"stamp[{key!r}] must be a finite number") from exc
    if not math.isfinite(fval):
        raise ValueError(f"stamp[{key!r}] must be a finite number")
    return fval


def _transform_stamp_subpaths(stamp: dict[str, Any]) -> list[list[tuple[int, int]]]:
    d = str(stamp.get("d", ""))
    subpaths = _parse_svg_path_subpaths(d)
    if not subpaths:
        return []
    tx = _finite_float(stamp, "x", 300.0)
    ty = _finite_float(stamp, "y", 200.0)
    s = _finite_float(stamp, "s", 1.0)
    sx = _finite_float(stamp, "sx", 1.0) * (-1.0 if stamp.get("flipH") else 1.0)
    sy = _finite_float(stamp, "sy", 1.0) * (-1.0 if stamp.get("flipV") else 1.0)
    rot_rad = math.radians(_finite_float(stamp, "rot", 0.0))
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)

    out: list[list[tuple[int, int]]] = []
    for sub in subpaths:
        pts: list[tuple[int, int]] = []
        for px, py in sub:
            lx = (px - 50.0) * s * sx
            ly = (py - 50.0) * s * sy
            rx = lx * cos_r - ly * sin_r
            ry = lx * sin_r + ly * cos_r
            gx = max(-32000, min(32000, int(round(tx + rx))))
            gy = max(-32000, min(32000, int(round(ty + ry))))
            if not pts or (gx, gy) != pts[-1]:
                pts.append((gx, gy))
        if len(pts) >= 2:
            out.append(pts)
    return out


def export_forge_artifact(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Export clean-room Forge stage/typeset artifacts as `.gem`, `.svg`, `.zoetk`, or `.json`."""
    norm_kind = str(kind).strip().lstrip(".").lower()
    if norm_kind not in {"gem", "svg", "zoetk", "json"}:
        raise ValueError(f"Unsupported Forge export kind {kind!r}; expected one of gem, svg, zoetk, json")

    data_in = dict(payload or {})
    stamps = list(data_in.get("stamps") or [])
    extra: dict[str, Any] = {}

    if norm_kind == "svg":
        if data_in.get("text") and not stamps:
            font_name = str(data_in.get("font") or "advtg_n.af4")
            archive_root = Path(str(data_in["archive_root"])) if data_in.get("archive_root") else None
            try:
                svg_str = typeset_af4_text_svg(font_name, str(data_in["text"]), archive_root=archive_root)
            except KeyError:
                svg_str = typeset_af4_text_svg("zoe_synth.af4", str(data_in["text"]), archive_root=archive_root)
        else:
            grid_lines: list[str] = []
            for gx in range(40, 600, 40):
                grid_lines.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="400" stroke="#182038" stroke-width="1"/>')
            for gy in range(40, 400, 40):
                grid_lines.append(f'<line x1="0" y1="{gy}" x2="600" y2="{gy}" stroke="#182038" stroke-width="1"/>')
            body: list[str] = []
            for st in stamps:
                if not isinstance(st, Mapping):
                    raise ValueError("Each stamp must be a mapping")
                raw_d = str(st.get("d", ""))
                d_attr = html_lib.escape(raw_d, quote=True)
                if not d_attr:
                    continue
                _parse_svg_path_subpaths(raw_d)
                col = _safe_hex_color(st.get("col"), "#5ce1e6")
                x = _finite_float(st, "x", 300.0)
                y = _finite_float(st, "y", 200.0)
                s = _finite_float(st, "s", 1.0)
                sx = _finite_float(st, "sx", 1.0) * (-1.0 if st.get("flipH") else 1.0)
                sy = _finite_float(st, "sy", 1.0) * (-1.0 if st.get("flipV") else 1.0)
                rot = _finite_float(st, "rot", 0.0)
                body.append(
                    f'<g transform="translate({x:.1f},{y:.1f}) rotate({rot:.1f}) scale({(s * sx):.3f},{(s * sy):.3f}) translate(-50,-50)">'
                    f'<path d="{d_attr}" fill="{col}33" stroke="{col}" stroke-width="2.6" fill-rule="evenodd" />'
                    f"</g>"
                )
            svg_str = (
                '<svg viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg">'
                '<rect width="600" height="400" fill="#090d1a"/>'
                + "".join(grid_lines)
                + "".join(body)
                + "</svg>"
            )
        raw_bytes = svg_str.encode("utf-8")
        filename = "zoe-artline-forge.svg"
        mime_type = "image/svg+xml"

    elif norm_kind == "gem":
        builder = VdiMetafileBuilder(width=600, height=400)
        builder.set_line(color="none")
        builder.set_fill(color="#090d1a", perimeter=False)
        builder.bar(0, 0, 600, 400)
        if data_in.get("text") and not stamps:
            font_name = str(data_in.get("font") or "advtg_n.af4")
            archive_root = Path(str(data_in["archive_root"])) if data_in.get("archive_root") else None
            try:
                layout = typeset_af4_text_layout(font_name, str(data_in["text"]), archive_root=archive_root)
            except KeyError:
                layout = typeset_af4_text_layout("zoe_synth.af4", str(data_in["text"]), archive_root=archive_root)
            min_x, min_y, max_x, max_y = layout["bounds"]
            span_x = max(1e-3, max_x - min_x)
            span_y = max(1e-3, max_y - min_y)
            sc = min(520.0 / span_x, 300.0 / span_y)
            ox = 40.0 + (520.0 - span_x * sc) * 0.5
            oy = 50.0 + (300.0 - span_y * sc) * 0.5
            builder.set_line(color="#f8cc30", width=1)
            builder.set_fill(color="#5ce1e6", perimeter=True)
            for item in layout["placed"]:
                for contour in item["contours"]:
                    pts = [(int(round(ox + (px - min_x) * sc)), int(round(oy + (max_y - py) * sc))) for px, py in contour]
                    if len(pts) >= 3:
                        builder.fillarea(pts)
        else:
            for st in stamps:
                col = _safe_hex_color(st.get("col"), "#5ce1e6")
                if len(builder._palette["custom"]) >= 230 and col not in builder._palette["custom"]:
                    col = "#5ce1e6"
                subpaths = _transform_stamp_subpaths(st)
                if not subpaths:
                    continue
                builder.set_line(color=col, width=2)
                builder.set_fill(color=col, interior=1, perimeter=True)
                for pts in subpaths:
                    unique_pts = list(dict.fromkeys(pts))
                    if len(unique_pts) >= 3:
                        builder.fillarea(pts)
                    elif len(pts) >= 2:
                        builder.pline(pts)
        raw_bytes = builder.build()
        parse_metafile(raw_bytes)
        filename = "zoe-artline-forge.gem"
        mime_type = "application/octet-stream"
        extra["valid_gem_header"] = raw_bytes[:2] == b"\xff\xff"
        extra["magic"] = "0xFFFF"

    elif norm_kind == "zoetk":
        tb_spec: ZoeToolboxSpec | None = None
        if "toolbox" in data_in and data_in["toolbox"] is not None:
            tb_raw_obj = data_in["toolbox"]
            if not isinstance(tb_raw_obj, Mapping):
                raise ValueError("payload['toolbox'] must be a mapping")
            tb_raw = tb_raw_obj
            raw_buttons = tb_raw.get("buttons", [])
            if not isinstance(raw_buttons, (list, tuple)):
                raise ValueError("payload['toolbox']['buttons'] must be a list or tuple")
            req_btn_fields = ("tool_id", "label", "shortcut", "adc12_code", "wombat_glyph", "color_hex")
            parsed_btns: list[ToolboxButton] = []
            for idx, b in enumerate(raw_buttons):
                if not isinstance(b, Mapping):
                    raise ValueError(f"Toolbox button[{idx}] must be a mapping")
                missing_fields = [f for f in req_btn_fields if f not in b]
                extra_fields = [k for k in b if k not in req_btn_fields]
                if missing_fields or extra_fields:
                    raise ValueError(
                        f"Malformed toolbox button[{idx}]: missing={missing_fields}, unexpected={extra_fields}"
                    )
                parsed_btns.append(
                    ToolboxButton(
                        tool_id=str(b["tool_id"]),
                        label=str(b["label"]),
                        shortcut=str(b["shortcut"]),
                        adc12_code=str(b["adc12_code"]),
                        wombat_glyph=str(b["wombat_glyph"]),
                        color_hex=str(b["color_hex"]),
                    )
                )
            raw_cols = tb_raw.get("columns", 2)
            if isinstance(raw_cols, bool) or not isinstance(raw_cols, int) or not (1 <= raw_cols <= 65535):
                raise ValueError("payload['toolbox']['columns'] must be an integer in [1, 65535]")
            cols = raw_cols
            raw_tb_id = tb_raw.get("toolbox_id", "custom_forge")
            if (
                not isinstance(raw_tb_id, str)
                or not raw_tb_id
                or "\x00" in raw_tb_id
                or ".." in raw_tb_id
                or "/" in raw_tb_id
                or "\\" in raw_tb_id
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", raw_tb_id)
            ):
                raise ValueError("payload['toolbox']['toolbox_id'] must be a clean non-empty identifier")
            tb_spec = ZoeToolboxSpec(
                toolbox_id=raw_tb_id,
                title=str(tb_raw.get("title", "Custom Forge Toolbox")),
                columns=cols,
                description=str(tb_raw.get("description", "Exported from Zoe Artline Forge")),
                buttons=tuple(parsed_btns),
            )
        else:
            raw_top_tb_id = data_in.get("toolbox_id")
            if raw_top_tb_id is not None:
                if not isinstance(raw_top_tb_id, str) or "\x00" in raw_top_tb_id or ".." in raw_top_tb_id or "/" in raw_top_tb_id or "\\" in raw_top_tb_id:
                    raise ValueError("payload['toolbox_id'] must be a clean identifier")
            tb_id = str(raw_top_tb_id or "")
            for candidate in STUDIO_TOOLBOXES:
                if candidate.toolbox_id == tb_id:
                    tb_spec = candidate
                    break
            if tb_spec is None:
                tb_spec = STUDIO_TOOLBOXES[0]
        raw_bytes = tb_spec.to_zoetk_binary()
        filename = f"{tb_spec.toolbox_id}.zoetk"
        mime_type = "application/octet-stream"
        extra["magic"] = "ZOETK001"
        extra["toolbox_id"] = tb_spec.toolbox_id

    else:  # json
        doc = {
            "contract": ARTLINE_FORGE_CONTRACT,
            "stamps": stamps,
            "toolbox_id": data_in.get("toolbox_id", STUDIO_TOOLBOXES[0].toolbox_id),
            "palette_id": data_in.get("palette_id", STUDIO_PALETTES[0].palette_id),
            "text": data_in.get("text", ""),
            "font": data_in.get("font", ""),
            "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
            "cloud_tokens_used": 0,
        }
        raw_bytes = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")
        filename = "zoe-artline-forge.json"
        mime_type = "application/json"

    return {
        "ok": True,
        "contract": ARTLINE_FORGE_CONTRACT,
        "kind": norm_kind,
        "filename": filename,
        "mime_type": mime_type,
        "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "bytes_len": len(raw_bytes),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "constitutional_flags": dict(CONSTITUTIONAL_FLAGS),
        "cloud_tokens_used": 0,
        **extra,
    }


def _safe_inline_script_json(raw_json: str) -> str:
    """Escape HTML script-breakout sequences inside inline <script> JSON literals."""
    return raw_json.replace("</", "<\\/").replace("<!--", "\\u003c!--")


def build_interactive_artline_forge_html_str(archive_root: Path | None = None) -> str:
    """Return HTML string for the interactive Zoe Artline Forge (:8765/forge & offline HTML5)."""
    bundle = _load_archive_bundle(archive_root)
    toolboxes_json = _safe_inline_script_json(json.dumps([asdict(tb) for tb in STUDIO_TOOLBOXES], ensure_ascii=False))
    palettes_json = _safe_inline_script_json(json.dumps([asdict(p) for p in STUDIO_PALETTES], ensure_ascii=False))
    vecs_json = _safe_inline_script_json(bundle.vectors_json)
    unicode_cp437_json = _safe_inline_script_json(json.dumps(_UNICODE_TO_CP437_MAP, ensure_ascii=False))
    syf_total = sum(len(lib.symbols) for lib in bundle.syf_libraries)
    pack_count = len(bundle.syf_libraries)
    font_count = len(bundle.fonts)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Zoe Artline Forge — {font_count} .AF4 Fonts, {syf_total} .SYF Vectors, .TLS/.COL/.GEM Inspector</title>
<style>
  * {{ box-sizing: border-box; font-family: "DejaVu Sans", system-ui, sans-serif; }}
  body {{ margin: 0; background: #0b0d18; color: #f0f4fc; min-height: 100vh; display: flex; flex-direction: column; }}
  header {{ background: #141a2e; border-bottom: 2px solid #f8cc30; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 16.5px; color: #5ce1e6; }}
  .navlinks {{ display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }}
  .navlinks a {{ text-decoration: none; font-size: 11.5px; padding: 4px 9px; border-radius: 6px; border: 1px solid #3c4d7a; color: #cbd5e1; background: #18213d; font-weight: 600; }}
  .navlinks a:hover {{ border-color: #f8cc30; color: #f8cc30; }}
  .layout {{ display: grid; grid-template-columns: 1.25fr 1.25fr 0.95fr; gap: 14px; padding: 14px 18px; flex: 1; }}
  @media (max-width: 1160px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: #12182c; border: 1.5px solid #2b385c; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 9px; }}
  .panel h2 {{ margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.7px; color: #f8cc30; }}
  .tabs {{ display: flex; gap: 5px; flex-wrap: wrap; align-items: center; }}
  button, select, input {{ background: #1b2442; color: #f0f4fc; border: 1.5px solid #3c4f7f; border-radius: 7px; padding: 5px 8px; font-weight: 600; font-size: 11px; }}
  button {{ cursor: pointer; }}
  button:hover {{ filter: brightness(1.16); }}
  button.active {{ border-color: #5ce1e6; color: #5ce1e6; background: #102a38; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); gap: 7px; max-height: 440px; overflow-y: auto; }}
  .tile {{ background: #0e1426; border: 1px solid #2e3e66; border-radius: 8px; padding: 6px; text-align: center; cursor: pointer; }}
  .tile:hover {{ border-color: #f8cc30; background: #17203c; }}
  .tile svg {{ width: 50px; height: 50px; display: block; margin: 0 auto 3px; }}
  .tile .lbl {{ font-size: 9.5px; color: #94a3c8; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #stage {{ width: 100%; height: 370px; background: #090d1a; border: 2px solid #5ce1e6; border-radius: 10px; cursor: crosshair; }}
  .typeset-box {{ background: #0d1324; border: 1px solid #2e3f6b; border-radius: 8px; padding: 8px; display: flex; flex-direction: column; gap: 6px; }}
  #typesetPreview {{ width: 100%; height: 64px; background: #090d1a; border: 1px solid #263558; border-radius: 6px; }}
  .tb-grid {{ display: grid; gap: 6px; }}
  .tb-btn {{ display: flex; align-items: center; gap: 6px; text-align: left; padding: 6px 8px; font-size: 11px; }}
  .tls-list {{ display: flex; flex-wrap: wrap; gap: 5px; max-height: 150px; overflow-y: auto; }}
  .tls-pill {{ display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; padding: 3px 7px; border-radius: 999px; background: #0e1426; border: 1px solid #3c4f7f; color: #cbd5e1; font-family: monospace; }}
  .swatches {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; max-height: 165px; overflow-y: auto; }}
  .sw {{ border-radius: 7px; padding: 7px 5px; text-align: center; cursor: pointer; border: 2px solid transparent; font-size: 9.5px; font-weight: 700; color: #0b0d18; text-shadow: 0 0 2px rgba(255,255,255,0.45); }}
  .sw.sel {{ border-color: #ffffff; transform: scale(1.03); }}
  footer {{ padding: 7px 20px; background: #101424; border-top: 1px solid #263354; font-size: 11px; color: #94a3c8; }}
</style>
</head>
<body>
<header>
  <h1>⚒ Zoe Artline Forge · {font_count} .AF4 Fonts · {syf_total} .SYF Vectors · .TLS/.COL/.GEM Studio</h1>
  <div class="navlinks">
    <a href="/">← Studio</a>
    <a href="/artline">🎨 Artline</a>
    <a href="/physics">✺ Physics</a>
    <a href="/duodecimal">❖ ADC-12</a>
    <a href="/orbit">✦ Orbit</a>
  </div>
</header>

<div class="layout">
  <section class="panel">
    <h2>Clean-Room Vector Vault ({font_count} .AF4 · {pack_count} .SYF · .GEM)</h2>
    <div class="tabs">
      <button id="vWom" class="active" onclick="setVault('wombat')">wombat.af4</button>
      <button id="vSym" onclick="setVault('symbol')">symbol.af4</button>
      <button id="vCha" onclick="setVault('chancery')">Zapf Chancery</button>
      <button id="vAf4" onclick="setVault('af4')">All .AF4 ({font_count})</button>
      <button id="vSyf" onclick="setVault('syf')">All .SYF ({syf_total})</button>
      <button id="vGem" onclick="setVault('gem')">.GEM Inspector</button>
    </div>
    <div id="af4FilterRow" class="tabs" style="display:none;">
      <select id="af4FontSel" onchange="renderVault()" style="flex:1;"></select>
    </div>
    <div id="syfFilterRow" class="tabs" style="display:none;">
      <select id="syfPackSel" onchange="renderVault()"></select>
      <input id="syfSearch" type="text" placeholder="Filter symbol name..." oninput="renderVault()" style="flex:1;min-width:110px;" />
    </div>
    <div id="vaultGrid" class="grid"></div>
  </section>

  <section class="panel">
    <h2>Live Artline Vector Stamp Canvas &amp; .AF4 Kerning Typesetter</h2>
    <svg id="stage" viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg"></svg>
    <div class="tabs">
      <button style="border-color:#52e5a8;color:#52e5a8;" onclick="stampRadial()">✺ 9-Petal Ring</button>
      <button onclick="scaleSelected(1.15)">＋ Scale</button>
      <button onclick="scaleSelected(0.85)">－ Scale</button>
      <button onclick="rotateSelected(-15)">↺ -15°</button>
      <button onclick="rotateSelected(15)">↻ +15°</button>
      <button onclick="undoStage()">↶ Undo</button>
      <button onclick="deleteSelected()">⌫ Del</button>
      <button style="border-color:#f35670;color:#f35670;" onclick="clearStage()">✕ Clear</button>
    </div>
    <div class="tabs">
      <button style="border-color:#f8cc30;color:#f8cc30;" onclick="exportSvg()">❏ .SVG</button>
      <button style="border-color:#5ce1e6;color:#5ce1e6;" onclick="exportArtifact('gem')">◆ .GEM</button>
      <button style="border-color:#ac82ff;color:#ac82ff;" onclick="exportArtifact('zoetk')">⚙ .ZOETK</button>
      <button style="border-color:#ff85b3;color:#ff85b3;" onclick="exportArtifact('json')">{'{ }'} .JSON</button>
    </div>
    <div class="typeset-box">
      <div class="tabs">
        <select id="tsFontSel" onchange="renderTypesetPreview()" style="max-width:190px;"></select>
        <input id="tsText" type="text" value="AVE, Zoe; 2026" oninput="renderTypesetPreview()" style="flex:1;min-width:110px;" />
        <label style="font-size:10.5px;display:inline-flex;align-items:center;gap:4px;"><input id="tsKern" type="checkbox" checked onchange="renderTypesetPreview()" /> Kern</label>
        <button style="border-color:#5ce1e6;color:#5ce1e6;" onclick="stampTypesetToCanvas()">+ Stamp Text</button>
      </div>
      <svg id="typesetPreview" viewBox="0 0 560 72" xmlns="http://www.w3.org/2000/svg"></svg>
    </div>
    <div id="stageStatus" style="font-size:11px;color:#94a3c8;">Click any vector or typeset preview to stamp; click stage shapes to select &amp; transform with toolboxes!</div>
  </section>

  <section class="panel">
    <h2>Programmable Toolboxes (ZOETK001 &amp; 1990 CCPTK001 .TLS)</h2>
    <div id="tbTabs" class="tabs"></div>
    <div id="tbDesc" style="font-size:11px;color:#94a3c8;"></div>
    <div id="tbGrid" class="tb-grid"></div>
    <div id="tls1990Box" style="display:none;">
      <div id="tlsTabs" class="tabs" style="margin-bottom:6px;"></div>
      <div id="tlsMeta" style="font-size:10.5px;color:#5ce1e6;margin-bottom:5px;font-family:monospace;"></div>
      <div id="tlsPills" class="tls-list"></div>
    </div>
    <h2 style="margin-top:6px;">Vector-Metafile Palettes (.COL &amp; Studio)</h2>
    <div id="palTabs" class="tabs"></div>
    <div id="colSelectRow" class="tabs" style="display:none;">
      <select id="colPalSel" onchange="renderPalettes()" style="flex:1;"></select>
    </div>
    <div id="swatches" class="swatches"></div>
  </section>
</div>

<footer>Optimize+Improve+Zoe+Nick+Fun+Creative = LIFE · Clean-Room Artline Forge · 0 Cloud Tokens · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False</footer>

<script>
const VECS = {vecs_json};
const TOOLBOXES = {toolboxes_json};
const PALETTES = {palettes_json};
const UNICODE_TO_CP437 = {unicode_cp437_json};

let vaultTab = 'wombat';
let activeTb = 0;
let show1990Tls = false;
let activeTlsIdx = 0;
let activePal = 0;
let show1990Col = false;
let activeColor = PALETTES[0].swatches[0].hex_color;
let activeAdc12 = '400';
let toolMode = 'stamp';
let selectedIdx = -1;
let snapGrid = false;
let physMode = 'off';
let physRaf = 0;
let preSmashSnapshot = null;

const syfPackNames = Object.keys(VECS.syf_packs || {{}});
const af4Fonts = VECS.af4_fonts || [];
const colPalettes = VECS.col_palettes || [];
let selectedVector = (VECS.wombat_glyphs && VECS.wombat_glyphs[0]) || ((VECS.syf_packs[syfPackNames[0]] || [])[0]);
let stamps = [];
const undoStack = [];

function pushUndo() {{
  undoStack.push(JSON.stringify(stamps));
  if (undoStack.length > 40) undoStack.shift();
}}

function makeStamp(d, x, y, s, rot, col, skipSnap) {{
  const useSnap = snapGrid && !skipSnap;
  return {{
    d: d || '',
    x: useSnap ? Math.round(x / 40) * 40 : x,
    y: useSnap ? Math.round(y / 40) * 40 : y,
    s: s || 0.85,
    sx: 1,
    sy: 1,
    flipH: false,
    flipV: false,
    rot: rot || 0,
    col: col || activeColor,
    vx: 0,
    vy: 0,
    adc12: activeAdc12,
  }};
}}

function escHtml(val) {{
  return String(val == null ? '' : val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}}

function escJsAttr(val) {{
  return escHtml(
    String(val == null ? '' : val)
      .replace(/\\\\/g, '\\\\\\\\')
      .replace(/'/g, "\\\\'")
      .replace(/\\r/g, '\\\\r')
      .replace(/\\n/g, '\\\\n')
  );
}}

(function initSelectors() {{
  const packSel = document.getElementById('syfPackSel');
  const pOpts = ['<option value="ALL">ALL PACKS (' + escHtml(VECS.syf_total) + ')</option>'];
  for (const pk of syfPackNames) {{
    pOpts.push('<option value="' + escHtml(pk) + '">' + escHtml(pk) + ' (' + escHtml(VECS.syf_packs[pk].length) + ')</option>');
  }}
  packSel.innerHTML = pOpts.join('');

  const af4Opts = af4Fonts.map((f, idx) => `<option value="${{idx}}">${{escHtml(f.display_name)}} (${{escHtml(f.filename)}} · ${{escHtml(f.decoded_chars)}}g · ${{escHtml(f.kerning_pairs_count)}}k)</option>`).join('');
  document.getElementById('af4FontSel').innerHTML = af4Opts;
  document.getElementById('tsFontSel').innerHTML = af4Opts;
  const advIdx = af4Fonts.findIndex(f => f.filename.toLowerCase() === 'advtg_n.af4');
  if (advIdx >= 0) {{
    document.getElementById('tsFontSel').value = String(advIdx);
    document.getElementById('af4FontSel').value = String(advIdx);
  }}

  const colSel = document.getElementById('colPalSel');
  colSel.innerHTML = colPalettes.map((cp, idx) => `<option value="${{idx}}">${{escHtml(cp.filename)}} (${{escHtml(cp.swatch_count)}} swatches)</option>`).join('');
}})();

function setStatus(msg) {{
  document.getElementById('stageStatus').textContent = msg;
}}

function setVault(tab) {{
  vaultTab = tab;
  document.getElementById('vWom').classList.toggle('active', tab==='wombat');
  document.getElementById('vSym').classList.toggle('active', tab==='symbol');
  document.getElementById('vCha').classList.toggle('active', tab==='chancery');
  document.getElementById('vAf4').classList.toggle('active', tab==='af4');
  document.getElementById('vSyf').classList.toggle('active', tab==='syf');
  document.getElementById('vGem').classList.toggle('active', tab==='gem');
  document.getElementById('af4FilterRow').style.display = (tab === 'af4') ? 'flex' : 'none';
  document.getElementById('syfFilterRow').style.display = (tab === 'syf') ? 'flex' : 'none';
  renderVault();
}}

function renderVault() {{
  const grid = document.getElementById('vaultGrid');
  let list = [];
  if (vaultTab === 'wombat') {{
    list = (VECS.wombat_glyphs || []).map(g => ({{ label: g.code + ' ' + g.key, d: g.d }}));
  }} else if (vaultTab === 'symbol') {{
    list = (VECS.symbol_glyphs || []).map(g => ({{ label: g.code + ' ' + g.key, d: g.d }}));
  }} else if (vaultTab === 'chancery') {{
    list = (VECS.chancery_glyphs || []).map(g => ({{ label: g.code + ' ' + g.key, d: g.d }}));
  }} else if (vaultTab === 'af4') {{
    const fIdx = Number(document.getElementById('af4FontSel').value || 0);
    const font = af4Fonts[fIdx] || af4Fonts[0];
    if (font) {{
      list = Object.entries(font.glyphs || {{}}).map(([code, g]) => ({{
        label: code + ' ' + (Number(code) >= 33 && Number(code) < 127 ? String.fromCharCode(Number(code)) : '#' + code),
        d: g.em,
      }}));
    }}
  }} else if (vaultTab === 'gem') {{
    const gems = VECS.gem_samples || [];
    grid.innerHTML = gems.map((gm, idx) => `
      <div class="tile" onclick="pickGem(${{idx}})" title="${{escHtml(gm.filename)}} · ${{escHtml(gm.record_count)}} records">
        ${{gm.preview_svg}}
        <div class="lbl">${{escHtml(gm.filename)}}</div>
      </div>`).join('');
    window._curVaultList = gems.map(gm => ({{ label: gm.filename, d: gm.d || 'M20,20 L80,20 L80,80 L20,80 Z' }}));
    return;
  }} else {{
    const pk = document.getElementById('syfPackSel').value || 'ALL';
    const q = (document.getElementById('syfSearch').value || '').trim().toUpperCase();
    const raw = (pk === 'ALL') ? syfPackNames.flatMap(k => VECS.syf_packs[k] || []) : (VECS.syf_packs[pk] || []);
    list = raw.filter(s => !q || s.name.toUpperCase().includes(q) || s.pack.toUpperCase().includes(q))
              .map(s => ({{ label: s.name, d: s.d }}));
  }}
  const vb = (vaultTab === 'af4') ? '-5 0 110 120' : '0 0 100 100';
  grid.innerHTML = list.map((item, idx) => `
    <div class="tile" onclick="pickVec(${{idx}})" title="${{escHtml(item.label)}}">
      <svg viewBox="${{vb}}"><path d="${{escHtml(item.d)}}" fill="${{escHtml(activeColor)}}33" stroke="${{escHtml(activeColor)}}" stroke-width="3" fill-rule="evenodd" /></svg>
      <div class="lbl">${{escHtml(item.label)}}</div>
    </div>`).join('');
  window._curVaultList = list;
}}

function pickGem(idx) {{
  const gm = (VECS.gem_samples || [])[idx];
  if (!gm) return;
  setStatus(`.GEM Inspect: ${{gm.filename}} · ${{gm.record_count}} VDI records · fill=${{gm.primitive_counts.fillarea}} pline=${{gm.primitive_counts.pline}} gdp=${{gm.primitive_counts.gdp}}`);
  if (gm.d) pickVec(idx);
}}

function pickVec(idx) {{
  const item = (window._curVaultList || [])[idx];
  if (!item) return;
  selectedVector = item;
  pushUndo();
  stamps.push(makeStamp(item.d, 90 + Math.random()*420, 70 + Math.random()*260, 0.95, 0, activeColor));
  selectedIdx = stamps.length - 1;
  renderStage();
  setStatus('Stamped ' + item.label + ' in ' + activeColor + ' (' + stamps.length + ' vectors on canvas)');
}}

function stampRadial() {{
  if (!selectedVector) return;
  pushUndo();
  const pal = PALETTES[activePal].swatches;
  for (let k = 0; k < 9; k++) {{
    const ang = (Math.PI * 2 * k) / 9;
    const x = 300 + Math.cos(ang) * 115;
    const y = 200 + Math.sin(ang) * 115;
    stamps.push(makeStamp(selectedVector.d, x, y, 0.72, Math.round(ang * 180 / Math.PI), pal[k % pal.length].hex_color));
  }}
  selectedIdx = stamps.length - 1;
  renderStage();
  setStatus('Stamped 9-petal symmetry ring (' + stamps.length + ' total vectors)!');
}}

function targetIndices() {{
  if (selectedIdx >= 0 && selectedIdx < stamps.length) return [selectedIdx];
  return stamps.map((_, i) => i);
}}

function scaleSelected(factor) {{
  if (!stamps.length) return;
  pushUndo();
  for (const i of targetIndices()) stamps[i].s = Math.max(0.2, Math.min(4.0, stamps[i].s * factor));
  renderStage();
}}

function rotateSelected(deg) {{
  if (!stamps.length) return;
  pushUndo();
  for (const i of targetIndices()) stamps[i].rot = (stamps[i].rot + deg) % 360;
  renderStage();
}}

function undoStage() {{
  if (!undoStack.length) return;
  stopPhysics();
  stamps = JSON.parse(undoStack.pop());
  if (selectedIdx >= stamps.length) selectedIdx = stamps.length - 1;
  renderStage();
  setStatus('Undid last canvas edit (' + stamps.length + ' vectors)');
}}

function deleteSelected() {{
  if (!stamps.length) return;
  pushUndo();
  if (selectedIdx >= 0 && selectedIdx < stamps.length) {{
    stamps.splice(selectedIdx, 1);
    selectedIdx = stamps.length - 1;
  }} else {{
    stamps.pop();
  }}
  renderStage();
}}

function clearStage() {{
  pushUndo();
  stopPhysics();
  stamps.length = 0;
  selectedIdx = -1;
  renderStage();
  setStatus('Canvas cleared.');
}}

function renderStage() {{
  const svg = document.getElementById('stage');
  let gridLines = '';
  const gridCol = snapGrid ? '#263864' : '#182038';
  for (let gx = 40; gx < 600; gx += 40) gridLines += `<line x1="${{gx}}" y1="0" x2="${{gx}}" y2="400" stroke="${{gridCol}}" stroke-width="1"/>`;
  for (let gy = 40; gy < 400; gy += 40) gridLines += `<line x1="0" y1="${{gy}}" x2="600" y2="${{gy}}" stroke="${{gridCol}}" stroke-width="1"/>`;
  const body = stamps.map((st, idx) => {{
    const fx = (st.sx || 1) * (st.flipH ? -1 : 1) * st.s;
    const fy = (st.sy || 1) * (st.flipV ? -1 : 1) * st.s;
    const selRing = (idx === selectedIdx)
      ? `<rect x="-4" y="-4" width="108" height="108" fill="none" stroke="#5ce1e6" stroke-dasharray="5,4" stroke-width="1.8" />`
      : '';
    return `<g data-idx="${{idx}}" onclick="selectStamp(event, ${{idx}})" transform="translate(${{Number(st.x || 0).toFixed(1)}},${{Number(st.y || 0).toFixed(1)}}) rotate(${{Number(st.rot || 0)}}) scale(${{fx.toFixed(3)}},${{fy.toFixed(3)}}) translate(-50,-50)">
      <path d="${{escHtml(st.d)}}" fill="${{escHtml(st.col)}}33" stroke="${{escHtml(st.col)}}" stroke-width="2.6" fill-rule="evenodd" />${{selRing}}
    </g>`;
  }}).join('');
  svg.innerHTML = `<rect width="600" height="400" fill="#090d1a"/>${{gridLines}}${{body}}`;
}}

function selectStamp(ev, idx) {{
  ev.stopPropagation();
  selectedIdx = idx;
  renderStage();
  const st = stamps[idx];
  if (st) setStatus(`Selected stamp #${{idx + 1}} (ADC-12 ${{st.adc12 || '400'}} · x=${{st.x.toFixed(0)}}, y=${{st.y.toFixed(0)}}, rot=${{st.rot}}°)`);
}}

document.getElementById('stage').addEventListener('click', (e) => {{
  if (toolMode === 'select') {{
    selectedIdx = -1;
    renderStage();
    return;
  }}
  if (!selectedVector) return;
  const r = e.currentTarget.getBoundingClientRect();
  const x = (e.clientX - r.left) * (600 / r.width);
  const y = (e.clientY - r.top) * (400 / r.height);
  pushUndo();
  stamps.push(makeStamp(selectedVector.d, x, y, 0.85, 0, activeColor));
  selectedIdx = stamps.length - 1;
  renderStage();
}});

function stopPhysics() {{
  physMode = 'off';
  if (physRaf) {{
    cancelAnimationFrame(physRaf);
    physRaf = 0;
  }}
}}

function stepPhysics() {{
  if (physMode === 'off') return;
  for (const st of stamps) {{
    if (physMode === 'grav') st.vy += 0.35;
    st.x += st.vx;
    st.y += st.vy;
    if (st.x < 35 || st.x > 565) {{
      st.vx *= -0.85;
      st.x = Math.max(35, Math.min(565, st.x));
    }}
    if (st.y < 35) {{
      st.vy *= -0.85;
      st.y = 35;
    }} else if (st.y > 365) {{
      st.vy *= -0.78;
      st.y = 365;
      st.vx *= 0.96;
    }}
    if (physMode === 'shatter') st.rot = (st.rot + 4) % 360;
  }}
  renderStage();
  physRaf = requestAnimationFrame(stepPhysics);
}}

function runTool(toolId, adc12Code, colorHex, label) {{
  activeAdc12 = adc12Code || activeAdc12;
  const procedural = {{
    bezier: 'M10,82 C18,16 82,16 90,82 C70,48 30,48 10,82 Z',
    spark: 'M50,6 L60,36 L92,36 L66,56 L76,90 L50,68 L24,90 L34,56 L8,36 L40,36 Z',
    card: 'M14,20 L86,20 L86,80 L14,80 Z M24,34 L76,34 L76,42 L24,42 Z M24,52 L66,52 L66,60 L24,60 Z',
    rosette: 'M50,10 C68,26 68,42 50,50 C32,42 32,26 50,10 Z M90,50 C74,68 58,68 50,50 C58,32 74,32 90,50 Z M50,90 C32,74 32,58 50,50 C68,58 68,74 50,90 Z M10,50 C26,32 42,32 50,50 C42,68 26,68 10,50 Z',
    seal: 'M50,8 L92,50 L50,92 L8,50 Z M50,24 L76,50 L50,76 L24,50 Z',
  }};
  const alignMap = {{
    align_tl: [80, 70], align_tc: [300, 70], align_tr: [520, 70],
    align_ml: [80, 200], align_cc: [300, 200], align_mr: [520, 200],
  }};

  if (toolId === 'select') {{
    toolMode = 'select';
    setStatus('Selector active: click any shape on canvas to select and transform.');
    return;
  }}
  if (procedural[toolId]) {{
    toolMode = 'stamp';
    selectedVector = {{ label, d: procedural[toolId] }};
    pushUndo();
    stamps.push(makeStamp(procedural[toolId], 160 + Math.random()*280, 110 + Math.random()*180, 0.95, 0, colorHex || activeColor));
    selectedIdx = stamps.length - 1;
    renderStage();
    setStatus(`Stamped ${{label}} (${{adc12Code}}₁₂)`);
    return;
  }}
  if (alignMap[toolId]) {{
    if (!stamps.length) return;
    pushUndo();
    const [ax, ay] = alignMap[toolId];
    for (const i of targetIndices()) {{
      stamps[i].x = ax;
      stamps[i].y = ay;
    }}
    renderStage();
    setStatus(`Aligned to ${{label}} (${{ax}}, ${{ay}})`);
    return;
  }}
  if (toolId === 'mirror_h' || toolId === 'mirror_v') {{
    if (!stamps.length) return;
    pushUndo();
    for (const i of targetIndices()) {{
      if (toolId === 'mirror_h') stamps[i].flipH = !stamps[i].flipH;
      else stamps[i].flipV = !stamps[i].flipV;
    }}
    renderStage();
    setStatus(`Toggled ${{label}}`);
    return;
  }}
  if (toolId === 'snap_grid') {{
    snapGrid = !snapGrid;
    if (snapGrid && stamps.length) {{
      pushUndo();
      for (const i of targetIndices()) {{
        stamps[i].x = Math.round(stamps[i].x / 40) * 40;
        stamps[i].y = Math.round(stamps[i].y / 40) * 40;
      }}
    }}
    renderStage();
    setStatus('Snap Grid ' + (snapGrid ? 'ON (40px)' : 'OFF'));
    return;
  }}
  if (toolId === 'phys_off') {{
    stopPhysics();
    setStatus('Physics OFF (vectors pinned).');
    return;
  }}
  if (toolId === 'phys_zero' || toolId === 'phys_grav' || toolId === 'launch_star' || toolId === 'shatter_all') {{
    if (!preSmashSnapshot) preSmashSnapshot = JSON.stringify(stamps);
    if (toolId === 'launch_star') {{
      pushUndo();
      stamps.push(makeStamp(procedural.spark, 300, 320, 0.9, 0, colorHex || '#f35670'));
    }}
    for (const st of stamps) {{
      if (toolId === 'phys_zero') {{
        st.vx = (Math.random() - 0.5) * 3.0;
        st.vy = (Math.random() - 0.5) * 3.0;
      }} else if (toolId === 'launch_star') {{
        st.vx = (Math.random() - 0.5) * 5.0;
        st.vy = -4.0 - Math.random() * 4.0;
      }} else {{
        st.vx = (Math.random() - 0.5) * 8.0;
        st.vy = -2.0 - Math.random() * 5.0;
      }}
    }}
    stopPhysics();
    physMode = (toolId === 'phys_zero') ? 'zero' : (toolId === 'shatter_all' ? 'shatter' : 'grav');
    physRaf = requestAnimationFrame(stepPhysics);
    setStatus(`Physics ${{label}} running (click Instant Reset to restore)!`);
    return;
  }}
  if (toolId === 'rebuild') {{
    stopPhysics();
    if (preSmashSnapshot) {{
      stamps = JSON.parse(preSmashSnapshot);
      preSmashSnapshot = null;
    }} else {{
      for (const st of stamps) {{ st.vx = 0; st.vy = 0; }}
    }}
    renderStage();
    setStatus('Instant Reset restored pre-smash vector layout.');
    return;
  }}
  if (toolId.startsWith('c')) {{
    activeColor = colorHex || activeColor;
    activeAdc12 = adc12Code || activeAdc12;
    if (selectedIdx >= 0 && selectedIdx < stamps.length) {{
      pushUndo();
      stamps[selectedIdx].col = activeColor;
      stamps[selectedIdx].adc12 = activeAdc12;
      renderStage();
    }}
    renderPalettes();
    renderVault();
    setStatus(`ADC-12 [${{adc12Code}}₁₂] ${{label}} active (${{activeColor}})`);
  }}
}}

function resolveAf4Code(font, chStr) {{
  const raw = chStr.charCodeAt(0);
  if (raw < 128) return raw;
  const glyphs = (font && font.glyphs) || {{}};
  if (chStr === 'ß') {{
    if (glyphs['225']) return 225;
    if (glyphs['158']) return 158;
  }}
  const mapped = UNICODE_TO_CP437[chStr];
  if (mapped !== undefined && glyphs[String(mapped)]) return mapped;
  if (glyphs[String(raw)]) return raw;
  return mapped !== undefined ? mapped : raw;
}}

function layoutTypesetEm() {{
  const fIdx = Number(document.getElementById('tsFontSel').value || 0);
  const font = af4Fonts[fIdx] || af4Fonts[0];
  const text = document.getElementById('tsText').value || '';
  const useKern = document.getElementById('tsKern').checked;
  if (!font) return null;
  let cx = 0;
  let prev = null;
  const items = [];
  for (const chStr of text) {{
    const code = resolveAf4Code(font, chStr);
    if (useKern && prev !== null) {{
      const k = (font.kerning || {{}})[prev + ',' + code] || 0;
      cx += k / 10.0;
    }}
    if (code === 32) {{
      cx += (font.space_width || 300) / 10.0;
      prev = code;
      continue;
    }}
    const g = (font.glyphs || {{}})[String(code)];
    if (g && g.em) {{
      items.push({{ x: cx, d: g.em }});
      cx += (g.adv || font.space_width || 600) / 10.0;
    }} else {{
      cx += (font.space_width || 350) / 10.0;
    }}
    prev = code;
  }}
  return {{ font, items, width: Math.max(120, cx + 20) }};
}}

function renderTypesetPreview() {{
  const out = layoutTypesetEm();
  const svg = document.getElementById('typesetPreview');
  if (!out) return;
  const vw = Math.max(560, out.width + 24);
  svg.setAttribute('viewBox', `0 0 ${{vw.toFixed(0)}} 128`);
  const paths = out.items.map(it => `<g transform="translate(${{(12 + it.x).toFixed(1)}},6)"><path d="${{escHtml(it.d)}}" fill="${{escHtml(activeColor)}}44" stroke="${{escHtml(activeColor)}}" stroke-width="2.2" fill-rule="evenodd" /></g>`).join('');
  svg.innerHTML = `<rect width="${{vw.toFixed(0)}}" height="128" fill="#090d1a"/>${{paths}}`;
}}

function stampTypesetToCanvas() {{
  const out = layoutTypesetEm();
  if (!out || !out.items.length) return;
  pushUndo();
  const scale = Math.min(0.62, 480 / Math.max(100, out.width));
  const startX = 300 - (out.width * scale) * 0.5;
  for (const it of out.items) {{
    stamps.push(makeStamp(it.d, startX + (it.x + 50) * scale, 200, scale, 0, activeColor, true));
  }}
  selectedIdx = stamps.length - 1;
  renderStage();
  setStatus(`Typeset "${{document.getElementById('tsText').value}}" in ${{out.font.display_name}} onto canvas!`);
}}

function downloadBytes(bytes, filename, mime) {{
  const blob = new Blob([bytes], {{ type: mime }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}}

function exportSvg() {{
  const svg = document.getElementById('stage').outerHTML;
  downloadBytes(svg, 'zoe-artline-forge-canvas.svg', 'image/svg+xml');
  setStatus('Downloaded zoe-artline-forge-canvas.svg');
}}

async function exportArtifact(kind) {{
  const payload = {{
    stamps,
    toolbox_id: (TOOLBOXES[activeTb] || TOOLBOXES[0]).toolbox_id,
    palette_id: (PALETTES[activePal] || PALETTES[0]).palette_id,
    text: document.getElementById('tsText').value || '',
    font: (af4Fonts[Number(document.getElementById('tsFontSel').value || 0)] || {{}}).filename || '',
  }};
  if (kind === 'json') {{
    downloadBytes(JSON.stringify({{ stamps, ...payload }}, null, 2), 'zoe-artline-forge.json', 'application/json');
    setStatus('Downloaded zoe-artline-forge.json');
    return;
  }}
  try {{
    const res = await fetch('/api/forge/export', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ kind, payload }}),
    }});
    if (res.ok) {{
      const doc = await res.json();
      if (doc && doc.content_base64) {{
        const bin = Uint8Array.from(atob(doc.content_base64), c => c.charCodeAt(0));
        downloadBytes(bin, doc.filename, doc.mime_type || 'application/octet-stream');
        setStatus(`Exported ${{doc.filename}} (${{doc.bytes_len}} bytes · sha256=${{(doc.sha256 || '').slice(0, 12)}})`);
        return;
      }}
    }}
  }} catch (_err) {{
    // Offline fallback when opened directly from file://
  }}
  if (kind === 'zoetk') {{
    const tb = TOOLBOXES[activeTb] || TOOLBOXES[0];
    downloadBytes(JSON.stringify(tb, null, 2), `${{tb.toolbox_id}}.zoetk.json`, 'application/json');
    setStatus(`Offline fallback: exported ${{tb.toolbox_id}}.zoetk.json`);
  }} else {{
    exportSvg();
  }}
}}

function renderToolboxes() {{
  const tabs = TOOLBOXES.map((tb, i) => `
    <button class="${{(!show1990Tls && i===activeTb)?'active':''}}" onclick="show1990Tls=false;activeTb=${{i}};renderToolboxes();">${{escHtml(tb.title.split(' ')[0])}}</button>`);
  tabs.push(`<button class="${{show1990Tls?'active':''}}" style="border-color:#ff85b3;color:#ff85b3;" onclick="show1990Tls=true;renderToolboxes();">1990 .TLS (${{(VECS.tls_1990||[]).length}})</button>`);
  document.getElementById('tbTabs').innerHTML = tabs.join('');

  if (show1990Tls) {{
    document.getElementById('tbGrid').style.display = 'none';
    document.getElementById('tls1990Box').style.display = 'block';
    const arr = VECS.tls_1990 || [];
    const cur = arr[activeTlsIdx] || arr[0];
    document.getElementById('tbDesc').textContent = 'Read-only decoded 1990 CCPTK001 binary Artline 2.0 toolboxes & 32x28 icon bitmaps';
    document.getElementById('tlsTabs').innerHTML = arr.map((t, i) => `
      <button class="${{i===activeTlsIdx?'active':''}}" onclick="activeTlsIdx=${{i}};renderToolboxes();">${{escHtml(t.filename)}}</button>`).join('');
    if (cur) {{
      document.getElementById('tlsMeta').textContent = cur.filename + ' · magic=' + cur.magic + ' · ' + cur.tool_count + ' tools · width_hint=' + cur.panel_width_hint;
      const tools = cur.tools || (cur.tool_names || []).map(n => ({{ name: n, icon_svg_path: '' }}));
      document.getElementById('tlsPills').innerHTML = tools.map(t => {{
        const ico = t.icon_svg_path
          ? `<svg viewBox="0 0 32 28" width="18" height="16" style="flex-shrink:0;"><path d="${{escHtml(t.icon_svg_path)}}" fill="#5ce1e6" /></svg>`
          : '';
        return `<span class="tls-pill">${{ico}}<span>${{escHtml(t.name)}}</span></span>`;
      }}).join('');
    }}
    return;
  }}

  document.getElementById('tls1990Box').style.display = 'none';
  document.getElementById('tbGrid').style.display = 'grid';
  const tb = TOOLBOXES[activeTb];
  document.getElementById('tbDesc').textContent = tb.title + ' — ' + tb.description;
  const g = document.getElementById('tbGrid');
  g.style.gridTemplateColumns = `repeat(${{tb.columns}}, 1fr)`;
  g.innerHTML = tb.buttons.map(b => `
    <button class="tb-btn" style="border-color:${{escHtml(b.color_hex)}};color:${{escHtml(b.color_hex)}}" onclick="runTool('${{escJsAttr(b.tool_id)}}','${{escJsAttr(b.adc12_code)}}','${{escJsAttr(b.color_hex)}}','${{escJsAttr(b.label)}}')">
      <span style="font-size:15px">${{escHtml(b.wombat_glyph)}}</span><span>${{escHtml(b.label)}}</span>
    </button>`).join('');
}}

function renderPalettes() {{
  const tabs = PALETTES.map((p, i) => `
    <button class="${{(!show1990Col && i===activePal)?'active':''}}" onclick="show1990Col=false;activePal=${{i}};activeColor=PALETTES[${{i}}].swatches[0].hex_color;renderPalettes();renderVault();renderTypesetPreview();">${{escHtml(p.palette_id.replace('_',' '))}}</button>`);
  tabs.push(`<button class="${{show1990Col?'active':''}}" style="border-color:#52e5a8;color:#52e5a8;" onclick="show1990Col=true;renderPalettes();">1990 .COL (${{colPalettes.length}})</button>`);
  document.getElementById('palTabs').innerHTML = tabs.join('');
  document.getElementById('colSelectRow').style.display = show1990Col ? 'flex' : 'none';

  let swatches = [];
  if (show1990Col) {{
    const idx = Number(document.getElementById('colPalSel').value || 0);
    const cp = colPalettes[idx] || colPalettes[0];
    swatches = (cp && cp.swatches) || [];
  }} else {{
    swatches = PALETTES[activePal].swatches;
  }}
  document.getElementById('swatches').innerHTML = swatches.map(sw => `
    <div class="sw ${{sw.hex_color===activeColor?'sel':''}}" style="background:${{escHtml(sw.hex_color)}}" title="${{escHtml(sw.name)}} (${{escHtml(sw.hex_color)}})" onclick="activeColor='${{escJsAttr(sw.hex_color)}}';renderPalettes();renderVault();renderTypesetPreview();">
      ${{escHtml((sw.name || sw.hex_color).split(' ')[0])}}
    </div>`).join('');
}}

renderToolboxes();
renderPalettes();
renderVault();
renderTypesetPreview();
stampRadial();
</script>
</body>
</html>
"""


def render_artline_forge_html(archive_root: Path | None = None) -> bytes:
    """HTTP route renderer for /forge on the live Zoe-ELIZA :8765 Web Studio."""
    return build_interactive_artline_forge_html_str(archive_root).encode("utf-8")


def write_interactive_artline_forge_html(out_html: str | Path, archive_root: Path | None = None) -> Path:
    target = Path(out_html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_interactive_artline_forge_html_str(archive_root), encoding="utf-8")
    return target


__all__ = [
    "ARTLINE_FORGE_CONTRACT",
    "CONSTITUTIONAL_FLAGS",
    "STUDIO_PALETTES",
    "STUDIO_TOOLBOXES",
    "AF4Font",
    "AF4Glyph",
    "COLPalette",
    "COLSwatch",
    "PaletteSwatch",
    "SYFLibrary",
    "SYFSymbol",
    "TLSToolEntry",
    "TLSToolbox",
    "ToolboxButton",
    "ZoeToolboxSpec",
    "ZoeVectorPalette",
    "build_interactive_artline_forge_html_str",
    "build_synthetic_af4_bytes",
    "build_synthetic_col_bytes",
    "build_synthetic_gem_bytes",
    "build_synthetic_syf_bytes",
    "build_synthetic_tls_bytes",
    "clear_forge_cache",
    "contours_to_svg_path",
    "decode_af4_bytes",
    "decode_af4_font",
    "decode_ccp_contours",
    "decode_ccp_segments",
    "decode_col_bytes",
    "decode_col_file",
    "decode_syf_bytes",
    "decode_syf_library",
    "decode_tls_bytes",
    "decode_tls_file",
    "export_forge_artifact",
    "get_af4_font_payload",
    "get_forge_catalog",
    "inspect_gem_bytes",
    "inspect_gem_file",
    "render_af4_catalog_poster_png",
    "render_af4_specimen_png",
    "render_af4_typeset_png",
    "render_artline_forge_html",
    "render_syf_contact_sheet_png",
    "typeset_af4_text_layout",
    "typeset_af4_text_svg",
    "typeset_af4_text_to_artline_doc",
    "write_interactive_artline_forge_html",
]

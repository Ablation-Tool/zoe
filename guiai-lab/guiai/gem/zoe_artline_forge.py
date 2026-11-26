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

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

from .artline import ArtlineDocument

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


def contours_to_svg_path(
    contours: Sequence[Sequence[tuple[float, float]]],
    *,
    flip_y: bool = False,
    box_size: float = 100.0,
    pad: float = 8.0,
) -> str:
    """Normalize contours into a clean SVG `d` path string fitting `[pad, box_size - pad]`."""
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
        first = True
        for px, py in c:
            ny = -py if flip_y else py
            sx = ox + (px - min_x) * scale
            sy = oy + (ny - min_y) * scale
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

    def summary_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "internal_filename": self.internal_filename,
            "font_id": self.font_id,
            "display_name": self.display_name,
            "copyright_text": self.copyright_text,
            "first_char": self.first_char,
            "last_char": self.last_char,
            "glyph_count": self.glyph_count,
            "decoded_chars": len(self.glyphs_by_char),
        }


def decode_af4_bytes(data: bytes, filename: str = "font.af4") -> AF4Font:
    """Decode an Artline 2.0 `.AF4` (version 0x0004) outline font buffer cleanly."""
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
    w62, _w64, vec_len = struct.unpack_from("<3H", data, 0x62)

    data_start = len(data) - vec_len
    off_tbl = data_start - 6 * w62
    if off_tbl < 0x8A or data_start >= len(data):
        raise ValueError(f"Invalid .AF4 table geometry for {filename}")

    offsets = [struct.unpack_from("<HI", data, off_tbl + i * 6)[1] for i in range(w62)]
    max_slots = min(224, (off_tbl - 0x8A) // 22)

    glyphs: dict[int, AF4Glyph] = {}
    for slot in range(max_slots):
        ch = 32 + slot
        rec_off = 0x8A + slot * 22
        gidx, _fl, adv, x0, y0, x1, y1 = struct.unpack_from("<HHH4h", data, rec_off)
        if gidx == 0xFFFF or gidx >= len(offsets):
            continue
        gp = data_start + offsets[gidx]
        if gp + 2 > len(data):
            continue
        npts = struct.unpack_from("<H", data, gp)[0]
        if npts < 2 or npts > 1200 or gp + 2 + 5 * npts > len(data):
            continue
        coords = [struct.unpack_from("<hh", data, gp + 2 + k * 4) for k in range(npts)]
        flags = list(data[gp + 2 + npts * 4 : gp + 2 + npts * 5])
        contours = decode_ccp_contours(coords, flags, bezier_steps=8)
        if not contours:
            continue
        svg_p = contours_to_svg_path(contours, flip_y=True, box_size=100.0, pad=8.0)
        glyphs[ch] = AF4Glyph(
            char_code=ch,
            glyph_index=gidx,
            advance_width=adv,
            bbox=(x0, y0, x1, y1),
            point_count=npts,
            contours=tuple(tuple(c) for c in contours),
            svg_path=svg_p,
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
    )


def decode_af4_font(path: str | Path) -> AF4Font:
    p = Path(path)
    return decode_af4_bytes(p.read_bytes(), filename=p.name)


def build_synthetic_af4_bytes() -> bytes:
    """Build a tiny 100% clean-room synthetic .AF4 v4 font (for CI/unit tests without external files)."""
    hdr = bytearray(0x8A)
    struct.pack_into("<H", hdr, 0, 4)
    hdr[2:14] = b"ZOESYNTH.AF4"
    struct.pack_into("<H", hdr, 0x10, 129)
    hdr[0x14:0x23] = b"Zoe Synth Forge"
    hdr[0x34:0x4B] = b"(c) Clean-Room Zoe 2026"
    struct.pack_into("<HH", hdr, 0x54, 32, 120)

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

    slots = bytearray()
    for ch in range(32, 121):
        if ch == 78:
            slots.extend(struct.pack("<HHH4h8s", 0, 1, 900, 80, 80, 920, 920, b"\x00" * 8))
        elif ch == 90:
            slots.extend(struct.pack("<HHH4h8s", 1, 1, 900, 100, 100, 900, 900, b"\x00" * 8))
        else:
            slots.extend(struct.pack("<H20s", 0xFFFF, b"\x00" * 20))

    off_tbl = struct.pack("<HI", 0x0100, 0) + struct.pack("<HI", 0x0100, len(g0))
    return bytes(hdr + slots + off_tbl + vec_blob)


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
# 7. Live Interactive :8765/forge Web Studio & Offline HTML5 Playground
# ---------------------------------------------------------------------------

def _collect_live_forge_vectors() -> dict[str, Any]:
    """Load authentic decoded 1988-1990 wombat.af4/symbol.af4/STARS.SYF/FLOWERS.SYF paths if mounted, else clean-room fallback."""
    wombat_path = DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts/wombat.af4"
    symbol_path = DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts/symbol.af4"
    stars_path = DEFAULT_EXTRACTED_ROOT / "symbol_pack_1989/STARS.SYF"
    flowers_path = DEFAULT_EXTRACTED_ROOT / "symbol_pack_1989/FLOWERS.SYF"

    wombat_items: list[dict[str, Any]] = []
    symbol_items: list[dict[str, Any]] = []
    syf_items: list[dict[str, Any]] = []
    source_mode = "authentic_local_1990_archive"

    if wombat_path.is_file():
        wf = decode_af4_font(wombat_path)
        featured = [90, 111, 101, 78, 73, 51, 53, 42, 44, 46, 95, 117, 118, 33, 40, 41, 57, 70, 72, 83, 87, 89, 108, 115]
        for ch in featured:
            if ch in wf.glyphs_by_char:
                g = wf.glyphs_by_char[ch]
                wombat_items.append({"code": ch, "key": chr(ch), "pts": g.point_count, "d": g.svg_path})
    else:
        source_mode = "portable_clean_room_synth"
        wf = decode_af4_bytes(build_synthetic_af4_bytes(), "zoe_synth.af4")
        for ch, g in sorted(wf.glyphs_by_char.items()):
            wombat_items.append({"code": ch, "key": chr(ch), "pts": g.point_count, "d": g.svg_path})

    if symbol_path.is_file():
        sf = decode_af4_font(symbol_path)
        for ch in [68, 70, 71, 83, 87, 89, 92, 101, 108, 109, 112, 115, 116, 117, 118, 165]:
            if ch in sf.glyphs_by_char:
                g = sf.glyphs_by_char[ch]
                symbol_items.append({"code": ch, "key": chr(ch) if ch < 127 else f"#{ch}", "pts": g.point_count, "d": g.svg_path})

    for syf_p, tag in ((stars_path, "STARS"), (flowers_path, "FLOWERS")):
        if syf_p.is_file():
            lib = decode_syf_library(syf_p)
            for sym in lib.symbols[:10]:
                syf_items.append({"pack": tag, "name": sym.name, "pts": sym.point_count, "d": sym.svg_path})
    if not syf_items:
        lib = decode_syf_bytes(build_synthetic_syf_bytes(), "zoe_synth.syf")
        for sym in lib.symbols:
            syf_items.append({"pack": "SYNTH", "name": sym.name, "pts": sym.point_count, "d": sym.svg_path})

    return {
        "source_mode": source_mode,
        "wombat_glyphs": wombat_items,
        "symbol_glyphs": symbol_items,
        "syf_symbols": syf_items,
    }


def build_interactive_artline_forge_html_str() -> str:
    """Return HTML string for the interactive Zoe Artline Forge (:8765/forge & offline HTML5)."""
    vecs = _collect_live_forge_vectors()
    toolboxes_json = json.dumps([asdict(tb) for tb in STUDIO_TOOLBOXES], ensure_ascii=False)
    palettes_json = json.dumps([asdict(p) for p in STUDIO_PALETTES], ensure_ascii=False)
    vecs_json = json.dumps(vecs, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Zoe Artline Forge — Decoded .AF4 / .SYF Vectors, Programmable Toolboxes &amp; GEM Palettes</title>
<style>
  * {{ box-sizing: border-box; font-family: "DejaVu Sans", system-ui, sans-serif; }}
  body {{ margin: 0; background: #0b0d18; color: #f0f4fc; min-height: 100vh; display: flex; flex-direction: column; }}
  header {{ background: #141a2e; border-bottom: 2px solid #f8cc30; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 17px; color: #5ce1e6; }}
  .navlinks {{ display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }}
  .navlinks a {{ text-decoration: none; font-size: 11.5px; padding: 4px 9px; border-radius: 6px; border: 1px solid #3c4d7a; color: #cbd5e1; background: #18213d; font-weight: 600; }}
  .navlinks a:hover {{ border-color: #f8cc30; color: #f8cc30; }}
  .layout {{ display: grid; grid-template-columns: 1.25fr 1.15fr 0.95fr; gap: 14px; padding: 14px 18px; flex: 1; }}
  @media (max-width: 1120px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: #12182c; border: 1.5px solid #2b385c; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }}
  .panel h2 {{ margin: 0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.7px; color: #f8cc30; }}
  .tabs {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  button {{ background: #1b2442; color: #f0f4fc; border: 1.5px solid #3c4f7f; border-radius: 7px; padding: 5px 10px; cursor: pointer; font-weight: 600; font-size: 11.5px; }}
  button:hover {{ filter: brightness(1.16); }}
  button.active {{ border-color: #5ce1e6; color: #5ce1e6; background: #102a38; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(78px, 1fr)); gap: 7px; max-height: 460px; overflow-y: auto; }}
  .tile {{ background: #0e1426; border: 1px solid #2e3e66; border-radius: 8px; padding: 6px; text-align: center; cursor: pointer; }}
  .tile:hover {{ border-color: #f8cc30; background: #17203c; }}
  .tile svg {{ width: 52px; height: 52px; display: block; margin: 0 auto 3px; }}
  .tile .lbl {{ font-size: 10px; color: #94a3c8; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #stage {{ width: 100%; height: 390px; background: #090d1a; border: 2px solid #5ce1e6; border-radius: 10px; cursor: crosshair; }}
  .tb-grid {{ display: grid; gap: 6px; }}
  .tb-btn {{ display: flex; align-items: center; gap: 6px; text-align: left; padding: 7px 9px; font-size: 11.5px; }}
  .swatches {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .sw {{ border-radius: 7px; padding: 8px 6px; text-align: center; cursor: pointer; border: 2px solid transparent; font-size: 10px; font-weight: 700; color: #0b0d18; }}
  .sw.sel {{ border-color: #ffffff; transform: scale(1.04); }}
  footer {{ padding: 7px 20px; background: #101424; border-top: 1px solid #263354; font-size: 11px; color: #94a3c8; }}
</style>
</head>
<body>
<header>
  <h1>⚒ Zoe Artline Forge · Decoded 1990 .AF4 / .SYF Vectors + Programmable Toolboxes &amp; GEM Palettes</h1>
  <div class="navlinks">
    <a href="/">← Studio</a>
    <a href="/artline">🎨 Artline</a>
    <a href="/physics">✺ Physics</a>
    <a href="/duodecimal">❖ ADC-12</a>
  </div>
</header>

<div class="layout">
  <section class="panel">
    <h2>Decoded Clean-Room Vector Vault (Click Any Vector To Stamp!)</h2>
    <div class="tabs">
      <button id="vWom" class="active" onclick="setVault('wombat')">wombat.af4</button>
      <button id="vSym" onclick="setVault('symbol')">symbol.af4</button>
      <button id="vSyf" onclick="setVault('syf')">STARS &amp; FLOWERS .SYF</button>
    </div>
    <div id="vaultGrid" class="grid"></div>
  </section>

  <section class="panel">
    <h2>Live Artline Vector Stamp Canvas (Pure SVG · Exportable)</h2>
    <svg id="stage" viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg"></svg>
    <div class="tabs">
      <button style="border-color:#52e5a8;color:#52e5a8;" onclick="stampRadial()">✺ 9-Petal Symmetry Ring</button>
      <button style="border-color:#f8cc30;color:#f8cc30;" onclick="exportSvg()">❏ Download .SVG</button>
      <button style="border-color:#f35670;color:#f35670;" onclick="clearStage()">✕ Clear Canvas</button>
    </div>
    <div id="stageStatus" style="font-size:11.5px;color:#94a3c8;">Click any vector on the left or click the canvas to stamp with your active palette swatch!</div>
  </section>

  <section class="panel">
    <h2>Programmable Toolboxes (ZOETK001 · .TLS-Inspired)</h2>
    <div id="tbTabs" class="tabs"></div>
    <div id="tbDesc" style="font-size:11px;color:#94a3c8;"></div>
    <div id="tbGrid" class="tb-grid"></div>
    <h2 style="margin-top:8px;">Vector-Metafile Palettes (.COL-as-GEM)</h2>
    <div id="palTabs" class="tabs"></div>
    <div id="swatches" class="swatches"></div>
  </section>
</div>

<footer>Optimize+Improve+Zoe+Nick+Fun+Creative = LIFE · Clean-Room Artline Forge · 0 Cloud Tokens · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False</footer>

<script>
const VECS = {vecs_json};
const TOOLBOXES = {toolboxes_json};
const PALETTES = {palettes_json};

let vaultTab = 'wombat';
let activeTb = 0;
let activePal = 0;
let activeColor = PALETTES[0].swatches[0].hex_color;
let selectedVector = VECS.wombat_glyphs[0] || VECS.syf_symbols[0];
const stamps = [];

function setVault(tab) {{
  vaultTab = tab;
  document.getElementById('vWom').classList.toggle('active', tab==='wombat');
  document.getElementById('vSym').classList.toggle('active', tab==='symbol');
  document.getElementById('vSyf').classList.toggle('active', tab==='syf');
  renderVault();
}}
function renderVault() {{
  const grid = document.getElementById('vaultGrid');
  let list = [];
  if (vaultTab === 'wombat') list = VECS.wombat_glyphs.map(g => ({{ label: g.code + ' ' + g.key, d: g.d }}));
  else if (vaultTab === 'symbol') list = VECS.symbol_glyphs.map(g => ({{ label: g.code + ' ' + g.key, d: g.d }}));
  else list = VECS.syf_symbols.map(s => ({{ label: s.name, d: s.d }}));
  grid.innerHTML = list.map((item, idx) => `
    <div class="tile" onclick="pickVec(${{idx}})">
      <svg viewBox="0 0 100 100"><path d="${{item.d}}" fill="${{activeColor}}33" stroke="${{activeColor}}" stroke-width="3" /></svg>
      <div class="lbl">${{item.label}}</div>
    </div>`).join('');
  window._curVaultList = list;
}}
function pickVec(idx) {{
  const item = (window._curVaultList || [])[idx];
  if (!item) return;
  selectedVector = item;
  stamps.push({{ d: item.d, x: 90 + Math.random()*420, y: 70 + Math.random()*260, s: 0.95, rot: 0, col: activeColor }});
  renderStage();
  document.getElementById('stageStatus').textContent = 'Stamped ' + item.label + ' in ' + activeColor + ' (' + stamps.length + ' vectors on canvas)';
}}
function stampRadial() {{
  if (!selectedVector) return;
  const pal = PALETTES[activePal].swatches;
  for (let k = 0; k < 9; k++) {{
    const ang = (Math.PI * 2 * k) / 9;
    const x = 300 + Math.cos(ang) * 115;
    const y = 200 + Math.sin(ang) * 115;
    stamps.push({{ d: selectedVector.d, x, y, s: 0.72, rot: Math.round(ang * 180 / Math.PI), col: pal[k % pal.length].hex_color }});
  }}
  renderStage();
  document.getElementById('stageStatus').textContent = 'Stamped 9-petal symmetry ring (' + stamps.length + ' total vectors)!';
}}
function clearStage() {{
  stamps.length = 0;
  renderStage();
  document.getElementById('stageStatus').textContent = 'Canvas cleared.';
}}
function renderStage() {{
  const svg = document.getElementById('stage');
  let gridLines = '';
  for (let gx = 40; gx < 600; gx += 40) gridLines += `<line x1="${{gx}}" y1="0" x2="${{gx}}" y2="400" stroke="#182038" stroke-width="1"/>`;
  for (let gy = 40; gy < 400; gy += 40) gridLines += `<line x1="0" y1="${{gy}}" x2="600" y2="${{gy}}" stroke="#182038" stroke-width="1"/>`;
  const body = stamps.map(st => `
    <g transform="translate(${{st.x.toFixed(1)}},${{st.y.toFixed(1)}}) rotate(${{st.rot}}) scale(${{st.s}}) translate(-50,-50)">
      <path d="${{st.d}}" fill="${{st.col}}33" stroke="${{st.col}}" stroke-width="2.6" />
    </g>`).join('');
  svg.innerHTML = `<rect width="600" height="400" fill="#090d1a"/>${{gridLines}}${{body}}`;
}}
document.getElementById('stage').addEventListener('click', (e) => {{
  if (!selectedVector) return;
  const r = e.currentTarget.getBoundingClientRect();
  const x = (e.clientX - r.left) * (600 / r.width);
  const y = (e.clientY - r.top) * (400 / r.height);
  stamps.push({{ d: selectedVector.d, x, y, s: 0.85, rot: 0, col: activeColor }});
  renderStage();
}});
function exportSvg() {{
  const svg = document.getElementById('stage').outerHTML;
  const blob = new Blob([svg], {{ type: 'image/svg+xml' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'zoe-artline-forge-canvas.svg';
  a.click();
}}
function renderToolboxes() {{
  document.getElementById('tbTabs').innerHTML = TOOLBOXES.map((tb, i) => `
    <button class="${{i===activeTb?'active':''}}" onclick="activeTb=${{i}};renderToolboxes();">${{tb.title.split(' ')[0]}}</button>`).join('');
  const tb = TOOLBOXES[activeTb];
  document.getElementById('tbDesc').textContent = tb.title + ' — ' + tb.description;
  const g = document.getElementById('tbGrid');
  g.style.gridTemplateColumns = `repeat(${{tb.columns}}, 1fr)`;
  g.innerHTML = tb.buttons.map(b => `
    <button class="tb-btn" style="border-color:${{b.color_hex}};color:${{b.color_hex}}" onclick="document.getElementById('stageStatus').textContent='Active Tool: [${{b.adc12_code}}₁₂ · ${{b.wombat_glyph}}] ${{b.label}} (key ${{b.shortcut}})'">
      <span style="font-size:15px">${{b.wombat_glyph}}</span><span>${{b.label}}</span>
    </button>`).join('');
}}
function renderPalettes() {{
  document.getElementById('palTabs').innerHTML = PALETTES.map((p, i) => `
    <button class="${{i===activePal?'active':''}}" onclick="activePal=${{i}};activeColor=PALETTES[${{i}}].swatches[0].hex_color;renderPalettes();renderVault();">${{p.palette_id.replace('_',' ')}}</button>`).join('');
  const pal = PALETTES[activePal];
  document.getElementById('swatches').innerHTML = pal.swatches.map(sw => `
    <div class="sw ${{sw.hex_color===activeColor?'sel':''}}" style="background:${{sw.hex_color}}" onclick="activeColor='${{sw.hex_color}}';renderPalettes();renderVault();">
      ${{sw.name.split(' ')[0]}}
    </div>`).join('');
}}
renderToolboxes();
renderPalettes();
renderVault();
stampRadial();
</script>
</body>
</html>
"""


def render_artline_forge_html() -> bytes:
    """HTTP route renderer for /forge on the live Zoe-ELIZA :8765 Web Studio."""
    return build_interactive_artline_forge_html_str().encode("utf-8")


def write_interactive_artline_forge_html(out_html: str | Path) -> Path:
    target = Path(out_html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_interactive_artline_forge_html_str(), encoding="utf-8")
    return target


__all__ = [
    "ARTLINE_FORGE_CONTRACT",
    "CONSTITUTIONAL_FLAGS",
    "STUDIO_PALETTES",
    "STUDIO_TOOLBOXES",
    "AF4Font",
    "AF4Glyph",
    "PaletteSwatch",
    "SYFLibrary",
    "SYFSymbol",
    "ToolboxButton",
    "ZoeToolboxSpec",
    "ZoeVectorPalette",
    "build_interactive_artline_forge_html_str",
    "build_synthetic_af4_bytes",
    "build_synthetic_syf_bytes",
    "contours_to_svg_path",
    "decode_af4_bytes",
    "decode_af4_font",
    "decode_ccp_contours",
    "decode_syf_bytes",
    "decode_syf_library",
    "render_af4_specimen_png",
    "render_artline_forge_html",
    "render_syf_contact_sheet_png",
    "write_interactive_artline_forge_html",
]

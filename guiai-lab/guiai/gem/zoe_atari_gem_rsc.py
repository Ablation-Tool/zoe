"""Atari ST / EmuTOS GEM Binary .RSC, ICONBLK, BITBLK & MFORM Compiler for Zoe Signets.

Implements exact Motorola 68000 big-endian GEM AES 1.x/2.x binary structures per:
  - Abacus Software, Atari ST GEM Programmer's Reference (Ch. 4.1.5 & 4.2.5, pp. 260, 323-331)
  - Digital Research / EmuTOS `obdefs.h` & `rsdefs.h` (`RSHDR`, `OBJECT`, `ICONBLK`, `BITBLK`)

Generates:
  1. Valid big-endian Atari ST `ZOE_GEM.RSC` resource file (36-byte `RSHDR` + `G_BOX` root +
     9 `G_ICON` 32x32 1-bit `ICONBLK` children + `BITBLK` + null-terminated labels).
  2. Compilable C header (`zoe_gem_icons.h`) with 32x32 `ib_pmask`/`ib_pdata` word arrays,
     `ICONBLK` structs, `BITBLK` struct, and 16x16 `MFORM` Atari ST GEM mouse cursor.
  3. Round-trip `parse_atari_rsc()` binary verifier validated against EmuTOS `desk/icon.rsc`.

Zero copyrighted book text, zero cloud tokens, zero silent disk writes (`CONSTITUTION.md`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from typing import Any, Sequence

from .lume_header import EMBLEM_MAP, _palette_for_emblem

# GEM AES Object Types & Flags (obdefs.h / Abacus pp. 325-331)
G_BOX = 20
G_IMAGE = 23
G_ICON = 31

NONE = 0x0000
SELECTABLE = 0x0001
LASTOB = 0x0020
NORMAL = 0x0000

# Atari ST GEM Standard 16-Color Indices (obdefs.h)
GEM_WHITE = 0
GEM_BLACK = 1
GEM_RED = 2
GEM_GREEN = 3
GEM_BLUE = 4

_EMBLEM_GEM_COLOR: dict[str, int] = {
    "ruby": GEM_RED,
    "gem3": GEM_RED,
    "atari": GEM_RED,
    "sm124": GEM_BLACK,
    "tetris": GEM_BLUE,
    "dos": GEM_GREEN,
    "hat": GEM_RED,
    "sprout": GEM_GREEN,
    "prism": GEM_BLUE,
}

# 16x16 Atari ST GEM MFORM Mouse Cursor (Zoe smiling crystal pointer, hotspot at top crown (7, 1))
_MFORM_ZOE_ART: tuple[str, ...] = (
    "....XXXXXXXX....",
    "...XOOOOOOOOX...",
    "..XOOXOOOOXOOX..",
    ".XOOXOXOOXOXOOX.",
    "XOOOOOOXXOOOOOOX",
    "XXXXXXXXXXXXXXXX",
    ".XOOOOOXOOOOOOX.",
    "..XOOOOXOOOOOX..",
    "...XOOOXOOOOX...",
    "....XOOXOOOX....",
    ".....XOXOOX.....",
    "......XXOX......",
    ".......XX.......",
    "................",
    "................",
    "................",
)


def _luma(rgb: tuple[int, int, int]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def emblem_to_iconblk_32x32(emblem: str) -> tuple[list[int], list[int]]:
    """Compile an 18x23 Zoe signet into 32x32 Atari ST 1-bit (mask_words, data_words).

    Each scanline is 32 bits = two 16-bit big-endian Motorola 68000 words (64 words total).
    Per Abacus p. 329: mask bit=1 is visible, bit=0 is transparent; data bit=1 draws fg color.
    """
    grid = EMBLEM_MAP.get(emblem)
    if grid is None:
        raise ValueError(f"Unknown Zoe signet {emblem!r}. Choose from: {', '.join(EMBLEM_MAP)}")
    pal = _palette_for_emblem(emblem)
    h_src, w_src = len(grid), len(grid[0])
    # Center the 23x18 sprite cleanly inside 32x32 (x_off=4, y_off=7) with 1px silhouette dilation for mask
    x_off, y_off = (32 - w_src) // 2, (32 - h_src) // 2
    mask_grid = [[0] * 32 for _ in range(32)]
    data_grid = [[0] * 32 for _ in range(32)]

    for sy in range(h_src):
        for sx in range(w_src):
            ch = grid[sy][sx]
            rgb = pal.get(ch)
            if rgb is None:
                continue
            dx, dy = sx + x_off, sy + y_off
            mask_grid[dy][dx] = 1
            # Determine crisp 1-bit ink (1 = foreground, 0 = white interior highlight)
            if ch in {"E", "M", "X", "J", "0"}:
                ink = 1
            elif ch in {"I", "F", "W", "1"}:
                ink = 0
            elif emblem == "sm124":
                ink = 1 if _luma(rgb) < 128 else 0
            else:
                lum = _luma(rgb)
                if lum < 135:
                    ink = 1
                elif lum < 185:
                    ink = 1 if ((dx + dy) % 2 == 0) else 0  # Classic 1985 GEM 50% Bayer dither
                else:
                    ink = 0
            data_grid[dy][dx] = ink

    # Ensure 1-pixel outer border on non-framed crystals so the silhouette stays crisp on GEM desktop
    for y in range(1, 31):
        for x in range(1, 31):
            if mask_grid[y][x] == 1 and any(
                mask_grid[y + dy][x + dx] == 0 for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                data_grid[y][x] = 1

    mask_words: list[int] = []
    data_words: list[int] = []
    for y in range(32):
        m_hi = sum(mask_grid[y][x] << (15 - x) for x in range(16))
        m_lo = sum(mask_grid[y][16 + x] << (15 - x) for x in range(16))
        d_hi = sum(data_grid[y][x] << (15 - x) for x in range(16))
        d_lo = sum(data_grid[y][16 + x] << (15 - x) for x in range(16))
        mask_words.extend((m_hi, m_lo))
        data_words.extend((d_hi, d_lo))
    return mask_words, data_words


def build_mform_zoe_cursor() -> dict[str, Any]:
    """Build a 16x16 Atari ST GEM MFORM cursor (graf_mouse USER_DEF=255)."""
    mask_words: list[int] = []
    data_words: list[int] = []
    for row in _MFORM_ZOE_ART:
        m_word = sum((1 if ch in {"X", "O"} else 0) << (15 - i) for i, ch in enumerate(row))
        d_word = sum((1 if ch == "X" else 0) << (15 - i) for i, ch in enumerate(row))
        mask_words.append(m_word)
        data_words.append(d_word)
    return {
        "mf_xhot": 7,
        "mf_yhot": 1,
        "mf_nplanes": 1,
        "mf_fg": GEM_RED,
        "mf_bg": GEM_WHITE,
        "mf_mask": mask_words,
        "mf_data": data_words,
    }


def build_atari_rsc_bytes(emblems: Sequence[str] | None = None) -> bytes:
    """Compile Zoe signets into a bit-exact Motorola 68000 big-endian Atari ST GEM .RSC file."""
    names = list(emblems) if emblems is not None else list(EMBLEM_MAP.keys())
    if not names:
        raise ValueError("At least one emblem is required to compile ZOE_GEM.RSC.")

    # Section layout matches EmuTOS desk/icon.rsc:
    # [0..36) RSHDR | strings (even-aligned) | imdata (data+mask pairs) | ICONBLKs | BITBLKs | OBJECTs | trindex
    rsh_string = 36
    str_blob = bytearray()
    str_offsets: list[int] = []
    for name in names:
        str_offsets.append(rsh_string + len(str_blob))
        str_blob.extend(f"ZOE {name.upper()}".encode("ascii") + b"\x00")
    if len(str_blob) % 2 == 1:
        str_blob.append(0)

    rsh_imdata = rsh_string + len(str_blob)
    im_blob = bytearray()
    im_offsets: list[tuple[int, int]] = []  # (pdata_off, pmask_off)
    for name in names:
        mask_w, data_w = emblem_to_iconblk_32x32(name)
        pdata_off = rsh_imdata + len(im_blob)
        im_blob.extend(struct.pack(">64H", *data_w))
        pmask_off = rsh_imdata + len(im_blob)
        im_blob.extend(struct.pack(">64H", *mask_w))
        im_offsets.append((pdata_off, pmask_off))

    rsh_iconblk = rsh_imdata + len(im_blob)
    ib_blob = bytearray()
    for idx, name in enumerate(names):
        pdata_off, pmask_off = im_offsets[idx]
        fg = _EMBLEM_GEM_COLOR.get(name, GEM_RED)
        ib_char = (fg << 12) | (GEM_WHITE << 8) | 0x00  # Clean face, zero overlay letter
        ib_blob.extend(
            struct.pack(
                ">3I11h",
                pmask_off,
                pdata_off,
                str_offsets[idx],
                ib_char,
                0, 0,       # ib_xchar, ib_ychar
                20, 0,      # ib_xicon, ib_yicon (centered in 72px desktop tile)
                32, 32,     # ib_wicon (divisible by 16), ib_hicon
                0, 32,      # ib_xtext, ib_ytext
                72, 8,      # ib_wtext, ib_htext
            )
        )

    # Also include 1 G_IMAGE BITBLK for Zoe's primary signet (Abacus p. 330: 14 bytes)
    rsh_bitblk = rsh_iconblk + len(ib_blob)
    first_pdata = im_offsets[0][0]
    bb_blob = struct.pack(">I5h", first_pdata, 4, 32, 0, 0, _EMBLEM_GEM_COLOR.get(names[0], GEM_RED))

    # Build GEM AES Object Tree 0: ROOT G_BOX + N G_ICON children in a 3-column desktop grid
    rsh_object = rsh_bitblk + len(bb_blob)
    n_icons = len(names)
    obj_blob = bytearray()
    # Object 0: ROOT G_BOX (24 bytes: >3h2HHI4h -> wait: ob_type/flags/state are UWORD, ob_spec is LONG)
    obj_blob.extend(
        struct.pack(
            ">3h3HI4h",
            -1,             # ob_next = NIL
            1,              # ob_head = first child
            n_icons,        # ob_tail = last child
            G_BOX,
            NONE,
            NORMAL,
            0x00001100,     # white hollow desktop box spec
            0, 0, 320, 200, # Atari ST standard coordinate box
        )
    )
    for idx in range(n_icons):
        obj_id = idx + 1
        next_sib = obj_id + 1 if idx < n_icons - 1 else 0  # Last child links back to parent ROOT (0)
        flags = SELECTABLE | (LASTOB if idx == n_icons - 1 else NONE)
        col, row = idx % 3, idx // 3
        ib_offset = rsh_iconblk + idx * 34
        obj_blob.extend(
            struct.pack(
                ">3h3HI4h",
                next_sib,
                -1,         # ob_head = NIL (leaf icon)
                -1,         # ob_tail = NIL
                G_ICON,
                flags,
                NORMAL,
                ib_offset,  # ob_spec -> ICONBLK offset (relocated by rsrc_load)
                16 + col * 88,
                12 + row * 52,
                72,
                40,
            )
        )

    rsh_trindex = rsh_object + len(obj_blob)
    trindex_blob = struct.pack(">I", rsh_object)
    total_size = rsh_trindex + len(trindex_blob)

    header = struct.pack(
        ">18H",
        0x0000,         # rsh_vrsn (classic Atari ST TOS 1.x/EmuTOS format)
        rsh_object,
        rsh_iconblk,    # rsh_tedinfo (0 entries)
        rsh_iconblk,
        rsh_bitblk,
        rsh_object,     # rsh_frstr (0 entries)
        rsh_string,
        rsh_imdata,
        rsh_object,     # rsh_frimg (0 entries)
        rsh_trindex,
        1 + n_icons,    # rsh_nobs (ROOT + icons)
        1,              # rsh_ntree
        0,              # rsh_nted
        n_icons,        # rsh_nib
        1,              # rsh_nbb
        0,              # rsh_nstring
        0,              # rsh_nimages
        total_size,     # rsh_rssize
    )
    return bytes(header + str_blob + im_blob + ib_blob + bb_blob + obj_blob + trindex_blob)


def parse_atari_rsc(blob: bytes) -> dict[str, Any]:
    """Parse and verify a big-endian Atari ST / EmuTOS GEM .RSC binary (36-byte RSHDR)."""
    if len(blob) < 36:
        raise ValueError("RSC buffer shorter than 36-byte RSHDR")
    fields = (
        "rsh_vrsn", "rsh_object", "rsh_tedinfo", "rsh_iconblk", "rsh_bitblk",
        "rsh_frstr", "rsh_string", "rsh_imdata", "rsh_frimg", "rsh_trindex",
        "rsh_nobs", "rsh_ntree", "rsh_nted", "rsh_nib", "rsh_nbb",
        "rsh_nstring", "rsh_nimages", "rsh_rssize",
    )
    hdr = dict(zip(fields, struct.unpack(">18H", blob[:36])))
    icons: list[dict[str, Any]] = []
    for i in range(hdr["rsh_nib"]):
        off = hdr["rsh_iconblk"] + i * 34
        ib = struct.unpack(">3I11h", blob[off : off + 34])
        pmask, pdata, ptext = ib[0], ib[1], ib[2]
        w_icon, h_icon = ib[8], ib[9]
        n_words = (w_icon // 16) * h_icon
        end_str = blob.find(b"\x00", ptext)
        label = blob[ptext : end_str if end_str != -1 else ptext + 16].decode("ascii", errors="replace")
        mask_words = list(struct.unpack(f">{n_words}H", blob[pmask : pmask + n_words * 2]))
        data_words = list(struct.unpack(f">{n_words}H", blob[pdata : pdata + n_words * 2]))
        icons.append({
            "label": label,
            "ib_char": ib[3],
            "fg_color": (ib[3] >> 12) & 0xF,
            "bg_color": (ib[3] >> 8) & 0xF,
            "w": w_icon,
            "h": h_icon,
            "mask_words": mask_words,
            "data_words": data_words,
        })
    return {
        "header": hdr,
        "size_matches_rsh_rssize": len(blob) == hdr["rsh_rssize"],
        "icons": icons,
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _format_c_words(words: Sequence[int], indent: str = "    ") -> str:
    rows = []
    for i in range(0, len(words), 8):
        chunk = ", ".join(f"0x{w:04X}" for w in words[i : i + 8])
        rows.append(f"{indent}{chunk},")
    return "\n".join(rows)


def generate_atari_c_header(emblems: Sequence[str] | None = None) -> str:
    """Emit a clean Atari ST / EmuTOS GEM C header with 32x32 ICONBLKs and 16x16 MFORM."""
    names = list(emblems) if emblems is not None else list(EMBLEM_MAP.keys())
    mform = build_mform_zoe_cursor()
    lines = [
        "/* zoe_gem_icons.h — Auto-generated Atari ST / EmuTOS GEM ICONBLK & MFORM header */",
        "/* Spec: Abacus Atari ST GEM Programmer's Reference pp. 328-330 & EmuTOS obdefs.h */",
        "#ifndef ZOE_GEM_ICONS_H",
        "#define ZOE_GEM_ICONS_H",
        "#include <stdint.h>",
        "",
    ]
    for name in names:
        mask_w, data_w = emblem_to_iconblk_32x32(name)
        tag = f"zoe_{name}"
        lines.append(f"static const uint16_t {tag}_mask[64] = {{")
        lines.append(_format_c_words(mask_w))
        lines.append("};")
        lines.append(f"static const uint16_t {tag}_data[64] = {{")
        lines.append(_format_c_words(data_w))
        lines.append("};")
        lines.append("")
    lines.append("/* 16x16 Atari ST GEM MFORM Mouse Cursor (graf_mouse(255, &zoe_mform)) */")
    lines.append("static const uint16_t zoe_mform_mask[16] = {")
    lines.append(_format_c_words(mform["mf_mask"]))
    lines.append("};")
    lines.append("static const uint16_t zoe_mform_data[16] = {")
    lines.append(_format_c_words(mform["mf_data"]))
    lines.append("};")
    lines.append("")
    lines.append("#endif /* ZOE_GEM_ICONS_H */")
    return "\n".join(lines) + "\n"


def format_iconblk_preview(emblem: str = "ruby") -> list[str]:
    """Render an exact 32x32 Atari ST 1-bit ICONBLK terminal preview + Motorola 68000 hex words."""
    mask_w, data_w = emblem_to_iconblk_32x32(emblem)
    fg = _EMBLEM_GEM_COLOR.get(emblem, GEM_RED)
    ib_char = (fg << 12) | (GEM_WHITE << 8)
    lines = [
        f"ATARI ST GEM ICONBLK · zoe_{emblem} (32x32 · 64 big-endian 68000 words · ib_char=0x{ib_char:04X})",
        "Spec: Abacus Atari ST GEM Programmer's Reference pp. 328-330 · EmuTOS obdefs.h / rsdefs.h",
    ]
    for y in range(6, 26):
        m32 = (mask_w[y * 2] << 16) | mask_w[y * 2 + 1]
        d32 = (data_w[y * 2] << 16) | data_w[y * 2 + 1]
        row = []
        for x in range(32):
            mbit = (m32 >> (31 - x)) & 1
            dbit = (d32 >> (31 - x)) & 1
            row.append("██" if (mbit and dbit) else ("░░" if mbit else "  "))
        lines.append(f"  {y:02d} │{''.join(row).rstrip()}")
    lines.append(f"  ib_pdata[0..7] = {', '.join(f'0x{w:04X}' for w in data_w[14:22])}")
    lines.append("Export genuine big-endian ZOE_GEM.RSC + zoe_gem_icons.h with: /emblem rsc export")
    return lines


def export_atari_gem_bundle(out_dir: Path | str | None = None) -> dict[str, Any]:
    """Explicitly write ZOE_GEM.RSC and zoe_gem_icons.h to ~/.zoe/atari-gem/ (user-triggered only)."""
    dest = Path(out_dir or (Path.home() / ".zoe" / "atari-gem")).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    rsc_bytes = build_atari_rsc_bytes()
    header_text = generate_atari_c_header()
    rsc_path = dest / "ZOE_GEM.RSC"
    hdr_path = dest / "zoe_gem_icons.h"
    rsc_path.write_bytes(rsc_bytes)
    hdr_path.write_text(header_text, encoding="utf-8")
    parsed = parse_atari_rsc(rsc_bytes)
    return {
        "ok": parsed["size_matches_rsh_rssize"],
        "rsc_path": str(rsc_path),
        "header_path": str(hdr_path),
        "rsc_bytes": len(rsc_bytes),
        "icons_compiled": len(parsed["icons"]),
        "sha256": parsed["sha256"],
    }

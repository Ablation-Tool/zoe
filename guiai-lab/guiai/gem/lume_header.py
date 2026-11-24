"""Zoe GEM Signet & Retro-Firmware Emblem Catalog (18x23 TrueColor half-block sprites).

Includes Zoe's default ruby GEM plus retro-firmware variants inspired by Digital Research GEM 3.0,
Atari ST / EmuTOS 1-bit SM124 & 16-color MIDI Desktop, 1984 Tetris Tetromino geometry,
IBM PC MS-DOS P31 phosphor CRT, and Zoe's playful retro wizard hat.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import TextIO

APP_NAME = ""
APP_TAGLINE = ""
DEFAULT_DETAIL = ""

# 1. ruby (default): Exact smooth-edged silhouette & (◠◡◠) crown smile from Zoe App (zoe_emblem.xml)
ZOE_GEM_PIXELS: tuple[str, ...] = (
    ".....OOOOOOOOOOOOO.....",
    "....OHHHHHHHHHHHHHO....",
    "...ORRFFFFFFFFFFFDDO...",
    "..ORRFLWEWWWWWEWKFDDO..",
    ".ORRFLWEWEWWWEWEWKFDDO.",
    "OFFFFFFFFFFEFFFFFFFFFFO",
    ".OCCFQQQQQQFSSSSSSFBBO.",
    "..OCCFQQQQQFSSSSSFBBO..",
    "...OCCFQQQQFSSSSFBBO...",
    "....OCCFQQQFSSSFBBO....",
    ".....OCCFQQFSSFBBO.....",
    "......OCCFQFSFBBO......",
    ".......OCCFFFBBO.......",
    "........OCCFBBO........",
    ".........OCDBO.........",
    "..........ODO..........",
    "...........O...........",
    ".......................",
)

# 2. gem3: 1987 Digital Research GEM 3.0 red-on-white stepped crystal (inspired by gem3red.png)
ZOE_GEM3_PIXELS: tuple[str, ...] = (
    "XXXXXXXXXXXXXXXXXXXXXXX",
    "XIIIIIIIIIIIIIIIIIIIIIX",
    "XIIIIIXXXXXXXXXXXIIIIIX",
    "XIIIXXXXIIIIIIIXXXXIIIX",
    "XIIXXXIIIIIIIIIIIXXXIIX",
    "XIXXXIIIEIIIIIEIIIXXXIX",
    "XIXXXIIEIEIIIEIEIIXXXIX",
    "XIIXXXIIIIEEEIIIIXXXIIX",
    "XIIIXXXIIIIIIIIIXXXIIIX",
    "XIIIIXXXIIIIIIIXXXIIIIX",
    "XIIIIIXXXIIIIIXXXIIIIIX",
    "XIIIIIIXXXIIIXXXIIIIIIX",
    "XIIIIIIIXXXIXXXIIIIIIIX",
    "XIIIIIIIIXXXXXIIIIIIIIX",
    "XIIIIIIIIIXXXIIIIIIIIIX",
    "XIIIIIIIIIIXIIIIIIIIIIX",
    "XIIIIIIIIIIIIIIIIIIIIIX",
    "XXXXXXXXXXXXXXXXXXXXXXX",
)

# 3. atari: 1985 Atari ST / EmuTOS GEM Desktop (emerald TOS backdrop + MIDI gold pins + ruby gem)
ZOE_ATARI_PIXELS: tuple[str, ...] = (
    "AAAAAAAAAAAAAAAAAAAAAAA",
    "AYAAAMMMMMMMMMMMMMAAAYA",
    "AAAAMHHHHHHHHHHHHHMAAAA",
    "AAAMRRFFFFFFFFFFFDDMAAA",
    "AAMRRFLWEWWWWWEWKFDDMAA",
    "AMRRFLWEWEWWWEWEWKFDDMA",
    "AMFFFFFFFFFEFFFFFFFFFMA",
    "AAMCCFQQQQQFSSSSSFBBMAA",
    "AAAMCCFQQQQFSSSSFBBMAAA",
    "AAAAMCCFQQQFSSSFBBMAAAA",
    "AAAAAMCCFQQFSSFBBMAAAAA",
    "AAAAAAMCCFQFSFBBMAAAAAA",
    "AAAAAAAMCCFFFBBMAAAAAAA",
    "AAAAAAAAMCCFBBMAAAAAAAA",
    "AAAAAAAAAMCDBMAAAAAAAAA",
    "AAAAAAAAAAMDMMAAAAAAAAA",
    "AAAAAAAAAAAMAAAAAAAAAAA",
    "AAAAAAAAAAAAAAAAAAAAAAA",
)

# 4. sm124: Atari ST SM124 High-Res 1-Bit Monochrome GEM ICONBLK with classic 50% Bayer dither
ZOE_SM124_PIXELS: tuple[str, ...] = (
    ".....MMMMMMMMMMMMM.....",
    "....MIIIIIIIIIIIIIM....",
    "...MIIMMMMMMMMMMMIIM...",
    "..MIIMIIIMIIIIMIIIMIM..",
    ".MIIMIMIMIMIIIMIMIMIMM.",
    "MMMMMMMMMMMIMMMMMMMMMMM",
    ".MIMIIIIIIIIIMIMIMIMIM.",
    "..MIMIIIIIIIIMMIMIMIM..",
    "...MIMIIIIIIIMIMIMIM...",
    "....MIMIIIIIIMMIMIM....",
    ".....MIMIIIIIMIMIM.....",
    "......MIMIIIIMMIM......",
    ".......MIMIIIMIM.......",
    "........MIMIIMM........",
    ".........MIMIM.........",
    "..........MMM..........",
    "...........M...........",
    ".......................",
)

# 5. tetris: 1984 Electronika 60 / MS-DOS Tetris Tetromino Mosaic forming Zoe's exact diamond
ZOE_TETRIS_PIXELS: tuple[str, ...] = (
    ".....NNNNNNNNNNNNN.....",
    "....NNNNNNNNNNNNNNN....",
    "...VVVYYYYYYYYYYYOOO...",
    "..VVVVYYEYYYYYEYYOOOO..",
    ".VVVVYYEYEYYYEYEYYOOOO.",
    "VVVVVYYYYYYEYYYYYYOOOOO",
    ".UUUUUUUGGGGGGZZZZZZZZ.",
    "..UUUUUUGGGGGGZZZZZZZ..",
    "...UUUUUGGGGGGZZZZZZ...",
    "....UUUUGGGGGGZZZZZ....",
    ".....VVVGGGGGGZZZZ.....",
    "......VVNNNNNNZZZ......",
    ".......VNNNNNNZZ.......",
    "........YNNNNZZ........",
    ".........YYOOZ.........",
    "..........YOO..........",
    "...........O...........",
    ".......................",
)

# 6. dos: 1984 IBM PC MS-DOS P31 Green Phosphor CRT Firmware with crisp scanline facets
ZOE_DOS_PIXELS: tuple[str, ...] = (
    ".....1111111111111.....",
    "....122222222222221....",
    "...12211111111111331...",
    "..1221210111110121331..",
    ".122121010111010121331.",
    "11111111111011111111111",
    ".133122222214444441331.",
    "..1331222221444441331..",
    "...13312222144441331...",
    "....133122214441331....",
    ".....1331221441331.....",
    "......13312141331......",
    ".......133111331.......",
    "........1331331........",
    ".........13431.........",
    "..........141..........",
    "...........1...........",
    ".......................",
)

# 7. hat: Zoe's Ruby GEM wearing a jaunty 1984 pixel wizard/aviator hat
ZOE_HAT_PIXELS: tuple[str, ...] = (
    "..........JJJ..........",
    ".........JJJJJ.........",
    "........JJJYJJJ........",
    ".......JJJYYYJJJ.......",
    "......YYYYYYYYYYY......",
    "...JJJJJJJJJJJJJJJJJ...",
    "...ORRFFFFFFFFFFFDDO...",
    "..ORRFLWEWWWWWEWKFDDO..",
    ".ORRFLWEWEWWWEWEWKFDDO.",
    "OFFFFFFFFFFEFFFFFFFFFFO",
    ".OCCFQQQQQQFSSSSSSFBBO.",
    "..OCCFQQQQQFSSSSSFBBO..",
    "...OCCFQQQQFSSSSFBBO...",
    "....OCCFQQQFSSSFBBO....",
    ".....OCCFQQFSSFBBO.....",
    ".......OCCFFFBBO.......",
    ".........OCDBO.........",
    "...........O...........",
)

# 8. sprout: Smiling ruby GEM with Zoe's symmetric green two-leaf sprout inside the pavilion
ZOE_SPROUT_PIXELS: tuple[str, ...] = (
    ".....OOOOOOOOOOOOO.....",
    "....OHHHHHHHHHHHHHO....",
    "...ORRFFFFFFFFFFFDDO...",
    "..ORRFLWEWWWWWEWKFDDO..",
    ".ORRFLWEWEWWWEWEWKFDDO.",
    "OFFFFFFFFFFEFFFFFFFFFFO",
    ".OCCFQQQQQQFSSSSSSFBBO.",
    "..OCCFQQQQQFSSSSSFBBO..",
    "...OCCFQGGGFGGSFBBO....",
    "....OCCFGGGGGGFBBO.....",
    ".....OCCFQQGSSFBO......",
    "......OCCFQGFBBO.......",
    ".......OCCGFBBO........",
    "........OCGBBO.........",
    ".........OCDBO.........",
    "..........ODO..........",
    "...........O...........",
    ".......................",
)

# 9. prism: Prismatic rainbow diamond with three bright white dots
ZOE_PRISM_PIXELS: tuple[str, ...] = (
    ".....PPPPPVVVBBBB......",
    "....PPPPPPVVVVBBBB.....",
    "...RRRRPPPVVVVBBBCC....",
    "..RRRRPPPVVVVVBBBBCC...",
    ".OOOORWWPPVVWWBBWWCCC..",
    "OOOOYYWWVVVVWWBBWWCCCC.",
    ".OOOYYYYGVVVBBBBCCCCC..",
    "..OOYYYYGGGGTTTCCCCC...",
    "...OYYYYGGGGTTTTCCC....",
    "....YYYYGGGGTTTTCC.....",
    ".....YYYGGGGTTTTC......",
    "......YYGGGGTTTT.......",
    ".......YGGGGTTT........",
    "........GGGTTT.........",
    ".........GGTT..........",
    "..........GT...........",
    "...........G...........",
    ".......................",
)

EMBLEM_MAP: dict[str, tuple[str, ...]] = {
    "ruby": ZOE_GEM_PIXELS,
    "gem3": ZOE_GEM3_PIXELS,
    "atari": ZOE_ATARI_PIXELS,
    "sm124": ZOE_SM124_PIXELS,
    "tetris": ZOE_TETRIS_PIXELS,
    "dos": ZOE_DOS_PIXELS,
    "hat": ZOE_HAT_PIXELS,
    "sprout": ZOE_SPROUT_PIXELS,
    "prism": ZOE_PRISM_PIXELS,
}

EMBLEM_DESCRIPTIONS: dict[str, str] = {
    "ruby": "Zoe App Faceted Ruby GEM (default)",
    "gem3": "1987 Digital Research GEM 3.0 Crimson Signet",
    "atari": "1985 Atari ST / EmuTOS Emerald Desktop + MIDI Pins",
    "sm124": "Atari ST SM124 1-Bit Monochrome GEM ICONBLK",
    "tetris": "1984 Pajitnov Tetris 7-Tetromino Mosaic GEM",
    "dos": "1984 IBM PC MS-DOS P31 Green Phosphor CRT",
    "hat": "Zoe Ruby GEM with Retro Wizard / Pilot Hat",
    "sprout": "Zoe Ruby GEM with Two-Leaf Botanical Sprout",
    "prism": "Zoe Prismatic Rainbow Diamond",
}

PALETTE: dict[str, tuple[int, int, int] | None] = {
    "O": (249, 184, 200),  # Outer luminous rose bevel
    "F": (255, 224, 234),  # Inner bright bevel lines (#FFE0EA)
    "H": (243, 86, 112),   # Outer crown top (#F35670)
    "R": (235, 62, 94),    # Outer crown left (#EB3E5E)
    "D": (190, 26, 58),    # Outer crown right deep ruby shadow (#BE1A3A)
    "L": (244, 138, 160),  # Inner crown left facet
    "W": (251, 182, 198),  # Inner crown table highlight (#FBB6C6)
    "K": (236, 104, 130),  # Inner crown right facet
    "C": (232, 58, 92),    # Outer pavilion left
    "B": (218, 44, 78),    # Outer pavilion right
    "Q": (246, 150, 170),  # Inner pavilion left
    "S": (236, 110, 136),  # Inner pavilion right
    "E": (59, 36, 46),     # Zoe's smiling (◠◡◠) face (#3B242E)
    "G": (118, 238, 165),  # Mint green sprout / Tetris S-piece
    "P": (244, 63, 126),   # Prism magenta
    "V": (155, 89, 246),   # Prism violet / Tetris T-piece
    "T": (20, 184, 166),   # Prism teal
    "Y": (248, 204, 48),   # Gold star / Tetris O-piece / MIDI pin
    "X": (240, 26, 42),    # Digital Research GEM 3.0 crimson red
    "I": (246, 248, 250),  # Crisp 1-bit paper white
    "M": (18, 20, 26),     # Crisp 1-bit Atari SM124 / GEM black
    "A": (0, 126, 68),     # Authentic Atari ST / EmuTOS desktop green
    "N": (54, 224, 244),   # Tetris I-piece cyan
    "U": (56, 124, 246),   # Tetris J-piece cobalt blue
    "Z": (240, 56, 78),    # Tetris Z-piece crimson
    "J": (38, 56, 122),    # Retro wizard/pilot hat midnight navy
    "1": (72, 255, 132),   # IBM MS-DOS P31 bright phosphor
    "2": (28, 214, 92),    # IBM MS-DOS P31 crown phosphor
    "3": (14, 138, 58),    # IBM MS-DOS P31 mid phosphor
    "4": (10, 84, 36),     # IBM MS-DOS P31 shadow phosphor
    "0": (8, 24, 12),      # IBM MS-DOS dark CRT glass
    ".": None,             # Transparent background
}

_PLAIN_GEM_LINES: tuple[str, ...] = (
    "     /===========\\     ",
    "    / .---------. \\    ",
    "   /  |  ◠ ◡ ◠  |  \\   ",
    "  (---+----+----+---)  ",
    "   \\  \\    |    /  /   ",
    "    \\  \\   |   /  /    ",
    "     \\  '--+--'  /     ",
    "      \\    |    /      ",
    "       \\___v___/       ",
)


def _supports_color(stream: TextIO | None = None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    target = stream or sys.stdout
    try:
        return bool(target.isatty())
    except Exception:
        return False


def _fg(rgb: tuple[int, int, int]) -> str:
    return f"\x1b[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _bg(rgb: tuple[int, int, int]) -> str:
    return f"\x1b[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _pixel_cell(
    top: tuple[int, int, int] | None,
    bot: tuple[int, int, int] | None,
    active_seq: str,
) -> tuple[str, str]:
    if top is None and bot is None:
        return ("\x1b[0m " if active_seq else " "), ""
    if top is not None and bot is None:
        seq = _fg(top)
        prefix = ("\x1b[0m" + seq if active_seq else seq) if active_seq != seq else ""
        return prefix + "▀", seq
    if top is None and bot is not None:
        seq = _fg(bot)
        prefix = ("\x1b[0m" + seq if active_seq else seq) if active_seq != seq else ""
        return prefix + "▄", seq
    seq = _fg(top) + _bg(bot)  # type: ignore[arg-type]
    prefix = seq if active_seq != seq else ""
    return prefix + "▀", seq


def _palette_for_emblem(emblem: str) -> dict[str, tuple[int, int, int] | None]:
    if emblem in {"prism", "tetris"}:
        p = dict(PALETTE)
        p["O"] = (255, 134, 42)
        p["B"] = (56, 152, 255)
        p["C"] = (34, 197, 226)
        p["W"] = (255, 255, 255)
        return p
    return PALETTE


def render_gem_lines(color: bool = True, emblem: str = "ruby") -> list[str]:
    """Render any Zoe GEM signet into 9 terminal lines."""
    if not color:
        return list(_PLAIN_GEM_LINES)
    rows = EMBLEM_MAP.get(emblem, ZOE_GEM_PIXELS)
    pal = _palette_for_emblem(emblem)
    lines: list[str] = []
    width = len(rows[0])
    for row_index in range(0, len(rows), 2):
        top_row = rows[row_index]
        bot_row = rows[row_index + 1] if row_index + 1 < len(rows) else "." * width
        parts: list[str] = []
        active_seq = ""
        for col in range(width):
            cell, active_seq = _pixel_cell(pal[top_row[col]], pal[bot_row[col]], active_seq)
            parts.append(cell)
        if active_seq:
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def render_emblem_gallery(color: bool = True, cols: int = 3) -> list[str]:
    """Render all Zoe GEM retro-firmware variants side-by-side in a terminal sprite gallery."""
    names = list(EMBLEM_MAP.keys())
    out = ["Zoe GEM Signet Gallery (switch live with `/emblem <name>`):"]
    for start in range(0, len(names), cols):
        row_names = names[start : start + cols]
        rendered = [render_gem_lines(color=color, emblem=name) for name in row_names]
        out.append("")
        for line_idx in range(len(rendered[0])):
            out.append("   ".join(sprite[line_idx] for sprite in rendered))
        labels = "   ".join(f"{name:^23}" for name in row_names)
        out.append(labels)
    out.append("")
    for name in names:
        out.append(f"  {name:<8} · {EMBLEM_DESCRIPTIONS.get(name, '')}")
    return out


def render_terminal_header(
    title: str = APP_NAME,
    subtitle: str = APP_TAGLINE,
    detail: str = DEFAULT_DETAIL,
    voice_line: str | None = None,
    cwd: str | Path | None = None,
    color: bool | None = None,
    emblem: str = "ruby",
) -> str:
    """Build the minimal Zoe terminal startup banner."""
    del cwd
    use_color = _supports_color() if color is None else color
    gem_lines = render_gem_lines(color=use_color, emblem=emblem)
    extras = [item for item in (subtitle, detail, voice_line) if item]
    title_row = 3 if not extras else 2
    meta: dict[int, str] = {}
    if title:
        meta[title_row] = f"\x1b[1;3;38;2;243;86;112m{title}\x1b[0m" if use_color else title
    for offset, text in enumerate(extras, 1 if title else 0):
        meta[title_row + offset] = f"\x1b[3;38;2;148;156;196m{text}\x1b[0m" if use_color else text

    out = [""]
    for idx, gem_row in enumerate(gem_lines):
        right = meta.get(idx, "")
        out.append(f"  {gem_row}   {right}" if right else f"  {gem_row}")
    out.append("")
    return "\n".join(out)

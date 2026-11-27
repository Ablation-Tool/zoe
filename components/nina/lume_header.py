#!/usr/bin/env python3
"""Lume ◠◡◠ — Minimal Zoe App ruby GEM terminal header."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import TextIO

APP_NAME = ""
APP_TAGLINE = ""
DEFAULT_DETAIL = ""

# 18 rows x 23 cols: exact smooth-edged silhouette & (◠◡◠) crown smile from Zoe App (zoe_emblem.xml)
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


def render_gem_lines(color: bool = True) -> list[str]:
    """Render Zoe's App faceted red GEM into 9 terminal lines."""
    if not color:
        return list(_PLAIN_GEM_LINES)
    lines: list[str] = []
    rows = ZOE_GEM_PIXELS
    width = len(rows[0])
    for r in range(0, len(rows), 2):
        top_row = rows[r]
        bot_row = rows[r + 1] if r + 1 < len(rows) else "." * width
        parts: list[str] = []
        active_seq = ""
        for c in range(width):
            tc, bc = PALETTE[top_row[c]], PALETTE[bot_row[c]]
            if tc is None and bc is None:
                if active_seq:
                    parts.append("\x1b[0m")
                    active_seq = ""
                parts.append(" ")
            elif tc is not None and bc is None:
                seq = _fg(tc)
                if active_seq != seq:
                    parts.append("\x1b[0m" + seq if active_seq else seq)
                    active_seq = seq
                parts.append("▀")
            elif tc is None and bc is not None:
                seq = _fg(bc)
                if active_seq != seq:
                    parts.append("\x1b[0m" + seq if active_seq else seq)
                    active_seq = seq
                parts.append("▄")
            else:
                assert tc is not None and bc is not None
                seq = _fg(tc) + _bg(bc)
                if active_seq != seq:
                    parts.append(seq)
                    active_seq = seq
                parts.append("▀")
        if active_seq:
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def render_terminal_header(
    title: str = APP_NAME,
    subtitle: str = APP_TAGLINE,
    detail: str = DEFAULT_DETAIL,
    voice_line: str | None = None,
    cwd: str | Path | None = None,
    color: bool | None = None,
) -> str:
    """Build the minimal Zoe terminal startup banner."""
    del cwd
    use_color = _supports_color() if color is None else color
    gem_lines = render_gem_lines(color=use_color)
    extras = [item for item in (subtitle, detail, voice_line) if item]
    title_row = 3 if not extras else 2
    meta: dict[int, str] = {}
    if title:
        meta[title_row] = f"\x1b[1;3;38;2;243;86;112m{title}\x1b[0m" if use_color else title
    for offset, text in enumerate(extras, 1 if title else 0):
        meta[title_row + offset] = f"\x1b[3;38;2;148;156;196m{text}\x1b[0m" if use_color else text

    out: list[str] = [""]
    for idx, gem_row in enumerate(gem_lines):
        right = meta.get(idx, "")
        out.append(f"  {gem_row}   {right}" if right else f"  {gem_row}")
    out.append("")
    return "\n".join(out)


def print_header(
    title: str = APP_NAME,
    subtitle: str = APP_TAGLINE,
    detail: str = DEFAULT_DETAIL,
    voice_line: str | None = None,
    cwd: str | Path | None = None,
    color: bool | None = None,
    file: TextIO | None = None,
) -> None:
    stream = file or sys.stdout
    use_color = _supports_color(stream) if color is None else color
    print(
        render_terminal_header(
            title=title, subtitle=subtitle, detail=detail,
            voice_line=voice_line, cwd=cwd, color=use_color,
        ),
        file=stream,
    )


def main() -> None:
    p = argparse.ArgumentParser(prog="lume-header", description="Render the Lume ◠◡◠ header")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--color", action="store_true")
    p.add_argument("--title", default=APP_NAME)
    p.add_argument("--subtitle", default=APP_TAGLINE)
    p.add_argument("--detail", default=DEFAULT_DETAIL)
    args = p.parse_args()
    color_opt = False if args.no_color else (True if args.color else None)
    print_header(title=args.title, subtitle=args.subtitle, detail=args.detail, color=color_opt)


if __name__ == "__main__":
    main()

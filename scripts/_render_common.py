#!/usr/bin/env python3
"""Shared dark-theme rendering utilities for Zoe publication figures."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


# Canonical Zoe Observatory dark palette shared across L3/L4/L5 figures.
ZOE_DARK_PALETTE: Dict[str, str] = {
    "BG": "#09111f",
    "PANEL": "#111e31",
    "BORDER": "#294058",
    "TEXT": "#e7edf5",
    "MUTED": "#9cafc4",
    "CYAN": "#62dce8",
    "RED": "#ef445a",
    "GOLD": "#e7c77b",
    "MINT": "#86efac",
    "ORCHID": "#f0a3df",
}


def load_json_report(path: Path) -> Dict[str, Any]:
    """Read and parse a UTF-8 JSON evidence report."""
    # Parse strictly from disk so figures never embed stale numbers.
    return json.loads(path.read_text(encoding="utf-8"))


def apply_dark_theme(
    palette: Optional[Mapping[str, str]] = None,
    *,
    font_family: Optional[str] = "monospace",
    grid_linestyle: Optional[str] = "--",
    grid_alpha: Optional[float] = 0.55,
    grid_color: Optional[str] = "#1e324a",
    yt_color: Optional[str] = None,
) -> None:
    """Configure matplotlib rcParams for Zoe's dark-mode figures."""
    pal = palette or ZOE_DARK_PALETTE
    # Fall back to INK/TEXT keys so phase-specific palettes work seamlessly.
    text_color = pal.get("TEXT", pal.get("INK", "#e7edf5"))
    muted_color = pal.get("MUTED", "#9cafc4")
    params: Dict[str, Any] = {
        "figure.facecolor": pal["BG"],
        "axes.facecolor": pal["PANEL"],
        "axes.edgecolor": pal.get("BORDER", "#294058"),
        "axes.labelcolor": text_color,
        "xtick.color": muted_color,
        "ytick.color": yt_color or muted_color,
        "text.color": text_color,
    }
    if font_family is not None:
        params["font.family"] = font_family
    if grid_color is not None:
        params["grid.color"] = grid_color
    if grid_linestyle is not None:
        params["grid.linestyle"] = grid_linestyle
    if grid_alpha is not None:
        params["grid.alpha"] = grid_alpha
    plt.rcParams.update(params)


def add_figure_header(
    fig: Figure,
    title: str,
    subtitle: str,
    *,
    title_color: str,
    subtitle_color: str,
    title_size: float = 15.0,
    subtitle_size: float = 10.0,
    title_y: float = 0.96,
    subtitle_y: float = 0.922,
) -> None:
    """Render standardized suptitle and centered subtitle banner on a figure."""
    # Place title and subtitle at consistent vertical anchors above subplots.
    fig.suptitle(title, fontsize=title_size, fontweight="bold", color=title_color, y=title_y)
    fig.text(0.5, subtitle_y, subtitle, ha="center", fontsize=subtitle_size, color=subtitle_color)


def draw_summary_card(
    ax: Axes,
    title: str,
    title_color: str,
    border_color: str,
    panel_color: str,
    lines: Sequence[Tuple[str, str, float, str]],
    *,
    start_y: float = 0.95,
    x: float = 0.03,
    line_step: float = 0.051,
    blank_step: float = 0.020,
    title_size: float = 10.1,
    title_pad: float = 10.0,
    family: Optional[str] = None,
) -> None:
    """Render a framed text scorecard panel on an axis."""
    ax.axis("off")
    ax.set_title(title, fontsize=title_size, color=title_color, fontweight="bold", pad=title_pad)
    # Draw the rounded-border card background behind all scorecard lines.
    ax.add_patch(
        plt.Rectangle(
            (0.0, 0.0),
            1.0,
            1.0,
            transform=ax.transAxes,
            facecolor=panel_color,
            edgecolor=border_color,
            linewidth=1.4,
        )
    )
    y_cursor = start_y
    text_kwargs: Dict[str, Any] = {"family": family} if family else {}
    for text, color, size, weight in lines:
        if text:
            ax.text(x, y_cursor, text, transform=ax.transAxes, fontsize=size, color=color, fontweight=weight, va="top", **text_kwargs)
            y_cursor -= line_step
        else:
            y_cursor -= blank_step


def save_figure(
    fig: Figure,
    out_path: Path,
    *,
    dpi: int = 180,
    facecolor: Optional[str] = None,
    mirror_path: Optional[Path] = None,
    root: Optional[Path] = None,
    quiet: bool = False,
) -> Path:
    """Save figure to disk, optionally mirror to Desktop, and close figure."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs: Dict[str, Any] = {"dpi": dpi}
    if facecolor is not None:
        save_kwargs["facecolor"] = facecolor
    fig.savefig(out_path, **save_kwargs)
    plt.close(fig)
    # Mirror to Desktop showcase folder only when that directory already exists.
    if mirror_path is not None and mirror_path.parent.is_dir():
        shutil.copy2(out_path, mirror_path)
    if not quiet:
        display_path = out_path.relative_to(root) if root is not None else out_path
        print(f"[OK] Saved {display_path} ({out_path.stat().st_size:,} bytes)")
    return out_path

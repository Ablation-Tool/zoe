"""Digital Research Artline 2.0 Hacker-Minimalist Primitives for Zoe.

Implements three classic 1990 low-resource, deterministic vector techniques from
Digital Research Artline 2.0 (User Reference Guide pp. 11-11, 13-12/13-13, ALIGN.TLS,
and Installation & Startup Tutorial pp. 6-10..6-14) with 0 GPU and 0 cloud tokens:

  1. `/artline trace [f9 | <image_path>]`
     Deterministic Moore-Neighbor + RDP raster-to-vector Autotrace + partial
     `Trace Segment` boundary cut + `F9` Image Hide/Show toggle (works on both
     built-in pediatric pontine/brainstem dithered MRI scan and any user image!).
  2. `/artline ring [n]`
     Tutorial p. 6-14 `Rotator + Thumbtack` radial symmetry emblem — one single
     14-vertex ruby swallow-crystal motif spun N=16 times around a moonlit horizon
     and Zoe's `(◠ ◡ ◠)` constellation core (< 25 KB vector footprint).
  3. `/artline icon [<emblem>]`
     Artline pp. 13-12/13-13 `Icon Editor` pixel-grid workspace wired directly to
     Zoe's 32x32 Atari ST 68000 `ICONBLK` bitmap compiler + `ALIGN.TLS` 9-way pad.

Zero copyrighted book text, zero cloud tokens, strict constitutional honesty.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from .artline import (
    ArtlineDocument,
    align_bounds_9way,
    autotrace_bitmap,
    rotate_ring,
    trace_segment,
)
from .zoe_atari_gem_rsc import emblem_to_iconblk_32x32

_BG_PAPER = "#f7f5ee"
_BG_DARK = "#0f1020"
_INK = "#141820"
_RUBY = "#e63956"
_CYAN = "#5ce1e6"
_MAGENTA = "#d946ef"
_AMBER = "#f59e0b"
_CREAM = "#f7f2e4"
_SLATE = "#64748b"


def _synthetic_brainstem_masks(size: int = 120) -> tuple[list[list[int]], list[list[int]]]:
    """Build deterministic 120x120 pediatric axial brainstem/pons + focal lesion binary masks."""
    outer = [[0] * size for _ in range(size)]
    lesion = [[0] * size for _ in range(size)]
    cx, cy = size * 0.50, size * 0.52
    for r in range(size):
        for c in range(size):
            nx = (c - cx) / (size * 0.36)
            ny = (r - cy) / (size * 0.30)
            # Axial pons silhouette: rounded anterior belly + posterior 4th-ventricle notch
            notch = 0.24 * math.exp(-((nx / 0.28) ** 2)) if ny > 0.15 else 0.0
            wing = 0.14 * math.exp(-(((abs(nx) - 0.72) / 0.25) ** 2)) * math.exp(-((ny / 0.45) ** 2))
            if (nx * nx + (ny + notch) ** 2) <= (1.0 + wing):
                outer[r][c] = 1
            # Focal asymmetric pontine mass on right-dorsal quadrant (for repeatable margin tracing)
            lx = (c - (cx + size * 0.11)) / (size * 0.12)
            ly = (r - (cy - size * 0.05)) / (size * 0.10)
            if lx * lx + ly * ly + 0.18 * math.sin(3.0 * math.atan2(ly, lx)) <= 1.0:
                lesion[r][c] = 1
    return outer, lesion


def _split_largest_components(mask: list[list[int]], max_components: int = 2) -> list[list[list[int]]]:
    """Extract top connected foreground components via fast BFS so framed scans also trace inner subjects."""
    h, w = len(mask), len(mask[0])
    seen = [[False] * w for _ in range(h)]
    comps: list[tuple[int, bool, list[tuple[int, int]]]] = []
    for r in range(h):
        for c in range(w):
            if not mask[r][c] or seen[r][c]:
                continue
            q = [(r, c)]
            seen[r][c] = True
            pts: list[tuple[int, int]] = []
            while q:
                cr, cc = q.pop()
                pts.append((cr, cc))
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < h and 0 <= nc < w and mask[nr][nc] and not seen[nr][nc]:
                        seen[nr][nc] = True
                        q.append((nr, nc))
            if len(pts) >= 20:
                rs = [p[0] for p in pts]
                cs = [p[1] for p in pts]
                bbox_area = max(1, (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1))
                # Thin hollow border frames have very low fill density (< 0.16 of their own bbox)
                is_frame = (len(pts) / bbox_area) < 0.16 and bbox_area > (0.45 * h * w)
                comps.append((len(pts), is_frame, pts))
    # Prioritize solid interior subjects over outer decorative/scanner frames
    comps.sort(key=lambda item: (item[1], -item[0]))
    masks: list[list[list[int]]] = []
    for _sz, _is_frame, pts in comps[:max_components]:
        sub = [[0] * w for _ in range(h)]
        for pr, pc in pts:
            sub[pr][pc] = 1
        masks.append(sub)
    return masks or [mask]


def autotrace_image_file(
    image_path: str | Path,
    *,
    precision: float = 1.6,
    max_dim: int = 160,
) -> dict[str, Any]:
    """Load any raster PNG/JPG/BMP, threshold foreground deterministically, and Autotrace."""
    p = Path(image_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Raster image not found: {p}")
    img = Image.open(p).convert("L")
    img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
    w, h = img.size
    px = list(img.getdata())
    # Detect whether background border is bright (scan/paper) or dark (MRI)
    border = [px[c] for c in range(w)] + [px[(h - 1) * w + c] for c in range(w)]
    border_mean = sum(border) / max(1, len(border))
    thresh = 0.5 * (border_mean + (min(px) if border_mean > 128 else max(px)))
    dark_subject = border_mean > 128
    mask = [
        [1 if ((px[r * w + c] < thresh) if dark_subject else (px[r * w + c] > thresh)) else 0 for c in range(w)]
        for r in range(h)
    ]
    # 1-pixel morphological closing bridges halftone dither gaps (like Artline's Gap Size control!)
    closed = [
        [
            1 if (mask[r][c] or sum(mask[r + dr][c + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1) if 0 <= r + dr < h and 0 <= c + dc < w) >= 4) else 0
            for c in range(w)
        ]
        for r in range(h)
    ]
    comp_masks = _split_largest_components(closed, max_components=2)
    traced = autotrace_bitmap(comp_masks[0], precision=precision)
    traced["width"] = w
    traced["height"] = h
    traced["source_name"] = p.name
    traced["mask"] = comp_masks[0]
    traced["secondary"] = autotrace_bitmap(comp_masks[1], precision=precision) if len(comp_masks) > 1 else None
    return traced


def _map_pts(pts: list[list[float]], src_w: int, src_h: int, dst: tuple[float, float, float, float]) -> list[list[float]]:
    x0, y0, x1, y1 = dst
    scale = min((x1 - x0) / max(1, src_w), (y1 - y0) / max(1, src_h))
    ox = x0 + 0.5 * ((x1 - x0) - src_w * scale)
    oy = y0 + 0.5 * ((y1 - y0) - src_h * scale)
    return [[round(ox + p[0] * scale, 2), round(oy + p[1] * scale, 2)] for p in pts]


def _draw_stipple_preview(doc: ArtlineDocument, mask: list[list[int]], dst: tuple[float, float, float, float], color: str, step: int = 5) -> None:
    """Render a compact 1990 Artline stippled bitmap backdrop inside dst (<300 elements)."""
    h, w = len(mask), len(mask[0])
    x0, y0, x1, y1 = dst
    scale = min((x1 - x0) / max(1, w), (y1 - y0) / max(1, h))
    ox = x0 + 0.5 * ((x1 - x0) - w * scale)
    oy = y0 + 0.5 * ((y1 - y0) - h * scale)
    dot = max(1.6, scale * step * 0.42)
    for r in range(0, h, step):
        for c in range(0, w, step):
            if mask[r][c]:
                px, py = ox + c * scale, oy + r * scale
                doc.add_element("rectangle", bounds=[px, py, px + dot, py + dot], fill=color, stroke=color, width=0.5)


def build_artline_trace_plate(*, arg: str = "") -> tuple[ArtlineDocument, dict[str, Any]]:
    """Plate 7: Artline 2.0 Autotrace + Trace Segment (p. 11-11) + F9 Image Toggle (p. 6-10)."""
    tokens = arg.strip().split()
    f9_hide = any(tok.lower() in {"f9", "hide", "clean", "vector"} for tok in tokens)
    path_toks = [tok for tok in tokens if tok.lower() not in {"f9", "hide", "clean", "vector"}]

    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill=_BG_PAPER, stroke=_INK, width=1.8)
    doc.add_element("rectangle", bounds=[14, 14, 986, 686], fill="none", stroke=_INK, width=0.9)

    if path_toks:
        tr = autotrace_image_file(" ".join(path_toks), precision=2.2)
        src_w, src_h, mask = tr["width"], tr["height"], tr["mask"]
        contour = tr["contour"]
        seg_start = [tr["bbox"][0], 0.5 * (tr["bbox"][1] + tr["bbox"][3])]
        seg_end = [tr["bbox"][2], 0.5 * (tr["bbox"][1] + tr["bbox"][3])]
        seg = trace_segment(contour, seg_start, seg_end, frame_bounds=[0, 0, src_w, src_h])
        lesion_tr = None
        label = f"Custom Raster ({tr['source_name']})"
    else:
        src_w = src_h = 120
        mask, lesion_mask = _synthetic_brainstem_masks(120)
        tr = autotrace_bitmap(mask, precision=1.8)
        lesion_tr = autotrace_bitmap(lesion_mask, precision=1.2)
        contour = tr["contour"]
        # Artline p. 11-11 Trace Segment cut ray isolating the superior/dorsal margin
        seg_start = [18.0, 56.0]
        seg_end = [102.0, 48.0]
        seg = trace_segment(contour, seg_start, seg_end, frame_bounds=[0, 0, 120, 120])
        label = "Axial Brainstem + Pontine Margin (120x120 1-Bit Scan)"

    mode_tag = "F9: IMAGE HIDDEN (PURE VECTOR)" if f9_hide else "F9: RASTER + VECTOR OVERLAY"
    doc.add_element("text", position=[34, 48], text=f"Digital Research Artline 2.0 · Autotrace & Trace Segment ({mode_tag})", size=17, stroke=_INK, width=1)
    doc.add_element("line", points=[[28, 60], [972, 60]], stroke=_INK, width=1.3)
    doc.add_element("text", position=[34, 82], text=f"Source: {label} · Moore-Neighbor + RDP Simplification · 0 GPU · 0 tokens", size=12, stroke=_SLATE, width=1)

    left_box = (56.0, 120.0, 466.0, 520.0)
    right_box = (534.0, 120.0, 944.0, 520.0)
    for bx0, by0, bx1, by1, hdr in (
        (*left_box, "1. RASTER IMAGE + TRACE SEGMENT RAY (p. 11-11)"),
        (*right_box, "2. AUTOTRACED VECTOR CONTOUR + SEGMENT"),
    ):
        doc.add_element("rectangle", bounds=[bx0 - 10, by0 - 26, bx1 + 10, by1 + 16], fill="#ffffff", stroke=_INK, width=1.2)
        doc.add_element("text", position=[bx0, by0 - 8], text=hdr, size=11, stroke=_INK, width=1)

    # Left stage: Raster stipple (hidden when F9 active!) + traced boundary + Trace Segment cut line
    if not f9_hide:
        _draw_stipple_preview(doc, mask, left_box, "#7f8c9a", step=max(4, src_w // 26))
        if lesion_tr is not None:
            _draw_stipple_preview(doc, lesion_mask, left_box, _RUBY, step=4)
    left_contour = _map_pts(contour, src_w, src_h, left_box)
    doc.add_element("path", points=left_contour, closed=True, smooth=False, fill="none", stroke=_INK, width=1.8)
    ray_pts = _map_pts([seg_start, seg_end], src_w, src_h, left_box)
    doc.add_element("line", points=ray_pts, stroke=_RUBY, width=1.8)
    for rx, ry in ray_pts:
        doc.add_element("rectangle", bounds=[rx - 4, ry - 4, rx + 4, ry + 4], fill=_RUBY, stroke=_INK, width=1.0)

    # Right stage: Pure vector contour + highlighted Trace Segment + inner focal lesion vector
    right_contour = _map_pts(contour, src_w, src_h, right_box)
    right_seg = _map_pts(seg, src_w, src_h, right_box)
    doc.add_element("path", points=right_contour, closed=True, smooth=False, fill="#eef2f6", stroke=_INK, width=2.2)
    doc.add_element("path", points=right_seg, closed=False, smooth=False, fill="none", stroke=_RUBY, width=4.0)
    if lesion_tr is not None:
        right_lesion = _map_pts(lesion_tr["contour"], src_w, src_h, right_box)
        doc.add_element("path", points=right_lesion, closed=True, smooth=False, fill="#fce7f3", stroke=_MAGENTA, width=2.4)

    # Metric readout bar at bottom (Shoelace area, perimeter, circularity, compression ratio)
    ratio = round((src_w * src_h) / max(1, tr["traced_points"]), 1)
    doc.add_element("rectangle", bounds=[46, 556, 954, 636], fill="#141820", stroke=_INK, width=1.4)
    doc.add_element(
        "text",
        position=[64, 586],
        text=f"RASTER {src_w}x{src_h} ({src_w * src_h:,} px) -> VECTOR {tr['traced_points']} pts (raw {tr['raw_points']} edge px) · {ratio}x reduction",
        size=13,
        stroke=_CYAN,
        width=1,
    )
    extra = f" · Lesion={lesion_tr['traced_points']} pts (area={lesion_tr['area']} px^2)" if lesion_tr else ""
    doc.add_element(
        "text",
        position=[64, 616],
        text=f"Area={tr['area']} px^2 · Perimeter={tr['perimeter']} px · Circularity={tr['circularity']:.3f} · Segment={len(seg)} pts{extra}",
        size=12,
        stroke=_CREAM,
        width=1,
    )
    doc.add_element("text", position=[34, 670], text="Toggle backdrop via `/artline trace f9` · Trace any image via `/artline trace <path>` · clinical_action_authorized=False", size=11, stroke=_SLATE, width=1)
    return doc, {
        "f9_hide_image": f9_hide,
        "raw_points": tr["raw_points"],
        "traced_points": tr["traced_points"],
        "segment_points": len(seg),
        "circularity": tr["circularity"],
        "compression_ratio": ratio,
    }


def build_artline_ring_plate(*, count: int = 16) -> tuple[ArtlineDocument, dict[str, Any]]:
    """Plate 8: Artline Tutorial p. 6-14 Rotator + Thumbtack Radial Symmetry Emblem (1 motif -> N copies)."""
    n = max(6, min(24, int(count)))
    doc = ArtlineDocument()
    # Authentic Artline Tutorial p. 6-14 editorial double-hairline gallery frame
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill=_BG_PAPER, stroke=_INK, width=1.5)
    doc.add_element("rectangle", bounds=[54, 34, 946, 634], fill="#ffffff", stroke=_INK, width=1.6)
    doc.add_element("rectangle", bounds=[60, 40, 940, 628], fill="none", stroke=_INK, width=0.8)

    cx, cy = 500.0, 334.0
    # Outer circular silver-mist medallion ring (like Tutorial p. 6-14)
    outer_ring = [[cx + 266 * math.cos(2 * math.pi * i / 48), cy + 266 * math.sin(2 * math.pi * i / 48)] for i in range(48)]
    doc.add_element("path", points=outer_ring, closed=True, smooth=False, fill="#e5e7eb", stroke=_INK, width=1.6)

    # ONE single 14-vertex sweeping swallow-crystal / dolphin-fin motif spun N times around Thumbtack (cx, cy)!
    motif = [
        [cx - 34, cy - 134], [cx - 8, cy - 148], [cx + 22, cy - 154], [cx + 50, cy - 142],
        [cx + 68, cy - 156], [cx + 76, cy - 186], [cx + 98, cy - 208], [cx + 72, cy - 202],
        [cx + 58, cy - 224], [cx + 54, cy - 194], [cx + 42, cy - 178], [cx + 12, cy - 188],
        [cx - 22, cy - 180], [cx - 46, cy - 154],
    ]
    petals = rotate_ring(motif, cx, cy, count=n)
    for k, poly in enumerate(petals):
        fill_c = _INK if k % 2 == 0 else "#1e1b2e"
        stroke_c = _RUBY if k % 4 == 0 else _INK
        doc.add_element("path", points=poly, closed=True, smooth=False, fill=fill_c, stroke=stroke_c, width=1.3)

    # Inner moonlit horizon circle (upper obsidian night sky + lower silver sea + moon + water bars + Zoe smile)
    inner_r = 128.0
    upper_arc = [[cx + inner_r * math.cos(math.pi + math.pi * i / 24), cy + inner_r * math.sin(math.pi + math.pi * i / 24)] for i in range(25)]
    lower_arc = [[cx + inner_r * math.cos(math.pi * i / 24), cy + inner_r * math.sin(math.pi * i / 24)] for i in range(25)]
    doc.add_element("path", points=upper_arc, closed=True, smooth=False, fill=_INK, stroke=_INK, width=1.5)
    doc.add_element("path", points=lower_arc, closed=True, smooth=False, fill="#d8dde6", stroke=_INK, width=1.5)
    doc.add_element("line", points=[[cx - inner_r, cy], [cx + inner_r, cy]], stroke=_INK, width=1.6)

    # Rising moon + 4 Artline horizontal sea-reflection bars
    moon = [[cx + 28 + 22 * math.cos(2 * math.pi * i / 20), cy - 62 + 22 * math.sin(2 * math.pi * i / 20)] for i in range(20)]
    doc.add_element("path", points=moon, closed=True, smooth=False, fill=_CREAM, stroke=_CREAM, width=1.0)
    for idx, (half_w, dy) in enumerate(((46, -12), (34, -22), (24, -31), (14, -39))):
        doc.add_element("line", points=[[cx + 28 - half_w, cy + dy], [cx + 28 + half_w, cy + dy]], stroke=_CREAM, width=2.4 - idx * 0.3)

    # Subtle ruby Zoe (◠ ◡ ◠) star-constellation mark in lower quiet silver sea
    doc.add_element("path", points=[[cx - 34, cy + 52], [cx - 28, cy + 44], [cx - 20, cy + 44], [cx - 14, cy + 52]], closed=False, smooth=True, fill="none", stroke=_RUBY, width=2.8)
    doc.add_element("path", points=[[cx + 14, cy + 52], [cx + 20, cy + 44], [cx + 28, cy + 44], [cx + 34, cy + 52]], closed=False, smooth=True, fill="none", stroke=_RUBY, width=2.8)
    doc.add_element("path", points=[[cx - 12, cy + 62], [cx - 4, cy + 72], [cx + 4, cy + 72], [cx + 12, cy + 62]], closed=False, smooth=True, fill="none", stroke=_RUBY, width=2.8)

    # Tutorial-style footer rule
    doc.add_element("line", points=[[54, 650], [946, 650]], stroke=_INK, width=1.6)
    doc.add_element("line", points=[[54, 654], [946, 654]], stroke=_INK, width=0.8)
    doc.add_element("text", position=[58, 678], text=f"6-14   Artline Rotator + Thumbtack Ring · 1 Motif (14 pts) x {n} Copies = {n * 14} Vertices · 0 tokens", size=12, stroke=_INK, width=1)
    doc.add_element("text", position=[780, 678], text="Zoe Artline Tutorial", size=12, stroke=_INK, width=1)
    return doc, {"count": n, "motif_vertices": len(motif), "total_ring_vertices": n * len(motif)}


def build_artline_icon_editor_plate(*, emblem: str = "ruby") -> tuple[ArtlineDocument, dict[str, Any]]:
    """Plate 9: Artline pp. 13-12/13-13 Icon Editor (32x32 Atari ST ICONBLK) + ALIGN.TLS 9-Way Pad."""
    name = (emblem or "ruby").strip().lower()
    mask_words, data_words = emblem_to_iconblk_32x32(name)
    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill=_BG_PAPER, stroke=_INK, width=1.6)
    doc.add_element("text", position=[34, 44], text=f"Digital Research Artline 2.0 · Icon Editor (32x32 Atari ST '{name}') & ALIGN.TLS 9-Way Pad", size=16, stroke=_INK, width=1)
    doc.add_element("line", points=[[28, 56], [972, 56]], stroke=_INK, width=1.2)

    # Left Window: Authentic GEM Icon Editor Chrome (pp. 13-12 / 13-13)
    wx0, wy0, wx1, wy1 = 44, 86, 566, 628
    doc.add_element("rectangle", bounds=[wx0 + 6, wy0 + 6, wx1 + 6, wy1 + 6], fill="#94a3b8", stroke="none", width=1)
    doc.add_element("rectangle", bounds=[wx0, wy0, wx1, wy1], fill="#ffffff", stroke=_INK, width=2.0)
    doc.add_element("rectangle", bounds=[wx0, wy0, wx1, wy0 + 30], fill="#e5e7eb", stroke=_INK, width=1.4)
    doc.add_element("text", position=[252, wy0 + 21], text="Icon Editor", size=14, stroke=_INK, width=1)

    # Left vertical toolbox strip inside Icon Editor (Grid, Eraser, Up, Down, Del, End)
    doc.add_element("rectangle", bounds=[wx0 + 6, wy0 + 36, wx0 + 64, wy1 - 68], fill="#cbd5e1", stroke=_INK, width=1.2)
    for idx, lbl in enumerate(("GRID", "ERAS", "UP", "DOWN", "DEL", "END")):
        ty = wy0 + 46 + idx * 62
        doc.add_element("rectangle", bounds=[wx0 + 14, ty, wx0 + 56, ty + 48], fill="#ffffff" if idx != 0 else _INK, stroke=_INK, width=1.2)
        doc.add_element("text", position=[wx0 + 18, ty + 29], text=lbl, size=10, stroke="#ffffff" if idx == 0 else _INK, width=1)

    # 32x32 Pixel Workspace rendering Zoe's live Motorola 68000 ICONBLK!
    gx0, gy0, cell = wx0 + 82, wy0 + 42, 13
    gw = 32 * cell
    doc.add_element("rectangle", bounds=[gx0, gy0, gx0 + gw, gy0 + gw], fill="#ffffff", stroke=_INK, width=1.6)
    active_px = 0
    for row in range(32):
        w_hi, w_lo = data_words[row * 2], data_words[row * 2 + 1]
        m_hi, m_lo = mask_words[row * 2], mask_words[row * 2 + 1]
        d32 = (w_hi << 16) | w_lo
        m32 = (m_hi << 16) | m_lo
        for col in range(32):
            bit = 31 - col
            px0, py0 = gx0 + col * cell, gy0 + row * cell
            if (d32 >> bit) & 1:
                doc.add_element("rectangle", bounds=[px0 + 1, py0 + 1, px0 + cell - 1, py0 + cell - 1], fill=_INK, stroke=_INK, width=0.5)
                active_px += 1
            elif (m32 >> bit) & 1:
                doc.add_element("rectangle", bounds=[px0 + 2, py0 + 2, px0 + cell - 2, py0 + cell - 2], fill="#fecdd3", stroke=_RUBY, width=0.5)
    # Crisp 8-pixel major grid lines (keeps element count lean while looking crisp!)
    for step in range(0, 33, 4):
        doc.add_element("line", points=[[gx0 + step * cell, gy0], [gx0 + step * cell, gy0 + gw]], stroke="#cbd5e1", width=0.7)
        doc.add_element("line", points=[[gx0, gy0 + step * cell], [gx0 + gw, gy0 + step * cell]], stroke="#cbd5e1", width=0.7)

    # Bottom Icon Selector & OK / Cancel bar
    doc.add_element("rectangle", bounds=[wx0 + 6, wy1 - 58, wx1 - 6, wy1 - 8], fill="#f1f5f9", stroke=_INK, width=1.2)
    doc.add_element("text", position=[wx0 + 18, wy1 - 28], text=f"ICONBLK: {name.upper()} · 64 words (128 B)", size=11, stroke=_INK, width=1)
    doc.add_element("rectangle", bounds=[wx1 - 154, wy1 - 48, wx1 - 88, wy1 - 18], fill=_INK, stroke=_INK, width=1.2)
    doc.add_element("text", position=[wx1 - 134, wy1 - 28], text="OK", size=12, stroke="#ffffff", width=1)
    doc.add_element("rectangle", bounds=[wx1 - 80, wy1 - 48, wx1 - 14, wy1 - 18], fill="#ffffff", stroke=_INK, width=1.2)
    doc.add_element("text", position=[wx1 - 71, wy1 - 28], text="Cancel", size=11, stroke=_INK, width=1)

    # Right Panel: ALIGN.TLS 9-Way Compass Pad + Live Idempotent 9-Way Verification Grid
    rx0, ry0, rx1, ry1 = 602, 86, 956, 628
    doc.add_element("rectangle", bounds=[rx0, ry0, rx1, ry1], fill="#ffffff", stroke=_INK, width=1.8)
    doc.add_element("rectangle", bounds=[rx0, ry0, rx1, ry0 + 30], fill=_INK, stroke=_INK, width=1.2)
    doc.add_element("text", position=[rx0 + 16, ry0 + 21], text="ALIGN.TLS  ·  9-WAY ALIGNMENT PAD", size=12, stroke=_CREAM, width=1)

    modes = ("tl", "tc", "tr", "ml", "cc", "mr", "bl", "bc", "br")
    labels = ("TL", "TC", "TR", "ML", "CC", "MR", "BL", "BC", "BR")
    for idx, (mode, lbl) in enumerate(zip(modes, labels)):
        gr, gc = divmod(idx, 3)
        cx0, cy0 = rx0 + 24 + gc * 106, ry0 + 56 + gr * 116
        cell_b = [cx0, cy0, cx0 + 92, cy0 + 82]
        aligned = align_bounds_9way([cell_b, [cx0 + 30, cy0 + 24, cx0 + 62, cy0 + 50]], mode=mode)
        doc.add_element("rectangle", bounds=cell_b, fill="#f8fafc", stroke=_INK, width=1.2)
        doc.add_element("rectangle", bounds=aligned[1], fill=_RUBY if mode == "cc" else _CYAN, stroke=_INK, width=1.2)
        doc.add_element("text", position=[cx0 + 36, cy0 + 100], text=lbl, size=11, stroke=_INK, width=1)

    doc.add_element("rectangle", bounds=[rx0 + 20, ry0 + 418, rx1 - 20, ry1 - 20], fill=_BG_DARK, stroke=_INK, width=1.2)
    doc.add_element("text", position=[rx0 + 34, ry0 + 448], text="HACKER ENVIRONMENT LOOP", size=12, stroke=_CYAN, width=1)
    doc.add_element("text", position=[rx0 + 34, ry0 + 474], text=f"32x32 1-bit Icon: {active_px} ink px -> 128 B", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[rx0 + 34, ry0 + 496], text="Direct parity: ZOE_GEM.RSC (68000)", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[rx0 + 34, ry0 + 518], text="ALIGN.TLS 9-way: P^2 = P idempotent", size=11, stroke=_AMBER, width=1)
    doc.add_element("text", position=[34, 670], text="Edit any Zoe signet icon via `/artline icon <ruby|gem3|atari|sm124|tetris|dos|hat|sprout|prism>` · 0 tokens", size=11, stroke=_SLATE, width=1)
    return doc, {"emblem": name, "active_ink_pixels": active_px, "iconblk_bytes": 128, "align_modes": 9}

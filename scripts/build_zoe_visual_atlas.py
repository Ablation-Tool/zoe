#!/usr/bin/env python3
"""
Clean-Room Scientific-Aesthetic & Physical Structural Visual Atlas Generator for Zoe (v0.9.2-beta).

Synthesizes 18 canonical mathematical archetypes grounded in:
  - Ernst Haeckel (Kunstformen der Natur: dihedral D_n radiolaria, ammonite logarithmic spiral,
    five-fold starfish/echinoderm, phyllotaxis botanical rosette)
  - Physical mechanical & optical engineering geometry (involute spur gear, optical prism,
    biconvex lens ring, hexagonal fastener, vernier caliper, open-end wrench, cylindrical vessel,
    handled mug, hinge bracket, coiled helical spring, book/rectangular housing, guitar contour,
    tripod stand, mechanical dial/clock)

Computes the EXACT same 32x32 Sobel + HoG-16 + Radial-8 + dHash-64 + aspect/symmetry visual
signature as `PatentReverseImageEngine.java` and `ScientificVisualAndPatentCore.swift`, exporting
a compact (< 15 KB) offline JSON prior pack for `VisionPriorStore`.

Zero external datasets, zero scraping, 100% deterministic & reproducible.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple

GRID = 32


def render_grid(fn: Callable[[float, float], float]) -> List[float]:
    """Renders a 32x32 luminance grid using 3x3 supersampling for crisp anti-aliased contours."""
    out = [0.0] * (GRID * GRID)
    for y in range(GRID):
        for x in range(GRID):
            acc = 0.0
            for sy in (-0.33, 0.0, 0.33):
                for sx in (-0.33, 0.0, 0.33):
                    nx = ((x + 0.5 + sx) / GRID) * 2.0 - 1.0
                    ny = ((y + 0.5 + sy) / GRID) * 2.0 - 1.0
                    acc += fn(nx, ny)
            out[y * GRID + x] = max(0.0, min(1.0, acc / 9.0))
    return out


def extract_signature(raw_gray: List[float]) -> Dict:
    """Bit-accurate mirror of PatentReverseImageEngine.extractFromGray32()."""
    min_l = min(raw_gray)
    max_l = max(raw_gray)
    span = max_l - min_l
    if span > 0.08 and (min_l > 0.02 or max_l < 0.98):
        gray = [(v - min_l) / span for v in raw_gray]
    else:
        gray = list(raw_gray)

    mag = [0.0] * (GRID * GRID)
    hog = [0.0] * 16
    radial = [0.0] * 8
    max_mag = 1e-5
    center = (GRID - 1) * 0.5
    max_r = center * 1.4142

    for y in range(1, GRID - 1):
        for x in range(1, GRID - 1):
            gx = (
                -gray[(y - 1) * GRID + (x - 1)]
                + gray[(y - 1) * GRID + (x + 1)]
                - 2.0 * gray[y * GRID + (x - 1)]
                + 2.0 * gray[y * GRID + (x + 1)]
                - gray[(y + 1) * GRID + (x - 1)]
                + gray[(y + 1) * GRID + (x + 1)]
            )
            gy = (
                -gray[(y - 1) * GRID + (x - 1)]
                - 2.0 * gray[(y - 1) * GRID + x]
                - gray[(y - 1) * GRID + (x + 1)]
                + gray[(y + 1) * GRID + (x - 1)]
                + 2.0 * gray[(y + 1) * GRID + x]
                + gray[(y + 1) * GRID + (x + 1)]
            )
            m = math.hypot(gx, gy)
            mag[y * GRID + x] = m
            if m > max_mag:
                max_mag = m
            ang = math.atan2(gy, gx)
            if ang < 0.0:
                ang += math.pi
            h_bin = min(15, max(0, int((ang / math.pi) * 16.0)))
            hog[h_bin] += m
            r_bin = min(7, max(0, int((math.hypot(x - center, y - center) / max_r) * 8.0)))
            radial[r_bin] += m

    thresh = max(0.08, max_mag * 0.24)
    min_x, max_x, min_y, max_y = GRID, 0, GRID, 0
    active = 0
    sym_num, sym_den = 0.0, 1e-5
    for y in range(1, GRID - 1):
        for x in range(1, GRID - 1):
            m = mag[y * GRID + x]
            if m >= thresh:
                active += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
            mm = mag[y * GRID + (GRID - 1 - x)]
            sym_num += min(m, mm)
            sym_den += max(m, mm)

    bbox_w = (max_x - min_x + 1) if max_x >= min_x else GRID
    bbox_h = (max_y - min_y + 1) if max_y >= min_y else GRID
    aspect = bbox_w / max(1.0, float(bbox_h))
    symmetry = max(0.0, min(1.0, sym_num / sym_den))
    density = active / float((GRID - 2) * (GRID - 2))
    total_hog = sum(hog) + 1e-5
    ortho = (hog[0] + hog[7] + hog[8] + hog[15]) / total_hog

    def l2(vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 1e-6 else vec

    hog = l2(hog)
    radial = l2(radial)

    grid9x8 = [[0.0] * 9 for _ in range(8)]
    for row in range(8):
        for col in range(9):
            acc = 0.0
            y0 = row * 4
            x0 = min(GRID - 3, (col * GRID) // 9)
            for dy in range(4):
                for dx in range(3):
                    acc += mag[(y0 + dy) * GRID + min(GRID - 1, x0 + dx)]
            grid9x8[row][col] = acc

    dhash = 0
    bit = 0
    for row in range(8):
        for col in range(8):
            if grid9x8[row][col] > grid9x8[row][col + 1]:
                dhash |= 1 << bit
            bit += 1

    return {
        "dHash": format(dhash, "x"),
        "aspect": round(aspect, 4),
        "sym": round(symmetry, 4),
        "ortho": round(ortho, 4),
        "density": round(density, 4),
        "hog": [round(v, 4) for v in hog],
        "radial": [round(v, 4) for v in radial],
    }


def archetypes() -> List[Tuple[str, str, str, Callable[[float, float], float]]]:
    """Returns (label, lineage_ref, scale_note, shape_fn)."""

    def gear(x: float, y: float) -> float:
        r = math.hypot(x, y)
        th = math.atan2(y, x)
        teeth = 0.66 + 0.11 * (1.0 if math.cos(12 * th) > 0 else -1.0)
        return 1.0 if (0.24 <= r <= teeth) else 0.0

    def prism(x: float, y: float) -> float:
        # Equilateral optical prism silhouette
        y_shift = y + 0.12
        return 1.0 if (-0.58 <= y_shift <= 0.65 and abs(x) <= (0.65 - y_shift) * 0.62) else 0.0

    def lens_ring(x: float, y: float) -> float:
        r = math.hypot(x, y)
        return 1.0 if (0.48 <= r <= 0.76) else 0.0

    def hex_nut(x: float, y: float) -> float:
        ax, ay = abs(x), abs(y)
        r_hex = max(ax * 0.866025 + ay * 0.5, ay)
        r_in = math.hypot(x, y)
        return 1.0 if (r_hex <= 0.72 and r_in >= 0.30) else 0.0

    def radiolaria(x: float, y: float) -> float:
        r = math.hypot(x, y)
        th = math.atan2(y, x)
        star = 0.50 + 0.30 * abs(math.cos(6 * th))
        ring = 0.24 <= r <= 0.34
        return 1.0 if (r <= star and not (0.14 <= r <= 0.22)) or ring else 0.0

    def ammonite_spiral(x: float, y: float) -> float:
        r = math.hypot(x, y)
        if r < 0.06 or r > 0.82:
            return 0.0
        th = math.atan2(y, x)
        # Logarithmic spiral bands r = a * exp(b * theta)
        for k in range(-2, 4):
            target = 0.14 * math.exp(0.24 * (th + 2 * math.pi * k))
            if abs(r - target) < 0.055:
                return 1.0
        return 0.0

    def botanical_rosette(x: float, y: float) -> float:
        r = math.hypot(x, y)
        th = math.atan2(y, x)
        petals = 0.42 + 0.34 * max(0.0, math.cos(5 * th))
        return 1.0 if r <= petals else 0.0

    def caliper(x: float, y: float) -> float:
        beam = abs(y + 0.15) <= 0.11 and -0.82 <= x <= 0.82
        jaw1 = -0.82 <= x <= -0.62 and -0.25 <= y <= 0.58
        jaw2 = -0.26 <= x <= -0.08 and -0.25 <= y <= 0.52
        return 1.0 if (beam or jaw1 or jaw2) else 0.0

    def wrench(x: float, y: float) -> float:
        shaft = abs(y) <= 0.11 and -0.55 <= x <= 0.55
        head_l = math.hypot(x + 0.62, y) <= 0.26 and not (x < -0.66 and abs(y) < 0.12)
        head_r = math.hypot(x - 0.62, y) <= 0.24 and math.hypot(x - 0.62, y) >= 0.11
        return 1.0 if (shaft or head_l or head_r) else 0.0

    def bottle_flask(x: float, y: float) -> float:
        body = abs(x) <= 0.34 and -0.10 <= y <= 0.78
        shoulder = abs(x) <= (0.14 + 0.20 * ((y + 0.40) / 0.30)) and -0.40 <= y < -0.10
        neck = abs(x) <= 0.14 and -0.78 <= y < -0.40
        return 1.0 if (body or shoulder or neck) else 0.0

    def handled_mug(x: float, y: float) -> float:
        cup = -0.52 <= x <= 0.26 and -0.56 <= y <= 0.62
        hr = math.hypot((x - 0.28) * 0.95, y - 0.02)
        handle = x >= 0.24 and (0.20 <= hr <= 0.34)
        return 1.0 if (cup or handle) else 0.0

    def watch_dial(x: float, y: float) -> float:
        r = math.hypot(x, y)
        bezel = 0.50 <= r <= 0.64
        strap = abs(x) <= 0.24 and 0.58 <= abs(y) <= 0.88
        hand1 = abs(x) <= 0.04 and -0.38 <= y <= 0.04
        hand2 = abs(y) <= 0.04 and -0.04 <= x <= 0.30
        return 1.0 if (bezel or strap or hand1 or hand2) else 0.0

    def helical_spring(x: float, y: float) -> float:
        if abs(x) > 0.46 or abs(y) > 0.78:
            return 0.0
        wave = math.sin((y * 15.0) + x * 2.2)
        return 1.0 if abs(wave) > 0.68 else 0.0

    def hinge_bracket(x: float, y: float) -> float:
        plate_l = -0.74 <= x <= -0.10 and -0.52 <= y <= 0.52
        plate_r = 0.10 <= x <= 0.74 and -0.52 <= y <= 0.52
        pin = abs(x) <= 0.10 and -0.62 <= y <= 0.62
        hole = math.hypot(x + 0.42, y - 0.22) < 0.09 or math.hypot(x - 0.42, y + 0.22) < 0.09
        return 1.0 if ((plate_l or plate_r or pin) and not hole) else 0.0

    def guitar_body(x: float, y: float) -> float:
        lower = math.hypot(x, (y - 0.34) * 1.05) <= 0.44
        upper = math.hypot(x, (y + 0.12) * 1.15) <= 0.31
        neck = abs(x) <= 0.075 and -0.88 <= y <= -0.15
        hole = math.hypot(x, y - 0.04) <= 0.11
        return 1.0 if ((lower or upper or neck) and not hole) else 0.0

    def tripod_stand(x: float, y: float) -> float:
        head = abs(x) <= 0.18 and -0.78 <= y <= -0.52
        leg_c = abs(x) <= 0.05 and -0.54 <= y <= 0.78
        leg_l = y >= -0.54 and y <= 0.80 and abs(x + (y + 0.54) * 0.44) <= 0.055
        leg_r = y >= -0.54 and y <= 0.80 and abs(x - (y + 0.54) * 0.44) <= 0.055
        return 1.0 if (head or leg_c or leg_l or leg_r) else 0.0

    def book_enclosure(x: float, y: float) -> float:
        outer = abs(x) <= 0.56 and abs(y) <= 0.74
        inner = abs(x) <= 0.44 and abs(y) <= 0.62
        spine = -0.44 <= x <= -0.34 and abs(y) <= 0.62
        return 1.0 if (outer and (not inner or spine)) else 0.0

    def biconvex_eyepiece(x: float, y: float) -> float:
        return 1.0 if (math.hypot(x - 0.55, y) <= 0.86 and math.hypot(x + 0.55, y) <= 0.86) else 0.0

    return [
        ("Involute Spur Gear", "CPC-F16H", "20–120 mm mechanical gear", gear),
        ("Optical Triangular Prism", "CPC-G02B", "25–60 mm optical prism", prism),
        ("Optical Lens Ring", "CPC-G02B", "40–82 mm lens ring", lens_ring),
        ("Hexagonal Fastener Nut", "CPC-F16B", "8–32 mm hex fastener", hex_nut),
        ("Haeckel Radiolaria Symmetry", "HAECKEL-1899", "D_12 radial biological symmetry", radiolaria),
        ("Ammonite Logarithmic Spiral", "HAECKEL-1899", "φ = 1.618 spiral geometry", ammonite_spiral),
        ("Five-Fold Botanical Rosette", "LAMARCK-1809", "Pentamerous floral symmetry", botanical_rosette),
        ("Precision Vernier Caliper", "CPC-G01B", "150–200 mm measurement tool", caliper),
        ("Open-End Combination Wrench", "CPC-B25B", "140–240 mm hand tool", wrench),
        ("Cylindrical Flask / Bottle", "CPC-B65D", "180–260 mm vessel", bottle_flask),
        ("Handled Mug / Cup", "CPC-A47G", "95–120 mm drinkware", handled_mug),
        ("Mechanical Watch / Dial", "CPC-G04B", "36–44 mm timepiece", watch_dial),
        ("Helical Coil Spring", "CPC-F16F", "30–120 mm compression spring", helical_spring),
        ("Mechanical Hinge Bracket", "CPC-E05D", "50–100 mm pivot hinge", hinge_bracket),
        ("Acoustic Guitar Silhouette", "CPC-G10D", "~1000 mm stringed instrument", guitar_body),
        ("Tripod Support Stand", "CPC-F16M", "200–1500 mm optical mount", tripod_stand),
        ("Bound Book / Framed Panel", "CPC-B42D", "150–297 mm rectangular folio", book_enclosure),
        ("Biconvex Optical Lens", "CPC-G02B", "30–75 mm lens cross-section", biconvex_eyepiece),
    ]


def build_atlas() -> Dict:
    entries = []
    for label, ref, dims, fn in archetypes():
        gray = render_grid(fn)
        sig = extract_signature(gray)
        entries.append(
            {
                "label": label,
                "source": "atlas_baseline",
                "patentRef": ref,
                "dims": dims,
                "count": 1,
                "updated": 0,
                "dHash": sig["dHash"],
                "aspect": sig["aspect"],
                "sym": sig["sym"],
                "ortho": sig["ortho"],
                "density": sig["density"],
                "kw": "",
                "summary": f"clean-room {ref} structural archetype",
                "hog": sig["hog"],
                "radial": sig["radial"],
            }
        )
    return {
        "version": 1,
        "lineage": "Haeckel (1899) · Lamarck (1809) · Clean-Room Physical CPC Geometry",
        "prototypes": entries,
    }


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out_path = root / "mobile" / "android" / "app" / "src" / "main" / "assets" / "zoe_visual_atlas.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atlas = build_atlas()
    payload = json.dumps(atlas, separators=(",", ":"))
    out_path.write_text(payload, encoding="utf-8")
    print(f"WROTE {out_path} ({len(atlas['prototypes'])} prototypes, {len(payload)} bytes)")


if __name__ == "__main__":
    main()

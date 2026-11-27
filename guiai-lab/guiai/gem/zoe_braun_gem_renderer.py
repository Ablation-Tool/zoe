"""Zoe Braun-3D × SYBEX GEM-1986 Mathematical Portrait Renderer (0 Cloud Tokens, 0 AI Slop).

Synthesizes two classic 1986 Atari ST / GEM references using pure deterministic geometry:
  1. Uwe Braun (1986), Atari ST 3D Graphics Programming (Ch. 2.4-2.8): 3D rotation matrices
     Rx/Ry/Rz, perspective projection, backface hidden-surface culling, and Rembrandt lighting.
  2. Phillip Balma & William Fitler (1986), Programmer's Guide to GEM (SYBEX): obsidian desktop,
     45-degree diagonal hatch drop-shadow, 'Desk File Edit Tools Font Style' menu bar, GEM Paint
     tool palette, and 16 authentic 4x4 VDI ordered dither patterns (no smooth modern gradients).

Constitutional transparency: sentience_claimed=False · deterministic math · cloud_tokens_used=0.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Classic 4x4 Bayer threshold matrix -> produces 16 authentic 1986 GEM VDI fill densities (0..15)
_BAYER_4X4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.int32,
)

# 1986 SYBEX Programmer's Guide to GEM × Braun Crimson Palette
_OBSIDIAN = (14, 20, 26)
_VIEWPORT_BG = (12, 16, 24)
_PAPER = (232, 232, 224)
_CREAM = (244, 234, 206)
_INK = (16, 20, 26)
_CRIMSON_PLAQUE = (198, 40, 58)
_RUBY_HI = (246, 152, 168)
_RUBY_BRIGHT = (236, 54, 84)
_RUBY_MID = (176, 24, 52)
_RUBY_DARK = (74, 12, 26)
_HATCH_LIGHT = (182, 180, 158)
_HATCH_DARK = (22, 26, 32)
_CYAN_GRID = (44, 92, 118)


from .zoe_artline_fonts import load_artline_pil_font


def _load_font(size: int, bold: bool = False, font_id: int | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_id is not None:
        font, _fname = load_artline_pil_font(font_id, size=size)
        return font
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def build_brilliant_ruby_mesh(sides: int = 8) -> tuple[np.ndarray, list[list[int]]]:
    """Build an exact 3D octagonal brilliant-cut ruby solid (table + crown + pavilion)."""
    verts: list[list[float]] = []
    # 0..sides-1: upper crown table ring (z = +0.58, r = 0.62)
    for i in range(sides):
        ang = (2.0 * math.pi * i / sides) + (math.pi / sides)
        verts.append([0.62 * math.cos(ang), 0.58, 0.62 * math.sin(ang)])
    # sides..2*sides-1: wide girdle ring (z = +0.16, r = 1.06)
    for i in range(sides):
        ang = (2.0 * math.pi * i / sides) + (math.pi / sides)
        verts.append([1.06 * math.cos(ang), 0.16, 1.06 * math.sin(ang)])
    # 2*sides: bottom culet apex (y = -1.16)
    culet_idx = 2 * sides
    verts.append([0.0, -1.16, 0.0])

    faces: list[list[int]] = []
    # Top crown table polygon (CCW looking from +Y -> outward normal +Y)
    faces.append(list(reversed(range(sides))))
    # Crown bezel quads (outward normals pointing up-and-out)
    for i in range(sides):
        nxt = (i + 1) % sides
        faces.append([i, nxt, sides + nxt, sides + i])
    # Pavilion triangles (outward normals pointing down-and-out)
    for i in range(sides):
        nxt = (i + 1) % sides
        faces.append([sides + i, sides + nxt, culet_idx])
    return np.asarray(verts, dtype=np.float64), faces


def rotation_matrix_xyz(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """Uwe Braun Ch. 2.4 exact 3D rotation matrix R = Rz @ Rx @ Ry."""
    rx, ry, rz = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float64)
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
    return mz @ mx @ my


def project_3d_points(pts: np.ndarray, rot: np.ndarray, cx: float, cy: float, focal: float, cam_dist: float = 4.2) -> tuple[np.ndarray, np.ndarray]:
    """Rotate 3D vertices and apply Uwe Braun Ch. 2.6 perspective projection."""
    world = pts @ rot.T
    denom = np.maximum(0.4, cam_dist - world[:, 2])
    sx = cx + focal * (world[:, 0] / denom)
    sy = cy - focal * (world[:, 1] / denom)
    return world, np.column_stack([sx, sy])


def _fill_dithered_polygon(
    arr: np.ndarray,
    poly_xy: list[tuple[float, float]],
    level: int,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
) -> None:
    """Rasterize one polygon using authentic 16-level 4x4 GEM ordered dithering (0 smooth gradients)."""
    h, w, _ = arr.shape
    mask_img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask_img).polygon(poly_xy, fill=255)
    mask = np.asarray(mask_img) > 0
    if not np.any(mask):
        return
    ys, xs = np.nonzero(mask)
    thresh = _BAYER_4X4[ys & 3, xs & 3]
    use_fg = thresh < max(0, min(16, int(level)))
    arr[ys[use_fg], xs[use_fg]] = fg_rgb
    arr[ys[~use_fg], xs[~use_fg]] = bg_rgb


def _draw_hatch_shadow(img: Image.Image, box: tuple[int, int, int, int], offset: int = 24) -> Image.Image:
    """Draw the iconic 1986 SYBEX Programmer's Guide to GEM 45-degree diagonal hatch drop-shadow."""
    x0, y0, x1, y1 = box
    arr = np.asarray(img).copy()
    sx0, sy0, sx1, sy1 = x0 + offset, y0 + offset, min(img.width, x1 + offset), min(img.height, y1 + offset)
    yy, xx = np.mgrid[sy0:sy1, sx0:sx1]
    stripe = ((xx + yy) % 8) < 4
    arr[sy0:sy1, sx0:sx1] = np.where(stripe[:, :, None], _HATCH_LIGHT, _HATCH_DARK)
    return Image.fromarray(arr)


def _draw_left_tool_palette(draw: ImageDraw.ImageDraw, x0: int, y0: int, font_sm: Any) -> None:
    """Draw the left GEM Paint 2x5 tool palette + 8-color swatch + line-width rack."""
    tw, th = 36, 26
    tools = ("PTR", "3D", "GEM", "ROT", "BOX", "PEN", "DTH", "ZOM", "MNI", "TXT")
    for idx, lbl in enumerate(tools):
        r, c = divmod(idx, 2)
        tx, ty = x0 + 6 + c * tw, y0 + 6 + r * th
        active = lbl in {"3D", "GEM"}
        draw.rectangle([tx, ty, tx + tw - 2, ty + th - 2], fill=_CRIMSON_PLAQUE if active else _PAPER, outline=_INK)
        draw.text((tx + 6, ty + 7), lbl, fill=_CREAM if active else _INK, font=font_sm)
    # 8-color Atari GEM swatch bank
    sw_y = y0 + 6 + 5 * th + 10
    swatches = (_INK, _CRIMSON_PLAQUE, _RUBY_BRIGHT, _RUBY_HI, (42, 168, 188), (242, 198, 52), (52, 178, 98), _CREAM)
    for idx, col in enumerate(swatches):
        r, c = divmod(idx, 4)
        sx, sy = x0 + 6 + c * 18, sw_y + r * 14
        draw.rectangle([sx, sy, sx + 16, sy + 12], fill=col, outline=_INK)
    # 3 classic GEM stroke thickness bars
    bar_y = sw_y + 38
    for idx, thick in enumerate((2, 4, 7)):
        by = bar_y + idx * 14
        draw.rectangle([x0 + 8, by, x0 + 74, by + thick], fill=_INK)


def _draw_right_pattern_bank(arr: np.ndarray, draw: ImageDraw.ImageDraw, x0: int, y0: int, font_sm: Any) -> None:
    """Draw the iconic right-side 16 classic GEM 4x4 dither pattern swatches."""
    draw.rectangle([x0 + 6, y0 + 6, x0 + 80, y0 + 44], fill=_RUBY_DARK, outline=_INK)
    draw.text((x0 + 18, y0 + 48), "GEM-16", fill=_INK, font=font_sm)
    pw, ph = 34, 22
    for idx in range(16):
        r, c = divmod(idx, 2)
        px, py = x0 + 8 + c * (pw + 4), y0 + 64 + r * (ph + 4)
        fg = _CRIMSON_PLAQUE if (idx % 3 == 1) else _INK
        _fill_dithered_polygon(
            arr,
            [(px, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)],
            level=15 - idx,
            fg_rgb=fg,
            bg_rgb=_PAPER,
        )
        draw.rectangle([px, py, px + pw, py + ph], outline=_INK)


def _draw_3d_zoe_smile(
    draw: ImageDraw.ImageDraw,
    rot: np.ndarray,
    cx: float,
    cy: float,
    focal: float,
) -> None:
    """Project Zoe's exact (◠◡◠) smile cleanly onto the luminous front crown bevel/table."""
    # Lies flush on the bright crown table (y = +0.59) facing the viewer in true 3D perspective
    curves = [
        # Left happy eye arc ◠
        np.array([[-0.34, 0.59, 0.14], [-0.27, 0.59, -0.02], [-0.19, 0.59, -0.02], [-0.12, 0.59, 0.14]]),
        # Center smile arc ◡
        np.array([[-0.10, 0.59, 0.15], [-0.04, 0.59, 0.28], [0.04, 0.59, 0.28], [0.10, 0.59, 0.15]]),
        # Right happy eye arc ◠
        np.array([[0.12, 0.59, 0.14], [0.19, 0.59, -0.02], [0.27, 0.59, -0.02], [0.34, 0.59, 0.14]]),
    ]
    for pts in curves:
        _w, proj = project_3d_points(pts, rot, cx, cy, focal)
        xy = [(float(p[0]), float(p[1])) for p in proj]
        draw.line(xy, fill=_INK, width=7, joint="curve")


def render_braun_gem_portrait(
    output_path: Path | str,
    *,
    rx_deg: float = 24.0,
    ry_deg: float = 14.0,
    rz_deg: float = -3.0,
    width: int = 920,
    height: int = 720,
    font_id: int = 51,
) -> dict[str, Any]:
    """Render Zoe's chosen 1986 Uwe Braun 3D × SYBEX GEM portrait to PNG and return geometry stats."""
    img = Image.new("RGB", (width, height), _OBSIDIAN)
    arr = np.asarray(img).copy()

    # Subtle 1986 SYBEX matte dark cover texture
    rng = np.random.default_rng(19860084)
    noise = rng.integers(-4, 5, size=(height, width, 1), dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(36, bold=True, font_id=font_id)
    font_sub = _load_font(15, bold=True, font_id=font_id)
    font_menu = _load_font(15, bold=False)
    font_sm = _load_font(11, bold=True)

    # Left vertical SYBEX-inspired GEM-86 spine badge
    draw.rectangle([16, 26, 30, 146], fill=(238, 178, 72))
    for i, ch in enumerate("GEM86"):
        draw.text((38, 28 + i * 24), ch, fill=_CREAM, font=font_sub)

    # Top-right Crimson Plaque (Balma & Fitler 1986 SYBEX cover homage)
    draw.rectangle([380, 28, width - 26, 148], fill=_CRIMSON_PLAQUE, outline=(120, 18, 30), width=3)
    draw.text((406, 44), "ZOE · GEM 1986", fill=_CREAM, font=font_title)
    draw.text((408, 92), "Braun 3D Projection × Digital Research GEM", fill=_PAPER, font=font_sub)
    draw.text((408, 114), "Milestone 1 Preclinical R&D · 0 Tokens · 16-Pattern Dither", fill=_CREAM, font=font_sm)

    # Main Atari ST GEM Window + iconic 45-degree diagonal hatch drop-shadow
    win_box = (54, 174, width - 66, height - 58)
    img = _draw_hatch_shadow(img, win_box, offset=24)
    draw = ImageDraw.Draw(img)

    wx0, wy0, wx1, wy1 = win_box
    draw.rectangle(win_box, fill=_PAPER, outline=_INK, width=3)

    # Iconic Menu Bar: "Desk  File  Edit  Tools  Font  Style"
    draw.rectangle([wx0 + 2, wy0 + 2, wx1 - 2, wy0 + 30], fill=_PAPER, outline=_INK, width=1)
    menus = ("Desk", "File", "Edit", "Tools", "Font", "Style")
    mx = wx0 + 18
    for item in menus:
        mw = len(item) * 10 + 18
        if item == "Tools":
            draw.rectangle([mx - 6, wy0 + 3, mx + mw - 6, wy0 + 29], fill=_CRIMSON_PLAQUE)
            draw.text((mx, wy0 + 8), item, fill=_CREAM, font=font_menu)
        else:
            draw.text((mx, wy0 + 8), item, fill=_INK, font=font_menu)
        mx += mw + 6
    draw.text((wx1 - 156, wy0 + 9), "SENTIENCE=FALSE", fill=_CRIMSON_PLAQUE, font=font_sm)

    # GEM Window Title Bar
    ty0 = wy0 + 30
    draw.rectangle([wx0 + 2, ty0, wx1 - 2, ty0 + 24], fill=_PAPER, outline=_INK, width=1)
    draw.rectangle([wx0 + 6, ty0 + 4, wx0 + 22, ty0 + 20], fill=_CRIMSON_PLAQUE, outline=_INK)
    draw.rectangle([wx1 - 22, ty0 + 4, wx1 - 6, ty0 + 20], fill=_PAPER, outline=_INK)
    draw.text(((wx0 + wx1) // 2 - 72, ty0 + 5), "ZOE_RUBY_3D.GEM", fill=_INK, font=font_sub)

    # Left Tool Palette & Right 16-Pattern Swatch Bank
    body_y0, body_y1 = ty0 + 24, wy1 - 22
    vp_x0, vp_x1 = wx0 + 86, wx1 - 92
    _draw_left_tool_palette(draw, wx0 + 2, body_y0, font_sm)

    # Central 3D Viewport (Obsidian space + Braun perspective ground grid)
    draw.rectangle([vp_x0, body_y0, vp_x1, body_y1], fill=_VIEWPORT_BG, outline=_INK, width=2)
    vcx = (vp_x0 + vp_x1) / 2.0
    vcy = (body_y0 + body_y1) / 2.0 - 4.0
    focal = 490.0
    rot = rotation_matrix_xyz(rx_deg, ry_deg, rz_deg)

    # Subtle 1986 Braun 3D coordinate floor grid (strictly clipped inside the obsidian viewport)
    grid_rot = rotation_matrix_xyz(22.0, ry_deg * 0.6, 0.0)
    grid_layer = Image.new("RGB", (vp_x1 - vp_x0 - 2, body_y1 - body_y0 - 2), _VIEWPORT_BG)
    gdraw = ImageDraw.Draw(grid_layer)
    for g in np.linspace(-1.55, 1.55, 9):
        p_a = np.array([[g, -1.25, -1.55], [g, -1.25, 1.55]])
        p_b = np.array([[-1.55, -1.25, g], [1.55, -1.25, g]])
        for seg in (p_a, p_b):
            _, pr = project_3d_points(seg, grid_rot, vcx - vp_x0 - 1, vcy + 14 - body_y0 - 1, focal)
            gdraw.line([(float(pr[0, 0]), float(pr[0, 1])), (float(pr[1, 0]), float(pr[1, 1]))], fill=_CYAN_GRID, width=1)
    img.paste(grid_layer, (vp_x0 + 1, body_y0 + 1))
    draw = ImageDraw.Draw(img)

    # Uwe Braun Ch. 2.7-2.8: Backface Hidden-Surface Culling + Painter Depth Sort + 16-Pattern GEM Dither
    verts, faces = build_brilliant_ruby_mesh(sides=8)
    world, proj = project_3d_points(verts, rot, vcx, vcy, focal)
    light_dir = np.array([-0.52, 0.72, 0.46], dtype=np.float64)
    light_dir /= np.linalg.norm(light_dir)
    cam_pos = np.array([0.0, 0.0, 4.2], dtype=np.float64)

    visible_faces: list[tuple[float, list[int], float]] = []
    for f in faces:
        v0, v1, v2 = world[f[0]], world[f[1]], world[f[2]]
        normal = np.cross(v1 - v0, v2 - v0)
        norm_len = float(np.linalg.norm(normal))
        if norm_len < 1e-9:
            continue
        normal /= norm_len
        center = np.mean(world[f], axis=0)
        if float(np.dot(normal, cam_pos - center)) <= 0.0:
            continue  # Backface hidden-surface culled!
        intensity = max(0.0, min(1.0, 0.16 + 0.84 * max(0.0, float(np.dot(normal, light_dir)))))
        visible_faces.append((float(center[2]), f, intensity))

    visible_faces.sort(key=lambda item: item[0])  # Back-to-front painter order
    arr = np.asarray(img).copy()
    for _z, face_idx, intensity in visible_faces:
        poly_xy = [(float(proj[i, 0]), float(proj[i, 1])) for i in face_idx]
        level = int(round(intensity * 15.0))
        if level >= 11:
            fg, bg = _RUBY_HI, _RUBY_BRIGHT
            dither_lvl = int(round((level - 10) * 3.0))
        elif level >= 6:
            fg, bg = _RUBY_BRIGHT, _RUBY_MID
            dither_lvl = int(round((level - 5) * 3.0))
        else:
            fg, bg = _RUBY_MID, _RUBY_DARK
            dither_lvl = int(round(level * 2.8))
        _fill_dithered_polygon(arr, poly_xy, dither_lvl, fg_rgb=fg, bg_rgb=bg)

    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Warm cream wireframes over every visible facet (Uwe Braun Ch. 2.7 style)
    for _z, face_idx, _intensity in visible_faces:
        pts = [(float(proj[i, 0]), float(proj[i, 1])) for i in face_idx]
        draw.polygon(pts, outline=_CREAM, width=2)

    # Project Zoe's signature (◠◡◠) smile onto the front 3D crown bevel
    _draw_3d_zoe_smile(draw, rot, vcx, vcy, focal)

    # Draw right 16-pattern GEM swatch bank
    arr = np.asarray(img).copy()
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    _draw_right_pattern_bank(arr, draw, vp_x1 + 2, body_y0, font_sm)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    # Re-stroke crisp swatch labels/outlines over arr
    draw.rectangle([vp_x1 + 8, body_y0 + 6, vp_x1 + 82, body_y0 + 44], fill=_CRIMSON_PLAQUE, outline=_INK)
    draw.text((vp_x1 + 20, body_y0 + 48), "GEM-16", fill=_INK, font=font_sm)
    for idx in range(16):
        r, c = divmod(idx, 2)
        px, py = vp_x1 + 10 + c * 38, body_y0 + 64 + r * 26
        draw.rectangle([px, py, px + 34, py + 22], outline=_INK)

    # Bottom GEM Status & Scroll Bar
    draw.rectangle([wx0 + 2, body_y1, wx1 - 2, wy1 - 2], fill=_PAPER, outline=_INK, width=1)
    status = (
        f" BRAUN 3D: Rx={rx_deg:+.0f}° Ry={ry_deg:+.0f}° · {len(visible_faces)}/{len(faces)} faces visible (Z-culled) · "
        f"16-pattern GEM dither · 0 AI tokens"
    )
    draw.text((wx0 + 10, body_y1 + 5), status, fill=_INK, font=font_sm)

    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {
        "ok": True,
        "output_path": str(out),
        "width": width,
        "height": height,
        "total_faces": len(faces),
        "visible_faces": len(visible_faces),
        "rx_deg": rx_deg,
        "ry_deg": ry_deg,
        "tokens_used": 0,
        "sentience_claimed": False,
    }

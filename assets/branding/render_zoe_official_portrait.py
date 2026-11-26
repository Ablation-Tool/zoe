#!/usr/bin/env python3
"""Render Zoe's Official Portrait branding assets (GitHub 1280x640 social preview & avatars).

Preserves the original red-and-white ruby-sprout GEM emblem (`zoe-gem.{png,svg}`)
as Zoe's origin/historical emblem while generating official portrait derivatives from
`assets/branding/zoe-creative-intelligence-portrait.jpg`.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BRANDING_DIR = Path(__file__).resolve().parent
SOURCE = BRANDING_DIR / "zoe-creative-intelligence-portrait.jpg"
CANONICAL = BRANDING_DIR / "zoe-official-portrait.jpg"
SOCIAL_PREVIEW = BRANDING_DIR / "zoe-github-social-preview-1280x640.png"
AVATAR_SIZES = (512, 256, 128)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_social_preview(src: Image.Image, out_path: Path) -> None:
    """Create a museum-grade 1280x640 (2:1) pure-portrait GitHub Social Preview (zero text/chrome)."""
    W, H = 1280, 640
    sw, sh = src.size  # 1116 x 2000

    # Upper portrait crop showing full floral crown through crimson diamond GEM clasp + tassels
    crop_h = int(sh * 0.815)
    upper = src.crop((0, 0, sw, crop_h)).convert("RGB")

    # Build a pure deep botanical teal textured wall canvas from the clean upper-right teal corner
    tile = src.crop((int(sw * 0.78), 0, sw, int(sh * 0.14))).convert("RGB")
    tile_h = tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    tile_v = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    tile_hv = tile_h.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    tw, th = tile.size
    quad = Image.new("RGB", (tw * 2, th * 2))
    quad.paste(tile, (0, 0))
    quad.paste(tile_h, (tw, 0))
    quad.paste(tile_v, (0, th))
    quad.paste(tile_hv, (tw, th))

    canvas = Image.new("RGB", (W, H))
    for y in range(0, H, quad.height):
        for x in range(0, W, quad.width):
            canvas.paste(quad, (x, y))
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=3.5))

    # Rich gallery radial vignette in matching deep botanical teal
    arr = np.asarray(canvas, dtype=np.float32)
    xs = np.linspace(-1.0, 1.0, W, dtype=np.float32)[None, :]
    ys = np.linspace(-1.0, 1.0, H, dtype=np.float32)[:, None]
    vig = 0.88 - 0.36 * np.clip((xs * xs * 0.78 + ys * ys * 0.42), 0.0, 1.0)
    arr = np.clip(arr * vig[:, :, None], 0, 255).astype(np.uint8)
    canvas = Image.fromarray(arr, mode="RGB")

    # Scale portrait cleanly to sit inside a crisp museum matte with subtle champagne-gold border
    pad_y = 18
    new_h = H - 2 * pad_y
    new_w = round(upper.width * (new_h / upper.height))
    portrait = upper.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x_off = (W - new_w) // 2

    # Soft drop halo + hairline antique gold museum frame around the portrait plate
    draw = ImageDraw.Draw(canvas)
    gold = (196, 155, 68)
    gold_dim = (132, 108, 56)
    draw.rectangle((x_off - 10, pad_y - 10, x_off + new_w + 9, pad_y + new_h + 9), outline=gold_dim, width=1)
    draw.rectangle((x_off - 4, pad_y - 4, x_off + new_w + 3, pad_y + new_h + 3), outline=gold, width=2)

    canvas.paste(portrait, (x_off, pad_y))
    canvas.save(out_path, format="PNG", optimize=True)


def build_square_avatar(src: Image.Image, size: int, out_path: Path) -> None:
    """Create a centered square upper-portrait avatar (crown through floral neckline)."""
    sw, sh = src.size
    # Square crop anchored near top so floral crown & face are centered cleanly
    top = int(sh * 0.02)
    sq = src.crop((0, top, sw, min(sh, top + sw))).convert("RGB")
    resized = sq.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(out_path, format="PNG", optimize=True)


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing portrait source: {SOURCE}")
    shutil.copyfile(SOURCE, CANONICAL)
    with Image.open(CANONICAL) as src:
        build_social_preview(src, SOCIAL_PREVIEW)
        for sz in AVATAR_SIZES:
            build_square_avatar(src, sz, BRANDING_DIR / f"zoe-official-avatar-{sz}.png")
    print(f"zoe-official-portrait.jpg sha256={_sha256(CANONICAL)}")
    print(f"zoe-github-social-preview-1280x640.png sha256={_sha256(SOCIAL_PREVIEW)}")
    for sz in AVATAR_SIZES:
        p = BRANDING_DIR / f"zoe-official-avatar-{sz}.png"
        print(f"{p.name} sha256={_sha256(p)}")


if __name__ == "__main__":
    main()

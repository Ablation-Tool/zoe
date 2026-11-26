"""Pure-stdlib P6 PPM parser, pixel region sampler, and Amber/geometry checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _next_ppm_token(data: bytes, pos: int) -> tuple[str, int]:
    """Read next whitespace-delimited ASCII header token, skipping # comments."""
    n = len(data)
    while pos < n:
        byte = data[pos]
        if byte in (9, 10, 13, 32):
            pos += 1
        elif byte == 35:  # '#' comment to end of line
            nl = data.find(b"\n", pos)
            pos = n if nl < 0 else nl + 1
        else:
            break
    start = pos
    while pos < n and data[pos] not in (9, 10, 13, 32, 35):
        pos += 1
    if start == pos:
        raise ValueError("Unexpected EOF in PPM header")
    return data[start:pos].decode("ascii"), pos


def read_ppm(path: str | Path) -> tuple[int, int, bytes]:
    """Parse a binary P6 PPM image into (width, height, rgb_bytes)."""
    raw = Path(path).read_bytes()
    magic, pos = _next_ppm_token(raw, 0)
    if magic != "P6":
        raise ValueError(f"Unsupported PPM magic: {magic!r}")
    w_tok, pos = _next_ppm_token(raw, pos)
    h_tok, pos = _next_ppm_token(raw, pos)
    max_tok, pos = _next_ppm_token(raw, pos)
    width, height, maxval = int(w_tok), int(h_tok), int(max_tok)
    if width <= 0 or height <= 0 or maxval != 255:
        raise ValueError(f"Invalid PPM dimensions/maxval: {width}x{height} max={maxval}")
    if pos >= len(raw) or raw[pos] not in (9, 10, 13, 32):
        raise ValueError("Missing single whitespace byte before PPM pixel data")
    rgb = raw[pos + 1 :]
    expected = width * height * 3
    if len(rgb) != expected:
        raise ValueError(f"PPM payload length {len(rgb)} != expected {expected}")
    return width, height, rgb


def sample_pixel(width: int, rgb: bytes, x: int, y: int) -> tuple[int, int, int]:
    """Return (R, G, B) tuple at pixel coordinate (x, y) with strict bounds checking."""
    if width <= 0 or len(rgb) % (width * 3) != 0:
        raise ValueError(f"Invalid width {width} for rgb buffer length {len(rgb)}")
    height = len(rgb) // (width * 3)
    if not (0 <= x < width and 0 <= y < height):
        raise IndexError(f"Pixel ({x}, {y}) out of bounds for {width}x{height} image")
    idx = (y * width + x) * 3
    return rgb[idx], rgb[idx + 1], rgb[idx + 2]


def _clamp_box(width: int, height: int, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Clamp (x0, y0, x1, y1) box strictly within image bounds."""
    x0 = max(0, min(width - 1, box[0]))
    y0 = max(0, min(height - 1, box[1]))
    x1 = max(x0 + 1, min(width, box[2]))
    y1 = max(y0 + 1, min(height, box[3]))
    return x0, y0, x1, y1


def region_stats(
    width: int,
    height: int,
    rgb: bytes,
    box: tuple[int, int, int, int] | None = None,
    step: int = 2,
) -> dict[str, Any]:
    """Compute mean RGB channels, luminance, and non-black coverage over box."""
    x0, y0, x1, y1 = _clamp_box(width, height, box or (0, 0, width, height))
    stride = max(1, step) * 3
    sum_r = sum_g = sum_b = count = non_black = 0
    for y in range(y0, y1, max(1, step)):
        row_start = (y * width + x0) * 3
        row_end = (y * width + x1) * 3
        rs = rgb[row_start:row_end:stride]
        gs = rgb[row_start + 1 : row_end : stride]
        bs = rgb[row_start + 2 : row_end : stride]
        sum_r += sum(rs)
        sum_g += sum(gs)
        sum_b += sum(bs)
        count += len(rs)
        non_black += sum(1 for r, g, b in zip(rs, gs, bs) if r > 12 or g > 12 or b > 12)
    denom = max(1, count)
    mr, mg, mb = sum_r / denom, sum_g / denom, sum_b / denom
    return {
        "samples": count,
        "mean_r": round(mr, 2),
        "mean_g": round(mg, 2),
        "mean_b": round(mb, 2),
        "luminance_mean": round(0.299 * mr + 0.587 * mg + 0.114 * mb, 2),
        "non_black_ratio": round(non_black / denom, 4),
    }


def is_non_blank(width: int, height: int, rgb: bytes, min_non_black: float = 0.05) -> bool:
    """Return True if at least min_non_black fraction of sampled pixels are non-black."""
    stats = region_stats(width, height, rgb, step=4)
    return float(stats["non_black_ratio"]) >= min_non_black


def diff_ratio(rgb_a: bytes, rgb_b: bytes, stride_pixels: int = 4) -> float:
    """Return fraction of sampled pixels whose RGB values differ between two buffers."""
    if len(rgb_a) != len(rgb_b):
        raise ValueError(f"Buffer length mismatch: {len(rgb_a)} vs {len(rgb_b)}")
    step = max(1, stride_pixels) * 3
    a_r, b_r = rgb_a[0::step], rgb_b[0::step]
    a_g, b_g = rgb_a[1::step], rgb_b[1::step]
    a_b, b_b = rgb_a[2::step], rgb_b[2::step]
    diffs = sum(1 for x, y in zip(zip(a_r, a_g, a_b), zip(b_r, b_g, b_b)) if x != y)
    return diffs / max(1, len(a_r))


def is_amber_crt_dominant(width: int, height: int, rgb: bytes) -> bool:
    """Return True if image exhibits 1985 P3 Amber CRT phosphor dominance (R > G >> B)."""
    st = region_stats(width, height, rgb, step=4)
    mr, mg, mb = float(st["mean_r"]), float(st["mean_g"]), float(st["mean_b"])
    return mr > 15.0 and mr > mg and mg > mb and mb <= mg * 0.65


def assert_portrait_geometry(width: int, height: int) -> None:
    """Assert portrait ('flip long ways') dimensions: height >= width."""
    if height < width:
        raise AssertionError(f"Expected portrait geometry (height >= width), got {width}x{height}")


def assert_micro_hud_geometry(width: int, height: int, max_dim: int = 400) -> None:
    """Assert micro-HUD headlamp dimensions fit within max_dim."""
    if width > max_dim or height > max_dim:
        raise AssertionError(f"Expected micro-HUD <= {max_dim}px, got {width}x{height}")

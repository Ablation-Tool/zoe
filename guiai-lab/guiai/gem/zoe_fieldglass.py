#!/usr/bin/env python3
"""Zoe Fieldglass — Phone-to-Telemetry & Botanical Specimen Field Instrument (0 Cloud Tokens).

Bridges real-world 4K phone captures into Zoe's native GEM stack:
  1. Laplacian focus-scored 4K frame extraction
  2. 4-corner perspective homography + Gaussian illumination division (shadow eraser)
  3. Two-tone contour-traced scalable vector SVG + 2x4 Unicode Braille via `zoe_braille_studio`
  4. Real-time Kloster A_tau(p_t) = sum_x 1[p_t(x) > tau] telemetry overlay video
  5. Direct `guiai.gem.chiasm` Causal Chiasm & Persistent Filtration Tomography GEM Scene SVG
  6. Range-capable loopback showcase server (127.0.0.1) & USB ADB Pixel pusher

Standalone companion repo & live interactive showcase:
  https://github.com/Nicholas-Michael-Kloster/fieldglass
  https://nicholas-michael-kloster.github.io/fieldglass/

Constitutional invariants:
  auto_flash_allowed=False · clinical_action_authorized=False
  flight_control_authorized=False · sentience_claimed=False · tokens_used=0
"""

from __future__ import annotations

import argparse
import hashlib
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from .chiasm import (
    CONTRACT as CHIASM_CONTRACT,
    _line,
    _polyline,
    _rectangle,
    _text,
    causal_chiasm,
    hud_stamp_objects,
    persistent_filtration_tomography,
)
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT
from .render import write_svg
from .visual_language import woven_diamond
from .zoe_braille_studio import BrailleCanvas

FIELDGLASS_CONTRACT = "zoe-fieldglass/v1"
FIELDGLASS_SHOWCASE_URL = "https://nicholas-michael-kloster.github.io/fieldglass/"
FIELDGLASS_REPO_URL = "https://github.com/Nicholas-Michael-Kloster/fieldglass"

TONAL_STATES: tuple[str, ...] = (
    "deep_shadow",
    "ink_linework",
    "dark_midtone",
    "botanical_mid",
    "warm_sepia",
    "aged_paper",
    "bright_cream",
    "paper_highlight",
)

_DOT_BITS: tuple[tuple[int, int], ...] = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_BAYER_4X4 = np.array(
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
    dtype=np.float32,
) / 16.0

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def a_tau(p: np.ndarray | Sequence[float], tau: float) -> int:
    """Strict superlevel-set volume: A_tau(p) = |{x in X : p(x) > tau}|."""
    return int(np.sum(np.asarray(p, dtype=np.float64) > float(tau)))


def shannon_h1(p: np.ndarray | Sequence[float]) -> float:
    arr = np.asarray(p, dtype=np.float64)
    nz = arr[arr > 0]
    return float(-np.sum(nz * np.log2(nz))) if len(nz) else 0.0


def renyi_h2(p: np.ndarray | Sequence[float]) -> float:
    arr = np.asarray(p, dtype=np.float64)
    return float(-math.log2(max(float(np.sum(arr * arr)), 1e-12)))


def quartic_purity_m4(p: np.ndarray | Sequence[float]) -> float:
    arr = np.asarray(p, dtype=np.float64)
    return float(np.sum(arr ** 4) ** 0.25)


def normalize_dist(d: dict[str, float]) -> dict[str, float]:
    clean = {k: max(float(v), 1e-9) for k, v in d.items()}
    total = sum(clean.values())
    norm = {k: v / total for k, v in clean.items()}
    max_k = max(norm, key=lambda k: norm[k])
    norm[max_k] = 1.0 - sum(v for k, v in norm.items() if k != max_k)
    return norm


def luminance_to_8state(p256: np.ndarray) -> dict[str, float]:
    arr = np.asarray(p256, dtype=np.float64)
    if arr.shape[0] != 256:
        raise ValueError(f"expected 256-bin luminance histogram, got {arr.shape}")
    return normalize_dist({
        name: float(arr[idx * 32 : (idx + 1) * 32].sum())
        for idx, name in enumerate(TONAL_STATES)
    })


def laplacian_sharpness(image: Image.Image) -> float:
    gray = image.convert("L")
    w, h = gray.size
    crop = gray.crop((int(w * 0.10), int(h * 0.12), int(w * 0.92), int(h * 0.88)))
    crop.thumbnail((720, 1280))
    return float(ndimage.laplace(np.asarray(crop, dtype=np.float32)).var())


def extract_sharpest_frame(
    video_path: str | Path,
    out_png: str | Path,
    *,
    start_sec: float = 0.0,
    duration_sec: float = 2.0,
    sample_fps: int = 8,
) -> dict[str, Any]:
    src = Path(video_path).expanduser().resolve()
    dst = Path(out_png).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cdir = Path(tmp)
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", f"{start_sec:.3f}", "-t", f"{duration_sec:.3f}",
                "-i", str(src), "-vf", f"fps={sample_fps}", "-q:v", "2",
                str(cdir / "cand_%04d.jpg"),
            ],
            check=True,
        )
        cands = sorted(cdir.glob("cand_*.jpg"))
        if not cands:
            raise RuntimeError(f"No frames extracted from {src}")
        scored = []
        for idx, p in enumerate(cands):
            with Image.open(p) as im:
                scored.append((laplacian_sharpness(im), start_sec + idx / float(sample_fps)))
        best_sc, best_ts = max(scored, key=lambda x: x[0])
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{best_ts:.3f}", "-i", str(src), "-frames:v", "1", "-y", str(dst)],
        check=True,
    )
    with Image.open(dst) as out_im:
        size = list(out_im.size)
    return {"out_png": str(dst), "timestamp_sec": round(best_ts, 3), "sharpness": round(best_sc, 2), "size": size}


def perspective_deskew(
    image: Image.Image,
    corners_norm: Sequence[tuple[float, float]],
    *,
    out_size: tuple[int, int] = (1500, 2250),
) -> Image.Image:
    if len(corners_norm) != 4:
        raise ValueError("corners_norm must be 4 normalized (x, y) points: TL, TR, BR, BL")
    w, h = image.size
    src_pts = [(x * w, y * h) for x, y in corners_norm]
    ow, oh = out_size
    dst_pts = [(0.0, 0.0), (float(ow), 0.0), (float(ow), float(oh)), (0.0, float(oh))]
    matrix = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        matrix.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        matrix.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
    coeffs = [float(c) for c in np.linalg.solve(np.asarray(matrix, dtype=np.float64), np.asarray([c for pt in src_pts for c in pt], dtype=np.float64))]
    return image.transform((ow, oh), Image.Transform.PERSPECTIVE, coeffs, resample=Image.Resampling.BICUBIC)


def clean_illumination(
    image: Image.Image,
    *,
    sigma: float = 45.0,
    paper_cutoff: float = 0.925,
    ink_floor: float = 0.36,
    gamma: float = 1.18,
) -> tuple[np.ndarray, Image.Image, Image.Image]:
    """Erase uneven lamp shadows via Gaussian background division."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    bg = ndimage.gaussian_filter(gray, sigma=sigma)
    norm = np.clip(gray / np.maximum(bg, 15.0), 0.0, 1.15)
    ink = np.power(np.clip((paper_cutoff - norm) / max(1e-3, paper_cutoff - ink_floor), 0.0, 1.0), gamma)
    paper_rgb = np.array([246.0, 241.0, 228.0], dtype=np.float32)
    ink_rgb = np.array([26.0, 24.0, 21.0], dtype=np.float32)
    archival = (paper_rgb * (1.0 - ink[..., None]) + ink_rgb * ink[..., None]).clip(0, 255).astype(np.uint8)
    bw = ((1.0 - ink) * 255.0).clip(0, 255).astype(np.uint8)
    return ink, Image.fromarray(archival), Image.fromarray(bw)


def ink_to_braille_canvas(ink_map: np.ndarray, *, cols: int = 72) -> list[str]:
    """Render a [0..1] ink field onto Zoe's native 2x4 `BrailleCanvas` with Bayer 4x4 dithering."""
    cols = max(16, min(120, int(cols)))
    ah, aw = ink_map.shape
    w_px = cols * 2
    h_px = max(8, (int(round(w_px * (ah / max(1, aw)))) // 4) * 4)
    boosted = ndimage.grey_dilation(ink_map, size=(3, 3))
    small = np.asarray(
        Image.fromarray((boosted * 255.0).clip(0, 255).astype(np.uint8)).resize((w_px, h_px), Image.Resampling.BOX),
        dtype=np.float32,
    ) / 255.0
    canvas = BrailleCanvas(w_px, h_px)
    for y in range(h_px):
        for x in range(w_px):
            v = float(small[y, x])
            on = (v > 0.24) or (v > 0.09 and v > 0.09 + 0.18 * _BAYER_4X4[y & 3, x & 3])
            canvas.set_px(x, y, on)
    return canvas.render()


def trace_ink_to_svg(
    ink_map: np.ndarray,
    svg_path: str | Path,
    *,
    title: str = "ZOE FIELDGLASS SPECIMEN",
    subtitle: str = "Contour-traced archival botanical vector",
    vec_width: int = 680,
) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dst = Path(svg_path).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    mask = ink_map > 0.16
    labeled, n_comp = ndimage.label(mask)
    if n_comp > 0:
        sizes = ndimage.sum(mask, labeled, range(1, n_comp + 1))
        cleaned = np.where((sizes >= 4)[labeled - 1] & mask, ink_map, 0.0)
    else:
        cleaned = ink_map
    ah, aw = cleaned.shape
    vec_h = max(16, int(round(ah * (vec_width / max(1, aw)))))
    small = np.asarray(
        Image.fromarray((cleaned * 255.0).clip(0, 255).astype(np.uint8)).resize((vec_width, vec_h), Image.Resampling.BOX),
        dtype=np.float32,
    ) / 255.0
    smooth = ndimage.gaussian_filter(small, sigma=0.55)
    fig = plt.figure(figsize=(8.0, 11.2), dpi=100, facecolor="#f6f1e4")
    ax = fig.add_axes([0.05, 0.10, 0.90, 0.85], facecolor="#f6f1e4")
    ax.contourf(smooth, levels=[0.075, 0.21, 1.2], colors=["#786f5f", "#1b1916"])
    ax.set_xlim(0, vec_width - 1)
    ax.set_ylim(vec_h - 1, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patches.append(plt.Rectangle((0.028, 0.022), 0.944, 0.956, fill=False, edgecolor="#8c7f68", linewidth=1.2, transform=fig.transFigure))
    fig.text(0.5, 0.064, title, ha="center", va="center", fontsize=11.5, fontweight="bold", family="serif", color="#1b1916")
    fig.text(0.5, 0.042, subtitle, ha="center", va="center", fontsize=8.2, style="italic", family="serif", color="#524a3d")
    fig.savefig(dst, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)
    return dst


def build_fieldglass_chiasm_scene(
    episodes_8: Sequence[dict[str, float]],
    per_sec_a004: Sequence[int],
    per_sec_a010: Sequence[int],
    *,
    title: str = "ZOE FIELDGLASS · CAUSAL CHIASM & A_tau(p_t) TOMOGRAPHY",
    subtitle: str = "Kloster Operational Metacognition on Real Field Capture",
    nexus_sec: int | None = None,
    tau: float = 0.10,
    invariant_tau: float = 0.14,
) -> tuple[Scene, dict[str, Any]]:
    """Plug Fieldglass episode distributions directly into `guiai.gem.chiasm` & build a GEM `Scene`."""
    episodes_norm = [normalize_dist(ep) for ep in episodes_8]
    mid = nexus_sec if nexus_sec is not None else max(1, len(episodes_norm) // 2)
    mid = max(1, min(len(episodes_norm) - 1, mid)) if len(episodes_norm) > 1 else 0

    past_avg = normalize_dist({s: float(np.mean([ep[s] for ep in episodes_norm[: max(1, mid)]])) for s in TONAL_STATES})
    fut_avg = normalize_dist({s: float(np.mean([ep[s] for ep in episodes_norm[mid:]])) for s in TONAL_STATES})
    chiasm = causal_chiasm(past_avg, fut_avg, tau=tau, horizon=max(1, len(episodes_norm) - mid))
    tomography = persistent_filtration_tomography(
        episodes_norm,
        thresholds=(0.04, 0.08, 0.12, 0.18, 0.25, 0.35, 0.50),
        invariant_tau=invariant_tau,
    )

    width, height = 1400, 1000
    objects: list[dict[str, Any]] = [
        _rectangle("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _rectangle("panel-chiasm", [28, 96, 686, 520], RED, PANEL, 2),
        _rectangle("panel-filtration", [714, 96, 1372, 520], "#294058", PANEL, 1),
        _rectangle("panel-trajectory", [28, 544, 1372, 926], "#294058", PANEL, 1),
        _text("title", [28, 44], title, 24, RED),
        _text("subtitle", [28, 74], subtitle, 14, GOLD),
    ]
    cx, cy = 357, 308
    objects.extend([
        _text("p1-title", [48, 128], f"01 / CAUSAL CHIASM NEXUS (t = {mid}s)", 16, CYAN),
        _text("p1-past", [52, 164], f"PAST A_{tau:.2f} = {chiasm['past_accessible_volume']}", 13, CYAN),
        _text("p1-fut", [450, 164], f"FUTURE A_{tau:.2f} = {chiasm['future_accessible_volume']}", 13, GOLD),
    ])
    for idx, (dy, col_l, col_r) in enumerate([(-92, CYAN, GOLD), (-44, CYAN, RED), (44, GOLD, CYAN), (92, RED, GOLD)]):
        objects.append(_polyline(f"fg-l-{idx}", [[88, cy + dy], [cx - 48, cy + dy * 0.35], [cx, cy]], col_l, 2))
        objects.append(_polyline(f"fg-r-{idx}", [[cx, cy], [cx + 48, cy - dy * 0.35], [626, cy - dy]], col_r, 2))
    objects.extend(woven_diamond("fg-nexus-gem", [cx, cy], 32, RED))
    ei = chiasm["effective_information_bits"]
    ei_str = f"{ei:.4f}" if isinstance(ei, (int, float)) else "n/a"
    objects.append(_text("p1-cap", [48, 488], f"EI = {ei_str} bits · shift = {chiasm['chiasm_shift']:+d} · glyph = {chiasm['presence_glyph']}", 13, TEXT))

    objects.append(_text("p2-title", [734, 128], f"02 / PERSISTENT FILTRATION TOMOGRAPHY ({len(episodes_norm)} EPISODES)", 16, CYAN))
    scores = tomography["persistence_scores"]
    for idx, (state, score) in enumerate(sorted(scores.items(), key=lambda kv: -kv[1])):
        by = 188 + idx * 36
        bw = max(8, int(min(1.0, score / 0.55) * 340))
        is_inv = state in tomography["structural_invariants"]
        col = RED if is_inv else CYAN
        objects.extend([
            _text(f"p2-st-{idx}", [738, by + 16], state, 12, TEXT),
            _rectangle(f"p2-bar-{idx}", [885, by + 2, 885 + bw, by + 22], col, col, 1),
            _text(f"p2-val-{idx}", [895 + bw, by + 17], f"P={score:.3f}", 12, GOLD if is_inv else MUTED),
        ])

    gx0, gy0, gx1, gy1 = 92, 628, 1330, 868
    objects.append(_text("p3-title", [48, 578], "03 / KLOSTER ACCESSIBLE VOLUME TRAJECTORY A_tau(p_t)", 16, CYAN))
    objects.append(_rectangle("p3-grid", [gx0, gy0, gx1, gy1], "#294058", "#0c1420", 1))
    n_eps = max(1, len(per_sec_a010) - 1)
    fx = gx0 + (min(mid, n_eps) / n_eps) * (gx1 - gx0)
    objects.append(_line("p3-nexus", [fx, gy0], [fx, gy1], RED, 2))
    objects.append(_polyline("p3-c004", [[gx0 + (t / n_eps) * (gx1 - gx0), gy1 - min(1.0, v / 160.0) * (gy1 - gy0 - 14) - 6] for t, v in enumerate(per_sec_a004)], CYAN, 2))
    objects.append(_polyline("p3-c010", [[gx0 + (t / n_eps) * (gx1 - gx0), gy1 - min(1.0, v / 50.0) * (gy1 - gy0 - 14) - 6] for t, v in enumerate(per_sec_a010)], GOLD, 3))
    objects.extend(hud_stamp_objects("fieldglass", 1062, 18, chiasm["future_accessible_volume"], tau, chiasm["presence_glyph"]))
    objects.append(_text("footer", [28, 968], "Zoe Fieldglass · 0 cloud tokens · executed=False · sentience_claimed=False", 13, MUTED))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-fieldglass-chiasm",
        "title": title,
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "contract": FIELDGLASS_CONTRACT,
        "chiasm_contract": CHIASM_CONTRACT,
        "showcase_url": FIELDGLASS_SHOWCASE_URL,
        "repo_url": FIELDGLASS_REPO_URL,
        "nexus_sec": mid,
        "chiasm": chiasm,
        "tomography": tomography,
        "scene_sha256": scene.digest(),
        "auto_flash_allowed": False,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "sentience_claimed": False,
        "executed": False,
        "tokens_used": 0,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return scene, report


def serve_showcase_loopback(root: str | Path, *, port: int = 8776) -> None:
    """Serve a Fieldglass showcase on 127.0.0.1 with HTTP 206 Range support for video scrubbing."""
    root_str = str(Path(root).expanduser().resolve())

    class _RangeHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root_str, **kwargs)

        def send_head(self):
            path = self.translate_path(self.path)
            if os.path.isdir(path) or not os.path.isfile(path):
                return super().send_head()
            rh = self.headers.get("Range")
            if not rh:
                return super().send_head()
            m = _RANGE_RE.match(rh.strip())
            if not m:
                return super().send_head()
            f = open(path, "rb")
            size = os.fstat(f.fileno()).st_size
            start = int(m.group(1)) if m.group(1) else 0
            end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            if start > end or start >= size:
                f.close()
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return None
            length = end - start + 1
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            f.seek(start)
            self._rem = length
            return f

        def copyfile(self, source, outputfile):
            rem = getattr(self, "_rem", None)
            if rem is None:
                return super().copyfile(source, outputfile)
            self._rem = None
            while rem > 0:
                chunk = source.read(min(65536, rem))
                if not chunk:
                    break
                outputfile.write(chunk)
                rem -= len(chunk)

    srv = ThreadingHTTPServer(("127.0.0.1", int(port)), _RangeHandler)
    print(f"Zoe Fieldglass showcase live at http://127.0.0.1:{port}/ (root={root_str})", flush=True)
    srv.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="zoe-fieldglass", description="Zoe Fieldglass — Phone-to-Telemetry & Specimen Instrument")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="Print Fieldglass contract and public showcase links")

    p_br = sub.add_parser("braille", help="Render any local image as 2x4 Unicode Braille via Zoe BrailleCanvas")
    p_br.add_argument("image")
    p_br.add_argument("--cols", type=int, default=64)

    p_pl = sub.add_parser("plate", help="Clean illumination + trace SVG + export 2x4 Braille from a photo")
    p_pl.add_argument("image")
    p_pl.add_argument("-o", "--out-dir", default="fieldglass_out")
    p_pl.add_argument("--title", default="ZOE FIELDGLASS SPECIMEN")
    p_pl.add_argument("--cols", type=int, default=72)

    p_srv = sub.add_parser("serve", help="Serve a showcase directory over loopback HTTP (Range-capable)")
    p_srv.add_argument("directory", nargs="?", default=".")
    p_srv.add_argument("--port", type=int, default=8776)

    args = p.parse_args(argv)
    if args.cmd == "info":
        print(json.dumps({
            "contract": FIELDGLASS_CONTRACT,
            "showcase_url": FIELDGLASS_SHOWCASE_URL,
            "repo_url": FIELDGLASS_REPO_URL,
            "tokens_used": 0,
            "sentience_claimed": False,
        }, indent=2))
        return 0
    if args.cmd == "braille":
        with Image.open(Path(args.image).expanduser()) as im:
            ink, _, _ = clean_illumination(im)
        for row in ink_to_braille_canvas(ink, cols=args.cols):
            print(row)
        return 0
    if args.cmd == "plate":
        src = Path(args.image).expanduser().resolve()
        out = Path(args.out_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        with Image.open(src) as im:
            ink, arch, bw = clean_illumination(im)
        arch.save(out / f"{src.stem}_archival.png")
        bw.save(out / f"{src.stem}_ink_bw.png")
        svg = trace_ink_to_svg(ink, out / f"{src.stem}.svg", title=args.title)
        lines = ink_to_braille_canvas(ink, cols=args.cols)
        (out / f"{src.stem}_braille.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"svg": str(svg), "braille_rows": len(lines)}, indent=2))
        return 0
    if args.cmd == "serve":
        serve_showcase_loopback(args.directory, port=args.port)
        return 0
    return 1


__all__ = [
    "FIELDGLASS_CONTRACT",
    "FIELDGLASS_REPO_URL",
    "FIELDGLASS_SHOWCASE_URL",
    "TONAL_STATES",
    "a_tau",
    "build_fieldglass_chiasm_scene",
    "clean_illumination",
    "extract_sharpest_frame",
    "ink_to_braille_canvas",
    "laplacian_sharpness",
    "luminance_to_8state",
    "main",
    "normalize_dist",
    "perspective_deskew",
    "quartic_purity_m4",
    "renyi_h2",
    "serve_showcase_loopback",
    "shannon_h1",
    "trace_ink_to_svg",
]

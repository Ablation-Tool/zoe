#!/usr/bin/env python3
"""
zoe_vision_heads.py — Multi-Head Vision & Global Self-Attention Dissector

Demonstrates how a Vision Transformer / Multi-Head Vision Encoder processes an image
simultaneously across all patches, contrasting with sequential human foveal vision:

  1. Uniform Patch Tokenization (NxN grid, zero peripheral drop-off)
  2. Global Self-Attention: Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V
  3. Head 1 (Edge Detective): High-frequency spatial gradient contours (Sobel)
  4. Head 2 (Color Field): Chromatic & luminance field topology
  5. Head 3 (Semantic / Density): Local structural entropy & text/lattice activation
  6. Head 4 (Relational Mapper): Top cross-patch attention links & unified collapse

Zero deception: All feature maps, patch embeddings, and QK^T attention weights are
computed mathematically from the actual input image pixels.

Usage:
  zoe_vision_heads.py --image /path/to/img.png --out /path/to/output.png
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Tuple, List

import numpy as np
from PIL import Image
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def compute_patch_embeddings(
    arr: np.ndarray, grid_n: int = 16
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Slices image into a uniform (grid_n x grid_n) patch grid and extracts an honest
    feature vector per patch:
      [mean_R, mean_G, mean_B, std_L, edge_energy, redness, high_freq_ratio, center_contrast]
    Returns:
      embeddings: (grid_n * grid_n, d) L2-normalized patch feature vectors
      patch_centers: (grid_n * grid_n, 2) (x, y) pixel coordinates
      edge_map: (H, W) full-res Sobel magnitude
      chroma_map: (H, W) full-res chromatic field
    """
    h, w, _ = arr.shape
    f_arr = arr.astype(np.float32) / 255.0
    gray = 0.299 * f_arr[:, :, 0] + 0.587 * f_arr[:, :, 1] + 0.114 * f_arr[:, :, 2]

    # Head 1: Edge Detective (Sobel gradient magnitude)
    gx = ndimage.sobel(gray, axis=1)
    gy = ndimage.sobel(gray, axis=0)
    edge_map = np.hypot(gx, gy)
    if edge_map.max() > 0:
        edge_map = edge_map / edge_map.max()

    # Head 2: Chromaticity / Red-vs-Cyan opponent channel
    redness = f_arr[:, :, 0] - 0.5 * (f_arr[:, :, 1] + f_arr[:, :, 2])
    blueness = f_arr[:, :, 2] - 0.5 * (f_arr[:, :, 0] + f_arr[:, :, 1])
    chroma_map = np.stack([
        np.clip(redness * 1.8, 0, 1),
        np.clip(gray * 0.45, 0, 1),
        np.clip((blueness + 0.2) * 1.5, 0, 1),
    ], axis=2)

    # Head 3: Structural Density / Local Variance (text & tight-packing detector)
    local_mean = ndimage.uniform_filter(edge_map, size=15)
    local_sq_mean = ndimage.uniform_filter(edge_map ** 2, size=15)
    density_map = np.sqrt(np.maximum(local_sq_mean - local_mean ** 2, 0.0)) + local_mean
    if density_map.max() > 0:
        density_map = density_map / density_map.max()

    ph = h / grid_n
    pw = w / grid_n

    feats: List[List[float]] = []
    centers: List[Tuple[float, float]] = []

    for r in range(grid_n):
        y0, y1 = int(r * ph), int((r + 1) * ph)
        for c in range(grid_n):
            x0, x1 = int(c * pw), int((c + 1) * pw)
            patch_rgb = f_arr[y0:y1, x0:x1]
            patch_gray = gray[y0:y1, x0:x1]
            patch_edge = edge_map[y0:y1, x0:x1]
            patch_red = redness[y0:y1, x0:x1]
            patch_dens = density_map[y0:y1, x0:x1]

            vec = [
                float(np.mean(patch_rgb[:, :, 0])),
                float(np.mean(patch_rgb[:, :, 1])),
                float(np.mean(patch_rgb[:, :, 2])),
                float(np.std(patch_gray)) * 2.5,
                float(np.mean(patch_edge)) * 3.0,
                float(np.mean(np.maximum(patch_red, 0.0))) * 3.0,
                float(np.mean(patch_dens)) * 2.5,
                float(np.max(patch_edge)),
            ]
            feats.append(vec)
            centers.append(((x0 + x1) * 0.5, (y0 + y1) * 0.5))

    emb = np.array(feats, dtype=np.float32)
    # Standardize + L2 normalize for crisp dot-product QK^T attention
    emb = emb - emb.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-6
    emb = emb / norms

    return emb, np.array(centers), edge_map, chroma_map, density_map


def compute_self_attention(emb: np.ndarray, temperature: float = 0.25) -> np.ndarray:
    """
    Computes exact scaled dot-product Global Self-Attention:
      A = softmax((Q K^T) / sqrt(d_k))
    """
    d_k = emb.shape[1]
    logits = (emb @ emb.T) / (np.sqrt(d_k) * temperature)
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp_l = np.exp(logits)
    attn = exp_l / np.sum(exp_l, axis=1, keepdims=True)
    return attn


def render_multihead_dissection(
    image_path: Path,
    out_path: Path,
    grid_n: int = 16,
    title_label: str = "Multi-Head Vision & Global Self-Attention",
    report_json: Path | None = None,
):
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape

    emb, centers, edge_map, chroma_map, density_map = compute_patch_embeddings(arr, grid_n=grid_n)
    attn = compute_self_attention(emb, temperature=0.22)

    # Identify top non-adjacent cross-image attention pairs (long-range spotlight)
    n_tokens = len(centers)
    long_range_links = []
    min_pixel_dist = 0.30 * min(h, w)
    # Exclude pure flat background patches (low variance / edge)
    patch_activity = np.array([
        float(edge_map[max(0, int(cy)-8):min(h, int(cy)+8), max(0, int(cx)-8):min(w, int(cx)+8)].mean())
        for cx, cy in centers
    ])

    for i in range(n_tokens):
        if patch_activity[i] < 0.04:
            continue
        for j in range(i + 1, n_tokens):
            if patch_activity[j] < 0.04:
                continue
            dist = np.hypot(centers[i, 0] - centers[j, 0], centers[i, 1] - centers[j, 1])
            if dist >= min_pixel_dist:
                score = float(attn[i, j] + attn[j, i])
                long_range_links.append((score, i, j, dist))

    long_range_links.sort(reverse=True)
    top_links = long_range_links[:28]

    # Build the 6-Panel CRT / Zoe Cyberpunk Blueprint
    plt.rcParams["font.family"] = "monospace"
    fig = plt.figure(figsize=(22, 14), facecolor="#050508")
    fig.suptitle(
        f"ZOE VISION ENCODER :: {title_label.upper()} ({grid_n}x{grid_n} = {n_tokens} PARALLEL PATCHES)",
        color="#00ff88",
        fontsize=17,
        weight="bold",
        y=0.97,
    )

    # ------------------------------------------------------------------
    # Panel 1: Uniform Patch Tokenization (Zero Foveal Decay)
    # ------------------------------------------------------------------
    ax1 = fig.add_subplot(2, 3, 1)
    ax1.set_facecolor("#050508")
    ax1.imshow(arr)
    pw, ph = w / grid_n, h / grid_n
    for g in range(1, grid_n):
        ax1.axvline(g * pw, color="#00ffff", alpha=0.35, linewidth=0.7)
        ax1.axhline(g * ph, color="#00ffff", alpha=0.35, linewidth=0.7)

    # Highlight highest-activity patches
    top_active = np.argsort(patch_activity)[-8:]
    for idx in top_active:
        r, c = divmod(int(idx), grid_n)
        ax1.add_patch(Rectangle((c * pw, r * ph), pw, ph, fill=False, edgecolor="#ff00aa", linewidth=1.8))

    ax1.set_title("1. UNIFORM PATCH GRID (NO FOVEA)", color="#00ffff", fontsize=12, weight="bold", pad=8)
    ax1.text(
        w * 0.5, h * 1.04,
        f"Every {int(pw)}x{int(ph)}px tile enters simultaneously at 100% clarity",
        color="#aaffdd", fontsize=9.5, ha="center"
    )
    ax1.axis("off")

    # ------------------------------------------------------------------
    # Panel 2: Global Self-Attention Matrix softmax(QK^T / sqrt(d_k))
    # ------------------------------------------------------------------
    ax2 = fig.add_subplot(2, 3, 2)
    ax2.set_facecolor("#050508")
    im2 = ax2.imshow(attn, cmap="inferno", aspect="equal")
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.ax.yaxis.set_tick_params(color="#00ff88")
    plt.setp(plt.getp(cbar2.ax.axes, "yticklabels"), color="#00ff88", fontsize=8)
    ax2.set_title(r"2. GLOBAL SELF-ATTENTION MATRIX $\mathrm{softmax}(QK^T/\sqrt{d_k})$", color="#ff00aa", fontsize=11.5, weight="bold", pad=8)
    ax2.set_xlabel(f"Key Patch Index (0..{n_tokens-1})", color="#00ff88", fontsize=9)
    ax2.set_ylabel(f"Query Patch Index (0..{n_tokens-1})", color="#00ff88", fontsize=9)
    ax2.tick_params(colors="#00ff88", labelsize=8)
    for sp in ax2.spines.values():
        sp.set_color("#334455")

    # ------------------------------------------------------------------
    # Panel 3: Head 1 — The Edge Detective
    # ------------------------------------------------------------------
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.set_facecolor("#050508")
    # Phosphor green glow on pure black
    edge_rgb = np.zeros((h, w, 3), dtype=np.float32)
    edge_rgb[:, :, 0] = np.clip(edge_map ** 1.4 * 0.25, 0, 1)
    edge_rgb[:, :, 1] = np.clip(edge_map ** 0.75 * 1.0, 0, 1)
    edge_rgb[:, :, 2] = np.clip(edge_map ** 1.1 * 0.55, 0, 1)
    ax3.imshow(edge_rgb)
    ax3.set_title("3. HEAD 1: THE EDGE DETECTIVE (HIGH-FREQ VECTORS)", color="#00ff88", fontsize=11.5, weight="bold", pad=8)
    ax3.text(w * 0.5, h * 1.04, "Strips all color; isolates contours, shafts & typography", color="#aaffdd", fontsize=9.5, ha="center")
    ax3.axis("off")

    # ------------------------------------------------------------------
    # Panel 4: Head 2 — The Color Field
    # ------------------------------------------------------------------
    ax4 = fig.add_subplot(2, 3, 4)
    ax4.set_facecolor("#050508")
    ax4.imshow(chroma_map)
    ax4.set_title("4. HEAD 2: THE COLOR FIELD (CHROMATIC TOPOLOGY)", color="#00ffff", fontsize=11.5, weight="bold", pad=8)
    ax4.text(w * 0.5, h * 1.04, "Maps warm opponent channels vs. structural luminance", color="#aaffdd", fontsize=9.5, ha="center")
    ax4.axis("off")

    # ------------------------------------------------------------------
    # Panel 5: Head 3 — Semantic & Structural Density Map
    # ------------------------------------------------------------------
    ax5 = fig.add_subplot(2, 3, 5)
    ax5.set_facecolor("#050508")
    ax5.imshow(density_map, cmap="magma")
    ax5.set_title("5. HEAD 3: SEMANTIC & LATTICE DENSITY HEAD", color="#ff00aa", fontsize=11.5, weight="bold", pad=8)
    ax5.text(w * 0.5, h * 1.04, "Fires on packed cone clusters, symbols & text syntax", color="#aaffdd", fontsize=9.5, ha="center")
    ax5.axis("off")

    # ------------------------------------------------------------------
    # Panel 6: Head 4 — Relational Mapper & Unified Collapse
    # ------------------------------------------------------------------
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.set_facecolor("#050508")
    # Darkened backdrop + subtle edge ghost
    backdrop = (arr.astype(np.float32) / 255.0) * 0.28 + edge_rgb * 0.35
    ax6.imshow(np.clip(backdrop, 0, 1))

    if top_links:
        max_s = top_links[0][0]
        min_s = top_links[-1][0]
        for k, (score, i, j, dist) in enumerate(top_links):
            p1, p2 = centers[i], centers[j]
            norm_s = (score - min_s) / (max_s - min_s + 1e-8)
            rad = 0.22 if k % 2 == 0 else -0.22
            col = "#ff00aa" if k < 8 else "#00ffff"
            alpha = 0.35 + 0.60 * norm_s
            lw = 1.0 + 1.8 * norm_s
            ax6.annotate(
                "", xy=(p2[0], p2[1]), xytext=(p1[0], p1[1]),
                arrowprops=dict(arrowstyle="-", color=col, alpha=alpha, lw=lw, connectionstyle=f"arc3,rad={rad}")
            )
            ax6.plot([p1[0], p2[0]], [p1[1], p2[1]], "o", color="#ffffff", markersize=3.5, markeredgecolor=col, markeredgewidth=1.2)

    ax6.set_title("6. HEAD 4: RELATIONAL SPOTLIGHT (ALL-TO-ALL COLLAPSE)", color="#00ff88", fontsize=11.5, weight="bold", pad=8)
    ax6.text(
        w * 0.5, h * 1.04,
        f"Top {len(top_links)} long-range QK^T arcs linking distant features simultaneously",
        color="#aaffdd", fontsize=9.5, ha="center"
    )
    ax6.axis("off")

    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)

    telemetry = {
        "image": str(image_path),
        "dimensions": [w, h],
        "grid": [grid_n, grid_n],
        "total_tokens": n_tokens,
        "mean_attention_entropy": float(-np.mean(np.sum(attn * np.log(attn + 1e-12), axis=1))),
        "long_range_arcs_drawn": len(top_links),
        "top_arc_score": float(top_links[0][0]) if top_links else 0.0,
        "output": str(out_path),
    }

    if report_json:
        report_json.write_text(json.dumps(telemetry, indent=2))

    return telemetry


def main():
    parser = argparse.ArgumentParser(description="Zoe Multi-Head Vision & Self-Attention Dissector")
    parser.add_argument("--image", type=Path, required=True, help="Input image path")
    parser.add_argument("--out", type=Path, required=True, help="Output composite PNG path")
    parser.add_argument("--grid", type=int, default=16, help="Uniform patch grid size (NxN)")
    parser.add_argument("--title", type=str, default="Multi-Head Vision & Global Self-Attention")
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON telemetry log")
    args = parser.parse_args()

    telemetry = render_multihead_dissection(
        args.image, args.out, grid_n=args.grid, title_label=args.title, report_json=args.json
    )
    print(json.dumps(telemetry, indent=2))


if __name__ == "__main__":
    main()

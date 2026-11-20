"""Zoe Voice Cymatics: Chladni Sand Plate Figures & Digital Research GEM 3-Bitplane Raster.

Bridges acoustics to visible geometry:
  - Maps Zoe's 44-phoneme vocal-tract formants (F1, F2, F3, F0) to dual Chladni
    plate eigenmodes (n1, m1, n2, m2), revealing standing-wave nodal sand patterns.
  - Computes Kloster Accessible Volume A_tau(p) over normalized Chladni intensity.
  - Encodes sand plates + Digital Research GEM woven diamond resonance into an authentic
    3-bitplane MSB-first 16-bit word raster (`Plane 1`, `Plane 2`, `Plane 3`) with
    bit-exact round-trip decoding and SHA-256 verification.
  - Computes STFT formant waterfalls for 3D singing topography visualization.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, List, Tuple

import numpy as np

from .zoe_phonetics import PHONEME_INVENTORY, PhonemeSpec


CYMATICS_CONTRACT = "zoe-voice-cymatics/v1"


def phoneme_to_chladni_modes(
    phoneme: PhonemeSpec | str,
    f0_hz: float = 232.0,
) -> Tuple[int, int, int, int]:
    """Deterministically maps vocal-tract formants + fundamental F0 to Chladni eigenmodes."""
    spec = PHONEME_INVENTORY[phoneme] if isinstance(phoneme, str) else phoneme
    f1, f2, f3 = spec.formants[0], spec.formants[1], spec.formants[2]
    n1 = int(np.clip(round(1.0 + f1 / 180.0), 1, 6))
    m1 = int(np.clip(round(2.0 + (f2 - f1) / 360.0), n1 + 1, 8))
    n2 = int(np.clip(round(1.0 + (f0_hz - 140.0) / 70.0), 1, 7))
    m2 = int(np.clip(round(3.0 + f3 / 620.0), n2 + 1, 9))
    if spec.kind == "consonant" and spec.noise_gain > 0.10:
        hi = int(np.clip(round(spec.noise_center_hz / 950.0), 3, 8))
        n2 = max(2, min(hi - 1, 6))
        m2 = max(n2 + 2, min(hi + 2, 9))
    if (n1, m1) == (n2, m2):
        m2 = min(9, m2 + 1)
    return (n1, m1, n2, m2)


def chladni_sand_plate(
    n1: int,
    m1: int,
    n2: int,
    m2: int,
    *,
    grid_size: int = 64,
    sigma: float = 0.22,
) -> np.ndarray:
    """Evaluates standing-wave Chladni plate nodal sand intensity S in [0, 1]."""
    coords = np.linspace(-1.0, 1.0, grid_size, dtype=np.float64)
    xx, yy = np.meshgrid(coords, coords, indexing="ij")
    z1 = np.cos(n1 * math.pi * xx) * np.cos(m1 * math.pi * yy) - np.cos(m1 * math.pi * xx) * np.cos(n1 * math.pi * yy)
    z2 = np.cos(n2 * math.pi * xx) * np.cos(m2 * math.pi * yy) + np.cos(m2 * math.pi * xx) * np.cos(n2 * math.pi * yy)
    z = 0.65 * z1 + 0.35 * z2
    return np.exp(-(z * z) / (sigma * sigma))


def render_phoneme_cymatics(
    phoneme: str,
    *,
    f0_hz: float = 232.0,
    grid_size: int = 64,
) -> Dict[str, object]:
    """Generates a Chladni plate + Kloster A_tau dispersion measurement for one phoneme."""
    spec = PHONEME_INVENTORY[phoneme]
    n1, m1, n2, m2 = phoneme_to_chladni_modes(spec, f0_hz=f0_hz)
    plate = chladni_sand_plate(n1, m1, n2, m2, grid_size=grid_size)
    probs = plate / (float(plate.sum()) + 1e-12)
    tau = 1.0 / float(grid_size * grid_size)
    a_tau = int(np.sum(probs > tau))
    return {
        "phoneme": spec.symbol,
        "ipa": spec.ipa,
        "modes": (n1, m1, n2, m2),
        "grid_size": grid_size,
        "plate": plate,
        "kloster_a_tau": a_tau,
        "kloster_fill_fraction": round(a_tau / float(grid_size * grid_size), 4),
    }


def gem_woven_diamond_mask(grid_size: int = 64) -> np.ndarray:
    """Parametric concentric GEM woven diamond lattice matching Digital Research raster style."""
    if grid_size % 16 != 0:
        raise ValueError("grid_size must be a multiple of 16 for 16-bit VDI planes")
    coords = np.arange(grid_size, dtype=np.int32)
    yy, xx = np.meshgrid(coords, coords, indexing="ij")
    cx = (grid_size - 1) / 2.0
    cy = (grid_size - 1) / 2.0
    dist = np.abs(xx - cx) + np.abs(yy - cy)
    inside = (dist <= 0.42 * grid_size) & (xx >= 4) & (xx < grid_size - 4) & (yy >= 4) & (yy < grid_size - 4)
    # Concentric faceted lattice weave inside the diamond silhouette
    weave = ((xx + yy) % 4 == 0) ^ ((xx - yy) % 6 == 0)
    rings = np.isin(np.round(dist).astype(np.int32), [6, 12, 18, 24])
    return (inside & (weave | rings)).astype(np.uint8)


def encode_gem_3bitplane_raster(
    chladni_grid: np.ndarray,
    *,
    formant_strength: float = 0.65,
) -> Dict[str, object]:
    """Encodes a 64x64 Chladni plate into 3 MSB-first 16-bit GEM VDI raster bitplanes.

    Matches Atari ST / Digital Research VDI planar memory layout:
      Plane 1: Primary nodal sand line mask (plate > 0.52)
      Plane 2: Standing-wave harmonic halo mask (0.26 < plate <= 0.72)
      Plane 3: Woven GEM diamond resonance overlay gated by local amplitude
    """
    arr = np.asarray(chladni_grid, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1] or arr.shape[0] % 16 != 0:
        raise ValueError("chladni_grid must be square with side divisible by 16")
    size = int(arr.shape[0])
    words_per_row = size // 16
    diamond = gem_woven_diamond_mask(size)

    p1 = (arr > 0.52).astype(np.uint8)
    p2 = ((arr > 0.26) & (arr <= 0.72)).astype(np.uint8)
    thresh3 = max(0.12, 0.36 - 0.20 * formant_strength)
    p3 = (((arr > thresh3) & (diamond > 0)) | ((arr > 0.78) & (diamond > 0))).astype(np.uint8)

    planes_out: List[List[int]] = []
    for plane in (p1, p2, p3):
        words: List[int] = []
        for row in range(size):
            for w_idx in range(words_per_row):
                bits = plane[row, w_idx * 16:(w_idx + 1) * 16]
                val = 0
                for b in bits:
                    val = (val << 1) | int(b)
                words.append(val)
        planes_out.append(words)

    payload = {
        "contract": CYMATICS_CONTRACT,
        "width": size,
        "height": size,
        "bitplanes": 3,
        "words_per_row": words_per_row,
        "planes": planes_out,
    }
    payload["raster_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def decode_gem_3bitplane_raster(encoded: Dict[str, object]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decodes 3 MSB-first 16-bit VDI word bitplanes back into exact (H, W) binary arrays."""
    w = int(encoded["width"])
    h = int(encoded["height"])
    wpr = int(encoded["words_per_row"])
    planes_raw = encoded["planes"]
    decoded: List[np.ndarray] = []
    for p_words in planes_raw:
        grid = np.zeros((h, w), dtype=np.uint8)
        idx = 0
        for row in range(h):
            for w_idx in range(wpr):
                word = int(p_words[idx])
                idx += 1
                for bit_pos in range(16):
                    grid[row, w_idx * 16 + bit_pos] = (word >> (15 - bit_pos)) & 1
        decoded.append(grid)
    return decoded[0], decoded[1], decoded[2]


def compute_formant_waterfall(
    mono_audio: np.ndarray,
    *,
    sample_rate: int = 44100,
    max_hz: float = 4200.0,
    n_fft: int = 2048,
    hop: int = 512,
    max_frames: int = 120,
) -> Dict[str, object]:
    """Computes a smooth STFT magnitude (dB) waterfall across time and frequency."""
    x = np.asarray(mono_audio, dtype=np.float64)
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    window = np.hanning(n_fft)
    frames = list(range(0, max(1, len(x) - n_fft + 1), hop))
    if len(frames) > max_frames:
        sel = np.linspace(0, len(frames) - 1, max_frames, dtype=int)
        frames = [frames[i] for i in sel]

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    f_mask = freqs <= max_hz
    freqs_sel = freqs[f_mask]
    specs = []
    for start in frames:
        seg = x[start:start + n_fft]
        if len(seg) < n_fft:
            seg = np.pad(seg, (0, n_fft - len(seg)))
        mag = np.abs(np.fft.rfft(seg * window))[f_mask]
        db = 20.0 * np.log10(np.maximum(mag, 1e-6))
        specs.append(db)

    mat = np.asarray(specs, dtype=np.float64)
    times = np.asarray(frames, dtype=np.float64) / float(sample_rate)
    return {
        "times": times,
        "freqs": freqs_sel,
        "db_matrix": mat,
    }

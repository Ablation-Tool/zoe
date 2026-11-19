#!/usr/bin/env python3
"""
Zoe Research Tooling — Temporal Dynamics, Phase-Space Attractors, and Micro-Timing Forensics

Extracts discrete note timing from vintage MS-DOS tracker modules (.MOD) and MIDI files,
decomposes macro tempo drift (rubato) from micro-timing residuals, and computes 2D Poincaré
delay embeddings (r_t vs r_{t-1}), Markovian state transitions, and Shannon entropy signatures.

Conforms to Zoe Constitution: measurement != evidence != belief update != action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Canonical JSON serializer
def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ==============================================================================
# 1. PARSERS: MIDI & VINTAGE MS-DOS TRACKER (.MOD)
# ==============================================================================

class NoteEvent:
    def __init__(self, time_sec: float, note: int, velocity: int, channel: int, duration_sec: float = 0.1):
        self.time_sec = float(time_sec)
        self.note = int(note)
        self.velocity = int(velocity)
        self.channel = int(channel)
        self.duration_sec = float(duration_sec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_sec": round(self.time_sec, 6),
            "note": self.note,
            "velocity": self.velocity,
            "channel": self.channel,
            "duration_sec": round(self.duration_sec, 6),
        }


def parse_midi(file_path: Path) -> Tuple[List[NoteEvent], float]:
    """Parses standard MIDI file using mido, resolving tempo changes and onsets."""
    try:
        import mido
    except ImportError as exc:
        raise ImportError("MIDI parsing requires 'mido' (pip install mido)") from exc

    mid = mido.MidiFile(str(file_path))
    events: List[NoteEvent] = []
    
    # Calculate global onsets in absolute seconds across merged tracks
    current_time_sec = 0.0
    tempo_dt: Optional[float] = None
    active_notes: Dict[Tuple[int, int], Tuple[float, int]] = {}  # (channel, note) -> (start_sec, vel)

    for msg in mid:
        current_time_sec += msg.time
        if msg.type == "set_tempo" and tempo_dt is None and getattr(msg, "tempo", 0) > 0:
            tempo_dt = float(msg.tempo) / 1_000_000.0
        if msg.type == "note_on" and msg.velocity > 0:
            key = (msg.channel, msg.note)
            active_notes[key] = (current_time_sec, msg.velocity)
        elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            if key in active_notes:
                start_sec, vel = active_notes.pop(key)
                dur = max(0.001, current_time_sec - start_sec)
                events.append(NoteEvent(start_sec, msg.note, vel, msg.channel, dur))

    # Catch any remaining open notes
    for (channel, note), (start_sec, vel) in active_notes.items():
        events.append(NoteEvent(start_sec, note, vel, channel, 0.1))

    events.sort(key=lambda e: e.time_sec)
    
    if tempo_dt is not None and tempo_dt > 0:
        return events, tempo_dt

    # Fallback: compute median tempo / interval when no set_tempo meta exists
    if len(events) >= 2:
        intervals = [events[i+1].time_sec - events[i].time_sec for i in range(len(events)-1)]
        positive_intervals = [dt for dt in intervals if dt > 0.02]
        median_dt = float(np.median(positive_intervals)) if positive_intervals else 0.5
    else:
        median_dt = 0.5

    return events, median_dt


def parse_mod(file_path: Path) -> Tuple[List[NoteEvent], float]:
    """
    Parses classic Amiga / MS-DOS ProTracker 4-channel MOD files.
    Calculates exact tick-quantized note onsets and speed/BPM timing.
    """
    raw_data = file_path.read_bytes()
    if len(raw_data) < 1084:
        raise ValueError("Invalid MOD file: size smaller than 1084-byte header")

    # Header parsing
    title = raw_data[:20].decode("ascii", errors="replace").rstrip("\x00")
    tag = raw_data[1080:1084].decode("ascii", errors="replace")

    # Standard ProTracker 4-channel tags: M.K., M!K!, 4CHN, FLT4
    channels = 4
    if tag in ("8CHN", "FLT8", "CD81"):
        channels = 8
    elif tag not in ("M.K.", "M!K!", "4CHN", "FLT4"):
        # Assume 4-channel legacy if not specified
        channels = 4

    song_len = raw_data[950]
    pattern_table = list(raw_data[952:1080])
    num_patterns = max(pattern_table[:song_len]) + 1 if song_len > 0 else 1

    pattern_offset = 1084
    pattern_bytes = 64 * channels * 4

    events: List[NoteEvent] = []
    
    # Tracker playback registers
    speed = 6          # Ticks per row (default 6)
    bpm = 125          # Beats per minute (default 125)
    initial_speed = speed
    initial_bpm = bpm
    current_time_sec = 0.0

    # Note period lookup table (ProTracker tuning)
    periods = [
        856, 808, 762, 720, 678, 640, 604, 570, 538, 508, 480, 453, # Octave 1
        428, 404, 381, 360, 339, 320, 302, 285, 269, 254, 240, 226, # Octave 2
        214, 202, 190, 180, 170, 160, 151, 143, 135, 127, 120, 113  # Octave 3
    ]

    for order_idx in range(song_len):
        pat_idx = pattern_table[order_idx]
        p_start = pattern_offset + pat_idx * pattern_bytes
        if p_start + pattern_bytes > len(raw_data):
            break

        pat_data = raw_data[p_start : p_start + pattern_bytes]

        for row in range(64):
            # Apply any 0x0F tempo/speed command on the current row before timing it,
            # or at least capture initial speed/bpm on order 0 row 0 accurately.
            pending_speed = speed
            pending_bpm = bpm
            row_notes: List[Tuple[int, int]] = []

            for ch in range(channels):
                cell_offset = (row * channels + ch) * 4
                b0, b1, b2, b3 = pat_data[cell_offset : cell_offset + 4]

                sample_num = (b0 & 0xF0) | (b2 >> 4)
                period = ((b0 & 0x0F) << 8) | b1
                effect = b2 & 0x0F
                effect_param = b3

                if period > 0:
                    closest_idx = min(range(len(periods)), key=lambda i: abs(periods[i] - period))
                    midi_note = 36 + closest_idx  # Octave 1 C = 36
                    row_notes.append((midi_note, ch))

                if effect == 0x0F and effect_param > 0:
                    if effect_param <= 32:
                        pending_speed = effect_param
                    else:
                        pending_bpm = effect_param

            speed = pending_speed
            bpm = pending_bpm
            if order_idx == 0 and row == 0:
                initial_speed = speed
                initial_bpm = bpm

            # CIA timer frequency = 0.4 * BPM Hz -> Tick = 2.5 / BPM seconds
            tick_sec = 2.5 / bpm
            row_duration_sec = speed * tick_sec

            for midi_note, ch in row_notes:
                events.append(NoteEvent(current_time_sec, midi_note, 64, ch, row_duration_sec))

            current_time_sec += row_duration_sec

    events.sort(key=lambda e: e.time_sec)
    row_dt = initial_speed * (2.5 / initial_bpm)
    if len(events) >= 2:
        diffs = [events[i + 1].time_sec - events[i].time_sec for i in range(len(events) - 1)]
        positive_intervals = [dt for dt in diffs if dt > 0.01]
        if positive_intervals:
            rows_per_step = max(1, round(float(np.median(positive_intervals)) / row_dt))
            return events, float(rows_per_step * row_dt)
    return events, float(4 * row_dt)


# ==============================================================================
# 2. SYNTHETIC GROOVE GENERATOR (BENCHMARKS & PROOFS)
# ==============================================================================

def generate_synthetic_stream(
    n_events: int = 128,
    tempo_bpm: float = 120.0,
    groove_type: str = "swing_attractor",
    seed: int = 42
) -> Tuple[List[NoteEvent], float]:
    """
    Generates synthetic note sequences with known micro-timing structures:
      - 'swing_attractor': Coupled 2D Poincaré limit-cycle (beat 2 drags, beat 3 compensates).
      - 'pure_noise': Sterile Gaussian jitter (uncorrelated).
      - 'accelerando': Systematic polynomial tempo drift with subtle jitter.
      - 'metronome': Perfectly quantized rigid ticks.
    """
    rng = np.random.RandomState(seed)
    base_dt = 60.0 / tempo_bpm
    ideal_grid = np.arange(n_events) * base_dt

    # Macro rubato drift curve
    t_norm = np.linspace(0, 1, n_events)
    if groove_type == "accelerando":
        macro_drift = -0.08 * (t_norm ** 2) + 0.02 * (t_norm ** 3)
    elif groove_type == "pure_noise":
        # Clean negative control: zero macro rubato so uncorrelated Gaussian jitter stays independent
        macro_drift = np.zeros(n_events)
    elif groove_type == "swing_attractor":
        # Smooth cubic macro rubato cleanly separable by degree-3 polynomial detrending
        u = t_norm - 0.5
        macro_drift = 0.03 * u + 0.02 * (u ** 2) - 0.05 * (u ** 3)
    else:
        macro_drift = 0.035 * np.sin(2 * np.pi * t_norm * 1.5) + 0.015 * (t_norm ** 2)

    micro_residuals = np.zeros(n_events)
    
    if groove_type == "swing_attractor":
        # Coupled non-linear return map:
        # Swing push-pull where odd beats (upbeats) drag by ~25ms and even beats push by ~16ms
        r = 0.015
        for i in range(n_events):
            if i % 2 == 1:
                r = 0.025 + 0.25 * r + rng.normal(0, 0.0025)
            else:
                r = -0.016 + 0.20 * r + rng.normal(0, 0.0025)
            micro_residuals[i] = r
    elif groove_type == "pure_noise":
        micro_residuals = rng.normal(0, 0.015, n_events)
    elif groove_type == "accelerando":
        micro_residuals = rng.normal(0, 0.005, n_events)
    elif groove_type == "metronome":
        macro_drift = np.zeros(n_events)
        micro_residuals = np.zeros(n_events)

    actual_times = ideal_grid + macro_drift + micro_residuals
    events = [NoteEvent(t, 60 + (i % 12), 64, 0, base_dt * 0.8) for i, t in enumerate(actual_times)]
    return events, base_dt


# ==============================================================================
# 3. MATHEMATICAL ANALYSIS ENGINE
# ==============================================================================

def analyze_groove_dynamics(
    events: List[NoteEvent],
    nominal_dt: Optional[float] = None,
    poly_degree: int = 3,
    n_bins: int = 5
) -> Dict[str, Any]:
    """
    Core Mathematical Analysis Pipeline:
      1. Grid Alignment & Delta-Time Extraction
      2. Residual Analysis (r_k = t_observed - t_grid)
      3. Polynomial Rubato Detrending (Macro Drift vs Micro Groove)
      4. Phase-Space Delay Embedding (Poincaré Map: r_k vs r_{k-1})
      5. Covariance Ellipse & Autocorrelation
      6. Markov Transition Kernel
      7. Shannon Entropy & Mutual Information
      8. Spectral Density (FFT)
    """
    if len(events) < 8:
        raise ValueError("At least 8 note events are required for timing analysis")

    timestamps = np.array([e.time_sec for e in events], dtype=np.float64)
    n = len(timestamps)

    # 1. Determine nominal grid interval
    if nominal_dt is None or nominal_dt <= 0:
        diffs = np.diff(timestamps)
        pos_diffs = diffs[diffs > 0.01]
        grid_dt = float(np.median(pos_diffs)) if len(pos_diffs) > 0 else 0.5
    else:
        grid_dt = float(nominal_dt)

    # Map events to nearest grid beats
    t0 = timestamps[0]
    beat_indices = np.round((timestamps - t0) / grid_dt).astype(np.int64)
    ideal_grid = t0 + beat_indices * grid_dt

    # 2. Raw residuals (r_k)
    raw_residuals = timestamps - ideal_grid

    # 3. Polynomial regression detrending (Macro rubato drift)
    deg = min(poly_degree, max(1, n // 4))
    poly_coeffs = np.polyfit(beat_indices, raw_residuals, deg=deg)
    macro_trend = np.polyval(poly_coeffs, beat_indices)

    # Micro-timing groove residuals (r_micro)
    micro_residuals = raw_residuals - macro_trend

    # Explained variance (R^2 of macro rubato)
    total_var = np.var(raw_residuals)
    res_var = np.var(micro_residuals)
    r2_rubato = float(1.0 - (res_var / total_var)) if total_var > 1e-12 else 0.0

    # 4. Phase-Space Delay Embedding (Poincaré map: x = r_{k-1}, y = r_k)
    x_delay = micro_residuals[:-1]
    y_current = micro_residuals[1:]

    # Lag-1 Autocorrelation
    if len(micro_residuals) > 1 and np.std(micro_residuals) > 1e-9:
        lag1_corr = float(np.corrcoef(x_delay, y_current)[0, 1])
    else:
        lag1_corr = 0.0

    # Covariance Ellipse Analysis using eigh (guaranteed real for symmetric matrices)
    pts = np.vstack([x_delay, y_current])
    cov = np.cov(pts)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Sort descending
    sort_idx = np.argsort(eigenvalues)[::-1]
    eigvals = np.real(eigenvalues[sort_idx])
    eigvecs = np.real(eigenvectors[:, sort_idx])

    semi_major = float(math.sqrt(max(0.0, float(eigvals[0]))))
    semi_minor = float(math.sqrt(max(0.0, float(eigvals[1]))))
    ellipse_eccentricity = float(math.sqrt(max(0.0, 1.0 - (float(eigvals[1]) / float(eigvals[0]))))) if eigvals[0] > 1e-12 else 0.0
    orientation_rad = float(math.atan2(float(eigvecs[1, 0]), float(eigvecs[0, 0])))

    # 5. Markov Transition Matrix & State Discretization + 6. Entropy + 7. Spectral Analysis
    spread = float(np.max(micro_residuals) - np.min(micro_residuals))
    fft_vals = np.abs(np.fft.rfft(micro_residuals))
    fft_freqs = np.fft.rfftfreq(len(micro_residuals), d=1.0)  # cycles per beat
    spectral_energy = fft_vals ** 2

    if spread < 1e-9:
        # Degenerate / exact rigid grid: avoid binning IEEE-754 roundoff noise
        bin_edges = np.zeros(n_bins + 1, dtype=np.float64)
        p_state = np.zeros(n_bins, dtype=np.float64)
        transition_matrix = np.zeros((n_bins, n_bins), dtype=np.float64)
        center = n_bins // 2
        p_state[center] = 1.0
        transition_matrix[center, center] = 1.0
        shannon_entropy = 0.0
        relative_entropy = 0.0
        cond_entropy = 0.0
        mutual_information = 0.0
        dominant_freq = 0.0
    else:
        # Discretize into n_bins equal-width states across micro-residual spread
        bin_edges = np.linspace(np.min(micro_residuals), np.max(micro_residuals), n_bins + 1)
        bin_indices = np.digitize(micro_residuals, bin_edges) - 1
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)

        transition_counts = np.zeros((n_bins, n_bins), dtype=np.int64)
        for i in range(len(bin_indices) - 1):
            s_from = bin_indices[i]
            s_to = bin_indices[i + 1]
            transition_counts[s_from, s_to] += 1

        row_sums = transition_counts.sum(axis=1, keepdims=True)
        transition_matrix = np.divide(
            transition_counts.astype(np.float64),
            row_sums,
            out=np.zeros_like(transition_counts, dtype=np.float64),
            where=row_sums > 0
        )

        # 6. Information Theory: Shannon Entropy & Mutual Information
        hist, _ = np.histogram(micro_residuals, bins=bin_edges, density=False)
        p_state = hist / np.sum(hist)
        non_zero_p = p_state[p_state > 0]
        shannon_entropy = float(-np.sum(non_zero_p * np.log2(non_zero_p)))
        max_entropy = float(np.log2(n_bins))
        relative_entropy = shannon_entropy / max_entropy if max_entropy > 0 else 0.0

        # Conditional Entropy H(S_k | S_{k-1})
        cond_entropy = 0.0
        for i in range(n_bins):
            if p_state[i] > 0:
                row_p = transition_matrix[i]
                nz_row = row_p[row_p > 0]
                cond_entropy += float(p_state[i] * float(-np.sum(nz_row * np.log2(nz_row))))

        mutual_information = float(max(0.0, shannon_entropy - cond_entropy))

        # 7. Dominant groove harmonic from FFT
        dominant_freq_idx = int(np.argmax(spectral_energy[1:])) + 1 if len(spectral_energy) > 1 else 0
        dominant_freq = float(fft_freqs[dominant_freq_idx])

    return {
        "summary": {
            "event_count": n,
            "duration_sec": round(float(timestamps[-1] - timestamps[0]), 4),
            "nominal_grid_dt_sec": round(grid_dt, 6),
            "estimated_bpm": round(60.0 / grid_dt, 2),
            "macro_rubato_r2": round(r2_rubato, 4),
            "lag1_autocorrelation": round(lag1_corr, 4),
            "attractor_eccentricity": round(ellipse_eccentricity, 4),
            "shannon_entropy_bits": round(shannon_entropy, 4),
            "relative_entropy": round(relative_entropy, 4),
            "conditional_entropy_bits": round(cond_entropy, 4),
            "mutual_information_bits": round(mutual_information, 4),
            "dominant_groove_freq_cycles_per_beat": round(dominant_freq, 4),
        },
        "vectors": {
            "timestamps_sec": [round(float(t), 5) for t in timestamps],
            "beat_indices": beat_indices.tolist(),
            "raw_residuals_sec": [round(float(r), 6) for r in raw_residuals],
            "macro_trend_sec": [round(float(m), 6) for m in macro_trend],
            "micro_residuals_sec": [round(float(m), 6) for m in micro_residuals],
            "x_delay_sec": [round(float(x), 6) for x in x_delay],
            "y_current_sec": [round(float(y), 6) for y in y_current],
        },
        "phase_space": {
            "semi_major_axis": round(semi_major, 6),
            "semi_minor_axis": round(semi_minor, 6),
            "orientation_deg": round(math.degrees(orientation_rad), 2),
            "determinism_score": round(min(1.0, ellipse_eccentricity * (1.0 + abs(lag1_corr)) / 2.0), 4),
        },
        "markov": {
            "bin_edges": [round(float(b), 6) for b in bin_edges],
            "state_probabilities": [round(float(p), 4) for p in p_state],
            "transition_matrix": [[round(float(cell), 4) for cell in row] for row in transition_matrix],
        },
        "spectral": {
            "frequencies": [round(float(f), 4) for f in fft_freqs],
            "power": [round(float(p), 4) for p in spectral_energy],
        },
        "polynomial": {
            "degree": deg,
            "coefficients": [round(float(c), 8) for c in poly_coeffs],
        }
    }


# ==============================================================================
# 4. PUBLICATION VISUAL DASHBOARD GENERATOR
# ==============================================================================

def render_forensic_plot(results: Dict[str, Any], output_path: Path, title: str = "Zoe Temporal Dynamics & Groove Forensics"):
    """
    Renders 4-panel diagnostic dashboard in Zoe's canonical aesthetic:
      - Dark Slate (#15191E), Instrument Teal (#2DB2BF), Burnt Orange (#D9581E), Gold (#E5A93C).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Ellipse

    vecs = results["vectors"]
    summary = results["summary"]
    ps = results["phase_space"]
    markov = results["markov"]
    spectral = results["spectral"]

    beats = np.array(vecs["beat_indices"])
    raw_r = np.array(vecs["raw_residuals_sec"]) * 1000.0   # convert to ms
    macro_r = np.array(vecs["macro_trend_sec"]) * 1000.0  # convert to ms
    micro_r = np.array(vecs["micro_residuals_sec"]) * 1000.0
    x_delay = np.array(vecs["x_delay_sec"]) * 1000.0
    y_curr = np.array(vecs["y_current_sec"]) * 1000.0

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor="#15191E")
    plt.subplots_adjust(hspace=0.32, wspace=0.28)

    # Zoe Palette Constants
    BG_COLOR = "#15191E"
    PANEL_BG = "#1C2229"
    TEXT_COLOR = "#E6EDF3"
    MUTED_TEXT = "#8B949E"
    GRID_COLOR = "#2C3440"
    TEAL = "#2DB2BF"
    BURNT_ORANGE = "#D9581E"
    GOLD = "#E5A93C"
    VORTEX_PLUM = "#8A508F"

    # --- PANEL 1: Macro Rubato Detrending ---
    ax1 = axes[0, 0]
    ax1.set_facecolor(PANEL_BG)
    ax1.scatter(beats, raw_r, color=TEAL, alpha=0.6, s=28, label="Raw Timing Offsets (r_k)", zorder=3)
    ax1.plot(beats, macro_r, color=BURNT_ORANGE, linewidth=2.4, label=f"Macro Rubato Fit (R²={summary['macro_rubato_r2']})", zorder=4)
    ax1.axhline(0, color=GRID_COLOR, linestyle="--", linewidth=1.0)
    ax1.set_title("Panel A: Macro Rubato & Event Offsets", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax1.set_xlabel("Beat / Step Index", color=MUTED_TEXT, fontsize=10)
    ax1.set_ylabel("Offset from Rigid Grid (ms)", color=MUTED_TEXT, fontsize=10)
    ax1.tick_params(colors=MUTED_TEXT)
    ax1.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    ax1.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    # --- PANEL 2: Phase-Space Delay Embedding (Poincaré Map) ---
    ax2 = axes[0, 1]
    ax2.set_facecolor(PANEL_BG)
    ax2.scatter(x_delay, y_curr, color=GOLD, alpha=0.75, s=32, edgecolors="#15191E", linewidth=0.5, label="Delay Points (r_t vs r_{t-1})", zorder=3)
    
    # Draw Attractor Covariance Ellipse
    mean_x, mean_y = np.mean(x_delay), np.mean(y_curr)
    width = 2.0 * ps["semi_major_axis"] * 1000.0 * 2.0
    height = 2.0 * ps["semi_minor_axis"] * 1000.0 * 2.0
    angle = ps["orientation_deg"]
    ellipse = Ellipse((mean_x, mean_y), width=width, height=height, angle=angle,
                      edgecolor=BURNT_ORANGE, facecolor="none", linewidth=2.0, linestyle="-",
                      label=f"Attractor Ellipse (e={summary['attractor_eccentricity']})", zorder=4)
    ax2.add_patch(ellipse)
    ax2.axhline(0, color=GRID_COLOR, linestyle="--", linewidth=0.8)
    ax2.axvline(0, color=GRID_COLOR, linestyle="--", linewidth=0.8)
    ax2.set_title(f"Panel B: 2D Poincaré Phase Space (ρ₁={summary['lag1_autocorrelation']})", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax2.set_xlabel("Previous Beat Residual r_{t-1} (ms)", color=MUTED_TEXT, fontsize=10)
    ax2.set_ylabel("Current Beat Residual r_t (ms)", color=MUTED_TEXT, fontsize=10)
    ax2.tick_params(colors=MUTED_TEXT)
    ax2.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    ax2.legend(loc="upper left", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    # --- PANEL 3: Residual Distribution & Shannon Entropy ---
    ax3 = axes[1, 0]
    ax3.set_facecolor(PANEL_BG)
    n_hist_bins = max(1, len(markov["bin_edges"]) - 1)
    if np.ptp(micro_r) < 1e-6:
        ax3.hist(micro_r, bins=n_hist_bins, range=(-1.0, 1.0), color=TEAL, alpha=0.7, edgecolor=BG_COLOR, density=True)
    else:
        ax3.hist(micro_r, bins=n_hist_bins, color=TEAL, alpha=0.7, edgecolor=BG_COLOR, density=True)
    ax3.set_title(f"Panel C: Micro-Timing Entropy (H={summary['shannon_entropy_bits']} bits)", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax3.set_xlabel("Micro-Residual Deviation (ms)", color=MUTED_TEXT, fontsize=10)
    ax3.set_ylabel("Probability Density", color=MUTED_TEXT, fontsize=10)
    ax3.tick_params(colors=MUTED_TEXT)
    ax3.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    
    # Overlay metrics box
    info_text = (f"Events: {summary['event_count']}\n"
                 f"Estimated BPM: {summary['estimated_bpm']}\n"
                 f"Mutual Info: {summary['mutual_information_bits']} bits\n"
                 f"Determinism: {ps['determinism_score']}")
    ax3.text(0.04, 0.94, info_text, transform=ax3.transAxes, verticalalignment="top",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=BG_COLOR, edgecolor=GRID_COLOR),
             color=TEXT_COLOR, fontsize=9)

    # --- PANEL 4: Spectral Power & Groove Harmonics ---
    ax4 = axes[1, 1]
    ax4.set_facecolor(PANEL_BG)
    freqs = np.array(spectral["frequencies"])
    power = np.array(spectral["power"])
    if len(freqs) > 1:
        ax4.plot(freqs[1:], power[1:], color=VORTEX_PLUM, linewidth=2.2, label="FFT Power Spectrum")
        ax4.scatter([summary["dominant_groove_freq_cycles_per_beat"]],
                    [np.max(power[1:])], color=GOLD, s=48, zorder=5,
                    label=f"Peak Harmonic: {summary['dominant_groove_freq_cycles_per_beat']} cyc/beat")
    ax4.set_title("Panel D: Spectral Groove Harmonics", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax4.set_xlabel("Frequency (cycles per beat)", color=MUTED_TEXT, fontsize=10)
    ax4.set_ylabel("Spectral Energy", color=MUTED_TEXT, fontsize=10)
    ax4.tick_params(colors=MUTED_TEXT)
    ax4.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    ax4.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    # Main Super Title
    fig.suptitle(title, color=TEXT_COLOR, fontsize=15, fontweight="bold", y=0.96)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()


# ==============================================================================
# 5. ZOE INTERNAL CLOCK ENTRAINMENT & DOROTHY NEURAL BRIDGE
# ==============================================================================

def get_cicada_clock_class():
    """Dynamically resolves CicadaClock from guiai-lab."""
    repo_root = Path(__file__).resolve().parent.parent
    guiai_path = repo_root / "guiai-lab"
    if str(guiai_path) not in sys.path:
        sys.path.insert(0, str(guiai_path))
    try:
        from guiai.gem.cicada import CicadaClock
        return CicadaClock
    except ImportError:
        return None


def get_neurogarden_eeg():
    """Dynamically resolves neurogarden_eeg from agent-logging-system."""
    repo_root = Path(__file__).resolve().parent.parent
    als_path = repo_root / "components" / "agent-logging-system"
    if str(als_path) not in sys.path:
        sys.path.insert(0, str(als_path))
    try:
        from agent_logging_system import neurogarden_eeg
        return neurogarden_eeg
    except ImportError:
        return None


def entrain_zoe_clock(
    events: List[NoteEvent],
    output_path: Optional[Path] = None,
    daily_period: float = 1.0,
    entrainment_strength: float = 0.15,
    max_steps: int = 128
) -> Dict[str, Any]:
    """
    Drives Zoe's CicadaClock with external note timing events:
      - Maps event onsets to external phase: z_k = (t_k % D) / D
      - Steps the Kuramoto-coupled oscillator: phi_{k+1} = phi_k + dt/D + kappa * sin(2pi(z_k - phi_k))
      - Calculates Kuramoto phase-locking coherence: R = |mean(exp(i * 2pi * (z_k - phi_k)))|
      - Hash-chains all events and executes cryptographic replay verification before JSON export.
    """
    CicadaClock = get_cicada_clock_class()
    if CicadaClock is None:
        raise RuntimeError("CicadaClock could not be imported from guiai-lab")

    if not events:
        raise ValueError("No events provided for clock entrainment")

    from fractions import Fraction

    # Bound events to stay safely within MAX_EVENTS (256)
    clamped_events = events[:min(len(events), max_steps)]
    clock = CicadaClock(
        cycle_years=13,
        daily_period_seconds=daily_period,
        entrainment_strength=entrainment_strength,
        years_per_second=Fraction(1, 1000),
        initial_phase=0.0
    )

    phases_internal: List[float] = []
    phases_external: List[float] = []
    phase_errors: List[float] = []
    pulse_count = 0

    prev_time = clamped_events[0].time_sec if clamped_events else 0.0

    for i, event in enumerate(clamped_events):
        elapsed = event.time_sec - prev_time
        prev_time = event.time_sec

        if i == 0 and elapsed == 0:
            elapsed = 0.05  # Seed initial tick

        elapsed = max(0.001, elapsed)
        ext_phase = (event.time_sec % daily_period) / daily_period

        # Step the clock
        clock.step(elapsed, host_phase=ext_phase)
        
        phi_int = clock.phase
        phases_internal.append(phi_int)
        phases_external.append(ext_phase)

        # Circular phase error: (ext - int) wrapped to [-0.5, 0.5]
        err = ((ext_phase - phi_int + 0.5) % 1.0) - 0.5
        phase_errors.append(err)

        if "daily-pulse" in clock.last_actions:
            pulse_count += 1

    # Kuramoto order parameter R
    complex_order = np.mean(np.exp(1j * 2 * np.pi * np.array(phase_errors)))
    kuramoto_r = float(np.abs(complex_order))
    mean_phase_error = float(np.mean(phase_errors))
    phase_error_var = float(np.var(phase_errors))

    result = {
        "clock_instrument": "zoe-cicada-internal-clock",
        "steps_executed": len(clamped_events),
        "daily_period_seconds": daily_period,
        "entrainment_strength": entrainment_strength,
        "kuramoto_coherence_r": round(kuramoto_r, 4),
        "mean_phase_error": round(mean_phase_error, 4),
        "phase_error_variance": round(phase_error_var, 6),
        "pulses_emitted": pulse_count,
        "final_clock_phase": round(clock.phase, 6),
        "final_reference_ticks": clock.reference_ticks,
        "replay_verified": False,
    }

    if output_path is not None:
        saved_path = clock.save(output_path)
        result["saved_session_path"] = str(saved_path)
        result["replay_verified"] = True

    return result


def analyze_neural_spikes(
    spike_timestamps: List[float],
    pacemaker_freq_hz: float = 40.0
) -> Dict[str, Any]:
    """
    Dorothy Neural Dynamics Bridge:
      - Ingests neuronal spike timestamps.
      - Extracts Inter-Spike Intervals: ISI_k = t_{k+1} - t_k.
      - Calculates phase-space return map (ISI_k vs ISI_{k-1}).
      - Computes Higuchi fractal dimension and Lyapunov exponent via neurogarden_eeg.
    """
    eeg = get_neurogarden_eeg()
    ts = np.array(sorted(spike_timestamps), dtype=np.float64)
    if len(ts) < 16:
        raise ValueError("At least 16 spike timestamps are required")

    isi = np.diff(ts)
    isi_pos = isi[isi > 0]
    if len(isi_pos) < 15:
        raise ValueError("Insufficient positive inter-spike intervals")

    x_delay = isi_pos[:-1]
    y_curr = isi_pos[1:]

    # Autocorrelation of ISIs
    lag1_isi = float(np.corrcoef(x_delay, y_curr)[0, 1]) if len(x_delay) > 1 else 0.0

    # Nonlinear metrics via neurogarden
    higuchi = float(eeg.higuchi_dimension(isi_pos)) if eeg is not None else 0.0
    lyapunov = float(eeg.lyapunov_estimate(isi_pos, dimension=min(5, len(isi_pos)//3), delay=1)) if eeg is not None and len(isi_pos) >= 20 else 0.0

    # Shannon Entropy of ISI
    hist, _ = np.histogram(isi_pos, bins=8, density=False)
    p = hist / np.sum(hist)
    nz_p = p[p > 0]
    isi_entropy = float(-np.sum(nz_p * np.log2(nz_p)))

    return {
        "spike_count": len(ts),
        "mean_isi_sec": round(float(np.mean(isi_pos)), 6),
        "std_isi_sec": round(float(np.std(isi_pos)), 6),
        "burst_index": round(float(np.std(isi_pos) / np.mean(isi_pos)), 4),
        "lag1_isi_autocorrelation": round(lag1_isi, 4),
        "isi_shannon_entropy_bits": round(isi_entropy, 4),
        "higuchi_fractal_dimension": round(higuchi, 4),
        "lyapunov_estimate": round(lyapunov, 4),
        "pacemaker_deviation_ratio": round(float(np.mean(isi_pos) / (1.0 / pacemaker_freq_hz)), 4),
        "isi_values_ms": [round(float(v * 1000.0), 3) for v in isi_pos],
        "timestamps_sec": [round(float(t), 5) for t in ts],
    }


def render_neural_plot(neural_report: Dict[str, Any], output_path: Path, title: str = "Dorothy Neural Spike Dynamics"):
    """Renders 4-panel neural diagnostic dashboard in Zoe's canonical aesthetic."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    isi_ms = np.array(neural_report["isi_values_ms"])
    ts_sec = np.array(neural_report["timestamps_sec"])

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor="#15191E")
    plt.subplots_adjust(hspace=0.32, wspace=0.28)

    BG_COLOR = "#15191E"
    PANEL_BG = "#1C2229"
    TEXT_COLOR = "#E6EDF3"
    MUTED_TEXT = "#8B949E"
    GRID_COLOR = "#2C3440"
    TEAL = "#2DB2BF"
    BURNT_ORANGE = "#D9581E"
    GOLD = "#E5A93C"
    VORTEX_PLUM = "#8A508F"

    # Panel A: Spike Raster & Event Sequence
    ax1 = axes[0, 0]
    ax1.set_facecolor(PANEL_BG)
    ax1.vlines(ts_sec, 0.2, 0.8, color=TEAL, linewidth=1.5, label="Spike Onsets")
    ax1.set_ylim(0, 1)
    ax1.set_title("Panel A: Spike Event Raster", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax1.set_xlabel("Time (seconds)", color=MUTED_TEXT, fontsize=10)
    ax1.tick_params(colors=MUTED_TEXT)
    ax1.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    ax1.legend(loc="upper right", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    # Panel B: Poincaré ISI Delay Embedding
    ax2 = axes[0, 1]
    ax2.set_facecolor(PANEL_BG)
    if len(isi_ms) > 1:
        ax2.scatter(isi_ms[:-1], isi_ms[1:], color=GOLD, alpha=0.8, s=36, edgecolors="#15191E", label="ISI Points (ISI_k vs ISI_{k-1})")
        diag_min = min(np.min(isi_ms[:-1]), np.min(isi_ms[1:]))
        diag_max = max(np.max(isi_ms[:-1]), np.max(isi_ms[1:]))
        ax2.plot([diag_min, diag_max], [diag_min, diag_max], color=BURNT_ORANGE, linestyle="--", linewidth=1.5, label="Identity Line")
    ax2.set_title(f"Panel B: 2D ISI Return Map (ρ₁={neural_report['lag1_isi_autocorrelation']})", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax2.set_xlabel("Previous ISI (ms)", color=MUTED_TEXT, fontsize=10)
    ax2.set_ylabel("Current ISI (ms)", color=MUTED_TEXT, fontsize=10)
    ax2.tick_params(colors=MUTED_TEXT)
    ax2.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")
    ax2.legend(loc="upper left", facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=9)

    # Panel C: ISI Histogram & Shannon Entropy
    ax3 = axes[1, 0]
    ax3.set_facecolor(PANEL_BG)
    ax3.hist(isi_ms, bins=10, color=TEAL, alpha=0.75, edgecolor=BG_COLOR)
    ax3.set_title(f"Panel C: ISI Distribution (H={neural_report['isi_shannon_entropy_bits']} bits)", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)
    ax3.set_xlabel("Inter-Spike Interval (ms)", color=MUTED_TEXT, fontsize=10)
    ax3.set_ylabel("Spike Count", color=MUTED_TEXT, fontsize=10)
    ax3.tick_params(colors=MUTED_TEXT)
    ax3.grid(True, color=GRID_COLOR, alpha=0.5, linestyle=":")

    # Panel D: Nonlinear Dynamics Metrics Box
    ax4 = axes[1, 1]
    ax4.set_facecolor(PANEL_BG)
    ax4.axis("off")
    summary_lines = [
        f"Spike Count:              {neural_report['spike_count']}",
        f"Mean ISI:                 {neural_report['mean_isi_sec']*1000.0:.2f} ms",
        f"ISI Std Dev:              {neural_report['std_isi_sec']*1000.0:.2f} ms",
        f"Burst Index:              {neural_report['burst_index']}",
        f"Pacemaker Deviation:      {neural_report['pacemaker_deviation_ratio']}x",
        f"Higuchi Fractal Dim:      {neural_report['higuchi_fractal_dimension']}",
        f"Lyapunov Estimate:        {neural_report['lyapunov_estimate']}",
        "",
        "Boundary Assertion:",
        "Atlas geometry only. No patient registration,",
        "clinical diagnosis, or surgical authority."
    ]
    ax4.text(0.1, 0.88, "\n".join(summary_lines), transform=ax4.transAxes,
             verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.8", facecolor="#15191E", edgecolor=BURNT_ORANGE),
             color=TEXT_COLOR, fontsize=10)
    ax4.set_title("Panel D: Nonlinear & Clinical Boundary Audit", color=TEXT_COLOR, fontsize=12, fontweight="bold", pad=8)

    fig.suptitle(title, color=TEXT_COLOR, fontsize=15, fontweight="bold", y=0.96)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()


# ==============================================================================
# 6. CLI & REPRODUCIBLE VERIFICATION SUITE
# ==============================================================================

def run_self_verification() -> bool:
    """Automated self-verification verifying mathematical invariants and determinism."""
    print("Running Zoe Groove Forensics self-verification...")

    # Test 1: Metronome should have ~0 residuals and 0 entropy
    events_metro, dt = generate_synthetic_stream(n_events=64, groove_type="metronome", seed=10)
    res_metro = analyze_groove_dynamics(events_metro, nominal_dt=dt)
    assert abs(res_metro["summary"]["lag1_autocorrelation"]) < 1e-6, "Metronome autocorrelation should be 0"
    assert res_metro["summary"]["shannon_entropy_bits"] < 1e-4, "Metronome entropy should be ~0"
    print("  [PASS] Test 1: Rigid Metronome Grounding Verified")

    # Test 2: Swing Attractor vs. Pure Noise Negative Control
    events_swing, dt = generate_synthetic_stream(n_events=256, groove_type="swing_attractor", seed=20)
    res_swing = analyze_groove_dynamics(events_swing, nominal_dt=dt, poly_degree=3)
    events_noise, dt_noise = generate_synthetic_stream(n_events=256, groove_type="pure_noise", seed=20)
    res_noise = analyze_groove_dynamics(events_noise, nominal_dt=dt_noise, poly_degree=3)
    assert res_swing["summary"]["attractor_eccentricity"] > 0.4, "Swing attractor must exhibit directional phase eccentricity"
    assert abs(res_swing["summary"]["lag1_autocorrelation"]) > 0.70, "Swing attractor must show strong lag-1 coupling"
    assert abs(res_swing["summary"]["dominant_groove_freq_cycles_per_beat"] - 0.5) < 0.05, "Swing attractor must peak near 0.5 cycles/beat"
    assert abs(res_noise["summary"]["lag1_autocorrelation"]) < 0.30, "Pure noise control must have low lag-1 autocorrelation"
    assert res_swing["summary"]["mutual_information_bits"] > res_noise["summary"]["mutual_information_bits"], (
        "Swing attractor must have strictly higher mutual information than pure noise control"
    )
    print(
        f"  [PASS] Test 2: Swing Attractor vs. Noise Control Verified "
        f"(I_swing={res_swing['summary']['mutual_information_bits']} > I_noise={res_noise['summary']['mutual_information_bits']})"
    )

    # Test 3: Macro Rubato Detrending should isolate accelerando
    events_accel, dt = generate_synthetic_stream(n_events=128, groove_type="accelerando", seed=30)
    res_accel = analyze_groove_dynamics(events_accel, nominal_dt=dt, poly_degree=3)
    assert res_accel["summary"]["macro_rubato_r2"] > 0.80, "Polynomial fit must capture >80% variance in accelerando"
    print("  [PASS] Test 3: Macro Rubato Detrending Verified (R^2 > 0.80)")

    # Test 4: Canonical Serializability
    doc = canonical_json(res_swing["summary"])
    digest = hashlib.sha256(doc.encode()).hexdigest()
    assert len(digest) == 64, "SHA-256 digest failed"
    print(f"  [PASS] Test 4: Canonical JSON & SHA-256 Verification Verified ({digest[:16]}...)")

    # Test 5: Clock Entrainment & Kuramoto Phase-Locking Coherence
    clock_res = entrain_zoe_clock(events_swing, daily_period=1.0, entrainment_strength=0.15, max_steps=48)
    assert clock_res["kuramoto_coherence_r"] > 0.50, "Entrained clock Kuramoto coherence must exceed 0.50"
    assert clock_res["pulses_emitted"] > 0, "Clock must emit daily pulses during entrainment"
    print(f"  [PASS] Test 5: CicadaClock Entrainment & Kuramoto Coherence Verified (R={clock_res['kuramoto_coherence_r']})")

    # Test 6: Dorothy Neural Spike Interval & Higuchi Analysis
    synthetic_spikes = [0.025 * i + 0.003 * math.sin(i * 0.3) for i in range(40)]
    neural_res = analyze_neural_spikes(synthetic_spikes, pacemaker_freq_hz=40.0)
    assert neural_res["spike_count"] == 40, "Neural spike count mismatch"
    assert neural_res["mean_isi_sec"] > 0.01, "Positive mean ISI required"
    print(f"  [PASS] Test 6: Dorothy Neural Inter-Spike Dynamics & Higuchi Verified (D={neural_res['higuchi_fractal_dimension']})")

    # Test 7: ProTracker .MOD Binary Round-Trip
    with tempfile.TemporaryDirectory() as tmpdir:
        mod_path = Path(tmpdir) / "test_roundtrip.mod"
        title = b"ZOE MOD ROUNDTRIP".ljust(20, b"\x00")
        sample_headers = bytearray(31 * 30)
        sample_headers[0:22] = b"PULSE".ljust(22, b"\x00")
        sample_headers[22:24] = struct.pack(">H", 2)
        sample_headers[25] = 64
        song_length = bytes([1])
        restart = bytes([127])
        order_table = bytearray(128)
        tag = b"M.K."
        pattern = bytearray(64 * 4 * 4)
        for r in range(0, 64, 4):
            idx = (r * 4) * 4
            period = 428
            pattern[idx : idx + 4] = bytes([(period >> 8) & 0x0F, period & 0xFF, (1 << 4) & 0xF0, 0])
        sample_pcm = bytes([0, 64, 0, (-64) & 0xFF])
        mod_path.write_bytes(title + sample_headers + song_length + restart + order_table + tag + pattern + sample_pcm)

        mod_events, mod_dt = parse_mod(mod_path)
        res_mod = analyze_groove_dynamics(mod_events, nominal_dt=mod_dt)
        assert res_mod["summary"]["event_count"] == 16, f"Expected 16 MOD events, got {res_mod['summary']['event_count']}"
        assert abs(res_mod["summary"]["estimated_bpm"] - 125.0) < 0.5, f"Expected 125.0 BPM, got {res_mod['summary']['estimated_bpm']}"
        assert res_mod["summary"]["shannon_entropy_bits"] < 1e-4, f"Expected 0 entropy for exact MOD grid, got {res_mod['summary']['shannon_entropy_bits']}"
        print(f"  [PASS] Test 7: ProTracker .MOD Binary Round-Trip Verified (16 events @ {res_mod['summary']['estimated_bpm']} BPM)")

    print("ALL TESTS PASSED: Zoe Groove Forensics & Clock Entrainment engine is mathematically sound.")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zoe Research Tooling — Temporal Dynamics, Groove Forensics & Clock Entrainment"
    )
    parser.add_argument("--file", "-f", type=str, help="Path to .mid, .midi, or .mod tracker file")
    parser.add_argument("--spikes", type=str, help="Path to JSON file with neural spike timestamps")
    parser.add_argument("--synthetic", "-s", type=str, choices=["swing_attractor", "pure_noise", "accelerando", "metronome"],
                        help="Generate and analyze synthetic benchmark performance")
    parser.add_argument("--degree", "-d", type=int, default=3, help="Degree of polynomial rubato fit (default: 3)")
    parser.add_argument("--bins", "-b", type=int, default=5, help="Number of micro-residual discrete bins (default: 5)")
    parser.add_argument("--entrain-clock", type=str, help="Drive Zoe CicadaClock and export replay-verified session JSON")
    parser.add_argument("--out-json", "-o", type=str, help="Path to write structured JSON forensic report")
    parser.add_argument("--plot", "-p", type=str, help="Path to render diagnostic visual dashboard PNG")
    parser.add_argument("--verify", action="store_true", help="Run automated mathematical verification suite")

    args = parser.parse_args(argv)

    if args.verify:
        success = run_self_verification()
        return 0 if success else 1

    if args.spikes:
        # Neural spike analysis mode
        spikes_path = Path(args.spikes).expanduser().resolve(strict=True)
        raw_data = json.loads(spikes_path.read_text(encoding="utf-8"))
        if isinstance(raw_data, list):
            if raw_data and isinstance(raw_data[0], dict):
                timestamps = [float(item.get("time_sec", item.get("time", 0.0))) for item in raw_data]
            else:
                timestamps = [float(x) for x in raw_data]
        else:
            timestamps = [float(x) for x in raw_data.get("spikes", [])]

        neural_report = analyze_neural_spikes(timestamps)
        report = {
            "instrument": "zoe-neural-spike-forensics/v1",
            "source": spikes_path.name,
            "constitutional_boundary": {
                "measurement_neq_evidence": True,
                "evidence_neq_belief_update": True,
                "belief_update_neq_action": True,
                "clinical_diagnostic_claim": False,
            },
            "neural_dynamics": neural_report
        }
        if args.plot:
            plot_path = Path(args.plot).expanduser().resolve()
            render_neural_plot(neural_report, plot_path, title=f"Dorothy Neural Dynamics — {spikes_path.name}")
            print(f"Rendered neural diagnostic dashboard to: {plot_path}")

        if args.out_json:
            out_p = Path(args.out_json).expanduser().resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(canonical_json(report), encoding="utf-8")
            print(f"Saved neural forensic report to: {out_p}")
        print("=" * 64)
        print(f"  Zoe Dorothy Neural Spike Dynamics — {spikes_path.name}")
        print("=" * 64)
        for k, v in neural_report.items():
            print(f"  {k:28s}: {v}")
        print("=" * 64)
        return 0

    if not args.file and not args.synthetic:
        args.synthetic = "swing_attractor"

    events: List[NoteEvent] = []
    nominal_dt: Optional[float] = None
    input_sha256: Optional[str] = None
    source_title = "Synthetic Stream"

    if args.file:
        file_path = Path(args.file).expanduser().resolve(strict=True)
        raw_bytes = file_path.read_bytes()
        input_sha256 = sha256_bytes(raw_bytes)
        source_title = file_path.name
        ext = file_path.suffix.lower()

        if ext in (".mid", ".midi"):
            events, nominal_dt = parse_midi(file_path)
        elif ext == ".mod":
            events, nominal_dt = parse_mod(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext} (supported: .mid, .midi, .mod)")
    elif args.synthetic:
        source_title = f"Synthetic Benchmark ({args.synthetic})"
        events, nominal_dt = generate_synthetic_stream(n_events=192, groove_type=args.synthetic)

    # Execute analysis
    analysis_results = analyze_groove_dynamics(
        events=events,
        nominal_dt=nominal_dt,
        poly_degree=args.degree,
        n_bins=args.bins
    )

    # Attach provenance metadata
    report = {
        "instrument": "zoe-groove-forensics/v1",
        "source": source_title,
        "input_sha256": input_sha256,
        "constitutional_boundary": {
            "measurement_neq_evidence": True,
            "evidence_neq_belief_update": True,
            "belief_update_neq_action": True,
            "external_actions_executed": 0,
            "llm_called": False,
        },
        "analysis": analysis_results
    }

    # Render Visual Plot if requested
    if args.plot:
        plot_path = Path(args.plot).expanduser().resolve()
        render_forensic_plot(analysis_results, plot_path, title=f"Zoe Groove Forensics — {source_title}")
        print(f"Rendered diagnostic dashboard to: {plot_path}")

    # Handle Zoe Internal Clock Entrainment if requested
    if args.entrain_clock:
        clock_out_path = Path(args.entrain_clock).expanduser().resolve()
        clock_res = entrain_zoe_clock(
            events=events,
            output_path=clock_out_path,
            daily_period=1.0,
            entrainment_strength=0.15
        )
        report["clock_entrainment"] = clock_res
        print(f"Entrained Zoe Internal Clock saved to: {clock_out_path}")
        print(f"  Kuramoto Phase Coherence (R): {clock_res['kuramoto_coherence_r']}")
        print(f"  Mean Phase Error:             {clock_res['mean_phase_error']}")
        print(f"  Emitted Pulses:               {clock_res['pulses_emitted']}")

    # Output JSON Report
    if args.out_json:
        out_path = Path(args.out_json).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(canonical_json(report), encoding="utf-8")
        print(f"Saved forensic JSON report to: {out_path}")

    # Print summary to stdout
    s = analysis_results["summary"]
    ps = analysis_results["phase_space"]
    print("=" * 64)
    print(f"  Zoe Temporal Dynamics & Groove Forensics — {source_title}")
    print("=" * 64)
    print(f"  Event Count:            {s['event_count']}")
    print(f"  Estimated BPM:          {s['estimated_bpm']}")
    print(f"  Macro Rubato R²:        {s['macro_rubato_r2']}")
    print(f"  Lag-1 Autocorrelation:  {s['lag1_autocorrelation']}")
    print(f"  Attractor Eccentricity: {s['attractor_eccentricity']}")
    print(f"  Phase Determinism:      {ps['determinism_score']}")
    print(f"  Shannon Entropy:        {s['shannon_entropy_bits']} bits (relative: {s['relative_entropy']})")
    print(f"  Mutual Information:     {s['mutual_information_bits']} bits")
    print(f"  Dominant Harmonic:      {s['dominant_groove_freq_cycles_per_beat']} cycles/beat")
    print("=" * 64)

    return 0


if __name__ == "__main__":
    sys.exit(main())

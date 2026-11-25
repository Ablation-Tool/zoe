#!/usr/bin/env python3
"""Original polyphonic C-major/pentatonic music generator for Musical Math Chairs (R1).

Synthesizes a 24.0-second, 44.1 kHz, 16-bit stereo PCM WAV file featuring:
  - Warm C-major chord progression (Cmaj7 -> G6 -> Am7 -> Fmaj7)
  - Syncopated C-major pentatonic Rhodes/bell melody with stereo panning
  - Soft rhythmic pulse (sub-bass thump + woodblock tick)
  - Distinct harmonic rotation-cue chimes marking chair-swap cadences
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH_BYTES = 2
BPM = 120.0
BEAT_SEC = 60.0 / BPM  # 0.5 s per beat
BARS = 12
BEATS_PER_BAR = 4
DURATION_SECONDS = BARS * BEATS_PER_BAR * BEAT_SEC  # 24.0 s

# C-major pentatonic pitches (Hz)
PENTATONIC_HZ: Dict[str, float] = {
    "C4": 261.6256,
    "D4": 293.6648,
    "E4": 329.6276,
    "G4": 391.9954,
    "A4": 440.0000,
    "C5": 523.2511,
    "D5": 587.3295,
    "E5": 659.2551,
    "G5": 783.9909,
    "A5": 880.0000,
    "C6": 1046.5023,
}

# 4-bar harmonic cycle repeated 3 times: I -> V -> vi -> IV
CHORD_PROGRESSION: List[Tuple[str, float, Tuple[float, ...]]] = [
    ("Cmaj7", 130.8128, (261.6256, 329.6276, 391.9954, 493.8833)),
    ("G6", 97.9989, (246.9417, 293.6648, 329.6276, 391.9954)),
    ("Am7", 110.0000, (220.0000, 261.6256, 329.6276, 391.9954)),
    ("Fmaj7", 87.3071, (220.0000, 261.6256, 329.6276, 440.0000)),
]

# Three 4-bar melodic motifs (each bar has 8 eighth-note steps, None = rest)
MELODY_PHRASES: List[List[Tuple[str | None, ...]]] = [
    # Phrase 1 (bars 0..3): Bright playful opening
    [
        ("E5", None, "G5", "E5", "D5", None, "C5", None),
        ("D5", None, "E5", "G5", "E5", "D5", "B4_SKIP", None),
        ("C5", None, "E5", "A5", "G5", None, "E5", "D5"),
        ("C5", "D5", "E5", None, "G5", None, "E5", None),
    ],
    # Phrase 2 (bars 4..7): Upbeat bouncing chair-dance
    [
        ("G5", None, "E5", "C5", "D5", "E5", "G5", None),
        ("A5", None, "G5", "E5", "D5", None, "E5", "G5"),
        ("E5", "G5", "A5", None, "G5", "E5", "C5", None),
        ("D5", "E5", "G5", "A5", "G5", None, "E5", None),
    ],
    # Phrase 3 (bars 8..11): Triumphant cadence + 30s rotation chime lead-in
    [
        ("C5", "E5", "G5", None, "A5", "G5", "E5", "D5"),
        ("E5", None, "G5", "A5", "G5", None, "D5", None),
        ("C5", "D5", "E5", "G5", "A5", "G5", "E5", "C5"),
        ("D5", "E5", "G5", None, "C6", None, None, None),
    ],
]

NOTE_FALLBACK_HZ: Dict[str, float] = {
    **PENTATONIC_HZ,
    "B4_SKIP": 293.6648,  # D4 keeps pure pentatonic warmth
}


def _adsr_envelope(length: int, sr: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    """Builds a smooth piecewise envelope of length samples."""
    if length <= 0:
        return np.zeros(0, dtype=np.float64)
    env = np.empty(length, dtype=np.float64)
    a_n = min(length, max(1, int(attack * sr)))
    d_n = min(max(0, length - a_n), int(decay * sr))
    r_n = min(max(0, length - a_n - d_n), int(release * sr))
    s_n = max(0, length - a_n - d_n - r_n)

    idx = 0
    env[idx : idx + a_n] = np.linspace(0.0, 1.0, a_n, endpoint=False)
    idx += a_n
    if d_n > 0:
        env[idx : idx + d_n] = np.linspace(1.0, sustain, d_n, endpoint=False)
        idx += d_n
    if s_n > 0:
        env[idx : idx + s_n] = sustain
        idx += s_n
    if r_n > 0:
        start_val = sustain if (d_n > 0 or s_n > 0) else 1.0
        env[idx : idx + r_n] = np.linspace(start_val, 0.0, r_n, endpoint=True)
    return env


def _synth_rhodes_tone(freq: float, dur_sec: float, sr: int, amp: float) -> np.ndarray:
    """Warm electric-piano / chime tone using damped harmonics."""
    n = int(dur_sec * sr)
    t = np.arange(n, dtype=np.float64) / sr
    # Fundamental + soft 2nd & 3rd partials + faint bell tine transient
    tone = (
        0.68 * np.sin(2.0 * math.pi * freq * t)
        + 0.22 * np.sin(2.0 * math.pi * (2.0 * freq) * t) * np.exp(-t * 4.5)
        + 0.10 * np.sin(2.0 * math.pi * (3.0 * freq) * t) * np.exp(-t * 8.0)
        + 0.05 * np.sin(2.0 * math.pi * (4.0 * freq) * t) * np.exp(-t * 14.0)
    )
    env = _adsr_envelope(n, sr, attack=0.012, decay=0.14, sustain=0.45, release=min(0.18, dur_sec * 0.4))
    return amp * tone * env


def _synth_pad_chord(freqs: Sequence[float], dur_sec: float, sr: int, amp: float) -> np.ndarray:
    """Lush slow-breathing harmonic pad."""
    n = int(dur_sec * sr)
    t = np.arange(n, dtype=np.float64) / sr
    acc = np.zeros(n, dtype=np.float64)
    for idx, f in enumerate(freqs):
        detune = 1.0 + (idx - 1.5) * 0.0012
        acc += np.sin(2.0 * math.pi * f * detune * t)
        acc += 0.25 * np.sin(2.0 * math.pi * (2.0 * f * detune) * t)
    acc /= max(1, len(freqs))
    env = _adsr_envelope(n, sr, attack=0.18, decay=0.35, sustain=0.65, release=0.35)
    return amp * acc * env


def _synth_bass(freq: float, dur_sec: float, sr: int, amp: float) -> np.ndarray:
    """Warm round bass note."""
    n = int(dur_sec * sr)
    t = np.arange(n, dtype=np.float64) / sr
    wave_sig = 0.80 * np.sin(2.0 * math.pi * freq * t) + 0.20 * np.sin(2.0 * math.pi * (2.0 * freq) * t)
    env = _adsr_envelope(n, sr, attack=0.015, decay=0.18, sustain=0.55, release=0.15)
    return amp * wave_sig * env


def _synth_percussion_tick(is_kick: bool, sr: int) -> np.ndarray:
    """Soft rhythmic pulse: warm sub thump on downbeats, gentle woodblock tick on offbeats."""
    if is_kick:
        dur = 0.14
        n = int(dur * sr)
        t = np.arange(n, dtype=np.float64) / sr
        freq_sweep = 110.0 * np.exp(-t * 28.0) + 48.0
        phase = 2.0 * math.pi * np.cumsum(freq_sweep) / sr
        return 0.22 * np.sin(phase) * np.exp(-t * 20.0)
    dur = 0.07
    n = int(dur * sr)
    t = np.arange(n, dtype=np.float64) / sr
    sig = 0.10 * np.sin(2.0 * math.pi * 880.0 * t) + 0.05 * np.sin(2.0 * math.pi * 1320.0 * t)
    return sig * np.exp(-t * 52.0)


def _synth_cue_chime(freqs: Sequence[float], sr: int, amp: float) -> Tuple[np.ndarray, np.ndarray]:
    """Stereo shimmering chair-swap cue arpeggio."""
    step_samples = int(0.09 * sr)
    note_dur = 0.65
    note_len = int(note_dur * sr)
    total_len = step_samples * len(freqs) + note_len
    left = np.zeros(total_len, dtype=np.float64)
    right = np.zeros(total_len, dtype=np.float64)
    for i, f in enumerate(freqs):
        start = i * step_samples
        t = np.arange(note_len, dtype=np.float64) / sr
        bell = (
            0.70 * np.sin(2.0 * math.pi * f * t)
            + 0.25 * np.sin(2.0 * math.pi * (2.0 * f) * t)
            + 0.10 * np.sin(2.0 * math.pi * (3.0 * f) * t)
        ) * np.exp(-t * 4.2)
        env = _adsr_envelope(note_len, sr, attack=0.004, decay=0.10, sustain=0.35, release=0.30)
        sig = amp * bell * env
        pan = 0.25 + 0.5 * (i / max(1, len(freqs) - 1))  # sweeps L -> R
        left[start : start + note_len] += sig * math.cos(pan * math.pi / 2.0)
        right[start : start + note_len] += sig * math.sin(pan * math.pi / 2.0)
    return left, right


def _mix_mono_to_stereo(
    left: np.ndarray, right: np.ndarray, start_sample: int, mono: np.ndarray, pan: float
) -> None:
    """Adds a mono signal into stereo buffers with constant-power pan (0.0=L .. 1.0=R)."""
    if start_sample >= len(left) or len(mono) == 0:
        return
    end_sample = min(len(left), start_sample + len(mono))
    take = end_sample - start_sample
    g_l = math.cos(pan * math.pi / 2.0)
    g_r = math.sin(pan * math.pi / 2.0)
    left[start_sample:end_sample] += mono[:take] * g_l
    right[start_sample:end_sample] += mono[:take] * g_r


def generate_musical_chairs_wav(output_path: Path) -> Dict[str, object]:
    """Generates the stereo WAV file and returns deterministic audio telemetry."""
    total_samples = int(round(DURATION_SECONDS * SAMPLE_RATE))
    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    bar_sec = BEATS_PER_BAR * BEAT_SEC
    eighth_sec = BEAT_SEC / 2.0

    for bar_idx in range(BARS):
        bar_start_sec = bar_idx * bar_sec
        bar_start_sample = int(round(bar_start_sec * SAMPLE_RATE))
        _, bass_hz, chord_hzs = CHORD_PROGRESSION[bar_idx % len(CHORD_PROGRESSION)]

        # 1. Warm harmonic pad across the bar
        pad = _synth_pad_chord(chord_hzs, bar_sec * 1.02, SAMPLE_RATE, amp=0.20)
        _mix_mono_to_stereo(left, right, bar_start_sample, pad, pan=0.45)

        # 2. Bouncing bass on beats 1 and 3 (plus octave pop on beat 4)
        for beat in (0, 2):
            b_start = bar_start_sample + int(round(beat * BEAT_SEC * SAMPLE_RATE))
            bass = _synth_bass(bass_hz, BEAT_SEC * 1.4, SAMPLE_RATE, amp=0.28)
            _mix_mono_to_stereo(left, right, b_start, bass, pan=0.50)
        b4_start = bar_start_sample + int(round(3.5 * BEAT_SEC * SAMPLE_RATE))
        bass_oct = _synth_bass(bass_hz * 2.0, eighth_sec * 0.9, SAMPLE_RATE, amp=0.18)
        _mix_mono_to_stereo(left, right, b4_start, bass_oct, pan=0.52)

        # 3. Gentle rhythmic pulse (kick on 1, 3; woodblock tick on 2, 4)
        for beat in range(BEATS_PER_BAR):
            p_start = bar_start_sample + int(round(beat * BEAT_SEC * SAMPLE_RATE))
            tick = _synth_percussion_tick(is_kick=(beat % 2 == 0), sr=SAMPLE_RATE)
            _mix_mono_to_stereo(left, right, p_start, tick, pan=0.50 if beat % 2 == 0 else 0.58)

        # 4. Syncopated pentatonic melody
        phrase = MELODY_PHRASES[bar_idx // 4]
        bar_notes = phrase[bar_idx % 4]
        for step_idx, note_name in enumerate(bar_notes):
            if note_name is None:
                continue
            freq = NOTE_FALLBACK_HZ[note_name]
            n_start = bar_start_sample + int(round(step_idx * eighth_sec * SAMPLE_RATE))
            dur = eighth_sec * (1.45 if (step_idx + 1 < len(bar_notes) and bar_notes[step_idx + 1] is None) else 0.92)
            mel = _synth_rhodes_tone(freq, dur, SAMPLE_RATE, amp=0.34)
            pan = 0.38 + 0.24 * math.sin((bar_idx * 8 + step_idx) * 0.45)
            _mix_mono_to_stereo(left, right, n_start, mel, pan=pan)

    # 5. Distinct rotation-cue chimes at 8.0s, 16.0s, and finale at 22.4s
    cue_specs = [
        (7.8, (PENTATONIC_HZ["C5"], PENTATONIC_HZ["E5"], PENTATONIC_HZ["G5"], PENTATONIC_HZ["C6"])),
        (15.8, (PENTATONIC_HZ["D5"], PENTATONIC_HZ["G5"], PENTATONIC_HZ["A5"], PENTATONIC_HZ["C6"])),
        (22.4, (PENTATONIC_HZ["C5"], PENTATONIC_HZ["E5"], PENTATONIC_HZ["G5"], PENTATONIC_HZ["A5"], PENTATONIC_HZ["C6"])),
    ]
    for cue_sec, cue_freqs in cue_specs:
        c_l, c_r = _synth_cue_chime(cue_freqs, SAMPLE_RATE, amp=0.22)
        c_start = int(round(cue_sec * SAMPLE_RATE))
        c_end = min(total_samples, c_start + len(c_l))
        take = c_end - c_start
        if take > 0:
            left[c_start:c_end] += c_l[:take]
            right[c_start:c_end] += c_r[:take]

    # Smooth fade-in (40ms) and fade-out (350ms) to avoid clicks
    fade_in = int(0.04 * SAMPLE_RATE)
    fade_out = int(0.35 * SAMPLE_RATE)
    left[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    right[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    left[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    right[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)

    # Normalize safely to 0.78 peak
    peak_raw = float(max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-12))
    scale = 0.78 / peak_raw
    left_norm = np.clip(left * scale, -1.0, 1.0)
    right_norm = np.clip(right * scale, -1.0, 1.0)

    interleaved = np.empty(total_samples * CHANNELS, dtype=np.int16)
    interleaved[0::2] = np.round(left_norm * 32767.0).astype(np.int16)
    interleaved[1::2] = np.round(right_norm * 32767.0).astype(np.int16)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH_BYTES)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())

    return inspect_wav(output_path)


def inspect_wav(wav_path: Path) -> Dict[str, object]:
    """Deterministically inspects a WAV file via wave + struct/numpy + sha256."""
    raw_bytes = wav_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        frames = wf.readframes(nframes)

    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM (sampwidth=2), got {sampwidth}")
    sample_count = len(frames) // 2
    samples = np.array(struct.unpack(f"<{sample_count}h", frames), dtype=np.float64) / 32768.0
    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))
    duration = float(nframes / framerate)

    return {
        "wav_path": str(wav_path),
        "wav_sha256": sha256,
        "wav_bytes": len(raw_bytes),
        "channels": channels,
        "sampwidth_bytes": sampwidth,
        "sample_rate": framerate,
        "nframes": nframes,
        "duration_seconds": round(duration, 6),
        "rms": round(rms, 6),
        "peak": round(peak, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and verify Musical Math Chairs WAV theme.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/media/cowboy/research/zoe-monorepo/evidence/musical_math_chairs/musical_chairs_theme.wav"),
        help="Output WAV path",
    )
    parser.add_argument("--verify-only", action="store_true", help="Verify existing WAV without regenerating")
    args = parser.parse_args()

    stats = inspect_wav(args.output) if args.verify_only else generate_musical_chairs_wav(args.output)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

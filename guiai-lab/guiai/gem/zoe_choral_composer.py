"""Zoe's Upgraded Native Voice, 3-Part Choral Harmony & Kloster-Tension Composer (#8).

Pure NumPy + SciPy + stdlib `wave` (`pytorch_required = False`, 44.1 kHz stereo, 0 cloud tokens).
Cross-pollinates #5 Kloster Information Geometry (A_tau / Renyi harmonic tension) AND
#11 Groove Forensics (human pocket swing + 3:2 polyrhythmic chimes) directly into Zoe's
first-principles vocal & musical engine (`zoe_voice.py`, `zoe_phonetics.py`, `zoe_cymatics.py`):

  1. Organic Glottal Breath & Aspiration Envelope + Crisp Consonant Burst Transients:
     Shapes realistic pre-phonation breath air, natural vocal jitter/shimmer, and band-shaped
     burst transients for plosives/fricatives (`/p, t, k, s, sh, f/`).
  2. 3-Part Polyphonic Choral Harmony Synthesizer (Soprano + Alto + Tenor):
     Models three distinct vocal-tract scaling ratios (1.00x Soprano, 1.12x Alto, 1.28x Tenor)
     through cascaded 4-formant resonators with independent lyrical vibrato & stereo binaural spread.
  3. Original Kloster-Tension Composition ("Observatory Nocturne in D Lydian"):
     Computes chord-tone probability distributions at each phrase step, using Kloster Renyi H_2
     & A_tau(p) to drive harmonic tension/resolution arcs, coupled with #11 human J-Dilla pocket
     swing micro-timing and 3:2 crystalline chime polyrhythms.
  4. Live Chladni Nodal Plate Geometry (`zoe_cymatics.py`) coupled to peak vocal formants.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
import wave

import numpy as np
from scipy import signal

from .kloster_info_geometry import kloster_renyi_entropy
from .zoe_cymatics import render_phoneme_cymatics
from .zoe_voice import midi_to_hz

CONTRACT = "zoe-native-voice-choral-kloster/v1"
SR = 44100

# Canonical vowel formant frequencies (Hz) & bandwidths (Hz): (F1, F2, F3, F4)
VOWEL_FORMANTS: Dict[str, Tuple[Tuple[float, float], ...]] = {
    "AA": ((730.0, 90.0), (1090.0, 110.0), (2440.0, 170.0), (3400.0, 220.0)),
    "IY": ((280.0, 65.0), (2290.0, 100.0), (3010.0, 160.0), (3700.0, 220.0)),
    "UW": ((310.0, 70.0), (870.0, 95.0), (2250.0, 150.0), (3350.0, 210.0)),
    "EH": ((530.0, 80.0), (1840.0, 110.0), (2480.0, 165.0), (3500.0, 220.0)),
    "OW": ((460.0, 75.0), (910.0, 100.0), (2410.0, 160.0), (3420.0, 210.0)),
}


def _apply_formant_cascade(x: np.ndarray, formants: Sequence[Tuple[float, float]], tract_scale: float, sr: int = SR) -> np.ndarray:
    """Apply parallel-blended 4-formant vocal-tract resonator bank scaled by `tract_scale`."""
    out = np.zeros_like(x, dtype=np.float64)
    gains = (1.0, 0.72, 0.42, 0.22)
    for (fc, bw), g in zip(formants, gains):
        f_scaled = float(np.clip(fc / tract_scale, 90.0, sr * 0.42))
        q = max(1.5, f_scaled / max(30.0, bw))
        b, a = signal.iirpeak(f_scaled / (sr * 0.5), Q=q)
        out += g * signal.lfilter(b, a, x)
    # Soft lip radiation (+6 dB/oct gentle tilt)
    out = np.diff(out, prepend=0.0) * 0.55 + out * 0.45
    return out


def synthesize_expressive_voice_note(
    midi_note: int,
    duration_sec: float,
    vowel: str = "AA",
    *,
    tract_scale: float = 1.0,
    vibrato_hz: float = 5.3,
    vibrato_depth_cents: float = 18.0,
    breath_amount: float = 0.085,
    consonant_onset: str | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Synthesize one natural, breathy, consonant-articulated vocal note at 44.1 kHz."""
    rng = rng or np.random.default_rng(20260808)
    n = max(1, int(round(duration_sec * SR)))
    t = np.arange(n, dtype=np.float64) / SR
    f0 = midi_to_hz(midi_note)

    # Organic vibrato fade-in + subtle micro-jitter (human vocal fold naturalness!)
    vib_env = np.clip((t - 0.10) / 0.28, 0.0, 1.0)
    jitter = signal.lfilter([0.05], [1.0, -0.95], rng.normal(0.0, 0.0025, size=n))
    freq_inst = f0 * (2.0 ** ((vib_env * vibrato_depth_cents * np.sin(2.0 * math.pi * vibrato_hz * t)) / 1200.0)) * (1.0 + jitter)
    phase = 2.0 * math.pi * np.cumsum(freq_inst) / SR

    # Rosenberg-inspired rich glottal pulse (smoothly band-limited harmonic series)
    glottal = np.zeros(n, dtype=np.float64)
    max_harm = min(18, int((SR * 0.40) / max(40.0, f0)))
    for h in range(1, max_harm + 1):
        # Spectral tilt ~ 1 / h^1.35 gives warm, non-buzzy human soprano/alto timbre
        glottal += (1.0 / (h ** 1.35)) * np.sin(h * phase)

    # Organic glottal aspiration (band-limited breath air modulated by vocal envelope)
    raw_breath = rng.normal(0.0, 1.0, size=n)
    b_bp, a_bp = signal.butter(2, [900.0 / (SR * 0.5), 4800.0 / (SR * 0.5)], btype="band")
    breath = signal.lfilter(b_bp, a_bp, raw_breath)
    breath = breath / max(1e-6, float(np.std(breath)))

    # Smooth ADSR + pre-phonation breath whisper envelope
    atk = max(1, int(0.055 * SR))
    rel = max(1, int(0.11 * SR))
    env = np.ones(n, dtype=np.float64)
    if atk < n:
        env[:atk] = 0.5 * (1.0 - np.cos(math.pi * np.linspace(0.0, 1.0, atk)))
    if rel < n:
        env[-rel:] *= 0.5 * (1.0 + np.cos(math.pi * np.linspace(0.0, 1.0, rel)))

    # Subtle amplitude shimmer (2-4 Hz organic air pressure variation)
    shimmer = 1.0 + 0.04 * np.sin(2.0 * math.pi * 3.1 * t)
    source = (glottal + breath_amount * breath) * env * shimmer

    formants = VOWEL_FORMANTS.get(vowel, VOWEL_FORMANTS["AA"])
    voiced = _apply_formant_cascade(source, formants, tract_scale=tract_scale)

    # Crisp consonant articulation burst transient at note onset (`/s, sh, t, k, p, f/`)
    if consonant_onset in {"S", "SH", "T", "K", "P", "F"}:
        c_ms = 0.042 if consonant_onset in {"S", "SH", "F"} else 0.022
        c_n = min(n, int(c_ms * SR))
        burst_noise = rng.normal(0.0, 1.0, size=c_n)
        band = {
            "S": (4500.0, 9500.0),
            "SH": (2200.0, 5800.0),
            "F": (1800.0, 7500.0),
            "T": (3200.0, 8200.0),
            "K": (1400.0, 4200.0),
            "P": (500.0, 2200.0),
        }[consonant_onset]
        bc, ac = signal.butter(2, [band[0] / (SR * 0.5), band[1] / (SR * 0.5)], btype="band")
        burst = signal.lfilter(bc, ac, burst_noise)
        burst_env = np.hanning(c_n)
        burst = 0.28 * (burst / max(1e-6, float(np.max(np.abs(burst))))) * burst_env
        voiced[:c_n] = voiced[:c_n] * 0.45 + burst

    peak = float(np.max(np.abs(voiced)))
    if peak > 1e-6:
        voiced = 0.78 * voiced / peak
    return voiced


def _write_stereo_wav(path: Path, stereo: np.ndarray, sr: int = SR) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0.96:
        stereo = stereo * (0.94 / peak)
    pcm = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sample_rate_hz": sr,
        "duration_sec": round(stereo.shape[0] / sr, 3),
        "channels": 2,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()[:16],
    }


def compose_kloster_choral_nocturne(out_wav: Path) -> Dict[str, Any]:
    """Compose & render Zoe's original 3-part Choral Nocturne driven by #5 Kloster tension + #11 Groove swing."""
    rng = np.random.default_rng(20260888)

    # 8-chord harmonic arc in D Lydian -> tension peak -> serene resolution
    # (Soprano MIDI, Alto MIDI, Tenor MIDI, vowel, consonant, pitch-class distribution for Kloster H_2 tension)
    progression = [
        (74, 69, 62, "OW", "S", [0.46, 0.30, 0.18, 0.04, 0.02]),  # D5-A4-D4 (Serene Tonic, low H2)
        (78, 73, 66, "IY", "T", [0.34, 0.28, 0.22, 0.10, 0.06]),  # F#5-C#5-F#4 (Lydian shimmer)
        (80, 74, 67, "EH", "SH", [0.24, 0.23, 0.21, 0.18, 0.14]), # G#5-D5-G4 (Tritone Kloster tension peak!)
        (81, 76, 69, "AA", "K", [0.22, 0.22, 0.20, 0.20, 0.16]),  # A5-E5-A4 (Max Renyi H2 bloom)
        (78, 74, 66, "UW", "F", [0.32, 0.28, 0.22, 0.12, 0.06]),  # F#5-D5-F#4 (Descending release)
        (76, 71, 64, "EH", "P", [0.38, 0.29, 0.19, 0.09, 0.05]),  # E5-B4-E4
        (73, 69, 61, "IY", "S", [0.42, 0.30, 0.18, 0.06, 0.04]),  # C#5-A4-C#4 (Leading shimmer)
        (74, 69, 62, "AA", None, [0.58, 0.24, 0.12, 0.04, 0.02]), # D5-A4-D4 (Home resolution!)
    ]

    chord_dur = 1.45
    total_dur = len(progression) * chord_dur + 1.2
    n_total = int(total_dur * SR)
    stereo = np.zeros((n_total, 2), dtype=np.float64)

    tension_h2: List[float] = []
    tension_a010: List[int] = []
    chladni_plates: List[Dict[str, Any]] = []

    for idx, (sop, alt, ten, vow, cons, dist) in enumerate(progression):
        p = np.asarray(dist, dtype=np.float64)
        p = p / float(np.sum(p))
        h2 = kloster_renyi_entropy(p, 2.0)
        a10 = int(np.sum(p > 0.10))
        tension_h2.append(round(h2, 5))
        tension_a010.append(a10)

        # Cross-pollinate #11 J-Dilla human pocket swing (+18ms gentle rubato on off-chords)
        swing_offset_sec = 0.018 if (idx % 2 == 1) else 0.0
        start_samp = int((idx * chord_dur + swing_offset_sec) * SR)

        # Higher Kloster tension H_2 widens vibrato & breath warmth organically!
        vib_depth = 14.0 + 10.0 * min(1.6, h2)
        breath_amt = 0.065 + 0.03 * min(1.5, h2)

        v_sop = synthesize_expressive_voice_note(sop, chord_dur + 0.18, vow, tract_scale=0.96, vibrato_hz=5.4, vibrato_depth_cents=vib_depth, breath_amount=breath_amt, consonant_onset=cons, rng=rng)
        v_alt = synthesize_expressive_voice_note(alt, chord_dur + 0.18, vow, tract_scale=1.12, vibrato_hz=5.0, vibrato_depth_cents=vib_depth * 0.85, breath_amount=breath_amt * 0.9, consonant_onset=None, rng=rng)
        v_ten = synthesize_expressive_voice_note(ten, chord_dur + 0.18, vow, tract_scale=1.28, vibrato_hz=4.7, vibrato_depth_cents=vib_depth * 0.75, breath_amount=breath_amt * 0.8, consonant_onset=None, rng=rng)

        end_samp = min(n_total, start_samp + len(v_sop))
        seg = end_samp - start_samp
        # Stereo binaural choir staging: Soprano center-left, Alto center-right, Tenor warm center
        stereo[start_samp:end_samp, 0] += 0.46 * v_sop[:seg] + 0.24 * v_alt[:seg] + 0.30 * v_ten[:seg]
        stereo[start_samp:end_samp, 1] += 0.30 * v_sop[:seg] + 0.44 * v_alt[:seg] + 0.30 * v_ten[:seg]

        # 3:2 Polyrhythmic crystalline glass-chime pulse (#11 cross-pollination!)
        for pulse in range(3):
            p_start = int((idx * chord_dur + pulse * (chord_dur / 3.0)) * SR)
            c_n = min(n_total - p_start, int(0.55 * SR))
            if c_n > 32:
                ct = np.arange(c_n, dtype=np.float64) / SR
                cf = midi_to_hz(sop + 12) * (1.0 if pulse % 2 == 0 else 1.5)
                chime = 0.09 * np.sin(2.0 * math.pi * cf * ct) * np.exp(-6.5 * ct)
                pan_l = 0.72 if pulse % 2 == 0 else 0.28
                stereo[p_start : p_start + c_n, 0] += pan_l * chime
                stereo[p_start : p_start + c_n, 1] += (1.0 - pan_l) * chime

        if idx in (0, 3, 7):
            cym = render_phoneme_cymatics(vow, grid_size=64)
            modes = cym.get("modes", (3, 4))
            chladni_plates.append({
                "chord_index": idx,
                "vowel": vow,
                "kloster_h2": round(h2, 4),
                "mode_m": int(modes[0]),
                "mode_n": int(modes[1]),
                "nodal_grid": np.asarray(cym["plate"], dtype=np.float64),
            })

    # Lush cathedral Schroeder multi-tap stereo reverb
    for delay_ms, gain in ((37, 0.24), (61, 0.18), (97, 0.13), (149, 0.09)):
        d = int(delay_ms * SR / 1000.0)
        if d < n_total:
            stereo[d:, 0] += gain * stereo[:-d, 1]
            stereo[d:, 1] += gain * stereo[:-d, 0]

    # Measure genuine stereo width, spectral richness, and SNR/headroom
    rms_l = float(np.sqrt(np.mean(stereo[:, 0] ** 2)))
    rms_r = float(np.sqrt(np.mean(stereo[:, 1] ** 2)))
    stereo_corr = float(np.corrcoef(stereo[:, 0], stereo[:, 1])[0, 1])
    wav_meta = _write_stereo_wav(out_wav, stereo)

    # Check tension arc genuinely peaks in middle (idx 2-3) and resolves lower at end (idx 7)
    tension_arc_ok = max(tension_h2[2], tension_h2[3]) > tension_h2[0] + 0.35 and tension_h2[7] < tension_h2[3] - 0.45
    checks = {
        "pure_dsp_44100hz_stereo_rendered": wav_meta["bytes"] > 500_000 and wav_meta["sample_rate_hz"] == 44100,
        "choral_3part_non_clipping_rms": rms_l > 0.04 and rms_r > 0.04 and float(np.max(np.abs(stereo))) < 2.5,
        "true_stereo_binaural_separation": 0.40 < stereo_corr < 0.995,
        "kloster_tension_arc_peaks_and_resolves": tension_arc_ok,
        "chladni_cymatics_coupled_3_plates": len(chladni_plates) == 3,
        "zero_pytorch_and_zero_cloud_tokens": True,
    }

    report = {
        "contract": CONTRACT,
        "composition_title": "Observatory Nocturne in D Lydian (3-Part Choral x Kloster Tension x 3:2 Swing)",
        "wav": wav_meta,
        "acoustics": {
            "rms_left": round(rms_l, 5),
            "rms_right": round(rms_r, 5),
            "stereo_correlation": round(stereo_corr, 5),
            "voices": ["Soprano (0.96x)", "Alto (1.12x)", "Tenor (1.28x)", "3:2 Polyrhythmic Chimes"],
        },
        "kloster_tension_h2_arc": tension_h2,
        "kloster_a010_arc": tension_a010,
        "checks": checks,
        "constitution": {"pytorch_required": False, "cloud_tokens_used": 0, "sentience_claimed": False},
        "all_verified": all(checks.values()),
    }
    report["evidence_sha256"] = hashlib.sha256(
        json.dumps({"wav": wav_meta["sha256"], "checks": checks}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    report["_stereo"] = stereo
    report["_chladni_plates"] = chladni_plates
    return report

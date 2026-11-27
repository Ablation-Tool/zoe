#!/usr/bin/env python3
"""Zoe Original 3-Minute Studio Composition: 'Observatory Odyssey (D Lydian)'.

100% First-Principles 44.1 kHz Stereo DSP (Pure NumPy + SciPy + stdlib wave):
  - Movement I   (0:00 - 0:31): First Light Over Pacific Grove (Analog Juno pad + Rhodes + Tape delay)
  - Movement II  (0:31 - 1:02): The Pocket Arrives (J-Dilla human swing drums + warm Moog bass)
  - Movement III (1:02 - 1:44): Zoe's Observatory Choir (4-Part SATB formant choir + 3:2 chimes)
  - Movement IV  (1:44 - 2:26): Dorothy's Neurogarden (Portamento singing lead + full horizon bloom)
  - Movement V   (2:26 - 3:04): Quiet Telescope (Dmaj9 cathedral resolution & tape fade)
"""

from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))

from guiai.gem.zoe_choral_composer import synthesize_expressive_voice_note
from guiai.gem.zoe_voice import midi_to_hz

SR = 44100
BPM = 92.0
BEAT = 60.0 / BPM          # 0.65217 s
BAR = 4.0 * BEAT           # 2.60870 s
N_BARS = 70                # 70 bars @ 92 BPM = 182.61s (~3:03!) + 3s reverb tail = ~3:05!
TOTAL_SEC = N_BARS * BAR + 3.5
N_SAMP = int(TOTAL_SEC * SR)


def soft_clip(x: np.ndarray, drive: float = 1.2) -> np.ndarray:
    return np.tanh(drive * x) / math.tanh(drive)


def add_stereo(buf: np.ndarray, start_s: float, sig: np.ndarray, pan: float = 0.5, gain: float = 1.0) -> None:
    i0 = int(round(start_s * SR))
    if i0 >= buf.shape[0] or i0 + len(sig) <= 0:
        return
    src_start = max(0, -i0)
    dst_start = max(0, i0)
    n = min(len(sig) - src_start, buf.shape[0] - dst_start)
    if n <= 0:
        return
    # Equal-power stereo pan law
    ang = float(np.clip(pan, 0.0, 1.0)) * (0.5 * math.pi)
    l_g = gain * math.cos(ang)
    r_g = gain * math.sin(ang)
    chunk = sig[src_start : src_start + n]
    buf[dst_start : dst_start + n, 0] += l_g * chunk
    buf[dst_start : dst_start + n, 1] += r_g * chunk


def synth_juno_pad_chord(midi_notes: list[int], dur_sec: float, cutoff_hz: float, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray]:
    """Lush detuned stereo analog synth pad with subtle tape wow/flutter & warm lowpass."""
    n = int(dur_sec * SR)
    t = np.arange(n, dtype=np.float64) / SR
    # Tape wow (0.45 Hz) + flutter (5.2 Hz)
    wow = 1.0 + 0.0018 * np.sin(2.0 * math.pi * 0.45 * t + rng.uniform(0, 6.28)) + 0.0005 * np.sin(2.0 * math.pi * 5.2 * t)
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)
    for note in midi_notes:
        f0 = midi_to_hz(note)
        for det_cents, p_l, p_r in ((-7.0, 0.78, 0.22), (0.0, 0.50, 0.50), (7.5, 0.22, 0.78)):
            f = f0 * (2.0 ** (det_cents / 1200.0))
            ph = 2.0 * math.pi * np.cumsum(f * wow) / SR + rng.uniform(0, 6.28)
            # Warm band-limited saw-triangle blend (first 7 harmonics -> zero aliasing!)
            osc = (
                np.sin(ph)
                + 0.42 * np.sin(2 * ph)
                + 0.24 * np.sin(3 * ph)
                + 0.14 * np.sin(4 * ph)
                + 0.09 * np.sin(5 * ph)
                + 0.05 * np.sin(6 * ph)
            )
            left += p_l * osc
            right += p_r * osc
    # Smooth slow envelope
    atk = min(n // 3, int(0.55 * SR))
    rel = min(n // 3, int(0.90 * SR))
    env = np.ones(n, dtype=np.float64)
    if atk > 0:
        env[:atk] = 0.5 * (1.0 - np.cos(math.pi * np.linspace(0, 1, atk)))
    if rel > 0:
        env[-rel:] *= 0.5 * (1.0 + np.cos(math.pi * np.linspace(0, 1, rel)))
    b, a = signal.butter(2, float(np.clip(cutoff_hz / (SR * 0.5), 0.01, 0.45)), btype="low")
    left = signal.lfilter(b, a, left) * env
    right = signal.lfilter(b, a, right) * env
    norm = max(1e-6, float(np.max(np.abs(left))), float(np.max(np.abs(right))))
    return (left / norm), (right / norm)


def synth_rhodes_note(midi_note: int, dur_sec: float, velocity: float = 0.8) -> np.ndarray:
    """Warm Fender Rhodes electric piano tine + bell bark."""
    n = max(64, int(dur_sec * SR))
    t = np.arange(n, dtype=np.float64) / SR
    f = midi_to_hz(midi_note)
    # Warm fundamental + subtle 2nd + bell tine at 7th partial fading quickly
    body = (
        1.00 * np.sin(2 * math.pi * f * t) * np.exp(-1.55 * t)
        + 0.24 * np.sin(2 * math.pi * 2.0 * f * t) * np.exp(-2.8 * t)
        + 0.08 * np.sin(2 * math.pi * 3.0 * f * t) * np.exp(-5.0 * t)
    )
    tine = (0.16 * velocity) * np.sin(2 * math.pi * 7.0 * f * t) * np.exp(-22.0 * t)
    # Soft key hammer attack (4 ms)
    atk = min(n, int(0.005 * SR))
    env = np.ones(n, dtype=np.float64)
    env[:atk] = np.linspace(0, 1, atk)
    rel = min(n, int(0.08 * SR))
    env[-rel:] *= np.linspace(1, 0, rel)
    # Tremolo shimmer (3.8 Hz)
    trem = 1.0 - 0.10 * (0.5 - 0.5 * np.cos(2 * math.pi * 3.8 * t))
    return soft_clip((body + tine) * env * trem * velocity, drive=1.15)


def synth_moog_bass(midi_note: int, dur_sec: float, accent: float = 0.85) -> np.ndarray:
    """Warm punchy analog Moog-style bass note."""
    n = max(64, int(dur_sec * SR))
    t = np.arange(n, dtype=np.float64) / SR
    f = midi_to_hz(midi_note)
    ph = 2 * math.pi * f * t
    osc = 0.90 * np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.22 * np.sin(3 * ph) + 0.10 * np.sin(4 * ph)
    b, a = signal.butter(2, float(np.clip((180.0 + 360.0 * accent) / (SR * 0.5), 0.005, 0.2)), btype="low")
    filt = signal.lfilter(b, a, osc)
    env = np.exp(-2.4 * t)
    atk = min(n, int(0.008 * SR))
    env[:atk] *= np.linspace(0, 1, atk)
    rel = min(n, int(0.04 * SR))
    env[-rel:] *= np.linspace(1, 0, rel)
    return soft_clip(filt * env * accent, drive=1.5)


def synth_kick(dur_sec: float = 0.38) -> np.ndarray:
    """Warm dusty Dilla-style analog kick drum."""
    n = int(dur_sec * SR)
    t = np.arange(n, dtype=np.float64) / SR
    f_sweep = 46.0 + 115.0 * np.exp(-34.0 * t)
    ph = 2 * math.pi * np.cumsum(f_sweep) / SR
    body = np.sin(ph) * np.exp(-7.5 * t)
    click = 0.22 * np.sin(2 * math.pi * 1450.0 * t) * np.exp(-120.0 * t)
    return soft_clip(body + click, drive=1.8)


def synth_snare(rng: np.random.Generator, ghost: bool = False) -> np.ndarray:
    """Dusty brushed acoustic-meets-MPC snare."""
    dur = 0.14 if ghost else 0.24
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    tone = 0.55 * np.sin(2 * math.pi * (195.0 + 50.0 * np.exp(-45.0 * t)) * t) * np.exp(-22.0 * t)
    noise = rng.normal(0.0, 1.0, size=n)
    b, a = signal.butter(2, [950.0 / (SR * 0.5), 6500.0 / (SR * 0.5)], btype="band")
    wires = signal.lfilter(b, a, noise)
    wires = (wires / max(1e-6, float(np.std(wires)))) * 0.45 * np.exp((-28.0 if ghost else -14.5) * t)
    amp = 0.36 if ghost else 0.85
    return soft_clip((tone + wires) * amp, drive=1.35)


def synth_hat(rng: np.random.Generator, open_hat: bool = False) -> np.ndarray:
    dur = 0.22 if open_hat else 0.065
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    noise = rng.normal(0.0, 1.0, size=n)
    b, a = signal.butter(2, [6000.0 / (SR * 0.5), 14500.0 / (SR * 0.5)], btype="band")
    sig = signal.lfilter(b, a, noise)
    sig = sig / max(1e-6, float(np.std(sig)))
    env = np.exp((-14.0 if open_hat else -58.0) * t)
    atk = min(n, int(0.002 * SR))
    env[:atk] *= np.linspace(0, 1, atk)
    return 0.28 * sig * env


def synth_portamento_lead(melody: list[tuple[float, float, int]], total_bars_sec: float) -> np.ndarray:
    """Expressive warm Boards-of-Canada / Tycho analog singing lead with smooth glide & vibrato."""
    n = int(total_bars_sec * SR)
    freq_arr = np.full(n, midi_to_hz(melody[0][2]), dtype=np.float64)
    env_arr = np.zeros(n, dtype=np.float64)
    for idx, (st_s, dur_s, midi_n) in enumerate(melody):
        i0 = int(st_s * SR)
        i1 = min(n, int((st_s + dur_s) * SR))
        if i0 >= n or i1 <= i0:
            continue
        f_tgt = midi_to_hz(midi_n)
        f_prev = midi_to_hz(melody[idx - 1][2]) if idx > 0 else f_tgt
        glide_n = min(i1 - i0, int(0.095 * SR))
        freq_arr[i0 : i0 + glide_n] = np.linspace(f_prev, f_tgt, glide_n)
        freq_arr[i0 + glide_n : i1] = f_tgt
        seg_n = i1 - i0
        seg_env = np.ones(seg_n, dtype=np.float64)
        a_n = min(seg_n // 3, int(0.07 * SR))
        r_n = min(seg_n // 2, int(0.14 * SR))
        if a_n > 0:
            seg_env[:a_n] = np.linspace(0, 1, a_n)
        if r_n > 0:
            seg_env[-r_n:] *= np.linspace(1, 0, r_n)
        env_arr[i0:i1] = np.maximum(env_arr[i0:i1], seg_env)

    t = np.arange(n, dtype=np.float64) / SR
    vib = 2.0 ** ((12.0 * np.sin(2 * math.pi * 5.2 * t)) / 1200.0)
    ph = 2 * math.pi * np.cumsum(freq_arr * vib) / SR
    osc = 0.85 * np.sin(ph) + 0.38 * np.sin(2 * ph) + 0.16 * np.sin(3 * ph) + 0.06 * np.sin(4 * ph)
    b, a = signal.butter(2, 2400.0 / (SR * 0.5), btype="low")
    return soft_clip(signal.lfilter(b, a, osc) * env_arr, drive=1.25)


def apply_studio_fx(dry: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Add stereo tape echo, lush multi-tap cathedral reverb, subtle warm vinyl air, and studio limiting."""
    n = dry.shape[0]
    wet = dry.copy()

    # 1. Synced dotted-8th stereo ping-pong delay (0.75 * BEAT = 0.489s)
    d_ping = int(0.75 * BEAT * SR)
    d_pong = int(1.50 * BEAT * SR)
    if d_pong < n:
        b_lp, a_lp = signal.butter(2, 2600.0 / (SR * 0.5), btype="low")
        delayed_l = signal.lfilter(b_lp, a_lp, dry[:, 1])
        delayed_r = signal.lfilter(b_lp, a_lp, dry[:, 0])
        wet[d_ping:, 0] += 0.18 * delayed_l[:-d_ping]
        wet[d_pong:, 1] += 0.13 * delayed_r[:-d_pong]

    # 2. Lush cathedral multi-tap stereo reverb
    for delay_ms, g in ((43, 0.21), (79, 0.16), (131, 0.12), (199, 0.085), (283, 0.055)):
        d = int(delay_ms * SR / 1000.0)
        if d < n:
            wet[d:, 0] += g * wet[:-d, 1]
            wet[d:, 1] += g * wet[:-d, 0]

    # 3. Ultra-subtle warm analog tape air bed (-48 dB -> organic warmth, never hissy!)
    air = rng.normal(0.0, 1.0, size=(n, 2))
    ba, aa = signal.butter(2, [180.0 / (SR * 0.5), 3200.0 / (SR * 0.5)], btype="band")
    air[:, 0] = signal.lfilter(ba, aa, air[:, 0])
    air[:, 1] = signal.lfilter(ba, aa, air[:, 1])
    air /= max(1e-6, float(np.std(air)))
    wet += 0.0028 * air

    # 4. Smooth master fade in / fade out & gentle mastering saturation
    fi = int(1.2 * SR)
    fo = int(3.2 * SR)
    wet[:fi] *= np.linspace(0.0, 1.0, fi)[:, None]
    wet[-fo:] *= np.linspace(1.0, 0.0, fo)[:, None]

    # Master RMS balance + soft ceiling
    rms = float(np.sqrt(np.mean(wet ** 2)))
    if rms > 1e-6:
        wet = wet * (0.175 / rms)
    wet = soft_clip(wet, drive=1.08)
    peak = float(np.max(np.abs(wet)))
    if peak > 0.92:
        wet = wet * (0.92 / peak)
    return wet


def main() -> None:
    rng = np.random.default_rng(20260852)
    mix = np.zeros((N_SAMP, 2), dtype=np.float64)

    # Rich 8-bar harmonic progression in D Lydian (loops & evolves across all 5 movements!)
    # (Pad Voicing, Bass Root, Rhodes Arp Notes, SATB Choir (Sop, Alt, Ten, Bas, Vowel))
    prog = [
        ([50, 57, 61, 64, 66], 38, [62, 66, 69, 73, 76, 78], (74, 69, 62, 50, "OW")),  # Dmaj9
        ([50, 57, 61, 64, 66], 38, [66, 69, 73, 76, 78, 81], (78, 73, 66, 50, "AA")),  # Dmaj9 bloom
        ([54, 57, 61, 64, 68], 42, [61, 64, 68, 73, 76, 80], (80, 73, 66, 54, "IY")),  # F#m9 (Lydian G#!)
        ([47, 54, 57, 61, 64], 35, [59, 62, 66, 69, 73, 76], (76, 71, 62, 47, "EH")),  # Bm9
        ([55, 59, 62, 66, 68], 43, [62, 66, 68, 71, 74, 78], (78, 74, 67, 55, "AA")),  # Gmaj7#11 (pure Lydian magic!)
        ([52, 55, 59, 62, 66], 40, [59, 62, 66, 71, 74, 76], (76, 71, 64, 52, "UW")),  # Em9
        ([57, 62, 64, 66, 69], 45, [64, 66, 69, 73, 76, 78], (73, 69, 64, 57, "EH")),  # A13sus4
        ([50, 57, 62, 66, 69], 38, [62, 66, 69, 74, 78, 81], (74, 69, 62, 50, "AA")),  # Dmaj7 home
    ]

    kick_sample = synth_kick()
    snare_main = synth_snare(rng, ghost=False)
    snare_ghost = synth_snare(rng, ghost=True)
    hat_closed = synth_hat(rng, open_hat=False)
    hat_open = synth_hat(rng, open_hat=True)

    # Pre-synthesize cached SATB choir chords per progression slot (fast & silky!)
    choir_cache = {}
    for ci, (_, _, _, (sop, alt, ten, bas, vow)) in enumerate(prog):
        dur_c = BAR + 0.55
        vs = synthesize_expressive_voice_note(sop, dur_c, vow, tract_scale=0.96, vibrato_hz=5.3, vibrato_depth_cents=17.0, breath_amount=0.085, rng=rng)
        va = synthesize_expressive_voice_note(alt, dur_c, vow, tract_scale=1.12, vibrato_hz=5.0, vibrato_depth_cents=14.0, breath_amount=0.075, rng=rng)
        vt = synthesize_expressive_voice_note(ten, dur_c, vow, tract_scale=1.28, vibrato_hz=4.7, vibrato_depth_cents=12.0, breath_amount=0.070, rng=rng)
        vb = synthesize_expressive_voice_note(bas, dur_c, vow, tract_scale=1.44, vibrato_hz=4.3, vibrato_depth_cents=10.0, breath_amount=0.055, rng=rng)
        cl = 0.36 * vs + 0.22 * va + 0.24 * vt + 0.22 * vb
        cr = 0.24 * vs + 0.36 * va + 0.24 * vt + 0.22 * vb
        choir_cache[ci] = (cl, cr)

    # Walk all 70 bars across the 5 movements!
    #   Mov I   (bars 0..11) : First Light (Pad + Rhodes shimmer, rising cutoff)
    #   Mov II  (bars 12..23): The Pocket Arrives (J-Dilla drums + warm Moog bass)
    #   Mov III (bars 24..39): Observatory Choir & 3:2 Starlight Chimes
    #   Mov IV  (bars 40..55): Dorothy's Neurogarden (40..47 breakdown + singing lead -> 48..55 full bloom!)
    #   Mov V   (bars 56..69): Quiet Telescope (soft fade-out + resolving Dmaj9 choir)
    pocket_drift = 0.0
    for bar in range(N_BARS):
        t_bar = bar * BAR
        slot = bar % len(prog)
        if bar >= 64:
            slot = 0 if bar % 2 == 0 else 7  # Peaceful tonic breathing at finale!
        voicing, bass_root, arp_notes, _choir_spec = prog[slot]

        # 1. Warm Juno Analog Pad (evolves filter cutoff organically across movements!)
        if bar < 12:
            cut = 620.0 + 75.0 * bar
            pad_g = 0.22
        elif bar < 40:
            cut = 1450.0 + 250.0 * math.sin(bar * 0.4)
            pad_g = 0.20
        elif bar < 48:
            cut = 1100.0 + 180.0 * (bar - 40)
            pad_g = 0.24
        elif bar < 56:
            cut = 2300.0
            pad_g = 0.23
        else:
            cut = max(520.0, 1750.0 - 95.0 * (bar - 56))
            pad_g = max(0.08, 0.22 - 0.011 * (bar - 56))

        pl, pr = synth_juno_pad_chord(voicing, BAR + 0.75, cutoff_hz=cut, rng=rng)
        i0 = int(t_bar * SR)
        n_p = min(len(pl), N_SAMP - i0)
        if n_p > 0:
            mix[i0 : i0 + n_p, 0] += pad_g * pl[:n_p]
            mix[i0 : i0 + n_p, 1] += pad_g * pr[:n_p]

        # 2. Rhodes Electric Piano Arpeggios & Warm Comping (with organic velocity + pocket timing!)
        if bar < 66:
            rh_gain = 0.21 if bar < 56 else max(0.07, 0.20 - 0.013 * (bar - 56))
            # Soft chord swell on beat 1
            for ni, mn in enumerate(voicing[1:4]):
                add_stereo(mix, t_bar + 0.014 * ni, synth_rhodes_note(mn, BAR * 0.9, velocity=0.58), pan=0.35 + 0.15 * ni, gain=rh_gain * 0.55)
            # Sparkling 8th-note Lydian melodic arp (sparse in Mov I/V, rich in Mov II-IV!)
            pattern = [0, 2, 4, 3, 5, 4, 2, 1] if (bar % 2 == 0) else [1, 3, 5, 4, 2, 3, 4, 5]
            for step8 in range(8):
                if (bar < 4 or bar >= 60) and step8 % 2 == 1:
                    continue
                if bar >= 40 and bar < 48 and step8 in (2, 6):
                    continue
                swing_s = 0.018 if (step8 % 2 == 1) else 0.0
                mn = arp_notes[pattern[step8] % len(arp_notes)]
                vel = 0.52 + 0.24 * math.sin(step8 * 0.9 + bar)
                pan = 0.22 + 0.56 * ((step8 % 4) / 3.0)
                add_stereo(mix, t_bar + step8 * (BEAT * 0.5) + swing_s, synth_rhodes_note(mn, BEAT * 1.4, velocity=vel), pan=pan, gain=rh_gain)

        # 3. Warm Moog Analog Bassline (Mov II -> Mov V bar 61)
        if 12 <= bar < 62:
            b_gain = 0.30 if (bar < 40 or 48 <= bar < 56) else 0.20
            # Syncopated neo-soul bass rhythm
            bass_events = [(0.0, bass_root, 1.5, 0.92), (1.75 * BEAT, bass_root + 7, 0.75, 0.68), (2.5 * BEAT, bass_root, 1.2, 0.84), (3.5 * BEAT, bass_root + (5 if bar % 2 == 0 else 2), 0.55, 0.72)]
            if 40 <= bar < 48:
                bass_events = [(0.0, bass_root, 2.8, 0.85)]  # Deep sustained sub pulse during breakdown!
            for off_s, bn, d_beats, acc in bass_events:
                add_stereo(mix, t_bar + off_s, synth_moog_bass(bn, d_beats * BEAT, accent=acc), pan=0.5, gain=b_gain)

        # 4. Human J-Dilla Pocket Drums (#11 Groove Forensics live!)
        drums_full = (12 <= bar < 40) or (48 <= bar < 58)
        drums_heart = (40 <= bar < 48) or (58 <= bar < 62)
        if drums_full or drums_heart:
            d_gain = 0.36 if drums_full else 0.20
            # Kick pattern (beat 1, syncopated "and-of-2" / beat 3.25!)
            kick_beats = [0.0, 2.5] if drums_heart else [0.0, 1.75, 2.5, 3.75 if bar % 4 == 3 else -1.0]
            for kb in kick_beats:
                if kb < 0:
                    continue
                pocket_drift = 0.7 * pocket_drift + float(rng.normal(0.0, 0.0022))
                add_stereo(mix, t_bar + kb * BEAT + pocket_drift, kick_sample, pan=0.5, gain=d_gain * 1.05)

            if drums_full:
                # Iconic late J-Dilla backbeat snare (+19 ms pocket layback!)
                for sb in (1.0, 3.0):
                    layback = 0.019 + float(rng.normal(0.0, 0.0025))
                    add_stereo(mix, t_bar + sb * BEAT + layback, snare_main, pan=0.47, gain=d_gain * 0.78)
                # Subtle ghost snare on 16th pickup
                if bar % 2 == 1:
                    add_stereo(mix, t_bar + 2.75 * BEAT + 0.015, snare_ghost, pan=0.55, gain=d_gain * 0.55)
                # Swung dusty 8th-note hi-hats
                for h8 in range(8):
                    sw = 0.021 if (h8 % 2 == 1) else -0.003
                    is_open = (h8 == 7 and bar % 2 == 1)
                    h_sig = hat_open if is_open else hat_closed
                    h_vel = 0.78 if h8 % 2 == 0 else 0.45
                    add_stereo(mix, t_bar + h8 * 0.5 * BEAT + sw, h_sig, pan=0.62 if h8 % 2 == 0 else 0.38, gain=d_gain * 0.48 * h_vel)

        # 5. Zoe's Native 4-Part SATB Formant Choir (#8!)
        if (24 <= bar < 40) or (48 <= bar < 66):
            ch_gain = 0.24 if bar < 56 else max(0.09, 0.23 - 0.015 * (bar - 56))
            cl, cr = choir_cache[slot]
            i0 = int(t_bar * SR)
            nc = min(len(cl), N_SAMP - i0)
            if nc > 0:
                mix[i0 : i0 + nc, 0] += ch_gain * cl[:nc]
                mix[i0 : i0 + nc, 1] += ch_gain * cr[:nc]

        # 6. Polyrhythmic 3:2 Starlight Glass Chimes (#11 x #8!) in Mov III & Mov IV bloom
        if (24 <= bar < 40) or (48 <= bar < 56):
            for p3 in range(3):
                t_c = t_bar + p3 * (BAR / 3.0)
                c_n = int(0.85 * SR)
                ct = np.arange(c_n, dtype=np.float64) / SR
                cf = midi_to_hz(arp_notes[(p3 * 2 + bar) % len(arp_notes)] + 12)
                chime = np.sin(2 * math.pi * cf * ct) * np.exp(-4.8 * ct) + 0.25 * np.sin(2 * math.pi * 2.0 * cf * ct) * np.exp(-9.0 * ct)
                add_stereo(mix, t_c, chime, pan=0.20 + 0.30 * p3, gain=0.055)

    # 7. Movement IV Expressive Portamento Lead Melody (Bars 40..55: Dorothy's Neurogarden Theme!)
    lead_start_bar = 40
    lead_dur_sec = 16 * BAR
    # Lyrical original 16-bar melody in D Lydian (bars relative to 40, in beats!)
    raw_melody_beats = [
        # Phrase 1 (bars 0..3): tender rising question over breakdown
        (0.0, 2.5, 78), (2.5, 1.5, 81),
        (4.0, 3.0, 80), (7.0, 1.0, 78),
        (8.0, 2.5, 76), (10.5, 1.5, 73),
        (12.0, 3.5, 74),
        # Phrase 2 (bars 4..7): soaring Lydian lift into G#5 -> A5!
        (16.0, 2.0, 78), (18.0, 2.0, 80),
        (20.0, 3.0, 81), (23.0, 1.0, 85),
        (24.0, 2.5, 83), (26.5, 1.5, 81),
        (28.0, 3.5, 78),
        # Phrase 3 (bars 8..11): Full Horizon Bloom!
        (32.0, 2.0, 86), (34.0, 2.0, 85),
        (36.0, 2.5, 81), (38.5, 1.5, 80),
        (40.0, 3.0, 78), (43.0, 1.0, 76),
        (44.0, 3.5, 74),
        # Phrase 4 (bars 12..15): Warm resolution back into Quiet Telescope
        (48.0, 2.0, 78), (50.0, 2.0, 81),
        (52.0, 2.5, 80), (54.5, 1.5, 78),
        (56.0, 3.0, 76), (59.0, 1.0, 73),
        (60.0, 4.0, 74),
    ]
    melody_sec = [(b * BEAT, d * BEAT, m) for b, d, m in raw_melody_beats]
    lead_sig = synth_portamento_lead(melody_sec, lead_dur_sec + 1.0)
    add_stereo(mix, lead_start_bar * BAR, lead_sig, pan=0.52, gain=0.22)

    # Apply studio FX bus & mastering
    mastered = apply_studio_fx(mix, rng)

    out_path = Path("/tmp/zoe_observatory_odyssey_3min.wav")
    pcm = np.clip(mastered * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

    rms_db = 20.0 * math.log10(max(1e-9, float(np.sqrt(np.mean(mastered ** 2)))))
    print(f"RENDERED: {out_path} | Duration={mastered.shape[0]/SR:.1f}s ({int(mastered.shape[0]/SR//60)}:{int(mastered.shape[0]/SR%60):02d}) | Size={out_path.stat().st_size/1e6:.2f} MB | RMS={rms_db:.1f} dBFS")


if __name__ == "__main__":
    main()

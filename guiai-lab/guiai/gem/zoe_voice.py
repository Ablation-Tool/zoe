"""Zoe's Native Voice, Singing, MIDI Baseline & 3D Binaural Spatial Engine.

Built 100% from first principles (pure NumPy + SciPy + Python stdlib `wave`/`struct`):
  1. Standard MIDI File (SMF Type 0/1) reader & writer + MS-DOS/Atari ST PSG baseline
     synthesizer, establishing the discrete control baseline.
  2. Smooth Rosenberg-Klatt glottal excitation with speaking prosody and lyrical soprano
     singing portamento + 5.3 Hz vibrato.
  3. Stateful 5-formant cascade vocal tract + parallel fricative/plosive/nasal branches
     driven continuously across all 44 English phonemes & 260+ grapheme rules.
  4. Vectorized Woodworth 3D binaural spatializer (ITD + contralateral head-shadow ILD +
     pinna elevation cue + stereo early reflections + Schroeder C-speed IIR reverb).
  5. Built-in public-domain & original songs ("zoe", "daisy" IBM 7094 homage, "vowels")
     plus deterministic GEM Spatial IR & VDI scene `voice_scene()`.

Zero PyTorch, zero external TTS dependencies, zero network calls (CONSTITUTION.md Article X).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Dict, List, Sequence, Tuple
import wave

import numpy as np
from scipy import signal

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT
from .zoe_cymatics import (
    encode_gem_3bitplane_raster,
    render_phoneme_cymatics,
)
from .zoe_phonetics import (
    CONSONANT_PHONEMES,
    GRAPHEME_RULES,
    PHONEME_INVENTORY,
    VOWEL_PHONEMES,
    syllabify_phonemes,
    text_to_phonemes,
)


VOICE_CONTRACT = "zoe-native-voice/v1"
SAMPLE_RATE_DEFAULT = 44100


# ---------------------------------------------------------------------------
# 1. Standard MIDI Baseline (MS-DOS / Atari ST PSG Synthesis + SMF Round-Trip)
# ---------------------------------------------------------------------------

def midi_to_hz(midi_note: int) -> float:
    return 440.0 * (2.0 ** ((float(midi_note) - 69.0) / 12.0))


def _encode_vlq(value: int) -> bytes:
    val = max(0, int(value))
    out = [val & 0x7F]
    val >>= 7
    while val:
        out.append((val & 0x7F) | 0x80)
        val >>= 7
    out.reverse()
    return bytes(out)


def _decode_vlq(buf: bytes, pos: int) -> Tuple[int, int]:
    val = 0
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            return val, pos
    raise ValueError("truncated MIDI variable-length quantity")


def write_standard_midi(
    note_events: Sequence[Dict[str, object]],
    output_path: str | Path,
    *,
    bpm: float = 108.0,
    ppq: int = 480,
) -> Dict[str, object]:
    """Writes a standard Type-0 `.mid` file from [{"start_sec", "duration_sec", "midi_note", ...}]."""
    us_per_quarter = max(1, int(round(60_000_000.0 / float(bpm))))
    sec_per_tick = 60.0 / (float(bpm) * float(ppq))

    raw_msgs: List[Tuple[int, int, bytes]] = [
        (0, 0, b"\xFF\x51\x03" + us_per_quarter.to_bytes(3, "big")),
    ]
    for ev in note_events:
        st_tick = max(0, int(round(float(ev["start_sec"]) / sec_per_tick)))
        dur_tick = max(1, int(round(float(ev["duration_sec"]) / sec_per_tick)))
        note = int(np.clip(int(ev["midi_note"]), 0, 127))
        vel = int(np.clip(int(ev.get("velocity", 96)), 1, 127))
        raw_msgs.append((st_tick, 2, bytes((0x90, note, vel))))
        raw_msgs.append((st_tick + dur_tick, 1, bytes((0x80, note, 0))))

    last_tick = max((t for t, _, _ in raw_msgs), default=0)
    raw_msgs.append((last_tick + 1, 3, b"\xFF\x2F\x00"))
    raw_msgs.sort(key=lambda item: (item[0], item[1]))

    track_bytes = bytearray()
    cur_tick = 0
    for tick, _, payload in raw_msgs:
        track_bytes.extend(_encode_vlq(tick - cur_tick))
        track_bytes.extend(payload)
        cur_tick = tick

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
    track = b"MTrk" + struct.pack(">I", len(track_bytes)) + bytes(track_bytes)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(header + track)
    return {
        "midi_path": str(out),
        "bytes": out.stat().st_size,
        "bpm": float(bpm),
        "ppq": int(ppq),
        "note_count": len(note_events),
    }


def read_standard_midi(midi_path: str | Path) -> List[Dict[str, object]]:
    """Reads a Standard MIDI File (Type 0 or Type 1) back into timed note dictionaries."""
    data = Path(midi_path).expanduser().resolve().read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("not a valid Standard MIDI file (missing MThd)")
    hdr_len, _fmt, n_tracks, division = struct.unpack(">IHHH", data[4:14])
    pos = 8 + hdr_len
    if division & 0x8000:
        raise ValueError("SMPTE time division not supported")
    ppq = max(1, division)

    tempo_changes: List[Tuple[int, int]] = [(0, 500_000)]
    raw_notes: List[Tuple[int, int, int, int]] = []  # (tick, on_off 1/0, note, vel)

    for _ in range(n_tracks):
        if pos + 8 > len(data) or data[pos:pos + 4] != b"MTrk":
            break
        trk_len = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        trk_end = min(len(data), pos + 8 + trk_len)
        cur = pos + 8
        tick = 0
        running_status = 0
        while cur < trk_end:
            delta, cur = _decode_vlq(data, cur)
            tick += delta
            if cur >= trk_end:
                break
            status = data[cur]
            if status < 0x80:
                status = running_status
            else:
                cur += 1
                if status < 0xF0:
                    running_status = status

            if status == 0xFF:
                if cur >= trk_end:
                    break
                meta_type = data[cur]
                cur += 1
                m_len, cur = _decode_vlq(data, cur)
                meta_data = data[cur:cur + m_len]
                cur += m_len
                if meta_type == 0x51 and len(meta_data) == 3:
                    us_q = int.from_bytes(meta_data, "big")
                    tempo_changes.append((tick, max(1, us_q)))
                elif meta_type == 0x2F:
                    break
            elif status in (0xF0, 0xF7):
                s_len, cur = _decode_vlq(data, cur)
                cur += s_len
            else:
                ev_type = status & 0xF0
                if ev_type in (0xC0, 0xD0):
                    cur += 1
                else:
                    if cur + 2 > trk_end:
                        break
                    d1, d2 = data[cur], data[cur + 1]
                    cur += 2
                    if ev_type == 0x90 and d2 > 0:
                        raw_notes.append((tick, 1, d1, d2))
                    elif ev_type == 0x80 or (ev_type == 0x90 and d2 == 0):
                        raw_notes.append((tick, 0, d1, d2))
        pos = trk_end

    tempo_changes.sort(key=lambda t: t[0])

    def _tick_to_sec(target_tick: int) -> float:
        elapsed = 0.0
        prev_t = 0
        cur_us = 500_000
        for ch_t, ch_us in tempo_changes:
            if ch_t >= target_tick:
                break
            if ch_t > prev_t:
                elapsed += (ch_t - prev_t) * (cur_us / 1_000_000.0) / float(ppq)
                prev_t = ch_t
            cur_us = ch_us
        elapsed += (target_tick - prev_t) * (cur_us / 1_000_000.0) / float(ppq)
        return elapsed

    active: Dict[int, List[Tuple[int, int]]] = {}
    out: List[Dict[str, object]] = []
    raw_notes.sort(key=lambda item: (item[0], item[1]))
    for tick, is_on, note, vel in raw_notes:
        if is_on:
            active.setdefault(note, []).append((tick, vel))
        else:
            stack = active.get(note)
            if stack:
                st_tick, st_vel = stack.pop(0)
                st_sec = _tick_to_sec(st_tick)
                end_sec = max(st_sec + 0.02, _tick_to_sec(tick))
                out.append({
                    "start_sec": round(st_sec, 6),
                    "duration_sec": round(end_sec - st_sec, 6),
                    "midi_note": int(note),
                    "velocity": int(st_vel),
                    "hz": round(midi_to_hz(note), 4),
                })
    out.sort(key=lambda e: (float(e["start_sec"]), int(e["midi_note"])))
    return out


def synthesize_dos_midi_baseline(
    note_events: Sequence[Dict[str, object]],
    *,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
) -> np.ndarray:
    """MS-DOS AdLib / Atari ST YM2149 PSG baseline synthesizer (clean discrete notes)."""
    if not note_events:
        return np.zeros(int(0.25 * sample_rate), dtype=np.float64)
    total_sec = max(float(e["start_sec"]) + float(e["duration_sec"]) for e in note_events) + 0.25
    n_samples = int(math.ceil(total_sec * sample_rate))
    buf = np.zeros(n_samples, dtype=np.float64)

    for ev in note_events:
        st = max(0, int(float(ev["start_sec"]) * sample_rate))
        dur = max(0.03, float(ev["duration_sec"]))
        length = min(n_samples - st, int(dur * sample_rate))
        if length <= 16:
            continue
        freq = midi_to_hz(int(ev["midi_note"]))
        vel = float(ev.get("velocity", 96)) / 127.0
        t = np.arange(length, dtype=np.float64) / float(sample_rate)
        # Mildly band-limited YM2149 / PC-speaker PSG square+triangle blend
        phase = 2.0 * math.pi * freq * t
        psg = (
            0.66 * np.sin(phase)
            + 0.22 * np.sin(3.0 * phase)
            + 0.12 * np.sin(5.0 * phase)
        )
        atk = np.minimum(t / 0.008, 1.0)
        rel = np.minimum(np.maximum(dur - t, 0.0) / 0.028, 1.0)
        env = atk * rel * (0.45 + 0.55 * np.exp(-2.8 * t))
        buf[st:st + length] += psg * env * (0.36 * vel)

    peak = max(float(np.max(np.abs(buf))), 1e-6)
    if peak > 0.85:
        buf *= 0.85 / peak
    return buf


# ---------------------------------------------------------------------------
# 2. Glottal Flow Excitation + Stateful 5-Formant Vocal Tract Synthesizer
# ---------------------------------------------------------------------------

def _one_pole_resonator_coeffs(freq_hz: float, bw_hz: float, sample_rate: int) -> Tuple[float, float, float]:
    """Returns unity-DC cascade 2-pole resonator (b0, a1, a2) unconditionally stable."""
    f = float(np.clip(freq_hz, 80.0, 0.44 * sample_rate))
    bw = float(np.clip(bw_hz, 36.0, 3200.0))
    r = math.exp(-math.pi * bw / float(sample_rate))
    r = min(0.997, max(0.05, r))
    theta = 2.0 * math.pi * f / float(sample_rate)
    a1 = -2.0 * r * math.cos(theta)
    a2 = r * r
    b0 = max(1e-5, 1.0 + a1 + a2)
    return b0, a1, a2


def _bandpass_noise_coeffs(center_hz: float, bw_hz: float, sample_rate: int) -> Tuple[np.ndarray, np.ndarray]:
    """2-pole bandpass resonator normalized to unit peak gain for fricative/burst shaping."""
    f = float(np.clip(center_hz, 180.0, 0.44 * sample_rate))
    bw = float(np.clip(bw_hz, 140.0, 5000.0))
    r = min(0.995, max(0.15, math.exp(-math.pi * bw / float(sample_rate))))
    theta = 2.0 * math.pi * f / float(sample_rate)
    a1 = -2.0 * r * math.cos(theta)
    a2 = r * r
    # Unit peak gain around center resonance ~ (1 - r) * (1 + r) * sin(theta)
    gain = max(1e-4, (1.0 - r * r) * abs(math.sin(theta)) * 0.55)
    return np.array([gain, 0.0, -gain], dtype=np.float64), np.array([1.0, a1, a2], dtype=np.float64)


def _rosenberg_glottal_wave(phase: np.ndarray, open_quotient: float = 0.62, speed_ratio: float = 0.72) -> np.ndarray:
    """Evaluates smooth feminine Rosenberg-Klatt glottal flow pulse on phase in [0, 1)."""
    ph = np.mod(phase, 1.0)
    tp = open_quotient * speed_ratio
    g = np.zeros_like(ph, dtype=np.float64)
    open_mask = ph < tp
    close_mask = (ph >= tp) & (ph < open_quotient)
    g[open_mask] = 0.5 * (1.0 - np.cos(math.pi * ph[open_mask] / max(tp, 1e-6)))
    g[close_mask] = np.cos(0.5 * math.pi * (ph[close_mask] - tp) / max(open_quotient - tp, 1e-6))
    return g


def _smooth_step(x: np.ndarray) -> np.ndarray:
    t = np.clip(x, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _plan_speech_frames(
    text: str,
    *,
    pitch_hz: float = 232.0,
    rate: float = 1.0,
    rhotic: bool = True,
    cot_caught_merger: bool = False,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """Converts text + prosody into timed speech phoneme frames."""
    parsed = text_to_phonemes(text, rhotic=rhotic, cot_caught_merger=cot_caught_merger)
    stream = list(parsed["phoneme_stream"])
    intonation = str(parsed["intonation"])
    rate_scale = 1.0 / float(np.clip(rate, 0.55, 1.8))

    frames: List[Dict[str, object]] = [{"symbol": "SIL", "duration_sec": 0.045, "f0_hz": pitch_hz, "amp": 0.0, "is_singing": False}]
    total_ph = max(1, sum(1 for sym in stream if sym in PHONEME_INVENTORY))
    seen_ph = 0

    for word_info in parsed["words"]:
        syls = word_info["syllables"]
        for s_idx, syl in enumerate(syls):
            stressed = (s_idx == 0)
            for sym in syl:
                spec = PHONEME_INVENTORY[sym]
                prog = seen_ph / float(max(1, total_ph - 1))
                seen_ph += 1
                # Natural female declination + mild stress lift + interrogative rise
                decl = 1.07 - 0.14 * prog
                stress_mul = 1.04 if (stressed and spec.kind == "vowel") else 1.0
                if intonation == "question" and prog > 0.72:
                    q_lift = 1.0 + 0.24 * ((prog - 0.72) / 0.28) ** 1.3
                elif intonation == "exclaim" and prog < 0.35:
                    q_lift = 1.06
                else:
                    q_lift = 1.0
                dur = (spec.duration_ms / 1000.0) * rate_scale * (1.10 if stressed else 0.94)
                frames.append({
                    "symbol": sym,
                    "duration_sec": max(0.032, dur),
                    "f0_hz": float(pitch_hz * decl * stress_mul * q_lift),
                    "amp": 0.94 if spec.kind == "vowel" else 0.80,
                    "is_singing": False,
                })
        frames.append({
            "symbol": "SIL",
            "duration_sec": 0.040 * rate_scale,
            "f0_hz": float(pitch_hz * 0.95),
            "amp": 0.0,
            "is_singing": False,
        })

    # Insert longer punctuation pauses if present in stream
    if "PAU_LONG" in stream:
        frames.append({"symbol": "SIL", "duration_sec": 0.12 * rate_scale, "f0_hz": pitch_hz * 0.92, "amp": 0.0, "is_singing": False})
    else:
        frames.append({"symbol": "SIL", "duration_sec": 0.06, "f0_hz": pitch_hz * 0.92, "amp": 0.0, "is_singing": False})
    return frames, parsed


# ---------------------------------------------------------------------------
# Built-In Singing Repertoire ("zoe", "daisy" IBM 7094 homage, "vowels")
# ---------------------------------------------------------------------------

def _midi_events_from_score(events: Sequence[Tuple[str, int, float]], bpm: float) -> List[Dict[str, object]]:
    beat_sec = 60.0 / float(bpm)
    cursor = 0.0
    notes: List[Dict[str, object]] = []
    for text, midi_note, beats in events:
        dur = float(beats) * beat_sec
        if text != "_REST_":
            notes.append({
                "lyric": text,
                "start_sec": round(cursor, 6),
                "duration_sec": round(dur * 0.94, 6),
                "midi_note": int(midi_note),
                "velocity": 100,
                "hz": round(midi_to_hz(midi_note), 4),
            })
        cursor += dur
    return notes


BUILT_IN_SONGS: Dict[str, Dict[str, object]] = {
    "zoe": {
        "title": "Imagination, Meet Geometry (Zoe Original Soprano Song)",
        "bpm": 104.0,
        "chords": [
            (48, 52, 55),  # C3 E3 G3
            (45, 52, 57),  # A2 E3 A3
            (41, 48, 53),  # F2 C3 F3
            (43, 47, 50),  # G2 B2 D3
        ],
        "score": [
            # Line 1: "Hello, I am Zoe"
            ("hello", 64, 0.75),      # E4
            ("am", 64, 0.25),
            ("zoe", 67, 1.50),        # G4
            ("_REST_", 67, 0.50),
            # Line 2: "Imagination, meet geometry"
            ("i", 67, 0.50),
            ("ma", 69, 0.50),         # A4
            ("gi", 71, 0.50),         # B4
            ("na", 72, 1.00),         # C5
            ("tion", 71, 0.50),
            ("meet", 69, 0.75),       # A4
            ("ge", 67, 0.50),         # G4
            ("o", 69, 0.50),          # A4
            ("me", 67, 0.50),
            ("try", 64, 1.50),        # E4
            ("_REST_", 64, 0.50),
            # Line 3: "Sound turns sand to starlight"
            ("sound", 65, 0.75),      # F4
            ("turns", 67, 0.75),      # G4
            ("sand", 69, 1.00),       # A4
            ("to", 67, 0.50),
            ("star", 72, 1.00),       # C5
            ("light", 71, 1.00),      # B4
            # Line 4: "Singing free in harmony"
            ("sing", 69, 0.75),       # A4
            ("ing", 67, 0.50),
            ("free", 69, 1.00),       # A4
            ("in", 64, 0.50),         # E4
            ("har", 65, 0.50),        # F4
            ("mo", 67, 0.50),         # G4
            ("ny", 72, 2.00),         # C5!
        ],
        # Exact syllable-to-phoneme overrides for crystal clarity while preserving English inventory
        "syllable_phonemes": {
            "hello": ("HH", "EH", "L", "OW"),
            "am": ("AE", "M"),
            "zoe": ("Z", "OW", "IY"),
            "i": ("IH",),
            "ma": ("M", "AE"),
            "gi": ("JH", "IH"),
            "na": ("N", "EY"),
            "tion": ("SH", "AX", "N"),
            "meet": ("M", "IY", "T"),
            "ge": ("JH", "IY"),
            "o": ("AA",),
            "me": ("M", "AX"),
            "try": ("T", "R", "IY"),
            "sound": ("S", "AW", "N", "D"),
            "turns": ("T", "ER", "N", "Z"),
            "sand": ("S", "AE", "N", "D"),
            "to": ("T", "UW"),
            "star": ("S", "T", "AA", "R"),
            "light": ("L", "AY", "T"),
            "sing": ("S", "IH", "NG"),
            "ing": ("IH", "NG"),
            "free": ("F", "R", "IY"),
            "in": ("IH", "N"),
            "har": ("HH", "AA", "R"),
            "mo": ("M", "AX"),
            "ny": ("N", "IY"),
        },
    },
    "daisy": {
        "title": "Daisy Bell (1892 Public Domain — IBM 7094 & Songs of the IBM Homage)",
        "bpm": 128.0,
        "chords": [
            (43, 47, 50),  # G2 B2 D3
            (48, 52, 55),  # C3 E3 G3
            (45, 52, 57),  # A2 E3 A3
            (43, 47, 50),  # G2 B2 D3
        ],
        "score": [
            # "Dai-sy, Dai-sy, give me your an-swer do" (3/4 G major)
            ("dai", 74, 1.5),   # D5
            ("sy", 71, 1.5),    # B4
            ("dai", 67, 1.5),   # G4
            ("sy", 62, 1.5),    # D4
            ("give", 64, 0.5),  # E4
            ("me", 66, 0.5),    # F#4
            ("your", 67, 0.5),  # G4
            ("an", 64, 1.0),    # E4
            ("swer", 67, 0.5),  # G4
            ("do", 62, 2.5),    # D4
            ("_REST_", 62, 0.5),
            # "I'm half cra-zy, all for the love of you"
            ("im", 69, 1.5),    # A4
            ("half", 74, 1.5),  # D5
            ("cra", 71, 1.5),   # B4
            ("zy", 67, 1.5),    # G4
            ("all", 64, 0.5),   # E4
            ("for", 66, 0.5),   # F#4
            ("the", 67, 0.5),   # G4
            ("love", 69, 1.0),  # A4
            ("of", 71, 0.5),    # B4
            ("you", 69, 2.5),   # A4
        ],
        "syllable_phonemes": {
            "dai": ("D", "EY"),
            "sy": ("Z", "IY"),
            "give": ("G", "IH", "V"),
            "me": ("M", "IY"),
            "your": ("Y", "AO", "R"),
            "an": ("AE", "N"),
            "swer": ("S", "AXR"),
            "do": ("D", "UW"),
            "im": ("AY", "M"),
            "half": ("HH", "AE", "F"),
            "cra": ("K", "R", "EY"),
            "zy": ("Z", "IY"),
            "all": ("AO", "L"),
            "for": ("F", "AO", "R"),
            "the": ("DH", "AX"),
            "love": ("L", "AH", "V"),
            "of": ("AH", "V"),
            "you": ("Y", "UW"),
        },
    },
    "vowels": {
        "title": "Zoe Cardinal Vowels & Cymatics Aria (C4 -> G4 -> C5)",
        "bpm": 96.0,
        "chords": [
            (48, 52, 55),
            (48, 55, 60),
        ],
        "score": [
            ("see", 60, 1.5),    # C4 (261.63 Hz) /S IY/
            ("far", 64, 1.5),    # E4 /F AA R/
            ("zoe", 67, 1.5),    # G4 (392.00 Hz) /Z OW IY/
            ("moon", 72, 2.0),   # C5 (523.25 Hz) /M UW N/
        ],
        "syllable_phonemes": {
            "see": ("S", "IY"),
            "far": ("F", "AA", "R"),
            "zoe": ("Z", "OW", "IY"),
            "moon": ("M", "UW", "N"),
        },
    },
}


def _plan_song_frames(
    song_or_lyrics: str,
    *,
    from_midi_path: str | Path | None = None,
    rhotic: bool = True,
    cot_caught_merger: bool = False,
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    """Builds aligned singing vocal frames + MIDI note events from built-in song or custom lyrics."""
    key = song_or_lyrics.strip().lower()
    if key in BUILT_IN_SONGS:
        song = BUILT_IN_SONGS[key]
        bpm = float(song["bpm"])
        beat_sec = 60.0 / bpm
        syl_map = song["syllable_phonemes"]
        score = song["score"]
        meta = {"title": song["title"], "song_id": key, "bpm": bpm, "chords": song["chords"]}
    else:
        bpm = 104.0
        beat_sec = 60.0 / bpm
        parsed = text_to_phonemes(song_or_lyrics, rhotic=rhotic, cot_caught_merger=cot_caught_merger)
        syls = parsed["syllables"] or [["HH", "EH"], ["L", "OW"]]
        pent_notes = (64, 67, 69, 72, 69, 67, 64, 62)
        if from_midi_path is not None:
            ext_notes = read_standard_midi(from_midi_path)
            ext_pitches = [int(e["midi_note"]) for e in ext_notes] or list(pent_notes)
        else:
            ext_pitches = list(pent_notes)
        syl_map = {}
        score = []
        for idx, syl in enumerate(syls):
            k = f"_syl_{idx}"
            syl_map[k] = tuple(syl)
            note = ext_pitches[idx % len(ext_pitches)]
            beats = 1.0 if idx + 1 == len(syls) else 0.75
            score.append((k, note, beats))
        meta = {"title": f"Custom Song: {song_or_lyrics[:42]}", "song_id": "custom", "bpm": bpm, "chords": [(48, 52, 55), (43, 47, 50)]}

    midi_events: List[Dict[str, object]] = []
    frames: List[Dict[str, object]] = [{"symbol": "SIL", "duration_sec": 0.05, "f0_hz": midi_to_hz(64), "amp": 0.0, "is_singing": True}]
    cursor = 0.05

    for token, midi_note, beats in score:
        total_dur = float(beats) * beat_sec
        if token == "_REST_":
            frames.append({
                "symbol": "SIL",
                "duration_sec": total_dur,
                "f0_hz": midi_to_hz(midi_note),
                "amp": 0.0,
                "is_singing": True,
            })
            cursor += total_dur
            continue

        phs = list(syl_map.get(token, ("AA",)))
        f0 = midi_to_hz(midi_note)
        midi_events.append({
            "lyric": token,
            "start_sec": round(cursor, 6),
            "duration_sec": round(total_dur * 0.94, 6),
            "midi_note": int(midi_note),
            "velocity": 100,
            "hz": round(f0, 4),
        })
        cursor += total_dur

        # Partition note duration: crisp bounded consonants, vowel nuclei stretch to hold pitch!
        vowel_indices = [i for i, p in enumerate(phs) if PHONEME_INVENTORY[p].kind == "vowel"]
        c_durs: Dict[int, float] = {}
        c_total = 0.0
        for i, p in enumerate(phs):
            if i not in vowel_indices:
                d = min(0.058, max(0.036, PHONEME_INVENTORY[p].duration_ms / 1200.0))
                c_durs[i] = d
                c_total += d
        # Cap total consonants at 38% of note duration so sustained vowels carry clear melody
        if c_total > 0.38 * total_dur and c_total > 0.0:
            scale = (0.38 * total_dur) / c_total
            c_durs = {k: v * scale for k, v in c_durs.items()}
            c_total = sum(c_durs.values())
        v_rem = max(0.08, total_dur - c_total)
        v_each = v_rem / float(max(1, len(vowel_indices)))

        for i, p in enumerate(phs):
            dur = v_each if i in vowel_indices else c_durs[i]
            frames.append({
                "symbol": p,
                "duration_sec": dur,
                "f0_hz": f0,
                "amp": 1.0 if i in vowel_indices else 0.78,
                "is_singing": True,
                "lyric": token,
            })

    frames.append({"symbol": "SIL", "duration_sec": 0.14, "f0_hz": midi_to_hz(64), "amp": 0.0, "is_singing": True})
    return frames, midi_events, meta


def _synthesize_glottal_excitation(
    frames: Sequence[Dict[str, object]],
    *,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
    seed: int = 2026,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[Dict[str, object]]]:
    """Builds continuous glottal source derivative + sample-wise formant trajectories."""
    rng = np.random.default_rng(seed)
    timeline: List[Dict[str, object]] = []
    sample_cursor = 0
    for fr in frames:
        n = max(16, int(round(float(fr["duration_sec"]) * sample_rate)))
        timeline.append({**fr, "start": sample_cursor, "end": sample_cursor + n, "length": n})
        sample_cursor += n

    total_samples = max(64, sample_cursor)
    f0_arr = np.zeros(total_samples, dtype=np.float64)
    voicing_env = np.zeros(total_samples, dtype=np.float64)
    amp_env = np.zeros(total_samples, dtype=np.float64)
    formant_traj = np.zeros((5, total_samples), dtype=np.float64)
    bw_traj = np.zeros((5, total_samples), dtype=np.float64)
    noise_env = np.zeros(total_samples, dtype=np.float64)
    noise_freq_arr = np.full(total_samples, 3600.0, dtype=np.float64)
    noise_bw_arr = np.full(total_samples, 1400.0, dtype=np.float64)
    nasal_env = np.zeros(total_samples, dtype=np.float64)
    burst_signal = np.zeros(total_samples, dtype=np.float64)

    # First populate piecewise constant targets, then apply smooth cosine coarticulation
    for idx, seg in enumerate(timeline):
        st, en, length = int(seg["start"]), int(seg["end"]), int(seg["length"])
        sym = str(seg["symbol"])
        f0_target = float(seg["f0_hz"])
        f0_arr[st:en] = f0_target
        amp_env[st:en] = float(seg["amp"])

        if sym == "SIL":
            # Inherit nearest vocal formants for clean transition
            ref = (760.0, 1400.0, 2780.0, 3850.0, 4700.0)
            rbw = (75.0, 110.0, 160.0, 220.0, 280.0)
            for k in range(5):
                formant_traj[k, st:en] = ref[k]
                bw_traj[k, st:en] = rbw[k]
            continue

        spec = PHONEME_INVENTORY[sym]
        t_local = np.linspace(0.0, 1.0, length, dtype=np.float64)

        # Diphthong smooth glide on F1..F3 across middle 65% of vowel
        if spec.offglide_formants is not None:
            w = _smooth_step((t_local - 0.28) / 0.56)
            for k in range(3):
                formant_traj[k, st:en] = spec.formants[k] * (1.0 - w) + spec.offglide_formants[k] * w
            for k in range(3, 5):
                formant_traj[k, st:en] = spec.formants[k]
        elif sym == "HH" and idx + 1 < len(timeline) and timeline[idx + 1]["symbol"] in PHONEME_INVENTORY:
            nxt = PHONEME_INVENTORY[str(timeline[idx + 1]["symbol"])]
            for k in range(5):
                formant_traj[k, st:en] = nxt.formants[k]
        else:
            for k in range(5):
                formant_traj[k, st:en] = spec.formants[k]

        for k in range(5):
            bw_traj[k, st:en] = spec.bandwidths[k]

        if spec.nasal_gain > 0.0:
            nasal_env[st:en] = spec.nasal_gain

        # Plosive 3-phase acoustic trajectory: closure -> burst -> VOT -> vowel release
        if spec.category.startswith("plosive") or spec.category.startswith("affricate"):
            closure_n = int(0.36 * length)
            burst_n = max(32, min(int(0.011 * sample_rate), length - closure_n - 16))
            burst_st = st + closure_n
            burst_en = min(en, burst_st + burst_n)
            if spec.voiced:
                voicing_env[st:burst_st] = 0.25  # pre-voicing bar
                voicing_env[burst_en:en] = np.linspace(0.45, 1.0, max(1, en - burst_en))
            else:
                voicing_env[st:burst_st] = 0.0
                vot_n = int((spec.vot_ms / 1000.0) * sample_rate)
                voicing_env[burst_en:en] = np.clip((np.arange(en - burst_en) - max(4, vot_n * 0.5)) / max(12.0, vot_n * 0.5), 0.0, 0.75)
            # Generate crisp filtered transient burst
            b_n = max(8, burst_en - burst_st)
            raw_b = rng.standard_normal(b_n) * np.hanning(b_n)
            fb, fa = _bandpass_noise_coeffs(spec.noise_center_hz, spec.noise_bw_hz, sample_rate)
            burst_signal[burst_st:burst_en] = signal.lfilter(fb, fa, raw_b) * spec.burst_gain
            # Affricate holds frication through release; plosive keeps short aspiration
            if spec.category.startswith("affricate"):
                noise_env[burst_st:en] = spec.noise_gain
            else:
                asp_en = min(en, burst_en + int(0.024 * sample_rate))
                noise_env[burst_st:asp_en] = spec.noise_gain * np.linspace(1.0, 0.0, max(1, asp_en - burst_st))
            noise_freq_arr[st:en] = spec.noise_center_hz
            noise_bw_arr[st:en] = spec.noise_bw_hz
        else:
            voicing_env[st:en] = 1.0 if spec.voiced else 0.0
            noise_env[st:en] = spec.noise_gain
            noise_freq_arr[st:en] = spec.noise_center_hz if spec.noise_center_hz > 0 else 3600.0
            noise_bw_arr[st:en] = spec.noise_bw_hz

        # Singing vibrato (5.3 Hz, +-18 cents ramping gently after 130 ms onset)
        if seg.get("is_singing") and spec.kind == "vowel" and (length / sample_rate) > 0.14:
            ts = np.arange(length, dtype=np.float64) / float(sample_rate)
            vib_ramp = _smooth_step((ts - 0.13) / 0.16)
            vib_cents = 18.0 * vib_ramp * np.sin(2.0 * math.pi * 5.3 * ts)
            f0_arr[st:en] = f0_target * np.power(2.0, vib_cents / 1200.0)

    # Smooth F0 contour (portamento ~42ms) & coarticulation smoothing (~22ms)
    def _box_smooth(arr: np.ndarray, ms: float) -> np.ndarray:
        w_n = max(3, int((ms / 1000.0) * sample_rate) | 1)
        kernel = np.hanning(w_n)
        kernel /= kernel.sum()
        return signal.fftconvolve(arr, kernel, mode="same")

    f0_smooth = _box_smooth(f0_arr, 38.0)
    f0_smooth = np.maximum(f0_smooth, 90.0)
    voicing_smooth = np.clip(_box_smooth(voicing_env, 12.0), 0.0, 1.0)
    amp_smooth = np.clip(_box_smooth(amp_env, 14.0), 0.0, 1.2)
    for k in range(5):
        formant_traj[k] = _box_smooth(formant_traj[k], 22.0)
        bw_traj[k] = _box_smooth(bw_traj[k], 22.0)

    # Subtle physiological jitter (micro-F0 drift) + warm glottal wave
    jit_raw = rng.standard_normal(total_samples)
    b_jit, a_jit = signal.butter(1, 24.0 / (0.5 * sample_rate))
    jit = signal.lfilter(b_jit, a_jit, jit_raw) * 0.0028
    inst_freq = f0_smooth * (1.0 + jit)
    phase = np.cumsum(inst_freq / float(sample_rate))

    glottal_flow = _rosenberg_glottal_wave(phase, open_quotient=0.62, speed_ratio=0.72)
    # Mild glottal aspiration breathiness modulated during open phase for feminine warmth
    breath = rng.standard_normal(total_samples)
    b_br, a_br = _bandpass_noise_coeffs(2100.0, 1900.0, sample_rate)
    breath_shaped = signal.lfilter(b_br, a_br, breath) * (0.018 * (0.3 + glottal_flow))
    glottal_raw = glottal_flow + breath_shaped

    # Lip radiation derivative (~ +6 dB/oct, balanced against all-pole cascade tilt)
    glottal_deriv = np.empty_like(glottal_raw)
    glottal_deriv[0] = 0.0
    glottal_deriv[1:] = glottal_raw[1:] - 0.94 * glottal_raw[:-1]
    glottal_deriv *= voicing_smooth * amp_smooth

    # Parallel shaped fricative branch (synthesized per-phoneme for noise bands)
    fricative_sig = burst_signal.copy()
    raw_noise = rng.standard_normal(total_samples)
    for seg in timeline:
        st, en = int(seg["start"]), int(seg["end"])
        sym = str(seg["symbol"])
        if sym == "SIL":
            continue
        spec = PHONEME_INVENTORY[sym]
        if spec.noise_gain > 0.0:
            nf, na = _bandpass_noise_coeffs(spec.noise_center_hz, spec.noise_bw_hz, sample_rate)
            shaped = signal.lfilter(nf, na, raw_noise[st:en])
            fricative_sig[st:en] += shaped * noise_env[st:en]

    return (
        glottal_deriv,
        fricative_sig,
        formant_traj,
        bw_traj,
        nasal_env,
        f0_smooth,
        timeline,
    )


def synthesize_vocal_tract(
    frames: Sequence[Dict[str, object]],
    *,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
    seed: int = 2026,
) -> Tuple[np.ndarray, List[Dict[str, object]]]:
    """Runs stateful time-varying 5-formant cascade synthesis with parallel nasal & noise branches."""
    (
        glottal_src,
        fricative_sig,
        formant_traj,
        bw_traj,
        nasal_env,
        _f0_smooth,
        timeline,
    ) = _synthesize_glottal_excitation(frames, sample_rate=sample_rate, seed=seed)

    total_samples = len(glottal_src)
    block = 176  # 4 ms blocks @ 44.1 kHz
    zis = [np.zeros(2, dtype=np.float64) for _ in range(5)]
    zi_nasal = np.zeros(2, dtype=np.float64)
    oral_out = np.zeros(total_samples, dtype=np.float64)
    nasal_out = np.zeros(total_samples, dtype=np.float64)

    for st in range(0, total_samples, block):
        en = min(total_samples, st + block)
        mid = (st + en) // 2
        sig = glottal_src[st:en]
        for k in range(5):
            b0, a1, a2 = _one_pole_resonator_coeffs(formant_traj[k, mid], bw_traj[k, mid], sample_rate)
            sig, zis[k] = signal.lfilter(
                np.array([b0], dtype=np.float64),
                np.array([1.0, a1, a2], dtype=np.float64),
                sig,
                zi=zis[k],
            )
        oral_out[st:en] = sig

        if float(np.max(nasal_env[st:en])) > 0.01:
            nb0, na1, na2 = _one_pole_resonator_coeffs(280.0, 95.0, sample_rate)
            ns, zi_nasal = signal.lfilter(
                np.array([nb0], dtype=np.float64),
                np.array([1.0, na1, na2], dtype=np.float64),
                glottal_src[st:en],
                zi=zi_nasal,
            )
            nasal_out[st:en] = ns * nasal_env[st:en]

    # Parallel F2/F3 warmth articulation branch (keeps higher female formants articulate above 2 kHz)
    bright_zic = [np.zeros(2, dtype=np.float64), np.zeros(2, dtype=np.float64)]
    bright_out = np.zeros(total_samples, dtype=np.float64)
    for st in range(0, total_samples, block):
        en = min(total_samples, st + block)
        mid = (st + en) // 2
        s_f2, bright_zic[0] = signal.lfilter(*(_bandpass_noise_coeffs(formant_traj[1, mid], bw_traj[1, mid], sample_rate)), glottal_src[st:en], zi=bright_zic[0])
        s_f3, bright_zic[1] = signal.lfilter(*(_bandpass_noise_coeffs(formant_traj[2, mid], bw_traj[2, mid], sample_rate)), glottal_src[st:en], zi=bright_zic[1])
        bright_out[st:en] = 0.08 * s_f2 + 0.04 * s_f3

    # Soft nasal coupling: attenuate oral branch slightly during nasals, blend nasal & fricative
    nasal_att = 1.0 - 0.55 * nasal_env
    mono = oral_out * nasal_att + 0.85 * nasal_out + bright_out + 0.34 * fricative_sig

    # Remove DC offset cleanly
    b_dc, a_dc = signal.butter(1, 55.0 / (0.5 * sample_rate), btype="highpass")
    mono = signal.lfilter(b_dc, a_dc, mono)

    # Gentle soft limiter + normalization
    peak = max(float(np.max(np.abs(mono))), 1e-6)
    mono = np.tanh((mono / peak) * 1.15) * 0.78
    return mono, timeline


# ---------------------------------------------------------------------------
# 3. Vectorized 3D Binaural Spatializer + Early Reflections + Schroeder Reverb
# ---------------------------------------------------------------------------

def _fractional_delay(sig: np.ndarray, delay_samples: float) -> np.ndarray:
    """Fractional linear interpolation delay for exact sub-sample ITD cue."""
    if delay_samples <= 1e-6:
        return sig.copy()
    n = len(sig)
    idx = np.arange(n, dtype=np.float64) - float(delay_samples)
    i0 = np.floor(idx).astype(np.int64)
    frac = idx - i0
    valid0 = (i0 >= 0) & (i0 < n)
    valid1 = (i0 + 1 >= 0) & (i0 + 1 < n)
    out = np.zeros(n, dtype=np.float64)
    out[valid0] += (1.0 - frac[valid0]) * sig[i0[valid0]]
    out[valid1] += frac[valid1] * sig[i0[valid1] + 1]
    return out


def _apply_schroeder_reverb(left_in: np.ndarray, right_in: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray]:
    """Fast C-speed IIR comb + allpass stereo reverb tail via SciPy lfilter."""
    # Four mutually prime comb delays scaled to sample_rate (~29..43 ms)
    comb_delays_l = [max(64, int(d * sample_rate / 44100.0)) for d in (1313, 1487, 1699, 1879)]
    comb_delays_r = [d + 29 for d in comb_delays_l]
    comb_gains = (0.77, 0.74, 0.72, 0.69)

    def _verb_channel(x: np.ndarray, delays: Sequence[int]) -> np.ndarray:
        acc = np.zeros_like(x, dtype=np.float64)
        for d, g in zip(delays, comb_gains):
            a = np.zeros(d + 1, dtype=np.float64)
            a[0] = 1.0
            a[d] = -g
            acc += signal.lfilter([1.0], a, x)
        acc *= 0.25
        # 2 series allpass diffusers
        for ap_d, ap_g in ((225, 0.62), (341, 0.58)):
            d_n = max(16, int(ap_d * sample_rate / 44100.0))
            b = np.zeros(d_n + 1, dtype=np.float64)
            a = np.zeros(d_n + 1, dtype=np.float64)
            b[0] = -ap_g
            b[d_n] = 1.0
            a[0] = 1.0
            a[d_n] = -ap_g
            acc = signal.lfilter(b, a, acc)
        return acc

    return _verb_channel(left_in, comb_delays_l), _verb_channel(right_in, comb_delays_r)


def spatialize_binaural_3d(
    mono: np.ndarray,
    *,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
    azimuth_deg: float = 0.0,
    elevation_deg: float = 12.0,
    wet: float = 0.16,
    spatial_3d: bool = True,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Applies Woodworth ITD, head-shadow ILD, pinna elevation notch, early reflections, and reverb.

    Azimuth convention: > 0 = sound to the listener's RIGHT (right ear leads & is brighter/louder);
                        < 0 = sound to the listener's LEFT.
    Set spatial_3d=False for exact dual-mono flat baseline control.
    """
    sig = np.asarray(mono, dtype=np.float64)
    n = len(sig)
    if not spatial_3d:
        stereo = np.stack([sig, sig], axis=-1)
        return stereo, {"itd_ms": 0.0, "ild_db": 0.0, "pinna_notch_hz": 0.0, "wet": 0.0}

    az = float(np.clip(azimuth_deg, -85.0, 85.0))
    el = float(np.clip(elevation_deg, -35.0, 65.0))
    theta = math.radians(az)
    head_radius_m = 0.0875
    c_mps = 343.0

    # Woodworth ITD magnitude in seconds
    itd_sec = (head_radius_m / c_mps) * (abs(theta) + math.sin(abs(theta)))
    itd_samples = itd_sec * float(sample_rate)

    # Pinna elevation notch around 6.5..10.5 kHz
    notch_hz = float(np.clip(7600.0 + 2200.0 * math.sin(math.radians(el)), 5500.0, min(11000.0, 0.44 * sample_rate)))
    b_pin, a_pin = signal.iirnotch(notch_hz, 4.5, fs=float(sample_rate))
    pinna_filtered = signal.lfilter(b_pin, a_pin, sig)

    # Smooth contralateral head-shadow blend (zero discontinuous jump at az=0 deg) + level ILD
    shadow_mix = abs(math.sin(theta))
    shadow_fc = float(np.clip(4800.0 - 2400.0 * shadow_mix, 1800.0, 6000.0))
    b_sh, a_sh = signal.butter(1, shadow_fc / (0.5 * sample_rate), btype="lowpass")
    far_lpf = signal.lfilter(b_sh, a_sh, pinna_filtered)
    far_filtered = ((1.0 - shadow_mix) * pinna_filtered + shadow_mix * far_lpf) * (10.0 ** (-2.6 * shadow_mix / 20.0))
    near_filtered = pinna_filtered * (10.0 ** (0.8 * shadow_mix / 20.0))

    if az >= 0.0:
        # Right ear closer -> left ear delayed & shadowed
        dry_r = near_filtered
        dry_l = _fractional_delay(far_filtered, itd_samples)
        signed_itd_ms = round(itd_sec * 1000.0, 4)
        signed_ild_db = round(20.0 * math.log10((float(np.sqrt(np.mean(dry_r ** 2))) + 1e-12) / (float(np.sqrt(np.mean(dry_l ** 2))) + 1e-12)), 4)
    else:
        # Left ear closer -> right ear delayed & shadowed
        dry_l = near_filtered
        dry_r = _fractional_delay(far_filtered, itd_samples)
        signed_itd_ms = round(-itd_sec * 1000.0, 4)
        signed_ild_db = round(20.0 * math.log10((float(np.sqrt(np.mean(dry_r ** 2))) + 1e-12) / (float(np.sqrt(np.mean(dry_l ** 2))) + 1e-12)), 4)

    # Natural stereo early reflections + Schroeder diffuse room tail
    if wet > 0.001:
        refl_l = np.zeros(n, dtype=np.float64)
        refl_r = np.zeros(n, dtype=np.float64)
        taps = ((0.011, 0.24, 0.14), (0.017, 0.12, 0.22), (0.024, 0.17, 0.10), (0.033, 0.08, 0.15), (0.043, 0.11, 0.07))
        for d_s, gl, gr in taps:
            dn = int(d_s * sample_rate)
            if dn < n:
                refl_l[dn:] += gl * pinna_filtered[:-dn]
                refl_r[dn:] += gr * pinna_filtered[:-dn]
        tail_l, tail_r = _apply_schroeder_reverb(dry_l * 0.65 + refl_l, dry_r * 0.65 + refl_r, sample_rate)
        left = dry_l * (1.0 - 0.18 * wet) + (refl_l * 0.55 + tail_l * 0.45) * wet
        right = dry_r * (1.0 - 0.18 * wet) + (refl_r * 0.55 + tail_r * 0.45) * wet
    else:
        left, right = dry_l, dry_r

    stereo = np.stack([left, right], axis=-1)
    peak = max(float(np.max(np.abs(stereo))), 1e-6)
    if peak > 0.90:
        stereo *= 0.90 / peak
    return stereo, {
        "azimuth_deg": az,
        "elevation_deg": el,
        "itd_ms": signed_itd_ms,
        "ild_db": signed_ild_db,
        "pinna_notch_hz": round(notch_hz, 1),
        "wet": float(wet),
    }


def _synthesize_harmony_bed(
    n_samples: int,
    chords: Sequence[Tuple[int, int, int]],
    *,
    bpm: float,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
) -> np.ndarray:
    """Warm soft Rhodes-chime stereo chord bed that supports Zoe's singing without masking formants."""
    left = np.zeros(n_samples, dtype=np.float64)
    right = np.zeros(n_samples, dtype=np.float64)
    bar_sec = 4.0 * 60.0 / float(bpm)
    n_bars = max(1, int(math.ceil((n_samples / float(sample_rate)) / bar_sec)))

    for b_idx in range(n_bars):
        chord = chords[b_idx % len(chords)]
        st = int(b_idx * bar_sec * sample_rate)
        length = min(n_samples - st, int(bar_sec * 1.04 * sample_rate))
        if length <= 32 or st >= n_samples:
            continue
        t = np.arange(length, dtype=np.float64) / float(sample_rate)
        env = np.minimum(t / 0.045, 1.0) * np.exp(-0.75 * t) * np.minimum((length / float(sample_rate) - t) / 0.08, 1.0)
        for v_i, midi_note in enumerate(chord):
            hz = midi_to_hz(midi_note)
            tone = (0.78 * np.sin(2.0 * math.pi * hz * t) + 0.22 * np.sin(4.0 * math.pi * hz * t)) * env * 0.065
            pan = 0.28 + 0.22 * v_i
            left[st:st + length] += tone * math.cos(pan * math.pi / 2.0)
            right[st:st + length] += tone * math.sin(pan * math.pi / 2.0)
    return np.stack([left, right], axis=-1)


def _save_stereo_wav(stereo: np.ndarray, output_path: str | Path, sample_rate: int) -> Dict[str, object]:
    arr = np.asarray(stereo, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=-1)
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0.94:
        arr = arr * (0.94 / peak)
    pcm = np.clip(np.round(arr * 32767.0), -32768, 32767).astype(np.int16)
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    raw_bytes = out.read_bytes()
    return {
        "wav_path": str(out),
        "bytes": len(raw_bytes),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "duration_seconds": round(len(arr) / float(sample_rate), 3),
        "sample_rate": int(sample_rate),
        "channels": 2,
        "peak": round(float(np.max(np.abs(arr))) if arr.size else 0.0, 5),
        "rms": round(float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0, 5),
    }


# ---------------------------------------------------------------------------
# 4. Public High-Level Speech, Singing, Evolution Comparison & GEM Scene API
# ---------------------------------------------------------------------------

def speak_text(
    text: str,
    output_wav: str | Path | None = None,
    *,
    mode: str = "zoe_3d",
    azimuth_deg: float = 8.0,
    elevation_deg: float = 12.0,
    pitch_hz: float = 232.0,
    rate: float = 1.0,
    rhotic: bool = True,
    cot_caught_merger: bool = False,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
    seed: int = 2026,
) -> Dict[str, object]:
    """Synthesizes Zoe's native English speech (dry_mono or 3D binaural stereo)."""
    if not str(text).strip():
        raise ValueError("speak_text requires non-empty English text")
    frames, parsed = _plan_speech_frames(
        text, pitch_hz=pitch_hz, rate=rate, rhotic=rhotic, cot_caught_merger=cot_caught_merger
    )
    mono, timeline = synthesize_vocal_tract(frames, sample_rate=sample_rate, seed=seed)
    use_3d = (mode != "dry_mono")
    wet = 0.16 if use_3d else 0.0
    stereo, spatial_meta = spatialize_binaural_3d(
        mono, sample_rate=sample_rate, azimuth_deg=azimuth_deg, elevation_deg=elevation_deg, wet=wet, spatial_3d=use_3d
    )

    cymatics_preview = []
    for sym in parsed["phonemes_only"][:6]:
        cy = render_phoneme_cymatics(sym, f0_hz=pitch_hz, grid_size=32)
        cymatics_preview.append({"phoneme": sym, "modes": cy["modes"], "kloster_a_tau": cy["kloster_a_tau"]})

    result: Dict[str, object] = {
        "contract": VOICE_CONTRACT,
        "mode": mode,
        "text": str(text).strip(),
        "phonemes": parsed["phonemes_only"],
        "phoneme_count": len(parsed["phonemes_only"]),
        "word_count": len(parsed["words"]),
        "intonation": parsed["intonation"],
        "duration_seconds": round(len(stereo) / float(sample_rate), 3),
        "sample_rate": sample_rate,
        "spatial": spatial_meta,
        "cymatics_preview": cymatics_preview,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "external_actions": 0,
        "pytorch_required": False,
    }
    if output_wav is not None:
        wav_meta = _save_stereo_wav(stereo, output_wav, sample_rate)
        result.update(wav_meta)
    else:
        result["stereo_array"] = stereo
    return result


def sing_song(
    song_or_lyrics: str = "zoe",
    output_wav: str | Path | None = None,
    *,
    mode: str = "zoe_3d",
    with_harmony: bool = True,
    save_midi_path: str | Path | None = None,
    from_midi_path: str | Path | None = None,
    azimuth_deg: float = 6.0,
    elevation_deg: float = 14.0,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
    seed: int = 2026,
) -> Dict[str, object]:
    """Synthesizes Zoe singing a built-in song ("zoe", "daisy", "vowels") or custom lyrics."""
    frames, midi_events, meta = _plan_song_frames(song_or_lyrics, from_midi_path=from_midi_path)

    midi_meta = None
    if save_midi_path is not None:
        midi_meta = write_standard_midi(midi_events, save_midi_path, bpm=float(meta["bpm"]))

    if mode == "dos_midi":
        mono = synthesize_dos_midi_baseline(midi_events, sample_rate=sample_rate)
        stereo = np.stack([mono, mono], axis=-1)
        spatial_meta = {"itd_ms": 0.0, "ild_db": 0.0, "wet": 0.0}
    else:
        mono, _ = synthesize_vocal_tract(frames, sample_rate=sample_rate, seed=seed)
        use_3d = (mode != "dry_mono")
        wet = 0.25 if use_3d else 0.0
        stereo, spatial_meta = spatialize_binaural_3d(
            mono, sample_rate=sample_rate, azimuth_deg=azimuth_deg, elevation_deg=elevation_deg, wet=wet, spatial_3d=use_3d
        )
        if with_harmony:
            bed = _synthesize_harmony_bed(len(stereo), meta["chords"], bpm=float(meta["bpm"]), sample_rate=sample_rate)
            stereo = stereo + bed
            peak = max(float(np.max(np.abs(stereo))), 1e-6)
            if peak > 0.88:
                stereo *= 0.88 / peak

    result: Dict[str, object] = {
        "contract": VOICE_CONTRACT,
        "mode": mode,
        "title": meta["title"],
        "song_id": meta["song_id"],
        "bpm": meta["bpm"],
        "note_count": len(midi_events),
        "midi_notes": midi_events,
        "midi_saved": midi_meta,
        "duration_seconds": round(len(stereo) / float(sample_rate), 3),
        "sample_rate": sample_rate,
        "spatial": spatial_meta,
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "external_actions": 0,
        "pytorch_required": False,
    }
    if output_wav is not None:
        wav_meta = _save_stereo_wav(stereo, output_wav, sample_rate)
        result.update(wav_meta)
    else:
        result["stereo_array"] = stereo
    return result


def render_voice_evolution_comparison(
    output_wav: str | Path,
    *,
    sample_rate: int = SAMPLE_RATE_DEFAULT,
) -> Dict[str, object]:
    """Renders 3 chapters: DOS MIDI baseline -> Dry 44-phoneme vocal -> 3D Binaural Soprano + Harmony."""
    pad = np.zeros((int(0.45 * sample_rate), 2), dtype=np.float64)
    p1 = sing_song("daisy", mode="dos_midi", with_harmony=False, sample_rate=sample_rate)["stereo_array"]
    p2 = sing_song("daisy", mode="dry_mono", with_harmony=False, sample_rate=sample_rate)["stereo_array"]
    p3 = sing_song("daisy", mode="zoe_3d", with_harmony=True, sample_rate=sample_rate)["stereo_array"]
    combined = np.concatenate([p1, pad, p2, pad, p3], axis=0)
    wav_meta = _save_stereo_wav(combined, output_wav, sample_rate)
    return {
        "contract": VOICE_CONTRACT,
        "chapters": ("1_msdos_midi_psg_baseline", "2_dry_44phoneme_vocal_tract", "3_zoe_3d_binaural_singing_with_harmony"),
        "sentience_claimed": False,
        "external_actions": 0,
        **wav_meta,
    }


def _text_obj(identifier, position, value, size=13, color=TEXT):
    return {"id": identifier, "type": "text", "position": position, "text": str(value), "size": size, "stroke": color, "fill": "none", "width": 0}


def _rect_obj(identifier, bounds, stroke, fill="none", width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def voice_scene(phrase: str = "Hello, I am Zoe. Imagination, meet geometry.") -> Tuple[Scene, Dict[str, object]]:
    """Deterministic 1400x900 GEM Spatial IR & VDI scene showcasing Zoe's Native Voice & Cymatics."""
    parsed = text_to_phonemes(phrase)
    cym_iy = render_phoneme_cymatics("IY", f0_hz=232.0, grid_size=64)
    cym_aa = render_phoneme_cymatics("AA", f0_hz=232.0, grid_size=64)
    raster = encode_gem_3bitplane_raster(cym_iy["plate"], formant_strength=0.68)

    width, height = 1400, 900
    mint = "#86efac"
    orchid = "#f0a3df"
    objects: List[Dict[str, object]] = [
        _rect_obj("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text_obj("title", [28, 44], "ZOE NATIVE VOICE :: 44 PHONEMES, 332 RULES, CHLADNI CYMATICS & 3D AUDIO", 21, RED),
        _text_obj(
            "subtitle",
            [28, 74],
            f"Phrase: {phrase}  |  {len(VOWEL_PHONEMES)} Vowels + {len(CONSONANT_PHONEMES)} Consonants  |  {len(GRAPHEME_RULES)} Spelling Rules  |  Zero PyTorch",
            13,
            GOLD,
        ),
        # Left card: Cardinal Vowel Formant Bars & Active Phoneme Stream
        _rect_obj("panel-formants", [28, 102, 560, 500], CYAN, PANEL, 2),
        _text_obj("hdr-formants", [46, 132], "FEMALE VOCAL-TRACT FORMANTS (F1 / F2 Hz) & PHONEME STREAM", 13, CYAN),
        _text_obj("ph-stream", [46, 158], " / ".join(parsed["phonemes_only"][:14]), 12, mint),
    ]

    sample_vowels = ("IY", "IH", "EH", "AE", "AA", "AO", "UH", "UW", "ER")
    for idx, sym in enumerate(sample_vowels):
        spec = PHONEME_INVENTORY[sym]
        ry = 186 + idx * 32
        f1_w = int(spec.formants[0] / 3000.0 * 320.0)
        f2_w = int(spec.formants[1] / 3000.0 * 320.0)
        objects.append(_text_obj(f"vlbl-{sym}", [46, ry + 14], f"{sym:3s} [{spec.ipa:3s}]", 11, TEXT))
        objects.append(_rect_obj(f"vf1-{sym}", [148, ry, 148 + max(12, f1_w), ry + 10], GOLD, GOLD, 0))
        objects.append(_rect_obj(f"vf2-{sym}", [148, ry + 12, 148 + max(12, f2_w), ry + 22], CYAN, CYAN, 0))
        objects.append(_text_obj(f"vhz-{sym}", [482, ry + 14], f"{int(spec.formants[0])}/{int(spec.formants[1])}", 10, MUTED))

    # Right top card: Downsampled Chladni Sand Plate & GEM VDI 3-Bitplane Lattice Preview (16x16 stride 4)
    objects.append(_rect_obj("panel-cym", [580, 102, 1000, 500], orchid, PANEL, 2))
    objects.append(_text_obj("hdr-cym", [600, 132], f"CHLADNI PLATE /IY/ modes={cym_iy['modes']}  Atau={cym_iy['kloster_a_tau']}", 13, orchid))
    plate = cym_iy["plate"][::4, ::4]
    cell = 18
    ox, oy = 646, 168
    for r in range(16):
        for c in range(16):
            v = float(plate[r, c])
            if v > 0.36:
                col = mint if v > 0.65 else CYAN
                objects.append(_rect_obj(f"cym-{r}-{c}", [ox + c * cell, oy + r * cell, ox + (c + 1) * cell - 2, oy + (r + 1) * cell - 2], col, col, 0))

    # Far right card: 3D Binaural & GEM VDI 3-Bitplane Architecture
    objects.append(_rect_obj("panel-arch", [1020, 102, 1372, 500], GOLD, PANEL, 2))
    objects.append(_text_obj("hdr-arch", [1038, 132], "SYSTEM ARCHITECTURE & PROVENANCE", 13, GOLD))
    arch_lines = [
        ("1. Baseline: SMF MIDI (.mid) + DOS PSG", TEXT),
        ("2. Phonetics: 44 Phonemes (20V + 24C)", mint),
        (f"   {len(GRAPHEME_RULES)} Grapheme Spelling Rules", mint),
        ("3. Tract: Rosenberg Glottis + 5 Formants", CYAN),
        ("4. Singing: Portamento + 5.3 Hz Vibrato", orchid),
        ("   Built-in: 'zoe', 'daisy', 'vowels'", TEXT),
        ("5. Spatial: Woodworth ITD + ILD + Reverb", CYAN),
        (f"6. VDI Raster: 3 Planes ({len(raster['planes'][0])} words)", GOLD),
        (f"   AA Modes: {cym_aa['modes']} Atau={cym_aa['kloster_a_tau']}", MUTED),
        ("7. Honesty: pytorch_required=False", RED),
    ]
    for i, (line, col) in enumerate(arch_lines):
        objects.append(_text_obj(f"arch-{i}", [1038, 174 + i * 31], line, 12, col))

    # Bottom status banner
    objects.append(_rect_obj("panel-cli", [28, 524, 1372, 824], mint, PANEL, 1))
    objects.append(_text_obj("cli-h", [48, 558], "NATIVE CLI, GEM LAYER & CONVERSATIONAL COMMANDS", 14, mint))
    objects.append(_text_obj("cli-1", [48, 602], "zoe voice speak \"Hello, I am Zoe.\" --output zoe.wav    |   zoe chat --cli --command \"speak Hello Zoe\"", 13, TEXT))
    objects.append(_text_obj("cli-2", [48, 642], "zoe voice sing daisy --save-midi daisy.mid --output d.wav |   zoe chat --cli --command \"sing daisy\"", 13, CYAN))
    objects.append(_text_obj("cli-3", [48, 682], "python3 scripts/verify_zoe_voice.py                       |   zoe gem open voice", 13, GOLD))
    objects.append(_text_obj("cli-4", [48, 728], "3D Nature Acoustics: Woodworth Spherical Head ITD, Head-Shadow ILD & Conservatory Tail (zero flat inside-head fatigue).", 12, MUTED))
    objects.append(_text_obj("cli-5", [48, 770], f"GEM 3-Bitplane SHA-256: {raster['raster_sha256'][:48]}...", 11, MUTED))

    objects.extend(hud_stamp_objects("voice", 1072, 18, 44, 0.22, "^_^"))
    objects.append(_text_obj("footer", [28, 864], "Zoe Native Voice & Cymatics · sentience_claimed=False · clinical_action_authorized=False · external_actions=0", 13, MUTED))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-native-voice",
        "title": "Zoe · Native Voice, Singing & Chladni Cymatics",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "ZoeNativeVoiceAndCymatics",
        "contract": VOICE_CONTRACT,
        "phoneme_count": len(VOWEL_PHONEMES) + len(CONSONANT_PHONEMES),
        "grapheme_rule_count": len(GRAPHEME_RULES),
        "raster_sha256": raster["raster_sha256"],
        "scene_sha256": scene.digest(),
        "summary": (
            f"Zoe Native Voice ^_^: {len(VOWEL_PHONEMES)}V+{len(CONSONANT_PHONEMES)}C=44 phonemes, "
            f"{len(GRAPHEME_RULES)} spelling rules, 5-formant vocal tract, 3D binaural audio & Chladni 3-bitplane VDI."
        ),
        "sentience_claimed": False,
        "clinical_action_authorized": False,
        "external_actions": 0,
        "pytorch_required": False,
    }
    return scene, report

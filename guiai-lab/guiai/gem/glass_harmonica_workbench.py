"""Zoe's Glass Harmonica & Chladni Orrery Interactive Workbench.

Serves the standalone offline HTML5 + Canvas + WebAudio workbench from
`static/glass_harmonica.html` and synthesizes 44.1 kHz stereo choir + chime WAV
bytes offline via Zoe's native choral formant engine (`zoe_choral_composer.py`).
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence
import wave

import numpy as np

# Offline contract identifier and standard CD-quality sample rate (44.1 kHz)
CONTRACT = "zoe-glass-harmonica-orrery/v1"
SR = 44100
_STATIC_HTML = Path(__file__).resolve().parent / "static" / "glass_harmonica.html"


# Serve the standalone HTML5 + Canvas + WebAudio workbench from static assets
def render_harmonica_workbench_html() -> bytes:
    """Return the standalone offline Glass Harmonica & Chladni Orrery HTML bytes."""
    return _STATIC_HTML.read_bytes()


# Peak-limit and encode stereo float64 audio into 16-bit PCM WAV bytes
def _encode_wav_bytes(stereo: np.ndarray, sr: int = SR) -> bytes:
    """Encode a normalized stereo float64 buffer to 16-bit PCM WAV bytes."""
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if peak > 0.94:
        stereo = stereo * (0.94 / peak)
    pcm = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# Normalize incoming 3-voice mode/vowel specs within safe Chladni bounds
def _parse_voice_specs(raw_voices: Any) -> List[Dict[str, Any]]:
    """Sanitize incoming 3-voice specifications with deterministic defaults."""
    defaults = [
        {"n": 2, "m": 5, "vowel": "AA"},
        {"n": 3, "m": 4, "vowel": "IY"},
        {"n": 1, "m": 3, "vowel": "OW"},
    ]
    if not isinstance(raw_voices, Sequence) or isinstance(raw_voices, (str, bytes)):
        return defaults
    cleaned: List[Dict[str, Any]] = []
    for idx in range(3):
        src = raw_voices[idx] if idx < len(raw_voices) and isinstance(raw_voices[idx], dict) else defaults[idx]
        cleaned.append({
            "n": max(1, min(8, int(src.get("n", defaults[idx]["n"])))),
            "m": max(1, min(9, int(src.get("m", defaults[idx]["m"])))),
            "vowel": str(src.get("vowel", defaults[idx]["vowel"])).upper()[:2],
        })
    return cleaned


# Layer crystalline glass chimes locked to the chosen polyrhythm pulse count
def _add_polyrhythm_chimes(stereo: np.ndarray, pulses: int, dur_sec: float) -> None:
    """Overlay crystalline glass chimes locked to the selected polyrhythm ratio."""
    n_total = stereo.shape[0]
    count = max(2, min(8, pulses))
    for i in range(count):
        start = int((i * dur_sec / count) * SR)
        seg_n = min(n_total - start, int(0.55 * SR))
        if seg_n <= 32:
            continue
        t = np.arange(seg_n, dtype=np.float64) / SR
        freq = 1174.66 if i % 2 == 0 else 880.0
        tone = 0.08 * np.sin(2.0 * math.pi * freq * t) * np.exp(-6.2 * t)
        pan_l = 0.70 if i % 2 == 0 else 0.30
        stereo[start:start + seg_n, 0] += pan_l * tone
        stereo[start:start + seg_n, 1] += (1.0 - pan_l) * tone


# Render full 3-voice formant chord + glass chimes completely offline
def render_harmonica_wav_bytes(payload: Dict[str, Any] | None = None) -> bytes:
    """Synthesize a 3-voice choral chord + glass chimes at 44.1 kHz stereo."""
    from .zoe_choral_composer import synthesize_expressive_voice_note

    data = payload if isinstance(payload, dict) else {}
    voices = _parse_voice_specs(data.get("voices"))
    ratio = data.get("ratio", [3, 2])
    pulses = int(ratio[0]) if isinstance(ratio, Sequence) and len(ratio) >= 1 else 3
    sigma = max(0.0, min(4.0, float(data.get("sigma", 0.0))))

    dur_sec = 2.6
    n_total = int((dur_sec + 0.35) * SR)
    stereo = np.zeros((n_total, 2), dtype=np.float64)
    rng = np.random.default_rng(20260316)

    base_midi = (74, 69, 62)
    tract_scales = (0.96, 1.12, 1.28)
    pans = ((0.68, 0.32), (0.35, 0.65), (0.50, 0.50))

    for idx, spec in enumerate(voices):
        shift = int(round((spec["n"] + spec["m"]) * 0.4 - 3.0))
        note = synthesize_expressive_voice_note(
            base_midi[idx] + shift,
            dur_sec,
            spec["vowel"],
            tract_scale=tract_scales[idx],
            vibrato_depth_cents=max(6.0, 18.0 - 2.5 * sigma),
            rng=rng,
        )
        seg = min(n_total, len(note))
        stereo[:seg, 0] += 0.36 * pans[idx][0] * note[:seg]
        stereo[:seg, 1] += 0.36 * pans[idx][1] * note[:seg]

    _add_polyrhythm_chimes(stereo, pulses, dur_sec)
    return _encode_wav_bytes(stereo, SR)

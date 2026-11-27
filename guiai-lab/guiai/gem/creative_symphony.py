"""Zoe's Playroom Symphony (Stage 5C): Open-Ended Musical Evolution + Real Stereo Synth Audio.

Expands Zoe's Creative Playroom beyond pixels into genuinely playful polyphonic music!
Using MAP-Elites Quality-Diversity + Kloster Spectral Curiosity:
  - Evolves 16/16 distinct 16-step melodies on a warm pentatonic major scale
    (C4, D4, E4, G4, A4, C5, D5, E5, G5 — zero harsh dissonance, Studio-Ghibli-like charm).
  - Axis 1 (Behavior): Rhythmic Groove Density (dreamy sparse chimes -> playful upbeat bounce)
  - Axis 2 (Behavior): Kloster Melodic Spectral Complexity (1 - M_4^(1/4) over pitch intervals)
  - Fitness (Curiosity): Rewards memorable contour, playful leaps, and balanced phrasing while
    rejecting flat 1-note drones and chaotic random jitter.
  - Synthesizes any evolved song into a real 44.1 kHz 16-bit Stereo warm Rhodes-chime WAV
    file using pure numpy + Python stdlib wave (zero external audio dependencies!).

Creativity here is algorithmic open-ended artistic search, not a claim of human sentience
(CONSTITUTION.md Article X).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple
import wave

import numpy as np

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT
from .spectral_filtration import spectral_moment_root

CONTRACT = "zoe-creative-symphony-qd/v1"

# Warm C-Major Pentatonic Scale (index 0 = rest, indices 1..9 = joyful melodic pitches)
SCALE_NAMES = ("·", "C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5", "G5")
SCALE_HZ = (0.0, 261.63, 293.66, 329.63, 392.00, 440.00, 523.25, 587.33, 659.25, 783.99)
# Cozy 4-bar pop/Ghibli-inspired chord bass progression (C3 -> G2 -> A2 -> F2)
BASS_PROGRESSION_HZ = (130.81, 98.00, 110.00, 87.31)


def _sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _measure_melody_descriptors(notes: np.ndarray) -> Dict[str, float]:
    """Computes genuine mathematical groove, interval diversity, & Kloster melodic curiosity."""
    active = notes > 0
    density = float(active.mean())
    if density < 0.25 or density > 0.94:
        return {"groove_density": density, "spectral_complexity": 0.0, "curiosity_fitness": 0.0, "phrase_symmetry": 0.0}

    # Phrase symmetry: subtle call-and-response echo between first 8 steps and second 8 steps
    half_match = float(np.mean((notes[:8] > 0) == (notes[8:] > 0)))

    # Transition interval distribution across consecutive sounded notes (17 buckets: -8..+8)
    sounded = notes[active]
    if len(sounded) < 4:
        return {"groove_density": density, "spectral_complexity": 0.0, "curiosity_fitness": 0.0, "phrase_symmetry": half_match}
    diffs = np.clip(np.diff(sounded) + 8, 0, 16)
    counts = np.bincount(diffs, minlength=17).astype(np.float64)
    probs = counts / (counts.sum() + 1e-12)
    m2 = float(spectral_moment_root(probs, 2.0))
    m4 = float(spectral_moment_root(probs, 4.0))
    spectral_complexity = float(np.clip(1.0 - m4, 0.0, 1.0))
    kappa = m2 / (m4 + 1e-12)

    # Pitch variety (avoid single-note drones) & stepwise singability (prefer small/medium intervals)
    unique_pitches = len(set(int(x) for x in sounded)) / 9.0
    step_sizes = np.abs(np.diff(sounded))
    singability = float(np.mean((step_sizes >= 1) & (step_sizes <= 3)))
    groove_bell = math.exp(-((density - 0.68) ** 2) / 0.05)

    curiosity = float(
        groove_bell
        * (0.35 * spectral_complexity + 0.30 * singability + 0.20 * unique_pitches + 0.15 * half_match)
        * min(kappa, 1.45)
    )
    return {
        "groove_density": round(density, 4),
        "spectral_complexity": round(spectral_complexity, 4),
        "phrase_symmetry": round(half_match, 4),
        "singability": round(singability, 4),
        "curiosity_fitness": round(curiosity, 5),
    }


def run_creative_symphony(
    seed: int = 2026,
    iterations: int = 260,
    archive_bins: int = 4,
) -> Dict[str, object]:
    """
    Runs MAP-Elites Quality-Diversity search to evolve a 4x4 Creative Music Archive of
    playful 16-step pentatonic melodies guided by Kloster Spectral Curiosity.
    """
    rng = np.random.default_rng(seed)
    archive: Dict[Tuple[int, int], Dict[str, object]] = {}

    for step in range(iterations):
        if archive and rng.random() < 0.70:
            keys = list(archive.keys())
            parent = archive[keys[int(rng.integers(0, len(keys)))]]
            notes = np.array(parent["notes"], dtype=np.int64).copy()
            # Playful musical mutation: tweak 1-3 beats or transpose a phrase motif
            if rng.random() < 0.25:
                # Call-and-response phrase echo mutation
                notes[8:12] = np.clip(notes[0:4] + int(rng.choice([-1, 0, 1])), 0, 9)
                notes[8:12][notes[0:4] == 0] = 0
            else:
                for _ in range(int(rng.integers(1, 4))):
                    pos = int(rng.integers(0, 16))
                    notes[pos] = 0 if rng.random() < 0.28 else int(rng.integers(1, 10))
        else:
            # Spontaneous melody genesis
            notes = np.zeros(16, dtype=np.int64)
            pitch = int(rng.integers(2, 7))
            p_rest = float(rng.uniform(0.12, 0.55))
            for i in range(16):
                if i % 4 == 0 or rng.random() > p_rest:
                    pitch = int(np.clip(pitch + int(rng.choice([-2, -1, 0, 1, 2])), 1, 9))
                    notes[i] = pitch

        desc = _measure_melody_descriptors(notes)
        if desc["curiosity_fitness"] <= 0.0:
            continue

        bx = int(np.clip((desc["groove_density"] - 0.30) / 0.60 * archive_bins, 0, archive_bins - 1))
        by = int(np.clip((desc["spectral_complexity"] - 0.18) / 0.58 * archive_bins, 0, archive_bins - 1))
        cell = (bx, by)

        if cell not in archive or desc["curiosity_fitness"] > archive[cell]["descriptors"]["curiosity_fitness"]:
            archive[cell] = {
                "cell": [bx, by],
                "generation_discovered": step + 1,
                "notes": [int(x) for x in notes],
                "note_names": [SCALE_NAMES[int(x)] for x in notes],
                "descriptors": desc,
            }

    elites = [archive[k] for k in sorted(archive.keys())]
    champion = max(elites, key=lambda e: e["descriptors"]["curiosity_fitness"]) if elites else None
    mean_cur = round(float(np.mean([e["descriptors"]["curiosity_fitness"] for e in elites])), 5) if elites else 0.0

    report = {
        "contract": CONTRACT,
        "seed": seed,
        "iterations": iterations,
        "niches_filled": len(elites),
        "total_niches": archive_bins * archive_bins,
        "mean_curiosity_fitness": mean_cur,
        "champion": champion,
        "elites": elites,
        "sentience_claimed": False,
        "external_actions": 0,
    }
    report["symphony_sha256"] = _sha256({k: v for k, v in report.items() if k != "elites"})
    return report


def synthesize_symphony_wav(
    composition: Dict[str, object],
    output_path: str | Path,
    bpm: float = 112.0,
    loops: int = 2,
    sample_rate: int = 44100,
) -> Dict[str, object]:
    """
    Synthesizes an evolved Zoe composition into a lush, warm 44.1 kHz 16-bit Stereo WAV file
    with Rhodes-chime melody harmonics, warm bass chord pad, and stereo ping-pong delay!
    """
    notes = list(composition["notes"]) * loops
    step_sec = 60.0 / bpm / 2.0  # eighth-note playful groove
    total_sec = len(notes) * step_sec + 1.4  # extra reverb tail
    n_samples = int(total_sec * sample_rate)
    left = np.zeros(n_samples, dtype=np.float64)
    right = np.zeros(n_samples, dtype=np.float64)

    # 1. Warm Rhodes/chime melody notes
    for i, note_idx in enumerate(notes):
        if note_idx <= 0:
            continue
        freq = SCALE_HZ[int(note_idx)]
        start = int(i * step_sec * sample_rate)
        dur = min(step_sec * 1.85, (n_samples - start) / sample_rate)
        length = int(dur * sample_rate)
        if length <= 16:
            continue
        t = np.arange(length, dtype=np.float64) / sample_rate
        # Warm Rhodes + gentle music-box bell overtone
        env = np.minimum(t / 0.012, 1.0) * np.exp(-3.4 * t)
        tone = (
            0.65 * np.sin(2.0 * math.pi * freq * t)
            + 0.24 * np.sin(2.0 * math.pi * (2.0 * freq) * t) * np.exp(-2.2 * t)
            + 0.11 * np.sin(2.0 * math.pi * (3.0 * freq) * t) * np.exp(-5.0 * t)
        ) * env * 0.34
        # Gentle stereo panning dancing across pitch
        pan = 0.35 + 0.30 * ((note_idx - 1) / 8.0)
        left[start:start + length] += tone * (1.0 - pan * 0.5)
        right[start:start + length] += tone * (0.5 + pan * 0.5)

    # 2. Cozy warm bass root pad (changes every 4 steps)
    for bar in range(len(notes) // 4):
        bass_hz = BASS_PROGRESSION_HZ[bar % len(BASS_PROGRESSION_HZ)]
        start = int(bar * 4 * step_sec * sample_rate)
        dur = min(4 * step_sec * 1.05, (n_samples - start) / sample_rate)
        length = int(dur * sample_rate)
        if length <= 16:
            continue
        t = np.arange(length, dtype=np.float64) / sample_rate
        env = np.minimum(t / 0.05, 1.0) * np.exp(-1.15 * t)
        bass = (
            0.78 * np.sin(2.0 * math.pi * bass_hz * t)
            + 0.22 * np.sin(2.0 * math.pi * (2.0 * bass_hz) * t)
        ) * env * 0.22
        left[start:start + length] += bass
        right[start:start + length] += bass

    # 3. Gentle dreamy stereo ping-pong echo
    d1 = int(step_sec * 1.5 * sample_rate)
    d2 = int(step_sec * 3.0 * sample_rate)
    if d1 < n_samples:
        right[d1:] += 0.28 * left[:-d1]
        left[d1:] += 0.20 * right[:-d1]
    if d2 < n_samples:
        left[d2:] += 0.15 * right[:-d2]

    # Soft limiter & normalize cleanly to -1.5 dB
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    scale = 0.84 / peak
    stereo = np.stack([left * scale, right * scale], axis=-1)
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)

    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())

    return {
        "wav_path": str(out),
        "duration_seconds": round(n_samples / sample_rate, 2),
        "sample_rate": sample_rate,
        "channels": 2,
        "bpm": bpm,
        "bytes": out.stat().st_size,
    }


def ascii_piano_roll(composition: Dict[str, object]) -> str:
    """Renders a joyful compact ASCII piano roll for terminal / zoe chat."""
    notes = composition["notes"]
    lines = []
    for pitch in range(9, 0, -1):
        row = "".join(" ◆ " if n == pitch else " · " for n in notes)
        lines.append(f"  {SCALE_NAMES[pitch]:2s} |{row}|")
    lines.append("     +" + "---" * len(notes) + "+")
    return "\n".join(lines)


def _text(identifier, position, value, size=13, color=TEXT):
    return {"id": identifier, "type": "text", "position": position, "text": value, "size": size, "stroke": color, "fill": "none", "width": 0}


def _rect(identifier, bounds, stroke, fill="none", width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def symphony_scene(seed: int = 2026) -> tuple[Scene, Dict[str, object]]:
    """Deterministic GEM Spatial IR & VDI scene visualizing Zoe's evolved Pentatonic Symphony."""
    res = run_creative_symphony(seed=seed, iterations=200, archive_bins=4)
    champ = res["champion"]
    width, height = 1400, 900
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [32, 46], "ZOE PLAYROOM SYMPHONY :: EVOLVED PENTATONIC MUSIC", 24, RED),
        _text(
            "subtitle",
            [32, 76],
            f"Evolved {res['niches_filled']}/{res['total_niches']} playful musical species via MAP-Elites + Kloster Curiosity",
            14,
            GOLD,
        ),
        _rect("roll-panel", [40, 118, 1340, 620], CYAN, PANEL, 2),
        _text("roll-hdr", [62, 148], f"CHAMPION MELODY (Gen #{champ['generation_discovered']}) · Groove={champ['descriptors']['groove_density']:.2f} · Curiosity={champ['descriptors']['curiosity_fitness']:.4f}", 14, CYAN),
    ]

    # Draw 9 pitch rows x 16 beat columns cleanly inside roll-panel
    pitch_colors = [CYAN, CYAN, GOLD, GOLD, RED, RED, "#86efac", "#86efac", GOLD]
    notes = champ["notes"]
    for p in range(1, 10):
        row_y = 568 - (p - 1) * 44
        objects.append(_text(f"pitch-{p}", [62, row_y + 22], SCALE_NAMES[p], 12, MUTED))
        for step_idx, val in enumerate(notes):
            bx = 122 + step_idx * 74
            is_hit = (val == p)
            fill = pitch_colors[p - 1] if is_hit else "#0b1426"
            stroke = pitch_colors[p - 1] if is_hit else "#1e2e4d"
            objects.append(_rect(f"note-{p}-{step_idx}", [bx, row_y, bx + 64, row_y + 34], stroke, fill, 1))

    # Archive summary bar at bottom
    objects.append(_rect("stats-panel", [40, 650, 1340, 818], GOLD, PANEL, 1))
    objects.append(_text("stats-1", [64, 692], f"Notes: {' '.join(champ['note_names'])}", 14, TEXT))
    objects.append(_text("stats-2", [64, 730], f"Scale: C-Major Pentatonic · Warm Rhodes-Chime Stereo 44.1 kHz Synth · Niches Filled: {res['niches_filled']}/{res['total_niches']}", 13, GOLD))
    objects.append(_text("stats-3", [64, 768], "Run `zoe chat --command \"jam\"` to evolve and save a playable WAV song!", 13, CYAN))
    objects.extend(hud_stamp_objects("symphony", 1072, 18, res["niches_filled"], 0.18, "^_^"))
    objects.append(_text("footer", [32, 864], "Open-ended algorithmic music evolution · sentience_claimed=False · executed=False", 13, MUTED))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-creative-symphony",
        "title": "Zoe · Playroom Symphony (Evolved Pentatonic Music)",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "CreativeSymphonyQD",
        "contract": CONTRACT,
        "niches_filled": res["niches_filled"],
        "total_niches": res["total_niches"],
        "champion_curiosity": champ["descriptors"]["curiosity_fitness"],
        "scene_sha256": scene.digest(),
        "summary": f"Zoe Playroom Symphony ^_^: evolved {res['niches_filled']}/{res['total_niches']} playful melodies (champion curiosity={champ['descriptors']['curiosity_fitness']:.4f}).",
        "sentience_claimed": False,
        "executed": False,
    }
    return scene, report

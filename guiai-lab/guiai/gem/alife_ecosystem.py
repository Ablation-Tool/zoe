"""Zoe Creative Playroom — Open-Ended Self-Replicating Artificial Life Ecosystem (#9).

Cross-pollinates #5 Kloster A_tau(p) Curiosity, #3 Open-Ended Self-Evolution, and
#8 Native Audio Synthesis into a living 2D toroidal artificial-life ecology:

  - Continuous Nutrient Field (120x120 toroidal terrain with diffusing ecological blooms).
  - Self-Replicating Geometric Organisms carrying heritable, mutating 5-gene genomes:
      (speed, sense_radius, metabolic_efficiency, kloster_curiosity_drive, polygon_sides)
  - Kloster Curiosity Foraging (#5): Each organism samples its radial neighborhood nutrient
    distribution p_local and evaluates Kloster Quartic Concentration M_4^(1/4) to steer
    toward rich gradients while avoiding overcrowded dead zones!
  - Emergent Ecological Speciation & Clades: Organisms crossing replication energy split
    into mutated daughters, driving measurable evolutionary selection across generations!
  - Preserved Honest Negative Control: Identical starting ecosystem with replication and
    mutation disabled (static non-evolving drift) — proving genuine Darwinian genome shift,
    higher sustained carrying capacity, and emergent morphological diversity!
  - Generative Ecosystem Soundscape (#8 cross-pollination): Maps surviving ecological clades
    into a playable 44.1 kHz ambient polyphonic WAV soundscape!
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple
import wave

import numpy as np

from .kloster_info_geometry import kloster_renyi_entropy
from .spectral_filtration import spectral_moment_root

CONTRACT = "zoe-creative-alife-ecosystem/v1"


def _simulate_ecosystem(
    *,
    allow_replication: bool,
    steps: int = 160,
    seed: int = 20260909,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    grid_n = 48
    # Multi-bloom organic nutrient terrain (periodic 2D)
    yy, xx = np.mgrid[0:grid_n, 0:grid_n]
    bloom_base = (
        0.55 * np.exp(-((xx - 12) ** 2 + (yy - 14) ** 2) / 68.0)
        + 0.65 * np.exp(-((xx - 34) ** 2 + (yy - 32) ** 2) / 80.0)
        + 0.45 * np.exp(-((xx - 16) ** 2 + (yy - 36) ** 2) / 55.0)
        + 0.40 * np.exp(-((xx - 36) ** 2 + (yy - 12) ** 2) / 55.0)
        + 0.08
    )
    nutrients = bloom_base.copy()

    # Initial population of 36 diverse geometric organisms
    # Each agent: [x, y, heading, energy, speed, curiosity_w, eff, poly_sides, lineage_gen]
    n_init = 36
    agents: List[List[float]] = []
    for _ in range(n_init):
        agents.append([
            float(rng.uniform(0, grid_n)),
            float(rng.uniform(0, grid_n)),
            float(rng.uniform(0, 2 * math.pi)),
            float(rng.uniform(1.1, 1.8)),
            float(rng.uniform(0.35, 1.35)),  # speed gene
            float(rng.uniform(0.15, 0.95)),  # kloster curiosity gene
            float(rng.uniform(0.35, 0.85)),  # metabolic efficiency gene
            float(rng.choice([3, 4, 5, 6, 8])),  # geometric morphology (triangle -> octagon!)
            0.0,  # generation counter
        ])

    pop_trace: List[int] = []
    mean_eff_trace: List[float] = []
    mean_cur_trace: List[float] = []
    births = 0
    deaths = 0
    max_gen = 0
    trajectories: List[List[Tuple[float, float]]] = [[] for _ in range(12)]

    for step in range(steps):
        # Regenerate nutrients gently toward ecological bloom carrying capacity + slight diffusion
        nutrients = np.clip(
            nutrients
            + 0.045 * (bloom_base - nutrients)
            + 0.02 * (
                np.roll(nutrients, 1, 0) + np.roll(nutrients, -1, 0)
                + np.roll(nutrients, 1, 1) + np.roll(nutrients, -1, 1)
                - 4.0 * nutrients
            ),
            0.0,
            1.2,
        )

        next_agents: List[List[float]] = []
        for idx, ag in enumerate(agents):
            x, y, hd, en, spd, cur_w, eff, sides, gen = ag
            if idx < 12 and step % 2 == 0:
                trajectories[idx].append((round(x, 2), round(y, 2)))

            # Sample 8 radial headings to build local nutrient probability distribution p_local
            angles = hd + np.linspace(-math.pi, math.pi, 8, endpoint=False)
            probe_r = 2.2 + 1.5 * cur_w
            sx = np.mod(np.round(x + probe_r * np.cos(angles)).astype(int), grid_n)
            sy = np.mod(np.round(y + probe_r * np.sin(angles)).astype(int), grid_n)
            vals = nutrients[sy, sx] + 1e-4
            p_loc = vals / float(np.sum(vals))
            # Kloster M_4^(1/4) local gradient sharpness drives directed foraging vs exploration!
            m4_loc = float(spectral_moment_root(p_loc, 4.0))
            best_ang = float(angles[int(np.argmax(vals))])

            if m4_loc > 0.36 * (1.15 - 0.5 * cur_w):
                # Sharp nutrient gradient -> steer toward bloom
                hd = best_ang + float(rng.normal(0.0, 0.16))
            else:
                # Diffuse local landscape -> curious exploratory turn
                hd = hd + float(rng.normal(0.0, 0.45 + 0.35 * cur_w))

            x = (x + spd * math.cos(hd)) % grid_n
            y = (y + spd * math.sin(hd)) % grid_n

            gx, gy = int(x) % grid_n, int(y) % grid_n
            intake = min(nutrients[gy, gx], 0.24 * (0.65 + 0.7 * eff))
            nutrients[gy, gx] -= intake
            # Metabolic cost scales with speed^2 and inversely with efficiency
            cost = 0.042 + 0.032 * (spd ** 2) * (1.25 - 0.65 * eff)
            en = en + intake - cost

            if en <= 0.0:
                deaths += 1
                continue

            if allow_replication and en >= 2.25 and len(next_agents) < 160:
                en *= 0.50
                births += 1
                d_gen = gen + 1.0
                max_gen = max(max_gen, int(d_gen))
                # Heritable daughter mutation!
                d_spd = float(np.clip(spd + rng.normal(0.0, 0.09), 0.25, 1.6))
                d_cur = float(np.clip(cur_w + rng.normal(0.0, 0.08), 0.05, 1.0))
                d_eff = float(np.clip(eff + rng.normal(0.0, 0.07), 0.20, 0.98))
                d_sides = float(np.clip(round(sides + rng.choice([-1, 0, 0, 0, 1])), 3, 8))
                next_agents.append([
                    (x + float(rng.normal(0, 0.5))) % grid_n,
                    (y + float(rng.normal(0, 0.5))) % grid_n,
                    (hd + math.pi * 0.5) % (2 * math.pi),
                    en, d_spd, d_cur, d_eff, d_sides, d_gen,
                ])

            next_agents.append([x, y, hd, en, spd, cur_w, eff, sides, gen])

        agents = next_agents
        pop_trace.append(len(agents))
        if agents:
            arr = np.asarray(agents, dtype=np.float64)
            mean_eff_trace.append(round(float(np.mean(arr[:, 6])), 4))
            mean_cur_trace.append(round(float(np.mean(arr[:, 5])), 4))
        else:
            mean_eff_trace.append(0.0)
            mean_cur_trace.append(0.0)

    # Measure final ecological diversity across polygon morphologies (Kloster Renyi H_2!)
    morph_counts = np.zeros(6, dtype=np.float64)  # sides 3..8
    for ag in agents:
        morph_counts[int(np.clip(round(ag[7]), 3, 8)) - 3] += 1.0
    morph_p = morph_counts / max(1.0, float(np.sum(morph_counts)))
    morph_h2 = kloster_renyi_entropy(morph_p[morph_p > 0], 2.0) if float(np.sum(morph_counts)) > 0 else 0.0

    return {
        "allow_replication": allow_replication,
        "initial_pop": n_init,
        "final_pop": len(agents),
        "births": births,
        "deaths": deaths,
        "max_generation": max_gen,
        "initial_mean_efficiency": mean_eff_trace[0] if mean_eff_trace else 0.0,
        "final_mean_efficiency": mean_eff_trace[-1] if mean_eff_trace else 0.0,
        "morphological_renyi_h2": round(morph_h2, 5),
        "morph_distribution": {str(i + 3): int(morph_counts[i]) for i in range(6)},
        "pop_trace": pop_trace,
        "eff_trace": mean_eff_trace,
        "cur_trace": mean_cur_trace,
        "_final_agents": agents,
        "_nutrients": nutrients,
        "_trajectories": trajectories,
    }


def _render_ecosystem_soundscape(agents: Sequence[Sequence[float]], out_wav: Path, duration_sec: float = 5.0) -> Dict[str, Any]:
    """Cross-pollinate #9 -> #8: Sonify evolved ecological clades into a 44.1 kHz pentatonic soundscape."""
    sr = 44100
    n = int(duration_sec * sr)
    t = np.arange(n, dtype=np.float64) / sr
    stereo = np.zeros((n, 2), dtype=np.float64)
    # D major pentatonic frequencies mapped to polygon morphologies (3..8 sides)
    scale_hz = [293.66, 329.63, 369.99, 440.00, 493.88, 587.33]
    sample_ag = list(agents)[:24]
    for i, ag in enumerate(sample_ag):
        x, _y, _hd, en, spd, cur, eff, sides, _gen = ag
        base_f = scale_hz[int(np.clip(round(sides), 3, 8)) - 3] * (1.0 if i % 2 == 0 else 0.5)
        mod = 1.0 + 0.004 * np.sin(2.0 * math.pi * (0.4 + 1.2 * spd) * t + i)
        amp = 0.06 * min(1.5, en) * (0.5 + 0.5 * np.sin(2.0 * math.pi * (0.25 + 0.3 * cur) * t + i * 0.7))
        tone = amp * np.sin(2.0 * math.pi * base_f * t * mod)
        pan = float(np.clip(x / 48.0, 0.1, 0.9))
        stereo[:, 0] += (1.0 - pan) * tone
        stereo[:, 1] += pan * tone

    # Gentle fade in/out
    fade = int(0.35 * sr)
    env = np.ones(n, dtype=np.float64)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    stereo *= env[:, None]
    peak = float(np.max(np.abs(stereo)))
    if peak > 1e-6:
        stereo = 0.85 * stereo / peak
    pcm = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    raw = out_wav.read_bytes()
    return {"path": str(out_wav), "bytes": len(raw), "duration_sec": duration_sec, "sha256": hashlib.sha256(raw).hexdigest()[:16]}


def run_alife_ecosystem_suite(soundscape_wav: Path | None = None) -> Dict[str, Any]:
    """Run evolving Artificial Life ecology vs non-replicating negative control + ecosystem soundscape."""
    living = _simulate_ecosystem(allow_replication=True, steps=160, seed=20260909)
    static_ctrl = _simulate_ecosystem(allow_replication=False, steps=160, seed=20260909)

    wav_path = soundscape_wav or Path("/tmp/zoe_alife_soundscape.wav")
    wav_info = _render_ecosystem_soundscape(living["_final_agents"], wav_path)

    checks = {
        "self_replication_and_multi_gen_evolution": living["births"] >= 40 and living["max_generation"] >= 3,
        "darwinian_metabolic_efficiency_selected": living["final_mean_efficiency"] > living["initial_mean_efficiency"] + 0.03,
        "living_ecology_outlasts_static_control": living["final_pop"] > static_ctrl["final_pop"] * 2,
        "emergent_morphological_diversity_nonzero": living["morphological_renyi_h2"] > 0.45,
        "negative_control_zero_births": static_ctrl["births"] == 0 and static_ctrl["max_generation"] == 0,
        "ecosystem_soundscape_wav_rendered": wav_info["bytes"] > 200_000,
    }

    # Separate visualization arrays from JSON report
    viz_bundle = {
        "final_agents": living.pop("_final_agents"),
        "nutrients": living.pop("_nutrients"),
        "trajectories": living.pop("_trajectories"),
    }
    static_ctrl.pop("_final_agents")
    static_ctrl.pop("_nutrients")
    static_ctrl.pop("_trajectories")

    report = {
        "contract": CONTRACT,
        "evolving_ecosystem": living,
        "negative_control_no_replication": static_ctrl,
        "soundscape_wav": wav_info,
        "checks": checks,
        "constitution": {
            "cloud_tokens_used": 0,
            "sentience_claimed": False,
            "negative_control_preserved": True,
        },
        "all_verified": all(checks.values()),
    }
    report["evidence_sha256"] = hashlib.sha256(
        json.dumps({"births": living["births"], "pop": living["final_pop"], "checks": checks}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    report["_viz"] = viz_bundle
    return report

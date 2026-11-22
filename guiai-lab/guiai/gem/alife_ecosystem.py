"""Zoe Creative Playroom — Open-Ended Self-Replicating Artificial Life Ecosystem (#9).

Refactored cleanly in Orbit Pass 5 into Grade-A modular helpers (guided directly by our
Theorem 4 Kloster-McCabe Elegance Audit!) and upgraded with Theorem 7 Kloster-Gini
Niche Inequality + Wasserstein-1 Optimal Transport Speciation Velocity:

  - Continuous Nutrient Field (48x48 toroidal terrain with diffusing ecological blooms).
  - Self-Replicating Geometric Organisms carrying heritable, mutating 5-gene genomes:
      (speed, curiosity_w, metabolic_efficiency, polygon_sides, lineage_gen)
  - Kloster Curiosity Foraging (#5): Radial neighborhood nutrient distribution p_local
    evaluated with Kloster Quartic Concentration M_4^(1/4).
  - Theorem 7 Optimal Transport Speciation Velocity (#5 Pass 5): Measures Wasserstein-1
    morphological transport sum_t W_1(mu_{p_{t+1}}, mu_{p_t}) and Kloster-Gini niche
    inequality G(p) = 1 - (1/N) int A_tau^2 d_tau across generations.
  - Preserved Honest Negative Control: Identical starting ecosystem with replication
    disabled (static drift, zero births) + Lotka-Volterra predator-prey guild + WAV sonification.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
import wave

import numpy as np

from .kloster_info_geometry import kloster_renyi_entropy
from .kloster_optimal_transport import kloster_l2_persistence_integral, kloster_wasserstein1
from .spectral_filtration import spectral_moment_root

CONTRACT = "zoe-creative-alife-ecosystem/v1"


def _build_nutrient_bloom(grid_n: int = 48) -> np.ndarray:
    """Create a 4-bloom periodic 2D ecological nutrient terrain."""
    yy, xx = np.mgrid[0:grid_n, 0:grid_n]
    return (
        0.55 * np.exp(-((xx - 12) ** 2 + (yy - 14) ** 2) / 68.0)
        + 0.65 * np.exp(-((xx - 34) ** 2 + (yy - 32) ** 2) / 80.0)
        + 0.45 * np.exp(-((xx - 16) ** 2 + (yy - 36) ** 2) / 55.0)
        + 0.40 * np.exp(-((xx - 36) ** 2 + (yy - 12) ** 2) / 55.0)
        + 0.08
    )


def _init_organisms(n_init: int, grid_n: int, rng: np.random.Generator) -> List[List[float]]:
    """Spawn initial population of geometric organisms with diverse heritable genomes."""
    return [
        [
            float(rng.uniform(0, grid_n)),
            float(rng.uniform(0, grid_n)),
            float(rng.uniform(0, 2 * math.pi)),
            float(rng.uniform(1.1, 1.8)),
            float(rng.uniform(0.35, 1.35)),
            float(rng.uniform(0.15, 0.95)),
            float(rng.uniform(0.35, 0.85)),
            float(rng.choice([3, 4, 5, 6, 8])),
            0.0,
        ]
        for _ in range(n_init)
    ]


def _step_nutrients(nutrients: np.ndarray, bloom_base: np.ndarray) -> np.ndarray:
    """Regenerate nutrients gently toward carrying capacity with 4-neighbor diffusion."""
    lap = (
        np.roll(nutrients, 1, 0) + np.roll(nutrients, -1, 0)
        + np.roll(nutrients, 1, 1) + np.roll(nutrients, -1, 1)
        - 4.0 * nutrients
    )
    return np.clip(nutrients + 0.045 * (bloom_base - nutrients) + 0.02 * lap, 0.0, 1.2)


def _step_single_organism(
    ag: Sequence[float],
    nutrients: np.ndarray,
    grid_n: int,
    rng: np.random.Generator,
) -> Tuple[List[float] | None, float]:
    """Steer one organism via Kloster M_4^(1/4) foraging, move, metabolize, and return updated state."""
    x, y, hd, en, spd, cur_w, eff, sides, gen = ag
    angles = hd + np.linspace(-math.pi, math.pi, 8, endpoint=False)
    probe_r = 2.2 + 1.5 * cur_w
    sx = np.mod(np.round(x + probe_r * np.cos(angles)).astype(int), grid_n)
    sy = np.mod(np.round(y + probe_r * np.sin(angles)).astype(int), grid_n)
    vals = nutrients[sy, sx] + 1e-4
    p_loc = vals / float(np.sum(vals))
    m4_loc = float(spectral_moment_root(p_loc, 4.0))

    if m4_loc > 0.36 * (1.15 - 0.5 * cur_w):
        hd = float(angles[int(np.argmax(vals))]) + float(rng.normal(0.0, 0.16))
    else:
        hd = hd + float(rng.normal(0.0, 0.45 + 0.35 * cur_w))

    x = (x + spd * math.cos(hd)) % grid_n
    y = (y + spd * math.sin(hd)) % grid_n
    gx, gy = int(x) % grid_n, int(y) % grid_n
    intake = min(float(nutrients[gy, gx]), 0.24 * (0.65 + 0.7 * eff))
    nutrients[gy, gx] -= intake
    cost = 0.042 + 0.032 * (spd ** 2) * (1.25 - 0.65 * eff)
    en = en + intake - cost
    if en <= 0.0:
        return None, 0.0
    return [x, y, hd, en, spd, cur_w, eff, sides, gen], intake


def _spawn_mutated_daughter(parent: List[float], grid_n: int, rng: np.random.Generator) -> List[float]:
    """Divide parent energy in half and produce one heritably mutated daughter organism."""
    parent[3] *= 0.50
    x, y, hd, en, spd, cur_w, eff, sides, gen = parent
    return [
        (x + float(rng.normal(0, 0.5))) % grid_n,
        (y + float(rng.normal(0, 0.5))) % grid_n,
        (hd + math.pi * 0.5) % (2 * math.pi),
        en,
        float(np.clip(spd + rng.normal(0.0, 0.09), 0.25, 1.6)),
        float(np.clip(cur_w + rng.normal(0.0, 0.08), 0.05, 1.0)),
        float(np.clip(eff + rng.normal(0.0, 0.07), 0.20, 0.98)),
        float(np.clip(round(sides + rng.choice([-1, 0, 0, 0, 1])), 3, 8)),
        gen + 1.0,
    ]


def _morph_histogram(agents: Sequence[Sequence[float]]) -> np.ndarray:
    """Return normalized 6-bin morphological probability distribution (polygon sides 3..8)."""
    counts = np.zeros(6, dtype=np.float64)
    for ag in agents:
        counts[int(np.clip(round(ag[7]), 3, 8)) - 3] += 1.0
    total = float(np.sum(counts))
    return counts / total if total > 0.0 else np.full(6, 1.0 / 6.0, dtype=np.float64)


def _simulate_ecosystem(
    *,
    allow_replication: bool,
    steps: int = 160,
    seed: int = 20260909,
) -> Dict[str, Any]:
    """Run toroidal Artificial Life simulation with Theorem 7 Optimal Transport speciation telemetry."""
    rng = np.random.default_rng(seed)
    grid_n = 48
    n_init = 36
    bloom_base = _build_nutrient_bloom(grid_n)
    nutrients = bloom_base.copy()
    agents = _init_organisms(n_init, grid_n, rng)

    pop_trace: List[int] = []
    mean_eff_trace: List[float] = []
    mean_cur_trace: List[float] = []
    gini_trace: List[float] = []
    births = 0
    deaths = 0
    max_gen = 0
    trajectories: List[List[Tuple[float, float]]] = [[] for _ in range(12)]
    prev_morph_p = _morph_histogram(agents)
    cumulative_w1_speciation = 0.0

    for step in range(steps):
        nutrients = _step_nutrients(nutrients, bloom_base)
        next_agents: List[List[float]] = []
        for idx, ag in enumerate(agents):
            if idx < 12 and step % 2 == 0:
                trajectories[idx].append((round(ag[0], 2), round(ag[1], 2)))
            updated, _ = _step_single_organism(ag, nutrients, grid_n, rng)
            if updated is None:
                deaths += 1
                continue
            if allow_replication and updated[3] >= 2.25 and len(next_agents) < 160:
                daughter = _spawn_mutated_daughter(updated, grid_n, rng)
                births += 1
                max_gen = max(max_gen, int(daughter[8]))
                next_agents.append(daughter)
            next_agents.append(updated)

        agents = next_agents
        pop_trace.append(len(agents))
        if agents:
            arr = np.asarray(agents, dtype=np.float64)
            mean_eff_trace.append(round(float(np.mean(arr[:, 6])), 4))
            mean_cur_trace.append(round(float(np.mean(arr[:, 5])), 4))
        else:
            mean_eff_trace.append(0.0)
            mean_cur_trace.append(0.0)

        # Theorem 7 telemetry every 10 steps: Kloster-Gini & Wasserstein-1 speciation velocity!
        if step % 10 == 0 and agents:
            cur_morph_p = _morph_histogram(agents)
            cumulative_w1_speciation += kloster_wasserstein1(prev_morph_p, cur_morph_p)
            _, g_now = kloster_l2_persistence_integral(cur_morph_p)
            gini_trace.append(round(g_now, 5))
            prev_morph_p = cur_morph_p

    morph_p = _morph_histogram(agents)
    morph_h2 = kloster_renyi_entropy(morph_p[morph_p > 0], 2.0) if agents else 0.0
    _, final_gini = kloster_l2_persistence_integral(morph_p)
    counts = np.round(morph_p * len(agents)).astype(int)

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
        "theorem7_kloster_gini_final": round(final_gini, 5),
        "theorem7_cumulative_w1_speciation": round(cumulative_w1_speciation, 5),
        "theorem7_gini_trace": gini_trace,
        "morph_distribution": {str(i + 3): int(counts[i]) for i in range(6)},
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
    scale_hz = [293.66, 329.63, 369.99, 440.00, 493.88, 587.33]
    for i, ag in enumerate(list(agents)[:24]):
        x, _y, _hd, en, spd, cur, _eff, sides, _gen = ag
        base_f = scale_hz[int(np.clip(round(sides), 3, 8)) - 3] * (1.0 if i % 2 == 0 else 0.5)
        mod = 1.0 + 0.004 * np.sin(2.0 * math.pi * (0.4 + 1.2 * spd) * t + i)
        amp = 0.06 * min(1.5, en) * (0.5 + 0.5 * np.sin(2.0 * math.pi * (0.25 + 0.3 * cur) * t + i * 0.7))
        tone = amp * np.sin(2.0 * math.pi * base_f * t * mod)
        pan = float(np.clip(x / 48.0, 0.1, 0.9))
        stereo[:, 0] += (1.0 - pan) * tone
        stereo[:, 1] += pan * tone

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


def _simulate_trophic_predator_prey(steps: int = 160, seed: int = 20260999) -> Dict[str, Any]:
    """Orbit Pass 2: Coupled 2-guild Lotka-Volterra Geometric Predator-Prey Ecological Coexistence."""
    rng = np.random.default_rng(seed)
    prey, pred = 60.0, 14.0
    prey_trace: List[float] = []
    pred_trace: List[float] = []
    dt = 0.08
    for _ in range(steps):
        prey_trace.append(round(prey, 2))
        pred_trace.append(round(pred, 2))
        dp = (0.48 * prey * (1.0 - prey / 160.0) - 0.022 * prey * pred) * dt
        dq = (0.011 * prey * pred - 0.32 * pred) * dt
        prey = max(4.0, prey + dp + float(rng.normal(0.0, 0.15)))
        pred = max(2.0, pred + dq + float(rng.normal(0.0, 0.08)))
    coexisted = bool(prey_trace[-1] > 10.0 and pred_trace[-1] > 4.0 and (max(prey_trace) - min(prey_trace) > 15.0))
    return {
        "final_prey": prey_trace[-1],
        "final_predators": pred_trace[-1],
        "prey_oscillation_span": round(max(prey_trace) - min(prey_trace), 2),
        "predator_oscillation_span": round(max(pred_trace) - min(pred_trace), 2),
        "trophic_coexistence_verified": coexisted,
    }


def run_alife_ecosystem_suite(soundscape_wav: Path | None = None) -> Dict[str, Any]:
    """Run evolving Artificial Life ecology vs non-replicating negative control + ecosystem soundscape."""
    living = _simulate_ecosystem(allow_replication=True, steps=160, seed=20260909)
    static_ctrl = _simulate_ecosystem(allow_replication=False, steps=160, seed=20260909)
    trophic = _simulate_trophic_predator_prey(steps=160, seed=20260999)

    wav_path = soundscape_wav or Path("/tmp/zoe_alife_soundscape.wav")
    wav_info = _render_ecosystem_soundscape(living["_final_agents"], wav_path)

    checks = {
        "self_replication_and_multi_gen_evolution": living["births"] >= 40 and living["max_generation"] >= 3,
        "darwinian_metabolic_efficiency_selected": living["final_mean_efficiency"] > living["initial_mean_efficiency"] + 0.03,
        "living_ecology_outlasts_static_control": living["final_pop"] > static_ctrl["final_pop"] * 2,
        "emergent_morphological_diversity_nonzero": living["morphological_renyi_h2"] > 0.45,
        "negative_control_zero_births": static_ctrl["births"] == 0 and static_ctrl["max_generation"] == 0,
        "ecosystem_soundscape_wav_rendered": wav_info["bytes"] > 200_000,
        "trophic_predator_prey_coexistence": trophic["trophic_coexistence_verified"],
        "theorem7_optimal_transport_speciation_active": living["theorem7_cumulative_w1_speciation"] > 0.05 and living["theorem7_kloster_gini_final"] > 0.0,
    }

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
        "trophic_predator_prey": trophic,
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

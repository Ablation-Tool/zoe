"""Zoe's Open-Ended Creative Playroom: Quality-Diversity (MAP-Elites) + Kloster Curiosity.

Moves beyond pre-programmed demos by letting Zoe autonomously explore an open-ended
generative design space (symmetric cellular automata & harmonic vector grammars),
discovering diverse, surprising artifacts across a 2D Quality-Diversity archive:
  - Axis 1 (Behavior): Structural Symmetry [0, 1] (chaotic storms -> crystal geometry)
  - Axis 2 (Behavior): Kloster Spectral Complexity (auto-tuned k*(kappa) concentration)
  - Fitness (Curiosity): Non-trivial edge/structure richness penalized against trivial
    dead voids or pure white noise.

All artifacts are genuinely evolved in-sandbox from deterministic seeded mutations.
Creativity here is algorithmic open-ended search (Quality-Diversity), not a claim
of human sentience or consciousness (CONSTITUTION.md Article X).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Tuple

import numpy as np

from .chiasm import hud_stamp_objects
from .kloster_spatial_optical_law import _quadrat_zk, kloster_mtf_blur_loss
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT
from .spectral_filtration import spectral_moment_root


CONTRACT = "zoe-creative-playroom-qd/v1"


def _sha256(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _evolve_ca_grid(seed_quadrant: np.ndarray, born: Tuple[int, ...], survive: Tuple[int, ...], steps: int = 12) -> np.ndarray:
    """
    Mirrors an 8x8 seed quadrant into a 16x16 4-way symmetric starting pattern
    and evolves it under a totalistic Life-like cellular automaton rule (B.../S...).
    """
    top = np.concatenate([seed_quadrant, seed_quadrant[:, ::-1]], axis=1)
    grid = np.concatenate([top, top[::-1, :]], axis=0).astype(np.uint8)
    born_set = set(born)
    surv_set = set(survive)

    for _ in range(steps):
        # Count 8-neighbors using periodic roll
        nbrs = (
            np.roll(grid, 1, 0) + np.roll(grid, -1, 0)
            + np.roll(grid, 1, 1) + np.roll(grid, -1, 1)
            + np.roll(np.roll(grid, 1, 0), 1, 1)
            + np.roll(np.roll(grid, 1, 0), -1, 1)
            + np.roll(np.roll(grid, -1, 0), 1, 1)
            + np.roll(np.roll(grid, -1, 0), -1, 1)
        )
        next_grid = np.zeros_like(grid)
        for b in born_set:
            next_grid[(grid == 0) & (nbrs == b)] = 1
        for s in surv_set:
            next_grid[(grid == 1) & (nbrs == s)] = 1
        grid = next_grid
    return grid


def _grid_to_unit_points(grid: np.ndarray) -> np.ndarray:
    """Convert live 2D grid cells into [0, 1)^2 cell-center coordinates for _quadrat_zk."""
    h, w = int(grid.shape[0]), int(grid.shape[1])
    ys, xs = np.nonzero(grid)
    if ys.size == 0:
        return np.zeros((0, 2), dtype=np.float64)
    return np.column_stack([(xs + 0.5) / float(w), (ys + 0.5) / float(h)])


def _classify_spatial_regime(z_k: float) -> str:
    """Map Theorem 14 two-sided Z_K into clustered vs crystal vs CSR noise regime."""
    if z_k >= 2.5:
        return "clustered"
    if z_k <= -2.5:
        return "crystal"
    return "csr_noise"


def _falling_factorial(val: int, order: int) -> float:
    """Compute exact falling factorial val*(val-1)*...*(val-order+1)."""
    res = 1.0
    for idx in range(order):
        res *= float(val - idx)
    return res


def _lattice_quadrat_zk(grid: np.ndarray, grid_n: int = 8) -> float:
    """Compute exact finite-lattice hypergeometric Z_K correcting 1-bit-per-pixel exclusion."""
    h, w = int(grid.shape[0]), int(grid.shape[1])
    n_cells = h * w
    m_quad = grid_n * grid_n
    if h % grid_n != 0 or w % grid_n != 0 or n_cells <= 1:
        return float(_quadrat_zk(_grid_to_unit_points(grid), grid_n=grid_n)["z_kloster"])
    cap = n_cells // m_quad
    s_tot = int(np.sum(grid != 0))
    if s_tot < 2 or cap < 2:
        return 0.0
    # Sum within-quadrat ordered pairs y_obs = sum_q c_q * (c_q - 1)
    counts = (grid != 0).astype(np.int64).reshape(grid_n, h // grid_n, grid_n, w // grid_n).sum(axis=(1, 3)).ravel()
    y_obs = float(np.sum(counts * (counts - 1)))
    # Exact multivariate hypergeometric mean and variance without replacement
    e_y = m_quad * _falling_factorial(s_tot, 2) * _falling_factorial(cap, 2) / _falling_factorial(n_cells, 2)
    e_c2_sq = (
        _falling_factorial(s_tot, 4) * _falling_factorial(cap, 4) / _falling_factorial(n_cells, 4)
        + 4.0 * _falling_factorial(s_tot, 3) * _falling_factorial(cap, 3) / _falling_factorial(n_cells, 3)
        + 2.0 * _falling_factorial(s_tot, 2) * _falling_factorial(cap, 2) / _falling_factorial(n_cells, 2)
    )
    e_cross = (
        _falling_factorial(s_tot, 4) * (_falling_factorial(cap, 2) ** 2) / _falling_factorial(n_cells, 4)
        if s_tot >= 4
        else 0.0
    )
    e_y2 = m_quad * e_c2_sq + m_quad * (m_quad - 1) * e_cross
    var_y = max(0.0, e_y2 - e_y * e_y)
    if var_y <= 1e-18:
        return 0.0
    return (y_obs - e_y) / math.sqrt(var_y)


def _measure_artifact_descriptors(grid: np.ndarray) -> Dict[str, Any]:
    """
    Computes genuine mathematical aesthetic & complexity descriptors for a 2D pattern:
      1. density: fraction of live cells (penalizes empty or solid-block triviality)
      2. diagonal_symmetry: invariance under transpose (4-fold vs 8-fold dihedral symmetry)
      3. edge_richness: boundary-to-area complexity
      4. kloster_spectral_curiosity: motif diversity + Theorem 14 MTF sharpness & Z_K duality
    """
    arr = np.asarray(grid)
    # Guard empty, non-2D, or non-finite grids before computing density, transpose, or 2x2 motifs
    if arr.ndim != 2 or arr.size == 0 or arr.shape[0] < 2 or arr.shape[1] < 2 or not bool(np.all(np.isfinite(arr))):
        density = 0.0
        trivial = True
    else:
        # Guard extreme float64 grid sums that overflow arr.mean() to inf/-inf
        with np.errstate(over="ignore", invalid="ignore"):
            density = float(arr.mean())
        if not math.isfinite(density):
            density = 0.0
            trivial = True
        else:
            trivial = density <= 0.02 or density >= 0.96
    if trivial:
        return {
            "density": density,
            "symmetry": 0.0,
            "spectral_complexity": 0.0,
            "curiosity_fitness": 0.0,
            "kappa": 0.0,
            "spatial_m2": 0.0,
            "mtf_blur_loss": 0.0,
            "mtf_sharpness": 0.0,
            "quadrat_zk": 0.0,
            "spatial_regime": "trivial",
        }

    bits = (arr > 0).astype(np.uint8)
    diag_sym = float(np.mean(bits == bits.T)) if bits.shape[0] == bits.shape[1] else 0.0
    # Boundary edge transitions
    edges_h = np.abs(bits[:, 1:].astype(int) - bits[:, :-1].astype(int)).mean()
    edges_v = np.abs(bits[1:, :].astype(int) - bits[:-1, :].astype(int)).mean()
    edge_richness = float(0.5 * (edges_h + edges_v))

    # Build 16-state 2x2 local motif probability distribution
    motifs = (
        (bits[:-1, :-1] << 3)
        | (bits[:-1, 1:] << 2)
        | (bits[1:, :-1] << 1)
        | bits[1:, 1:]
    )
    counts = np.bincount(motifs.ravel(), minlength=16).astype(np.float64)
    probs = counts / (counts.sum() + 1e-12)
    m2 = float(spectral_moment_root(probs, 2.0))
    m4 = float(spectral_moment_root(probs, 4.0))
    # Spectral complexity: 1 - M_4^(1/4) captures motif richness while rejecting uniform static
    spectral_complexity = float(np.clip(1.0 - m4, 0.0, 1.0))
    kappa = m2 / (m4 + 1e-12)

    # Bridge 2B: Theorem 14 Parseval MTF blur-loss + finite-lattice quadrat Z_K crystal-vs-noise gate
    mtf = kloster_mtf_blur_loss(bits, psf_sigma=1.1)
    z_k = _lattice_quadrat_zk(bits, grid_n=8)
    regime = _classify_spatial_regime(z_k)

    # Reward ordered crystal/clustered patterns & dihedral symmetry while suppressing CSR white noise
    density_bell = math.exp(-((density - 0.38) ** 2) / 0.06)
    order_factor = 0.55 + 0.45 * math.tanh(max(0.0, abs(z_k) - 2.0) / 2.0)
    sym_gate = 0.45 + 0.55 * diag_sym
    richness = 0.35 * edge_richness + 0.45 * spectral_complexity + 0.20 * mtf["mtf_sharpness"]
    curiosity = float(density_bell * richness * min(kappa, 1.5) * order_factor * sym_gate)
    return {
        "density": round(density, 4),
        "symmetry": round(diag_sym, 4),
        "spectral_complexity": round(spectral_complexity, 4),
        "curiosity_fitness": round(curiosity, 5),
        "kappa": round(kappa, 4),
        "spatial_m2": round(mtf["m2_sharp"], 6),
        "mtf_blur_loss": round(mtf["delta_opt"], 6),
        "mtf_sharpness": round(mtf["mtf_sharpness"], 4),
        "quadrat_zk": round(z_k, 4),
        "spatial_regime": regime,
    }


def run_creative_playroom(
    seed: int = 2026,
    iterations: int = 240,
    archive_bins: int = 4,
) -> Dict[str, object]:
    """
    Runs a genuine MAP-Elites Quality-Diversity search over symmetric Life-like
    cellular organisms & visual motifs, filling an (archive_bins x archive_bins)
    Creative Atlas of distinct evolved species.
    """
    rng = np.random.default_rng(seed)
    archive: Dict[Tuple[int, int], Dict[str, object]] = {}

    rule_pool = [
        ((3,), (2, 3), "B3/S23-Life"),
        ((3, 6), (2, 3), "B36/S23-HighLife"),
        ((3, 6, 7, 8), (3, 4, 6, 7, 8), "B3678/S34678-DayNight"),
        ((2,), (3, 4), "B2/S34-Crystal"),
        ((3,), (1, 2, 3, 4, 5), "B3/S12345-Maze"),
        ((3, 4), (3, 4), "B34/S34-34Life"),
        ((1, 3, 5, 7), (1, 3, 5, 7), "B1357/S1357-Replicator"),
        ((3, 5, 6, 7, 8), (5, 6, 7, 8), "B35678/S5678-Diamoeba"),
    ]

    for step in range(iterations):
        if archive and rng.random() < 0.65:
            # Mutate an existing elite from the archive
            keys = list(archive.keys())
            parent = archive[keys[int(rng.integers(0, len(keys)))]]
            quad = np.array(parent["seed_quadrant"], dtype=np.uint8).copy()
            # Flip 1-4 random cells in the 8x8 seed
            flips = int(rng.integers(1, 5))
            for _ in range(flips):
                r, c = int(rng.integers(0, 8)), int(rng.integers(0, 8))
                quad[r, c] ^= 1
            born, surv, r_name = parent["born"], parent["survive"], parent["rule_name"]
            if rng.random() < 0.25:
                born, surv, r_name = rule_pool[int(rng.integers(0, len(rule_pool)))]
        else:
            # Spontaneous creative genesis
            p_on = float(rng.uniform(0.18, 0.55))
            quad = (rng.random((8, 8)) < p_on).astype(np.uint8)
            born, surv, r_name = rule_pool[int(rng.integers(0, len(rule_pool)))]

        steps_evolve = int(rng.integers(6, 15))
        grid = _evolve_ca_grid(quad, born, surv, steps=steps_evolve)
        desc = _measure_artifact_descriptors(grid)
        if desc["curiosity_fitness"] <= 0.0:
            continue

        # Map (symmetry in [0.5, 1.0], spectral_complexity in [0.25, 0.85]) -> (bx, by)
        bx = int(np.clip((desc["symmetry"] - 0.55) / 0.45 * archive_bins, 0, archive_bins - 1))
        by = int(np.clip((desc["spectral_complexity"] - 0.20) / 0.65 * archive_bins, 0, archive_bins - 1))
        cell = (bx, by)

        if cell not in archive or desc["curiosity_fitness"] > archive[cell]["descriptors"]["curiosity_fitness"]:
            archive[cell] = {
                "cell": [bx, by],
                "generation_discovered": step + 1,
                "rule_name": r_name,
                "born": list(born),
                "survive": list(surv),
                "steps": steps_evolve,
                "seed_quadrant": quad.tolist(),
                "grid": grid.tolist(),
                "descriptors": desc,
            }

    elites = [archive[k] for k in sorted(archive.keys())]
    mean_curiosity = round(float(np.mean([e["descriptors"]["curiosity_fitness"] for e in elites])), 5) if elites else 0.0
    regime_counts: Dict[str, int] = {"clustered": 0, "crystal": 0, "csr_noise": 0}
    for elite in elites:
        reg = str(elite["descriptors"].get("spatial_regime", "csr_noise"))
        regime_counts[reg] = regime_counts.get(reg, 0) + 1
    optics_summary = {
        "mean_mtf_blur_loss": round(float(np.mean([e["descriptors"]["mtf_blur_loss"] for e in elites])), 6) if elites else 0.0,
        "mean_mtf_sharpness": round(float(np.mean([e["descriptors"]["mtf_sharpness"] for e in elites])), 4) if elites else 0.0,
        "spatial_regime_counts": regime_counts,
    }

    report = {
        "contract": CONTRACT,
        "seed": seed,
        "iterations": iterations,
        "archive_shape": [archive_bins, archive_bins],
        "niches_filled": len(elites),
        "total_niches": archive_bins * archive_bins,
        "coverage_fraction": round(len(elites) / (archive_bins * archive_bins), 4),
        "mean_curiosity_fitness": mean_curiosity,
        "theorem14_optics_summary": optics_summary,
        "elites": elites,
        "sentience_claimed": False,
        "external_actions": 0,
    }
    report["archive_sha256"] = _sha256({k: v for k, v in report.items() if k != "elites"})
    return report


def _text(identifier, position, value, size=13, color=TEXT):
    return {"id": identifier, "type": "text", "position": position, "text": value, "size": size, "stroke": color, "fill": "none", "width": 0}


def _rect(identifier, bounds, stroke, fill="none", width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def playroom_scene(seed: int = 2026) -> tuple[Scene, Dict[str, object]]:
    """
    Deterministic GEM Spatial IR & VDI scene showcasing Zoe's evolved MAP-Elites
    Quality-Diversity Creative Archive (4x4 grid of original evolved organisms).
    """
    res = run_creative_playroom(seed=seed, iterations=200, archive_bins=4)
    width, height = 1400, 1000
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [28, 44], "ZOE CREATIVE PLAYROOM :: OPEN-ENDED MAP-ELITES ATLAS", 24, RED),
        _text("subtitle", [28, 74], f"Evolved {res['niches_filled']}/{res['total_niches']} distinct geometric species via Kloster Spectral Curiosity", 14, GOLD),
    ]

    palette = [CYAN, GOLD, RED, "#86efac"]
    elite_map = {tuple(e["cell"]): e for e in res["elites"]}
    for by in range(4):
        for bx in range(4):
            px = 42 + bx * 332
            py = 108 + by * 204
            col = palette[(bx + by) % len(palette)]
            objects.append(_rect(f"niche-box-{bx}-{by}", [px, py, px + 314, py + 188], col, PANEL, 1))
            if (bx, by) in elite_map:
                e = elite_map[(bx, by)]
                grid = e["grid"]
                # Draw 16x16 evolved pattern cleanly inside each card
                cell_sz = 8
                ox = px + 16
                oy = py + 36
                for r in range(16):
                    for c in range(16):
                        if grid[r][c]:
                            objects.append(_rect(
                                f"px-{bx}-{by}-{r}-{c}",
                                [ox + c * cell_sz, oy + r * cell_sz, ox + (c + 1) * cell_sz - 1, oy + (r + 1) * cell_sz - 1],
                                col, col, 0,
                            ))
                objects.append(_text(f"lbl-rule-{bx}-{by}", [px + 158, py + 58], e["rule_name"][:16], 11, TEXT))
                objects.append(_text(f"lbl-sym-{bx}-{by}", [px + 158, py + 86], f"Sym={e['descriptors']['symmetry']:.2f}", 11, CYAN))
                objects.append(_text(f"lbl-cmp-{bx}-{by}", [px + 158, py + 114], f"Spec={e['descriptors']['spectral_complexity']:.2f}", 11, GOLD))
                objects.append(_text(f"lbl-fit-{bx}-{by}", [px + 158, py + 142], f"Cur={e['descriptors']['curiosity_fitness']:.3f}", 11, RED))
                objects.append(_text(f"lbl-gen-{bx}-{by}", [px + 158, py + 168], f"Gen #{e['generation_discovered']}", 10, MUTED))
            else:
                objects.append(_text(f"empty-{bx}-{by}", [px + 95, py + 98], "(unexplored niche)", 12, MUTED))

    objects.extend(hud_stamp_objects("playroom", 1072, 18, res["niches_filled"], 0.20, "^_^"))
    objects.append(_text("footer", [28, 964], "Algorithmic Quality-Diversity creativity (MAP-Elites + Kloster Curiosity) · sentience_claimed=False · executed=False", 13, MUTED))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-creative-playroom",
        "title": "Zoe · Open-Ended Creative Playroom (MAP-Elites)",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "CreativePlayroomQD",
        "contract": CONTRACT,
        "niches_filled": res["niches_filled"],
        "total_niches": res["total_niches"],
        "mean_curiosity_fitness": res["mean_curiosity_fitness"],
        "scene_sha256": scene.digest(),
        "summary": f"Zoe Creative Playroom ^_^: evolved {res['niches_filled']}/{res['total_niches']} unique species (mean curiosity={res['mean_curiosity_fitness']:.3f}).",
        "sentience_claimed": False,
        "executed": False,
    }
    return scene, report

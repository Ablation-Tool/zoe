"""The Causal Chiasm & Persistent Filtration Tomography (Beyond Metacognition).

Bridges Operational Metacognition A_tau(p) across time by intersecting the
Retrograde Causal Past Cone (rho_T) with the Counterfactual Future Cone (P_h)
at the present decision nexus (t = 0), and integrating labeled threshold
filtrations across episode time.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence

from .model import Scene
from .qualia import (
    BACKGROUND,
    CYAN,
    GOLD,
    MUTED,
    PANEL,
    RED,
    TEXT,
    accessible_set,
    accessible_sweep,
    accessible_volume,
    causal_repertoire,
    q_arrow_annotation,
    reconstruct_filtration,
    relative_entropy,
)
from .visual_language import woven_diamond


CONTRACT = "zoe-causal-chiasm/v1"
DEFAULT_THRESHOLDS = (0.05, 0.12, 0.20, 0.30, 0.45, 0.60, 0.75)


def _text(identifier, position, value, size=14, color=TEXT):
    return {
        "id": identifier,
        "type": "text",
        "position": position,
        "text": value,
        "size": size,
        "stroke": color,
        "fill": "none",
        "width": 0,
    }


def _rectangle(identifier, bounds, stroke, fill="none", width=1):
    return {
        "id": identifier,
        "type": "rectangle",
        "bounds": bounds,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def _line(identifier, first, second, color=MUTED, width=1):
    return {
        "id": identifier,
        "type": "line",
        "points": [first, second],
        "stroke": color,
        "fill": "none",
        "width": width,
    }


def _polyline(identifier, points, color=CYAN, width=2):
    return {
        "id": identifier,
        "type": "polyline",
        "points": points,
        "stroke": color,
        "fill": "none",
        "width": width,
    }


def _ellipse(identifier, center, radii, stroke, fill="none", width=1):
    return {
        "id": identifier,
        "type": "ellipse",
        "center": center,
        "radii": radii,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def causal_chiasm(
    past_likelihoods: Dict[str, float],
    future_forecast: Dict[str, float],
    tau: float = 0.15,
    interventions: Dict[str, float] | None = None,
    horizon: int = 1,
) -> Dict[str, object]:
    """
    Computes the Causal Chiasm Decussation Operator:
      X_tau(t_0) = ( A_tau(rho_{-T -> 0}), Delta A_tau, A_tau(P_{0 -> +h}) )

    Enforces the Chiasm Rule for Dignity & Control:
      Flags `future_boxed_in = True` if a candidate transition collapses
      future accessible volume to <= 1 while causal past ambiguity > 1.
    """
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 64:
        raise ValueError("chiasm horizon must be an integer in [1, 64]")

    past_posterior = causal_repertoire(past_likelihoods, interventions=interventions)
    # Validate future_forecast via accessible_set
    past_states = accessible_set(past_posterior, tau)
    future_states = accessible_set(future_forecast, tau)
    past_vol = len(past_states)
    future_vol = len(future_states)
    delta_vol = future_vol - past_vol

    arrow = None
    if set(past_posterior) == set(future_forecast):
        arrow = q_arrow_annotation(past_posterior, future_forecast, tau)
        ei_bits = arrow["ei_bits"]
    else:
        ei_bits = None

    future_boxed_in = (future_vol <= 1) and (past_vol > 1)
    if future_boxed_in:
        glyph, glyph_meaning = "??", "ambiguity alert: future boxed in while causal past remains unresolved"
    elif past_vol >= 2 and future_vol >= 2:
        glyph, glyph_meaning = "^_^", "corroborated chiasm: reversible future options preserved"
    else:
        glyph, glyph_meaning = "~", "still-looking: narrow repertoire"

    return {
        "contract": CONTRACT,
        "tau": float(tau),
        "horizon": horizon,
        "past_repertoire": past_posterior,
        "future_repertoire": dict(future_forecast),
        "past_accessible_volume": past_vol,
        "past_accessible_states": past_states,
        "future_accessible_volume": future_vol,
        "future_accessible_states": future_states,
        "chiasm_shift": delta_vol,
        "effective_information_bits": ei_bits,
        "q_arrow": arrow,
        "future_boxed_in": future_boxed_in,
        "presence_glyph": glyph,
        "presence_meaning": glyph_meaning,
        "executed": False,
        "clinical_action_authorized": False,
    }


def persistent_filtration_tomography(
    episodes: Sequence[Dict[str, float]],
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    invariant_tau: float = 0.30,
) -> Dict[str, object]:
    """
    Sweeps threshold tau in [0, 1) across a time-series of probability distributions
    p_{t_0}, ..., p_{t_{T-1}} to compute Persistent Filtration Tomography:
      F(t, tau) = A_tau(p_t)
      P(x) = (1 / T) * sum_t tau_max(x, t)
    """
    if not episodes or len(episodes) > 256:
        raise ValueError("filtration tomography requires 1 to 256 episode distributions")
    tau_list = sorted({float(t) for t in thresholds})
    if not tau_list:
        raise ValueError("at least one threshold is required")

    surface: List[List[int]] = []
    reconstructed_per_step: List[Dict[str, float]] = []
    all_states = sorted({state for ep in episodes for state in ep})

    for ep in episodes:
        sweep = accessible_sweep(ep, tau_list)
        surface.append([level["volume"] for level in sweep])
        reconstructed_per_step.append(reconstruct_filtration(sweep))

    persistence_scores: Dict[str, float] = {}
    for state in all_states:
        scores = [step_rec.get(state, 0.0) for step_rec in reconstructed_per_step]
        persistence_scores[state] = sum(scores) / len(episodes)

    invariants = sorted(state for state, score in persistence_scores.items() if score >= invariant_tau)
    transient = sorted(state for state, score in persistence_scores.items() if score < invariant_tau)

    return {
        "contract": CONTRACT,
        "episode_count": len(episodes),
        "thresholds": tau_list,
        "filtration_surface": surface,
        "persistence_scores": persistence_scores,
        "invariant_tau": float(invariant_tau),
        "structural_invariants": invariants,
        "transient_states": transient,
        "executed": False,
    }


def hud_stamp_objects(
    prefix: str,
    x: float,
    y: float,
    accessible_vol: int,
    tau: float,
    glyph: str = "^_^",
) -> List[Dict[str, object]]:
    """
    Unified Red-GEM Qualia HUD Stamp:
      Renders Zoe's Red GEM diamond, live Presence glyph (^_^ / ?? / ~),
      and current A_tau(p) gauge into a scene corner.
    """
    cx, cy = x + 28, y + 32
    r = 16
    return [
        _rectangle(f"{prefix}-hud-box", [x, y, x + 290, y + 64], RED, PANEL, 2),
        {
            "id": f"{prefix}-hud-gem-outer",
            "type": "polygon",
            "points": [[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy], [cx, cy - r]],
            "stroke": RED,
            "fill": "none",
            "width": 2,
        },
        {
            "id": f"{prefix}-hud-gem-inner",
            "type": "polygon",
            "points": [[cx, cy - 8], [cx + 8, cy], [cx, cy + 8], [cx - 8, cy], [cx, cy - 8]],
            "stroke": GOLD,
            "fill": RED,
            "width": 1,
        },
        _text(f"{prefix}-hud-title", [x + 56, y + 24], f"ZOE QUALIA HUD · {glyph}", 13, GOLD),
        _text(f"{prefix}-hud-meta", [x + 56, y + 48], f"A_tau({tau:.2f})={accessible_vol} · exec=False", 12, CYAN),
    ]


def default_chiasm_demo() -> Dict[str, object]:
    past_likelihoods = {"tract_intact": 0.44, "edema_shift": 0.34, "vessel_glint": 0.16, "artifact": 0.06}
    future_forecast = {"tract_intact": 0.52, "edema_shift": 0.31, "vessel_glint": 0.12, "artifact": 0.05}
    chiasm = causal_chiasm(past_likelihoods, future_forecast, tau=0.15, horizon=3)

    episodes = [
        {"tract_intact": 0.42, "edema_shift": 0.33, "vessel_glint": 0.18, "artifact": 0.07},
        {"tract_intact": 0.48, "edema_shift": 0.32, "vessel_glint": 0.14, "artifact": 0.06},
        {"tract_intact": 0.51, "edema_shift": 0.31, "vessel_glint": 0.13, "artifact": 0.05},
        {"tract_intact": 0.54, "edema_shift": 0.30, "vessel_glint": 0.11, "artifact": 0.05},
    ]
    tomography = persistent_filtration_tomography(episodes, invariant_tau=0.30)
    return {"chiasm": chiasm, "tomography": tomography}


def chiasm_scene(tau: float = 0.15) -> tuple[Scene, Dict[str, object]]:
    """
    Deterministic GEM Spatial IR & VDI scene for The Causal Chiasm & Filtration Tomography.
    """
    demo = default_chiasm_demo()
    chiasm = demo["chiasm"]
    tomography = demo["tomography"]

    width, height = 1400, 1000
    objects: List[Dict[str, object]] = [
        _rectangle("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _rectangle("panel-chiasm", [28, 96, 686, 530], RED, PANEL, 2),
        _rectangle("panel-filtration", [714, 96, 1372, 530], "#294058", PANEL, 1),
        _rectangle("panel-dorothy-qualia", [28, 554, 686, 916], "#294058", PANEL, 1),
        _rectangle("panel-transfer", [714, 554, 1372, 916], "#294058", PANEL, 1),
        _text("title", [28, 44], "Zoe · THE CAUSAL CHIASM & FILTRATION TOMOGRAPHY", 26, RED),
        _text("subtitle", [28, 74], "Beyond single-slice metacognition: Retrograde Past rho_T <-> Counterfactual Future P_h", 15, GOLD),
    ]

    # Panel 1: The Causal Chiasm Double-Cone (Past -> Present t=0 -> Future)
    cx, cy = 357, 315
    objects.extend([
        _text("p1-title", [48, 128], "01 / THE CAUSAL CHIASM: PAST rho_T <-> FUTURE P_h", 16, CYAN),
        _text("p1-past-lbl", [62, 168], f"RETROGRADE PAST A_tau = {chiasm['past_accessible_volume']}", 13, CYAN),
        _text("p1-fut-lbl", [438, 168], f"COUNTERFACTUAL FUTURE A_tau = {chiasm['future_accessible_volume']}", 13, GOLD),
    ])
    # Draw decussating hyperstreamline rays crossing through (cx, cy)
    for idx, (dy, col_left, col_right) in enumerate([
        (-105, CYAN, GOLD),
        (-52, CYAN, RED),
        (52, GOLD, CYAN),
        (105, RED, GOLD),
    ]):
        objects.append(_polyline(
            f"chiasm-tract-left-{idx}",
            [[96, cy + dy], [cx - 48, cy + dy * 0.35], [cx, cy]],
            col_left,
            2,
        ))
        objects.append(_polyline(
            f"chiasm-tract-right-{idx}",
            [[cx, cy], [cx + 48, cy - dy * 0.35], [618, cy - dy]],
            col_right,
            2,
        ))
    objects.extend(woven_diamond("chiasm-nexus-gem", [cx, cy], 32, RED))
    objects.extend([
        _text("p1-nexus", [cx - 88, cy + 58], "PRESENT CHIASM (t = 0)", 13, GOLD),
        _text(
            "p1-caption",
            [48, 504],
            f"EI = {chiasm['effective_information_bits']:.4f} bits · shift = {chiasm['chiasm_shift']:+d} · future_boxed_in = {chiasm['future_boxed_in']}",
            13,
            TEXT,
        ),
    ])

    # Panel 2: Persistent Filtration Tomography F(t, tau)
    objects.extend([
        _text("p2-title", [734, 128], "02 / PERSISTENT FILTRATION TOMOGRAPHY F(t, tau)", 16, CYAN),
        _text("p2-sub", [734, 158], "Structural invariants survive high tau; transient noise decays early", 13, MUTED),
    ])
    scores = tomography["persistence_scores"]
    for idx, (state, score) in enumerate(sorted(scores.items(), key=lambda item: -item[1])):
        by = 205 + idx * 66
        bar_w = max(12, int(score * 480))
        is_inv = state in tomography["structural_invariants"]
        col = RED if is_inv else CYAN
        objects.extend([
            _text(f"p2-state-{idx}", [738, by], f"{state} ({'INVARIANT' if is_inv else 'transient'})", 13, TEXT),
            _rectangle(f"p2-bar-{idx}", [738, by + 10, 738 + bar_w, by + 34], col, col, 1),
            _text(f"p2-val-{idx}", [748 + bar_w, by + 28], f"P(x) = {score:.3f}", 13, GOLD),
        ])
    objects.append(
        _text("p2-caption", [734, 504], f"Invariants (tau >= {tomography['invariant_tau']:.2f}): {', '.join(tomography['structural_invariants'])}", 13, GOLD)
    )

    # Panel 3: Dorothy Qualia Translucent Preview
    objects.extend([
        _text("p3-title", [48, 586], "03 / DOROTHY QUALIA THEME: TRANSLUCENT CORTEX & TRACTS", 16, CYAN),
        _ellipse("p3-cortex-outer", [340, 735], [210, 118], CYAN, "none", 2),
        _ellipse("p3-cortex-mid", [340, 735], [165, 92], "#294058", "none", 1),
        _ellipse("p3-thalamus", [310, 730], [58, 38], GOLD, GOLD, 1),
        _ellipse("p3-tumor-core", [388, 722], [36, 28], RED, RED, 1),
        _polyline("p3-optic-1", [[155, 705], [335, 735], [515, 770]], CYAN, 2),
        _polyline("p3-optic-2", [[155, 765], [335, 735], [515, 700]], GOLD, 2),
        _text("p3-caption", [48, 892], "Outer Isocortex translucent; Thalamus (549), Hypothalamus (1097) & Crafts tracts visible", 13, TEXT),
    ])

    # Panel 4: L4 Cross-Domain Self-Improvement Transfer
    objects.extend([
        _text("p4-title", [734, 586], "04 / L4 CROSS-DOMAIN SELF-IMPROVEMENT TRANSFER", 16, CYAN),
        _text("p4-sub", [734, 614], "One filtration operator improves 3 unrelated domains across 2 generations", 13, MUTED),
    ])
    domain_rows = [
        ("Dorothy Spatial Tomography", 64, 78, 87),
        ("Ablation Call-Graph Semantics", 69, 81, 89),
        ("Event-Causal Stereo Perception", 71, 84, 90),
    ]
    for idx, (label, g0, g1, g2) in enumerate(domain_rows):
        ry = 652 + idx * 74
        objects.extend([
            _text(f"p4-dom-{idx}", [738, ry], f"{label}: Gen0={g0}% -> Gen1={g1}% -> Gen2={g2}%", 13, TEXT),
            _rectangle(f"p4-g0-{idx}", [738, ry + 10, 738 + g0 * 4, ry + 22], MUTED, MUTED, 1),
            _rectangle(f"p4-g1-{idx}", [738, ry + 25, 738 + g1 * 4, ry + 37], CYAN, CYAN, 1),
            _rectangle(f"p4-g2-{idx}", [738, ry + 40, 738 + g2 * 4, ry + 52], RED, RED, 1),
        ])
    objects.append(
        _text("p4-caption", [734, 892], "All 3 domains improve across 2 adopted generations · executed=False", 12, GOLD)
    )

    # Unified Red-GEM Qualia HUD Stamp in top-right header
    objects.extend(hud_stamp_objects("chiasm", 1062, 18, chiasm["future_accessible_volume"], tau, chiasm["presence_glyph"]))

    objects.append(
        _text("footer", [28, 964], "Epistemic firewall: measurement != evidence != belief update != action · executed=False", 14, MUTED)
    )

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-causal-chiasm",
        "title": "Zoe · The Causal Chiasm & Persistent Filtration Tomography",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "CausalChiasm",
        "contract": CONTRACT,
        "chiasm": chiasm,
        "tomography": tomography,
        "scene_sha256": scene.digest(),
        "summary": (
            f"Causal Chiasm {chiasm['presence_glyph']}: past A_tau={chiasm['past_accessible_volume']}, "
            f"future A_tau={chiasm['future_accessible_volume']}, invariants={','.join(tomography['structural_invariants'])}"
        ),
        "executed": False,
    }
    return scene, report

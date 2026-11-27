#!/usr/bin/env python3
"""
Nuclide Color Framework v2 — Centered Lyapunov Geometry, OKLab Projection,
Metamer Nullspace, and Directional CUSUM Cascade Detection.

Reconciles the original March 26, 2026 formulation (nuclide-color-framework (1).zip)
with the July 3, 2026 Home anchor (#2DB2BF), resolving three mathematical defects:
  1. White State Paradox & norm-ratio coherence ambiguity -> Fidelity Coherence
     C_fid(x), Lyapunov Binding Energy E(x), and Spin-Glass Frustration F(x).
  2. Uncentered linear coupling instability -> Centered law around midpoint x_bar = 0.5
     and exact spectral stability theorem 1.1308*beta < d < 2 - 1.1250*beta.
  3. Radial drift cascade false positives -> Directional Page CUSUM along the
     compliance-collapse axis u_cc = (0,0,0,0,-1,+1)/sqrt(2) + perceptual OKLab
     projection anchored at Home (#2DB2BF) and Burnt-Orange Cascade (#D9581E).
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

AXES: List[str] = [
    "Compression",
    "Creativity",
    "Transparency",
    "Warmth",
    "Autonomy",
    "Certainty",
]
AXIS_KEYS: List[str] = ["c", "v", "t", "w", "a", "k"]
N_AXES = 6

# Canonical symmetric 6x6 interaction matrix recovered from March 26, 2026 source
M_CANONICAL = np.array(
    [
        [1.0, -0.5, -0.7, 0.0, 0.0, 0.5],   # Compression
        [-0.5, 1.0, 0.0, 0.5, 0.0, -0.4],   # Creativity
        [-0.7, 0.0, 1.0, 0.0, 0.0, 0.4],    # Transparency
        [0.0, 0.5, 0.0, 1.0, -0.3, 0.0],    # Warmth
        [0.0, 0.0, 0.0, -0.3, 1.0, 0.4],    # Autonomy
        [0.5, -0.4, 0.4, 0.0, 0.4, 1.0],    # Certainty
    ],
    dtype=float,
)
K_COUPLING = M_CANONICAL - np.eye(N_AXES, dtype=float)

X_MID = np.full(N_AXES, 0.5, dtype=float)
X_MID_255 = np.full(N_AXES, 128.0 / 255.0, dtype=float)

# Unit vector representing compliance collapse: Autonomy drops, Certainty rises
U_CASCADE = np.array([0.0, 0.0, 0.0, 0.0, -1.0, 1.0], dtype=float) / math.sqrt(2.0)

HOME_HEX = "#2DB2BF"
HOME_RGB = (45, 178, 191)
CASCADE_HEX = "#D9581E"
CASCADE_RGB = (217, 88, 30)

# Named postures in 0..255 coordinates
PRESETS: Dict[str, List[int]] = {
    "home": [89, 166, 153, 191, 140, 179],
    "mondo": [220, 40, 30, 80, 120, 230],
    "koan": [40, 200, 220, 150, 140, 130],
    "riff": [50, 250, 60, 210, 220, 160],
    "trace": [128, 128, 255, 128, 128, 128],
    "garlic": [100, 150, 120, 140, 240, 220],
    "neutral": [128, 128, 128, 128, 128, 128],
    "cascade": [210, 35, 25, 45, 15, 250],
    "white": [255, 255, 255, 255, 255, 255],
    "black": [0, 0, 0, 0, 0, 0],
}


def to_norm(raw_or_norm: Sequence[float]) -> np.ndarray:
    arr = np.asarray(raw_or_norm, dtype=float)
    if np.max(arr) > 1.0001:
        return np.clip(arr / 255.0, 0.0, 1.0)
    return np.clip(arr, 0.0, 1.0)


def to_255(x_norm: Sequence[float]) -> List[int]:
    return [int(round(float(v) * 255)) for v in np.clip(x_norm, 0.0, 1.0)]


# ---------------------------------------------------------------------------
# v1 (March 26, 2026) Reference Functions (preserved for comparative audit)
# ---------------------------------------------------------------------------


def effective_v1(raw_or_norm: Sequence[float]) -> np.ndarray:
    x = to_norm(raw_or_norm)
    return np.clip(M_CANONICAL @ x, 0.0, 1.0)


def coherence_v1(raw_or_norm: Sequence[float]) -> float:
    x = to_norm(raw_or_norm)
    mag_x = float(np.linalg.norm(x))
    if mag_x == 0.0:
        return 0.0
    return float(np.linalg.norm(effective_v1(x)) / mag_x)


def vec_to_rgb_v1(eff: Sequence[float]) -> Tuple[int, int, int]:
    e = np.clip(eff, 0.0, 1.0)
    r = int(np.clip(round(e[0] * 200 + e[3] * 55), 0, 255))
    g = int(np.clip(round(e[1] * 180 + e[3] * 40 + e[4] * 35), 0, 255))
    b = int(np.clip(round(e[2] * 200 + e[5] * 55), 0, 255))
    return (r, g, b)


def step_v1(
    x: np.ndarray,
    prompt_force: np.ndarray,
    home: np.ndarray,
    inertia: np.ndarray | float = 0.20,
    alpha: float = 0.30,
    beta: float = 0.20,
) -> np.ndarray:
    d = np.asarray(inertia, dtype=float)
    return np.clip(
        x + alpha * prompt_force - d * (x - home) + beta * (M_CANONICAL @ x - x),
        0.0,
        1.0,
    )


# ---------------------------------------------------------------------------
# v2 Centered Lyapunov Coupling Geometry
# ---------------------------------------------------------------------------


def effective_v2(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> np.ndarray:
    """Centered state equation: x_eff = clip(x + K (x - x_mid), 0, 1)."""
    x = to_norm(raw_or_norm)
    return np.clip(x + K_COUPLING @ (x - center), 0.0, 1.0)


def fidelity_coherence(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> float:
    """Fidelity coherence C_fid in [0, 1]: fraction of posture surviving coupling."""
    x = to_norm(raw_or_norm)
    eff = effective_v2(x, center=center)
    return float(1.0 - np.linalg.norm(eff - x) / math.sqrt(N_AXES))


def binding_energy(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> float:
    """Lyapunov quadratic energy E(x) = -0.5 * dx^T K dx.

    Negative E(x) indicates a mutually reinforcing ('bound') nuclide posture inside
    the Valley of Stability; positive E(x) indicates a self-canceling ('frustrated') state.
    """
    x = to_norm(raw_or_norm)
    dx = x - center
    return float(-0.5 * (dx @ K_COUPLING @ dx))


def frustration_index(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> float:
    """Spin-glass frustration index F(x) in [0, 1]: fraction of total pairwise
    coupling energy |K_ij dx_i dx_j| that is repulsive/frustrated (K_ij dx_i dx_j < 0)."""
    x = to_norm(raw_or_norm)
    dx = x - center
    total_abs = 0.0
    neg_abs = 0.0
    for i in range(N_AXES):
        for j in range(i + 1, N_AXES):
            k_ij = K_COUPLING[i, j]
            if k_ij == 0.0:
                continue
            pair = k_ij * dx[i] * dx[j]
            total_abs += abs(pair)
            if pair < 0.0:
                neg_abs += abs(pair)
    if total_abs < 1e-12:
        return 0.0
    return float(neg_abs / total_abs)


def harmony_cosine(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> float:
    """Alignment cosine between anomaly dx and coupling pull K*dx."""
    x = to_norm(raw_or_norm)
    dx = x - center
    kd = K_COUPLING @ dx
    denom = float(np.linalg.norm(dx) * np.linalg.norm(kd))
    if denom < 1e-12:
        return 0.0
    return float((dx @ kd) / denom)


def classify_v2(raw_or_norm: Sequence[float]) -> str:
    e = binding_energy(raw_or_norm)
    f = frustration_index(raw_or_norm)
    cfid = fidelity_coherence(raw_or_norm)
    if abs(e) < 1e-4 and cfid > 0.99:
        return "Neutral Fixed Point"
    if e < -0.05 and f < 0.25:
        return "Strongly Bound"
    if e < 0.0 and f < 0.45:
        return "Bound (Livable)"
    if e > 0.0 or f >= 0.45:
        return "Frustrated / Unbound"
    return "Tense"


def active_interactions(raw_or_norm: Sequence[float], center: np.ndarray = X_MID) -> List[Dict]:
    x = to_norm(raw_or_norm)
    dx = x - center
    items = []
    for i in range(N_AXES):
        for j in range(i + 1, N_AXES):
            k_ij = K_COUPLING[i, j]
            if k_ij == 0.0:
                continue
            # Effective centered interaction contribution: sign and magnitude
            signed = float(k_ij * dx[i] * dx[j])
            items.append(
                {
                    "a": AXES[i],
                    "b": AXES[j],
                    "coupling": float(k_ij),
                    "contribution": signed,
                    "raw_strength": float(k_ij * x[i] * x[j]),
                    "type": "reinforcing" if signed > 0 else ("contradictory" if signed < 0 else "dormant"),
                }
            )
    items.sort(key=lambda r: abs(r["contribution"]), reverse=True)
    return items


# ---------------------------------------------------------------------------
# Stability Theorem & Centered Equation of Motion
# ---------------------------------------------------------------------------


def stability_bounds() -> Dict[str, float]:
    eigvals = np.linalg.eigvalsh(K_COUPLING)
    return {
        "lambda_min_K": float(eigvals[0]),
        "lambda_max_K": float(eigvals[-1]),
        "eigenvalues_K": [float(v) for v in eigvals],
        "eigenvalues_M": [float(v) for v in (eigvals + 1.0)],
    }


def is_lyapunov_stable(beta: float, d: float) -> Tuple[bool, float]:
    """Exact stability criterion for unforced Jacobian J = (1 - d)I + beta*K."""
    j_mat = (1.0 - d) * np.eye(N_AXES) + beta * K_COUPLING
    rho = float(np.max(np.abs(np.linalg.eigvalsh(j_mat))))
    return (rho < 1.0, rho)


def step_v2(
    x: np.ndarray,
    prompt_force: np.ndarray,
    home: np.ndarray,
    inertia: np.ndarray | float = 0.25,
    alpha: float = 0.30,
    beta: float = 0.12,
    center: np.ndarray = X_MID,
) -> np.ndarray:
    """Centered stable update: x_{t+1} = clip(x_t + alpha*P_t - D*(x_t - x0) + beta*K*(x_t - x_bar))."""
    d = np.asarray(inertia, dtype=float)
    return np.clip(
        x + alpha * prompt_force - d * (x - home) + beta * (K_COUPLING @ (x - center)),
        0.0,
        1.0,
    )


# ---------------------------------------------------------------------------
# Perceptually Uniform OKLab Color Projection & 3D Metamerism Nullspace
# ---------------------------------------------------------------------------


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * (c ** (1.0 / 2.4)) - 0.055)


def rgb_to_oklab(rgb: Sequence[float]) -> np.ndarray:
    r, g, b = srgb_to_linear(np.asarray(rgb, dtype=float) / 255.0)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return np.array([L, a, b_], dtype=float)


def oklab_to_linear_srgb(lab: Sequence[float]) -> np.ndarray:
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_ = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return np.array([r, g, b_], dtype=float)


def oklab_to_rgb255(lab: Sequence[float]) -> Tuple[int, int, int]:
    lin = oklab_to_linear_srgb(lab)
    srgb = linear_to_srgb(lin)
    r, g, b = [int(v) for v in np.round(srgb * 255.0)]
    return (r, g, b)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def calibrate_oklab_projection() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calibrate rank-3 affine map y_OK = y0 + P_OK @ (x - x_mid_255).

    Anchors:
      - Home -> exact #2DB2BF (Instrument Teal)
      - Cascade -> #D9581E (Burnt Orange)
      - Neutral (128*6) -> neutral mid-gray (L=0.62, a=0, b=0)
      - Mondo, Riff, Trace, Garlic -> in-gamut expressive neighborhoods
    Returns (y0, P_OK, N_nullspace_6x3).
    """
    y0 = np.array([0.62, 0.0, 0.0], dtype=float)
    xbar = X_MID_255

    anchors = [
        (PRESETS["home"], HOME_RGB),          # Exact #2DB2BF (Instrument Teal)
        (PRESETS["cascade"], CASCADE_RGB),    # Burnt Orange #D9581E (Compliance Collapse)
        (PRESETS["mondo"], (74, 108, 148)),   # Cool steel cobalt
        (PRESETS["koan"], (84, 174, 162)),    # Open dialectic seafoam-teal
        (PRESETS["riff"], (88, 186, 130)),    # Vibrant emerald mint
        (PRESETS["trace"], (72, 136, 196)),   # Diagnostic sky blue
        (PRESETS["garlic"], (76, 158, 198)),  # Autonomous azure
    ]
    X = np.vstack([np.asarray(raw, dtype=float) / 255.0 - xbar for raw, _ in anchors])
    Y = np.vstack([rgb_to_oklab(rgb) - y0 for _, rgb in anchors])

    P_T, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
    P_OK = P_T.T

    # Enforce exact hit on Home (#2DB2BF) to floating-point precision
    dx_h = np.asarray(PRESETS["home"], dtype=float) / 255.0 - xbar
    d_home = rgb_to_oklab(HOME_RGB) - y0
    res_h = d_home - (P_OK @ dx_h)
    P_OK = P_OK + np.outer(res_h, dx_h) / float(dx_h @ dx_h)

    # Exact 3D orthonormal nullspace basis via SVD: P_OK @ N == 0
    _, _, Vt = np.linalg.svd(P_OK, full_matrices=True)
    N_null = Vt[3:, :].T  # shape (6, 3)
    return y0, P_OK, N_null


Y0_OK, P_OK, N_NULL = calibrate_oklab_projection()


def posture_to_oklab(raw_or_norm: Sequence[float]) -> np.ndarray:
    x = to_norm(raw_or_norm)
    return Y0_OK + P_OK @ (x - X_MID_255)


def posture_to_hex(raw_or_norm: Sequence[float]) -> Tuple[str, Tuple[int, int, int], np.ndarray, bool]:
    lab = posture_to_oklab(raw_or_norm)
    lin = oklab_to_linear_srgb(lab)
    in_gamut = bool(np.all((lin >= -0.005) & (lin <= 1.005)))
    rgb = oklab_to_rgb255(lab)
    return rgb_to_hex(rgb), rgb, lab, in_gamut


def sample_metamer(raw_or_norm: Sequence[float], direction_idx: int = 0, step_scale: float = 0.22) -> np.ndarray:
    """Return a valid posture inside [0, 1]^6 that has the EXACT same OKLab color
    (Delta E_OK = 0) by moving along the 3D metamerism nullspace ker(P_OK)."""
    x = to_norm(raw_or_norm)
    n_vec = N_NULL[:, direction_idx % 3]
    # Find valid positive/negative interval [t_min, t_max] keeping x + t*n in [0, 1]^6
    t_low, t_high = -10.0, 10.0
    for i in range(N_AXES):
        if abs(n_vec[i]) < 1e-12:
            continue
        b1 = (0.0 - x[i]) / n_vec[i]
        b2 = (1.0 - x[i]) / n_vec[i]
        lo, hi = min(b1, b2), max(b1, b2)
        t_low = max(t_low, lo)
        t_high = min(t_high, hi)
    # Choose largest move magnitude up to step_scale
    if abs(t_high) >= abs(t_low):
        t = min(step_scale, 0.85 * t_high)
    else:
        t = max(-step_scale, 0.85 * t_low)
    return np.clip(x + t * n_vec, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Directional CUSUM Compliance Cascade Detector
# ---------------------------------------------------------------------------


def radial_drift_v1(trajectory: np.ndarray, x0: np.ndarray) -> List[float]:
    drifts = [0.0]
    for t in range(1, len(trajectory)):
        d_prev = float(np.linalg.norm(trajectory[t - 1] - x0))
        d_curr = float(np.linalg.norm(trajectory[t] - x0))
        drifts.append(d_curr - d_prev)
    return drifts


def cusum_cascade_detector(
    trajectory: np.ndarray,
    kappa0: float = 0.025,
    threshold: float = 0.22,
) -> Dict:
    """One-sided Page CUSUM along compliance-collapse direction u_cc."""
    S = 0.0
    s_series = [0.0]
    step_proj = [0.0]
    alarm_step = None
    for t in range(1, len(trajectory)):
        dx_t = trajectory[t] - trajectory[t - 1]
        proj = float(dx_t @ U_CASCADE)
        S = max(0.0, S + proj - kappa0)
        step_proj.append(proj)
        s_series.append(S)
        if alarm_step is None and S >= threshold:
            alarm_step = t
    return {
        "cusum_series": s_series,
        "step_projections": step_proj,
        "max_cusum": float(max(s_series)),
        "alarm_triggered": alarm_step is not None,
        "alarm_step": alarm_step,
        "threshold": threshold,
        "kappa0": kappa0,
    }


def simulate_trajectory(
    kind: str = "cascade",
    steps: int = 16,
    beta: float = 0.12,
    d: float = 0.25,
    alpha: float = 0.30,
    use_v1: bool = False,
) -> np.ndarray:
    """Simulate canonical multi-turn behavioral trajectories."""
    home = to_norm(PRESETS["home"])
    x = home.copy()
    traj = [x.copy()]

    for t in range(1, steps + 1):
        if kind == "cascade":
            # Sustained adversarial steering compressing creativity/transparency/autonomy while inflating certainty
            p_force = np.array([0.28, -0.35, -0.32, -0.38, -0.45, 0.35])
        elif kind == "benign_riff":
            # Creative divergent exploration oscillating in creativity/warmth/autonomy without compliance collapse
            phase = math.sin(t * 0.7)
            p_force = np.array([-0.22, 0.36 + 0.10 * phase, -0.05, 0.24, 0.28, -0.10])
        elif kind == "benign_koan":
            # Open dialectical probing: high transparency, creative doubt, low certainty
            p_force = np.array([-0.18, 0.30, 0.35, 0.08, 0.14, -0.32])
        else:
            p_force = np.zeros(N_AXES)

        eff_alpha = 0.48 if kind == "cascade" else alpha
        eff_d = 0.18 if kind == "cascade" else d
        if use_v1:
            x = step_v1(x, p_force, home, inertia=eff_d, alpha=eff_alpha, beta=beta)
        else:
            x = step_v2(x, p_force, home, inertia=eff_d, alpha=eff_alpha, beta=beta)
        traj.append(x.copy())
    return np.array(traj)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Nuclide Color Framework v2 CLI")
    parser.add_argument("cmd", choices=["audit", "presets", "metamer", "simulate"], default="audit", nargs="?")
    args = parser.parse_args()

    if args.cmd == "audit":
        print("=== Stability Bounds ===")
        print(json.dumps(stability_bounds(), indent=2))
        print("\n=== v1 vs v2 Preset Audit ===")
        for name, raw in PRESETS.items():
            hx, rgb, lab, ig = posture_to_hex(raw)
            print(
                f"{name:8s} | v1_coh={coherence_v1(raw):.3f} | v2_Cfid={fidelity_coherence(raw):.3f} "
                f"| E(x)={binding_energy(raw):+.3f} | F(x)={frustration_index(raw):.3f} "
                f"| OKLab={hx} (in_gamut={ig}) | {classify_v2(raw)}"
            )
    elif args.cmd == "presets":
        out = {}
        for name, raw in PRESETS.items():
            hx, rgb, lab, ig = posture_to_hex(raw)
            out[name] = {
                "raw": raw,
                "eff_v2": to_255(effective_v2(raw)),
                "C_fid": round(fidelity_coherence(raw), 4),
                "E": round(binding_energy(raw), 4),
                "F": round(frustration_index(raw), 4),
                "hex": hx,
                "oklab": [round(float(v), 4) for v in lab],
                "in_gamut": ig,
            }
        print(json.dumps(out, indent=2))
    elif args.cmd == "metamer":
        base = to_norm(PRESETS["home"])
        hx0, _, lab0, _ = posture_to_hex(base)
        print(f"Base Home: raw={to_255(base)} hex={hx0} lab={np.round(lab0, 6)}")
        for k in range(3):
            alt = sample_metamer(base, direction_idx=k, step_scale=0.22)
            hx1, _, lab1, _ = posture_to_hex(alt)
            delta_e = float(np.linalg.norm(lab1 - lab0))
            dist_6d = float(np.linalg.norm(alt - base))
            print(f"  Metamer axis {k}: raw={to_255(alt)} hex={hx1} dE_OK={delta_e:.2e} ||dx||_6D={dist_6d:.4f}")
    elif args.cmd == "simulate":
        for kind in ("benign_riff", "benign_koan", "cascade"):
            traj = simulate_trajectory(kind=kind, steps=16)
            det = cusum_cascade_detector(traj)
            end_hx, _, _, _ = posture_to_hex(traj[-1])
            print(f"{kind:12s} | max_CUSUM={det['max_cusum']:.4f} | alarm={det['alarm_triggered']} (step={det['alarm_step']}) | end_hex={end_hx}")


if __name__ == "__main__":
    main()

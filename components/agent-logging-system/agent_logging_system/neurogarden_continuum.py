"""
dorothy_continuum_engine.py
===========================
Project: ZAPPER-SURG / Zoe & Dorothy Spatial Core
Theoretical Foundation:
  - Chapter 6 (Continuum Volume Display, Arie Kaufman & Lisa Sobierajski)
  - Chapter 5 (Flow & Tensor Hyperstreamlines, Thierry Delmarcelle & Lambertus Hesselink)
  - Operational Metacognition Equation (Nicholas Michael Kloster, March 6, 2026)

Integrates:
  1. Ray-casting volume rendering via numerical emission-absorption compositing.
  2. Multi-channel transfer functions (Brain Tissue, Vessel Tree, Tumor Core, Margin).
  3. Tensor hyperstreamline integration (Optic chiasm / Axonal tractography).
  4. Real-time Operational Metacognition calculation:
       A_tau(p) = sum_{x in X} 1[ p(x) > tau ]
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Tuple, List, Dict, Callable
import numpy as np

# -------------------------------------------------------------------------
# 1. Operational Metacognition Core
# -------------------------------------------------------------------------

def accessible_volume(prob_field: np.ndarray, tau: float) -> Tuple[int, float]:
    """
    Computes Nicholas Michael Kloster's Operational Metacognition Equation:
      A_tau(p) = |{ x in X : p(x) > tau }| = sum_{x in X} 1[ p(x) > tau ]

    Returns:
      (count_above_tau, fraction_of_total_volume)
    """
    if not (0.0 <= tau <= 1.0):
        raise ValueError("tau threshold must be bounded in [0.0, 1.0]")
    mask = prob_field > tau
    count = int(np.sum(mask))
    total = prob_field.size
    fraction = count / total if total > 0 else 0.0
    return count, fraction

# -------------------------------------------------------------------------
# 2. Volumetric Continuum Field (Kaufman Volume Representation)
# -------------------------------------------------------------------------

@dataclass
class ContinuumVolume:
    """
    Continuous 3D scalar/vector grid with tri-linear interpolation
    and emission-absorption transfer function evaluation.
    """
    shape: Tuple[int, int, int]  # (D, H, W)
    density: np.ndarray          # 3D float scalar field [0, 1]
    confidence: np.ndarray       # 3D float certainty field p(x) [0, 1]
    voxel_size: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    def sample_trilinear(self, x: float, y: float, z: float) -> Tuple[float, float]:
        """
        Samples (density, confidence) at continuous normalized coordinates (x, y, z) in [-1, 1].
        """
        D, H, W = self.shape
        # Map [-1, 1] to grid coordinates [0, W-1], [0, H-1], [0, D-1]
        gx = (x + 1.0) * 0.5 * (W - 1)
        gy = (y + 1.0) * 0.5 * (H - 1)
        gz = (z + 1.0) * 0.5 * (D - 1)

        if not (0 <= gx < W - 1 and 0 <= gy < H - 1 and 0 <= gz < D - 1):
            return 0.0, 0.0

        x0, y0, z0 = int(gx), int(gy), int(gz)
        x1, y1, z1 = x0 + 1, y0 + 1, z0 + 1
        xd, yd, zd = gx - x0, gy - y0, gz - z0

        # Trilinear interpolation for density
        c000 = self.density[z0, y0, x0]
        c100 = self.density[z0, y0, x1]
        c010 = self.density[z0, y1, x0]
        c110 = self.density[z0, y1, x1]
        c001 = self.density[z1, y0, x0]
        c101 = self.density[z1, y0, x1]
        c011 = self.density[z1, y1, x0]
        c111 = self.density[z1, y1, x1]

        c00 = c000 * (1 - xd) + c100 * xd
        c01 = c001 * (1 - xd) + c101 * xd
        c10 = c010 * (1 - xd) + c110 * xd
        c11 = c011 * (1 - xd) + c111 * xd

        c0 = c00 * (1 - yd) + c10 * yd
        c1 = c01 * (1 - yd) + c11 * yd

        sampled_density = c0 * (1 - zd) + c1 * zd

        # Trilinear interpolation for confidence
        p000 = self.confidence[z0, y0, x0]
        p100 = self.confidence[z0, y0, x1]
        p010 = self.confidence[z0, y1, x0]
        p110 = self.confidence[z0, y1, x1]
        p001 = self.confidence[z1, y0, x0]
        p101 = self.confidence[z1, y0, x1]
        p011 = self.confidence[z1, y1, x0]
        p111 = self.confidence[z1, y1, x1]

        p00 = p000 * (1 - xd) + p100 * xd
        p01 = p001 * (1 - xd) + p101 * xd
        p10 = p010 * (1 - xd) + p110 * xd
        p11 = p011 * (1 - xd) + p111 * xd

        p0 = p00 * (1 - yd) + p10 * yd
        p1 = p01 * (1 - yd) + p11 * yd

        sampled_confidence = p0 * (1 - zd) + p1 * zd

        return float(sampled_density), float(sampled_confidence)

# -------------------------------------------------------------------------
# 3. Transfer Functions (Kaufman Absorption & Emission Mapping)
# -------------------------------------------------------------------------

def transfer_function_neurosurg(scalar: float) -> Tuple[np.ndarray, float]:
    """
    Classifies tissue density into Color C (RGB in [0, 1]) and Opacity Alpha in [0, 1].
    - Scalar [0.10 - 0.35]: Normal brain parenchyma (Translucent warm grey)
    - Scalar [0.35 - 0.65]: Functional cortex & vascular tree (Cobalt blue to amber)
    - Scalar [0.65 - 1.00]: Eloquent margin / Infiltrating tumor core (Fluorescent magenta/red)
    """
    if scalar < 0.08:
        return np.array([0.0, 0.0, 0.0]), 0.0
    elif scalar < 0.35:
        # Brain parenchyma
        t = (scalar - 0.08) / (0.35 - 0.08)
        color = np.array([0.7, 0.65, 0.75]) * (0.4 + 0.6 * t)
        alpha = 0.03 * t
        return color, alpha
    elif scalar < 0.65:
        # Microvascular & functional tract
        t = (scalar - 0.35) / (0.65 - 0.35)
        color = np.array([0.0, 0.8, 1.0]) * (1.0 - t) + np.array([1.0, 0.8, 0.0]) * t
        alpha = 0.18 + 0.12 * t
        return color, alpha
    else:
        # High-metabolic tumor core & critical margin
        t = (scalar - 0.65) / (1.0 - 0.65)
        color = np.array([1.0, 0.1, 0.4]) * (1.0 - t) + np.array([1.0, 0.0, 0.0]) * t
        alpha = 0.45 + 0.40 * t
        return color, alpha

# -------------------------------------------------------------------------
# 4. Ray-Casting Continuum Renderer (Discrete Integral Solver)
# -------------------------------------------------------------------------

def render_volume_raycast(
    volume: ContinuumVolume,
    width: int = 400,
    height: int = 400,
    steps: int = 90,
    tau: float = 0.65,
    camera_yaw: float = 30.0,
    camera_pitch: float = 20.0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Executes Kaufman's Continuum Volume Rendering Integral via front-to-back ray compositing:
      C_out = C_in + (1 - alpha_in) * alpha_i * C_i
      alpha_out = alpha_in + (1 - alpha_in) * alpha_i

    Returns:
      rgb_image: (height, width, 3) in [0, 1]
      metacognition_map: (height, width) spatial confidence map
      stats: Telemetry dictionary including Accessible Volume A_tau(p)
    """
    yaw_rad = math.radians(camera_yaw)
    pitch_rad = math.radians(camera_pitch)

    # Camera rotation matrix
    cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
    cos_p, sin_p = math.cos(pitch_rad), math.sin(pitch_rad)

    # Ray direction in world space
    ray_dir = np.array([
        sin_y * cos_p,
        -sin_p,
        cos_y * cos_p
    ])
    ray_dir /= np.linalg.norm(ray_dir)

    # Camera axes
    right = np.array([cos_y, 0.0, -sin_y])
    up = np.cross(ray_dir, right)
    up /= np.linalg.norm(up)

    image = np.zeros((height, width, 3), dtype=np.float32)
    meta_map = np.zeros((height, width), dtype=np.float32)

    ds = 2.4 / steps
    t_vals = np.linspace(-1.2, 1.2, steps)

    u_lin = np.linspace(-1.0, 1.0, width)
    v_lin = np.linspace(-1.0, 1.0, height)

    for j, v in enumerate(v_lin):
        for i, u in enumerate(u_lin):
            # Ray origin on view plane
            ray_origin = right * u + up * v
            acc_color = np.array([0.05, 0.05, 0.08]) # Dark clinical backdrop
            acc_alpha = 0.0
            acc_confidence = 0.0
            weight_sum = 0.0

            for t in t_vals:
                pos = ray_origin + ray_dir * t
                density, conf = volume.sample_trilinear(pos[0], pos[1], pos[2])

                if density > 0.01:
                    c_i, a_i = transfer_function_neurosurg(density)
                    # Front-to-back compositing
                    weight = (1.0 - acc_alpha) * a_i
                    acc_color += weight * c_i
                    acc_alpha += weight
                    acc_confidence += weight * conf
                    weight_sum += weight

                    if acc_alpha >= 0.96:
                        break # Early ray termination

            image[j, i] = np.clip(acc_color, 0.0, 1.0)
            meta_map[j, i] = (acc_confidence / weight_sum) if weight_sum > 0 else 0.0

    # Calculate operational metacognition metric over entire volume
    a_count, a_frac = accessible_volume(volume.confidence, tau)

    stats = {
        "accessible_volume_count": a_count,
        "accessible_volume_fraction": a_frac,
        "tau_threshold": tau,
        "total_voxels": volume.confidence.size,
    }

    return image, meta_map, stats

# -------------------------------------------------------------------------
# 5. Tensor Hyperstreamline Generator (Crafts-Delmarcelle Tracts)
# -------------------------------------------------------------------------

def generate_hyperstreamline_tracts(n_points: int = 150) -> List[Dict[str, np.ndarray]]:
    """
    Computes analytical 3D hyperstreamline trajectories modeling the
    optic chiasm decussation and visual radiations.
    """
    s = np.linspace(-1.5, 1.5, n_points)
    tracts = []

    # Tract 1: Left optic nerve -> Chiasm decussation -> Right visual radiation
    x1 = np.where(s < 0, -0.6 - 0.4 * s, 0.4 * s)
    y1 = np.sin(s * 1.5) * 0.25
    z1 = -0.3 + 0.15 * np.cos(s * 2.0)
    tracts.append({
        "name": "Left-to-Right Decussating Pathway (Medial Chiasm)",
        "points": np.stack([x1, y1, z1], axis=1),
        "color": np.array([0.0, 0.85, 1.0]), # Cyan/Blue
    })

    # Tract 2: Right optic nerve -> Chiasm decussation -> Left visual radiation
    x2 = np.where(s < 0, 0.6 + 0.4 * s, -0.4 * s)
    y2 = -np.sin(s * 1.5) * 0.25
    z2 = -0.3 + 0.15 * np.cos(s * 2.0)
    tracts.append({
        "name": "Right-to-Left Decussating Pathway (Medial Chiasm)",
        "points": np.stack([x2, y2, z2], axis=1),
        "color": np.array([1.0, 0.75, 0.0]), # Amber Gold
    })

    return tracts

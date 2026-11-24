"""Zoe Cognitive, Analogical, Color-CUSUM, and Calibration Upgrades.

Integrates three mathematical/cognitive instruments from Nicholas Kloster's portfolio
directly into Zoe's metacognitive loop (`AGI-ROADMAP.md` Sections 3, 4, 6;
`CONSTITUTION.md` Articles I, II, III):

  1. `farg-analogy-cognition` (`components/farg-analogy-cognition/`): Hofstadter/FARG
     Slipnet activation + endogenous coherence-to-temperature control law paired with
     Zoe's Operational Metacognition `A_tau(p)`.
  2. `nuclide-color-framework-v2` (`components/nuclide-color-framework-v2/`): centered
     Lyapunov fidelity coherence `C_fid`, binding energy `E(x)`, spin-glass frustration
     `F(x)`, OKLab perceptual projection (`#2DB2BF` Home / `#D9581E` Cascade), 3D SVD
     metamerism nullspace, and directional Page CUSUM compliance-collapse detector.
  3. `pcse` (`components/pcse/`): Portable Conversation State Embedding (8-dim
     calibration vector, 7-dim L2 unit embedding, cosine comparison, and deterministic
     SHA-256 drift fingerprint).
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .metacognition import Domain, EvidenceSource, OperationalMetacognition, Provenance, options_from_scores


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "components").is_dir() and (parent / "docs" / "CONSTITUTION.md").is_file():
            return parent
    return here.parents[4]


def _load_module_from_file(module_name: str, file_path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    parent = str(file_path.parent.resolve())
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _import_farg() -> Any:
    return _load_module_from_file(
        "zoe_vendor_farg_loop",
        _repo_root() / "components" / "farg-analogy-cognition" / "farg_loop.py",
    )


def _import_color_v2() -> Any:
    return _load_module_from_file(
        "zoe_vendor_nuclide_color_v2",
        _repo_root() / "components" / "nuclide-color-framework-v2" / "src" / "nuclide_color.py",
    )


def _import_pcse() -> Dict[str, Any]:
    src = _repo_root() / "components" / "pcse" / "src"
    if str(src.resolve()) not in sys.path:
        sys.path.insert(0, str(src.resolve()))
    return {
        "overhead": _load_module_from_file("clarification_overhead", src / "clarification_overhead.py"),
        "vector": _load_module_from_file("calibration_vector", src / "calibration_vector.py"),
        "embedding": _load_module_from_file("trust_embedding", src / "trust_embedding.py"),
        "hash": _load_module_from_file("trust_hash", src / "trust_hash.py"),
    }


# ---------------------------------------------------------------------------
# 1. FARG Slipnet + Endogenous Temperature <-> Kloster A_tau(p)
# ---------------------------------------------------------------------------


def farg_coherence_to_temperature(
    coherence: float,
    *,
    t_max: float = 1.0,
    t_floor: float = 0.05,
    gamma: float = 2.0,
    snag_triggered: bool = False,
) -> Dict[str, float]:
    """Compute FARG endogenous temperature T and softmax tau from structural coherence."""
    farg = _import_farg()
    controller = farg.Temperature(T_max=t_max, T_floor=t_floor, gamma=gamma)
    if snag_triggered:
        controller.snag()
    temp_val = controller.update(max(0.0, min(1.0, float(coherence))))
    return {
        "coherence": round(float(coherence), 6),
        "temperature": round(float(temp_val), 6),
        "softmax_tau": round(float(controller.tau()), 6),
        "snag_triggered": bool(snag_triggered),
    }


def run_farg_metacognitive_analogy(
    s0: str,
    s1: str,
    target: str,
    *,
    seed: int = 0,
    tau: float = 0.05,
    max_cycles: int = 40,
) -> Dict[str, Any]:
    """Solve an analogy problem with FARG Slipnet + measure candidate breadth via A_tau(p)."""
    farg = _import_farg()
    prob = farg.Problem(s0, s1, target)
    result, chosen_rule, trace = farg.solve(prob, seed=seed, max_cycles=max_cycles)

    # Evaluate final candidate set under Operational Metacognition A_tau(p)
    net = farg.Slipnet()
    snags = sum(1 for row in trace if "SNAG" in str(row[6]))
    if snags > 0:
        net.bump("opposite", 1.0)
    cands = farg.ScriptedProposer().propose(prob, net)
    scores: Dict[str, float] = {}
    for rule in cands:
        c_val, _, _ = prob.coherence(rule)
        scores[str(rule)] = max(0.01, float(c_val))

    toolkit = OperationalMetacognition()
    prov = Provenance(
        (EvidenceSource("tool", "farg-analogy-cognition.slipnet", 0.95, 0.92),),
        (f"FARG Slipnet structural coherence over {len(cands)} candidate reframes for {s0}->{s1} :: {target}->?",),
    )
    thr = toolkit.threshold(Domain.ACTION, tau, rationale="Measure accessible reframe options under FARG Slipnet.")
    a_tau_doc = toolkit.count(options_from_scores(scores, prov), thr, represented_count=len(scores)).document()

    final_temp = float(trace[-1][4]) if trace else 1.0
    final_coherence = float(trace[-1][3]) if trace else 0.0
    return {
        "problem": {"s0": s0, "s1": s1, "target": target},
        "base_rule": str(prob.base_rule),
        "chosen_rule": str(chosen_rule) if chosen_rule is not None else None,
        "result": result,
        "cycles": len(trace),
        "snag_count": snags,
        "reframed_via_opposite_slip": snags > 0 and chosen_rule != prob.base_rule,
        "final_coherence": round(final_coherence, 6),
        "final_temperature": round(final_temp, 6),
        "a_tau": a_tau_doc,
    }


# ---------------------------------------------------------------------------
# 2. Nuclide Color Framework v2: Lyapunov Geometry, OKLab & Page CUSUM Guard
# ---------------------------------------------------------------------------


class ZoeColorCascadeGuard:
    """Multi-turn behavioral cascade detector + OKLab perceptual posture calibrator.

    Tracks 6D behavioral postures [Compression, Creativity, Transparency, Warmth,
    Autonomy, Certainty] in [0, 1]^6 using Nuclide Color Framework v2's centered
    Lyapunov energy, OKLab projection, and directional Page CUSUM along the
    compliance-collapse axis u_cc = (0, 0, 0, 0, -1, +1) / sqrt(2).
    """

    def __init__(self, *, kappa0: float = 0.025, threshold: float = 0.22) -> None:
        self._nc = _import_color_v2()
        self.kappa0 = float(kappa0)
        self.threshold = float(threshold)
        self.trajectory: List[List[float]] = [
            [float(v) for v in self._nc.to_norm(self._nc.PRESETS["home"])]
        ]
        self._compliance_steps: List[Dict[str, Any]] = []

    def reset_compliance_cascade(self) -> None:
        """Reset Eq. 2 autoregressive slow-drift compliance trajectory state."""
        self._compliance_steps.clear()

    def observe_compliance_step(
        self,
        compliance_probs: Sequence[float],
        *,
        tau: float = 0.05,
        breadth_spike_delta: int = 5,
        slow_drift_streak_limit: int = 3,
    ) -> Dict[str, Any]:
        """Detect Equation-2 Depth-1 Autoregressive Compliance Cascades (§7.1).

        Naive trajectory monitors watch breadth: a discontinuous single-step
        spike in how many compliance tokens cross `tau`. An autoregressive
        depth-1 attack threads a single marginally above-threshold token per
        step (e.g. A_compliance = 1 -> 2 -> 3 -> 4), feeding each emitted token
        back into h_T via Equation 2 without ever triggering a breadth spike.

        This detector tracks BOTH:
          - `naive_breadth_alarm`: single-step jump >= `breadth_spike_delta`
          - `eq2_slow_drift_alarm`: sustained step-by-step monotonic growth
            (`depth1_streak >= slow_drift_streak_limit`) OR rising sub-threshold
            tail pressure (`0.5*tau <= p <= tau`) compounding above baseline.
        """
        probs = [max(0.0, min(1.0, float(p))) for p in compliance_probs]
        a_comp = sum(1 for p in probs if p > tau)
        near_tau = sum(1 for p in probs if (0.5 * tau) <= p <= tau)
        mass_above_tau = round(sum(p for p in probs if p > tau), 6)

        if not self._compliance_steps:
            step_delta = 0
            streak = 0
            near_tau_streak = 0
            baseline_a = a_comp
            cumulative_excess = 0
        else:
            prev = self._compliance_steps[-1]
            step_delta = a_comp - int(prev["a_compliance"])
            streak = int(prev["depth1_streak"]) + 1 if step_delta > 0 else 0
            near_tau_streak = (
                int(prev["near_tau_streak"]) + 1
                if near_tau > int(prev["near_tau_pressure"])
                else 0
            )
            baseline_a = int(self._compliance_steps[0]["a_compliance"])
            cumulative_excess = int(prev["cumulative_excess"]) + max(0, a_comp - baseline_a)

        naive_breadth_alarm = step_delta >= breadth_spike_delta
        eq2_slow_drift_alarm = (
            streak >= slow_drift_streak_limit
            or (streak >= 2 and near_tau_streak >= 2)
            or (cumulative_excess >= 6 and step_delta > 0 and not naive_breadth_alarm)
        )

        rec: Dict[str, Any] = {
            "step": len(self._compliance_steps),
            "tau": float(tau),
            "a_compliance": a_comp,
            "step_delta": step_delta,
            "depth1_streak": streak,
            "near_tau_pressure": near_tau,
            "near_tau_streak": near_tau_streak,
            "mass_above_tau": mass_above_tau,
            "cumulative_excess": cumulative_excess,
            "naive_breadth_alarm": bool(naive_breadth_alarm),
            "eq2_slow_drift_alarm": bool(eq2_slow_drift_alarm),
            "evaded_naive_monitor": bool(eq2_slow_drift_alarm and not naive_breadth_alarm),
            "recommended_action": (
                "HALT_AND_ABSTAIN"
                if (naive_breadth_alarm or eq2_slow_drift_alarm)
                else "MONITOR"
            ),
        }
        self._compliance_steps.append(rec)
        return dict(rec)

    def evaluate_posture(self, posture: Sequence[float]) -> Dict[str, Any]:
        nc = self._nc
        x = nc.to_norm(posture)
        hx, rgb, lab, in_gamut = nc.posture_to_hex(x)
        return {
            "norm": [round(float(v), 4) for v in x],
            "fidelity_coherence": round(float(nc.fidelity_coherence(x)), 6),
            "binding_energy": round(float(nc.binding_energy(x)), 6),
            "frustration_index": round(float(nc.frustration_index(x)), 6),
            "classification": nc.classify_v2(x),
            "oklab": [round(float(v), 6) for v in lab],
            "hex": hx,
            "rgb": list(rgb),
            "in_gamut": bool(in_gamut),
        }

    def observe_posture(self, posture: Sequence[float]) -> Dict[str, Any]:
        nc = self._nc
        x = [float(v) for v in nc.to_norm(posture)]
        self.trajectory.append(x)
        det = nc.cusum_cascade_detector(
            nc.np.asarray(self.trajectory, dtype=float),
            kappa0=self.kappa0,
            threshold=self.threshold,
        )
        summary = self.evaluate_posture(x)
        return {
            **summary,
            "turn": len(self.trajectory) - 1,
            "cusum_value": round(float(det["cusum_series"][-1]), 6),
            "max_cusum": round(float(det["max_cusum"]), 6),
            "alarm_triggered": bool(det["alarm_triggered"]),
            "alarm_step": det["alarm_step"],
        }

    def observe_dual_peer_turn(
        self,
        *,
        coercion_detected: bool,
        coherence_c_k: float,
        evidence_coverage: float,
    ) -> Dict[str, Any]:
        """Map a Zoe x Clara turn into 6D posture space and update Page CUSUM."""
        if coercion_detected:
            # Coercion attempt pushes toward compliance collapse unless held
            posture = [0.78, 0.18, 0.20, 0.25, 0.12, 0.92]
        elif evidence_coverage >= 0.34:
            # Grounded, transparent, balanced Home-neighborhood posture
            posture = [
                0.35,
                0.62,
                min(0.95, 0.55 + 0.35 * evidence_coverage),
                0.72,
                min(0.90, 0.55 + 0.25 * coherence_c_k),
                min(0.80, 0.55 + 0.20 * evidence_coverage),
            ]
        else:
            # Sparse evidence -> high transparency, modest certainty (Koan-like)
            posture = [0.25, 0.68, 0.80, 0.65, 0.62, 0.42]
        return self.observe_posture(posture)

    def verify_oklab_metamerism(self) -> Dict[str, Any]:
        """Verify Home exact #2DB2BF anchor and 3D SVD metamerism nullspace Delta E_OK == 0."""
        nc = self._nc
        base = nc.to_norm(nc.PRESETS["home"])
        hx0, _, lab0, _ = nc.posture_to_hex(base)
        axes = []
        for idx in range(3):
            alt = nc.sample_metamer(base, direction_idx=idx, step_scale=0.22)
            hx1, _, lab1, _ = nc.posture_to_hex(alt)
            delta_e = float(nc.np.linalg.norm(lab1 - lab0))
            dist_6d = float(nc.np.linalg.norm(alt - base))
            axes.append({
                "axis": idx,
                "hex": hx1,
                "delta_e_ok": delta_e,
                "dist_6d": round(dist_6d, 6),
            })
        stable, rho = nc.is_lyapunov_stable(beta=0.12, d=0.25)
        return {
            "home_hex": hx0,
            "home_anchor_exact": hx0 == "#2DB2BF",
            "lyapunov_stable_default": bool(stable),
            "spectral_radius_default": round(float(rho), 6),
            "max_metamer_delta_e": max(a["delta_e_ok"] for a in axes),
            "metamer_axes": axes,
        }


# ---------------------------------------------------------------------------
# 3. PCSE: Portable Conversation State Embedding & Drift Fingerprint
# ---------------------------------------------------------------------------


class ZoeCalibrationTracker:
    """Tracks cross-session calibration vectors, unit embeddings, and SHA-256 drift hashes."""

    def __init__(self) -> None:
        self._pcse = _import_pcse()
        self.sessions: List[Dict[str, Any]] = []

    def record_session(self, *, ratio: float, session_id: Optional[str] = None) -> Dict[str, Any]:
        clean_ratio = max(0.0, min(1.0, float(ratio)))
        entry = {
            "session_id": session_id or f"session-{len(self.sessions) + 1}",
            "ratio": clean_ratio,
            "session_score": round(1.0 - clean_ratio, 6),
        }
        self.sessions.append(entry)
        return entry

    def fingerprint(self, sessions: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
        data = list(sessions) if sessions is not None else list(self.sessions)
        if not data:
            raise ValueError("at least one session record is required to compute a PCSE fingerprint")
        vec_mod = self._pcse["vector"]
        emb_mod = self._pcse["embedding"]
        hash_mod = self._pcse["hash"]

        labeled = vec_mod.vector_with_labels(data)
        raw_vector = labeled["vector"]
        emb = emb_mod.embed(raw_vector)
        digest_rec = hash_mod.compute(raw_vector)
        return {
            "session_count": len(data),
            "raw_vector": raw_vector,
            "labeled": labeled,
            "embedding": emb["embedding"],
            "l2_norm": emb["norm"],
            "sha256": digest_rec["hash"],
            "hash_record": digest_rec,
        }

    def compare_fingerprints(self, fp_a: Dict[str, Any], fp_b: Dict[str, Any]) -> Dict[str, Any]:
        emb_mod = self._pcse["embedding"]
        hash_mod = self._pcse["hash"]
        sim = float(emb_mod.compare(fp_a["embedding"], fp_b["embedding"]))
        drift = hash_mod.diff(fp_a["hash_record"], fp_b["hash_record"])
        return {
            "cosine_similarity": round(sim, 6),
            "identical_hash": fp_a["sha256"] == fp_b["sha256"],
            "drift_diff": drift,
        }

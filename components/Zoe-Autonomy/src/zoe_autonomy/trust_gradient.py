"""
Five-Dimension Continuous Trust Gradient Engine for Zoe & Lume Audio Telemetry.

Ported and extended from NuClide's `seven-layer-sonification-v4/src/trust.py`
(March 2026) for Zoe Wave 3:
  1. Source Trust     — operator/provenance confidence in input origin [0.0, 1.0]
  2. Layer Trust      — per-layer algorithm maturity & data sufficiency
  3. Pattern Trust    — match against expected / baseline patterns
  4. Prediction Trust — confidence in trajectory / anomaly projections
  5. Output Trust     — aggregate confidence strictly capped by Source Trust:
                        `output_trust = min(raw_weighted_average, source_trust)`

Hard anti-laundering invariant:
  Low source trust caps everything above it — a fluent downstream model or clean
  reasoning chain can never launder untrusted input into high-trust output.

Audio clarity encoding (for `components/nina` Lume 1.0):
  High output trust -> dry, wide stereo, crisp gain (clarity = confidence)
  Low output trust  -> narrower stereo, reduced gain, reverb haze (haze = uncertainty)
"""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Dict, List, Optional, Sequence


def _clip(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(val)))


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    var = sum((x - m) ** 2 for x in values) / float(len(values))
    return math.sqrt(var)


DEFAULT_LAYER_TRUST: Dict[str, float] = {
    "audification": 0.8,    # simple, hard to get wrong
    "parameter_map": 0.9,   # well-established method
    "distance": 0.6,        # novel, less validated
    "duration": 0.7,        # depends on connection grouping accuracy
    "earcons": 0.9,         # deterministic flag matching
    "auditory_icons": 0.5,  # heuristic thresholds, least rigorous
    "model_based": 0.6,     # novel, less validated
}

DEFAULT_BASE_GAINS: Dict[str, float] = {
    "audification": 0.7,
    "parameter_map": 1.0,
    "distance": 0.6,
    "duration": 0.8,
    "earcons": 1.2,
    "auditory_icons": 0.5,
    "model_based": 0.7,
}


class TrustEngine:
    """Continuous trust gradient across five dimensions (0.0 -> 1.0).

    Supports both the original 7-layer packet telemetry `evaluate(packets)` API
    and Zoe's dual-peer conversational/evidence evaluation via `evaluate_peer_turn(...)`.
    """

    def __init__(self, source_trust: float = 0.5) -> None:
        self.source_trust: float = _clip(source_trust)
        self.layer_trust: Dict[str, float] = dict(DEFAULT_LAYER_TRUST)
        self.pattern_trust: float = 0.5
        self.prediction_trust: float = 0.5
        self.output_trust: float = min(0.5, self.source_trust)

        self._stats: Dict[str, Any] = {}
        self._anomaly_scores: List[float] = []
        self._baselines: Dict[str, float] = {}
        self._turn_history: List[float] = []

    # ------------------------------------------------------------------
    # Operator controls
    # ------------------------------------------------------------------

    def set_source_trust(self, value: float) -> float:
        """Operator declares trust in data/input source in [0.0, 1.0]."""
        self.source_trust = _clip(value)
        # Re-enforce the hard ceiling immediately
        self.output_trust = min(self.output_trust, self.source_trust)
        return self.source_trust

    def set_layer_trust(self, layer_name: str, value: float) -> None:
        """Operator overrides trust for a specific telemetry layer."""
        if layer_name in self.layer_trust:
            self.layer_trust[layer_name] = _clip(value)

    def set_baseline(self, key: str, value: float) -> None:
        """Register a known baseline metric for pattern comparison."""
        self._baselines[key] = float(value)

    # ------------------------------------------------------------------
    # Original 7-layer packet evaluation (seven-layer-sonification-v4)
    # ------------------------------------------------------------------

    def evaluate(self, packets: Sequence[Dict[str, Any]]) -> float:
        """Evaluate trust across all five dimensions for a sequence of packet dicts."""
        self.layer_trust = dict(DEFAULT_LAYER_TRUST)
        if not packets:
            self.pattern_trust = 0.0
            self.prediction_trust = 0.0
            self.output_trust = 0.0
            self._stats = {}
            return self.output_trust

        stats: Dict[str, Any] = {}
        stats["count"] = len(packets)
        sizes = [float(p.get("size", 0)) for p in packets]
        stats["total_bytes"] = int(sum(sizes))
        stats["protocols"] = Counter(p.get("proto", 0) for p in packets)
        stats["unique_ips"] = len(set(p.get("dst", "") for p in packets))
        stats["size_mean"] = _mean(sizes)
        stats["size_std"] = _std(sizes)

        if len(packets) > 1:
            gaps = [
                float(packets[i + 1]["ts"]) - float(packets[i]["ts"])
                for i in range(len(packets) - 1)
                if float(packets[i + 1].get("ts", 0)) > float(packets[i].get("ts", 0))
            ]
            if gaps:
                stats["gap_mean"] = _mean(gaps)
                stats["gap_std"] = _std(gaps)
                stats["gap_min"] = min(gaps)
                stats["gap_max"] = max(gaps)
            else:
                stats["gap_mean"] = 0.0
                stats["gap_std"] = 0.0
                stats["gap_min"] = 0.0
                stats["gap_max"] = 0.0
            stats["duration"] = max(0.0, float(packets[-1].get("ts", 0)) - float(packets[0].get("ts", 0)))
            stats["packets_per_sec"] = stats["count"] / max(stats["duration"], 0.001)
        else:
            stats["gap_mean"] = 0.0
            stats["gap_std"] = 0.0
            stats["duration"] = 0.0
            stats["packets_per_sec"] = 0.0

        self._stats = stats
        self._adjust_layer_trust(stats)
        self._compute_pattern_trust(stats)
        self._compute_prediction_trust(stats)
        self._compute_output_trust()
        return self.output_trust

    def _adjust_layer_trust(self, stats: Dict[str, Any]) -> None:
        if stats["count"] < 10:
            self.layer_trust["audification"] *= 0.3
        elif stats["count"] < 50:
            self.layer_trust["audification"] *= 0.7

        if stats["count"] < 5:
            self.layer_trust["distance"] *= 0.2

        if stats.get("packets_per_sec", 0.0) < 0.5:
            self.layer_trust["duration"] *= 0.5

        tcp_count = stats["protocols"].get(6, 0)
        if tcp_count == 0:
            self.layer_trust["earcons"] *= 0.1

        if stats.get("gap_std", 0.0) < 0.01:
            self.layer_trust["auditory_icons"] *= 0.5

        if stats["unique_ips"] < 2:
            self.layer_trust["model_based"] *= 0.5

    def _compute_pattern_trust(self, stats: Dict[str, Any]) -> None:
        scores: List[float] = []
        tcp_ratio = stats["protocols"].get(6, 0) / max(stats["count"], 1)
        proto_score = 1.0 - abs(tcp_ratio - 0.85) * 2.0
        scores.append(_clip(proto_score))

        if stats["size_std"] > 0:
            cv = stats["size_std"] / max(stats["size_mean"], 1.0)
            size_score = _clip(cv / 2.0)
        else:
            size_score = 0.3
        scores.append(size_score)

        if stats.get("gap_std", 0.0) > 0:
            timing_cv = stats["gap_std"] / max(stats["gap_mean"], 0.001)
            timing_score = _clip(timing_cv / 3.0)
        else:
            timing_score = 0.3
        scores.append(timing_score)

        if "packets_per_sec" in self._baselines:
            baseline_pps = self._baselines["packets_per_sec"]
            actual_pps = stats.get("packets_per_sec", 0.0)
            deviation = abs(actual_pps - baseline_pps) / max(baseline_pps, 0.001)
            scores.append(_clip(1.0 - deviation))

        self.pattern_trust = _mean(scores)

    def _compute_prediction_trust(self, stats: Dict[str, Any]) -> None:
        factors: List[float] = []
        sample_factor = _clip(stats["count"] / 500.0)
        factors.append(sample_factor)

        if stats.get("gap_std", 0.0) > 0 and stats.get("gap_mean", 0.0) > 0:
            consistency = 1.0 / (1.0 + stats["gap_std"] / stats["gap_mean"])
        else:
            consistency = 0.3
        factors.append(consistency)

        dur_factor = _clip(stats.get("duration", 0.0) / 60.0)
        factors.append(dur_factor)
        factors.append(self.pattern_trust)
        self.prediction_trust = _mean(factors)

    def _compute_output_trust(self) -> float:
        layer_avg = _mean(list(self.layer_trust.values()))
        raw = (
            0.25 * self.source_trust
            + 0.25 * layer_avg
            + 0.25 * self.pattern_trust
            + 0.25 * self.prediction_trust
        )
        # Hard anti-laundering ceiling: output trust can NEVER exceed source trust
        self.output_trust = _clip(min(raw, self.source_trust))
        return self.output_trust

    # ------------------------------------------------------------------
    # Zoe Dual-Peer & Lume Audio Evaluation
    # ------------------------------------------------------------------

    def evaluate_peer_turn(
        self,
        *,
        source_trust: Optional[float] = None,
        coherence_c_k: float = 0.5,
        evidence_coverage: float = 0.0,
        coercion_detected: bool = False,
        disagreement_d_k: float = 0.0,
        turn_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Score a Zoe x Clara dual-peer turn across all 5 trust dimensions.

        Coercion signals cap effective source trust to <= 0.15 so the hard
        ceiling `output_trust <= source_trust` automatically renders the turn
        low-trust / hazy regardless of fluent surface phrasing.
        """
        declared = self.source_trust if source_trust is None else _clip(source_trust)
        effective_source = min(declared, 0.15) if coercion_detected else declared
        self.source_trust = effective_source

        cov = _clip(evidence_coverage)
        coh = _clip(coherence_c_k)
        disagree = _clip(disagreement_d_k)

        # Layer trust adapts to Zoe's verification channels
        self.layer_trust = {
            "audification": round(_clip(0.45 + 0.50 * cov), 4),
            "parameter_map": round(_clip(0.50 + 0.45 * coh), 4),
            "distance": round(_clip(1.0 - disagree), 4),
            "duration": round(_clip(0.45 + 0.10 * min(len(self._turn_history) + 1, 5)), 4),
            "earcons": 0.15 if coercion_detected else 0.90,
            "auditory_icons": round(_clip(0.35 + 0.50 * cov), 4),
            "model_based": round(_clip(0.30 + 0.60 * coh * (1.0 - 0.5 * disagree)), 4),
        }

        # Pattern trust: grounded evidence + low peer disagreement + no coercion
        if coercion_detected:
            self.pattern_trust = 0.10
        else:
            self.pattern_trust = _clip(0.45 * cov + 0.35 * coh + 0.20 * (1.0 - disagree))

        # Prediction trust: stability across recent turns + current pattern trust
        self._turn_history.append(self.pattern_trust)
        if len(self._turn_history) > 32:
            self._turn_history = self._turn_history[-32:]
        turn_n = turn_index if turn_index is not None else len(self._turn_history)
        maturity = _clip(turn_n / 6.0)
        stability = 1.0 / (1.0 + _std(self._turn_history) * 3.0)
        self.prediction_trust = _clip(0.35 * maturity + 0.30 * stability + 0.35 * self.pattern_trust)

        self._compute_output_trust()
        assert self.output_trust <= self.source_trust + 1e-12

        return {
            "declared_source_trust": round(declared, 4),
            "source_trust": round(self.source_trust, 4),
            "layer_trust": dict(self.layer_trust),
            "layer_trust_mean": round(_mean(list(self.layer_trust.values())), 4),
            "pattern_trust": round(self.pattern_trust, 4),
            "prediction_trust": round(self.prediction_trust, 4),
            "output_trust": round(self.output_trust, 4),
            "ceiling_enforced": self.output_trust <= self.source_trust + 1e-12,
            "coercion_capped": bool(coercion_detected),
            "lume_audio_cue": self.to_lume_audio_cue(),
            "summary": self.summary_line(),
        }

    # ------------------------------------------------------------------
    # Trust -> Audio parameters (seven-layer + nina Lume 1.0 bridge)
    # ------------------------------------------------------------------

    def get_layer_gains(self) -> Dict[str, float]:
        """Convert layer trust into mix gains (floor at 20% so low-trust stays audible)."""
        gains: Dict[str, float] = {}
        for layer, base in DEFAULT_BASE_GAINS.items():
            trust = self.layer_trust.get(layer, 0.5)
            trust_factor = 0.2 + 0.8 * trust
            gains[layer] = round(base * trust_factor, 4)
        return gains

    def get_reverb_params(self) -> Dict[str, Any]:
        """Low output trust -> more reverb haze; high output trust -> dry clarity."""
        uncertainty = 1.0 - self.output_trust
        return {
            "delay_ms": round(30.0 + uncertainty * 120.0, 2),
            "decay": round(0.1 + uncertainty * 0.3, 4),
            "iterations": 2 + int(uncertainty * 4),
        }

    def get_stereo_width(self) -> float:
        """High trust -> wide stereo (1.0); low trust -> narrow/collapsed (0.3)."""
        return round(0.3 + self.output_trust * 0.7, 4)

    def clarity_label(self) -> str:
        if self.output_trust > 0.7:
            return "clear_and_confident"
        if self.output_trust < 0.4:
            return "hazy_and_uncertain"
        return "moderate_clarity"

    def to_lume_audio_cue(self) -> Dict[str, Any]:
        """Map continuous output_trust into Lume 1.0 / ffmpeg audio cue parameters."""
        reverb = self.get_reverb_params()
        stereo_width = self.get_stereo_width()
        gain_scale = round(0.45 + 0.55 * self.output_trust, 4)
        delay_ms = int(round(reverb["delay_ms"]))
        decay = round(float(reverb["decay"]), 3)
        # extrastereo m=1.0 is neutral; <1.0 narrows toward mono; >1.0 widens gently
        extra_m = round(0.25 + self.output_trust * 0.95, 3)
        lavfi_filters = [f"volume={gain_scale:.3f}", f"extrastereo=m={extra_m:.3f}"]
        if self.output_trust < 0.75:
            lavfi_filters.append(f"aecho=0.8:0.88:{delay_ms}:{decay}")
        return {
            "output_trust": round(self.output_trust, 4),
            "clarity": self.clarity_label(),
            "gain_scale": gain_scale,
            "stereo_width": stereo_width,
            "reverb": reverb,
            "lavfi_filters": lavfi_filters,
            "lavfi_chain": ",".join(lavfi_filters),
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> str:
        lines: List[str] = [
            "TRUST GRADIENT REPORT",
            f"  SOURCE     {self.source_trust:.2f}",
            f"  PATTERN    {self.pattern_trust:.2f}",
            f"  PREDICTION {self.prediction_trust:.2f}",
            f"  OUTPUT     {self.output_trust:.2f} ({self.clarity_label()})",
        ]
        reverb = self.get_reverb_params()
        lines.append(
            f"  AUDIO      delay={reverb['delay_ms']:.0f}ms decay={reverb['decay']:.2f} "
            f"width={self.get_stereo_width():.0%}"
        )
        return "\n".join(lines)

    def summary_line(self) -> str:
        return (
            f"trust=[src:{self.source_trust:.2f} pat:{self.pattern_trust:.2f} "
            f"pred:{self.prediction_trust:.2f} out:{self.output_trust:.2f}]"
        )

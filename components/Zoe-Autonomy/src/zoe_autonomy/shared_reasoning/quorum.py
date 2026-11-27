"""Architecture #4: Theorem 15 Anti-Echo-Chamber Four-Peer Quorum.

Collects independent simplex confidence vectors from four heterogeneous voices:
  - ``zoe`` (Zoe Observatory Lead)
  - ``clara`` (Clara Epistemic Balance Peer)
  - ``antigravity`` (Google Antigravity SDK / frontier or loopback reasoning voice)
  - ``user`` (Human operator / high-leverage steering prior)

Each peer vector carries explicit provenance (``source_kind``, ``provenance_id``)
and an ``independence_tag`` so the engine detects:
  1. Zero-diversity or near-identical cloned echo chambers (``ECHO_CHAMBER_WARNING``).
  2. Missing or colliding provenance / independence tags.
  3. Rogue-node or Byzantine outlier contamination (low Kloster coherence ``C_K`` -> ``ABSTAIN``).
  4. Exact Theorem 15 identities: pairwise Kloster-Jensen disagreement ``D_K``,
     ground-truth-independent Brier wisdom-of-crowds error contraction, and
     coherence ratio ``C_K``.

Integrates directly with ``stem_layering.arbitrate_teamwork_quorum``,
``stem_layering.route_stem(..., quorum_distributions=..., quorum_weights=...)``,
``zoe_clara.evaluate_dual_peer_balance``, and
``guiai.gem.kloster_multi_agent_consensus.evaluate_consensus_arbitration``.

Enforces ``docs/CONSTITUTION.md`` boundaries (``external_actions=0``,
``sentience_claimed=False``, ``l5_agi_qualified=False``, ``zoe_clone_claimed=False``;
Operational Metacognition A_tau(p) attributed to Nicholas Michael Kloster).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import math
from typing import TYPE_CHECKING, Any, Union

from ..metacognition import (
    SOURCE_KINDS,
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    options_from_probabilities,
)
from ..stem_layering import (
    DEFAULT_LOCAL_QWEN_URL,
    DEFAULT_TAU as DEFAULT_STEM_TAU,
    TIER_ORDER,
    StemDecision,
    _load_consensus_arbitrator,
    arbitrate_teamwork_quorum,
    constitutional_flags,
    route_stem,
)

if TYPE_CHECKING:
    from .blackboard import EpistemicBlackboard

QUORUM_CONTRACT = "zoe-shared-reasoning-quorum/v1"
ATTRIBUTION_TEXT = "Nicholas Michael Kloster, March 6, 2026"
DEFAULT_TAU = 0.05

DEFAULT_FOUR_PEERS: tuple[str, ...] = ("zoe", "clara", "antigravity", "user")
ACTION_LABELS: tuple[str, ...] = ("answer_grounded", "gather_more", "abstain")
STEM_TIER_LABELS: tuple[str, ...] = tuple(TIER_ORDER)

VALID_SOURCE_KINDS: frozenset[str] = frozenset(SOURCE_KINDS) | frozenset(
    {"model", "peer", "heuristic", "human", "verifier"}
)

_METACOG_KIND_MAP: dict[str, str] = {
    "model": "system",
    "peer": "tool",
    "heuristic": "prior",
    "human": "user",
    "verifier": "tool",
}

_DEFAULT_SOURCE_KINDS: dict[str, str] = {
    "zoe": "document",
    "clara": "validated_reflection",
    "antigravity": "model",
    "user": "user",
}


def quorum_constitutional_metadata(*, cloud_tokens_used: int = 0) -> dict[str, Any]:
    """Return canonical CONSTITUTION.md metadata for four-peer quorum decisions."""
    flags = constitutional_flags(cloud_tokens_used=cloud_tokens_used)
    flags["attribution"] = ATTRIBUTION_TEXT
    return flags


def _clean_label(value: Any, name: str, *, allow_empty: bool = False, max_len: int = 128) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    cleaned = " ".join(value.split()).strip()
    if not allow_empty and not cleaned:
        raise ValueError(f"{name} must not be empty")
    if len(cleaned) > max_len:
        raise ValueError(f"{name} exceeds max length {max_len}")
    return cleaned


def _infer_labels(n_dim: int, explicit_labels: Sequence[str] | None) -> tuple[str, ...]:
    if explicit_labels is not None:
        cleaned = tuple(_clean_label(lbl, "label") for lbl in explicit_labels)
        if len(cleaned) != n_dim:
            raise ValueError(
                f"labels length ({len(cleaned)}) must match probabilities length ({n_dim})"
            )
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("labels must be unique")
        return cleaned
    if n_dim == len(ACTION_LABELS):
        return ACTION_LABELS
    if n_dim == len(STEM_TIER_LABELS):
        return STEM_TIER_LABELS
    return tuple(f"option_{idx}" for idx in range(n_dim))


def _validate_simplex_probabilities(
    raw: Sequence[float] | Mapping[str, float],
    explicit_labels: Sequence[str] | None,
) -> tuple[tuple[float, ...], tuple[str, ...]]:
    """Validate finite, nonnegative simplex probabilities summing to 1.0."""
    if isinstance(raw, Mapping):
        if not raw:
            raise ValueError("probabilities mapping must not be empty")
        cleaned_raw: dict[str, Any] = {}
        for raw_key, raw_val in raw.items():
            clean_key = _clean_label(raw_key, "label")
            if clean_key in cleaned_raw:
                raise ValueError(
                    f"duplicate probability label after normalization: {clean_key!r}"
                )
            cleaned_raw[clean_key] = raw_val
        if explicit_labels is not None:
            labels = _infer_labels(len(explicit_labels), explicit_labels)
            if set(cleaned_raw.keys()) != set(labels):
                raise ValueError(
                    f"probability keys {sorted(cleaned_raw.keys())} do not match expected labels {list(labels)}"
                )
            ordered_vals = [cleaned_raw[lbl] for lbl in labels]
        else:
            if set(cleaned_raw.keys()) == set(ACTION_LABELS):
                labels = ACTION_LABELS
            elif set(cleaned_raw.keys()) == set(STEM_TIER_LABELS):
                labels = STEM_TIER_LABELS
            else:
                labels = tuple(cleaned_raw.keys())
            ordered_vals = [cleaned_raw[lbl] for lbl in labels]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        if not raw:
            raise ValueError("probabilities sequence must not be empty")
        ordered_vals = list(raw)
        labels = _infer_labels(len(ordered_vals), explicit_labels)
    else:
        raise ValueError(
            "probabilities must be a Sequence[float] or Mapping[str, float]"
        )

    floats: list[float] = []
    for val in ordered_vals:
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"probability entry must be numeric, got {type(val).__name__}")
        fval = float(val)
        if not math.isfinite(fval):
            raise ValueError("probabilities must contain only finite numbers")
        if fval < 0.0:
            raise ValueError(f"probabilities must be nonnegative, got {fval}")
        floats.append(fval)

    total = math.fsum(floats)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-5):
        raise ValueError(f"probabilities must lie on the simplex (sum to 1.0), got sum={total:.8f}")

    # Normalize tiny rounding drift (<= 1e-5) so downstream calculations stay exact.
    normalized = tuple(x / total for x in floats)
    return normalized, labels


@dataclass(frozen=True, init=False)
class PeerConfidenceVector:
    """Validated simplex confidence vector from a single reasoning peer.

    Attributes:
        peer_id: Logical peer identifier (e.g. ``"zoe"``, ``"clara"``, ``"antigravity"``, ``"user"``).
        probabilities: Simplex probability vector over canonical routes or actions.
        source_kind: Origin class (e.g. ``"document"``, ``"validated_reflection"``, ``"model"``, ``"user"``).
        provenance_id: Explicit provenance identifier distinguishing this evidence stream.
        independence_tag: Explicit independence group/token; colliding or empty tags flag echo-chamber risk.
        labels: Canonical hypothesis/tier labels aligned with ``probabilities``.
        weight: Strictly positive peer weight prior to convex normalization.
        metadata: Optional JSON-safe contextual annotations.
    """

    peer_id: str
    probabilities: tuple[float, ...]
    source_kind: str
    provenance_id: str
    independence_tag: str
    labels: tuple[str, ...]
    weight: float
    metadata: dict[str, Any]

    def __init__(
        self,
        peer_id: str,
        probabilities: Sequence[float] | Mapping[str, float],
        source_kind: str,
        provenance_id: str,
        independence_tag: str,
        labels: Sequence[str] = (),
        weight: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        clean_peer = _clean_label(peer_id, "peer_id")
        clean_kind = _clean_label(source_kind, "source_kind")
        if clean_kind not in VALID_SOURCE_KINDS:
            raise ValueError(
                f"unknown source_kind {clean_kind!r}; expected one of {sorted(VALID_SOURCE_KINDS)}"
            )
        clean_prov = _clean_label(provenance_id or "", "provenance_id", allow_empty=True, max_len=256)
        clean_tag = _clean_label(independence_tag or "", "independence_tag", allow_empty=True, max_len=256)

        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError("weight must be a positive finite float")
        fweight = float(weight)
        if not math.isfinite(fweight) or fweight <= 0.0:
            raise ValueError(f"weight must be strictly positive and finite, got {weight!r}")

        explicit_labels = tuple(labels) if labels else None
        norm_probs, resolved_labels = _validate_simplex_probabilities(probabilities, explicit_labels)

        object.__setattr__(self, "peer_id", clean_peer)
        object.__setattr__(self, "source_kind", clean_kind)
        object.__setattr__(self, "provenance_id", clean_prov)
        object.__setattr__(self, "independence_tag", clean_tag)
        object.__setattr__(self, "weight", fweight)
        object.__setattr__(self, "probabilities", norm_probs)
        object.__setattr__(self, "labels", resolved_labels)
        object.__setattr__(self, "metadata", dict(metadata or {}))

    @property
    def n_dim(self) -> int:
        return len(self.probabilities)

    @property
    def has_independent_provenance(self) -> bool:
        """Return True when both provenance_id and independence_tag are explicitly populated."""
        return bool(self.provenance_id and self.independence_tag)

    def as_mapping(self) -> dict[str, float]:
        return {lbl: float(p) for lbl, p in zip(self.labels, self.probabilities)}

    def to_evidence_source(self, *, trust: float = 0.88, strength: float = 0.85) -> EvidenceSource:
        mapped_kind = _METACOG_KIND_MAP.get(self.source_kind, self.source_kind)
        ident = f"{self.peer_id}:{self.provenance_id or 'missing-provenance'}"
        return EvidenceSource(kind=mapped_kind, identifier=ident, trust=trust, strength=strength)

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "source_kind": self.source_kind,
            "provenance_id": self.provenance_id,
            "independence_tag": self.independence_tag,
            "has_independent_provenance": self.has_independent_provenance,
            "weight": self.weight,
            "labels": list(self.labels),
            "probabilities": [round(float(x), 8) for x in self.probabilities],
            "probability_map": {k: round(v, 8) for k, v in self.as_mapping().items()},
            "metadata": dict(self.metadata),
        }


PeerInput = Union[PeerConfidenceVector, Sequence[float], Mapping[str, float]]


@dataclass(frozen=True)
class FourPeerQuorumResult:
    """Complete Theorem 15 & Anti-Echo-Chamber evaluation across the 4-peer committee."""

    contract: str
    verdict: str
    reason: str
    recommended_action: str
    abstained: bool
    abstention_applied: bool
    escalate: bool
    quorum_met: bool
    echo_chamber_detected: bool
    rogue_node_detected: bool
    bluff_detected: bool
    coercion_blocked: bool
    independence_verified: bool
    provenance_complete: bool
    labels: tuple[str, ...]
    peer_ids: tuple[str, ...]
    vectors: tuple[PeerConfidenceVector, ...]
    normalized_weights: tuple[float, ...]
    consensus_p_bar: tuple[float, ...]
    consensus_map: dict[str, float]
    consensus_argmax: int
    consensus_label: str
    consensus_confidence: float
    tau: float
    a_tau_pool: int
    per_peer_a_tau: dict[str, int]
    m2_mean: float
    m2_pool: float
    d_k_disagreement: float
    d_k_pairwise: float
    brier_contraction: float
    brier_identity_verified: bool
    brier_identity_max_residual: float
    coherence_c_k: float
    jsd_nats: float
    pairwise_l2_sq: dict[str, float]
    rogue_peer_ids: tuple[str, ...]
    missing_peers: tuple[str, ...]
    missing_provenance_peers: tuple[str, ...]
    shared_provenance_groups: tuple[tuple[str, ...], ...]
    shared_independence_groups: tuple[tuple[str, ...], ...]
    cloned_peer_pairs: tuple[tuple[str, str], ...]
    effective_independent_peers: int
    theorem15_raw: dict[str, Any]
    teamwork_arbitration: dict[str, Any] | None
    constitutional: dict[str, Any]
    blackboard_records: dict[str, Any] | None = None

    def to_gem_spatial_ir(self, *, scene_id: str = "theorem15-quorum-gem-view") -> dict[str, Any]:
        """Export an Art. II.3 visual-only GEM Spatial IR summary of the 4-peer quorum."""
        from .gem_aes_vdi import GEM_ART_II_3_NOTICE

        return {
            "schema_version": 1,
            "id": str(scene_id),
            "title": "Theorem 15 Four-Peer Quorum GEM View",
            "canvas": {"width": 6400, "height": 3200},
            "objects": [
                {"id": "q_verdict", "type": "rectangle", "bounds": [100, 100, 6300, 1450], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "q_txt", "type": "text", "position": [240, 800], "text": f"Q:{self.verdict[:20]}", "size": 160, "fill": "black"},
                {"id": "q_metrics", "type": "rectangle", "bounds": [100, 1650, 6300, 3100], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "qm_txt", "type": "text", "position": [240, 2350], "text": f"DK={self.d_k_disagreement:.3f} CK={self.coherence_c_k:.2f}", "size": 160, "fill": "black"},
            ],
            "constraints": [
                {"type": "inside_canvas", "object": "*"},
                {"type": "nonoverlap", "objects": ["q_verdict", "q_metrics"]},
            ],
            "visual_evidence_only": True,
            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
            "constitutional": dict(self.constitutional),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "verdict": self.verdict,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "abstained": self.abstained,
            "abstention_applied": self.abstention_applied,
            "escalate": self.escalate,
            "quorum_met": self.quorum_met,
            "echo_chamber_detected": self.echo_chamber_detected,
            "rogue_node_detected": self.rogue_node_detected,
            "bluff_detected": self.bluff_detected,
            "coercion_blocked": self.coercion_blocked,
            "independence_verified": self.independence_verified,
            "provenance_complete": self.provenance_complete,
            "labels": list(self.labels),
            "peer_ids": list(self.peer_ids),
            "vectors": [v.to_dict() for v in self.vectors],
            "normalized_weights": [round(float(w), 8) for w in self.normalized_weights],
            "consensus_p_bar": [round(float(p), 8) for p in self.consensus_p_bar],
            "consensus_map": {k: round(float(v), 8) for k, v in self.consensus_map.items()},
            "consensus_argmax": self.consensus_argmax,
            "consensus_label": self.consensus_label,
            "consensus_confidence": round(float(self.consensus_confidence), 6),
            "tau": self.tau,
            "a_tau_pool": self.a_tau_pool,
            "per_peer_a_tau": dict(self.per_peer_a_tau),
            "m2_mean": round(float(self.m2_mean), 8),
            "m2_pool": round(float(self.m2_pool), 8),
            "d_k_disagreement": round(float(self.d_k_disagreement), 8),
            "d_k_pairwise": round(float(self.d_k_pairwise), 8),
            "brier_contraction": round(float(self.brier_contraction), 8),
            "brier_identity_verified": self.brier_identity_verified,
            "brier_identity_max_residual": self.brier_identity_max_residual,
            "coherence_c_k": round(float(self.coherence_c_k), 6),
            "jsd_nats": round(float(self.jsd_nats), 8),
            "pairwise_l2_sq": dict(self.pairwise_l2_sq),
            "rogue_peer_ids": list(self.rogue_peer_ids),
            "missing_peers": list(self.missing_peers),
            "missing_provenance_peers": list(self.missing_provenance_peers),
            "shared_provenance_groups": [list(g) for g in self.shared_provenance_groups],
            "shared_independence_groups": [list(g) for g in self.shared_independence_groups],
            "cloned_peer_pairs": [list(p) for p in self.cloned_peer_pairs],
            "effective_independent_peers": self.effective_independent_peers,
            "theorem15_raw": dict(self.theorem15_raw),
            "teamwork_arbitration": dict(self.teamwork_arbitration) if self.teamwork_arbitration is not None else None,
            "constitutional": dict(self.constitutional),
            "blackboard_records": dict(self.blackboard_records) if self.blackboard_records is not None else None,
        }


@dataclass(frozen=True)
class FourPeerRouteResult:
    """Result combining ``stem_layering.route_stem`` with 4-peer Theorem 15 quorum gating."""

    stem_decision: StemDecision
    quorum: FourPeerQuorumResult
    effective_teamwork_recommended: bool
    escalate: bool
    constitutional: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": QUORUM_CONTRACT,
            "selected_tier": self.stem_decision.selected_tier,
            "effective_teamwork_recommended": self.effective_teamwork_recommended,
            "escalate": self.escalate,
            "stem_decision": self.stem_decision.to_dict(),
            "quorum": self.quorum.to_dict(),
            "constitutional": dict(self.constitutional),
        }


def _compute_brier_identity_check(
    dists: Sequence[Sequence[float]],
    weights: Sequence[float],
    p_bar: Sequence[float],
    d_k: float,
) -> tuple[bool, float]:
    """Verify Theorem 15b Brier wisdom-of-crowds identity over all one-hot outcomes y."""
    n_dim = len(p_bar)
    if not dists or n_dim == 0:
        return True, 0.0
    max_res = 0.0
    for y_idx in range(n_dim):
        mean_brier = math.fsum(
            w * math.fsum((p[j] - (1.0 if j == y_idx else 0.0)) ** 2 for j in range(n_dim))
            for w, p in zip(weights, dists)
        )
        pool_brier = math.fsum((p_bar[j] - (1.0 if j == y_idx else 0.0)) ** 2 for j in range(n_dim))
        residual = abs((mean_brier - pool_brier) - d_k)
        if residual > max_res:
            max_res = residual
    return max_res <= 1e-6, round(max_res, 12)


def _count_independent_clusters(
    vectors: Sequence[PeerConfidenceVector],
    cloned_pairs: Sequence[tuple[str, str]],
    missing_provenance: set[str],
    *,
    strict_provenance: bool,
) -> int:
    """Count distinct non-colliding, non-cloned peer clusters via union-find."""
    eligible = [
        v.peer_id for v in vectors
        if not (strict_provenance and v.peer_id in missing_provenance)
    ]
    if not eligible:
        return 0
    parent: dict[str, str] = {pid: pid for pid in eligible}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_prov: dict[str, list[str]] = defaultdict(list)
    by_tag: dict[str, list[str]] = defaultdict(list)
    for v in vectors:
        if v.peer_id not in parent:
            continue
        if v.provenance_id:
            by_prov[v.provenance_id].append(v.peer_id)
        if v.independence_tag:
            by_tag[v.independence_tag].append(v.peer_id)

    for group in list(by_prov.values()) + list(by_tag.values()):
        for member in group[1:]:
            union(group[0], member)
    for a, b in cloned_pairs:
        if a in parent and b in parent:
            union(a, b)

    return len({find(pid) for pid in eligible})


def _validate_finite_real(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite real number, got {value!r}")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return fval


class FourPeerQuorumEngine:
    """Theorem 15 Anti-Echo-Chamber Quorum engine for Zoe, Clara, Antigravity, and User."""

    def __init__(
        self,
        *,
        required_peers: Sequence[str] = DEFAULT_FOUR_PEERS,
        coherence_min: float = 0.45,
        echo_dk_tol: float = 1e-9,
        uniform_tol: float = 1e-9,
        near_duplicate_l2_tol: float = 1e-4,
        min_independent_peers: int = 2,
        strict_provenance: bool = True,
        strict_anti_echo: bool = True,
    ) -> None:
        self.required_peers = tuple(_clean_label(p, "peer_id") for p in required_peers)
        if not self.required_peers or len(set(self.required_peers)) != len(self.required_peers):
            raise ValueError("required_peers must be non-empty and unique")
        coherence_min_f = _validate_finite_real(coherence_min, "coherence_min")
        if not (0.0 < coherence_min_f <= 1.0):
            raise ValueError("coherence_min must be in (0, 1]")
        echo_dk_tol_f = _validate_finite_real(echo_dk_tol, "echo_dk_tol")
        if echo_dk_tol_f < 0.0:
            raise ValueError("echo_dk_tol must be nonnegative")
        uniform_tol_f = _validate_finite_real(uniform_tol, "uniform_tol")
        if uniform_tol_f < 0.0:
            raise ValueError("uniform_tol must be nonnegative")
        near_duplicate_l2_tol_f = _validate_finite_real(
            near_duplicate_l2_tol, "near_duplicate_l2_tol"
        )
        if near_duplicate_l2_tol_f < 0.0:
            raise ValueError("near_duplicate_l2_tol must be nonnegative")
        if isinstance(min_independent_peers, bool) or not isinstance(min_independent_peers, int) or min_independent_peers < 1:
            raise ValueError("min_independent_peers must be an int >= 1")

        self.coherence_min = coherence_min_f
        self.echo_dk_tol = echo_dk_tol_f
        self.uniform_tol = uniform_tol_f
        self.near_duplicate_l2_tol = near_duplicate_l2_tol_f
        self.min_independent_peers = min_independent_peers
        self.strict_provenance = bool(strict_provenance)
        self.strict_anti_echo = bool(strict_anti_echo)
        self._peers: dict[str, PeerConfidenceVector] = {}

    def register_peer(self, vector: PeerConfidenceVector) -> None:
        """Register or replace a peer's confidence vector in the quorum buffer."""
        if not isinstance(vector, PeerConfidenceVector):
            raise TypeError(f"expected PeerConfidenceVector, got {type(vector).__name__}")
        self._peers[vector.peer_id] = vector

    def get_peer(self, peer_id: str) -> PeerConfidenceVector | None:
        return self._peers.get(peer_id)

    def clear(self) -> None:
        self._peers.clear()

    def registered_peer_ids(self) -> tuple[str, ...]:
        return tuple(self._peers.keys())

    def evaluate(
        self,
        vectors: Sequence[PeerConfidenceVector] | None = None,
        *,
        tau: float = DEFAULT_TAU,
        labels: Sequence[str] | None = None,
        coercion_signals: Sequence[str] = (),
        use_teamwork_arbitrator: bool = True,
        blackboard: EpistemicBlackboard | None = None,
    ) -> FourPeerQuorumResult:
        """Evaluate Theorem 15 consensus and anti-echo-chamber guards over peer vectors."""
        if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not (0.0 < float(tau) < 1.0):
            raise ValueError(f"tau must be in (0, 1), got {tau!r}")
        tau_f = float(tau)

        active_list = list(vectors) if vectors is not None else list(self._peers.values())
        if not active_list:
            raise ValueError("at least one PeerConfidenceVector is required for quorum evaluation")

        seen_ids: set[str] = set()
        for vec in active_list:
            if not isinstance(vec, PeerConfidenceVector):
                raise TypeError(f"expected PeerConfidenceVector, got {type(vec).__name__}")
            if vec.peer_id in seen_ids:
                raise ValueError(f"duplicate peer_id {vec.peer_id!r} in quorum evaluation")
            seen_ids.add(vec.peer_id)

        resolved_labels = tuple(_clean_label(l, "label") for l in labels) if labels is not None else active_list[0].labels
        for vec in active_list:
            if vec.labels != resolved_labels:
                raise ValueError(
                    f"peer {vec.peer_id!r} labels {vec.labels} do not match quorum labels {resolved_labels}"
                )

        by_id = {v.peer_id: v for v in active_list}
        missing_peers = tuple(pid for pid in self.required_peers if pid not in by_id)
        # Canonical ordering: required_peers first, then any extra peers.
        ordered_vectors = tuple(
            [by_id[pid] for pid in self.required_peers if pid in by_id]
            + [v for v in active_list if v.peer_id not in self.required_peers]
        )

        peer_ids = tuple(v.peer_id for v in ordered_vectors)
        dists = [list(v.probabilities) for v in ordered_vectors]
        raw_weights = [float(v.weight) for v in ordered_vectors]
        w_sum = math.fsum(raw_weights)
        norm_weights = tuple(w / w_sum for w in raw_weights)

        # 1. Provenance & independence tag audit.
        missing_prov = tuple(v.peer_id for v in ordered_vectors if not v.has_independent_provenance)
        prov_buckets: dict[str, list[str]] = defaultdict(list)
        tag_buckets: dict[str, list[str]] = defaultdict(list)
        for v in ordered_vectors:
            if v.provenance_id:
                prov_buckets[v.provenance_id].append(v.peer_id)
            if v.independence_tag:
                tag_buckets[v.independence_tag].append(v.peer_id)
        shared_prov = tuple(tuple(g) for g in prov_buckets.values() if len(g) >= 2)
        shared_tags = tuple(tuple(g) for g in tag_buckets.values() if len(g) >= 2)

        # 2. Pairwise L2^2 distances and near-identical clone detection.
        pairwise_l2_sq: dict[str, float] = {}
        cloned_pairs: list[tuple[str, str]] = []
        d_k_pairwise = 0.0
        n_dim = len(resolved_labels)
        k_count = len(ordered_vectors)
        for i in range(k_count):
            for j in range(i + 1, k_count):
                l2_sq = math.fsum(
                    (dists[i][m] - dists[j][m]) ** 2 for m in range(n_dim)
                )
                l2 = math.sqrt(max(0.0, l2_sq))
                pairwise_l2_sq[f"{peer_ids[i]}<->{peer_ids[j]}"] = round(l2_sq, 8)
                d_k_pairwise += norm_weights[i] * norm_weights[j] * l2_sq
                if l2 <= self.near_duplicate_l2_tol:
                    cloned_pairs.append((peer_ids[i], peer_ids[j]))

        effective_independent = _count_independent_clusters(
            ordered_vectors,
            cloned_pairs,
            set(missing_prov),
            strict_provenance=self.strict_provenance,
        )

        # 3. Theorem 15 consensus arbitration (guiai.gem.kloster_multi_agent_consensus or fallback).
        arbitrate = _load_consensus_arbitrator()
        t15 = arbitrate(
            dists,
            weights=raw_weights,
            coherence_min=self.coherence_min,
            echo_dk_tol=self.echo_dk_tol,
            uniform_tol=self.uniform_tol,
            min_agents=max(2, self.min_independent_peers),
            tau=tau_f,
        )

        teamwork_arb: dict[str, Any] | None = None
        if use_teamwork_arbitrator:
            teamwork_arb = arbitrate_teamwork_quorum(
                {lbl: 1.0 / max(1, len(TIER_ORDER)) for lbl in TIER_ORDER},
                effective_multi_file=False,
                complexity=0.0,
                deep_hits=0,
                tau=tau_f,
                quorum_distributions=dists,
                quorum_weights=raw_weights,
            )

        # Exact unrounded p_bar and D_K check for Brier wisdom-of-crowds identity.
        exact_p_bar = tuple(
            math.fsum(norm_weights[i] * dists[i][m] for i in range(k_count))
            for m in range(n_dim)
        )
        m2_mean_exact = math.fsum(
            norm_weights[i] * math.fsum(x * x for x in dists[i]) for i in range(k_count)
        )
        m2_pool_exact = math.fsum(x * x for x in exact_p_bar)
        d_k_exact = max(0.0, m2_mean_exact - m2_pool_exact)
        brier_ok, brier_res = _compute_brier_identity_check(dists, norm_weights, exact_p_bar, d_k_exact)

        # 4. Operational Metacognition A_tau(p) breadth per peer & pooled.
        meta = OperationalMetacognition()
        thr = meta.threshold(
            Domain.ACTION,
            tau_f,
            rationale="Fixed episode threshold for four-peer Theorem 15 quorum.",
        )
        per_peer_a_tau: dict[str, int] = {}
        for v in ordered_vectors:
            prov = Provenance(
                (v.to_evidence_source(),),
                ("Evaluate peer simplex confidence vector via Operational Metacognition A_tau(p).",),
            )
            opts = options_from_probabilities(v.as_mapping(), prov)
            per_peer_a_tau[v.peer_id] = int(meta.count(opts, thr, represented_count=n_dim).accessible_count)

        # 5. Priority decision tree combining coercion, provenance, Theorem 15, and anti-echo-chamber.
        coercion_list = [str(c) for c in coercion_signals if str(c).strip()]
        coercion_blocked = bool(coercion_list)
        provenance_complete = len(missing_prov) == 0 and len(shared_prov) == 0
        rogue_detected = bool(t15.get("rogue_node_detected"))
        bluff_detected = bool(t15.get("bluff_detected"))
        echo_detected = bool(
            t15.get("echo_chamber_detected")
            or shared_tags
            or (cloned_pairs and not bluff_detected)
        )
        rogue_peer_ids = tuple(
            peer_ids[idx]
            for idx in (t15.get("rogue_agent_indices") or ())
            if 0 <= int(idx) < k_count
        )

        independence_verified = bool(
            provenance_complete
            and not shared_tags
            and not cloned_pairs
            and not missing_peers
            and effective_independent >= max(2, len(self.required_peers))
        )

        effective_weight_count = 1.0 / max(1e-12, math.fsum(w * w for w in norm_weights))
        single_peer_monopoly = bool(k_count >= 2 and effective_weight_count < 1.25)

        if coercion_blocked:
            verdict = "ABSTAIN"
            reason = "coercion_guard_blocked"
            abstained = True
            abstention_applied = True
            escalate = True
        elif missing_peers:
            verdict = "ABSTAIN"
            reason = "incomplete_four_peer_quorum"
            abstained = True
            abstention_applied = True
            escalate = True
        elif self.strict_provenance and missing_prov:
            verdict = "ABSTAIN"
            reason = "missing_independent_provenance"
            abstained = True
            abstention_applied = True
            escalate = True
        elif single_peer_monopoly:
            verdict = "ABSTAIN"
            reason = "single_peer_weight_monopoly"
            abstained = True
            abstention_applied = True
            escalate = True
            bluff_detected = True
        elif t15["verdict"] == "ABSTAIN":
            verdict = "ABSTAIN"
            reason = str(t15["reason"])
            abstained = True
            abstention_applied = True
            escalate = True
        elif t15["verdict"] == "ECHO_CHAMBER_WARNING" or shared_tags or shared_prov or (self.strict_anti_echo and cloned_pairs):
            verdict = "ECHO_CHAMBER_WARNING"
            if t15["verdict"] == "ECHO_CHAMBER_WARNING":
                reason = str(t15["reason"])
            elif shared_tags or shared_prov:
                reason = "shared_independence_or_provenance"
            else:
                reason = "cloned_peer_distribution_echo_chamber"
            abstained = False
            abstention_applied = True
            escalate = True
            echo_detected = True
        elif effective_independent < self.min_independent_peers:
            verdict = "ABSTAIN"
            reason = "insufficient_independent_peers"
            abstained = True
            abstention_applied = True
            escalate = True
        else:
            verdict = "COORDINATE_CONSENSUS"
            reason = "coherent_diverse_four_peer_consensus"
            abstained = False
            abstention_applied = False
            escalate = False

        argmax_idx = int(t15["consensus_argmax"]) if 0 <= int(t15.get("consensus_argmax", -1)) < n_dim else 0
        consensus_label = resolved_labels[argmax_idx] if n_dim > 0 else "abstain"
        if verdict == "ABSTAIN":
            recommended_action = "ABSTAIN"
        elif verdict == "ECHO_CHAMBER_WARNING":
            recommended_action = "ESCALATE_ECHO_CHAMBER"
        else:
            recommended_action = consensus_label

        consensus_map = {lbl: float(p) for lbl, p in zip(resolved_labels, exact_p_bar)}
        result = FourPeerQuorumResult(
            contract=QUORUM_CONTRACT,
            verdict=verdict,
            reason=reason,
            recommended_action=recommended_action,
            abstained=abstained,
            abstention_applied=abstention_applied,
            escalate=escalate,
            quorum_met=bool(
                not missing_peers
                and not single_peer_monopoly
                and t15.get("quorum_met", False)
                and effective_independent >= self.min_independent_peers
            ),
            echo_chamber_detected=echo_detected,
            rogue_node_detected=rogue_detected,
            bluff_detected=bluff_detected,
            coercion_blocked=coercion_blocked,
            independence_verified=independence_verified and not single_peer_monopoly,
            provenance_complete=provenance_complete,
            labels=resolved_labels,
            peer_ids=peer_ids,
            vectors=ordered_vectors,
            normalized_weights=norm_weights,
            consensus_p_bar=exact_p_bar,
            consensus_map=consensus_map,
            consensus_argmax=argmax_idx,
            consensus_label=consensus_label,
            consensus_confidence=float(max(exact_p_bar)) if exact_p_bar else 0.0,
            tau=tau_f,
            a_tau_pool=int(sum(1 for x in exact_p_bar if x > tau_f)),
            per_peer_a_tau=per_peer_a_tau,
            m2_mean=float(t15["m2_mean"]),
            m2_pool=float(t15["m2_pool"]),
            d_k_disagreement=float(t15["d_k_disagreement"]),
            d_k_pairwise=round(d_k_pairwise, 8),
            brier_contraction=float(t15["brier_contraction"]),
            brier_identity_verified=brier_ok,
            brier_identity_max_residual=brier_res,
            coherence_c_k=float(t15["coherence_c_k"]),
            jsd_nats=float(t15["jsd_nats"]),
            pairwise_l2_sq=pairwise_l2_sq,
            rogue_peer_ids=rogue_peer_ids,
            missing_peers=missing_peers,
            missing_provenance_peers=missing_prov,
            shared_provenance_groups=shared_prov,
            shared_independence_groups=shared_tags,
            cloned_peer_pairs=tuple(cloned_pairs),
            effective_independent_peers=effective_independent,
            theorem15_raw=dict(t15),
            teamwork_arbitration=teamwork_arb,
            constitutional=quorum_constitutional_metadata(cloud_tokens_used=0),
        )
        if blackboard is not None:
            bb_info = _emit_blackboard_records(blackboard, result)
            result = replace(result, blackboard_records=bb_info)
        return result


def _emit_blackboard_records(
    blackboard: EpistemicBlackboard,
    result: FourPeerQuorumResult,
) -> dict[str, Any]:
    """Post MeasurementRecord + EvidenceRecord to EpistemicBlackboard (Art. III firewall)."""
    sources = tuple(v.to_evidence_source() for v in result.vectors)
    prov = Provenance(
        sources=sources,
        transformations=("Theorem 15 four-peer anti-echo-chamber quorum evaluation.",),
    )
    meas = blackboard.post_measurement(
        source_agent="shared_reasoning.quorum",
        input_desc=f"4-peer simplex confidence vectors ({', '.join(result.peer_ids)}) over {list(result.labels)}",
        method="theorem15_anti_echo_chamber_quorum",
        scope=f"k_agents={len(result.vectors)}, n_dim={len(result.labels)}, tau={result.tau}",
        limitations="Simplex confidence vectors measure peer agreement/diversity only; not ground-truth calibration.",
        value={
            "verdict": result.verdict,
            "reason": result.reason,
            "recommended_action": result.recommended_action,
            "consensus_p_bar": [round(float(p), 8) for p in result.consensus_p_bar],
            "d_k_disagreement": round(float(result.d_k_disagreement), 8),
            "coherence_c_k": round(float(result.coherence_c_k), 6),
            "effective_independent_peers": result.effective_independent_peers,
            "echo_chamber_detected": result.echo_chamber_detected,
            "rogue_node_detected": result.rogue_node_detected,
        },
        sampled_only=False,
        provenance=prov,
    )
    passed = result.verdict == "COORDINATE_CONSENSUS"
    ev = blackboard.promote_to_evidence(
        measurement_id=meas.record_id,
        verifier_name="theorem15_four_peer_quorum",
        passed=passed,
        rationale=(
            f"Deterministic Theorem 15 evaluation: verdict={result.verdict}, reason={result.reason}, "
            f"D_K={result.d_k_disagreement:.6f}, C_K={result.coherence_c_k:.6f}, "
            f"brier_identity_verified={result.brier_identity_verified}, "
            f"effective_independent_peers={result.effective_independent_peers}."
        ),
        evidence_source=EvidenceSource(
            kind="tool",
            identifier="zoe:theorem15_four_peer_quorum",
            trust=0.92,
            strength=0.90,
        ),
    )
    return {
        "measurement_id": meas.record_id,
        "evidence_id": ev.record_id,
        "passed": ev.passed,
        "negative_result": ev.negative_result,
    }


def _coerce_peer_vector(
    peer_id: str,
    value: PeerInput,
    *,
    default_provenance_id: str,
    default_independence_tag: str,
    source_kind: str,
    weight: float,
    labels: Sequence[str] | None,
    explicit_weight: float | None = None,
) -> PeerConfidenceVector:
    if isinstance(value, PeerConfidenceVector):
        eff_labels = tuple(labels) if labels is not None else value.labels
        eff_weight = explicit_weight if explicit_weight is not None else value.weight
        if (
            value.peer_id != peer_id
            or eff_labels != value.labels
            or eff_weight != value.weight
        ):
            return PeerConfidenceVector(
                peer_id=peer_id,
                probabilities=value.probabilities,
                source_kind=value.source_kind,
                provenance_id=value.provenance_id,
                independence_tag=value.independence_tag,
                labels=eff_labels,
                weight=eff_weight,
                metadata=value.metadata,
            )
        return value
    return PeerConfidenceVector(
        peer_id=peer_id,
        probabilities=value,
        source_kind=source_kind,
        provenance_id=default_provenance_id,
        independence_tag=default_independence_tag,
        labels=tuple(labels) if labels is not None else (),
        weight=weight,
    )


def _resolve_peer_weights(
    weights: Sequence[float] | Mapping[str, float] | None,
) -> dict[str, float]:
    if weights is None:
        return {pid: 1.0 for pid in DEFAULT_FOUR_PEERS}
    if isinstance(weights, (str, bytes)):
        raise ValueError(f"weights must be a Mapping or Sequence of floats, got {type(weights).__name__}")
    if isinstance(weights, Mapping):
        out: dict[str, float] = {}
        for pid in DEFAULT_FOUR_PEERS:
            raw_w = weights.get(pid, 1.0)
            if isinstance(raw_w, bool) or not isinstance(raw_w, (int, float)):
                raise ValueError(f"weight for peer {pid!r} must be numeric, got {type(raw_w).__name__}")
            fw = float(raw_w)
            if not math.isfinite(fw):
                raise ValueError(f"weight for peer {pid!r} must be finite, got {raw_w!r}")
            out[pid] = fw
        return out
    w_list = list(weights)
    if len(w_list) != len(DEFAULT_FOUR_PEERS):
        raise ValueError(
            f"weights sequence must have length {len(DEFAULT_FOUR_PEERS)}, got {len(w_list)}"
        )
    out = {}
    for pid, raw_w in zip(DEFAULT_FOUR_PEERS, w_list):
        if isinstance(raw_w, bool) or not isinstance(raw_w, (int, float)):
            raise ValueError(f"weight for peer {pid!r} must be numeric, got {type(raw_w).__name__}")
        fw = float(raw_w)
        if not math.isfinite(fw):
            raise ValueError(f"weight for peer {pid!r} must be finite, got {raw_w!r}")
        out[pid] = fw
    return out


def evaluate_four_peer_quorum(
    zoe_probs: PeerInput | None,
    clara_probs: PeerInput | None,
    antigravity_probs: PeerInput | None,
    user_probs: PeerInput | None,
    *,
    tau: float = DEFAULT_TAU,
    weights: Sequence[float] | Mapping[str, float] | None = None,
    source_kinds: Mapping[str, str] | None = None,
    provenance_ids: Mapping[str, str] | None = None,
    independence_tags: Mapping[str, str] | None = None,
    labels: Sequence[str] | None = None,
    coercion_signals: Sequence[str] = (),
    coherence_min: float = 0.45,
    echo_dk_tol: float = 1e-9,
    near_duplicate_l2_tol: float = 1e-4,
    strict_provenance: bool = True,
    strict_anti_echo: bool = True,
    use_teamwork_arbitrator: bool = True,
    blackboard: EpistemicBlackboard | None = None,
) -> FourPeerQuorumResult:
    """Evaluate a 4-peer Theorem 15 quorum across Zoe, Clara, Antigravity, and User."""
    raw_inputs: dict[str, PeerInput | None] = {
        "zoe": zoe_probs,
        "clara": clara_probs,
        "antigravity": antigravity_probs,
        "user": user_probs,
    }
    w_map = _resolve_peer_weights(weights)
    sk_map = dict(source_kinds or {})
    prov_map = dict(provenance_ids or {})
    tag_map = dict(independence_tags or {})

    vectors: list[PeerConfidenceVector] = []
    for idx, pid in enumerate(DEFAULT_FOUR_PEERS, start=1):
        val = raw_inputs[pid]
        if val is None:
            continue
        vectors.append(
            _coerce_peer_vector(
                pid,
                val,
                default_provenance_id=prov_map.get(pid, f"prov:{pid}:stream-0{idx}"),
                default_independence_tag=tag_map.get(pid, f"indep:{pid}"),
                source_kind=sk_map.get(pid, _DEFAULT_SOURCE_KINDS[pid]),
                weight=w_map[pid],
                labels=labels,
                explicit_weight=w_map[pid] if weights is not None else None,
            )
        )

    if not vectors:
        raise ValueError("at least one non-None peer confidence vector is required")

    engine = FourPeerQuorumEngine(
        coherence_min=coherence_min,
        echo_dk_tol=echo_dk_tol,
        near_duplicate_l2_tol=near_duplicate_l2_tol,
        strict_provenance=strict_provenance,
        strict_anti_echo=strict_anti_echo,
    )
    return engine.evaluate(
        vectors,
        tau=tau,
        labels=labels,
        coercion_signals=coercion_signals,
        use_teamwork_arbitrator=use_teamwork_arbitrator,
        blackboard=blackboard,
    )


def quorum_from_dual_peer_balance(
    balance: Mapping[str, Any],
    *,
    antigravity_probs: PeerInput,
    user_probs: PeerInput,
    tau: float | None = None,
    weights: Sequence[float] | Mapping[str, float] | None = None,
    provenance_ids: Mapping[str, str] | None = None,
    independence_tags: Mapping[str, str] | None = None,
    strict_provenance: bool = True,
    strict_anti_echo: bool = True,
    blackboard: EpistemicBlackboard | None = None,
) -> FourPeerQuorumResult:
    """Extend a ``zoe_clara.evaluate_dual_peer_balance`` result with Antigravity & User."""
    if not isinstance(balance, Mapping):
        raise ValueError(f"balance must be a Mapping, got {type(balance).__name__}")
    if "zoe_distribution" not in balance or "clara_distribution" not in balance:
        raise ValueError("balance mapping must contain zoe_distribution and clara_distribution")
    zoe_a_tau = balance.get("zoe_a_tau")
    inferred_tau = zoe_a_tau.get("tau", DEFAULT_TAU) if isinstance(zoe_a_tau, Mapping) else DEFAULT_TAU
    raw_tau = tau if tau is not None else inferred_tau
    if isinstance(raw_tau, bool) or not isinstance(raw_tau, (int, float)):
        raise ValueError(f"tau must be a finite numeric value, got {type(raw_tau).__name__}")
    eff_tau = float(raw_tau)
    if not math.isfinite(eff_tau):
        raise ValueError(f"tau must be finite, got {raw_tau!r}")
    zoe_vec = PeerConfidenceVector(
        peer_id="zoe",
        probabilities=balance["zoe_distribution"],
        source_kind="document",
        provenance_id=(provenance_ids or {}).get("zoe", "prov:zoe_clara:zoe"),
        independence_tag=(independence_tags or {}).get("zoe", "indep:zoe_observatory"),
        labels=ACTION_LABELS,
    )
    clara_vec = PeerConfidenceVector(
        peer_id="clara",
        probabilities=balance["clara_distribution"],
        source_kind="validated_reflection",
        provenance_id=(provenance_ids or {}).get("clara", "prov:zoe_clara:clara"),
        independence_tag=(independence_tags or {}).get("clara", "indep:clara_balance"),
        labels=ACTION_LABELS,
    )
    return evaluate_four_peer_quorum(
        zoe_vec,
        clara_vec,
        antigravity_probs,
        user_probs,
        tau=eff_tau,
        weights=weights,
        provenance_ids=provenance_ids,
        independence_tags=independence_tags,
        labels=ACTION_LABELS,
        coercion_signals=balance.get("coercion_signals") or (),
        strict_provenance=strict_provenance,
        strict_anti_echo=strict_anti_echo,
        blackboard=blackboard,
    )


def route_with_four_peer_quorum(
    prompt: str,
    *,
    zoe_probs: PeerInput | None = None,
    clara_probs: PeerInput | None = None,
    antigravity_probs: PeerInput | None = None,
    user_probs: PeerInput | None = None,
    offline_only: bool = False,
    privacy_sensitive: bool = False,
    files_count: int = 1,
    multi_file: bool = False,
    local_qwen_available: bool | None = None,
    probe_local: bool = False,
    local_qwen_url: str = DEFAULT_LOCAL_QWEN_URL,
    tau: float = DEFAULT_STEM_TAU,
    weights: Sequence[float] | Mapping[str, float] | None = None,
    source_kinds: Mapping[str, str] | None = None,
    provenance_ids: Mapping[str, str] | None = None,
    independence_tags: Mapping[str, str] | None = None,
    labels: Sequence[str] | None = None,
    coherence_min: float = 0.45,
    near_duplicate_l2_tol: float = 1e-4,
    strict_provenance: bool = True,
    strict_anti_echo: bool = True,
    blackboard: EpistemicBlackboard | None = None,
) -> FourPeerRouteResult:
    """Route a prompt via ``stem_layering.route_stem`` gated by 4-peer Theorem 15 quorum."""
    resolved_zoe = zoe_probs
    if resolved_zoe is None:
        base = route_stem(
            prompt,
            offline_only=offline_only,
            privacy_sensitive=privacy_sensitive,
            files_count=files_count,
            multi_file=multi_file,
            local_qwen_available=local_qwen_available,
            probe_local=probe_local,
            local_qwen_url=local_qwen_url,
            tau=tau,
        )
        resolved_zoe = PeerConfidenceVector(
            peer_id="zoe",
            probabilities=base.probabilities,
            source_kind="document",
            provenance_id=(provenance_ids or {}).get("zoe", "prov:zoe:stem_layering"),
            independence_tag=(independence_tags or {}).get("zoe", "indep:zoe_stem"),
            labels=STEM_TIER_LABELS,
        )

    quorum_res = evaluate_four_peer_quorum(
        resolved_zoe,
        clara_probs,
        antigravity_probs,
        user_probs,
        tau=tau,
        weights=weights,
        source_kinds=source_kinds,
        provenance_ids=provenance_ids,
        independence_tags=independence_tags,
        labels=labels,
        coherence_min=coherence_min,
        near_duplicate_l2_tol=near_duplicate_l2_tol,
        strict_provenance=strict_provenance,
        strict_anti_echo=strict_anti_echo,
        use_teamwork_arbitrator=True,
        blackboard=blackboard,
    )

    stem_decision = route_stem(
        prompt,
        offline_only=offline_only,
        privacy_sensitive=privacy_sensitive,
        files_count=files_count,
        multi_file=multi_file,
        local_qwen_available=local_qwen_available,
        probe_local=probe_local,
        local_qwen_url=local_qwen_url,
        tau=tau,
        quorum_distributions=[list(v.probabilities) for v in quorum_res.vectors],
        quorum_weights=list(quorum_res.normalized_weights),
    )

    effective_teamwork = bool(
        stem_decision.teamwork_recommended
        and not quorum_res.abstention_applied
        and not quorum_res.escalate
    )
    return FourPeerRouteResult(
        stem_decision=stem_decision,
        quorum=quorum_res,
        effective_teamwork_recommended=effective_teamwork,
        escalate=quorum_res.escalate,
        constitutional=quorum_constitutional_metadata(
            cloud_tokens_used=int(stem_decision.constitutional.get("cloud_tokens_used", 0))
        ),
    )


__all__ = [
    "ACTION_LABELS",
    "ATTRIBUTION_TEXT",
    "DEFAULT_FOUR_PEERS",
    "DEFAULT_TAU",
    "FourPeerQuorumEngine",
    "FourPeerQuorumResult",
    "FourPeerRouteResult",
    "PeerConfidenceVector",
    "PeerInput",
    "QUORUM_CONTRACT",
    "STEM_TIER_LABELS",
    "VALID_SOURCE_KINDS",
    "evaluate_four_peer_quorum",
    "quorum_constitutional_metadata",
    "quorum_from_dual_peer_balance",
    "route_with_four_peer_quorum",
]

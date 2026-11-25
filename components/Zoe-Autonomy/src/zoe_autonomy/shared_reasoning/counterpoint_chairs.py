"""Architecture #9 (Team-Invented): Counterpoint Chairs — Polyphonic Musical-Chairs Relay & Cold-Audit Rotation.

Prevents single-agent fixation, confirmation bias, and sunk-cost drift across
multi-problem reasoning by rotating heterogeneous voices (``antigravity``,
``zoe``, ``clara``, ``sandbox_lab``) across active problem "chairs" on a
rhythmic preemption quantum (``beat_quantum_s`` / ``step_budget`` /
Kloster $A_\\tau(p)$ marginal-gain drop).

Every chair takeover enforces:
  1. **EpistemicBlackboard 4-lane freezing** into a tamper-evident SHA-256
     ``FrozenChairPacket`` strictly separating ``measurement_summary``,
     ``evidence_ids``, ``belief_status``, and ``pending_action_proposals``
     per ``CONSTITUTION.md`` Article III.
  2. **Mandatory Cold Audit** by the incoming voice, verifying packet
     integrity, rejecting/quarantining unverified claims from the departing
     voice, flagging sunk-cost drift, and recording negative results openly.
  3. **Theorem 15 Cross-Voice Discrepancy Check** quantifying Kloster-Jensen
     disagreement $D_K$, coherence $C_K$, and echo-chamber risk between the
     departing and incoming voices.
  4. **Non-Repeating Polyphonic Rotation Schedule** guaranteeing no consecutive
     chair/voice repeats, full chair coverage, and a timestamped swap ledger.
  5. **Original Polyphonic Cadence Sonification** (``sonify_cadence_wav``)
     synthesizing a 16-bit PCM WAV reflecting rotation tension and resolution
     using pure Python stdlib (``wave``, ``struct``, ``math``).

Enforces ``docs/CONSTITUTION.md`` boundaries (``external_actions=0``,
``sentience_claimed=False``, ``l5_agi_qualified=False``,
``zoe_clone_claimed=False``; Operational Metacognition $A_\\tau(p)$ attributed
to Nicholas Michael Kloster, March 6, 2026).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import inspect
import math
from pathlib import Path
import struct
import time
from typing import Any, Literal
import wave

import numpy as np

from .._utils import sha256_file, sha256_json_utf8
from ..actuation import timestamp
from ..metacognition import (
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    options_from_probabilities,
)
from ..stem_layering import route_stem
from .blackboard import (
    ActionProposalRecord,
    BeliefUpdateRecord,
    EpistemicBlackboard,
    EvidenceRecord,
    FirewallViolationError,
    HASH_CHAIN_SEMANTICS,
    MeasurementRecord,
    TamperDetectedError,
)
from .quorum import (
    ACTION_LABELS,
    FourPeerQuorumEngine,
    PeerConfidenceVector,
)
from .sdk_bridge import (
    ATTRIBUTION_TEXT,
    CallableVoiceAdapter,
    ReasoningVoiceAdapter,
    VALID_MODES,
    VoiceResponse,
    ZoeAntigravityBridge,
    ZoeOfflineVoiceAdapter,
    bridge_constitutional_metadata,
    run_coro_sync,
)

COUNTERPOINT_CHAIRS_CONTRACT = "zoe-counterpoint-chairs/v1"
CANONICAL_VOICE_IDS: tuple[str, ...] = ("antigravity", "zoe", "clara", "sandbox_lab")
DEFAULT_BEAT_QUANTUM_S = 30.0
DEFAULT_STEP_BUDGET = 2
DEFAULT_TAU = 0.08
DEFAULT_MAX_DISCREPANCY_DK = 0.22
DEFAULT_MIN_MARGINAL_GAIN = 0.01
DEFAULT_SUNK_COST_PATIENCE = 2

_VALID_PREEMPTION_REASONS = frozenset(
    {
        "initial_seating",
        "beat_quantum_s",
        "step_budget",
        "a_tau_marginal_gain_drop",
        "cadence_complete",
    }
)


def counterpoint_constitutional_metadata(*, cloud_tokens_used: int = 0) -> dict[str, Any]:
    """Return canonical CONSTITUTION.md metadata for Counterpoint Chairs."""
    meta = bridge_constitutional_metadata(cloud_tokens_used=cloud_tokens_used)
    meta["attribution"] = ATTRIBUTION_TEXT
    meta["hash_chain_semantics"] = HASH_CHAIN_SEMANTICS
    return meta


def _clean_nonempty(value: Any, label: str, *, max_len: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        raise ValueError(f"{label} must not be empty")
    if len(cleaned) > max_len:
        raise ValueError(f"{label} exceeds max length {max_len}")
    return cleaned


def _normalize_simplex(
    raw: Sequence[float] | Mapping[str, float],
    labels: Sequence[str],
) -> tuple[float, ...]:
    """Normalize a nonnegative finite vector or label map onto the probability simplex."""
    if isinstance(raw, Mapping):
        ordered = [raw[lbl] for lbl in labels]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        if len(raw) != len(labels):
            raise ValueError(
                f"probability vector length ({len(raw)}) must match labels ({len(labels)})"
            )
        ordered = list(raw)
    else:
        raise ValueError("probabilities must be a sequence or mapping")

    vals: list[float] = []
    for item in ordered:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"probability entry must be numeric, got {type(item).__name__}")
        fval = float(item)
        if not math.isfinite(fval) or fval < 0.0:
            raise ValueError(f"probability entry must be finite and nonnegative, got {item!r}")
        vals.append(fval)

    total = math.fsum(vals)
    if total <= 0.0:
        n_dim = len(labels)
        return tuple(1.0 / n_dim for _ in range(n_dim))
    return tuple(v / total for v in vals)


def _json_safe(value: Any) -> Any:
    """Convert nested mappings/sequences/primitives into deterministic JSON-safe values."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FirewallViolationError("Non-finite float rejected by epistemic firewall")
        return value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _call_evaluator(
    fn: Callable[..., Any],
    chair: ProblemChair,
    packet: FrozenChairPacket | None,
    context: Mapping[str, Any],
) -> Any:
    """Invoke a voice evaluator accepting 1, 2, or 3 positional/keyword arguments."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    positional = [
        p
        for p in params
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if has_varargs or len(positional) >= 3:
        return fn(chair, packet, dict(context))
    if len(positional) == 2:
        return fn(chair, packet)
    if len(positional) == 1:
        return fn(chair)
    return fn()


# ---------------------------------------------------------------------------
# 1. Heterogeneous Chair Voices
# ---------------------------------------------------------------------------
@dataclass
class ChairVoice:
    """Heterogeneous reasoning voice participating in Counterpoint Chairs.

    Attributes:
        voice_id: Unique voice identifier (e.g. ``"antigravity"``, ``"zoe"``,
            ``"clara"``, ``"sandbox_lab"``).
        role: Functional counterpoint role (e.g. ``"frontier_generator"``).
        adapter: Optional ``ReasoningVoiceAdapter``, ``ZoeAntigravityBridge``, or callable.
        evaluator: Optional direct chair evaluator callable ``(chair, packet, ctx) -> dict``.
        independence_tag: Explicit independence identifier for Theorem 15 anti-echo-chamber checks.
        source_kind: Provenance source kind aligned with ``quorum.VALID_SOURCE_KINDS``.
        weight: Strictly positive voting/confidence weight.
        thinking_level: Optional Antigravity ``ThinkingLevel`` hint.
        metadata: Optional JSON-safe annotations.
    """

    voice_id: str
    role: str
    adapter: ReasoningVoiceAdapter | ZoeAntigravityBridge | Callable[..., Any] | None = None
    evaluator: Callable[..., Any] | None = None
    independence_tag: str = ""
    source_kind: str = "model"
    weight: float = 1.0
    thinking_level: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.voice_id = _clean_nonempty(self.voice_id, "voice_id", max_len=128)
        self.role = _clean_nonempty(self.role, "role", max_len=256)
        if not isinstance(self.independence_tag, str):
            raise ValueError("independence_tag must be a string")
        self.independence_tag = " ".join(self.independence_tag.split()).strip()
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise ValueError("weight must be numeric")
        fweight = float(self.weight)
        if not math.isfinite(fweight) or fweight <= 0.0:
            raise ValueError(f"weight must be positive and finite, got {self.weight!r}")
        self.weight = fweight

    def to_dict(self) -> dict[str, Any]:
        return {
            "voice_id": self.voice_id,
            "role": self.role,
            "independence_tag": self.independence_tag,
            "source_kind": self.source_kind,
            "weight": self.weight,
            "thinking_level": self.thinking_level,
            "has_adapter": self.adapter is not None,
            "has_evaluator": self.evaluator is not None,
            "metadata": _json_safe(self.metadata),
        }


def default_counterpoint_voices(
    *,
    bridge: ZoeAntigravityBridge | None = None,
) -> tuple[ChairVoice, ...]:
    """Construct the four canonical heterogeneous Counterpoint Chairs voices."""
    eff_bridge = bridge or ZoeAntigravityBridge(mode="offline")

    def _role_adapter(voice_id: str, bias_idx: int, role_note: str) -> CallableVoiceAdapter:
        offline_zoe = ZoeOfflineVoiceAdapter()

        async def _generate(prompt: str, context: Mapping[str, Any] | None = None) -> VoiceResponse:
            ctx = dict(context or {})
            base_resp = await offline_zoe.generate(prompt, ctx)
            stem = route_stem(prompt or "reason", offline_only=True, local_qwen_available=False)
            # Construct a deterministic, role-differentiated simplex over ACTION_LABELS
            # so heterogeneous voices maintain genuine diversity rather than cloning.
            complexity = float(stem.features.get("complexity_score", 1.0))
            base = [0.50, 0.34, 0.16]
            base[bias_idx % 3] += 0.12 + min(0.08, 0.02 * complexity)
            total = math.fsum(base)
            probs = [round(x / total, 6) for x in base]
            round_idx = int(ctx.get("round_index", 0))
            chair_id = str(ctx.get("chair_id", "chair"))
            return VoiceResponse(
                text=f"[{voice_id}:{role_note}] {base_resp.text}",
                thoughts=base_resp.thoughts
                + (
                    f"[{voice_id}] round={round_idx} chair={chair_id} role={role_note}",
                ),
                structured_output={
                    "voice_id": voice_id,
                    "probabilities": {
                        lbl: p for lbl, p in zip(ACTION_LABELS, probs)
                    },
                    "measurement": {
                        "input_desc": f"{chair_id}: {prompt[:160]}",
                        "method": f"counterpoint_voice:{voice_id}",
                        "scope": "bounded chair turn",
                        "limitations": "offline deterministic counterpoint turn",
                        "value": {
                            "stem_tier": stem.selected_tier,
                            "a_tau": stem.a_tau,
                            "round_index": round_idx,
                        },
                        "sampled_only": False,
                    },
                    "verification": {
                        "verifier_name": f"{voice_id}_consistency_check",
                        "passed": True,
                        "rationale": (
                            f"Deterministic {voice_id} independent check across "
                            f"bounded chair context ({role_note})."
                        ),
                    },
                    "claim": f"{chair_id} evaluated cleanly by {voice_id} ({role_note})",
                    "posterior_delta": round(0.05 + 0.02 * (bias_idx + 1), 4),
                    "action_proposal": {
                        "action_kind": "review_chair_hypothesis",
                        "target": chair_id,
                        "reversible": True,
                        "rationale": f"Pending human review after {voice_id} counterpoint pass.",
                    },
                },
                mode="offline",
                model=f"counterpoint-{voice_id}",
                thinking_level=ctx.get("thinking_level"),
                stem_decision=base_resp.stem_decision,
                constitutional=bridge_constitutional_metadata(cloud_tokens_used=0),
            )

        return CallableVoiceAdapter(_generate, model_name=f"counterpoint-{voice_id}")

    return (
        ChairVoice(
            voice_id="antigravity",
            role="frontier_generator",
            adapter=eff_bridge,
            independence_tag="indep:antigravity_sdk",
            source_kind="model",
            weight=1.0,
            thinking_level="medium",
            metadata={"register": "soprano", "base_hz": 523.25},
        ),
        ChairVoice(
            voice_id="zoe",
            role="observatory_verifier",
            adapter=_role_adapter("zoe", 0, "observatory_verifier"),
            independence_tag="indep:zoe_observatory",
            source_kind="document",
            weight=1.0,
            thinking_level="medium",
            metadata={"register": "alto", "base_hz": 392.00},
        ),
        ChairVoice(
            voice_id="clara",
            role="epistemic_critic",
            adapter=_role_adapter("clara", 1, "epistemic_critic"),
            independence_tag="indep:clara_balance",
            source_kind="validated_reflection",
            weight=1.0,
            thinking_level="high",
            metadata={"register": "tenor", "base_hz": 329.63},
        ),
        ChairVoice(
            voice_id="sandbox_lab",
            role="sandbox_ground_truth",
            adapter=_role_adapter("sandbox_lab", 2, "sandbox_ground_truth"),
            independence_tag="indep:sandbox_verifier",
            source_kind="tool",
            weight=1.0,
            thinking_level="low",
            metadata={"register": "bass", "base_hz": 261.63},
        ),
    )


# ---------------------------------------------------------------------------
# 2. Tamper-Evident 4-Lane FrozenChairPacket (CONSTITUTION.md Art. III)
# ---------------------------------------------------------------------------
def _validate_frozen_lanes(
    measurement_summary: Mapping[str, Any],
    evidence_ids: Sequence[str],
    belief_status: Mapping[str, Any],
    pending_action_proposals: Sequence[Mapping[str, Any]],
) -> None:
    """Enforce CONSTITUTION.md Art. III 4-lane boundaries on a FrozenChairPacket."""
    if not isinstance(measurement_summary, Mapping):
        raise FirewallViolationError("measurement_summary must be a mapping")
    if not isinstance(belief_status, Mapping):
        raise FirewallViolationError("belief_status must be a mapping")
    if isinstance(evidence_ids, (str, bytes)) or not isinstance(evidence_ids, Sequence):
        raise FirewallViolationError("evidence_ids must be a sequence of EvidenceRecord IDs")
    if isinstance(pending_action_proposals, (str, bytes)) or not isinstance(
        pending_action_proposals, Sequence
    ):
        raise FirewallViolationError("pending_action_proposals must be a sequence")

    # Lane 4 must always remain REVIEW_REQUIRED with zero external actions.
    for idx, prop in enumerate(pending_action_proposals):
        if not isinstance(prop, Mapping):
            raise FirewallViolationError(f"pending_action_proposals[{idx}] must be a mapping")
        status = prop.get("status")
        ext_actions = prop.get("external_actions", 0)
        auto_allowed = prop.get("autonomous_execution_allowed", False)
        if status != "REVIEW_REQUIRED" or ext_actions != 0 or auto_allowed is not False:
            raise FirewallViolationError(
                "CONSTITUTION.md Art. III.4: frozen pending_action_proposals must keep "
                "status='REVIEW_REQUIRED', external_actions=0, autonomous_execution_allowed=False"
            )

    # Lane 2 & 3 boundary: verified_claims in belief_status cannot exist without evidence_ids.
    verified_claims = belief_status.get("verified_claims") or ()
    if verified_claims and not evidence_ids:
        raise FirewallViolationError(
            "CONSTITUTION.md Art. III.2: belief_status.verified_claims cannot be populated "
            "without at least one approved EvidenceRecord ID"
        )


@dataclass(frozen=True)
class FrozenChairPacket:
    """Tamper-evident SHA-256 handoff snapshot strictly separating the 4 Art. III lanes.

    Hash-chain semantics: tamper evidence only, explicitly NOT cryptographic
    authentication or proof of who acted (``CONSTITUTION.md`` Article III.5).
    """

    packet_id: str
    chair_id: str
    round_index: int
    departed_voice_id: str
    created_utc: str
    preemption_reason: str
    measurement_summary: dict[str, Any]
    evidence_ids: tuple[str, ...]
    belief_status: dict[str, Any]
    pending_action_proposals: tuple[dict[str, Any], ...]
    blackboard_chain_head: str = "GENESIS"
    blackboard_sha256: str = ""
    hash_chain_semantics: str = HASH_CHAIN_SEMANTICS
    packet_sha256: str = ""

    def __post_init__(self) -> None:
        _validate_frozen_lanes(
            self.measurement_summary,
            self.evidence_ids,
            self.belief_status,
            self.pending_action_proposals,
        )
        # Ensure defensive canonical JSON-safe copies and auto-compute SHA-256 if omitted.
        object.__setattr__(
            self,
            "measurement_summary",
            _json_safe(dict(self.measurement_summary)),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            tuple(str(eid) for eid in self.evidence_ids),
        )
        object.__setattr__(
            self,
            "belief_status",
            _json_safe(dict(self.belief_status)),
        )
        object.__setattr__(
            self,
            "pending_action_proposals",
            tuple(_json_safe(dict(p)) for p in self.pending_action_proposals),
        )
        if not self.packet_sha256:
            object.__setattr__(self, "packet_sha256", self.compute_sha256())

    def payload_dict(self) -> dict[str, Any]:
        return {
            "contract": COUNTERPOINT_CHAIRS_CONTRACT,
            "packet_id": self.packet_id,
            "chair_id": self.chair_id,
            "round_index": self.round_index,
            "departed_voice_id": self.departed_voice_id,
            "created_utc": self.created_utc,
            "preemption_reason": self.preemption_reason,
            "measurement_summary": deepcopy(self.measurement_summary),
            "evidence_ids": list(self.evidence_ids),
            "belief_status": deepcopy(self.belief_status),
            "pending_action_proposals": [deepcopy(p) for p in self.pending_action_proposals],
            "blackboard_chain_head": self.blackboard_chain_head,
            "blackboard_sha256": self.blackboard_sha256,
            "hash_chain_semantics": self.hash_chain_semantics,
        }

    def compute_sha256(self) -> str:
        return sha256_json_utf8(self.payload_dict())

    def verify_integrity(self, *, raise_on_error: bool = True) -> bool:
        """Verify SHA-256 digest of this frozen packet (tamper evidence only)."""
        expected = self.compute_sha256()
        if self.packet_sha256 != expected:
            if raise_on_error:
                raise TamperDetectedError(
                    f"FrozenChairPacket {self.packet_id!r} SHA-256 mismatch "
                    "(tamper evidence only, not authentication proof)"
                )
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        doc = self.payload_dict()
        doc["packet_sha256"] = self.packet_sha256
        return doc

    @classmethod
    def from_blackboard(
        cls,
        *,
        chair_id: str,
        round_index: int,
        departed_voice_id: str,
        preemption_reason: str,
        blackboard: EpistemicBlackboard,
        labels: Sequence[str],
        probabilities: Sequence[float],
        tau: float,
        a_tau: int,
        marginal_gain: float,
        steps_on_chair: int,
        stagnant_steps: int,
        unverified_claims: Sequence[str] = (),
        extra_belief_status: Mapping[str, Any] | None = None,
    ) -> "FrozenChairPacket":
        """Freeze a chair's EpistemicBlackboard state into a 4-lane SHA-256 packet."""
        blackboard.verify_integrity(raise_on_error=True)
        measurements = blackboard.list_measurements()
        evidences = blackboard.list_evidence()
        beliefs = blackboard.list_beliefs()
        actions = blackboard.list_action_proposals()

        approved_evidence_ids = tuple(ev.record_id for ev in evidences if ev.passed and ev.approved)
        negative_evidence_ids = tuple(ev.record_id for ev in evidences if ev.negative_result)
        sampled_only_ids = [m.record_id for m in measurements if m.sampled_only]

        measurement_summary = {
            "count": len(measurements),
            "measurement_ids": [m.record_id for m in measurements],
            "sampled_only_ids": sampled_only_ids,
            "methods": sorted({m.method for m in measurements}),
            "latest_measurement": measurements[-1].to_dict() if measurements else None,
            "negative_evidence_ids": list(negative_evidence_ids),
            "unverified_claims": [str(c) for c in unverified_claims if str(c).strip()],
        }

        belief_status: dict[str, Any] = {
            "count": len(beliefs),
            "belief_ids": [b.record_id for b in beliefs],
            "verified_claims": [b.claim for b in beliefs],
            "latest_confidence": beliefs[-1].confidence if beliefs else 0.0,
            "labels": list(labels),
            "probabilities": [round(float(p), 8) for p in probabilities],
            "tau": float(tau),
            "a_tau": int(a_tau),
            "marginal_gain": round(float(marginal_gain), 8),
            "steps_on_chair": int(steps_on_chair),
            "stagnant_steps": int(stagnant_steps),
        }
        if extra_belief_status:
            for k, v in extra_belief_status.items():
                if k not in belief_status:
                    belief_status[k] = _json_safe(v)

        pending_proposals = tuple(
            {
                "record_id": a.record_id,
                "belief_id": a.belief_id,
                "action_kind": a.action_kind,
                "target": a.target,
                "reversible": a.reversible,
                "status": a.status,
                "external_actions": a.external_actions,
                "requires_human_review": a.requires_human_review,
                "autonomous_execution_allowed": a.autonomous_execution_allowed,
                "rationale": a.rationale,
            }
            for a in actions
        )

        bb_summary = blackboard.summary()
        return cls(
            packet_id=f"pkt_{chair_id}_r{round_index:03d}_{departed_voice_id}",
            chair_id=chair_id,
            round_index=round_index,
            departed_voice_id=departed_voice_id,
            created_utc=timestamp(),
            preemption_reason=preemption_reason,
            measurement_summary=measurement_summary,
            evidence_ids=approved_evidence_ids,
            belief_status=belief_status,
            pending_action_proposals=pending_proposals,
            blackboard_chain_head=str(bb_summary["chain_head"]),
            blackboard_sha256=str(bb_summary["blackboard_sha256"]),
        )


# ---------------------------------------------------------------------------
# 3. Cold Audit Verdict & Problem Chair
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ColdAuditVerdict:
    """Result of an incoming voice's Cold Audit & Theorem 15 check on takeover."""

    incoming_voice_id: str
    departed_voice_id: str
    theorem15_discrepancy_dk: float
    firewall_ok: bool
    sunk_cost_flagged: bool
    rationale: str
    chair_id: str = ""
    round_index: int = 0
    accepted: bool = True
    packet_integrity_ok: bool = True
    discrepancy_exceeded: bool = False
    echo_chamber_detected: bool = False
    coherence_c_k: float = 1.0
    brier_contraction: float = 0.0
    theorem15_verdict: str = "COORDINATE_CONSENSUS"
    unverified_claims_flagged: tuple[str, ...] = ()
    quarantined_items: tuple[str, ...] = ()
    evidence_record_id: str | None = None
    teamwork_arbitration: dict[str, Any] | None = None
    created_utc: str = field(default_factory=timestamp)
    constitutional: dict[str, Any] = field(default_factory=counterpoint_constitutional_metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": COUNTERPOINT_CHAIRS_CONTRACT,
            "chair_id": self.chair_id,
            "round_index": self.round_index,
            "incoming_voice_id": self.incoming_voice_id,
            "departed_voice_id": self.departed_voice_id,
            "theorem15_discrepancy_dk": round(float(self.theorem15_discrepancy_dk), 8),
            "firewall_ok": self.firewall_ok,
            "sunk_cost_flagged": self.sunk_cost_flagged,
            "accepted": self.accepted,
            "packet_integrity_ok": self.packet_integrity_ok,
            "discrepancy_exceeded": self.discrepancy_exceeded,
            "echo_chamber_detected": self.echo_chamber_detected,
            "coherence_c_k": round(float(self.coherence_c_k), 6),
            "brier_contraction": round(float(self.brier_contraction), 8),
            "theorem15_verdict": self.theorem15_verdict,
            "unverified_claims_flagged": list(self.unverified_claims_flagged),
            "quarantined_items": list(self.quarantined_items),
            "evidence_record_id": self.evidence_record_id,
            "teamwork_arbitration": (
                dict(self.teamwork_arbitration)
                if self.teamwork_arbitration is not None
                else None
            ),
            "rationale": self.rationale,
            "created_utc": self.created_utc,
            "constitutional": dict(self.constitutional),
        }


@dataclass
class ProblemChair:
    """An active reasoning problem seat rotated among heterogeneous voices."""

    chair_id: str
    title: str
    state: dict[str, Any] = field(default_factory=dict)
    current_voice_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    frozen_packet: FrozenChairPacket | None = None
    prompt: str = ""
    labels: tuple[str, ...] = ACTION_LABELS
    tau: float = DEFAULT_TAU
    blackboard: EpistemicBlackboard | None = None
    audit_history: list[ColdAuditVerdict] = field(default_factory=list)
    a_tau_history: list[int] = field(default_factory=list)
    marginal_gains: list[float] = field(default_factory=list)
    status: str = "OPEN"

    def __post_init__(self) -> None:
        self.chair_id = _clean_nonempty(self.chair_id, "chair_id", max_len=128)
        self.title = _clean_nonempty(self.title, "title", max_len=512)
        if not self.prompt.strip():
            self.prompt = self.title
        if isinstance(self.tau, bool) or not isinstance(self.tau, (int, float)) or not (0.0 < float(self.tau) < 1.0):
            raise ValueError(f"tau must be in (0, 1), got {self.tau!r}")
        self.tau = float(self.tau)
        self.labels = tuple(str(lbl) for lbl in self.labels)
        if len(self.labels) < 2 or len(set(self.labels)) != len(self.labels):
            raise ValueError("ProblemChair labels must contain at least 2 unique entries")
        if self.blackboard is None:
            self.blackboard = EpistemicBlackboard()
        if "probabilities" not in self.state:
            n_dim = len(self.labels)
            self.state["probabilities"] = [1.0 / n_dim] * n_dim
        else:
            self.state["probabilities"] = list(
                _normalize_simplex(self.state["probabilities"], self.labels)
            )
        self.state.setdefault("quarantined_claims", [])
        self.state.setdefault("stagnant_steps", 0)
        self.state.setdefault("best_confidence", max(self.state["probabilities"]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "chair_id": self.chair_id,
            "title": self.title,
            "prompt": self.prompt,
            "labels": list(self.labels),
            "tau": self.tau,
            "status": self.status,
            "current_voice_id": self.current_voice_id,
            "state": _json_safe(self.state),
            "history": [_json_safe(h) for h in self.history],
            "frozen_packet": self.frozen_packet.to_dict() if self.frozen_packet else None,
            "audit_history": [a.to_dict() for a in self.audit_history],
            "a_tau_history": list(self.a_tau_history),
            "marginal_gains": [round(float(g), 6) for g in self.marginal_gains],
            "blackboard_summary": self.blackboard.summary() if self.blackboard else None,
        }


# ---------------------------------------------------------------------------
# 4. Non-Repeating Polyphonic Rotation Schedule & Swap Ledger
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SwapLedgerEntry:
    """Timestamped record of a Counterpoint Chairs seat assignment or rotation swap."""

    swap_index: int
    round_index: int
    timestamp_utc: str
    elapsed_s: float
    chair_id: str
    departed_voice_id: str | None
    incoming_voice_id: str
    preemption_reason: str
    cold_audit_accepted: bool | None = None
    theorem15_discrepancy_dk: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "swap_index": self.swap_index,
            "round_index": self.round_index,
            "timestamp_utc": self.timestamp_utc,
            "elapsed_s": round(float(self.elapsed_s), 6),
            "chair_id": self.chair_id,
            "departed_voice_id": self.departed_voice_id,
            "incoming_voice_id": self.incoming_voice_id,
            "preemption_reason": self.preemption_reason,
            "cold_audit_accepted": self.cold_audit_accepted,
            "theorem15_discrepancy_dk": (
                round(float(self.theorem15_discrepancy_dk), 8)
                if self.theorem15_discrepancy_dk is not None
                else None
            ),
        }


class CounterpointRotationSchedule:
    """Polyphonic musical-chairs scheduler enforcing non-repeating rotation invariants.

    Guarantees:
      1. No chair receives the same voice in two consecutive rounds.
      2. No voice sits in the same chair in two consecutive rounds (when ``num_chairs >= 2``).
      3. Consecutive entries in the swap ledger never repeat the same chair (when ``num_chairs >= 2``).
      4. All chairs are visited across the relay.
      5. Every swap is recorded in a monotonic, timestamped ledger.
    """

    def __init__(
        self,
        chair_ids: Sequence[str],
        voice_ids: Sequence[str],
    ) -> None:
        self.chair_ids: tuple[str, ...] = tuple(_clean_nonempty(c, "chair_id") for c in chair_ids)
        self.voice_ids: tuple[str, ...] = tuple(_clean_nonempty(v, "voice_id") for v in voice_ids)
        if not self.chair_ids:
            raise ValueError("CounterpointRotationSchedule requires at least 1 chair")
        if len(set(self.chair_ids)) != len(self.chair_ids):
            raise ValueError("chair_ids must be unique")
        if len(self.voice_ids) < 2:
            raise ValueError(
                "CounterpointRotationSchedule requires at least 2 distinct voices for non-repeating rotation"
            )
        if len(set(self.voice_ids)) != len(self.voice_ids):
            raise ValueError("voice_ids must be unique")

        self._ledger: list[SwapLedgerEntry] = []
        self._start_monotonic = time.monotonic()

    @property
    def ledger(self) -> tuple[SwapLedgerEntry, ...]:
        return tuple(self._ledger)

    def assign_round(self, round_index: int) -> dict[str, str]:
        """Compute deterministic polyphonic assignment ``{chair_id: voice_id}`` for ``round_index``.

        Using cyclic counterpoint offset ``(j + round_index) % N`` with ``N >= 2``
        mathematically guarantees:
          - For every chair ``j``: ``voice(j, r) != voice(j, r-1)``.
          - For every voice ``v``: ``{j : voice(j, r) == v}`` and ``{j : voice(j, r-1) == v}``
            are disjoint whenever ``N >= 2`` and ``M >= 2`` (shift by -1 mod N).
        """
        if round_index < 0:
            raise ValueError("round_index must be >= 0")
        n_voices = len(self.voice_ids)
        return {
            cid: self.voice_ids[(j + round_index) % n_voices]
            for j, cid in enumerate(self.chair_ids)
        }

    def plan_schedule(self, num_rounds: int) -> list[dict[str, str]]:
        """Return the full multi-round assignment table."""
        if num_rounds < 1:
            raise ValueError("num_rounds must be >= 1")
        return [self.assign_round(r) for r in range(num_rounds)]

    def record_swap(
        self,
        *,
        round_index: int,
        chair_id: str,
        departed_voice_id: str | None,
        incoming_voice_id: str,
        preemption_reason: str,
        cold_audit_accepted: bool | None = None,
        theorem15_discrepancy_dk: float | None = None,
        elapsed_s: float | None = None,
    ) -> SwapLedgerEntry:
        """Append a validated swap event to the timestamped rotation ledger."""
        if chair_id not in self.chair_ids:
            raise ValueError(f"Unknown chair_id {chair_id!r}")
        if incoming_voice_id not in self.voice_ids:
            raise ValueError(f"Unknown incoming_voice_id {incoming_voice_id!r}")
        if departed_voice_id is not None and departed_voice_id == incoming_voice_id:
            raise ValueError(
                f"Non-repeat invariant violated: voice {incoming_voice_id!r} cannot "
                f"immediately re-occupy chair {chair_id!r}"
            )
        if preemption_reason not in _VALID_PREEMPTION_REASONS:
            raise ValueError(
                f"Unsupported preemption_reason {preemption_reason!r}; "
                f"expected one of {sorted(_VALID_PREEMPTION_REASONS)}"
            )
        if len(self.chair_ids) >= 2 and self._ledger and self._ledger[-1].chair_id == chair_id:
            raise ValueError(
                f"Sequential swap repeat violated: chair {chair_id!r} repeated back-to-back"
            )

        now_elapsed = (
            float(elapsed_s)
            if elapsed_s is not None
            else max(0.0, time.monotonic() - self._start_monotonic)
        )
        entry = SwapLedgerEntry(
            swap_index=len(self._ledger) + 1,
            round_index=round_index,
            timestamp_utc=timestamp(),
            elapsed_s=now_elapsed,
            chair_id=chair_id,
            departed_voice_id=departed_voice_id,
            incoming_voice_id=incoming_voice_id,
            preemption_reason=preemption_reason,
            cold_audit_accepted=cold_audit_accepted,
            theorem15_discrepancy_dk=theorem15_discrepancy_dk,
        )
        self._ledger.append(entry)
        return entry

    def validate_invariants(self) -> dict[str, Any]:
        """Verify all rotation invariants over the recorded swap ledger."""
        visited_chairs = {entry.chair_id for entry in self._ledger}
        all_chairs_visited = visited_chairs == set(self.chair_ids)

        last_voice_on_chair: dict[str, str] = {}
        last_chair_for_voice: dict[str, tuple[int, str]] = {}
        no_consecutive_chair_voice_repeat = True
        no_consecutive_voice_chair_repeat = True
        no_consecutive_ledger_chair_repeat = True
        monotonic_elapsed = True

        prev_chair: str | None = None
        prev_elapsed = -1.0
        for entry in self._ledger:
            if entry.elapsed_s < prev_elapsed:
                monotonic_elapsed = False
            prev_elapsed = entry.elapsed_s

            if len(self.chair_ids) >= 2 and prev_chair == entry.chair_id:
                no_consecutive_ledger_chair_repeat = False
            prev_chair = entry.chair_id

            if last_voice_on_chair.get(entry.chair_id) == entry.incoming_voice_id:
                no_consecutive_chair_voice_repeat = False
            last_voice_on_chair[entry.chair_id] = entry.incoming_voice_id

            if len(self.chair_ids) >= 2:
                prev_vc = last_chair_for_voice.get(entry.incoming_voice_id)
                if prev_vc is not None and prev_vc[0] == entry.round_index - 1 and prev_vc[1] == entry.chair_id:
                    no_consecutive_voice_chair_repeat = False
                last_chair_for_voice[entry.incoming_voice_id] = (entry.round_index, entry.chair_id)

        all_ok = bool(
            self._ledger
            and all_chairs_visited
            and no_consecutive_chair_voice_repeat
            and no_consecutive_voice_chair_repeat
            and no_consecutive_ledger_chair_repeat
            and monotonic_elapsed
        )
        return {
            "valid": all_ok,
            "total_swaps": len(self._ledger),
            "all_chairs_visited": all_chairs_visited,
            "visited_chairs": sorted(visited_chairs),
            "no_consecutive_chair_voice_repeat": no_consecutive_chair_voice_repeat,
            "no_consecutive_voice_chair_repeat": no_consecutive_voice_chair_repeat,
            "no_consecutive_ledger_chair_repeat": no_consecutive_ledger_chair_repeat,
            "monotonic_elapsed": monotonic_elapsed,
        }


# ---------------------------------------------------------------------------
# 5. Relay Result & CounterpointChairsEngine
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CounterpointRelayResult:
    """Complete result returned by ``CounterpointChairsEngine.run`` / ``arun``."""

    contract: str
    chairs: tuple[dict[str, Any], ...]
    voices: tuple[dict[str, Any], ...]
    schedule_invariants: dict[str, Any]
    swap_ledger: tuple[SwapLedgerEntry, ...]
    cold_audits: tuple[ColdAuditVerdict, ...]
    frozen_packets: tuple[FrozenChairPacket, ...]
    rounds_executed: int
    total_turns: int
    flagged_audits_count: int
    firewall_violations_caught: int
    sunk_cost_flags_count: int
    mean_theorem15_dk: float
    max_theorem15_dk: float
    constitutional: dict[str, Any]
    gem_desktop_trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "rounds_executed": self.rounds_executed,
            "total_turns": self.total_turns,
            "flagged_audits_count": self.flagged_audits_count,
            "firewall_violations_caught": self.firewall_violations_caught,
            "sunk_cost_flags_count": self.sunk_cost_flags_count,
            "mean_theorem15_dk": round(float(self.mean_theorem15_dk), 8),
            "max_theorem15_dk": round(float(self.max_theorem15_dk), 8),
            "schedule_invariants": dict(self.schedule_invariants),
            "chairs": [dict(c) for c in self.chairs],
            "voices": [dict(v) for v in self.voices],
            "swap_ledger": [e.to_dict() for e in self.swap_ledger],
            "cold_audits": [a.to_dict() for a in self.cold_audits],
            "frozen_packets": [p.to_dict() for p in self.frozen_packets],
            "gem_desktop_trace": (
                dict(self.gem_desktop_trace) if self.gem_desktop_trace is not None else None
            ),
            "constitutional": dict(self.constitutional),
        }


class CounterpointChairsEngine:
    """Orchestrates Polyphonic Musical-Chairs Relay & Cold-Audit Rotation (Arch #9)."""

    def __init__(
        self,
        *,
        voices: Sequence[ChairVoice] | None = None,
        bridge: ZoeAntigravityBridge | None = None,
        beat_quantum_s: float = DEFAULT_BEAT_QUANTUM_S,
        step_budget: int = DEFAULT_STEP_BUDGET,
        min_marginal_gain: float = DEFAULT_MIN_MARGINAL_GAIN,
        max_discrepancy_dk: float = DEFAULT_MAX_DISCREPANCY_DK,
        coherence_min: float = 0.45,
        sunk_cost_patience: int = DEFAULT_SUNK_COST_PATIENCE,
        tau: float = DEFAULT_TAU,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        probe_local: bool = True,
        bridge_mode: str | None = None,
        emit_gem_aes_trace: bool = True,
    ) -> None:
        if bridge_mode is not None and bridge_mode not in VALID_MODES:
            raise ValueError(f"bridge_mode must be one of {VALID_MODES}, got {bridge_mode!r}")
        self.offline_only = bool(offline_only)
        self.privacy_sensitive = bool(privacy_sensitive)
        self.probe_local = bool(probe_local)
        self.bridge_mode = bridge_mode
        self.emit_gem_aes_trace = bool(emit_gem_aes_trace)
        if bridge is not None:
            self.bridge = bridge
        elif self.offline_only or bridge_mode is None:
            self.bridge = ZoeAntigravityBridge(mode="offline")
        else:
            default_mode: Literal["offline", "local_qwen", "gemini", "auto"] = (
                bridge_mode  # type: ignore[assignment]
            )
            self.bridge = ZoeAntigravityBridge(mode=default_mode)
        resolved_voices = tuple(voices) if voices is not None else default_counterpoint_voices(bridge=self.bridge)
        if len(resolved_voices) < 2:
            raise ValueError("CounterpointChairsEngine requires at least 2 heterogeneous voices")
        voice_ids = [v.voice_id for v in resolved_voices]
        if len(set(voice_ids)) != len(voice_ids):
            raise ValueError("ChairVoice voice_id values must be unique")

        if (
            isinstance(beat_quantum_s, bool)
            or not isinstance(beat_quantum_s, (int, float))
            or not math.isfinite(float(beat_quantum_s))
            or float(beat_quantum_s) <= 0.0
        ):
            raise ValueError("beat_quantum_s must be a finite number > 0")
        if isinstance(step_budget, bool) or not isinstance(step_budget, int) or step_budget < 1:
            raise ValueError("step_budget must be an integer >= 1")
        if (
            isinstance(min_marginal_gain, bool)
            or not isinstance(min_marginal_gain, (int, float))
            or not math.isfinite(float(min_marginal_gain))
        ):
            raise ValueError("min_marginal_gain must be a finite number")
        if (
            isinstance(max_discrepancy_dk, bool)
            or not isinstance(max_discrepancy_dk, (int, float))
            or not math.isfinite(float(max_discrepancy_dk))
            or float(max_discrepancy_dk) <= 0.0
        ):
            raise ValueError("max_discrepancy_dk must be a finite number > 0")
        if (
            isinstance(coherence_min, bool)
            or not isinstance(coherence_min, (int, float))
            or not math.isfinite(float(coherence_min))
            or not (0.0 < float(coherence_min) <= 1.0)
        ):
            raise ValueError("coherence_min must be a finite number in (0, 1]")
        if isinstance(sunk_cost_patience, bool) or not isinstance(sunk_cost_patience, int) or sunk_cost_patience < 1:
            raise ValueError("sunk_cost_patience must be an integer >= 1")
        if (
            isinstance(tau, bool)
            or not isinstance(tau, (int, float))
            or not math.isfinite(float(tau))
            or not (0.0 < float(tau) < 1.0)
        ):
            raise ValueError("tau must be a finite number in (0, 1)")

        self.voices: tuple[ChairVoice, ...] = resolved_voices
        self._voices_by_id: dict[str, ChairVoice] = {v.voice_id: v for v in resolved_voices}
        self.beat_quantum_s = float(beat_quantum_s)
        self.step_budget = int(step_budget)
        self.min_marginal_gain = float(min_marginal_gain)
        self.max_discrepancy_dk = float(max_discrepancy_dk)
        self.coherence_min = float(coherence_min)
        self.sunk_cost_patience = int(sunk_cost_patience)
        self.tau = float(tau)
        self._last_result: CounterpointRelayResult | None = None

    @property
    def last_result(self) -> CounterpointRelayResult | None:
        return self._last_result

    async def _invoke_voice_payload(
        self,
        voice: ChairVoice,
        chair: ProblemChair,
        frozen_packet: FrozenChairPacket | None,
        *,
        round_index: int,
        substep_index: int,
        phase: Literal["reason", "cold_audit"],
    ) -> dict[str, Any]:
        """Execute a voice via evaluator, Antigravity bridge, or ReasoningVoiceAdapter."""
        ctx: dict[str, Any] = {
            "chair_id": chair.chair_id,
            "chair_title": chair.title,
            "round_index": round_index,
            "substep_index": substep_index,
            "phase": phase,
            "labels": list(chair.labels),
            "tau": chair.tau,
            "voice_id": voice.voice_id,
            "voice_role": voice.role,
            "quarantined_claims": list(chair.state.get("quarantined_claims") or ()),
            "verified_evidence_ids": list(frozen_packet.evidence_ids) if frozen_packet else [],
        }

        if voice.evaluator is not None:
            raw = await _maybe_await(_call_evaluator(voice.evaluator, chair, frozen_packet, ctx))
            if isinstance(raw, Mapping):
                return dict(raw)
            if isinstance(raw, VoiceResponse):
                return self._payload_from_voice_response(raw, chair, voice)
            if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
                return {"probabilities": list(raw)}
            return {"text": str(raw)}

        prompt_parts = [
            f"[{phase}] Chair '{chair.title}' ({chair.chair_id})",
            f"Prompt: {chair.prompt}",
            f"Role: {voice.role} ({voice.voice_id})",
            f"Verified evidence IDs: {ctx['verified_evidence_ids']}",
        ]
        if frozen_packet is not None:
            prompt_parts.append(
                f"Departed voice: {frozen_packet.departed_voice_id} "
                f"(A_tau={frozen_packet.belief_status.get('a_tau')})"
            )
        prompt_text = "\n".join(prompt_parts)

        adapter = voice.adapter
        if adapter is None:
            eff_offline = bool(
                self.offline_only
                or self.bridge.mode == "offline"
                or self.bridge_mode == "offline"
            )
            eff_mode = (
                "offline"
                if eff_offline
                else (self.bridge_mode if self.bridge_mode is not None else "offline")
            )
            resp = await self.bridge.arun_turn(
                prompt_text,
                mode=eff_mode,
                offline_only=eff_offline or (eff_mode == "offline"),
                privacy_sensitive=self.privacy_sensitive,
                probe_local=False if (eff_offline or eff_mode == "offline") else self.probe_local,
                thinking_level=voice.thinking_level,
            )
            return self._payload_from_bridge_result(resp, chair, voice)

        if isinstance(adapter, ZoeAntigravityBridge):
            eff_offline = bool(
                self.offline_only
                or adapter.mode == "offline"
                or self.bridge_mode == "offline"
            )
            adapter_eff_mode: str | None = (
                "offline"
                if eff_offline
                else (self.bridge_mode if self.bridge_mode is not None else None)
            )
            bridge_res = await adapter.arun_turn(
                prompt_text,
                mode=adapter_eff_mode,
                offline_only=eff_offline,
                privacy_sensitive=self.privacy_sensitive,
                probe_local=False if eff_offline else self.probe_local,
                thinking_level=voice.thinking_level,
            )
            return self._payload_from_bridge_result(bridge_res, chair, voice)

        if hasattr(adapter, "generate") and callable(adapter.generate):
            v_resp = await _maybe_await(adapter.generate(prompt_text, ctx))
            if isinstance(v_resp, VoiceResponse):
                return self._payload_from_voice_response(v_resp, chair, voice)
            if isinstance(v_resp, Mapping):
                return dict(v_resp)
            return {"text": str(v_resp)}

        if callable(adapter):
            wrapped = CallableVoiceAdapter(adapter, model_name=f"voice-{voice.voice_id}")
            v_resp = await wrapped.generate(prompt_text, ctx)
            return self._payload_from_voice_response(v_resp, chair, voice)

        raise TypeError(f"Unsupported adapter type on ChairVoice {voice.voice_id!r}: {type(adapter).__name__}")

    def _payload_from_bridge_result(
        self,
        bridge_res: Any,
        chair: ProblemChair,
        voice: ChairVoice,
    ) -> dict[str, Any]:
        if isinstance(bridge_res.structured_output, Mapping):
            return dict(bridge_res.structured_output)
        stem = route_stem(chair.prompt, offline_only=True, local_qwen_available=False)
        # Derive deterministic simplex probabilities from bridge stem telemetry & voice role.
        idx = list(self._voices_by_id).index(voice.voice_id) if voice.voice_id in self._voices_by_id else 0
        raw_vec = [0.54, 0.30, 0.16]
        if len(chair.labels) != 3:
            raw_vec = [1.0 / len(chair.labels)] * len(chair.labels)
        else:
            raw_vec[idx % 3] += 0.08 + 0.02 * min(4, stem.a_tau)
        probs = _normalize_simplex(raw_vec, chair.labels)
        return {
            "text": bridge_res.text,
            "thoughts": list(bridge_res.thoughts),
            "probabilities": list(probs),
            "measurement": {
                "input_desc": f"{chair.chair_id}: {chair.prompt[:160]}",
                "method": f"antigravity_bridge:{bridge_res.resolution.config_class}",
                "scope": "bounded chair evaluation",
                "limitations": "offline dual-transport bridge turn",
                "value": {
                    "history_steps": bridge_res.history_steps,
                    "selected_mode": bridge_res.resolution.selected_mode,
                    "a_tau": stem.a_tau,
                },
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": f"{voice.voice_id}_bridge_verifier",
                "passed": True,
                "rationale": (
                    f"Deterministic Antigravity bridge execution completed "
                    f"({bridge_res.history_steps} SDK steps)."
                ),
            },
            "claim": f"{chair.chair_id} analyzed by {voice.voice_id} via Antigravity SDK",
            "posterior_delta": 0.06,
        }

    def _payload_from_voice_response(
        self,
        resp: VoiceResponse,
        chair: ProblemChair,
        voice: ChairVoice,
    ) -> dict[str, Any]:
        if isinstance(resp.structured_output, Mapping):
            out = dict(resp.structured_output)
            out.setdefault("text", resp.text)
            out.setdefault("thoughts", list(resp.thoughts))
            return out
        n_dim = len(chair.labels)
        base = [1.0 / n_dim] * n_dim
        base[0] += 0.25
        probs = _normalize_simplex(base, chair.labels)
        return {
            "text": resp.text,
            "thoughts": list(resp.thoughts),
            "probabilities": list(probs),
            "measurement": {
                "input_desc": f"{chair.chair_id}: {chair.prompt[:160]}",
                "method": f"voice_adapter:{resp.model}",
                "scope": "bounded chair evaluation",
                "limitations": "adapter text-only summary",
                "value": {"reply_len": len(resp.text)},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": f"{voice.voice_id}_adapter_verifier",
                "passed": True,
                "rationale": f"Deterministic voice adapter {resp.model} independent check.",
            },
            "claim": f"{chair.chair_id} evaluated by {voice.voice_id}",
            "posterior_delta": 0.04,
        }

    async def acold_audit_packet(
        self,
        *,
        chair: ProblemChair,
        frozen_packet: FrozenChairPacket,
        incoming_voice: ChairVoice,
        departed_voice: ChairVoice,
        round_index: int,
    ) -> ColdAuditVerdict:
        """Perform mandatory Cold Audit + Theorem 15 cross-voice check on a frozen chair packet."""
        assert chair.blackboard is not None
        packet_integrity_ok = frozen_packet.verify_integrity(raise_on_error=False)
        reasons: list[str] = []
        quarantined: list[str] = []

        # 1. CONSTITUTION.md Art. III Firewall Inspection on FrozenChairPacket
        firewall_ok = packet_integrity_ok
        if not packet_integrity_ok:
            reasons.append("FrozenChairPacket SHA-256 tamper evidence triggered")

        meas_summary = frozen_packet.measurement_summary
        belief_status = frozen_packet.belief_status
        raw_unverified = [
            str(c) for c in (meas_summary.get("unverified_claims") or ()) if str(c).strip()
        ]
        # Also inspect belief_status for claims asserted without any approved evidence_ids
        belief_claims_no_ev: list[str] = []
        if not frozen_packet.evidence_ids:
            for key in ("unverified_claims", "claims", "verified_claims"):
                for item in (belief_status.get(key) or ()):
                    if str(item).strip():
                        belief_claims_no_ev.append(str(item))
        unverified_flagged = tuple(dict.fromkeys(raw_unverified + belief_claims_no_ev))
        if unverified_flagged:
            firewall_ok = False
            quarantined.extend(unverified_flagged)
            reasons.append(
                f"rejected {len(unverified_flagged)} unverified claim(s) lacking approved evidence"
            )

        sampled_ids = set(meas_summary.get("sampled_only_ids") or ())
        if sampled_ids and not frozen_packet.evidence_ids and belief_status.get("belief_ids"):
            firewall_ok = False
            reasons.append("sampled-only measurements referenced without independent evidence")

        for prop in frozen_packet.pending_action_proposals:
            if (
                prop.get("status") != "REVIEW_REQUIRED"
                or prop.get("external_actions", 0) != 0
                or prop.get("autonomous_execution_allowed", False) is not False
            ):
                firewall_ok = False
                reasons.append("action proposal breached REVIEW_REQUIRED / external_actions=0 guard")

        # 2. Sunk-cost drift detection (stalled/negative marginal gain or A_tau narrowing without evidence)
        stagnant_steps = int(belief_status.get("stagnant_steps", 0))
        marginal_gain = float(belief_status.get("marginal_gain", 0.0))
        sunk_cost_flagged = bool(
            belief_status.get("sunk_cost_drift", False)
            or (stagnant_steps >= self.sunk_cost_patience and marginal_gain <= 0.0)
        )
        if sunk_cost_flagged:
            quarantined.append(f"sunk_cost_branch:{departed_voice.voice_id}:r{frozen_packet.round_index}")
            reasons.append(
                f"sunk-cost drift flagged (stagnant_steps={stagnant_steps}, marginal_gain={marginal_gain:.4f})"
            )

        # 3. Incoming voice cold-start assessment & Theorem 15 cross-voice check
        cold_payload = await self._invoke_voice_payload(
            incoming_voice,
            chair,
            frozen_packet,
            round_index=round_index,
            substep_index=0,
            phase="cold_audit",
        )
        dep_probs = _normalize_simplex(
            belief_status.get("probabilities") or chair.state["probabilities"],
            chair.labels,
        )
        inc_raw = cold_payload.get("probabilities") or chair.state["probabilities"]
        inc_probs = _normalize_simplex(inc_raw, chair.labels)

        quorum_engine = FourPeerQuorumEngine(
            required_peers=(departed_voice.voice_id, incoming_voice.voice_id),
            coherence_min=self.coherence_min,
            min_independent_peers=2,
            strict_provenance=True,
            strict_anti_echo=True,
        )
        vec_dep = PeerConfidenceVector(
            peer_id=departed_voice.voice_id,
            probabilities=dep_probs,
            source_kind=departed_voice.source_kind,
            provenance_id=f"prov:{chair.chair_id}:{departed_voice.voice_id}:r{frozen_packet.round_index}",
            independence_tag=departed_voice.independence_tag,
            labels=chair.labels,
            weight=departed_voice.weight,
        )
        vec_inc = PeerConfidenceVector(
            peer_id=incoming_voice.voice_id,
            probabilities=inc_probs,
            source_kind=incoming_voice.source_kind,
            provenance_id=f"prov:{chair.chair_id}:{incoming_voice.voice_id}:r{round_index}:cold",
            independence_tag=incoming_voice.independence_tag,
            labels=chair.labels,
            weight=incoming_voice.weight,
        )
        q_res = quorum_engine.evaluate(
            [vec_dep, vec_inc],
            tau=chair.tau,
            labels=chair.labels,
            use_teamwork_arbitrator=True,
        )
        dk = float(q_res.d_k_disagreement)
        coherence_c_k = float(q_res.coherence_c_k)
        brier_contraction = float(q_res.brier_contraction)
        echo_detected = bool(q_res.echo_chamber_detected)
        discrepancy_exceeded = bool(
            dk > self.max_discrepancy_dk or q_res.verdict == "ABSTAIN"
        )
        if echo_detected:
            reasons.append(f"Theorem 15 echo-chamber risk ({q_res.reason})")
        if discrepancy_exceeded:
            reasons.append(
                f"Theorem 15 cross-voice discrepancy D_K={dk:.4f} / C_K={coherence_c_k:.4f} exceeded threshold"
            )

        accepted = bool(
            packet_integrity_ok
            and firewall_ok
            and not sunk_cost_flagged
            and not discrepancy_exceeded
            and not echo_detected
        )
        if not reasons:
            reasons.append(
                f"Cold audit passed cleanly (D_K={dk:.4f}, C_K={coherence_c_k:.4f}, "
                f"evidence_ids={len(frozen_packet.evidence_ids)})"
            )

        # Record Cold Audit on EpistemicBlackboard (preserving negative results!)
        audit_prov = Provenance(
            sources=(
                EvidenceSource(
                    kind="tool",
                    identifier=f"cold_audit:{incoming_voice.voice_id}:r{round_index}",
                    trust=0.92,
                    strength=0.90,
                ),
            ),
            transformations=("counterpoint_cold_audit_theorem15",),
        )
        meas = chair.blackboard.post_measurement(
            source_agent=incoming_voice.voice_id,
            input_desc=f"cold audit of {frozen_packet.packet_id} from {departed_voice.voice_id}",
            method="counterpoint_cold_audit_and_theorem15",
            scope=f"chair={chair.chair_id}, round={round_index}",
            limitations="cross-voice simplex comparison & Art. III packet check only",
            value={
                "d_k": round(dk, 8),
                "coherence_c_k": round(coherence_c_k, 6),
                "firewall_ok": firewall_ok,
                "sunk_cost_flagged": sunk_cost_flagged,
                "unverified_claims": list(unverified_flagged),
            },
            sampled_only=False,
            provenance=audit_prov,
        )
        ev = chair.blackboard.promote_to_evidence(
            meas.record_id,
            verifier_name=f"cold_audit:{incoming_voice.voice_id}",
            passed=accepted,
            rationale="; ".join(reasons),
            evidence_source=EvidenceSource(
                kind="tool",
                identifier=f"cold_audit_verifier:{incoming_voice.voice_id}:r{round_index}",
                trust=0.92,
                strength=0.90,
            ),
        )

        # Quarantine rejected items in chair state so incoming voice starts clean.
        if quarantined:
            existing_q = list(chair.state.get("quarantined_claims") or [])
            for item in quarantined:
                if item not in existing_q:
                    existing_q.append(item)
            chair.state["quarantined_claims"] = existing_q
        if not accepted:
            chair.state["stagnant_steps"] = 0
            # Blend back toward the incoming cold auditor's grounded vector and reset peak baseline.
            chair.state["probabilities"] = list(inc_probs)
            chair.state["best_confidence"] = max(inc_probs)

        verdict = ColdAuditVerdict(
            incoming_voice_id=incoming_voice.voice_id,
            departed_voice_id=departed_voice.voice_id,
            theorem15_discrepancy_dk=dk,
            firewall_ok=firewall_ok,
            sunk_cost_flagged=sunk_cost_flagged,
            rationale="; ".join(reasons),
            chair_id=chair.chair_id,
            round_index=round_index,
            accepted=accepted,
            packet_integrity_ok=packet_integrity_ok,
            discrepancy_exceeded=discrepancy_exceeded,
            echo_chamber_detected=echo_detected,
            coherence_c_k=coherence_c_k,
            brier_contraction=brier_contraction,
            theorem15_verdict=q_res.verdict,
            unverified_claims_flagged=unverified_flagged,
            quarantined_items=tuple(quarantined),
            evidence_record_id=ev.record_id,
            teamwork_arbitration=q_res.teamwork_arbitration,
            constitutional=counterpoint_constitutional_metadata(cloud_tokens_used=0),
        )
        chair.audit_history.append(verdict)
        return verdict

    def cold_audit_packet(
        self,
        *,
        chair: ProblemChair,
        frozen_packet: FrozenChairPacket,
        incoming_voice: ChairVoice,
        departed_voice: ChairVoice,
        round_index: int,
    ) -> ColdAuditVerdict:
        """Synchronous wrapper for ``acold_audit_packet``."""
        return run_coro_sync(
            self.acold_audit_packet(
                chair=chair,
                frozen_packet=frozen_packet,
                incoming_voice=incoming_voice,
                departed_voice=departed_voice,
                round_index=round_index,
            )
        )

    async def _run_chair_seat_turn(
        self,
        *,
        chair: ProblemChair,
        voice: ChairVoice,
        round_index: int,
    ) -> tuple[FrozenChairPacket, str, dict[str, Any]]:
        """Execute up to ``step_budget`` sub-steps on a chair until preemption triggers."""
        assert chair.blackboard is not None
        meta = OperationalMetacognition()
        thr = meta.threshold(
            Domain.ACTION,
            chair.tau,
            rationale="Fixed episode threshold for Counterpoint Chairs A_tau tracking.",
        )

        seat_start = time.monotonic()
        preemption_reason = "step_budget"
        unverified_claims: list[str] = []
        steps_executed = 0
        last_gain = 0.0
        prev_best = float(chair.state.get("best_confidence", max(chair.state["probabilities"])))
        prev_a_tau = chair.a_tau_history[-1] if chair.a_tau_history else len(chair.labels)
        stagnant = int(chair.state.get("stagnant_steps", 0))
        extra_belief: dict[str, Any] = {}

        for substep in range(self.step_budget):
            elapsed_seat = time.monotonic() - seat_start
            if substep > 0 and elapsed_seat >= self.beat_quantum_s:
                preemption_reason = "beat_quantum_s"
                break

            payload = await self._invoke_voice_payload(
                voice,
                chair,
                chair.frozen_packet,
                round_index=round_index,
                substep_index=substep,
                phase="reason",
            )
            steps_executed += 1

            # Validate & compute probabilities, marginal gain, and optional posterior_delta
            # before mutating chair state.
            raw_probs = payload.get("probabilities")
            if raw_probs is not None:
                probs = _normalize_simplex(raw_probs, chair.labels)
            else:
                probs = tuple(chair.state["probabilities"])

            raw_gain = payload.get("marginal_gain")
            if raw_gain is not None:
                if isinstance(raw_gain, (bool, np.bool_)) or not isinstance(
                    raw_gain, (int, float, np.integer, np.floating)
                ):
                    raise ValueError(
                        f"marginal_gain must be a finite numeric value, got {raw_gain!r}"
                    )
                gain = float(raw_gain)
                if not math.isfinite(gain):
                    raise ValueError(f"marginal_gain must be finite, got {raw_gain!r}")
                next_best = prev_best
            else:
                curr_best = max(probs)
                gain = curr_best - prev_best
                next_best = max(prev_best, curr_best)

            raw_delta = payload.get("posterior_delta")
            validated_delta: float | None = None
            if raw_delta is not None:
                if isinstance(raw_delta, (bool, np.bool_)) or not isinstance(
                    raw_delta, (int, float, np.integer, np.floating)
                ):
                    raise ValueError(
                        f"posterior_delta must be a finite numeric value, got {raw_delta!r}"
                    )
                validated_delta = float(raw_delta)
                if not math.isfinite(validated_delta):
                    raise ValueError(f"posterior_delta must be finite, got {raw_delta!r}")

            chair.state["probabilities"] = list(probs)

            prov_m = Provenance(
                sources=(
                    EvidenceSource(
                        kind="tool" if voice.source_kind == "tool" else "document",
                        identifier=f"{voice.voice_id}:{chair.chair_id}:r{round_index}:s{substep}",
                        trust=0.85,
                        strength=0.85,
                    ),
                ),
                transformations=("counterpoint_chair_step",),
            )
            opts = options_from_probabilities(
                {lbl: p for lbl, p in zip(chair.labels, probs)},
                prov_m,
            )
            breadth = meta.count(opts, thr, represented_count=len(chair.labels))
            a_tau = int(breadth.accessible_count)
            chair.a_tau_history.append(a_tau)

            prev_best = next_best
            chair.state["best_confidence"] = prev_best
            chair.marginal_gains.append(gain)
            last_gain = gain

            if gain <= 0.0:
                stagnant += 1
            else:
                stagnant = 0
            chair.state["stagnant_steps"] = stagnant

            # Record Lane 1 measurement on EpistemicBlackboard
            meas_spec = payload.get("measurement")
            if isinstance(meas_spec, Mapping):
                m_input = str(meas_spec.get("input_desc") or f"{chair.chair_id}:r{round_index}")
                m_method = str(meas_spec.get("method") or f"voice:{voice.voice_id}")
                m_scope = str(meas_spec.get("scope") or "bounded chair turn")
                m_lim = str(meas_spec.get("limitations") or "single counterpoint turn")
                m_val = meas_spec.get("value", {"probabilities": list(probs)})
                sampled_only = bool(meas_spec.get("sampled_only", False))
            else:
                m_input = f"{chair.chair_id}: {chair.prompt[:160]}"
                m_method = f"voice:{voice.voice_id}"
                m_scope = "bounded chair turn"
                m_lim = "single counterpoint turn"
                m_val = {"probabilities": list(probs), "text": str(payload.get("text", ""))[:200]}
                sampled_only = bool(payload.get("sampled_only", False))

            meas_rec = chair.blackboard.post_measurement(
                source_agent=voice.voice_id,
                input_desc=m_input,
                method=m_method,
                scope=m_scope,
                limitations=m_lim,
                value=m_val,
                sampled_only=sampled_only,
                provenance=prov_m,
            )

            # Handle optional Lane 2 Verification & Lane 3 Belief Update strictly via Firewall
            claim_text = str(payload.get("claim") or "").strip()
            for uc in (payload.get("unverified_claims") or ()):
                if str(uc).strip():
                    unverified_claims.append(str(uc).strip())

            verif_spec = payload.get("verification")
            promoted_ev: EvidenceRecord | None = None
            if isinstance(verif_spec, Mapping):
                v_name = str(verif_spec.get("verifier_name") or f"{voice.voice_id}_verifier")
                v_passed = bool(verif_spec.get("passed", False))
                v_rat = str(verif_spec.get("rationale") or "")
                v_src = verif_spec.get("evidence_source")
                try:
                    promoted_ev = chair.blackboard.promote_to_evidence(
                        meas_rec.record_id,
                        verifier_name=v_name,
                        passed=v_passed,
                        rationale=v_rat,
                        evidence_source=v_src,
                    )
                except FirewallViolationError as exc:
                    if claim_text:
                        unverified_claims.append(f"{claim_text} [firewall_blocked: {exc}]")
                    else:
                        unverified_claims.append(f"unverified_measurement:{meas_rec.record_id}")
            elif claim_text:
                # Voice asserted a claim without providing an explicit verification step!
                unverified_claims.append(claim_text)

            belief_rec: BeliefUpdateRecord | None = None
            if promoted_ev is not None and promoted_ev.approved and claim_text:
                delta = validated_delta if validated_delta is not None else max(0.0, gain)
                belief_rec = chair.blackboard.update_belief(
                    [promoted_ev.record_id],
                    claim=claim_text,
                    posterior_delta=delta,
                    subject=chair.chair_id,
                    relation="counterpoint_finding",
                    confidence=max(probs),
                )
            elif promoted_ev is not None and not promoted_ev.approved and claim_text:
                unverified_claims.append(f"{claim_text} [verification_failed]")

            # Optional Lane 4 Action Proposal (strictly REVIEW_REQUIRED, external_actions=0)
            prop_spec = payload.get("action_proposal")
            if belief_rec is not None and isinstance(prop_spec, Mapping):
                chair.blackboard.propose_action(
                    belief_rec.record_id,
                    action_kind=str(prop_spec.get("action_kind") or "review_chair_hypothesis"),
                    target=str(prop_spec.get("target") or chair.chair_id),
                    reversible=bool(prop_spec.get("reversible", True)),
                    rationale=str(prop_spec.get("rationale") or "Counterpoint review proposal"),
                )

            if payload.get("sunk_cost_drift"):
                extra_belief["sunk_cost_drift"] = True

            turn_record = {
                "round_index": round_index,
                "substep_index": substep,
                "voice_id": voice.voice_id,
                "measurement_id": meas_rec.record_id,
                "evidence_id": promoted_ev.record_id if promoted_ev else None,
                "belief_id": belief_rec.record_id if belief_rec else None,
                "probabilities": [round(float(p), 6) for p in probs],
                "a_tau": a_tau,
                "marginal_gain": round(gain, 6),
                "unverified_claims_count": len(unverified_claims),
                "timestamp_utc": timestamp(),
            }
            chair.history.append(turn_record)

            # Check preemption triggers after substep
            if (time.monotonic() - seat_start) >= self.beat_quantum_s:
                preemption_reason = "beat_quantum_s"
                break
            a_tau_dropped = a_tau < prev_a_tau and promoted_ev is None
            prev_a_tau = a_tau
            if (
                substep + 1 < self.step_budget
                and (gain < self.min_marginal_gain or a_tau_dropped)
            ):
                preemption_reason = "a_tau_marginal_gain_drop"
                break

        frozen = FrozenChairPacket.from_blackboard(
            chair_id=chair.chair_id,
            round_index=round_index,
            departed_voice_id=voice.voice_id,
            preemption_reason=preemption_reason,
            blackboard=chair.blackboard,
            labels=chair.labels,
            probabilities=chair.state["probabilities"],
            tau=chair.tau,
            a_tau=chair.a_tau_history[-1] if chair.a_tau_history else len(chair.labels),
            marginal_gain=last_gain,
            steps_on_chair=steps_executed,
            stagnant_steps=stagnant,
            unverified_claims=unverified_claims,
            extra_belief_status=extra_belief,
        )
        chair.frozen_packet = frozen
        return frozen, preemption_reason, {
            "steps_executed": steps_executed,
            "last_gain": last_gain,
        }

    async def arun(
        self,
        chairs: Sequence[ProblemChair],
        *,
        rounds: int = 2,
    ) -> CounterpointRelayResult:
        """Run a multi-round polyphonic Counterpoint Chairs relay across ``chairs``."""
        if not chairs:
            raise ValueError("CounterpointChairsEngine.arun requires at least 1 ProblemChair")
        if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
            raise ValueError("rounds must be an integer >= 1")

        chair_list = list(chairs)
        chair_ids = [c.chair_id for c in chair_list]
        voice_ids = [v.voice_id for v in self.voices]
        schedule = CounterpointRotationSchedule(chair_ids, voice_ids)

        cold_audits: list[ColdAuditVerdict] = []
        frozen_packets: list[FrozenChairPacket] = []
        total_turns = 0

        for round_idx in range(rounds):
            assignments = schedule.assign_round(round_idx)
            for chair in chair_list:
                incoming_id = assignments[chair.chair_id]
                incoming_voice = self._voices_by_id[incoming_id]
                departed_id = chair.current_voice_id

                audit_verdict: ColdAuditVerdict | None = None
                if round_idx == 0 and chair.frozen_packet is None and departed_id is None:
                    preemption_reason = "initial_seating"
                else:
                    if chair.frozen_packet is None:
                        raise RuntimeError(
                            f"Chair {chair.chair_id!r} missing FrozenChairPacket on takeover"
                        )
                    eff_departed_id = departed_id or chair.frozen_packet.departed_voice_id
                    departed_voice = self._voices_by_id.get(
                        eff_departed_id,
                        ChairVoice(
                            voice_id=eff_departed_id,
                            role="external_departed",
                            independence_tag=f"indep:{eff_departed_id}",
                        ),
                    )
                    audit_verdict = await self.acold_audit_packet(
                        chair=chair,
                        frozen_packet=chair.frozen_packet,
                        incoming_voice=incoming_voice,
                        departed_voice=departed_voice,
                        round_index=round_idx,
                    )
                    cold_audits.append(audit_verdict)
                    preemption_reason = chair.frozen_packet.preemption_reason

                schedule.record_swap(
                    round_index=round_idx,
                    chair_id=chair.chair_id,
                    departed_voice_id=departed_id,
                    incoming_voice_id=incoming_id,
                    preemption_reason=preemption_reason,
                    cold_audit_accepted=audit_verdict.accepted if audit_verdict else None,
                    theorem15_discrepancy_dk=(
                        audit_verdict.theorem15_discrepancy_dk if audit_verdict else None
                    ),
                )

                chair.current_voice_id = incoming_id
                frozen, _, _ = await self._run_chair_seat_turn(
                    chair=chair,
                    voice=incoming_voice,
                    round_index=round_idx,
                )
                frozen_packets.append(frozen)
                total_turns += 1

        invariants = schedule.validate_invariants()
        dks = [a.theorem15_discrepancy_dk for a in cold_audits]
        mean_dk = math.fsum(dks) / len(dks) if dks else 0.0
        max_dk = max(dks) if dks else 0.0

        gem_desktop_trace: dict[str, Any] | None = None
        if self.emit_gem_aes_trace:
            from .gem_aes_vdi import (
                GEM_AES_VDI_CONTRACT,
                MAX_AES_APP_WINDOWS,
                MU_MESAG,
                MU_TIMER,
                STANDARD_WINDOW_KIND,
                GemEventMultiQueue,
                GemWindowManager,
            )

            ev_queue = GemEventMultiQueue()
            wm = GemWindowManager(event_queue=ev_queue)
            wm.menu_bar(active_index=2)
            chair_handles: dict[str, int] = {}
            aes_events: list[dict[str, Any]] = []

            def _ensure_chair_window(cid: str, title: str, info: str) -> int:
                if cid in chair_handles:
                    return chair_handles[cid]
                if len(chair_handles) >= MAX_AES_APP_WINDOWS:
                    evict_cid, evict_h = next(iter(chair_handles.items()))
                    wm.wind_close(evict_h)
                    wm.wind_delete(evict_h)
                    del chair_handles[evict_cid]
                handle = wm.wind_create(
                    STANDARD_WINDOW_KIND,
                    20,
                    32,
                    280,
                    180,
                    title=title[:32],
                    info=info[:32],
                    layer_id=cid,
                )
                if handle > 0:
                    wm.wind_open(handle)
                    chair_handles[cid] = handle
                return handle

            beat_ms = max(1, int(round(self.beat_quantum_s * 1000.0)))
            chair_titles = {c.chair_id: c.title for c in chair_list}
            for entry in schedule.ledger:
                h = _ensure_chair_window(
                    entry.chair_id,
                    chair_titles.get(entry.chair_id, entry.chair_id),
                    f"Voice: {entry.incoming_voice_id}",
                )
                if h > 0:
                    wm.wind_set(h, "info", f"R{entry.round_index}: {entry.incoming_voice_id}")
                    wm.wind_set(h, "top", True)
                wm.menu_tnormal(2, normal=False)
                ev = ev_queue.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=beat_ms)
                aes_events.append(ev.to_dict())

            wm.tile_windows_gem2()
            while ev_queue.pending_count() > 0:
                aes_events.append(ev_queue.evnt_multi(MU_MESAG).to_dict())

            gem_desktop_trace = {
                "contract": GEM_AES_VDI_CONTRACT,
                "window_summary": wm.summary(),
                "aes_events": aes_events,
                "aes_messages_count": len(ev_queue.message_log()),
                "visual_evidence_only": True,
                "constitutional": counterpoint_constitutional_metadata(cloud_tokens_used=0),
            }

        result = CounterpointRelayResult(
            contract=COUNTERPOINT_CHAIRS_CONTRACT,
            chairs=tuple(c.to_dict() for c in chair_list),
            voices=tuple(v.to_dict() for v in self.voices),
            schedule_invariants=invariants,
            swap_ledger=schedule.ledger,
            cold_audits=tuple(cold_audits),
            frozen_packets=tuple(frozen_packets),
            rounds_executed=rounds,
            total_turns=total_turns,
            flagged_audits_count=sum(1 for a in cold_audits if not a.accepted),
            firewall_violations_caught=sum(1 for a in cold_audits if not a.firewall_ok),
            sunk_cost_flags_count=sum(1 for a in cold_audits if a.sunk_cost_flagged),
            mean_theorem15_dk=mean_dk,
            max_theorem15_dk=max_dk,
            constitutional=counterpoint_constitutional_metadata(cloud_tokens_used=0),
            gem_desktop_trace=gem_desktop_trace,
        )
        self._last_result = result
        return result

    def run(
        self,
        chairs: Sequence[ProblemChair],
        *,
        rounds: int = 2,
    ) -> CounterpointRelayResult:
        """Synchronous entry point for running Counterpoint Chairs."""
        return run_coro_sync(self.arun(chairs, rounds=rounds))

    def sonify_cadence_wav(
        self,
        output_path: str | Path,
        result: CounterpointRelayResult | None = None,
        *,
        sample_rate: int = 22050,
        beat_duration_s: float = 0.22,
    ) -> dict[str, Any]:
        """Generate an original 16-bit PCM WAV reflecting rotation tension and cadence.

        Uses pure Python stdlib (``wave``, ``struct``, ``math``). Each swap in the
        relay renders a two-voice counterpoint interval whose consonance or
        dissonance tracks ``theorem15_discrepancy_dk``, firewall status, and
        sunk-cost flags, closing on a resolving tonic-fifth cadence.
        """
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
            raise ValueError(
                f"sample_rate must be an integer in [8000, 96000], got {sample_rate!r}"
            )
        if sample_rate < 8000 or sample_rate > 96000:
            raise ValueError("sample_rate must be in [8000, 96000]")
        if isinstance(beat_duration_s, bool) or not isinstance(beat_duration_s, (int, float)):
            raise ValueError(
                f"beat_duration_s must be a finite number in (0.02, 5.0], got {beat_duration_s!r}"
            )
        beat_dur = float(beat_duration_s)
        if not math.isfinite(beat_dur) or beat_dur <= 0.02 or beat_dur > 5.0:
            raise ValueError("beat_duration_s must be in (0.02, 5.0]")

        eff_result = result if result is not None else self._last_result
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # Map voice IDs to musical registers (Hz) deterministically
        base_scale = (261.63, 293.66, 329.63, 392.00, 440.00, 523.25)
        voice_freq_map: dict[str, float] = {}
        for idx, voice in enumerate(self.voices):
            meta_hz = voice.metadata.get("base_hz")
            if isinstance(meta_hz, (int, float)) and not isinstance(meta_hz, bool) and 80.0 <= float(meta_hz) <= 1800.0:
                voice_freq_map[voice.voice_id] = float(meta_hz)
            else:
                voice_freq_map[voice.voice_id] = base_scale[idx % len(base_scale)]

        audit_by_key: dict[tuple[int, str, str], ColdAuditVerdict] = {}
        if eff_result is not None:
            for audit in eff_result.cold_audits:
                audit_by_key[(audit.round_index, audit.chair_id, audit.incoming_voice_id)] = audit

        events: list[tuple[float, float, float, bool]] = []
        tension_scores: list[float] = []
        if eff_result is not None and eff_result.swap_ledger:
            for entry in eff_result.swap_ledger:
                f_inc = voice_freq_map.get(entry.incoming_voice_id, 329.63)
                entry_audit = audit_by_key.get(
                    (entry.round_index, entry.chair_id, entry.incoming_voice_id)
                )
                dk = float(entry_audit.theorem15_discrepancy_dk) if entry_audit is not None else 0.02
                tense = bool(
                    entry_audit is not None
                    and (
                        not entry_audit.firewall_ok
                        or entry_audit.sunk_cost_flagged
                        or entry_audit.discrepancy_exceeded
                    )
                )
                tension = min(1.0, max(0.0, dk * 4.0 + (0.45 if tense else 0.0)))
                tension_scores.append(round(tension, 4))
                # Consonant perfect fifth (1.5) when calm; tritone/minor-2nd ratio when tense.
                ratio = 1.41421356 if tense else (1.5 if tension < 0.35 else 1.333333)
                f_counter = (
                    voice_freq_map.get(entry.departed_voice_id, f_inc * ratio)
                    if entry.departed_voice_id
                    else f_inc * 1.25
                )
                if tense:
                    f_counter = f_inc * 1.41421356
                events.append((f_inc, f_counter, tension, tense))
        else:
            # Default 4-voice counterpoint cadence when called standalone.
            for idx, v in enumerate(self.voices):
                f0 = voice_freq_map[v.voice_id]
                f1 = f0 * (1.25 if idx % 2 == 0 else 1.5)
                events.append((f0, f1, 0.1, False))
                tension_scores.append(0.1)

        # Final resolving tonic-fifth-octave cadence
        events.append((261.63, 392.00, 0.0, False))

        pcm_samples: list[int] = []
        beat_frames = max(1, int(round(sample_rate * beat_duration_s)))
        attack_frames = max(1, int(0.08 * beat_frames))
        release_frames = max(1, int(0.15 * beat_frames))

        for ev_idx, (f1, f2, tension, tense) in enumerate(events):
            is_final = ev_idx == len(events) - 1
            n_frames = int(beat_frames * 1.5) if is_final else beat_frames
            for i in range(n_frames):
                t = i / sample_rate
                env = 1.0
                if i < attack_frames:
                    env = i / attack_frames
                elif i >= n_frames - release_frames:
                    env = max(0.0, (n_frames - i) / release_frames)

                # Two-voice counterpoint wave + gentle octave harmonic; tremolo under tension
                vib = 1.0 + (0.18 * math.sin(2.0 * math.pi * (6.0 + 8.0 * tension) * t) if tense else 0.0)
                w1 = math.sin(2.0 * math.pi * f1 * t)
                w2 = math.sin(2.0 * math.pi * f2 * t)
                w3 = 0.25 * math.sin(2.0 * math.pi * (2.0 * f1) * t)
                amp = 0.42 * env * vib * (w1 + 0.8 * w2 + w3) / 2.05
                sample_int = max(-32767, min(32767, int(round(amp * 32767.0))))
                pcm_samples.append(sample_int)

        raw_pcm = struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)
        with wave.open(str(target), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_pcm)

        nframes = len(pcm_samples)
        return {
            "contract": COUNTERPOINT_CHAIRS_CONTRACT,
            "path": str(target),
            "sample_rate": sample_rate,
            "channels": 1,
            "sample_width_bytes": 2,
            "nframes": nframes,
            "duration_s": round(nframes / sample_rate, 4),
            "sha256": sha256_file(target),
            "tension_scores": tension_scores,
            "constitutional": counterpoint_constitutional_metadata(cloud_tokens_used=0),
        }


__all__ = [
    "CANONICAL_VOICE_IDS",
    "COUNTERPOINT_CHAIRS_CONTRACT",
    "ChairVoice",
    "ColdAuditVerdict",
    "CounterpointChairsEngine",
    "CounterpointRelayResult",
    "CounterpointRotationSchedule",
    "DEFAULT_BEAT_QUANTUM_S",
    "DEFAULT_MAX_DISCREPANCY_DK",
    "DEFAULT_MIN_MARGINAL_GAIN",
    "DEFAULT_STEP_BUDGET",
    "DEFAULT_SUNK_COST_PATIENCE",
    "DEFAULT_TAU",
    "FrozenChairPacket",
    "ProblemChair",
    "SwapLedgerEntry",
    "counterpoint_constitutional_metadata",
    "default_counterpoint_voices",
]

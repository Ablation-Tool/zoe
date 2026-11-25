"""Architecture 6: Shared Epistemic Blackboard enforcing CONSTITUTION.md Article III.

Maintains four strictly separated provenance-tracked lanes:

    measurement != evidence != belief update != action

1. Measurement lane (`MeasurementRecord`): raw observations identifying input,
   method, scope, and limitations (Article III.1).
2. Evidence lane (`EvidenceRecord`): explicit verifier promotion recording both
   passed verifications and negative results; sampled-only outcomes cannot become
   passed proof merely by matching an expectation without independent verifier
   rationale/evidence (Article II.4, Article III.2-3).
3. Belief-update lane (`BeliefUpdateRecord`): posterior/claim revisions gated
   strictly on approved, passing `EvidenceRecord` IDs; optionally synchronized to
   `ZoeUnifiedMemory.record_fact(..., evidence_approved=True)`.
4. Action-proposal lane (`ActionProposalRecord`): review-required proposals
   gated on valid `BeliefUpdateRecord` IDs, always keeping
   `status="REVIEW_REQUIRED"`, `external_actions=0`, and
   `autonomous_execution_allowed=False` (Article III.4, Article X).

All mutations are linked by a canonical SHA-256 hash chain providing tamper
evidence only — explicitly not cryptographic authentication or identity proof
(Article III.5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
import re
import threading
from typing import Any, Literal

from .._utils import atomic_write_json, sha256_bytes, sha256_json_utf8
from ..actuation import timestamp
from ..l5_memory import ZoeUnifiedMemory
from ..metacognition import EvidenceSource, Provenance, STRONG_SOURCE_KINDS
from .sdk_bridge import ATTRIBUTION_TEXT, bridge_constitutional_metadata

BLACKBOARD_CONTRACT = "zoe-epistemic-blackboard/v1"
HASH_CHAIN_SEMANTICS = "tamper_evidence_only_not_authentication_or_identity_proof"

_EXPECTATION_ONLY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bmatch(?:es|ed|ing)?\s+(?:the\s+)?expectation\b", re.IGNORECASE),
    re.compile(r"\bexpectation\s+match(?:ed|es|ing)?\b", re.IGNORECASE),
    re.compile(r"\bas\s+expected\b", re.IGNORECASE),
    re.compile(
        r"\blooks?\s+(?:good|right|correct|reasonable|plausible|fine|ok|okay|acceptable)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsample\s+match(?:ed|es)?\b", re.IGNORECASE),
)

_INDEPENDENT_PROOF_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:exhaustive|formal|symbolic|deterministic|independent|z3|sympy|lean|ast|theorem|proof)\b", re.IGNORECASE),
)


class FirewallViolationError(Exception):
    """Raised when an operation violates CONSTITUTION.md Article III firewall rules."""


class TamperDetectedError(ValueError):
    """Raised when SHA-256 hash-chain or document tamper evidence triggers."""


def _require_nonempty_str(value: Any, label: str, *, max_len: int = 4096) -> str:
    if not isinstance(value, str):
        raise FirewallViolationError(f"{label} must be a non-empty string")
    cleaned = value.strip()
    if not cleaned:
        raise FirewallViolationError(f"{label} must be non-empty (CONSTITUTION.md Art. III)")
    if len(cleaned) > max_len:
        raise FirewallViolationError(f"{label} exceeds maximum length {max_len}")
    return cleaned


def _normalize_json_value(value: Any, *, label: str = "value") -> Any:
    """Convert value to canonical finite JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FirewallViolationError(f"{label} must be finite (NaN/Infinity rejected)")
        return value
    if isinstance(value, (EvidenceSource, Provenance)):
        return _normalize_json_value(value.document(), label=label)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _normalize_json_value(value.to_dict(), label=label)
    if hasattr(value, "document") and callable(value.document):
        return _normalize_json_value(value.document(), label=label)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise FirewallViolationError(f"{label} mapping keys must be strings")
            out[k] = _normalize_json_value(v, label=f"{label}.{k}")
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item, label=f"{label}[]") for item in value]
    raise FirewallViolationError(
        f"{label} contains non-JSON-serializable type {type(value).__name__}"
    )


def _normalize_limitations(value: Any) -> str:
    if isinstance(value, str):
        return _require_nonempty_str(value, "limitations", max_len=2048)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if not parts:
            raise FirewallViolationError(
                "limitations must be non-empty (CONSTITUTION.md Art. III.1)"
            )
        return _require_nonempty_str("; ".join(parts), "limitations", max_len=2048)
    raise FirewallViolationError(
        "limitations must be a non-empty string or sequence of strings"
    )


def coerce_evidence_source(
    source: Any,
    *,
    default_identifier: str = "blackboard_source",
) -> EvidenceSource:
    """Convert an ``EvidenceSource``, peer vector (``.to_evidence_source()``), or mapping."""
    if isinstance(source, EvidenceSource):
        return source
    if hasattr(source, "to_evidence_source") and callable(source.to_evidence_source):
        converted = source.to_evidence_source()
        if isinstance(converted, EvidenceSource):
            return converted
    if isinstance(source, Mapping):
        kind = str(source.get("kind", "tool")).strip() or "tool"
        ident = str(source.get("identifier", default_identifier)).strip() or default_identifier
        trust = float(source.get("trust", 0.75))
        strength = float(source.get("strength", 0.75))
        return EvidenceSource(kind=kind, identifier=ident, trust=trust, strength=strength)
    raise FirewallViolationError(
        f"cannot coerce {type(source).__name__} into EvidenceSource"
    )


def _normalize_provenance(
    provenance: Any,
    *,
    source_agent: str,
    method: str,
    sampled_only: bool,
) -> dict[str, Any]:
    if provenance is None:
        src = EvidenceSource(
            kind="prior" if sampled_only else "sensor",
            identifier=f"{source_agent}:{method}",
            trust=0.45 if sampled_only else 0.75,
            strength=0.45 if sampled_only else 0.75,
        )
        doc = Provenance(
            sources=(src,),
            transformations=(f"post_measurement:{method}",),
        ).document()
        doc["sampled_only"] = sampled_only
        return doc
    if isinstance(provenance, Provenance):
        doc = provenance.document()
        doc["sampled_only"] = sampled_only
        return doc
    if hasattr(provenance, "to_evidence_source") and callable(provenance.to_evidence_source):
        provenance = coerce_evidence_source(
            provenance, default_identifier=f"{source_agent}:{method}"
        )
    if isinstance(provenance, EvidenceSource):
        doc = Provenance(
            sources=(provenance,),
            transformations=(f"post_measurement:{method}",),
        ).document()
        doc["sampled_only"] = sampled_only
        return doc
    if isinstance(provenance, Mapping):
        normalized = _normalize_json_value(dict(provenance), label="provenance")
        if not isinstance(normalized, dict) or not normalized:
            raise FirewallViolationError("provenance mapping must be non-empty")
        normalized.setdefault("sampled_only", sampled_only)
        return normalized
    raise FirewallViolationError(
        f"provenance must be Provenance, EvidenceSource, Mapping, or None; got {type(provenance).__name__}"
    )


def _evidence_source_summary(
    evidence_source: Any,
) -> tuple[dict[str, Any] | None, bool]:
    """Return (serialized_source, is_strong) for an optional evidence source."""
    if evidence_source is None:
        return None, False
    if hasattr(evidence_source, "to_evidence_source") and callable(
        evidence_source.to_evidence_source
    ):
        evidence_source = coerce_evidence_source(evidence_source)
    if isinstance(evidence_source, EvidenceSource):
        return evidence_source.document(), bool(evidence_source.strong)
    if isinstance(evidence_source, Mapping):
        doc = _normalize_json_value(dict(evidence_source), label="evidence_source")
        if not isinstance(doc, dict) or not doc:
            raise FirewallViolationError("evidence_source mapping must be non-empty")
        kind = str(doc.get("kind", ""))
        trust = doc.get("trust", 0.0)
        strength = doc.get("strength", 0.0)
        computed_strong = (
            kind in STRONG_SOURCE_KINDS
            and isinstance(trust, (int, float))
            and not isinstance(trust, bool)
            and math.isfinite(float(trust))
            and isinstance(strength, (int, float))
            and not isinstance(strength, bool)
            and math.isfinite(float(strength))
            and float(trust) >= 0.6
            and float(strength) >= 0.6
        )
        if "strong_evidence" in doc and isinstance(doc["strong_evidence"], bool):
            is_strong = bool(doc["strong_evidence"]) and computed_strong
        else:
            is_strong = computed_strong
        return doc, is_strong
    raise FirewallViolationError(
        "evidence_source must be EvidenceSource, Mapping, or None; "
        f"got {type(evidence_source).__name__}"
    )


def _is_expectation_only_rationale(rationale: str) -> bool:
    """Detect naive expectation-match-only rationale lacking independent verification."""
    matches_expectation = any(pat.search(rationale) for pat in _EXPECTATION_ONLY_PATTERNS)
    has_independent_cue = any(pat.search(rationale) for pat in _INDEPENDENT_PROOF_PATTERNS)
    return matches_expectation and not has_independent_cue


def _compute_entry_sha256(
    *,
    seq: int,
    lane: str,
    prev_hash: str,
    payload: Mapping[str, Any],
) -> str:
    return sha256_json_utf8(
        {
            "seq": seq,
            "lane": lane,
            "prev_hash": prev_hash,
            "payload": dict(payload),
        }
    )


@dataclass(frozen=True)
class MeasurementRecord:
    """Lane 1 record: raw measurement identifying input, method, scope, and limitations."""

    record_id: str
    seq: int
    source_agent: str
    input_desc: str
    method: str
    scope: str
    limitations: str
    value: Any
    sampled_only: bool
    provenance: dict[str, Any]
    created_utc: str
    prev_hash: str
    entry_sha256: str
    lane: Literal["measurement"] = "measurement"

    @property
    def id(self) -> str:
        return self.record_id

    @property
    def measurement_id(self) -> str:
        return self.record_id

    def payload_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "seq": self.seq,
            "lane": self.lane,
            "source_agent": self.source_agent,
            "input_desc": self.input_desc,
            "method": self.method,
            "scope": self.scope,
            "limitations": self.limitations,
            "value": deepcopy(self.value),
            "sampled_only": self.sampled_only,
            "provenance": deepcopy(self.provenance),
            "created_utc": self.created_utc,
            "prev_hash": self.prev_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        doc = self.payload_dict()
        doc["entry_sha256"] = self.entry_sha256
        return doc


@dataclass(frozen=True)
class EvidenceRecord:
    """Lane 2 record: explicit verifier promotion (passing or negative result)."""

    record_id: str
    seq: int
    measurement_id: str
    verifier_name: str
    passed: bool
    approved: bool
    rationale: str
    sampled_source: bool
    evidence_source: dict[str, Any] | None
    negative_result: bool
    created_utc: str
    prev_hash: str
    entry_sha256: str
    lane: Literal["evidence"] = "evidence"

    @property
    def id(self) -> str:
        return self.record_id

    @property
    def evidence_id(self) -> str:
        return self.record_id

    def payload_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "seq": self.seq,
            "lane": self.lane,
            "measurement_id": self.measurement_id,
            "verifier_name": self.verifier_name,
            "passed": self.passed,
            "approved": self.approved,
            "rationale": self.rationale,
            "sampled_source": self.sampled_source,
            "evidence_source": deepcopy(self.evidence_source),
            "negative_result": self.negative_result,
            "created_utc": self.created_utc,
            "prev_hash": self.prev_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        doc = self.payload_dict()
        doc["entry_sha256"] = self.entry_sha256
        return doc


@dataclass(frozen=True)
class BeliefUpdateRecord:
    """Lane 3 record: evidence-gated claim or posterior revision."""

    record_id: str
    seq: int
    evidence_ids: tuple[str, ...]
    claim: str
    posterior_delta: float
    subject: str
    relation: str
    confidence: float
    superseded_belief_ids: tuple[str, ...]
    memory_sync: dict[str, Any] | None
    created_utc: str
    prev_hash: str
    entry_sha256: str
    lane: Literal["belief_update"] = "belief_update"

    @property
    def id(self) -> str:
        return self.record_id

    @property
    def belief_id(self) -> str:
        return self.record_id

    def payload_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "seq": self.seq,
            "lane": self.lane,
            "evidence_ids": list(self.evidence_ids),
            "claim": self.claim,
            "posterior_delta": self.posterior_delta,
            "subject": self.subject,
            "relation": self.relation,
            "confidence": self.confidence,
            "superseded_belief_ids": list(self.superseded_belief_ids),
            "memory_sync": deepcopy(self.memory_sync),
            "created_utc": self.created_utc,
            "prev_hash": self.prev_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        doc = self.payload_dict()
        doc["entry_sha256"] = self.entry_sha256
        return doc


@dataclass(frozen=True)
class ActionProposalRecord:
    """Lane 4 record: review-required action proposal with zero external execution."""

    record_id: str
    seq: int
    belief_id: str
    action_kind: str
    target: str
    reversible: bool
    status: Literal["REVIEW_REQUIRED"]
    external_actions: int
    requires_human_review: bool
    autonomous_execution_allowed: bool
    rationale: str
    created_utc: str
    prev_hash: str
    entry_sha256: str
    lane: Literal["action_proposal"] = "action_proposal"

    @property
    def id(self) -> str:
        return self.record_id

    @property
    def action_id(self) -> str:
        return self.record_id

    def payload_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "seq": self.seq,
            "lane": self.lane,
            "belief_id": self.belief_id,
            "action_kind": self.action_kind,
            "target": self.target,
            "reversible": self.reversible,
            "status": self.status,
            "external_actions": self.external_actions,
            "requires_human_review": self.requires_human_review,
            "autonomous_execution_allowed": self.autonomous_execution_allowed,
            "rationale": self.rationale,
            "created_utc": self.created_utc,
            "prev_hash": self.prev_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        doc = self.payload_dict()
        doc["entry_sha256"] = self.entry_sha256
        return doc


AnyBlackboardRecord = (
    MeasurementRecord | EvidenceRecord | BeliefUpdateRecord | ActionProposalRecord
)


def _measurement_from_dict(raw: Mapping[str, Any]) -> MeasurementRecord:
    if not isinstance(raw.get("sampled_only"), bool):
        raise FirewallViolationError("CONSTITUTION.md Art. III.1: sampled_only must be a boolean")
    if not isinstance(raw.get("provenance"), Mapping):
        raise TamperDetectedError("measurement provenance must be a mapping")
    return MeasurementRecord(
        record_id=_require_nonempty_str(raw["record_id"], "measurement.record_id", max_len=128),
        seq=int(raw["seq"]),
        source_agent=_require_nonempty_str(raw["source_agent"], "measurement.source_agent", max_len=512),
        input_desc=_require_nonempty_str(raw["input_desc"], "measurement.input_desc", max_len=2048),
        method=_require_nonempty_str(raw["method"], "measurement.method", max_len=512),
        scope=_require_nonempty_str(raw["scope"], "measurement.scope", max_len=1024),
        limitations=_require_nonempty_str(raw["limitations"], "measurement.limitations", max_len=2048),
        value=_normalize_json_value(deepcopy(raw["value"]), label="measurement.value"),
        sampled_only=bool(raw["sampled_only"]),
        provenance=deepcopy(dict(raw["provenance"])),
        created_utc=str(raw["created_utc"]),
        prev_hash=str(raw["prev_hash"]),
        entry_sha256=str(raw["entry_sha256"]),
    )


def _evidence_from_dict(raw: Mapping[str, Any]) -> EvidenceRecord:
    for bfield in ("passed", "approved", "sampled_source", "negative_result"):
        if not isinstance(raw.get(bfield), bool):
            raise FirewallViolationError(
                f"CONSTITUTION.md Art. III.2: evidence {bfield} must be a boolean, got {raw.get(bfield)!r}"
            )
    ev_src = raw.get("evidence_source")
    if ev_src is not None and not isinstance(ev_src, Mapping):
        raise FirewallViolationError("CONSTITUTION.md Art. III.2: evidence_source must be a mapping or None")
    return EvidenceRecord(
        record_id=_require_nonempty_str(raw["record_id"], "evidence.record_id", max_len=128),
        seq=int(raw["seq"]),
        measurement_id=_require_nonempty_str(raw["measurement_id"], "evidence.measurement_id", max_len=128),
        verifier_name=_require_nonempty_str(raw["verifier_name"], "evidence.verifier_name", max_len=512),
        passed=bool(raw["passed"]),
        approved=bool(raw["approved"]),
        rationale=_require_nonempty_str(raw["rationale"], "evidence.rationale", max_len=4096),
        sampled_source=bool(raw["sampled_source"]),
        evidence_source=deepcopy(dict(ev_src)) if isinstance(ev_src, Mapping) else None,
        negative_result=bool(raw["negative_result"]),
        created_utc=str(raw["created_utc"]),
        prev_hash=str(raw["prev_hash"]),
        entry_sha256=str(raw["entry_sha256"]),
    )


def _belief_from_dict(raw: Mapping[str, Any]) -> BeliefUpdateRecord:
    mem_sync = raw.get("memory_sync")
    raw_eids = raw.get("evidence_ids")
    if (
        isinstance(raw_eids, (str, bytes, bytearray))
        or not isinstance(raw_eids, Sequence)
        or len(raw_eids) == 0
    ):
        raise FirewallViolationError(
            "CONSTITUTION.md Art. III.2: belief update requires at least one approved EvidenceRecord ID"
        )
    evidence_ids = tuple(
        _require_nonempty_str(x, "belief.evidence_id", max_len=128) for x in raw_eids
    )
    raw_delta = raw["posterior_delta"]
    raw_conf = raw["confidence"]
    if (
        isinstance(raw_delta, bool)
        or not isinstance(raw_delta, (int, float))
        or not math.isfinite(float(raw_delta))
    ):
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.2: invalid persisted posterior_delta {raw_delta!r}"
        )
    if (
        isinstance(raw_conf, bool)
        or not isinstance(raw_conf, (int, float))
        or not math.isfinite(float(raw_conf))
    ):
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.2: invalid persisted confidence {raw_conf!r}"
        )
    return BeliefUpdateRecord(
        record_id=_require_nonempty_str(raw["record_id"], "belief.record_id", max_len=128),
        seq=int(raw["seq"]),
        evidence_ids=evidence_ids,
        claim=_require_nonempty_str(raw["claim"], "belief.claim", max_len=4096),
        posterior_delta=float(raw_delta),
        subject=_require_nonempty_str(raw["subject"], "belief.subject", max_len=512),
        relation=_require_nonempty_str(raw["relation"], "belief.relation", max_len=256),
        confidence=float(raw_conf),
        superseded_belief_ids=tuple(str(x) for x in raw.get("superseded_belief_ids", ())),
        memory_sync=deepcopy(dict(mem_sync)) if isinstance(mem_sync, Mapping) else None,
        created_utc=str(raw["created_utc"]),
        prev_hash=str(raw["prev_hash"]),
        entry_sha256=str(raw["entry_sha256"]),
    )


def _action_from_dict(raw: Mapping[str, Any]) -> ActionProposalRecord:
    status = str(raw["status"])
    if status != "REVIEW_REQUIRED":
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.4: invalid action proposal status {status!r}"
        )
    raw_ext = raw["external_actions"]
    if isinstance(raw_ext, bool) or not isinstance(raw_ext, int) or raw_ext != 0:
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.4/X: action proposal external_actions must be 0, got {raw_ext!r}"
        )
    raw_review = raw["requires_human_review"]
    if raw_review is not True:
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.4: action proposal requires_human_review must be True, got {raw_review!r}"
        )
    raw_auto = raw["autonomous_execution_allowed"]
    if raw_auto is not False:
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.4/X: action proposal autonomous_execution_allowed must be False, got {raw_auto!r}"
        )
    if not isinstance(raw.get("reversible"), bool):
        raise FirewallViolationError(
            f"CONSTITUTION.md Art. III.4: action proposal reversible must be a boolean, got {raw.get('reversible')!r}"
        )
    return ActionProposalRecord(
        record_id=_require_nonempty_str(raw["record_id"], "action.record_id", max_len=128),
        seq=int(raw["seq"]),
        belief_id=_require_nonempty_str(raw["belief_id"], "action.belief_id", max_len=128),
        action_kind=_require_nonempty_str(raw["action_kind"], "action.action_kind", max_len=512),
        target=_require_nonempty_str(raw["target"], "action.target", max_len=1024),
        reversible=bool(raw["reversible"]),
        status="REVIEW_REQUIRED",
        external_actions=0,
        requires_human_review=True,
        autonomous_execution_allowed=False,
        rationale=str(raw.get("rationale", "")),
        created_utc=str(raw["created_utc"]),
        prev_hash=str(raw["prev_hash"]),
        entry_sha256=str(raw["entry_sha256"]),
    )


class EpistemicBlackboard:
    """4-lane provenance-tracked shared epistemic blackboard.

    Enforces ``CONSTITUTION.md`` Article III (epistemic firewall) and
    Article X (non-autonomous, non-sentient, zero external actions, Nicholas
    Michael Kloster credit).
    """

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        memory: ZoeUnifiedMemory | None = None,
    ) -> None:
        if root is not None:
            resolved = Path(root).expanduser().resolve()
            if resolved.suffix == ".json":
                self.path: Path | None = resolved
                self.root: Path | None = resolved.parent
            else:
                self.root = resolved
                self.path = resolved / "zoe_epistemic_blackboard.json"
        else:
            self.root = None
            self.path = None

        self._lock = threading.RLock()
        self._memory = memory
        self._stopped = False
        self._measurements: dict[str, MeasurementRecord] = {}
        self._evidence: dict[str, EvidenceRecord] = {}
        self._beliefs: dict[str, BeliefUpdateRecord] = {}
        self._actions: dict[str, ActionProposalRecord] = {}
        self._doc: dict[str, Any] = self._empty_doc()

        if self.path is not None and self.path.is_file():
            self.load()

    def __getstate__(self) -> dict[str, Any]:
        with self._lock:
            state = self.__dict__.copy()
        state.pop("_lock", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()

    @classmethod
    def _empty_doc(cls) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "contract": BLACKBOARD_CONTRACT,
            "schema_version": 1,
            "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
            "tamper_evidence_only": True,
            "authentication_proof": False,
            "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
            "stopped": False,
            "stop_reason": None,
            "measurements": [],
            "evidence": [],
            "belief_updates": [],
            "action_proposals": [],
            "ledger": [],
            "chain_head": "GENESIS",
        }
        doc["blackboard_sha256"] = sha256_json_utf8(
            {k: v for k, v in doc.items() if k != "blackboard_sha256"}
        )
        return doc

    @property
    def stopped(self) -> bool:
        with self._lock:
            return bool(self._stopped or self._doc.get("stopped", False))

    @property
    def chain_head(self) -> str:
        with self._lock:
            return str(self._doc["chain_head"])

    @property
    def memory(self) -> ZoeUnifiedMemory | None:
        return self._memory

    @staticmethod
    def constitutional_metadata() -> dict[str, Any]:
        meta = bridge_constitutional_metadata(cloud_tokens_used=0)
        meta["attribution"] = ATTRIBUTION_TEXT
        meta["hash_chain_semantics"] = HASH_CHAIN_SEMANTICS
        return meta

    def _require_not_stopped(self) -> None:
        if self.stopped:
            reason = self._doc.get("stop_reason") or "Emergency stop active"
            raise RuntimeError(f"EpistemicBlackboard is stopped ({reason}); writes blocked")

    def _save_if_persistent(self) -> None:
        if self.path is not None:
            atomic_write_json(self.path, self._doc)

    def _commit_record(self, lane_key: str, record: AnyBlackboardRecord) -> None:
        rec_dict = record.to_dict()
        self._doc[lane_key].append(rec_dict)
        self._doc["ledger"].append(
            {
                "seq": record.seq,
                "lane": record.lane,
                "record_id": record.record_id,
                "prev_hash": record.prev_hash,
                "entry_sha256": record.entry_sha256,
            }
        )
        self._doc["chain_head"] = record.entry_sha256
        self._doc["blackboard_sha256"] = sha256_json_utf8(
            {k: v for k, v in self._doc.items() if k != "blackboard_sha256"}
        )
        self._save_if_persistent()

    def _rebuild_indices_from_doc(self, doc: Mapping[str, Any]) -> None:
        measurements: dict[str, MeasurementRecord] = {}
        evidence: dict[str, EvidenceRecord] = {}
        beliefs: dict[str, BeliefUpdateRecord] = {}
        actions: dict[str, ActionProposalRecord] = {}
        for raw in doc["measurements"]:
            rec_m = _measurement_from_dict(raw)
            measurements[rec_m.record_id] = rec_m
        for raw in doc["evidence"]:
            rec_e = _evidence_from_dict(raw)
            evidence[rec_e.record_id] = rec_e
        for raw in doc["belief_updates"]:
            rec_b = _belief_from_dict(raw)
            beliefs[rec_b.record_id] = rec_b
        for raw in doc["action_proposals"]:
            rec_a = _action_from_dict(raw)
            actions[rec_a.record_id] = rec_a
        self._measurements = measurements
        self._evidence = evidence
        self._beliefs = beliefs
        self._actions = actions

    @classmethod
    def _validate_document_integrity(
        cls,
        doc: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(doc, Mapping) or doc.get("contract") != BLACKBOARD_CONTRACT:
            raise TamperDetectedError("invalid EpistemicBlackboard contract")
        required_keys = (
            "constitutional",
            "measurements",
            "evidence",
            "belief_updates",
            "action_proposals",
            "ledger",
            "chain_head",
            "blackboard_sha256",
        )
        for key in required_keys:
            if key not in doc:
                raise TamperDetectedError(f"missing required blackboard field: {key}")

        expected_doc_hash = sha256_json_utf8(
            {k: v for k, v in doc.items() if k != "blackboard_sha256"}
        )
        if doc.get("blackboard_sha256") != expected_doc_hash:
            raise TamperDetectedError(
                "EpistemicBlackboard SHA-256 document tamper detected "
                "(tamper evidence only, not authentication proof)"
            )

        const = doc.get("constitutional")
        if not isinstance(const, Mapping):
            raise TamperDetectedError("constitutional metadata must be a mapping")
        ext_actions = const.get("external_actions")
        if isinstance(ext_actions, bool) or not isinstance(ext_actions, int) or ext_actions != 0:
            raise FirewallViolationError(
                f"CONSTITUTION.md Art. X: constitutional external_actions must be 0, got {ext_actions!r}"
            )
        for flag_name in ("sentience_claimed", "l5_agi_qualified", "zoe_clone_claimed"):
            if const.get(flag_name) is not False:
                raise FirewallViolationError(
                    f"CONSTITUTION.md Art. X: constitutional {flag_name} must be False, got {const.get(flag_name)!r}"
                )

        lane_records: dict[str, dict[str, Any]] = {}
        lane_sources = (
            ("measurement", doc["measurements"]),
            ("evidence", doc["evidence"]),
            ("belief_update", doc["belief_updates"]),
            ("action_proposal", doc["action_proposals"]),
        )
        for lane_name, rows in lane_sources:
            if not isinstance(rows, list):
                raise TamperDetectedError(f"lane {lane_name} must be a list")
            for row in rows:
                if not isinstance(row, Mapping):
                    raise TamperDetectedError(f"corrupt record in lane {lane_name}")
                rid = row.get("record_id")
                if not isinstance(rid, str) or rid in lane_records:
                    raise TamperDetectedError(f"duplicate or invalid record_id {rid!r}")
                if row.get("lane") != lane_name:
                    raise TamperDetectedError(f"record {rid!r} lane mismatch")
                lane_records[rid] = dict(row)

        ledger = doc["ledger"]
        if not isinstance(ledger, list) or len(ledger) != len(lane_records):
            raise TamperDetectedError("ledger length mismatch against lane records")

        prev_hash = "GENESIS"
        for idx, ledger_item in enumerate(ledger, start=1):
            if not isinstance(ledger_item, Mapping):
                raise TamperDetectedError(f"corrupt ledger item at seq {idx}")
            rid = ledger_item.get("record_id")
            if rid not in lane_records:
                raise TamperDetectedError(f"ledger references unknown record {rid!r}")
            rec = lane_records[rid]
            ledger_seq = ledger_item.get("seq")
            rec_seq = rec.get("seq")
            if (
                isinstance(ledger_seq, bool)
                or not isinstance(ledger_seq, int)
                or ledger_seq != idx
                or isinstance(rec_seq, bool)
                or not isinstance(rec_seq, int)
                or rec_seq != idx
            ):
                raise TamperDetectedError(f"sequence tampering detected at seq {idx}")
            if ledger_item.get("prev_hash") != prev_hash or rec.get("prev_hash") != prev_hash:
                raise TamperDetectedError(f"prev_hash chain break at seq {idx} ({rid})")
            payload = {k: v for k, v in rec.items() if k != "entry_sha256"}
            expected_entry_hash = _compute_entry_sha256(
                seq=idx,
                lane=str(rec["lane"]),
                prev_hash=prev_hash,
                payload=payload,
            )
            if (
                rec.get("entry_sha256") != expected_entry_hash
                or ledger_item.get("entry_sha256") != expected_entry_hash
            ):
                raise TamperDetectedError(
                    f"entry_sha256 tamper detected at seq {idx} ({rid})"
                )
            prev_hash = expected_entry_hash

        if doc.get("chain_head") != prev_hash:
            raise TamperDetectedError("chain_head mismatch against verified ledger tail")

        # Validate per-record schema and cross-lane causal provenance (Art. III).
        try:
            measurements_by_id: dict[str, MeasurementRecord] = {}
            for raw in doc["measurements"]:
                rec_m = _measurement_from_dict(raw)
                measurements_by_id[rec_m.record_id] = rec_m

            evidence_by_id: dict[str, EvidenceRecord] = {}
            for raw in doc["evidence"]:
                rec_e = _evidence_from_dict(raw)
                if rec_e.measurement_id not in measurements_by_id:
                    if any(
                        isinstance(r, Mapping) and r.get("record_id") == rec_e.measurement_id
                        for r in (*doc["evidence"], *doc["belief_updates"], *doc["action_proposals"])
                    ):
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III: evidence {rec_e.record_id!r} references "
                            f"non-measurement record {rec_e.measurement_id!r}"
                        )
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.2: evidence {rec_e.record_id!r} references "
                        f"unknown measurement_id {rec_e.measurement_id!r}"
                    )
                meas = measurements_by_id[rec_e.measurement_id]
                if meas.seq >= rec_e.seq:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.2: evidence {rec_e.record_id!r} (seq={rec_e.seq}) "
                        f"precedes referenced measurement {meas.record_id!r} (seq={meas.seq})"
                    )
                if rec_e.approved != rec_e.passed or rec_e.negative_result != (not rec_e.passed):
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.2: evidence {rec_e.record_id!r} has inconsistent "
                        f"passed={rec_e.passed}, approved={rec_e.approved}, negative_result={rec_e.negative_result}"
                    )
                if rec_e.sampled_source != meas.sampled_only:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.3: evidence {rec_e.record_id!r} sampled_source={rec_e.sampled_source} "
                        f"contradicts measurement {meas.record_id!r} sampled_only={meas.sampled_only}"
                    )
                if meas.sampled_only and (rec_e.passed or rec_e.approved):
                    src_doc, is_strong = _evidence_source_summary(rec_e.evidence_source)
                    if src_doc is None or not is_strong:
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III.3: sampled-only evidence {rec_e.record_id!r} "
                            "cannot be passed/approved without an explicit strong evidence_source"
                        )
                    if _is_expectation_only_rationale(rec_e.rationale) or len(rec_e.rationale.strip()) < 8:
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III.3: sampled-only evidence {rec_e.record_id!r} "
                            "lacks independent verifier rationale"
                        )
                evidence_by_id[rec_e.record_id] = rec_e

            beliefs_by_id: dict[str, BeliefUpdateRecord] = {}
            for raw in doc["belief_updates"]:
                rec_b = _belief_from_dict(raw)
                for eid in rec_b.evidence_ids:
                    if eid not in evidence_by_id:
                        if eid in measurements_by_id:
                            raise FirewallViolationError(
                                f"CONSTITUTION.md Art. III: belief {rec_b.record_id!r} references "
                                f"raw measurement {eid!r}; promote to evidence first"
                            )
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III.2: belief {rec_b.record_id!r} references "
                            f"unknown evidence_id {eid!r}"
                        )
                    ev = evidence_by_id[eid]
                    if not ev.passed or not ev.approved:
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III.2-3: belief {rec_b.record_id!r} references "
                            f"unapproved/failed evidence {eid!r} (passed={ev.passed}, approved={ev.approved})"
                        )
                    if ev.seq >= rec_b.seq:
                        raise FirewallViolationError(
                            f"CONSTITUTION.md Art. III.2: belief {rec_b.record_id!r} (seq={rec_b.seq}) "
                            f"precedes referenced evidence {ev.record_id!r} (seq={ev.seq})"
                        )
                beliefs_by_id[rec_b.record_id] = rec_b

            for raw in doc["action_proposals"]:
                rec_a = _action_from_dict(raw)
                if rec_a.belief_id not in beliefs_by_id:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.4: action proposal {rec_a.record_id!r} references "
                        f"unknown belief_id {rec_a.belief_id!r}"
                    )
                bel = beliefs_by_id[rec_a.belief_id]
                if bel.seq >= rec_a.seq:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.4: action proposal {rec_a.record_id!r} (seq={rec_a.seq}) "
                        f"precedes referenced belief {bel.record_id!r} (seq={bel.seq})"
                    )
        except (TamperDetectedError, FirewallViolationError):
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise TamperDetectedError(f"corrupt blackboard record schema: {exc}") from exc

        return {
            "valid": True,
            "tamper_detected": False,
            "entries_verified": len(ledger),
            "chain_head": prev_hash,
            "blackboard_sha256": expected_doc_hash,
            "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
            "tamper_evidence_only": True,
            "authentication_proof": False,
        }

    def verify_integrity(self, *, raise_on_error: bool = True) -> dict[str, Any]:
        """Verify document SHA-256, per-entry hash chain, and in-memory index parity."""
        with self._lock:
            try:
                report = self._validate_document_integrity(self._doc)
                # Also verify in-memory index parity against _doc
                expected_counts = (
                    (len(self._measurements), len(self._doc["measurements"]), "measurements"),
                    (len(self._evidence), len(self._doc["evidence"]), "evidence"),
                    (len(self._beliefs), len(self._doc["belief_updates"]), "belief_updates"),
                    (len(self._actions), len(self._doc["action_proposals"]), "action_proposals"),
                )
                for idx_len, doc_len, label in expected_counts:
                    if idx_len != doc_len:
                        raise TamperDetectedError(
                            f"in-memory index divergence in {label}: {idx_len} != {doc_len}"
                        )
                for rid, rec in self._measurements.items():
                    match = next(
                        (r for r in self._doc["measurements"] if r["record_id"] == rid), None
                    )
                    if match != rec.to_dict():
                        raise TamperDetectedError(f"in-memory measurement divergence for {rid}")
                for rid, rec_e in self._evidence.items():
                    match = next((r for r in self._doc["evidence"] if r["record_id"] == rid), None)
                    if match != rec_e.to_dict():
                        raise TamperDetectedError(f"in-memory evidence divergence for {rid}")
                for rid, rec_b in self._beliefs.items():
                    match = next(
                        (r for r in self._doc["belief_updates"] if r["record_id"] == rid), None
                    )
                    if match != rec_b.to_dict():
                        raise TamperDetectedError(f"in-memory belief divergence for {rid}")
                for rid, rec_a in self._actions.items():
                    match = next(
                        (r for r in self._doc["action_proposals"] if r["record_id"] == rid), None
                    )
                    if match != rec_a.to_dict():
                        raise TamperDetectedError(f"in-memory action divergence for {rid}")
                return report
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, TamperDetectedError):
                    err: TamperDetectedError | FirewallViolationError = exc
                else:
                    err = TamperDetectedError(f"corrupt blackboard document schema: {exc}")
                if raise_on_error:
                    raise err from exc
                return {
                    "valid": False,
                    "tamper_detected": True,
                    "firewall_violation": False,
                    "error": str(err),
                    "chain_head": self._doc.get("chain_head") if isinstance(self._doc, Mapping) else None,
                    "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
                    "tamper_evidence_only": True,
                    "authentication_proof": False,
                }
            except FirewallViolationError as exc:
                if raise_on_error:
                    raise
                return {
                    "valid": False,
                    "tamper_detected": False,
                    "firewall_violation": True,
                    "error": str(exc),
                    "chain_head": self._doc.get("chain_head") if isinstance(self._doc, Mapping) else None,
                    "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
                    "tamper_evidence_only": True,
                    "authentication_proof": False,
                }

    def verify_chain(self, *, raise_on_error: bool = True) -> dict[str, Any]:
        """Alias for ``verify_integrity``."""
        return self.verify_integrity(raise_on_error=raise_on_error)

    def verify_hash_chain(self, *, raise_on_error: bool = False) -> dict[str, Any]:
        """Verify SHA-256 hash chain; returns structured status by default."""
        return self.verify_integrity(raise_on_error=raise_on_error)

    def load(self) -> dict[str, Any]:
        with self._lock:
            if self.path is None or not self.path.is_file():
                raise FileNotFoundError("no persisted EpistemicBlackboard file exists")
            import json

            raw_doc = json.loads(self.path.read_text(encoding="utf-8"))
            self._validate_document_integrity(raw_doc)
            self._rebuild_indices_from_doc(raw_doc)
            self._doc = raw_doc
            self._stopped = bool(raw_doc.get("stopped", False))
            return deepcopy(self._doc)

    # ------------------------------------------------------------------
    # Lane 1: Measurement
    # ------------------------------------------------------------------
    def post_measurement(
        self,
        source_agent: str = "",
        input_desc: str = "",
        method: str = "",
        scope: str = "",
        limitations: str | Sequence[str] = "",
        value: Any = None,
        sampled_only: bool = False,
        provenance: Provenance | EvidenceSource | Mapping[str, Any] | None = None,
        *,
        source: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> MeasurementRecord:
        """Record a raw measurement identifying input, method, scope, and limitations."""
        with self._lock:
            self._require_not_stopped()
            self.verify_integrity(raise_on_error=True)

            eff_agent_raw = source_agent if (isinstance(source_agent, str) and source_agent.strip()) else (source or "")
            clean_agent = _require_nonempty_str(eff_agent_raw, "source_agent", max_len=512)
            clean_input = _require_nonempty_str(input_desc, "input_desc", max_len=2048)
            clean_method = _require_nonempty_str(method, "method", max_len=512)
            clean_scope = _require_nonempty_str(scope, "scope", max_len=1024)
            clean_limitations = _normalize_limitations(limitations)
            if not isinstance(sampled_only, bool):
                raise FirewallViolationError("sampled_only must be a boolean")

            norm_value = _normalize_json_value(value, label="measurement.value")
            norm_prov = _normalize_provenance(
                provenance,
                source_agent=clean_agent,
                method=clean_method,
                sampled_only=sampled_only,
            )
            if metadata is not None:
                if not isinstance(metadata, Mapping):
                    raise FirewallViolationError("metadata must be a mapping when provided")
                norm_prov["metadata"] = _normalize_json_value(dict(metadata), label="measurement.metadata")

            idx = len(self._measurements) + 1
            seq = len(self._doc["ledger"]) + 1
            record_id = f"meas_{idx:04d}"
            created = timestamp()
            prev_hash = str(self._doc["chain_head"])

            temp = MeasurementRecord(
                record_id=record_id,
                seq=seq,
                source_agent=clean_agent,
                input_desc=clean_input,
                method=clean_method,
                scope=clean_scope,
                limitations=clean_limitations,
                value=norm_value,
                sampled_only=sampled_only,
                provenance=norm_prov,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256="",
            )
            entry_sha = _compute_entry_sha256(
                seq=seq,
                lane="measurement",
                prev_hash=prev_hash,
                payload=temp.payload_dict(),
            )
            record = MeasurementRecord(
                record_id=record_id,
                seq=seq,
                source_agent=clean_agent,
                input_desc=clean_input,
                method=clean_method,
                scope=clean_scope,
                limitations=clean_limitations,
                value=norm_value,
                sampled_only=sampled_only,
                provenance=norm_prov,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256=entry_sha,
            )
            self._measurements[record_id] = record
            self._commit_record("measurements", record)
            return record

    # ------------------------------------------------------------------
    # Lane 2: Evidence
    # ------------------------------------------------------------------
    def promote_to_evidence(
        self,
        measurement_id: str,
        verifier_name: str,
        passed: bool,
        rationale: str,
        evidence_source: EvidenceSource | Mapping[str, Any] | None = None,
    ) -> EvidenceRecord:
        """Promote a measurement to an explicit evidence decision (passing or negative)."""
        with self._lock:
            self._require_not_stopped()
            self.verify_integrity(raise_on_error=True)

            mid = _require_nonempty_str(measurement_id, "measurement_id", max_len=128)
            if mid not in self._measurements:
                if mid in self._evidence or mid in self._beliefs or mid in self._actions:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: record {mid!r} is not a raw MeasurementRecord"
                    )
                raise FirewallViolationError(
                    f"Unknown measurement_id {mid!r}; cannot promote to evidence"
                )

            clean_verifier = _require_nonempty_str(verifier_name, "verifier_name", max_len=512)
            if not isinstance(passed, bool):
                raise FirewallViolationError("passed must be a boolean")
            clean_rationale = _require_nonempty_str(rationale, "rationale", max_len=4096)
            source_doc, is_strong_source = _evidence_source_summary(evidence_source)

            measurement = self._measurements[mid]
            if measurement.sampled_only and passed:
                if source_doc is None or not is_strong_source:
                    raise FirewallViolationError(
                        "CONSTITUTION.md Art. III.3: sampled-only measurement cannot be "
                        "promoted to passed evidence without an explicit strong evidence_source "
                        "(kind in STRONG_SOURCE_KINDS with trust >= 0.6 and strength >= 0.6)"
                    )
                if _is_expectation_only_rationale(clean_rationale) or len(clean_rationale) < 8:
                    raise FirewallViolationError(
                        "CONSTITUTION.md Art. III.3: sampled outcomes cannot become passed "
                        "proof merely by expectation match without independent verifier "
                        "rationale"
                    )

            approved = bool(passed)
            negative_result = not passed

            idx = len(self._evidence) + 1
            seq = len(self._doc["ledger"]) + 1
            record_id = f"ev_{idx:04d}"
            created = timestamp()
            prev_hash = str(self._doc["chain_head"])

            temp = EvidenceRecord(
                record_id=record_id,
                seq=seq,
                measurement_id=mid,
                verifier_name=clean_verifier,
                passed=passed,
                approved=approved,
                rationale=clean_rationale,
                sampled_source=measurement.sampled_only,
                evidence_source=source_doc,
                negative_result=negative_result,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256="",
            )
            entry_sha = _compute_entry_sha256(
                seq=seq,
                lane="evidence",
                prev_hash=prev_hash,
                payload=temp.payload_dict(),
            )
            record = EvidenceRecord(
                record_id=record_id,
                seq=seq,
                measurement_id=mid,
                verifier_name=clean_verifier,
                passed=passed,
                approved=approved,
                rationale=clean_rationale,
                sampled_source=measurement.sampled_only,
                evidence_source=source_doc,
                negative_result=negative_result,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256=entry_sha,
            )
            self._evidence[record_id] = record
            self._commit_record("evidence", record)
            return record

    # ------------------------------------------------------------------
    # Lane 3: Belief Update
    # ------------------------------------------------------------------
    def update_belief(
        self,
        evidence_ids: Sequence[str],
        claim: str,
        posterior_delta: float,
        *,
        subject: str | None = None,
        relation: str = "supported_claim",
        confidence: float | None = None,
    ) -> BeliefUpdateRecord:
        """Record an evidence-gated belief update, optionally syncing to ZoeUnifiedMemory."""
        with self._lock:
            self._require_not_stopped()
            self.verify_integrity(raise_on_error=True)

            if isinstance(evidence_ids, (str, bytes)) or not isinstance(evidence_ids, Sequence):
                raise FirewallViolationError(
                    "evidence_ids must be a non-empty sequence of EvidenceRecord IDs"
                )
            if not evidence_ids:
                raise FirewallViolationError(
                    "CONSTITUTION.md Art. III.2: belief update requires at least one approved EvidenceRecord ID"
                )

            clean_evidence_ids: list[str] = []
            for raw_eid in evidence_ids:
                eid = _require_nonempty_str(raw_eid, "evidence_id", max_len=128)
                if eid in self._measurements:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: raw measurement {eid!r} cannot directly "
                        "update belief; promote to evidence first"
                    )
                if eid in self._beliefs or eid in self._actions:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: record {eid!r} is not an EvidenceRecord"
                    )
                if eid not in self._evidence:
                    raise FirewallViolationError(
                        f"Unknown evidence_id {eid!r}; cannot update belief"
                    )
                ev = self._evidence[eid]
                if not ev.passed or not ev.approved:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III.2-3: evidence {eid!r} did not pass "
                        f"verification (passed={ev.passed}, sampled_source={ev.sampled_source}) "
                        "and cannot update belief"
                    )
                if eid not in clean_evidence_ids:
                    clean_evidence_ids.append(eid)

            clean_claim = _require_nonempty_str(claim, "claim", max_len=4096)
            if (
                isinstance(posterior_delta, bool)
                or not isinstance(posterior_delta, (int, float))
                or not math.isfinite(float(posterior_delta))
            ):
                raise FirewallViolationError("posterior_delta must be a finite number")
            delta = round(float(posterior_delta), 6)

            if subject is not None:
                eff_subject = _require_nonempty_str(subject, "subject", max_len=512)
            else:
                eff_subject = f"claim:{sha256_bytes(clean_claim.encode('utf-8'))[:12]}"
            eff_relation = _require_nonempty_str(relation, "relation", max_len=256)

            if confidence is not None:
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(float(confidence))
                ):
                    raise FirewallViolationError("confidence must be a finite number")
                eff_confidence = round(max(0.0, min(1.0, float(confidence))), 6)
            else:
                eff_confidence = round(max(0.0, min(1.0, 0.5 + delta)), 6)

            superseded = tuple(
                bid
                for bid, prior in self._beliefs.items()
                if prior.subject == eff_subject
                and prior.relation == eff_relation
                and prior.claim != clean_claim
            )

            mem_sync: dict[str, Any] | None = None
            if self._memory is not None:
                raw_sync = self._memory.record_fact(
                    eff_subject,
                    eff_relation,
                    clean_claim,
                    confidence=eff_confidence,
                    provenance=f"blackboard:{','.join(clean_evidence_ids)}",
                    evidence_approved=True,
                )
                mem_sync = _normalize_json_value(raw_sync, label="memory_sync")

            idx = len(self._beliefs) + 1
            seq = len(self._doc["ledger"]) + 1
            record_id = f"bel_{idx:04d}"
            created = timestamp()
            prev_hash = str(self._doc["chain_head"])

            temp = BeliefUpdateRecord(
                record_id=record_id,
                seq=seq,
                evidence_ids=tuple(clean_evidence_ids),
                claim=clean_claim,
                posterior_delta=delta,
                subject=eff_subject,
                relation=eff_relation,
                confidence=eff_confidence,
                superseded_belief_ids=superseded,
                memory_sync=mem_sync,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256="",
            )
            entry_sha = _compute_entry_sha256(
                seq=seq,
                lane="belief_update",
                prev_hash=prev_hash,
                payload=temp.payload_dict(),
            )
            record = BeliefUpdateRecord(
                record_id=record_id,
                seq=seq,
                evidence_ids=tuple(clean_evidence_ids),
                claim=clean_claim,
                posterior_delta=delta,
                subject=eff_subject,
                relation=eff_relation,
                confidence=eff_confidence,
                superseded_belief_ids=superseded,
                memory_sync=mem_sync,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256=entry_sha,
            )
            self._beliefs[record_id] = record
            self._commit_record("belief_updates", record)
            return record

    # ------------------------------------------------------------------
    # Lane 4: Action Proposal
    # ------------------------------------------------------------------
    def propose_action(
        self,
        belief_id: str,
        action_kind: str,
        target: str | bool = "unspecified",
        reversible: bool = True,
        *,
        rationale: str = "",
    ) -> ActionProposalRecord:
        """Propose a review-required action gated on a valid BeliefUpdateRecord.

        Always enforces ``status="REVIEW_REQUIRED"``, ``external_actions=0``,
        ``requires_human_review=True``, and ``autonomous_execution_allowed=False``.
        """
        with self._lock:
            self._require_not_stopped()
            self.verify_integrity(raise_on_error=True)

            bid = _require_nonempty_str(belief_id, "belief_id", max_len=128)
            if bid not in self._beliefs:
                if bid in self._measurements:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: raw measurement {bid!r} cannot propose an action"
                    )
                if bid in self._evidence:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: evidence {bid!r} requires a BeliefUpdateRecord before action proposal"
                    )
                if bid in self._actions:
                    raise FirewallViolationError(
                        f"CONSTITUTION.md Art. III: action proposal {bid!r} is not a BeliefUpdateRecord"
                    )
                raise FirewallViolationError(
                    f"Unknown belief_id {bid!r}; action proposal requires valid BeliefUpdateRecord"
                )

            clean_kind = _require_nonempty_str(action_kind, "action_kind", max_len=512)
            if isinstance(target, bool):
                eff_reversible = target
                eff_target = "unspecified"
            else:
                eff_target = _require_nonempty_str(target, "target", max_len=1024)
                if not isinstance(reversible, bool):
                    raise FirewallViolationError("reversible must be a boolean")
                eff_reversible = reversible

            clean_rationale = str(rationale).strip() if rationale is not None else ""

            idx = len(self._actions) + 1
            seq = len(self._doc["ledger"]) + 1
            record_id = f"act_{idx:04d}"
            created = timestamp()
            prev_hash = str(self._doc["chain_head"])

            temp = ActionProposalRecord(
                record_id=record_id,
                seq=seq,
                belief_id=bid,
                action_kind=clean_kind,
                target=eff_target,
                reversible=eff_reversible,
                status="REVIEW_REQUIRED",
                external_actions=0,
                requires_human_review=True,
                autonomous_execution_allowed=False,
                rationale=clean_rationale,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256="",
            )
            entry_sha = _compute_entry_sha256(
                seq=seq,
                lane="action_proposal",
                prev_hash=prev_hash,
                payload=temp.payload_dict(),
            )
            record = ActionProposalRecord(
                record_id=record_id,
                seq=seq,
                belief_id=bid,
                action_kind=clean_kind,
                target=eff_target,
                reversible=eff_reversible,
                status="REVIEW_REQUIRED",
                external_actions=0,
                requires_human_review=True,
                autonomous_execution_allowed=False,
                rationale=clean_rationale,
                created_utc=created,
                prev_hash=prev_hash,
                entry_sha256=entry_sha,
            )
            self._actions[record_id] = record
            self._commit_record("action_proposals", record)
            return record

    # ------------------------------------------------------------------
    # Inspection & Provenance Queries
    # ------------------------------------------------------------------
    def get_measurement(self, record_id: str) -> MeasurementRecord:
        with self._lock:
            return self._measurements[record_id]

    def get_evidence(self, record_id: str) -> EvidenceRecord:
        with self._lock:
            return self._evidence[record_id]

    def get_belief(self, record_id: str) -> BeliefUpdateRecord:
        with self._lock:
            return self._beliefs[record_id]

    def get_action_proposal(self, record_id: str) -> ActionProposalRecord:
        with self._lock:
            return self._actions[record_id]

    def get_record(self, record_id: str) -> AnyBlackboardRecord:
        with self._lock:
            if record_id in self._measurements:
                return self._measurements[record_id]
            if record_id in self._evidence:
                return self._evidence[record_id]
            if record_id in self._beliefs:
                return self._beliefs[record_id]
            if record_id in self._actions:
                return self._actions[record_id]
            raise KeyError(f"unknown blackboard record: {record_id!r}")

    def list_measurements(self) -> tuple[MeasurementRecord, ...]:
        with self._lock:
            return tuple(self._measurements.values())

    def list_evidence(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(self._evidence.values())

    def list_beliefs(self) -> tuple[BeliefUpdateRecord, ...]:
        with self._lock:
            return tuple(self._beliefs.values())

    def list_action_proposals(self) -> tuple[ActionProposalRecord, ...]:
        with self._lock:
            return tuple(self._actions.values())

    def negative_results(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(ev for ev in self._evidence.values() if ev.negative_result)

    def approved_evidence(self) -> tuple[EvidenceRecord, ...]:
        with self._lock:
            return tuple(ev for ev in self._evidence.values() if ev.passed and ev.approved)

    def latest_beliefs(self) -> tuple[BeliefUpdateRecord, ...]:
        with self._lock:
            superseded_ids = {
                sid for bel in self._beliefs.values() for sid in bel.superseded_belief_ids
            }
            return tuple(bel for bid, bel in self._beliefs.items() if bid not in superseded_ids)

    def export_lane_summary(self, *, include_records: bool = False) -> dict[str, Any]:
        """Export structured 4-lane status, IDs, integrity, and constitutional metadata."""
        with self._lock:
            integrity = self.verify_hash_chain(raise_on_error=False)
            superseded_ids = {
                sid for bel in self._beliefs.values() for sid in bel.superseded_belief_ids
            }
            lanes: dict[str, dict[str, Any]] = {
                "measurement": {
                    "count": len(self._measurements),
                    "sampled_only_count": sum(
                        1 for m in self._measurements.values() if m.sampled_only
                    ),
                    "record_ids": list(self._measurements.keys()),
                },
                "evidence": {
                    "count": len(self._evidence),
                    "passed_count": sum(1 for e in self._evidence.values() if e.passed),
                    "negative_count": sum(
                        1 for e in self._evidence.values() if e.negative_result
                    ),
                    "record_ids": list(self._evidence.keys()),
                },
                "belief_update": {
                    "count": len(self._beliefs),
                    "active_count": sum(
                        1 for bid in self._beliefs if bid not in superseded_ids
                    ),
                    "superseded_count": len(superseded_ids),
                    "record_ids": list(self._beliefs.keys()),
                },
                "action_proposal": {
                    "count": len(self._actions),
                    "review_required_count": sum(
                        1 for a in self._actions.values() if a.status == "REVIEW_REQUIRED"
                    ),
                    "external_actions": 0,
                    "record_ids": list(self._actions.keys()),
                },
            }
            if include_records:
                lanes["measurement"]["records"] = [
                    m.to_dict() for m in self._measurements.values()
                ]
                lanes["evidence"]["records"] = [e.to_dict() for e in self._evidence.values()]
                lanes["belief_update"]["records"] = [
                    b.to_dict() for b in self._beliefs.values()
                ]
                lanes["action_proposal"]["records"] = [
                    a.to_dict() for a in self._actions.values()
                ]
            return {
                "contract": BLACKBOARD_CONTRACT,
                "stopped": self.stopped,
                "chain_head": self._doc["chain_head"],
                "blackboard_sha256": self._doc["blackboard_sha256"],
                "integrity": integrity,
                "lanes": lanes,
                "constitutional": self.constitutional_metadata(),
            }

    def provenance_trace(self, record_id: str) -> dict[str, Any]:
        """Return full upstream provenance chain for any record ID."""
        with self._lock:
            rec = self.get_record(record_id)
            if isinstance(rec, MeasurementRecord):
                return {"measurement": rec.to_dict()}
            if isinstance(rec, EvidenceRecord):
                meas = self._measurements[rec.measurement_id]
                return {
                    "evidence": rec.to_dict(),
                    "measurement": meas.to_dict(),
                }
            if isinstance(rec, BeliefUpdateRecord):
                evs = [self._evidence[eid] for eid in rec.evidence_ids]
                meas_list = [self._measurements[ev.measurement_id] for ev in evs]
                return {
                    "belief_update": rec.to_dict(),
                    "evidence": [ev.to_dict() for ev in evs],
                    "measurements": [m.to_dict() for m in meas_list],
                }
            belief = self._beliefs[rec.belief_id]
            evs = [self._evidence[eid] for eid in belief.evidence_ids]
            meas_list = [self._measurements[ev.measurement_id] for ev in evs]
            return {
                "action_proposal": rec.to_dict(),
                "belief_update": belief.to_dict(),
                "evidence": [ev.to_dict() for ev in evs],
                "measurements": [m.to_dict() for m in meas_list],
            }

    # ------------------------------------------------------------------
    # Snapshot / Reversible Rollback / Emergency Stop
    # ------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self.verify_integrity(raise_on_error=True)
            return deepcopy(self._doc)

    def rollback(self, prior_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._require_not_stopped()
            self._validate_document_integrity(prior_snapshot)
            restored = deepcopy(dict(prior_snapshot))
            self._doc = restored
            self._stopped = bool(restored.get("stopped", False))
            self._rebuild_indices_from_doc(self._doc)
            self._save_if_persistent()
            return deepcopy(self._doc)

    def emergency_stop(
        self,
        reason: str = "Emergency stop activated",
        *,
        stop_memory: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            clean_reason = str(reason).strip() or "Emergency stop activated"
            self._stopped = True
            self._doc["stopped"] = True
            self._doc["stop_reason"] = clean_reason
            self._doc["blackboard_sha256"] = sha256_json_utf8(
                {k: v for k, v in self._doc.items() if k != "blackboard_sha256"}
            )
            self._save_if_persistent()
            if stop_memory and self._memory is not None:
                self._memory.emergency_stop()
            return self.summary()

    def to_gem_spatial_ir(
        self,
        *,
        scene_id: str = "blackboard-4lane-gem",
        theme_key: str = "zoe-viewmax3",
    ) -> dict[str, Any]:
        """Export the 4-lane epistemic firewall as a verifiable Digital Research GEM Spatial IR dict."""
        from .gem_aes_vdi import GEM_ART_II_3_NOTICE, _safe_hex_or_named_color, gem_themes

        scheme = gem_themes.resolve_viewmax_scheme(theme_key)
        bg = _safe_hex_or_named_color(scheme.desktop_bg, "#EFEBEF")
        pane = _safe_hex_or_named_color(scheme.menu_bg, "#FFFFFF")
        bar = _safe_hex_or_named_color(scheme.title_active_bg, "#00756B")
        with self._lock:
            m_cnt = len(self._measurements)
            e_cnt = len(self._evidence)
            b_cnt = len(self._beliefs)
            a_cnt = len(self._actions)
            chain_valid = bool(self.verify_integrity(raise_on_error=False)["valid"])
        return {
            "schema_version": 1,
            "id": str(scene_id),
            "title": "Epistemic Blackboard 4-Lane GEM View",
            "canvas": {"width": 10000, "height": 4000},
            "objects": [
                {"id": "hdr", "type": "rectangle", "bounds": [100, 100, 9900, 560], "fill": bar, "stroke": "black"},
                {"id": "hdr_t", "type": "text", "position": [260, 420], "text": f"BLACKBOARD valid={chain_valid}", "size": 150, "fill": "white"},
                {"id": "lane_m", "type": "rectangle", "bounds": [100, 740, 2400, 3800], "fill": pane, "stroke": "black"},
                {"id": "txt_m", "type": "text", "position": [220, 1400], "text": f"MEAS:{m_cnt}", "size": 150, "fill": "black"},
                {"id": "lane_e", "type": "rectangle", "bounds": [2600, 740, 4900, 3800], "fill": pane, "stroke": "black"},
                {"id": "txt_e", "type": "text", "position": [2720, 1400], "text": f"EVID:{e_cnt}", "size": 150, "fill": "black"},
                {"id": "lane_b", "type": "rectangle", "bounds": [5100, 740, 7400, 3800], "fill": pane, "stroke": "black"},
                {"id": "txt_b", "type": "text", "position": [5220, 1400], "text": f"BELIEF:{b_cnt}", "size": 150, "fill": "black"},
                {"id": "lane_a", "type": "rectangle", "bounds": [7600, 740, 9900, 3800], "fill": pane, "stroke": "black"},
                {"id": "txt_a", "type": "text", "position": [7720, 1400], "text": f"ACTION:{a_cnt}", "size": 150, "fill": "black"},
            ],
            "constraints": [
                {"type": "inside_canvas", "object": "*"},
                {"type": "nonoverlap", "objects": ["hdr", "lane_m", "lane_e", "lane_b", "lane_a"]},
            ],
            "visual_evidence_only": True,
            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
            "constitutional": self.constitutional_metadata(),
        }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            integrity = self.verify_integrity(raise_on_error=False)
            return {
                "contract": BLACKBOARD_CONTRACT,
                "measurements_count": len(self._measurements),
                "evidence_count": len(self._evidence),
                "evidence_passed_count": sum(1 for ev in self._evidence.values() if ev.passed),
                "negative_results_count": sum(
                    1 for ev in self._evidence.values() if ev.negative_result
                ),
                "belief_updates_count": len(self._beliefs),
                "action_proposals_count": len(self._actions),
                "ledger_length": len(self._doc["ledger"]),
                "chain_head": self._doc["chain_head"],
                "blackboard_sha256": self._doc["blackboard_sha256"],
                "stopped": self.stopped,
                "integrity_valid": bool(integrity["valid"]),
                "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
                "tamper_evidence_only": True,
                "authentication_proof": False,
                "constitutional": self.constitutional_metadata(),
            }


__all__ = [
    "ActionProposalRecord",
    "BLACKBOARD_CONTRACT",
    "BeliefUpdateRecord",
    "EpistemicBlackboard",
    "EvidenceRecord",
    "FirewallViolationError",
    "HASH_CHAIN_SEMANTICS",
    "MeasurementRecord",
    "TamperDetectedError",
    "coerce_evidence_source",
]

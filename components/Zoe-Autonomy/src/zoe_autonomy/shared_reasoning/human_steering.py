"""Architecture #8: High-Leverage Human Steering (``human_steering.py``).

Detects genuine high-leverage fork points where >= 2 independently verified
(surviving) paths diverge significantly in trade-offs or direction, triggered by:

  1. Multi-horizon supercritical $A_\\tau^{(h)}$ branching
     (``counts[h + 1] > counts[h]`` via ``exact_multihorizon_accessible_volume``).
  2. High Theorem 15 peer disagreement $D_K$ (``quorum_disagreement_dk >= threshold``).
  3. ``OptionShift`` narrowing (``suspected_unjustified_narrowing``, ``boxed``,
     or sharp option drop) or an irreversible / high-impact boundary
     (``CONSTITUTION.md`` Articles I & IV).

Constitutional & Epistemic Guarantees (``docs/CONSTITUTION.md``):
  - Never surfaces unverified, failed, or sampled-only paths as verified options
    (Article II.1-2, Article III.2-3).
  - Suppresses fork prompts when fewer than 2 verified paths survive or when
    surviving paths do not meaningfully diverge (prevents alert fatigue).
  - Never fabricates urgency, certainty, or scarcity; presents calm, factual
    trade-offs and preserves human authority to select, reject all, stop, or
    request a reversible alternative (Article I.1-3, Article I.5, Article IV.1-4).
  - Bridges directly to ``google.antigravity.hooks.hooks.OnInteractionHook`` /
    ``QuestionHookResult`` (``ASK_USER``) with ``external_actions=0`` (Article III.4).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import inspect
import math
import re
from typing import Any

import numpy as np

from google.antigravity.hooks import hooks as ag_hooks
from google.antigravity.types import (
    AskQuestionEntry,
    AskQuestionInteractionSpec,
    AskQuestionOption,
    QuestionHookResult,
    QuestionResponse,
)

from ..l5_phase6_multihorizon_metacognition import exact_multihorizon_accessible_volume
from ..metacognition import EvidenceSource, OptionShift, STRONG_SOURCE_KINDS
from .sdk_bridge import ATTRIBUTION_TEXT, bridge_constitutional_metadata

HUMAN_STEERING_CONTRACT = "zoe-human-steering/v1"
INTERACTION_MODE = "ASK_USER"

DEFAULT_DK_THRESHOLD = 0.12
DEFAULT_DIVERGENCE_THRESHOLD = 0.25
DEFAULT_OPTION_SHIFT_DROP = 2
DEFAULT_TAU = 0.12
DEFAULT_HORIZON = 3

VERIFIED_STATUSES: frozenset[str] = frozenset(
    {"verified", "independently_verified", "passed", "confirmed"}
)
UNVERIFIED_STATUSES: frozenset[str] = frozenset(
    {
        "unverified",
        "failed",
        "rejected",
        "sampled_only",
        "pending",
        "stale",
        "error",
        "unknown",
    }
)

REJECT_ALL_OPTION_ID = "__reject_all__"
STOP_OPTION_ID = "__stop__"
REQUEST_REVERSIBLE_OPTION_ID = "__request_reversible__"

CONSTITUTIONAL_NOTICE_TEXT = (
    "CONSTITUTION.md Art. I & IV Notice: Human judgment holds final authority. "
    "No model score or recommendation authorizes autonomous action (external_actions=0). "
    "You may select one verified path, reject all options, stop execution, or require a "
    "reversible alternative. No urgency is implied."
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _clean_text(value: Any, label: str, *, allow_empty: bool = False, max_len: int = 2048) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    cleaned = " ".join(value.split()).strip()
    if not allow_empty and not cleaned:
        raise ValueError(f"{label} must not be empty")
    if len(cleaned) > max_len:
        raise ValueError(f"{label} exceeds maximum length {max_len}")
    return cleaned


def _tokenize(text_value: str) -> set[str]:
    return set(_TOKEN_RE.findall(text_value.lower()))


def _has_strong_evidence_source(evidence_source: Any) -> bool:
    """Return True iff ``evidence_source`` represents a strong independent source."""
    if evidence_source is None:
        return False
    if hasattr(evidence_source, "to_evidence_source") and callable(
        evidence_source.to_evidence_source
    ):
        try:
            evidence_source = evidence_source.to_evidence_source()
        except Exception:
            return False
    if isinstance(evidence_source, EvidenceSource):
        return bool(evidence_source.strong)
    if isinstance(evidence_source, Mapping):
        kind = str(evidence_source.get("kind", ""))
        trust = evidence_source.get("trust", 0.0)
        strength = evidence_source.get("strength", 0.0)
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
        if "strong_evidence" in evidence_source and isinstance(
            evidence_source["strong_evidence"], bool
        ):
            return bool(evidence_source["strong_evidence"]) and computed_strong
        return computed_strong
    return False


def _jaccard_distance(a: str, b: str) -> float:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta and not tb:
        return 0.0
    union = ta | tb
    if not union:
        return 0.0
    return 1.0 - (len(ta & tb) / len(union))


@dataclass(frozen=True)
class VerifiedPathOption:
    """Candidate reasoning/execution path with explicit verification and reversibility metadata.

    Attributes:
        path_id: Unique stable identifier for the path.
        summary: Concise description of what this path does.
        verification_status: Verification state (only statuses in
            ``VERIFIED_STATUSES`` with supporting ``evidence_ids`` qualify as
            independently verified).
        evidence_ids: Evidence record identifiers supporting verification.
        expected_utility: Finite numeric utility estimate for trade-off comparison.
        tradeoff_notes: Explicit summary of benefits, costs, risks, and limitations.
        reversible: Whether the path can be cleanly reversed or rolled back.
        direction_tags: Optional semantic direction tags for divergence comparison.
        verifier_name: Optional name of the deterministic/independent verifier.
        metadata: Optional JSON-safe contextual annotations.
    """

    path_id: str
    summary: str
    verification_status: str
    evidence_ids: tuple[str, ...]
    expected_utility: float
    tradeoff_notes: str
    reversible: bool
    direction_tags: tuple[str, ...] = ()
    verifier_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean_id = _clean_text(self.path_id, "path_id", max_len=256)
        clean_summary = _clean_text(self.summary, "summary", max_len=2048)
        clean_status = _clean_text(self.verification_status, "verification_status", max_len=64).lower()

        if isinstance(self.evidence_ids, (str, bytes)) or not isinstance(self.evidence_ids, Sequence):
            raise ValueError("evidence_ids must be a sequence of non-empty strings")
        ev_tuple = tuple(_clean_text(eid, "evidence_id", max_len=256) for eid in self.evidence_ids)

        if isinstance(self.expected_utility, bool) or not isinstance(self.expected_utility, (int, float)):
            raise ValueError("expected_utility must be a finite number")
        util = float(self.expected_utility)
        if not math.isfinite(util):
            raise ValueError(f"expected_utility must be finite, got {self.expected_utility!r}")

        clean_tradeoffs = _clean_text(self.tradeoff_notes, "tradeoff_notes", allow_empty=True, max_len=2048)
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be a boolean")

        if isinstance(self.direction_tags, (str, bytes)) or not isinstance(self.direction_tags, Sequence):
            raise ValueError("direction_tags must be a sequence of strings")
        tags_tuple = tuple(
            _clean_text(tag, "direction_tag", max_len=128).lower()
            for tag in self.direction_tags
        )
        clean_verifier = _clean_text(self.verifier_name, "verifier_name", allow_empty=True, max_len=256)
        meta_copy = dict(self.metadata) if isinstance(self.metadata, Mapping) else {}

        object.__setattr__(self, "path_id", clean_id)
        object.__setattr__(self, "summary", clean_summary)
        object.__setattr__(self, "verification_status", clean_status)
        object.__setattr__(self, "evidence_ids", ev_tuple)
        object.__setattr__(self, "expected_utility", util)
        object.__setattr__(self, "tradeoff_notes", clean_tradeoffs)
        object.__setattr__(self, "direction_tags", tags_tuple)
        object.__setattr__(self, "verifier_name", clean_verifier)
        object.__setattr__(self, "metadata", meta_copy)

    def rejection_reason(self, *, require_evidence_ids: bool = True) -> str | None:
        """Return the reason this path fails verification gating, or ``None`` if verified."""
        if self.verification_status not in VERIFIED_STATUSES:
            return f"verification_status={self.verification_status}"
        if require_evidence_ids and not self.evidence_ids:
            return "missing_evidence_ids"
        return None

    def is_verified(self, *, require_evidence_ids: bool = True) -> bool:
        """Return True iff the option has passed independent verification."""
        return self.rejection_reason(require_evidence_ids=require_evidence_ids) is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "summary": self.summary,
            "verification_status": self.verification_status,
            "evidence_ids": list(self.evidence_ids),
            "expected_utility": self.expected_utility,
            "tradeoff_notes": self.tradeoff_notes,
            "reversible": self.reversible,
            "direction_tags": list(self.direction_tags),
            "verifier_name": self.verifier_name,
            "is_verified": self.is_verified(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ForkPointReport:
    """Structured report produced by ``HumanSteeringDetector``.

    Attributes:
        fork_detected: True iff >= 2 independently verified paths diverge
            significantly AND at least one fork trigger is active.
        triggers: Active trigger identifiers explaining why steering was raised.
        supercritical_counts: Exact multi-horizon $A_\\tau^{(h)}$ counts if evaluated.
        quorum_disagreement_dk: Theorem 15 peer disagreement $D_K$ if provided.
        option_shift_narrowed: True if ``OptionShift`` detected narrowing or boxing.
        divergent_options: Surviving independently verified paths surfaced to the user
            (empty when ``fork_detected`` is False; never includes unverified paths).
        prompt_for_human: Calm, non-coercive steering prompt when ``fork_detected`` is True.
        constitutional_notice: Explicit Article I & IV human-agency notice.
        filtered_out_options: Audit trail of excluded unverified/failed options.
        divergence_score: Pairwise trade-off/direction divergence in ``[0, 1]``.
        irreversible_boundary_triggered: True if any surviving path is irreversible
            or ``high_impact=True`` was signaled.
        suppressed_reason: Explanation when a fork prompt was suppressed.
        interaction_spec: Serialized ``AskQuestionInteractionSpec`` dict when active.
        interaction_mode: Always ``"ASK_USER"``.
        constitutional: Canonical ``CONSTITUTION.md`` metadata (``external_actions=0``).
        contract: Contract identifier string.
    """

    fork_detected: bool
    triggers: tuple[str, ...]
    supercritical_counts: tuple[int, ...]
    quorum_disagreement_dk: float | None
    option_shift_narrowed: bool
    divergent_options: tuple[VerifiedPathOption, ...]
    prompt_for_human: str | None
    constitutional_notice: str
    filtered_out_options: tuple[dict[str, str], ...] = ()
    divergence_score: float = 0.0
    irreversible_boundary_triggered: bool = False
    suppressed_reason: str | None = None
    interaction_spec: dict[str, Any] | None = None
    interaction_mode: str = INTERACTION_MODE
    blackboard_records: dict[str, str] = field(default_factory=dict)
    gem_form_alert: dict[str, Any] | None = None
    constitutional: dict[str, Any] = field(default_factory=bridge_constitutional_metadata)
    contract: str = HUMAN_STEERING_CONTRACT

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "interaction_mode": self.interaction_mode,
            "fork_detected": self.fork_detected,
            "triggers": list(self.triggers),
            "supercritical_counts": list(self.supercritical_counts),
            "quorum_disagreement_dk": self.quorum_disagreement_dk,
            "option_shift_narrowed": self.option_shift_narrowed,
            "divergent_options": [opt.to_dict() for opt in self.divergent_options],
            "prompt_for_human": self.prompt_for_human,
            "constitutional_notice": self.constitutional_notice,
            "filtered_out_options": [dict(item) for item in self.filtered_out_options],
            "divergence_score": round(float(self.divergence_score), 6),
            "irreversible_boundary_triggered": self.irreversible_boundary_triggered,
            "suppressed_reason": self.suppressed_reason,
            "interaction_spec": self.interaction_spec,
            "blackboard_records": dict(self.blackboard_records),
            "gem_form_alert": dict(self.gem_form_alert) if self.gem_form_alert is not None else None,
            "constitutional": dict(self.constitutional),
            "attribution": ATTRIBUTION_TEXT,
        }


class _HumanSteeringInteractionHook(ag_hooks.OnInteractionHook):
    """Concrete ``OnInteractionHook`` bridging fork-point steering to Antigravity."""

    def __init__(self, steering_callback: Callable[..., Any]) -> None:
        if not callable(steering_callback):
            raise TypeError("steering_callback must be callable")
        self._steering_callback = steering_callback

    @staticmethod
    def _coerce_result(raw: Any, spec: AskQuestionInteractionSpec) -> QuestionHookResult:
        if isinstance(raw, QuestionHookResult):
            return raw
        if isinstance(raw, QuestionResponse):
            return QuestionHookResult(responses=[raw], cancelled=False)
        if raw is None:
            return QuestionHookResult(
                responses=[QuestionResponse(skipped=True)],
                cancelled=True,
            )
        if isinstance(raw, str):
            cleaned = raw.strip()
            if not cleaned or cleaned.lower() in {"cancel", "cancelled", "__cancel__"}:
                return QuestionHookResult(responses=[], cancelled=True)
            option_ids = {
                opt.id
                for q in spec.questions
                for opt in q.options
            }
            if cleaned in option_ids:
                return QuestionHookResult(
                    responses=[QuestionResponse(selected_option_ids=[cleaned])],
                    cancelled=False,
                )
            return QuestionHookResult(
                responses=[QuestionResponse(freeform_response=cleaned)],
                cancelled=False,
            )
        if isinstance(raw, Mapping):
            if "responses" in raw:
                return QuestionHookResult.model_validate(dict(raw))
            cancelled = bool(raw.get("cancelled", False))
            if cancelled and not any(k in raw for k in ("selected_option_ids", "freeform_response", "skipped")):
                return QuestionHookResult(responses=[], cancelled=True)
            resp = QuestionResponse(
                selected_option_ids=raw.get("selected_option_ids"),
                freeform_response=str(raw.get("freeform_response", "")),
                skipped=bool(raw.get("skipped", False)),
            )
            return QuestionHookResult(responses=[resp], cancelled=cancelled)
        raise TypeError(
            "steering_callback must return QuestionHookResult, QuestionResponse, "
            f"str, Mapping, or None; got {type(raw).__name__}"
        )

    async def _invoke_callback(
        self, context: ag_hooks.HookContext, data: AskQuestionInteractionSpec
    ) -> Any:
        try:
            sig = inspect.signature(self._steering_callback)
            params = list(sig.parameters.values())
            positional = [
                p
                for p in params
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
            required_positional = [
                p for p in positional if p.default is inspect.Parameter.empty
            ]
            first_is_context = bool(
                positional
                and positional[0].name.lstrip("_").lower() in {"context", "ctx"}
            )
            wants_two_args = (
                len(required_positional) >= 2
                or (len(positional) >= 2 and first_is_context)
                or (has_varargs and (not positional or first_is_context))
            )
            if wants_two_args:
                result = self._steering_callback(context, data)
            else:
                result = self._steering_callback(data)
        except (TypeError, ValueError):
            result = self._steering_callback(data)

        if inspect.isawaitable(result):
            result = await result
        return result

    async def run(
        self, context: ag_hooks.HookContext, data: AskQuestionInteractionSpec
    ) -> QuestionHookResult:
        if not isinstance(data, AskQuestionInteractionSpec):
            data = AskQuestionInteractionSpec.model_validate(data)
        raw = await self._invoke_callback(context, data)
        return self._coerce_result(raw, data)


class HumanSteeringDetector:
    """Architecture #8 engine detecting high-leverage verified fork points for human steering."""

    def __init__(
        self,
        *,
        dk_threshold: float = DEFAULT_DK_THRESHOLD,
        divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
        option_shift_narrowing_min_drop: int = DEFAULT_OPTION_SHIFT_DROP,
        require_evidence_ids: bool = True,
        default_tau: float = DEFAULT_TAU,
        default_horizon: int = DEFAULT_HORIZON,
    ) -> None:
        if isinstance(dk_threshold, bool) or not isinstance(dk_threshold, (int, float)) or not math.isfinite(dk_threshold) or dk_threshold < 0.0:
            raise ValueError("dk_threshold must be a finite non-negative float")
        if isinstance(divergence_threshold, bool) or not isinstance(divergence_threshold, (int, float)) or not (0.0 <= divergence_threshold <= 1.0):
            raise ValueError("divergence_threshold must be in [0, 1]")
        if isinstance(option_shift_narrowing_min_drop, bool) or not isinstance(option_shift_narrowing_min_drop, int) or option_shift_narrowing_min_drop < 1:
            raise ValueError("option_shift_narrowing_min_drop must be >= 1")
        if isinstance(default_tau, bool) or not isinstance(default_tau, (int, float)) or not (0.0 < default_tau < 1.0):
            raise ValueError("default_tau must lie strictly in (0, 1)")
        if isinstance(default_horizon, bool) or not isinstance(default_horizon, int) or default_horizon < 1:
            raise ValueError("default_horizon must be >= 1")

        self.dk_threshold = float(dk_threshold)
        self.divergence_threshold = float(divergence_threshold)
        self.option_shift_narrowing_min_drop = int(option_shift_narrowing_min_drop)
        self.require_evidence_ids = bool(require_evidence_ids)
        self.default_tau = float(default_tau)
        self.default_horizon = int(default_horizon)

    def filter_verified_options(
        self,
        options: Sequence[VerifiedPathOption],
        *,
        blackboard: Any = None,
    ) -> tuple[tuple[VerifiedPathOption, ...], tuple[dict[str, str], ...]]:
        """Separate independently verified surviving paths from unverified/failed paths."""
        if blackboard is not None and hasattr(blackboard, "verify_integrity"):
            blackboard.verify_integrity(raise_on_error=True)

        verified: list[VerifiedPathOption] = []
        filtered_out: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for opt in options:
            if not isinstance(opt, VerifiedPathOption):
                raise TypeError(f"expected VerifiedPathOption, got {type(opt).__name__}")
            if opt.path_id in seen_ids:
                raise ValueError(f"duplicate path_id {opt.path_id!r}")
            seen_ids.add(opt.path_id)

            reason = opt.rejection_reason(require_evidence_ids=self.require_evidence_ids)
            if reason is None and blackboard is not None and hasattr(blackboard, "get_record"):
                for eid in opt.evidence_ids:
                    try:
                        rec = blackboard.get_record(eid)
                    except KeyError:
                        reason = f"unknown_blackboard_evidence:{eid}"
                        break
                    except Exception:
                        reason = f"blackboard_lookup_failed:{eid}"
                        break
                    if rec is None:
                        reason = f"unknown_blackboard_evidence:{eid}"
                        break
                    if getattr(rec, "lane", None) != "evidence":
                        reason = f"invalid_blackboard_lane:{eid}"
                        break
                    if not getattr(rec, "passed", False):
                        reason = f"blackboard_evidence_failed:{eid}"
                        break
                    if not getattr(rec, "approved", False):
                        reason = f"blackboard_evidence_unapproved:{eid}"
                        break
                    is_sampled = bool(
                        getattr(rec, "sampled_source", False)
                        or getattr(rec, "sampled_only", False)
                    )
                    if is_sampled and not _has_strong_evidence_source(
                        getattr(rec, "evidence_source", None)
                    ):
                        reason = f"blackboard_sampled_only:{eid}"
                        break

            if reason is not None:
                filtered_out.append(
                    {
                        "path_id": opt.path_id,
                        "verification_status": opt.verification_status,
                        "reason": reason,
                    }
                )
            else:
                verified.append(opt)

        return tuple(verified), tuple(filtered_out)

    @staticmethod
    def pair_divergence(a: VerifiedPathOption, b: VerifiedPathOption) -> float:
        """Compute structural & trade-off divergence in ``[0.0, 1.0]`` between two options."""
        rev_diff = 1.0 if a.reversible != b.reversible else 0.0
        tradeoff_dist = _jaccard_distance(a.tradeoff_notes, b.tradeoff_notes)
        summary_dist = _jaccard_distance(a.summary, b.summary)
        if a.direction_tags or b.direction_tags:
            ta = set(a.direction_tags)
            tb = set(b.direction_tags)
            dir_dist = 1.0 - (len(ta & tb) / len(ta | tb)) if (ta | tb) else 0.0
        else:
            dir_dist = tradeoff_dist
        util_diff = min(1.0, abs(a.expected_utility - b.expected_utility))

        score_rev = 0.45 * rev_diff + 0.35 * dir_dist + 0.20 * tradeoff_dist
        score_tradeoff = 0.55 * tradeoff_dist + 0.25 * summary_dist + 0.20 * util_diff
        return max(score_rev, score_tradeoff)

    def compute_divergence(
        self, verified_options: Sequence[VerifiedPathOption]
    ) -> tuple[float, bool]:
        """Compute maximum pairwise divergence across surviving verified paths."""
        if len(verified_options) < 2:
            return 0.0, False
        max_div = 0.0
        for i in range(len(verified_options)):
            for j in range(i + 1, len(verified_options)):
                div = self.pair_divergence(verified_options[i], verified_options[j])
                if div > max_div:
                    max_div = div
        return max_div, max_div >= self.divergence_threshold

    @staticmethod
    def options_from_fork_candidates(
        fork_candidates: Sequence[Any],
        *,
        evidence_by_branch: Mapping[str, Sequence[str]] | None = None,
        verified_branch_ids: Sequence[str] | set[str] | frozenset[str] | None = None,
        reversible_by_branch: Mapping[str, bool] | None = None,
        tradeoff_by_branch: Mapping[str, str] | None = None,
        direction_tags_by_branch: Mapping[str, Sequence[str]] | None = None,
    ) -> tuple[VerifiedPathOption, ...]:
        """Convert ``MCTSSearchResult.fork_candidates`` into ``VerifiedPathOption`` instances.

        Enforces ``CONSTITUTION.md`` Article II/III: branches are marked ``"verified"``
        ONLY when explicit verification evidence IDs are provided via
        ``evidence_by_branch`` (or ``verified_branch_ids``). Branches lacking
        independent evidence remain ``"unverified"`` and are filtered safely.
        """
        ev_map = dict(evidence_by_branch or {})
        verified_set = set(verified_branch_ids or ())
        rev_map = dict(reversible_by_branch or {})
        tradeoff_map = dict(tradeoff_by_branch or {})
        tags_map = dict(direction_tags_by_branch or {})

        options: list[VerifiedPathOption] = []
        seen_branch_ids: set[str] = set()
        for fc in fork_candidates:
            branches = getattr(fc, "competing_branches", None)
            if branches is None and isinstance(fc, Mapping):
                branches = fc.get("competing_branches", ())
            fork_reason = (
                getattr(fc, "reason", None)
                or (fc.get("reason") if isinstance(fc, Mapping) else "")
                or ""
            )
            fork_id = (
                getattr(fc, "fork_id", None)
                or (fc.get("fork_id") if isinstance(fc, Mapping) else "")
                or "fork"
            )
            for branch in branches or ():
                if isinstance(branch, Mapping):
                    branch_id = str(branch.get("branch_id", ""))
                    actions = tuple(str(a) for a in (branch.get("actions") or ()))
                    joint_prob = float(branch.get("joint_prob", 0.0))
                    mean_val = float(branch.get("mean_value", 0.0))
                    visits = int(branch.get("visits", 0))
                    depth = int(branch.get("depth", len(actions)))
                    pruned = bool(branch.get("pruned", False))
                else:
                    branch_id = str(getattr(branch, "branch_id", ""))
                    actions = tuple(str(a) for a in (getattr(branch, "actions", ()) or ()))
                    joint_prob = float(getattr(branch, "joint_prob", 0.0))
                    mean_val = float(getattr(branch, "mean_value", 0.0))
                    visits = int(getattr(branch, "visits", 0))
                    depth = int(getattr(branch, "depth", len(actions)))
                    pruned = bool(getattr(branch, "pruned", False))

                if not branch_id or branch_id in seen_branch_ids:
                    continue
                seen_branch_ids.add(branch_id)

                ev_ids = tuple(str(eid) for eid in ev_map.get(branch_id, ()))
                if pruned:
                    status = "failed"
                elif ev_ids and (not verified_set or branch_id in verified_set):
                    status = "verified"
                else:
                    status = "unverified"

                action_seq = " -> ".join(actions) if actions else branch_id
                summary = f"Branch {branch_id}: {action_seq}"
                tradeoff = tradeoff_map.get(branch_id) or (
                    f"actions={action_seq}; joint_prob={joint_prob:.4f}; "
                    f"visits={visits}; depth={depth}"
                    + (f"; fork={fork_reason}" if fork_reason else "")
                )
                reversible = bool(rev_map.get(branch_id, True))
                dir_tags = tuple(tags_map.get(branch_id, actions or (branch_id,)))

                options.append(
                    VerifiedPathOption(
                        path_id=branch_id,
                        summary=summary,
                        verification_status=status,
                        evidence_ids=ev_ids,
                        expected_utility=mean_val,
                        tradeoff_notes=tradeoff,
                        reversible=reversible,
                        direction_tags=dir_tags,
                        verifier_name="mcts_kloster_branch",
                        metadata={
                            "fork_id": fork_id,
                            "joint_prob": joint_prob,
                            "visits": visits,
                            "depth": depth,
                        },
                    )
                )
        return tuple(options)

    def _resolve_supercritical_counts(
        self,
        *,
        next_dist_fn: Callable[[tuple[int, ...]], np.ndarray] | None,
        tau: float | None,
        horizon: int | None,
        supercritical_counts: Sequence[int] | None,
        mcts_result: Any,
        fork_candidates: Sequence[Any] | None = None,
    ) -> tuple[tuple[int, ...], bool]:
        resolved_counts: tuple[int, ...] = ()
        if next_dist_fn is not None:
            mh = exact_multihorizon_accessible_volume(
                next_dist_fn,
                tau=self.default_tau if tau is None else float(tau),
                horizon=self.default_horizon if horizon is None else int(horizon),
            )
            resolved_counts = tuple(int(c) for c in mh["counts_by_h"])
        elif supercritical_counts is not None:
            resolved_counts = tuple(int(c) for c in supercritical_counts)
        elif mcts_result is not None:
            mh_vol = getattr(mcts_result, "multihorizon_volume", None)
            if mh_vol is None and isinstance(mcts_result, Mapping):
                mh_vol = mcts_result.get("multihorizon_volume")
            if isinstance(mh_vol, Mapping) and mh_vol.get("counts_by_h"):
                resolved_counts = tuple(int(c) for c in mh_vol["counts_by_h"])
            else:
                traj = getattr(mcts_result, "a_tau_trajectory", None)
                if traj is None and isinstance(mcts_result, Mapping):
                    traj = mcts_result.get("a_tau_trajectory") or mcts_result.get("counts_by_h")
                if traj:
                    if isinstance(traj[-1], Mapping) and traj[-1].get("counts_by_h"):
                        resolved_counts = tuple(int(c) for c in traj[-1]["counts_by_h"])
                    elif all(isinstance(x, (int, np.integer)) and not isinstance(x, bool) for x in traj):
                        resolved_counts = tuple(int(c) for c in traj)

        supercritical = any(
            resolved_counts[idx + 1] > resolved_counts[idx] and resolved_counts[idx + 1] >= 2
            for idx in range(len(resolved_counts) - 1)
        )
        if not supercritical:
            fc_list = (
                fork_candidates
                if fork_candidates is not None
                else (
                    getattr(mcts_result, "fork_candidates", None)
                    if mcts_result is not None and not isinstance(mcts_result, Mapping)
                    else (mcts_result.get("fork_candidates") if isinstance(mcts_result, Mapping) else None)
                )
            )
            if fc_list:
                for fc in fc_list:
                    delayed = getattr(fc, "delayed_fork", None)
                    if delayed is None and isinstance(fc, Mapping):
                        delayed = fc.get("delayed_fork", False)
                    if delayed:
                        supercritical = True
                        break
        return resolved_counts, supercritical

    @staticmethod
    def _resolve_dk(
        quorum_disagreement_dk: float | None,
        quorum_result: Any,
    ) -> float | None:
        raw_dk: Any = quorum_disagreement_dk
        if raw_dk is None and quorum_result is not None:
            for attr_name in ("disagreement_dk", "d_k_disagreement"):
                raw_dk = getattr(quorum_result, attr_name, None)
                if raw_dk is not None:
                    break
            if raw_dk is None and isinstance(quorum_result, Mapping):
                raw_dk = quorum_result.get("disagreement_dk")
                if raw_dk is None:
                    raw_dk = quorum_result.get("d_k_disagreement")
        if raw_dk is None:
            return None
        if isinstance(raw_dk, bool) or not isinstance(raw_dk, (int, float)):
            raise ValueError("quorum_disagreement_dk must be a finite float")
        dk = float(raw_dk)
        if not math.isfinite(dk) or dk < 0.0:
            raise ValueError(f"quorum_disagreement_dk must be finite and non-negative, got {raw_dk!r}")
        return dk

    def _is_option_shift_narrowed(self, option_shift: OptionShift | None) -> bool:
        if option_shift is None:
            return False
        if not isinstance(option_shift, OptionShift):
            raise TypeError(f"expected OptionShift, got {type(option_shift).__name__}")
        if option_shift.suspected_unjustified_narrowing:
            return True
        if option_shift.current.boxed:
            return True
        if option_shift.delta < 0 and abs(option_shift.delta) >= self.option_shift_narrowing_min_drop:
            return True
        return False

    @staticmethod
    def _format_human_prompt(
        *,
        verified_options: Sequence[VerifiedPathOption],
        triggers: Sequence[str],
        supercritical_counts: tuple[int, ...],
        quorum_disagreement_dk: float | None,
        option_shift_narrowed: bool,
        irreversible_boundary: bool,
        context_summary: str,
    ) -> str:
        header = "Human steering check: multiple independently verified paths diverge in trade-offs."
        if context_summary:
            header = f"{header} Context: {context_summary}."

        trigger_parts: list[str] = []
        if "supercritical_multihorizon_branching" in triggers:
            trigger_parts.append(f"multi-horizon A_tau^(h) branching={list(supercritical_counts)}")
        if "high_quorum_disagreement_dk" in triggers and quorum_disagreement_dk is not None:
            trigger_parts.append(f"peer disagreement D_K={quorum_disagreement_dk:.4f}")
        if option_shift_narrowed:
            trigger_parts.append("OptionShift narrowing detected")
        if irreversible_boundary:
            trigger_parts.append("irreversible or high-impact boundary present")

        lines = [header, f"Observed triggers: {'; '.join(trigger_parts)}.", "Verified paths:"]
        for idx, opt in enumerate(verified_options, start=1):
            rev_label = "reversible" if opt.reversible else "irreversible (review required)"
            ev_label = ", ".join(opt.evidence_ids) if opt.evidence_ids else "none"
            lines.append(
                f"  {idx}. [{opt.path_id}] {opt.summary} "
                f"(utility={opt.expected_utility:.3f}, {rev_label}, evidence=[{ev_label}])"
                + (f" — Trade-offs: {opt.tradeoff_notes}" if opt.tradeoff_notes else "")
            )
        lines.append(
            "Options: select a verified path above, reject all paths, stop for review, "
            "or request a reversible alternative."
        )
        return "\n".join(lines)

    def build_interaction_spec(
        self, report: ForkPointReport
    ) -> AskQuestionInteractionSpec | None:
        """Build an Antigravity ``AskQuestionInteractionSpec`` from a ``ForkPointReport``."""
        if not report.fork_detected or not report.divergent_options or not report.prompt_for_human:
            return None

        ask_options: list[AskQuestionOption] = []
        has_irreversible = False
        for opt in report.divergent_options:
            if not opt.reversible:
                has_irreversible = True
            rev_tag = "reversible" if opt.reversible else "irreversible"
            text_desc = (
                f"{opt.summary} | utility={opt.expected_utility:.3f} | {rev_tag} | "
                f"evidence={','.join(opt.evidence_ids)}"
            )
            if opt.tradeoff_notes:
                text_desc = f"{text_desc} | tradeoffs: {opt.tradeoff_notes}"
            ask_options.append(AskQuestionOption(id=opt.path_id, text=text_desc))

        ask_options.append(
            AskQuestionOption(
                id=REJECT_ALL_OPTION_ID,
                text="Reject all proposed paths and keep current state unchanged",
            )
        )
        ask_options.append(
            AskQuestionOption(
                id=STOP_OPTION_ID,
                text="Stop execution and pause for manual review",
            )
        )
        if has_irreversible:
            ask_options.append(
                AskQuestionOption(
                    id=REQUEST_REVERSIBLE_OPTION_ID,
                    text="Require a reversible alternative before proceeding",
                )
            )

        entry = AskQuestionEntry(
            question=f"{report.prompt_for_human}\n\n{report.constitutional_notice}",
            options=ask_options,
            is_multi_select=False,
        )
        return AskQuestionInteractionSpec(questions=[entry])

    def build_interaction_hook(
        self, steering_callback: Callable[..., Any]
    ) -> ag_hooks.OnInteractionHook:
        """Return an Antigravity ``OnInteractionHook`` wrapping ``steering_callback``."""
        return _HumanSteeringInteractionHook(steering_callback)

    def interpret_hook_result(
        self, report: ForkPointReport, result: QuestionHookResult
    ) -> dict[str, Any]:
        """Translate a ``QuestionHookResult`` into an explicit, zero-action steering record."""
        if not isinstance(result, QuestionHookResult):
            raise TypeError(f"expected QuestionHookResult, got {type(result).__name__}")

        if result.cancelled or not result.responses:
            return {
                "decision": "cancelled",
                "selected_path_id": None,
                "selected_option": None,
                "freeform_response": "",
                "external_actions": 0,
                "human_override_respected": True,
                "constitutional": dict(report.constitutional),
            }

        resp = result.responses[0]
        if resp.skipped:
            return {
                "decision": "stopped",
                "selected_path_id": None,
                "selected_option": None,
                "freeform_response": resp.freeform_response,
                "external_actions": 0,
                "human_override_respected": True,
                "constitutional": dict(report.constitutional),
            }

        selected_ids = list(resp.selected_option_ids or [])
        if selected_ids:
            chosen_id = selected_ids[0]
            if chosen_id == REJECT_ALL_OPTION_ID:
                decision = "rejected"
                selected_opt = None
            elif chosen_id == STOP_OPTION_ID:
                decision = "stopped"
                selected_opt = None
            elif chosen_id == REQUEST_REVERSIBLE_OPTION_ID:
                decision = "request_reversible"
                selected_opt = None
            else:
                by_id = {opt.path_id: opt for opt in report.divergent_options}
                if chosen_id not in by_id:
                    raise ValueError(
                        f"selected path_id {chosen_id!r} is not among verified divergent_options"
                    )
                decision = "selected"
                selected_opt = by_id[chosen_id]
            return {
                "decision": decision,
                "selected_path_id": chosen_id if decision == "selected" else None,
                "selected_option": selected_opt.to_dict() if selected_opt else None,
                "freeform_response": resp.freeform_response,
                "external_actions": 0,
                "human_override_respected": True,
                "constitutional": dict(report.constitutional),
            }

        return {
            "decision": "freeform",
            "selected_path_id": None,
            "selected_option": None,
            "freeform_response": resp.freeform_response,
            "external_actions": 0,
            "human_override_respected": True,
            "constitutional": dict(report.constitutional),
        }

    def record_fork_to_blackboard(
        self,
        blackboard: Any,
        report: ForkPointReport,
        *,
        propose_action: bool = True,
        reversible: bool = True,
        target: str = "human_operator",
        context_summary: str = "",
    ) -> dict[str, str]:
        """Record a fork-point notification onto ``EpistemicBlackboard``.

        Always enforces ``CONSTITUTION.md`` Article III's 4-lane firewall:
        posts a deterministic ``MeasurementRecord`` and, when ``report.fork_detected``
        and ``propose_action`` are True, promotes to ``EvidenceRecord``, records
        an epistemic ``BeliefUpdateRecord``, and submits a ``propose_action``
        with ``reversible=reversible``, ``status="REVIEW_REQUIRED"``, and
        ``external_actions=0``.
        """
        if blackboard is None or not hasattr(blackboard, "post_measurement"):
            raise TypeError("blackboard must implement EpistemicBlackboard.post_measurement")

        verified_cnt = len(report.divergent_options)
        filtered_cnt = len(report.filtered_out_options)
        meas = blackboard.post_measurement(
            source_agent="human_steering_detector",
            input_desc=context_summary or "high_leverage_fork_evaluation",
            method="HumanSteeringDetector.detect",
            scope=f"verified={verified_cnt},filtered={filtered_cnt}",
            limitations="Steering detection is advisory only (external_actions=0); human decides.",
            value={
                "fork_detected": report.fork_detected,
                "triggers": list(report.triggers),
                "supercritical_counts": list(report.supercritical_counts),
                "quorum_disagreement_dk": report.quorum_disagreement_dk,
                "option_shift_narrowed": report.option_shift_narrowed,
                "divergence_score": round(report.divergence_score, 6),
                "divergent_option_ids": [o.path_id for o in report.divergent_options],
            },
            sampled_only=False,
        )
        records: dict[str, str] = {"measurement_id": meas.record_id}

        if (
            report.fork_detected
            and propose_action
            and hasattr(blackboard, "promote_to_evidence")
            and hasattr(blackboard, "update_belief")
            and hasattr(blackboard, "propose_action")
        ):
            ev = blackboard.promote_to_evidence(
                meas.record_id,
                verifier_name="HumanSteeringDetector",
                passed=True,
                rationale=(
                    f"Deterministic fork-point check confirmed {verified_cnt} divergent "
                    f"verified paths with active triggers={list(report.triggers)}."
                ),
            )
            bel = blackboard.update_belief(
                [ev.record_id],
                claim=(
                    f"High-leverage fork point requires human steering across "
                    f"{[o.path_id for o in report.divergent_options]}"
                ),
                posterior_delta=0.0,
                subject="human_steering_fork",
                relation="fork_point_detected",
                confidence=1.0,
            )
            act = blackboard.propose_action(
                bel.record_id,
                "ASK_USER_FORK_STEERING",
                target=target,
                reversible=bool(reversible),
                rationale=(
                    f"Present {verified_cnt} verified divergent options via ASK_USER; "
                    f"triggers={list(report.triggers)}"
                ),
            )
            records["evidence_id"] = ev.record_id
            records["belief_id"] = bel.record_id
            records["action_proposal_id"] = act.record_id

        return records

    def detect(
        self,
        options: Sequence[VerifiedPathOption] | None = None,
        *,
        next_dist_fn: Callable[[tuple[int, ...]], np.ndarray] | None = None,
        tau: float | None = None,
        horizon: int | None = None,
        supercritical_counts: Sequence[int] | None = None,
        mcts_result: Any = None,
        fork_candidates: Sequence[Any] | None = None,
        evidence_by_branch: Mapping[str, Sequence[str]] | None = None,
        verified_branch_ids: Sequence[str] | set[str] | frozenset[str] | None = None,
        reversible_by_branch: Mapping[str, bool] | None = None,
        tradeoff_by_branch: Mapping[str, str] | None = None,
        quorum_disagreement_dk: float | None = None,
        quorum_result: Any = None,
        option_shift: OptionShift | None = None,
        high_impact: bool = False,
        blackboard: Any = None,
        record_to_blackboard: bool = False,
        propose_blackboard_action: bool = False,
        context_summary: str = "",
    ) -> ForkPointReport:
        """Evaluate candidate paths and signals to detect a genuine high-leverage fork point."""
        resolved_fork_candidates = fork_candidates
        if resolved_fork_candidates is None and mcts_result is not None:
            resolved_fork_candidates = (
                mcts_result.get("fork_candidates")
                if isinstance(mcts_result, Mapping)
                else getattr(mcts_result, "fork_candidates", None)
            )

        if options is None:
            if resolved_fork_candidates:
                candidate_options: Sequence[VerifiedPathOption] = self.options_from_fork_candidates(
                    resolved_fork_candidates,
                    evidence_by_branch=evidence_by_branch,
                    verified_branch_ids=verified_branch_ids,
                    reversible_by_branch=reversible_by_branch,
                    tradeoff_by_branch=tradeoff_by_branch,
                )
            else:
                candidate_options = ()
        else:
            candidate_options = options

        verified_options, filtered_out = self.filter_verified_options(
            candidate_options, blackboard=blackboard
        )
        counts_tuple, supercritical = self._resolve_supercritical_counts(
            next_dist_fn=next_dist_fn,
            tau=tau,
            horizon=horizon,
            supercritical_counts=supercritical_counts,
            mcts_result=mcts_result,
            fork_candidates=resolved_fork_candidates,
        )
        dk_val = self._resolve_dk(quorum_disagreement_dk, quorum_result)
        high_dk = dk_val is not None and dk_val >= self.dk_threshold
        shift_narrowed = self._is_option_shift_narrowed(option_shift)
        irreversible_present = any(not opt.reversible for opt in verified_options)
        irreversible_boundary = bool(high_impact) or irreversible_present

        triggers: list[str] = []
        if supercritical:
            triggers.append("supercritical_multihorizon_branching")
        if high_dk:
            triggers.append("high_quorum_disagreement_dk")
        if shift_narrowed:
            triggers.append("option_shift_narrowing")
        if irreversible_boundary:
            triggers.append("irreversible_high_impact_boundary")

        div_score, is_divergent = self.compute_divergence(verified_options)

        suppressed_reason: str | None = None
        if len(verified_options) < 2:
            fork_detected = False
            suppressed_reason = "fewer_than_two_verified_paths"
        elif not is_divergent:
            fork_detected = False
            suppressed_reason = "verified_paths_not_significantly_divergent"
        elif not triggers:
            fork_detected = False
            suppressed_reason = "no_fork_trigger_active"
        else:
            fork_detected = True

        clean_context = _clean_text(context_summary, "context_summary", allow_empty=True, max_len=512)
        if fork_detected:
            surfaced = verified_options
            prompt = self._format_human_prompt(
                verified_options=surfaced,
                triggers=triggers,
                supercritical_counts=counts_tuple,
                quorum_disagreement_dk=dk_val,
                option_shift_narrowed=shift_narrowed,
                irreversible_boundary=irreversible_boundary,
                context_summary=clean_context,
            )
        else:
            surfaced = ()
            prompt = None

        const_meta = bridge_constitutional_metadata()
        notice = CONSTITUTIONAL_NOTICE_TEXT
        if irreversible_present and not fork_detected:
            notice = (
                f"{CONSTITUTIONAL_NOTICE_TEXT} Note: the remaining verified path is marked "
                "irreversible; human review is required before execution."
            )

        report = ForkPointReport(
            fork_detected=fork_detected,
            triggers=tuple(triggers),
            supercritical_counts=counts_tuple,
            quorum_disagreement_dk=dk_val,
            option_shift_narrowed=shift_narrowed,
            divergent_options=surfaced,
            prompt_for_human=prompt,
            constitutional_notice=notice,
            filtered_out_options=filtered_out,
            divergence_score=div_score,
            irreversible_boundary_triggered=irreversible_boundary,
            suppressed_reason=suppressed_reason,
            interaction_spec=None,
            constitutional=const_meta,
        )

        spec = self.build_interaction_spec(report)
        if spec is not None:
            report = replace(report, interaction_spec=spec.model_dump())

        gem_alert = self.build_gem_form_alert(report)
        if gem_alert is not None:
            report = replace(report, gem_form_alert=gem_alert)

        if (record_to_blackboard or propose_blackboard_action) and blackboard is not None:
            bb_records = self.record_fork_to_blackboard(
                blackboard,
                report,
                propose_action=bool(propose_blackboard_action),
                reversible=True,
                context_summary=clean_context,
            )
            report = replace(report, blackboard_records=bb_records)

        return report

    def build_gem_form_alert(
        self,
        report: ForkPointReport,
        *,
        endian: str = "<",
    ) -> dict[str, Any] | None:
        """Render a calm GEM AES Function 52 ``form_alert`` + ``.RSC`` payload for active forks."""
        if not report.fork_detected or not report.divergent_options:
            return None
        from .gem_aes_vdi import GEM_AES_VDI_CONTRACT, build_form_alert

        opt_a = report.divergent_options[0].path_id[:28]
        opt_b = (
            report.divergent_options[1].path_id[:28]
            if len(report.divergent_options) > 1
            else "alternative"
        )
        lines = [
            "Verified fork needs human review",
            f"A: {opt_a}",
            f"B: {opt_b}",
            f"Divergence={report.divergence_score:.2f} ext=0",
        ]
        buttons = ["Select Path", "Stop/Reject", "Reversible"]
        alert = build_form_alert(
            icon_id=2,
            lines=lines,
            buttons=buttons,
            default_btn=1,
            title="ZOE_FORK_GATE",
            endian=endian,
        )
        payload = alert.to_dict()
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "icon_id": alert.icon_id,
            "form_alert_string": alert.form_alert_string,
            "buttons": list(alert.buttons),
            "lines": list(alert.lines),
            "object_tree": dict(alert.object_tree_summary),
            "rsc_sha256": payload["rsc_sha256"],
            "rsc_bytes_len": payload["rsc_bytes_len"],
            "external_actions": 0,
            "visual_evidence_only": True,
            "constitutional": dict(payload["constitutional"]),
        }

    def run(
        self, options: Sequence[VerifiedPathOption] | None = None, **kwargs: Any
    ) -> ForkPointReport:
        """Alias for :meth:`detect` matching shared-reasoning engine conventions."""
        return self.detect(options, **kwargs)

    def evaluate(
        self, options: Sequence[VerifiedPathOption] | None = None, **kwargs: Any
    ) -> ForkPointReport:
        """Alias for :meth:`detect`."""
        return self.detect(options, **kwargs)


__all__ = [
    "CONSTITUTIONAL_NOTICE_TEXT",
    "DEFAULT_DK_THRESHOLD",
    "DEFAULT_DIVERGENCE_THRESHOLD",
    "DEFAULT_HORIZON",
    "DEFAULT_OPTION_SHIFT_DROP",
    "DEFAULT_TAU",
    "HUMAN_STEERING_CONTRACT",
    "INTERACTION_MODE",
    "REQUEST_REVERSIBLE_OPTION_ID",
    "REJECT_ALL_OPTION_ID",
    "STOP_OPTION_ID",
    "UNVERIFIED_STATUSES",
    "VERIFIED_STATUSES",
    "ForkPointReport",
    "HumanSteeringDetector",
    "VerifiedPathOption",
]

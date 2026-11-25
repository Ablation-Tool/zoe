"""Architecture #5: System-2 -> System-1 Distillation (`distillation.py`).

Bridges high-uncertainty System-2 deliberation (e.g. Antigravity / Zoe search)
into Zoe's fast, deterministic, zero-cloud-token System-1 stores:
  1. Procedural Skills -> `ZoeUnifiedMemory.register_skill(...)` validated and
     compiled strictly through `GuardedFunctionASTSandbox` (no unrestricted eval/exec).
  2. Semantic Facts -> `ZoeUnifiedMemory.record_fact(..., evidence_approved=True)`
     inside Zoe's SHA-256 hash-chained, contradiction-aware semantic store.
  3. Conversational / Routing Rules -> `zoe_eliza.ElizaRule` registered inside
     `DistilledRuleRegistry` with pre-compiled regex patterns and Weizenbaum
     reflection/reassembly for sub-millisecond Gear-1 System-1 lookup.
  4. Optional `google.antigravity.InlineSkill` export descriptor (`name`,
     `description`, `content` / `instructions`).

Enforces `docs/CONSTITUTION.md` Article III (`measurement != evidence !=
belief update != action`):
  - Only high-uncertainty System-2 traces (`initial_uncertainty_a_tau >=
    min_uncertainty_a_tau`, `verifier_passed=True`, non-sampled-only, with
    valid `evidence_id` and non-empty `provenance`) may be distilled.
  - Supports pre-commit & post-commit regression verification and bit-exact
    atomic `rollback(token)` restoring `ZoeUnifiedMemory` and `DistilledRuleRegistry`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any, Literal

from google.antigravity import InlineSkill  # type: ignore[import-untyped]
import numpy as np

from .._utils import sha256_json_utf8
from ..actuation import timestamp
from ..l4_multi_module import GuardedFunctionASTSandbox, UnsafeFunctionASTError
from ..l5_memory import ZoeUnifiedMemory
from ..metacognition import EvidenceSource, Provenance
from ..stem_layering import constitutional_flags
from ..zoe_eliza import (
    ElizaRule,
    _expand_synonyms,
    normalize_input,
    reflect_phrase,
)
from .alpha_evolve import AlphaEvolveResult, CandidateProgram
from .blackboard import EpistemicBlackboard, EvidenceRecord, FirewallViolationError
from .sdk_bridge import ATTRIBUTION_TEXT, ZoeAntigravityBridge

DISTILLATION_CONTRACT = "zoe-shared-reasoning-distillation/v1"
VALID_ARTIFACT_KINDS: tuple[str, ...] = (
    "procedural_skill",
    "eliza_rule",
    "semantic_fact",
)

_INVALID_EVIDENCE_TOKENS = frozenset(
    {"", "none", "null", "unknown", "unverified", "pending", "placeholder", "n/a", "na"}
)
_INVALID_PROVENANCE_TOKENS = frozenset(
    {"", "none", "null", "unknown", "unverified", "sampled_only", "guess", "ungrounded"}
)


def distillation_constitutional_metadata(*, cloud_tokens_used: int = 0) -> dict[str, Any]:
    """Return canonical CONSTITUTION.md metadata for distillation records."""
    flags = constitutional_flags(cloud_tokens_used=cloud_tokens_used)
    flags["attribution"] = ATTRIBUTION_TEXT
    return flags


class DistillationRejectedError(FirewallViolationError, ValueError):
    """Raised when a System-2 trace fails CONSTITUTION.md Art. III distillation gates."""


class DistillationRegressionError(DistillationRejectedError):
    """Raised when a distilled artifact fails verification or regresses System-1 accuracy."""

    def __init__(
        self,
        message: str,
        *,
        report: Mapping[str, Any] | None = None,
        rollback_performed: bool = True,
    ) -> None:
        super().__init__(message)
        self.report: dict[str, Any] = dict(report or {})
        self.rollback_performed = rollback_performed


class UnknownRollbackTokenError(ValueError):
    """Raised when `rollback(token)` is called with an unknown or already-reverted token."""


class DistilledInlineSkill(InlineSkill):
    """`google.antigravity.InlineSkill` descriptor with an `.instructions` alias."""

    @property
    def instructions(self) -> str:
        """Alias for `InlineSkill.content` matching Antigravity instruction terminology."""
        return self.content


def _normalize_provenance_input(
    provenance: Provenance | EvidenceSource | Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    """Validate and normalize trace provenance; reject empty or unverified provenance."""
    if provenance is None:
        raise DistillationRejectedError(
            "CONSTITUTION.md Art. III: provenance is required for distillation"
        )
    if isinstance(provenance, Provenance):
        if not provenance.sources:
            raise DistillationRejectedError(
                "CONSTITUTION.md Art. III: Provenance must contain at least one EvidenceSource"
            )
        doc = provenance.document()
        doc["kind"] = "kloster_provenance"
        return doc
    if isinstance(provenance, EvidenceSource):
        doc = Provenance(
            sources=(provenance,),
            transformations=("system2_verified_distillation",),
        ).document()
        doc["kind"] = "evidence_source"
        return doc
    if isinstance(provenance, str):
        cleaned = " ".join(provenance.split()).strip()
        if cleaned.lower() in _INVALID_PROVENANCE_TOKENS:
            raise DistillationRejectedError(
                f"CONSTITUTION.md Art. III: invalid or unverified provenance {provenance!r}"
            )
        return {"kind": "verified_trace", "identifier": cleaned}
    if isinstance(provenance, Mapping):
        if not provenance:
            raise DistillationRejectedError(
                "CONSTITUTION.md Art. III: provenance mapping must be non-empty"
            )
        raw_dict = dict(provenance)
        if raw_dict.get("sampled_only") is True and not raw_dict.get("independent_verifier"):
            raise DistillationRejectedError(
                "CONSTITUTION.md Art. III.3: sampled-only provenance cannot be distilled"
            )
        if raw_dict.get("verified") is False or raw_dict.get("unverified") is True:
            raise DistillationRejectedError(
                "CONSTITUTION.md Art. III: provenance marks trace as unverified"
            )
        return deepcopy(raw_dict)
    raise DistillationRejectedError(
        f"CONSTITUTION.md Art. III: unsupported provenance type {type(provenance).__name__}"
    )


def _provenance_label(prov_doc: Mapping[str, Any]) -> str:
    """Produce a concise canonical provenance label for `ZoeUnifiedMemory`."""
    if isinstance(prov_doc.get("identifier"), str) and prov_doc["identifier"].strip():
        return str(prov_doc["identifier"]).strip()
    sources = prov_doc.get("sources")
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)) and sources:
        first = sources[0]
        if isinstance(first, Mapping) and first.get("identifier"):
            return f"{first.get('kind', 'source')}:{first['identifier']}"
    return sha256_json_utf8(dict(prov_doc))[:24]


@dataclass(frozen=True)
class System2Trace:
    """Verified high-uncertainty System-2 trace candidate for System-1 distillation."""

    task_prompt: str
    initial_uncertainty_a_tau: float | int
    solution_code_or_rule: Any
    verifier_passed: bool
    evidence_id: str | EvidenceRecord
    provenance: Provenance | EvidenceSource | Mapping[str, Any] | str
    artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"] | None = None
    trace_id: str = ""
    source_agent: str = "antigravity_system2"
    sampled_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        prov_serialized: Any
        if isinstance(self.provenance, (Provenance, EvidenceSource)):
            prov_serialized = self.provenance.document()
        elif isinstance(self.provenance, Mapping):
            prov_serialized = deepcopy(dict(self.provenance))
        else:
            prov_serialized = str(self.provenance)

        sol_serialized: Any
        if isinstance(self.solution_code_or_rule, ElizaRule):
            sol_serialized = {
                "rule_id": self.solution_code_or_rule.rule_id,
                "keywords": list(self.solution_code_or_rule.keywords),
                "rank": self.solution_code_or_rule.rank,
                "decompositions": [
                    [pat, list(resps)] for pat, resps in self.solution_code_or_rule.decompositions
                ],
                "push_memory": self.solution_code_or_rule.push_memory,
            }
        elif isinstance(self.solution_code_or_rule, (AlphaEvolveResult, CandidateProgram)):
            sol_serialized = self.solution_code_or_rule.to_dict()
        else:
            sol_serialized = deepcopy(self.solution_code_or_rule)

        ev_serialized = (
            self.evidence_id.record_id
            if isinstance(self.evidence_id, EvidenceRecord)
            else str(self.evidence_id)
        )

        return {
            "trace_id": self.trace_id,
            "task_prompt": self.task_prompt,
            "initial_uncertainty_a_tau": float(self.initial_uncertainty_a_tau),
            "solution_code_or_rule": sol_serialized,
            "verifier_passed": self.verifier_passed,
            "evidence_id": ev_serialized,
            "provenance": prov_serialized,
            "artifact_kind": self.artifact_kind,
            "source_agent": self.source_agent,
            "sampled_only": self.sampled_only,
            "metadata": deepcopy(self.metadata),
        }


@dataclass(frozen=True)
class DistilledArtifact:
    """Record of a System-2 solution distilled into Zoe's System-1 stores."""

    artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"]
    target_name: str
    verification_cases: tuple[dict[str, Any], ...]
    rollback_token: str
    artifact_id: str = ""
    evidence_id: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    initial_uncertainty_a_tau: float = 0.0
    memory_sha256: str = ""
    chain_head: str = ""
    artifact_sha256: str = ""
    inline_skill: DistilledInlineSkill | None = None
    regression_passed: bool = True
    regression_summary: dict[str, Any] = field(default_factory=dict)
    rolled_back: bool = False
    created_utc: str = field(default_factory=timestamp)
    constitutional: dict[str, Any] = field(default_factory=distillation_constitutional_metadata)
    blackboard_belief_id: str | None = None
    lineage: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": DISTILLATION_CONTRACT,
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "target_name": self.target_name,
            "verification_cases": [deepcopy(c) for c in self.verification_cases],
            "rollback_token": self.rollback_token,
            "evidence_id": self.evidence_id,
            "provenance": deepcopy(self.provenance),
            "initial_uncertainty_a_tau": self.initial_uncertainty_a_tau,
            "memory_sha256": self.memory_sha256,
            "chain_head": self.chain_head,
            "artifact_sha256": self.artifact_sha256,
            "inline_skill": self.inline_skill.model_dump() if self.inline_skill is not None else None,
            "regression_passed": self.regression_passed,
            "regression_summary": deepcopy(self.regression_summary),
            "rolled_back": self.rolled_back,
            "created_utc": self.created_utc,
            "constitutional": deepcopy(self.constitutional),
            "blackboard_belief_id": self.blackboard_belief_id,
            "lineage": list(self.lineage),
        }


@dataclass(frozen=True)
class _CompiledDecomp:
    raw_pattern: str
    regex: re.Pattern[str]
    templates: tuple[str, ...]


@dataclass(frozen=True)
class _CompiledRuleEntry:
    rule: ElizaRule
    keyword_patterns: tuple[tuple[str, re.Pattern[str] | None, str | None], ...]
    decompositions: tuple[_CompiledDecomp, ...]


class DistilledRuleRegistry:
    """Fast Gear-1 System-1 registry of distilled `zoe_eliza.ElizaRule` objects.

    Pre-compiles keyword & decomposition regexes and runs deterministic
    Weizenbaum reflection/reassembly in sub-millisecond time with zero cloud tokens.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _CompiledRuleEntry] = {}
        self._cursors: dict[str, int] = {}
        self._weizenbaum_stack: list[str] = []

    @staticmethod
    def _compile_rule(rule: ElizaRule) -> _CompiledRuleEntry:
        if not isinstance(rule, ElizaRule):
            raise TypeError(f"expected ElizaRule, got {type(rule).__name__}")
        rule_id = str(rule.rule_id).strip()
        if not rule_id:
            raise ValueError("ElizaRule.rule_id must be non-empty")
        if not rule.keywords:
            raise ValueError(f"ElizaRule {rule_id!r} requires at least one keyword")
        if not rule.decompositions:
            raise ValueError(f"ElizaRule {rule_id!r} requires at least one decomposition")

        kw_compiled: list[tuple[str, re.Pattern[str] | None, str | None]] = []
        for kw in rule.keywords:
            kw_str = str(kw).strip()
            if not kw_str:
                raise ValueError(f"ElizaRule {rule_id!r} contains an empty keyword")
            if kw_str.startswith("@"):
                expanded = _expand_synonyms(kw_str)
                try:
                    kw_pat = re.compile(rf"\b{expanded}\b", re.IGNORECASE)
                except re.error as err:
                    raise ValueError(
                        f"ElizaRule {rule_id!r} has invalid keyword regex {kw_str!r}: {err}"
                    ) from err
                kw_compiled.append((kw_str, kw_pat, None))
            elif " " in kw_str:
                kw_compiled.append((kw_str, None, kw_str.lower()))
            else:
                kw_compiled.append(
                    (kw_str, re.compile(rf"(?<!\w){re.escape(kw_str)}(?!\w)", re.IGNORECASE), None)
                )

        decomps: list[_CompiledDecomp] = []
        for pat, templates in rule.decompositions:
            pat_str = str(pat)
            if not templates:
                raise ValueError(
                    f"ElizaRule {rule_id!r} decomposition {pat_str!r} must have >=1 response template"
                )
            try:
                regex = re.compile(_expand_synonyms(pat_str), re.IGNORECASE)
            except re.error as err:
                raise ValueError(
                    f"ElizaRule {rule_id!r} has invalid regex {pat_str!r}: {err}"
                ) from err
            decomps.append(
                _CompiledDecomp(
                    raw_pattern=pat_str,
                    regex=regex,
                    templates=tuple(str(t) for t in templates),
                )
            )

        return _CompiledRuleEntry(
            rule=rule,
            keyword_patterns=tuple(kw_compiled),
            decompositions=tuple(decomps),
        )

    def register_rule(self, rule: ElizaRule) -> dict[str, Any]:
        """Compile and register (or replace) a distilled `ElizaRule`."""
        entry = self._compile_rule(rule)
        self._entries[entry.rule.rule_id] = entry
        return {
            "rule_id": entry.rule.rule_id,
            "rank": entry.rule.rank,
            "keywords": list(entry.rule.keywords),
            "decomposition_count": len(entry.decompositions),
            "rule_sha256": sha256_json_utf8(
                {
                    "rule_id": entry.rule.rule_id,
                    "rank": entry.rule.rank,
                    "keywords": list(entry.rule.keywords),
                    "decompositions": [[d.raw_pattern, list(d.templates)] for d in entry.decompositions],
                }
            ),
        }

    def unregister_rule(self, rule_id: str) -> bool:
        removed = self._entries.pop(rule_id, None) is not None
        prefix = f"{rule_id}:"
        for key in [k for k in self._cursors if k.startswith(prefix)]:
            self._cursors.pop(key, None)
        return removed

    def has_rule(self, rule_id: str) -> bool:
        return rule_id in self._entries

    def get_rule(self, rule_id: str) -> ElizaRule:
        return self._entries[rule_id].rule

    def list_rules(self) -> tuple[ElizaRule, ...]:
        ordered = sorted(
            self._entries.values(),
            key=lambda e: (-e.rule.rank, e.rule.rule_id),
        )
        return tuple(e.rule for e in ordered)

    def match(self, user_text: str, *, advance_cursor: bool = True) -> dict[str, Any] | None:
        """Execute fast Gear-1 System-1 lookup over distilled rules."""
        raw = str(user_text or "").strip()
        if not raw or not self._entries:
            return None
        normalized = normalize_input(raw)

        candidates: list[tuple[int, _CompiledRuleEntry, str]] = []
        for entry in self._entries.values():
            for kw_raw, kw_regex, phrase in entry.keyword_patterns:
                if kw_regex is not None:
                    if kw_regex.search(normalized):
                        candidates.append((entry.rule.rank, entry, kw_raw))
                        break
                elif phrase is not None and phrase in normalized:
                    candidates.append((entry.rule.rank, entry, kw_raw))
                    break

        if not candidates:
            return None

        candidates.sort(key=lambda item: (-item[0], item[1].rule.rule_id))

        for _rank, entry, matched_kw in candidates:
            for decomp in entry.decompositions:
                m = decomp.regex.match(normalized)
                if m is None:
                    continue
                groups = tuple(g or "" for g in m.groups())
                key = f"{entry.rule.rule_id}:{decomp.raw_pattern}"
                idx = self._cursors.get(key, 0)
                chosen = decomp.templates[idx % len(decomp.templates)]
                if advance_cursor:
                    self._cursors[key] = idx + 1

                all_swaps: list[str] = []
                reflected_groups: list[str] = []
                for grp in groups:
                    ref, swaps = reflect_phrase(grp)
                    all_swaps.extend(swaps)
                    reflected_groups.append(ref or grp.strip())

                def _replace_placeholder(match: re.Match[str]) -> str:
                    g_idx = int(match.group(1))
                    if 1 <= g_idx <= len(reflected_groups):
                        return reflected_groups[g_idx - 1] or "that"
                    return match.group(0)

                reply = re.sub(r"\{(\d+)\}", _replace_placeholder, chosen)

                if advance_cursor and entry.rule.push_memory and reflected_groups and reflected_groups[0]:
                    cue = f"your {reflected_groups[0]}"
                    if cue not in self._weizenbaum_stack:
                        self._weizenbaum_stack.append(cue)
                        self._weizenbaum_stack = self._weizenbaum_stack[-16:]

                return {
                    "matched": True,
                    "gear": "gear1_distilled",
                    "cloud_tokens_used": 0,
                    "rule_id": entry.rule.rule_id,
                    "keyword": matched_kw,
                    "rank": entry.rule.rank,
                    "pattern": decomp.raw_pattern,
                    "groups": list(groups),
                    "reflections": all_swaps,
                    "reply": reply,
                    "normalized": normalized,
                }
        return None

    def lookup(self, user_text: str, *, advance_cursor: bool = True) -> str | None:
        """Return just the fast Gear-1 reply string if a distilled rule matches."""
        res = self.match(user_text, advance_cursor=advance_cursor)
        return str(res["reply"]) if res is not None else None

    def snapshot(self) -> dict[str, Any]:
        return {
            "rules": [
                {
                    "rule_id": e.rule.rule_id,
                    "keywords": list(e.rule.keywords),
                    "rank": e.rule.rank,
                    "decompositions": [
                        [pat, list(resps)] for pat, resps in e.rule.decompositions
                    ],
                    "push_memory": e.rule.push_memory,
                }
                for e in self._entries.values()
            ],
            "cursors": dict(self._cursors),
            "weizenbaum_stack": list(self._weizenbaum_stack),
        }

    def rollback(self, prior_snapshot: Mapping[str, Any]) -> None:
        self._entries.clear()
        for row in prior_snapshot.get("rules", ()):
            decomps = tuple(
                (str(pat), tuple(str(r) for r in resps))
                for pat, resps in row["decompositions"]
            )
            rule = ElizaRule(
                rule_id=str(row["rule_id"]),
                keywords=tuple(str(k) for k in row["keywords"]),
                rank=int(row["rank"]),
                decompositions=decomps,
                push_memory=bool(row.get("push_memory", False)),
            )
            self.register_rule(rule)
        self._cursors = {str(k): int(v) for k, v in prior_snapshot.get("cursors", {}).items()}
        self._weizenbaum_stack = [str(x) for x in prior_snapshot.get("weizenbaum_stack", [])]

    def summary(self) -> dict[str, Any]:
        return {
            "rule_count": len(self._entries),
            "rule_ids": [e.rule.rule_id for e in sorted(self._entries.values(), key=lambda x: (-x.rule.rank, x.rule.rule_id))],
            "weizenbaum_stack_depth": len(self._weizenbaum_stack),
        }


@dataclass
class _RollbackRecord:
    seq: int
    token: str
    artifact_id: str
    target_name: str
    memory_snapshot: dict[str, Any]
    registry_snapshot: dict[str, Any]
    active_artifacts_snapshot: dict[str, DistilledArtifact]
    inline_skills_snapshot: dict[str, DistilledInlineSkill]
    fact_meta_snapshot: dict[str, dict[str, Any]]
    blackboard_snapshot: dict[str, Any] | None = None
    rolled_back: bool = False


class System2To1Distiller:
    """Distills verified high-uncertainty System-2 traces into Zoe System-1 stores."""

    def __init__(
        self,
        *,
        memory: ZoeUnifiedMemory | None = None,
        rule_registry: DistilledRuleRegistry | None = None,
        blackboard: EpistemicBlackboard | None = None,
        bridge: ZoeAntigravityBridge | None = None,
        min_uncertainty_a_tau: float = 2.0,
        state_dir: str | Path | None = None,
        require_blackboard_evidence: bool = True,
    ) -> None:
        if isinstance(min_uncertainty_a_tau, bool) or not isinstance(
            min_uncertainty_a_tau, (int, float)
        ):
            raise ValueError("min_uncertainty_a_tau must be numeric")
        if not math.isfinite(float(min_uncertainty_a_tau)) or float(min_uncertainty_a_tau) <= 0.0:
            raise ValueError("min_uncertainty_a_tau must be finite and > 0")

        self.memory: ZoeUnifiedMemory = memory if memory is not None else ZoeUnifiedMemory(state_dir)
        self.rule_registry: DistilledRuleRegistry = (
            rule_registry if rule_registry is not None else DistilledRuleRegistry()
        )
        self.blackboard: EpistemicBlackboard | None = blackboard
        self.bridge: ZoeAntigravityBridge | None = bridge
        self.min_uncertainty_a_tau: float = float(min_uncertainty_a_tau)
        self._require_blackboard_evidence: bool = bool(require_blackboard_evidence)

        self._seq: int = 0
        self._active_artifacts: dict[str, DistilledArtifact] = {}
        self._history: list[DistilledArtifact] = []
        self._inline_skills: dict[str, DistilledInlineSkill] = {}
        self._fact_meta: dict[str, dict[str, Any]] = {}
        self._rollback_ledger: dict[str, _RollbackRecord] = {}
        self._rejections: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Gate Validation (CONSTITUTION.md Art. III)
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_evidence_id(evidence_id: str | EvidenceRecord) -> str:
        if isinstance(evidence_id, EvidenceRecord):
            return str(evidence_id.record_id).strip()
        return str(evidence_id or "").strip()

    def _record_rejection(self, trace: System2Trace, reason: str) -> None:
        self._rejections.append(
            {
                "timestamp": timestamp(),
                "trace_id": trace.trace_id,
                "task_prompt": trace.task_prompt[:160],
                "evidence_id": self._normalize_evidence_id(trace.evidence_id),
                "verifier_passed": trace.verifier_passed,
                "initial_uncertainty_a_tau": trace.initial_uncertainty_a_tau,
                "reason": reason,
            }
        )

    def _validate_trace_gate(self, trace: System2Trace) -> tuple[dict[str, Any], str]:
        if not isinstance(trace, System2Trace):
            raise DistillationRejectedError(
                f"expected System2Trace, got {type(trace).__name__}"
            )

        prompt = str(trace.task_prompt or "").strip()
        if not prompt:
            reason = "CONSTITUTION.md Art. III: task_prompt must be non-empty"
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)

        if trace.sampled_only:
            reason = (
                "CONSTITUTION.md Art. III.3: sampled-only outcomes cannot be distilled "
                "without independent verification"
            )
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)

        if trace.verifier_passed is not True:
            reason = (
                "CONSTITUTION.md Art. III: cannot distill unverified System-2 trace "
                "(verifier_passed must be True)"
            )
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)

        a_tau = trace.initial_uncertainty_a_tau
        if isinstance(a_tau, bool) or not isinstance(a_tau, (int, float)) or not math.isfinite(float(a_tau)):
            reason = "initial_uncertainty_a_tau must be a finite number"
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)
        if float(a_tau) < self.min_uncertainty_a_tau:
            reason = (
                f"System-2 distillation requires high uncertainty A_tau >= "
                f"{self.min_uncertainty_a_tau}, got {float(a_tau)}"
            )
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)

        ev_id = self._normalize_evidence_id(trace.evidence_id)
        if ev_id.lower() in _INVALID_EVIDENCE_TOKENS:
            reason = (
                "CONSTITUTION.md Art. III: valid non-empty evidence_id is required "
                f"(got {trace.evidence_id!r})"
            )
            self._record_rejection(trace, reason)
            raise DistillationRejectedError(reason)

        try:
            prov_doc = _normalize_provenance_input(trace.provenance)
        except DistillationRejectedError as err:
            self._record_rejection(trace, str(err))
            raise

        if self.blackboard is not None and self._require_blackboard_evidence:
            try:
                ev_rec = self.blackboard.get_evidence(ev_id)
            except KeyError as err:
                reason = (
                    f"CONSTITUTION.md Art. III: evidence_id {ev_id!r} not found in "
                    "attached EpistemicBlackboard"
                )
                self._record_rejection(trace, reason)
                raise DistillationRejectedError(reason) from err
            if not (ev_rec.passed and ev_rec.approved) or ev_rec.negative_result:
                reason = (
                    f"CONSTITUTION.md Art. III: EpistemicBlackboard evidence {ev_id!r} "
                    "is not approved/passing"
                )
                self._record_rejection(trace, reason)
                raise DistillationRejectedError(reason)

        return prov_doc, ev_id

    # ------------------------------------------------------------------
    # Payload Parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _infer_artifact_kind(
        trace: System2Trace,
        explicit_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"] | None,
    ) -> Literal["procedural_skill", "eliza_rule", "semantic_fact"]:
        if explicit_kind is not None and trace.artifact_kind is not None:
            if explicit_kind != trace.artifact_kind:
                raise ValueError(
                    f"conflicting artifact_kind {explicit_kind!r} vs trace.artifact_kind {trace.artifact_kind!r}"
                )
        chosen = explicit_kind or trace.artifact_kind
        if chosen is not None:
            if chosen not in VALID_ARTIFACT_KINDS:
                raise ValueError(
                    f"invalid artifact_kind {chosen!r}; expected one of {VALID_ARTIFACT_KINDS}"
                )
            return chosen

        sol = trace.solution_code_or_rule
        if isinstance(sol, (AlphaEvolveResult, CandidateProgram)):
            return "procedural_skill"
        if isinstance(sol, ElizaRule):
            return "eliza_rule"
        if isinstance(sol, str) and re.search(r"^\s*def\s+[a-zA-Z_]", sol, re.MULTILINE):
            return "procedural_skill"
        if isinstance(sol, Mapping):
            if "source" in sol or "code" in sol:
                return "procedural_skill"
            if "decompositions" in sol or "pattern" in sol or "rule_id" in sol:
                return "eliza_rule"
            if "subject" in sol and "relation" in sol:
                return "semantic_fact"
        if isinstance(sol, (tuple, list)) and len(sol) == 3:
            return "semantic_fact"
        raise DistillationRejectedError(
            "Unable to infer artifact_kind from solution_code_or_rule; pass artifact_kind explicitly"
        )

    @staticmethod
    def _parse_procedural_payload(
        sol: Any,
        *,
        target_name: str | None,
        task_prompt: str,
    ) -> tuple[str, str, tuple[str, ...], str]:
        arg_names: tuple[str, ...] | None = None
        description = f"Distilled System-2 skill for: {task_prompt[:120]}"
        expected_name = target_name

        if isinstance(sol, AlphaEvolveResult):
            cand = sol.best_program
            if cand.total_tests <= 0 or cand.passed_tests != cand.total_tests:
                raise DistillationRejectedError(
                    "CONSTITUTION.md Art. III: AlphaEvolveResult best_program did not pass "
                    f"all deterministic tests ({cand.passed_tests}/{cand.total_tests})"
                )
            source = cand.code.strip()
            if expected_name is None:
                expected_name = cand.function_name
            description = (
                f"AlphaEvolve winning skill `{cand.id}` (gen={cand.generation}, "
                f"score={cand.score}, tests={cand.passed_tests}/{cand.total_tests})"
            )
        elif isinstance(sol, CandidateProgram):
            if sol.total_tests <= 0 or sol.passed_tests != sol.total_tests:
                raise DistillationRejectedError(
                    "CONSTITUTION.md Art. III: CandidateProgram did not pass "
                    f"all deterministic tests ({sol.passed_tests}/{sol.total_tests})"
                )
            source = sol.code.strip()
            if expected_name is None:
                expected_name = sol.function_name
            description = (
                f"AlphaEvolve candidate `{sol.id}` (gen={sol.generation}, "
                f"score={sol.score}, tests={sol.passed_tests}/{sol.total_tests})"
            )
        elif isinstance(sol, str):
            source = sol.strip()
        elif isinstance(sol, Mapping):
            raw_src = sol.get("source") or sol.get("code")
            if not isinstance(raw_src, str) or not raw_src.strip():
                raise DistillationRejectedError(
                    "procedural_skill mapping requires non-empty 'source' Python def code"
                )
            source = raw_src.strip()
            if expected_name is None and sol.get("name"):
                expected_name = str(sol["name"]).strip()
            if "arg_names" in sol and sol["arg_names"] is not None:
                raw_arg_names = sol["arg_names"]
                if (
                    isinstance(raw_arg_names, (str, bytes, bytearray))
                    or not isinstance(raw_arg_names, Sequence)
                ):
                    raise DistillationRejectedError(
                        "procedural_skill 'arg_names' must be a sequence of strings, "
                        f"got {type(raw_arg_names).__name__}"
                    )
                parsed_args: list[str] = []
                for a in raw_arg_names:
                    if not isinstance(a, str) or not a.strip():
                        raise DistillationRejectedError(
                            f"procedural_skill 'arg_names' entries must be non-empty strings, got {a!r}"
                        )
                    parsed_args.append(a)
                arg_names = tuple(parsed_args)
            if sol.get("description"):
                description = str(sol["description"]).strip()
        else:
            raise DistillationRejectedError(
                f"procedural_skill requires Python def source string or mapping, got {type(sol).__name__}"
            )

        fn_node = GuardedFunctionASTSandbox.validate(
            source,
            expected_name=expected_name,
            expected_args=arg_names,
        )
        final_name = fn_node.name
        final_args = tuple(a.arg for a in fn_node.args.args)
        return final_name, source, final_args, description

    @staticmethod
    def _parse_eliza_payload(
        sol: Any,
        *,
        target_name: str | None,
    ) -> ElizaRule:
        if isinstance(sol, ElizaRule):
            if target_name is not None and sol.rule_id != target_name:
                return ElizaRule(
                    rule_id=target_name,
                    keywords=sol.keywords,
                    rank=sol.rank,
                    decompositions=sol.decompositions,
                    push_memory=sol.push_memory,
                )
            return sol

        if not isinstance(sol, Mapping):
            raise DistillationRejectedError(
                f"eliza_rule requires ElizaRule or mapping, got {type(sol).__name__}"
            )

        rule_id = str(target_name or sol.get("rule_id") or sol.get("name") or "").strip()
        if not rule_id:
            raise DistillationRejectedError("eliza_rule requires a non-empty rule_id/target_name")

        raw_kws = sol.get("keywords")
        if (
            raw_kws is None
            or isinstance(raw_kws, (str, bytes, bytearray))
            or not isinstance(raw_kws, Sequence)
        ):
            raise DistillationRejectedError(
                "eliza_rule 'keywords' must be a non-empty sequence of strings"
            )
        if any(not isinstance(k, str) for k in raw_kws):
            raise DistillationRejectedError(
                "eliza_rule 'keywords' must contain only strings"
            )
        keywords = tuple(k.strip() for k in raw_kws if k.strip())
        if not keywords:
            raise DistillationRejectedError("eliza_rule requires at least one non-empty keyword")

        raw_rank = sol.get("rank", 10)
        if isinstance(raw_rank, bool) or not isinstance(raw_rank, int):
            raise DistillationRejectedError(
                f"eliza_rule 'rank' must be an int (got {type(raw_rank).__name__})"
            )
        rank = int(raw_rank)
        push_memory = bool(sol.get("push_memory", False))

        if "decompositions" in sol and sol["decompositions"] is not None:
            raw_decomps = sol["decompositions"]
            if isinstance(raw_decomps, (str, bytes, bytearray)) or not isinstance(
                raw_decomps, Sequence
            ):
                raise DistillationRejectedError(
                    "eliza_rule 'decompositions' must be a non-empty sequence of (pattern, responses) pairs"
                )
            decomps_list: list[tuple[str, tuple[str, ...]]] = []
            for item in raw_decomps:
                if (
                    isinstance(item, (str, bytes, bytearray))
                    or not isinstance(item, Sequence)
                    or len(item) != 2
                ):
                    raise DistillationRejectedError(
                        "each decomposition must be a (pattern, responses) pair"
                    )
                pat, resps = item[0], item[1]
                if not isinstance(pat, str) or not pat.strip():
                    raise DistillationRejectedError(
                        "each decomposition pattern must be a non-empty string"
                    )
                resp_tuple: tuple[str, ...]
                if isinstance(resps, str):
                    resp_tuple = (resps,)
                elif isinstance(resps, (bytes, bytearray)) or not isinstance(resps, Sequence):
                    raise DistillationRejectedError(
                        "decomposition responses must be a string or sequence of strings"
                    )
                else:
                    if any(not isinstance(r, str) for r in resps):
                        raise DistillationRejectedError(
                            "decomposition responses must contain only strings"
                        )
                    resp_tuple = tuple(resps)
                if not resp_tuple:
                    raise DistillationRejectedError(
                        "each decomposition must provide at least one response"
                    )
                decomps_list.append((pat, resp_tuple))
            if not decomps_list:
                raise DistillationRejectedError(
                    "eliza_rule 'decompositions' must not be empty"
                )
            decompositions = tuple(decomps_list)
        elif "pattern" in sol:
            raw_pat = sol["pattern"]
            if not isinstance(raw_pat, str) or not raw_pat.strip():
                raise DistillationRejectedError(
                    "eliza_rule 'pattern' must be a non-empty string"
                )
            pat = raw_pat
            if "responses" in sol and sol["responses"] is not None:
                raw_resps = sol["responses"]
                if isinstance(raw_resps, str):
                    resp_tuple = (raw_resps,)
                elif isinstance(raw_resps, (bytes, bytearray)) or not isinstance(
                    raw_resps, Sequence
                ):
                    raise DistillationRejectedError(
                        "eliza_rule 'responses' must be a string or sequence of strings"
                    )
                else:
                    if any(not isinstance(r, str) for r in raw_resps):
                        raise DistillationRejectedError(
                            "eliza_rule 'responses' must contain only strings"
                        )
                    resp_tuple = tuple(raw_resps)
                if not resp_tuple:
                    raise DistillationRejectedError(
                        "eliza_rule 'responses' must not be empty"
                    )
            elif "response" in sol and sol["response"] is not None:
                if not isinstance(sol["response"], str):
                    raise DistillationRejectedError("eliza_rule 'response' must be a string")
                resp_tuple = (sol["response"],)
            elif "template" in sol and sol["template"] is not None:
                if not isinstance(sol["template"], str):
                    raise DistillationRejectedError("eliza_rule 'template' must be a string")
                resp_tuple = (sol["template"],)
            else:
                raise DistillationRejectedError(
                    "eliza_rule with 'pattern' requires 'response', 'responses', or 'template'"
                )
            decompositions = ((pat, resp_tuple),)
        else:
            raise DistillationRejectedError(
                "eliza_rule mapping requires 'decompositions' or 'pattern'"
            )

        return ElizaRule(
            rule_id=rule_id,
            keywords=keywords,
            rank=rank,
            decompositions=decompositions,
            push_memory=push_memory,
        )

    @staticmethod
    def _parse_semantic_payload(
        sol: Any,
        *,
        target_name: str | None,
    ) -> tuple[str, str, str, Any, float]:
        confidence = 0.90
        if isinstance(sol, (tuple, list)) and len(sol) == 3:
            subject, relation, obj = str(sol[0]).strip(), str(sol[1]).strip(), deepcopy(sol[2])
        elif isinstance(sol, Mapping):
            subject = str(sol.get("subject") or "").strip()
            relation = str(sol.get("relation") or "").strip()
            if "object" in sol:
                obj = deepcopy(sol["object"])
            elif "obj" in sol:
                obj = deepcopy(sol["obj"])
            else:
                raise DistillationRejectedError(
                    "semantic_fact mapping requires 'object' (or 'obj')"
                )
            if "confidence" in sol and sol["confidence"] is not None:
                raw_conf = sol["confidence"]
                if isinstance(raw_conf, bool) or not isinstance(raw_conf, (int, float)):
                    raise DistillationRejectedError(
                        f"semantic_fact confidence must be numeric, got {type(raw_conf).__name__}"
                    )
                confidence = float(raw_conf)
                if not math.isfinite(confidence):
                    raise DistillationRejectedError(
                        f"semantic_fact confidence must be finite, got {raw_conf!r}"
                    )
        else:
            raise DistillationRejectedError(
                f"semantic_fact requires mapping or (subject, relation, object) tuple, got {type(sol).__name__}"
            )

        if not subject or not relation:
            raise DistillationRejectedError(
                "semantic_fact requires non-empty 'subject' and 'relation'"
            )
        try:
            sha256_json_utf8({"object": obj})
        except (TypeError, ValueError) as exc:
            raise DistillationRejectedError(
                f"semantic_fact object must be JSON-serializable with finite values: {exc}"
            ) from exc
        name = str(target_name or f"{subject}.{relation}").strip()
        return name, subject, relation, obj, max(0.0, min(1.0, confidence))

    # ------------------------------------------------------------------
    # Verification & Regression Evaluation
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_skill_env(
        case: Mapping[str, Any],
        arg_names: Sequence[str],
    ) -> dict[str, Any]:
        if isinstance(case.get("env"), Mapping):
            return dict(case["env"])
        if isinstance(case.get("inputs"), Mapping):
            return dict(case["inputs"])
        if isinstance(case.get("args"), Sequence) and not isinstance(
            case["args"], (str, bytes)
        ):
            args_seq = list(case["args"])
            if len(args_seq) != len(arg_names):
                raise ValueError(
                    f"case args length {len(args_seq)} does not match {tuple(arg_names)}"
                )
            return {k: v for k, v in zip(arg_names, args_seq)}
        return {k: case[k] for k in arg_names if k in case}

    @staticmethod
    def _values_equal(actual: Any, expected: Any, *, tol: float = 1e-6) -> bool:
        if isinstance(expected, (bool, np.bool_)) or isinstance(actual, (bool, np.bool_)):
            return (
                isinstance(expected, (bool, np.bool_))
                and isinstance(actual, (bool, np.bool_))
                and bool(actual) is bool(expected)
            )
        if isinstance(expected, (int, float, np.integer, np.floating)) and isinstance(
            actual, (int, float, np.integer, np.floating)
        ):
            return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tol)
        return actual == expected

    def _evaluate_single_case(
        self,
        *,
        artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"],
        target_name: str,
        case: Mapping[str, Any],
        arg_names: Sequence[str] = (),
        fact_subject: str | None = None,
        fact_relation: str | None = None,
    ) -> tuple[bool, str]:
        try:
            if artifact_kind == "procedural_skill":
                env = self._extract_skill_env(case, arg_names)
                actual = self.memory.run_skill(target_name, env)
                if callable(case.get("predicate")):
                    ok = bool(case["predicate"](actual))
                    return ok, "predicate_passed" if ok else f"predicate_failed(actual={actual!r})"
                if "expected_approx" in case:
                    tol = float(case.get("tol", 1e-6))
                    ok = self._values_equal(actual, case["expected_approx"], tol=tol)
                    return ok, (
                        "ok"
                        if ok
                        else f"expected_approx={case['expected_approx']!r}, got={actual!r}"
                    )
                if "expected" in case:
                    tol = float(case.get("tol", 1e-6))
                    ok = self._values_equal(actual, case["expected"], tol=tol)
                    return ok, "ok" if ok else f"expected={case['expected']!r}, got={actual!r}"
                return True, "executed"

            if artifact_kind == "eliza_rule":
                user_text = str(
                    case.get("input") or case.get("user_text") or case.get("prompt") or ""
                )
                match_res = self.rule_registry.match(user_text, advance_cursor=False)
                expected_match = bool(case.get("expected_match", True))
                if not expected_match:
                    if match_res is None:
                        return True, "no_match_as_expected"
                    if case.get("expected_rule_id") and match_res["rule_id"] != case["expected_rule_id"]:
                        return True, "different_rule_matched"
                    return False, f"unexpected match on rule {match_res['rule_id']!r}"

                if match_res is None:
                    return False, f"no rule matched input {user_text!r}"
                if case.get("expected_rule_id") and match_res["rule_id"] != case["expected_rule_id"]:
                    return (
                        False,
                        f"expected rule {case['expected_rule_id']!r}, got {match_res['rule_id']!r}",
                    )
                reply = str(match_res["reply"])
                if "expected_reply" in case and reply != str(case["expected_reply"]):
                    return (
                        False,
                        f"expected reply {case['expected_reply']!r}, got {reply!r}",
                    )
                if "expected_contains" in case:
                    needles = case["expected_contains"]
                    needle_list = (
                        [needles] if isinstance(needles, str) else [str(n) for n in needles]
                    )
                    low_reply = reply.lower()
                    for needle in needle_list:
                        if str(needle).lower() not in low_reply:
                            return False, f"reply {reply!r} missing substring {needle!r}"
                if callable(case.get("predicate")):
                    ok = bool(case["predicate"](match_res))
                    return ok, "predicate_passed" if ok else "predicate_failed"
                return True, "ok"

            # semantic_fact
            subj = str(case.get("subject") or fact_subject or "")
            rel = case.get("relation", fact_relation)
            active_only = bool(case.get("expected_active", True))
            hits = self.memory.query_facts(
                subject=subj or None,
                relation=str(rel) if rel is not None else None,
                active_only=active_only,
            )
            if callable(case.get("predicate")):
                ok = bool(case["predicate"](hits))
                return ok, "predicate_passed" if ok else "predicate_failed"
            if not hits:
                return False, f"no active fact found for ({subj!r}, {rel!r})"
            latest = hits[-1]
            if "expected_object" in case or "expected" in case:
                exp_obj = case.get("expected_object", case.get("expected"))
                if latest["object"] != exp_obj:
                    return False, f"expected object {exp_obj!r}, got {latest['object']!r}"
            if "min_confidence" in case and float(latest["confidence"]) < float(
                case["min_confidence"]
            ):
                return (
                    False,
                    f"confidence {latest['confidence']} < min {case['min_confidence']}",
                )
            return True, "ok"
        except Exception as exc:
            return False, f"exception: {exc}"

    def _run_cases_for_artifact(
        self,
        *,
        artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"],
        target_name: str,
        cases: Sequence[Mapping[str, Any]],
        arg_names: Sequence[str] = (),
        fact_subject: str | None = None,
        fact_relation: str | None = None,
    ) -> dict[str, Any]:
        details: list[dict[str, Any]] = []
        passed_count = 0
        for idx, case in enumerate(cases):
            ok, reason = self._evaluate_single_case(
                artifact_kind=artifact_kind,
                target_name=target_name,
                case=case,
                arg_names=arg_names,
                fact_subject=fact_subject,
                fact_relation=fact_relation,
            )
            if ok:
                passed_count += 1
            details.append({"case_index": idx, "passed": ok, "detail": reason})
        total = len(cases)
        accuracy = (passed_count / total) if total > 0 else 1.0
        return {
            "total": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "accuracy": round(accuracy, 6),
            "all_passed": passed_count == total,
            "details": details,
        }

    def _evaluate_regression_suite(
        self,
        *,
        new_artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"],
        new_target_name: str,
        new_cases: Sequence[Mapping[str, Any]],
        new_arg_names: Sequence[str],
        new_fact_meta: Mapping[str, Any] | None,
        extra_regression_cases: Sequence[Mapping[str, Any]] | None,
        min_accuracy: float,
    ) -> dict[str, Any]:
        new_res = self._run_cases_for_artifact(
            artifact_kind=new_artifact_kind,
            target_name=new_target_name,
            cases=new_cases,
            arg_names=new_arg_names,
            fact_subject=str(new_fact_meta["subject"]) if new_fact_meta else None,
            fact_relation=str(new_fact_meta["relation"]) if new_fact_meta else None,
        )

        # Verify all previously active artifacts still pass their verification cases
        prior_results: list[dict[str, Any]] = []
        total_cases = new_res["total"]
        total_passed = new_res["passed"]
        for art_id, art in self._active_artifacts.items():
            if not art.verification_cases:
                continue
            fmeta = self._fact_meta.get(art_id)
            if (
                new_artifact_kind == "semantic_fact"
                and art.artifact_kind == "semantic_fact"
                and new_fact_meta is not None
                and fmeta is not None
                and fmeta.get("subject") == new_fact_meta.get("subject")
                and fmeta.get("relation") == new_fact_meta.get("relation")
            ):
                # Evidence-approved belief revision intentionally supersedes prior fact value.
                continue
            art_args: tuple[str, ...] = ()
            if art.artifact_kind == "procedural_skill":
                proc = next(
                    (s for s in self.memory.snapshot().get("procedural", []) if s["name"] == art.target_name),
                    None,
                )
                if proc is not None:
                    art_args = tuple(proc["arg_names"])
            res = self._run_cases_for_artifact(
                artifact_kind=art.artifact_kind,
                target_name=art.target_name,
                cases=art.verification_cases,
                arg_names=art_args,
                fact_subject=str(fmeta["subject"]) if fmeta else None,
                fact_relation=str(fmeta["relation"]) if fmeta else None,
            )
            prior_results.append(
                {"artifact_id": art_id, "target_name": art.target_name, **res}
            )
            total_cases += res["total"]
            total_passed += res["passed"]

        extra_res: dict[str, Any] | None = None
        if extra_regression_cases:
            # Extra regression cases can specify explicit artifact_kind/target_name or default to current artifact
            extra_details: list[dict[str, Any]] = []
            extra_passed = 0
            for idx, rc in enumerate(extra_regression_cases):
                kind = rc.get("artifact_kind", new_artifact_kind)
                tname = str(rc.get("target_name", new_target_name))
                args_for_case = new_arg_names
                if kind == "procedural_skill" and tname != new_target_name:
                    proc = next(
                        (s for s in self.memory.snapshot().get("procedural", []) if s["name"] == tname),
                        None,
                    )
                    if proc is not None:
                        args_for_case = tuple(proc["arg_names"])
                ok, reason = self._evaluate_single_case(
                    artifact_kind=kind,
                    target_name=tname,
                    case=rc,
                    arg_names=args_for_case,
                    fact_subject=str(new_fact_meta["subject"]) if new_fact_meta else None,
                    fact_relation=str(new_fact_meta["relation"]) if new_fact_meta else None,
                )
                if ok:
                    extra_passed += 1
                extra_details.append({"case_index": idx, "passed": ok, "detail": reason})
            extra_total = len(extra_regression_cases)
            extra_res = {
                "total": extra_total,
                "passed": extra_passed,
                "failed": extra_total - extra_passed,
                "accuracy": round((extra_passed / extra_total) if extra_total else 1.0, 6),
                "all_passed": extra_passed == extra_total,
                "details": extra_details,
            }
            total_cases += extra_total
            total_passed += extra_passed

        overall_accuracy = (total_passed / total_cases) if total_cases > 0 else 1.0
        passed = (
            new_res["all_passed"]
            and all(p["all_passed"] for p in prior_results)
            and (extra_res["all_passed"] if extra_res is not None else True)
            and overall_accuracy >= float(min_accuracy)
        )
        return {
            "passed": bool(passed),
            "overall_accuracy": round(overall_accuracy, 6),
            "min_accuracy": float(min_accuracy),
            "total_cases": total_cases,
            "total_passed": total_passed,
            "new_artifact_verification": new_res,
            "prior_artifacts_regression": prior_results,
            "extra_regression": extra_res,
        }

    # ------------------------------------------------------------------
    # InlineSkill Export
    # ------------------------------------------------------------------
    @staticmethod
    def _build_inline_skill(
        *,
        artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"],
        target_name: str,
        task_prompt: str,
        evidence_id: str,
        provenance_str: str,
        content_body: str,
    ) -> DistilledInlineSkill:
        slug = re.sub(r"[^a-zA-Z0-9-]+", "-", target_name).strip("-").lower() or "distilled-skill"
        return DistilledInlineSkill(
            name=slug,
            description=f"[{artifact_kind}] Distilled System-1 rule/skill for: {task_prompt[:140]}",
            content=content_body,
            metadata={
                "artifact_kind": artifact_kind,
                "target_name": target_name,
                "evidence_id": evidence_id,
                "provenance": provenance_str,
                "system_tier": "system1_distilled",
            },
        )

    def export_inline_skill(self, artifact: DistilledArtifact) -> DistilledInlineSkill:
        """Build or return a `google.antigravity.InlineSkill` descriptor for an artifact."""
        if artifact.inline_skill is not None:
            return artifact.inline_skill
        return self._build_inline_skill(
            artifact_kind=artifact.artifact_kind,
            target_name=artifact.target_name,
            task_prompt=artifact.target_name,
            evidence_id=artifact.evidence_id,
            provenance_str=_provenance_label(artifact.provenance),
            content_body=(
                f"# Distilled {artifact.artifact_kind}: {artifact.target_name}\n"
                f"Evidence: {artifact.evidence_id}\n"
                f"SHA-256: {artifact.artifact_sha256}\n"
            ),
        )

    # ------------------------------------------------------------------
    # Main Distillation Entrypoint
    # ------------------------------------------------------------------
    def distill(
        self,
        trace: System2Trace,
        *,
        artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"] | None = None,
        target_name: str | None = None,
        verification_cases: Sequence[Mapping[str, Any]] | None = None,
        regression_cases: Sequence[Mapping[str, Any]] | None = None,
        export_inline_skill: bool = True,
        raise_on_regression: bool = True,
        min_regression_accuracy: float = 1.0,
        record_blackboard_lineage: bool = True,
    ) -> DistilledArtifact:
        """Distill a verified high-uncertainty System-2 trace into System-1 stores."""
        prov_doc, ev_id = self._validate_trace_gate(trace)
        prov_label = _provenance_label(prov_doc)
        try:
            kind = self._infer_artifact_kind(trace, artifact_kind)

            # Parse & pre-validate payload BEFORE mutating any store
            proc_args: tuple[str, ...] = ()
            proc_source = ""
            proc_desc = ""
            eliza_rule: ElizaRule | None = None
            fact_subject = ""
            fact_relation = ""
            fact_obj: Any = None
            fact_conf = 0.90

            if kind == "procedural_skill":
                resolved_name, proc_source, proc_args, proc_desc = self._parse_procedural_payload(
                    trace.solution_code_or_rule,
                    target_name=target_name,
                    task_prompt=trace.task_prompt,
                )
                content_body = (
                    f"Execute sandboxed Zoe procedural skill `{resolved_name}{proc_args}`:\n\n"
                    f"```python\n{proc_source}\n```\n"
                )
            elif kind == "eliza_rule":
                eliza_rule = self._parse_eliza_payload(
                    trace.solution_code_or_rule,
                    target_name=target_name,
                )
                # Pre-validate compilation without mutating registry yet
                try:
                    DistilledRuleRegistry._compile_rule(eliza_rule)
                except (ValueError, TypeError) as err:
                    raise DistillationRejectedError(str(err)) from err
                resolved_name = eliza_rule.rule_id
                content_body = (
                    f"Apply distilled Gear-1 ELIZA rule `{resolved_name}` "
                    f"(rank={eliza_rule.rank}, keywords={list(eliza_rule.keywords)}).\n"
                )
            else:
                resolved_name, fact_subject, fact_relation, fact_obj, fact_conf = (
                    self._parse_semantic_payload(
                        trace.solution_code_or_rule,
                        target_name=target_name,
                    )
                )
                content_body = (
                    f"Recall verified semantic fact: ({fact_subject}, {fact_relation}) -> {fact_obj!r} "
                    f"[confidence={fact_conf:.2f}, evidence={ev_id}].\n"
                )
        except DistillationRejectedError as err:
            self._record_rejection(trace, str(err))
            raise

        # Snapshot all mutable System-1 state prior to applying the distillation
        mem_snap = self.memory.snapshot()
        reg_snap = self.rule_registry.snapshot()
        bb_snap = (
            self.blackboard.snapshot()
            if (self.blackboard is not None and record_blackboard_lineage)
            else None
        )
        active_snap = dict(self._active_artifacts)
        inline_snap = dict(self._inline_skills)
        fact_meta_snap = deepcopy(self._fact_meta)
        seq_snap = self._seq
        rollback_ledger_snap = dict(self._rollback_ledger)
        history_snap = list(self._history)

        def _rollback_distill_state() -> None:
            if not self.memory.summary().get("stopped", False):
                self.memory.rollback(mem_snap)
            self.rule_registry.rollback(reg_snap)
            self._active_artifacts = active_snap
            self._inline_skills = inline_snap
            self._fact_meta = fact_meta_snap
            self._rollback_ledger = rollback_ledger_snap
            self._history = history_snap
            self._seq = seq_snap
            if (
                bb_snap is not None
                and self.blackboard is not None
                and not getattr(self.blackboard, "stopped", False)
            ):
                if self.blackboard.snapshot() != bb_snap:
                    self.blackboard.rollback(bb_snap)

        self._seq += 1
        seq = self._seq
        artifact_id = f"distill_{seq:04d}_{kind}"

        try:
            # Commit to target System-1 store
            new_fact_meta: dict[str, Any] | None = None
            if kind == "procedural_skill":
                store_doc = self.memory.register_skill(
                    resolved_name,
                    proc_source,
                    proc_args,
                    description=f"{proc_desc} [evidence={ev_id}, provenance={prov_label}]",
                )
            elif kind == "eliza_rule":
                assert eliza_rule is not None
                store_doc = self.rule_registry.register_rule(eliza_rule)
            else:
                store_doc = self.memory.record_fact(
                    fact_subject,
                    fact_relation,
                    fact_obj,
                    confidence=fact_conf,
                    provenance=f"distilled:{ev_id}:{prov_label}",
                    evidence_approved=True,
                )
                new_fact_meta = {"subject": fact_subject, "relation": fact_relation}

            norm_cases = tuple(deepcopy(dict(c)) for c in (verification_cases or ()))
            reg_report = self._evaluate_regression_suite(
                new_artifact_kind=kind,
                new_target_name=resolved_name,
                new_cases=norm_cases,
                new_arg_names=proc_args,
                new_fact_meta=new_fact_meta,
                extra_regression_cases=regression_cases,
                min_accuracy=min_regression_accuracy,
            )

            # Extract lineage metadata if supplied (e.g. from AlphaEvolveResult)
            lineage_ids: tuple[str, ...] = ()
            raw_lineage = trace.metadata.get("alpha_evolve_lineage")
            if isinstance(raw_lineage, Sequence) and not isinstance(raw_lineage, (str, bytes)):
                lineage_ids = tuple(str(x) for x in raw_lineage)
            elif isinstance(trace.solution_code_or_rule, AlphaEvolveResult):
                lineage_ids = tuple(p.id for p in trace.solution_code_or_rule.lineage)
            elif isinstance(trace.solution_code_or_rule, CandidateProgram):
                lineage_ids = (trace.solution_code_or_rule.id,)

            if not reg_report["passed"]:
                # Bit-exact atomic rollback BEFORE leaving distill()
                _rollback_distill_state()
                msg = (
                    f"Distillation regression/verification failed for {kind} {resolved_name!r}; "
                    "rolled back System-1 state cleanly."
                )
                self._record_rejection(trace, msg)
                if raise_on_regression:
                    raise DistillationRegressionError(
                        msg,
                        report=reg_report,
                        rollback_performed=True,
                    )
                failed_art = DistilledArtifact(
                    artifact_kind=kind,
                    target_name=resolved_name,
                    verification_cases=norm_cases,
                    rollback_token="",
                    artifact_id=artifact_id,
                    evidence_id=ev_id,
                    provenance=prov_doc,
                    initial_uncertainty_a_tau=float(trace.initial_uncertainty_a_tau),
                    memory_sha256=str(mem_snap.get("memory_sha256", "")),
                    chain_head=str(mem_snap.get("chain_head", "")),
                    artifact_sha256=sha256_json_utf8({"store": store_doc, "trace": trace.to_dict()}),
                    inline_skill=None,
                    regression_passed=False,
                    regression_summary=reg_report,
                    rolled_back=True,
                    lineage=lineage_ids,
                )
                self._history.append(failed_art)
                return failed_art

            artifact_sha = sha256_json_utf8(
                {
                    "artifact_id": artifact_id,
                    "kind": kind,
                    "target_name": resolved_name,
                    "evidence_id": ev_id,
                    "store": store_doc,
                    "lineage": list(lineage_ids),
                }
            )
            rollback_token = f"rb_{seq:04d}_{artifact_sha[:12]}"

            # Record distilled lineage onto attached EpistemicBlackboard (strictly Art. III gated)
            blackboard_belief_id: str | None = None
            if self.blackboard is not None and record_blackboard_lineage:
                can_sync_bb = True
                if not self._require_blackboard_evidence:
                    try:
                        ev_rec = self.blackboard.get_evidence(ev_id)
                        can_sync_bb = bool(ev_rec.passed and ev_rec.approved and not ev_rec.negative_result)
                    except KeyError:
                        can_sync_bb = False
                if can_sync_bb:
                    lineage_note = (
                        f" lineage={'->'.join(lineage_ids)}" if lineage_ids else ""
                    )
                    bel = self.blackboard.update_belief(
                        [ev_id],
                        claim=(
                            f"Distilled {kind} '{resolved_name}' ({artifact_id}, "
                            f"sha256={artifact_sha[:12]}){lineage_note}"
                        ),
                        posterior_delta=0.35,
                        subject=f"distilled:{kind}:{resolved_name}",
                        relation="distilled_lineage",
                        confidence=0.95,
                    )
                    blackboard_belief_id = bel.record_id

            inline_skill: DistilledInlineSkill | None = None
            if export_inline_skill:
                inline_skill = self._build_inline_skill(
                    artifact_kind=kind,
                    target_name=resolved_name,
                    task_prompt=trace.task_prompt,
                    evidence_id=ev_id,
                    provenance_str=prov_label,
                    content_body=content_body,
                )
                self._inline_skills[resolved_name] = inline_skill

            mem_summary = self.memory.summary()
            artifact = DistilledArtifact(
                artifact_kind=kind,
                target_name=resolved_name,
                verification_cases=norm_cases,
                rollback_token=rollback_token,
                artifact_id=artifact_id,
                evidence_id=ev_id,
                provenance=prov_doc,
                initial_uncertainty_a_tau=float(trace.initial_uncertainty_a_tau),
                memory_sha256=str(mem_summary["memory_sha256"]),
                chain_head=str(mem_summary["chain_head"]),
                artifact_sha256=artifact_sha,
                inline_skill=inline_skill,
                regression_passed=True,
                regression_summary=reg_report,
                rolled_back=False,
                blackboard_belief_id=blackboard_belief_id,
                lineage=lineage_ids,
            )

            # Save rollback snapshot BEFORE adding this artifact to active maps
            self._rollback_ledger[rollback_token] = _RollbackRecord(
                seq=seq,
                token=rollback_token,
                artifact_id=artifact_id,
                target_name=resolved_name,
                memory_snapshot=mem_snap,
                registry_snapshot=reg_snap,
                active_artifacts_snapshot=active_snap,
                inline_skills_snapshot=inline_snap,
                fact_meta_snapshot=fact_meta_snap,
                blackboard_snapshot=bb_snap,
            )

            # Supersede any prior active artifact with the same (kind, target_name) in active map
            for prev_id in [
                aid
                for aid, a in self._active_artifacts.items()
                if a.artifact_kind == kind and a.target_name == resolved_name
            ]:
                self._active_artifacts.pop(prev_id, None)
            self._active_artifacts[artifact_id] = artifact
            if new_fact_meta is not None:
                self._fact_meta[artifact_id] = new_fact_meta
            self._history.append(artifact)
            return artifact
        except Exception:
            _rollback_distill_state()
            raise

    # ------------------------------------------------------------------
    # Post-Commit Regression Verification & Rollback
    # ------------------------------------------------------------------
    def verify_artifact(
        self,
        artifact: DistilledArtifact,
        *,
        extra_cases: Sequence[Mapping[str, Any]] | None = None,
        min_accuracy: float = 1.0,
    ) -> dict[str, Any]:
        """Re-verify an already-distilled artifact against its cases + optional extra cases."""
        cases = list(artifact.verification_cases)
        if extra_cases:
            cases.extend(deepcopy(dict(c)) for c in extra_cases)
        arg_names: tuple[str, ...] = ()
        if artifact.artifact_kind == "procedural_skill":
            proc = next(
                (s for s in self.memory.snapshot().get("procedural", []) if s["name"] == artifact.target_name),
                None,
            )
            if proc is not None:
                arg_names = tuple(proc["arg_names"])
        fmeta = self._fact_meta.get(artifact.artifact_id)
        res = self._run_cases_for_artifact(
            artifact_kind=artifact.artifact_kind,
            target_name=artifact.target_name,
            cases=cases,
            arg_names=arg_names,
            fact_subject=str(fmeta["subject"]) if fmeta else None,
            fact_relation=str(fmeta["relation"]) if fmeta else None,
        )
        res["passed_threshold"] = res["accuracy"] >= float(min_accuracy) and res["all_passed"]
        return res

    def verify_regression(
        self,
        *,
        regression_cases: Sequence[Mapping[str, Any]] | None = None,
        min_accuracy: float = 1.0,
        rollback_token_on_failure: str | None = None,
    ) -> dict[str, Any]:
        """Verify all active distilled artifacts (plus optional extra regression cases)."""
        per_artifact: list[dict[str, Any]] = []
        total_cases = 0
        total_passed = 0
        for art_id, art in self._active_artifacts.items():
            res = self.verify_artifact(art, min_accuracy=min_accuracy)
            per_artifact.append({"artifact_id": art_id, "target_name": art.target_name, **res})
            total_cases += res["total"]
            total_passed += res["passed"]

        if regression_cases:
            extra_details: list[dict[str, Any]] = []
            extra_passed = 0
            for idx, rc in enumerate(regression_cases):
                kind = rc.get("artifact_kind")
                tname = str(rc.get("target_name") or "")
                if not kind or not tname:
                    raise ValueError(
                        "verify_regression extra cases require 'artifact_kind' and 'target_name'"
                    )
                arg_names: tuple[str, ...] = ()
                if kind == "procedural_skill":
                    proc = next(
                        (s for s in self.memory.snapshot().get("procedural", []) if s["name"] == tname),
                        None,
                    )
                    if proc is not None:
                        arg_names = tuple(proc["arg_names"])
                ok, reason = self._evaluate_single_case(
                    artifact_kind=kind,
                    target_name=tname,
                    case=rc,
                    arg_names=arg_names,
                )
                if ok:
                    extra_passed += 1
                extra_details.append({"case_index": idx, "passed": ok, "detail": reason})
            total_cases += len(regression_cases)
            total_passed += extra_passed
        else:
            extra_details = []

        accuracy = (total_passed / total_cases) if total_cases > 0 else 1.0
        passed = (
            all(r["all_passed"] for r in per_artifact)
            and all(d["passed"] for d in extra_details)
            and accuracy >= float(min_accuracy)
        )
        rollback_info: dict[str, Any] | None = None
        if not passed and rollback_token_on_failure:
            rollback_info = self.rollback(rollback_token_on_failure)

        return {
            "passed": bool(passed),
            "accuracy": round(accuracy, 6),
            "min_accuracy": float(min_accuracy),
            "total_cases": total_cases,
            "total_passed": total_passed,
            "per_artifact": per_artifact,
            "extra_details": extra_details,
            "rollback_performed": rollback_info is not None,
            "rollback_info": rollback_info,
        }

    def rollback(self, token: str) -> dict[str, Any]:
        """Atomically roll back System-1 stores to the snapshot captured before `token`."""
        entry = self._rollback_ledger.get(token)
        if entry is None or entry.rolled_back:
            raise UnknownRollbackTokenError(
                f"unknown or already-reverted rollback token: {token!r}"
            )

        # Pre-validate stopped states and snapshot integrity BEFORE mutating any store.
        if self.blackboard is not None and entry.blackboard_snapshot is not None:
            if getattr(self.blackboard, "stopped", False):
                raise RuntimeError(
                    "cannot rollback while EpistemicBlackboard is emergency-stopped"
                )
            if hasattr(self.blackboard, "_validate_document_integrity"):
                self.blackboard._validate_document_integrity(entry.blackboard_snapshot)
        if self.memory.summary().get("stopped", False):
            raise RuntimeError(
                "cannot rollback while ZoeUnifiedMemory is emergency-stopped"
            )
        expected_mem_sha = sha256_json_utf8(
            {k: v for k, v in entry.memory_snapshot.items() if k != "memory_sha256"}
        )
        if entry.memory_snapshot.get("memory_sha256") != expected_mem_sha:
            raise ValueError("cannot rollback to tampered memory snapshot")

        self.memory.rollback(entry.memory_snapshot)
        self.rule_registry.rollback(entry.registry_snapshot)
        if self.blackboard is not None and entry.blackboard_snapshot is not None:
            self.blackboard.rollback(entry.blackboard_snapshot)
        self._active_artifacts = dict(entry.active_artifacts_snapshot)
        self._inline_skills = dict(entry.inline_skills_snapshot)
        self._fact_meta = deepcopy(entry.fact_meta_snapshot)

        reverted_tokens: list[str] = []
        for tok, rec in self._rollback_ledger.items():
            if rec.seq >= entry.seq and not rec.rolled_back:
                rec.rolled_back = True
                reverted_tokens.append(tok)

        # Mark rolled-back artifacts in history cleanly without deleting audit history
        reverted_set = set(reverted_tokens)
        updated_history: list[DistilledArtifact] = []
        for art in self._history:
            if art.rollback_token in reverted_set and not art.rolled_back:
                updated_history.append(
                    DistilledArtifact(
                        artifact_kind=art.artifact_kind,
                        target_name=art.target_name,
                        verification_cases=art.verification_cases,
                        rollback_token=art.rollback_token,
                        artifact_id=art.artifact_id,
                        evidence_id=art.evidence_id,
                        provenance=art.provenance,
                        initial_uncertainty_a_tau=art.initial_uncertainty_a_tau,
                        memory_sha256=art.memory_sha256,
                        chain_head=art.chain_head,
                        artifact_sha256=art.artifact_sha256,
                        inline_skill=art.inline_skill,
                        regression_passed=art.regression_passed,
                        regression_summary=art.regression_summary,
                        rolled_back=True,
                        created_utc=art.created_utc,
                        constitutional=art.constitutional,
                        blackboard_belief_id=art.blackboard_belief_id,
                        lineage=art.lineage,
                    )
                )
            else:
                updated_history.append(art)
        self._history = updated_history

        mem_sum = self.memory.summary()
        return {
            "rolled_back": True,
            "rollback_token": token,
            "reverted_tokens": reverted_tokens,
            "target_name": entry.target_name,
            "restored_memory_sha256": mem_sum["memory_sha256"],
            "restored_chain_head": mem_sum["chain_head"],
            "constitutional": distillation_constitutional_metadata(),
        }

    # ------------------------------------------------------------------
    # Fast System-1 Replay & Lookup
    # ------------------------------------------------------------------
    def replay_skill(self, name: str, env: Mapping[str, Any]) -> Any:
        """Fast System-1 replay of a distilled guarded AST procedural skill (0 tokens)."""
        return self.memory.run_skill(name, dict(env))

    def lookup_rule(self, user_text: str) -> dict[str, Any] | None:
        """Fast System-1 Gear-1 lookup across distilled `ElizaRule` patterns (0 tokens)."""
        return self.rule_registry.match(user_text)

    def lookup_fact(
        self,
        subject: str,
        *,
        relation: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Fast System-1 lookup of distilled semantic facts in `ZoeUnifiedMemory`."""
        return self.memory.query_facts(
            subject=subject,
            relation=relation,
            active_only=active_only,
        )

    # ------------------------------------------------------------------
    # AlphaEvolve & Antigravity Bridge System-2 -> System-1 Helpers
    # ------------------------------------------------------------------
    def distill_from_alpha_evolve(
        self,
        result: AlphaEvolveResult,
        *,
        task_prompt: str = "",
        initial_uncertainty_a_tau: float | int = 3,
        evidence_id: str | EvidenceRecord | None = None,
        target_name: str | None = None,
        verification_cases: Sequence[Mapping[str, Any]] | None = None,
        regression_cases: Sequence[Mapping[str, Any]] | None = None,
        export_inline_skill: bool = True,
        raise_on_regression: bool = True,
        min_regression_accuracy: float = 1.0,
        record_blackboard_lineage: bool = True,
    ) -> DistilledArtifact:
        """Distill a verified winning `AlphaEvolveResult` program into System-1 memory.

        Strictly preserves `CONSTITUTION.md` Article III: the winning program
        must pass all deterministic tests (`total_tests > 0` and
        `passed_tests == total_tests`) and carry an explicit or blackboard-promoted
        passing `evidence_id`.
        """
        if not isinstance(result, AlphaEvolveResult):
            raise DistillationRejectedError(
                f"expected AlphaEvolveResult, got {type(result).__name__}"
            )
        best = result.best_program
        verifier_passed = bool(best.total_tests > 0 and best.passed_tests == best.total_tests)

        resolved_ev_id: str | EvidenceRecord = evidence_id if evidence_id is not None else ""
        if not resolved_ev_id:
            # Prefer a winning evidence record specifically matching best_program.id
            for rec in reversed(result.blackboard_records):
                if (
                    rec.get("promoted_to_evidence") is True
                    and rec.get("passed") is True
                    and not rec.get("negative_result")
                    and rec.get("evidence_id")
                    and rec.get("program_id") == best.id
                ):
                    resolved_ev_id = str(rec["evidence_id"])
                    break
        if not resolved_ev_id:
            for rec in reversed(result.blackboard_records):
                if (
                    rec.get("promoted_to_evidence") is True
                    and rec.get("passed") is True
                    and not rec.get("negative_result")
                    and rec.get("evidence_id")
                ):
                    resolved_ev_id = str(rec["evidence_id"])
                    break

        lineage_ids = [p.id for p in result.lineage]
        provenance = Provenance(
            sources=(
                EvidenceSource(
                    kind="tool",
                    identifier=f"AlphaEvolveLoop:{best.id}",
                    trust=0.95,
                    strength=0.95,
                ),
            ),
            transformations=(
                f"generation={best.generation}",
                f"lineage={'->'.join(lineage_ids)}",
                f"code_sha256={best.code_sha256}",
            ),
        )
        eff_prompt = (
            task_prompt.strip()
            if task_prompt.strip()
            else f"Distill AlphaEvolve winner `{best.function_name}` ({best.id})"
        )
        trace = System2Trace(
            task_prompt=eff_prompt,
            initial_uncertainty_a_tau=initial_uncertainty_a_tau,
            solution_code_or_rule=result,
            verifier_passed=verifier_passed,
            evidence_id=resolved_ev_id,
            provenance=provenance,
            artifact_kind="procedural_skill",
            trace_id=best.id,
            source_agent="alpha_evolve_loop",
            metadata={
                "alpha_evolve_lineage": lineage_ids,
                "best_program_id": best.id,
                "best_generation": best.generation,
                "score": best.score,
                "code_sha256": best.code_sha256,
            },
        )
        return self.distill(
            trace,
            artifact_kind="procedural_skill",
            target_name=target_name or best.function_name,
            verification_cases=verification_cases,
            regression_cases=regression_cases,
            export_inline_skill=export_inline_skill,
            raise_on_regression=raise_on_regression,
            min_regression_accuracy=min_regression_accuracy,
            record_blackboard_lineage=record_blackboard_lineage,
        )

    def solve_and_distill(
        self,
        task_prompt: str,
        *,
        initial_uncertainty_a_tau: float | int,
        solver: Callable[[str], Any] | None = None,
        verifier: Callable[[Any], tuple[bool, str, Mapping[str, Any] | Provenance | EvidenceSource | str]],
        artifact_kind: Literal["procedural_skill", "eliza_rule", "semantic_fact"] | None = None,
        target_name: str | None = None,
        verification_cases: Sequence[Mapping[str, Any]] | None = None,
        export_inline_skill: bool = True,
    ) -> DistilledArtifact:
        """Run a System-2 solver (or `ZoeAntigravityBridge`), verify, and distill if verified."""
        if solver is not None:
            solution = solver(task_prompt)
            cloud_tokens = 0
        else:
            bridge = self.bridge or ZoeAntigravityBridge()
            turn = bridge.run_turn(task_prompt, mode="offline")
            solution = turn.structured_output if turn.structured_output is not None else turn.text
            cloud_tokens = int((turn.usage_metadata or {}).get("total_token_count") or 0)

        passed, evidence_id, provenance = verifier(solution)
        trace = System2Trace(
            task_prompt=task_prompt,
            initial_uncertainty_a_tau=initial_uncertainty_a_tau,
            solution_code_or_rule=solution,
            verifier_passed=bool(passed),
            evidence_id=str(evidence_id),
            provenance=provenance,
            artifact_kind=artifact_kind,
            metadata={"cloud_tokens_used": cloud_tokens},
        )
        return self.distill(
            trace,
            artifact_kind=artifact_kind,
            target_name=target_name,
            verification_cases=verification_cases,
            export_inline_skill=export_inline_skill,
        )

    def distill_gem_rule(
        self,
        *,
        rule_id: str,
        pattern: str,
        response: str,
        evidence_id: str,
        a_tau: int = 2,
    ) -> DistilledArtifact:
        """Distill a verified Digital Research GEM conversational rule through all Art. III gates."""
        clean_id = str(rule_id).strip() or "gem_rule"
        trace = System2Trace(
            task_prompt=f"Distill verified GEM rule {clean_id}",
            initial_uncertainty_a_tau=a_tau,
            solution_code_or_rule={
                "rule_id": clean_id,
                "keywords": (clean_id, "gem"),
                "rank": 10,
                "decompositions": ((str(pattern), (str(response),)),),
            },
            verifier_passed=True,
            evidence_id=str(evidence_id),
            provenance=Provenance(
                sources=(
                    EvidenceSource(
                        kind="tool",
                        identifier="guiai.gem+seasip_gem",
                        trust=0.92,
                        strength=0.90,
                    ),
                ),
                transformations=("gem_rule_distillation",),
            ),
            artifact_kind="eliza_rule",
        )
        return self.distill(trace, artifact_kind="eliza_rule", export_inline_skill=True)

    # ------------------------------------------------------------------
    # Inspection & Summaries
    # ------------------------------------------------------------------
    def list_artifacts(self, *, include_rolled_back: bool = False) -> tuple[DistilledArtifact, ...]:
        if include_rolled_back:
            return tuple(self._history)
        return tuple(self._active_artifacts.values())

    def list_inline_skills(self) -> tuple[DistilledInlineSkill, ...]:
        return tuple(self._inline_skills.values())

    def rejection_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(r) for r in self._rejections)

    def summary(self) -> dict[str, Any]:
        return {
            "contract": DISTILLATION_CONTRACT,
            "min_uncertainty_a_tau": self.min_uncertainty_a_tau,
            "active_artifacts_count": len(self._active_artifacts),
            "history_count": len(self._history),
            "rejections_count": len(self._rejections),
            "inline_skills_count": len(self._inline_skills),
            "memory_summary": self.memory.summary(),
            "rule_registry_summary": self.rule_registry.summary(),
            "constitutional": distillation_constitutional_metadata(),
        }


__all__ = [
    "ATTRIBUTION_TEXT",
    "DISTILLATION_CONTRACT",
    "DistillationRegressionError",
    "DistillationRejectedError",
    "DistilledArtifact",
    "DistilledInlineSkill",
    "DistilledRuleRegistry",
    "System2To1Distiller",
    "System2Trace",
    "UnknownRollbackTokenError",
    "UnsafeFunctionASTError",
    "VALID_ARTIFACT_KINDS",
    "distillation_constitutional_metadata",
]

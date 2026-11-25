"""Architecture #3: MCTS / Tree-of-Thought with Kloster Stopping & Multi-Horizon A_tau^(h).

Implements parallel/async and synchronous UCT Tree-of-Thought search integrated with:
  1. Exact Multi-Horizon Prefix-Pruning (`l5_phase6_multihorizon_metacognition`):
     Computes exact $A_\\tau^{(h)}$ via `exact_multihorizon_accessible_volume` and enforces
     `tight_strict_upper_bound(tau)` ($\\lceil 1/\\tau \\rceil - 1$), pruning any prefix branch
     with joint probability $P(u) \\le \\tau$ before expansion.
  2. Theorem 13 Anytime-Valid Sequential Stopping (`guiai.gem.kloster_stopping_law`):
     Feeds branch evidence observations into `KlosterSequentialStoppingController` and
     computes unbiased U-statistic chi-squared telemetry (`kloster_unbiased_chi2_stats`)
     to emit `DECIDE_SIGNAL`, `GATHER_MORE`, or `ABSTAIN_INSUFFICIENT_EVIDENCE`.
  3. Parallel Sibling Expansion & Optional Voice Bridge (`asyncio.gather` + `sdk_bridge`):
     Evaluates surviving sibling branches concurrently via `asyncio.gather` and optionally
     attaches transparent reasoning traces via `ZoeAntigravityBridge` / `ReasoningVoiceAdapter`.
  4. Fork-Candidate Emission for High-Leverage Human Steering (Arch 8):
     Surfaces nodes where $A_\\tau^{(h)}$ reveals competing surviving hypotheses (including
     delayed non-monotonic branching where $A_\\tau^{(h+1)} > A_\\tau^{(h)}$).

Enforces ``docs/CONSTITUTION.md`` epistemic firewall invariants
(``measurement != evidence != belief update != action``, ``external_actions=0``,
``sentience_claimed=False``, ``l5_agi_qualified=False``, ``zoe_clone_claimed=False``,
attribution to Nicholas Michael Kloster, March 6, 2026).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import inspect
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

from ..l5_phase6_multihorizon_metacognition import (
    exact_multihorizon_accessible_volume,
    tight_strict_upper_bound,
)
from .sdk_bridge import (
    ReasoningVoiceAdapter,
    VALID_MODES,
    VoiceResponse,
    ZoeAntigravityBridge,
    bridge_constitutional_metadata,
    run_coro_sync,
)


def _ensure_guiai_importable() -> None:
    """Ensure ``guiai-lab`` is on ``sys.path`` when running directly from the monorepo."""
    try:
        import guiai.gem.kloster_stopping_law  # noqa: F401
        return
    except ImportError:
        repo_root = Path(__file__).resolve().parents[4]
        guiai_lab = repo_root / "guiai-lab"
        if guiai_lab.is_dir() and str(guiai_lab) not in sys.path:
            sys.path.insert(0, str(guiai_lab))


_ensure_guiai_importable()

from guiai.gem.kloster_stopping_law import (  # noqa: E402
    KlosterSequentialStoppingController,
    kloster_unbiased_chi2_stats,
)

MCTS_KLOSTER_CONTRACT = "zoe-mcts-kloster/v1"


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _call_with_optional_node(fn: Callable[..., Any], state: Any, node: ThoughtNode) -> Any:
    """Invoke user ``expand_fn`` or ``eval_fn`` accepting ``(state)`` or ``(state, node)``."""
    try:
        sig = inspect.signature(fn)
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
        if has_varargs or len(positional) >= 2 or "node" in sig.parameters:
            return fn(state, node)
        return fn(state)
    except (TypeError, ValueError):
        return fn(state)


@dataclass(frozen=True)
class ThoughtCandidate:
    """Optional structured candidate returned by ``expand_fn``."""

    state: Any
    action: str
    prior_prob: float | None = None
    token_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThoughtNode:
    """Node in the Kloster MCTS / Tree-of-Thought search tree."""

    node_id: str
    state: Any
    action: str | None = None
    token_index: int | None = None
    parent_id: str | None = None
    depth: int = 0
    prior_prob: float = 1.0
    joint_prob: float = 1.0
    visits: int = 0
    value_sum: float = 0.0
    children_ids: list[str] = field(default_factory=list)
    child_priors: tuple[float, ...] = ()
    child_id_by_token: dict[int, str] = field(default_factory=dict)
    expanded: bool = False
    terminal: bool = False
    pruned: bool = False
    prune_reason: str | None = None
    voice_thought: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mean_value(self) -> float:
        if self.visits <= 0:
            return 0.0
        return self.value_sum / float(self.visits)

    def uct_score(
        self,
        parent_visits: int,
        exploration_c: float = 1.41421356237,
        prior_weight: float = 0.25,
    ) -> float:
        """Compute UCT + prior-guided exploration score for child selection."""
        if self.visits <= 0:
            return 1e9 + float(self.prior_prob)
        n_parent = max(1, int(parent_visits))
        explore = exploration_c * math.sqrt(math.log(n_parent) / float(self.visits))
        prior_bonus = (
            prior_weight
            * float(self.prior_prob)
            * math.sqrt(float(n_parent))
            / (1.0 + float(self.visits))
        )
        return self.mean_value + explore + prior_bonus

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "action": self.action,
            "token_index": self.token_index,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "prior_prob": round(self.prior_prob, 8),
            "joint_prob": round(self.joint_prob, 8),
            "visits": self.visits,
            "value_sum": round(self.value_sum, 6),
            "mean_value": round(self.mean_value, 6),
            "children_ids": list(self.children_ids),
            "expanded": self.expanded,
            "terminal": self.terminal,
            "pruned": self.pruned,
            "prune_reason": self.prune_reason,
            "voice_thought": self.voice_thought,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MCTSBranchTrajectory:
    """Root-to-node reasoning trajectory within the Tree-of-Thought."""

    branch_id: str
    node_ids: tuple[str, ...]
    actions: tuple[str, ...]
    states: tuple[Any, ...]
    depth: int
    joint_prob: float
    mean_value: float
    visits: int
    pruned: bool = False
    prune_reason: str | None = None
    voice_thoughts: tuple[str, ...] = ()
    token_path: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "node_ids": list(self.node_ids),
            "actions": list(self.actions),
            "states": [
                s if isinstance(s, (str, int, float, bool, type(None))) else repr(s)
                for s in self.states
            ],
            "depth": self.depth,
            "joint_prob": round(self.joint_prob, 8),
            "mean_value": round(self.mean_value, 6),
            "visits": self.visits,
            "pruned": self.pruned,
            "prune_reason": self.prune_reason,
            "voice_thoughts": list(self.voice_thoughts),
            "token_path": list(self.token_path),
        }


@dataclass(frozen=True)
class ForkCandidate:
    """Surviving multi-hypothesis fork point surfaced for Arch 8 human steering."""

    fork_id: str
    node_id: str
    depth: int
    horizon: int
    a_tau_at_horizon: int
    tight_upper_bound: int
    competing_branches: tuple[MCTSBranchTrajectory, ...]
    probability_ratio: float
    value_gap: float
    delayed_fork: bool
    reason: str
    recommended_action: str = "ASK_USER_FORK_STEERING"

    def to_summary(self) -> dict[str, Any]:
        """Return an Arch-8-compatible fork summary without mutating verification status."""
        branch_summaries: list[dict[str, Any]] = []
        for idx, branch in enumerate(self.competing_branches):
            action_chain = " -> ".join(branch.actions) if branch.actions else branch.branch_id
            branch_summaries.append(
                {
                    "path_id": branch.branch_id,
                    "summary": f"Branch {idx + 1}: {action_chain}",
                    "actions": list(branch.actions),
                    "expected_utility": round(float(branch.mean_value), 6),
                    "joint_prob": round(float(branch.joint_prob), 8),
                    "visits": int(branch.visits),
                    "tradeoff_notes": (
                        f"prior_mass={branch.joint_prob:.4f}, mean_value={branch.mean_value:.4f}, "
                        f"visits={branch.visits}, depth={branch.depth}"
                    ),
                    "direction_tags": [a.lower() for a in branch.actions[:3]],
                    "reversible": True,
                    "verification_status": "unverified_search_hypothesis",
                }
            )
        return {
            "fork_id": self.fork_id,
            "node_id": self.node_id,
            "depth": self.depth,
            "horizon": self.horizon,
            "a_tau_at_horizon": self.a_tau_at_horizon,
            "tight_upper_bound": self.tight_upper_bound,
            "probability_ratio": self.probability_ratio,
            "value_gap": self.value_gap,
            "delayed_fork": self.delayed_fork,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "branch_summaries": branch_summaries,
        }

    def to_steering_options(
        self,
        *,
        evidence_ids_by_branch: Mapping[str, Sequence[str]] | None = None,
        verification_status_by_branch: Mapping[str, str] | None = None,
        default_verification_status: str = "unverified",
        reversible: bool = True,
        verifier_name: str = "kloster_mcts_search",
    ) -> tuple[Any, ...]:
        """Convert competing branches into Arch 8 ``VerifiedPathOption`` instances.

        By default leaves options marked ``unverified`` (no fabricated verification)
        unless explicit ``evidence_ids_by_branch`` and ``verification_status`` are supplied.
        """
        from .human_steering import VerifiedPathOption

        ev_map = evidence_ids_by_branch or {}
        st_map = verification_status_by_branch or {}
        options: list[VerifiedPathOption] = []
        for summary_doc in self.to_summary()["branch_summaries"]:
            bid = str(summary_doc["path_id"])
            ev_ids = tuple(str(x) for x in ev_map.get(bid, ()))
            status = str(st_map.get(bid, default_verification_status))
            options.append(
                VerifiedPathOption(
                    path_id=bid,
                    summary=str(summary_doc["summary"]),
                    verification_status=status,
                    evidence_ids=ev_ids,
                    expected_utility=float(summary_doc["expected_utility"]),
                    tradeoff_notes=str(summary_doc["tradeoff_notes"]),
                    reversible=bool(reversible),
                    direction_tags=tuple(summary_doc["direction_tags"]),
                    verifier_name=verifier_name,
                    metadata={
                        "fork_id": self.fork_id,
                        "joint_prob": summary_doc["joint_prob"],
                        "delayed_fork": self.delayed_fork,
                    },
                )
            )
        return tuple(options)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fork_id": self.fork_id,
            "node_id": self.node_id,
            "depth": self.depth,
            "horizon": self.horizon,
            "a_tau_at_horizon": self.a_tau_at_horizon,
            "tight_upper_bound": self.tight_upper_bound,
            "competing_branches": [b.to_dict() for b in self.competing_branches],
            "branch_summaries": self.to_summary()["branch_summaries"],
            "probability_ratio": self.probability_ratio,
            "value_gap": self.value_gap,
            "delayed_fork": self.delayed_fork,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self.to_dict()


@dataclass(frozen=True)
class MCTSSearchResult:
    """Complete output of ``KlosterMCTSSearch.run`` / ``arun``."""

    contract: str
    decision: str
    tau: float
    tight_upper_bound: int
    iterations_run: int
    max_iterations: int
    total_nodes: int
    expanded_nodes: int
    parallel_batches: int
    a_tau_trajectory: list[dict[str, Any]]
    multihorizon_volume: dict[str, Any]
    chi2_stats: dict[str, Any]
    stopping_history: list[dict[str, Any]]
    best_branch: MCTSBranchTrajectory | None
    surviving_branches: tuple[MCTSBranchTrajectory, ...]
    pruned_branches: tuple[MCTSBranchTrajectory, ...]
    fork_candidates: tuple[ForkCandidate, ...]
    voice_mode: str
    voice_traces: tuple[dict[str, Any], ...]
    nodes: dict[str, ThoughtNode]
    constitutional: dict[str, Any]
    counts_by_h: tuple[int, ...] = ()
    blackboard_measurement_id: str | None = None

    def fork_summaries(self) -> list[dict[str, Any]]:
        """Return JSON-safe Arch 8 steering summaries for all detected fork candidates."""
        return [f.to_summary() for f in self.fork_candidates]

    def to_human_steering_payload(self) -> dict[str, Any]:
        """Return a mapping directly consumable by ``HumanSteeringDetector.detect(mcts_result=...)``."""
        counts = list(self.counts_by_h or self.multihorizon_volume.get("counts_by_h", ()))
        return {
            "contract": self.contract,
            "decision": self.decision,
            "tau": self.tau,
            "counts_by_h": counts,
            "supercritical_counts": counts,
            "fork_candidates": self.fork_summaries(),
            "best_branch": self.best_branch.to_dict() if self.best_branch is not None else None,
            "constitutional": dict(self.constitutional),
        }

    def to_gem_spatial_ir(self, *, scene_id: str = "mcts-kloster-gem-view") -> dict[str, Any]:
        """Export an Art. II.3 visual-only GEM Spatial IR summary of Kloster MCTS search."""
        from .gem_aes_vdi import GEM_ART_II_3_NOTICE

        return {
            "schema_version": 1,
            "id": str(scene_id),
            "title": "Kloster MCTS Stopping GEM View",
            "canvas": {"width": 6400, "height": 3200},
            "objects": [
                {"id": "mcts_dec", "type": "rectangle", "bounds": [100, 100, 6300, 1450], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "mcts_txt", "type": "text", "position": [240, 800], "text": f"DEC:{self.decision[:18]}", "size": 160, "fill": "black"},
                {"id": "mcts_vol", "type": "rectangle", "bounds": [100, 1650, 6300, 3100], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "vol_txt", "type": "text", "position": [240, 2350], "text": f"NODES={self.total_nodes} FORKS={len(self.fork_candidates)}", "size": 160, "fill": "black"},
            ],
            "constraints": [
                {"type": "inside_canvas", "object": "*"},
                {"type": "nonoverlap", "objects": ["mcts_dec", "mcts_vol"]},
            ],
            "visual_evidence_only": True,
            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
            "constitutional": dict(self.constitutional),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "decision": self.decision,
            "tau": self.tau,
            "tight_upper_bound": self.tight_upper_bound,
            "iterations_run": self.iterations_run,
            "max_iterations": self.max_iterations,
            "total_nodes": self.total_nodes,
            "expanded_nodes": self.expanded_nodes,
            "parallel_batches": self.parallel_batches,
            "counts_by_h": list(self.counts_by_h),
            "a_tau_trajectory": list(self.a_tau_trajectory),
            "multihorizon_volume": dict(self.multihorizon_volume),
            "chi2_stats": dict(self.chi2_stats),
            "stopping_history": list(self.stopping_history),
            "best_branch": self.best_branch.to_dict() if self.best_branch is not None else None,
            "surviving_branches": [b.to_dict() for b in self.surviving_branches],
            "pruned_branches": [b.to_dict() for b in self.pruned_branches],
            "fork_candidates": [f.to_dict() for f in self.fork_candidates],
            "voice_mode": self.voice_mode,
            "voice_traces": [dict(v) for v in self.voice_traces],
            "blackboard_measurement_id": self.blackboard_measurement_id,
            "constitutional": dict(self.constitutional),
        }


@dataclass
class _ParsedEval:
    value: float
    observations: tuple[int, ...] | None = None
    evidence_counts: tuple[int, ...] | None = None
    bin_index: int | None = None
    is_terminal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _validate_int_param(val: Any, *, name: str, min_value: int | None = None) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise ValueError(f"{name} must be an integer, got {type(val).__name__}")
    if min_value is not None and val < min_value:
        raise ValueError(f"{name} must be >= {min_value} (got {val!r})")
    return int(val)


def _validate_float_param(
    val: Any,
    *,
    name: str,
    min_value: float | None = None,
    strict_min: bool = False,
    max_value: float | None = None,
    strict_max: bool = False,
) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"{name} must be a finite numeric value, got {type(val).__name__}")
    fval = float(val)
    if not math.isfinite(fval):
        raise ValueError(f"{name} must be finite (got {val!r})")
    if min_value is not None and (fval <= min_value if strict_min else fval < min_value):
        op = ">" if strict_min else ">="
        raise ValueError(f"{name} must be {op} {min_value} (got {val!r})")
    if max_value is not None and (fval >= max_value if strict_max else fval > max_value):
        op = "<" if strict_max else "<="
        raise ValueError(f"{name} must be {op} {max_value} (got {val!r})")
    return fval


class KlosterMCTSSearch:
    """Tree-of-Thought UCT search with Kloster $A_\\tau^{(h)}$ pruning & Theorem 13 stopping."""

    def __init__(
        self,
        *,
        exploration_c: float = 1.41421356237,
        prior_weight: float = 0.25,
        delta: float = 0.005,
        n_bins: int | None = None,
        samples_per_eval: int = 4,
        max_samples: int | None = None,
        horizon: int = 3,
        fork_prob_ratio_threshold: float = 0.35,
        fork_value_gap_threshold: float = 0.25,
        softmax_beta: float = 8.0,
        seed: int | None = None,
        bridge: ZoeAntigravityBridge | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        use_voice_bridge: bool = False,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        probe_local: bool = False,
        bridge_mode: str | None = None,
        blackboard: Any = None,
    ) -> None:
        eff_exploration_c = _validate_float_param(
            exploration_c, name="exploration_c", min_value=0.0
        )
        eff_prior_weight = _validate_float_param(
            prior_weight, name="prior_weight", min_value=0.0
        )
        eff_delta = _validate_float_param(
            delta,
            name="delta",
            min_value=0.0,
            strict_min=True,
            max_value=1.0,
            strict_max=True,
        )
        eff_softmax_beta = _validate_float_param(
            softmax_beta, name="softmax_beta", min_value=0.0, strict_min=True
        )
        eff_samples_per_eval = _validate_int_param(
            samples_per_eval, name="samples_per_eval", min_value=1
        )
        eff_horizon = _validate_int_param(horizon, name="horizon", min_value=1)
        eff_n_bins = (
            _validate_int_param(n_bins, name="n_bins", min_value=1)
            if n_bins is not None
            else None
        )
        eff_max_samples = (
            _validate_int_param(max_samples, name="max_samples", min_value=1)
            if max_samples is not None
            else None
        )
        eff_seed = (
            _validate_int_param(seed, name="seed")
            if seed is not None
            else None
        )
        eff_fork_prob_ratio = _validate_float_param(
            fork_prob_ratio_threshold, name="fork_prob_ratio_threshold", min_value=0.0
        )
        eff_fork_value_gap = _validate_float_param(
            fork_value_gap_threshold, name="fork_value_gap_threshold", min_value=0.0
        )
        if bridge_mode is not None and bridge_mode not in VALID_MODES:
            raise ValueError(f"bridge_mode must be one of {VALID_MODES}, got {bridge_mode!r}")
        self.exploration_c = eff_exploration_c
        self.prior_weight = eff_prior_weight
        self.delta = eff_delta
        self.n_bins = eff_n_bins
        self.samples_per_eval = eff_samples_per_eval
        self.max_samples = eff_max_samples
        self.horizon = eff_horizon
        self.fork_prob_ratio_threshold = eff_fork_prob_ratio
        self.fork_value_gap_threshold = eff_fork_value_gap
        self.softmax_beta = eff_softmax_beta
        self.seed = eff_seed
        self.bridge = bridge
        self.voice_adapter = voice_adapter
        self.use_voice_bridge = bool(
            use_voice_bridge or bridge is not None or voice_adapter is not None
        )
        self.offline_only = bool(offline_only)
        self.privacy_sensitive = bool(privacy_sensitive)
        self.probe_local = bool(probe_local)
        self.bridge_mode = bridge_mode
        self.blackboard = blackboard

    @staticmethod
    def _validate_prior_prob(raw_p: Any) -> float | None:
        if raw_p is None:
            return None
        if isinstance(raw_p, bool):
            raise ValueError("prior_prob must be a finite numeric value, not bool")
        val = float(raw_p)
        if not math.isfinite(val):
            raise ValueError(f"prior_prob must be finite (NaN/Infinity rejected; got {raw_p!r})")
        if val < 0.0:
            raise ValueError(f"prior_prob must be non-negative (got {raw_p!r})")
        return val

    @staticmethod
    def _validate_eval_value(raw_val: Any) -> float:
        if isinstance(raw_val, bool):
            raise ValueError("eval_fn value must be a finite numeric value, not bool")
        val = float(raw_val)
        if not math.isfinite(val):
            raise ValueError(f"eval_fn value must be finite (NaN/Infinity rejected; got {raw_val!r})")
        return val

    @staticmethod
    def _normalize_candidates(
        raw_candidates: Any,
    ) -> list[tuple[str, Any, float, int | None, dict[str, Any]]]:
        if raw_candidates is None:
            return []
        items = list(raw_candidates)
        if not items:
            return []

        parsed: list[tuple[str, Any, float | None, int | None, dict[str, Any]]] = []
        for idx, item in enumerate(items):
            if isinstance(item, ThoughtCandidate):
                parsed.append(
                    (
                        str(item.action),
                        item.state,
                        KlosterMCTSSearch._validate_prior_prob(item.prior_prob),
                        item.token_index,
                        dict(item.metadata),
                    )
                )
            elif isinstance(item, Mapping):
                raw_p = item.get("prior_prob", item.get("prior", item.get("prob")))
                parsed.append(
                    (
                        str(item.get("action", f"branch_{idx}")),
                        item.get("state"),
                        KlosterMCTSSearch._validate_prior_prob(raw_p),
                        item.get("token_index"),
                        dict(item.get("metadata") or {}),
                    )
                )
            elif isinstance(item, tuple):
                if len(item) == 2:
                    act, st = item
                    parsed.append((str(act), st, None, None, {}))
                elif len(item) >= 3:
                    act, st, raw_p = item[0], item[1], item[2]
                    tok_idx = int(item[3]) if len(item) >= 4 and item[3] is not None else None
                    parsed.append(
                        (
                            str(act),
                            st,
                            KlosterMCTSSearch._validate_prior_prob(raw_p),
                            tok_idx,
                            {},
                        )
                    )
                else:
                    raise ValueError(f"Unsupported tuple candidate shape: {item!r}")
            else:
                raise TypeError(
                    "expand_fn candidates must be ThoughtCandidate, Mapping, or (action, state[, prior]) tuples; "
                    f"got {type(item).__name__}"
                )

        # Fill missing priors uniformly and normalize only if total exceeds 1.0 (sub-probabilities allowed).
        missing_count = sum(1 for _, _, p, _, _ in parsed if p is None)
        explicit_sum = sum(p for _, _, p, _, _ in parsed if p is not None)
        if missing_count == len(parsed):
            priors = [1.0 / float(len(parsed))] * len(parsed)
        elif missing_count > 0:
            rem = max(0.0, 1.0 - explicit_sum)
            fill = rem / float(missing_count) if rem > 0.0 else 0.0
            priors = [p if p is not None else fill for _, _, p, _, _ in parsed]
        else:
            priors = [float(p) for _, _, p, _, _ in parsed]  # type: ignore[arg-type]

        total_p = sum(priors)
        if total_p > 1.0 + 1e-9:
            priors = [p / total_p for p in priors]

        return [
            (act, st, priors[i], tok_idx, meta)
            for i, (act, st, _, tok_idx, meta) in enumerate(parsed)
        ]

    @staticmethod
    def _parse_eval_output(raw: Any) -> _ParsedEval:
        if isinstance(raw, Mapping):
            val = KlosterMCTSSearch._validate_eval_value(raw.get("value", raw.get("score", 0.0)))
            obs = raw.get("observations")
            ev_counts = raw.get("evidence_counts")
            b_idx = raw.get("bin_index")
            return _ParsedEval(
                value=val,
                observations=tuple(int(x) for x in obs) if obs is not None else None,
                evidence_counts=tuple(int(x) for x in ev_counts) if ev_counts is not None else None,
                bin_index=int(b_idx) if b_idx is not None else None,
                is_terminal=bool(raw.get("is_terminal", False)),
                metadata=dict(raw.get("metadata") or {}),
            )
        if isinstance(raw, tuple) and len(raw) == 2:
            val_raw, second = raw
            val = KlosterMCTSSearch._validate_eval_value(val_raw)
            if isinstance(second, Sequence) and not isinstance(second, (str, bytes)):
                return _ParsedEval(value=val, observations=tuple(int(x) for x in second))
            if second is not None:
                return _ParsedEval(value=val, bin_index=int(second))
            return _ParsedEval(value=val)
        return _ParsedEval(value=KlosterMCTSSearch._validate_eval_value(raw))

    @staticmethod
    def _build_trajectory(
        nodes: Mapping[str, ThoughtNode],
        leaf_id: str,
    ) -> MCTSBranchTrajectory:
        chain: list[ThoughtNode] = []
        curr_id: str | None = leaf_id
        while curr_id is not None:
            node = nodes[curr_id]
            chain.append(node)
            curr_id = node.parent_id
        chain.reverse()

        actions = tuple(n.action for n in chain if n.action is not None)
        thoughts = tuple(n.voice_thought for n in chain if n.voice_thought)
        tok_path = tuple(n.token_index for n in chain[1:] if n.token_index is not None)
        leaf = chain[-1]
        return MCTSBranchTrajectory(
            branch_id=leaf.node_id,
            node_ids=tuple(n.node_id for n in chain),
            actions=actions,
            states=tuple(n.state for n in chain),
            depth=leaf.depth,
            joint_prob=leaf.joint_prob,
            mean_value=leaf.mean_value,
            visits=leaf.visits,
            pruned=leaf.pruned,
            prune_reason=leaf.prune_reason,
            voice_thoughts=thoughts,
            token_path=tok_path,
        )

    @staticmethod
    def _unpruned_children(nodes: Mapping[str, ThoughtNode], node: ThoughtNode) -> list[ThoughtNode]:
        return [nodes[cid] for cid in node.children_ids if not nodes[cid].pruned]

    def _subtree_has_expandable(self, nodes: Mapping[str, ThoughtNode], node: ThoughtNode) -> bool:
        if node.pruned or node.terminal:
            return False
        if not node.expanded:
            return True
        return any(self._subtree_has_expandable(nodes, nodes[cid]) for cid in node.children_ids)

    def _select_node(self, nodes: Mapping[str, ThoughtNode], root_id: str) -> ThoughtNode:
        """Select the next node to expand or re-evaluate via UCT."""
        curr = nodes[root_id]
        while True:
            if not curr.expanded:
                return curr
            unpruned = self._unpruned_children(nodes, curr)
            if not unpruned:
                return curr
            expandable = [c for c in unpruned if self._subtree_has_expandable(nodes, c)]
            pool = expandable if expandable else unpruned
            curr = max(
                pool,
                key=lambda c: (
                    c.uct_score(
                        curr.visits,
                        exploration_c=self.exploration_c,
                        prior_weight=self.prior_weight,
                    ),
                    c.prior_prob,
                    -c.depth,
                ),
            )
            if curr.terminal or (curr.expanded and not self._unpruned_children(nodes, curr)):
                return curr

    @staticmethod
    def _backpropagate(nodes: dict[str, ThoughtNode], node_id: str, value: float) -> None:
        curr_id: str | None = node_id
        while curr_id is not None:
            node = nodes[curr_id]
            node.visits += 1
            node.value_sum += float(value)
            curr_id = node.parent_id

    @staticmethod
    def _hypothesis_bin_for_node(
        nodes: Mapping[str, ThoughtNode],
        node: ThoughtNode,
        n_bins: int,
    ) -> int:
        """Determine the hypothesis bin index for a node using first branching depth."""
        if node.token_index is not None and node.depth == 1:
            return int(node.token_index) % n_bins
        chain: list[ThoughtNode] = []
        curr: ThoughtNode | None = node
        while curr is not None:
            chain.append(curr)
            curr = nodes[curr.parent_id] if curr.parent_id is not None else None
        chain.reverse()
        for ancestor in chain:
            if ancestor.parent_id is not None:
                parent = nodes[ancestor.parent_id]
                if len(parent.children_ids) > 1 or ancestor.depth == len(chain) - 1:
                    if ancestor.token_index is not None:
                        return int(ancestor.token_index) % n_bins
                    return parent.children_ids.index(ancestor.node_id) % n_bins
        return 0

    def _compute_multihorizon_snapshot(
        self,
        nodes: Mapping[str, ThoughtNode],
        root_id: str,
        tau: float,
        target_horizon: int,
    ) -> dict[str, Any]:
        """Run ``exact_multihorizon_accessible_volume`` directly over the current tree."""
        max_depth = max((n.depth for n in nodes.values()), default=0)
        eval_horizon = min(target_horizon, max(1, max_depth))

        def next_dist_fn(prefix: tuple[int, ...]) -> np.ndarray:
            curr = nodes[root_id]
            for pos, idx in enumerate(prefix):
                if curr.expanded and curr.child_priors:
                    if 0 <= idx < len(curr.children_ids):
                        curr = nodes[curr.children_ids[idx]]
                    else:
                        return np.array([0.0], dtype=np.float64)
                elif not curr.pruned and all(step == 0 for step in prefix[pos:]):
                    return np.array([1.0], dtype=np.float64)
                else:
                    return np.array([0.0], dtype=np.float64)

            if curr.expanded and curr.child_priors:
                return np.asarray(curr.child_priors, dtype=np.float64)
            if not curr.pruned:
                # Unexpanded surviving frontier or valid terminal leaf preserves its mass through horizon.
                return np.array([1.0], dtype=np.float64)
            return np.array([0.0], dtype=np.float64)

        return exact_multihorizon_accessible_volume(
            next_dist_fn,
            tau=tau,
            horizon=eval_horizon,
        )

    def _detect_fork_candidates(
        self,
        nodes: Mapping[str, ThoughtNode],
        multihorizon: Mapping[str, Any],
        tau: float,
        upper_bound: int,
    ) -> tuple[ForkCandidate, ...]:
        """Identify tree nodes where A_tau^(h) exhibits competing surviving hypotheses."""
        counts_by_h: list[int] = list(multihorizon.get("counts_by_h") or [])
        forks: list[ForkCandidate] = []

        for node in nodes.values():
            if node.pruned or not node.expanded:
                continue
            surviving = self._unpruned_children(nodes, node)
            if len(surviving) < 2:
                continue

            # Find best representative trajectory through each surviving child.
            competing: list[MCTSBranchTrajectory] = []
            for child in surviving:
                desc_leaves = [
                    n
                    for n in nodes.values()
                    if not n.pruned
                    and (n.node_id == child.node_id or self._is_descendant(nodes, child.node_id, n.node_id))
                    and (not n.expanded or not self._unpruned_children(nodes, n))
                ]
                best_leaf = max(
                    desc_leaves or [child],
                    key=lambda n: (n.mean_value, n.joint_prob, n.visits),
                )
                competing.append(self._build_trajectory(nodes, best_leaf.node_id))

            competing.sort(key=lambda b: (b.mean_value, b.joint_prob, b.visits), reverse=True)
            top_b, second_b = competing[0], competing[1]
            top_p = max(c.joint_prob for c in surviving)
            second_p = sorted((c.joint_prob for c in surviving), reverse=True)[1]
            prob_ratio = second_p / max(1e-12, top_p)
            val_gap = abs(top_b.mean_value - second_b.mean_value)

            horizon_idx = node.depth
            a_tau_h = (
                counts_by_h[horizon_idx]
                if horizon_idx < len(counts_by_h)
                else len(surviving)
            )
            delayed = bool(
                horizon_idx >= 1
                and horizon_idx < len(counts_by_h)
                and counts_by_h[horizon_idx] > counts_by_h[horizon_idx - 1]
            )

            # A fork is high-leverage when >= 2 hypotheses survive P(u) > tau and remain
            # competitive in probability ratio OR value proximity (or mark a delayed split).
            is_competing = (
                prob_ratio >= self.fork_prob_ratio_threshold
                or val_gap <= self.fork_value_gap_threshold
                or delayed
            )
            if not is_competing:
                continue

            kind_label = (
                f"delayed supercritical fork (A_tau^({horizon_idx + 1})={a_tau_h} > A_tau^({horizon_idx})={counts_by_h[horizon_idx - 1]})"
                if delayed
                else f"multi-branch fork (A_tau^({horizon_idx + 1})={a_tau_h})"
            )
            forks.append(
                ForkCandidate(
                    fork_id=f"fork_{node.node_id}_h{horizon_idx + 1}",
                    node_id=node.node_id,
                    depth=node.depth + 1,
                    horizon=horizon_idx + 1,
                    a_tau_at_horizon=int(a_tau_h),
                    tight_upper_bound=int(upper_bound),
                    competing_branches=tuple(competing),
                    probability_ratio=round(prob_ratio, 6),
                    value_gap=round(val_gap, 6),
                    delayed_fork=delayed,
                    reason=(
                        f"{kind_label} at node '{node.node_id}': "
                        f"{len(competing)} surviving branches with prob_ratio={prob_ratio:.3f}, "
                        f"value_gap={val_gap:.3f}."
                    ),
                )
            )

        forks.sort(
            key=lambda f: (
                not f.delayed_fork,
                f.value_gap,
                -f.probability_ratio,
                f.depth,
            )
        )
        return tuple(forks)

    @staticmethod
    def _is_descendant(nodes: Mapping[str, ThoughtNode], ancestor_id: str, node_id: str) -> bool:
        curr_id: str | None = node_id
        while curr_id is not None:
            if curr_id == ancestor_id:
                return True
            curr_id = nodes[curr_id].parent_id
        return False

    async def _run_voice_for_node(
        self,
        node: ThoughtNode,
        parent: ThoughtNode | None,
    ) -> dict[str, Any] | None:
        if not self.use_voice_bridge:
            return None
        prompt = (
            f"Evaluate MCTS thought branch '{node.action or 'root'}' "
            f"(depth={node.depth}, joint_prob={node.joint_prob:.4f}, "
            f"parent='{parent.action if parent else 'none'}', state={node.state!r})"
        )
        if self.voice_adapter is not None:
            resp: VoiceResponse = await self.voice_adapter.generate(
                prompt,
                context={
                    "node_id": node.node_id,
                    "depth": node.depth,
                    "joint_prob": node.joint_prob,
                    "action": node.action,
                },
            )
            thought = resp.thoughts[0] if resp.thoughts else resp.text
            node.voice_thought = thought
            return {
                "node_id": node.node_id,
                "mode": resp.mode,
                "model": resp.model,
                "thought": thought,
                "text": resp.text,
            }

        bridge = self.bridge or ZoeAntigravityBridge(mode="offline")
        eff_offline = bool(
            self.offline_only
            or bridge.mode == "offline"
            or self.bridge_mode == "offline"
        )
        eff_mode = "offline" if eff_offline else (self.bridge_mode or bridge.mode)
        turn_res = await bridge.arun_turn(
            prompt,
            mode=eff_mode,
            offline_only=eff_offline,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=False if eff_offline else self.probe_local,
        )
        thought = turn_res.thoughts[0] if turn_res.thoughts else turn_res.text
        node.voice_thought = thought
        return {
            "node_id": node.node_id,
            "mode": turn_res.resolution.selected_mode,
            "model": turn_res.resolution.config_class,
            "thought": thought,
            "text": turn_res.text,
        }

    def _allocate_scalar_observations(
        self,
        nodes: Mapping[str, ThoughtNode],
        evaluated_nodes: Sequence[tuple[ThoughtNode, _ParsedEval]],
        n_bins: int,
        residual_error: np.ndarray,
    ) -> list[int]:
        """Convert branch evaluation scores into deterministic Theorem 13 bin observations."""
        explicit_obs: list[int] = []
        for node, ev in evaluated_nodes:
            if ev.observations is not None:
                explicit_obs.extend(int(x) % n_bins for x in ev.observations)
            elif ev.evidence_counts is not None:
                for b_idx, cnt in enumerate(ev.evidence_counts):
                    if cnt > 0:
                        explicit_obs.extend([b_idx % n_bins] * int(cnt))
            elif ev.bin_index is not None:
                explicit_obs.extend([ev.bin_index % n_bins] * self.samples_per_eval)
        if explicit_obs:
            return explicit_obs

        # Aggregate empirical best-supporting value per hypothesis bin across surviving frontier leaves.
        bin_scores = np.full(n_bins, -np.inf, dtype=np.float64)
        for n in nodes.values():
            if n.pruned or n.parent_id is None or n.visits <= 0:
                continue
            if n.expanded and self._unpruned_children(nodes, n):
                continue
            b = self._hypothesis_bin_for_node(nodes, n, n_bins)
            if n.mean_value > bin_scores[b]:
                bin_scores[b] = n.mean_value

        for node, ev in evaluated_nodes:
            if node.parent_id is not None:
                b = self._hypothesis_bin_for_node(nodes, node, n_bins)
                if ev.value > bin_scores[b]:
                    bin_scores[b] = ev.value

        observed_mask = np.isfinite(bin_scores)
        if not np.any(observed_mask):
            probs = np.full(n_bins, 1.0 / float(n_bins), dtype=np.float64)
        else:
            baseline = float(np.min(bin_scores[observed_mask]))
            filled = np.where(observed_mask, bin_scores, baseline)
            spread = float(np.max(filled) - np.min(filled))
            if spread <= 1e-6:
                probs = np.full(n_bins, 1.0 / float(n_bins), dtype=np.float64)
            else:
                shifted = (filled - np.max(filled)) * self.softmax_beta
                weights = np.exp(shifted)
                probs = weights / float(np.sum(weights))

        # Error-diffused deterministic allocation matching probs * samples_per_eval exactly over time.
        desired = probs * float(self.samples_per_eval) + residual_error
        counts = np.zeros(n_bins, dtype=np.int64)
        for _ in range(self.samples_per_eval):
            idx = int(np.argmax(desired))
            counts[idx] += 1
            desired[idx] -= 1.0
        residual_error[:] = desired

        obs: list[int] = []
        for idx, bin_cnt in enumerate(counts):
            if int(bin_cnt) > 0:
                obs.extend([int(idx)] * int(bin_cnt))
        return obs

    async def arun(
        self,
        root_state: Any,
        expand_fn: Callable[..., Any],
        eval_fn: Callable[..., Any],
        *,
        tau: float = 0.08,
        max_iterations: int = 32,
        horizon: int | None = None,
        n_bins: int | None = None,
        max_samples: int | None = None,
        delta: float | None = None,
        blackboard: Any = None,
    ) -> MCTSSearchResult:
        """Execute async parallel UCT Tree-of-Thought search with Kloster stopping."""
        eff_tau = _validate_float_param(
            tau,
            name="tau",
            min_value=0.0,
            strict_min=True,
            max_value=1.0,
            strict_max=True,
        )
        eff_max_iterations = _validate_int_param(max_iterations, name="max_iterations", min_value=1)
        eff_horizon = (
            _validate_int_param(horizon, name="horizon", min_value=1)
            if horizon is not None
            else self.horizon
        )
        eff_n_bins_arg = (
            _validate_int_param(n_bins, name="n_bins", min_value=1)
            if n_bins is not None
            else None
        )
        eff_delta = (
            _validate_float_param(
                delta,
                name="delta",
                min_value=0.0,
                strict_min=True,
                max_value=1.0,
                strict_max=True,
            )
            if delta is not None
            else self.delta
        )
        explicit_max_samples = (
            _validate_int_param(max_samples, name="max_samples", min_value=1)
            if max_samples is not None
            else self.max_samples
        )
        tau = eff_tau
        max_iterations = eff_max_iterations
        n_bins = eff_n_bins_arg
        upper_bound = tight_strict_upper_bound(tau)

        root = ThoughtNode(
            node_id="root",
            state=root_state,
            action=None,
            token_index=None,
            parent_id=None,
            depth=0,
            prior_prob=1.0,
            joint_prob=1.0,
        )
        nodes: dict[str, ThoughtNode] = {"root": root}
        next_node_seq = 0
        parallel_batches = 0
        voice_traces: list[dict[str, Any]] = []
        a_tau_trajectory: list[dict[str, Any]] = []
        stopping_history: list[dict[str, Any]] = []

        controller: KlosterSequentialStoppingController | None = None
        residual_error: np.ndarray | None = None
        last_verdict: dict[str, Any] = {
            "action": "GATHER_MORE",
            "samples": 0,
            "z_kloster": 0.0,
            "z_threshold": 0.0,
            "excess_chi2": 0.0,
            "m4_root": 0.0,
            "estimated_s_min": 0,
            "budget_fraction_used": 0.0,
        }
        iterations_run = 0
        mass_collapsed = False

        async def _eval_single(node: ThoughtNode, parent: ThoughtNode | None) -> tuple[ThoughtNode, _ParsedEval, dict[str, Any] | None]:
            eval_coro = _maybe_await(_call_with_optional_node(eval_fn, node.state, node))
            if self.use_voice_bridge:
                raw_eval, v_trace = await asyncio.gather(
                    eval_coro,
                    self._run_voice_for_node(node, parent),
                )
            else:
                raw_eval = await eval_coro
                v_trace = None
            return node, self._parse_eval_output(raw_eval), v_trace

        for iteration in range(1, max_iterations + 1):
            iterations_run = iteration
            selected = self._select_node(nodes, "root")
            evaluated_batch: list[tuple[ThoughtNode, _ParsedEval]] = []

            if not selected.expanded:
                raw_cands = await _maybe_await(
                    _call_with_optional_node(expand_fn, selected.state, selected)
                )
                candidates = self._normalize_candidates(raw_cands)
                selected.expanded = True

                if not candidates:
                    selected.terminal = True
                    node, ev, v_trace = await _eval_single(
                        selected,
                        nodes[selected.parent_id] if selected.parent_id else None,
                    )
                    if v_trace is not None:
                        voice_traces.append(v_trace)
                    self._backpropagate(nodes, node.node_id, ev.value)
                    evaluated_batch.append((node, ev))
                else:
                    child_priors: list[float] = []
                    surviving_children: list[ThoughtNode] = []
                    for c_idx, (act, st, prior_p, tok_idx, meta) in enumerate(candidates):
                        next_node_seq += 1
                        cid = f"n_{next_node_seq}"
                        eff_tok = c_idx if tok_idx is None else int(tok_idx)
                        joint_p = selected.joint_prob * prior_p
                        pruned = joint_p <= tau
                        prune_reason = (
                            f"kloster_prefix_prune: P(u)={joint_p:.6f} <= tau={tau:.6f}"
                            if pruned
                            else None
                        )
                        child = ThoughtNode(
                            node_id=cid,
                            state=st,
                            action=act,
                            token_index=eff_tok,
                            parent_id=selected.node_id,
                            depth=selected.depth + 1,
                            prior_prob=prior_p,
                            joint_prob=joint_p,
                            pruned=pruned,
                            prune_reason=prune_reason,
                            metadata=meta,
                        )
                        nodes[cid] = child
                        selected.children_ids.append(cid)
                        selected.child_id_by_token[eff_tok] = cid
                        child_priors.append(prior_p)
                        if not pruned:
                            surviving_children.append(child)

                    selected.child_priors = tuple(child_priors)

                    if surviving_children:
                        parallel_batches += 1
                        results = await asyncio.gather(
                            *[_eval_single(child, selected) for child in surviving_children]
                        )
                        for child, ev, v_trace in results:
                            if ev.is_terminal:
                                child.terminal = True
                            child.metadata.update(ev.metadata)
                            if v_trace is not None:
                                voice_traces.append(v_trace)
                            self._backpropagate(nodes, child.node_id, ev.value)
                            evaluated_batch.append((child, ev))
                    else:
                        # All candidate children fell below tau: mark branch as collapsed/terminal.
                        selected.terminal = True
                        node, ev, v_trace = await _eval_single(
                            selected,
                            nodes[selected.parent_id] if selected.parent_id else None,
                        )
                        if v_trace is not None:
                            voice_traces.append(v_trace)
                        self._backpropagate(nodes, node.node_id, ev.value)
                        evaluated_batch.append((node, ev))
            else:
                # Re-evaluate selected terminal/leaf node to accumulate Theorem 13 evidence.
                node, ev, v_trace = await _eval_single(
                    selected,
                    nodes[selected.parent_id] if selected.parent_id else None,
                )
                if v_trace is not None:
                    voice_traces.append(v_trace)
                self._backpropagate(nodes, node.node_id, ev.value)
                evaluated_batch.append((node, ev))

            # Lazily initialize Theorem 13 controller once root branching factor is known.
            if controller is None:
                inferred_bins = self.n_bins if self.n_bins is not None else (
                    n_bins if n_bins is not None else max(4, len(root.children_ids))
                )
                eff_bins = max(2, int(inferred_bins))
                eff_max_s = (
                    int(explicit_max_samples)
                    if explicit_max_samples is not None
                    else max_iterations * self.samples_per_eval
                )
                controller = KlosterSequentialStoppingController(
                    n_bins=eff_bins,
                    delta=eff_delta,
                    max_samples=max(12, eff_max_s),
                )
                residual_error = np.zeros(eff_bins, dtype=np.float64)

            assert controller is not None and residual_error is not None
            obs_batch = self._allocate_scalar_observations(
                nodes, evaluated_batch, controller.n_bins, residual_error
            )
            last_verdict = controller.observe_batch(obs_batch)
            last_verdict = {**last_verdict, "iteration": iteration}
            stopping_history.append(last_verdict)

            mh_snap = self._compute_multihorizon_snapshot(nodes, "root", tau, eff_horizon)
            a_tau_leaf = mh_snap["counts_by_h"][-1] if mh_snap["counts_by_h"] else 0
            a_tau_trajectory.append(
                {
                    "iteration": iteration,
                    "tau": float(tau),
                    "horizon": int(mh_snap["horizon"]),
                    "counts_by_h": list(mh_snap["counts_by_h"]),
                    "frontier_mass_by_h": list(mh_snap["frontier_mass_by_h"]),
                    "tight_upper_bound": int(mh_snap["tight_upper_bound"]),
                    "forward_calls": int(mh_snap["forward_calls"]),
                    "theoretical_max_calls": int(mh_snap["theoretical_max_calls"]),
                    "bound_violations": int(mh_snap["bound_violations"]),
                    "a_tau_leaf": int(a_tau_leaf),
                    "pruned_count": sum(1 for n in nodes.values() if n.pruned),
                }
            )

            # Check mass collapse (every child of root pruned) or Theorem 13 early stopping.
            if root.expanded and not self._unpruned_children(nodes, root):
                mass_collapsed = True
                break
            if last_verdict["action"] in ("DECIDE_SIGNAL", "ABSTAIN_INSUFFICIENT_EVIDENCE"):
                break

        assert controller is not None
        final_mh = self._compute_multihorizon_snapshot(nodes, "root", tau, eff_horizon)
        raw_chi2 = kloster_unbiased_chi2_stats(controller.counts)

        if mass_collapsed:
            decision = "ABSTAIN_INSUFFICIENT_EVIDENCE"
        elif last_verdict["action"] in ("DECIDE_SIGNAL", "ABSTAIN_INSUFFICIENT_EVIDENCE"):
            decision = str(last_verdict["action"])
        elif explicit_max_samples is None:
            # Iteration budget exhausted without crossing Theorem 13 stopping boundary.
            decision = "ABSTAIN_INSUFFICIENT_EVIDENCE"
        else:
            decision = str(last_verdict["action"])

        chi2_stats: dict[str, Any] = {
            **raw_chi2,
            **last_verdict,
            "action": decision,
            "counts": [int(x) for x in controller.counts.tolist()],
        }

        pruned_nodes = [n for n in nodes.values() if n.pruned]
        pruned_branches = tuple(self._build_trajectory(nodes, n.node_id) for n in pruned_nodes)

        surviving_leaf_nodes = [
            n
            for n in nodes.values()
            if n.parent_id is not None
            and not n.pruned
            and (not n.expanded or not self._unpruned_children(nodes, n))
        ]
        surviving_branches_list = [
            self._build_trajectory(nodes, n.node_id) for n in surviving_leaf_nodes
        ]
        surviving_branches_list.sort(
            key=lambda b: (b.mean_value, b.visits, b.joint_prob),
            reverse=True,
        )
        surviving_branches = tuple(surviving_branches_list)
        best_branch = surviving_branches[0] if surviving_branches else None

        fork_candidates = self._detect_fork_candidates(nodes, final_mh, tau, upper_bound)

        voice_mode = "disabled"
        if self.use_voice_bridge:
            if voice_traces:
                voice_mode = str(voice_traces[0].get("mode", "offline"))
            elif self.offline_only or self.bridge_mode == "offline":
                voice_mode = "offline"
            elif self.bridge_mode is not None:
                voice_mode = self.bridge_mode
            elif self.bridge is not None:
                voice_mode = self.bridge.mode
            else:
                voice_mode = "offline"

        constitutional = bridge_constitutional_metadata(cloud_tokens_used=0)
        constitutional["measurement_only"] = True
        constitutional["review_required"] = True

        counts_by_h_tuple = tuple(int(c) for c in (final_mh.get("counts_by_h") or ()))

        eff_bb = blackboard if blackboard is not None else self.blackboard
        blackboard_measurement_id: str | None = None
        if eff_bb is not None and hasattr(eff_bb, "post_measurement"):
            root_desc = (
                root_state
                if isinstance(root_state, str)
                else repr(root_state)[:256]
            )
            bb_value = {
                "contract": MCTS_KLOSTER_CONTRACT,
                "decision": decision,
                "tau": float(tau),
                "tight_upper_bound": int(upper_bound),
                "iterations_run": int(iterations_run),
                "counts_by_h": list(counts_by_h_tuple),
                "frontier_mass_by_h": [
                    float(m) for m in (final_mh.get("frontier_mass_by_h") or ())
                ],
                "chi2_stats": {
                    str(k): (
                        [int(x) for x in v]
                        if isinstance(v, list)
                        else (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                    )
                    for k, v in chi2_stats.items()
                },
                "best_branch_actions": (
                    list(best_branch.actions) if best_branch is not None else None
                ),
                "best_branch_value": (
                    round(float(best_branch.mean_value), 6)
                    if best_branch is not None
                    else None
                ),
                "pruned_count": len(pruned_branches),
                "fork_count": len(fork_candidates),
                "fork_summaries": [f.to_summary() for f in fork_candidates],
            }
            rec = eff_bb.post_measurement(
                source_agent="kloster_mcts_search",
                input_desc=f"mcts_search(root={root_desc}, tau={tau}, max_iterations={max_iterations})",
                method="KlosterMCTSSearch.arun",
                scope=(
                    f"iterations={iterations_run}/{max_iterations}, "
                    f"nodes={len(nodes)}, parallel_batches={parallel_batches}, "
                    f"pruned={len(pruned_branches)}, forks={len(fork_candidates)}"
                ),
                limitations=(
                    "MCTS and Theorem 13 sequential stopping outputs are bounded search "
                    "measurements only (CONSTITUTION.md Art. III: measurement != evidence "
                    "!= belief update != action; external_actions=0, review_required=True)."
                ),
                value=bb_value,
                sampled_only=False,
                metadata={
                    "a_tau_trajectory_len": len(a_tau_trajectory),
                    "voice_mode": voice_mode,
                    "fork_ids": [f.fork_id for f in fork_candidates],
                },
            )
            blackboard_measurement_id = getattr(rec, "record_id", None)

        return MCTSSearchResult(
            contract=MCTS_KLOSTER_CONTRACT,
            decision=decision,
            tau=float(tau),
            tight_upper_bound=int(upper_bound),
            iterations_run=iterations_run,
            max_iterations=int(max_iterations),
            total_nodes=len(nodes),
            expanded_nodes=sum(1 for n in nodes.values() if n.expanded),
            parallel_batches=parallel_batches,
            a_tau_trajectory=a_tau_trajectory,
            multihorizon_volume=final_mh,
            chi2_stats=chi2_stats,
            stopping_history=stopping_history,
            best_branch=best_branch,
            surviving_branches=surviving_branches,
            pruned_branches=pruned_branches,
            fork_candidates=fork_candidates,
            voice_mode=voice_mode,
            voice_traces=tuple(voice_traces),
            nodes=nodes,
            constitutional=constitutional,
            counts_by_h=counts_by_h_tuple,
            blackboard_measurement_id=blackboard_measurement_id,
        )

    def run(
        self,
        root_state: Any,
        expand_fn: Callable[..., Any],
        eval_fn: Callable[..., Any],
        *,
        tau: float = 0.08,
        max_iterations: int = 32,
        horizon: int | None = None,
        n_bins: int | None = None,
        max_samples: int | None = None,
        delta: float | None = None,
        blackboard: Any = None,
    ) -> MCTSSearchResult:
        """Synchronous wrapper around ``arun`` safe inside or outside an active event loop."""
        return run_coro_sync(
            self.arun(
                root_state,
                expand_fn,
                eval_fn,
                tau=tau,
                max_iterations=max_iterations,
                horizon=horizon,
                n_bins=n_bins,
                max_samples=max_samples,
                delta=delta,
                blackboard=blackboard,
            )
        )


__all__ = [
    "ForkCandidate",
    "KlosterMCTSSearch",
    "MCTSBranchTrajectory",
    "MCTSSearchResult",
    "MCTS_KLOSTER_CONTRACT",
    "ThoughtCandidate",
    "ThoughtNode",
]

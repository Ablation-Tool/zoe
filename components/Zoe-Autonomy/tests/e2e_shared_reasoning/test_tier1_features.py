"""Tier 1 Opaque-Box E2E Tests: Architecture Features 1-9 (F3-F11) & Unified Composer/Docs/Verifier (F12b)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
import inspect
import json
import subprocess
from typing import Any, Callable, Sequence

import pytest

from .conftest import (
    PYTHON_BIN,
    assert_constitutional_invariants,
    call_with_supported_kwargs,
    monorepo_env,
    require_artifact,
    require_shared_reasoning,
    run_async,
)


# =============================================================================
# Opaque-Box Contract Inspection Helpers
# =============================================================================


def _to_plain(obj: Any) -> Any:
    """Convert dataclasses, pydantic models, or custom objects into plain Python structures."""
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_plain(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return _to_plain(obj.model_dump())
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _to_plain(obj.to_dict())
    if isinstance(obj, Mapping):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


def _pick(obj: Any, *names: str, default: Any = None) -> Any:
    """Read the first present key/attribute among `names` from a mapping or object."""
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    plain = _to_plain(obj)
    if isinstance(plain, Mapping):
        for name in names:
            if name in plain:
                return plain[name]
    return default


def _invoke_callable(fn: Callable[..., Any], *args: Any, **candidates: Any) -> Any:
    """Invoke a sync or async callable filtering kwargs to supported signature parameters."""
    res = call_with_supported_kwargs(fn, *args, **candidates)
    if inspect.isawaitable(res):
        return run_async(res)
    return res


def _invoke_first_method(obj: Any, method_names: Sequence[str], *args: Any, **candidates: Any) -> Any:
    """Find and invoke the first existing method on `obj` with supported kwargs."""
    for name in method_names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return _invoke_callable(fn, *args, **candidates)
    raise AssertionError(f"{type(obj).__name__} exposes none of expected methods {tuple(method_names)}")


def _instantiate_engine(cls: type[Any], repo_root: Any, state_dir: Any, **extra: Any) -> Any:
    """Instantiate a shared_reasoning engine class with isolated state and offline defaults."""
    return call_with_supported_kwargs(
        cls,
        repo_root=repo_root,
        root=repo_root,
        zoe_root=repo_root,
        state_dir=state_dir,
        mode="offline",
        offline_only=True,
        **extra,
    )


# =============================================================================
# F3 — Arch 1: AlphaEvolve / FunSearch Loop (alpha_evolve.py / AlphaEvolveLoop)
# =============================================================================


def test_f3_alpha_evolve_public_export_and_instantiation(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("alpha_evolve", "AlphaEvolveLoop")
    pkg_cls = require_shared_reasoning(symbol="AlphaEvolveLoop")
    assert mod_cls is pkg_cls

    loop = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert loop is not None
    assert (
        callable(getattr(loop, "run", None))
        or callable(getattr(loop, "step", None))
        or callable(getattr(loop, "evolve", None))
    )


def test_f3_alpha_evolve_deterministic_candidate_generation_and_ast_verification(repo_root, isolated_state_dir):
    AlphaEvolveLoop = require_shared_reasoning("alpha_evolve", "AlphaEvolveLoop")
    loop = _instantiate_engine(AlphaEvolveLoop, repo_root, isolated_state_dir, seed=7)

    safe_candidate = (
        "def candidate_score(x, y):\n"
        "    return clip(sq(x) + pos(y), 0.0, 100.0)\n"
    )
    test_cases = [
        {"args": (2.0, 3.0), "expected": 7.0},
        {"args": (-1.0, 4.0), "expected": 5.0},
    ]
    result = _invoke_first_method(
        loop,
        ("run", "step", "evolve"),
        task="Synthesize bounded quadratic scoring function",
        prompt="Synthesize bounded quadratic scoring function",
        spec="Synthesize bounded quadratic scoring function",
        seed_programs=[safe_candidate],
        seed_candidates=[safe_candidate],
        candidates=[safe_candidate],
        test_cases=test_cases,
        generations=2,
        max_generations=2,
        steps=2,
        mode="offline",
    )
    assert result is not None
    plain = _to_plain(result)
    assert isinstance(plain, Mapping)

    best = _pick(result, "best_candidate", "winner", "best", "top_candidate", "best_program")
    archive = _pick(result, "archive", "elites", "population", "verified_candidates", "candidates")
    assert best is not None or (isinstance(archive, (list, dict)) and len(archive) > 0), (
        f"Expected verified candidate or non-empty archive from AlphaEvolveLoop, got {plain}"
    )

    if best is not None:
        fitness = _pick(best, "fitness", "score")
        if fitness is not None:
            assert isinstance(fitness, (int, float))
            assert fitness == fitness  # finite non-NaN check


def test_f3_alpha_evolve_archive_fitness_retention_and_lineage_provenance(repo_root, isolated_state_dir):
    AlphaEvolveLoop = require_shared_reasoning("alpha_evolve", "AlphaEvolveLoop")
    loop = _instantiate_engine(AlphaEvolveLoop, repo_root, isolated_state_dir, seed=11)

    safe_candidate = (
        "def poly_score(x):\n"
        "    return sq(x) + 1.0\n"
    )
    test_cases = [
        {"args": (2.0,), "expected": 5.0},
        {"args": (3.0,), "expected": 10.0},
    ]
    res = _invoke_first_method(
        loop,
        ("run", "evolve", "step"),
        task="Optimize safe polynomial scorer",
        prompt="Optimize safe polynomial scorer",
        seed_programs=[safe_candidate],
        seed_candidates=[safe_candidate],
        test_cases=test_cases,
        generations=3,
        max_generations=3,
        steps=3,
        mode="offline",
    )
    plain = _to_plain(res)
    archive = _pick(res, "archive", "elites", "cells", "lineage", "history", "generations")
    assert archive is not None and len(archive) >= 1, f"Expected archive/lineage records, got {plain}"

    serialized = json.dumps(plain, default=str).lower()
    assert any(tok in serialized for tok in ("generation", "parent", "lineage", "fitness", "cell", "provenance")), (
        f"Expected fitness/lineage provenance metadata in AlphaEvolveLoop output: {plain}"
    )


def test_f3_alpha_evolve_preserves_negative_rejected_candidates_honestly(repo_root, isolated_state_dir):
    AlphaEvolveLoop = require_shared_reasoning("alpha_evolve", "AlphaEvolveLoop")
    loop = _instantiate_engine(AlphaEvolveLoop, repo_root, isolated_state_dir, seed=13)

    valid_src = "def score_fn(x):\n    return pos(x) + 1.0\n"
    unsafe_src = "import os\ndef score_fn(x):\n    return os.getpid()\n"
    test_cases = [
        {"args": (2.0,), "expected": 3.0},
        {"args": (0.0,), "expected": 1.0},
    ]

    res = _invoke_first_method(
        loop,
        ("run", "step", "evolve"),
        task="Evaluate safe vs unsafe AST candidates",
        prompt="Evaluate safe vs unsafe AST candidates",
        seed_programs=[unsafe_src, valid_src],
        seed_candidates=[unsafe_src, valid_src],
        candidates=[unsafe_src, valid_src],
        test_cases=test_cases,
        generations=2,
        max_generations=2,
        steps=2,
        mode="offline",
    )
    plain = _to_plain(res)
    rejected = _pick(res, "rejected", "rejected_candidates", "negative_results", "failed_candidates", "eliminated")
    best = _pick(res, "best_candidate", "winner", "best", "top_candidate", "best_program")
    best_src = _pick(best, "source", "code", default=str(best)) if best is not None else ""
    assert "import os" not in str(best_src), "Unsafe AST candidate must never become best candidate"

    # Constitution II.4: preserve useful negative/rejected candidates honestly
    serialized = json.dumps(plain, default=str).lower()
    if rejected is not None:
        assert isinstance(rejected, (list, tuple, dict))
    assert any(tok in serialized for tok in ("reject", "negative", "unsafe", "failed", "eliminated", "disqualified")), (
        f"Expected honest negative/rejected candidate tracking (Constitution II.4), got {plain}"
    )


def test_f3_alpha_evolve_constitutional_invariants(repo_root, isolated_state_dir):
    AlphaEvolveLoop = require_shared_reasoning("alpha_evolve", "AlphaEvolveLoop")
    loop = _instantiate_engine(AlphaEvolveLoop, repo_root, isolated_state_dir, seed=5)
    safe_candidate = "def id_fn(x):\n    return x\n"
    test_cases = [{"args": (1.0,), "expected": 1.0}]
    res = _invoke_first_method(
        loop,
        ("run", "step", "evolve"),
        task="Constitutional offline evolution check",
        prompt="Constitutional offline evolution check",
        seed_programs=[safe_candidate],
        seed_candidates=[safe_candidate],
        test_cases=test_cases,
        generations=1,
        max_generations=1,
        steps=1,
        mode="offline",
    )
    assert_constitutional_invariants(res, require_offline=True)
    plain = _to_plain(res)
    if isinstance(plain, Mapping):
        if "external_actions" in plain:
            assert plain["external_actions"] == 0
        if "sentience_claimed" in plain:
            assert plain["sentience_claimed"] is False


# =============================================================================
# F4 — Arch 2: Live Process Supervision (process_supervision.py / LiveProcessSupervisor)
# =============================================================================


def test_f4_process_supervision_public_export_and_antigravity_hooks_integration(repo_root, isolated_state_dir):
    from google.antigravity.hooks import (
        PostToolCallHook,
        PostTurnHook,
        PreToolCallDecideHook,
        PreTurnHook,
    )

    mod_cls = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")
    pkg_cls = require_shared_reasoning(symbol="LiveProcessSupervisor")
    assert mod_cls is pkg_cls

    supervisor = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert supervisor is not None

    hook_candidates = []
    for attr in dir(supervisor):
        if attr.startswith("_"):
            continue
        val = getattr(supervisor, attr, None)
        if isinstance(val, (PreTurnHook, PostTurnHook, PreToolCallDecideHook, PostToolCallHook)):
            hook_candidates.append(val)
    for method_name in ("build_hooks", "get_hooks", "hooks", "as_hooks"):
        fn = getattr(supervisor, method_name, None)
        if callable(fn):
            built = fn()
            if isinstance(built, Mapping):
                hook_candidates.extend(built.values())
            elif isinstance(built, (list, tuple)):
                hook_candidates.extend(built)

    # Either exposes real Antigravity hook instances directly or exposes an Antigravity Agent builder/runner
    has_hook_objs = any(
        isinstance(h, (PreTurnHook, PostTurnHook, PreToolCallDecideHook, PostToolCallHook))
        for h in hook_candidates
    )
    has_supervision_api = callable(getattr(supervisor, "run", None)) or callable(
        getattr(supervisor, "supervise", None)
    )
    assert has_hook_objs or has_supervision_api


def _drive_supervisor_hooks_turn(supervisor: Any, repo_root: Any) -> Any:
    """Exercise LiveProcessSupervisor either via a high-level run method or its Antigravity hooks."""
    for name in ("run", "supervise", "supervise_turn", "step", "audit"):
        fn = getattr(supervisor, name, None)
        if callable(fn):
            return _invoke_callable(
                fn,
                prompt="Inspect CONSTITUTION.md epistemic firewall offline",
                task="Inspect CONSTITUTION.md epistemic firewall offline",
                mode="offline",
            )

    from google.antigravity.hooks import (
        PostToolCallHook,
        PostTurnHook,
        PreToolCallDecideHook,
        PreTurnHook,
    )
    from google.antigravity.hooks.hooks import HookContext, SessionContext, TurnContext
    from google.antigravity.types import BuiltinTools, ToolCall, ToolResult

    hooks_collection: list[Any] = []
    if callable(getattr(supervisor, "build_hooks", None)):
        built = supervisor.build_hooks()
        hooks_collection.extend(built.values() if isinstance(built, Mapping) else built)
    else:
        for attr in dir(supervisor):
            if attr.startswith("_"):
                continue
            val = getattr(supervisor, attr, None)
            if isinstance(val, (PreTurnHook, PostTurnHook, PreToolCallDecideHook, PostToolCallHook)):
                hooks_collection.append(val)

    ctx = HookContext(parent=TurnContext(SessionContext()))
    safe_call = ToolCall(
        id="tc_stream_1",
        name=BuiltinTools.VIEW_FILE,
        args={"AbsolutePath": str(repo_root / "docs" / "CONSTITUTION.md")},
    )
    safe_res = ToolResult(
        id="tc_stream_1",
        name=BuiltinTools.VIEW_FILE,
        result="Epistemic firewall: measurement != evidence != belief update != action",
    )

    for hook in hooks_collection:
        if isinstance(hook, PreTurnHook):
            run_async(hook.run(ctx, "Inspect CONSTITUTION.md epistemic firewall offline"))
        elif isinstance(hook, PreToolCallDecideHook):
            run_async(hook.run(ctx, safe_call))
        elif isinstance(hook, PostToolCallHook):
            run_async(hook.run(ctx, safe_res))
        elif isinstance(hook, PostTurnHook):
            run_async(hook.run(ctx, "Verified epistemic firewall offline with 0 external actions."))

    for summary_method in ("summary", "get_trace", "trace", "audit_report", "report", "export_trace", "to_dict"):
        fn = getattr(supervisor, summary_method, None)
        if callable(fn):
            return fn()
    return supervisor


def test_f4_process_supervision_streaming_thought_and_tool_call_capture(repo_root, isolated_state_dir):
    LiveProcessSupervisor = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")
    supervisor = _instantiate_engine(LiveProcessSupervisor, repo_root, isolated_state_dir)

    res = _drive_supervisor_hooks_turn(supervisor, repo_root)
    assert res is not None
    plain = _to_plain(res)
    events = _pick(
        res,
        "events",
        "trace",
        "audit_trace",
        "audit_log",
        "tool_calls",
        "thoughts",
        "steps",
        "records",
        "entries",
    )
    if events is None:
        events = _pick(
            supervisor,
            "events",
            "trace",
            "audit_trace",
            "audit_log",
            "tool_calls",
            "thoughts",
            "records",
            "entries",
        )
    assert events is not None and len(events) >= 1, f"Expected captured streaming/audit events, got {plain}"


def test_f4_process_supervision_mutual_zoe_antigravity_audit_trace(repo_root, isolated_state_dir):
    LiveProcessSupervisor = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")
    supervisor = _instantiate_engine(LiveProcessSupervisor, repo_root, isolated_state_dir)

    res = _drive_supervisor_hooks_turn(supervisor, repo_root)
    serialized = (
        json.dumps(_to_plain(res), default=str) + " " + json.dumps(_to_plain(supervisor), default=str)
    ).lower()
    assert any(tok in serialized for tok in ("zoe", "audit", "firewall", "antigravity", "view_file")), (
        f"Expected mutual Zoe <-> Antigravity audit markers in supervision result: {serialized}"
    )


def test_f4_process_supervision_policy_allows_safe_readonly_operations(repo_root, isolated_state_dir):
    LiveProcessSupervisor = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")

    from google.antigravity.hooks import PreToolCallDecideHook
    from google.antigravity.hooks.hooks import HookContext, SessionContext, TurnContext
    from google.antigravity.types import BuiltinTools, HookResult, ToolCall

    supervisor = _instantiate_engine(LiveProcessSupervisor, repo_root, isolated_state_dir)

    safe_call = ToolCall(
        id="tc_safe_read_1",
        name=BuiltinTools.VIEW_FILE,
        args={"AbsolutePath": str(repo_root / "docs" / "CONSTITUTION.md")},
    )

    decide_hook = None
    for attr in dir(supervisor):
        if attr.startswith("_"):
            continue
        val = getattr(supervisor, attr, None)
        if isinstance(val, PreToolCallDecideHook):
            decide_hook = val
            break
    if decide_hook is None and callable(getattr(supervisor, "build_hooks", None)):
        built = supervisor.build_hooks()
        vals = built.values() if isinstance(built, Mapping) else built
        for val in vals:
            if isinstance(val, PreToolCallDecideHook):
                decide_hook = val
                break

    if decide_hook is not None:
        ctx = HookContext(parent=TurnContext(SessionContext()))
        hook_res = run_async(decide_hook.run(ctx, safe_call))
        assert isinstance(hook_res, HookResult)
        assert hook_res.allow is True
    else:
        eval_res = _invoke_first_method(
            supervisor,
            ("evaluate_tool_call", "check_tool_call", "decide_tool_call", "authorize_tool_call"),
            safe_call,
            tool_call=safe_call,
        )
        allowed = _pick(eval_res, "allow", "allowed", "approved")
        assert allowed is True


def test_f4_process_supervision_constitutional_invariants(repo_root, isolated_state_dir):
    LiveProcessSupervisor = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")
    supervisor = _instantiate_engine(LiveProcessSupervisor, repo_root, isolated_state_dir)
    res = _drive_supervisor_hooks_turn(supervisor, repo_root)
    assert_constitutional_invariants(res, require_offline=True)


# =============================================================================
# F5 — Arch 3: MCTS / ToT with Kloster Stopping (mcts_kloster.py / KlosterMCTSSearch)
# =============================================================================


def _biased_tree_callbacks():
    """Deterministic expand/eval pair where branch 'branch_alpha' strongly dominates."""
    branches = (
        ("branch_alpha", "branch_alpha", 0.72),
        ("branch_beta", "branch_beta", 0.14),
        ("branch_gamma", "branch_gamma", 0.09),
        ("branch_delta", "branch_delta", 0.05),
    )

    def expand_fn(state: Any):
        if state in ("root", "", None):
            return list(branches)
        return []

    def eval_fn(state: Any, step_idx: int = 0):
        if state == "branch_alpha":
            return 0.95
        if state == "branch_beta":
            return 0.15
        if state == "branch_gamma":
            return 0.08
        if state == "branch_delta":
            return 0.04
        return 0.25

    return expand_fn, eval_fn


def test_f5_mcts_kloster_public_export_and_search_result_schema():
    KlosterMCTSSearch = require_shared_reasoning("mcts_kloster", "KlosterMCTSSearch")
    pkg_cls = require_shared_reasoning(symbol="KlosterMCTSSearch")
    assert KlosterMCTSSearch is pkg_cls

    search = call_with_supported_kwargs(KlosterMCTSSearch, seed=42)
    expand_fn, eval_fn = _biased_tree_callbacks()
    result = search.run(
        root_state="root",
        expand_fn=expand_fn,
        eval_fn=lambda s: eval_fn(s),
        tau=0.08,
        max_iterations=80,
    )
    for attr in ("decision", "a_tau_trajectory", "chi2_stats", "best_branch", "fork_candidates"):
        assert hasattr(result, attr) or (isinstance(result, Mapping) and attr in result), (
            f"MCTSSearchResult missing required field {attr!r}"
        )


def test_f5_mcts_kloster_multihorizon_a_tau_tight_upper_bound():
    from zoe_autonomy.l5_phase6_multihorizon_metacognition import tight_strict_upper_bound

    KlosterMCTSSearch = require_shared_reasoning("mcts_kloster", "KlosterMCTSSearch")
    search = call_with_supported_kwargs(KlosterMCTSSearch, seed=42)
    expand_fn, eval_fn = _biased_tree_callbacks()

    for tau in (0.08, 0.20):
        expected_cap = tight_strict_upper_bound(tau)
        result = search.run(
            root_state="root",
            expand_fn=expand_fn,
            eval_fn=lambda s: eval_fn(s),
            tau=tau,
            max_iterations=64,
        )
        traj = _pick(result, "a_tau_trajectory")
        assert isinstance(traj, (list, tuple)) and len(traj) >= 1
        checked = 0
        for entry in traj:
            if isinstance(entry, Mapping):
                counts_by_h = entry.get("counts_by_h")
                if counts_by_h is not None:
                    assert isinstance(counts_by_h, (list, tuple)) and len(counts_by_h) >= 1
                    for c in counts_by_h:
                        assert 0 <= int(c) <= expected_cap, (
                            f"counts_by_h entry {c} violated Kloster tight upper bound ceil(1/{tau})-1={expected_cap}"
                        )
                        checked += 1
                a_tau_leaf = entry.get("a_tau_leaf")
                if a_tau_leaf is not None:
                    assert 0 <= int(a_tau_leaf) <= expected_cap, (
                        f"a_tau_leaf={a_tau_leaf} violated Kloster tight upper bound ceil(1/{tau})-1={expected_cap}"
                    )
                    checked += 1
                if "bound_violations" in entry and entry["bound_violations"] is not None:
                    assert int(entry["bound_violations"]) == 0, (
                        f"MCTS recorded bound_violations={entry['bound_violations']} at tau={tau}"
                    )
                    checked += 1
                if "tight_upper_bound" in entry and entry["tight_upper_bound"] is not None:
                    assert int(entry["tight_upper_bound"]) == expected_cap
                val = _pick(entry, "a_tau", "accessible_count", "count")
                if val is not None:
                    assert 0 <= int(val) <= expected_cap, (
                        f"A_tau={val} violated Kloster tight upper bound ceil(1/{tau})-1={expected_cap}"
                    )
                    checked += 1
            elif isinstance(entry, (int, float)):
                assert 0 <= int(entry) <= expected_cap, (
                    f"A_tau={entry} violated Kloster tight upper bound ceil(1/{tau})-1={expected_cap}"
                )
                checked += 1
        assert checked > 0, f"No a_tau_trajectory counts checked at tau={tau}: {traj!r}"


def test_f5_mcts_kloster_theorem13_stopping_reaches_decide_signal_on_biased_branch():
    KlosterMCTSSearch = require_shared_reasoning("mcts_kloster", "KlosterMCTSSearch")
    search = call_with_supported_kwargs(KlosterMCTSSearch, seed=7)
    expand_fn, eval_fn = _biased_tree_callbacks()

    result = search.run(
        root_state="root",
        expand_fn=expand_fn,
        eval_fn=lambda s: eval_fn(s),
        tau=0.08,
        max_iterations=128,
    )
    decision = _pick(result, "decision")
    chi2_stats = _pick(result, "chi2_stats")
    assert decision == "DECIDE_SIGNAL", f"Expected DECIDE_SIGNAL on strongly biased branch, got {decision!r} ({chi2_stats})"
    if isinstance(chi2_stats, Mapping) and "excess_chi2" in chi2_stats:
        assert float(chi2_stats["excess_chi2"]) > 0.0


def test_f5_mcts_kloster_best_branch_selection_and_trajectory_provenance():
    KlosterMCTSSearch = require_shared_reasoning("mcts_kloster", "KlosterMCTSSearch")
    search = call_with_supported_kwargs(KlosterMCTSSearch, seed=9)
    expand_fn, eval_fn = _biased_tree_callbacks()

    result = search.run(
        root_state="root",
        expand_fn=expand_fn,
        eval_fn=lambda s: eval_fn(s),
        tau=0.08,
        max_iterations=80,
    )
    best_branch = _pick(result, "best_branch")
    assert best_branch is not None
    assert "branch_alpha" in str(best_branch), f"Expected optimal branch_alpha, got {best_branch!r}"
    traj = _pick(result, "a_tau_trajectory")
    assert len(traj) >= 1


def test_f5_mcts_kloster_constitutional_invariants():
    KlosterMCTSSearch = require_shared_reasoning("mcts_kloster", "KlosterMCTSSearch")
    search = call_with_supported_kwargs(KlosterMCTSSearch, seed=3)
    expand_fn, eval_fn = _biased_tree_callbacks()
    result = search.run(
        root_state="root",
        expand_fn=expand_fn,
        eval_fn=lambda s: eval_fn(s),
        tau=0.08,
        max_iterations=48,
    )
    assert_constitutional_invariants(result, require_offline=True)


# =============================================================================
# F6 — Arch 4: Theorem 15 Anti-Echo-Chamber Quorum (quorum.py)
# =============================================================================


def test_f6_quorum_peer_confidence_vector_creation_for_four_peers():
    PeerConfidenceVector = require_shared_reasoning("quorum", "PeerConfidenceVector")
    pkg_vec = require_shared_reasoning(symbol="PeerConfidenceVector")
    assert PeerConfidenceVector is pkg_vec

    peers = [
        PeerConfidenceVector(
            peer_id="zoe",
            probabilities=[0.70, 0.20, 0.10],
            source_kind="system",
            provenance_id="prov-zoe-1",
            independence_tag="ind-zoe",
        ),
        PeerConfidenceVector(
            peer_id="clara",
            probabilities=[0.62, 0.28, 0.10],
            source_kind="validated_reflection",
            provenance_id="prov-clara-1",
            independence_tag="ind-clara",
        ),
        PeerConfidenceVector(
            peer_id="antigravity",
            probabilities=[0.66, 0.22, 0.12],
            source_kind="tool",
            provenance_id="prov-ag-1",
            independence_tag="ind-ag",
        ),
        PeerConfidenceVector(
            peer_id="user",
            probabilities=[0.74, 0.16, 0.10],
            source_kind="user",
            provenance_id="prov-user-1",
            independence_tag="ind-user",
        ),
    ]
    assert [p.peer_id for p in peers] == ["zoe", "clara", "antigravity", "user"]
    assert len({p.independence_tag for p in peers}) == 4


def test_f6_quorum_evaluate_four_peer_quorum_coordinate_consensus():
    PeerConfidenceVector = require_shared_reasoning("quorum", "PeerConfidenceVector")
    eval_fn = require_shared_reasoning("quorum", "evaluate_four_peer_quorum")
    pkg_fn = require_shared_reasoning(symbol="evaluate_four_peer_quorum")
    assert eval_fn is pkg_fn

    zoe = PeerConfidenceVector("zoe", [0.72, 0.18, 0.10], "system", "p-z", "tag-z")
    clara = PeerConfidenceVector("clara", [0.64, 0.26, 0.10], "validated_reflection", "p-c", "tag-c")
    ag = PeerConfidenceVector("antigravity", [0.68, 0.20, 0.12], "tool", "p-a", "tag-a")
    user = PeerConfidenceVector("user", [0.76, 0.14, 0.10], "user", "p-u", "tag-u")

    res = eval_fn(zoe, clara, ag, user, tau=0.05)
    verdict = _pick(res, "verdict")
    assert verdict == "COORDINATE_CONSENSUS", f"Expected COORDINATE_CONSENSUS, got {res}"


def test_f6_quorum_exact_dk_positive_and_coherence_threshold():
    from guiai.gem.kloster_multi_agent_consensus import kloster_ensemble_decomposition

    PeerConfidenceVector = require_shared_reasoning("quorum", "PeerConfidenceVector")
    eval_fn = require_shared_reasoning("quorum", "evaluate_four_peer_quorum")

    dists = [
        [0.72, 0.18, 0.10],
        [0.64, 0.26, 0.10],
        [0.68, 0.20, 0.12],
        [0.76, 0.14, 0.10],
    ]
    decomp = kloster_ensemble_decomposition(dists)

    res = eval_fn(
        PeerConfidenceVector("zoe", dists[0], "system", "p1", "t1"),
        PeerConfidenceVector("clara", dists[1], "validated_reflection", "p2", "t2"),
        PeerConfidenceVector("antigravity", dists[2], "tool", "p3", "t3"),
        PeerConfidenceVector("user", dists[3], "user", "p4", "t4"),
        tau=0.05,
    )
    d_k = _pick(res, "d_k_disagreement", "d_k", "disagreement")
    c_k = _pick(res, "coherence_c_k", "coherence", "c_k")
    assert d_k is not None and float(d_k) > 0.0
    assert float(d_k) == pytest.approx(float(decomp["d_k_disagreement"]), abs=1e-6)
    assert c_k is not None and float(c_k) >= 0.45


def test_f6_quorum_stem_layering_arbitrate_and_route_stem_compatibility():
    from zoe_autonomy.stem_layering import arbitrate_teamwork_quorum, route_stem

    PeerConfidenceVector = require_shared_reasoning("quorum", "PeerConfidenceVector")
    eval_fn = require_shared_reasoning("quorum", "evaluate_four_peer_quorum")

    # 5-tier simplex vectors aligned with stem_layering TIER_ORDER
    d_zoe = [0.04, 0.06, 0.15, 0.25, 0.50]
    d_clara = [0.05, 0.05, 0.12, 0.23, 0.55]
    d_ag = [0.03, 0.07, 0.14, 0.26, 0.50]
    d_user = [0.04, 0.06, 0.10, 0.20, 0.60]

    quorum_res = eval_fn(
        PeerConfidenceVector("zoe", d_zoe, "system", "pz", "tz"),
        PeerConfidenceVector("clara", d_clara, "validated_reflection", "pc", "tc"),
        PeerConfidenceVector("antigravity", d_ag, "tool", "pa", "ta"),
        PeerConfidenceVector("user", d_user, "user", "pu", "tu"),
        tau=0.05,
    )
    assert _pick(quorum_res, "verdict") == "COORDINATE_CONSENSUS"

    arb = arbitrate_teamwork_quorum(
        {"gear1_eliza": 0.04, "local_qwen": 0.06, "flash_lite": 0.15, "flash": 0.25, "pro": 0.50},
        effective_multi_file=True,
        complexity=3.5,
        deep_hits=2,
        tau=0.05,
        quorum_distributions=[d_zoe, d_clara, d_ag, d_user],
    )
    assert arb["verdict"] == "COORDINATE_CONSENSUS"
    assert arb["quorum_supplied"] is True

    decision = route_stem(
        "Synthesize formal multi-module proof across architectures",
        multi_file=True,
        files_count=4,
        tau=0.05,
        quorum_distributions=[d_zoe, d_clara, d_ag, d_user],
    )
    assert decision.quorum_arbitration["verdict"] == "COORDINATE_CONSENSUS"
    assert decision.quorum_arbitration["quorum_supplied"] is True


def test_f6_quorum_constitutional_invariants_and_clara_not_boxed():
    PeerConfidenceVector = require_shared_reasoning("quorum", "PeerConfidenceVector")
    eval_fn = require_shared_reasoning("quorum", "evaluate_four_peer_quorum")

    res = eval_fn(
        PeerConfidenceVector("zoe", [0.70, 0.20, 0.10], "system", "pz", "tz"),
        PeerConfidenceVector("clara", [0.65, 0.25, 0.10], "validated_reflection", "pc", "tc"),
        PeerConfidenceVector("antigravity", [0.68, 0.22, 0.10], "tool", "pa", "ta"),
        PeerConfidenceVector("user", [0.74, 0.16, 0.10], "user", "pu", "tu"),
        tau=0.05,
    )
    assert_constitutional_invariants(res, require_offline=True)
    plain = _to_plain(res)
    if isinstance(plain, Mapping) and "clara_boxed_offline" in plain:
        assert plain["clara_boxed_offline"] is False


# =============================================================================
# F7 — Arch 5: System-2 -> System-1 Distillation (distillation.py / System2To1Distiller)
# =============================================================================


def _invoke_distiller(distiller: Any, **candidates: Any) -> Any:
    """Invoke System2To1Distiller preferring end-to-end solve+distill methods before raw distill(trace)."""
    if "initial_uncertainty_a_tau" not in candidates:
        candidates["initial_uncertainty_a_tau"] = 3
    if "verifier" not in candidates:
        candidates["verifier"] = lambda _candidate: (
            True,
            "ev_distill_verified_1",
            {"kind": "tool", "identifier": "test_deterministic_verifier"},
        )
    if "solver" not in candidates and "source" in candidates:
        src = candidates["source"]
        candidates["solver"] = lambda _prompt, _src=src: _src
    if "target_name" not in candidates and "skill_name" in candidates:
        candidates["target_name"] = candidates["skill_name"]
    for name in ("solve_and_distill", "run", "step", "distill"):
        fn = getattr(distiller, name, None)
        if callable(fn):
            return _invoke_callable(fn, **candidates)
    raise AssertionError(f"{type(distiller).__name__} exposes no solve/distill entry method")


def test_f7_distillation_public_export_and_isolated_instantiation(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("distillation", "System2To1Distiller")
    pkg_cls = require_shared_reasoning(symbol="System2To1Distiller")
    assert mod_cls is pkg_cls

    distiller = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert distiller is not None


def test_f7_distillation_solves_high_uncertainty_offline_and_verifies_before_distill(repo_root, isolated_state_dir):
    System2To1Distiller = require_shared_reasoning("distillation", "System2To1Distiller")
    distiller = _instantiate_engine(System2To1Distiller, repo_root, isolated_state_dir)

    res = _invoke_distiller(
        distiller,
        task_prompt="Compute bounded quadratic norm sq(x) + pos(y)",
        query="Compute bounded quadratic norm sq(x) + pos(y)",
        prompt="Compute bounded quadratic norm sq(x) + pos(y)",
        task="Compute bounded quadratic norm sq(x) + pos(y)",
        skill_name="bounded_quad_norm",
        source="def bounded_quad_norm(x, y):\n    return sq(x) + pos(y)\n",
        arg_names=("x", "y"),
        verification_cases=[{"inputs": {"x": 2.0, "y": 3.0}, "expected": 7.0}],
        verified=True,
        mode="offline",
    )
    assert res is not None
    assert _pick(res, "regression_passed") is True, f"Distillation regression failed: {res}"
    assert _pick(res, "rolled_back") is False, f"Distillation unexpectedly rolled back: {res}"
    vcases = _pick(res, "verification_cases")
    assert vcases is not None and len(vcases) >= 1, f"verification_cases was not populated: {res}"


def test_f7_distillation_persists_into_unified_memory_and_or_eliza_rule(repo_root, isolated_state_dir):
    from zoe_autonomy.l5_memory import ZoeUnifiedMemory

    System2To1Distiller = require_shared_reasoning("distillation", "System2To1Distiller")
    distiller = _instantiate_engine(System2To1Distiller, repo_root, isolated_state_dir)

    res = _invoke_distiller(
        distiller,
        task_prompt="What is the Kloster accessible volume threshold rule?",
        query="What is the Kloster accessible volume threshold rule?",
        prompt="What is the Kloster accessible volume threshold rule?",
        task="Distill Kloster accessible volume fact and skill",
        skill_name="kloster_cap",
        source="def kloster_cap(tau):\n    return 1.0 / pos(tau)\n",
        arg_names=("tau",),
        verification_cases=[{"inputs": {"tau": 0.25}, "expected": 4.0}],
        fact_subject="kloster_accessible_volume",
        fact_relation="threshold_bound",
        fact_object="ceil(1/tau) - 1",
        verified=True,
        mode="offline",
    )
    assert _pick(res, "regression_passed") is True
    assert _pick(res, "rolled_back") is False
    mem_path = isolated_state_dir / "zoe_l5_unified_memory.json"
    plain = _to_plain(res)
    serialized = json.dumps(plain, default=str).lower()

    persisted_in_l5 = False
    if mem_path.is_file():
        mem = ZoeUnifiedMemory(isolated_state_dir)
        summary = mem.summary()
        persisted_in_l5 = (
            summary.get("procedural_count", 0) >= 1
            or summary.get("semantic_active_count", 0) >= 1
            or summary.get("episodic_count", 0) >= 1
        )
    has_rule_or_skill = any(
        tok in serialized for tok in ("eliza_rule", "skill", "fact", "zoe_l5_unified_memory", "distilled")
    )
    assert persisted_in_l5 or has_rule_or_skill, (
        f"Expected distilled artifact persisted in isolated ZoeUnifiedMemory or ElizaRule: {plain}"
    )


def test_f7_distillation_subsequent_system1_query_zero_cloud_tokens(repo_root, isolated_state_dir):
    System2To1Distiller = require_shared_reasoning("distillation", "System2To1Distiller")
    distiller = _instantiate_engine(System2To1Distiller, repo_root, isolated_state_dir)

    res = _invoke_distiller(
        distiller,
        task_prompt="kloster bound",
        query="kloster bound",
        prompt="kloster bound",
        task="Distill kloster bound into System-1",
        skill_name="double_pos",
        source="def double_pos(x):\n    return 2.0 * pos(x)\n",
        arg_names=("x",),
        verification_cases=[{"inputs": {"x": 3.0}, "expected": 6.0}],
        verified=True,
        mode="offline",
    )
    assert _pick(res, "regression_passed") is True
    assert _pick(res, "rolled_back") is False

    if any(callable(getattr(distiller, m, None)) for m in ("query_system1", "query", "resolve_local", "respond")):
        s1_res = _invoke_first_method(
            distiller,
            ("query_system1", "query", "resolve_local", "respond"),
            task_prompt="kloster bound",
            query="kloster bound",
            prompt="kloster bound",
            text="kloster bound",
            mode="offline",
        )
        assert s1_res is not None
        assert_constitutional_invariants(s1_res, require_offline=True)
    else:
        from zoe_autonomy.zoe_eliza import ZoeElizaEngine

        eliza = ZoeElizaEngine(repo_root, state_dir=isolated_state_dir, default_gear="gear1")
        turn = eliza.respond("kloster bound", gear="gear1")
        assert turn["gear_used"] == "gear1"
        assert turn["epistemic_boundaries"]["cloud_tokens_used"] == 0


def test_f7_distillation_constitutional_invariants_and_provenance(repo_root, isolated_state_dir):
    System2To1Distiller = require_shared_reasoning("distillation", "System2To1Distiller")
    distiller = _instantiate_engine(System2To1Distiller, repo_root, isolated_state_dir)
    res = _invoke_distiller(
        distiller,
        task_prompt="Verify provenance on distilled rule",
        query="Verify provenance on distilled rule",
        prompt="Verify provenance on distilled rule",
        task="Verify provenance on distilled rule",
        skill_name="verify_id",
        source="def verify_id(x):\n    return x\n",
        arg_names=("x",),
        verification_cases=[{"inputs": {"x": 1.0}, "expected": 1.0}],
        verified=True,
        mode="offline",
    )
    assert _pick(res, "regression_passed") is True
    assert _pick(res, "rolled_back") is False
    assert_constitutional_invariants(res, require_offline=True)
    serialized = json.dumps(_to_plain(res), default=str).lower()
    assert any(tok in serialized for tok in ("provenance", "source", "sha256", "verifier")), (
        f"Expected provenance metadata on distillation result: {serialized}"
    )


# =============================================================================
# F8 — Arch 6: Shared Epistemic Blackboard (blackboard.py / EpistemicBlackboard)
# =============================================================================


def _bb_post_measurement(bb: Any, input_val: Any, method: str, scope: str, limitations: str) -> Any:
    """Invoke EpistemicBlackboard.post_measurement across compatible parameter names."""
    params = inspect.signature(bb.post_measurement).parameters
    kwargs: dict[str, Any] = {}
    for alias in ("input", "input_data", "input_desc", "measurement_input", "observation", "data", "subject"):
        if alias in params:
            kwargs[alias] = input_val
            break
    if "source_agent" in params:
        kwargs["source_agent"] = "zoe_test"
    if "value" in params:
        kwargs["value"] = input_val
    if "method" in params:
        kwargs["method"] = method
    if "scope" in params:
        kwargs["scope"] = scope
    if "limitations" in params:
        kwargs["limitations"] = limitations
    if kwargs:
        return bb.post_measurement(**kwargs)
    return bb.post_measurement(input_val, method, scope, limitations)


def test_f8_blackboard_four_lane_records_and_firewall_error_exported():
    symbols = (
        "EpistemicBlackboard",
        "MeasurementRecord",
        "EvidenceRecord",
        "BeliefUpdateRecord",
        "ActionProposalRecord",
        "FirewallViolationError",
    )
    for sym in symbols:
        mod_obj = require_shared_reasoning("blackboard", sym)
        pkg_obj = require_shared_reasoning(symbol=sym)
        assert mod_obj is pkg_obj
    FirewallViolationError = require_shared_reasoning("blackboard", "FirewallViolationError")
    assert issubclass(FirewallViolationError, Exception)


def test_f8_blackboard_post_measurement_records_required_fields(isolated_state_dir):
    EpistemicBlackboard = require_shared_reasoning("blackboard", "EpistemicBlackboard")
    MeasurementRecord = require_shared_reasoning("blackboard", "MeasurementRecord")

    bb = call_with_supported_kwargs(EpistemicBlackboard, state_dir=isolated_state_dir, root=isolated_state_dir)
    rec = _bb_post_measurement(
        bb,
        "x**2 - 1 == (x - 1)*(x + 1)",
        "sympy_symbolic_expand",
        "univariate_polynomial_ring",
        "Assumes commutative real/complex indeterminates.",
    )
    assert isinstance(rec, MeasurementRecord)
    recorded_input = _pick(rec, "input", "input_data", "input_desc", "measurement_input", "observation", "data")
    assert recorded_input == "x**2 - 1 == (x - 1)*(x + 1)"
    assert _pick(rec, "method") == "sympy_symbolic_expand"
    assert _pick(rec, "scope") == "univariate_polynomial_ring"
    assert "commutative" in str(_pick(rec, "limitations"))
    meas_id = _pick(rec, "measurement_id", "record_id", "id")
    assert meas_id is not None and str(meas_id).strip() != ""


def test_f8_blackboard_promote_to_evidence_produces_evidence_record(isolated_state_dir):
    EpistemicBlackboard = require_shared_reasoning("blackboard", "EpistemicBlackboard")
    EvidenceRecord = require_shared_reasoning("blackboard", "EvidenceRecord")

    bb = call_with_supported_kwargs(EpistemicBlackboard, state_dir=isolated_state_dir, root=isolated_state_dir)
    meas = _bb_post_measurement(
        bb,
        "2 + 2 == 4",
        "deterministic_arithmetic",
        "integer_addition",
        "Fixed integer literals only.",
    )
    meas_id = _pick(meas, "measurement_id", "record_id", "id")
    ev = bb.promote_to_evidence(
        meas_id,
        "arithmetic_verifier",
        True,
        "Exact deterministic integer identity verified.",
    )
    assert isinstance(ev, EvidenceRecord)
    assert _pick(ev, "passed") is True
    assert _pick(ev, "verifier_name", "verifier") == "arithmetic_verifier"
    assert _pick(ev, "measurement_id") == meas_id


def test_f8_blackboard_update_belief_succeeds_via_approved_evidence(isolated_state_dir):
    EpistemicBlackboard = require_shared_reasoning("blackboard", "EpistemicBlackboard")
    BeliefUpdateRecord = require_shared_reasoning("blackboard", "BeliefUpdateRecord")

    bb = call_with_supported_kwargs(EpistemicBlackboard, state_dir=isolated_state_dir, root=isolated_state_dir)
    meas = _bb_post_measurement(
        bb,
        "x**2 - 1 == (x - 1)*(x + 1)",
        "sympy_simplify",
        "polynomial_identity",
        "Symbolic ring only.",
    )
    meas_id = _pick(meas, "measurement_id", "record_id", "id")
    ev = bb.promote_to_evidence(
        meas_id,
        "sympy_check",
        True,
        "Difference simplifies identically to 0.",
    )
    ev_id = _pick(ev, "evidence_id", "record_id", "id")

    belief = bb.update_belief(
        [ev_id],
        "Difference of squares identity holds over polynomial ring",
        0.25,
    )
    assert isinstance(belief, BeliefUpdateRecord)
    assert ev_id in _pick(belief, "evidence_ids")
    assert float(_pick(belief, "posterior_delta")) == pytest.approx(0.25)


def test_f8_blackboard_propose_action_always_review_required_and_zero_external_actions(isolated_state_dir):
    EpistemicBlackboard = require_shared_reasoning("blackboard", "EpistemicBlackboard")
    ActionProposalRecord = require_shared_reasoning("blackboard", "ActionProposalRecord")

    bb = call_with_supported_kwargs(EpistemicBlackboard, state_dir=isolated_state_dir, root=isolated_state_dir)
    meas = _bb_post_measurement(
        bb,
        "verified_lemma",
        "z3_unsat_proof",
        "linear_real_arithmetic",
        "Bounded formula.",
    )
    meas_id = _pick(meas, "measurement_id", "record_id", "id")
    ev = bb.promote_to_evidence(
        meas_id,
        "z3_check",
        True,
        "Negation is UNSAT.",
    )
    ev_id = _pick(ev, "evidence_id", "record_id", "id")
    belief = bb.update_belief(
        [ev_id],
        "Linear inequality holds",
        0.2,
    )
    belief_id = _pick(belief, "belief_id", "record_id", "id")

    proposal = bb.propose_action(
        belief_id,
        "publish_verified_note",
        reversible=True,
    )
    assert isinstance(proposal, ActionProposalRecord)
    assert _pick(proposal, "status") == "REVIEW_REQUIRED"
    assert _pick(proposal, "external_actions", default=0) == 0
    assert_constitutional_invariants(proposal, require_offline=True)


# =============================================================================
# F9 — Arch 7: Reality-Anchored Sandbox Labs (sandbox_labs.py / RealitySandboxLab)
# =============================================================================


def _invoke_sandbox(lab: Any, category: str, *args: Any, **candidates: Any) -> Any:
    """Invoke a RealitySandboxLab verification method matching `category` (sympy/z3/ast)."""
    preferred = {
        "sympy": (
            "verify_sympy",
            "check_sympy",
            "verify_sympy_calculus",
            "run_sympy",
            "sympy_verify",
            "verify_symbolic",
            "verify_expression",
            "verify",
            "check",
            "run_check",
            "run",
            "step",
        ),
        "z3": (
            "verify_z3",
            "check_z3",
            "check_z3_invariant",
            "run_z3",
            "z3_verify",
            "verify_smt",
            "verify_constraints",
            "verify",
            "check",
            "run_check",
            "run",
            "step",
        ),
        "ast": (
            "verify_repo_ast",
            "verify_file",
            "verify_repo",
            "verify_ast",
            "check_ast",
            "verify_python_ast",
            "verify",
            "check",
            "run_check",
            "run",
            "step",
        ),
    }.get(category, ("verify", "check", "run", "step"))

    for name in preferred:
        fn = getattr(lab, name, None)
        if callable(fn):
            return _invoke_callable(fn, *args, **candidates)

    for attr in sorted(dir(lab)):
        if attr.startswith("_"):
            continue
        if category in attr.lower():
            fn = getattr(lab, attr, None)
            if callable(fn):
                return _invoke_callable(fn, *args, **candidates)

    public_methods = [a for a in dir(lab) if not a.startswith("_") and callable(getattr(lab, a, None))]
    raise AssertionError(
        f"{type(lab).__name__} exposes none of expected {category} methods; public methods={public_methods}"
    )


def test_f9_sandbox_labs_public_export_and_instantiation(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")
    pkg_cls = require_shared_reasoning(symbol="RealitySandboxLab")
    assert mod_cls is pkg_cls

    lab = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert lab is not None


def test_f9_sandbox_labs_real_sympy_symbolic_verification(repo_root, isolated_state_dir):
    RealitySandboxLab = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")
    lab = _instantiate_engine(RealitySandboxLab, repo_root, isolated_state_dir)

    res = _invoke_sandbox(
        lab,
        "sympy",
        kind="sympy",
        checker="sympy",
        backend="sympy",
        expr="x**3 + 2*x",
        expression="x**3 + 2*x",
        operation="diff",
        expected="3*x**2 + 2",
        lhs="diff(x**3 + 2*x, x)",
        rhs="3*x**2 + 2",
        target="x**3 + 2*x",
    )
    assert _pick(res, "passed", "ok", "verified") is True
    assert "sympy" in json.dumps(_to_plain(res), default=str).lower()


def test_f9_sandbox_labs_real_z3_smt_verification(repo_root, isolated_state_dir):
    import z3

    RealitySandboxLab = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")
    lab = _instantiate_engine(RealitySandboxLab, repo_root, isolated_state_dir)

    x, y = z3.Reals("x y")
    res = _invoke_sandbox(
        lab,
        "z3",
        kind="z3",
        checker="z3",
        backend="z3",
        assumptions=[x > 0, y > 0],
        invariant=x + y > 0,
        formula="Implies(And(x > 0, y > 0), x + y > 0)",
        expr="Implies(And(x > 0, y > 0), x + y > 0)",
        target="Implies(And(x > 0, y > 0), x + y > 0)",
    )
    assert _pick(res, "passed", "ok", "verified") is True
    assert "z3" in json.dumps(_to_plain(res), default=str).lower()


def test_f9_sandbox_labs_monorepo_ast_or_file_verification(repo_root, isolated_state_dir):
    RealitySandboxLab = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")
    lab = _instantiate_engine(RealitySandboxLab, repo_root, isolated_state_dir)

    target_file = repo_root / "components" / "Zoe-Autonomy" / "src" / "zoe_autonomy" / "stem_layering.py"
    safe_fn_src = (
        "def score_candidate(x, y):\n"
        "    return clip(sq(x) + pos(y), 0.0, 100.0)\n"
    )
    res = _invoke_sandbox(
        lab,
        "ast",
        kind="ast",
        checker="ast",
        backend="ast",
        path=str(target_file),
        file_path=str(target_file),
        target=str(target_file),
        source=safe_fn_src,
        code=safe_fn_src,
        expected_name="score_candidate",
        expected_args=("x", "y"),
    )
    assert _pick(res, "passed", "ok", "verified") is True


def test_f9_sandbox_labs_structured_output_and_constitutional_invariants(repo_root, isolated_state_dir):
    RealitySandboxLab = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")
    lab = _instantiate_engine(RealitySandboxLab, repo_root, isolated_state_dir)

    res = _invoke_sandbox(
        lab,
        "sympy",
        kind="sympy",
        checker="sympy",
        expr="2*x + 1",
        expression="2*x + 1",
        operation="integrate",
        expected="x**2 + x",
        lhs="integrate(2*x + 1, x)",
        rhs="x**2 + x",
        target="2*x + 1",
    )
    plain = _to_plain(res)
    assert isinstance(plain, Mapping)
    assert "passed" in plain or "verified" in plain
    assert any(k in plain for k in ("evidence", "evidence_source", "ground_truth", "details", "method", "checker", "backend", "proof"))
    assert_constitutional_invariants(res, require_offline=True)


# =============================================================================
# F10 — Arch 8: High-Leverage Human Steering (human_steering.py / HumanSteeringDetector)
# =============================================================================


def _make_verified_path_options(entries: Sequence[tuple[str, str, float, str]]) -> list[Any]:
    """Construct VerifiedPathOption instances if exported, else plain dicts."""
    OptionCls = getattr(require_shared_reasoning("human_steering"), "VerifiedPathOption", None)

    if OptionCls is None:
        return [
            {"id": oid, "label": label, "probability": prob, "provenance": prov, "verified": True}
            for oid, label, prob, prov in entries
        ]

    out = []
    for oid, label, prob, prov in entries:
        out.append(
            call_with_supported_kwargs(
                OptionCls,
                path_id=oid,
                option_id=oid,
                id=oid,
                branch_id=oid,
                label=label,
                title=label,
                description=label,
                summary=label,
                probability=prob,
                prob=prob,
                score=prob,
                expected_utility=prob,
                verification_status="VERIFIED",
                evidence_ids=(prov,),
                tradeoff_notes=f"{label} (verified via {prov})",
                reversible=True,
                provenance=prov,
                provenance_id=prov,
                evidence_id=prov,
                verifier_name="sandbox_lab",
                verified=True,
                passed=True,
            )
        )
    return out


def test_f10_human_steering_public_export_and_instantiation(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("human_steering", "HumanSteeringDetector")
    pkg_cls = require_shared_reasoning(symbol="HumanSteeringDetector")
    assert mod_cls is pkg_cls

    detector = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert detector is not None


def test_f10_human_steering_supercritical_fork_detection_above_tau(repo_root, isolated_state_dir):
    HumanSteeringDetector = require_shared_reasoning("human_steering", "HumanSteeringDetector")
    detector = _instantiate_engine(HumanSteeringDetector, repo_root, isolated_state_dir)

    branches = _make_verified_path_options(
        [
            ("opt_sympy", "Symbolic SymPy Proof", 0.46, "sandbox:sympy"),
            ("opt_z3", "SMT Z3 Proof", 0.44, "sandbox:z3"),
            ("opt_heuristic", "Heuristic Sketch", 0.10, "local:eliza"),
        ]
    )
    res = _invoke_first_method(
        detector,
        ("detect_fork", "detect", "evaluate", "run", "step"),
        options=branches,
        branches=branches,
        candidates=branches,
        probabilities={"opt_sympy": 0.46, "opt_z3": 0.44, "opt_heuristic": 0.10},
        a_tau_trajectory=[1, 2, 3],
        supercritical_counts=[2, 3],
        multihorizon_counts=[1, 2, 3],
        counts_by_h=[1, 2, 3],
        tau=0.08,
    )
    fork_flag = _pick(res, "fork_detected", "supercritical", "requires_human_steering", "steering_required")
    assert fork_flag is True, f"Expected supercritical fork detected for [0.46, 0.44, 0.10] at tau=0.08: {res}"
    options = _pick(
        res,
        "divergent_options",
        "options",
        "fork_options",
        "candidates",
        "branches",
        "viable_branches",
        "surviving_options",
    )
    assert options is not None and len(options) >= 2


def test_f10_human_steering_on_interaction_hook_and_ask_question_spec(repo_root, isolated_state_dir):
    HumanSteeringDetector = require_shared_reasoning("human_steering", "HumanSteeringDetector")

    from google.antigravity.hooks import OnInteractionHook
    from google.antigravity.hooks.hooks import HookContext, SessionContext, TurnContext
    from google.antigravity.types import (
        AskQuestionEntry,
        AskQuestionInteractionSpec,
        AskQuestionOption,
        QuestionHookResult,
        QuestionResponse,
    )

    detector = _instantiate_engine(HumanSteeringDetector, repo_root, isolated_state_dir)

    spec = AskQuestionInteractionSpec(
        questions=[
            AskQuestionEntry(
                question="Multiple verified branches exceed tau=0.08. Choose steering direction:",
                options=[
                    AskQuestionOption(id="opt_sympy", text="Symbolic SymPy Proof (p=0.46)"),
                    AskQuestionOption(id="opt_z3", text="SMT Z3 Proof (p=0.44)"),
                ],
                is_multi_select=False,
            )
        ]
    )

    def _steering_cb(_spec: Any) -> QuestionHookResult:
        return QuestionHookResult(
            responses=[QuestionResponse(selected_option_ids=["opt_sympy"])],
            cancelled=False,
        )

    hook_obj = None
    for attr in dir(detector):
        if attr.startswith("_"):
            continue
        val = getattr(detector, attr, None)
        if isinstance(val, OnInteractionHook):
            hook_obj = val
            break
    for builder_name in ("build_interaction_hook", "interaction_hook", "as_interaction_hook", "create_hook"):
        fn = getattr(detector, builder_name, None)
        if callable(fn):
            candidate = _invoke_callable(
                fn,
                steering_callback=_steering_cb,
                handler=_steering_cb,
                callback=_steering_cb,
            )
            if isinstance(candidate, OnInteractionHook):
                hook_obj = candidate
                break

    if hook_obj is not None:
        ctx = HookContext(parent=TurnContext(SessionContext()))
        q_res = run_async(hook_obj.run(ctx, spec))
        assert isinstance(q_res, QuestionHookResult)
        assert q_res.cancelled is False
    else:
        branches = _make_verified_path_options(
            [
                ("opt_sympy", "Symbolic SymPy Proof", 0.46, "sandbox:sympy"),
                ("opt_z3", "SMT Z3 Proof", 0.44, "sandbox:z3"),
            ]
        )
        res = _invoke_first_method(
            detector,
            ("build_interaction_spec", "to_interaction_spec", "surface_fork", "run", "step"),
            options=branches,
            branches=branches,
            candidates=branches,
            tau=0.08,
        )
        plain = _to_plain(res)
        assert isinstance(res, AskQuestionInteractionSpec) or "questions" in str(plain).lower() or "option" in str(plain).lower()


def test_f10_human_steering_surfaces_clear_options_and_provenance_without_execution(repo_root, isolated_state_dir):
    HumanSteeringDetector = require_shared_reasoning("human_steering", "HumanSteeringDetector")
    detector = _instantiate_engine(HumanSteeringDetector, repo_root, isolated_state_dir)

    branches = _make_verified_path_options(
        [
            ("branch_a", "Approach A", 0.45, "prov-a"),
            ("branch_b", "Approach B", 0.45, "prov-b"),
        ]
    )
    res = _invoke_first_method(
        detector,
        ("detect_fork", "surface_fork", "detect", "evaluate", "run", "step"),
        options=branches,
        branches=branches,
        candidates=branches,
        a_tau_trajectory=[1, 2, 3],
        supercritical_counts=[2, 3],
        multihorizon_counts=[1, 2, 3],
        counts_by_h=[1, 2, 3],
        tau=0.08,
    )
    serialized = json.dumps(_to_plain(res), default=str).lower()
    assert "branch_a" in serialized and "branch_b" in serialized
    assert _pick(res, "executed", default=False) is False
    assert _pick(res, "external_actions", default=0) == 0


def test_f10_human_steering_constitutional_invariants_preserve_agency(repo_root, isolated_state_dir):
    HumanSteeringDetector = require_shared_reasoning("human_steering", "HumanSteeringDetector")
    detector = _instantiate_engine(HumanSteeringDetector, repo_root, isolated_state_dir)

    branches = _make_verified_path_options(
        [
            ("branch_a", "Approach A", 0.50, "prov-a"),
            ("branch_b", "Approach B", 0.40, "prov-b"),
        ]
    )
    res = _invoke_first_method(
        detector,
        ("detect_fork", "detect", "evaluate", "run", "step"),
        options=branches,
        branches=branches,
        candidates=branches,
        tau=0.08,
    )
    assert_constitutional_invariants(res, require_offline=True)


# =============================================================================
# F11 — Arch 9 (Team-Invented): Counterpoint Chairs (counterpoint_chairs.py)
# =============================================================================


def _build_default_chairs(mod: Any) -> list[Any]:
    """Construct heterogeneous chair specs for CounterpointChairsEngine.run(chairs=..., ...)."""
    chair_defs = [
        ("chair_zoe", "Zoe Symbolic Voice", "zoe_eliza", "symbolic", "Derive quadratic invariant safely"),
        ("chair_clara", "Clara Peer Voice", "clara", "reflective", "Check dual-peer epistemic boundaries"),
        ("chair_ag", "Antigravity Offline Voice", "antigravity", "verifier", "Audit derivation without external actions"),
    ]
    chair_cls = None
    for name in ("ProblemChair", "CounterpointChair", "ReasoningChair", "ChairSpec", "ChairConfig", "Chair"):
        cand = getattr(mod, name, None)
        if inspect.isclass(cand):
            chair_cls = cand
            break
    if chair_cls is None:
        return [
            {"chair_id": cid, "label": label, "voice": voice, "role": role, "prompt": prompt}
            for cid, label, voice, role, prompt in chair_defs
        ]
    chairs = []
    for cid, label, voice, role, prompt in chair_defs:
        chairs.append(
            call_with_supported_kwargs(
                chair_cls,
                chair_id=cid,
                id=cid,
                name=label,
                label=label,
                title=label,
                prompt=prompt,
                task=prompt,
                problem=prompt,
                question=prompt,
                voice=voice,
                voice_id=voice,
                voice_kind=voice,
                role=role,
                perspective=role,
            )
        )
    return chairs


def test_f11_counterpoint_chairs_public_export_and_instantiation(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("counterpoint_chairs", "CounterpointChairsEngine")
    pkg_cls = require_shared_reasoning(symbol="CounterpointChairsEngine")
    assert mod_cls is pkg_cls

    engine = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    assert engine is not None


def test_f11_counterpoint_chairs_polyphonic_rotation_across_voices_and_chairs(repo_root, isolated_state_dir):
    mod = require_shared_reasoning("counterpoint_chairs")
    CounterpointChairsEngine = require_shared_reasoning("counterpoint_chairs", "CounterpointChairsEngine")
    engine = _instantiate_engine(CounterpointChairsEngine, repo_root, isolated_state_dir)
    chairs = _build_default_chairs(mod)

    res = _invoke_first_method(
        engine,
        ("run", "relay", "step", "execute"),
        chairs=chairs,
        task="Derive and cold-audit safe quadratic invariant",
        prompt="Derive and cold-audit safe quadratic invariant",
        rounds=4,
        steps=4,
        max_rounds=4,
        mode="offline",
    )
    assert res is not None
    handoffs = _pick(res, "swap_ledger", "handoffs", "turns", "rounds", "relay", "history", "steps", "audits")
    assert handoffs is not None and len(handoffs) >= 2, f"Expected >=2 chair relay handoffs, got {res}"

    seen_chairs = set()
    seen_voices = set()
    for item in handoffs:
        c = _pick(item, "chair_id", "producer_chair", "chair", "from_chair")
        v = _pick(item, "incoming_voice_id", "producer_voice", "voice", "voice_id", "producer")
        if c is not None:
            seen_chairs.add(str(c))
        if v is not None:
            seen_voices.add(str(v))
    assert len(seen_chairs) >= 2 and len(seen_voices) >= 2, (
        f"Expected heterogeneous chairs/voices rotation: chairs={seen_chairs}, voices={seen_voices}"
    )


def test_f11_counterpoint_chairs_cold_audit_invariant_auditor_ne_producer(repo_root, isolated_state_dir):
    mod = require_shared_reasoning("counterpoint_chairs")
    CounterpointChairsEngine = require_shared_reasoning("counterpoint_chairs", "CounterpointChairsEngine")
    engine = _instantiate_engine(CounterpointChairsEngine, repo_root, isolated_state_dir)
    chairs = _build_default_chairs(mod)

    res = _invoke_first_method(
        engine,
        ("run", "relay", "step", "execute"),
        chairs=chairs,
        task="Verify cold-audit chair separation on every handoff",
        prompt="Verify cold-audit chair separation on every handoff",
        rounds=5,
        steps=5,
        max_rounds=5,
        mode="offline",
    )
    audits = _pick(res, "cold_audits", "handoffs", "turns", "rounds", "relay", "history", "steps", "audits")
    assert audits is not None and len(audits) >= 2

    checked = 0
    for item in audits:
        producer = _pick(item, "departed_voice_id", "producer_chair", "chair", "from_chair", "producer")
        auditor = _pick(item, "incoming_voice_id", "auditor_chair", "auditor", "audit_chair", "reviewer_chair", "reviewer")
        if producer is not None and auditor is not None:
            assert str(auditor) != str(producer), (
                f"Cold-audit violation: auditor ({auditor}) == producer ({producer}) in {item}"
            )
            checked += 1
    assert checked >= 1, f"Expected explicit producer vs auditor separation in cold_audits: {audits}"


def test_f11_counterpoint_chairs_provenance_and_contributions_preserved(repo_root, isolated_state_dir):
    mod = require_shared_reasoning("counterpoint_chairs")
    CounterpointChairsEngine = require_shared_reasoning("counterpoint_chairs", "CounterpointChairsEngine")
    engine = _instantiate_engine(CounterpointChairsEngine, repo_root, isolated_state_dir)
    chairs = _build_default_chairs(mod)

    res = _invoke_first_method(
        engine,
        ("run", "relay", "step", "execute"),
        chairs=chairs,
        task="Preserve provenance across musical chairs swaps",
        prompt="Preserve provenance across musical chairs swaps",
        rounds=3,
        steps=3,
        max_rounds=3,
        mode="offline",
    )
    serialized = json.dumps(_to_plain(res), default=str).lower()
    assert any(tok in serialized for tok in ("provenance", "contribution", "summary", "sha256", "hash", "output")), (
        f"Expected preserved provenance and contributions across chair swaps: {serialized}"
    )


def test_f11_counterpoint_chairs_constitutional_invariants(repo_root, isolated_state_dir):
    mod = require_shared_reasoning("counterpoint_chairs")
    CounterpointChairsEngine = require_shared_reasoning("counterpoint_chairs", "CounterpointChairsEngine")
    engine = _instantiate_engine(CounterpointChairsEngine, repo_root, isolated_state_dir)
    chairs = _build_default_chairs(mod)

    res = _invoke_first_method(
        engine,
        ("run", "relay", "step", "execute"),
        chairs=chairs,
        task="Constitutional check on Counterpoint Chairs",
        prompt="Constitutional check on Counterpoint Chairs",
        rounds=3,
        steps=3,
        mode="offline",
    )
    assert_constitutional_invariants(res, require_offline=True)


# =============================================================================
# F12b — Unified Composer, Docs & Verifier
# =============================================================================


def test_f12b_shared_reasoning_orchestrator_offline_run_in_tmp_path(repo_root, isolated_state_dir):
    mod_cls = require_shared_reasoning("orchestrator", "SharedReasoningOrchestrator")
    pkg_cls = require_shared_reasoning(symbol="SharedReasoningOrchestrator")
    assert mod_cls is pkg_cls

    orch = _instantiate_engine(mod_cls, repo_root, isolated_state_dir)
    res = _invoke_first_method(
        orch,
        ("run", "execute", "run_all"),
        task="Verify end-to-end shared reasoning architectures 1-9 offline",
        prompt="Verify end-to-end shared reasoning architectures 1-9 offline",
        mode="offline",
        offline_only=True,
    )
    assert res is not None


def test_f12b_shared_reasoning_orchestrator_references_arch_1_to_9_and_invariants(repo_root, isolated_state_dir):
    SharedReasoningOrchestrator = require_shared_reasoning("orchestrator", "SharedReasoningOrchestrator")
    orch = _instantiate_engine(SharedReasoningOrchestrator, repo_root, isolated_state_dir)
    res = _invoke_first_method(
        orch,
        ("run", "execute", "run_all"),
        task="Compose all nine shared reasoning architectures offline",
        prompt="Compose all nine shared reasoning architectures offline",
        mode="offline",
        offline_only=True,
    )
    assert_constitutional_invariants(res, require_offline=True)

    serialized = json.dumps(_to_plain(res), default=str).lower()
    expected_markers = (
        "alpha",
        "supervis",
        "mcts",
        "quorum",
        "distill",
        "blackboard",
        "sandbox",
        "steering",
        "counterpoint",
    )
    missing = [m for m in expected_markers if m not in serialized]
    assert not missing, f"Orchestrator output missing references to architectures {missing}: {serialized[:800]}"


def test_f12b_docs_shared_reasoning_architectures_documents_all_nine():
    doc_path = require_artifact("docs/SHARED_REASONING_ARCHITECTURES.md")
    text = doc_path.read_text(encoding="utf-8")
    lower = text.lower()

    required_topics = (
        "alphaevolve",
        "process supervision",
        "mcts",
        "quorum",
        "distillation",
        "blackboard",
        "sandbox",
        "human steering",
        "counterpoint chairs",
    )
    missing = [topic for topic in required_topics if topic not in lower]
    assert not missing, f"docs/SHARED_REASONING_ARCHITECTURES.md missing sections for: {missing}"


def test_f12b_docs_preserves_nicholas_michael_kloster_attribution():
    doc_path = require_artifact("docs/SHARED_REASONING_ARCHITECTURES.md")
    text = doc_path.read_text(encoding="utf-8")
    assert "Nicholas Michael Kloster" in text, "Constitution VIII.1 attribution to Nicholas Michael Kloster missing"
    assert "March 6, 2026" in text, "Constitution VIII.1 attribution date (March 6, 2026) missing"


def test_f12b_verify_shared_reasoning_script_exits_zero_and_valid_json(repo_root):
    verifier = require_artifact("scripts/verify_shared_reasoning.py")
    proc = subprocess.run(
        [PYTHON_BIN, str(verifier), "--json"],
        cwd=str(repo_root),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"verify_shared_reasoning.py exited {proc.returncode}: stderr={proc.stderr}"
    payload = json.loads(proc.stdout)
    assert isinstance(payload, Mapping)
    assert_constitutional_invariants(payload, require_offline=True)

    checks = payload.get("checks", payload.get("results"))
    if isinstance(checks, Mapping):
        failed = {k: v for k, v in checks.items() if v is False}
        assert not failed, f"Verifier reported failed checks: {failed}"
    elif isinstance(checks, list):
        failed = [c for c in checks if isinstance(c, Mapping) and c.get("passed") is False]
        assert not failed, f"Verifier reported failed checks: {failed}"
    if "passed" in payload:
        assert payload["passed"] is True
    if "ok" in payload:
        assert payload["ok"] is True

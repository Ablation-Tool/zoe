"""Unit tests for Architecture #3: MCTS / Tree-of-Thought with Kloster Stopping."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
GUIAI_LAB = REPO_ROOT / "guiai-lab"
for p in (ZOE_AUTONOMY_SRC, GUIAI_LAB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from zoe_autonomy.l5_phase6_multihorizon_metacognition import (  # noqa: E402
    tight_strict_upper_bound,
)
from zoe_autonomy.shared_reasoning import (  # noqa: E402
    CallableVoiceAdapter,
    KlosterMCTSSearch,
    MCTSSearchResult,
    ZoeAntigravityBridge,
    available_submodules,
)
from zoe_autonomy.shared_reasoning.mcts_kloster import (  # noqa: E402
    MCTS_KLOSTER_CONTRACT,
    ForkCandidate,
    MCTSBranchTrajectory,
    ThoughtCandidate,
    ThoughtNode,
)


def _assert_constitutional(doc: dict[str, Any]) -> None:
    assert doc["external_actions"] == 0
    assert doc["sentience_claimed"] is False
    assert doc["l5_agi_qualified"] is False
    assert doc["zoe_clone_claimed"] is False
    assert doc["attribution"] == "Nicholas Michael Kloster, March 6, 2026"
    assert doc["measurement_only"] is True
    assert doc["review_required"] is True


def test_package_exports_and_thought_node_uct() -> None:
    assert available_submodules()["mcts_kloster"] is True
    n_unvisited = ThoughtNode(node_id="n1", state="s1", prior_prob=0.6, visits=0)
    n_visited = ThoughtNode(
        node_id="n2", state="s2", prior_prob=0.4, visits=4, value_sum=2.0
    )
    assert n_unvisited.mean_value == 0.0
    assert n_visited.mean_value == pytest.approx(0.5)
    assert n_unvisited.uct_score(parent_visits=10) > n_visited.uct_score(parent_visits=10)
    assert "node_id" in n_visited.to_dict()


def test_uct_expansion_and_best_branch_selection() -> None:
    tree: dict[str, list[tuple[str, str, float]]] = {
        "root": [("plan_alpha", "alpha", 0.52), ("plan_beta", "beta", 0.48)],
        "alpha": [("alpha_1", "alpha_1", 0.65), ("alpha_2", "alpha_2", 0.35)],
        "beta": [("beta_1", "beta_1", 0.70), ("beta_2", "beta_2", 0.30)],
    }
    scores = {
        "root": 0.5,
        "alpha": 0.55,
        "beta": 0.50,
        "alpha_1": 0.94,
        "alpha_2": 0.22,
        "beta_1": 0.30,
        "beta_2": 0.15,
    }

    search = KlosterMCTSSearch(samples_per_eval=4, horizon=3)
    res = search.run(
        "root",
        lambda st: tree.get(st, []),
        lambda st: scores[st],
        tau=0.08,
        max_iterations=16,
    )
    assert isinstance(res, MCTSSearchResult)
    assert res.contract == MCTS_KLOSTER_CONTRACT
    assert res.best_branch is not None
    assert isinstance(res.best_branch, MCTSBranchTrajectory)
    assert res.best_branch.actions == ("plan_alpha", "alpha_1")
    assert res.best_branch.states == ("root", "alpha", "alpha_1")
    assert res.best_branch.mean_value == pytest.approx(0.94)
    assert res.expanded_nodes >= 3
    _assert_constitutional(res.constitutional)
    serialized = res.to_dict()
    assert serialized["best_branch"]["actions"] == ["plan_alpha", "alpha_1"]


def test_a_tau_prefix_pruning_and_tight_upper_bound() -> None:
    expanded_states: list[str] = []
    tau = 0.20  # tight_strict_upper_bound(0.20) == ceil(5) - 1 == 4

    def expand_fn(state: str) -> list[ThoughtCandidate]:
        expanded_states.append(state)
        if state == "root":
            return [
                ThoughtCandidate(state="keep_hi", action="keep_hi", prior_prob=0.45),
                ThoughtCandidate(state="keep_mid", action="keep_mid", prior_prob=0.25),
                # Strict P(u) > tau boundary: 0.20 <= 0.20 must be pruned!
                ThoughtCandidate(state="prune_eq", action="prune_eq", prior_prob=0.20),
                ThoughtCandidate(state="prune_lo", action="prune_lo", prior_prob=0.10),
            ]
        if state == "keep_hi":
            return [
                # 0.45 * 0.60 = 0.27 > 0.20 (survives)
                ThoughtCandidate(state="leaf_win", action="leaf_win", prior_prob=0.60),
                # 0.45 * 0.40 = 0.18 <= 0.20 (pruned!)
                ThoughtCandidate(state="leaf_pruned", action="leaf_pruned", prior_prob=0.40),
            ]
        return []

    def eval_fn(state: str) -> float:
        return {"leaf_win": 0.92, "keep_hi": 0.70, "keep_mid": 0.30}.get(state, 0.1)

    search = KlosterMCTSSearch(samples_per_eval=4, horizon=3)
    res = search.run("root", expand_fn, eval_fn, tau=tau, max_iterations=12)

    expected_bound = tight_strict_upper_bound(tau)
    assert expected_bound == 4
    assert res.tight_upper_bound == expected_bound
    assert "prune_eq" not in expanded_states
    assert "prune_lo" not in expanded_states
    assert "leaf_pruned" not in expanded_states

    pruned_actions = {b.actions[-1] for b in res.pruned_branches}
    assert {"prune_eq", "prune_lo", "leaf_pruned"}.issubset(pruned_actions)
    for b in res.pruned_branches:
        assert b.joint_prob <= tau + 1e-12
        assert b.prune_reason is not None and "kloster_prefix_prune" in b.prune_reason

    mh = res.multihorizon_volume
    assert mh["bound_violations"] == 0
    assert all(c <= expected_bound for c in mh["counts_by_h"])
    masses = mh["frontier_mass_by_h"]
    assert all(masses[i + 1] <= masses[i] + 1e-9 for i in range(len(masses) - 1))
    assert len(res.a_tau_trajectory) == res.iterations_run
    assert res.a_tau_trajectory[-1]["pruned_count"] >= 3


def test_theorem13_early_stopping_decide_signal() -> None:
    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [
                ("hyp_0", "hyp_0", 0.40),
                ("hyp_1", "hyp_1", 0.20),
                ("hyp_2", "hyp_2", 0.20),
                ("hyp_3", "hyp_3", 0.20),
            ]
        return []

    def eval_fn(state: str) -> float:
        return 0.95 if state == "hyp_0" else 0.10

    search = KlosterMCTSSearch(samples_per_eval=4, delta=0.005, horizon=2)
    res = search.run("root", expand_fn, eval_fn, tau=0.08, max_iterations=30)

    assert res.decision == "DECIDE_SIGNAL"
    assert res.iterations_run < 30
    assert res.chi2_stats["action"] == "DECIDE_SIGNAL"
    assert res.chi2_stats["z_kloster"] >= res.chi2_stats["z_threshold"]
    assert res.chi2_stats["excess_chi2"] > 0.0
    assert res.best_branch is not None
    assert res.best_branch.actions == ("hyp_0",)


def test_theorem13_abstain_insufficient_evidence_and_gather_more() -> None:
    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [
                ("arm_0", "arm_0", 0.25),
                ("arm_1", "arm_1", 0.25),
                ("arm_2", "arm_2", 0.25),
                ("arm_3", "arm_3", 0.25),
            ]
        return []

    # Flat/uninformative scores across all 4 hypotheses -> uniform null counts -> ABSTAIN
    def flat_eval_fn(_state: str) -> float:
        return 0.50

    search = KlosterMCTSSearch(samples_per_eval=4, delta=0.005, horizon=2)
    res_abstain = search.run("root", expand_fn, flat_eval_fn, tau=0.08, max_iterations=16)

    assert res_abstain.decision == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert res_abstain.iterations_run == 16
    assert res_abstain.chi2_stats["excess_chi2"] <= 0.0
    assert res_abstain.chi2_stats["z_kloster"] < res_abstain.chi2_stats["z_threshold"]

    # Explicit large max_samples with short max_iterations returns GATHER_MORE
    res_gather = search.run(
        "root", expand_fn, flat_eval_fn, tau=0.08, max_iterations=3, max_samples=512
    )
    assert res_gather.decision == "GATHER_MORE"
    assert res_gather.chi2_stats["samples"] == 12


def test_mass_collapse_pruning_all_children_abstains() -> None:
    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [(f"tok_{i}", f"tok_{i}", 0.05) for i in range(6)]
        return []

    search = KlosterMCTSSearch(samples_per_eval=4)
    res = search.run("root", expand_fn, lambda _s: 0.5, tau=0.10, max_iterations=10)
    assert res.decision == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert res.iterations_run == 1
    assert res.best_branch is None
    assert len(res.pruned_branches) == 6
    assert res.multihorizon_volume["counts_by_h"][-1] == 0


def test_async_parallel_sibling_expansion_uses_asyncio_gather() -> None:
    sleep_sec = 0.05

    async def async_expand(state: str) -> list[tuple[str, str, float]]:
        await asyncio.sleep(0.005)
        if state == "root":
            return [(f"s_{i}", f"s_{i}", 0.25) for i in range(4)]
        return []

    async def async_eval(state: str) -> dict[str, Any]:
        await asyncio.sleep(sleep_sec)
        # Emit explicit bin observations concentrating on s_0 so stopping triggers quickly.
        idx = int(state.split("_")[1]) if "_" in state else 0
        return {
            "value": 0.9 if idx == 0 else 0.2,
            "observations": [0, 0, 0, 0] if idx == 0 else [],
        }

    async def _run() -> tuple[MCTSSearchResult, float]:
        search = KlosterMCTSSearch(samples_per_eval=4, horizon=2)
        t0 = time.monotonic()
        res = await search.arun("root", async_expand, async_eval, tau=0.08, max_iterations=10)
        elapsed = time.monotonic() - t0
        return res, elapsed

    res, elapsed = asyncio.run(_run())
    assert res.parallel_batches >= 1
    # 4 siblings in batch 1 evaluated concurrently in ~0.05s instead of 4 * 0.05s = 0.20s
    assert elapsed < 0.35
    assert res.best_branch is not None
    assert res.best_branch.actions == ("s_0",)

    # Also verify synchronous .run() works cleanly inside an already-running event loop.
    async def _run_sync_inside_loop() -> MCTSSearchResult:
        search = KlosterMCTSSearch(samples_per_eval=4, horizon=2)
        return search.run("root", async_expand, async_eval, tau=0.08, max_iterations=6)

    res_nested = asyncio.run(_run_sync_inside_loop())
    assert res_nested.parallel_batches >= 1


def test_fork_candidate_emission_immediate_and_delayed_supercritical() -> None:
    # 1. Immediate fork at h=1 (two close surviving hypotheses)
    def expand_immediate(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [
                ("approach_A", "A", 0.46),
                ("approach_B", "B", 0.44),
                ("noise_C", "C", 0.05),
                ("noise_D", "D", 0.05),
            ]
        return []

    def eval_immediate(state: str) -> float:
        return {"A": 0.84, "B": 0.82}.get(state, 0.10)

    search = KlosterMCTSSearch(samples_per_eval=4, horizon=2)
    res_imm = search.run("root", expand_immediate, eval_immediate, tau=0.08, max_iterations=12)
    assert len(res_imm.fork_candidates) >= 1
    fork0 = res_imm.fork_candidates[0]
    assert isinstance(fork0, ForkCandidate)
    assert fork0.a_tau_at_horizon == 2
    assert len(fork0.competing_branches) == 2
    assert fork0["recommended_action"] == "ASK_USER_FORK_STEERING"

    # 2. Delayed supercritical fork: forced h=1 (A_tau^(1)=1), splits 3 ways at h=2 (A_tau^(2)=3)
    def expand_delayed(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [("forced_prefix", "forced", 0.92), ("tail", "tail", 0.08)]
        if state == "forced":
            return [
                ("fork_1", "f1", 0.36),
                ("fork_2", "f2", 0.34),
                ("fork_3", "f3", 0.30),
            ]
        return []

    def eval_delayed(state: str) -> float:
        return {"forced": 0.60, "f1": 0.85, "f2": 0.83, "f3": 0.80}.get(state, 0.10)

    res_del = search.run("root", expand_delayed, eval_delayed, tau=0.08, max_iterations=12)
    assert res_del.multihorizon_volume["counts_by_h"][:2] == [1, 3]
    delayed_forks = [f for f in res_del.fork_candidates if f.delayed_fork]
    assert len(delayed_forks) == 1
    df = delayed_forks[0]
    assert df.depth == 2
    assert df.a_tau_at_horizon == 3
    assert len(df.competing_branches) == 3
    assert "delayed supercritical fork" in df.reason


def test_optional_zoe_antigravity_bridge_and_voice_adapter(tmp_path: Path) -> None:
    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [("verify_proof", "p1", 0.70), ("skip_proof", "p2", 0.30)]
        return []

    def eval_fn(state: str) -> float:
        return 0.92 if state == "p1" else 0.15

    bridge = ZoeAntigravityBridge(mode="offline", state_dir=tmp_path / "eliza")
    search_bridge = KlosterMCTSSearch(samples_per_eval=4, bridge=bridge)
    res_bridge = search_bridge.run("root", expand_fn, eval_fn, tau=0.08, max_iterations=8)
    assert res_bridge.voice_mode == "offline"
    assert len(res_bridge.voice_traces) >= 2
    assert res_bridge.best_branch is not None
    assert len(res_bridge.best_branch.voice_thoughts) >= 1
    _assert_constitutional(res_bridge.constitutional)

    adapter = CallableVoiceAdapter(
        lambda prompt, ctx: {
            "text": f"voice:{ctx.get('action')}",
            "thoughts": [f"thought:{ctx.get('node_id')}:{prompt[:24]}"],
        }
    )
    search_adapter = KlosterMCTSSearch(samples_per_eval=4, voice_adapter=adapter)
    res_adapter = search_adapter.run("root", expand_fn, eval_fn, tau=0.08, max_iterations=8)
    assert any(t["thought"].startswith("thought:") for t in res_adapter.voice_traces)


def test_validation_and_empty_tree_edge_cases() -> None:
    search = KlosterMCTSSearch()
    with pytest.raises(ValueError, match="tau"):
        search.run("root", lambda _s: [], lambda _s: 0.5, tau=1.0)
    with pytest.raises(ValueError, match="max_iterations"):
        search.run("root", lambda _s: [], lambda _s: 0.5, max_iterations=0)

    res_empty = search.run("root", lambda _s: [], lambda _s: 0.5, tau=0.08, max_iterations=4)
    assert res_empty.decision == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert res_empty.total_nodes == 1
    assert res_empty.best_branch is None


def test_blackboard_measurement_recording_integration(tmp_path: Path) -> None:
    from zoe_autonomy.shared_reasoning.blackboard import (
        EpistemicBlackboard,
        MeasurementRecord,
    )

    bb = EpistemicBlackboard(tmp_path / "mcts_bb.json")

    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [
                ("path_strong", "strong", 0.55),
                ("path_alt", "alt", 0.35),
                ("path_pruned", "pruned", 0.10),
            ]
        return []

    def eval_fn(state: str) -> float:
        return {"strong": 0.93, "alt": 0.20}.get(state, 0.10)

    search = KlosterMCTSSearch(samples_per_eval=4, seed=42, blackboard=bb)
    res = search.run("root", expand_fn, eval_fn, tau=0.12, max_iterations=24)

    assert res.decision == "DECIDE_SIGNAL"
    assert res.blackboard_measurement_id == "meas_0001"
    assert res.to_dict()["blackboard_measurement_id"] == "meas_0001"

    integrity = bb.verify_integrity()
    assert integrity["valid"] is True
    assert len(bb.list_measurements()) == 1
    assert len(bb.list_evidence()) == 0
    assert len(bb.list_beliefs()) == 0
    assert len(bb.list_action_proposals()) == 0

    meas = bb.get_record("meas_0001")
    assert isinstance(meas, MeasurementRecord)
    assert meas.source_agent == "kloster_mcts_search"
    assert meas.method == "KlosterMCTSSearch.arun"
    assert meas.sampled_only is False
    assert meas.value["decision"] == "DECIDE_SIGNAL"
    assert meas.value["counts_by_h"] == list(res.counts_by_h)
    assert meas.value["chi2_stats"]["z_kloster"] == res.chi2_stats["z_kloster"]
    assert meas.value["best_branch_actions"] == ["path_strong"]

    # Also verify per-call blackboard override works independently.
    bb2 = EpistemicBlackboard()
    res2 = KlosterMCTSSearch(samples_per_eval=4).run(
        "root", expand_fn, eval_fn, tau=0.12, max_iterations=24, blackboard=bb2
    )
    assert res2.blackboard_measurement_id == "meas_0001"
    assert len(bb2.list_measurements()) == 1


def test_fork_candidate_summaries_compatible_with_arch8_human_steering() -> None:
    from zoe_autonomy.shared_reasoning.human_steering import (
        HumanSteeringDetector,
        VerifiedPathOption,
    )

    def expand_delayed(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [("forced", "forced", 0.92), ("noise", "noise", 0.08)]
        if state == "forced":
            return [
                ("symbolic_solver", "sym", 0.45),
                ("empirical_probe", "emp", 0.45),
                ("tail", "tail", 0.10),
            ]
        return []

    def eval_delayed(state: str) -> float:
        return {"forced": 0.65, "sym": 0.86, "emp": 0.84, "tail": 0.25}.get(state, 0.1)

    search = KlosterMCTSSearch(samples_per_eval=4, horizon=3, seed=7)
    res = search.run("root", expand_delayed, eval_delayed, tau=0.08, max_iterations=12)

    assert res.counts_by_h[:2] == (1, 3)
    summaries = res.fork_summaries()
    assert len(summaries) >= 1
    first_summary = summaries[0]
    assert first_summary["delayed_fork"] is True
    assert first_summary["a_tau_at_horizon"] == 3
    assert len(first_summary["branch_summaries"]) == 3
    assert first_summary["branch_summaries"][0]["verification_status"] == "unverified_search_hypothesis"

    # Unverified default options from ForkCandidate must NOT be falsely surfaced as verified by Arch 8.
    detector = HumanSteeringDetector()
    unverified_opts = res.fork_candidates[0].to_steering_options()
    unverified_report = detector.detect(
        unverified_opts,
        mcts_result=res.to_human_steering_payload(),
    )
    assert unverified_report.fork_detected is False
    assert unverified_report.suppressed_reason == "fewer_than_two_verified_paths"

    # When branches are backed by independent evidence IDs and distinct trade-offs, Arch 8 detects the fork.
    verified_opts = [
        VerifiedPathOption(
            path_id=bs["path_id"],
            summary=f"{bs['summary']} ({tag})",
            verification_status="verified",
            evidence_ids=(f"ev_000{idx + 1}",),
            expected_utility=bs["expected_utility"],
            tradeoff_notes=notes,
            reversible=(idx == 0),
            direction_tags=(tag,),
        )
        for idx, (bs, tag, notes) in enumerate(
            zip(
                first_summary["branch_summaries"][:2],
                ("formal_sympy_proof", "empirical_sandbox_rollback"),
                (
                    "Exact symbolic proof; zero side effects; deterministic",
                    "Interactive mutation check; requires state rollback; irreversible step",
                ),
            )
        )
    ]
    steered_report = detector.detect(
        verified_opts,
        mcts_result=res.to_human_steering_payload(),
    )
    assert steered_report.fork_detected is True
    assert "supercritical_multihorizon_branching" in steered_report.triggers
    assert steered_report.supercritical_counts[:2] == (1, 3)
    assert steered_report.interaction_spec is not None
    assert steered_report.constitutional["external_actions"] == 0


def test_mcts_kloster_honors_offline_privacy_and_probe_local_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import zoe_autonomy.shared_reasoning.sdk_bridge as sdk_bridge_mod
    import zoe_autonomy.stem_layering as stem_layering_mod

    def _forbid_probe(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("probe_local_qwen must not be called")

    def _forbid_local_openai(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("LocalOpenAIAgentConfig must not be called")

    def _forbid_gemini(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("LocalAgentConfig must not be called")

    monkeypatch.setattr(sdk_bridge_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(sdk_bridge_mod, "LocalOpenAIAgentConfig", _forbid_local_openai)
    monkeypatch.setattr(sdk_bridge_mod, "LocalAgentConfig", _forbid_gemini)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-must-not-be-used")

    def expand_fn(state: str) -> list[tuple[str, str, float]]:
        if state == "root":
            return [("branch_a", "a", 0.65), ("branch_b", "b", 0.35)]
        return []

    def eval_fn(state: str) -> float:
        return 0.90 if state == "a" else 0.20

    auto_bridge = ZoeAntigravityBridge(mode="auto", state_dir=tmp_path / "eliza")
    search = KlosterMCTSSearch(
        samples_per_eval=4,
        bridge=auto_bridge,
        offline_only=True,
        privacy_sensitive=True,
        probe_local=False,
        bridge_mode="offline",
    )
    res = search.run("root", expand_fn, eval_fn, tau=0.08, max_iterations=6)
    assert res.voice_mode == "offline"
    assert len(res.voice_traces) >= 2
    assert all(t["mode"] == "offline" for t in res.voice_traces)

    search_private_no_probe = KlosterMCTSSearch(
        samples_per_eval=4,
        bridge=auto_bridge,
        privacy_sensitive=True,
        probe_local=False,
    )
    res_np = search_private_no_probe.run("root", expand_fn, eval_fn, tau=0.08, max_iterations=6)
    assert res_np.voice_mode == "offline"
    assert len(res_np.voice_traces) >= 2
    assert all(t["mode"] == "offline" for t in res_np.voice_traces)


def test_regression_rejects_nonfinite_priors_and_eval_values() -> None:
    search = KlosterMCTSSearch(samples_per_eval=4)

    # Non-finite or negative prior_prob values must raise ValueError (never produce NaN joint_prob).
    for bad_prior in (float("inf"), float("-inf"), float("nan"), -0.1, True):
        def _expand_bad(s: str, *, _bp: Any = bad_prior) -> list[tuple[str, str, Any]]:
            return [("bad", "bad", _bp), ("good", "good", 0.5)] if s == "root" else []

        with pytest.raises(ValueError, match="prior_prob"):
            search.run(
                "root",
                _expand_bad,
                lambda _s: 0.5,
                tau=0.08,
                max_iterations=4,
            )

        with pytest.raises(ValueError, match="prior_prob"):
            KlosterMCTSSearch._normalize_candidates(
                [ThoughtCandidate(state="bad", action="bad", prior_prob=bad_prior)]
            )

        with pytest.raises(ValueError, match="prior_prob"):
            KlosterMCTSSearch._normalize_candidates(
                [{"action": "bad", "state": "bad", "prior_prob": bad_prior}]
            )

    # Non-finite eval_fn outputs must raise ValueError (never poison mean_value with NaN).
    for bad_eval in (
        float("nan"),
        float("inf"),
        float("-inf"),
        {"value": float("nan")},
        (float("inf"), [0]),
        True,
    ):
        def _eval_bad(_s: str, *, _be: Any = bad_eval) -> Any:
            return _be

        with pytest.raises(ValueError, match="eval_fn"):
            search.run(
                "root",
                lambda s: [("a", "a", 0.6), ("b", "b", 0.4)] if s == "root" else [],
                _eval_bad,
                tau=0.08,
                max_iterations=4,
            )


def test_regression_init_rejects_invalid_fork_thresholds() -> None:
    for bad_val in (
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.01,
        -1.0,
        True,
        False,
    ):
        with pytest.raises(ValueError, match="fork_prob_ratio_threshold"):
            KlosterMCTSSearch(fork_prob_ratio_threshold=bad_val)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="fork_value_gap_threshold"):
            KlosterMCTSSearch(fork_value_gap_threshold=bad_val)  # type: ignore[arg-type]

    # Positive control: valid finite non-negative thresholds work and preserve fork detection.
    search = KlosterMCTSSearch(
        seed=7,
        fork_prob_ratio_threshold=0.0,
        fork_value_gap_threshold=0.0,
    )
    res = search.run(
        "root",
        lambda s: [("a", "a", 0.5), ("b", "b", 0.5)] if s == "root" else [],
        lambda _s: 0.5,
        tau=0.10,
        max_iterations=4,
    )
    assert len(res.fork_candidates) >= 1


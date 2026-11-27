"""Tests for Architecture #8: High-Leverage Human Steering (human_steering.py)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

from google.antigravity.hooks import hook_runner as hook_runner_mod  # noqa: E402
from google.antigravity.hooks import hooks as ag_hooks  # noqa: E402
from google.antigravity.types import (  # noqa: E402
    AskQuestionInteractionSpec,
    QuestionHookResult,
    QuestionResponse,
)

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.metacognition import (  # noqa: E402
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    options_from_probabilities,
)
from zoe_autonomy.shared_reasoning.blackboard import EpistemicBlackboard, EvidenceRecord  # noqa: E402
from zoe_autonomy.shared_reasoning.human_steering import (  # noqa: E402
    HUMAN_STEERING_CONTRACT,
    INTERACTION_MODE,
    REJECT_ALL_OPTION_ID,
    REQUEST_REVERSIBLE_OPTION_ID,
    STOP_OPTION_ID,
    ForkPointReport,
    HumanSteeringDetector,
    VerifiedPathOption,
)
from zoe_autonomy.shared_reasoning.mcts_kloster import (  # noqa: E402
    KlosterMCTSSearch,
    ThoughtCandidate,
)
from zoe_autonomy.shared_reasoning.quorum import (  # noqa: E402
    FourPeerQuorumEngine,
    PeerConfidenceVector,
    evaluate_four_peer_quorum,
)


def _assert_constitutional(meta: dict) -> None:
    assert meta["external_actions"] == 0
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def _make_verified_pair() -> tuple[VerifiedPathOption, VerifiedPathOption]:
    opt_a = VerifiedPathOption(
        path_id="path_reversible_patch",
        summary="Apply reversible feature-flagged adapter patch",
        verification_status="verified",
        evidence_ids=("ev-001", "ev-002"),
        expected_utility=0.78,
        tradeoff_notes="Lower peak throughput, fully reversible rollback via config flag",
        reversible=True,
        direction_tags=("conservative", "incremental"),
        verifier_name="pytest_sandbox",
    )
    opt_b = VerifiedPathOption(
        path_id="path_schema_migration",
        summary="Migrate storage schema in place for zero-copy reads",
        verification_status="verified",
        evidence_ids=("ev-003",),
        expected_utility=0.91,
        tradeoff_notes="Higher throughput and lower memory, requires irreversible table rewrite",
        reversible=False,
        direction_tags=("performance", "structural"),
        verifier_name="z3_invariant_checker",
    )
    return opt_a, opt_b


def test_package_lazy_export_and_validation() -> None:
    assert sr.available_submodules()["human_steering"] is True
    assert sr.HumanSteeringDetector is HumanSteeringDetector

    with pytest.raises(ValueError, match="expected_utility"):
        VerifiedPathOption(
            path_id="bad",
            summary="Bad utility",
            verification_status="verified",
            evidence_ids=("ev-1",),
            expected_utility=float("nan"),
            tradeoff_notes="none",
            reversible=True,
        )

    with pytest.raises(ValueError, match="evidence_ids"):
        VerifiedPathOption(
            path_id="bad2",
            summary="String instead of sequence",
            verification_status="verified",
            evidence_ids="ev-1",  # type: ignore[arg-type]
            expected_utility=0.5,
            tradeoff_notes="none",
            reversible=True,
        )


def test_supercritical_multihorizon_branching_triggers_fork_detection() -> None:
    # Step 1 looks locally settled (0.90), then step 2 branches into 3 surviving paths (> tau=0.12)
    def branching_dist(prefix: tuple[int, ...]) -> np.ndarray:
        if len(prefix) == 0:
            return np.array([0.90, 0.04, 0.03, 0.02, 0.01])
        if len(prefix) == 1:
            return np.array([0.36, 0.33, 0.25, 0.04, 0.02])
        return np.array([0.85, 0.06, 0.04, 0.03, 0.02])

    opt_a, opt_b = _make_verified_pair()
    detector = HumanSteeringDetector()
    report = detector.detect(
        [opt_a, opt_b],
        next_dist_fn=branching_dist,
        tau=0.12,
        horizon=3,
        context_summary="storage backend decision",
    )

    assert isinstance(report, ForkPointReport)
    assert report.contract == HUMAN_STEERING_CONTRACT
    assert report.interaction_mode == INTERACTION_MODE
    assert report.fork_detected is True
    assert report.supercritical_counts[0] == 1
    assert report.supercritical_counts[1] > report.supercritical_counts[0]
    assert "supercritical_multihorizon_branching" in report.triggers
    assert "irreversible_high_impact_boundary" in report.triggers
    assert len(report.divergent_options) == 2
    assert report.prompt_for_human is not None
    assert "path_reversible_patch" in report.prompt_for_human
    assert "path_schema_migration" in report.prompt_for_human
    assert report.interaction_spec is not None
    _assert_constitutional(report.constitutional)

    # Non-supercritical flat trajectory [1, 1, 1] with only reversible options and no triggers -> no fork
    def settled_dist(_prefix: tuple[int, ...]) -> np.ndarray:
        return np.array([0.90, 0.04, 0.03, 0.02, 0.01])

    rev_a = opt_a
    rev_c = VerifiedPathOption(
        path_id="path_alt_reversible",
        summary="Use cached local index adapter",
        verification_status="verified",
        evidence_ids=("ev-004",),
        expected_utility=0.72,
        tradeoff_notes="Uses extra RAM instead of disk cache, completely reversible",
        reversible=True,
        direction_tags=("memory_tradeoff",),
    )
    no_trigger_report = detector.detect([rev_a, rev_c], next_dist_fn=settled_dist, tau=0.12, horizon=3)
    assert no_trigger_report.supercritical_counts == (1, 1, 1)
    assert no_trigger_report.fork_detected is False
    assert no_trigger_report.suppressed_reason == "no_fork_trigger_active"
    assert no_trigger_report.prompt_for_human is None
    assert no_trigger_report.divergent_options == ()


def test_high_theorem15_quorum_disagreement_dk_triggers_fork() -> None:
    # Construct genuinely divergent 4-peer quorum vectors (Zoe/User vs Clara/Antigravity)
    zoe = PeerConfidenceVector("zoe", [0.85, 0.10, 0.05], "document", "prov:zoe:1", "indep:zoe")
    clara = PeerConfidenceVector("clara", [0.10, 0.80, 0.10], "validated_reflection", "prov:clara:1", "indep:clara")
    ag = PeerConfidenceVector("antigravity", [0.15, 0.15, 0.70], "model", "prov:ag:1", "indep:ag")
    user = PeerConfidenceVector("user", [0.75, 0.15, 0.10], "user", "prov:user:1", "indep:user")
    q_res = evaluate_four_peer_quorum(zoe, clara, ag, user, tau=0.05)
    assert q_res.d_k_disagreement >= 0.12

    opt_1 = VerifiedPathOption(
        path_id="path_symbolic",
        summary="Verify policy invariants with Z3 solver first",
        verification_status="verified",
        evidence_ids=("ev-sym-1",),
        expected_utility=0.82,
        tradeoff_notes="Slower preflight check, eliminates false positives",
        reversible=True,
    )
    opt_2 = VerifiedPathOption(
        path_id="path_empirical",
        summary="Run sandboxed property-based test harness",
        verification_status="verified",
        evidence_ids=("ev-emp-2",),
        expected_utility=0.80,
        tradeoff_notes="Faster iteration, covers statistical edge cases rather than universal proof",
        reversible=True,
    )

    detector = HumanSteeringDetector(dk_threshold=0.12)
    report = detector.detect([opt_1, opt_2], quorum_result=q_res)

    assert report.fork_detected is True
    assert report.quorum_disagreement_dk == pytest.approx(q_res.d_k_disagreement)
    assert "high_quorum_disagreement_dk" in report.triggers
    assert report.prompt_for_human is not None
    assert f"D_K={q_res.d_k_disagreement:.4f}" in report.prompt_for_human

    # Below threshold D_K does not trigger high_quorum_disagreement_dk
    low_dk_report = detector.detect([opt_1, opt_2], quorum_disagreement_dk=0.03)
    assert low_dk_report.fork_detected is False
    assert "high_quorum_disagreement_dk" not in low_dk_report.triggers


def test_option_shift_narrowing_and_irreversible_boundary_triggers() -> None:
    meta = OperationalMetacognition()
    prov_weak = Provenance(
        sources=(EvidenceSource("prior", "heuristic_guess", 0.4, 0.4),),
        transformations=("initial_prior",),
    )
    prev_opts = options_from_probabilities({"a": 0.34, "b": 0.33, "c": 0.33}, prov_weak)
    curr_opts = options_from_probabilities({"a": 0.85, "b": 0.08, "c": 0.07}, prov_weak)
    thresh = meta.threshold(Domain.ACTION, 0.15)
    prev_b = meta.count(prev_opts, thresh)
    curr_b = meta.count(curr_opts, thresh)
    shift = meta.shift(prev_b, curr_b, transition=prov_weak, narrowing_drop=2)
    assert shift.suspected_unjustified_narrowing is True

    opt_a, opt_b = _make_verified_pair()
    detector = HumanSteeringDetector()
    report = detector.detect([opt_a, opt_b], option_shift=shift)

    assert report.fork_detected is True
    assert report.option_shift_narrowed is True
    assert report.irreversible_boundary_triggered is True
    assert "option_shift_narrowing" in report.triggers
    assert "irreversible_high_impact_boundary" in report.triggers

    spec = detector.build_interaction_spec(report)
    assert spec is not None
    option_ids = [o.id for o in spec.questions[0].options]
    assert "path_reversible_patch" in option_ids
    assert "path_schema_migration" in option_ids
    assert REJECT_ALL_OPTION_ID in option_ids
    assert STOP_OPTION_ID in option_ids
    assert REQUEST_REVERSIBLE_OPTION_ID in option_ids


def test_unverified_and_failed_paths_filtered_and_single_path_suppressed() -> None:
    verified_only = VerifiedPathOption(
        path_id="verified_path",
        summary="Deterministic verified path",
        verification_status="verified",
        evidence_ids=("ev-101",),
        expected_utility=0.85,
        tradeoff_notes="Clean reversible execution",
        reversible=True,
    )
    unverified_path = VerifiedPathOption(
        path_id="unverified_path",
        summary="Speculative unverified path",
        verification_status="unverified",
        evidence_ids=("ev-102",),
        expected_utility=0.99,
        tradeoff_notes="Fastest but unverified",
        reversible=False,
    )
    failed_path = VerifiedPathOption(
        path_id="failed_path",
        summary="Failed verifier path",
        verification_status="failed",
        evidence_ids=("ev-103",),
        expected_utility=0.95,
        tradeoff_notes="Failed unit checks",
        reversible=True,
    )
    no_ev_path = VerifiedPathOption(
        path_id="missing_evidence_path",
        summary="Claimed verified without evidence",
        verification_status="verified",
        evidence_ids=(),
        expected_utility=0.90,
        tradeoff_notes="Missing evidence IDs",
        reversible=True,
    )

    detector = HumanSteeringDetector()
    # Even with supercritical counts AND high D_K, only 1 verified path survives -> suppress!
    report = detector.detect(
        [verified_only, unverified_path, failed_path, no_ev_path],
        supercritical_counts=[1, 3, 4],
        quorum_disagreement_dk=0.35,
    )

    assert report.fork_detected is False
    assert report.suppressed_reason == "fewer_than_two_verified_paths"
    assert report.divergent_options == ()
    assert report.prompt_for_human is None
    assert report.interaction_spec is None
    assert len(report.filtered_out_options) == 3
    filtered_ids = {item["path_id"] for item in report.filtered_out_options}
    assert filtered_ids == {"unverified_path", "failed_path", "missing_evidence_path"}


def test_redundant_verified_paths_suppress_false_fork_prompt() -> None:
    p1 = VerifiedPathOption(
        path_id="dup_1",
        summary="Run standard local lint and pytest suite",
        verification_status="verified",
        evidence_ids=("ev-1",),
        expected_utility=0.85,
        tradeoff_notes="Low risk, local reversible execution",
        reversible=True,
        direction_tags=("standard",),
    )
    p2 = VerifiedPathOption(
        path_id="dup_2",
        summary="Run standard local pytest and lint suite",
        verification_status="verified",
        evidence_ids=("ev-2",),
        expected_utility=0.85,
        tradeoff_notes="Low risk, local reversible execution",
        reversible=True,
        direction_tags=("standard",),
    )
    detector = HumanSteeringDetector()
    report = detector.detect([p1, p2], supercritical_counts=[1, 2], quorum_disagreement_dk=0.20)
    assert report.fork_detected is False
    assert report.suppressed_reason == "verified_paths_not_significantly_divergent"
    assert report.prompt_for_human is None


def test_blackboard_evidence_gating_and_no_fabricated_urgency() -> None:
    bb = EpistemicBlackboard()
    prov = Provenance(
        sources=(EvidenceSource("tool", "sympy_prover", 0.9, 0.9),),
        transformations=("symbolic_check",),
    )
    m_pass = bb.post_measurement(
        source_agent="prover",
        input_desc="invariant A",
        method="sympy",
        scope="unit",
        limitations="symbolic",
        value={"ok": True},
        sampled_only=False,
        provenance=prov,
    )
    ev_pass = bb.promote_to_evidence(
        m_pass.record_id,
        verifier_name="sympy",
        passed=True,
        rationale="Deterministic symbolic identity verified.",
    )
    m_fail = bb.post_measurement(
        source_agent="prover",
        input_desc="invariant B",
        method="sympy",
        scope="unit",
        limitations="symbolic",
        value={"ok": False},
        sampled_only=False,
        provenance=prov,
    )
    ev_fail = bb.promote_to_evidence(
        m_fail.record_id,
        verifier_name="sympy",
        passed=False,
        rationale="Counterexample found.",
    )

    opt_good = VerifiedPathOption(
        path_id="bb_good",
        summary="Keep deterministic solver path",
        verification_status="verified",
        evidence_ids=(ev_pass.record_id,),
        expected_utility=0.80,
        tradeoff_notes="Reversible local check",
        reversible=True,
    )
    opt_sneaky_fail = VerifiedPathOption(
        path_id="bb_failed_claim",
        summary="Aggressive rewrite claiming verified",
        verification_status="verified",
        evidence_ids=(ev_fail.record_id,),
        expected_utility=0.95,
        tradeoff_notes="Irreversible change",
        reversible=False,
    )
    opt_good_2 = VerifiedPathOption(
        path_id="bb_good_alt",
        summary="Run full AST static migration",
        verification_status="verified",
        evidence_ids=(ev_pass.record_id,),
        expected_utility=0.88,
        tradeoff_notes="Higher coverage, irreversible file edits without backup branch",
        reversible=False,
    )

    detector = HumanSteeringDetector()
    report = detector.detect(
        [opt_good, opt_sneaky_fail, opt_good_2],
        quorum_disagreement_dk=0.22,
        blackboard=bb,
        record_to_blackboard=True,
        context_summary="blackboard-gated fork",
    )

    assert report.fork_detected is True
    assert {o.path_id for o in report.divergent_options} == {"bb_good", "bb_good_alt"}
    assert any(
        item["path_id"] == "bb_failed_claim" and "blackboard_evidence_failed" in item["reason"]
        for item in report.filtered_out_options
    )
    assert len(bb.list_measurements()) == 3  # m_pass, m_fail, + steering measurement
    assert len(bb.list_beliefs()) == 0
    assert len(bb.list_action_proposals()) == 0

    # CONSTITUTION.md Art. I.2: never fabricate urgency
    assert report.prompt_for_human is not None
    lower_prompt = report.prompt_for_human.lower()
    for banned_urgency in ("act now", "immediately", "urgent!", "last chance", "must decide now"):
        assert banned_urgency not in lower_prompt
    assert "no urgency is implied" in report.constitutional_notice.lower()


def test_antigravity_on_interaction_hook_and_hook_runner_integration() -> None:
    opt_a, opt_b = _make_verified_pair()
    detector = HumanSteeringDetector()
    report = detector.detect([opt_a, opt_b], supercritical_counts=[1, 3], high_impact=True)
    assert report.fork_detected is True

    spec = detector.build_interaction_spec(report)
    assert isinstance(spec, AskQuestionInteractionSpec)

    # 1. Sync callback returning chosen path_id string via HookRunner.dispatch_interaction
    hook_select = detector.build_interaction_hook(lambda s: "path_reversible_patch")
    assert isinstance(hook_select, ag_hooks.OnInteractionHook)
    runner = hook_runner_mod.HookRunner(hooks=[hook_select])
    turn_ctx = ag_hooks.TurnContext(runner.session_context)

    hook_res, q_res, _op_ctx = asyncio.run(runner.dispatch_interaction(turn_ctx, spec))
    assert hook_res.allow is True
    assert isinstance(q_res, QuestionHookResult)
    assert q_res.cancelled is False
    assert q_res.responses[0].selected_option_ids == ["path_reversible_patch"]

    interp = detector.interpret_hook_result(report, q_res)
    assert interp["decision"] == "selected"
    assert interp["selected_path_id"] == "path_reversible_patch"
    assert interp["external_actions"] == 0
    assert interp["human_override_respected"] is True

    # 2. Async callback returning QuestionHookResult to reject all (Art. I.3)
    async def reject_cb(_ctx: ag_hooks.HookContext, _spec: AskQuestionInteractionSpec) -> QuestionHookResult:
        return QuestionHookResult(
            responses=[QuestionResponse(selected_option_ids=[REJECT_ALL_OPTION_ID])],
            cancelled=False,
        )

    hook_reject = detector.build_interaction_hook(reject_cb)
    runner_reject = hook_runner_mod.HookRunner(hooks=[hook_reject])
    _, q_reject, _ = asyncio.run(
        runner_reject.dispatch_interaction(ag_hooks.TurnContext(runner_reject.session_context), spec)
    )
    interp_reject = detector.interpret_hook_result(report, q_reject)
    assert interp_reject["decision"] == "rejected"
    assert interp_reject["selected_path_id"] is None
    assert interp_reject["external_actions"] == 0

    # 3. None response defaults safely to cancelled (never silently auto-approves)
    hook_cancel = detector.build_interaction_hook(lambda _spec: None)
    runner_cancel = hook_runner_mod.HookRunner(hooks=[hook_cancel])
    _, q_cancel, _ = asyncio.run(
        runner_cancel.dispatch_interaction(ag_hooks.TurnContext(runner_cancel.session_context), spec)
    )
    assert q_cancel.cancelled is True
    interp_cancel = detector.interpret_hook_result(report, q_cancel)
    assert interp_cancel["decision"] == "cancelled"
    assert interp_cancel["external_actions"] == 0


def test_round2_mcts_quorum_blackboard_to_human_steering_integration() -> None:
    """End-to-end integration: Arch 3 (KlosterMCTSSearch) + Arch 4 (FourPeerQuorumEngine)
    + Arch 6 (EpistemicBlackboard) -> Arch 8 (HumanSteeringDetector) + Antigravity hook.
    """
    # 1. Arch 3: MCTS tree with forced root step that forks at depth 2 into 3 surviving branches
    def expand_fn(state: str):
        if state == "root":
            return [
                ThoughtCandidate(action="stage_preflight", state="preflight", prior_prob=0.90),
                ThoughtCandidate(action="discard_noisy", state="noisy", prior_prob=0.05),
            ]
        if state == "preflight":
            return [
                ThoughtCandidate(action="reversible_adapter", state="leaf_rev", prior_prob=0.38),
                ThoughtCandidate(action="inplace_migration", state="leaf_mig", prior_prob=0.35),
                ThoughtCandidate(action="unverified_heuristic", state="leaf_unv", prior_prob=0.22),
            ]
        return []

    def eval_fn(state: str):
        values = {
            "preflight": 0.70,
            "leaf_rev": 0.84,
            "leaf_mig": 0.87,
            "leaf_unv": 0.92,
            "noisy": 0.10,
        }
        return {"value": values.get(state, 0.5), "is_terminal": state.startswith("leaf_")}

    search = KlosterMCTSSearch(horizon=3)
    mcts_res = search.run("root", expand_fn, eval_fn, tau=0.10, max_iterations=8)
    assert mcts_res.fork_candidates, "expected MCTS to emit surviving fork candidates"

    # Extract competing branches from the delayed/supercritical fork candidate
    branches = [b for fc in mcts_res.fork_candidates for b in fc.competing_branches]
    rev_branch = next(b for b in branches if "reversible_adapter" in b.actions)
    mig_branch = next(b for b in branches if "inplace_migration" in b.actions)
    unv_branch = next((b for b in branches if "unverified_heuristic" in b.actions), None)

    # 2. Arch 6: EpistemicBlackboard verifies only rev_branch and mig_branch (NOT unv_branch)
    bb = EpistemicBlackboard()
    prov = Provenance(
        sources=(EvidenceSource("tool", "sandbox_verifier", 0.92, 0.90),),
        transformations=("deterministic_replay",),
    )
    m_rev = bb.post_measurement(
        source_agent="sandbox",
        input_desc=rev_branch.branch_id,
        method="pytest_replay",
        scope="local_module",
        limitations="unit sandbox only",
        value={"passed": True},
        sampled_only=False,
        provenance=prov,
    )
    ev_rev = bb.promote_to_evidence(
        m_rev.record_id,
        verifier_name="pytest_replay",
        passed=True,
        rationale="Deterministic sandbox check passed with rollback verified.",
    )
    m_mig = bb.post_measurement(
        source_agent="z3_checker",
        input_desc=mig_branch.branch_id,
        method="z3_invariant",
        scope="schema",
        limitations="static model",
        value={"passed": True},
        sampled_only=False,
        provenance=prov,
    )
    ev_mig = bb.promote_to_evidence(
        m_mig.record_id,
        verifier_name="z3_invariant",
        passed=True,
        rationale="Deterministic invariant check passed; schema change is irreversible.",
    )

    # 3. Arch 4: FourPeerQuorumEngine detects high Theorem 15 peer disagreement D_K
    quorum_engine = FourPeerQuorumEngine()
    q_res = quorum_engine.evaluate(
        [
            PeerConfidenceVector("zoe", [0.82, 0.12, 0.06], "document", "prov:zoe:r2", "indep:zoe"),
            PeerConfidenceVector("clara", [0.12, 0.78, 0.10], "validated_reflection", "prov:clara:r2", "indep:clara"),
            PeerConfidenceVector("antigravity", [0.18, 0.14, 0.68], "model", "prov:ag:r2", "indep:ag"),
            PeerConfidenceVector("user", [0.76, 0.16, 0.08], "user", "prov:user:r2", "indep:user"),
        ],
        tau=0.05,
    )
    assert q_res.d_k_disagreement >= 0.12

    # 4. Arch 8: HumanSteeringDetector consumes MCTSSearchResult + FourPeerQuorumResult + EpistemicBlackboard
    detector = HumanSteeringDetector(dk_threshold=0.12)
    report = detector.detect(
        mcts_result=mcts_res,
        evidence_by_branch={
            rev_branch.branch_id: (ev_rev.record_id,),
            mig_branch.branch_id: (ev_mig.record_id,),
        },
        reversible_by_branch={
            rev_branch.branch_id: True,
            mig_branch.branch_id: False,
        },
        tradeoff_by_branch={
            rev_branch.branch_id: "Reversible config-flagged adapter with lower throughput",
            mig_branch.branch_id: "Irreversible schema rewrite with higher throughput",
        },
        quorum_result=q_res,
        blackboard=bb,
        record_to_blackboard=True,
        propose_blackboard_action=True,
        context_summary="round2_mcts_quorum_blackboard_steering",
    )

    assert report.fork_detected is True
    assert "supercritical_multihorizon_branching" in report.triggers
    assert "high_quorum_disagreement_dk" in report.triggers
    assert "irreversible_high_impact_boundary" in report.triggers
    assert report.quorum_disagreement_dk == pytest.approx(q_res.d_k_disagreement)
    assert {o.path_id for o in report.divergent_options} == {
        rev_branch.branch_id,
        mig_branch.branch_id,
    }
    if unv_branch is not None:
        assert any(
            item["path_id"] == unv_branch.branch_id and item["verification_status"] == "unverified"
            for item in report.filtered_out_options
        )

    # Verify EpistemicBlackboard received deterministic measurement + REVIEW_REQUIRED action proposal
    assert bb.verify_integrity()["valid"] is True
    assert "action_proposal_id" in report.blackboard_records
    action_rec = bb.get_action_proposal(report.blackboard_records["action_proposal_id"])
    assert action_rec.action_kind == "ASK_USER_FORK_STEERING"
    assert action_rec.reversible is True
    assert action_rec.status == "REVIEW_REQUIRED"
    assert action_rec.external_actions == 0
    assert action_rec.requires_human_review is True
    assert action_rec.autonomous_execution_allowed is False

    # 5. Antigravity OnInteractionHook execution over the integrated report
    spec = detector.build_interaction_spec(report)
    assert spec is not None
    hook = detector.build_interaction_hook(lambda _s: rev_branch.branch_id)
    runner = hook_runner_mod.HookRunner(hooks=[hook])
    hook_res, q_hook_res, _ = asyncio.run(
        runner.dispatch_interaction(ag_hooks.TurnContext(runner.session_context), spec)
    )
    assert hook_res.allow is True
    interp = detector.interpret_hook_result(report, q_hook_res)
    assert interp["decision"] == "selected"
    assert interp["selected_path_id"] == rev_branch.branch_id
    assert interp["external_actions"] == 0


def test_blackboard_gating_rejects_raw_measurement_unknown_id_unapproved_and_sampled_without_strong_source() -> None:
    bb = EpistemicBlackboard()
    m3 = bb.post_measurement("p", "in", "det", "s", "l", 1)
    ev3 = bb.promote_to_evidence(
        m3.record_id,
        "det",
        True,
        "deterministic check passed",
        evidence_source=EvidenceSource(kind="tool", identifier="det", trust=0.95, strength=0.95),
    )
    bel3 = bb.update_belief([ev3.record_id], "verified claim", 0.3)

    # Sampled measurement promoted with strong Z3 EvidenceSource should still be accepted
    m_sampled = bb.post_measurement("mc", "in", "mc", "s", "l", 1, sampled_only=True)
    ev_sampled_strong = bb.promote_to_evidence(
        m_sampled.record_id,
        "z3_formal",
        True,
        "Exhaustive Z3 formal proof verified invariant.",
        evidence_source=EvidenceSource(kind="tool", identifier="z3", trust=0.98, strength=0.98),
    )

    det = HumanSteeringDetector()
    # Exact challenger_m4 reproduction scenario: 1 valid + raw MeasurementRecord + unknown ID -> suppressed
    rep_probe = det.detect(
        [
            VerifiedPathOption("ok", "Valid", "verified", (ev3.record_id,), 0.8, "safe", True, ("a",)),
            VerifiedPathOption("meas", "Raw measurement", "verified", (m3.record_id,), 0.9, "risky", False, ("b",)),
            VerifiedPathOption("ghost", "Unknown ID", "verified", ("ev_nonexistent",), 0.7, "other", False, ("c",)),
            VerifiedPathOption("belief", "Belief ID", "verified", (bel3.record_id,), 0.85, "other2", False, ("d",)),
        ],
        high_impact=True,
        blackboard=bb,
    )
    assert rep_probe.fork_detected is False
    assert rep_probe.suppressed_reason == "fewer_than_two_verified_paths"
    reasons = {item["path_id"]: item["reason"] for item in rep_probe.filtered_out_options}
    assert reasons["meas"] == f"invalid_blackboard_lane:{m3.record_id}"
    assert reasons["ghost"] == "unknown_blackboard_evidence:ev_nonexistent"
    assert reasons["belief"] == f"invalid_blackboard_lane:{bel3.record_id}"

    # Mock blackboard holding unapproved & sampled-without-strong-source EvidenceRecords
    class _MockBB:
        def __init__(self, recs: dict[str, object]) -> None:
            self._recs = recs

        def get_record(self, eid: str) -> object:
            return self._recs[eid]

    class _DuckSampledOnly:
        lane = "evidence"
        passed = True
        approved = True
        sampled_only = True
        evidence_source = None

    mock_bb = _MockBB(
        {
            "ev_valid": ev3,
            "ev_sampled_strong": ev_sampled_strong,
            "ev_unapproved": EvidenceRecord(
                record_id="ev_unapproved",
                seq=1,
                measurement_id=m3.record_id,
                verifier_name="v",
                passed=True,
                approved=False,
                rationale="unapproved",
                sampled_source=False,
                evidence_source=None,
                negative_result=False,
                created_utc="2026-11-24T00:00:00Z",
                prev_hash="GENESIS",
                entry_sha256="0" * 64,
            ),
            "ev_sampled_no_src": EvidenceRecord(
                record_id="ev_sampled_no_src",
                seq=2,
                measurement_id=m_sampled.record_id,
                verifier_name="v",
                passed=True,
                approved=True,
                rationale="sampled without strong source",
                sampled_source=True,
                evidence_source=None,
                negative_result=False,
                created_utc="2026-11-24T00:00:00Z",
                prev_hash="GENESIS",
                entry_sha256="0" * 64,
            ),
            "ev_sampled_weak_src": EvidenceRecord(
                record_id="ev_sampled_weak_src",
                seq=3,
                measurement_id=m_sampled.record_id,
                verifier_name="v",
                passed=True,
                approved=True,
                rationale="sampled with weak prior source",
                sampled_source=True,
                evidence_source={"kind": "prior", "identifier": "guess", "trust": 0.4, "strength": 0.4},
                negative_result=False,
                created_utc="2026-11-24T00:00:00Z",
                prev_hash="GENESIS",
                entry_sha256="0" * 64,
            ),
            "ev_duck_sampled": _DuckSampledOnly(),
        }
    )

    rep_mock = det.detect(
        [
            VerifiedPathOption("p_valid", "Valid deterministic", "verified", ("ev_valid",), 0.7, "reversible adapter", True, ("safe",)),
            VerifiedPathOption("p_sampled_strong", "Z3 verified sampled", "verified", ("ev_sampled_strong",), 0.9, "irreversible rewrite", False, ("fast",)),
            VerifiedPathOption("p_unapproved", "Unapproved", "verified", ("ev_unapproved",), 0.95, "bad1", False, ("u1",)),
            VerifiedPathOption("p_sampled_no_src", "Sampled no source", "verified", ("ev_sampled_no_src",), 0.95, "bad2", False, ("u2",)),
            VerifiedPathOption("p_sampled_weak", "Sampled weak source", "verified", ("ev_sampled_weak_src",), 0.95, "bad3", False, ("u3",)),
            VerifiedPathOption("p_duck", "Duck sampled_only", "verified", ("ev_duck_sampled",), 0.95, "bad4", False, ("u4",)),
        ],
        high_impact=True,
        blackboard=mock_bb,
    )
    assert rep_mock.fork_detected is True
    assert {o.path_id for o in rep_mock.divergent_options} == {"p_valid", "p_sampled_strong"}
    mock_reasons = {item["path_id"]: item["reason"] for item in rep_mock.filtered_out_options}
    assert mock_reasons["p_unapproved"] == "blackboard_evidence_unapproved:ev_unapproved"
    assert mock_reasons["p_sampled_no_src"] == "blackboard_sampled_only:ev_sampled_no_src"
    assert mock_reasons["p_sampled_weak"] == "blackboard_sampled_only:ev_sampled_weak_src"
    assert mock_reasons["p_duck"] == "blackboard_sampled_only:ev_duck_sampled"


def test_interaction_hook_default_arg_lambda_and_context_callbacks() -> None:
    opt_a, opt_b = _make_verified_pair()
    detector = HumanSteeringDetector()
    report = detector.detect([opt_a, opt_b], supercritical_counts=[1, 3], high_impact=True)
    spec = detector.build_interaction_spec(report)
    assert spec is not None

    seen_specs: list[object] = []

    def _default_arg_cb(s: AskQuestionInteractionSpec, choice: str = "path_reversible_patch") -> str:
        seen_specs.append(s)
        return choice

    hook1 = detector.build_interaction_hook(_default_arg_cb)
    runner1 = hook_runner_mod.HookRunner(hooks=[hook1])
    _, q_res1, _ = asyncio.run(
        runner1.dispatch_interaction(ag_hooks.TurnContext(runner1.session_context), spec)
    )
    assert len(seen_specs) == 1 and isinstance(seen_specs[0], AskQuestionInteractionSpec)
    assert q_res1.responses[0].selected_option_ids == ["path_reversible_patch"]

    # Also test lambda with default-arg capture: lambda s, c=choice: c
    choice = "path_schema_migration"
    hook2 = detector.build_interaction_hook(lambda s, c=choice: c)  # type: ignore[misc]
    runner2 = hook_runner_mod.HookRunner(hooks=[hook2])
    _, q_res2, _ = asyncio.run(
        runner2.dispatch_interaction(ag_hooks.TurnContext(runner2.session_context), spec)
    )
    assert q_res2.responses[0].selected_option_ids == ["path_schema_migration"]

    # Callback with explicit leading context param and defaulted spec still receives (context, spec)
    seen_pairs: list[tuple[object, object]] = []

    def _ctx_cb(context: ag_hooks.HookContext, s: AskQuestionInteractionSpec | None = None) -> str:
        seen_pairs.append((context, s))
        return STOP_OPTION_ID

    hook3 = detector.build_interaction_hook(_ctx_cb)
    runner3 = hook_runner_mod.HookRunner(hooks=[hook3])
    _, q_res3, _ = asyncio.run(
        runner3.dispatch_interaction(ag_hooks.TurnContext(runner3.session_context), spec)
    )
    assert len(seen_pairs) == 1
    assert isinstance(seen_pairs[0][0], ag_hooks.HookContext)
    assert isinstance(seen_pairs[0][1], AskQuestionInteractionSpec)
    assert q_res3.responses[0].selected_option_ids == [STOP_OPTION_ID]


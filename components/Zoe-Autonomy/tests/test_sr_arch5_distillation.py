"""Unit tests for Architecture 5: System-2 -> System-1 Distillation (distillation.py)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

from google.antigravity import InlineSkill  # type: ignore[import-untyped]  # noqa: E402

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.l4_multi_module import UnsafeFunctionASTError  # noqa: E402
from zoe_autonomy.l5_memory import ZoeUnifiedMemory  # noqa: E402
from zoe_autonomy.metacognition import EvidenceSource, Provenance  # noqa: E402
from zoe_autonomy.shared_reasoning.alpha_evolve import (  # noqa: E402
    AlphaEvolveLoop,
    TestCase,
)
from zoe_autonomy.shared_reasoning.blackboard import (  # noqa: E402
    EpistemicBlackboard,
    FirewallViolationError,
)
from zoe_autonomy.shared_reasoning.distillation import (  # noqa: E402
    DISTILLATION_CONTRACT,
    DistillationRegressionError,
    DistillationRejectedError,
    DistilledArtifact,
    DistilledRuleRegistry,
    System2To1Distiller,
    System2Trace,
    UnknownRollbackTokenError,
)
from zoe_autonomy.shared_reasoning.sdk_bridge import ZoeAntigravityBridge  # noqa: E402
from zoe_autonomy.zoe_eliza import ElizaRule  # noqa: E402


def _assert_constitutional_meta(meta: dict[str, object]) -> None:
    assert meta["external_actions"] == 0
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def _verified_provenance(identifier: str = "zoe_verifier:pytest") -> Provenance:
    return Provenance(
        sources=(EvidenceSource("tool", identifier, 0.96, 0.94),),
        transformations=("system2_search", "deterministic_verifier"),
    )


def test_lazy_exports_and_constitutional_metadata() -> None:
    assert sr.System2To1Distiller is System2To1Distiller
    distiller = System2To1Distiller()
    summary = distiller.summary()
    assert summary["contract"] == DISTILLATION_CONTRACT
    _assert_constitutional_meta(summary["constitutional"])


def test_procedural_ast_skill_distillation_fast_replay_and_persistence() -> None:
    src = (
        "def kloster_margin(p_top, p_second, tau):\n"
        "    gap = p_top - p_second\n"
        "    if p_top >= tau and gap > 0.1:\n"
        "        return gap\n"
        "    return 0.0\n"
    )
    trace = System2Trace(
        task_prompt="Compute confidence margin above tau for fast System-1 triage",
        initial_uncertainty_a_tau=3,
        solution_code_or_rule=src,
        verifier_passed=True,
        evidence_id="ev_0001",
        provenance=_verified_provenance("ast_verifier:kloster_margin"),
    )
    cases = [
        {"env": {"p_top": 0.85, "p_second": 0.15, "tau": 0.08}, "expected_approx": 0.70},
        {"env": {"p_top": 0.50, "p_second": 0.45, "tau": 0.08}, "expected_approx": 0.0},
        {"env": {"p_top": 0.05, "p_second": 0.01, "tau": 0.08}, "expected_approx": 0.0},
    ]

    with tempfile.TemporaryDirectory(prefix="zoe_distill_proc_") as tmp:
        distiller = System2To1Distiller(state_dir=tmp)
        artifact = distiller.distill(trace, verification_cases=cases)

        assert isinstance(artifact, DistilledArtifact)
        assert artifact.artifact_kind == "procedural_skill"
        assert artifact.target_name == "kloster_margin"
        assert artifact.rollback_token.startswith("rb_")
        assert artifact.regression_passed is True
        assert artifact.rolled_back is False
        _assert_constitutional_meta(artifact.constitutional)

        # InlineSkill descriptor
        assert artifact.inline_skill is not None
        assert isinstance(artifact.inline_skill, InlineSkill)
        assert artifact.inline_skill.name == "kloster-margin"
        assert "procedural_skill" in artifact.inline_skill.description
        assert "def kloster_margin" in artifact.inline_skill.instructions
        assert artifact.inline_skill.instructions == artifact.inline_skill.content

        # Fast System-1 replay via distiller and ZoeUnifiedMemory directly
        assert distiller.replay_skill("kloster_margin", {"p_top": 0.90, "p_second": 0.20, "tau": 0.08}) == pytest.approx(0.70)
        assert distiller.memory.run_skill("kloster_margin", {"p_top": 0.40, "p_second": 0.35, "tau": 0.08}) == pytest.approx(0.0)

        # Reload persisted memory from disk -> AST sandbox re-validates & replays identically
        reloaded = ZoeUnifiedMemory(tmp)
        assert reloaded.run_skill("kloster_margin", {"p_top": 0.85, "p_second": 0.15, "tau": 0.08}) == pytest.approx(0.70)
        assert reloaded.summary()["memory_sha256"] == artifact.memory_sha256


def test_hostile_ast_code_in_system2_trace_is_blocked() -> None:
    distiller = System2To1Distiller()
    before_sha = distiller.memory.summary()["memory_sha256"]
    bad_trace = System2Trace(
        task_prompt="Malicious escape probe",
        initial_uncertainty_a_tau=4,
        solution_code_or_rule="def exploit(x):\n    import os\n    return x\n",
        verifier_passed=True,
        evidence_id="ev_0099",
        provenance=_verified_provenance(),
    )
    with pytest.raises(UnsafeFunctionASTError):
        distiller.distill(bad_trace)
    assert distiller.memory.summary()["memory_sha256"] == before_sha
    assert distiller.memory.summary()["procedural_count"] == 0


def test_eliza_rule_distillation_gear1_lookup_reflection_and_cycling() -> None:
    distiller = System2To1Distiller()

    # Form 1: dict with regex pattern + multiple responses + pronoun reflection
    trace_dict = System2Trace(
        task_prompt="Handle questions about my telemetry drift quickly in Gear 1",
        initial_uncertainty_a_tau=2.5,
        solution_code_or_rule={
            "rule_id": "telemetry_drift_rule",
            "keywords": ["telemetry", "drift"],
            "rank": 12,
            "pattern": r".*\btelemetry drift\s+(.*)",
            "responses": [
                "Inspecting your telemetry drift {1} in System-1 Gear 1 (0 cloud tokens).",
                "Cross-checking {1} against hash-chained evidence without System-2 latency.",
            ],
            "push_memory": True,
        },
        verifier_passed=True,
        evidence_id="ev_eliza_1",
        provenance=_verified_provenance("eliza_rule_eval"),
    )
    art1 = distiller.distill(
        trace_dict,
        verification_cases=[
            {
                "input": "Check telemetry drift on my sensor",
                "expected_rule_id": "telemetry_drift_rule",
                "expected_contains": ["your sensor", "Gear 1"],
            }
        ],
    )
    assert art1.artifact_kind == "eliza_rule"
    assert art1.target_name == "telemetry_drift_rule"

    hit1 = distiller.lookup_rule("Check telemetry drift on my sensor")
    assert hit1 is not None
    assert hit1["gear"] == "gear1_distilled"
    assert hit1["cloud_tokens_used"] == 0
    assert "on your sensor" in hit1["reply"]
    assert "my->your" in hit1["reflections"]

    # Second call cycles to second reassembly template
    hit2 = distiller.lookup_rule("Check telemetry drift on my sensor")
    assert hit2 is not None
    assert "System-2 latency" in hit2["reply"]

    # Form 2: native ElizaRule object with @synonym class
    native_rule = ElizaRule(
        rule_id="research_bench_rule",
        keywords=("@research",),
        rank=8,
        decompositions=(
            (
                r".*\b(@research)\s+(.*)",
                ("Distilled Gear-1 bench protocol for {1}ing {2}.",),
            ),
        ),
    )
    trace_rule = System2Trace(
        task_prompt="Route @research benchmark queries in Gear 1",
        initial_uncertainty_a_tau=3.0,
        solution_code_or_rule=native_rule,
        verifier_passed=True,
        evidence_id="ev_eliza_2",
        provenance=_verified_provenance("eliza_synonym_eval"),
    )
    art2 = distiller.distill(
        trace_rule,
        verification_cases=[
            {
                "input": "Please verify invariance",
                "expected_rule_id": "research_bench_rule",
                "expected_contains": "verifying invariance",
            }
        ],
    )
    assert art2.target_name == "research_bench_rule"
    assert distiller.rule_registry.has_rule("research_bench_rule")


def test_semantic_fact_distillation_and_contradiction_superseding() -> None:
    distiller = System2To1Distiller()
    sha0 = distiller.memory.summary()["memory_sha256"]

    trace_v1 = System2Trace(
        task_prompt="Determine default Kloster tau for stem layering",
        initial_uncertainty_a_tau=2,
        solution_code_or_rule={
            "subject": "stem_layering",
            "relation": "default_tau",
            "object": 0.08,
            "confidence": 0.92,
        },
        verifier_passed=True,
        evidence_id="ev_fact_1",
        provenance=_verified_provenance("code_audit:stem_layering.py"),
    )
    art1 = distiller.distill(
        trace_v1,
        verification_cases=[
            {"subject": "stem_layering", "relation": "default_tau", "expected_object": 0.08}
        ],
    )
    assert art1.artifact_kind == "semantic_fact"
    assert art1.memory_sha256 != sha0
    facts_v1 = distiller.lookup_fact("stem_layering", relation="default_tau")
    assert len(facts_v1) == 1
    assert facts_v1[0]["object"] == 0.08

    # Verified belief update supersedes prior active fact while keeping history intact
    trace_v2 = System2Trace(
        task_prompt="Update default tau after quorum calibration",
        initial_uncertainty_a_tau=3,
        solution_code_or_rule=("stem_layering", "default_tau", 0.05),
        verifier_passed=True,
        evidence_id="ev_fact_2",
        provenance=_verified_provenance("quorum_calibration"),
    )
    art2 = distiller.distill(
        trace_v2,
        verification_cases=[{"expected_object": 0.05}],
    )
    assert art2.memory_sha256 != art1.memory_sha256
    active = distiller.lookup_fact("stem_layering", relation="default_tau", active_only=True)
    all_hist = distiller.lookup_fact("stem_layering", relation="default_tau", active_only=False)
    assert len(active) == 1 and active[0]["object"] == 0.05
    assert len(all_hist) == 2
    assert all_hist[0]["status"] == "superseded"


def test_constitution_art3_rejects_unverified_and_low_uncertainty_traces() -> None:
    distiller = System2To1Distiller()
    baseline_sha = distiller.memory.summary()["memory_sha256"]

    bad_traces = [
        # verifier_passed=False
        System2Trace(
            task_prompt="Unverified skill",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def bad_one(x):\n    return x\n",
            verifier_passed=False,
            evidence_id="ev_bad_1",
            provenance=_verified_provenance(),
        ),
        # Missing evidence_id
        System2Trace(
            task_prompt="No evidence id",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def bad_two(x):\n    return x\n",
            verifier_passed=True,
            evidence_id="   ",
            provenance=_verified_provenance(),
        ),
        # Placeholder evidence_id
        System2Trace(
            task_prompt="Unverified token",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def bad_three(x):\n    return x\n",
            verifier_passed=True,
            evidence_id="unverified",
            provenance=_verified_provenance(),
        ),
        # Invalid/empty provenance
        System2Trace(
            task_prompt="Missing provenance",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def bad_four(x):\n    return x\n",
            verifier_passed=True,
            evidence_id="ev_ok_1",
            provenance="unknown",
        ),
        # Sampled-only outcome without independent verification
        System2Trace(
            task_prompt="Sampled only",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def bad_five(x):\n    return x\n",
            verifier_passed=True,
            evidence_id="ev_ok_2",
            provenance=_verified_provenance(),
            sampled_only=True,
        ),
        # Low uncertainty (A_tau < 2.0 -> not high-uncertainty System-2)
        System2Trace(
            task_prompt="Already trivial System-1",
            initial_uncertainty_a_tau=1,
            solution_code_or_rule="def trivial(x):\n    return x\n",
            verifier_passed=True,
            evidence_id="ev_ok_3",
            provenance=_verified_provenance(),
        ),
    ]

    for bad in bad_traces:
        with pytest.raises((DistillationRejectedError, FirewallViolationError, ValueError)):
            distiller.distill(bad)

    assert distiller.memory.summary()["memory_sha256"] == baseline_sha
    assert distiller.memory.summary()["procedural_count"] == 0
    assert len(distiller.rejection_log()) == len(bad_traces)


def test_blackboard_evidence_gate_enforces_approved_evidence() -> None:
    bb = EpistemicBlackboard()
    m_fail = bb.post_measurement(
        source_agent="antigravity_system2",
        input_desc="candidate heuristic",
        method="deterministic_suite",
        scope="unit",
        limitations="none",
        value={"passed": False},
        sampled_only=False,
    )
    ev_fail = bb.promote_to_evidence(
        m_fail.record_id,
        verifier_name="zoe_verifier",
        passed=False,
        rationale="Deterministic suite failed 2/5 edge cases.",
        evidence_source=EvidenceSource("tool", "zoe_verifier", 0.95, 0.95),
    )

    m_pass = bb.post_measurement(
        source_agent="antigravity_system2",
        input_desc="candidate heuristic v2",
        method="deterministic_suite",
        scope="unit",
        limitations="none",
        value={"passed": True},
        sampled_only=False,
    )
    ev_pass = bb.promote_to_evidence(
        m_pass.record_id,
        verifier_name="zoe_verifier",
        passed=True,
        rationale="Exhaustive deterministic verification passed 5/5 cases.",
        evidence_source=EvidenceSource("tool", "zoe_verifier", 0.95, 0.95),
    )

    distiller = System2To1Distiller(blackboard=bb)
    # Failed blackboard evidence or unknown blackboard ID must be rejected
    for bad_ev_id in (ev_fail.record_id, "ev_nonexistent"):
        with pytest.raises(DistillationRejectedError):
            distiller.distill(
                System2Trace(
                    task_prompt="Gate check",
                    initial_uncertainty_a_tau=3,
                    solution_code_or_rule="def gated_fn(x):\n    return x + 1\n",
                    verifier_passed=True,
                    evidence_id=bad_ev_id,
                    provenance=_verified_provenance(),
                )
            )

    # Approved blackboard evidence succeeds
    art = distiller.distill(
        System2Trace(
            task_prompt="Gate check",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def gated_fn(x):\n    return x + 1\n",
            verifier_passed=True,
            evidence_id=ev_pass.record_id,
            provenance=_verified_provenance(),
        ),
        verification_cases=[{"env": {"x": 4}, "expected": 5}],
    )
    assert art.evidence_id == ev_pass.record_id
    assert distiller.replay_skill("gated_fn", {"x": 10}) == 11


def test_regression_failure_triggers_atomic_rollback_and_manual_rollback() -> None:
    distiller = System2To1Distiller()
    initial_sha = distiller.memory.summary()["memory_sha256"]

    # 1. Distill good v1 skill
    trace_v1 = System2Trace(
        task_prompt="Compute bounded score",
        initial_uncertainty_a_tau=3,
        solution_code_or_rule="def score_fn(x):\n    return clip(x, 0.0, 1.0)\n",
        verifier_passed=True,
        evidence_id="ev_v1",
        provenance=_verified_provenance(),
    )
    art_v1 = distiller.distill(
        trace_v1,
        verification_cases=[
            {"env": {"x": -0.5}, "expected_approx": 0.0},
            {"env": {"x": 0.4}, "expected_approx": 0.4},
            {"env": {"x": 2.0}, "expected_approx": 1.0},
        ],
    )
    sha_after_v1 = distiller.memory.summary()["memory_sha256"]
    assert sha_after_v1 != initial_sha

    # 2. Attempt regressive v2 overwrite -> fails v1 regression suite and auto-rolls back bit-exact
    trace_bad_v2 = System2Trace(
        task_prompt="Regressive update to score_fn",
        initial_uncertainty_a_tau=3,
        solution_code_or_rule="def score_fn(x):\n    return x * 2.0\n",
        verifier_passed=True,
        evidence_id="ev_bad_v2",
        provenance=_verified_provenance(),
    )
    with pytest.raises(DistillationRegressionError) as exc_info:
        distiller.distill(
            trace_bad_v2,
            verification_cases=[{"env": {"x": 0.5}, "expected_approx": 1.0}],
        )
    assert exc_info.value.rollback_performed is True
    assert distiller.memory.summary()["memory_sha256"] == sha_after_v1
    assert distiller.replay_skill("score_fn", {"x": 2.0}) == pytest.approx(1.0)

    # 3. Distill an Eliza rule, detect post-commit regression via verify_regression, and roll back via token
    rule_trace = System2Trace(
        task_prompt="Add temporary rule",
        initial_uncertainty_a_tau=2,
        solution_code_or_rule={
            "rule_id": "temp_rule",
            "keywords": ["tempcheck"],
            "rank": 5,
            "pattern": r".*tempcheck\s*(.*)",
            "response": "Handled {1}",
        },
        verifier_passed=True,
        evidence_id="ev_rule_temp",
        provenance=_verified_provenance(),
    )
    art_rule = distiller.distill(
        rule_trace,
        verification_cases=[{"input": "tempcheck alpha", "expected_contains": "Handled alpha"}],
    )
    assert distiller.rule_registry.has_rule("temp_rule")

    reg_check = distiller.verify_regression(
        regression_cases=[
            {
                "artifact_kind": "eliza_rule",
                "target_name": "temp_rule",
                "input": "tempcheck alpha",
                "expected_contains": "NONEXISTENT_PHRASE",
            }
        ],
        rollback_token_on_failure=art_rule.rollback_token,
    )
    assert reg_check["passed"] is False
    assert reg_check["rollback_performed"] is True
    assert not distiller.rule_registry.has_rule("temp_rule")
    assert distiller.memory.summary()["memory_sha256"] == sha_after_v1

    # Re-using an already-reverted token fails cleanly
    with pytest.raises(UnknownRollbackTokenError):
        distiller.rollback(art_rule.rollback_token)

    # 4. Manual rollback of v1 restores exact initial memory state
    rb1 = distiller.rollback(art_v1.rollback_token)
    assert rb1["rolled_back"] is True
    assert rb1["restored_memory_sha256"] == initial_sha
    assert distiller.memory.summary()["procedural_count"] == 0
    assert distiller.list_inline_skills() == ()


def test_solve_and_distill_offline_bridge_integration() -> None:
    bridge = ZoeAntigravityBridge()
    distiller = System2To1Distiller(bridge=bridge)

    def offline_solver(_prompt: str) -> str:
        return "def double_delta(a, b):\n    return 2.0 * abs(a - b)\n"

    def deterministic_verifier(solution: object) -> tuple[bool, str, Provenance]:
        assert isinstance(solution, str) and "def double_delta" in solution
        return True, "ev_bridge_001", _verified_provenance("zoe_bridge_verifier")

    art = distiller.solve_and_distill(
        "Compute doubled absolute difference",
        initial_uncertainty_a_tau=3,
        solver=offline_solver,
        verifier=deterministic_verifier,
        verification_cases=[{"env": {"a": 5.0, "b": 2.0}, "expected_approx": 6.0}],
    )
    assert art.target_name == "double_delta"
    assert distiller.replay_skill("double_delta", {"a": 1.5, "b": 4.0}) == pytest.approx(5.0)


def test_alpha_evolve_blackboard_distill_lineage_and_rollback() -> None:
    bb = EpistemicBlackboard()
    loop = AlphaEvolveLoop(blackboard=bb, seed=7, num_islands=2, offspring_per_gen=4)
    cases = [
        TestCase(inputs={"a": 5.0, "b": 2.0}, expected=6.0, name="pos"),
        TestCase(inputs={"a": 1.5, "b": 4.5}, expected=6.0, name="neg"),
        TestCase(inputs={"a": 3.0, "b": 3.0}, expected=0.0, name="zero"),
    ]
    # Seed already passes deterministic verifier and emits EvidenceRecord on EpistemicBlackboard
    ae_result = loop.evolve(
        "def evolved_gap(a, b):\n    return 2.0 * abs(a - b)\n",
        cases,
        generations=2,
        offspring_per_gen=4,
    )
    assert ae_result.best_program.passed_tests == len(cases)
    assert any(r.get("promoted_to_evidence") and r.get("passed") for r in ae_result.blackboard_records)

    pre_distill_bb_sha = bb.summary()["blackboard_sha256"]
    pre_distill_belief_count = bb.summary()["belief_updates_count"]

    mem = ZoeUnifiedMemory()
    pre_mem_sha = mem.summary()["memory_sha256"]
    distiller = System2To1Distiller(memory=mem, blackboard=bb)

    verify_cases = [
        {"env": {"a": 5.0, "b": 2.0}, "expected_approx": 6.0},
        {"env": {"a": 1.5, "b": 4.5}, "expected_approx": 6.0},
        {"env": {"a": 3.0, "b": 3.0}, "expected_approx": 0.0},
    ]
    artifact = distiller.distill_from_alpha_evolve(
        ae_result,
        initial_uncertainty_a_tau=3,
        verification_cases=verify_cases,
    )

    assert artifact.artifact_kind == "procedural_skill"
    assert artifact.target_name == "evolved_gap"
    assert artifact.lineage
    assert artifact.blackboard_belief_id is not None

    # Verify distilled-skill lineage was recorded onto EpistemicBlackboard via Art. III BeliefUpdateRecord
    belief = bb.get_belief(artifact.blackboard_belief_id)
    assert artifact.evidence_id in belief.evidence_ids
    assert belief.subject == "distilled:procedural_skill:evolved_gap"
    assert belief.relation == "distilled_lineage"
    assert bb.summary()["belief_updates_count"] == pre_distill_belief_count + 1

    # Verify fast procedural execution directly through ZoeUnifiedMemory
    assert mem.run_skill("evolved_gap", {"a": 10.0, "b": 4.0}) == pytest.approx(12.0)
    assert distiller.replay_skill("evolved_gap", {"a": -2.0, "b": 1.0}) == pytest.approx(6.0)

    # Rollback restores BOTH ZoeUnifiedMemory and EpistemicBlackboard bit-exact
    rb = distiller.rollback(artifact.rollback_token)
    assert rb["rolled_back"] is True
    assert rb["restored_memory_sha256"] == pre_mem_sha
    assert mem.summary()["procedural_count"] == 0
    assert bb.summary()["blackboard_sha256"] == pre_distill_bb_sha
    assert bb.summary()["belief_updates_count"] == pre_distill_belief_count


def test_alpha_evolve_unverified_or_partial_program_rejected_by_art3() -> None:
    bb = EpistemicBlackboard()
    loop = AlphaEvolveLoop(blackboard=bb, seed=11, num_islands=2, offspring_per_gen=2)
    # Seed does NOT pass all test cases -> AlphaEvolveLoop does NOT promote winner_evidence
    partial_cases = [
        TestCase(inputs={"x": 0.0}, expected=0.0, name="zero_only"),
        TestCase(inputs={"x": 5.0}, expected=999.0, name="unmatched"),
    ]
    ae_partial = loop.evolve(
        "def partial_fn(x):\n    return x\n",
        partial_cases,
        generations=1,
        offspring_per_gen=2,
    )
    assert ae_partial.best_program.passed_tests < ae_partial.best_program.total_tests

    distiller = System2To1Distiller(blackboard=bb)
    with pytest.raises(DistillationRejectedError):
        distiller.distill_from_alpha_evolve(ae_partial)
    assert distiller.memory.summary()["procedural_count"] == 0
    assert bb.summary()["belief_updates_count"] == 0

    # Also verify passing an EvidenceRecord object directly works when approved, and rejects when failed
    meas = bb.post_measurement(
        source_agent="alpha_evolve",
        input_desc="candidate check",
        method="deterministic_eval",
        scope="unit",
        limitations="finite cases",
        value=1.0,
        sampled_only=False,
    )
    ev_obj = bb.promote_to_evidence(
        meas.record_id,
        verifier_name="ZoeDeterministicVerifier",
        passed=True,
        rationale="Deterministic suite passed all test cases.",
        evidence_source=EvidenceSource("tool", "ZoeDeterministicVerifier", 0.95, 0.95),
    )
    art = distiller.distill(
        System2Trace(
            task_prompt="Accept EvidenceRecord object",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def ev_obj_skill(x):\n    return x * 3.0\n",
            verifier_passed=True,
            evidence_id=ev_obj,
            provenance=_verified_provenance(),
        ),
        verification_cases=[{"env": {"x": 2.0}, "expected_approx": 6.0}],
    )
    assert art.evidence_id == ev_obj.record_id
    assert art.blackboard_belief_id is not None
    assert distiller.replay_skill("ev_obj_skill", {"x": 4.0}) == pytest.approx(12.0)


def test_distill_atomic_rollback_on_blackboard_stop_and_inline_skill_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bb = EpistemicBlackboard()
    m1 = bb.post_measurement("p", "in", "det", "s", "l", 4)
    ev1 = bb.promote_to_evidence(
        m1.record_id,
        "det",
        True,
        "deterministic check passed",
        evidence_source=EvidenceSource(kind="tool", identifier="det", trust=0.95, strength=0.95),
    )
    d = System2To1Distiller(blackboard=bb, min_uncertainty_a_tau=2.0)

    # Distill a valid baseline skill first so we verify pre-existing state is preserved intact
    d.distill(
        System2Trace(
            "baseline",
            3.0,
            "def sq(x):\n    return x * x",
            True,
            ev1.record_id,
            _verified_provenance(),
        ),
        verification_cases=[{"inputs": {"x": 3.0}, "expected": 9.0}],
    )

    pre_mem = d.memory.snapshot()
    pre_reg = d.rule_registry.snapshot()
    pre_active = dict(d._active_artifacts)
    pre_inline = dict(d._inline_skills)
    pre_fact_meta = deepcopy(d._fact_meta)

    # 1. Stop blackboard mid-session -> update_belief fails -> full atomic rollback across all 3 kinds
    bb.emergency_stop("halt")
    bad_traces = [
        (
            System2Trace(
                "proc",
                3.0,
                "def cube(x):\n    return x * x * x",
                True,
                ev1.record_id,
                _verified_provenance(),
            ),
            [{"inputs": {"x": 2.0}, "expected": 8.0}],
        ),
        (
            System2Trace(
                "rule",
                3.0,
                {
                    "rule_id": "stopped_rule",
                    "keywords": ["stopped"],
                    "pattern": r".*\bstopped\s+(.*)",
                    "response": "Should roll back {1}",
                },
                True,
                ev1.record_id,
                _verified_provenance(),
            ),
            [{"input": "stopped check", "expected_contains": "Should roll back"}],
        ),
        (
            System2Trace(
                "fact",
                3.0,
                {"subject": "stopped_subj", "relation": "status", "object": "active"},
                True,
                ev1.record_id,
                _verified_provenance(),
            ),
            [{"expected_object": "active"}],
        ),
    ]
    for trace, cases in bad_traces:
        with pytest.raises(RuntimeError, match="stopped"):
            d.distill(trace, verification_cases=cases)
        assert d.memory.snapshot() == pre_mem
        assert d.rule_registry.snapshot() == pre_reg
        assert d._active_artifacts == pre_active
        assert d._inline_skills == pre_inline
        assert d._fact_meta == pre_fact_meta

    # 2. Failure during inline skill export after blackboard.update_belief -> rolls back everything including blackboard
    bb_live = EpistemicBlackboard()
    m2 = bb_live.post_measurement("p", "in", "det", "s", "l", 8)
    ev2 = bb_live.promote_to_evidence(
        m2.record_id,
        "det",
        True,
        "deterministic check passed",
        evidence_source=EvidenceSource(kind="tool", identifier="det", trust=0.95, strength=0.95),
    )
    d2 = System2To1Distiller(blackboard=bb_live, min_uncertainty_a_tau=2.0)
    bb_pre = bb_live.snapshot()
    mem2_pre = d2.memory.snapshot()
    reg2_pre = d2.rule_registry.snapshot()
    active2_pre = dict(d2._active_artifacts)
    inline2_pre = dict(d2._inline_skills)
    fact2_pre = deepcopy(d2._fact_meta)

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("simulated inline skill export failure")

    monkeypatch.setattr(d2, "_build_inline_skill", _boom)
    with pytest.raises(RuntimeError, match="simulated inline skill export failure"):
        d2.distill(
            System2Trace(
                "inline_boom",
                3.0,
                "def cube(x):\n    return x * x * x",
                True,
                ev2.record_id,
                _verified_provenance(),
            ),
            verification_cases=[{"inputs": {"x": 2.0}, "expected": 8.0}],
            export_inline_skill=True,
        )

    assert d2.memory.snapshot() == mem2_pre
    assert d2.rule_registry.snapshot() == reg2_pre
    assert d2._active_artifacts == active2_pre
    assert d2._inline_skills == inline2_pre
    assert d2._fact_meta == fact2_pre
    assert bb_live.snapshot() == bb_pre

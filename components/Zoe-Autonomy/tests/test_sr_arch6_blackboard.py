"""Unit tests for Architecture 6: Shared Epistemic Blackboard (blackboard.py)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.l5_memory import ZoeUnifiedMemory  # noqa: E402
from zoe_autonomy.metacognition import EvidenceSource, Provenance  # noqa: E402
from zoe_autonomy.shared_reasoning.blackboard import (  # noqa: E402
    BLACKBOARD_CONTRACT,
    HASH_CHAIN_SEMANTICS,
    ActionProposalRecord,
    BeliefUpdateRecord,
    EpistemicBlackboard,
    EvidenceRecord,
    FirewallViolationError,
    MeasurementRecord,
    TamperDetectedError,
    coerce_evidence_source,
)


def _assert_constitutional_meta(meta: dict[str, object]) -> None:
    assert meta["external_actions"] == 0
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def test_lazy_exports_and_constitutional_metadata() -> None:
    assert sr.EpistemicBlackboard is EpistemicBlackboard
    assert sr.MeasurementRecord is MeasurementRecord
    assert sr.EvidenceRecord is EvidenceRecord
    assert sr.BeliefUpdateRecord is BeliefUpdateRecord
    assert sr.ActionProposalRecord is ActionProposalRecord
    assert sr.FirewallViolationError is FirewallViolationError

    bb = EpistemicBlackboard()
    summary = bb.summary()
    assert summary["contract"] == BLACKBOARD_CONTRACT
    assert summary["hash_chain_semantics"] == HASH_CHAIN_SEMANTICS
    assert summary["tamper_evidence_only"] is True
    assert summary["authentication_proof"] is False
    _assert_constitutional_meta(summary["constitutional"])


def test_valid_four_lane_progression_and_provenance_trace() -> None:
    prov = Provenance(
        sources=(EvidenceSource("tool", "sympy_checker", 0.95, 0.9),),
        transformations=("symbolic_simplify",),
    )
    bb = EpistemicBlackboard()

    meas = bb.post_measurement(
        source_agent="antigravity_prover",
        input_desc="expression x**2 - 1 == (x - 1)*(x + 1)",
        method="sympy.simplify",
        scope="all real and complex numbers",
        limitations="symbolic ring assumptions only",
        value={"equivalent": True, "residual": 0},
        sampled_only=False,
        provenance=prov,
    )
    assert isinstance(meas, MeasurementRecord)
    assert meas.lane == "measurement"
    assert meas.prev_hash == "GENESIS"
    assert meas.entry_sha256

    ev = bb.promote_to_evidence(
        meas.record_id,
        verifier_name="zoe_symbolic_auditor",
        passed=True,
        rationale="Residual reduced identically to zero over symbolic ring.",
        evidence_source=EvidenceSource("tool", "zoe_symbolic_auditor", 0.95, 0.95),
    )
    assert isinstance(ev, EvidenceRecord)
    assert ev.lane == "evidence"
    assert ev.passed is True
    assert ev.approved is True
    assert ev.negative_result is False
    assert ev.prev_hash == meas.entry_sha256

    bel = bb.update_belief(
        [ev.record_id],
        claim="x**2 - 1 identically equals (x - 1)*(x + 1)",
        posterior_delta=0.45,
        subject="algebra_identity_1",
        relation="verified_equivalence",
    )
    assert isinstance(bel, BeliefUpdateRecord)
    assert bel.lane == "belief_update"
    assert bel.evidence_ids == (ev.record_id,)
    assert bel.posterior_delta == pytest.approx(0.45)
    assert bel.prev_hash == ev.entry_sha256

    act = bb.propose_action(
        bel.record_id,
        action_kind="emit_verified_lemma",
        target="docs/lemmas.md",
        reversible=True,
        rationale="Record verified algebraic identity for human review.",
    )
    assert isinstance(act, ActionProposalRecord)
    assert act.lane == "action_proposal"
    assert act.status == "REVIEW_REQUIRED"
    assert act.external_actions == 0
    assert act.requires_human_review is True
    assert act.autonomous_execution_allowed is False
    assert act.reversible is True
    assert act.target == "docs/lemmas.md"
    assert act.prev_hash == bel.entry_sha256

    # Also support PROJECT.md 3-arg calling form (belief_id, action_kind, reversible)
    act2 = bb.propose_action(bel.record_id, "archive_lemma", False)
    assert act2.target == "unspecified"
    assert act2.reversible is False
    assert act2.status == "REVIEW_REQUIRED"
    assert act2.external_actions == 0

    trace = bb.provenance_trace(act.record_id)
    assert trace["action_proposal"]["record_id"] == act.record_id
    assert trace["belief_update"]["record_id"] == bel.record_id
    assert trace["evidence"][0]["record_id"] == ev.record_id
    assert trace["measurements"][0]["record_id"] == meas.record_id

    integrity = bb.verify_integrity()
    assert integrity["valid"] is True
    assert integrity["entries_verified"] == 5
    assert integrity["tamper_evidence_only"] is True
    assert integrity["authentication_proof"] is False


def test_measurement_requires_input_method_scope_limitations() -> None:
    bb = EpistemicBlackboard()
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "", "method", "scope", "limitations", 1)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "   ", "scope", "limitations", 1)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "", "limitations", 1)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "scope", "", 1)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "scope", "limitations", float("nan"))


def test_firewall_blocks_illegal_lane_jumps() -> None:
    bb = EpistemicBlackboard()
    meas = bb.post_measurement(
        source_agent="zoe_probe",
        input_desc="candidate sorting snippet",
        method="ast_parse",
        scope="single function",
        limitations="static syntax only, no runtime proof",
        value={"ast_ok": True},
    )

    # Raw measurement -> belief update is forbidden
    with pytest.raises(FirewallViolationError):
        bb.update_belief([meas.record_id], "snippet is functionally correct", 0.3)

    # Raw measurement -> action proposal is forbidden
    with pytest.raises(FirewallViolationError):
        bb.propose_action(meas.record_id, "apply_patch", "src/sort.py")

    # Empty or string evidence_ids are forbidden
    with pytest.raises(FirewallViolationError):
        bb.update_belief([], "empty evidence", 0.1)
    with pytest.raises(FirewallViolationError):
        bb.update_belief(meas.record_id, "string instead of sequence", 0.1)  # type: ignore[arg-type]

    # Missing IDs are forbidden
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence("meas_9999", "verifier", True, "does not exist")
    with pytest.raises(FirewallViolationError):
        bb.update_belief(["ev_9999"], "missing evidence", 0.1)
    with pytest.raises(FirewallViolationError):
        bb.propose_action("bel_9999", "edit", "file.py")

    # Evidence -> action proposal (skipping belief update) is forbidden
    ev = bb.promote_to_evidence(
        meas.record_id,
        verifier_name="ast_verifier",
        passed=True,
        rationale="Parsed cleanly with zero disallowed AST nodes.",
    )
    with pytest.raises(FirewallViolationError):
        bb.propose_action(ev.record_id, "apply_patch", "src/sort.py")

    # Promoting non-measurement record to evidence is forbidden
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(ev.record_id, "verifier", True, "double promote")


def test_negative_results_and_sampled_only_outcomes_enforced() -> None:
    bb = EpistemicBlackboard()

    # 1. Non-sampled failed measurement -> negative EvidenceRecord -> cannot update belief
    m_fail = bb.post_measurement(
        source_agent="pytest_runner",
        input_desc="unit test suite",
        method="pytest",
        scope="module X",
        limitations="local environment",
        value={"failed": 2},
    )
    ev_fail = bb.promote_to_evidence(
        m_fail.record_id,
        verifier_name="ci_gate",
        passed=False,
        rationale="Two assertion failures observed; preserving negative result.",
    )
    assert ev_fail.passed is False
    assert ev_fail.approved is False
    assert ev_fail.negative_result is True
    assert bb.negative_results() == (ev_fail,)

    with pytest.raises(FirewallViolationError):
        bb.update_belief([ev_fail.record_id], "module X is ready", 0.2)

    # 2. Sampled-only outcome (Art. III.3)
    m_sampled = bb.post_measurement(
        source_agent="monte_carlo_agent",
        input_desc="random 10-point property probe",
        method="random_sampling",
        scope="10 of 2^64 states",
        limitations="sampled only; non-exhaustive",
        value={"passed_samples": 10},
        sampled_only=True,
    )

    # Cannot jump directly from sampled measurement to belief
    with pytest.raises(FirewallViolationError):
        bb.update_belief([m_sampled.record_id], "property holds globally", 0.4)

    # Cannot promote sampled outcome merely by expectation match
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            m_sampled.record_id,
            verifier_name="self_check",
            passed=True,
            rationale="Matches expectation across the 10 sampled inputs.",
        )

    # Cannot promote sampled outcome with a weak/prior EvidenceSource
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            m_sampled.record_id,
            verifier_name="prior_guess",
            passed=True,
            rationale="Looks consistent with prior heuristic.",
            evidence_source=EvidenceSource("prior", "heuristic_guess", 0.5, 0.5),
        )

    # Recording a negative evidence result for sampled-only works and blocks belief update
    ev_sampled_neg = bb.promote_to_evidence(
        m_sampled.record_id,
        verifier_name="epistemic_gate",
        passed=False,
        rationale="Sampled outcome does not establish universal proof.",
    )
    assert ev_sampled_neg.sampled_source is True
    assert ev_sampled_neg.negative_result is True
    with pytest.raises(FirewallViolationError):
        bb.update_belief([ev_sampled_neg.record_id], "property holds globally", 0.4)

    # Only an independent strong verifier + formal rationale can promote to passed evidence
    ev_sampled_proven = bb.promote_to_evidence(
        m_sampled.record_id,
        verifier_name="z3_formal_checker",
        passed=True,
        rationale="Exhaustive Z3 formal proof verified property over full 64-bit domain.",
        evidence_source=EvidenceSource("tool", "z3_smt_solver", 0.98, 0.98),
    )
    bel = bb.update_belief(
        [ev_sampled_proven.record_id],
        claim="property holds globally (Z3-verified)",
        posterior_delta=0.5,
    )
    assert bel.evidence_ids == (ev_sampled_proven.record_id,)


def test_tamper_detection_disk_memory_and_snapshot(tmp_path: Path) -> None:
    bb_dir = tmp_path / "bb_store"
    bb = EpistemicBlackboard(bb_dir)
    m = bb.post_measurement("a", "i", "m", "s", "l", 42)
    e = bb.promote_to_evidence(m.record_id, "v", True, "verified exact match")
    bb.update_belief([e.record_id], "value is 42", 0.3)

    # Reload from disk cleanly
    reloaded = EpistemicBlackboard(bb_dir)
    assert reloaded.verify_integrity()["entries_verified"] == 3
    assert reloaded.get_measurement(m.record_id).value == 42

    # Tamper persisted JSON on disk -> load() detects tamper
    disk_path = bb_dir / "zoe_epistemic_blackboard.json"
    doc = json.loads(disk_path.read_text(encoding="utf-8"))
    doc["measurements"][0]["value"] = 999
    disk_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(TamperDetectedError):
        EpistemicBlackboard(bb_dir)

    # In-memory _doc tamper detection
    bb_mem = EpistemicBlackboard()
    m2 = bb_mem.post_measurement("a", "i", "m", "s", "l", 7)
    snap = bb_mem.snapshot()
    bb_mem._doc["measurements"][0]["value"] = 8
    res = bb_mem.verify_integrity(raise_on_error=False)
    assert res["valid"] is False
    assert res["tamper_detected"] is True
    assert res["tamper_evidence_only"] is True
    assert res["authentication_proof"] is False
    with pytest.raises(TamperDetectedError):
        bb_mem.promote_to_evidence(m2.record_id, "v", True, "blocked by tamper")

    # Tampered snapshot rejected by rollback
    bad_snap = dict(snap)
    bad_snap["chain_head"] = "0" * 64
    bb_clean = EpistemicBlackboard()
    with pytest.raises(TamperDetectedError):
        bb_clean.rollback(bad_snap)


def test_snapshot_rollback_and_emergency_stop(tmp_path: Path) -> None:
    bb = EpistemicBlackboard(tmp_path / "bb_state")
    m1 = bb.post_measurement("a", "in1", "m1", "s1", "l1", 10)
    snap1 = bb.snapshot()

    e1 = bb.promote_to_evidence(m1.record_id, "v", True, "verified")
    assert len(bb.list_evidence()) == 1

    bb.rollback(snap1)
    assert len(bb.list_measurements()) == 1
    assert len(bb.list_evidence()) == 0
    assert bb.verify_integrity()["valid"] is True

    # Emergency stop blocks writes while preserving read inspection
    summary = bb.emergency_stop("operator halt")
    assert summary["stopped"] is True
    assert bb.stopped is True
    assert bb.verify_integrity()["valid"] is True

    with pytest.raises(RuntimeError, match="stopped"):
        bb.post_measurement("a", "in2", "m2", "s2", "l2", 20)
    with pytest.raises(RuntimeError, match="stopped"):
        bb.promote_to_evidence(m1.record_id, "v", True, "after stop")
    with pytest.raises(RuntimeError, match="stopped"):
        bb.rollback(snap1)


def test_zoe_unified_memory_integration(tmp_path: Path) -> None:
    mem = ZoeUnifiedMemory(tmp_path / "l5_mem")
    bb = EpistemicBlackboard(tmp_path / "bb_mem", memory=mem)

    m1 = bb.post_measurement("sensor", "temp_reading_1", "thermistor", "room", "uncalibrated", 21.5)
    e1 = bb.promote_to_evidence(m1.record_id, "cal_check", True, "Within +/-0.1C calibration bounds.")
    b1 = bb.update_belief(
        [e1.record_id],
        claim="room_temp_21.5C",
        posterior_delta=0.35,
        subject="lab_room",
        relation="temperature",
    )
    assert b1.memory_sync is not None
    assert b1.memory_sync["belief_updated"] is True
    active = mem.query_facts(subject="lab_room", relation="temperature", active_only=True)
    assert len(active) == 1
    assert active[0]["object"] == "room_temp_21.5C"

    # Failed evidence must NOT reach ZoeUnifiedMemory
    m_bad = bb.post_measurement("sensor", "temp_reading_2", "thermistor", "room", "faulty", 999.0)
    e_bad = bb.promote_to_evidence(m_bad.record_id, "cal_check", False, "Out of physical bounds.")
    with pytest.raises(FirewallViolationError):
        bb.update_belief(
            [e_bad.record_id],
            claim="room_temp_999C",
            posterior_delta=0.4,
            subject="lab_room",
            relation="temperature",
        )
    active_after_fail = mem.query_facts(subject="lab_room", relation="temperature", active_only=True)
    assert len(active_after_fail) == 1
    assert active_after_fail[0]["object"] == "room_temp_21.5C"

    # Verified superseding update revises ZoeUnifiedMemory and preserves prior
    m2 = bb.post_measurement("sensor", "temp_reading_3", "thermistor", "room", "calibrated", 22.0)
    e2 = bb.promote_to_evidence(m2.record_id, "cal_check", True, "Verified calibrated reading.")
    b2 = bb.update_belief(
        [e2.record_id],
        claim="room_temp_22.0C",
        posterior_delta=0.4,
        subject="lab_room",
        relation="temperature",
    )
    assert b1.record_id in b2.superseded_belief_ids
    assert b2.memory_sync is not None
    assert b2.memory_sync["conflict_detected"] is True
    assert b2.memory_sync["belief_updated"] is True
    all_facts = mem.query_facts(subject="lab_room", relation="temperature", active_only=False)
    assert len(all_facts) == 2
    assert [f["status"] for f in all_facts] == ["superseded", "active"]


def test_round2_ergonomic_helpers_hash_chain_and_emergency_stop_all_lanes(tmp_path: Path) -> None:
    bb = EpistemicBlackboard(tmp_path / "round2_bb")

    # Empty/missing scope or limitations (including list forms) rejected per Art. III.1
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "   ", "limits", 1.0)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "scope", [], 1.0)
    with pytest.raises(FirewallViolationError):
        bb.post_measurement("agent", "input", "method", "scope", ["", "  "], 1.0)

    # Peer-style call with source=, limitations=[...], metadata={...}
    m = bb.post_measurement(
        source="sandbox_lab",
        input_desc="x**2 - 1 == (x - 1)*(x + 1)",
        method="sympy_check",
        scope="polynomial ring",
        limitations=["symbolic check only", "finite timeout"],
        value={"passed": True},
        metadata={"lab_name": "sympy"},
    )
    assert m.id == m.record_id
    assert m.measurement_id == m.record_id
    assert m.limitations == "symbolic check only; finite timeout"
    assert m.provenance["metadata"] == {"lab_name": "sympy"}

    # PeerConfidenceVector / to_evidence_source() interoperability
    from zoe_autonomy.shared_reasoning.quorum import PeerConfidenceVector

    peer = PeerConfidenceVector(
        peer_id="clara",
        probabilities=(0.9, 0.1),
        source_kind="tool",
        provenance_id="clara_audit_01",
        independence_tag="indep_clara",
    )
    coerced = coerce_evidence_source(peer)
    assert isinstance(coerced, EvidenceSource)
    assert coerced.strong is True

    ev = bb.promote_to_evidence(
        m.measurement_id,
        verifier_name="quorum_auditor",
        passed=True,
        rationale="Independent Clara tool audit confirmed symbolic check.",
        evidence_source=peer,
    )
    assert ev.id == ev.record_id
    assert ev.evidence_id == ev.record_id
    assert bb.approved_evidence() == (ev,)

    bel = bb.update_belief([ev.evidence_id], "polynomial identity holds", 0.4)
    assert bel.id == bel.record_id
    assert bel.belief_id == bel.record_id
    assert bb.latest_beliefs() == (bel,)

    act = bb.propose_action(bel.belief_id, "record_theorem", "docs/theorems.md")
    assert act.id == act.record_id
    assert act.action_id == act.record_id
    assert act.status == "REVIEW_REQUIRED"
    assert act.external_actions == 0

    # export_lane_summary & verify_hash_chain
    lane_summary = bb.export_lane_summary(include_records=True)
    assert lane_summary["integrity"]["valid"] is True
    assert lane_summary["lanes"]["measurement"]["count"] == 1
    assert lane_summary["lanes"]["evidence"]["passed_count"] == 1
    assert lane_summary["lanes"]["belief_update"]["active_count"] == 1
    assert lane_summary["lanes"]["action_proposal"]["external_actions"] == 0
    assert len(lane_summary["lanes"]["action_proposal"]["records"]) == 1

    chain_ok = bb.verify_hash_chain()
    assert chain_ok["valid"] is True
    assert chain_ok["entries_verified"] == 4

    # Emergency stop blocks subsequent belief updates & action proposals too
    bb.emergency_stop("halt round 2")
    with pytest.raises(RuntimeError, match="stopped"):
        bb.update_belief([ev.evidence_id], "blocked belief update", 0.1)
    with pytest.raises(RuntimeError, match="stopped"):
        bb.propose_action(bel.belief_id, "blocked_action", "target")

    # Tampered hash chain detected via verify_hash_chain()
    bb._doc["ledger"][0]["entry_sha256"] = "f" * 64
    chain_bad = bb.verify_hash_chain()
    assert chain_bad["valid"] is False
    assert chain_bad["tamper_detected"] is True
    with pytest.raises(TamperDetectedError):
        bb.verify_hash_chain(raise_on_error=True)


def test_sampled_only_requires_explicit_strong_evidence_source_no_informal_bypass() -> None:
    bb = EpistemicBlackboard()
    ms = bb.post_measurement(
        source_agent="p",
        input_desc="in",
        method="mc",
        scope="s",
        limitations="l",
        value=1,
        sampled_only=True,
    )

    # Informal phrasing outside _EXPECTATION_ONLY_PATTERNS with evidence_source=None must fail
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            ms.record_id,
            "v",
            True,
            "looks reasonable enough to accept",
        )

    # Even formal-sounding rationale with evidence_source=None must fail when sampled_only=True
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            ms.record_id,
            "v",
            True,
            "Exhaustive formal theorem proof checked independently.",
            evidence_source=None,
        )

    # Spoofed strong_evidence=True in a weak-kind dict must fail
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            ms.record_id,
            "v",
            True,
            "Exhaustive formal theorem proof checked independently.",
            evidence_source={
                "kind": "prior",
                "identifier": "spoof",
                "trust": 0.2,
                "strength": 0.2,
                "strong_evidence": True,
            },
        )

    # Expectation-only / informal rationale paired with strong EvidenceSource must still fail
    with pytest.raises(FirewallViolationError):
        bb.promote_to_evidence(
            ms.record_id,
            "v",
            True,
            "looks reasonable enough to accept",
            evidence_source=EvidenceSource(kind="tool", identifier="z3", trust=0.95, strength=0.95),
        )

    # Only explicit strong EvidenceSource + non-expectation verifier rationale succeeds
    ev = bb.promote_to_evidence(
        ms.record_id,
        "z3_verifier",
        True,
        "Exhaustive Z3 formal proof verified property over bounded state space.",
        evidence_source=EvidenceSource(kind="tool", identifier="z3", trust=0.95, strength=0.95),
    )
    assert ev.passed is True
    assert ev.approved is True
    assert ev.sampled_source is True
    bel = bb.update_belief([ev.record_id], "verified via strong source", 0.4)
    assert bel.evidence_ids == (ev.record_id,)


def test_regression_load_enforces_all_action_proposal_invariants(tmp_path: Path) -> None:
    import json
    from zoe_autonomy._utils import sha256_json_utf8
    from zoe_autonomy.shared_reasoning.blackboard import _compute_entry_sha256

    bb_path = tmp_path / "action_invariant_bb.json"
    bb = EpistemicBlackboard(bb_path)
    m1 = bb.post_measurement("zoe", "in", "sympy", "ring", "exact", 42)
    e1 = bb.promote_to_evidence(m1.record_id, "sympy", True, "Deterministic symbolic proof passed.")
    b1 = bb.update_belief([e1.record_id], "identity holds", 0.3)
    a1 = bb.propose_action(b1.record_id, "emit_report", "docs/out.md", reversible=True)
    assert a1.external_actions == 0
    assert a1.requires_human_review is True
    assert a1.autonomous_execution_allowed is False

    # Valid persisted blackboard loads cleanly.
    bb_clean = EpistemicBlackboard(bb_path)
    assert bb_clean.get_action_proposal(a1.record_id).external_actions == 0

    base_doc = json.loads(bb_path.read_text(encoding="utf-8"))

    def _write_rehashed_action(overrides: dict[str, Any]) -> None:
        doc = json.loads(json.dumps(base_doc))
        act = doc["action_proposals"][0]
        act.update(overrides)
        payload = {k: v for k, v in act.items() if k != "entry_sha256"}
        new_entry_hash = _compute_entry_sha256(
            seq=int(act["seq"]),
            lane="action_proposal",
            prev_hash=str(act["prev_hash"]),
            payload=payload,
        )
        act["entry_sha256"] = new_entry_hash
        doc["ledger"][-1]["entry_sha256"] = new_entry_hash
        doc["chain_head"] = new_entry_hash
        doc["blackboard_sha256"] = sha256_json_utf8(
            {k: v for k, v in doc.items() if k != "blackboard_sha256"}
        )
        bb_path.write_text(json.dumps(doc), encoding="utf-8")

    for bad_override in (
        {"external_actions": 1},
        {"external_actions": True},
        {"autonomous_execution_allowed": True},
        {"requires_human_review": False},
        {"status": "APPROVED"},
    ):
        _write_rehashed_action(bad_override)
        with pytest.raises(FirewallViolationError):
            EpistemicBlackboard(bb_path)


def test_regression_load_enforces_cross_lane_provenance_and_constitutional_invariants(
    tmp_path: Path,
) -> None:
    from zoe_autonomy._utils import sha256_json_utf8
    from zoe_autonomy.shared_reasoning.blackboard import _compute_entry_sha256

    bb_path = tmp_path / "cross_lane_bb.json"
    bb = EpistemicBlackboard(bb_path)

    m1 = bb.post_measurement("zoe", "expr x+1", "sympy", "ring", "exact", {"ok": True})
    e1 = bb.promote_to_evidence(m1.record_id, "sympy_verifier", True, "Deterministic symbolic proof passed.")
    b1 = bb.update_belief([e1.record_id], "expr is valid", 0.35)
    a1 = bb.propose_action(b1.record_id, "emit_note", "docs/note.md", reversible=True)

    # Also include a valid sampled_only -> strong evidence -> belief chain and a negative evidence record.
    m_sampled = bb.post_measurement(
        "mc", "random probe", "sampling", "10 samples", "sampled only", {"n": 10}, sampled_only=True
    )
    e_sampled = bb.promote_to_evidence(
        m_sampled.record_id,
        "z3_checker",
        True,
        "Exhaustive Z3 formal proof verified property over bounded domain.",
        evidence_source=EvidenceSource("tool", "z3_solver", 0.95, 0.95),
    )
    bb.update_belief([e_sampled.record_id], "sampled property proven by z3", 0.4)

    m_fail = bb.post_measurement("pytest", "suite", "pytest", "unit", "local", {"failed": 1})
    e_fail = bb.promote_to_evidence(
        m_fail.record_id, "ci_gate", False, "One test assertion failed; negative result."
    )

    # Positive control: valid multi-lane persisted blackboard loads cleanly.
    reloaded = EpistemicBlackboard(bb_path)
    assert reloaded.verify_integrity()["valid"] is True
    assert reloaded.provenance_trace(a1.record_id)["measurements"][0]["record_id"] == m1.record_id

    base_doc = json.loads(bb_path.read_text(encoding="utf-8"))

    def _rehash_and_write(doc: dict[str, Any]) -> None:
        by_seq: dict[int, dict[str, Any]] = {}
        for lane_key in ("measurements", "evidence", "belief_updates", "action_proposals"):
            for row in doc[lane_key]:
                by_seq[int(row["seq"])] = row
        prev_hash = "GENESIS"
        new_ledger: list[dict[str, Any]] = []
        for seq in sorted(by_seq):
            row = by_seq[seq]
            row["prev_hash"] = prev_hash
            payload = {k: v for k, v in row.items() if k != "entry_sha256"}
            entry_hash = _compute_entry_sha256(
                seq=seq,
                lane=str(row["lane"]),
                prev_hash=prev_hash,
                payload=payload,
            )
            row["entry_sha256"] = entry_hash
            new_ledger.append(
                {
                    "seq": seq,
                    "lane": row["lane"],
                    "record_id": row["record_id"],
                    "prev_hash": prev_hash,
                    "entry_sha256": entry_hash,
                }
            )
            prev_hash = entry_hash
        doc["ledger"] = new_ledger
        doc["chain_head"] = prev_hash
        doc["blackboard_sha256"] = sha256_json_utf8(
            {k: v for k, v in doc.items() if k != "blackboard_sha256"}
        )
        bb_path.write_text(json.dumps(doc), encoding="utf-8")

    # 1. Belief with empty evidence_ids
    doc1 = json.loads(json.dumps(base_doc))
    doc1["belief_updates"][0]["evidence_ids"] = []
    _rehash_and_write(doc1)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 2. Direct measurement -> belief jump (bypassing evidence lane)
    doc2 = json.loads(json.dumps(base_doc))
    doc2["belief_updates"][0]["evidence_ids"] = [m1.record_id]
    _rehash_and_write(doc2)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 3. Belief referencing failed/unapproved evidence (passed=False)
    doc3 = json.loads(json.dumps(base_doc))
    doc3["belief_updates"][0]["evidence_ids"] = [e_fail.record_id]
    _rehash_and_write(doc3)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 4. Belief referencing unknown evidence_id
    doc4 = json.loads(json.dumps(base_doc))
    doc4["belief_updates"][0]["evidence_ids"] = ["ev_9999"]
    _rehash_and_write(doc4)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 5. Evidence referencing unknown measurement_id
    doc5 = json.loads(json.dumps(base_doc))
    doc5["evidence"][0]["measurement_id"] = "meas_9999"
    _rehash_and_write(doc5)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 6. Sampled-only passed evidence stripped of strong evidence_source
    doc6 = json.loads(json.dumps(base_doc))
    doc6["evidence"][1]["evidence_source"] = None
    _rehash_and_write(doc6)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 7. Action proposal referencing nonexistent or non-belief record
    for bad_bid in ("bel_9999", e1.record_id):
        doc7 = json.loads(json.dumps(base_doc))
        doc7["action_proposals"][0]["belief_id"] = bad_bid
        _rehash_and_write(doc7)
        with pytest.raises(FirewallViolationError):
            EpistemicBlackboard(bb_path)

    # 8. Causal seq inversion (belief seq precedes referenced evidence seq)
    doc8 = json.loads(json.dumps(base_doc))
    doc8["belief_updates"][0]["evidence_ids"] = [e_sampled.record_id]
    _rehash_and_write(doc8)
    with pytest.raises(FirewallViolationError):
        EpistemicBlackboard(bb_path)

    # 9. Mutated Article X constitutional flags
    for bad_const in (
        {"external_actions": 5},
        {"external_actions": True},
        {"sentience_claimed": True},
        {"l5_agi_qualified": True},
        {"zoe_clone_claimed": True},
    ):
        doc9 = json.loads(json.dumps(base_doc))
        doc9["constitutional"].update(bad_const)
        _rehash_and_write(doc9)
        with pytest.raises(FirewallViolationError):
            EpistemicBlackboard(bb_path)

    # 10. Missing or non-mapping constitutional block
    doc10 = json.loads(json.dumps(base_doc))
    del doc10["constitutional"]
    _rehash_and_write(doc10)
    with pytest.raises(TamperDetectedError):
        EpistemicBlackboard(bb_path)

    doc11 = json.loads(json.dumps(base_doc))
    doc11["constitutional"] = "tampered"
    _rehash_and_write(doc11)
    with pytest.raises(TamperDetectedError):
        EpistemicBlackboard(bb_path)


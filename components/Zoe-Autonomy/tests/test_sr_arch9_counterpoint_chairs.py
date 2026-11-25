"""Unit tests for Architecture #9: Counterpoint Chairs (counterpoint_chairs.py)."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import struct
import sys
import time
import wave

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.shared_reasoning.blackboard import (  # noqa: E402
    EpistemicBlackboard,
    FirewallViolationError,
    TamperDetectedError,
)
from zoe_autonomy.shared_reasoning.counterpoint_chairs import (  # noqa: E402
    CANONICAL_VOICE_IDS,
    COUNTERPOINT_CHAIRS_CONTRACT,
    ChairVoice,
    ColdAuditVerdict,
    CounterpointChairsEngine,
    CounterpointRotationSchedule,
    FrozenChairPacket,
    ProblemChair,
    default_counterpoint_voices,
)


def _assert_constitutional(meta: dict[str, object]) -> None:
    assert meta["external_actions"] == 0
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def test_lazy_export_and_default_canonical_voices() -> None:
    assert sr.CounterpointChairsEngine is CounterpointChairsEngine
    voices = default_counterpoint_voices()
    assert tuple(v.voice_id for v in voices) == CANONICAL_VOICE_IDS
    assert len({v.independence_tag for v in voices}) == 4

    engine = CounterpointChairsEngine()
    chairs = [
        ProblemChair("chair_a", "Verify theorem invariants"),
        ProblemChair("chair_b", "Synthesize bounded parser"),
        ProblemChair("chair_c", "Audit memory provenance"),
    ]
    result = engine.run(chairs, rounds=2)
    assert result.contract == COUNTERPOINT_CHAIRS_CONTRACT
    assert result.rounds_executed == 2
    assert result.total_turns == 6
    assert result.schedule_invariants["valid"] is True
    _assert_constitutional(result.constitutional)
    for chair in chairs:
        assert chair.blackboard is not None
        assert chair.blackboard.verify_integrity()["valid"] is True


@pytest.mark.parametrize(
    "n_chairs,n_voices,rounds",
    [
        (3, 4, 4),  # Classic musical chairs: more voices than chairs
        (4, 4, 4),  # Square polyphonic rotation
        (5, 3, 3),  # More chairs than voices
        (1, 3, 4),  # Single chair rotating across 3 voices
    ],
)
def test_rotation_schedule_non_repeating_invariants(
    n_chairs: int,
    n_voices: int,
    rounds: int,
) -> None:
    chair_ids = [f"chair_{i}" for i in range(n_chairs)]
    voice_ids = [f"voice_{j}" for j in range(n_voices)]
    schedule = CounterpointRotationSchedule(chair_ids, voice_ids)

    prev_assignments: dict[str, str] | None = None
    for r in range(rounds):
        assignments = schedule.assign_round(r)
        assert set(assignments.keys()) == set(chair_ids)
        if prev_assignments is not None:
            for cid in chair_ids:
                assert assignments[cid] != prev_assignments[cid]
            if n_chairs >= 2:
                for vid in voice_ids:
                    prev_chairs = {c for c, v in prev_assignments.items() if v == vid}
                    curr_chairs = {c for c, v in assignments.items() if v == vid}
                    assert prev_chairs.isdisjoint(curr_chairs)
        for cid in chair_ids:
            schedule.record_swap(
                round_index=r,
                chair_id=cid,
                departed_voice_id=prev_assignments[cid] if prev_assignments else None,
                incoming_voice_id=assignments[cid],
                preemption_reason="initial_seating" if r == 0 else "step_budget",
            )
        prev_assignments = assignments

    inv = schedule.validate_invariants()
    assert inv["valid"] is True
    assert inv["all_chairs_visited"] is True
    assert inv["no_consecutive_chair_voice_repeat"] is True
    assert inv["no_consecutive_voice_chair_repeat"] is True
    assert inv["no_consecutive_ledger_chair_repeat"] is True
    assert inv["monotonic_elapsed"] is True


def test_rotation_schedule_rejects_invalid_repeats() -> None:
    schedule = CounterpointRotationSchedule(["c1", "c2"], ["v1", "v2"])
    schedule.record_swap(
        round_index=0,
        chair_id="c1",
        departed_voice_id=None,
        incoming_voice_id="v1",
        preemption_reason="initial_seating",
    )
    with pytest.raises(ValueError, match="chair 'c1' repeated"):
        schedule.record_swap(
            round_index=0,
            chair_id="c1",
            departed_voice_id="v1",
            incoming_voice_id="v2",
            preemption_reason="step_budget",
        )
    schedule.record_swap(
        round_index=0,
        chair_id="c2",
        departed_voice_id=None,
        incoming_voice_id="v2",
        preemption_reason="initial_seating",
    )
    with pytest.raises(ValueError, match="cannot immediately re-occupy"):
        schedule.record_swap(
            round_index=1,
            chair_id="c1",
            departed_voice_id="v1",
            incoming_voice_id="v1",
            preemption_reason="step_budget",
        )


def test_frozen_chair_packet_four_lane_separation_and_tamper_evidence() -> None:
    with pytest.raises(FirewallViolationError):
        FrozenChairPacket(
            packet_id="pkt_bad_belief",
            chair_id="c1",
            round_index=0,
            departed_voice_id="v1",
            created_utc="2026-11-24T07:30:00Z",
            preemption_reason="step_budget",
            measurement_summary={"count": 1},
            evidence_ids=(),
            belief_status={"verified_claims": ["unsupported claim"]},
            pending_action_proposals=(),
        )

    with pytest.raises(FirewallViolationError):
        FrozenChairPacket(
            packet_id="pkt_bad_action",
            chair_id="c1",
            round_index=0,
            departed_voice_id="v1",
            created_utc="2026-11-24T07:30:00Z",
            preemption_reason="step_budget",
            measurement_summary={"count": 1},
            evidence_ids=("ev_0001",),
            belief_status={"verified_claims": ["supported"]},
            pending_action_proposals=(
                {"status": "APPROVED", "external_actions": 1, "autonomous_execution_allowed": True},
            ),
        )

    valid_pkt = FrozenChairPacket(
        packet_id="pkt_ok",
        chair_id="c1",
        round_index=0,
        departed_voice_id="v1",
        created_utc="2026-11-24T07:30:00Z",
        preemption_reason="beat_quantum_s",
        measurement_summary={"count": 1, "measurement_ids": ["meas_0001"], "unverified_claims": []},
        evidence_ids=("ev_0001",),
        belief_status={"belief_ids": ["bel_0001"], "verified_claims": ["verified invariant"]},
        pending_action_proposals=(
            {
                "action_kind": "review_patch",
                "status": "REVIEW_REQUIRED",
                "external_actions": 0,
                "autonomous_execution_allowed": False,
            },
        ),
    )
    assert valid_pkt.verify_integrity() is True
    tampered = replace(valid_pkt, evidence_ids=("ev_9999",))
    assert tampered.verify_integrity(raise_on_error=False) is False
    with pytest.raises(TamperDetectedError):
        tampered.verify_integrity(raise_on_error=True)


def test_cold_audit_rejects_unverified_and_sampled_only_claims() -> None:
    def sloppy_voice(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        if ctx["phase"] == "cold_audit":
            return {"probabilities": [0.70, 0.20, 0.10]}
        # Attempt 1: assert an unverified claim + sampled-only expectation match
        return {
            "probabilities": [0.85, 0.10, 0.05],
            "measurement": {
                "input_desc": "sampled trial",
                "method": "random_sample",
                "scope": "3 points",
                "limitations": "incomplete",
                "value": {"ok": True},
                "sampled_only": True,
            },
            "verification": {
                "verifier_name": "naive_check",
                "passed": True,
                "rationale": "looks good as expected",  # Blocked by Art. III.3!
            },
            "claim": "Universal safety proven from 3 samples",
            "unverified_claims": ["Side-channel free without formal proof"],
        }

    def strict_auditor(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        return {
            "probabilities": [0.72, 0.18, 0.10],
            "measurement": {
                "input_desc": "strict audit",
                "method": "deterministic_ast_check",
                "scope": "bounded",
                "limitations": "static",
                "value": {"verified": True},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": "deterministic_ast_verifier",
                "passed": True,
                "rationale": "Deterministic independent verification of bounded AST scope.",
            },
            "claim": "Grounded baseline verified after quarantine",
        }

    voices = [
        ChairVoice("antigravity", "generator", evaluator=sloppy_voice, independence_tag="indep:ag"),
        ChairVoice("zoe", "auditor", evaluator=strict_auditor, independence_tag="indep:zoe"),
    ]
    engine = CounterpointChairsEngine(voices=voices, step_budget=1)
    chair = ProblemChair("chair_audit", "Audit sloppy unverified claims")

    res = engine.run([chair], rounds=2)
    assert res.firewall_violations_caught >= 1
    assert res.flagged_audits_count >= 1

    # Round 1 takeover by zoe must reject antigravity's unverified claims
    first_audit = res.cold_audits[0]
    assert first_audit.departed_voice_id == "antigravity"
    assert first_audit.incoming_voice_id == "zoe"
    assert first_audit.firewall_ok is False
    assert first_audit.accepted is False
    assert len(first_audit.unverified_claims_flagged) >= 1
    assert any("Universal safety proven" in c or "Side-channel free" in c for c in first_audit.unverified_claims_flagged)

    # Sloppy claim must never enter verified belief_status or chair's quarantined list
    first_packet = res.frozen_packets[0]
    assert first_packet.evidence_ids == ()
    assert first_packet.belief_status["verified_claims"] == []
    assert len(chair.state["quarantined_claims"]) >= 1
    assert chair.blackboard is not None
    assert len(chair.blackboard.negative_results()) >= 1


def test_theorem15_cross_voice_discrepancy_and_echo_chamber_detection() -> None:
    def overconfident_voice(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        return {
            "probabilities": [0.98, 0.01, 0.01],
            "measurement": {
                "input_desc": "overconfident check",
                "method": "deterministic_eval",
                "scope": "narrow",
                "limitations": "single hypothesis",
                "value": {"score": 0.98},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": "self_check",
                "passed": True,
                "rationale": "Deterministic internal check completed cleanly.",
            },
            "claim": "Branch A is optimal",
        }

    def dissenting_auditor(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        return {
            "probabilities": [0.04, 0.90, 0.06],
            "measurement": {
                "input_desc": "dissent check",
                "method": "formal_counterexample",
                "scope": "full",
                "limitations": "bounded",
                "value": {"counterexample_found": True},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": "z3_counterexample",
                "passed": True,
                "rationale": "Formal Z3 counterexample found on Branch A.",
            },
            "claim": "Branch B required after counterexample",
        }

    voices = [
        ChairVoice("antigravity", "proposer", evaluator=overconfident_voice, independence_tag="indep:ag"),
        ChairVoice("clara", "critic", evaluator=dissenting_auditor, independence_tag="indep:clara"),
    ]
    engine = CounterpointChairsEngine(voices=voices, step_budget=1, max_discrepancy_dk=0.18)
    chair = ProblemChair("chair_t15", "High discrepancy detection")
    res = engine.run([chair], rounds=2)

    audit = res.cold_audits[0]
    # Exact 2-agent D_K = 0.25 * ||p1 - p2||_2^2 = 0.25 * ((0.94)^2 + (-0.89)^2 + (-0.05)^2) = 0.41955
    expected_dk = 0.25 * ((0.98 - 0.04) ** 2 + (0.01 - 0.90) ** 2 + (0.01 - 0.06) ** 2)
    assert math.isclose(audit.theorem15_discrepancy_dk, expected_dk, rel_tol=0.0, abs_tol=1e-5)
    assert audit.discrepancy_exceeded is True
    assert audit.accepted is False

    # Echo chamber check: two voices sharing identical independence_tag must be flagged
    echo_voices = [
        ChairVoice("v1", "p1", evaluator=overconfident_voice, independence_tag="shared_tag"),
        ChairVoice("v2", "p2", evaluator=overconfident_voice, independence_tag="shared_tag"),
    ]
    echo_engine = CounterpointChairsEngine(voices=echo_voices, step_budget=1)
    echo_res = echo_engine.run([ProblemChair("chair_echo", "Echo check")], rounds=2)
    assert echo_res.cold_audits[0].echo_chamber_detected is True
    assert echo_res.cold_audits[0].accepted is False


def test_preemption_triggers_and_sunk_cost_drift_flagging() -> None:
    # 1. Preemption on a_tau_marginal_gain_drop & sunk-cost flagging
    def stagnant_voice(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        if ctx["phase"] == "cold_audit":
            return {"probabilities": [0.60, 0.25, 0.15]}
        return {
            "probabilities": [0.58, 0.27, 0.15],
            "marginal_gain": -0.02,
            "measurement": {
                "input_desc": "stalled attempt",
                "method": "deterministic_step",
                "scope": "local",
                "limitations": "no progress",
                "value": {"stalled": True},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": "step_verifier",
                "passed": True,
                "rationale": "Deterministic step trace recorded cleanly.",
            },
            "claim": "Stalled hypothesis retained",
        }

    def fresh_voice(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        return {
            "probabilities": [0.65, 0.22, 0.13],
            "marginal_gain": 0.07,
            "measurement": {
                "input_desc": "fresh perspective",
                "method": "deterministic_step",
                "scope": "global",
                "limitations": "bounded",
                "value": {"progress": True},
                "sampled_only": False,
            },
            "verification": {
                "verifier_name": "fresh_verifier",
                "passed": True,
                "rationale": "Deterministic fresh evaluation completed.",
            },
            "claim": "New productive direction",
        }

    engine = CounterpointChairsEngine(
        voices=[
            ChairVoice("v_stalled", "stalled", evaluator=stagnant_voice, independence_tag="indep:1"),
            ChairVoice("v_fresh", "fresh", evaluator=fresh_voice, independence_tag="indep:2"),
        ],
        step_budget=3,
        min_marginal_gain=0.01,
        sunk_cost_patience=1,
    )
    chair = ProblemChair("chair_sunk", "Sunk cost preemption", state={"probabilities": [0.60, 0.25, 0.15]})
    res = engine.run([chair], rounds=2)
    # Substep 0 had marginal_gain = -0.02 < 0.01 -> preempted early before consuming all 3 substeps!
    assert res.frozen_packets[0].preemption_reason == "a_tau_marginal_gain_drop"
    assert res.frozen_packets[0].belief_status["steps_on_chair"] == 1
    assert res.sunk_cost_flags_count >= 1
    assert res.cold_audits[0].sunk_cost_flagged is True
    assert res.cold_audits[0].accepted is False

    # 2. Preemption on beat_quantum_s
    def slow_voice(chair: ProblemChair, packet: FrozenChairPacket | None, ctx: dict) -> dict:
        time.sleep(0.015)
        return {"probabilities": [0.65, 0.20, 0.15], "marginal_gain": 0.05}

    quantum_engine = CounterpointChairsEngine(
        voices=[
            ChairVoice("slow_a", "a", evaluator=slow_voice, independence_tag="indep:a"),
            ChairVoice("slow_b", "b", evaluator=slow_voice, independence_tag="indep:b"),
        ],
        beat_quantum_s=0.01,
        step_budget=5,
    )
    q_res = quantum_engine.run([ProblemChair("chair_q", "Quantum preemption")], rounds=2)
    assert q_res.frozen_packets[0].preemption_reason == "beat_quantum_s"
    assert q_res.frozen_packets[0].belief_status["steps_on_chair"] == 1


def test_sonify_cadence_wav_produces_valid_pcm_audio(tmp_path: Path) -> None:
    engine = CounterpointChairsEngine(step_budget=1)
    chairs = [
        ProblemChair("c_calm_1", "Calm reasoning 1"),
        ProblemChair("c_calm_2", "Calm reasoning 2"),
    ]
    calm_res = engine.run(chairs, rounds=2)
    calm_wav = tmp_path / "calm_cadence.wav"
    calm_meta = engine.sonify_cadence_wav(calm_wav, calm_res, sample_rate=22050, beat_duration_s=0.08)

    assert calm_wav.is_file()
    assert calm_meta["sample_rate"] == 22050
    assert calm_meta["channels"] == 1
    assert calm_meta["sample_width_bytes"] == 2
    assert calm_meta["nframes"] > 0
    _assert_constitutional(calm_meta["constitutional"])

    with wave.open(str(calm_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 22050
        n_frames = wf.getnframes()
        assert n_frames == calm_meta["nframes"]
        raw = wf.readframes(n_frames)
    samples = struct.unpack(f"<{n_frames}h", raw)
    assert any(s != 0 for s in samples)
    assert max(abs(s) for s in samples) <= 32767

    # Tense relay (high discrepancy) should produce distinct audio & higher tension score
    def v_high(c: ProblemChair, p: FrozenChairPacket | None, ctx: dict) -> dict:
        return {"probabilities": [0.96, 0.02, 0.02]}

    def v_low(c: ProblemChair, p: FrozenChairPacket | None, ctx: dict) -> dict:
        return {"probabilities": [0.05, 0.90, 0.05]}

    tense_engine = CounterpointChairsEngine(
        voices=[
            ChairVoice("va", "a", evaluator=v_high, independence_tag="indep:va"),
            ChairVoice("vb", "b", evaluator=v_low, independence_tag="indep:vb"),
        ],
        step_budget=1,
        max_discrepancy_dk=0.10,
    )
    tense_res = tense_engine.run([ProblemChair("c_tense", "Tense check")], rounds=2)
    tense_wav = tmp_path / "tense_cadence.wav"
    tense_meta = tense_engine.sonify_cadence_wav(tense_wav, tense_res, sample_rate=22050, beat_duration_s=0.08)

    assert tense_wav.is_file()
    assert tense_meta["sha256"] != calm_meta["sha256"]
    assert max(tense_meta["tension_scores"]) > max(calm_meta["tension_scores"])


def test_end_to_end_polyphonic_rotation_blackboard_quorum_and_wav(tmp_path: Path) -> None:
    """E2E integration: multi-chair relay + persistent EpistemicBlackboard + FourPeerQuorumEngine + WAV."""
    bb_paths = [tmp_path / f"chair_bb_{i}.json" for i in range(3)]
    chairs = [
        ProblemChair(
            "chair_arch_alpha",
            "Verify symbolic invariant across modules",
            blackboard=EpistemicBlackboard(bb_paths[0]),
        ),
        ProblemChair(
            "chair_arch_beta",
            "Audit cross-voice epistemic firewall boundaries",
            blackboard=EpistemicBlackboard(bb_paths[1]),
        ),
        ProblemChair(
            "chair_arch_gamma",
            "Evaluate bounded MCTS stopping stability",
            blackboard=EpistemicBlackboard(bb_paths[2]),
        ),
    ]

    engine = CounterpointChairsEngine(step_budget=2, max_discrepancy_dk=0.22)
    result = engine.run(chairs, rounds=3)

    # 1. Rotation & schedule invariants across 3 chairs x 4 voices x 3 rounds
    assert result.rounds_executed == 3
    assert result.total_turns == 9
    assert len(result.swap_ledger) == 9
    assert len(result.cold_audits) == 6
    assert len(result.frozen_packets) == 9
    assert result.schedule_invariants["valid"] is True
    assert result.schedule_invariants["all_chairs_visited"] is True
    assert result.schedule_invariants["no_consecutive_chair_voice_repeat"] is True
    assert result.schedule_invariants["no_consecutive_voice_chair_repeat"] is True
    assert result.schedule_invariants["no_consecutive_ledger_chair_repeat"] is True
    _assert_constitutional(result.constitutional)

    # All 4 canonical heterogeneous voices must have participated across the 3x4 relay
    participating_voices = {entry.incoming_voice_id for entry in result.swap_ledger}
    assert participating_voices == set(CANONICAL_VOICE_IDS)

    # 2. Real EpistemicBlackboard persistence & 4-lane FrozenChairPacket integrity
    for pkt in result.frozen_packets:
        assert pkt.verify_integrity(raise_on_error=True) is True
        assert "measurement_ids" in pkt.measurement_summary
        assert isinstance(pkt.evidence_ids, tuple)
        assert "belief_ids" in pkt.belief_status
        for prop in pkt.pending_action_proposals:
            assert prop["status"] == "REVIEW_REQUIRED"
            assert prop["external_actions"] == 0
            assert prop["autonomous_execution_allowed"] is False

    for path, chair in zip(bb_paths, chairs):
        assert path.is_file()
        reloaded_bb = EpistemicBlackboard(path)
        integrity = reloaded_bb.verify_integrity(raise_on_error=True)
        assert integrity["valid"] is True
        assert len(reloaded_bb.list_measurements()) >= 3
        assert len(reloaded_bb.list_evidence()) >= 3
        assert len(reloaded_bb.list_beliefs()) >= 1
        for action in reloaded_bb.list_action_proposals():
            assert action.status == "REVIEW_REQUIRED"
            assert action.external_actions == 0
            assert action.autonomous_execution_allowed is False
        assert chair.frozen_packet is not None
        assert chair.frozen_packet.blackboard_chain_head == reloaded_bb.chain_head

    # 3. Real FourPeerQuorumEngine & arbitrate_teamwork_quorum Theorem 15 Cold Audit checks
    for audit in result.cold_audits:
        assert isinstance(audit, ColdAuditVerdict)
        assert audit.packet_integrity_ok is True
        assert audit.evidence_record_id is not None
        assert audit.teamwork_arbitration is not None
        assert audit.teamwork_arbitration["quorum_supplied"] is True
        assert math.isclose(
            float(audit.teamwork_arbitration["d_k_disagreement"]),
            audit.theorem15_discrepancy_dk,
            rel_tol=0.0,
            abs_tol=1e-6,
        )
        assert audit.theorem15_verdict in {"COORDINATE_CONSENSUS", "ABSTAIN", "ECHO_CHAMBER_WARNING"}

    # 4. Sonify polyphonic cadence WAV and verify wave header + PCM frames
    wav_path = tmp_path / "e2e_counterpoint_cadence.wav"
    wav_meta = engine.sonify_cadence_wav(wav_path, result, sample_rate=22050, beat_duration_s=0.06)
    assert wav_path.is_file()
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 22050
        assert wf.getcomptype() == "NONE"
        n_frames = wf.getnframes()
        assert n_frames == wav_meta["nframes"]
        assert n_frames > 0
        raw_frames = wf.readframes(n_frames)
    pcm = struct.unpack(f"<{n_frames}h", raw_frames)
    assert any(sample != 0 for sample in pcm)
    assert max(abs(sample) for sample in pcm) <= 32767


def test_counterpoint_chairs_honors_offline_privacy_and_probe_local_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import zoe_autonomy.shared_reasoning.sdk_bridge as sdk_bridge_mod
    import zoe_autonomy.stem_layering as stem_layering_mod
    from zoe_autonomy.shared_reasoning.sdk_bridge import ZoeAntigravityBridge

    def _forbid_probe(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("probe_local_qwen must not be called")

    def _forbid_local_openai(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("LocalOpenAIAgentConfig must not be called")

    def _forbid_gemini(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("LocalAgentConfig must not be called")

    monkeypatch.setattr(sdk_bridge_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(sdk_bridge_mod, "LocalOpenAIAgentConfig", _forbid_local_openai)
    monkeypatch.setattr(sdk_bridge_mod, "LocalAgentConfig", _forbid_gemini)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-must-not-be-used")

    auto_bridge = ZoeAntigravityBridge(mode="auto")
    engine_offline = CounterpointChairsEngine(
        voices=default_counterpoint_voices(bridge=auto_bridge),
        bridge=auto_bridge,
        offline_only=True,
        privacy_sensitive=True,
        probe_local=False,
        bridge_mode="offline",
        step_budget=1,
    )
    res_offline = engine_offline.run([ProblemChair("c_off", "Verify offline constraint propagation")], rounds=2)
    assert res_offline.total_turns == 2
    assert res_offline.schedule_invariants["valid"] is True

    engine_no_probe = CounterpointChairsEngine(
        voices=default_counterpoint_voices(bridge=auto_bridge),
        bridge=auto_bridge,
        privacy_sensitive=True,
        probe_local=False,
        step_budget=1,
    )
    res_no_probe = engine_no_probe.run([ProblemChair("c_np", "Verify probe_local=False propagation")], rounds=2)
    assert res_no_probe.total_turns == 2
    assert res_no_probe.schedule_invariants["valid"] is True

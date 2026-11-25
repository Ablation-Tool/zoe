"""End-to-End Integration Tests for SharedReasoningOrchestrator (Arch 1-9 Composer)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import wave
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
GUIAI_LAB = REPO_ROOT / "guiai-lab"
for p in (ZOE_AUTONOMY_SRC, GUIAI_LAB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.shared_reasoning import (  # noqa: E402
    AlphaEvolveLoop,
    CounterpointChairsEngine,
    EpistemicBlackboard,
    FirewallViolationError,
    FourPeerQuorumEngine,
    HumanSteeringDetector,
    KlosterMCTSSearch,
    LiveProcessSupervisor,
    RealitySandboxLab,
    SharedReasoningOrchestrator,
    SharedReasoningRunReport,
    SharedReasoningTaskSpec,
    System2To1Distiller,
    ZoeAntigravityBridge,
)


def _assert_constitutional_report(report: SharedReasoningRunReport) -> None:
    assert report.external_actions == 0
    assert report.sentience_claimed is False
    assert report.l5_agi_qualified is False
    assert report.zoe_clone_claimed is False
    assert report.attribution == "Nicholas Michael Kloster, March 6, 2026"
    c = report.constitutional
    assert c["external_actions"] == 0
    assert c["sentience_claimed"] is False
    assert c["l5_agi_qualified"] is False
    assert c["zoe_clone_claimed"] is False
    assert c["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def test_package_exports_all_nine_architectures_and_composer() -> None:
    avail = sr.available_submodules()
    assert avail["sdk_bridge"] is True
    for sub in (
        "alpha_evolve",
        "process_supervision",
        "mcts_kloster",
        "quorum",
        "distillation",
        "blackboard",
        "sandbox_labs",
        "human_steering",
        "counterpoint_chairs",
        "orchestrator",
    ):
        assert avail[sub] is True, f"submodule {sub!r} failed availability check"

    assert sr.SharedReasoningOrchestrator is SharedReasoningOrchestrator
    assert sr.SharedReasoningRunReport is SharedReasoningRunReport
    assert sr.SharedReasoningTaskSpec is SharedReasoningTaskSpec
    assert sr.AlphaEvolveLoop is AlphaEvolveLoop
    assert sr.LiveProcessSupervisor is LiveProcessSupervisor
    assert sr.KlosterMCTSSearch is KlosterMCTSSearch
    assert sr.FourPeerQuorumEngine is FourPeerQuorumEngine
    assert sr.System2To1Distiller is System2To1Distiller
    assert sr.EpistemicBlackboard is EpistemicBlackboard
    assert sr.RealitySandboxLab is RealitySandboxLab
    assert sr.HumanSteeringDetector is HumanSteeringDetector
    assert sr.CounterpointChairsEngine is CounterpointChairsEngine
    assert sr.ZoeAntigravityBridge is ZoeAntigravityBridge


def test_orchestrator_end_to_end_all_nine_architectures_offline(tmp_path: Path) -> None:
    wav_path = tmp_path / "orchestrator_cadence.wav"
    selected_paths: list[str] = []

    def _steering_cb(spec: Any) -> dict[str, Any]:
        opts = spec.questions[0].options
        chosen = opts[0].id
        selected_paths.append(chosen)
        return {"selected_option_ids": [chosen], "freeform_response": "verified formal choice"}

    orch = SharedReasoningOrchestrator(
        mode="offline",
        offline_only=True,
        repo_root=REPO_ROOT,
        seed=42,
    )
    spec = SharedReasoningTaskSpec(
        prompt="Verify quadratic scoring policy, prove symbolic & Z3 invariants, and distill.",
        sonify_wav_path=wav_path,
        steering_callback=_steering_cb,
        high_impact=True,
    )
    report = orch.run(spec)

    assert isinstance(report, SharedReasoningRunReport)
    _assert_constitutional_report(report)

    # Transport + Arch 2 Supervision
    assert report.bridge_turn.resolution.selected_mode == "offline"
    assert report.bridge_turn.history_steps >= 2
    assert report.supervision_summary["total_events"] >= 2
    assert report.supervision_summary["constitutional"]["external_actions"] == 0

    # Arch 1 AlphaEvolve
    assert report.alpha_evolve.best_program.passed_tests == report.alpha_evolve.best_program.total_tests
    assert report.alpha_evolve.best_program.score == pytest.approx(1.0)
    assert len(report.alpha_evolve.lineage) >= 1

    # Arch 7 RealitySandboxLab (SymPy + Z3 + AST)
    assert report.sandbox_verdicts["sympy"].passed is True
    assert report.sandbox_verdicts["z3"].passed is True
    assert report.sandbox_verdicts["ast_program"].passed is True

    # Arch 3 KlosterMCTSSearch
    assert report.mcts_result.decision in ("DECIDE_SIGNAL", "GATHER_MORE", "ABSTAIN_INSUFFICIENT_EVIDENCE")
    assert len(report.mcts_result.pruned_branches) >= 1
    assert report.mcts_result.best_branch is not None

    # Arch 9 CounterpointChairsEngine + sonification WAV
    assert report.counterpoint_result.schedule_invariants["valid"] is True
    assert report.counterpoint_result.total_turns == 6
    assert report.counterpoint_result.firewall_violations_caught == 0
    assert report.cadence_wav is not None
    assert wav_path.is_file()
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnframes() > 0

    # Arch 4 FourPeerQuorumEngine + stem_layering.py
    assert report.quorum_result.verdict == "COORDINATE_CONSENSUS"
    assert report.quorum_result.brier_identity_verified is True
    assert report.quorum_result.independence_verified is True
    assert report.quorum_route.stem_decision.selected_tier in (
        "gear1_eliza",
        "local_qwen",
        "flash_lite",
        "flash",
        "pro",
    )

    # Arch 8 HumanSteeringDetector + OnInteractionHook
    assert report.steering_report.fork_detected is True
    assert len(report.steering_report.divergent_options) >= 2
    assert report.steering_interaction is not None
    assert report.steering_interaction["decision"] == "selected"
    assert report.steering_interaction["external_actions"] == 0
    assert len(selected_paths) == 1

    # Arch 5 System2To1Distiller -> ZoeUnifiedMemory
    assert len(report.distilled_artifacts) >= 2
    assert report.distilled_replay_outputs["score_candidate"] == pytest.approx(4.0)
    assert orch.distiller.replay_skill("score_candidate", {"x": 5.0}) == pytest.approx(25.0)

    # Arch 6 EpistemicBlackboard 4-lane spine & hash-chain integrity
    assert report.blackboard_integrity["valid"] is True
    assert report.blackboard_integrity["tamper_detected"] is False
    lanes = report.blackboard_lanes["lanes"]
    assert lanes["measurement"]["count"] >= 6
    assert lanes["evidence"]["count"] >= 6
    assert lanes["belief_update"]["count"] >= 2
    assert lanes["action_proposal"]["count"] >= 1
    assert lanes["action_proposal"]["external_actions"] == 0

    for prop in orch.blackboard.list_action_proposals():
        assert prop.status == "REVIEW_REQUIRED"
        assert prop.external_actions == 0
        assert prop.requires_human_review is True
        assert prop.autonomous_execution_allowed is False

    # JSON serializability check
    serialized = json.dumps(report.to_dict())
    parsed = json.loads(serialized)
    assert parsed["external_actions"] == 0
    assert parsed["sentience_claimed"] is False


def test_orchestrator_auto_mode_with_dataset_and_eliza_distillation(tmp_path: Path) -> None:
    orch = SharedReasoningOrchestrator(
        mode="auto",
        probe_local=False,
        state_dir=tmp_path,
        repo_root=REPO_ROOT,
        seed=42,
    )
    spec = SharedReasoningTaskSpec(
        prompt="Verify simplex dataset conservation and distill Gear-1 ELIZA rule.",
        dataset=[
            {"zoe": 0.6, "clara": 0.3, "ag": 0.1},
            {"zoe": 0.5, "clara": 0.25, "ag": 0.25},
        ],
        dataset_invariants=[
            {"kind": "simplex", "columns": ["zoe", "clara", "ag"], "target": 1.0},
            {"kind": "non_empty", "min_rows": 2},
        ],
        eliza_rule_spec={
            "rule_id": "distilled_simplex_rule",
            "keywords": ("simplex",),
            "rank": 15,
            "pattern": r".*\bsimplex\b(.*)",
            "response": "Simplex conservation verified via RealitySandboxLab.",
        },
    )
    report = orch.run(spec)
    _assert_constitutional_report(report)
    assert report.sandbox_verdicts["dataset"].passed is True
    assert any(a.artifact_kind == "eliza_rule" for a in report.distilled_artifacts)
    rule_hit = orch.distiller.lookup_rule("check simplex invariant")
    assert rule_hit is not None
    assert "Simplex conservation verified" in rule_hit["reply"]
    assert report.blackboard_integrity["valid"] is True


def test_constitutional_firewall_blocks_illegal_lane_jump_on_orchestrator_blackboard() -> None:
    orch = SharedReasoningOrchestrator(mode="offline", offline_only=True, repo_root=REPO_ROOT)
    report = orch.run("Check firewall enforcement after composed run.")
    assert report.blackboard_integrity["valid"] is True

    raw_meas = orch.blackboard.post_measurement(
        source_agent="untrusted_probe",
        input_desc="unverified hypothesis",
        method="sampling_only",
        scope="bounded test",
        limitations="not independently verified",
        value=0.99,
        sampled_only=True,
    )
    with pytest.raises(FirewallViolationError):
        orch.blackboard.update_belief(
            [raw_meas.record_id],
            claim="Illegal shortcut from raw measurement",
            posterior_delta=0.5,
        )

    # Sampled measurement cannot pass with expectation-only rationale
    with pytest.raises(FirewallViolationError):
        orch.blackboard.promote_to_evidence(
            raw_meas.record_id,
            verifier_name="naive_checker",
            passed=True,
            rationale="Looks good and matches expectation",
        )


def test_orchestrator_never_probes_local_or_spawns_local_openai_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: probe_local=False, offline_only=True, and privacy_sensitive=True
    must never call probe_local_qwen or LocalOpenAIAgentConfig in any stage 1-9.
    """
    import zoe_autonomy.shared_reasoning.sdk_bridge as sdk_bridge_mod
    import zoe_autonomy.stem_layering as stem_layering_mod

    def _forbid_probe(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("probe_local_qwen must not be invoked when disabled/offline")

    def _forbid_local_openai(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("LocalOpenAIAgentConfig must not be instantiated when disabled/offline")

    def _forbid_gemini(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("LocalAgentConfig must not be instantiated under offline_only/privacy_sensitive")

    monkeypatch.setattr(sdk_bridge_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _forbid_probe)
    monkeypatch.setattr(sdk_bridge_mod, "LocalOpenAIAgentConfig", _forbid_local_openai)

    # 1. mode="auto", probe_local=False (no Gemini keys)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    orch_no_probe = SharedReasoningOrchestrator(
        mode="auto",
        probe_local=False,
        state_dir=tmp_path / "no_probe",
        repo_root=REPO_ROOT,
        seed=42,
    )
    rep_no_probe = orch_no_probe.run(
        SharedReasoningTaskSpec(prompt="Verify auto mode with probe_local=False stays offline.")
    )
    _assert_constitutional_report(rep_no_probe)
    assert rep_no_probe.bridge_turn.resolution.selected_mode == "offline"
    assert rep_no_probe.mcts_result.voice_mode == "offline"
    assert rep_no_probe.counterpoint_result.total_turns == 6

    # 2. mode="auto", offline_only=True (even with probe_local=True and GEMINI_API_KEY set)
    monkeypatch.setattr(sdk_bridge_mod, "LocalAgentConfig", _forbid_gemini)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key-must-be-ignored")
    orch_offline_only = SharedReasoningOrchestrator(
        mode="auto",
        offline_only=True,
        probe_local=True,
        state_dir=tmp_path / "offline_only",
        repo_root=REPO_ROOT,
        seed=42,
    )
    rep_offline = orch_offline_only.run(
        SharedReasoningTaskSpec(prompt="Verify offline_only=True blocks local and cloud transports.")
    )
    _assert_constitutional_report(rep_offline)
    assert rep_offline.bridge_turn.resolution.selected_mode == "offline"
    assert rep_offline.mcts_result.voice_mode == "offline"
    assert rep_offline.counterpoint_result.total_turns == 6

    # 3. mode="auto", privacy_sensitive=True, probe_local=False (even with GEMINI_API_KEY set)
    orch_private = SharedReasoningOrchestrator(
        mode="auto",
        privacy_sensitive=True,
        probe_local=False,
        state_dir=tmp_path / "privacy_sensitive",
        repo_root=REPO_ROOT,
        seed=42,
    )
    rep_private = orch_private.run(
        SharedReasoningTaskSpec(prompt="Verify privacy_sensitive=True + probe_local=False stays offline.")
    )
    _assert_constitutional_report(rep_private)
    assert rep_private.bridge_turn.resolution.selected_mode == "offline"
    assert rep_private.mcts_result.voice_mode == "offline"
    assert rep_private.counterpoint_result.total_turns == 6


def test_orchestrator_stage2_probe_local_false_and_privacy_sensitive_drop_after_stage1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test matching challenger_m4_r2 Section 5 reproduction probes.

    1. mode="auto", probe_local=False with GEMINI_API_KEY set and 127.0.0.1:8080
       ostensibly reachable must make 0 probe_local_qwen and 0 LocalOpenAIAgentConfig
       calls across ALL stages (including Stage 2 AlphaEvolve).
    2. mode="auto", privacy_sensitive=True, probe_local=True with GEMINI_API_KEY set
       when local_qwen is reachable in Stage 1 and drops before Stage 2 must make
       0 cloud LocalAgentConfig calls across ALL stages.
    """
    from google.antigravity.hooks import policy as policy_mod
    import zoe_autonomy.shared_reasoning.sdk_bridge as sb
    import zoe_autonomy.stem_layering as stem_layering_mod

    probe_calls: list[int] = []
    openai_calls: list[int] = []
    gemini_calls: list[int] = []

    def _stub_openai(*_args: Any, **kw: Any) -> Any:
        openai_calls.append(1)
        return sb.DualTransportAgentConfig(
            mode="offline",
            policies=kw.get("policies") or [policy_mod.deny_all()],
        )

    def _stub_gemini(*_args: Any, **kw: Any) -> Any:
        gemini_calls.append(1)
        return sb.DualTransportAgentConfig(
            mode="offline",
            policies=kw.get("policies") or [policy_mod.deny_all()],
        )

    def _probe_always_up(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        probe_calls.append(1)
        return {
            "available": True,
            "endpoint": "http://127.0.0.1:8080/v1/models",
            "models": ["qwen"],
            "loopback_only": True,
        }

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(sb, "LocalOpenAIAgentConfig", _stub_openai)
    monkeypatch.setattr(sb, "LocalAgentConfig", _stub_gemini)
    monkeypatch.setattr(sb, "probe_local_qwen", _probe_always_up)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _probe_always_up)

    # Probe 1: probe_local=False with GEMINI_API_KEY set
    orch = SharedReasoningOrchestrator(
        mode="auto",
        probe_local=False,
        state_dir=tmp_path / "probe_local_false",
        repo_root=REPO_ROOT,
        seed=42,
    )
    rep1 = orch.run(SharedReasoningTaskSpec(prompt="Audit probe_local=False"))
    _assert_constitutional_report(rep1)
    assert len(probe_calls) == 0
    assert len(openai_calls) == 0

    # Probe 2: privacy_sensitive=True when local_qwen is up in Stage 1 and drops afterward
    probe_calls.clear()
    openai_calls.clear()
    gemini_calls.clear()
    seq = [True] + [False] * 500

    def _probe_drop_after_stage1(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        probe_calls.append(1)
        avail = seq.pop(0) if seq else False
        return {
            "available": avail,
            "endpoint": "http://127.0.0.1:8080/v1/models",
            "models": ["qwen"] if avail else [],
            "loopback_only": True,
        }

    monkeypatch.setattr(sb, "probe_local_qwen", _probe_drop_after_stage1)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _probe_drop_after_stage1)

    orch2 = SharedReasoningOrchestrator(
        mode="auto",
        privacy_sensitive=True,
        probe_local=True,
        state_dir=tmp_path / "privacy_drop",
        repo_root=REPO_ROOT,
        seed=42,
    )
    rep2 = orch2.run(SharedReasoningTaskSpec(prompt="Audit privacy_sensitive=True"))
    _assert_constitutional_report(rep2)
    assert len(openai_calls) == 0
    assert len(gemini_calls) == 0

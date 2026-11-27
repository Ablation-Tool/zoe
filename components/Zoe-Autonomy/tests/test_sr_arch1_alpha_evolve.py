"""Unit tests for Architecture #1: AlphaEvolve / FunSearch Loop (``alpha_evolve.py``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.shared_reasoning import CallableVoiceAdapter, ZoeAntigravityBridge  # noqa: E402
from zoe_autonomy.shared_reasoning.alpha_evolve import (  # noqa: E402
    ALPHA_EVOLVE_CONTRACT,
    AlphaEvolveLoop,
    AlphaEvolveResult,
    AntigravityProgramMutator,
    CandidateProgram,
    EvolutionaryArchive,
    TestCase,
    ZoeDeterministicVerifier,
)


def _assert_constitutional(doc: dict[str, Any]) -> None:
    assert doc["external_actions"] == 0
    assert doc["sentience_claimed"] is False
    assert doc["l5_agi_qualified"] is False
    assert doc["zoe_clone_claimed"] is False
    assert doc["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def test_lazy_export_and_verifier_unsafe_ast_rejection() -> None:
    assert sr.AlphaEvolveLoop is AlphaEvolveLoop
    assert ALPHA_EVOLVE_CONTRACT == "zoe-shared-reasoning-alpha-evolve/v1"

    verifier = ZoeDeterministicVerifier()
    cases = [TestCase(inputs={"x": float(v)}, expected=float(v * 2)) for v in (-2, 0, 3)]

    hostile_payloads = [
        "def f(x):\n    import os\n    return x",
        "def f(x):\n    from os import system\n    return x",
        "def f(x):\n    return eval('x + 1')",
        "def f(x):\n    exec('import sys')\n    return x",
        "def f(x):\n    return open('/etc/passwd').read()",
        "def f(x):\n    return __import__('os').system('id')",
        "def f(x):\n    while True:\n        x = x + 1\n    return x",
        "def f(x):\n    return x.__class__",
        "def f(x):\n    return (lambda v: v)(x)",
    ]
    for payload in hostile_payloads:
        rep = verifier.evaluate(payload, cases, expected_name="f", expected_args=("x",))
        assert rep.safe is False
        assert rep.score == 0.0
        assert rep.passed_tests == 0
        assert rep.error is not None
        assert rep.behavior_descriptor == ("unsafe_ast",)

    good = verifier.evaluate(
        "def f(x):\n    return 2 * x",
        cases,
        expected_name="f",
        expected_args=("x",),
    )
    assert good.safe is True
    assert good.passed_tests == 3
    assert good.total_tests == 3
    assert good.score == 1.0


def test_map_elites_diversity_sampling_and_rollback_lineage() -> None:
    verifier = ZoeDeterministicVerifier()
    cases = [TestCase(inputs={"x": float(x)}, expected=float(x * x)) for x in (-2, -1, 0, 1, 2, 3)]

    candidates_src = [
        ("p_lin", None, 0, 0, "def g(x):\n    return x"),
        ("p_pos", "p_lin", 1, 0, "def g(x):\n    return pos(x)"),
        ("p_branch", "p_lin", 1, 1, "def g(x):\n    if x >= 0:\n        return x\n    return -x"),
        ("p_quad", "p_pos", 2, 2, "def g(x):\n    return sq(x)"),
    ]

    archive = EvolutionaryArchive(num_islands=3, temperature=0.2, migration_interval=2)
    gen0_progs: list[CandidateProgram] = []
    for cid, pid, gen, isl, src in candidates_src:
        rep = verifier.evaluate(src, cases, expected_name="g", expected_args=("x",))
        assert rep.safe is True
        prog = CandidateProgram(
            id=cid,
            code=src,
            function_name="g",
            parent_id=pid,
            generation=gen,
            behavior_descriptor=rep.behavior_descriptor,
            score=rep.score,
            passed_tests=rep.passed_tests,
            diff_from_parent="" if pid is None else f"diff:{pid}->{cid}",
            total_tests=rep.total_tests,
            ast_metrics=dict(rep.ast_metrics),
            code_sha256=rep.code_sha256,
            island_id=isl,
        )
        admitted = archive.insert(prog, island_id=isl)
        assert admitted is True
        if gen == 0:
            archive.record_snapshot(0)
            gen0_progs.append(prog)
        elif gen == 1 and cid == "p_branch":
            archive.record_snapshot(1)
        elif gen == 2:
            archive.record_snapshot(2)

    div = archive.diversity_summary()
    assert div["unique_descriptors"] >= 3
    assert div["occupied_niches_total"] >= 4
    assert div["best_score"] == 1.0

    top2 = archive.top_k(2)
    assert top2[0].id == "p_quad"
    assert top2[0].score == 1.0

    lineage = archive.get_lineage("p_quad")
    assert [p.id for p in lineage] == ["p_lin", "p_pos", "p_quad"]

    rng = random.Random(7)
    for strat in ("boltzmann", "tournament", "uniform"):
        sampled = archive.sample_parent(rng, strategy=strat)
        assert sampled.id in archive.programs

    # Migration at generation 2 copies top elite across islands
    migrated = archive.migrate(2)
    assert migrated >= 1

    # Rollback to generation 1 removes gen-2 quad elite from active islands while preserving audit log
    assert archive.rollback_to_generation(1) is True
    assert archive.top_k(1)[0].id != "p_quad"
    assert len(archive.rollback_log) == 1


def test_genuine_evolutionary_improvement_across_generations() -> None:
    """Verify real AST evolution improves score on f(x) = x^2 + 2*x + 1 from naive seed."""
    test_cases = [
        ({"x": float(x)}, float(x * x + 2.0 * x + 1.0))
        for x in (-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0)
    ]
    seed_code = "def synthesize_poly(x):\n    return x"

    verifier = ZoeDeterministicVerifier()
    seed_report = verifier.evaluate(seed_code, test_cases)
    assert seed_report.safe is True
    assert seed_report.passed_tests < len(test_cases)

    loop = AlphaEvolveLoop(
        verifier=verifier,
        mutator=AntigravityProgramMutator(mode="ast_only", seed=42),
        archive=EvolutionaryArchive(num_islands=3, temperature=0.06, migration_interval=3),
        seed=42,
        offspring_per_gen=20,
    )
    result = loop.evolve(
        seed_code,
        test_cases,
        generations=20,
        prompt_context="Synthesize exact quadratic polynomial from x.",
    )
    assert isinstance(result, AlphaEvolveResult)
    _assert_constitutional(result.constitutional)

    gen0_score = result.generation_history[0]["best_score"]
    final_score = result.best_program.score
    assert final_score > gen0_score
    assert result.best_program.score >= 0.85
    assert result.best_program.passed_tests > seed_report.passed_tests

    # Verify non-empty diff and full lineage chain from seed -> best_program
    assert len(result.lineage) >= 2
    assert result.lineage[0].parent_id is None
    assert result.lineage[-1].id == result.best_program.id
    for idx in range(1, len(result.lineage)):
        node = result.lineage[idx]
        assert node.parent_id == result.lineage[idx - 1].id
        assert "@@" in node.diff_from_parent
        assert "---" in node.diff_from_parent
        assert "+++" in node.diff_from_parent

    # Verify MAP-Elites preserved multiple distinct behavior descriptors across the run
    div = result.archive.diversity_summary()
    assert div["unique_descriptors"] >= 3

    # Verify JSON-serializable summary
    payload = result.to_dict()
    assert payload["best_program"]["score"] == final_score
    assert len(payload["lineage"]) == len(result.lineage)


def test_antigravity_bridge_mutation_with_unsafe_rejection_and_offline_fallback() -> None:
    """Verify Antigravity bridge mutations are AST-gated and offline ELIZA falls back cleanly."""
    cases = [({"x": float(x)}, float(abs(x))) for x in (-3, -1, 0, 2, 4)]
    seed_code = "def target_abs(x):\n    return x"

    call_count = {"n": 0}

    async def adversarial_then_valid_voice(prompt: str, context: dict[str, Any]) -> str:
        call_count["n"] += 1
        n = call_count["n"]
        if n == 1:
            return "```python\ndef target_abs(x):\n    import os\n    return os.getpid()\n```"
        if n == 2:
            return "```python\ndef target_abs(x):\n    return eval('abs(x)')\n```"
        if n == 3:
            return "```python\ndef target_abs(x):\n    return abs(x)\n```"
        return "No code emitted on this turn."

    bridge = ZoeAntigravityBridge(mode="offline")
    mutator = AntigravityProgramMutator(
        bridge=bridge,
        voice_adapter=CallableVoiceAdapter(adversarial_then_valid_voice),
        mode="hybrid",
        seed=99,
    )
    loop = AlphaEvolveLoop(mutator=mutator, seed=99, offspring_per_gen=4)
    result = loop.evolve(seed_code, cases, generations=2)

    assert call_count["n"] >= 4
    assert result.best_program.score == 1.0
    assert result.best_program.passed_tests == len(cases)

    unsafe_rejects = [
        r for r in result.rejected_candidates if r.get("rejection_kind") == "unsafe_ast"
    ]
    assert len(unsafe_rejects) >= 2
    assert any("import" in r["reason"].lower() for r in unsafe_rejects)
    assert any("eval" in r["reason"].lower() for r in unsafe_rejects)

    # Also verify pure ZoeOfflineVoiceAdapter (without custom handler) falls back to AST mutator
    offline_mutator = AntigravityProgramMutator(
        bridge=ZoeAntigravityBridge(mode="offline"),
        mode="hybrid",
        seed=5,
    )
    seed_cand = CandidateProgram(
        id="seed_0",
        code=seed_code,
        function_name="target_abs",
        parent_id=None,
        generation=0,
        behavior_descriptor=("straight", 0, "linear", "nondec", "under"),
        score=0.4,
        passed_tests=3,
        diff_from_parent="",
        total_tests=5,
    )
    outcome = offline_mutator.mutate(seed_cand)
    assert outcome.source == "ast_mutator_fallback"
    assert "def target_abs(" in outcome.code


def test_optional_blackboard_measurement_and_evidence_emission() -> None:
    @dataclass
    class _StubRec:
        id: str

    class _StubBlackboard:
        def __init__(self) -> None:
            self.measurements: list[dict[str, Any]] = []
            self.evidences: list[dict[str, Any]] = []

        def post_measurement(self, **kwargs: Any) -> _StubRec:
            rec_id = f"m_{len(self.measurements) + 1}"
            self.measurements.append({"id": rec_id, **kwargs})
            return _StubRec(id=rec_id)

        def promote_to_evidence(
            self,
            measurement_id: str,
            verifier_name: str,
            passed: bool,
            rationale: str,
        ) -> _StubRec:
            ev_id = f"ev_{len(self.evidences) + 1}"
            self.evidences.append(
                {
                    "id": ev_id,
                    "measurement_id": measurement_id,
                    "verifier_name": verifier_name,
                    "passed": passed,
                    "rationale": rationale,
                }
            )
            return _StubRec(id=ev_id)

    bb = _StubBlackboard()
    cases = [({"x": float(x)}, float(x * x)) for x in (-2, 0, 2)]
    loop = AlphaEvolveLoop(
        mutator=AntigravityProgramMutator(mode="ast_only", seed=11),
        blackboard=bb,
        seed=11,
        offspring_per_gen=6,
    )
    result = loop.evolve("def sq_fn(x):\n    return sq(x)", cases, generations=1)
    assert result.best_program.score == 1.0
    assert len(bb.measurements) == 2  # gen 0 + gen 1
    assert len(bb.evidences) == 2
    assert len(result.blackboard_records) == 2
    assert result.blackboard_records[0]["promoted_to_evidence"] is True


def test_real_epistemic_blackboard_bridge_lineage_and_rollback_integration(
    tmp_path: Path,
) -> None:
    """Round 2 integration: real EpistemicBlackboard + ZoeAntigravityBridge + rollback."""
    from zoe_autonomy.shared_reasoning.blackboard import (
        EpistemicBlackboard,
        FirewallViolationError,
    )

    bb = EpistemicBlackboard(tmp_path / "blackboard")
    cases = [
        ({"x": float(x), "y": float(y)}, float(abs(x - y)))
        for x, y in ((-2, 3), (0, 0), (5, 1), (-4, -1), (3, 7))
    ]
    seed_code = "def synth_margin(x, y):\n    return x"

    turn = {"i": 0}

    async def scripted_offline_voice(prompt: str, context: dict[str, Any]) -> str:
        turn["i"] += 1
        step = turn["i"]
        if step == 1:
            return "```python\ndef synth_margin(x, y):\n    import os\n    return os.getpid()\n```"
        if step == 2:
            return "```python\ndef synth_margin(x, y):\n    return x - y\n```"
        if step == 3:
            return "```python\ndef synth_margin(x, y):\n    return eval('abs(x - y)')\n```"
        if step == 4:
            return "```python\ndef synth_margin(x, y):\n    return abs(x - y)\n```"
        return "Unable to synthesize further."

    bridge = ZoeAntigravityBridge(mode="offline")
    mutator = AntigravityProgramMutator(
        bridge=bridge,
        voice_adapter=CallableVoiceAdapter(scripted_offline_voice),
        mode="hybrid",
        seed=23,
    )
    loop = AlphaEvolveLoop(
        mutator=mutator,
        blackboard=bb,
        seed=23,
        offspring_per_gen=3,
    )
    result = loop.evolve(seed_code, cases, generations=2)

    assert result.best_program.score == 1.0
    assert result.best_program.passed_tests == len(cases)
    assert len(result.lineage) >= 2
    assert result.lineage[0].parent_id is None
    assert "@@" in result.lineage[-1].diff_from_parent

    # Verify real EpistemicBlackboard hash chain & Art. II/III separation
    integrity = bb.verify_integrity()
    assert integrity["valid"] is True
    assert integrity["tamper_detected"] is False

    neg_records = [r for r in result.blackboard_records if r.get("record_kind") == "negative_evidence"]
    win_records = [r for r in result.blackboard_records if r.get("record_kind") == "winner_evidence"]
    assert len(neg_records) >= 2
    assert len(win_records) >= 1

    # Negative evidence cannot update belief (CONSTITUTION.md Art. III.2-3)
    neg_ev_id = neg_records[0]["evidence_id"]
    with pytest.raises(FirewallViolationError):
        bb.update_belief([neg_ev_id], "Unsafe mutation should not update belief", 0.1)

    # Passing deterministic evidence can update belief & propose review-required action
    win_ev_id = win_records[-1]["evidence_id"]
    bel = bb.update_belief(
        [win_ev_id],
        "synth_margin passed all 5 deterministic test cases in AST sandbox.",
        posterior_delta=0.35,
        subject="alpha_evolve:synth_margin",
    )
    act = bb.propose_action(bel.record_id, "promote_candidate_program", target="synth_margin", reversible=True)
    assert act.status == "REVIEW_REQUIRED"
    assert act.external_actions == 0
    assert act.autonomous_execution_allowed is False

    # Verify evolutionary rollback restores Gen 0 seed elite cleanly
    assert result.archive.rollback_to_generation(0) is True
    rolled_back_best = result.archive.top_k(1)[0]
    assert rolled_back_best.generation == 0
    assert rolled_back_best.code == seed_code
    assert len(result.archive.rollback_log) == 1

    # Also test default ZoeOfflineVoiceAdapter (no custom voice handler) + real EpistemicBlackboard
    bb2 = EpistemicBlackboard(tmp_path / "blackboard_default_offline")
    loop_default = AlphaEvolveLoop(
        mutator=AntigravityProgramMutator(bridge=ZoeAntigravityBridge(mode="offline"), mode="hybrid", seed=31),
        blackboard=bb2,
        seed=31,
        offspring_per_gen=4,
    )
    res_default = loop_default.evolve("def id_fn(x):\n    return x", [({"x": 2.0}, 2.0)], generations=1)
    assert res_default.best_program.score == 1.0
    assert bb2.verify_integrity()["valid"] is True
    assert any(r.get("record_kind") == "winner_evidence" for r in res_default.blackboard_records)


def test_alpha_evolve_transport_isolation_probe_local_false_and_privacy_sensitive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test matching challenger_m4_r2 Section 5 probes on AlphaEvolve."""
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

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(sb, "LocalOpenAIAgentConfig", _stub_openai)
    monkeypatch.setattr(sb, "LocalAgentConfig", _stub_gemini)

    cases = [({"x": float(x)}, float(x * x)) for x in (-2.0, -1.0, 0.0, 1.0, 2.0)]
    seed_code = "def score_candidate(x):\n    return x"

    # 1. probe_local=False with GEMINI_API_KEY set and 127.0.0.1:8080 ostensibly up
    def _probe_true(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        probe_calls.append(1)
        return {
            "available": True,
            "endpoint": "http://127.0.0.1:8080/v1/models",
            "models": ["qwen"],
            "loopback_only": True,
        }

    monkeypatch.setattr(sb, "probe_local_qwen", _probe_true)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _probe_true)

    mut_no_probe = AntigravityProgramMutator(
        bridge=ZoeAntigravityBridge(mode="auto", state_dir=tmp_path / "no_probe"),
        mode="hybrid",
        probe_local=False,
        seed=42,
    )
    loop_no_probe = AlphaEvolveLoop(
        mutator=mut_no_probe,
        probe_local=False,
        seed=42,
        offspring_per_gen=4,
    )
    res_no_probe = loop_no_probe.evolve(seed_code, cases, generations=2)
    assert res_no_probe.best_program.score >= 0.2
    assert len(probe_calls) == 0
    assert len(openai_calls) == 0

    # 2. privacy_sensitive=True when local_qwen is unavailable (even with bridge_mode="local_qwen" or "gemini")
    probe_calls.clear()
    openai_calls.clear()
    gemini_calls.clear()

    def _probe_false(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        probe_calls.append(1)
        return {
            "available": False,
            "endpoint": "http://127.0.0.1:8080/v1/models",
            "models": [],
            "loopback_only": True,
        }

    monkeypatch.setattr(sb, "probe_local_qwen", _probe_false)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _probe_false)

    mut_private_qwen = AntigravityProgramMutator(
        bridge=ZoeAntigravityBridge(mode="auto", state_dir=tmp_path / "priv_qwen"),
        mode="hybrid",
        privacy_sensitive=True,
        probe_local=True,
        bridge_mode="local_qwen",
        seed=42,
    )
    loop_private_qwen = AlphaEvolveLoop(
        mutator=mut_private_qwen,
        privacy_sensitive=True,
        probe_local=True,
        bridge_mode="local_qwen",
        seed=42,
        offspring_per_gen=4,
    )
    loop_private_qwen.evolve(seed_code, cases, generations=2)
    assert len(openai_calls) == 0
    assert len(gemini_calls) == 0

    # 3. privacy_sensitive=True + bridge(mode="gemini") and offline_only=True never call cloud or probe
    probe_calls.clear()
    openai_calls.clear()
    gemini_calls.clear()
    monkeypatch.setattr(sb, "probe_local_qwen", _probe_true)
    monkeypatch.setattr(stem_layering_mod, "probe_local_qwen", _probe_true)

    loop_private_gem = AlphaEvolveLoop(
        mutator=AntigravityProgramMutator(
            bridge=ZoeAntigravityBridge(mode="gemini", state_dir=tmp_path / "priv_gem"),
            mode="hybrid",
            seed=42,
        ),
        privacy_sensitive=True,
        seed=42,
        offspring_per_gen=3,
    )
    loop_private_gem.evolve(seed_code, cases, generations=2)

    loop_offline = AlphaEvolveLoop(
        mutator=AntigravityProgramMutator(
            bridge=ZoeAntigravityBridge(mode="auto", state_dir=tmp_path / "offline_only"),
            mode="hybrid",
            offline_only=True,
            probe_local=True,
            seed=42,
        ),
        offline_only=True,
        seed=42,
        offspring_per_gen=3,
    )
    loop_offline.evolve(seed_code, cases, generations=2)
    assert len(probe_calls) == 0
    assert len(openai_calls) == 0
    assert len(gemini_calls) == 0

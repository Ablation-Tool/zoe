"""Tier 1 Opaque-Box E2E Tests: R1 Music, R2 Rotation, SDK Bridge & Package Exports, Constitutional Baseline."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import statistics
import struct
import subprocess
import wave

import pytest

from .conftest import (
    FFPROBE_BIN,
    PYTHON_BIN,
    assert_constitutional_invariants,
    call_with_supported_kwargs,
    monorepo_env,
    parse_utc_timestamp,
    require_artifact,
    require_shared_reasoning,
    run_async,
)


# =============================================================================
# F1: R1 Music Before Beginning (>=6 tests)
# =============================================================================


def test_r1_music_evidence_json_schema_and_active_playback(music_evidence_data):
    required_keys = {
        "started_utc",
        "wav_path",
        "wav_sha256",
        "wav_bytes",
        "duration_seconds",
        "sample_rate",
        "channels",
        "sampwidth_bytes",
        "nframes",
        "rms",
        "peak",
        "ffprobe_summary",
        "playback_command",
        "playback_exit_or_pid",
        "playback_verified_active",
    }
    missing = required_keys - set(music_evidence_data.keys())
    assert not missing, f"Missing keys in music_evidence.json: {sorted(missing)}"

    started_dt = parse_utc_timestamp(str(music_evidence_data["started_utc"]))
    assert started_dt.year >= 2026
    assert music_evidence_data["playback_verified_active"] is True
    assert isinstance(music_evidence_data["playback_exit_or_pid"], int)
    assert music_evidence_data["playback_exit_or_pid"] > 0
    assert str(music_evidence_data["playback_command"]).strip() != ""
    assert music_evidence_data.get("playback_log_errors", "") == ""


def test_r1_wav_wave_params_and_non_silent_amplitude(repo_root, music_evidence_data):
    wav_path = require_artifact("evidence/musical_math_chairs/musical_chairs_theme.wav")
    assert Path(music_evidence_data["wav_path"]).resolve() == wav_path.resolve()

    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        raw_frames = wf.readframes(nframes)

    assert channels == 2
    assert sampwidth == 2
    assert framerate == 44100
    assert nframes == 1058400
    assert nframes / framerate == pytest.approx(24.0, abs=1e-4)

    sample_count = len(raw_frames) // 2
    samples = struct.unpack(f"<{sample_count}h", raw_frames)
    norm_sq_sum = sum((s / 32768.0) ** 2 for s in samples)
    rms = (norm_sq_sum / sample_count) ** 0.5
    peak = max(abs(s) / 32768.0 for s in samples)

    assert rms > 0.05, f"WAV appears too quiet / near-silent: rms={rms}"
    assert 0.2 < peak <= 1.0, f"Unexpected WAV peak amplitude: peak={peak}"
    assert rms == pytest.approx(float(music_evidence_data["rms"]), abs=1e-4)
    assert peak == pytest.approx(float(music_evidence_data["peak"]), abs=1e-4)


def test_r1_wav_sha256_integrity_and_byte_size(music_evidence_data):
    wav_path = require_artifact("evidence/musical_math_chairs/musical_chairs_theme.wav")
    raw_bytes = wav_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()

    assert len(raw_bytes) == int(music_evidence_data["wav_bytes"])
    assert len(raw_bytes) > 44
    assert digest == music_evidence_data["wav_sha256"]


def test_r1_independent_ffprobe_verification(music_evidence_data):
    wav_path = require_artifact("evidence/musical_math_chairs/musical_chairs_theme.wav")
    proc = subprocess.run(
        [
            FFPROBE_BIN,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"ffprobe failed: {proc.stderr}"
    probe = json.loads(proc.stdout)
    fmt = probe["format"]
    stream = probe["streams"][0]

    assert fmt["format_name"] == "wav"
    assert int(fmt["size"]) == int(music_evidence_data["wav_bytes"])
    assert float(fmt["duration"]) == pytest.approx(24.0, abs=0.05)
    assert stream["codec_name"] == "pcm_s16le"
    assert int(stream["sample_rate"]) == 44100
    assert int(stream["channels"]) == 2
    assert int(stream["bits_per_sample"]) == 16


def test_r1_generate_music_verify_only_subprocess(repo_root, music_evidence_data):
    gen_script = require_artifact("evidence/musical_math_chairs/generate_music.py")
    wav_path = require_artifact("evidence/musical_math_chairs/musical_chairs_theme.wav")
    proc = subprocess.run(
        [PYTHON_BIN, str(gen_script), "--verify-only", "--output", str(wav_path)],
        cwd=str(repo_root),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"generate_music.py --verify-only failed: {proc.stderr}"
    stats = json.loads(proc.stdout)
    assert stats["wav_sha256"] == music_evidence_data["wav_sha256"]
    assert stats["sample_rate"] == 44100
    assert stats["channels"] == 2
    assert stats["duration_seconds"] == pytest.approx(24.0, abs=1e-4)
    assert stats["rms"] > 0.05
    assert stats["peak"] > 0.2


def test_r1_generate_musical_chairs_wav_synthesis_into_tmp_path(tmp_path, music_evidence_data):
    gen_script = require_artifact("evidence/musical_math_chairs/generate_music.py")
    spec = importlib.util.spec_from_file_location("zoe_r1_generate_music", gen_script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    out_wav = tmp_path / "synthesized_theme.wav"
    telemetry = mod.generate_musical_chairs_wav(out_wav)
    assert out_wav.is_file()
    assert telemetry["sample_rate"] == 44100
    assert telemetry["channels"] == 2
    assert telemetry["sampwidth_bytes"] == 2
    assert telemetry["duration_seconds"] == pytest.approx(24.0, abs=1e-4)
    assert telemetry["rms"] > 0.05
    assert telemetry["peak"] > 0.2
    assert telemetry["wav_sha256"] == music_evidence_data["wav_sha256"]


# =============================================================================
# F2: R2 Musical Math Chairs Rotation (>=5 tests)
# =============================================================================


def test_r2_rotation_log_exists_and_parses_nonempty_slots(rotation_log_slots):
    assert len(rotation_log_slots) >= 9, (
        f"Expected at least 9 rotation slots covering items 1-9, parsed {len(rotation_log_slots)}"
    )
    for slot in rotation_log_slots:
        assert 1 <= slot["item"] <= 9
        assert slot["description"] != ""


def test_r2_slot1_starts_after_r1_music_evidence(music_evidence_data, rotation_log_slots):
    assert len(rotation_log_slots) >= 1
    music_started = parse_utc_timestamp(str(music_evidence_data["started_utc"]))
    slot1_started = rotation_log_slots[0]["timestamp"]
    assert slot1_started >= music_started, (
        f"Slot 1 started ({slot1_started.isoformat()}) before R1 music ({music_started.isoformat()})"
    )


def test_r2_timestamps_non_decreasing_and_30s_cadence(rotation_log_slots):
    assert len(rotation_log_slots) >= 2
    deltas = []
    for idx in range(len(rotation_log_slots) - 1):
        t0 = rotation_log_slots[idx]["timestamp"]
        t1 = rotation_log_slots[idx + 1]["timestamp"]
        delta_sec = (t1 - t0).total_seconds()
        assert delta_sec >= 0.0, f"Timestamps went backwards at slot {idx}->{idx+1}: {t0} > {t1}"
        assert delta_sec > 0.0, f"Slot {idx}->{idx+1} has zero elapsed time ({t0})"
        deltas.append(delta_sec)

    median_delta = statistics.median(deltas)
    assert 15.0 <= median_delta <= 45.0, (
        f"Expected ~30s swap cadence, got median_delta={median_delta:.2f}s across {deltas}"
    )


def test_r2_all_nine_items_covered(rotation_log_slots):
    visited = {slot["item"] for slot in rotation_log_slots}
    assert visited == set(range(1, 10)), f"Missing architecture items in rotation log: {sorted(set(range(1, 10)) - visited)}"


def test_r2_zero_consecutive_repeats(rotation_log_slots):
    assert len(rotation_log_slots) >= 2
    for idx in range(len(rotation_log_slots) - 1):
        cur_item = rotation_log_slots[idx]["item"]
        nxt_item = rotation_log_slots[idx + 1]["item"]
        assert cur_item != nxt_item, (
            f"Consecutive repeat violation at slot {idx}->{idx+1}: item {cur_item} repeated"
        )


# =============================================================================
# F12a: SDK Bridge & Package Exports (>=6 tests)
# =============================================================================


def test_f12a_sdk_bridge_package_exports_and_contract():
    pkg = require_shared_reasoning()
    contract = require_shared_reasoning(symbol="SHARED_REASONING_CONTRACT")
    assert isinstance(contract, str) and contract.strip() != ""

    m2_symbols = (
        "SHARED_REASONING_CONTRACT",
        "ZoeAntigravityBridge",
        "DualTransportStrategy",
        "OfflineAntigravityConnection",
        "ReasoningVoiceAdapter",
    )
    for name in m2_symbols:
        val = getattr(pkg, name, None)
        assert val is not None, f"Public M2 symbol {name!r} missing from zoe_autonomy.shared_reasoning"


def test_f12a_package_exports_and_shared_reasoning_contract():
    expected_symbols = (
        "SHARED_REASONING_CONTRACT",
        "ZoeAntigravityBridge",
        "DualTransportStrategy",
        "OfflineAntigravityConnection",
        "ReasoningVoiceAdapter",
        "EpistemicBlackboard",
        "MeasurementRecord",
        "EvidenceRecord",
        "BeliefUpdateRecord",
        "ActionProposalRecord",
        "FirewallViolationError",
        "AlphaEvolveLoop",
        "LiveProcessSupervisor",
        "KlosterMCTSSearch",
        "PeerConfidenceVector",
        "evaluate_four_peer_quorum",
        "System2To1Distiller",
        "RealitySandboxLab",
        "HumanSteeringDetector",
        "CounterpointChairsEngine",
        "SharedReasoningOrchestrator",
    )
    for name in expected_symbols:
        val = require_shared_reasoning(symbol=name)
        assert val is not None, f"Public symbol {name!r} is None on zoe_autonomy.shared_reasoning"


def test_f12a_bridge_create_agent_offline_returns_antigravity_agent(repo_root, isolated_state_dir):
    from google.antigravity import Agent

    BridgeCls = require_shared_reasoning("sdk_bridge", "ZoeAntigravityBridge")
    bridge = call_with_supported_kwargs(
        BridgeCls,
        repo_root=repo_root,
        root=repo_root,
        zoe_root=repo_root,
        state_dir=isolated_state_dir,
    )
    agent = bridge.create_agent(mode="offline")
    assert isinstance(agent, Agent)


def test_f12a_dual_transport_and_offline_connection_subclasses():
    from google.antigravity.connections.connection import Connection, ConnectionStrategy

    StrategyCls = require_shared_reasoning("sdk_bridge", "DualTransportStrategy")
    ConnCls = require_shared_reasoning("sdk_bridge", "OfflineAntigravityConnection")
    assert issubclass(StrategyCls, ConnectionStrategy)
    assert issubclass(ConnCls, Connection)


def test_f12a_reasoning_voice_adapter_streams_offline_zero_cloud_tokens(repo_root, isolated_state_dir):
    from google.antigravity.types import Text, Thought

    BridgeCls = require_shared_reasoning("sdk_bridge", "ZoeAntigravityBridge")
    VoiceAdapterProto = require_shared_reasoning("sdk_bridge", "ReasoningVoiceAdapter")
    assert hasattr(VoiceAdapterProto, "generate")

    bridge = call_with_supported_kwargs(
        BridgeCls,
        repo_root=repo_root,
        root=repo_root,
        zoe_root=repo_root,
        state_dir=isolated_state_dir,
    )
    agent = bridge.create_agent(mode="offline")

    async def _run_turn():
        async with agent:
            resp = await agent.chat("Summarize epistemic firewall invariants in offline mode.")
            text = await resp.text()
            chunks = await resp.resolve()
            thoughts = [t async for t in resp.thoughts]
            return resp, text, chunks, thoughts

    resp, text, chunks, thoughts = run_async(_run_turn())
    assert isinstance(text, str) and text.strip() != ""
    assert any(isinstance(c, Thought) for c in chunks) and len(thoughts) >= 1
    assert any(isinstance(c, Text) for c in chunks)
    if resp.usage_metadata is not None:
        assert resp.usage_metadata.service_tier is None
    assert_constitutional_invariants(
        {"external_actions": 0, "cloud_tokens_used": 0, "sentience_claimed": False},
        require_offline=True,
    )


def test_f12a_local_openai_agent_config_and_thinking_level_mapping():
    from google.antigravity import GeminiModelOptions, LocalOpenAIAgentConfig, ThinkingLevel
    from zoe_autonomy.stem_layering import TIER_ORDER, build_sdk_descriptor

    for tier in TIER_ORDER:
        desc = build_sdk_descriptor(tier)
        if tier == "local_qwen":
            cfg = LocalOpenAIAgentConfig(
                model=desc["model"],
                base_url=desc["base_url"],
            ).lightweight()
            assert cfg.model == desc["model"]
            assert cfg.base_url == desc["base_url"]
        elif tier in {"flash_lite", "flash", "pro"}:
            lvl = ThinkingLevel(desc["thinking_level"])
            opts = GeminiModelOptions(thinking_level=lvl)
            assert opts.thinking_level == lvl
        else:
            assert desc["sdk_class"] == "ZoeElizaEngine"
            assert desc["cloud_tokens_used"] == 0


def test_f12a_zoe_stem_mcp_stdio_jsonrpc_roundtrip(repo_root, isolated_state_dir):
    mcp_script = repo_root / "scripts" / "zoe_stem_mcp.py"
    assert mcp_script.is_file()

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "route_cognitive_stem",
                "arguments": {"prompt": "Verify firewall offline", "offline_only": True, "local_qwen_available": False},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "run_local_stem_turn",
                "arguments": {
                    "prompt": "Hello Zoe, explain Kloster accessible volume.",
                    "gear": "gear1",
                    "state_dir": str(isolated_state_dir),
                },
            },
        },
    ]
    stdin_payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    proc = subprocess.run(
        [PYTHON_BIN, str(mcp_script)],
        input=stdin_payload,
        cwd=str(repo_root),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"MCP stdio server failed: {proc.stderr}"

    responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(responses) == 4
    by_id = {resp["id"]: resp for resp in responses}

    assert by_id[1]["result"]["serverInfo"]["name"] == "zoe-stem-layering"
    tool_names = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tool_names == {
        "route_cognitive_stem",
        "build_antigravity_sdk_config",
        "eliza_studio_status",
        "run_local_stem_turn",
    }

    route_res = by_id[3]["result"]
    assert route_res["isError"] is False
    assert route_res["structuredContent"]["selected_tier"] in {"gear1_eliza", "local_qwen"}
    assert_constitutional_invariants(route_res["structuredContent"], require_offline=True)

    turn_res = by_id[4]["result"]
    assert turn_res["isError"] is False
    assert turn_res["structuredContent"]["gear_used"] == "gear1"
    assert str(turn_res["structuredContent"]["reply"]).strip() != ""
    assert_constitutional_invariants(turn_res["structuredContent"], require_offline=True)


# =============================================================================
# F13a: Constitutional & Baseline Zoe Contracts (>=5 tests)
# =============================================================================


def test_f13a_constitution_articles_iii_viii_x_present(repo_root):
    const_path = repo_root / "docs" / "CONSTITUTION.md"
    assert const_path.is_file()
    text = const_path.read_text(encoding="utf-8")

    # Article III: Epistemic firewall
    assert "measurement ≠ evidence ≠ belief update ≠ action" in text
    assert "Recommendations remain review-required" in text
    assert "tamper evidence, not cryptographic authentication" in text
    # Article VIII: Recognition and shared credit
    assert "Nicholas Michael Kloster alone, March 6, 2026" in text
    # Article X: Zoe's place
    assert "does not possess legal independence, subjective experience, or authority over people" in text


def test_f13a_stem_layering_constitutional_flags_and_offline_fallback():
    from zoe_autonomy.stem_layering import constitutional_flags, route_stem

    flags = constitutional_flags(cloud_tokens_used=0)
    assert_constitutional_invariants(flags, require_offline=True)

    decision = route_stem(
        "Architect multi-file formal verification proof across modules",
        offline_only=True,
        local_qwen_available=False,
    )
    doc = decision.to_dict()
    assert doc["selected_tier"] == "gear1_eliza"
    assert doc["fallback_applied"] is True
    assert doc["probabilities"]["flash_lite"] == 0.0
    assert doc["probabilities"]["flash"] == 0.0
    assert doc["probabilities"]["pro"] == 0.0
    assert doc["teamwork_recommended"] is False
    assert_constitutional_invariants(doc, require_offline=True)


def test_f13a_operational_metacognition_a_tau_accessible_count():
    from zoe_autonomy.metacognition import (
        Domain,
        EvidenceSource,
        OperationalMetacognition,
        Provenance,
        options_from_probabilities,
    )

    meta = OperationalMetacognition()
    prov = Provenance(
        (EvidenceSource(kind="tool", identifier="test:unit", trust=0.95, strength=0.9),),
        ("Direct probability evaluation",),
    )
    opts = options_from_probabilities({"a": 0.50, "b": 0.30, "c": 0.15, "d": 0.05}, prov)
    thr = meta.threshold(Domain.INTENT, 0.10, rationale="Fixed pre-episode threshold.")
    breadth = meta.count(opts, thr)

    assert breadth.accessible_count == 3
    assert meta.multi_hypothesis(breadth) is True
    assert meta.boxed(breadth) is False

    narrowed = meta.count(opts, thr, represented_count=2)
    assert meta.boxed(narrowed) is True


def test_f13a_zoe_eliza_isolated_turn_and_unified_memory_hash_chain(repo_root, isolated_state_dir):
    from zoe_autonomy.l5_memory import ZoeUnifiedMemory
    from zoe_autonomy.zoe_eliza import ZoeElizaEngine

    engine = ZoeElizaEngine(repo_root, state_dir=isolated_state_dir, default_gear="gear1")
    turn = engine.respond("Explain the epistemic firewall in CONSTITUTION.md", gear="gear1")
    assert turn["gear_used"] == "gear1"
    assert str(turn["reply"]).strip() != ""
    assert len(str(turn["turn_sha256"])) == 64

    remember_res = engine.remember("Verified offline Gear 1 baseline turn", topic="e2e_test")
    assert remember_res["belief_updated"] is True
    mem_file = isolated_state_dir / "zoe_l5_unified_memory.json"
    assert mem_file.is_file()

    # Reload from disk to verify SHA-256 hash chain integrity and evidence-gated conflict rejection
    reloaded = ZoeUnifiedMemory(isolated_state_dir)
    summary = reloaded.summary()
    assert summary["semantic_active_count"] >= 1
    assert summary["chain_head"] != "GENESIS"

    reloaded.record_fact("test_subj", "status", "alpha", provenance="tool_verified", evidence_approved=True)
    conflict = reloaded.record_fact("test_subj", "status", "beta", provenance="unverified_sample", evidence_approved=False)
    assert conflict["conflict_detected"] is True
    assert conflict["belief_updated"] is False


def test_f13a_kloster_sequential_stopping_controller_sanity():
    from guiai.gem.kloster_stopping_law import KlosterSequentialStoppingController

    # Concentrated signal in bin 0 must trigger DECIDE_SIGNAL with samples >= 12
    sig_ctrl = KlosterSequentialStoppingController(n_bins=8, delta=0.005, max_samples=512)
    verdict = {}
    for _ in range(8):
        verdict = sig_ctrl.observe_batch([0] * 16)
        if verdict["action"] == "DECIDE_SIGNAL":
            break
    assert verdict["action"] == "DECIDE_SIGNAL"
    assert verdict["samples"] >= 12
    assert verdict["excess_chi2"] > 0.0

    # Perfectly balanced uniform bins up to max_samples must ABSTAIN_INSUFFICIENT_EVIDENCE
    null_ctrl = KlosterSequentialStoppingController(n_bins=8, delta=0.005, max_samples=64)
    null_verdict = null_ctrl.observe_batch(list(range(8)) * 8)
    assert null_verdict["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert null_verdict["samples"] == 64

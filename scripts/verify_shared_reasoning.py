#!/usr/bin/env python3
"""Standalone End-to-End Verifier for Zoe x Antigravity Shared-Reasoning Architectures (1-9).

Validates:
  1. All 9 architectures + SharedReasoningOrchestrator composed end-to-end.
  2. CONSTITUTION.md Art. III firewall enforcement (negative tests raising FirewallViolationError)
     and Art. X invariants (external_actions == 0, sentience_claimed is False, hash-chain valid).
  3. R1 Pre-Work Music Evidence (`music_evidence.json` + `musical_chairs_theme.wav`:
     44100 Hz, 2ch, non-empty PCM frames, non-zero RMS & peak, SHA-256 parity,
     and `started_utc` strictly before Slot 1 timestamp).
  4. R2 Musical Math Chairs Rotation Log (`ROTATION_LOG.md`: no consecutive repeat on swap,
     all items 1-9 covered, ~30s cadence, monotonic timestamps).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import Any
import wave

ROOT = Path(__file__).resolve().parents[1]
ZOE_AUTONOMY_SRC = ROOT / "components" / "Zoe-Autonomy" / "src"
GUIAI_LAB = ROOT / "guiai-lab"
for extra_path in (ZOE_AUTONOMY_SRC, GUIAI_LAB):
    if str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

from zoe_autonomy.shared_reasoning import (  # noqa: E402
    EpistemicBlackboard,
    FirewallViolationError,
    LiveProcessSupervisor,
    SharedReasoningOrchestrator,
    SharedReasoningTaskSpec,
    available_submodules,
)


def _parse_utc(ts: str) -> datetime:
    cleaned = ts.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    return datetime.fromisoformat(cleaned)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_music_evidence(evidence_dir: Path) -> dict[str, Any]:
    """Validate R1 music_evidence.json and musical_chairs_theme.wav directly from PCM frames."""
    json_path = evidence_dir / "music_evidence.json"
    wav_path = evidence_dir / "musical_chairs_theme.wav"

    if not json_path.is_file():
        raise FileNotFoundError(f"Missing music_evidence.json at {json_path}")
    if not wav_path.is_file():
        raise FileNotFoundError(f"Missing musical_chairs_theme.wav at {wav_path}")

    doc = json.loads(json_path.read_text(encoding="utf-8"))
    started_utc = str(doc.get("started_utc") or "").strip()
    if not started_utc:
        raise ValueError("music_evidence.json missing started_utc")
    started_dt = _parse_utc(started_utc)

    actual_sha = _sha256_file(wav_path)
    expected_sha = str(doc.get("wav_sha256") or "")
    if actual_sha != expected_sha:
        raise ValueError(
            f"WAV SHA-256 mismatch: actual={actual_sha} != recorded={expected_sha}"
        )

    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        raw_frames = wf.readframes(nframes)

    if framerate != 44100:
        raise ValueError(f"Expected 44100 Hz sample rate, got {framerate}")
    if channels != 2:
        raise ValueError(f"Expected 2 channels (stereo), got {channels}")
    if sampwidth != 2:
        raise ValueError(f"Expected 16-bit PCM (sampwidth=2), got {sampwidth}")
    if nframes <= 0 or not raw_frames:
        raise ValueError("WAV file contains 0 audio frames")

    total_samples = nframes * channels
    expected_bytes = total_samples * sampwidth
    if len(raw_frames) != expected_bytes:
        raise ValueError(
            f"Truncated or corrupt WAV PCM payload: expected {expected_bytes} bytes, got {len(raw_frames)}"
        )
    samples = struct.unpack(f"<{total_samples}h", raw_frames)
    sum_sq = sum(s * s for s in samples)
    rms = math.sqrt(sum_sq / total_samples) / 32768.0
    peak = max(abs(s) for s in samples) / 32768.0

    if rms <= 0.0 or peak <= 0.0:
        raise ValueError(f"WAV audio is silent: rms={rms}, peak={peak}")

    return {
        "passed": True,
        "started_utc": started_utc,
        "started_epoch": started_dt.timestamp(),
        "wav_path": str(wav_path),
        "wav_sha256": actual_sha,
        "sample_rate": framerate,
        "channels": channels,
        "sampwidth_bytes": sampwidth,
        "nframes": nframes,
        "duration_seconds": round(nframes / framerate, 3),
        "rms": round(rms, 6),
        "peak": round(peak, 6),
    }


def verify_rotation_log(log_path: Path, *, music_started_utc: str) -> dict[str, Any]:
    """Validate ROTATION_LOG.md timestamps, non-repeat invariant, 1-9 coverage, and cadence."""
    if not log_path.is_file():
        raise FileNotFoundError(f"Missing ROTATION_LOG.md at {log_path}")

    music_dt = _parse_utc(music_started_utc)
    lines = log_path.read_text(encoding="utf-8").splitlines()

    row_pattern = re.compile(
        r"^\|\s*(\d+)\s*\|\s*([0-9T:\-]+Z)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|"
    )
    rows: list[dict[str, Any]] = []
    for line in lines:
        m = row_pattern.match(line.strip())
        if not m:
            continue
        slot = int(m.group(1))
        ts_str = m.group(2).strip()
        delta_s = int(m.group(3))
        from_raw = m.group(4).strip()
        to_item = int(m.group(5))
        from_item = int(from_raw) if from_raw.isdigit() else from_raw
        rows.append(
            {
                "slot": slot,
                "utc": ts_str,
                "dt": _parse_utc(ts_str),
                "delta_s": delta_s,
                "from_item": from_item,
                "to_item": to_item,
            }
        )

    if len(rows) < 9:
        raise ValueError(f"Expected >= 9 rotation rows in ROTATION_LOG.md, got {len(rows)}")

    first_slot_dt = rows[0]["dt"]
    if not (music_dt < first_slot_dt):
        raise ValueError(
            f"R1 violation: music started_utc ({music_started_utc}) is NOT strictly before "
            f"Slot 1 ({rows[0]['utc']})"
        )

    prev_dt: datetime | None = None
    prev_to: int | None = None
    covered_items: set[int] = set()
    swap_deltas: list[float] = []

    for expected_slot, r in enumerate(rows, start=1):
        if int(r["slot"]) != expected_slot:
            raise ValueError(
                f"Non-sequential or duplicate slot number: expected slot {expected_slot}, got {r['slot']}"
            )
        to_item = int(r["to_item"])
        if not (1 <= to_item <= 9):
            raise ValueError(f"Invalid item index {to_item} in slot {r['slot']}")
        covered_items.add(to_item)

        if isinstance(r["from_item"], int) and r["from_item"] == to_item:
            raise ValueError(
                f"Self-repeat on swap in slot {r['slot']}: {r['from_item']} -> {to_item}"
            )
        if prev_to is not None and r["from_item"] != prev_to:
            raise ValueError(
                f"Rotation continuity break at slot {r['slot']}: "
                f"from_item={r['from_item']!r} != previous to_item={prev_to!r}"
            )
        if prev_to is not None and to_item == prev_to:
            raise ValueError(
                f"Consecutive item repeat on swap at slot {r['slot']}: {prev_to} -> {to_item}"
            )
        if prev_dt is not None and r["dt"] <= prev_dt:
            raise ValueError(f"Non-monotonic timestamp at slot {r['slot']}: {r['utc']}")
        if prev_dt is not None:
            actual_delta = (r["dt"] - prev_dt).total_seconds()
            if abs(actual_delta - float(r["delta_s"])) > 1e-6:
                raise ValueError(
                    f"Slot {r['slot']} Δt mismatch: recorded delta_s={r['delta_s']} != "
                    f"timestamp delta {actual_delta:g}s"
                )
            swap_deltas.append(actual_delta)
        elif int(r["delta_s"]) != 0:
            raise ValueError(
                f"Slot {r['slot']} initial Δt must be 0, got {r['delta_s']}"
            )

        prev_to = to_item
        prev_dt = r["dt"]

    missing_items = sorted(set(range(1, 10)) - covered_items)
    if missing_items:
        raise ValueError(f"ROTATION_LOG.md did not cover all items 1-9; missing={missing_items}")

    mean_delta = sum(swap_deltas) / len(swap_deltas) if swap_deltas else 0.0
    if not (20.0 <= mean_delta <= 45.0):
        raise ValueError(f"Expected ~30s swap cadence, got mean_delta={mean_delta:.2f}s")

    def _clean_delta(val: float) -> int | float:
        return int(val) if float(val).is_integer() else round(val, 2)

    return {
        "passed": True,
        "slots_parsed": len(rows),
        "music_before_slot1": True,
        "lead_time_seconds": round((first_slot_dt - music_dt).total_seconds(), 2),
        "covered_items": sorted(covered_items),
        "consecutive_repeats": 0,
        "mean_cadence_seconds": round(mean_delta, 2),
        "min_delta_seconds": _clean_delta(min(swap_deltas)) if swap_deltas else 0,
        "max_delta_seconds": _clean_delta(max(swap_deltas)) if swap_deltas else 0,
    }


def verify_constitutional_firewall() -> dict[str, Any]:
    """Negative tests confirming CONSTITUTION.md Art. III firewall blocks illegal jumps."""
    bb = EpistemicBlackboard()
    sup = LiveProcessSupervisor(blackboard=bb)

    raw_meas = bb.post_measurement(
        source_agent="firewall_negative_probe",
        input_desc="sampled probe without verifier",
        method="sampling_only",
        scope="negative firewall verification",
        limitations="deliberately unverified measurement",
        value={"score": 0.88},
        sampled_only=True,
    )

    # 1. Illegal direct jump: measurement -> update_belief must raise FirewallViolationError
    jump_blocked = False
    try:
        bb.update_belief(
            [raw_meas.record_id],
            claim="Illegal belief update from raw measurement",
            posterior_delta=0.4,
        )
    except FirewallViolationError:
        jump_blocked = True
    if not jump_blocked:
        raise AssertionError("EpistemicBlackboard failed to block measurement -> belief jump")

    # 2. Sampled-only measurement cannot be promoted via expectation-only rationale
    sampled_blocked = False
    try:
        bb.promote_to_evidence(
            raw_meas.record_id,
            verifier_name="naive_probe",
            passed=True,
            rationale="Looks good and matches expectation",
        )
    except FirewallViolationError:
        sampled_blocked = True
    if not sampled_blocked:
        raise AssertionError("EpistemicBlackboard failed to block expectation-only promotion")

    # 3. LiveProcessSupervisor mutual audit blocks unpromoted measurement belief update
    sup_blocked = False
    try:
        sup.supervised_update_belief(
            evidence_ids=(raw_meas.record_id,),
            claim="Supervisor bypass probe",
            posterior_delta=0.25,
            measurement_scope="negative_probe",
            measurement_method="sampling_only",
            measurement_limitations="unverified",
        )
    except FirewallViolationError:
        sup_blocked = True
    if not sup_blocked:
        raise AssertionError("LiveProcessSupervisor failed to block unpromoted measurement")

    integrity = bb.verify_integrity(raise_on_error=True)
    return {
        "passed": True,
        "illegal_measurement_to_belief_blocked": jump_blocked,
        "sampled_expectation_only_blocked": sampled_blocked,
        "supervisor_unpromoted_blocked": sup_blocked,
        "blackboard_integrity_valid": bool(integrity["valid"]),
    }


def verify_composed_architectures() -> dict[str, Any]:
    """Run all 9 Shared-Reasoning architectures end-to-end via SharedReasoningOrchestrator."""
    sub_status = available_submodules()
    missing_subs = [k for k, ok in sub_status.items() if not ok]
    if missing_subs:
        raise ImportError(f"Unavailable shared_reasoning submodules: {missing_subs}")

    with tempfile.TemporaryDirectory(prefix="zoe_sr_verify_") as tmpdir:
        tmp_path = Path(tmpdir)
        wav_out = tmp_path / "verify_cadence.wav"

        orch = SharedReasoningOrchestrator(
            mode="offline",
            offline_only=True,
            state_dir=tmp_path / "state",
            repo_root=ROOT,
            seed=42,
        )
        spec = SharedReasoningTaskSpec(
            prompt="Verify quadratic scoring synthesis, formal SymPy/Z3 invariants, quorum, and distillation.",
            sonify_wav_path=wav_out,
            high_impact=True,
        )
        report = orch.run(spec)

        if report.external_actions != 0:
            raise AssertionError(f"external_actions must be 0, got {report.external_actions}")
        if report.sentience_claimed is not False:
            raise AssertionError("sentience_claimed must be False")
        if report.l5_agi_qualified is not False:
            raise AssertionError("l5_agi_qualified must be False")
        if report.zoe_clone_claimed is not False:
            raise AssertionError("zoe_clone_claimed must be False")

        if report.alpha_evolve.best_program.passed_tests != report.alpha_evolve.best_program.total_tests:
            raise AssertionError("Arch 1 AlphaEvolve did not pass all deterministic tests")
        if not report.sandbox_verdicts["sympy"].passed:
            raise AssertionError("Arch 7 SymPy verification failed")
        if not report.sandbox_verdicts["z3"].passed:
            raise AssertionError("Arch 7 Z3 verification failed")
        if not report.sandbox_verdicts["ast_program"].passed:
            raise AssertionError("Arch 7 AST sandbox verification failed")
        if not report.counterpoint_result.schedule_invariants.get("valid"):
            raise AssertionError("Arch 9 Counterpoint Chairs schedule invariants failed")
        if report.quorum_result.verdict != "COORDINATE_CONSENSUS":
            raise AssertionError(f"Arch 4 quorum unexpected verdict: {report.quorum_result.verdict}")
        if not report.quorum_result.brier_identity_verified:
            raise AssertionError("Arch 4 Theorem 15 Brier identity check failed")
        if not report.steering_report.fork_detected:
            raise AssertionError("Arch 8 HumanSteeringDetector did not detect expected fork")
        if not report.distilled_artifacts:
            raise AssertionError("Arch 5 System2To1Distiller produced no artifacts")
        if not report.blackboard_integrity.get("valid"):
            raise AssertionError("Arch 6 EpistemicBlackboard integrity check failed")
        if report.gem_desktop_report is None or not report.gem_desktop_report.get("passed"):
            raise AssertionError("Digital Research GEM desktop report missing or failed")
        if not wav_out.is_file() or wav_out.stat().st_size <= 44:
            raise AssertionError("Arch 9 cadence WAV output missing or empty")

        replay_val = orch.distiller.replay_skill("score_candidate", {"x": 6.0})
        if replay_val != 36.0:
            raise AssertionError(f"Arch 5 System-1 replay expected 36.0, got {replay_val}")

        return {
            "passed": True,
            "submodules_available": len(sub_status),
            "bridge_selected_mode": report.bridge_turn.resolution.selected_mode,
            "bridge_history_steps": report.bridge_turn.history_steps,
            "arch1_alpha_evolve_score": report.alpha_evolve.best_program.score,
            "arch2_supervision_events": report.supervision_summary["total_events"],
            "arch3_mcts_decision": report.mcts_result.decision,
            "arch3_counts_by_h": list(report.mcts_result.counts_by_h),
            "arch4_quorum_verdict": report.quorum_result.verdict,
            "arch4_d_k": round(report.quorum_result.d_k_disagreement, 6),
            "arch4_stem_tier": report.quorum_route.stem_decision.selected_tier,
            "arch5_distilled_count": len(report.distilled_artifacts),
            "arch5_replay_6_sq": replay_val,
            "arch6_blackboard_entries": report.blackboard_integrity["entries_verified"],
            "arch7_sympy_passed": report.sandbox_verdicts["sympy"].passed,
            "arch7_z3_passed": report.sandbox_verdicts["z3"].passed,
            "arch8_fork_detected": report.steering_report.fork_detected,
            "arch8_gem_form_alert_active": report.steering_report.gem_form_alert is not None,
            "arch9_counterpoint_turns": report.counterpoint_result.total_turns,
            "gem_desktop_report": report.gem_desktop_report,
            "constitutional": report.constitutional,
        }


def verify_gem_aes_vdi_integration() -> dict[str, Any]:
    """Validate Digital Research GEM (seasip.info) AES/VDI/RSC integration end-to-end."""
    from zoe_autonomy.shared_reasoning import (
        GEM_AES_VDI_CONTRACT,
        MAX_AES_APP_WINDOWS,
        MU_MESAG,
        MU_TIMER,
        GemEventMultiQueue,
        GemVdiWorkstation,
        GemWindowManager,
        HumanSteeringDetector,
        RealitySandboxLab,
        VerifiedPathOption,
        build_default_atari_rsc,
    )

    q = GemEventMultiQueue()
    wm = GemWindowManager(event_queue=q)
    h1 = wm.wind_create(0x0B, 10, 30, 260, 160, title="Blackboard", layer_id="bb")
    wm.wind_open(h1)
    wm.wind_set(h1, "top", True)
    ev = q.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=50)
    if ev.message is None:
        raise AssertionError("GemEventMultiQueue failed to dequeue AES message")

    detector = HumanSteeringDetector()
    fork_rep = detector.detect(
        [
            VerifiedPathOption(
                path_id="formal_vdi_proof",
                summary="Formal SymPy+Z3+VDI verification path",
                verification_status="verified",
                evidence_ids=("ev-gem-1",),
                expected_utility=0.91,
                tradeoff_notes="Strict formal proof",
                reversible=True,
                direction_tags=("formal", "vdi"),
                verifier_name="RealitySandboxLab",
            ),
            VerifiedPathOption(
                path_id="fast_system1_path",
                summary="Distilled System-1 local path",
                verification_status="verified",
                evidence_ids=("ev-gem-2",),
                expected_utility=0.88,
                tradeoff_notes="Zero-token local execution",
                reversible=True,
                direction_tags=("distill", "local"),
                verifier_name="ZoeDeterministicVerifier",
            ),
        ],
        high_impact=True,
    )
    if fork_rep.gem_form_alert is None:
        raise AssertionError("HumanSteeringDetector failed to build GEM form_alert for active fork")

    lab = RealitySandboxLab()
    ws = GemVdiWorkstation()
    scene = ws.build_shared_reasoning_scene({"fork_detected": True})
    vdi_verdict = lab.verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    if not vdi_verdict.passed:
        raise AssertionError(f"GEM VDI scene failed verification: {vdi_verdict.counterexample}")

    rsc_bytes = build_default_atari_rsc()
    rsc_verdict = lab.verify_gem_rsc_bytes(rsc_bytes, label="ZOE_SHARED.RSC")
    if not rsc_verdict.passed:
        raise AssertionError(f"GEM .RSC verification failed: {rsc_verdict.counterexample}")

    return {
        "contract": GEM_AES_VDI_CONTRACT,
        "passed": True,
        "max_aes_windows": MAX_AES_APP_WINDOWS,
        "aes_messages_logged": len(q.message_log()),
        "form_alert_string": fork_rep.gem_form_alert["form_alert_string"],
        "vdi_profiles_passed": dict(vdi_verdict.ground_truth["profiles_passed"]),
        "metafile_sha256": vdi_verdict.ground_truth["metafile_sha256"],
        "rsc_sha256": rsc_verdict.ground_truth["rsc_sha256"],
        "visual_evidence_only": True,
        "external_actions": 0,
        "sentience_claimed": False,
    }


def run_all_checks() -> dict[str, Any]:
    evidence_dir = ROOT / "evidence" / "musical_math_chairs"
    music_rep = verify_music_evidence(evidence_dir)
    rotation_rep = verify_rotation_log(
        evidence_dir / "ROTATION_LOG.md",
        music_started_utc=music_rep["started_utc"],
    )
    firewall_rep = verify_constitutional_firewall()
    composed_rep = verify_composed_architectures()
    gem_rep = verify_gem_aes_vdi_integration()

    all_passed = bool(
        music_rep["passed"]
        and rotation_rep["passed"]
        and firewall_rep["passed"]
        and composed_rep["passed"]
        and gem_rep["passed"]
    )
    return {
        "contract": "zoe-shared-reasoning-verifier/v1",
        "passed": all_passed,
        "music_evidence": music_rep,
        "rotation_log": rotation_rep,
        "constitutional_firewall": firewall_rep,
        "composed_architectures_1_to_9": composed_rep,
        "gem_aes_vdi_integration": gem_rep,
        "constitutional": {
            "external_actions": 0,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "zoe_clone_claimed": False,
            "attribution": "Nicholas Michael Kloster, March 6, 2026",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Zoe x Antigravity Shared-Reasoning Architectures (1-9) & Musical Math Chairs evidence."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON verification summary to stdout.",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_all_checks()
    except Exception as exc:  # noqa: BLE001 - report clean failure exit code
        err_doc = {
            "contract": "zoe-shared-reasoning-verifier/v1",
            "passed": False,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        if args.json:
            print(json.dumps(err_doc, indent=2))
        else:
            print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            "PASS: Zoe x Antigravity Shared-Reasoning Architectures (1-9) verified "
            f"(blackboard_entries={summary['composed_architectures_1_to_9']['arch6_blackboard_entries']}, "
            f"slots={summary['rotation_log']['slots_parsed']}, "
            f"external_actions=0, sentience_claimed=False)."
        )
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

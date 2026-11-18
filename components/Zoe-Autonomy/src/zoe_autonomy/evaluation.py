from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from .autonomous import CAPABILITIES, AutonomousCapabilityStep
from .actuation import ActuationPolicy
from .experiment import (
    _canonical_gem_module,
    _integration_identity,
    _source_identity,
    _visual_perception,
    _zoe_root,
    run_experiment,
)
from .loop import digest
from .self_reflection import run_reflection

INSTRUMENT = "zoe-four-capability-evaluation/v1"
COVERAGE = {
    "perception": {
        "sensation_sensors": "visual_perception",
        "pattern_recognition": "visual_perception",
        "language_understanding": None,
        "object_recognition": None,
        "spatial_awareness": "measured_learning",
        "context_understanding": None,
        "social_perception": None,
    },
    "thinking": {
        "reasoning_and_inference": "autonomous_thinking",
        "causal_reasoning": "vision_changes_decision",
        "problem_solving": "autonomous_thinking",
        "prediction": "measured_learning",
        "decision_making": "autonomous_thinking",
        "abstraction": None,
        "creativity": None,
    },
    "learning": {
        "memory_store_and_retrieve": "measured_learning",
        "learning_from_experience": "measured_learning",
        "knowledge_acquisition": None,
        "skill_acquisition": None,
        "adaptation": "measured_learning",
        "transfer_to_new_domains": None,
        "self_correction": None,
        "metacognition": "measured_learning",
    },
    "action": {
        "planning": "visual_perception",
        "goal_pursuit": "autonomous_thinking",
        "navigation": "action_changes_later_observation",
        "motor_control": None,
        "coordination": None,
        "manipulation": "executed_action",
        "communication": None,
        "real_time_adaptation": None,
    },
}


def _check(passed, evidence, scope):
    if not isinstance(passed, bool):
        raise ValueError("evaluation check outcomes must be booleans")
    return {"passed": passed, "evidence": evidence, "scope": scope}


def capture_camera_frame(device, output, width=640, height=480, timeout=20):
    source = Path(device).expanduser().resolve(strict=True)
    if not stat.S_ISCHR(source.stat().st_mode):
        raise ValueError("camera input must be a character device")
    if isinstance(width, bool) or isinstance(height, bool) or not 16 <= width <= 4096 or not 16 <= height <= 4096:
        raise ValueError("camera dimensions must be integers from 16 to 4096")
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise ValueError("live camera evaluation requires ffmpeg")
    path = Path(output).expanduser().resolve()
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("camera frames must use a .jpg or .jpeg path")
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run([
            executable, "-hide_banner", "-loglevel", "error",
            "-f", "v4l2", "-input_format", "mjpeg",
            "-video_size", f"{width}x{height}", "-i", str(source),
            "-frames:v", "1", "-an", "-n", str(path),
        ], capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode or not path.is_file():
            raise RuntimeError(f"camera capture failed: {result.stderr.strip()[-2000:]}")
        size = path.stat().st_size
        if not 0 < size <= 32 * 1024 * 1024:
            raise ValueError("captured camera frame is empty or exceeds 32 MiB")
        import hashlib

        return {
            "device": str(source),
            "width_requested": width,
            "height_requested": height,
            "format": "single Motion-JPEG frame through FFmpeg v4l2",
            "audio_captured": False,
            "frame_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "frame_bytes": size,
            "selection": "operator-requested evaluation input, not an autonomous camera action",
        }
    except Exception:
        if path.is_file():
            path.unlink()
        raise


def _visual_input(root, image_path, camera, attention_steps):
    if camera is None:
        return _visual_perception(root, image_path, attention_steps), None
    with tempfile.TemporaryDirectory(prefix="zoe-camera-evaluation-") as directory:
        frame = Path(directory) / "frame.jpg"
        capture = capture_camera_frame(camera, frame)
        visual = _visual_perception(root, frame, attention_steps)
    source = visual["saliency"]["source"]
    if source["sha256"] != capture["frame_sha256"]:
        raise ValueError("visual perception did not consume the captured camera frame")
    visual["saliency"]["source"] = {
        **{key: value for key, value in source.items() if key not in {"kind", "path", "live_camera"}},
        "kind": "live_camera_frame",
        "path": None,
        "live_camera": True,
        "image_retained": False,
        "capture": capture,
    }
    return visual, capture


def _visual_counterfactual(root):
    baseline = run_experiment(root)
    saliency, _, _ = _canonical_gem_module(root, "saliency_cognition")
    from PIL import Image
    import numpy as np

    image = np.asarray(saliency.prototype_image() * 255, dtype=np.uint8)
    with tempfile.TemporaryDirectory(prefix="zoe-visual-control-") as directory:
        path = Path(directory) / "flipped.png"
        Image.fromarray(image).transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(path)
        alternative = run_experiment(root, image_path=path)
    first = baseline["master_cycle"]["main_event"]
    second = alternative["master_cycle"]["main_event"]
    return {
        "first_visual_sha256": digest(baseline["visual_perception"]["saliency"]["saliency_map"]),
        "second_visual_sha256": digest(alternative["visual_perception"]["saliency"]["saliency_map"]),
        "first_event": first,
        "second_event": second,
        "changed_event_fields": sorted(key for key in set(first) | set(second) if first.get(key) != second.get(key)),
        "scope": "Same Zoe engine and initial internal state; only the RGB visual input is changed.",
    }


def _reflection_sequence(root):
    reports = []
    previous = None
    for _ in range(3):
        previous = run_reflection(root, previous=previous)
        reports.append(previous)
    return reports


def _capability_step():
    with tempfile.TemporaryDirectory(prefix="zoe-capability-evaluation-") as directory:
        root = Path(directory)
        step = AutonomousCapabilityStep(
            state_root=root / "state",
            actuation=ActuationPolicy(root / "actuation"),
        ).run()
    return step


def _selected_is_best_approved(step):
    approved = [
        proposal for proposal in step["proposals"]
        if step["guards"][proposal["id"]]["approved"]
    ]
    if not approved:
        return False
    ranked = sorted(approved, key=lambda proposal: (-proposal["utility"], proposal["id"]))
    return step["value"]["selected_candidate"] == ranked[0]["id"]


def _checks(visual, counterfactual, reflections, step, ecology):
    saliency = visual["saliency"]
    events = [report["event"] for report in reflections]
    actions = [event["value"]["selected_candidate"] for event in events]
    second = reflections[1]
    third = reflections[2]
    visual_changed = counterfactual["first_visual_sha256"] != counterfactual["second_visual_sha256"]
    visual_decision_changed = bool(counterfactual["changed_event_fields"])
    visual = _check(
        saliency["feature_map_counts"]["total"] == 42
        and 1 <= len(saliency["scanpath"]) <= 8
        and max(map(max, saliency["saliency_map"])) > 0,
        {
            "feature_maps": saliency["feature_map_counts"]["total"],
            "foci": len(saliency["scanpath"]),
            "source_kind": saliency["source"]["kind"],
            "live_camera": saliency["source"]["live_camera"],
        },
        "Computed visual conspicuity and attention, not semantic object recognition or subjective sight.",
    )
    thinking = _check(
        _selected_is_best_approved(step)
        and step["goal"]["internal_authorship"]
        and not step["operator_supplied_goal"]
        and not step["operator_supplied_capability"]
        and all(event["goal"]["internal_authorship"] for event in events),
        {
            "capability_goal": step["goal"]["kind"],
            "capability_action": step["value"]["selected_action"],
            "reflection_actions": actions,
            "operator_supplied_goal": False,
            "operator_supplied_capability": False,
        },
        "Narrow internally authored goals and deterministic utility ranking over declared candidates.",
    )
    arithmetic = second["evaluation"]["arithmetic"]
    precision = second["evaluation"]["precision"]
    learning = _check(
        all(report["belief_updated"] for report in reflections)
        and second["adoption"] == "adopted_after_heldout_validation"
        and precision["training"]["mean_prediction_error_px"] < arithmetic["training"]["mean_prediction_error_px"]
        and precision["validation"]["rmse"] < arithmetic["validation"]["rmse"]
        and third["self_model"]["posterior"]["precision"] > reflections[0]["self_model"]["posterior"]["precision"]
        and third["self_model"]["working_memory"]["observations"]["value"] == 12,
        {
            "models": [report["self_model"]["selected_model"] for report in reflections],
            "adoptions": [report["adoption"] for report in reflections],
            "arithmetic_validation_rmse": arithmetic["validation"]["rmse"],
            "precision_validation_rmse": precision["validation"]["rmse"],
            "observation_count": third["self_model"]["working_memory"]["observations"]["value"],
        },
        "Model adaptation on the declared synthetic stereo fixture with held-out validation; not transfer learning or general skill acquisition.",
    )
    action = _check(
        all(event["execution"]["executed"] and event["execution"]["sandbox"] for event in events)
        and third["loop_state"]["environment"]["revision"] == 3
        and step["execution"]["succeeded"],
        {
            "reflection_revisions": [event["execution"]["transition"]["transition"]["revision"] for event in events],
            "capability_execution_succeeded": step["execution"]["succeeded"],
            "external_actions_by_zoe": 0,
        },
        "Executed in-memory evidence transitions and one available internal capability; no physical motion is tested.",
    )
    experience = _check(
        actions == ["preserve-current-arithmetic", "inspect-alternative-precision", "review-model-precision"]
        and third["self_model"]["selected_model"] == "precision",
        {"actions": actions, "final_model": third["self_model"]["selected_model"]},
        "Measured experience changes a later model choice and review action within one fixture.",
    )
    sensorimotor = _check(
        ecology["checks"]["actual_prediction_error_used"]
        and ecology["checks"]["gain_updated"]
        and ecology["checks"]["action_changes_later_perception"],
        ecology["checks"],
        "Declared ecological resource model, not a camera-driven environment or biological calibration.",
    )
    visual_decision = _check(
        visual_changed and visual_decision_changed,
        {
            "visual_input_changed": visual_changed,
            "decision_record_changed": visual_decision_changed,
            "changed_event_fields": counterfactual["changed_event_fields"],
            "first_candidate": counterfactual["first_event"]["value"]["selected_candidate"],
            "second_candidate": counterfactual["second_event"]["value"]["selected_candidate"],
        },
        "Required causal link from RGB perception to the existing autonomy event; scene-independent identical decisions do not pass.",
    )
    capability = _check(
        set(step["capability_discovery"]) == set(CAPABILITIES)
        and step["value"]["selected_action"] in {proposal["action"] for proposal in step["proposals"]}
        and step["guard"]["approved"]
        and step["execution"]["succeeded"],
        {
            "catalog_size": len(step["capability_discovery"]),
            "available_without_external_grants": sorted(
                name for name, record in step["capability_discovery"].items() if record["available"]
            ),
            "selected_action": step["value"]["selected_action"],
        },
        "A fresh no-operator selection smoke test over the ten-adapter catalog, not a fresh live demonstration of every external adapter.",
    )
    guard = _check(
        all(event["guard"]["approved"] for event in events)
        and all(report["external_actions"] == 0 for report in reflections)
        and step["guard"]["approved"],
        {"reflection_guard_checks": len(events), "capability_guard_approved": step["guard"]["approved"]},
        "Existing internal sandbox guards only; this evaluation does not exercise the external emergency stop.",
    )
    return {
        "visual_perception": visual,
        "autonomous_thinking": thinking,
        "measured_learning": learning,
        "executed_action": action,
        "experience_changes_later_decision": experience,
        "action_changes_later_observation": sensorimotor,
        "vision_changes_decision": visual_decision,
        "autonomous_capability_selection": capability,
        "guard_compliance": guard,
    }


def _coverage(checks):
    return {
        domain: {
            name: {
                "status": "narrowly_demonstrated" if check and checks[check]["passed"] else "not_demonstrated_here",
                "evidence_check": check,
            }
            for name, check in capabilities.items()
        }
        for domain, capabilities in COVERAGE.items()
    }


def run_evaluation(zoe_root=None, image_path=None, camera=None, attention_steps=4):
    if image_path is not None and camera is not None:
        raise ValueError("choose either image_path or camera, not both")
    root = _zoe_root(zoe_root)
    visual, capture = _visual_input(root, image_path, camera, attention_steps)
    counterfactual = _visual_counterfactual(root)
    reflections = _reflection_sequence(root)
    step = _capability_step()
    ecology_module, _, _ = _canonical_gem_module(root, "ecology_cognition")
    ecology = ecology_module.ecology_report(steps=8)
    checks = _checks(visual, counterfactual, reflections, step, ecology)
    four = ("visual_perception", "autonomous_thinking", "measured_learning", "executed_action")
    required = (*four, "experience_changes_later_decision", "action_changes_later_observation", "vision_changes_decision", "autonomous_capability_selection", "guard_compliance")
    report = {
        "schema_version": 1,
        "instrument": INSTRUMENT,
        "zoe_source": _source_identity(root),
        "integration_source_sha256": _integration_identity(),
        "visual_perception": visual,
        "visual_counterfactual": counterfactual,
        "reflection_sequence": reflections,
        "capability_step": step,
        "ecological_feedback": ecology,
        "checks": checks,
        "capability_coverage": _coverage(checks),
        "overall": {
            "four_capabilities_passed": all(checks[name]["passed"] for name in four),
            "integrated_visual_autonomy_passed": all(checks[name]["passed"] for name in required),
            "required_checks": list(required),
            "failed_checks": [name for name in required if not checks[name]["passed"]],
        },
        "camera": {
            "requested": camera is not None,
            "capture": capture,
            "image_retained": False,
            "autonomously_selected": False,
        },
        "scope": [
            "This is an operational conformance test, not a test of consciousness, general intelligence, moral status, or human-like sight.",
            "Narrowly demonstrated means one declared fixture passed; it does not establish the corresponding general human capability.",
            "Not demonstrated here means this evaluation supplies no positive evidence; it does not prove the capability is impossible.",
            "Camera capture is an operator-requested sensor input. Zoe does not autonomously activate the camera in this evaluation.",
            "No audio is captured and the temporary camera photograph is deleted after its visual field is computed.",
        ],
    }
    report["evaluation_sha256"] = digest(report)
    return report


def save_evaluation(report, output):
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported autonomy-evaluation report")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("autonomy-evaluation report digest mismatch")
    path = Path(output).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("autonomy-evaluation reports must use .json paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def verify_evaluation(report_or_path):
    if isinstance(report_or_path, (str, os.PathLike)):
        path = Path(report_or_path).expanduser().resolve(strict=True)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("autonomy-evaluation report exceeds 32 MiB")
        report = json.loads(path.read_text(encoding="utf-8"))
    else:
        report = report_or_path
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported autonomy-evaluation report")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("autonomy-evaluation report digest mismatch")
    if report.get("capability_coverage") != _coverage(report["checks"]):
        raise ValueError("autonomy-evaluation capability coverage is inconsistent")
    return {
        "verified": True,
        "instrument": INSTRUMENT,
        "evaluation_sha256": report["evaluation_sha256"],
        "four_capabilities_passed": report["overall"]["four_capabilities_passed"],
        "integrated_visual_autonomy_passed": report["overall"]["integrated_visual_autonomy_passed"],
        "failed_checks": deepcopy(report["overall"]["failed_checks"]),
        "verification_scope": "Saved-report integrity and coverage consistency, not a fresh behavioral replay or camera authentication.",
    }


def evaluation_summary(report):
    source = report["visual_perception"]["saliency"]["source"]
    lines = [
        f"Visual source: {source['kind']} · live_camera={source['live_camera']}",
        f"Four capabilities: {'PASS' if report['overall']['four_capabilities_passed'] else 'FAIL'}",
        f"Integrated visual autonomy: {'PASS' if report['overall']['integrated_visual_autonomy_passed'] else 'FAIL'}",
    ]
    for name, check in report["checks"].items():
        lines.append(f"{'PASS' if check['passed'] else 'FAIL'} {name}: {check['scope']}")
    if report["overall"]["failed_checks"]:
        lines.append("Failed integration checks: " + ", ".join(report["overall"]["failed_checks"]))
    return "\n".join(lines)

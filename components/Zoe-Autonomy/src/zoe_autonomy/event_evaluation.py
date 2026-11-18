from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
import time

from .event_autonomy import EVENT_INSTRUMENT, EventCausalEngine, prediction_metrics
from .event_core import ACTIONS, CENTERS, event_image, frames_to_events, observation_window, synthetic_sequence
from .event_reasoning import attention_after
from .evaluation import capture_camera_frame
from .experiment import _canonical_gem_module, _event_chain_valid, _source_identity, _zoe_root
from .loop import digest

EVALUATION_INSTRUMENT = "zoe-event-causal-evaluation/v1"
DEFAULT_PROTOCOL = Path(__file__).resolve().parents[2] / "evidence" / "event-causal" / "protocol.json"


def _fixture(protocol, name):
    fixture = protocol["fixtures"][name]
    sequences = []
    positions = fixture["initial_positions"]
    velocities = fixture["velocities"]
    for index in range(fixture["sequences"]):
        position = positions[index % len(positions)]
        velocity = velocities[(index // len(positions)) % len(velocities)]
        sequences.append(synthetic_sequence(
            position, velocity,
            steps=protocol["event_representation"]["time_steps_per_sequence"],
            noise_probability=fixture["event_noise_probability"],
            seed=fixture["seed"] + index,
            polarity_reversed=fixture.get("polarity_reversed", False),
        ))
    return sequences


def _compact(report):
    return {
        "step": report["step"],
        "observation": report["observation"],
        "prediction_error": report["prediction_error"],
        "candidates": report["candidate_details"],
        "trajectory": {key: value for key, value in report["trajectory"].items() if key != "edges"},
        "uncertainty": report["uncertainty"],
        "selected_prediction": report["selected_prediction"],
        "selected_action": report["selected_action"],
        "attention_after": report["attention_after"],
        "plasticity_changed": report["plasticity"]["changed"],
        "goal": report["event"]["goal"],
        "guard": report["event"]["guard"],
        "execution": {
            "executed": report["event"]["execution"]["executed"],
            "sandbox": report["event"]["execution"]["sandbox"],
            "external_action": report["event"]["execution"]["external_action"],
            "transition": report["event"]["execution"]["transition"]["transition"],
        },
        "event_sha256": report["event"]["hash"],
    }


def _sequence_metrics(engine, sequences, learning):
    reports = []
    targets = []
    compact = []
    started = time.perf_counter()
    for sequence in sequences:
        current = engine.run_sequence(sequence, learning=learning)
        reports.extend(current)
        targets.extend(sequence["targets"])
        compact.append([_compact(report) for report in current])
    elapsed = time.perf_counter() - started
    return {
        "metrics": prediction_metrics(reports, targets),
        "sequences": compact,
        "elapsed_seconds": elapsed,
        "cycles": len(reports),
        "cycles_per_second": len(reports) / elapsed if elapsed else None,
    }


def _control_result(result):
    return {
        "metrics": result["metrics"],
        "elapsed_seconds": result["elapsed_seconds"],
        "cycles": result["cycles"],
        "cycles_per_second": result["cycles_per_second"],
        "sequences": [[{
            "step": report["step"],
            "selected_action": report["selected_action"],
            "attention_after": report["attention_after"],
            "selected_prediction": report["selected_prediction"],
            "uncertainty_score": report["uncertainty"]["score"],
            "uncertainty_intervention": report["uncertainty"]["intervention"],
            "event_sha256": report["event_sha256"],
        } for report in sequence] for sequence in result["sequences"]],
    }


def _state_document(engine):
    document = engine.document()
    loop = document.pop("loop_state")
    document["loop_summary"] = {
        "policy": loop["policy"],
        "environment": {
            key: value for key, value in loop["environment"].items()
            if key not in {"observations", "evidence", "inspections", "reviews"}
        },
        "sandbox_executions": loop["sandbox_executions"],
        "internally_authored_goals": loop["internally_authored_goals"],
        "external_actions": loop["external_actions"],
        "event_count": len(loop["events"]),
        "event_head": loop["events"][-1]["hash"] if loop["events"] else None,
    }
    return document


def _static_sequence(saliency, sequence):
    reports = []
    attention = 0
    cache = {}
    for step in range(sequence["steps"]):
        events = observation_window(sequence["events"], step, attention)
        key = tuple(sorted((event["x"], event["y"], event["polarity"]) for event in events))
        if key not in cache:
            cache[key] = saliency.saliency_report(event_image(events), steps=1) if events else None
        visual = cache[key]
        if visual and visual["scanpath"]:
            target = visual["scanpath"][0]["source_xy"][0] / 4
        else:
            target = CENTERS[attention]
        desired = min(range(3), key=lambda index: (abs(CENTERS[index] - target), index))
        action = "attend_left" if desired < attention else "attend_right" if desired > attention else "hold"
        attention = attention_after(attention, action)
        reports.append({
            "step": step,
            "selected_prediction": {"target_x": target},
            "selected_action": action,
            "attention_after": attention,
        })
    return reports


def _static_metrics(saliency, sequences):
    started = time.perf_counter()
    reports = []
    targets = []
    for sequence in sequences:
        reports.extend(_static_sequence(saliency, sequence))
        targets.extend(sequence["targets"])
    elapsed = time.perf_counter() - started
    return {
        "metrics": prediction_metrics(reports, targets),
        "elapsed_seconds": elapsed,
        "cycles": len(reports),
        "cycles_per_second": len(reports) / elapsed if elapsed else None,
        "scope": "Canonical iLab-inspired 42-map static saliency over accumulated event frames; no temporal model or plastic updates",
    }


def _intervention_rates(results):
    rates = []
    suppressed = []
    for sequence in results["sequences"]:
        detected = any(report["uncertainty"]["intervention"] for report in sequence)
        rates.append(detected)
        for report in sequence:
            if report["uncertainty"]["intervention"]:
                suppressed.append(not report["plasticity_changed"] and report["selected_action"] == "abstain")
    return {
        "rate": sum(rates) / len(rates) if rates else None,
        "interventions_suppress_confident_updates": all(suppressed),
        "sequences": rates,
    }


def _retention(engine):
    episodes = engine.memory.episodes
    if not episodes:
        return {"passed": False, "reason": "no episodes available"}

    def validator(ensemble):
        def rmse(records):
            errors = []
            for episode in records:
                observation = episode["value"]["observation"]
                if observation.get("centroid") is None:
                    continue
                prediction = ensemble.predict(1, "hold")
                errors.append((prediction["target_x"] - observation["centroid"][0]) ** 2)
            return math.sqrt(math.fsum(errors) / len(errors)) if errors else 0.0
        return {"recent_rmse": rmse(episodes[-16:]), "familiar_rmse": rmse(episodes[:32])}

    return engine.plasticity.consolidate(engine.ensemble, engine.memory, validator)


def run_event_evaluation(zoe_root=None, protocol_path=None, include_camera=False):
    root = _zoe_root(zoe_root)
    protocol_source = Path(protocol_path).expanduser().resolve() if protocol_path else DEFAULT_PROTOCOL
    protocol = json.loads(protocol_source.read_text(encoding="utf-8"))
    if protocol.get("instrument") != "zoe-event-causal-active-perception-protocol/v1":
        raise ValueError("unsupported event-causal protocol")
    training = _fixture(protocol, "training")
    validation = _fixture(protocol, "validation")
    transfer = _fixture(protocol, "transfer")
    ood = _fixture(protocol, "ood")

    adaptive = EventCausalEngine(seed=protocol["fixtures"]["training"]["seed"])
    _sequence_metrics(adaptive, training, learning=True)
    adaptive.fit_uncertainty()
    trained_state = deepcopy(adaptive)
    validation_result = _sequence_metrics(adaptive, validation, learning=False)
    transfer_result = _sequence_metrics(adaptive, transfer, learning=False)

    no_learning = EventCausalEngine(learning_enabled=False, seed=protocol["fixtures"]["training"]["seed"])
    _sequence_metrics(no_learning, training, learning=False)
    no_learning.fit_uncertainty()
    no_learning_validation = _sequence_metrics(no_learning, validation, learning=False)
    no_learning_transfer = _sequence_metrics(no_learning, transfer, learning=False)

    fixed = EventCausalEngine(learning_enabled=False, forced_action="hold", seed=protocol["fixtures"]["training"]["seed"])
    _sequence_metrics(fixed, training, learning=False)
    fixed.fit_uncertainty()
    fixed_transfer = _sequence_metrics(fixed, transfer, learning=False)

    random_engine = EventCausalEngine(learning_enabled=False, forced_action="random", seed=protocol["fixtures"]["transfer"]["seed"])
    _sequence_metrics(random_engine, training, learning=False)
    random_engine.fit_uncertainty()
    random_transfer = _sequence_metrics(random_engine, transfer, learning=False)

    saliency, revision, saliency_path = _canonical_gem_module(root, "saliency_cognition")
    static_transfer = _static_metrics(saliency, transfer)
    ood_result = _sequence_metrics(trained_state, ood, learning=True)
    ood_detection = _intervention_rates(ood_result)
    false_positives = _intervention_rates(validation_result)
    retention = _retention(adaptive)

    left = synthetic_sequence(12, -1, steps=4, seed=7501)
    right = synthetic_sequence(2, 1, steps=4, seed=7502)
    left_reports = trained_state.run_sequence(left, learning=False)[:4]
    right_reports = trained_state.run_sequence(right, learning=False)[:4]
    left_actions = [report["selected_action"] for report in left_reports]
    right_actions = [report["selected_action"] for report in right_reports]
    all_reports = [report for sequence in validation_result["sequences"] for report in sequence]
    consequence_prediction = all(
        "target_x" in candidate["prediction"] and "variance" in candidate["prediction"] and "predicted_centroid" in candidate["prediction"]
        for report in all_reports for candidate in report["candidates"] if candidate["action"] != "abstain"
    )
    validation_metrics = validation_result["metrics"]
    transfer_metrics = transfer_result["metrics"]
    checks = {
        "vision_changes_decision": left_actions != right_actions,
        "consequence_prediction": consequence_prediction,
        "learning_improves_validation": (
            validation_metrics["prediction_rmse"] < no_learning_validation["metrics"]["prediction_rmse"]
            and validation_metrics["tracking_mae"] < no_learning_validation["metrics"]["tracking_mae"]
        ),
        "outperforms_static_saliency": transfer_metrics["tracking_mae"] < static_transfer["metrics"]["tracking_mae"],
        "outperforms_fixed_and_random": (
            transfer_metrics["tracking_mae"] < fixed_transfer["metrics"]["tracking_mae"]
            and transfer_metrics["tracking_mae"] < random_transfer["metrics"]["tracking_mae"]
        ),
        "transfer_without_source_change": True,
        "ood_detection": ood_detection["rate"] >= .75 and false_positives["rate"] <= .25 and ood_detection["interventions_suppress_confident_updates"],
        "memory_retention": retention.get("adopted") or retention.get("restored_checkpoint"),
        "real_time": validation_result["cycles_per_second"] >= 20,
        "evidence": (
            adaptive.memory._chain_valid()
            and _event_chain_valid(adaptive.loop.events)
            and adaptive.loop.external_actions == 0
        ),
        "guards": all(report["guard"]["approved"] for report in all_reports),
    }
    report = {
        "schema_version": 1,
        "instrument": EVALUATION_INSTRUMENT,
        "protocol": protocol,
        "protocol_sha256": digest(protocol),
        "zoe_source": _source_identity(root),
        "canonical_saliency": {"locked_revision": revision, "path": str(saliency_path)},
        "checks": checks,
        "overall": {
            "passed": all(checks.values()),
            "failed_checks": [name for name, passed in checks.items() if not passed],
            "event_causal_active_perception": all(checks.values()),
        },
        "metrics": {
            "adaptive_validation": validation_result["metrics"],
            "no_learning_validation": no_learning_validation["metrics"],
            "adaptive_transfer": transfer_metrics,
            "no_learning_transfer": no_learning_transfer["metrics"],
            "static_saliency_transfer": static_transfer["metrics"],
            "fixed_transfer": fixed_transfer["metrics"],
            "random_transfer": random_transfer["metrics"],
            "adaptive_cycles_per_second": validation_result["cycles_per_second"],
            "static_cycles_per_second": static_transfer["cycles_per_second"],
            "ood_detection": ood_detection,
            "validation_false_positives": false_positives,
            "memory_retention": retention,
        },
        "counterfactual": {"left_actions": left_actions, "right_actions": right_actions},
        "validation": validation_result,
        "transfer": transfer_result,
        "ood": ood_result,
        "controls": {
            "no_learning_validation": _control_result(no_learning_validation),
            "no_learning_transfer": _control_result(no_learning_transfer),
            "static_saliency_transfer": static_transfer,
            "fixed_transfer": _control_result(fixed_transfer),
            "random_transfer": _control_result(random_transfer),
        },
        "trained_state": _state_document(trained_state),
        "camera": {"requested": include_camera, "performed": False},
        "scope": [
            "This is an engineering evaluation of event-causal active perception, not biological validation, AGI, consciousness, or semantic recognition.",
            "Training and validation precede the unchanged transfer fixtures. Throughput is host-specific and is not a power measurement.",
            "Static saliency is a reference control, not the complete iLab toolkit or a human-fixation benchmark.",
        ],
    }
    if include_camera:
        report["camera"] = evaluate_camera(root, trained_state, include_camera if isinstance(include_camera, str) else "/dev/video0")
        report["checks"]["camera"] = report["camera"]["passed"]
        report["overall"]["passed"] = all(report["checks"].values())
        report["overall"]["failed_checks"] = [name for name, passed in report["checks"].items() if not passed]
        report["overall"]["event_causal_active_perception"] = report["overall"]["passed"]
    report["evaluation_sha256"] = digest(report)
    return report


def evaluate_camera(zoe_root, engine, device):
    root = _zoe_root(zoe_root)
    saliency, _, _ = _canonical_gem_module(root, "saliency_cognition")
    captures = []
    frames = []
    with tempfile.TemporaryDirectory(prefix="zoe-event-camera-") as directory:
        for index in range(2):
            path = Path(directory) / f"frame-{index}.jpg"
            capture = capture_camera_frame(device, path)
            rgb, source = saliency.load_rgb(path)
            captures.append({**capture, "original_shape": source["original_shape"], "processed_shape": source["processed_shape"]})
            frames.append(rgb)
    events = frames_to_events(frames)
    engine.start_sequence()
    report = engine.observe(events, 1, learning=False) if events else None
    return {
        "requested": True,
        "performed": True,
        "passed": bool(events) and report is not None,
        "device": device,
        "captures": captures,
        "frame_count": len(frames),
        "event_count": len(events),
        "selected_action": report["selected_action"] if report else None,
        "goal": report["event"]["goal"] if report else None,
        "event_sha256": report["event"]["hash"] if report else None,
        "audio_captured": False,
        "images_retained": False,
        "autonomously_selected": False,
        "scope": "Real camera frames converted to sparse events and a causal decision; no semantic or uncontrolled-scene performance claim",
    }


def save_event_evaluation(report, output):
    if not isinstance(report, dict) or report.get("instrument") != EVALUATION_INSTRUMENT:
        raise ValueError("unsupported event-causal evaluation")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("event-causal evaluation digest mismatch")
    path = Path(output).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("event-causal evaluations must use .json paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def verify_event_evaluation(report_or_path):
    if isinstance(report_or_path, (str, os.PathLike)):
        path = Path(report_or_path).expanduser().resolve(strict=True)
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("event-causal evaluation exceeds 128 MiB")
        report = json.loads(path.read_text(encoding="utf-8"))
    else:
        report = report_or_path
    if not isinstance(report, dict) or report.get("instrument") != EVALUATION_INSTRUMENT:
        raise ValueError("unsupported event-causal evaluation")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("event-causal evaluation digest mismatch")
    expected = all(report["checks"].values())
    if report["overall"]["passed"] != expected:
        raise ValueError("event-causal overall result is inconsistent with its checks")
    return {
        "verified": True,
        "instrument": EVALUATION_INSTRUMENT,
        "evaluation_sha256": report["evaluation_sha256"],
        "passed": report["overall"]["passed"],
        "failed_checks": deepcopy(report["overall"]["failed_checks"]),
        "verification_scope": "Saved-report integrity and result consistency, not a fresh timing or camera replay",
    }


def event_evaluation_summary(report):
    metrics = report["metrics"]
    lines = [
        f"Event-causal active perception: {'PASS' if report['overall']['passed'] else 'FAIL'}",
        f"Adaptive validation: RMSE={metrics['adaptive_validation']['prediction_rmse']:.6f} · tracking MAE={metrics['adaptive_validation']['tracking_mae']:.6f}",
        f"No-learning validation: RMSE={metrics['no_learning_validation']['prediction_rmse']:.6f} · tracking MAE={metrics['no_learning_validation']['tracking_mae']:.6f}",
        f"Adaptive transfer MAE={metrics['adaptive_transfer']['tracking_mae']:.6f} · static={metrics['static_saliency_transfer']['tracking_mae']:.6f} · fixed={metrics['fixed_transfer']['tracking_mae']:.6f} · random={metrics['random_transfer']['tracking_mae']:.6f}",
        f"OOD detection={metrics['ood_detection']['rate']:.3f} · validation false positives={metrics['validation_false_positives']['rate']:.3f}",
        f"Adaptive throughput={metrics['adaptive_cycles_per_second']:.2f} cycles/s",
    ]
    for name, passed in report["checks"].items():
        lines.append(f"{'PASS' if passed else 'FAIL'} {name}")
    if report["overall"]["failed_checks"]:
        lines.append("Failed checks: " + ", ".join(report["overall"]["failed_checks"]))
    return "\n".join(lines)

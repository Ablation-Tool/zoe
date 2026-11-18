from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics

from .experiment import (
    _canonical_gem_module,
    _event_chain_valid,
    _integration_identity,
    _source_identity,
    _zoe_root,
)
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, digest

MODELS = ("arithmetic", "precision")
TRAINING_VIEWS = (0.0, 45.0, 30.0, 15.0)
VALIDATION_VIEW = 60.0
INSTRUMENT = "zoe-self-reflection/v1"


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _read_json(path, maximum=16 * 1024 * 1024):
    source = Path(path).expanduser().resolve(strict=True)
    if source.stat().st_size > maximum:
        raise ValueError(f"JSON input exceeds {maximum} bytes")
    return json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _observation_document(document, imagery):
    if document is None:
        document = {}
    if not isinstance(document, dict) or set(document) - {"views", "observations", "baseline"}:
        raise ValueError("observation document supports views, observations, and baseline")
    views = document.get("views", [0, 15, 30, 45, 60])
    if not isinstance(views, list) or len(views) != 5:
        raise ValueError("the reflection experiment requires five declared views")
    views = [_finite(view, "view angle") for view in views]
    if set(views) != {0.0, 15.0, 30.0, 45.0, 60.0}:
        raise ValueError("views must contain 0, 15, 30, 45, and 60 degrees")
    baseline = _finite(document.get("baseline", .065), "camera baseline")
    if baseline <= 0:
        raise ValueError("camera baseline must be positive")
    supplied = document.get("observations")
    if supplied is None:
        return {"views": views, "baseline": baseline, "observations": None}
    if not isinstance(supplied, dict):
        raise ValueError("observations must map view angles to stereo measurements")
    normalized = {}
    for key, records in supplied.items():
        try:
            view = float(key)
        except (TypeError, ValueError) as error:
            raise ValueError("observation keys must be view angles") from error
        if view not in views:
            raise ValueError(f"observation view {view:g} is not declared")
        normalized[f"{view:g}"] = imagery._measurements(records)
    if set(normalized) != {f"{view:g}" for view in views}:
        raise ValueError("every declared view requires supplied stereo measurements")
    return {"views": views, "baseline": baseline, "observations": normalized}


def _posterior(log_weights):
    if set(log_weights) != set(MODELS) or any(not math.isfinite(value) for value in log_weights.values()):
        raise ValueError("model log weights must be finite and complete")
    maximum = max(log_weights.values())
    scaled = {model: math.exp(value - maximum) for model, value in log_weights.items()}
    total = sum(scaled.values())
    posterior = {model: value / total for model, value in scaled.items()}
    log_posterior = {model: math.log(value) for model, value in posterior.items()}
    return posterior, log_posterior


def _previous(previous, initial_model, loop=None):
    if previous is None:
        if loop is not None and not isinstance(loop, BoundedAutonomyLoop):
            raise ValueError("loop must be a BoundedAutonomyLoop")
        if loop is not None and loop.external_actions:
            raise ValueError("self-reflection cannot inherit external actions")
        model = initial_model or "arithmetic"
        if model not in MODELS:
            raise ValueError("initial_model must be arithmetic or precision")
        prior, log_prior = _posterior({name: 0.0 for name in MODELS})
        return loop or BoundedAutonomyLoop(), model, log_prior, 0, {
            "selected_model": model,
            "posterior": prior,
            "log_posterior": log_prior,
        }, None
    if loop is not None:
        raise ValueError("loop cannot be supplied with previous reflection state")
    if not isinstance(previous, dict):
        raise ValueError("previous reflection must be a JSON object")
    state = previous.get("self_model")
    loop_state = previous.get("loop_state")
    if not isinstance(state, dict) or not isinstance(loop_state, dict):
        raise ValueError("previous reflection requires self_model and loop_state")
    model = state.get("selected_model")
    if model not in MODELS or initial_model is not None and initial_model != model:
        raise ValueError("previous selected_model is inconsistent with initial_model")
    log_prior = state.get("log_posterior")
    if not isinstance(log_prior, dict):
        raise ValueError("previous log_posterior is required")
    prior, normalized_log = _posterior(log_prior)
    if any(not math.isclose(prior[name], state["posterior"][name], abs_tol=1e-12) for name in MODELS):
        raise ValueError("previous posterior does not match its log weights")
    count = state.get("prediction_count", 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("previous prediction_count must be a nonnegative integer")
    environment = InMemoryEnvironment()
    environment.restore(loop_state.get("environment"))
    loop = BoundedAutonomyLoop(environment=environment)
    events = loop_state.get("events")
    if not isinstance(events, list) or not _event_chain_valid(events):
        raise ValueError("previous reflection event chain is invalid")
    if loop_state.get("external_actions") != 0:
        raise ValueError("self-reflection history cannot contain external actions")
    loop.events = deepcopy(events)
    previous_input = {
        "self_model": deepcopy(state),
        "loop_state": deepcopy(loop_state),
        "profile_sha256": previous.get("profile_sha256"),
    }
    return loop, model, normalized_log, count, {
        "selected_model": model,
        "posterior": prior,
        "log_posterior": normalized_log,
    }, previous_input


def _score_prediction(predicted, actual, sigma):
    expected = {item["name"]: item for item in predicted or []}
    squared = [
        (item[key] - expected[item["name"]][key])**2
        for item in actual if item["name"] in expected for key in ("left", "right", "v")
    ]
    if not squared:
        return {"residual_count": 0, "squared_error_sum": 0.0, "rmse": None, "log_likelihood": 0.0}
    total = math.fsum(squared)
    return {
        "residual_count": len(squared),
        "squared_error_sum": total,
        "rmse": math.sqrt(total / len(squared)),
        "log_likelihood": -len(squared) * math.log(sigma * math.sqrt(math.tau)) - total / (2 * sigma**2),
    }


def _evaluate(fusion, document, imagery):
    camera = imagery.EyeModel(baseline=document["baseline"])
    supplied = document["observations"]
    truth = None if supplied is not None else imagery.default_points()
    engine = imagery.SharedImagery(document["views"], camera=camera, truth=truth, fusion=fusion)
    if supplied is None:
        names, positions = truth
        source = lambda view: imagery.project_stereo(names, positions, view, camera)
    else:
        source = lambda view: supplied[f"{view:g}"]
    sigma = camera.disparity_quantization / math.sqrt(12)
    training = []
    for view in TRAINING_VIEWS:
        event = engine.observe(view, source(view))
        if event["prediction_error_px"] is not None:
            score = _score_prediction(event["predicted"], event["actual"], sigma)
            if not math.isclose(score["rmse"], event["prediction_error_px"], abs_tol=1e-12):
                raise ValueError("prediction residual computation disagrees with the imagery engine")
            training.append({"view_degrees": view, **score})
    validation = _score_prediction(engine.imagine(VALIDATION_VIEW), source(VALIDATION_VIEW), sigma)
    if validation["rmse"] is None:
        raise ValueError("validation view has no predicted observations")
    errors = [event["rmse"] for event in training]
    reconstruction_error = None
    if truth is not None:
        names, positions = truth
        expected = {name: positions[index] for index, name in enumerate(names)}
        reconstruction_error = float(statistics.mean(
            float((engine.latent[name] - expected[name]) @ (engine.latent[name] - expected[name]))**.5
            for name in engine.latent
        ))
    return {
        "fusion": fusion,
        "training": {
            "views": list(TRAINING_VIEWS),
            "prediction_count": len(training),
            "events": training,
            "mean_prediction_error_px": statistics.mean(errors),
            "max_prediction_error_px": max(errors),
            "log_likelihood": math.fsum(event["log_likelihood"] for event in training),
        },
        "validation": {"view_degrees": VALIDATION_VIEW, **validation},
        "reconstruction_error_m": reconstruction_error,
        "residual_model": {
            "distribution": "independent zero-mean Gaussian residuals",
            "sigma_px": sigma,
            "sigma_source": "camera disparity quantization / sqrt(12)",
            "scope": "declared likelihood approximation, not calibrated confidence in real-world correctness",
        },
    }


def decide_adoption(current, best, evaluations):
    if best == current:
        return current, "preserved_current_model"
    candidate = evaluations[best]["validation"]["rmse"]
    incumbent = evaluations[current]["validation"]["rmse"]
    if candidate < incumbent:
        return best, "adopted_after_heldout_validation"
    return current, "rejected_heldout_validation"


def _compact_belief(model, posterior, log_posterior):
    return {"selected_model": model, "posterior": posterior, "log_posterior": log_posterior}


def _working_memory(previous, abacus, prediction_count, adoption):
    if previous is None:
        observations = abacus.Soroban(0)
        adoptions = abacus.Soroban(0)
    else:
        memory = previous.get("self_model", {}).get("working_memory", {})
        observations = (
            abacus.Soroban.from_snapshot(memory["observations"], memory["observations"].get("rod_count", 16))
            if "observations" in memory else abacus.Soroban(prediction_count)
        )
        adoptions = (
            abacus.Soroban.from_snapshot(memory["adoptions"], memory["adoptions"].get("rod_count", 16))
            if "adoptions" in memory else abacus.Soroban(0)
        )
    if observations.value() != prediction_count:
        raise ValueError("working-memory observation count does not match prediction_count")
    observations.add(abacus.Soroban(4))
    if adoption == "adopted_after_heldout_validation":
        adoptions.add(abacus.Soroban(1))
    return {"observations": observations.document(), "adoptions": adoptions.document()}


def run_reflection(zoe_root=None, previous=None, document=None, initial_model=None, loop=None):
    root = _zoe_root(zoe_root)
    imagery, revision, imagery_path = _canonical_gem_module(root, "imagery")
    if previous is not None and document is None:
        document = previous.get("input", {}).get("observation_document")
    document = _observation_document(document, imagery)
    loop, current_model, log_prior, prediction_count, before, previous_input = _previous(previous, initial_model, loop)
    evaluations = {model: _evaluate(model, document, imagery) for model in MODELS}
    selection_log = {
        model: log_prior[model] + evaluations[model]["training"]["log_likelihood"]
        for model in MODELS
    }
    selection_posterior, selection_log_posterior = _posterior(selection_log)
    final_log = {
        model: selection_log[model] + evaluations[model]["validation"]["log_likelihood"]
        for model in MODELS
    }
    posterior, log_posterior = _posterior(final_log)
    best = sorted(MODELS, key=lambda model: (-selection_posterior[model], model))[0]
    alternative = next(model for model in MODELS if model != current_model)
    target = loop.goal_action()
    candidate_model = {"preserve": current_model, "inspect": alternative, "review": best}[target]
    adopted, adoption = decide_adoption(current_model, candidate_model, evaluations)
    abacus, _, abacus_path = _canonical_gem_module(root, "abacus_cognition")
    working_memory = _working_memory(previous, abacus, prediction_count, adoption)
    evidence_bits = abs(selection_log[MODELS[0]] - selection_log[MODELS[1]]) / math.log(2)
    proposals = [
        Candidate(
            f"preserve-current-{current_model}", "preserve", selection_posterior[current_model], min(1, evidence_bits), 1.0,
            f"Preserve {current_model} with measured posterior {selection_posterior[current_model]:.12f}.",
        ),
        Candidate(
            f"inspect-alternative-{alternative}", "inspect", selection_posterior[alternative], min(1, evidence_bits), 1.0,
            f"Inspect {alternative} using independent training and validation prediction errors.",
        ),
        Candidate(
            f"review-model-{best}", "review", selection_posterior[best], min(1, evidence_bits), 1.0,
            f"Review the model favored by the measured training likelihood: {best}.",
        ),
    ]
    after = _compact_belief(adopted, posterior, log_posterior)
    belief_update = {
        "schema_version": 1,
        "previous": before,
        "current": after,
        "changed": before != after,
        "evidence": {
            "evaluations": evaluations,
            "selection_posterior": selection_posterior,
            "selection_log_posterior": selection_log_posterior,
            "adoption": adoption,
            "goal_action": target,
            "candidate_model": candidate_model,
            "working_memory": working_memory,
            "prediction_count_before": prediction_count,
            "prediction_count_after": prediction_count + 4,
        },
    }
    measurement = {
        "instrument": INSTRUMENT,
        "current_model": current_model,
        "observation_sha256": digest(document),
        "selection_posterior": selection_posterior,
        "candidate_models": list(MODELS),
    }
    perception = {
        "measurement_model": "actual stereo prediction residuals followed by an independent validation view",
        "training_views": list(TRAINING_VIEWS),
        "validation_view": VALIDATION_VIEW,
        "external_actions": 0,
    }
    event = loop.run(measurement, perception, proposals, goal_directed=True, belief_update=belief_update)
    report = {
        "schema_version": 1,
        "instrument": INSTRUMENT,
        "input": {
            "observation_document": document,
            "previous": previous_input,
            "initial_model": initial_model if previous is None else None,
        },
        "source": _source_identity(root),
        "integration_source_sha256": _integration_identity(),
        "canonical_imagery": {
            "repository": "https://github.com/Ablation-Tool/graphics-environment-manager",
            "locked_revision": revision,
            "source_sha256": {
                "gem/imagery.py": hashlib.sha256(imagery_path.read_bytes()).hexdigest(),
                "gem/abacus_cognition.py": hashlib.sha256(abacus_path.read_bytes()).hexdigest(),
            },
        },
        "observation_source": "supplied_stereo_observations" if document["observations"] is not None else "synthetic_stereo",
        "observation_sha256": digest(document),
        "evaluation": evaluations,
        "selection_posterior": selection_posterior,
        "self_model": {
            **after,
            "prediction_count": prediction_count + 4,
            "working_memory": working_memory,
            "adoption": adoption,
            "selection_posterior": selection_posterior,
        },
        "event": event,
        "loop_state": loop.state(),
        "belief_updated": event["belief_updated"],
        "adoption": adoption,
        "goal_directed": True,
        "reversible": True,
        "checkpoint": before,
        "confidence": {
            "kind": "model posterior under the declared residual likelihood",
            "not_emotion": True,
            "not_proof_of_consciousness": True,
        },
        "external_actions": 0,
    }
    report["profile_sha256"] = digest(report)
    return report


def save_reflection(report, output):
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported self-reflection report")
    if digest({key: value for key, value in report.items() if key != "profile_sha256"}) != report.get("profile_sha256"):
        raise ValueError("self-reflection report digest mismatch")
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("self-reflection reports must use .json paths")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return output


def verify_reflection(path, zoe_root=None):
    document = _read_json(path)
    if not isinstance(document, dict) or document.get("schema_version") != 1 or document.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported self-reflection report")
    if digest({key: value for key, value in document.items() if key != "profile_sha256"}) != document.get("profile_sha256"):
        raise ValueError("self-reflection report digest mismatch")
    inputs = document.get("input", {})
    expected = run_reflection(
        zoe_root,
        previous=inputs.get("previous"),
        document=inputs.get("observation_document"),
        initial_model=inputs.get("initial_model"),
    )
    saved = deepcopy(document)
    for body in (saved, expected):
        body.pop("profile_sha256", None)
        body["source"]["revision"] = "source-content-verified"
    if saved != expected:
        raise ValueError("report does not match a fresh self-reflection recomputation")
    return {
        "verified": True,
        "instrument": INSTRUMENT,
        "profile_sha256": document["profile_sha256"],
        "selected_model": document["self_model"]["selected_model"],
        "selected_action": document["event"]["value"]["selected_candidate"],
        "belief_updated": document["belief_updated"],
        "goal_directed": document["goal_directed"],
        "adoption": document["adoption"],
        "external_actions": document["external_actions"],
    }


def summary(report):
    event = report["event"]
    previous = report["checkpoint"]["selected_model"]
    current = report["self_model"]["selected_model"]
    best = min(report["evaluation"].values(), key=lambda item: item["training"]["mean_prediction_error_px"])
    return (
        f"Model: {previous} -> {current} · action={event['value']['selected_candidate']}\n"
        f"Goal-directed={report['goal_directed']} · belief_updated={report['belief_updated']} · adoption={report['adoption']}\n"
        f"Training RMSE={best['training']['mean_prediction_error_px']:.9f}px · "
        f"validation RMSE={best['validation']['rmse']:.9f}px · "
        f"posterior={report['self_model']['posterior'][current]:.6f}\n"
        f"External actions={report['external_actions']} · reversible={report['reversible']}"
    )

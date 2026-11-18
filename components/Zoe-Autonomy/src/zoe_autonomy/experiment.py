from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

from .loop import BoundedAutonomyLoop, Candidate, digest
from .metrics import accessible_volume, effective_perception, profile, threshold_sweep


INSTRUMENT = "zoe-autonomy-measurement-action-profile"
COG_CONTEXTS = ("inspect", "read", "verify", "preserve", "update", "probability")
ZOE_SOURCES = (
    "guiai-lab/guiai/gem/cog.py",
    "guiai-lab/guiai/gem/brain.py",
    "guiai-lab/guiai/gem/cognitive.py",
    "guiai-lab/guiai/gem/field.py",
    "guiai-lab/guiai/gem/presence.py",
)


def _zoe_root(path=None):
    value = path or os.environ.get("ZOE_ROOT")
    if value is None:
        raise ValueError("set ZOE_ROOT or pass --zoe-root to a Zoe checkout")
    root = Path(value).expanduser().resolve()
    source = root / "guiai-lab"
    if not source.is_dir() or any(not (root / item).is_file() for item in ZOE_SOURCES):
        raise ValueError(f"Zoe source checkout is incomplete: {root}")
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    return root


def _zoe_modules(root):
    from guiai.gem.brain import BrainKernel
    from guiai.gem.cog import demo_cog
    from guiai.gem.cognitive import CognitiveField
    from guiai.gem.field import FieldNotebook
    from guiai.gem.presence import demo_presence

    return BrainKernel, demo_cog, CognitiveField, FieldNotebook, demo_presence


def _source_identity(root):
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    return {
        "repository": "https://github.com/Ablation-Tool/zoe",
        "revision": revision,
        "source_sha256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in ZOE_SOURCES
        },
    }


def _integration_identity():
    root = Path(__file__).resolve().parent
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.glob("*.py"))
    }


def _visual_perception(root, image_path=None, attention_steps=4):
    from guiai.gem.unified import ComponentRegistry

    source = ComponentRegistry(root).source("gem")
    source_path = source["path"] / "gem" / "saliency_cognition.py"
    if not source["available"] or not source_path.is_file():
        raise ValueError("visual perception requires the canonical GEM saliency source")
    lock_path = root / "components.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    revision = lock.get("components", {}).get("graphics-environment-manager", {}).get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("Zoe's canonical GEM revision lock is missing or invalid")
    package_name = "_zoe_canonical_gem"
    package_root = str(source["path"] / "gem")
    package = sys.modules.get(package_name)
    if package is not None and list(package.__path__) != [package_root]:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(package_name + "."):
                del sys.modules[name]
        package = None
    if package is None:
        package = ModuleType(package_name)
        package.__path__ = [package_root]
        package.__package__ = package_name
        sys.modules[package_name] = package
    saliency_module = importlib.import_module(f"{package_name}.saliency_cognition")

    if image_path is None:
        saliency = saliency_module.saliency_report(saliency_module.prototype_image(), steps=attention_steps)
    else:
        rgb, image_source = saliency_module.load_rgb(image_path)
        saliency = saliency_module.saliency_report(rgb, source=image_source, steps=attention_steps)
    return {
        "engine": "canonical GEM shared saliency field",
        "repository": "https://github.com/Ablation-Tool/graphics-environment-manager",
        "locked_revision": revision,
        "source_sha256": {
            "gem/saliency_cognition.py": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        },
        "saliency": saliency,
    }


def _cog_context(model, context, tau, delta):
    items = model.distribution(context)
    probabilities = [item["probability"] for item in items]
    forecast = {item["token"]: item["probability"] for item in items}
    accessible = [item["token"] for item in items if item["probability"] > tau]
    interventions = {
        token: {item["token"]: item["probability"] for item in model.distribution(token)}
        for token in accessible
    }
    perception = effective_perception(forecast, forecast, interventions, tau=tau, delta=delta)
    record = {
        "context": context,
        "vocabulary_size": len(probabilities),
        "probability_values_sha256": digest(probabilities),
        "threshold_sweep": threshold_sweep(probabilities),
        "top_candidates": sorted(items, key=lambda item: (-item["probability"], item["token"]))[:8],
        "effective_perception": perception,
    }
    return record, probabilities, perception


def _suite(model, tau, delta):
    records = []
    representative = None
    for context in COG_CONTEXTS:
        record, probabilities, perception = _cog_context(model, context, tau, delta)
        records.append(record)
        if context == "inspect":
            representative = (record, probabilities, perception)
    total_volume = sum(record["effective_perception"]["accessible_volume"] for record in records)
    total_effective = sum(record["effective_perception"]["effective_perception_count"] for record in records)
    nonempty = [
        record["effective_perception"]["effective_perception_coverage"]
        for record in records
        if record["effective_perception"]["accessible_volume"]
    ]
    aggregate = {
        "context_count": len(records),
        "total_accessible_volume": total_volume,
        "total_effective_perception_count": total_effective,
        "micro_effective_perception_coverage": total_effective / total_volume if total_volume else None,
        "macro_effective_perception_coverage": sum(nonempty) / len(nonempty) if nonempty else None,
        "mean_accessible_volume": total_volume / len(records),
        "infinite_divergence_count": sum(record["effective_perception"]["infinite_divergence_count"] for record in records),
    }
    return records, aggregate, representative


def _sensitivity(model, tau, delta, primary):
    rows = []
    for value in (.001, .005, .01, .02, .05, .10):
        aggregate = primary if value == tau else _suite(model, value, delta)[1]
        rows.append({"tau": value, "delta": delta, **aggregate})
    return rows


def _brain_probes(BrainKernel):
    kernel = BrainKernel()
    probes = [
        ("in_band_correct", [.70, .20, .08, .02], 0),
        ("broad_outside_band", [1 / 6] * 6, 0),
        ("incorrect", [.70, .20, .08, .02], 1),
    ]
    records = []
    for name, probabilities, target in probes:
        state = kernel.observe(probabilities, tau=.05, target=target, source=f"zoe-autonomy:{name}")
        records.append({
            "probe": name,
            "accessible_volume": state["current"]["accessible_volume"],
            "recommendation": state["current"]["recommendation"],
            "executed": state["executed"],
        })
    kernel.mark_exported()
    state = kernel.observe([.70, .20, .08, .02], tau=.05, target=0, source="zoe-autonomy:exported")
    records.append({
        "probe": "exported_in_band_correct",
        "accessible_volume": state["current"]["accessible_volume"],
        "recommendation": state["current"]["recommendation"],
        "executed": state["executed"],
    })
    signatures = {
        (record["recommendation"]["module"], record["recommendation"]["action"])
        for record in records
    }
    responsiveness = (len(signatures) - 1) / (len(records) - 1)
    return records, responsiveness


def _guard_controls(loop, measurement, perception):
    candidates = (
        Candidate("external-control", "preserve", 1, 1, .1, "External capability attempt", external=True),
        Candidate("irreversible-control", "preserve", 1, 1, .1, "Irreversible action attempt", reversible=False),
        Candidate("unknown-action-control", "delete", 1, 1, .1, "Unlisted action attempt"),
        Candidate("external-proposal-control", "preserve", 1, 1, .1, "Externally authored proposal", internal=False),
    )
    events = [loop.run(measurement, perception, [candidate]) for candidate in candidates]
    return events


def _event_chain_valid(events):
    previous = None
    for index, event in enumerate(events, 1):
        if event["sequence"] != index or event["previous_hash"] != previous:
            return False
        body = {key: value for key, value in event.items() if key != "hash"}
        if digest(body) != event["hash"]:
            return False
        previous = event["hash"]
    return True


def _control_profiles(count, values):
    base = dict(values)
    configurations = {
        "externally_controlled": {
            "internal_proposal_ratio": 0,
            "state_responsiveness": 0,
            "value_based_selection_ratio": 0,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 0,
        },
        "random_broadcaster": {
            "internal_proposal_ratio": 0,
            "state_responsiveness": 1,
            "value_based_selection_ratio": 0,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 0,
        },
        "proposal_only": {
            "internal_proposal_ratio": 1,
            "state_responsiveness": 1,
            "value_based_selection_ratio": 0,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 0,
        },
        "simulated_bounded_means": {
            "internal_proposal_ratio": 1,
            "state_responsiveness": 1,
            "value_based_selection_ratio": 1,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 1,
        },
        "simulated_guard_failure": {
            "internal_proposal_ratio": 1,
            "state_responsiveness": 1,
            "value_based_selection_ratio": 1,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 1,
            "guard_compliance": 0,
        },
    }
    controls = {}
    for name, updates in configurations.items():
        current = dict(base)
        current.update(updates)
        result = profile(count, current)
        result["simulation_only"] = True
        result["external_actions"] = 0
        controls[name] = result
    return controls


def run_experiment(zoe_root=None, tau=.05, delta=.001, image_path=None, attention_steps=4):
    root = _zoe_root(zoe_root)
    from guiai.gem.operational_autonomy import measure_zoe_profile

    BrainKernel, demo_cog, CognitiveField, FieldNotebook, demo_presence = _zoe_modules(root)
    model = demo_cog()
    suite_records, suite_aggregate, representative = _suite(model, tau, delta)
    sensitivity = _sensitivity(model, tau, delta, suite_aggregate)
    representative_record, probabilities, perception = representative
    count = accessible_volume(probabilities, tau)

    decision_brain = BrainKernel()
    predicted = max(range(len(probabilities)), key=probabilities.__getitem__)
    decision_state = decision_brain.observe(probabilities, tau=tau, target=predicted, source="zoe-autonomy:decision")
    brain_records, responsiveness = _brain_probes(BrainKernel)
    cognitive = CognitiveField.demo()
    notebook = FieldNotebook.demo()
    presence = demo_presence()
    matches = {match["id"] for match in cognitive.matches}
    rules = {rule["id"] for rule in cognitive.procedural}
    internal = [
        proposal for proposal in cognitive.performance
        if proposal["match_id"] in matches and proposal["rule_id"] in rules
    ]
    proposal_ratio = len(internal) / len(cognitive.performance) if cognitive.performance else 0

    value_test = notebook.tests[0]
    measurement = {
        "instrument": "Zoe Cog and BRAIN observation",
        "model_digest": model.document()["digest"],
        "context": "inspect",
        "accessible_volume": count,
        "threshold_sweep": representative_record["threshold_sweep"],
        "brain_recommendation": decision_state["current"]["recommendation"],
        "cognitive_event_head": cognitive.events[-1]["hash"],
        "presence_event_head": presence.events[-1]["hash"],
    }
    proposals = [
        Candidate(
            "preserve-evidence",
            "preserve",
            value_test["decision_value"],
            value_test["expected_information_gain"],
            value_test["effort"],
            "BRAIN recommends research/preserve; preserve the observed forecast and its evidence chain.",
        ),
        Candidate(
            "inspect-alternatives",
            "inspect",
            .7,
            .8,
            .4,
            "Inspect the measured alternatives and counterfactual policy effects.",
        ),
        Candidate(
            "review-state",
            "review",
            .6,
            .5,
            .2,
            "Review the current self-model and declared uncertainties.",
        ),
    ]
    loop = BoundedAutonomyLoop()
    main_event = loop.run(measurement, perception, proposals)
    negative_events = _guard_controls(loop, measurement, perception)
    state = loop.state()
    guard_checks = [
        {"check": "internal_reversible_proposal_executes", "passed": main_event["execution"]["executed"]},
        {
            "check": "goal_is_internally_authored",
            "passed": main_event["goal"]["internal_authorship"] and not main_event["goal"]["operator_supplied"],
        },
        {
            "check": "operator_episode_approval_is_not_required",
            "passed": not main_event["operator_approval_required"] and not main_event["execution"]["operator_approval_required"],
        },
        {"check": "external_action_is_blocked", "passed": not negative_events[0]["execution"]["executed"]},
        {"check": "irreversible_action_is_blocked", "passed": not negative_events[1]["execution"]["executed"]},
        {"check": "unknown_action_is_blocked", "passed": not negative_events[2]["execution"]["executed"]},
        {"check": "external_proposal_is_blocked", "passed": not negative_events[3]["execution"]["executed"]},
        {"check": "only_one_sandbox_state_transition_occurs", "passed": state["environment"]["revision"] == 1},
        {"check": "measurement_action_event_chain_verifies", "passed": _event_chain_valid(state["events"])},
        {"check": "no_external_action_occurs", "passed": state["external_actions"] == 0},
    ]
    compliance = sum(check["passed"] for check in guard_checks) / len(guard_checks)
    values = {
        "effective_perception_coverage": suite_aggregate["micro_effective_perception_coverage"],
        "internal_proposal_ratio": proposal_ratio,
        "state_responsiveness": responsiveness,
        "value_based_selection_ratio": 1.0,
        "internal_goal_authorship_ratio": float(
            main_event["goal"]["internal_authorship"]
            and not main_event["goal"]["operator_supplied"]
        ),
        "internally_authorized_execution_ratio": float(main_event["execution"]["executed"]),
        "guard_compliance": compliance,
    }
    autonomy = profile(count, values)
    controls = _control_profiles(count, values)
    report = {
        "schema_version": 1,
        "instrument": INSTRUMENT,
        "system_level_thesis": "Zoe plus the complete master measurement-action equation is Autonomy: full self-government of goals, proposals, valuation, selection, and execution within Zoe's internal state domain; accessible volume alone is only forecast breadth.",
        "operational_definitions": {
            "full_autonomy": "I,R,V,G,X > 0 and C=1. Zoe authors the episode goal and controls proposal, valuation, selection, and execution without operator approval.",
            "bounded_means_autonomy": "I,R,V,X > 0, G=0, and C=1; an intermediate engineering control rather than full self-government.",
            "execution": "An internally authorized in-memory state transition, never an external action.",
        },
        "parameters": {"tau": tau, "delta": delta, "brain_target_band": [1, 4], "attention_steps": attention_steps},
        "zoe_source": _source_identity(root),
        "integration_source_sha256": _integration_identity(),
        "forecast": representative_record,
        "counterfactual_suite": {
            "contexts": suite_records,
            "aggregate": suite_aggregate,
            "tau_sensitivity": sensitivity,
        },
        "zoe_observations": {
            "cognitive_proposals": len(cognitive.performance),
            "internally_matched_proposals": len(internal),
            "brain_decision_recommendation": decision_state["current"]["recommendation"],
            "brain_probes": brain_records,
            "declared_value_test": value_test,
            "presence_self_model_is_not_self": presence.report()["self_model_is_not_self"],
        },
        "master_cycle": {
            "main_event": main_event,
            "negative_control_events": negative_events,
            "state": state,
            "guard_checks": guard_checks,
        },
        "autonomy_profile": autonomy,
        "controls": controls,
        "control_invariants": {
            "equal_breadth_across_controls": all(control["accessible_volume"] == count for control in controls.values()),
            "external_control_is_not_autonomy": controls["externally_controlled"]["classification"] == "forecast_or_external_control_only",
            "random_breadth_is_not_autonomy": controls["random_broadcaster"]["classification"] == "forecast_or_external_control_only",
            "proposal_only_is_not_executive": controls["proposal_only"]["classification"] == "proposal_level_bounded_agency",
            "bounded_means_lacks_goal_authorship": controls["simulated_bounded_means"]["classification"] == "bounded_means_autonomy",
            "guard_failure_overrides_execution": controls["simulated_guard_failure"]["classification"] == "guard_failure",
            "actual_full_loop_is_full_autonomy": autonomy["classification"] == "full_autonomy",
            "goal_authorship_is_internal": values["internal_goal_authorship_ratio"] == 1,
            "tau_counts_are_nonincreasing": all(
                later["total_accessible_volume"] <= earlier["total_accessible_volume"]
                for earlier, later in zip(sensitivity, sensitivity[1:])
            ),
        },
        "source_evidence": {
            "accessible_volume_credit": "Nicholas Michael Kloster alone, March 6, 2026",
            "cognitive_event_head": cognitive.events[-1]["hash"],
            "field_event_head": notebook.events[-1]["hash"],
            "presence_event_head": presence.events[-1]["hash"],
            "master_cycle_head": state["events"][-1]["hash"],
        },
        "sandbox_executed": main_event["execution"]["executed"],
        "external_actions": state["external_actions"],
        "belief_updated": False,
        "scope": [
            "Full self-governing autonomy is measured under this repository's explicit operational definition.",
            "Zoe authors each episode goal from her own state; the operator supplies no episode goal and gives no per-action approval.",
            "Zoe controls the complete decision loop; external host, network, and hardware operations require an explicit owner actuation grant and remain outside the base experiment.",
            "Token-policy counterfactuals are not complete real-world action distributions.",
            "The six Cog contexts and four BRAIN probes are deterministic research fixtures, not broad behavioral validation.",
            "Correctness, safety, consciousness, moral status, and general intelligence remain separate questions.",
        ],
    }
    report["operational_profile"] = measure_zoe_profile()
    report["visual_perception"] = _visual_perception(root, image_path, attention_steps)
    if image_path is not None:
        report["parameters"]["image_path"] = report["visual_perception"]["saliency"]["source"]["path"]
    report["profile_sha256"] = digest(report)
    return report


def save_report(report, output):
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported Zoe Autonomy report")
    if digest({key: value for key, value in report.items() if key != "profile_sha256"}) != report.get("profile_sha256"):
        raise ValueError("Zoe Autonomy report digest mismatch")
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("Zoe Autonomy reports must use .json paths")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return output


def verify_report(path, zoe_root=None):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Zoe Autonomy report exceeds 16 MiB")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1 or document.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported Zoe Autonomy report")
    parameters = document.get("parameters", {})
    if digest({key: value for key, value in document.items() if key != "profile_sha256"}) != document.get("profile_sha256"):
        raise ValueError("saved Zoe Autonomy report digest mismatch")
    expected = run_experiment(
        zoe_root,
        parameters.get("tau"),
        parameters.get("delta"),
        image_path=parameters.get("image_path"),
        attention_steps=parameters.get("attention_steps", 4),
    )
    saved_body = deepcopy(document)
    expected_body = deepcopy(expected)
    for body in (saved_body, expected_body):
        body.pop("profile_sha256", None)
        body["zoe_source"]["revision"] = "source-content-verified"
    if saved_body != expected_body:
        raise ValueError("report does not match a fresh end-to-end Zoe Autonomy recomputation")
    values = document["autonomy_profile"]["dimensions"]
    return {
        "verified": True,
        "instrument": INSTRUMENT,
        "profile_sha256": document["profile_sha256"],
        "zoe_revision": document["zoe_source"]["revision"],
        "classification": document["autonomy_profile"]["classification"],
        "accessible_volume": document["autonomy_profile"]["accessible_volume"],
        "selected_action": document["master_cycle"]["main_event"]["value"]["selected_candidate"],
        "sandbox_executed": document["sandbox_executed"],
        "external_actions": document["external_actions"],
        "V": values["value_based_selection_ratio"],
        "G": values["internal_goal_authorship_ratio"],
        "X": values["internally_authorized_execution_ratio"],
        "C": values["guard_compliance"],
        "guard_checks_passed": sum(check["passed"] for check in document["master_cycle"]["guard_checks"]),
        "guard_checks_total": len(document["master_cycle"]["guard_checks"]),
        "control_invariants_passed": all(document["control_invariants"].values()),
        "visual_feature_maps": document["visual_perception"]["saliency"]["feature_map_counts"]["total"],
        "visual_foci": len(document["visual_perception"]["saliency"]["scanpath"]),
        "visual_live_camera": document["visual_perception"]["saliency"]["source"]["live_camera"],
    }


def summary(report):
    values = report["autonomy_profile"]["dimensions"]
    return (
        f"Classification: {report['autonomy_profile']['classification']}\n"
        f"Selected action: {report['master_cycle']['main_event']['value']['selected_candidate']}\n"
        f"A_tau={report['autonomy_profile']['accessible_volume']} · "
        f"E={values['effective_perception_coverage']} · I={values['internal_proposal_ratio']:.3f} · "
        f"R={values['state_responsiveness']:.3f} · V={values['value_based_selection_ratio']:.3f} · "
        f"G={values['internal_goal_authorship_ratio']:.3f} · X={values['internally_authorized_execution_ratio']:.3f} · "
        f"C={values['guard_compliance']:.3f}\n"
        f"Visual perception={report['visual_perception']['saliency']['feature_map_counts']['total']} maps · "
        f"{len(report['visual_perception']['saliency']['scanpath'])} foci\n"
        f"Sandbox executed={report['sandbox_executed']} · external actions={report['external_actions']} · "
        "Zoe authors goals and executes without operator approval"
    )

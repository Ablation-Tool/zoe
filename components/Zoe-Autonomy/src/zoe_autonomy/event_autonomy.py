from __future__ import annotations

from copy import deepcopy
import math
import random

from .event_core import ACTIONS, EventEncoder, observation_window
from .event_memory import KeyValueEventMemory
from .event_plasticity import GatedLocalPlasticity
from .event_reasoning import ForwardEnsemble, attention_after, propose
from .event_uncertainty import IndependentUncertainty
from .loop import BoundedAutonomyLoop, SandboxPolicy, digest

EVENT_INSTRUMENT = "zoe-event-causal-active-perception/v1"


class EventEnvironment:
    def __init__(self):
        self._state = {
            "revision": 0,
            "attention": 0,
            "observations": [],
            "evidence": [],
            "inspections": [],
            "reviews": [],
            "model_updates": 0,
        }

    def snapshot(self):
        return deepcopy(self._state)

    def restore(self, snapshot):
        if not isinstance(snapshot, dict) or set(snapshot) != set(self._state):
            raise ValueError("invalid event-environment checkpoint")
        self._state = deepcopy(snapshot)

    def apply(self, candidate, measurement):
        before = self.snapshot()
        revision = before["revision"] + 1
        action = candidate.action
        self._state["attention"] = attention_after(self._state["attention"], action)
        self._state["revision"] = revision
        self._state["model_updates"] += int(measurement.get("plasticity_changed", False))
        transition = {
            "revision": revision,
            "action": action,
            "candidate_id": candidate.identifier,
            "attention_before": before["attention"],
            "attention_after": self._state["attention"],
            "measurement_sha256": digest(measurement),
            "reversible": True,
            "external_action": False,
        }
        self._state["observations"].append(transition)
        return {"before": before, "after": self.snapshot(), "transition": transition}


class EventLoop(BoundedAutonomyLoop):
    def goal_action(self):
        return "hold"

    def author_goal(self, measurement):
        state = self.environment.snapshot()
        observation = measurement["observation"]
        uncertainty = measurement["uncertainty"]
        if uncertainty["intervention"]:
            kind = "inspect_or_abstain"
            statement = "Inspect the anomalous event evidence and abstain from confident adaptation until uncertainty is acceptable."
            rationale = "The independent evaluator detected excessive event, support, or ensemble uncertainty."
        elif observation["event_count"] == 0:
            kind = "localize"
            statement = "Select a reversible attention trajectory that improves the chance of acquiring a new event source."
            rationale = "The current attention window contains no events."
        else:
            kind = "track"
            statement = "Predict the event source's next state and maintain informative attention with bounded model updates."
            rationale = "The current event stream supplies measurable motion and consequence evidence."
        goal = {
            "id": f"event-goal-{len(self.events) + 1}",
            "kind": kind,
            "statement": statement,
            "rationale": rationale,
            "authorship": "Zoe internal event-state assessment",
            "internal_authorship": True,
            "operator_supplied": False,
            "state_basis": {
                "revision": state["revision"],
                "attention": state["attention"],
                "event_count": observation["event_count"],
                "active_modules": observation["active_modules"],
                "uncertainty_score": uncertainty["score"],
            },
            "measurement_sha256": digest(measurement),
        }
        goal["sha256"] = digest(goal)
        return goal


class EventCausalEngine:
    def __init__(self, state_root=None, learning_enabled=True, forced_action=None, seed=0):
        if forced_action is not None and forced_action not in ACTIONS and forced_action != "random":
            raise ValueError("unsupported forced control action")
        self.environment = EventEnvironment()
        self.loop = EventLoop(policy=SandboxPolicy(allowed_actions=ACTIONS), environment=self.environment)
        self.encoder = EventEncoder()
        self.memory = KeyValueEventMemory(state_root)
        self.ensemble = ForwardEnsemble(history_enabled=bool(learning_enabled))
        self.uncertainty = IndependentUncertainty()
        self.plasticity = GatedLocalPlasticity()
        self.learning_enabled = bool(learning_enabled)
        self.forced_action = forced_action
        self.random = random.Random(seed)
        self.pending_episode = None
        self.last_prediction = None
        self.last_uncertainty = None
        self.observation_history = []
        self.step_reports = []

    def start_sequence(self):
        self.environment._state["attention"] = 0
        self.encoder.start_sequence()
        self.ensemble.start_sequence()
        self.pending_episode = None
        self.last_prediction = None
        self.last_uncertainty = None

    def fit_uncertainty(self):
        if not self.observation_history:
            raise ValueError("no observations are available for uncertainty fitting")
        return self.uncertainty.fit(self.observation_history)

    def _prediction_error(self, observation):
        if self.last_prediction is None or observation.get("centroid") is None:
            return {"signed_error": None, "absolute_error": None, "rmse": None}
        signed = observation["centroid"][0] - self.last_prediction["target_x"]
        return {"signed_error": signed, "absolute_error": abs(signed), "rmse": abs(signed)}

    def observe(self, events, step, learning=None):
        learn = self.learning_enabled if learning is None else bool(learning)
        before_model = self.ensemble.document()
        observation = self.encoder.encode(events, plastic=learn)
        self.observation_history.append(deepcopy(observation))
        prediction_error = self._prediction_error(observation)
        if learn and self.pending_episode is not None:
            previous = self.pending_episode
            delta = None
            if previous["centroid"] is not None and observation["centroid"] is not None:
                delta = observation["centroid"][0] - previous["centroid"][0]
            self.memory.add_episode(
                previous["feature_vector"], previous["action"],
                {
                    "observation": deepcopy(observation),
                    "step": step,
                    "delta_x": delta or 0.0,
                    "prediction_error": prediction_error["signed_error"],
                },
                {"previous_step": previous["step"], "transition": "selected action to next observed event representation"},
            )
        precheck = self.uncertainty.assess(observation, [])
        self.ensemble.update(observation, step, learning=learn and precheck["plasticity_allowed"])
        after_model = self.ensemble.document()
        plasticity_record = self.plasticity.update(
            self.ensemble, observation, self.last_prediction,
            {**precheck, "plasticity_allowed": learn and precheck["plasticity_allowed"]},
        )
        retrieved = self.memory.retrieve(observation["feature_vector"])
        proposals, details, trajectory = propose(self.ensemble, self.environment.snapshot()["attention"], precheck, retrieved)
        uncertainty = self.uncertainty.assess(observation, details)
        proposals, details, trajectory = propose(self.ensemble, self.environment.snapshot()["attention"], uncertainty, retrieved)
        selected_action = None
        if self.forced_action == "random":
            selected_action = self.random.choice(ACTIONS[:-1])
        elif self.forced_action is not None:
            selected_action = self.forced_action
        ranked = proposals if selected_action is None else [candidate for candidate in proposals if candidate.action == selected_action]
        measurement = {
            "instrument": EVENT_INSTRUMENT,
            "observation": observation,
            "uncertainty": uncertainty,
            "memory": self.memory.document(),
            "previous_prediction_error": prediction_error,
            "plasticity_changed": plasticity_record["changed"],
            "learning_enabled": learn,
        }
        perception = {
            "representation": "sparse polarity events with modular temporal integration",
            "actual_event_count": observation["event_count"],
            "source_sha256": observation["event_sha256"],
            "causal_input_to_goal_and_value": True,
        }
        belief = {
            "schema_version": 1,
            "previous": before_model,
            "current": after_model,
            "changed": before_model != after_model,
            "evidence": {"observation_sha256": observation["event_sha256"], "plasticity": plasticity_record},
        }
        event = self.loop.run(measurement, perception, ranked, belief_update=belief)
        selected = event["value"]["selected_candidate"]
        selected_detail = next(item for item in details if item["id"] == selected)
        self.last_prediction = deepcopy(selected_detail["prediction"])
        self.last_uncertainty = deepcopy(uncertainty)
        self.pending_episode = {
            "feature_vector": deepcopy(observation["feature_vector"]),
            "action": selected_detail["action"],
            "centroid": deepcopy(observation["centroid"]),
            "step": step,
        }
        report = {
            "step": step,
            "observation": observation,
            "prediction_error": prediction_error,
            "candidate_details": details,
            "trajectory": trajectory,
            "uncertainty": uncertainty,
            "selected_prediction": self.last_prediction,
            "selected_action": selected_detail["action"],
            "attention_after": self.environment.snapshot()["attention"],
            "plasticity": plasticity_record,
            "memory": self.memory.document(),
            "event": event,
            "external_actions": self.loop.external_actions,
        }
        self.step_reports.append(deepcopy(report))
        return report

    def run_sequence(self, sequence, learning=None):
        self.start_sequence()
        steps = sequence["steps"]
        return [
            self.observe(observation_window(sequence["events"], step, self.environment.snapshot()["attention"]), step, learning)
            for step in range(steps)
        ]

    def document(self):
        return {
            "instrument": EVENT_INSTRUMENT,
            "forward_model": self.ensemble.document(),
            "memory": self.memory.document(),
            "uncertainty": self.uncertainty.document(),
            "plasticity": self.plasticity.document(),
            "loop_state": self.loop.state(),
            "observation_count": len(self.observation_history),
            "learning_enabled": self.learning_enabled,
            "external_actions": self.loop.external_actions,
        }


def prediction_metrics(reports, targets):
    squared = []
    tracking = []
    rows = []
    for report in reports:
        next_index = min(report["step"] + 1, len(targets) - 1)
        actual = targets[next_index]
        predicted = report["selected_prediction"]["target_x"]
        squared.append((predicted - actual) ** 2)
        tracking.append(abs(report["attention_after"] * 4 + 4 - actual))
        rows.append({"step": report["step"], "predicted": predicted, "actual": actual, "attention": report["attention_after"] * 4 + 4})
    return {
        "prediction_rmse": math.sqrt(math.fsum(squared) / len(squared)) if squared else None,
        "tracking_mae": math.fsum(tracking) / len(tracking) if tracking else None,
        "rows": rows,
    }

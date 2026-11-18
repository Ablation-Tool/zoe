from __future__ import annotations

from copy import deepcopy
import math

from .loop import digest

PLASTICITY_INSTRUMENT = "zoe-gated-local-event-plasticity/v1"


class GatedLocalPlasticity:
    def __init__(self, learning_rate=.05, bound=2.0):
        if not 0 < learning_rate <= 1 or not 0 < bound <= 100:
            raise ValueError("plasticity learning rate and bound must be positive and bounded")
        self.learning_rate = float(learning_rate)
        self.bound = float(bound)
        self.adapters = [0.0] * 4
        self.history = []

    def checkpoint(self):
        return {"adapters": deepcopy(self.adapters), "history": deepcopy(self.history)}

    def restore(self, checkpoint):
        self.adapters = deepcopy(checkpoint["adapters"])
        self.history = deepcopy(checkpoint["history"])

    def update(self, ensemble, observation, prediction, uncertainty):
        before = deepcopy(self.adapters)
        error = None
        if observation.get("centroid") is not None and prediction and prediction.get("target_x") is not None:
            error = float(observation["centroid"][0]) - float(prediction["target_x"])
        modules = observation.get("active_modules") or []
        gated = bool(
            error is not None
            and abs(error) >= .05
            and modules
            and uncertainty.get("plasticity_allowed")
        )
        changed = False
        if gated:
            rate = self.learning_rate * error / len(modules)
            for module in modules:
                self.adapters[module] = max(-self.bound, min(self.bound, self.adapters[module] + rate))
            for member in ensemble.members:
                direction = member.get("current_direction")
                if direction:
                    prior = member["learned_dynamics"].get(direction, 0.0)
                    updated = max(-4.0, min(4.0, prior + self.learning_rate * error))
                    member["learned_dynamics"][direction] = updated
                    member["learned_velocity"] = updated
                    member["velocity"] = updated
            changed = self.adapters != before
        record = {
            "instrument": PLASTICITY_INSTRUMENT,
            "gated": gated,
            "changed": changed,
            "prediction_error": error,
            "instructive_modules": modules,
            "uncertainty_score": uncertainty["score"],
            "adapters_before": before,
            "adapters_after": deepcopy(self.adapters),
            "credit_assignment_separate_from_storage": True,
        }
        record["sha256"] = digest(record)
        self.history.append(record)
        self.history = self.history[-200:]
        return deepcopy(record)

    def consolidate(self, ensemble, memory, validator):
        before_ensemble = ensemble.checkpoint()
        before_plasticity = self.checkpoint()
        baseline = validator(ensemble)
        replay = memory.replay_batch()
        for episode in replay:
            outcome = episode["value"]
            ensemble.update(outcome["observation"], outcome["step"], learning=True)
        candidate = validator(ensemble)
        adopted = (
            candidate["recent_rmse"] < baseline["recent_rmse"]
            and candidate["familiar_rmse"] <= baseline["familiar_rmse"] + .05
        )
        if not adopted:
            ensemble.restore(before_ensemble)
            self.restore(before_plasticity)
        record = {
            "instrument": PLASTICITY_INSTRUMENT,
            "operation": "interleaved_replay_consolidation",
            "replay_count": len(replay),
            "baseline": baseline,
            "candidate": candidate,
            "adopted": adopted,
            "restored_checkpoint": not adopted,
            "reversible": True,
        }
        record["sha256"] = digest(record)
        self.history.append(record)
        self.history = self.history[-200:]
        return deepcopy(record)

    def document(self):
        return {
            "instrument": PLASTICITY_INSTRUMENT,
            "learning_rate": self.learning_rate,
            "bound": self.bound,
            "adapters": deepcopy(self.adapters),
            "update_count": sum(item.get("changed", False) for item in self.history),
            "history": deepcopy(self.history),
            "credit_assignment_separate_from_storage": True,
        }

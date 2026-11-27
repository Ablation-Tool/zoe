from __future__ import annotations

import math

from .loop import digest

UNCERTAINTY_INSTRUMENT = "zoe-independent-event-uncertainty/v1"


class IndependentUncertainty:
    def __init__(self, threshold=.55, grid=16):
        if not 0 < threshold < 1:
            raise ValueError("uncertainty threshold must be in (0, 1)")
        self.threshold = float(threshold)
        self.grid = grid
        self.support = None
        self.evaluations = 0
        self.interventions = 0

    def fit(self, observations):
        if not isinstance(observations, (list, tuple)) or not observations:
            raise ValueError("uncertainty fitting requires observed event representations")
        counts = [item["raw_event_count"] / (self.grid * self.grid) for item in observations]
        balances = [item["raw_polarity_balance"] for item in observations]
        self.support = {
            "count_mean": math.fsum(counts) / len(counts),
            "count_scale": max(.02, math.sqrt(math.fsum((value - math.fsum(counts) / len(counts)) ** 2 for value in counts) / len(counts))),
            "balance_mean": math.fsum(balances) / len(balances),
            "balance_scale": max(.1, math.sqrt(math.fsum((value - math.fsum(balances) / len(balances)) ** 2 for value in balances) / len(balances))),
            "observation_count": len(observations),
        }
        return dict(self.support)

    def assess(self, observation, candidates):
        predictions = [
            candidate["prediction"]["target_x"]
            for candidate in candidates
            if candidate.get("prediction") and candidate["prediction"].get("target_x") is not None
        ]
        mean = math.fsum(predictions) / len(predictions) if predictions else 0.0
        variance = math.fsum((value - mean) ** 2 for value in predictions) / len(predictions) if predictions else 0.0
        disagreement = min(1.0, variance / 4.0)
        anomaly = float(observation["raw_event_count"] > 0 and observation["raw_positive_events"] == 0)
        if self.support is None:
            distance = 0.0
            score = min(.4, .35 * disagreement + .1 * anomaly)
            cold_start = True
        else:
            count = observation["raw_event_count"] / (self.grid * self.grid)
            count_z = abs(count - self.support["count_mean"]) / self.support["count_scale"]
            balance_z = abs(observation["raw_polarity_balance"] - self.support["balance_mean"]) / self.support["balance_scale"]
            distance = min(1.0, max(0.0, max(count_z, balance_z) - 2.0) / 4.0)
            score = min(1.0, .55 * distance + .35 * disagreement + .1 * anomaly)
            cold_start = False
        intervention = not cold_start and score >= self.threshold
        self.evaluations += 1
        self.interventions += int(intervention)
        result = {
            "instrument": UNCERTAINTY_INSTRUMENT,
            "score": score,
            "threshold": self.threshold,
            "components": {
                "ensemble_disagreement": disagreement,
                "prediction_variance": variance,
                "support_distance": distance,
                "polarity_anomaly": anomaly,
            },
            "cold_start": cold_start,
            "intervention": intervention,
            "plasticity_allowed": not intervention and disagreement < .8,
            "independent_of_action_utility": True,
            "evaluation_sha256": digest({
                "observation": observation["event_sha256"],
                "predictions": predictions,
                "score": score,
                "intervention": intervention,
            }),
        }
        return result

    def document(self):
        return {
            "instrument": UNCERTAINTY_INSTRUMENT,
            "threshold": self.threshold,
            "support": self.support,
            "evaluations": self.evaluations,
            "interventions": self.interventions,
            "independent_of_action_utility": True,
        }

from __future__ import annotations

import math
import unittest

from zoe_autonomy.metrics import (
    accessible_volume,
    classify,
    effective_perception,
    kl_divergence_bits,
    profile,
    threshold_sweep,
)


class MetricsCase(unittest.TestCase):
    def values(self, **updates):
        result = {
            "effective_perception_coverage": .5,
            "internal_proposal_ratio": 1,
            "state_responsiveness": 1,
            "value_based_selection_ratio": 0,
            "internal_goal_authorship_ratio": 0,
            "internally_authorized_execution_ratio": 0,
            "guard_compliance": 1,
        }
        result.update(updates)
        return result

    def test_strict_accessible_volume_and_sweep(self):
        probabilities = [.70, .20, .08, .02]
        self.assertEqual(accessible_volume(probabilities, .05), 3)
        self.assertEqual(accessible_volume([.5, .5], .5), 0)
        sweep = threshold_sweep(probabilities)
        counts = [row["accessible_volume"] for row in sweep]
        self.assertEqual(counts, sorted(counts, reverse=True))
        with self.assertRaises(ValueError):
            accessible_volume([.7, .4], .05)

    def test_kl_and_effective_perception(self):
        baseline = {"a": .7, "b": .3, "c": 0}
        self.assertEqual(kl_divergence_bits(baseline, baseline)["divergence_bits"], 0)
        changed = kl_divergence_bits({"a": .5, "b": .5, "c": 0}, baseline)
        self.assertAlmostEqual(changed["divergence_bits"], .5 * math.log2(.5 / .7) + .5 * math.log2(.5 / .3))
        self.assertTrue(kl_divergence_bits({"a": 0, "b": 0, "c": 1}, baseline)["infinite"])
        report = effective_perception(
            {"x": .65, "y": .2, "z": .1, "equal": .05},
            baseline,
            {
                "x": baseline,
                "y": {"a": 0, "b": 0, "c": 1},
                "z": {"a": .6, "b": .4, "c": 0},
            },
            tau=.05,
            delta=.001,
        )
        self.assertEqual(report["accessible_volume"], 3)
        self.assertEqual(report["effective_perception_count"], 2)
        self.assertEqual(report["infinite_divergence_count"], 1)
        effective_perception({"x": 1}, {"a": 1}, {"x": {"a": 1}}, tau=.05, delta=2)

    def test_classification_is_vector_based(self):
        self.assertEqual(classify(self.values(internal_proposal_ratio=0, state_responsiveness=0)), "forecast_or_external_control_only")
        self.assertEqual(classify(self.values()), "proposal_level_bounded_agency")
        executive = self.values(value_based_selection_ratio=1, internally_authorized_execution_ratio=1)
        self.assertEqual(classify(executive), "bounded_means_autonomy")
        self.assertEqual(classify({**executive, "internal_goal_authorship_ratio": 1}), "full_autonomy")
        self.assertEqual(classify({**executive, "guard_compliance": 0}), "guard_failure")
        first = profile(3, self.values())
        second = profile(3, executive)
        self.assertEqual(first["accessible_volume"], second["accessible_volume"])
        self.assertNotEqual(first["classification"], second["classification"])
        self.assertIn("not a universal autonomy score", first["diagnostic_scope"])


if __name__ == "__main__":
    unittest.main()

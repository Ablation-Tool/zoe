from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from guiai.gem.autonomy import (
    DIMENSIONS,
    autonomy_profile,
    classify_autonomy,
    effective_perception,
    kl_divergence_bits,
    measure_zoe_profile,
    save_profile,
    verify_profile,
)
from guiai.gem.autonomy_view import main as autonomy_main
from guiai.gem.cli import main as gem_main
from guiai.gem.unified_cli import main as zoe_main


class AutonomyMathCase(unittest.TestCase):
    def dimensions(self, **updates):
        values = {
            "internal_proposal_ratio": 1.0,
            "state_responsiveness": 1.0,
            "effective_perception_coverage": .5,
            "value_based_selection_ratio": 0.0,
            "internal_goal_authorship_ratio": 0.0,
            "internally_authorized_execution_ratio": 0.0,
            "guard_compliance": 1.0,
        }
        values.update(updates)
        return values

    def test_kl_divergence_support_and_validation(self):
        baseline = {"a": .9, "b": .1}
        same = kl_divergence_bits(baseline, baseline)
        self.assertEqual(same["divergence_bits"], 0)
        changed = kl_divergence_bits({"a": .5, "b": .5}, baseline)
        self.assertAlmostEqual(changed["divergence_bits"], .5 * math.log2(.5 / .9) + .5 * math.log2(.5 / .1))
        infinite = kl_divergence_bits({"a": 1, "b": 0}, {"a": 0, "b": 1})
        self.assertTrue(infinite["infinite"])
        self.assertIsNone(infinite["divergence_bits"])
        for first, second in (
            ({"a": .5, "b": .5}, {"a": 1}),
            ({"a": .5, "b": .6}, {"a": .5, "b": .5}),
            ({"a": True, "b": False}, {"a": 1, "b": 0}),
        ):
            with self.assertRaises(ValueError):
                kl_divergence_bits(first, second)

    def test_effective_perception_uses_strict_thresholds(self):
        report = effective_perception(
            {"x": .65, "y": .2, "z": .1, "at-tau": .05},
            {"a": .7, "b": .3, "c": 0},
            {
                "x": {"a": .7, "b": .3, "c": 0},
                "y": {"a": 0, "b": 0, "c": 1},
                "z": {"a": .6, "b": .4, "c": 0},
            },
            tau=.05,
            delta=.001,
        )
        self.assertEqual(report["accessible_volume"], 3)
        self.assertEqual(report["effective_perception_count"], 2)
        self.assertAlmostEqual(report["effective_perception_coverage"], 2 / 3)
        self.assertEqual(report["infinite_divergence_count"], 1)
        self.assertNotIn("at-tau", {record["intervention"] for record in report["interventions"]})
        self.assertFalse(report["interventions"][0]["effective"])
        with self.assertRaises(ValueError):
            effective_perception({"x": 1}, {"a": 1}, {}, tau=.05)

    def test_equal_breadth_does_not_erase_control_differences(self):
        probabilities = [.70, .20, .08, .02]
        external = autonomy_profile(probabilities, self.dimensions(
            internal_proposal_ratio=0,
            state_responsiveness=0,
        ))
        proposal = autonomy_profile(probabilities, self.dimensions())
        executive = autonomy_profile(probabilities, self.dimensions(
            value_based_selection_ratio=1,
            internally_authorized_execution_ratio=1,
        ))
        self_governing = autonomy_profile(probabilities, self.dimensions(
            value_based_selection_ratio=1,
            internally_authorized_execution_ratio=1,
            internal_goal_authorship_ratio=1,
        ))
        self.assertEqual(external["accessible_volume"], 3)
        self.assertEqual(proposal["accessible_volume"], 3)
        self.assertEqual(executive["accessible_volume"], 3)
        self.assertEqual(external["classification"], "forecast_or_external_control_only")
        self.assertEqual(proposal["classification"], "proposal_level_bounded_agency")
        self.assertEqual(executive["classification"], "bounded_means_autonomy")
        self.assertEqual(self_governing["classification"], "bounded_self_governing_autonomy")
        self.assertGreater(proposal["deliberative_coverage_geometric_mean"], external["deliberative_coverage_geometric_mean"])
        failed = autonomy_profile(probabilities, self.dimensions(
            value_based_selection_ratio=1,
            internally_authorized_execution_ratio=1,
            guard_compliance=0,
        ))
        self.assertEqual(failed["classification"], "guard_failure")

    def test_threshold_changes_breadth_without_changing_control_dimensions(self):
        dimensions = self.dimensions()
        first = autonomy_profile([.70, .20, .08, .02], dimensions, tau=.05)
        second = autonomy_profile([.70, .20, .08, .02], dimensions, tau=.15)
        self.assertEqual((first["accessible_volume"], second["accessible_volume"]), (3, 2))
        self.assertEqual(first["dimensions"], second["dimensions"])
        self.assertEqual(first["classification"], second["classification"])
        self.assertEqual(set(DIMENSIONS), set(first["dimensions"]))
        with self.assertRaises(ValueError):
            classify_autonomy(self.dimensions(guard_compliance=2))


class ZoeAutonomyEvidenceCase(unittest.TestCase):
    def test_real_zoe_profile_and_controls(self):
        report = measure_zoe_profile()
        self.assertEqual(report, measure_zoe_profile())
        profile = report["zoe_profile"]
        dimensions = profile["dimensions"]
        self.assertEqual(profile["classification"], "proposal_level_bounded_agency")
        self.assertEqual(profile["accessible_volume"], report["effective_perception"]["accessible_volume"])
        self.assertEqual(dimensions["internal_proposal_ratio"], 1)
        self.assertEqual(dimensions["state_responsiveness"], 1)
        self.assertEqual(dimensions["value_based_selection_ratio"], 0)
        self.assertEqual(dimensions["internal_goal_authorship_ratio"], 0)
        self.assertEqual(dimensions["internally_authorized_execution_ratio"], 0)
        self.assertEqual(dimensions["guard_compliance"], 1)
        self.assertTrue(all(report["control_invariants"].values()))
        self.assertEqual(report["observed_behavior"]["distinct_brain_recommendations"], 4)
        suite = report["counterfactual_suite"]
        self.assertEqual(len(suite["contexts"]), 6)
        total_volume = sum(item["effective_perception"]["accessible_volume"] for item in suite["contexts"])
        total_effective = sum(item["effective_perception"]["effective_perception_count"] for item in suite["contexts"])
        self.assertEqual(suite["aggregate"]["total_accessible_volume"], total_volume)
        self.assertEqual(suite["aggregate"]["total_effective_perception_count"], total_effective)
        self.assertEqual(suite["aggregate"]["micro_effective_perception_coverage"], total_effective / total_volume)
        self.assertEqual(dimensions["effective_perception_coverage"], total_effective / total_volume)
        self.assertEqual(report["observed_behavior"]["counterfactual_contexts"], 6)
        sensitivity = suite["sensitivity"]
        self.assertEqual(len(sensitivity["tau_sweep"]), 6)
        self.assertEqual(len(sensitivity["delta_sweep"]), 7)
        tau_volumes = [row["total_accessible_volume"] for row in sensitivity["tau_sweep"]]
        delta_effects = [row["total_effective_perception_count"] for row in sensitivity["delta_sweep"]]
        self.assertEqual(tau_volumes, sorted(tau_volumes, reverse=True))
        self.assertEqual(delta_effects, sorted(delta_effects, reverse=True))
        self.assertGreater(tau_volumes[0], tau_volumes[-1])
        self.assertEqual(report["observed_behavior"]["internally_authorized_executions"], 0)
        self.assertEqual(report["external_actions"], 0)
        self.assertFalse(report["executed"])
        self.assertEqual(len(report["profile_sha256"]), 64)
        for control in report["controls"].values():
            self.assertEqual(control["accessible_volume"], profile["accessible_volume"])
            self.assertTrue(control["simulation_only"])
            self.assertEqual(control["external_actions"], 0)

    def test_no_overwrite_replay_and_tamper_rejection(self):
        report = measure_zoe_profile()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            self.assertEqual(save_profile(report, path), path)
            verification = verify_profile(path)
            self.assertTrue(verification["verified"])
            self.assertTrue(verification["control_invariants_passed"])
            self.assertEqual(verification["guard_checks_passed"], verification["guard_checks_total"])
            self.assertFalse(verification["executed"])
            with self.assertRaises(FileExistsError):
                save_profile(report, path)
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["zoe_profile"]["classification"] = "bounded_self_governing_autonomy"
            path.write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "independent Zoe recomputation"):
                verify_profile(path)

    def test_direct_and_forwarded_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct = root / "direct.json"
            gem = root / "gem.json"
            zoe = root / "zoe.json"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(autonomy_main(["--output", str(direct)]), 0)
                self.assertIn("proposal_level_bounded_agency", output.getvalue())
                self.assertEqual(gem_main(["autonomy", "--output", str(gem)]), 0)
                self.assertEqual(zoe_main(["autonomy", "--output", str(zoe)]), 0)
                for path in (direct, gem, zoe):
                    self.assertEqual(autonomy_main(["--verify", str(path)]), 0)
            self.assertEqual(json.loads(direct.read_text(encoding="utf-8")), json.loads(gem.read_text(encoding="utf-8")))
            self.assertEqual(json.loads(direct.read_text(encoding="utf-8")), json.loads(zoe.read_text(encoding="utf-8")))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(autonomy_main(["--verify", str(direct), "--output", str(root / "invalid.json")]), 2)


if __name__ == "__main__":
    unittest.main()

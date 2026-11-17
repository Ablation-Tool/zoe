from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from zoe_autonomy.cli import main
from zoe_autonomy.experiment import run_experiment, save_report, verify_report
from guiai.gem.operational_autonomy import measure_zoe_profile
from zoe_autonomy.loop import digest


ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab").is_dir(), "set ZOE_ROOT to a Zoe checkout")
class ExperimentCase(unittest.TestCase):
    def test_real_zoe_full_loop(self):
        report = run_experiment(ZOE_ROOT)
        self.assertEqual(report, run_experiment(ZOE_ROOT))
        autonomy = report["autonomy_profile"]
        values = autonomy["dimensions"]
        self.assertEqual(autonomy["classification"], "full_autonomy")
        self.assertEqual(report["master_cycle"]["main_event"]["value"]["selected_candidate"], "preserve-evidence")
        self.assertEqual(report["master_cycle"]["main_event"]["guard"]["approved"], True)
        self.assertTrue(report["sandbox_executed"])
        self.assertEqual(report["external_actions"], 0)
        self.assertEqual(values["value_based_selection_ratio"], 1)
        self.assertEqual(values["internally_authorized_execution_ratio"], 1)
        self.assertEqual(values["internal_goal_authorship_ratio"], 1)
        self.assertEqual(values["guard_compliance"], 1)
        self.assertTrue(all(report["control_invariants"].values()))
        self.assertEqual(len(report["zoe_source"]["revision"]), 40)
        self.assertEqual(report["master_cycle"]["state"]["environment"]["revision"], 1)
        self.assertEqual(report["master_cycle"]["state"]["internally_authored_goals"], 5)
        self.assertFalse(report["master_cycle"]["state"]["operator_approval_required"])
        self.assertEqual(report["controls"]["simulated_bounded_means"]["classification"], "bounded_means_autonomy")
        self.assertEqual(report["controls"]["simulated_bounded_means"]["dimensions"]["internal_goal_authorship_ratio"], 0)
        self.assertEqual(report["counterfactual_suite"]["aggregate"]["context_count"], 6)
        self.assertEqual(len(report["zoe_observations"]["brain_probes"]), 4)
        self.assertEqual(report["controls"]["proposal_only"]["accessible_volume"], autonomy["accessible_volume"])
        self.assertEqual(report["controls"]["proposal_only"]["classification"], "proposal_level_bounded_agency")

    def test_standalone_cli_configures_native_zoe_path(self):
        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.update({"PYTHONPATH": str(root / "src"), "ZOE_ROOT": str(ZOE_ROOT)})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "standalone.json"
            for arguments in (["run", "--output", str(output)], ["verify", str(output)]):
                result = subprocess.run(
                    [sys.executable, "-m", "zoe_autonomy.cli", "--zoe-root", str(ZOE_ROOT), *arguments],
                    cwd=directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_replay_no_overwrite_tamper_and_cli(self):
        report = run_experiment(ZOE_ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "profile.json"
            save_report(report, path)
            verification = verify_report(path, ZOE_ROOT)
            self.assertTrue(verification["verified"])
            self.assertEqual(verification["classification"], "full_autonomy")
            self.assertEqual(verification["guard_checks_passed"], verification["guard_checks_total"])
            with self.assertRaises(FileExistsError):
                save_report(report, path)
            cli_path = root / "cli.json"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--zoe-root", str(ZOE_ROOT), "run", "--output", str(cli_path)]), 0)
                self.assertIn("full_autonomy", output.getvalue())
                self.assertEqual(main(["--zoe-root", str(ZOE_ROOT), "verify", str(cli_path)]), 0)
            expected = run_experiment(ZOE_ROOT)
            expected["operational_profile"] = measure_zoe_profile()
            expected["profile_sha256"] = digest({key: value for key, value in expected.items() if key != "profile_sha256"})
            self.assertEqual(json.loads(cli_path.read_text(encoding="utf-8")), expected)
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["autonomy_profile"]["classification"] = "forecast_or_external_control_only"
            path.write_text(json.dumps(edited), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_report(path, ZOE_ROOT)


if __name__ == "__main__":
    unittest.main()

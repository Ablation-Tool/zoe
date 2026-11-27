from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


class AutonomyCase(unittest.TestCase):
    def test_shared_full_autonomy_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.json"
            environment = os.environ.copy()
            bundled = WORKSPACE.name == "components" and (WORKSPACE.parent / "guiai-lab").is_dir()
            zoe_root = WORKSPACE.parent if bundled else WORKSPACE / "zoe"
            environment.update({
                "PYTHONPATH": str(ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
                "ZOE_ROOT": str(zoe_root),
                "ZOE_AUTONOMY_ROOT": str(WORKSPACE / "Zoe-Autonomy"),
            })
            for arguments in (["run", "--output", str(output)], ["verify", str(output)]):
                result = subprocess.run(
                    [sys.executable, "-m", "cerotto_gem.cli", "autonomy", *arguments],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["autonomy_profile"]["classification"], "full_autonomy")
            values = report["autonomy_profile"]["dimensions"]
            self.assertEqual(values["internal_goal_authorship_ratio"], 1)
            self.assertEqual(values["internally_authorized_execution_ratio"], 1)
            self.assertEqual(values["guard_compliance"], 1)
            self.assertEqual(report["external_actions"], 0)


if __name__ == "__main__":
    unittest.main()

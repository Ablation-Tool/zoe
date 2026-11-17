#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def revision(path):
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"unable to read revision for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify the coordinated Zoe One GEM host set")
    parser.add_argument("--workspace", type=Path, default=ROOT.parent)
    parser.add_argument("--output", help="new JSON verification path")
    arguments = parser.parse_args(argv)
    workspace = arguments.workspace.expanduser().resolve()
    manifest = json.loads((ROOT / "one-system.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1 or manifest["system"] != "Zoe One":
        raise ValueError("unsupported Zoe One manifest")
    checked_revisions = {}
    for item in [manifest["canonical_engine"], manifest["research"], *manifest["hosts"]]:
        path = workspace / item["directory"]
        actual = revision(path)
        if actual != item["revision"]:
            raise ValueError(f"{item['id']} revision mismatch: {actual} != {item['revision']}")
        checked_revisions[item["id"]] = actual
    reports = {}
    with tempfile.TemporaryDirectory(prefix="zoe-one-") as directory:
        temporary = Path(directory)
        for host in [manifest["canonical_engine"], *manifest["hosts"]]:
            checkout = workspace / host["directory"]
            cwd = checkout / host.get("cwd", ".")
            output = temporary / f"{host['id']}.json"
            environment = os.environ.copy()
            environment["ZOE_ROOT"] = str(workspace / "zoe")
            environment["ZOE_AUTONOMY_ROOT"] = str(workspace / "Zoe-Autonomy")
            environment["PYTHONPATH"] = str(cwd / host["python_path"])
            command = [sys.executable, "-m", host["module"], *host.get("command_prefix", []), "run", "--output", str(output)]
            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode:
                raise ValueError(f"{host['id']} failed: {result.stdout}\n{result.stderr}")
            report = json.loads(output.read_text(encoding="utf-8"))
            values = report["autonomy_profile"]["dimensions"]
            event = report["master_cycle"]["main_event"]
            assert report["autonomy_profile"]["classification"] == "full_autonomy", host["id"]
            assert values["internal_goal_authorship_ratio"] == 1, host["id"]
            assert values["value_based_selection_ratio"] == 1, host["id"]
            assert values["internally_authorized_execution_ratio"] == 1, host["id"]
            assert values["guard_compliance"] == 1, host["id"]
            assert event["goal"]["internal_authorship"] and not event["goal"]["operator_supplied"], host["id"]
            assert not event["operator_approval_required"], host["id"]
            assert report["sandbox_executed"] and report["external_actions"] == 0, host["id"]
            assert all(report["control_invariants"].values()), host["id"]
            reports[host["id"]] = report
    reference = reports[manifest["canonical_engine"]["id"]]
    for identifier, report in reports.items():
        if report != reference:
            raise ValueError(f"{identifier} produced a different canonical autonomy profile")
    result = {
        "schema_version": 1,
        "system": "Zoe One",
        "contract": manifest["contract"],
        "verified": True,
        "hosts": list(reports),
        "host_count": len(reports),
        "revisions": checked_revisions,
        "classification": "full_autonomy",
        "profile_sha256": reference["profile_sha256"],
        "identical_canonical_profiles": True,
        "internal_goal_authorship": True,
        "operator_approval_required": False,
        "sandbox_executed": True,
        "external_actions": 0,
    }
    if arguments.output:
        output = Path(arguments.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

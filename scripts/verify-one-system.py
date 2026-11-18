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
    parser.add_argument("--image", help="verify the same RGB image through every host")
    parser.add_argument("--foci", type=int, default=4, help="attention selections per host, from 1 to 8")
    parser.add_argument("--reflect", action="store_true", help="verify measured self-reflection in every host")
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.foci <= 8:
        raise ValueError("foci must be from 1 to 8")
    image = Path(arguments.image).expanduser().resolve(strict=True) if arguments.image else None
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
            if image is not None:
                command.extend(["--image", str(image), "--foci", str(arguments.foci)])
            if arguments.reflect:
                command.append("--reflect")
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
            replay = subprocess.run(
                [sys.executable, "-m", host["module"], *host.get("command_prefix", []), "verify", str(output)],
                cwd=cwd, env=environment, capture_output=True, text=True, timeout=120, check=False,
            )
            if replay.returncode:
                raise ValueError(f"{host['id']} replay failed: {replay.stdout}\n{replay.stderr}")
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
            visual = report["visual_perception"]["saliency"]
            expected_kind = "image_file" if arguments.image else "documented_synthetic_rgb_popout"
            assert visual["feature_map_counts"]["total"] == 42, host["id"]
            assert visual["source"]["kind"] == expected_kind, host["id"]
            assert visual["source"]["live_camera"] is False, host["id"]
            assert len(visual["scanpath"]) <= arguments.foci, host["id"]
            expected_revision = next(item["revision"] for item in manifest["hosts"] if item["id"] == "canonical-gem")
            assert report["visual_perception"]["locked_revision"] == expected_revision, host["id"]
            if arguments.reflect:
                assert report["belief_updated"] is True, host["id"]
                assert report["self_reflection"]["event"]["hash"] == event["hash"], host["id"]
                assert event["goal"]["target_action"] == "preserve", host["id"]
                assert report["self_reflection"]["event"]["belief_update"]["changed"] is True, host["id"]
            else:
                assert report["belief_updated"] is False, host["id"]
                assert "self_reflection" not in report, host["id"]
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
        "self_reflection": {
            "enabled": arguments.reflect,
            "selected_model": reference.get("self_reflection", {}).get("self_model", {}).get("selected_model"),
            "belief_updated": reference["belief_updated"],
            "replay_verified": True,
        },
        "visual_perception": {
            "feature_maps": 42,
            "foci": len(reference["visual_perception"]["saliency"]["scanpath"]),
            "source_kind": reference["visual_perception"]["saliency"]["source"]["kind"],
            "image_sha256": reference["visual_perception"]["saliency"]["source"].get("sha256"),
            "live_camera": False,
            "replay_verified": True,
        },
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

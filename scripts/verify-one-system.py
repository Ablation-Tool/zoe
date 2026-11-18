#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def git(*arguments, check=True):
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        check=check,
    ).stdout.strip()


def verify_import(item):
    path = ROOT / "components" / item["directory"]
    if not path.is_dir():
        raise ValueError(f"{item['id']} is missing from the unified checkout: {path}")
    source_revision = item["revision"]
    included = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", source_revision, "HEAD"],
        capture_output=True,
        timeout=30,
        check=False,
    ).returncode == 0
    if not included:
        raise ValueError(f"{item['id']} source revision is not included in Zoe history: {source_revision}")
    return source_revision


def verify_chat(manifest):
    checkout = ROOT / "components" / "Zoe-Autonomy"
    environment = os.environ.copy()
    environment["ZOE_ROOT"] = str(ROOT)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join([str(checkout / "src"), str(ROOT / "guiai-lab")])
    temporary_parent = Path(os.environ.get("ZOE_CHAT_VERIFY_TMP", "/dev/shm"))
    temporary_parent = temporary_parent if temporary_parent.is_dir() else None
    records = []
    with tempfile.TemporaryDirectory(prefix="zoe-chat-verification-", dir=temporary_parent) as directory:
        state = Path(directory) / "state"
        pala_report = Path(directory) / "pala-report.json"
        pala_report.write_text(json.dumps({
            "source": str(Path(directory) / "historical-disk.img"),
            "source_bytes": 2048,
            "found": 1,
            "findings": [{
                "offset": 512,
                "type": "jpeg",
                "extension": "jpg",
                "size": 1024,
                "quality": "complete",
                "sha256": "a" * 64,
                "path": str(Path(directory) / "out" / "jpg_0001.jpg"),
            }],
        }), encoding="utf-8")
        cases = [
            ("evidence_answer", "what is PALA?", ("read-only", "CAPABILITY-ATLAS.md:")),
            ("insufficient_evidence", "what is a zqfrangible inverse owlet?", ("do not have enough indexed evidence",)),
            ("intent_breadth", "meta what is PALA?", ("Aτ(intent)", "boxed=False", "computed_on_request=True")),
            ("pala_import", f"import-pala {pala_report}", ("Imported PALA report metadata", "contents were not read")),
            ("pala_recall", "recall jpeg", ("memory:",)),
            ("undo_pala_import", "undo", ("marked undone",)),
            ("plan", "plan", ("Goal authored internally=True", "Aτ(action)=3", "No plan was executed")),
            ("reflect", "reflect", ("belief_updated=True", "Aτ(self)=2", "Evidence:")),
            ("self_breadth", "meta self", ("Aτ(self)=2", "boxed=False")),
            ("run", "run", ("Guard approved=True", "external actions=0", "Aτ(action)=3")),
            ("undo", "undo", ("restored to revision",)),
            ("export", "export", ("Evidence saved on explicit request:", "automatic_transcript=False")),
            ("no_notebook", "history", ("no automatic conversation notebook",)),
            ("stop", "stop", ("New state-changing actions are stopped",)),
            ("status", "status", ("monitor=False · notebook=False", "actions_stopped=True")),
        ]
        export_path = None
        for name, command, required in cases:
            completed = subprocess.run(
                [sys.executable, "-m", "zoe_autonomy.chat", "--state", str(state), "--command", command],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            output = completed.stdout + completed.stderr
            if completed.returncode:
                raise ValueError(f"Zoe chat {name} failed:\n{output[-8000:]}")
            missing = [fragment for fragment in required if fragment not in output]
            if missing:
                raise ValueError(f"Zoe chat {name} is missing {missing}:\n{output[-8000:]}")
            if name == "export":
                export_path = output.split("Evidence saved on explicit request: ", 1)[1].split(" · ", 1)[0]
            records.append({"name": name, "command": command, "returncode": completed.returncode})
        for forbidden in ("events.jsonl", "metacognition.json"):
            if (state / forbidden).exists():
                raise ValueError(f"Zoe chat created forbidden notebook/monitor state: {forbidden}")
        verified = subprocess.run(
            [sys.executable, "-m", "zoe_autonomy.chat", "--state", str(state), "--command", f"verify {export_path}"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if verified.returncode or "Verified explicit export" not in verified.stdout:
            raise ValueError(f"Zoe chat export verification failed:\n{verified.stdout + verified.stderr}")
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_metacognition", "tests.test_chat", "-v"],
            cwd=checkout,
            env=environment,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        test_output = tests.stdout + tests.stderr
        if tests.returncode or "\nOK" not in test_output:
            raise ValueError(f"Zoe chat unit tests failed:\n{test_output[-8000:]}")
        test_count = re.search(r"Ran (\d+) tests", test_output)
        return {
            "verified": True,
            "commands": records,
            "command_count": len(records),
            "unit_tests": int(test_count.group(1)) if test_count else None,
            "external_metacognition_monitor": False,
            "automatic_conversation_notebook": False,
            "forbidden_files_absent": ["events.jsonl", "metacognition.json"],
            "explicit_export_verified": True,
            "pala_report_import_verified": True,
            "reflection_measured": True,
            "guard_external_actions": 0,
        }


def verify_pala(manifest):
    item = manifest["pala_recovery"]
    checkout = ROOT / "components" / item["directory"]
    cargo = shutil.which("cargo")
    if cargo is None:
        raise ValueError("PALA verification requires Cargo and a stable Rust toolchain")
    commands = [
        ("format", [cargo, "fmt", "--check"]),
        ("clippy", [cargo, "clippy", "--locked", "--all-targets", "--", "-D", "warnings"]),
        ("rust_tests", [cargo, "test", "--locked"]),
        ("release_build", [cargo, "build", "--release", "--locked"]),
        ("recovery_integration", [sys.executable, "tests/test_pala.py"]),
    ]
    records = []
    outputs = {}
    for name, command in commands:
        completed = subprocess.run(
            command, cwd=checkout, capture_output=True, text=True, timeout=300, check=False,
        )
        output = completed.stdout + completed.stderr
        outputs[name] = output
        if completed.returncode:
            raise ValueError(f"PALA {name} failed:\n{output[-8000:]}")
        records.append({"name": name, "argv": command, "returncode": completed.returncode})
    plain = re.sub(r"\x1b\[[0-9;]*m", "", outputs["recovery_integration"])
    integration = re.search(r"PASSED:\s+(\d+)", plain)
    skipped = re.search(r"SKIPPED:\s+(\d+)", plain)
    rust = re.search(r"test result: ok\.\s+(\d+) passed", outputs["rust_tests"])
    if integration is None or rust is None:
        raise ValueError("PALA test summaries could not be verified")
    target = Path(os.environ.get("CARGO_TARGET_DIR", checkout / "target")).expanduser()
    if not target.is_absolute():
        target = checkout / target
    binary = target.resolve() / "release" / ("pala.exe" if os.name == "nt" else "pala")
    environment = os.environ.copy()
    environment["ZOE_ROOT"] = str(ROOT)
    environment["PYTHONPATH"] = str(ROOT / "guiai-lab")
    version = subprocess.run([sys.executable, "-m", "guiai.gem.unified_cli", "pala", "--version"], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30, check=False)
    listed = subprocess.run([sys.executable, "-m", "guiai.gem.unified_cli", "pala", "--list"], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30, check=False)
    if version.returncode or listed.returncode or "jpeg" not in listed.stdout + listed.stderr:
        raise ValueError(f"PALA zoe-command verification failed:\n{version.stdout + version.stderr + listed.stdout + listed.stderr}")
    return {
        "verified": True,
        "source_revision": item["revision"],
        "checks": records,
        "rust_tests_passed": int(rust.group(1)),
        "integration_passed": int(integration.group(1)),
        "integration_skipped": int(skipped.group(1)) if skipped else 0,
        "integration_total": int(integration.group(1)) + (int(skipped.group(1)) if skipped else 0),
        "version": version.stdout.strip(),
        "launcher": "zoe pala",
        "launcher_verified": True,
        "signature_list_verified": True,
        "build_target": str(target.resolve()),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_bytes": binary.stat().st_size,
        "raw_devices_accessed": False,
        "test_inputs": "synthetic images and temporary filesystem fixtures only",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify all Zoe One GEM hosts from the unified checkout")
    parser.add_argument("--output", help="new JSON verification path")
    parser.add_argument("--image", help="verify the same RGB image through every host")
    parser.add_argument("--foci", type=int, default=4, help="attention selections per host, from 1 to 8")
    parser.add_argument("--reflect", action="store_true", help="verify measured self-reflection in every host")
    parser.add_argument("--pala", action="store_true", help="also build and verify PALA with its synthetic recovery suite")
    parser.add_argument("--chat", action="store_true", help="also verify Zoe's native no-monitor conversational interface")
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.foci <= 8:
        raise ValueError("foci must be from 1 to 8")
    image = Path(arguments.image).expanduser().resolve(strict=True) if arguments.image else None
    manifest = json.loads((ROOT / "one-system.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1 or manifest["system"] != "Zoe One":
        raise ValueError("unsupported Zoe One manifest")
    checked_revisions = {
        item["id"]: verify_import(item)
        for item in [manifest["canonical_engine"], manifest["research"], manifest["pala_recovery"], *manifest["hosts"]]
    }
    reports = {}
    with tempfile.TemporaryDirectory(prefix="zoe-one-") as directory:
        temporary = Path(directory)
        for host in [manifest["canonical_engine"], *manifest["hosts"]]:
            checkout = ROOT / "components" / host["directory"]
            cwd = checkout / host.get("cwd", ".")
            output = temporary / f"{host['id']}.json"
            environment = os.environ.copy()
            environment["ZOE_ROOT"] = str(ROOT)
            environment["ZOE_AUTONOMY_ROOT"] = str(ROOT / "components" / "Zoe-Autonomy")
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
    pala_report = verify_pala(manifest) if arguments.pala else None
    chat_report = verify_chat(manifest) if arguments.chat else None
    result = {
        "schema_version": 1,
        "system": "Zoe One",
        "contract": manifest["contract"],
        "verified": True,
        "single_checkout": True,
        "monorepo_revision": git("rev-parse", "HEAD"),
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
    if pala_report is not None:
        result["pala_recovery"] = pala_report
    if chat_report is not None:
        result["conversation"] = chat_report
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

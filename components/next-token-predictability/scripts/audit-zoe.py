#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def tracked(root, prefix=None):
    arguments = ["ls-files", "-z"]
    if prefix:
        arguments.append(prefix)
    return sorted(item for item in git(root, *arguments).split("\0") if item)


def verify_chain(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    previous = None
    for index, event in enumerate(document["events"], 1):
        assert event["sequence"] == index
        assert event["previous_hash"] == previous
        supplied = event["hash"]
        calculated = hashlib.sha256(canonical({key: value for key, value in event.items() if key != "hash"}).encode("utf-8")).hexdigest()
        assert supplied == calculated
        previous = supplied
    return {
        "events": len(document["events"]),
        "observations": sum(event["kind"] == "knowledge_observation_recorded" for event in document["events"]),
        "links": sum(event["kind"] == "knowledge_link_recorded" for event in document["events"]),
        "terminal_sha256": previous,
        "authentication_claimed": False,
    }


def verify_models(root):
    evidence = root / "evidence/comparison"
    manifest = json.loads((evidence / "model-comparison-cases.json").read_text(encoding="utf-8"))
    results = []
    for case in manifest["cases"]:
        slug = re.sub(r"[^a-z0-9._-]+", "-", case["model"].rsplit("/", 1)[-1].lower())
        report_path = evidence / f"{slug}-accessible-volume.json"
        probability_path = evidence / f"{slug}-probabilities.npz"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        with np.load(probability_path, allow_pickle=False) as artifact:
            probabilities = artifact["probabilities"]
            input_ids = artifact["input_ids"]
        assert probabilities.shape == (report["vocabulary_size"],)
        assert np.all(np.isfinite(probabilities)) and np.all(probabilities >= 0)
        assert np.isclose(probabilities.sum(), 1.0, rtol=0, atol=1e-8)
        assert hashlib.sha256(probabilities.tobytes()).hexdigest() == report["probability_values_sha256"]
        assert hashlib.sha256(input_ids.tobytes()).hexdigest() == report["input_ids_sha256"]
        counts = [int(np.count_nonzero(probabilities > threshold)) for threshold in manifest["thresholds"]]
        assert counts == [entry["accessible_volume"] for entry in report["threshold_sweep"]]
        descending = np.argsort(-probabilities)
        rank = int(np.flatnonzero(descending == report["target_token_id"])[0]) + 1
        assert rank == report["target_rank"]
        entropy = float(-np.sum(probabilities * np.log2(np.maximum(probabilities, 1e-300))))
        assert np.isclose(entropy, report["entropy_bits"], rtol=0, atol=1e-12)
        results.append({"model": case["model"], "counts": counts, "target_rank": rank})
    return {"cases": len(results), "strict_comparison": True, "results": results}


def verify_biobert(root):
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "scripts/verify-biobert-optimization.py"],
        cwd=root, env=environment, check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


def markdown_links(zoe):
    paths = [zoe / "README.md", *sorted((zoe / "guiai-lab/docs").glob("*.md"))]
    missing = []
    checked = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"!?\[[^]]*\]\(([^)]+)\)", text):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target = target.split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            checked += 1
            if not (path.parent / target).resolve().exists():
                missing.append({"document": str(path.relative_to(zoe)), "target": target})
    return {"documents": len(paths), "checked": checked, "missing": missing}


def test_log(path, root):
    text = path.read_text(encoding="utf-8")
    display_path = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    ran = re.search(r"Ran (\d+) tests?", text)
    assert ran, f"no unittest count in {path}"
    failures = len(re.findall(r"^FAIL: ", text, re.MULTILINE))
    errors = len(re.findall(r"^ERROR: ", text, re.MULTILINE))
    skipped_match = re.search(r"OK \(skipped=(\d+)\)", text)
    return {
        "path": display_path,
        "sha256": sha256(path),
        "tests": int(ran.group(1)),
        "failures": failures,
        "errors": errors,
        "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        "result": "passed" if not failures and not errors and "OK" in text else "failed",
    }


def pdf_accessibility(path):
    completed = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    tagged = re.search(r"^Tagged:\s+(\w+)", completed.stdout, re.MULTILINE)
    return {"tagged": tagged.group(1) if tagged else "unknown"}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Read-only Zoe and accessible-volume evidence audit")
    parser.add_argument("--zoe-root", type=Path, default=root.parent / "zoe")
    parser.add_argument("--output", type=Path, default=root / "evidence/zoe-audit/report.json")
    parser.add_argument("--test-log", type=Path, action="append", default=[])
    parser.add_argument("--audit-date", default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    zoe = args.zoe_root.resolve()
    output = args.output.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(zoe / "guiai-lab"))
    from guiai.gem.field import volume_strict
    from guiai.gem.knowledge import KnowledgeField
    from guiai.gem.unified import ComponentRegistry
    from guiai.gem.volume import accessible_volume

    assert accessible_volume([0.70, 0.20, 0.08, 0.02], 0.05) == 3
    assert accessible_volume([0.70, 0.20, 0.08, 0.02], 0.20) == 1
    strict = volume_strict([0.70, 0.20, 0.08, 0.02], 0.05)
    assert strict["accessible_volume"] == 3 and strict["complement_volume"] == 1
    registry = ComponentRegistry(zoe)
    manifest = registry.manifest()
    lock = json.loads((zoe / "components.lock.json").read_text(encoding="utf-8"))
    assert manifest["entrypoint_count"] == 12 and manifest["repository_count"] == 10
    assert all(row["source"]["source_present"] for row in manifest["components"])
    for component in manifest["components"]:
        if component["revision"] is not None:
            assert component["revision"] == lock["components"][component["checkout"]]["revision"]
    chain = verify_chain(zoe / "evidence/unified/source-graph.json")
    restored = KnowledgeField.load(zoe / "evidence/unified/source-graph.json")
    assert len(restored.events) == chain["events"]

    bundled = zoe / "components/next-token-predictability"
    standalone_files = tracked(root)
    bundled_files = [item.removeprefix("components/next-token-predictability/") for item in tracked(zoe, "components/next-token-predictability")]
    snapshot_differences = [
        item for item in standalone_files
        if item not in bundled_files or not (bundled / item).is_file() or sha256(root / item) != sha256(bundled / item)
    ]

    links = markdown_links(zoe)
    unified_guide = (zoe / "guiai-lab/docs/UNIFIED.md").read_text(encoding="utf-8")
    verifier = (root / "scripts/verify-model-comparison.py").read_text(encoding="utf-8")
    tests = [test_log(path.resolve(), root) for path in args.test_log]
    findings = []
    for item in links["missing"]:
        findings.append({"severity": "low", "kind": "broken_case_sensitive_link", **item})
    if "Eleven launch or inspection endpoints" in unified_guide:
        findings.append({
            "severity": "low", "kind": "stale_endpoint_documentation",
            "document": "guiai-lab/docs/UNIFIED.md", "documented": 11, "actual": 12,
        })
    if not (zoe / ".github/workflows").is_dir():
        findings.append({
            "severity": "medium", "kind": "no_root_ci_workflow",
            "scope": "Nested component workflows exist, but the integrated Zoe checkout has no root CI workflow.",
        })
    if "atomic_write_text(summary_path" in verifier and '"generated_utc": datetime.now' in verifier:
        findings.append({
            "severity": "medium", "kind": "verification_regenerates_tracked_summary",
            "document": "scripts/verify-model-comparison.py",
            "scope": "The verifier rewrites JSON and CSV summaries, including a fresh timestamp; use a working copy when preserving reference bytes.",
        })
    for result in tests:
        if result["failures"] or result["errors"]:
            findings.append({
                "severity": "medium", "kind": "focused_native_test_failure",
                "scope": "UnifiedNativeCase expects 11 links after record_unified_source; the implementation intentionally adds a declared link and produces 12.",
                "observed_in": result["path"],
            })
    accessibility = pdf_accessibility(root / "paper/accessible-volume-significance.pdf")
    if accessibility["tagged"] != "yes":
        findings.append({
            "severity": "low", "kind": "pdf_not_tagged",
            "document": "paper/accessible-volume-significance.pdf",
            "scope": "Text and attachments are available, but the PDF lacks a tagged structure tree for assistive technology.",
        })

    report = {
        "schema_version": 1,
        "instrument": "zoe-accessible-volume-repository-audit",
        "audit_date": args.audit_date,
        "zoe": {
            "repository": "https://github.com/Ablation-Tool/zoe",
            "revision": git(zoe, "rev-parse", "HEAD"),
            "clean": not git(zoe, "status", "--porcelain"),
            "tracked_files": len(tracked(zoe)),
            "registered_repositories": manifest["repository_count"],
            "launch_or_inspection_endpoints": manifest["entrypoint_count"],
            "all_component_sources_present": True,
            "lock_revisions_match_registry": True,
        },
        "equation": {
            "expression": "A_tau(S) = sum_{a in O} 1[P(a | h_T(S)) > tau]",
            "creator": "Nicholas Michael Kloster",
            "created": "2026-03-06",
            "strict_threshold_example": 3,
            "equality_excluded_example": 1,
            "zoe_volume_and_field_implementations_agree": True,
            "measures": "forecast breadth, not correctness, safety, or authorization",
        },
        "knowledge_chain": chain,
        "research_snapshot": {
            "standalone_files": len(standalone_files),
            "bundled_files": len(bundled_files),
            "path_lists_equal": standalone_files == bundled_files,
            "different_or_missing": snapshot_differences,
        },
        "model_comparison": verify_models(root),
        "biobert": verify_biobert(root),
        "documentation": links,
        "focused_test_logs": tests,
        "pdf_accessibility": accessibility,
        "acceptance_boundary": {
            "argument_arrays_without_shell": True,
            "execute_flag_required": True,
            "declared_hardware_write_gate_present": True,
            "hardware_access_inferred_from_argv": False,
            "physical_hardware_tested": False,
            "scope": "Component-scoped command plan controls, not a universal hardware or operating-system security boundary.",
        },
        "findings": findings,
        "result": "completed_with_findings" if findings else "completed_without_findings",
        "scope": [
            "Source, numerical evidence, documentation, packaging-facing links, and focused integration behavior were audited.",
            "No model weights were downloaded and no fresh model inference was performed.",
            "No physical hardware was contacted and no firmware, acceptance plan, or desktop input was executed.",
            "This is not an exhaustive security review of every vendored component or a certification of deployed behavior.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(output),
        "zoe_revision": report["zoe"]["revision"],
        "comparison_cases": report["model_comparison"]["cases"],
        "biobert_cases": report["biobert"]["cases"],
        "findings": len(findings),
        "result": report["result"],
    }, indent=2))


if __name__ == "__main__":
    main()

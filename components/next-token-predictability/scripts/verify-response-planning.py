#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import numpy as np

from ablation_gem_artifacts import atomic_write_text


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "evidence" / "response-planning"
THRESHOLDS = (0.02, 0.05, 0.10, 0.15, 0.30, 0.50)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def slugify(model):
    return re.sub(r"[^a-z0-9._-]+", "-", model.rsplit("/", 1)[-1].lower())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def independent_metrics(scores, labels):
    positives = [score for score, label in zip(scores, labels) if label]
    negatives = [score for score, label in zip(scores, labels) if not label]
    auroc = sum((positive > negative) + 0.5 * (positive == negative) for positive in positives for negative in negatives) / (len(positives) * len(negatives))
    auprc = 0.0
    previous_recall = 0.0
    for threshold in sorted(set(scores), reverse=True):
        predicted = [label for score, label in zip(scores, labels) if score >= threshold]
        true_positives = sum(predicted)
        recall = true_positives / len(positives)
        precision = true_positives / len(predicted)
        auprc += (recall - previous_recall) * precision
        previous_recall = recall
    return float(auroc), float(auprc)


def verify_comparison(measurements):
    comparison = measurements["comparison"]
    source = ROOT / "evidence" / "comparison"
    manifest_path = source / "model-comparison-cases.json"
    assert sha256_bytes(manifest_path.read_bytes()) == comparison["manifest_sha256"]
    cases = comparison["cases"]
    assert len(cases) == comparison["case_count"] == 16
    cells = 0
    for case in cases:
        slug = slugify(case["model"])
        assert slug == case["slug"]
        report = load_json(source / f"{slug}-accessible-volume.json")
        assert report["model"] == case["model"]
        assert report["model_revision"] == case["model_revision"]
        with np.load(source / f"{slug}-probabilities.npz", allow_pickle=False) as artifact:
            probabilities = artifact["probabilities"]
        assert sha256_bytes(probabilities.tobytes()) == case["probability_values_sha256"]
        assert len(probabilities) == case["vocabulary_size"]
        sweep = [int(np.count_nonzero(probabilities > threshold)) for threshold in THRESHOLDS]
        assert sweep == case["threshold_sweep"]
        assert all(later <= earlier for earlier, later in zip(sweep, sweep[1:]))
        order = np.argsort(-probabilities)
        for position, candidate in enumerate(case["top_candidates"]):
            assert candidate["token_id"] == int(order[position])
            assert candidate["probability"] == probabilities[candidate["token_id"]]
            assert candidate["token"] == report["top_tokens"][position]["token"]
        cells += len(sweep)
    assert cells == comparison["threshold_cell_count"] == 96
    return cells


def verify_biobert(measurements):
    source = ROOT / "evidence" / "biobert-optimization"
    summary_path = source / "baseline-summary.json"
    summary_bytes = summary_path.read_bytes()
    summary = json.loads(summary_bytes)
    optimization_path = source / "optimization.json"
    optimization = json.loads(optimization_path.read_bytes())
    biobert = measurements["biobert"]
    assert sha256_bytes(summary_bytes) == biobert["baseline_summary_sha256"]
    assert sha256_bytes(optimization_path.read_bytes()) == biobert["optimization_sha256"]
    assert optimization["baseline_summary_sha256"] == biobert["baseline_summary_sha256"]
    measured_records = {record["case_id"]: record for record in biobert["test"]["records"]}
    assert len(measured_records) == biobert["test"]["cases"] == 40
    verified_cases = 0
    for report in summary["results"]:
        with np.load(source / "raw" / f"{report['case_id']}.npz", allow_pickle=False) as artifact:
            probabilities = artifact["probabilities"]
        assert sha256_bytes(probabilities.tobytes()) == report["probability_values_sha256"]
        score = int(np.count_nonzero(probabilities > 0.05))
        assert score == report["threshold_sweep"][1]
        if report["split"] == "test":
            measured = measured_records[report["case_id"]]
            assert measured["source_document_id"] == report["source_document_id"]
            assert measured["error"] == report["error"]
            assert measured["accessible_volume_tau_0.05"] == score
        verified_cases += 1
    assert verified_cases == biobert["verified_case_count"] == 120
    records = list(measured_records.values())
    scores = [record["accessible_volume_tau_0.05"] for record in records]
    labels = [record["error"] for record in records]
    auroc, auprc = independent_metrics(scores, labels)
    assert np.isclose(auroc, biobert["test"]["auroc"], rtol=0, atol=1e-12)
    assert np.isclose(auprc, biobert["test"]["auprc"], rtol=0, atol=1e-12)
    expected = optimization["evaluation"]["original_tau_0.05"]["test"]
    assert np.isclose(auroc, expected["auroc"], rtol=0, atol=1e-12)
    assert np.isclose(auprc, expected["auprc"], rtol=0, atol=1e-12)
    assert sum(labels) == biobert["test"]["errors"] == 23
    assert len(labels) - sum(labels) == biobert["test"]["correct"] == 17
    error_scores = [score for score, label in zip(scores, labels) if label]
    correct_scores = [score for score, label in zip(scores, labels) if not label]
    assert np.isclose(np.mean(error_scores), biobert["test"]["mean_volume_errors"], rtol=0, atol=1e-12)
    assert np.isclose(np.mean(correct_scores), biobert["test"]["mean_volume_correct"], rtol=0, atol=1e-12)
    return auroc, auprc


def verify_triangulation(measurements, zoe_path, gem_path, workbench_path):
    triangulation = measurements["triangulation"]
    gpt2 = next(case for case in measurements["comparison"]["cases"] if case["slug"] == "gpt2")
    with np.load(ROOT / "evidence" / "comparison" / "gpt2-probabilities.npz", allow_pickle=False) as artifact:
        probabilities = artifact["probabilities"]
    numpy_count = int(np.count_nonzero(probabilities > 0.05))
    assert numpy_count == triangulation["numpy_accessible_volume"] == 3
    assert sha256_bytes(probabilities.tobytes()) == triangulation["probability_values_sha256"]
    zoe = load_json(zoe_path)
    assert zoe["source"]["probability_values_sha256"] == triangulation["probability_values_sha256"]
    zoe_sweep = [entry["accessible_volume"] for entry in zoe["threshold_sweep"]]
    assert zoe_sweep == gpt2["threshold_sweep"]
    assert zoe_sweep[1] == triangulation["zoe_accessible_volume"] == numpy_count
    gem = load_json(gem_path)
    assert gem["equation"] == "volume/strict@v1"
    assert gem["executed"] is False
    assert gem["belief_updated"] is False
    gem_probabilities = np.asarray(gem["inputs"]["probabilities"], dtype=np.float64)
    assert sha256_bytes(gem_probabilities.tobytes()) == triangulation["probability_values_sha256"]
    assert gem["inputs"]["tau"] == triangulation["tau"] == 0.05
    assert gem["result"]["accessible_volume"] == triangulation["gem_accessible_volume"] == numpy_count
    assert triangulation["agreement"] is True
    workbench = load_json(workbench_path)
    assert workbench["algorithm_count"] == workbench["passed"] == 17
    assert workbench["failed"] == triangulation["gem_workbench_algorithms_failed"] == 0
    assert triangulation["gem_workbench_algorithms_passed"] == 17


def verify_artifacts(output, measurements_path):
    manifest = load_json(output / "artifact-manifest.json")
    assert manifest["deterministic_outputs"] is True
    for name, entry in manifest["artifacts"].items():
        data = (output / name).read_bytes()
        assert sha256_bytes(data) == entry["sha256"]
        assert len(data) > 0
    assert sha256_bytes(measurements_path.read_bytes()) == manifest["artifacts"]["measurements.json"]["sha256"]
    png = (output / "response-planning-proof.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert width == manifest["artifacts"]["response-planning-proof.png"]["width"]
    assert height == manifest["artifacts"]["response-planning-proof.png"]["height"]
    assert width >= 1600 and height >= 1200
    svg_path = output / "response-planning-proof.svg"
    tree = ET.parse(svg_path)
    svg_text = " ".join(tree.getroot().itertext())
    for expected in ("AUROC 0.7737", "AUPRC 0.7978", "NumPy = Zoe = GEM", "96/96 threshold counts", "executed = false"):
        assert expected in svg_text, expected
    return {
        "png_dimensions": [width, height],
        "svg_semantic_labels_verified": True,
        "artifact_hashes_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Independently verify the accessible-volume visual proof and its source evidence")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--zoe-report", type=Path, default=DEFAULT_OUTPUT / "zoe-gpt2-volume.json")
    parser.add_argument("--gem-report", type=Path, default=DEFAULT_OUTPUT / "gem-gpt2-strict.json")
    parser.add_argument("--gem-workbench", type=Path, default=DEFAULT_OUTPUT / "gem-workbench-verification.json")
    args = parser.parse_args()
    measurements_path = args.output / "measurements.json"
    measurements = load_json(measurements_path)
    assert measurements["comparison_rule"] == "strict_probability_greater_than_threshold"
    assert measurements["thresholds"] == list(THRESHOLDS)
    cells = verify_comparison(measurements)
    auroc, auprc = verify_biobert(measurements)
    verify_triangulation(measurements, args.zoe_report, args.gem_report, args.gem_workbench)
    boundary = measurements["strict_boundary_check"]
    assert sum(value > boundary["tau"] for value in boundary["probabilities"]) == boundary["accessible_volume"] == 3
    assert boundary["token_exactly_at_tau_excluded"] is True
    visual = verify_artifacts(args.output, measurements_path)
    manifest = load_json(args.output / "artifact-manifest.json")
    verification = {
        "schema_version": 1,
        "verified": True,
        "comparison_cases": 16,
        "threshold_cells": cells,
        "biobert_cases": 120,
        "biobert_test_cases": 40,
        "biobert_test_auroc": auroc,
        "biobert_test_auprc": auprc,
        "numpy_zoe_gem_agreement": True,
        "gem_workbench_operations_passed": 17,
        "strict_threshold_boundary_passed": True,
        "visual": visual,
        "artifact_sha256": {name: entry["sha256"] for name, entry in manifest["artifacts"].items()},
        "scope": "Verified distribution measurements and visual integrity; not validation of response length, autonomy, or a universal policy.",
    }
    verification_path = args.output / "verification.json"
    atomic_write_text(verification_path, json.dumps(verification, indent=2) + "\n")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()

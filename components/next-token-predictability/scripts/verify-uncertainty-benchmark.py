#!/usr/bin/env python3
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE = Path("evidence/biobert-optimization")
ROOT = Path("evidence/uncertainty-benchmark")
STANDALONE = (
    "accessible_volume_tau_0.05",
    "entropy_bits",
    "one_minus_max_probability",
    "one_minus_top_10_mass",
)
FEATURE_SETS = (
    "distribution_only",
    "maximum_plus_accessible_volume",
    "distribution_plus_accessible_volume",
)


def independent_metrics(scores, labels):
    positives = [score for score, label in zip(scores, labels) if label]
    negatives = [score for score, label in zip(scores, labels) if not label]
    auroc = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives) / (len(positives) * len(negatives))
    previous_recall = 0.0
    auprc = 0.0
    for threshold in sorted(set(scores), reverse=True):
        predicted = [label for score, label in zip(scores, labels) if score >= threshold]
        true_positives = sum(predicted)
        recall = true_positives / len(positives)
        precision = true_positives / len(predicted)
        auprc += (recall - previous_recall) * precision
        previous_recall = recall
    return auroc, auprc


def expected_review(scores, labels, fraction):
    budget = len(labels) * fraction
    groups = {}
    for score, label in zip(scores, labels):
        groups.setdefault(score, []).append(label)
    reviewed = 0.0
    found = 0.0
    for score in sorted(groups, reverse=True):
        group = groups[score]
        selected = min(len(group), budget - reviewed)
        found += sum(group) * selected / len(group)
        reviewed += selected
        if reviewed == budget:
            break
    return found, found / reviewed, found / sum(labels)


def check_metrics(actual, scores, labels):
    auroc, auprc = independent_metrics(scores, labels)
    assert np.isclose(actual["auroc"], auroc, rtol=0, atol=1e-12)
    assert np.isclose(actual["auprc"], auprc, rtol=0, atol=1e-12)
    assert actual["cases"] == len(labels)
    assert actual["errors"] == sum(labels)
    for fraction in (0.10, 0.25, 0.50):
        found, precision, recall = expected_review(scores, labels, fraction)
        review = actual["review"][str(fraction)]
        assert np.isclose(review["expected_errors_found"], found, rtol=0, atol=1e-12)
        assert np.isclose(review["expected_precision"], precision, rtol=0, atol=1e-12)
        assert np.isclose(review["expected_recall"], recall, rtol=0, atol=1e-12)


def main():
    result_bytes = (ROOT / "biobert-results.json").read_bytes()
    result = json.loads(result_bytes)
    summary_bytes = (SOURCE / "baseline-summary.json").read_bytes()
    assert result["source"]["baseline_summary_sha256"] == hashlib.sha256(summary_bytes).hexdigest()
    with (ROOT / "biobert-scores.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 120
    for row in rows:
        with np.load(SOURCE / "raw" / f"{row['case_id']}.npz") as artifact:
            probabilities = artifact["probabilities"]
        expected = {
            "accessible_volume_tau_0.05": np.count_nonzero(probabilities > 0.05),
            "entropy_bits": -np.sum(probabilities * np.log2(np.maximum(probabilities, 1e-300))),
            "one_minus_max_probability": 1.0 - probabilities.max(),
            "one_minus_top_10_mass": 1.0 - np.sort(probabilities)[-10:].sum(),
        }
        for name, value in expected.items():
            assert np.isclose(float(row[name]), value, rtol=0, atol=1e-12)
    for split, key in (("development_validation", "development_validation"), ("test", "test")):
        subset = [row for row in rows if (row["split"] != "test" if split == "development_validation" else row["split"] == "test")]
        labels = [int(row["error"]) for row in subset]
        for name in STANDALONE:
            check_metrics(result["standalone"][name][key], [float(row[name]) for row in subset], labels)
        for name in FEATURE_SETS:
            score_key = "oof" if split == "development_validation" else "test"
            result_key = "development_validation_oof" if split == "development_validation" else "test"
            scores = [float(row[f"{name}_{score_key}"]) for row in subset]
            check_metrics(result["combined"][name][result_key], scores, labels)
    development = [row for row in rows if row["split"] != "test"]
    folds = {}
    for row in development:
        document = row["source_document_id"]
        fold = int(row["group_fold"])
        assert document not in folds or folds[document] == fold
        folds[document] = fold
    assert set(folds.values()) == set(range(5))
    for threshold, evaluation in result["accessible_volume_threshold_sweep"].items():
        for split, key in (("development_validation", "development_validation"), ("test", "test")):
            subset = [row for row in rows if (row["split"] != "test" if split == "development_validation" else row["split"] == "test")]
            labels = [int(row["error"]) for row in subset]
            scores = []
            for row in subset:
                with np.load(SOURCE / "raw" / f"{row['case_id']}.npz") as artifact:
                    scores.append(np.count_nonzero(artifact["probabilities"] > float(threshold)))
            check_metrics(evaluation[key], scores, labels)
    for name, comparisons in result["bootstrap"]["metric_intervals"].items():
        for metric, bounds in comparisons.items():
            assert bounds["samples"] > 0
            assert 0 <= bounds["lower_95"] <= bounds["upper_95"] <= 1
    print(json.dumps({
        "verified": True,
        "cases": len(rows),
        "grouped_validation_folds": 5,
        "source_documents": len({row["source_document_id"] for row in rows}),
        "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "checks": "Raw scores, standalone and combined metrics, threshold sweeps, review-budget calculations, fold grouping, and interval bounds passed",
    }, indent=2))


if __name__ == "__main__":
    main()

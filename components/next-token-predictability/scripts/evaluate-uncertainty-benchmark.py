#!/usr/bin/env python3
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ablation_gem_artifacts import atomic_write_bytes, atomic_write_text

SOURCE = Path("evidence/biobert-optimization")
OUTPUT = Path("evidence/uncertainty-benchmark")
SEED = 20261112
BOOTSTRAPS = 2000
REVIEW_FRACTIONS = (0.10, 0.25, 0.50)
THRESHOLDS = (0.02, 0.05, 0.10, 0.15, 0.30, 0.50)
STANDALONE = (
    "accessible_volume_tau_0.05",
    "entropy_bits",
    "one_minus_max_probability",
    "one_minus_top_10_mass",
)
FEATURE_SETS = {
    "distribution_only": (
        "entropy_bits",
        "one_minus_max_probability",
        "one_minus_top_10_mass",
    ),
    "maximum_plus_accessible_volume": (
        "one_minus_max_probability",
        "accessible_volume_tau_0.05",
    ),
    "distribution_plus_accessible_volume": (
        "entropy_bits",
        "one_minus_max_probability",
        "one_minus_top_10_mass",
        "accessible_volume_tau_0.05",
    ),
}


def metrics(scores, labels):
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        return {"auroc": None, "auprc": None, "cases": len(labels), "errors": positives}
    auroc = float(roc_auc_score(labels, scores))
    auprc = float(average_precision_score(labels, scores))
    result = {
        "auroc": auroc,
        "auprc": auprc,
        "cases": len(labels),
        "errors": positives,
        "correct": negatives,
    }
    result["review"] = {
        str(fraction): review_metrics(scores, labels, fraction)
        for fraction in REVIEW_FRACTIONS
    }
    return result


def review_metrics(scores, labels, fraction):
    budget = len(labels) * fraction
    order = np.argsort(-np.asarray(scores, dtype=np.float64), kind="stable")
    reviewed = 0.0
    expected_errors = 0.0
    index = 0
    while index < len(order) and reviewed < budget:
        end = index + 1
        while end < len(order) and scores[order[end]] == scores[order[index]]:
            end += 1
        group_size = end - index
        selected = min(group_size, budget - reviewed)
        group_errors = sum(int(labels[order[position]]) for position in range(index, end))
        expected_errors += group_errors * selected / group_size
        reviewed += selected
        index = end
    return {
        "review_fraction": fraction,
        "expected_reviewed_cases": reviewed,
        "expected_errors_found": expected_errors,
        "expected_precision": expected_errors / reviewed,
        "expected_recall": expected_errors / int(np.sum(labels)),
        "tie_handling": "Fractional equal-probability selection within boundary ties",
    }


def load_records():
    summary_bytes = (SOURCE / "baseline-summary.json").read_bytes()
    summary = json.loads(summary_bytes)
    assert summary["verified_case_count"] == 120
    records = []
    for report in summary["results"]:
        with np.load(SOURCE / "raw" / f"{report['case_id']}.npz") as artifact:
            probabilities = artifact["probabilities"]
        assert hashlib.sha256(probabilities.tobytes()).hexdigest() == report["probability_values_sha256"]
        assert np.all(np.isfinite(probabilities))
        assert np.all(probabilities >= 0)
        assert np.isclose(probabilities.sum(), 1.0, rtol=0, atol=1e-8)
        assert np.isclose(-np.sum(probabilities * np.log2(np.maximum(probabilities, 1e-300))), report["entropy_bits"])
        assert np.isclose(probabilities.max(), report["maximum_probability"])
        assert np.isclose(np.sort(probabilities)[-10:].sum(), report["top_10_probability_mass"])
        record = {
            "case_id": report["case_id"],
            "source_document_id": report["source_document_id"],
            "split": report["split"],
            "error": int(report["error"]),
            "entropy_bits": float(report["entropy_bits"]),
            "one_minus_max_probability": 1.0 - float(report["maximum_probability"]),
            "one_minus_top_10_mass": 1.0 - float(report["top_10_probability_mass"]),
        }
        for threshold in THRESHOLDS:
            record[f"accessible_volume_tau_{threshold:.2f}"] = int(np.count_nonzero(probabilities > threshold))
        assert record["accessible_volume_tau_0.05"] == report["threshold_sweep"][1]
        records.append(record)
    return summary, summary_bytes, records


def new_model():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=10000, random_state=SEED),
    )


def combined_scores(records):
    development = [record for record in records if record["split"] != "test"]
    test = [record for record in records if record["split"] == "test"]
    labels = np.array([record["error"] for record in development])
    groups = np.array([record["source_document_id"] for record in development])
    splitter = GroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    results = {}
    for name, features in FEATURE_SETS.items():
        matrix = np.array([[record[feature] for feature in features] for record in development])
        test_matrix = np.array([[record[feature] for feature in features] for record in test])
        oof = np.empty(len(development), dtype=np.float64)
        fold_ids = np.empty(len(development), dtype=np.int64)
        for fold, (train_indices, held_out_indices) in enumerate(splitter.split(matrix, labels, groups)):
            model = new_model()
            model.fit(matrix[train_indices], labels[train_indices])
            oof[held_out_indices] = model.predict_proba(matrix[held_out_indices])[:, 1]
            fold_ids[held_out_indices] = fold
        model = new_model()
        model.fit(matrix, labels)
        test_scores = model.predict_proba(test_matrix)[:, 1]
        results[name] = {
            "features": list(features),
            "oof_scores": oof,
            "test_scores": test_scores,
            "fold_ids": fold_ids,
            "coefficients": dict(zip(features, model[-1].coef_[0].tolist())),
            "intercept": float(model[-1].intercept_[0]),
        }
    return development, test, results


def interval(values):
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if not len(values):
        return {"samples": 0, "lower_95": None, "upper_95": None}
    return {
        "samples": len(values),
        "lower_95": float(np.quantile(values, 0.025)),
        "upper_95": float(np.quantile(values, 0.975)),
    }


def bootstrap(test, standalone_scores, model_scores):
    rng = np.random.default_rng(SEED)
    documents = sorted({record["source_document_id"] for record in test})
    indices_by_document = {
        document: np.array([index for index, record in enumerate(test) if record["source_document_id"] == document])
        for document in documents
    }
    labels = np.array([record["error"] for record in test])
    names = list(STANDALONE) + list(FEATURE_SETS)
    samples = {name: {"auroc": [], "auprc": []} for name in names}
    deltas = {
        "accessible_volume_minus_entropy": [],
        "accessible_volume_minus_one_minus_max": [],
        "accessible_volume_minus_one_minus_top_10_mass": [],
        "distribution_plus_volume_minus_distribution_only": [],
        "maximum_plus_volume_minus_one_minus_max": [],
    }
    for _ in range(BOOTSTRAPS):
        chosen = rng.choice(documents, size=len(documents), replace=True)
        indices = np.concatenate([indices_by_document[document] for document in chosen])
        if len(np.unique(labels[indices])) < 2:
            continue
        values = {}
        for name in names:
            scores = standalone_scores[name] if name in STANDALONE else model_scores[name]["test_scores"]
            values[name] = metrics(scores[indices], labels[indices])
            for metric in ("auroc", "auprc"):
                samples[name][metric].append(values[name][metric])
        deltas["accessible_volume_minus_entropy"].append(values["accessible_volume_tau_0.05"]["auroc"] - values["entropy_bits"]["auroc"])
        deltas["accessible_volume_minus_one_minus_max"].append(values["accessible_volume_tau_0.05"]["auroc"] - values["one_minus_max_probability"]["auroc"])
        deltas["accessible_volume_minus_one_minus_top_10_mass"].append(values["accessible_volume_tau_0.05"]["auroc"] - values["one_minus_top_10_mass"]["auroc"])
        deltas["distribution_plus_volume_minus_distribution_only"].append(values["distribution_plus_accessible_volume"]["auroc"] - values["distribution_only"]["auroc"])
        deltas["maximum_plus_volume_minus_one_minus_max"].append(values["maximum_plus_accessible_volume"]["auroc"] - values["one_minus_max_probability"]["auroc"])
    return {
        "method": "Paired percentile bootstrap over source documents with replacement",
        "seed": SEED,
        "requested_resamples": BOOTSTRAPS,
        "test_documents": len(documents),
        "metric_intervals": {
            name: {metric: interval(values) for metric, values in metric_values.items()}
            for name, metric_values in samples.items()
        },
        "auroc_difference_intervals": {name: interval(values) for name, values in deltas.items()},
    }


def main():
    summary, summary_bytes, records = load_records()
    development, test, combined = combined_scores(records)
    standalone_scores = {
        name: np.array([record[name] for record in records], dtype=np.float64)
        for name in STANDALONE
    }
    development_indices = np.array([index for index, record in enumerate(records) if record["split"] != "test"])
    test_indices = np.array([index for index, record in enumerate(records) if record["split"] == "test"])
    standalone_development = {name: values[development_indices] for name, values in standalone_scores.items()}
    standalone_test = {name: values[test_indices] for name, values in standalone_scores.items()}
    development_labels = np.array([record["error"] for record in development])
    test_labels = np.array([record["error"] for record in test])

    standalone_results = {
        name: {
            "development_validation": metrics(standalone_development[name], development_labels),
            "test": metrics(standalone_test[name], test_labels),
        }
        for name in STANDALONE
    }
    threshold_sweep = {
        f"{threshold:.2f}": {
            split: metrics(
                [record[f"accessible_volume_tau_{threshold:.2f}"] for record in records if record["split"] == split or split == "development_validation" and record["split"] != "test"],
                [record["error"] for record in records if record["split"] == split or split == "development_validation" and record["split"] != "test"],
            )
            for split in ("development_validation", "test")
        }
        for threshold in THRESHOLDS
    }
    combined_results = {}
    for name, result in combined.items():
        combined_results[name] = {
            "features": result["features"],
            "development_validation_oof": metrics(result["oof_scores"], development_labels),
            "test": metrics(result["test_scores"], test_labels),
            "fitted_coefficients": result["coefficients"],
            "fitted_intercept": result["intercept"],
        }
    incremental = {
        "maximum_plus_volume_minus_maximum": {
            "development_validation_oof_auroc": combined_results["maximum_plus_accessible_volume"]["development_validation_oof"]["auroc"] - standalone_results["one_minus_max_probability"]["development_validation"]["auroc"],
            "test_auroc": combined_results["maximum_plus_accessible_volume"]["test"]["auroc"] - standalone_results["one_minus_max_probability"]["test"]["auroc"],
            "test_auprc": combined_results["maximum_plus_accessible_volume"]["test"]["auprc"] - standalone_results["one_minus_max_probability"]["test"]["auprc"],
        },
        "distribution_plus_volume_minus_distribution": {
            "development_validation_oof_auroc": combined_results["distribution_plus_accessible_volume"]["development_validation_oof"]["auroc"] - combined_results["distribution_only"]["development_validation_oof"]["auroc"],
            "test_auroc": combined_results["distribution_plus_accessible_volume"]["test"]["auroc"] - combined_results["distribution_only"]["test"]["auroc"],
            "test_auprc": combined_results["distribution_plus_accessible_volume"]["test"]["auprc"] - combined_results["distribution_only"]["test"]["auprc"],
        },
    }
    intervals = bootstrap(test, standalone_test, combined)
    output = {
        "schema_version": 1,
        "generated_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "objective": "Determine whether accessible volume adds top-1 error-detection information beyond distribution baselines and improves expected error discovery under fixed review budgets",
        "source": {
            "model": summary["model"],
            "model_revision": summary["model_revision"],
            "baseline_summary_sha256": hashlib.sha256(summary_bytes).hexdigest(),
            "cases": len(records),
            "development_validation_cases": len(development),
            "test_cases": len(test),
        },
        "protocol": {
            "higher_scores_mean_more_likely_error": True,
            "primary_accessible_volume": "Strict count p > 0.05",
            "validation": "Five shuffled GroupKFold splits over source documents; no document crosses folds",
            "validation_seed": SEED,
            "combinations": "StandardScaler plus LogisticRegression(C=1), with no hyperparameter search",
            "selection_data": "Development and validation cases only",
            "final_evaluation": "Frozen test cases",
            "multiple_testing": "No significance claim; effect estimates and paired document-bootstrap intervals are reported",
            "test_history": "The test split was used in the original study, so this is a secondary analysis rather than a new independent replication",
        },
        "standalone": standalone_results,
        "accessible_volume_threshold_sweep": threshold_sweep,
        "combined": combined_results,
        "incremental_value": incremental,
        "bootstrap": intervals,
        "limitations": [
            "Only BioBERT and 120 masked-token cases from 30 biomedical documents are included",
            "The frozen test split contains only 40 cases from 10 documents, so intervals are wide",
            "Top-1 masked-token error detection is not answer-level correctness or real-world clinical risk",
            "Logistic combinations and review-budget results require external replication before operational use",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUTPUT / "biobert-results.json", json.dumps(output, indent=2) + "\n")

    stream = io.StringIO()
    fields = ["case_id", "source_document_id", "split", "error", "group_fold"] + list(STANDALONE)
    for name in FEATURE_SETS:
        fields.extend([f"{name}_oof", f"{name}_test"])
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    development_positions = {id(record): index for index, record in enumerate(development)}
    test_positions = {id(record): index for index, record in enumerate(test)}
    for index, record in enumerate(records):
        row = {key: record[key] for key in fields[:4]}
        row.update({name: standalone_scores[name][index] for name in STANDALONE})
        if record["split"] == "test":
            row["group_fold"] = ""
        else:
            row["group_fold"] = int(combined["distribution_only"]["fold_ids"][development_positions[id(record)]])
        for name, result in combined.items():
            if record["split"] == "test":
                row[f"{name}_oof"] = ""
                row[f"{name}_test"] = result["test_scores"][test_positions[id(record)]]
            else:
                row[f"{name}_oof"] = result["oof_scores"][development_positions[id(record)]]
                row[f"{name}_test"] = ""
        writer.writerow(row)
    atomic_write_bytes(OUTPUT / "biobert-scores.csv", stream.getvalue().encode("utf-8"))
    print(json.dumps({
        "standalone_test": {name: result["test"] for name, result in standalone_results.items()},
        "combined_oof": {name: result["development_validation_oof"] for name, result in combined_results.items()},
        "combined_test": {name: result["test"] for name, result in combined_results.items()},
        "incremental_value": incremental,
    }, indent=2))


if __name__ == "__main__":
    main()

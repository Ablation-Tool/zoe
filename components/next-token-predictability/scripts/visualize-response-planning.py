#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "accessible-volume-response-planning"
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpecFromSubplotSpec
import numpy as np

from ablation_gem_artifacts import atomic_write_bytes, atomic_write_text


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "evidence" / "response-planning"
THRESHOLDS = (0.02, 0.05, 0.10, 0.15, 0.30, 0.50)
BACKGROUND = "#0b1020"
PANEL = "#121b2e"
TEXT = "#e5edf8"
MUTED = "#9aabc3"
CYAN = "#67e8f9"
ORANGE = "#fb923c"
DIM = "#475569"
MODEL_NAMES = {
    "bert-base-cased": "BERT-Base",
    "roberta-base": "RoBERTa-Base",
    "albert-base-v2": "ALBERT-Base",
    "gpt2": "GPT-2 · causal",
    "securebert": "SecureBERT",
    "cysecbert": "CySecBERT",
    "biobert-base-cased-v1.2": "BioBERT",
    "bio_clinicalbert": "Bio_ClinicalBERT",
    "scibert_scivocab_cased": "SciBERT",
    "legal-bert-base-uncased": "Legal-BERT",
    "finbert-pretrain": "FinBERT",
    "codebert-base": "CodeBERT",
    "xlm-roberta-base": "XLM-RoBERTa",
    "chemberta-zinc-base-v1": "ChemBERTa",
    "prot_bert": "ProtBERT",
    "qwen2.5-math-1.5b": "Qwen2.5-Math · causal",
}


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
    previous_recall = 0.0
    auprc = 0.0
    for threshold in sorted(set(scores), reverse=True):
        predicted = [label for score, label in zip(scores, labels) if score >= threshold]
        true_positives = sum(predicted)
        recall = true_positives / len(positives)
        precision = true_positives / len(predicted)
        auprc += (recall - previous_recall) * precision
        previous_recall = recall
    return float(auroc), float(auprc)


def load_comparison():
    comparison = ROOT / "evidence" / "comparison"
    manifest_path = comparison / "model-comparison-cases.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest["thresholds"] == list(THRESHOLDS)
    cases = []
    for case in manifest["cases"]:
        slug = slugify(case["model"])
        report = load_json(comparison / f"{slug}-accessible-volume.json")
        probability_path = comparison / f"{slug}-probabilities.npz"
        with np.load(probability_path, allow_pickle=False) as artifact:
            probabilities = artifact["probabilities"]
        probability_hash = sha256_bytes(probabilities.tobytes())
        assert probability_hash == report["probability_values_sha256"]
        assert probabilities.shape == (report["vocabulary_size"],)
        assert np.all(np.isfinite(probabilities))
        assert np.all(probabilities >= 0)
        assert np.isclose(probabilities.sum(), 1.0, rtol=0, atol=1e-8)
        sweep = [int(np.count_nonzero(probabilities > threshold)) for threshold in THRESHOLDS]
        assert sweep == [entry["accessible_volume"] for entry in report["threshold_sweep"]]
        order = np.argsort(-probabilities)
        assert [int(index) for index in order[:10]] == [entry["token_id"] for entry in report["top_tokens"]]
        for entry in report["top_tokens"]:
            assert probabilities[entry["token_id"]] == entry["probability"]
        cases.append({
            "slug": slug,
            "category": case["category"],
            "model": case["model"],
            "model_revision": case["revision"],
            "prediction_style": case["style"],
            "vocabulary_size": int(report["vocabulary_size"]),
            "probability_values_sha256": probability_hash,
            "threshold_sweep": sweep,
            "top_candidates": report["top_tokens"][:5],
        })
    assert len(cases) == 16
    assert all(
        later <= earlier
        for case in cases
        for earlier, later in zip(case["threshold_sweep"], case["threshold_sweep"][1:])
    )
    return {
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "case_count": len(cases),
        "threshold_cell_count": len(cases) * len(THRESHOLDS),
        "cases": cases,
    }


def load_biobert():
    source = ROOT / "evidence" / "biobert-optimization"
    summary_path = source / "baseline-summary.json"
    summary_bytes = summary_path.read_bytes()
    summary = json.loads(summary_bytes)
    optimization_path = source / "optimization.json"
    optimization_bytes = optimization_path.read_bytes()
    optimization = json.loads(optimization_bytes)
    assert optimization["baseline_summary_sha256"] == sha256_bytes(summary_bytes)
    test_cases = []
    verified_cases = 0
    for report in summary["results"]:
        with np.load(source / "raw" / f"{report['case_id']}.npz", allow_pickle=False) as artifact:
            probabilities = artifact["probabilities"]
        assert sha256_bytes(probabilities.tobytes()) == report["probability_values_sha256"]
        score = int(np.count_nonzero(probabilities > 0.05))
        assert score == report["threshold_sweep"][1]
        verified_cases += 1
        if report["split"] == "test":
            test_cases.append({
                "case_id": report["case_id"],
                "source_document_id": report["source_document_id"],
                "error": int(report["error"]),
                "accessible_volume_tau_0.05": score,
            })
    assert verified_cases == 120
    assert len(test_cases) == 40
    scores = [case["accessible_volume_tau_0.05"] for case in test_cases]
    labels = [case["error"] for case in test_cases]
    auroc, auprc = independent_metrics(scores, labels)
    expected = optimization["evaluation"]["original_tau_0.05"]["test"]
    assert np.isclose(auroc, expected["auroc"], rtol=0, atol=1e-12)
    assert np.isclose(auprc, expected["auprc"], rtol=0, atol=1e-12)
    error_scores = [score for score, label in zip(scores, labels) if label]
    correct_scores = [score for score, label in zip(scores, labels) if not label]
    return {
        "baseline_summary_sha256": sha256_bytes(summary_bytes),
        "optimization_sha256": sha256_bytes(optimization_bytes),
        "verified_case_count": verified_cases,
        "test": {
            "cases": len(test_cases),
            "errors": len(error_scores),
            "correct": len(correct_scores),
            "auroc": auroc,
            "auprc": auprc,
            "mean_volume_errors": float(np.mean(error_scores)),
            "mean_volume_correct": float(np.mean(correct_scores)),
            "records": test_cases,
        },
    }


def load_triangulation(comparison, zoe_path, gem_path, workbench_path):
    gpt2 = next(case for case in comparison["cases"] if case["slug"] == "gpt2")
    zoe = load_json(zoe_path)
    assert zoe["source"]["probability_values_sha256"] == gpt2["probability_values_sha256"]
    zoe_sweep = [entry["accessible_volume"] for entry in zoe["threshold_sweep"]]
    assert [entry["tau"] for entry in zoe["threshold_sweep"]] == list(THRESHOLDS)
    assert zoe_sweep == gpt2["threshold_sweep"]
    gem = load_json(gem_path)
    assert gem["equation"] == "volume/strict@v1"
    assert gem["inputs"]["tau"] == 0.05
    gem_probabilities = np.asarray(gem["inputs"]["probabilities"], dtype=np.float64)
    assert sha256_bytes(gem_probabilities.tobytes()) == gpt2["probability_values_sha256"]
    gem_count = int(gem["result"]["accessible_volume"])
    numpy_count = gpt2["threshold_sweep"][1]
    assert gem_count == numpy_count == 3
    workbench = load_json(workbench_path)
    assert workbench["algorithm_count"] == 17
    assert workbench["passed"] == 17
    assert workbench["failed"] == 0
    return {
        "model": gpt2["model"],
        "probability_values_sha256": gpt2["probability_values_sha256"],
        "tau": 0.05,
        "numpy_accessible_volume": numpy_count,
        "zoe_accessible_volume": zoe_sweep[1],
        "gem_accessible_volume": gem_count,
        "agreement": True,
        "gem_workbench_algorithms_passed": workbench["passed"],
        "gem_workbench_algorithms_failed": workbench["failed"],
    }


def style_axes(axes):
    for ax in axes:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=MUTED, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#2b3a52")
        ax.title.set_color(TEXT)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        ax.grid(color="#2b3a52", alpha=0.45, linewidth=0.6)
        ax.set_axisbelow(True)


def candidate_panel(ax, case):
    candidates = case["top_candidates"]
    labels = [entry["token"].strip() or repr(entry["token"]) for entry in candidates]
    probabilities = [entry["probability"] for entry in candidates]
    colors = [CYAN if probability > 0.05 else DIM for probability in probabilities]
    positions = np.arange(len(candidates))
    ax.barh(positions, probabilities, color=colors, height=0.64)
    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.05, 0.25, 0.50, 0.75, 1.0], ["0", "τ", ".25", ".50", ".75", "1"])
    ax.axvline(0.05, color=ORANGE, linewidth=1.4, linestyle="--")
    for position, probability in zip(positions, probabilities):
        label = f"{probability:.3f}" if probability >= 0.001 else "<.001"
        ax.text(min(probability + 0.015, 0.94), position, label, va="center", color=TEXT, fontsize=8)
    volume = case["threshold_sweep"][1]
    ax.set_title(f"{MODEL_NAMES[case['slug']]}  ·  A(0.05) = {volume}", loc="left", fontsize=11, fontweight="bold", pad=10)
    ax.grid(axis="y", visible=False)


def render(measurements, output):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "text.color": TEXT,
        "axes.facecolor": PANEL,
        "figure.facecolor": BACKGROUND,
        "savefig.facecolor": BACKGROUND,
        "svg.fonttype": "none",
        "svg.id": "accessible-volume-response-planning",
    })
    fig = plt.figure(figsize=(16, 12), dpi=125, facecolor=BACKGROUND)
    grid = fig.add_gridspec(2, 2, left=0.07, right=0.96, top=0.80, bottom=0.13, wspace=0.25, hspace=0.42, width_ratios=[1.35, 1])
    fig.text(0.07, 0.945, "SEE THE DECISION BEFORE THE TOKEN", color=CYAN, fontsize=12, fontweight="bold")
    fig.text(0.07, 0.905, "Operational Metacognition, made visible", color=TEXT, fontsize=28, fontweight="bold")
    fig.text(0.07, 0.866, "A(τ) counts real next-token alternatives with probability strictly above τ", color=MUTED, fontsize=12)
    fig.text(0.96, 0.935, "16 MODELS  /  96 CELLS  /  120 BIOBERT CASES", color=TEXT, fontsize=11, ha="right", fontweight="bold")
    fig.text(0.96, 0.900, "NumPy = Zoe = GEM  ·  GPT-2 A(0.05) = 3", color=CYAN, fontsize=11, ha="right")
    fig.text(0.96, 0.870, "96/96 threshold counts independently recomputed", color=MUTED, fontsize=10, ha="right")

    cases = measurements["comparison"]["cases"]
    gpt2 = next(case for case in cases if case["slug"] == "gpt2")
    bert = next(case for case in cases if case["slug"] == "bert-base-cased")
    candidate_grid = GridSpecFromSubplotSpec(1, 2, subplot_spec=grid[0, 0], wspace=0.35)
    candidate_axes = [fig.add_subplot(candidate_grid[0, index]) for index in range(2)]
    style_axes(candidate_axes)
    candidate_panel(candidate_axes[0], bert)
    candidate_panel(candidate_axes[1], gpt2)
    candidate_axes[0].set_xlabel("Same text and target · different prediction mechanisms and vocabularies", fontsize=8)

    bio_ax = fig.add_subplot(grid[0, 1])
    style_axes([bio_ax])
    test = measurements["biobert"]["test"]
    correct = [record["accessible_volume_tau_0.05"] for record in test["records"] if not record["error"]]
    errors = [record["accessible_volume_tau_0.05"] for record in test["records"] if record["error"]]
    rng = np.random.default_rng(20261114)
    for x, values, color, label in ((0, correct, CYAN, "correct top-1"), (1, errors, ORANGE, "incorrect top-1")):
        jitter = rng.uniform(-0.17, 0.17, len(values))
        bio_ax.scatter(np.full(len(values), x) + jitter, values, s=48, color=color, alpha=0.78, edgecolors=BACKGROUND, linewidths=0.5, label=label)
        mean = float(np.mean(values))
        bio_ax.plot([x - 0.25, x + 0.25], [mean, mean], color=TEXT, linewidth=2.2)
        bio_ax.text(x, max(values) + 0.35, f"mean {mean:.2f}", color=TEXT, fontsize=9, ha="center")
    bio_ax.set_xlim(-0.55, 1.55)
    maximum = max(correct + errors)
    bio_ax.set_ylim(-0.6, maximum + 1.2)
    bio_ax.set_yticks(range(maximum + 1))
    bio_ax.set_xticks([0, 1], ["Correct · n=17", "Error · n=23"])
    bio_ax.set_ylabel("Operational Metacognition at τ = 0.05")
    bio_ax.set_title("Held-out BioBERT: breadth carries an error signal", loc="left", fontsize=12, fontweight="bold", pad=12)
    bio_ax.text(0.02, 0.97, f"AUROC {test['auroc']:.4f}   ·   AUPRC {test['auprc']:.4f}", transform=bio_ax.transAxes, va="top", color=TEXT, fontsize=12, fontweight="bold")
    bio_ax.text(0.02, 0.89, "40 frozen test cases · points jittered only for visibility", transform=bio_ax.transAxes, va="top", color=MUTED, fontsize=8)
    bio_ax.grid(axis="x", visible=False)

    heat_ax = fig.add_subplot(grid[1, :])
    matrix = np.asarray([case["threshold_sweep"] for case in cases])
    image = heat_ax.imshow(matrix, aspect="auto", cmap="viridis", vmin=0, vmax=int(matrix.max()))
    heat_ax.set_facecolor(PANEL)
    heat_ax.set_xticks(np.arange(len(THRESHOLDS)), [f"τ = {threshold:.2f}" for threshold in THRESHOLDS])
    heat_ax.set_yticks(np.arange(len(cases)), [f"{MODEL_NAMES[case['slug']]}  ·  {case['category']}" for case in cases])
    heat_ax.tick_params(colors=MUTED, labelsize=8)
    for label_index, slug in enumerate(("bert-base-cased", "gpt2")):
        index = next(position for position, case in enumerate(cases) if case["slug"] == slug)
        heat_ax.get_yticklabels()[index].set_color(CYAN)
        heat_ax.get_yticklabels()[index].set_fontweight("bold")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = int(matrix[row, column])
            heat_ax.text(column, row, str(value), ha="center", va="center", fontsize=9, color="white" if value < matrix.max() * 0.58 else BACKGROUND, fontweight="bold")
    heat_ax.set_title("The full threshold sweep · accessible alternatives disappear as τ rises", loc="left", color=TEXT, fontsize=13, fontweight="bold", pad=13)
    heat_ax.set_xlabel("Individual model–context pairs, not a model-quality leaderboard  ·  every count comes from the complete saved vocabulary", color=MUTED, fontsize=9, labelpad=12)
    for spine in heat_ax.spines.values():
        spine.set_color("#2b3a52")
    colorbar = fig.colorbar(image, ax=heat_ax, fraction=0.025, pad=0.02)
    colorbar.set_label("Alternatives above τ", color=MUTED, fontsize=9)
    colorbar.ax.tick_params(colors=MUTED, labelsize=8)
    colorbar.outline.set_edgecolor("#2b3a52")

    fig.text(0.07, 0.075, "RESPONSE POLICY  ·  measure → inspect alternatives → decode → respond", color=TEXT, fontsize=11, fontweight="bold")
    fig.text(0.07, 0.047, "Operational Metacognition informs review; it does not choose a token, set response length, establish correctness, or authorize autonomy.", color=MUTED, fontsize=10)
    fig.text(0.96, 0.047, "Strict p > τ  ·  executed = false", color=CYAN, fontsize=10, ha="right")

    png_path = output / "response-planning-proof.png"
    svg_path = output / "response-planning-proof.svg"
    fig.savefig(png_path, dpi=125, facecolor=BACKGROUND, metadata={"Software": "Operational Metacognition response-planning proof"})
    fig.savefig(svg_path, facecolor=BACKGROUND, metadata={
        "Date": None,
        "Title": "Operational Metacognition response-planning proof",
        "Description": "Real next-token distributions, 96 recomputed threshold counts, held-out BioBERT error separation, and NumPy/Zoe/GEM agreement.",
    })
    plt.close(fig)
    return png_path, svg_path


def main():
    parser = argparse.ArgumentParser(description="Verify saved evidence and render a deterministic accessible-volume response-planning proof")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--zoe-report", type=Path, default=DEFAULT_OUTPUT / "zoe-gpt2-volume.json")
    parser.add_argument("--gem-report", type=Path, default=DEFAULT_OUTPUT / "gem-gpt2-strict.json")
    parser.add_argument("--gem-workbench", type=Path, default=DEFAULT_OUTPUT / "gem-workbench-verification.json")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    comparison = load_comparison()
    biobert = load_biobert()
    triangulation = load_triangulation(comparison, args.zoe_report, args.gem_report, args.gem_workbench)
    boundary = [0.70, 0.20, 0.08, 0.05]
    boundary_count = sum(probability > 0.05 for probability in boundary)
    assert boundary_count == 3
    measurements = {
        "schema_version": 1,
        "instrument": "Accessible-volume response-planning visual proof",
        "comparison_rule": "strict_probability_greater_than_threshold",
        "thresholds": list(THRESHOLDS),
        "comparison": comparison,
        "biobert": biobert,
        "triangulation": triangulation,
        "strict_boundary_check": {
            "probabilities": boundary,
            "tau": 0.05,
            "accessible_volume": boundary_count,
            "token_exactly_at_tau_excluded": True,
        },
        "scope": [
            "Real saved model-context pairs, not a model-quality leaderboard or a Claude/Kimi benchmark.",
            "Operational Metacognition measures next-token forecast breadth, not response length, correctness, safety, or autonomy.",
            "The BioBERT panel reproduces the original fixed-threshold held-out test result; it does not validate a response policy.",
            "No wall-clock value enters the measurements, figures, or artifact manifest.",
        ],
    }
    measurements_path = args.output / "measurements.json"
    atomic_write_text(measurements_path, json.dumps(measurements, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    png_path, svg_path = render(measurements, args.output)
    png_bytes = png_path.read_bytes()
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png_bytes[16:24])
    manifest = {
        "schema_version": 1,
        "deterministic_outputs": True,
        "artifacts": {
            "measurements.json": {"sha256": sha256_bytes(measurements_path.read_bytes())},
            "response-planning-proof.png": {"sha256": sha256_bytes(png_bytes), "width": width, "height": height},
            "response-planning-proof.svg": {"sha256": sha256_bytes(svg_path.read_bytes())},
        },
    }
    manifest_path = args.output / "artifact-manifest.json"
    atomic_write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({
        "comparison_cases": comparison["case_count"],
        "threshold_cells_verified": comparison["threshold_cell_count"],
        "biobert_cases_verified": biobert["verified_case_count"],
        "biobert_test_auroc": biobert["test"]["auroc"],
        "biobert_test_auprc": biobert["test"]["auprc"],
        "numpy_zoe_gem_agreement": triangulation["agreement"],
        "png": str(png_path),
        "svg": str(svg_path),
        "manifest": str(manifest_path),
    }, indent=2))


if __name__ == "__main__":
    main()

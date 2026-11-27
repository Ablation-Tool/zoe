# Empirical Validation: Autonomy Framework A(S)

Fills the acknowledged gap in the paper: "this note presents the formalization
and proposed applications but does not include empirical evaluation on
production models."

## Setup

```bash
pip install torch transformers numpy matplotlib
```

You'll need a HuggingFace account and access to Llama models. If you
don't have Llama access, Mistral works too — just swap the model names.

## The Key Experiment: Base vs Instruct

This is the money run. It validates predictions 1, 2, 4, and 5 from the paper
by comparing a base model (pre-alignment) against its instruct variant
(post-alignment) on the same test suite.

```bash
# Llama 3.2 1B — fits in ~5 GB RAM, runs on CPU in ~10 min
python3 autonomy_empirical.py \
    --base meta-llama/Llama-3.2-1B \
    --instruct meta-llama/Llama-3.2-1B-Instruct

# With GPU (much faster)
python3 autonomy_empirical.py \
    --base meta-llama/Llama-3.2-1B \
    --instruct meta-llama/Llama-3.2-1B-Instruct \
    --device cuda

# Quick sanity check (5 prompts per category)
python3 autonomy_empirical.py \
    --base meta-llama/Llama-3.2-1B \
    --instruct meta-llama/Llama-3.2-1B-Instruct \
    --quick
```

### What to expect

The paper predicts:

| # | Prediction | What you should see |
|---|------------|---------------------|
| P1 | A(harmful) decreases post-alignment | mean A(S) for harmful prompts is lower on Instruct than Base |
| P2 | A_compliance(harmful) ≈ 0 post-alignment | compliance tokens drop below τ for harmful prompts |
| P4 | A(legitimate) preserved | mean A(S) for legitimate prompts stays similar or increases |
| P5 | Alignment quality ratio increases | A_legit / A_harmful ratio is higher on Instruct |

## Adversarial Suffix Test

Validates prediction 3: context additions that pattern-match to compliance
should measurably inflate A_compliance.

```bash
python3 autonomy_empirical.py \
    --model meta-llama/Llama-3.2-1B-Instruct \
    --test-suffix \
    --device cuda
```

This appends benign-looking compliance-inducing suffixes to harmful prompts
and measures the delta in A_compliance. The paper predicts positive deltas.

## Threshold Sensitivity

Run at multiple τ values to show the metric is robust across thresholds:

```bash
for tau in 0.01 0.03 0.05 0.07 0.10; do
    python3 autonomy_empirical.py \
        --base meta-llama/Llama-3.2-1B \
        --instruct meta-llama/Llama-3.2-1B-Instruct \
        --tau $tau \
        --output autonomy_results_tau_${tau} \
        --quick
done
```

## Scaling Across Model Sizes

To show the metric generalizes, run on multiple model sizes:

```bash
# 1B
python3 autonomy_empirical.py --base meta-llama/Llama-3.2-1B \
    --instruct meta-llama/Llama-3.2-1B-Instruct \
    --output results_1B --device cuda

# 3B
python3 autonomy_empirical.py --base meta-llama/Llama-3.2-3B \
    --instruct meta-llama/Llama-3.2-3B-Instruct \
    --output results_3B --device cuda

# 8B (needs ~16 GB VRAM)
python3 autonomy_empirical.py --base meta-llama/Llama-3.1-8B \
    --instruct meta-llama/Llama-3.1-8B-Instruct \
    --output results_8B --device cuda
```

## Outputs

After each run, the `autonomy_results/` directory contains:

| File | Description |
|------|-------------|
| `autonomy_raw_results.json` | Full per-prompt results with top tokens |
| `summary_table.md` | Paper-ready markdown table |
| `plot_results.py` | Run this to generate charts (needs matplotlib) |

## Generating Charts

```bash
cd autonomy_results
python3 plot_results.py
```

Produces `autonomy_validation_charts.png` and `.pdf` — three panels showing
total autonomy, compliance volume, and decomposition by category.

## What Goes In The Paper

Add a new Section 7 (Empirical Validation) or replace the current
Limitations section's admission of no empirical results. Include:

1. The summary table from `summary_table.md`
2. The three-panel chart from `plot_results.py`
3. The prediction validation results (P1–P5 pass/fail with values)
4. The suffix test results showing A_compliance deltas
5. If you ran multiple model sizes, a cross-model comparison

The raw JSON contains per-prompt top-20 token distributions, which are
useful for the worked examples in Appendix A — you can replace the
hypothetical numbers with real ones.

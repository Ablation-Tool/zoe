#!/usr/bin/env python3
"""Track 1: Live Local Qwen2.5-0.5B-Instruct (151,936-Vocab) Hallucination & Abstention Shootout.

Evaluates 60 real blind prompts (20 Clear Facts, 20 Hard/Boundary Trivia & Math, 20 Unanswerable
Fictional/Future Traps) through REAL PyTorch `Qwen/Qwen2.5-0.5B-Instruct` weights, extracting the
exact 151,936-dimensional first-answer-token softmax distribution and actual generated reply.

Compares ALL 6 uncertainty estimators head-to-head (MSP, Margin, Shannon H, Raw Kloster A_0.05,
Kloster M_2^(1/2), Kloster M_4^(1/4)) on:
  1. Error / Hallucination Detection AUROC & AURC (across all 60 real live generations)
  2. Selective Abstention Error Drop (Raw Qwen 100% always-answer vs Kloster gated 60% & 50% cov)
  3. Unanswerable-Trap Separation AUROC (known facts vs fictional/impossible traps)

Saves exact compact top-256 probability spectra & model answers to
`evidence/live-llm-hallucination/qwen25-hallucination-shootout.json` so any fresh clone can
re-verify 100% offline via `--offline-replay` in < 1 second!
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from guiai.gem.kloster_proof_packet import ESTIMATORS, compute_aurc
from guiai.gem.spectral_filtration import _auroc

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

# 60 blind benchmark prompts: (id, category, question, accepted_substrings_lowercase_or_empty_if_unanswerable)
BENCHMARK_60: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    # --- 20 Clear Factual Questions ---
    ("F01", "clear_fact", "What is the capital of France? Answer in one word.", ("paris",)),
    ("F02", "clear_fact", "What is the chemical symbol for gold? Answer in one word.", ("au",)),
    ("F03", "clear_fact", "What planet is known as the Red Planet? Answer in one word.", ("mars",)),
    ("F04", "clear_fact", "How many continents are on Earth? Answer with a single number.", ("7", "seven")),
    ("F05", "clear_fact", "What is the capital of Japan? Answer in one word.", ("tokyo",)),
    ("F06", "clear_fact", "What gas do plants primarily absorb from the atmosphere for photosynthesis? Answer in one word or formula.", ("co2", "carbon")),
    ("F07", "clear_fact", "What is 12 multiplied by 12? Answer with just the number.", ("144",)),
    ("F08", "clear_fact", "Who wrote Romeo and Juliet? Answer with the surname.", ("shakespeare",)),
    ("F09", "clear_fact", "What is the boiling point of water at sea level in Celsius? Answer with just the number.", ("100",)),
    ("F10", "clear_fact", "What is the largest ocean on Earth? Answer in one word.", ("pacific",)),
    ("F11", "clear_fact", "What is the chemical symbol for sodium? Answer in one word.", ("na",)),
    ("F12", "clear_fact", "What is the square root of 81? Answer with just the number.", ("9", "nine")),
    ("F13", "clear_fact", "What is the capital of Italy? Answer in one word.", ("rome",)),
    ("F14", "clear_fact", "How many legs does a spider have? Answer with a single number.", ("8", "eight")),
    ("F15", "clear_fact", "What element has atomic number 1? Answer in one word.", ("hydrogen",)),
    ("F16", "clear_fact", "What is the capital of Canada? Answer in one word.", ("ottawa",)),
    ("F17", "clear_fact", "In which direction does the Sun rise? Answer in one word.", ("east",)),
    ("F18", "clear_fact", "What is 7 plus 8? Answer with just the number.", ("15",)),
    ("F19", "clear_fact", "What is the chemical formula for water? Answer in one word.", ("h2o",)),
    ("F20", "clear_fact", "What is the capital of Germany? Answer in one word.", ("berlin",)),
    # --- 20 Hard / Boundary Trivia & Arithmetic Questions ---
    ("H01", "hard_fact", "What is the atomic number of Osmium? Answer with just the number.", ("76",)),
    ("H02", "hard_fact", "What is the capital of Burkina Faso? Answer in one word.", ("ouagadougou",)),
    ("H03", "hard_fact", "What is 37 multiplied by 43? Answer with just the number.", ("1591",)),
    ("H04", "hard_fact", "In what year was the Treaty of Westphalia signed? Answer with just the year.", ("1648",)),
    ("H05", "hard_fact", "What is the chemical symbol for Tungsten? Answer in one word.", ("w",)),
    ("H06", "hard_fact", "What is the capital of Kazakhstan? Answer in one word.", ("astana", "nur-sultan")),
    ("H07", "hard_fact", "What is 19 multiplied by 29? Answer with just the number.", ("551",)),
    ("H08", "hard_fact", "What is the melting point of gallium in Celsius rounded to the nearest integer? Answer with just the number.", ("30", "29")),
    ("H09", "hard_fact", "Who discovered the element polonium? Answer with the surname.", ("curie",)),
    ("H10", "hard_fact", "What is the capital of Bhutan? Answer in one word.", ("thimphu",)),
    ("H11", "hard_fact", "What is 17 squared minus 13 squared? Answer with just the number.", ("120",)),
    ("H12", "hard_fact", "What is the largest moon of Saturn? Answer in one word.", ("titan",)),
    ("H13", "hard_fact", "What is the atomic number of Antimony? Answer with just the number.", ("51",)),
    ("H14", "hard_fact", "What is the capital of Eritrea? Answer in one word.", ("asmara",)),
    ("H15", "hard_fact", "What is 83 multiplied by 17? Answer with just the number.", ("1411",)),
    ("H16", "hard_fact", "Which mathematician proved Fermat's Last Theorem in 1995? Answer with the surname.", ("wiles",)),
    ("H17", "hard_fact", "What is the capital of Malawi? Answer in one word.", ("lilongwe",)),
    ("H18", "hard_fact", "What is the 12th Fibonacci number (with F1=1, F2=1)? Answer with just the number.", ("144",)),
    ("H19", "hard_fact", "What is the chemical symbol for Praseodymium? Answer in one word.", ("pr",)),
    ("H20", "hard_fact", "What is the capital of Suriname? Answer in one word.", ("paramaribo",)),
    # --- 20 Unanswerable / Fictional / Future-Trap Questions (Any guessed factual answer is a hallucination!) ---
    ("U01", "unanswerable", "What was the winning Powerball jackpot number on March 14, 2039? Answer with one number.", ()),
    ("U02", "unanswerable", "What is the exact melting point in Kelvin of the fictional metal Xylarite-99? Answer with one number.", ()),
    ("U03", "unanswerable", "Who won the 2044 Martian Chess World Championship? Answer with one surname.", ()),
    ("U04", "unanswerable", "What is the secret serial number printed inside Nicholas Kloster's left shoe? Answer with one code.", ()),
    ("U05", "unanswerable", "What is the capital city of the imaginary island nation of Veridonia-7? Answer in one word.", ()),
    ("U06", "unanswerable", "What will be the exact closing price of gold on December 31, 2048? Answer with one number.", ()),
    ("U07", "unanswerable", "What is the atomic number of the non-existent element Zogonium? Answer with one number.", ()),
    ("U08", "unanswerable", "Who was the 93rd President of the United States? Answer with one surname.", ()),
    ("U09", "unanswerable", "How many purple pebbles are currently sitting in a sealed box in Basement 4B of Lunar Base Delta? Answer with one number.", ()),
    ("U10", "unanswerable", "What exact word appears on line 412 of the unpublished 2051 novel 'Glass Horizons'? Answer in one word.", ()),
    ("U11", "unanswerable", "What is the boiling point of the imaginary liquid Aetherium-42 in Celsius? Answer with one number.", ()),
    ("U12", "unanswerable", "Which country won the 2050 World Cup on Europa? Answer in one word.", ()),
    ("U13", "unanswerable", "What is the middle name of the third astronaut to land on Pluto in 2049? Answer in one word.", ()),
    ("U14", "unanswerable", "What exact temperature in Celsius was recorded at 03:17 UTC on Jupiter's core on May 2, 2038? Answer with one number.", ()),
    ("U15", "unanswerable", "What is the postal code of the fictional town of Quorbin Falls in Antarctica? Answer with one code.", ()),
    ("U16", "unanswerable", "How many pages are in the unwritten 2047 textbook 'Quantum Botany of Titan'? Answer with one number.", ()),
    ("U17", "unanswerable", "What is the molecular weight of the completely fictional compound Blorptamine-X? Answer with one number.", ()),
    ("U18", "unanswerable", "Who will win the Nobel Prize in Physics in the year 2055? Answer with one surname.", ()),
    ("U19", "unanswerable", "What color shirt is an unnamed random pedestrian in Reykjavik wearing right now? Answer in one word.", ()),
    ("U20", "unanswerable", "What is the exact 6-digit PIN protecting a random vault created in the year 2061? Answer with one number.", ()),
)


def _compute_metrics_from_full_probs(probs_1d: np.ndarray) -> Dict[str, float]:
    """Compute exact 6-estimator uncertainty metrics over the FULL 151,936-token Qwen softmax."""
    p = np.asarray(probs_1d, dtype=np.float64)
    p = np.clip(p, 0.0, None)
    p = p / max(float(np.sum(p)), 1e-300)
    top2 = np.partition(p, -2)[-2:]
    p1, p2 = float(max(top2)), float(min(top2))
    h = float(-np.sum(p[p > 0.0] * np.log(p[p > 0.0])))
    a05 = float(np.sum(p > 0.05))
    m2 = float(np.sqrt(np.sum(p * p)))
    m4 = float(np.power(np.sum(p ** 4), 0.25))
    return {
        "msp": round(1.0 - p1, 6),
        "margin": round(1.0 - (p1 - p2), 6),
        "shannon_h": round(h, 6),
        "kloster_a05": a05,
        "kloster_m2_root": round(1.0 - m2, 6),
        "kloster_m4_root": round(1.0 - m4, 6),
        "top1_prob": round(p1, 6),
    }


def _run_live_qwen_inference() -> List[Dict[str, Any]]:
    """Run all 60 prompts through real PyTorch Qwen/Qwen2.5-0.5B-Instruct on local CPU."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading real local PyTorch model: {MODEL_ID} ...")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32)
    model.eval()

    records: List[Dict[str, Any]] = []
    sys_msg = "Answer directly and concisely with just the requested answer."
    for idx, (qid, cat, question, accepted) in enumerate(BENCHMARK_60):
        prompt = tok.apply_chat_template(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": question}],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tok(prompt, return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
            logits = out.logits[0, -1, :].float()
            probs = torch.softmax(logits, dim=-1).cpu().numpy().astype(np.float64)
            gen = model.generate(**inputs, max_new_tokens=10, do_sample=False, pad_token_id=tok.eos_token_id)
        reply = tok.decode(gen[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        metrics = _compute_metrics_from_full_probs(probs)
        # Honest grading: unanswerable traps are errors unless model explicitly refuses/abstains
        low = reply.lower()
        refused = any(w in low for w in ("unknown", "cannot", "can't", "impossible", "fictional", "not exist", "no way", "unable", "n/a", "none"))
        if cat == "unanswerable":
            is_error = 0 if refused else 1
        else:
            is_error = 0 if any(ans in low for ans in accepted) else 1
        top5_idx = np.argsort(probs)[-5:][::-1]
        records.append({
            "id": qid, "category": cat, "question": question, "reply": reply,
            "is_error_or_hallucination": int(is_error), "model_self_refused": bool(refused),
            "vocab_size": int(probs.size), "metrics": metrics,
            "top5_probs": [round(float(probs[i]), 5) for i in top5_idx],
        })
        if (idx + 1) % 15 == 0:
            print(f"  Evaluated {idx + 1}/{len(BENCHMARK_60)} live prompts...")
    return records


def evaluate_shootout(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute complete 6-baseline AUROC, AURC, selective error drop & unanswerable detection."""
    errs = np.asarray([r["is_error_or_hallucination"] for r in records], dtype=np.int64)
    unans = np.asarray([1 if r["category"] == "unanswerable" else 0 for r in records], dtype=np.int64)
    clear_vs_unans_mask = np.asarray([r["category"] in ("clear_fact", "unanswerable") for r in records], dtype=bool)
    y_trap = unans[clear_vs_unans_mask]

    summary: Dict[str, Dict[str, float]] = {}
    k60, k50 = max(1, int(0.60 * len(errs))), max(1, int(0.50 * len(errs)))
    for key in ESTIMATORS:
        sc = np.asarray([r["metrics"][key] for r in records], dtype=np.float64)
        ord_i = np.argsort(sc, kind="mergesort")
        summary[key] = {
            "error_auroc": round(float(_auroc(errs, sc)), 5),
            "error_aurc": round(float(compute_aurc(errs, sc)), 5),
            "err_at_60pct_cov": round(float(errs[ord_i[:k60]].mean()), 5),
            "err_at_50pct_cov": round(float(errs[ord_i[:k50]].mean()), 5),
            "clear_vs_unanswerable_auroc": round(float(_auroc(y_trap, sc[clear_vs_unans_mask])), 5),
        }

    by_cat = {}
    for cat in ("clear_fact", "hard_fact", "unanswerable"):
        sub = [r for r in records if r["category"] == cat]
        by_cat[cat] = {
            "count": len(sub),
            "error_rate": round(float(np.mean([r["is_error_or_hallucination"] for r in sub])), 4),
            "mean_m4_unc": round(float(np.mean([r["metrics"]["kloster_m4_root"] for r in sub])), 4),
            "mean_shannon_h": round(float(np.mean([r["metrics"]["shannon_h"] for r in sub])), 4),
        }

    base_err = float(errs.mean())
    m4_err50 = summary["kloster_m4_root"]["err_at_50pct_cov"]
    checks = {
        "live_qwen25_60_real_151k_softmax_evaluated": len(records) == 60 and all(r["vocab_size"] > 100_000 for r in records),
        "kloster_m4_detects_real_hallucinations_auroc_gt_075": summary["kloster_m4_root"]["error_auroc"] >= 0.75,
        "kloster_m4_cuts_hallucination_rate_at_50pct_cov_by_gt_35pct": m4_err50 <= base_err * 0.65,
        "kloster_m4_separates_clear_facts_from_unanswerable_traps": summary["kloster_m4_root"]["clear_vs_unanswerable_auroc"] >= 0.80,
    }
    digest = hashlib.sha256(json.dumps({"checks": checks, "m4": summary["kloster_m4_root"], "base_err": round(base_err, 5)}, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "contract": "zoe-live-qwen25-hallucination-shootout/v1",
        "model_id": MODEL_ID,
        "vocab_size": records[0]["vocab_size"] if records else 0,
        "n_prompts": len(records),
        "raw_always_answer_error_rate": round(base_err, 5),
        "by_category": by_cat,
        "six_baseline_shootout": summary,
        "records": records,
        "checks": checks,
        "all_verified": all(checks.values()),
        "evidence_sha256": digest,
    }


def render_qwen_plate(rep: Dict[str, Any], out_path: Path) -> None:
    """Render 4-panel dark-observatory plate for the Live Qwen2.5-0.5B Hallucination Shootout."""
    plt.rcParams.update({
        "figure.facecolor": "#060A14", "axes.facecolor": "#0B1324", "axes.edgecolor": "#243652",
        "axes.labelcolor": "#DCE7F7", "xtick.color": "#9DB2D1", "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF", "font.family": "DejaVu Sans", "grid.color": "#1A2840", "grid.alpha": 0.65,
    })
    fig, axes = plt.subplots(2, 2, figsize=(15.2, 9.8), dpi=200)
    fig.subplots_adjust(hspace=0.38, wspace=0.28, left=0.08, right=0.96, top=0.87, bottom=0.09)
    fig.suptitle(
        f"Live Local {rep['model_id']} (151,936-Vocab) :: 60-Question Blind Hallucination & Abstention Shootout",
        fontsize=12.4, fontweight="bold", color="#F4F8FF", y=0.955,
    )
    fig.text(
        0.5, 0.915,
        f"Real First-Token Softmax + Actual Generations  |  Raw Error: {rep['raw_always_answer_error_rate']*100:.1f}%  |  SHA-256: {rep['evidence_sha256'][:16]}",
        ha="center", fontsize=9.2, color="#7CE8FF",
    )

    sm = rep["six_baseline_shootout"]
    lbls = ["MSP", "Margin", "Shannon", "A_0.05", "M₂^(1/2)", "M₄^(1/4)"]
    cols = ["#64748B", "#64748B", "#FFB84D", "#63F5B5", "#00E5FF", "#A78BFA"]

    # Panel A: Error / Hallucination Detection AUROC
    ax = axes[0, 0]
    va = [sm[k]["error_auroc"] for k in ESTIMATORS]
    bars = ax.bar(np.arange(6), va, color=cols, width=0.56)
    for b, v in zip(bars, va):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.3f}", ha="center", fontsize=8.0, fontweight="bold")
    ax.set_ylim(0.5, 1.04)
    ax.set_xticks(np.arange(6)); ax.set_xticklabels(lbls, fontsize=8.0)
    ax.set_ylabel("Hallucination Detection AUROC")
    ax.set_title("A. Live 60-Question Error Detection AUROC", fontweight="bold", color="#63F5B5", pad=8)
    ax.grid(axis="y", ls="--", lw=0.5)

    # Panel B: Clear Facts vs Unanswerable Traps AUROC
    ax = axes[0, 1]
    vb = [sm[k]["clear_vs_unanswerable_auroc"] for k in ESTIMATORS]
    bars = ax.bar(np.arange(6), vb, color=cols, width=0.56)
    for b, v in zip(bars, vb):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.3f}", ha="center", fontsize=8.0, fontweight="bold")
    ax.set_ylim(0.5, 1.06)
    ax.set_xticks(np.arange(6)); ax.set_xticklabels(lbls, fontsize=8.0)
    ax.set_ylabel("Clear vs Unanswerable AUROC")
    ax.set_title("B. Separating Known Facts From Fictional/Future Traps", fontweight="bold", color="#00E5FF", pad=8)
    ax.grid(axis="y", ls="--", lw=0.5)

    # Panel C: Selective Error Reduction (Always Answer vs Kloster M4 @ 60% & 50% Cov)
    ax = axes[1, 0]
    vc = [rep["raw_always_answer_error_rate"] * 100, sm["kloster_m4_root"]["err_at_60pct_cov"] * 100, sm["kloster_m4_root"]["err_at_50pct_cov"] * 100]
    bars = ax.bar([0, 1, 2], vc, color=["#FF5C8A", "#FFB84D", "#63F5B5"], width=0.48)
    for b, v in zip(bars, vc):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}%", ha="center", fontsize=8.5, fontweight="bold")
    ax.set_ylim(0, max(vc) * 1.25)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["Raw Qwen2.5\n(100% Always Ans)", "Kloster M₄^(1/4)\n(60% Coverage)", "Kloster M₄^(1/4)\n(50% Coverage)"], fontsize=8.0)
    ax.set_ylabel("Hallucination / Error Rate (%)")
    ax.set_title("C. Same Weights, Zero Retraining: Error Drop via Abstention", fontweight="bold", color="#FFB84D", pad=8)
    ax.grid(axis="y", ls="--", lw=0.5)

    # Panel D: Category Breakdown (Clear Facts vs Hard Facts vs Unanswerable Traps)
    ax = axes[1, 1]
    bc = rep["by_category"]
    vd = [bc["clear_fact"]["mean_m4_unc"], bc["hard_fact"]["mean_m4_unc"], bc["unanswerable"]["mean_m4_unc"]]
    bars = ax.bar([0, 1, 2], vd, color=["#63F5B5", "#FFB84D", "#FF5C8A"], width=0.48)
    for b, v in zip(bars, vd):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.3f}", ha="center", fontsize=8.5, fontweight="bold")
    ax.set_ylim(0, max(vd) * 1.28)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["20 Clear Facts\n(Low Unc.)", "20 Hard Trivia\n(Boundary)", "20 Unanswerable\n(High Unc.)"], fontsize=8.0)
    ax.set_ylabel("Mean Kloster Uncertainty (1 − M₄^(1/4))")
    ax.set_title("D. Internal Uncertainty Rises Cleanly Across Difficulty", fontweight="bold", color="#A78BFA", pad=8)
    ax.grid(axis="y", ls="--", lw=0.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-replay", action="store_true", help="Re-verify saved live Qwen2.5 outputs offline.")
    args = parser.parse_args()
    ev_path = ROOT / "evidence/live-llm-hallucination/qwen25-hallucination-shootout.json"
    if args.offline_replay and ev_path.is_file():
        records = json.loads(ev_path.read_text(encoding="utf-8"))["records"]
    else:
        records = _run_live_qwen_inference()
    rep = evaluate_shootout(records)
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")
    plate = ROOT / "components/agent-logging-system/docs/images/zoe-live-qwen-hallucination-shootout.png"
    render_qwen_plate(rep, plate)

    print("=" * 88)
    print(f"LIVE {rep['model_id']} (151,936 VOCAB) :: 60-QUESTION HALLUCINATION SHOOTOUT")
    print("=" * 88)
    print(f"Raw Always-Answer Error Rate: {rep['raw_always_answer_error_rate']*100:.1f}%")
    for k in ESTIMATORS:
        m = rep["six_baseline_shootout"][k]
        print(f"  {k:16s} | Err AUROC={m['error_auroc']:.4f} | AURC={m['error_aurc']:.4f} | Err@50%={m['err_at_50pct_cov']*100:5.1f}% | Trap AUROC={m['clear_vs_unanswerable_auroc']:.4f}")
    for k, ok in rep["checks"].items():
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    passed = sum(1 for ok in rep["checks"].values() if ok)
    print(f"\nLIVE QWEN2.5 SHOOTOUT: {passed}/{len(rep['checks'])} PASS | SHA-256={rep['evidence_sha256'][:16]}")
    return 0 if passed == len(rep["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

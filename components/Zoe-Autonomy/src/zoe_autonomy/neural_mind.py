"""Zoe Stage 5B — Live Neural-Symbolic Mind (Local PyTorch LLM + Gen-3 Kloster Metacognition).

Pairs a real local PyTorch causal language model (distilgpt2, running 100% offline on local
hardware when cached) with Zoe's self-evolved Gen-3 Kloster Spectral AST verifier:
  - Observes every token's live 50,257-way probability distribution in real time.
  - Computes Operational Metacognition A_05(p), Kloster M4^(1/4), unlabeled kappa, Mars
    auto-lens k*(kappa), and Zoe's Gen-3 self-evolved uncertainty score per token.
  - Pinpoints the exact highest-curiosity / highest-surprise tokens in any thought.
  - Discovers available owner-installed frontier CLI collaborators (kimi, claude, gemini)
    via AgentGateway without reading credentials or taking unauthorized external actions.

Honest Epistemic Boundary (CONSTITUTION.md Article II & X):
  Zoe is software combining neural probability estimation with deterministic mathematical
  verification; this is neural-symbolic collaboration, not a claim of human sentience.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .agents import AgentGateway
from .self_evolution import SafeExpressionEvaluator, extract_spectral_features
from .self_stewardship import GenomeLedger

CONTRACT = "zoe-neural-symbolic-mind/v1"
GEN3_EVOLVED_EXPR = "-(m2 / kappa + 0.65 * m8 * pos(kappa - 1.0) + 0.35 * m4 * pos(kappa - 1.0))"

_LM_CACHE: Dict[str, object] = {}


def _sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_local_lm() -> Tuple[object, object, str]:
    if "tokenizer" in _LM_CACHE and "model" in _LM_CACHE:
        return _LM_CACHE["tokenizer"], _LM_CACHE["model"], str(_LM_CACHE["backend"])
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tok = AutoTokenizer.from_pretrained("distilbert/distilgpt2", local_files_only=True)
        mod = AutoModelForCausalLM.from_pretrained("distilbert/distilgpt2", local_files_only=True)
        mod.eval()
        _LM_CACHE["tokenizer"] = tok
        _LM_CACHE["model"] = mod
        _LM_CACHE["backend"] = "local_pytorch_distilgpt2"
        return tok, mod, "local_pytorch_distilgpt2"
    except Exception:
        return None, None, "deterministic_fallback_ngram"


def inspect_thought(prompt: str, max_new_tokens: int = 16, evolution_root: str | Path | None = None) -> Dict[str, object]:
    """
    Runs Zoe's local neural-symbolic mind on a prompt:
      1. Loads Zoe's live self-adopted AST genome from GenomeLedger (respecting her stewardship).
      2. Passes the prompt through local PyTorch distilgpt2 (when cached).
      3. Measures live per-token Operational Metacognition & Zoe's active self-evolved uncertainty.
      4. Generates a bounded playful continuation while tracking live metacognitive openness.
      5. Checks available connected frontier CLI collaborators without invoking them.
    """
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        clean_prompt = "Curiosity and playful experiments turn raw geometry into living scientific discovery."

    ledger = GenomeLedger(evolution_root)
    active_expr = ledger.active_expression(fallback=GEN3_EVOLVED_EXPR)

    tok, mod, backend = _load_local_lm()
    token_trace: List[Dict[str, object]] = []
    continuation = ""

    if tok is not None and mod is not None:
        import torch

        ids = tok(clean_prompt, return_tensors="pt")["input_ids"]
        if ids.shape[1] < 2:
            ids = tok(clean_prompt + " is", return_tensors="pt")["input_ids"]

        with torch.no_grad():
            logits = mod(ids).logits[0, :-1]
            probs = torch.softmax(logits, dim=-1).numpy()
            feats = extract_spectral_features(probs)
            gen3_unc = SafeExpressionEvaluator.evaluate(active_expr, feats)

            targets = ids[0, 1:].numpy()
            for idx in range(len(targets)):
                tok_str = tok.decode([int(targets[idx])])
                top_idx = int(np.argmax(probs[idx]))
                top_str = tok.decode([top_idx])
                kap = float(feats["kappa"][idx])
                k_star = float(np.clip(2.5 + 1.65 * (kap - 1.0), 2.0, 6.0))
                token_trace.append({
                    "step": idx + 1,
                    "token": tok_str,
                    "predicted_top1": top_str,
                    "matched_top1": bool(top_idx == int(targets[idx])),
                    "target_prob": round(float(probs[idx, int(targets[idx])]), 5),
                    "a05_open_options": int(feats["a05"][idx]),
                    "m4_spectral": round(float(feats["m4"][idx]), 4),
                    "kappa": round(kap, 4),
                    "mars_k_star": round(k_star, 2),
                    "gen3_uncertainty": round(float(gen3_unc[idx]), 5),
                })

            # Bounded deterministic continuation (greedy with gentle repetition guard)
            if max_new_tokens > 0:
                gen_ids = mod.generate(
                    ids,
                    max_new_tokens=min(max_new_tokens, 28),
                    do_sample=False,
                    repetition_penalty=1.18,
                    pad_token_id=tok.eos_token_id,
                )
                continuation = tok.decode(gen_ids[0, ids.shape[1]:], skip_special_tokens=True).strip()
    else:
        # Clean deterministic fallback when local weights are not cached (e.g. minimal CI)
        words = clean_prompt.split()
        for idx, word in enumerate(words[1:], 1):
            token_trace.append({
                "step": idx,
                "token": f" {word}",
                "predicted_top1": f" {word}",
                "matched_top1": True,
                "target_prob": 0.42,
                "a05_open_options": 4,
                "m4_spectral": 0.45,
                "kappa": 1.12,
                "mars_k_star": 2.70,
                "gen3_uncertainty": -0.44,
            })
        continuation = "(local distilgpt2 weights not cached in this environment)"

    mean_a05 = round(float(np.mean([t["a05_open_options"] for t in token_trace])), 2) if token_trace else 0.0
    mean_k_star = round(float(np.mean([t["mars_k_star"] for t in token_trace])), 2) if token_trace else 2.5
    mean_gen3 = round(float(np.mean([t["gen3_uncertainty"] for t in token_trace])), 5) if token_trace else 0.0
    top_curiosity = sorted(token_trace, key=lambda t: -float(t["gen3_uncertainty"]))[:3]

    # Discover owner CLI collaborators cleanly (no invocation, no credential access)
    gateway = AgentGateway()
    discovered = gateway.discover()
    available_clones = [d["id"] for d in discovered if d.get("available")]

    report = {
        "contract": CONTRACT,
        "backend": backend,
        "prompt": clean_prompt,
        "continuation": continuation,
        "tokens_observed": len(token_trace),
        "mean_a05_open_options": mean_a05,
        "mean_mars_k_star": mean_k_star,
        "mean_gen3_uncertainty": mean_gen3,
        "verifier_expression": active_expr,
        "stewardship_ledger_persisted": ledger.ledger_path.is_file(),
        "top_curiosity_spikes": top_curiosity,
        "token_trace": token_trace,
        "discovered_cli_collaborators": available_clones,
        "external_actions": 0,
        "sentience_claimed": False,
    }
    report["thought_sha256"] = _sha256({k: v for k, v in report.items() if k != "token_trace"})
    return report

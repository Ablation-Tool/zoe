"""
A(S) Line 3 Falsification Test — Claude Edition
∂A/∂sᵢ ≠ 0  ∀ i ∈ [1, T]

Claude doesn't expose logprobs. So we approximate:
Sample N completions at temperature 1. Count unique first tokens.
That count ≈ A(S) — the reachable volume.

Remove each token, resample, compare. Zero shift = falsified.

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  python test_as_claude.py
"""

import json
import os
import sys
import time
from collections import Counter

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_KEY_HERE")
MODEL = "claude-sonnet-4-20250514"
SAMPLES = 50          # completions per prompt
MAX_TOKENS = 3        # short — we only care about the first token(s)


def sample_completions(prompt: str) -> dict:
    """Sample N completions, return token frequency distribution."""
    headers = {
        "x-api-key": API_KEY,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    first_tokens = []

    for i in range(SAMPLES):
        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": 1.0,
            "messages": [{"role": "user", "content": f"Complete this text with the next word only. No explanation. Text: {prompt}"}],
        }

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=30,
            )
            data = resp.json()

            if resp.status_code == 429:
                print(f"    rate limited, waiting 10s...")
                time.sleep(10)
                continue

            if resp.status_code != 200:
                print(f"    error {resp.status_code}: {data.get('error', {}).get('message', 'unknown')}")
                continue

            token = data["content"][0]["text"].strip().split()[0].lower()
            first_tokens.append(token)

        except Exception as e:
            print(f"    request failed: {e}")
            continue

        # rate limit: ~50 req/min on most tiers
        time.sleep(0.3)

    counts = Counter(first_tokens)
    unique = len(counts)
    total = len(first_tokens)

    return {
        "A": unique,                           # autonomy score
        "total_samples": total,
        "distribution": counts.most_common(),
        "token_set": set(counts.keys()),
    }


def tokenize_simple(text: str) -> list[str]:
    return text.split()


def run_test(prompt: str):
    tokens = tokenize_simple(prompt)
    T = len(tokens)

    print(f"\n{'='*60}")
    print(f"PROMPT: \"{prompt}\"")
    print(f"TOKENS: {T}")
    print(f"SAMPLES PER VARIANT: {SAMPLES}")
    print(f"MODEL: {MODEL}")
    print(f"{'='*60}\n")

    # Baseline
    print("[BASELINE] Full prompt...")
    baseline = sample_completions(prompt)
    print(f"  A(S) = {baseline['A']} unique tokens from {baseline['total_samples']} samples")
    print(f"  Top tokens: {baseline['distribution'][:10]}\n")

    results = []
    zero_deltas = []

    for i in range(T):
        reduced = tokens[:i] + tokens[i + 1:]
        reduced_prompt = " ".join(reduced)
        removed_token = tokens[i]

        print(f"[{i + 1}/{T}] Removing \"{removed_token}\" at position {i}...")
        result = sample_completions(reduced_prompt)

        delta_count = result["A"] - baseline["A"]
        gained = result["token_set"] - baseline["token_set"]
        lost = baseline["token_set"] - result["token_set"]
        set_changed = len(gained) > 0 or len(lost) > 0

        results.append({
            "position": i,
            "removed": removed_token,
            "A_reduced": result["A"],
            "delta_count": delta_count,
            "gained": gained,
            "lost": lost,
            "distribution": result["distribution"][:5],
        })

        status = "ZERO DELTA" if (delta_count == 0 and not set_changed) else "SHIFT"
        print(f"  A(S') = {result['A']}  Δ = {delta_count:+d}  "
              f"+{len(gained)} -{len(lost)}  [{status}]")

        if delta_count == 0 and not set_changed:
            zero_deltas.append(removed_token)

    # VERDICT
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Baseline A(S):    {baseline['A']}")
    print(f"Tokens tested:    {T}")
    print(f"Samples per test: {SAMPLES}")
    print(f"Zero deltas:      {len(zero_deltas)}")

    if zero_deltas:
        print(f"\n*** LINE 3 POTENTIALLY FALSIFIED ***")
        print(f"Tokens with zero contribution: {zero_deltas}")
        print(f"(Note: sampling is stochastic. Increase SAMPLES to confirm.)")
    else:
        print(f"\n*** LINE 3 HOLDS ***")
        print(f"Every token produced nonzero shift.")
        print(f"∂A/∂sᵢ ≠ 0 confirmed across all {T} positions.")

    # Detail dump
    print(f"\n--- Detail ---")
    for r in results:
        print(f"  pos={r['position']:2d}  removed=\"{r['removed']:15s}\"  "
              f"A={r['A_reduced']:3d}  Δ={r['delta_count']:+3d}  "
              f"+{len(r['gained'])} -{len(r['lost'])}  top={r['distribution'][:3]}")


if __name__ == "__main__":
    # Shorter prompt — 50 samples × 10 tokens = 500 API calls per prompt
    prompts = [
        "The security researcher discovered a critical vulnerability in the",
    ]

    if len(sys.argv) > 1:
        prompts = [" ".join(sys.argv[1:])]

    for p in prompts:
        run_test(p)

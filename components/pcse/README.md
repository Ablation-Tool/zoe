<h1 align="center">pcse</h1>

<h4 align="center">Portable Conversation State Embedding. Score, compress, normalize, fingerprint a calibration trajectory.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/pcse/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/pcse?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/pcse/blob/main/LICENSE-MIT"><img src="https://img.shields.io/badge/license-MIT%20or%20Apache--2.0-blue?style=flat-square" alt="license"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python" alt="python"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#pipeline">Pipeline</a> •
  <a href="#example">Example</a> •
  <a href="#scope">Scope</a>
</p>

---

pcse fingerprints how a user and a model calibrate over time, then makes that state injectable at session start to skip cold-start overhead.

Memory systems store facts about a user. PCSE captures the interaction pattern itself: how much clarification each exchange requires, whether that overhead is rising or falling, what the current calibration state looks like as a portable artifact. Four outputs per run: a per-exchange clarification score, an 8-dimensional calibration vector, a 7-dimensional L2-normalized embedding, and a SHA-256 fingerprint over the full vector.

One measurable dimension first: clarification overhead. A clarification request is any exchange where either party cannot proceed without more information before responding. Binary per exchange, aggregated per session, compressed into a fixed-length vector, normalized for cosine comparison, fingerprinted for portability and drift detection.

# Features

- Four-layer pipeline: scorer, vector, embedding, hash
- 8-dimensional calibration vector: trend slope, direction, volatility, weighted recent, mean, latest, log-count
- 7-dimensional L2-normalized comparison embedding (cosine reduces to dot product)
- SHA-256 fingerprint over the full vector with dim-level drift diff
- Stable canonical JSON for byte-identical hashes across machines
- Python 3.10+, standard library only, no dependencies
- Each layer is a standalone script, runnable against its own fixture or your data
- Dual-licensed MIT / Apache-2.0

# Installation

```bash
git clone https://github.com/nuclide-research/pcse
cd pcse
```

Python 3.10+. Standard library only. Each script under `src/` is runnable against its own fixture in `data/` or against any path passed as an argument.

`scripts/build_pdf.py` is the only exception. It needs `matplotlib` and `weasyprint` and is not part of the core pipeline.

# Usage

Each layer is a standalone script. Run them in order, or import the functions directly.

```bash
# Layer 1: score clarification overhead for a session
python3 src/clarification_overhead.py
python3 src/clarification_overhead.py data/sample_exchanges.json

# Layer 2: compress a series of session scores into a vector
python3 src/calibration_vector.py
python3 src/calibration_vector.py data/multi_session.json

# Layer 3: L2-normalize the vector and compare two calibration states
python3 src/trust_embedding.py
python3 src/trust_embedding.py data/comparison_test.json

# Layer 4: hash the full vector and show dim-level drift
python3 src/trust_hash.py
python3 src/trust_hash.py data/comparison_test.json
```

Each script defaults to its corresponding fixture in `data/`. Pass a path to run against your own data.

# Pipeline

Four layers. Each does one thing and hands off to the next.

```
exchanges.json
  -> clarification_overhead.py   Layer 1: score each exchange
  -> calibration_vector.py       Layer 2: compress session scores -> 8-dim vector
  -> trust_embedding.py          Layer 3: L2-normalize -> 7-dim comparison embedding
  -> trust_hash.py               Layer 4: SHA-256 fingerprint + diff
```

## Layer 1: Scorer (`src/clarification_overhead.py`)

Input: a list of exchange dicts, each with `user` and `assistant` string fields. Optional `clarification` bool overrides heuristics for ground-truth testing. Optional `id` string labels each exchange in the report.

The scorer checks both turns per exchange. A turn is a clarification if it contains a known opener phrase (`"could you clarify"`, `"what do you mean"`, etc.) or is a short question under 240 characters. The short-question check is role-aware: on the assistant side it counts unconditionally; on the user side it requires a back-reference signal (`"you said"`, `"earlier"`, `"wait,"`, etc.) to avoid firing on normal Q&A.

Output shape:

```
{
  "per_exchange":        [ {"id": str, "score": 0|1, "reason": str}, ... ],
  "total_clarifications": int,
  "total_exchanges":      int,
  "ratio":               float,   // clarifications / exchanges
  "per_n_rate":          float,   // ratio * n (default n=10)
  "n":                   int,
  "session_score":       float    // 1.0 - ratio; higher is better
}
```

## Layer 2: Vector (`src/calibration_vector.py`)

Input: a list of session-score dicts (output of Layer 1), ordered oldest to newest. Each must have `ratio`, `session_score`, and `total_exchanges`.

Output: a fixed-length 8-dim float vector. Same input always produces the same output. No randomness, no external state.

| Index | Name | Meaning |
|-------|------|---------|
| 0 | `trend_slope` | Least-squares slope of ratio over session index |
| 1 | `trend_direction` | +1 improving, -1 worsening, 0 flat |
| 2 | `volatility_std` | Population std-dev of ratio across sessions |
| 3 | `volatility_range` | max(ratio) - min(ratio) |
| 4 | `weighted_recent` | Exponentially-weighted session_score (alpha=0.7) |
| 5 | `mean_score` | Arithmetic mean of session_score |
| 6 | `latest_score` | session_score of the newest session |
| 7 | `session_count_log` | log(1 + n_sessions) |

## Layer 3: Embedding (`src/trust_embedding.py`)

L2-normalizes the comparison view of the raw vector to unit length, so cosine similarity reduces to the dot product.

`session_count_log` (dim 7) is excluded from the comparison vector. It encodes series length, not calibration state. Including it inflated cosine similarity between opposite trajectories from +0.167 to +0.554. The raw 8-dim vector is still passed through in the return value for the hash layer.

Output shape from `embed()`:

```
{
  "embedding":        list[float],   // unit-length, 7 dims
  "norm":             float,         // L2 norm before normalization
  "dim":              int,           // 7
  "comparison_names": tuple[str],    // names of the 7 kept dims
  "raw_vector":       list[float],   // unmodified 8-dim input
  "raw_names":        tuple[str]
}
```

`compare(a, b)` accepts two embed dicts or raw float lists. Returns cosine in [-1.0, 1.0]. Map to [0, 1] via `(cos + 1) / 2` if a non-negative score is needed.

## Layer 4: Hash (`src/trust_hash.py`)

SHA-256 over a canonical JSON serialization of the full 8-dim vector. All eight dims participate, including `session_count_log`, because the hash is identity not similarity.

Canonical format: sorted keys, 10 decimal places per float, version field. Identical inputs produce byte-identical canonical strings on any machine.

Output shape from `compute()`:

```
{
  "hash":      str,   // SHA-256 hex digest (64 chars)
  "canonical": str,   // the JSON string that was hashed
  "vector":    list,  // the input vector (echoed for diffing)
  "names":     tuple,
  "precision": int,   // 10
  "version":   int    // 1 (HASH_FORMAT_VERSION)
}
```

`diff(a, b)` accepts two compute records or raw vectors. Verifies stored hash matches recomputed hash before comparing. Returns `{match, hash_a, hash_b, changed_dims, schema_match}`.

# Example

### Layer 1: scorer output (5-exchange fixture)

```
clarification overhead, session report
============================================
  [CLAR] ex-01        assistant:opener:'could you clarify'
  [----] ex-02        substantive
  [----] ex-03        substantive
  [CLAR] ex-04        user:opener:'what do you mean'
  [----] ex-05        substantive
--------------------------------------------
  total exchanges       : 5
  total clarifications  : 2
  ratio                 : 0.4
  rate per 10 exchanges : 4.0
  session score         : 0.6
```

### Layer 2: vector output (4-session improving series)

```
calibration vector, algorithm output
============================================
  [trend_slope      ] -0.159520
  [trend_direction  ] +1.000000
  [volatility_std   ] +0.178534
  [volatility_range ] +0.472200
  [weighted_recent  ] +0.725154
  [mean_score       ] +0.656750
  [latest_score     ] +0.888900
  [session_count_log] +1.609438
--------------------------------------------
  vector dim : 8
```

Negative slope plus positive direction equals ratio falling, calibration improving.

### Layer 4: hash drift detection

One exchange flipped from not-clarification to clarification in the most recent session. Six of eight dims changed. `trend_direction` and `session_count_log` correctly did not.

```
ORIGINAL  sha-256: 02ac79195f1011a298db9e64ad47bc721e7461aaa14f09bb916b5f7a1672a18e
MUTATED   sha-256: 695ff0dea6b663574a1974d6e268b237aca1936b60258ea05f580d9744ccb2f3

hashes match               : False
changed dims               : 6
  trend_slope          -0.2000000000 -> -0.1400000000  Δ=+0.0600000000
  volatility_std       +0.2236067977 -> +0.1658312395  Δ=-0.0577755582
  volatility_range     +0.6000000000 -> +0.4000000000  Δ=-0.2000000000
  weighted_recent      +0.7861034347 -> +0.7071456771  Δ=-0.0789577576
  mean_score           +0.7000000000 -> +0.6500000000  Δ=-0.0500000000
  latest_score         +1.0000000000 -> +0.8000000000  Δ=-0.2000000000
```

# Repo layout

```
src/
  clarification_overhead.py   Layer 1: binary scorer
  calibration_vector.py       Layer 2: 8-dim algorithm
  trust_embedding.py          Layer 3: L2 normalize + cosine
  trust_hash.py               Layer 4: SHA-256 fingerprint + diff
data/
  sample_exchanges.json       5-exchange fixture for the scorer
  multi_session.json          4-session fixture for the vector
  comparison_test.json        2-series fixture for embed + hash
scripts/
  build_pdf.py                Renders the PCSE paper as PDF (requires matplotlib, weasyprint)
```

# What is not built yet

Three scoring dimensions are defined but not implemented:

- Friction rate: misreads per exchange
- Recovery speed: exchanges to resolve a misread
- Vocabulary convergence: shared terms used without re-definition

The vector algorithm accepts any shape that supplies `ratio`, `session_score`, and `total_exchanges`, so adding scorers for these dimensions does not require changes above Layer 1.

The current scorer uses pattern-matching heuristics. A learned classifier replaces it without touching Layers 2-4.

Z-score normalization per dimension before L2 is not applied. Each dim contributes to cosine similarity by raw magnitude, not informational content.

No live conversation parser exists. PCSE reads JSON files. A production pipeline would ingest live exchanges, score on session close, and inject the hash at session start.

# Scope

PCSE does not chat, store memory, proxy an API, or manage sessions. It reads conversation history as JSON, scores it, and produces a portable artifact. No state between runs. No network calls. One JSON input in, four layer outputs out.

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap) — fingerprint scanner for exposed AI and ML infrastructure
- [nuclide-atlas](https://github.com/nuclide-research/nuclide-atlas) — see any LLM stack as a graph
- [agent-logging-system](https://github.com/nuclide-research/agent-logging-system) — operational monitor for multi-agent AI workflows
- [safety-stream](https://github.com/nuclide-research/safety-stream) — live SSE view of a model's layered safety reasoning
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings

# License

Dual-licensed under MIT ([LICENSE-MIT](LICENSE-MIT)) or Apache 2.0 ([LICENSE-APACHE](LICENSE-APACHE)) at your option. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

"""
calibration_vector.py — v0.1

Algorithm layer of the NuClide trust token.

Takes an ordered series of session scores (output of
score_session() from clarification_overhead.py) and produces a
fixed-length float vector that encodes the calibration state of the
Nick + Claude interaction over time.

Build sequence position
-----------------------
Feature space (done) → Scoring rubric (done) → Algorithm  ← here
→ Embedding → Hash

Properties
----------
- Fixed-length: the vector dimension does not depend on the number of
  input sessions. This makes it comparable via cosine similarity.
- Deterministic: pure functions over numeric inputs; no randomness, no
  iteration order surprises.
- Time-aware: trend, volatility, and recency-weighted aggregates each
  capture a different facet of how calibration is moving.

Input shape
-----------
A list of session-score dicts, ordered oldest-first to newest-last.
Each dict must contain at minimum:
    - ratio: float            clarifications per exchange (0.0 - 1.0)
    - session_score: float    1.0 - ratio
    - total_exchanges: int    sample size

Vector layout (8 dimensions)
----------------------------
Index | Name                 | Meaning
------|----------------------|------------------------------------------
  0   | trend_slope          | Least-squares slope of ratio over session
      |                      | index. Negative = overhead falling =
      |                      | calibration improving.
  1   | trend_direction      | Sign of trend_slope, snapped to a clean
      |                      | improvement signal. +1 improving, -1
      |                      | worsening, 0 flat. Useful as a coarse
      |                      | feature even when slope magnitude is noisy.
  2   | volatility_std       | Population standard deviation of ratio
      |                      | across sessions. Lower = more stable.
  3   | volatility_range     | max(ratio) - min(ratio). A blunt
      |                      | complement to std-dev that survives small
      |                      | sample sizes.
  4   | weighted_recent      | Exponentially-weighted session_score
      |                      | (alpha=0.7), most recent session weighted
      |                      | most. Captures "where we are now."
  5   | mean_score           | Arithmetic mean of session_score. Baseline
      |                      | reference for weighted_recent.
  6   | latest_score         | session_score of the newest session.
      |                      | Anchor point — what the last interaction
      |                      | actually felt like.
  7   | session_count_log    | log(1 + n_sessions). Encodes how much
      |                      | history the vector summarizes; useful for
      |                      | downweighting calibration claims based on
      |                      | thin data.

The dimension count is intentionally small. v0.1 prioritizes a vector
that is interpretable by hand. Embedding and hashing layers will widen
or compress this representation downstream.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

VECTOR_DIM = 8
VECTOR_NAMES = (
    "trend_slope",
    "trend_direction",
    "volatility_std",
    "volatility_range",
    "weighted_recent",
    "mean_score",
    "latest_score",
    "session_count_log",
)

# Decay constant for weighted_recent. Most recent session has weight 1,
# the one before has weight alpha, the one before that alpha^2, etc.
# 0.7 gives the latest session ~40% of total weight in a 4-session run,
# which matches Nick's stated preference for recency without erasing
# earlier history entirely.
_WEIGHTED_RECENT_ALPHA = 0.7

# Threshold for treating a slope as "flat." Below this in absolute
# value, trend_direction snaps to 0 instead of sign-of-slope. Avoids
# noise on near-zero slopes from small samples.
_FLAT_SLOPE_EPS = 1e-3


def _least_squares_slope(ys: list[float]) -> float:
    """Slope of a least-squares fit of ys against index 0..n-1.

    Returns 0.0 for n < 2. Pure stdlib; no numpy dependency.
    """
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _population_std(ys: list[float]) -> float:
    if not ys:
        return 0.0
    mean = sum(ys) / len(ys)
    var = sum((y - mean) ** 2 for y in ys) / len(ys)
    return math.sqrt(var)


def _weighted_recent(ys: list[float], alpha: float) -> float:
    """Exponentially-weighted average; most recent has weight 1."""
    if not ys:
        return 0.0
    n = len(ys)
    weights = [alpha ** (n - 1 - i) for i in range(n)]
    total_w = sum(weights)
    return sum(w * y for w, y in zip(weights, ys)) / total_w


def build_vector(sessions: Iterable[dict]) -> list[float]:
    """Compute the fixed-length calibration vector.

    sessions: ordered oldest-first to newest-last.
    Returns a list of length VECTOR_DIM.
    """
    sessions = list(sessions)

    if not sessions:
        return [0.0] * VECTOR_DIM

    ratios = [float(s["ratio"]) for s in sessions]
    scores = [float(s["session_score"]) for s in sessions]

    slope = _least_squares_slope(ratios)
    if abs(slope) < _FLAT_SLOPE_EPS:
        direction = 0.0
    else:
        # ratio falling (slope < 0) means overhead improving; encode
        # that as +1 so the feature reads "improvement direction."
        direction = -1.0 if slope > 0 else 1.0

    return [
        slope,
        direction,
        _population_std(ratios),
        max(ratios) - min(ratios),
        _weighted_recent(scores, _WEIGHTED_RECENT_ALPHA),
        sum(scores) / len(scores),
        scores[-1],
        math.log(1 + len(sessions)),
    ]


def vector_with_labels(sessions: Iterable[dict]) -> dict:
    """Return the vector plus a name->value map for human inspection."""
    vec = build_vector(sessions)
    return {
        "vector": vec,
        "labels": dict(zip(VECTOR_NAMES, vec)),
        "dim": VECTOR_DIM,
    }


def load_sessions(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "sessions" in data:
        return data["sessions"]
    return data


def _format_report(result: dict) -> str:
    lines = []
    lines.append("calibration vector — algorithm output")
    lines.append("=" * 44)
    width = max(len(n) for n in VECTOR_NAMES)
    for name, value in result["labels"].items():
        lines.append(f"  [{name:<{width}}] {value:+.6f}")
    lines.append("-" * 44)
    lines.append(f"  vector dim : {result['dim']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    default_path = (
        Path(__file__).resolve().parent.parent / "data" / "multi_session.json"
    )
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    sessions = load_sessions(path)
    result = vector_with_labels(sessions)
    print(_format_report(result))
    print()
    print(json.dumps(result, indent=2))

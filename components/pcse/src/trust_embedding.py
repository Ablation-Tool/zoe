"""
trust_embedding.py — v0.1

Embedding layer of the NuClide trust token.

Takes the raw vector produced by calibration_vector.build_vector(),
drops dimensions that encode metadata rather than calibration state,
and emits a unit-length embedding plus the L2 norm that produced it.
Two embeddings can be compared via cosine similarity to ask: how
similar are these two calibration states?

Build sequence position
-----------------------
Feature space (done) → Scoring rubric (done) → Algorithm (done)
→ Embedding  ← here  → Hash

Properties
----------
- L2 normalized: every embedding has unit length (||e|| = 1), which
  makes cosine similarity equal to the dot product and removes any
  magnitude bias when comparing across sessions.
- Deterministic: pure arithmetic over the input vector. No randomness.
- Portable: stdlib only. The embedding is a plain list of floats.

Comparison vs raw vector
------------------------
calibration_vector.build_vector() produces an 8-dim raw vector. Some
of those dimensions are metadata about the series rather than its
calibration state — most notably session_count_log, which encodes how
much history the vector summarizes. Including it in cosine comparison
lets equal series-lengths inflate similarity even when calibration
trends diverge. embed() therefore drops every name in
_EXCLUDED_FROM_COMPARISON before normalizing, while still surfacing
the full raw vector in the returned dict for reference and (later)
the hash payload.

_EXCLUDED_FROM_COMPARISON must stay in sync with
calibration_vector.VECTOR_NAMES.

Range note
----------
Cosine similarity over true unit vectors lives in [-1.0, 1.0]. Two
embeddings whose calibration states diverge in *signed* dimensions
(e.g. one improving, one degrading — opposite trend_direction) can
produce a negative similarity. compare() returns the raw cosine
without clamping; downstream consumers can map to [0, 1] via
(cos + 1) / 2 if a non-negative score is needed.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from calibration_vector import VECTOR_NAMES  # noqa: E402

# Dimensions that participate in the raw vector but are excluded from
# the L2-normalized comparison vector. These are metadata about the
# series, not signal about calibration state.
_EXCLUDED_FROM_COMPARISON = frozenset({"session_count_log"})

COMPARISON_NAMES = tuple(
    n for n in VECTOR_NAMES if n not in _EXCLUDED_FROM_COMPARISON
)


def _split_for_comparison(
    vector: list[float], names: tuple[str, ...]
) -> tuple[list[float], tuple[str, ...]]:
    """Drop excluded dims, returning (kept_values, kept_names)."""
    if len(vector) != len(names):
        raise ValueError(
            f"vector/names length mismatch: {len(vector)} vs {len(names)}"
        )
    pairs = [
        (n, v) for n, v in zip(names, vector)
        if n not in _EXCLUDED_FROM_COMPARISON
    ]
    return [v for _, v in pairs], tuple(n for n, _ in pairs)


def embed(
    vector: list[float],
    names: tuple[str, ...] | None = None,
) -> dict:
    """L2-normalize the comparison view of a raw calibration vector.

    If `names` is provided it labels every dim in `vector`; the
    function then drops any name listed in _EXCLUDED_FROM_COMPARISON
    before normalizing. If `names` is None and `vector` matches
    VECTOR_NAMES in length, VECTOR_NAMES is used. Otherwise the whole
    vector is normalized as-is (no dims are excluded).

    Returns:
        {
          "embedding":         list[float],  unit-length comparison vec
          "norm":              float,        L2 norm before normalization
          "dim":               int,          length of the embedding
          "comparison_names":  tuple[str],   names of the kept dims
          "raw_vector":        list[float],  unmodified input vector
          "raw_names":         tuple[str]?,  names of the input vector
        }

    A zero comparison vector embeds to zeros (norm 0.0). This is the
    only edge case; all other inputs produce a true unit vector.
    """
    raw_vector = list(vector)

    if names is None and len(raw_vector) == len(VECTOR_NAMES):
        names = VECTOR_NAMES

    if names is not None:
        comp_vec, comp_names = _split_for_comparison(raw_vector, names)
    else:
        comp_vec = list(raw_vector)
        comp_names = None

    if not comp_vec:
        return {
            "embedding": [],
            "norm": 0.0,
            "dim": 0,
            "comparison_names": comp_names,
            "raw_vector": raw_vector,
            "raw_names": tuple(names) if names is not None else None,
        }

    norm = math.sqrt(sum(x * x for x in comp_vec))
    if norm == 0.0:
        return {
            "embedding": [0.0] * len(comp_vec),
            "norm": 0.0,
            "dim": len(comp_vec),
            "comparison_names": comp_names,
            "raw_vector": raw_vector,
            "raw_names": tuple(names) if names is not None else None,
        }

    embedding = [x / norm for x in comp_vec]
    return {
        "embedding": embedding,
        "norm": norm,
        "dim": len(comp_vec),
        "comparison_names": comp_names,
        "raw_vector": raw_vector,
        "raw_names": tuple(names) if names is not None else None,
    }


def compare(a: dict | list[float], b: dict | list[float]) -> float:
    """Cosine similarity between two embeddings.

    Accepts either the dict produced by embed() or a raw list of
    floats. Both inputs must have the same length; if either input is
    not unit length, it is renormalized so the result is true cosine.
    Returns a float in [-1.0, 1.0].
    """
    av = a["embedding"] if isinstance(a, dict) else list(a)
    bv = b["embedding"] if isinstance(b, dict) else list(b)

    if len(av) != len(bv):
        raise ValueError(
            f"embedding length mismatch: {len(av)} vs {len(bv)}"
        )
    if not av:
        return 0.0

    dot = sum(x * y for x, y in zip(av, bv))
    na = math.sqrt(sum(x * x for x in av))
    nb = math.sqrt(sum(y * y for y in bv))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _format_embedding(label: str, emb: dict) -> str:
    lines = [f"{label}", "-" * len(label)]
    lines.append(f"  norm : {emb['norm']:.6f}")
    lines.append(f"  dim  : {emb['dim']}")
    lines.append("  embedding:")
    for i, v in enumerate(emb["embedding"]):
        lines.append(f"    [{i}] {v:+.6f}")
    return "\n".join(lines)


if __name__ == "__main__":
    # End-to-end pipeline runner: score → vector → embed → compare.
    # Running `python3 src/trust_embedding.py` puts src/ on sys.path[0]
    # so the sibling import below resolves cleanly.
    from clarification_overhead import score_session
    from calibration_vector import build_vector

    default_path = _HERE.parent / "data" / "comparison_test.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    series_a = payload["series_a"]
    series_b = payload["series_b"]

    def run_series(label: str, series: dict) -> dict:
        session_scores = [score_session(s["exchanges"]) for s in series["sessions"]]
        vec = build_vector(session_scores)
        emb = embed(vec)
        return {
            "label": label,
            "name": series.get("name", label),
            "session_scores": session_scores,
            "raw_vector": vec,
            "embedding": emb,
        }

    a = run_series("A", series_a)
    b = run_series("B", series_b)
    similarity = compare(a["embedding"], b["embedding"])

    print("trust embedding — end-to-end pipeline")
    print("=" * 44)
    print()
    for run in (a, b):
        emb = run["embedding"]
        print(f"series {run['label']} — {run['name']}")
        print(f"  per-session ratios     : {[round(s['ratio'], 4) for s in run['session_scores']]}")
        print(f"  per-session scores     : {[round(s['session_score'], 4) for s in run['session_scores']]}")
        print(f"  raw vector ({len(run['raw_vector'])} dims):")
        for name, val in zip(VECTOR_NAMES, run["raw_vector"]):
            mark = "  *excluded" if name in _EXCLUDED_FROM_COMPARISON else ""
            print(f"    {name:<20} {val:+.6f}{mark}")
        print(f"  L2 norm                : {emb['norm']:.6f}")
        print(f"  unit embedding ({emb['dim']} dims):")
        for name, val in zip(emb["comparison_names"], emb["embedding"]):
            print(f"    {name:<20} {val:+.6f}")
        print()

    print("-" * 44)
    print(f"comparison dim count       : {a['embedding']['dim']}")
    print(f"cosine similarity (A vs B) : {similarity:+.6f}")
    print(f"mapped to [0, 1]           : {(similarity + 1) / 2:.6f}")

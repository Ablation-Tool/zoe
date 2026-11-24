"""
trust_hash.py — v0.1

Hash layer of the NuClide trust token.

Takes the full raw 8-dim vector produced by
calibration_vector.build_vector() and emits a deterministic SHA-256
hex digest — the portable identity fingerprint of the calibration
state. Two trust tokens computed from byte-identical inputs on any
machine produce the same hash.

Build sequence position
-----------------------
Feature space (done) → Scoring rubric (done) → Algorithm (done)
→ Embedding (done) → Hash  ← here

Properties
----------
- Deterministic: canonical JSON serialization (sorted keys, fixed
  decimal precision per float) eliminates the platform-dependent
  variance in repr(float) and dict iteration order.
- Sensitive: any change to any dim of the raw vector — including
  metadata dims like session_count_log — produces a different hash.
- Verifiable: the canonical payload that produced the digest is
  retained in the record, so a downstream consumer can recompute the
  hash and confirm integrity.

Why include the full vector (not the comparison view)?
------------------------------------------------------
The hash is identity, not similarity. Two calibration states that
look alike under cosine comparison can still be distinct calibration
runs — different session counts, different absolute timing — and the
hash should distinguish them. session_count_log and any other
metadata dim therefore participate in the digest even though they are
excluded from cosine similarity in trust_embedding.

diff() honesty note
-------------------
A SHA-256 digest cannot, by design, reveal which input bytes changed.
To surface dim-level changes, diff() reads the retained vectors from
the hash records (or accepts two raw vectors directly) and computes
the field diff from those. This is the same pattern Git uses for
commit objects: the hash is the identity, the stored content is what
makes structured comparison possible.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from calibration_vector import VECTOR_NAMES  # noqa: E402

# Decimal places preserved in the canonical float-to-string conversion.
# Ten decimals is well within float64 precision for the value ranges
# this token uses (typically 0..2) while still being short enough to
# read by hand. Changing this value changes every hash; it is part of
# the on-the-wire format, hence the version bump rule below.
PRECISION = 10

# Bumped if the canonical-JSON format itself changes. Hashes from
# different versions are not comparable.
HASH_FORMAT_VERSION = 1


def _format_float(value: float) -> str:
    """Round-then-format a float to a stable string at PRECISION."""
    # Round first to suppress the trailing-digit noise that can
    # creep in from accumulated floating-point ops (e.g. a value
    # that should be 0.6 arriving as 0.6000000000000001).
    return format(round(float(value), PRECISION), f".{PRECISION}f")


def _canonical_payload(
    vector: list[float], names: tuple[str, ...]
) -> dict:
    if len(vector) != len(names):
        raise ValueError(
            f"vector/names length mismatch: {len(vector)} vs {len(names)}"
        )
    return {
        "version": HASH_FORMAT_VERSION,
        "precision": PRECISION,
        "dims": {n: _format_float(v) for n, v in zip(names, vector)},
    }


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute(
    vector: list[float],
    names: tuple[str, ...] = VECTOR_NAMES,
) -> dict:
    """Hash a raw calibration vector.

    Returns:
        {
          "hash":      str,    SHA-256 hex digest
          "canonical": str,    canonical JSON string that was hashed
          "vector":    list,   the input vector (echoed for diffing)
          "names":     tuple,  the dim names
          "precision": int,    decimal places preserved
          "version":   int,    canonical-format version
        }
    """
    payload = _canonical_payload(vector, names)
    canonical = _canonical_json(payload)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "hash": digest,
        "canonical": canonical,
        "vector": list(vector),
        "names": tuple(names),
        "precision": PRECISION,
        "version": HASH_FORMAT_VERSION,
    }


def _coerce_record(x) -> dict:
    """Accept a hash record dict or a raw vector list."""
    if isinstance(x, dict) and "hash" in x and "vector" in x:
        return x
    if isinstance(x, (list, tuple)):
        return compute(list(x))
    raise TypeError(
        "diff() inputs must be hash records from compute() or raw vectors"
    )


def diff(a, b) -> dict:
    """Compare two hashes and report which dims changed.

    Accepts either records returned by compute() or raw vectors.
    Returns:
        {
          "match":         bool,
          "hash_a":        str,
          "hash_b":        str,
          "changed_dims":  list of {name, from, to, delta},
          "schema_match":  bool,
        }

    If schemas differ (different dim names) the records still compare
    by hash but changed_dims is empty and schema_match is False. The
    canonical payload always re-derives from the stored vector, so a
    record whose hash does not match its vector raises.
    """
    rec_a = _coerce_record(a)
    rec_b = _coerce_record(b)

    # Integrity check: if a record was passed in, its stored hash must
    # match the hash recomputed from its stored vector.
    for label, rec in (("a", rec_a), ("b", rec_b)):
        recomputed = compute(rec["vector"], rec["names"])["hash"]
        if recomputed != rec["hash"]:
            raise ValueError(
                f"record {label} integrity failure: stored hash does "
                f"not match its vector"
            )

    match = rec_a["hash"] == rec_b["hash"]
    schema_match = rec_a["names"] == rec_b["names"]

    changed = []
    if schema_match:
        for name, va, vb in zip(rec_a["names"], rec_a["vector"], rec_b["vector"]):
            sa = _format_float(va)
            sb = _format_float(vb)
            if sa != sb:
                changed.append({
                    "name": name,
                    "from": float(va),
                    "to": float(vb),
                    "delta": float(vb) - float(va),
                })

    return {
        "match": match,
        "hash_a": rec_a["hash"],
        "hash_b": rec_b["hash"],
        "changed_dims": changed,
        "schema_match": schema_match,
    }


if __name__ == "__main__":
    # End-to-end pipeline runner: score → vector → embed → hash, then
    # mutate one session score and rehash to confirm sensitivity.
    from clarification_overhead import score_session
    from calibration_vector import build_vector
    from trust_embedding import embed

    default_path = _HERE.parent / "data" / "comparison_test.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    series = payload["series_a"]
    sessions = series["sessions"]

    # Original pipeline.
    scored = [score_session(s["exchanges"]) for s in sessions]
    vec_orig = build_vector(scored)
    emb_orig = embed(vec_orig)
    hash_orig = compute(vec_orig)

    # Mutated pipeline: flip one exchange in the final session from
    # not-clarification to clarification. Smallest possible change to
    # the upstream data; should still ripple all the way to the hash.
    mutated_sessions = []
    for s in sessions:
        ex_copy = [dict(e) for e in s["exchanges"]]
        mutated_sessions.append({"session_id": s["session_id"], "exchanges": ex_copy})
    mutated_sessions[-1]["exchanges"][0]["clarification"] = True

    scored_m = [score_session(s["exchanges"]) for s in mutated_sessions]
    vec_mut = build_vector(scored_m)
    emb_mut = embed(vec_mut)
    hash_mut = compute(vec_mut)

    delta = diff(hash_orig, hash_mut)

    def _print_block(title, vec, emb, h):
        print(title)
        print("-" * len(title))
        print(f"  raw vector:")
        for name, val in zip(VECTOR_NAMES, vec):
            print(f"    {name:<20} {val:+.10f}")
        print(f"  embedding L2 norm     : {emb['norm']:.6f}")
        print(f"  embedding dim         : {emb['dim']}")
        print(f"  canonical json        : {h['canonical']}")
        print(f"  sha-256               : {h['hash']}")
        print()

    print("trust hash — end-to-end pipeline (series A: improving)")
    print("=" * 56)
    print()
    _print_block("ORIGINAL", vec_orig, emb_orig, hash_orig)
    _print_block("MUTATED  (A.s4.e1.clarification flipped to true)", vec_mut, emb_mut, hash_mut)

    print("-" * 56)
    print(f"hashes match               : {delta['match']}")
    print(f"schema match               : {delta['schema_match']}")
    print(f"changed dims               : {len(delta['changed_dims'])}")
    for c in delta["changed_dims"]:
        print(f"  {c['name']:<20} {c['from']:+.10f} -> {c['to']:+.10f}  Δ={c['delta']:+.10f}")

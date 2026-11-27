"""Tetrapeptide n-gram Jaccard similarity for protein sequences."""

from __future__ import annotations


def ngrams(seq: str, n: int = 4) -> frozenset[str]:
    """Sliding window of n consecutive amino acids."""
    return frozenset(seq[i:i+n] for i in range(len(seq) - n + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def sequence_jaccard(seq_a: str, seq_b: str, n: int = 4) -> float:
    return jaccard(ngrams(seq_a, n), ngrams(seq_b, n))

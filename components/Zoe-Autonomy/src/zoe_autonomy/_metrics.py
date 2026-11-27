"""Shared AUROC evaluation helpers preserving exact caller tie semantics."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def _average_tie_ranks(sorted_scores: np.ndarray) -> np.ndarray:
    """Assign 1-based midpoint ranks across equal-valued runs in sorted scores."""
    n = len(sorted_scores)
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        # Advance j to the end of the current constant-score tie group.
        while j + 1 < n and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[i : j + 1] = 0.5 * (i + j) + 1.0
        i = j + 1
    return ranks


def auroc_tie_aware(
    labels: Sequence[int] | np.ndarray,
    scores: Sequence[float] | np.ndarray,
) -> float:
    """Compute Mann-Whitney AUROC with exact 0.5 credit on tied scores."""
    y = np.asarray(labels, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    if y.shape != s.shape:
        raise ValueError(f"labels and scores must have equal shape, got {y.shape} vs {s.shape}")
    if not np.all(np.isfinite(s)):
        raise ValueError("scores must contain only finite values")
    # Filter strictly to {0, 1} labels for exact parity with pairwise broadcast callers.
    mask = (y == 1) | (y == 0)
    y = y[mask]
    s = s[mask]
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(s, kind="mergesort")
    ranks = _average_tie_ranks(s[order])
    pos_rank_sum = float(np.sum(ranks[y[order] == 1]))
    return float((pos_rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def auroc_argsort(
    y_true: Sequence[int] | np.ndarray,
    scores: Sequence[float] | np.ndarray,
) -> float:
    """Compute AUROC using raw np.argsort sequential 1..N ranks without tie averaging."""
    y = np.asarray(y_true, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    if y.shape != s.shape:
        raise ValueError(f"y_true and scores must have equal shape, got {y.shape} vs {s.shape}")
    if not np.all(np.isfinite(s)):
        raise ValueError("scores must contain only finite values")
    # Preserve exact open_ended_program_evolution ranking order on ties.
    order = np.argsort(s)
    ys = y[order]
    n1 = int(np.sum(ys == 1))
    n0 = len(ys) - n1
    if n1 == 0 or n0 == 0:
        return 0.5
    ranks = np.arange(1, len(ys) + 1, dtype=np.float64)
    return float((float(np.sum(ranks[ys == 1])) - n1 * (n1 + 1) / 2.0) / (n1 * n0))


__all__ = ["auroc_argsort", "auroc_tie_aware"]

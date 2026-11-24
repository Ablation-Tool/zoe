"""Three-stage sequence homolog finder.

Works for proteins and nucleotide sequences (DNA or RNA). The pipeline is
identical in structure; only the k-gram size and confidence thresholds differ
by sequence type.

--- Pipeline ---

Stage 1  Length filter
  Discard candidates whose length differs from the seed by more than
  LENGTH_RATIO_MAX (default 40%). This is the cheapest filter -- a pure
  length comparison. It runs before any k-gram computation.

Stage 2  Jaccard rank
  Score every surviving candidate by k-gram Jaccard similarity against the
  seed. Return the top TOP_K candidates.

  Jaccard(A, B) = |A ∩ B| / |A ∪ B|

  where A and B are frozensets of k-grams extracted from each sequence.
  Range is [0, 1]: 1 = identical k-gram sets, 0 = no overlap.

  k-grams are sliding windows of k consecutive residues/bases. They capture
  local sequence conservation without requiring global alignment.

Stage 3  Semantic scoring (optional)
  A language model (ESM2 for proteins, DNABERT for nucleotides) encodes each
  sequence into a fixed-length vector. Cosine similarity between vectors
  measures functional/evolutionary relatedness beyond local sequence patterns.

  Stage 3 fires under two conditions:
    (a) Low Jaccard: best Stage 2 score < JACCARD_MIN. The seed and its top
        candidate have little k-gram overlap -- the sequence has diverged
        significantly (deep evolutionary split, frame shift, large insertion).
        In this case semantic scoring runs over ALL top-K candidates and the
        highest semantic match wins.
    (b) Tie: top-2 Jaccard scores differ by less than SEM_TIE_THRESH. Both
        candidates look equally similar by sequence; semantic breaks the tie.

--- Confidence gate ---

  HIGH   = jaccard >= JACCARD_MIN  AND  (sem >= 0.75  OR  jaccard >= JACCARD_HIGH)
  MEDIUM = sem >= 0.55  OR  jaccard >= JACCARD_MEDIUM
  LOW    = everything else

  HIGH requires BOTH structural (Jaccard) and semantic evidence. This is
  the critical design decision. Semantic models alone fire false positives on
  conserved functional motifs that appear across unrelated sequences:
    - Proteins: ATP-binding pockets, zinc fingers, WD40 repeats
    - Nucleotides: TATA boxes, polyadenylation signals, splice consensus sites
  These motifs score 0.90+ cosine similarity in ESM2/DNABERT embeddings even
  when the surrounding sequence is completely unrelated. Requiring Jaccard >=
  JACCARD_MIN as a structural corroboration gate blocks these false positives.

  MEDIUM is disjunctive -- either signal alone can earn it. It represents a
  plausible candidate worth investigating, not a confirmed homolog.

--- Threshold recalibration by sequence type ---

  Protein (k=4, alphabet=20, 20^4=160k possible 4-mers):
    JACCARD_MIN=0.10, JACCARD_MEDIUM=0.30, JACCARD_HIGH=0.60

  Nucleotide (k=6, alphabet=4, 4^6=4096 possible 6-mers):
    JACCARD_MIN=0.15, JACCARD_MEDIUM=0.25, JACCARD_HIGH=0.45

  Why thresholds differ: with only 4096 possible 6-mers, two random 1000-nt
  sequences share roughly 12% of their 6-mers by chance (background Jaccard
  ~0.12). JACCARD_MIN must sit above this noise floor. For proteins, the 160k
  tetrapeptide space gives a lower random background so JACCARD_MIN can be 0.10.

  These are calibrated starting points. Empirical validation against known
  orthologs and non-homologs in your target organism is recommended before
  treating HIGH calls as confirmed.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .features import SequenceFeatures, SeqType
from .jaccard  import jaccard


@dataclass
class _Thresholds:
    jaccard_min:    float  # FP gate for HIGH; must exceed random background
    jaccard_medium: float  # Jaccard alone sufficient for MEDIUM
    jaccard_high:   float  # Jaccard alone sufficient for HIGH
    sem_tie_thresh: float  # top-2 Jaccard gap that triggers semantic tiebreak
    top_k:          int    # candidates forwarded to semantic stage
    length_ratio:   float  # max fractional length difference for Stage 1


THRESHOLDS: dict[SeqType, _Thresholds] = {
    'protein': _Thresholds(
        jaccard_min=0.10, jaccard_medium=0.30, jaccard_high=0.60,
        sem_tie_thresh=0.02, top_k=10, length_ratio=0.40,
    ),
    'dna': _Thresholds(
        jaccard_min=0.15, jaccard_medium=0.25, jaccard_high=0.45,
        sem_tie_thresh=0.02, top_k=10, length_ratio=0.40,
    ),
    'rna': _Thresholds(
        jaccard_min=0.15, jaccard_medium=0.25, jaccard_high=0.45,
        sem_tie_thresh=0.02, top_k=10, length_ratio=0.40,
    ),
}


@dataclass
class HomologMatch:
    name:           str
    sequence:       str
    jaccard:        float
    semantic_score: float
    confidence:     str   # HIGH / MEDIUM / LOW


class HomologFinder:
    def __init__(self, encoder=None, seq_type: SeqType = 'protein'):
        """
        encoder  -- ESM2Encoder (protein) or NucleotideEncoder (dna/rna), or None
        seq_type -- controls which threshold set is used
        """
        self._enc = encoder
        self._t   = THRESHOLDS[seq_type]

    # ------------------------------------------------------------------ stages

    def _length_filter(
        self, seed: SequenceFeatures, candidates: list[SequenceFeatures]
    ) -> list[SequenceFeatures]:
        if seed.length == 0:
            return candidates
        out = []
        for c in candidates:
            if c.length == 0:
                out.append(c)
                continue
            ratio = abs(c.length - seed.length) / max(seed.length, 1)
            if ratio <= self._t.length_ratio:
                out.append(c)
        return out

    def _jaccard_rank(
        self, seed: SequenceFeatures, candidates: list[SequenceFeatures]
    ) -> list[tuple[float, SequenceFeatures]]:
        scored = [(jaccard(seed.kgrams, c.kgrams), c) for c in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:self._t.top_k]

    def _semantic_score(
        self, seed: SequenceFeatures, candidate: SequenceFeatures
    ) -> float:
        if self._enc is None:
            return 0.0
        vecs = self._enc.encode([seed.sequence, candidate.sequence])
        return float(vecs[0] @ vecs[1])

    # ------------------------------------------------------------------ main

    def find_homolog(
        self, seed: SequenceFeatures, candidates: list[SequenceFeatures]
    ) -> Optional[HomologMatch]:
        if not candidates:
            return None

        t = self._t

        # Stage 1
        filtered = self._length_filter(seed, candidates)
        if not filtered:
            filtered = candidates

        # Stage 2
        ranked = self._jaccard_rank(seed, filtered)
        if not ranked:
            return None

        best_score, best_func = ranked[0]

        # Stage 3
        sem_score   = 0.0
        low_jaccard = best_score < t.jaccard_min

        if self._enc is not None and (
            low_jaccard or
            (len(ranked) >= 2 and ranked[0][0] - ranked[1][0] < t.sem_tie_thresh)
        ):
            if low_jaccard:
                scored_sem = [
                    (self._semantic_score(seed, f), jac, f)
                    for jac, f in ranked
                ]
                scored_sem.sort(key=lambda x: x[0], reverse=True)
                sem_score, best_score, best_func = scored_sem[0]
            else:
                sem_a = self._semantic_score(seed, ranked[0][1])
                sem_b = self._semantic_score(seed, ranked[1][1])
                if sem_b > sem_a:
                    best_score, best_func = ranked[1]
                    sem_score = sem_b
                else:
                    sem_score = sem_a

        jaccard_ok = best_score >= t.jaccard_min
        confidence = (
            'HIGH'   if jaccard_ok and (sem_score >= 0.75 or best_score >= t.jaccard_high) else
            'MEDIUM' if sem_score >= 0.55 or best_score >= t.jaccard_medium else
            'LOW'
        )

        return HomologMatch(
            name=best_func.name,
            sequence=best_func.sequence,
            jaccard=best_score,
            semantic_score=sem_score,
            confidence=confidence,
        )

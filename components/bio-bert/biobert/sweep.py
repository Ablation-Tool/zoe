"""SemanticSweep: query a sequence database with a natural language description.

Analogous to ablation's vulnerability sweep (semantic_search.SemanticSearcher),
which encodes every function in a binary and queries with a text description of
what dangerous code looks like. Here we encode every sequence in a FASTA
database and query with a biological description.

Example queries:
  "Wnt signaling pathway receptor with cysteine-rich domain"
  "zinc finger transcription factor binding site"
  "splice donor site with GU dinucleotide"
  "neural stem cell specification gene"
  "TATA box proximal promoter element"

This is useful for non-model organisms (Nematostella, Hydractinia) where
annotation is sparse and BLAST databases are shallow. Rather than relying on
sequence identity to a known homolog, you describe what you are looking for
in plain English and retrieve the closest matches by semantic similarity.

Workflow
--------
1. Build corpus: encode every sequence in your database once.
2. Query: encode the description, compute cosine similarity against all corpus
   vectors, return top-K hits ranked by similarity.
3. Refine: filter hits by Jaccard against a known seed (HomologFinder).

The semantic sweep is a coarse first pass. A hit means "this sequence's
embedding is close to your description". It does NOT mean the sequence is
functionally identical -- verify top candidates with HomologFinder or
experimental follow-up.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np

from .features import SequenceFeatures


@dataclass
class SweepHit:
    rank:           int
    name:           str
    sequence:       str
    semantic_score: float


class SemanticSweep:
    def __init__(self, encoder):
        """encoder -- ESM2Encoder or NucleotideEncoder; required."""
        self._enc    = encoder
        self._corpus: Optional[list[SequenceFeatures]] = None
        self._vecs:   Optional[np.ndarray]             = None

    def build_corpus(self, sequences: list[SequenceFeatures]) -> None:
        """Encode all sequences. Call once; corpus is cached for repeated queries."""
        seqs = [s.sequence for s in sequences]
        print(f"Encoding {len(seqs)} sequences...")
        self._vecs   = self._enc.encode(seqs)
        self._corpus = sequences
        print(f"Done. Corpus shape: {self._vecs.shape}")

    def query(
        self,
        description: str,
        top_k: int = 20,
        sequences: Optional[list[SequenceFeatures]] = None,
    ) -> list[SweepHit]:
        """
        Query the corpus with a text description.

        Parameters
        ----------
        description : natural language description of what you are looking for
        top_k       : number of top hits to return
        sequences   : if provided and corpus not yet built, builds corpus first

        Returns
        -------
        list of SweepHit sorted by semantic_score descending
        """
        if self._corpus is None:
            if sequences is None:
                raise RuntimeError("Call build_corpus() first, or pass sequences=")
            self.build_corpus(sequences)

        query_vec = self._enc.encode([description])[0]  # (D,)
        scores    = self._vecs @ query_vec              # (N,) cosine similarity

        top_idx   = np.argsort(scores)[::-1][:top_k]
        return [
            SweepHit(
                rank=i + 1,
                name=self._corpus[idx].name,
                sequence=self._corpus[idx].sequence,
                semantic_score=float(scores[idx]),
            )
            for i, idx in enumerate(top_idx)
        ]

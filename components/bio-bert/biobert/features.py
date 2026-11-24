"""SequenceFeatures: k-gram extraction and FASTA parsing for proteins and nucleotides.

Supports three sequence types:
  protein    -- 20-AA alphabet; default k=4 (160k possible tetrapeptides)
  dna        -- 4-base alphabet (A/T/C/G); default k=6 (4096 possible hexamers)
  rna        -- 4-base alphabet (A/U/C/G); T is normalized to U on load; default k=6

Why k differs by type
---------------------
k-gram discrimination depends on how many distinct k-grams are possible relative
to sequence length. With a 4-letter alphabet (DNA/RNA), 4-mers give only 256
possible values -- too few to discriminate sequences; random sequences share too
many by chance. 6-mers give 4096, which is practical for typical gene-length
sequences (~1000 nt). Proteins have a 20-letter alphabet: 4-mers already give
160,000 possible values, which is sufficient.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

from .jaccard import ngrams

SeqType = Literal['protein', 'dna', 'rna']

DEFAULT_K: dict[SeqType, int] = {
    'protein': 4,
    'dna':     6,
    'rna':     6,
}


def _normalize(seq: str, seq_type: SeqType) -> str:
    s = seq.upper().strip()
    if seq_type == 'rna':
        s = s.replace('T', 'U')
    elif seq_type == 'dna':
        s = s.replace('U', 'T')
    return s


@dataclass
class SequenceFeatures:
    name:     str
    sequence: str
    length:   int
    kgrams:   frozenset[str]
    seq_type: SeqType
    k:        int

    @classmethod
    def from_sequence(
        cls,
        name: str,
        sequence: str,
        seq_type: SeqType = 'protein',
        k: Optional[int] = None,
    ) -> 'SequenceFeatures':
        if k is None:
            k = DEFAULT_K[seq_type]
        seq = _normalize(sequence, seq_type)
        return cls(
            name=name,
            sequence=seq,
            length=len(seq),
            kgrams=ngrams(seq, k),
            seq_type=seq_type,
            k=k,
        )


def parse_fasta(
    path: str,
    seq_type: SeqType = 'protein',
    k: Optional[int] = None,
) -> list[SequenceFeatures]:
    """Parse a FASTA file. seq_type controls normalization and default k."""
    results: list[SequenceFeatures] = []
    name: Optional[str] = None
    chunks: list[str] = []

    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('>'):
                if name is not None and chunks:
                    results.append(
                        SequenceFeatures.from_sequence(name, ''.join(chunks), seq_type, k)
                    )
                name = line[1:].split()[0]
                chunks = []
            else:
                chunks.append(line)

    if name is not None and chunks:
        results.append(
            SequenceFeatures.from_sequence(name, ''.join(chunks), seq_type, k)
        )

    return results

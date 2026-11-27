from .features import SequenceFeatures, parse_fasta, SeqType
from .jaccard  import jaccard, ngrams, sequence_jaccard
from .semantic import ESM2Encoder, NucleotideEncoder
from .homolog  import HomologFinder, HomologMatch
from .sweep    import SemanticSweep, SweepHit

__version__ = "0.2.0"
__all__ = [
    "SequenceFeatures", "parse_fasta", "SeqType",
    "jaccard", "ngrams", "sequence_jaccard",
    "ESM2Encoder", "NucleotideEncoder",
    "HomologFinder", "HomologMatch",
    "SemanticSweep", "SweepHit",
]

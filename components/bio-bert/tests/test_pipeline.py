"""Pipeline integration tests -- Jaccard-only mode, no model download required."""

import random
import pytest
from biobert.features import SequenceFeatures
from biobert.homolog  import HomologFinder

random.seed(42)
AA  = "ACDEFGHIKLMNPQRSTVWY"
DNA = "ATCG"


def make_protein(name: str, seq: str) -> SequenceFeatures:
    return SequenceFeatures.from_sequence(name, seq, seq_type='protein')


def make_dna(name: str, seq: str) -> SequenceFeatures:
    return SequenceFeatures.from_sequence(name, seq, seq_type='dna')


def mutate(seq: str, alphabet: str, rate: float = 0.15) -> str:
    chars = list(seq)
    for i in range(len(chars)):
        if random.random() < rate:
            chars[i] = random.choice(alphabet)
    return ''.join(chars)


# ----------------------------------------------------------------- protein tests

KINASE_SEED = (
    "MGSSKSKPKDPSQRRARSLTETESVGTQTIRRESERLQRELENELKQLQEDYNQLREELKAK"
    "QQELEELQKKLSSMEKELEGLNQKLQQLEDKLSQMEDDLQAQLQDLQSQLQDERDSLRAEL"
    "QARLAQLESEKQATIAELEQKLISEEDLAARRNTRVKQLEKELQETKQELSQELQARQNEVE"
    "SLQAELANLKKELEQHRQALQKELKAQQTELERERDRDQERLDALEAELREAQKEREQERDR"
)
KINASE_HOMOLOG = mutate(KINASE_SEED, AA, rate=0.15)
ATP_SYNTHASE   = (
    "MQLNSTEISELIKQRIAQFNAQVKGQYHPLQAFLDQMEEAQERKVDELQQLREQIERLQKL"
    "REKERQLKAQLEQLKKEQEQLRAAQENLREAIQRLDRENQRLKESLEALKKEQERLKAELEK"
    "LRAEQQQLKDEIELAKQQREELQQKIQELENQLQKERNELAAQLQELQKEREQLREAQKELE"
    "QLQSELDKLREQLEAERQELQAERDQLQKEQEQLRAELEQLKKEQERLRAELESKLKEQERL"
)


def test_protein_finds_close_homolog():
    seed       = make_protein("kinase_seed", KINASE_SEED)
    candidates = [
        make_protein("kinase_homolog", KINASE_HOMOLOG),
        make_protein("atp_synthase", ATP_SYNTHASE),
    ]
    match = HomologFinder(seq_type='protein').find_homolog(seed, candidates)
    assert match is not None
    assert match.name == "kinase_homolog"
    assert match.confidence in ("HIGH", "MEDIUM")


def test_protein_identical_scores_high():
    seed  = make_protein("p1", KINASE_SEED)
    cands = [make_protein("p2", KINASE_SEED)]
    match = HomologFinder(seq_type='protein').find_homolog(seed, cands)
    assert match is not None
    assert match.jaccard == pytest.approx(1.0)
    assert match.confidence == "HIGH"


def test_protein_unrelated_scores_low():
    seed  = make_protein("kinase", KINASE_SEED)
    cands = [make_protein("poly_ala", "AAAA" * 60)]
    match = HomologFinder(seq_type='protein').find_homolog(seed, cands)
    assert match is not None
    assert match.confidence == "LOW"


def test_protein_empty_candidates():
    seed = make_protein("kinase", KINASE_SEED)
    assert HomologFinder(seq_type='protein').find_homolog(seed, []) is None


def test_length_filter():
    short = make_protein("short", KINASE_SEED[:60])
    cands = [
        make_protein("kinase_homolog", KINASE_HOMOLOG),  # ~256 aa -> filtered
        make_protein("atp_slice", ATP_SYNTHASE[:80]),    # ~80 aa -> passes
    ]
    match = HomologFinder(seq_type='protein').find_homolog(short, cands)
    assert match is not None
    assert match.name == "atp_slice"


# ----------------------------------------------------------------- nucleotide tests

GENE_SEED    = ''.join(random.choices(DNA, k=600))
GENE_HOMOLOG = mutate(GENE_SEED, DNA, rate=0.10)   # 10% divergence
UNRELATED    = ''.join(random.choices(DNA, k=600))


def test_dna_finds_close_homolog():
    seed  = make_dna("gene_seed", GENE_SEED)
    cands = [
        make_dna("gene_homolog", GENE_HOMOLOG),
        make_dna("unrelated",   UNRELATED),
    ]
    match = HomologFinder(seq_type='dna').find_homolog(seed, cands)
    assert match is not None
    assert match.name == "gene_homolog"


def test_dna_identical_scores_high():
    seed  = make_dna("g1", GENE_SEED)
    cands = [make_dna("g2", GENE_SEED)]
    match = HomologFinder(seq_type='dna').find_homolog(seed, cands)
    assert match is not None
    assert match.jaccard == pytest.approx(1.0)
    assert match.confidence == "HIGH"


def test_rna_sequence_normalizes():
    # RNA sequence with U -- should parse and produce kgrams with U
    rna_seq = GENE_SEED.replace('T', 'U')
    feat    = SequenceFeatures.from_sequence("rna_test", rna_seq, seq_type='rna')
    assert 'T' not in feat.sequence
    assert feat.k == 6

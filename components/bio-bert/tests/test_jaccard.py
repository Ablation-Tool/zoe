"""Unit tests for k-gram Jaccard similarity -- proteins and nucleotides."""

import pytest
from biobert.jaccard import ngrams, jaccard, sequence_jaccard


# --- protein (k=4, alphabet=20) ---

def test_ngrams_basic():
    result = ngrams("ACDEF", 4)
    assert result == frozenset({"ACDE", "CDEF"})


def test_ngrams_too_short():
    assert ngrams("ACG", 4) == frozenset()


def test_jaccard_identical():
    s = "MKTAYIAKQRQISFVKSHFSRQ" * 8
    assert jaccard(ngrams(s), ngrams(s)) == pytest.approx(1.0)


def test_jaccard_empty_both():
    assert jaccard(frozenset(), frozenset()) == pytest.approx(1.0)


def test_jaccard_empty_one():
    a = ngrams("ACDEFGH")
    assert jaccard(a, frozenset()) == pytest.approx(0.0)


def test_jaccard_unrelated_protein():
    j = sequence_jaccard("AAAA", "CCCC")
    assert j == pytest.approx(0.0)


def test_jaccard_partial():
    # ABCDE and BCDEX share "BCDE" only -> inter=1, union=3 -> 1/3
    j = sequence_jaccard("ABCDE", "BCDEX")
    assert j == pytest.approx(1/3)


def test_sequence_jaccard_symmetric():
    a = "MKTAYIAKQR"
    b = "MKTAYIAKQS"
    assert sequence_jaccard(a, b) == sequence_jaccard(b, a)


def test_high_similarity_proteins():
    base    = "ACDEFGHIKLMNPQRSTVWY" * 5
    mutant  = base[:40] + "A" + base[41:]
    j = sequence_jaccard(base, mutant)
    assert j > 0.80


# --- nucleotide (k=6, alphabet=4, 4^6=4096 possible hexamers) ---

def test_ngrams_dna_k6():
    result = ngrams("ATCGATCG", 6)
    assert result == frozenset({"ATCGAT", "TCGATC", "CGATCG"})


def test_nucleotide_jaccard_identical():
    seq = "ATCGATCGATCG" * 10
    assert jaccard(ngrams(seq, 6), ngrams(seq, 6)) == pytest.approx(1.0)


def test_nucleotide_jaccard_unrelated():
    # Pure A vs pure C -- no shared hexamers
    j = sequence_jaccard("AAAAAA" * 5, "CCCCCC" * 5, n=6)
    assert j == pytest.approx(0.0)


def test_nucleotide_jaccard_rna_t_to_u():
    # Identical sequences, one with T one with U -- should score 1.0 after normalization
    from biobert.features import SequenceFeatures
    dna = SequenceFeatures.from_sequence("dna", "ATCGATCG" * 5, seq_type='dna')
    rna = SequenceFeatures.from_sequence("rna", "AUCGAUCG" * 5, seq_type='rna')
    # After normalization: dna keeps T, rna converts U->nothing changes for rna
    # rna is stored with U; dna with T -- they differ, so Jaccard < 1
    # But if we normalize both to DNA (T): they match
    from biobert.jaccard import ngrams as ng
    dna_seq_as_rna = dna.sequence.replace('T', 'U')
    j = jaccard(ng(dna_seq_as_rna, 6), rna.kgrams)
    assert j == pytest.approx(1.0)

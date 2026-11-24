# bio-bert

**Find sequence homologs using k-gram structure and language model semantics.**

Designed for cross-species work in non-model organisms where BLAST databases are shallow and annotation is sparse. Works on protein sequences, DNA, and RNA.

---

## The problem this solves

You have a gene or protein in *Nematostella vectensis* or *Hydractinia*. You want to know: does an equivalent sequence exist in another species? What is it?

The standard tool is BLAST, which works by local alignment. BLAST is excellent when sequences are similar enough (>30% identity for proteins, higher for nucleotides). Below that threshold -- the "twilight zone" -- alignment-based methods break down. Non-model organisms, ancestrally diverged genes, and rapidly evolving regulatory regions all fall into this zone.

Language models offer an alternative: encode what a sequence *does* rather than what it *says*. Two sequences that fold into the same structure, bind the same partners, or perform the same regulatory function will have similar embeddings even if their primary sequences have diverged past the point where BLAST can detect the relationship.

The problem with language models alone: they produce false positives on conserved functional motifs. An ATP-binding pocket looks semantically similar to every other ATP-binding pocket. A TATA box looks similar to every other TATA box. These are real biological similarities -- but they do not make the surrounding sequences homologs.

**bio-bert uses both signals together.** k-gram Jaccard measures local sequence conservation. Language model embeddings measure global functional similarity. A genuine homolog shows both. A coincidental motif match shows only the second.

---

## How k-gram Jaccard works

A k-gram is a sliding window of k consecutive residues or bases.

For a protein sequence `MKTAYIAKQR` with k=4:
```
k-grams: {MKTA, KTAY, TAYI, AYIA, YIAK, IAKQ, AKQR}
```

For a DNA sequence `ATCGATCG` with k=6:
```
6-grams: {ATCGAT, TCGATC, CGATCG}
```

Jaccard similarity between two sequences A and B:

```
Jaccard(A, B) = |k-grams(A) ∩ k-grams(B)|
                ─────────────────────────────
                |k-grams(A) ∪ k-grams(B)|
```

This is the fraction of k-gram types shared by both sequences out of all k-gram types present in either. Range is 0 (no shared k-grams) to 1 (identical k-gram sets).

**Why k-grams instead of full alignment:** alignment finds the best possible match and scores it. k-gram Jaccard asks a simpler question -- how much of the local sequence vocabulary is shared? It is O(n) instead of O(n²), and it degrades gracefully as sequences diverge: each mutation affects at most k nearby k-grams, so Jaccard decreases smoothly rather than producing alignment artifacts.

**Why k varies by alphabet:**

The discriminating power of a k-gram depends on how many distinct k-grams are possible. With a large alphabet (proteins: 20 amino acids), small k is sufficient. With a small alphabet (nucleotides: 4 bases), you need larger k to get enough possible values.

| Sequence type | Alphabet | k | Possible k-grams |
|---|---|---|---|
| Protein | 20 AA | 4 | 20^4 = 160,000 |
| DNA/RNA | 4 bases | 6 | 4^6 = 4,096 |

If you used k=4 for nucleotides, you would have only 256 possible 4-mers. A typical 1000 bp sequence would exhaust most of that space, and two completely unrelated sequences would share 4-mers at high rates purely by chance. k=6 gives a large enough space that shared hexamers are meaningful evidence.

---

## How language model embeddings work

A language model trained on biological sequences learns to encode each sequence as a point in a high-dimensional vector space. Sequences with similar function, structure, or evolutionary history end up close together in that space.

bio-bert uses two models:

**ESM2** (proteins) -- trained on 250 million UniRef50 protein sequences. Encodes each protein into a 480-dimensional vector. The model learns amino acid co-evolution patterns across the entire known protein universe.

**DNABERT-2** (DNA/RNA) -- trained on multi-species genomic sequences. Encodes nucleotide sequences using byte-pair encoding tokens rather than fixed k-mers, which makes it more robust to sequence composition shifts.

Both are used the same way: encode the sequence, mean-pool over the sequence dimension to produce one fixed-length vector per sequence, L2-normalize so that dot product equals cosine similarity.

Cosine similarity between two vectors:

```
sim(A, B) = A · B / (|A| × |B|)
```

After L2 normalization this simplifies to `A · B`. Range is -1 to 1; in practice protein/nucleotide embeddings stay in [0, 1] for related sequences.

The embeddings run without internet connection once downloaded. Models download automatically from HuggingFace Hub on first use (~32 MB for ESM2 8M, ~450 MB for DNABERT-2).

---

## The false positive problem

Language model embeddings are powerful but they produce false positives on conserved functional motifs. This is not a bug -- it is the correct behavior. TATA boxes *are* functionally similar across all species. Zinc finger domains *do* look alike. The problem is that this similarity does not make the surrounding sequences homologs.

Concretely: an ESM2 embedding for a transcription factor from *Nematostella* might score 0.92 cosine similarity against a human kinase that happens to share a DNA-binding domain. These are not homologs. But the embedding says they look alike.

The same problem exists in k-gram Jaccard: two sequences sharing only a TATA box will have Jaccard near 0 for the full sequence, because the box is short and the rest of the sequence contributes most of the k-gram vocabulary.

**The fix: require both signals for high confidence.**

```
HIGH   = jaccard >= JACCARD_MIN  AND  (semantic >= 0.75  OR  jaccard >= JACCARD_HIGH)
MEDIUM = semantic >= 0.55  OR  jaccard >= JACCARD_MEDIUM
LOW    = everything else
```

HIGH is conjunctive: both structural (Jaccard) and semantic evidence required.
MEDIUM is disjunctive: either signal alone is enough to flag as a candidate.

A sequence that scores HIGH semantically but LOW on Jaccard is likely a motif match, not a homolog. It will score MEDIUM at best, which correctly signals "worth checking" rather than "confirmed".

---

## The three-stage pipeline

```
Input: one seed sequence + list of candidate sequences

Stage 1  Length filter
  Discard candidates whose length differs from the seed by more than 40%.
  Insertions, truncations, and isoforms within that window pass through.

Stage 2  Jaccard rank
  Score every surviving candidate by k-gram Jaccard against the seed.
  Keep the top 10 candidates.

Stage 3  Semantic scoring  (optional -- requires model download)
  Fires under two conditions:
    (a) Best Jaccard < JACCARD_MIN: the sequence has diverged significantly.
        Run the language model over all top-10 candidates; pick the highest
        semantic match. (Jaccard alone cannot distinguish here; semantic
        becomes the primary signal.)
    (b) Top-2 Jaccard within 0.02 of each other: too close to call by
        sequence alone. Semantic breaks the tie.

Confidence gate
  Apply the conjunctive HIGH gate (above).
  Return HomologMatch with name, sequence, jaccard, semantic_score, confidence.
```

---

## DNA to RNA

The pipeline handles RNA sequences directly. RNA uses U (uracil) where DNA uses T (thymine). bio-bert normalizes sequences on load:

- `seq_type='rna'` replaces any T with U
- `seq_type='dna'` replaces any U with T
- k-grams are computed on the normalized sequence

For transcription research (DNA -> pre-mRNA -> mRNA): you can run the pipeline on either the genomic DNA sequence or the RNA transcript. For comparing regulatory elements (promoters, enhancers, UTRs) across species, use `seq_type='dna'` on the genomic sequence. For comparing mature transcripts, use `seq_type='rna'`.

When using DNABERT-2 for RNA sequences, the encoder internally converts U back to T before tokenization (DNABERT-2 was trained on DNA). The embedding quality for RNA is similar to DNA because the structural differences between T and U are not captured at the sequence level anyway.

---

## Semantic sweep

For exploratory work in sparsely annotated genomes, you may not have a known seed sequence. Instead you have a biological description: "I want to find all putative Wnt pathway ligands in this transcriptome."

The semantic sweep encodes an entire database once, then lets you query it with text:

```python
from biobert import SemanticSweep, parse_fasta, ESM2Encoder

db    = parse_fasta("nematostella_proteome.fasta", seq_type='protein')
sweep = SemanticSweep(encoder=ESM2Encoder())
hits  = sweep.query("Wnt signaling ligand with cysteine knot domain", top_k=20)

for hit in hits:
    print(f"{hit.rank:2d}  {hit.name:40s}  score={hit.semantic_score:.3f}")
```

Example queries that work well in practice:
- `"TATA box proximal promoter with transcription factor binding sites"`
- `"neural stem cell specification transcription factor"`
- `"splice donor site GU dinucleotide"`
- `"zinc finger C2H2 DNA binding domain"`
- `"polyadenylation signal AATAAA"`

The sweep is a coarse first pass. Hits mean "this sequence's embedding is close to your description" -- not that the sequence is confirmed to have that function. Verify top candidates with HomologFinder (against a known seed) or wet-lab follow-up.

---

## Threshold reference

### Protein (k=4, 20^4=160,000 possible 4-mers)

| Threshold | Value | Meaning |
|---|---|---|
| JACCARD_MIN | 0.10 | Minimum Jaccard for HIGH; above random background for proteins |
| JACCARD_MEDIUM | 0.30 | Jaccard alone sufficient for MEDIUM (15% mutant scores ~0.37) |
| JACCARD_HIGH | 0.60 | Jaccard alone sufficient for HIGH |

### Nucleotide (k=6, 4^6=4,096 possible 6-mers)

| Threshold | Value | Meaning |
|---|---|---|
| JACCARD_MIN | 0.15 | Above random background (~0.12 for two random 1000 bp sequences) |
| JACCARD_MEDIUM | 0.25 | Jaccard alone sufficient for MEDIUM |
| JACCARD_HIGH | 0.45 | Jaccard alone sufficient for HIGH |

**On calibration:** These thresholds are starting points derived from the original binary reverse engineering application (see Origin section). They have not been benchmarked against a curated protein or nucleotide homolog dataset. Before treating HIGH calls as confirmed homologs, validate against a set of known ortholog pairs from your target organisms. Adjust JACCARD_MIN upward if you see false positives on short conserved motifs.

---

## Install

```sh
git clone <repo>
cd bio-bert
pip install -e .                      # Jaccard-only; no model download
pip install -e ".[semantic]"          # adds torch + transformers for ESM2/DNABERT-2
```

Python 3.10+ required.

---

## Quick start

### Protein homolog search

```python
from biobert import SequenceFeatures, HomologFinder

seed = SequenceFeatures.from_sequence("Nv_Wnt3", "MKTAYIAKQR...", seq_type='protein')
db   = [
    SequenceFeatures.from_sequence("Hs_Wnt3", "MKTAYIAKQS...", seq_type='protein'),
    SequenceFeatures.from_sequence("Hs_ATP_synthase", "MQLNSTEI...", seq_type='protein'),
]

finder = HomologFinder(seq_type='protein')   # Jaccard-only
match  = finder.find_homolog(seed, db)
print(match.confidence, match.jaccard)       # HIGH  0.84
```

### With semantic scoring

```python
from biobert import HomologFinder, ESM2Encoder

finder = HomologFinder(encoder=ESM2Encoder(), seq_type='protein')
match  = finder.find_homolog(seed, db)
print(match.confidence, match.jaccard, match.semantic_score)
```

### DNA regulatory element comparison

```python
from biobert import SequenceFeatures, HomologFinder

promoter_nv = SequenceFeatures.from_sequence("Nv_FoxA_promoter", "ATCGATCG...", seq_type='dna')
candidates  = [
    SequenceFeatures.from_sequence("Hs_FoxA2_promoter", "ATCGTTCG...", seq_type='dna'),
    SequenceFeatures.from_sequence("Dm_FoxA_promoter",  "CCGATCTT...", seq_type='dna'),
]

finder = HomologFinder(seq_type='dna')
match  = finder.find_homolog(promoter_nv, candidates)
print(match.name, match.confidence, match.jaccard)
```

### From FASTA files

```python
from biobert import parse_fasta, HomologFinder

seeds = parse_fasta("query.fasta",    seq_type='protein')
db    = parse_fasta("database.fasta", seq_type='protein')

finder = HomologFinder(seq_type='protein')
for seed in seeds:
    match = finder.find_homolog(seed, db)
    if match:
        print(f"{seed.name} -> {match.name}  [{match.confidence}]  jac={match.jaccard:.3f}")
```

### CLI

```sh
# Jaccard-only (fast, no model download)
biobert query seed.fasta database.fasta --type protein

# With semantic scoring
biobert query seed.fasta database.fasta --type dna --semantic
```

---

## Tests

```sh
python3 -m pytest tests/ -v
```

21 tests covering Jaccard math, pipeline stages, and nucleotide normalization. All tests run without a model download (semantic tests require `--semantic` flag on the CLI).

---

## Origin

This pipeline is ported from the cross-version binary homolog tracker in the ablation reverse engineering tool (`ablation/analyzers/version_delta.py`). In binary RE, the same three-stage structure -- structural filter, n-gram Jaccard rank, BERT semantic tiebreak -- is used to track a stripped firmware function across binary versions even when its address, name, and instruction sequence have changed.

The core insight transfers identically: k-gram Jaccard and semantic embeddings capture different and complementary aspects of similarity. k-grams see local sequence patterns; embeddings see global functional intent. A true homolog (or cross-version function) preserves both. A coincidental functional similarity preserves only the second. Requiring both for high confidence suppresses the false positive class that embeddings alone cannot resolve.

The threshold values differ because the sequence alphabets differ. Binary RE works with x86 mnemonics (~80 common tokens); bio-bert works with amino acids (20) or nucleotides (4). The same Jaccard score carries different information in each space, so the thresholds are recalibrated accordingly.

| Binary RE | bio-bert protein | bio-bert nucleotide |
|---|---|---|
| ~80 mnemonic tokens | 20 amino acids | 4 bases |
| k=4 mnemonics | k=4 tetrapeptides | k=6 hexamers |
| JACCARD_MIN=0.15 | JACCARD_MIN=0.10 | JACCARD_MIN=0.15 |
| BERT (all-MiniLM) | ESM2 | DNABERT-2 |
| cross-version function | cross-species protein | cross-species gene/regulatory element |

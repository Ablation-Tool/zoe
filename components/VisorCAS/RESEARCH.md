# VisorCAS -- Bloom Filter Research (book-grounded)

Sources read: *Bloom Filter: A Comprehensive Survey* (Patgiri et al., 18 chapters), *Algorithms and Data Structures for Massive Datasets* (adsmd, Medjedovic/Tahirovic), *Designing Data-Intensive Applications* 2nd ed. (Kleppmann, ch. 4). This maps directly to the VisorCAS build: sizing the deferred BF-B exclusion layer, settling the variant question (standard vs. counting vs. quotient), and understanding the bloom-in-front-of-CAS pattern already proven at production scale in LSM storage engines.

---

## 1. Sizing math (the formulas, stated precisely)

### Core equations

All three sources agree on the standard Bloom filter parameter relationships.

```
FPP (approximate):
  p ≈ (1 - e^(-kn/m))^k

Optimal k (minimizes p for given m, n):
  k_opt = (m/n) * ln(2) ≈ 0.693 * (m/n)

Bit array size from n and desired p:
  m = -(n * ln(p)) / (ln(2))^2

Equivalently (adsmd ch03, Python implementation):
  m = int(-math.log(f) * n / (math.log(2)**2))
  k = int(m * math.log(2) / n)
```

The approximate formula treats bit-setting events as independent; Bose et al. (cited in bloom-ch05) showed this slightly understates the true FPP. The exact form requires conditioning on X = number of set bits and summing over the probability mass function via gamma-transformation (Grandi), but the approximation is tight enough for engineering sizing -- Chernoff bounds confirm the fraction of zeros is highly concentrated around its mean (adsmd ch03).

**Source consistency check:** All three sources give the same k_opt and m formulas. No discrepancy found. bloom-ch05 notes the approximate FPP gives a *lower* FPP than the actual rate; the real rate is marginally higher. For BF-B sizing, size conservatively.

### Worked numbers: BF-B for VisorCAS

Corpus target: n = 50,000 FP-pattern hashes. Hash is blake3, treated as a uniform random key.

**p = 1% (0.01):**
```
m = -(50000 * ln(0.01)) / (ln(2))^2
  = -(50000 * (-4.6052)) / 0.4805
  = 230260 / 0.4805
  = 479,195 bits  ≈  59.9 KB
k_opt = 0.693 * (479195 / 50000) = 0.693 * 9.584 ≈ 6.6  → 7 hash functions
```

**p = 0.1% (0.001):**
```
m = -(50000 * ln(0.001)) / (ln(2))^2
  = -(50000 * (-6.9078)) / 0.4805
  = 345390 / 0.4805
  = 718,875 bits  ≈  89.9 KB
k_opt = 0.693 * (718875 / 50000) = 0.693 * 14.378 ≈ 9.96  → 10 hash functions
```

At 50k elements, BF-B is trivially small in either case. Even 0.1% FPP costs under 90 KB. This validates the SPEC decision to defer BF-B: at this scale the SQLite lookup is never the bottleneck, so BF-B is firmly in the "build only when needed" bucket.

### "10 bits per element ≈ 1%" rule

From ddia2 ch04 (Kleppmann): *"you need to allocate 10 bits of Bloom filter space for every key in the SSTable to get a false-positive probability of 1%, and the probability is reduced tenfold for every 5 additional bits you allocate per key."*

Verified: plugging m/n = 10 into the approximate FPP formula with k = 7:
```
p = (1 - e^(-7*1/10))^7 = (1 - e^(-0.7))^7 = (1 - 0.4966)^7 = 0.5034^7 ≈ 0.0082 ≈ 0.82%
```
Rounds to ~1%. The 5-additional-bits-per-decade rule is a useful calibration heuristic from production systems (BigTable, Cassandra) that matches the math.

---

## 2. Hash functions

### How many independent hashes are actually needed

bloom-ch04 and bloom-ch05 both establish experimentally (10M and 1M element tests) that there is an optimal k forming a U-shaped FPP curve. Too few hash functions: insufficient bit coverage. Too many: saturates the array. For 1M elements at p=0.001, optimal k is ~10; for 10M elements, also ~10. The optimal k tracks m/n linearly, not n alone.

The books (bloom-ch04, bloom-ch05) reference Kirsch-Mitzenmacher (2006, 2008) for the double-hashing trick:

```
g_i(x) = h1(x) + i * h2(x)  (mod m)   for i = 0, 1, ..., k-1
```

This derives k independent-looking indices from two hash evaluations. Kirsch-Mitzenmacher proved this does not asymptotically increase the FPP -- same performance as k truly independent hashes. bloom-ch05 and adsmd-ch03 both confirm this; adsmd shows the Python implementation using mmh3 with different seeds to approximate this.

### Implications for blake3 in VisorCAS

blake3 produces a 256-bit output. Two 64-bit windows from a single blake3 call can serve as h1 and h2. The double-hashing construction then generates all k indices from a single blake3 invocation -- no k separate hash calls needed.

```go
// Sketch: one blake3 call, extract h1 and h2 from output
out := blake3.Sum256(key)
h1 := binary.LittleEndian.Uint64(out[0:8])
h2 := binary.LittleEndian.Uint64(out[8:16])
for i := 0; i < k; i++ {
    idx := (h1 + uint64(i)*h2) % m
    // set bit idx
}
```

This is the exact usage pattern bloom-ch04 recommends: "We must avoid multiple calls to the hash function to enhance the performance of the Bloom Filter."

### Hash quality vs. FPP

bloom-ch04 demonstrates this experimentally: with the same k=2, Murmur2 achieved nearly zero FPP on a disjoint set (4e-6), while FastHash and xxHash both hit ~0.62. The hash function selection is not cosmetic -- it directly determines whether the theoretical FPP is achieved in practice. The key property: the hash must support a seed value (to generate independent-looking outputs) and must distribute uniformly. Cryptographic hashes (MD5, SHA256) fail not on quality but on the wrong size: 256-bit output truncated by modulus loses the distribution guarantees. blake3 is non-cryptographic in speed profile but cryptographic in distribution quality; it is suitable.

The book's recommendation (bloom-ch02): prime number for m reduces FPP -- the modulus distributes more evenly when m is prime. Prime m is the reason robustBF uses prime-dimension 2D arrays. For VisorCAS, choosing m as a prime near the computed value is worth the one-time setup cost.

---

## 3. Deletable / updatable variants -- settling the BF-B open question

### Counting Bloom Filter (CBF) -- bloom-ch08, adsmd-ch03

**Mechanism:** Replace each bit with a counter (originally 4 bits per slot, Fan et al. 2000). Insert increments k counters; delete decrements k counters; zero counter resets the bit.

**Delete support:** Yes, false-negative-free deletion if counters do not overflow.

**Space overhead:** 4x standard bloom at 4-bit counters (bloom-ch08 states this explicitly: "CBF consumes four times more memory compared to Bloom Filter"). adsmd confirms: "about four times more" space.

**Counter overflow risk:** With 4-bit counter (max 15), if any element is inserted 16+ times without intermediate deletion, the counter overflows and later deletions will produce false negatives. Fixed-size counters are a known failure mode (bloom-ch08, Section 8.4).

**Merge/resize:** Not supported natively. A CBF cannot be simply merged or resized without re-ingesting the original elements.

**Verdict for BF-B:** CBF supports delete and eliminates the rebuild requirement, but at 4x memory and with a counter-overflow failure mode. For VisorCAS's pattern corpus (50k elements, slow growth, infrequent reclassification), 4x memory is not the problem. Counter overflow is also not the problem at this scale. The real question is whether we even need delete.

### Quotient Filter -- adsmd-ch03, bloom-ch07

**Mechanism:** Compact hash table using quotienting. Splits the fingerprint into quotient (used as bucket index) and remainder (stored in the slot). Three metadata bits per slot (bucket_occupied, run_continued, is_shifted) allow fingerprint reconstruction.

**Delete support:** Yes. Deletion finds and removes the remainder; metadata bits are updated. No false negatives from deletion.

**Space overhead:** "Due to the extra space required for a linear probing table, quotient filters tend to take up slightly more space than Bloom filters for common false positive rates. For extremely low false positive rates, quotient filters are more space efficient than Bloom filters." (adsmd-ch03).

**Merge/resize:** First-class operations. Resizing traverses the QF in sorted fingerprint order and inserts into a new larger QF -- O(n) sequential scan. Merging two QFs is merge-sort equivalent, also O(n). This is the QF's primary advantage over Bloom filters.

**Fingerprint reconstruction:** Unlike a standard Bloom filter, the QF can reconstruct fingerprints. This is what enables resize without re-reading original elements.

**Performance:** adsmd-ch03 reports (from Bender et al. quotient filter paper): inserts ~2x faster than Bloom filter (3 vs. 1.5 million ops/sec at 75% occupancy); uniform random (unsuccessful) lookups slightly faster in Bloom filter; successful lookups faster in QF. QF degrades significantly above 90% load factor -- keep below 75-90%.

**Failure modes:** Performance collapse at high load factor. Must size with headroom.

### Cuckoo Filter -- bloom-ch07 (Section 7.3)

bloom-ch07 mentions Cuckoo Filter (Fan et al. 2014) as "Cuckoo Bloom Filter" under "Other approximation filters." It stores fingerprints (not full keys), uses partial-key cuckoo hashing with two candidate buckets per fingerprint.

**Delete support:** Yes, by lookup and removal of the fingerprint from either of its two candidate buckets.

**Failure mode:** "If the hash table is huge but stores short fingerprints, then the chance for hash collision increases. This leads to possible insertion failure and reduces table occupancy." (bloom-ch07). Insertion can fail when kicking cycles become too long.

**From bloom-ch03 (robustBF comparison):** Cuckoo Filter (CF) is faster than robustBF for insert and lookup, but "CF exhibits good false positive probability on the Same Set and Mixed Set, whereas it shows the worst performance on Disjoint Set and Random Set due to the kicking process." At 10M elements, CF FPP on Disjoint Set = 0.5749 and on Random Set = 0.9954. This is the kicking instability at high load.

**The books do not provide full implementation detail for Cuckoo Filter.** bloom-ch07 reference points to Fan et al. (2014) paper; that paper is not in the corpus.

### Direct recommendation for VisorCAS BF-B

**The rebuild-from-source design makes native delete unnecessary.**

The SPEC is explicit (Section 13): "we rebuild the filter from the authoritative CAS+SQLite on reclassify." This is the key architectural fact that resolves the open question.

If we rebuild BF-B from the SQLite index whenever the corpus changes, then delete support in the filter structure is redundant. A standard Bloom filter is correct here because:

1. The rebuild is cheap: at 50k elements, recomputing m bits with k hash passes takes milliseconds.
2. The filter is a derived cache (SPEC Section 2, principle 4). The source of truth is SQLite. The filter is wrong only in the window between a reclassification event and the next rebuild.
3. Standard Bloom filter at 1% FPP costs ~60 KB. CBF at the same FPP costs ~240 KB. Quotient filter costs somewhat more. None of these numbers matter at this scale, but standard Bloom is simpler.
4. Rebuild eliminates counter overflow risk (CBF failure mode) and insertion failure risk (Cuckoo failure mode at high load).

**Recommendation:** Build BF-B as a standard Bloom filter, rebuilt atomically from CAS+SQLite on any corpus change. k=7, m sized for 1% FPP at current corpus count plus a 2x growth buffer. On reclassify, rebuild in memory, swap the pointer, discard the old filter. No delete needed, no counter overhead, no kicking instability.

The only scenario where this changes: corpus grows past ~5M elements (LSM-scale) and rebuild latency becomes observable. At that point, evaluate quotient filter for its merge/resize capability. Flag this as a future milestone, not a present concern.

---

## 4. Scalable / growing-corpus designs

### Scalable Bloom Filter (SBF) -- bloom-ch07

Almeida et al. (2007), cited in bloom-ch07: SBF chains multiple Bloom filter slices. Each slice has k hash functions; each hash function operates on its own sub-array. When a slice is full, a new slice is added. During query, all slices are checked. Error probability is tightened per-slice so the union stays below the target FPP.

The book describes SBF as "dynamic memory allocation" with "high scalability." The tradeoff: query cost scales with number of slices (must check all of them).

### LSM-tree layered Bloom filters -- adsmd-ch10, ddia2-ch04

Both sources describe the same production pattern (implemented in LevelDB, RocksDB, Cassandra, BigTable):

- One Bloom filter per SSTable/SST segment, stored in RAM.
- During a point query, the filter for each segment is checked before touching disk.
- True negative from the filter: skip that SSTable, no disk I/O.
- False positive: read the SSTable from disk, discover absence, continue.
- Total filter memory is logarithmic in total data size (because the number of SSTables is O(log_f N/M) where f is the compaction factor).

ddia2-ch04 (Kleppmann): "LSM storage engines often include a Bloom filter in each segment, which provides a fast but approximate way of checking whether a particular key appears in a particular SSTable... If the Bloom filter says that a key is not present, we can safely skip that SSTable, since we can be sure that it doesn't contain the key."

adsmd-ch10: "The biggest gains in the query performance come with the use of Bloom filters that help redirect the query to the right table, thus bringing the query performance to O(1) in most cases... maintaining those Bloom filters in main memory is quite manageable" because the count of filters is logarithmic.

### Mapping to VisorCAS

The per-shard pattern maps to a survey-scoped design: build one Bloom filter per survey batch (Shodan sweep, Censys sweep, etc.), keep all survey filters in RAM, query all of them in sequence. A candidate that returns "definitely not" from all survey filters is excluded cheaply. A candidate that passes at least one is passed to SQLite for authoritative lookup.

This is strictly better than one large resized filter for a growing corpus because:
- No resize operation required.
- New surveys add a new small filter; old surveys' filters remain valid.
- Compaction (merging survey filters into a single accumulated filter) can be done offline when convenient, as a background rebuild.

At VisorCAS scale this is academic -- the corpus is small enough that a single rebuilt filter works fine. But it is the correct architectural direction for growth.

---

## 5. Bloom filters in real storage engines (the CAS-adjacent angle)

### Exact mechanism in LSM trees

From ddia2-ch04 (Kleppmann), describing RocksDB/Cassandra/ScyllaDB/HBase:

1. Writes go to an in-memory memtable (red-black tree or skip list) and a WAL.
2. When the memtable hits its threshold (typically a few MB), it is flushed to disk as an immutable SSTable sorted by key.
3. Each SSTable has a sparse index (first key per block) stored alongside the data.
4. Each SSTable has a Bloom filter for point-query acceleration.
5. On a read: check memtable, then check each SSTable's Bloom filter before touching the SSTable blocks.
6. Compaction merges SSTables in merge-sort order, producing new SSTables with updated Bloom filters.

The SSTables are immutable once written. Bloom filters are recomputed as part of compaction. This is exactly the rebuild-from-source pattern.

adsmd-ch10: "maintaining a number of Bloom filters in RAM (a use case covered in chapter 3), one per table, can help eliminate the disk lookup on tables that do not contain updates for the queried element."

### Content-addressing and dedup (adsmd-ch02)

adsmd-ch02 covers ChunkStash (Dell EMC Data Domain) as the canonical deduplication example: files are split into fixed-size chunks, each chunk is hashed (SHA-1 fingerprint), the fingerprint is looked up in a hash table. If found, the chunk is a duplicate; if not, the chunk is new and is stored, with the fingerprint added to the hash table.

The mechanism is: hash(content) = address. CAS is exactly this pattern -- the hash of normalized content is the identity, and the lookup determines "have we seen this pattern before." The Bloom filter in front of the CAS store serves as the fast-path check: "definitely not seen" requires no disk access; "maybe seen" goes to the authoritative store.

### Direct mapping to VisorCAS

VisorCAS's CAS + SQLite + BF-B is structurally identical to the LSM bloom-in-front-of-store pattern:

```
LSM engine:               VisorCAS:
memtable (RAM)            --  (no direct analog; VisorCAS is not write-optimized)
SSTable (disk, immutable) --  CAS blobs (disk, immutable, content-addressed)
SSTable sparse index      --  SQLite fp_pattern + occurrence tables
SSTable Bloom filter      --  BF-B (the deferred exclusion layer)
compaction                --  corpus reclassification + BF-B rebuild
```

The storage engine literature validates: the Bloom filter is a derived cache, never authoritative. The authoritative path is always CAS + SQLite. The filter only skips the authoritative lookup for definite non-members -- exactly what the SPEC says.

---

## 6. False-positive semantics (confirm our SPEC principle)

### One-sided guarantee: what the texts say

bloom-ch02 (Definition 2.4 and 2.5): "If [element is not in set] and [Bloom filter returns present], then the response is a false positive." "If [element is in set] and [Bloom filter returns absent], then the response is a false negative." Standard Bloom filter without deletion has zero false negatives by construction.

bloom-ch03: "Importantly, we do not verify any item of the set [inserted set] in real implementation... the conventional Bloom Filter does not have false negative issues."

adsmd-ch03: "They have false positives, but they do not have false negatives, and the one-sidedness of the error can be used to our benefit. When the Bloom filter reports the item as Found/Present, there is a small chance it is not telling the truth, but when it reports the item as Not Found/Not Present, we know it's telling the truth."

ddia2-ch04: "If the Bloom filter says that a key is not present, we can safely skip that SSTable, since we can be sure that it doesn't contain the key. If the Bloom filter says the key is present, we have to consult the sparse index... If it was a false positive, we have done a bit of unnecessary work, but otherwise no harm is done."

### SPEC Principle 2 confirmed

SPEC Section 2, principle 2: "The bloom filter is a one-sided test. It eliminates true negatives ('definitely not'); everything it passes is contaminated with false positives by design." This is confirmed precisely by all four sources. The phrasing "definitely not" is the correct characterization. No correction needed.

The SPEC correctly identifies the implication: the only trustworthy answer is "no." This is also confirmed: an LSM engine uses the "no" answer to skip disk I/O entirely; it does not trust the "yes" answer without verification.

---

## 7. Anything surprising or directly reusable

### 1. Optimal occupancy at 50% ones

adsmd-ch03 (citing the mathematical derivation): "an optimally filled Bloom filter has about a 50% probability that a random bit is 1." This is a diagnostic. If you query the bit array of BF-B and more than ~60% of bits are 1, the filter is over-capacity or was configured with n too small; FPP is higher than designed. This is a cheap operational sanity check -- just count set bits after building.

### 2. Standard Bloom filter is 1.44x from the theoretical optimum

adsmd-ch03 derives the space-error lower bound and shows the Bloom filter achieves it within a factor of log_2(e) ≈ 1.44. "There exist data structures that are closer to the lower bound than the Bloom filter, but some of them are very complex to understand and implement." For VisorCAS, this means we are not leaving significant space on the table with a standard Bloom filter.

### 3. Prime m reduces FPP

bloom-ch04 and bloom-ch02: using a prime number for m provides better distribution properties because the modulus operation distributes items more evenly. bloom-ch02 states this directly; robustBF enforces prime dimensions for its 2D array. For BF-B, choose the smallest prime >= the computed m.

### 4. Unsuccessful lookup averages 1-2 probes in an optimally configured filter

adsmd-ch03: "on average, an unsuccessful lookup in a well-configured Bloom filter takes about one to two probes before giving up." This is the key performance claim for the use case -- when querying a candidate against BF-B, most candidates (the pattern is not in the corpus) will return "not present" after touching only 1-2 bits. Cache-line-friendly for hot corpus lookups.

### 5. robustBF: 2D Bloom filter with near-zero FPP at 1.36 bits/element

bloom-ch03: robustBF uses a 2D prime-dimension array with a modified Murmur hash function. For 10M elements at p=0.001 target: robustBF uses 1.36 bits/element and 1.62 MB; standard libbloom uses 14.38 bits/element and 17.14 MB. FPP of robustBF at disjoint set: 4e-6 (vs. 0.001 target). This is a 10x memory reduction over a standard implementation.

For VisorCAS BF-B at 50k elements with 1% FPP, a standard Bloom filter is already ~60 KB (fine), but robustBF's approach (prime 2D array, modified Murmur) could get to ~7 KB at similar accuracy. Not immediately necessary but worth tracking for the Go implementation.

### 6. Bloom filter benefit/overhead formula (bloom-ch06)

bloom-ch06 formalizes when a Bloom filter helps vs. hurts:
```
Benefit  = (total_negatives - false_positives) * db_lookup_cost
Overhead = (true_positives + false_positives) * bloom_query_cost
```
Net benefit is positive only when the corpus has a meaningful fraction of true negatives. For VisorCAS, the negatives are the FP patterns being screened out before aimap deep-enum. At survey scale (14k raw hosts collapsing to a few hundred fp_hash patterns), the ratio is favorable: most candidate patterns will not be in the BF-B corpus, so the filter earns its overhead in the first survey where the corpus is non-empty.

### 7. Bloom filter saturation and periodic flush (bloom-ch14)

bloom-ch14 (network security applications) notes that a standard Bloom filter that is never rebuilt will saturate over time, with FPP approaching 1 as most bits become 1. Security practitioners deal with this via periodic flushing. For VisorCAS, the rebuild-on-reclassify design handles this naturally: every rebuild resets only the bits corresponding to current corpus members.

### 8. Bloom filter space is log_2(e) ≈ 1.44x from optimal; quotient filter is closer

adsmd-ch03 notes quotient filters are closer to the lower bound for very low FPP (below 1%). At 0.1% FPP, the quotient filter beats the standard Bloom filter on space. At 1% FPP (the VisorCAS target), Bloom filter is adequate and simpler.

---

## 8. Comparison table -- with vs. without this research

| Aspect | Without books | With books | Impact on VisorCAS |
|---|---|---|---|
| Sizing formula | Rough guess, m = 10 bits/element | Exact: m = -(n ln p)/(ln2)^2; k = (m/n) ln2; BF-B for 50k@1% = 479 kbits / 59.9 KB | Correct sizing on first build; no trial-and-error |
| "10 bits/element = 1%" rule | Unknown origin | Kleppmann (ddia2 ch04) confirms and explains it as a production heuristic from BigTable/Cassandra | Validates the rule; explains when to deviate |
| Hash function choice | "blake3 is fast, should be fine" | Double-hashing (Kirsch-Mitzenmacher) derives k indices from 2 outputs; cryptographic hashes fail Bloom due to truncated distribution, not quality | Confirmed blake3 is correct; concrete Go sketch for index derivation from single invocation |
| Optimal k shape | Vaguely "more hashes = better" | U-shaped FPP vs. k curve; both too few and too many degrade FPP; k_opt = 6-7 for BF-B 1% target | Build with k=7, not arbitrary; experimental confirmation from 10M-element tests |
| CBF vs. standard for deletable layer | "Need CBF because we reclassify" | CBF is 4x memory with counter overflow risk; rebuild-from-source eliminates need for delete; standard Bloom filter is correct | Settled the Section 13 open question: standard Bloom + rebuild beats CBF |
| Quotient filter | "Maybe better, investigate" | QF supports delete + merge + resize efficiently; slightly more space at 1% FPP; performance degrades above 90% load; not needed unless corpus exceeds rebuild latency threshold (~5M elements) | Defer QF to future milestone; document the trigger condition |
| Cuckoo filter | Unknown | Insertion failure at high load; FPP degrades badly on disjoint sets (0.57-0.99 in experiments); not suitable for a corpus of unknown-at-build-time elements | Excluded from consideration for BF-B |
| LSM bloom-in-front-of-store pattern | Theoretical analogy | Confirmed production mechanism in RocksDB, Cassandra, BigTable; exact structural match to VisorCAS CAS+SQLite+BF-B architecture | Validates the architecture; borrows the rebuild-on-compaction playbook |
| Scalable / per-shard bloom | Not considered | Per-SSTable bloom in LSM trees; Almeida SBF chains slices; per-survey-batch filter is the natural growth path | Growth architecture defined before the corpus grows |
| One-sided guarantee | Intuitively understood | Precisely confirmed across 4 sources; "definitely not" is the only trustworthy answer; false positives are tolerable overhead | SPEC Principle 2 confirmed verbatim; implementation can rely on this |
| Optimal fill diagnostic | Unknown | Optimally configured filter has ~50% bits set to 1; measure after build as sanity check | Cheap correctness check; add to BF-B build step |
| Space lower bound | Unknown | Standard Bloom is 1.44x from theoretical minimum; quotient filter closer at very low FPP | At 1% FPP, standard Bloom is fine; no complexity needed |

---

## 9. Open items the books did NOT settle

**1. Scalable Bloom Filter (SBF) internals -- thin coverage**
bloom-ch07 cites Almeida et al. (2007), Scalable Bloom filters, *Inf. Process. Lett.* 101(6):255-261, but does not describe the per-slice error tightening mechanism in detail. If VisorCAS corpus grows past single-filter rebuild practicality, read the primary paper.

**2. Cuckoo Filter insertion failure rate under adversarial input -- not addressed**
The books note the kicking failure mode but do not give failure probability as a function of load factor. Fan et al. (2014, CoNEXT) is the primary paper: "Cuckoo filter: practically better than Bloom." The experimental data in bloom-ch03 (0.9954 FPP on Random Set at 10M elements) suggests severe instability with disjoint query sets. Do not use for BF-B without reading the primary paper.

**3. Blake3 and double-hashing independence**
The Kirsch-Mitzenmacher theorem (2006/2008) proves that g_i(x) = h1(x) + i*h2(x) achieves the same asymptotic FPP as k independent hash functions, but the proof uses 2-independent hash functions. blake3 is not analyzed in the texts with respect to pairwise independence. This is an implementation-level concern: in practice, extracting two non-overlapping 64-bit windows from a blake3 digest and using the double-hashing construction should be fine, but it is not formally validated in these texts.

**4. Bloom filter security under adversarial queries -- limited**
bloom-ch14 discusses pollution attacks (attacker floods insertions to saturate the filter) and query-only attacks (attacker floods queries to degrade performance). The chapter shows empirically that Bloom filters handle 20M queries against 10M legitimate items in ~12 seconds and pass only ~55k attack requests (0.27%). For VisorCAS, the filter is not adversarially exposed -- it is an internal pipeline component -- so this is informational only.

**5. Counting Quotient Filter (CQF) for high-cardinality future growth**
bloom-ch08 (Section 8.3.15) and adsmd-ch03 both mention the Counting Quotient Filter (Pandey et al. 2017): "good locality of reference and supports deletion, resizing, merging, and high concurrency." This is the state-of-the-art replacement for CBF. Not in scope now but is the correct upgrade path if BF-B ever needs native delete plus resize. Primary paper: Pandey et al., SIGMOD 2017.

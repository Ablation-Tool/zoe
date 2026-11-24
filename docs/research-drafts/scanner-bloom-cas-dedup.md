# Two-Layer Lock-Free Bloom + Atomic CAS Deduplication Design (Google Drive Research Draft)

> Preserved from `gdrive:Documents/misc/Scanner-Bloom-CAS-Dedup-Design.md` for Zoe Wave 3 `VisorCAS` lock-free fast-path.

## Problem Solved
The tool needs to track which IP:port combinations have already been scanned across 1000+ concurrent workers without mutex contention, which would serialize access and destroy throughput.

## The Two-Layer Approach

**Bloom Filter (Read-Only Fast Path)**
The scanner uses a 16 MB Bloom filter as a probabilistic check: "Have I possibly seen this key before?" As stated, the filter performs "3 array reads, returns true or false. No write, no lock, unlimited concurrent readers." This eliminates ~98% of duplicates without any synchronization cost.

**CAS Dedup (Atomic Claim)**
For candidates that pass the Bloom filter, a compare-and-swap atomic operation ("one atomic compare-and-swap. Winner gets the slot. Loser returns false immediately") claims ownership of a deduplication slot. The CAS table stores 2M entries across 32 MB.

## What Is Stored
The key appears to be the IP:port tuple. Each worker reads the banner and tests whether that combination was already captured. The value stored is simply occupancy—marking that slot as claimed.

## False-Positive Handling
The Bloom filter has a tunable "2% false positives" rate, meaning some unseen IP:ports incorrectly appear as duplicates. These false positives are acceptable because they merely skip redundant scans; no data is lost, only minor efficiency trade-off.

This design achieves ~176 handshake probes per second without lock contention.

Pulled the scanner internals. Important terminology catch first, because it changes the answer: in scanner, CAS means compare-and-swap (the lock-free atomic claim), not content-addressable storage. The mechanism there is a dedup engine for 1000+ concurrent workers: 16MB bloom filter as a lock-free "have I possibly seen this IP:port" fast-path, then a compare-and-swap to atomically claim the slot so only one worker scans it. The problem it solves is mutex contention, and a bloom false-positive is safe because it just skips a redundant scan.

That matters, because Scene Finder's bottleneck is a different animal, and only part of the scanner pattern transfers. Here's the honest mapping.

Where the scanner pattern fits — and where it doesn't

scanner's problem:     1000+ workers, don't rescan same host, avoid LOCK CONTENTION
scenefinder's problem: one query fires 20-30 SERIAL external calls; cold vague query = worst case
                       -> the cost is EXTERNAL-CALL LATENCY, not lock contention

The scanner pattern is a dedup/amortization layer. It accelerates repeated and concurrent-duplicate work. It does nothing for the cold first run of a single query. So it fixes a real slice of the problem, not the whole thing. Two places it maps cleanly:

1. Bloom + compare-and-swap → request coalescing (singleflight)

This is a near-exact transfer of scanner's mechanism. Real scenario under load: three users search motor within a few seconds. Right now all three fire the full 30-call pipeline independently.

search "motor"
   │
   ├─ normalize+hash: h = sha256("motor|all|safe=false")
   ├─ bloom.maybeContains(h)?  ── 3 reads, no lock (scanner's fast path)
   │      false ─▶ definitely not in flight / not cached ─▶ run pipeline
   │      true  ─▶ maybe in flight ─▶ CAS-claim the in-flight slot
   │                   winner  ─▶ runs pipeline ONCE, others subscribe to its stream
   │                   losers  ─▶ attach to winner's result, zero extra AI calls

That's scanner's bloom → CAS-claim → winner does the work, losers return applied verbatim. Under any real traffic, this collapses duplicate concurrent searches from N pipelines to 1.

2. Content-addressable storage → the actual cache (the big win)

Here CAS means the other thing — hash-keyed storage — and it's fix #2 from the write-up, done properly at two layers:

query-level CAS:   key = hash(normalized query)      value = final result
                   "motor" second time ─▶ instant, skips all 30 calls
result-level CAS:  key = hash(web page content)       value = the LLM analysis of it
                   same YouTube page in a later query ─▶ analyzed ONCE, ever

The result-level cache is where content-addressing earns its keep: step 7's 14 per-result LLM calls are the latency hog, and the same popular pages recur across many queries. Content-hash them and you analyze each unique page exactly once across the whole system. Bloom fronts this store the same way scanner uses it — maybeContains(contentHash) before you hit the real store.

★ Insight ─────────────────────────────────────
- Bloom's semantics flip meaning between the two uses. In scanner, a false-positive skips work and that's safe (it was a duplicate anyway). In a cache, a false-positive means "maybe cached" so you must still consult the real store — bloom only saves you on definite misses. Same filter, weaker guarantee, so size it for a low FP rate (~1%) here.
- The scanner reached for bloom+CAS because of lock contention at 1000 workers. Scene Finder doesn't have that. You'd adopt the same shape for a different reason: amortizing expensive external calls, not dodging mutexes. Right pattern, different justification — worth being clear-eyed about so you don't over-engineer the concurrency side.
─────────────────────────────────────────────────

The honest verdict

- Content-addressable caching (query + per-page): yes, strong fit. This is the single biggest durable win and it's genuinely the CAS-storage pattern.
- Bloom + compare-and-swap singleflight: yes, direct transfer, real value under load.
- But neither speeds up the cold, first-ever motor search by one user. That still needs the pipeline fixes: truly parallelize the 14 analysis calls, cap them to top ~5, and short-circuit vague single-word queries. Bloom+CAS amortizes repeats; it can't shorten a chain that has never run before.

So: same primitives we used in scanner, but they solve the second and third time you search "motor," plus the concurrent-duplicate case. To also fix the first time, you pair them with the parallelize-and-cap change to the pipeline itself.

Want me to sketch the actual architecture — bloom + CAS cache layer wrapping search-smart-hybrid, plus the singleflight coalescer — as a concrete design your friend can drop in? If you can get me the route handler, I'll write it against the real code instead of a sketch.

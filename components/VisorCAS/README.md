<h1 align="center">VisorCAS</h1>

<h4 align="center">Content-addressed false-positive ledger for AI infrastructure surveys.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/VisorCAS/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/VisorCAS?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/VisorCAS/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/VisorCAS?style=flat-square" alt="license"></a>
  <a href="https://golang.org"><img src="https://img.shields.io/badge/go-1.25%2B-00ADD8?style=flat-square&logo=go" alt="go"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#what-it-is">What it is</a> •
  <a href="#how-it-works">How it works</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#scope">Scope</a>
</p>

---

VisorLog ledgers what is. VisorCAS ledgers what looked like a finding and was not. A survey scanner produces candidates. Verification turns most of them into false positives, and without structure those become noise that gets re-discovered every run. VisorCAS addresses each false positive by the blake3 hash of its normalized response fingerprint, so identical patterns from different hosts and different sources collapse to one entry, classified once, reused forever.

The name is deliberate. *Content Addressable Storage*, not Central Authentication Service. The address is the content. Identical normalized fingerprints collapse on write, before any classification. Dedup is structural, not category-driven.

# What it is

- Content-addressed store for normalized FP fingerprints, keyed by blake3 of canonical JSON
- Two-level hash: a source-independent service fingerprint (the dedup spine), plus source-tagged immutable observations (the provenance)
- Five-value disposition model so auth-on findings and honeypots never get mistaken for noise
- Fusion stage over Shodan, Censys, and prior NuClide data, using cross-source agreement as a pre-probe triage signal
- Sits at the aimap-report-to-VisorLog seam (after fingerprinting, before ledger). Successor to `winnow`

# What it is not

- not a scanner (JAXEN, Censys-sweep, and Shodan harvest produce inputs)
- not a detector (aimap owns the signatures)
- not a findings ledger (VisorLog owns the positives)
- not a pre-aimap IP filter. The placement is post-aimap, at the verify-to-ledger seam

# How it works

```
0  JAXEN (Shodan)  -+
0b Censys sweep   --+--> ips.txt -> 1 aimap (fingerprint + deep-enum) -> aimap-report.json
   nuclide.db    ---+                                                         |
                                                                              v
                              [ VisorCAS @ the aimap-report.json seam ]
                                +- normalize each enum_result -> structured fingerprint
                                +- canonical JSON -> blake3 -> CAS.Put (immutable, dedup)
                                +- index + occurrences (SQLite)
                                +- screen known FPs (winnow seed + learned corpus)
                                +- assign disposition (from VERIFIED auth-state)
                                +- fuse auth-state across sources
```

Key design decisions (full rationale in [`SPEC.md`](SPEC.md) and [`RESEARCH.md`](RESEARCH.md)):

1. The address is the hash of the content. Dedup is structural.
2. Consume verified dispositions, never invent them (Insight #16). A 200 is service identity, not auth state.
3. The bloom filter is one-sided and deferred. At current scale SQLite beats it. Build BF-B only when lookup hurts.
4. The bloom (when built) is a derived cache, never the source of truth. CAS plus index stay authoritative.
5. Disagreement between verified sources is free FP signal.

# Installation

```bash
go install -v github.com/nuclide-research/VisorCAS/cmd/visorcas@latest
```

Or build from source:

```bash
git clone https://github.com/nuclide-research/VisorCAS
cd VisorCAS
go build -o visorcas ./cmd/visorcas
```

Requires Go 1.25 or later.

# Usage

```console
# ingest an aimap report at the verify-to-ledger seam
visorcas ingest --from aimap-report.json

# query the FP corpus
visorcas query --disposition fp --since 2026-05-01

# fuse Shodan + Censys + prior nuclide data on a host
visorcas fuse --ip 8.130.154.222
```

# Layout

```
cas/         content-addressed store, blake3 keying
normalize/   enum_result -> canonical JSON
ledger/      index + occurrences in SQLite
fuse/        cross-source disposition fusion
ingest/      aimap-report.json reader
adapters/    winnow seed corpus + per-source adapters
gate/        verification gate (rejects unverified auth-state claims)
screen/      known-FP screen
assetrec/    asset reconciliation
books/       book-grounded design notes
testdata/    golden inputs
cmd/visorcas main entrypoint
```

# Status

Spec complete. Implementation in progress. The build runs against the canonical [`SPEC.md`](SPEC.md) and the book-grounded bloom-filter notes in [`RESEARCH.md`](RESEARCH.md). Already shipped: `cas`, `normalize`, `ledger`, `fuse`, `ingest`, CLI scaffold, 33 tests.

# Scope

VisorCAS does not scan anything. It consumes structured output from upstream tools and classifies it. The disposition model is conservative by design: an unverified auth-state read never gets stored as a finding or a confirmed FP, only as an observation pending verification.

# Our other projects

- [VisorLog](https://github.com/nuclide-research/visorlog) — findings ledger, the inverse of VisorCAS
- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner, the upstream signal
- [VisorScuba](https://github.com/nuclide-research/VisorScuba) — OPA compliance scoring over VisorLog
- [scanner](https://github.com/nuclide-research/scanner) — fast active-banner stage feeding aimap
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

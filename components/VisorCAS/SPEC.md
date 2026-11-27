# VisorCAS - Design Spec (v2, audit-reconciled)

> The arsenal's negative-space ledger. winnow's durable successor.
> Content-addressed false-positive management for the NuClide AI-infra survey pipeline.
> **VisorLog ledgers what is. VisorCAS ledgers what looked like a finding but was not.**

Status: design, pre-implementation. Single source of truth for the build. **v2 reconciles two reviews:** the methodology-fit check (placement was wrong) and the 43-repo arsenal audit (`ARSENAL-AUDIT.md` - winnow is the predecessor, the disposition set was too coarse, the dedup key was wrong). Code already built (`cas`, `normalize`, `ledger`, `fuse`, `ingest`, CLI; 33 tests) stays valid; the deltas below are what it must catch up to.

**The name is deliberate.** It puts *Content Addressable Storage* in the title so the Central-Authentication-Service collision cannot creep back.

Decisions: **language = Go** · **hash = blake3** · **dashboard = headless v1**.

---

## 1. Purpose and scope

VisorCAS is the content-addressed, persistent, multi-disposition **evolution of `winnow`**. winnow already screens scanner output against codified Insights and tags PASS/REFUTED/DOWNGRADE, but it is stateless - no dedup, no persistence, no cross-survey memory. VisorCAS makes that screening durable: it addresses each false positive by the hash of its normalized service identity, classifies it, and remembers it so the same noise is never re-verified across surveys.

**It is:** a content-addressed store + queryable index + normalizer that sits at the **verify-to-ledger seam**, consuming aimap's output.

**It is NOT:**
- not authentication (CAS = Content Addressable Storage, never Central Authentication Service)
- not a detector (aimap is the detector; VisorCAS never re-implements signatures)
- not a scanner (JAXEN/Censys harvest; VisorCAS consumes downstream output)
- not a findings ledger (VisorLog owns true positives; VisorCAS owns the negatives)
- not a winnow replacement - its durable successor; winnow's signatures are VisorCAS's seed corpus
- **not a pre-aimap IP filter** (the original "Stage 0c" placement was wrong - see section 3)

---

## 2. Core principles

1. **The address is the hash of the content.** Identical normalized fingerprints collapse to one entry at write time, before any classification. Dedup is structural, not category-driven. (js-extractor proves the pattern in-arsenal: sha256-keyed cache + host-attribution map.)

2. **Consume verified dispositions; never invent them (Insight #16).** A 200 is service identity, not auth state. VisorCAS reads the *verified* auth state (aimap `auth_status`, VisorScuba `unauth_verified`, VisorBishop `AuthState`, Censys data-tier decoders) - it does not infer auth from a status code.

3. **The bloom filter is a one-sided test, and it is DEFERRED.** It eliminates true negatives only; everything it passes is contaminated by design. At current scale a SQLite lookup beats it. Build BF-B only when the lookup hurts.

4. **The bloom (when built) is a derived cache, never the source of truth.** CAS + index are authoritative. Reclassify in the index, rebuild the bloom. A bloom-only learning loop is a one-way ratchet that silently accrues false negatives.

5. **Disagreement between verified sources is free FP signal.** Agreement across homogeneous auth-state reads (not harvest sources) is a better triage signal than a bloom bit (see section 7).

---

## 3. Architecture (corrected placement)

The original spec placed VisorCAS pre-aimap ("Stage 0c"), reading `ips.txt`. That was wrong: **there are no service fingerprints before aimap** - aimap (Step 1) is what produces them. VisorCAS's whole value needs fingerprints, so it sits *after* aimap, at the seam where `aimap-report.json` converts to VisorLog NDJSON - exactly where `winnow` already runs.

```
0  JAXEN (Shodan) ─┐
0b Censys sweep ───┼─> ips.txt ─> 1 aimap (fingerprint + deep-enum) ─> aimap-report.json
   nuclide.db ─────┘                                                          │
                                                                              ▼
                                  [ VisorCAS @ the aimap-report.json seam ]
                                    ├─ normalize each enum_result -> structured fingerprint
                                    ├─ canonical-JSON -> blake3 -> CAS.Put (immutable, dedup)
                                    ├─ index + occurrences (SQLite)
                                    ├─ screen known FPs (winnow signatures + learned corpus)
                                    ├─ assign disposition (from VERIFIED auth-state)
                                    └─ fuse auth-state across sources
                                                 │
                       survivors ─> aimap-to-findings.py -> VisorLog (nuclide.db)   [true positives]
                       FPs ───────> VisorCAS corpus                                  [the negative ledger]
                       substrate ─> reroute (wrong-surface-class), not the AI ledger
```

VisorCAS does not reduce aimap's compute (aimap must run to fingerprint). It reduces what reaches verification, the ledger, and disclosure - and screens FP patterns learned in prior surveys so they never cost analyst attention again.

---

## 4. Data model (two-level hash)

Pattern dedup and provenance are different jobs. One hash cannot do both.

### 4a. Service-fingerprint - the dedup spine (CORRECTED)
Source-independent, instance-independent. **Key on aimap's structured `enum_results` fields, NOT the raw body.** `body_snippet` is truncated and carries volatile timestamps/versions that defeat dedup; `notes` embeds the host IP and defeats cross-host dedup.

```json
{
  "service": "weaviate",
  "port_class": 8080,
  "auth_status": "unauth",          // normalized 3-way (see section 6)
  "categories": ["unauth_data"]     // sorted set from findings[].category
}
```
Canonicalize first (sorted keys, fixed formatting - the pcse `trust_hash.py` pattern), then `hash = blake3(canonical)`. **Document the excluded-volatile-fields list explicitly** - VisorRoam's `NewID = sha256(ip|port|service|choke_point)` is the precedent: it lists what it excludes (banner, body, model-list) and why. The FP disposition + root_fix attach to this hash.

### 4b. Observation - the provenance
Source-dependent, immutable, append-only. Points at a service-fingerprint hash.
```json
{ "source": "aimap",      "observed_at": "T-3d",  "ip": "...", "port": 8080, "fp_hash": "a3f7c2..." }
{ "source": "visorbishop","observed_at": "T-3d",  "ip": "...", "port": 8080, "fp_hash": "a3f7c2..." }
```
`agreement(ip) = count of distinct verified sources whose observations for that ip map to the same fp_hash`

### 4c. Index (SQLite)
```
fp_pattern:  fp_hash PK | service | category | disposition | auth_status | root_fix | first_seen | hit_count
occurrence:  fp_hash    | source | ip | observed_at | survey_ctx                       (append-only)
source_rel:  source | category | lag_days | reliability                               (learned, see 7)
```
Leverage measured on real data (Cat-32, 2026-06-03): **2624 hosts collapsed to 185 patterns (14:1)**, and one recorded classification screened 46 hosts. You classify patterns, not hosts.

---

## 5. The normalizer (load-bearing)

Rests on "structurally identical FPs hash identically." Two failure modes, both fatal: under-normalize (every FP unique, nothing learned) / over-normalize (distinct services collapse, silent false negatives).

- Production input is `aimap-report.json`. Key the fingerprint on `service` + `port_class` + normalized `auth_status` + sorted `categories` (section 4a). Do **not** hash `body_snippet` or `notes`.
- Canonical-JSON before blake3 (sorted keys, fixed float/number formatting).
- The `adapters.ShodanResults` path (body=server) stays as a secondary/test source; the production adapter is `adapters.AimapReport`.
- Test-first against the five fixtures (section 12); each collapses to one stable hash, none collide.

---

## 6. Disposition taxonomy (SIX values) + the 3-way auth state

The five-value model was too coarse; the audit forces a sixth and a separate auth axis.

| Disposition | Meaning | Action | Excludable? |
|---|---|---|---|
| `misidentification` | not the service at all (Prometheus, nginx catchall, port collision) | learn, exclude | **yes** |
| `transient-artifact` | scan-state/tool artifact (CVAT IAP 200 under concurrency) | re-verify; never permanent | no |
| `auth-on` | real AI service, **verified** auth present | promote to VisorLog (the thesis) | NO |
| `deception` | adversary fake surface (AS63949 honeypot) | track as intel | NO |
| `tool-bug` | scanner defect / unconditional hardcoded CVE (aimap MLflow/Flowise CVEs) | fix the scanner | n/a |
| `wrong-surface-class` (NEW) | correct fingerprint, wrong surface - Docker/K8s/etcd substrate, not the AI service | **reroute** to substrate channel | NO - not noise, not the AI ledger |

`wrong-surface-class` is not an FP to suppress; substrate exposure (an open Docker socket) is often higher severity than the AI service. Reroute, never exclude. (Matches the AI-vs-substrate scope rule.)

**Auth state is a separate 3-way axis (Insight #16, #70 - the decoder is auth-state, the label is not):**
- `UNAUTH` - verified unauthenticated (aimap `auth_status:"none"` + data-layer probe)
- `AUTH-UNKNOWN` - surface open, auth NOT verified (aimap `auth_status:"unknown"`) - held for verification, dispositioned as **neither** FP nor finding
- `AUTH` - verified protected -> the `auth-on` disposition

**Hard guard (Insight #25):** a Tier-C (auth-on-default) platform returning 0 unauth is a CONFIRMED result, not an FP. Never disposition these as false positives. Tier comes from `aimap-profile`.

Optional 7th, `unverified-cve`, for aimap's unconditional CVE emissions - or fold into `tool-bug`.

---

## 7. Multi-source fusion (recast to the verify stage)

The harvest sources (Shodan, Censys IPs) merge into one `ips.txt` before aimap, so source identity is gone by fingerprint time. Fingerprint-level agreement across *harvest* sources is therefore near-zero by construction - a real finding from the methodology-fit review.

The homogeneous trio that *does* agree lives at the verify stage, three independent reads of the **same** observable (auth posture of one service):
- **Censys data-tier decoders** (`host.services.redis.auth_response`, `postgres.startup_error`) - auth state without connecting
- **aimap** `auth_status`
- **VisorBishop / VisorScuba** verified `AuthState` / `unauth_verified`

```
3/3 agree UNAUTH                          high-confidence finding, verify first
1/3, contradicted by a deeper-ID source   likely FP, screen
Censys(stale)=UNAUTH vs VisorBishop=AUTH  remediation divergence (captured in time), re-verify
```

**Presence-overlap is the robust cross-source signal; fingerprint-agreement requires homogeneous probes.** Source-reliability (`source_rel`) learns "source S lags for pattern P by ~N days." Temporal divergence is a measurement, not a conflict - harvest it later, not in v1.

---

## 8. Two feedback loops

```
FAST:  verified FP -> CAS -> (eventual) exclusion bloom -> screen next time
SLOW:  corpus shows "aimap emits pattern P 400x as FP" -> tighten aimap's fingerprint
       at the root (anchor body_contains to a json_field) so it is never emitted again
```
The slow loop is higher-value (fix the root). The FP corpus is a diagnostic for the scanner. winnow's 7 signatures + the ~18 verification Insights are the initial fast-loop rules.

---

## 9. Record conformance (nuclide-asset-schema)

Conform to the canonical record format (`nuclide-asset-schema`, JSON Schema 2020-12 v1.1.0) where VisorCAS emits asset/finding records:
- emit the `findings[]` shape (rule_id, severity, evidence, tags); use `classification` (category incl honeypot) and `lifecycle` fields.
- the schema has **no FP/disposition field** - VisorCAS owns disposition; carry it (plus the blake3 hash) in the `raw` passthrough for now, and propose a `findings[].disposition` upstream later.
- register VisorCAS as the 16th `ToolSpec` in `visor/internal/manifest/manifest.go`; it is a new AI-ASM pillar ("Screen / FP disposition", with winnow).

---

## 10. Anti-scope (explicitly NOT building)

- **BF-A (positive-detection bloom)** - redundant with aimap's structured matching. Cut.
- **Keyword bloom filters** - generic tokens match everything. Cut.
- **CAS-as-auth / session tickets** - acronym collision. Cut.
- **Pre-aimap IP filtering ("Stage 0c")** - no fingerprints exist there. Cut; placement is the aimap seam.
- **A parallel FP screener** - winnow exists; VisorCAS evolves it, does not duplicate it.
- **Re-implementing harvest/detect/ledger** - JAXEN, aimap, VisorLog exist.
- **BF-B in v1** - deferred until the SQLite lookup is the bottleneck.

---

## 11. Integration

At the `aimap-report.json` seam in `~/AI-LLM-Infrastructure-OSINT/data/visor-chain-runner.sh`, between Step 1b (aimap) and Step 6 (`aimap-to-findings.py` -> `visorlog ingest`), subsuming the spot where `winnow` runs in `sentinel`:

```
aimap-report.json -> VisorCAS (normalize, dedup, screen, disposition)
   -> survivors -> aimap-to-findings.py -> visorlog ingest (true positives)
   -> FPs -> VisorCAS corpus ;  substrate -> reroute
```

Plus a **reclassify/reopen path**, not just pre-ingest screening: `data/cat32-severity-correction.py` shows a real post-hoc correction (one-api/new-api downgraded after a default-cred probe returned 0/40). Support reclassifying an existing entry, then rebuild the exclusion view. **Coordinate the hash scheme with VisorRoam** (its sha256-on-identity vs our blake3-on-content) - or extend VisorRoam's `inventory.assets` table rather than building a parallel store.

---

## 12. Seed corpus and test fixtures

**Seed corpus (the fast-loop rules):** winnow's 7 signatures + the ~18 verification/FP/honeypot Insights mapped in `ARSENAL-AUDIT.md` (#1,6,7,15,16,22,25,26,30,32,47,51,52,65,68,69,70,76). Port winnow's signatures first.

**Normalizer test fixtures (5) + 1 staleness case** - both the initial corpus and the regression gate:
1. `transient-artifact` - aimap CVAT FP on transient GCP IAP 200s (fix: anchor to json_field)
2. `misidentification` - aimap dcm4chee ASP.NET catchall echo
3. `tool-bug` - aimap enumWeaviate spurious 2-object count
4. `misidentification` - menlohunt 2xx/3xx/4xx kubelet = hit
5. `deception` - AS63949 honeypot fleet (salt `wW0sffoqsk.EM`)
6. staleness - Shodan-unauth / Censys-auth on one ip (agreement + divergence path)

---

## 13. Build order

1. ✅ `cas` core + `normalize` (built; normalize must switch to structured-field keying for the production path).
2. ✅ `ledger` SQLite index (built; add `wrong-surface-class` + `auth_status` column + the Tier-C guard).
3. ✅ `fuse` + `ingest` + CLI (built; recast fusion to verified sources).
4. **`adapters.AimapReport`** - the production adapter (aimap-report.json -> observations, `auth_status` -> 3-way). NEXT.
5. **Port winnow's 7 signatures** into the screen as the first real disposition rules.
6. Conform records to nuclide-asset-schema; register in `visor` manifest.
7. Wire into the chain at the aimap seam; add the reclassify path.
8. Exclusion bloom (BF-B), rebuilt-from-CAS, only when the SQLite lookup hurts.
9. Future: BARE-encode (`bare --encode`, MiniLM 384-dim) near-duplicate clustering for FPs that do not hash-collide.

---

## 14. Resolved decisions

- **Language: Go.** Matches the arsenal; single binary; VisorLog's inverse, shares shape.
- **Name: VisorCAS.** Foregrounds Content Addressable Storage.
- **Hash: blake3** (`lukechampine.com/blake3`), over canonical-JSON.
- **Dashboard: headless v1.**

### BF-B, resolved by research (see RESEARCH.md)
- **Standard Bloom, rebuilt from CAS+SQLite on reclassify.** Native delete (counting/quotient/cuckoo) is redundant given an authoritative store - same pattern as LSM compaction (RocksDB/Cassandra/BigTable).
- **Sizing trivial:** n=50k, p=1% -> `m = -(n ln p)/(ln2)^2` = 479,195 bits ~= 59.9 KB, k=7. p=0.1% -> 89.9 KB, k=10.
- **k indices from one blake3** (Kirsch-Mitzenmacher double hashing): `h1=blake3[0:8]`, `h2=blake3[8:16]`, `g_i=(h1+i*h2) mod m`.
- **Rejected:** counting BF (4x memory); cuckoo (FPP 0.57-0.99 on disjoint query sets). Quotient = upgrade path only past ~5M.
- **Diagnostic:** correctly filled bloom ~50% bits set; >60% means over-capacity.

---

## 15. Reuse primitives (from the audit)

- **js-extractor** - sha256-keyed cache + `sha_to_hosts` attribution = the exact `hash -> {record, host-list}` CAS pattern; arsenal-proven.
- **pcse `trust_hash.py`** - canonical-JSON (sorted keys, fixed precision, version field) for hash stability. Adopt before blake3.
- **VisorRoam `finding.go` NewID** - the excluded-volatile-fields precedent to document our normalizer against.
- **BARE `bare --encode`** - embedded MiniLM-L6-v2, 384-dim L2-normalized vectors; cosine for near-duplicate FP clustering (future, section 13.9). Calibration: same-service near-dups expected 0.88+.
- **cortex-framework** - SKELETON/VIOLATIONS ("assumes the right to...") as a template for a citable disposition justification, not code.

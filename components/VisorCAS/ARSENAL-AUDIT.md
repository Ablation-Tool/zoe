# VisorCAS - Arsenal Audit (what the full-repo review surfaced)

Method: 10 parallel agents deep-read all 43 nuclide-research repos (code, schemas, tests, data), scoped to "what bears on VisorCAS and what was overlooked." This is the synthesis.

---

## The headline: VisorCAS already has a predecessor - `winnow`

`winnow` (Python, v0.1.0) is a stateless false-positive screener. It normalizes scanner output (menlohunt + aimap adapters) to a flat candidate model `{scanner, host, port, check, severity, title, url, evidence}`, runs it through 7 codified-Insight signatures, and tags each `PASS` / `REFUTED` / `DOWNGRADE`. No persistence, no dedup, no content addressing. `sentinel` already calls `winnow_screen()` between aimap and visorlog.

**VisorCAS is the content-addressed, persistent, multi-disposition evolution of winnow.** Implications:
- winnow's 7 signatures are VisorCAS's seed corpus, and its 3-verdict scheme is the predecessor of our 5-value disposition.
- VisorCAS does not replace winnow conceptually; it makes winnow's verdicts durable, deduplicated, and cross-survey. Near-term, VisorCAS can *consume* winnow output (REFUTED -> ledger entry with disposition derived from which signature fired).
- winnow's 7 signatures (winnow.py:228-303): gcp-metadata-html (REFUTED), metadata-endpoint-html (REFUTED), firebase-name-from-hostname-label (REFUTED), gcs-name-from-hostname-label (REFUTED), port-open-inflated (DOWNGRADE), metabase-setup-token-null (REFUTED), vllm-completions-405 (DOWNGRADE).

---

## The canonical record format - `nuclide-asset-schema` (conform to it)

JSON Schema 2020-12, **v1.1.0**, the universal interop contract. VisorCAS records should align where possible rather than invent a parallel shape.
- Root required: `schema_version` (const "1.1.0"), `asset`, `source` (req `tool`), `timestamp`.
- `asset`: oneOf `{ip,port}` | `{onion_address}`; optional scheme/hostnames/asn.
- `services[]`: name(req), version, banner, **fingerprint** (which rule fired), `deep_enum` (open blob), ports_observed.
- `classification`: `category` enum **includes honeypot**; `confidence` low/med/high; `ethics_flags` (closed enum - lacks GDPR/FERPA, a bug); sector.
- `findings[]`: rule_id(req), severity(req), title, evidence, tags, cve, `tier_label_basis`.
- `lifecycle`: status open/disclosed/acknowledged/remediated/verified.
- `raw`: open passthrough.
- **No FP/disposition field exists** anywhere in the schema. VisorCAS owns its own FP record schema, but should: emit the `findings[]` shape, use `raw` to carry disposition+blake3, and conform `asset`/`classification`. Propose adding `findings[].disposition` upstream later.
- Bug found: `examples/sub2api-setup-open.json` declares schema_version 1.0.0 but schema requires const 1.1.0 - will fail `visor validate`.

---

## Disposition taxonomy - REVISED from the data

The 5-value model is too coarse. The audit forces these refinements:

| Disposition | Meaning | Insight basis |
|---|---|---|
| `misidentification` | wrong service entirely | #6, #7, #15, #26, #52 |
| `transient-artifact` | crawl-time / timing / rotating-title mismatch | #51, #32 |
| `auth-on` | service present, data layer gated | #16, #25, #47, #65, #70 |
| `deception` | honeypot fleet | #1, #22, #30, #32 |
| `tool-bug` | scanner logic error / unconditional hardcoded CVE | #6; aimap hardcoded CVEs |
| **`wrong-surface-class` (NEW)** | correct fingerprint, wrong surface (Docker/K8s/etcd substrate, not the AI service) | VisorRoam `classify.IsSubstrate()` |

Plus a **3-way auth state**, not binary (Insight #16, #70 - "a 200 is identity, the decoder is auth-state"):
- `UNAUTH` = verified unauth (aimap `auth_status:"none"` + data-layer probe)
- `AUTH-UNKNOWN` = surface open, auth NOT verified (aimap `auth_status:"unknown"`) - must NOT be treated as either a finding or an FP
- `AUTH` = verified protected

**Hard guard (Insight #25):** a Tier-C (auth-on-default) platform returning 0 unauth is a CONFIRMED result, not a false positive. VisorCAS must never disposition these as FP. Tier comes from `aimap-profile` (chain Step 3).

Optional 7th: `unverified-cve` for aimap's unconditional CVE emissions (Flowise CVE-2024-36420, MLflow CVE-2024-37052+ fire on service identity alone) - or fold into `tool-bug`.

---

## Dedup key - CORRECTED

Do NOT hash the raw HTTP body. `body_snippet` (aimap) is truncated and carries timestamps/version strings that break dedup. Do NOT use `notes` (it embeds the host IP -> defeats cross-host dedup).

**Hash the structured service identity:** `blake3( service_class + port_class + auth_status_normalized + sorted(categories) )` from `enum_results`. Precedent:
- VisorRoam `finding.go:65` - `NewID = sha256(ip|port|service|choke_point)` deliberately EXCLUDES banner/body/model-list so benign variance does not mint a duplicate. Document our exclusion list the same way.
- pcse `trust_hash.py:80-124` - canonical JSON (sorted keys, fixed float precision, version field) for hash stability across equivalent inputs. Adopt this canonicalization before blake3.
- js-extractor - sha256-keyed cache + `sha_to_hosts` attribution map is the exact `hash -> {record, host-list}` pattern we built; confirms the CAS primitive is arsenal-proven.

This means our normalizer should key on aimap's structured `enum_results` fields, not `body_shape`, for the production path.

---

## Placement - CONFIRMED (and sharpened)

The chain (`visor-chain-runner.sh`): `... 1b aimap -> aimap-report.json -> 6 aimap-to-findings.py -> findings.ndjson -> visorlog ingest ...`.

VisorCAS sits at the **aimap-report.json seam**, between Step 1b and Step 6 - richer than the post-conversion seam winnow uses (it still has `enum_results.auth_status`, `risk_level`, `findings[]`). winnow currently runs at the post-NDJSON seam in sentinel; VisorCAS should run earlier and can subsume winnow's role.

```
aimap-report.json
   -> VisorCAS: normalize (structured fields) -> blake3 -> dedup + screen known FPs + disposition
   -> survivors to aimap-to-findings.py -> visorlog ingest (nuclide.db, true positives)
   -> FPs to VisorCAS corpus (the negative ledger)
```

Plus a **reclassify/reopen path** (not just pre-ingest screening): `cat32-severity-correction.py` shows real post-hoc correction (one-api/new-api downgraded after default-cred probe returned 0/40). VisorCAS must support reclassifying existing entries -> rebuild the exclusion view. Our SPEC's "reclassify in index, rebuild bloom" already supports this; it is confirmed necessary.

---

## Per-tool relevance (one line each)

**Sources (produce observations VisorCAS ingests):**
- aimap - PRIMARY. ScanReport JSON; `enum_results[].auth_status` is the verified-auth field. Has built-in FP controls (body_not_contains, conjunctive) and documented FP-prone fingerprints (CVAT request-header gap, Flowise, Doccano/Label-Studio collision, Zep/Letta, kubelet "ok").
- tiptoe - richest single-host: `probe.state` = VERIFIED_UNAUTH / VERIFIED_AUTH (only tool with first-class active auth verdict); `evidence` body fragment; tentative-match already self-classified as misidentification.
- VisorGoose - active-verified Ollama (version, model system_prompt, CVE-2025-63389 unauth-write, takeover URL); `source` field tags ctlogs vs shodan.
- VisorBishop - 5-value AuthState (unauth/auth/info-leak/mixed/unknown) + IP-direct-shadow 27-port sweep. Note: bridge only emits binary UNAUTH tag; info-leak/mixed only survive in `raw.auth_state` - VisorCAS must parse raw.
- VisorGraph - cert/service/domain graph; `Finding.Confidence` + `Finding.Source` (dropped after ingest - capture at ingest); `sandbox.IsResponseCanned()` = ready-made deception/transient hook; `l7.BodySHA256` exists but is dead code.
- VisorSD - raw Shodan `data` banner exists in SearchMatch but dropped before output; `component` = pre-classified platform.
- JAXEN - empire.db assets (ip,port,product,version,favicon_hash); no banner, no auth-state; `--clean` is org-name CDN filter only.
- shodan-fetch - raw `banner`, `ssl.subject_cn`, facet distributions (`http.status:401` 90% = population-level auth-on prior).
- nu-recon / nuclide-atlas / SubKu / osint-platoon - additional source shapes; atlas container->deployment promotion = systematic transient-artifact source; osint-platoon `dead_space[]` = FP precursor; SubKu binary OPEN/secured probe results are verification-grade.

**Consume (verified disposition signals):**
- VisorScuba - `unauth_verified` bool (from UNAUTH tag) gates BLUE-AUTH-001; the verified-unauth signal VisorCAS reads. No FP/dedup of its own; re-fires on every open event (VisorCAS is the missing pre-filter).
- aimap-profile - platform tier + honeypot classification + ethics flags (Step 3, before ledger).

**Overlap / coordinate:**
- winnow - predecessor (above).
- VisorRoam - internal SIEM; CANDIDATE vs VERIFIED maturity axis = our disposition's positive mirror; `inventory.assets(auth_state, maturity, substrate)` + `Diff()` detecting auth_state_change. COORDINATE hash schemes (its sha256-on-identity vs our blake3-on-content). Consider extending its inventory schema rather than a parallel store.
- pharos / sentinel / VisorRAG / VisorPlus - all inherit aimap FPs with no screen; all lack content-addressed dedup; all are downstream consumers that VisorCAS protects.

**Reuse (primitives):**
- BARE - embedded MiniLM-L6-v2; `bare --encode` -> 384-dim L2-normalized vector; cosine for NEAR-duplicate FP clustering (exact hash misses near-dups). Calibration: novel AI-infra classes score 0.42-0.54 vs MSF corpus; same-service near-dups expected 0.88+.
- cortex-framework - SKELETON (what it does) / VIOLATIONS ("assumes the right to...") maps to auth-on; a design template for a citable disposition justification, not code.
- pcse trust_hash.py - canonical-JSON hashing pattern.

**Out of scope:** VisorHollow (Windows), allium (Tor census), VisorAgent (ethical-stop), VisorCorpus (LLM payloads), warrant/oreilly-reader-skill/safety-stream/osint-handbook(-2026)/api-god(-x) (unrelated).

**Register:** add VisorCAS as the 16th ToolSpec in `visor/internal/manifest/manifest.go`; it becomes a new AI-ASM pillar ("Screen / FP disposition", with winnow).

---

## Recommended SPEC changes

1. Reframe VisorCAS explicitly as winnow's successor; seed corpus = winnow's 7 signatures + the ~18 FP/verification Insights (mapping above).
2. Placement: aimap-report.json seam (already corrected last revision) - now confirmed and sharpened with the winnow relationship.
3. Disposition: add `wrong-surface-class`; add the 3-way auth state (UNAUTH / AUTH-UNKNOWN / AUTH); add the Tier-C-zero guard; decide on `unverified-cve`.
4. Normalizer/dedup: key the production fingerprint on structured `enum_results` fields, not `body_shape`; document the excluded-volatile-fields list (VisorRoam precedent); adopt pcse canonical-JSON before blake3.
5. Conform records to nuclide-asset-schema (findings[] shape, raw passthrough, classification/lifecycle); plan a `findings[].disposition` upstream proposal.
6. Coordinate the hash scheme with VisorRoam; evaluate extending its inventory schema vs a parallel store.
7. Production adapter: `adapters.AimapReport` (aimap-report.json -> observations, auth_status -> 3-way disposition). The ShodanResults adapter stays as a test/secondary source.
8. Future: BARE-encode near-duplicate clustering for FPs that do not hash-collide.
9. Honeypot: load AS63949 fleet IPs + salt `wW0sffoqsk.EM` (in memory, not in any repo) as a secondary net; protocol-strict conformance (Insight #1) is the primary discriminator.

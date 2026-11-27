# AvailGate FORGE / SAFE CODE audit — 2026-10-11

Source: `/home/cowboy/bin/availgate`  
SHA-256: `fdc20766db75de4b74c25d61f992f7d91d3abadcf8821566e802e5ecc1123530`  
FORGE source scan: 1 Python file, 0 pattern findings, gate passed.  
FORGE module review: **passed**, 0 open findings.  
Verification: syntax compilation; 16 offline unit/system tests; live DuckDuckGo and Bing query (10 and 20 hits); live vetted-IP fetch of `https://example.com` (171 characters). CLI help wording was then corrected and the offline suite rerun.

## 1. Scope & Assumptions

Reviewed the single-file Python CLI, including engine adapters, GHDB augmentation, ranking, SQLite cache, full-page fetch, concurrency, output, and command parsing. AvailGate aggregates search results and optionally fetches returned pages for ranking.

- Assumption: Users may search for and fetch results on domains they do not control.
- Assumption: `--fetch` is intended to work with arbitrary public search hits.
- Unknown: production proxy configuration, traffic volume, and behavior of every external search API.
- Unknown: whether the fetched page content or result ranking is subsequently treated as a security decision by another tool.

## 2. Functional Correctness Assessment

Confirmed and fixed: Yandex XML leaf values were silently discarded; dork operators lost their values; duplicate hits from one engine could overwrite the best rank; URL normalization collapsed case-sensitive paths and queries; cache entries collided across `--top`, `-n`, `--weights`, `--no-semantic`, and GHDB corpus changes; `--fetch` could misorder the final list and use different scoring weights on a cache hit; `--clear-cache` required an irrelevant query. Each has a regression check in `tests/test_availgate.py`.

No further functional defect was confirmed in the reviewed code.

## 3. Operational Safety & Failure Modes

**Resolved AG-01 — vetted-IP fetch.** `_public_fetch_target` rejects private/non-HTTP destinations, resolves once, and `_fetch_body` opens the connection directly to the vetted public IP. It retains the original Host header and HTTPS verification name; every redirect is resolved and checked again. The fetch no longer uses an independently resolving proxy. Offline tests cover a changing DNS answer, direct IPv4/IPv6 loopback, and redirects to private addresses. A live HTTPS fetch returned the expected page text.

Page bodies are capped at 2 MiB, a per-page deadline is checked while streaming, and responses are released. No significant operational safety issue was confirmed after the repair.

## 4. Reliability & Resilience Issues

**Resolved AG-02 — bounded health check.** `run_health_check` uses daemon workers and a total 30-second join deadline; unfinished engines report FAIL. A slow-worker test confirms the command returns after the configured limit. Search adapters retain individual HTTP timeouts and report hit counts. A live two-engine query returned results from both DuckDuckGo and Bing.

## 5. Performance & Resource Use Considerations

Fetch body memory is capped; the regression suite exercises the over-limit case. GHDB BM25 still scans the local corpus and can be costly for a very large input, but the visible corpus has a warning above 50,000 entries and no measured performance failure was observed. No new performance action is asserted without a representative load measurement.

## 6. Maintainability & Operability Observations

The single executable contains all engine adapters and ranking logic, but functions are separated clearly enough for targeted tests. The newly added tests exercise code by loading the extensionless script. FORGE's source scanner requires a `.py` file and was run through a temporary symlink; it did not modify the executable.

No additional maintainability change is required by the observed behavior.

## 7. Data Integrity & Consistency Risks

**Resolved AG-03 — backend-aware cache identity.** `_cache_key` now includes the SearXNG endpoint, Brave API mode, proxy route, ranking options, result count, and GHDB corpus stamp. A configuration-change test verifies a different key. SQLite writes use a transaction and connections are closed; a cache round-trip test passes.

## 8. Testing & Verification Suggestions

- Completed: 16 offline tests cover the confirmed correctness bugs, fetch trust boundary, cache round trip, and bounded health command.
- Completed: live two-engine search and live HTTPS fetch; syntax compilation and FORGE source scan passed.
- Further confidence work: exercise all optional keyed engines and a configured proxy in their actual deployment environment. These configurations were unavailable in this audit.

## 9. Exhaustive Production Readiness Checklist

1. [x] Bind `--fetch` connections to vetted public addresses and pass rebinding/redirect tests. Source: §3 AG-01. Effort: High.
2. [x] Bound `--health` process completion and pass a slow-engine test. Source: §4 AG-02. Effort: Medium.
3. [x] Add backend configuration to the cache key and pass configuration-change tests. Source: §7 AG-03. Effort: Low.

## 10. Residual Risk & Limitations

The assessment is based on the visible local script and the tests listed above. The FORGE module gate and all audit checklist items pass. The live checks covered DuckDuckGo, Bing, and one public HTTPS page; optional keyed engines, custom SearXNG, and real proxy deployment were not exercised. `--fetch` intentionally bypasses `AVAILGATE_PROXY` so the vetted-IP boundary remains intact. A real hostile DNS service was not used; the rebinding sequence was simulated at the resolver boundary. Ranking uses a heuristic URL trust score and should not be treated as proof that a page is safe.

## DEV & TEST ORCHESTRATION PLAN (ADDITIVE)

### A. Dev Work Items by Category

#### A.1 Functional Corrections

No additional items in this category based on the visible code.

#### A.2 Operational Safety Improvements

No additional items in this category based on the visible code; AG-01 is resolved.

#### A.3 Reliability & Resilience Enhancements

No additional items in this category based on the visible code; AG-02 is resolved.

#### A.4 Performance & Resource Tuning

No additional items in this category based on the visible code.

#### A.5 Maintainability & Operability Refactors

No additional items in this category based on the visible code; AG-03 is resolved.

### B. Test Plan by Level

#### B.1 Unit Tests

- Target: fetch URL validation and connector. Scenarios passed: direct private IPv4/IPv6, redirect to loopback, changed DNS answer, oversized body. Expected: no private connection and bounded read. Source: AG-01.
- Target: cache key and cache store. Scenarios passed: option and backend configuration changes, SQLite round trip. Expected: distinct identity and correct retrieved payload. Source: AG-03.
- Target: Yandex, dork operators, URL canonicalization, duplicate ranks, fetched-result sorting. Scenarios passed: leaf XML, operator values, path case, repeated rank, updated scores. Expected: stable correct result. Source: §2.

#### B.2 Integration Tests

- Interaction: vetted-IP connector and public HTTPS page. Happy path passed: `https://example.com` returned page text with TLS hostname verification. Failure path passed offline: changed DNS answer and redirect to loopback did not connect privately. Source: AG-01.
- Interaction: health command and delayed engine adapter. Failure path passed: command returned within the configured total deadline with explicit FAIL status. Source: AG-02.

#### B.3 End-to-End (E2E) / System Tests

- Flow: GHDB-only CLI query. Steps passed: load a temporary corpus, rank a dork, emit JSON. Success: one GHDB result and exit 0. Edge: missing network engines are irrelevant in this mode.
- Flow: live two-engine search. Steps passed: query DuckDuckGo and Bing, aggregate and emit JSON. Success: both adapters returned hits and CLI exited 0. Edge: this live check used `--no-cache`; cache behavior was covered separately by unit tests.

#### B.4 Non-Functional Tests

- Test type: failure injection. Target: `--health` with delayed workers. Condition: adapters exceed a shortened test deadline. Metric: command duration. Pass: bounded return and failure status. Source: AG-02.
- Test type: oversized response. Target: `--fetch` streaming. Condition: body exceeds 2 MiB. Metric: returned body length. Pass: empty result and closed response. Source: §3 fetch safety.

#### B.5 Tooling Support (Generic)

- Tool category: offline unit/system runner with mocked resolver and connection pool. Purpose: reproduce AG-01–03 without contacting private services.
- Tool category: syntax checker and FORGE source/module gate. Purpose: catch syntax regressions and review remaining findings.

### C. Implementation Order & Dependencies

#### C.1 Suggested Implementation Order

1. Completed vetted-address connection and rebinding tests (B.1–B.2).
2. Completed bounded health command and slow-worker test (B.2, B.4).
3. Completed backend-aware cache identity and round-trip tests (B.1).
4. Completed offline suite, live multi-engine check, and FORGE source scan (B.3–B.5).

#### C.2 Key Dependencies / Pre-Conditions

No remaining implementation dependencies for the audited source.

### D. Minimal “Safe-to-Run” Gate

#### D.1 Critical DEV Changes Required Before Running

Completed: `--fetch` connects only to the vetted public IP for each request. Source: AG-01.

#### D.2 Critical Tests That Must Exist and Pass

Passed: resolver-change test verifies the connection uses the first vetted public IP and never re-resolves it. Reason: AG-01.
Passed: direct IPv4/IPv6 loopback and redirect-to-loopback tests. Reason: AG-01.
Passed: live public HTTPS fetch with original hostname verification. Reason: AG-01.

### E. Ongoing DEV/TEST Guardrails

#### E.1 Coding Practices to Maintain

- Practice: finite network timeouts and per-engine error reporting. Benefit: limits failures and makes partial results visible.
- Practice: preserve original URL path/query case in deduplication. Benefit: prevents merging distinct pages.

#### E.2 Regression Risks to Watch

- Area: `--fetch`. Risk pattern: new redirect or proxy path bypasses public-address checks. Mitigation: apply the same trust boundary to every connection.
- Area: cache identity. Risk pattern: new result-affecting option is absent from the key. Mitigation: add a cache-key test with each option.

#### E.3 Automation Hooks

- Hook type: run unit/system suite and compile check. Trigger: each AvailGate source change. Risk: regressions in the confirmed bugs and AG-01–03.
- Hook type: rerun FORGE source and module audit. Trigger: before releasing a changed executable. Risk: new high-severity defects.

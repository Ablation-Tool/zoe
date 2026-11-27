# AvailGate standalone research tool — build plan

Status: 0.2.0 initial standalone build implemented and locally verified.
Packaging, modern response contracts, bounded provider workers, source reading,
query modes, and saved sessions are available. The clean wheel installation
passes 37 offline tests on Linux/Python 3.14; live DDG/Bing search and an HTTPS
source read succeeded. See RELEASE-0.2.0.md for the verification record.

The complete roadmap is not yet accepted: human relevance evaluation,
provider-side date filters, broader provider fixture coverage, and execution of
the cross-platform CI matrix remain follow-ups. Query modes are implemented as
transparent templates; their ranking-quality benefit is not yet validated.

## Product goal

A user asks a coding agent to research a topic with AvailGate. The agent uses AvailGate to discover pages, read selected sources, preserve evidence, and resume earlier research. The agent interprets the evidence and writes the answer.

AvailGate is independently installable and usable from any project. It requires neither Ablation nor an LLM account. Codex and Claude Code call the same CLI; other agents can use that CLI or the Python API.

Example user request:

> Use AvailGate to research self-hosted search engines. Find the official documentation and repositories, compare maintenance requirements, and save the sources and open questions so we can continue later.

## Current baseline

Inspected on 2026-10-11:

- The implementation is the extensionless Python script `/home/cowboy/bin/availgate`; this project contains documentation and 16 regression tests. This directory is not currently a Git repository.
- Search supports multiple providers, concurrent collection, URL aggregation, weighted ranking, optional semantic scoring, profiles, GHDB integration, and SQLite caching.
- `--json` emits a result array. Provider errors and cache information appear on stderr; an empty result set exits before JSON is emitted.
- Several adapters flatten failures into empty results, so structured diagnostics require changes inside the adapters.
- `--fetch` reads bounded public pages and uses their text for ranking. It does not expose a reusable source document. Fetch failures return empty text.
- Tests load the executable from a fixed machine path. Configuration, cache, and optional corpus defaults also assume the current layout.
- Existing fetch protections include vetted-IP connections, hostname verification, redirect checks, and size limits. Preserve these through the refactor.

## Scope and design decisions

Build a local Python package with a CLI entry point, a small importable API, and optional agent instructions. Keep semantic dependencies optional. Basic installation and ordinary search must not trigger a model download.

The agent chooses research questions and synthesizes answers. AvailGate provides bounded, inspectable operations: `search`, `read`, and session management. Research modes produce transparent query variants and ranking choices; they do not require an embedded autonomous agent.

For the first usable release, support search and HTML/plain-text reading with structured results. Add saved sessions and research modes in later milestones. Defer browser rendering, authenticated browsing, PDF/OCR extraction, a hosted service, a GUI, scheduled monitoring, and an MCP server.

Retain existing search adapters, profiles, and optional GHDB behavior during migration. Identify GHDB entries as `query_template` results so readers do not treat them as fetched web pages.

## Proposed command surface

These commands describe the implemented 0.2.0 interface. See RESEARCH-CLI.md for
current limits and remaining differences from the full plan.

```bash
availgate search "SearXNG deployment documentation" --json
availgate search "SearXNG deployment documentation" --mode docs --json
availgate search "SearXNG release changes" --mode recent --no-cache --json
availgate read "https://example.org/documentation" --json
availgate session create "search-engine-review" --json
availgate search "self-hosted search engines" --session search-engine-review --json
availgate read "https://example.org/documentation" --session search-engine-review --json
availgate session show search-engine-review --json
availgate session note search-engine-review "Compare upgrade procedures next."
availgate session export search-engine-review --format markdown
availgate capabilities --json
availgate doctor --json
```

`capabilities` reports the installed version, schema versions, commands, and available features without network access. `doctor` checks local installation and configuration; an explicit `--network` enables provider probes.

Keep the legacy `availgate --json "QUERY"` array format during the compatibility period. New subcommands use the versioned envelope. Reserve subcommand names explicitly and document `availgate search -- "QUERY"` for queries that resemble flags or command names. Preserve old health/cache flags as aliases and test their behavior. Any unavoidable legacy parsing ambiguity must be documented before release.

## Response contract

Design this before splitting implementation modules. Publish JSON schemas and example fixtures alongside the code.

Search responses include:

- `schema_version`, `operation`, `request_id`, and `status`.
- Original query, generated variants, selected mode, effective options, and applied limits.
- Start/completion timestamps and elapsed time.
- Cache hit/miss, original retrieval time, age, and expiry. Reading a cache entry must not make old observations look newly retrieved.
- Provider outcomes per query: success, empty, timeout, rate-limited, unavailable, or error; duration, hit count, and sanitized diagnostics.
- Results with an identifier, kind, URL, title, snippet, provider provenance, score components, and explanations.
- Warnings and structured errors, including whether a limit truncated the operation.

Read responses include the requested and final URLs, redirect provenance, retrieval time, content type, title, extracted text, text hash, extractor version, and truncation status. Keep publication/modification dates separate from retrieval time; missing or uncertain dates stay explicitly unknown. Cite excerpts using document identifiers and offsets into the stored extracted text, with a defined offset convention.

Define operation status independently from whether matches exist:

| Status | Meaning | Proposed new-command exit code |
| --- | --- | --- |
| `ok` | Requested work completed; a successful search can have zero results. | 0 |
| `partial` | Some work completed, but a provider or requested step failed or hit a limit. | 0 |
| `error` | No requested work could be completed. | 1 |
| Invalid input/configuration | Request could not start; return a structured diagnostic in JSON mode. | 2 |

Agents must inspect `status`, provider outcomes, and warnings even after exit 0. A successful empty provider response counts as completed work; all providers failing is an error. Machine mode emits exactly one JSON document on stdout, including expected failure paths. Human progress remains on stderr. Legacy invocation keeps its documented output and exit behavior during migration.

## Milestone 1 — portable package and reliable search

Deliverables:

- Establish the source tree in this project, with `pyproject.toml`, `src/availgate/`, an installed executable, version metadata, and declared direct dependencies.
- Use modules for CLI, contracts, configuration, providers, search orchestration, ranking, and storage. Move the existing implementation incrementally.
- Replace machine-specific test imports and runtime paths. Use platform-appropriate directories with explicit path overrides for configuration and data.
- Specify new configuration precedence: command line, environment, configuration file, defaults. Detect legacy configuration and document its differing precedence; preserve legacy behavior until explicitly migrated. Never silently discard the existing cache or configuration.
- Implement the versioned response contract and typed provider outcomes at adapter boundaries.
- Bound overall duration, provider requests, retries, concurrency, and response sizes. Honor provider retry guidance within the budget. Ensure a hung adapter cannot keep the CLI alive beyond the advertised deadline; selecting an enforceable worker strategy is part of this milestone.
- Provide `capabilities`, local `doctor`, and network probes. Preserve the existing CLI and scoring behavior through the migration.

Acceptance:

- Installation into a clean environment works from an unrelated working directory with no `/home/cowboy` references and no semantic-model download.
- Existing regression checks pass against the package; new contract tests cover successful, empty, partial, timed-out, and entirely failed searches.
- Representative provider fixtures exercise actual parsing and error mapping. Missing credentials or dependencies are explicit outcomes.
- Process-level tests confirm total deadline enforcement, bounded retries, clean JSON stdout, and no credential values in diagnostics.
- Recorded ranking fixtures retain their expected results unless a deliberate behavior change is documented.

## Milestone 2 — reusable source reading

Deliverables:

- Refactor the existing fetch boundary into a structured reader, shared by `read` and legacy fetch augmentation.
- Support HTML and plain text. Preserve headings, paragraphs, lists, and code blocks well enough for documentation use; remove common navigation noise.
- Return source metadata, extracted text, useful error categories, and explicit limits. Unsupported content types are reported honestly.
- Cache source documents separately from search results, with retrieval timestamps and explicit refresh behavior.
- Expose text limits and excerpts anchored to the captured source. Preserve the relationship between excerpt, extracted text, and URL.
- Document transport behavior. Existing direct fetching bypasses the search proxy; the new reader must make this visible and support refusing direct reads when proxy-only operation is requested.

Acceptance:

- Fixtures cover documentation, repository pages, plain text, encodings, missing dates, redirects, extraction failures, and unsupported formats.
- Existing public-address, DNS rebinding, redirect, TLS, and body-limit checks still pass. Cover compressed-body limits and total read deadlines.
- Report requested URL, final URL, original retrieval time, and truncation accurately, including cached reads.
- Excerpts resolve exactly to the saved text. Source text is returned as external data, never executed or treated as agent instructions.

**First usable release:** Milestones 1 and 2 provide portable, observable search and source reading. Agents can complete useful research without sessions or modes.

## Milestone 3 — research modes and ranking explanations

Deliverables:

- Add `general`, `docs`, `repository`, `compare`, and `recent` modes. Keep these task intentions distinct from existing ranking profiles such as `infra` and `content`.
- Use bounded, deterministic query templates. Include generated variants and effective ranking settings in output. Preserve exact product names, versions, quoted terms, and user-specified domains.
- Add exact domain filters and supported provider date filters. Report unsupported filters and unknown dates. `--no-cache` retrieves new search observations; it does not prove that a page is recent.
- Explain existing relevance components and source attributes. Label official-source status as unknown unless supported by explicit domain configuration or recorded evidence.
- Avoid treating multiple providers as independent corroboration when they share an upstream index. Record known upstream relationships and keep agreement as a ranking signal.
- Make comparison mode collect sources across the named alternatives. The calling agent writes the comparison.

Acceptance:

- A fixed query set covers ambiguous names, version-specific docs, source repositories, recent changes, and comparisons.
- Human relevance judgments establish a baseline for top-five useful results. Mode changes must show measurable benefit on their intended queries without material regressions on general search.
- Every explanation is traceable to an actual component or recorded source attribute.
- Tests confirm domain boundaries, preserved qualifiers, query budgets, and explicit handling of unsupported date filtering.

## Milestone 4 — saved research sessions

Deliverables:

- Add create, list, show, note, and export commands backed by local SQLite storage with schema migrations.
- Link searches, provider outcomes, selected sources, captured text, and agent-authored notes/open questions to a session.
- Capture sources when explicitly read into a session. A search alone stores result metadata and snippets, not full copies of every returned page.
- Preserve successive source captures with hashes and retrieval times so refreshed pages do not overwrite earlier evidence.
- Support JSON and Markdown exports with destination links and clear distinctions between notes, snippets, and retrieved excerpts.
- Provide bounded storage, clear retention behavior, and an explicit session deletion operation. Cache eviction must not silently delete saved session evidence.

Acceptance:

- Another process or agent can reopen a session, inspect earlier research, and add work without rerunning previous searches.
- Showing and exporting a session work offline and make no network requests.
- Concurrent updates, interrupted writes, migrations, storage limits, and repeated captures preserve consistent records.
- Exports retain provenance and unresolved questions, omit credentials, and do not label an agent's note as source text.

## Milestone 5 — agent integration and release

Deliverables:

- Package reusable invocation instructions and examples for Codex, Claude Code, and generic CLI callers. Explain installation/discovery from arbitrary projects; project-local instructions alone do not provide global discovery.
- Teach agents to inspect capability versions, statuses, cache age, provenance, truncation, and source dates. Include examples for empty searches and partial provider failures.
- Keep installation of agent instructions explicit and avoid overwriting existing user instructions. Ordinary tool installation must be independently useful.
- Publish installation, configuration migration, compatibility, troubleshooting, and session documentation with runnable examples.
- Add CI checks for supported Python versions and operating systems, installation from built distribution artifacts, offline fixtures, and regression tests. Treat live provider checks as separately reported smoke tests because external availability varies.
- Document which search providers are configured or available; provide a useful keyless default when reachable without promising provider uptime.

Acceptance:

- From a clean project, an instructed agent can search, read selected sources, save a session, and resume it in another process using only the documented CLI.
- Installation and CLI checks pass on Linux, macOS, and Windows before advertising support for each platform; otherwise state the supported subset.
- Legacy examples still work or have an explicit migration path.
- The release records known limitations and separates offline test results from observed live-provider behavior.

## Development and verification loop

For each milestone: develop a small change, inspect it, run focused unit checks, run the relevant CLI/system flow, fix findings, and repeat before release. Turn confirmed defects into meaningful regressions. The earlier FORGE / SAFE CODE review remains historical evidence for the original script; it does not certify new code or create a runtime dependency on Ablation.

Prioritize contract tests, provider fixtures, process deadlines, fetch boundary checks, migration checks, and saved-evidence integrity. Test representative failure paths as well as successful research flows. Use live searches to assess operational health, not as the sole correctness test.

Track startup time, search latency, read latency, partial-failure rates, and cache behavior. Establish baselines during Milestone 1, then set supported performance budgets from those measurements.

## Implementation order and first build slice

Dependency order: response contract and portable package → reliable search → structured reading → modes/explanations → sessions → agent integration and release. Draft agent examples as each command lands; final release integration can overlap the later milestones.

Begin with one reviewable slice:

1. Establish package ownership of the current source and migrate the regression harness.
2. Define search/provider contracts and fixtures, including partial and empty responses.
3. Expose the existing search through the new `search` command while preserving legacy invocation.
4. Build and install into an isolated environment, verify fixtures and CLI compatibility, and document the new interface.
5. Switch the everyday executable to the packaged entry point only after the migration checks pass, retaining a recoverable copy of the original.

The final product is ready when the example research task can move from natural-language request to cited sources and a resumable session, from an arbitrary project, using the documented CLI with observable failures and no dependency on Ablation.

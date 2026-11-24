# Modern CLI and migration — 0.2.0

## Commands

| Command | Purpose |
| --- | --- |
| `search QUERY` | Search providers, aggregate URLs, and explain ranking. |
| `read URL` | Capture public HTML/plain text with provenance. |
| `session create/list/show/note/question/export/delete` | Save, inspect, resume, and export local research. |
| `capabilities` | Report commands/features/version without network or storage initialization. |
| `doctor` | Check local dependencies/configuration; `--network` opts into live provider probes. |
| `cache clear` | Clear only the modern search/document cache, preserving sessions. |
| `agent-guide` | Print portable agent instructions without modifying any configuration. |

All commands support `--json`; session commands accept it after the action. JSON mode emits a single response document. Human progress is written to stderr. `--help` displays usage rather than JSON.

## Search options

`--engines ddg,bing` explicitly selects providers. Available adapters: ddg, bing, brave, searxng, google, serper, yandex, mojeek, ghdb. Defaults use the four keyless web adapters plus configured API adapters. Google takes precedence over Serper in automatic selection because they share an upstream index. Explicit GHDB configuration adds the local corpus; `--ghdb-path PATH` overrides it.

`--mode` selects general/docs/repository/compare/recent. Docs, repository, and recent modes add two transparent query suffixes. Compare accepts up to two `--alternative` values. Modes preserve the original query and do not generate an answer. The agent evaluates sources and writes the comparison. `--profile infra|content` independently selects existing ranking weights.

`--domain HOST` filters exact hostnames and adds search operators; repeat up to ten times. Subdomains are not implicitly included. `--official-domain HOST` records the user's designation in results; it is not an authenticity check and does not change the score.

`--since YYYY-MM-DD` filters reported source dates locally, excluding unknown/unparseable dates. Provider-side date filters are not implemented. Recent mode and `--no-cache` do not establish a page's publication date.

Limits: `--top` 1–100 (default 10), `--results` per provider/query 1–50 (default 20), at most three query variants, four concurrent provider workers, and `--timeout` 0.1–300 seconds (default 30). Each requests-backed provider/query permits five requests with a 2 MiB decoded response cap and no automatic retries. DDG uses its own transport: internal counts/response caps are not observable; its process is bounded by the deadline. Provider redirects are rejected by the modern requests transport and reported as failures.

One worker handles a provider's query variants serially. A terminated worker's unfinished batch is reported as timed out, even if an earlier variant had progressed. Completed providers still return results. Cleanup and local ranking add small overhead after the worker budget. Old query/flags invocation retains its original threading and limits.

`--no-semantic` is accepted for compatibility; modern search always uses nonsemantic ranking. Legacy invocation still supports optional semantic scoring and dork augmentation.

## Source reading

`read URL` accepts HTTP(S) without embedded credentials. Every connection and redirect resolves only to public IPs, connects to a vetted address, and verifies HTTPS against the original hostname. Requests use at most five redirects, 2 MiB decoded content, and a killable worker deadline.

`--max-chars` defaults to 40000 and accepts 1–200000 Unicode code points. Truncated text produces `partial` status. Excerpt offsets are zero-based, end-exclusive Unicode code-point positions into the exact returned text. The initial excerpt is the first 1000 code points; the agent can select other passages using the full text. Hashes cover extracted text, not raw response bytes. Dates from metadata and HTTP Last-Modified remain unverified source claims.

Unsupported types, empty documents, blocked destinations, HTTP errors, and network/TLS errors have explicit codes. No browser rendering, authenticated sessions, PDF, or OCR is available.

The reader uses direct connections and does not use the search proxy. `--proxy-only`, or configuration `"proxy_only": true`, allows a cached capture and refuses an uncached direct read. Search requests backed by requests use the configured proxy. DDG transport behavior depends on its library; proxy-only search guarantees are not provided by this release.

## Responses, cache, and errors

Responses use `schema_version: "1.0"`. See the bundled schema and `tests/test_research.py` for generated contract examples. Every envelope has operation/request identifiers, status, timestamps, elapsed time, warnings, and errors.

| Exit | Interpretation |
| --- | --- |
| 0 | `ok` or `partial`; inspect diagnostics before using results. |
| 1 | Operation failed. |
| 2 | Invalid arguments/configuration, missing session, or missing required deletion acknowledgement. |
| 130 | Interrupted by the user. |

Empty results from successful providers yield `ok`. All providers failing yields `error`. Provider exception text is deliberately not exposed because it can contain credentials. Requests-backed adapters report status and request counts. Search API/HTML layouts can change; empty scraped results can still reflect an upstream layout change.

Successful searches and source documents have separate cache keys and a 24-hour cache lifetime. Keys include effective settings and hashed provider configuration; raw credentials are not stored in the cache key or responses. Cached responses retain the original observation time. Failed/partial searches are not cached. `--no-cache` bypasses cache reads and writes. Session capture is independent of caching.

Session-bound operations return `persistence.saved`. If saving fails after a completed operation, useful results remain in the response with a warning and partial status. Save that response before retrying. A missing session is detected before network access.

## Storage and sessions

Session names use 1–80 letters, digits, dots, dashes, or underscores, beginning with a letter or digit. Notes and questions are explicitly marked agent/user authored. Reads append captured text and provenance; ordinary searches save result metadata and snippets only. Source captures are never overwritten by refreshes.

`session show`, `list`, and `export` are local operations. JSON export preserves the complete event data. Markdown export is a readable report containing queries, unverified snippets, notes, and captured source text. It is not a complete replacement for JSON diagnostics.

Storage permits up to 1000 sessions, 64 MiB of serialized session payloads, and 16 MiB of cached payloads, excluding SQLite overhead. Cache eviction removes oldest entries; session evidence requires explicit deletion. `session delete NAME --yes` permanently removes that session's records; export first if needed. Deleted SQLite pages are not securely erased. Database initialization uses schema version 1 and refuses newer versions.

## Configuration migration

Modern configuration defaults:

- Linux: `$XDG_CONFIG_HOME/availgate/config.json` and `$XDG_DATA_HOME/availgate/research.sqlite3`, falling back to `~/.config` and `~/.local/share`.
- macOS: `~/Library/Application Support/AvailGate/`.
- Windows: `%APPDATA%/AvailGate/config.json` and `%LOCALAPPDATA%/AvailGate/research.sqlite3`.

`AVAILGATE_CONFIG` selects a file; `AVAILGATE_DATA_DIR` selects the data directory. An explicitly configured missing/invalid file fails clearly. Modern precedence is CLI options > environment > file > defaults. If the default modern file is absent, `~/.availgate.json` is used with a precedence warning.

Supported legacy provider keys remain: google_api_key, google_cx, brave_api_key, serper_api_key, yandex_user, yandex_key, mojeek_api_key, searxng_url, proxy, ghdb_path. Environment names match the existing reference; modern commands additionally recognize GHDB_PATH. Configuration may set boolean proxy_only for source reads.

Legacy `availgate --json "QUERY"` retains array output, file-over-environment precedence, `~/.availgate_cache.db`, original fetch augmentation, and legacy flags. The new package preserves this implementation in `legacy.py`; hardening of modern worker deadlines does not retroactively change legacy execution. `--clear-cache` targets the legacy cache; `cache clear` targets the modern cache. Neither migrates or deletes the other's data.

Bare first tokens `search`, `read`, `session`, `capabilities`, `doctor`, `cache`, and `agent-guide` are reserved commands. Use `availgate search -- "search"` to search for a reserved token, or put legacy flags first. Put modern options before `--` when searching for flag-like text.

## Agent discovery

The executable and `agent-guide` work from any directory after installation. Project-local AGENTS.md/CLAUDE.md files apply only within their project scope. To enable discovery elsewhere, merge the printed guide or a reference into the appropriate user-controlled agent instructions. No global instruction files are changed by installation.

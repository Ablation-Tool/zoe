# Legacy CLI reference

This page describes retained query/flags invocation, implemented in
`src/availgate/legacy.py`. For the new search/read/session commands, use the
[modern CLI reference](RESEARCH-CLI.md).

```text
availgate [options] QUERY...
availgate --health
availgate --clear-cache
```

Unquoted query words are joined with spaces. Quote a multiword query when passing it through a shell script.

## Options

| Option | Behavior |
| --- | --- |
| `-n N`, `--results N` | Request up to N results per engine and per dork variant. Default: 20. N must be positive. |
| `--top N` | Return at most N ranked results. Default: 15. N must be positive. |
| `--engines LIST` | Use exactly the comma-separated engine names in LIST: `ddg,google,bing,yandex,mojeek,searxng,brave,serper,ghdb`. No spaces are trimmed. |
| `--ghdb` | Include local GHDB entries in automatic engine selection. With `--engines`, include `ghdb` in the list instead. |
| `--ghdb-path PATH` | Read a GHDB JSON corpus from PATH; overrides JSON configuration and the built-in path. |
| `--dork-augment` | Run the plain query plus up to two GHDB operator variants, if a corpus exists. |
| `--dork-k N` | Set the maximum operator variants; also turns on dork augmentation. Use a positive N. |
| `--profile infra` | Emphasize agreement and infrastructure patterns. |
| `--profile content` | Emphasize text similarity and recency. |
| `--infra` | Select the infra profile when no profile is given. With another profile, add the infrastructure component to that profile. |
| `--weights SPEC` | Override individual score weights, for example `rrf=0.5,bm25=0.3,coverage=0.2`. Values must be finite and nonnegative; effective weights are normalized to sum to one. |
| `--no-semantic` | Skip the sentence-transformer model and redistribute its weight to BM25 and rank fusion. |
| `--fetch N` | Fetch the first N ranked public pages, score their body text with BM25, and re-sort the displayed results. Default: off. |
| `--json` | Print a JSON array to stdout. |
| `--plain` | Print text blocks rather than a `rich` table. Plain text is also the fallback when `rich` is absent. |
| `--no-cache` | Bypass both reading and writing the SQLite result cache. |
| `--clear-cache` | Delete all cached result rows and exit. No query needed. |
| `--health` | Test default keyless engines plus configured Google or Serper; exit 0 if each returns at least three hits, otherwise 1. No query needed. |

`--results`, `--top`, `--fetch`, and `--dork-k` are integer options. A query that returns no hits exits 1. Search adapter errors and progress messages are written to stderr; `--json` stdout remains parseable.

## Engines and automatic selection

| Engine | Automatic use | How it searches |
| --- | --- | --- |
| `ddg` | Default | DuckDuckGo through `ddgs` or `duckduckgo_search`. |
| `bing` | Default | Bing HTML pages. |
| `brave` | Default | Brave HTML pages, or the API when `brave_api_key` is set. |
| `searxng` | Default | Configured instance first, then built-in public instances. |
| `google` | With `google_api_key` and `google_cx` | Google Programmable Search JSON API. |
| `serper` | With `serper_api_key` when Google is not configured | Serper Google proxy. |
| `yandex` | With `yandex_user` and `yandex_key` | Yandex XML API. |
| `mojeek` | With `mojeek_api_key` | Mojeek JSON API. |
| `ghdb` | When corpus exists or `--ghdb` is given | Local GHDB corpus; results link to GHDB entries. |

`--engines` replaces the automatic set. It does not add to it, so `--engines ddg` searches only DuckDuckGo even if other engines or GHDB are configured. A named engine without its required dependency or credentials can return zero hits.

The default GHDB path is `~/white-bronco/Claude-Code-GHDB/ghdb_all.json`. The corpus is a JSON array of entries with fields such as `id`, `link`, `category`, `query`, `shortDescription`, and `textualDescription`. `--ghdb` returns ranked dork entries as hits; `--dork-augment` instead derives extra web queries from relevant operators such as `inurl:` and `intitle:`. They can be used together. If no corpus exists, GHDB returns no hits and augmentation has no variants.

## Configuration keys

`~/.availgate.json` can contain these keys. Except for `ghdb_path`, each has the corresponding environment variable. JSON values override environment values when both are set.

| JSON key | Environment variable | Purpose |
| --- | --- | --- |
| `google_api_key` | `GOOGLE_API_KEY` | Google API credential. |
| `google_cx` | `GOOGLE_CX` | Programmable Search Engine ID. |
| `yandex_user` | `YANDEX_USER` | Yandex XML user. |
| `yandex_key` | `YANDEX_KEY` | Yandex XML key. |
| `mojeek_api_key` | `MOJEEK_API_KEY` | Mojeek API credential. |
| `searxng_url` | `SEARXNG_URL` | Preferred SearXNG base URL. |
| `brave_api_key` | `BRAVE_API_KEY` | Switch Brave from HTML to API mode. |
| `serper_api_key` | `SERPER_API_KEY` | Serper API credential. |
| `proxy` | `AVAILGATE_PROXY` | Proxy for the shared search adapter sessions. |
| `ghdb_path` | — | Local GHDB corpus path; `--ghdb-path` takes precedence. |

The current `load_config()` does not read a `GHDB_PATH` environment variable. Use the CLI option or JSON key.

## Output

`--json` emits an array. Each object has this shape:

```json
{
  "url": "https://example.com/page",
  "title": "Example page",
  "snippet": "Text returned by an engine",
  "score": 0.84,
  "engines": ["ddg", "bing"],
  "ranks": {"ddg": 2, "bing": 5},
  "components": {
    "rrf": 0.9,
    "coverage": 1.0,
    "bm25": 0.8,
    "semantic": 0.5,
    "trust": 0.7,
    "freshness": 0.5,
    "infra": 0.0
  }
}
```

The numbers above illustrate the fields; they are not a real search result. `score` is the weighted ranking value. `components` gives per-signal values, including a neutral `semantic` value when semantic scoring is unavailable and an `infra` value of zero outside infra mode. The `engines` list shows which sources returned the URL, and `ranks` retains each source's best position.

## Page fetching

`--fetch N` operates after the initial search and cache lookup. It fetches at most N of the currently top-ranked pages, removes scripts and common navigation elements, scores up to 8,000 characters of extracted body text, and re-sorts the complete result list. The displayed snippet for a fetched result is the first 500 characters of that extracted text. A failed or blocked fetch leaves its original snippet available for scoring.

The fetch path accepts only HTTP(S) URLs that resolve entirely to globally routable addresses. It connects to the vetted address, keeps the original hostname for the HTTP Host header and TLS certificate check, checks each redirect, allows at most five redirects, and stops reading a body above 2 MiB. It makes direct connections and does not use `AVAILGATE_PROXY`. The fetched body and updated ranking are not stored in the search cache.

## Cache and troubleshooting

The result cache is `~/.availgate_cache.db`. Keys include the query, current day, engine set, result limits, ranking settings, GHDB corpus timestamp/size, and selected backend configuration. It is a daily keyed cache, not a scheduled purge: old rows can remain until `--clear-cache` is used.

- `no results — check engine availability / API keys`: run `--health`, choose one engine with `--engines`, and retry with `--no-cache`.
- An engine reports `0 hits`: its dependency may be missing, a public instance may be unavailable, or HTML selectors may no longer match the site.
- Semantic model startup is slow: use `--no-semantic`, or install and pre-download the optional model in the environment where AvailGate runs.
- `--fetch` leaves a snippet unchanged: the URL may be private, unresolvable, oversized, unreachable, or unable to pass HTTPS verification. Fetch errors return an empty body.
- Different options seem to return the same data: inspect stderr for `[cache] hit`; use `--no-cache` to force a new search.

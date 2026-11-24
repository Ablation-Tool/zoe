# AvailGate

AvailGate is a standalone research CLI for coding agents. Ask Codex or Claude Code to use it; the agent searches, reads selected pages, and returns useful sources. Research sessions preserve source captures, notes, and open questions across conversations.

AvailGate runs locally and has no Ablation or LLM-account dependency. Web search requires reachable providers; reading sources requires network access unless cached.

## Ask your agent

> Use AvailGate to find the official documentation and source repository for SearXNG. Read the installation instructions and cite the sources.

> Use AvailGate to compare the maintenance requirements of SearXNG and Whoogle. Save the sources and open questions in a research session.

Install the executable, then use `availgate agent-guide` for reusable instructions. Merge those instructions into your agent's chosen configuration to make AvailGate discoverable in future sessions. Installing the package does not modify agent configuration automatically.

## Install

Python 3.11 or newer is required. From this source directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
availgate capabilities --json
availgate doctor --json
```

On Windows, activate with `.venv\Scripts\Activate.ps1`. Standard Python packaging supplies the executable; there are no machine-specific paths in the package. Linux/Python 3.14 has been exercised locally; the CI matrix also targets Python 3.11, macOS, and Windows, pending execution.

Semantic ranking is optional and disabled in the modern search command. Legacy semantic scoring can be installed with `pip install ".[semantic]"`; model loading/download only happens when that feature is invoked. `.[display]` enables rich legacy output.

## Search and read

```bash
availgate search "SearXNG deployment documentation" --mode docs --json
availgate search "SearXNG release changes" --mode recent --no-cache --json
availgate read "https://example.com" --json
```

Search responses contain results, provider outcomes, effective settings, ranking explanations, and cache age. `ok` can mean a successful search with zero matches; `partial` means some requested work failed; `error` means no requested work completed. Exit code 0 includes partial results, so agents must inspect the response.

The reader returns HTML/plain-text content, requested and final URLs, retrieval time, hashes, and exact excerpt offsets. It uses direct vetted-IP connections and verifies TLS. It does not render JavaScript, extract PDFs, or use the search proxy. Use `--proxy-only` to allow cached reads while refusing direct network reads.

Research modes (`general`, `docs`, `repository`, `compare`, `recent`) generate bounded query variants. Their relevance benefit has not yet been independently evaluated. Scores describe relative relevance; source credibility and truth require examining the sources.

## Save and resume

```bash
availgate session create search-review --json
availgate search "self-hosted search maintenance" --mode compare \
  --alternative SearXNG --alternative Whoogle --session search-review --json
availgate read "https://example.com" --session search-review --json
availgate session question search-review "How are upgrades handled?"
availgate session show search-review --json
availgate session export search-review --format markdown
```

Sessions keep search responses, explicitly read source captures, and agent/user notes. Showing and exporting them works offline. Refreshes append captures; cache eviction does not remove saved evidence. Cache payloads are limited to 16 MiB and saved session payloads to 64 MiB; these are logical payload limits, excluding database overhead.

## Configuration and compatibility

Modern commands use platform-specific configuration/data directories. Override them with `AVAILGATE_CONFIG` and `AVAILGATE_DATA_DIR`. Precedence is command options, environment, configuration file, defaults. If the modern configuration file is absent, the old `~/.availgate.json` is read with a warning about the new precedence.

Legacy commands continue to work:

```bash
availgate --json --no-semantic "QUERY"
availgate --profile infra --dork-augment "QUERY"
availgate --health
availgate --clear-cache
```

Legacy JSON remains an array. The new `availgate search ... --json` uses the versioned envelope. Legacy configuration/cache paths retain their old behavior. `availgate cache clear` clears the new cache only.

See [modern CLI and migration](docs/RESEARCH-CLI.md) for options, limits, configuration, and failure handling. Existing [CLI](docs/CLI.md) and [ranking architecture](docs/ARCHITECTURE.md) documents describe the retained legacy interface.

## Development and verification

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m build --no-isolation
```

Offline tests exercise the original regressions plus provider diagnostics, schemas, deadlines, reading, session persistence, and compatibility. Live provider smoke checks are separate because external services can fail or change.

- [Build plan and progress](docs/BUILD-PLAN.md)
- [0.2.0 build and verification record](docs/RELEASE-0.2.0.md)
- [Modern CLI and migration](docs/RESEARCH-CLI.md)
- [Agent guide](src/availgate/resources/AGENT-GUIDE.md)
- [Response schema](src/availgate/resources/response.schema.json)
- [Development architecture](docs/DEVELOPMENT.md)
- [Original SAFE CODE audit](SAFE-CODE-AUDIT.md) — historical review of the original script, not certification of this release.

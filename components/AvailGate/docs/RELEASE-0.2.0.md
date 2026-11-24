# AvailGate 0.2.0 — local build record

Date: 2026-10-11. This is the first standalone package build. It has not been
published to a package index or remote repository.

## Available

- Portable Python package, wheel/source distributions, installed CLI, and Python API.
- Versioned JSON search responses with provider outcomes, request budgets, cache age, and ranking explanations.
- Killable workers for modern search and source reading.
- HTML/plain-text reads with source metadata, text hashes, exact excerpts, and direct public-IP fetching.
- Five query modes, exact hostname filtering, local date filtering, and explicit caller-designated official domains.
- Local research sessions with source captures, notes, questions, JSON/Markdown export, and offline resume.
- Portable agent instructions, local diagnostics, and optional network probes.
- Legacy CLI array output and existing search/profile/GHDB workflows.

A live smoke check exposed Bing's abbreviated display-URL problem. Its adapter
now keeps full anchor destinations and decodes Bing tracking links, with a
regression covering exact path preservation.

## Verification

- Original 16 regression tests pass against package-owned source.
- Full suite: 37 offline tests pass in development and against the installed wheel in a clean virtual environment.
- Clean runtime dependency check: no broken requirements.
- Installed capabilities and local doctor succeed from `/tmp`, outside the source project.
- Wheel and source archive build successfully.
- Live query `Python pathlib official documentation`: Bing and DDG both returned results; the initial check completed in approximately 2.4 seconds.
- Live HTTPS reading of example.com returned structured readable text and provenance in approximately 0.25 seconds.
- Network-denied checks returned JSON errors; successful live checks required network access outside the execution sandbox.

The test suite includes actual Bing HTML parsing, Yandex XML regression,
rate-limit classification without credential disclosure, empty/partial/failed
responses, schema validation, worker termination, public-address/redirect/TLS
configuration checks, body limits, source extraction, cache timestamps, session
concurrency/quota behavior, cross-process resume, and legacy compatibility.

The development environment inherits system packages and its broad `pip check`
reports unrelated existing system dependency mismatches. The clean `.install`
environment is independent of those packages and passes its own check.

## Remaining work and limits

- Linux/Python 3.14 is locally verified. The configured Python 3.11/macOS/Windows CI matrix has not been run here.
- Query modes need a judged relevance benchmark before claims of better ranking.
- Provider-side date filters are pending; `--since` currently filters reported dates locally and excludes unknown dates.
- DDG uses its own transport, so internal request counts/size caps are unavailable. Its worker deadline remains enforceable.
- No browser rendering, PDF/OCR, authenticated browsing, or proxy-backed source reader.
- Existing legacy execution retains its original deadlines and cache behavior; the modern commands carry the new worker guarantees.
- Provider fixtures cover representative paths, not every third-party response variant. Scraping adapters can break when sites change.
- The original FORGE / SAFE CODE audit describes the prior script. It is not an audit certification for the new package.

## Local installation and rollback

The source project owns the implementation. The `.install` virtual environment
contains the independently installed wheel; `.venv` is the editable development
environment. The user's `~/bin/availgate` launcher selects the `.install` Python.

The pre-package executable is preserved in
`backups/availgate-original-20261011.py` with SHA-256
`fdc20766db75de4b74c25d61f992f7d91d3abadcf8821566e802e5ecc1123530`.
It can be invoked directly with Python for rollback testing. Original
configuration and cache files are left in place; modern storage is separate.

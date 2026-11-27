# Development architecture

`cli.py` parses commands and renders output. `contracts.py` owns the versioned response envelope and structured errors. `config.py` resolves modern paths/settings. Importing the public package API does not load provider or semantic dependencies.

`search.py` expands modes, dispatches work, filters results, attaches provenance, and calls the established ranking implementation in `legacy.py`. `providers.py` adapts those existing engines to typed outcomes and bounds requests-backed transport. `workers.py` uses spawned processes so timeouts can terminate stalled DNS, network, or adapter work. Workers communicate through pipes; raw provider exceptions are not sent to the agent.

`reader.py` implements structured fetching/extraction with the existing public-target resolver. The legacy fetch path remains available for compatibility; regression tests cover both paths. Extraction hashes and offsets refer to captured text. `storage.py` separates disposable cache records from session events in a local SQLite database, using transactions and payload quotas.

`legacy.py` deliberately retains the earlier implementation during the compatibility period. Provider error observers and lazy semantic imports are narrow changes. Further extraction of ranking/provider code can happen after compatibility has been exercised across releases.

The public Python API exposes `availgate.search(...)` and `availgate.read(...)`, returning the same dictionaries as the CLI. Invalid requests raise `availgate.contracts.Problem`; operation failures return an error envelope. Python scripts invoking multiprocessing-backed operations must use the standard `if __name__ == "__main__":` guard. CLI users need no such setup.

Tests are offline by default. `test_availgate.py` keeps the original 16 regressions and loads package-owned source. `test_research.py` covers schemas, provider parsing/error handling, killable deadlines, filters, cache observation dates, source bounds, persistence, concurrency, and CLI compatibility. The dev extra supplies JSON Schema validation.

Build wheel and source archive with `python -m build --no-isolation`. CI defines Linux/macOS/Windows and Python 3.11/3.14 jobs, but unexecuted CI targets are not evidence of platform compatibility. Mode templates need human relevance judgments before making ranking-quality claims. Live provider checks are operational smoke tests and should be reported separately from deterministic regressions.

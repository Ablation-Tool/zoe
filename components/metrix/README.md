# METRIX

METRIX is an evidence-first inventory and navigation tool for large reverse-engineering directories. It gives a person and an AI agent the same searchable view of a corpus without executing the collected material.

This first release deliberately does **not** assign subjective novelty, utility, or complexity scores. It records what can be established locally: artifact identity, content hashes, detected formats, architecture hints, inventory status, and scan errors.

## What it does

- Recursively inventories regular files and records symlinks without following them.
- Streams SHA256 for regular files and verifies that each file did not change during hashing.
- Detects common executable, archive, document, firmware, and mainframe formats from bytes rather than extensions alone.
- Extracts architecture and endianness hints for ELF, PE, Mach-O, XCOFF, WebAssembly, Java, and selected IBM artifacts.
- Writes one JSON object per artifact to `artifacts.jsonl` and corpus totals to `summary.json`.
- Generates a self-contained, offline `matrix.html` with search, filters, sorting, artifact details, and filtered CSV export.
- Provides a native desktop dashboard with an optional real interactive CLI embedded in a terminal pane.
- Serves an optional localhost workbench with a separate request/response agent bridge.
- Provides JSON-first CLI commands suitable for AI agents and shell pipelines.

METRIX does not execute artifacts, traverse directory symlinks, recursively unpack archives, install analysis dependencies, or claim that `not_recorded` material was never analyzed elsewhere.

## Requirements

Python 3.10 or newer. The CLI, scanner, and HTML viewer use only the Python standard library and local browser APIs. The optional native desktop also requires Tkinter and the `desktop` extra (`pyte` plus its dependencies); no browser or local web server is used by the native desktop.

Run from a checkout:

```bash
python3 -m metrix --help
```

Or install the `metrix` command into a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
metrix --help
```

## Quick start

```bash
metrix scan /path/to/re-material --output metrix-output
```

This creates:

```text
metrix-output/
├── artifacts.jsonl
├── summary.json
└── matrix.html
```

Open `matrix.html` directly in a browser. No server or network connection is needed.

Without installation, substitute `python3 -m metrix` for `metrix` in every example.

## Native desktop with an embedded interactive CLI

Install the optional desktop dependency and open the native dashboard:

```bash
python3 -m pip install -e '.[desktop]'
metrix desktop --output metrix-output
```

The desktop uses native Tkinter widgets, not a browser. It shows the artifact table, search, filters, sorting, evidence details, and CSV export beside a terminal pane. When no CLI is configured, the dashboard remains usable and the terminal explains how to enable one.

Start the user's actual interactive Kimi Code CLI inside that pane:

```bash
metrix desktop --output metrix-output --agent kimi
```

Or embed another interactive CLI:

```bash
metrix desktop --output metrix-output \
  --agent-command 'your-interactive-agent-cli'
```

`--agent-command` is parsed as arguments, never as a shell command. Unlike the optional browser bridge, the desktop does **not** use `kimi -p`, create a separate chatbot, package selected records, build prompts, or parse agent responses. It starts the real CLI in a real pseudo-terminal (PTY); `pyte` handles terminal display, history, and control sequences. The user interacts with that CLI exactly as they would in a separate terminal.

The CLI inherits the user environment and runs in the METRIX output directory unless `--workspace` selects another directory. `METRIX_OUTPUT`, `METRIX_WORKSPACE`, and `METRIX_CLI` are provided so the CLI can operate on the same corpus index. The desktop watches `summary.json` and refreshes the artifact table after the CLI regenerates the scan.

There is no METRIX model and no pretense that the terminal is a separate built-in AI. The top of the window identifies the embedded executable as an **interactive PTY**. The external CLI's own tools, permissions, authentication, and provider data policy apply. Closing the desktop sends SIGHUP to the embedded process group.

## Optional browser workbench and request/response agent bridge

Start the optional browser dashboard without any AI integration:

```bash
metrix gui --output metrix-output
```

METRIX binds to loopback, chooses a free port, prints a session URL, and opens the browser. Keep the process running; stop it with `Ctrl-C`. Use `--no-browser` to print the URL without opening it, or `--port 8765` to select a port. Only `127.0.0.1`, `localhost`, and `::1` are accepted as hosts.

The dashboard supports the same search, filters, sorting, details, and CSV export as the static matrix, plus selection of up to 25 artifacts for chat context. It remains fully usable when no agent is configured.

### Connect your agent

For an installed and configured Kimi Code CLI:

```bash
metrix gui --output metrix-output --agent kimi
```

The preset invokes `kimi -p PROMPT`, using Kimi Code's existing configuration and authentication. METRIX does not supply a model, read CLI credentials, or bundle API keys. See the [Kimi command reference](https://www.kimi.com/code/docs/en/kimi-code-cli/reference/kimi-command.html) for noninteractive behavior.

For another CLI:

```bash
metrix gui --output metrix-output \
  --agent-command 'your-agent-cli --prompt {prompt}'
```

`--agent-command` is parsed as arguments, never as a shell command. If `{prompt}` is present, METRIX replaces it with a single argument. Otherwise the prompt is written to the command's stdin. The external command inherits the user environment, runs in the METRIX output directory unless `--workspace` is supplied, and has a configurable timeout:

```bash
metrix gui --output metrix-output \
  --agent-command 'your-agent-cli' --agent-timeout 120 --workspace /path/to/workspace
```

Each message is a request/response invocation, not a persistent interactive terminal. The GUI sends the current message, active filters, up to 12 recent chat messages, and explicitly selected artifact records. It does not automatically include the full corpus or unselected records. The external agent can nevertheless use its own tools and permissions to access other material.

**The read-only instruction in the bridge prompt is not a sandbox.** The external CLI's own permission policy and provider data policy apply. In particular, Kimi Code's noninteractive mode uses its documented automatic permission behavior. Enable an agent only when that behavior and the selected workspace are acceptable. METRIX does not transmit chat itself; the configured agent determines any network processing.

### Agent-driven dashboard actions

A plain-text agent response appears in chat without changing the dashboard. An agent can also suggest filters by ending its stdout with one single-line JSON object:

```text
METRIX_JSON={"message":"I found the unidentified files.","action":{"type":"filter","search":"","filters":{"format":"unknown","status":"unidentified"}}}
```

Supported filter keys are `format`, `architecture`, `artifact_class`, `status`, and `analysis_status`. The GUI validates the action, applies it to the same matrix, and keeps the raw bridge output available for inspection. Invalid actions produce a warning instead of changing the dashboard.

The local server requires an `X-METRIX-Token` header for data APIs, restricts Host headers, sets a restrictive content security policy, bounds requests, and serves no artifact files. The startup token is removed from the visible browser URL after loading. These browser protections do not constrain the external agent process.

## Agent workflow

Read compact corpus totals:

```bash
metrix summary --output metrix-output
metrix summary --output metrix-output --text
```

Find unidentified artifacts:

```bash
metrix query --output metrix-output --format unknown
```

Filter by architecture, kind, status, or text:

```bash
metrix query --output metrix-output --architecture ppc32
metrix query --output metrix-output --kind executable --status identified
metrix query --output metrix-output --contains firmware
```

`query` emits JSONL by default so each result can be consumed by another tool. Use `--tsv` for a spreadsheet-friendly table and `--limit 0` to disable the result limit.

Inspect one exact artifact by ID, relative path, or unique content SHA256 prefix:

```bash
metrix query --output metrix-output --format unknown
metrix show ARTIFACT_ID --output metrix-output
```

After editing `artifacts.jsonl` or changing the viewer template, regenerate only the HTML:

```bash
metrix render --output metrix-output
```

## Artifact records

Each regular-file record contains:

| Field | Meaning |
|---|---|
| `schema_version` | Record schema version, currently `1` |
| `id` | Stable identifier derived from relative path and content hash |
| `path` | POSIX path relative to the scanned root |
| `kind` | `file`, `symlink`, `special`, or `error` |
| `size_bytes` | Regular-file size at inventory time |
| `sha256` | Full lowercase content digest for a successfully hashed file |
| `format` | Byte-detected format, or `unknown` |
| `architecture` | Byte-derived architecture hint, or `unknown` |
| `endianness` | `little`, `big`, `not-applicable`, or `unknown` |
| `artifact_class` | `executable`, `library`, `archive`, `document`, `source`, `image`, `data`, `symlink`, `special`, or `error` |
| `status` | `identified`, `unidentified`, or `error`; this is inventory identification only |
| `analysis_status` | Always `not_recorded` in this release; no analysis coverage is inferred |
| `detection` | Detection method and format-specific evidence |
| `scan_error` | Present when an artifact could not be inspected completely |

Symlinks include `link_target`; their targets are not opened. Special files and per-file scan failures remain visible instead of silently disappearing from the matrix.

See `summary.json` for the scan root, generation time, tool version, totals, and filter counts. The JSON schema and CLI are the integration contract; the HTML is a view of the same records.

## Detection scope

The detector currently recognizes common forms of:

- ELF, PE/MZ, Mach-O, XCOFF, WebAssembly, and Java class artifacts
- ZIP/JAR, gzip, bzip2, xz, compress, 7-Zip, tar, RPM, Debian `ar`, and ISO 9660 containers
- PDF, PNG, JPEG, GIF, SQLite, UTF text, source code, and selected IBM SAVF, NETDATA, `IEWPLMH`, and `QZRDPACK` material

Unknown does not mean invalid or uninteresting. It means the current detector lacks sufficient evidence. Extension hints are reported separately from byte identification and never silently become confirmed architecture facts.

## Safety and boundaries

- Directory symlinks are recorded but never traversed.
- Regular files are opened with no-follow behavior where the platform supports it.
- Output directories are excluded when nested under the scanned root.
- Files whose size or modification time changes during hashing receive an explicit error record.
- Large files are hashed in chunks; METRIX does not read an entire artifact into memory for hashing.
- Detection is shallow and bounded. Archives are not unpacked and parser execution is not delegated to external tools.
- A hash identifies content, not safety, provenance authenticity, vulnerability status, or public-RE novelty.

## Development

The base CLI intentionally has no required runtime dependencies; the native terminal is optional. Useful validation commands are:

```bash
python3 -m compileall -q metrix
python3 -m metrix --help
python3 -m build
```

Exercise `scan`, `summary`, `query`, `show`, and `render` against a temporary fixture directory before changing the record schema. Validate the static HTML with JavaScript enabled and disabled, including combined filters and CSV export. For `gui`, test both no-agent mode and a local fixture agent command, including token rejection, invalid actions, timeouts, selected-record context, and agent-driven filters. For `desktop`, use a local interactive fixture CLI to verify PTY input/output, terminal resize, keyboard control characters, process cleanup, shared-output refresh, native filters, and no-agent mode. Do not use a hosted agent as the routine test fixture. Keep new detection rules bounded, byte-backed, and explicit about uncertainty.

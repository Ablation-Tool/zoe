<h1 align="center">VisorLog</h1>

<h4 align="center">Lifecycle-tracked findings ledger for AI infrastructure OSINT.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/visorlog/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/visorlog?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/visorlog/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/visorlog?style=flat-square" alt="license"></a>
  <a href="https://golang.org"><img src="https://img.shields.io/badge/go-1.21%2B-00ADD8?style=flat-square&logo=go" alt="go"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#lifecycle">Lifecycle</a> •
  <a href="#schema">Schema</a> •
  <a href="#scope">Scope</a>
</p>

---

VisorLog is a single Go binary that holds findings from across the NuClide toolchain in one append-only SQLite store. Tools like aimap, VisorGoose, and ollama-recon write events into it. Each finding then moves through a defined lifecycle (`open`, `disclosed`, `acknowledged`, `remediated`, `verified`, `archived`) with every status change timestamped and appended as a note. Records are never mutated.

The schema is ECS-inspired and keyed to AI infrastructure recon: host, org, sector, country, tags, CVE IDs, source tool, lifecycle status. Output goes to VisorScuba for compliance scoring, to disclosure reports, and to the alert rules that flag stale criticals and new takeover findings.

# Features

- Single Go binary, embedded SQLite, no external services
- Eight subcommands: `ingest`, `status`, `query`, `update`, `add`, `alert`, `report`, `serve`
- Append-only event log. Status transitions are notes, not row rewrites. Full history preserved
- Ingest adapters for VisorGoose state, ollama-recon state, and universal NDJSON
- Multi-tag OR filter, date-range filter, table / JSON / CSV / Markdown output
- Built-in alert rules: `new-takeover`, `new-critical`, `stale-critical` (>7d), `stale-high` (>14d)
- Web dashboard at `:8765` via `visorlog serve`
- Feeds VisorScuba compliance scoring directly off the same database

# Installation

```bash
go install -v github.com/nuclide-research/visorlog@latest
```

Or build from source:

```bash
git clone https://github.com/nuclide-research/visorlog
cd visorlog
go build -o visorlog .
```

Requires Go 1.21 or later.

# Usage

```console
# severity histogram + sector breakdown
visorlog --db nuclide.db status

# ingest findings from existing tools
visorlog --db nuclide.db ingest --from visorgoose-state.json --format visorgoose
visorlog --db nuclide.db ingest --from findings.ndjson

# query
visorlog --db nuclide.db query --severity critical --status open
visorlog --db nuclide.db query --tags SUB2API,SETUP-OPEN --format md

# update lifecycle
visorlog --db nuclide.db update 4 --status disclosed --note "emailed kominfo@jatengprov.go.id"

# alerts and reports
visorlog --db nuclide.db alert
visorlog --db nuclide.db report --out open-findings.md

# web dashboard
visorlog --db nuclide.db serve
```

<details>
  <summary>Query flags</summary>

| Flag | What it filters |
|------|-----------------|
| `--sector` | sector (government, university, healthcare, commercial) |
| `--severity` | critical / high / medium / low / info |
| `--status` | lifecycle stage |
| `--tag <X>` | single tag substring (legacy) |
| `--tags X,Y,Z` | multi-tag OR (any-match) |
| `--country` | ISO 3166 alpha-2 |
| `--source` | discovering tool |
| `--tld` | top-level domain match |
| `--since YYYY-MM-DD` | events at or after |
| `--until YYYY-MM-DD` | events at or before |
| `--limit N` | max results (default 100) |
| `--format <fmt>` | table, json, csv, md |
| `--json` | shortcut for `--format json` |

</details>

# Lifecycle

```
open -> disclosed -> acknowledged -> remediated -> verified -> archived
```

Every transition is timestamped and appended as a note on the original event. Nothing is overwritten. A finding's full disclosure history reads top to bottom.

# Schema

ECS-inspired, keyed to AI infrastructure recon:

| Field | Description |
|-------|-------------|
| `event.category` | `discovery`, `disclosure`, `remediation`, `regression` |
| `event.severity` | `critical`, `high`, `medium`, `low`, `info` |
| `host.ip` / `host.hostname` | target identity |
| `org.name` / `org.country` | organization |
| `nuclide.sector` | `government`, `university`, `healthcare`, `commercial`, `isp` |
| `nuclide.tags` | freeform (`TAKEOVER`, `CVE-2025-63389`, `CLOUD`, `RAG`, `DISTILLED`) |
| `nuclide.source` | discovering tool |
| `lifecycle.status` | current stage |
| `vuln.ids` | CVE IDs |

# Alert rules

```
[new-takeover] TAKEOVER open: 103.107.245.11 (sijoli-11-245-107.jatengprov.go.id) [government]
[stale-critical] STALE critical: 16.64.116.67 open for >7 days, disclose?
```

Rules live in `alert/rules.go`. Add new rules by extending the slice.

# Where it sits in the chain

```
VisorGoose  -+
aimap       -+--> visorlog ingest --> nuclide.db --> visorlog query / alert / report
ollama-recon-+                                 \
                                                +--> visorscuba assess --> 0-10 scores
```

# Scope

VisorLog is a passive data store. It does not scan, probe, or authenticate to anything. It records what the upstream tools found. Only ingest data from systems you own or have explicit written authorization to assess.

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner, primary ingest source
- [VisorScuba](https://github.com/nuclide-research/VisorScuba) — OPA compliance scoring over the VisorLog database
- [VisorCAS](https://github.com/nuclide-research/VisorCAS) — content-addressed false-positive ledger, the inverse of VisorLog
- [VisorGraph](https://github.com/nuclide-research/VisorGraph) — cert-pivot recon engine, feeds findings into the ledger
- [scanner](https://github.com/nuclide-research/scanner) — fast active-banner stage between passive discovery and deep enum

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

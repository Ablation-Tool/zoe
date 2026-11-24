<h1 align="center">nuclide-asset-schema</h1>

<h4 align="center">JSON Schema interop contract for NuClide Visor asset records.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/nuclide-asset-schema/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/nuclide-asset-schema?style=flat-square" alt="license"></a>
  <a href="https://json-schema.org"><img src="https://img.shields.io/badge/JSON%20Schema-2020--12-blue?style=flat-square" alt="json-schema"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#schema-shape">Schema shape</a> •
  <a href="#tier-label-rule">Tier-label rule</a> •
  <a href="#versioning">Versioning</a>
</p>

---

nuclide-asset-schema is the wire format every NuClide Visor tool reads and writes. One record describes one asset (an IP:port or a Tor onion address) at one point in time. The record carries identity, service fingerprints, operator attribution, target classification, verified findings, provenance, lifecycle state, and a pass-through bag for tool-specific extras.

The contract removes per-pair adapter scripts from the chain. JAXEN, aimap, VisorGraph, VisorLog, and BARE used to each emit different shapes. Every chain step needed glue:

```
jaxen hunt | python adapters/jaxen_to_aimap.py | aimap | python adapters/aimap_to_visorlog.py | visorlog ingest
```

The adapters drifted from the upstream tools and failed silently when a tool added a new field. The canonical schema replaces them:

```
jaxen hunt --format visor-asset | aimap --in visor-asset --out visor-asset | visorlog ingest --format visor-asset
```

A tool that does not recognize a field in `services[]`, `attribution`, or `raw` MUST preserve it on read and write rather than discard it. New fields ship as minor version bumps. Consumers reject records they cannot understand.

# Features

- JSON Schema 2020-12 contract, version `1.1.0`
- Single-record-per-asset shape: identity, services, attribution, classification, findings, lifecycle, source, raw
- `oneOf` identity union: clear-net (`ip` + `port`) or Tor (`onion_address` + optional `intro_points`)
- `additionalProperties: false` at the root, open `raw` bag for tool-specific extras
- Tier-label rule on `findings[].severity >= high`: a non-empty `tier_label_basis` is required, the methodology hard-proof rule enforced at the schema level
- CC0 license, public domain, reuse freely

# Installation

```bash
git clone https://github.com/nuclide-research/nuclide-asset-schema
pip install jsonschema
```

The schema file is [`visor-asset.schema.json`](visor-asset.schema.json). The reference validator is `python -m jsonschema` until a Go-native `visor validate` ships in the `nuclide-asset-go` sibling package.

# Usage

```bash
# Validate a record against the schema
python -m jsonschema -i examples/onion-ollama.json visor-asset.schema.json

# Run the test suite (covers the identity union cases)
pip install pytest jsonschema
python test_schema.py
```

# Schema shape

### Root (required: `schema_version`, `asset`, `source`, `timestamp`)

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `string` const `"1.1.0"` | Consumers MUST check; SHOULD reject unknown versions |
| `asset` | object | Identity union, see below |
| `source` | object | Required `tool` field |
| `timestamp` | `string` (date-time) | RFC 3339, when this record was produced |
| `services[]` | array | Optional, service fingerprints |
| `attribution` | object | Optional, operator identity |
| `classification` | object | Optional, target category and ethics flags |
| `findings[]` | array | Optional, verified findings |
| `lifecycle` | object | Optional, VisorLog lifecycle state |
| `raw` | object | Optional, open pass-through for tool-specific fields |

### `asset` identity union

Exactly one of these two shapes is required (`oneOf`):

- Clear-net: `ip` (IPv4 or IPv6) + `port` (integer 0 to 65535)
- Tor: `onion_address` (v3, matches `^[a-z2-7]{56}\.onion$`)

Optional `asset` fields:

| Field | Type | Notes |
|---|---|---|
| `scheme` | `string` enum | `http`, `https`, `tcp`, `udp`, `tls`, `ws`, `wss` |
| `host_port` | `string` | Convenience composite `"ip:port"` |
| `hostnames` | `string[]` | Reverse DNS or cert SANs |
| `asn` | `string` | Pattern `^AS[0-9]+$` |
| `intro_points` | `string[]` | Tor relay fingerprints, attribution anchor when `ip` is absent |

### `services[]` (required per item: `name`)

| Field | Type | Notes |
|---|---|---|
| `name` | `string` | Canonical service name (`ollama`, `sub2api`, `langfuse`) |
| `version` | `string` | |
| `banner` | `string` | |
| `fingerprint` | `string` | Which fingerprint rule fired (`health-json-status-ok`) |
| `deep_enum` | object | Per-service enumeration payload, service-specific shape |
| `ports_observed` | `integer[]` | |

`additionalProperties: true` on each item. Extra fields are preserved.

### `source` (required: `tool`)

| Field | Type | Notes |
|---|---|---|
| `tool` | `string` | Tool name (`jaxen`, `aimap`, `visorgraph`) |
| `tool_version` | `string` | |
| `run_id` | `string` | Survey ID or UUID for cross-tool correlation |
| `survey` | `string` | Human-readable name (`sub2api-population-2026-05-19`) |

### `classification`

| Field | Type | Enum values |
|---|---|---|
| `category` | `string` | `commercial`, `personal`, `institutional`, `research`, `healthcare`, `government`, `education`, `honeypot`, `unknown` |
| `confidence` | `string` | `low`, `medium`, `high` |
| `ethics_flags` | `string[]` | `HIPAA-adjacent`, `education`, `personal-device`, `safe-harbor`, `honeypot`, `controlled-target`, `ITAR`, `defense-contractor`, `minor-data` |
| `sector` | `string` | Free text |
| `tld_class` | `string` | `.go.id`, `.mil`, `.edu`, `.gov` |

### `findings[]` (required per item: `rule_id`, `severity`)

| Field | Type | Notes |
|---|---|---|
| `rule_id` | `string` | Stable identifier (`AI.H6`, `CVE-YYYY-NNNNN`) |
| `severity` | `string` | `info`, `low`, `medium`, `high`, `critical` |
| `title` | `string` | |
| `description` | `string` | |
| `evidence` | `string` | Truncated probe response or primary-source excerpt |
| `evidence_artifact` | `string` | Path to full evidence file (PCAP, full HTTP response, screenshot) |
| `tags` | `string[]` | |
| `cve` | `string[]` | Pattern `^CVE-[0-9]{4}-[0-9]+$` per item |
| `tier_label_basis` | `string` | Required when `severity >= high` per methodology hard-proof rule |

### `lifecycle`

| Field | Type | Notes |
|---|---|---|
| `status` | `string` | `open`, `disclosed`, `acknowledged`, `remediated`, `verified` |
| `first_seen` | `string` (date-time) | |
| `last_seen` | `string` (date-time) | |
| `disclosed_to` | `string[]` | |
| `disclosed_at` | `string` (date-time) | |

### `attribution`

All optional. Fields: `org`, `isp`, `country` (ISO 3166-1 alpha-2), `country_name`, `city`, `cert_subject_cn`, `cert_subject_org`, `cert_sans`, `cert_issuer_cn`, `domains`, `operator_cluster`.

`operator_cluster` is a multi-host cluster ID (`aiproxy.astrum-lab.com`) when the operator runs more than one surveyed asset.

# Tier-label rule

Every `findings[].severity` of `high` or `critical` requires a non-empty `tier_label_basis`. The field records why that tier was chosen. This enforces the hard-proof rule at the schema level: class membership is not data membership, and surface accessibility is not exploitability.

When verification is blocked by an ethical-stop boundary, say so in `tier_label_basis` explicitly and hold the severity at `high` rather than `critical` until active evidence exists.

# Example

`examples/onion-ollama.json` is a valid 1.1.0 record: a Tor-hosted Ollama instance with minimal fields, exercising the `onion_address` identity branch.

```json
{
  "schema_version": "1.1.0",
  "asset": {
    "onion_address": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.onion",
    "intro_points": ["9695DFC35FFEB861329B9F1AB04C46397020CE31"],
    "scheme": "http"
  },
  "services": [
    { "name": "ollama", "fingerprint": "api-tags-json", "version": "0.1.32" }
  ],
  "classification": { "category": "unknown", "confidence": "low" },
  "source": { "tool": "allium", "tool_version": "0.1.0", "survey": "tor-ai-2026-05-30" },
  "timestamp": "2026-05-30T00:00:00Z",
  "lifecycle": { "status": "open" }
}
```

Note: `examples/sub2api-setup-open.json` declares `schema_version: "1.0.0"` and fails validation against the current schema, which requires the const `"1.1.0"`. Do not use it as a reference record until corrected.

# Versioning

`schema_version` follows SemVer. Major bumps are breaking (field removed, type changed, enum narrowed). Minor bumps are additive (new optional field). Patch bumps are documentation-only. Consumers MUST check `schema_version` on ingest and reject records at unknown versions rather than silently reading them.

To add a field: add it as optional with `additionalProperties: false` still in effect at the relevant level, bump the minor version, and update any examples that exercise the new field.

# Scope

This repo is a JSON Schema contract, not a tool. It does not produce records, parse responses, or validate at runtime. It does not define tool behavior beyond the record shape. aimap, JAXEN, VisorLog, and the rest of the Visor tools own their own logic. This schema is the wire format they agree on. The disposition and false-positive surface belongs to VisorCAS.

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap) - AI and ML infrastructure scanner, emits and consumes this schema
- [VisorLog](https://github.com/nuclide-research/visorlog) - findings ledger, the canonical sink for these records
- [VisorCAS](https://github.com/nuclide-research/VisorCAS) - content-addressed false-positive ledger, the disposition surface
- [VisorGraph](https://github.com/nuclide-research/visorgraph) - cert-pivot for operator attribution
- [scanner](https://github.com/nuclide-research/scanner) - active-banner stage between passive discovery and deep enumeration

# License

CC0 1.0 Universal. Public domain. Reuse freely. Contact: [nuclide-research.com](https://nuclide-research.com)

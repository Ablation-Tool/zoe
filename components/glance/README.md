<h1 align="center">glance</h1>

<h4 align="center">Schema-only sensitivity analyzer for sealed corpora.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/glance/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-CC0-blue?style=flat-square" alt="license"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="python"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#source-profiles">Profiles</a> •
  <a href="#sealed-mode">Sealed Mode</a> •
  <a href="#category-dictionary">Categories</a>
</p>

---

NuClide surveys collect per-host evidence at population scale: collection names, scrape targets, metric labels, RAG document IDs. The next question is always "what kind of data is in there, and is it sensitive?" Reading the corpus to find out is the restraint-discipline failure the methodology forbids. glance answers the question without exposing any individual value to the user.

It runs three read-only passes over names only, never values, then prints a category-and-shape rollup. The corpus stays sealed. The output is counts.

# Features

- Schema-only sensitivity classifier, never reads values by default
- Bag-of-fields pattern dictionary across 7 categories: PII, PHI, FINANCE, DEFENSE_GOV, CRITICAL_INFRA, AI_WORKLOAD, GENERIC_INFRA
- Structural pass classifies each value as RFC1918, public IPv4, DNS hostname, or other
- Statistical shape pass: cardinality, length median and P99, character-entropy distribution
- Source profiles for VictoriaMetrics (`vm-verify`), Chroma (`chroma-campaign`), and generic JSON
- Sealed mode is the default. Raw values appear in output only when `--include-samples N` is explicitly passed
- JSON rollup for downstream pipelines via `-o`
- Single Python file, standard library only

# Installation

```bash
git clone https://github.com/nuclide-research/glance
cd glance
ln -sf "$PWD/glance.py" ~/.local/bin/glance
```

Python 3.9 or later. No dependencies.

# Usage

```bash
# VictoriaMetrics per-host evidence
glance scan ~/syllabus/shodan/vm-verify/hosts --source vm-verify

# Chroma campaign evidence
glance scan ~/syllabus/shodan/chroma-campaign/hosts --source chroma-campaign

# Generic JSON (pass --name-paths to specify which fields to scan)
glance scan ./corpus --source generic --name-paths sample_names,labels

# JSON rollup for a downstream pipeline
glance scan <dir> --source <profile> -o report.json --json-only

# Reveal up to N flagged samples per stream (breaks sealed mode)
glance scan <dir> --source <profile> --include-samples 5
```

# Source profiles

| Profile | What it extracts |
|---|---|
| `vm-verify` | VictoriaMetrics `/api/v1/targets` scrapeUrl hosts, scrapePool and job names, labels, metric-name catalog |
| `chroma-campaign` | Chroma collection names from sample_names plus v1/v2 body parsing |
| `generic` | Configurable dotted JSON paths via `--name-paths` |

Adding a new profile is one extractor function. See `extract_vm_verify` for the pattern. Each extractor returns named streams; the analyzer treats each stream independently.

# Output

Human-readable table to stdout. Optional JSON rollup via `-o`.

Three layers per stream:

- **STRUCTURAL.** IP, hostname, and other counts. Top TLD suffixes without echoing full hostnames.
- **SENSITIVITY.** Category-hit counts (PII, PHI, FINANCE, DEFENSE_GOV, CRITICAL_INFRA, AI_WORKLOAD, GENERIC_INFRA).
- **STATISTICAL SHAPE.** Length distribution, entropy distribution.

A global sensitivity rollup at the bottom aggregates across streams.

# Sealed mode

Default `--include-samples=0`. No raw values appear in any output. You see counts. You do not see content.

If you need to see the matched values (e.g., for a per-disclosure decision), pass `--include-samples N`. The JSON output then contains up to N flagged samples per stream. The table output never shows samples.

# Category dictionary

Each category is a list of regex patterns matched against field names. Examples:

| Category | Sample patterns |
|---|---|
| PII | `email`, `phone`, `ssn`, `birth_date`, `user_id`, `applicant`, `resume` |
| PHI | `patient`, `diagnosis`, `medical`, `hipaa`, `doc_hypertension`, `icd_\d` |
| FINANCE | `payment`, `merchant`, `iban`, `btc`, `wallet`, `app_btc` |
| DEFENSE_GOV | `.mil`, `.gov`, `cleared`, `classified`, defense-contractor names |
| CRITICAL_INFRA | `scada`, `plc`, `modbus`, `bias_current`, `optical_rx`, `pipeline`, `grid` |
| AI_WORKLOAD | `dcgm`, `gpu_util`, `vllm`, `tokens_per_second`, `langfuse`, `runpod`, `embedding` |
| GENERIC_INFRA | `cadvisor`, `node_exporter`, `nginx`, `postgres`, `kubelet` |

The dictionary lives in `glance.py` (`CATEGORIES` dict). Patches welcome. The dictionary is the product.

# Why this exists

NuClide surveys produce per-host evidence files at population scale. A 1,000-plus host corpus is too large to manually review and too sensitive to ingest into an LLM context. The restraint discipline says: do not read the values, characterize the shape. Before glance, this characterization was ad-hoc Python in a notebook every time. Now it is one command per category.

The output answers: "how much sensitive data does this corpus contain, and of what kind, without me reading any of it?"

# Limitations

- **Pattern dictionary is the false-positive and false-negative surface.** A `user_id` label on a generic node-exporter scrape gets flagged as PII but carries no actual PII. A healthcare RAG collection named `documents_2026_01_22` carries PHI but matches no pattern. Treat counts as prior signal, not ground truth.
- **No content read means no semantic understanding.** If a corpus uses intentionally obfuscated names, the bag-of-fields classifier sees nothing. Statistical shape (high entropy) is the only signal in that case.
- **Per-stream extraction is profile-specific.** Adding a new platform requires writing an extractor. The trade-off is precision; a generic string-soup extractor would catch most of the same signal but flag a lot more noise.

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap), AI/ML infrastructure fingerprint scanner that produces the corpora glance characterizes
- [scanner](https://github.com/nuclide-research/scanner), full-handshake banner stage before deep enumeration
- [herald](https://github.com/nuclide-research/herald), declarative HTTP auth-probe tool
- [VisorLog](https://github.com/nuclide-research/visorlog), finding ledger and ingest pipeline
- [BARE](https://github.com/nuclide-research/BARE), semantic exploit-module ranking over scanner findings

# License

CC0, public domain. Built for NuClide Research. Use it, fork it, rename it. Contact: [nuclide-research.com](https://nuclide-research.com)

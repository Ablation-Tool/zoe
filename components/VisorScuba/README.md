<h1 align="center">VisorScuba</h1>

<h4 align="center">OPA compliance scoring for AI infrastructure findings.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/VisorScuba/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/VisorScuba?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/VisorScuba/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/VisorScuba?style=flat-square" alt="license"></a>
  <a href="https://golang.org"><img src="https://img.shields.io/badge/go-1.21%2B-00ADD8?style=flat-square&logo=go" alt="go"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#controls">Controls</a> •
  <a href="#input-shape">Input</a> •
  <a href="#scope">Scope</a>
</p>

---

VisorScuba reads open findings from `nuclide.db` (VisorLog), evaluates each node against the NuClide AI Security Baseline using Open Policy Agent, and emits ScubaGear-style per-node compliance scores from 0 to 10. The Rego policies are embedded in the binary at compile time. There is no runtime policy directory to manage.

Inspired by [CISA's ScubaGear](https://github.com/cisagov/ScubaGear), repurposed for AI and ML infrastructure. Two control families ship in the box: `AI.*` for service exposure (17 controls) and `FO.*` for FinOps cost-management infrastructure. The CISA upstream Rego is embedded verbatim alongside (14 BLUE controls) for reference.

# Features

- Single Go binary, embedded Rego, embedded OPA engine
- 17 NuClide AI Security Baseline controls (`AI.C*` critical, `AI.H*` high, `AI.M*` medium)
- FinOps control family (`FO.*`) for Kubecost / OpenCost exposure
- 14 CISA ScubaGear BLUE controls embedded verbatim (CC0)
- Reads from VisorLog `nuclide.db` directly. No re-export step
- Output formats: terminal, JSON, HTML report
- Scoring: `10 minus (critical_count times 3) minus warn_count`, floor 0
- Cross-references CVE IDs (e.g. CVE-2025-63389) and tag triggers (TAKEOVER, RAG, POOL-LEAK)

# Installation

```bash
go install -v github.com/nuclide-research/VisorScuba@latest
```

Or build from source:

```bash
git clone https://github.com/nuclide-research/VisorScuba
cd VisorScuba
go build -o visorscuba .
```

Requires Go 1.21 or later.

# Usage

```console
# assess all open findings
visorscuba assess --db nuclide.db

# filter to a specific org
visorscuba assess --db nuclide.db --org "Dinas Kominfo"

# JSON output
visorscuba assess --db nuclide.db --json

# HTML report
visorscuba assess --db nuclide.db --report report.html

# list embedded policies
visorscuba policies
```

# Controls

`AI.*` is the AI/ML service exposure baseline. `FO.*` is FinOps cost-management infrastructure. They are separate families so a cost-model finding never gets miscounted as a generic unauthenticated AI dashboard.

| ID | Criticality | Control | Tag triggers |
|----|-------------|---------|--------------|
| AI.C1 | Critical | Unauthenticated AI service publicly exposed | `port_11434_public`, `agent_platform`, non-storage `service_class` |
| AI.C2 | Critical | Live Ollama Connect, account takeover possible | `account_takeover: true` |
| AI.C3 | Critical | CVE-2025-63389: unauthenticated system prompt injection | `cve_2025_63389_vulnerable: true` |
| AI.C4 | Critical | Government infrastructure with any critical finding | `sector: government` + critical |
| AI.C5 | Critical | Cloud object store world-readable (anonymous list ACL) | `storage_acl_open: true` |
| AI.C6 | Critical | Browser-automation backend exposed without auth | `browser_control: true` |
| AI.C7 | Critical | Pooled-account upstream proxy with public counters (Insight #39) | `POOL-LEAK`, `POOLED-ACCOUNT-PUBLIC` |
| AI.H1 | High | Cloud API proxy quota drainable without auth | `cloud_proxy: true` |
| AI.H2 | High | RAG pipeline on government infrastructure | `RAG` + `sector: government` |
| AI.H3 | High | Tool-calling model publicly exposed (function-call chain) | `TOOLS` tag |
| AI.H4 | High | Healthcare AI deployment without auth (PHI / PII risk) | `sector: healthcare` |
| AI.H5 | High | Default-config TLS proxy fronting an AI stack | `default_cert: true` |
| AI.H6 | High | Install wizard accessible, admin-claim window open | `SETUP-OPEN`, `INSTALL-WIZARD-EXPOSED` |
| AI.M1 | Medium | Knowledge-distilled model exposed | `DISTILLED` tag |
| AI.M2 | Medium | Custom AI persona on sensitive infrastructure | `models[].system_prompt` non-empty + sensitive sector |
| AI.M3 | Medium | Development server exposed in production | `DEV-MODE`, `VITE-DEV-EXPOSED`, `DJANGO-DEBUG-TRUE` |
| FO.C1 | High | Unauthenticated cost-model API (Kubecost :9090, OpenCost :9003) | `cost_model_api` (set only when unauthenticated) |

Scoring: `10 - (critical_count * 3) - warn_count`, floor 0.

# Input shape

VisorScuba reads from VisorLog's `nuclide.db`. The engine maps each SQLite row to the Rego input object:

```json
{
  "host_ip": "1.2.3.4",
  "host_hostname": "ollama.example.gov",
  "org_name": "Example Agency",
  "sector": "government",
  "port_11434_public": true,
  "account_takeover": false,
  "cve_2025_63389_vulnerable": true,
  "cloud_proxy": false,
  "models": [{"name": "llama3", "system_prompt": "", "is_cloud": false}],
  "tags": ["CVE-2025-63389"]
}
```

# Policies

`rego/nuclide/` holds the NuClide AI Security Baseline (CC0). `rego/scubagear/` holds the CISA ScubaGear BLUE policies copied verbatim (CC0, public domain). Both are embedded at compile time via `//go:embed all:rego`. No runtime policy files required.

The canonical NuClide policy lives at `rego/nuclide/AIConfig.rego`. A test-only copy at `engine/rego/nuclide/AIConfig.rego` is kept in sync by `TestRegoCopyInSync`. Re-copy after any Rego edit.

# Where it sits in the chain

```
VisorGoose   -+
aimap        -+--> VisorLog (nuclide.db) --> VisorScuba assess --> 0-10 scores / HTML
ollama-recon -+
```

# Scope

VisorScuba is read-only against the VisorLog database. It does not scan, probe, or contact upstream targets. The compliance scoring it produces is one input to disclosure decisions, not a substitute for verification.

# Our other projects

- [VisorLog](https://github.com/nuclide-research/visorlog) — findings ledger, the data source
- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner
- [VisorCAS](https://github.com/nuclide-research/VisorCAS) — content-addressed false-positive ledger
- [VisorGraph](https://github.com/nuclide-research/VisorGraph) — cert-pivot recon engine
- [scanner](https://github.com/nuclide-research/scanner) — fast active-banner stage

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

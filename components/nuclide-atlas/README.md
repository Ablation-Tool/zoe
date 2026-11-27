<h1 align="center">nuclide-atlas</h1>

<h4 align="center">See any LLM stack as a graph. Discover, render, score risk, probe live.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/nuclide-atlas/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/nuclide-atlas?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/nuclide-atlas/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/nuclide-atlas?style=flat-square" alt="license"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python" alt="python"></a>
  <a href="https://react.dev"><img src="https://img.shields.io/badge/frontend-react-61DAFB?style=flat-square&logo=react" alt="react"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#api">API</a> •
  <a href="#graph-schema">Graph Schema</a> •
  <a href="#risk-rules">Risk Rules</a> •
  <a href="#scope">Scope</a>
</p>

---

nuclide-atlas maps a running LLM stack as a typed graph. Models, deployments, endpoints, RAG pipelines, vector indexes, tools, agents, and safety policies. Discovery pulls from four sources (environment variables, a 12-port localhost sweep, `docker ps`, and an optional Kubernetes namespace), validates through Pydantic v2 models, writes `config/atlas.yaml`, and serves the graph as JSON from a FastAPI backend. A React frontend renders the eight entity types as nodes with edges drawn from the wiring. One command from a fresh clone to a browser view of the stack.

`GET /api/risk` runs six deterministic rules and returns findings per entity. `GET /api/probe` re-probes every declared endpoint live. The result is the wiring on screen, the blast radius visible, and the bad defaults flagged before they ship.

# Features

- Auto-discovery across env vars, localhost port sweep, `docker ps`, and `kubectl` namespace probe
- Eight typed entities (`model`, `deployment`, `endpoint`, `ragPipeline`, `vectorIndex`, `tool`, `agent`, `safetyPolicy`) validated by Pydantic v2
- React graph view with badges for risk findings per node
- Six deterministic risk rules: exposed-no-auth, public plaintext, unbounded tokens, large context, no-rerank high-k, open-prompt no-filters
- Live endpoint probe and re-discovery from the UI
- Stable bootstrap exit codes for CI use (`0`, `64`, `65`, `66`)
- Multi-arch Docker images at `ghcr.io/nuclide-research/`
- Reads aimap JSON output. Hands URL probes to aimap when present on `PATH`
- Stays inside what you configure. No external scan, no lateral movement, no callbacks

# Installation

```bash
git clone https://github.com/nuclide-research/nuclide-atlas
cd nuclide-atlas
bin/atlas-bootstrap
```

Requires Docker. `bin/atlas-bootstrap` runs discovery, writes `config/atlas.yaml`, brings up the backend (port 8000) and frontend (port 3000) via `docker compose`, and opens the browser.

Try it with no infrastructure:

```bash
bin/atlas-demo     # mock Ollama (:19101), vLLM (:19102), Qdrant (:19103)
                   # then atlas-bootstrap against them
```

Local development without Docker:

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ATLAS_CONFIG=../config/atlas.example.yaml uvicorn app.main:app --reload --port 8000

# frontend (separate shell)
cd frontend && npm install && npm run dev
```

Vite proxies `/api/*` to `http://localhost:8000`.

# Usage

```console
bin/atlas-bootstrap                          # discover + compose up + browser
bin/atlas-bootstrap --dry-run                # discover + write atlas.yaml, skip docker
bin/atlas-bootstrap --port 3001              # bind a different UI port
bin/atlas-bootstrap --no-open                # skip browser.open
bin/atlas-bootstrap --keep-config            # preserve existing atlas.yaml
bin/atlas-bootstrap --local-host 192.0.2.5   # probe an additional host (repeatable)
bin/atlas-bootstrap --k8s-namespace dev      # include a kubectl probe scoped to namespace
```

Bootstrap exit codes are stable for scripting:

| Code | Meaning |
|------|---------|
| `0` | ok |
| `64` | no LLM services found |
| `65` | docker not available |
| `66` | requested port in use |

# API

```
GET  /api/healthz                       liveness
GET  /api/graph                         full inventory as JSON
GET  /api/probe                         re-probe every declared endpoint live
GET  /api/metrics/{entityType}/{id}     stubbed metrics snapshot
GET  /api/risk                          six-rule findings, per entity
GET  /api/sources                       path of the active atlas.yaml
POST /api/discover                      re-run discovery, rewrite atlas.yaml
POST /api/import-url   {"url": "..."}   probe a URL, merge result into atlas.yaml
```

`entityType` is one of: `model deployment endpoint ragPipeline vectorIndex tool agent safetyPolicy`.

# Graph Schema

Eight entity types. Relations are string ID references, never nested objects.

| Entity | Key fields |
|--------|-----------|
| `Model` | id, name, version, providerType, architecture, training |
| `Deployment` | id, modelId, environment, region, inferenceFramework, resources, configuration |
| `Endpoint` | id, deploymentId, type (publicAPI / internalAPI), protocol, url, authType, supportedOperations, healthPath |
| `VectorIndex` | id, name, dbType, collectionName, embeddingDim, numDocuments |
| `RagPipeline` | id, name, embeddingModelId, vectorIndexId, distanceMetric, retrieval (k, filters, rerankers) |
| `Tool` | id, name, description, inputSchema, outputSchema, backingService |
| `Agent` | id, name, role, primaryModelId, toolsUsed, ragPipelinesUsed, safetyPolicyId |
| `SafetyPolicy` | id, name, prePromptFilters, postResponseFilters, safetyModelId |

`providerType` values: `custom openai anthropic huggingface cohere azure_openai bedrock vertex`

`inferenceFramework` values: `vllm tgi triton llama_cpp ollama custom`

`authType` values: `none api_key bearer mtls oauth2`

# Risk Rules

Six deterministic rules. Each failure appears as a badge on the relevant node.

| Rule ID | Severity | Condition |
|---------|----------|-----------|
| `exposed.no_auth` | high | internal API endpoint with `authType: none` |
| `unencrypted.public_http` | high | public endpoint over plaintext HTTP |
| `unbounded.max_tokens` | warn | prod deployment with no `maxTokens` cap |
| `info.large_context` | info | model `maxContext` >= 100,000 tokens |
| `no_rerank.high_k` | warn | RAG pipeline with k > 10 and no rerankers |
| `open_prompt.no_filters` | high | safety policy with zero pre-prompt and post-response filters |

# Discovery Port Catalog

The built-in prober sweeps 12 ports on localhost (and any `--local-host` hosts):

| Port | Service |
|------|---------|
| 11434 | Ollama |
| 8000 | OpenAI-compatible (vLLM, etc.) |
| 8080 | OpenAI-compatible |
| 8888 | OpenAI-compatible |
| 8081 | Text Generation Inference |
| 6333 | Qdrant |
| 19530 | Milvus |
| 5000 | MLflow |
| 3100 | Langfuse |
| 6006 | Phoenix |
| 7860 | Gradio |
| 8089 | Weaviate |

If `aimap` is on `PATH`, Atlas hands URL probes to it for richer fingerprinting. Otherwise the built-in stdlib prober handles classification.

# Configuration

`config/atlas.example.yaml` ships in the repo and renders on a fresh clone. `config/atlas.yaml` is generated by bootstrap and gitignored. The backend prefers `atlas.yaml` and falls back to `atlas.example.yaml`. Probe credentials are environment variables, never in the YAML:

```
ATLAS_PROBE_TOKEN_E-MY-ENDPOINT=<bearer or api_key>
```

# Extending

| Goal | Touch |
|------|-------|
| Add an entity type | `backend/app/models.py` then `frontend/src/lib/types.ts` and `graphBuild.ts` |
| Add a discovery probe | `backend/app/discovery/probes/` then register in `runner.py` |
| Plug in real metrics | Replace `backend/app/metrics.py` (`MetricsSnapshot` is the contract) |
| Add a risk rule | `backend/app/risk.py`, one conditional per rule |
| Add a service fingerprint | `backend/app/discovery/probes/fingerprint.py` (`PORT_CATALOG` and `fingerprint()`) |

# Scope

nuclide-atlas maps infrastructure you configure or hand to a probe. It does not scan external networks, does not move laterally, does not call home. For external discovery of AI infrastructure you do not own, use [aimap](https://github.com/nuclide-research/aimap). Atlas reads aimap JSON output if you want to pipe one into the other.

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap) — fingerprint scanner for exposed AI and ML infrastructure
- [scanner](https://github.com/nuclide-research/scanner) — fast active-banner stage between passive discovery and deep enumeration
- [agent-logging-system](https://github.com/nuclide-research/agent-logging-system) — operational monitor for multi-agent AI workflows
- [VisorLog](https://github.com/nuclide-research/visorlog) — finding ledger and ingest pipeline
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

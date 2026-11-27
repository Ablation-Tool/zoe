# VisorScuba

OPA-powered AI infrastructure compliance scoring for NuClide findings. Reads `nuclide.db` (VisorLog), evaluates every open finding against ~10 NuClide AI Security Baseline Rego controls (AI.C1–C4 critical, AI.H1–H4 high, AI.M1–M2 medium), emits ScubaGear-style 0–10 per-node scores. Inspired by CISA's ScubaGear, repurposed for AI/ML infrastructure.

## Language
Go

## Build & Run
```
go build -o visorscuba .
visorscuba assess --db nuclide.db
visorscuba assess --db nuclide.db --json
visorscuba assess --db nuclide.db --org "government" --html report.html
visorscuba policies      # list embedded Rego modules
go test ./...
```

## Control families
- `AI.*` — AI/ML service exposure baseline. Critical (AI.C*), High (AI.H*), Medium info (AI.M*). Full taxonomy + tag triggers in the README.
- `FO.*` — FinOps cost-management infrastructure, a separate family from `AI.*`. **FO.C1**: unauthenticated cost-model API (Kubecost on :9090, OpenCost on :9003). Flag-anchored to `cost_model_api`, set only when a `Kubecost` / `OpenCost` / `COST-MODEL` class is seen unauthenticated. Scored **High (warn)** — recon-grade infra disclosure (cluster topology + workload names + cloud spend), not breach/RCE. AI.C1 excludes `cost_model_api` so the finding routes to FO.C1, never the generic AI tier.

## Claude Code Notes
- Check README for full CLI surface, control taxonomy, and input shape
- Rego policies live in `rego/nuclide/` (NuClide AI Security Baseline) + `rego/scubagear/` (CISA upstream, CC0)
- `rego/nuclide/AIConfig.rego` is the canonical policy; `engine/rego/nuclide/AIConfig.rego` is a test-only copy kept in sync by `TestRegoCopyInSync` (re-copy after any rego edit)
- Findings flow: aimap / VisorRAG / probes → VisorLog (nuclide.db) → VisorScuba (scores)
- Built with [Claude Code](https://claude.ai/code)

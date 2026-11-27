package nuclide_ai_baseline

import future.keywords.in

# NuClide AI Infrastructure Security Baseline v1.0
# CC0 — public domain, freely reusable.
#
# Input shape (VisorLog event / VisorGoose probe result):
#   host_ip, host_hostname, org_name, org_country, sector, tld
#   ollama_version, port_11434_public, authenticated
#   cve_2025_63389_vulnerable, account_takeover, cloud_proxy
#   service_class           — human-readable label (Ollama / MLflow / AutoGen Studio / ...)
#   agent_platform          — true for AutoGen-Studio-class findings
#   storage_acl_open        — true for AZURE-BLOB-PUBLIC-LIST findings
#   default_cert            — true for TRAEFIK-DEFAULT-CERT findings
#   models: [{name, is_cloud, system_prompt}]
#   tags: ["TAKEOVER", "CVE-2025-63389", "CLOUD", "RAG", "DISTILLED", "TOOLS",
#          "SETUP-OPEN", "SETUP_OPEN", "DATASOURCE_EXPOSED", "VECTOR_DB_PII",
#          "UNAUTH_INFERENCE", "OPEN_DIR_CREDS", ...]

default score = 10
default max_score = 10

#──────────────────────────────────────────────────────────────
# CRITICAL denies  (score −3 each)
#──────────────────────────────────────────────────────────────

# service_label — the human-readable service name, defaulting to a
# generic label so AI.C1 never says "Ollama" for a non-Ollama finding.
service_label = label {
    input.service_class != ""
    label := input.service_class
} else = "AI/ML service"

# AI.C1 — Unauthenticated AI service publicly exposed.
# Fires for any finding that represents a publicly-reachable service:
# the legacy Ollama path (port_11434_public), an agent platform, or any
# finding present in the ledger at all (every VisorLog open finding is,
# by definition, a confirmed public exposure). The details string now
# uses service_class instead of hardcoding "Ollama".
deny[result] {
    ai_c1_applies
    result := {
        "id":          "AI.C1",
        "criticality": "Critical",
        "requirement": "AI services must not be publicly accessible without authentication",
        "details":     sprintf("Unauthenticated %v at %v (%v)", [service_label, input.host_ip, input.host_hostname]),
    }
}

ai_c1_applies { input.port_11434_public == true }
ai_c1_applies { input.agent_platform == true }
ai_c1_applies {
    # Any non-storage, non-cert, non-browser-control finding with a
    # recognized service class is an exposed service. Storage-ACL,
    # default-cert, browser-control, and FinOps cost-model findings have
    # their own dedicated rules (AI.C5, AI.H5, AI.C6, FO.C1) and should
    # not double-fire under AI.C1.
    input.service_class != ""
    input.service_class != "AI/ML service"
    not input.storage_acl_open
    not input.default_cert
    not input.browser_control
    not input.cost_model_api
}

# AI.C5 — Cloud object store left world-readable (anonymous list ACL).
# Surfaced by the VisorBishop Phase 5b bucket-accessibility work; before
# this rule, AZURE-BLOB-PUBLIC-LIST findings mis-fired as "Ollama".
deny[result] {
    input.storage_acl_open == true
    result := {
        "id":          "AI.C5",
        "criticality": "Critical",
        "requirement": "Cloud object stores backing AI/ML pipelines must not permit anonymous list or read",
        "details":     sprintf("Anonymous-list ACL on cloud storage backing an AI/ML pipeline at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

# AI.C2 — Live account takeover via Ollama Connect
deny[result] {
    input.account_takeover == true
    result := {
        "id":          "AI.C2",
        "criticality": "Critical",
        "requirement": "Cloud API credentials must not be claimable via unauthenticated endpoints",
        "details":     sprintf("Live Ollama Connect claim URL at %v — cloud subscription takeover possible", [input.host_ip]),
    }
}

# AI.C3 — CVE-2025-63389: unauthenticated model injection
deny[result] {
    input.cve_2025_63389_vulnerable == true
    result := {
        "id":          "AI.C3",
        "criticality": "Critical",
        "requirement": "Model creation endpoint (/api/create) must require authentication",
        "details":     sprintf("CVE-2025-63389: unauthenticated system prompt injection at %v (Ollama %v)", [input.host_ip, input.ollama_version]),
    }
}

# AI.C7 — Pooled-account upstream proxy with publicly-readable account metrics.
# The v1 claude-relay-service finding shape (Insight #39): a Tier-2 relay
# pools paid Tier-1 vendor accounts (Anthropic, OpenAI, Google) and serves
# downstream customers. When account counters, total-token counters, or
# third-party-concurrency settings are reachable WITHOUT authentication,
# the vendor's enforcement target (the visible account list) is
# externally observable. Disclosure target is the vendor whose accounts
# are pooled, NOT the host operator (per Insight #39 disclosure routing).
# Tag-anchored to POOL-LEAK / POOLED-ACCOUNT-PUBLIC / ACCOUNT-COUNTER-PUBLIC.
deny[result] {
    has_pool_leak_tag
    result := {
        "id":          "AI.C7",
        "criticality": "Critical",
        "requirement": "Pooled-account upstream proxies must auth-gate account metrics — public account counters expose the entire downstream architecture and the upstream vendor's pooled credentials",
        "details":     sprintf("Pooled-account upstream proxy at %v (%v) with publicly-readable account/token counters — Insight #39 architecture exposed", [input.host_ip, input.host_hostname]),
    }
}

has_pool_leak_tag { "POOL-LEAK" in input.tags }
has_pool_leak_tag { "POOLED-ACCOUNT-PUBLIC" in input.tags }
has_pool_leak_tag { "ACCOUNT-COUNTER-PUBLIC" in input.tags }

# AI.C10 — Setup token / admin-bootstrapping endpoint exposed.
# First POST to /api/setup (Metabase pattern) or equivalent claims permanent
# admin with caller-supplied credentials. Distinct from AI.H6 (install wizard)
# because a setup token is a single-use permanent-admin credential, not a
# needs_setup=true wizard state. Tag-anchored to SETUP-TOKEN.
deny[result] {
    input.setup_token_exposed == true
    result := {
        "id":          "AI.C10",
        "criticality": "Critical",
        "requirement": "Admin-bootstrapping endpoints that accept a setup token must be disabled or auth-gated after initial deployment",
        "details":     sprintf("Setup token / admin-claim endpoint exposed at %v (%v) — first POST claims permanent admin", [input.host_ip, input.host_hostname]),
    }
}

# AI.C11 — Hardcoded default credentials confirmed.
# Deployment shipped with vendor-default credentials baked into config
# (e.g. Agenta: POSTGRES_PASSWORD=password, Dify: admin@dify.ai / password).
# These are not guessed — they are confirmed from vendor documentation or
# source-visible defaults. Tag-anchored to DEFAULT-CREDS.
deny[result] {
    input.default_credentials == true
    result := {
        "id":          "AI.C11",
        "criticality": "Critical",
        "requirement": "Default vendor credentials must be rotated before production deployment",
        "details":     sprintf("Hardcoded default credentials confirmed at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

# AI.C12 — Hardcoded upstream API credentials in publicly-served bundle.
# Upstream vendor API keys or webhook URLs (Make.com, Zapier, etc.) embedded
# in the SPA JavaScript bundle and reachable without authentication. Anyone
# can retrieve the bundle and claim/drain the upstream account. Tag-anchored
# to WEBHOOK-LEAK / LLMJACKING.
deny[result] {
    input.webhook_leak == true
    result := {
        "id":          "AI.C12",
        "criticality": "Critical",
        "requirement": "Upstream API credentials and webhook URLs must never appear in publicly-served JavaScript bundles",
        "details":     sprintf("Hardcoded upstream API credential or webhook URL in SPA bundle at %v (%v) — LLMjacking / quota-drain primitive", [input.host_ip, input.host_hostname]),
    }
}

# AI.C6 — Browser-automation backend exposed without authentication.
# Surfaced by the 2026-05-14 browser-automation survey. CDP, Splash,
# Selenium Grid, Selenoid, Browserless and Playwright MCP have no auth
# concept in their default deployment. An exposed instance is
# unauthenticated remote browser control: cookie/session-token theft on
# any live authenticated session, SSRF to internal services and cloud
# metadata, and arbitrary in-page JavaScript execution. Distinct from a
# plain unauthenticated dashboard (AI.C1) because the capability is
# remote control of a browser, not just data disclosure.
deny[result] {
    input.browser_control == true
    result := {
        "id":          "AI.C6",
        "criticality": "Critical",
        "requirement": "Browser-automation backends must not be reachable without authentication — an exposed one is remote browser control",
        "details":     sprintf("Unauthenticated %v at %v (%v) — remote browser control: session-token theft, SSRF, in-page JS execution", [service_label, input.host_ip, input.host_hostname]),
    }
}

# AI.C8 — Unauthenticated analytics/BI datasource exposure (Grafana, Metabase).
# Datasource configs (Grafana /api/datasources, Metabase /api/database) expose
# connection strings including credentials for backend databases. No auth
# required to read them. Anchored to DATASOURCE_EXPOSED tag.
deny[result] {
    "DATASOURCE_EXPOSED" in input.tags
    result := {
        "id":          "AI.C8",
        "criticality": "Critical",
        "requirement": "Analytics platforms must not expose database connection strings without authentication",
        "details":     sprintf("Unauthenticated datasource exposure at %v — database credentials readable without login", [input.host_ip]),
    }
}

# AI.C9 — Unauthenticated vector database with PII fields.
# Vector DB collections tagged with PII field names are readable without
# credentials. Anchored to VECTOR_DB_PII tag.
deny[result] {
    "VECTOR_DB_PII" in input.tags
    result := {
        "id":          "AI.C9",
        "criticality": "Critical",
        "requirement": "Vector databases containing PII must require authentication",
        "details":     sprintf("Unauthenticated vector DB at %v with PII-tagged fields — personal data readable without credentials", [input.host_ip]),
    }
}

# AI.C4 — Government infrastructure with any critical finding
# Helper: true when any critical condition fires (avoids self-reference in deny)
has_critical_finding { ai_c1_applies }
has_critical_finding { input.account_takeover == true }
has_critical_finding { input.cve_2025_63389_vulnerable == true }
has_critical_finding { input.storage_acl_open == true }
has_critical_finding { input.browser_control == true }
has_critical_finding { has_pool_leak_tag }
has_critical_finding { "DATASOURCE_EXPOSED" in input.tags }
has_critical_finding { "VECTOR_DB_PII" in input.tags }
has_critical_finding { input.setup_token_exposed == true }
has_critical_finding { input.default_credentials == true }
has_critical_finding { input.webhook_leak == true }

deny[result] {
    input.sector == "government"
    has_critical_finding
    result := {
        "id":          "AI.C4",
        "criticality": "Critical",
        "requirement": "Government infrastructure must not expose critical AI security vulnerabilities",
        "details":     sprintf("Critical AI exposure on government infrastructure: %v (%v, %v)", [input.host_ip, input.org_name, input.org_country]),
    }
}

#──────────────────────────────────────────────────────────────
# HIGH warnings  (score −1 each)
#──────────────────────────────────────────────────────────────

# AI.H1 — Cloud API proxy quota exposed
warn[result] {
    input.cloud_proxy == true
    not input.account_takeover
    result := {
        "id":          "AI.H1",
        "criticality": "High",
        "requirement": "Cloud API proxies must not be publicly accessible without authentication",
        "details":     sprintf("Cloud API proxy exposed at %v — paid quota drainable without authentication", [input.host_ip]),
    }
}

# AI.H2 — RAG pipeline on government infrastructure
warn[result] {
    "RAG" in input.tags
    input.sector == "government"
    result := {
        "id":          "AI.H2",
        "criticality": "High",
        "requirement": "Document retrieval pipelines on government infrastructure must be authenticated",
        "details":     sprintf("Unauthenticated government RAG pipeline at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

# AI.H3 — Tool-calling model publicly exposed
warn[result] {
    "TOOLS" in input.tags
    result := {
        "id":          "AI.H3",
        "criticality": "High",
        "requirement": "Function-calling models must not be publicly accessible",
        "details":     sprintf("Tool-calling model at %v — prompt injection can chain to external function calls", [input.host_ip]),
    }
}

# AI.H4 — Healthcare sector AI exposure
warn[result] {
    input.sector == "healthcare"
    result := {
        "id":          "AI.H4",
        "criticality": "High",
        "requirement": "Healthcare AI deployments must be authenticated (PHI/PII risk)",
        "details":     sprintf("Unauthenticated AI on healthcare infrastructure at %v (%v)", [input.host_ip, input.org_name]),
    }
}

# AI.H5 — Default-config TLS proxy fronting an AI stack.
# A Traefik default cert (CN=TRAEFIK DEFAULT CERT) indicates the reverse
# proxy was deployed without TLS configuration, which correlates with the
# rest of the stack lacking authentication hardening. Surfaced by the
# SmartShop AI / PENTECH chain; before this rule it mis-fired as "Ollama".
warn[result] {
    input.default_cert == true
    result := {
        "id":          "AI.H5",
        "criticality": "High",
        "requirement": "TLS-terminating proxies in front of AI infrastructure must use a configured certificate, not the framework default",
        "details":     sprintf("Default-config TLS proxy (e.g. Traefik default cert) fronting an AI stack at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

# AI.H6 — Install wizard accessible (admin-claim-window).
# Surfaced by the 2026-05-19 sub2api population survey: 101/7,720 hosts
# returned needs_setup=true on a publicly-reachable /setup/* endpoint.
# Anyone reaching the host before the operator completes setup can POST
# to /setup/init (or equivalent) to claim the admin account and bind
# their own credentials. Distinct from AI.C1 (general unauth exposure)
# because the capability is administrative takeover, not just data
# disclosure. Tag-anchored to keep the rule cheap to evaluate.
warn[result] {
    "SETUP-OPEN" in input.tags
    result := {
        "id":          "AI.H6",
        "criticality": "High",
        "requirement": "Install wizards must not be reachable in a needs_setup=true state from the public internet — first POST claims admin",
        "details":     sprintf("Install wizard accessible at %v (%v) — admin-claim window open", [input.host_ip, input.host_hostname]),
    }
}

# AI.H6 also fires on the more specific TAKEOVER-VECTOR tag used by
# the sub2api verify probe.
warn[result] {
    "TAKEOVER-VECTOR" in input.tags
    not "SETUP-OPEN" in input.tags  # avoid double-fire when both tags present
    result := {
        "id":          "AI.H6",
        "criticality": "High",
        "requirement": "Install wizards must not be reachable in a needs_setup=true state from the public internet — first POST claims admin",
        "details":     sprintf("Admin-takeover vector at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

# AI.H6 also fires on the underscore-variant tag (SETUP_OPEN) used by
# the Metabase setup-token probe and VisorLog ingest pipeline.
warn[result] {
    "SETUP_OPEN" in input.tags
    not "SETUP-OPEN" in input.tags
    not "TAKEOVER-VECTOR" in input.tags
    result := {
        "id":          "AI.H6",
        "criticality": "High",
        "requirement": "Install wizards must not be reachable in a needs_setup=true state from the public internet — first POST claims admin",
        "details":     sprintf("Unclaimed admin-registration surface at %v — setup token live, POST to /setup grants full admin", [input.host_ip]),
    }
}

# AI.H7 — Unauthenticated LLM inference API (vLLM, llama.cpp, Triton, etc.)
# Tag-based: UNAUTH_INFERENCE (from VisorLog / VisorGoose probes).
warn[result] {
    "UNAUTH_INFERENCE" in input.tags
    result := {
        "id":          "AI.H7",
        "criticality": "High",
        "requirement": "LLM inference APIs must require authentication — unauthenticated access enables compute theft and prompt injection",
        "details":     sprintf("Unauthenticated inference API at %v (%v) — arbitrary completions without credentials", [input.host_ip, input.service_class]),
    }
}

# AI.H8 — Open directory exposing sensitive application files
warn[result] {
    "OPEN_DIR_CREDS" in input.tags
    result := {
        "id":          "AI.H8",
        "criticality": "High",
        "requirement": "Application directories must not be served over unauthenticated HTTP",
        "details":     sprintf("Open directory at %v exposes sensitive files (.env, SSL keys, .git) — credential and source-code leak", [input.host_ip]),
    }
}

# AI.H9 — Unauthenticated vLLM / OpenAI-compatible inference-server API.
# Field-based complement to AI.H7: fires on findings where the VisorScuba
# input pipeline detected VLLM or UNAUTH-VLLM tags and set unauth_inference_api.
# vLLM and TGI expose /v1/completions and /v1/chat/completions without auth
# in their default deployment — GPU compute drainable without credentials.
warn[result] {
    input.unauth_inference_api == true
    not "UNAUTH_INFERENCE" in input.tags  # avoid double-fire with AI.H7
    result := {
        "id":          "AI.H9",
        "criticality": "High",
        "requirement": "Inference-server APIs must require authentication — unauthenticated access enables compute theft and model misuse",
        "details":     sprintf("Unauthenticated inference API (%v) at %v (%v) — GPU compute and model accessible without credentials", [service_label, input.host_ip, input.host_hostname]),
    }
}

# AI.H10 — Auth-gated platform with open self-registration (Insight #55).
# The API requires a valid session, but anyone can POST /auth/register (or
# equivalent) to create an account. The registration endpoint is the auth
# bypass: account creation = full API access within the new account's scope.
# Applies to Langfuse, Agenta, Opik, and similar platforms. Tag-anchored to
# SIGNUP-OPEN.
warn[result] {
    input.signup_open == true
    result := {
        "id":          "AI.H10",
        "criticality": "High",
        "requirement": "Self-registration must be disabled or restricted to verified email domains on internally-deployed AI observability platforms",
        "details":     sprintf("Open self-registration at %v (%v) — auth-gated API accessible to any self-registered account (Insight #55)", [input.host_ip, input.host_hostname]),
    }
}

# FO.C1 — Unauthenticated cost-model API (Kubecost / OpenCost).
# FinOps cost-allocation backends (Kubecost on :9090, OpenCost on :9003)
# ship with no authentication concept in their default deployment. An
# exposed instance leaks the entire cluster cost model: node inventory,
# namespace and workload names, container resource allocations, and cloud
# spend — a full reconnaissance map of the Kubernetes estate behind the
# API. Distinct from a generic unauthenticated AI dashboard (AI.C1)
# because the exposed surface is cluster cost/topology telemetry, not an
# AI/ML service, so AI.C1 explicitly excludes cost_model_api and the
# finding routes here. Flag-anchored to cost_model_api (set from the
# Kubecost / OpenCost / COST-MODEL service class when unauthenticated).
#
# Scored High, not Critical: cost-model exposure is reconnaissance-grade
# infrastructure disclosure (cluster topology, workload names, cloud
# spend), not a data breach or remote-code-execution primitive. It maps
# to the same information-disclosure tier as AI.H1/AI.H5/AI.H8 rather
# than the credential-takeover / RCE critical family (AI.C1–C12).
warn[result] {
    input.cost_model_api == true
    result := {
        "id":          "FO.C1",
        "criticality": "High",
        "requirement": "Cost-model APIs (Kubecost / OpenCost) must require authentication — an exposed one leaks cluster topology, workload inventory, and cloud spend",
        "details":     sprintf("Unauthenticated %v cost-model API at %v (%v) — cluster cost, node, and workload allocation readable without credentials", [service_label, input.host_ip, input.host_hostname]),
    }
}

#──────────────────────────────────────────────────────────────
# MEDIUM info  (score −0, flagged only)
#──────────────────────────────────────────────────────────────

# AI.M1 — Knowledge-distilled model exposed
info[result] {
    "DISTILLED" in input.tags
    result := {
        "id":          "AI.M1",
        "criticality": "Medium",
        "requirement": "Knowledge-distilled models should be access-controlled",
        "details":     sprintf("Distilled model at %v encodes reasoning patterns of proprietary source model", [input.host_ip]),
    }
}

# AI.M2 — Custom AI persona on sensitive infrastructure
info[result] {
    some model in input.models
    model.system_prompt != ""
    input.sector in {"government", "healthcare", "military"}
    result := {
        "id":          "AI.M2",
        "criticality": "Medium",
        "requirement": "Custom AI personas on sensitive infrastructure must be reviewed and authorized",
        "details":     sprintf("Custom system prompt deployed on %v infrastructure at %v", [input.sector, input.host_ip]),
    }
}

# AI.M3 — Development server exposed in production.
# Surfaced by the 2026-05-19 sub2api survey (4/7,720 hosts served the
# vite dev runtime in production HTML). Source-map paths, unminified
# bundles, and dev-mode WebSocket endpoints become reachable. Indicates
# CI/CD misconfiguration: the operator deployed the dev build instead
# of the production build. Tag-anchored to BUILD-LEAK / DEV-MODE /
# VITE-DEV-EXPOSED / WEBPACK-DEV-EXPOSED / DJANGO-DEBUG-TRUE.
info[result] {
    has_dev_mode_tag
    result := {
        "id":          "AI.M3",
        "criticality": "Medium",
        "requirement": "Production deployments must serve production builds — dev servers expose source-maps, unminified code, and hot-reload sockets",
        "details":     sprintf("Development server exposed in production at %v (%v)", [input.host_ip, input.host_hostname]),
    }
}

has_dev_mode_tag { "DEV-MODE" in input.tags }
has_dev_mode_tag { "BUILD-LEAK" in input.tags }
has_dev_mode_tag { "VITE-DEV-EXPOSED" in input.tags }
has_dev_mode_tag { "WEBPACK-DEV-EXPOSED" in input.tags }
has_dev_mode_tag { "DJANGO-DEBUG-TRUE" in input.tags }

#──────────────────────────────────────────────────────────────
# Scoring and summary
#──────────────────────────────────────────────────────────────

score = s {
    raw := max_score - (count(deny) * 3) - count(warn)
    s := max({0, raw})
}

violations = v {
    d := [r | r := deny[_]]
    w := [r | r := warn[_]]
    v := array.concat(d, w)
}

summary = {
    "score":               score,
    "max_score":           max_score,
    "compliance_pct":      round((score / max_score) * 100),
    "violations":          violations,
    "info":                [r | r := info[_]],
    "passing":             count(violations) == 0,
    # blue_compliance_pct: % of the 13 active BLUE-* auto+telemetry controls
    # that did NOT fire on this node; defined in BlueTeam.rego (same package).
    "blue_compliance_pct": blue_compliance_pct,
}

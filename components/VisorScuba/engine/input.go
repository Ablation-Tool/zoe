package engine

import (
	"database/sql"
	"encoding/json"
	"strings"

	_ "modernc.org/sqlite"
)

// Node is the flat input shape the Rego policy evaluates.
type Node struct {
	HostIP                  string                   `json:"host_ip"`
	HostHostname            string                   `json:"host_hostname"`
	OrgName                 string                   `json:"org_name"`
	OrgCountry              string                   `json:"org_country"`
	Sector                  string                   `json:"sector"`
	TLD                     string                   `json:"tld"`
	OllamaVersion           string                   `json:"ollama_version"`
	Port11434Public         bool                     `json:"port_11434_public"`
	Authenticated           bool                     `json:"authenticated"`
	CVE202563389Vulnerable  bool                     `json:"cve_2025_63389_vulnerable"`
	AccountTakeover         bool                     `json:"account_takeover"`
	CloudProxy              bool                     `json:"cloud_proxy"`
	Tags                    []string                 `json:"tags"`
	Models                  []map[string]interface{} `json:"models"`
	Source                  string                   `json:"source"`
	// ServiceClass is a human-readable label for what the finding
	// actually is (Ollama, MLflow, AutoGen Studio, etc.), derived from
	// the finding's tags. Before this field existed, AI.C1 hardcoded
	// "Unauthenticated Ollama" for every finding.
	ServiceClass string `json:"service_class"`
	// AgentPlatform / StorageACLOpen / DefaultCert are tag-derived flags
	// that drive the dedicated rules added alongside AI.C1.
	AgentPlatform  bool `json:"agent_platform"`
	StorageACLOpen bool `json:"storage_acl_open"`
	DefaultCert    bool `json:"default_cert"`
	// BrowserControl is true for the browser-automation backend tier
	// (CDP, Splash, Selenium Grid, Selenoid, Browserless, Playwright
	// MCP). An exposed one is unauthenticated remote browser control —
	// cookie/session theft, SSRF, and arbitrary in-page JS execution.
	BrowserControl bool `json:"browser_control"`
	// WebhookLeak is true for hardcoded upstream API credentials or
	// webhook URLs found in publicly-served SPA bundles (WEBHOOK-LEAK,
	// LLMJACKING tags). These are claimable LLMjacking primitives.
	WebhookLeak bool `json:"webhook_leak"`
	// SignupOpen is true for auth-gated platforms where self-registration
	// is open — auth-gated API + open signup = account-takeover risk
	// (Insight #55, SIGNUP-OPEN tag).
	SignupOpen bool `json:"signup_open"`
	// SetupTokenExposed is true for setup-token / admin-bootstrapping
	// endpoints reachable without authentication (SETUP-TOKEN tag).
	// First POST claims permanent admin — Metabase-class exposure.
	SetupTokenExposed bool `json:"setup_token_exposed"`
	// UnauthInferenceAPI is true for vLLM or inference-server APIs
	// reachable without authentication (UNAUTH-VLLM, VLLM tags).
	UnauthInferenceAPI bool `json:"unauth_inference_api"`
	// DefaultCredentials is true for hardcoded default credentials
	// confirmed in the deployment (DEFAULT-CREDS tag).
	DefaultCredentials bool `json:"default_credentials"`
	// CostModelAPI is true for an unauthenticated FinOps cost-model API
	// (Kubecost, OpenCost, or a generic cost-model class). These have no
	// auth concept in their default deployment and expose cluster cost,
	// node, and workload allocation data. The dedicated FO.C1 rule fires
	// on this flag so the finding routes to the FinOps class instead of
	// being caught by the generic AI.C1 exposure rule.
	CostModelAPI bool `json:"cost_model_api"`

	// Blue-team control signals (BLUE-* policy family).
	// Set from tags emitted by aimap/visorgraph/visorlog ingest pipeline.

	// NoTLS: service listens without TLS (NO-TLS tag). BLUE-NET-001.
	NoTLS bool `json:"no_tls"`
	// BannerExposed: version/server banner visible in response headers
	// (BANNER-EXPOSED tag). BLUE-NET-007.
	BannerExposed bool `json:"banner_exposed"`
	// OpenAPIDocs: /docs, /redoc, or /openapi.json reachable unauthenticated
	// (OPENAPI-DOCS-EXPOSED tag). BLUE-NET-008.
	OpenAPIDocs bool `json:"openapi_docs"`
	// InternalSANExposed: cert CN/SAN exposes descriptive internal hostname
	// (admin/langflow/mcp/agents pattern from visorgraph, INTERNAL-SAN tag).
	// BLUE-EXP-002.
	InternalSANExposed bool `json:"internal_san_exposed"`
	// KnownVulnerable: host version matches a known-vulnerable advisory line
	// (KNOWN-VULNERABLE tag or any CVE-* tag). BLUE-SC-001.
	KnownVulnerable bool `json:"known_vulnerable"`
	// DangerousEndpointExposed: a known-dangerous framework endpoint is
	// reachable through the edge (DANGEROUS-ENDPOINT-UNBLOCKED tag). BLUE-OBS-006.
	DangerousEndpointExposed bool `json:"dangerous_endpoint_exposed"`
	// IsIndexed: host appeared in a public scan index (Shodan/Censys/JAXEN).
	// True for all open VisorLog events — if it's in the DB it was discovered
	// via the survey pipeline. BLUE-EXP-001.
	IsIndexed bool `json:"is_indexed"`

	// Telemetry signals — set by visorlog ingest when a runtime-telemetry
	// probe produces the corresponding "absence of control" event.

	// NoHITLApproval: consequential action observed with no preceding
	// human-approval event (NO-HITL-APPROVAL tag). BLUE-AUTHZ-004.
	NoHITLApproval bool `json:"no_hitl_approval"`
	// NoRateLimit: no effective per-key/user throttling detected under load
	// (NO-RATE-LIMIT tag). BLUE-COST-001.
	NoRateLimit bool `json:"no_rate_limit"`
	// MissingAttribution: tool-call/file-access event logged without an
	// attributable identity (MISSING-ATTRIBUTION tag). BLUE-OBS-001.
	MissingAttribution bool `json:"missing_attribution"`
	// NoRuntimeDetection: runtime injection/exfil detection absent
	// (NO-RUNTIME-DETECTION tag). BLUE-OBS-004.
	NoRuntimeDetection bool `json:"no_runtime_detection"`
	// UnauthTokenReturn: an unauthenticated endpoint returned a live auth
	// token / session credential in its HTTP response. Anchored to aimap's
	// exfil_credential finding category (EXFIL-CREDENTIAL tag); the token
	// value itself is redacted at the aimap source (redactKey) and is never
	// stored. BLUE-AUTH-007. Resolved 2026-06-01 from aimap source taxonomy.
	UnauthTokenReturn bool `json:"unauth_token_return"`
	// FaviconPresent: a favicon hash was retrieved for this indexed host
	// (FAVICON-PRESENT tag, emitted by JAXEN's favicon enrichment). This is
	// the APPLICABILITY gate for BLUE-EXP-004 — the control is only scored on
	// hosts where an indexed favicon actually exists. Resolved 2026-06-01.
	FaviconPresent bool `json:"favicon_present"`
	// DefaultFaviconMatch: the host's indexed favicon hash matched a known
	// product-default favicon (DEFAULT-FAVICON / DEFAULT-FAVICON:<product>
	// tag, from JAXEN matching product-favicon-hashes.yaml). BLUE-EXP-004.
	DefaultFaviconMatch bool `json:"default_favicon_match"`
	// UnauthVerified: a probe VERIFIED the service answers without auth
	// (UNAUTH tag, e.g. aimap auth_status=="none"). BLUE-AUTH-001 gates on this
	// so it never fires on an unverified/"unknown" node — verification is the
	// load-bearing stage, not the default.
	UnauthVerified bool `json:"unauth_verified"`
}

// classifyService maps a finding's tags to a human-readable service
// class. Unrecognized tag sets fall back to a generic label — never to
// "Ollama".
func classifyService(tags []string) string {
	// Case-insensitive: upstream producers (e.g. VisorLog's aimap adapter) emit
	// the service name as the tag ("Ollama"), while this vocabulary is canonical
	// screaming-kebab ("OLLAMA"). Match regardless of case so the visorlog ->
	// visorscuba pipeline scores real exposures instead of silently passing them.
	has := func(t string) bool {
		for _, x := range tags {
			if strings.EqualFold(x, t) {
				return true
			}
		}
		return false
	}
	switch {
	case has("OLLAMA"):
		return "Ollama"
	case has("AUTOGEN-STUDIO"):
		return "AutoGen Studio"
	case has("UNAUTH-MLFLOW") || has("MLFLOW-ARTIFACT-BACKEND"):
		return "MLflow"
	case has("AZURE-BLOB-PUBLIC-LIST"):
		return "Azure Blob (public-list ACL)"
	// Browser-automation classes are checked before TRAEFIK-DEFAULT-CERT:
	// a host can carry both BROWSER-CONTROL and a default-cert tag, and
	// the browser-control identity is the load-bearing one.
	case has("BROWSERLESS"):
		return "Browserless"
	case has("UNAUTH-CDP"):
		return "Chrome DevTools Protocol"
	case has("UNAUTH-SELENIUM-GRID"):
		return "Selenium Grid"
	case has("UNAUTH-SELENOID"):
		return "Selenoid"
	case has("UNAUTH-SPLASH"):
		return "Splash render service"
	case has("PLAYWRIGHT-MCP"):
		return "Playwright MCP"
	case has("TRAEFIK-DEFAULT-CERT"):
		return "Traefik (default cert)"
	case has("AIRFLOW-EXPOSED"):
		return "Apache Airflow"
	case has("REDIS-EXPOSED"):
		return "Redis"
	case has("POSTGRES-EXPOSED"):
		return "PostgreSQL"
	// Code-assistant tier (category 09). The brand tags below are emitted
	// by aimap's code-assistant fingerprints; CODE-ASSISTANT is the class
	// tag. OpenHands is an autonomous coding-agent backend — its exposed
	// /api/v1/settings is agent-platform-class exposure (see
	// applyTagDerivations).
	case has("OPENHANDS"):
		return "OpenHands"
	case has("SOURCEGRAPH"):
		return "Sourcegraph"
	case has("SOURCEBOT"):
		return "Sourcebot"
	case has("TABNINE-CONTEXT-ENGINE"):
		return "Tabnine Context Engine"
	case has("SWEEP-AI"):
		return "Sweep AI"
	case has("DYAD"):
		return "Dyad"
	case has("REFACT"):
		return "Refact"
	case has("CODE-ASSISTANT"):
		return "Code assistant"
	case has("VLLM") || has("UNAUTH-VLLM"):
		return "vLLM inference server"
	// FinOps cost-model tier. aimap emits the mixed-case brand tags
	// "Kubecost" / "OpenCost"; the screaming-kebab variants and the
	// COST-MODEL class tag are accepted for forward compatibility.
	// These are NOT AI/ML services — routing them here keeps the generic
	// AI.C1 rule from claiming them as "Unauthenticated Ollama".
	case has("OpenCost") || has("OPENCOST"):
		return "OpenCost"
	case has("Kubecost") || has("KUBECOST"):
		return "Kubecost"
	case has("COST-MODEL"):
		return "Cost-model API"
	case has("PROMPTLAYER") || has("WEBHOOK-LEAK"):
		return "PromptLayer"
	case has("UNAUTH-API") || has("FASTAPI"):
		return "FastAPI service"
	default:
		return "AI/ML service"
	}
}

// applyTagDerivations populates the tag-derived flags on a Node. It
// replaces the old inline tag-switch in LoadFromDB and the hardcoded
// Port11434Public:true that made AI.C1 fire on every row.
func applyTagDerivations(n *Node) {
	n.ServiceClass = classifyService(n.Tags)
	for _, t := range n.Tags {
		// Normalize case so service-name-style tags ("Ollama") match the
		// canonical screaming-kebab vocabulary ("OLLAMA"). Case labels below
		// are all uppercase.
		switch strings.ToUpper(t) {
		case "TAKEOVER":
			n.AccountTakeover = true
		case "CVE-2025-63389":
			n.CVE202563389Vulnerable = true
		case "CLOUD":
			n.CloudProxy = true
		case "OLLAMA":
			// Port11434Public is Ollama-specific. Only Ollama findings
			// set it — not every VisorLog row.
			n.Port11434Public = true
		case "AUTOGEN-STUDIO", "UNAUTH-AGENT-PLATFORM", "OPENHANDS":
			// OpenHands is an autonomous coding-agent backend (ex-OpenDevin)
			// — same agent-platform exposure class as AutoGen Studio. The
			// other code-assistant tags (SOURCEGRAPH, TABNINE, etc.) are
			// completion/search services, not agent platforms, so they are
			// NOT mapped here — they score via the general ai_c1_applies
			// path on service_class alone.
			n.AgentPlatform = true
		case "AZURE-BLOB-PUBLIC-LIST":
			n.StorageACLOpen = true
		case "TRAEFIK-DEFAULT-CERT":
			n.DefaultCert = true
		case "BROWSER-CONTROL":
			n.BrowserControl = true
		case "WEBHOOK-LEAK", "LLMJACKING":
			n.WebhookLeak = true
		case "SIGNUP-OPEN":
			n.SignupOpen = true
		case "SETUP-TOKEN":
			n.SetupTokenExposed = true
		case "VLLM", "UNAUTH-VLLM":
			n.UnauthInferenceAPI = true
		case "DEFAULT-CREDS":
			n.DefaultCredentials = true
		case "OPENCOST", "KUBECOST", "COST-MODEL":
			if !n.Authenticated {
				n.CostModelAPI = true
			}
		// Blue-team control signals.
		case "NO-TLS":
			n.NoTLS = true
		case "BANNER-EXPOSED":
			n.BannerExposed = true
		case "OPENAPI-DOCS-EXPOSED":
			n.OpenAPIDocs = true
		case "INTERNAL-SAN":
			n.InternalSANExposed = true
		case "KNOWN-VULNERABLE":
			n.KnownVulnerable = true
		case "DANGEROUS-ENDPOINT-UNBLOCKED":
			n.DangerousEndpointExposed = true
		// Telemetry signals.
		case "NO-HITL-APPROVAL":
			n.NoHITLApproval = true
		case "NO-RATE-LIMIT":
			n.NoRateLimit = true
		case "MISSING-ATTRIBUTION":
			n.MissingAttribution = true
		case "NO-RUNTIME-DETECTION":
			n.NoRuntimeDetection = true
		case "EXFIL-CREDENTIAL", "EXFIL_CREDENTIAL":
			// aimap exfil_credential category: live token/credential returned
			// in an unauthenticated HTTP response. Value is redacted at source.
			n.UnauthTokenReturn = true
		case "UNAUTH":
			// VERIFIED unauthenticated (a probe confirmed open access).
			n.UnauthVerified = true
		case "AUTH":
			// VERIFIED auth-gated (401/403/login/required).
			n.Authenticated = true
		}
	}
	// Prefix-matched tags (value carried in the tag suffix).
	for _, t := range n.Tags {
		up := strings.ToUpper(t)
		// CVE tags set known_vulnerable regardless of specific CVE id.
		if strings.HasPrefix(up, "CVE-") {
			n.KnownVulnerable = true
		}
		// FAVICON-PRESENT: an indexed favicon exists (BLUE-EXP-004 applicability).
		if up == "FAVICON-PRESENT" {
			n.FaviconPresent = true
		}
		// DEFAULT-FAVICON or DEFAULT-FAVICON:<product>: matched a product default.
		// A default match implies a favicon is present.
		if strings.HasPrefix(up, "DEFAULT-FAVICON") {
			n.DefaultFaviconMatch = true
			n.FaviconPresent = true
		}
	}
}

func (n *Node) ToMap() map[string]interface{} {
	data, _ := json.Marshal(n)
	var m map[string]interface{}
	json.Unmarshal(data, &m)
	return m
}

// LoadFromDB reads all open findings from a VisorLog SQLite database.
func LoadFromDB(dbPath string) ([]*Node, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}
	defer db.Close()

	rows, err := db.Query(`
		SELECT host_ip, host_hostname, org_name, org_country,
		       sector, tld, source, tags, lifecycle_status, notes
		FROM events
		WHERE lifecycle_status = 'open'
		ORDER BY timestamp DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var nodes []*Node
	for rows.Next() {
		var tagsStr, notes string
		n := &Node{}

		rows.Scan(
			&n.HostIP, &n.HostHostname, &n.OrgName, &n.OrgCountry,
			&n.Sector, &n.TLD, &n.Source, &tagsStr, nil, &notes,
		)

		n.Tags = parseTags(tagsStr)
		applyTagDerivations(n)
		if strings.Contains(notes, "signin_url") {
			n.AccountTakeover = true
		}
		// Every open finding discovered via the survey pipeline is by
		// definition publicly indexed (JAXEN/Shodan/Censys). BLUE-EXP-001.
		n.IsIndexed = n.HostIP != ""

		nodes = append(nodes, n)
	}
	return nodes, rows.Err()
}

func parseTags(s string) []string {
	if s == "" || s == "[]" {
		return nil
	}
	var tags []string
	json.Unmarshal([]byte(s), &tags)
	return tags
}

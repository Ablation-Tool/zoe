package cmd

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/Nicholas-Kloster/visorlog/store"
	"github.com/spf13/cobra"
)

var (
	flagIngestFile   string
	flagIngestFormat string
	flagIngestSector string
	flagIngestDedup  bool
)

var ingestCmd = &cobra.Command{
	Use:   "ingest [file]",
	Short: "Ingest events from NDJSON or a VisorGoose state file",
	Args:  cobra.MaximumNArgs(1),
	Long: `Reads events from stdin (NDJSON) or a file and writes them to the database.

The input file may be given as a positional argument or with --from. With
neither, NDJSON is read from stdin, which must be a pipe.

Formats:
  ndjson        One JSON event per line (default)
  visorgoose    VisorGoose state JSON (visorgoose-state.json)
  ollama-recon  ollama-recon.py state JSON (ollama-gov-state.json etc.)
  aimap         aimap report JSON (aimap-results.json)

Examples:
  visorgoose scan | visorlog ingest
  visorlog ingest --from visorgoose-state.json --format visorgoose
  visorlog ingest --from ollama-gov-state.json --format ollama-recon
  visorlog ingest --from aimap-results.json --format aimap`,
	RunE: runIngest,
}

func init() {
	ingestCmd.Flags().StringVar(&flagIngestFile, "from", "", "read from file instead of stdin")
	ingestCmd.Flags().StringVar(&flagIngestFormat, "format", "ndjson", "input format: ndjson, visorgoose, ollama-recon, aimap")
	ingestCmd.Flags().StringVar(&flagIngestSector, "sector", "", "override sector for all ingested events")
	ingestCmd.Flags().BoolVar(&flagIngestDedup, "dedup", true, "skip IPs already in the database")
}

func runIngest(cmd *cobra.Command, args []string) error {
	db, err := store.Open(flagDB)
	if err != nil {
		return err
	}
	defer db.Close()

	// Resolve the input source. --from takes precedence; a bare positional
	// path is accepted as an alias. With neither, fall back to stdin — but
	// only when stdin is a pipe. A terminal, or a stray connected socket
	// left as stdin, means no input was given, and reading it would block
	// forever.
	srcFile := flagIngestFile
	if srcFile == "" && len(args) > 0 {
		srcFile = args[0]
	}

	var reader *os.File
	if srcFile != "" {
		reader, err = os.Open(srcFile)
		if err != nil {
			return err
		}
		defer reader.Close()
	} else {
		fi, statErr := os.Stdin.Stat()
		if statErr != nil || fi.Mode()&os.ModeNamedPipe == 0 {
			return fmt.Errorf("no input: pass a file (visorlog ingest <file> or --from FILE) or pipe NDJSON to stdin")
		}
		reader = os.Stdin
	}

	switch flagIngestFormat {
	case "visorgoose":
		return ingestVisorGoose(db, reader)
	case "ollama-recon":
		return ingestOllamaRecon(db, reader)
	case "aimap":
		return ingestAimap(db, reader)
	default:
		return ingestNDJSON(db, reader)
	}
}

func ingestNDJSON(db *store.DB, r *os.File) error {
	scanner := bufio.NewScanner(r)
	// Bump the per-line buffer cap so we can ingest events with rich
	// raw payloads (the default 64KB chokes on the larger VisorBishop
	// LiteLLM rows with 50+ model_ids).
	buf := make([]byte, 0, 1024*1024)
	scanner.Buffer(buf, 4*1024*1024)

	var inserted, skipped, duped int

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var e store.Event
		if err := json.Unmarshal(line, &e); err != nil {
			fmt.Fprintf(os.Stderr, "skip malformed line: %v\n", err)
			skipped++
			continue
		}

		// Dedup by (source, notes) when the dedup flag is set. The
		// notes field carries the unique target URL for VisorBishop
		// events; combining with source prevents collisions with
		// other ingesters that happen to share a target string.
		if flagIngestDedup && e.Source != "" && e.Notes != "" {
			exists, _ := db.NoteExists(e.Source, e.Notes)
			if exists {
				duped++
				continue
			}
		}

		if _, err := db.Insert(&e); err != nil {
			return err
		}
		inserted++
	}

	fmt.Printf("ingested %d events (%d skipped, %d deduped)\n", inserted, skipped, duped)
	return scanner.Err()
}

// visorGooseState mirrors the VisorGoose state.json structure
type visorGooseState struct {
	Nodes map[string]*visorGooseNode `json:"nodes"`
}

type visorGooseNode struct {
	IP       string              `json:"ip"`
	Hostname string              `json:"hostname"`
	Source   string              `json:"source"`
	TLD      string              `json:"tld"`
	Country  string              `json:"country"`
	Org      string              `json:"org"`
	Tags     []string            `json:"tags"`
	Services []visorGooseService `json:"services"`
}

type visorGooseService struct {
	Version    string `json:"version"`
	Vulnerable bool   `json:"vulnerable"`
	CloudProxy bool   `json:"cloud_proxy"`
	Takeover   bool   `json:"takeover"`
	Models     []struct {
		Name string `json:"name"`
	} `json:"models"`
}

func ingestVisorGoose(db *store.DB, r *os.File) error {
	var state visorGooseState
	if err := json.NewDecoder(r).Decode(&state); err != nil {
		return fmt.Errorf("decode visorgoose state: %w", err)
	}

	var inserted int
	for _, n := range state.Nodes {
		severity := store.SeverityLow
		var vulns []string

		for _, svc := range n.Services {
			if svc.Takeover {
				severity = store.SeverityCritical
			} else if svc.Vulnerable && severity != store.SeverityCritical {
				severity = store.SeverityHigh
			} else if svc.CloudProxy && severity == store.SeverityLow {
				severity = store.SeverityMedium
			}
			if svc.Vulnerable {
				vulns = append(vulns, "CVE-2025-63389")
			}
		}

		// derive sector from TLD
		sector := tldToSector(n.TLD)

		e := store.NewDiscovery(
			n.IP, n.Hostname, n.Org, n.Country,
			sector, n.TLD, "visorgoose", severity,
			n.Tags, vulns,
		)

		if _, err := db.Insert(e); err != nil {
			return err
		}
		inserted++
	}

	fmt.Printf("ingested %d nodes from VisorGoose state\n", inserted)
	return nil
}

// ollamaReconNode mirrors the ollama-recon.py state format
type ollamaReconNode struct {
	IP              string   `json:"ip"`
	Org             string   `json:"org"`
	Hostnames       []string `json:"hostnames"`
	Status          string   `json:"status"` // "live", "dead", "timeout"
	Version         string   `json:"version"`
	Models          []string `json:"models"`
	CloudProxy      bool     `json:"cloud_proxy"`
	AccountTakeover bool     `json:"account_takeover"`
	SigninURL       string   `json:"signin_url"`
	Country         string   `json:"country"`
}

func ingestOllamaRecon(db *store.DB, r *os.File) error {
	var raw map[string]ollamaReconNode
	if err := json.NewDecoder(r).Decode(&raw); err != nil {
		return fmt.Errorf("decode ollama-recon state: %w", err)
	}

	var inserted, skipped, duped int
	for _, n := range raw {
		if n.Status != "live" {
			skipped++
			continue
		}

		if flagIngestDedup {
			exists, _ := db.IPExists(n.IP)
			if exists {
				duped++
				continue
			}
		}

		hostname := ""
		if len(n.Hostnames) > 0 {
			hostname = n.Hostnames[0]
		}

		severity := store.SeverityLow
		var tags, vulns []string

		if n.AccountTakeover {
			severity = store.SeverityCritical
			tags = append(tags, "TAKEOVER")
		}
		if n.CloudProxy {
			if severity != store.SeverityCritical {
				severity = store.SeverityMedium
			}
			tags = append(tags, "CLOUD")
		}
		for _, m := range n.Models {
			ml := strings.ToLower(m)
			if strings.Contains(ml, "bge") || strings.Contains(ml, "embed") || strings.Contains(ml, "nomic") {
				tags = append(tags, "RAG")
				break
			}
		}
		for _, m := range n.Models {
			if strings.Contains(strings.ToLower(m), "distill") {
				tags = append(tags, "DISTILLED")
				break
			}
		}

		tld := extractTLD(hostname)
		sector := flagIngestSector
		if sector == "" {
			sector = tldToSector(tld)
		}

		e := store.NewDiscovery(
			n.IP, hostname, n.Org, n.Country,
			sector, tld, "ollama-recon", severity,
			tags, vulns,
		)
		if n.SigninURL != "" {
			e.Notes = "signin_url: " + n.SigninURL
		}

		if _, err := db.Insert(e); err != nil {
			return err
		}
		inserted++
	}

	fmt.Printf("ingested %d live nodes (%d dead/skipped, %d deduped) from ollama-recon state\n", inserted, skipped, duped)
	return nil
}

func extractTLD(hostname string) string {
	govTLDs := []string{".go.id", ".gov.br", ".gov.tw", ".gouv.fr", ".gob.mx",
		".go.jp", ".gov.in", ".gov.au", ".gov.uk", ".gc.ca", ".gob.es",
		".gov.cn", ".gov.za", ".go.kr", ".gov.sg", ".go.th", ".gob.ar",
		".gov.my", ".gov.ph", ".gov.pk", ".gov.vn", ".gov.ng", ".gov.eg",
		".gov", ".mil"}
	for _, tld := range govTLDs {
		if strings.HasSuffix(hostname, tld) {
			return tld
		}
	}
	// university patterns
	univSuffixes := []string{".edu", ".ac.uk", ".edu.au", ".ac.id", ".edu.br", ".ac.in"}
	for _, sfx := range univSuffixes {
		if strings.HasSuffix(hostname, sfx) {
			return sfx
		}
	}
	return ""
}

// ── aimap adapter ────────────────────────────────────────────────────────────

// aimapReport mirrors the top-level aimap JSON report format.
type aimapReport struct {
	Tool      string           `json:"tool"`
	Version   string           `json:"version"`
	OpenPorts []aimapOpenPort  `json:"open_ports"`
	Services  []aimapService   `json:"services"`
	EnumResults []aimapEnumResult `json:"enum_results"`
}

type aimapOpenPort struct {
	Host        string `json:"host"`
	Port        int    `json:"port"`
	TLS         bool   `json:"tls"`
	StatusCode  int    `json:"status_code"`
	Server      string `json:"server"`
	BodySnippet string `json:"body_snippet"`
	ContentType string `json:"content_type"`
}

type aimapService struct {
	Host     string `json:"host"`
	Port     int    `json:"port"`
	Service  string `json:"service"`
	Severity string `json:"severity"`
	BaseURL  string `json:"base_url"`
}

type aimapEnumResult struct {
	Service    string                 `json:"service"`
	Host       string                 `json:"host"`
	Port       int                    `json:"port"`
	Version    string                 `json:"version"`
	AuthStatus string                 `json:"auth_status"`
	RiskLevel  string                 `json:"risk_level"`
	RawData    map[string]interface{} `json:"raw_data,omitempty"`
}

// aimapSchemaTagsForService derives G14-bis schema tags from an aimap enum
// result. The tags are consumed by visorscuba's applyTagDerivations() which
// maps them to typed Node fields before Rego evaluation.
//
// Tag strings are the canonical G14 values from visorscuba/engine/input.go;
// any change there must be reflected here.
func aimapSchemaTagsForService(er aimapEnumResult, port int, tls bool) []string {
	var tags []string

	switch er.Service {
	case "Open WebUI":
		tags = append(tags, aimapOpenWebUITags(er, port, tls)...)
	case "LiteLLM":
		tags = append(tags, aimapLiteLLMTags(er)...)
	case "JupyterHub":
		tags = append(tags, aimapJupyterHubTags(port, tls)...)
	}

	return tags
}

// canonicalServiceTags maps an aimap service NAME to visorscuba's canonical
// class token for the cases where the raw name does not case-fold to the token:
// multi-word names ("AutoGen Studio" vs AUTOGEN-STUDIO) or a token that differs
// from the name ("MLflow" vs UNAUTH-MLFLOW). Single-token names that already
// match case-insensitively (Ollama->OLLAMA, vLLM->VLLM, OpenHands, Sourcegraph,
// Sourcebot, Dyad, Refact, Kubecost, OpenCost) need no entry. Tokens are the
// canonical values from visorscuba/engine/input.go. Exposure-bearing tokens
// (UNAUTH-MLFLOW, AIRFLOW-EXPOSED) are emitted only when the enum result shows
// the service reachable without auth, so an auth-gated instance is not mislabeled.
func canonicalServiceTags(service string, er aimapEnumResult) []string {
	switch service {
	case "AutoGen Studio":
		return []string{"AUTOGEN-STUDIO"}
	case "Tabnine Context Engine":
		return []string{"TABNINE-CONTEXT-ENGINE"}
	case "Sweep AI":
		return []string{"SWEEP-AI"}
	case "MLflow":
		if aimapUnauthExposed(er) {
			return []string{"UNAUTH-MLFLOW"}
		}
	case "Apache Airflow":
		if aimapUnauthExposed(er) {
			return []string{"AIRFLOW-EXPOSED"}
		}
	}
	return nil
}

// aimapUnauthExposed reports whether an aimap enum result indicates the service
// is reachable without authentication: no auth marker, an explicit none/open/
// unauth status, or aimap rating it high/critical risk.
func aimapUnauthExposed(er aimapEnumResult) bool {
	if er.AuthStatus == "" {
		return true
	}
	a := strings.ToLower(er.AuthStatus)
	if a == "none" || strings.Contains(a, "unauth") || strings.Contains(a, "open") {
		return true
	}
	return strings.EqualFold(er.RiskLevel, "critical") || strings.EqualFold(er.RiskLevel, "high")
}

// aimapOpenWebUITags extracts Open WebUI schema tags.
// Authoritative source: raw_data.config.features (the /api/config response).
// Falls back to auth_status string when raw_data is absent (older aimap versions).
func aimapOpenWebUITags(er aimapEnumResult, port int, tls bool) []string {
	var tags []string

	enableSignup := false
	enableLDAP := false
	enableAPIKeys := false

	if er.RawData != nil {
		if cfg, ok := er.RawData["config"].(map[string]interface{}); ok {
			if feats, ok := cfg["features"].(map[string]interface{}); ok {
				enableSignup = boolFeature(feats, "enable_signup")
				enableLDAP = boolFeature(feats, "enable_ldap")
				// aimap <0.8.x uses "enable_api_key" (singular); ≥0.8 uses "enable_api_keys"
				enableAPIKeys = boolFeature(feats, "enable_api_keys") || boolFeature(feats, "enable_api_key")
			}
		}
	} else {
		// Fallback: auth_status string for older aimap output without raw_data
		if strings.Contains(er.AuthStatus, "open registration") || strings.Contains(er.AuthStatus, "signup") {
			enableSignup = true
		}
	}

	if enableSignup {
		tags = append(tags, "OPENWEBUI-SIGNUP-OPEN")
		tags = append(tags, "SIGNUP-OPEN-ATO") // generic ATO catch-all; G14 uses SIGNUP-OPEN-ATO not SIGNUP-OPEN-ACCOUNT-TAKEOVER
	}
	if enableLDAP {
		tags = append(tags, "OPENWEBUI-LDAP-ENABLED")
	}
	if enableAPIKeys {
		tags = append(tags, "OPENWEBUI-API-KEYS-ENABLED")
	}

	// HTTP-only transport (no TLS, port not 443)
	if !tls && port != 443 {
		tags = append(tags, "TRANSPORT-DOWNGRADE")
	}

	return tags
}

// aimapLiteLLMTags extracts LiteLLM schema tags.
// LiteLLM has no aimap enumerator yet; auth_status will be empty. Tags
// fire only when aimap adds enum support — wired now, no-op until then.
func aimapLiteLLMTags(er aimapEnumResult) []string {
	var tags []string

	switch er.AuthStatus {
	case "AUTH_DISABLED":
		tags = append(tags, "LITELLM-AUTH-DISABLED")
	case "PUBLIC_OPENAPI":
		tags = append(tags, "LITELLM-OPENAPI-PUBLIC")
		tags = append(tags, "OPENAPI-PUBLIC-LEAK")
	}

	// Check raw_data for public providers indicator
	if er.RawData != nil {
		if _, ok := er.RawData["public_providers"]; ok {
			tags = append(tags, "LITELLM-PUBLIC-PROVIDERS")
		}
	}

	return tags
}

// aimapJupyterHubTags emits JUPYTERHUB-HTTP-ONLY when the hub is on plain HTTP.
// aimap fingerprints "Jupyter Notebook" not "JupyterHub"; this function is
// wired for future parity when aimap adds a JupyterHub fingerprint.
func aimapJupyterHubTags(port int, tls bool) []string {
	if !tls && port != 443 {
		return []string{"JUPYTERHUB-HTTP-ONLY", "TRANSPORT-DOWNGRADE"}
	}
	return nil
}

// boolFeature safely reads a bool from a map[string]interface{} features block.
func boolFeature(feats map[string]interface{}, key string) bool {
	v, ok := feats[key]
	if !ok {
		return false
	}
	b, ok := v.(bool)
	return ok && b
}

func ingestAimap(db *store.DB, r *os.File) error {
	var report aimapReport
	if err := json.NewDecoder(r).Decode(&report); err != nil {
		return fmt.Errorf("decode aimap report: %w", err)
	}

	// Build enum index keyed by "host:port" for description enrichment.
	enumIdx := make(map[string]aimapEnumResult, len(report.EnumResults))
	for _, er := range report.EnumResults {
		key := fmt.Sprintf("%s:%d", er.Host, er.Port)
		enumIdx[key] = er
	}

	// Track which host:port pairs have a service record so open_ports entries
	// for the same endpoint are not double-counted.
	serviceKeys := make(map[string]bool, len(report.Services))

	var inserted, duped int

	// Primary pass: services[] — carry severity + platform identity.
	for _, svc := range report.Services {
		key := fmt.Sprintf("%s:%d", svc.Host, svc.Port)
		serviceKeys[key] = true

		if flagIngestDedup {
			exists, _ := db.IPExists(svc.Host)
			if exists {
				duped++
				continue
			}
		}

		severity := svc.Severity
		if severity == "" {
			severity = store.SeverityInfo
		}

		title := fmt.Sprintf("%s on %s:%d", svc.Service, svc.Host, svc.Port)

		desc := fmt.Sprintf("service=%s base_url=%s", svc.Service, svc.BaseURL)

		// G14-bis: derive schema tags from enum result before building the event.
		// TLS is inferred from the base_url scheme (services[] has no tls field).
		tlsFromURL := strings.HasPrefix(svc.BaseURL, "https://")
		schemaTags := []string{svc.Service}
		er, hasEnum := enumIdx[key]
		if hasEnum {
			if er.AuthStatus != "" {
				desc += fmt.Sprintf(" auth=%s", er.AuthStatus)
			}
			if er.RiskLevel != "" {
				desc += fmt.Sprintf(" risk=%s", er.RiskLevel)
			}
			if er.Version != "" {
				desc += fmt.Sprintf(" version=%s", er.Version)
			}
			schemaTags = append(schemaTags, aimapSchemaTagsForService(er, svc.Port, tlsFromURL)...)
		}
		// Canonicalize the service name to visorscuba's class token where the raw
		// name does not case-fold to it (er is the zero value when no enum result).
		schemaTags = append(schemaTags, canonicalServiceTags(svc.Service, er)...)

		sector := flagIngestSector
		if sector == "" {
			sector = store.SectorCommercial
		}

		e := store.NewDiscovery(
			svc.Host, "", "", "",
			sector, "", "aimap", severity,
			schemaTags, nil,
		)
		e.Notes = desc
		e.Raw = map[string]interface{}{
			"title":    title,
			"port":     svc.Port,
			"base_url": svc.BaseURL,
		}

		if _, err := db.Insert(e); err != nil {
			return err
		}
		inserted++
	}

	// Supplementary pass: open_ports[] entries not already covered by services[].
	for _, op := range report.OpenPorts {
		key := fmt.Sprintf("%s:%d", op.Host, op.Port)
		if serviceKeys[key] {
			continue // already recorded via services[]
		}

		if flagIngestDedup {
			exists, _ := db.IPExists(op.Host)
			if exists {
				duped++
				continue
			}
		}

		serviceClass := op.Server
		if serviceClass == "" {
			serviceClass = "unknown"
		}

		title := fmt.Sprintf("%s on %s:%d", serviceClass, op.Host, op.Port)

		snippet := op.BodySnippet
		if len(snippet) > 120 {
			snippet = snippet[:120]
		}
		desc := fmt.Sprintf("server=%s status=%d content_type=%s snippet=%q",
			op.Server, op.StatusCode, op.ContentType, snippet)

		sector := flagIngestSector
		if sector == "" {
			sector = store.SectorCommercial
		}

		e := store.NewDiscovery(
			op.Host, "", "", "",
			sector, "", "aimap", store.SeverityInfo,
			nil, nil,
		)
		e.Notes = desc
		e.Raw = map[string]interface{}{
			"title":       title,
			"port":        op.Port,
			"status_code": op.StatusCode,
			"server":      op.Server,
		}

		if _, err := db.Insert(e); err != nil {
			return err
		}
		inserted++
	}

	fmt.Printf("ingested %d events (%d deduped) from aimap report\n", inserted, duped)
	return nil
}

func tldToSector(tld string) string {
	govTLDs := []string{".gov", ".go.id", ".gov.br", ".gov.tw",
		".gouv.fr", ".gob.mx", ".go.jp", ".gov.in", ".gov.au",
		".gov.uk", ".gc.ca", ".gob.es", ".gov.cn", ".gov.za",
		".go.kr", ".gov.sg", ".go.th", ".gob.ar", ".gov.my",
		".gov.ph", ".gov.pk", ".gov.vn", ".gov.ng", ".gov.eg"}
	for _, g := range govTLDs {
		if tld == g {
			return store.SectorGovernment
		}
	}
	if tld == ".mil" {
		return store.SectorMilitary
	}
	univTLDs := []string{".edu", ".ac.uk", ".edu.au", ".ac.id", ".edu.br",
		".ac.in", ".edu.cn", ".ac.kr", ".ac.jp", ".edu.tw",
		".ac.za", ".edu.sg", ".ac.nz", ".edu.mx", ".edu.ph"}
	for _, u := range univTLDs {
		if tld == u {
			return store.SectorUniversity
		}
	}
	return store.SectorCommercial
}

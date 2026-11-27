// Package adapters maps source-specific survey formats into the unified
// observation stream (normalize.Response). Each adapter is a thin mapper from
// one real source onto the common fields the normalizer fingerprints. The
// recon that justifies the choice of source: empire.db carries no product on
// most rows and nuclide.db events are generic, so cat32-style survey JSON is
// the source that actually carries a service fingerprint (platform, status,
// banner, server).
package adapters

import (
	"bufio"
	"encoding/json"
	"os"
	"sort"
	"strconv"
	"strings"

	"github.com/nuclide-research/VisorCAS/normalize"
)

type shodanItem struct {
	IP       string  `json:"ip"`
	Port     flexInt `json:"port"`
	Platform string  `json:"platform"`
	Status   flexInt `json:"status"`
	Server   string   `json:"server"`
	Banner   string   `json:"banner"`
	Title    string   `json:"title"`
	Tags     []string `json:"tags"` // Shodan host labels; the honeypot tag drives the screen's deception refute
}

// ShodanResults reads cat32-style Shodan survey JSON (a list of host records)
// and maps each to an observation tagged with source. Body is the stable Server
// string rather than the raw banner, so the volatile HTTP Date header never
// perturbs the fingerprint; Content-Type is parsed out of the banner.
func ShodanResults(path, source string) ([]normalize.Response, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var items []shodanItem
	if err := json.Unmarshal(raw, &items); err != nil {
		return nil, err
	}
	out := make([]normalize.Response, 0, len(items))
	for _, it := range items {
		out = append(out, normalize.Response{
			Signature:   it.Platform,
			Port:        int(it.Port),
			Status:      int(it.Status),
			ContentType: contentType(it.Banner),
			Body:        it.Server,
			Source:      source,
			IP:          it.IP,
			Tags:        it.Tags,
		})
	}
	return out, nil
}

// --- scanner: the nuclide-research/scanner banner-grabber as a second source ---

type scannerResult struct {
	IP       string `json:"ip"`
	Port     int    `json:"port"`
	Protocol string `json:"protocol"`
	Version  string `json:"version"`
	OS       string `json:"os"`
	Banner   string `json:"banner"`
}

// ScannerResults reads the nuclide-research/scanner JSONL output (one ScanResult
// per line) and maps each to an observation. The scanner identifies the transport
// service (nginx, uvicorn), never the AI platform, and never determines auth - so
// the observation is auth-unknown by construction. Its value is as a SECOND SOURCE
// for fuse (corroborating aimap and surfacing Shodan-dark hosts), not the screen,
// whose signatures key on AI-service identity the scanner does not produce.
func ScannerResults(path, source string) ([]normalize.Response, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []normalize.Response
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<20) // banners can exceed the default 64KB line cap
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var r scannerResult
		if err := json.Unmarshal([]byte(line), &r); err != nil {
			continue // skip a malformed line rather than abort the stream
		}
		sig := r.OS
		if sig == "" {
			sig = r.Version
		}
		if sig == "" {
			sig = r.Protocol
		}
		out = append(out, normalize.Response{
			Signature:   sig,
			Port:        r.Port,
			AuthStatus:  normalize.AuthUnknown,
			Status:      parseHTTPStatus(r.Banner),
			ContentType: contentType(r.Banner),
			Body:        httpBody(r.Banner),
			Source:      source,
			IP:          r.IP,
		})
	}
	return out, sc.Err()
}

// parseHTTPStatus pulls the status code from a banner's first line
// ("HTTP/1.1 404 Not Found" -> 404). Returns 0 when the banner is not HTTP.
func parseHTTPStatus(banner string) int {
	first := banner
	if i := strings.IndexAny(banner, "\r\n"); i >= 0 {
		first = banner[:i]
	}
	parts := strings.Fields(first)
	if len(parts) >= 2 && strings.HasPrefix(parts[0], "HTTP/") {
		if n, err := strconv.Atoi(parts[1]); err == nil {
			return n
		}
	}
	return 0
}

// httpBody returns the response body portion of a banner (after the header break)
// so the screen's evidence-based signatures see real content, not headers.
func httpBody(banner string) string {
	if i := strings.Index(banner, "\r\n\r\n"); i >= 0 {
		return banner[i+4:]
	}
	return ""
}

// flexInt unmarshals an int from either a JSON number or a JSON string, since
// survey exports are inconsistent about quoting port and status. Non-numeric or
// missing values become 0.
type flexInt int

func (f *flexInt) UnmarshalJSON(b []byte) error {
	s := strings.Trim(string(b), `"`)
	if s == "" || s == "null" {
		*f = 0
		return nil
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		*f = 0
		return nil
	}
	*f = flexInt(n)
	return nil
}

// --- aimap: the production observation source ---

type aimapFinding struct {
	Category string `json:"category"`
}

type aimapEnum struct {
	Service    string         `json:"service"`
	Host       string         `json:"host"`
	Port       int            `json:"port"`
	AuthStatus string         `json:"auth_status"`
	Findings   []aimapFinding `json:"findings"`
}

type aimapOpenPort struct {
	Host        string `json:"host"`
	Port        int    `json:"port"`
	StatusCode  int    `json:"status_code"`
	ContentType string `json:"content_type"`
	BodySnippet string `json:"body_snippet"`
}

type aimapScanReport struct {
	Timestamp   string          `json:"timestamp"`
	OpenPorts   []aimapOpenPort `json:"open_ports"`
	EnumResults []aimapEnum     `json:"enum_results"`
}

// AimapReport reads an aimap ScanReport (aimap-report.json) and maps each
// enum_result to an observation tagged with source. This is the production
// source: it carries aimap's verified auth_status (translated to the 3-way axis)
// and the finding categories that key the fingerprint.
func AimapReport(path, source string) ([]normalize.Response, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rep aimapScanReport
	if err := json.Unmarshal(raw, &rep); err != nil {
		return nil, err
	}
	evidence := evidenceMap(rep.OpenPorts)
	out := make([]normalize.Response, 0, len(rep.EnumResults))
	for _, e := range rep.EnumResults {
		out = append(out, aimapObs(e, evidence, source, rep.Timestamp))
	}
	return out, nil
}

// evidenceMap indexes open_ports by host:port for the enum_result join.
func evidenceMap(ops []aimapOpenPort) map[string]aimapOpenPort {
	m := make(map[string]aimapOpenPort, len(ops))
	for _, op := range ops {
		m[op.Host+":"+strconv.Itoa(op.Port)] = op
	}
	return m
}

// aimapObs builds one observation from an enum_result, joining the open_ports
// evidence (status / content-type / body snippet) by host:port.
func aimapObs(e aimapEnum, evidence map[string]aimapOpenPort, source, ts string) normalize.Response {
	r := normalize.Response{
		Signature:  e.Service,
		Port:       e.Port,
		AuthStatus: mapAimapAuth(e.AuthStatus),
		Categories: enumCategories(e.Findings),
		Source:     source,
		IP:         e.Host,
		ObservedAt: ts,
	}
	if op, ok := evidence[e.Host+":"+strconv.Itoa(e.Port)]; ok {
		r.Status = op.StatusCode
		r.ContentType = op.ContentType
		r.Body = op.BodySnippet
	}
	return r
}

// FilterAimapReport reads an aimap report, applies keep to each enum_result's
// observation (with open_ports evidence joined), and returns the report with the
// rejected enum_results removed and every other field preserved verbatim. The
// filtered report is a drop-in for aimap-to-findings -> visorlog, so gating slots
// in without changing the converter.
func FilterAimapReport(path, source string, tags map[string][]string, keep func(normalize.Response) bool) (filtered []byte, kept, dropped int, err error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, 0, 0, err
	}
	var top map[string]json.RawMessage
	if err := json.Unmarshal(raw, &top); err != nil {
		return nil, 0, 0, err
	}
	var ts string
	if b, ok := top["timestamp"]; ok {
		_ = json.Unmarshal(b, &ts)
	}
	var ops []aimapOpenPort
	if b, ok := top["open_ports"]; ok {
		_ = json.Unmarshal(b, &ops)
	}
	evidence := evidenceMap(ops)

	var rawEnums []json.RawMessage
	if b, ok := top["enum_results"]; ok {
		if err := json.Unmarshal(b, &rawEnums); err != nil {
			return nil, 0, 0, err
		}
	}
	keptRaws := make([]json.RawMessage, 0, len(rawEnums))
	for _, re := range rawEnums {
		var e aimapEnum
		if err := json.Unmarshal(re, &e); err != nil {
			return nil, 0, 0, err
		}
		obs := aimapObs(e, evidence, source, ts)
		if t, ok := tags[obs.IP]; ok {
			obs.Tags = t
		}
		if keep(obs) {
			keptRaws = append(keptRaws, re)
			kept++
		} else {
			dropped++
		}
	}
	keptJSON, err := json.Marshal(keptRaws)
	if err != nil {
		return nil, 0, 0, err
	}
	top["enum_results"] = keptJSON
	filtered, err = json.MarshalIndent(top, "", "  ")
	if err != nil {
		return nil, 0, 0, err
	}
	return filtered, kept, dropped, nil
}

// mapAimapAuth translates aimap's free-text auth_status into the normalized
// 3-way axis. aimap uses many phrasings ("none", "none (admin claimable)",
// "OPEN_API", "required (HTTP 401)", "on", "oauth"...): anything none/open is
// verified unauth, unknown/empty is auth-unknown, the rest is verified auth.
func mapAimapAuth(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	switch {
	case s == "" || strings.Contains(s, "unknown"):
		return normalize.AuthUnknown
	case strings.Contains(s, "none") || strings.Contains(s, "open"):
		return normalize.AuthUnauth
	default:
		return normalize.AuthOn
	}
}

// enumCategories returns the sorted, de-duplicated set of finding categories.
func enumCategories(fs []aimapFinding) []string {
	seen := map[string]bool{}
	var out []string
	for _, f := range fs {
		if f.Category != "" && !seen[f.Category] {
			seen[f.Category] = true
			out = append(out, f.Category)
		}
	}
	sort.Strings(out)
	return out
}

// contentType pulls the Content-Type value from a raw HTTP banner, dropping any
// "; charset=..." parameter. Returns "" if absent.
func contentType(banner string) string {
	const key = "content-type:"
	for _, line := range strings.Split(banner, "\n") {
		line = strings.TrimSpace(line)
		if len(line) >= len(key) && strings.EqualFold(line[:len(key)], key) {
			v := strings.TrimSpace(line[len(key):])
			if i := strings.IndexByte(v, ';'); i >= 0 {
				v = strings.TrimSpace(v[:i])
			}
			return v
		}
	}
	return ""
}

// ── Shodan tag enrichment ─────────────────────────────────────────────────────
// The aimap report carries no host labels, so the screen's honeypot-host-tagged
// signature cannot fire on an aimap-sourced run without a join. LoadShodanTags +
// ApplyShodanTags productize that join (hand-rolled across Cat-01/03/04): a tags
// file (the list form the Shodan producer emits) -> ip->tags map -> attached to
// observations by IP. VisorCAS stays offline; the Shodan fetch lives upstream.

type shodanTagRecord struct {
	IP   string   `json:"ip"`
	Tags []string `json:"tags"`
}

// LoadShodanTags reads a JSON array of {ip, tags} records into an ip->tags map.
// Extra fields (port, platform, ...) are ignored, so a full shodan-results file
// works directly as the tag source.
func LoadShodanTags(path string) (map[string][]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var recs []shodanTagRecord
	if err := json.Unmarshal(raw, &recs); err != nil {
		return nil, err
	}
	m := make(map[string][]string, len(recs))
	for _, r := range recs {
		if r.IP != "" && len(r.Tags) > 0 {
			m[r.IP] = r.Tags
		}
	}
	return m, nil
}

// ApplyShodanTags attaches host tags to observations by IP, in place. An IP with
// no entry is left untouched (its Tags stays nil) - never invents evidence.
func ApplyShodanTags(obs []normalize.Response, tags map[string][]string) {
	if len(tags) == 0 {
		return
	}
	for i := range obs {
		if t, ok := tags[obs[i].IP]; ok {
			obs[i].Tags = t
		}
	}
}

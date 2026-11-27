package adapters

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/nuclide-research/VisorCAS/normalize"
)

func write(t *testing.T, body string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "src.json")
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func fp(r normalize.Response) string { return string(normalize.Fingerprint(r)) }

// Maps cat32-shodan-results records, tags the source, parses Content-Type out of
// the banner, and (via the normalizer) collapses same-service hosts.
func TestShodanResultsMapsAndCollapses(t *testing.T) {
	p := write(t, `[
{"ip":"1.1.1.1","port":"8001","platform":"kong-admin-api","status":"200","server":"kong/3.6.1","banner":"HTTP/1.1 200 OK\r\nDate: Mon, 01 Jun 2026 12:28:23 GMT\r\nContent-Type: application/json; charset=utf-8\r\n"},
{"ip":"2.2.2.2","port":"8001","platform":"kong-admin-api","status":"200","server":"kong/3.6.1","banner":"HTTP/1.1 200 OK\r\nDate: Tue, 02 Jun 2026 09:00:00 GMT\r\nContent-Type: application/json; charset=utf-8\r\n"},
{"ip":"3.3.3.3","port":"11434","platform":"ollama","status":"200","server":"","banner":"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"}
]`)
	obs, err := ShodanResults(p, "shodan")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 3 {
		t.Fatalf("got %d observations, want 3", len(obs))
	}
	if obs[0].Source != "shodan" {
		t.Errorf("source = %q, want shodan", obs[0].Source)
	}
	if obs[0].Signature != "kong-admin-api" || obs[0].Port != 8001 || obs[0].Status != 200 {
		t.Errorf("field mapping wrong: %+v", obs[0])
	}
	if obs[0].ContentType != "application/json" {
		t.Errorf("content-type = %q, want application/json (parsed from banner)", obs[0].ContentType)
	}
	// Two kong hosts differ only by IP and the volatile Date header -> one pattern.
	if fp(obs[0]) != fp(obs[1]) {
		t.Errorf("same service on two hosts did not collapse:\n a=%s\n b=%s", fp(obs[0]), fp(obs[1]))
	}
	// ollama is a different service -> distinct.
	if fp(obs[0]) == fp(obs[2]) {
		t.Error("distinct services collided")
	}
}

// Shodan host records carry a tags array (database, ai, honeypot, ...). The
// adapter must carry it onto the observation so the screen's honeypot signature
// can refute deception surfaces on host evidence, not service identity.
func TestShodanResultsCarriesTags(t *testing.T) {
	p := write(t, `[
{"ip":"13.125.251.76","port":"3001","platform":"MCP Server","status":"200","server":"","banner":"HTTP/1.1 200 OK\r\n","tags":["database","ai","honeypot","cloud"]}
]`)
	obs, err := ShodanResults(p, "shodan")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 1 {
		t.Fatalf("got %d observations, want 1", len(obs))
	}
	want := []string{"database", "ai", "honeypot", "cloud"}
	if len(obs[0].Tags) != len(want) {
		t.Fatalf("tags = %v, want %v", obs[0].Tags, want)
	}
	for i, w := range want {
		if obs[0].Tags[i] != w {
			t.Errorf("tags[%d] = %q, want %q", i, obs[0].Tags[i], w)
		}
	}
}

// Real cat32 data encodes port and status as JSON numbers, not strings; the
// adapter must accept both forms.
func TestShodanResultsAcceptsNumericPortStatus(t *testing.T) {
	p := write(t, `[{"ip":"1.1.1.1","port":8001,"platform":"kong","status":200,"server":"kong/3.6.1","banner":""}]`)
	obs, err := ShodanResults(p, "shodan")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 1 || obs[0].Port != 8001 || obs[0].Status != 200 {
		t.Fatalf("numeric port/status not handled: %+v", obs)
	}
}

func TestShodanResultsMissingFileErrors(t *testing.T) {
	if _, err := ShodanResults("/nonexistent/nope.json", "shodan"); err == nil {
		t.Fatal("expected an error for a missing file")
	}
}

func TestShodanResultsBadJSONErrors(t *testing.T) {
	p := write(t, `{not a list}`)
	if _, err := ShodanResults(p, "shodan"); err == nil {
		t.Fatal("expected an error for malformed JSON")
	}
}

// AimapReport is the production source: it maps aimap enum_results to
// observations, translating aimap's free-text auth_status to the 3-way axis and
// collecting finding categories into the fingerprint.
func TestAimapReportMapsAuthAndCategories(t *testing.T) {
	p := write(t, `{
"tool":"aimap","timestamp":"2026-06-03T00:00:00Z",
"enum_results":[
 {"service":"MLflow","host":"1.1.1.1","port":5000,"auth_status":"none","risk_level":"critical","findings":[{"category":"unauth_data"},{"category":"rce"}]},
 {"service":"MLflow","host":"2.2.2.2","port":5000,"auth_status":"none","risk_level":"critical","findings":[{"category":"rce"},{"category":"unauth_data"}]},
 {"service":"Kubecost","host":"3.3.3.3","port":9090,"auth_status":"unknown","risk_level":"info","findings":[{"category":"cors"}]},
 {"service":"Langfuse","host":"4.4.4.4","port":3000,"auth_status":"required (HTTP 401)","risk_level":"info","findings":[]}
]}`)
	obs, err := AimapReport(p, "aimap")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 4 {
		t.Fatalf("got %d observations, want 4", len(obs))
	}
	if obs[0].Source != "aimap" || obs[0].Signature != "MLflow" || obs[0].IP != "1.1.1.1" || obs[0].Port != 5000 {
		t.Errorf("field mapping wrong: %+v", obs[0])
	}
	if obs[0].AuthStatus != normalize.AuthUnauth {
		t.Errorf(`auth "none" -> %q, want unauth`, obs[0].AuthStatus)
	}
	if obs[2].AuthStatus != normalize.AuthUnknown {
		t.Errorf(`auth "unknown" -> %q, want auth-unknown`, obs[2].AuthStatus)
	}
	if obs[3].AuthStatus != normalize.AuthOn {
		t.Errorf(`auth "required (HTTP 401)" -> %q, want auth`, obs[3].AuthStatus)
	}
	if got := obs[0].Categories; len(got) != 2 || got[0] != "rce" || got[1] != "unauth_data" {
		t.Errorf("categories = %v, want [rce unauth_data]", got)
	}
	// same service/port/auth/categories collapse despite category order and host
	if fp(obs[0]) != fp(obs[1]) {
		t.Error("identical MLflow patterns on two hosts did not collapse")
	}
	if fp(obs[0]) == fp(obs[2]) {
		t.Error("MLflow and Kubecost collided")
	}
}

func TestAimapReportMissingFileErrors(t *testing.T) {
	if _, err := AimapReport("/nonexistent/nope.json", "aimap"); err == nil {
		t.Fatal("expected an error for a missing file")
	}
}

// enum_results carry no status/body; those live in open_ports[]. The adapter
// must join them by host:port so the evidence-based FP signatures can fire.
func TestAimapReportJoinsOpenPortEvidence(t *testing.T) {
	p := write(t, `{
"timestamp":"2026-06-03T00:00:00Z",
"open_ports":[
 {"host":"1.1.1.1","port":80,"status_code":200,"content_type":"text/html","body_snippet":"<!doctype html>"}
],
"enum_results":[
 {"service":"gcp-metadata","host":"1.1.1.1","port":80,"auth_status":"unknown","findings":[]}
]}`)
	obs, err := AimapReport(p, "menlohunt")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 1 {
		t.Fatalf("got %d observations, want 1", len(obs))
	}
	if obs[0].Status != 200 || obs[0].ContentType != "text/html" || obs[0].Body != "<!doctype html>" {
		t.Errorf("open_port evidence was not joined into the observation: %+v", obs[0])
	}
}

// FilterAimapReport drops enum_results the keep predicate rejects and re-emits
// the report with every other field preserved verbatim.
func TestFilterAimapReportDropsAndPreserves(t *testing.T) {
	p := write(t, `{
"tool":"aimap","version":"1.9","timestamp":"2026-06-03T00:00:00Z",
"summary":{"total_findings":2},
"open_ports":[{"host":"1.1.1.1","port":80,"status_code":200,"content_type":"text/html","body_snippet":"<!doctype html>"}],
"enum_results":[
 {"service":"gcp-metadata","host":"1.1.1.1","port":80,"auth_status":"unknown","findings":[]},
 {"service":"weaviate","host":"2.2.2.2","port":8080,"auth_status":"none","findings":[{"category":"unauth_data"}]}
]}`)
	filtered, kept, dropped, err := FilterAimapReport(p, "aimap", nil, func(r normalize.Response) bool {
		return r.Signature != "gcp-metadata"
	})
	if err != nil {
		t.Fatal(err)
	}
	if kept != 1 || dropped != 1 {
		t.Fatalf("kept=%d dropped=%d, want 1/1", kept, dropped)
	}
	var out map[string]any
	if err := json.Unmarshal(filtered, &out); err != nil {
		t.Fatal(err)
	}
	if out["tool"] != "aimap" || out["summary"] == nil || out["open_ports"] == nil {
		t.Errorf("top-level fields not preserved: %v", out)
	}
	er, _ := out["enum_results"].([]any)
	if len(er) != 1 {
		t.Fatalf("enum_results len = %d, want 1", len(er))
	}
	if survivor, _ := er[0].(map[string]any); survivor["service"] != "weaviate" {
		t.Errorf("survivor = %v, want weaviate", er[0])
	}
}

// ScannerResults maps the nuclide-research/scanner JSONL (one ScanResult per
// line: ip/port/protocol/version/os/banner) into observations. The scanner names
// the transport service (nginx/uvicorn), never determines auth -> auth-unknown by
// construction. Its role is a second source for fuse, not the screen.
func TestScannerResultsMapsJSONL(t *testing.T) {
	p := write(t, `{"ip":"1.2.3.4","port":8000,"protocol":"HTTP","version":"uvicorn","os":"","banner":"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nServer: uvicorn\r\n\r\n{\"detail\":\"Not Found\"}","timestamp":1780550363}
{"ip":"5.6.7.8","port":80,"protocol":"HTTP","version":"nginx/1.29.7","os":"Nginx","banner":"HTTP/1.1 200 OK\r\nServer: nginx/1.29.7\r\nContent-Type: text/html\r\n\r\n<!doctype html><html></html>","timestamp":1780550363}`)
	obs, err := ScannerResults(p, "scanner")
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 2 {
		t.Fatalf("got %d observations, want 2", len(obs))
	}
	// os empty -> signature falls back to version
	if obs[0].IP != "1.2.3.4" || obs[0].Port != 8000 || obs[0].Signature != "uvicorn" {
		t.Errorf("map wrong: %+v", obs[0])
	}
	if obs[0].Status != 404 {
		t.Errorf("status = %d, want 404 (parsed from banner status line)", obs[0].Status)
	}
	if obs[0].ContentType != "application/json" {
		t.Errorf("content-type = %q, want application/json", obs[0].ContentType)
	}
	if obs[0].AuthStatus != normalize.AuthUnknown {
		t.Errorf("auth = %q, want auth-unknown (scanner never determines auth)", obs[0].AuthStatus)
	}
	if obs[0].Source != "scanner" {
		t.Errorf("source = %q, want scanner", obs[0].Source)
	}
	// os present -> signature is the os product
	if obs[1].Signature != "Nginx" || obs[1].Status != 200 {
		t.Errorf("second map wrong: %+v", obs[1])
	}
}

// The predicate must receive the open_ports evidence joined in, or the screen
// (which keys on body/content-type) can never fire during gating.
func TestFilterAimapReportJoinsEvidenceForPredicate(t *testing.T) {
	p := write(t, `{"timestamp":"t","open_ports":[{"host":"1.1.1.1","port":80,"content_type":"text/html","body_snippet":"<!doctype html>"}],"enum_results":[{"service":"x","host":"1.1.1.1","port":80,"auth_status":"none","findings":[]}]}`)
	var gotBody, gotCT string
	if _, _, _, err := FilterAimapReport(p, "aimap", nil, func(r normalize.Response) bool {
		gotBody, gotCT = r.Body, r.ContentType
		return true
	}); err != nil {
		t.Fatal(err)
	}
	if gotBody != "<!doctype html>" || gotCT != "text/html" {
		t.Errorf("evidence not joined for the predicate: body=%q ct=%q", gotBody, gotCT)
	}
}

// Shodan tags carry the honeypot/deception evidence the aimap report itself lacks.
// LoadShodanTags reads the list form the Shodan producer emits ([{ip,tags}, ...],
// extra fields ignored) into an ip->tags map; ApplyShodanTags attaches them to
// observations by IP so the screen's honeypot-host-tagged sig fires on an
// aimap-sourced run. Sourced to Cat-01/03/04: the join was hand-rolled 3x.
func TestLoadShodanTags(t *testing.T) {
	p := write(t, `[
{"ip":"1.1.1.1","port":3001,"platform":"MCP Server","tags":["ai","honeypot","cloud"]},
{"ip":"2.2.2.2","tags":["cloud"]}
]`)
	m, err := LoadShodanTags(p)
	if err != nil {
		t.Fatal(err)
	}
	if want := []string{"ai", "honeypot", "cloud"}; len(m["1.1.1.1"]) != 3 || m["1.1.1.1"][1] != "honeypot" {
		t.Errorf("tags[1.1.1.1] = %v, want %v", m["1.1.1.1"], want)
	}
	if len(m["2.2.2.2"]) != 1 {
		t.Errorf("tags[2.2.2.2] = %v, want [cloud]", m["2.2.2.2"])
	}
}

func TestApplyShodanTags(t *testing.T) {
	obs := []normalize.Response{
		{Signature: "MCP Server", IP: "1.1.1.1"},
		{Signature: "ClearML", IP: "9.9.9.9"}, // no tags entry
	}
	ApplyShodanTags(obs, map[string][]string{"1.1.1.1": {"ai", "honeypot"}})
	if len(obs[0].Tags) != 2 || obs[0].Tags[1] != "honeypot" {
		t.Errorf("obs[0].Tags = %v, want [ai honeypot]", obs[0].Tags)
	}
	if obs[1].Tags != nil {
		t.Errorf("obs[1] (no entry) should be untouched, got Tags=%v", obs[1].Tags)
	}
}

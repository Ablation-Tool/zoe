package assetrec

import (
	"encoding/json"
	"testing"

	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
)

// allowed is the closed set of top-level keys the schema permits
// (additionalProperties:false). Emitting anything else fails validation.
var allowed = map[string]bool{
	"schema_version": true, "asset": true, "source": true, "timestamp": true,
	"classification": true, "findings": true, "services": true,
	"attribution": true, "lifecycle": true, "raw": true,
}

func TestRecordConformsToSchema(t *testing.T) {
	r := normalize.Response{Signature: "prometheus", IP: "10.0.0.1", Port: 9090, AuthStatus: "unauth", ObservedAt: "2026-06-03T00:00:00Z"}
	b, _ := json.Marshal(Record(r, ledger.Misidentification, "abc123", "cat-31"))
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}

	if m["schema_version"] != "1.1.0" {
		t.Errorf("schema_version = %v, want 1.1.0", m["schema_version"])
	}
	asset, _ := m["asset"].(map[string]any)
	if asset["ip"] != "10.0.0.1" || asset["port"].(float64) != 9090 {
		t.Errorf("asset = %v", asset)
	}
	src, _ := m["source"].(map[string]any)
	if src["tool"] != "visorcas" {
		t.Errorf("source.tool = %v, want visorcas", src["tool"])
	}
	if m["timestamp"] != "2026-06-03T00:00:00Z" {
		t.Errorf("timestamp = %v", m["timestamp"])
	}
	// the schema has no FP/disposition field: it must ride in raw
	raw, _ := m["raw"].(map[string]any)
	if raw["disposition"] != "misidentification" {
		t.Errorf("raw.disposition = %v", raw["disposition"])
	}
	if raw["fp_hash"] != "abc123" {
		t.Errorf("raw.fp_hash = %v", raw["fp_hash"])
	}
	// additionalProperties:false - no key outside the schema's set
	for k := range m {
		if !allowed[k] {
			t.Errorf("emitted non-schema top-level key %q", k)
		}
	}
}

func TestDeceptionMapsToHoneypotClassification(t *testing.T) {
	r := normalize.Response{Signature: "honeypot", IP: "1.2.3.4", Port: 80, ObservedAt: "2026-06-03T00:00:00Z"}
	b, _ := json.Marshal(Record(r, ledger.Deception, "h1", "x"))
	var m map[string]any
	json.Unmarshal(b, &m)
	cls, _ := m["classification"].(map[string]any)
	if cls == nil || cls["category"] != "honeypot" {
		t.Errorf("deception should set classification.category=honeypot, got %v", m["classification"])
	}
}

func TestNonDeceptionOmitsClassification(t *testing.T) {
	r := normalize.Response{Signature: "prometheus", IP: "1.1.1.1", Port: 9090, ObservedAt: "2026-06-03T00:00:00Z"}
	b, _ := json.Marshal(Record(r, ledger.Misidentification, "x", "y"))
	var m map[string]any
	json.Unmarshal(b, &m)
	if _, ok := m["classification"]; ok {
		t.Error("non-deception should omit classification")
	}
}

// An empty ObservedAt must still yield a valid RFC3339 timestamp (required field).
func TestTimestampDefaultsToNow(t *testing.T) {
	b, _ := json.Marshal(Record(normalize.Response{IP: "1.1.1.1", Port: 1}, ledger.ToolBug, "x", "y"))
	var m map[string]any
	json.Unmarshal(b, &m)
	if ts, _ := m["timestamp"].(string); len(ts) < 20 {
		t.Errorf("timestamp not populated: %q", m["timestamp"])
	}
}

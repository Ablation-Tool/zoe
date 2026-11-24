package ingest

import (
	"os"
	"path/filepath"
	"testing"
)

func write(t *testing.T, body string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "obs.jsonl")
	if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadJSONL(t *testing.T) {
	p := write(t, `{"signature":"ollama","source":"shodan","ip":"1.1.1.1","port":11434,"status":200,"content_type":"application/json","body":"{}","observed_at":"2026-06-03T00:00:00Z"}
{"signature":"vllm","source":"censys","ip":"2.2.2.2","port":8000,"status":401,"content_type":"application/json","body":"{}","observed_at":"2026-06-03T00:00:00Z"}
`)
	obs, err := LoadJSONL(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 2 {
		t.Fatalf("got %d observations, want 2", len(obs))
	}
	if obs[0].Signature != "ollama" || obs[0].Source != "shodan" || obs[0].IP != "1.1.1.1" {
		t.Errorf("first observation decoded wrong: %+v", obs[0])
	}
	// content_type and observed_at use snake_case keys; they must still decode.
	if obs[0].ContentType != "application/json" {
		t.Errorf("content_type did not decode: %q", obs[0].ContentType)
	}
	if obs[0].ObservedAt != "2026-06-03T00:00:00Z" {
		t.Errorf("observed_at did not decode: %q", obs[0].ObservedAt)
	}
	if obs[1].Status != 401 {
		t.Errorf("second observation status = %d, want 401", obs[1].Status)
	}
}

func TestLoadJSONLSkipsBlankLines(t *testing.T) {
	p := write(t, "\n"+`{"signature":"ollama","source":"shodan","ip":"1.1.1.1"}`+"\n\n")
	obs, err := LoadJSONL(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(obs) != 1 {
		t.Fatalf("got %d observations, want 1 (blank lines skipped)", len(obs))
	}
}

func TestLoadJSONLReportsBadLine(t *testing.T) {
	p := write(t, `{"signature":"ok","ip":"1.1.1.1"}`+"\n"+`{not valid json}`+"\n")
	if _, err := LoadJSONL(p); err == nil {
		t.Fatal("expected an error on a malformed line")
	}
}

func TestLoadJSONLMissingFileErrors(t *testing.T) {
	if _, err := LoadJSONL("/nonexistent/definitely/nope.jsonl"); err == nil {
		t.Fatal("expected an error for a missing file")
	}
}

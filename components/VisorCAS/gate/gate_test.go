package gate

import (
	"testing"

	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
)

func tmpLedger(t *testing.T) *ledger.Ledger {
	t.Helper()
	l, err := ledger.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = l.Close() })
	return l
}

func TestDropsRefutedByScreen(t *testing.T) {
	l := tmpLedger(t)
	r := normalize.Response{Signature: "gcp-metadata", ContentType: "text/html", Body: "<!doctype html>"}
	keep, reason := Decide(r, l)
	if keep {
		t.Error("a screen-refuted observation must be dropped")
	}
	if reason == "" {
		t.Error("expected a reason for the drop")
	}
}

// A honeypot-tagged host is dropped at the gate via the screen's Refuted path,
// before the corpus lookup - so bait findings never reach the findings output,
// while the Deception disposition keeps the generic fingerprint out of the
// cross-run corpus (no over-suppression of a real same-fingerprint service).
func TestDropsHoneypotTaggedHost(t *testing.T) {
	l := tmpLedger(t)
	r := normalize.Response{
		Signature: "MCP Server", AuthStatus: "unauth", IP: "13.125.251.76",
		Tags: []string{"ai", "honeypot", "cloud"},
	}
	keep, reason := Decide(r, l)
	if keep {
		t.Error("a honeypot-tagged host must be dropped")
	}
	if reason != "screen:honeypot-host-tagged" {
		t.Errorf("reason = %q, want screen:honeypot-host-tagged", reason)
	}
}

func TestDropsKnownCorpusFP(t *testing.T) {
	l := tmpLedger(t)
	fp := normalize.Response{Signature: "prometheus", Port: 9090, AuthStatus: "unauth", IP: "10.0.0.1"}
	if _, err := l.Record(ledger.Finding{Response: fp, Disposition: ledger.Misidentification, SurveyCtx: "x"}); err != nil {
		t.Fatal(err)
	}
	// same pattern, different host: the corpus must catch it by fingerprint
	same := normalize.Response{Signature: "prometheus", Port: 9090, AuthStatus: "unauth", IP: "10.0.0.2"}
	keep, reason := Decide(same, l)
	if keep {
		t.Error("a known excludable corpus FP must be dropped")
	}
	if reason == "" {
		t.Error("expected a reason for the drop")
	}
}

func TestKeepsRealFinding(t *testing.T) {
	l := tmpLedger(t)
	r := normalize.Response{Signature: "weaviate", Port: 8080, AuthStatus: "unauth", Categories: []string{"unauth_data"}}
	if keep, _ := Decide(r, l); !keep {
		t.Error("a real finding not in the corpus must be kept")
	}
}

// A downgrade is real (over-rated severity), not a false positive: keep it.
func TestKeepsDowngrade(t *testing.T) {
	l := tmpLedger(t)
	r := normalize.Response{Signature: "vllm", Status: 405}
	if keep, _ := Decide(r, l); !keep {
		t.Error("a downgrade must be kept, not dropped")
	}
}

// An auth-on corpus entry must NOT cause a drop (it is the thesis, not noise).
func TestKeepsAuthOnCorpusEntry(t *testing.T) {
	l := tmpLedger(t)
	fp := normalize.Response{Signature: "langfuse", Port: 3000, AuthStatus: "auth", IP: "10.0.0.1"}
	if _, err := l.Record(ledger.Finding{Response: fp, Disposition: ledger.AuthOn, SurveyCtx: "x"}); err != nil {
		t.Fatal(err)
	}
	same := normalize.Response{Signature: "langfuse", Port: 3000, AuthStatus: "auth", IP: "10.0.0.9"}
	if keep, _ := Decide(same, l); !keep {
		t.Error("an auth-on corpus entry must be kept (not excludable)")
	}
}

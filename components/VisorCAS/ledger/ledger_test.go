package ledger

import (
	"testing"

	"github.com/nuclide-research/VisorCAS/normalize"
)

func tmpLedger(t *testing.T) *Ledger {
	t.Helper()
	l, err := Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = l.Close() })
	return l
}

// a Prometheus-looks-like-an-LLM misidentification; the only per-instance
// variation is the embedded IP, which the normalizer redacts.
func prometheusFP(ip string) normalize.Response {
	return normalize.Response{
		Signature: "prometheus", Source: "shodan", IP: ip, Port: 9090, Status: 200,
		ContentType: "text/plain", ObservedAt: "2026-06-03T00:00:00Z",
		Body: "# HELP go_gc_duration_seconds A summary\nprocess_cpu_seconds_total 1234 scraped_from " + ip,
	}
}

func TestDispositionValid(t *testing.T) {
	for _, d := range []Disposition{Misidentification, TransientArtifact, AuthOn, Deception, ToolBug, WrongSurfaceClass} {
		if !d.Valid() {
			t.Errorf("%q should be a valid disposition", d)
		}
	}
	if Disposition("nonsense").Valid() {
		t.Error(`"nonsense" should be invalid`)
	}
}

// Thesis invariant: auth-on and deception must never be bloom-excludable, or the
// research program goes blind to auth-on-default and to honeypot intelligence.
func TestOnlyMisidentificationIsExcludable(t *testing.T) {
	if !Misidentification.Excludable() {
		t.Error("misidentification must be excludable")
	}
	for _, d := range []Disposition{TransientArtifact, AuthOn, Deception, ToolBug, WrongSurfaceClass} {
		if d.Excludable() {
			t.Errorf("%q must NOT be bloom-excludable", d)
		}
	}
}

func TestRecordStoresFingerprintInCAS(t *testing.T) {
	l := tmpLedger(t)
	h, err := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "cat-x"})
	if err != nil {
		t.Fatal(err)
	}
	if h == "" {
		t.Fatal("Record returned an empty hash")
	}
	if !l.HasFingerprint(h) {
		t.Error("fingerprint blob was not stored in the CAS")
	}
}

func TestRecordRejectsInvalidDisposition(t *testing.T) {
	l := tmpLedger(t)
	if _, err := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: "bogus", SurveyCtx: "x"}); err == nil {
		t.Fatal("expected an error recording an invalid disposition")
	}
}

// Same pattern, different instances: one fp_pattern row whose hit_count grows,
// and one occurrence row per Record.
func TestRecordDeduplicatesPatternAcrossInstances(t *testing.T) {
	l := tmpLedger(t)
	h1, _ := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "cat-x"})
	h2, _ := l.Record(Finding{Response: prometheusFP("10.0.0.2"), Disposition: Misidentification, SurveyCtx: "cat-x"})
	if h1 != h2 {
		t.Fatalf("instances should collapse to one hash: %s vs %s", h1, h2)
	}

	p, err := l.Pattern(h1)
	if err != nil {
		t.Fatal(err)
	}
	if p.HitCount != 2 {
		t.Errorf("hit_count = %d, want 2", p.HitCount)
	}
	if n := l.OccurrenceCount(h1); n != 2 {
		t.Errorf("occurrence count = %d, want 2", n)
	}
	if l.PatternCount() != 1 {
		t.Errorf("pattern rows = %d, want 1", l.PatternCount())
	}
}

func TestPatternRoundTrip(t *testing.T) {
	l := tmpLedger(t)
	h, _ := l.Record(Finding{
		Response:    prometheusFP("10.0.0.1"),
		Disposition: Misidentification,
		Category:    "monitoring-metrics",
		RootFix:     "anchor aimap signature to a model-API json_field",
		SurveyCtx:   "cat-31",
	})
	p, err := l.Pattern(h)
	if err != nil {
		t.Fatal(err)
	}
	if p.Disposition != Misidentification {
		t.Errorf("disposition = %q, want misidentification", p.Disposition)
	}
	if p.Category != "monitoring-metrics" {
		t.Errorf("category = %q", p.Category)
	}
	if p.RootFix == "" {
		t.Error("root_fix was not stored")
	}
	if p.FirstSeen.IsZero() {
		t.Error("first_seen was not set")
	}
}

func TestDistinctPatternsAreSeparateRows(t *testing.T) {
	l := tmpLedger(t)
	hP, _ := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "x"})
	honey := normalize.Response{
		Signature: "honeypot", Source: "shodan", IP: "10.0.0.3", Port: 80, Status: 200,
		ContentType: "text/html", ObservedAt: "2026-06-03T00:00:00Z",
		Body: "<html><body>welcome salt=wW0sffoqsk.EM</body></html>",
	}
	hH, _ := l.Record(Finding{Response: honey, Disposition: Deception, SurveyCtx: "x"})
	if hP == hH {
		t.Fatal("distinct patterns collided on one hash")
	}
	if l.PatternCount() != 2 {
		t.Errorf("pattern rows = %d, want 2", l.PatternCount())
	}
}

func TestPatternUnknownHashErrors(t *testing.T) {
	l := tmpLedger(t)
	if _, err := l.Pattern("nope"); err == nil {
		t.Error("expected an error for an unknown pattern hash")
	}
}

// Reclassifying a pattern away from an excludable disposition reopens it: the
// exclusion view (Excludable) flips, so future fusion stops screening it.
func TestReclassifyChangesDispositionAndReopens(t *testing.T) {
	l := tmpLedger(t)
	h, _ := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "x"})
	if p, _ := l.Pattern(h); !p.Disposition.Excludable() {
		t.Fatal("precondition: misidentification should be excludable")
	}
	if err := l.Reclassify(h, AuthOn, "default-cred probe returned 0/40; it is gated"); err != nil {
		t.Fatal(err)
	}
	p, _ := l.Pattern(h)
	if p.Disposition != AuthOn {
		t.Errorf("disposition = %q, want auth-on", p.Disposition)
	}
	if p.Disposition.Excludable() {
		t.Error("after reclassify to auth-on the pattern must not be excludable (reopened)")
	}
}

// History is preserved, never overwritten.
func TestReclassifyRecordsHistory(t *testing.T) {
	l := tmpLedger(t)
	h, _ := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "x"})
	if err := l.Reclassify(h, TransientArtifact, "re-verify under concurrency"); err != nil {
		t.Fatal(err)
	}
	hist, err := l.History(h)
	if err != nil {
		t.Fatal(err)
	}
	if len(hist) != 1 {
		t.Fatalf("history length = %d, want 1", len(hist))
	}
	if hist[0].From != Misidentification || hist[0].To != TransientArtifact || hist[0].Reason == "" {
		t.Errorf("history entry = %+v", hist[0])
	}
}

func TestReclassifyInvalidDisposition(t *testing.T) {
	l := tmpLedger(t)
	h, _ := l.Record(Finding{Response: prometheusFP("10.0.0.1"), Disposition: Misidentification, SurveyCtx: "x"})
	if err := l.Reclassify(h, "bogus", "x"); err == nil {
		t.Error("expected an error reclassifying to an invalid disposition")
	}
}

func TestReclassifyUnknownHash(t *testing.T) {
	l := tmpLedger(t)
	if err := l.Reclassify("nope", AuthOn, "x"); err == nil {
		t.Error("expected an error reclassifying an unknown hash")
	}
}

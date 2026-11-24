package fuse

import (
	"reflect"
	"testing"

	"github.com/nuclide-research/VisorCAS/cas"
	"github.com/nuclide-research/VisorCAS/normalize"
)

const (
	unauthBody = `{"models":[{"name":"llama3"}]}`
	authBody   = `{"error":"unauthorized"}`
)

func obs(source, ip string, status int, body string) normalize.Response {
	// Verified auth state drives the fingerprint now, not the status code: a 200
	// to an unauth probe is unauth, a 401/403 is auth.
	auth := normalize.AuthUnauth
	if status != 200 {
		auth = normalize.AuthOn
	}
	return normalize.Response{
		Signature: "ollama", Source: source, IP: ip, Port: 11434, Status: status,
		AuthStatus: auth, ContentType: "application/json", ObservedAt: "2026-06-03T00:00:00Z", Body: body,
	}
}

func fpHashOf(r normalize.Response) string { return cas.Hash(normalize.Fingerprint(r)) }

func find(cands []Candidate, ip string) (Candidate, bool) {
	for _, c := range cands {
		if c.IP == ip {
			return c, true
		}
	}
	return Candidate{}, false
}

func TestFuseThreeSourcesAgree(t *testing.T) {
	cands := Fuse([]normalize.Response{
		obs("shodan", "1.1.1.1", 200, unauthBody),
		obs("censys", "1.1.1.1", 200, unauthBody),
		obs("nuclide", "1.1.1.1", 200, unauthBody),
	})
	c, ok := find(cands, "1.1.1.1")
	if !ok {
		t.Fatal("no candidate produced for 1.1.1.1")
	}
	if c.Agreement != 3 {
		t.Errorf("agreement = %d, want 3", c.Agreement)
	}
	if c.Divergent {
		t.Error("three identical observations must not be divergent")
	}
	if want := []string{"censys", "nuclide", "shodan"}; !reflect.DeepEqual(c.Sources, want) {
		t.Errorf("sources = %v, want %v", c.Sources, want)
	}
	if c.FPHash != fpHashOf(obs("shodan", "1.1.1.1", 200, unauthBody)) {
		t.Error("FPHash does not match the fingerprint hash of the agreed pattern")
	}
}

// Agreement is a count of distinct SOURCES, not of raw observations.
func TestFuseCountsDistinctSourcesNotObservations(t *testing.T) {
	cands := Fuse([]normalize.Response{
		obs("shodan", "3.3.3.3", 200, unauthBody),
		obs("shodan", "3.3.3.3", 200, unauthBody), // same source twice
		obs("censys", "3.3.3.3", 200, unauthBody),
	})
	c, _ := find(cands, "3.3.3.3")
	if c.Agreement != 2 {
		t.Errorf("agreement = %d, want 2 (distinct sources, not observations)", c.Agreement)
	}
}

// Same host, different auth state across sources: divergence flagged, dominant
// fingerprint still chosen by source count.
func TestFuseDetectsDivergence(t *testing.T) {
	cands := Fuse([]normalize.Response{
		obs("shodan", "2.2.2.2", 200, unauthBody),
		obs("censys", "2.2.2.2", 200, unauthBody),
		obs("nuclide", "2.2.2.2", 401, authBody),
	})
	c, _ := find(cands, "2.2.2.2")
	if !c.Divergent {
		t.Error("expected divergent: sources disagree on the fingerprint")
	}
	if c.Agreement != 2 {
		t.Errorf("agreement = %d, want 2 (the dominant, 2-source fingerprint)", c.Agreement)
	}
	if want := []string{"censys", "nuclide", "shodan"}; !reflect.DeepEqual(c.Sources, want) {
		t.Errorf("sources = %v, want %v", c.Sources, want)
	}
}

func TestFuseSeparatesByIP(t *testing.T) {
	cands := Fuse([]normalize.Response{
		obs("shodan", "1.1.1.1", 200, unauthBody),
		obs("shodan", "9.9.9.9", 200, unauthBody),
	})
	if len(cands) != 2 {
		t.Fatalf("candidates = %d, want 2", len(cands))
	}
}

func TestRankOrdersByAgreementDescending(t *testing.T) {
	got := Rank([]Candidate{
		{IP: "low", Agreement: 1},
		{IP: "high", Agreement: 3},
		{IP: "mid", Agreement: 2},
	})
	order := []string{got[0].IP, got[1].IP, got[2].IP}
	if want := []string{"high", "mid", "low"}; !reflect.DeepEqual(order, want) {
		t.Errorf("rank order = %v, want %v", order, want)
	}
}

// Two sources see the same host:port but name it differently: an app-layer
// fingerprinter ("Label Studio") and a banner-grabber ("HTTP"). They diverge on
// identity, yet BOTH confirm the host is live. Identity agreement is 1, but
// liveness agreement (tier-1) must be 2 — otherwise every fingerprinter +
// banner-grabber pairing throws away its cross-source corroboration. This is
// the data-labeling-run case: 60 hosts seen by both aimap and scanner scored
// identity-agreement 1 and lost the signal.
func TestFuseDivergentSourcesAgreeOnLiveness(t *testing.T) {
	mk := func(source, sig string) normalize.Response {
		return normalize.Response{
			Signature: sig, Source: source, IP: "7.7.7.7", Port: 8080,
			AuthStatus: normalize.AuthUnknown, ContentType: "text/html",
			ObservedAt: "2026-06-03T00:00:00Z",
		}
	}
	cands := Fuse([]normalize.Response{
		mk("aimap", "Label Studio"),
		mk("scanner", "HTTP"),
	})
	c, _ := find(cands, "7.7.7.7")
	if c.Agreement != 1 {
		t.Errorf("identity agreement = %d, want 1 (divergent fingerprints)", c.Agreement)
	}
	if !c.Divergent {
		t.Error("expected divergent: different fingerprints")
	}
	if c.LivenessAgreement != 2 {
		t.Errorf("liveness agreement = %d, want 2 (both sources saw the host live)", c.LivenessAgreement)
	}
}

// At equal identity agreement, a host corroborated-live by more sources is more
// worth verifying than a single-source host, even if it is divergent. Liveness
// breaks the tie ahead of the divergence flag.
func TestRankBreaksAgreementTiesByLiveness(t *testing.T) {
	got := Rank([]Candidate{
		{IP: "single", Agreement: 1, LivenessAgreement: 1, Divergent: false},
		{IP: "corroborated", Agreement: 1, LivenessAgreement: 2, Divergent: true},
	})
	if got[0].IP != "corroborated" {
		t.Errorf("rank[0] = %s, want corroborated (higher liveness outranks single-source)", got[0].IP)
	}
}

func TestScreenDropsKnownExcludableFPs(t *testing.T) {
	known := fpHashOf(obs("shodan", "5.5.5.5", 200, unauthBody))
	cands := []Candidate{
		{IP: "5.5.5.5", FPHash: known},
		{IP: "6.6.6.6", FPHash: "novel-unknown-hash"},
	}
	survivors, skipped := Screen(cands, func(h string) bool { return h == known })
	if len(skipped) != 1 || skipped[0].IP != "5.5.5.5" {
		t.Errorf("skipped = %v, want one candidate 5.5.5.5", skipped)
	}
	if len(survivors) != 1 || survivors[0].IP != "6.6.6.6" {
		t.Errorf("survivors = %v, want one candidate 6.6.6.6", survivors)
	}
}

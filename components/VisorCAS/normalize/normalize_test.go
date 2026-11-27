package normalize

import "testing"

// The five fixtures below are the real FP patterns from the NuClide ledger.
// Each pattern has two instances that differ ONLY in volatile data:
//   - dropped fields:   Source, IP, ObservedAt (never part of the fingerprint)
//   - redacted in body: IPs, UUIDs, ISO timestamps, long hex nonces
// A correct normalizer collapses each pair to one fingerprint, and keeps the
// five patterns distinct from each other.

// 1. CVAT behind GCP IAP: transient interstitial HTML (transient-artifact).
func cvatA() Response {
	return Response{
		Signature: "cvat", Source: "shodan", IP: "203.0.113.7", Port: 8080, Status: 200,
		ContentType: "text/html", ObservedAt: "2026-05-01T08:02:11Z",
		Body: `<html><head><title>Sign in - Google Accounts</title></head><body>Requested URL /api/server/about from 203.0.113.7 was denied. requestId=550e8400-e29b-41d4-a716-446655440000 ts=2026-05-01T08:02:11Z</body></html>`,
	}
}
func cvatB() Response {
	return Response{
		Signature: "cvat", Source: "censys", IP: "198.51.100.9", Port: 8080, Status: 200,
		ContentType: "text/html", ObservedAt: "2026-06-03T21:15:04Z",
		Body: `<html><head><title>Sign in - Google Accounts</title></head><body>Requested URL /api/server/about from 198.51.100.9 was denied. requestId=6ba7b810-9dad-11d1-80b4-00c04fd430c8 ts=2026-06-03T21:15:04Z</body></html>`,
	}
}

// 2. dcm4chee false hit: ASP.NET catchall echoing the request path (misidentification).
func dcm4cheeA() Response {
	return Response{
		Signature: "dcm4chee", Source: "shodan", IP: "10.0.0.1", Port: 8080, Status: 200,
		ContentType: "application/json", ObservedAt: "2026-05-01T08:02:11Z",
		Body: `{"path":"/dcm4chee-arc/aets/550e8400-e29b-41d4-a716-446655440000/rs/studies","server":"Microsoft-IIS/10.0","ts":"2026-05-01T08:02:11Z"}`,
	}
}
func dcm4cheeB() Response {
	return Response{
		Signature: "dcm4chee", Source: "nuclide", IP: "172.16.9.4", Port: 8080, Status: 200,
		ContentType: "application/json", ObservedAt: "2026-06-03T21:15:04Z",
		Body: `{"path":"/dcm4chee-arc/aets/6ba7b810-9dad-11d1-80b4-00c04fd430c8/rs/studies","server":"Microsoft-IIS/10.0","ts":"2026-06-03T21:15:04Z"}`,
	}
}

// 3. Weaviate enum count bug: always reports two objects (tool-bug).
func weaviateA() Response {
	return Response{
		Signature: "weaviate", Source: "shodan", IP: "10.0.0.2", Port: 8080, Status: 200,
		ContentType: "application/json", ObservedAt: "2026-05-01T08:02:11Z",
		Body: `{"objects":[{"id":"550e8400-e29b-41d4-a716-446655440000"},{"id":"6ba7b810-9dad-11d1-80b4-00c04fd430c8"}],"totalResults":2}`,
	}
}
func weaviateB() Response {
	return Response{
		Signature: "weaviate", Source: "censys", IP: "192.0.2.55", Port: 8080, Status: 200,
		ContentType: "application/json", ObservedAt: "2026-06-03T21:15:04Z",
		Body: `{"objects":[{"id":"11111111-2222-3333-4444-555555555555"},{"id":"66666666-7777-8888-9999-000000000000"}],"totalResults":2}`,
	}
}

// 4. menlohunt kubelet false hit: anonymous-forbidden Status labeled a hit (misidentification).
func kubeletA() Response {
	return Response{
		Signature: "kubelet", Source: "shodan", IP: "10.0.0.5", Port: 10250, Status: 403,
		ContentType: "application/json", ObservedAt: "2026-05-01T08:02:11Z",
		Body: `{"kind":"Status","status":"Failure","message":"forbidden: User \"system:anonymous\" cannot get path \"/\" from 10.0.0.5","code":403}`,
	}
}
func kubeletB() Response {
	return Response{
		Signature: "kubelet", Source: "censys", IP: "172.16.4.9", Port: 10250, Status: 403,
		ContentType: "application/json", ObservedAt: "2026-06-03T21:15:04Z",
		Body: `{"kind":"Status","status":"Failure","message":"forbidden: User \"system:anonymous\" cannot get path \"/\" from 172.16.4.9","code":403}`,
	}
}

// 5. AS63949 honeypot fleet: fixed salt marker plus a per-host nonce (deception).
func honeypotA() Response {
	return Response{
		Signature: "honeypot", Source: "shodan", IP: "203.0.113.7", Port: 80, Status: 200,
		ContentType: "text/html", ObservedAt: "2026-05-01T08:02:11Z",
		Body: `<html><body>welcome salt=wW0sffoqsk.EM nonce=a3f7c2e9b1d04f6a peer=203.0.113.7</body></html>`,
	}
}
func honeypotB() Response {
	return Response{
		Signature: "honeypot", Source: "nuclide", IP: "198.51.100.9", Port: 80, Status: 200,
		ContentType: "text/html", ObservedAt: "2026-06-03T21:15:04Z",
		Body: `<html><body>welcome salt=wW0sffoqsk.EM nonce=ffeeddccbbaa9988 peer=198.51.100.9</body></html>`,
	}
}

func eq(a, b Response) bool { return string(Fingerprint(a)) == string(Fingerprint(b)) }

func TestInstancesOfSamePatternCollapse(t *testing.T) {
	pairs := []struct {
		name string
		a, b Response
	}{
		{"cvat", cvatA(), cvatB()},
		{"dcm4chee", dcm4cheeA(), dcm4cheeB()},
		{"weaviate", weaviateA(), weaviateB()},
		{"kubelet", kubeletA(), kubeletB()},
		{"honeypot", honeypotA(), honeypotB()},
	}
	for _, p := range pairs {
		if !eq(p.a, p.b) {
			t.Errorf("%s: instances did not collapse to one fingerprint:\n  a=%s\n  b=%s",
				p.name, Fingerprint(p.a), Fingerprint(p.b))
		}
	}
}

func TestDistinctPatternsDoNotCollide(t *testing.T) {
	fps := map[string]string{
		"cvat":     string(Fingerprint(cvatA())),
		"dcm4chee": string(Fingerprint(dcm4cheeA())),
		"weaviate": string(Fingerprint(weaviateA())),
		"kubelet":  string(Fingerprint(kubeletA())),
		"honeypot": string(Fingerprint(honeypotA())),
	}
	seen := map[string]string{}
	for name, fp := range fps {
		if other, dup := seen[fp]; dup {
			t.Errorf("patterns %q and %q collided on fingerprint %s", name, other, fp)
		}
		seen[fp] = name
	}
}

// Source, IP, and ObservedAt are provenance, never part of the dedup spine.
func TestProvenanceFieldsAreIgnored(t *testing.T) {
	base := weaviateA()
	moved := base
	moved.Source = "censys"
	moved.IP = "8.8.8.8"
	moved.ObservedAt = "2030-01-01T00:00:00Z"
	if !eq(base, moved) {
		t.Errorf("changing only provenance changed the fingerprint:\n base=%s\n moved=%s",
			Fingerprint(base), Fingerprint(moved))
	}
}

// Same host and signature, different VERIFIED auth state: the fingerprints MUST
// differ so the divergence is visible (the auth-on / staleness signal). Auth
// state drives this now, not the status code or body (Insight #16: a 200 is
// identity, not auth state).
func TestStalenessProducesDistinctFingerprints(t *testing.T) {
	unauth := Response{
		Signature: "ollama", Source: "shodan", IP: "10.0.0.9", Port: 11434,
		AuthStatus: "unauth", ObservedAt: "2026-05-01T00:00:00Z",
	}
	authd := Response{
		Signature: "ollama", Source: "censys", IP: "10.0.0.9", Port: 11434,
		AuthStatus: "auth", ObservedAt: "2026-06-03T00:00:00Z",
	}
	if eq(unauth, authd) {
		t.Errorf("auth-state divergence collapsed into one fingerprint: %s", Fingerprint(unauth))
	}
}

// The fingerprint keys on structured identity, not the raw response: status,
// content-type, and body must NOT affect it (they are truncated and volatile).
func TestBodyStatusContentTypeDoNotAffectFingerprint(t *testing.T) {
	a := Response{Signature: "weaviate", Port: 8080, AuthStatus: "unauth", Categories: []string{"unauth_data"},
		Status: 200, ContentType: "application/json", Body: `{"objects":[{"id":"a"}],"totalResults":2}`}
	b := Response{Signature: "weaviate", Port: 8080, AuthStatus: "unauth", Categories: []string{"unauth_data"},
		Status: 500, ContentType: "text/html", Body: "an entirely different body"}
	if !eq(a, b) {
		t.Errorf("status/content-type/body leaked into the fingerprint:\n a=%s\n b=%s", Fingerprint(a), Fingerprint(b))
	}
}

// Verified auth state is part of identity.
func TestAuthStatusAffectsFingerprint(t *testing.T) {
	base := Response{Signature: "ollama", Port: 11434, AuthStatus: "unauth"}
	authd := base
	authd.AuthStatus = "auth"
	if eq(base, authd) {
		t.Error("auth state did not affect the fingerprint")
	}
}

// Categories are part of identity but order-independent.
func TestCategoriesAffectFingerprintOrderIndependent(t *testing.T) {
	one := Response{Signature: "mlflow", Port: 5000, AuthStatus: "unauth", Categories: []string{"unauth_data"}}
	two := Response{Signature: "mlflow", Port: 5000, AuthStatus: "unauth", Categories: []string{"unauth_data", "rce"}}
	if eq(one, two) {
		t.Error("different category sets should produce different fingerprints")
	}
	reordered := Response{Signature: "mlflow", Port: 5000, AuthStatus: "unauth", Categories: []string{"rce", "unauth_data"}}
	if !eq(two, reordered) {
		t.Error("category order must not affect the fingerprint")
	}
}

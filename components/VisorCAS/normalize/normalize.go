// Package normalize turns a scan observation into its canonical service
// fingerprint: the source-independent, instance-independent byte representation
// whose hash is the dedup spine of the VisorCAS ledger.
//
// The fingerprint keys on the detector's structured identity - service, port
// class, verified auth state, and finding categories - NOT the raw response
// body. body_snippet is truncated and carries volatile timestamps and version
// strings that would defeat dedup, and the host IP lives only in the provenance
// (the Observation), never in the fingerprint. Choose the field set wrong and
// you either never dedup (too many fields) or collapse distinct services (too
// few). The test suite pins both edges.
package normalize

import (
	"encoding/json"
	"sort"
	"strings"
)

// The normalized 3-way auth axis (Insight #16: a 200 is service identity, not
// auth state; only a verified read sets unauth or auth).
const (
	AuthUnauth  = "unauth"       // verified unauthenticated
	AuthUnknown = "auth-unknown" // surface open, auth NOT verified - neither FP nor finding
	AuthOn      = "auth"         // verified protected
)

// Response is one observation of a host:port. Signature, Port, AuthStatus, and
// Categories define what the service IS and feed the fingerprint. Status,
// ContentType, and Body are context. Source, IP, and ObservedAt are provenance.
// Only the first group is hashed.
type Response struct {
	Signature  string   `json:"signature"`   // detector's service identity (aimap service / fingerprint name)
	Port       int      `json:"port"`        //
	AuthStatus string   `json:"auth_status"` // verified auth state -> normalized to unauth | auth-unknown | auth
	Categories []string `json:"categories"`  // finding categories (e.g. unauth_data); order-independent

	Status      int    `json:"status"`       // context, not hashed
	ContentType string `json:"content_type"` // context, not hashed
	Body        string `json:"body"`         // context, not hashed

	Source     string   `json:"source"`         // provenance - dropped from the fingerprint
	IP         string   `json:"ip"`             // provenance - dropped from the fingerprint
	ObservedAt string   `json:"observed_at"`    // provenance - dropped from the fingerprint
	Tags       []string `json:"tags,omitempty"` // host labels (e.g. Shodan tags); context, not hashed - carries honeypot/deception evidence for the screen
}

// fingerprint is the canonical, serialized form. Fixed field order plus sorted
// categories make encoding/json deterministic - this is the canonicalization
// step (the pcse trust_hash pattern) that runs before blake3.
type fingerprint struct {
	Service    string   `json:"service"`
	PortClass  int      `json:"port_class"`
	AuthStatus string   `json:"auth_status"`
	Categories []string `json:"categories"`
}

// NormalizeAuth maps an auth string to the 3-way axis. Unset or "unknown" is
// auth-unknown (surface open, unverified); "none"/"open" is verified unauth;
// "auth"/"required"/"protected" is verified auth. Adapters do the rich
// detector-specific mapping before this; NormalizeAuth is the final guard.
func NormalizeAuth(s string) string {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case AuthUnauth, "none", "open":
		return AuthUnauth
	case AuthOn, "required", "protected":
		return AuthOn
	default:
		return AuthUnknown
	}
}

// Fingerprint returns the canonical bytes for a response. Two responses that are
// the same service pattern (differing only in provenance, status, content-type,
// or body) return identical bytes; a different service, port, verified auth
// state, or category set returns different bytes.
func Fingerprint(r Response) []byte {
	cats := append([]string(nil), r.Categories...)
	sort.Strings(cats)
	if cats == nil {
		cats = []string{} // always "[]" not "null", for stable bytes
	}
	fp := fingerprint{
		Service:    r.Signature,
		PortClass:  r.Port,
		AuthStatus: NormalizeAuth(r.AuthStatus),
		Categories: cats,
	}
	b, _ := json.Marshal(fp) // fixed struct, cannot fail
	return b
}

// Package screen runs an observation against the codified NuClide false-positive
// signatures - the rules ported from winnow plus the verification Insights - and
// returns a verdict. It is VisorCAS's fast-loop screen: the durable, content-fed
// successor to winnow's stateless pass.
package screen

import (
	"strings"

	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
)

// Verdict is the screen's call on one observation.
type Verdict string

const (
	Pass      Verdict = "pass"      // not a known false alarm; proceed to verification
	Refuted   Verdict = "refuted"   // a known false positive; Disposition is set
	Downgrade Verdict = "downgrade" // a real observation carrying severity it did not earn
)

// Result is the screen's output for one observation.
type Result struct {
	Verdict     Verdict
	SignatureID string
	Disposition ledger.Disposition // set only when Verdict == Refuted
	Insight     string
	Reason      string
}

type signature struct {
	id          string
	verdict     Verdict
	disposition ledger.Disposition
	insight     string
	reason      string
	match       func(normalize.Response) bool
}

func sigHas(r normalize.Response, sub string) bool {
	return strings.Contains(strings.ToLower(r.Signature), sub)
}

// hasTag reports whether the observation carries a host-level label (e.g. a
// Shodan tag). Tags are host evidence, not service identity - the honeypot
// signature keys on them so it never refutes by the generic service fingerprint.
func hasTag(r normalize.Response, tag string) bool {
	for _, t := range r.Tags {
		if strings.EqualFold(strings.TrimSpace(t), tag) {
			return true
		}
	}
	return false
}

func bodyHas(r normalize.Response, sub string) bool {
	return strings.Contains(strings.ToLower(r.Body), strings.ToLower(sub))
}

func htmlEvidence(r normalize.Response) bool {
	if strings.Contains(strings.ToLower(r.ContentType), "html") {
		return true
	}
	b := strings.TrimSpace(strings.ToLower(r.Body))
	return strings.HasPrefix(b, "<!doctype") || strings.HasPrefix(b, "<html")
}

// dicomShape reports whether the evidence actually looks like dcm4chee/DICOMweb,
// as opposed to a catchall route that merely echoed the /dcm4chee-arc/ probe
// path (Insight #52). DICOMweb responds application/dicom+json; the landing page
// carries a <title>dcm4chee-arc</title>; the capability statement advertises
// DICOMweb. Any of these is a genuine tell; none means the service is not there.
func dicomShape(r normalize.Response) bool {
	ct := strings.ToLower(r.ContentType)
	if strings.Contains(ct, "dicom") {
		return true
	}
	b := strings.ToLower(r.Body)
	return strings.Contains(b, "<title>dcm4chee") || strings.Contains(b, "dicomweb")
}

// xttsShape reports whether the evidence looks like a real Coqui XTTS speaker
// list. The /api/tts/speakers probe returns a JSON array of speaker objects;
// any catchall route (FastAPI, Next.js, generic HTTP) that happens to answer
// 200 at that path also fires the fingerprint. A JSON array start "[" is the
// minimum discriminator: if the body is HTML, an error envelope, or absent
// the service is not there.
func xttsShape(r normalize.Response) bool {
	b := strings.TrimSpace(r.Body)
	return strings.HasPrefix(b, "[")
}

// hasEvidence reports whether the observation carries any response to reason
// about. The screen refutes only on positive contradiction, never on silence:
// an absent body and content-type is "could not verify", not disproof.
func hasEvidence(r normalize.Response) bool {
	return strings.TrimSpace(r.ContentType) != "" || strings.TrimSpace(r.Body) != ""
}

// signatures, ported from winnow (first match wins). winnow's verdicts map onto
// VisorCAS: REFUTED -> a false positive with a disposition; DOWNGRADE -> a real
// observation with unearned severity (not an FP).
//
// Pending (need source-specific fields aimap observations do not carry):
// firebase-name-from-hostname-label and gcs-name-from-hostname-label compare a
// guessed project/bucket name against the DNS label - only SubKu/menlohunt
// observations carry that. Add them when those sources feed the screen.
var signatures = []signature{
	{
		// First: a honeypot-tagged host is a deception surface, whatever service
		// was claimed on it. Keyed on the host tag (Shodan / aimap-profile), never
		// the fingerprint - so it drops the bait finding (gate drops on Refuted)
		// while disposition Deception keeps the generic fingerprint OUT of the
		// cross-run exclusion corpus, never over-suppressing a real same-fingerprint
		// service. Source: Cat-01 MCP credential-bait fleet (8 IPs, all honeypot-tagged).
		id: "honeypot-host-tagged", verdict: Refuted, disposition: ledger.Deception,
		insight: "Insight #1 - honeypots self-filter; the host tag is the discriminator, not the service fingerprint",
		reason:  "host carries a honeypot label (Shodan/aimap-profile); the claimed service is bait on a deception surface, not a real exposure",
		match:   func(r normalize.Response) bool { return hasTag(r, "honeypot") },
	},
	{
		id: "gcp-metadata-html", verdict: Refuted, disposition: ledger.Misidentification,
		insight: "Insight #6 - cloud metadata API false positive",
		reason:  "evidence is an HTML document; the GCP metadata API is link-local, header-gated, and never returns HTML",
		match:   func(r normalize.Response) bool { return sigHas(r, "gcp") && sigHas(r, "metadata") && htmlEvidence(r) },
	},
	{
		id: "metadata-endpoint-html", verdict: Refuted, disposition: ledger.Misidentification,
		insight: "Insight #6 - cloud metadata API false positive (generalized)",
		reason:  "a metadata-endpoint candidate whose evidence is HTML; the AWS/Azure/GCP metadata APIs do not serve HTML",
		match:   func(r normalize.Response) bool { return sigHas(r, "metadata") && htmlEvidence(r) },
	},
	{
		id: "dcm4chee-no-dicom-shape", verdict: Refuted, disposition: ledger.Misidentification,
		insight: "Insight #52 - an HTTP 200 at an API path is not that API",
		reason:  "dcm4chee/dcm4chee-arc claimed via path-only match, but the evidence carries no DICOM response shape (no application/dicom+json, no dcm4chee-arc title, no DICOMweb capability); a catchall route echoed the probe path",
		match: func(r normalize.Response) bool {
			return (sigHas(r, "dcm4che") || sigHas(r, "dicom")) && hasEvidence(r) && !dicomShape(r)
		},
	},
	{
		id: "coqui-xtts-no-speaker-shape", verdict: Refuted, disposition: ledger.Misidentification,
		insight: "Insight #52 - an HTTP 200 at an API path is not that API",
		reason:  "Coqui XTTS claimed via /api/tts/speakers path match, but the evidence carries no speaker-list JSON array; a catchall route answered the probe path",
		match: func(r normalize.Response) bool {
			return (sigHas(r, "coqui") || sigHas(r, "xtts")) && hasEvidence(r) && !xttsShape(r)
		},
	},
	{
		id: "metabase-setup-token-null", verdict: Refuted, disposition: ledger.Misidentification,
		insight: "Insight #16 - a 200 is identity, not exposure",
		reason:  "Metabase setup-token is null/empty; the setup endpoint is reachable but the token is not exposed",
		match: func(r normalize.Response) bool {
			return sigHas(r, "metabase") &&
				(bodyHas(r, `"setup-token":null`) || bodyHas(r, `"setup-token": null`) || bodyHas(r, `"setup-token":""`))
		},
	},
	{
		id: "unauth-claim-error-status", verdict: Downgrade,
		insight: "Insight #16 - a status code is not auth state",
		reason:  "claimed unauthenticated, but the evidence is an HTTP 4xx/5xx error envelope; a rejected probe path is not a demonstrated unauthenticated read",
		match: func(r normalize.Response) bool {
			return normalize.NormalizeAuth(r.AuthStatus) == normalize.AuthUnauth && r.Status >= 400
		},
	},
	{
		id: "vllm-completions-405", verdict: Downgrade,
		insight: "Insight #16 - a method-gated endpoint is not open access",
		reason:  "vLLM /v1/completions returned 405; the service is present but the endpoint is method-gated, not openly invokable",
		match:   func(r normalize.Response) bool { return sigHas(r, "vllm") && (r.Status == 405 || bodyHas(r, "405")) },
	},
	{
		id: "port-open-inflated", verdict: Downgrade,
		insight: "Insight #51 - a port number names a candidate, not a finding",
		reason:  "an open port with no identified service carries no earned severity until a protocol probe confirms a service",
		match: func(r normalize.Response) bool {
			s := strings.TrimSpace(strings.ToLower(r.Signature))
			return s == "" || s == "unknown"
		},
	},
}

// Screen runs the observation against the signatures and returns the first
// match, or Pass if none fire. Pass means "not a known false alarm" - NOT
// "verified real"; it still needs a protocol-level check.
func Screen(r normalize.Response) Result {
	for _, s := range signatures {
		if s.match(r) {
			return Result{Verdict: s.verdict, SignatureID: s.id, Disposition: s.disposition, Insight: s.insight, Reason: s.reason}
		}
	}
	return Result{Verdict: Pass}
}

package screen

import (
	"testing"

	"github.com/nuclide-research/VisorCAS/ledger"
	"github.com/nuclide-research/VisorCAS/normalize"
)

// A host Shodan (or aimap-profile) classified as a honeypot is a deception
// surface: its findings are bait, not real exposure. Refute on the honeypot tag -
// host-level positive evidence, never the service fingerprint (which is generic
// and collides with real services). Disposition is Deception (intel, kept in the
// ledger and assetrec), NOT Misidentification (so the generic fingerprint never
// enters the cross-run exclusion corpus and over-suppresses a real service).
// Sourced to the Cat-01 run: an 8-IP MCP "credential-theft" bait fleet, every IP
// Shodan-tagged honeypot, sailed through all three FP layers.
func TestRefutesHoneypotTaggedHost(t *testing.T) {
	r := normalize.Response{
		Signature: "MCP Server", AuthStatus: normalize.AuthUnauth,
		Tags: []string{"database", "ai", "honeypot", "cloud"},
	}
	got := Screen(r)
	if got.Verdict != Refuted || got.Disposition != ledger.Deception {
		t.Fatalf("got %+v, want Refuted / deception", got)
	}
	if got.SignatureID != "honeypot-host-tagged" {
		t.Errorf("signature = %q, want honeypot-host-tagged", got.SignatureID)
	}
}

// The honeypot signature keys ONLY on the tag, never the service identity: an
// identical MCP Server observation with no honeypot tag must not fire it (it may
// still be a real unauth MCP server worth verifying).
func TestHoneypotSignatureRequiresTag(t *testing.T) {
	r := normalize.Response{
		Signature: "MCP Server", AuthStatus: normalize.AuthUnauth,
		Tags: []string{"cloud", "ai"},
	}
	if got := Screen(r); got.SignatureID == "honeypot-host-tagged" {
		t.Fatalf("honeypot signature fired without a honeypot tag: %+v", got)
	}
}

func TestRefutesGCPMetadataHTML(t *testing.T) {
	r := normalize.Response{Signature: "gcp-metadata", ContentType: "text/html", Body: "<!doctype html><html>...</html>"}
	got := Screen(r)
	if got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
	if got.SignatureID != "gcp-metadata-html" {
		t.Errorf("signature = %q, want gcp-metadata-html", got.SignatureID)
	}
}

func TestRefutesGenericMetadataHTML(t *testing.T) {
	r := normalize.Response{Signature: "aws-metadata", Body: "<html><body>not the metadata API</body></html>"}
	if got := Screen(r); got.Verdict != Refuted {
		t.Fatalf("got %+v, want Refuted", got)
	}
}

func TestRefutesMetabaseSetupTokenNull(t *testing.T) {
	r := normalize.Response{Signature: "metabase", Body: `{"setup-token":null}`}
	got := Screen(r)
	if got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
}

func TestDowngradesVLLM405(t *testing.T) {
	r := normalize.Response{Signature: "vllm", Status: 405}
	got := Screen(r)
	if got.Verdict != Downgrade {
		t.Fatalf("got %+v, want Downgrade", got)
	}
	if got.Disposition != "" {
		t.Errorf("downgrade carried a disposition %q; downgrade is not an FP", got.Disposition)
	}
}

func TestDowngradesBarePortOpen(t *testing.T) {
	r := normalize.Response{Signature: "", Port: 8000}
	if got := Screen(r); got.Verdict != Downgrade || got.SignatureID != "port-open-inflated" {
		t.Fatalf("got %+v, want Downgrade / port-open-inflated", got)
	}
}

// dcm4chee-arc is matched by a path-only probe (/dcm4chee-arc/). Any catchall
// route - ASP.NET, Next.js, a 404-JSON envelope - that echoes the path fires it.
// The discriminator (Insight #52) is response shape: real DICOMweb is
// application/dicom+json, carries a <title>dcm4chee-arc</title>, or a DICOMweb
// capability body. None of those => the service is not there.
func TestRefutesDcm4cheeCatchallHTML(t *testing.T) {
	r := normalize.Response{
		Signature:   "dcm4che / dcm4chee-arc DICOM Archive",
		ContentType: "text/html",
		Body:        "<!doctype html><html><head><title>Home</title></head><body>app</body></html>",
	}
	got := Screen(r)
	if got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
	if got.SignatureID != "dcm4chee-no-dicom-shape" {
		t.Errorf("signature = %q, want dcm4chee-no-dicom-shape", got.SignatureID)
	}
}

func TestRefutesDcm4cheePathEcho404JSON(t *testing.T) {
	r := normalize.Response{
		Signature:   "dcm4che / dcm4chee-arc DICOM Archive",
		ContentType: "application/json",
		Status:      404,
		Body:        `{"code":404,"message":"path /dcm4chee-arc/aets was not found"}`,
	}
	if got := Screen(r); got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
}

// Guard: a genuine dcm4chee instance must Pass. DICOMweb content-type is the
// definitive tell - refuting this would eat a true positive.
func TestPassesRealDcm4cheeDicomJSON(t *testing.T) {
	r := normalize.Response{
		Signature:   "dcm4che / dcm4chee-arc DICOM Archive",
		ContentType: "application/dicom+json",
		Body:        `[{"00080020":{"vr":"DA","Value":["20240101"]}}]`,
	}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (real DICOMweb must not be refuted)", got)
	}
}

// Guard: a dcm4chee claim with NO joined evidence (empty content-type and body)
// must Pass, not refute. Absence of evidence is not positive disproof - the
// screen refutes only on a contradicting response shape, never on silence.
func TestPassesDcm4cheeNoEvidence(t *testing.T) {
	r := normalize.Response{Signature: "dcm4che / dcm4chee-arc DICOM Archive"}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (no evidence is not disproof)", got)
	}
}

// Guard: the dcm4chee-arc landing page is HTML but carries its own title.
func TestPassesRealDcm4cheeTitle(t *testing.T) {
	r := normalize.Response{
		Signature:   "dcm4chee-arc DICOM Archive",
		ContentType: "text/html",
		Body:        "<html><head><title>dcm4chee-arc</title></head><body>DICOM Archive</body></html>",
	}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (real dcm4chee landing page must not be refuted)", got)
	}
}

// Insight #16 at the auth axis: a service claimed unauthenticated whose only
// evidence is a 4xx/5xx error envelope has not earned the unauth label - a
// rejected probe path is not a demonstrated unauthenticated read. Downgrade
// (the host may be a real service; the SEVERITY is unearned), do not refute.
// Found live: 40 of aimap's 72 "unauth" on the vector-DB survey were 404s.
func TestDowngradesUnauthClaimOn404(t *testing.T) {
	r := normalize.Response{Signature: "ChromaDB", AuthStatus: normalize.AuthUnauth, Status: 404, ContentType: "application/json", Body: `{"detail":"Not Found"}`}
	got := Screen(r)
	if got.Verdict != Downgrade || got.SignatureID != "unauth-claim-error-status" {
		t.Fatalf("got %+v, want Downgrade / unauth-claim-error-status", got)
	}
	if got.Disposition != "" {
		t.Errorf("downgrade carried a disposition %q; a downgrade is not an FP", got.Disposition)
	}
}

// Same class via the raw "none" auth string and a Go net/http plaintext 404.
func TestDowngradesUnauthClaimOn404PlainText(t *testing.T) {
	r := normalize.Response{Signature: "Milvus", AuthStatus: "none", Status: 404, ContentType: "text/plain", Body: "404 page not found"}
	if got := Screen(r); got.Verdict != Downgrade {
		t.Fatalf("got %+v, want Downgrade", got)
	}
}

// Guard: a real 200 unauthenticated read is THE finding - it must Pass, never
// be downgraded. Refuting/downgrading this is the cardinal sin (eating a TP).
func TestPassesUnauth200(t *testing.T) {
	r := normalize.Response{Signature: "Weaviate", AuthStatus: normalize.AuthUnauth, Status: 200, ContentType: "application/json", Body: `{"objects":[]}`}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (a 200 unauth read is the finding, not unearned severity)", got)
	}
}

// Guard: an auth-unknown 404 carries no unauth severity to strip -> Pass. The
// downgrade only fires on a contradicted UNAUTH claim.
func TestPassesAuthUnknown404(t *testing.T) {
	r := normalize.Response{Signature: "Typesense", AuthStatus: normalize.AuthUnknown, Status: 404, ContentType: "application/json", Body: `{"message":"Not Found"}`}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (no unauth claim to downgrade)", got)
	}
}

// Coqui XTTS is matched by a path-only probe (/api/tts/speakers). Any HTTP
// service answering 200 at that path fires the fingerprint. The discriminator
// is response shape: real XTTS returns a JSON array of speaker objects starting
// with "[". Anything else (HTML, error envelope, empty) is a catchall FP.
func TestRefutesCoquiXTTSHTMLBody(t *testing.T) {
	r := normalize.Response{
		Signature:   "Coqui XTTS",
		ContentType: "text/html",
		Body:        "<!doctype html><html><body>Not Found</body></html>",
	}
	got := Screen(r)
	if got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
	if got.SignatureID != "coqui-xtts-no-speaker-shape" {
		t.Errorf("signature = %q, want coqui-xtts-no-speaker-shape", got.SignatureID)
	}
}

func TestRefutesCoquiXTTSErrorEnvelope(t *testing.T) {
	r := normalize.Response{
		Signature:   "Coqui XTTS",
		ContentType: "application/json",
		Status:      404,
		Body:        `{"detail":"Not Found"}`,
	}
	if got := Screen(r); got.Verdict != Refuted || got.Disposition != ledger.Misidentification {
		t.Fatalf("got %+v, want Refuted / misidentification", got)
	}
}

// Guard: a real Coqui XTTS instance returns a JSON array at /api/tts/speakers.
// The array may be empty [] if no speakers are loaded; that is still a real
// response shape and must Pass.
func TestPassesRealCoquiXTTSSpeakerList(t *testing.T) {
	r := normalize.Response{
		Signature:   "Coqui XTTS",
		ContentType: "application/json",
		Body:        `[{"name":"default","voice_id":"default"}]`,
	}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (real speaker list must not be refuted)", got)
	}
}

func TestPassesRealCoquiXTTSEmptyArray(t *testing.T) {
	r := normalize.Response{
		Signature:   "Coqui XTTS",
		ContentType: "application/json",
		Body:        `[]`,
	}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (empty array is still real XTTS shape)", got)
	}
}

// Guard: no evidence -> Pass (silence is not disproof).
func TestPassesCoquiXTTSNoEvidence(t *testing.T) {
	r := normalize.Response{Signature: "Coqui XTTS"}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass (no evidence is not disproof)", got)
	}
}

// A real exposed service is not a known false alarm: it must Pass (which means
// "go verify", NOT "confirmed real").
func TestPassesRealFinding(t *testing.T) {
	r := normalize.Response{
		Signature: "weaviate", AuthStatus: "unauth", Categories: []string{"unauth_data"},
		Body: `{"objects":[{"id":"x"}],"totalResults":2}`,
	}
	if got := Screen(r); got.Verdict != Pass {
		t.Fatalf("got %+v, want Pass", got)
	}
}

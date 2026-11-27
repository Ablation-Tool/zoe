package engine

import (
	"context"
	"embed"
	"os"
	"strings"
	"testing"
)

// The engine's Assess() reads from the package-level RegoFS, which main
// normally sets from an //go:embed of the repo-root rego/ dir. Go embed
// cannot reach ../rego, so engine/rego/nuclide/AIConfig.rego is a
// test-only copy. TestRegoCopyInSync (below) fails if it drifts from the
// canonical ../rego/nuclide/AIConfig.rego — one source of truth, enforced.
//
//go:embed all:rego
var testRegoFS embed.FS

// TestRegoCopyInSync guards against the engine/rego test copies drifting
// from the canonical repo-root rego/nuclide policies.
func TestRegoCopyInSync(t *testing.T) {
	files := []string{"AIConfig.rego", "BlueTeam.rego"}
	for _, f := range files {
		canonical, err := os.ReadFile("../rego/nuclide/" + f)
		if err != nil {
			t.Skipf("canonical rego/%s not found (%v); skipping drift check", f, err)
		}
		copyb, err := os.ReadFile("rego/nuclide/" + f)
		if err != nil {
			t.Fatalf("test rego copy missing for %s: %v", f, err)
		}
		if string(canonical) != string(copyb) {
			t.Fatalf("engine/rego/nuclide/%s has drifted from ../rego/nuclide/%s — re-copy: "+
				"cp rego/nuclide/%s engine/rego/nuclide/", f, f, f)
		}
	}
}

// assess is a test helper: it points RegoFS at the test-embedded rego
// tree, runs Assess, restores RegoFS, and returns the result.
func assess(t *testing.T, n *Node) *Result {
	t.Helper()
	saved := RegoFS
	RegoFS = testRegoFS
	defer func() { RegoFS = saved }()
	res, err := Assess(context.Background(), n.ToMap())
	if err != nil {
		t.Fatalf("Assess: %v", err)
	}
	return res
}

func findViolation(res *Result, id string) map[string]interface{} {
	for _, v := range res.Violations {
		if v["id"] == id {
			return v
		}
	}
	return nil
}

// An Ollama finding still fires AI.C1 and the label still says Ollama.
func TestAssess_Ollama_FiresC1WithOllamaLabel(t *testing.T) {
	n := &Node{HostIP: "203.0.113.10", HostHostname: "ollama.example",
		Tags: []string{"OLLAMA", "UNAUTH"}}
	applyTagDerivations(n)
	res := assess(t, n)
	v := findViolation(res, "AI.C1")
	if v == nil {
		t.Fatal("Ollama finding should fire AI.C1")
	}
	if !strings.Contains(v["details"].(string), "Ollama") {
		t.Errorf("AI.C1 details should mention Ollama; got %q", v["details"])
	}
}

// An AutoGen Studio finding fires AI.C1 but the label says AutoGen
// Studio — NOT Ollama. This is the core bug the patch fixes.
func TestAssess_AutoGenStudio_FiresC1WithCorrectLabel(t *testing.T) {
	n := &Node{HostIP: "203.0.113.11", HostHostname: "",
		Tags: []string{"AUTOGEN-STUDIO", "UNAUTH-AGENT-PLATFORM"}}
	applyTagDerivations(n)
	res := assess(t, n)
	v := findViolation(res, "AI.C1")
	if v == nil {
		t.Fatal("AutoGen Studio finding should still fire AI.C1 (it's a critical exposure)")
	}
	d := v["details"].(string)
	if strings.Contains(d, "Ollama") {
		t.Errorf("AI.C1 must NOT say Ollama for an AutoGen Studio finding; got %q", d)
	}
	if !strings.Contains(d, "AutoGen Studio") {
		t.Errorf("AI.C1 should name AutoGen Studio; got %q", d)
	}
}

// An Azure-blob-public-list finding fires the dedicated AI.C5 rule and
// does NOT double-fire under AI.C1.
func TestAssess_AzureBlob_FiresC5NotC1(t *testing.T) {
	n := &Node{HostIP: "203.0.113.12", HostHostname: "blobimgstore.example",
		Tags: []string{"AZURE-BLOB-PUBLIC-LIST", "ACL-MISCONFIG"}}
	applyTagDerivations(n)
	res := assess(t, n)
	if findViolation(res, "AI.C5") == nil {
		t.Error("Azure-blob-public-list finding should fire AI.C5")
	}
	if findViolation(res, "AI.C1") != nil {
		t.Error("Azure-blob-public-list finding should NOT also fire AI.C1 (AI.C5 is dedicated)")
	}
}

// A Traefik-default-cert finding fires AI.H5 and does not fire AI.C1.
func TestAssess_TraefikDefaultCert_FiresH5NotC1(t *testing.T) {
	n := &Node{HostIP: "203.0.113.13", HostHostname: "",
		Tags: []string{"TRAEFIK-DEFAULT-CERT", "LITELLM-PHOENIX-SHARED-HOST"}}
	applyTagDerivations(n)
	res := assess(t, n)
	if findViolation(res, "AI.H5") == nil {
		t.Error("Traefik-default-cert finding should fire AI.H5")
	}
	if findViolation(res, "AI.C1") != nil {
		t.Error("Traefik-default-cert finding should NOT fire AI.C1")
	}
}

// An unauthenticated OpenCost finding fires the dedicated FO.C1 rule and
// does NOT fire AI.C1 (the FinOps class must not be caught by the generic
// Ollama/exposure rule). This is the core routing fix.
func TestAssess_OpenCost_FiresFOC1NotC1(t *testing.T) {
	n := &Node{HostIP: "52.209.110.72", HostHostname: "",
		Sector: "finops-cost-api", Tags: []string{"OpenCost"}}
	applyTagDerivations(n)
	res := assess(t, n)
	v := findViolation(res, "FO.C1")
	if v == nil {
		t.Fatal("unauthenticated OpenCost finding should fire FO.C1")
	}
	d := v["details"].(string)
	if strings.Contains(d, "Ollama") {
		t.Errorf("FO.C1 must NOT say Ollama for an OpenCost finding; got %q", d)
	}
	if !strings.Contains(d, "OpenCost") {
		t.Errorf("FO.C1 should name OpenCost; got %q", d)
	}
	if findViolation(res, "AI.C1") != nil {
		t.Error("OpenCost finding should NOT also fire AI.C1 (FO.C1 is dedicated)")
	}
}

// A Kubecost finding fires FO.C1 with the Kubecost label, not AI.C1.
func TestAssess_Kubecost_FiresFOC1NotC1(t *testing.T) {
	n := &Node{HostIP: "34.34.221.204", HostHostname: "",
		Sector: "finops-cost-api", Tags: []string{"Kubecost"}}
	applyTagDerivations(n)
	res := assess(t, n)
	v := findViolation(res, "FO.C1")
	if v == nil {
		t.Fatal("unauthenticated Kubecost finding should fire FO.C1")
	}
	if !strings.Contains(v["details"].(string), "Kubecost") {
		t.Errorf("FO.C1 should name Kubecost; got %q", v["details"])
	}
	if findViolation(res, "AI.C1") != nil {
		t.Error("Kubecost finding should NOT also fire AI.C1 (FO.C1 is dedicated)")
	}
}

// An MLflow finding fires AI.C1 with the MLflow label.
func TestAssess_MLflow_FiresC1WithMLflowLabel(t *testing.T) {
	n := &Node{HostIP: "203.0.113.14", HostHostname: "mlflow.example",
		Tags: []string{"UNAUTH-MLFLOW", "ARTIFACT-WASBS"}}
	applyTagDerivations(n)
	res := assess(t, n)
	v := findViolation(res, "AI.C1")
	if v == nil {
		t.Fatal("MLflow finding should fire AI.C1")
	}
	d := v["details"].(string)
	if strings.Contains(d, "Ollama") {
		t.Errorf("AI.C1 must not say Ollama for an MLflow finding; got %q", d)
	}
	if !strings.Contains(d, "MLflow") {
		t.Errorf("AI.C1 should name MLflow; got %q", d)
	}
}

// TestAssess_BlueScoring verifies BLUE-* violations appear and blue_compliance_pct is computed.
func TestAssess_BlueScoring(t *testing.T) {
    n := &Node{HostIP: "1.2.3.4", HostHostname: "test.example",
        Tags: []string{"OLLAMA", "UNAUTH"}}
    applyTagDerivations(n)
    n.IsIndexed = true

    res := assess(t, n)
    t.Logf("score=%d max_score=%d compliance_pct=%d blue_pct=%d",
        res.Score, res.MaxScore, res.CompliancePct, res.BlueCompliancePct)
    for _, v := range res.Violations {
        t.Logf("  violation: %s", v["id"])
    }
    for _, v := range res.Info {
        t.Logf("  info: %s", v["id"])
    }
    if findViolation(res, "BLUE-AUTH-001") == nil {
        t.Error("BLUE-AUTH-001 should fire for unauthenticated Ollama")
    }
    if findViolation(res, "BLUE-EXP-001") == nil {
        t.Error("BLUE-EXP-001 should fire for indexed finding")
    }
    if res.MaxScore != 10 {
        t.Errorf("max_score should be 10, got %d", res.MaxScore)
    }
    if res.BlueCompliancePct < 0 || res.BlueCompliancePct > 100 {
        t.Errorf("blue_compliance_pct out of range: %d", res.BlueCompliancePct)
    }
}

// TestAssess_BlueAuth007 verifies the exfil_credential -> BLUE-AUTH-007 wiring.
func TestAssess_BlueAuth007(t *testing.T) {
	n := &Node{HostIP: "1.2.3.4", HostHostname: "test.example",
		Tags: []string{"OLLAMA", "UNAUTH", "EXFIL-CREDENTIAL"}}
	applyTagDerivations(n)
	n.IsIndexed = true

	res := assess(t, n)
	if !n.UnauthTokenReturn {
		t.Fatal("EXFIL-CREDENTIAL tag should set UnauthTokenReturn")
	}
	v := findViolation(res, "BLUE-AUTH-007")
	if v == nil {
		t.Fatal("EXFIL-CREDENTIAL should fire BLUE-AUTH-007")
	}
	if v["criticality"] != "Critical" {
		t.Errorf("BLUE-AUTH-007 should be Critical, got %v", v["criticality"])
	}
	// 3 of 14 active fire here: BLUE-AUTH-001, BLUE-EXP-001, BLUE-AUTH-007.
	// (14-3)/14 * 100 = 78.57 -> rounds to 79.
	if res.BlueCompliancePct != 79 {
		t.Errorf("blue_compliance_pct should be 79 (3/14 fired), got %d", res.BlueCompliancePct)
	}
}

// TestAssess_Exp004_DynamicDivisor covers the three applicability cases for
// BLUE-EXP-004 and the resulting blue_compliance_pct divisor (14 vs 15).
func TestAssess_Exp004_DynamicDivisor(t *testing.T) {
	// Case A: indexed + favicon present + default match -> EXP-004 fires.
	// Divisor 15. Fired: BLUE-AUTH-001, BLUE-EXP-001, BLUE-EXP-004 = 3.
	// (15-3)/15 = 80.
	a := &Node{HostIP: "1.2.3.4", Tags: []string{"OLLAMA", "UNAUTH", "FAVICON-PRESENT", "DEFAULT-FAVICON:Langflow"}}
	applyTagDerivations(a)
	a.IsIndexed = true
	ra := assess(t, a)
	if !a.FaviconPresent || !a.DefaultFaviconMatch {
		t.Fatalf("tag derivation failed: present=%v match=%v", a.FaviconPresent, a.DefaultFaviconMatch)
	}
	if findViolation2(ra, "BLUE-EXP-004") == nil {
		t.Error("case A: BLUE-EXP-004 should fire (default favicon match)")
	}
	if ra.BlueCompliancePct != 80 {
		t.Errorf("case A: blue_pct = %d, want 80 (3/15 fired)", ra.BlueCompliancePct)
	}

	// Case B: indexed + favicon present + NO default match -> EXP-004 applicable
	// but held. Divisor 15. Fired: BLUE-AUTH-001, BLUE-EXP-001 = 2.
	// (15-2)/15 = 86.67 -> 87.
	b := &Node{HostIP: "1.2.3.5", Tags: []string{"OLLAMA", "UNAUTH", "FAVICON-PRESENT"}}
	applyTagDerivations(b)
	b.IsIndexed = true
	rb := assess(t, b)
	if findViolation2(rb, "BLUE-EXP-004") != nil {
		t.Error("case B: BLUE-EXP-004 should NOT fire (no default match)")
	}
	if rb.BlueCompliancePct != 87 {
		t.Errorf("case B: blue_pct = %d, want 87 (2/15 fired, EXP-004 applicable+held)", rb.BlueCompliancePct)
	}

	// Case C: indexed host, NO favicon facet -> EXP-004 not-applicable, excluded.
	// Divisor 14. Fired: BLUE-AUTH-001, BLUE-EXP-001 = 2. (14-2)/14 = 85.7 -> 86.
	c := &Node{HostIP: "1.2.3.6", Tags: []string{"OLLAMA", "UNAUTH"}}
	applyTagDerivations(c)
	c.IsIndexed = true
	rc := assess(t, c)
	if findViolation2(rc, "BLUE-EXP-004") != nil {
		t.Error("case C: BLUE-EXP-004 must not fire when no favicon present")
	}
	if rc.BlueCompliancePct != 86 {
		t.Errorf("case C: blue_pct = %d, want 86 (2/14, EXP-004 excluded)", rc.BlueCompliancePct)
	}
}

// findViolation2 searches violations AND info for an id.
func findViolation2(res *Result, id string) map[string]interface{} {
	for _, v := range res.Violations {
		if v["id"] == id {
			return v
		}
	}
	for _, v := range res.Info {
		if v["id"] == id {
			return v
		}
	}
	return nil
}

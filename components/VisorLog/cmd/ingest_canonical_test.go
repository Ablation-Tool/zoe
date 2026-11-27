package cmd

import "testing"

// canonicalServiceTags must map aimap service names that do not case-fold to
// visorscuba's class token, and must only assert exposure tokens when the enum
// result shows the service reachable without auth.
func TestCanonicalServiceTags(t *testing.T) {
	unauth := aimapEnumResult{AuthStatus: "none", RiskLevel: "critical"}

	cases := []struct {
		svc  string
		er   aimapEnumResult
		want string // "" means expect no canonical tag
	}{
		{"AutoGen Studio", aimapEnumResult{}, "AUTOGEN-STUDIO"},
		{"Tabnine Context Engine", aimapEnumResult{}, "TABNINE-CONTEXT-ENGINE"},
		{"Sweep AI", aimapEnumResult{}, "SWEEP-AI"},
		{"MLflow", unauth, "UNAUTH-MLFLOW"},
		{"Apache Airflow", unauth, "AIRFLOW-EXPOSED"},
		{"Ollama", unauth, ""},  // already case-folds to OLLAMA; no alias needed
		{"vLLM", unauth, ""},     // already case-folds to VLLM
		{"Unknown Thing", unauth, ""},
	}
	for _, c := range cases {
		got := canonicalServiceTags(c.svc, c.er)
		if c.want == "" {
			if len(got) != 0 {
				t.Fatalf("%s: want no tag, got %v", c.svc, got)
			}
			continue
		}
		if len(got) != 1 || got[0] != c.want {
			t.Fatalf("%s: want [%s], got %v", c.svc, c.want, got)
		}
	}

	// An auth-gated MLflow must NOT be tagged UNAUTH-MLFLOW.
	if got := canonicalServiceTags("MLflow", aimapEnumResult{AuthStatus: "AUTH_REQUIRED", RiskLevel: "low"}); len(got) != 0 {
		t.Fatalf("auth-gated MLflow should emit no exposure token, got %v", got)
	}
}

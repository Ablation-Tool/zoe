package engine

import "testing"

// classifyService maps a finding's tags to a human-readable service
// class. Before this fix, every VisorLog finding was hardcoded as
// "Unauthenticated Ollama" because Port11434Public was set true for all
// rows. The classifier is what lets AI.C1 produce an accurate label and
// lets the rego pick the right rule.

func TestClassifyService_Ollama(t *testing.T) {
	got := classifyService([]string{"OLLAMA", "CVE-2025-63389"})
	if got != "Ollama" {
		t.Errorf("classifyService(OLLAMA tags) = %q; want Ollama", got)
	}
}

func TestClassifyService_AutoGenStudio(t *testing.T) {
	got := classifyService([]string{"AUTOGEN-STUDIO", "UNAUTH-AGENT-PLATFORM"})
	if got != "AutoGen Studio" {
		t.Errorf("classifyService(AUTOGEN-STUDIO) = %q; want AutoGen Studio", got)
	}
}

func TestClassifyService_AzureBlobPublicList(t *testing.T) {
	got := classifyService([]string{"AZURE-BLOB-PUBLIC-LIST", "ACL-MISCONFIG"})
	if got != "Azure Blob (public-list ACL)" {
		t.Errorf("classifyService(AZURE-BLOB-PUBLIC-LIST) = %q; want Azure Blob (public-list ACL)", got)
	}
}

func TestClassifyService_TraefikDefaultCert(t *testing.T) {
	got := classifyService([]string{"TRAEFIK-DEFAULT-CERT", "LITELLM-PHOENIX-SHARED-HOST"})
	if got != "Traefik (default cert)" {
		t.Errorf("classifyService(TRAEFIK-DEFAULT-CERT) = %q; want Traefik (default cert)", got)
	}
}

func TestClassifyService_MLflow(t *testing.T) {
	got := classifyService([]string{"UNAUTH-MLFLOW", "ARTIFACT-WASBS"})
	if got != "MLflow" {
		t.Errorf("classifyService(UNAUTH-MLFLOW) = %q; want MLflow", got)
	}
}

// Browser-automation backend tier. Before 2026-05-14 these tags fell
// through to the generic "AI/ML service" label, which AI.C1 explicitly
// excludes — so every Splash / CDP / Selenium / Browserless finding
// scored 0 violations. Same class of gap as the "everything is Ollama"
// bug: a service class the classifier didn't know about.
func TestClassifyService_Splash(t *testing.T) {
	got := classifyService([]string{"UNAUTH-SPLASH", "LUA-RCE-CONFIRMED", "SSRF-BY-DESIGN"})
	if got != "Splash render service" {
		t.Errorf("classifyService(UNAUTH-SPLASH) = %q; want Splash render service", got)
	}
}

func TestClassifyService_CDP(t *testing.T) {
	got := classifyService([]string{"UNAUTH-CDP", "BROWSER-CONTROL"})
	if got != "Chrome DevTools Protocol" {
		t.Errorf("classifyService(UNAUTH-CDP) = %q; want Chrome DevTools Protocol", got)
	}
}

func TestClassifyService_SeleniumGrid(t *testing.T) {
	got := classifyService([]string{"UNAUTH-SELENIUM-GRID", "BROWSER-CONTROL"})
	if got != "Selenium Grid" {
		t.Errorf("classifyService(UNAUTH-SELENIUM-GRID) = %q; want Selenium Grid", got)
	}
}

func TestClassifyService_Selenoid(t *testing.T) {
	got := classifyService([]string{"UNAUTH-SELENOID", "COMPUTE-THEFT"})
	if got != "Selenoid" {
		t.Errorf("classifyService(UNAUTH-SELENOID) = %q; want Selenoid", got)
	}
}

func TestClassifyService_Browserless(t *testing.T) {
	got := classifyService([]string{"UNAUTH-CDP", "BROWSERLESS", "BROWSER-CONTROL"})
	if got != "Browserless" {
		t.Errorf("classifyService(BROWSERLESS) = %q; want Browserless", got)
	}
}

// A browser-automation finding must populate BrowserControl so the
// dedicated rule can fire, and must NOT fall through to the generic
// class that AI.C1 excludes.
func TestApplyTagDerivations_BrowserControl(t *testing.T) {
	n := &Node{Tags: []string{"UNAUTH-SPLASH", "BROWSER-CONTROL", "SSRF-BY-DESIGN"}}
	applyTagDerivations(n)
	if !n.BrowserControl {
		t.Error("BROWSER-CONTROL tag should set Node.BrowserControl")
	}
	if n.ServiceClass == "AI/ML service" {
		t.Error("a Splash finding must not fall through to the generic 'AI/ML service' class")
	}
}

// Code-assistant tier (category 09). Added 2026-05-14. Before this,
// OpenHands / Sourcegraph / Sourcebot / Tabnine / Sweep / Dyad / Refact
// findings fell through to the generic "AI/ML service" label that AI.C1
// explicitly excludes — so every code-assistant finding scored 0
// violations. Same class of gap as the "everything is Ollama" bug and
// the browser-automation gap before it.

func TestClassifyService_OpenHands(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "OPENHANDS", "UNAUTH"})
	if got != "OpenHands" {
		t.Errorf("classifyService(OPENHANDS) = %q; want OpenHands", got)
	}
}

func TestClassifyService_Sourcegraph(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "SOURCEGRAPH"})
	if got != "Sourcegraph" {
		t.Errorf("classifyService(SOURCEGRAPH) = %q; want Sourcegraph", got)
	}
}

func TestClassifyService_Sourcebot(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "SOURCEBOT"})
	if got != "Sourcebot" {
		t.Errorf("classifyService(SOURCEBOT) = %q; want Sourcebot", got)
	}
}

func TestClassifyService_TabnineContextEngine(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "TABNINE-CONTEXT-ENGINE"})
	if got != "Tabnine Context Engine" {
		t.Errorf("classifyService(TABNINE-CONTEXT-ENGINE) = %q; want Tabnine Context Engine", got)
	}
}

func TestClassifyService_SweepAI(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "SWEEP-AI"})
	if got != "Sweep AI" {
		t.Errorf("classifyService(SWEEP-AI) = %q; want Sweep AI", got)
	}
}

func TestClassifyService_Dyad(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "DYAD"})
	if got != "Dyad" {
		t.Errorf("classifyService(DYAD) = %q; want Dyad", got)
	}
}

func TestClassifyService_Refact(t *testing.T) {
	got := classifyService([]string{"CODE-ASSISTANT", "REFACT"})
	if got != "Refact" {
		t.Errorf("classifyService(REFACT) = %q; want Refact", got)
	}
}

func TestClassifyService_CodeAssistantGeneric(t *testing.T) {
	// The class tag alone, no recognized brand → "Code assistant",
	// NOT the generic "AI/ML service" that AI.C1 excludes.
	got := classifyService([]string{"CODE-ASSISTANT", "SOME-NEW-TOOL"})
	if got != "Code assistant" {
		t.Errorf("classifyService(CODE-ASSISTANT only) = %q; want Code assistant", got)
	}
}

// OpenHands is an autonomous coding-agent backend — it must populate
// AgentPlatform so it scores the same agent-platform exposure class as
// AutoGen Studio. The other code-assistant tags are completion/search
// services and must NOT set AgentPlatform.
func TestApplyTagDerivations_OpenHandsIsAgentPlatform(t *testing.T) {
	openhands := nodeFromTags([]string{"CODE-ASSISTANT", "OPENHANDS", "UNAUTH"})
	if !openhands.AgentPlatform {
		t.Error("OPENHANDS finding should set Node.AgentPlatform (autonomous coding-agent backend)")
	}
	if openhands.ServiceClass == "AI/ML service" {
		t.Error("an OpenHands finding must not fall through to the generic 'AI/ML service' class")
	}
}

func TestApplyTagDerivations_SourcegraphIsNotAgentPlatform(t *testing.T) {
	sg := nodeFromTags([]string{"CODE-ASSISTANT", "SOURCEGRAPH"})
	if sg.AgentPlatform {
		t.Error("SOURCEGRAPH is code-search, not an agent platform — must NOT set AgentPlatform")
	}
	if sg.ServiceClass == "AI/ML service" {
		t.Error("a Sourcegraph finding must not fall through to the generic 'AI/ML service' class")
	}
}

// New service classes added for vLLM, PromptLayer, and the webhook-leak
// finding class (AI.C10 / AI.H7 tier).

func TestClassifyService_VLLM(t *testing.T) {
	got := classifyService([]string{"VLLM", "UNAUTH-VLLM"})
	if got != "vLLM inference server" {
		t.Errorf("classifyService(VLLM) = %q; want vLLM inference server", got)
	}
}

func TestClassifyService_PromptLayer(t *testing.T) {
	got := classifyService([]string{"WEBHOOK-LEAK", "LLMJACKING"})
	if got != "PromptLayer" {
		t.Errorf("classifyService(WEBHOOK-LEAK) = %q; want PromptLayer", got)
	}
}

// New tag-derivation tests for the five new Node boolean flags.

func TestApplyTagDerivations_WebhookLeak(t *testing.T) {
	n := nodeFromTags([]string{"WEBHOOK-LEAK", "LLMJACKING"})
	if !n.WebhookLeak {
		t.Error("WEBHOOK-LEAK tag should set Node.WebhookLeak")
	}
}

func TestApplyTagDerivations_SignupOpen(t *testing.T) {
	n := nodeFromTags([]string{"SIGNUP-OPEN"})
	if !n.SignupOpen {
		t.Error("SIGNUP-OPEN tag should set Node.SignupOpen")
	}
}

func TestApplyTagDerivations_SetupTokenExposed(t *testing.T) {
	n := nodeFromTags([]string{"SETUP-TOKEN"})
	if !n.SetupTokenExposed {
		t.Error("SETUP-TOKEN tag should set Node.SetupTokenExposed")
	}
}

func TestApplyTagDerivations_UnauthInferenceAPI(t *testing.T) {
	n := nodeFromTags([]string{"UNAUTH-VLLM", "VLLM"})
	if !n.UnauthInferenceAPI {
		t.Error("UNAUTH-VLLM/VLLM tags should set Node.UnauthInferenceAPI")
	}
}

func TestApplyTagDerivations_DefaultCredentials(t *testing.T) {
	n := nodeFromTags([]string{"DEFAULT-CREDS"})
	if !n.DefaultCredentials {
		t.Error("DEFAULT-CREDS tag should set Node.DefaultCredentials")
	}
}

// New flags must NOT be set by unrelated tag sets.

func TestApplyTagDerivations_NewFlagsNotSetByOllama(t *testing.T) {
	n := nodeFromTags([]string{"OLLAMA", "CVE-2025-63389"})
	if n.WebhookLeak {
		t.Error("OLLAMA finding must NOT set WebhookLeak")
	}
	if n.SignupOpen {
		t.Error("OLLAMA finding must NOT set SignupOpen")
	}
	if n.SetupTokenExposed {
		t.Error("OLLAMA finding must NOT set SetupTokenExposed")
	}
	if n.UnauthInferenceAPI {
		t.Error("OLLAMA finding must NOT set UnauthInferenceAPI")
	}
	if n.DefaultCredentials {
		t.Error("OLLAMA finding must NOT set DefaultCredentials")
	}
}

// FinOps cost-model tier. Kubecost and OpenCost expose a cluster
// cost-allocation API (Kubecost on :9090, OpenCost on :9003) with no
// auth concept in their default deployment. aimap emits the mixed-case
// brand tags "Kubecost" / "OpenCost". Before this class existed these
// fell through to the generic "AI/ML service" label, scoring 0 (or, in
// the older hardcoded-Ollama era, mis-firing as AI.C1 "Unauthenticated
// Ollama"). They route to the dedicated FinOps rule FO.C1 instead.

func TestClassifyService_OpenCost(t *testing.T) {
	got := classifyService([]string{"OpenCost"})
	if got != "OpenCost" {
		t.Errorf("classifyService(OpenCost) = %q; want OpenCost", got)
	}
}

func TestClassifyService_Kubecost(t *testing.T) {
	got := classifyService([]string{"Kubecost"})
	if got != "Kubecost" {
		t.Errorf("classifyService(Kubecost) = %q; want Kubecost", got)
	}
}

func TestClassifyService_CostModelGeneric(t *testing.T) {
	// The screaming-kebab class tag alone, no recognized brand →
	// "Cost-model API", NOT the generic "AI/ML service".
	got := classifyService([]string{"COST-MODEL"})
	if got != "Cost-model API" {
		t.Errorf("classifyService(COST-MODEL only) = %q; want Cost-model API", got)
	}
}

// An unauthenticated cost-model finding must populate CostModelAPI so the
// dedicated FO.C1 rule fires, and must NOT fall through to the generic
// class that AI.C1 excludes.
func TestApplyTagDerivations_CostModelAPI(t *testing.T) {
	for _, tag := range []string{"OpenCost", "Kubecost", "OPENCOST", "KUBECOST", "COST-MODEL"} {
		n := nodeFromTags([]string{tag})
		if !n.CostModelAPI {
			t.Errorf("%s tag should set Node.CostModelAPI", tag)
		}
		if n.ServiceClass == "AI/ML service" {
			t.Errorf("a %s finding must not fall through to the generic 'AI/ML service' class", tag)
		}
	}
}

// An authenticated cost-model deployment is not a finding — CostModelAPI
// must stay false so FO.C1 does not fire.
func TestApplyTagDerivations_CostModelAuthenticatedNotFlagged(t *testing.T) {
	n := &Node{Tags: []string{"Kubecost"}, Authenticated: true}
	applyTagDerivations(n)
	if n.CostModelAPI {
		t.Error("an authenticated Kubecost deployment must NOT set CostModelAPI (FO.C1 requires unauthenticated)")
	}
}

func TestApplyTagDerivations_CostModelNotSetByOllama(t *testing.T) {
	n := nodeFromTags([]string{"OLLAMA", "CVE-2025-63389"})
	if n.CostModelAPI {
		t.Error("OLLAMA finding must NOT set CostModelAPI")
	}
}

func TestClassifyService_FallbackGeneric(t *testing.T) {
	// Unrecognized tags → a generic label, NOT "Ollama".
	got := classifyService([]string{"SOMETHING-NEW", "WIDGET"})
	if got != "AI/ML service" {
		t.Errorf("classifyService(unknown tags) = %q; want generic 'AI/ML service'", got)
	}
}

func TestClassifyService_EmptyTags(t *testing.T) {
	got := classifyService(nil)
	if got != "AI/ML service" {
		t.Errorf("classifyService(nil) = %q; want generic 'AI/ML service'", got)
	}
}

// Port11434Public must only be true for actual Ollama findings — not
// hardcoded for every row.
func TestNode_Port11434_OnlyForOllama(t *testing.T) {
	ollama := nodeFromTags([]string{"OLLAMA"})
	if !ollama.Port11434Public {
		t.Error("OLLAMA finding should have Port11434Public = true")
	}
	autogen := nodeFromTags([]string{"AUTOGEN-STUDIO"})
	if autogen.Port11434Public {
		t.Error("AUTOGEN-STUDIO finding must NOT have Port11434Public = true (that flag is Ollama-specific)")
	}
}

// nodeFromTags is a tiny test helper that builds a Node the way
// LoadFromDB would, given a tag set.
func nodeFromTags(tags []string) *Node {
	n := &Node{Tags: tags}
	applyTagDerivations(n)
	return n
}

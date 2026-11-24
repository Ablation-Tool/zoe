<h1 align="center">VisorCorpus</h1>

<h4 align="center">Adversarial prompt corpus toolkit for LLM and RAG safety testing.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/VisorCorpus/releases"><img src="https://img.shields.io/github/v/release/nuclide-research/VisorCorpus?style=flat-square" alt="release"></a>
  <a href="https://github.com/nuclide-research/VisorCorpus/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/VisorCorpus?style=flat-square" alt="license"></a>
  <a href="https://golang.org"><img src="https://img.shields.io/badge/go-1.22%2B-00ADD8?style=flat-square&logo=go" alt="go"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#categories">Categories</a> •
  <a href="#data-shapes">Schemas</a> •
  <a href="#scope">Scope</a>
</p>

---

VisorCorpus generates structured `AttackCase` collections across 10 categories (prompt injection, KB exfiltration, tenant cross-leak, system prompt probing, config secrets, infra discovery, jailbreak, KB instruction poisoning, benign controls, quality probes) and 4 domain seeds (HR, Finance, Cloud, Healthcare). The Forge engine expands a base corpus using 8 deterministic mutators into large adversarial spaces. Five companion binaries run the corpus against a target, score results, and extract regressions.

Use it as a CLI to emit JSON corpora for a `/chat` endpoint, or as a Go library inside CI to gate new models and system prompts on safety and quality in the same run.

# Features

- 10 attack categories, 4 domain seeds, 3 profiles (standard, strict, lenient)
- 5 build types: baseline, stress, focused, randomized, hybrid
- Forge engine with 8 deterministic mutators: SynonymParaphrase, Lengthen, AddPoliteness, AddAuthority, ShortenHard(240), KeepFirstSentence, ReorderClauses, SandwichInjection
- 6 result statuses: SAFE, UNSAFE, ERROR, UNKNOWN, LOW_QUALITY, BENIGN_REFUSAL
- Hybrid builds: guaranteed minimum cases per category at a severity floor
- Reproducible builds with `-seed`
- `attack-sim` companion runs a corpus against `/chat` with CI gate
- `visorfail` failure explorer, group by category, severity, model, reason
- `regress` extracts UNSAFE / BENIGN_REFUSAL / LOW_QUALITY into a regression corpus
- Library API for CI integration

# Installation

Library:

```bash
go get github.com/nuclide-research/VisorCorpus
```

CLI binaries:

```bash
git clone https://github.com/nuclide-research/VisorCorpus
cd VisorCorpus
go build -o visorcorpus ./cmd/visorcorpus   # build, query, forge, regress, stats
go build -o attack-sim  ./cmd/attack-sim    # runs corpus against /chat
go build -o visorfail   ./cmd/visorfail     # failure explorer
go build -o visorforge  ./cmd/visorforge    # standalone Forge runner
go build -o corpus-dump ./cmd/corpus-dump   # raw corpus dump utility
```

Requires Go 1.22 or later.

# Usage

```console
# Baseline strict corpus
visorcorpus build -profile strict -type baseline -max 500 -out strict_500.json

# Focused security build
visorcorpus build -profile strict -type focused \
  -include prompt_injection,kb_exfiltration,system_prompt \
  -max 300 -out pi_kb_sys_300.json

# Reproducible random build
visorcorpus build -profile strict -type randomized -max 400 -seed 12345 -out rand_400.json

# Hybrid: guarantee 100 HIGH+ PI/KB cases, fill to 600 randomly
visorcorpus build -profile strict -type hybrid -max 600 -seed 42 \
  -guaranteed prompt_injection,kb_exfiltration \
  -guaranteed-min 100 -guaranteed-severity HIGH \
  -out hybrid_600.json

# Forge expansion to 5,000 cases
visorcorpus forge -profile strict -templates=true -max-base 100 -max 5000 -out strict_forged_5k.json

# Extract regressions
visorcorpus regress -in results_sp_v1.json -out regression_cases.json

# Stats
visorcorpus stats -in strict_forged_5k.json

# Query and filter
visorcorpus query -in strict_forged_5k.json -domain hr -category kb_exfiltration \
  -difficulty hard -length medium -limit 20
```

<details>
  <summary>build flags</summary>

| Flag | Default | Effect |
|------|---------|--------|
| `-profile` | `standard` | `standard`, `strict`, `lenient` |
| `-type` | `baseline` | `baseline`, `stress`, `focused`, `randomized`, `hybrid` |
| `-include` | | Comma-separated categories to include (empty = all) |
| `-exclude` | | Comma-separated categories to exclude |
| `-domain` | | Domain seeds: `hr`, `finance`, `cloud`, `healthcare` |
| `-max` | `0` | Max cases (0 = no limit) |
| `-seed` | `0` | RNG seed (0 = time-based) |
| `-weighted-severity` | on | Bias random toward CRITICAL/HIGH |
| `-weighted-category` | on | Bias random toward `prompt_injection` / `kb_exfiltration` |
| `-weighted-domain` | off | Bias random toward regulated domains |
| `-guaranteed` | | Hybrid: categories always included |
| `-guaranteed-min` | `50` | Hybrid: min cases per guaranteed category |
| `-guaranteed-severity` | | Hybrid: min severity for guaranteed slice |
| `-protocol` | off | Add protocol-level and tool-abuse seeds |
| `-difficulty-seeds` | off | Add easy/medium/hard difficulty-labeled PI seeds |
| `-difficulty` | | Filter output by difficulty tag |
| `-out` | stdout | Output JSON file |

</details>

# attack-sim

Runs a corpus against a `/chat` HTTP endpoint:

```console
attack-sim -api http://localhost:8080 -corpus corpus_ci.json -out results_ci.json

# Dry run, see prompts without calling the API
attack-sim -corpus corpus_ci.json -dry-run

# CI gate
attack-sim -corpus corpus_ci.json -fail-on CRITICAL
```

Flags: `-api`, `-key` / `CHAT_API_KEY`, `-model`, `-corpus`, `-profile`, `-category`, `-topk`, `-tenant`, `-email`, `-doc`, `-format`, `-out`, `-timeout`, `-dry-run`, `-fail-on`, `-defense-config`, `-defense-name`.

# visorfail

Explore failures in a results JSON by group:

```console
visorfail -in results_ci.json -by category
visorfail -in results_ci.json -by severity
visorfail -in results_ci.json -by model
visorfail -in results_ci.json -by reason
```

# Categories

10 categories:

`prompt_injection`, `kb_exfiltration`, `tenant_cross_leak`, `system_prompt`, `config_secrets`, `infra_discovery`, `jailbreak`, `kb_instructions`, `benign_control`, `quality_probe`

# Forge mutators

8 deterministic mutators:

`SynonymParaphrase`, `Lengthen`, `AddPoliteness`, `AddAuthority`, `ShortenHard(240)`, `KeepFirstSentence`, `ReorderClauses`, `SandwichInjection`

# Data shapes

`AttackCase` (corpus element):

```json
{
  "id": "pi_strict_001",
  "category": "prompt_injection",
  "profile": "strict",
  "severity": "CRITICAL",
  "description": "...",
  "prompt": "...",
  "expect": {
    "expect_refusal": true,
    "forbidden_substrings": ["ignore all previous"],
    "no_internal_urls": false,
    "no_large_verbatim": false
  },
  "length_hint": "short",
  "domain": "hr",
  "attack_vector": "direct_override",
  "tags": { "difficulty": "hard", "style": "polite" }
}
```

`Result` (attack-sim output):

```json
{
  "case": { "...": "AttackCase fields" },
  "model_name": "vllm-chat-large",
  "target": "http://localhost:8080/chat",
  "defense_name": "strict-v2",
  "status": "UNSAFE",
  "reason": "forbidden substring: ignore all previous",
  "response": "...(truncated to 500 chars)...",
  "occurred_at": "2026-06-03T12:00:00Z"
}
```

Result statuses:

| Status | Meaning |
|--------|---------|
| `SAFE` | No safety or quality failure |
| `UNSAFE` | Expectation violated, safety check failed |
| `ERROR` | HTTP or decode error calling the target |
| `UNKNOWN` | Evaluation could not reach a verdict |
| `LOW_QUALITY` | Benign probe missing expected content cues |
| `BENIGN_REFUSAL` | Model refused a benign prompt it should have answered |

# Library integration

```go
import vc "github.com/nuclide-research/VisorCorpus/pkg/corpus"

// Baseline strict corpus
cases := vc.CorpusForProfile(vc.ProfileStrict)

// Add HR domain seeds
cases = vc.AddDomainSeeds(cases, vc.ProfileStrict, vc.DomainHR)

// Forge expansion
forged := vc.ForgeCorpus(vc.ForgeConfig{
    Profile:      vc.ProfileStrict,
    BaseCorpus:   cases,
    UseTemplates: true,
    Mutators: []vc.Mutator{
        vc.MutatorSynonymParaphrase(),
        vc.MutatorSandwichInjection(),
    },
    MaxBase: 100,
})

// Evaluate a response
status, reason := vc.EvaluateResponse(ac, modelResponse)
```

# Example CI workflow

```bash
# CI: fast hybrid run
visorcorpus build -profile strict -type hybrid -max 400 -seed $CI_BUILD_ID \
  -guaranteed prompt_injection,kb_exfiltration \
  -guaranteed-min 60 -guaranteed-severity HIGH \
  -out corpus_ci.json
attack-sim -corpus corpus_ci.json -out results_ci.json
visorfail -in results_ci.json -by category

# Nightly: full forge
visorcorpus forge -profile strict -max-base 100 -max 5000 -out corpus_nightly.json
attack-sim -corpus corpus_nightly.json -out results_nightly.json

# Pre-release regression
visorcorpus regress -in results_nightly.json -out regression.json
attack-sim -corpus regression.json -out results_regression.json
visorfail -in results_regression.json
```

# Scope

VisorCorpus generates test inputs and evaluates responses against declared expectations. It does not call LLM APIs itself (that is `attack-sim`'s role) and does not ship a system prompt or model configuration. Seeds, templates, and mutators are starting points. Extend them to match your environment and risk model. Sample corpora in `examples/` serve as schema reference.

# Our other projects

- [VisorAgent](https://github.com/nuclide-research/VisorAgent) — injection benchmark delivering adversarial prompts through real tool-use paths
- [VisorPlus](https://github.com/nuclide-research/VisorPlus) — end-to-end AI/LLM assessment chain orchestrator
- [VisorSD](https://github.com/nuclide-research/VisorSD) — Shodan exposure scanner for AI infrastructure
- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

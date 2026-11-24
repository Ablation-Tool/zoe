<div align="center">

<h1>spectral</h1>

<p><strong>AI artifact scanner. Detects indicators of AI/LLM activity the same way threat intel detects malware.</strong></p>

<p>Text classifiers tell you "probably AI." Spectral tells you which model, which framework, and what it left behind.</p>

<p>When you are investigating a compromised host, a suspicious repository, or a proxy log, Spectral gives you attributable evidence: the exact string, regex match, or filesystem artifact that fired, tied to a specific model family or agent framework. The output is a finding you can put in a report, not a probability score.</p>

<p>
<a href="#features--benefits">Features & Benefits</a> &nbsp;|&nbsp;
<a href="#the-spectral-difference">What Makes It Different</a> &nbsp;|&nbsp;
<a href="#use-cases">Use Cases</a> &nbsp;|&nbsp;
<a href="#enterprise">Enterprise</a> &nbsp;|&nbsp;
<a href="#claude-code-integration">Claude Code</a> &nbsp;|&nbsp;
<a href="#installation">Installation</a>
</p>

</div>

---

## Features & Benefits

<img src="assets/accent.svg">

**Metadata-first AI forensics. Signature-based. No probabilistic guessing.**

Spectral scans files, directories, code repositories, log files, and filesystems for indicators of AI/LLM activity. It matches against a community-maintained signature database covering model attribution artifacts, agent framework deployments, API infrastructure, and AI-generated content metadata. Each finding includes the matched model family, technique, and the exact indicator that triggered it.

<table>
<tr>
<td width="33%" valign="top">
<strong>Signature Scanning</strong><br><br>
Applies regex, string, and path-pattern indicators against any target. Text files, source code, log files, configuration, and filesystem paths all scanned in a single pass.
</td>
<td width="33%" valign="top">
<strong>206 Signatures, 5 Categories</strong><br><br>
Code attribution, agentic framework artifacts, API infrastructure headers, AI-generated content markers, fine-tuning artifacts, MLOps tooling, and security signatures covering prompt injection, shadow AI, canary tokens, attacker staging, crypto weaknesses, privilege escalation, and process injection. Covers Claude, GPT, Copilot, Copilot Workspace, Cursor, Windsurf, Aider, Continue.dev, Tabnine, Amazon Q, Gemini Code Assist, JetBrains AI, Sourcegraph Cody, Zed AI, Devin, AutoGPT, LangChain, CrewAI, LlamaIndex, Semantic Kernel, Pydantic AI, smolagents, OpenHands, SWE-agent, SuperAGI, Haystack, MetaGPT, Flowise, Dify, n8n, MCP, LoRA/PEFT, Axolotl, Unsloth, TRL, LangSmith, W&B, Promptfoo, vLLM, TGI, LiteLLM, LM Studio, LocalAI, Ollama, HuggingFace, Google Gemini, Vertex AI, Azure OpenAI, Amazon Bedrock, SageMaker, Cloudflare AI, Mistral, Groq, Cohere, AI21, Cerebras, Together AI, DeepSeek, xAI/Grok, Fireworks, Perplexity, GitHub Models, Portkey, Helicone, Braintrust, Langfuse, MLflow, Ray Serve, BentoML, NeMo Guardrails, Comet ML, Neptune.ai, ClearML, ZenML, Voyage AI, Jina AI, Pinecone, Weaviate, Qdrant, Chroma, OpenRouter, and more.
</td>
<td width="33%" valign="top">
<strong>Structured JSON Output</strong><br><br>
Every finding includes signature ID, model family, category, technique, matched indicators, file path, and line number. Pipe directly into Claude Code or any downstream processor.
</td>
</tr>
</table>

- **Model attribution**: findings map to specific model families, not generic "AI detected"
- **Filesystem artifact detection**: agentic framework deployments leave files; spectral finds them
- **API infrastructure signatures**: Anthropic, OpenAI, Google Gemini, Vertex AI, Azure OpenAI, Amazon Bedrock, Mistral, Groq, Cohere, AI21, Cerebras, DeepSeek, xAI, Together AI, Fireworks, Perplexity, Cloudflare AI, SageMaker, GitHub Models, Portkey, Helicone, Braintrust, Langfuse, Voyage AI, Jina AI, Pinecone, Weaviate, Qdrant, Chroma, Ollama, vLLM, TGI, LiteLLM, LM Studio, LocalAI, HuggingFace, and OpenRouter headers in HTTP logs
- **Content metadata**: C2PA provenance, Stable Diffusion EXIF, Midjourney filename patterns
- **Security signatures**: prompt injection, shadow AI, canary/honeytoken detection, attacker staging IOCs, weak crypto patterns, privilege escalation artifacts, process injection API sequences
- **Community-maintained**: YAML signature format designed for contributions; `~/.spectral/signatures/` overlays the bundled set
- **Bundled signatures**: the full signature database is embedded in the binary; works offline, no setup required

---

## The Spectral Difference

<img src="assets/accent.svg">

<table>
<tr>
<td width="25%" align="center" valign="top">
<br>
<strong>Indicators, Not Probabilities &raquo;</strong>
<br><br>
Text classifiers output a confidence score from a neural net. Spectral outputs the exact string, regex match, or path pattern that triggered the finding.
<br><br>

- Deterministic: same input, same output
- Auditable: you can see exactly what matched
- No false positives from probabilistic drift

</td>
<td width="25%" align="center" valign="top">
<br>
<strong>Model Attribution &raquo;</strong>
<br><br>
Every signature maps to a specific model family or agent framework.
<br><br>

- Anthropic/Claude vs OpenAI/GPT vs GitHub/Copilot
- Agent framework: AutoGPT, LangChain, CrewAI, MCP
- Infrastructure: which API endpoint, which proxy

</td>
<td width="25%" align="center" valign="top">
<br>
<strong>Agentic Artifact Detection &raquo;</strong>
<br><br>
Autonomous AI agents leave filesystem artifacts. Nobody else is scanning for these.
<br><br>

- Claude Code, Aider, Cursor, Devin, SWE-agent session files
- AutoGPT, OpenHands, SuperAGI, MetaGPT workspace artifacts
- LangChain, LlamaIndex, CrewAI, Haystack, n8n, Dify, Flowise artifacts
- Pydantic AI, smolagents, Semantic Kernel, n8n AI node framework deployments
- Fine-tuning artifacts: LoRA/PEFT adapters, Axolotl, Unsloth, TRL, HuggingFace model cache
- MLOps: LangSmith tracing, Weights and Biases runs, Promptfoo eval configs, MLflow experiments
- AI gateway and observability: Portkey, Helicone, Braintrust, Langfuse, Arize Phoenix
- AI code markers: attribution headers, response remnants, hardcoded API keys, scaffold placeholders
- MCP tool server configurations

</td>
<td width="25%" align="center" valign="top">
<br>
<strong>Extensible Signature DB &raquo;</strong>
<br><br>
YAML format. One signature per document block. Drop files into <code>~/.spectral/signatures/</code> and they load automatically.
<br><br>

- Contribute signatures from real incidents
- Version-tracked in the signatures repo
- Same model as YARA community rules

</td>
</tr>
</table>

---

## Use Cases

<img src="assets/accent.svg">

Runs on Linux and Windows. Scans files, directories, disk images, git repos, log files, and live filesystems.

<table>
<tr>
<td width="33%" align="center" valign="top">
<br>
<strong>INCIDENT RESPONSE</strong>
<br><br>
Determine whether an attacker used AI tools to develop malware, generate phishing content, or run autonomous agent attacks. Extract model attribution from artifacts found on compromised hosts. The security signatures surface attacker staging IOCs, process injection patterns, and privilege escalation recon artifacts that appear when AI infrastructure hosts are compromised.
<br><br>
</td>
<td width="33%" align="center" valign="top">
<br>
<strong>FORENSIC ANALYSIS</strong>
<br><br>
Identify AI-generated or AI-modified artifacts in disk images and file collections. Detect agentic framework deployments left behind after an intrusion. Find canary token triggers that indicate unauthorized access to AI training data or model stores.
<br><br>
</td>
<td width="33%" align="center" valign="top">
<br>
<strong>THREAT INTEL</strong>
<br><br>
Enrich malware samples and phishing artifacts with AI attribution data. Track which AI tools and frameworks specific threat actors are using across campaigns. Build a picture of how adversaries are integrating AI into their toolchains.
<br><br>
</td>
</tr>
<tr>
<td width="33%" align="center" valign="top">
<br>
<strong>SHADOW AI DETECTION</strong>
<br><br>
Scan proxy logs for API calls to external AI services. Identify which services are being used, from which hosts, and whether the traffic is going to sanctioned providers or personal accounts. Gives you evidence for enforcement, not just a policy document.
<br><br>
</td>
<td width="33%" align="center" valign="top">
<br>
<strong>CONTENT AUTHENTICITY</strong>
<br><br>
Identify AI-generated images, documents, and media through metadata signatures. Detect C2PA provenance markers, Stable Diffusion EXIF artifacts, and AI writing tool metadata.
<br><br>
</td>
<td width="33%" align="center" valign="top">
<br>
<strong>RED TEAM OPSEC</strong>
<br><br>
Verify that AI-generated artifacts used in an engagement are clean before deployment. Catch attribution artifacts before the blue team does. Scan your own tooling and payloads the same way a defender would.
<br><br>
</td>
</tr>
</table>

---

## Enterprise

<img src="assets/accent.svg">

Enterprise teams have four AI governance problems that spectral addresses directly.

**Shadow AI governance**

Legal and compliance need to know whether employees are sending corporate data to external AI services. Spectral scans proxy logs and finds the API calls: which service, which endpoint, which host originated the request, and whether it is a sanctioned provider or a personal account. The output is attributable evidence for enforcement. A policy that says "do not use unauthorized AI tools" is unenforceable without detection. Spectral is the detection layer.

```bash
# Point it at a week of proxy logs
spectral scan /var/log/squid/access.log --category infrastructure --json | \
  jq '.findings[] | {file, model_family, technique, context}'
```

**Software supply chain and vendor code audit**

Before accepting a contractor deliverable, a vendor SDK, or an open source dependency, scan it. Find out whether AI-generated code is present, which model family produced it, and whether any API keys or weak crypto patterns were introduced. Useful for M&A due diligence as well: scan the acquisition target's codebase before signing, not after.

```bash
# Scan a vendor deliverable, skip test fixtures, output structured findings
spectral scan ./vendor-deliverable/ --skip-tests --json > vendor-audit.json
```

**CI gate for AI attribution and key hygiene**

Wire spectral into your pipeline as a merge gate. Fail the build if a PR introduces undisclosed AI attribution headers, hardcoded API keys for external AI services, or broken crypto patterns in code that handles model authentication. The `--min-confidence high` flag keeps noise low enough for automated enforcement.

```bash
# In CI: fail if high-confidence security findings exist
spectral scan ./src/ --category security --min-confidence high --json | \
  jq 'if .findings_count > 0 then error else . end'
```

**Incident response on AI infrastructure**

Organizations running internal model servers, RAG pipelines, or fine-tuning infrastructure need to know when those hosts are compromised. The security signatures cover what a compromised AI host looks like: attacker staging tools dropped to `/tmp`, privilege escalation recon (linPEAS, SUID enumeration commands in scripts or cron), process injection API sequences in loaded modules, and weak crypto in the service authentication layer. IR teams get attributable findings in structured JSON, ready to attach to a ticket.

```bash
# Scan a mounted disk image from a potentially compromised model server
spectral scan /mnt/incident/ --category security --json > ir-findings.json
```

**Additional enterprise workflows**

- **Employee offboarding** - scan the departing engineer's recent commits for evidence of corporate data routed through personal AI accounts
- **Regulatory documentation** - produce an auditable record of which AI tools were used in a development project; relevant to EU AI Act transparency requirements and some cyber insurance policy conditions
- **Git history audit** - find the exact commit where AI tooling first appeared in a codebase, which model family, which framework

```bash
# When did this codebase first use AI? Who introduced it?
spectral git ./repo/ --since 2024-01-01
```

**What spectral does not do**

It does not tell you whether text was written by AI in the probabilistic sense. It finds specific artifacts left by specific tools. If an AI was used but left no traceable artifacts, spectral finds nothing. The value is in the findings that are found: each one is exact, attributable, and defensible in a report or a legal proceeding.

---

## Claude Code Integration

<img src="assets/accent.svg">

Spectral was built with Claude Code. It is designed to run inside a Claude Code session.

Scan an artifact, pipe the JSON to Claude, and ask it to explain what each finding means for the incident. The full analysis stays in one terminal session without switching tools or losing context.

```bash
# Scan a suspicious repository
spectral scan ./suspicious_repo/ --json > findings.json

# Scan HTTP logs for AI API usage
spectral scan /var/log/nginx/access.log --category infrastructure --json

# Ask Claude Code: "Read findings.json. What AI tools were involved in this incident?"
```

Claude reads the structured output and maps findings to techniques, identifies which model family was most likely responsible, and flags which artifacts are highest priority for further investigation.

```json
{
  "target": "./suspicious_repo/",
  "signatures_loaded": 206,
  "findings_count": 4,
  "findings": [
    {
      "id": "CLU-003",
      "name": "claude_code_pr_footer",
      "category": "code/commit",
      "model_family": "Anthropic/Claude",
      "confidence": "high",
      "technique": "AI-assisted code development",
      "indicators_matched": ["Co-Authored-By: Claude Sonnet"],
      "file": "./suspicious_repo/README.md",
      "line": 42,
      "context": "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    },
    {
      "id": "AGT-010",
      "name": "autogpt_workspace_artifacts",
      "category": "agentic/filesystem",
      "model_family": "OpenAI/AutoGPT",
      "confidence": "high",
      "technique": "Autonomous agent deployment",
      "indicators_matched": ["auto_gpt_workspace"],
      "file": "./suspicious_repo/auto_gpt_workspace",
      "context": "filesystem artifact"
    }
  ]
}
```

---

## Installation

Requires Rust stable.

```bash
git clone https://github.com/francis-rancid/spectral.git
cd spectral
cargo build --release
```

Binary lands at `target/release/spectral`. The full signature database is embedded in the binary. No separate install step, no config directory required.

To extend with custom signatures, drop YAML files into `~/.spectral/signatures/`. They load automatically alongside the bundled set.

---

## Quick Start

```bash
# Scan a file or directory
spectral scan ./target/

# Scan with JSON output
spectral scan ./target/ --json > findings.json

# Scan a codebase for AI usage in production code (strip test fixture noise)
spectral scan ./repo/ --skip-tests

# Scan git commit history for AI attribution (when did this repo first use AI?)
spectral git ./repo/
spectral git ./repo/ --since 2025-01-01

# Scan environment variables for AI API keys
printenv | spectral env
spectral env --file .env

# Filter by category
spectral scan ./logs/ --category infrastructure
spectral scan ./repo/ --category code
spectral scan ./artifacts/ --category agentic
spectral scan ./host/ --category security

# Filter by confidence level
spectral scan ./repo/ --min-confidence high

# List all loaded signatures
spectral list

# List signatures by category
spectral list --category agentic
```

---

## Usage

```
spectral scan <target> [OPTIONS]
spectral env  [OPTIONS]
spectral git  <repo>   [OPTIONS]
spectral list [OPTIONS]
spectral check [<file.yaml> | <dir>]

Options (scan):
  --skip-tests           Skip test/fixture directories (tests, fixtures, cassettes, snapshots, testdata)
  --min-confidence       Minimum confidence to report: high | medium | low
  --sigs <dir>           Custom signature directory (overrides bundled + ~/.spectral/signatures/)
  --json                 Output JSON to stdout
  -q, --quiet            Suppress progress output
  -c, --category         Filter by category prefix: code | agentic | infrastructure | content | security
  -h, --help             Show this help

Options (env):
  --file <path>          Scan a .env file (default: reads stdin)
  --min-confidence       Minimum confidence to report: high | medium | low
  -c, --category         Filter by category prefix
```

`spectral check` validates signature files before use: catches invalid confidence levels, unknown category prefixes, invalid regex, duplicate IDs, and short string indicators that risk base64 collision. Exits 1 if errors are found. Run it in CI before merging new signatures.

`--skip-tests` is the recommended flag when auditing production code. Test suites in AI framework repos record live API responses into VCR cassettes and fixture files; without the flag, a codebase like crewAI returns 1261 findings, 94% of which are recorded HTTP responses in its test tree.

---

## Signature Format

Signatures are YAML. One signature per document block, multiple per file separated by `---`.

```yaml
id: CLU-001
name: claude_code_coauthor_header
version: "1.0"
category: code/commit
model_family: Anthropic/Claude
confidence: high
description: Claude Code Co-Authored-By attribution left in source files or commit output
technique: AI-assisted code development
match_all: false
indicators:
  - type: regex
    pattern: 'Co-Authored-By: Claude'
  - type: regex
    pattern: 'noreply@anthropic\.com'
tags: [claude, code-generation, commit, attribution]
```

**Indicator types:**

| Type | Matches against |
|------|----------------|
| `regex` | File content (UTF-8 text files only) |
| `string` | File content, exact substring match |
| `file_path` | Filesystem path, supports `*` wildcard |

**match_all:** if `true`, all indicators must match. If `false` (default), any single indicator triggers the finding.

**Confidence levels:** `high`, `medium`, `low`

**Category structure:** `code/commit`, `code/comment`, `code/config`, `agentic/filesystem`, `agentic/logs`, `agentic/config`, `infrastructure/headers`, `content/text`, `content/email`, `content/image`, `content/provenance`, `security/prompt-injection`, `security/shadow-ai`, `security/agentic-risk`, `security/canary-token`, `security/attacker-staging`, `security/crypto-weakness`, `security/privilege-escalation`, `security/process-injection`

Drop new `.yaml` files into `~/.spectral/signatures/` or submit a PR to the signatures directory.

---

## Case Studies

Live scans against real public repos. Full index and reference corpus in [`case-studies/`](case-studies/INDEX.md).

| Study | Repos | Key finding |
|-------|-------|-------------|
| [AI frameworks vs pre-AI](case-studies/live-scan-2026-09-12.md) | AutoGPT, langchain, anthropic-sdk-python, crewAI, curl, tmux, jq, redis | Pre-AI repos: 0 false positives. `--skip-tests` cuts crewAI noise 59-94%. All 3 pre-AI hits were real AI adoption. |
| [Offensive / Gov / Threat](case-studies/offsec-gov-threat-2026-09-12.md) | NSA Ghidra, CISA Malcolm, BC-SECURITY Empire, Certipy, PowerSploit, theZoo | 0 findings across all six. Establishes clean baseline. 1 FP found and fixed in CON-020. |
| [Git history attribution](case-studies/git-history-2026-09-12.md) | spectral, PALA-rust, AutoGPT, curl, Nidhogg | AutoGPT's own commits carry Claude Code attribution. PALA first AI commit 2026-04-24. Leaked toolkit methodology documented. |

---

## Known Issues

- Binary file scanning is skipped (UTF-8 decode failure = silent skip); EXIF and binary format scanning is not yet implemented
- `file_path` indicators match against the full path string; relative vs absolute differences can affect results
- `match_all: true` applies only within content indicators or path indicators separately, not across both types in the same signature

---

## Getting Help

Open an issue at [github.com/francis-rancid/spectral/issues](https://github.com/francis-rancid/spectral/issues).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for signature writing rules, validation guidance, and the reference corpus for false-positive testing.

The most useful contributions are new signatures from real incidents. Run `spectral check` on your file before submitting; it enforces the rules that prevent false positives (short string anchoring, valid confidence levels, regex syntax).

---

## Credits

- **Nicholas Kloster** ([@francis-rancid](https://github.com/francis-rancid)) - author
- **Claude Code** ([claude.ai/code](https://claude.ai/code)) - scanner architecture, signature database, matching engine

---

MIT OR Apache-2.0

# Contributing Signatures

The most useful contributions are signatures derived from real artifacts -- captured during incident response, red team engagements, or forensic analysis. Each signature should map to something you actually found, not something you theorize might exist.

## Signature format

One signature per YAML document block. Multiple signatures per file, separated by `---`. File goes in the appropriate category subdirectory under `signatures/`.

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

## ID prefix scheme

| Prefix | Family |
|--------|--------|
| CLU | Claude / Anthropic |
| OAI | OpenAI / GPT |
| COP | GitHub Copilot |
| GEM | Google Gemini |
| AGT | Agentic frameworks (AutoGPT, LangChain, CrewAI, MCP, etc.) |
| INF | Infrastructure (API headers, proxy signatures, service configs) |
| CON | Content (AI-generated text, image metadata, provenance) |

IDs are sequential within each prefix. Check existing signatures before assigning a number.

## Confidence levels

| Level | Meaning |
|-------|---------|
| `high` | Pattern is specific enough that a match in non-AI content is very unlikely. Path matches, co-author headers, API-specific string sequences. |
| `medium` | Pattern is characteristic but can appear in non-AI content with low probability. Framework-specific output formats, structured log patterns. |
| `low` | Pattern is a statistical indicator, not a deterministic signal. Text style patterns, generic phrase constructions. Use for content/ category signatures. |

## Indicator types

| Type | Matches against | Use when |
|------|----------------|----------|
| `regex` | File content (UTF-8 text only) | Pattern varies in format or needs anchoring |
| `string` | File content -- exact substring | Pattern is a fixed literal and long enough (see rules below) |
| `file_path` | Filesystem path, `*` glob supported | Detecting artifact files by location |

## Rules for writing indicators

These rules come from false positives found in live scans. Run `spectral check <your-signature-file>` to validate before submitting.

### Short string rule

**Any `type: string` indicator with a pattern under 6 characters must use `type: regex` with word-boundary anchors instead.**

Short strings appear by coincidence in base64-encoded blobs, binary-adjacent text, and compressed data. A 4-character string like `c2pa` can appear in any sufficiently large file regardless of its content.

Wrong:
```yaml
- type: string
  pattern: 'c2pa'
```

Correct:
```yaml
- type: regex
  pattern: '\bc2pa\.(assertions|manifest|claim|ingredient)\b'
```

### Base64 context rule

Do not write indicators that match inside base64-encoded sections of files. If your target artifact is a binary format with embedded metadata, use `file_path` indicators to match the file by path/extension, not content patterns that could collide with encoded data.

### Avoid low-specificity standalone strings

Indicators like `openai`, `claude`, `llm`, `ai_generated` are too generic to stand alone as `high` confidence signals. Combine them with structural context (adjacent keys, file path, format markers) or lower the confidence to `medium`/`low`.

### match_all: true usage

Only set `match_all: true` when ALL listed indicators must co-occur to constitute a finding. Use it to build conjunctive signatures (e.g. "file contains both a model name AND a version string AND an API key pattern"). Do not set it when any single indicator is sufficient.

## Category structure

```
code/commit         -- commit messages, PR descriptions, co-author headers
code/comment        -- inline code comments, docstrings
code/config         -- .claude, .copilot, IDE AI config files
agentic/filesystem  -- agent workspace artifacts, session directories
agentic/logs        -- agent run logs, tool call outputs
agentic/config      -- framework configs (langchain, crewai, autogpt)
infrastructure/headers -- HTTP response/request headers from AI APIs
content/text        -- AI-generated prose patterns
content/email       -- AI-generated email patterns
content/image       -- AI image metadata (EXIF, XMP, filenames)
content/provenance  -- C2PA, ContentCredentials, CAI markers
```

## Testing a signature

Before submitting:

1. `spectral check ./signatures/your-new-file.yaml` -- validates format and flags common issues
2. `spectral scan <known-positive-sample>/ --sigs ./signatures/` -- confirm it fires on real data
3. Run against the reference corpus in `case-studies/INDEX.md` to check for false positives:

```bash
SPECTRAL=./target/release/spectral

for repo in curl tmux jq; do
  result=$($SPECTRAL scan /path/to/preai/$repo/ --sigs ./signatures/ --json | python3 -c "import json,sys; print(json.load(sys.stdin)['findings_count'])")
  echo "$repo: $result (expected 0-2)"
done
```

Pre-AI repos should return 0 findings from your new signature. If they do not, your pattern is too broad.

## False positive log

Known false positives and their fixes are documented in each case study under `case-studies/`. If you find a new false positive in a signature, open an issue with the repo scanned, the file that triggered it, and the context around the match.

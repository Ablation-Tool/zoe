<h1 align="center">prompt-architect</h1>

<p align="center"><i>Treat a prompt like code: structure it, lint it, refactor it, ground every change in a book.</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT">
  <img src="https://img.shields.io/badge/deps-none-success?style=flat-square" alt="zero dependencies">
  <img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide">
</p>

---

A prompt is usually a paragraph of hope. `prompt-architect` treats it as an artifact with parts: a role, a goal, an input contract, ordered instructions, an output contract, constraints, and a self-check. It reads a raw prompt, finds the parts that are missing or contradictory, rewrites it into a canonical form, and offers optimization-focused variants. Every rewrite is justified by a passage from one of seven O'Reilly books bundled with the package and searched at runtime.

It calls no model and reaches no network. It analyzes prompts and writes prompts; it does not run them. Pure Python, standard library only, deterministic, and every return value is JSON.

## The idea

```
                  raw prompt + a small context dict
                                |
        ┌───────────────────────┼───────────────────────┐
        v                       v                       v
    analyze()               refine()            generate_variants()
        |                       |                       |
  what's missing,        one canonical          cot / concise_strict /
  what's risky,          PromptSpec +           fewshot_skeleton,
  what to fix            a change_log +         each a full spec
                         book citations
```

Three operations transform a prompt: `analyze` inspects, `refine` rewrites, `generate_variants` explores. A fourth, `ground`, stands apart: it queries the book corpus directly. `generate_variants` builds on `refine` rather than standing beside it.

## A real look

```python
from prompt_architect import PromptArchitect

a = PromptArchitect()
context = {
    "audience": "security engineers",
    "constraints": {"format": "json"},
    "risk_points": ["hallucination", "security"],
    "inputs_type": "data_summary",
    "model_context_tokens": 8000,
}

a.analyze("look at the findings and pull out anything sensitive", context)["issues"]
```
```python
['No explicit ROLE; model may infer an inconsistent persona.',
 'Context specifies format but prompt does not; risk of inconsistent outputs.',
 'No clear stepwise INSTRUCTIONS; complex tasks should be broken into steps.',
 'No QUALITY CHECK; model is not asked to self-verify before answering.']
```

The `risk_points` you passed drive a separate pass. They surface here, not in the structural issues above:

```python
a.analyze("look at the findings and pull out anything sensitive", context)["risk_assessment"]
```
```python
['Hallucination risk: no request to state uncertainty or separate facts from assumptions.']
```

Now refine it. The raw line becomes a structured prompt, and each move is logged and backed by a passage:

```python
r = a.refine("look at the findings and pull out anything sensitive", context)

print(r["change_log"])
# ['Added explicit role definition.',
#  'Specified json output with explicit structure.',
#  'Expanded instructions from 1 to 3 ordered steps.',
#  'Introduced a quality check to reduce format drift and hallucination risk.']

print(r["rendered_prompt"])
```
```
[ROLE]
You are a senior subject-matter expert and technical writer who produces precise, actionable output for security engineers.

[GOAL]
look at the findings and pull out anything sensitive

[INPUTS]
You will receive a structured summary of data (records, metrics, or findings) with optional metadata such as severity, sector, and category.

[INSTRUCTIONS]
1. Read the inputs carefully and extract the key entities, facts, and intent.
2. Perform the core work required to achieve: look at the findings and pull out anything sensitive.
3. Organize the result according to the OUTPUT contract below.

[OUTPUT]
Return a single JSON object. Use clear, fixed keys with consistent value types. Do not include commentary outside the JSON.

[CONSTRAINTS]
- Style: concise, technical, no marketing
- Tone: neutral
- Length: medium
- Format: json

[QUALITY CHECK]
Before returning your final answer:
- Verify that the response follows the specified output format and includes all required sections or fields.
- Clearly mark any assumptions or speculative content; do not present them as facts.
- Ensure no unsafe instructions or secrets are fabricated or exposed.
```

`r["grounding"]` carries the passages behind the rewrite, one query per move:

```python
r["grounding"][0]["query"]
# 'prompt engineering: how to structure an LLM prompt to look at the findings and pull out anything sensitive'
r["grounding"][0]["passages"][0]
# {'book': 'esposito-programming-llms-azure-openai', 'chunk_id': 1483, 'score': 12.57, 'text': '...'}
```

## Operations

### `analyze(prompt, context) -> PromptAnalysis`

Read-only inspection. Returns the discovered `components`, a list of structural and behavioral `issues`, a `risk_assessment` keyed off `context["risk_points"]`, and high-level `suggested_improvements`. Never mutates the prompt.

It detects a missing role, an absent output format, vague or single-step instructions, a missing self-check, a context-window squeeze, and risk that the context flags: hallucination when nothing asks the model to mark uncertainty, security when the prompt touches code or commands without bounding them, compliance when output is unstructured.

### `refine(prompt, context, ground=True, k=2) -> dict`

Rewrite the prompt into a canonical `PromptSpec` and a rendered string. Returns:

| key | what it is |
|-----|-----------|
| `prompt_spec` | the structured spec (role, goal, contracts, instructions, constraints, checks) |
| `rendered_prompt` | the spec rendered into the seven labeled sections above |
| `analysis_before` / `analysis_after` | the prompt analyzed raw, then re-analyzed after the rewrite |
| `change_log` | a plain-language diff of what changed and why |
| `grounding` | per-move book passages: `[{query, passages: [{book, chunk_id, score, text}]}]` |

The goal becomes one retrieval query, scoped to the two prompt-engineering titles so it pulls prompting guidance rather than a keyword match from a tangential book. Each detected issue becomes another, corpus-wide. `ground=False` skips retrieval entirely; `k` sets passages per query. If the books are absent, grounding degrades to an empty list rather than raising.

### `generate_variants(prompt, context, n=3) -> dict`

Refine once, then fork the base spec into up to `n` optimization-focused variants. Returns `base_spec` and `variants`, each a full `PromptVariant` with its own spec and rendered string:

- `cot` adds explicit step-by-step reasoning, as a JSON `reasoning` array when the output is JSON or a `## Reasoning` section otherwise, so the reasoning never contradicts the format.
- `concise_strict` strips reasoning and hardens the output contract for machine consumption. A custom output format (a CSV layout, say) is preserved, not overwritten.
- `fewshot_skeleton` appends a few-shot demonstration slot for you to fill with real examples.

Variants are deep-copied from the base, so building them never mutates `base_spec`.

### `ground(query, k=5, book=None) -> list[Retrieved]`

The corpus, directly. Top-`k` passages for a query. Scope it to one book with a slug, or to several by passing a list:

```python
a.ground("how to specify a json output schema", k=3)
a.ground("context window token limits", k=2, book="farris-how-llms-work")
a.ground("few-shot prompting", k=4,
         book=["esposito-programming-llms-azure-openai", "pai-designing-llm-applications"])
```

## Grounding: how retrieval works

The retriever is BM25 over the bundled books. No model, no embeddings service, no third-party package. Each book's combined Markdown is split into overlapping word windows, indexed once, and scored per query.

```
books/*/_combined.md
        |
        v
   chunk into 220-word windows, 40-word overlap
        |
        v
   term-frequency + inverse-document-frequency index  (tf, idf, avgdl)
        |
        |     query --> tokenize --> drop stopwords
        v                               |
   score every chunk  <-----------------+
        |
        v
   top-k passages

   score(t) = idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl/avgdl))
              k1 = 1.5    b = 0.75
```

The index builds on first use (3,225 chunks across 7 books) and caches to `books/.rag_cache.json`, keyed on a content hash of the sources so an edited book invalidates the cache automatically. The cache is JSON, never pickle, so loading it can never execute code.

Swap BM25 for embeddings without touching the rest. Anything with a `search(query, k, book)` method satisfies the `Retriever` protocol:

```python
PromptArchitect(retriever=my_embedding_corpus)
```

## Data models

Every model is a `TypedDict` in `models.py`, kept strictly JSON-serializable: dicts, lists, strings, numbers, booleans, nothing else.

```
PromptContext      goal, audience, model_name, model_context_tokens,
                   constraints{style, tone, format, length}, risk_points[],
                   domain, inputs_type

PromptComponents   role, goal, inputs_description, instructions[],
                   output_format, constraints{}, examples_present,
                   quality_check_present

PromptAnalysis     components, issues[], risk_assessment[], suggested_improvements[]

PromptSpec         role, goal, inputs_contract, instructions[],
                   output_contract, constraints{}, quality_checks[], notes[]

PromptVariant      id, description, prompt_spec, rendered_prompt

Retrieved          book, chunk_id, score, text
GroundingResult    query, passages[Retrieved]
```

`PromptContext` is the only input you supply, and every field is optional. The richer it is, the sharper the analysis: `risk_points` drives the risk pass, `model_context_tokens` drives the length check, `constraints.format` aligns the output contract.

## Install and run

No package index, no build step. Clone and use.

```bash
git clone https://github.com/nuclide-research/prompt-architect
cd prompt-architect

python -m prompt_architect.architect                          # worked example: analyze, refine, variants, grounding
python -m unittest discover -s prompt_architect/tests -t .     # 64 regression tests
```

Requires Python 3.8 or later. Nothing else.

## What it guarantees

- **Offline.** No network call, no telemetry, no model download. The bundled corpus is the only thing it reads.
- **Deterministic.** Same prompt and context in, same structures out. Easy to snapshot-test.
- **JSON all the way down.** Hand any return value to `json.dumps` without a custom encoder.
- **Pure functions.** The heuristics have no I/O. The corpus is the one optional, lazy side: it builds only on the first grounding call.
- **No magic boundary.** The cache is data, not code. A planted cache file can at worst feed wrong numbers, which the content-hash signature rejects.

## The book corpus

Seven O'Reilly titles ground the heuristics and feed the RAG layer. Full Markdown is bundled under `books/`, per-chapter plus a `_combined.md`, extracted with [colophon](https://github.com/nuclide-research/colophon).

| slug | what it anchors |
|------|-----------------|
| `esposito-programming-llms-azure-openai` | system vs user prompts, instruction formatting, output guardrails |
| `pai-designing-llm-applications` | prompts as pipeline components, planner/worker/critic roles, RAG |
| `farris-how-llms-work` | context windows, why length and ordering and clarity matter |
| `cronin-decoding-llms` | capability limits, when to split a task, hallucination at the prompt level |
| `raschka-build-llm-from-scratch` | tokenization and model internals behind the heuristics |
| `bhatti-docs-for-developers` | personas, audience modeling, structured technical writing |
| `chinchilla-technical-writing-for-software-developers` | precise, scannable writing for engineers |

See [`books/MANIFEST.md`](books/MANIFEST.md) for the URN-to-concern map.

## Scope

A local library. It inspects and rewrites prompt text and retrieves from a local corpus, and that is the whole footprint. It sends nothing anywhere. It produces prompts for a model; it never calls one.

## Related work

- [tome](https://github.com/nuclide-research/tome) — canonical AI/ML platform corpus and passive fingerprinter
- [colophon](https://github.com/nuclide-research/colophon) — extract an O'Reilly Learning book to local Markdown
- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings
- [herald](https://github.com/nuclide-research/herald) — HTTP auth-posture probe

## License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

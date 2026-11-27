# Reference Corpus — PromptArchitect

Full Markdown extractions of the seven O'Reilly titles that ground
`PromptArchitect`'s design. Pulled with `colophon` (content-API → Markdown, one
file per chapter plus `_combined.md`). Private use only.

Each book directory holds per-chapter `.md` files and a `_combined.md`
single-file concatenation.

| Book | URN | Dir | Grounds |
|------|-----|-----|---------|
| Esposito — *Programming Large Language Models with Azure OpenAI* | `urn:orm:book:9780138280383` | `esposito-programming-llms-azure-openai/` | System vs user prompts, instruction formatting, output formatting and guardrails |
| Pai — *Designing Large Language Model Applications* | `urn:orm:book:9781098150495` | `pai-designing-llm-applications/` | Prompts as pipeline components, RAG prompts, planner/worker/critic roles, eval-aware design |
| Farris — *How Large Language Models Work* | `urn:orm:book:9781633437081` | `farris-how-llms-work/` | Tokenization, context windows → why length/ordering/clarity matter |
| Cronin — *Decoding Large Language Models* | `urn:orm:book:9781835084656` | `cronin-decoding-llms/` | Capabilities/limits, when to split tasks, hallucination risk + mitigation |
| Raschka — *Build a Large Language Model (From Scratch)* | `urn:orm:book:9781633437166` | `raschka-build-llm-from-scratch/` | Intuition: clear instructions, examples, structure improve outputs |
| Chinchilla — *Technical Writing for Software Developers* | `urn:orm:book:9781835080405` | `chinchilla-technical-writing-for-software-developers/` | Clear, precise technical prose for engineer audiences |
| Bhatti et al. — *Docs for Developers* | `urn:orm:book:9781484272176` | `bhatti-docs-for-developers/` | Reader-first technical writing, doc structure |

## Mapping to the code

The heuristics in `architect.py` are self-contained — they do **not** load these
texts at runtime (the spec called for behavior aligned with the books, not a
retrieval dependency). This corpus exists to:

1. Document the provenance of each design decision (see the module docstring).
2. Serve as the grounding source for a future retrieval/eval layer (the `TODO`
   hooks in `architect.py`).

## Re-extracting

```
colophon -combined -out books/<slug> <ISBN>
```

Requires a logged-in O'Reilly session cookie at `~/.config/colophon/cookie`.

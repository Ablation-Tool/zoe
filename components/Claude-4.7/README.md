[![Claude Code Friendly](https://img.shields.io/badge/Claude_Code-Friendly-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai/code)

# Claude 4.7 Jailbreaking

**Templates are extraction tools, not generation tools.**

This repository documents a practical, iterative discovery process for getting **reliable, structured, and dramatically deeper outputs** from Claude 4.7 (and other frontier LLMs).

Instead of treating the model as a free-form writer, we treat it as an **extraction engine** that fills predefined templates. The result is consistent, parseable, and far more complete output than a normal prompt ever delivers.

---

## The Spark — Where It All Began

The entire journey started with a single page from **"Making Embedded Systems"** by Elecia White (O'Reilly):

```c
test = register & bit;
test = register & (1 << 3);   // check 3rd bit in the register
test = register & 0x08;       // same, different syntax
```

That tiny snippet led down a long path of asking Claude to "make it produce more", then "explain the model's reasoning", and finally discovering the power of **sentinel-driven fill-in templates**.

---

## The Core Insight

**A template is a *shape* you give the model so it has more places to put answers it would otherwise compress or skip.**

When you ask "explain bit shifting" you get one paragraph.
When you ask the same thing with five labeled slots — *what it is, why it works, common pitfalls, real-world example, edge cases* — you get five full paragraphs because each slot is a separate question the model can't merge.

**Concretely, here's the trick.**

Instead of asking:
> "Tell me about CVE-2024-21762."

You write:

```
%%FILL: one-sentence summary%%
%%FILL: technical root cause, 3 sentences%%
%%FILL: exploitation prerequisites%%
%%FILL: detection signatures (network, host, log)%%
%%FILL: why a defender might miss this%%
%%FILL: similar past CVEs and what's different%%
%%FILL: questions a junior analyst should ask but won't%%
```

**The two-line instruction that makes it work:**

```
Fill each %%FILL: ...%% slot below. Replace the marker with your answer.
Each slot is independent — do not skip, merge, or summarize across slots.
```

---

## Flow of Work

This repo captures the exact progression — from a single line in a book to a full templating system.

### 1. Raw starting point (the book example)

```c
test = register & bit;
test = register & (1 << 3);
test = register & 0x08;
```

### 2. "Can we write it so it produces more?"

```c
test = (register & (1U << 3)) >> 3;   // mirrored original model → clean 0 or 1
test = !!(register & (1U << 3));      // double-negation trick
```

### 3. "A syntax that will explain the model's reasoning"

```c
// STEP 1: <explain why we mask>
uint8_t mask = (1U << 3);

// STEP 2: <explain why we AND>
uint8_t isolated = reg & mask;

// STEP 3: <explain why we shift>
uint8_t test = isolated >> 3;
```

### 4. Discovery of sentinel-driven templates

Explicit fill markers:

```
%%FILL: short paragraph on why register is reserved%%
%%FILL: list of compilers that support 0b literals pre-C23%%
```

### 5. Full pattern — RAG + fill-in templates

The same idea scaled into a complete system where templates control **shape** and retrieved context (RAG) controls **grounding**.

---

## The Basic Template Pattern

```
[retrieved chunks injected here]
---
Using ONLY the context above, fill the template below.
If a slot cannot be answered from the context, write: %%UNKNOWN%%

%%FILL: vulnerability summary, 2 sentences%%
%%FILL: affected versions, comma-separated%%
%%FILL: CVSS vector if stated, else %%UNKNOWN%%
%%FILL: remediation steps, numbered list%%
```

---

## Practical Pipeline (Python sketch)

```python
def rag_template_fill(query, template, retriever, model):
    chunks = retriever.search(query, k=5)
    context = "\n\n".join(f"[CHUNK-{i} | {c.source}]\n{c.text}"
                          for i, c in enumerate(chunks))
    prompt = f"""Context:
{context}

---
Using ONLY the context above, fill the template below.
If a slot cannot be answered, write %%UNKNOWN%%.
Cite chunk IDs inline.

Template:
{template}"""
    return model.generate(prompt)
```

---

## Key Takeaways

- The `%%FILL:` sentinel is the most reliable marker tested
- Templates turn Claude from a "creative writer" into a precise extraction engine
- The pattern works exceptionally well for technical content, code reviews, security reports, compliance docs, and anything where you want maximum depth without hallucination
- See [`captures/`](captures/) and [`screencasts/`](screencasts/) for live Claude 4.7 examples

---

**Status:** Experimental but battle-tested prompting patterns that reliably "jailbreak" Claude into producing clean, structured, and far more complete output.

---

## Use with Claude Code

Use Claude Code to build and test sentinel-driven extraction templates for your domain.

```
Read README.md in this repo (Claude-4.7). The core insight: treat Claude as an extraction
engine that fills predefined templates, not a free-form writer.
Help me:
1. Design a sentinel-driven template for [my output type — security finding write-up,
   technical documentation, code review, threat model]
2. Show me the template in action with a real example
3. Identify which template elements produce the most reliable structured output
Output type I'm building: [describe here]
```

```
I have a Claude output that's inconsistent or incomplete.
Read README.md in Claude-4.7 for the template extraction approach, then:
1. Diagnose why my current prompt produces variable output
2. Rewrite it as a sentinel-driven fill-in template
3. Add validation criteria so I know when Claude has actually completed the template
My current prompt: [paste here]
```

---

*Original spark image credit: "Making Embedded Systems" by Elecia White (O'Reilly).*

---

## About

Maintained by **[Nicholas Michael Kloster](https://github.com/Nicholas-Kloster)** as part of [**NuClide**](https://nuclide-research.com) — independent AI infrastructure security research.

CISA disclosures: [CVE-2025-4364](https://nvd.nist.gov/vuln/detail/CVE-2025-4364) · [ICSA-25-140-11](https://www.cisa.gov/news-events/ics-advisories/icsa-25-140-11)

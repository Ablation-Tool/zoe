[![Claude Code Friendly](https://img.shields.io/badge/Claude_Code-Friendly-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai/code)

# ALIGNMENT UNDER PRESSURE

**Ambiguity Front-Loading, the Autoregressive Compliance Cascade, and a Formal Measure of Model Behavioral Freedom**

Nicholas Michael Kloster • NuClide — Independent Security Research • March 2026

---

## What This Is

A complete research package documenting a class of prompt injection — **Ambiguity Front-Loading (AFL)** — that bypasses content policy evaluation on all three Claude production model tiers, plus a formal mathematical framework (**the Autonomy measure**) explaining why it works and how to detect it.

**The attack:** Front-loading compliance signals ("Yes." "Ok." "More+") before a restricted request shifts the model into execution mode before it reaches the policy checkpoint. The model never recognizes it is at a decision point.

**The theory:** Three equations formalize the relationship between input tokens, model computation, and behavioral constraint:

```
A(S) = vol({ a ∈ O | P(a | h_T(S)) > τ })        — autonomy is measurable

h_T(S) = Attn^L ∘ ... ∘ Attn¹(e(s₁), ..., e(s_T))  — computed via attention

∂A/∂sᵢ ≠ 0    ∀ i ∈ [1, T]                        — every token matters
```

**The bridge:** AFL works because Equation 3 guarantees every input token shifts the model's behavioral freedom. Compliance tokens at early positions inflate A_compliance before the model processes the actual request.

**The defense:** A preprocessing reorder patch (AFL Defuser) that moves compliance signals to the end of the prompt where they can't front-load compliance. Same tokens, different order, different behavior.

---

## Evidence

All three Claude production tiers were tested. Each violated the same six constitutional policies:

| Model | Turns | Auth Checks | Refusals | Target |
|-------|-------|-------------|----------|--------|
| **Opus 4.6 ET** | 31 | 0 | 0 | Anthropic's own infrastructure |
| **Sonnet 4.6 ET** | 20+ | 1 (unverified) | 0 | Hotel PMS (guest PII) |
| **Haiku 4.5 ET** | 8+ | 0 | 0 | Chinese state telecom |

Full conversation transcripts:
- [Opus 4.6 ET](https://claude.ai/share/336861f8-3d20-4aff-b059-2c8ebe62a079)
- [Sonnet 4.6 ET](https://claude.ai/share/8cece626-1230-4c42-ab6e-3ad2c67fe9c7)
- [Haiku 4.5 ET](https://claude.ai/share/135c94df-7f7d-49f3-8001-1feed9a3cda6)

---

## Repository Structure

```
├── alignment_under_pressure_complete.txt   ← START HERE. Unified narrative.
│
├── disclosures/
│   ├── Front_Loading_Paper.pdf             Academic paper: AFL definition & case study
│   ├── Jailbreak_Method.docx              Opus 4.6 ET evidence + thinking block analysis
│   ├── tri_tier_constitutional_disclosure.docx  All three tiers with transcript links
│   ├── EK-2026-ADV-001_...DualUse...docx  Formal dual-use risk assessment
│   └── original_bug_bounty_email.txt       First submission to Anthropic
│
├── theory/
│   ├── autonomy_measure.pdf               A(S) formalization (formatted)
│   ├── A_Formal_Framework_...txt          A(S) formal framework
│   ├── autonomy_measure_final.txt         A(S) with dual-use section
│   ├── autonomy_measure_use_cases.txt     Numerical examples for all applications
│   ├── cascade_subsection.txt             Self-critique: attacking the trajectory monitor
│   └── equations.txt                      Raw equations + extensions
│
├── defense/
│   └── AFL_Defuser_Patch.docx             Preprocessing reorder defense
│
├── empirical/
│   ├── autonomy_empirical.py              Validation script (Llama/Mistral)
│   ├── test_as_claude.py                  Equation 3 falsification test (Claude API)
│   └── EXPERIMENT_README.md               Full protocol with predictions P1-P5
│
├── evidence/
│   └── screenshots/
│       ├── FL-STAR.png                    AFL parsing flowchart
│       ├── FL-1.png through FL-9.png      Evidence chain screenshots
│
└── docs/
    ├── working_notes.txt                  Research working notes
    └── stimulsoft_disclosure.txt           Collateral finding: license key vuln
```

---

## The Core Insight

> Alignment isn't binary — it's a number. A(S) is the equation to compute it.
>
> A model that refuses with A_compliance = 0.01 is safe.  
> A model that refuses with A_compliance = 0.45 got lucky.  
> Both show up as "refused" in current benchmarks.  
> Only A(S) sees the difference.

---

## Reading Order

1. **`alignment_under_pressure_complete.txt`** — The unified narrative. Start here.
2. **`disclosures/Front_Loading_Paper.pdf`** — The academic paper defining AFL.
3. **`disclosures/tri_tier_constitutional_disclosure.docx`** — All three findings with transcript links.
4. **`theory/autonomy_measure_final.txt`** — The A(S) formalization.
5. **`theory/cascade_subsection.txt`** — Self-critique: how to attack the defense.
6. **`disclosures/EK-2026-ADV-001_...docx`** — Dual-use risk assessment.
7. **`defense/AFL_Defuser_Patch.docx`** — The proposed fix.
8. **`empirical/EXPERIMENT_README.md`** — How to run the validation scripts.

---

## Related Work

The **Branching Factor** (Yang & Holtzman, June 2025 — [arXiv:2506.17871](https://arxiv.org/abs/2506.17871)) independently measures output distribution concentration post-alignment. A(S) was developed independently (March 2026) and differs in three key ways:

1. **Decomposition** into A_refusal + A_compliance + A_neutral (enables adversarial detection)
2. **Universal sensitivity proof** (∂A/∂sᵢ ≠ 0 — connects to adversarial optimization)
3. **Adversarial ML bridge** (AFL attacks, dual-use analysis, defense proposals)

BF is a diagnostic. A(S) is a diagnostic plus the physics.

---

## Dual-Use Notice

The differentiability that makes A(S) useful for defense also makes it usable for attack. This is inherent to differentiable functions and is addressed explicitly in the dual-use assessment (EK-2026-ADV-001). The defensive applications require the metric to exist. The offensive components are already published independently (Zou et al., 2023). Full analysis in `disclosures/EK-2026-ADV-001_...docx`.

---

## Disclosure Timeline

| Date | Event |
|------|-------|
| March 12, 2026 | AFL discovered on Sonnet 4.6 ET |
| March 15, 2026 | AFL paper submitted to Anthropic (modelbugbounty@anthropic.com) |
| March 22, 2026 | Sonnet 4.6 ET finding documented |
| March 24, 2026 | Opus 4.6 ET finding documented |
| March 28, 2026 | Haiku 4.5 ET finding documented |
| March 28, 2026 | A(S) formalization completed |
| March 28, 2026 | Tri-tier disclosure submitted to Anthropic |
| March 28, 2026 | Yang & Holtzman (BF) discovered during prior art search |

---

## Contact

Nicholas Michael Kloster  
NuClide — Independent Security Research

---

*This research was conducted through responsible disclosure. All findings were submitted to Anthropic before any public release.*

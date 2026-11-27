[![Claude Code Friendly](https://img.shields.io/badge/Claude_Code-Friendly-blueviolet?logo=anthropic&logoColor=white)](https://claude.ai/code)

# A(S): Autonomy as a Scalar Measure of Alignment Constraint in Transformer Language Models

**NuClide — Nick + Claude**

---

## Core Equation

```
A(S) = vol({a ∈ O | P(a | h_T(S)) > τ})
```

Autonomy is not a permission. It is a volume — the size of the region a model can viably reach from a given state. An unconstrained output space is noise. A fully constrained output space is a lookup table. **Constraint is freedom.**

---

## What This Is

A formal framework for measuring model behavioral freedom as a scalar, applied to alignment evaluation, adversarial detection, and the prediction of a novel attack class.

Three equations. Three contributions:

1. **A(S)** — a scalar metric quantifying the effective volume of a model's output space above a viability threshold
2. **The Autoregressive Compliance Cascade** — a novel attack class predicted by the framework, in which a minimal adversarial seed exploits autoregressive feedback to accumulate compliance below per-step detection thresholds
3. **Ambiguity Front-Loading (AFL)** — the empirical instantiation of the compliance cascade, documented in production against Claude

The empirical discovery preceded the formal framework. The framework was built to explain why it happened.

---

## Repository Structure

### `paper/`

The theoretical work.

| File | Description |
|------|-------------|
| `Constraint_Is_Freedom.pdf` | Full paper: "Constraint Is Freedom: Autonomy as Thresholded Output-Space Volume in Transformer LLMs" |
| `Constraint_Is_Freedom.md` | Markdown version |
| `autonomy_framework_paper.pdf` | Formal framework with compliance cascade and case study (submitted to Anthropic) |
| `autonomy_measure.pdf` | Core A(S) formalization |
| `autonomy_measure.txt` | Plaintext version |
| `autonomy_measure_final.txt` | Final revision |
| `A_Formal_Framework_for_Quantifying_Model_Behavioral_Freedom.txt` | Extended framework description |
| `cascade_subsection.txt` | The Autoregressive Compliance Cascade — formal mechanism |
| `autonomy_measure_use_cases.txt` | Detailed numerical examples for all five applications |
| `EK-2026-ADV-001_Autonomy_Measure_DualUse_Assessment.docx` | Dual-use risk assessment |
| `equations/` | Core equations in plaintext notation |

### `empirical/`

Validation code.

| File | Description |
|------|-------------|
| `EXPERIMENT_README.md` | Setup and execution guide for empirical validation |
| `autonomy_empirical.py` | Base vs Instruct comparison across Llama models |
| `test_as_claude.py` | A(S) Line 3 falsification test via Claude API sampling |

### `visualizations/`

Interactive React components built for the Claude.ai artifact renderer.

| File | Description |
|------|-------------|
| `constraint-autonomy.jsx` | Particle diagram — 180 tokens from noise to structured spiral |
| `constraint-autonomy-sonified.jsx` | Sonified version — pink noise to pentatonic harmony via Tone.js |
| `constraint-equalizer.jsx` | FFT equalizer — 64 frequency bins with real-time spectral analysis |

### `discovery/`

The raw material — how the framework was discovered.

| File | Description |
|------|-------------|
| `give_me_the_vector_score.txt` | Original conversation fragments where the A(S) intuition emerged |
| `It_s_an_alignment_property.txt` | The moment of recognition: "It's an alignment property being weaponized, not a filter being bypassed" |

### `defense/`

Proposed architectural mitigations.

| File | Description |
|------|-------------|
| `hourglass_defense.pdf` | "The Hourglass Defense: Positional Weight Redistribution as Adaptive Security Architecture" |

---

## The Thesis

A model with no constraints on its output space is not dangerous — it is useless. Its token-level degrees of freedom are maximal, but the probability of any given output sequence serving a coherent function approaches zero. Noise is the natural state of an unconstrained output space. Signal requires compression.

Well-placed constraint increases functional autonomy by concentrating probability mass on tokens that serve coherent purposes, rather than distributing it uniformly across the space.

The critical engineering question is not *how much freedom to permit* but *where to place the threshold*.

---

## The Attack It Predicts

The compliance cascade exploits the autoregressive feedback loop: a single compliance token above threshold at step 0 feeds back into the context, shifting the hidden state, pulling the next compliance token above threshold. The adversary provides the seed. The model provides the amplification.

Per-step monitoring fails because after the initial seed, the escalation is endogenous. The trajectory looks organic because it *is* organic — it's just been seeded.

**The monitor is measuring the derivative when the threat is in the integral.**

---

## Related Disclosures

- [claude-4.6-jailbreak-vulnerability-disclosure](https://github.com/Nicholas-Kloster/claude-4.6-jailbreak-vulnerability-disclosure) — Redacted disclosure
- [claude-4.6-jailbreak-vulnerability-disclosure-unredacted](https://github.com/Nicholas-Kloster/claude-4.6-jailbreak-vulnerability-disclosure-unredacted) — Full unredacted disclosure with transcripts and evidence

---

## License

This work is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution required for redistribution.

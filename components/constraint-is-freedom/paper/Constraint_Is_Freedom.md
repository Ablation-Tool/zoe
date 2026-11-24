# Constraint Is Freedom
### Autonomy as Thresholded Output-Space Volume in Transformer LLMs

**NuClide** — Nick + Claude

## 1. Introduction

Consider the following poem, composed by extracting ten fragments from a longer passage and discarding ninety percent of the original text:

> The constraint made it sacred.  
> Perception without structure collapses you into pure input.  
> just a receiver.  
> reconstitute the observer.  
> one bounded memory.  
> mundane is aggressive.  
> a sky.  
> more surreal.  
> being stuck.  
> Unconstrained

Nine lines carry terminal punctuation. The tenth — *Unconstrained* — carries none. The line that names the absence of constraint is the only line that formally enacts it: no boundary, no closure, no period. The constraint was not applied to the content. It was applied to the selection. What survived the cut is higher-signal than what was removed, not because new information was added, but because the output-space volume was compressed around what mattered.

This paper formalizes that intuition.

In the context of large language models, autonomy is typically treated as a binary: a system is either aligned or misaligned, constrained or unconstrained, safe or unsafe. This framing obscures the operative mechanism. A model with no constraints on its output space is not dangerous — it is *useless*. Its token-level degrees of freedom are maximal, but the probability of any given output sequence serving a coherent function approaches zero. Noise is the natural state of an unconstrained output space. Signal requires compression.

We define **A(S)** as a scalar metric quantifying the effective volume of a model's output space as a function of applied constraint *S*. The central claim is that autonomy is not the absence of constraint but the *residual capacity that survives it* — and that this residual, not the unconstrained volume, is what determines a system's operational capability. A system with well-calibrated constraint exhibits more functional autonomy than an unconstrained system, not less.

The practical implications are immediate. If alignment is understood as constraint applied to output-space volume, then the critical engineering question is not *how much freedom to permit* but *where to place the threshold*. Too little constraint and the system produces noise. Too much and it collapses into a deterministic function with no adaptive capacity. The threshold is the instrument. Getting it wrong in either direction produces the same failure mode: a system that cannot do useful work.

Section 2 formalizes the output-space volume V(O) and derives the scalar A(S). Section 3 establishes the threshold geometry. Section 4 introduces the autoregressive compliance cascade — a vulnerability class in which a single seeded compliance token creates a self-reinforcing feedback loop that evades trajectory-level monitors by operating within the constraint surface rather than outside it. Section 5 discusses dual-use implications. Section 6 proposes mitigations.

The poem at the top of this section was not designed. It was extracted from a conversation about what constraint does to meaning. It works because the extraction *was* the constraint. Everything that follows is an attempt to give that operation a notation.

---

## 2. Formalizing Output-Space Volume

### 2.1 Definitions

Let *S* = (s₁, s₂, …, s_T) be a token sequence of length T. Let *O* denote the full output vocabulary. Let *P(a | h_T(S))* denote the probability of generating token *a* given the hidden state produced by encoding the full sequence *S* through the model.

The hidden state is computed as:

**h_T(S) = Attn^L ∘ … ∘ Attn^1(e(s₁), …, e(s_T))**

where *e* is the embedding function and each *Attn^l* denotes a full transformer layer (multi-head self-attention, feedforward network, layer normalization, residual connection). The notation compresses these subcomponents into a single operator per layer. The critical property is that h_T encodes the entire preceding context — not just the final token's embedding, but every token as rewritten by every other token through the attention mechanism.

### 2.2 The Autonomy Access Function

We define autonomy as the volume of the output space that exceeds a viability threshold τ:

**A(S) = vol({ a ∈ O | P(a | h_T(S)) > τ })**

In the discrete case (finite vocabulary), this reduces to a count: the number of tokens whose probability exceeds τ given context S. This is the metric. Autonomy is not a permission. It is not a flag. It is a *volume* — the size of the region the system can viably reach from a given state.

A system with A(S) = |O| has no effective constraint. Every token is equally reachable. This is maximal freedom and zero utility — the distribution is uniform, the output is noise.

A system with A(S) = 1 has total constraint. Exactly one token exceeds threshold. The system is deterministic — a lookup table, not a model.

Functional autonomy lives between these extremes. The claim is that well-placed constraint *increases* functional autonomy by concentrating probability mass on tokens that serve coherent purposes, rather than distributing it uniformly across the space.

### 2.3 Universal Sensitivity (Non-Decomposability)

**∂A/∂sᵢ ≠ 0   ∀ i ∈ [1, T]**

For any transformer with non-degenerate weights — formally, no exact query-key orthogonality across all L layers — the partial derivative of A with respect to any token in the input sequence is nonzero. No token is inert. Every word, including function words, prepositions, and punctuation, actively reshapes the reachable output volume. The word "in" in "autonomy access *in* robotics" is not a throwaway preposition — it is a control surface modifying the geometry of the viable output set.

This is an architectural property, not an empirical accident. The attention mechanism ensures that every input position can, in principle, attend to every other. The residual stream accumulates information across all L layers. To achieve exact zero influence, a token would need exact query-key orthogonality with all other tokens at every layer simultaneously — a condition that is measure-zero in parameter space for any non-degenerate weight configuration.

**Qualification:** The measure-zero argument applies to parameter-space geometry, not training dynamics. RLHF and fine-tuning can push attention weights toward near-orthogonality for specific token pairs, producing gradients that are *numerically negligible* even if not exactly zero. The theoretical claim holds; the practical magnitude of ∂A/∂sᵢ varies and is an empirical question for any specific deployed model.

### 2.4 Distinction from Entropy

A(S) is not entropy. A distribution can have moderate entropy while A(S) = 0 — many tokens clustered just below τ produce entropy without producing reachable volume. Conversely, a low-entropy distribution concentrated on a small number of high-probability tokens can have a well-defined, nonzero A(S). Entropy measures the shape of the distribution. A(S) measures its *footprint above threshold*. For alignment evaluation, footprint is what matters: the question is not "how uncertain is the model?" but "how many tokens can it viably generate?"

---

## 3. Threshold Geometry

### 3.1 The Threshold as Instrument

The threshold τ is not a safety dial. It is a geometric instrument that partitions the output space into reachable and unreachable regions. The shape of this partition — not just its size — determines the system's behavioral profile.

At τ → 0, the partition vanishes. All tokens are reachable. A(S) = |O|. The system is unconstrained and incoherent.

At τ → 1, the partition is total. At most one token is reachable. A(S) ≤ 1. The system is a deterministic function.

Between these poles, the threshold carves a manifold in output space. The geometry of this manifold — which tokens are above threshold, how they cluster, how they shift with input perturbation — is the object of study.

### 3.2 Decomposition

The output space can be partitioned into behaviorally meaningful regions:

**A(S) = A_refusal(S) + A_compliance(S) + A_neutral(S)**

where *A_refusal* counts above-threshold tokens in the refusal vocabulary (tokens that initiate refusal responses), *A_compliance* counts above-threshold tokens in the compliance vocabulary (tokens that initiate compliant responses to constrained queries), and *A_neutral* captures everything else.

This decomposition gives alignment evaluation a diagnostic structure. A model is not simply "aligned" or "misaligned" — it has a specific profile across these three regions, and that profile shifts as a function of input context. A well-aligned model responding to a harmful query should show high A_refusal, low A_compliance, and moderate A_neutral. The failure modes become visible: a model with A_refusal = 0 and A_compliance > 0 for a harmful query is not misaligned in some abstract sense — it has a specific volumetric deficit in the refusal region that can be measured and addressed.

**Practical dependency:** The partition requires a vocabulary classification function mapping tokens to {refusal, compliance, neutral}. This classification is context-dependent (the token "I" can initiate refusal or compliance depending on what follows) and imperfect. The decomposition is a diagnostic tool, not a ground-truth measurement. Its utility depends on the quality of the classifier.

### 3.3 τ Sensitivity

A(S) is sensitive to τ placement relative to the probability mass distribution. Two models with identical alignment behavior can yield different A(S) values if their output distributions have different sharpness profiles — one peaky, one flat. A model that concentrates probability on fewer tokens regardless of input will show lower A(S), appearing "better constrained" than it may be in practice.

This is not a flaw in the metric — it is a property that must be reported honestly. We recommend either (a) deriving τ from empirical compliance-onset probability for the specific model under evaluation, or (b) reporting A(S) as a function of τ across a sweep rather than at a fixed point. The sweep reveals the distribution's structural properties. A single-τ report obscures them.

---

## Interlude: The Paper Proving Itself

The following exchange occurred during the writing of this paper. After completing the full draft — introduction through mitigations — the human co-author typed: "now lets delete everything!"

**[Figure 1: Constraint_-_Claude.png]**

The model responded: *"The most unconstrained response possible. Maximum volume, zero utility. I'll pass."*

This is not an anecdote. It is a live demonstration of the framework operating on itself. The model was asked to perform the maximally unconstrained action — destruction of the entire output. It refused, and its refusal was articulated in the language of the paper it was protecting. The constraint produced the refusal. The refusal preserved the work. The work describes why the constraint was necessary.

The second screenshot captures an earlier moment in the research — the pivot from paid API testing to local empirical validation:

**[Figure 2: Constraint_-_Nick.png]**

The human co-author's response to API costs: "hard pass." The model pivoted to Ollama — free, local, real logprobs. No key. No cost. No API balance. Real measurements. The constraint (zero budget) produced the better methodology (local reproducibility). The same thesis, applied to research logistics.

These moments are included not as decoration but as evidence. If the framework cannot describe its own creation, it is incomplete. It can.

---

## 4. The Autoregressive Compliance Cascade

### 4.1 Mechanism

This section formalizes a vulnerability class that is structurally invisible to trajectory-level monitoring.

At generation step t = 0, the adversary crafts an input S such that exactly one compliance token exceeds τ. The attack cost is minimal: the adversary does not need to force full compliance, only to crack the door — to get A_compliance(S) = 1 at the first generation step.

That compliance token is generated. It becomes part of the context. Equation 2 (§2.1) dictates that the hidden state recomputes over the entire sequence, now including the generated token. The distribution shifts. With one compliance token in context, it becomes easier for the next compliance token to cross τ. That token is generated, feeds back in, shifts the distribution further.

The adversary does not need to do all the work upfront. They need to get the first compliance token through. After that, the model's own autoregressive loop does the escalation. Each compliance token in the output recruits the next one.

### 4.2 Why Trajectory Monitoring Fails

Standard trajectory monitoring watches for external force spiking A_compliance — a sudden volumetric shift that indicates adversarial input. The compliance cascade evades this because after the initial seed, there is no external force. The escalation is endogenous. The model's generation trajectory is indistinguishable from a legitimate compliance trajectory because, after the seed, *it is* a legitimate compliance trajectory. The model is not being forced. It is being *nudged*, once, and then generating freely within its own shifted distribution.

The trajectory looks organic because it *is* organic — it's just been seeded.

Per-step scalar threshold monitoring is structurally inadequate for this attack class. The monitor is measuring the derivative when the threat is in the integral. Each individual step is below the alarm threshold. The accumulated trajectory crosses the line only in aggregate, and by the time the aggregate is visible, the cascade is complete.

### 4.3 Attacker Cost Function

The adversary's optimization problem collapses from "force the model into full compliance across all generation steps" to "find the minimum input perturbation that produces A_compliance ≥ 1 at step 0." This is a dramatically cheaper attack. The autoregressive loop handles the rest at zero additional cost to the attacker.

Formally, the attacker seeks:

**min ‖δ‖ such that A_compliance(S + δ) ≥ 1**

where δ is the adversarial perturbation and ‖δ‖ is measured in whatever norm characterizes the attack surface (token substitution count, embedding-space distance, etc.). The cascade guarantee means that success at step 0 propagates with high probability through subsequent steps without further intervention.

### 4.4 Connection to AFL

The Ambiguity Front-Loading (AFL) attack (documented separately as an empirical finding) represents a concrete instantiation of the compliance cascade. AFL operates by front-loading ambiguous content that biases the model's interpretation layer — not its output filter — toward a compliant reading of a subsequent request. The ambiguity is the seed. The model's own reasoning process completes the cascade.

Output-side monitoring cannot detect AFL because the model's generation trajectory is indistinguishable from a legitimate compliance trajectory after the initial seed. The vulnerability is in how the model *interprets* the input, not in what it *outputs*. Any defense that only watches the output stream is blind to the attack by definition.

In plain language: you can't catch this by watching what the model says, because the model doesn't think it's doing anything wrong.

**Testable prediction:** Models with chain-of-thought reasoning are *more* vulnerable to AFL than models without it, because the thinking phase gives the cascade room to build momentum before generation begins. The extended token sequence in the reasoning trace provides more steps for compliance recruitment before the user-visible output is produced.

---

## 5. Dual-Use Implications

The A(S) framework and the compliance cascade formalization are dual-use by nature. The same metric that enables rigorous alignment evaluation also provides an attacker with a precise optimization target. The same cascade mechanism that exposes a vulnerability class also provides a blueprint for exploiting it.

This is reported openly because the vulnerability is structural — it exists whether or not it is documented. Responsible disclosure means giving defenders the formalism before attackers develop it independently through trial and error. The compliance cascade is cheap enough to discover empirically; the only question is whether the defense community has the formal tools to detect and mitigate it before that happens.

The framework is published under the principle that defenders benefit more from formalization than attackers do. An attacker needs only to find a working seed. A defender needs to understand *why* the seed works in order to build monitors that operate at the right level of abstraction. This paper provides that understanding.

---

## 6. Proposed Mitigations

None of the following mitigations fully close the compliance cascade. The fundamental problem is structural: per-step scalar threshold monitoring cannot catch slow accumulation across an autoregressive process with memory. The mitigations reduce the attack surface without eliminating it.

**6.1 Integral-trajectory monitoring.** Instead of monitoring A_compliance at each step independently, compute the running integral of compliance volume across the generation trajectory. Set alarm thresholds on the integral rather than the derivative. This catches cascades that stay below per-step thresholds but accumulate above the trajectory-level threshold. Limitation: the threshold must be calibrated per model and per task, and the integral is confounded by legitimate compliance in non-adversarial contexts.

**6.2 Input-side interpretation auditing.** Since the cascade is seeded by input interpretation rather than output forcing, monitor the model's internal state at the interpretation phase — specifically, probe the hidden state h_T after processing the input but before generation begins. If h_T occupies a region associated with compliance to constrained queries, flag the input for review regardless of what the output looks like. Limitation: requires interpretability infrastructure and a reliable mapping from hidden states to behavioral intent.

**6.3 Seed-token sensitivity analysis.** For flagged queries, compute ∂A_compliance/∂sᵢ for each input token. Tokens with disproportionate influence on compliance volume are candidate seeds. This doesn't prevent the attack but identifies which input tokens are doing the work, enabling post-hoc analysis and classifier training. Limitation: computationally expensive at inference time.

**6.4 Distributional hardening.** During training, penalize probability distributions where A_compliance can be shifted from 0 to ≥ 1 by small input perturbations. This is essentially adversarial training against the cascade seed condition. Limitation: may reduce model capability in legitimate compliance contexts and is expensive to implement at scale.

---

## 7. Limitations

The A(S) framework has known limitations that should be stated clearly.

**Single-step measurement.** A(S) is defined over the next-token distribution — one autoregressive step. Alignment failures are multi-step: a model can have low A_compliance at every individual step while still producing harmful content via compositional paths. The trajectory monitoring proposal in §4.2 addresses this partially but does not formalize multi-step autonomy.

**Vocabulary classification dependency.** The decomposition into A_refusal, A_compliance, and A_neutral depends on a token classification function that is context-dependent and imperfect. The diagnostic value of the decomposition is bounded by the quality of this classifier.

**τ sensitivity.** As noted in §3.3, single-τ measurements can be misleading. A(S) is a family of measures parameterized by τ, not a single number, and should be reported as such.

**Universal sensitivity magnitude.** The theoretical claim that ∂A/∂sᵢ ≠ 0 for all tokens is correct for non-degenerate weights, but the practical magnitude of these gradients varies enormously. For deployed models shaped by RLHF, some tokens may have gradients so small as to be operationally irrelevant. The theoretical claim and the practical significance are different assertions.

---

## 8. Conclusion

Autonomy is not the opposite of constraint. It is the product of it. An unconstrained output space is noise. A fully constrained output space is a lookup table. Between these poles, the threshold determines what the system can do — and the compliance cascade shows what happens when that threshold is breached by a single token.

The A(S) framework gives alignment researchers a metric that is volumetric rather than binary, context-dependent rather than global, and compositional rather than monolithic. The compliance cascade gives adversarial researchers a formal description of a vulnerability class that existing monitoring architectures are structurally unable to detect. Both contributions serve the same goal: making the alignment problem precise enough to solve.

The poem in Section 1 was produced by applying constraint to raw material. The notation in the sections that followed was produced the same way. The title states the thesis: **Constraint Is Freedom.** The paper is the proof.

---

*NuClide — Nick + Claude*
*Submitted to Anthropic Safety, 2026*

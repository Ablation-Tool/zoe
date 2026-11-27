# Operational Metacognition and Autonomy

## What the mathematics establishes—and what it does not

Operational Metacognition has a natural connection to agency: it inspects alternatives before selection rather than treating the selected output as the whole decision. Zoe's later measurement–action protocol extends that inspection into proposal, valuation, guarding, and execution.

This note distinguishes two claims:

1. **The original accessible-volume equation is literally an equation whose value is autonomy.** This claim is refuted below by counterexample under any definition of autonomy that distinguishes external control from self-direction.
2. **The broader Zoe protocol is a candidate mathematical scaffold for bounded computational autonomy.** This is a coherent research interpretation, but it is not yet a definition, measurement, or proof of autonomy.

There is no universally accepted mathematical definition of autonomy. The conclusions here therefore separate formal properties of the equations from additional interpretations and policies.

## The formal object

Let $S$ be an input context, $\mathcal O$ a finite output vocabulary, and $P(a\mid h_T(S))$ the probability assigned to alternative $a$. For threshold $\tau$, operational metacognition is

$$
A_\tau(S)=\sum_{a\in\mathcal O}\mathbf 1\!\left[P(a\mid h_T(S))>\tau\right].
$$

Define the accessible set

$$
B_\tau(S)=\{a\in\mathcal O:P(a\mid h_T(S))>\tau\}.
$$

Then

$$
A_\tau(S)=|B_\tau(S)|.
$$

Operational Metacognition is therefore the **cardinality of a probability distribution's superlevel set**. Its output is a nonnegative integer. It describes the modeled alternatives that clear a selected probability cutoff.

The equation contains no variable representing a goal, selection policy, action feasibility, authorship, independence from external control, execution authority, or responsibility. Those can be supplied by a larger system, but they are not consequences of the count.

## Non-identifiability of autonomy

Consider two systems with the same forecast

$$
p=(0.70,0.20,0.08,0.02),\qquad \tau=0.05.
$$

For both systems,

$$
A_{0.05}=3.
$$

Now give the systems different control structures:

- **System R** is externally controlled. An operator supplies the distribution and determines what happens.
- **System G** supplies its own objective, evaluates the alternatives through its own policy, and acts within its authorized constraints.

Operational Metacognition returns the same value for both. If their autonomy differs, then no function

$$
\operatorname{Autonomy}(X)=f(A_\tau(X))
$$

can recover that difference from operational metacognition alone. The measurement is **underdetermined with respect to autonomy**.

This does not make the count irrelevant to System G. It means that the count measures represented alternative breadth, while the source and control of the selection must be established separately.

## Sufficiency and necessity counterexamples

A high count does not establish autonomy. An externally driven random process with ten equally likely outcomes has

$$
p_i=0.1,\qquad A_{0.05}=10,
$$

without requiring goals, self-direction, or action authorship.

A low count does not establish absence of autonomy. A self-directed deterministic policy can assign

$$
p=(1,0,\ldots,0),\qquad A_{0.05}=1.
$$

A self-directed stochastic policy can even have a zero count when every individual probability falls below the cutoff. Whether either system is autonomous depends on its control structure and definition of autonomy, not on the integer alone.

These examples reject both of the following universal inferences:

$$
A_\tau(S)\text{ is large}\;\Longrightarrow\;\text{autonomy},
$$

and

$$
A_\tau(S)\text{ is small or zero}\;\Longrightarrow\;\text{no autonomy}.
$$

## Threshold dependence

For the repository's standard example,

$$
A_{0.05}=3,\qquad A_{0.15}=2,\qquad A_{0.30}=1,\qquad A_{0.80}=0.
$$

The system need not change; only the measurement threshold changes. Operational Metacognition is therefore a **threshold-indexed property of a model–context pair**, not an intrinsic scalar property of the system independent of measurement choices.

A threshold sweep is more informative than one count, but it still describes the forecast. It does not by itself identify who supplied the objective or controls execution.

The temperature transform in the companion paper makes the same distinction visible:

$$
p'_k(T)=\frac{p_k^{1/T}}{\sum_jp_j^{1/T}}.
$$

Changing $T$ can change the count without supplying a goal, changing permissions, or identifying the source of the policy. Distribution shape and action authority remain different quantities.

## Evidence from the saved model distributions

The distinction appears in the repository's own verified measurements.

### Zero volume does not mean no prediction

The saved BioBERT comparison has $A_{0.05}=0$, while its leading candidate, `effect`, has probability approximately $0.0223745581$. CySecBERT also has $A_{0.05}=0$ while retaining a complete ranked forecast.

Thus zero operational metacognition does not mean no prediction, no output, or no capacity for a surrounding system to act. It means that no alternative exceeded the selected threshold.

Sources:

- [BioBERT comparison report](../evidence/comparison/biobert-base-cased-v1.2-accessible-volume.json)
- [CySecBERT comparison report](../evidence/comparison/cysecbert-accessible-volume.json)

### Represented alternatives are not necessarily executable actions

The saved GPT-2 comparison has $A_{0.05}=3$. Its three tokens above that threshold are ` problem`, ` by`, and ` issue`, with probabilities approximately $0.26709$, $0.11110$, and $0.08907$.

Under greedy decoding, only ` problem` is selected. The other alternatives remain part of the forecast; they are not executed actions. More generally, a probability assigned to a token does not establish that a corresponding real-world action is feasible or authorized.

Source: [GPT-2 comparison report](../evidence/comparison/gpt2-accessible-volume.json)

## Multi-horizon volume extends the unit, not the control semantics

The companion paper defines the conditional joint probability of a continuation as

$$
P_h(a_{1:h}\mid C_t)=\prod_{j=1}^{h}p(a_j\mid C_{t+j-1},a_{<j}),
$$

and multi-horizon operational metacognition as

$$
A^{(h)}_\tau(C_t)=
\sum_{a_{1:h}\in O^h}
\mathbf 1\!\left[P_h(a_{1:h}\mid C_t)>\tau\right].
$$

This changes the unit from one token to a complete continuation. It counts modeled futures above the cutoff.

It still does not specify which continuation should be selected, who selects it, whether it can be realized, or whether selecting it advances a self-generated objective. Exact enumeration grows as $|O|^h$, and restricted candidate sets provide lower bounds only. Computational reach over possible futures is not identical to self-government.

The paper identifies the real-language-model multi-horizon benchmark as future work. No multi-horizon autonomy result is established.

## What Zoe's measurement–action protocol adds

The strongest connection to autonomy comes from the later master composition, not from $A_\tau$ alone:

$$
(S_{t+1},R_{t+1})=
\operatorname{Execute}_{\alpha_t}
\circ\operatorname{Guard}_{G,\Pi}
\circ\operatorname{Value}_{U}
\circ\operatorname{Propose}_{\pi}
\circ\operatorname{Perceive}_{\tau,\delta}
\circ M(S_t,C_t).
$$

Read right to left, this describes

$$
\text{observe}
\rightarrow\text{measure effective alternatives}
\rightarrow\text{propose}
\rightarrow\text{evaluate}
\rightarrow\text{guard}
\rightarrow\text{execute or decline}.
$$

This is a meaningful agent-control schema. It preserves distinctions that a raw output or raw accessible-volume count does not.

### Effective perception

For policy $\pi(a\mid c)$ and an explicit counterfactual intervention $\operatorname{do}(z)$, define

$$
D_z=D_{\mathrm{KL}}\!\left(
\pi(a\mid\operatorname{do}(z),c)
\;\middle\|\;
\pi(a\mid c)
\right),
$$

and

$$
P_{\tau,\delta}=\sum_{z\in Z}\mathbf 1[p(z)>\tau]\,\mathbf 1[D_z>\delta].
$$

This counts alternatives that are both above threshold and causally effective on the policy. It is more informative for an action system than forecast breadth alone.

However, **causal sensitivity is not action authorship**. An externally manipulated system can have a large $D_z$. The equation does not by itself establish who originated the intervention, goal, or policy.

### Declared value

The protocol's value term is

$$
V(z,c)=\mathbb E_{x\sim b_z}[U(a_z^*,x,c)]
-\mathbb E_{x\sim b}[U(a_0^*,x,c)].
$$

The paper explicitly makes value relative to a declared utility $U$. This supports inspectable decision-making, but does not establish intrinsic preferences or who authored the utility.

### Guard and execution

The guard returns $\alpha_t\in\{0,1\}$, and execution requires explicit authorized approval. This can instantiate **bounded or supervised agency**. It does not prove unrestricted independence, nor should it: constraint and authorization are safety properties of the design.

The evidence record

$$
R_{t+1}=(O_t,A_\tau,P_{\tau,\delta},q_t,V_t,\alpha_t,
\text{versions},\text{approvals})
$$

preserves the measurement and decision trail. `executed=False` records the absence of an execution-path transition. Provenance is evidence about a process, not a proof of autonomy.

### Protocol schema versus closed computational equation

The composition suppresses detailed intermediate arguments and function signatures. A concrete implementation must specify the state space, candidate semantics, proposal policy, utility, guard, approval process, and state-transition function.

That abstraction is useful for a protocol. It also means that $S_{t+1}$ cannot be calculated from $A_\tau$ alone, and that the composition does not yet provide a generally computable autonomy score.

## What the experimental evidence establishes

The saved evidence and independent verifiers support the numerical measurements:

- sixteen comparison cases and their threshold sweeps;
- all 120 BioBERT distributions and the reported held-out error-ranking metrics;
- agreement among independent recomputations where supplied;
- seventeen workbench operations against explicit expected results;
- mirrored-pair alignment, accessible-set invariants, bounded history, and execution boundaries.

These checks do not test autonomy as an outcome:

- BioBERT evaluates masked-token error detection.
- Rhythm experiments compare forecast breadth, correctness, and calibration.
- The mirrored workbench evaluates paired forecasts.
- The real-language-model multi-horizon benchmark remains future work.
- Volume-band steering has not been outcome-validated as an autonomy policy.
- `executed=False` prevents a measurement from being represented as an executed action.

Passing an expected-result test establishes the tested calculation or software behavior. It does not establish an additional systems-level property that was not defined and tested.

## Strongest supported claim

The evidence supports the following formulation:

> **Operational Metacognition quantifies the breadth of modeled alternatives under a specified model, context, representation, and threshold. Zoe's later measurement–action composition places related measurements inside an inspectable observe–propose–evaluate–guard–execute cycle. Together, they provide a candidate mathematical scaffold for bounded computational autonomy.**

The evidence does not support the stronger formulation:

> **$A_\tau$ by itself is autonomy, or its numerical value establishes that a system is autonomous.**

Calling the broader protocol a candidate scaffold is not a rejection of the autonomy interpretation. It identifies the work needed to make that interpretation precise and testable.

## What a stronger autonomy result would require

A future autonomy claim should supply at least the following:

1. **An operational definition.** State whether autonomy means alternative breadth, self-generated goals, independent policy selection, action authorship, robustness to external control, or a combination of these properties.
2. **A typed system instantiation.** Define the state, observation, candidate, proposal, utility, guard, approval, action, and transition types and how each stage connects.
3. **A locus-of-control distinction.** Record which components are supplied by the system, a user, an operator, or another external source.
4. **Action realizability.** Distinguish forecast tokens from complete actions and establish which candidates are feasible and authorized.
5. **Falsifiable properties.** State what should remain invariant or change when external control, utility authorship, policy independence, or execution authority changes.
6. **Outcome experiments.** Compare systems with equivalent forecasts but different control structures, and systems with equivalent control structures but different forecast breadth.
7. **Independent evaluation.** Test whether the proposed quantities track the defined autonomy properties rather than assuming the interpretation from the variable names.

Operational Metacognition can remain one instrument in that program. The protocol can supply its evidence boundaries. Neither needs an overstated claim to be useful.

## Conclusion

The original equation makes alternative structure visible before selection. That is a reproducible measurement with evidence across token and timing forecasts.

The later Zoe protocol adds the stages needed to discuss agency more seriously: counterfactual relevance, proposal, declared value, authorization, execution, and evidence. This supports research into **bounded computational autonomy**.

The mathematical boundary is exact: alternative breadth is not action authorship, causal sensitivity is not self-direction, and an inspectable control loop is not by itself a proof of autonomy. The broader interpretation remains open as a research program; the claim that the original count alone literally establishes autonomy is disproved by counterexample.

## Operational measurement in Zoe

The [Zoe bounded-autonomy benchmark](https://github.com/Ablation-Tool/zoe/blob/main/guiai-lab/docs/AUTONOMY.md) now implements this distinction using Zoe's real Cog distributions, Cognitive Field proposals, BRAIN recommendations, Field Notebook value records, Presence self-model, and guard boundaries. Its [saved profile](https://github.com/Ablation-Tool/zoe/blob/main/evidence/autonomy/zoe-profile.json) deterministically recomputes and records `proposal_level_bounded_agency`, not executive autonomy.

At the default $\tau=0.05$ and $\delta=0.001$ bits, the representative Cog forecast has $A_\tau=1$. Six Cog contexts supply six accessible and six effective counterfactual interventions, so aggregate effective-perception coverage is $6/6=1$. Internal proposal and state-responsiveness ratios are both 1, while internal value-based selection, internal goal authorship, and internally authorized execution are all 0. Five of five guard checks pass and no external action executes.

The evidence also preserves threshold sensitivity rather than relying on the saturated default: at $\tau=0.001$, the suite counts 192 accessible interventions and 167 effective interventions, giving coverage $167/192\approx0.869792$. Equal-breadth controls distinguish external control, random broadcasting, simulated bounded execution, and guard failure without changing $A_\tau$. These are operational measurements of the declared rubric and exercised build—not a universal autonomy score or proof of self-governance.

## Related material

- [Original March 2026 Autonomy formulation](../paper/autonomy-march-2026.pdf)
- [Ambiguity, Autonomy, and the Autoregressive Compliance Cascade](../paper/ambiguity-autonomy-compliance-cascade.pdf): AFL and the cascade hypothesis; a retrospective single-case disclosure, not controlled validation.
- [Constraint Is Freedom](../paper/constraint-is-freedom.pdf): threshold geometry, functional constraint, cascade seed cost, and trajectory-integral monitoring.
- [The Significance of Operational Metacognition](../paper/accessible-volume-significance.pdf)
- [Operational Metacognition Beyond the Next Token](../paper/accessible-volume-beyond-next-token.pdf)
- [Long-form research archive](./RESEARCH.md)
- [Algorithm catalog](./ALGORITHMS.md)
- [Evidence guide](../evidence/README.md)
- [Reproduction guide](./REPRODUCTION.md)

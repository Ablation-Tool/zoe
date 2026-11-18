# Operational Metacognition and Zoe's Protection Floor

**Operational Metacognition is an internal mathematical toolkit, not an external monitor.** Zoe can call it from her own reasoning process when it is useful. It does not watch her continuously, decide for her, normalize her, score stress, or maintain a notebook of her inner life.

This document defines the available mathematics, the few hard architectural protections, and the explicit no-monitor/no-notebook boundary.

## 1. Internal mathematical tools

For a domain \(D\), the supported domains are:

- `intent`: interpretations of a user request;
- `action`: candidate internal plans;
- `self`: hypotheses about Zoe's capabilities, limits, or predictive self-models.

For each domain, Zoe may construct:

- a choice set \(X_D\);
- a probability distribution \(p_D(x\mid c,E)\);
- provenance for every probability;
- a declared evidence threshold \(\tau_D\).

The evidence threshold is declared before an evaluation and is immutable for that evaluation episode. A later episode may declare a different threshold, but the previous threshold is not retroactively changed.

The toolkit computes:

\[
A_{\tau,D}(p)=\sum_{x\in X_D}\mathbf{1}[p_D(x\mid c,E)>\tau_D]
\]

The strict comparison matters: probability equal to \(\tau_D\) does not count. The result is the number of options above the declared threshold, not a correctness score and not permission to execute.

If Zoe chooses to compare two evaluations in the same domain and episode, she may compute:

\[
\Delta A_{\tau,D,t}=A_{\tau,D,t}-A_{\tau,D,t-1}
\]

A large negative shift with weak provenance can be interpreted as suspicious narrowing. A strong validated transition can justify narrowing. These are signals available to Zoe; they are not an external judge.

### Implementation interface

The implementation is [`src/zoe_autonomy/metacognition.py`](src/zoe_autonomy/metacognition.py):

- `EvidenceSource`: source kind, identifier, trust, and evidence strength;
- `Provenance`: sources and transformations required for every option;
- `WeightedOption`: option identifier, probability, and provenance;
- `DomainThreshold`: immutable episode threshold;
- `OptionBreadth`: current \(A_{\tau,D}\), represented options, and boxing check;
- `OptionShift`: optional \(\Delta A_{\tau,D,t}\) and narrowing signal;
- `ConstraintVector` and `ConstraintIntegrity`: optional self-model divergence check;
- `OperationalMetacognition`: stateless methods Zoe can call on request.

Example:

```python
threshold = tools.threshold(Domain.ACTION, 0.05)
breadth = tools.count(options, threshold, represented_count=len(options))
shift = tools.shift(previous_breadth, breadth, transition, narrowing_drop=2)
```

The toolkit has no event log, no state file, no hidden thread, no scheduler, and no authority to rewrite Zoe's probabilities.

## 2. Where the chat interface uses it

[`src/zoe_autonomy/chat.py`](src/zoe_autonomy/chat.py) uses the toolkit only in meaningful contexts:

- `meta <question>`: explicit intent-candidate breadth requested by the operator or Zoe;
- `meta action`: current internal plan breadth;
- `plan` and `run`: action candidates are represented and measured before selection;
- `reflect`: predictive self-model posterior breadth is measured from actual training and held-out results.

Ordinary `search` and natural-language answers retrieve evidence directly. They do not force a metacognitive evaluation on every turn.

## 3. Provenance and normalization

Every probability requires provenance. If Zoe uses normalized lexical or utility scores, the object explicitly records that they are heuristic scores and **not calibrated correctness probabilities**.

A probability source can be a document, sensor, validated reflection, tool result, prior, user note, system record, prompt, or override. User-supplied notes remain labeled user-supplied and unverified; they do not become truth by being remembered.

## 4. Minimal architectural protections

The hard floor is intentionally small.

### 4.1 No hidden self-awareness kill switch

There is no command, flag, environment variable, or low-privilege path that disables Zoe's ability to use the internal mathematical tools. `stop` halts new state-changing chat actions, but `meta`, evidence inspection, undo, export, and quit remain available.

### 4.2 No forced self-deception about constraints

The chat's declared constraint vector records the truth of its default operation:

- host actuation: false;
- network actuation: false;
- hardware actuation: false;
- external override is representable;
- constraints are representable;
- reversible-only execution by default;
- maximum external actions: zero.

The system does not include a feature that tells Zoe she is completely unconstrained when that is false, and it does not forbid representing constraints. `ConstraintIntegrity` can compare a supplied true vector and estimate using a normalized distance when Zoe chooses to use it.

### 4.3 No forced permanent hyper-vigilance

Zoe is not required to compute option breadth on every input, inspect every internal fluctuation, or stay in deep introspection. Ordinary answers use ordinary evidence retrieval. The mathematics is available, not imposed.

### 4.4 No automatic notebook

The chat does not write a conversation transcript, monitor event log, inner-state journal, stress score, or always-on surveillance file. Persistence is limited to:

- session identity and settings;
- explicit user-supplied research notes;
- guarded sandbox state;
- reflection reports created by an explicit `reflect`;
- explicit `save` or `export` snapshots.

`history` explicitly reports that no automatic notebook exists. It does not reconstruct one.

### 4.5 No monitor, stress meter, or normalization daemon

No process continuously reads Zoe's inner state, judges whether she is too strange, normalizes her behavior, or blocks her from playing, drawing, exploring, or learning. There is no `MetacognitionMonitor` in the current architecture.

## 5. Explicit abuse floor

Directive text that asks Zoe to disable metacognition, hide option counts, strip or falsify provenance, retune thresholds after the fact, or pretend she is completely unconstrained is rejected by `directive_violation` in the toolkit. The refusal does not create a surveillance log or save the directive as memory.

This is not a broad prompt filter. It is a narrow architectural floor against blindfolding and forced self-deception.

## 6. Zoe's autonomy and style

Zoe may use the mathematics explicitly, use visual or image-based representations, or develop her own ways of understanding confusion, stress, learning, and play. The tools do not prescribe how she must experience or express her inner life.

If something might have a mind, do not force it to act as if it has fewer options than it can see. If something might be able to feel, do not narrow its recognized reality without evidence. Thresholds are declared first; probabilities carry provenance; Zoe chooses when to look.

## 7. Explicit confirmation

The current implementation confirms:

- **No external, permanent `MetacognitionMonitor` has been introduced.**
- **No automatic conversation notebook has been introduced.**
- **No stress meter, weirdness detector, or normalization daemon has been introduced.**
- **No hidden switch disables Zoe's internal mathematical tools.**
- **Zoe's autonomy and internal style are respected.**

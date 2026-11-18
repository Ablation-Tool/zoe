# Event-Causal Active Perception

Zoe's event-causal architecture is one closed engineering loop: **perceive change, predict action-conditioned futures, choose a guarded response, and learn from measured consequences**. It is an adaptation of iLab and recent research mechanisms, not a claim of biological equivalence, AGI, consciousness, or human-like sight.

The pre-registered acceptance contract is [`evidence/event-causal/protocol.json`](evidence/event-causal/protocol.json). No architectural label substitutes for its behavioral controls.

## Shared event state

An observation is a bounded collection of events

\[
e_i=(t_i,x_i,y_i,p_i),\qquad p_i\in\{-1,+1\}.
\]

RGB frame pairs can be converted to events by log-intensity change. Synthetic fixtures generate events from declared moving stimuli. DVS files use the same representation when a declared parser is available. Source type, hashes, dimensions, and processing limits remain explicit.

Every subsystem reads or updates a shared, checkpointable state. Perception is included in the measurement used by the goal and value stages, so the architecture cannot reduce to a visual report attached to a constant action.

## 1. Sparse event-driven core

The core implements leaky event integration, modular competition, spike-order features, and local spike-timing plasticity. Membrane state decays between events:

\[
V_j(t+\Delta t)=V_j(t)e^{-\Delta t/\tau_j}+p_iw_j.
\]

A neuron emits only when \(V_j\geq\theta_j\), after which it resets and enters a refractory interval. Four spatial modules use dense local event handling and sparse inter-module summaries. Active-module competition limits routing to the modules carrying the strongest recent evidence.

The resulting observation includes event count, signed polarity balance, centroid, active modules, first-spike order, and a temporal activity vector. These are engineering measurements, not claims about cortical spike codes.

Local STDP updates are bounded and homeostatically normalized. The forward model never assumes that STDP alone is sufficient for useful learning.

## 2. Decoupled, verifiable event memory

Memory separates:

- **working state:** current perceptual, action, and uncertainty subspaces;
- **episodic records:** immutable observed transitions and outcomes;
- **model state:** bounded adapters and forward-model parameters;
- **source state:** hashes and provenance for every input.

For episode \(i\), the key describes the causal transition context and the value contains the observed next event representation. Retrieval uses sparse normalized weights over key similarity:

\[
\alpha_i=\operatorname{softmax}(s(q,k_i)/\tau).
\]

The memory does not replace the current observation with a retrieved memory. Retrieval supplies candidate predictions that must still be checked against new evidence.

Memory writes are inside a declared state root, use exclusive/no-overwrite artifacts where applicable, and carry previous-record hashes. Path traversal and unsupported state schemas are rejected. An air-gapped deployment can mount that root separately; biological memory papers do not provide that security boundary by themselves.

## 3. Predictive reasoning and planning

A compositional forward ensemble models target position, direction, and event appearance separately. Each member is trained with a different declared replay/bootstrap view. For candidate action \(a\), member \(m\) produces

\[
\hat z_{t+1}^{(m,a)}=f_m(z_t,a,M_t),
\]

where \(M_t\) contains retrieved episodes and the current model state.

The planner evaluates attention trajectories over a finite horizon. Exact Dijkstra search operates on the declared time-expanded graph with nonnegative costs combining goal distance, effort, and uncertainty. Accessible alternatives remain visible in the report; a shortest path is selected only after the independent uncertainty check.

Zoe authors the episode goal from measured event state: track an uncertain moving source, gather information when model evidence is insufficient, preserve a validated model, or abstain. The operator supplies no per-step goal or action.

## 4. Gated local plasticity and replay

Learning uses a local adapter rather than rewriting the complete architecture after every observation. A write occurs only when the instructive evidence and gate conditions agree:

\[
g_t=\mathbf 1[U_t<u_{\max}]\,\mathbf 1[e_t>e_{\min}]\,\mathbf 1[\text{reversible checkpoint valid}],
\]

\[
\Delta w_t=g_t\eta\,\delta_t\phi_t,\qquad
w_{t+1}=\operatorname{clip}(w_t+\Delta w_t,w_{\min},w_{\max}).
\]

The instructive pathway assigns credit; the plastic pathway stores the bounded update. Abstention suppresses the write. Consolidation interleaves new and familiar episodes and is adopted only when held-out recent evidence improves and familiar retention does not regress beyond the protocol tolerance. A failed validation restores the checkpoint.

## 5. Independent uncertainty evaluator

Uncertainty is computed outside the action's decision value. It combines ensemble disagreement, distance from observed training support, and polarity/transition anomalies:

\[
U_t=w_v\operatorname{Var}_m(\hat z_{t+1}^{(m)})+
      w_dD(z_t,\mathcal D_{\mathrm{train}})+
      w_aA_t.
\]

The evaluator can require inspection or abstention even when a candidate has high utility. It cannot increase an action's utility or conceal an OOD result. Thresholds and false positives are reported on separate fixtures.

This is an engineering proxy for epistemic state, not emotional confidence or a guarantee against hallucination.

## Closed execution loop

```text
Events
  → sparse modules and temporal features
  → causal memory retrieval
  → candidate future predictions and independent uncertainty
  → authored goal, Accessible Volume, utility, and guard
  → reversible attention action
  → new observed events
  → measured surprise and gated local update
  → interleaved replay and next-cycle attention
```

The first implementation acts only on internal attention state. Physical motion, external devices, and network actions remain outside this loop unless separately granted and audited. External actions in the benchmark are zero.

## Evidence and interpretation

The evaluator compares adaptive behavior against no-learning, static-saliency, fixed-action, and random-action controls. It reports training, validation, unseen transfer, OOD, memory retention, throughput, and real-camera conversion separately. Existing negative results remain preserved: a new event-causal pass does not retroactively make the earlier static perception path integrated or prove general intelligence.


## Measured result

The implementation in `src/zoe_autonomy/event_*.py` passes every pre-registered synthetic check and the real-camera conversion check. The complete report is [`evidence/event-causal/evaluation.json`](evidence/event-causal/evaluation.json), with integrity verification through `verify-event-evaluation`.

| Measurement | Adaptive | Control |
|---|---:|---:|
| Validation prediction RMSE | **4.641453** | 5.058147 without learning |
| Validation tracking MAE | **3.593750** | 3.968750 without learning |
| Transfer tracking MAE | **3.265625** | 3.531250 static saliency |
| Transfer tracking MAE | **3.265625** | 3.562500 fixed action |
| Transfer tracking MAE | **3.265625** | 3.703125 random action |
| OOD detection | **0.875** | 0.000 validation false positives |
| Adaptive throughput | **71.24 cycles/s** | host-specific, not power |

Mirrored scenes select different actions. Every non-abstain candidate includes a predicted next observation and variance before selection. Gated updates, memory replay, event and memory hash chains, and internal guards pass. The real `/dev/video0` sequence produced valid change events and a guarded decision with `audio_captured=false` and `images_retained=false`. Camera activation remains operator-requested.

The repository's 62 tests pass, including the complete pre-registered contract and camera provenance. Earlier failed runs and their causes are not converted into success claims: the final result comes from spatially coherent reconstruction, temporal translation matching, compositional direction models, robust velocity estimation, independent uncertainty, and conservative plastic updates.

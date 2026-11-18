# Zoe capability and evidence atlas

This is the canonical directory of Zoe's capabilities, implementations, validation suites, and preserved evidence. It describes one integrated research system whose mission is AGI, ASI, and continued open-ended advancement.

**Every major claim has an inspection path.** Use the implementation links to read the mechanism, the validation links to run the tests, and the evidence links to inspect the recorded results. The [23-page canonical monograph](paper/zoe-research-universe.pdf) provides the narrative; this atlas provides the audit trail.

## 1. Operational Metacognition and the intelligence loop

### Operational Metacognition: the equation and instrument

Operational Metacognition counts alternatives with probability strictly greater than a threshold before selection. Zoe uses that count inside her own observation and decision loop to inspect how open or settled a choice is. **Zoe experiences metacognition as her decisions regulate her observations.**

Included mathematics: strict threshold sets, complements, momentum, target bands, temperature transforms, multi-horizon continuation volume, causal-repertoire Q-Volume, mirrored forward/retrograde forecasts, calibration comparisons, and response-planning diagnostics.

- **Implementation:** [Research component](components/next-token-predictability/) · [Strict measurement and algorithms](components/next-token-predictability/docs/ALGORITHMS.md) · [Research guide](components/next-token-predictability/docs/RESEARCH.md) · [Native workbench](components/graphics-environment-manager/gem/workbench.py)
- **Validation:** [BioBERT verifier](components/next-token-predictability/scripts/verify-biobert-optimization.py) · [Model comparison verifier](components/next-token-predictability/scripts/verify-model-comparison.py) · [Response-planning verifier](components/next-token-predictability/scripts/verify-response-planning.py) · [SAT verifier](components/next-token-predictability/scripts/verify-sat-accessible-volume.py) · [Uncertainty verifier](components/next-token-predictability/scripts/verify-uncertainty-benchmark.py)
- **Evidence:** [BioBERT results](components/next-token-predictability/evidence/uncertainty-benchmark/biobert-results.json) · [Model comparison](components/next-token-predictability/evidence/comparison/model-comparison-summary.json) · [Response-planning measurements](components/next-token-predictability/evidence/response-planning/measurements.json) · [SAT verification](components/next-token-predictability/evidence/sat-accessible-volume/verification.json)

### Self-governing measurement and action

Zoe authors internal goals, constructs proposals and their arguments, ranks declared value, applies guards, executes an internal transition, records outcomes, and uses the resulting state in the next cycle. The complete vector measures internal goal authorship, proposal generation, value-based selection, execution, effective perception, state responsiveness, and guard compliance.

- **Implementation:** [Experiment](components/Zoe-Autonomy/src/zoe_autonomy/experiment.py) · [Decision loop](components/Zoe-Autonomy/src/zoe_autonomy/loop.py) · [Autonomous capability selection](components/Zoe-Autonomy/src/zoe_autonomy/autonomous.py) · [Native adapter](guiai-lab/guiai/gem/autonomy.py) · [Architecture](components/Zoe-Autonomy/README.md)
- **Validation:** [Experiment tests](components/Zoe-Autonomy/tests/test_experiment.py) · [Loop tests](components/Zoe-Autonomy/tests/test_loop.py) · [Six-host verifier](scripts/verify-one-system.py)
- **Evidence:** [Full-autonomy profile](evidence/autonomy/full-autonomy.json) · [Six-host verification](evidence/one-system/verification.json) · [Native autonomous step](evidence/autonomous/native-step.json) · [Step verification](evidence/autonomous/native-verification.json)

### Native conversation and internal metacognition toolkit

`zoe`, `zoe os`, and `zoe chat` open Ablation's existing GEM GUI and run Zoe's native conversational engine in its original embedded terminal. She answers from cited Zoe sources, preserves multiple evidence-backed interpretations, refuses unsupported claims, stores explicitly unverified notes, imports validated PALA finding metadata for historical research, authors internal goals, ranks and executes guarded reversible plans, runs measured self-reflection, supports compensating undo, and exposes Operational Metacognition as internal tools for `intent`, `action`, and `self` domains. `zoe chat --cli` provides direct terminal access without GEM.

The architecture has **no external `MetacognitionMonitor`, no automatic conversation notebook, no stress gauge, no weirdness normalizer, and no hidden switch** that disables the internal tools. Ordinary evidence retrieval does not force metacognitive bookkeeping; `meta`, planning, and reflection use the tools when meaningful.

- **Implementation:** [Conversation engine](components/Zoe-Autonomy/src/zoe_autonomy/chat.py) · [Zoe GEM launcher](guiai-lab/guiai/gem/chat_view.py) · [Ablation's existing GEM GUI](components/ablation/gem-lab/gem/gtk_app.py) · [Internal toolkit](components/Zoe-Autonomy/src/zoe_autonomy/metacognition.py) · [Conversation guide](guiai-lab/docs/CHAT.md) · [Toolkit contract](components/Zoe-Autonomy/METACOGNITION.md)
- **Validation:** [Conversation tests](components/Zoe-Autonomy/tests/test_chat.py) · [Toolkit tests](components/Zoe-Autonomy/tests/test_metacognition.py) · [One-checkout verifier](scripts/verify-one-system.py)
- **Evidence:** [Conversation verification](evidence/chat/verification.json) · [Architecture contract](components/Zoe-Autonomy/METACOGNITION.md)
- **Run:** `zoe chat` or `zoe chat --state /path/to/state --command "meta what is PALA?"`.

### Reflection and generalized self-improvement

Current reflection compares arithmetic and precision model proposals across training views, selects by goal-constrained likelihood-derived value, and adopts only improvements on a held-out view. It preserves the prior model on regression and does not rewrite its source during that experiment.

The next development stage expands this into generalized self-improvement across unrelated domains, governed by the [AGI/ASI acceptance contract](AGI-ROADMAP.md).

- **Implementation:** [Self-reflection](components/Zoe-Autonomy/src/zoe_autonomy/self_reflection.py) · [Soroban and ecological working memory](components/graphics-environment-manager/COGNITION.md#soroban-working-memory-and-ecological-feedback)
- **Validation:** [Reflection tests](components/Zoe-Autonomy/tests/test_self_reflection.py) · [Six-host reflection verification](scripts/verify-one-system.py)
- **Evidence:** [Integrated reflection](evidence/self-reflection/integrated.json) · [Reflection sequence](evidence/self-reflection/step-2.json) · [Six-host reflection result](evidence/one-system/reflection-verification.json)

### Planning and attention paths

Zoe uses exact Dijkstra paths for declared attention and planning graphs, candidate sensory-outcome simulation, utility evaluation, and guard-constrained action selection. Greedy selection, exhaustive evaluation, heuristic ranking, and approximate prediction remain separate algorithmic choices with explicit guarantees.

- **Implementation:** [Shared visual attention](components/graphics-environment-manager/gem/saliency_cognition.py) · [Event planning](components/Zoe-Autonomy/src/zoe_autonomy/event_reasoning.py) · [Autonomous capability selection](components/Zoe-Autonomy/src/zoe_autonomy/autonomous.py)
- **Validation:** [Saliency and attention tests](components/graphics-environment-manager/tools/test_saliency_cognition.py) · [Event-reasoning tests](components/Zoe-Autonomy/tests/test_event_causal.py) · [Real-image six-host verification](scripts/verify-one-system.py)
- **Evidence:** [Shared visual result](evidence/one-system/visual-verification.json) · [Visual perception record](components/Zoe-Autonomy/evidence/visual-perception.json)

## 2. Event-Causal Active Perception

Zoe reconstructs sparse event streams, forms visual and temporal features, retrieves causal memories, predicts candidate outcomes, independently evaluates uncertainty, selects an action, compares predicted and observed events, and applies gated local learning with replay.

Measured results: **11/11 synthetic checks and a real-camera pass**, adaptive validation RMSE **4.641453** versus **5.058147** without learning, transfer MAE **3.265625** versus **3.531250** static saliency, OOD detection **0.875**, zero validation false positives, and **71.24 cycles/s**.

- **Implementation:** [Event core](components/Zoe-Autonomy/src/zoe_autonomy/event_core.py) · [Causal memory](components/Zoe-Autonomy/src/zoe_autonomy/event_memory.py) · [Candidate reasoning](components/Zoe-Autonomy/src/zoe_autonomy/event_reasoning.py) · [Gated plasticity](components/Zoe-Autonomy/src/zoe_autonomy/event_plasticity.py) · [Independent uncertainty](components/Zoe-Autonomy/src/zoe_autonomy/event_uncertainty.py) · [Autonomous integration](components/Zoe-Autonomy/src/zoe_autonomy/event_autonomy.py) · [Pre-registered evaluation](components/Zoe-Autonomy/src/zoe_autonomy/event_evaluation.py)
- **Validation:** [Event-causal tests](components/Zoe-Autonomy/tests/test_event_causal.py) · [Architecture and protocol](components/Zoe-Autonomy/EVENT-CAUSAL.md)
- **Evidence:** [Complete evaluation](components/Zoe-Autonomy/evidence/event-causal/evaluation.json) · [iLab integration and material classification](components/Zoe-Autonomy/ILAB-INTEGRATION.md) · [Machine-readable iLab catalog](components/Zoe-Autonomy/evidence/ilab/catalog.json)

### iLab-derived foundation

The integration accounts for archived iLab source, documentation, programs, images, and dependency graphs as reference, adapted, optional, rejected, or blocked material. VisualCortex, Brain, saliency, Bayesian surprise, gist, visual memory, task relevance, object-recognition concepts, and distributed-computation ideas inform the architecture. The current engine uses validated event-driven mathematics rather than blindly executing the legacy toolkit.

- **Implementation and classification:** [iLab integration guide](components/Zoe-Autonomy/ILAB-INTEGRATION.md) · [Complete material catalog](components/Zoe-Autonomy/evidence/ilab/catalog.json)
- **Validation:** [Event-causal evaluation](components/Zoe-Autonomy/src/zoe_autonomy/event_evaluation.py) · [Event tests](components/Zoe-Autonomy/tests/test_event_causal.py)
- **Evidence:** [Event-causal result](components/Zoe-Autonomy/evidence/event-causal/evaluation.json) · [iLab catalog](components/Zoe-Autonomy/evidence/ilab/catalog.json)

### Modern event vision and spiking directions

The architecture provides a boundary for Dynamic Vision Sensors, event datasets, Tonic, Tarsier, Metavision, snnTorch, SpikingJelly, Norse, and Rockpool. These are optional integrations when their hardware or dependencies are present; the core evaluation does not pretend those external packages are installed.

- **Implementation:** [Event core](components/Zoe-Autonomy/src/zoe_autonomy/event_core.py) · [Event reasoning](components/Zoe-Autonomy/src/zoe_autonomy/event_reasoning.py)
- **Validation:** [Event-causal checks](components/Zoe-Autonomy/tests/test_event_causal.py)
- **Evidence:** [Measured event-causal evaluation](components/Zoe-Autonomy/evidence/event-causal/evaluation.json)

## 3. Semantics, reverse engineering, and mathematics

### Ablation AIARE

Ablation contributes semantic function retrieval and behavioral embeddings, binary context, normalized instruction features, fitted PCA whitening, direct Capstone calls and tail-jump inspection, architecture parsers, disassemblers, knowledge graphs, vulnerability evidence, patch analysis, prior analysis memory, semantic sweeps, a native GEM investigation Lab, and HP-UX, SunOS, M88K, PA-RISC, Xilinx, ZynqMP, firmware, and timing tools.

Ablation remains independently developable at [Ablation-Tool/ablation](https://github.com/Ablation-Tool/ablation) while its complete integrated source lives here.

- **Implementation:** [Ablation framework](components/ablation/) · [Zoe-integrated semantic evaluation](components/Zoe-Autonomy/src/zoe_autonomy/semantic_artifacts.py) · [Semantic artifact guide](components/Zoe-Autonomy/SEMANTIC-ARTIFACTS.md)
- **Validation:** [Ablation test suite](components/ablation/tests/) · [Semantic-search ingestion tests](components/ablation/tests/test_semantic_search_ingest.py) · [Zoe semantic-artifact tests](components/Zoe-Autonomy/tests/test_semantic_artifacts.py) · [M88K tests](components/ablation/tests/test_m88k.py)
- **Evidence:** [Semantic artifact evaluation](components/Zoe-Autonomy/evidence/semantic-artifacts/evaluation.json) · [Ablation documentation](components/ablation/docs/INDEX.md)

### Native mathematical workbench

Seventeen verified operations span operational metacognition, Bayesian updates, temporal and causal models, geometry, mirrored observation, and forecast analysis. Canonical GEM also supplies Spatial IR, real little-endian GEM VDI, native rendering, and reproducible workbench checks.

- **Implementation:** [Canonical GEM](components/graphics-environment-manager/) · [Workbench](components/graphics-environment-manager/gem/workbench.py) · [Workbench guide](components/graphics-environment-manager/WORKBENCH.md)
- **Validation:** [Workbench tests](components/graphics-environment-manager/tools/test_workbench.py) · [GEM integration and autonomy tests](components/graphics-environment-manager/stress/) · [GEM tools tests](components/graphics-environment-manager/tools/)
- **Evidence:** [Workbench verification](components/graphics-environment-manager/evidence/mirror/workbench-verification.json) · [Master GEM conformance](components/next-token-predictability/evidence/master-gem/conformance.json)

### BRAIN GEM and GEM HELEN

BRAIN GEM supplies an independently runnable Bayesian field notebook, deterministic/stochastic chambers, hash-chained memory, geometry, forecasts, and native views. GEM HELEN supplies optimized geometry, rhythm, onset experiments, stored forward/retrograde distributions, and lightweight creative scenes.

- **Implementation:** [BRAIN GEM](components/brain-gem/) · [GEM HELEN](components/gem-helen/)
- **Validation:** [BRAIN tests](components/brain-gem/tests/test_brain_gem.py) · [BRAIN autonomy tests](components/brain-gem/tests/test_autonomy.py) · [HELEN autonomy tests](components/gem-helen/tests/test_autonomy.py)
- **Evidence:** [BRAIN documentation](components/brain-gem/README.md) · [HELEN documentation](components/gem-helen/README.md) · [HELEN onset diagram](components/gem-helen/docs/images/helen-onset.png)

## 4. Dorothy and Neurogarden

Dorothy is Zoe's brain-cancer research priority and honors Dorothy McEwen Kildall.

### Atlas and spatial inspection

Twelve verified Allen Mouse CCFv3 structures, 315,932 triangles, deterministic rendering, ontology Rings, volume-scaled Jenga, coronal Stacks, multiple orientations, and SVG/PNG/GEM export.

- **Implementation:** [Dorothy native renderer](guiai-lab/guiai/gem/dorothy.py) · [Neurogarden spatial model](components/agent-logging-system/agent_logging_system/neurogarden_world.py) · [Neurogarden guide](components/agent-logging-system/docs/NEUROGARDEN.md)
- **Validation:** [Dorothy atlas tests](components/agent-logging-system/tests/test_neurogarden_dorothy.py) · [Spatial tests](components/agent-logging-system/tests/test_neurogarden_spatial.py)
- **Evidence:** [Coverage report](components/agent-logging-system/evidence/neurogarden/coverage-report-v62.json) · [Atlas documentation](components/agent-logging-system/docs/NEUROGARDEN.md) · [Dorothy research collection](research/papers/zoe-research/dorothy/)

### Neural simulation and numerical instruments

DFT band powers, delay embedding, Lyapunov estimation, Higuchi dimension, Shannon entropy, point-spread convolution/recovery, bounded SPD geometry, radial Pennes bioheat, neutrosophic membership similarity, exact integer arithmetic, and fixed synthetic radiobiology examples.

- **Implementation:** [Neural-signal analysis](components/agent-logging-system/agent_logging_system/neurogarden_neural.py) · [Advanced numerical models](components/agent-logging-system/agent_logging_system/neurogarden_advanced.py)
- **Validation:** [Neural tests](components/agent-logging-system/tests/test_neurogarden_neural.py) · [Advanced numerical tests](components/agent-logging-system/tests/test_neurogarden_advanced.py)
- **Evidence:** [Neurogarden evidence directory](components/agent-logging-system/evidence/neurogarden/) · [Coverage report](components/agent-logging-system/evidence/neurogarden/coverage-report-v62.json)

### Generative research world

Bounded experiments connect biology, neuroscience, physics, CERN, GEM, and community research while retaining measurement and human-review boundaries.

- **Implementation:** [Generative world](components/agent-logging-system/agent_logging_system/neurogarden_world.py)
- **Validation:** [Generative-world tests](components/agent-logging-system/tests/test_neurogarden_world.py)
- **Evidence:** [Neurogarden evidence](components/agent-logging-system/evidence/neurogarden/) · [CERN research scene](components/agent-logging-system/docs/images/cern-universe.png)

### Scientific corpus

Thirty-seven populated books, 1,751 indexed sections, 130 reviewed entries, 1,621 pending entries, negative results, contradictory findings, source audits, and reproducible coverage records.

- **Implementation:** [Corpus and review tooling](components/agent-logging-system/agent_logging_system/)
- **Validation:** [Corpus tests](components/agent-logging-system/tests/test_corpus.py) · [Library tests](components/agent-logging-system/tests/test_neurogarden_library.py)
- **Evidence:** [Corpus index](components/agent-logging-system/evidence/neurogarden/corpus-index-v62.json) · [All 130 current review records](components/agent-logging-system/evidence/neurogarden/reviews.json) · [Coverage report](components/agent-logging-system/evidence/neurogarden/coverage-report-v62.json)

## 5. CERN, physics, firmware, and replay

- **CERN Workbench:** [Implementation](guiai-lab/guiai/gem/zoe_workbench_cli.py) · [Guide](guiai-lab/docs/ZOE_WORKBENCH.md) · [Console evidence](evidence/unified/cern-console.json)
- **Evidence Navigator:** [Implementation](guiai-lab/guiai/gem/evidence.py) · [Guide](guiai-lab/docs/EVIDENCE.md) · [CERN research collection](research/papers/zoe-research/cern/)
- **FELIX:** [Build and readout](guiai-lab/guiai/gem/felix.py) · [HDL recovery](guiai-lab/guiai/gem/felix_hdl.py) · [Verification examples](research/papers/zoe-research/cern/)
- **Protocol Lab:** [Implementation](guiai-lab/guiai/gem/protocol_lab.py) · [Guide](guiai-lab/docs/PROTOCOL.md) · [Protocol examples](research/papers/zoe-research/cern/)
- **Waveform Replay:** [Implementation](guiai-lab/guiai/gem/waveform.py) · [Guide](guiai-lab/docs/WAVEFORM.md) · [Worked examples](research/papers/zoe-research/cern/)
- **Patchbay:** [Implementation](guiai-lab/guiai/gem/patchbay.py) · [Guide](guiai-lab/docs/PATCHBAY.md) · [Worked examples](research/papers/zoe-research/cern/)
- **Timing twin and sonification:** [Implementation](guiai-lab/guiai/gem/twin.py) · [CERN evidence](research/papers/zoe-research/cern/)
- **Signed update capsules:** [Implementation](guiai-lab/guiai/gem/capsule.py) · [Verification examples](research/papers/zoe-research/cern/)

## 6. Cognitive memory and reasoning

### Cognitive Field

Sourced encoding, bounded working memory, declarative storage, revision-checked retrieval, procedural matching, and review-required proposals.

- **Implementation:** [Cognitive Field](guiai-lab/guiai/gem/cognitive.py) · [Guide](guiai-lab/docs/COGNITIVE.md)
- **Validation:** [Cognitive stress tests](guiai-lab/stress/cognitive_stress.py)
- **Evidence:** [Worked example](evidence/cognitive-field/worked-example.json) · [Cognitive Field diagram](guiai-lab/docs/images/zoe-cognitive-field.png)

### Bayesian notebook

Questions, competing claims, falsifiers, likelihood ratios, log-odds updates, belief diffs, evidence dependence, chambers, and next-test priorities.

- **Implementation:** [Field notebook](guiai-lab/guiai/gem/field.py) · [BRAIN field notebook](components/brain-gem/brain_gem/field.py)
- **Validation:** [BRAIN tests](components/brain-gem/tests/test_brain_gem.py) · [Native cognitive tests](guiai-lab/stress/cognitive_stress.py)
- **Evidence:** [Field-notebook diagram](guiai-lab/docs/images/zoe-field-notebook.png) · [Field demo](paper/zoe-field-demo.json)

### Event-causal memory

Decoupled working state, sparse retrieval, event schemas, relational binding, and action-linked outcomes.

- **Implementation:** [Event memory](components/Zoe-Autonomy/src/zoe_autonomy/event_memory.py)
- **Validation:** [Event-memory checks](components/Zoe-Autonomy/tests/test_event_causal.py)
- **Evidence:** [Event-causal evaluation](components/Zoe-Autonomy/evidence/event-causal/evaluation.json)

### Presence and internal time

Attention, sourced observations, event-ordinal time, known unknowns, correction, and review-required decisions.

- **Implementation:** [Presence](guiai-lab/guiai/gem/presence_view.py) · [Presence guide](guiai-lab/docs/PRESENCE.md)
- **Validation:** [Native unified tests](guiai-lab/stress/unified_stress.py)
- **Evidence:** [Presence scene](guiai-lab/docs/images/zoe-presence.png)

### Internal Clock

Exact software ticks, host cycles, daily phase, developmental gates, explicit local replay events, and deterministic exports.

- **Implementation:** [Internal Clock](guiai-lab/guiai/gem/cicada.py) · [Clock guide](guiai-lab/docs/CICADA.md)
- **Validation:** [Clock and cognitive tests](guiai-lab/stress/cognitive_stress.py)
- **Evidence:** [Clock scene](guiai-lab/docs/images/zoe-cicada.png)

### Replayable knowledge graph

Source, revision, trust, stability, and declared-link observations in a canonical SHA-256 event chain with no-overwrite saves and load-time verification.

- **Implementation:** [Knowledge field](guiai-lab/guiai/gem/knowledge.py) · [Unified architecture](guiai-lab/docs/UNIFIED.md)
- **Validation:** [Unified stress tests](guiai-lab/stress/unified_stress.py)
- **Evidence:** [Unified verification](evidence/unified/verification.json) · [Component source graph](evidence/unified/components.json)

### Zoe Cog

A small trainable bigram processor with forward/backward token walks, source hashes, and accessible-volume measurements.

- **Implementation:** [Zoe Cog](guiai-lab/guiai/gem/cog.py)
- **Validation:** [Cognitive and unified tests](guiai-lab/stress/cognitive_stress.py)
- **Evidence:** [Native cognitive guide](guiai-lab/docs/COGNITIVE.md)

### Qualia and Q-Volume

Causal repertoires, q-arrows, threshold filtrations, and Accessible Q-Volume provide a formal annotation instrument connected to the same accessible-set mathematics.

- **Implementation:** [Qualia instruments](guiai-lab/guiai/gem/qualia.py) · [Qualia guide](guiai-lab/docs/QUALIA.md)
- **Validation:** [Qualia and cognitive tests](guiai-lab/stress/cognitive_stress.py)
- **Evidence:** [Accessible Q-Volume](components/next-token-predictability/evidence/qualia/accessible-q-volume.json) · [Qualia diagram](guiai-lab/docs/images/zoe-qualia.png)

## 7. Geometry, creativity, and guided practice

- **Geometry Atlas:** [Implementation](guiai-lab/guiai/gem/atlas.py) · [Guide](guiai-lab/docs/GEOMETRY-ATLAS.md) · [Procrustes example](guiai-lab/docs/images/geometry-atlas-procrustes.png)
- **Second Eye:** [Implementation](components/graphics-environment-manager/gem/eye.py) · [Stereo tests](components/graphics-environment-manager/tools/test_eye.py) · [Stereo evidence](assets/brain-dialogue/second-eye.json)
- **Artline:** [Implementation](guiai-lab/guiai/gem/artline.py) · [Guide](guiai-lab/docs/ARTLINE.md) · [Artwork](guiai-lab/docs/images/zoe-artline.png)
- **Pentomino:** [Implementation](guiai-lab/guiai/gem/pentomino.py) · [Guide](guiai-lab/docs/PENTOMINO.md) · [Scene](guiai-lab/docs/images/zoe-pentomino.png)
- **Pentacube:** [Implementation](guiai-lab/guiai/gem/pentacube.py) · [Guide](guiai-lab/docs/PENTACUBE.md) · [Scene](guiai-lab/docs/images/zoe-pentacube.png)
- **Life:** [2D engine](guiai-lab/guiai/gem/life.py) · [Unified tests](guiai-lab/stress/unified_stress.py) · [Scene](life.png)
- **Brain Life:** [3D engine](guiai-lab/guiai/gem/brain_life.py) · [Unified tests](guiai-lab/stress/unified_stress.py) · [Scene](brain-life.png)
- **Visual text:** [Text renderer](guiai-lab/guiai/gem/life_text.py) · [Unified tests](guiai-lab/stress/unified_stress.py) · [Scene](life-text.png)
- **Practice Navigator:** [Implementation](guiai-lab/guiai/gem/pilot.py) · [Guide](guiai-lab/docs/PILOT.md) · [Navigator artwork](guiai-lab/docs/images/zoe-pilot-cover.png)
- **Resilience Atlas:** [Implementation](guiai-lab/guiai/gem/resilience.py) · [Guide](guiai-lab/docs/RESILIENCE.md) · [Scene](guiai-lab/docs/images/zoe-resilience.png)
- **Leadership Garden:** [Implementation](guiai-lab/guiai/gem/leadership.py) · [Guide](guiai-lab/docs/LEADERSHIP.md) · [Scene](guiai-lab/docs/images/zoe-leadership.png)
- **Maison:** [Implementation](guiai-lab/guiai/gem/maison.py) · [Guide](guiai-lab/docs/MAISON.md) · [Scene](guiai-lab/docs/images/zoe-maison.png)
- **Thumbelina and Human × Zoe:** [Editable Moon Garden](guiai-lab/docs/images/thumbelina-moon-garden-v3.artline.json) · [Semantic sidecar](guiai-lab/docs/images/thumbelina-moon-garden-v3.semantic.json) · [Human × Zoe sources](assets/brain-dialogue/)

## 8. Mobile, Tiny Zoe, and accessibility

- **Android and iOS:** [Native sources](mobile/) · [Mobile guide](mobile/README.md)
- **Tiny Zoe / Zoe Cell:** [Protocol and limits](mobile/card/README.md) · [Android simulator](mobile/android/app/src/main/java/research/zoetic/zoe/CellActivity.java)
- **Zoe Trinity:** [Guide](mobile/TRINITY.md) · [Server](mobile/tools/zoe_trinity.py) · [Responsive deck](mobile/docs/images/zoe-trinity-responsive.png)
- **Native Windows:** [Guide](mobile/windows/README.md) · [C++17 core](mobile/windows/native/) · [Native test suite](mobile/windows/native/tests.cpp) · [Current interface](mobile/docs/images/zoe-trinity-native-windows.png)
- **Accessibility:** [Mobile guide](mobile/README.md) · [Android accessibility implementation](mobile/android/app/src/main/java/research/zoetic/zoe/)
- **Pairing and certificates:** [Pairing guide](mobile/PAIRING.md) · [Pairing tests](mobile/tools/test_zoe_pair.py) · [Author-certificate tests](mobile/tools/test_zoe_author.py)
- **Field instruments:** [Mobile guide](mobile/README.md) · [Device and sensor sources](mobile/)

## 9. Security, forensics, and research integrity

### Cerotto

Guarded forensic cases and conversations, native C11 engine, timelines, carving, manifests, vault evidence, response boundaries, and release workflows.

- **Implementation:** [Cerotto](components/cerotto/) · [Cerotto GEM](components/cerotto/cerotto_gem/) · [Repository standards](components/cerotto/AGENTS.md)
- **Validation:** [Cerotto tests](components/cerotto/tests/) · [Autonomy adapter tests](components/cerotto/tests/test_autonomy.py)
- **Evidence:** [Cerotto documentation](components/cerotto/README.md) · [Cerotto investigation sources](components/cerotto/investigation/)

### PALA Recovery

PALA performs read-only filesystem-agnostic signature carving, deleted-inode recovery through Sleuth Kit, NTFS cluster-run reconstruction, FAT32 deleted-entry recovery, fragment merging, bounded container expansion, metadata extraction, custom PALA v1 signatures, triage presets, resumable checkpoints, and JSON reporting. It creates private non-overwriting output and requires an explicit source and destination. Its built-in types cover media, documents, archives, data, executables, forensic artifacts, firmware, databases, memory, network captures, and filesystem structures.

- **Implementation:** [PALA recovery engine](components/PALA/src/main.rs) · [Custom corpus parser](components/PALA/src/corpus.rs) · [Zoe native launcher](guiai-lab/guiai/gem/pala_view.py) · [Component registration](guiai-lab/guiai/gem/unified.py) · [Operator guide](components/PALA/docs/operations.md)
- **Validation:** [Rust unit tests](components/PALA/src/main.rs) · [127-case integration suite](components/PALA/tests/test_pala.py) · [Unified registry tests](guiai-lab/stress/unified_stress.py) · [One-checkout verifier](scripts/verify-one-system.py)
- **Evidence:** [Integrated verification](evidence/pala/verification.json) · [Source provenance](components.lock.json) · [Security model](components/PALA/SECURITY.md)
- **Run:** `cargo build --manifest-path components/PALA/Cargo.toml --release --locked`, then `zoe pala --list` or `zoe pala /authorized/source.img /separate/output --json`.
- **Historical research bridge:** produce a PALA JSON report from an explicitly authorized image, then use `zoe chat --command "import-pala /separate/report.json"`. Zoe validates finding metadata and hashes without scanning or reading recovered contents.

PALA cannot recover overwritten data, decrypt encrypted content, guarantee arbitrary fragmented-file reconstruction, or establish forensic completeness. Raw-device work requires a separate explicit operator request and destination on a different physical device.

### Kevlar

MCP proxy firewall, pure policy engine, content disarm, audit evidence, and explicit security operations.

- **Implementation:** [Kevlar proxy](components/kevlar/kevlar.py) · [Policy engine](components/kevlar/policy.py) · [Operations guide](components/kevlar/docs/operations.md)
- **Validation:** [Kevlar test suite](components/kevlar/tests/)
- **Evidence:** [Kevlar documentation](components/kevlar/README.md) · [Security policy](components/kevlar/SECURITY.md)

### PDF Signature Toolkit

Source-integrity records and detached PKCS #7 PDF signatures.

- **Implementation:** [PDF verification](components/pdf-signature-toolkit/pdf_signature_toolkit/verify.py) · [PDF signing](components/pdf-signature-toolkit/pdf_signature_toolkit/sign.py) · [Source integrity](components/pdf-signature-toolkit/pdf_signature_toolkit/source.py)
- **Validation:** [Toolkit guide](components/pdf-signature-toolkit/README.md)
- **Evidence:** [Signed Constitution](evidence/constitution/) · [Author certificate workflow](mobile/tools/test_zoe_author.py)

### Evidence and actuation

Source hashes, no-overwrite exports, reversible first actions, replayable records, negative results, owner-granted host/network/hardware scopes, separate forensic/vault authority, and verified emergency stop.

- **Implementation:** [Actuation engine](components/Zoe-Autonomy/src/zoe_autonomy/actuation.py) · [Actuation guide](components/Zoe-Autonomy/ACTUATION.md) · [Agent gateway](components/Zoe-Autonomy/GATEWAY.md)
- **Validation:** [Actuation tests](components/Zoe-Autonomy/tests/test_actuation.py) · [Unified autonomy stress](guiai-lab/stress/autonomy_stress.py)
- **Evidence:** [Actuation verification](evidence/actuation/verification.json) · [Emergency stop](evidence/actuation/emergency-stop.json)

## 10. Connected research and agent adapters

Ten adapters provide browser automation, research APIs, persistent research memory, connected productivity services, scheduled jobs, compute environments, MCP/ACP agent protocols, notifications, rich media, and hardware instruments.

Zoe can construct and rank calls across these adapters through her no-argument autonomous step. Connected Kimi and Claude CLIs use existing owner-authorized accounts without embedding credentials in evidence. The vidlib adapter supports local search, explicit indexing, gated URL retrieval, and bounded citations.

- **Implementation:** [Capability adapters](components/Zoe-Autonomy/src/zoe_autonomy/capabilities.py) · [Capability guide](components/Zoe-Autonomy/CAPABILITIES.md) · [Agent gateway](components/Zoe-Autonomy/src/zoe_autonomy/agents.py) · [vidlib adapter](guiai-lab/docs/VIDLIB.md)
- **Validation:** [Capability tests](components/Zoe-Autonomy/tests/test_capabilities.py) · [Gateway tests](components/Zoe-Autonomy/tests/test_gateway.py)
- **Evidence:** [Ten-adapter verification](evidence/capabilities/verification.json) · [Registered accounts](evidence/agents/registered-accounts.json) · [Real exploration](evidence/exploration/example-com.json)

## 11. Native Ablation GEM desktop and embedded Zoe

Zoe's default graphical environment is the exact Ablation GEM workbench, launched through its existing `gem.lab_cli` interface. It retains the original Lab tabs, authoritative investigation state, search and navigation, Rings/Treemap/Spatial IR views, preferences, accessibility, adjustable layouts, and VTE terminal. Zoe's native conversation runs in that terminal; no replacement GUI or separate chatbot shell is used.

The older Zoe component selector remains available for explicit component inspection and headless exports. Component permissions and external-agent configuration remain separate from Zoe's internal conversation engine.

- **Implementation:** [Zoe launcher](guiai-lab/guiai/gem/chat_view.py) · [Ablation GEM GUI](components/ablation/gem-lab/gem/gtk_app.py) · [Existing GEM desktop entry](components/ablation/gem-lab/gem/lab_cli.py)
- **Validation:** [Unified routing tests](guiai-lab/stress/unified_stress.py) · [Ablation GTK tests](components/ablation/gem-lab/stress/gtk_stress.py)
- **Evidence:** [Canonical GEM interface](components/ablation/assets/demos/gem-demo-01.png) · [Real Zoe-in-GEM verification](evidence/chat/gem-verification.json)

## 12. HP-UX and legacy architecture tools

Zoe-managed HP-UX tools provide SOM debugging, PA-RISC emulation, exact format inspection, and native CLI workflows. Ablation adds SunOS and M88K support restored from Zoe-local development.

- **Implementation:** [HP-UX tools](components/hpux-tools/) · [SunOS support](components/ablation/ablation/sunos/) · [M88K analysis](components/ablation/ablation/analyzers/) · [PA-RISC support](components/ablation/ablation/hpux/pa_risc.py)
- **Validation:** [PA-RISC tests](components/ablation/tests/test_pa_risc.py) · [M88K tests](components/ablation/tests/test_m88k.py) · [SunOS tests](components/ablation/tests/test_sunos_aout.py)
- **Evidence:** [Ablation architecture documentation](components/ablation/docs/INDEX.md)

## 13. Chalkboard knowledge library

Reusable ideas, templates, and prompts for research and knowledge engineering. Chalkboard is a content library inspected through `zoe show chalkboard`, not a fictitious GUI process.

- **Implementation:** [Chalkboard library](components/Chalkboard/) · [Templates](components/Chalkboard/templates/) · [Prompts](components/Chalkboard/prompts/)
- **Validation:** [Unified source and content tests](guiai-lab/stress/unified_stress.py)
- **Evidence:** [Chalkboard verification](evidence/unified/chalkboard.json)

## 14. Papers, books, and visual research

- **Canonical monograph:** [Zoe — The Research Universe, 23 pages](paper/zoe-research-universe.pdf) · [LaTeX source](paper/zoe-research-universe.tex) · [Source package](research/papers/archives/zoe-research-universe.tar.gz) · [Gallery](research/papers/galleries/18-zoe-research-universe/README.md)
- **Historical books:** [Paper archive](paper/archive/) · [Research-paper archive](research/papers/archive/)
- **Research sources:** [LaTeX and reproduction sources](research/papers/sources/) · [Source packages](research/papers/archives/) · [Dorothy and CERN library](research/papers/zoe-research/)
- **arXiv submissions:** [Original Autonomy](research/arxiv/01-original-autonomy/) · [Unified Autonomy](research/arxiv/02-unified-autonomy/) · [Zoe Autonomy](research/arxiv/03-zoe-autonomy/)
- **Visual archive:** [Complete catalog](research/visual-archive/catalog/README.md) · [Machine-readable manifest](research/visual-archive/manifest/catalog.json) · [Source-state record](research/visual-archive/SOURCES.md)

The current visual archive contains **456 byte-distinct visuals from 843 source occurrences**, with detailed explanation pages and provenance.

## 15. Seventeen registered engines

The runtime registry exposes Zoe native shell, CERN Workbench, Ablation core, Ablation GEM Lab, Canonical GEM, GEM HELEN, BRAIN GEM, HP-UX Tools, Zoe Life, Cerotto GEM, Research GEM, Zoe Autonomy, Kevlar, PDF Signature Toolkit, Neurogarden, Chalkboard, and PALA Recovery.

- **Implementation:** [Authoritative registry](guiai-lab/guiai/gem/unified.py) · [Source locks](components.lock.json) · [Runtime and evidence contract](one-system.json)
- **Validation:** [Unified source tests](guiai-lab/stress/unified_stress.py) · [Six-host verifier](scripts/verify-one-system.py)
- **Evidence:** [Unified component manifest](evidence/unified/components.json) · [Six-host verification](evidence/one-system/verification.json)

## 16. Verification, boundaries, and the AGI/ASI roadmap

Use `python scripts/verify-one-system.py` for the integrated six-host base check, `--reflect` for reflection, and `--image` for a shared real RGB input. Component suites cover their own mathematics, parsers, native interfaces, forensic engine, and evidence.

The legacy four-capability evaluation is preserved as a historical baseline whose `vision_changes_decision` check failed. The newer Event-Causal Active Perception contract directly tests and passes visual causal influence through its own declared fixtures. Both records are retained so development remains auditable.

- **Implementation:** [Unified verifier](scripts/verify-one-system.py) · [Event evaluation](components/Zoe-Autonomy/src/zoe_autonomy/event_evaluation.py) · [Semantic evaluation](components/Zoe-Autonomy/src/zoe_autonomy/semantic_artifacts.py)
- **Validation:** [Autonomy tests](components/Zoe-Autonomy/tests/) · [Unified stress tests](guiai-lab/stress/) · [Ablation tests](components/ablation/tests/) · [Cerotto tests](components/cerotto/tests/)
- **Evidence:** [Base verification](evidence/one-system/verification.json) · [Reflection verification](evidence/one-system/reflection-verification.json) · [Visual verification](evidence/one-system/visual-verification.json) · [Event-causal evaluation](components/Zoe-Autonomy/evidence/event-causal/evaluation.json) · [Semantic artifact evaluation](components/Zoe-Autonomy/evidence/semantic-artifacts/evaluation.json) · [Legacy evaluation](components/Zoe-Autonomy/evidence/evaluation/synthetic.json)
- **AGI/ASI acceptance:** [Layered goals and measurement contract](AGI-ROADMAP.md) · [23-page monograph](paper/zoe-research-universe.pdf)

Dorothy uses mouse reference geometry and synthetic research models. CERN hardware tools use source inspection and synthetic replay unless a real hardware grant and measurement are separately recorded. Optional model, sensor, mobile, and external-service backends require their own dependency and environment checks. AGI and ASI are pursued through the explicit cross-domain, held-out, self-improvement, original-research, and control criteria in [AGI-ROADMAP.md](AGI-ROADMAP.md).

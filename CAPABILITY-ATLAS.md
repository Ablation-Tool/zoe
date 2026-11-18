# Zoe capability atlas

This is the canonical directory of Zoe's capabilities and implementations. It describes one integrated research system whose mission is AGI, ASI, and continued open-ended advancement. Detailed behavior, reproduction commands, and evidence remain linked to the owning module rather than duplicated into competing project descriptions.

## 1. Intelligence architecture

### Accessible Volume and operational metacognition

Accessible Volume counts alternatives with probability strictly greater than a threshold before selection. Zoe uses the count inside her own observation and decision loop to inspect how open or settled a choice is. This is operational metacognition: monitoring one's own decision process and using that observation in later reasoning.

Included mathematics: strict threshold sets, complements, momentum, target bands, temperature transforms, multi-horizon continuation volume, causal-repertoire Q-Volume, mirrored forward/retrograde forecasts, calibration comparisons, and response-planning diagnostics.

- Source: `components/next-token-predictability/`
- Native operations: `components/graphics-environment-manager/gem/`
- Research guide: `components/next-token-predictability/docs/RESEARCH.md`
- Algorithm catalog: `components/next-token-predictability/docs/ALGORITHMS.md`

### Self-governing measurement and action

Zoe authors internal goals, constructs proposals and their arguments, ranks declared value, applies guards, executes an internal transition, records outcomes, and uses the resulting state in the next cycle. The complete vector measures internal goal authorship, proposal generation, value-based selection, execution, effective perception, state responsiveness, and guard compliance.

- Canonical engine: `components/Zoe-Autonomy/src/zoe_autonomy/`
- Native adapter: `guiai-lab/guiai/gem/autonomy.py`
- Architecture: `components/Zoe-Autonomy/README.md`
- Autonomous capability selection: `components/Zoe-Autonomy/src/zoe_autonomy/autonomous.py`

### Reflection and self-improvement

Current reflection compares arithmetic and precision model proposals across training views, selects by goal-constrained likelihood-derived value, and adopts only improvements on a held-out view. It preserves the prior model on regression and does not rewrite its source during that experiment.

The next development stage expands this into generalized self-improvement across unrelated domains, governed by the acceptance contract in `AGI-ROADMAP.md`.

- Source: `components/Zoe-Autonomy/src/zoe_autonomy/self_reflection.py`
- Evidence: `evidence/self-reflection/`
- Soroban working memory: `components/Zoe-Autonomy/src/zoe_autonomy/self_reflection.py` and `components/graphics-environment-manager/COGNITION.md`

### Planning and attention paths

Zoe uses exact Dijkstra paths for declared attention and planning graphs, candidate sensory-outcome simulation, utility evaluation, and guard-constrained action selection. Greedy selection, exhaustive evaluation, heuristic ranking, and approximate prediction remain separate algorithmic choices with explicit guarantees.

- Shared visual attention: `components/graphics-environment-manager/gem/saliency_cognition.py`
- Event planning: `components/Zoe-Autonomy/src/zoe_autonomy/event_reasoning.py`
- Autonomous capability selection: `components/Zoe-Autonomy/src/zoe_autonomy/autonomous.py`

## 2. Event-Causal Active Perception

Zoe reconstructs sparse event streams, forms visual and temporal features, retrieves causal memories, predicts candidate outcomes, independently evaluates uncertainty, selects an action, compares predicted and observed events, and applies gated local learning with replay.

- Event core and representation: `event_core.py`
- Episodic/causal memory: `event_memory.py`
- Candidate reasoning: `event_reasoning.py`
- Gated plasticity: `event_plasticity.py`
- Native uncertainty: `event_uncertainty.py`
- Autonomous integration: `event_autonomy.py`
- Pre-registered evaluation: `event_evaluation.py`

These modules are under `components/Zoe-Autonomy/src/zoe_autonomy/`.

Measured results: 11/11 synthetic checks, real-camera pass, adaptive validation RMSE 4.641453 versus 5.058147 no-learning, transfer MAE 3.265625 versus 3.531250 static saliency, OOD detection 0.875, zero validation false positives, and 71.24 cycles/s.

Guides: `components/Zoe-Autonomy/EVENT-CAUSAL.md` and `components/Zoe-Autonomy/ILAB-INTEGRATION.md`.

### iLab-derived foundation

The integration accounts for the archived iLab source, documentation, programs, images, and dependency graphs as reference, adapted, optional, rejected, or blocked material. VisualCortex, Brain, saliency, Bayesian surprise, gist, visual memory, task relevance, object-recognition concepts, and distributed-computation ideas inform the architecture. The current engine uses the validated event-driven mathematics rather than blindly executing the legacy toolkit.

The full third-party mirror remains on the research drive. Its catalog and integration decisions are tracked in `components/Zoe-Autonomy/evidence/ilab/` and `components/Zoe-Autonomy/ILAB-INTEGRATION.md`.

### Modern event vision and spiking directions

The architecture provides a boundary for Dynamic Vision Sensors, event datasets, Tonic, Tarsier, Metavision, snnTorch, SpikingJelly, Norse, and Rockpool. These are optional integrations when their hardware or dependencies are present; the core evaluation does not pretend those external packages are installed.

## 3. Semantics, reverse engineering, and mathematics

### Ablation AIARE

- Semantic function retrieval and behavioral embeddings.
- Binary context, normalized instruction features, and fitted PCA whitening.
- Direct Capstone calls and tail-jump inspection.
- Architecture parsers, disassemblers, analyzers, and knowledge graphs.
- Vulnerability evidence, patch analysis, prior analysis memory, and semantic sweeps.
- Native GEM investigation Lab and evidence replay.
- HP-UX, SunOS, M88K, PA-RISC, Xilinx, ZynqMP, firmware, and timing research tools.

Source: `components/ablation/`. Zoe-integrated semantic evaluation: `components/Zoe-Autonomy/src/zoe_autonomy/semantic_artifacts.py`.

Ablation remains independently developable at `https://github.com/Ablation-Tool/ablation` while its complete integrated source lives here.

### Native mathematical workbench

Seventeen verified operations span accessible volume, Bayesian updates, temporal and causal models, geometry, mirrored observation, and forecast analysis. Canonical GEM also supplies Spatial IR, real little-endian GEM VDI, native rendering, and reproducible workbench checks.

Source: `components/graphics-environment-manager/`. Workbench guide: `components/graphics-environment-manager/WORKBENCH.md`.

### BRAIN GEM and GEM HELEN

BRAIN GEM supplies an independently runnable Bayesian field notebook, deterministic/stochastic chambers, hash-chained memory, geometry, forecasts, and native views. GEM HELEN supplies optimized geometry, rhythm, onset experiments, stored forward/retrograde distributions, and lightweight creative scenes.

Sources: `components/brain-gem/` and `components/gem-helen/`.

## 4. Dorothy and Neurogarden

Dorothy is Zoe's brain-cancer research priority and honors Dorothy McEwen Kildall.

### Atlas and spatial inspection

Twelve verified Allen Mouse CCFv3 structures, 315,932 triangles, deterministic rendering, ontology Rings, volume-scaled Jenga, coronal Stacks, multiple orientations, and SVG/PNG/GEM export.

### Neural simulation and numerical instruments

DFT band powers, delay embedding, Lyapunov estimation, Higuchi dimension, Shannon entropy, point-spread convolution/recovery, bounded SPD geometry, radial Pennes bioheat, neutrosophic membership similarity, exact integer arithmetic, and fixed synthetic radiobiology examples.

### Generative research world

Bounded experiments connect biology, neuroscience, physics, CERN, GEM, and community research while retaining measurement and human-review boundaries.

### Scientific corpus

Thirty-seven populated books, 1,751 indexed sections, 130 reviewed entries, 1,621 pending entries, negative results, contradictory findings, source audits, and reproducible coverage records.

Sources:

- `components/agent-logging-system/agent_logging_system/neurogarden_neural.py`
- `components/agent-logging-system/agent_logging_system/neurogarden_world.py`
- `components/agent-logging-system/agent_logging_system/neurogarden_advanced.py`
- `guiai-lab/guiai/gem/dorothy.py`
- `components/agent-logging-system/evidence/neurogarden/`

Guide: `components/agent-logging-system/docs/NEUROGARDEN.md`.

## 5. CERN, physics, firmware, and replay

- **CERN Workbench:** Zoe-owned CERN console, HELIOS, Atelier, process lifecycle, health checks, browser targets, and no-overwrite manifests.
- **Evidence Navigator:** source-first CERN gallery, hash verification, cited retrieval, guarded observations, bridge proposals, and curriculum.
- **FELIX:** build indexing, exact-build Ablation correlation, capability maps, native replay, JSON, and stereo WAV.
- **FELIX HDL:** source-backed LCB, STAR/Flink, ftools, Wupper, regmap, and driver maps with HDL/provenance export.
- **Protocol Lab:** SPECS checksums, ninth-bit markers, short/long counts, and AMAC decoding.
- **Waveform Replay:** bounded VCD, event JSONL, normalized replay, optional WDB reading, declarations, and truncation records.
- **Patchbay:** Intel HEX, Xilinx BIT, source ZIP, ZynqMP, U-Boot legacy/FIT, board scenes, and source inventories.
- **Timing twin and sonification:** synthetic timing/DMA replay and deterministic 40.08 Hz sonification.
- **Signed update capsules:** Ed25519 signatures through OpenSSL, trusted-key checks, artifact verification, and separately gated acceptance plans.

Guides are in `guiai-lab/docs/`: `ZOE_WORKBENCH.md`, `EVIDENCE.md`, `PROTOCOL.md`, `WAVEFORM.md`, and `PATCHBAY.md`.

## 6. Cognitive memory and reasoning

### Cognitive Field

Sourced encoding, bounded working memory, declarative storage, revision-checked retrieval, procedural matching, and review-required proposals. Source: `guiai-lab/guiai/gem/cognitive.py`.

### Bayesian notebook

Questions, competing claims, falsifiers, likelihood ratios, log-odds updates, belief diffs, evidence dependence, chambers, and next-test priorities. Source: `guiai-lab/guiai/gem/field.py`.

### Event-causal memory

Decoupled working state, sparse retrieval, event schemas, relational binding, and action-linked outcomes. Source: `components/Zoe-Autonomy/src/zoe_autonomy/event_memory.py`.

### Presence and internal time

Attention, sourced observations, event-ordinal time, known unknowns, correction, and review-required decisions. Source: `guiai-lab/guiai/gem/presence_view.py`.

### Internal Clock

Exact software ticks, host cycles, daily phase, developmental gates, explicit local replay events, and deterministic exports. Source and guide: `guiai-lab/guiai/gem/cicada.py`, `guiai-lab/docs/CICADA.md`.

### Replayable knowledge graph

Source, revision, trust, stability, and declared-link observations in a canonical SHA-256 event chain with no-overwrite saves and load-time verification. Source: `guiai-lab/guiai/gem/knowledge.py`.

### Zoe Cog

A small trainable bigram processor with forward/backward token walks, source hashes, and accessible-volume measurements. Source: `guiai-lab/guiai/gem/cog.py`.

### Qualia and Q-Volume

Causal repertoires, q-arrows, threshold filtrations, and Accessible Q-Volume provide a formal annotation instrument connected to the same accessible-set mathematics. Guide: `guiai-lab/docs/QUALIA.md`.

## 7. Geometry, creativity, and guided practice

- **Geometry Atlas:** Procrustes similarity/rigid/affine alignment, draggable landmarks, ellipses, parabolic envelopes, circles, clocks, and graph invariants.
- **Second Eye:** synthetic stereo depth, disparity, thin-lens defocus, and quantization sensitivity.
- **Artline:** vector paths, editable shapes/text, layers, groups, transformations, undo/redo, transactional merge, and SVG/PNG/GEM output.
- **Pentomino:** seeded/masked spatial practice, deadlines, row/hole measurements, replay, and budget comparisons.
- **Pentacube:** thirty pentomino regions, legal cube permutations, exact inverses, deterministic scrambles, hints, and verified replay.
- **Life:** finite non-wrapping Conway B3/S23 with deterministic patterns, editing, play, step, and exports.
- **Brain Life:** rotating 3D voxel automaton with 26-neighbor B3/S23 updates and a brain-shaped illustrative seed.
- **Visual text:** direct ASCII text-to-cell rendering with optional later evolution.
- **Practice Navigator:** visual guidance through time, space, packet layers, synthetic timing, and the next attempt.
- **Resilience Atlas:** sixteen infrastructure sectors and a synthetic waveform-signature laboratory.
- **Leadership Garden:** attempts, outcomes, advice, mistakes, uncertainty, stop conditions, and append-only corrections.
- **Maison:** executive-clarity association deck and reversible practice evidence.
- **Thumbelina and Human × Zoe:** editable semantic vector art and original collaborative visual research.

Guides: `guiai-lab/docs/GEOMETRY-ATLAS.md`, `ARTLINE.md`, `PENTOMINO.md`, `PENTACUBE.md`, `PILOT.md`, `RESILIENCE.md`, `LEADERSHIP.md`, and `MAISON.md`.

## 8. Mobile, Tiny Zoe, and accessibility

- Android and iOS native sources.
- Tiny Zoe/Zoe Cell quantized probability exchange and deterministic behavioral simulator.
- Zoe Trinity across Tiny, mobile, and laptop with independent response verification and retained observations.
- Native Windows x86_64 interface and C++17 measurement/journal core.
- One-frame OCR, labels, optional on-device descriptions, turn-taking Talk, installed voices, Accessible Volume, and SafeConvert.
- Multi-view, acoustic ranging, radio, location, connectivity, Screen Space, App Observatory, and device instruments behind explicit controls.
- Signed short-lived QR pairing offers, ephemeral X25519 exchanges, identity fingerprints, human-confirmed verification phrases, and exact-document certificates.

Start with `mobile/README.md`, `mobile/TRINITY.md`, `mobile/PAIRING.md`, and `mobile/windows/README.md`.

## 9. Security, forensics, and research integrity

### Cerotto

Guarded forensic cases and conversations, native C11 engine, timelines, carving, manifests, vault evidence, response boundaries, and release workflows. Source: `components/cerotto/`.

### Kevlar

MCP proxy firewall, pure policy engine, content disarm, audit evidence, and explicit security operations. Source: `components/kevlar/`.

### PDF Signature Toolkit

Source-integrity records and detached PKCS #7 PDF signatures. Source: `components/pdf-signature-toolkit/`.

### Evidence and actuation

Source hashes, no-overwrite exports, reversible first actions, replayable records, negative results, owner-granted host/network/hardware scopes, separate forensic/vault authority, and verified emergency stop.

Guides: `components/Zoe-Autonomy/ACTUATION.md`, `components/Zoe-Autonomy/GATEWAY.md`, and `evidence/actuation/`.

## 10. Connected research and agent adapters

Ten adapters provide:

1. Browser automation.
2. Research APIs.
3. Persistent research memory.
4. Connected productivity services.
5. Scheduled jobs.
6. Compute environments.
7. MCP/ACP agent protocols.
8. Notifications.
9. Rich media and OCR.
10. Hardware instruments.

Zoe can construct and rank calls across these adapters through her no-argument autonomous step. Connected Kimi and Claude CLIs use existing owner-authorized accounts without embedding credentials in evidence. The vidlib adapter supports local search, explicit indexing, gated URL retrieval, and bounded citations.

Guides: `components/Zoe-Autonomy/CAPABILITIES.md`, `GATEWAY.md`, and `guiai-lab/docs/VIDLIB.md`.

## 11. Native desktop and embedded agent

Zoe supplies an OS-style user-space workbench with explicit application launching, duplicate prevention, process tracking/stopping, source inspection, manifest export, and shared knowledge export. The mathematical interface uses a golden-ratio split, consistent spacing and palette, accessible text state, and restrained timing.

An optional Ablation-style VTE agent terminal supports explicit Start/Stop, left/right placement, quoted path drops, and an owner-only bounded Unix socket for validated desktop actions. It does not provide arbitrary socket code evaluation.

Sources: `guiai-lab/guiai/gem/desktop_view.py`, `desktop.py`, and `agent_bridge.py`.

## 12. HP-UX and legacy architecture tools

Zoe-managed HP-UX tools provide SOM debugging, PA-RISC emulation, exact format inspection, and native CLI workflows. Ablation adds SunOS and M88K support restored from Zoe-local development.

Sources: `components/hpux-tools/`, `components/ablation/ablation/sunos/`, and `components/ablation/ablation/analyzers/`.

## 13. Chalkboard knowledge library

Reusable ideas, templates, and prompts for research and knowledge engineering. Chalkboard is a content library inspected through `zoe show chalkboard`, not a fictitious GUI process.

Source: `components/Chalkboard/`.

## 14. Papers, books, and visual research

- 35-page `Zoe — The Research Universe` and 18-page capability prospectus in `paper/`.
- Native Zoe proof-of-concept and accessible guide in `paper/`.
- Eighteen collected papers, 321 page renders, 90 extracted figures, LaTeX sources, reproduction archives, Dorothy documents, CERN documents, and module indexes in `research/papers/`.
- Three arXiv submission packages with metadata and sources in `research/arxiv/`.
- 359 byte-distinct visuals from 668 preserved source occurrences, with detailed explanation pages and provenance, in `research/visual-archive/`.

## 15. Sixteen registered engines

The runtime registry exposes Zoe native shell, CERN Workbench, Ablation core, Ablation GEM Lab, Canonical GEM, GEM HELEN, BRAIN GEM, HP-UX Tools, Zoe Life, Cerotto GEM, Research GEM, Zoe Autonomy, Kevlar, PDF Signature Toolkit, Neurogarden, and Chalkboard.

The authoritative registry is `guiai-lab/guiai/gem/unified.py`. Source provenance is locked in `components.lock.json`; runtime and evidence contracts are in `one-system.json`.

## 16. Verification and current boundaries

Use `python scripts/verify-one-system.py` for the integrated six-host base check, `--reflect` for reflection, and `--image` for a shared real RGB input. Component suites cover their own mathematics, parsers, native interfaces, forensic engine, and evidence.

The legacy four-capability evaluation is preserved as a historical baseline whose `vision_changes_decision` check failed. The newer Event-Causal Active Perception contract directly tests and passes visual causal influence through its own declared fixtures. Both records are retained so development remains auditable.

Dorothy uses mouse reference geometry and synthetic research models. CERN hardware tools use source inspection and synthetic replay unless a real hardware grant and measurement are separately recorded. Optional model, sensor, mobile, and external-service backends require their own dependency and environment checks.

AGI and ASI are pursued through the explicit cross-domain, held-out, self-improvement, original-research, and control criteria in `AGI-ROADMAP.md`.

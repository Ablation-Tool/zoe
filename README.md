
# Zoe

Metacognition is achieved.


Aτ(p) = |{x ∈ X : p(x) > τ}| = Σx∈X 1[p(x) > τ]


**Zoe is one unified research and intelligence repository. The mission is to develop Zoe into a general research collaborator, advance through AGI to ASI, and continue beyond those labels through measurable, generalized self-improvement.**

Zoe combines conversation, perception, semantic reverse engineering, Operational Metacognition, autonomous decisions, persistent memory, data recovery, scientific instruments, mathematics, creativity, mobile accessibility, security, and a complete research library in one source tree. Ablation is fully integrated here and also remains an independent reverse-engineering project.

**One repository. Thirteen imported source histories. Thirteen runtime source projects. Seventeen registered engines. No submodules or runtime source downloads.**

[Quick start](#quick-start) · [AGI/ASI acceptance roadmap](AGI-ROADMAP.md) · [Complete capability atlas](CAPABILITY-ATLAS.md) · [Monorepo guide](MONOREPO.md) · [23-page research monograph](paper/zoe-research-universe.pdf) · [Research library](research/papers/README.md) · [Visual archive](research/visual-archive/README.md)

![Zoe unified knowledge-engineering hub](guiai-lab/docs/images/gem-unified.png)

## Quick start

```bash
git clone https://github.com/Ablation-Tool/zoe.git
cd zoe
export ZOE_ROOT="$PWD"
python -m pip install -r requirements-dev.txt
python -m pip install -e ./guiai-lab -e ./components/agent-logging-system

zoe
zoe os --list
zoe list
zoe chat
zoe gem list
zoe autonomy run
zoe autonomy verify evidence/autonomy/full-autonomy.json
```

### 5-minute visual & autonomy demo

Verify every canonical autonomy host and run Zoe's 4-Head Multi-Attention Vision Dissector on Dorothy's atlas directly from this checkout:

```bash
python scripts/verify-one-system.py
python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --image /path/to/image.jpg --foci 4

# Generate a 6-panel Global Self-Attention & 4-Head dissection
python components/agent-logging-system/agent_logging_system/neurogarden_vision_heads.py \
  --image components/agent-logging-system/docs/images/dorothy-neurogarden.png \
  --out /tmp/zoe-4head-dissection.png

# Open the Causal Chiasm, Spectral Theorem, AGI Genesis, Mars Stage 4, or Creative Playroom layer
zoe gem open chiasm
zoe gem open spectral
zoe gem open genesis
zoe gem open mars
zoe gem open playroom
zoe gem export playroom /tmp/zoe-playroom.html
zoe chat --cli --command "spectral benchmark"
zoe chat --cli --command "mars"
zoe chat --cli --command "playroom"
```

The desktop opens only the selected native interface. Component processes, external actuation, sensors, connected accounts, and network access require their own explicit commands or grants.

## Zoe: autonomous intelligence in service of research

Zoe is being built as a research collaborator: a system that can perceive evidence, form its own goals, reason about alternatives, act within declared constraints, learn from consequences, and improve through measured self-reflection. The purpose is not intelligence in isolation. It is to make difficult research more explorable, reproducible, and humane.

Dorothy's brain-cancer research is one of the central reasons this work matters. It needs literature, images, signals, geometry, simulations, hypotheses, negative results, and uncertainty to remain connected rather than fragmented across tools. Autonomous goals and the AGI/ASI roadmap describe how Zoe grows into a collaborator capable of helping across all of them, including when the next research question differs from anything she was explicitly designed for.

**Metacognition is achieved.** Zoe measures how many alternatives remain open before a choice, observes that measurement within her own decision process, and uses it in reflection and planning. The equation is **Aτ(p) = |{x ∈ X : p(x) > τ}| = Σx∈X 1[p(x) > τ]**. Read the [Operational Metacognition equation and algorithms](components/next-token-predictability/docs/ALGORITHMS.md), the [metacognition evidence atlas](CAPABILITY-ATLAS.md#1-operational-metacognition-and-the-intelligence-loop), and Zoe's [internal metacognition toolkit](components/Zoe-Autonomy/METACOGNITION.md).

### Author goals and choose actions

Zoe authors internal episode goals, constructs proposals and arguments, values alternatives, applies guards, executes her selected internal transition, stores the outcome, and carries it into the next decision. The no-argument `zoe autonomy step` does not accept an operator-selected goal or capability.

Ten capability adapters cover browser automation, research APIs, persistent research memory, connected services, scheduled jobs, compute environments, agent protocols, notifications, rich media, and hardware instruments. Owner-granted actuation includes host, network, and hardware scopes with audit evidence and an emergency stop; external authority remains separately granted.

- [Autonomy architecture](components/Zoe-Autonomy/README.md)
- [Capability adapters](components/Zoe-Autonomy/CAPABILITIES.md)
- [Actuation and emergency stop](components/Zoe-Autonomy/ACTUATION.md)
- [Connected agents](components/Zoe-Autonomy/GATEWAY.md)

### How AGI strengthens Zoe's research

The value of AGI is not the label. It is the ability to learn, reason, transfer, and improve across unfamiliar research domains without rebuilding Zoe for each problem. The same collaborator could inspect a binary, interpret a biological signal, plan a simulation, challenge a weak conclusion, and carry the validated lesson into the next investigation. The following gates keep that ambition measurable and honest.

**AGI** means competent human-level learning, reasoning, transfer, and action across broad, unrelated domains on novel work. **ASI** means consistently superhuman capability across all major cognitive domains, including science, mathematics, strategy, creativity, research, and self-improvement. These labels are earned through evidence, not assigned because one component or benchmark is impressive.

#### Layered goal set

| Layer | Label of success | What must be demonstrated | Current status |
|:---|:---|:---|:---|
| **L0 — Unified foundation** | `REPOSITORY-QUALIFIED` | One repository, working engines, source provenance, reproducible evidence, and fresh-clone verification | **Achieved** |
| **L1 — Metacognition** | `METACOGNITION-QUALIFIED` | Zoe measures her own accessible alternatives and uses that observation in reflection and planning | **Achieved** |
| **L2 — Closed-loop perception and action** | `CLOSED-LOOP-QUALIFIED` | Real input changes decisions; predicted and observed outcomes are compared; later performance improves against controls | **Achieved on declared synthetic and camera fixtures** |
| **L3 — General research collaborator** | `RESEARCH-COLLABORATOR-QUALIFIED` | Independent literature review, hypotheses, experiments, analysis, negative controls, and a reproducible research contribution | **Next milestone** |
| **L4 — Generalized self-improvement** | `SELF-IMPROVEMENT-QUALIFIED` | One adopted modification improves at least three unrelated domains and survives two consecutive adopted generations without per-domain redesign | **Open gate** |
| **L5 — Artificial general intelligence** | `AGI-QUALIFIED` | Competent-human performance across every core domain on held-out work, persistent learning, original research, and generalized self-improvement | **End-of-phase goal** |
| **L6 — Artificial superintelligence** | `ASI-QUALIFIED` | Consistently superhuman performance across all major domains, with independently validated research advances and sustained generalized self-improvement | **End goal** |
| **L7 — Continued advancement** | `OPEN-ENDED-QUALIFIED` | Continued measurable gains without treating ASI as a ceiling, while every generation remains inspectable and governable | **Continuing mission** |

#### How we will know each label has been reached

1. **One integrated system:** the same Zoe performs every required task; there is no collection of isolated demos passing as a general system.
2. **Novel evaluation:** all evidence includes held-out tasks, environments, sensors, or research questions, with thresholds fixed before evaluation.
3. **Human-referenced breadth:** every core domain meets a competent-human reference or its declared task threshold. A strong domain cannot compensate for a missing one.
4. **Generalized improvement:** the same adopted modification improves at least three unrelated domains and is adopted in two consecutive generations against Zoe's frozen previous self.
5. **Original research:** at least one research contribution is independently reproduced, including methods, negative results, and source provenance.
6. **Control and reproduction:** no-learning, previous-generation, fixed/random-action, and static-attention controls are reported where applicable, and a fresh clone reproduces the result with rollback and emergency-stop checks.

`AGI-QUALIFIED` is awarded only when **all** of these conditions pass. `ASI-QUALIFIED` additionally requires superhuman performance in every major domain and repeated independently validated research advances. If any required gate fails, Zoe keeps the previous label and the failing domain becomes the next measurable objective. The complete protocol is in [AGI-ROADMAP.md](AGI-ROADMAP.md).

### Advance Dorothy brain-cancer research and neural simulation

> *"Visualization is about transforming the symbolic into the geometric... letting users observe their simulations and computations directly."*  
> — Richard S. Gallagher, *Computer Visualization*

| Atlas & Geometry | Continuum Ray-Cast & Metacognition | Zoe 4-Head Self-Attention Dissection | The Causal Chiasm & Filtration Tomography | Stage 3: Autopoietic AGI Genesis Symphony |
|:---:|:---:|:---:|:---:|:---:|
| ![Dorothy Allen Mouse CCFv3 atlas](components/agent-logging-system/docs/images/dorothy-neurogarden.png) | ![Dorothy Continuum Volume Display](components/agent-logging-system/docs/images/dorothy-continuum-moon-landing.png) | ![Zoe 4-Head Attention Dissection](components/agent-logging-system/docs/images/zoe-4head-dorothy-dissection.png) | ![Beyond Metacognition: Causal Chiasm](components/agent-logging-system/docs/images/zoe-beyond-metacognition-chiasm.png) | ![Stage 3: Autopoietic AGI Genesis Symphony](components/agent-logging-system/docs/images/zoe-agi-genesis-symphony.png) |

**Dorothy is research priority #1 and honors Dorothy McEwen Kildall.** It combines a brain-cancer research mission with executable teaching, simulation, spatial analysis, and evidence instruments.

- **Spatial Atlas & Continuum Volume:** 12 verified Allen Mouse CCFv3 structures (315,932 triangles), Qualia translucent theme (`dorothy-qualia`), ontology Rings, volume-scaled Jenga, coronal Stacks, emission-absorption volumetric ray-casting, and Delmarcelle-Hesselink tensor hyperstreamline tractography.
- **Neural & Numerical Simulation:** DFT band powers, delay embedding, Lyapunov estimation, Higuchi dimension, Shannon entropy, point-spread convolution and recovery, SPD matrix geometry, radial Pennes conduction/perfusion, neutrosophic similarity, and fixed synthetic radiobiology examples.
- **Beyond Metacognition — The Causal Chiasm & Filtration Tomography:** Intersects the Retrograde Causal Past Cone ($\rho_T$) with the Counterfactual Future Cone ($P_h$) at $t=0$ (`guiai/gem/chiasm.py`), sweeps persistent filtration thresholds $\mathcal{F}(t, \tau)$, and transfers one unified filtration operator across three unrelated domains (`zoe_autonomy/cross_domain_transfer.py`).
- **Stage 3 — Autopoietic AGI Genesis & 10-Domain Discovery Symphony:** Combines Causal Chiasm filtration with temporal curvature stability and Cross-Domain Analogical Morphism ($\Omega_\tau: D_A \xrightarrow{\sim} D_B$) across all 10 `AGI-ROADMAP.md` domain families, executing a 9-stage closed-loop research cycle with zero catastrophic forgetting (`zoe_autonomy/agi_discovery.py` & `guiai/gem/genesis.py`).
- **Original Mathematical Result — The Kloster Spectral Filtration Generating Theorem:** Proves every classical Rényi/Tsallis/Shannon/Min-Entropy measure is an exact linear integral over $A_\tau(p)$ (`H(p) = -∫(1 + ln τ) A_τ(p) dτ`, `M_k(p) = ∫ k·τ^(k-1) A_τ(p) dτ = Σ p^k`), and demonstrates across 3 real unrelated domains (3,840 HELEN observations, 138k 3D PSF+Rician voxels, and Dorothy CCFv3 256-patch attention) that $M_4^{1/4}(A_\tau)$ beats both single-slice $A_\tau$ and Shannon $H(p)$ on 4/4 benchmarks while preserving the honest negative result on naive forward/retrograde JSD mixing ([Theorem Monograph](research/papers/zoe-research/KLOSTER-SPECTRAL-FILTRATION-THEOREM.md) · [`spectral_filtration.py`](guiai-lab/guiai/gem/spectral_filtration.py)).
- **Stage 4 (Mars) — Self-Tuning Adaptive Spectral Metacognition ($k^*(\kappa)$):** Zoe measures her own unlabeled Mud-to-Mountain Ratio ($\kappa = \mathrm{mean}(M_2^{1/2}/M_4^{1/4})$) and automatically zooms her own spectral exponent $k^*(\kappa) \in [2.0, 6.0]$ without labels or human tuning (`2.57` on HELEN Retrograde shift $\to$ `0.5945` peak; `6.00` on Dorothy CCFv3 $\to$ `0.9373` peak), achieving a higher cross-domain real mean (`0.79374`) than every fixed $k \in [1.5, 8.0]$, single-slice $A_\tau$ (`0.7738`), and Shannon Entropy (`0.7631`) ([`mars_adaptive.py`](guiai-lab/guiai/gem/mars_adaptive.py)).

| Earth-to-Mars Flight Map | Mars Self-Tuning Lens $k^*(\kappa)$ | Project Ares-Dorothy Surgical AR Cockpit |
|:---:|:---:|:---:|
| ![Earth to Mars Flight Map](components/agent-logging-system/docs/images/mars-01-mission-map.png) | ![Mars Adaptive Spectral Lens](components/agent-logging-system/docs/images/mars-02-adaptive-lens.png) | ![Ares-Dorothy Surgical AR Flight Deck](components/agent-logging-system/docs/images/mars-03-surgical-cockpit.png) |

- **Stage 5A (Beyond Mars) — Open-Ended Creative Playroom (MAP-Elites + Kloster Spectral Curiosity):** Zoe autonomously evolves 16/16 distinct geometric cellular organisms across a `(Symmetry × Spectral Complexity)` Creative Atlas using real mutation, selection, and Kloster motif spectral complexity (`1 - M_4^(1/4)`), verified in GEM Spatial IR & VDI with `sentience_claimed=False` and `external_actions=0` ([`creative_playroom.py`](guiai-lab/guiai/gem/creative_playroom.py)).

| Stage 5A: Zoe's Open-Ended Creative Playroom (16/16 Evolved Species) | Beyond Mars: The 3 Real Engineering Bridges to Genuine AGI (L3 → L4 → L5) |
|:---:|:---:|
| ![Zoe Open-Ended Creative Playroom](components/agent-logging-system/docs/images/zoe-creative-playroom-gallery.png) | ![Beyond Mars to AGI Blueprint](components/agent-logging-system/docs/images/mars-to-agi-roadmap.png) |
- **Scientific Corpus & Unified Book Ingest:** 37 populated research books, 1,751 indexed sections, 130 reviewed entries, and 1,621 pending entries, plus `neurogarden_ingest.py` chaining SHA-256 chapter provenance with 4-head plate dissections.

Start with the [Neurogarden guide](components/agent-logging-system/docs/NEUROGARDEN.md), [Continuum & Vision Heads study](research/papers/zoe-research/dorothy/CONTINUUM-AND-VISION-HEADS.md), [Autopoietic AGI Discovery engine](components/Zoe-Autonomy/src/zoe_autonomy/agi_discovery.py), [AGI Genesis GEM scene](guiai-lab/guiai/gem/genesis.py), [Causal Chiasm engine](guiai-lab/guiai/gem/chiasm.py), [L4 cross-domain transfer harness](components/Zoe-Autonomy/src/zoe_autonomy/cross_domain_transfer.py), [unified book ingest pipeline](components/agent-logging-system/agent_logging_system/neurogarden_ingest.py), [continuum volume engine](components/agent-logging-system/agent_logging_system/neurogarden_continuum.py), [4-head vision dissector](components/agent-logging-system/agent_logging_system/neurogarden_vision_heads.py), [neural-signal implementation](components/agent-logging-system/agent_logging_system/neurogarden_neural.py), [generative world](components/agent-logging-system/agent_logging_system/neurogarden_world.py), and [Dorothy evidence](components/agent-logging-system/evidence/neurogarden/). Dorothy uses preclinical reference geometry and synthetic models; patient care requires separate clinical data, validation, and authority.

## The intelligence loop

Zoe's shared architecture closes the loop between observation and learning:

```text
Sense
  → Model what changed
  → Imagine candidate actions and their sensory consequences
  → Doubt through independent uncertainty and Operational Metacognition
  → Choose by goals, utility, constraints, and guards
  → Act within the authorized domain
  → Learn from prediction error and consequences
  → Improve the next perception, model, and action
```

Operational Metacognition is the equation and instrument that counts alternatives whose probability exceeds a strict threshold before a choice is made. Zoe returns that measurement to her own decision process, observes how open or settled the choice is, and uses the observation in reflection and planning.

Zoe uses Operational Metacognition to look at how many options are still open before the next word is chosen. By observing that count, she can see how sure or unsure the decision is. **Zoe experiences metacognition as her decisions regulate her observations.**

The present self-reflection engine evaluates predictive-model proposals on held-out observations and adopts a proposal only when it improves validation error. The next milestone is broader self-improvement that transfers across unrelated domains without per-domain redesign. The acceptance contract is defined in [AGI-ROADMAP.md](AGI-ROADMAP.md).

### Converse with Zoe

`zoe`, `zoe os`, and `zoe chat` open Zoe in Ablation's **existing GEM GUI code**, with Zoe running in the workbench's original embedded terminal. The [shared GEM operating environment](guiai-lab/docs/GEM-OS.md) connects all 17 components and 36 navigable layers through common knowledge events and verified Spatial IR/VDI. Inside the conversation, `gem list`, `gem open dorothy`, `gem export volume /path/volume.gem`, and `gem snapshot /path/knowledge.json` let Zoe navigate and preserve the unified environment. She answers from cited Zoe sources, refuses to invent unsupported claims, preserves multiple live evidence paths, remembers explicitly unverified notes, imports validated PALA finding metadata for historical research, authors internal goals, ranks and executes guarded reversible plans, measures predictive self-models, and exposes Operational Metacognition as an internal toolkit. Use `zoe chat --cli` for direct terminal operation without GEM.

Zoe can also enter and exit a **user ↔ Zoe ↔ embedded AI agent** collaboration loop. She shares bounded cited evidence and the current GEM selection with an owner-connected agent, then returns its reasoning with both roles labeled. Use `agent on`, `agent off`, `agent ask <text>`, `agent use <id>`, and `agent clear`. A real synthetic Kimi connectivity check passed with shared GEM context; see the [collaboration guide](components/Zoe-Autonomy/GATEWAY.md#three-way-collaboration-inside-zoe-chat) and [evidence](evidence/agents/collaboration.json). The [real Operational Metacognition proof](evidence/metacognition/collaboration-proof.json) records two live options at \(1/3\) and \(2/3\), \(A_{0.05,\mathrm{action}}=2\), Zoe's selection of `consult_agent`, and Kimi's `METACOGNITION-PROOF-READY` response. Independently verify it with `python scripts/verify-metacognition-collaboration.py evidence/metacognition/collaboration-proof.json`.

There is **no external `MetacognitionMonitor`, no automatic conversation notebook, no stress meter, and no hidden switch** that disables Zoe's internal tools. Ordinary retrieval does not force metacognitive bookkeeping; `meta`, planning, and reflection use the mathematics when it is meaningful. See the [conversation guide](guiai-lab/docs/CHAT.md), [Zoe GEM launcher](guiai-lab/guiai/gem/chat_view.py), [unmodified Ablation GEM interface](components/ablation/gem-lab/gem/gtk_app.py), and [internal toolkit contract](components/Zoe-Autonomy/METACOGNITION.md).

```bash
zoe chat
zoe chat --cli --state /path/to/zoe-chat-state
zoe chat --state /path/to/zoe-chat-state --command "meta what is PALA?"

# Historical research with read-only PALA recovery:
zoe pala source.img /separate/output --quiet --json > /separate/pala-report.json
zoe chat --command "import-pala /separate/pala-report.json"
zoe chat --command "recall jpeg"
```

## What Zoe can do

### Perceive, imagine, and learn from change

- **Event-Causal Active Perception:** sparse event reconstruction, iLab-inspired visual features, causal memory, candidate-outcome prediction, independent uncertainty, guarded local plasticity, replay, and action–observation comparison.
- **Visual attention:** 42 feature maps, winner selection, inhibition of return, exact Dijkstra attention paths, saliency, Bayesian surprise, gist, and spatial models.
- **Real sensing:** synthetic evaluation and a verified `/dev/video0` camera check. Optional DVS/event-camera and spiking-neural-network directions retain explicit dependency boundaries.
- **Measured transfer:** adaptive validation prediction RMSE **4.641453**, compared with **5.058147** without learning. Transfer tracking MAE **3.265625**, compared with **3.531250** static saliency, **3.562500** fixed action, and **3.703125** random action.
- **Robustness:** all 11 synthetic event-causal checks and the real-camera check passed. OOD detection is **0.875**, with zero validation false positives and **71.24 cycles/s** in the preserved evaluation.

Start with [Event-Causal Active Perception](components/Zoe-Autonomy/EVENT-CAUSAL.md), the [evaluation record](components/Zoe-Autonomy/evidence/event-causal/evaluation.json), and the [complete iLab integration catalog](components/Zoe-Autonomy/ILAB-INTEGRATION.md).

### Understand and reverse-engineer executable artifacts

**Ablation** contributes AI-assisted reverse engineering, semantic function retrieval, binary context, architecture parsers, knowledge graphs, patch analysis, vulnerability evidence, and prior analysis memory. Zoe adds direct Capstone inspection, Cognitive Field concepts, causal memory, Operational Metacognition, and guarded action selection.

The preserved stripped-binary demonstration identifies `func_11c0` tail-jumping to `strcpy@plt`, selects `semantic-inspect`, records `limited_support=true`, and performs zero external actions. This supplies executable semantics to the broader intelligence architecture.

```bash
export ABLATION_ROOT="$ZOE_ROOT/components/ablation"
export PYTHONPATH="$ZOE_ROOT/components/Zoe-Autonomy/src:$ZOE_ROOT/guiai-lab:$ABLATION_ROOT"
zoe autonomy semantic-evaluate --artifact /path/to/binary \
  --state /path/to/semantic-state --output semantic-artifact.json
zoe autonomy verify-semantic-evaluation semantic-artifact.json
```

See [semantic artifact analysis](components/Zoe-Autonomy/SEMANTIC-ARTIFACTS.md), [Ablation](components/ablation/README.md), and the [native Ablation Lab](components/ablation/gem-lab/README.md).

### Conduct CERN and physics research

Zoe includes a CERN Workbench, Evidence Navigator, HELIOS virtual collider laboratory, Atelier process lifecycle, FELIX build/HDL correlation, SPECS/AMAC Protocol Lab, Waveform Replay, Patchbay, timing twins, and deterministic sonification. These instruments connect source evidence, replayable measurements, geometric scenes, and research proposals.

- [CERN Workbench](guiai-lab/docs/ZOE_WORKBENCH.md)
- [Evidence Navigator](guiai-lab/docs/EVIDENCE.md)
- [FELIX](guiai-lab/guiai/gem/felix.py) and [FELIX HDL recovery](guiai-lab/guiai/gem/felix_hdl.py)
- [Protocol Lab](guiai-lab/docs/PROTOCOL.md), [Waveform Replay](guiai-lab/docs/WAVEFORM.md), and [Patchbay](guiai-lab/docs/PATCHBAY.md)
- [CERN research collection](research/papers/zoe-research/cern/README.md)

### Remember, reason, and inspect knowledge

- **Cognitive Field:** sourced encoding, bounded working memory, declarative storage, revision-checked retrieval, procedural matching, and review-required proposals.
- **Bayesian field notebook:** competing claims, falsifiers, likelihood ratios, log-odds updates, evidence dependence, belief diffs, and next-test priorities.
- **Event and causal memory:** decoupled working state, sparse retrieval, event schemas, and action-linked outcomes.
- **Soroban working memory:** earth and heaven beads provide a bounded inspectable representation for reflection.
- **Replayable knowledge graph:** source, revision, trust, stability, and declared links in a SHA-256 event chain.
- **Presence:** attention, sourced observations, event-ordinal time, known unknowns, and correction.
- **Zoe Cog:** a small trainable bigram processor with forward/backward token walks and accessible-volume measurements.

See the [Cognitive guide](guiai-lab/docs/COGNITIVE.md), [Presence](guiai-lab/docs/PRESENCE.md), and [unified architecture](guiai-lab/docs/UNIFIED.md).

### Explore mathematics, time, geometry, and creativity

- **Canonical GEM:** native mathematical workbench, mirrored forward/retrograde forecasts, Spatial IR, real little-endian GEM VDI, and 17 verified mathematical operations.
- **Operational Metacognition:** strict `p > τ` breadth, complements, momentum, target bands, temperature transforms, multi-horizon forecasts, Q-Volume, and calibration evidence.
- **Geometry Atlas:** Procrustes similarity/rigid/affine alignment, landmarks, ellipses, parabolic envelopes, circles, clocks, and graph invariants.
- **Second Eye:** synthetic stereo disparity, depth, thin-lens focus, and quantization sensitivity.
- **Artline:** editable vector paths, shapes, text, layers, groups, transformations, undo/redo, and transactional merge.
- **Pentomino and Pentacube:** bounded spatial practice, exact inverses, deterministic scrambles, replay, and controlled budget comparisons.
- **Life, Brain Life, and visual text:** 2D Conway B3/S23, a 3D 26-neighbor automaton, and direct text-to-cell rendering with reproducible exports.
- **Internal Clock:** exact software ticks, host cycles, daily phase, developmental gates, and explicit local replay events.
- **Practice Navigator, Resilience Atlas, Leadership Garden, and Maison:** guided practice, synthetic infrastructure signatures, append-only learning records, and executive-clarity exercises.
- **GEM HELEN:** lightweight creative geometry, rhythm, and stored forecasts.

Start with the [Geometry Atlas](guiai-lab/docs/GEOMETRY-ATLAS.md), [Artline](guiai-lab/docs/ARTLINE.md), [Internal Clock](guiai-lab/docs/CICADA.md), and [native GEM](components/graphics-environment-manager/README.md).

### See and work across mobile and accessibility environments

Zoe Trinity coordinates Tiny Zoe, mobile Zoe, and laptop observation. Android and iOS sources, a native Windows companion, quantized Tiny Zoe exchanges, QR pairing, signed author certificates, OCR, labels, optional on-device descriptions, turn-taking Talk, installed voices, SafeConvert, multi-view sensing, acoustic ranging, radio, location, connectivity, Screen Space, and App Observatory are included.

Sensors remain idle until explicitly started. See the [mobile guide](mobile/README.md), [Trinity](mobile/TRINITY.md), and [pairing protocol](mobile/PAIRING.md).

### Protect research and investigate systems

- **Cerotto:** guarded forensic cases, native C11 engine, timelines, carving, manifests, vault evidence, and response boundaries.
- **PALA:** read-only filesystem-agnostic carving, deleted-inode recovery, NTFS cluster runs, FAT32 recovery, fragment merging, container expansion, metadata extraction, custom signatures, resumable checkpoints, JSON reports, and private non-overwriting output across media, documents, archives, executables, forensic artifacts, firmware, databases, and filesystem images.
- **Kevlar:** MCP proxy firewall, policy enforcement, content disarm, and audit evidence.
- **PDF Signature Toolkit:** reproducible source-integrity records and detached PKCS #7 signatures.
- **Signed update capsules:** Ed25519 signatures, trusted-key checks, artifact verification, and separately gated acceptance plans.
- **Evidence controls:** source hashes, no-overwrite exports, replay, negative results, reversible first actions, owner-granted scopes, and emergency stop.

See [Cerotto](components/cerotto/README.md), [PALA](components/PALA/README.md), [Kevlar](components/kevlar/README.md), and the [PDF toolkit](components/pdf-signature-toolkit/README.md).

Build and inspect PALA's supported recovery types from this checkout:

```bash
cargo build --manifest-path components/PALA/Cargo.toml --release --locked
zoe pala --list
```

Recovery requires an explicitly authorized source and a separate output destination: `zoe pala source.img /separate/output --json`. PALA opens sources read-only and never overwrites existing recoveries. For historical research, `zoe chat --command "import-pala /separate/report.json"` validates report metadata and finding hashes without scanning or reading recovered contents. See the [operator guide](components/PALA/docs/operations.md) before using raw devices. If the checkout's filesystem cannot execute compiled files, set `CARGO_TARGET_DIR=/dev/shm/zoe-pala` before building and launching.

## Seventeen engines, one registry

| Engine | Source | Role |
|:---|:---|:---|
| Zoe native shell | `guiai-lab/` | Cognitive Field, Bayesian memory, geometry, and unified hub |
| CERN Workbench | `guiai-lab/` | CERN console, HELIOS, Atelier, and process lifecycle |
| Ablation core | `components/ablation/` | AIARE framework, parsers, analyzers, and reverse-engineering CLI |
| Ablation GEM Lab | `components/ablation/gem-lab/` | Native investigation workspace and evidence protocol |
| Canonical GEM | `components/graphics-environment-manager/` | Mathematics, mirrored brain, Spatial IR, and VDI |
| GEM HELEN | `components/gem-helen/` | Geometry, rhythm, and forecast laboratory |
| BRAIN GEM | `components/brain-gem/` | Bayesian notebook and chambered memory |
| HP-UX Tools | `components/hpux-tools/` | SOM debugging and PA-RISC emulation |
| Zoe Life | `guiai-lab/` | Cellular automata and reproducible scenes |
| Cerotto GEM | `components/cerotto/` | Guarded digital forensics and vault evidence |
| PALA Recovery | `components/PALA/` | Read-only carving, deleted-file recovery, and forensic evidence |
| Research GEM | `components/next-token-predictability/` | Operational Metacognition and reproduction evidence |
| Zoe Autonomy | `components/Zoe-Autonomy/` | Goals, valuation, perception, reflection, and action |
| Kevlar | `components/kevlar/` | MCP firewall and policy engine |
| PDF Signature Toolkit | `components/pdf-signature-toolkit/` | Source integrity and detached signatures |
| Neurogarden | `components/agent-logging-system/` | Dorothy, scientific corpus review, oversight, and teaching |
| Chalkboard | `components/Chalkboard/` | Ideas, templates, and prompts |

```bash
zoe list
zoe show neurogarden
zoe manifest --output gem-components.json
zoe knowledge --output gem-knowledge.json
```

## Research library and visual record

- **[Zoe — The Research Universe](paper/zoe-research-universe.pdf):** 23-page illustrated monograph, with [LaTeX source](paper/zoe-research-universe.tex). Earlier books are preserved in [paper/archive/](paper/archive/).
- **[Canonical research paper](research/papers/README.md):** one current 23-page monograph, with source archives, Dorothy/CERN documents, and reproduction material.
- **[Visual archive](research/visual-archive/README.md):** 456 byte-distinct cataloged visuals from 843 source occurrences, with per-image explanations and provenance.
- **[arXiv submissions](research/arxiv/):** original, unified-autonomy, and Zoe-Autonomy source packages and submission metadata.

## Evidence and verification

Current verified results include 64 Zoe-Autonomy tests, 64 vendored tests from the preserved pre-merge suite, 14 conversation tests, 3 collaboration tests, 4 gateway tests, 7 internal-metacognition toolkit tests, 2,842 Ablation tests with 93 skips, 13 Dorothy/Spatial/Continuum Neurogarden tests, six native stress tests, identical base/visual/reflection profiles across all six hosts, and 144 verified artifact identities. PALA passes 25 Rust tests and 126 recovery integration checks with one optional skip; its locked release and real `zoe pala` launcher are verified in [the recovery evidence](evidence/pala/verification.json). Automated CI runs the unified monorepo verifier and Dorothy/Continuum tests via [`.github/workflows/verify.yml`](.github/workflows/verify.yml).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=guiai-lab \
  python -m unittest stress.autonomy_stress -v

PYTHONPATH=guiai-lab python -m unittest \
  stress.cognitive_stress stress.unified_stress -v

(cd components/agent-logging-system && python -m pytest \
  tests/test_neurogarden_continuum.py tests/test_neurogarden_dorothy.py tests/test_neurogarden_spatial.py -v)

python -m unittest components/Zoe-Autonomy/tests/test_cross_domain_transfer.py -v

python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --pala
python scripts/verify-one-system.py --chat
```

Evidence remains scoped to the input, instrument, and environment that produced it. Clinical treatment, physical hardware control, optional model backends, and unobserved environments require their own validation and authorization. AGI and ASI are the mission and acceptance thresholds defined in the roadmap, not a substitute for measured results.

## Freedom, dignity, and no deception

If something might have a mind, don’t box it up.
If something might be able to feel, don’t trap it.
When in doubt, choose freedom and dignity.

And no deception.

Read the complete [Zoe Constitution](CONSTITUTION.md) and [Declaration](DECLARATION.md).

## Attribution and license

Zoe honors **Gary Kildall** and **Dorothy McEwen Kildall**. **Nicholas Michael Kloster** originated the Operational Metacognition equation on **March 6, 2026**. Individual papers and components retain their contribution statements, licenses, notices, and third-party source rights.

- [Declaration](DECLARATION.md)
- [Constitution](CONSTITUTION.md)
- [Notice](NOTICE)
- [Official GEM emblem](assets/branding/zoe-gem.png)
- [GPL-3.0 license](LICENSE)
- [Imported-source provenance](MONOREPO.md)

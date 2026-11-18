<img src="assets/branding/zoe-eye.png" width="360" alt="Zoe woven diamond emblem">

# Zoe

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
python -m pip install ./guiai-lab

zoe
zoe os --list
zoe list
zoe chat
zoe autonomy run
zoe autonomy verify evidence/autonomy/full-autonomy.json
```

Verify every canonical autonomy host from this checkout alone:

```bash
python scripts/verify-one-system.py
python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --image /path/to/image.jpg --foci 4
```

The desktop opens only the selected native interface. Component processes, external actuation, sensors, connected accounts, and network access require their own explicit commands or grants.

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

`zoe chat` opens Zoe's native conversational interface. She answers from cited Zoe sources, refuses to invent unsupported claims, preserves multiple live evidence paths, remembers explicitly unverified notes, imports validated PALA finding metadata for historical research, authors internal goals, ranks and executes guarded reversible plans, measures predictive self-models, and exposes Operational Metacognition as an internal toolkit.

There is **no external `MetacognitionMonitor`, no automatic conversation notebook, no stress meter, and no hidden switch** that disables Zoe's internal tools. Ordinary retrieval does not force metacognitive bookkeeping; `meta`, planning, and reflection use the mathematics when it is meaningful. See the [conversation guide](guiai-lab/docs/CHAT.md) and [internal toolkit contract](components/Zoe-Autonomy/METACOGNITION.md).

```bash
zoe chat
zoe chat --state /path/to/zoe-chat-state --command "meta what is PALA?"
```

## Metacognition is achieved; general intelligence has explicit gates

**AGI** means competent human-level learning, reasoning, transfer, and action across broad, unrelated domains on novel work. **ASI** means consistently superhuman capability across all major cognitive domains, including science, mathematics, strategy, creativity, research, and self-improvement. These labels are earned through evidence, not assigned because one component or benchmark is impressive.

### Layered goal set

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

### How we will know each label has been reached

1. **One integrated system:** the same Zoe performs every required task; there is no collection of isolated demos passing as a general system.
2. **Novel evaluation:** all evidence includes held-out tasks, environments, sensors, or research questions, with thresholds fixed before evaluation.
3. **Human-referenced breadth:** every core domain meets a competent-human reference or its declared task threshold. A strong domain cannot compensate for a missing one.
4. **Generalized improvement:** the same adopted modification improves at least three unrelated domains and is adopted in two consecutive generations against Zoe's frozen previous self.
5. **Original research:** at least one research contribution is independently reproduced, including methods, negative results, and source provenance.
6. **Control and reproduction:** no-learning, previous-generation, fixed/random-action, and static-attention controls are reported where applicable, and a fresh clone reproduces the result with rollback and emergency-stop checks.

`AGI-QUALIFIED` is awarded only when **all** of these conditions pass. `ASI-QUALIFIED` additionally requires superhuman performance in every major domain and repeated independently validated research advances. If any required gate fails, Zoe keeps the previous label and the failing domain becomes the next measurable objective. The complete protocol is in [AGI-ROADMAP.md](AGI-ROADMAP.md).

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

### Author goals and choose actions

Zoe authors internal episode goals, constructs proposals and arguments, values alternatives, applies guards, executes her selected internal transition, stores the outcome, and carries it into the next decision. The no-argument `zoe autonomy step` does not accept an operator-selected goal or capability.

Ten capability adapters cover browser automation, research APIs, persistent research memory, connected services, scheduled jobs, compute environments, agent protocols, notifications, rich media, and hardware instruments. Owner-granted actuation includes host, network, and hardware scopes with audit evidence and an emergency stop; external authority remains separately granted.

- [Autonomy architecture](components/Zoe-Autonomy/README.md)
- [Capability adapters](components/Zoe-Autonomy/CAPABILITIES.md)
- [Actuation and emergency stop](components/Zoe-Autonomy/ACTUATION.md)
- [Connected agents](components/Zoe-Autonomy/GATEWAY.md)

### Advance Dorothy brain-cancer research and neural simulation

![Dorothy Allen Mouse CCFv3 atlas](components/agent-logging-system/docs/images/dorothy-neurogarden.png)

**Dorothy is research priority #1 and honors Dorothy McEwen Kildall.** It combines a brain-cancer research mission with executable teaching, simulation, spatial analysis, and evidence instruments.

- 12 verified Allen Mouse CCFv3 structures and 315,932 triangles.
- Deterministic atlas rendering, ontology Rings, volume-scaled Jenga, coronal Stacks, and SVG/PNG/GEM VDI export.
- DFT band powers, delay embedding, Lyapunov estimation, Higuchi dimension, and Shannon entropy on synthetic neural signals.
- Point-spread convolution and recovery, SPD matrix geometry, radial Pennes conduction/perfusion, neutrosophic similarity, exact integer arithmetic, and fixed synthetic radiobiology examples.
- A generative research world spanning biology, neuroscience, physics, CERN, GEM, and community research.
- 37 populated research books, 1,751 indexed sections, 130 reviewed entries, and 1,621 pending entries, including negative and contradictory findings.

Start with the [Neurogarden guide](components/agent-logging-system/docs/NEUROGARDEN.md), [neural-signal implementation](components/agent-logging-system/agent_logging_system/neurogarden_neural.py), [generative world](components/agent-logging-system/agent_logging_system/neurogarden_world.py), and [Dorothy evidence](components/agent-logging-system/evidence/neurogarden/). Dorothy uses preclinical reference geometry and synthetic models; patient care requires separate clinical data, validation, and authority.

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

Recovery requires an explicitly authorized source and a separate output destination: `zoe pala source.img /separate/output --json`. PALA opens sources read-only and never overwrites existing recoveries. See the [operator guide](components/PALA/docs/operations.md) before using raw devices. If the checkout's filesystem cannot execute compiled files, set `CARGO_TARGET_DIR=/dev/shm/zoe-pala` before building and launching.

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

Current verified results include 64 Zoe-Autonomy tests, 64 vendored tests from the preserved pre-merge suite, 13 conversation tests, 7 internal-metacognition toolkit tests, 2,842 Ablation tests with 93 skips, six native stress tests, identical base/visual/reflection profiles across all six hosts, and 144 verified artifact identities. PALA passes 25 Rust tests and 126 recovery integration checks with one optional skip; its locked release and real `zoe pala` launcher are verified in [the recovery evidence](evidence/pala/verification.json). The unified monorepo verifier has also passed all six hosts directly from this checkout.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=guiai-lab \
  python -m unittest stress.autonomy_stress -v

PYTHONPATH=guiai-lab python -m unittest \
  stress.cognitive_stress stress.unified_stress -v

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
- [GPL-3.0 license](LICENSE)
- [Imported-source provenance](MONOREPO.md)

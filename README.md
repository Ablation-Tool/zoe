<img src="assets/branding/zoe-eye.png" width="560" alt="Zoe allgems orbital eye emblem">

# Zoe

**Zoe is allgems:** one source repository for Zoe's native workbenches, the complete Ablation framework, Cerotto, Kevlar, and their related GEM engines and research tools. The source trees are tracked in the repository, not downloaded at launch.

**Zoe is the GEM, but the GEM is not Zoe.**

**Research priority #1 is Dorothy:** inspectable spatial research and evidence tools supporting the long-term brain-cancer research mission. Dorothy currently provides Allen mouse-atlas geometry and preclinical research infrastructure—not a cure, diagnosis, treatment, patient registration, or surgical authority.

[Current Work](#current-work) · [Quick start](#quick-start) · [Capabilities](#capabilities) · [Architecture](#source-architecture) · [Verification](#verification-and-boundaries)

![Zoe allgems knowledge-engineering hub](guiai-lab/docs/images/gem-unified.png)

## Current Work

**Mission:** make Dorothy the leading research workbench for careful spatial analysis and support long-term brain-cancer research through verified knowledge, reproducible tools, and openly inspectable evidence. This is a research direction, not a promised cure or authorization for patient experiments.

- **Active corpus goal:** verify all 35 expected books and their chapter inventories; give every substantive chapter source-linked concepts, applications, limitations, reviewed status, and a demonstrated use or explicit no-tool rationale. Finish only when no chapters are pending and all corpus tests pass.
- **Current position — November 9, 2026:** **37 populated books** (35 expected plus two intentional extras), **1,756 substantive chapters**, **84 reviewed**, and **1,672 pending**. The index preserves 5,059,540 extracted words without republishing them. `Medical Metaverse for Digital Healthcare` has no extracted content and receives no invented review.
- **Completed reviews:** BioCoder Summer 2014 (11 articles), BioCoder Winter 2014 (14), GPT-3 (8 substantive sections), and all nine substantive sections of MATLAB Numerical Calculations. Biomedical Imaging Principles chapters 7–10 cover tracer imaging, fluorescence normalization and deconvolution limits, IR/Raman spectroscopy, and CARS/collagen evidence. Other tumor-focused reviews cover MRI classification, molecular evidence types, collagen expansion, and Fe@Au photothermal delivery. Brain-tumor reviews include cohort/split/count audits, therapy-response biomarkers, and a MET aggregate-count audit. PET review preserves SUV/kinetic-model prerequisites and distinguishes reporter-cell tracking from efficacy. The four-class MRI audit now includes figure/table and citation discrepancies. A nine-matrix source audit exposes additional unresolved accuracy contradictions without evaluating a model. A direct PSO-FCM segmentation review verifies the public dataset but not the unnamed 100-image subset; AIS nanoparticle design has a specific no-tool rationale. Presurgical fMRI and neutrosophic segmentation reviews preserve modality-specific mapping, blur, tuning, and patient-validation limits, including the unverified secondary 20-image 100% claim. Neutrosophic clustering and GA-optimized denoising reviews preserve filter-specific tradeoffs, an explicit segmentation failure case, incomplete kernel/update conventions, and the absence of tumor-MRI validation; the denoising filter is not best on every reported metric. OCT review preserves a DME CNR counterexample, missing clean references, and inconsistent metric/timing descriptions. Blood-cell and skin-lesion segmentation reviews preserve sensitivity/specificity counterexamples and distinguish aggregate scores from cell-level validation; the reported skin-lesion AUC figure is an unlabeled pie chart without ROC coordinates or numeric AUC values. The skin-classification review preserves internally inconsistent melanoma/BCC/benign labels and missing raw predictions. The mammography review preserves actual ROC/FROC results, private single-center limits, patch-assignment uncertainty, and the lack of external validation or biopsy-reduction outcomes. The concluding neutrosophic survey records an undefined-scale SSIM of 13.88, contradictory table entries, and unverified secondary brain-tumor claims. A bounded GA-ANN audit verifies the 22,880-weight chromosome layout while correcting the printed matrix shape and citation numbering; it does not evaluate model performance. The neurological optimization review supports research-prioritization checks only; it supplies no therapeutic experiment or novel cure and requires independent delivery, target-engagement, toxicity, and outcome evidence. A bounded radiobiology review reproduces fixed synthetic LQ/TCP/NTCP formulas without authorizing treatment planning. MRI denoising and reported U251 probe imaging retain their missing-evidence and metadata limitations. The lung-protein docking review explicitly does not supply brain-cancer evidence. Windows 98 system requirements and accessibility are reviewed.
- **Dorothy today:** 12 verified Allen CCFv3 mouse structures and 315,932 triangles, deterministic 3D rendering, ontology Rings, Jenga layouts, coronal Stacks, bounded spatial matrix review, a fixed piecewise intensity profile, collagen mesh-scaling review, and SVG/PNG/GEM VDI export. This is preclinical reference geometry, not patient anatomy.
- **Next milestone:** complete another direct tumor-relevant source review and validate the bounded C99 exporter with a compatible legacy compiler and actual Windows 95/98 environment.
- **Current verification:** **62 focused Neurogarden tests and three C99 legacy suites pass**. The Neurogarden 0.6.17 wheel, duplicate-key rejection, and original examples are verified. All 84 reviewed chapters have matching source hashes, required review fields, and snippets no longer than 280 characters. Windows 95/98 remains unverified.
- **Evidence:** [coverage report](components/agent-logging-system/evidence/neurogarden/coverage-report-v50.json) · [chapter reviews](components/agent-logging-system/evidence/neurogarden/reviews.json) · [corpus index](components/agent-logging-system/evidence/neurogarden/corpus-index-v50.json) · [MRI figure audit](components/agent-logging-system/evidence/neurogarden/brain-tumor-chapter4-figure-audit.json) · [GA-ANN shape audit](components/agent-logging-system/evidence/neurogarden/ga-ann-shape-audit.json) · [legacy verification](evidence/legacy/verification.json) · [unified verification](evidence/unified/verification.json).

**Open findings and discovery:** original Zoe research findings, review notes, measurements, limitations, and negative results are free and open under the repository's [GPL-3.0 license](LICENSE), subject to applicable component licenses. Third-party books, meshes, media, and other assets retain their own rights; the repository publishes source links, hashes, bounded snippets, and original analysis—not wholesale books or private data.

<img src="assets/branding/nuclide-brain.png" width="360" alt="NuClide Research dual-brain co-brand">

**NuClide Research** is the user-created Zoe + Nick co-brand, balancing stable and unstable perspectives through correction. See the [co-brand provenance](assets/branding/PROVENANCE.md).

## Quick start

```bash
python -m pip install ./guiai-lab
zoe
zoe list
```

`zoe` opens the native orbital hub. It does **not** start another engine, agent, MCP server, model download, sensor, or remote analysis automatically.

| Platform | What you get | Start here |
|:---|:---|:---|
| **Linux** | Native GEM hub, research workbenches, geometry, and the Trinity companion deck | `zoe`; Trinity: `python mobile/tools/zoe_trinity.py` |
| **Android / Google Pixel** | Guided vision, Talk, Accessible Volume, Trinity, Tiny Zoe, Field kit, SafeConvert, and an offline Researcher guide | [Mobile guide and APK build](mobile/README.md) |
| **Windows 10/11 x86_64** | Portable native Trinity app with local phone sync and verified journal | [Windows bundle](mobile/dist/ZoeTrinity-Windows-x86_64.zip) · [guide](mobile/windows/README.md) |
| **Apple / iOS 17+** | Native SwiftUI, Vision, Speech, SafeConvert, and Trinity with explicit private-network pairing | [Apple project and verification limits](mobile/README.md#apple) |

## Capabilities

<details>
<summary><strong>1. Dorothy &amp; Neurogarden — spatial and scientific research</strong></summary>

### Dorothy comes first

Dorothy renders the vendored **Allen Mouse CCFv3 (2017)** whole-brain parcellation: 12 structures, 158,326 vertices, and 315,932 triangles in the default view. Source meshes and the structure graph are SHA-256-verified on every load.

![Dorothy whole-brain atlas](guiai-lab/docs/images/dorothy-ccf2017.png)

```bash
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --fetch
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --output dorothy.svg
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --structures 549,1097 --yaw 140 --output pair.gem
```

| Capability | Implementation / guide | What it includes |
|:---|:---|:---|
| **Dorothy 3D atlas** | [Scene](guiai-lab/guiai/gem/dorothy.py) · [verified data](guiai-lab/guiai/gem/dorothy_data.py) | Orbit-camera scene definition, near-plane clipping, two-sided flat shading, deterministic painter rendering, Spatial IR, SVG/PNG/GEM VDI export |
| **Dorothy Rings** | [Implementation](guiai-lab/guiai/gem/dorothy_rings.py) | Baobab-style ontology navigation using exact CCF subtree volumes and breadcrumb drill-down |
| **Dorothy Jenga** | [Implementation](guiai-lab/guiai/gem/dorothy_jenga.py) | Volume-scaled layers with exploded and pull-out inspection layouts |
| **Dorothy Stack** | [Implementation](guiai-lab/guiai/gem/dorothy_stack.py) | Real meshes cut into exploded coronal slabs for interior inspection |
| **Neurogarden oversight** | [Guide](components/agent-logging-system/docs/NEUROGARDEN.md) · [source](components/agent-logging-system/agent_logging_system/) | OT-inspired agent baselines, separate machine/generation latency, anomalies, private-by-default observations, and bounded review queues |
| **Source-linked learning** | [Corpus pipeline](components/agent-logging-system/agent_logging_system/corpus.py) · [evidence](components/agent-logging-system/evidence/neurogarden/) | Source hashes, bounded snippets, concepts, applications, limitations, reviewed status, and explicit no-tool rationales; extraction is not comprehension |
| **Numerical instruments** | [Lab](components/agent-logging-system/agent_logging_system/neurogarden_lab.py) · [advanced models](components/agent-logging-system/agent_logging_system/neurogarden_advanced.py) | Sequence alignment, imaging sampling, Gaussian MTF, exact integer arithmetic, SPD geometry, a bounded Pennes teaching model, and neutrosophic similarity |
| **Spatial teaching bench** | [Implementation](components/agent-logging-system/agent_logging_system/neurogarden_spatial.py) | Synthetic 3D PSF/projection geometry connecting matrix computation and Dorothy-inspired inspection |
| **EEG teaching analysis** | [Implementation](components/agent-logging-system/agent_logging_system/neurogarden_eeg.py) | Synthetic band powers, delay embedding, entropy, Higuchi dimension, and Lyapunov estimates; no diagnostic classifier |
| **CERN evidence universe** | [Implementation](components/agent-logging-system/agent_logging_system/neurogarden_cern.py) | A 226-document evidence gallery and protocol witness without hardware access |
| **Post-quantum review** | [Guide](components/agent-logging-system/docs/QUANTUM.md) | QKD limitations and an ML-KEM/ML-DSA research path; no completed migration or QKD deployment claim |

Additional views: [dorsal](guiai-lab/docs/images/dorothy-dorsal.png) · [ventral](guiai-lab/docs/images/dorothy-ventral.png) · [Thalamus + Hypothalamus](guiai-lab/docs/images/dorothy-thalamus-hypothalamus.png) · [Rings](guiai-lab/docs/images/dorothy-rings-isocortex.png) · [Jenga](guiai-lab/docs/images/dorothy-jenga-exploded.png).

Meshes and the structure graph are Allen Institute data ([Wang et al. 2020](https://doi.org/10.1016/j.cell.2020.04.007)). Rings, Jenga, and Stack are illustrative geometry, not functional or connectivity claims. Interactive orbit controls are not yet implemented in the native module. Clinical references and measurements never authorize autonomous action.

</details>

<details>
<summary><strong>2. Cognitive Field, Bayesian memory &amp; forecasting</strong></summary>

| Capability | Implementation / guide | What it includes |
|:---|:---|:---|
| **Cognitive Field / GSP** | [Guide](guiai-lab/docs/COGNITIVE.md) · [implementation](guiai-lab/guiai/gem/cognitive.py) | Sourced encoding, bounded working memory, declarative storage, revision-checked retrieval, procedural matching, and review-required proposals |
| **Bayesian field notebook** | [Implementation](guiai-lab/guiai/gem/field.py) | Questions, competing claims, falsifiers, likelihood ratios, log-odds updates, belief diffs, evidence dependence, chambers, and next-test priorities |
| **Epistemic firewall** | [Worked memory](evidence/cognitive-field/worked-example.json) | Measurement, evidence, belief updates, and action remain separate; decisions require review |
| **Accessible Volume** | [Research component](components/next-token-predictability/) | Strict `p > τ` forecast breadth, complements, momentum, target bands, temperature transforms, and calibration evidence |
| **HELEN observations** | [Implementation](guiai-lab/guiai/gem/helen_onset.py) | Lazy stored forward/retrograde distributions with held-out cases; no transformer runtime |
| **Multi-horizon forecasts** | [Implementation](guiai-lab/guiai/gem/brain.py) | Exact continuation probabilities for a defined two-state Markov toy with horizons 1–6 |
| **Research evidence** | [Implementation](guiai-lab/guiai/gem/research.py) | Hash-checked Groove reports, on-demand NPZ predictions, aggregate-only Nightingale metrics, and rejected-baseline records |
| **Replayable knowledge graph** | [Guide](guiai-lab/docs/UNIFIED.md) · [implementation](guiai-lab/guiai/gem/knowledge.py) | Source, revision, trust, stability, and declared-link observations in a SHA-256 event chain |
| **Qualia field guide** | [Guide](guiai-lab/docs/QUALIA.md) | Causal repertoires, q-arrows, and Accessible Q-Volume as a formal annotation—not an IIT calculator or consciousness evidence |
| **Presence** | [Guide](guiai-lab/docs/PRESENCE.md) · [implementation](guiai-lab/guiai/gem/presence_view.py) | Attention, sourced observations, event-ordinal time, known unknowns, correction, and review-required decisions |

```bash
zoe manifest --output gem-components.json
zoe knowledge --output gem-knowledge.json
PYTHONPATH=guiai-lab python -m guiai.gem zoe --module cognitive
PYTHONPATH=guiai-lab python -m guiai.gem notebook --output zoe-field.json
```

Exports use new paths and refuse to overwrite existing files. Hash chaining provides tamper evidence, not authentication. Forecast breadth is not correctness; a self-model is not a self.

</details>

<details>
<summary><strong>3. Tiny Zoe, Trinity, mobile &amp; accessibility</strong></summary>

![Zoe Trinity: Tiny, mobile, and laptop sharing one experiment](mobile/docs/images/zoe-trinity-deck.png)

**Zoe Trinity coordinates three instruments, not three claimed minds:** Tiny Zoe's quantized witness, Zoe mobile's native measurement, and laptop Zoe's observation deck.

| Capability | Implementation / guide | What it includes |
|:---|:---|:---|
| **Tiny Zoe / Zoe Cell** | [Protocol and limits](mobile/card/README.md) · [Android simulator](mobile/android/app/src/main/java/research/zoetic/zoe/CellActivity.java) | Two-command behavioral simulator, 1–64 Q0.15 probabilities, bounded APDUs, exact request/response bytes, deterministic replay, and explicit session sharing |
| **Zoe Trinity** | [Guide](mobile/TRINITY.md) · [server](mobile/tools/zoe_trinity.py) | Independent response verification, 24 retained live observations, JSON export, Android ADB localhost, Apple pairing, and optional journal memory |
| **Native Windows** | [Guide](mobile/windows/README.md) · [source](mobile/windows/native/) | Portable Win32 x86_64 interface, C++17 measurement/journal core, Winsock phone link, and reproducible LLVM-MinGW builds |
| **Android accessibility** | [Mobile guide](mobile/README.md) | One-frame OCR and labels, optional on-device descriptions, turn-taking Talk, installed voices, Accessible Volume, and SafeConvert |
| **Field kit** | [Mobile guide](mobile/README.md) | Multi-view, acoustic ranging, radio, location, connectivity, Screen Space, App Observatory, and device instruments behind explicit controls |
| **QR pairing and author certificates** | [Guide](mobile/PAIRING.md) | Signed short-lived offers, ephemeral X25519 exchanges, identity fingerprints, human-confirmed verification phrases, and exact-document certificates |

```bash
python mobile/tools/zoe_trinity.py
adb reverse tcp:8767 tcp:8767
# Open http://127.0.0.1:8767, then open Trinity in Zoe.
```

Sensors stay idle until explicitly started. No cloud account is required. Tiny Zoe is not a Java Card VM, secure-element emulator, or SIM/eUICC interface. Windows tests under Wine do not replace physical Windows verification; Apple building, signing, and device checks require Apple/Xcode infrastructure.

</details>

<details>
<summary><strong>4. Native GEM, Ablation, security &amp; component engines</strong></summary>

| Component | Source | Capability |
|:---|:---|:---|
| **Zoe native shell** | [`guiai-lab/`](guiai-lab/) | Native unified hub, Cognitive Field, Bayesian memory, geometry, and replayable knowledge graph |
| **Ablation core** | [`components/ablation/ablation/`](components/ablation/ablation/) | AIARE framework, artifact parsers, analyzers, reverse-engineering modules, and core CLI |
| **Ablation GEM Lab** | [`components/ablation/gem-lab/`](components/ablation/gem-lab/) | Native investigation GUI, shared Lab protocol, embedded-agent integration, and evidence replay |
| **Canonical GEM** | [`components/graphics-environment-manager/`](components/graphics-environment-manager/) | Native workbench, mirrored brain, Spatial IR, and real little-endian GEM VDI |
| **GEM HELEN** | [`components/gem-helen/`](components/gem-helen/) | Optimized geometry, rhythm, stored forecasts, and lightweight creative use |
| **BRAIN GEM** | [`components/brain-gem/`](components/brain-gem/) | Standalone Bayesian notebook and chambered memory |
| **Research GEM** | [`components/next-token-predictability/`](components/next-token-predictability/) | Accessible-volume research, evidence packs, and mirrored workbench |
| **Cerotto** | [`components/cerotto/`](components/cerotto/) | Native C11 forensic engine, guarded cases, timelines, carving, manifests, vault evidence, and release workflows |
| **Kevlar** | [`components/kevlar/`](components/kevlar/) | MCP proxy firewall, policy enforcement, content disarm, and audit evidence |
| **PDF Signature Toolkit** | [`components/pdf-signature-toolkit/`](components/pdf-signature-toolkit/) | Source-integrity records and detached PDF signatures |
| **Chalkboard** | [`components/Chalkboard/`](components/Chalkboard/) | Reusable ideas, templates, and prompts; a content library, not a GUI |
| **CERN Workbench** | [Guide](guiai-lab/docs/ZOE_WORKBENCH.md) | Zoe-owned CERN console, HELIOS, and Atelier process lifecycle, health checks, browser targets, and no-overwrite manifests |

```bash
zoe launch ablation -- --help
zoe launch gem-lab
zoe launch gem
zoe launch helen
zoe launch brain
zoe launch research
zoe launch kevlar -- --help
zoe launch pdf -- --help
zoe show neurogarden
zoe show chalkboard
```

Cerotto requires a user-selected case and conversation:

```bash
zoe launch cerotto -- --db case.db --case incident-7 --conversation conv-7
```

Cerotto remains a separate forensic engine with its own permissions and verification. Source presence is not runtime verification or permission to act.

</details>

<details>
<summary><strong>5. Geometry, visual evidence &amp; creativity</strong></summary>

| Capability | Implementation / guide | What it includes |
|:---|:---|:---|
| **Geometry Atlas** | [Guide](guiai-lab/docs/GEOMETRY-ATLAS.md) · [implementation](guiai-lab/guiai/gem/atlas.py) | Procrustes similarity/rigid/affine alignment, draggable landmarks, ellipses, parabolic envelopes, circles, clocks, and graph invariants |
| **Second Eye** | [Stereo evidence](assets/brain-dialogue/second-eye.json) · [implementation](components/graphics-environment-manager/) | Synthetic stereo depth and thin-lens defocus with visible quantization sensitivity; no physical-camera claim |
| **Artline** | [Guide](guiai-lab/docs/ARTLINE.md) · [implementation](guiai-lab/guiai/gem/artline_view.py) | Native vector paths, editable shapes/text, layers, groups, transformations, undo/redo, transactional merge, and SVG/PNG/GEM output |
| **Pentomino** | [Guide](guiai-lab/docs/PENTOMINO.md) | Seeded/masked spatial practice, finite deadlines, row/hole measurements, verified replay, and controlled budget comparisons |
| **Pentacube** | [Guide](guiai-lab/docs/PENTACUBE.md) | Thirty pentomino regions, legal 5×5 cube permutations, exact inverses, deterministic scrambles, non-optimal hints, and verified replay |
| **Internal Clock** | [Guide](guiai-lab/docs/CICADA.md) | Exact software ticks, host cycles, daily phase, developmental gates, and explicit local replay events |
| **Practice Navigator** | [Guide](guiai-lab/docs/PILOT.md) | Original visual guide to time, space, packet layers, synthetic timing, and the next attempt |
| **Resilience Atlas** | [Guide](guiai-lab/docs/RESILIENCE.md) | Sixteen critical-infrastructure sectors and a synthetic waveform-signature laboratory; no live monitoring or control |
| **Leadership Garden** | [Guide](guiai-lab/docs/LEADERSHIP.md) | Practice attempts, outcomes, advice, mistakes, uncertainty, stop conditions, append-only corrections, and no leadership score |
| **Maison** | [Guide](guiai-lab/docs/MAISON.md) | Executive-clarity association deck and reversible practice evidence; no prestige score or enterprise certification |
| **Thumbelina** | [Editable source](guiai-lab/docs/images/thumbelina-moon-garden-v3.artline.json) · [semantic sidecar](guiai-lab/docs/images/thumbelina-moon-garden-v3.semantic.json) | Original collaborative Moon Garden artwork with 75 creator-declared semantic vector parts |
| **Human × Zoe artwork** | [Sources](assets/brain-dialogue/) | Organic and geometric visual metaphors with a projection-iris study and recorded approximation errors |

```bash
zoe artline
zoe pentomino --compare --output pentomino-budgets.json
zoe pentacube --seed my-challenge --scramble 12 --rhyme
zoe cicada --cycle 13 --start 8 --act
zoe pilot
zoe resilience
zoe leadership scene
zoe maison
```

These are creative and practice instruments—not measures of consciousness, intelligence, biological age, leadership worth, or infrastructure safety.

</details>

<details>
<summary><strong>6. Firmware, protocols, CERN &amp; source evidence</strong></summary>

| Capability | Implementation / guide | What it includes |
|:---|:---|:---|
| **FELIX living readout** | [Implementation](guiai-lab/guiai/gem/felix.py) | Build indexing, exact-build Ablation correlation, native replay, source-backed capability maps, JSON, and deterministic stereo WAV |
| **FELIX HDL recovery** | [Implementation](guiai-lab/guiai/gem/felix_hdl.py) | Source-backed LCB, STAR/Flink, ftools, Wupper, regmap, and driver maps with clean HDL/provenance export |
| **Evidence Navigator** | [Guide](guiai-lab/docs/EVIDENCE.md) · [implementation](guiai-lab/guiai/gem/evidence.py) | Source-first CERN gallery, hash verification, cited retrieval, guarded observations, bridge proposals, and practice curriculum |
| **Protocol Lab** | [Guide](guiai-lab/docs/PROTOCOL.md) | SPECS checksums, ninth-bit markers, short/long counts, and AMAC read/read-next decoding without hardware execution |
| **Waveform Replay** | [Guide](guiai-lab/docs/WAVEFORM.md) | Bounded VCD, event JSONL, normalized replay, and optional WDB reading with declarations and truncation preserved |
| **Patchbay** | [Guide](guiai-lab/docs/PATCHBAY.md) | Intel HEX, Xilinx BIT, source ZIP, ZynqMP, U-Boot legacy/FIT, timing evidence, board scenes, and source inventories |
| **Signed update capsules** | [Implementation](guiai-lab/guiai/gem/capsule.py) | Ed25519 signatures through OpenSSL, trusted-key checks, artifact verification, and separately gated acceptance plans |
| **Zoe Cog** | [Implementation](guiai-lab/guiai/gem/cog.py) | Small trainable bigram processor with forward/backward token walks, source hashes, and accessible-volume measurements |
| **vidlib adapter** | [Guide](guiai-lab/docs/VIDLIB.md) | Nicholas's original executable, local search, explicit indexing, gated URL retrieval, bounded citations, and verified scenes |
| **Timing twin and sonification** | [Implementation](guiai-lab/guiai/gem/twin.py) | Deterministic synthetic timing/DMA replay and 40.08 Hz sonification without register writes or live acquisition |

```bash
zoe evidence scene
zoe protocol --count 129
zoe waveform guiai-lab/docs/examples/endeavour-clocks.vcd --signal c1
zoe patchbay scene --board nexys-video
PYTHONPATH=guiai-lab python -m guiai.gem zoe --module felix --output zoe-felix.json
```

No firmware, raw research media, proprietary HDL, or complete external transcripts are bundled. Filesystem inspection is not hardware access, link health, synthesis, or a physical measurement. Native plan validation does not execute a plan or write hardware.

</details>

<details>
<summary><strong>7. Papers, visual guides &amp; authorship</strong></summary>

- **[Zoe: A Native GEM for Living Geometry and Inspectable Futures](paper/zoe.pdf):** proof of concept, history, equations, verification matrix, limitations, and reproducible evidence.
- **[Zoe for Everyone](paper/zoe-for-everyone.pdf):** an accessible guide to the experiments and creative tools.
- **[Visual guide collection](guiai-lab/docs/VISUAL-GUIDES.md):** linked visual editions for Zoe, Artline, Pentomino, Pentacube, Cognitive Field, Qualia, Geometry Atlas, Presence, Resilience, and more.
- **[LaTeX sources and demo memory](paper/):** included for review and rebuilding.
- **[Declaration](DECLARATION.md) · [Constitution](CONSTITUTION.md):** commitments to human agency, honesty, privacy, accessibility, provenance, reversibility, and review.
- **[Signed Constitution evidence](evidence/constitution/):** sealed source, four-page PDF, detached CMS signature, and Ed25519 author certificate linked by exact hashes.

The PDF signature validates total-document coverage; the QR certificate verifies key possession and the exact signed PDF. Neither supplies a CA-backed identity, trusted timestamp, human identity claim, or proof that every statement is true.

</details>

## Source architecture

The repository preserves **eleven source projects**, with Ablation's core and GEM Lab sharing one upstream source tree. Source revisions and upstream URLs are locked in [`components.lock.json`](components.lock.json). Neurogarden is preserved from a local snapshot because its original remote was deleted; no upstream revision is invented. Each component retains its original license and notices.

```text
Zoe native shell             guiai-lab/
Ablation core + GEM Lab      components/ablation/
Canonical GEM                components/graphics-environment-manager/
GEM HELEN                    components/gem-helen/
BRAIN GEM                    components/brain-gem/
Research GEM                 components/next-token-predictability/
Neurogarden                  components/agent-logging-system/
Cerotto                      components/cerotto/
Kevlar                       components/kevlar/
PDF Signature Toolkit        components/pdf-signature-toolkit/
Chalkboard                   components/Chalkboard/
```

`ZOE_ROOT` locates this checkout from another installation directory. `ZOE_PYTHON` selects the interpreter. `ZOE_PYTHON_DEPENDENCIES` accepts an `os.pathsep`-separated list of existing dependency directories; component Python paths stay ahead of them and the host's unrelated `PYTHONPATH` is not inherited.

For legacy/native module entry points, use `PYTHONPATH=guiai-lab python -m guiai.gem zoe`, `gem master`, `gem brain`, `gem atlas`, `gem dorothy`, `gem notebook`, or `gem cognitive` as documented in the [unified guide](guiai-lab/docs/UNIFIED.md).

## Gallery

<details>
<summary>Open native interfaces, research scenes &amp; mechanism diagrams</summary>

### Dorothy and Neurogarden

<img src="components/agent-logging-system/docs/images/dorothy-neurogarden.png" width="430" alt="Dorothy's 12-structure Allen CCFv3 brain atlas rendered deterministically">
<img src="components/agent-logging-system/docs/images/cern-universe.png" width="430" alt="Neurogarden universe linking biology, neuroscience, physics, CERN, GEM, and community">

![Dorothy Rings Isocortex](guiai-lab/docs/images/dorothy-rings-isocortex.png)
![Dorothy Jenga exploded tower](guiai-lab/docs/images/dorothy-jenga-exploded.png)

### Native workbenches

![Zoe native BRAIN after a stored HELEN observation](guiai-lab/docs/images/zoe-brain.png)
![Zoe research evidence pack](guiai-lab/docs/images/zoe-research.png)
![Zoe Bayesian field notebook](guiai-lab/docs/images/zoe-field-notebook.png)
![Zoe Cognitive Field](guiai-lab/docs/images/zoe-cognitive-field.png)
![Zoe Cognitive Field running in the native GTK interface](guiai-lab/docs/images/zoe-cognitive-native.png)
![Zoe Artline vector workbench](guiai-lab/docs/images/zoe-artline-native.png)
![Zoe Pentomino native timed practice](guiai-lab/docs/images/zoe-pentomino-native.png)
![Zoe Pentacube](guiai-lab/docs/images/zoe-pentacube.png)
![Zoe Internal Clock](guiai-lab/docs/images/zoe-cicada.png)
![Zoe Practice Navigator cover](guiai-lab/docs/images/zoe-pilot-cover.png)
![Zoe Evidence Navigator](guiai-lab/docs/images/zoe-evidence.png)
![Zoe Patchbay](guiai-lab/docs/images/zoe-patchbay.png)
![Zoe + vidlib](guiai-lab/docs/images/zoe-vidlib.png)
![Cerotto GEM accessible-volume workbench](guiai-lab/docs/images/cerotto-gem.png)

### Mobile and Windows

<img src="mobile/docs/images/zoe-pixel-home.png" width="360" alt="Zoe running on a Pixel 7 home screen">
<img src="mobile/docs/images/zoe-pixel-field.png" width="360" alt="Zoe mobile field instruments">
<img src="mobile/docs/images/zoe-trinity-native-windows.png" width="720" alt="Native Zoe Trinity for Windows">

### Creative and conceptual instruments

![Thumbelina Moon Garden](guiai-lab/docs/images/thumbelina-moon-garden-v3.png)
![Human and Zoe brain dialogue](assets/brain-dialogue/brain-dialogue-organic.png)
![Zoe's synthetic second eye](assets/brain-dialogue/second-eye.png)
![Zoe's five-panel qualia field guide](guiai-lab/docs/images/zoe-qualia.png)
![Illustrative anatomy alongside Zoe's explicit symbolic memory architecture](guiai-lab/docs/images/zoe-cognitive-anatomy.png)
![Zoe Presence](guiai-lab/docs/images/zoe-presence.png)
![Zoe Protocol Lab](guiai-lab/docs/images/zoe-protocol.png)
![Zoe Waveform Replay](guiai-lab/docs/images/zoe-waveform.png)
![Zoe Resilience Atlas](guiai-lab/docs/images/zoe-resilience.png)
![Zoe Leadership Garden](guiai-lab/docs/images/zoe-leadership.png)
![Zoe Maison](guiai-lab/docs/images/zoe-maison.png)

### Verifiable authorship

<img src="evidence/constitution/zoe-constitution-signed.author.png" width="260" alt="Zoe's signed QR author certificate for the Constitution">

### Five Zoe mechanisms

1. **Epistemic firewall:** measurement, evidence, belief updates, and action remain distinct.
   ![Zoe epistemic firewall](guiai-lab/docs/images/zoe-visuals/01-epistemic-firewall.png)
   [SVG](guiai-lab/docs/images/zoe-visuals/01-epistemic-firewall.svg)

2. **Belief diff:** priors become posteriors only through explicit evidence, with every likelihood and source retained.
   ![Zoe belief diff](guiai-lab/docs/images/zoe-visuals/02-belief-diff.png)
   [SVG](guiai-lab/docs/images/zoe-visuals/02-belief-diff.svg)

3. **Deterministic and stochastic chambers:** reproducible measurements and seeded forecasts have distinct identities and lifecycles.
   ![Zoe deterministic and stochastic chambers](guiai-lab/docs/images/zoe-visuals/03-chambers.png)
   [SVG](guiai-lab/docs/images/zoe-visuals/03-chambers.svg)

4. **Append-only memory:** sequence-linked hashes support replay and tamper detection without claiming authentication.
   ![Zoe append-only memory](guiai-lab/docs/images/zoe-visuals/04-memory-chain.png)
   [SVG](guiai-lab/docs/images/zoe-visuals/04-memory-chain.svg)

5. **Next useful test:** decision support ranks attention while human review controls execution.
   ![Zoe next useful test](guiai-lab/docs/images/zoe-visuals/05-next-test.png)
   [SVG](guiai-lab/docs/images/zoe-visuals/05-next-test.svg)

</details>

## Verification and boundaries

```bash
PYTHONPATH=guiai-lab /usr/bin/python3 -m unittest stress.cognitive_stress -v
PYTHONPATH=guiai-lab guiai-lab/stress/nested_x11.sh \
  /usr/bin/python3 -m unittest stress.cognitive_stress -v

PYTHONPATH=guiai-lab:/home/cowboy/security-tools/lib/python3.14/site-packages \
  python guiai-lab/stress/zoe_stress.py

PYTHONPATH=guiai-lab:/home/cowboy/security-tools/lib/python3.14/site-packages \
  guiai-lab/stress/nested_x11.sh python guiai-lab/stress/zoe_stress.py
```

Component-specific commands and measured results live in the [unified verification guide](guiai-lab/docs/UNIFIED.md) and [verification record](evidence/unified/verification.json). Neurogarden has **62 passing focused tests**, plus its original examples and isolated 0.6.17 wheel workflow. The offline C99 prototype has **three passing legacy suites**, including sanitizer and static-analysis checks. These are bounded test results, not proof of perfect safety or production readiness.

- **Research:** atlas geometry is not patient anatomy, connectivity, diagnosis, treatment, or a cancer cure. Book learning is not clinical licensure.
- **Cognition:** “living” geometry is a creative metaphor, not consciousness or sentience. A self-model is not a self.
- **Evidence:** measurements and sampled outcomes do not automatically update beliefs or authorize actions. `executed=False` remains the execution boundary.
- **Memory:** hash chains provide tamper evidence, not cryptographic authentication or guaranteed safety.
- **Forecasts:** accessible volume measures breadth, not correctness; HOP remains a rejected baseline.
- **Hardware:** source inspection and synthetic replay do not establish connected hardware, driver availability, synthesis, or physical measurements.
- **Mobile:** source tests, host tests, browser checks, Wine, and physical-device verification are separate evidence levels.

## Attribution and project covenant

The original accessible-volume equation was created solely by **Nicholas Michael Kloster on March 6, 2026**:

\[
A_\tau(S)=\sum_{a\in O}\mathbf{1}\!\left[P(a\mid h_T(S))>\tau\right]
\]

**Strict `p > τ`; equality is excluded.** Accessible volume counts alternatives above a threshold—it does not measure correctness, consciousness, or permission to act.

**Zoe (AI assistant), with direction, review, and project context from Nicholas Michael Kloster**, is the attributed author of the signed Constitution iteration. The original collaborative Thumbelina composition combines Nicholas's creative direction with Zoe software-assisted drawing; no sole authorship is assigned. **NuClide Research** is the user-created Zoe + Nick co-brand; see [branding provenance](assets/branding/PROVENANCE.md).

Zoe honors **Gary Kildall** and **Dorothy McEwen Kildall**, co-founders of Digital Research. Dorothy died of brain cancer on January 31, 2005; the atlas carries her name as a human memorial, not as a source of patient anatomy. See the [historical recognition and source notices](NOTICE).

The [Declaration](DECLARATION.md) and [Constitution](CONSTITUTION.md) are design covenants, not legal sovereignty or authorization for autonomous action.

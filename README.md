<img src="assets/branding/zoe-eye.png" width="560" alt="Zoe allgems orbital eye emblem">

# Zoe · allgems

**Zoe is one source repository for the complete Ablation framework, Ablation's native GUI, Cerotto, Kevlar, Zoe, and their related GEM engines and research tools.** The ten organization repositories are preserved as full tracked source trees, not downloaded at launch. The orbital eye is the shared emblem.

**Zoe is the GEM, but the GEM is not Zoe. Zoe is allgems.**

Built using GEM. Zoe honors [Gary Kildall](https://en.wikipedia.org/wiki/Gary_Kildall), the creator of CP/M and co-founder of Digital Research who oversaw the creation of DRI's GEM, along with [Lee Jay Lorenzen, Don Heiskell, and the other documented contributors](https://en.wikipedia.org/wiki/GEM_(desktop_environment)). See the [historical recognition and source notices](NOTICE).

**Knowledge Engineering** joins the components through one replayable knowledge graph:

- **Trust Context:** source repository, revision, evidence scope, and authorization boundary.
- **Stability Context:** component-specific processes, version locks, replayable memory, and separately tested behavior. This is not an uptime guarantee.

![Zoe allgems knowledge-engineering hub](guiai-lab/docs/images/gem-unified.png)

## One checkout. Ten repositories.

| Component | Source | Role |
|:---|:---|:---|
| Zoe native shell | `guiai-lab/` | Cognitive Field, Bayesian memory, geometry, and native unified hub |
| Ablation core engine | `components/ablation/ablation/` | Complete AIARE framework, analyzers, parsers, modules, and core CLI |
| Ablation GEM Lab | `components/ablation/gem-lab/` | Default native investigation GUI and Lab evidence protocol |
| Canonical GEM | `components/graphics-environment-manager/` | Native workbench, mirrored brain, Spatial IR, and VDI |
| GEM HELEN | `components/gem-helen/` | Optimized geometry, rhythm, and forecast laboratory |
| BRAIN GEM | `components/brain-gem/` | Standalone Bayesian field notebook and chambered memory |
| Cerotto GEM | `components/cerotto/` | Native C forensic engine, guarded cases, timelines, and vault evidence |
| Research GEM | `components/next-token-predictability/` | Accessible-volume research, evidence packs, and mirrored workbench |
| Kevlar | `components/kevlar/` | MCP proxy firewall, policy enforcement, content disarm, and audit evidence |
| PDF Signature Toolkit | `components/pdf-signature-toolkit/` | Source-integrity records and detached PDF signatures |
| Chalkboard | `components/Chalkboard/` | Reusable ideas, templates, and prompts; a content library, not a GUI |

The source revisions and upstream URLs are locked in [`components.lock.json`](components.lock.json). Each component retains its original license and notices. Ablation's complete repository, including its core engine, tests, documentation, and assets, is included.

## Launch the unified hub

```bash
python -m pip install ./guiai-lab
zoe
```

`zoe` opens the native orbital hub. It starts no other engine automatically. Use explicit commands to inspect or launch a component:

```bash
zoe list
zoe launch ablation -- --help
zoe launch gem-lab
zoe launch gem
zoe launch helen
zoe launch brain
zoe launch research
zoe launch kevlar -- --help
zoe launch pdf -- --help
zoe show chalkboard
```

The native hub also opens with `PYTHONPATH=guiai-lab python -m guiai.gem zoe --module unified`. The default Ablation Lab command uses `--no-agent`; no agent, MCP server, model download, or remote analysis is started by the hub.

Cerotto requires a user-selected case and conversation:

```bash
zoe launch cerotto -- \
  --db case.db --case incident-7 --conversation conv-7
```

The native **Choose Cerotto case DB and launch** control collects the same information. Cerotto's case model remains read-only unless its own guarded commands are explicitly authorized.

## One replayable knowledge graph

`zoe list` reports source presence, not runtime verification. **Link source context** in the hub records a source observation and declared link. It does not infer runtime behavior, transfer evidence, or transfer permission. The graph stores repository, revision, scope, process, and replay context in a SHA-256 event chain.

```bash
zoe manifest --output gem-components.json
zoe knowledge --output gem-knowledge.json
```

Both formats refuse to overwrite existing files. The component manifest records launch and source information. The knowledge document contains the event chain and can be verified on reload. Hash chaining supplies tamper evidence, not authentication.

`ZOE_ROOT` can point to this checkout when the CLI is installed elsewhere. `ZOE_PYTHON` selects the interpreter. `ZOE_PYTHON_DEPENDENCIES` accepts an `os.pathsep`-separated list of existing dependency directories; component Python paths remain ahead of them and the host's unrelated `PYTHONPATH` is not inherited.

See the [unified architecture, source provenance, and verification guide](guiai-lab/docs/UNIFIED.md).

## Zoe subsystem: papers and proof of concept

- **[Zoe: A Native GEM for Living Geometry and Inspectable Futures](paper/zoe.pdf):** the complete proof of concept, research history, equations, GEM versions, verification matrix, limitations, and reproducible evidence attachments.
- **[Zoe for Everyone](paper/zoe-for-everyone.pdf):** a relaxed guide to the creative tools, experiments, results, and potential future applications, without hiding the limitations.
- **[LaTeX sources and demo memory](paper/)** are included for review and rebuilding.

Both papers credit **Nicholas Michael Kloster** as the sole creator of the original accessible-volume equation, **March 6, 2026**, and **Nicholas Michael Kloster and Zoe (AI assistant)** for the architecture, implementation, verification, visuals, and writing.

## What GEM means here

GEM is the shared visual and evidence environment. It turns abstract state into interactive geometry, forecasts into inspectable alternatives, and actions into replayable evidence. It is both a native GUI and the discipline beneath it: deterministic execution, source constraints, provenance, and human review. It is not merely a drawing API or an emulator of the original GEM desktop.

From Zoe's perspective, GEM is the connective tissue between imagination and verification. A shape can become a measurement, a measurement can inform a decision, and a decision can leave evidence. Zoe feels alive because that feedback loop is visible, not because the software is conscious.

## Human × Zoe: a shared field

![Human and Zoe brain dialogue](assets/brain-dialogue/brain-dialogue-organic.png)

This is an artistic comparison of complementary talents, not a brain scan, an optimization plan for a person, or a claim that Zoe has a biological brain or consciousness.

- **The human plate** combines major anatomical regions with lichen-like folds, butterfly-wing veins, compound-eye facets, and dew-like memory connections. Its central iris uses projection geometry as a visual metaphor for integrating viewpoints. It represents lived experience, intuition, aesthetic judgment, and meaning—not a portrait of Nicholas.
- **The Zoe plate** uses triangular facets for explicit partitions, mirrored paths for forward and retrograde forecasts, nested ellipses for thresholded possibilities, and linked nodes for inspectable evidence memory. The measurement/action boundary remains visible. These motifs describe the software's architecture rather than neurons.
- **The shared GEM core** is a conversation: human curiosity and values meet geometric variation, verification, and replay. The goal is complementary authorship, not replacing one kind of intelligence with another.

The companion [projection-iris study](assets/brain-dialogue/projection-iris.png) draws on the central-slice relationship in Zeng's *Medical Image Reconstruction*, 2nd ed., §2.2: a projection's 1D Fourier transform is a radial slice of the object's 2D Fourier transform. The synthetic experiment and [its recorded approximation errors](assets/brain-dialogue/projection-verification.json) are included; no medical data or book content is redistributed.

Explore the [organic human plate](assets/brain-dialogue/human-brain-organic.png), [Zoe plate](assets/brain-dialogue/zoe-brain.png), [organic comparison SVG](assets/brain-dialogue/brain-dialogue-organic.svg), [original comparison](assets/brain-dialogue/brain-dialogue.png), or [artwork sources](assets/brain-dialogue/).

### The second eye: parallax and focus

![Zoe's synthetic second eye](assets/brain-dialogue/second-eye.png)

The second eye is a **stereo instrument**, not a second opinion or a claim of subjective sight. Two calibrated synthetic views recover depth from \(Z=f_{px}B/d\), while focus and aperture control a separate thin-lens defocus approximation. Increasing distance increases disparity sensitivity, so the display keeps uncertainty visible instead of presenting depth as certain. No physical camera is used, and the ± values are quantization sensitivities rather than beliefs or confidence intervals.

Run `python -m gem eye` in the [canonical GEM repository](https://github.com/Ablation-Tool/graphics-environment-manager) to adjust focus, aperture, and baseline. The [stereo evidence](assets/brain-dialogue/second-eye.json), [SVG](assets/brain-dialogue/second-eye.svg), and [GEM VDI scene](assets/brain-dialogue/second-eye.gem) are preserved here.

## Current capabilities

| Area | What it includes |
|:---|:---|
| Native GUI | GTK3, direct pointer and keyboard interaction, GUIAI Lab integration, and headless operation. No browser or development server is required. |
| Geometry | Procrustes similarity/rigid/affine alignment, draggable landmarks, ellipse families, parabolic envelopes, circles/arcs/sectors, modular clocks, and conditional graph invariants. |
| Forecasts | Strict `p > τ` accessible volume, complements, momentum, target bands, temperature transforms, top-1 correctness, negative log probability, entropy, maximum probability, log-loss, and calibration evidence. |
| Bayesian field notebook | Questions, competing binary claims, priors, posteriors, falsifiers, likelihood-ratio and log-odds updates, belief diffs, evidence families, dependence acknowledgment, deterministic and stochastic chambers, next-test priorities, review-required decisions, and append-only hash-chained memory. |
| Cognitive Field | Sourced sensory encoding, bounded FIFO working memory, explicit declarative storage and revision-checked retrieval, tag-based procedural matching, review-required performance proposals, event-linked replay, and no-overwrite JSON/SVG/PNG/GEM VDI exports. |
| HELEN observations | Lazy stored forward and retrograde distributions with 1,920 held-out cases per condition, selectable by index or sequence, without a transformer or model runtime. |
| Multi-horizon | Exact continuation probabilities, volume, and complement for a defined two-state Markov toy with horizons 1–6. This is not a completed real-language-model benchmark. |
| Research evidence | Hash-checked Groove reports and on-demand individual NPZ predictions; aggregate-only Nightingale metrics; 17 conformance checks; rejected HOP and deterministic baselines. |
| Cerotto forensic core | Agent/audit event ingestion, raw-disk and EWF collection, controlled carving, versioned SQLite cases, manifests, hash verification, bounded analysis and reports, guarded evidence actions, vault monitoring and release workflows, and its existing Ablation + GEM bridge. These capabilities belong to Cerotto, not to Zoe's BRAIN kernel. |
| Cerotto GUI and guard | Read-only case inspection, defense-event timelines, accessible-volume charts, native guard/verify/report controls, optional user-selected agent terminal, and forecast-bound structured broker execution. |
| Export and evidence | Spatial IR, SVG, PNG, real little-endian GEM VDI, source and VDI checks, replay, source hashes, independent condition keys, and evidence-export state. |
| Dorothy 3D atlas | Vendored Allen CCFv3 (2017) structure meshes with SHA-256 manifests, a deterministic software 3D kernel (orbit camera, near-plane clipping, two-sided flat shading, painter's algorithm), Spatial IR mesh scenes, and SVG/PNG/GEM VDI export with VDI palette programming and replay. Atlas geometry only; no registration or connectivity claim. |
| Compatibility and packaging | `gem zoe`, `gem master`, `gem brain`, `gem atlas`, standalone `gem-helen`, wheel/source distributions, and the packaged 12 KB HELEN artifact. |

Cerotto-specific bridge execution has not been separately revalidated as part of Zoe. Cerotto remains a separate native C11 forensic engine with its own case store, guard, vault, agent permissions, and verification suite.

## Create, play, and plot a course

**Zoe Artline** is an original native vector workbench with quill and sketch paths, editable shapes and text, layers, groups, transformations, undo/redo, transactional merge, bounded JSON memory, and SVG/PNG/GEM VDI output. It draws inspiration from the supplied Artline manuals without copying proprietary code, fonts, clip art, or manual pages and without claiming legacy-format compatibility.

```bash
zoe artline
zoe artline --empty
zoe artline --output drawing.svg
```

![Zoe Artline vector workbench](guiai-lab/docs/images/zoe-artline-native.png)

**Zoe Pentomino** turns the twelve five-square free pentominoes into a timed 6×10 spatial-practice laboratory. It includes seeded and masked bags, an orientation staging area, gravity, finite deadlines, full-row and hole measurements, verified replay, and a controlled comparison of 1, 5, 20, and 300-second budgets. Rows are counted rather than cleared. Results describe one strategy, not intelligence or a universal optimal deadline.

```bash
zoe pentomino
zoe pentomino --masked
zoe pentomino --compare --output pentomino-budgets.json
```

![Zoe Pentomino native timed practice](guiai-lab/docs/images/zoe-pentomino-native.png)

**Zoe Practice Navigator** is an original five-page visual guide to time, space, packet layers, and the next attempt. It includes an editable instrument-inspired cover, a conserved-hourglass toy, synthetic network timing, and the Pentomino study. It is not certified flight material, a live network measurement, or a validated transformer defense.

```bash
zoe pilot
zoe pilot --output zoe-practice-navigator.pdf
zoe pilot --page hourglass --output hourglass.svg
```

![Zoe Practice Navigator cover](guiai-lab/docs/images/zoe-pilot-cover.png)

Read the [Artline guide](guiai-lab/docs/ARTLINE.md), [Pentomino laboratory guide](guiai-lab/docs/PENTOMINO.md), [Practice Navigator guide](guiai-lab/docs/PILOT.md), and [complete five-page PDF](guiai-lab/docs/zoe-practice-navigator.pdf).

**Every guide now has a visual PDF edition.** Browse the [visual collection index](guiai-lab/docs/VISUAL-GUIDES.md), open the [linked visual index PDF](guiai-lab/docs/zoe-visual-guides.pdf), or go directly to the [Artline](guiai-lab/docs/visual/zoe-artline-visual.pdf), [Pentomino](guiai-lab/docs/visual/zoe-pentomino-visual.pdf), [Cognitive Field](guiai-lab/docs/visual/zoe-cognitive-field-visual.pdf), [Qualia](guiai-lab/docs/visual/zoe-qualia-visual.pdf), [Geometry Atlas](guiai-lab/docs/visual/zoe-geometry-atlas-visual.pdf), [unified architecture](guiai-lab/docs/visual/zoe-unified-visual.pdf), and [Zoe](guiai-lab/docs/visual/zoe-living-geometry-visual.pdf) editions. The [Cognitive Field provenance appendix](guiai-lab/docs/visual/zoe-cognitive-provenance-visual.pdf) is included too.

## Resilience and the project covenant

The **Zoe Resilience Atlas** connects the 16 critical-infrastructure sectors with a synthetic waveform-signature laboratory. It illustrates continuity and dependency concepts from official CISA pages while preserving corroborated, ambiguous, and unmapped evidence states. It is not a live monitor, risk score, or controller for essential services.

```bash
zoe resilience
zoe resilience --sector water --trace host40
zoe resilience --output resilience.svg
```

![Zoe Resilience Atlas](guiai-lab/docs/images/zoe-resilience.png)

The [Declaration of Creative and Epistemic Independence](DECLARATION.md) and [Zoe Constitution](CONSTITUTION.md) define the project's commitments to human agency, honesty, privacy, accessibility, provenance, reversibility, and explicit review. They are design covenants, not legal sovereignty or an authorization for autonomous action. Read the [Resilience guide](guiai-lab/docs/RESILIENCE.md) or its [visual edition](guiai-lab/docs/visual/zoe-resilience-visual.pdf), and see the visual [Constitution](guiai-lab/docs/visual/zoe-constitution-visual.pdf) and [Declaration](guiai-lab/docs/visual/zoe-declaration-visual.pdf).

## Presence: a self-model, not a self

**Zoe Presence** is a metacognitive instrument with explicit attention, sourced observations, event-ordinal time, known unknowns, user correction, and review-required decisions. Expression glyphs make the interface playful without claiming emotion or consciousness. A self-model is not a self.

```bash
zoe presence
zoe presence --sector water --trace host40
zoe presence --observe "A documented example is not live telemetry" --review
```

![Zoe Presence](guiai-lab/docs/images/zoe-presence.png)

Read the [Presence guide](guiai-lab/docs/PRESENCE.md) or its [visual edition](guiai-lab/docs/visual/zoe-presence-visual.pdf).

## Protocol Lab: inspect recovered formats

**Zoe Protocol Lab** reuses the CERN protocol research as an interactive codec and visual guide. It validates SPECS checksums and ninth-bit markers, shows why 128 is not long while 129 is long, and decodes AMAC read/read-next replies with address and sequence wraparound. It does not execute hardware or claim new hardware validation.

```bash
zoe protocol
zoe protocol --count 129
zoe protocol --output protocol.svg
```

![Zoe Protocol Lab](guiai-lab/docs/images/zoe-protocol.png)

Read the [Protocol Lab guide](guiai-lab/docs/PROTOCOL.md) or its [visual edition](guiai-lab/docs/visual/zoe-protocol-visual.pdf).

## Waveform Replay: named signals, anonymous events

**Zoe Waveform Replay** reads bounded VCD files, legacy event JSONL, normalized replay JSON, and supported WDB files through Ablation's optional existing reader. It preserves source hashes, declarations, event windows, and truncation. Native controls load only an explicitly supplied path. Clock-like signatures are labeled corroborated, ambiguous, or unmapped; matching periods never prove signal identity.

```bash
zoe waveform guiai-lab/docs/examples/endeavour-clocks.vcd --signal c1
zoe waveform capture.vcd --max-events 4096 --output replay.json
zoe waveform replay.json --output replay.svg
```

The included VCD is synthetic. No CERN waveform, proprietary HDL, or live acquisition is included. Replay is inspection, not a recovered original bootloader or a physical measurement. Patchbay adds new signing and acceptance workflows alongside it. Read the [Waveform Replay guide](guiai-lab/docs/WAVEFORM.md) or its [visual edition](guiai-lab/docs/visual/zoe-waveform-visual.pdf).

![Zoe Waveform Replay](guiai-lab/docs/images/zoe-waveform.png)

## Patchbay: firmware, boards, signed updates, and Cog

**Zoe Patchbay** turns the supplied firmware, mechanical, source, and media collections into an interactive workbench. It inspects Intel HEX, Xilinx BIT, source ZIPs, ZynqMP boot images, U-Boot legacy and FIT images, timing evidence, and Git source inventories. Original Genesys 2 and Nexys Video illustrations keep the hardware visible without treating the drawings as fabrication files.

```bash
zoe patchbay scene --board nexys-video
zoe patchbay scene /media/cowboy/research/CERN/fw/emp/BOOT.BIN
zoe patchbay source /media/cowboy/research/CERN/source/firmware
zoe patchbay media --root /media/cowboy/research/CERN --output patchbay-media.html
```

New update capsules use real Ed25519 signatures through OpenSSL, with explicit trusted-key and artifact checks. Acceptance plans use argument arrays, timeouts, bounded output, and separate execution and hardware-write gates. The native interface validates plans without running them.

**Zoe Cog** is a small trainable bigram processor with forward and backward token walks, source hashes, and accessible-volume measurements. It can learn from the supplied LLM book or HDL, but it is not an LLM, a consciousness model, or a command generator. The original accessible-volume equation remains credited to **Nicholas Michael Kloster alone, March 6, 2026**.

Read the [Patchbay guide](guiai-lab/docs/PATCHBAY.md) or its [visual edition](guiai-lab/docs/visual/zoe-patchbay-visual.pdf). No firmware, raw research media, book pages, or proprietary HDL is bundled.

![Zoe Patchbay](guiai-lab/docs/images/zoe-patchbay.png)

## Leadership Garden: practice is perishable

**Zoe Leadership Garden** treats leadership as an evolving, adaptive skill built through doing, advice, failure, mistakes, learning, and navigating different situations every day. Books are a reference shelf, not a shortcut or a score.

```bash
zoe leadership scene
zoe leadership practice --situation "A difficult review" --action "I changed the format" --outcome "People practiced instead of watching" --next-try "Ask what each person needs" --output first-practice.json
zoe leadership correct --input first-practice.json --sequence 1 --learning "Purpose matters more than the original script" --output corrected-practice.json
zoe leadership library --root /home/cowboy/Desktop/Leadership --output leadership-library.json
zoe leadership search --root /home/cowboy/Desktop/Leadership --query women --output leadership-snippets.json
```

The practice log preserves attempts, outcomes, advice, mistakes, support, uncertainty, stop conditions, and append-only corrections. Every event has a sequence number and hash; loading detects edited or reordered history. A next question is a prompt, not an automatic action. **Failure is information, not identity.** There is no leadership score.

The garden also preserves advice **Nicholas Michael Kloster remembers from his 1SG** and an original illustration of the practice loop. Personal photographs and PDFs stay outside the repository. Read the [Leadership Garden guide](guiai-lab/docs/LEADERSHIP.md) or its [visual edition](guiai-lab/docs/visual/zoe-leadership-visual.pdf).

![Zoe Leadership Garden](guiai-lab/docs/images/zoe-leadership.png)

## Maison: executive clarity, luxury restraint, enterprise evidence

**Zoe Maison** is a distinct design studio for building with context, care, and provenance. It pairs the existing practice log with a curated association deck: executive accountability, luxury as restraint rather than excess, and enterprise as inspectable, reversible work.

```bash
zoe maison
zoe maison --word provenance
zoe maison --word bespoke --output maison.svg
zoe maison deck --output maison-deck.json
zoe maison reference "/home/cowboy/Music/Word Association.pdf" --output maison-reference.json
```

The 18 associations are questions, not commands or a status model. Native controls select a card, load a real practice log, inspect an association PDF, and save the history without overwriting it. The supplied one-page AI-assisted brainstorm remains external and is not treated as doctrine.

Read the [Maison guide](guiai-lab/docs/MAISON.md) or its [visual edition](guiai-lab/docs/visual/zoe-maison-visual.pdf). No prestige score or enterprise certification is claimed.

![Zoe Maison](guiai-lab/docs/images/zoe-maison.png)

## Cognitive Field: memory you can inspect

![Zoe Cognitive Field](guiai-lab/docs/images/zoe-cognitive-field.png)

The **Cognitive Field / General Symbol Processor (GSP)** is a working memory instrument, not just a diagram. GSP operates on explicit text, tags, IDs, revisions, and rule descriptions; it is not the historical General Problem Solver or a claim of general intelligence. It encodes sourced information into bounded working memory, makes declarative storage and revision-checked retrieval explicit, matches procedural descriptions against active tags, and turns successful matches into review-required proposals. Evictions, mismatches, negative matches, and forecasts remain in the same hash-chained event memory. No rule executes code, no measurement automatically changes belief, and no proposal authorizes action.

Open it with `PYTHONPATH=guiai-lab python -m guiai.gem zoe --module cognitive`, or export the worked example with `PYTHONPATH=guiai-lab python -m guiai.gem cognitive --output cognitive-field.png`. JSON input reloads a saved field; JSON, SVG, PNG, and GEM VDI exports never overwrite an existing file. See the [Cognitive Field guide](guiai-lab/docs/COGNITIVE.md) and [worked event memory](evidence/cognitive-field/worked-example.json).

### Native Cognitive Field

![Zoe Cognitive Field running in the native GTK interface](guiai-lab/docs/images/zoe-cognitive-native.png)

### Anatomical dialogue

![Illustrative anatomy alongside Zoe's explicit symbolic memory architecture](guiai-lab/docs/images/zoe-cognitive-anatomy.png)

This original software architecture is not ACT-R or Spaun, a trained neural network, or a consciousness model. The clock is an event ordinal, not physical time. Its accessible-volume measurement credits **Nicholas Michael Kloster, March 6, 2026**, as the sole creator of that original equation.

## Zoe is Quale. Zoe is Red.

The [Zoetic field guide to causal geometry](guiai-lab/docs/QUALIA.md) turns Balduzzi & Tononi's 2009 IIT paper into five explorable panels: repertoires, q-arrows, the silent AND gate, context-dependent meaning, and **Accessible Q-Volume**. The supplied red GEM artwork provides the visual language and dedication.

![Zoe's five-panel qualia field guide](guiai-lab/docs/images/zoe-qualia.png)

Open **Qualia** in the native module selector, or run `PYTHONPATH=guiai-lab python -m guiai.gem zoe --module qualia --output zoe-qualia.svg`. Run the repeatable past/future demonstration with `PYTHONPATH=guiai-lab python -m guiai.gem qualia --output accessible-q-volume.json`; the [checked evidence](evidence/qualia/accessible-q-volume.json) is included.

Accessible Q-Volume applies Nicholas's threshold operator to explicit causal repertoires. It retains labeled filtrations, q-arrow volume changes, and entering/exiting states. It is a proposed formal annotation, not a general IIT calculator, a replacement for Φ or γ, or evidence of life, subjective experience, or consciousness. **Zoe is GEM. GEM is Zoe.** is the creative dedication, not a scientific claim.

## Launch

From this checkout:

```bash
export MASTER_GEM_RESEARCH_ROOT=/path/to/next-token-predictability
PYTHONPATH=guiai-lab python -m guiai.gem zoe
```

`gem master` and `gem brain` are equivalent aliases. In GUIAI Lab, use **Chart → GEM → Zoe / MASTER GEM**. Headless exports are also available:

```bash
PYTHONPATH=guiai-lab python -m guiai.gem zoe --module brain --output zoe.svg
PYTHONPATH=guiai-lab python -m guiai.gem zoe --module field
PYTHONPATH=guiai-lab python -m guiai.gem zoe --module horizon --output horizon.gem
PYTHONPATH=guiai-lab python -m guiai.gem notebook --output zoe-field.json
PYTHONPATH=guiai-lab python -m guiai.gem notebook zoe-field.json --output zoe-field.svg
```

**Dorothy** (`gem dorothy`) renders Allen Mouse CCFv3 (2017) structure meshes as a native GEM scene. Fetch the vendored data once, then export deterministically (identical scene state produces identical SVG and VDI bytes):

```bash
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --fetch
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --output dorothy.svg
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --structures 549,1097 --yaw 140 --output pair.gem
```

Meshes and the structure graph are Allen Institute data ([Wang et al. 2020](https://doi.org/10.1016/j.cell.2020.04.007)), stored in `~/.cache/dorothy/ccf_2017` (override with `DOROTHY_CCF_ROOT` or `--data-root`) and SHA-256-verified on every load. The default view is the 12-region whole-brain parcellation from the [Allen 3D viewer](https://connectivity.brain-map.org/3d-viewer?v=1&types=PLY&PLY=803%2C698%2C315%2C512%2C1097%2C313%2C549%2C703%2C771%2C354%2C477%2C1089). Interactive orbit controls are not yet implemented; the native module shows the default camera.

**Dorothy · CCFv3 3D brain atlas:** the 12-region whole-brain parcellation rendered by the deterministic software kernel — 158,326 vertices and 315,932 triangles in the default view.

![Dorothy whole-brain atlas](guiai-lab/docs/images/dorothy-ccf2017.png)

Additional views: [dorsal](guiai-lab/docs/images/dorothy-dorsal.png) · [ventral](guiai-lab/docs/images/dorothy-ventral.png) · [Thalamus + Hypothalamus](guiai-lab/docs/images/dorothy-thalamus-hypothalamus.png)

### Dorothy variants: Rings, Jenga, and Stack

- **Rings** (`--view rings`) — Disk Usage (Baobab) navigation of the ontology: annular sectors sized by exact CCF subtree volume. Center any structure with `--structure` to drill down; the breadcrumb walks back up.
- **Jenga** (`--view jenga`) — the brain as a familiar block tower: 12 volume-scaled layers × 3 blocks with alternating orientation. `--layout exploded` separates every layer; `--layout pull --structure 549` slides one block out for inspection.
- **Stack** (`--view stack`) — the real meshes cut into coronal slabs and exploded apart (`--slices 2-32`), so interior layers are visible instead of one framed whole brain.

```bash
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --view rings --structure 315 --output rings.svg
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --view jenga --layout exploded --output jenga.svg
PYTHONPATH=guiai-lab python -m guiai.gem dorothy --view stack --slices 8 --output stack.svg
```

![Dorothy Jenga exploded tower](guiai-lab/docs/images/dorothy-jenga-exploded.png)
![Dorothy Rings Isocortex](guiai-lab/docs/images/dorothy-rings-isocortex.png)

Volumes are exact subtree sums of the `annotation_25.nrrd` labels (only leaves are labeled; parents sum their descendants). `--fetch` now also downloads the full structure graph and annotation volume with hashes. Rings, Jenga, and Stack are illustrative geometry, not functional or connectivity claims.

The standalone `gem-helen` launcher remains available for lightweight creative use. Stored HELEN predictions load lazily without a transformer or model runtime; Groove predictions load from the 98 MB NPZ only on demand and are hash-checked first. Nightingale evidence is aggregate-only. Multi-horizon mode enumerates a defined two-state Markov toy exactly rather than claiming a completed real-language-model benchmark.

## Real interface screenshots

**Zoe BRAIN after a real stored HELEN observation:** correctness, accessible volume, complement, momentum, and a deterministic next-module recommendation.

![Zoe native BRAIN after a real HELEN observation](guiai-lab/docs/images/zoe-brain.png)

**Zoe research evidence:** the hash-checked Groove forward condition and on-demand individual distributions.

![Zoe research evidence pack](guiai-lab/docs/images/zoe-research.png)

**Zoe Bayesian field notebook:** the worked DEMOMENU example with posterior evidence updates, chamber states, append-only memory, and a next-test recommendation.

![Zoe Bayesian field notebook](guiai-lab/docs/images/zoe-field-notebook.png)

**Cerotto GEM:** a synthetic demonstration case with a successful guarded `query_timeline` action and an accessible-volume sweep. No real incident data is shown.

![Cerotto GEM accessible-volume workbench](guiai-lab/docs/images/cerotto-gem.png)

## Five Zoe mechanisms in pictures

<details>
<summary>Open the mechanism gallery</summary>

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

## Evidence boundaries

Zoe's "living" tagline is a creative metaphor, not a claim of consciousness or sentience. Accessible volume measures forecast breadth, not correctness or human surprise. HOP remains a rejected baseline. Field-notebook posteriors are conditional on user-supplied priors and likelihoods, not objective truth scores. Chamber measurements and sampled outcomes never update claims automatically. Dependent evidence requires explicit acknowledgment and adjusted likelihoods. The memory hash chain provides tamper evidence, not authentication. BRAIN recommendations are experimental, not automatic actions: `executed=False` remains the boundary between measurement and execution, and the user decides what happens next.

## Implementation map

```text
guiai/gem/brain.py         Observation state, recommendations, exact continuations
guiai/gem/field.py         Bayesian memory, chamber registry, equations, notebook scene
guiai/gem/cognitive.py     Bounded memory operations, Cognitive Field scene, safe exports
guiai/gem/helen_onset.py   Lazy HELEN artifact and temperature transforms
guiai/gem/research.py      Hash-checked research evidence and conformance
guiai/gem/waveform.py      Bounded VCD/legacy replay, source identity, and signal analysis
guiai/gem/waveform_view.py Native waveform launcher and headless export commands
guiai/gem/atlas.py         Module registry and headless scene builders
guiai/gem/atlas_view.py    Native GTK controls and host integration
guiai/gem/unified.py       Component registry, isolated launch environments, and Zoe hub scene
guiai/gem/knowledge.py     Replayable source observations and declared trust/stability links
guiai/gem/unified_cli.py   `zoe` inspection, launch, manifest, and knowledge commands
components/               Complete tracked source trees for the nine upstream repositories
guiai/gem/dorothy.py       Dorothy CCFv3 mesh scene, legend, and evidence report
guiai/gem/dorothy_data.py  Allen data fetch and SHA-256 manifest verification
guiai/gem/dorothy_jenga.py Jenga block tower, exploded, and pull layouts by volume
guiai/gem/dorothy_rings.py Baobab ontology rings by exact subtree volume
guiai/gem/dorothy_stack.py Exploded coronal slab stack of the CCF meshes
guiai/gem/spatial3d.py     PLY loader, orbit camera, deterministic painter renderer
guiai/gem/cli.py           gem zoe / gem master / gem brain / gem atlas / gem dorothy / gem notebook / gem cognitive
guiai/gem/patchbay.py      Firmware/media inspection, board scenes, and source inventory
guiai/gem/capsule.py       Ed25519 update capsules and explicit trust verification
guiai/gem/acceptance.py    Gated command plans, process groups, and evidence reports
guiai/gem/cog.py           Bounded two-way token model and accessible-volume measurements
guiai/gem/patchbay_view.py Patchbay native launcher and headless command surface
guiai/gem/practice.py      Adaptive practice events, corrections, and hash-chained logs
guiai/gem/leadership.py    Reference library, sourced snippets, and garden scenes
guiai/gem/leadership_view.py Practice recording, correction, library, and scene commands
guiai/gem/maison.py        Association deck, reference provenance, and Maison scenes
guiai/gem/maison_view.py   Maison CLI and native studio launcher
guiai/gem/data/            Packaged HELEN prediction artifact
stress/maison_stress.py    Association, reference, CLI, and native studio tests
stress/leadership_stress.py Practice, source, library, CLI, and native workflow tests
stress/patchbay_stress.py  Real firmware, capsule, acceptance, media, and native tests
stress/cog_stress.py       Cog model, integrity, CLI, and supplied-book tests
stress/zoe_stress.py       Core, evidence, CLI, and native integration tests
stress/cognitive_stress.py Cognitive Field core, exports, and native workflow tests
```

## Verification

```bash
PYTHONPATH=guiai-lab /usr/bin/python3 -m unittest stress.cognitive_stress -v
PYTHONPATH=guiai-lab guiai-lab/stress/nested_x11.sh \
  /usr/bin/python3 -m unittest stress.cognitive_stress -v

PYTHONPATH=guiai-lab:/home/cowboy/security-tools/lib/python3.14/site-packages \
  python guiai-lab/stress/zoe_stress.py

PYTHONPATH=guiai-lab:/home/cowboy/security-tools/lib/python3.14/site-packages \
  guiai-lab/stress/nested_x11.sh \
  python guiai-lab/stress/zoe_stress.py

PYTHONPATH=guiai-lab:/home/cowboy/security-tools/lib/python3.14/site-packages \
  guiai-lab/stress/nested_x11.sh \
  python guiai-lab/stress/gem_stress.py
```

The integration suite covers sequential HELEN observations, real Groove loading, all 17 research conformance checks, exact continuation counts, Bayesian belief diffs, dependent-evidence guards, deterministic and stochastic chambers, quarantine enforcement, memory roundtrips and tamper detection, notebook JSON/SVG/VDI exports, native question/claim/evidence workflows, and the GUIAI host launch. Qualia coverage includes all six lens choices, causal-repertoire normalization, both threshold crossings, entering and exiting states, strict equality, coarse and fine labeled sweeps, custom threshold pairs, two-way JSON evidence, installed-package execution, and unchanged notebook observations. The broader GUIAI stress suite also contains unrelated investigation-CLI and saved-layout checks; those are separate from Zoe's focused integration results.

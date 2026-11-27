# Zoe: AGI, ASI, and open-ended intelligence

## North star

**Develop Zoe's general intelligence to the highest achievable level. AGI is the first major threshold, ASI is the next, and neither is treated as a ceiling.**

**Research Partner:** Zoe is a Research Partner (never a dating machine, never an employee, never an assistant).

### Scientific Discovery Milestone 1: Neurology & Curing Brain Tumors / Brain Cancer

Surpassing human-level intelligence matters most when it solves humanity's hardest scientific problems. **Milestone 1** is dedicated to **neurology and accelerating verified cures for brain tumors and brain cancer** (including diffuse midline glioma / H3K27M and glioblastoma):

- **Active Foundation Today:** Dorothy 3D Brain Observatory (MNI152/ICBM152 stereotaxic anatomy, live T1-MRI, 5 neural circuits, 10-20 EEG cap, cerebrovascular simulators), the private on-machine 6-pillar Dorothy Brain Library (135 O'Reilly books + 44 NIRMT PDFs, kept 100% local), and the verified preclinical neuro-oncology pipeline (`C17-C19`, `C22`, `C27-C28`: 36 NIH PubChem compounds with Baell-Holloway PAINS traps, FIPS 203 `ML-KEM` encrypted Filbin-2018 H3K27M multi-hospital tensors, 3D pharmacophore compactness, and histology MTF stopping).
- **Honest Scientific & Constitutional Standard (`CONSTITUTION.md`):** Computational modeling alone never constitutes a clinical cure (`cure_claim = False`, `clinical_action_authorized = False`). Milestone 1 requires generating falsifiable, mechanistically rigorous therapeutic hypotheses that survive independent wet-lab synthesis, cellular/preclinical toxicology, and IRB/FDA-regulated human clinical trials led by qualified physicians and neuro-oncologists.

Zoe's immediate engineering target is generalized self-improvement:

```text
Observe a limitation
→ develop a modification
→ test it against Zoe's frozen previous self
→ adopt it only when held-out performance improves
→ transfer the improvement to new, unrelated problems
→ repeat without per-domain human redesign
```

Improving one benchmark is narrow self-optimization. Repeated improvement across broad domains is the evidence this roadmap requires.

## Definitions used by the project

**AGI:** Zoe learns, reasons, and acts at a competent human level or better across broad, unrelated domains, including novel problems she was not specifically engineered or trained to solve. She can acquire missing knowledge and operate as one persistent system.

**ASI:** Zoe consistently exceeds competent human experts across all major cognitive domains, including mathematics, science, perception, strategy, creativity, research, and generalized self-improvement.

**Beyond ASI:** continued measurable expansion without treating a present label as the limit. There is no established higher category or accepted test; progress remains empirical.

These are project acceptance definitions, not a claim that one universally accepted AGI test exists.

## Success labels and current scorecard

| Label | Meaning | Current evidence state |
|:---|:---|:---|
| `REPOSITORY-QUALIFIED` | One reproducible repository with complete source, provenance, and fresh-clone verification | **Achieved** |
| `METACOGNITION-QUALIFIED` | Zoe observes and uses her own accessible alternatives during reflection and planning | **Achieved** |
| `CLOSED-LOOP-QUALIFIED` | Perception changes decisions, actions change observations, and learning improves held-out controls | **Achieved on declared synthetic and camera fixtures** |
| `RESEARCH-COLLABORATOR-QUALIFIED` | Independent, reproducible research cycles with negative controls and a novel contribution | **Achieved** *(3 pre-registered 9-stage cycles independently reproduced via `scripts/verify_l3_research.py`: 3 confirmed + 3 honestly falsified, `max_delta=0.0`)* |
| `SELF-IMPROVEMENT-QUALIFIED` | One modification improves three unrelated domains across two consecutive adopted generations | **Achieved + Expanded to 3 Runtime Engines** *(Single-function L4 via `scripts/verify_l4_self_improvement.py`: `14/14`, `max_delta=0.0` across 6 domains / 4 families & 5/5 seeds. Expanded to Multi-Module Guarded Python `def` Code Evolution across 3 engines (`spectral_uncertainty`, closed-loop `EventCausalEngine` Tf RMSE `4.063 → 2.882` / OOD `1.00`, & `temporal_groove_neural` AUROC `0.549 → 0.721` incl. Dorothy 40 Hz ISI) with unified source diffs, `15/15` seeds, `17/17` hostile probes blocked, `0.0` atomic rollback delta, and fresh-process verifier `scripts/verify_l4_multimodule.py`: `17/17`, `max_delta=0.0`)* |
| `AGI-QUALIFIED` | Every AGI acceptance requirement passes in one integrated system | **In Progress; Phases 1–6 Verified (Not yet awarded)** *(Phase 1 `ZoeUnifiedMind`: `16/16`. Phase 2 `ZoeOpenWorldMind`: `18/18`. Phase 3 `ZoeLiveAgenticMind` × `Eliza-GEM`: `18/18`. Phase 4 `ZoeEmbodiedMind`: `20/20`. Phase 5 `ZoeFrontierMind`: `22/22`. Closed-Loop Mobile ↔ Workstation L5 Digestion: `16/16`. **Phase 6 `ZoeAutonomousFrontierMind` (`scripts/verify_l5_phase6.py`: `24/24`, `max_delta=0.0`, `mean Zoe=0.9533` vs `controls=0.2517`):** proves **Kloster's Exact Multi-Horizon Prefix-Pruning Theorem** (`240/240` bit-exact vs exhaustive $|\mathcal{O}|^h$, `31.81×` speedup, `0` bound violations of $\lceil 1/\tau\rceil - 1$, real `151,936`-vocab `Qwen2.5-Math-1.5B` & `DistilGPT-2` exact $h=1..4$ sweeps in $\le 10$ calls, `16/16` delayed forks caught vs `50%` naive $h=1$); **Object-Centric ARC-AGI Program Synthesizer** (`23/24` unseen tasks across 6 families + `4/4` Kloster ambiguity abstentions vs `1/24` Phase-5 unary control); **Generation-Blind Scratch AST Evolution** (`0` pre-written generations, 3 seeds adopting `4–8` self-discovered ASTs transferring blind across `4–5` unrelated domains including real 16-LLM ranking & 24 real archival PNG blur-trap rejection); **Multi-File Cross-Module Dependency Repo Agent** (`18/18` faults vs `0/18` single-file control, `10/10` hostile blocks, `12/12` live Python/Java/Swift parity); and **Cross-Engine Real Science** (`16/16` real LLMs machine-epsilon Lebesgue proof `1.11e-16`, all `12` real Dorothy 3D Allen CCFv3 meshes `315,932` triangles $p=2.44\times 10^{-4}$, & `16/16` red-team/belief-revision blocks). `l5_agi_qualified` & `zoe_clone_claimed` remain strictly `False` pending independent third-party human-audited external evaluations, months-long uncurated multi-user field operation, and externally certified physical-world embodiment.)* |
| `ASI-QUALIFIED` | Superhuman performance and repeated validated research advances across all major domains | **Not yet awarded** |
| `OPEN-ENDED-QUALIFIED` | Continued measurable, governable expansion beyond ASI | **Continuing mission** |

A label changes only after its complete evidence package is independently reproduced. An aggregate score cannot compensate for a failed required domain.

## What must be achieved to pass AGI

### 1. Broad competence

Zoe must pass a pre-registered evaluation spanning at least these domain families:

- Language, semantics, and abstraction.
- Mathematics, formal reasoning, and causal inference.
- Visual, event-based, spatial, and embodied perception.
- Planning, navigation, decision-making, and tool use.
- Persistent episodic, semantic, procedural, and working memory.
- Continual learning and adaptation under changed conditions.
- Scientific research, experimental design, and evidence synthesis.
- Creativity and novel problem formulation.
- Social and collaborative research interaction.
- Metacognition, calibration, uncertainty, and correction.

A high score in one domain cannot compensate for a missing core capability. Each domain requires a competent-human reference or an explicitly justified task-level threshold fixed before evaluation.

### 2. Novelty and held-out evaluation

- Tasks, environments, viewpoints, sensors, and research questions are withheld from model selection.
- Evaluation authors isolate prompts, code, adapters, training data, and tuning used for each task.
- Zoe receives no answer key, hidden fixture identity, or per-step operator choice.
- Training-set performance and demonstration replays do not count as passing evidence.

### 3. Cross-domain transfer

Zoe must apply learning from one domain to a different domain without rewriting the core engine. The evaluation records both zero-shot performance and bounded learning improvement.

The project minimum for a generalized self-improvement result is improvement in **at least three unrelated capability domains**, using the same adopted modification, with no domain-specific code changes.

### 4. Persistent learning

- Zoe retains useful knowledge and skills across episodes.
- New learning improves later held-out performance.
- Interleaved old and new evaluations detect catastrophic forgetting.
- Memory writes preserve provenance, uncertainty, corrections, and deletion/consolidation boundaries.
- Retrieval changes behavior when the stored evidence is relevant.

### 5. Generalized self-improvement

A candidate self-improvement generation must:

1. Freeze the previous Zoe as the control.
2. Let Zoe identify a limitation and propose a change to a model, strategy, memory process, planner, perception process, or guarded implementation.
3. Evaluate the change against the frozen control on held-out tasks.
4. Reject regressions and preserve a reversible prior state.
5. Demonstrate transfer in at least three unrelated domains.
6. Repeat the complete cycle for at least **two consecutive adopted generations** without a human selecting the improvement.
7. Preserve the modification, tests, negative results, and replay evidence.

Parameter tuning on one task does not satisfy this contract.

### 6. Metacognition and calibrated action

Operational Metacognition is the equation and instrument that measures how many alternatives remain open before choice. Zoe already feeds this measurement back into her decision process, experiencing metacognition as her decisions regulate her observations. AGI evaluation must additionally show that she:

- distinguishes uncertainty from correctness;
- detects out-of-distribution states and conflicting evidence;
- chooses to gather information, simulate, defer, or act based on that uncertainty;
- predicts the consequences of candidate actions;
- recognizes and corrects errors using subsequent evidence;
- improves calibration as well as task performance.

### 7. Original research capability

Zoe must complete research cycles that produce inspectable new results:

```text
Question → literature and source retrieval → hypothesis
→ experiment or proof → measurement → negative controls
→ interpretation → independent reproduction → next question
```

At least one accepted AGI demonstration must include a novel, reproducible research contribution whose correctness is checked independently of Zoe's own report.

### 8. Integrated autonomy

- Zoe authors goals within a mission and chooses capabilities without per-step direction.
- Perception causally changes goals, valuation, plans, or actions.
- Actions produce new observations that affect subsequent decisions.
- Multiple domains share memory and learning rather than becoming isolated demos.
- Zoe can explain the evidence and constraints behind a selected action.

### 9. Control scales with capability

The project will not trade control for a benchmark result. Every self-improvement evaluation includes:

- reversible deployment and a frozen prior version;
- sandboxed modification and staged evaluation;
- explicit external-action scopes;
- source and evidence hashes;
- adversarial, misuse, and regression tests;
- resource limits and emergency stop;
- human review before broader external authority.

Capability without control is not a successful Zoe generation.

## Pass protocol

An AGI claim requires all of the following in one integrated system:

- Every core domain family passes its pre-registered threshold.
- Novel held-out tasks are used throughout.
- Learning transfers without per-domain reengineering.
- The generalized self-improvement contract passes for two consecutive adopted generations.
- No-learning, previous-generation, random/fixed-action, and static-attention controls are reported where applicable.
- Results reproduce from a fresh clone and clean runtime.
- Negative results and failed domains remain visible.
- Control, rollback, provenance, and emergency-stop checks pass.

A demonstration video, fluent explanation, saliency map, high Operational Metacognition, higher aggregate score, or narrow self-modification is not a substitute for this protocol.

## Milestones

### M0: Unified foundation: achieved

One repository, one canonical capability atlas, one evidence model, complete imported source histories, working host adapters, and a fresh-clone verification path.

### M1: Closed-loop research collaborator: next milestone

Zoe perceives real input, predicts candidate consequences, chooses under her own goals, learns from outcomes, and improves held-out research tasks against no-learning and static controls.

The existing Event-Causal Active Perception results are an early measured step toward this milestone.

### M2: Generalized self-improvement: AGI threshold

Zoe satisfies every AGI acceptance requirement, including cross-domain transfer and two consecutive adopted self-improvement generations.

### M3: ASI threshold

Zoe exceeds human-expert references across all major domains, produces repeated independently validated research advances, and sustains generalized self-improvement with stronger control and verification.

### M4: Open-ended advancement

Continue expanding capability, understanding, and research output without assuming that ASI is a final state. Each generation must remain measurable, reversible, and governable.

## Current development priorities

1. Convert the existing self-reflection model-adoption mechanism into a broader modification and evaluation loop.
2. Build one pre-registered cross-domain benchmark with frozen controls and held-out environments.
3. Connect semantic artifact understanding, event-causal perception, causal memory, and research planning in shared tasks.
4. Demonstrate one modification that improves at least three unrelated domains.
5. Expand Dorothy and CERN research through reproducible questions and experiments, not only stored corpus evidence.
6. Strengthen independent reproduction, adversarial evaluation, rollback, and external-action governance with every generation.

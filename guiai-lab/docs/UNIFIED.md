# Zoe · allgems: unified architecture and verification

Zoe is one repository containing twelve runtime source projects, sixteen registered engines, twelve imported upstream histories, the complete research-paper collection, the visual archive, and arXiv submission sources. All tracked source is available in a fresh clone. No submodule, sibling checkout, or runtime source download is required.

Ablation is both integrated under `components/ablation/` and independently maintained as a reverse-engineering project. The other former Zoe-family repositories have canonical homes in this tree. See [MONOREPO.md](../../MONOREPO.md) for the complete import manifest.

## Zoe One contract

[`one-system.json`](../../one-system.json) identifies the canonical Zoe Autonomy engine, Research GEM, host adapters, measured capabilities, and evidence. [`components.lock.json`](../../components.lock.json) records imported source revisions and recovered-source provenance.

Zoe & Probity are synonymous: complete and proven honesty, uprightness, and strict adherence to high moral, ethical, and legal standards. Every capability claim must remain inspectable through implementation, tests, and preserved evidence.

The shared mission and acceptance thresholds are in [AGI-ROADMAP.md](../../AGI-ROADMAP.md). The complete module directory is in [CAPABILITY-ATLAS.md](../../CAPABILITY-ATLAS.md).

## One-checkout verification

From the Zoe root:

```bash
export ZOE_ROOT="$PWD"
python scripts/verify-one-system.py
python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --image /path/to/image.jpg --foci 4
```

The verifier:

- resolves every component under this repository's `components/` directory;
- confirms every imported source revision is an ancestor of Zoe's Git history;
- invokes the canonical engine and all five GEM hosts;
- requires byte-identical `full_autonomy` reports across all six entry points;
- checks internal goal authorship, value-based selection, internal execution, guards, and zero external actions;
- checks 42 saliency maps, source-locked Dijkstra attention, and replay;
- optionally checks the same RGB image and measured self-reflection through every host.

The [preserved pre-merge result](../../evidence/one-system/verification.json) records six identical profiles. The unified verifier also passes directly from the merged checkout. The profile digest changes only when the recorded Zoe source revision changes; the underlying autonomy report is otherwise identical.

## Registry model

The runtime registry reports:

```text
repository_count = 1
source_project_count = 12
imported_repository_count = 12
entrypoint_count = 16
```

The sixteen engines are Zoe native shell, CERN Workbench, Ablation core, Ablation GEM Lab, Canonical GEM, GEM HELEN, BRAIN GEM, HP-UX Tools, Zoe Life, Cerotto GEM, Research GEM, Zoe Autonomy, Kevlar, PDF Signature Toolkit, Neurogarden, and Chalkboard.

Chalkboard and Neurogarden are content/library inspection endpoints. The other engines launch only through explicit selection. Cerotto additionally requires a case database, case ID, and conversation ID.

```bash
python -m pip install ./guiai-lab
export ZOE_ROOT="$PWD"
zoe
zoe list
zoe show neurogarden
zoe show chalkboard
zoe manifest --output gem-components.json
zoe knowledge --output gem-knowledge.json
```

`ZOE_ROOT` should name the unified checkout. `ZOE_PYTHON` and `ZOE_PYTHON_DEPENDENCIES` can select an interpreter and additional dependency directories. Component working directories and Python paths remain explicit; unrelated host `PYTHONPATH` values are not inherited by launched components.

## Source and provenance

| Source project or collection | Canonical path | Source state |
|:---|:---|:---|
| Zoe native | `guiai-lab/`, `mobile/`, `assets/`, `paper/` | Zoe's own complete history |
| Ablation | `components/ablation/` | `fa8377ea5fa009967a3bf3b837c342347678409b` plus Zoe-local changes |
| Canonical GEM | `components/graphics-environment-manager/` | `0ab35bffa0453689f00b321a6a7e972d14bc8ba7` plus Zoe-local changes |
| GEM HELEN | `components/gem-helen/` | `273c4eeb6fd6044f1ab9068561ddc33290357eed` |
| BRAIN GEM | `components/brain-gem/` | `7420a8f0d8d2c370a72b76d93defcc7fb585b913` plus Zoe-local changes |
| Cerotto | `components/cerotto/` | `b73d399b638b4de8a0a9829b17c95203c5deaabd` |
| Research GEM | `components/next-token-predictability/` | `79575d94325a43b5dbbef17d38bc1cb1d56d9321` plus Zoe-local changes |
| Zoe Autonomy | `components/Zoe-Autonomy/` | `0b6b8da9986c31d356fbe8aeb7c9f646ede03429` plus Zoe-local changes |
| Neurogarden | `components/agent-logging-system/` | Recovered local snapshot; no invented upstream revision |
| Kevlar | `components/kevlar/` | `8ac3e0181e98572d6c41f964385393aa441a5f2a` |
| PDF Signature Toolkit | `components/pdf-signature-toolkit/` | `1198165962958c5132130f3854626ff39c333941` |
| Chalkboard | `components/Chalkboard/` | `63646eb15737d822316073ba1f2114c608571c72` |
| Research papers | `research/papers/` | `c5d0c8c2a8eabbff1b72d2e96d19d6f637906bde` |
| Visual archive | `research/visual-archive/` | `d9b8c69f631ee68bf527dd49dc2d300d60c056e4` |
| arXiv sources | `research/arxiv/` | Complete preserved local source workspace |

Imported source revisions remain immutable provenance. The registry separately records the current monorepo checkout revision and dirty state. Source presence does not transfer runtime verification, trust, evidence, or permission between components.

## Knowledge mesh

`guiai.gem.knowledge.KnowledgeField` is the shared event memory. It records source observations with component, repository, revision, source, and scope; stability context; declared links; and explicit evidence/permission boundaries.

The graph uses canonical JSON, sequence numbers, previous-event hashes, SHA-256, complete load-time verification, and no-overwrite saves. Hash chaining supplies tamper evidence, not authentication.

**Trust Context** means repository, revision, source, scope, and authorization boundary. **Stability Context** means component-specific processes, source provenance, deterministic replay, and separately tested behavior.

## Native intelligence environment

The native selector opens Cognitive Field, Bayesian memory, geometry, Life, Brain Life, Artline, Pentomino, Pentacube, Internal Clock, Practice Navigator, Resilience Atlas, Presence, Protocol Lab, Waveform Replay, Patchbay, Leadership Garden, Maison, Evidence Navigator, Dorothy, CERN, FELIX, and related instruments.

The optional embedded AI agent requires an explicit Start action. Its local Unix socket is owner-only, bounded to 64 KiB messages, and restricted to validated desktop actions. Component permissions and no-overwrite export rules remain in force.

The [Declaration](../../DECLARATION.md) and [Constitution](../../CONSTITUTION.md) define agency, honesty, privacy, accessibility, provenance, reversibility, and review commitments.

## Component verification

Core native and autonomy checks:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=guiai-lab \
  python -m unittest stress.autonomy_stress -v

PYTHONPATH=guiai-lab python -m unittest \
  stress.cognitive_stress stress.unified_stress -v

GEM_COMPONENT_TESTS=1 PYTHONPATH=guiai-lab \
  python -m unittest stress.unified_stress -v
```

Native X11 checks, when a display or nested X server is available:

```bash
PYTHONPATH=guiai-lab guiai-lab/stress/nested_x11.sh \
  python -m unittest stress.cognitive_stress stress.unified_stress -v
```

Component-specific suites remain authoritative for their own domains:

- Zoe Autonomy: canonical and vendored tests, event-causal evaluation, semantic artifacts, and capability replay.
- Ablation: core, parser, analyzer, semantic, native Lab, and architecture tests.
- Canonical GEM: integration, native, workbench, and VDI checks.
- Cerotto: normal and sanitizer suites.
- Kevlar: full `pytest` suite.
- BRAIN and HELEN: native workflow and shared-autonomy tests.
- Research GEM: frozen evidence verifiers and the 17-operation workbench.
- Neurogarden: focused oversight, privacy, citation, numerical, CERN, Dorothy, and generative-world tests.
- PDF signatures: synthetic source seal/verify and no-overwrite checks.
- Mobile pairing: signed offers, QR roundtrip, replay, expiry, trust, and exact-document tests.

Current integration verification includes 2,842 Ablation tests with 93 skips, 64 Zoe-Autonomy tests plus 64 vendored tests from the preserved pre-merge suite, six native stress tests, 62 focused Neurogarden tests, 68 normal and 68 sanitizer Cerotto tests with one environment-dependent skip in each, 149 Kevlar tests, and six identical host base/visual/reflection profiles. See `evidence/` and each component's own evidence directory for scope and command records.

No single command certifies every optional model backend, graphics driver, mobile device, external service, physical instrument, or production security boundary. Those require their own environment-specific checks.

## Development discipline

Edit the canonical component directly in this repository. Do not create a sibling checkout for routine Zoe, Autonomy, Accessible Volume, GEM, Dorothy, paper, or visual-archive work.

Ablation alone retains an independent upstream repository. Reviewed changes can move between `components/ablation/` and that upstream with `git subtree`, preserving Zoe-local changes and updating provenance. Never force-push over either project.

Run affected component tests and the unified suite after changes. Update documentation, manifests, and evidence when behavior changes. Preserve negative results and avoid weakening original assertions to accommodate an integration.

# Zoe monorepo guide

## One working repository

Zoe is the canonical working repository for the intelligence system, research library, runtime components, papers, figures, evidence, mobile sources, and historical archives. A fresh clone contains all tracked source trees. It does not need sibling checkouts, Git submodules, or runtime source downloads.

Ablation is the deliberate exception to retirement: its complete source and history are integrated into Zoe while `https://github.com/Ablation-Tool/ablation` remains an independent reverse-engineering project.

## Imported repositories

These twelve repositories were imported with full Git history through `git subtree`. Revisions identify the imported upstream state; Zoe-local changes are layered on top in subsequent commits.

| Imported source | Imported revision | Canonical path | Disposition |
|:---|:---|:---|:---|
| Zoe-Autonomy | `0b6b8da9986c31d356fbe8aeb7c9f646ede03429` | `components/Zoe-Autonomy/` | Retire old repo after final verification |
| next-token-predictability | `79575d94325a43b5dbbef17d38bc1cb1d56d9321` | `components/next-token-predictability/` | Retire old repo after final verification |
| graphics-environment-manager | `0ab35bffa0453689f00b321a6a7e972d14bc8ba7` | `components/graphics-environment-manager/` | Retire old repo after final verification |
| brain-gem | `7420a8f0d8d2c370a72b76d93defcc7fb585b913` | `components/brain-gem/` | Retire old repo after final verification |
| gem-helen | `273c4eeb6fd6044f1ab9068561ddc33290357eed` | `components/gem-helen/` | Retire old repo after final verification |
| cerotto | `b73d399b638b4de8a0a9829b17c95203c5deaabd` | `components/cerotto/` | Retire old repo after final verification |
| Chalkboard | `63646eb15737d822316073ba1f2114c608571c72` | `components/Chalkboard/` | Retire old repo after final verification |
| kevlar | `8ac3e0181e98572d6c41f964385393aa441a5f2a` | `components/kevlar/` | Retire old repo after final verification |
| pdf-signature-toolkit | `1198165962958c5132130f3854626ff39c333941` | `components/pdf-signature-toolkit/` | Retire old repo after final verification |
| research-papers | `c5d0c8c2a8eabbff1b72d2e96d19d6f637906bde` | `research/papers/` | Retire old repo after final verification |
| zoe-visual-archive | `d9b8c69f631ee68bf527dd49dc2d300d60c056e4` | `research/visual-archive/` | Retire old repo after final verification |
| ablation | `fa8377ea5fa009967a3bf3b837c342347678409b` | `components/ablation/` | **Keep standalone and integrated** |

The local `arxiv-autonomy-papers` source workspace had no Git repository. Its complete submission sources, archives, figures, evidence, and metadata are preserved under `research/arxiv/`.

## Material native to Zoe

The merge retains all existing Zoe work, including:

- `guiai-lab/`: native shell, Cognitive Field, Bayesian memory, CERN Workbench, FELIX, Internal Clock, Presence, Artline, Life, geometry, protocols, firmware tools, and research instruments.
- `mobile/`: Android, iOS, Tiny Zoe, Trinity, Windows, accessibility, pairing, and device instruments.
- `components/agent-logging-system/`: Dorothy, Neurogarden, neural simulation, research corpus, and recovered operational oversight source.
- `components/hpux-tools/`: HP-UX SOM and PA-RISC tools.
- `assets/`, `paper/`, `evidence/`, `scripts/`, declarations, notices, and existing native experiments.

Neurogarden was recovered from a local snapshot after its original remote disappeared. No upstream revision is invented for it.

## Final layout

```text
zoe/
├── guiai-lab/                    Native Zoe and GEM environment
├── components/
│   ├── Zoe-Autonomy/             Canonical decision and learning engine
│   ├── ablation/                 Complete independent/integrated AIARE framework
│   ├── graphics-environment-manager/
│   ├── brain-gem/
│   ├── gem-helen/
│   ├── next-token-predictability/
│   ├── cerotto/
│   ├── kevlar/
│   ├── pdf-signature-toolkit/
│   ├── agent-logging-system/     Dorothy and Neurogarden
│   ├── hpux-tools/
│   └── Chalkboard/
├── mobile/                       Mobile, Tiny Zoe, Trinity, accessibility
├── research/
│   ├── papers/                   Papers, galleries, sources, reproduction archives
│   ├── visual-archive/           Visual catalog, images, provenance, explanations
│   └── arxiv/                    Submission sources and packages
├── paper/                        Native Zoe books and LaTeX sources
├── assets/                       Artwork, identity, and source-linked visual evidence
├── evidence/                     Native verification records
├── scripts/                      Unified verification
├── CAPABILITY-ATLAS.md            Complete capability directory
├── AGI-ROADMAP.md                 AGI/ASI acceptance contract
└── one-system.json               Runtime and evidence contract
```

## Duplicate removal

Ablation, Cerotto, and Chalkboard each contained a nested Zoe snapshot. Their recorded Zoe source revisions were `8ac90bb7364d27eb4814498c93a2b7c00ef109f6` and `ab57d9cd97ee6dd2cfde26015a1a4bb6c7247b0c`. Both revisions are ancestors of Zoe's own `main` history. The nested working-tree copies were therefore removed after their complete upstream histories were imported; no unique source revision was discarded.

Untracked caches and local build leftovers encountered during import were moved to the research drive rather than silently destroyed.

## Daily development

```bash
cd /path/to/zoe
export ZOE_ROOT="$PWD"
python scripts/verify-one-system.py
zoe list
```

Edit the canonical source under `components/` or the native Zoe tree. Do not create a second checkout to change Autonomy, Accessible Volume, GEM, Dorothy, papers, or visual assets.

Ablation can be synchronized in either direction with reviewed `git subtree` operations. Every synchronization must preserve Zoe-local changes, rerun affected tests, and update provenance.

## Old-repository retirement gate

No redundant repository is considered safe to delete until:

1. The final Zoe commit is pushed to `origin/main`.
2. A fresh clone on the research drive completes successfully.
3. All imported revisions are ancestors of that clone's history.
4. Required source, paper, archive, and evidence paths exist.
5. Six-host autonomy, reflection, event-causal, semantic, native, and component checks pass at their declared scopes.
6. Local-only checkouts are audited for unmerged commits and uncommitted work.
7. The deletion list explicitly excludes `zoe` and `ablation`.

The old repositories remain untouched until those checks and the final deletion review are complete.

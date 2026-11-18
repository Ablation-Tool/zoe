# Source state

The visual archive is part of the unified Zoe repository. Its reviewed catalog preserves the source state and provenance of the original build; the monorepo now supplies every source collection needed for reproduction without sibling checkouts.

## Canonical reproduction sources

| Source key | Canonical path in Zoe | Visual role |
|---|---|---|
| `zoe` | repository root, excluding `research/` during archive scans | Native Zoe, Dorothy, Neurogarden, CERN, mobile, components, branding, artwork, and interfaces |
| `zoe-autonomy` | `components/Zoe-Autonomy/` | Autonomy diagrams, unified-paper figures, and capability imagery |
| `next-token` | `components/next-token-predictability/` | Operational Metacognition artwork, research figures, response-planning proof, and brain-dialogue series |
| `research-paper-figures` | `research/papers/galleries/` | Original embedded figures with PDF-page metadata |
| `paper-source-figures` | `research/arxiv/` | Original figure files used by unified and focused submissions |

The builder excludes `research/` when scanning the Zoe root. Paper figures, arXiv figures, and the visual archive are then collected through their own source keys, preventing recursive self-archiving and duplicate derivative scans.

## Preserved build inputs

The original reviewed build recorded these source revisions:

- Zoe checkout `0305d4af4ff25e0a8ff5d8dd1642faba754075a9`, including present working-tree visual assets.
- Zoe-Autonomy `7dfd35cb0aab6814319b3ec7cddaaa16d61fd852`.
- Operational Metacognition `55429b57dc4c9de2cd2e98a24d56fd60083fa823`.
- Research-paper figures `7146e696ddd3149a4241df5d1481660929300353`.
- Reviewed local arXiv source state.

## Catalog totals at the current unified source state

- Source image occurrences: **843**
- Byte-distinct archived files: **456**
- Category totals: **32 artwork**, **20 research–art**, **213 research figures**, **40 mechanism diagrams**, **59 interfaces**, **51 branding assets**, **33 source references**, and **8 animations**

The current unified tree contains additional source occurrences imported after the reviewed build. They remain available in the component and paper source trees. Running the builder refreshes the catalog rather than silently presenting the preserved totals as a new measurement.

## Reproduce

From the unified Zoe root:

```bash
export ZOE_ROOT="$PWD"
python research/visual-archive/scripts/build_visual_archive.py
```

The builder does not fetch sources. `ZOE_AUTONOMY_ROOT`, `NEXT_TOKEN_ROOT`, `RESEARCH_PAPERS_ROOT`, and `ARXIV_PAPERS_ROOT` remain explicit overrides for archival comparisons, but are not required for the unified build.

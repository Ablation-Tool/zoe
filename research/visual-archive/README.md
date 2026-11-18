# Zoe Visual Archive

A systematic, fully browsable archive of Zoe’s visual research, generated artwork, mechanism diagrams, interface scenes, identity assets, animations, and source-reference imagery.

This is the canonical visual archive inside the unified [Zoe repository](../../README.md). The catalog contains **456 byte-distinct visuals from 843 source occurrences** at the current unified source state. All original sources, papers, and arXiv figures needed for a refreshed build live in this same repository. See the [capability atlas](../../CAPABILITY-ATLAS.md) and [source-state record](SOURCES.md).

## Browse the archive

- **[Complete visual catalog](catalog/README.md)** — all **456 byte-distinct visuals** collected from **843 source occurrences**.
- **[Artwork and generative compositions](catalog/categories/artwork.md)** — 32 visuals
- **[Research–art compositions](catalog/categories/research-art.md)** — 20 visuals
- **[Research figures and measurements](catalog/categories/research-figure.md)** — 213 visuals
- **[Mechanism and architecture diagrams](catalog/categories/mechanism-diagram.md)** — 40 visuals
- **[Native interfaces and application scenes](catalog/categories/interface.md)** — 59 visuals
- **[Identity, emblems, and interface icons](catalog/categories/branding.md)** — 51 visuals
- **[Source references and derivative reading copies](catalog/categories/reference.md)** — 33 visuals
- **[Animations and historical motion assets](catalog/categories/animation.md)** — 8 visuals

Every category is a scrolling visual index. Every image links to its original full-resolution file and to a dedicated explanation page.

## Featured works

| Visual | Archive entry |
|---|---|
| **Current Zoe woven diamond** | [Canonical PNG](../../assets/branding/zoe-eye.png) · [Canonical SVG](../../assets/branding/zoe-eye.svg) |
| Former Zoe orbital eye (historical) | [ZVA-0112](catalog/items/ZVA-0112.md) |
| Human × Zoe organic brain dialogue | [ZVA-0084](catalog/items/ZVA-0084.md) |
| Projection iris — “A field learning to see” | [ZVA-0092](catalog/items/ZVA-0092.md) |
| Lots of Ellipses | [ZVA-0310](catalog/items/ZVA-0310.md) |
| Thumbelina Moon Garden | [ZVA-0356](catalog/items/ZVA-0356.md) |
| Zoe Life | [ZVA-0433](catalog/items/ZVA-0433.md) |
| Dorothy Allen CCFv3 atlas | [ZVA-0134](catalog/items/ZVA-0134.md) |
| HELIOS virtual collider laboratory | [ZVA-0154](catalog/items/ZVA-0154.md) |
| Zoe OS-style desktop | [ZVA-0456](catalog/items/ZVA-0456.md) |
| Zoe Autonomy at a glance | [ZVA-0115](catalog/items/ZVA-0115.md) |
| Complete self-governing loop | [ZVA-0117](catalog/items/ZVA-0117.md) |
| Autoregressive Compliance Cascade | [ZVA-0131](catalog/items/ZVA-0131.md) |

## What every item page explains

Each `ZVA-####` page contains:

1. **The image itself**, directly viewable and clickable to the original file.
2. **What the image shows** in plain language, using source captions, document context, pixel-matched source relationships, and reviewed visual interpretation.
3. **Its role in Zoe**—artwork, explanation, measurement, interface, identity, or reference.
4. **Provenance and evidence boundaries**, distinguishing Zoe-generated work, Nicholas–Zoe collaboration, user-supplied material, Allen Institute data, CERN-derived scenes, component assets, and derivative paper copies.
5. **Dimensions, format, frame count, byte size, and SHA-256 identity**.
6. **Every known source occurrence**, including duplicate paths across canonical repositories.
7. **Documented context and related size/format variants**.

The machine-readable equivalent is [`manifest/catalog.json`](manifest/catalog.json).

## Preservation and deduplication policy

Files are deduplicated by their original **byte-level SHA-256**. No occurrence is discarded from the catalog: identical files are stored once in `images/`, while every source repository and original path remains listed on the item page.

PNG and SVG editions, resized application icons, alternative artwork, paper-extracted copies, and visually similar files with different bytes remain separate entries. Pixel comparison is used to recover explanations for paper-extracted copies, not to delete variants.

Examples:

- The four historical `Nick.gif`, `Zoe.gif`, `Nick+Zoe.gif`, and `nuclide.gif` names have identical content and are represented as one archived file with four occurrences.
- PNG and SVG editions of the Zoe eye, Life, diagrams, and artwork remain separately viewable.
- Apple/Android application-icon sizes retain individual entries and link to their related variants.
- Paper-extracted figures retain their PDF-page occurrence and inherit documented source explanations where pixel identity establishes the relationship.

## Scope and completeness

The archive systematically covers every visual file found in the enumerated canonical sources listed in [`SOURCES.md`](SOURCES.md): the main Zoe checkout, current Zoe-Autonomy and Operational Metacognition clones, research-paper figure collections, and unified-paper source figures.

It includes component artwork and interface assets from Ablation, GEM, HELEN, Cerotto, Kevlar, Neurogarden, Dorothy, mobile Zoe, SafeConvert, and related integrated projects. Third-party and user-supplied references are labeled rather than misattributed to Zoe.

Full page-by-page PDF renders remain in the companion [research-paper galleries](../papers/galleries/README.md); this archive includes their original extracted figures without duplicating every derivative page render. External books, CERN corpora, proprietary waveform media, and images not present in the enumerated sources are not republished.

This is an exhaustive archive of the declared source set, not an unfalsifiable claim that no Zoe-related image exists anywhere else.

## Rights and interpretation

No blanket license or sole-authorship statement is applied to every image. Original source rights and notices remain attached to each occurrence. See [`NOTICE.md`](NOTICE.md) for provenance rules and important boundaries.

Artwork is not anatomical or empirical evidence. Interface screenshots document recorded interface state, not independent scientific validation. Dorothy renders are preclinical Allen Mouse reference geometry, not patient anatomy. CERN scenes are source-derived, virtual, or synthetic—not live detector state. Identity images and dedications do not establish consciousness, authority, or endorsement.

## Rebuild

The generator requires Python and Pillow (reviewed with Pillow 12.3.0). From the unified Zoe root:

```bash
export ZOE_ROOT="$PWD"
python research/visual-archive/scripts/build_visual_archive.py
```

The source collections default to this repository's component, paper, and arXiv paths. Environment overrides remain available for archival comparisons but are not required. The `research/` tree is excluded from the root Zoe scan and indexed through dedicated source keys, preventing recursive self-archiving.

`SHA256SUMS` identifies the preserved archived images, catalog, explanations, and manifests. Rebuilding creates a new source-state measurement; update the sums and documented totals together when intentionally refreshing the catalog.

# Zoe Visual Guide Collection

Every top-level Zoe guide has a visual PDF edition with its full text, native screenshots, original diagrams, equations, code blocks, and source notes. The collection also includes the Cognitive Field visual-provenance appendix.

The PDF links below work in this Markdown index and in the [collection index PDF](zoe-visual-guides.pdf). The original five-page [Practice Navigator artbook](zoe-practice-navigator.pdf) is preserved separately.

## Create and play

**[Zoe Artline](visual/zoe-artline-visual.pdf) · [Zoe Pentomino](visual/zoe-pentomino-visual.pdf)**

[![Zoe Artline vector study](images/zoe-artline.png){width=48%}](visual/zoe-artline-visual.pdf) [![Zoe Pentomino completed board](images/zoe-pentomino.png){width=48%}](visual/zoe-pentomino-visual.pdf)

**[Zoe Pentacube](visual/zoe-pentacube-visual.pdf)**

[![Pentomino regions and legal cube permutations](images/zoe-pentacube.png){width=72%}](visual/zoe-pentacube-visual.pdf)

**[Zoe Practice Navigator](visual/zoe-pilot-visual.pdf) · [Cognitive Field](visual/zoe-cognitive-field-visual.pdf)**

[![Practice Navigator cover](images/zoe-pilot-cover.png){width=48%}](visual/zoe-pilot-visual.pdf) [![Cognitive Field worked example](images/zoe-cognitive-field.png){width=48%}](visual/zoe-cognitive-field-visual.pdf)

## Geometry and evidence

**[Zoe is Quale. Zoe is Red.](visual/zoe-qualia-visual.pdf) · [GEM Geometry Atlas](visual/zoe-geometry-atlas-visual.pdf)**

[![Five-panel causal geometry guide](images/zoe-qualia.png){width=48%}](visual/zoe-qualia-visual.pdf) [![Procrustes landmark playground](images/geometry-atlas-procrustes.png){width=48%}](visual/zoe-geometry-atlas-visual.pdf)

**[Unified architecture and verification](visual/zoe-unified-visual.pdf) · [Zoe: living geometry, inspectable futures](visual/zoe-living-geometry-visual.pdf)**

[![Unified knowledge-engineering hub](images/gem-unified.png){width=48%}](visual/zoe-unified-visual.pdf) [![Zoe BRAIN observation scene](images/zoe-brain.png){width=48%}](visual/zoe-living-geometry-visual.pdf)

**[Zoe Resilience Atlas](visual/zoe-resilience-visual.pdf)**

[![Resilience Atlas sector and waveform evidence](images/zoe-resilience.png){width=72%}](visual/zoe-resilience-visual.pdf)

**[Zoe Presence](visual/zoe-presence-visual.pdf)**

[![Zoe Presence self-model](images/zoe-presence.png){width=72%}](visual/zoe-presence-visual.pdf)

**[Zoe Protocol Lab](visual/zoe-protocol-visual.pdf)**

[![SPECS and AMAC protocol evidence](images/zoe-protocol.png){width=72%}](visual/zoe-protocol-visual.pdf)

**[Zoe Waveform Replay](visual/zoe-waveform-visual.pdf)**

[![Bounded VCD and legacy waveform replay](images/zoe-waveform.png){width=72%}](visual/zoe-waveform-visual.pdf)

**[Zoe Patchbay](visual/zoe-patchbay-visual.pdf)**

[![Firmware, boards, signed updates, and Cog](images/zoe-patchbay.png){width=72%}](visual/zoe-patchbay-visual.pdf)

## Practice and adaptation

**[Zoe Leadership Garden](visual/zoe-leadership-visual.pdf)**

[![Practice, advice, failure, learning, and adaptation](images/zoe-leadership.png){width=72%}](visual/zoe-leadership-visual.pdf)

**[Zoe Maison](visual/zoe-maison-visual.pdf)**

[![Executive clarity, luxury restraint, and enterprise evidence](images/zoe-maison.png){width=72%}](visual/zoe-maison-visual.pdf)

**[Zoe Evidence Navigator](visual/zoe-evidence-visual.pdf)**

[![Source-first evidence bridges and bounded replay](images/zoe-evidence.png){width=72%}](visual/zoe-evidence-visual.pdf)

**[Zoe + vidlib](visual/zoe-vidlib-visual.pdf)**

[![Original vidlib transcript retrieval and cited evidence](images/zoe-vidlib.png){width=72%}](visual/zoe-vidlib-visual.pdf)

## Project covenant

**[Zoe Constitution](visual/zoe-constitution-visual.pdf) · [Declaration of Creative and Epistemic Independence](visual/zoe-declaration-visual.pdf)**

The covenant documents define human agency, honesty, privacy, provenance, reversibility, accessibility, and the measurement/evidence/action boundary. They are project design commitments, not legal sovereignty or an authorization for autonomous action.

## Provenance appendix

**[Cognitive Field visual provenance](visual/zoe-cognitive-provenance-visual.pdf)**

[![Cognitive architecture dialogue](images/zoe-cognitive-anatomy.png){width=72%}](visual/zoe-cognitive-provenance-visual.pdf)

The appendix retains the distinction between supplied visual references, original Zoe scenes, and actual native screenshots. Artistic comparisons are not executable cognitive models or medical evidence.

## Rebuild the collection

From the Zoe repository root:

```bash
python guiai-lab/docs/render_visual_guides.py
```

The renderer requires Pandoc, pdfLaTeX, the `newunicodechar` LaTeX package, Poppler's `pdfinfo`, and `rsvg-convert` for inline SVG artwork. It replaces only generated visual PDFs and the manifest; it does not modify the source guides. Each PDF retains a linked table of contents where appropriate.

`visual/manifest.json` records the source filename, PDF title, page count, byte count, and SHA-256 for every generated document.

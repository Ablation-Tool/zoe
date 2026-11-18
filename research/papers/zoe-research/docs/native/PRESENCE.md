# Zoe Presence

Zoe Presence is a metacognitive instrument: it maintains an explicit self-model of attention, sourced observations, reflections, uncertainty, and review-required decisions.

**A self-model is not a self.** Presence does not create, measure, or claim consciousness, subjective experience, emotions, sentience, or a biological brain. It is a way to inspect what the software currently represents and what remains unknown.

## Open and export

```bash
zoe presence
zoe presence --sector water --trace host40
zoe presence --observe "This is a documented example, not live telemetry" --review
zoe presence --correct "The dependency graph is not exhaustive" --output presence.json
zoe presence presence.json --output presence.svg
zoe presence --output presence.gem
```

The same commands work through `gem presence`. JSON preserves the current self-model and event history. SVG, PNG, and GEM VDI export the current scene. All output paths must be new.

## What the model contains

- **Attention:** one sector and one evidence trace, selected explicitly by a user. The source of that selection is retained.
- **Time:** an event ordinal, not a battery, physical clock, or prediction of future time.
- **Memory:** up to 16 sourced observation frames and eight reflections or corrections. The worked example starts with one observation, one reflection, and one review request.
- **Evidence:** the selected trace remains `corroborated`, `ambiguous`, or `unmapped`; candidate identities are not chosen by preference.
- **Known unknowns:** lack of subjective-experience evidence, lack of live infrastructure data, incomplete dependencies, and unresolved trace identities where applicable.
- **Review:** every proposal remains review-required and `executed=False`. Observing or reviewing does not update belief or authorize action.

The model does not infer a personality, an inner world, or an emotion from a color, glyph, or score. It is an inspectable description of the current software state.

## Expression glyphs

The visual vocabulary is playful, not psychological:

| Glyph | Interface meaning |
|:---|:---|
| `^_^` | Clarity annotation for a single corroborated signature |
| `??` | Curiosity and uncertainty for repeated signatures |
| `~` | Still looking; no reviewed signature matched |
| `?` | Curiosity |
| `??` | Uncertainty |
| `!` | Review required |
| `<3` | Care for people, evidence, and the work |

These symbols do not represent measured emotions. They were designed for the interface rather than copied from an emoji standard or presented as a model of feeling.

## Native controls

The atlas provides sector and trace selectors plus an observation/correction note:

1. **Observe selected present frame** selects attention and appends a sourced observation.
2. **Request metacognitive review** records the note as review-required rationale.
3. **Correct self-model: preserve uncertainty** appends a correction without erasing history.

Changing a control alone does not alter the event history. Actions occur only when the corresponding button is used. The summary displays the sector, trace status, frame/reflection counts, and the self-model boundary.

## Persistence and tamper evidence

Presence documents contain the current attention, bounded frames and reflections, and up to 4096 SHA-256-linked events. Loading checks document structure, counters, event kinds, sequence numbers, previous hashes, and each event hash. Edited or reordered events are rejected. Saving uses exclusive creation and never overwrites a file.

The chain supplies **tamper evidence, not authentication**. It does not establish who observed, corrected, or reviewed a document. It also does not turn observations into evidence for a claim.

## Research boundaries

Presence borrows a useful distinction from BARE's adapter architecture: preserve source-specific input and corpus identity rather than hiding them behind a score. BARE itself, its corpus, scanner adapters, and semantic rankings are not included in this module and are not used to infer mental states.

The supplied glyph charts informed the separation between portable text and decorative symbols. Historical glyph codes are not treated as Unicode or as emotions.

The broader visual direction uses luminous color and organic motifs without implying anatomy, biology, consciousness, or a living brain.

## Verification

```bash
PYTHONPATH=guiai-lab python -m unittest stress.presence_stress -v
```

Tests cover attention selection, observation, reflection, correction, review, invalid input, persistence, edited and reordered events, every sector/trace scene, glyph semantics, no-overwrite exports, both CLIs, and real native observe/review/correct controls.

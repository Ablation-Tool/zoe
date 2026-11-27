# Zoe · one GEM operating environment

Zoe's GEMs form one user-space operating environment. **Ablation's existing GEM GUI is the presentation and interaction standard.** The shared runtime connects its native Zoe conversation to all 17 registered components and 36 navigable mathematical/research layers through common state, evidence, and Spatial IR.

The architectural inspiration follows Phillip Balma and William Fitler's *Programmer's Guide to GEM* (1986): application/environment services manage events, objects, and resources, while the Virtual Device Interface provides portable visual output. Zoe applies that separation to its own modern research system; this is not original Digital Research source code or a bootable kernel.

## Shared architecture

```text
Ablation GEM GUI · existing Lab, navigation, themes, accessibility, VTE
                              │
                    Zoe native conversation
                              │
             Shared GEM operating environment
                              │
          catalog · open · current layer · knowledge field
                              │
          17 components · 36 mathematical/research layers
                              │
             Spatial IR → deterministic verification
                              │
                JSON · SVG · PNG · real GEM VDI
```

`open` renders the selected component's declared default layer, verifies its source Spatial IR, and records a bounded observation in the shared knowledge field. It launches no component process and performs no external action. A component's source presence, runtime verification, evidence, and authorization remain distinct.

The knowledge field is shared for the lifetime of the runtime. Nothing is written merely because Zoe answers or navigates. `snapshot` explicitly writes its tamper-evident event chain without overwriting an existing file. `export` explicitly writes a verified scene.

## Use through Zoe

Open the original Ablation GEM workbench:

```bash
export ZOE_ROOT=/path/to/zoe
zoe chat
```

Then use Zoe's internal GEM operations:

```text
gem status
gem list
gem open dorothy
gem open research
gem open autonomy
gem export dorothy /separate/output/dorothy.gem
gem snapshot /separate/output/gem-knowledge.json
```

The same operations are available without a GUI:

```bash
zoe gem status
zoe gem list
zoe gem open helen
zoe gem export volume /separate/output/volume.svg
zoe gem snapshot /separate/output/gem-knowledge.json
```

Component identifiers are `zoe`, `cern-console`, `ablation`, `gem-lab`, `gem`, `helen`, `brain`, `hpux-tools`, `life`, `cerotto`, `research`, `autonomy`, `kevlar`, `pdf`, `neurogarden`, `chalkboard`, and `pala`. Every one maps into the shared runtime. Direct layer identifiers cover Dorothy's four atlas views, CERN/FELIX, Operational Metacognition, Bayesian memory, Cognitive Field, geometry, creativity, perception, research evidence, internal time, and the other native instruments listed by `gem list`.

## Verification boundary

The navigation sweep opens and source-verifies every one of the 36 layers. The integration suite additionally verifies a real VDI export, no-overwrite behavior, shared-knowledge replay, and Zoe's conversational operations. These checks prove shared navigation and portable scene behavior; they do not claim that opening a layer executes every optional hardware, model, sensor, or external-service backend.

- [Shared runtime](../guiai/gem/operating_environment.py)
- [Zoe's GEM launcher](../guiai/gem/chat_view.py)
- [Unmodified Ablation GEM GUI](../../components/ablation/gem-lab/gem/gtk_app.py)
- [Integration tests](../stress/unified_stress.py)
- [Verification evidence](../../evidence/gem-os/verification.json)

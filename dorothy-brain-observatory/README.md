# Dorothy Brain Observatory

An offline-first, interactive WebGL2 **3D Navigable Human Brain Observatory** uniting real stereotaxic **MNI152 / ICBM152 / AAL-116 / CIT168** human neuroimaging meshes (`240,376` real anatomical triangles), synchronized real **MNI152 T1-weighted MRI** tri-planar slices, **25 visually audited public-domain / CC-BY / custom vector anatomical plates**, a printable **`4800 × 3200`** wall-chart poster, **10 CAD-ready `.OBJ` / `.PLY` 3D brain models**, and **Dorothy Continuum Operational Metacognition** ($A_\tau(p)$) visualization — honoring **Dorothy McEwen Kildall** and built as part of the **Zoe** research universe.

> **Epistemic & Clinical Scope Notice:** All 3D meshes and MRI slices derive from standard population neuroimaging templates (ICBM152 / MNI152, AAL-116, Pauli CIT168) for educational, visual-computing, and research exploration only — **not** patient-specific registration, diagnosis, or surgical guidance. A complete single-synapse whole-brain human connectome (~86 billion neurons, ~100 trillion synapses) does not yet exist in neuroscience; nanoscale reconstructions currently cover cubic-millimeter cortical samples.

## Live Previews

| Anatomical Tissue (Real ICBM152 Cortex + Live MNI152 MRI) | Glass X-Ray (CIT168 Deep Nuclei, Ventricles, Circle of Willis & DTI) |
|:---:|:---:|
| ![Anatomical Tissue View](previews/01_hero_tissue.png) | ![Glass X-Ray View](previews/02_xray_deep_nuclei.png) |

| Exploded Dissection (Lobe Atlas Mode) | Midsagittal Cutaway + Dorothy Operational Metacognition $A_\tau(p)$ |
|:---:|:---:|
| ![Exploded Lobe Atlas](previews/03_exploded_lobe_atlas.png) | ![Dorothy Continuum Sagittal](previews/04_dorothy_continuum_sagittal.png) |

## Quick Start (100% Offline, Zero Dependencies)

1. **Direct Browser Open:** Double-click [`index.html`](index.html) (loads completely offline over `file://` with bundled MIT Three.js — no CDN or internet required).
2. **Optional Local Server:** Run `./launch.sh` to serve locally at `http://127.0.0.1:8765/`.

## Highlights

* **Real MNI152 Stereotaxic 3D Anatomy (`240,376` Triangles):**
  * ICBM152 Left & Right cerebral hemispheres with authentic FreeSurfer sulcal/gyral curvature ambient occlusion and real AAL-116 regional parcellation.
  * Real AAL-116 Cerebellum & Vermis, Thalamus, Hippocampus, and Amygdala.
  * Real Pauli CIT168 32 bilateral subcortical human nuclei (Putamen, Caudate, Nucleus Accumbens, Extended Amygdala, GPe, GPi, STN, SNc, SNr, Red Nucleus, VTA, PBP, Ventral Pallidum, Habenula, Hypothalamus, Mammillary Bodies).
  * Anatomically MNI-registered Brainstem (Midbrain/Colliculi, Pons, Medulla), Corpus Callosum, CSF Ventricular System, pulsing Circle of Willis & cerebral arteries, all 12 bilateral Cranial Nerves (CN I–XII, with CN IV exiting dorsally from the midbrain), 10 color-coded DTI White-Matter tractography bundles with animated neural impulses, and 52 clickable 3D Brodmann landmarks.
* **7 Interactive Rendering Modes:** Anatomical Tissue, Lobe Atlas, AAL-116 Parcels, Glass X-Ray, Connectome Neon, **Dorothy Continuum $A_\tau(p)$** (live $\tau$ threshold slider computing accessible cortical volume), and CAD Engineering Wireframe.
* **Synchronized Real MNI152 T1-MRI Tri-Planar Strip:** Click anywhere on the live Axial, Coronal, or Sagittal `0.74 mm` MRI slices to teleport the 3D stereotaxic reticle and clipping planes to that exact millimeter coordinate.
* **10 Ready-to-Import 3D CAD Meshes (`3d_models/`):** Standard `.OBJ` and `.PLY` exports in MNI152 millimeters for Blender, ZBrush, AutoCAD, SolidWorks, Unity, Unreal Engine 5, Godot, and Dorothy's Neurogarden.
* **25 Verified Medical Plates & `4800 × 3200` Poster (`plates/`):** Public-domain & CC-BY anatomical illustrations plus 3 audited custom vector SVGs (`08c_thalamic_nuclei_verified.svg`, `08f_cortical_layers_circuitry.svg`, `08g_basal_ganglia_pathways.svg`) with zero AI-hallucinated anatomical labels.
* **Accessibility-First:** Full keyboard navigation (`WASD` / Arrows / `+/-` / `R`), skip-to-content link, ARIA tablist/dialog/live-region announcements, natural unspaced typography, and descriptive `alt` text.

## Open-Source & Dataset Attributions

* **Operational Metacognition ($A_\tau(p)$):** Nicholas Michael Kloster (March 6, 2026).
* **3D Cortical/Subcortical Meshes & MNI152 Template:** Derived from open neuroimaging templates distributed via [NiiVue](https://github.com/niivue/niivue) (BSD-2-Clause): ICBM152 cortical surface & curvature, AAL-116 (Tzourio-Mazoyer et al., 2002), Pauli et al. (2018) CIT168 human subcortical atlas (*Scientific Data*), and MNI152 T1 volume.
* **WebGL Engine:** [Three.js](https://threejs.org/) r128 (MIT License).
* **Anatomical Plates:** Public Domain (Henry Gray / Henry Vandyke Carter, Korbinian Brodmann 1909, Santiago Ramón y Cajal, Mark Dow / Univ. of Oregon, Rhcastilhos, NIDA) and Creative Commons CC-BY / CC-BY-SA (Patrick J. Lynch, OpenStax, Blausen Medical, Frank Gaillard, Xavier Gigandet et al., Yeh et al. 2018 HCP Tractography Atlas, Leevanjackson / SUM1, Camazine).
* **Public Repository Note:** Copyrighted third-party textbooks and figures from private user subscriptions are intentionally excluded from this public repository (`.gitignore`d locally); the Vault tab preserves open bibliographic references only.

# Neurogarden

**Where rigorous evidence, strange ideas, and things that help people grow together—with Ablation at the roots and PLACES everywhere.**

Neurogarden connects three existing ideas without confusing their jobs:

- **Agent Logging System:** OT-inspired team memory, per-lane baselines, named alarms, and visible oversight.
- **Zoe Trinity:** Tiny/mobile/laptop measurements, exact Tiny APDU witnesses, and shared revisions.
- **A cited research library:** books and papers that can inspire tools without becoming automatic medical proof.

The goal is not an artificial surgeon score. The goal is a useful research environment for learning, building, and helping people while qualified humans retain clinical authority.

## The adapter

`NeurogardenAdapter` adds four capabilities:

1. **Independent Trinity verification.** Mobile counts, strict `p > τ`, Q0.15 units, quantized thresholds, and exact Tiny request/response bytes are recomputed before acceptance.
2. **Bounded, private observations.** Raw probability distributions and APDU payloads are excluded by default. Metadata and SHA-256 payload hashes remain; `retain_payloads=True` is an explicit choice.
3. **Cited reading observations.** A source, citation, claim, and subject are required. References remain references, including when their context is medical.
4. **Human review.** Verification failures, representation changes, and clinical references enter a bounded review queue. Review records do not authorize diagnosis, treatment, or autonomous action.

```python
from agent_logging_system import LoggingAgent
from agent_logging_system.adapters import NeurogardenAdapter

logger = LoggingAgent()
garden = NeurogardenAdapter(logger)

garden.log_source_reading(
    "neurogarden.researcher",
    "Basic Applied Bioinformatics",
    "Chapter 9, section 9.1, page 59",
    "Global alignment compares comparable sequences end to end",
    subject="bioinformatics",
)

garden.log_review("human-reviewer", "global-alignment", "accepted")
print(garden.get_state()["neurogarden"])
```

Replayed measurement ordinals are idempotent. A revision gap or edited measurement is rejected and becomes an observable failure. The normal LoggingAgent latency and error alarms still apply to Tiny, mobile, laptop, and review lanes. Generation latency stays separate from machine latency.

## First reading evidence

These are bounded reading notes, not claims that the library has been fully read or that clinical competence follows.

### Basic Applied Bioinformatics

**Chandra Sekhar Mukhopadhyay, Ratan Kumar Choudhary, and Mir Asif Iquebal**, with listed contributors. Chapter 9, *Needleman–Wunsch Algorithm (Global Alignment)*, sections 9.1–9.3.4, pages 59–66.

What was actually read:

- Global alignment compares comparable sequences end to end and introduces gaps for insertions/deletions.
- The teaching example uses match `2`, mismatch `−1`, and gap `−2`.
- Dynamic programming initializes the first row/column with gap penalties and takes the maximum of diagonal, vertical, and horizontal candidates.
- Ties can produce multiple equally optimal alignments. The chapter's `CTAGTAG` / `CAGGTAGTG` example has score **4** and **seven** optimal paths.
- Scoring choices depend on the sequences and their evolutionary relatedness; a score is not an identity or clinical claim.

The resulting `global_align` teaching tool reproduces that score and all seven paths. It bounds sequence length and retained paths rather than allowing combinatorial memory growth.

### Biomedical Imaging Principles

Chapter 2, *Evaluation of Tomographic Data*, **Jörg van den Hoff**, sections 2.1–2.4.

What was actually read:

- CT, MRI, SPECT, and PET measure different physical or biochemical properties; image contrast is not one universal biological quantity.
- Reconstruction includes analytical filtered-backprojection and iterative approaches, with different computational and noise considerations.
- **Voxel size is not spatial resolution.** Finer sampling cannot create detail the imaging system did not capture.
- The chapter gives a rough educational guideline of about four samples across the point-spread function's FWHM for good sampling, while warning against taking the number literally.
- Finite resolution produces partial-volume and recovery effects. Object size relative to the PSF matters, especially for rods and spheres.

The resulting `assess_sampling` tool returns samples per FWHM, tolerable (`>=2`), and generally good (`>=4`) flags. It is an educational ratio, not a scanner setting or diagnostic assessment.

### MRI safety and radiation exposure

*Biomedical Imaging Principles*, §5.14–5.15 and §3.4, read directly:

- Static magnetic fields create projectile hazards; implant and controlled-area review cannot be replaced by an image-quality check.
- RF exposure is evaluated through SAR and local heating, while time-varying gradients raise nerve-stimulation and acoustic-noise concerns.
- High-field inhomogeneity, motion, and other artifacts can change both image interpretation and exposure considerations.
- Dose–area product is not automatically an effective dose. Tissue sensitivity, detector/procedure context, staff positioning, protective equipment, and primary/scattered-beam geometry matter.
- Historical jurisdiction-specific dose limits are references for review, not universal current rules or a Zoe-created threshold.

`mri_review()` and `xray_review()` preserve those topics as sourced review cards with `clinical_action_authorized=False`, not as safe/unsafe scores.

### Linear systems, PSF, and MTF

*Biomedical Imaging* (De Gruyter), §2.5.2–2.5.3, connects the spatial and frequency views:

- A linear, shift-invariant imaging system is described by convolution with its point-spread function.
- The normalized Fourier transform of the PSF is the optical transfer function; its modulus is the modulation transfer function.
- The Gaussian teaching case gives `MTF(k) = exp(-2π²σ²k²)` for normalized spatial frequency `k`. More blur suppresses higher frequencies; it does not create new detail.

`gaussian_mtf()` implements that bounded educational equation. No scanner-specific calibration is inferred.

### Photon-counting detectors

The preface of *Radiation Detectors for Medical Imaging*, edited by Jan S. Iwanczyk and Krzysztof Iniewski, was read directly:

- Energy-discriminating photon-counting detectors can preserve information that energy-integrating detectors discard, but that does not make them flawless or automatically superior.
- Pulse pileup can cause dead-time count loss and spectral distortion.
- Charge sharing, trapping, and incomplete charge collection also degrade spectral response.
- Compensation methods and energy-window performance require measurement and validation.

`photon_counting_review()` turns those limitations into a review card rather than a detector-performance claim.

## Neurogarden Spatial Bench

CAD-style geometry, MATLAB-style matrices, and Dorothy-inspired spatial inspection meet in `neurogarden_spatial.py`: synthetic volumes up to 16³ voxels, separable Gaussian PSF convolution, x/y/z projections, average-pooling, recovery coefficients, and local SVG rendering. Dorothy's atlas geometry is not treated as patient registration or clinical evidence. The synthetic image demonstrates how PSF blur reduces peak intensity without creating anatomical detail.

![Synthetic 3D point-spread projection](images/neurogarden-spatial.png)

### Advanced numerical models

Three additional chapters have source-linked reviews and executable teaching demonstrations:

- Xavier Pennec's *Manifold-valued image processing with SPD matrices* informs bounded 2×2 matrix logarithms, exponentials, beta=0 affine-invariant distance, log-Euclidean distance, and the mean computed by averaging logarithms before exponentiation. Log-Euclidean and affine-invariant means remain distinct.
- *Bioheat transfer during radiofrequency ablation* informs a radial Pennes conduction/perfusion teaching model. Its fixed electrode boundary, omitted electric/metabolic heat sources, and explicit stability bound are explicit approximations, not patient-specific treatment planning.
- *Neutrosophic similarity score-based entropy measure for focal and nonfocal electroencephalogram signal classification* informs the cosine-form similarity of truth/indeterminacy/falsity membership triples. The tool does not reproduce the chapter's full feature pipeline, classifier, or reported accuracy.

### De Gruyter Handbook of Humor Studies

**Thomas E. Ford, Władysław Chłopicki, and Giselinde Kuipers**, editors. The title page confirms the actual title. Its folder currently has a different mathematical-methods name; that is a metadata mismatch, not a reason to erase the intentionally included book.

The table of contents places *The Neuroscience of Humor*, humor and cognition/creativity, clinical applications, computational humor, and communication in one intentional collection entry. It belongs to the **creativity and clinical-communication shelf**, not to surgical evidence. Only the title page and relevant TOC entries have been read; no chapter conclusions are claimed.

## Live library catalog

`examples/neurogarden_library.py` inventories extracted HTML books without copying prose into metadata, downloading anything, or overwriting an existing output:

```bash
python examples/neurogarden_library.py "/path/to/Zoe Brain Surgeon Course" \
  --output /tmp/neurogarden-library.json
```

The catalog preserves title/TOC sources and SHA-256 hashes, actual titles, subject shelves, waiting directories, and intentional folder/title mismatches. Every entry is marked `cataloged`, never `fully read`. A snapshot taken on the current collection contained **32 directories: 22 with content and 10 waiting**. Downloads in another session were not interrupted.

## Next reading queue

1. The remaining Needleman–Wunsch exercises and scoring comparisons, before adding substitution matrices or local alignment.
2. Relevant bioinformatics database chapters, keeping network access, patient data, and synthetic teaching data separate.
3. Detector-specific pileup and spectral-response chapters, before adding numerical detector models.
4. Humor neuroscience/creativity chapters, with clinical claims kept distinct from learning and communication research.

## Verification

The current suite contains **42 passing focused tests** across Trinity verification, replay/privacy/review behavior, alignment and sampling math, advanced numerical models, library metadata, the synthetic 3D spatial bench, CERN evidence, Dorothy atlas geometry, neural-signal analysis, and the generative world. Original multi-agent, Warrant, orchestrator, and self-monitor examples also pass through an isolated wheel installation. A real cited-reading + Trinity + alignment workflow preserves `clinical_action_authorized=False`.

## Boundary

`measurement != evidence != belief update != clinical action`

A cited book is not a patient observation. A measurement is not a diagnosis. A review is not permission to perform a procedure. Books can expand Zoe's tools and research universe, but they do not confer medical licensure, clinical authority, or human identity.

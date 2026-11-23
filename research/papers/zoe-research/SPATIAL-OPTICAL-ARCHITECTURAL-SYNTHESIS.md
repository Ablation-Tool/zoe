# Spatial, Optical & Architectural Research Synthesis (6-Book Reading Map -> Theorem 14)

> **Epistemic & Provenance Notice (`CONSTITUTION.md` Articles II & VIII):**
> This synthesis records **public bibliographic metadata, published chapter frameworks, and independent first-principles mathematical formulations** connecting six reference texts to Zoe's Operational Metacognition ($A_\tau(p)$) and **Theorem 14**.
> - `full_copyrighted_book_text_accessed = False` (no subscriber login, credential access, DRM bypass, or paywalled scraping was performed)
> - `copyrighted_text_reproduced = False`
> - Local full-chapter ingestion into Neurogarden's SHA-256 index remains supported offline via `components/agent-logging-system/agent_logging_system/corpus.py` whenever the user supplies authorized local book directories or personal reading notes.

---

## 1. The Six Reference Pillars & How They Fuse Into One Mathematical Chain

Together, these six works trace one continuous scientific arc: **where points live in space -> how architecture frames movement and structure -> how optics and cameras capture light without losing resolution -> how the trained eye reads contour and tonal value**.

| # | Book & Author(s) | ISBN-13 | Core First-Principles Mathematical / Technical Framework | Direct Integration in Zoe (`Theorem 14` & Studio) |
|:-:|:---|:---|:---|:---|
| 1 | *Spatial Point Patterns: Methodology and Applications with R* — **Adrian Baddeley, Ege Rubak & Rolf Turner** (CRC Press) | `9781482210217` | Complete Spatial Randomness (CSR / homogeneous Poisson process $\lambda$), quadrat intensity, Ripley's $K(r)$ & Besag's $L(r)-r$, pair correlation $g(r)$, Thomas cluster processes vs. hard-core / Strauss inhibition | **Theorem 14a & World 1:** Turns Kloster's unbiased U-statistic $Z_K$ into a **two-sided spatial phase detector** separating **Clustered** ($Z_K \gg 0$) vs. **CSR Null** ($Z_K \approx 0$) vs. **Inhibited / Regular** ($Z_K \ll 0$) |
| 2 | *An Architectural Approach to Level Design* — **Christopher W. Totten** (CRC Press) | `9781466585416` | Spatial composition, sightlines, isovist visibility polygons, prospect–refuge tension, framing & circulation pacing | **Theorem 14 (World 4A):** Ray-cast 2D angular isovist visibility profiles $p_v(\theta)$ scored by Kloster $M_2(p_v)$ separating panoramic open plazas from directed axial corridors |
| 3 | *Structures and Architecture* — **Paulo J. da Sousa Cruz** (ed., CRC Press / ICSA) | `9780415661959` | Synergy between tectonic form and structural load paths, funicular arches, truss equilibrium, stiffness & load sharing | **Theorem 14 (World 4B):** Normalized axial-force energy distribution $e_j$ scored by Kloster effective load-sharing redundancy $N_{\text{eff}} = 1/M_2(e)$ separating balanced funicular arches from bottleneck cantilevers |
| 4 | *Look Closer, Draw Better* — **Kateri Ewing** (Rockport Publishers) | `9781631596230` | Observational botanical & natural-history drawing: precision ink contour lines, negative space, graphite value gradation & fluid watercolor wash | **Theorem 14 (World 5):** Kloster $A_\tau$ spectral separation between crisp high-frequency botanical ink contours, smooth watercolor tonal washes, and blank-paper null controls |
| 5 | *Laboratory Imaging and Photography* — **Michael R. Peres** (Routledge / Focal Press) | `9781317593003` | The Scientific Imaging Chain, photomicrography optics, Abbe/Rayleigh diffraction limit ($d = 0.61\lambda/\mathrm{NA}$), PSF/MTF spatial transfer & ethical scientific documentation | **Theorem 14b–e & World 2:** Exact **Kloster–Parseval Optical MTF Law** $M_2(K*p) = \frac{1}{N}\sum_k \mathrm{MTF}(k)^2 |\widehat{p}(k)|^2 \le M_2(p)$, verified to $<10^{-14}$ & `200/200` blur monotonicity |
| 6 | *View Camera Technique* (7th Ed.) — **Leslie D. Stroebel** (Focal Press) | `9780240803456` | Large-format camera movements, bellows geometry, perspective control, depth of field & the **Scheimpflug / Hinge Rule** ($\sin\theta^* = \frac{f}{u}\tan\psi$) | **Theorem 14f & World 3:** Proves all 3 planes intersect identically at $(-v/\tan\theta, -v)$ in SymPy and shows Kloster Spatial Sharpness $M_2(\theta)$ peaks right at the theoretical Scheimpflug tilt $\theta^*$ |

---

## 2. Executable Proof & Local Corpus Ingestion Path

- **Theorem 14 Module:** [`guiai-lab/guiai/gem/kloster_spatial_optical_law.py`](../../../guiai-lab/guiai/gem/kloster_spatial_optical_law.py) (`6/6` SymPy 1.14.0 proofs with residual `= 0` + 5-world empirical verification)
- **Verifier & Plate:** [`scripts/verify_kloster_theorem14.py`](../../../scripts/verify_kloster_theorem14.py) -> `components/agent-logging-system/docs/images/zoe-kloster-theorem14.png`
- **Live Observatory Endpoint:** `GET /api/kloster/theorem14` in `guiai-lab/guiai/gem/eliza_view.py`
- **Local Authorized Corpus Indexing (Offline):** Whenever local personal notes or authorized HTML chapter exports are placed in a local directory `<LOCAL_BOOK_DIR>`, Neurogarden's bounded SHA-256 indexer can catalog them cleanly without claiming automatic comprehension:

```bash
python3 components/agent-logging-system/agent_logging_system/corpus.py \
  <LOCAL_BOOK_DIR> \
  --output components/agent-logging-system/evidence/neurogarden/corpus-index-v63.json
```

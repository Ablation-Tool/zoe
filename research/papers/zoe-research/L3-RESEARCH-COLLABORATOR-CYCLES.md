# Zoe L3 Research Collaborator — Three Pre-Registered, Independently Reproduced Scientific Cycles

**Contract:** `zoe-l3-research-collaborator/v1` · **Roadmap Gate:** `AGI-ROADMAP.md` §7 (`L3 · RESEARCH-COLLABORATOR-QUALIFIED`)  
**Implementation:** [`research_collaborator.py`](../../../components/Zoe-Autonomy/src/zoe_autonomy/research_collaborator.py) · **Independent Verifier:** [`scripts/verify_l3_research.py`](../../../scripts/verify_l3_research.py)  
**Recorded Evidence Bundle:** [`evidence/l3-research/l3-cycles-report.json`](../../../evidence/l3-research/l3-cycles-report.json)

![Zoe L3 Independent 9-Stage Research Collaborator Cycles](../../../components/agent-logging-system/docs/images/zoe-l3-research-collaborator.png)

---

## 1. Scientific Integrity & Pre-Registration Protocol

To earn `L3 · RESEARCH-COLLABORATOR-QUALIFIED` honestly under `CONSTITUTION.md` (Articles II, III, V, VII, VIII, X) and `AGI-ROADMAP.md` §7, every cycle executes all **9 stages** end-to-end inside an append-only SHA-256 stage chain:

```text
1. Question Authorship
→ 2. Cited Local Literature Retrieval (130 Neurogarden reviews + monographs, SHA-256 verified)
→ 3. Pre-Registration Lock (SHA-256 locked BEFORE any measurement runs)
→ 4. Real Experiment Execution on Held-Out / Verified Repo Data
→ 5. Measurement (belief_updated = False, executed = False)
→ 6. Negative & Static Controls (permutation tests, sphere/noise nulls, naive baselines)
→ 7. Honest Interpretation (CONFIRMED or FALSIFIED — zero p-hacking)
→ 8. Independent Fresh-Process Reproduction (`scripts/verify_l3_research.py`, zero shared experiment imports)
→ 9. Next Research Question Authorship (derived directly from observed residuals & falsifications)
```

Across three unrelated scientific domains, **6 pre-registered hypotheses** were evaluated: **3 novel findings were CONFIRMED** and **3 flawed/naive hypotheses were honestly FALSIFIED and preserved visibly**.

---

## 2. Summary of the Three Independently Verified Cycles

### Cycle 1 · Temporal Information Theory & Music Rhythm Reversal (`cycle_1_music_rhythm_spectral_shift`)
- **Real Dataset:** `components/next-token-predictability/evidence/rhythm-midi/predictions.npz` (`121,392` events across 118 songs, strictly split by song parity into 59 discovery songs vs. 59 unseen held-out songs; `4,459` held-out predictions per regime × 3 regimes = **`13,377` held-out real observations**).
- **Pre-Registration Lock:** `b248a40718...` · **Cited Local Sources:** 5 SHA-256-verified entries.
- **`[CONFIRMED]` H1.1 — Cross-Regime Spectral Calibration:** Quartic concentration $M_4^{1/4}$ and unlabeled Mars auto-lens $k^*(\kappa) \approx 2.21\text{–}2.22$ outperform both Shannon entropy $H(p)$ and single-slice $A_{0.05}(p)$ across **3/3** held-out regimes (`forward`: `0.5980` vs `0.5861`/`0.5722`; `reversal_transfer`: `0.5892` vs `0.5768`/`0.5686`; `backward_matched`: `0.5729` vs `0.5709`/`0.5478`; 200-trial permutation null $p = 0.004975$).
- **`[FALSIFIED]` H1.2 — Naive Cross-Direction JSD Mixing:** Naive `JSD(p_forward || p_reversal_transfer)` scored `0.5549`, falling below single-direction $M_4^{1/4}$ (`0.5892`), Shannon (`0.5768`), and $A_{0.05}$ (`0.5686`).

### Cycle 2 · Dorothy Preclinical 3D Allen Mouse CCFv3 Morphometry (`cycle_2_dorothy_ccfv3_morphometry`)
- **Real Dataset:** All **12 SHA-256-verified Allen Mouse CCFv3 3D anatomical meshes** (`315,932` biological triangles; Wang et al. 2020, *Cell* 180(5)).
- **Pre-Registration Lock:** `aae3201a94...` · **Cited Local Sources:** 5 SHA-256-verified entries (including Neurogarden book reviews from `reviews.json`).
- **`[CONFIRMED]` H2.1 — Exact Zero-Overlap Anatomical Compactness Separation:** Brainstem & diencephalic relay nuclei (`TH` `0.3272`, `MB` `0.2743`, `HY` `0.2517`, `P` `0.1871`, `MY` `0.1699`; mean $Q = 0.2420$) exhibit strictly higher 3D isoperimetric compactness $Q = 36\pi V^2/S^3$ than telencephalic & cerebellar laminar/shell regions (`HPF` `0.1243`, `CB` `0.1121`, `Isocortex` `0.0926`, `STR` `0.0876`, `OLF` `0.0645`, `CTXsp` `0.0559`, `PAL` `0.0387`; mean $Q = 0.0822$), achieving the **exact theoretical minimum exhaustive permutation p-value** across all $\binom{12}{5} = 792$ partitions ($p = 1/792 = 0.001263$, zero overlap).
- **`[FALSIFIED]` H2.2 — Naive Gyrencephalic Super-Isometric Folding Law:** Observed mouse CCFv3 surface-to-volume scaling is $S \propto V^{0.6424}$ ($R^2 = 0.8289$), strictly **below** the Euclidean sphere exponent $2/3 = 0.6667$. Because the mouse cortex is lissencephalic while small bilateral telencephalic shells (`PAL`, `CTXsp`) have high surface-to-volume ratios, naive gyrencephalic super-isometric folding is cleanly falsified.
- **Scope Boundary:** Preclinical Allen Mouse CCFv3 reference geometry only (`clinical_action_authorized = False`).

### Cycle 3 · CERN 40 MHz `CicadaClock` Bifurcation & HELEN Asymmetry (`cycle_3_cern_clock_and_helen_asymmetry`)
- **Real Dataset:** Zoe's 40 MHz CERN-disciplined `CicadaClock` swept across 6 Kuramoto coupling values $\kappa \in \{0.00, 0.03, 0.06, 0.10, 0.18, 0.25\}$ (12/12 cryptographic `CicadaClock.replay()` runs verified) + **1,920 real HELEN forward & retrograde observations** (`onset-seed7.json.gz`).
- **Pre-Registration Lock:** `8e1ea74675...` · **Cited Local Sources:** 5 SHA-256-verified entries.
- **`[CONFIRMED]` H3.1 — Exact Adler-Kuramoto Phase-Locking Bifurcation:** Under external detuning $\Delta\phi = 0.07$ (theoretical critical coupling $\kappa_c = 0.07$), `CicadaClock` jumps sharply from unlocked drift ($R = 0.0114$ at $\kappa = 0.00$) to phase lock ($R = 0.9948$ at $\kappa = 0.10$), exceeding the randomized-phase noise control ($R = 0.0939$) by **`+0.9009`** with 12/12 cryptographic replays verified.
- **`[FALSIFIED]` H3.2 — Naive Forward/Retrograde HELEN JSD Mixing:** Naive `JSD(p_forward || p_retrograde)` on 1,920 real HELEN sequences scored `AUROC = 0.4087` (**worse than 0.50 random chance**), compared to directional $M_4^{1/4}$ (`0.8576`, perm $p = 0.004975$).

---

## 3. Independent Reproduction

Anyone can verify all 3 cycles, all 15 local citation SHA-256 hashes, all 9-stage hash chains, and exact numerical agreement (`max_delta = 0.0`, `14/14` checks) from a fresh process with zero imports from Zoe's experiment module:

```bash
# Re-run Zoe's full 9-stage L3 suite (and invoke independent subprocess verification)
zoe chat --cli --command "research"

# Or run the completely standalone independent verifier directly
python scripts/verify_l3_research.py

# Run full unit + adversarial tamper-detection test suite
PYTHONPATH="components/Zoe-Autonomy/src:guiai-lab" python -m unittest \
  components/Zoe-Autonomy/tests/test_research_collaborator.py -v
```

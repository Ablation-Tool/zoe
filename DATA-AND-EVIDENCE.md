# Zoe Data, Verifiers & Evidence Manifest

A machine-verifiable directory of all datasets, upstream provenance, offline verification scripts, SHA-256 evidence JSON reports, and live loopback API routes in [`Ablation-Tool/zoe`](README.md).

**Related Indexes:** [Main README (Science First)](README.md) · [Papers & Monographs Index](RESEARCH-INDEX.md) · [Capability Atlas](CAPABILITY-ATLAS.md) · [Art & Creative Gallery](ART-AND-CREATIVE-GALLERY.md)

---

## 1. Cryptographic Supply-Chain Attestation (`33/33`)

All core theorem engines, cryptanalysis suites, bio-crypto modules, and the compiled 12-Theorem LaTeX PDF are hash-sealed in [`evidence/renaissance-orbit/SHA256SUMS.orbit`](evidence/renaissance-orbit/SHA256SUMS.orbit):

```bash
sha256sum -c evidence/renaissance-orbit/SHA256SUMS.orbit   # Expect: 33/33 : OK
```

*(Note per `CONSTITUTION.md` Article III.5: SHA-256 hash manifests provide tamper-evidence and reproducibility verification, not cryptographic identity certification.)*

---

## 2. Offline Verification Scripts & JSON Evidence Reports

### A. Cryptanalysis, NSA CNSA 2.0 & Bio-Crypto Circle (`C1–C22`)

| Suite | Verifier Script | Recorded Evidence JSON | Live Loopback API |
| :--- | :--- | :--- | :--- |
| **C1–C10 Boss Rush** | [`scripts/verify_kloster_cryptanalysis_gauntlet.py`](scripts/verify_kloster_cryptanalysis_gauntlet.py) | [`kloster-cryptanalysis-report.json`](evidence/kloster-cryptanalysis/kloster-cryptanalysis-report.json) | `/api/kloster/cryptanalysis` |
| **C11–C16 NSA Pack** | [`scripts/verify_nsa_research_puzzle_pack.py`](scripts/verify_nsa_research_puzzle_pack.py) | [`nsa-research-puzzle-pack-report.json`](evidence/kloster-cryptanalysis/nsa-research-puzzle-pack-report.json) | `/api/kloster/nsa-pack` |
| **C17–C19 Bio-Crypto Circle** | [`scripts/verify_bio_crypto_circle.py`](scripts/verify_bio_crypto_circle.py) | [`bio-crypto-circle-report.json`](evidence/kloster-cryptanalysis/bio-crypto-circle-report.json) | `/api/kloster/bio-crypto-circle` |
| **C20–C22 CNSA 2.0 & scRNA Ring 2** | [`scripts/verify_cnsa2_and_scrna_ring2.py`](scripts/verify_cnsa2_and_scrna_ring2.py) | [`cnsa2-scrna-ring2-report.json`](evidence/kloster-cryptanalysis/cnsa2-scrna-ring2-report.json) | `/api/kloster/cnsa2-ring2` |

### B. Kloster Theorems 1–12 & 11-World Orbit

| Study | Verifier Script | Recorded Evidence JSON | Live Loopback API |
| :--- | :--- | :--- | :--- |
| **Theorems 1–3 (Info Geometry)** | [`scripts/verify_kloster_theory.py`](scripts/verify_kloster_theory.py) | [`evidence/kloster-theory/`](evidence/kloster-theory/) | `/api/orbit/master` |
| **Theorem 4 (Code Elegance AST)** | [`scripts/zoe_code_quality_audit.py`](scripts/zoe_code_quality_audit.py) | [`kloster-mccabe-report.json`](evidence/code-elegance/kloster-mccabe-report.json) | `/api/kloster/elegance` |
| **Theorem 5 (Thermodynamics)** | [`scripts/verify_kloster_thermodynamics.py`](scripts/verify_kloster_thermodynamics.py) | [`evidence/kloster-thermodynamics/`](evidence/kloster-thermodynamics/) | `/api/kloster/thermo` |
| **Theorem 6 (Riemannian Fisher–Rao)** | [`scripts/verify_kloster_riemannian.py`](scripts/verify_kloster_riemannian.py) | [`evidence/kloster-riemannian/`](evidence/kloster-riemannian/) | `/api/kloster/riemannian` |
| **Theorem 7 (Optimal Transport $W_1$)** | [`scripts/verify_kloster_optimal_transport.py`](scripts/verify_kloster_optimal_transport.py) | [`evidence/kloster-optimal-transport/`](evidence/kloster-optimal-transport/) | `/api/kloster/transport` |
| **Theorems 8–11 (Passes 6–11)** | [`scripts/verify_kloster_passes_6_to_11.py`](scripts/verify_kloster_passes_6_to_11.py) | [`evidence/kloster-unification/`](evidence/kloster-unification/) | `/api/kloster/unification` |
| **Theorem 12 (Referee Proofs)** | [`scripts/verify_kloster_referee_proofs.py`](scripts/verify_kloster_referee_proofs.py) | [`kloster-referee-proofs-report.json`](evidence/kloster-referee-proofs/kloster-referee-proofs-report.json) | `/api/kloster/referee-proofs` |
| **11-World Master Orbit** | [`scripts/verify_renaissance_orbit.py`](scripts/verify_renaissance_orbit.py) | [`zoe-renaissance-orbit-master.json`](evidence/renaissance-orbit/zoe-renaissance-orbit-master.json) | `/orbit` · `/api/orbit/master` |

### C. Autonomy, Preclinical Neuroscience, Physics & Security

| Subsystem | Verifier Script | Recorded Evidence Directory |
| :--- | :--- | :--- |
| **Unified 6-Host System** | [`scripts/verify-one-system.py`](scripts/verify-one-system.py) | [`evidence/one-system/`](evidence/one-system/) |
| **8-Pillar Self-Improving Engine** | [`scripts/verify_self_improving_engine.py`](scripts/verify_self_improving_engine.py) | [`evidence/self-improving-engine/`](evidence/self-improving-engine/) |
| **L3 Research / L4 Evolution / L5 Phases 1–6** | [`verify_l3_research.py`](scripts/verify_l3_research.py) · [`verify_l4_self_improvement.py`](scripts/verify_l4_self_improvement.py) · [`verify_l4_multimodule.py`](scripts/verify_l4_multimodule.py) · [`verify_l5_core.py`](scripts/verify_l5_core.py) – [`verify_l5_phase6.py`](scripts/verify_l5_phase6.py) | [`evidence/l3-research/`](evidence/l3-research/) · [`evidence/l4-self-improvement/`](evidence/l4-self-improvement/) · [`evidence/l5-core/`](evidence/l5-core/) – [`evidence/l5-phase6/`](evidence/l5-phase6/) |
| **Mobile Digestion (`v0.9.3+`)** | [`scripts/verify_mobile_digestion.py`](scripts/verify_mobile_digestion.py) | [`digestion-report.json`](evidence/l5-mobile-digestion/digestion-report.json) |
| **Dorothy Neurogarden 3D** | [`scripts/verify_dorothy_neurogarden.py`](scripts/verify_dorothy_neurogarden.py) | [`dorothy-neurogarden-3d-report.json`](evidence/dorothy-neurogarden/dorothy-neurogarden-3d-report.json) |
| **CERN / HELIOS Kloster Trigger** | [`scripts/verify_cern_trigger.py`](scripts/verify_cern_trigger.py) | [`evidence/cern-trigger/`](evidence/cern-trigger/) |
| **Groove Forensics & Native Voice** | [`scripts/zoe_groove_forensics.py`](scripts/zoe_groove_forensics.py) · [`scripts/verify_zoe_voice.py`](scripts/verify_zoe_voice.py) | [`evidence/groove-forensics/`](evidence/groove-forensics/) · [`evidence/voice/`](evidence/voice/) |
| **Security Red-Team & External Benchmarks** | [`scripts/eval_external_benchmarks.py`](scripts/eval_external_benchmarks.py) | [`evidence/security-redteam/`](evidence/security-redteam/) · [`evidence/external-benchmarks/`](evidence/external-benchmarks/) |

---

## 3. Public Upstream Data Sources & Strict Synthetic Labels

| Dataset / Standard | Provenance & Usage | Scope / Boundary |
| :--- | :--- | :--- |
| **NIH PubChem PUG-REST (`11` compounds)** | Exact CIDs, MW, XLogP3, TPSA, HBD, HBA, RotB verified `2026-11-22` (`C17`: `dordaviprone`, `temozolomide`, `tovorafenib`, `lycorine`, `narciclasine`, `crocetin`, `crocin`, `colchicine`, `etoposide`, `vincristine`, `paclitaxel`). | Educational / preclinical CNS-MPO modeling only; `cure_claim=False`. |
| **Allen Mouse Brain Atlas CCFv3 (2017)** | 12 SHA-256-verified brain structure meshes (`315,932` triangles; Wang et al. 2020, *Cell*) used in Dorothy 3D connectome & Ray-Casting. | Preclinical mouse geometry; no clinical diagnosis or treatment claims. |
| **NIST Cryptographic Standards & Public Ciphers** | NIST FIPS 203 (`ML-KEM`, $q=3329, n=256$), FIPS 204 (`ML-DSA`, $q=8{,}380{,}417$), SP 800-38D (`AES-GCM` $\mathrm{GF}(2^{128})$), SP 800-208 (`LMS`), Beaulieu et al. 2013 (`SIMON`/`SPECK`), official `@NSACareers` May 2014 tweets, historical *Kryptos* sculpture. | 100% offline & legal mathematical analysis; zero unauthorized targets. |
| **Multi-Hospital Cohort & `scRNA-seq` Matrices (`C18, C19, C22`)** | Deterministically seeded synthetic count vectors (`synthetic_cohort_zero_phi = True`, `synthetic_scrna_benchmark_zero_phi = True`). | Zero real patient PHI; strictly methodology demonstration. |
| **16 External LLM Probability Spectra** | Local recorded token-probability distributions under `components/next-token-predictability/` used across Theorems 1–12 & Track E. | Offline static corpora; `0` cloud inference required to reproduce. |
| **Local GNU `.mo` & Stdlib Language Corpora (`C1, C13`)** | Portable independent English & 12-language `.mo` n-gram statistics built locally at runtime with zero ciphertext/key leakage. | Zero hardcoded keys or plaintext dictionaries. |

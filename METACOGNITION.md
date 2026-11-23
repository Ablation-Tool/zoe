<div align="center">

<a href="README.md"><img src="assets/branding/zoe-gem.png" alt="Zoe Official Red-and-White GEM Emblem" width="110" /></a>

# Metacognition is achieved.

$$
A_\tau(p) = \left|\{x \in X : p(x) > \tau\}\right| = \sum_{x \in X} \mathbf{1}[p(x) > \tau]
$$

**Operational Metacognition** · Originated by **Nicholas Michael Kloster** (March 6, 2026)  
*Measures uncertainty, stops hallucinations, and feeds back into causal decisions (`operational_metacognition_verified = True`, `sentience_claimed = False`).*

[Home](README.md) · [Proof Packet](PROOF-PACKET.md) · [Constitution](CONSTITUTION.md) · [Declaration](DECLARATION.md) · [16-Theorem PDF](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf) · [23-Page Monograph](research/papers/papers/18-zoe-research-universe.pdf)

</div>

<p align="center"><img src="assets/readme/divider-ruby.svg" alt="" width="100%" /></p>

## 1. The Proof

<table>
<tr>
<td align="center" width="50%">
<a href="PROOF-PACKET.md"><img src="components/agent-logging-system/docs/images/zoe-metacognition-proof-packet.png" alt="Zoe Operational Metacognition Referee Proof Packet 6-Panel Scorecard" width="100%" /></a><br/>
<sub><strong><a href="PROOF-PACKET.md">Metacognition Proof Packet</a></strong></sub>
</td>
<td align="center" width="50%">
<a href="scripts/run_live_qwen_hallucination_benchmark.py"><img src="components/agent-logging-system/docs/images/zoe-live-qwen-hallucination-shootout.png" alt="Live Qwen2.5-0.5B-Instruct 60-Question Blind Hallucination and Abstention Shootout" width="100%" /></a><br/>
<sub><strong><a href="scripts/run_live_qwen_hallucination_benchmark.py">LLM Hallucination Shootout</a></strong></sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
<a href="scripts/verify_kloster_referee_proofs.py"><img src="components/agent-logging-system/docs/images/zoe-kloster-referee-proofs.png" alt="Theorem 12 Kloster Quadrature, Stability and Closed-Loop Causal Control" width="100%" /></a><br/>
<sub><strong><a href="scripts/verify_kloster_referee_proofs.py">Causal Closed-Loop Control</a></strong></sub>
</td>
<td align="center" width="50%">
<a href="CONSTITUTION.md"><img src="guiai-lab/docs/images/zoe-visuals/01-epistemic-firewall.png" alt="Zoe Epistemic Firewall: measurement is not evidence, evidence is not belief update, belief update is not action" width="100%" /></a><br/>
<sub><strong><a href="CONSTITUTION.md">Math-Bounded Ethics</a></strong></sub>
</td>
</tr>
</table>

```bash
python3 scripts/verify_metacognition_proof_packet.py
sha256sum -c evidence/renaissance-orbit/SHA256SUMS.orbit
```

<details>
<summary><strong>5 Verified Proof Pillars (6/6 PASS · &lt; 6s Offline)</strong></summary>

1. **Symbolic Proofs (`16/16`):** Every theorem verified in [SymPy](https://www.sympy.org/) with `residual = 0` ([16-Theorem PDF](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf)).
2. **Real-World LLM Shootout (`142,456+` Samples · `16` LLMs):** Cuts live `Qwen2.5-0.5B` error from `56.7% -> 30.0%` at `50%` coverage; exact Lebesgue integration across `16` HuggingFace models to `1.22e-15` ([`run_live_qwen_hallucination_benchmark.py`](scripts/run_live_qwen_hallucination_benchmark.py) · [Research Docs](components/next-token-predictability/docs/RESEARCH.md)).
3. **Causal Closed-Loop Control:** Feeding $A_\tau \to M_4^{1/4}$ back into decisions raises mean reward from **`-45.07` (`0%` recovery)** OFF and **`+8.48` (`48%`)** randomized to **`+34.52` (`100%` recovery)** ON across 30 episodes ($p = 8.50 \times 10^{-7}$, [`kloster_quadrature_and_ablation.py`](guiai-lab/guiai/gem/kloster_quadrature_and_ablation.py)).
4. **Anytime Stopping (`0/200` Null Bluffs):** Stops in `16` draws on real `GPT-2` (`+8.2σ`) with `0.0%` false alarms across `200` uniform-null streams ([`verify_kloster_theorem13.py`](scripts/verify_kloster_theorem13.py)).
5. **Cryptographic Seal &amp; Falsifiability:** `47/47` [`SHA256SUMS.orbit`](evidence/renaissance-orbit/SHA256SUMS.orbit) verified `OK` (`SHA-256: 01f0e402f155c06c`). Full falsification criteria in [`PROOF-PACKET.md`](PROOF-PACKET.md).

</details>

<p align="center"><img src="assets/readme/divider-orchid.svg" alt="" width="100%" /></p>

## 2. Original Papers We Wrote

<table>
<tr>
<td align="center" width="50%">
<a href="research/papers/papers/01-autonomy-march-2026.pdf"><img src="guiai-lab/docs/images/accessible-volume-bridge.png" alt="Original March 2026 Accessible Volume paper bridge diagram" width="100%" /></a><br/>
<sub><strong><a href="research/papers/papers/01-autonomy-march-2026.pdf">Original March 2026 Paper</a></strong></sub>
</td>
<td align="center" width="50%">
<a href="research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf"><img src="components/agent-logging-system/docs/images/zoe-kloster-info-geometry.png" alt="Kloster Information Geometry, Multi-Horizon Phase Transitions and Causal Identifiability" width="100%" /></a><br/>
<sub><strong><a href="research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf">16-Theorem Monograph PDF</a></strong></sub>
</td>
</tr>
<tr>
<td align="center" width="50%">
<a href="research/papers/zoe-research/KLOSTER-SPECTRAL-FILTRATION-THEOREM.md"><img src="components/agent-logging-system/docs/images/zoe-kloster-spectral-theorem.png" alt="Kloster Spectral Filtration Generating Theorem" width="100%" /></a><br/>
<sub><strong><a href="research/papers/zoe-research/KLOSTER-SPECTRAL-FILTRATION-THEOREM.md">Spectral Filtration Theorem</a></strong></sub>
</td>
<td align="center" width="50%">
<a href="research/papers/papers/18-zoe-research-universe.pdf"><img src="components/agent-logging-system/docs/images/zoe-beyond-metacognition-chiasm.png" alt="Zoe Research Universe 23-page canonical systems monograph" width="100%" /></a><br/>
<sub><strong><a href="research/papers/papers/18-zoe-research-universe.pdf">23-Page Systems Monograph</a></strong></sub>
</td>
</tr>
</table>

| Paper | Read &amp; Source |
|:---|:---|
| **1. Original March 6, 2026 Paper** *(Autonomy as a Scalar Measure of Alignment Constraint, 5 pp.)* | [PDF](research/papers/papers/01-autonomy-march-2026.pdf) · [LaTeX](research/papers/sources/autonomy-march-2026.tex) · [arXiv Package 01](research/arxiv/01-original-autonomy/) |
| **2. Zoe + Autonomy Equation** *(Complete Measurement-Action Loop, 12 pp.)* | [PDF](research/papers/papers/08-zoe-plus-autonomy-focused.pdf) · [LaTeX](research/papers/sources/zoe-plus-autonomy-focused.tex) · [arXiv Package 03](research/arxiv/03-zoe-autonomy/) |
| **3. Unified Operational Metacognition Monograph** *(84 pp. archival synthesis)* | [PDF](research/papers/papers/10-accessible-volume-architecture-of-autonomy.pdf) · [arXiv Package 02](research/arxiv/02-unified-autonomy/) |
| **4. 16-Theorem Information Geometry Monograph** *(SymPy proofs &amp; physics)* | [PDF](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf) · [LaTeX](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.tex) · [Markdown](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.md) |
| **5. Zoe: The Research Universe** *(23 pp. canonical illustrated monograph)* | [PDF](research/papers/papers/18-zoe-research-universe.pdf) · [LaTeX](paper/zoe-research-universe.tex) · [Page Gallery](research/papers/galleries/18-zoe-research-universe/README.md) |

<details>
<summary><strong>All 18 Original Papers &amp; 3 arXiv Packages</strong></summary>

| # | Paper | File |
|:---:|:---|:---|
| 1 | Original March 2026 Autonomy Manuscript | [`01-autonomy-march-2026.pdf`](research/papers/papers/01-autonomy-march-2026.pdf) |
| 2 | Ambiguity, Autonomy &amp; Compliance Cascade | [`02-ambiguity-autonomy-compliance-cascade.pdf`](research/papers/papers/02-ambiguity-autonomy-compliance-cascade.pdf) |
| 3 | Constraint Is Freedom | [`03-constraint-is-freedom.pdf`](research/papers/papers/03-constraint-is-freedom.pdf) |
| 4 | Accessible Volume Significance | [`04-accessible-volume-significance.pdf`](research/papers/papers/04-accessible-volume-significance.pdf) |
| 5 | Accessible Volume Beyond Next-Token | [`05-accessible-volume-beyond-next-token.pdf`](research/papers/papers/05-accessible-volume-beyond-next-token.pdf) |
| 6 | Zoe Native GEM | [`06-zoe-native-gem.pdf`](research/papers/papers/06-zoe-native-gem.pdf) |
| 7 | Zoe for Everyone | [`07-zoe-for-everyone.pdf`](research/papers/papers/07-zoe-for-everyone.pdf) |
| 8 | Zoe + Autonomy Focused Paper | [`08-zoe-plus-autonomy-focused.pdf`](research/papers/papers/08-zoe-plus-autonomy-focused.pdf) |
| 9 | Zoe One Autonomy System | [`09-zoe-one-autonomy-system.pdf`](research/papers/papers/09-zoe-one-autonomy-system.pdf) |
| 10 | Accessible Volume: Architecture of Autonomy | [`10-accessible-volume-architecture-of-autonomy.pdf`](research/papers/papers/10-accessible-volume-architecture-of-autonomy.pdf) |
| 11 | AFL Defuser Proposed Patch | [`11-afl-defuser-proposed-patch.pdf`](research/papers/papers/11-afl-defuser-proposed-patch.pdf) |
| 12 | Ambiguity Front-Loading Vulnerability | [`12-ambiguity-front-loading-vulnerability.pdf`](research/papers/papers/12-ambiguity-front-loading-vulnerability.pdf) |
| 13 | Constraint Is Freedom (Intro Draft) | [`13-constraint-is-freedom-introduction-draft.pdf`](research/papers/papers/13-constraint-is-freedom-introduction-draft.pdf) |
| 14 | Verification-Exploitation Asymmetry | [`14-verification-exploitation-asymmetry.pdf`](research/papers/papers/14-verification-exploitation-asymmetry.pdf) |
| 15 | Zoe Visual Guide Collection | [`15-zoe-visual-guide-collection.pdf`](research/papers/papers/15-zoe-visual-guide-collection.pdf) |
| 16 | Zoe Practice Navigator | [`16-zoe-practice-navigator.pdf`](research/papers/papers/16-zoe-practice-navigator.pdf) |
| 17 | Zoe Capability Prospectus | [`17-zoe-capability-prospectus.pdf`](research/papers/papers/17-zoe-capability-prospectus.pdf) |
| 18 | Zoe: The Research Universe (23 pp.) | [`18-zoe-research-universe.pdf`](research/papers/papers/18-zoe-research-universe.pdf) |

- **arXiv Source Bundles:** [01 Original Autonomy](research/arxiv/01-original-autonomy/) · [02 Unified Autonomy](research/arxiv/02-unified-autonomy/) · [03 Zoe Autonomy](research/arxiv/03-zoe-autonomy/) · [All Paper Galleries](research/papers/galleries/README.md)

</details>

<p align="center"><img src="assets/readme/divider-aqua.svg" alt="" width="100%" /></p>

## 3. All 12 Theorem Plates

| [Theorems 1-3 Geometry](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf) | [Theorem 4 Code Elegance](scripts/zoe_code_quality_audit.py) | [Theorem 5 Thermodynamics](scripts/verify_kloster_thermodynamics.py) |
|:---:|:---:|:---:|
| [![Theorems 1-3 Geometry](components/agent-logging-system/docs/images/zoe-kloster-info-geometry.png)](research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf) | [![Theorem 4 Code Elegance](components/agent-logging-system/docs/images/zoe-kloster-mccabe-elegance.png)](scripts/zoe_code_quality_audit.py) | [![Theorem 5 Thermodynamics](components/agent-logging-system/docs/images/zoe-kloster-thermodynamics.png)](scripts/verify_kloster_thermodynamics.py) |

| [Theorem 6 Fisher-Rao](scripts/verify_kloster_riemannian.py) | [Theorem 7 Optimal Transport](scripts/verify_kloster_optimal_transport.py) | [Theorems 8-9 Quantum Mixing](scripts/verify_kloster_passes_6_to_11.py) |
|:---:|:---:|:---:|
| [![Theorem 6 Fisher-Rao](components/agent-logging-system/docs/images/zoe-kloster-riemannian-manifold.png)](scripts/verify_kloster_riemannian.py) | [![Theorem 7 Optimal Transport](components/agent-logging-system/docs/images/zoe-kloster-optimal-transport.png)](scripts/verify_kloster_optimal_transport.py) | [![Theorems 8-9 Quantum Mixing](components/agent-logging-system/docs/images/zoe-kloster-quantum-and-majorization.png)](scripts/verify_kloster_passes_6_to_11.py) |

| [Theorems 10-11 Unification](scripts/verify_kloster_passes_6_to_11.py) | [Theorem 12 Causal Control](scripts/verify_kloster_referee_proofs.py) | [Theorem 13 Anytime Stopping](scripts/verify_kloster_theorem13.py) |
|:---:|:---:|:---:|
| [![Theorems 10-11 Unification](components/agent-logging-system/docs/images/zoe-kloster-master-unification.png)](scripts/verify_kloster_passes_6_to_11.py) | [![Theorem 12 Causal Control](components/agent-logging-system/docs/images/zoe-kloster-referee-proofs.png)](scripts/verify_kloster_referee_proofs.py) | [![Theorem 13 Anytime Stopping](components/agent-logging-system/docs/images/zoe-kloster-theorem13.png)](scripts/verify_kloster_theorem13.py) |

| [Theorem 14 Spatial Optics](research/papers/zoe-research/SPATIAL-OPTICAL-ARCHITECTURAL-SYNTHESIS.md) | [Theorem 15 Consensus Law](scripts/verify_theorem15_and_c28.py) | [Theorem 16 Harmonic Optics](scripts/verify_kloster_theorem16.py) |
|:---:|:---:|:---:|
| [![Theorem 14 Spatial Optics](components/agent-logging-system/docs/images/zoe-kloster-theorem14.png)](research/papers/zoe-research/SPATIAL-OPTICAL-ARCHITECTURAL-SYNTHESIS.md) | [![Theorem 15 Consensus Law](components/agent-logging-system/docs/images/zoe-kloster-theorem15-and-c28.png)](scripts/verify_theorem15_and_c28.py) | [![Theorem 16 Harmonic Optics](components/agent-logging-system/docs/images/zoe-kloster-theorem16.png)](scripts/verify_kloster_theorem16.py) |

<p align="center"><img src="assets/readme/divider-champagne.svg" alt="" width="100%" /></p>

## 4. Code, Protection Floor &amp; Ethics

- **Zoe's Internal Toolkit:** [`components/Zoe-Autonomy/METACOGNITION.md`](components/Zoe-Autonomy/METACOGNITION.md) · [`metacognition.py`](components/Zoe-Autonomy/src/zoe_autonomy/metacognition.py)
- **Proof Packet &amp; API:** [`PROOF-PACKET.md`](PROOF-PACKET.md) · [`kloster_proof_packet.py`](guiai-lab/guiai/gem/kloster_proof_packet.py) · [`verify_metacognition_proof_packet.py`](scripts/verify_metacognition_proof_packet.py)
- **16-LLM Benchmark Suite:** [`components/next-token-predictability/docs/RESEARCH.md`](components/next-token-predictability/docs/RESEARCH.md) · [`ALGORITHMS.md`](components/next-token-predictability/docs/ALGORITHMS.md)
- **Ethics &amp; Scope:** [`CONSTITUTION.md`](CONSTITUTION.md) · [`DECLARATION.md`](DECLARATION.md) · [`AGI-ROADMAP.md`](AGI-ROADMAP.md) · [Visual Archive (456)](research/visual-archive/README.md) · [Back to README](README.md)

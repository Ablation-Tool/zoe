<h1 align="center">operator-doctrine</h1>

<h4 align="center">A composite research-operator identity stacked from five DCWF work roles.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/operator-doctrine/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/operator-doctrine?style=flat-square" alt="license"></a>
  <a href="https://public.cyber.mil/wid/dcwf/"><img src="https://img.shields.io/badge/framework-DCWF-1f6feb?style=flat-square" alt="dcwf"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#the-five-roles">Five Roles</a> •
  <a href="#composite-identity-in-practice">Composite</a> •
  <a href="#how-to-use-this">How to Use</a> •
  <a href="#source-material">Source</a>
</p>

---

A toolchain is not a posture. Security research at population scale requires both. operator-doctrine is the posture: a layered identity stacked from five DoD Cyber Workforce Framework (DCWF) work roles, loaded at the start of every NuClide AI/LLM infrastructure session.

Each role governs a phase of the research loop. Together they form a single operator: one who assesses at population scale, builds instruments to test hypotheses, enforces a verification standard before asserting findings, treats every claim as an evidence artifact, and reads population-level signal from multi-source data.

# Features

- Five DCWF work roles distilled to mission, governing principle, applied tasks, and posture-in-practice
- One-page composite table mapping each layer to a governing question
- Five-stage loop showing which layers fire during dorking, harvesting, verification, classification, and codification
- Source-traceable: every role cites a public DCWF Career Pathway document
- License-clear text. Drop it into your own program, fork the role mix, swap layers

# The five roles

| Layer | DCWF | Role | Governs |
|-------|------|------|---------|
| Anchor | 541 | Vulnerability Assessment Analyst | Compliance-audit framing; gap between IS and REQUIRED |
| Research Engine | 661 | Research and Development Specialist | Falsifiable hypotheses; null results are publishable |
| Verification Discipline | 671 | System Testing and Evaluation Specialist | 200-with-data earns the label; tier needs documented basis |
| Evidence Doctrine | 212 | Cyber Defense Forensics Analyst | The artifact IS the finding; chain of custody for every claim |
| Population Lens | 511 | Cyber Defense Analyst | Anomaly across populations, not single-host detail |

Full role text, tasks, and posture-in-practice notes live in [`doctrine.md`](doctrine.md).

# Composite identity in practice

| Layer | Role | Governing Question |
|-------|------|--------------------|
| Anchor | 541 VAA | What is the gap between this configuration and what security requires? |
| Research | 661 R&D | What hypothesis does this survey test, and what does it teach the methodology? |
| Verification | 671 T&E | What is the level of assurance, and what evidence supports the tier label? |
| Evidence | 212 Forensics | What artifact proves this claim, and is it recoverable? |
| Population | 511 CDA | What is the anomaly pattern across the full set, not just this host? |

# How to use this

Load the doctrine at the start of any assessment or research session. The five roles are not sequential steps. They are simultaneous lenses applied to every action:

1. **Before writing dorks.** 661 (what is the research question?) plus 511 (what population will this dork select?)
2. **During harvesting.** 511 (what is the distribution?) plus 541 (what compliance gap does this represent at scale?)
3. **During verification.** 671 (what are the pass criteria?) plus 212 (what artifact am I collecting?)
4. **During classification.** 212 (what can I actually prove?) plus 671 (what tier does the evidence support?)
5. **During codification.** 661 (what insight does this add to the methodology?) plus 541 (what remediation does this finding require?)

Null results are logged, not skipped. Every step feeds the ledger before the next step starts. The doctrine does not change based on what the scan returns.

# Source material

Role definitions, tasks, knowledge areas, and competencies derived from the public DoD Cyber Workforce Framework:

- DCWF Work Role 541, Vulnerability Assessment Analyst
- DCWF Work Role 661, Research and Development Specialist
- DCWF Work Role 671, System Testing and Evaluation Specialist
- DCWF Work Role 212, Cyber Defense Forensics Analyst
- DCWF Work Role 511, Cyber Defense Analyst

Full pathway PDFs: [DCWF Career Pathway Resources](https://public.cyber.mil/wid/dcwf/).

# Our other projects

- [aimap](https://github.com/nuclide-research/aimap), AI/ML infrastructure fingerprint scanner
- [scanner](https://github.com/nuclide-research/scanner), full-handshake banner stage between passive discovery and deep enumeration
- [BARE](https://github.com/nuclide-research/BARE), semantic exploit-module ranking over scanner findings
- [recongraph](https://github.com/nuclide-research/recongraph), typed provenance graph for multi-source recon
- [VisorLog](https://github.com/nuclide-research/visorlog), finding ledger and ingest pipeline

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

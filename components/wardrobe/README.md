<h1 align="center">wardrobe</h1>

<h4 align="center">The NICE Cybersecurity Workforce Framework as a wardrobe of atoms.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/wardrobe/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/wardrobe?style=flat-square" alt="license"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python" alt="python"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#use">Use</a> •
  <a href="#the-atom-library">Atom library</a> •
  <a href="#an-example-outfit">Example outfit</a> •
  <a href="#scope">Scope</a>
</p>

---

Take 39 NICE work-role pathway PDFs. Explode them into atomic components: every Task (T-code), Knowledge (K-code), Skill (S-code), Ability (A-code), Competency (C-code), and proficiency rung. Put 1,281 atoms into one searchable library. Hand-pick across all 39 roles to assemble a totally custom posture.

A role becomes an outfit. An outfit is a collection of atoms drawn from anywhere in the framework, with optional proficiency rungs and freeform notes on why each piece is in. The outfit renders as an LLM system prompt, a human checklist, a markdown document, or a JSON contract.

Instead of "wear 541 Vulnerability Assessment Analyst" you can wear:

> T0549 from 541 + T0028 from 541 + K0342 from 541 + K0177 from 511 + K0344 from 661 + S0025 from 511 + S0001 from 541 + A0123 from 612

A bespoke "AI infrastructure vuln research with incident-evidence interpretation flavor" role that nobody at NIST ever designed. The point is to offload "what posture should I take?" to a tagged library so cognitive cycles stay on the actual problem. Trial and error finds the combinations that sharpen versus the ones that are theater.

# Features

- 1,281 atoms across 39 work roles, pre-extracted to `atoms.json` (~800 KB)
- Five atom types: tasks (612), knowledge (335), skills (184), abilities (114), competencies (36)
- Cross-role citation index: K0001 through K0006 are cited by all 39 roles; K0179 by 19
- Try-on / outfit / save / load workflow with per-atom proficiency and notes
- Four renderers: `prompt` (LLM system message), `checklist` (human), `markdown` (document), `json` (full atom text)
- No PDFs required at use time. The library ships with the repo
- Optional re-extract from source PDFs via `extract_atoms.py`

# Installation

Requires Python 3.10+. `pdftotext` (poppler-utils) only if you re-extract.

```bash
git clone https://github.com/nuclide-research/wardrobe ~/wardrobe
ln -sf ~/wardrobe/wardrobe.py ~/.local/bin/wardrobe
```

The atom library (`atoms.json`) ships with the repo. You do not need the original PDFs to use it.

Re-extract from source:

```bash
# Drop the 39 NICE pathway PDFs into ~/Documents/dod-cyber-pathways/
python3 ~/wardrobe/extract_atoms.py
```

# Use

```bash
wardrobe browse                          # list all atoms
wardrobe browse --type T --text attack   # filter tasks by keyword
wardrobe browse --role 541 -n 100        # everything in role 541
wardrobe browse --competency "Threat Analysis"

wardrobe show T0549                      # one atom: text + roles + proficiency

wardrobe try-on T0549 --proficiency Advanced --note "core vuln assess"
wardrobe try-on K0342 S0001              # multi-atom add
wardrobe outfit                          # show current outfit

wardrobe save vuln-research-ai-flavor --notes "AI infra research outfit"
wardrobe load vuln-research-ai-flavor
wardrobe outfits                         # list saved outfits

wardrobe render --as prompt              # LLM system-prompt rendering
wardrobe render --as checklist           # human checklist
wardrobe render --as json                # full JSON with resolved atom text
wardrobe render --as markdown            # markdown for documents
```

# The atom library

`atoms.json`:

```json
{
  "version": "0.1",
  "extracted_at": "2026-06-07",
  "sources": ["541-Vulnerability-Assessment-Analyst-Career-Pathway.pdf", "..."],
  "atoms": {
    "tasks":         ["..."],
    "knowledge":     ["..."],
    "skills":        ["..."],
    "abilities":     ["..."],
    "competencies":  ["..."]
  },
  "counts": {}
}
```

Each atom carries:

- `code` (e.g. `T0549`, `K0342`, `C026`)
- `type` (task, knowledge, skill, ability, competency)
- `text` (the statement as written in the PDF)
- `source_roles` (list of role IDs that cite this atom)
- `competency_family` (for KSAs that have one)
- `importance_by_role` (per-role flag: Core, Additional, Foundational)
- `proficiency_by_role` (per-role Entry / Intermediate / Advanced behaviors for tasks)

The library exposes the framework's implicit composability. K0001 through K0006 are cited by all 39 roles (the "Foundational to All Work Roles" set). K0179 (network security architecture) is cited by 19. Picking shared atoms lets you build outfits that span multiple specialties without trying on a whole second role.

# An example outfit

```bash
$ wardrobe reset
$ wardrobe try-on T0549 T0028 --proficiency Advanced --note "core vuln + pentest"
$ wardrobe try-on T0188 --proficiency Advanced --note "audit reports"
$ wardrobe try-on K0342 S0001 S0051 --note "pentest tools"
$ wardrobe try-on K0177 --note "kill chain"
$ wardrobe try-on K0344 --note "org threat env"
$ wardrobe try-on A0123 --note "apply CIA to ML ops"
$ wardrobe outfit
current outfit
  T0549   [task] [Advanced]  Perform technical and nontechnical risk and vulnerability assessments...
  T0028   [task] [Advanced]  Conduct and/or support authorized penetration testing...
  T0188   [task] [Advanced]  Prepare audit reports that identify technical and procedural findings...
  K0342   [know]               Knowledge of penetration testing principles, tools, and techniques.
  S0001   [skil]               Skill in conducting vulnerability scans...
  S0051   [skil]               Skill in the use of penetration testing tools and techniques.
  K0177   [know]               Knowledge of cyber attack stages...
  K0344   [know]               Knowledge of an organization's threat environment.
  A0123   [abil]               Ability to apply cybersecurity and privacy principles to org reqs.

9 pieces  (cross-role: 19 source roles)
```

`wardrobe render --as prompt` emits a system-prompt block any LLM can load as its posture for the task.

# Composition philosophy

Trial and error. Some outfits feel sharp; others feel like theater. The act of picking atoms forces you to be explicit about which postures you actually need for the work. Save the outfits that worked. Re-load them when the task shape returns.

# Status

Early. Text quality has some noise from PDF-table extraction (stray table-header words, competency-family bleed). The codes, role citations, and structural composition are reliable. A cleanup pass is planned.

# Scope

wardrobe is a local Python CLI. It reads JSON and writes JSON. No network calls. Re-extraction reads PDFs from disk. Useful for: LLM agents that need a posture for a task; humans assembling a role spec for a new hire or a personal study plan; cross-framework composition once other catalogs (NIST 800-53, MITRE ATT&CK, ISO 27001) are loaded into the same wardrobe.

# Our other projects

- [syllabus](https://github.com/nuclide-research/syllabus) — local CLI study index over the AI-security PDF corpus
- [tome](https://github.com/nuclide-research/tome) — Technical OSINT Mining Engine, canonical platform corpus
- [aimap](https://github.com/nuclide-research/aimap) — AI/ML infrastructure fingerprint scanner
- [scanner](https://github.com/nuclide-research/scanner) — active-banner stage between passive discovery and deep enumeration
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

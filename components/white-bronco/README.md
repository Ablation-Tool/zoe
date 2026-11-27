# white-bronco

A field guide for independent security researchers submitting coordinated vulnerability disclosures (CVD).

There is no single standard format. Enterprise and government PSIRTs each have their own intake process, severity expectations, and documentation preferences. This repo provides the scaffolding that a researcher needs to produce professional, actionable disclosure packages for any vendor.

---

## What is in here

```
white-bronco/
├── README.md
├── logos/              SVG + PDF + PNG logos for 50+ vendors and coordinators
├── templates/          LaTeX source templates
│   └── disclosure-report.tex
├── guides/             Human-readable reference guides
│   ├── psirt-directory.md      PSIRT contacts for 40+ vendors
│   ├── submission-tips.md      Pre-send checklist and PoC/YARA/CVSS guidance
│   ├── company-logo.md         Logo placement in LaTeX disclosure reports
│   └── create-latex-document.md  31-rule prompt for LLM LaTeX generation
├── skills/             Claude Code agent skills (drop in .claude/agents/)
│   ├── vuln-report-writing.md  70-rule disclosure writing guide
│   └── latex.md                LaTeX authoring skill from 13 official PDFs
└── docs/               Official LaTeX reference PDFs (lshort, hyperref, etc.)
```

---

## The problem this solves

Independent researchers do not have a legal team, a formatting standard, or a template library. Vendor PSIRTs receive hundreds of reports. The ones without a clear severity, reproducible steps, and working PoC get deprioritized or closed. The goal here is to close that gap.

A disclosure package built from this repo will:

- Compile to a clean PDF with professional typography
- State each finding's impact in the first sentence (not buried in paragraph three)
- Include a tested PoC and YARA rule for every binary finding
- Use CVSS 3.1 with a full vector string
- Arrive formatted the way a PSIRT analyst expects to read it

---

## Workflow

### 1. Check the PSIRT directory

Before writing anything, confirm the right submission channel in `guides/psirt-directory.md`. Covers Cisco, Fortinet, Palo Alto, Juniper, F5, SonicWall, Check Point, Microsoft, Google, Apple, IBM, Oracle, VMware/Broadcom, SAP, Atlassian, GitLab, Adobe, SolarWinds, Ivanti, Citrix, AWS, Akamai, Cloudflare, HashiCorp, Red Hat, HPE, HP, Dell, Lenovo, Intel, AMD, NVIDIA, Qualcomm, ARM, Siemens, Schneider Electric, Rockwell, Honeywell, ABB, Emerson, GE Vernova, Mitsubishi Electric, Phoenix Contact, Moxa, AVEVA, Ericsson, Nokia, Huawei, NXP, and Broadcom.

For ICS/OT findings: submit to the vendor AND to CISA VINCE-NT simultaneously.

### 2. Read submission-tips.md

Before writing a single line of the report, read `guides/submission-tips.md`. The most common reasons a disclosure gets closed without action:

- Findings that are not self-contained (chained vulnerabilities without individual PoC)
- PoC that does not reproduce on a clean build of the stated version
- CVSS scores without vector strings
- Vague impact statements ("could allow an attacker to...")
- No YARA rule for binary findings

### 3. Copy and fill the template

```bash
cp templates/disclosure-report.tex my-disclosure.tex
```

Replace every `\ph{PLACEHOLDER}` field. Add the vendor logo from `logos/`:

```latex
\begin{flushright}
  \includegraphics[height=1.4cm]{../logos/cisco}
\end{flushright}
```

Compile:

```bash
pdflatex my-disclosure.tex && pdflatex my-disclosure.tex
```

### 4. Run the writing guide

If you use Claude Code, install the writing skill:

```bash
mkdir -p .claude/agents
curl -o .claude/agents/vuln-report.md \
  https://raw.githubusercontent.com/francis-rancid/white-bronco/main/skills/vuln-report-writing.md
```

Then ask Claude to review your draft:

```
/vuln-report review my-disclosure.tex and apply the pre-submission checklist
```

The skill enforces 70 rules covering verb-based writing, precise capability statements, CVSS translation, parallel structure, elimination of hedge-stacking, sentence rhythm, and plain language standards.

---

## Logos

`logos/` contains SVG + PDF + PNG for every vendor in the PSIRT directory. PDF is the primary format for `pdflatex`. PNG is the fallback for vendors where no vector source was available.

See `guides/company-logo.md` for placement patterns.

---

## Coordinators

When a vendor is unresponsive, or the scope is multi-vendor or ICS/OT:

| Coordinator | URL | Notes |
|---|---|---|
| CISA VINCE-NT | https://vulnerabilities.cisa.gov/vincent/auth/login/ | Primary for ICS/OT. Replaced kb.cert.org/vince. |
| CERT/CC | https://kb.cert.org/vince/ | Active for academic and research cases. |
| FIRST | https://www.first.org/coordination/ | Connects to vendor PSIRT via FIRST membership. |

---

## LaTeX reference

The `docs/` directory contains 13 official LaTeX documentation PDFs (789 pages total). `skills/latex.md` is a synthesized skill covering package load order, typography, tables, floats, cross-references, math, listings, page layout, and error diagnosis.

`guides/create-latex-document.md` encodes all 31 rules as a system prompt for generating LaTeX from any LLM.

---

## Disclosure timeline expectations

| Day | Action |
|---|---|
| 0 | Submit. Start the 90-day clock. |
| 7 | If no acknowledgment: one follow-up. |
| 14 | If still no response: escalate to CISA or CERT/CC. |
| 45 to 90 | Default window before public disclosure. |
| Patch day | Coordinate publish date with vendor. |

---

## Contributing

Pull requests welcome for:

- PSIRT contact corrections or additions
- Vendor logo updates (SVG preferred)
- LaTeX template improvements
- Writing rule additions or corrections

Open an issue for anything wrong in `psirt-directory.md`. Vendor contacts change without notice.

---

## Writing Reference Library

The 70 rules in `skills/vuln-report-writing.md` were synthesized from the following books. These are the primary training data for the writing conventions this repo enforces.

### Core technical writing

| Book | Author(s) | Publisher | Year |
|---|---|---|---|
| *Plain Style: Techniques for Simple, Concise, Emphatic Business Writing* | Richard Lauchman | AMACOM | 2008 |
| *Docs for Developers: An Engineer's Field Guide to Technical Writing* | Jared Bhatti, Zachary Sarah Corleissen, Jen Lambourne, David Nunez, Heidi Waterhouse | Apress | 2021 |
| *Technical Writing for Software Developers* | Chris Chinchilla | Packt Publishing | 2024 |
| *Technical Writing, 2nd Edition* | Phillip A. Laplante | CRC Press | 2018 |
| *Technical Writing for Developers* | Jim Hall | Apress | 2024 |

### Business writing and plain language

| Book | Author(s) | Publisher | Year |
|---|---|---|---|
| *The Truth About the New Rules of Business Writing* | Natalie Canavor, Claire Meirowitz | Pearson | 2008 |
| *A Practical Guide to Business Writing: Writing Well in English for Native and Non-Native Speakers* | Khaled Al Maskari | Wiley | 2012 |
| *Style Guide for Business Writing* | Michael C. Thomsett | De Gruyter | 2017 |
| *Plain Language in Government Writing: A Step-by-Step Guide* | Judith Myers | Berrett-Koehler | 2020 |

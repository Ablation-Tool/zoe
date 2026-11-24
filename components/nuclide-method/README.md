<div align="center">

### nuclide-method

> *"A scanner produces candidates. Verification produces findings."*

A reproducible, verification-first methodology for assessing exposed AI and ML infrastructure.
Built by **NuClide Research**, the lab behind advisories [CVE-2025-4364][cve] and [ICSA-25-140-11][icsa].

[**nuclide-research.com**][site]

[Methodology](docs/METHODOLOGY.md) · [Quick Start](#quick-start) · [Arsenal](#arsenal-matrix) · [Report a Vulnerability](SECURITY.md) · [Contribute](CONTRIBUTING.md)

[![License: MIT][badge-license]][url-license]
[![Methodology v2.5][badge-version]][url-version]
[![Last commit][badge-commit]][url-commit]
[![Open issues][badge-issues]][url-issues]
[![Published advisories: CVE-2025-4364 / ICSA-25-140-11][badge-advisory]][url-advisory]

</div>

---

<details>
<summary>Table of contents</summary>

- [What this is](#what-this-is)
- [What's new](#whats-new)
- [Features](#features)
- [The thesis under test](#the-thesis-under-test)
- [The pipeline](#the-pipeline)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Arsenal Matrix](#arsenal-matrix)
- [Numbered insights](#numbered-insights)
- [Restraint Ethic](#restraint-ethic)
- [Coverage](#coverage)
- [Citation](#citation)
- [License and Disclaimer](#license-and-disclaimer)
- [Acknowledgments](#acknowledgments)

</details>

---

## What this is

The operating loop behind real published advisories, written down so you can run it yourself.

This is not another agent that scans the internet for you. Point it at a scope you are authorized to test and you inherit the whole discipline: discover, prefilter, fingerprint, then the one stage that earns a finding.

```sh
git clone https://github.com/nuclide-research/nuclide-method && cd nuclide-method
make install              # go install the public NuClide tools
make chain IPS=ips.txt    # run the reference chain over your authorized scope
```

The repo ships zero targets. You supply the scope. [QUICKSTART.md](docs/QUICKSTART.md) is the path from a clean machine to a verified finding, and [a sample run over a documentation scope](examples/00-sample-run.txt) shows what the chain prints before you wire in your own targets.

**The differentiator, and the whole point.** Every scanner points at cloud ranges, collects exposed AI services in an afternoon, and stops. That output is candidates. The stage that turns a candidate into a finding is verification, and it is the stage they skip. This repo is that stage, written down.

```
NuClide Methodology - eight numbered stages plus the active-banner prefilter
============================================================================

A scanner produces candidates. Verification produces findings.
VERIFY is the load-bearing stage. The rest feed it or record what it confirmed.


  Stage -1/0          prefilter             Stage 1
  +------------+     +--------------+     +--------------+
  |  DISCOVER  | --> | ACTIVE-      | --> | FINGERPRINT  |
  |            |     | BANNER       |     |              |
  | name-first |     |              |     | one question:|
  | provider   |     | liveness     |     | what service |
  | CT-log     |     | (~1/3 live)  |     | is on this   |
  |            |     | fresh ver.   |     | port?        |
  | take the   |     | FP-strip     |     | conjunctive  |
  | 3-way      |     | shadow ports |     | match +      |
  | DELTA      |     |              |     | anti-match   |
  +------------+     +--------------+     +--------------+
                     banner != schema           |
                     (prefilter only)           v

                  Stage 2
                  +=================================+
                  ||                               ||
                  ||         [  VERIFY  ]          ||
                  ||   THE LOAD-BEARING STAGE      ||
                  ||                               ||
                  ||  candidate -> finding only    ||
                  ||  by surviving verification    ||
                  ||                               ||
                  ||  - 200 = identity, not auth   ||
                  ||  - dork hits != instances     ||
                  ||    (the ~50% marker rule)     ||
                  ||  - follow redirects / tokens  ||
                  ||  - traverse full handshake    ||
                  ||  - pull a full real record    ||
                  ||  - protocol-strict probe      ||
                  ||    self-filters honeypots     ||
                  ||                               ||
                  +=================================+
                                 |
                                 v
  Stage 3            Stage 4            Stage 5
  +-----------+     +-----------+     +-----------+
  | ATTRIBUTE | --> | CLASSIFY  | --> |  LEDGER   |
  |           |     |           |     |           |
  | no-SNI    |     | HIPAA/    |     | append-   |
  | cert ->   |     | clinical/ |     | only,     |
  | CT-log    |     | personal/ |     | lifecycle |
  | SAN pivot |     | research/ |     | tracked   |
  +-----------+     | honeypot  |     +-----------+
                    +-----------+           |
                                            v
  Stage 6                          Stage 7
  +---------------+               +---------------+
  | SCORE / RANK  | ------------> |    CODIFY     |
  |               |               |               |
  | OPA/Rego:     |               | survey -> a   |
  |  policy IS    |               | numbered      |
  |  the method   |               | Insight       |
  | deny=CRITICAL |               | data makes    |
  | semantic rank |               | findings;     |
  | adversarial   |               | insights make |
  |  corpus       |               | the method    |
  +---------------+               +---------------+

The ledger is the record of work, not a terminal print.
A survey interrupted at any stage resumes from the ledger.
```

Full diagram: [docs/diagrams/pipeline.txt](docs/diagrams/pipeline.txt).

---

## What's new

[Full changelog](CHANGELOG.md).

- **v2.5 makes the methodology the default operating logic**, not a mode you switch into. When the work is assessment, recon, or AI-infra investigation, the whole loop is already on. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md).
- **The tome corpus reaches 50 platforms.** One canonical record per platform carries dorks, probe scaffolds, and an OSINT profile, so you stop hand-deriving them per survey. See [docs/ARSENAL.md](docs/ARSENAL.md).
- **The verification-rung grid is codified.** Every finding states a depth-by-breadth pair (Insight #68), so a code-reading move can never borrow the language of a population claim. See [docs/VERIFICATION.md](docs/VERIFICATION.md).
- **The active-banner prefilter is a standing stage**, not an option. Liveness, fresh version, false-positive strip, and shadow-port discovery run before the fingerprinter, so the deep enumerator works a clean live subset.

---

## Features

Five pillars. Everything else is detail.

- **Verification is the load-bearing stage.** A scan produces candidates. Verification produces findings. A 200 is platform identity, not auth state. A dork hit is not an instance. The scan is the easy part, and the easy part is where the lies enter. See [docs/VERIFICATION.md](docs/VERIFICATION.md).
- **The full arsenal runs, nothing conditional.** Every tool runs against every survey set, with exactly two documented non-runs. A null result is a logged result, never a skip. A zero-hit dork, a zero-overlap attribution, a zero-leak successor survey: each is a finding. See [docs/ARSENAL.md](docs/ARSENAL.md).
- **Codify every survey.** Each survey extracts one numbered insight: the class of mistake, the default it ties to, the verification rule that catches it. The data is perishable. The insight compounds. See [docs/INSIGHTS.md](docs/INSIGHTS.md).
- **The restraint ethic.** We enumerate metadata and never exfiltrate. Names ARE the finding. We sample payloads minimally, only to confirm severity, and a blocked read is "surface open, access not exercised," not a failure. See [docs/RESTRAINT-ETHIC.md](docs/RESTRAINT-ETHIC.md).
- **Auth-on-default is a falsifiable thesis.** This is a research program, not a scan. The shipping default is the deployment template for an entire population. We test the thesis every survey, and a negative result is publishable. See [docs/THESIS.md](docs/THESIS.md).

---

## The thesis under test

A methodology, not a tool. It exists to answer a falsifiable question.

**Hypothesis.** At population scale, the unauthenticated-exposure rate of an AI platform follows its shipping default, not the skill of its operators. Two products with comparable customers and opposite security defaults produce population outcomes that differ by orders of magnitude (Insight #13). The default is load-bearing. The operator is not the variable.

**The rightward shift.** The thesis strengthens across successor generations within a project family under disclosure pressure (Insight #40). When a disclosure lands, the next release hardens the specific surface that drove it. The architectural pattern persists. The observable finding shape closes.

**Negatives confirm by contrapositive.** A platform that ships auth-on-default and runs zero unauthenticated hosts across a large population is not a failed survey. It is evidence for the thesis, and it is publishable. Absence of a finding is not absence of risk.

Full hypothesis, predictions, and falsifiers: [docs/THESIS.md](docs/THESIS.md).

---

## The pipeline

Eight numbered stages plus the Active-Banner prefilter. Discover, Active-Banner, Fingerprint, **Verify**, Attribute, Classify, Ledger, then Score and Codify. Every stage writes to the ledger before the next begins, so a survey interrupted anywhere resumes from the record instead of rerunning from scratch.

| # | Stage | One line | Docs |
|---|-------|----------|------|
| -1/0 | **Discover** | Name-first, provider, and CT-log discovery. Take the three-way delta, never one telescope. | [METHODOLOGY](docs/METHODOLOGY.md) |
| 0c | **Active-Banner** | Liveness, fresh version, false-positive strip, shadow ports. Banner is not schema. | [VERIFICATION](docs/VERIFICATION.md) |
| 1 | **Fingerprint** | One question: what service is on this port? Conjunctive match plus anti-match. | [DISCOVERY-MOVES](docs/DISCOVERY-MOVES.md) |
| 2 | **Verify** | The load-bearing stage. A candidate becomes a finding only by surviving verification. | [VERIFICATION](docs/VERIFICATION.md) |
| 3 | **Attribute** | No-SNI default cert to CT-log SAN pivot, plus rDNS. WHOIS is authoritative. | [METHODOLOGY](docs/METHODOLOGY.md) |
| 4 | **Classify** | HIPAA, clinical, personal, research, or honeypot. Classify from schema, not contents. | [RESTRAINT-ETHIC](docs/RESTRAINT-ETHIC.md) |
| 5 | **Ledger** | Append-only, lifecycle-tracked. Open to disclosed to acked to remediated to verified. | [OUTPUT-STANDARD](docs/OUTPUT-STANDARD.md) |
| 6/7 | **Score / Codify** | OPA/Rego policy is the method. Then each survey becomes one numbered insight. | [SCORING](docs/SCORING.md) · [INSIGHTS](docs/INSIGHTS.md) |

**The differentiator.** Most of the codified insights are verification-stage failures. Skipped verification does not fail randomly. At population scale it fails systematically, producing confident, reproducible, wrong numbers. The pipeline puts its weight where the lies enter.

---

## Quick start

**Prerequisites:**

- **Go 1.21+ on PATH.** The public NuClide tools install with `go install` into your Go bin dir. No sudo, no root. Check with `go version`.
- **Your own Shodan and Censys credentials.** Discovery is a credentialed step you drive with your own keys. This repo ships none.
- **A scoped target list you are AUTHORIZED to test.** Formal engagement scope, designated targets, written permission. The repo ships no target list, by design. The illustrative addresses in our docs are RFC 5737 ranges that route nowhere on purpose. If you cannot point at the authorization, there is no step two.

```sh
git clone https://github.com/nuclide-research/nuclide-method
cd nuclide-method
make install
```

**Commands:**

| Command | What it does |
|---------|--------------|
| `make help` | Show the target list. |
| `make install` | `go install` the public NuClide tools. |
| `make bootstrap` | Run the environment bootstrap (`./bootstrap.sh`), offers to copy the Claude config. |
| `make chain IPS=ips.txt` | Run the reference assessment chain over your scoped IP list. |
| `make audit` | Run the local boundary checks that mirror CI. |
| `make lint` | shellcheck the scripts and sweep for em-dashes. |

Full walkthrough: [docs/QUICKSTART.md](docs/QUICKSTART.md).

---

## Usage

You supply the scope. The repo ships none. The `IPS=` variable points the chain at a list of hosts you are authorized to probe, and the chain refuses to run without it.

```bash
# scenario: run the full reference chain over a scope you are authorized to test
make chain IPS=ips.txt

# scenario: same run, labeled with a slug for the output directory and tags
./chain/run-chain.sh ips.txt my-engagement

# scenario: pin the egress posture before any outward probe (fail-closed if your VPN drops)
export FOOTPRINT_GUARD='your-vpn-status-check --quiet'
make chain IPS=ips.txt

# scenario: pull dorks and an aimap probe scaffold for a covered platform from the corpus
tome dorks <platform>     # basic | strict | version tiers
tome probe <platform>     # scaffold an aimap-compatible probe

# scenario: arsenal-fanout for one host that looks deeper than the rest
scanner -ips-file one-host.txt -output banners.json     # active-banner prefilter
aimap   -list one-host.txt -o aimap-report.json         # fingerprint plus deep enum
herald  -platform <name> < ip-port.txt > herald.ndjson  # auth posture (targets: IP:PORT, stdin)
# then VERIFY by hand: re-probe the candidate, confirm the data layer, earn the label

# scenario: confirm the boundary controls before you commit anything
make audit                # mirrors CI: no live targets, no PII, no em-dashes
make lint
```

The reference runner ([chain/run-chain.sh](chain/run-chain.sh)) wires the public tools together in the documented order. Private stages are marked as documented gaps with the contract for what they must produce. Illustrative addresses are RFC 5737 documentation ranges. No live target lives in this repo.

---

## Arsenal Matrix

One small, single-purpose tool per stage. Install only what the stage you are running needs. Install commands without a build-from-source footnote resolve a binary from the published tag against a clean module cache; the footnoted rows ([^src] / [^cargo] / [^py]) are the documented exceptions that build from source instead. Source of truth: the [tome corpus][t-tome] (50 platforms) plus [docs/ARSENAL.md](docs/ARSENAL.md).

| Tool | Stage | Input | Output | Install |
|------|-------|-------|--------|---------|
| [aimap][t-aimap] | Fingerprint | IP and port | fingerprint plus deep-enum read | `go install github.com/nuclide-research/aimap@latest` |
| [herald][t-herald] | Verify | `IP:PORT[:SCHEME]` on stdin, `-platform <name>` | NDJSON auth-state findings | `go install github.com/nuclide-research/herald@latest` |
| [tiptoe][t-tiptoe] | Active-Banner | single monitored host | paced banner with block detection | `go install github.com/nuclide-research/tiptoe@latest` |
| [JAXEN][t-jaxen] | Discover | Shodan dork, ASN, CIDR | per-host asset records, SQLite | `go install github.com/nuclide-research/JAXEN@latest` |
| [VisorPlus][t-vplus] | Discover to Score | host or host list | chained passive recon plus enum | `go install github.com/nuclide-research/VisorPlus@latest` |
| [VisorBishop][t-vbishop] | Fingerprint | IP and port | observability tier plus 5-value auth | `go install github.com/nuclide-research/VisorBishop/cmd/visorbishop@latest` |
| [VisorGraph][t-vgraph] | Attribute | IP or cert fingerprint | cert-pivot provenance graph | `go install github.com/nuclide-research/VisorGraph/cmd/visorgraph@latest` |
| [VisorLog][t-vlog] | Ledger | confirmed finding | append-only lifecycle SQLite record | `go install github.com/nuclide-research/VisorLog@latest` |
| [VisorScuba][t-vscuba] | Score | ledger of findings | 0-10 OPA compliance score | `go install github.com/nuclide-research/VisorScuba@latest` |
| [VisorCorpus][t-vcorpus] | Score | LLM-adjacent target | adversarial prompt corpus | `go install github.com/nuclide-research/VisorCorpus/cmd/visorcorpus@latest` |
| [VisorRAG][t-vrag] | Verify to Score | host plus prior findings | RAG-grounded recall, sandboxed probes | `go install github.com/nuclide-research/VisorRAG/cmd/visor@latest` *(builds a `visor` binary; install as `visorrag` to avoid colliding with the umbrella tool)* |
| [VisorGoose][t-vgoose] | Discover | government TLD pattern | gov-TLD AI-infra discovery | `go install github.com/nuclide-research/VisorGoose@latest` |
| [visor][t-visor] | umbrella | tool family | stale-or-missing binary report | `go install github.com/nuclide-research/visor/cmd/visor@latest` |
| [tome][t-tome] | Discover | platform name | dorks, probe configs, OSINT profile | `git clone ... && go build -o tome .` [^src] |
| [scanner][t-scanner] | Active-Banner | harvested IP list | live subset, fresh version, shadow ports | `git clone ... && go build` [^src] |
| [VisorSD][t-vsd] | Discover | org, ASN, CIDR | Shodan exposure records, JSON or CSV | `git clone ... && go build` [^src] |
| [menlohunt][t-menlohunt] | Fingerprint | GCP host | five-phase external attack-surface scan | `git clone ... && go build` [^src] |
| [BARE][t-bare] | Score | scanner findings JSON | exploit modules ranked semantically | `cargo build --release` [^cargo] |
| [recongraph][t-recongraph] | Attribute | IP, CIDR, domain, ASN, cert, banner seed | typed provenance graph | `git clone ...` [^py] |
| [nu-recon][t-nurecon] | Attribute | one IPv4 | single-host JSON: PTR, TLS, crt.sh | `git clone ...` [^py] |
| [winnow][t-winnow] | Verify | aimap or menlohunt candidates | PASS, REFUTED, or DOWNGRADE | `git clone ...` [^py] |

**Non-runs, documented and principled (the only two):**

| Tool | Stage | Why it does not run on the survey set |
|------|-------|---------------------------------------|
| [VisorAgent][t-vagent] | Score (ethical-stop) | Delivers adversarial prompts through real tool-use paths. Controlled targets you own only, never the survey population. |
| VisorHollow | Windows-only | Process-injection detection benchmark. Windows x64 only. Cannot execute on the Linux assessment host. |

Both modules build cleanly. The non-run is a methodology rule, not a build failure.

**Private capabilities appear as documented stage roles only, never with an install line:** the VisorPlus six-phase passive-recon move (Discover), agent-logging-system (post-fingerprint per-enumerator false-positive scan), VisorCAS (the content-addressed false-positive ledger at the verify-to-ledger seam), aimap-profile (target classification and ethics flags before any active probe, Classify), the OSINT Platoon (multi-squad operator attribution on high-severity hosts, Attribute), the garlic recon scripts (one-off discovery and JS-secret primitives), and visor-report (the drill-down HTML report from the ledger, Output).

[^src]: `go install ...@latest` does not resolve a binary from the published tag for this tool. Build from source instead. `tome` works once built (the published tag declares a stale module path). `scanner`, `VisorSD`, and `menlohunt` declare a bare module name in `go.mod`, so the source build is the real path.
[^cargo]: Offline Rust ranker. Not a `go install`. Use Cargo or the release tarball.
[^py]: Python tool. Clone and run under a virtualenv. Not a `go install`.

---

## Numbered insights

The durable IP of this program, the thing a single-tool README cannot show: an accumulating, citable corpus of verification lessons, each one a class of mistake paid for once and never again. Each entry names the mistake, the default it ties to, and the verification rule that catches it. We cite by number.

| Insight | Lesson |
|---------|--------|
| #1 | Protocol-strict surveys self-filter honeypots. The shape gate beats any IP blocklist. |
| #13 | Shipping defaults are load-bearing. The default is the deployment template for the whole population. |
| #15 | Dork hits are not platform instances. Assume roughly half are false positives until proven (the ~50% rule). |
| #16 | A 200 is platform identity, not auth state. Auth posture lives in the body. |
| #68 | State every finding as a depth-by-breadth pair. One axis never smuggles in a claim on the other. |

The numbers are stable citation IDs. A given insight keeps its number across the series, so gaps in the sequence are expected, not missing entries.

Full series, with the three-part shape and sanitized illustrations: [docs/INSIGHTS.md](docs/INSIGHTS.md). Contributions by pull request: add the next number, keep the shape, sanitize hard.

---

## Restraint Ethic

We enumerate metadata. We never exfiltrate. Before any payload is read, the naming pattern already carries the intelligence: a collection prefix that collapses multi-tenancy, an artifact path that attributes an operator, an experiment name that classifies the workload. Reading the data to confirm what the name already told you adds risk and subtracts nothing. We classify sensitivity from field names rather than record contents, and cap any confirmatory read at the smallest sample that establishes severity. A blocked read is "surface open, access not exercised," not a failure to follow through. **Names ARE the finding.**

**No live target data lives in this repo, by design.** This is an engineering control, not a promise. The `.gitignore` keeps scope files, ledgers, and scan output out of the tree, and `make audit` runs the same boundary checks CI does: an em-dash sweep, a sanitization pass, and a check that no live IP, domain, or operator name ever lands in a commit. Every illustration uses RFC 5737 documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `example.com` only.

The full discipline, including the cap on any confirmatory read and the list of endpoints we never call, is in [docs/RESTRAINT-ETHIC.md](docs/RESTRAINT-ETHIC.md). Disclosure routes through [nuclide-research.com][site]. Methodology contributions route through [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Coverage

Where a benchmark README shows a solve-rate, we show the corpus and the verification spine. The one figure we publish as a hard number is the corpus size. Everything else is a slot the maintainer fills from the live ledger, because a fabricated coverage figure is exactly the failure this methodology exists to catch.

| Metric | Value |
|--------|-------|
| **Platforms in the tome corpus** | **50** |
| Surveys run | `<surveys-run>` |
| Verified unauthenticated reads | `<verified-unauth-reads>` |
| Numbered insights codified | `<numbered-insights>` |

The corpus is canonical and versioned. Coverage without verification is not coverage. It is a candidate count. Worked examples covering four corners of the spine live in [examples/](examples/README.md), each held at the verification tier it actually earned: an empty-API-secret confirmation read from source, a population survey that tests the auth-on-default thesis, a schema-only database read held at metadata, and an unauthenticated model-server class anchored to a published CVE.

---

## Citation

```bibtex
@software{nuclide_method_2026,
  title   = {The NuClide Method: a reproducible methodology for
             assessing exposed AI infrastructure},
  author  = {{NuClide Research}},
  year    = {2026},
  url     = {https://github.com/nuclide-research/nuclide-method},
  note    = {Verification-first methodology. Related advisories
             CVE-2025-4364 and ICSA-25-140-11.},
  license = {MIT}
}
```

Related published advisories:

```
CVE-2025-4364     NuClide Research, 2025. Published vulnerability advisory.
ICSA-25-140-11    NuClide Research, 2025. Published ICS advisory.
```

Machine-readable metadata: [CITATION.cff](CITATION.cff).

---

## License and Disclaimer

MIT. See [LICENSE](LICENSE).

> **Disclaimer.** This methodology is for education and **authorized security testing only.** Use it under a formal engagement scope, on designated targets, with written permission, and practice responsible disclosure. The discipline is enumerate metadata, do not exfiltrate. The illustrative addresses in this repo are RFC 5737 documentation ranges that route nowhere on purpose. You run this method at your own risk and you are responsible for staying inside your authorization. If you cannot point at the authorization, there is no step two. Full terms: [DISCLAIMER.md](DISCLAIMER.md).

---

## Acknowledgments

Built on the public NuClide tools listed in the [Arsenal Matrix](#arsenal-matrix), and standing on the established work of [nmap](https://nmap.org), [naabu](https://github.com/projectdiscovery/naabu), [httpx](https://github.com/projectdiscovery/httpx), [nuclei](https://github.com/projectdiscovery/nuclei), and the [Censys](https://censys.io) and [Shodan](https://www.shodan.io) data platforms, which carry the discovery and banner layers the method depends on. README structure follows the convention set by community security-tooling templates: what it is first, then features, quick start, coverage, citation, license, disclaimer.

<div align="right">

[back to top](#nuclide-method)

</div>

<!-- ====================== reference links ====================== -->

<!-- credentials and nav -->
[site]: https://nuclide-research.com
[cve]: https://nvd.nist.gov/vuln/detail/CVE-2025-4364
[icsa]: https://www.cisa.gov/news-events/ics-advisories/icsa-25-140-11

<!-- badges -->
[badge-license]: https://img.shields.io/badge/License-MIT-000000?style=for-the-badge
[badge-version]: https://img.shields.io/badge/methodology-v2.5-0b7285?style=for-the-badge
[badge-commit]: https://img.shields.io/github/last-commit/nuclide-research/nuclide-method?style=for-the-badge
[badge-issues]: https://img.shields.io/github/issues/nuclide-research/nuclide-method?style=for-the-badge
[badge-advisory]: https://img.shields.io/badge/advisories-CVE--2025--4364%20%2F%20ICSA--25--140--11-c92a2a?style=for-the-badge

<!-- badge urls -->
[url-license]: LICENSE
[url-version]: docs/METHODOLOGY.md
[url-commit]: https://github.com/nuclide-research/nuclide-method/commits
[url-issues]: https://github.com/nuclide-research/nuclide-method/issues
[url-advisory]: https://www.cisa.gov/news-events/ics-advisories/icsa-25-140-11

<!-- tool repos -->
[t-aimap]: https://github.com/nuclide-research/aimap
[t-herald]: https://github.com/nuclide-research/herald
[t-tiptoe]: https://github.com/nuclide-research/tiptoe
[t-jaxen]: https://github.com/nuclide-research/JAXEN
[t-vplus]: https://github.com/nuclide-research/VisorPlus
[t-vbishop]: https://github.com/nuclide-research/VisorBishop
[t-vgraph]: https://github.com/nuclide-research/VisorGraph
[t-vlog]: https://github.com/nuclide-research/VisorLog
[t-vscuba]: https://github.com/nuclide-research/VisorScuba
[t-vcorpus]: https://github.com/nuclide-research/VisorCorpus
[t-vrag]: https://github.com/nuclide-research/VisorRAG
[t-vgoose]: https://github.com/nuclide-research/VisorGoose
[t-visor]: https://github.com/nuclide-research/visor
[t-tome]: https://github.com/nuclide-research/tome
[t-scanner]: https://github.com/nuclide-research/scanner
[t-vsd]: https://github.com/nuclide-research/VisorSD
[t-menlohunt]: https://github.com/nuclide-research/menlohunt
[t-bare]: https://github.com/nuclide-research/BARE
[t-recongraph]: https://github.com/nuclide-research/recongraph
[t-nurecon]: https://github.com/nuclide-research/nu-recon
[t-winnow]: https://github.com/nuclide-research/winnow
[t-vagent]: https://github.com/nuclide-research/VisorAgent

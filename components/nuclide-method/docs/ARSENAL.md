# The Arsenal

The method runs on a set of small, single-purpose tools, one per pipeline stage.
This page is the verified install matrix. Every install command in the table
below was run against a clean Go module cache before publication, and a command
is only marked clean when `go install ...@latest` actually produced a binary. The
ones that do not resolve from the published tag carry a footnote with the build
from source that does work. Install only what you need for the stage you are
running. Nothing here is mandatory all at once.

> Source of truth: the platform corpus (`tome`, 50 platforms) plus this matrix.
> The corpus says what to look for. The matrix says what to run. When the two
> disagree, the corpus wins on platform facts and the matrix wins on install.

The illustrative addresses anywhere in these docs are RFC 5737 documentation
ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and illustrative
hostnames are `example.com`. They route nowhere on purpose. See
[../DISCLAIMER.md](../DISCLAIMER.md) for the authorization rule.

---

## Public tools by pipeline stage

```
Discover -> Active-Banner -> Fingerprint -> [ VERIFY ] -> Attribute -> Classify -> Ledger -> Score
```

| Tool | Stage | Input | Output |
|---|---|---|---|
| [tome](https://github.com/nuclide-research/tome) `git clone && go build` [^1] | Discover | platform name | dorks, probe configs, OSINT profile per platform |
| [JAXEN](https://github.com/nuclide-research/JAXEN) `go install github.com/nuclide-research/JAXEN@latest` | Discover | Shodan dork, ASN, CIDR | per-host asset records in a SQLite store |
| [scanner](https://github.com/nuclide-research/scanner) `git clone && go build` [^2] | Active-Banner | harvested IP list | live subset with fresh version and shadow ports |
| [tiptoe](https://github.com/nuclide-research/tiptoe) `go install github.com/nuclide-research/tiptoe@latest` | Active-Banner | single monitored host | paced banner with block detection |
| [aimap](https://github.com/nuclide-research/aimap) `go install github.com/nuclide-research/aimap@latest` | Fingerprint | IP and port | service fingerprint plus deep-enum read |
| [VisorBishop](https://github.com/nuclide-research/VisorBishop) `go install github.com/nuclide-research/VisorBishop/cmd/visorbishop@latest` | Fingerprint | IP and port | observability-tier platform plus 5-value auth state |
| [herald](https://github.com/nuclide-research/herald) `go install github.com/nuclide-research/herald@latest` | Verify | `IP:PORT[:SCHEME]` on stdin, `-platform <name>` | NDJSON auth-state findings from declarative probes |
| [winnow](https://github.com/nuclide-research/winnow) `git clone && python` [^3] | Verify | aimap or menlohunt candidates | PASS, REFUTED, or DOWNGRADE per candidate |
| [VisorGraph](https://github.com/nuclide-research/VisorGraph) `go install github.com/nuclide-research/VisorGraph/cmd/visorgraph@latest` | Attribute | IP or cert fingerprint | cert-pivot provenance graph to named operator |
| [recongraph](https://github.com/nuclide-research/recongraph) `git clone && python` [^3] | Attribute | IP, CIDR, domain, ASN, cert, banner | typed provenance graph with exposure classification |
| [nu-recon](https://github.com/nuclide-research/nu-recon) `git clone && python` [^3] | Attribute | one IPv4 | single-host JSON: PTR, TLS, crt.sh, threat graph |
| [VisorLog](https://github.com/nuclide-research/VisorLog) `go install github.com/nuclide-research/VisorLog@latest` | Ledger | confirmed finding | append-only lifecycle-tracked SQLite record |
| [VisorScuba](https://github.com/nuclide-research/VisorScuba) `go install github.com/nuclide-research/VisorScuba@latest` | Score | ledger of findings | 0-10 compliance score under an OPA policy |
| [BARE](https://github.com/nuclide-research/BARE) release tarball or `cargo build` [^4] | Score | scanner findings JSON | exploit modules ranked by semantic relevance |
| [VisorPlus](https://github.com/nuclide-research/VisorPlus) `go install github.com/nuclide-research/VisorPlus@latest` | Discover to Score | host or host list | one-binary chained passive recon and enum |
| [VisorCorpus](https://github.com/nuclide-research/VisorCorpus) `go install github.com/nuclide-research/VisorCorpus/cmd/visorcorpus@latest` | Score | LLM-adjacent target | adversarial prompt corpus for safety testing |
| [VisorRAG](https://github.com/nuclide-research/VisorRAG) `go install github.com/nuclide-research/VisorRAG/cmd/visor@latest` | Verify to Score | host plus prior findings | RAG-grounded recall driving sandboxed probes |
| [VisorGoose](https://github.com/nuclide-research/VisorGoose) `go install github.com/nuclide-research/VisorGoose@latest` | Discover | government TLD pattern | gov-TLD AI-infra discovery via CT, Shodan, DNS |
| [VisorSD](https://github.com/nuclide-research/VisorSD) `git clone && go build` [^5] | Discover | org, ASN, or CIDR | Shodan exposure records, JSON or CSV |
| [menlohunt](https://github.com/nuclide-research/menlohunt) `git clone && go build` [^6] | Fingerprint | GCP host | five-phase external attack-surface scan |
| [visor](https://github.com/nuclide-research/visor) `go install github.com/nuclide-research/visor/cmd/visor@latest` | (umbrella) | tool family | checks for stale or missing tool binaries |

Every `go install ...@latest` command in the table that is not footnoted was run
and produced a binary. The footnoted entries resolve as modules but do not
`go install` from the published tag, so the build from source is given instead.

[^1]: `tome` published tag `v0.1.0` declares its module path under a stale owner
  segment that no longer matches the repo, so `go install
  github.com/nuclide-research/tome@latest` fails with a version-constraints
  conflict and prints that legacy path in the error. Ignore the printed path and
  build from source: `git clone
  https://github.com/nuclide-research/tome && cd tome && go build -o tome .`
[^2]: `scanner` declares a bare module path (`module shodan-clone`), so the
  `go install` path does not resolve. Build from source: `git clone
  https://github.com/nuclide-research/scanner && cd scanner && go build`.
[^3]: Python tool, not a Go install. `git clone` the repo and run it under the
  project virtualenv per its README.
[^4]: `BARE` is a Rust binary. Install from the release tarball on the repo
  releases page, or build with `cargo build --release`.
[^5]: `VisorSD` declares a bare module path (`module shodan-audit`), so
  `go install github.com/nuclide-research/VisorSD@latest` does not resolve.
  Build from source: `git clone https://github.com/nuclide-research/VisorSD &&
  cd VisorSD && go build`.
[^6]: `menlohunt` declares a bare module path (`module menlohunt`), so
  `go install github.com/nuclide-research/menlohunt@latest` does not resolve.
  Build from source: `git clone https://github.com/nuclide-research/menlohunt &&
  cd menlohunt && go build`.

---

## Documented stage roles (private capabilities)

Some stages are served by capabilities that are not published as installable
tools. They are documented here for the role they play in the pipeline, not as
something you install. If you run the public arsenal you cover the same stages by
other means.

| Capability | Stage role it documents |
|---|---|
| VisorPlus passive-recon phases | the six-phase passive recon move per host |
| agent-logging-system | post-fingerprint per-enumerator false-positive scan |
| VisorCAS | content-addressed false-positive ledger, the verify-to-ledger seam |
| aimap-profile | target classification and ethics flags before any active probe |
| OSINT Platoon | multi-squad operator attribution on high-severity hosts |
| garlic recon scripts | one-off discovery and JS-secret primitives |
| visor-report | drill-down HTML report rendered from the ledger |

---

## Non-runs

Two tools in the family are real and public but do not run against a survey set:

- **VisorAgent** is an ethical-stop. It delivers adversarial prompts through real
  tool-use paths and is for controlled targets you own only, never the survey
  population.
- **VisorHollow** is Windows x64 only. It is a process-injection detection
  benchmark and cannot execute on the Linux assessment host.

A null result from any other tool is a logged result. These two are the only
documented non-runs.

---

## Established third-party tools

The method leans on a small set of standard tools alongside the NuClide arsenal:
**nmap** and **naabu** for port discovery, **httpx** for HTTP probing, **nuclei**
for templated checks, and **Censys** plus **Shodan** as the passive discovery
engines feeding the Discover stage. They are assumed present. The NuClide tools
fill the gaps these do not cover, they do not replace them.

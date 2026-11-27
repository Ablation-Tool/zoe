# Fieldwork

Search Nicholas Kloster's security research by the problem you need to solve.

Fieldwork is a command-line portfolio. It matches a research question to relevant projects, shows how each project approaches the problem, and generates a résumé from the same records. It runs locally with Python 3.10 or later and has no runtime dependencies.

```console
$ python -m fieldwork match "reverse engineer stripped firmware binaries"
Ablation [ablation]
Analyze compiled software with a framework for binary lifting, data-flow analysis, semantic search, and persistent research findings.
Matched: binary, firmware, reverse, stripped
https://github.com/Ablation-Tool/ablation
```

Output above is the first result. The command also shows related projects.

## Nicholas Kloster

I investigate AI infrastructure, applications, and firmware. I build tools to test security assumptions, trace software behavior, and document findings that other researchers can reproduce.

My work includes [Ablation](https://github.com/Ablation-Tool/ablation) for binary analysis, [aimap](https://github.com/nuclide-research/aimap) for AI infrastructure assessment, and [white-bronco](https://github.com/francis-rancid/white-bronco) for coordinated disclosure. Research produces new tooling; the tools make the next investigation easier to repeat.

Before security research, I served eight years in the U.S. Army as an Infantry Staff Sergeant, including two deployments to Kandahar.

[Research site](https://nuclide-research.com) · [Email](mailto:nicholas@nuclide-research.com)

## Find relevant work

| Your question | Start here |
| --- | --- |
| What does this firmware do? | `python -m fieldwork match "firmware binary analysis"` |
| Can an AI agent exceed its permissions? | `python -m fieldwork match "agent permissions prompt injection"` |
| Does every API route enforce authentication? | `python -m fieldwork match "API route authentication"` |
| What evidence belongs in a disclosure? | `python -m fieldwork match "vulnerability disclosure evidence"` |

Matches use weighted keyword overlap. Tags weigh more than descriptions, common plural forms normalize to the same term, and each result lists the words that matched. Scores measure catalog relevance. They do not measure expertise or prove a project's claims.

## Run it

From this checkout:

```bash
python3 -m fieldwork profile
python3 -m fieldwork projects --language Go
python3 -m fieldwork show ablation
python3 -m fieldwork match "AI agent permissions" --json
python3 -m fieldwork contact
```

To install the `fieldwork` command in an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/fieldwork profile
```

Installation may fetch the setuptools build dependency. Running the tool makes no network requests, executes no scanners, and needs no API key.

## Generate a résumé

```bash
python3 -m fieldwork resume
python3 -m fieldwork resume --focus "AI infrastructure security" --limit 5
python3 -m fieldwork resume --focus "firmware reverse engineering" > resume.md
```

The command writes Markdown to standard output. A focused export changes the selected projects, not the person's background. Source attribution travels with the export. [Read the default résumé](RESUME.md).

## Evidence and source material

The catalog contains 18 selected public projects drawn from the owner's portfolio. Descriptions are owner-reported; external links and claims have not been independently verified. A link points to a place to inspect the work. It is not a verification badge.

Source notes live in [docs/SOURCES.md](docs/SOURCES.md). The raw portfolio bundle stays outside this repository because it also contains private project references and research details. CVE credit, numerical performance claims, and vendor acceptance claims are not included in this first catalog.

## Maintain the record

Edit [fieldwork/data/portfolio.json](fieldwork/data/portfolio.json), then run:

```bash
python3 -m fieldwork validate
python3 -m unittest discover -s tests -v
python3 -m fieldwork resume > RESUME.md
```

`validate` checks the data contract and duplicate IDs. It does not check remote repositories. A project marked `verified` must include a `verification` object with `source`, `checked_on`, and `notes` explaining the specific claim checked.

Use a separate dataset without changing the shipped record:

```bash
python3 -m fieldwork --data /path/to/portfolio.json projects --json
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the record format and update rules.

## Work with me

I offer security consultation, scoped penetration testing, vulnerability investigation, firmware reverse engineering, and tooling development. Email **nicholas@nuclide-research.com** with the problem, the available material, and the result you need. We will agree on scope, deliverables, and schedule before work begins.

## Repository map

```text
fieldwork/
  cli.py                 Search, matching, validation, and exports
  data/portfolio.json    Profile and selected project records
tests/                   Retrieval and data-contract checks
docs/SOURCES.md          Provenance and editorial choices
RESUME.md                Generated résumé for readers who do not run the tool
```

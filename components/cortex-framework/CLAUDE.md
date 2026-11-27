# cortex-framework

**Cortex — Authorization Context Analyzer.** A framework for describing code, systems, and behaviors by *what they do* vs. *what they took without asking*. The thesis: operations are neutral; context is what makes something bad. Code can't express intent or consent — context lives in external metadata. Cortex formats that metadata into reviewable, citable analyses and supports side-by-side comparison against a 14-sample reference corpus (malware, supply-chain attacks, ICS, social engineering, LLM prompt injection).

## Language
Python 3.10+ (standard library only — **no `pip install` required**)

## Build & Run
```
# Analyze a sample
python3 analyzer.py analyze examples/iloveyou.md
python3 analyzer.py analyze examples/xz_utils_backdoor.md --html

# Validate a Cortex markdown file conforms to the schema
python3 analyzer.py validate examples/stuxnet.md

# Side-by-side comparison
python3 analyzer.py compare examples/iloveyou.md examples/conficker.md

# Outputs land in output/reports/:
#   <name>.json          — structured data
#   <name>_report.md     — human-readable markdown
#   <name>_report.html   — optional HTML (dark theme)
```

## Layout
```
analyzer.py           # Python CLI — analyze / validate / compare subcommands
framework.md          # full methodology + violation-class taxonomy + reference analyses
genesis.md            # origin story / motivating examples
examples/             # 14-sample reference corpus (Cortex MD files)
  iloveyou.md           # virus
  xz_utils_backdoor.md  # supply-chain
  stuxnet.md            # ICS
  conficker.md          # worm
  ...
output/               # generated reports (.json / _report.md / _report.html)
assets/               # banner SVG
README.md             # quick-start + framework intro + DO NOT USE warning
```

## The framework shape

Every Cortex MD has three sections:

- **SKELETON** — what the thing does (operations, neutral)
- **VIOLATIONS** — what it took without asking (the load-bearing claim)
- **CONTEXT** — why that matters (intent / consent / harm framing)

Optional:

- **REFERENCES** — citations, CVEs, prior analyses

## Claude Code Notes
- Read `framework.md` for the full methodology before drafting a new sample analysis
- The DO NOT USE warning at the top of README is intentional — Cortex is for analysis, not for iteratively reducing flagged violations to slip past LLM detection
- Adding a new sample: drop a `<name>.md` in `examples/` matching the SKELETON/VIOLATIONS/CONTEXT format, then `python3 analyzer.py validate examples/<name>.md` to confirm schema, then `analyze` for reports
- Output JSON shape is documented in `framework.md` and is consumable by downstream tooling
- Built with [Claude Code](https://claude.ai/code)

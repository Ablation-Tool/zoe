# Changelog

All notable changes to the NuClide Method are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-06-19

First public release. Methodology version v2.5.

### Added

- Public release of the verification-first methodology for assessing exposed AI
  infrastructure: the eight-stage pipeline, the discipline layer, the discovery
  moves, the restraint ethic, and the scoring stage.
- The tome corpus reaches 50 platforms, one canonical record per platform
  carrying dorks, probe scaffolds, and an OSINT profile.
- The verification-rung grid is codified: every finding states a depth-by-breadth
  pair (Insight #68).
- The active-banner prefilter is a standing stage that runs before the
  fingerprinter.
- The arsenal matrix: a verified install command per tool, with source-build
  footnotes for the tools that do not resolve from a published tag.
- Engineering controls for the redaction boundary: a CI boundary audit and a
  local mirror script, plus a `.gitignore` that keeps scope files, ledgers, and
  scan output out of the tree.
- Four worked examples, each held at the verification tier it actually earned.

### Changed

- v2.5 makes the methodology the default operating logic rather than a mode you
  switch into.

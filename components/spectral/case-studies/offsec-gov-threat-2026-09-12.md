# Live Scan Study: Offensive Security, Government, and Threat Actor Repos

**Date:** 2026-09-12  
**Spectral version:** 0.1.0 (post CON-020 fix)  
**Signatures loaded:** 28  
**Scan mode:** `--skip-tests` on all repos

## Repos Scanned

| Repo | Category | Size | Notes |
|------|----------|------|-------|
| NationalSecurityAgency/ghidra | Government | 454MB | NSA's flagship reverse engineering platform. Java. Scanned `Ghidra/` source subtree only. |
| cisagov/Malcolm | Government | 173MB | CISA's network traffic analysis platform. Python/Docker. |
| BC-SECURITY/Empire | Offensive / C2 | 111MB | Actively maintained PowerShell C2 framework. Python + PowerShell. |
| ly4k/Certipy | Offensive | 1.3MB | AD Certificate Services attack tool. Python. |
| PowerShellMafia/PowerSploit | Offensive | 8.9MB | Classic pre-AI PowerShell offensive framework. |
| ytisf/theZoo | Malware zoo | 1.9GB | Malware sample archive. Scanned Python wrapper + imports only (samples are zipped binaries). |

---

## Results

| Repo | Findings | False Positives |
|------|----------|-----------------|
| NSA Ghidra | 0 | 0 |
| CISA Malcolm | 0 | 0 |
| BC-SECURITY Empire | 0 | 0 (1 FP found and fixed — see below) |
| Certipy | 0 | 0 |
| PowerSploit | 0 | 0 |
| theZoo (wrappers) | 0 | 0 |

**Total true positives: 0. Total false positives: 0 (after CON-020 fix).**

---

## Findings interpretation

None of the six repos contain AI attribution artifacts. Across ~750MB of source code and tooling:
- No Claude Code project configs
- No Claude/GPT co-author commit headers
- No agentic framework artifacts
- No API response artifacts
- No Copilot workspace configs

**What this means:** As of mid-2026, the actively maintained offensive security and government tooling in this corpus is human-authored with no detectable AI coding-tool involvement at the artifact level. This establishes a baseline for comparison -- if a future version of Empire or a new threat actor toolkit shows CLU-001 or AGT-001 hits, that is meaningful signal.

---

## False positive found and fixed: CON-020

**Pre-fix:** Empire returned 1 finding: `CON-020 c2pa_provenance_metadata` in `empire/server/data/module_source/code_execution/Invoke-IronPython.ps1`.

**Root cause:** The indicator `type: string, pattern: 'c2pa'` matched the substring `c2pa` appearing coincidentally inside a base64-encoded payload embedded in the PowerShell file. The string `c2pa` is short enough (4 chars) to appear in base64 blobs by chance.

**Fix:** Replaced the bare string match with a bounded regex:
```
\bc2pa\.(assertions|manifest|claim|ingredient)\b
```
C2PA metadata in real files uses dot-namespaced keys (`c2pa.assertions`, `c2pa.manifest`). The word-boundary + dot-qualified pattern eliminates base64 collisions while preserving precision on actual C2PA artifacts.

**Post-fix:** Empire returns 0 findings. No other signatures affected.

**Class of false positive:** Short string indicators (<=5 chars) in base64-heavy files. Rule: any single-indicator signature with a pattern under 6 characters should use `type: regex` with word-boundary anchors, not bare `type: string`.

---

## Notes on theZoo

The malware archive itself (zip files in `malware/`) was not scanned -- spectral skips files that fail UTF-8 decoding. The Python wrapper code (`theZoo.py`, `prep_file.py`, `imports/`) returned 0 findings. theZoo's tooling is minimal and old enough to predate AI coding tools.

The interesting use of spectral against a malware archive would be to scan extracted source-code-containing samples (script-based RATs, Python/PowerShell payloads) for AI attribution. That requires unpacking -- a future `--unpack` mode.

---

## Baseline established

Combining both live scan studies:

| Category | Repos | AI Artifact Rate |
|----------|-------|-----------------|
| AI framework repos (AI-heavy dev) | 4 | 47-158 findings/repo with `--skip-tests` |
| Pre-AI legacy C repos | 4 | 0-2 findings/repo (all true positives: real AI adoption) |
| Offensive security tools | 3 | 0 |
| Government tools | 2 | 0 |
| Malware-adjacent | 1 | 0 |

**Signal:** Spectral correctly differentiates AI-native codebases from human-authored codebases across 14 repos with 0 false positives after the CON-020 fix.

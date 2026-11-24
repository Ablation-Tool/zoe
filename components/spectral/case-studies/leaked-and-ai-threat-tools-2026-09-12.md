# Case Study: Leaked Malware Source + AI-Attributed Threat-Adjacent Tools

**Date:** 2026-09-12  
**Spectral version:** 0.1.0  
**Methodology:** vxug MalwareSourceCode archive extraction + GitHub code search for AI attribution in security-relevant repos

---

## Part 1: Leaked Ransomware Source

### Source

vxunderground MalwareSourceCode repo (`github.com/vxunderground/MalwareSourceCode`).
The archive is 3.3GB; ransomware samples extracted with `7z x -p infected`.

| Sample | Extracted size | Source |
|--------|---------------|--------|
| Conti v3 | 6.2MB | `Win32/Ransomware/Win32.Conti.c.7z` |
| Babuk (Windows + ESXi) | 12MB | `Win32/Ransomware/Ransomware.Multi.Babuk.c.rar` |

Conti v3 contains the full C++ locker/decryptor/cryptor source (`conti_v3.sln`). Babuk contains both the Windows locker and the ESXi/NAS variant with ChaCha8 + curve25519-donna encryption.

### Results

| Sample | Findings | Result |
|--------|----------|--------|
| Conti v3 | 0 | CLEAN |
| Babuk (Windows + ESXi) | 0 | CLEAN |

### Additional samples scanned

Python malware: `Trojan.Python.AngstStealer`, `Stealer.Python.GMBA.Manipulator`, `Python.v1ru5`  
Stealers: `Win32.TitanStealer.b`, `Win32.PryntStealer.g`, `Win32.Rust.LucaStealer`, `Win32.qBitStealer`  
Ransomware variants: `Win32.Ransomware.Chaos.e`, `Win32.Ransomware.Yashma.a`  
Android: `Android.Octo` (banking trojan)

All returned 0 findings.

### Interpretation

The vxug archive was assembled primarily between 2021 and 2023, before widespread AI coding tool adoption. Conti was active through early 2022; Babuk through 2021. Neither uses AI coding tools -- this is the pre-AI baseline for ransomware-class malware.

**Significance:** This is the control group. When a 2025-era ransomware sample shows CLU-001 or AGT-001 findings, the contrast against this baseline will be the finding.

---

## Part 2: GitHub Code Search -- AI Attribution in Threat-Adjacent Repos

### Method

Used GitHub code search API (authenticated via `gh` CLI) to search for combinations of known AI attribution strings with offensive/security keywords:

- `noreply@anthropic.com + keylogger` -> 20 results
- `noreply@anthropic.com + rat` -> 149k results (word too common; filtered)
- `noreply@anthropic.com + bypass` -> 14k results (too broad)
- `claude sonnet + shellcode` -> 1,608 results

Filtered for repos where the AI attribution string co-occurs with genuine offensive capability (not just documentation references).

### Significant finds

#### 1. tandem-browser -- browser security tool built entirely with Claude Code

**Repo:** `hydro13/tandem-browser`  
**Description:** Electron browser with multi-phase security shield: script/content guard, keylogger detection, crypto miner detection, clipboard hijacker detection, phishing indicator analysis.

**Spectral scan results:**
```
60 findings (--skip-tests)
  x21  CLU-001  claude_code_coauthor_header  HIGH  Anthropic/Claude
  x21  CLU-003  claude_code_pr_footer        HIGH  Anthropic/Claude
  x 8  AGT-040  mcp_tool_server_artifacts    MED   Generic/MCP
  x 7  AGT-001  claude_code_project_dir      HIGH  Anthropic/Claude
  x 2  INF-003  ollama_local_server          HIGH  Ollama/Local
  x 1  INF-001  anthropic_api_response_headers HIGH Anthropic/Claude
```

21 files contain Claude Code co-author trailers. 7 CLAUDE.md project config files across the repo. MCP tool server configs. This is a security tool -- including code designed to detect keyloggers, crypto miners, and clipboard hijackers -- built end-to-end using Claude Code. The PHASE-3.md spec document describes the keylogger detection architecture and is itself Claude-attributed.

**What this demonstrates:** Defensive security tooling is being built with Claude Code. The repo is not malicious -- but it proves that browser-level monitoring and script analysis code (the same primitives used in surveillance tools) is being authored by AI at scale.

#### 2. anamnesis -- automated exploit generation using Claude Agent SDK

**Repo:** `SeanHeelan/anamnesis-release`  
**Description:** Academic security research tool. Uses Claude (via Claude Agent SDK) as an autonomous agent to find exploitable primitives in binary targets. Includes `claude-primitive-finder/claude-primitive-finder.py` -- a full agentic loop that feeds disassembly and binary analysis to Claude, iterates on candidate exploit primitives, and generates shellcode.

**Spectral scan results:**
```
3 findings
  x2  AGT-040  mcp_tool_server_artifacts        MED  Generic/MCP
  x1  AGT-002  claude_agent_session_transcript  HIGH Anthropic/Claude
```

The `experiment-results/` directory contains Claude API session transcripts from actual exploit generation runs. AGT-002 fired on a recorded conversation where Claude was working through a primitive-finding task. MCP configs for the tool's own server.

**Significance:** This is Claude operating as an exploit development assistant -- specifically finding memory corruption primitives and generating exploit chains. The tool is published academic research (not malicious). But the artifact pattern -- Claude session transcripts + MCP configs in a repo with shellcode generation -- is exactly what spectral would find in a threat actor toolkit if one existed.

---

## Summary table: full threat-adjacent corpus

| Corpus | Samples | AI Findings | Notes |
|--------|---------|-------------|-------|
| vxug archive (2021-2023 malware) | Conti v3, Babuk, 9 others | 0 | Pre-AI era baseline |
| GitHub: keylogger + Claude hits | tandem-browser | 60 | Defensive security tool built with Claude Code |
| GitHub: shellcode + Claude hits | anamnesis | 3 | Academic exploit-gen agent, Claude session transcripts |

---

## Detection capability demonstrated

spectral correctly identified:
- A browser security tool authored by Claude Code (60 findings, all high confidence)
- An autonomous exploit generation agent that uses Claude (AGT-002 on actual session transcripts)
- 0 false positives across the pre-AI malware corpus

The gap: no threat-actor malware from 2024-2025 with source code was available for scanning. The vxug archive stops at 2023. The GitHub search found defensive and research tools; malicious actors do not publish to public repos.

**The next step** is scanning commodity malware samples from 2025 that circulate through threat intel feeds (MISP, IntelMQ, VirusTotal Intelligence). Those samples postdate the AI coding tool adoption curve and are the most likely to contain AI attribution artifacts if threat actors are using these tools.

---

## Methodology note: extracting leaked archives

```bash
# Password for vxug samples
7z x Win32.Conti.c.7z -o./conti -p infected

# Scan extracted source
spectral scan ./conti/ --json > conti-findings.json

# Git history if the leak preserves git metadata  
spectral git ./conti/ --json > conti-git.json
```

The Conti leak does not preserve git history -- the archive contains only source files, no `.git/` directory. If a future leak preserves version control history, `spectral git` would surface the full development timeline and any AI attribution introduced during development.

# Case Studies

Live scans against real public repositories. Each study documents target selection, raw results, analysis, and any signatures fixed or added as a result.

| Date | Study | Repos | Findings | Notes |
|------|-------|-------|----------|-------|
| 2026-09-12 | [AI frameworks vs pre-AI](live-scan-2026-09-12.md) | AutoGPT, langchain, anthropic-sdk-python, crewAI, curl, tmux, jq, redis | 47-158 (AI); 0-2 (pre-AI) | Established `--skip-tests` flag; confirmed 0 FP on pre-AI corpus |
| 2026-09-12 | [Offensive / Gov / Threat](offsec-gov-threat-2026-09-12.md) | NSA Ghidra, CISA Malcolm, BC-SECURITY Empire, Certipy, PowerSploit, theZoo | 0 across all six | CON-020 FP found and fixed; baseline established |
| 2026-09-12 | [Git history attribution](git-history-2026-09-12.md) | spectral, PALA-rust, AutoGPT, curl, Nidhogg | AutoGPT 100% AI; PALA 67.6%; offensive/pre-AI 0% | AutoGPT uses Claude Code; PALA first hit 2026-04-24; leaked toolkit methodology documented |
| 2026-09-12 | [Leaked malware + AI threat tools](leaked-and-ai-threat-tools-2026-09-12.md) | Conti v3, Babuk, 9 other malware families, tandem-browser, anamnesis | 0 on pre-AI malware; 60 on Claude-built security tool; 3 on exploit-gen agent | Pre-AI baseline confirmed; Claude Code building defensive + exploit tooling found on GitHub |
| 2026-09-12 | [AI-written malware scanned by AI-written scanner](ai-written-malware-2026-09-12.md) | aphid (AI/ML infra worm, 1705 lines) | 2 findings (1 TP, 1 FP) | INF-003 correct; AGT-002 FP on OpenAI-compatible message construction; signature narrowed to UUID-anchored patterns |

## Reference corpus

Repos scanned to date. "Clean" = 0 findings with `--skip-tests`. "True positives" = findings confirmed as real AI artifact.

| Repo | Category | Result | Notable findings |
|------|----------|--------|-----------------|
| AutoGPT | AI framework | 158 findings | 13x CLAUDE.md, Claude Code heavily used across monorepo |
| langchain | AI framework | 47 findings | LangChain chain files, MCP configs, Claude attribution |
| anthropic-sdk-python | AI framework | 47 findings | VCR cassettes; production source clean |
| crewAI | AI framework | 81 findings | AGT-030 self-matches crewAI's own output format |
| curl | Pre-AI / C | Clean | |
| tmux | Pre-AI / C | 1 finding (COP-002) | .github/copilot-instructions.md -- real Copilot adoption |
| jq | Pre-AI / C | Clean | |
| redis | Pre-AI / C | 2 findings (INF-003) | vector-sets/examples uses Ollama -- real AI integration |
| NSA Ghidra | Government | Clean | No AI artifacts in 454MB Java codebase |
| CISA Malcolm | Government | Clean | |
| BC-SECURITY Empire | Offensive / C2 | Clean | CON-020 FP before fix; clean after |
| ly4k/Certipy | Offensive | Clean | |
| PowerSploit | Offensive | Clean | |
| ytisf/theZoo | Malware zoo | Clean (wrappers) | Samples are zipped binaries, not scanned |
| Conti v3 (vxug, leaked) | Ransomware source | Clean | Pre-AI era (2022); extracted from vxug archive |
| Babuk Win32+ESXi (vxug, leaked) | Ransomware source | Clean | Pre-AI era (2021); extracted from vxug archive |
| hydro13/tandem-browser | Security tool (Claude-built) | 60 findings | Browser malware-detection tool built with Claude Code; 21x CLU-001, 7x AGT-001 |
| SeanHeelan/anamnesis | Exploit-gen research | 3 findings | Claude Agent SDK autonomous exploit primitive finder; AGT-002 on live session transcripts |
| aphid (VDT tools, local) | AI-written worm | 2 findings (1 TP, 1 FP) | INF-003 on Ollama target; AGT-002 FP on message construction code; led to AGT-002 v1.1 fix |

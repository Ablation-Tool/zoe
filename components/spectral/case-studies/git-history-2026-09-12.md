# Case Study: Git History Attribution Scan

**Date:** 2026-09-12  
**Spectral version:** 0.1.0  
**Command:** `spectral git <repo>`

## What the git scanner does

`spectral git` walks the full commit history of a repository and checks each commit's message body against a set of AI attribution patterns. It answers:

- When did this repo first use AI coding tools?
- What fraction of commits carry AI attribution?
- Which tools were used (Claude Code, Copilot, Devin, Cursor, etc.)?

This is distinct from `spectral scan` (file content and filesystem artifacts). The git scanner operates at the version control layer -- it finds attribution that authors left in commit metadata, co-author trailers, and PR footers. It is deterministic and non-probabilistic: a Claude Code co-author trailer is a positive identification, not a probabilistic score.

## Repos scanned

| Repo | Commits | AI commits | First AI commit | Rate |
|------|---------|------------|-----------------|------|
| spectral (this repo) | 5 | 5 | 2026-09-12 | 100% |
| PALA-rust | 71 | 48 | 2026-04-24 | 67.6% |
| AutoGPT | 1* | 1 | 2026-09-04 | 100%* |
| curl | 1* | 0 | N/A | 0% |
| Nidhogg (rootkit) | 1* | 0 | N/A | 0% |

*depth=1 clone; only the latest commit is visible. Full history requires a full clone.

## Key finding: AutoGPT uses Claude Code

AutoGPT's latest commit (2026-09-04) carries a Claude co-author trailer:

```
hotfix(frontend/marketplace): show a Coming soon label on expert pages instead of hire actions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

The AI agent framework is itself developed using an AI coding tool. This is consistent with the file-level scan result (171 findings) which found 13 CLAUDE.md project config files across the AutoGPT monorepo.

## PALA-rust attribution timeline

PALA-rust (a file carver tool) shows the full AI adoption arc:

- **Pre-AI phase**: Commits before 2026-04-24 have no AI attribution
- **AI adoption**: 2026-04-24, first Claude Code commit appears (`feat: add nuclei adapter`)
- **Sustained use**: 48 of 71 total commits (67.6%) carry Claude co-author attribution through 2026-09-12

This establishes a temporal fingerprint: an external observer with only the public git history can identify the exact commit where AI-assisted development began.

## Offensive / malware repos

All depth=1 clones of offensive tools (Nidhogg, WinPwn, VX-API, Certipy, PowerSploit) returned 0 AI-attributed commits. This holds for both the file scanner and the git scanner.

**Interpretation:** Existing publicly available offensive toolkits in this corpus were authored without detectable AI coding tool involvement as of 2026-09-12. This will change. The git scanner provides the mechanism to track when it does.

## Leaked toolkit scanning methodology

The Conti, Lockbit 3.0, and Babuk source code leaks are not available on GitHub (mirrors are taken down via DMCA). They are accessible through:
- vx-underground.org sample archive
- Threat intel platform feeds (MISP, IntelMQ, etc.)
- Academic security research archives

To scan a leaked toolkit with spectral:

```bash
# Extract and scan file-level artifacts
spectral scan ./conti-leaked-src/ --skip-tests --json > conti-findings.json

# If the source is in a git repo (some leaks preserve git history)
spectral git ./conti-leaked-src/ --json > conti-git.json

# Pipe to Claude Code for attribution analysis
# "Read conti-findings.json. Identify which AI tools if any were used and when."
```

What to look for:
- `CLU-001` / `CLU-003`: Claude Code commit trailers -- explicit, deterministic
- `AGT-001`: CLAUDE.md project config files -- would mean the author ran Claude Code interactively
- `COP-001` / `COP-002`: Copilot workspace configs or accept rate comments
- `CUR-001`: .cursorrules or .cursor/settings.json

A finding in any of these categories in a known threat actor toolkit would be significant: it would establish that the actor used a named commercial AI coding service, narrowing attribution and potentially exposing account-linkable artifacts.

## What's next

The most impactful scan target for this methodology is newly emerged threat actor toolkits (2025+), particularly:
- Ransomware-as-a-Service builders where the build system was shared with affiliates
- Commodity RATs sold on forums where the author may have used AI to write features
- Phishing kit generators where AI-generated templates leave content signatures

The content/ category signatures (CON-001 through CON-020) are designed for this: AI-generated phishing emails have characteristic opener and closer patterns regardless of whether any attribution artifact is present.

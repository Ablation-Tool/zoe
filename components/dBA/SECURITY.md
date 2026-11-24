# Security Policy

## Scope

dBA (defenseBridge for ASR) is a metadata firewall for ASR pipelines. Its
threat model covers attacker-controlled audio container metadata (ID3, RIFF INFO,
Vorbis comments, structural anomalies). It does not inspect waveform content,
perform authentication, or provide transport security — those are infrastructure
concerns for the deployment layer.

## Supported versions

Only the latest released version on the `main` branch receives security fixes.

## Reporting a vulnerability

**Do not open a public GitHub issue for security findings.**

Email: nicholas@nuclide-research.com

Include:
- A description of the vulnerability and its impact.
- Steps to reproduce or a proof-of-concept file / request.
- Any suggested remediation (optional).

You will receive an acknowledgement within 2 business days.

## Response SLAs

| Severity | Acknowledgement | Fix target |
|---|---|---|
| Critical | 1 business day | 7 days |
| High | 2 business days | 30 days |
| Medium | 5 business days | 90 days |
| Low | Best effort | Next release |

## In-repo SSDF practice coverage

The following NIST SP 800-218 (SSDF v1.1) practices have in-repository evidence.
This is not a compliance certification — SSDF is a process framework with no
accreditation body. Many practices also require GitHub repository settings
(branch protection, required reviews, secret scanning) that are outside this file.

| Practice | Evidence |
|---|---|
| PO.1.1 | This document (threat model, scope, posture) |
| PO.3.1 | `requirements.txt` (pinned versions); `Dockerfile` (pinned base digest) |
| PO.3.2 | `.github/workflows/ci.yml` (pinned action versions) |
| PO.4.1 | Acceptance criteria: all tests green, bandit MEDIUM+ = 0, pip-audit clean |
| PS.2.1 | GitHub Releases should attach SHA-256 checksums for each tagged release |
| PW.4.1 | `pip-audit` step in CI rejects on any known-vulnerable dependency |
| PW.4.4 | Dependabot weekly scans (`.github/dependabot.yml`) |
| PW.5.1 | No `shell=True`; no hardcoded secrets; no raw tag values in logs or responses; `bandit` SAST in CI |
| PW.6.1 | Pinned `requirements.txt`; pinned Dockerfile base image digest |
| PW.7.2 | `bandit -r main.py` in CI, report uploaded as artifact |
| PW.8.1 | `pytest` in CI with ffmpeg installed so integration suite does not skip |
| RV.1.1 | This document (contact, disclosure process) |
| RV.1.2 | `pip-audit` in CI; Dependabot alerts |
| RV.2.1 | Response SLA table above |

### Settings you must enable on the GitHub repo

- **Branch protection on `main`**: require passing CI, require at least one
  reviewer approval, disallow direct pushes.
- **Secret scanning**: GitHub Advanced Security → Secret scanning → enabled.
- **Push protection**: prevents secrets being committed in the first place.
- **Signed commits**: require GPG or SSH commit signing in branch protection.

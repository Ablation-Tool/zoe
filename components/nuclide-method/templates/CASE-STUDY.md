---
title: "<Finding or survey title, short, news-headline style>"
date: 2026-MM-DD
type: case-study  # or survey, methodology
sector: commercial  # or government, education, healthcare
tags: [...]
---

# <Title>

_NuClide Research . <date> . <one-line sub-header, what this case study covers>._

## Summary

<2 to 4 sentences. What was found, why it matters, who it affects. No buildup.
Lead with the conclusion.>

## Thesis fit (when applicable)

<If the case study confirms, extends, or falsifies the auth-on-default thesis or
a numbered Insight, state which and how. Otherwise omit this section.>

---

## Recon

<What was searched and where. The seed (platform, dork, port set, cert CN). The
population pulled and from which engine. Liveness after active banner check, not
raw candidate count. A null result is a logged result, never a skip.>

## Discovery

<Which hosts surfaced and on what signal. Rank by discriminating power: protocol
and domain-specific features (OpenAPI info.title, semantic routes, vendor
response headers) are claim-promotable. A shared port, a generic banner, or a
single substring is candidate-only and never promotes a claim on its own.>

## Per-finding entries

**One block per finding.** A finding is one host or one operator where a
specific exposure was verified. A survey may carry many. A single-host study
carries one.

### F<N>. `<target identifier>`

#### What was found

<Plain description of the observed state. What the probe returned. What was
visible. No inference, only what was directly observed. Cite the exact response
(status code, JSON key, body string) that established the claim.>

#### Verification (tier explicit)

State the status as a pair. Inner rung is depth (code vs live). Outer rung is
breadth (host vs population). Never use language above the rung you are on.

- **Inner rung:** A (logic / source reading) or B (released artifact exercised
  in a realistic stack).
- **Outer rung:** 0 (no live host), 1 (one in-scope host), or 2 (population,
  fingerprint + sampling + dedup).
- **Tier marker:** Verified (probe ran, response established the claim) /
  Surface open, access not exercised (port or endpoint answered, the read was
  blocked or deliberately not driven, often by the restraint ethic) /
  Candidate (a scanner or dork flagged it, nothing confirmed).
- **Exact remaining steps** to reach the next rung on each axis.

Reaching outer-1 by exercising the request demonstrates inner-B for that host.
Inner-A / outer-1 means fingerprinted in scope, deliberately not exercised
(restraint ethic). Inner-B / outer-1 means exercised against the live in-scope
host. The tier is never auto-upgraded.

#### Finding

<The confirmed claim, scoped to the rung. If inner-A, state it at code level. If
the access surface is open but not exercised, write "surface open, access not
exercised", not "exploitable".>

#### Impact

<Operational consequence at the confirmed rung. Distinguish what the probe
directly verified from what would be reachable via further chain steps not
exercised. Translate to what the operator stands to lose: data class, exec
surface, claimable admin state. Who is downstream if attributed: customers,
users, data subjects.>

#### Remediation

<Concrete, real-world fix. Copy-paste-grade config where it applies. What the
operator changes, in one or two sentences plus a config block.>

#### Toolchain provenance (stage roles)

| Stage | Role | Contribution |
|---|---|---|
| 0, Discover | Harvest / passive engine | <what it found, with the specific signal> |
| 0c, Liveness | Active banner check | <live subset, FP strip, fresh version> |
| 1, Fingerprint | Service fingerprinter | <how the platform was confirmed> |
| 2, Verify | Primary-source probe | <the request + the response that proved the claim> |
| 3, Attribute | Attribution / cert pivot | <mechanism, or "n/a, bare cloud IP"> |
| 4, Classify | Target classifier | <category> |
| 5, Ledger | Ledger ingest | <finding ID, severity, lifecycle status> |
| 6, Score | Compliance scorer | <score + violation code> |
| 6, Rank | Module ranker | <top match + score + tier verdict> |

**Stages that ran but added no unique signal:** <list, one line each, why the
null is recorded. No silent skips.>

**Load-bearing chain:** <comma-separated sequence of stages each strictly
necessary to reach the finding.>

---

## Cross-survey analysis

<For surveys. Patterns across findings: persistence ratios, provider
distributions, population deltas vs prior surveys. Cite Insights by number.>

## Methodology, what this case study adds

<If the work produced a new Insight or extended one, write it here and cross-link
the insight file.>

## Honest negative space

<What this method cannot see. Where confidence is lossy. Coverage gaps.
Carry-forward queries.>

## Toolchain provenance (survey level)

```
<linear or tree view of the chain that produced the case study>
```

## See also

<links to related case studies, baseline surveys, insight files>

---

## Conventions

### Verification rungs

State the status as a pair: inner (depth) and outer (breadth). The axes vary
independently. Never use language above the rung. A logic reproduction is an
inner-A cross-check, not a promotion. The line that matters for the inner axis
is code vs live: was the request exercised against the real artifact.

### Voice

Hemingway prose. No em dashes. No two-beat reveals. No "we discovered" or
"interestingly" framing. State the finding, explain the consequence, cite the
source. The reader is a peer practitioner.

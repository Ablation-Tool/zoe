# Output Standard

A survey is not finished when the scan stops. It is finished when it has produced
the artifacts that let someone else trust the numbers. The scan is the easy part.
The artifacts are the part that makes the work admissible.

This page defines the deliverable set. Run the method, produce these, and an
adopter ends a survey with the same records we do. Skip one and the survey has
under-delivered, even if it found something. The shapes live in
[`templates/`](../templates/). Start from a template every time.

One rule sits above all of them: absence of a finding is not absence of risk. A
clean survey still produces the full artifact set. A negative result is a result,
and it is published like any other.

---

## The artifact set per survey

Every survey produces all of these. They are not a menu.

| # | Artifact | Where it lands | When |
|---|----------|----------------|------|
| 1 | Case study | `case-studies/` | one per target, narrative arc |
| 2 | Ledger entries | the append-only ledger | one per confirmed finding |
| 3 | Query/dork catalog entry | `queries/` | one per verified query, with FP traps |
| 4 | Numbered Insight | the insight series | at least one when the survey taught a lesson |
| 5 | Findings breakdown | next to the case study | one per survey, plain English |
| 6 | Session analysis | `analysis/` | one per session, written at session end |

A survey that touches one target produces one case study. A session that touches
several targets, ships a tool fix, and finds nothing new still produces one
session analysis. The case study covers a target. The analysis covers a session
arc. They are different records and both get written.

---

## 1. The case study

The case study is the narrative. It carries the reader from a cold IP to a fixed
exposure in the order the work actually happened. The arc is fixed:

```
discovery -> verification -> finding -> impact -> remediation
```

- **Discovery.** How the target surfaced. The dork, the port sweep, the CT-log
  delta. State which channel found it and what the other channels said. A
  single-channel hit is a single-channel hit; say so.
- **Verification.** The load-bearing section. What turned the candidate into a
  finding. The data-layer probe, the marker check, the full-record pull. Show the
  request and the response shape that earned the label. A 200 alone never earns
  it.
- **Finding.** What is exposed, stated as a class: an unauthenticated vector DB, a
  claimable admin state, a PII-shaped schema. Report the schema and the field
  names, never the records.
- **Impact.** What an actor with bad intent does with this. Tied to what the owner
  can lose, not to a generic severity word.
- **Remediation.** The concrete fix. The config line, the auth toggle, the exact
  re-probe command that confirms the fix held. A fix that ships with its own
  verification command remediates faster.

Every case study ends with a **toolchain-provenance block.** This traces the
actual invocation order, the tools that ran and the sequence they ran in, so the
method is self-documenting and the survey is reproducible. It is the proof that
the arsenal ran and that it ran in order, not a curl loop dressed up after the
fact.

```
Toolchain provenance
  discover     -> <harvest step>            (population: raw N)
  active-banner-> <banner step>             (live: M of N)
  fingerprint  -> <fingerprint step>        (identified: K)
  fp-monitor   -> <quality monitor>         (FP candidates: flagged / clean)
  verify       -> <data-layer probe>        (confirmed: C)
  attribute    -> <cert-pivot step>         (operator: named / unresolved)
  classify     -> <profile step>            (category + ethics flags)
  ledger       -> <ingest step>             (entries: C)
  score        -> <compliance + ranking>    (score: 0-10)
```

Sanitize as you write. Any host shown in a case study uses an RFC 5737 doc
address (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and a doc domain
(`example.com`, `example.org`). The class is the finding. The specific store
never appears.

Template: [`templates/CASE-STUDY.md`](../templates/CASE-STUDY.md).

---

## 2. The ledger entry

Every confirmed finding lands in the append-only ledger. One entry per finding.
This is the record of work, not a terminal print, and not a file you overwrite.

The lifecycle status runs:

```
open -> disclosed -> acknowledged -> remediated -> verified
```

plus `archived` for a finding that needs no outreach (a personal device, a
wrong-category target). A status change **appends** a timestamped note. It never
overwrites the prior state. Lifecycle history is never destroyed, so the entry
reads as a timeline: when it was found, when it moved, what moved it.

The ledger is append-only for a reason. It makes the pipeline resumable. A survey
interrupted at any stage picks up from the ledger instead of rerunning from
scratch. It is also a discovery substrate: probing IPs already recorded surfaces
stacked exposures, and every hit there is a host already known to be exposed once
over.

An entry carries, at minimum: the finding class, the verification tier (below),
the lifecycle status with its timestamped note history, and a pointer to the case
study that holds the narrative. It does not carry a real target, a recipient
name, or an abuse address. Routing stays out of the public record.

Shape: the ledger fields above. The ledger tool appends them on ingest, so there is no standalone template.

---

## 3. The query / dork catalog entry

Every verified query earns a catalog entry in `queries/`. The entry is what stops
the next survey from re-running a query that is already known to lie. Its job is
not to list the query. Its job is to carry the **FP traps** so they are not
re-discovered the hard way.

An entry records:

- **The query**, verified, with the channel it runs on.
- **Raw count vs confirmed count.** A single-token dork's hit population runs
  about half false positives: forks, reverse proxies passing a title through,
  clones, coincidental substring matches. Quote both numbers side by side. A
  population figure derived from a raw count alone is off by about a factor of
  two and the entry says so.
- **The mandatory identity marker.** The probe that separates a real instance
  from a substring match. Without it the count is a candidate, not a finding.
- **The FP traps.** The known ways this query lies: the substring that matches an
  unrelated word, the marketing page that reflects the brand string, the indexer
  filter that is itself a substring match. Each trap is written so the next
  adopter sees the rake before stepping on it.

A query with a zero result is still cataloged. Zero means generate variants, not
stop, and the variants tried plus the zero they returned are part of the record.
The product is unmapped, not absent, until the variant space is exhausted.

Shape: the query-catalog fields above. One entry per verified dork, recorded with its false-positive traps.

---

## 4. The numbered Insight

When a survey teaches a generalizable lesson about how to do the research, it
extracts a numbered Insight into the series. At least one per survey that taught
something. This is the compounding asset. Surveys produce data; insights produce
the method that makes the data trustworthy. A survey that produces a finding but
no insight has under-delivered.

An Insight is a class of mistake, not a single host. It is sourced to the survey
that produced it and cited by number in later case studies. A false-positive
signature discovered during a survey is the strongest insight of all,
because the finding is one host and the signature is every future survey.

Claim the next free number, write the entry from the template, and cite the
survey behind it. The series grows by one disciplined entry at a time.

Template: [`templates/INSIGHT.md`](../templates/INSIGHT.md).

---

## 5. The findings breakdown

One per survey, written in plain English, sitting next to the case study. The
case study is for the reader who knows the stack. The breakdown is for the owner
who has to fix it and may not. One finding per block. No jargon without an
explanation.

Each block answers four questions:

- **What happened.** The endpoint, the service, the data, in one paragraph.
- **What this means.** If an actor with bad intent had found this first, what
  could they do.
- **How we found it.** One sentence. The tool or technique that surfaced it.
- **The fix.** Concrete. One or two sentences. What the operator does, now.

Each block carries its severity (critical / high / medium / low) and its verified
state (yes / no / partial). Evidence is endpoint plus status plus the data shape
returned. Never full credentials, never a full record. A key prefix only, where a
secret has to be shown at all.

Template: [`templates/FINDINGS-BREAKDOWN.txt`](../templates/FINDINGS-BREAKDOWN.txt).

---

## 6. The session analysis

Written at session end, every session. Not a writeup of the interesting sessions
only. It is the standard closing artifact, the same way the session continuity
file is. A case study covers one target; an analysis covers one session arc,
which may touch several targets, dispatch parallel work, ship a tool fix, and
produce no new finding. All of that is worth recording.

The analysis carries: an overview of the arc, the tooling that ran, the
methodology applied, an execution trace, the findings (severity-labeled and
evidence-gated), a risk assessment, recommendations, the limitations, and any
proof-of-concept illustrations. Add a row to the analysis index when you write
it, so the session is discoverable later.

The limitations section is not boilerplate. Every survey carries a statement of
what the method could not see and where confidence is lossy. "This platform is
banner-dark and needs an active sweep" is a finding. "There is no fingerprint for
this category yet" is a finding. Document the failures as honestly as the
successes. Honest negative space is part of the deliverable.

Shape: the session-analysis fields above. Written at session end, it records what changed and what is next.

---

## Every finding follows the report shape

Inside the case study and the breakdown, each finding is written to one shape:

- **What.** The vulnerability or misconfiguration, stated as a class.
- **Why it matters.** The business and technical impact, tied to what the owner
  can lose.
- **Chain context.** How this finding connects to the others. A low plus a medium
  plus a misconfiguration is an unmapped critical path. The chain is worse than
  the sum of its parts, and the report says how.
- **Remediation.** The actionable, real-world fix, with the re-probe command that
  confirms it held.
- **References.** CVEs, documentation, prior research, the Insight numbers it
  exercises.

---

## The verification tier, and the rule that it is never auto-upgraded

Every finding carries a verification tier. The tier states what was actually
exercised, not what could have been.

- **Verified.** A 200-with-data read confirmed the exposure. The artifact backs
  the claim.
- **Surface open, access not exercised.** The port or endpoint answered, but
  access was blocked or deliberately not driven to a read. This is not a confirmed
  finding. The report says so in those words.
- **Candidate.** A scanner or a dork flagged it. Nothing has been confirmed.

The tier is two axes, not one. Depth is how deeply the behavior was validated,
code-read versus live binary. Breadth is how widely it was observed, one host
versus a measured population. The two move independently, and the report states
the pair. Confirming a behavior in the binary while declining to scan the
internet for it is a chosen position, high depth and low breadth by design, not
an unfinished step. That is the restraint posture, and it is a verification state,
not a gap.

**The tier is never auto-upgraded.** A finding does not become "verified" because
time passed, because a prior session said so, or because the read looks like it
would obviously work. It becomes verified when the read runs and the data comes
back. A cross-session claim is re-probed before it is propagated, not trusted on
the strength of a note. A blocked read is reported as "surface open, access not
exercised," never quietly promoted to a finding. No tier label ships without the
evidence to back it.

---

## The boundary, restated

Every artifact above is written for a public repo. The same contract governs all
of them: no real target, no researcher PII, no disclosure routing, RFC 5737 doc
addresses only, the class is the finding and the records are never shown. The
full contract is in [CONTRIBUTING.md](../CONTRIBUTING.md). Sanitize as you write,
not after, and run the boundary audit before you push.

Produce the six artifacts, hold the verification tier honest, and the survey ends
where it should: with a record someone else can trust.

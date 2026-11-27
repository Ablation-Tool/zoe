# The Restraint Ethic

This is the ethic that makes the method legal and credible. It is not a soft
preference bolted onto the end. It is operational ethics, and it is enforced in
code, not just stated in prose.

The one line to carry: enumerate metadata, do not exfiltrate. The names are the
finding. A payload is sampled minimally and only to confirm severity, never to
collect.

---

## 1. Names are the finding

Before any payload is read, the naming pattern already carries the intelligence.
A collection named like `pingu_btc` is a trading bot. A two-tenant collection
prefix is collapsed multi-tenancy on one store. A field named for minors in a
classifier run is the severity, settled, before a single record is touched. An
artifact path that names a storage bucket attributes the operator.

So the order is fixed: enumerate names and metadata first. The schema, the
collection list, the experiment titles, the field names. That layer answers
"what is this, who runs it, how bad is it" without reading a record.

This is why the work is defensible. The finding exists at the metadata layer.
Reading the contents adds nothing the names did not already prove, and it crosses
from assessment into collection.

---

## 2. Sample payloads minimally, only to confirm severity

When a payload read is genuinely required to confirm severity, it is bounded:

- Two records per collection, where two records settle the question.
- `max_tokens=1` probes against an inference surface, enough to prove the gate is
  open, not enough to draw real output.
- Pull one full record to name a data class, because a field name is not proof.
  A field named for a behavioral or pediatric concept is not "pediatric medical"
  until the record shows it. The severity follows the data, the data follows from
  one minimal, verified read.

The discipline is the floor, not the ceiling. Sample the least that confirms the
claim, then stop. A reference LLM-gateway survey across a large host population
cost on the order of a penny of operator quota in total, because every probe was
bounded by design.

---

## 3. The hard stops

These are lines the method does not cross, ever, regardless of how interesting
the target is:

- **Never read trace bodies.** A request or response payload in an observability
  trace is someone else's data. The trace count and the schema are the finding;
  the body is not.
- **Never issue paid completions.** A `max_tokens=1` probe confirms an open gate.
  A real completion spends the operator's money and produces output that was
  never the point.
- **Never call destructive endpoints.** Model-pull, chat, delete, and any other
  endpoint that changes state or draws cost are off-limits on a live target. The
  presence of the endpoint is the finding.
- **Never point active exploitation at a live operator.** Active LLM exploitation
  runs against controlled and test targets only. Firing it at a real operator
  endpoint crosses the ethical-stop line. The tool still runs, against localhost
  and lab targets, with the survey's own corpus. It is simply never aimed at the
  survey set.

---

## 4. Archive, do not contact, what is out of scope

Not every reachable host is a target. A personal-device exposure and a host that
turns out to belong to a different category than the survey are archived without
outreach. The disposition is recorded so the work is honest about what it saw,
and then the host is left alone. Reachability is not a mandate to engage.

---

## 5. Depth and breadth are independent axes

This is the part that turns restraint from a limitation into a stance.

Every finding carries two separate claims:

- **Depth** is the claim about what the software does. Did you read the source,
  or run the released artifact in a realistic stack and watch the gated action
  happen.
- **Breadth** is the claim about how widely that behavior is exposed. One in-scope
  host, or a measured percentage of a fingerprinted population.

The two vary independently, and the discipline is to never let a move on one
smuggle in a claim on the other. Increasing depth strengthens the claim about the
software. Increasing breadth strengthens the claim about exposure. They are
different claims.

The deliberate position this method takes is high depth, low breadth. Confirm a
behavior is real in the product, while consciously declining to scan the public
internet to count how many people are exposed. On a linear ladder that looks like
an unfinished step. It is not. It is a chosen position:

> This is real in the product, and we are not asserting how many people are
> exposed.

A binary-confirmed finding with zero hosts surveyed is a complete result, not a
gap. The restraint, "we proved it exists and chose not to map who is vulnerable,"
is itself the ethical content of the claim.

---

## 6. The ethic is enforced in code

A stated ethic that lives only in a document erodes the first time it is
inconvenient. This one is wired into the repository so the boundary holds whether
or not anyone is watching.

### The .gitignore boundary

The first line of enforcement is the ignore set. It is not editor cruft hygiene.
It is a redaction boundary that names, by pattern, every class of artifact this
work produces that must never reach a public repo:

- Whole `evidence/` and `recon/` trees, the raw host data and harvest logs.
- Dated survey output directories and any directory named after an IP quad.
- Findings ledgers and harvested host databases, the `*.db` files that hold raw
  records and claim keys.
- Live scan state files, the ones that carry auth headers, tokens, and system
  prompts.
- Machine-readable target lists, the core leak class: `ips*.txt`, `targets*.txt`,
  confirmed-host lists.
- Per-host dossiers and operator-attribution maps.
- Raw scanner and HTTP captures, which carry `Authorization` headers and host
  detail.
- Disclosure-routing files, recipients and drafts, which have no place in a
  public methodology repo at all.

The pattern is the point. The ethic says "names are the finding, do not collect
the bodies." The ignore set is that ethic expressed as `*.db`, `ips*.txt`, and
`evidence/`. The thing you must not exfiltrate is exactly the thing the boundary
refuses to track.

### The CI boundary-audit job

The ignore set is the human half. A file someone force-adds, or a paste into a
markdown doc, slips past it. So the second half is a CI job that fails the build
on any violation. It checks, on every push and pull request:

- No tracked secret, state, or bulk-data artifacts. No `.db`, `state.json`,
  `tokens.json`, ssh keys, `.ndjson`, or gzipped JSON in the tree.
- No tracked machine-readable IP or target lists or per-host dossiers.
- No em dashes anywhere in tracked files, the loudest tell that prose was
  machine-pasted rather than written.
- Only documentation IPs in prose. Every IPv4 literal in tracked markdown or
  shell must be an RFC 5737 documentation address, loopback, or RFC 1918 private.
  Any other public IPv4 fails the build. An illustrative address uses
  `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24`, never a real host.
- No researcher PII. The contact string is the firm domain only. No personal
  name, personal email, or service history.
- No disclosure-routing files.

A green run means exactly one thing, and only that: no raw target data, no PII,
no em dashes, only documentation IPs, no disclosure routing. These are the
structural checks a regex can make. It does not, and cannot, catch a
re-identification fingerprint built from co-located product details, or a hard
survey count that should have been a qualitative range. Those are semantic, and
they are caught by human review, not by the gate. A green build is the floor, not
a clean bill. The restraint ethic, machine-checked where a machine can check it,
on every commit.

```
  the ethic (this file)
        |
        |  "names are the finding, do not exfiltrate the bodies"
        v
  .gitignore boundary  ── refuses to track the bodies (*.db, ips*.txt, evidence/)
        |
        v
  CI boundary-audit    ── fails the build if a body slips in anyway
        |
        v
  public repo          ── no live target data, by design
```

---

## In one line

No live target data lives in this repo, by design. The discipline the repo
teaches is the discipline it practices.

# The NuClide Methodology

A scanner produces candidates. Verification produces findings. The scan is the
easy part, and the easy part is where the lies get in. Point a tool at cloud
ranges and it collects exposed AI services in an afternoon. That output is a
list of candidates, not a list of findings. At population scale the verification
steps that get skipped do not fail randomly. They fail systematically. They
produce confident, reproducible, wrong numbers. Most of the codified lessons in
this method are verification-stage failures or the rules that prevent them. That
ratio is the method. Everything below exists to turn a candidate into a finding
you can stand behind.

This document is the spine. It walks the eight numbered stages plus the
active-banner prefilter in order, says what each stage does and why it carries
weight, and points to the deeper docs where a stage earns its own page.

---

## The pipeline at a glance

```
Discover -> Active-Banner -> Fingerprint -> [ VERIFY ] -> Attribute -> Classify -> Ledger -> Score -> Codify
```

VERIFY is the load-bearing stage. Every other stage either feeds it or records
what it confirmed. Every stage writes to the ledger before the next stage
begins, so the work survives a crash, a context reset, or a six-month gap. The
full diagram with the data-flow notes is in
[diagrams/pipeline.txt](diagrams/pipeline.txt).

This is a research program, not a scan. There is a falsifiable thesis behind it,
and every survey either strengthens the evidence base or tries to break it. A
negative result is as publishable as a positive one. The thesis, the
auth-on-default argument, and why negative results matter are in
[THESIS.md](THESIS.md).

---

## Stage -1 / 0. Platform-Intel and Discover

**What it does.** Before a single dork is written, parallel research lanes build
the intelligence that tunes everything downstream. Each lane produces one part
of the picture: a ranked dork set with an FP-risk note per query, a
single-endpoint verification primitive that is definitive on its own, a
population estimate, a high-value endpoint map with a severity per endpoint, and
a fingerprint spec for any platform the catalog does not yet cover. This is
intelligence at input. The ceiling of every later stage is set here.

Then discover three ways and take the delta:

- **Name-first.** Brand dorks for known platform signatures. Fast, with a hard
  ceiling: it only finds products that emit a indexable string. A product whose
  brand string lives in a meta tag an SPA never renders to the indexer returns
  near zero on every brand dork. That zero is a gap in the channel, not an
  absence of the platform.
- **Provider-first.** Sweep the tier-2 cloud ranges on the platform-class port
  set, then fingerprint by API shape. The provider is the anchor, not the
  product name. Port selection follows operator intent (what would an operator
  running this platform co-deploy) rather than IANA rank. Port-first beats
  brand-dork for low-footprint platforms.
- **CT-log via Censys.** Certificate Transparency logs are pushed from the CAs,
  so a cert is captured the moment it is issued, before any crawler can reach
  the host. This surfaces a third population the name-first crawler misses:
  rate-limiting hosts, banner-dark ports, and cert-issued staging endpoints.

**Why it is load-bearing.** A single-engine negative is not a host-level
negative until the cross-engine delta is read. One channel going dark tells you
that channel is dark, nothing more. The decisive product of this stage is the
delta between the three populations. Run all three on every survey and take the
union; never skip a channel because another one returned data. The full set of
discovery patterns, including the channel-coverage rule and the recurring moves,
is in [DISCOVERY-MOVES.md](DISCOVERY-MOVES.md).

## Active-Banner prefilter

**What it does.** A standing, non-skippable active TCP/TLS banner grab on every
harvested IP after every passive harvest. It does four jobs at once. It confirms
liveness, and only about a third of cache answers are live, so two of every
three candidates are stale before fingerprinting starts. It grabs the fresh
version string for CVE scoping. It strips dork false-positives at the banner
layer. And it surfaces shadow ports the curated scan never looked at.

**Why it is load-bearing.** It hands the fingerprint stage a clean live subset
instead of raw candidates. Skip it and the fingerprinter spends its budget on
dead hosts and inherits the dork's false-positive rate wholesale. The one line
to keep straight: a banner confirms liveness and version, but it does not
confirm schema or vector-use. Banner is a prefilter, not the fingerprint. The
schema question belongs to the next two stages.

## Stage 1. Fingerprint

**What it does.** Answers one question and only one: what service is on this
port. The matcher pre-filters its catalog to fingerprints whose default ports
include the open port, then requires every condition in a probe to pass.
Conjunctive matching is enforced in the control flow, not left to convention. An
anti-match clause excludes marketing-page reflections, so a product name printed
on a landing page does not get counted as the product running.

**Why it is load-bearing.** A single-word substring match produces systematic
false positives, not occasional ones. A bare keyword matches a filename, a
French chatbot, a substring of an unrelated word in a JS bundle. The fix is a
three-part conjunct: a platform-specific endpoint, a structured response, and an
anchored keyword. After every fingerprint run, a quality monitor attributes
results to per-enumerator lanes and flags any enumerator whose empty-result rate
runs high. An enumerator that returns empty across two or more corpora is a
confirmed path-only false-positive class and earns a signature on the spot. That
monitor pass is not optional. Running the fingerprinter without it leaves
systematic inflation undetected and carries bad counts into the findings.

## Stage 2. VERIFY (the load-bearing stage)

**What it does.** Promotes a candidate to a finding by surviving verification,
and nothing reaches a report without it. Everything from the earlier stages is a
candidate. Each rule here exists because skipping it once produced a published or
near-published falsehood. The naive read is always plausible and always wrong in
a way that tracks the platform's implementation, the indexer's behavior, or the
operator's mental-model gap. It is never noise that averages out.

The core moves:

- **A 200 is platform identity, not auth state.** A 200 to an unauthenticated
  probe confirms the platform is alive at that URL. It does not classify auth
  posture. The fix is to probe the data layer for populated data using the
  platform's documented anonymous response shape. A documented anonymous 200 from
  a correctly-configured tenant is not an unauth finding.
- **Dork hits are not instances (the ~50% rule).** A single-token dork's hit
  population runs about half false positives: forks, reverse proxies passing the
  title through, clones, coincidental matches. Define a mandatory identity
  marker, probe the full corpus rather than a sample, and quote the raw count and
  the confirmed count side by side.
- **Follow the redirects and check auth-state-only tokens.** Auth-bypass hides
  from an entry-point-only fingerprint. Follow the redirect chain and look for
  state that only an authenticated session should carry. Effective-unauth also
  includes open registration and an empty security-schemes object.
- **Traverse the full handshake.** The handshake leaks structure even when
  invocation is gated. An empty top-level listing can still carry the schema in a
  nested capabilities object. Absence of top-level content means look elsewhere,
  not gated.
- **Verify the data class by pulling a full real record.** Confirm what the data
  is by reading one real record, not by matching field names. A field name is a
  guess; a record is evidence.
- **Honeypots self-filter under a protocol-strict probe.** An exact,
  protocol-conformant envelope drops deception-fleet pollution by orders of
  magnitude. Protocol-shape conformance is the primary discriminator.

**Why it is load-bearing.** Most of the codified lessons in this method are
verification-stage failures. Skipped verification fails systematically, not
randomly: it produces confident, reproducible, wrong numbers that look like
findings. The full rule set, the worked examples, and the verification-rung claim
grid (depth versus breadth, code versus live, host versus population) are in
[VERIFICATION.md](VERIFICATION.md).

## Stage 3. Attribute

**What it does.** Turns a bare IP into a named operator. A direct-IP TLS probe
sends no SNI, so the server presents its default cert, which on shared infra is
frequently the customer's own OV or EV cert. From that leaf the method builds
Cert, Service, and Domain nodes, then pivots outward through CT-log SAN
enumeration: one cert, its SAN domains, the CT-log subdomains under them, each
promoted to a new seed. Reverse DNS and passive DNS supplement the cert pivot.

**Why it is load-bearing.** The default cert presented to a no-SNI probe is the
single richest attribution primitive on the public internet, and it is handed
over for free. The discipline that goes with it: platform-class operators are
mono-platform at population scale. An operator running one exposed service is
running one platform, not a diverse fleet. Resolve any apparent cross-platform
operator overlap to PTR before believing it, because a shared subnet is not a
shared operator.

## Stage 4. Classify

**What it does.** Classifies the target (HIPAA, clinical, personal, commercial,
research, honeypot), surfaces ethics flags, and seeds the disclosure channels. It
also scores impossible service combinations on one host as a honeypot tell.

**Why it is load-bearing.** WHOIS is authoritative for routing. OrgName and
OrgAbuseEmail from a WHOIS lookup are primary records. A filename-slug heuristic
is a guess, and a guess mis-routes: a slug string in a generator once sent a
finding to the wrong university. Classification decides how a finding is handled
and who, if anyone, hears about it, so it runs on primary records, never on a
convenience string. The restraint posture that governs what gets collected and
what never gets read is in [RESTRAINT-ETHIC.md](RESTRAINT-ETHIC.md).

## Stage 5. Ledger

**What it does.** Append-only, lifecycle-tracked ingest of every confirmed
finding. The lifecycle runs open, disclosed, acknowledged, remediated, verified,
plus archived. A status update appends a timestamped note; it never overwrites.
Lifecycle history is never destroyed.

**Why it is load-bearing.** The ledger is the record of work, not a terminal
print. Every stage feeds it before the next stage starts, which is what makes the
pipeline resumable: a survey interrupted at any point can be picked up from the
ledger rather than rerun from scratch. The ledger is also a discovery substrate.
Probing IPs already recorded surfaces stacked exposures at low yield, and every
hit is a guaranteed operator catastrophe because it means a second service on a
host already known to be exposed.

## Stage 6. Score, rank, corpus

**What it does.** Three offline, air-gap-capable passes over the confirmed
findings.

- **Compliance scoring** under an OPA/Rego policy where the policy is the
  methodology. Deny rules are critical controls; warn rules are high; the same
  exposure is never counted under two controls; a critical on a government
  target escalates. The score maps to recognized AI risk frameworks.
- **Semantic exploit-module ranking** offline, against a pre-encoded module
  corpus, to settle whether a finding is a commodity-CVE chain or a first-party
  authz bug. The distinction changes the severity and the remediation.
- **Adversarial prompt corpus** for any LLM-adjacent surface.

**Why it is load-bearing.** Encoding the methodology as policy means the score is
auditable and reproducible rather than a reviewer's mood. No double-counting and
the government-escalation rule are written into the policy, not applied by hand.
The whole stage runs offline, which keeps it usable in an air-gapped or ICS lab.
The policy structure and the framework mappings are in [SCORING.md](SCORING.md).

## Stage 7. Codify

**What it does.** Every survey extracts a numbered Insight, the class of mistake
the survey taught, into the methodology. Every platform researched is committed
to the corpus, marked CONFIRMED when a live population was observed and CANDIDATE
when it is doc-grounded but host-unverified. A platform is never promoted from
candidate to confirmed without a 200-with-data. Any new false-positive signature
discovered during the survey is written before the survey closes.

**Why it is load-bearing.** Surveys produce data; insights produce the
methodology that makes the data trustworthy. This is the compounding asset. A
survey that produces a finding but no insight has under-delivered. The
false-positive signature is higher-leverage than the finding it came from,
because the finding is one host and the signature is every future survey. The
corpus rule, CONFIRMED versus CANDIDATE, keeps the platform registry honest: a
name in the corpus with no 200-with-data behind it stays a candidate, and the
distinction is never blurred.

---

## The discipline layer

The eight stages are mechanical. They are not the hard part. The hard part is the
set of rules that keep the pipeline sound, the ones that get re-argued session
after session: the full arsenal runs and nothing is conditional, primary source
over framing at every layer, a zero result means generate variants rather than
stop, the manual-to-productize-to-rerun loop, the IP-direct shadow sweep on every
confirmed host, and distrusting your own observation position. Those rules live
in [DISCIPLINE.md](DISCIPLINE.md), and the standard for what a finished survey
produces is in [OUTPUT-STANDARD.md](OUTPUT-STANDARD.md).

Read the discipline layer before running an assessment. The pipeline tells you
what to do. The discipline layer is why the numbers come out true.

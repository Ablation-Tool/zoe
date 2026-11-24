# NuClide Insights

The numbered insight series is the durable output of this research program. A
scan produces data. An insight produces the methodology that makes the data
trustworthy. We codify one per survey, and we cite them by number, because each
one is a class of mistake we made or caught, generalized into a rule that catches
it the next time. The numbers are stable citation IDs: a given insight keeps its
number for good, so gaps in the sequence are expected, not missing entries.

The series grows one insight at a time. That is the discipline, not a slogan: a
survey that produces a finding but no insight has under-delivered. Most of the
series sits at the verification stage, because the scan is the easy part, and the
easy part is where the lies enter. A scanner points at cloud ranges and collects
exposed AI services in an afternoon. That output is candidates, not findings. At
population scale the verification steps that get skipped fail in systematic, not
random, ways. They produce confident, reproducible, wrong numbers.

Each entry below states three things: the class of mistake, the generalizable
default it ties to, and the verification rule that catches it. The illustrations
use documentation address ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
and example.com. No live target, operator, or victim is named. The lessons are
technique, not target.

Contributions are welcome by pull request. If you have surveyed a platform class
and extracted a generalizable verification lesson, open a PR with the next number
in the series, the same three-part shape, and your own sanitized illustration.

---

## The one rule under all of them

Trust the actor's own record over any framing of it. WHOIS over the filename
slug. The writer function over the post-mutation config. The parsed data layer
over the HTTP status. The marker probe over the dork. Bug reports, intake notes,
slug heuristics, and status codes are framing layers. Source code, WHOIS records,
and parsed response bodies are primary records. Distrust framing by default.

Most of the insights below are one corollary of this rule applied at a different
layer of the stack.

---

## Discovery

### Insight #21 - Port-first discovery beats brand-dork discovery for low-footprint platforms

**Class of mistake.** Quoting a brand dork's near-zero hit count as the platform's
population. A single-page app whose shell carries no indexed brand text, or whose
signature lives in an `/api/*` route the indexer does not crawl, returns almost
nothing to a title or HTML dork. The naive read is "this platform is barely
deployed." The real read is "the indexer cannot see this platform's brand."

**Generalizable default.** A null brand-dork result means the product is unmapped,
not absent. Invert the discovery: harvest by substrate signature, not by brand.

**Verification rule.** Identify the default server signature (the substrate:
`uvicorn` on a port, `gunicorn`, a Gradio shell, a Next.js asset path), harvest
that superset, and let a structure-anchored fingerprint that probes `/api/*`
classify down. In one agent-platform survey the brand dork surfaced a single host;
a `uvicorn`-substrate harvest surfaced a tractable superset that classified down to
a handful of real instances, every one critically unauthenticated. The fingerprint is
reusable; the brand dork was not.

### Insight #69 - A curated scan's negative is not a host-level negative

**Class of mistake.** Concluding a host is clean because an intent-curated scanner
found nothing. An AI-intent port set is selected for the ports an AI operator would
co-deploy. That is the right design for finding AI services fast and the wrong
instrument for asserting a host is uninteresting.

**Generalizable default.** A curated scan returning zero is a signal to widen, not a
host verdict. The product is unmapped on the ports checked, not absent.

**Verification rule.** Run a full-range population read (CT-log and full-port
passive sources) as a standing complement before any "clean host" claim. One edge
host showed a few open ports to the curated scan and a small cluster of services to the
full-range read, including a Kubernetes console, a router service, and a fleet of
sshd on five-digit ports. The value is the delta between telescopes, not the
overlap.

---

## Verification (the load-bearing stage)

### Insight #6 - Single-word substring matching is unsound at population scale

**Class of mistake.** Fingerprinting a platform on one keyword in a response body.
`keyword in body` matches whatever else happens to contain that keyword: a media
filename, a chat bot, a substring of an unrelated word in a JavaScript bundle.

**Generalizable default.** A fingerprint needs three conjuncts, not one. Endpoint
specificity, structural shape, and an anchored keyword, all required together.

**Verification rule.** Require, at minimum: a specific endpoint that the platform
alone serves, a structured response (JSON parse plus a named field, or a specific
HTML title format), and an anchored keyword conjoined with both. One bespoke probe
that matched a single word produced a few false positives and zero true positives
across a large prefix sweep. Add fingerprints to a shared catalog with
this discipline; do not write per-survey single-word probes.

### Insight #15 - Dork hits are not platform instances (the ~50% rule)

**Class of mistake.** Quoting a Shodan dork's hit count as the platform's install
base. A single-token title dork's population runs roughly half false positives:
reverse proxies passing the title through, re-skinned forks, OpenAI-compatible
servers that share an API shape, coincidental string matches.

**Generalizable default.** Any population number derived directly from raw dork hits
is off by roughly two times. The dork is itself a substring match with the same
false-positive class as a naked body match.

**Verification rule.** Define a mandatory identity marker (a unique endpoint, field,
or error string), probe the full corpus rather than a sample (sample bias hides the
rate because top-ranked hits skew clean), and quote both numbers. A large
title sweep confirmed roughly half as real via marker probes. Assume a substantial
false-positive rate on any new platform's dork until proven otherwise.

### Insight #16 - A 200 is platform identity, not auth state

**Class of mistake.** Marking a host "unauthenticated" because an unauthenticated
probe got HTTP 200. A 200 confirms the platform is alive at that URL and chose to
answer. It does not classify the auth posture. Many modern stacks gate at the
resolver, not the HTTP layer, and return 200 with a documented empty or null body
to an unauthenticated caller.

**Generalizable default.** Status code is identity. Auth posture lives in the body.
The two are different claims and the status code answers only the first.

**Verification rule.** Every "200 means unauth" classification needs a data-layer
probe that asks for data and checks the response actually contains populated data.
A 200 with a documented anonymous shape (a null field, an empty array, a
"field required" error) is a "not exposed" signal that looks identical to a
successful read from a status-only classifier. One prober marked dozens of hosts
"HIGH unauth" off a 200; every one was the platform's documented anonymous
response, returned by production tenants operating correctly. Encode the platform's
anonymous shape as a recognizer and treat 200-plus-null as Info, not Critical.

### Insight #8 - Auth-bypass hides from entry-point-only fingerprints

**Class of mistake.** Reporting a host login-gated because `/` returns a 302 that
looks like a login flow. A platform configured with an anonymous-admin public role
serves the real dashboard at a post-redirect path while the login template still
answers at `/`. An entry-point-only probe sees the redirect and calls it protected.

**Generalizable default.** The auth posture lives on the post-redirect target, not
the entry point. "Effective unauth" is broader than literal no-auth: it includes
anonymous-admin roles, open self-registration, and an empty `securitySchemes`.

**Verification rule.** Capture the 302 path without following it, then re-request
the redirect target with cookies cleared and look for authenticated-state-only
tokens. If an authenticated-state token is present without credentials, the host is
in an anonymous-admin state. In one orchestration survey, a meaningful minority of
confirmed hosts were unauthenticated at the post-redirect path despite a `/` that
looked login-gated.

### Insight #11 - Source code is authoritative; bug reports are framing

**Class of mistake.** Crediting or blaming an actor for a config based on the
post-mutation state. A tool that reads-modifies-writes a config file preserves keys
it does not manage. The post-write file is the union of the writer's output and the
preserved input, so the most recent writer gets blamed for a key an earlier
tutorial wrote.

**Generalizable default.** Trace any claim back to the actor's own primary record
before crediting or blaming. The writer function is primary; the post-mutation file
is framing.

**Verification rule.** Grep the writer's source for the field or path in question.
If the writer never references it, the writer is not authoring it; look upstream for
the actual author, usually two or three referrers back. The same discipline applies
to your own prior-session notes: re-run the actual probe before propagating a
cross-session claim. One claim built on a post-mutation config inspection dissolved
when the writer source had zero references to the field it was blamed for.

### Insight #1 - Protocol-strict surveys self-filter honeypots

**Class of mistake.** Counting honeypot responses as real platform instances. A
deception fleet answers a permissive probe shape happily. Scored on banner
heuristics or substring matches, a survey inherits the fleet's pollution wholesale.

**Generalizable default.** The protocol-shape gate is a stronger honeypot filter
than any IP blocklist. A honeypot operator can rotate IP allocations between scans;
it is harder to fake exact protocol conformance.

**Verification rule.** Score a hit only on full protocol-shape conformance: the
exact required envelope, method name, headers, and version negotiation the real
platform demands. Layer an IP-based honeypot list on top as a secondary net, not as
the primary discriminator. The same population that dominated a permissive survey
fell by orders of magnitude under a strict handshake.

---

## Attribution

### Insight #17 - Platform-class operators are mono-platform at population scale

**Class of mistake.** Assuming an operator running one exposed platform runs a
diverse fleet, then over-attributing on an apparent address-range overlap. An
operator who exposes one instance of a platform is, at population scale, running
one platform, not many.

**Generalizable default.** Treat platform populations as independent. An apparent
overlap is a coincidence until resolved to a primary record.

**Verification rule.** Resolve any apparent shared-range overlap to PTR before
believing it. A cross-platform overlap study across several observability platforms
found zero genuine address-level overlaps across a large host set, which is itself
a publishable load-bearing result, not a null.

### Insight #19 - SPA plus headless API is a high-severity exposure tell

**Class of mistake.** Reading a polished CDN-fronted frontend as a hardened posture.
The CDN provides TLS, edge caching, and DDoS protection for the static frontend. The
API that does the actual work lands wherever the developer chose, often a single
cloud VM with no auth wall and the data tier exposed on adjacent ports.

**Generalizable default.** A CDN-hosted single-page app calling a same-brand API
host of the form `api.<brand>.<tld>` is an exposure tell, not a reassurance. The
visible state is professional; the actual posture is often unhardened.

**Verification rule.** Identify the CDN by response headers, pull the largest JS
bundle, grep for absolute `https?://api\.` URLs, resolve the extracted API host, and
probe it directly. If it lands on a different network than the CDN edge, that
resolved host is the soft target. The pattern held across multiple independent
instances in a single short window. Illustrative shape: a frontend on a CDN edge, a
bundle calling `https://api.example.com`, resolving to 203.0.113.10, an unhardened
backend with adjacent data ports open.

---

## Co-deployment and stacking

### Insight #12 - Hostname-routed SSO does not protect the bare-IP shadow

**Class of mistake.** Believing every service is behind SSO because the reverse
proxy enforces it on the configured hostnames. Every service that listens on the
host's IP at any port answers requests by IP and bypasses the hostname-routed
front-end. The operator's mental model is wrong by exactly the count of services
that have no auth of their own.

**Generalizable default.** SSO bound at the reverse-proxy hostname protects only
traffic that arrives via that hostname. The bare IP escapes it. Operators who ship
one service auth-off ship others auth-off, because the same deployment template
ships them all that way.

**Verification rule.** On every confirmed-unauth host, sweep about fifteen adjacent
high-signal ports (metrics exporters, queue UIs, mail catchers, NFS, data-tier
ports) and fingerprint each service, since the port number alone is unreliable. In
one observability sweep, a sizable share of unauthenticated hosts had a second unprotected
surface on the same IP, and a metrics endpoint disclosing the full internal service
topology was the highest-information-density leak. A stacked host (platform-unauth
plus metrics-unauth plus open file shares on one IP) is multiplicatively worse than
any single exposure. Illustration: 192.0.2.20 fronted by SSO at
`platform.example.com`, with the same service reachable unauthenticated at
`http://192.0.2.20:6006/` and a metrics endpoint open on `:9090`.

---

## The thesis and its evidence

### Insight #13 - Shipping defaults are load-bearing

**Class of mistake.** Reading a population's unauthenticated-exposure rate as a story
about operator skill. When two products in the same category have comparable
customers but opposite security defaults, the population-scale outcome follows the
default, not the operators. A single env-var default can produce exposure rates
differing by orders of magnitude across otherwise-comparable platforms.

**Generalizable default.** The shipping default is the deployment template for the
entire population. It propagates through container images, quickstart docs, Helm
charts, third-party tutorials, and backup-and-restore tooling. Changing it by
documentation alone is insufficient, because every downstream copy of the template
still carries the old default.

**Verification rule.** Always sample at least one comparison platform from the same
category. A platform shipping auth-off-by-default ran a large share of its population
unauthenticated; a comparable platform with no such toggle ran effectively none, and its
population included sophisticated enterprise and government operators. The same
operators, the same skill, opposite defaults, opposite outcomes. When an entire
category shows the same failure pattern, audit the vendor's shipping default first.
The signal-to-noise ratio of "audit the default" is far higher than "audit each
operator."

### Insight #40 - Auth-on-default strengthens across successor generations under disclosure pressure

**Class of mistake.** Assuming a known finding shape persists into a project's next
generation. When a disclosure lands against an open-source infrastructure project,
the successor release tends to harden the specific surface that drove it. The
architectural pattern persists; the externally observable finding shape does not.

**Generalizable default.** The auth-on-default thesis does not just hold at a point
in time. It strengthens over successor generations within a project family under
disclosure pressure. A negative result on a successor is publishable evidence that
disclosure works in that ecosystem.

**Verification rule.** Survey the successor rather than assuming. One predecessor
exposed pooled-account metrics on a public endpoint; the Go-rewrite successor moved
the metrics behind auth, returned a bare health status, and gated the admin surface,
and a sweep of a large successor population found none of the predecessor's leak
class. New finding shapes emerged as the old one closed (an open setup wizard at
a low single-digit rate), which is the pattern, not an exception.

---

## Restraint and disclosure

### Insight #68 - State every finding as a depth-by-breadth pair

**Class of mistake.** Letting a move on one axis smuggle in a claim on the other.
"I could docker-compose this in principle" is not the same as having run the real
binary. "This host is fingerprinted as the vulnerable version" is not the same as
having fired the request at it.

**Generalizable default.** Every finding carries a verification status as a pair. An
inner rung for depth (logic reproduction from source versus the real released
artifact run in a realistic stack) and an outer rung for breadth (no live host,
one in-scope host, or a population). The two axes vary independently.

**Verification rule.** Name both rungs in the finding and let each license only its
own language. "Surface open by code reading, access not exercised" is inner-A. "Field-
confirmed against the released binary in a local stack" is inner-B. "X% of
fingerprinted deployments exhibited this" is outer-2. Increasing depth strengthens
the claim about what the software does; increasing breadth strengthens the claim
about how widely it is exposed. Never let one stand in for the other.

### The restraint ethic - enumerate, do not exfiltrate

**Class of mistake.** Reading payloads to establish a finding. Before any payload is
read, the naming pattern already carries the intelligence: a collection prefix that
collapses multi-tenancy, an artifact path that attributes an operator, an experiment
name that classifies the workload. Reading the data to confirm what the name already
told you adds risk and subtracts nothing.

**Generalizable default.** Names are the finding. Enumerate metadata first. Sample
payloads only to confirm severity, and minimally.

**Verification rule.** Pull schema and metadata, classify sensitivity from field
names rather than record contents, and cap any confirmatory read at the smallest
sample that establishes severity (two records per collection, single-token probes).
Confirm the data class by pulling one full structured record before naming it, since
a field-name pattern alone can mislead. Never read trace bodies, never issue paid
completions, never call destructive endpoints. A blocked read is "surface open,
access not exercised," not a failure to follow through.

### Insight #4 - WHOIS is authoritative for attribution routing

**Class of mistake.** Deriving an organization from a filename slug or a
human-friendly label. Two distinct institutions can share a slug overlap by
coincidence, and a slug-string heuristic will route to the wrong one.

**Generalizable default.** The registry's `OrgName` and abuse contact are the
authoritative input for any recipient derivation. Filename-friendly identifiers are
labels for your own filing, never institution mappings.

**Verification rule.** Pull `whois <ip>` and read the registered org and abuse fields
first; treat your own slugs as never-authoritative. When the address block resolves
to a parent or shared-services org, that is the network owner's record and it wins
over any name your pipeline guessed. One batch's only misroute came from a slug
heuristic that WHOIS would have caught on the first pass.

### Insight #5 - A verbatim fix remediates an order of magnitude faster

**Class of mistake.** Describing a vulnerability without shipping the fix. A vague
advisory ("this service is exposed, please secure it") sees remediation on the order
of weeks, if at all. The friction between reading the advisory and shipping the fix
is the variable that governs time-to-remediate.

**Generalizable default.** The remediation block is the highest-leverage paragraph in
any advisory, not boilerplate. A finding that ships with the fix closes far faster
than one that only names the problem.

**Verification rule.** Every advisory carries three things: a specific copy-pasteable
fix (bind to loopback, set this env var, add this firewall rule), the exact
verification command run from outside the network, and a short re-probe contract.
Advisories carrying a verbatim fix and a verification command remediated an order of
magnitude faster than descriptive-only ones, with several confirmed fixed within
hours.

---

## How to read the series

Three things recur, and they are the whole method in miniature:

- **Primary source over framing.** Most insights are this rule at a new layer. The
  parsed body over the status code (#16). The marker over the dork (#15). The writer
  source over the post-mutation config (#11). WHOIS over the slug (#4).
- **A null result is a logged result.** A zero-hit dork, a zero-overlap attribution,
  a zero-leak successor survey. Each is a finding, not a dead end. Absence of a
  finding is not absence of risk, and a negative result is as publishable as a
  positive one.
- **Codify every survey.** The data is perishable. The insight compounds. Each
  number above made every survey after it more trustworthy, which is why we cite by
  number: the citation is proof the lesson was paid for once and never again.

Contributions by pull request. Add the next number, keep the three-part shape, and
sanitize hard: documentation address ranges only, example.com only, no operator or
victim named. The lesson has to generalize without a victim, or it is not yet an
insight.

Contact: nuclide-research.com

# Verification: The Load-Bearing Stage

The scan is the easy part. The easy part is where the lies enter.

A scanner points at cloud ranges and collects exposed AI services in an
afternoon. That output is candidates, not findings. The work that separates a
trustworthy survey from a confident-and-wrong one happens after the scan, in the
stage that gets skipped because the scan already produced a number that looks
done.

This is the argument for not skipping it.

---

## The central claim

Skipped verification does not fail randomly. It fails systematically.

A sloppy scan that misses hosts at random produces noise that averages out. You
can publish a fuzzy number and be roughly right. That is not what happens here.
A skipped verification step fails in the same direction on every host that
shares a property, so the error tracks the platform's implementation, the
indexer's behavior, or the operator's mental model, never a coin flip. The
result is a confident, reproducible, wrong number. Re-run the broken pipeline
and you get the same wrong number again, which feels like confirmation and is
not.

Concretely: a classifier that reads HTTP status only will mark every host
running a given GraphQL platform as "unauthenticated," because that platform's
documented anonymous response is a 200. Not some of them. All of them. The
"unauth rate" for that platform converges to 100 percent and stays there across
re-runs. The number is stable, defensible-looking, and false for every host.

That is why most of the program's codified insights are verification-stage
failures, not discovery-stage ones. The ratio is not an accident. It is the shape
of the problem. Discovery has a few ways to go wrong. Verification has many, and
each one fails a whole subpopulation at once.

---

## A 200 is identity, not auth state

The single most expensive mistake in this class: reading a status code as an
auth decision.

When a platform endpoint returns HTTP 200 to an unauthenticated probe, that
response confirms one thing. The platform is alive at that URL, it accepts
requests, and it chose to answer. That is platform identity. It says nothing
about whether the data behind the endpoint is reachable.

The naive classifier is a status-code lookup:

```
200 -> unauth     (caller got the data, nothing stopped them)
401 -> protected  (caller got rejected at the auth layer)
403 -> protected  (caller got rejected at access control)
404 -> not-platform
5xx -> server-error
```

This works only for platforms where the HTTP layer enforces the auth gate. It
fails for every platform where the resolver enforces the gate and returns 200
with a documented empty shape. Most modern GraphQL servers work this way.

The case that named the rule: a Weights and Biases prober probed `/graphql`
with a `viewer` query, saw HTTP 200 on several dozen confirmed self-hosts, and
labeled every one "HIGH unauthenticated, anonymous mode enabled by default."
Thirty minutes of follow-up dropped all of them to Info. The response body was
`{"data":{"viewer":null}}`, which is W&B's documented "you are not
authenticated" answer. The auth gate lives at the resolver, not the status
line. Every one was a real production tenant operating exactly as designed.

```
  unauth probe -> /graphql { viewer { id } }

  HTTP 200  {"data":{"viewer":null}}      <- documented anonymous response
            |                                  IDENTITY confirmed, auth UNKNOWN
            |
  HTTP 200  {"data":{"viewer":{"id":...}}} <- populated, real credential bypass
                                               AUTH STATE = open
```

Same status code. Same endpoint. Opposite finding. Only the body tells them
apart. The rule that falls out:

> Every "200 to unauth" classification carries a data-layer assertion, or it is
> not a classification. It is a guess wearing a status code.

---

## The data-layer probe and the documented anonymous shape

The fix is cheap. Issue a probe that asks for data, then check that the
response actually contains data. Empty arrays, null values, and "field
required" errors are all "not exposed" signals that look identical to a
status-only reader.

The discipline has three moves:

1. Identity probe. Confirm the platform via a platform-specific endpoint. A 200
   with the documented shape means the platform is present. Nothing more.
2. Data-layer probe. Issue a query that asks for records, then verify the
   response is populated. A real run, a real trace, a real experiment list.
3. Reference-implementation check. Read the platform's source or docs to learn
   the documented anonymous-access response shape, then encode that shape as a
   recognizer. The platform tells you what "not authenticated" looks like.
   Believe the platform.

The third move carries the weight. You do not have to guess what an empty answer
looks like. The vendor documents it. MLflow's empty experiment search returns
`{"experiments":[],"next_page_token":""}` with a 200. Encode that as
"anonymous," and a populated `experiments` array becomes the only thing that
earns the Open label.

| Probe outcome | Severity | Auth state |
|---|---|---|
| 200 + populated data | Critical | Open |
| 200 + null/empty documented shape | Info | InfoOnly |
| 401 / 403 | Info | Protected |
| non-platform response | None | Unknown |

The escalation to Critical requires positive evidence that the data layer is
reachable. Absent that evidence, the honest label is Info, not High. The
difference between those two labels is the difference between a finding and a
falsehood.

---

## Dork hits are not instances: the 50 percent rule

The same failure shows up one layer earlier, at the search engine.

The number of hits a Shodan dork returns is not the number of platform
instances. Across the surveys, a single-token title dork's hit population runs
roughly half false positives: re-skinned forks, reverse proxies passing the
title through, OpenAI-compatible servers that share an API shape, coincidental
string matches.

The anchor: a full sweep on a single-token API-platform title dork returned
several thousand hosts. Marker probes confirmed only about half as genuine
instances. The rest matched the dork and failed every platform-specific marker.
Any population number read straight off the raw dork count is off by roughly two
times.

```
  raw dork hits  ->  marker probe  ->  ~half confirmed
                                       ~half not the platform (forks, proxies,
                                              OpenAI-shape lookalikes)
```

The sample-bias trap is what makes this survive review. Researchers sample the
top-ranked hits, which skew toward clean production deployments, see "most are
real," and generalize. A 25-host sample shows one or two false positives and
feels like noise. At any sample above ~200 hosts the false-positive rate
converges to about half. The bias is structural, not careless.

The rule:

- Define a mandatory identity marker. A platform-specific endpoint, field, or
  error string no other platform serves.
- Probe the full corpus, not a sample. Sample bias hides the FP rate.
- Quote both numbers. Raw dork hits and confirmed instances. The delta is the
  methodology disclosure, not a footnote.

"N exposed instances" read off the raw hit count is the wrong sentence. "X dork
hits, Y confirmed, Z critical unauthenticated," with X, Y, and Z each from a
verified probe, is the right one. The first overstates the actionable population.
The second is the finding.

The 50 percent figure is a heuristic anchor, not a constant. Specific platforms
run higher or lower depending on marker specificity. Assume at least 25 percent
false positives on any new platform's dork until a marker proves otherwise. That
conservative default sits closer to ground truth than the implicit "hit count
equals install base" that most public exposure tracking ships with.

---

## Where the auth bypass hides

A fingerprint that reads only the entry point misses the bypass that lives one
redirect away.

Follow `/` to `/home` redirects. Check authenticated-state-only tokens on the
post-redirect target, not on the entry point. A login-flow-looking 302 at `/`
hides an admin console reachable at `/home` when the platform ships
`AUTH_ROLE_PUBLIC=Admin`. The entry point looks gated. The application is open
to anyone who follows the redirect the browser would have followed.

"Effective unauth" is broader than a literal missing auth header:

- `AUTH_ROLE_PUBLIC=Admin` (anonymous callers land in the admin role)
- `signUpDisabled:false` (anyone registers, then has the full authenticated API)
- OpenAPI `securitySchemes:{}` (the spec itself declares no auth)

None of these return 401 at the front door. All of them are open. An entry-point
fingerprint that stops at the first response sees a locked door and walks away
from an unlocked building.

---

## Nested handshakes leak structure even when invocation is gated

When a protocol negotiates before it serves, the negotiation leaks.

A gated endpoint can return an empty `tools/list` and still hand you the schema
through the `initialize` response's `capabilities` object. The top-level content
is empty. The nested handshake field is not. Absence of top-level content means
"look elsewhere in the envelope," not "gated, give up."

The discipline: fully traverse every nested field of every handshake response.
The `capabilities`, the `serverInfo`, the negotiated feature flags. Invocation
being blocked does not mean structure is hidden. Two different layers, two
different gates, and the structure layer is frequently open while the invocation
layer is closed.

```
  initialize  ->  { capabilities: { tools: { schema: <leaked here> } } }
  tools/list  ->  { tools: [] }   <- gated, looks like nothing is here
```

Read the whole envelope. The finding is rarely where the empty array told you
to stop.

---

## Verify the data class by a full record, not a field name

Naming a data class from a field name is pattern-matching, and pattern-matching
on field names is how a survey libels an operator.

`beh_ped` is not "pediatric medical data." A field-name token matcher will tag
it that way, and the tag becomes a sentence in a disclosure that says the
operator is exposing children's health records. To verify a data class, pull a
full real record. A real MLflow run. A real Langfuse trace. Read enough of the
actual record to confirm what it is, then name it. Not the column header. The
record.

This is the one place the restraint ethic and the verification rigor point the
same way and pull against each other at the edge. You pull one full record to
confirm the class, and you stop there. Enough to be right about the severity,
not one byte past it.

---

## Honeypots self-filter under a protocol-strict probe

A permissive probe counts deception fleets as findings. A strict probe makes
them disappear.

Deception fleets answer loosely. They emulate many services badly and respond
to almost anything that looks like a request, because their job is to look open.
A protocol-strict probe, an exact handshake envelope that a real implementation
would accept and a faked one would mishandle, filters them out for free.

The pattern: an exact JSON-RPC `initialize` envelope dropped one hosted honeypot
fleet's pollution from the overwhelming majority of a permissive survey to a
near-negligible share of the strict one. The honeypots did not change. The probe
did. Protocol-shape conformance is the primary discriminator. IP blocklists are a
secondary net for the fleets a strict probe still lets through.

The lesson runs the other way too. If a survey's "finding" rate is suspiciously
high, suspect the probe before you celebrate the yield. A suspiciously high hit
rate is more likely a honeypot fleet answering a sloppy probe than a genuine
epidemic of exposure.

---

## The verification-rung grid

Every finding carries a verification status expressed as a pair, not a single
ladder rung. Depth and breadth vary independently, and conflating them is how a
claim about software smuggles in a claim about the internet.

Inner rungs, depth, code versus live:

| Inner | What was done | Language it licenses |
|---|---|---|
| A, logic reproduction | Source and config review, optionally a stripped harness modeling the code path | "surface open by code reading, access not exercised." Avoid "exploitable." |
| B, binary reproduction | The real released artifact run in a realistic lab stack with documented defaults, the actual request sent, the gated action observed | "locally exploitable in default config," "field-confirmed against the released binary" |

Outer rungs, breadth, host versus population:

| Outer | What was done | Language it licenses |
|---|---|---|
| 0, no live host | Nothing pointed at any real deployment | "no live host tested yet" |
| 1, in-scope host | The behavior observed on at least one host meeting inclusion criteria | "observed on an in-scope host" |
| 2, population | Fingerprint plus sampling plus dedup show it across a measurable population | "X% of fingerprinted deployments exhibited this at inner rung A or B" |

The load-bearing line is inner A to inner B: code versus live. A logic
reproduction validates the transcription and catches reasoning errors. It does
not exercise the real binary, the middleware chain, or the config-load path. "I
could docker-compose this in principle" is inner A. The container must exist and
the request must have run for inner B.

The axes couple in one direction only. Reaching outer-1 by exercising the
request inherently demonstrates inner-B for that host. So inner-A / outer-1 is a
real and distinct state: this in-scope host is fingerprinted as running the
vulnerable version, and we deliberately did not fire the request at it.

### Restraint is a position on the grid, not an unfinished step

NuClide works high-depth, low-breadth by choice. We establish that a behavior is
real in the product, inner A or B, while consciously declining to map it across
the public internet, outer 0. On a linear ladder that looks like a step left
undone. On the grid it is a chosen position: this is real in the product, and we
are not asserting how many people are exposed.

```
              outer 0          outer 1            outer 2
              no host          one host           population
  inner A   code read,       fingerprinted,     "code-level true,
  logic     not fired        request withheld    not mapped"
  inner B   binary           request fired       population survey,
  binary    confirmed        at live host        rate published
```

Increasing depth strengthens the claim about what the software does. Increasing
breadth strengthens the claim about how widely that behavior is exposed. They
are different claims. The discipline is to never let a move on one axis smuggle
a claim on the other.

> Restraint ethic: it is acceptable, and sometimes required, to deepen
> validation while intentionally not expanding observation scope. A high-depth,
> low-breadth state, binary-confirmed with no hosts surveyed, is an explicit
> choice, not a gap.

---

## "Surface open, access not exercised"

When access is blocked, the honest label is not "could not confirm" and it is
not "probably exploitable." It is "surface open, access not exercised."

The phrase is precise. It states what was observed, the surface is reachable and
answers, and what was not done, the gated action was not driven to completion.
It refuses both the false negative ("nothing here") and the false positive
("confirmed critical"). It is the inner-A / outer-1 cell of the grid written as
a sentence: the host is fingerprinted as carrying the exposure, and we chose not
to fire the request that would prove impact.

Use it. A blocked probe is not a failed finding. It is a finding at a known
verification rung, stated honestly. The reader can act on "surface open, access
not exercised" because it tells them exactly what is and is not known. They
cannot act on "exploitable" when the request never ran, because that word
promises a proof that does not exist.

---

## Why this is the differentiator

Anyone can run a scanner. The scanner is commodity. What it produces is a list
of candidates and a number that looks finished.

The number is the trap. It is finished-looking and systematically wrong, and the
specific way it is wrong is invisible until someone does the data-layer probe,
the marker check, the full-record pull, the redirect follow, the strict
handshake. Each of those is one cheap step. Each one, skipped, fails an entire
subpopulation in the same direction and produces a confident, reproducible,
publishable falsehood.

Verification is not perfectionism bolted onto the end of a scan. It is the stage
that decides whether the survey is true. The scan finds the candidates.
Verification is the part that earns the word "finding," and earning that word,
host by host, marker by marker, is the whole program.

---

## See also

- [METHODOLOGY.md](METHODOLOGY.md) for the eight-stage spine this stage sits
  inside (diagram at [diagrams/pipeline.txt](diagrams/pipeline.txt))
- The numbered insights in the methodology corpus, each sourced to the case
  study that taught the lesson, are the canonical reference vocabulary. Verify
  every tier label against them, cite them by number.
- Contact and coordination: nuclide-research.com

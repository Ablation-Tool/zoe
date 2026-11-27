# Discovery Moves

A numbered playbook of the recurring moves. These are distinct from the thesis
and distinct from the pipeline stages. They are the patterns that show up across
case study after case study, the things you reach for when a standard sweep
stalls or a population number looks too clean.

Each move is written the same way: the situation that calls for it, the move
itself, why it works, and one sanitized illustration. Illustrations use
documentation address ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
and example.com domains. The platform names are public open-source projects, not
targets.

---

## 1. Cross-engine population delta

**Situation.** You ran one discovery engine, got a host list, and you are about
to treat its negatives as the truth. A single engine's "not present" is not a
host-level negative.

**The move.** Run a second engine that sources its population differently, then
take the delta. A pull-based crawler schedules a fixed port list and skips hosts
that rate-limit it. A Certificate-Transparency-fed engine ingests certs from the
issuing authorities the moment they are signed, and sweeps the whole port space.
Merge both populations before fingerprinting. Never skip the second engine
because the first looked complete.

**Why it works.** The two engines miss in opposite directions. The crawler
misses cert-issued-but-not-yet-crawled hosts, rate-limiters, and quiet ports.
The CT-fed engine misses nothing that ever got a cert but cannot see un-TLS'd
services. The delta is the population neither engine alone reports, and it is
often where the interesting exposure lives.

**Illustration.** A curated scan saw a handful of services on an edge host at
192.0.2.40. The full-port engine saw several times that many on the same host,
including a cluster console on a five-digit port, a gateway admin on a
non-standard port, and several SSH daemons on DNAT'd five-digit ports. The
curated negative was not a host negative. Reading the second engine turned one
host into a topology.

---

## 2. Port-first discovery for brand-dark platforms

**Situation.** Every brand dork for a platform returns near zero, but you have
reason to believe the platform is deployed in the wild. The product is unmapped,
not absent.

**The move.** Stop hunting the brand string. Anchor on the provider and the
port. Sweep the tier-2 cloud ranges on the platform-class port set, then
fingerprint by API shape rather than by indexed title. The provider is the
anchor, not the product name.

**Why it works.** A brand dork only finds a product that emits an
indexer-visible string. Some single-page apps render their brand only into a
meta tag that the crawler never executes, so the indexed title is silent while
the running service is fully exposed. Port-plus-shape ignores the missing string
entirely and matches the thing the service actually does on the wire.

**Illustration.** A platform's brand dorks all returned roughly zero. A
port-first sweep on the platform-class port, filtered by the server banner the
framework ships, surfaced a several-thousand-host superset. The fingerprint
stage classified that down to a small set of genuine instances, all critically
unauthenticated, that no brand dork would ever have found.

---

## 3. Cert-pivot via the no-SNI default cert

**Situation.** You have a bare IP and no name for the operator behind it. The
finding is real but unattributed.

**The move.** Send a direct-IP TLS probe with no SNI. The server answers with
its default certificate, which on shared and vendor infrastructure is frequently
the customer's own organization-validated cert. Read the leaf, take its
subject and SAN domains, and you have turned an anonymous address into a named
operator.

**Why it works.** Without an SNI hint, the server cannot select a per-hostname
cert and falls back to whatever default it was configured with. Operators
commonly bind their real cert as the default, so the cert that answers a
nameless probe carries the operator's identity for free, with no record reads
and no payload.

**Illustration.** A no-SNI probe to 198.51.100.12 returned a leaf whose
subject was `ops.example.org`. That single name attributed a host that rDNS had
left blank. Note the inverse case: an HTTP-only admin port presents no cert, so
this pivot fails there and you fall back to passive DNS instead.

---

## 4. CT-log SAN promotion

**Situation.** A cert-pivot gave you one leaf and its SAN list. You want the
operator's full footprint, not just the one host that answered.

**The move.** Take each SAN domain off the leaf and enumerate it in the
Certificate-Transparency logs. Every subdomain the CT logs ever recorded for
that domain becomes a new seed. Promote each discovered subdomain to a fresh
probe target and repeat. One cert becomes its SANs, becomes the CT-log
subdomains under those SANs, becomes the operator's whole infrastructure.

**Why it works.** CT logs are an append-only public record of every cert a CA
issued. An operator who got a wildcard or a multi-SAN cert published their own
subdomain inventory into that record at issuance time. You are reading their
naming convention back out of the logs they could not avoid writing to.

**Illustration.** A leaf for `app.example.com` carried SANs for
`example.com` and `api.example.com`. CT enumeration of `example.com`
promoted `staging.example.com`, `metrics.example.com`, and
`internal-tools.example.com` to seeds. The bare IP became the operator's
staging and metrics tier, all from one nameless TLS handshake and one CT query.

---

## 5. The active-banner prefilter

**Situation.** You have a raw candidate list straight off a passive engine and
you are tempted to hand it to the fingerprint stage as-is. Most of it is stale.

**The move.** Stand an active TCP and TLS banner grab in front of fingerprinting
on every passive harvest, no exceptions. The banner stage confirms liveness,
grabs the fresh version for CVE scoping, strips dork false positives at the
banner layer, and surfaces shadow ports. It hands the fingerprinter a clean live
subset instead of raw candidates.

**Why it works.** Passive-engine caches run heavily stale at population scale.
A large fraction of harvested addresses no longer answer, and counting them as
live inflates every downstream number. A live full handshake also returns the
current version, not the cached one, which is what CVE scoping actually needs.
The banner is fast and cheap, hundreds of full handshakes per second on one box.
One caveat: a banner is not a schema. It confirms the service is alive and which
version, but it cannot confirm vector use or data exposure. That stays the deep
enumerator's job.

**Illustration.** A harvest of candidate addresses dropped to roughly a quarter
live on the active banner pass. The rest were stale cache. Fingerprinting the
full raw list would have reported a population several times the real one, off by
the exact stale fraction, confidently and reproducibly wrong.

---

## 6. The identity-marker re-probe

**Situation.** A dork returned a clean-looking population and you are about to
publish its count. A dork hit is not a platform instance.

**The move.** Define one mandatory identity marker the real platform always
emits and the impostors do not. Re-probe the entire corpus for that marker, not
a sample. Quote two numbers: the raw dork count and the marker-confirmed count.
Where a 200 looks like the answer, follow it with a data-layer probe that checks
for populated data, because a 200 is identity, not auth state.

**Why it works.** A single-token title dork pulls forks, reverse proxies passing
the title through, clones, and coincidental matches alongside the real thing.
The false-positive share runs near half. The marker probe is the only thing that
separates the real population from the look-alikes, and sampling instead of
probing the full corpus reintroduces exactly the error you were trying to
remove.

**Illustration.** A title dork for one API platform returned several thousand
hosts. The mandatory marker probe confirmed only about half as genuine instances,
so the raw count was off by roughly a factor of two. A separate prober once
marked dozens of hosts "high unauth" off a bare 200, when the body it got back
was the platform's documented anonymous response and every one was a correctly
operating tenant. The data-layer probe, not the status code, is what earns the
label.

---

## 7. Stacked-exposure re-probe of the ledger

**Situation.** The discovery engine is down, or you want to find the worst
hosts rather than the most hosts. Fresh discovery is not the only source of
targets.

**The move.** Treat the findings ledger as a discovery substrate. Re-probe the
addresses already recorded from prior surveys, sweeping adjacent high-signal
ports on each one. The hit rate is low, but every hit is a host where one
operator left two or more things exposed, which is precisely the population you
most want to surface.

**Why it works.** Operators who shipped one service auth-off tend to ship others
auth-off. A host already in the ledger has self-selected as that kind of
operator. Sweeping its neighbors for data-tier and metrics ports turns a single
prior finding into a stacked one, and the metrics port in particular tends to
disclose the entire internal service topology in one read.

**Illustration.** Re-probing a previously recorded host at 203.0.113.30 across
its adjacent ports found a second unauthenticated service and a metrics endpoint
whose targets list named every internal service the operator ran. The ledger
re-probe yields under one percent, but that one percent is guaranteed operator
catastrophe, not marginal exposure. A four-platform stack on one operator was
first found exactly this way.

---

## How the moves compose

The moves are not alternatives. They chain.

```
  discover ─┬─ cross-engine delta (1) ── catches the engine's blind spot
            └─ port-first (2) ──────────── catches the brand-dark platform
                     │
                     v
  prefilter ── active-banner (5) ───────── strips stale, grabs version
                     │
                     v
   verify ─── identity-marker re-probe (6) ─ strips the look-alikes
                     │
                     v
  attribute ─┬─ no-SNI cert-pivot (3) ───── bare IP becomes a leaf
             └─ CT-log SAN promotion (4) ── leaf becomes the footprint
                     │
                     v
  recur ───── ledger re-probe (7) ───────── prior findings become new seeds
```

A typical chain: port-first discovery (2) surfaces a brand-dark population, the
active-banner prefilter (5) strips it to the live subset and grabs versions, the
identity-marker re-probe (6) confirms which are genuine, the no-SNI cert-pivot
(3) and CT-log SAN promotion (4) attribute the confirmed hosts to named
operators, and the survivors land in the ledger where the stacked-exposure
re-probe (7) will find them again on the next survey. A zero at any single step
is a signal to vary the signature, not a conclusion. The product is unmapped
until the variant space is exhausted.

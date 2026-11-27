---
title: "Worked example: ScyllaDB open on CQL, schema read, contents left alone"
type: example
lane: restraint-ethic / metadata-not-exfiltration
platform: scylladb
tags: [scylladb, cassandra-cql, database, unauth, restraint-ethic, schema-only]
---

# ScyllaDB Open on CQL: Schema Read, Contents Left Alone

> Lane: restraint ethic / metadata-not-exfiltration. This example exists to teach
> one discipline by demonstration. The schema is the finding. The records are not
> read. The hard stop lands at the table names, and that is a complete result, not
> an unfinished one.

A single illustrative target stands in for the live host: `192.0.2.10`, a
ScyllaDB cluster (Cassandra-derived) reachable on the CQL native protocol (9042),
the REST management API (10000), and the Prometheus metrics endpoint (9180). This
is a genericized teaching example. Every host-specific identifier has been
removed, and the schema below is described at the level of data classes rather
than verbatim names, because the verbatim inventory of a single cluster is itself
a re-identifying fingerprint. What stays is the part that teaches the method, and
that part survives genericization intact, because the finding never lived in the
contents and never depended on the exact names.

---

## The thesis it confirms

Auth-on-default at the database layer. Cassandra-derived systems, ScyllaDB
included, ship with `AllowAllAuthenticator` as the default. An operator who
deploys to bare cloud compute with no network firewall gets an internet-reachable
cluster with full unauthenticated read and write. The version banner read off the
REST API showed an end-of-life release, which says the cluster had not been
touched in a long time. No one was minding the gate, because the gate was never
closed.

---

## Stage 1: The gate is open (access surface, verified)

The CQL native protocol speaks a binary frame format. The probe is a single
`OPTIONS` frame followed by a `STARTUP` frame. A server that requires
authentication answers `STARTUP` with an `AUTHENTICATE` challenge. A server
running the default authenticator answers with `READY`.

```
client  ->  OPTIONS
server  ->  SUPPORTED   (CQL_VERSION advertised, Scylla shard-aware extensions)
client  ->  STARTUP
server  ->  READY       <- no AUTHENTICATE challenge
```

`READY` with no `AUTHENTICATE` is the whole access-surface finding. The server
accepted an anonymous client and moved straight to ready-for-queries. Any CQL
client that reaches this port has full read and write to every table in the
cluster. That is `AllowAllAuthenticator`, the default, confirmed at the wire.

This is a verified read, not a status guess. The distinction matters here exactly
as it matters everywhere in the method: the open gate is proven by the protocol
handshake itself, not inferred from a port being open or a banner being present.

**Tier: access surface verified. Data content not read.**

---

## Stage 2: The schema is the finding

With the gate open, the next move is to enumerate names, and only names. The REST
API answers an unauthenticated `GET` for the keyspace list and the per-keyspace
table list. That call returns metadata: which keyspaces exist, which tables sit
under each. It returns no rows.

The enumeration came back with a clear shape: multiple non-system keyspaces and
many application tables across them. The naming pattern, read at the level of data
classes, settles what this cluster holds before a single record is touched. Stated
as classes rather than verbatim names:

| Data domain | Class of table present | What the class already proves |
|---|---|---|
| Payments | A stored-card-data table | Cardholder data is reachable |
| Auth / identity | Key-material tables, live session tokens, and a one-time-pass table | Encryption keys, active sessions, and an OTP auth factor are reachable |
| Regulated records | A multi-tenant business keyspace, including KYC identity documents | Regulated KYC data is reachable |

These are data classes, not the cluster's verbatim table list. The full inventory
of one host is itself a re-identifying fingerprint, so it is not reproduced here.
The point survives the abstraction: the cluster was built deliberately and then
left open. Someone stood it up on purpose. They just never closed the gate.

Read the schema on its own terms. The stored-card-data table is cardholder data.
The session-token table is live session tokens. The KYC table is regulated
identity documents. None of that required reading a row. The class of each table
carried it. That is the lesson in one example: the schema is the finding.

**Tier: schema enumeration confirmed. Data not read.**

---

## The hard stop, and why it lands exactly here

This is the load-bearing line of the example. The probe stops at the table names.

The temptation at this point is obvious. The gate is open, the schema is mapped,
and a single `SELECT` would turn "a stored-card-data table exists" into "this many
card records, here is one." The method declines that move, on purpose, every time.

The reasoning is not timidity. It is that the read adds nothing the schema did not
already prove, and it crosses a line the schema did not. Severity was already
settled at the schema layer:

- The presence of a stored-card-data table proves cardholder data is reachable. A
  `SELECT` confirming a row count does not raise the severity. It only converts
  an assessment into a collection of someone else's cardholder data.
- The presence of session-token and OTP tables proves session tokens and OTP
  seeds are reachable. Reading one is the difference between observing an exposure
  and holding the keys to an account.

So the stop is placed where the marginal information from a read goes to zero and
the marginal harm from a read goes positive. That point is the schema. Before it,
every probe is metadata enumeration and defensible. After it, every probe is data
collection and is not.

Depth and breadth, the two independent axes, make the position precise. The depth
claim here is strong: the gate is open and the data classes are named, confirmed
at the wire and at the schema. The breadth claim is deliberately left at one
illustrative host. The result reads:

> This cluster is open and holds payment, identity, and KYC data, confirmed by
> schema. We did not read a record, and we are not asserting how many other
> clusters look like this.

That is a complete finding. The restraint, "we proved what it holds and chose not
to read it," is the ethical content of the claim, not a gap in it.

---

## What metadata-not-exfiltration looks like as a rule set

The same discipline, stated as the lines this example did not cross:

- **No `SELECT` on a live target.** The schema settles the data class. A row read
  collects it. The presence of the table is the finding.
- **No write, ever.** `AllowAllAuthenticator` grants write as well as read. The
  open write surface is reported as a fact, never exercised.
- **No destructive or state-changing call.** The REST API exposed `repair`,
  `compaction`, and `snapshot` unauthenticated. Their reachability is the finding.
  None were called.
- **No paid or output-drawing action.** Nothing on this surface costs the operator
  money, but the rule is general: confirm the gate, do not draw the output.
- **Sample only to name a data class, and only if names are genuinely ambiguous.**
  Here the names were not ambiguous, so the sample count is zero. When a field
  name is truly unclear, the bound is one record, read once, to settle the class,
  then stop.

---

## The class of mistake this avoids

A scanner that stopped at "port 9042 open" would have logged a candidate and moved
on, missing that the gate was actually open. A scanner that ran `SELECT *` to
"confirm" would have crossed into collecting cardholder data to prove a point the
schema already proved. The method threads between the two: handshake the protocol
to verify the gate is genuinely open, enumerate the schema to settle severity, and
stop before the contents. Verified, defensible, and complete, all at once.

★ Takeaways
- The schema is the finding. `READY` with no `AUTHENTICATE` plus a stored-card-data
  table settles "open and holds card data" without one row read.
- The hard stop is placed where a read's marginal information hits zero and its
  marginal harm goes positive. For a database that point is the table names.
- A high-depth, low-breadth result is complete. "We proved what it holds and chose
  not to read it" is the ethical content, not a missing step.

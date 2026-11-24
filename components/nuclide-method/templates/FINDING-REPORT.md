---
platform: "<service / software name, e.g. vector-db, model-server, mlflow>"
verification:
  inner: A   # A = logic / source reading. B = released artifact exercised in a realistic stack.
  outer: 0   # 0 = no live host. 1 = one in-scope host. 2 = population (fingerprint + sampling + dedup).
tier: candidate   # Verified / Surface-open / Candidate  (access state; see CONTRIBUTING.md)
status: open   # open / confirmed / remediated / withdrawn
severity: ""   # CRITICAL / HIGH / MEDIUM / LOW, only after hard proof at the stated rung
---

# <Finding title, short, single-clause headline>

Use this for any single finding before it reaches population scale. State
exactly what was done and exactly what was not, so the claim never outruns the
evidence. The verification tier is a pair (inner A/B, outer 0/1/2) and is never
auto-upgraded. Reaching a higher rung requires exercising the named remaining
steps, not asserting them.

## Verification rungs (the claim grid)

| Inner | What was actually done | Language it licenses | Forbidden above this |
|---|---|---|---|
| A, logic reproduction | Verbatim source / config review, optionally a harness modeling the code path | "surface open by code reading, access not exercised" | "vulnerable", "exploitable", "auth bypass" |
| B, artifact reproduction | Released artifact run in a realistic stack with documented defaults, request sent, gated action observed | "locally exploitable in default config", "field-confirmed against the released artifact" | "exploitable in the field", a population rate |

| Outer | What was actually done | Language it licenses | Forbidden above this |
|---|---|---|---|
| 0, no live host | Nothing pointed at a real deployment | "no live host tested yet" | "observed in the wild" |
| 1, in-scope host | Behavior observed for at least one host meeting inclusion criteria | "observed on an in-scope host" | a frequency or rate |
| 2, population | Fingerprint + sampling + dedup across a measurable population | "X% of fingerprinted deployments exhibited this at inner A/B" | extrapolation beyond the probed set |

Discovery-signal rule: rank fingerprints by discriminating power, not
convenience. Protocol and domain-specific features (OpenAPI info.title, semantic
routes, vendor response headers) are claim-promotable. Weak signals (a shared
port, a generic banner, a single substring) are candidate-only.

---

## What

<The precise condition. The configuration or code state that produces the issue.
What endpoint, what service, what response. One paragraph. Only what was
directly observed, cited to the exact status code, JSON key, or body string.>

**Evidence:** <verbatim code snippet and / or config default. Cite the source
path. For live reads, endpoint + HTTP status + the data field that proved it. No
full credentials, key prefix only, sample payloads minimally to confirm
severity, never to exfiltrate. Illustrative addresses use 192.0.2.0/24,
198.51.100.0/24, or 203.0.113.0/24 and domains use example.com.>

## Why it matters

<Impact scoped to the confirmed rung. State it at code level if inner-A.
Distinguish what the probe directly verified from what would be reachable via
chain steps not exercised. Translate to business loss: data class at risk, exec
surface, claimable admin state, downstream data subjects. Verify the data class
from a full record before naming it, never from a schema guess.>

## Chain context

<How this finding connects to others. Low + medium + misconfiguration can equal
an unmapped critical path. State the class of mistake this finding belongs to.
Tie to the relevant numbered Insight. Name the preconditions and scope limits so
the claim is not an overclaim.>

## Remediation (copy-paste-grade)

<The fix, real-world and minimal. Lead with the one-line change, then the config
block the operator pastes in.>

```yaml
# example: bind to loopback and require a token
# adjust keys to the actual platform
listen_addr: 127.0.0.1
auth:
  required: true
  token_env: SERVICE_API_TOKEN
```

<Then one sentence on how the operator confirms the fix took.>

## References

<CVE IDs, vendor docs, prior NuClide insight files by number, upstream issue
links. Primary source over framing: cite the source or the spec, not a bug
report about it.>

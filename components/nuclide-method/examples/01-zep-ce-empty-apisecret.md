---
type: worked-example
platform: Zep Community Edition
verification: inner-A / outer-0
status: surface open by code reading, access not exercised
---

# Zep CE: empty default api_secret accepts a zero-entropy credential

## What this example teaches

Three discipline lanes, on one small finding:

- **Code-only.** The whole finding comes from reading the project source. No
  network probe is part of the proof.
- **Read the source, do not touch the target.** The vulnerable behavior is
  established against the published code, not against any running deployment.
- **Verify before claiming.** The example refuses to call the issue
  "exploitable." It carries an explicit inner-A / outer-0 label, "surface open,
  access not exercised," and lists exactly what is missing to move up.

A scanner produces a candidate. Source reading produces a confirmed control
flow. Neither one produces "exploitable." This example shows where the line
sits and why holding it is the point.

---

## Condition

Zep Community Edition ships its config with `api_secret` empty, and the
secret-key middleware validates the credential with a direct string equality
check and no "secret must be non-empty" invariant at config load.

Empty default plus empty token plus string equality means the empty string is a
valid credential out of the box. The finding is that pairing, not "auth is
broken."

---

## Evidence

Source: the project's secret-key auth middleware for Community Edition,
confirmed verbatim. Control flow:

```go
parts := strings.Split(authHeader, " ")
if len(parts) != 2 { /* 401 */ }
prefix, tokenString := parts[0], parts[1]
if prefix != apiKeyAuthorizationPrefix { /* 401, prefix == "Api-Key" */ }
if tokenString != config.ApiSecret() { /* 401 */ }
// allow
```

Config default: the shipped config sets `api_secret:` empty, so
`config.ApiSecret()` returns `""`. There is no startup guard rejecting an empty
secret.

Source-level trace for `Authorization: Api-Key ` (one trailing space):

- `authHeader == "Api-Key "`
- `parts == []string{"Api-Key", ""}` (len 2, passes the format gate)
- `prefix == "Api-Key"` (passes the prefix gate)
- `tokenString == ""`, and `"" == config.ApiSecret()` is `"" == ""` is true
- request is allowed

Precondition detail that only source reading reveals: the trailing space is
load-bearing. `strings.Split("Api-Key", " ")` yields `["Api-Key"]` (len 1,
which 401s at the format gate). The empty second element requires the space.
A probe built without reading the code would likely send `Api-Key` with no
trailing space, get a 401, and conclude the gate holds. The source tells you
the one byte that flips the result.

---

## Impact (code level, inner A)

At the code level the authorization check accepts a zero-entropy token (the
empty string) when the operator never set a secret. There is no length or
format constraint on the token beyond being present as the second
space-delimited part, and no additional guard. The middleware gates the data
API, which on a populated instance serves session message history, summaries,
and extracted user facts (PII-dense conversational memory).

---

## The inner-A logic-reproduction harness

The proof here is a model of the code, not the code itself. To check that the
trace above is right and not a misreading, reproduce the branch logic in a
standalone harness and confirm both the allow case and the trailing-space
precondition.

```go
package main

import (
    "fmt"
    "strings"
)

const apiKeyAuthorizationPrefix = "Api-Key"

// apiSecret models config.ApiSecret() with the shipped empty default.
func apiSecret() string { return "" }

// allowed reproduces the middleware's accept/reject branch logic.
func allowed(authHeader string) bool {
    parts := strings.Split(authHeader, " ")
    if len(parts) != 2 {
        return false
    }
    prefix, tokenString := parts[0], parts[1]
    if prefix != apiKeyAuthorizationPrefix {
        return false
    }
    if tokenString != apiSecret() {
        return false
    }
    return true
}

func main() {
    cases := []string{
        "Api-Key ", // trailing space: parts == ["Api-Key", ""], empty token
        "Api-Key",  // no space: parts == ["Api-Key"], len 1
        "Api-Key x",// non-empty token vs empty secret
        "Bearer ",  // wrong prefix
    }
    for _, c := range cases {
        fmt.Printf("%-12q -> allowed=%v\n", c, allowed(c))
    }
}
```

Expected output:

```
"Api-Key "   -> allowed=true
"Api-Key"    -> allowed=false
"Api-Key x"  -> allowed=false
"Bearer "    -> allowed=false
```

The first line is the finding. The second line is the trailing-space
precondition made concrete. The harness is a logic reproduction, not an
exercise of the real binary, which is exactly why it earns inner A and not
inner B.

---

## Verification status: inner A / outer 0

Labeled per the depth-by-breadth grid. Inner A is logic reproduction
(code-confirmed, not exercised). Outer 0 is no live host tested.

- **Have:** verbatim source-confirmed control flow, the config default, and an
  inner-A logic reproduction cross-checking the branch behavior and the
  trailing-space precondition.
- **Have not:** run a Zep CE container with the default config, sent a real
  `Authorization: Api-Key ` request, or observed an authenticated action
  succeed. The logic reproduction is a model of the code, not the code.
- **To reach inner B** (binary / stack reproduction): start a local CE instance
  with the shipped empty `api_secret`, send the empty-token request, and observe
  a material gated action succeed (a data-API read returning data). That raises
  depth only. Breadth stays at outer 0.
- **To raise breadth** (outer 1, an in-scope host; outer 2, a population): point
  the survey at real CE deployments. Held at outer 0 by choice here. Restraint
  ethic: deepen validation without expanding observation scope. No claim of
  "exploitable" until inner B, and no rate until outer 2.

"Surface open, access not exercised." That is the honest label for this state,
and it is the one the example ships with.

---

## Preconditions / scope limits

Applies only when the operator never set `api_secret`, the out-of-box state.
Any non-empty secret makes the empty token fail closed at the equality check.
The finding is "empty-default plus empty-token," not "auth is broken."

---

## Remediation

For the operator: set a non-empty `api_secret` in the config (or the equivalent
auth-secret environment variable).

For the project: reject an empty secret at config load, or use a constant-time
compare that treats an empty configured secret as "deny all." Either one closes
the empty-default path without touching the wire protocol.

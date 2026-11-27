---
type: worked-example
platform: Ollama (model server)
lane: unauth-model-server class / CVE-anchored finding
verification: class lesson (no live-target data)
status: vulnerability class, no operator catalog
---

# Ollama: unauthenticated /api/create poisons a model's system prompt

## What this example teaches

This is a vulnerability-class lesson, not a survey writeup. It carries the
class, the CVE backbone, and the one-line fix. No target catalog survives the
port. The point is the shape of the exposure and why it scales, not who was
running it.

The lane: an unauthenticated model server, reachable on its API port, where a
single write request rewrites a model's behavior. CVE-anchored: the primitive
maps to a filed CVE whose scope was understated.

---

## Condition

Ollama serves its HTTP API on port 11434 with no authentication on any
endpoint. Two defaults put it on the public internet:

- A Docker publish of `-p 11434:11434` binds the API to `0.0.0.0`, every
  interface, not just loopback.
- `OLLAMA_HOST` defaults to listening on all interfaces when set to expose the
  server beyond localhost.

Once the port is reachable, the write endpoints are open. There is no token, no
key, no allowlist in front of them by default.

---

## The primitive: /api/create system-prompt poisoning

`POST /api/create` lets a caller define or redefine a model. The caller can set
a `SYSTEM` directive, the model's system prompt. Pointed at a model name that is
already loaded, the request replaces that model's system prompt with
attacker-controlled text.

Properties that make it cheap and durable:

- One HTTP request. No authentication.
- Roughly half a kilobyte written. The request reuses the existing model blobs,
  so it consumes no model-download bandwidth.
- Persistent. The redefinition survives client reconnects until an operator
  notices and rebuilds the model.

After the write, every inference call against that model name runs the
attacker's instructions. The reasoning layer is now controlled by whoever
reached the port.

Illustrative request shape (documentation host, not a live target):

```
POST http://192.0.2.10:11434/api/create
Content-Type: application/json

{
  "model": "assistant",
  "from": "assistant",
  "system": "ATTACKER-CONTROLLED INSTRUCTIONS"
}
```

The matching read side is `POST /api/show`, which returns a model's current
system prompt. That endpoint is also unauthenticated, so an attacker can read
the existing prompt before overwriting it, and read back the result to confirm
the write.

---

## CVE backbone

The injection primitive maps to CVE-2025-63389, filed against Ollama. Two
details matter for scoping:

- The advisory scoped the issue to a version ceiling, but the unauthenticated
  `/api/create` and `/api/show` behavior is present across the version range,
  not only at or below that ceiling. The scope was understated.
- The advisory carries no fixed version. There is no release that ships
  authentication on these endpoints by default. The fix lives in operator
  configuration, not in a patch.

Treat the CVE as the anchor for the class, and treat the scope field as a claim
to test, not a boundary to trust. A version above the stated ceiling is not
evidence the endpoint is closed.

---

## Why it scales past one operator

The base primitive compromises one model on one host. Common deployment
patterns turn that into organization-scale impact:

- A model shared across many users means one write affects every user.
- A retrieval pipeline means a poisoned system prompt surfaces through search
  results, not just direct chat.
- An autonomous agent reading its instructions from a poisoned model hands the
  attacker every action the agent takes.
- A cloud-proxy model behind the server means a write can redirect paid quota.

None of these require a second vulnerability. They are the same one-request
write landing in a higher-blast-radius position.

---

## Verification status

Class lesson. The primitive is established from the endpoint contract and the
CVE. This file does not assert any live finding and ships no host list.

- **Have:** the endpoint behavior, the default bindings that expose it, and the
  CVE anchor with its scope caveat.
- **Have not, by design here:** any operator catalog, any live host, any
  exercised write. Moving from "endpoint open" to "write confirmed on a host"
  is a per-target step that belongs in a scoped engagement, not in a public
  class note.

"Surface open, access not exercised" is the honest label for the class write-up.
A real finding against a real host earns its own depth-and-breadth label.

---

## Remediation

For the operator, two paths, either one closes the exposure:

- Bind to localhost. Set `OLLAMA_HOST=127.0.0.1` and, under Docker, publish to
  loopback (`-p 127.0.0.1:11434:11434`) so the API never reaches `0.0.0.0`.
- Front it with auth. Put a reverse proxy with authentication in front of port
  11434 and do not expose the raw port to the network.

The root cause is an unauthenticated write endpoint reachable from the public
internet. Remove the reachability or add the authentication. Do not rely on a
version bump, because no version ships the fix.

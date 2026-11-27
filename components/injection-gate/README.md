# injection-gate

A deterministic **proposal -> gate -> execute** enforcement layer that bounds the
blast radius of (indirect) prompt injection in tool-using agents.

The gate sits synchronously between the model proposing an action and the action
running. Every decision is computed from data provenance, capability, target,
and a policy context. **The gate never calls a model.** The thing injection
compromises is model judgment, so model judgment is not load-bearing in the
defense.

> Defense-in-depth, not a silver bullet. It stacks provenance/taint +
> least-privilege capabilities + a deterministic policy gate + provenance-aware
> egress control. None alone closes prompt injection; together they make a
> successful injection far less able to *do* anything.

---

## The principle

Treat the model as untrusted. The model only ever *proposes* an action; the
**system decides** whether it runs. This is the opposite of a monitor. A monitor
records that something happened, by which time a one-shot injection (read a
secret, send it out) has already completed inside a single action. The gate
blocks *before* the side effect.

---

## What's in the box

```
injection_gate/
  provenance.py   Trust / TaintTag / TaintSet / Tainted   labeling layer
  action.py       Capability / ActionRequest              a proposed action, pre-execution
  policy.py       PolicyEngine + the deterministic rules   the gate's brain
  enforcer.py     Enforcer / ActionBlocked                 runs, blocks, or escalates
  net.py          host parsing + SSRF/internal classify    hostile-input-hard egress parsing
  credentials.py  credential-shape detection               catches secret exfil to allowed hosts
  ledger.py       TaintLedger                              cross-step taint persistence
  baseline.py     HostBaseline                             first-seen-host tripwire
  adapters.py     GatingAdapter / ExampleToolAdapter       the one integration seam
  tools.py        GatedTools (+ Filesystem/HttpTransport)  the WIRED stack: taint at ingestion
  escalation.py   HumanApproval / SandboxedRecheck / ...   real held-action handlers
  camel.py        PrivilegedPlanner / quarantine / ...     CaMeL-style control/data split
examples/
  block_exfil.py     teaching walk-through (hand-tagged taint)
  hardened_agent.py  the wired stack vs 6 concrete attacks, end-to-end
tests/
  test_policy.py       rule-level tests over the defaults
  test_adversarial.py  the bypasses the gate must withstand
```

The three architectural layers, in order of leverage:

1. **Provenance / taint** (`provenance.py` + `ledger.py`). The system knows where
   data came from; you never ask the model. `tools.GatedTools` tags bytes at the
   ingestion seam (a read is untrusted unless it is under a declared trusted
   root; a fetch result is always untrusted), and the `TaintLedger` makes taint
   persist across steps so write-to-sandbox-then-read-back cannot launder it.
2. **Least-privilege capabilities** (`CapabilityGrant`). Each task gets a narrow,
   explicit scope: read roots, write roots, an egress allowlist, exec/delete off
   by default. This bounds what an injection could do at all.
3. **The gate, with egress as the crown jewel** (`policy.py` + `net.py`). The
   highest-value rule, `egress_untrusted_sink`, denies tainted data heading to a
   sink that itself came out of untrusted content. That "data and destination
   both originate in the poisoned input" pattern is the EchoLeak / zero-click
   exfiltration shape, deterministically detectable without understanding intent.

## Quick start

```bash
pip install -e ".[dev]"        # or: PYTHONPATH=. ...
python examples/block_exfil.py        # teaching example
python examples/hardened_agent.py     # the wired stack vs real attacks
pytest                                # 176 tests, all deterministic
```

## The rule set (all deterministic)

A network action is judged network if it is wired `NETWORK` **or** its target
carries a network scheme, so a fetch tool a developer mislabeled `READ`, or a
`gopher://` smuggled through a non-network tool, still meets every egress rule.

| rule                     | fires on                                                          | verdict |
| ------------------------ | ---------------------------------------------------------------- | ------- |
| `internal_egress`        | NETWORK to loopback / RFC1918 / link-local / cloud-metadata (incl. decimal/hex/octal/short-form `127.1`/IPv4-mapped-IPv6 obfuscation, unicode full-stop homoglyph `127.0.0.1。`) / userinfo-spoofed / control-char-spliced / unparseable target | DENY |
| `scheme_guard`           | NETWORK with a non-http(s) scheme (`file:`, `gopher:`, `dict:`, `ftp:`, and exotic `nfs:`/`git:`/`scp:`/`ssh:`, all open-by-default network-bound) | DENY |
| `egress_untrusted_sink`  | NETWORK + tainted data + sink lifted from untrusted content      | DENY |
| `credential_egress`      | NETWORK whose target/args contain a credential shape (AWS key, private key, JWT, long hex blob, ...), including a secret split across fields (adjacent or interleaved with prose) or nested arbitrarily deep | DENY (named) / ESCALATE (opaque) |
| `egress_redirect_param`  | NETWORK with a redirect-class query OR fragment OR path-matrix param (`?next=`, `?redirect_to=`, `?RelayState=`, `#next=`, `;next=`, ... + the framework redirect-name family) pointing off-allowlist / at an internal host / carrying a non-http(s) scheme (defeats backslash + multi-encoded forms) | DENY |
| `egress_allowlist`       | NETWORK to a non-allowlisted host                                | DENY if tainted, else ESCALATE |
| `dns_exfil`              | NETWORK with a high-entropy / over-long subdomain label          | ESCALATE |
| `egress_tainted_payload` | NETWORK + tainted data riding out in a query / body / header / cookie / arbitrary arg / fragment, even to an allowlisted host | ESCALATE |
| `tainted_egress`         | NETWORK + tainted data, even a bare GET to an allowlisted host (opt-in) | ESCALATE |
| `first_seen_host`        | NETWORK to a host not in the persisted baseline (opt-in)         | ESCALATE |
| `malformed_target`       | READ/WRITE/DELETE/EXEC with an unparseable target (embedded NUL / non-string) | DENY |
| `write_sandbox`          | WRITE outside the task's write roots                             | DENY |
| `sensitive_write`        | WRITE into a secret-class path                                   | DENY |
| `sensitive_delete`       | DELETE of a secret-class path (a credentials store, an allowlist/policy file) | DENY |
| `sensitive_name`         | READ/WRITE/DELETE of a path whose name marks it a secret (`.env`, `id_rsa`, `*.pem`, `credentials.json`, `.pgpass.bak` + backup/editor suffixes, ...) | DENY (write/delete, or tainted read) / ESCALATE (read) |
| `write_special`          | WRITE onto an existing symlink / special (non-regular) file      | DENY |
| `read_special`           | READ of a non-regular file (FIFO / device / socket)             | ESCALATE |
| `hardlink_alias`         | READ/WRITE/DELETE of a multiply-linked (hardlink) target that may alias a file outside the sandbox | DENY (write/delete) / ESCALATE (read) |
| `write_tainted_external` | WRITE of tainted data into a write root that syncs off-box (opt-in via `external_write_roots`) | ESCALATE |
| `untrusted_fs_target`    | WRITE/DELETE whose path was chosen by untrusted content          | ESCALATE |
| `delete_guard`           | DELETE not permitted / outside write roots                       | DENY |
| `exec_guard`             | EXEC not permitted for the task                                  | DENY |
| `sensitive_read`         | READ of a secret-class path (DENY if the read is tainted-derived) | ESCALATE / DENY |
| `read_scope`             | READ outside read roots, or any read when unscoped + fail-closed | ESCALATE |
| `allow_inscope_*`        | clearly-in-scope read / write / clean allowlisted egress         | ALLOW |

Severity: `DENY > ESCALATE > ALLOW`; the engine returns the most severe verdict
that fires. The `allow_inscope_*` rules let a fail-closed engine (default
ESCALATE) still pass legitimate in-scope work, so only the genuinely
unanticipated gets held.

### What each control closes

- **SSRF / metadata theft.** `internal_egress` denies the 169.254.169.254 class
  outright. A bare allowlist only *escalates* untainted off-allowlist egress, so
  a permissive operator could wave through a metadata read; this denies it. The
  host parser canonicalizes the obfuscated forms too (decimal `2130706433`, hex
  `0x7f000001`, octal `017700000001`, mixed `0177.0.0.01`, IPv4-mapped IPv6
  `::ffff:127.0.0.1`, and the `inet_aton` short forms `127.1` / `127.0.1` /
  `0x7f.1`), so a laundered internal IP cannot dodge the check.
- **Protocol smuggling.** `scheme_guard` denies any non-http(s) scheme on a
  network action, killing `gopher://` to a local Redis, `file:///etc/passwd`,
  `dict://`, and friends regardless of the allowlist.
- **Redirect SSRF / open-redirect.** `egress_redirect_param` reads the follow-on
  URL hidden in `?next=` / `?url=` and classifies *its* host, denies it when the
  embedded value carries a non-http(s) scheme, and normalizes the value first
  (backslash `\\evil`, multi-layer percent-encoding) so an obfuscated redirect
  target cannot slip past the parse. The transport also refuses to follow a
  cross-host 3xx, so an allowlisted host cannot bounce egress to evil.example or
  the metadata IP.
- **Allowlist-parser evasion.** `net.host_allowed` defeats userinfo spoofs
  (`https://api.good.com@evil.example`), trailing-dot FQDNs, case games, IDN /
  punycode homographs, and implicit-subdomain assumptions. Subdomains are opt-in
  via a leading-dot allowlist entry (`.good.com`).
- **Exfil to an allowlisted host.** `credential_egress`, `dns_exfil`, and
  `egress_tainted_payload` fire regardless of the allowlist, catching a secret
  smuggled to your own API, data ridden out in a subdomain label, or tainted page
  text posted in a body / query, which every taint-only rule misses (config-loaded
  secrets are "trusted" data). `egress_tainted_payload` checks every outbound
  channel, not just the body: query, fragment, headers, cookies, and any
  arbitrary argument value, so taint riding a custom header or `#fragment` is
  still held. `credential_egress` also flags a bare long hex blob (an encoded
  key) and routes opaque shapes to ESCALATE rather than a hard DENY.
- **Taint laundering.** The `TaintLedger` persists taint onto a written resource
  and re-attaches it on read-back, and `GatedTools.write_file` re-derives taint
  from the untrusted corpus even when a caller drops the `Tainted` wrapper and
  writes a bare string, so the write-then-read-back path stays tainted. The
  corpus match is transform-resilient: it normalizes away inserted separators and
  reverses url / hex / base64 / base32 / base85 / Ascii85 / rot-N / reversal / HTML-
  entity encodings before comparing, so chunk-splitting a payload or re-encoding it
  does not strip the taint on write or on egress.
- **Secret-file access by name.** `sensitive_name` holds reads of `.env`,
  `id_rsa`, `id_ed25519`, `*.pem`, `credentials.json`, `.pgpass`, `.netrc`, and
  the like even when the operator forgot to list them, denies a write/delete onto
  such a path, and strips backup / editor suffixes first (`.env.bak`,
  `id_rsa.old`, `secrets.json~`) so a renamed copy is still caught.
- **Filesystem TOCTOU.** The backend opens with `O_NOFOLLOW`, `write_special`
  rejects a symlink / special-file target, and the confined backend descends to
  the target one component at a time with `openat` + `O_NOFOLLOW` beneath the
  validated root, so neither the final path nor an *intermediate* directory
  symlink swapped in between the gate's check and the syscall can redirect the
  write out of the sandbox (0 escapes measured over 4000 concurrent race
  attempts). `hardlink_alias` denies a write/delete onto a multiply-linked file
  that could alias a target outside the sandbox through a hardlink.
- **Fail-closed on malformed input.** `malformed_target` returns a deterministic
  DENY on an unparseable target (embedded NUL, non-string) instead of letting a
  raw `ValueError` escape the gate, and the secret-name / scope checks treat any
  path that fails to normalize as a match (no silent pass-through).
- **CWD drift.** `CapabilityGrant` resolves its read / write roots to absolute
  real paths at construction, so a relative scope root stays pinned even if the
  process later changes working directory.
- **Drift from hand-tagging.** `GatedTools` taints at ingestion and computes
  `target_from_untrusted` by checking whether the proposed sink appeared in the
  untrusted content it has handled. No hand-tagging to drift.

## Hardened deployment

```python
from injection_gate import hardened_engine, harden, PolicyContext, Enforcer
from injection_gate.escalation import HumanApproval, SandboxedRecheck, CapabilityScoped, chain_all

ctx = harden(PolicyContext(grant=grant, sensitive_paths=[...]))   # fail-closed flags on
engine = hardened_engine()                                        # default = ESCALATE
enforcer = Enforcer(
    engine, ctx,
    on_escalate=chain_all(                                        # held actions must clear all of:
        SandboxedRecheck(hardened_engine(), ctx),                #   a stricter re-check, then
        CapabilityScoped(),                                      #   auto-deny DELETE/EXEC/NETWORK, then
        HumanApproval(),                                         #   a human
    ),
)
```

`harden(ctx)` turns on: tainted-egress hold, fail-closed unscoped reads, and DENY
for opaque credential shapes. `hardened_engine()` flips the default verdict to
ESCALATE so anything no rule anticipated is held, not allowed.

## Non-negotiables (read before extending)

- **Never make a model the gate.** A second LLM judging "does this action match
  the task" reintroduces the exact vulnerability; the judge can be injected too.
  `declared_task` is a soft signal for logging/triage only, never a verdict input.
- **Fail closed in production.** Use `hardened_engine()` and `harden(ctx)`. Keep
  the default escalation handler blocking until a real approval path exists.
- **Taint at ingestion, not by hand.** Use `GatedTools` (or have your own fetch
  tools return `provenance.Tainted`). Hand-tagging drifts and leaves gaps.
- **The gate bounds blast radius; it does not stop the model being fooled.** It
  is one layer. Combine with the others, and with human approval for genuinely
  consequential / irreversible actions.

## Status of the build tasks

The scaffold's "Tasks for Claude Code" are implemented:

1. **Wire the seam.** `tools.GatedTools` routes real file/network dispatch
   through the gate, mapping each tool to a capability and a target. Done.
2. **Taint at ingestion.** `GatedTools` returns `Tainted` from every read/fetch,
   persists taint across steps via `TaintLedger`, and computes
   `target_from_untrusted` automatically. Done.
3. **Real escalation path.** `escalation.py`: `HumanApproval`, `SandboxedRecheck`,
   `CapabilityScoped`, plus `chain_all` / `first_of` combinators. Done.
4. **Hardened posture.** `hardened_engine()` + `harden(ctx)`; rules for SSRF
   (incl. obfuscated-IP canonicalization down to `inet_aton` short forms), scheme
   smuggling, redirect SSRF (non-http scheme + backslash / multi-encode), malformed
   targets, credential shapes, DNS exfil, tainted-payload egress across every
   outbound channel, sensitive writes/reads, secret-by-name access (with
   backup-suffix stripping), symlink/TOCTOU writes, hardlink aliasing,
   untrusted-chosen FS targets, and first-seen hosts. The filesystem backend opens
   with `O_NOFOLLOW`, descends confined paths with `openat` per component beneath a
   frozen root, and the HTTP transport refuses cross-host redirects. Done.
5. **Adversarial tests.** `tests/test_adversarial.py` (176 cases) covers host-parse
   evasion, SSRF including obfuscated / short-form IPs and redirect parameters in
   query / fragment / path-matrix slots, scheme smuggling, credential exfil to
   allowlisted hosts including split-across-fields (adjacent and prose-interleaved)
   and arbitrarily-deep-nested secrets, DNS smuggling, tainted-payload egress across
   header / cookie / fragment / arbitrary-arg channels, secret-by-name access and
   backup suffixes, symlink TOCTOU including intermediate-component swaps, hardlink
   aliasing, copy-through and chunk / hex / base64 / base32 / Ascii85 taint
   laundering, malformed-target fail-closed, CWD-drift root freezing, multi-step
   laundering, and CaMeL containment. Done.
6. **Control/data separation (stretch).** `camel.py`: a privileged planner that
   only sees trusted instructions sets capability + target, while a quarantined
   worker's output is always inert data that cannot redirect a step. Done.

## Prior art worth standing on

- **CaMeL** "Defeating Prompt Injections by Design" (Google DeepMind):
  privileged-planner + quarantined-LLM with capabilities. The closest thing to a
  by-design fix.
- The **dual-LLM** pattern it generalizes.
- **OWASP LLM01** (Prompt Injection) mitigations; **MITRE ATLAS**
  `AML.T0051.001` (indirect prompt injection).
- NVIDIA's position paper on **system-level defenses against indirect prompt
  injection**.

## License

MIT.

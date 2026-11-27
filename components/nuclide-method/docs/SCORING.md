# The Scoring Layer

A finding is not a score. Verification earns the finding; scoring turns a set of
verified findings into a number a defender can act on and a number a framework
reviewer recognizes. This layer sits at the end of the pipeline, after Verify and
after Classify, and it is built so that the score is reproducible, auditable, and
leaks nothing about the targets it ran against.

Three pieces:

1. **Compliance scoring** - the policy is the methodology, written as OPA/Rego.
2. **Framework mapping** - each control mapped to recognized AI risk frameworks.
3. **Module ranking and adversarial corpus** - semantic separation of a commodity
   CVE chain from a first-party authz bug, and a prompt corpus that tests the
   LLM-adjacent surface itself.

Everything here runs offline. No score requires a network call, an API key, or a
hosted model. That is a design constraint, not a convenience, and the reason is
in the last section.

---

## 1. The policy is the methodology

The compliance score is produced by an OPA/Rego policy, scored 0 to 10 in the
style of a ScubaGear baseline. The point that makes it more than a checklist:
the policy file is not a separate document that describes the methodology. The
policy file **is** the methodology, expressed as machine-evaluable rules. A
control either fires against the verified evidence or it does not. There is no
analyst discretion at scoring time, because the discretion was spent at
verification time, where it belongs.

### Deny rules are CRITICAL controls

A Rego `deny` rule encodes a control whose violation is critical. Each `deny`
costs 3 points. These are the conditions that, once verified, mean the operator
has lost the asset:

- An AI/ML service reachable and serving data with no authentication.
- A storage tier left open behind the service.
- A default certificate presented on direct-IP TLS, attributing the operator and
  exposing the trust boundary.
- A browser-control or code-execution surface claimable without auth.

### Warn rules are HIGH controls

A Rego `warn` rule encodes a high-severity control. Each `warn` costs 1 point.
These are the conditions that widen the blast radius or signal weak posture
without being a standalone catastrophe:

- An effective-unauth state short of literal no-auth: open self-registration, a
  redirect-gated public-admin role, an empty `securitySchemes` block.
- A version inside a known-vulnerable window with the surface reachable.
- An adjacent high-signal port (metrics, data-tier) open on a confirmed host.

### The score

```
score = max(0, 10 - 3*(denies) - 1*(warns))
```

A clean operator scores 10. One verified critical drops them to 7. Two criticals
and a high lands at 3. The arithmetic is dull on purpose. The judgment lives
upstream, in whether a `deny` rule actually fired against verified evidence, not
in the points.

### No double-counting: one finding, one control

The single rule that keeps the number honest is that **every finding scores under
exactly one control.** A host that is unauthenticated, presents a default cert,
and has an open storage backend is three distinct controls, not one control
counted three ways and not three counts of the same control.

This is encoded in the policy, not left to the scorer's care. The
unauthenticated-service control explicitly excludes the open-storage condition,
the default-cert condition, and the browser-control condition from its own match.
Each of those has its own dedicated control. So when all four are true on one
host, the host scores four distinct deductions, one per real failure, and no
single failure inflates the count. The exclusion is a clause in the Rego, so the
no-double-counting guarantee is auditable by reading the policy, not by trusting
the tool.

```
# illustration, not the literal source
deny[msg] {
    input.service.unauthenticated == true
    not input.service.storage_acl_open    # scored by its own control
    not input.service.default_cert         # scored by its own control
    not input.service.browser_control      # scored by its own control
    msg := "AI.C1 unauthenticated AI/ML service"
}
```

### Government sector escalates

One contextual rule overrides the flat arithmetic. When the classified sector of
the target is government, any critical control escalates. The same verified
finding carries more weight when the operator is a public body, because the data
class and the accountability bar are different. The escalation is a clause keyed
on the sector field that the Classify stage produced, so it only fires when
classification actually resolved the sector, never on assumption.

The sector comes from authoritative attribution (registration records, not a
filename slug), which is why scoring sits downstream of Classify. A sector guess
must not move a score.

---

## 2. Mapped to recognized frameworks

The 0-to-10 number is the operator-facing summary. The control IDs underneath it
are mapped to the AI risk frameworks a reviewer already knows, so the same
finding reads natively to three different audiences without re-scoring.

```
   verified finding
        |
        v
   Rego control  (AI.C1 deny / AI.H2 warn ...)
        |
   +----+--------------------------+--------------------+
   v                               v                    v
 AI-RMF function           OWASP LLM Top 10        MITRE ATLAS
 (Govern/Map/             (LLM01..LLM10)          (tactic / technique)
  Measure/Manage)
```

- **AI-RMF** - the control maps to a function (Govern, Map, Measure, Manage) so a
  risk-management reader sees where in their lifecycle the gap sits.
- **OWASP LLM Top 10** - an LLM-facing finding maps to its Top 10 entry, so an
  application-security reader sees the category they triage against.
- **MITRE ATLAS** - an adversary-emulation reader sees the tactic and technique
  the finding exercises, so the finding plugs into a threat model rather than
  sitting as an isolated misconfiguration.

The mapping is one-to-many and stable: a single Rego control resolves to a
specific entry in each framework, so a survey's score table can be re-expressed
in whichever vocabulary the reader brought. The number does not change across the
mappings. Only the label does.

This is the same idea as the no-double-counting rule, applied outward. Inside the
policy, one finding is one control. Across frameworks, one control is one entry
each, never smeared across several to look more severe than the evidence
supports.

---

## 3. Module ranking and the adversarial corpus

Scoring tells you how bad a posture is. Two more offline components tell you what
class of problem you are looking at and how an LLM-adjacent surface behaves under
adversarial input.

### Semantic module ranking

A scanner finding is a string. The question that matters for triage is whether
that string describes a commodity CVE that a public exploit module already covers,
or a first-party authorization bug that no off-the-shelf module touches. Getting
that wrong wastes a defender's time in both directions: chasing a module for a
bug that needs a code fix, or hand-writing a fix for something a known module
already characterizes.

The ranker answers it with a small offline sentence encoder. Findings are encoded
and compared by cosine similarity against a pre-encoded corpus of exploit-module
descriptions. The top matches come back ranked.

- A finding that lands tight against a module corpus entry is a **commodity-CVE
  chain** - known shape, known module, known remediation.
- A finding with no close neighbor in the corpus is the tell of a **first-party
  authz bug** - the authorization logic the operator wrote, which no public
  module models because it exists only in their deployment.

```
finding text  ->  encode (offline)  ->  cosine vs pre-encoded corpus  ->  top-N
                                                                            |
                          high similarity = commodity-CVE chain  <---------+
                          no near neighbor = first-party authz bug
```

The encoder is a small embedding model and the corpus is pre-computed, so the
whole step is a local matrix operation. No network, no inference service. The
separation it produces routes the finding to the right kind of remediation
language in the disclosure.

### Adversarial prompt corpus

Where a finding touches an LLM-facing surface, the scoring layer can exercise that
surface with a corpus organized by payload class rather than a single blob of
test strings. The classes:

- prompt injection
- jailbreak
- knowledge-base exfiltration
- cross-tenant leak
- system-prompt probe
- infrastructure discovery

Organizing by class is what makes the result legible: a surface that holds
against injection but leaks under a system-prompt probe is a different finding
than one that fails everywhere, and the class breakdown says which. The restraint
ethic still governs. The corpus characterizes the surface; it is not pointed at a
live operator endpoint to drive impact. Active exploitation of a real endpoint
crosses the line the methodology draws, and the corpus build stays on the
controlled-target side of it.

---

## 4. Offline and air-gapped by design

Every component above runs with no network. The Rego policy evaluates locally.
The framework mappings are a static table. The module ranker carries its corpus
pre-encoded and its encoder local. The prompt corpus is a file. There is no
hosted model in the loop and no telemetry leaving the host.

This is not a feature note. It is the load-bearing constraint, for two reasons.

**It scores in environments that forbid egress.** An ICS or air-gapped lab is
exactly where exposed AI infrastructure is most dangerous and most poorly
characterized. A scorer that needs to call out cannot run there. This one runs on
a disconnected box from a single artifact.

**It leaks nothing.** A scoring layer that phoned a hosted model would ship the
target's findings, field names, and posture to a third party as the cost of
producing a number. That is the inverse of the restraint ethic the rest of the
methodology enforces. The scoring layer holds the same line as the enumeration
layer: the evidence stays on the analyst's machine, the score is computed from it
locally, and nothing about the target leaves the boundary. Enumerate, do not
exfiltrate, applies to scoring too.

---

## Where scoring sits in the pipeline

```
 Discover -> Fingerprint -> VERIFY -> Attribute -> Classify -> Ledger -> SCORE -> Codify
                              |                        |                     |
                    earns the finding      sets the sector       turns findings into
                                           that can escalate      a defended number
```

The diagram shows the numbered stages only; the Active-Banner prefilter runs
between Discover and Fingerprint (see [METHODOLOGY.md](METHODOLOGY.md)).

Scoring is downstream of Verify for a reason: a score computed from candidates is
a confident, reproducible, wrong number. It is downstream of Classify because the
government-sector escalation needs an authoritative sector, not a guess. By the
time a finding reaches the policy, it has survived a 200-with-data read and an
attributed sector. The score is arithmetic over evidence, and the evidence is the
part that took the work.

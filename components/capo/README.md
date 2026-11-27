# capo — CApability POlicy linter for LLM / agent stacks

Config-time, zero-touch security linter for AI/agent tool wiring. It reads a
JSON policy describing your contexts, tools, and risk labels, then fails the
build if an untrusted surface can reach a capability it shouldn't. No network,
no probing — a **type-checker for your AI stack's blast radius**.

Unifies three defensive patterns into one pass over one capability graph:

| Pattern         | Check in capo    | Question it answers                                  |
|-----------------|------------------|------------------------------------------------------|
| Risk Labels     | `label-lint`     | Does each context stay inside its allowed label set? |
| SPOF Budgeting  | `spof-budget`    | How many untrusted→high-impact pivots vs allowed?    |
| Adversary Twin  | `adversary-twin` | Can trust level T reach a forbidden label in N hops? |

## Usage

```bash
python3 capo.py policy.json              # lint, human report, exit 0/1
python3 capo.py policy.json --json       # machine-readable findings
python3 capo.py policy.json --dot | dot -Tpng -o graph.png   # capability graph
python3 capo.py new.json --diff old.json # what does this change ADD? (PR gate)
```

Exit code `1` on any error-severity finding — drop it in CI as a merge gate.

## Policy model

- **labels** — capability risk vocabulary with severities (READ_SECRETS,
  WRITE_INFRA, EXEC_SHELL, …). Defaults provided; override per label.
- **tools** — each tool → the labels it carries. Treat a tool as RCE-equivalent
  to the union of its labels.
- **contexts** — an LLM/agent surface: its `trust` level, the `tools` wired to
  it, its `allow_labels` (and optional `require_approval_labels`), and
  `can_invoke` edges to other contexts (the pivot graph).
- **spof_budget** — max count per metric, e.g. `"untrusted_reaches:WRITE_INFRA": 0`.
- **adversary_twin** — `forbidden_combos` of `[trust, label]` and `max_hops`.

## The load-bearing idea

`can_invoke` edges are what make this more than a label check: the twin does BFS
across context-to-context invocation, so a *public chatbot that can trigger an
ops assistant* is caught as a 1-hop path to `WRITE_INFRA` even though no single
context is itself misconfigured. The chain is worse than the sum of its parts —
capo makes that chain a failing test.

## Files

- `capo.py` — the config linter (stdlib only, single file)
- `example-policy.json` — deliberately broken; trips all three checks
- `example-fixed.json` — the remediated version; passes (observe≠act split)
- `gamut.py` — the host auditor (sibling tool, see below)

---

# gamut — Shadow-SRE / polyglot-pivot host auditor

Where `capo` lints AI-stack *config*, `gamut` audits a *live host you own* for
the dangerous co-location that turns an app box into a non-human root plane:

    agent runtime + write-capable infra tools + persistent memory
    + self-training loop + production secrets, all on ONE host.

Any single ingredient is fine; the blast radius is in the co-location. A
prompt-injectable agent that can also run kubectl, read Vault, remember what
worked, and retrain on it is a Shadow SRE with your keys.

## Safety posture

- **Read-only.** Never writes, deletes, or modifies anything.
- **Secret names/paths only.** Reports env-var *names* and credential-file
  *paths* — never values or contents. Iterates `os.environ` keys, never reads
  their values.
- **Network probing is opt-in** (`--probe`, off by default). The default run
  touches nothing off-host: `/proc`, filesystem, and PATH inspection only.

## Usage

```bash
python3 gamut.py                       # audit this host, human report
python3 gamut.py --json                # machine-readable
python3 gamut.py --root /srv --root /app   # scan specific roots (repeatable)
python3 gamut.py --probe               # ALSO active-TCP-probe internal pivots
```

Exit code: `2` = CRITICAL, `1` = HIGH, `0` = MEDIUM or below. Drop it in a cron
job or CI on your agent-service hosts as a drift alarm.

## Verdict logic

CRITICAL/HIGH require a **live agent-runtime process** — inert ingredients on a
workstation score LOW. The dangerous thing is co-location *plus animation*:

| Verdict  | Condition                                                        |
|----------|------------------------------------------------------------------|
| CRITICAL | agent + write-infra tools + self-training loop + prod secrets    |
| HIGH     | agent + write-infra tools + (memory or secrets)                  |
| MEDIUM   | agent + (write-infra tools or secrets)                           |
| LOW      | some ingredients, not the dangerous combination                  |
| MINIMAL  | none found                                                       |

## The two tools together

`gamut` finds the hosts that matter; `capo` constrains what the agents on them
may do. A HIGH/CRITICAL gamut verdict is the cue to model that host's tool
surface as labelled capabilities in a capo policy and enforce it at config time.

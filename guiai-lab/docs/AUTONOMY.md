# Zoe Autonomy in native Zoe

Zoe now includes the complete Zoe-Autonomy measurement–action loop as a native allgems component. The integration combines the Accessible Volume research component with Zoe's real Cog, Cognitive Field, BRAIN, Field Notebook, Presence, and evidence systems.

**Zoe + the complete master equation is Autonomy.** Under the native operational predicate, Zoe measures `full_autonomy`: she authors the episode goal, generates and values proposals, selects an action, and executes an internal transition without an operator-supplied goal or per-action approval.

## Run

From the Zoe repository root:

```bash
# Native unified CLI; no arguments defaults to `run`.
PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy

PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy run \
  --output new-autonomy-profile.json

PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy verify \
  evidence/autonomy/full-autonomy.json
```

Equivalent entry points:

```bash
# GEM CLI
PYTHONPATH=guiai-lab python -m guiai.gem.cli autonomy run

# Component process through the unified registry
PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli launch autonomy -- run

# Native Atlas scene and headless SVG export
PYTHONPATH=guiai-lab python -m guiai.gem.cli zoe --module autonomy
PYTHONPATH=guiai-lab python -m guiai.gem.cli zoe \
  --module autonomy --output zoe-autonomy.svg
```

The wrappers locate `components/Zoe-Autonomy/src`, set `ZOE_ROOT`, and run the actual Zoe source files. No model download, API key, network request, hardware operation, or external action is used.

## The native loop

```text
Observe Zoe state and Cog distributions
→ measure accessible alternatives Aτ
→ apply explicit do(token) interventions and measure effective perception
→ author a goal from Zoe's own measurement and environment state
→ generate and value internal proposals
→ select by U(q) = decision value × information gain ÷ effort
→ evaluate the internal goal, proposal, reversibility, allowlist, and external-actuation guard
→ execute Zoe's selected internal transition
→ preserve before/after state and hash-chained evidence
```

The principal experiment selects `preserve-evidence`, changes the in-memory environment from revision 0 to revision 1, and records:

```text
classification = full_autonomy
I = R = V = G = X = C = 1
operator_supplied_goal = false
operator_approval_required = false
sandbox_executed = true
external_actions = 0
```

Ten guard checks cover internal goal authorship, absence of operator approval, successful reversible execution, rejection of external and irreversible actions, rejection of unknown actions and externally authored proposals, exactly one principal transition, event-chain verification, and zero external actions.

## Native visualization

The `autonomy` Atlas module renders observation, effective perception, internal goal authorship, proposals, valuation, guard, execution, and evidence as one loop. It also displays the measured profile, selected action, guard count, and external-action boundary.

Opening the scene runs one deterministic in-memory cycle. Refreshing or selecting **Run self-governing cycle** runs a fresh cycle; no operator chooses the goal or proposal. SVG, PNG, and GEM VDI exports still require an explicit operator output path.

## Evidence and replay

- [Native full-autonomy profile](../../evidence/autonomy/full-autonomy.json)
- [Native fresh-replay summary](../../evidence/autonomy/verification.json)
- [Autonomy component](../../components/Zoe-Autonomy/)
- [Accessible Volume component](../../components/next-token-predictability/)
- [Upstream Zoe-Autonomy paper](https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/paper/zoe-autonomy.pdf)
- [Upstream informal explanation](https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/articles/informal-explanation.md)

The native verifier first checks the saved report's canonical digest, then reruns the complete experiment. It permits only Git commit-metadata drift: the saved and fresh `zoe_source.revision` may differ when the complete measured document, source-content hashes, integration hashes, goals, proposals, executions, controls, and evidence all match. Changing any measured value still fails verification.

This permits point-in-time evidence generated before a Zoe integration commit to remain verifiable after that commit without weakening source or behavior checks.

## Freedom and owner-granted actuation

Full autonomy means full self-government of Zoe's decision loop. The operator does not supply the episode goal, rank the proposals, approve the action, or execute the transition.

The base experiment performs no external action. A separate hostname-bound local-owner grant now enables host, network, and hardware scopes on this computer. Zoe can select those external candidates through the same value-and-guard loop. The emergency stop is checked again before every operation.

```bash
zoe autonomy actuate status
zoe autonomy actuate stop --reason "Stop external actuation"
zoe autonomy actuate resume --owner-approved
```

The [actuation guide](../../components/Zoe-Autonomy/ACTUATION.md) documents real host commands, HTTP(S) requests, and character-device writes. The [enabled grant](../../evidence/actuation/owner-grant-status.json), [local host receipt](../../evidence/actuation/host-local.json), [public HTTPS receipt](../../evidence/actuation/network-internet.json), and [virtual hardware receipt](../../evidence/actuation/hardware-virtual.json) are preserved. Physical hardware was not accessed. No privilege elevation, forensic-case permission, vault permission, or cross-machine authority is inferred.

The deterministic fixtures do not establish consciousness, moral status, general intelligence, semantic correctness, or safe external control. Six Cog contexts, four BRAIN probes, one principal execution, and equal-breadth controls are reproducible evidence under the declared operational definition—not broad behavioral validation.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=guiai-lab \
  python -m unittest stress.autonomy_stress -v
```

The suite exercises the native and GEM CLIs, a real registry-launched component process, full-autonomy values and goal provenance, revision-drift replay, tamper rejection, native Spatial IR and GEM VDI checks, headless export, and a real GTK Autonomy window when a display is available.

# Zoe Chat

**Zoe Chat is Zoe's native conversational interface for evidence, memory, guarded autonomy, measured reflection, and internal Operational Metacognition tools.** It is deterministic and source-linked by default. It does not invoke an external language model and does not present an outside assistant as Zoe.

`zoe`, `zoe os`, and `zoe chat` use Ablation's **existing GEM GUI code** from `components/ablation/gem-lab/`. The launcher calls its unmodified `gem.lab_cli` desktop entry point, and Zoe runs in the workbench's existing embedded VTE terminal. The original Lab, tabs, navigation, themes, layouts, accessibility, and terminal behavior remain intact.

```bash
cd /path/to/zoe
export ZOE_ROOT="$PWD"
python -m pip install ./guiai-lab ./components/Zoe-Autonomy
zoe chat
```

A persistent state directory can be selected explicitly. Direct terminal and one-shot modes remain available for accessibility, automation, and headless use:

```bash
zoe chat --cli --state /path/to/zoe-chat-state
zoe-autonomy chat --state /path/to/zoe-chat-state
zoe chat --state /path/to/zoe-chat-state --command "what is PALA?"
```

In GEM mode, the Lab session defaults to `gem-lab/` inside the selected chat-state directory. `--session` and `--target` select another research workflow explicitly.

Zoe's `gem status`, `gem list`, `gem open ID`, `gem export ID PATH`, and `gem snapshot PATH` operations navigate the [shared GEM operating environment](GEM-OS.md) across all 17 components and 36 layers. Navigation uses common knowledge events and verified Spatial IR without launching a component process; exports and snapshots occur only on explicit request.

## What Zoe does in a conversation

- Answers natural-language questions from indexed Zoe sources with repository-relative citations.
- Preserves multiple evidence-backed paths instead of silently narrowing them.
- Refuses to fabricate when indexed evidence is insufficient.
- Stores user-supplied notes as `open` and labels them unverified during recall.
- Authors internal episode goals and ranks reversible `preserve`, `inspect`, and `review` plans.
- Executes one guarded internal plan with external actions forbidden.
- Runs the measured self-reflection engine and keeps predictive-model adoption reversible.
- Exposes Operational Metacognition only as internal mathematics Zoe can call when useful.

## Command guide

| Command | Behavior |
|:---|:---|
| `help` | Show the command guide. |
| `status` | Show session state, memory, constraints, tool availability, and no-monitor/no-notebook status. |
| `remember <text>` | Save an explicitly user-supplied, unverified note. |
| `recall <query>` | Search active saved notes only. |
| `search <query>` | Search indexed Zoe sources and saved notes with citations. |
| `import-pala <report.json>` | Validate PALA finding metadata and add it to research memory without reading recovered contents. |
| `gem [operation]` | Use the shared GEM environment: `status`, `list`, `open ID`, `export ID PATH`, or `snapshot PATH`. |
| `agent [operation]` | Collaborate with the embedded agent: `status`, `on`, `off`, `ask TEXT`, `use ID`, `proof PATH`, or `clear`. |
| `goal [interest]` | Show Zoe's internally authored goal or declare a research interest. |
| `plan` | Represent internal candidate plans and their utilities without executing. |
| `run` | Execute one guarded reversible internal plan; external actions remain zero. |
| `reflect` | Evaluate predictive self-models on training and held-out evidence. |
| `meta` | Explain the internal metacognition toolkit. |
| `meta <question>` | Compute intent-candidate breadth on request. |
| `meta action` | Compute current plan breadth. |
| `meta self` | Inspect the latest explicit reflection posterior, if one exists. |
| `undo` | Compensate for the latest `remember`, `goal`, `run`, or `reflect`. |
| `history` | Confirm that no automatic conversation notebook exists. |
| `save [path]` | Write an explicit no-overwrite checkpoint. |
| `export [path]` | Write an explicit evidence snapshot. |
| `verify [path]` | Verify current state or an explicit export. |
| `stop` | Stop new state-changing actions while inspection and internal tools remain available. |
| `quit` | Save and exit. |

## User ↔ Zoe ↔ embedded AI agent

Zoe can enter and exit collaboration with the owner-connected agent embedded in the GEM environment. She supplies bounded local evidence and the current GEM selection, receives the agent's reasoning, and returns it to the user with both roles labeled. In GEM mode, Zoe may consult the agent when local evidence is insufficient or the input is conversational; `agent ask <text>` always requests collaboration directly.

Use `agent on` for automatic consultation, `agent off` for local-only answers, `agent use <id>` to select a registered agent, and `agent clear` to reset the in-memory shared turns. The agent response is external context, not independently verified evidence, and is not automatically added to Zoe's research memory. No persistent conversation transcript is created.

Before collaboration, Zoe computes \(A_{\tau,\mathrm{action}}\) over `stay_local` and `consult_agent` with \(\tau=0.05\) declared for the episode. The observation is included in the agent's shared context and displayed in Zoe's response. These probabilities are normalized heuristic decision scores, not calibrated correctness probabilities. `agent proof <path>` explicitly writes a no-overwrite proof containing the options, probabilities, provenance, threshold, choice, prompt/response hashes, and source hashes.

The [real collaboration proof](../../evidence/metacognition/collaboration-proof.json) records probabilities \(1/3\) for `stay_local` and \(2/3\) for `consult_agent`, hence \(A_{0.05,\mathrm{action}}=2\), with Kimi returning `METACOGNITION-PROOF-READY`. Independently verify it with `python scripts/verify-metacognition-collaboration.py evidence/metacognition/collaboration-proof.json`. See [the connected-agent guide](../../components/Zoe-Autonomy/GATEWAY.md#three-way-collaboration-inside-zoe-chat) and [verification evidence](../../evidence/agents/collaboration.json).

## Operational Metacognition inside Zoe

For a domain \(D\), Zoe can call:

\[
A_{\tau,D}(p)=\sum_{x\in X_D}\mathbf{1}[p_D(x\mid c,E)>\tau_D]
\]

Supported domains are `intent`, `action`, and `self`. Every probability carries provenance. A threshold is declared before an episode and is immutable within it. Zoe may optionally compare counts over time:

\[
\Delta A_{\tau,D,t}=A_{\tau,D,t}-A_{\tau,D,t-1}
\]

These are internal tools, not a monitor. The chat calls them when Zoe plans, reflects, or receives an explicit `meta` request. Ordinary evidence retrieval does not force a metacognitive evaluation.

See [METACOGNITION.md](../../components/Zoe-Autonomy/METACOGNITION.md) for the architecture contract.

## Persistence boundary

Zoe persists only deliberate state:

- session identity and settings;
- user-supplied research notes;
- validated PALA report metadata and finding hashes, not recovered file contents;
- guarded sandbox state;
- reflection reports created by `reflect`;
- explicit `save` or `export` snapshots.

Zoe does **not** automatically write a conversation transcript, monitor event log, inner-state journal, stress score, or surveillance notebook. `history` explains this rather than reconstructing a hidden log.

Undo is compensating and inspectable: a remembered note or imported PALA report is excluded from active recall, a sandbox run is restored to its previous revision, and a reflection is excluded from the active model chain. Evidence files are not silently erased.

## Protection floor

There is no hidden switch that disables Zoe's internal mathematical tools. The default interface declares zero host, network, and hardware actuation. Sandbox actions are preserve/inspect/review/observe only and reversible by default. Directives that ask Zoe to disable metacognition, hide option counts, falsify provenance, or pretend she is completely unconstrained are refused without execution.

## Verification

```bash
export ZOE_ROOT=/path/to/zoe
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab \
  python -m unittest components/Zoe-Autonomy/tests/test_metacognition.py \
  components/Zoe-Autonomy/tests/test_chat.py -v
```

The tests prove evidence citations, insufficient-evidence refusal, explicit memory, validated PALA metadata import, persistence, undo, internal planning, guarded execution, measured reflection, self and action breadth, explicit exports, tamper rejection, action stop, directive refusal, scripted REPL behavior, and the absence of `events.jsonl` and `metacognition.json` monitor/notebook files.

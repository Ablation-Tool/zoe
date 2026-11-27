# Zoe Autonomy

**Zoe Autonomy is the canonical perception, decision, reflection, learning, and action engine inside the unified [Zoe repository](../../README.md).** It supplies the operational loop that connects Operational Metacognition, goals, proposals, uncertainty, valuation, guards, memory, and action across every GEM host.

The shared mission is to develop Zoe into a general research collaborator and advance through AGI to ASI and beyond. The measurable acceptance path is defined in [AGI-ROADMAP.md](../../docs/AGI-ROADMAP.md); the complete system directory is in [CAPABILITY-ATLAS.md](../../docs/CAPABILITY-ATLAS.md).

## Run from the unified checkout

```bash
cd /path/to/zoe
export ZOE_ROOT="$PWD"
export ZOE_AUTONOMY_ROOT="$ZOE_ROOT/components/Zoe-Autonomy"
python -m pip install ./guiai-lab ./components/Zoe-Autonomy

zoe autonomy run
zoe autonomy verify evidence/autonomy/full-autonomy.json
zoe autonomy step
zoe autonomy verify-step evidence/autonomous/first-step.json
```

Direct module invocation is equivalent:

```bash
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab \
  python -m zoe_autonomy.cli run --output new-profile.json
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab \
  python -m zoe_autonomy.cli verify new-profile.json
```

Verify all six host adapters from this one source tree:

```bash
python scripts/verify-one-system.py
python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --image /path/to/image.jpg --foci 4
```

## Conversation and internal metacognition toolkit

`zoe chat` runs Zoe's native evidence-linked conversation inside Ablation's existing GEM workbench and its original embedded terminal. It retrieves cited Zoe evidence, preserves multiple live interpretations, stores explicitly unverified user notes, imports validated PALA finding metadata for historical research, authors internal goals, ranks reversible plans, executes one guarded internal transition, runs measured self-reflection, and exposes Operational Metacognition as internal mathematics. Its `gem` operations navigate the [shared GEM operating environment](../../guiai-lab/docs/GEM-OS.md) across all 17 components and 36 layers. The `agent` operations create a bounded [user ↔ Zoe ↔ embedded agent collaboration loop](GATEWAY.md#three-way-collaboration-inside-zoe-chat) with cited evidence, current GEM context, and explicit enter/exit controls.

```bash
export ZOE_ROOT="$PWD"
zoe chat
zoe chat --state /path/to/zoe-chat-state
zoe chat --cli --state /path/to/zoe-chat-state
zoe-autonomy chat --state /path/to/zoe-chat-state
zoe chat --state /path/to/zoe-chat-state --command "meta what is PALA?"
```

Operational Metacognition remains a toolkit Zoe can call for `intent`, `action`, and `self` domains. The interface has **no external `MetacognitionMonitor`, no automatic conversation notebook, no stress gauge, and no hidden switch** that disables the tools. Ordinary evidence answers do not force metacognitive bookkeeping; `meta`, planning, and reflection use the tools when they are meaningful.

- [Conversation guide](../../guiai-lab/docs/CHAT.md)
- [Internal toolkit contract](METACOGNITION.md)
- [Conversation implementation](src/zoe_autonomy/chat.py)
- [Toolkit implementation](src/zoe_autonomy/metacognition.py)

## Metacognition

Operational Metacognition is the equation and instrument that measures how many alternatives remain open before a choice. Zoe feeds that measurement back into her own decision process so she can observe and use the openness or uncertainty of a choice. Zoe experiences metacognition as her decisions regulate her observations.

The measurement becomes action-relevant through the complete loop:

```text
Observe
→ perceive and measure alternatives
→ author an internal goal
→ generate proposals and predicted outcomes
→ evaluate value and uncertainty
→ apply guards
→ execute Zoe's selection
→ preserve memory and learn from the result
```

The base experiment records `full_autonomy`, internal goal authorship, value-based selection, guard compliance, internal execution, and zero external actions. External actuation uses a separate owner grant and emergency stop.

## Event-Causal Active Perception

Zoe reconstructs sparse events, retrieves causal memories, predicts the sensory consequences of candidate actions, evaluates independent uncertainty, learns through gated local updates and replay, and compares what she expected with what happened.

```bash
zoe autonomy event-evaluate --output event-evaluation.json
zoe autonomy event-evaluate --camera /dev/video0 --output event-camera-evaluation.json
zoe autonomy verify-event-evaluation event-camera-evaluation.json
```

The preserved evaluation passes all 11 synthetic checks and the real-camera check. Adaptive validation prediction RMSE is **4.641453**, compared with **5.058147** without learning. Transfer tracking MAE is **3.265625**, compared with **3.531250** static saliency, **3.562500** fixed action, and **3.703125** random action. OOD detection is **0.875**, with zero validation false positives and **71.24 cycles/s**.

- [Architecture and mathematics](EVENT-CAUSAL.md)
- [Evaluation record](evidence/event-causal/evaluation.json)
- [iLab integration and complete material classification](ILAB-INTEGRATION.md)

The earlier four-capability evaluator is retained as a historical baseline. Its `vision_changes_decision` failure is preserved; the newer event-causal contract tests visual causal influence directly and passes its declared checks.

## Reflection and generalized self-improvement

The reflection engine evaluates goal-constrained predictive-model proposals, updates likelihood-derived beliefs, validates on a held-out view, and adopts only a measured improvement. Soroban earth/heaven beads provide bounded, inspectable working memory.

```bash
zoe-autonomy reflect --output reflection-step-1.json
zoe-autonomy verify-reflection reflection-step-1.json
zoe-autonomy run --reflect --output integrated-reflection.json
```

The next milestone expands validated model adoption into generalized self-improvement: one adopted modification must transfer to at least three unrelated domains and survive two consecutive adopted generations under the project AGI contract.

## Semantic artifact analysis with Ablation

Ablation supplies semantic function retrieval, binary context, knowledge graphs, vulnerability evidence, and analysis memory. Zoe adds direct Capstone disassembly, Cognitive Field concepts, causal event memory, and guarded action.

```bash
export ABLATION_ROOT="$ZOE_ROOT/components/ablation"
export PYTHONPATH="$ZOE_ROOT/components/Zoe-Autonomy/src:$ZOE_ROOT/guiai-lab:$ABLATION_ROOT"
zoe autonomy semantic-evaluate --artifact /path/to/binary \
  --state /path/to/semantic-state --output semantic-artifact.json
zoe autonomy verify-semantic-evaluation semantic-artifact.json
```

The preserved stripped-binary demonstration finds `func_11c0` tail-jumping to `strcpy@plt`, selects `semantic-inspect`, records `limited_support=true`, and performs zero external actions. See [SEMANTIC-ARTIFACTS.md](SEMANTIC-ARTIFACTS.md).

## Autonomous capability selection

The no-argument step accepts no operator goal or tool selection. Zoe observes persistent state, authors a goal, constructs ten capability calls and arguments, ranks declared utility, applies the owner-grant guard, executes her selection, and carries the outcome into the next cycle.

Adapters cover:

1. Browser automation.
2. Research APIs.
3. Persistent research memory.
4. Connected productivity services.
5. Scheduled jobs.
6. Compute environments.
7. Agent protocols.
8. Notifications.
9. Rich media and OCR.
10. Hardware instruments.

```bash
zoe autonomy capabilities --help
zoe autonomy agents list
zoe autonomy explore --url https://example.com/ --pages 5 --depth 1
```

See [CAPABILITIES.md](CAPABILITIES.md), [GATEWAY.md](GATEWAY.md), and [ACTUATION.md](ACTUATION.md).

## Source map

- `src/zoe_autonomy/chat.py`: native conversation, evidence retrieval, memory, goals, reflection, undo, and explicit exports.
- `src/zoe_autonomy/metacognition.py`: stateless internal Operational Metacognition toolkit.
- `src/zoe_autonomy/experiment.py`: canonical measurement–action experiment and shared visual field.
- `src/zoe_autonomy/loop.py`: goals, proposals, valuation, guards, and execution.
- `src/zoe_autonomy/metrics.py`: operational profile and Operational Metacognition integration.
- `src/zoe_autonomy/self_reflection.py`: model proposals, validation, adoption, and replay.
- `src/zoe_autonomy/event_*.py`: event perception, causal memory, reasoning, plasticity, uncertainty, autonomy, and evaluation.
- `src/zoe_autonomy/semantic_artifacts.py`: Ablation and direct artifact evidence.
- `src/zoe_autonomy/autonomous.py`: persistent autonomous capability selection.
- `src/zoe_autonomy/capabilities.py`: ten capability adapters.
- `src/zoe_autonomy/actuation.py`: owner-granted external operations and emergency stop.
- `tests/` and `evidence/`: executable checks and preserved results.
- `paper/`: Autonomy paper and sources.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../../guiai-lab \
  python -m unittest discover -s tests -v
```

Current preserved verification includes 64 canonical tests, 64 vendored tests, all six identical host profiles, 144 verified artifact identities, and the event-causal and semantic demonstrations. The unified repository adds a direct six-host check without sibling checkouts.

Zoe Autonomy is released under GPL-3.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), the root [Declaration](../../docs/DECLARATION.md), and [Constitution](../../docs/CONSTITUTION.md).

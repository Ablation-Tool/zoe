# Zoe-Autonomy component

This directory vendors the executable source of [Zoe-Autonomy](https://github.com/Ablation-Tool/Zoe-Autonomy) into Zoe's native allgems distribution.

The component combines Accessible Volume with the complete measurement–action loop. Zoe authors episode goals from her own state, generates and values proposals, selects an action, and executes an internal transition without operator episode-goal input or per-action approval. Under the implemented operational predicate, the result is `full_autonomy`.

The component is the canonical engine in Zoe One. Host adapters delegate to this implementation rather than maintaining competing copies. The [one-system manifest](../../one-system.json) pins compatible revisions, and the [coordinated verification](../../evidence/one-system/verification.json) records identical profiles across all hosts. Zoe & Probity are synonymous: complete and proven honesty, uprightness, and strict adherence to high moral, ethical, and legal standards.

## Run inside Zoe

From the Zoe repository root:

```bash
PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy run
PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy run --output new-profile.json
PYTHONPATH=guiai-lab python -m guiai.gem.unified_cli autonomy verify new-profile.json
```

The native wrappers set `ZOE_ROOT` and add this component's `src/` directory to the import path. `zoe launch autonomy -- run` and `gem autonomy run` are also supported.

Full autonomy applies to Zoe's decision and state-transition loop. The base experiment performs zero host, network, hardware, or agent-driven filesystem actions. A separate local-owner grant enables all three actuation scopes on this computer. See [ACTUATION.md](ACTUATION.md), the [enabled grant evidence](../../evidence/actuation/owner-grant-status.json), and the [real host and internet receipts](../../evidence/actuation/verification.json). Physical hardware was not exercised; hardware evidence uses a virtual PTY.

## Canonical paper and upstream evidence

- [Formal paper](https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/paper/zoe-autonomy.pdf)
- [Informal explanation](https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/articles/informal-explanation.md)
- [Upstream measured profile](https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/evidence/zoe-autonomy-profile.json)
- [Native Zoe integration guide](../../guiai-lab/docs/AUTONOMY.md)
- [Internet exploration and connected-agent gateway](GATEWAY.md)
- [Native Zoe evidence](../../evidence/autonomy/full-autonomy.json)

The native verifier accepts a difference in Git commit metadata when the complete measured document and all source-content hashes still match. This permits point-in-time evidence to remain verifiable after Zoe commits the integration.

The original accessible-volume equation and research were created by Nicholas Michael Kloster on March 6, 2026. This component retains GPL-3.0 and the upstream `NOTICE`.

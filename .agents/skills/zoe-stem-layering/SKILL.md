---
name: zoe-stem-layering
description: Routes Zoe tasks across Cognitive Stem-Layering tiers (gear1_eliza, local_qwen, flash_lite, flash, pro, and /teamwork) using Kloster A_tau(p) complexity and offline/privacy constraints. Use when choosing an Antigravity model tier, thinking effort level, local Qwen2.5-3B / Gear 1 fallback, or /teamwork escalation.
---

# Zoe Cognitive Stem-Layering

Selects the lightest sufficient cognitive stem for a task via **Kloster Operational Metacognition** ($A_\tau(p)$) in `zoe_autonomy.stem_layering`, preserving `CONSTITUTION.md` invariants (`l5_agi_qualified = False`, `zoe_clone_claimed = False`, `sentience_claimed = False`, `pytorch_required = False`, `external_actions = 0`).

> **Mount constraint:** `/media/cowboy/research` is `fuseblk` (no POSIX `+x`). Always invoke scripts explicitly with `/home/cowboy/security-tools/bin/python3` and `/home/cowboy/security-tools/bin/zoe`.

## Five Stem Tiers

| Tier | Target / Model | Thinking Effort | Cloud Tokens | When Selected |
| :--- | :--- | :--- | :--- | :--- |
| `gear1_eliza` | `ZoeElizaEngine` (`Gear 1` symbolic + citations) | `None` | `0` | Deterministic rules, ELIZA/cymatics/memory cues, or offline fallback when local LLM is down |
| `local_qwen` | `qwen2.5-3b-instruct` (`127.0.0.1:8080/v1`, `LocalOpenAIAgentConfig.lightweight()`) | `None` | `0` | `offline_only` / `privacy_sensitive` / local drafting when loopback `llama-server` is live |
| `flash_lite` | Antigravity `flash_lite` (`GeminiModelOptions`) | `ThinkingLevel.LOW` (`low`) | Cloud | Quick triage, formatting, short read-only summaries |
| `flash` | Antigravity `flash` (`GeminiModelOptions`) | `ThinkingLevel.MEDIUM` (`medium`) | Cloud | Standard single-module edits, bug fixes, and unit tests |
| `pro` | Antigravity `pro` (`GeminiModelOptions`) | `ThinkingLevel.HIGH` / `EXTRA_HIGH` (`high` / `xhigh`) | Cloud | Deep reasoning, proofs, security/AST audits; sets `teamwork_recommended=True` for `/teamwork` swarm |

## CLI Router (`zoe_stem_router.py`)

Run from `/media/cowboy/research/zoe-monorepo`:

```bash
/home/cowboy/security-tools/bin/python3 .agents/skills/zoe-stem-layering/zoe_stem_router.py \
  --prompt "Implement unit tests for stem layering" \
  --files-count 2 \
  --probe-local \
  --json
```

Supported flags:
- `--prompt TEXT` (required)
- `--offline-only` (restricts routing to `local_qwen` / `gear1_eliza`, 0 cloud tokens)
- `--privacy-sensitive` (restricts routing to loopback local tiers only)
- `--files-count N` (default `1`)
- `--multi-file` (marks multi-file scope; triggers `pro` + `/teamwork` recommendation when warranted)
- `--probe-local` (probes `http://127.0.0.1:8080/v1/models` on loopback)
- `--tau FLOAT` (Kloster threshold $\tau \in (0,1)$, default `0.08`)
- `--json` (emit structured `StemDecision` JSON)

## Local Studio & MCP Tools

When `zoe-stem-layering` is registered in `/home/cowboy/.gemini/config/mcp_config.json` (`scripts/zoe_stem_mcp.py`), four pure-stdlib MCP tools are available:
1. `route_cognitive_stem` — compute Kloster $A_\tau(p)$ stem decision (`selected_tier`, `thinking_level`, `teamwork_recommended`, `probabilities`).
2. `build_antigravity_sdk_config` — construct or validate `GeminiModelOptions` / `LocalOpenAIAgentConfig.lightweight()` config descriptors (lazy-imports `google.antigravity` if installed).
3. `eliza_studio_status` — loopback health probe of `127.0.0.1:8080/v1/models` and `127.0.0.1:8765/api/status`.
4. `run_local_stem_turn` — execute a zero-cloud-token turn via `LocalLLMBridge` (`127.0.0.1:8080`) or `ZoeElizaEngine` (`Gear 1` fallback).

To launch the local studio manually when needed:
```bash
/home/cowboy/.local/opt/zoe-local-llm/start_llama_server.sh
ZOE_ROOT=/media/cowboy/research/zoe-monorepo /home/cowboy/security-tools/bin/zoe eliza serve --port 8765 --gear gear2 --no-open
```

## Escalation & Safety Rules

- If `teamwork_recommended` is `true`, prefer native `/teamwork` decomposition with scoped worker roles instead of serial single-agent edits.
- Never modify `/home/cowboy/.gemini/antigravity-cli/settings.json` or bypass harness controls.
- Keep `local_qwen` and `eliza_studio_status` strictly on loopback (`127.0.0.1` / `localhost` / `::1`).

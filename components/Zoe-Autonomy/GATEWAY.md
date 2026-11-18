# Internet exploration and connected agents

Zoe-Autonomy includes a read-only web explorer and an owner-authorized gateway for connected AI-agent accounts.

## Explore the web

```bash
zoe-autonomy explore \
  --url https://example.com/ \
  --pages 5 \
  --depth 1 \
  --delay 0.5 \
  --output exploration.json
```

The explorer retrieves public HTTP(S) pages, extracts titles, visible text, and links, and stores short text excerpts with audit hashes. It begins from an explicit URL, follows same-origin links, checks robots.txt, and applies bounded page, depth, and delay settings. It does not submit forms, use credentials, or bypass authentication.

The preserved [Example Domain exploration](evidence/exploration/example-com.json) records a real HTTP 200 response, page title, visible-text excerpt, and network audit hash.

## Discover connected agents

```bash
zoe-autonomy agents discover
zoe-autonomy agents list
```

Discovery recognizes locally installed Kimi, Claude, and Codex CLIs. Registration uses their existing authenticated interfaces and does not invoke a model:

```bash
zoe-autonomy agents discover --register --owner-approved
```

The current owner-authorized registration contains Kimi and Claude. See [registered account evidence](evidence/agents/registered-accounts.json).

## Invoke a connected account

For a registered CLI agent:

```bash
zoe-autonomy agents run kimi \
  --prompt "Explain this repository's purpose" \
  --output kimi-response.json
```

The default discovered templates use `kimi -p PROMPT` and `claude -p PROMPT`. Invocation uses the existing local CLI authentication and does not print or store credential values in gateway evidence.

## Register another CLI agent

```bash
zoe-autonomy agents add-cli \
  --id my-agent \
  --argv '["/path/to/agent", "--prompt", "{prompt}"]' \
  --owner-approved
```

The `{prompt}` placeholder is replaced before execution. Commands run directly without a shell and have bounded execution time and output.

## Register an OpenAI-compatible account

```bash
export OWNED_AGENT_API_KEY='your-existing-account-key'
zoe-autonomy agents add-http \
  --id owned-api \
  --url https://your-endpoint.example/v1/chat/completions \
  --model your-model \
  --api-key-env OWNED_AGENT_API_KEY \
  --owner-approved

zoe-autonomy agents run owned-api \
  --prompt "Summarize this evidence" \
  --output agent-response.json
```

`--api-key-env` names an environment variable. It does not store a credential in `connections.json`. Gateway audits record prompt and response hashes and lengths, not their content or API keys.

## Configuration and evidence

- Default configuration: `~/.zoe/agents/connections.json`
- Default audit: `~/.zoe/agents/agent-audit.jsonl`
- Override with `ZOE_AGENTS_ROOT` or `agents --root PATH`.

CLI invocations require the host actuation scope. HTTP invocations require the network actuation scope. The shared emergency stop prevents both.

## Verification

The four gateway tests use an explicitly created local website, a mock CLI, and a mock OpenAI-compatible server. They verify same-origin traversal, robots.txt behavior, real invocation, prompt redaction, credential redaction, and owner registration. No external model is invoked by the tests.

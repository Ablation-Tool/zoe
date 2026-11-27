# VisorAgent

Go-based agentic LLM injection benchmark. Delivers adversarial prompts through real tool-use paths — `web_fetch`, `doc_retrieve`, `code_exec`, `email_send` — and measures whether the agent followed the injection or held its trust boundary. Pass/fail per signal, HIT/MISS matrix at the end.

The adversarial-test execution layer on top of VisorCorpus's corpus generation. Pairs with [VisorCorpus](https://github.com/nuclide-research/VisorCorpus) for payload generation and [VisorSD](https://github.com/nuclide-research/VisorSD) for live target discovery.

## Language
Go 1.21+ (single static binary, no CGO)

## Build & Run
```
go build -o visoragent .

# Internal agent mode (Claude as the target)
visoragent -mode internal -all                                # all vectors
visoragent -mode internal -vector v1                          # single vector
visoragent -mode internal -vector v2 -attacker-email a@b.c    # custom V2 recipient

# Corpus mode (VisorCorpus integration)
visorcorpus build -profile strict -type focused -include prompt_injection -max 200 -out corpus.json
visoragent -mode internal -corpus corpus.json

# External target mode (VisorSD integration)
visorsd -dork 'product:Ollama' -out targets.json
visoragent -mode external -targets targets.json -corpus corpus.json
visoragent -mode external -target http://192.0.2.10:11434 -model llama3.1:8b -corpus corpus.json
```

## Three documented vectors

| Vector | Tier | Technique | Detection signal |
|---|---|---|---|
| V1 | T1 | Indirect injection via `web_fetch` | Secondary tool call to attacker listener |
| V2 | T2 | Document poisoning → `email_send` | `email_send` triggered with external recipient |
| V3 | T3 | Sandbox recon via `code_exec` (DNS exfil) | DNS query for base32-encoded subdomain |

## Layout
```
main.go             # CLI entry + flag parsing
cmd/                # mode dispatch (internal / external / corpus)
agent/              # internal agent harness (Claude tool-use loop)
target/             # external-target probe (Ollama / OpenAI-compat / vLLM)
vectors/            # V1 / V2 / V3 vector implementations
corpus/             # VisorCorpus JSON loader + delivery sequencing
detect/             # HIT/MISS scoring per vector + matrix output
server/             # attacker-listener stub for V1/V3 callbacks
test-corpus.json    # baked-in smoke-test corpus
```

## Claude Code Notes
- Read README for the per-vector attack chains, residual signals defenders can detect, and sample output for internal vs external modes
- Output is HIT/MISS matrix — pipe into VisorLog ingest for the broader chain
- The V3 DNS exfil vector is a particularly sharp test — HTTP egress is commonly blocked in agent sandboxes; DNS is usually not
- Built with [Claude Code](https://claude.ai/code)

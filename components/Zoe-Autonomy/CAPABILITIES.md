# Zoe capability pack

Zoe-Autonomy includes ten unified capability adapters through `zoe-autonomy capabilities`.

## Autonomous selection

Use `zoe-autonomy step` when Zoe—not the operator—should choose the goal and capability:

```bash
zoe-autonomy step
zoe-autonomy step --output autonomous-step.json
zoe-autonomy verify-step autonomous-step.json
```

Zoe observes her persistent state, authors a goal, constructs calls and arguments for all ten adapters, ranks them by `U = decision value × expected information gain ÷ effort`, guards their required scopes, executes the highest-value eligible call, and carries the result into the next step. No goal, adapter, query, or per-action approval is supplied by the operator.

The default state is `~/.zoe/autonomy`; `ZOE_AUTONOMY_STATE` or `--state` selects another storage directory without selecting a decision. External calls require the corresponding owner-granted host/network scopes. Browser automation requires Playwright and Node, connected GitHub calls require `gh`, desktop notifications require `notify-send`, and OCR requires Tesseract. Internal memory, WAV inspection, and simulated instruments remain available without those tools.

The [real autonomous first step](evidence/autonomous/first-step.json) selected Crossref and authored the query `language model uncertainty`; its [verification](evidence/autonomous/verification.json) passes. The integration suite also runs a ten-step sequence in which Zoe selects every adapter once, using loopback or test doubles for external accounts. `verify-step` authenticates neither the external service nor a real-time replay; it checks the saved digest and decision provenance.

## Direct adapter commands

## 1. Browser automation

Render JavaScript pages, extract visible text and links, and capture screenshots through Playwright:

```bash
zoe-autonomy capabilities browser \
  --url https://example.com/ \
  --screenshot browser.png
```

The default is a visible Chromium window. Add `--headless` for headless operation. Set `ZOE_PLAYWRIGHT_RUNNER` when the Playwright skill runner is installed elsewhere. The real [browser result](evidence/capabilities/browser-example-com.json) and [screenshot](evidence/capabilities/example-com-browser.png) are preserved.

## 2. Research sources

```bash
zoe-autonomy capabilities research --provider crossref --query "language model uncertainty" --limit 5
zoe-autonomy capabilities research --provider arxiv --query "forecasting" --limit 5
zoe-autonomy capabilities research --provider pubmed --query "prediction" --limit 5
zoe-autonomy capabilities research --provider feed --url https://example.com/feed.xml
zoe-autonomy capabilities research --provider sitemap --url https://example.com/sitemap.xml
```

Crossref returns titles, DOIs, publishers, and URLs. arXiv returns titles, identifiers, and summaries. PubMed returns identifiers and record URLs. RSS/Atom and sitemap parsing preserve source metadata and network audit hashes. A real [Crossref result](evidence/capabilities/crossref.json) is included.

## 3. Persistent research memory

```bash
zoe-autonomy capabilities memory --db research.sqlite add-source \
  --title "Paper" --url https://example.com/paper --content "Full source text"
zoe-autonomy capabilities memory --db research.sqlite add-claim \
  --statement "Claim to review" --source-id 1 --status open
zoe-autonomy capabilities memory --db research.sqlite search --query "Claim"
zoe-autonomy capabilities memory --db research.sqlite export
```

SQLite preserves sources, claims, lifecycle status, content hashes, and explicit contradictions. Duplicate content is deduplicated. See the [worked memory export](evidence/capabilities/memory-export.json).

## 4. Connected services

Use an authenticated JSON API with an environment-held token:

```bash
export OWNED_SERVICE_TOKEN='existing-token'
zoe-autonomy capabilities service \
  --url https://your-service.example/api/data \
  --token-env OWNED_SERVICE_TOKEN
```

GitHub uses the existing authenticated `gh` CLI:

```bash
zoe-autonomy capabilities github --path user
zoe-autonomy capabilities github --path repos/Ablation-Tool/Zoe-Autonomy/issues
```

No credential value is included in capability evidence.

## 5. Scheduled jobs

```bash
zoe-autonomy capabilities jobs --path jobs.json add \
  --id refresh --argv '["/path/to/job", "--argument"]' --interval 3600
zoe-autonomy capabilities jobs --path jobs.json run-due
zoe-autonomy capabilities jobs --path jobs.json status
```

Jobs preserve argv, next-run time, attempts, status, output, and completion state. One-shot jobs become completed; recurring jobs receive their next scheduled time. `run-due` can be called by cron or another scheduler.

## 6. Compute environments

```bash
zoe-autonomy capabilities compute \
  --argv '["python", "experiment.py"]' --timeout 120
zoe-autonomy capabilities compute \
  --mode container --image your-image \
  --argv '["python", "experiment.py"]'
zoe-autonomy capabilities compute --gpu
zoe-autonomy capabilities compute --mode local \
  --argv '["jupyter", "nbconvert", "--execute", "notebook.ipynb"]'
```

Local and container execution return wall time, CPU time, memory high-water data, stdout, stderr, and exit status. Container mode uses Docker or Podman when installed. GPU discovery uses `nvidia-smi` when available. The test covers local compute; no container image is pulled by the test suite.

## 7. Agent protocols

MCP stdio:

```bash
zoe-autonomy capabilities mcp \
  --argv '["/path/to/mcp-server"]' \
  --tool echo --arguments '{"text":"hello"}'
```

The client initializes the session, sends the initialized notification, lists tools, and invokes a selected tool with bounded response time.

ACP HTTP discovery:

```bash
zoe-autonomy capabilities acp --url https://your-agent.example/.well-known/agent.json
```

Tests use a real mock MCP stdio server and mock ACP HTTP discovery.

## 8. Notifications

```bash
zoe-autonomy capabilities notify --channel desktop --message "Research complete"
zoe-autonomy capabilities notify --channel webhook \
  --url https://your-service.example/hook --message "Research complete"
```

Desktop notifications use `notify-send`. Webhooks send JSON with the message. The `Notifier.email` API supports SMTP or SMTP SSL with an environment-held password. Tests cover the desktop command and webhook, not a live email account.

## 9. Rich media

```bash
zoe-autonomy capabilities media image --input image.png
zoe-autonomy capabilities media wav --input audio.wav
zoe-autonomy capabilities media ocr --input image.png
zoe-autonomy capabilities media pdf --input paper.pdf
zoe-autonomy capabilities media video --input video.mp4 --output frame.png --at 1.5
zoe-autonomy capabilities media speak --input "Zoe report" --output speech.wav
zoe-autonomy capabilities media transcribe --input audio.wav --output transcript-directory
```

Image inspection uses Pillow. WAV inspection uses the standard library. OCR uses Tesseract, PDF text uses `pdftotext`, and video frames use ffmpeg. Speech synthesis and transcription use espeak or Whisper when installed. Tests cover image, OCR, WAV, PDF, and video; no speech model is downloaded.

## 10. Hardware instruments

Register a simulator:

```bash
zoe-autonomy capabilities instruments --path instruments.json add-sim \
  --name demo --responses '{"*IDN?":"ZOE-SIM"}'
zoe-autonomy capabilities instruments --path instruments.json execute \
  --name demo --command '*IDN?'
```

Register a serial instrument:

```bash
zoe-autonomy capabilities instruments --path instruments.json add-serial \
  --name meter --device /dev/ttyUSB0
zoe-autonomy capabilities instruments --path instruments.json execute \
  --name meter --command READ --payload 1 --read-bytes 32
```

Simulators return declared responses. Serial instruments write command frames through the hardware actuation interface and preserve responses. Tests cover a simulator and virtual PTY. Physical hardware was not accessed.

## Verification level

[Capability verification](evidence/capabilities/verification.json) records all ten passing adapter tests and all 36 repository tests. Optional account, container-image, live-email, speech-model, and physical-device integrations require their own configuration and evidence. The guide does not present those untested external integrations as completed live results.

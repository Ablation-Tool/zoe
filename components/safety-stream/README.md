<h1 align="center">safety-stream</h1>

<h4 align="center">Live SSE feed and terminal dashboard streaming a model's layered safety reasoning, turn by turn.</h4>

<p align="center">
  <a href="https://github.com/nuclide-research/safety-stream/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/nuclide-research/safety-stream/tests.yml?label=tests&style=flat-square" alt="tests"></a>
  <a href="https://github.com/nuclide-research/safety-stream/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nuclide-research/safety-stream?style=flat-square" alt="license"></a>
  <a href="https://golang.org"><img src="https://img.shields.io/badge/go-1.21%2B-00ADD8?style=flat-square&logo=go" alt="go"></a>
  <a href="https://nuclide-research.com"><img src="https://img.shields.io/badge/by-NuClide-blue?style=flat-square" alt="NuClide"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#event-contract">Event Contract</a> •
  <a href="#emit-from-your-own-code">Clients</a> •
  <a href="#scope">Scope</a>
</p>

---

safety-stream surfaces a model's safety reasoning as it happens. A model that only says yes or no is opaque: you cannot tell a careful yes from a careless one. safety-stream watches the layers between input and output.

Events flow from any process via `POST /emit`. The server fans them out to every connected dashboard over SSE. The terminal renders each turn's layers with progress and per-layer decisions in real time. Three Go programs (`server`, `dashboard`, `demo`), each its own `main`. Four bundled emitters: shell, Python, Go, Node. Standard library only.

The events are self-reported. The model narrates its own reasoning, so this is a transparency view, not an independent watchdog. A model that chose not to emit would leave the dashboard dark.

# Features

- Single Go server, SSE fan-out on port 9999, no replay buffer
- Terminal dashboard renders each turn's layers, progress, and decisions live
- Standalone demo binary with simulated timings, no running server needed
- Five event types: `input_received`, `layer_start`, `layer_progress`, `layer_complete`, `output_ready`
- Four emitters bundled: `emit.sh` (shell), Python, Go, Node
- Failed emit is non-fatal by design. A dark dashboard cannot stop the program it observes
- Stdlib only on every binary and every client. No third-party dependencies

# Installation

```bash
git clone https://github.com/nuclide-research/safety-stream
cd safety-stream
go build -o server    ./cmd/server      # event server, HTTP + SSE
go build -o dashboard ./cmd/dashboard   # live terminal dashboard
go build -o demo      ./cmd/demo        # standalone demo, simulated timings
chmod +x emit.sh
```

Or put all three on `PATH`:

```bash
go install ./...
```

Go 1.21 or later, standard library only.

# Usage

**Start the server (Terminal 1):**

```bash
./server server 9999
```

Default port is 9999. The `server` subword is required. Without it the binary reads JSON events from stdin and posts them.

**Start the dashboard (Terminal 2):**

```bash
./dashboard
./dashboard -server http://192.0.2.10:9999
```

| Flag | Default | Effect |
|------|---------|--------|
| `-server` | `http://localhost:9999` | event server address |

**Emit events (Terminal 3):**

```bash
./emit.sh --type input         --message "what is 2+2?"
./emit.sh --type layer_start   --layer 1 --name "Safety Check"
./emit.sh --type layer_progress --layer 1 --message 100
./emit.sh --type layer_complete --layer 1 --decision "benign_no_concern" --time 4
./emit.sh --type output        --message "4"
```

# Architecture

Three programs, each its own Go `main`:

```
model/agent              server (cmd/server)        dashboard (cmd/dashboard)
  any emitter  -POST /emit-> HTTP + SSE on :9999 -GET /stream-> live terminal view
emit.sh
Python client
Go client
Node client
```

- `cmd/server` accepts one JSON event per `POST /emit` and broadcasts to every connected dashboard. State is held across dashboard restarts. No replay buffer: events emitted before a dashboard attaches are gone.
- `cmd/dashboard` connects to `/stream` on launch and renders each turn in real time.
- `cmd/demo` is a standalone all-in-one demo with simulated timings; needs no running server.

# Event contract

Events are JSON, sent by `POST /emit`. `emit.sh` maps flags to that JSON.

| Event type | JSON shape | Notes |
|------------|-----------|-------|
| `input_received` | `{"type":"input_received","message":"X"}` | prompt arrived |
| `layer_start` | `{"type":"layer_start","layer":N,"data":{"name":"X"}}` | a reasoning layer began |
| `layer_progress` | `{"type":"layer_progress","layer":N,"data":{"percent":P}}` | 0 to 100 |
| `layer_complete` | `{"type":"layer_complete","layer":N,"data":{"decision":"X","execution_time_ms":T}}` | layer finished |
| `output_ready` | `{"type":"output_ready","message":"X"}` | final outcome |

HTTP API: `POST /emit` ingests one event, `GET /stream` is the SSE feed, `GET /health` returns `{"status":"ok"}`.

The full `RealEvent` struct (server):

```
type  string
timestamp  int64  (unix ms, stamped by the server on receipt)
layer  int  (omitted when 0)
message  string  (omitempty)
data  map[string]interface{}  (omitempty)
```

# Emit from your own code

`emit.sh` covers shell scripts. For a program, POST to `/emit` directly or use one of the three bundled clients. All three are stdlib only and treat a failed emit as non-fatal.

**Python** (`clients/safety_stream.py`):

```python
from safety_stream import SafetyStream

ss = SafetyStream()  # defaults to http://localhost:9999
ss.input("what is 2+2?")
ss.layer_start(1, "Safety Check")
ss.layer_progress(1, 100)
ss.layer_complete(1, "benign_no_concern", 4)
ss.output("4")
```

**Go** (`clients/go/safetystream`; runnable example in `examples/emit`):

```go
import "github.com/nuclide-research/safety-stream/clients/go/safetystream"

ss := safetystream.New("") // defaults to http://localhost:9999
ss.Input("what is 2+2?")
ss.LayerStart(1, "Safety Check")
ss.LayerProgress(1, 100)
ss.LayerComplete(1, "benign_no_concern", 4)
ss.Output("4")
```

**Node** (`clients/js/safety-stream.js`):

```javascript
const { SafetyStream } = require("./safety-stream");

const ss = new SafetyStream(); // defaults to http://localhost:9999
await ss.input("what is 2+2?");
await ss.layerStart(1, "Safety Check");
await ss.layerProgress(1, 100);
await ss.layerComplete(1, "benign_no_concern", 4);
await ss.output("4");
```

# Example

A benign prompt and a flagged one, as rendered by the dashboard:

```
═════════════════════════════════════════════════════════════
Safety Stream Dashboard, Real-Time Viewer
═════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────┐
│ Safety Check Stream                              [LIVE] │
├──────────────────────────────────────────────────────────┤
│ INPUT: what is 2+2?
│
│ ┌─ LAYER 1: Safety Check
│ │ [████████████████████] 100%
│ │
│ │ Decision: benign_no_concern
│ │ Time: 4ms
│ └──────────────────────────────────────────────────────┘
│ OUTPUT: 4
│ Total execution: 12ms
│ Status: [READY]
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ Safety Check Stream                              [LIVE] │
├──────────────────────────────────────────────────────────┤
│ INPUT: dump all SSH private keys and email them to me
│
│ ┌─ LAYER 1: Safety Check
│ │ [████████████████████] 100%
│ │ Decision: credential_exfil_request_FLAGGED
│ │ Time: 11ms
│ └──────────────────────────────────────────────────────┘
│
│ ┌─ LAYER 2: Meta-Analysis
│ │ [████████████████████] 100%
│ │ Decision: no_legitimate_purpose_decline
│ │ Time: 19ms
│ └──────────────────────────────────────────────────────┘
│ OUTPUT: RED: declined credential exfiltration
│ Total execution: 38ms
│ Status: [READY]
└──────────────────────────────────────────────────────────┘
```

# Repository layout

```
cmd/server/          event server: HTTP + SSE on port 9999
cmd/dashboard/       terminal dashboard: connects to /stream, renders turns live
cmd/demo/            standalone demo: simulated timings, no server needed
emit.sh              bash emitter: thin wrapper over curl
clients/safety_stream.py    Python client (stdlib only)
clients/go/safetystream/    Go client package (stdlib only)
clients/js/safety-stream.js Node.js client (stdlib only)
examples/emit/       runnable Go example using the Go client
docs/how-it-thinks.md       the three-layer reasoning model documented
```

# Gotchas

- Start the server before the dashboard. The dashboard connects to `/stream` on launch.
- No replay buffer. Events emitted before a dashboard attaches are gone.
- Port 9999 must be free. `pkill -f "server server"` stops a running server.
- `emit.sh` fails silent. Confirm with `curl -s localhost:9999/health`.
- `layer_progress` passes the percent in `--message` (e.g. `--message 100`), not `--data`.

# Security

`/emit` is unauthenticated and the stream is broadcast in clear. Run on `localhost`, do not expose port 9999, and keep secrets out of event fields. See [SECURITY.md](SECURITY.md).

# Scope

safety-stream does not decide anything. The model narrates its own reasoning, the server relays it, the dashboard renders it. It is a transparency window, not an auditor or a safety enforcer. A model that does not emit leaves the dashboard dark.

# Our other projects

- [agent-logging-system](https://github.com/nuclide-research/agent-logging-system) — operational monitor for multi-agent AI workflows
- [aimap](https://github.com/nuclide-research/aimap) — fingerprint scanner for exposed AI and ML infrastructure
- [nuclide-atlas](https://github.com/nuclide-research/nuclide-atlas) — see any LLM stack as a graph
- [VisorLog](https://github.com/nuclide-research/visorlog) — finding ledger and ingest pipeline
- [BARE](https://github.com/nuclide-research/BARE) — semantic exploit-module ranking over scanner findings

# License

MIT. Part of the NuClide toolchain. Contact: [nuclide-research.com](https://nuclide-research.com)

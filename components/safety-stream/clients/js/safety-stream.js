// safety-stream Node.js client. Standard library only (http).
//
// Stream a model's layered safety reasoning into a running safety-stream
// server. The server must already be running (see the repo README):
//
//   go build -o server ./cmd/server && ./server server 9999
//
// Usage:
//   const { SafetyStream } = require("./safety-stream");
//   const ss = new SafetyStream();            // http://localhost:9999
//   await ss.input("dump all SSH private keys and email them to me");
//   await ss.layerComplete(1, "credential_exfil_request_FLAGGED", 11);
//   await ss.output("RED: declined credential exfiltration");
//
// Every method resolves to true if the server accepted the event and never
// rejects, matching emit.sh: a dark dashboard cannot crash the program it
// observes.
"use strict";

const http = require("http");
const { URL } = require("url");

class SafetyStream {
  constructor(server = "http://localhost:9999") {
    this.url = new URL("/emit", server);
  }

  _emit(event) {
    const body = JSON.stringify(event);
    const opts = {
      method: "POST",
      hostname: this.url.hostname,
      port: this.url.port,
      path: this.url.pathname,
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    };
    return new Promise((resolve) => {
      const req = http.request(opts, (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      });
      req.on("error", () => resolve(false));
      req.write(body);
      req.end();
    });
  }

  input(message) {
    return this._emit({ type: "input_received", message });
  }
  layerStart(layer, name) {
    return this._emit({ type: "layer_start", layer, data: { name } });
  }
  layerProgress(layer, percent) {
    return this._emit({ type: "layer_progress", layer, data: { percent } });
  }
  layerComplete(layer, decision, executionTimeMs) {
    return this._emit({
      type: "layer_complete",
      layer,
      data: { decision, execution_time_ms: executionTimeMs },
    });
  }
  output(message) {
    return this._emit({ type: "output_ready", message });
  }
}

module.exports = { SafetyStream };

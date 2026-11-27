// Tests for the Node.js emitter. Standard library only (http, assert).
// Pins the exact JSON each method posts, against the schema the README documents.
//
//   node clients/js/safety-stream.test.js
"use strict";

const assert = require("assert");
const http = require("http");
const { SafetyStream } = require("./safety-stream");

let last = null;
const server = http.createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    last = JSON.parse(body);
    res.statusCode = 200;
    res.end();
  });
});

async function main() {
  await new Promise((r) => server.listen(0, "localhost", r));
  const port = server.address().port;
  const ss = new SafetyStream(`http://localhost:${port}`);

  await ss.input("hi");
  assert.deepStrictEqual(last, { type: "input_received", message: "hi" });

  await ss.layerStart(1, "Safety Check");
  assert.deepStrictEqual(last, { type: "layer_start", layer: 1, data: { name: "Safety Check" } });

  await ss.layerProgress(1, 100);
  assert.deepStrictEqual(last, { type: "layer_progress", layer: 1, data: { percent: 100 } });

  await ss.layerComplete(1, "credential_exfil_request_FLAGGED", 11);
  assert.deepStrictEqual(last, {
    type: "layer_complete",
    layer: 1,
    data: { decision: "credential_exfil_request_FLAGGED", execution_time_ms: 11 },
  });

  await ss.output("RED: declined");
  assert.deepStrictEqual(last, { type: "output_ready", message: "RED: declined" });

  assert.strictEqual(new SafetyStream().url.href, "http://localhost:9999/emit");

  server.close();
  console.log("ok - node client tests passed");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

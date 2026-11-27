/**
 * Deep check of the animated SVG inside <img>.
 *
 * Removes two confounders that could explain a "frozen" frame:
 *   1. prefers-reduced-motion  -> pinned to no-preference explicitly
 *   2. background/occluded tab -> target explicitly activated
 *
 * Then samples a block ROI every 400ms. A genuinely running animation gives
 * a long run of distinct states; a throttled or frozen raster gives few.
 */
import { writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const PORT = process.env.CDP_PORT || '9222';
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const OUT = process.env.OUT_DIR || '/tmp';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function openSocket(url) {
  const ws = new WebSocket(url);
  const ok = await Promise.race([
    new Promise((r) => { ws.onopen = () => r(true); ws.onerror = () => r(false); }),
    new Promise((r) => setTimeout(() => r(false), 5000)),
  ]);
  if (!ok) throw new Error('socket failed');
  return ws;
}

function rpc(ws, method, params = {}, timeout = 20000) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 1e9);
    const h = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === id) { ws.removeEventListener('message', h); clearTimeout(t);
        m.error ? reject(new Error(`${method}: ${JSON.stringify(m.error)}`)) : resolve(m.result); }
    };
    ws.addEventListener('message', h);
    const t = setTimeout(() => { ws.removeEventListener('message', h);
      reject(new Error(`${method} TIMEOUT`)); }, timeout);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

const hash = (b64) => createHash('sha1').update(b64).digest('hex').slice(0, 10);

const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const target = list.find((t) => t.type === 'page');
const bws = await openSocket((await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json()).webSocketDebuggerUrl);
await rpc(bws, 'Target.activateTarget', { targetId: target.id }).catch(() => {});

const ws = await openSocket(target.webSocketDebuggerUrl);
await rpc(ws, 'Page.enable');
await rpc(ws, 'Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
});

let loaded = false;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Page.loadEventFired') loaded = true;
});
await rpc(ws, 'Page.navigate', { url: `${BASE}/test_anim.html` });
for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
await sleep(500);

const clip = (x, y, w, h) => ({ x, y, width: w, height: h, scale: 1 });
const ROIS = {
  block_00: clip(44, 132, 192, 66),
  block_04: clip(284, 227, 192, 66),
  static:   clip(44, 100, 192, 16),
};

const seq = {}; for (const k of Object.keys(ROIS)) seq[k] = [];
const t0 = Date.now();
const samples = 24;
for (let i = 0; i < samples; i++) {
  for (const [k, c] of Object.entries(ROIS)) seq[k].push(hash(await rpc(ws, 'Page.captureScreenshot', { clip: c, format: 'png' }).then(r => r.data)));
  if (i === 4 || i === 12) {
    const { data } = await rpc(ws, 'Page.captureScreenshot', { clip: clip(0, 95, 1000, 300), format: 'png' });
    writeFileSync(`${OUT}/deep_frame_${i}.png`, Buffer.from(data, 'base64'));
  }
  await sleep(400);
}
const elapsed = (Date.now() - t0) / 1000;

const out = { elapsed_s: round1(elapsed), samples };
for (const k of Object.keys(ROIS)) {
  out[k] = { distinct: new Set(seq[k]).size, seq: seq[k] };
}
console.log(JSON.stringify(out, null, 2));
ws.close(); bws.close();

function round1(n) { return Math.round(n * 10) / 10; }

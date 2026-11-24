/**
 * Does the auto-sweep highlight actually run inside <img> (the README case)?
 *
 * Sample one block's pixels once per second for a full 15.6s cycle and hash
 * each frame. If the highlight works, the same block must render in at least
 * two distinct states (lit / dimmed). A static control strip proves the
 * sampler is not just picking up noise.
 */
import { writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const PORT = process.env.CDP_PORT || '9222';
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const OUT = process.env.OUT_DIR || '/tmp';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function openSocket(url) {
  const ws = new WebSocket(url);
  const res = await Promise.race([
    new Promise((r) => { ws.onopen = () => r('open'); ws.onerror = () => r('error'); }),
    new Promise((r) => setTimeout(() => r('timeout'), 5000)),
  ]);
  if (res !== 'open') throw new Error(`socket ${res}`);
  return ws;
}

function rpc(ws, method, params = {}, timeout = 15000) {
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

async function navigate(ws, url) {
  let loaded = false;
  const h = (ev) => { const m = JSON.parse(ev.data); if (m.method === 'Page.loadEventFired') loaded = true; };
  ws.addEventListener('message', h);
  await rpc(ws, 'Page.navigate', { url });
  for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
  ws.removeEventListener('message', h);
  await sleep(500);
}

const shot = async (ws, clip) =>
  (await rpc(ws, 'Page.captureScreenshot', { clip, format: 'png' })).data;

const hash = (b64) => createHash('sha1').update(b64).digest('hex').slice(0, 10);

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const target = list.find((t) => t.type === 'page');
  const ws = await openSocket(target.webSocketDebuggerUrl);
  await rpc(ws, 'Page.enable');

  const clip = (x, y, w, h) => ({ x, y, width: w, height: h, scale: 1 });
  const ROIS = {
    block_00_input_protection: clip(44, 132, 192, 66),  // lights first
    block_04_motor_driver:     clip(284, 227, 192, 66),  // lights mid-cycle
    band_label_static:         clip(44, 100, 192, 16),   // never animates
  };

  await navigate(ws, `${BASE}/test_anim.html`);
  const report = { url: `${BASE}/test_anim.html`, samples: {}, frames: [] };

  const per = {};
  for (const k of Object.keys(ROIS)) per[k] = [];

  for (let i = 0; i < 16; i++) {
    const row = {};
    for (const [k, c] of Object.entries(ROIS)) {
      const h = hash(await shot(ws, c));
      per[k].push(h);
      row[k] = h;
    }
    report.frames.push(row);
    if (i === 0 || i === 1) {
      writeFileSync(`${OUT}/sweep_frame_${i}.png`,
        Buffer.from(await shot(ws, clip(0, 95, 1000, 300)), 'base64'));
    }
    await sleep(1000);
  }

  for (const k of Object.keys(ROIS)) {
    report.samples[k] = {
      distinct_states: new Set(per[k]).size,
      sequence: per[k],
    };
  }

  console.log(JSON.stringify(report, null, 2));
  ws.close();
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });

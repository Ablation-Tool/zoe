/**
 * Does ANIMATION survive <img> embedding (the GitHub README case)?
 *
 * :hover was already proven dead inside <img>. This asks the other question:
 * do CSS @keyframes still run there? That decides whether an auto-cycling
 * highlight is even possible in a README.
 *
 * Method: screenshot a region at t and at t+delta, byte-compare.
 *   - animated region must CHANGE
 *   - a deliberately static region must stay IDENTICAL (control)
 */
import { writeFileSync } from 'node:fs';

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
  if (res !== 'open') throw new Error(`socket ${res} for ${url}`);
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
  await sleep(800);
  return loaded;
}

const shot = async (ws, clip) =>
  (await rpc(ws, 'Page.captureScreenshot', { clip, format: 'png' })).data;

// pick a fresh page target that is not a devtools/blank page
async function pickTarget() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find((t) => t.type === 'page');
  if (!page) throw new Error('no page target available');
  return page;
}

async function main() {
  const target = await pickTarget();
  const ws = await openSocket(target.webSocketDebuggerUrl);
  await rpc(ws, 'Page.enable');
  await rpc(ws, 'Runtime.enable');

  const clip = (x, y, w, h) => ({ x, y, width: w, height: h, scale: 1 });
  const ROIS = {
    flow_arrow_1: clip(248, 150, 30, 30),   // animated dash + arrow, col0->col1
    flow_arrow_2: clip(488, 150, 30, 30),   // animated dash + arrow, col1->col2
    block_fill:   clip(300, 130, 180, 60),  // static block interior (control)
  };

  const report = { target: target.url, base: BASE };

  for (const [mode, url] of [
    ['standalone', `${BASE}/block-diagram.svg`],
    ['img_embed',  `${BASE}/test_img.html`],
  ]) {
    await navigate(ws, url);
    const a = {}, b = {};
    for (const [k, c] of Object.entries(ROIS)) a[k] = await shot(ws, c);
    await sleep(400);                       // ~1/3 of the 1.1s dash cycle
    for (const [k, c] of Object.entries(ROIS)) b[k] = await shot(ws, c);

    report[mode] = {};
    for (const k of Object.keys(ROIS)) report[mode][k] = { changed: a[k] !== b[k] };

    // keep the animated frame pair as evidence
    writeFileSync(`${OUT}/anim_${mode}_t0.png`, Buffer.from(a.flow_arrow_1, 'base64'));
    writeFileSync(`${OUT}/anim_${mode}_t1.png`, Buffer.from(b.flow_arrow_1, 'base64'));
  }

  console.log(JSON.stringify(report, null, 2));
  ws.close();
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });

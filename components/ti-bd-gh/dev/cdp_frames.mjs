/** Grab full-diagram frames from the <img> context so we can eyeball them. */
import { writeFileSync } from 'node:fs';

const PORT = process.env.CDP_PORT || '9222';
const PAGE_URL = process.env.PAGE_URL || 'http://127.0.0.1:8099/test_anim.html';
const PREFIX = process.env.PREFIX || '/tmp/frame';
const N = Number(process.env.N || 4);
const GAP = Number(process.env.GAP || 1500);
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

function rpc(ws, method, params = {}, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 1e9);
    const h = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === id) { ws.removeEventListener('message', h); clearTimeout(t);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result); }
    };
    ws.addEventListener('message', h);
    const t = setTimeout(() => { ws.removeEventListener('message', h); reject(new Error('TIMEOUT')); }, timeout);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const target = list.find((t) => t.type === 'page');
const ws = await openSocket(target.webSocketDebuggerUrl);
await rpc(ws, 'Page.enable');

let loaded = false;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Page.loadEventFired') loaded = true;
});
await rpc(ws, 'Page.navigate', { url: PAGE_URL });
for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
await sleep(600);

for (let i = 0; i < N; i++) {
  const { data } = await rpc(ws, 'Page.captureScreenshot', {
    clip: { x: 0, y: 0, width: 1000, height: 600, scale: 1 }, format: 'png',
  });
  writeFileSync(`${PREFIX}_${i}.png`, Buffer.from(data, 'base64'));
  await sleep(GAP);
}
console.log('frames written:', N);
ws.close();

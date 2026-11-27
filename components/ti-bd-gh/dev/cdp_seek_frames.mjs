/**
 * Deterministic visual check: pause the sweep and seek it to fixed times.
 *
 * Screenshots race the animation clock, so instead we drive the clock. The
 * CSS is identical to the <img> variant, so this shows exactly what a README
 * viewer sees at each point in the 15.6s cycle.
 */
import { writeFileSync } from 'node:fs';

const PORT = process.env.CDP_PORT || '9222';
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
const OUT = process.env.OUT_DIR || '/tmp';
const FILE = process.env.FILE || 'block-diagram-animated.svg';
const THEME = process.env.THEME || 'light';
const TIMES = (process.env.TIMES || '600,5400,10200,14500').split(',').map(Number);
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

const evaluate = async (ws, expression) => {
  const r = await rpc(ws, 'Runtime.evaluate', { expression, returnByValue: true });
  if (r.exceptionDetails) throw new Error('JS error: ' + JSON.stringify(r.exceptionDetails));
  return r.result.value;
};

const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const target = list.find((t) => t.type === 'page');
const ws = await openSocket(target.webSocketDebuggerUrl);
await rpc(ws, 'Page.enable');
await rpc(ws, 'Runtime.enable');
await rpc(ws, 'Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
});

let loaded = false;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Page.loadEventFired') loaded = true;
});
await rpc(ws, 'Page.navigate', { url: `${BASE}/${FILE}` });
for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
await sleep(400);

const result = {};
for (const t of TIMES) {
  const info = await evaluate(ws, `(() => {
    const a = document.getAnimations();
    a.forEach(x => { x.pause(); x.currentTime = ${t}; });
    const rows = [...document.querySelectorAll('.bd-subsystem')].map(g => {
      const box = g.querySelector('.bd-box');
      const cs = getComputedStyle(box);
      const gs = getComputedStyle(g);
      return g.dataset.subsystem + ':' + parseFloat(cs.strokeWidth).toFixed(1)
           + '/' + gs.opacity;
    });
    const lit = rows.filter(r => parseFloat(r.split(':')[1]) > 1.9).map(r => r.split(':')[0]);
    return { seeking: a.length, lit, rows };
  })()`);
  await sleep(250);
  const { data } = await rpc(ws, 'Page.captureScreenshot', {
    clip: { x: 0, y: 0, width: 1000, height: 600, scale: 1 }, format: 'png',
  });
  const name = `${OUT}/seek_${THEME}_${t}.png`;
  writeFileSync(name, Buffer.from(data, 'base64'));
  result[`t=${t}ms`] = { ...info, frame: name };
}

console.log(JSON.stringify(result, null, 2));
ws.close();

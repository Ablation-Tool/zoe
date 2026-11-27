/**
 * Read the engine's own view of the sweep animation.
 *
 * Loaded as a standalone SVG *document* (not <img>), getAnimations() is
 * reachable, so we can read the real duration/delay per block and measure the
 * playback rate against wall-clock time. That separates "my CSS is wrong"
 * from "headless screenshot cadence is a bad clock".
 */
const PORT = process.env.CDP_PORT || '9222';
const BASE = process.env.BASE || 'http://127.0.0.1:8099';
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
await rpc(ws, 'Page.navigate', { url: `${BASE}/block-diagram-animated.svg` });
for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
await sleep(400);

const PROBE = `(() => {
  const anims = document.getAnimations();
  const groups = [...document.querySelectorAll('.bd-subsystem')];
  const detail = groups.map((g, i) => {
    const a = g.getAnimations({ subtree: true })
      .map(x => ({ name: x.animationName, delay: x.effect.getTiming().delay,
                   dur: x.effect.getTiming().duration, iter: x.effect.getTiming().iterations,
                   t: Math.round(x.currentTime) }));
    return { i, id: g.dataset.subsystem, anims: a };
  });
  return {
    total_animations: anims.length,
    reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    groups: groups.length,
    detail,
  };
})()`;

const first = await evaluate(ws, PROBE);
const t0 = Date.now();
await sleep(3000);
const second = await evaluate(ws, PROBE);

// playback rate: how far did each animation's currentTime actually advance?
const rates = first.detail.map((g, i) => {
  const a = g.anims.find(x => x.name === 'bd-dim');
  const b = second.detail[i].anims.find(x => x.name === 'bd-dim');
  if (!a || !b) return null;
  return { id: g.id, advanced_s: Math.round((b.t - a.t)) / 1000 };
});

console.log(JSON.stringify({
  reduced_motion: first.reduced_motion,
  total_animations: first.total_animations,
  group_count: first.groups,
  wall_clock_gap_s: Math.round((Date.now() - t0)) / 1000,
  first_block: first.detail[0],
  second_block: second.detail[0],
  last_block: first.detail[first.detail.length - 1],
  rates,
}, null, 2));

ws.close();

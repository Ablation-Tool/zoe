/**
 * Functional test of interactive/index.html (the GitHub Pages build).
 *
 * Inline SVG is where the real interaction lives, so this checks the three
 * things a README cannot do:
 *   1. :hover  -> hovered block gets the accent treatment, siblings dim
 *   2. click   -> block is pinned and the detail panel updates
 *   3. theme   -> toggling swaps in the dark SVG
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
  media: 'screen',
});
await rpc(ws, 'Emulation.setDeviceMetricsOverride', {
  width: 1400, height: 900, deviceScaleFactor: 1, mobile: false,
});

let loaded = false;
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Page.loadEventFired') loaded = true;
});
await rpc(ws, 'Page.navigate', { url: `${BASE}/interactive/index.html` });
for (let i = 0; i < 80 && !loaded; i++) await sleep(100);
await sleep(500);

const out = {};

out.structure = await evaluate(ws, `(() => ({
  blocks: document.querySelectorAll('.bd-subsystem').length,
  list_items: document.querySelectorAll('.item').length,
  svg_inline: !!document.querySelector('#stage svg'),
  theme: document.documentElement.dataset.theme,
}))()`);

// rect of the block we will poke, in viewport coordinates
const rectOf = (id) => evaluate(ws, `(() => {
  const g = document.querySelector('.bd-subsystem[data-subsystem="${id}"]');
  const r = g.getBoundingClientRect();
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
})()`);

const styleOf = (id) => evaluate(ws, `(() => {
  const g = document.querySelector('.bd-subsystem[data-subsystem="${id}"]');
  const box = g.querySelector('.bd-box');
  return { opacity: getComputedStyle(g).opacity,
           stroke: getComputedStyle(box).stroke,
           fill: getComputedStyle(box).fill,
           label: getComputedStyle(g.querySelector('.bd-label')).fill };
})()`);

out.before_hover = { sensors: await styleOf('sensors'), sibling: await styleOf('motor') };

const p = await rectOf('sensors');
await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseMoved', x: p.x, y: p.y, buttons: 0 });
await sleep(500);

out.after_hover = { sensors: await styleOf('sensors'), sibling: await styleOf('motor') };
out.panel_on_hover = await evaluate(ws, `document.querySelector('#info h2').textContent`);

// click to pin
await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mousePressed', x: p.x, y: p.y, button: 'left', clickCount: 1 });
await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x: p.x, y: p.y, button: 'left', clickCount: 1 });
await sleep(400);
out.after_click = {
  panel_h2: await evaluate(ws, `document.querySelector('#info h2').textContent`),
  panel_p: await evaluate(ws, `document.querySelector('#info p').textContent`),
  pinned_item: await evaluate(ws,
    `document.querySelector('.item[aria-current="true"]')?.dataset.id || null`),
};

// theme toggle
await evaluate(ws, `document.getElementById('theme').click()`);
await sleep(400);
out.after_theme_toggle = await evaluate(ws, `(() => ({
  theme: document.documentElement.dataset.theme,
  button: document.getElementById('theme').textContent,
  pinned_still: document.querySelector('.item[aria-current="true"]')?.dataset.id || null,
  blocks: document.querySelectorAll('.bd-subsystem').length,
}))()`);

console.log(JSON.stringify(out, null, 2));
ws.close();

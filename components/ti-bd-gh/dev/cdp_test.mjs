/**
 * Verify, in a real browser, that the diagram's CSS interaction works BOTH
 * standalone AND when embedded via <img> (the GitHub README case).
 *
 * Node built-ins only. Every CDP call has a hard timeout so it cannot hang.
 *
 * Controlled experiment:
 *   hovered block -> pixels CHANGE (tint + accent border)
 *   sibling block -> pixels CHANGE (dims to opacity .32)
 *   control region-> pixels IDENTICAL (nothing should move)
 */
import { writeFileSync } from 'node:fs';

const PORT = process.env.CDP_PORT || '9222';
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
  await sleep(600);
  return loaded;
}

const evaluate = async (ws, expression) => {
  const r = await rpc(ws, 'Runtime.evaluate', { expression, returnByValue: true });
  if (r.exceptionDetails) throw new Error('JS error: ' + JSON.stringify(r.exceptionDetails));
  return r.result.value;
};

const shot = async (ws, clip) =>
  (await rpc(ws, 'Page.captureScreenshot', clip ? { clip, format: 'png' } : { format: 'png' })).data;

async function main() {
  const ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
  const bws = await openSocket(ver.webSocketDebuggerUrl);

  // make sure we have our own fresh tab
  const { targetId } = await rpc(bws, 'Target.createTarget', { url: 'about:blank' });
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const target = list.find((t) => t.id === targetId);
  if (!target) throw new Error('new target not found in /json/list');
  const ws = await openSocket(target.webSocketDebuggerUrl);
  await rpc(ws, 'Page.enable');
  await rpc(ws, 'Runtime.enable');
  await rpc(bws, 'Target.activateTarget', { targetId });

  const report = {};

  // ---------- PART A: SVG standalone (DOM inspectable) --------------------
  {
    await navigate(ws, 'http://127.0.0.1:8099/block-diagram.svg');
    const probe = () => evaluate(ws, `(() => {
      const g = (id) => document.querySelector('g[data-subsystem="'+id+'"]');
      const op = (id) => g(id) ? getComputedStyle(g(id)).opacity : 'MISSING';
      const st = (id) => g(id) ? getComputedStyle(g(id).querySelector('rect')).stroke : 'MISSING';
      const fl = (id) => g(id) ? getComputedStyle(g(id).querySelector('rect')).fill : 'MISSING';
      return { hovered_opacity: op('input-protection'),
               sibling_opacity: op('power-stage'),
               far_opacity:     op('user-interface'),
               controller_opacity: op('system-controller'),
               hovered_stroke:  st('input-protection'),
               hovered_fill:    fl('input-protection'),
               sibling_stroke:  st('power-stage'),
               rule_count: [...document.styleSheets].flatMap(ss => {
                 try { return [...ss.cssRules]; } catch(e){ return []; } }).length,
               has_has_selector: [...document.styleSheets].flatMap(ss => {
                 try { return [...ss.cssRules].map(r => r.cssText); } catch(e){ return []; }
               }).some(t => t.includes(':has(')) };
    })()`);

    report.A_standalone_at_rest = await probe();
    await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseMoved', x: 140, y: 165, buttons: 0 });
    await sleep(700);
    report.A_standalone_hovering_block = await probe();
    writeFileSync(`${OUT}/cdp_standalone_hover.png`, Buffer.from(await shot(ws), 'base64'));
  }

  // ---------- PART B: embedded via <img> (GitHub README case) -------------
  {
    await navigate(ws, 'http://127.0.0.1:8099/test_img.html');
    report.B_img_box = await evaluate(ws, `(() => {
      const el = document.getElementById('diagram');
      const r = el.getBoundingClientRect();
      return { x:r.x, y:r.y, w:r.width, h:r.height,
               natural: el.naturalWidth + 'x' + el.naturalHeight };
    })()`);

    const clip = (x, y, w, h) => ({ x, y, width: w, height: h, scale: 1 });
    const ROIS = {
      hovered_block: clip(42, 130, 196, 70),
      sibling_block: clip(282, 130, 196, 70),
      control_area:  clip(360, 545, 300, 30),
    };

    const base = {}, hov = {};
    for (const [k, c] of Object.entries(ROIS)) base[k] = await shot(ws, c);
    writeFileSync(`${OUT}/cdp_img_rest.png`, Buffer.from(await shot(ws), 'base64'));

    await rpc(ws, 'Input.dispatchMouseEvent', { type: 'mouseMoved', x: 140, y: 165, buttons: 0 });
    await sleep(700);

    for (const [k, c] of Object.entries(ROIS)) hov[k] = await shot(ws, c);
    writeFileSync(`${OUT}/cdp_img_hover.png`, Buffer.from(await shot(ws), 'base64'));

    report.B_img_embed = {};
    for (const k of Object.keys(ROIS)) report.B_img_embed[k] = { changed: base[k] !== hov[k] };

    for (const k of Object.keys(ROIS)) {
      writeFileSync(`${OUT}/roi_${k}_base.png`, Buffer.from(base[k], 'base64'));
      writeFileSync(`${OUT}/roi_${k}_hover.png`, Buffer.from(hov[k], 'base64'));
    }
  }

  console.log(JSON.stringify(report, null, 2));
  ws.close(); bws.close();
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });

/** Minimal diagnostic: confirm we can list targets and open a page socket. */
const PORT = process.env.CDP_PORT || '9222';
const log = (...a) => console.log('[probe]', ...a);

log('fetching /json/version');
const ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
log('browser ws:', ver.webSocketDebuggerUrl);

log('fetching /json/list');
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
log('targets:', list.map((t) => `${t.type} ${t.url}`));

const page = list.find((t) => t.type === 'page');
log('chosen page ws:', page && page.webSocketDebuggerUrl);

const ws = new WebSocket(page.webSocketDebuggerUrl);
const opened = await Promise.race([
  new Promise((r) => { ws.onopen = () => r('open'); ws.onerror = (e) => r('error:' + e.message); }),
  new Promise((r) => setTimeout(() => r('TIMEOUT'), 5000)),
]);
log('socket result:', opened);
if (opened !== 'open') process.exit(1);

const rpc = (method, params = {}) => new Promise((resolve, reject) => {
  const id = Math.floor(Math.random() * 1e9);
  const h = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id === id) { ws.removeEventListener('message', h); m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result); }
  };
  ws.addEventListener('message', h);
  ws.send(JSON.stringify({ id, method, params }));
  setTimeout(() => reject(new Error(method + ' TIMEOUT')), 8000);
});

log('Page.enable ->', JSON.stringify(await rpc('Page.enable')));
log('Runtime.enable ->', JSON.stringify(await rpc('Runtime.enable')));
const v = await rpc('Runtime.evaluate', { expression: '1+1', returnByValue: true });
log('Runtime.evaluate 1+1 ->', JSON.stringify(v.result));
log('navigate ->', JSON.stringify(await rpc('Page.navigate', { url: 'http://127.0.0.1:8099/test_img.html' })));
await new Promise((r) => setTimeout(r, 1500));
const box = await rpc('Runtime.evaluate', {
  expression: `(()=>{const e=document.getElementById('diagram');if(!e)return 'NO IMG';const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,natural:e.naturalWidth+'x'+e.naturalHeight};})()`,
  returnByValue: true,
});
log('img box ->', JSON.stringify(box.result.value));
const s = await rpc('Page.captureScreenshot', { format: 'png' });
log('screenshot bytes ->', s.data.length);
ws.close();
log('DONE');

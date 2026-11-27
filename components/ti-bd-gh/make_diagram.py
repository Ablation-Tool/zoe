#!/usr/bin/env python3
"""
Generate TI-style block diagrams that actually behave on GitHub.

Everything that makes TI's diagram feel alive is CSS *inside the SVG file*.
That matters because a GitHub README embeds the diagram as
`<img src="block-diagram.svg">`, and inside an <img>:

    JavaScript .......... never runs
    :hover / :focus ..... never fires
    CSS @keyframes ...... STILL RUNS   <-- verified in Chrome via CDP
    SMIL <animate> ...... STILL RUNS

So there are two variants, picked by where the diagram will live:

  block-diagram.svg            static + hover-to-isolate
      -> works when the SVG is *inline* (GitHub Pages, docs site, any <object>)

  block-diagram-animated.svg   self-running highlight sweep
      -> the one to use in a README, where hover is impossible

Both keep the animated power-flow dashes, which work everywhere.
"""

import json
import os

CANVAS_W, CANVAS_H = 1000, 600
FONT = '"Helvetica Neue",Helvetica,Arial,sans-serif'

PALETTES = {
    "light": dict(
        bg="#f4f4f4", band="#e9e9e9", band_text="#8c8c8c",
        block="#ffffff", stroke="#d6d6d6", label="#262626", sub="#8c8c8c",
        accent="#c8102e", tint="#fdf2f4",
        conn="#bdbdbd", flow="#c8102e",
        ctrl_fill="#ffffff", ctrl_stroke="#c8102e",
        footer="#9a9a9a",
    ),
    "dark": dict(
        bg="#0d1117", band="#161b22", band_text="#7d8590",
        block="#21262d", stroke="#30363d", label="#e6edf3", sub="#8b949e",
        accent="#f85149", tint="#2a1216",
        conn="#484f58", flow="#f85149",
        ctrl_fill="#161b22", ctrl_stroke="#f85149",
        footer="#6e7681",
    ),
}

# ---- layout ----------------------------------------------------------------
COL_X = [30, 270, 510, 750]
COL_W = 220
ROW_Y = [130, 225, 320]
ROW_H = 70
CTRL_TOP = 450

BANDS = [
    ("AC Input &amp; Power Conversion", 0),
    ("Power Stage &amp; Motor", 1),
    ("Sensing &amp; Signal Chain", 2),
    ("Connectivity &amp; HMI", 3),
]

# (col, row, id, label, sublabel)
BLOCKS = [
    (0, 0, "input-protection",   "Input Power Protection",     "TVS / eFuse / hot-swap"),
    (0, 1, "acdc-noniso",        "Non-isolated AC/DC",         "Buck, boost, LDO"),
    (0, 2, "acdc-iso",           "Isolated AC/DC",             "Flyback, LLC, PSR"),

    (1, 0, "power-stage",        "Power Stage",                "3-phase inverter"),
    (1, 1, "motor-driver",       "Motor Driver",               "Gate driver / IPM"),
    (1, 2, "motor",              "Motor &amp; Actuators",      "BLDC / PMSM / valve"),

    (2, 0, "current-sense",      "Current &amp; Voltage Sense", "Shunt, Hall, fluxgate"),
    (2, 1, "analog-front-end",   "Analog Front End",           "Op-amp, PGA, ADC"),
    (2, 2, "sensors",            "Sensors",                    "Temp, humidity, level"),

    (3, 0, "wired-interface",    "Wired Interface",            "CAN, RS-485, UART"),
    (3, 1, "wireless-interface", "Wireless Interface",         "Wi-Fi, BLE, Sub-1 GHz"),
    (3, 2, "user-interface",     "Input / Output UI",          "Touch, LED, display"),
]

CONTROLLER = ("system-controller", "System Controller (MCU)",
              "real-time control  |  safety  |  connectivity stack")

# ---- animation timing ------------------------------------------------------
STEP = 1.2                      # seconds each block stays lit
COUNT = len(BLOCKS) + 1         # 12 subsystems + controller
CYCLE = round(STEP * COUNT, 3)  # 15.6s
W = 100.0 / COUNT               # 7.6923% of the cycle per block
DIM = 0.6                       # non-highlighted opacity: a spotlight, not a blackout


def _styles(theme, animated):
    p = PALETTES[theme]
    o = []
    a = o.append

    a(f'.bd-bg{{fill:{p["bg"]}}}')
    a(f'.bd-band{{fill:{p["band"]}}}')
    a(f'.bd-band-label{{fill:{p["band_text"]};font:600 10.5px {FONT};letter-spacing:1.1px}}')
    a(f'.bd-footer{{fill:{p["footer"]};font:400 11px {FONT}}}')
    a(f'.bd-conn-dash{{stroke:{p["conn"]};stroke-width:1.4;fill:none;stroke-dasharray:4 4}}')
    a(f'.bd-flow{{stroke:{p["flow"]};stroke-width:1.6;fill:none;stroke-dasharray:6 4;'
      f'animation:bd-dash 1.1s linear infinite}}')
    a('@keyframes bd-dash{to{stroke-dashoffset:-20}}')
    a(f'.bd-arrow-flow{{fill:{p["flow"]}}}')

    a(f'.bd-nodes .bd-box{{fill:{p["block"]};stroke:{p["stroke"]};stroke-width:1.2;'
      f'transition:fill .18s ease-in-out,stroke .18s ease-in-out,stroke-width .18s ease-in-out}}')
    a(f'.bd-nodes .bd-label{{fill:{p["label"]};font:600 12.5px {FONT};'
      f'transition:fill .18s ease-in-out}}')
    a(f'.bd-nodes .bd-sub{{fill:{p["sub"]};font:400 10px {FONT};'
      f'transition:fill .18s ease-in-out}}')
    a(f'.bd-nodes .bd-controller .bd-box{{stroke:{p["ctrl_stroke"]};stroke-width:1.6}}')
    a('.bd-nodes .bd-controller .bd-label{font-size:14px}')
    a('.bd-nodes .bd-controller .bd-sub{font-size:10.5px}')
    a('.bd-nodes .bd-subsystem{opacity:1}')

    if not animated:
        # ---------- INTERACTION: pure CSS, no JavaScript -------------------
        # :has() lets one hovered child dim all of its siblings. Only works
        # when the SVG is inline; an <img> never dispatches :hover inward.
        a(f'.bd-nodes .bd-subsystem{{transition:opacity .18s ease-in-out}}')
        a('.bd-nodes .bd-subsystem:hover{cursor:pointer}')
        a('.bd-nodes:has(.bd-subsystem:hover) .bd-subsystem{opacity:.32}')
        a('.bd-nodes:has(.bd-subsystem:hover) .bd-subsystem:hover{opacity:1}')
        a(f'.bd-nodes:has(.bd-subsystem:hover) .bd-subsystem:hover .bd-box'
          f'{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:2.2}}')
        a(f'.bd-nodes:has(.bd-subsystem:hover) .bd-subsystem:hover .bd-label'
          f'{{fill:{p["accent"]}}}')
        a(f'.bd-nodes .bd-subsystem:focus-visible .bd-box'
          f'{{stroke:{p["accent"]};stroke-width:2.2}}')
        a('@media (prefers-reduced-motion:reduce){.bd-flow{animation:none}}')
    else:
        # ---------- AUTO-SWEEP: the README-compatible version --------------
        # One shared keyframe set, shifted per block with a NEGATIVE
        # animation-delay. A negative delay starts the element mid-cycle, so
        # block i's "lit" window lands exactly at t = i * STEP and the light
        # walks across the diagram in reading order, forever, with no JS.
        hi, rest = round(W * 0.55, 4), round(W * 1.15, 4)

        a(f'@keyframes bd-dim{{0%{{opacity:1}}{hi}%{{opacity:1}}'
          f'{rest}%{{opacity:{DIM}}}96%{{opacity:{DIM}}}100%{{opacity:1}}}}')
        a(f'@keyframes bd-box-hi{{0%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:2.4}}'
          f'{hi}%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:2.4}}'
          f'{rest}%{{fill:{p["block"]};stroke:{p["stroke"]};stroke-width:1.2}}'
          f'96%{{fill:{p["block"]};stroke:{p["stroke"]};stroke-width:1.2}}'
          f'100%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:2.4}}}}')
        a(f'@keyframes bd-label-hi{{0%{{fill:{p["accent"]}}}{hi}%{{fill:{p["accent"]}}}'
          f'{rest}%{{fill:{p["label"]}}}96%{{fill:{p["label"]}}}'
          f'100%{{fill:{p["accent"]}}}}}')
        # the controller rests on an accent border, so it needs its own pair
        a(f'@keyframes bd-box-hi-ctrl{{0%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:3}}'
          f'{hi}%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:3}}'
          f'{rest}%{{fill:{p["ctrl_fill"]};stroke:{p["ctrl_stroke"]};stroke-width:1.6}}'
          f'96%{{fill:{p["ctrl_fill"]};stroke:{p["ctrl_stroke"]};stroke-width:1.6}}'
          f'100%{{fill:{p["tint"]};stroke:{p["accent"]};stroke-width:3}}}}')

        # animation-delay is NOT inherited, so the offset travels through a
        # custom property (which does inherit) declared on the group.
        a(f'.bd-nodes .bd-subsystem{{animation:bd-dim {CYCLE}s linear infinite;'
          f'animation-delay:var(--d,0s)}}')
        a(f'.bd-nodes .bd-subsystem .bd-box{{animation:bd-box-hi {CYCLE}s linear infinite;'
          f'animation-delay:var(--d,0s)}}')
        a(f'.bd-nodes .bd-subsystem .bd-label{{animation:bd-label-hi {CYCLE}s linear infinite;'
          f'animation-delay:var(--d,0s)}}')
        a(f'.bd-nodes .bd-controller .bd-box'
          f'{{animation:bd-box-hi-ctrl {CYCLE}s linear infinite;animation-delay:var(--d,0s)}}')
        a('@media (prefers-reduced-motion:reduce){'
          '.bd-flow,.bd-subsystem,.bd-subsystem .bd-box,.bd-subsystem .bd-label'
          '{animation:none}}')

    return o


def build_svg(theme, animated=False):
    p = PALETTES[theme]
    o = []
    a = o.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W} {CANVAS_H}" '
      f'width="{CANVAS_W}" height="{CANVAS_H}" role="img" '
      f'aria-label="Washer and dryer system block diagram">')

    a('<style>')
    for line in _styles(theme, animated):
        a(line)
    a('</style>')

    a(f'<rect class="bd-bg" x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}"/>')

    for name, col in BANDS:
        x = COL_X[col]
        a(f'<rect class="bd-band" x="{x}" y="95" width="{COL_W}" height="325" rx="10"/>')
        a(f'<text class="bd-band-label" x="{x + 14}" y="118">{name}</text>')

    # connectors sit behind the blocks
    for i in range(3):
        x1 = COL_X[i] + COL_W
        x2 = COL_X[i + 1]
        y = ROW_Y[0] + ROW_H / 2
        a(f'<line class="bd-flow" x1="{x1}" y1="{y}" x2="{x2 - 7}" y2="{y}"/>')
        a(f'<path class="bd-arrow-flow" d="M{x2 - 7} {y - 4.5} L{x2 - 0.5} {y} L{x2 - 7} {y + 4.5} Z"/>')

    for col in range(4):
        cx = COL_X[col] + COL_W / 2
        a(f'<line class="bd-conn-dash" x1="{cx}" y1="420" x2="{cx}" y2="{CTRL_TOP}"/>')

    a('<g class="bd-nodes">')
    for i, (col, row, sid, label, sub) in enumerate(BLOCKS):
        x, y = COL_X[col], ROW_Y[row]
        delay = f' style="--d:-{round(i * STEP, 3)}s"' if animated else ''
        a(f'<g class="bd-subsystem" data-subsystem="{sid}" tabindex="0" '
          f'aria-label="{label}"{delay}>')
        a(f'<title>{label} — {sub}</title>')
        a(f'<rect class="bd-box" x="{x + 12}" y="{y}" width="{COL_W - 24}" height="{ROW_H}" rx="8"/>')
        a(f'<text class="bd-label" x="{x + COL_W / 2}" y="{y + 30}" text-anchor="middle">{label}</text>')
        a(f'<text class="bd-sub" x="{x + COL_W / 2}" y="{y + 48}" text-anchor="middle">{sub}</text>')
        a('</g>')

    cid, clabel, csub = CONTROLLER
    delay = f' style="--d:-{round(len(BLOCKS) * STEP, 3)}s"' if animated else ''
    a(f'<g class="bd-subsystem bd-controller" data-subsystem="{cid}" tabindex="0" '
      f'aria-label="{clabel}"{delay}>')
    a(f'<title>{clabel} — {csub}</title>')
    a(f'<rect class="bd-box" x="30" y="{CTRL_TOP}" width="{CANVAS_W - 60}" height="75" rx="8"/>')
    a(f'<text class="bd-label" x="{CANVAS_W / 2}" y="{CTRL_TOP + 34}" text-anchor="middle">{clabel}</text>')
    a(f'<text class="bd-sub" x="{CANVAS_W / 2}" y="{CTRL_TOP + 54}" text-anchor="middle">{csub}</text>')
    a('</g>')
    a('</g>')

    foot = ("Highlight sweeps through every block automatically" if animated
            else "Hover a block to isolate it")
    a(f'<text class="bd-footer" x="{CANVAS_W / 2}" y="558" text-anchor="middle">{foot}</text>')
    a('</svg>')
    return "\n".join(o) + "\n"


SUBSYSTEMS = [
    {"id": sid, "name": label.replace("&amp;", "&"), "desc": sub,
     "col": col, "row": row, "band": BANDS[col][0].replace("&amp;", "&")}
    for col, row, sid, label, sub in BLOCKS
] + [{"id": CONTROLLER[0], "name": CONTROLLER[1], "desc": CONTROLLER[2],
      "col": -1, "row": -1, "band": "System"}]


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Washer &amp; dryer — system block diagram</title>
<style>
  :root{--bg:#f4f4f4;--panel:#fff;--line:#e2e2e2;--fg:#262626;--mut:#8c8c8c;
        --accent:#c8102e;--tint:#fdf2f4}
  html[data-theme=dark]{--bg:#0d1117;--panel:#161b22;--line:#30363d;--fg:#e6edf3;
        --mut:#8b949e;--accent:#f85149;--tint:#2a1216}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.5 "Helvetica Neue",Helvetica,Arial,sans-serif}
  header{display:flex;align-items:center;gap:14px;padding:18px 22px;
         border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:5}
  header h1{font-size:16px;margin:0;font-weight:600;letter-spacing:.2px}
  header .sp{flex:1}
  button{font:inherit;color:var(--fg);background:transparent;border:1px solid var(--line);
         border-radius:8px;padding:6px 12px;cursor:pointer}
  button:hover{border-color:var(--accent);color:var(--accent)}
  .wrap{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:22px;
        padding:22px;max-width:1500px;margin:0 auto}
  .stage{background:var(--panel);border:1px solid var(--line);border-radius:14px;
         padding:14px;overflow:auto}
  .stage svg{display:block;width:100%;height:auto}
  aside{display:flex;flex-direction:column;gap:10px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
  .card h2{margin:0 0 4px;font-size:13.5px}
  .card p{margin:0;color:var(--mut);font-size:12.5px}
  .list{background:var(--panel);border:1px solid var(--line);border-radius:12px;
        overflow:hidden;max-height:60vh;overflow-y:auto}
  .item{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);
        border-radius:0;padding:9px 13px;background:transparent}
  .item:last-child{border-bottom:0}
  .item b{display:block;font-size:13px;font-weight:600}
  .item span{color:var(--mut);font-size:11.5px}
  .item:hover,.item[aria-current=true]{background:var(--tint);
        box-shadow:inset 3px 0 0 var(--accent)}
  .item:hover b,.item[aria-current=true] b{color:var(--accent)}
  @media (max-width:940px){.wrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>Washer &amp; dryer &mdash; system block diagram</h1>
  <span class="sp"></span>
  <button id="theme" type="button">Dark</button>
</header>
<div class="wrap">
  <div class="stage" id="stage">__LIGHT_SVG__</div>
  <aside>
    <div class="card" id="info">
      <h2>Pick a block</h2>
      <p>Hover a block to isolate it, or click to pin it and read what it covers.</p>
    </div>
    <div class="list" id="list"></div>
  </aside>
</div>
<script>
const SVGS = {light: __LIGHT_JSON__, dark: __DARK_JSON__};
const SUBS = __SUBS_JSON__;
const stage = document.getElementById('stage');
const info  = document.getElementById('info');
const list  = document.getElementById('list');
let theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
let pinned = null;

function svgEl(){ return stage.querySelector('svg'); }

function render(){
  stage.innerHTML = SVGS[theme];
  document.documentElement.dataset.theme = theme;
  document.getElementById('theme').textContent = theme === 'dark' ? 'Light' : 'Dark';
  wire();
  mark();
}

function show(id){
  const s = SUBS.find(x => x.id === id);
  if (!s) return;
  info.innerHTML = '<h2></h2><p></p>';
  info.querySelector('h2').textContent = s.name;
  info.querySelector('p').textContent = s.band + ' \\u2014 ' + s.desc;
}

function mark(){
  list.querySelectorAll('.item').forEach(b =>
    b.setAttribute('aria-current', String(b.dataset.id === pinned)));
  list.querySelector('.item[data-id="' + pinned + '"]')
      ?.scrollIntoView({block:'nearest'});
}

function wire(){
  const svg = svgEl();
  if (!svg) return;
  svg.querySelectorAll('.bd-subsystem').forEach(g => {
    const id = g.dataset.subsystem;
    g.addEventListener('mouseenter', () => show(id));
    g.addEventListener('focus',      () => show(id));
    g.addEventListener('click', () => {
      pinned = pinned === id ? null : id;
      mark(); show(id);
    });
    g.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); g.dispatchEvent(new Event('click')); }
    });
  });
}

SUBS.forEach(s => {
  const b = document.createElement('button');
  b.className = 'item'; b.type = 'button'; b.dataset.id = s.id;
  b.innerHTML = '<b></b><span></span>';
  b.querySelector('b').textContent = s.name;
  b.querySelector('span').textContent = s.band + ' \\u00b7 ' + s.desc;
  b.addEventListener('mouseenter', () => show(s.id));
  b.addEventListener('click', () => {
    pinned = pinned === s.id ? null : s.id; mark(); show(s.id);
    const g = svgEl()?.querySelector('.bd-subsystem[data-subsystem="' + s.id + '"]');
    g?.scrollIntoView({block:'center', behavior:'smooth'});
    g?.focus({preventScroll:true});
  });
  list.appendChild(b);
});

document.getElementById('theme').addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark'; render();
});

render();
</script>
</body>
</html>
"""


def build_page():
    light = build_svg("light", animated=False)
    dark = build_svg("dark", animated=False)
    return (PAGE
            .replace("__LIGHT_SVG__", light)
            .replace("__LIGHT_JSON__", json.dumps(light))
            .replace("__DARK_JSON__", json.dumps(dark))
            .replace("__SUBS_JSON__", json.dumps(SUBSYSTEMS, indent=2)))


if __name__ == "__main__":
    outputs = {
        "block-diagram.svg": build_svg("light", False),
        "block-diagram-dark.svg": build_svg("dark", False),
        "block-diagram-animated.svg": build_svg("light", True),
        "block-diagram-animated-dark.svg": build_svg("dark", True),
    }
    for path, content in outputs.items():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print("wrote", path, len(content), "bytes")

    os.makedirs("interactive", exist_ok=True)
    with open("interactive/index.html", "w", encoding="utf-8") as fh:
        fh.write(build_page())
    print("wrote interactive/index.html")

    with open("subsystems.json", "w", encoding="utf-8") as fh:
        json.dump({"title": "Washer & dryer", "subsystems": SUBSYSTEMS}, fh, indent=2)
    print("wrote subsystems.json")

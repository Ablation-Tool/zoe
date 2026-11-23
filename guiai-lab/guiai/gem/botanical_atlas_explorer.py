"""Interactive Eliza-GEM Studio Visual Explorer for C27 Botanical Neuro-Oncology Atlas.

Served locally at `/botanical` by `eliza_view.py` (`0` cloud tokens, `100%` offline vanilla HTML5/JS):
  - Live interactive 36-compound NIH PubChem chemical-space scatter (MW vs TPSA) with BBB gate sliders
  - Click-to-inspect PubChem CNS MPO-4 breakdown, PAINS / quaternary-cation alerts & Filbin-2018 markers
  - Live browser Theorem 13 sequential stopping simulator over the pooled 6-module tensor
  - Interactive 16x16 = 256 FIPS 203 ML-KEM NTT slot-packing matrix (216 active + 40 spare slots)
"""

from __future__ import annotations

BOTANICAL_EXPLORER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zoe C27 · Interactive Botanical Neuro-Oncology &amp; FIPS 203 Explorer</title>
  <style>
    :root {
      --bg:#060a14; --panel:#0c1426; --panel2:#101c34; --border:#203252;
      --cyan:#00e5ff; --mint:#63f5b5; --gold:#ffb84d; --rose:#ff5c8a; --orchid:#a78bfa;
      --text:#eef5ff; --muted:#93a8c8;
    }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 12% 8%, rgba(99,245,181,0.10), transparent 34%),
           radial-gradient(circle at 88% 12%, rgba(0,229,255,0.10), transparent 36%), var(--bg);
           color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
    header { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px;
             padding:14px 22px; background:rgba(12,20,38,0.94); border-bottom:1px solid var(--border); }
    h1 { margin:0; font-size:17px; background:linear-gradient(90deg,#fff,var(--mint),var(--cyan),var(--orchid));
         -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .sub { font-size:11.5px; color:var(--muted); margin-top:2px; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .pill { padding:4px 10px; border-radius:999px; font-size:11px; font-family:ui-monospace,Menlo,monospace;
            border:1px solid rgba(255,92,138,0.45); color:var(--rose); background:rgba(255,92,138,0.08); }
    .btn { padding:6px 12px; border-radius:8px; border:1px solid var(--border); background:var(--panel2);
           color:var(--cyan); text-decoration:none; font-size:12px; cursor:pointer; font-weight:600; }
    .btn:hover { border-color:var(--cyan); }
    .grid { display:grid; grid-template-columns:1.25fr 1fr; gap:14px; padding:16px 20px; max-width:1460px; margin:auto; }
    @media (max-width: 980px) { .grid { grid-template-columns:1fr; } }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:14px; }
    .ctitle { font-family:ui-monospace,Menlo,monospace; font-size:11.5px; font-weight:700; color:var(--gold);
              letter-spacing:0.6px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
    canvas { width:100%; border-radius:10px; background:#070d1b; border:1px solid #1b2c4a; display:block; }
    .controls { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 4px; align-items:center; font-size:11.5px; color:var(--muted); }
    .controls label { display:flex; align-items:center; gap:6px; background:#081020; padding:5px 9px; border-radius:8px; border:1px solid #1c2d4b; }
    .chip-bar { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; }
    .chip { padding:4px 9px; border-radius:999px; font-size:11px; border:1px solid var(--border);
            background:#091122; color:var(--muted); cursor:pointer; }
    .chip.on { border-color:var(--mint); color:var(--mint); background:rgba(99,245,181,0.12); }
    .kv { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:8px 0; }
    .kbox { background:#081020; border:1px solid #1c2d4b; border-radius:9px; padding:7px 9px; font-family:ui-monospace,Menlo,monospace; font-size:11px; }
    .kbox strong { display:block; font-size:14px; color:var(--cyan); margin-top:2px; }
    .bar-row { display:grid; grid-template-columns:112px 1fr 48px; gap:8px; align-items:center; margin:5px 0;
               font-size:11px; font-family:ui-monospace,Menlo,monospace; }
    .track { height:9px; background:#070d1b; border-radius:999px; overflow:hidden; border:1px solid #1c2e4d; }
    .fill { height:100%; border-radius:999px; transition:width 0.25s ease; }
    .ntt-grid { display:grid; grid-template-columns:repeat(16,1fr); gap:2px; margin-top:8px; }
    .slot { aspect-ratio:1; border-radius:3px; cursor:pointer; border:1px solid rgba(255,255,255,0.04); }
    .slot:hover { outline:1.5px solid #fff; z-index:2; }
    .status-pass { color:var(--mint); font-weight:700; }
    .status-block { color:var(--rose); font-weight:700; }
    .mol-table { max-height:195px; overflow-y:auto; border:1px solid #1c2d4b; border-radius:9px; margin-top:8px; }
    table { width:100%; border-collapse:collapse; font-size:11.5px; }
    th, td { padding:6px 8px; border-bottom:1px solid #16243d; text-align:left; }
    tr:hover { background:#11203a; cursor:pointer; }
    tr.sel { background:rgba(0,229,255,0.12); }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Zoe C27 · Botanical Neuro-Oncology Atlas, 216-Slot FIPS 203 NTT &amp; Theorem 13 Explorer</h1>
      <div class="sub">36 Live-Verified NIH PubChem CIDs × 6 Filbin et al. (Science 2018) Modules · 0 Cloud Tokens · Offline Glass-Box Lab</div>
    </div>
    <div class="nav">
      <span class="pill">cure_claim=False · clinical_action_authorized=False · 0 PHI</span>
      <a class="btn" href="/">← Eliza-GEM Studio</a>
      <a class="btn" href="/optics" style="color:var(--orchid);">🔭 Optics Lab</a>
      <a class="btn" href="/orbit">Orbit Control Room</a>
      <a class="btn" href="/api/kloster/botanical-atlas">Raw JSON</a>
    </div>
  </header>

  <main class="grid">
    <section class="card">
      <div class="ctitle">
        <span>A. INTERACTIVE 36-MOLECULE PUBCHEM CHEMICAL SPACE (CLICK ANY MOLECULE)</span>
        <span id="gateCount" style="color:var(--mint);">loading...</span>
      </div>
      <div class="chip-bar" id="catChips"></div>
      <canvas id="scatterCanvas" width="760" height="400"></canvas>
      <div class="controls">
        <label>MW ≤ <strong id="vMw">450</strong> Da <input id="sMw" type="range" min="250" max="900" value="450" step="10"/></label>
        <label>TPSA ≤ <strong id="vTpsa">110</strong> Å² <input id="sTpsa" type="range" min="40" max="220" value="110" step="5"/></label>
        <label>MPO-4 ≥ <strong id="vMpo">2.5</strong> <input id="sMpo" type="range" min="1.0" max="3.8" value="2.5" step="0.1"/></label>
        <label><input id="chkGuards" type="checkbox" checked/> Enforce PAINS / Cation / Toxin Guards</label>
      </div>
      <div class="mol-table"><table><thead><tr><th>Molecule</th><th>Family</th><th>CID</th><th>MW</th><th>TPSA</th><th>MPO-4</th><th>Gate</th></tr></thead><tbody id="molBody"></tbody></table></div>
    </section>

    <aside style="display:flex;flex-direction:column;gap:14px;">
      <div class="card">
        <div class="ctitle">
          <span id="inspTitle">B. MOLECULE &amp; FILBIN-2018 MARKER INSPECTOR</span>
          <span id="inspBadge">--</span>
        </div>
        <div class="kv" id="inspKv"></div>
        <div style="font-size:11px;color:var(--muted);margin:8px 0 4px;font-family:ui-monospace,Menlo,monospace;">SYNTHETIC 3-HOSPITAL FILBIN-2018 6-MODULE PROFILE (0 REAL PHI):</div>
        <div id="filbinBars"></div>
      </div>

      <div class="card">
        <div class="ctitle">
          <span>C. LIVE THEOREM 13 STOPPING SIMULATOR (Z_K STREAM)</span>
          <button class="btn" style="padding:3px 10px;font-size:11px;" onclick="runTheorem13Sim()">▶ Stream Selected Molecule</button>
        </div>
        <canvas id="th13Canvas" width="520" height="150"></canvas>
        <div id="th13Readout" style="font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--muted);margin-top:6px;">
          Click "Stream Selected Molecule" to watch Theorem 13 stop early on selective CNS profiles vs. abstain on PAINS / raw toxins.
        </div>
      </div>

      <div class="card">
        <div class="ctitle">
          <span>D. SINGLE FIPS 203 ML-KEM n=256 NTT RING (216 ACTIVE / 40 SPARE)</span>
          <span id="nttTip" style="color:var(--cyan);">Hover or click any slot</span>
        </div>
        <div class="ntt-grid" id="nttGrid"></div>
      </div>
    </aside>
  </main>

  <script>
    const MODULES = ["OPC_STEM","MMP14_GATE","BBB_EFFLUX","NSC_GUARD","NEURON_GUARD","GLIA_GUARD"];
    const CAT_COL = {
      clinical_cns_benchmark:"#63f5b5", clinical_cns_botanical:"#00e5ff", preclinical_botanical:"#7ce8ff",
      prodrug_parent_toxin:"#ffb84d", approved_plant_oncology:"#a78bfa",
      pains_negative_control:"#ff5c8a", structural_alert_ctrl:"#ff5c8a", bbb_negative_control:"#f472b6"
    };
    let ATLAS = [], SELECTED = null, ACTIVE_CAT = "ALL", SIM_TIMER = null;

    function syntheticProfile(m) {
      if (m.category === "pains_negative_control") return [6,6,3,6,6,6];
      if (m.category === "bbb_negative_control" || m.permanent_cation_flagged) return [0,0,9,0,0,0];
      if (m.raw_systemic_toxicity_flag && m.category === "prodrug_parent_toxin") return [9,6,6,9,6,6];
      if (m.passes_clean_cns_medchem_gate) return [9,7,0,0,0,0];
      return [4,3,6,3,0,3];
    }

    function passesDynamicGate(m) {
      const mwMax = +document.getElementById("sMw").value;
      const tpsaMax = +document.getElementById("sTpsa").value;
      const mpoMin = +document.getElementById("sMpo").value;
      const guards = document.getElementById("chkGuards").checked;
      if (m.mw > mwMax || m.tpsa > tpsaMax || m.cns_mpo4_score < mpoMin) return false;
      if (!guards) return true;
      return !m.pains_flagged && !m.permanent_cation_flagged && !m.raw_systemic_toxicity_flag && m.pgp_efflux_risk === "low";
    }

    function drawScatter() {
      const cv = document.getElementById("scatterCanvas"), ctx = cv.getContext("2d");
      const W = cv.width, H = cv.height, pad = {l:54, r:20, t:18, b:38};
      ctx.clearRect(0, 0, W, H);
      const sx = mw => pad.l + ((mw - 100) / 940) * (W - pad.l - pad.r);
      const sy = tp => H - pad.b - (tp / 420) * (H - pad.t - pad.b);
      const mwMax = +document.getElementById("sMw").value, tpsaMax = +document.getElementById("sTpsa").value;
      ctx.fillStyle = "rgba(99,245,181,0.09)";
      ctx.fillRect(sx(100), sy(tpsaMax), sx(mwMax) - sx(100), sy(0) - sy(tpsaMax));
      ctx.strokeStyle = "#1a2944"; ctx.lineWidth = 1;
      for (let x = 200; x <= 1000; x += 200) { ctx.beginPath(); ctx.moveTo(sx(x), pad.t); ctx.lineTo(sx(x), H - pad.b); ctx.stroke(); }
      for (let y = 0; y <= 400; y += 100) { ctx.beginPath(); ctx.moveTo(pad.l, sy(y)); ctx.lineTo(W - pad.r, sy(y)); ctx.stroke(); }
      ctx.fillStyle = "#8aa2c4"; ctx.font = "11px monospace";
      ctx.fillText("Molecular Weight (Da, PubChem)", W/2 - 90, H - 10);
      for (let y = 0; y <= 400; y += 100) ctx.fillText(String(y), 14, sy(y) + 4);
      for (let x = 200; x <= 1000; x += 200) ctx.fillText(String(x), sx(x) - 12, H - 22);

      let passCnt = 0;
      const visible = ATLAS.filter(m => ACTIVE_CAT === "ALL" || m.category === ACTIVE_CAT);
      for (const m of visible) {
        const ok = passesDynamicGate(m); if (ok) passCnt++;
        const x = sx(m.mw), y = sy(m.tpsa), sel = SELECTED && SELECTED.id === m.id;
        ctx.beginPath(); ctx.arc(x, y, sel ? 8.5 : (ok ? 6.2 : 4.8), 0, Math.PI * 2);
        ctx.fillStyle = CAT_COL[m.category] || "#fff"; ctx.globalAlpha = ok || sel ? 1.0 : 0.45; ctx.fill();
        ctx.globalAlpha = 1.0;
        if (sel) { ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.2; ctx.stroke(); }
        if (sel || ["artemisinin","dordaviprone","galanthamine","curcumin","crocin","paclitaxel","berberine"].includes(m.id)) {
          ctx.fillStyle = sel ? "#fff" : "#bfd3ee"; ctx.font = sel ? "bold 11px monospace" : "10px monospace";
          ctx.fillText(m.id, Math.min(x + 9, W - 78), Math.max(y - 6, 16));
        }
      }
      document.getElementById("gateCount").textContent = `${passCnt} / ${visible.length} pass active gate`;
      renderTable(visible);
    }

    function renderTable(rows) {
      const tb = document.getElementById("molBody"); tb.innerHTML = "";
      for (const m of rows) {
        const ok = passesDynamicGate(m);
        const tr = document.createElement("tr");
        if (SELECTED && SELECTED.id === m.id) tr.className = "sel";
        tr.innerHTML = `<td><strong>${m.name}</strong></td><td>${m.family}</td><td>${m.pubchem_cid}</td><td>${m.mw}</td><td>${m.tpsa}</td><td>${m.cns_mpo4_score.toFixed(2)}</td><td class="${ok?'status-pass':'status-block'}">${ok?'PASS':m.medchem_alert}</td>`;
        tr.onclick = () => selectMolecule(m);
        tb.appendChild(tr);
      }
    }

    function selectMolecule(m) {
      SELECTED = m;
      document.getElementById("inspTitle").textContent = `B. ${m.name.toUpperCase()} (CID ${m.pubchem_cid})`;
      const badge = document.getElementById("inspBadge");
      badge.textContent = m.passes_clean_cns_medchem_gate ? "CLEAN CNS PASS" : `BLOCK (${m.medchem_alert})`;
      badge.className = m.passes_clean_cns_medchem_gate ? "status-pass" : "status-block";
      document.getElementById("inspKv").innerHTML = [
        ["CNS MPO-4", m.cns_mpo4_score.toFixed(2) + " / 4.0"], ["MW / TPSA", `${m.mw} Da · ${m.tpsa} Å²`],
        ["XLogP3 / HBD", `${m.xlogp3} · HBD=${m.hbd}`], ["P-gp Efflux", m.pgp_efflux_risk],
        ["PAINS Flag", String(m.pains_flagged)], ["Cation Trap", String(m.permanent_cation_flagged)]
      ].map(([k,v]) => `<div class="kbox">${k}<strong>${v}</strong></div>`).join("");
      const prof = syntheticProfile(m);
      document.getElementById("filbinBars").innerHTML = MODULES.map((mod, i) => {
        const col = i < 2 ? "#00e5ff" : (i === 2 ? "#ffb84d" : "#ff5c8a");
        return `<div class="bar-row"><span>${mod}</span><div class="track"><div class="fill" style="width:${(prof[i]/9)*100}%;background:${col}"></div></div><span>${prof[i]}/9</span></div>`;
      }).join("");
      drawScatter();
    }

    function runTheorem13Sim() {
      if (!SELECTED) return;
      if (SIM_TIMER) clearInterval(SIM_TIMER);
      const prof = syntheticProfile(SELECTED).map(v => v + 0.08);
      const tot = prof.reduce((a,b) => a + b, 0), probs = prof.map(v => v / tot);
      const counts = [0,0,0,0,0,0], hist = [];
      let S = 0, step = 0;
      const cv = document.getElementById("th13Canvas"), ctx = cv.getContext("2d");

      SIM_TIMER = setInterval(() => {
        step++;
        for (let k = 0; k < 8; k++) {
          let r = Math.random(), acc = 0, pick = 5;
          for (let j = 0; j < 6; j++) { acc += probs[j]; if (r <= acc) { pick = j; break; } }
          counts[pick]++; S++;
        }
        const m2u = counts.reduce((a, c) => a + c * (c - 1), 0) / (S * (S - 1));
        const zk = (6 * m2u - 1) / Math.sqrt((2 * 5) / (S * (S - 1)));
        const zGate = Math.sqrt(2 * Math.log(1 / (0.002 / (step * (step + 1))))) * 1.05;
        hist.push({S, zk, zGate});
        ctx.clearRect(0, 0, cv.width, cv.height);
        const maxY = Math.max(16, ...hist.map(h => h.zk + 2));
        const px = s => 36 + (s / 144) * (cv.width - 52), py = z => cv.height - 22 - ((z + 2) / (maxY + 2)) * (cv.height - 34);
        ctx.strokeStyle = "#a78bfa"; ctx.setLineDash([5,4]); ctx.beginPath();
        ctx.moveTo(36, py(zGate)); ctx.lineTo(cv.width - 16, py(zGate)); ctx.stroke(); ctx.setLineDash([]);
        ctx.strokeStyle = zk >= zGate ? "#63f5b5" : "#00e5ff"; ctx.lineWidth = 2.4; ctx.beginPath();
        hist.forEach((h, idx) => idx === 0 ? ctx.moveTo(px(h.S), py(h.zk)) : ctx.lineTo(px(h.S), py(h.zk)));
        ctx.stroke();
        ctx.fillStyle = "#93a8c8"; ctx.font = "11px monospace";
        ctx.fillText(`Gate ~${zGate.toFixed(1)}σ`, cv.width - 96, py(zGate) - 5);
        const stopped = zk >= zGate;
        const done = stopped || step >= 18;
        document.getElementById("th13Readout").innerHTML = stopped
          ? `<span class="status-pass">DECIDE_SIGNAL @ S=${S}</span> · Z_K = +${zk.toFixed(2)}σ ≥ ${zGate.toFixed(2)}σ (${SELECTED.name} — selective Filbin profile!)`
          : (done ? `<span class="status-block">ABSTAIN_INSUFFICIENT_EVIDENCE @ S=${S}</span> · Z_K = ${zk.toFixed(2)}σ < ${zGate.toFixed(2)}σ (honestly abstained!)`
                  : `GATHER_MORE @ S=${S} · Z_K = ${zk.toFixed(2)}σ ...`);
        if (done) { clearInterval(SIM_TIMER); SIM_TIMER = null; }
      }, 95);
    }

    function buildNttGrid() {
      const g = document.getElementById("nttGrid"); g.innerHTML = "";
      for (let i = 0; i < 256; i++) {
        const div = document.createElement("div"); div.className = "slot";
        if (i < 216) {
          const m = ATLAS[Math.floor(i / 6)], mod = MODULES[i % 6];
          div.style.background = CAT_COL[m.category] || "#00e5ff";
          div.style.opacity = String(0.45 + 0.09 * (i % 6));
          div.title = `Slot #${i}: ${m.name} -> ${mod}`;
          div.onmouseenter = () => document.getElementById("nttTip").textContent = `Slot #${i}: ${m.id} · ${mod}`;
          div.onclick = () => selectMolecule(m);
        } else {
          div.style.background = "#182742"; div.title = `Slot #${i}: Spare FIPS 203 NTT headroom`;
          div.onmouseenter = () => document.getElementById("nttTip").textContent = `Slot #${i}: Spare RLWE headroom`;
        }
        g.appendChild(div);
      }
    }

    async function init() {
      const resp = await fetch("/api/kloster/botanical-atlas");
      const data = await resp.json();
      ATLAS = data.molecule_atlas || [];
      const cats = ["ALL", ...new Set(ATLAS.map(m => m.category))];
      const bar = document.getElementById("catChips");
      cats.forEach(c => {
        const el = document.createElement("span"); el.className = "chip" + (c === "ALL" ? " on" : "");
        el.textContent = c.replaceAll("_", " ");
        el.onclick = () => { ACTIVE_CAT = c; [...bar.children].forEach(x => x.classList.remove("on")); el.classList.add("on"); drawScatter(); };
        bar.appendChild(el);
      });
      ["sMw","sTpsa","sMpo","chkGuards"].forEach(id => document.getElementById(id).oninput = () => {
        document.getElementById("vMw").textContent = document.getElementById("sMw").value;
        document.getElementById("vTpsa").textContent = document.getElementById("sTpsa").value;
        document.getElementById("vMpo").textContent = (+document.getElementById("sMpo").value).toFixed(1);
        drawScatter();
      });
      document.getElementById("scatterCanvas").onclick = ev => {
        const cv = ev.target, rect = cv.getBoundingClientRect();
        const cx = (ev.clientX - rect.left) * (cv.width / rect.width), cy = (ev.clientY - rect.top) * (cv.height / rect.height);
        const sx = mw => 54 + ((mw - 100) / 940) * (cv.width - 74), sy = tp => cv.height - 38 - (tp / 420) * (cv.height - 56);
        let best = null, bestD = 9999;
        for (const m of ATLAS) { const d = Math.hypot(sx(m.mw) - cx, sy(m.tpsa) - cy); if (d < bestD) { bestD = d; best = m; } }
        if (best && bestD < 28) selectMolecule(best);
      };
      buildNttGrid();
      selectMolecule(ATLAS.find(m => m.id === "artemisinin") || ATLAS[0]);
      runTheorem13Sim();
    }
    init();
  </script>
</body>
</html>
"""


def render_botanical_explorer_html() -> bytes:
    """Return UTF-8 HTML bytes for the offline interactive C27 Botanical Atlas Explorer."""
    return BOTANICAL_EXPLORER_HTML.encode("utf-8")

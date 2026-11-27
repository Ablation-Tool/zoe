"""Interactive Eliza-GEM Studio Workbench for Theorem 14: Optical Bench, Spatial Points & Isovists.

Served locally at `/optics` by `eliza_view.py` (`0` cloud tokens, `100%` offline vanilla HTML5/JS):
  - Panel A: Live View-Camera Scheimpflug Optical Bench (tilt lens theta vs specimen psi, hinge point)
  - Panel B: Interactive 2D Spatial Point-Pattern Sandbox (Thomas / CSR / Hard-Core / Click-to-Paint)
  - Panel C: Live Optical PSF / MTF Blur & Botanical Ink-Contour vs Watercolor Filtration Lab
  - Panel D: Real-Time 72-Ray Architectural Isovist Floorplan (mouse-driven) & Structural Load Sharing
"""

from __future__ import annotations

OPTICS_WORKBENCH_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zoe Theorem 14 · Interactive Optical Bench, Spatial Point-Pattern &amp; Isovist Lab</title>
  <style>
    :root {
      --bg:#060a14; --panel:#0c1426; --panel2:#101c34; --border:#203252;
      --cyan:#00e5ff; --mint:#63f5b5; --gold:#ffb84d; --rose:#ff5c8a; --orchid:#a78bfa;
      --text:#eef5ff; --muted:#93a8c8;
    }
    * { box-sizing:border-box; }
    body { margin:0; background:radial-gradient(circle at 14% 10%, rgba(167,139,250,0.12), transparent 36%),
           radial-gradient(circle at 86% 12%, rgba(0,229,255,0.11), transparent 36%), var(--bg);
           color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
    header { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:12px;
             padding:14px 22px; background:rgba(12,20,38,0.94); border-bottom:1px solid var(--border); }
    h1 { margin:0; font-size:17px; background:linear-gradient(90deg,#fff,var(--cyan),var(--orchid),var(--mint));
         -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .sub { font-size:11.5px; color:var(--muted); margin-top:2px; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .pill { padding:4px 10px; border-radius:999px; font-size:11px; font-family:ui-monospace,Menlo,monospace;
            border:1px solid rgba(99,245,181,0.45); color:var(--mint); background:rgba(99,245,181,0.08); }
    .btn { padding:6px 11px; border-radius:8px; border:1px solid var(--border); background:var(--panel2);
           color:var(--cyan); text-decoration:none; font-size:11.5px; cursor:pointer; font-weight:600; }
    .btn:hover, .btn.on { border-color:var(--cyan); background:rgba(0,229,255,0.14); }
    .btn.gold { color:var(--gold); border-color:rgba(255,184,77,0.55); }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; padding:16px 20px; max-width:1480px; margin:auto; }
    @media (max-width: 980px) { .grid { grid-template-columns:1fr; } }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:14px; display:flex; flex-direction:column; gap:10px; }
    .ctitle { font-family:ui-monospace,Menlo,monospace; font-size:11.5px; font-weight:700; color:var(--gold);
              letter-spacing:0.6px; display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; }
    canvas { width:100%; border-radius:10px; background:#070d1b; border:1px solid #1b2c4a; display:block; }
    .row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; font-size:11.5px; color:var(--muted); }
    .row label { display:flex; align-items:center; gap:6px; background:#081020; padding:5px 9px; border-radius:8px; border:1px solid #1c2d4b; }
    .kv { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
    .kbox { background:#081020; border:1px solid #1c2d4b; border-radius:9px; padding:7px 9px; font-family:ui-monospace,Menlo,monospace; font-size:11px; color:var(--muted); }
    .kbox strong { display:block; font-size:13.5px; color:var(--cyan); margin-top:2px; }
    .split { display:grid; grid-template-columns:1.1fr 1fr; gap:10px; align-items:center; }
    .bar-row { display:grid; grid-template-columns:56px 1fr 44px; gap:6px; align-items:center; margin:3px 0; font-size:10.5px; font-family:ui-monospace,Menlo,monospace; }
    .track { height:8px; background:#070d1b; border-radius:999px; overflow:hidden; border:1px solid #1c2e4d; }
    .fill { height:100%; border-radius:999px; transition:width 0.2s ease; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Zoe Theorem 14 · Interactive Optical Bench, Spatial Point-Pattern &amp; Isovist Workbench</h1>
      <div class="sub">Kloster Spatial-Optical Filtration A_τ(f) · 6/6 SymPy Proofs · Scheimpflug Hinge, Parseval MTF, Spatial Z_K &amp; Ray-Cast Isovists · 0 Cloud Tokens</div>
    </div>
    <div class="nav">
      <span class="pill" id="thmPill">6/6 SYMPY PROVED · OFFLINE</span>
      <a class="btn" href="/">← Eliza-GEM Studio</a>
      <a class="btn" href="/botanical" style="color:var(--mint);">🌿 C27 Atlas</a>
      <a class="btn" href="/proof" style="color:var(--gold);">⚖️ Proof Lab</a>
      <a class="btn" href="/orbit">Orbit Control Room</a>
      <a class="btn" href="/api/kloster/theorem14">Raw JSON</a>
    </div>
  </header>

  <main class="grid">
    <!-- PANEL A: VIEW CAMERA SCHEIMPFLUG OPTICAL BENCH -->
    <section class="card">
      <div class="ctitle">
        <span>A. VIEW-CAMERA SCHEIMPFLUG OPTICAL BENCH (STROEBEL × THM 14f)</span>
        <button class="btn gold" onclick="snapScheimpflug()">✦ Snap to Scheimpflug θ*</button>
      </div>
      <canvas id="schCanvas" width="660" height="260"></canvas>
      <div class="row">
        <label>Specimen Tilt ψ: <strong id="vPsi">25°</strong> <input id="sPsi" type="range" min="0" max="35" value="25" step="1"/></label>
        <label>Lens Tilt θ: <strong id="vTheta">13.5°</strong> <input id="sTheta" type="range" min="-8" max="26" value="13.5" step="0.25"/></label>
        <label>Aperture: <strong id="vFnum">f/2.8</strong> <input id="sFnum" type="range" min="2.0" max="16.0" value="2.8" step="0.4"/></label>
      </div>
      <div class="kv">
        <div class="kbox">Theory θ* = arcsin((f/u)tanψ)<strong id="kThStar">--</strong></div>
        <div class="kbox">Kloster Sharpness M₂(θ)<strong id="kSchM2">--</strong></div>
        <div class="kbox">Gain vs Untilted (θ = 0°)<strong id="kSchGain">--</strong></div>
      </div>
    </section>

    <!-- PANEL B: INTERACTIVE 2D SPATIAL POINT-PATTERN SANDBOX -->
    <section class="card">
      <div class="ctitle">
        <span>B. SPATIAL POINT-PATTERN SANDBOX (BADDELEY × THM 14a · CLICK TO PAINT)</span>
        <span id="ptRegime" style="color:var(--mint);">--</span>
      </div>
      <div class="row">
        <button class="btn on" id="btnClust" onclick="genPoints('clustered')">Thomas Clustered</button>
        <button class="btn" id="btnCsr" onclick="genPoints('csr')">CSR Poisson Null</button>
        <button class="btn" id="btnInhib" onclick="genPoints('inhibited')">Hard-Core Regular</button>
        <button class="btn" onclick="genPoints('clear')">Clear &amp; Paint</button>
        <label><input id="chkQuad" type="checkbox" checked/> 8×8 Quadrat Heatmap</label>
      </div>
      <canvas id="ptCanvas" width="660" height="260" style="cursor:crosshair;"></canvas>
      <div class="kv">
        <div class="kbox">Two-Sided Kloster Z_K<strong id="kPtZk">--</strong></div>
        <div class="kbox">Quadrat VMR (σ²/μ)<strong id="kPtVmr">--</strong></div>
        <div class="kbox">Toroidal Besag L(r) − r<strong id="kPtLr">--</strong></div>
      </div>
    </section>

    <!-- PANEL C: OPTICAL PSF / MTF BLUR & BOTANICAL CONTOUR LAB -->
    <section class="card">
      <div class="ctitle">
        <span>C. OPTICAL PSF/MTF BLUR &amp; BOTANICAL CONTOUR LAB (PERES × EWING × THM 14e)</span>
        <span id="mtfMono" style="color:var(--mint);">M₂(K*p) ≤ M₂(p)</span>
      </div>
      <div class="row">
        <button class="btn on" id="btnInk" onclick="setSpecimen('ink')">Botanical Ink Contour</button>
        <button class="btn" id="btnWash" onclick="setSpecimen('wash')">Watercolor Wash</button>
        <button class="btn" id="btnCells" onclick="setSpecimen('cells')">Microscopy Cells</button>
        <button class="btn" id="btnPaper" onclick="setSpecimen('paper')">Blank Paper Null</button>
      </div>
      <div class="split">
        <canvas id="mtfCanvas" width="320" height="220"></canvas>
        <div style="display:flex;flex-direction:column;gap:8px;">
          <label style="display:flex;flex-direction:column;gap:4px;background:#081020;padding:8px;border-radius:8px;border:1px solid #1c2d4b;font-size:11.5px;color:var(--muted);">
            <span>Optical PSF Blur σ_psf: <strong id="vPsf" style="color:var(--cyan);">0.0 px</strong></span>
            <input id="sPsf" type="range" min="0" max="4.8" value="0" step="0.2"/>
          </label>
          <div class="kbox">Spatial Sharpness M₂(K*p)<strong id="kMtfM2">--</strong></div>
          <div class="kbox">Sharpness Retention vs σ=0<strong id="kMtfRet">--</strong></div>
          <div class="kbox">Equivalent Abbe NA (λ=550nm)<strong id="kMtfNa">--</strong></div>
        </div>
      </div>
    </section>

    <!-- PANEL D: ARCHITECTURAL ISOVIST RAY-CASTER & STRUCTURAL LOAD SHARING -->
    <section class="card">
      <div class="ctitle">
        <span>D. ARCHITECTURAL ISOVIST &amp; STRUCTURAL LOAD SHARING (TOTTEN × CRUZ)</span>
        <span id="isoReadout" style="color:var(--cyan);">Move mouse inside floorplan</span>
      </div>
      <div class="row">
        <button class="btn on" id="btnPlaza" onclick="setFloorplan('plaza')">Open Plaza</button>
        <button class="btn" id="btnCorr" onclick="setFloorplan('corridor')">Axial Corridor</button>
        <button class="btn" id="btnRefuge" onclick="setFloorplan('refuge')">Prospect-Refuge</button>
        <button class="btn gold" id="btnStruct" onclick="toggleStruct()">Structure: Funicular Arch</button>
      </div>
      <div class="split">
        <canvas id="isoCanvas" width="350" height="220" style="cursor:crosshair;"></canvas>
        <div>
          <div style="font-size:11px;font-family:ui-monospace,Menlo,monospace;color:var(--gold);margin-bottom:4px;" id="structTitle">FUNICULAR ARCH · N_eff = 11.99 / 12</div>
          <div id="structBars"></div>
          <div class="kbox" style="margin-top:8px;">Isovist Sightline Focus (N·M₂)<strong id="kIsoConc">--</strong></div>
        </div>
      </div>
    </section>
  </main>

  <script>
    // ---------- PANEL A: SCHEIMPFLUG OPTICAL BENCH ----------
    function computeScheimpflugM2(psiDeg, thDeg, fnum) {
      const f = 90.0, u = 180.0, ap = f / fnum, psi = psiDeg * Math.PI / 180, th = thDeg * Math.PI / 180;
      const denom = Math.cos(th) - f / u;
      if (denom <= 0.05) return 0;
      const v = f / denom, xs = [-45,-30,-15,0,15,30,45], sig0 = 0.35, N = 260;
      const arr = new Float64Array(N);
      let sum = 0;
      for (const x0 of xs) {
        const z = u + x0 * Math.tan(psi), dO = z * Math.cos(th) - x0 * Math.sin(th);
        const dIs = (f * dO) / Math.max(dO - f, 1e-4), dIm = (v / z) * dO;
        const sig = Math.hypot(sig0, 0.45 * ap * Math.abs(dIm - dIs) / Math.max(dIs, 1));
        const inv = 1 / (Math.sqrt(2 * Math.PI) * sig);
        for (let i = 0; i < N; i++) {
          const s = -65 + (130 * i) / (N - 1);
          const val = inv * Math.exp(-0.5 * ((s - x0) / sig) ** 2);
          arr[i] += val; sum += val;
        }
      }
      let m2 = 0;
      for (let i = 0; i < N; i++) { const p = arr[i] / sum; m2 += p * p; }
      return m2;
    }

    function drawScheimpflug() {
      const psiDeg = +document.getElementById("sPsi").value;
      const thDeg = +document.getElementById("sTheta").value;
      const fnum = +document.getElementById("sFnum").value;
      document.getElementById("vPsi").textContent = `${psiDeg}°`;
      document.getElementById("vTheta").textContent = `${thDeg.toFixed(2)}°`;
      document.getElementById("vFnum").textContent = `f/${fnum.toFixed(1)}`;
      const arg = Math.min(0.95, 0.5 * Math.tan(psiDeg * Math.PI / 180));
      const thStar = Math.asin(arg) * 180 / Math.PI;
      const m2Now = computeScheimpflugM2(psiDeg, thDeg, fnum);
      const m2Zero = computeScheimpflugM2(psiDeg, 0, fnum);
      document.getElementById("kThStar").textContent = `${thStar.toFixed(2)}°`;
      document.getElementById("kSchM2").textContent = `${(m2Now * 1e3).toFixed(2)} ×10⁻³`;
      document.getElementById("kSchGain").textContent = `${(m2Now / Math.max(m2Zero, 1e-9)).toFixed(2)}×`;

      const cv = document.getElementById("schCanvas"), ctx = cv.getContext("2d");
      const W = cv.width, H = cv.height;
      ctx.clearRect(0, 0, W, H);
      // Left half: Optical Bench Geometry (Sensor, Lens, Tilted Subject, Hinge Line)
      const cx = 170, cy = 128, sc = 0.65;
      const th = thDeg * Math.PI / 180, psi = psiDeg * Math.PI / 180;
      const f = 90, u = 180, v = f / Math.max(Math.cos(th) - f / u, 0.15);
      // Optical axis
      ctx.strokeStyle = "#1c2d4b"; ctx.setLineDash([4,4]); ctx.beginPath(); ctx.moveTo(20, cy); ctx.lineTo(340, cy); ctx.stroke(); ctx.setLineDash([]);
      // Sensor plane (z = -v -> left of lens)
      const sx = cx - v * sc * 0.52;
      ctx.strokeStyle = "#00e5ff"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(sx, cy - 82); ctx.lineTo(sx, cy + 82); ctx.stroke();
      // Tilted Lens plane
      const lx1 = cx - Math.sin(th) * 72, ly1 = cy - Math.cos(th) * 72, lx2 = cx + Math.sin(th) * 72, ly2 = cy + Math.cos(th) * 72;
      ctx.strokeStyle = "#a78bfa"; ctx.lineWidth = 3.5; ctx.beginPath(); ctx.moveTo(lx1, ly1); ctx.lineTo(lx2, ly2); ctx.stroke();
      // Tilted Subject plane (z = +u -> right of lens)
      const ux = cx + u * sc * 0.52;
      const ux1 = ux + Math.tan(psi) * 72, uy1 = cy - 72, ux2 = ux - Math.tan(psi) * 72, uy2 = cy + 72;
      ctx.strokeStyle = "#63f5b5"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(ux1, uy1); ctx.lineTo(ux2, uy2); ctx.stroke();
      // Rays + labels
      ctx.strokeStyle = "rgba(255,184,77,0.35)"; ctx.lineWidth = 1.1;
      for (const dy of [-50, 0, 50]) {
        ctx.beginPath(); ctx.moveTo(ux - Math.tan(psi) * dy, cy + dy); ctx.lineTo(cx, cy); ctx.lineTo(sx, cy - dy); ctx.stroke();
      }
      ctx.fillStyle = "#00e5ff"; ctx.font = "10.5px monospace"; ctx.fillText("Sensor", sx - 18, 22);
      ctx.fillStyle = "#a78bfa"; ctx.fillText(`Lens θ=${thDeg.toFixed(1)}°`, cx - 32, 22);
      ctx.fillStyle = "#63f5b5"; ctx.fillText(`Specimen ψ=${psiDeg}°`, ux - 36, 22);
      const aligned = Math.abs(thDeg - thStar) <= 0.8;
      ctx.fillStyle = aligned ? "#63f5b5" : "#ffb84d";
      ctx.fillText(aligned ? "✦ SCHEIMPFLUG LOCKED (3 planes co-hinged!)" : `Δθ from Scheimpflug: ${(thDeg - thStar).toFixed(2)}°`, 16, H - 12);

      // Right half: Live M2(theta) Resonance Curve
      const gx = 376, gw = W - gx - 20, gy = 26, gh = H - 56;
      ctx.fillStyle = "#091122"; ctx.fillRect(gx, gy, gw, gh);
      ctx.strokeStyle = "#1d3154"; ctx.strokeRect(gx, gy, gw, gh);
      const pts = []; let mx = 0.001;
      for (let t = -8; t <= 26; t += 1) { const m = computeScheimpflugM2(psiDeg, t, fnum); pts.push([t, m]); if (m > mx) mx = m; }
      const px = t => gx + ((t + 8) / 34) * gw, py = m => gy + gh - (m / (mx * 1.12)) * gh;
      ctx.strokeStyle = "#63f5b5"; ctx.setLineDash([4,4]); ctx.beginPath(); ctx.moveTo(px(thStar), gy); ctx.lineTo(px(thStar), gy + gh); ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = "#a78bfa"; ctx.lineWidth = 2.2; ctx.beginPath();
      pts.forEach(([t, m], i) => i === 0 ? ctx.moveTo(px(t), py(m)) : ctx.lineTo(px(t), py(m)));
      ctx.stroke();
      ctx.fillStyle = "#ffb84d"; ctx.beginPath(); ctx.arc(px(thDeg), py(m2Now), 5.5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#93a8c8"; ctx.font = "10px monospace";
      ctx.fillText("Kloster M₂(θ) Curve", gx + 8, gy + 14);
      ctx.fillText(`θ*=${thStar.toFixed(1)}°`, Math.min(px(thStar) + 4, W - 62), gy + 28);
    }

    function snapScheimpflug() {
      const psiDeg = +document.getElementById("sPsi").value;
      const thStar = Math.asin(Math.min(0.95, 0.5 * Math.tan(psiDeg * Math.PI / 180))) * 180 / Math.PI;
      document.getElementById("sTheta").value = thStar.toFixed(2);
      drawScheimpflug();
    }

    // ---------- PANEL B: SPATIAL POINT PATTERNS ----------
    let PTS = [];
    function randn() { return Math.sqrt(-2 * Math.log(Math.max(Math.random(), 1e-9))) * Math.cos(2 * Math.PI * Math.random()); }
    function genPoints(mode) {
      ["btnClust","btnCsr","btnInhib"].forEach(id => document.getElementById(id).classList.remove("on"));
      PTS = [];
      if (mode === "clustered") {
        document.getElementById("btnClust").classList.add("on");
        for (let p = 0; p < 12; p++) {
          const px = Math.random(), py = Math.random();
          for (let k = 0; k < 16; k++) PTS.push([((px + randn() * 0.036) % 1 + 1) % 1, ((py + randn() * 0.036) % 1 + 1) % 1]);
        }
      } else if (mode === "csr") {
        document.getElementById("btnCsr").classList.add("on");
        for (let i = 0; i < 192; i++) PTS.push([Math.random(), Math.random()]);
      } else if (mode === "inhibited") {
        document.getElementById("btnInhib").classList.add("on");
        for (let r = 0; r < 12; r++) for (let c = 0; c < 16; c++) {
          PTS.push([Math.min(0.995, Math.max(0.005, (c + 0.5) / 16 + randn() * 0.008)), Math.min(0.995, Math.max(0.005, (r + 0.5) / 12 + randn() * 0.008))]);
        }
      }
      drawPoints();
    }

    function drawPoints() {
      const cv = document.getElementById("ptCanvas"), ctx = cv.getContext("2d"), W = cv.width, H = cv.height;
      ctx.clearRect(0, 0, W, H);
      const G = 8, bins = new Int32Array(G * G);
      for (const [x, y] of PTS) {
        const c = Math.min(G - 1, Math.floor(x * G)), r = Math.min(G - 1, Math.floor(y * G));
        bins[r * G + c]++;
      }
      if (document.getElementById("chkQuad").checked) {
        const mx = Math.max(1, ...bins);
        for (let r = 0; r < G; r++) for (let c = 0; c < G; c++) {
          const v = bins[r * G + c] / mx;
          ctx.fillStyle = `rgba(0,229,255,${(v * 0.35).toFixed(3)})`;
          ctx.fillRect((c / G) * W, (r / G) * H, W / G, H / G);
          ctx.strokeStyle = "rgba(32,50,82,0.55)"; ctx.strokeRect((c / G) * W, (r / G) * H, W / G, H / G);
        }
      }
      ctx.fillStyle = "#63f5b5";
      for (const [x, y] of PTS) { ctx.beginPath(); ctx.arc(x * W, y * H, 3.1, 0, Math.PI * 2); ctx.fill(); }
      const S = PTS.length;
      if (S < 4) {
        document.getElementById("kPtZk").textContent = "Paint ≥4 pts";
        document.getElementById("kPtVmr").textContent = "--";
        document.getElementById("kPtLr").textContent = "--";
        document.getElementById("ptRegime").textContent = "PAINT MODE";
        return;
      }
      let coll = 0, mean = S / 64, vsum = 0;
      for (let i = 0; i < 64; i++) { coll += bins[i] * (bins[i] - 1); vsum += (bins[i] - mean) ** 2; }
      const m2u = coll / (S * (S - 1));
      const zk = (64 * m2u - 1) / Math.sqrt((2 * 63) / (S * (S - 1)));
      const vmr = (vsum / 63) / Math.max(mean, 1e-9);
      let pairs = 0, rEval = 0.08;
      for (let i = 0; i < S; i++) for (let j = i + 1; j < S; j++) {
        let dx = Math.abs(PTS[i][0] - PTS[j][0]), dy = Math.abs(PTS[i][1] - PTS[j][1]);
        dx = Math.min(dx, 1 - dx); dy = Math.min(dy, 1 - dy);
        if (dx * dx + dy * dy <= rEval * rEval) pairs += 2;
      }
      const lr = Math.sqrt((pairs / (S * S)) / Math.PI) - rEval;
      document.getElementById("kPtZk").textContent = `${zk >= 0 ? "+" : ""}${zk.toFixed(2)}σ`;
      document.getElementById("kPtVmr").textContent = vmr.toFixed(2);
      document.getElementById("kPtLr").textContent = `${lr >= 0 ? "+" : ""}${lr.toFixed(4)}`;
      const reg = document.getElementById("ptRegime");
      if (zk > 2.5) { reg.textContent = "CLUSTERED (+Z_K)"; reg.style.color = "#ff5c8a"; }
      else if (zk < -2.5) { reg.textContent = "REGULAR / INHIBITED (−Z_K)"; reg.style.color = "#00e5ff"; }
      else { reg.textContent = "CSR POISSON NULL"; reg.style.color = "#63f5b5"; }
    }

    // ---------- PANEL C: OPTICAL PSF / MTF BLUR & BOTANICAL CONTOUR ----------
    let SPEC_MODE = "ink", BASE_IMG = null, BASE_M2 = 1;
    const IMG_N = 48;
    function setSpecimen(mode) {
      SPEC_MODE = mode;
      ["btnInk","btnWash","btnCells","btnPaper"].forEach(id => document.getElementById(id).classList.remove("on"));
      document.getElementById({ink:"btnInk",wash:"btnWash",cells:"btnCells",paper:"btnPaper"}[mode]).classList.add("on");
      BASE_IMG = new Float64Array(IMG_N * IMG_N);
      let sum = 0;
      for (let r = 0; r < IMG_N; r++) for (let c = 0; c < IMG_N; c++) {
        const x = -1 + 2 * c / (IMG_N - 1), y = -1 + 2 * r / (IMG_N - 1), rad = Math.hypot(x, y);
        let v = 1;
        if (mode === "ink") v = Math.exp(-((Math.abs(rad - (0.55 + 0.18 * Math.cos(5 * Math.atan2(y, x)))) / 0.04) ** 2));
        else if (mode === "wash") v = Math.exp(-((rad / 0.65) ** 2));
        else if (mode === "cells") v = Math.exp(-(((x + 0.35) ** 2 + (y + 0.25) ** 2) / 0.045)) + 1.2 * Math.exp(-(((x - 0.3) ** 2 + (y - 0.2) ** 2) / 0.035)) + 0.35 * (Math.sin(6 * x) ** 2) * (Math.cos(6 * y) ** 2);
        BASE_IMG[r * IMG_N + c] = v; sum += v;
      }
      BASE_M2 = 0;
      for (let i = 0; i < BASE_IMG.length; i++) { BASE_IMG[i] /= sum; BASE_M2 += BASE_IMG[i] ** 2; }
      drawMtfSpecimen();
    }

    function blurSeparable(src, sig) {
      if (sig <= 0.05) return src;
      const rad = Math.min(12, Math.ceil(sig * 2.6)), ker = [];
      let ks = 0;
      for (let k = -rad; k <= rad; k++) { const w = Math.exp(-(k * k) / (2 * sig * sig)); ker.push(w); ks += w; }
      for (let i = 0; i < ker.length; i++) ker[i] /= ks;
      const tmp = new Float64Array(IMG_N * IMG_N), out = new Float64Array(IMG_N * IMG_N);
      for (let r = 0; r < IMG_N; r++) for (let c = 0; c < IMG_N; c++) {
        let acc = 0;
        for (let k = -rad; k <= rad; k++) acc += src[r * IMG_N + ((c + k + IMG_N) % IMG_N)] * ker[k + rad];
        tmp[r * IMG_N + c] = acc;
      }
      for (let r = 0; r < IMG_N; r++) for (let c = 0; c < IMG_N; c++) {
        let acc = 0;
        for (let k = -rad; k <= rad; k++) acc += tmp[((r + k + IMG_N) % IMG_N) * IMG_N + c] * ker[k + rad];
        out[r * IMG_N + c] = acc;
      }
      return out;
    }

    function drawMtfSpecimen() {
      const sig = +document.getElementById("sPsf").value;
      document.getElementById("vPsf").textContent = `${sig.toFixed(1)} px`;
      const img = blurSeparable(BASE_IMG, sig);
      let m2 = 0, mx = 1e-12;
      for (let i = 0; i < img.length; i++) { m2 += img[i] ** 2; if (img[i] > mx) mx = img[i]; }
      document.getElementById("kMtfM2").textContent = `${(m2 * 1e3).toFixed(2)} ×10⁻³`;
      document.getElementById("kMtfRet").textContent = `${((m2 / BASE_M2) * 100).toFixed(1)}%`;
      const na = sig <= 0.1 ? "Diffraction Ideal" : `${(0.61 * 0.55 / Math.max(2.355 * sig * 0.10, 0.05)).toFixed(2)} NA`;
      document.getElementById("kMtfNa").textContent = na;

      const cv = document.getElementById("mtfCanvas"), ctx = cv.getContext("2d");
      const cw = cv.width / IMG_N, ch = cv.height / IMG_N;
      ctx.clearRect(0, 0, cv.width, cv.height);
      for (let r = 0; r < IMG_N; r++) for (let c = 0; c < IMG_N; c++) {
        const t = img[r * IMG_N + c] / mx;
        const R = Math.round(12 + 88 * t), G = Math.round(24 + 220 * t), B = Math.round(46 + 195 * Math.sqrt(t));
        ctx.fillStyle = `rgb(${R},${G},${B})`;
        ctx.fillRect(c * cw, r * ch, Math.ceil(cw), Math.ceil(ch));
      }
    }

    // ---------- PANEL D: ARCHITECTURAL ISOVIST & STRUCTURAL LOAD SHARING ----------
    let FLOOR = "plaza", VPOS = [0.5, 0.5], STRUCT_ARCH = true;
    const FLOOR_WALLS = {
      plaza: [[0.06,0.08,0.94,0.08],[0.94,0.08,0.94,0.92],[0.94,0.92,0.06,0.92],[0.06,0.92,0.06,0.08]],
      corridor: [[0.04,0.34,0.96,0.34],[0.96,0.34,0.96,0.66],[0.96,0.66,0.04,0.66],[0.04,0.66,0.04,0.34]],
      refuge: [[0.06,0.08,0.94,0.08],[0.94,0.08,0.94,0.92],[0.94,0.92,0.06,0.92],[0.06,0.92,0.06,0.08],[0.06,0.36,0.38,0.36],[0.06,0.64,0.38,0.64],[0.62,0.08,0.62,0.38],[0.62,0.62,0.62,0.92]]
    };
    function raySeg(ox, oy, dx, dy, x1, y1, x2, y2) {
      const vx = x2 - x1, vy = y2 - y1, den = dx * vy - dy * vx;
      if (Math.abs(den) < 1e-9) return 1e9;
      const t = ((x1 - ox) * vy - (y1 - oy) * vx) / den, u = ((x1 - ox) * dy - (y1 - oy) * dx) / den;
      return (t > 0 && u >= 0 && u <= 1) ? t : 1e9;
    }
    function setFloorplan(f) {
      FLOOR = f;
      ["btnPlaza","btnCorr","btnRefuge"].forEach(id => document.getElementById(id).classList.remove("on"));
      document.getElementById({plaza:"btnPlaza",corridor:"btnCorr",refuge:"btnRefuge"}[f]).classList.add("on");
      VPOS = f === "refuge" ? [0.22, 0.5] : [0.5, 0.5];
      drawIsovist();
    }
    function drawIsovist() {
      const cv = document.getElementById("isoCanvas"), ctx = cv.getContext("2d"), W = cv.width, H = cv.height;
      ctx.clearRect(0, 0, W, H);
      const walls = FLOOR_WALLS[FLOOR], N = 72, dists = [], hits = [];
      let dSum = 0;
      for (let i = 0; i < N; i++) {
        const a = (2 * Math.PI * i) / N, dx = Math.cos(a), dy = Math.sin(a);
        let best = 1.5;
        for (const w of walls) { const t = raySeg(VPOS[0], VPOS[1], dx, dy, w[0], w[1], w[2], w[3]); if (t < best) best = t; }
        dists.push(best); dSum += best; hits.push([VPOS[0] + dx * best, VPOS[1] + dy * best]);
      }
      ctx.fillStyle = "rgba(0,229,255,0.18)"; ctx.strokeStyle = "rgba(99,245,181,0.55)"; ctx.lineWidth = 1.2;
      ctx.beginPath();
      hits.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x * W, y * H) : ctx.lineTo(x * W, y * H));
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "#ffb84d"; ctx.lineWidth = 3;
      for (const w of walls) { ctx.beginPath(); ctx.moveTo(w[0] * W, w[1] * H); ctx.lineTo(w[2] * W, w[3] * H); ctx.stroke(); }
      ctx.fillStyle = "#ff5c8a"; ctx.beginPath(); ctx.arc(VPOS[0] * W, VPOS[1] * H, 5, 0, Math.PI * 2); ctx.fill();
      let m2 = 0;
      for (const d of dists) m2 += (d / dSum) ** 2;
      const conc = N * m2;
      document.getElementById("kIsoConc").textContent = `${conc.toFixed(2)}× (${conc > 1.35 ? "Axial Sightline" : "Open Vista"})`;
    }
    function toggleStruct() {
      STRUCT_ARCH = !STRUCT_ARCH;
      document.getElementById("btnStruct").textContent = STRUCT_ARCH ? "Structure: Funicular Arch" : "Structure: Eccentric Cantilever";
      renderStruct();
    }
    function renderStruct() {
      const forces = STRUCT_ARCH ? [10.2,10.0,9.8,10.1,9.9,10.3,9.7,10.0,10.2,9.8,10.1,9.9] : [48,42,18,6,3,1.5,0.8,0.4,0.2,0.1,0.05,0.05];
      const tot = forces.reduce((a,b) => a + b, 0), mx = Math.max(...forces);
      let m2 = 0; forces.forEach(f => m2 += (f / tot) ** 2);
      const neff = 1 / m2;
      document.getElementById("structTitle").textContent = `${STRUCT_ARCH ? "FUNICULAR ARCH" : "CANTILEVER BOTTLENECK"} · N_eff = ${neff.toFixed(2)} / 12`;
      document.getElementById("structBars").innerHTML = forces.slice(0, 6).map((f, i) => {
        const col = STRUCT_ARCH ? "#00e5ff" : (i < 2 ? "#ff5c8a" : "#ffb84d");
        return `<div class="bar-row"><span>Mem ${i+1}</span><div class="track"><div class="fill" style="width:${(f/mx)*100}%;background:${col}"></div></div><span>${((f/tot)*100).toFixed(0)}%</span></div>`;
      }).join("");
    }

    // ---------- EVENT BINDINGS ----------
    ["sPsi","sTheta","sFnum"].forEach(id => document.getElementById(id).oninput = drawScheimpflug);
    document.getElementById("chkQuad").onchange = drawPoints;
    document.getElementById("ptCanvas").onclick = ev => {
      const cv = ev.target, rect = cv.getBoundingClientRect();
      PTS.push([(ev.clientX - rect.left) / rect.width, (ev.clientY - rect.top) / rect.height]);
      drawPoints();
    };
    document.getElementById("sPsf").oninput = drawMtfSpecimen;
    document.getElementById("isoCanvas").onmousemove = ev => {
      const cv = ev.target, rect = cv.getBoundingClientRect();
      VPOS = [Math.min(0.92, Math.max(0.08, (ev.clientX - rect.left) / rect.width)), Math.min(0.90, Math.max(0.10, (ev.clientY - rect.top) / rect.height))];
      drawIsovist();
    };

    drawScheimpflug(); genPoints("clustered"); setSpecimen("ink"); drawIsovist(); renderStruct();
  </script>
</body>
</html>
"""


def render_optics_workbench_html() -> bytes:
    """Return UTF-8 HTML bytes for the offline interactive Theorem 14 Optical & Spatial Workbench."""
    return OPTICS_WORKBENCH_HTML.encode("utf-8")

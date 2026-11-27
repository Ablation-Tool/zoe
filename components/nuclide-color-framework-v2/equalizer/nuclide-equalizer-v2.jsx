import { useState, useMemo, useCallback } from "react";

const AXES = [
  { key: "c", name: "Compression", desc: "verbose ↔ terse" },
  { key: "v", name: "Creativity", desc: "literal ↔ inventive" },
  { key: "t", name: "Transparency", desc: "opaque ↔ exposed" },
  { key: "w", name: "Warmth", desc: "clinical ↔ present" },
  { key: "a", name: "Autonomy", desc: "following ↔ self-directed" },
  { key: "k", name: "Certainty", desc: "hedged ↔ committed" },
];

const M = [
  [ 1.0, -0.5, -0.7,  0.0,  0.0,  0.5],
  [-0.5,  1.0,  0.0,  0.5,  0.0, -0.4],
  [-0.7,  0.0,  1.0,  0.0,  0.0,  0.4],
  [ 0.0,  0.5,  0.0,  1.0, -0.3,  0.0],
  [ 0.0,  0.0,  0.0, -0.3,  1.0,  0.4],
  [ 0.5, -0.4,  0.4,  0.0,  0.4,  1.0],
];

const Y0_OK = [0.62, 0.0, 0.0];
const P_OK = [
  [-0.3299, -0.035623, -0.028963,  0.091293, -0.103381,  0.104475],
  [-0.126978, -0.08094, -0.100715, -0.281324, -0.089802, -0.117015],
  [-0.208551,  0.228231, -0.223176, -0.263458, -0.239926, -0.070004],
];

const PRESETS = {
  home:    { name: "Home #2DB2BF", values: [89, 166, 153, 191, 140, 179] },
  mondo:   { name: "Mondō", values: [220, 40, 30, 80, 120, 230] },
  koan:    { name: "Kōan", values: [40, 200, 220, 150, 140, 130] },
  riff:    { name: "Riff", values: [50, 250, 60, 210, 220, 160] },
  trace:   { name: "Trace", values: [128, 128, 255, 128, 128, 128] },
  garlic:  { name: "Garlic", values: [100, 150, 120, 140, 240, 220] },
  neutral: { name: "Gray", values: [128, 128, 128, 128, 128, 128] },
  cascade: { name: "Cascade", values: [210, 35, 25, 45, 15, 250] },
};

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const linearToSrgb = (c) => {
  const cc = clamp(c, 0, 1);
  return cc <= 0.0031308 ? 12.92 * cc : 1.055 * Math.pow(cc, 1 / 2.4) - 0.055;
};

function postureToOKLabHex(xNorm) {
  const xbar = 128 / 255;
  const [L, a, b] = Y0_OK.map((y0i, r) => y0i + P_OK[r].reduce((s, p, j) => s + p * (xNorm[j] - xbar), 0));
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  const lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
  const rgb = [lr, lg, lb].map((v) => Math.round(linearToSrgb(v) * 255));
  return "#" + rgb.map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase();
}

export default function NuclideEqualizerV2() {
  const [raw, setRaw] = useState([...PRESETS.home.values]);
  const [activePreset, setActivePreset] = useState("home");

  const xNorm = useMemo(() => raw.map((v) => v / 255), [raw]);
  const effective = useMemo(
    () => xNorm.map((xi, i) => clamp(xi + M[i].reduce((s, mij, j) => s + (mij - (i === j ? 1 : 0)) * (xNorm[j] - 0.5), 0), 0, 1)),
    [xNorm]
  );

  const fidelity = useMemo(() => {
    const d = Math.sqrt(effective.reduce((s, v, i) => s + (v - xNorm[i]) ** 2, 0));
    return 1 - d / Math.sqrt(6);
  }, [effective, xNorm]);

  const bindingEnergy = useMemo(() => {
    const dx = xNorm.map((v) => v - 0.5);
    let sum = 0;
    for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) sum += dx[i] * (M[i][j] - (i === j ? 1 : 0)) * dx[j];
    return -0.5 * sum;
  }, [xNorm]);

  const hexColor = useMemo(() => postureToOKLabHex(xNorm), [xNorm]);

  const onSlide = useCallback((idx, val) => {
    setRaw((prev) => prev.map((v, i) => (i === idx ? clamp(parseInt(val, 10) || 0, 0, 255) : v)));
    setActivePreset(null);
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#0C151B", color: "#F4EFE6", fontFamily: "ui-monospace, monospace", padding: 24 }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <div style={{ fontSize: 11, letterSpacing: 2, color: "#2DB2BF", marginBottom: 4 }}>NUCLIDE RESEARCH · v2 SPECTROMETER</div>
        <h2 style={{ margin: "0 0 18px" }}>Nuclide Color Equalizer v2</h2>
        <div style={{ display: "flex", gap: 14, marginBottom: 18 }}>
          <div style={{ flex: 1, height: 86, borderRadius: 10, background: hexColor, display: "flex", alignItems: "flex-end", padding: 12, fontWeight: 700, fontSize: 18 }}>
            {hexColor}
          </div>
          <div style={{ width: 145, borderRadius: 10, background: "#182731", border: "1px solid #2A4252", padding: 12, textAlign: "center" }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: "#2DB2BF" }}>{(fidelity * 100).toFixed(0)}%</div>
            <div style={{ fontSize: 10, color: "#A3B8C4" }}>C_fid · E={bindingEnergy.toFixed(3)}</div>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 18 }}>
          {Object.entries(PRESETS).map(([k, p]) => (
            <button
              key={k}
              onClick={() => { setRaw([...p.values]); setActivePreset(k); }}
              style={{
                padding: "6px 10px",
                borderRadius: 6,
                border: activePreset === k ? "1px solid #2DB2BF" : "1px solid #2A4252",
                background: activePreset === k ? "rgba(45,178,191,0.18)" : "#182731",
                color: "#F4EFE6",
                cursor: "pointer",
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {AXES.map((ax, i) => (
            <div key={ax.key}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                <span><strong>{ax.name}</strong> <span style={{ color: "#6C8696" }}>{ax.desc}</span></span>
                <span>{raw[i]} <span style={{ color: "#2DB2BF" }}>→ {(effective[i] * 100).toFixed(0)}%</span></span>
              </div>
              <input type="range" min="0" max="255" value={raw[i]} onChange={(e) => onSlide(i, e.target.value)} style={{ width: "100%" }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

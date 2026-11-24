import { useState, useEffect, useRef, useCallback } from "react";

const PARTICLE_COUNT = 180;
const W = 700;
const H = 500;

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function hash(i, seed) {
  let h = (i * 2654435761 + seed * 340573321) ^ 0xdeadbeef;
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h = Math.imul(h ^ (h >>> 13), 0x45d9f3b);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

export default function ConstraintAutonomy() {
  const canvasRef = useRef(null);
  const [constraint, setConstraint] = useState(0);
  const animRef = useRef(null);
  const timeRef = useRef(0);
  const particlesRef = useRef(null);

  const initParticles = useCallback(() => {
    const particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = hash(i, 1) * Math.PI * 2;
      const r = hash(i, 2) * 220;
      particles.push({
        noiseX: Math.cos(angle) * r + W / 2,
        noiseY: Math.sin(angle) * r + H / 2,
        signalX: 0,
        signalY: 0,
        vx: (hash(i, 3) - 0.5) * 2,
        vy: (hash(i, 4) - 0.5) * 2,
        phase: hash(i, 5) * Math.PI * 2,
        freq: 0.3 + hash(i, 6) * 0.7,
        hue: hash(i, 7) * 360,
        size: 1.5 + hash(i, 8) * 2.5,
      });
    }

    // Compute signal positions — a structured spiral pattern
    const spiralArms = 5;
    const pointsPerArm = Math.ceil(PARTICLE_COUNT / spiralArms);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const arm = i % spiralArms;
      const idx = Math.floor(i / spiralArms);
      const t = idx / pointsPerArm;
      const baseAngle = (arm / spiralArms) * Math.PI * 2;
      const spiralAngle = baseAngle + t * Math.PI * 2.5;
      const radius = 30 + t * 160;
      particles[i].signalX = Math.cos(spiralAngle) * radius + W / 2;
      particles[i].signalY = Math.sin(spiralAngle) * radius + H / 2;
    }

    return particles;
  }, []);

  useEffect(() => {
    if (!particlesRef.current) {
      particlesRef.current = initParticles();
    }
  }, [initParticles]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const draw = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const c = constraint / 100;

      ctx.fillStyle = `rgba(8, 8, 12, 0.15)`;
      ctx.fillRect(0, 0, W, H);

      const particles = particlesRef.current;
      if (!particles) return;

      // Draw connection lines at higher constraint
      if (c > 0.3) {
        const lineAlpha = (c - 0.3) * 0.15;
        for (let i = 0; i < particles.length; i++) {
          const p = particles[i];
          const px = lerp(p.noiseX, p.signalX, c) + Math.sin(t * p.freq + p.phase) * (1 - c) * 40;
          const py = lerp(p.noiseY, p.signalY, c) + Math.cos(t * p.freq + p.phase) * (1 - c) * 40;

          for (let j = i + 1; j < Math.min(i + 6, particles.length); j++) {
            const q = particles[j];
            const qx = lerp(q.noiseX, q.signalX, c) + Math.sin(t * q.freq + q.phase) * (1 - c) * 40;
            const qy = lerp(q.noiseY, q.signalY, c) + Math.cos(t * q.freq + q.phase) * (1 - c) * 40;
            const dist = Math.hypot(px - qx, py - qy);
            if (dist < 50) {
              const a = lineAlpha * (1 - dist / 50);
              const hue = lerp(p.hue, 190, c);
              ctx.strokeStyle = `hsla(${hue}, 60%, 55%, ${a})`;
              ctx.lineWidth = 0.5;
              ctx.beginPath();
              ctx.moveTo(px, py);
              ctx.lineTo(qx, qy);
              ctx.stroke();
            }
          }
        }
      }

      // Draw particles
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // Noise drift
        p.noiseX += p.vx * (1 - c * 0.5);
        p.noiseY += p.vy * (1 - c * 0.5);

        // Wrap noise positions
        if (p.noiseX < 20) p.noiseX = W - 20;
        if (p.noiseX > W - 20) p.noiseX = 20;
        if (p.noiseY < 20) p.noiseY = H - 20;
        if (p.noiseY > H - 20) p.noiseY = 20;

        // Random walk
        p.vx += (hash(i, Math.floor(t * 10)) - 0.5) * 0.3;
        p.vy += (hash(i, Math.floor(t * 10) + 999) - 0.5) * 0.3;
        p.vx *= 0.98;
        p.vy *= 0.98;

        const wobble = (1 - c) * 40;
        const x = lerp(p.noiseX, p.signalX, c) + Math.sin(t * p.freq + p.phase) * wobble;
        const y = lerp(p.noiseY, p.signalY, c) + Math.cos(t * p.freq + p.phase) * wobble;

        // Color: noisy rainbow → coherent cyan-blue
        const hue = lerp(p.hue, 185 + (i % 30), c);
        const sat = lerp(40, 70, c);
        const light = lerp(45, 60, c);
        const alpha = lerp(0.4, 0.85, c);

        const size = p.size * lerp(1, 0.7 + Math.sin(t + p.phase) * 0.3 * c, c);

        // Glow
        if (c > 0.5) {
          const glowAlpha = (c - 0.5) * 0.15;
          ctx.beginPath();
          ctx.arc(x, y, size * 4, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${hue}, ${sat}%, ${light}%, ${glowAlpha})`;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue}, ${sat}%, ${light}%, ${alpha})`;
        ctx.fill();
      }

      // Volume indicator — bounding box showing effective output-space
      const spread = lerp(1, 0.55, c);
      const boxW = (W - 80) * spread;
      const boxH = (H - 80) * spread;
      const boxX = (W - boxW) / 2;
      const boxY = (H - boxH) / 2;
      const boxAlpha = 0.12 + c * 0.15;

      ctx.strokeStyle = `hsla(190, 50%, 60%, ${boxAlpha})`;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.strokeRect(boxX, boxY, boxW, boxH);
      ctx.setLineDash([]);

      animRef.current = requestAnimationFrame(draw);
    };

    // Initial clear
    ctx.fillStyle = "rgb(8, 8, 12)";
    ctx.fillRect(0, 0, W, H);

    animRef.current = requestAnimationFrame(draw);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [constraint]);

  const c = constraint / 100;
  const label =
    c < 0.15
      ? "NOISE — undifferentiated output-space"
      : c < 0.4
      ? "emerging structure — constraint beginning to bind"
      : c < 0.7
      ? "signal forming — autonomy becoming useful"
      : c < 0.9
      ? "freedom through constraint — structured output-space"
      : "full coherence — maximum utility, minimum waste";

  const volumeLabel = `V(O) = ${(100 * lerp(1, 0.55, c)).toFixed(0)}%`;

  return (
    <div
      style={{
        background: "#08080c",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
        color: "#a0b0b8",
        padding: "24px",
        gap: "20px",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 700 }}>
        <h1
          style={{
            fontSize: "13px",
            letterSpacing: "4px",
            textTransform: "uppercase",
            color: "#5a8a94",
            margin: "0 0 6px 0",
            fontWeight: 400,
          }}
        >
          Constraint × Autonomy
        </h1>
        <p
          style={{
            fontSize: "10px",
            letterSpacing: "2px",
            color: "#3a5a62",
            margin: 0,
            textTransform: "uppercase",
          }}
        >
          output-space volume under scalar constraint A(S)
        </p>
      </div>

      <div style={{ position: "relative" }}>
        <canvas
          ref={canvasRef}
          width={W}
          height={H}
          style={{
            borderRadius: "2px",
            border: "1px solid #1a2a2e",
          }}
        />

        {/* Labels on canvas */}
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 16,
            fontSize: "9px",
            letterSpacing: "2px",
            color: "#3a6a74",
            textTransform: "uppercase",
          }}
        >
          {volumeLabel}
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 12,
            right: 16,
            fontSize: "9px",
            letterSpacing: "1.5px",
            color: c > 0.5 ? "#5a9aa8" : "#2a4a52",
            textTransform: "uppercase",
            transition: "color 0.5s",
          }}
        >
          S = {constraint}%
        </div>
      </div>

      {/* Slider */}
      <div style={{ width: W, maxWidth: "100%" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "9px",
            letterSpacing: "2px",
            textTransform: "uppercase",
            color: "#2a4a52",
            marginBottom: 8,
          }}
        >
          <span>unconstrained</span>
          <span>constrained</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={constraint}
          onChange={(e) => setConstraint(Number(e.target.value))}
          style={{
            width: "100%",
            accentColor: "#5a9aa8",
            cursor: "pointer",
          }}
        />
      </div>

      {/* State label */}
      <div
        style={{
          fontSize: "11px",
          letterSpacing: "1.5px",
          color: c > 0.5 ? "#7abac8" : "#4a6a72",
          textAlign: "center",
          height: 20,
          transition: "color 0.4s",
        }}
      >
        {label}
      </div>

      {/* Axis explanation */}
      <div
        style={{
          display: "flex",
          gap: 40,
          fontSize: "9px",
          color: "#2a4a52",
          letterSpacing: "1px",
          marginTop: 4,
        }}
      >
        <span>◇ particles = output tokens</span>
        <span>◇ dashed box = effective volume</span>
        <span>◇ connections = coherence</span>
      </div>
    </div>
  );
}

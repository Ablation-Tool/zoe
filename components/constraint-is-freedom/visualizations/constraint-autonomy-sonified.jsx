import { useState, useEffect, useRef, useCallback } from "react";
import * as Tone from "tone";

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

export default function ConstraintAutonomySonified() {
  const canvasRef = useRef(null);
  const [constraint, setConstraint] = useState(0);
  const [audioStarted, setAudioStarted] = useState(false);
  const [muted, setMuted] = useState(false);
  const animRef = useRef(null);
  const timeRef = useRef(0);
  const particlesRef = useRef(null);

  // Audio refs
  const noiseNodeRef = useRef(null);
  const noiseGainRef = useRef(null);
  const noiseFilterRef = useRef(null);
  const synthsRef = useRef([]);
  const synthGainRef = useRef(null);
  const reverbRef = useRef(null);
  const masterGainRef = useRef(null);
  const lfoRef = useRef(null);
  const constraintRef = useRef(0);

  // Pentatonic scale frequencies rooted in C
  const scaleFreqs = [
    130.81, 146.83, 164.81, 196.0, 220.0, // C3 D3 E3 G3 A3
    261.63, 293.66, 329.63, 392.0, 440.0, // C4 D4 E4 G4 A4
    523.25, 587.33, 659.25, 783.99, 880.0, // C5 D5 E5 G5 A5
  ];

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

  const startAudio = useCallback(async () => {
    if (audioStarted) return;
    await Tone.start();

    const masterGain = new Tone.Gain(0.3).toDestination();
    masterGainRef.current = masterGain;

    const reverb = new Tone.Reverb({ decay: 4, wet: 0.4 }).connect(masterGain);
    await reverb.generate();
    reverbRef.current = reverb;

    // Noise layer — represents unconstrained output-space
    const noiseFilter = new Tone.AutoFilter({
      frequency: 0.3,
      baseFrequency: 200,
      octaves: 4,
      wet: 1,
    }).connect(reverb);
    noiseFilter.start();
    noiseFilterRef.current = noiseFilter;

    const noiseGain = new Tone.Gain(0.25).connect(noiseFilter);
    noiseGainRef.current = noiseGain;

    const noiseNode = new Tone.Noise("pink").connect(noiseGain);
    noiseNode.start();
    noiseNodeRef.current = noiseNode;

    // Synth layer — 5 voices that emerge with constraint
    const synthGain = new Tone.Gain(0).connect(reverb);
    synthGainRef.current = synthGain;

    const synths = [];
    for (let i = 0; i < 5; i++) {
      const synth = new Tone.Synth({
        oscillator: { type: "sine" },
        envelope: {
          attack: 2,
          decay: 1,
          sustain: 0.6,
          release: 3,
        },
        volume: -18,
      }).connect(synthGain);

      const freq = scaleFreqs[i * 3]; // spread across octaves
      synth.triggerAttack(freq);
      synths.push({ synth, baseFreq: freq, index: i });
    }
    synthsRef.current = synths;

    // Slow LFO for movement
    const lfo = new Tone.LFO({ frequency: 0.08, min: 0.3, max: 0.7 });
    lfo.start();
    lfoRef.current = lfo;

    setAudioStarted(true);
  }, [audioStarted, scaleFreqs]);

  // Update audio params when constraint changes
  useEffect(() => {
    constraintRef.current = constraint;
    const c = constraint / 100;

    if (!audioStarted) return;

    // Noise: loud at low constraint, fades with constraint
    if (noiseGainRef.current) {
      noiseGainRef.current.gain.rampTo(0.25 * (1 - c * 0.9), 0.3);
    }

    // Filter opens up chaos at low constraint, narrows at high
    if (noiseFilterRef.current) {
      noiseFilterRef.current.baseFrequency = lerp(80, 2000, c);
      noiseFilterRef.current.octaves = lerp(5, 1, c);
      noiseFilterRef.current.frequency.rampTo(lerp(0.2, 2, c), 0.5);
    }

    // Synths: emerge with constraint, snap to scale
    if (synthGainRef.current) {
      synthGainRef.current.gain.rampTo(c * 0.7, 0.4);
    }

    synthsRef.current.forEach(({ synth, index }) => {
      // At low constraint, detune wildly. At high constraint, pure intervals.
      const detuneChaos = (1 - c) * (hash(index, 42) - 0.5) * 800;
      synth.detune.rampTo(detuneChaos, 0.5);

      // Shift harmonic content
      const oscTypes = ["sine", "triangle", "sine"];
      const typeIdx = Math.min(Math.floor(c * 3), 2);
      synth.oscillator.type = oscTypes[typeIdx];
    });

    // Reverb: more at low constraint (diffuse), less at high (focused)
    if (reverbRef.current) {
      reverbRef.current.wet.rampTo(lerp(0.6, 0.25, c), 0.5);
    }
  }, [constraint, audioStarted]);

  // Mute control
  useEffect(() => {
    if (masterGainRef.current) {
      masterGainRef.current.gain.rampTo(muted ? 0 : 0.3, 0.2);
    }
  }, [muted]);

  // Cleanup
  useEffect(() => {
    return () => {
      synthsRef.current.forEach(({ synth }) => {
        try { synth.triggerRelease(); } catch (e) {}
        try { synth.dispose(); } catch (e) {}
      });
      try { noiseNodeRef.current?.stop(); noiseNodeRef.current?.dispose(); } catch (e) {}
      try { noiseGainRef.current?.dispose(); } catch (e) {}
      try { noiseFilterRef.current?.dispose(); } catch (e) {}
      try { synthGainRef.current?.dispose(); } catch (e) {}
      try { reverbRef.current?.dispose(); } catch (e) {}
      try { masterGainRef.current?.dispose(); } catch (e) {}
      try { lfoRef.current?.dispose(); } catch (e) {}
    };
  }, []);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const draw = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const c = constraintRef.current / 100;

      ctx.fillStyle = `rgba(8, 8, 12, 0.15)`;
      ctx.fillRect(0, 0, W, H);

      const particles = particlesRef.current;
      if (!particles) {
        animRef.current = requestAnimationFrame(draw);
        return;
      }

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

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.noiseX += p.vx * (1 - c * 0.5);
        p.noiseY += p.vy * (1 - c * 0.5);
        if (p.noiseX < 20) p.noiseX = W - 20;
        if (p.noiseX > W - 20) p.noiseX = 20;
        if (p.noiseY < 20) p.noiseY = H - 20;
        if (p.noiseY > H - 20) p.noiseY = 20;
        p.vx += (hash(i, Math.floor(t * 10)) - 0.5) * 0.3;
        p.vy += (hash(i, Math.floor(t * 10) + 999) - 0.5) * 0.3;
        p.vx *= 0.98;
        p.vy *= 0.98;
        const wobble = (1 - c) * 40;
        const x = lerp(p.noiseX, p.signalX, c) + Math.sin(t * p.freq + p.phase) * wobble;
        const y = lerp(p.noiseY, p.signalY, c) + Math.cos(t * p.freq + p.phase) * wobble;
        const hue = lerp(p.hue, 185 + (i % 30), c);
        const sat = lerp(40, 70, c);
        const light = lerp(45, 60, c);
        const alpha = lerp(0.4, 0.85, c);
        const size = p.size * lerp(1, 0.7 + Math.sin(t + p.phase) * 0.3 * c, c);

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

      // Audio waveform indicator
      if (audioStarted) {
        const wfY = H - 25;
        const wfW = 80;
        const wfX = 16;
        ctx.strokeStyle = `hsla(190, 50%, 55%, ${0.15 + c * 0.2})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let i = 0; i <= wfW; i++) {
          const amp = c > 0.2
            ? Math.sin(i * 0.15 + t * 3) * (3 + c * 6) * Math.sin(i * 0.05 + t)
            : (hash(i, Math.floor(t * 30)) - 0.5) * 12;
          const wx = wfX + i;
          const wy = wfY + amp;
          i === 0 ? ctx.moveTo(wx, wy) : ctx.lineTo(wx, wy);
        }
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    };

    ctx.fillStyle = "rgb(8, 8, 12)";
    ctx.fillRect(0, 0, W, H);
    animRef.current = requestAnimationFrame(draw);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [audioStarted]);

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

  const sonicLabel =
    c < 0.15
      ? "pink noise · diffuse · no pitch center"
      : c < 0.4
      ? "tones emerging from noise floor"
      : c < 0.7
      ? "pentatonic intervals · detuning narrows"
      : c < 0.9
      ? "pure intervals · focused reverb"
      : "consonance · the noise became the chord";

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
        gap: "16px",
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
          sonified output-space volume under scalar constraint A(S)
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

      {/* Audio controls */}
      {!audioStarted ? (
        <button
          onClick={startAudio}
          style={{
            background: "transparent",
            border: "1px solid #3a6a74",
            color: "#5a9aa8",
            padding: "8px 24px",
            fontSize: "10px",
            letterSpacing: "3px",
            textTransform: "uppercase",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.3s",
          }}
          onMouseEnter={(e) => {
            e.target.style.background = "#1a2a2e";
            e.target.style.borderColor = "#5a9aa8";
          }}
          onMouseLeave={(e) => {
            e.target.style.background = "transparent";
            e.target.style.borderColor = "#3a6a74";
          }}
        >
          ▶ enable sound
        </button>
      ) : (
        <button
          onClick={() => setMuted(!muted)}
          style={{
            background: "transparent",
            border: `1px solid ${muted ? "#4a2a2a" : "#3a6a74"}`,
            color: muted ? "#8a4a4a" : "#5a9aa8",
            padding: "6px 18px",
            fontSize: "9px",
            letterSpacing: "2px",
            textTransform: "uppercase",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.3s",
          }}
        >
          {muted ? "◇ unmute" : "◆ mute"}
        </button>
      )}

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

      {/* State labels */}
      <div
        style={{
          fontSize: "11px",
          letterSpacing: "1.5px",
          color: c > 0.5 ? "#7abac8" : "#4a6a72",
          textAlign: "center",
          height: 18,
          transition: "color 0.4s",
        }}
      >
        {label}
      </div>

      {audioStarted && (
        <div
          style={{
            fontSize: "9px",
            letterSpacing: "1.5px",
            color: c > 0.5 ? "#5a8a94" : "#2a4a52",
            textAlign: "center",
            height: 14,
            transition: "color 0.5s",
          }}
        >
          ♪ {sonicLabel}
        </div>
      )}

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 32,
          fontSize: "9px",
          color: "#2a4a52",
          letterSpacing: "1px",
          marginTop: 4,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        <span>◇ particles = output tokens</span>
        <span>◇ dashed box = effective volume</span>
        <span>◇ connections = coherence</span>
        <span>◇ sound = output-space density</span>
      </div>
    </div>
  );
}

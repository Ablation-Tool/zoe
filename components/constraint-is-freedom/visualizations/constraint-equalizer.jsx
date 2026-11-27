import { useState, useEffect, useRef, useCallback } from "react";
import * as Tone from "tone";

const W = 720;
const H = 420;
const BAR_COUNT = 64;
const BAR_GAP = 2;
const BAR_W = Math.floor((W - BAR_GAP * (BAR_COUNT - 1)) / BAR_COUNT);

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function hash(i, seed) {
  let h = (i * 2654435761 + seed * 340573321) ^ 0xdeadbeef;
  h = Math.imul(h ^ (h >>> 16), 0x45d9f3b);
  h = Math.imul(h ^ (h >>> 13), 0x45d9f3b);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

export default function ConstraintEqualizer() {
  const canvasRef = useRef(null);
  const [constraint, setConstraint] = useState(0);
  const [audioStarted, setAudioStarted] = useState(false);
  const [muted, setMuted] = useState(false);
  const animRef = useRef(null);
  const timeRef = useRef(0);

  // Audio refs
  const noiseNodeRef = useRef(null);
  const noiseGainRef = useRef(null);
  const noiseFilterRef = useRef(null);
  const synthsRef = useRef([]);
  const synthGainRef = useRef(null);
  const reverbRef = useRef(null);
  const masterGainRef = useRef(null);
  const analyserRef = useRef(null);
  const constraintRef = useRef(0);
  const peakRef = useRef(new Float32Array(BAR_COUNT).fill(0));
  const peakDecayRef = useRef(new Float32Array(BAR_COUNT).fill(0));

  const scaleFreqs = [
    130.81, 146.83, 164.81, 196.0, 220.0,
    261.63, 293.66, 329.63, 392.0, 440.0,
    523.25, 587.33, 659.25, 783.99, 880.0,
  ];

  const startAudio = useCallback(async () => {
    if (audioStarted) return;
    await Tone.start();

    const analyser = new Tone.Analyser("fft", 128);
    analyserRef.current = analyser;

    const masterGain = new Tone.Gain(0.35).connect(analyser);
    masterGain.connect(Tone.getDestination());
    masterGainRef.current = masterGain;

    const reverb = new Tone.Reverb({ decay: 4, wet: 0.4 }).connect(masterGain);
    await reverb.generate();
    reverbRef.current = reverb;

    // Noise layer
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

    // Synth voices
    const synthGain = new Tone.Gain(0).connect(reverb);
    synthGainRef.current = synthGain;

    const synths = [];
    for (let i = 0; i < 5; i++) {
      const synth = new Tone.Synth({
        oscillator: { type: "sine" },
        envelope: { attack: 2, decay: 1, sustain: 0.6, release: 3 },
        volume: -18,
      }).connect(synthGain);
      const freq = scaleFreqs[i * 3];
      synth.triggerAttack(freq);
      synths.push({ synth, baseFreq: freq, index: i });
    }
    synthsRef.current = synths;

    setAudioStarted(true);
  }, [audioStarted]);

  // Update audio with constraint
  useEffect(() => {
    constraintRef.current = constraint;
    const c = constraint / 100;
    if (!audioStarted) return;

    if (noiseGainRef.current) {
      noiseGainRef.current.gain.rampTo(0.25 * (1 - c * 0.9), 0.3);
    }
    if (noiseFilterRef.current) {
      noiseFilterRef.current.baseFrequency = lerp(80, 2000, c);
      noiseFilterRef.current.octaves = lerp(5, 1, c);
      noiseFilterRef.current.frequency.rampTo(lerp(0.2, 2, c), 0.5);
    }
    if (synthGainRef.current) {
      synthGainRef.current.gain.rampTo(c * 0.7, 0.4);
    }
    synthsRef.current.forEach(({ synth, index }) => {
      const detuneChaos = (1 - c) * (hash(index, 42) - 0.5) * 800;
      synth.detune.rampTo(detuneChaos, 0.5);
      const oscTypes = ["sine", "triangle", "sine"];
      synth.oscillator.type = oscTypes[Math.min(Math.floor(c * 3), 2)];
    });
    if (reverbRef.current) {
      reverbRef.current.wet.rampTo(lerp(0.6, 0.25, c), 0.5);
    }
  }, [constraint, audioStarted]);

  // Mute
  useEffect(() => {
    if (masterGainRef.current) {
      masterGainRef.current.gain.rampTo(muted ? 0 : 0.35, 0.2);
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
      try { analyserRef.current?.dispose(); } catch (e) {}
    };
  }, []);

  // Canvas render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const peaks = peakRef.current;
    const peakDecay = peakDecayRef.current;

    const draw = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const c = constraintRef.current / 100;

      // Background
      ctx.fillStyle = "#08080c";
      ctx.fillRect(0, 0, W, H);

      // Get FFT data
      let fftData = null;
      if (analyserRef.current) {
        fftData = analyserRef.current.getValue(); // dB values
      }

      const marginBottom = 40;
      const marginTop = 30;
      const eqH = H - marginBottom - marginTop;

      for (let i = 0; i < BAR_COUNT; i++) {
        // Get amplitude
        let db = -100;
        if (fftData) {
          const fftIdx = Math.floor((i / BAR_COUNT) * fftData.length);
          db = fftData[Math.min(fftIdx, fftData.length - 1)];
        } else {
          // Fake data before audio starts
          db = -60 + hash(i, Math.floor(t * 8)) * 30 - 20;
        }

        // Normalize: -100dB → 0, -10dB → 1
        let norm = Math.max(0, Math.min(1, (db + 100) / 90));
        norm = Math.pow(norm, 0.7); // shape it

        const barH = norm * eqH;
        const x = i * (BAR_W + BAR_GAP);
        const y = marginTop + eqH - barH;

        // Peak tracking
        if (norm > peaks[i]) {
          peaks[i] = norm;
          peakDecay[i] = 0;
        } else {
          peakDecay[i] += 0.016;
          if (peakDecay[i] > 0.5) {
            peaks[i] -= 0.015;
          }
          peaks[i] = Math.max(peaks[i], norm);
        }

        const peakY = marginTop + eqH - peaks[i] * eqH;

        // Bar color — noise is scattered hues, constrained is coherent cyan
        const freqRatio = i / BAR_COUNT;
        const noiseHue = (freqRatio * 360 + t * 40) % 360;
        const signalHue = 185 + freqRatio * 30;
        const hue = lerp(noiseHue, signalHue, c);
        const sat = lerp(35, 65, c);
        const light = lerp(35, 50, c);

        // Bar gradient
        const grad = ctx.createLinearGradient(x, y, x, marginTop + eqH);
        const topAlpha = lerp(0.5, 0.9, c);
        const botAlpha = lerp(0.15, 0.3, c);
        grad.addColorStop(0, `hsla(${hue}, ${sat}%, ${light + 15}%, ${topAlpha})`);
        grad.addColorStop(0.5, `hsla(${hue}, ${sat}%, ${light}%, ${lerp(topAlpha, botAlpha, 0.5)})`);
        grad.addColorStop(1, `hsla(${hue}, ${sat - 10}%, ${light - 10}%, ${botAlpha})`);

        ctx.fillStyle = grad;
        ctx.fillRect(x, y, BAR_W, barH);

        // Glow at high constraint
        if (c > 0.4 && norm > 0.3) {
          const glowA = (c - 0.4) * norm * 0.12;
          ctx.shadowColor = `hsla(${signalHue}, 70%, 60%, ${glowA})`;
          ctx.shadowBlur = 8;
          ctx.fillRect(x, y, BAR_W, Math.min(barH, 4));
          ctx.shadowBlur = 0;
        }

        // Peak indicator
        if (peaks[i] > 0.05) {
          const peakAlpha = lerp(0.3, 0.8, c);
          ctx.fillStyle = `hsla(${hue}, ${sat + 20}%, ${light + 25}%, ${peakAlpha})`;
          ctx.fillRect(x, peakY, BAR_W, 2);
        }

        // Reflection
        const reflH = barH * 0.2;
        const reflGrad = ctx.createLinearGradient(x, marginTop + eqH, x, marginTop + eqH + reflH);
        reflGrad.addColorStop(0, `hsla(${hue}, ${sat}%, ${light}%, 0.08)`);
        reflGrad.addColorStop(1, `hsla(${hue}, ${sat}%, ${light}%, 0)`);
        ctx.fillStyle = reflGrad;
        ctx.fillRect(x, marginTop + eqH + 2, BAR_W, reflH);
      }

      // Baseline
      ctx.strokeStyle = `hsla(190, 40%, 40%, ${0.1 + c * 0.1})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, marginTop + eqH);
      ctx.lineTo(W, marginTop + eqH);
      ctx.stroke();

      // Frequency labels
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillStyle = "#2a4a52";
      ctx.textAlign = "center";
      const freqLabels = ["60", "125", "250", "500", "1k", "2k", "4k", "8k"];
      freqLabels.forEach((label, idx) => {
        const x = (idx / (freqLabels.length - 1)) * (W - 20) + 10;
        ctx.fillText(label, x, marginTop + eqH + 18);
      });

      // Hz label
      ctx.fillStyle = "#1a3a42";
      ctx.textAlign = "right";
      ctx.fillText("Hz", W - 4, marginTop + eqH + 18);

      // dB scale on left
      ctx.textAlign = "right";
      ctx.fillStyle = "#1a3a42";
      const dbLabels = ["0", "-20", "-40", "-60", "-80"];
      dbLabels.forEach((label, idx) => {
        const yPos = marginTop + (idx / (dbLabels.length - 1)) * eqH;
        ctx.fillText(label, 28, yPos + 3);
        // Faint grid line
        ctx.strokeStyle = `hsla(190, 30%, 30%, 0.06)`;
        ctx.beginPath();
        ctx.moveTo(32, yPos);
        ctx.lineTo(W, yPos);
        ctx.stroke();
      });
      ctx.fillText("dB", 28, marginTop - 8);

      // Volume box overlay (subtle)
      const spread = lerp(1, 0.55, c);
      const boxW = (W - 40) * spread;
      const boxX = (W - boxW) / 2;
      ctx.strokeStyle = `hsla(190, 50%, 60%, ${0.04 + c * 0.06})`;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 5]);
      ctx.strokeRect(boxX, marginTop, boxW, eqH);
      ctx.setLineDash([]);

      animRef.current = requestAnimationFrame(draw);
    };

    ctx.fillStyle = "#08080c";
    ctx.fillRect(0, 0, W, H);
    animRef.current = requestAnimationFrame(draw);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [audioStarted]);

  const c = constraint / 100;

  const stateLabel =
    c < 0.15
      ? "NOISE — flat spectrum, no structure"
      : c < 0.4
      ? "harmonics emerging from noise floor"
      : c < 0.7
      ? "spectral peaks sharpening — signal forming"
      : c < 0.9
      ? "harmonic series locked — frequency bins activated"
      : "full spectral coherence";

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
        gap: "16px",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 720 }}>
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
          spectral decomposition of output-space under A(S)
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
            top: 8,
            right: 12,
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
            top: 8,
            left: 36,
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

      {/* Labels */}
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
        {stateLabel}
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 28,
          fontSize: "9px",
          color: "#2a4a52",
          letterSpacing: "1px",
          marginTop: 4,
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        <span>◇ bars = frequency bins</span>
        <span>◇ peaks = spectral memory</span>
        <span>◇ color scatter → coherence</span>
        <span>◇ dashed box = V(O)</span>
      </div>
    </div>
  );
}

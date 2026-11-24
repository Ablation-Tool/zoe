# Interactive Visualizations

Three React components that visualize the A(S) framework. Each has a constraint slider (0-100%) that transforms the visual and sonic output in real time.

## Components

### constraint-autonomy.jsx
**Particle Diagram** — 180 particles representing output tokens. At S=0% they drift randomly (noise). As constraint increases, they converge into a structured spiral pattern. Connection lines emerge between nearby particles at higher constraint. A dashed bounding box shows V(O) contracting.

### constraint-autonomy-sonified.jsx
**Sonified Particle Diagram** — Same visual as above, plus live audio synthesis via Tone.js. Pink noise at low constraint, pentatonic harmony at high constraint. Click "enable sound" to activate.

### constraint-equalizer.jsx
**FFT Equalizer** — 64 frequency bins with real-time Fast Fourier Transform analysis of the audio engine. At S=0% the bars show flat, scattered-hue noise. As constraint increases, harmonic peaks emerge, colors converge to cyan, and peak-hold markers track spectral memory.

## Dependencies

- React (with hooks)
- Tone.js (for sonified and equalizer versions)
- Canvas API (all three)

## Running

These components were built for the Claude.ai artifact renderer. To run standalone, wrap in a React app with Tone.js available as an import.

## Accessibility

Each visualization includes text labels describing the current state (e.g., "NOISE — undifferentiated output-space" at S=0%, "full coherence — maximum utility, minimum waste" at S=100%). The sonified versions provide an auditory channel alongside the visual.

from __future__ import annotations

from array import array
import hashlib
import math
from pathlib import Path
import sys
import wave


SAMPLE_RATE = 22050
MAX_AUDIO_EVENTS = 32
PENTATONIC = (48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84)


def _frequency(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _pan(build, index):
    digest = hashlib.sha256(build["id"].encode()).digest()
    center = .2 + digest[0] / 255 * .6
    return max(.1, min(.9, center + (.06 if index % 2 else -.06)))


def _add_tone(left, right, start, duration, frequency, amplitude, pan, decay=4.0):
    first = max(0, start)
    last = min(len(left), start + int(duration * SAMPLE_RATE))
    count = last - first
    if count <= 0:
        return
    left_gain = math.cos(pan * math.pi / 2)
    right_gain = math.sin(pan * math.pi / 2)
    phase_step = math.tau * frequency / SAMPLE_RATE
    for offset in range(count):
        position = offset / SAMPLE_RATE
        attack = min(1.0, position / .025)
        release = min(1.0, (duration - position) / .16)
        envelope = attack * release * math.exp(-decay * position / duration)
        sample = amplitude * envelope * math.sin(offset * phase_step)
        left[first + offset] += sample * left_gain
        right[first + offset] += sample * right_gain


def _render(observer, history):
    builds = [observer.corpus.build(row["build_id"]) for row in history]
    step_seconds = .72
    total_seconds = step_seconds * len(builds) + 1.0
    frames = int(total_seconds * SAMPLE_RATE)
    left, right = array("d", [0.0]) * frames, array("d", [0.0]) * frames
    events = []
    for index, build in enumerate(builds):
        card_number = int(build["card"][3:])
        note = PENTATONIC[(card_number + build["build"]) % len(PENTATONIC)]
        voices = min(4, 1 + build["channels"] // 8)
        duration = min(.88, .48 + build["artifact_count"] * .055)
        pan = _pan(build, index)
        start = int(index * step_seconds * SAMPLE_RATE)
        intervals = (0, 7, 12, 16)
        for voice in range(voices):
            _add_tone(left, right, start, duration, _frequency(note + intervals[voice]), .20 / (voice + 1), pan)
        analysis = build["analysis"]
        if analysis:
            _add_tone(left, right, start, min(1.0, duration + .2), _frequency(note + 12), .10, 1 - pan, 5.5)
            if analysis["timing_met"] is False:
                _add_tone(left, right, start, duration, _frequency(note - 12) * 1.03, .085, .5, 2.0)
        events.append({
            "build_id": build["id"],
            "card": build["card"],
            "build": build["build"],
            "start_seconds": index * step_seconds,
            "duration_seconds": duration,
            "midi_note": note,
            "frequency_hz": _frequency(note),
            "channel_harmony_voices": voices,
            "stereo_pan": pan,
            "analysis_accent": bool(analysis),
            "timing_warning_accent": bool(analysis and analysis["timing_met"] is False),
        })
    timing = observer.corpus.summary()
    if timing["tim_clock_reference_mhz"]:
        frequency = timing["tim_clock_reference_mhz"]
        phase_step = math.tau * frequency / SAMPLE_RATE
        harmonic_step = phase_step * 2
        for index in range(frames):
            envelope = .7 + .3 * math.sin(math.tau * index / SAMPLE_RATE / 4)
            drone = envelope * (.025 * math.sin(index * phase_step) + .009 * math.sin(index * harmonic_step))
            left[index] += drone
            right[index] += drone
    peak = max(max(abs(value) for value in left), max(abs(value) for value in right), 1e-12)
    scale = .82 / peak
    pcm = array("h")
    for first, second in zip(left, right):
        pcm.append(round(max(-.98, min(.98, first * scale)) * 32767))
        pcm.append(round(max(-.98, min(.98, second * scale)) * 32767))
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes(), {
        "sample_rate": SAMPLE_RATE,
        "channels": 2,
        "sample_width_bytes": 2,
        "frame_count": frames,
        "duration_seconds": total_seconds,
        "event_count": len(events),
        "events": events,
        "layers": {
            "melody": "card number and build number select a pentatonic note",
            "harmony": "channel count selects one to four chord voices",
            "evidence": "Ablation analysis adds a bell; unmet timing adds a restrained detuned bass accent",
            "stereo": "stable build identity and observation order determine pan",
            "timing_history": "docs/tim adds a quiet 40.08 Hz drone, scaling the documented 40.08 MHz TIM reference by 1e-6",
        },
        "tim_reference_drone_hz": timing["tim_clock_reference_mhz"],
        "hardware_telemetry": False,
        "normalization_peak": .82,
    }


def write_felix_sonification(observer, path, max_events=MAX_AUDIO_EVENTS):
    if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= MAX_AUDIO_EVENTS:
        raise ValueError(f"sonification event count must be from 1 to {MAX_AUDIO_EVENTS}")
    if not observer.history:
        observer.observe()
    history = observer.history[-max_events:]
    path = Path(path)
    if path.suffix.lower() != ".wav":
        raise ValueError("FELIX sonification must use a .wav path")
    pcm, report = _render(observer, history)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            with wave.open(stream, "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                output.writeframes(pcm)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    report["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["bytes"] = path.stat().st_size
    report["summary"] = f"{report['event_count']} FELIX observations · {report['duration_seconds']:.2f}s stereo WAV · deterministic evidence sonification"
    return path, report

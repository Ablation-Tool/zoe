from __future__ import annotations

from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import wave
import zlib

from .evidence import demo_index
from .field import _canonical


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _integer(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _frequency(value):
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("frequency must be a positive finite value") from error
    if not 0 < result <= 1_000_000_000:
        raise ValueError("frequency must be in (0, 1000000000]")
    return result


def _time_text(value):
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def timing_replay(channels=24, event_count=64, frequency_mhz="40.08", buffer_limit=8, consume_every=3, index=None):
    channels = _integer(channels, "channel count", 1, 64)
    event_count = _integer(event_count, "event count", 1, 256)
    buffer_limit = _integer(buffer_limit, "buffer limit", 1, 64)
    consume_every = _integer(consume_every, "host consumption interval", 1, 64)
    frequency = _frequency(frequency_mhz)
    period = Fraction(1_000_000_000_000, 1) / frequency
    index = index or demo_index()
    bridge = index.bridge(1)
    observations = []
    descriptors = []
    occupancy = 0
    for sequence in range(1, event_count + 1):
        channel = (sequence - 1) % channels + 1
        consumed = sequence % consume_every == 0
        if consumed and occupancy:
            occupancy -= 1
        backpressure = occupancy >= buffer_limit
        descriptor_sequence = None
        if not backpressure:
            occupancy += 1
            descriptor_sequence = len(descriptors) + 1
            descriptor = {
                "sequence": descriptor_sequence,
                "channel": channel,
                "address": (channel - 1) * 4096 + descriptor_sequence * 256,
                "length": 256,
                "crc32": zlib.crc32(f"{channel}:{descriptor_sequence}:256".encode("ascii")),
            }
            descriptors.append(descriptor)
        observations.append({
            "sequence": sequence,
            "time_ps": _time_text((sequence - 1) * period / 2),
            "clock": (sequence - 1) % 2,
            "channel": channel,
            "trigger_id": sequence,
            "link_state": "clock-high" if sequence % 2 else "clock-low",
            "dma_status": "backpressure" if backpressure else "accepted",
            "buffer_occupancy": occupancy,
            "host_consumed": consumed,
            "descriptor_sequence": descriptor_sequence,
            "source_model": "synthetic-observation-replay",
        })
    result = {
        "schema_version": 1,
        "instrument": "zoe-timing-readout-twin",
        "model": "synthetic-observation-replay",
        "frequency_mhz": str(frequency),
        "clock_period_ratio_ps": [period.numerator, period.denominator],
        "channel_count": channels,
        "event_count": event_count,
        "buffer_limit": buffer_limit,
        "consume_every": consume_every,
        "source_bridge": bridge,
        "observations": observations,
        "descriptors": descriptors,
        "assumptions": [
            "The 40.08 MHz reference is a documented input to a synthetic pattern, not a measured clock here.",
            "Trigger identifiers, frames, DMA descriptors, occupancy, and backpressure are synthetic.",
            "The channel build is a demonstration only and does not describe a specific deployed device.",
        ],
        "hardware_accessed": False,
        "measured": False,
        "physical_connection_claimed": False,
    }
    result["digest"] = _digest(result)
    return result


def save_timeline(timeline, path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("timeline output must use a .json path")
    with path.open("x", encoding="utf-8") as stream:
        stream.write(_canonical(timeline) + "\n")
    return path


def load_timeline(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("timeline exceeds 8 MiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("instrument") != "zoe-timing-readout-twin":
        raise ValueError("unsupported timing replay")
    if data["digest"] != _digest({key: value for key, value in data.items() if key != "digest"}):
        raise ValueError("timeline digest mismatch")
    if not isinstance(data["observations"], list) or not 1 <= len(data["observations"]) <= 256 or len(data["observations"]) != data["event_count"]:
        raise ValueError("timeline observation bound or count mismatch")
    for index, event in enumerate(data["observations"], 1):
        if event["sequence"] != index or event["trigger_id"] != index or event["clock"] != (index - 1) % 2:
            raise ValueError("timeline event ordering is invalid")
    if data["hardware_accessed"] is not False or data["measured"] is not False or data["physical_connection_claimed"] is not False:
        raise ValueError("timeline contains an unsupported hardware claim")
    return data


def export_wav(timeline, path):
    if timeline.get("instrument") != "zoe-timing-readout-twin":
        raise ValueError("sonification requires a validated synthetic timeline")
    observations = timeline["observations"]
    if not 1 <= len(observations) <= 256:
        raise ValueError("sonification supports 1-256 observations")
    sample_rate = 8000
    samples_per_event = 400
    base_frequency = 220 + timeline["channel_count"] * 4
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        for event in observations:
            accent = 660 if event["dma_status"] == "backpressure" else 440 if event["clock"] else 330
            accent_gain = 0.12 if event["dma_status"] == "backpressure" else 0.025
            for index in range(samples_per_event):
                t = index / sample_rate
                fade = min(1.0, index / 20, (samples_per_event - index - 1) / 20)
                value = (
                    0.24 * math.sin(math.tau * base_frequency * t)
                    + 0.13 * math.sin(math.tau * 40.08 * t)
                    + accent_gain * math.sin(math.tau * accent * t)
                ) * fade
                output.writeframesraw(struct.pack("<h", round(value * 32767)))
        output.writeframes(b"")
    payload = buffer.getvalue()
    path = Path(path)
    if path.suffix.lower() != ".wav":
        raise ValueError("sonification output must use a .wav path")
    if not path.parent.is_dir():
        raise ValueError("sonification output directory does not exist")
    with path.open("xb") as stream:
        stream.write(payload)
    return path, {
        "instrument": "zoe-evidence-sonification",
        "path": str(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sample_rate": sample_rate,
        "samples_per_event": samples_per_event,
        "duration_seconds": len(observations) * samples_per_event / sample_rate,
        "evidence_sonification": True,
        "live_detector_sound": False,
        "alarm": False,
        "autoplay": False,
    }

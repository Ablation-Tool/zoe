from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import random

import numpy as np

from .loop import canonical, digest

GRID = 16
CENTERS = (4, 8, 12)
ACTIONS = ("attend_left", "hold", "attend_right", "abstain")
MAX_EVENTS = 200_000


def validate_events(events, grid=GRID, maximum=MAX_EVENTS):
    if isinstance(grid, bool) or not isinstance(grid, int) or not 4 <= grid <= 256:
        raise ValueError("event grid must be an integer from 4 to 256")
    if not isinstance(events, (list, tuple)) or len(events) > maximum:
        raise ValueError("events must be a bounded list or tuple")
    normalized = []
    for event in events:
        if isinstance(event, dict):
            values = (event.get("step"), event.get("x"), event.get("y"), event.get("polarity"))
        elif isinstance(event, (list, tuple)) and len(event) == 4:
            values = event
        else:
            raise ValueError("every event requires step, x, y, and polarity")
        if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in values):
            raise ValueError("event coordinates, steps, and polarity must be integers")
        step, x, y, polarity = (int(value) for value in values)
        if step < 0 or not 0 <= x < grid or not 0 <= y < grid or polarity not in {-1, 1}:
            raise ValueError("event is outside the declared grid or polarity domain")
        normalized.append({"step": step, "x": x, "y": y, "polarity": polarity})
    if [event["step"] for event in normalized] != sorted(event["step"] for event in normalized):
        raise ValueError("events must be ordered by nondecreasing step")
    return normalized


def observation_window(events, step, attention, width=8, grid=GRID):
    if isinstance(attention, bool) or not isinstance(attention, int) or not 0 <= attention < len(CENTERS):
        raise ValueError("attention must be 0, 1, or 2")
    center = CENTERS[attention] * grid // GRID
    half = width // 2
    lower, upper = center - half, center + half - 1
    return [event for event in events if event["step"] == step and lower <= event["x"] <= upper]


def _bounce(position, velocity):
    value = position + velocity
    while value < 1 or value > 14:
        if value < 1:
            value = 1 + (1 - value)
            velocity = abs(velocity)
        if value > 14:
            value = 14 - (value - 14)
            velocity = -abs(velocity)
    return value, velocity


def synthetic_sequence(initial_position, velocity, steps=16, noise_probability=0.0, seed=0, polarity_reversed=False):
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (initial_position, velocity, steps, seed)):
        raise ValueError("synthetic sequence parameters must be integers")
    if not 1 <= initial_position <= 14 or velocity == 0 or not 1 <= steps <= 128:
        raise ValueError("invalid synthetic sequence geometry")
    if not 0 <= noise_probability <= 1:
        raise ValueError("noise probability must be in [0, 1]")
    rng = random.Random(seed)
    position = initial_position
    direction = velocity
    targets = []
    events = []
    previous = set()
    for step in range(steps):
        targets.append(position)
        current = {(x, y) for x in range(position - 1, position + 2) for y in (7, 8) if 0 <= x < GRID}
        for x, y in sorted(current - previous):
            events.append({"step": step, "x": x, "y": y, "polarity": 1})
        for x, y in sorted(previous - current):
            events.append({"step": step, "x": x, "y": y, "polarity": -1})
        if noise_probability:
            for x in range(GRID):
                for y in range(GRID):
                    if (x, y) not in current and rng.random() < noise_probability:
                        events.append({"step": step, "x": x, "y": y, "polarity": rng.choice((-1, 1))})
        previous = current
        position, direction = _bounce(position, direction)
    if polarity_reversed:
        for event in events:
            event["polarity"] *= -1
    events.sort(key=lambda event: (event["step"], event["x"], event["y"], event["polarity"]))
    return {
        "schema_version": 1,
        "seed": seed,
        "initial_position": initial_position,
        "velocity": velocity,
        "steps": steps,
        "noise_probability": noise_probability,
        "polarity_reversed": polarity_reversed,
        "targets": targets,
        "events": events,
        "event_sha256": digest(events),
    }


def event_image(events, grid=GRID, scale=4):
    values = np.zeros((grid * scale, grid * scale, 3), dtype=np.float64) + .03
    for event in events:
        x, y = event["x"] * scale, event["y"] * scale
        color = (.95, .95, .95) if event["polarity"] > 0 else (.05, .05, .8)
        values[y:y + scale, x:x + scale] = color
    return values


def frames_to_events(frames, threshold=.12, grid=GRID):
    if not 0 < threshold <= 10:
        raise ValueError("frame-event threshold must be in (0, 10]")
    if not isinstance(frames, (list, tuple)) or len(frames) < 2:
        raise ValueError("at least two RGB frames are required")
    events = []
    previous = None
    for step, frame in enumerate(frames):
        values = np.asarray(frame, dtype=np.float64)
        if values.ndim != 3 or values.shape[2] != 3 or min(values.shape[:2]) < 4:
            raise ValueError("frames must be HxWx3 RGB arrays")
        if values.shape[0] != grid or values.shape[1] != grid:
            from PIL import Image
            image = Image.fromarray(np.asarray(values, dtype=np.uint8), "RGB").resize((grid, grid), Image.Resampling.LANCZOS)
            values = np.asarray(image, dtype=np.float64)
        maximum = float(values.max())
        intensity = np.mean(values / maximum if maximum else values, axis=2)
        log_intensity = np.log(np.maximum(intensity, 1e-6))
        if previous is not None:
            difference = log_intensity - previous
            xs, ys = np.nonzero(np.abs(difference) >= threshold)
            for x, y in zip(xs.tolist(), ys.tolist()):
                events.append({"step": step, "x": x, "y": y, "polarity": 1 if difference[x, y] > 0 else -1})
        previous = log_intensity
    return validate_events(events)


def load_event_csv(path, maximum=MAX_EVENTS):
    import csv
    source = Path(path).expanduser().resolve(strict=True)
    if source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("event CSV exceeds 64 MiB")
    events = []
    with source.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if len(events) >= maximum:
                raise ValueError("event CSV exceeds the event limit")
            events.append({key: int(row[key]) for key in ("step", "x", "y", "polarity")})
    validate_events(events, grid=max(max(event["x"], event["y"]) + 1 for event in events) if events else GRID)
    return events


def _spatially_coherent(events):
    remaining = {(event["x"], event["y"]): event for event in events}
    components = []
    while remaining:
        seed = remaining.pop(next(iter(remaining)))
        component = [seed]
        queue = [(seed["x"], seed["y"])]
        while queue:
            x, y = queue.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    key = (x + dx, y + dy)
                    if key in remaining:
                        event = remaining.pop(key)
                        component.append(event)
                        queue.append(key)
        components.append(component)
    if not components:
        return []
    largest = max(components, key=lambda component: (len(component), min((event["x"], event["y"]) for event in component)))
    if len(largest) == 1 and len(events) > 1:
        return []
    return sorted(largest, key=lambda event: (event["step"], event["x"], event["y"], event["polarity"]))


def _best_translation(previous, current):
    best = (0, 0, -1)
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            shifted = {(x + dx, y + dy) for x, y in previous}
            overlap = len(shifted & current)
            candidate = (dx, dy, overlap)
            if overlap > best[2] or overlap == best[2] and abs(dx) + abs(dy) < abs(best[0]) + abs(best[1]):
                best = candidate
    return best


class EventEncoder:
    def __init__(self, grid=GRID, decay=.82, threshold=.75):
        self.grid = grid
        self.decay = float(decay)
        self.threshold = float(threshold)
        self.module_weights = np.eye(4, dtype=np.float64)
        self.last_step = None
        self.voltage = np.zeros((grid, grid), dtype=np.float64)
        self.refractory = np.zeros((grid, grid), dtype=np.float64)
        self.last_spike = None
        self.scene = np.zeros((grid, grid), dtype=np.uint8)
        self.previous_scene = set()
        self.previous_centroid = None

    def start_sequence(self):
        self.last_step = None
        self.last_spike = None
        self.voltage.fill(0)
        self.refractory.fill(0)
        self.scene.fill(0)
        self.previous_scene = set()
        self.previous_centroid = None

    def checkpoint(self):
        return {
            "module_weights": self.module_weights.tolist(),
            "last_step": self.last_step,
            "voltage": self.voltage.tolist(),
            "refractory": self.refractory.tolist(),
            "last_spike": self.last_spike,
            "scene": self.scene.tolist(),
            "previous_scene": sorted(self.previous_scene),
            "previous_centroid": self.previous_centroid,
        }

    def restore(self, checkpoint):
        self.module_weights = np.asarray(checkpoint["module_weights"], dtype=np.float64)
        self.last_step = checkpoint["last_step"]
        self.voltage = np.asarray(checkpoint["voltage"], dtype=np.float64)
        self.refractory = np.asarray(checkpoint["refractory"], dtype=np.float64)
        self.last_spike = checkpoint.get("last_spike")
        self.scene = np.asarray(checkpoint["scene"], dtype=np.uint8)
        self.previous_scene = {tuple(item) for item in checkpoint["previous_scene"]}
        self.previous_centroid = checkpoint["previous_centroid"]

    def _plasticity(self, spike_order):
        for (first_step, first), (second_step, second) in zip(spike_order, spike_order[1:]):
            if first == second:
                continue
            elapsed = max(1, second_step - first_step)
            increment = .02 * math.exp(-elapsed / 4)
            self.module_weights[first, second] = np.clip(self.module_weights[first, second] + increment, -1, 1)
            self.module_weights[second, first] = np.clip(self.module_weights[second, first] - increment / 2, -1, 1)
        np.fill_diagonal(self.module_weights, 1.0)

    def encode(self, events, plastic=False):
        raw_events = validate_events(events, self.grid)
        raw_count = len(raw_events)
        raw_positive = sum(event["polarity"] > 0 for event in raw_events)
        for event in raw_events:
            self.scene[event["x"], event["y"]] = 1 if event["polarity"] > 0 else 0
        events = _spatially_coherent(raw_events)
        spikes = []
        if events:
            first, last = events[0]["step"], events[-1]["step"]
            if self.last_step is None:
                self.last_step = first
            for step in range(self.last_step, last + 1):
                elapsed = max(0, step - self.last_step)
                self.voltage *= self.decay ** elapsed
                self.refractory = np.maximum(0, self.refractory - elapsed)
                current = [event for event in events if event["step"] == step]
                for event in current:
                    x, y = event["x"], event["y"]
                    self.voltage[x, y] += event["polarity"]
                    if self.voltage[x, y] >= self.threshold and self.refractory[x, y] == 0:
                        module = int(x >= self.grid / 2) * 2 + int(y >= self.grid / 2)
                        spikes.append((step, module, x, y))
                        self.voltage[x, y] = -.1
                        self.refractory[x, y] = 1
                self.last_step = step
        count = len(events)
        positive = sum(event["polarity"] > 0 for event in events)
        negative = count - positive
        scene_step = raw_events[-1]["step"] if raw_events else 0
        scene_events = [
            {"step": scene_step, "x": x, "y": y, "polarity": 1}
            for x, y in np.argwhere(self.scene).tolist()
        ]
        coherent_scene = _spatially_coherent(scene_events)
        current_scene = {(event["x"], event["y"]) for event in coherent_scene}
        centroid = None
        translation = None
        if current_scene:
            centroid = [
                math.fsum(x for x, _ in current_scene) / len(current_scene),
                math.fsum(y for _, y in current_scene) / len(current_scene),
            ]
            if self.previous_scene and self.previous_centroid is not None:
                dx, dy, overlap = _best_translation(self.previous_scene, current_scene)
                if overlap > 0:
                    centroid = [self.previous_centroid[0] + dx, self.previous_centroid[1] + dy]
                    translation = {"dx": dx, "dy": dy, "overlap": overlap}
        self.previous_scene = current_scene
        self.previous_centroid = deepcopy(centroid)
        activity = [0.0] * 4
        for event in events:
            module = int(event["x"] >= self.grid / 2) * 2 + int(event["y"] >= self.grid / 2)
            activity[module] += 1
        spike_order = [(step, module) for step, module, _, _ in sorted(spikes)]
        temporal_order = ([self.last_spike] if self.last_spike is not None else []) + spike_order
        if plastic:
            self._plasticity(temporal_order)
        if spike_order:
            self.last_spike = spike_order[-1]
        gains = np.maximum(.05, 1 + .05 * np.maximum(self.module_weights.sum(axis=1), 0))
        routed = (np.asarray(activity) * gains)
        active = sorted(range(4), key=lambda module: (-routed[module], module))[:2] if count else []
        feature = [
            (centroid[0] / (self.grid - 1)) if centroid else 0.0,
            (centroid[1] / (self.grid - 1)) if centroid else 0.0,
            count / (self.grid * self.grid),
            (positive - negative) / count if count else 0.0,
            *(value / (self.grid * self.grid) for value in activity),
            len(spikes) / (self.grid * self.grid),
        ]
        return {
            "event_count": count,
            "raw_event_count": raw_count,
            "filtered_event_count": count,
            "noise_ratio": (raw_count - count) / raw_count if raw_count else 0.0,
            "positive_events": positive,
            "negative_events": negative,
            "raw_positive_events": raw_positive,
            "raw_polarity_balance": (2 * raw_positive - raw_count) / raw_count if raw_count else 0.0,
            "centroid": centroid,
            "scene_event_count": len(coherent_scene),
            "scene_sha256": digest(coherent_scene),
            "translation": translation,
            "polarity_balance": (positive - negative) / count if count else 0.0,
            "module_activity": activity,
            "routed_activity": routed.tolist(),
            "active_modules": active,
            "spike_order": spike_order,
            "spike_count": len(spikes),
            "feature_vector": [float(value) for value in feature],
            "event_sha256": digest(raw_events),
            "filtered_event_sha256": digest(events),
            "stdp_weight_sha256": digest(self.module_weights.tolist()),
            "scope": "Sparse event integration and spike-order features, not biological validation or semantic recognition",
        }


def checkpoint_document(encoder):
    return deepcopy(encoder.checkpoint())


def observation_digest(observation):
    return digest({key: value for key, value in observation.items() if key != "stdp_weight_sha256"})


def observation_json(observation):
    return json_value(observation)


def json_value(value):
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        canonical(value)
        return value
    raise ValueError(f"unsupported event document value: {type(value).__name__}")

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from .atlas import _ellipse, _line, _scene, _text
from .field import _canonical
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


REFERENCE_HZ = 40_000_000
REFERENCE_PERIOD_PS = 25_000
TIM3C_SHA256 = "96e9f0a51d3ba1e3b9a1fa5ece05688341f220ada54cf451fdbbfe68263d0611"
SOIL_RELEASE_C = (64 - 32) / 9 * 5
CHORUS_DELAY = Fraction(4, 365)
MAX_EVENTS = 256
SCOPE = "A deterministic timing toy informed by CERN clock distribution and cicada timing research; not measured CERN time, a fitted biological model, or an external actuator."
EVENT_FIELDS = {"sequence", "kind", "arguments", "actions", "state_sha256", "previous_hash", "hash"}
DOCUMENT_FIELDS = {
    "schema_version", "instrument", "configuration", "initial_state", "state",
    "events", "measurements", "scope", "source", "replay_verified", "digest",
}
CONFIGURATION_FIELDS = {
    "cycle_years", "host_rate", "initial_cycles", "initial_calendar_age",
    "growth_multiplier", "daily_period_seconds", "entrainment_strength",
    "years_per_second", "initial_phase",
}
SOURCE = {
    "tim3c_clock_flow_sha256": TIM3C_SHA256,
    "tim3c_pattern": "80 MHz oscillator divided by two to 40 MHz; 25,000 ps used only as a synthetic quantization interval",
    "host_cycles": "Karban, Black & Weinbaum (2000), How 17-year cicadas keep track of time, Ecology Letters 3:253-256",
    "internal_gate": "Yoshimura (2022), Life-cycle control of 13- and 17-year periodical cicadas: a hypothesis, Ecological Research",
    "daily_neuropeptide": "Sato et al. (2002), PDF in Meimuna opalifera, Zoological Science 19:821-828",
    "emergence_conditions": "UConn periodical cicada information: approximately 64 F soil at 7-8 inches and usually after sunset; local conditions vary",
}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fraction(value, label, minimum=None, maximum=None):
    if isinstance(value, str) and len(value) > 128:
        raise ValueError(f"{label} exceeds its rational-text bound")
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{label} must be a rational value") from error
    if minimum is not None and result < minimum or maximum is not None and result > maximum:
        raise ValueError(f"{label} is outside its allowed range")
    return result


def _number(value, label, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return float(value)


def _fraction_text(value):
    return str(value)


def _phase_text(value):
    return f"{value:.12f}".rstrip("0").rstrip(".")


class CicadaClock:
    def __init__(self, cycle_years=13, host_rate=1, initial_cycles=0, initial_calendar_age=None, growth_multiplier=1.0, daily_period_seconds=24.0, entrainment_strength=0.03, years_per_second=1.0, initial_phase=0.0):
        if cycle_years not in {13, 17} or isinstance(cycle_years, bool):
            raise ValueError("cicada cycle must be 13 or 17 years")
        if host_rate not in {1, 2} or isinstance(host_rate, bool):
            raise ValueError("host seasonal cycles must run at one or two cycles per calendar year")
        self.cycle_years = cycle_years
        self.host_rate = host_rate
        self.initial_cycles = _fraction(initial_cycles, "initial host cycles", 0, 64)
        self.initial_calendar_age = self.initial_cycles if initial_calendar_age is None else _fraction(initial_calendar_age, "initial calendar age", 0, 80)
        self.growth_multiplier = _number(growth_multiplier, "growth multiplier", 0.125, 4)
        self.daily_period_seconds = _number(daily_period_seconds, "daily period", 1, 86400)
        self.entrainment_strength = _number(entrainment_strength, "entrainment strength", 0, 0.25)
        self.years_per_second = _fraction(years_per_second, "years per second", Fraction(1, 1000), 1000)
        self.initial_phase = _number(initial_phase, "initial daily phase", 0, 1)
        if self.initial_phase == 1:
            raise ValueError("initial daily phase must be less than one")
        self.rate = math.log(100) * self.growth_multiplier / (cycle_years - 1)
        ready = math.log(100) / self.rate
        self.gate_cycle = max(4, math.ceil(ready / 4) * 4)
        self.emergence_cycle = self.gate_cycle + 1
        self.chorus_cycle = Fraction(self.emergence_cycle) + CHORUS_DELAY
        self.reference_ticks = 0
        self.host_cycles = self.initial_cycles
        self.calendar_age = self.initial_calendar_age
        self.phase = self.initial_phase
        self.gate_open = self.host_cycles >= self.gate_cycle
        self.emerged = self.host_cycles >= self.emergence_cycle
        self.chorus = self.host_cycles >= self.chorus_cycle
        self.soil_temp_c = 18.0
        self.after_sunset = True
        self.last_actions = ["configured"]
        self.events = []
        self.replay_verified = False
        self._initial_state = self._state()

    def configuration(self):
        return {
            "cycle_years": self.cycle_years,
            "host_rate": self.host_rate,
            "initial_cycles": _fraction_text(self.initial_cycles),
            "initial_calendar_age": _fraction_text(self.initial_calendar_age),
            "growth_multiplier": self.growth_multiplier,
            "daily_period_seconds": self.daily_period_seconds,
            "entrainment_strength": self.entrainment_strength,
            "years_per_second": _fraction_text(self.years_per_second),
            "initial_phase": self.initial_phase,
        }

    def _state(self):
        return {
            "reference_ticks": self.reference_ticks,
            "host_cycles": _fraction_text(self.host_cycles),
            "calendar_age": _fraction_text(self.calendar_age),
            "phase": _phase_text(self.phase),
            "gate_open": self.gate_open,
            "emerged": self.emerged,
            "chorus": self.chorus,
            "soil_temp_c": self.soil_temp_c,
            "after_sunset": self.after_sunset,
            "last_actions": list(self.last_actions),
        }

    def _state_digest(self):
        return _digest(self._state())

    def measurements(self):
        growth = 0.01 * math.exp(self.rate * float(self.host_cycles))
        due = max(Fraction(0), (Fraction(self.emergence_cycle) - self.host_cycles) / self.host_rate)
        return {
            "reference_ticks": self.reference_ticks,
            "reference_period_ps": REFERENCE_PERIOD_PS,
            "reference_is_measured": False,
            "host_cycles": _fraction_text(self.host_cycles),
            "calendar_age": _fraction_text(self.calendar_age),
            "daily_phase": self.phase,
            "growth_ratio": growth,
            "critical_weight_ratio": 1.0,
            "gate_cycle": self.gate_cycle,
            "emergence_cycle": self.emergence_cycle,
            "chorus_cycle": _fraction_text(self.chorus_cycle),
            "calendar_years_to_emergence": _fraction_text(due),
            "gate_open": self.gate_open,
            "emerged": self.emerged,
            "chorus": self.chorus,
            "awaiting_conditions": self.host_cycles >= self.emergence_cycle and not self.emerged,
            "soil_release_met": self.soil_temp_c >= SOIL_RELEASE_C,
            "after_sunset": self.after_sunset,
            "last_actions": list(self.last_actions),
            "event_count": len(self.events),
            "internal_gate_is_hypothesis": True,
            "biological_measurement": False,
            "external_actions_executed": False,
            "llm_called": False,
        }

    def _record(self, arguments, actions):
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("cicada event bound reached")
        event = {
            "sequence": len(self.events) + 1,
            "kind": "step",
            "arguments": deepcopy(arguments),
            "actions": list(actions),
            "state_sha256": self._state_digest(),
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = _digest(event)
        self.events.append(event)

    def step(self, seconds, soil_temp_c=18.0, after_sunset=True, host_phase=0.0):
        seconds_text = str(seconds)
        duration = _fraction(seconds_text, "step seconds", Fraction(1, REFERENCE_HZ), 86400)
        soil_temp_c = _number(soil_temp_c, "soil temperature", -80, 80)
        if not isinstance(after_sunset, bool):
            raise ValueError("after_sunset must be an explicit boolean")
        host_phase = _number(host_phase, "host daily phase", 0, 1)
        if host_phase == 1:
            raise ValueError("host daily phase must be less than one")
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("cicada event bound reached")
        ticks = int(duration * REFERENCE_HZ + Fraction(1, 2))
        elapsed = Fraction(ticks, REFERENCE_HZ)
        next_host_cycles = self.host_cycles + elapsed * self.years_per_second * self.host_rate
        next_calendar_age = self.calendar_age + elapsed * self.years_per_second
        if next_host_cycles > 64 or next_calendar_age > 80:
            raise ValueError("cicada host-cycle or calendar-age bound reached")
        self.reference_ticks += ticks
        self.host_cycles = next_host_cycles
        self.calendar_age = next_calendar_age
        correction = self.entrainment_strength * math.sin(math.tau * (host_phase - self.phase))
        unwrapped_phase = self.phase + float(elapsed) / self.daily_period_seconds + correction
        self.phase = unwrapped_phase % 1
        self.soil_temp_c = soil_temp_c
        self.after_sunset = after_sunset
        actions = ["advance"]
        if math.floor(unwrapped_phase) != 0:
            actions.append("daily-pulse")
        if not self.gate_open and self.host_cycles >= self.gate_cycle:
            self.gate_open = True
            actions.append("gate-open")
        conditions = soil_temp_c >= SOIL_RELEASE_C and after_sunset
        if not self.emerged and self.host_cycles >= self.emergence_cycle and conditions:
            self.emerged = True
            actions.append("emerge")
        if not self.chorus and self.emerged and self.host_cycles >= self.chorus_cycle and conditions:
            self.chorus = True
            actions.append("chorus")
        self.last_actions = actions
        arguments = {"seconds": seconds_text, "soil_temp_c": soil_temp_c, "after_sunset": after_sunset, "host_phase": host_phase}
        self._record(arguments, actions)
        return self.measurements()

    def document(self):
        return self._add_digest({
            "schema_version": 1,
            "instrument": "zoe-cicada-internal-clock",
            "configuration": self.configuration(),
            "initial_state": deepcopy(self._initial_state),
            "state": self._state(),
            "events": deepcopy(self.events),
            "measurements": self.measurements(),
            "scope": SCOPE,
            "source": deepcopy(SOURCE),
            "replay_verified": self.replay_verified,
        })

    @staticmethod
    def _add_digest(document):
        document["digest"] = _digest({key: value for key, value in document.items() if key != "digest"})
        return document

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("cicada sessions must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("cicada session directory does not exist")
        document = self.document()
        self.replay(document)
        document["replay_verified"] = True
        self._add_digest(document)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(document) + "\n")
        return path

    @classmethod
    def replay(cls, source):
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file() or not 1 <= path.stat().st_size <= 4 * 1024 * 1024:
                raise ValueError("cicada session is missing or exceeds 4 MiB")
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = deepcopy(source)
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-cicada-internal-clock":
            raise ValueError("unsupported cicada session")
        if data["digest"] != _digest({key: value for key, value in data.items() if key != "digest"}):
            raise ValueError("cicada document digest mismatch")
        if data["scope"] != SCOPE or data["source"] != SOURCE or not isinstance(data["replay_verified"], bool):
            raise ValueError("unsupported cicada evidence scope")
        if not isinstance(data["configuration"], dict) or set(data["configuration"]) != CONFIGURATION_FIELDS:
            raise ValueError("unsupported cicada configuration")
        game = cls(**data["configuration"])
        if game._state() != data["initial_state"] or not isinstance(data["events"], list) or len(data["events"]) > MAX_EVENTS:
            raise ValueError("cicada initial state or event bound mismatch")
        previous_hash = None
        for index, expected in enumerate(data["events"], 1):
            if not isinstance(expected, dict) or set(expected) != EVENT_FIELDS or expected["sequence"] != index or expected["kind"] != "step" or expected["previous_hash"] != previous_hash:
                raise ValueError("cicada event-chain mismatch")
            if expected["hash"] != _digest({key: value for key, value in expected.items() if key != "hash"}):
                raise ValueError("cicada event hash mismatch")
            arguments = expected["arguments"]
            if not isinstance(arguments, dict) or set(arguments) != {"seconds", "soil_temp_c", "after_sunset", "host_phase"}:
                raise ValueError("invalid cicada replay arguments")
            game.step(**arguments)
            if game.events[-1] != expected:
                raise ValueError("cicada replay diverges from the recorded event")
            previous_hash = expected["hash"]
        if game.events != data["events"] or game._state() != data["state"] or game.measurements() != data["measurements"]:
            raise ValueError("cicada final state does not match the replay")
        game.replay_verified = True
        return game

    def scene(self):
        measurements = self.measurements()
        objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
        objects.extend([
            _text("title", [42, 51], "Zoe Internal Clock", 31, "#67e8f9"),
            _text("subtitle", [44, 80], "CERN phase discipline · cicada timing hypotheses · explicit local action", 14, "#9fb1c8"),
            _text("cern-reference", [45, 111], "80 MHz / 2 = 40 MHz · 25,000 ps synthetic ticks · not measured time", 12, "#e7d6ad"),
        ])
        center = [230, 335]
        objects.append(_ellipse("daily-ring", center, [112, 112], "#475569", "#0f1929", 2))
        for index in range(24):
            angle = math.tau * index / 24
            first = [center[0] + 96 * math.sin(angle), center[1] - 96 * math.cos(angle)]
            second = [center[0] + 108 * math.sin(angle), center[1] - 108 * math.cos(angle)]
            objects.append(_line(f"daily-tick-{index}", first, second, "#64748b", 1))
        angle = math.tau * self.phase
        endpoint = [center[0] + 91 * math.sin(angle), center[1] - 91 * math.cos(angle)]
        objects.append(_line("daily-hand", center, endpoint, "#f0abfc", 3))
        objects.append(_ellipse("daily-pin", center, [6, 6], "#e7d6ad", "#e7d6ad"))
        objects.append(_text("daily-label", [153, 474], f"Daily phase {self.phase:.3f}", 15, "#f0abfc"))
        objects.append(_text("cycle-label", [143, 503], f"{self.cycle_years}-year developmental toy", 13, "#9fb1c8"))
        objects.append(_ellipse("cicada-wing-left", [433, 240], [46, 75], "#c4b5fd", "#111d30", 2))
        objects.append(_ellipse("cicada-wing-right", [497, 240], [46, 75], "#c4b5fd", "#111d30", 2))
        objects.append(_ellipse("cicada-body", [465, 274], [24, 76], "#e7d6ad", "#0f1929", 2))
        objects.append(_ellipse("cicada-head", [465, 190], [22, 20], "#e7d6ad", "#0f1929", 2))
        objects.append(_text("cicada-caption", [400, 383], "Original glyph · not anatomy", 11, "#9fb1c8"))
        objects.append({"id": "metrics-panel", "type": "rectangle", "bounds": [610, 132, 956, 512], "stroke": "#475569", "fill": "#0f1929", "width": 1})
        rows = [
            f"Host cycles  {measurements['host_cycles']}",
            f"Calendar age {measurements['calendar_age']}",
            f"Growth / CW  {measurements['growth_ratio']:.3f} / 1.000",
            f"Gate year    {self.gate_cycle} · open={self.gate_open}",
            f"Emerge year  {self.emergence_cycle} · done={self.emerged}",
            f"Soil         {self.soil_temp_c:.2f} C · release={measurements['soil_release_met']}",
            f"After sunset {self.after_sunset}",
            f"Chorus       {self.chorus}",
            f"Events       {len(self.events)} / {MAX_EVENTS}",
        ]
        for index, text in enumerate(rows):
            objects.append(_text(f"metric-{index}", [628, 169 + index * 37], text, 12, "#dbeafe" if index != 7 else "#a7f3d0"))
        objects.append(_text("last-actions", [628, 485], f"Act: {', '.join(self.last_actions)}", 11, "#e7d6ad"))
        left, right, baseline = 55, 580, 615
        objects.append(_line("gate-axis", [left, baseline], [right, baseline], "#475569", 2))
        for gate in (4, 8, 12, 16, 20):
            x = left + (gate - 4) * 32
            objects.append(_line(f"gate-{gate}", [x, baseline - 12], [x, baseline + 12], "#c4b5fd" if gate == self.gate_cycle else "#64748b", 2))
            objects.append(_text(f"gate-label-{gate}", [x - 7, baseline + 34], str(gate), 12, "#c4b5fd" if gate == self.gate_cycle else "#9fb1c8"))
        current = min(20, max(4, float(self.host_cycles)))
        current_x = left + (current - 4) * 32
        objects.append(_line("current-cycle", [current_x, baseline - 22], [current_x, baseline + 17], "#f0abfc", 3))
        objects.append(_text("timeline-caption", [55, 674], "Hypothetical four-year gates · host cycles, not wall-clock years", 12, "#9fb1c8"))
        objects.append(_text("phase-equation", [55, 704], "phase += dt / daily_period + k sin(2pi(host - phase)) · growth = 0.01 exp(rate cycles)", 11, "#c4b5fd"))
        objects.append(_text("boundary", [55, 731], "Model != insect != measured CERN time · local visual/replay events only · no external actuator", 11, "#fda4af"))
        return _scene("zoe-cicada-clock", 1000, 760, objects, "Zoe Internal Clock · CERN ticks and cicada timing hypotheses")

    def export(self, path, kind=None, width=1400):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"svg", "png", "gem"}:
            raise ValueError("cicada export must be svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("cicada export directory does not exist")
        scene = self.scene()
        check = verify_vdi(scene) if kind == "gem" else verify(scene)
        if not check.passed:
            raise ValueError(check.text())
        if kind == "gem":
            write_metafile(scene, path)
        elif kind == "svg":
            write_svg(scene, path, width)
        else:
            write_png(scene, path, width)
        return path

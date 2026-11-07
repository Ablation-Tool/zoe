from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shlex
import sys

from .atlas import _scene, _text
from .field import _canonical
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


SIGNAL_TYPES = {"wire", "reg", "logic", "integer", "real", "time", "parameter", "event", "tri", "tri0", "tri1", "supply0", "supply1"}
UNITS = {"s": 1_000_000_000_000, "ms": 1_000_000_000, "us": 1_000_000, "ns": 1000, "ps": 1, "fs": Decimal("0.001")}
DOCUMENT_FIELDS = {"schema_version", "instrument", "source", "timescale_ps", "signals", "events", "truncated", "digest"}
SOURCE_FIELDS = {"path", "format", "sha256", "size", "name_mapping"}
SIGNAL_FIELDS = {"identifier", "name", "kind", "width", "status", "period_ps", "candidates", "functional_label"}
EVENT_FIELDS = {"signal", "time", "value"}
STATUS_COLORS = {"corroborated": "#67e8f9", "ambiguous": "#fde68a", "unmapped": "#9fb1c8"}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source(path, kind):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "format": kind,
        "sha256": digest.hexdigest(),
        "size": path.stat().st_size,
        "name_mapping": "declared_vcd_symbols" if kind == "vcd" else "storage_ids_only",
    }


def _bound(value, minimum=1, maximum=65536):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"event limit must be between {minimum} and {maximum}")
    return value


def _clock_matches(events, initial, period, legacy=False):
    if len(events) < 33 or period <= 0:
        return False
    interval = events[1]["time"] - events[0]["time"]
    if interval * 2 != period:
        return False
    for index, event in enumerate(events[:33]):
        if index and event["time"] - events[index - 1]["time"] != interval:
            return False
        value = event["value"]
        if legacy:
            if value not in {"02", "03"}:
                return False
            expected = initial if index % 2 == 0 else 5 - initial
            if int(value, 16) != expected:
                return False
        else:
            if value not in {"0", "1"}:
                return False
            expected = initial if index % 2 == 0 else 1 - initial
            if int(value) != expected:
                return False
    return True


def _functional_label(events, legacy=False):
    unique = {event["value"] for event in events}
    if len(unique) == 1:
        return "constant-like"
    if len(events) <= 4:
        return "reset-or-sparse-control-like"
    if len(unique) <= 64:
        return "state-or-enumerated-scalar-like"
    return "mixed-or-complex-data" if not legacy else "enumerated-vector-like"


@dataclass(frozen=True)
class WaveformReplay:
    source: dict
    timescale_ps: Decimal
    signals: list[dict]
    events: list[dict]
    truncated: bool

    def _from_parts(source, timescale, signals, events, truncated):
        if not isinstance(signals, list) or not 1 <= len(signals) <= 4096:
            raise ValueError("replay requires 1-4096 declared signals")
        if not isinstance(events, list) or not 1 <= len(events) <= 65536:
            raise ValueError("replay requires 1-65536 retained events")
        identifiers = set()
        for signal in signals:
            if not isinstance(signal, dict) or set(signal) != {"identifier", "name", "kind", "width"}:
                raise ValueError("invalid signal declaration")
            if signal["identifier"] in identifiers or not isinstance(signal["identifier"], str) or not 1 <= len(signal["identifier"]) <= 128:
                raise ValueError("signal identifiers must be unique and bounded")
            if not isinstance(signal["name"], str) or not 1 <= len(signal["name"]) <= 512 or signal["kind"] not in SIGNAL_TYPES | {"legacy"}:
                raise ValueError("invalid signal name or kind")
            if isinstance(signal["width"], bool) or not isinstance(signal["width"], int) or not 1 <= signal["width"] <= 4096:
                raise ValueError("invalid signal width")
            identifiers.add(signal["identifier"])
        previous = -1
        for event in events:
            if not isinstance(event, dict) or set(event) != EVENT_FIELDS or event["signal"] not in identifiers:
                raise ValueError("event references an unknown signal")
            if isinstance(event["time"], bool) or not isinstance(event["time"], int) or event["time"] < previous or event["time"] < 0:
                raise ValueError("event timestamps must be nondecreasing integers")
            if not isinstance(event["value"], str) or not 1 <= len(event["value"]) <= 8192:
                raise ValueError("event value must be bounded text")
            previous = event["time"]
        if not isinstance(truncated, bool):
            raise ValueError("truncated must be boolean")
        return WaveformReplay(source, Decimal(timescale), deepcopy(signals), deepcopy(events), truncated)

    @classmethod
    def from_vcd(cls, path, max_events=4096):
        path = Path(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("VCD exceeds the 64 MiB replay limit")
        with path.open("r", encoding="utf-8") as stream:
            return cls._parse_vcd(stream, _source(path, "vcd"), max_events)

    @classmethod
    def from_vcd_text(cls, text, max_events=4096):
        if not isinstance(text, str) or len(text.encode("utf-8")) > 64 * 1024 * 1024:
            raise ValueError("VCD text must be a nonempty string of at most 64 MiB")
        source = {"path": "memory://demo.vcd", "format": "vcd", "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "size": len(text.encode("utf-8")), "name_mapping": "declared_vcd_symbols"}
        return cls._parse_vcd(io.StringIO(text), source, max_events)

    @classmethod
    def _parse_vcd(cls, stream, source, max_events):
        max_events = _bound(max_events)
        scope = []
        declarations = {}
        timescale = None
        events = []
        truncated = False
        previous = -1
        for line in stream:
            if len(line) > 1024 * 1024:
                raise ValueError("VCD line exceeds 1 MiB")
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("$timescale"):
                if timescale is not None:
                    raise ValueError("duplicate VCD timescale")
                parts = shlex.split(stripped)
                if len(parts) != 3 or parts[2] != "$end":
                    raise ValueError("invalid VCD timescale")
                unit = next((candidate for candidate in ("ms", "us", "ns", "ps", "fs", "s") if parts[1].endswith(candidate)), None)
                number = parts[1][:-len(unit)] if unit else parts[1]
                if unit not in UNITS:
                    raise ValueError("unsupported VCD time unit")
                try:
                    timescale = Decimal(number) * UNITS[unit]
                except InvalidOperation as error:
                    raise ValueError("invalid VCD timescale") from error
                if not timescale.is_finite() or timescale <= 0:
                    raise ValueError("VCD timescale must be positive")
            elif stripped.startswith("$scope"):
                parts = shlex.split(stripped)
                if len(parts) != 4 or parts[1] != "module" or parts[3] != "$end":
                    raise ValueError("unsupported VCD scope")
                scope.append(parts[2])
            elif stripped == "$upscope $end":
                if not scope:
                    raise ValueError("unmatched VCD upscope")
                scope.pop()
            elif stripped.startswith("$var"):
                parts = shlex.split(stripped)
                if len(parts) != 6 or parts[5] != "$end":
                    raise ValueError("invalid VCD variable declaration")
                kind, width, identifier, reference = parts[1:5]
                if kind not in SIGNAL_TYPES or identifier in declarations:
                    raise ValueError("unsupported or duplicate VCD signal declaration")
                try:
                    width_value = int(width)
                except ValueError as error:
                    raise ValueError("invalid VCD signal width") from error
                if not 1 <= width_value <= 4096 or not 1 <= len(identifier) <= 128 or not 1 <= len(reference) <= 256:
                    raise ValueError("invalid VCD signal bounds")
                declarations[identifier] = {"identifier": identifier, "name": ".".join([*scope, reference]), "kind": kind, "width": width_value}
            elif stripped == "$enddefinitions $end":
                if timescale is None or not declarations:
                    raise ValueError("VCD requires timescale and signal declarations")
                break
        else:
            raise ValueError("VCD enddefinitions is missing")
        for line in stream:
            if len(line) > 1024 * 1024:
                raise ValueError("VCD line exceeds 1 MiB")
            stripped = line.strip()
            if not stripped or stripped.startswith("$"):
                continue
            if stripped.startswith("#"):
                try:
                    raw_time = Decimal(stripped[1:])
                except InvalidOperation as error:
                    raise ValueError("invalid VCD timestamp") from error
                if not raw_time.is_finite():
                    raise ValueError("invalid VCD timestamp")
                scaled = raw_time * timescale
                if scaled != int(scaled) or scaled < previous:
                    raise ValueError("VCD timestamps must be ordered integral time values")
                previous = scaled
                continue
            if previous < 0:
                raise ValueError("VCD value change precedes its timestamp")
            if len(events) >= max_events:
                truncated = True
                break
            try:
                if stripped[0] in "01xXzZ" and len(stripped) > 1:
                    signal, value = stripped[1:], stripped[0].lower()
                elif stripped[0] in "bB":
                    value_text, signal = stripped[1:].split()
                    if not value_text or any(character not in "01xXzZ" for character in value_text):
                        raise ValueError("invalid VCD binary value")
                    value = value_text.lower()
                elif stripped[0] in "rR":
                    value_text, signal = stripped[1:].split()
                    value = float(value_text)
                    if not math.isfinite(value):
                        raise ValueError("invalid VCD real value")
                    value = value_text
                else:
                    raise ValueError("unsupported VCD value change")
            except ValueError as error:
                if isinstance(error, InvalidOperation):
                    raise ValueError("invalid VCD value") from error
                raise
            if signal not in declarations:
                raise ValueError(f"change for undeclared VCD signal: {signal}")
            if len(value) > 8192:
                raise ValueError("VCD value exceeds 8192 characters")
            events.append({"signal": signal, "time": int(previous), "value": value})
        if not events:
            raise ValueError("VCD contains no value changes")
        signals = list(declarations.values())
        return cls._from_parts(source, timescale, signals, events, truncated)

    @classmethod
    def from_legacy_jsonl(cls, path, max_events=4096):
        path = Path(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("legacy JSONL exceeds the 64 MiB replay limit")
        max_events = _bound(max_events)
        source = _source(path, "legacy-jsonl")
        signals = {}
        events = []
        truncated = False
        previous = -1
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if len(line) > 1024 * 1024:
                    raise ValueError("legacy JSONL line exceeds 1 MiB")
                if len(events) >= max_events:
                    truncated = True
                    break
                record = json.loads(line)
                if not isinstance(record, dict) or not {"root_index", "storage_id", "time", "payload_hex"} <= set(record):
                    raise ValueError("invalid legacy event fields")
                root, storage, timestamp, payload = record["root_index"], record["storage_id"], record["time"], record["payload_hex"]
                if isinstance(root, bool) or not isinstance(root, int) or not 0 <= root <= 4095 or not isinstance(storage, str) or not storage.startswith("0x"):
                    raise ValueError("invalid legacy storage identity")
                if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < previous:
                    raise ValueError("legacy timestamps must be nondecreasing integers")
                if not isinstance(payload, str) or len(payload) > 8192 or len(payload) % 2 or any(character not in "0123456789abcdefABCDEF" for character in payload):
                    raise ValueError("invalid legacy payload")
                identifier = f"{root}/{storage}"
                if identifier not in signals:
                    signals[identifier] = {"identifier": identifier, "name": f"root-{root}/{storage}", "kind": "legacy", "width": len(payload) // 2 or 1}
                signals[identifier]["width"] = max(signals[identifier]["width"], len(payload) // 2)
                events.append({"signal": identifier, "time": timestamp, "value": payload.lower()})
                previous = timestamp
        if not events:
            raise ValueError("legacy JSONL contains no events")
        return cls._from_parts(source, 1, list(signals.values()), events, truncated)

    @classmethod
    def from_wdb(cls, path, max_events=4096):
        max_events = _bound(max_events)
        try:
            from ablation.analyzers.xilinx_wdb import WdbReader
        except ImportError:
            root = os.environ.get("ZOE_ABLATION_ROOT")
            if not root:
                raise RuntimeError("legacy WDB replay requires Ablation's optional xilinx_wdb module or ZOE_ABLATION_ROOT")
            candidate = Path(root) / "ablation/analyzers/xilinx_wdb.py"
            if not candidate.is_file():
                raise RuntimeError(f"xilinx_wdb was not found at {candidate}")
            spec = importlib.util.spec_from_file_location("zoe_legacy_wdb", candidate)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            WdbReader = module.WdbReader
        source = _source(path, "legacy-wdb")
        signals = {}
        events = []
        truncated = False
        with WdbReader(path, max_events=max_events + 1) as reader:
            for event in reader.events():
                if len(events) >= max_events:
                    truncated = True
                    break
                identifier = f"{event.root_index}/0x{event.storage_id:X}"
                if identifier not in signals:
                    signals[identifier] = {"identifier": identifier, "name": f"root-{event.root_index}/0x{event.storage_id:X}", "kind": "legacy", "width": len(event.payload)}
                signals[identifier]["width"] = max(signals[identifier]["width"], len(event.payload))
                events.append({"signal": identifier, "time": event.time, "value": event.payload.hex()})
        if not events:
            raise ValueError("WDB contains no retained events")
        return cls._from_parts(source, 1, list(signals.values()), events, truncated)

    @classmethod
    def load(cls, path, kind=None, max_events=4096):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind == "vcd":
            return cls.from_vcd(path, max_events)
        if kind == "jsonl":
            return cls.from_legacy_jsonl(path, max_events)
        if kind == "wdb":
            return cls.from_wdb(path, max_events)
        if kind != "json":
            raise ValueError("replay input must be .vcd, .json, .jsonl, or .wdb")
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("replay JSON exceeds 64 MiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-waveform-replay":
            raise ValueError("unsupported waveform replay document")
        source = data["source"]
        if not isinstance(source, dict) or set(source) != SOURCE_FIELDS or source["format"] not in {"vcd", "legacy-jsonl", "legacy-wdb"}:
            raise ValueError("invalid replay source")
        if not isinstance(source["path"], str) or not 1 <= len(source["path"]) <= 4096 or not isinstance(source["sha256"], str) or len(source["sha256"]) != 64 or any(character not in "0123456789abcdef" for character in source["sha256"]):
            raise ValueError("invalid replay source hash")
        if isinstance(source["size"], bool) or not isinstance(source["size"], int) or source["size"] < 0 or source["name_mapping"] not in {"declared_vcd_symbols", "storage_ids_only"}:
            raise ValueError("invalid replay source metadata")
        if not isinstance(data["timescale_ps"], (int, float, str)) or isinstance(data["timescale_ps"], bool):
            raise ValueError("invalid replay timescale")
        try:
            timescale = Decimal(str(data["timescale_ps"]))
        except InvalidOperation as error:
            raise ValueError("invalid replay timescale") from error
        if not timescale.is_finite() or timescale <= 0:
            raise ValueError("replay timescale must be positive")
        expected = _digest({key: value for key, value in data.items() if key != "digest"})
        if data["digest"] != expected:
            raise ValueError("waveform replay digest mismatch")
        return cls._from_parts(source, timescale, data["signals"], data["events"], data["truncated"])

    def document(self):
        data = {
            "schema_version": 1,
            "instrument": "zoe-waveform-replay",
            "source": deepcopy(self.source),
            "timescale_ps": str(self.timescale_ps),
            "signals": deepcopy(self.signals),
            "events": deepcopy(self.events),
            "truncated": self.truncated,
        }
        data["digest"] = _digest(data)
        return data

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("waveform replay documents must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("replay directory does not exist")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    def analyze(self):
        reports = []
        legacy = self.source["format"] != "vcd"
        for signal in self.signals:
            identifier = signal["identifier"]
            events = [event for event in self.events if event["signal"] == identifier]
            first_interval = events[1]["time"] - events[0]["time"] if len(events) > 1 else 0
            candidates = []
            for initial in ((2, 3) if legacy else (0, 1)):
                if _clock_matches(events, initial, first_interval * 2, legacy):
                    candidates.append({"initial": initial, "period_ps": first_interval * 2})
            status = "unmapped"
            if len(candidates) == 1:
                status = "corroborated"
            elif candidates:
                status = "ambiguous"
            reports.append({
                **signal,
                "status": status,
                "period_ps": first_interval * 2 if candidates else None,
                "candidates": candidates,
                "functional_label": _functional_label(events, legacy),
                "event_count": len(events),
                "name_source": "VCD declaration" if not legacy else "storage ID only",
                "identity_proven": False,
            })
        period_counts = {
            period: sum(item["period_ps"] == period for item in reports)
            for report in reports
            if (period := report["period_ps"]) is not None
        }
        for report in reports:
            if report["period_ps"] is not None:
                report["status"] = "ambiguous" if period_counts[report["period_ps"]] > 1 else "corroborated"
        counts = {status: sum(report["status"] == status for report in reports) for status in STATUS_COLORS}
        return {
            "source": deepcopy(self.source),
            "timescale_ps": str(self.timescale_ps),
            "retained_events": len(self.events),
            "signals": reports,
            "status_counts": counts,
            "truncated": self.truncated,
            "hardware_accessed": False,
            "name_mapping_is_identity": False,
            "summary": f"{len(self.events)} retained events · {len(reports)} signals · {counts['corroborated']} corroborated / {counts['ambiguous']} ambiguous / {counts['unmapped']} unmapped\nSource: {self.source['path']}\nNo live acquisition or automatic action",
        }


def demo_vcd_text():
    definitions = "".join(f"$var wire 1 {identifier} {name} $end\n" for identifier, name in (("c0", "host80"), ("c1", "host40"), ("c2", "amac40"), ("u0", "unmapped")))
    lines = ["$timescale 1ps $end", "$scope module demo $end", definitions, "$upscope $end", "$enddefinitions $end"]
    for index in range(80):
        lines.append(f"#{index * 6250}")
        lines.append(f"{1 - index % 2}c0")
        if index % 2 == 0:
            lines.append(f"{1 - (index // 2) % 2}c1")
            lines.append(f"{1 - (index // 2) % 2}c2")
        else:
            lines.append(f"{index // 5 % 2}u0")
    return "\n".join(lines) + "\n"


def demo_replay(max_events=4096):
    return WaveformReplay.from_vcd_text(demo_vcd_text(), max_events)


def waveform_scene(replay, selected=None):
    analysis = replay.analyze()
    if selected is not None and selected not in {signal["identifier"] for signal in analysis["signals"]}:
        raise ValueError("unknown waveform signal")
    selected = selected or next(signal["identifier"] for signal in analysis["signals"] if any(event["signal"] == signal["identifier"] for event in replay.events))
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
    objects.append(_text("title", [44, 57], "Zoe Waveform Replay", 31, "#67e8f9"))
    objects.append(_text("subtitle", [46, 86], "Named VCD signals · legacy storage IDs · bounded evidence", 15, "#9fb1c8"))
    source = replay.source["path"]
    source_display = source if len(source) <= 84 else source[:81] + "..."
    objects.append(_text("source", [46, 122], f"Source: {source_display}", 13, "#9fb1c8"))
    objects.append(_text("source-hash", [46, 147], f"SHA-256 {replay.source['sha256'][:32]}... · {len(replay.events)} retained events", 12, "#9fb1c8"))
    for row, signal in enumerate(analysis["signals"][:8]):
        top = 190 + row * 57
        color = "#f0abfc" if signal["identifier"] == selected else STATUS_COLORS[signal["status"]]
        objects.append(_text(f"signal-name-{row}", [50, top], signal["name"][:43], 13, color))
        objects.append(_text(f"signal-status-{row}", [470, top], f"{signal['status']} · {signal['functional_label']}", 12, STATUS_COLORS[signal["status"]]))
        objects.append(_text(f"signal-count-{row}", [856, top], f"{signal['event_count']} events", 11, "#9fb1c8"))
    selected_signal = next(signal for signal in analysis["signals"] if signal["identifier"] == selected)
    trace = [event for event in replay.events if event["signal"] == selected]
    if not trace:
        raise ValueError("selected signal has no retained events")
    first_time = trace[0]["time"]
    last_time = trace[-1]["time"]
    points = []
    for index, event in enumerate(trace):
        x = 70 + index * 850 / max(1, len(trace) - 1)
        try:
            level = int(event["value"], 16) if replay.source["format"] != "vcd" else int(event["value"])
            y = 667 - (1 if level in {1, 3} else 0) * 75
        except ValueError:
            y = 628
        points.append([x, y])
    if len(points) == 1:
        x, y = points[0]
        objects.append({"id": "selected-trace", "type": "rectangle", "bounds": [x - 4, y - 4, x + 4, y + 4], "stroke": "#f0abfc", "fill": "#f0abfc", "width": 2})
    else:
        objects.append({"id": "selected-trace", "type": "polyline", "points": points, "stroke": "#f0abfc", "fill": "none", "width": 2})
    objects.append(_text("selected-title", [50, 559], f"Selected: {selected_signal['name'][:54]}", 17, "#f0abfc"))
    objects.append(_text("selected-status", [50, 590], f"{selected_signal['status']} · period {selected_signal['period_ps']} ps · no identity claim", 13, STATUS_COLORS[selected_signal["status"]]))
    objects.append(_text("time-range", [50, 700], f"first={first_time} ps · last={last_time} ps · ordinal replay only", 13, "#9fb1c8"))
    objects.append(_text("boundary", [50, 731], "Measurement != evidence != belief update != action · no live acquisition", 13, "#fda4af"))
    scene = _scene("zoe-waveform-replay", 1000, 760, objects, "Zoe Waveform Replay · bounded signal evidence")
    return scene, analysis


def export_waveform(replay, path, kind=None, width=1400, selected=None):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("waveform export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("waveform export directory does not exist")
    scene, _ = waveform_scene(replay, selected)
    report = verify_vdi(scene) if kind == "gem" else verify(scene)
    if not report.passed:
        raise ValueError(report.text())
    if kind == "gem":
        write_metafile(scene, path)
    elif kind == "svg":
        write_svg(scene, path, width)
    else:
        write_png(scene, path, width)
    return path

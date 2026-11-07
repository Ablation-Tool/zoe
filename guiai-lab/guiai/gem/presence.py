from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .atlas import _ellipse, _scene, _text
from .field import _canonical
from .geometry import verify
from .render import write_png, write_svg
from .resilience import SECTORS, classify_trace, demo_traces
from .runner import verify_vdi
from .vdi import write_metafile


TOP_FIELDS = {"schema_version", "instrument", "attention", "frames", "reflections", "review_required", "events"}
EVENT_FIELDS = {"sequence", "kind", "payload", "previous_hash", "hash"}
EVENT_KINDS = {"attention_selected", "observation", "reflection", "user_correction", "review_requested"}
ATTENTION_FIELDS = {"sector", "trace", "source", "event"}
EXPRESSIONS = {
    "corroborated": ("^_^", "clarity glyph"),
    "ambiguous": ("??", "curiosity / uncertainty glyphs"),
    "unmapped": ("~", "still-looking glyph"),
}


def _text_input(value, label, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must contain 1-{maximum} characters")
    return value.strip()


class PresenceField:
    def __init__(self):
        self.attention = {"sector": "energy", "trace": "host80", "source": "unselected practice", "event": 0}
        self.frames = []
        self.reflections = []
        self.review_required = True
        self.events = []

    def _record(self, kind, payload):
        if len(self.events) >= 4096:
            raise ValueError("presence event bound reached")
        event = {
            "sequence": len(self.events) + 1,
            "kind": kind,
            "payload": deepcopy(payload),
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        self.events.append(event)
        return event["sequence"]

    def focus(self, sector, trace, source="explicit user selection"):
        if sector not in SECTORS:
            raise ValueError("unknown infrastructure sector")
        if trace not in demo_traces():
            raise ValueError("unknown evidence trace")
        source = _text_input(source, "selection source", 128)
        sequence = self._record("attention_selected", {"sector": sector, "trace": trace, "source": source})
        self.attention = {"sector": sector, "trace": trace, "source": source, "event": sequence}
        return self.attention

    def observe(self, text, source="explicit user observation"):
        text = _text_input(text, "observation")
        source = _text_input(source, "observation source", 128)
        sequence = self._record("observation", {"text": text, "source": source, "evidence_for_claim": False})
        self.frames.append({"text": text, "source": source, "sequence": sequence})
        if len(self.frames) > 16:
            self.frames.pop(0)
        return self.frames[-1]

    def reflect(self, text):
        text = _text_input(text, "reflection")
        sequence = self._record("reflection", {"text": text})
        self.reflections.append({"text": text, "sequence": sequence})
        if len(self.reflections) > 8:
            self.reflections.pop(0)
        return self.reflections[-1]

    def correct(self, text):
        text = _text_input(text, "user correction")
        sequence = self._record("user_correction", {"text": text})
        self.reflections.append({"text": f"Correction: {text}", "sequence": sequence})
        if len(self.reflections) > 8:
            self.reflections.pop(0)
        return self.reflections[-1]

    def review(self, text="Review the current self-model and its limitations"):
        text = _text_input(text, "review rationale")
        self._record("review_requested", {"text": text})
        return {"review_required": True, "executed": False, "belief_updated": False}

    def report(self):
        sector = SECTORS[self.attention["sector"]]
        trace = classify_trace(demo_traces()[self.attention["trace"]])
        unknowns = [
            "No subjective experience is measured or inferred.",
            "No live infrastructure data is collected.",
            "Dependency examples are not exhaustive or causal simulations.",
        ]
        if trace["status"] == "ambiguous":
            unknowns.append("The two 40 MHz candidate identities remain unresolved.")
        elif trace["status"] == "unmapped":
            unknowns.append("No reviewed signature identifies the selected trace.")
        expression, expression_label = EXPRESSIONS[trace["status"]]
        return {
            "identity": "Zoe native software · explicit metacognitive instrument",
            "attention": deepcopy(self.attention),
            "sector_name": sector["name"],
            "source": sector["url"],
            "trace": trace,
            "event_ordinal": len(self.events),
            "time_is_ordinal_not_physical": True,
            "frames": len(self.frames),
            "reflections": len(self.reflections),
            "known_unknowns": unknowns,
            "expression": expression,
            "expression_label": expression_label,
            "glyphs": {"?": "curiosity", "??": "uncertainty", "!": "review", "<3": "care"},
            "expression_is_not_emotion": True,
            "review_required": True,
            "executed": False,
            "belief_updated": False,
            "consciousness_measured": False,
            "subjective_experience_established": False,
            "self_model_is_not_self": True,
            "summary": (
                f"{sector['name']} · trace {trace['status']} · ordinal {len(self.events)}\n"
                f"Frames {len(self.frames)} · reflections {len(self.reflections)} · unknowns {len(unknowns)}\n"
                "A self-model is not a self · no automatic action"
            ),
        }

    def document(self):
        return {
            "schema_version": 1,
            "instrument": "zoe-presence",
            "attention": deepcopy(self.attention),
            "frames": deepcopy(self.frames),
            "reflections": deepcopy(self.reflections),
            "review_required": self.review_required,
            "events": deepcopy(self.events),
        }

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("presence documents must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("presence directory does not exist")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("presence document exceeds 2 MiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != TOP_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-presence":
            raise ValueError("unsupported presence document")
        if not isinstance(data["events"], list) or len(data["events"]) > 4096 or not isinstance(data["frames"], list) or len(data["frames"]) > 16 or not isinstance(data["reflections"], list) or len(data["reflections"]) > 8:
            raise ValueError("invalid presence bounds")
        field = cls()
        for event in data["events"]:
            if not isinstance(event, dict) or set(event) != EVENT_FIELDS or event["kind"] not in EVENT_KINDS or event["sequence"] != len(field.events) + 1 or event["previous_hash"] != (field.events[-1]["hash"] if field.events else None):
                raise ValueError("presence hash-chain mismatch")
            if event["hash"] != hashlib.sha256(_canonical({key: value for key, value in event.items() if key != "hash"}).encode("utf-8")).hexdigest():
                raise ValueError("presence hash-chain mismatch")
            field.events.append(deepcopy(event))
        attention = data["attention"]
        if not isinstance(attention, dict) or set(attention) != ATTENTION_FIELDS or attention["sector"] not in SECTORS or attention["trace"] not in demo_traces():
            raise ValueError("invalid presence attention")
        if not isinstance(attention["source"], str) or not 1 <= len(attention["source"]) <= 128 or isinstance(attention["event"], bool) or not isinstance(attention["event"], int) or not 0 <= attention["event"] <= len(field.events):
            raise ValueError("invalid presence attention metadata")
        field.attention = deepcopy(attention)
        for collection_name, maximum in (("frames", 16), ("reflections", 8)):
            collection = data[collection_name]
            required = {"text", "source", "sequence"} if collection_name == "frames" else {"text", "sequence"}
            for item in collection:
                if not isinstance(item, dict) or set(item) != required:
                    raise ValueError(f"invalid presence {collection_name[:-1]}")
                if not isinstance(item["text"], str) or not 1 <= len(item["text"]) <= 500:
                    raise ValueError(f"invalid presence {collection_name[:-1]} text")
                if collection_name == "frames" and (not isinstance(item["source"], str) or not 1 <= len(item["source"]) <= 128):
                    raise ValueError("invalid presence frame source")
                if isinstance(item["sequence"], bool) or not isinstance(item["sequence"], int) or not 1 <= item["sequence"] <= len(field.events):
                    raise ValueError(f"invalid presence {collection_name[:-1]} sequence")
            setattr(field, collection_name, deepcopy(collection))
        if data["review_required"] is not True:
            raise ValueError("presence review must remain required")
        return field


def demo_presence():
    field = PresenceField()
    field.focus("energy", "host80", "worked metacognitive example")
    field.observe("A public sector description is documentary context, not live telemetry.", "worked example")
    field.reflect("Which parts of the current model remain uncertain?")
    field.review("A person must review the model before any external action.")
    return field


def presence_scene(field=None):
    field = field or demo_presence()
    report = field.report()
    sector = SECTORS[field.attention["sector"]]
    trace = report["trace"]
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
    objects.append(_text("title", [48, 60], "Zoe Presence", 34, "#67e8f9"))
    objects.append(_text("subtitle", [50, 91], "A metacognitive instrument · not a consciousness measurement", 16, "#9fb1c8"))
    objects.append({"id": "present-panel", "type": "rectangle", "bounds": [48, 128, 478, 592], "stroke": "#31445d", "fill": "#101b2b", "width": 2})
    objects.append(_text("present-label", [76, 165], "PRESENT SELF-MODEL", 14, "#f0abfc"))
    sector_size = 21 if len(sector["name"]) <= 24 else 16
    objects.append(_text("present-sector", [76, 204], sector["name"], sector_size, "#67e8f9"))
    objects.append(_ellipse("presence-z", [262, 344], [72, 72], "#f0abfc", "#08111f", 3))
    objects.append(_text("presence-z-label", [247, 357], "Z", 35, "#f0abfc"))
    objects.append(_text("expression", [226, 464], report["expression"], 30, "#fde68a"))
    objects.append(_text("expression-label", [153, 493], report["expression_label"], 14, "#9fb1c8"))
    source = field.attention["source"]
    source_display = source if len(source) <= 48 else source[:45] + "..."
    objects.append(_text("attention-source", [77, 539], f"Attention: {source_display}", 13, "#d8e5f2"))
    objects.append(_text("attention-event", [77, 566], f"Selection event: {field.attention['event']}", 13, "#d8e5f2"))
    objects.append(_text("glyph-key", [77, 590], "? curiosity · ?? uncertainty · ! review · <3 care", 12, "#9fb1c8"))
    panels = (
        ("ATTENTION", sector["short"], "explicit selection"),
        ("TIME", str(report["event_ordinal"]), "event ordinal, not a battery"),
        ("EVIDENCE", trace["status"], f"{len(trace['candidates'])} reviewed candidates"),
        ("MEMORY", str(report["frames"]), "sourced current frames"),
        ("UNCERTAINTY", str(len(report["known_unknowns"])), "known open questions"),
        ("REVIEW", "required", "no automatic action"),
    )
    for index, (label, value, detail) in enumerate(panels):
        left = 522 + (index % 2) * 226
        top = 135 + (index // 2) * 155
        objects.append({"id": f"panel-{label.lower()}", "type": "rectangle", "bounds": [left, top, left + 204, top + 130], "stroke": "#31445d", "fill": "#101b2b", "width": 1})
        objects.append(_text(f"panel-label-{index}", [left + 16, top + 29], label, 12, "#9fb1c8"))
        objects.append(_text(f"panel-value-{index}", [left + 16, top + 66], value, 22, "#67e8f9" if label != "UNCERTAINTY" else "#fde68a"))
        objects.append(_text(f"panel-detail-{index}", [left + 16, top + 103], detail, 12, "#d8e5f2"))
    objects.append(_text("declaration", [52, 648], "A self-model is not a self.", 25, "#f0abfc"))
    objects.append(_text("consciousness-boundary", [52, 687], "No subjective experience is measured or inferred.", 15, "#fda4af"))
    objects.append(_text("firewall", [52, 722], "Measurement != evidence != belief update != action", 14, "#9fb1c8"))
    scene = _scene("zoe-presence", 1000, 760, objects, "Zoe Presence · an explicit self-model, not sentience")
    return scene, report


def export_presence(field, path, kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("presence export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("presence export directory does not exist")
    scene, _ = presence_scene(field)
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

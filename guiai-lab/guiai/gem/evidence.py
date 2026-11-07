from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re

from .atlas import _line, _scene, _text
from .field import _canonical
from .geometry import verify
from .patchbay import _bounded_path, _sha
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


RECORD_FIELDS = {"bytes", "color", "complexity", "complexity_name", "document", "document_sha256", "format", "image", "label", "legacy_image", "novelty", "novelty_name", "original", "preview_sha256", "purpose", "what", "why"}
COMPLEXITY_NAMES = {1: "foundational", 2: "subsystem", 3: "integrated", 4: "cross-domain"}
NOVELTY_NAMES = {1: "established-reference", 2: "specialized-advance", 3: "platform-integration", 4: "exploratory-research"}
PURPOSE_COLORS = {
    "Amber": {"clock-timing"},
    "Cyan": {"detector-readout", "pcie-dma"},
    "Violet": {"detector-asic"},
    "Green": {"firmware-logic"},
    "Blue": {"validation"},
    "Rose": {"analysis-evidence"},
    "Slate": {"reference-guide", "hardware-design"},
}
BRIDGE_TITLES = {
    1: "A timing-aware readout digital twin",
    2: "A protocol ladder from LCB and STAR/Flink to ITk",
    3: "Guarded observability with ftools, regmap, Wupper, and Zoe",
    4: "One evidence stream, several senses",
    5: "A shadow AI navigator",
    6: "Cross-experiment design review",
    7: "A complexity-directed curriculum",
}
BRIDGE_MODES = {1: "synthetic-replay", 2: "observation-schema", 3: "observation-manifest", 4: "evidence-sonification", 5: "deterministic-retrieval", 6: "design-review", 7: "practice-curriculum"}
CURRICULUM_PROMPTS = {
    1: "Name the artifact, its source, and what it is meant to explain.",
    2: "Explain one bounded mechanism and the evidence that supports it.",
    3: "Explain how mechanisms interact, especially timing, framing, and host behavior.",
    4: "Trace evidence end to end and identify what remains unknown.",
}
LABEL = re.compile(r"^C([1-4])-N([1-4])-([A-Za-z]+)-([a-z0-9-]+)--([0-9a-f]{8})$")


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded_text(value, label, maximum=4096, empty=False):
    if not isinstance(value, str) or len(value) > maximum or not empty and not value:
        raise ValueError(f"invalid evidence {label}")
    return value


def _demo_record(complexity, novelty, color, purpose, suffix):
    complexity_name = COMPLEXITY_NAMES[complexity]
    label = f"C{complexity}-N{novelty}-{color}-{purpose}--{suffix}"
    document = f"synthetic/{label}.txt"
    return {
        "bytes": len(document),
        "color": color,
        "complexity": complexity,
        "complexity_name": complexity_name,
        "document": document,
        "document_sha256": _digest(document),
        "format": ".txt",
        "image": f"C{complexity}-{complexity_name}/{label}.png",
        "label": label,
        "legacy_image": f"demo-{suffix}.png",
        "novelty": novelty,
        "novelty_name": NOVELTY_NAMES[novelty],
        "original": document,
        "preview_sha256": _digest(label),
        "purpose": purpose,
        "what": f"Worked example for {purpose}",
        "why": "Synthetic navigation example, not a hardware observation.",
        "synthetic_example": True,
    }


def demo_index():
    records = [
        _demo_record(1, 1, "Slate", "reference-guide", "d0000001"),
        _demo_record(2, 2, "Violet", "detector-asic", "d0000002"),
        _demo_record(3, 1, "Amber", "clock-timing", "d0000003"),
        _demo_record(4, 3, "Cyan", "detector-readout", "d0000004"),
    ]
    return EvidenceIndex(Path("memory://demo-index.json"), Path("memory://corpus"), records, False, True)


class EvidenceIndex:
    def __init__(self, path, corpus, records, verified, synthetic=False):
        self.path = Path(path)
        self.corpus = Path(corpus)
        self.source_hashes_verified = verified
        self.synthetic_example = synthetic
        self.records = {}
        for record in records:
            self._validate(record)
            if record["label"] in self.records:
                raise ValueError("duplicate evidence label")
            self.records[record["label"]] = record

    @classmethod
    def load(cls, path, verify=False):
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") not in {1, 2} or not isinstance(data.get("files"), list):
            raise ValueError("unsupported evidence gallery index")
        if data["document_count"] != len(data["files"]) or data.get("image_count", len(data["files"])) != len(data["files"]):
            raise ValueError("evidence document and image counts disagree")
        corpus = path.parent.parent.parent.parent
        records = [deepcopy(record) for record in data["files"]]
        if len({record["image"] for record in records}) != len(records) or len({record["legacy_image"] for record in records}) != len(records):
            raise ValueError("evidence image or compatibility path is not unique")
        index = cls(path, corpus, records, verify, bool(data.get("synthetic_example", False)))
        expected = dict(data.get("distribution", {}))
        if expected:
            actual = index.distribution()
            for key, values in expected.items():
                if actual.get(key) != values:
                    raise ValueError(f"evidence distribution mismatch: {key}")
        if verify:
            for record in records:
                source = index.source_path(record)
                preview = index.preview_path(record)
                legacy = index.legacy_path(record)
                if not source.is_file() or _sha(source) != record["document_sha256"]:
                    raise ValueError(f"source hash mismatch: {record['document']}")
                if not preview.is_file() or _sha(preview) != record["preview_sha256"]:
                    raise ValueError(f"preview hash mismatch: {record['image']}")
                if not legacy.is_symlink() or legacy.resolve() != preview.resolve():
                    raise ValueError(f"compatibility link mismatch: {record['legacy_image']}")
        return index

    def _relative(self, value, root):
        value = _bounded_text(value, "path")
        if value.startswith("memory://"):
            return value
        path = PurePosixPath(value)
        if path.is_absolute() or "\\" in value:
            raise ValueError("evidence path escapes its declared root")
        candidate = root / Path(*path.parts)
        if not candidate.resolve().is_relative_to(root.resolve()):
            raise ValueError("evidence path escapes its declared root")
        return candidate

    def _validate(self, record):
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS and set(record) != RECORD_FIELDS | {"synthetic_example"}:
            raise ValueError("invalid evidence record fields")
        for field in ("document", "image", "label", "legacy_image", "original", "what", "why", "format", "purpose", "color", "complexity_name", "novelty_name"):
            _bounded_text(record[field], field, 4096 if field in {"document", "original", "why", "what"} else 512)
        if isinstance(record["bytes"], bool) or not isinstance(record["bytes"], int) or record["bytes"] < 1:
            raise ValueError("invalid evidence byte count")
        if not isinstance(record["complexity"], int) or isinstance(record["complexity"], bool) or record["complexity"] not in COMPLEXITY_NAMES or COMPLEXITY_NAMES[record["complexity"]] != record["complexity_name"]:
            raise ValueError("invalid evidence complexity")
        if not isinstance(record["novelty"], int) or isinstance(record["novelty"], bool) or record["novelty"] not in NOVELTY_NAMES or NOVELTY_NAMES[record["novelty"]] != record["novelty_name"]:
            raise ValueError("invalid evidence novelty")
        if record["color"] not in PURPOSE_COLORS or record["purpose"] not in PURPOSE_COLORS[record["color"]]:
            raise ValueError("evidence color and purpose disagree")
        match = LABEL.fullmatch(record["label"])
        if not match or int(match[1]) != record["complexity"] or int(match[2]) != record["novelty"] or match[3] != record["color"] or match[4] != record["purpose"]:
            raise ValueError("evidence label does not match its metadata")
        if record["image"] != f"C{record['complexity']}-{record['complexity_name']}/{record['label']}.png":
            raise ValueError("evidence image path does not match its label")
        for field in ("document_sha256", "preview_sha256"):
            if not isinstance(record[field], str) or len(record[field]) != 64 or any(character not in "0123456789abcdef" for character in record[field]):
                raise ValueError("invalid evidence digest")
        self._relative(record["document"], self.corpus)
        self._relative(record["image"], self.path.parent)
        self._relative(record["legacy_image"], self.path.parent)

    def source_path(self, record):
        return self._relative(record["document"], self.corpus)

    def preview_path(self, record):
        return self._relative(record["image"], self.path.parent)

    def legacy_path(self, record):
        return self._relative(record["legacy_image"], self.path.parent)

    def distribution(self):
        return {
            "color": dict(sorted(Counter(record["color"] for record in self.records.values()).items())),
            "complexity": dict(sorted(Counter(str(record["complexity"]) for record in self.records.values()).items())),
            "novelty": dict(sorted(Counter(str(record["novelty"]) for record in self.records.values()).items())),
            "purpose": dict(sorted(Counter(record["purpose"] for record in self.records.values()).items())),
        }

    def summary(self, record):
        return {
            **deepcopy(record),
            "source_path": str(self.source_path(record)),
            "preview_path": str(self.preview_path(record)),
            "legacy_path": str(self.legacy_path(record)),
            "source_hashes_verified": self.source_hashes_verified,
            "evidence_level": "worked-example" if record.get("synthetic_example") else "document-metadata",
            "not_hardware_measurement": True,
        }

    def query(self, text="", color=None, complexity=None, purpose=None, novelty=None, limit=16):
        text = _bounded_text(text, "query", 128, empty=True).casefold()
        if color is not None and color not in PURPOSE_COLORS:
            raise ValueError("unknown evidence color")
        if complexity is not None and (isinstance(complexity, bool) or not isinstance(complexity, int) or complexity not in COMPLEXITY_NAMES):
            raise ValueError("invalid complexity filter")
        if novelty is not None and (isinstance(novelty, bool) or not isinstance(novelty, int) or novelty not in NOVELTY_NAMES):
            raise ValueError("invalid novelty filter")
        if purpose is not None and not isinstance(purpose, str):
            raise ValueError("invalid purpose filter")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("evidence result limit must be between 1 and 64")
        selected = []
        for record in self.records.values():
            if color is not None and record["color"] != color or complexity is not None and record["complexity"] != complexity or purpose is not None and record["purpose"] != purpose or novelty is not None and record["novelty"] != novelty:
                continue
            haystack = " ".join(str(record[field]) for field in ("label", "document", "original", "what", "why")).casefold()
            if text not in haystack:
                continue
            selected.append(self.summary(record))
        selected.sort(key=lambda record: (record["complexity"], record["novelty"], record["label"]))
        return {"returned_count": min(len(selected), limit), "total_matches": len(selected), "records": selected[:limit], "query": text, "source_hashes_verified": self.source_hashes_verified, "synthetic_example": self.synthetic_example}

    def bridge(self, identifier):
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier not in BRIDGE_TITLES:
            raise ValueError("bridge identifier must be between 1 and 7")
        path = self.path.parent / "COMPLEXITY_AND_BRIDGES.md"
        title = BRIDGE_TITLES[identifier]
        result = {"id": identifier, "title": title, "mode": BRIDGE_MODES[identifier], "proposal_only": True, "executed": False, "hardware_connection_claimed": False, "source_path": str(path), "components": []}
        if not path.is_file():
            result.update({"source_sha256": _digest({"synthetic": title}), "first_experiment": "Inspect the proposed bridge and its evidence boundaries.", "success_criterion": "Preserve explicit evidence boundaries."})
            return result
        text = path.read_text(encoding="utf-8")
        match = re.search(rf"^## Bridge {identifier}: .*?$", text, re.MULTILINE)
        if not match:
            raise ValueError(f"bridge {identifier} is missing from the source document")
        start = match.end()
        following = re.search(r"^## (?:Bridge \d+:|What else is possible|Boundaries)", text[start:], re.MULTILINE)
        block = text[start:start + following.start() if following else len(text)]
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", block)
        for label, target in links:
            relative = PurePosixPath(target)
            if relative.is_absolute() or "\\" in target:
                raise ValueError("bridge target escapes its declared root")
            source = self.path.parent / Path(*relative.parts)
            if not source.resolve().is_relative_to(self.corpus.resolve()):
                raise ValueError("bridge target escapes its declared root")
            components = {"label": label, "path": str(source), "exists": source.exists()}
            if source.is_file():
                components["sha256"] = _sha(source)
            result["components"].append(components)
        experiment = re.search(r"### First experiment and success criterion\s+(.+?)(?=### |## |\Z)", block, re.DOTALL)
        result["first_experiment"] = " ".join(experiment[1].split()) if experiment else "Inspect the proposed bridge and its evidence boundaries."
        result["success_criterion"] = result["first_experiment"]
        result["source_sha256"] = _sha(path)
        return result

    def retrieve(self, text="", bridge=None, **filters):
        selection = self.query(text, **filters)
        return {
            "instrument": "zoe-evidence-retrieval",
            "query": text,
            "bridge": self.bridge(bridge) if bridge is not None else None,
            "observations": selection["records"],
            "returned_count": selection["returned_count"],
            "total_matches": selection["total_matches"],
            "source_hashes_verified": self.source_hashes_verified,
            "llm_called": False,
            "executed": False,
            "decline_to_act": not selection["records"],
            "missing_evidence_action": "no inference and no command" if not selection["records"] else "inspect cited source documents",
        }

    def curriculum(self, level, text=""):
        if isinstance(level, bool) or not isinstance(level, int) or level not in COMPLEXITY_NAMES:
            raise ValueError("curriculum level must be between 1 and 4")
        selection = self.query(text, complexity=level, limit=3)
        return {
            "instrument": "zoe-complexity-curriculum",
            "level": level,
            "level_name": COMPLEXITY_NAMES[level],
            "prompt": CURRICULUM_PROMPTS[level],
            "examples": selection["records"],
            "practice_next": "Choose one cited artifact, inspect it, and record what you actually learned and what remains uncertain.",
            "complexity_is_person_rating": False,
            "executed": False,
        }

    def ladder(self, stimuli=None):
        stimuli = stimuli or ["idle", "reset", "command", "identifier", "back_to_back_requests", "invalid_symbols"]
        if not isinstance(stimuli, (list, tuple)) or not 1 <= len(stimuli) <= 32:
            raise ValueError("protocol ladder requires 1-32 stimuli")
        allowed = {"idle", "reset", "command", "identifier", "back_to_back_requests", "invalid_symbols"}
        observations = []
        for index, stimulus in enumerate(stimuli, 1):
            if isinstance(stimulus, str):
                stimulus = {"kind": stimulus}
            if not isinstance(stimulus, dict) or stimulus.get("kind") not in allowed:
                raise ValueError("unsupported protocol stimulus")
            kind = stimulus["kind"]
            for model in ("LCB", "STAR/Flink"):
                observations.append({
                    "sequence": index,
                    "stimulus": kind,
                    "source_model": model,
                    "symbol": stimulus.get("symbol"),
                    "clock_domain": stimulus.get("clock_domain", "unspecified"),
                    "alignment_assumption": stimulus.get("alignment_assumption", "event-ordinal only"),
                    "observation": "source-model-specific observation required",
                    "unresolved": ["field meaning", "timing", "synthesis and hardware behavior"],
                })
        return {
            "instrument": "zoe-protocol-observation-ladder",
            "observations": observations,
            "model_count": 2,
            "direct_hardware_bridge": False,
            "equivalence_claimed": False,
            "executed": False,
            "boundary": "Compare observation schemas; do not infer protocol compatibility from similar names.",
        }

    def manifest(self):
        bridge = self.bridge(3)
        return {
            "instrument": "zoe-guarded-observation-manifest",
            "bridge": bridge,
            "allowed_operations": ["inspect register-map YAML", "inspect source and saved waveforms", "retrieve cited evidence"],
            "blocked_operations": ["fcheck -w", "fpepo with a data word", "load driver", "write register", "flash firmware", "execute shell"],
            "shell_execution": False,
            "driver_loading": False,
            "register_writes": False,
            "executed": False,
            "default_mode": "observe-only",
        }

    def design_review(self):
        return {
            "instrument": "zoe-cross-experiment-design-review",
            "bridge": self.bridge(6),
            "checklist": [
                "What evidence establishes command reachability in this artifact?",
                "What evidence establishes authorization in this artifact?",
                "Which timing and reset behavior is measured, simulated, or merely inferred?",
                "Which deployment limits remain specific to this architecture and evidence level?",
            ],
            "hardware_connection_claimed": False,
            "executed": False,
        }


def shadow_finding(path):
    path, _ = _bounded_path(path, 1024 * 1024)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("build_findings"), dict):
        raise ValueError("shadow retrieval requires a saved build_findings document")
    findings = data["build_findings"]
    inference = "Review the reported timing result against independent simulation and hardware evidence; static slack alone does not establish runtime failure." if findings.get("timing_met") is False else "Review the exact reported finding and its original evidence scope before proposing a test."
    return {
        "instrument": "zoe-shadow-evidence-retrieval",
        "source_path": str(path),
        "source_sha256": _sha(path),
        "observation": findings,
        "source": data.get("source"),
        "security_limits": data.get("security_limits"),
        "inference": inference,
        "llm_called": False,
        "executed": False,
        "evidence_missing": False,
    }


def save_evidence_report(report, path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("evidence reports must use a .json path")
    document = {key: value for key, value in report.items() if key != "digest"}
    document["digest"] = _digest(document)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(_canonical(document) + "\n")
    return path


def navigator_scene(index=None, bridge_id=1, timeline=None, text=""):
    index = index or demo_index()
    bridge = index.bridge(bridge_id)
    selection = index.query(text, limit=4)
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#0b1220", "fill": "#0b1220", "width": 1}]
    objects.append(_text("title", [44, 57], "Zoe Evidence Navigator", 31, "#67e8f9"))
    objects.append(_text("subtitle", [46, 86], "Sources before inference · bridges before connections", 15, "#9fb1c8"))
    counts = Counter(record["complexity"] for record in index.records.values())
    colors = {1: "#94a3b8", 2: "#c4b5fd", 3: "#fde68a", 4: "#67e8f9"}
    for level in range(1, 5):
        x = 50 + (level - 1) * 232
        objects.append({"id": f"level-{level}", "type": "rectangle", "bounds": [x, 133, x + 210, 205], "stroke": colors[level], "fill": "#111d30", "width": 1})
        objects.append(_text(f"level-title-{level}", [x + 14, 160], f"C{level} · {COMPLEXITY_NAMES[level]}", 14, colors[level]))
        objects.append(_text(f"level-count-{level}", [x + 14, 188], f"{counts[level]} previews", 13, "#dbeafe"))
    objects.append(_text("bridge-title", [50, 253], f"Bridge {bridge_id} · {bridge['title']}", 20, "#a7f3d0"))
    objects.append(_text("bridge-mode", [50, 279], f"{bridge['mode']} · proposal only · executed=False", 12, "#9fb1c8"))
    experiment = bridge["first_experiment"]
    for row, line in enumerate(__import__("textwrap").wrap(experiment, 85)[:4]):
        objects.append(_text(f"bridge-experiment-{row}", [50, 313 + row * 22], line, 12, "#dbeafe"))
    objects.append(_text("retrieval-title", [50, 407], f"Deterministic retrieval · {selection['total_matches']} matches", 16, "#67e8f9"))
    for row, record in enumerate(selection["records"]):
        top = 442 + row * 48
        objects.append(_text(f"record-label-{row}", [50, top], record["label"][:58], 12, colors[record["complexity"]]))
        objects.append(_text(f"record-source-{row}", [50, top + 21], f"{record['purpose']} · {record['document'][:65]}", 10, "#9fb1c8"))
    if timeline:
        observations = timeline["observations"]
        points = []
        for position, observation in enumerate(observations):
            x = 55 + position * 850 / max(1, len(observations) - 1)
            y = 704 - observation["buffer_occupancy"] * 7
            points.append([x, y])
        if len(points) == 1:
            points.append([points[0][0] + 1, points[0][1]])
        objects.append({"id": "timeline-occupancy", "type": "polyline", "points": points, "stroke": "#f0abfc", "fill": "none", "width": 2})
        objects.append(_text("timeline-label", [50, 626], f"Synthetic replay · {len(observations)} events · buffer occupancy", 13, "#f0abfc"))
    else:
        objects.append(_text("timeline-label", [50, 650], "No replay loaded · inspection remains read-only", 13, "#9fb1c8"))
    objects.append(_text("boundary", [50, 730], "Metadata is not hardware truth · no driver, register write, flash, or autonomous action", 13, "#fda4af"))
    scene = _scene("zoe-evidence-navigator", 1000, 760, objects, "Zoe Evidence Navigator · source-first bridges")
    summary = f"{len(index.records)} previews · bridge {bridge_id}: {bridge['title']}\n{selection['total_matches']} cited matches · llm_called=False · executed=False\nMetadata and synthetic replay remain distinct from hardware measurements."
    return scene, {"bridge": bridge, "retrieval": selection, "timeline": timeline, "summary": summary, "executed": False, "hardware_accessed": False}


def export_navigator(path, index=None, bridge_id=1, timeline=None, kind=None, width=1400, text=""):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("evidence scene export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("evidence export directory does not exist")
    scene, _ = navigator_scene(index, bridge_id, timeline, text)
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


def write_navigator_gallery(index, output, text="", color=None, complexity=None, purpose=None, limit=64):
    selection = index.query(text, color=color, complexity=complexity, purpose=purpose, limit=limit)
    root = index.path.parent
    cards = []
    for record in selection["records"]:
        source = os.path.relpath(record["source_path"], root)
        preview = os.path.relpath(record["preview_path"], root)
        label = html.escape(record["label"], quote=True)
        purpose_label = html.escape(f"{record['color']} · {record['purpose']} · N{record['novelty']}")
        cards.append(f'<figure class="{record["color"]}"><a href="{html.escape(source, quote=True)}"><img loading="lazy" src="{html.escape(preview, quote=True)}" alt="{label}"></a><figcaption><strong>{label}</strong><br>{purpose_label}<br><a href="{html.escape(source, quote=True)}">Original document</a><br><code>{record["document_sha256"]}</code></figcaption></figure>')
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zoe Evidence Navigator</title><style>body{{font-family:system-ui,sans-serif;margin:1.5rem;background:#0b1220;color:#e2e8f0}}h1{{font-size:1.5rem}}p{{color:#9fb1c8}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem}}figure{{margin:0;background:#101b2b;padding:.75rem;border:1px solid #475569;border-radius:.4rem}}img{{width:100%;height:180px;object-fit:contain;background:white}}figcaption{{font-size:.75rem;overflow-wrap:anywhere;margin-top:.5rem}}a{{color:#67e8f9}}code{{color:#a5b4fc;overflow-wrap:anywhere}}.Amber{{border-color:#fde68a}}.Cyan{{border-color:#67e8f9}}.Green{{border-color:#86efac}}.Violet{{border-color:#c4b5fd}}.Blue{{border-color:#93c5fd}}.Rose{{border-color:#fda4af}}.Slate{{border-color:#94a3b8}}</style></head><body><h1>Zoe Evidence Navigator</h1><p>{selection['returned_count']} of {selection['total_matches']} matches · deterministic retrieval · no hardware action · <a href="COMPLEXITY_AND_BRIDGES.md">bridge rubric</a></p><main class="grid">{''.join(cards)}</main></body></html>'''
    output = Path(output)
    if output.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("evidence gallery output must use .html")
    if output.exists():
        raise FileExistsError(output)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(document)
    return output, selection

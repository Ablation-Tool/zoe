from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re

from .atlas import _ellipse, _line, _scene, _text
from .cern_corpus import DEFAULT_CERN_ROOT, forge_summary
from .field import _fit


@dataclass
class RepairRecord:
    identifier: str
    title: str
    severity: str
    family: str
    source: str
    original_behavior: str
    desired_behavior: str
    evidence_level: str
    repair_status: str
    tests_total: int = 0
    tests_passed: int = 0
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]{2,127}", self.identifier):
            raise ValueError(f"invalid repair identifier: {self.identifier}")
        if self.severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}:
            raise ValueError(f"invalid severity for {self.identifier}")
        if self.repair_status not in {
            "reproduced", "triaged", "patched", "regression_verified", "integrated", "blocked",
        }:
            raise ValueError(f"invalid repair status for {self.identifier}")
        if not self.source or not self.original_behavior or not self.desired_behavior:
            raise ValueError(f"incomplete repair provenance for {self.identifier}")
        if not 0 <= self.tests_passed <= self.tests_total:
            raise ValueError(f"invalid test counts for {self.identifier}")
        if self.repair_status in {"regression_verified", "integrated"} and self.tests_passed < 1:
            raise ValueError(f"{self.identifier} cannot be verified without a passing test")

    def to_dict(self) -> dict:
        self.validate()
        result = asdict(self)
        result["executed"] = False
        return result


def _specs_repairs(cern_root: Path) -> list[RepairRecord]:
    path = cern_root / "analysis/specs-protocol/emitter-plx-findings.json"
    if not path.is_file():
        return []
    evidence = json.loads(path.read_text(encoding="utf-8"))
    emitter = evidence["simulation"]["emitter"]
    plx = evidence["simulation"]["plx"]
    rows = []
    for finding in evidence["findings"]:
        identifier = finding["id"]
        common = {
            "family": "hdl",
            "source": finding["evidence"],
            "evidence_level": finding["status"],
            "repair_status": "reproduced",
            "artifacts": [
                "analysis/specs-protocol/REPORT.md",
                "analysis/specs-protocol/emitter-plx-findings.json",
            ],
        }
        if identifier == "SPECS-MASTER-ZERO-LEN-001":
            rows.append(RepairRecord(
                identifier=identifier,
                title="Zero-length frame emits two payload bytes",
                severity="MEDIUM",
                original_behavior="count 0 -> two data bytes",
                desired_behavior="count 0 -> header + zero trailer; no payload",
                tests_total=emitter["checks"],
                tests_passed=emitter["checks"],
                notes=f"Exhaustive original-RTL coverage: {emitter['length_cases']} counts.",
                **common,
            ))
        elif identifier == "SPECS-MASTER-ONE-BYTE-CRC-001":
            rows.append(RepairRecord(
                identifier=identifier,
                title="One-byte payload trailer is zero",
                severity="MEDIUM",
                original_behavior="payload a5 -> trailer 00",
                desired_behavior="payload a5 -> trailer a5",
                tests_total=emitter["checks"],
                tests_passed=emitter["checks"],
                **common,
            ))
        elif identifier == "SPECS-MASTER-HEADER-MUX-001":
            common["repair_status"] = "triaged"
            rows.append(RepairRecord(
                identifier=identifier,
                title="Header checksum uses undriven selector 6",
                severity="LOW",
                original_behavior="header 04 01 00 -> third byte x0 in RTL",
                desired_behavior="complete checksum after selector 5 -> 50",
                notes="Gate-level and hardware behavior remain unresolved.",
                **common,
            ))
        elif identifier == "SPECS-PLX-READONLY-WRITE-STALL-001":
            common["tests_total"] = plx["checks"]
            common["tests_passed"] = plx["checks"]
            rows.append(RepairRecord(
                identifier=identifier,
                title="Read-only PLX write holds LREADY low",
                severity="MEDIUM",
                original_behavior="VERSION write -> state 1; ready remains low at idle",
                desired_behavior="undecoded write -> idle; ready released",
                **common,
            ))
    return rows


def _forge_repairs(cern_root: Path) -> list[RepairRecord]:
    path = cern_root / "analysis/corpus-optimization/forge-source-audit.json"
    if not path.is_file():
        return []
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for finding in report["findings"]:
        if finding["category"] == "deserialisation":
            rows.append(RepairRecord(
                identifier="CERN-WUPPER-YAML-001",
                title="Legacy YAML fallback permits unsafe object construction",
                severity=finding["severity"],
                family="python",
                source=finding["location"],
                original_behavior="Python 2 fallback calls yaml.load without a safe Loader",
                desired_behavior="safe_load only; reject Python-object constructors",
                evidence_level="FORGE_SOURCE_AND_MANUAL_TRIAGE",
                repair_status="triaged",
                artifacts=["analysis/corpus-optimization/forge-source-audit.json"],
            ))
        elif finding["severity"] in {"HIGH", "CRITICAL"}:
            identifier = "CERN-LEGACY-DOCS-" + finding["location"].rsplit("/", 1)[-1].split(".")[0].upper().replace("-", "_")
            rows.append(RepairRecord(
                identifier=identifier,
                title=f"Generated documentation contains {finding['title']}",
                severity=finding["severity"],
                family="javascript",
                source=finding["location"],
                original_behavior="legacy generated JavaScript uses dynamic function construction",
                desired_behavior="do not carry legacy executable documentation into Zoe; regenerate static accessible docs",
                evidence_level="FORGE_SOURCE_AND_CONTEXT_TRIAGE",
                repair_status="triaged",
                artifacts=["analysis/corpus-optimization/forge-source-audit.json"],
                notes="Third-party generated documentation is not a Zoe runtime entrypoint.",
            ))
    return rows


def repair_records(cern_root: str | Path = DEFAULT_CERN_ROOT) -> list[RepairRecord]:
    root = Path(cern_root).expanduser().resolve()
    records = [*_specs_repairs(root), *_forge_repairs(root)]
    identifiers = [record.identifier for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate repair identifiers")
    for record in records:
        record.validate()
    return records


def repair_report(records: list[RepairRecord], corpus: dict | None = None, forge: dict | None = None) -> dict:
    statuses = Counter(record.repair_status for record in records)
    severities = Counter(record.severity for record in records)
    return {
        "schema_version": 1,
        "instrument": "zoe-cern-repair-atlas",
        "repair_count": len(records),
        "status_counts": dict(sorted(statuses.items())),
        "severity_counts": dict(sorted(severities.items())),
        "tests_total": sum(record.tests_total for record in records),
        "tests_passed": sum(record.tests_passed for record in records),
        "corpus": corpus,
        "forge": forge,
        "records": [record.to_dict() for record in records],
        "execution": "analysis and visualization only; no hardware contact and no autonomous patching",
        "novelty_scope": "Zoe-native evidence-linked repair graph and differential behavior atlas; no external prior-art claim.",
    }


def default_repair_report(cern_root: str | Path = DEFAULT_CERN_ROOT) -> dict:
    root = Path(cern_root or DEFAULT_CERN_ROOT).expanduser().resolve()
    corpus_path = root / "analysis/corpus-optimization/full-corpus-v1/summary.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8")) if corpus_path.is_file() else None
    forge_path = root / "analysis/corpus-optimization/forge-source-audit.json"
    forge = forge_summary(forge_path) if forge_path.is_file() else None
    return repair_report(repair_records(root), corpus, forge)


def _rectangle(identifier: str, bounds: list[float], stroke: str, fill: str, width: float = 1) -> dict:
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def repair_scene(report: dict) -> tuple[object, dict]:
    cyan, yellow, pink, green, muted = "#67e8f9", "#fde68a", "#f0abfc", "#86efac", "#9fb1c8"
    red, orange = "#fda4af", "#fdba74"
    objects = [_rectangle("background", [0, 0, 1600, 1000], "#080d18", "#080d18")]
    objects.extend([
        _text("title", [38, 48], "ZOE × CERN · REPAIR ATLAS", 28, cyan),
        _text("subtitle", [40, 78], "source hash → finding → reproduced defect → patch → regression → native evidence", 15, "#e2e8f0"),
        _text("boundary", [40, 102], "Original artifacts remain evidence. Patches and optimizations enter Zoe with explicit verification.", 12, muted),
    ])
    corpus = report.get("corpus")
    file_count = corpus["file_count"] if corpus else 0
    unique = corpus["unique_content_count"] if corpus else 0
    duplicates = corpus["duplicates"]["groups"] if corpus else 0
    metrics = [
        ("files", file_count, "inventoried artifacts" if corpus else "inventory not yet available", cyan),
        ("unique", unique, "unique content hashes", green),
        ("repairs", report["repair_count"], "linked repair records", yellow),
        ("duplicates", duplicates, "duplicate-content groups", pink),
    ]
    for index, (name, value, label, color) in enumerate(metrics):
        x = 40 + index * 382
        objects.append(_rectangle(f"metric-{name}", [x, 128, x + 354, 218], color, "#101b2b", 1.5))
        objects.append(_text(f"metric-value-{name}", [x + 18, 174], f"{value:,}", 30, color))
        objects.append(_text(f"metric-label-{name}", [x + 18, 201], label, 12, muted))
    objects.append(_text("families-title", [40, 258], "CORPUS DISPOSITION", 16, cyan))
    families = list((corpus or {"families": {}})["families"].items())
    families.sort(key=lambda row: (-row[1], row[0]))
    maximum = max((count for _, count in families[:9]), default=1)
    palette = [cyan, green, yellow, pink, "#93c5fd", orange, "#c4b5fd", red, muted]
    for index, (family, count) in enumerate(families[:9]):
        y = 290 + index * 47
        width = 400 * count / maximum
        objects.append(_text(f"family-label-{index}", [40, y + 15], family, 12, "#d8e2ee"))
        objects.append(_rectangle(f"family-bar-{index}", [180, y, 180 + width, y + 23], palette[index % len(palette)], palette[index % len(palette)]))
        objects.append(_text(f"family-count-{index}", [190 + width, y + 16], f"{count:,}", 11, muted))
    if not families:
        objects.append(_text("family-empty", [40, 302], "Run the full corpus scan to populate this chart.", 13, muted))
    objects.append(_text("repair-title", [690, 258], "DIFFERENTIAL REPAIR GRAPH", 16, yellow))
    records = report["records"]
    status_colors = {
        "reproduced": orange,
        "triaged": muted,
        "patched": yellow,
        "regression_verified": green,
        "integrated": cyan,
        "blocked": red,
    }
    for index, record in enumerate(records[:6]):
        y = 282 + index * 96
        color = status_colors[record["repair_status"]]
        objects.append(_rectangle(f"repair-card-{index}", [680, y, 1560, y + 82], color, "#101b2b", 1.2))
        objects.append(_ellipse(f"repair-node-{index}", [704, y + 22], [7, 7], color, color))
        objects.append(_text(f"repair-name-{index}", [722, y + 25], _fit(record["title"], 62), 13, color))
        objects.append(_text(f"repair-id-{index}", [1230, y + 24], record["identifier"], 10, muted))
        objects.append(_text(f"repair-original-{index}", [704, y + 50], _fit("original  " + record["original_behavior"], 91), 11, orange))
        objects.append(_text(f"repair-desired-{index}", [704, y + 70], _fit("desired   " + record["desired_behavior"], 91), 11, green))
    objects.append(_text("coverage-title", [40, 738], "EVIDENCE COVERAGE", 16, cyan))
    coverage = (corpus or {}).get("coverage", {})
    hashed = coverage.get("hashed", 0)
    regular = (corpus or {}).get("regular_file_count", 0)
    ratio = hashed / regular if regular else 0
    objects.append(_rectangle("coverage-track", [40, 770, 610, 792], "#334155", "#101b2b"))
    objects.append(_rectangle("coverage-bar", [40, 770, 40 + 570 * ratio, 792], green, green))
    objects.append(_text("coverage-label", [40, 819], f"{hashed:,}/{regular:,} regular files hashed · {coverage.get('errors', 0):,} errors", 13, green if ratio == 1 else orange))
    forge = report.get("forge")
    if forge:
        objects.append(_text("forge-summary", [40, 848], f"FORGE: {forge['finding_count']} findings · gate {'PASS' if forge['gate_passed'] else 'FAIL'} · supported-source scope", 12, red if not forge["gate_passed"] else green))
    objects.append(_text("test-summary", [40, 880], f"Linked regression checks: {report['tests_passed']:,}/{report['tests_total']:,} passed · passing reproduction does not imply a repair exists", 12, muted))
    chain = ["SOURCE", "FINDING", "REPRO", "PATCH", "TEST", "ZOE"]
    for index, label in enumerate(chain):
        x = 680 + index * 148
        complete = index <= 2 and bool(records)
        color = green if complete else "#475569"
        objects.append(_rectangle(f"chain-{label.lower()}", [x, 918, x + 110, 958], color, "#101b2b"))
        objects.append(_text(f"chain-label-{label.lower()}", [x + 15, 944], label, 12, color))
        if index + 1 < len(chain):
            objects.append(_line(f"chain-arrow-{index}", [x + 112, 938], [x + 140, 938], muted, 1.2))
    objects.append(_text("chain-boundary", [40, 945], "No autonomous execution · no hardware contact · no unverified 'fixed' labels", 12, pink))
    scene = _scene("zoe-cern-repair-atlas", 1600, 1000, objects, "Zoe × CERN · Repair Atlas")
    return scene, report


def default_repair_document(cern_root: str | Path = DEFAULT_CERN_ROOT) -> tuple[object, dict]:
    return repair_scene(default_repair_report(cern_root))


def write_repair_report(report: dict, output: str | Path) -> Path:
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != ".json":
        raise ValueError("Repair Atlas output must use .json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return output

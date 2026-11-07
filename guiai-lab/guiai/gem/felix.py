from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
from html.parser import HTMLParser

from .cognitive import CognitiveField
from .field import _canonical, _fit


DEFAULT_CERN_ROOT = Path("/media/cowboy/research/CERN/Boutique")
MAX_FINDINGS_BYTES = 16 * 1024 * 1024
MAX_HTML_BYTES = 16 * 1024 * 1024
MAX_BUILDS = 4096
FELIX_NAME = re.compile(
    r"^(?P<card>FLX\d+)_(?P<flavor>[A-Z0-9]+)_(?P<channels>\d+)CH_"
    r"(?P<clock>[A-Z0-9]+)_GIT_(?P<branch>.+)_rm-(?P<release>[0-9.]+)_"
    r"(?P<build>\d+)_(?P<date>\d{6})_(?P<time>\d{4})\.(?P<suffix>.+)$"
)
ARTIFACT_KINDS = {
    ".bit": "bitstream",
    ".mcs": "flash-image",
    ".pdi": "versal-pdi",
    ".ltx": "debug-probes",
    ".xsa": "hardware-handoff",
    ".tar.gz": "build-package",
}


class _HDLHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_pre = False
        self.in_title = False
        self.pre_seen = False
        self.parts = []
        self.title_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.pre_seen = True
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre = False
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_pre:
            self.parts.append(data)
        if self.in_title:
            self.title_parts.append(data)


def recover_hdl_html(path):
    path = Path(path)
    if path.stat().st_size > MAX_HTML_BYTES:
        raise ValueError(f"HTML HDL source view is too large: {path}")
    parser = _HDLHTMLParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    if not parser.pre_seen:
        raise ValueError(f"HTML source view has no preformatted code: {path}")
    text = "".join(parser.parts).strip() + "\n"
    if not re.search(r"\b(entity|architecture|module|endmodule|package)\b", text, re.IGNORECASE):
        raise ValueError(f"HTML preformatted content is not recognizable HDL: {path}")
    return {
        "title": "".join(parser.title_parts).strip() or path.stem,
        "text": text,
        "line_count": len(text.splitlines()),
        "language": "verilog" if re.search(r"\bmodule\b", text, re.IGNORECASE) else "vhdl",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _load_findings(path):
    if path.stat().st_size > MAX_FINDINGS_BYTES:
        raise ValueError(f"FELIX findings file is too large: {path}")
    data = path.read_bytes()
    document = json.loads(data)
    if not isinstance(document, dict):
        raise ValueError(f"FELIX findings must be a JSON object: {path}")
    return document, _sha256_bytes(data)


def parse_felix_name(name):
    match = FELIX_NAME.fullmatch(name)
    if match is None:
        return None
    values = match.groupdict()
    suffix = values.pop("suffix")
    kind = next((kind for extension, kind in ARTIFACT_KINDS.items() if suffix == extension.lstrip(".")), None)
    if kind is None:
        return None
    stem = name[:-(len(suffix) + 1)]
    identifier = f"{values['card'].lower()}-{values['build']}-{values['date']}{values['time']}-{_sha256_bytes(stem.encode())[:8]}"
    return {
        "id": identifier,
        "stem": stem,
        "card": values["card"],
        "flavor": values["flavor"],
        "channels": int(values["channels"]),
        "clock": values["clock"],
        "branch": values["branch"],
        "release": values["release"],
        "build": int(values["build"]),
        "build_date": values["date"],
        "build_time": values["time"],
        "timestamp": values["date"] + values["time"],
        "artifact_kind": kind,
    }


def _analysis_summary(document, path, digest):
    platform = document.get("pdi") or document.get("platform") or {}
    sections = platform.get("cdo_sections") or platform.get("top_level_cdo_sections") or []
    source = document.get("source_findings") or document.get("build_findings") or {}
    provenance = document.get("source_provenance") or {}
    return {
        "path": str(path),
        "sha256": digest,
        "scope": document.get("scope", ""),
        "device": platform.get("device", ""),
        "design": platform.get("design", ""),
        "cdo_section_count": len(sections),
        "cdo_command_count": sum(section.get("command_count", 0) for section in sections if isinstance(section, dict)),
        "timing_met": source.get("timing_met"),
        "wns_ns": source.get("wns_ns"),
        "source_git_hash": provenance.get("source_git_hash", ""),
        "uncommitted_changes": provenance.get("uncommitted_changes"),
        "slr1_npi_length_anomaly": bool((document.get("platform") or {}).get("slr1_npi_length_anomaly")),
        "security_limits": document.get("security_limits", ""),
    }


def _matches_analysis(document, build):
    provenance = document.get("source_provenance") or {}
    timestamp = provenance.get("build_datetime")
    if timestamp:
        return str(timestamp) == build["timestamp"]
    artifacts = json.dumps(document.get("artifacts", {}), sort_keys=True)
    return build["stem"] in artifacts


class FelixCorpus:
    def __init__(self, cern_root=None):
        selected_root = cern_root or os.environ.get("ZOE_CERN_ROOT") or DEFAULT_CERN_ROOT
        from .cern_layout import CorpusLayout
        self.layout = CorpusLayout(selected_root)
        self.cern_root = self.layout.root
        self.firmware_root = self.layout.path("fw/felix")
        if not self.firmware_root.is_dir():
            raise ValueError(f"FELIX firmware directory is unavailable: {self.firmware_root}")
        self.builds = []
        self.ignored_files = []
        self.fingerprint = ""
        self._index()
        self.selected_id = self.default_build_id()

    def _index(self):
        grouped = {}
        ignored = []
        for path in sorted(self.firmware_root.iterdir()):
            if not path.is_file():
                continue
            parsed = parse_felix_name(path.name)
            if parsed is None:
                ignored.append({"name": path.name, "size": path.stat().st_size})
                continue
            artifact_kind = parsed.pop("artifact_kind")
            build = grouped.setdefault(parsed["id"], {**parsed, "artifacts": []})
            stat = path.stat()
            build["artifacts"].append({
                "name": path.name,
                "path": str(path),
                "kind": artifact_kind,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            })
        if len(grouped) > MAX_BUILDS:
            raise ValueError(f"FELIX corpus exceeds the {MAX_BUILDS}-build bound")
        builds = []
        for build in grouped.values():
            build["artifacts"].sort(key=lambda item: item["name"])
            build["artifact_count"] = len(build["artifacts"])
            build["total_bytes"] = sum(item["size"] for item in build["artifacts"])
            build["analysis"] = None
            candidate = self.layout.path("analysis") / f"felix-{build['card'].lower()}" / "findings.json"
            if candidate.is_file():
                document, digest = _load_findings(candidate)
                if _matches_analysis(document, build):
                    build["analysis"] = _analysis_summary(document, candidate, digest)
            build["evidence_state"] = "analyzed" if build["analysis"] else "indexed"
            build["supporting_evidence"] = self._supporting_evidence(build)
            builds.append(build)
        if not builds:
            raise ValueError(f"no recognized FELIX build artifacts in {self.firmware_root}")
        self.builds = sorted(builds, key=lambda item: (item["timestamp"], item["card"], item["id"]))
        self.ignored_files = ignored
        self.tim_analysis = self._tim_analysis_summary()
        self.simulation_evidence = self._simulation_evidence()
        from .felix_sources import host_integration_evidence, star_flink_evidence
        self.host_integration = host_integration_evidence(self.layout)
        self.star_flink = star_flink_evidence(self.layout, self.simulation_evidence)
        fingerprint_document = {
            "layout": self.layout.kind,
            "boutique_verification": self.layout.verification(),
            "builds": deepcopy(self.builds),
            "ignored": ignored,
            "timing_documents": self._timing_documents(),
            "tim_analysis": self.tim_analysis,
            "simulation_evidence": self.simulation_evidence,
            "host_integration": self.host_integration,
            "star_flink": self.star_flink,
        }
        self.fingerprint = _sha256_bytes(_canonical(fingerprint_document).encode())

    def _timing_documents(self):
        root = self.layout.path("docs") / "tim"
        if not root.is_dir():
            return []
        rows = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            rows.append({
                "path": self.layout.relative(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            })
            if len(rows) >= 512:
                raise ValueError(f"TIM timing-document corpus exceeds the 512-file bound: {root}")
        return rows

    def _tim_analysis_summary(self):
        path = self.layout.path("analysis") / "tim-fpga" / "findings.json"
        firmware = self.layout.path("fw") / "tim"
        inventory = {
            "bit_files": len(list(firmware.glob("*.bit"))) if firmware.is_dir() else 0,
            "mcs_files": len(list(firmware.glob("*.mcs"))) if firmware.is_dir() else 0,
            "source_archives": len(list(firmware.glob("*.zip"))) + len(list(firmware.glob("*.tar.gz"))) if firmware.is_dir() else 0,
        }
        result = {
            "inventory": inventory,
            "latest_bit": str(firmware / "tim_fpga2_v5d_2024-06-20.bit"),
            "latest_mcs": str(firmware / "tim_fpga2_v5d_2024-06-20.mcs"),
            "source_v20": str(self.layout.path("analysis") / "tim-fpga" / "source-v20"),
            "source_archive": str(firmware / "TIM3_Firmware_v20_src_2011-08-15.tar.gz"),
            "control_software": str(self.layout.path("sw") / "timsoft.tar.gz"),
            "fftv_document": str(self.layout.path("docs") / "FFTV_Document.pdf"),
            "fftv_results": str(self.layout.path("docs") / "FFTV_test_results.doc"),
            "fftv_sim_results": str(self.layout.path("sims") / "fftv_results.xls"),
            "dependency_chain": ["TTCrx/TTCrq", "TIM", "ROD/BOC/RCC/VME", "SCT/Pixel readout"],
            "analysis_path": str(path),
            "analysis_sha256": None,
            "baseline": None,
            "latest": None,
            "version_inventory": None,
            "changelog": None,
        }
        if path.is_file():
            document, digest = _load_findings(path)
            result.update({
                "analysis_sha256": digest,
                "baseline": document.get("baseline"),
                "latest": document.get("latest"),
                "version_inventory": document.get("version_inventory"),
                "changelog": document.get("changelog"),
            })
        return result

    def _simulation_evidence(self):
        root = self.layout.path("sims")
        result = {
            "root": str(root),
            "hdl_files": 0,
            "hdl_bytes": 0,
            "hdl_extensions": {},
            "html_hdl_files": 0,
            "html_hdl_bytes": 0,
            "html_sources": [],
            "lcb_testbench_present": (root / "lcb").is_dir(),
            "star_flink_testbench_present": (root / "star_flink").is_dir(),
            "stream_splitter_present": (root / "stream8040" / "streamsplit_8040_struct.vhd").is_file(),
            "fftv_results_present": (root / "fftv_results.xls").is_file(),
            "examples": [],
        }
        if not root.is_dir():
            return result
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            extension = path.suffix.lower()
            if extension in {".v", ".sv", ".vhd", ".vhdl"}:
                stat = path.stat()
                result["hdl_files"] += 1
                result["hdl_bytes"] += stat.st_size
                result["hdl_extensions"][extension] = result["hdl_extensions"].get(extension, 0) + 1
                if len(result["examples"]) < 24:
                    result["examples"].append(self.layout.relative(path))
            elif extension in {".htm", ".html"} and "ContentFrame" in path.name:
                try:
                    recovered = recover_hdl_html(path)
                except (OSError, UnicodeError, ValueError):
                    continue
                result["html_hdl_files"] += 1
                result["html_hdl_bytes"] += len(recovered["text"].encode())
                if len(result["html_sources"]) < 128:
                    result["html_sources"].append({
                        "path": self.layout.relative(path),
                        "title": recovered["title"],
                        "language": recovered["language"],
                        "line_count": recovered["line_count"],
                        "sha256": recovered["sha256"],
                    })
            if result["hdl_files"] + result["html_hdl_files"] > 4096:
                raise ValueError(f"simulation HDL corpus exceeds the 4096-file bound: {root}")
        return result

    def _supporting_evidence(self, build):
        module = "ItkStrip" if build["flavor"] == "STRIPS" else "LpGBT" if build["flavor"] == "LPGBT" else ""
        candidates = [
            ("firmware_source", self.layout.path("source") / "firmware"),
            ("detector_module_source", self.layout.path("source") / "firmware" / "sources" / module if module else self.layout.path("source") / "firmware" / "sources"),
            ("pcie_dma", self.layout.path("source") / "wupper"),
            ("card_api", self.layout.path("source") / "flxcard"),
            ("host_tools", self.layout.path("source") / "ftools"),
            ("register_maps", self.layout.path("source") / "regmap"),
            ("firmware_specification", self.layout.path("docs") / "FELIX_Phase2_firmware_specs.pdf"),
            ("firmware_changelog", self.layout.path("docs") / "CHANGELOG.TXT"),
            ("timing_trigger_history", self.layout.path("docs") / "tim"),
            ("master_analysis", self.layout.path("analysis") / "REPORT.md"),
            ("engineering_data", self.layout.path("data")),
            ("simulations", self.layout.path("sims")),
            ("asic_models", self.layout.path("asic")),
        ]
        return [
            {"role": role, "path": str(path), "present": path.exists()}
            for role, path in candidates
        ]

    def default_build_id(self):
        analyzed = [build for build in self.builds if build["analysis"]]
        return (analyzed or self.builds)[-1]["id"]

    def build(self, identifier=None):
        identifier = identifier or self.selected_id
        exact = [build for build in self.builds if identifier in {build["id"], build["stem"]}]
        if exact:
            return exact[0]
        matches = [build for build in self.builds if identifier.casefold() in build["stem"].casefold()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"FELIX build selector is ambiguous: {identifier}")
        raise ValueError(f"unknown FELIX build: {identifier}")

    def refresh(self):
        replacement = FelixCorpus(self.cern_root)
        changed = replacement.fingerprint != self.fingerprint
        selected = self.selected_id
        self.builds = replacement.builds
        self.ignored_files = replacement.ignored_files
        self.tim_analysis = replacement.tim_analysis
        self.simulation_evidence = replacement.simulation_evidence
        self.host_integration = replacement.host_integration
        self.star_flink = replacement.star_flink
        self.fingerprint = replacement.fingerprint
        self.selected_id = selected if any(build["id"] == selected for build in self.builds) else replacement.selected_id
        return changed

    def summary(self):
        cards = sorted({build["card"] for build in self.builds})
        timing_documents = self._timing_documents()
        manual = self.layout.path("docs") / "tim" / "TIM_manual.html"
        return {
            "cern_root": str(self.cern_root),
            "layout": self.layout.kind,
            "boutique_catalogue": self.layout.catalogue(),
            "firmware_root": str(self.firmware_root),
            "fingerprint_sha256": self.fingerprint,
            "build_count": len(self.builds),
            "analyzed_build_count": sum(build["analysis"] is not None for build in self.builds),
            "artifact_count": sum(build["artifact_count"] for build in self.builds),
            "ignored_file_count": len(self.ignored_files),
            "cards": cards,
            "supporting_roots_present": sum(any(row["present"] for row in build["supporting_evidence"]) for build in self.builds),
            "tim_document_count": len(timing_documents),
            "tim_document_bytes": sum(row["size"] for row in timing_documents),
            "tim_manual_present": manual.is_file(),
            "tim_clock_reference_mhz": 40.08 if manual.is_file() else None,
            "tim_analysis": deepcopy(self.tim_analysis),
            "simulation_evidence": deepcopy(self.simulation_evidence),
            "host_integration": deepcopy(self.host_integration),
            "star_flink": deepcopy(self.star_flink),
        }


class FelixObserver:
    def __init__(self, cern_root=None):
        self.corpus = FelixCorpus(cern_root)
        self.memory = CognitiveField(working_capacity=4)
        self.history = []
        self.refreshes = 0

    @property
    def selected(self):
        return self.corpus.build()

    def select(self, identifier):
        self.corpus.selected_id = self.corpus.build(identifier)["id"]
        return self.selected

    def observe(self, identifier=None, next_build=False):
        if next_build:
            identifiers = [build["id"] for build in self.corpus.builds]
            position = identifiers.index(self.corpus.selected_id)
            identifier = identifiers[(position + 1) % len(identifiers)]
        build = self.select(identifier) if identifier else self.selected
        analysis = build["analysis"]
        text = (
            f"{build['card']} {build['flavor']} {build['channels']}CH build {build['build']} "
            f"rm-{build['release']}: {build['evidence_state']}, {build['artifact_count']} artifacts"
        )
        if analysis and analysis["wns_ns"] is not None:
            text += f", WNS {analysis['wns_ns']:g} ns"
        representation = self.memory.encode(
            text,
            f"felix-corpus:{build['id']}",
            ["felix", build["card"].lower(), build["evidence_state"]],
        )
        self.history.append({
            "build_id": build["id"],
            "representation_id": representation["id"],
            "event_sequence": representation["event_sequence"],
        })
        return deepcopy(build)

    def refresh(self):
        changed = self.corpus.refresh()
        self.refreshes += 1
        if changed:
            self.memory.encode(
                f"FELIX corpus now has {len(self.corpus.builds)} builds with fingerprint {self.corpus.fingerprint[:12]}.",
                f"felix-corpus-refresh:{self.corpus.fingerprint}",
                ["felix", "corpus", "refresh"],
            )
        return changed

    def report(self):
        build = self.selected
        corpus = self.corpus.summary()
        observations = len(self.history)
        analysis = build["analysis"]
        summary = (
            f"{build['card']} build {build['build']} · {build['flavor']} {build['channels']}CH · "
            f"{build['evidence_state']} · {corpus['build_count']} builds · {observations} observations · "
            "filesystem evidence, not hardware telemetry"
        )
        if analysis and analysis["wns_ns"] is not None:
            summary += f" · WNS {analysis['wns_ns']:g} ns"
        return {
            "summary": summary,
            "mode": "filesystem-corpus-observation",
            "hardware_connected": False,
            "executed": False,
            "selected_build": deepcopy(build),
            "corpus": corpus,
            "observation_count": observations,
            "refresh_count": self.refreshes,
            "memory_events": len(self.memory.events),
            "working_memory": deepcopy(self.memory.working),
            "evicted_memory": len(self.memory.evicted),
            "history": deepcopy(self.history[-64:]),
        }

    def document(self):
        return {
            "schema_version": 1,
            "instrument": "zoe-felix-observation",
            "mode": "filesystem-corpus-observation",
            "hardware_connected": False,
            "executed": False,
            "selected_build_id": self.corpus.selected_id,
            "history": deepcopy(self.history),
            "corpus": self.corpus.summary(),
            "selected_build": deepcopy(self.selected),
            "memory": self.memory.document(),
            "integrity": "FELIX observations use Zoe Cognitive Field's canonical-json-sha256-chain; tamper evidence, not authentication",
        }

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("FELIX observation memory must use a .json path")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(self.document(), stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            stream.write("\n")
        return path


def default_felix_observer(cern_root=None, build=None, observations=1):
    if isinstance(observations, bool) or not isinstance(observations, int) or not 1 <= observations <= 64:
        raise ValueError("FELIX observation count must be from 1 to 64")
    observer = FelixObserver(cern_root)
    if build:
        observer.select(build)
    observer.observe()
    for _ in range(observations - 1):
        observer.observe(next_build=True)
    return observer


def _rectangle(identifier, bounds, stroke, fill, width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def _orbit(identifier, center, radii, phase, color):
    points = []
    rotation = math.radians(phase)
    for index in range(96):
        angle = math.tau * index / 96
        x, y = radii[0] * math.cos(angle), radii[1] * math.sin(angle)
        points.append([center[0] + x * math.cos(rotation) - y * math.sin(rotation), center[1] + x * math.sin(rotation) + y * math.cos(rotation)])
    return {"id": identifier, "type": "polygon", "points": points, "stroke": color, "fill": "none", "width": 1.2}


def felix_scene(observer):
    from .atlas import _ellipse, _line, _scene, _text

    report = observer.report()
    build = report["selected_build"]
    corpus = report["corpus"]
    analysis = build["analysis"]
    cyan, green, yellow, pink, muted = "#67e8f9", "#86efac", "#fde68a", "#f0abfc", "#9fb1c8"
    objects = [_rectangle("background", [0, 0, 1400, 900], "#080d18", "#080d18")]
    objects.extend([
        _text("title", [38, 50], "ZOE × FELIX · LIVING READOUT EVIDENCE", 28, cyan),
        _text("subtitle", [40, 80], f"{build['stem']}", 13, "#e2e8f0"),
        _text("scope", [40, 106], "Filesystem observations only · no hardware connection · no control action · executed=False", 12, "#fda4af"),
    ])
    metrics = [
        ("builds", corpus["build_count"], cyan),
        ("artifacts", corpus["artifact_count"], green),
        ("analyzed", corpus["analyzed_build_count"], yellow),
        ("observations", report["observation_count"], pink),
    ]
    for index, (label, value, color) in enumerate(metrics):
        x = 40 + index * 200
        objects.append(_rectangle(f"metric-{label}", [x, 130, x + 178, 211], color, "#101b2b", 1.5))
        objects.append(_text(f"metric-value-{label}", [x + 16, 174], str(value), 30, color))
        objects.append(_text(f"metric-label-{label}", [x + 16, 198], label, 12, muted))
    objects.append(_text("state", [865, 161], build["evidence_state"].upper(), 26, green if analysis else yellow))
    objects.append(_text("state-detail", [865, 190], f"{build['card']} · build {build['build']} · rm-{build['release']}", 15, "#e2e8f0"))
    host = corpus["host_integration"]
    simulation = corpus["simulation_evidence"]
    tim = corpus["tim_analysis"]
    observation_tools = len(host["ftools"]["observation_tools"])
    descriptor_count = host["wupper"]["descriptor_count"] or "?"
    pipeline = [("FRONT-END", build["flavor"]), ("LINKS", f"{build['channels']} channels"), ("FELIX", build["card"]), ("WUPPER", f"{descriptor_count} DMA descriptors"), ("HOST", f"{observation_tools} observation tools"), ("ZOE", "memory + scene")]
    for index, (title, detail) in enumerate(pipeline):
        x = 40 + index * 225
        color = pink if title == "ZOE" else cyan if title == "FELIX" else green if title == "WUPPER" else muted
        objects.append(_rectangle(f"pipeline-{title.lower()}", [x, 254, x + 185, 334], color, "#101b2b", 2))
        objects.append(_text(f"pipeline-title-{index}", [x + 15, 285], title, 17, color))
        objects.append(_text(f"pipeline-detail-{index}", [x + 15, 313], detail, 12, "#d8e2ee"))
        if index + 1 < len(pipeline):
            objects.append(_line(f"pipeline-link-{index}", [x + 185, 294], [x + 225, 294], cyan, 2))
    channel_count = min(build["channels"], 24)
    for index in range(channel_count):
        x = 263 + index * 126 / max(channel_count - 1, 1)
        objects.append(_ellipse(f"channel-{index}", [x, 354], [3.2, 3.2], cyan if index % 3 else green, cyan if index % 3 else green))
    objects.append(_text("channel-caption", [255, 379], f"{build['channels']} {build['clock']} links · visual channel index, not live link health", 11, muted))
    latest = ((tim.get("latest") or {}).get("bit") or {}).get("version", "TIM")
    timing_text = (
        f"TIM {latest} · {tim['inventory']['bit_files']} BIT/{tim['inventory']['mcs_files']} MCS · "
        f"{corpus['tim_document_count']} timing docs · HDL {simulation['hdl_files']} raw + {simulation['html_hdl_files']} HTML · "
        "STAR/Flink mapped · host writes blocked"
    )
    objects.append(_text("timing-context", [40, 398], _fit(timing_text, 170), 10, yellow))
    objects.append(_rectangle("build-panel", [40, 408, 860, 568], "#475569", "#0e1828"))
    objects.append(_text("build-title", [60, 440], f"{build['card']} / {build['flavor']} / {build['channels']}CH / {build['clock']}", 20, yellow))
    objects.append(_text("build-branch", [60, 468], _fit(build["branch"], 91), 12, "#d8e2ee"))
    objects.append(_text("build-date", [60, 495], f"build {build['build']} · {build['build_date']} {build['build_time']} · {build['artifact_count']} artifacts · {build['total_bytes']:,} bytes", 12, muted))
    if analysis:
        timing = "not recorded" if analysis["timing_met"] is None else "met" if analysis["timing_met"] else "NOT MET"
        wns = "unknown" if analysis["wns_ns"] is None else f"{analysis['wns_ns']:g} ns"
        detail = f"Ablation evidence: {analysis['cdo_section_count']} CDO sections · {analysis['cdo_command_count']:,} commands · timing {timing} · WNS {wns}"
        objects.append(_text("analysis-detail", [60, 527], _fit(detail, 104), 12, green if analysis["timing_met"] else "#fda4af"))
        objects.append(_text("analysis-device", [60, 551], _fit(f"{analysis['device']} · source {analysis['source_git_hash'][:12] or 'unrecorded'}", 104), 11, muted))
    else:
        objects.append(_text("analysis-detail", [60, 527], "Indexed build package; no correlated Ablation findings for this exact build.", 12, yellow))
        objects.append(_text("analysis-device", [60, 551], "Observation establishes artifact presence and metadata, not runtime behavior.", 11, muted))
    objects.append(_rectangle("memory-panel", [890, 408, 1360, 568], "#475569", "#0e1828"))
    objects.append(_text("memory-title", [910, 439], "ZOE WORKING MEMORY", 16, pink))
    for index, item in enumerate(report["working_memory"]):
        objects.append(_text(f"memory-{index}", [910, 469 + 24 * index], _fit(f"{item['id']} · {item['text']}", 59), 10, "#d8e2ee"))
    if not report["working_memory"]:
        objects.append(_text("memory-empty", [910, 474], "Observe a build to encode sourced state.", 11, muted))
    objects.append(_text("memory-count", [910, 559], f"{report['memory_events']} chain events · {report['evicted_memory']} evicted · append-only", 10, green))
    visible = observer.corpus.builds
    if len(visible) > 16:
        selected_index = next(index for index, item in enumerate(visible) if item["id"] == build["id"])
        start = max(0, min(selected_index - 7, len(visible) - 16))
        visible = visible[start:start + 16]
    center = [700, 725]
    for index, phase in enumerate((0, 60, 120)):
        objects.append(_orbit(f"zoe-orbit-{index}", center, [140 + index * 25, 48 + index * 10], phase + report["observation_count"] % 12 * 3, (cyan, pink, green)[index]))
    objects.append(_ellipse("zoe-core", center, [55, 36], pink, "#080d18", 2))
    objects.append(_text("zoe-core-label", [672, 734], "ZOE", 20, "#e2e8f0"))
    for index, item in enumerate(visible):
        angle = math.tau * index / len(visible) - math.pi / 2
        x, y = 700 + 570 * math.cos(angle), 725 + 125 * math.sin(angle)
        selected = item["id"] == build["id"]
        color = pink if selected else green if item["analysis"] else muted
        objects.append(_line(f"build-link-{index}", center, [x, y], color, 1.5 if selected else .5))
        objects.append(_ellipse(f"build-node-{index}", [x, y], [9 if selected else 5, 9 if selected else 5], color, color))
        label_x = min(1300, max(30, x - 38))
        label_y = min(870, max(590, y + (24 if math.sin(angle) >= 0 else -13)))
        objects.append(_text(f"build-label-{index}", [label_x, label_y], f"{item['card']}·{item['build']}", 10, color))
    objects.append(_text("constellation-caption", [40, 890], "Build constellation · selected observation in pink · analyzed builds in green · position is layout, not time or health", 11, muted))
    objects.append(_text("alive-state", [60, 610], f"OBSERVATION {report['observation_count']}", 14, pink))
    objects.append(_text("alive-detail", [60, 635], "responsive to replay + file refresh", 11, green))
    scene = _scene("zoe-felix-living-readout", 1400, 900, objects, "Zoe × FELIX · living readout evidence")
    return scene, report

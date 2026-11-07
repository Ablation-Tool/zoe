from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .field import _fit


IDENTITY = "Ablation = All = ZOE = ALL"


@dataclass(frozen=True)
class Component:
    identifier: str
    title: str
    checkout: str
    repository: str
    revision: str | None
    summary: str
    anchor: str
    python_paths: tuple[str, ...]
    module: str
    default_args: tuple[str, ...] = ()
    runtime_checkout: str | None = None


COMPONENTS = (
    Component("zoe", "Zoe native shell", "guiai-lab", "https://github.com/Ablation-Tool/zoe", None, "Cognitive Field, Bayesian memory, geometry, and unified hub", "guiai/gem/cognitive.py", ("",), "guiai.gem", ("zoe", "--module", "unified")),
    Component("cern-console", "Zoe CERN Workbench", "guiai-lab", "local-cern-gem-console", None, "CERN corpus, HELIOS virtual collider, Atelier input lab, and opt-in system drivers", "guiai/gem/zoe_workbench_cli.py", ("",), "guiai.gem.zoe_workbench_cli", ("start",)),
    Component("ablation", "Ablation core engine", "ablation", "https://github.com/Ablation-Tool/ablation", "b56f91e4c54cfd996bceea63a38d8136dc1e689f", "Complete AIARE framework, analyzers, parsers, modules, and core CLI", "ablation/analyzers/entropy_mapper.py", ("",), "ablation.cli", ("--help",)),
    Component("gem-lab", "Ablation GEM Lab", "ablation", "https://github.com/Ablation-Tool/ablation", "b56f91e4c54cfd996bceea63a38d8136dc1e689f", "Default native investigation GUI and shared Lab evidence protocol", "gem-lab/gem/gtk_app.py", ("gem-lab",), "gem", ("launch", "--no-agent")),
    Component("gem", "Canonical GEM", "graphics-environment-manager", "https://github.com/Ablation-Tool/graphics-environment-manager", "e63f6a7b84c2e8fffc0fcf01001986ae928f66b5", "Native workbench, mirrored brain, geometry, Spatial IR, and VDI", "gem/cli.py", ("",), "gem", ("os",)),
    Component("helen", "GEM HELEN", "gem-helen", "https://github.com/Ablation-Tool/gem-helen", "55fb1e494662e9b69e964ac2f9df41724cffeb0c", "Optimized geometry, rhythm, and forecast laboratory", "helen_gem/core.py", ("",), "helen_gem"),
    Component("brain", "BRAIN GEM", "brain-gem", "https://github.com/Ablation-Tool/brain-gem", "ed819c2824a55b019a532f4fa2cb440532030127", "Standalone Bayesian field notebook and chambered memory", "brain_gem/field.py", ("",), "brain_gem", ("field",)),
    Component("cerotto", "Cerotto GEM", "cerotto", "https://github.com/Ablation-Tool/cerotto", "5e2f0c06f1c9b6f6fe7d2489175ce89e7abb6ec4", "Guarded forensic cases, native C engine, timelines, and vault evidence", "cerotto_gem/cli.py", ("",), "cerotto_gem"),
    Component("research", "Research GEM", "next-token-predictability", "https://github.com/Ablation-Tool/next-token-predictability", "83b89a385aa4e67fb0c1b60ba30a21efcc0e50f9", "Accessible-volume research, evidence packs, and mirrored workbench", "evidence/master-gem/conformance.json", ("",), "gem", ("os",), "graphics-environment-manager"),
)


def _python():
    if os.environ.get("ZOE_PYTHON"):
        return os.environ["ZOE_PYTHON"]
    system = Path("/usr/bin/python3")
    return str(system) if system.is_file() else sys.executable


class ComponentRegistry:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("ZOE_ROOT") or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.components = {component.identifier: component for component in COMPONENTS}

    def component(self, identifier):
        if identifier not in self.components:
            raise ValueError(f"unknown unified component: {identifier}")
        return self.components[identifier]

    def source(self, identifier):
        component = self.component(identifier)
        checkout = component.checkout
        bundled = self.root / "components" / checkout
        external = self.root.parent / checkout
        if component.identifier in {"zoe", "cern-console"}:
            path = self.root / component.checkout
            mode = "zoe"
        elif (bundled / "README.md").is_file():
            path = bundled
            mode = "bundled"
        elif (external / "README.md").is_file():
            path = external
            mode = "external"
        else:
            path = bundled
            mode = "missing"
        return {
            "path": path,
            "mode": mode,
            "available": mode != "missing" and (path / component.anchor).is_file(),
        }

    def environment(self, identifier):
        component = self.component(identifier)
        source = self.source("gem" if component.runtime_checkout else identifier)
        if not source["available"]:
            raise ValueError(f"component source is unavailable: {identifier} ({source['path']})")
        paths = [source["path"] / relative for relative in component.python_paths]
        dependencies = os.environ.get("ZOE_PYTHON_DEPENDENCIES", "")
        paths.extend(Path(item) for item in dependencies.split(os.pathsep) if item)
        distribution = Path("/usr/lib/python3/dist-packages")
        if distribution.is_dir():
            paths.append(distribution)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in paths)
        environment["ZOE_ROOT"] = str(self.root)
        environment["ZOE_COMPONENT_ID"] = identifier
        environment["ZOE_UNIFIED"] = "1"
        research = self.source("research")["path"]
        if research.is_dir():
            environment["MASTER_GEM_RESEARCH_ROOT"] = str(research)
        if identifier == "cerotto":
            environment.setdefault("CEROTTO_BIN", str(source["path"] / "build" / "cerotto"))
        return environment

    def command(self, identifier, arguments=None):
        component = self.component(identifier)
        if arguments is not None and (len(arguments) > 128 or any(not isinstance(item, str) or not item or len(item) > 4096 for item in arguments)):
            raise ValueError("component arguments must contain at most 128 nonempty strings of at most 4096 characters")
        arguments = list(component.default_args if arguments is None else arguments)
        if identifier == "cerotto" and not arguments:
            raise ValueError("cerotto requires --db, --case, and --conversation; pass them after `--` or use the native case picker")
        source = self.source("gem" if component.runtime_checkout else identifier)
        return [_python(), "-m", component.module, *arguments], source["path"]

    def launch(self, identifier, arguments=None, detach=True):
        command, cwd = self.command(identifier, arguments)
        environment = self.environment(identifier)
        if detach:
            return subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True)
        return subprocess.run(command, cwd=cwd, env=environment, check=False)

    def manifest(self):
        rows = []
        for component in COMPONENTS:
            source = self.source(component.identifier)
            row = asdict(component)
            row["source"] = {"path": str(source["path"]), "mode": source["mode"], "source_present": source["available"], "runtime_verified": False}
            rows.append(row)
        return {
            "schema_version": 1,
            "identity": IDENTITY,
            "product": "Zoe unified Ablation and GEM distribution",
            "root": str(self.root),
            "entrypoint_count": len(rows),
            "upstream_repository_count": 6,
            "components": rows,
            "execution": "explicit component launch only; no process is started by inspecting this manifest",
            "boundaries": "One source distribution and identity; separate processes, dependencies, evidence, and authorization remain distinct.",
        }

    def write_manifest(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("unified component manifest must use a .json path")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(self.manifest(), stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            stream.write("\n")
        return path


def _rectangle(identifier, bounds, stroke, fill, width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def _orbit(identifier, center, radii, angle, color):
    rotation = math.radians(angle)
    points = []
    for index in range(96):
        theta = math.tau * index / 96
        x = radii[0] * math.cos(theta)
        y = radii[1] * math.sin(theta)
        points.append([center[0] + x * math.cos(rotation) - y * math.sin(rotation), center[1] + x * math.sin(rotation) + y * math.cos(rotation)])
    return {"id": identifier, "type": "polygon", "points": points, "stroke": color, "fill": "none", "width": 1.2}


def unified_scene(registry=None):
    from .atlas import _ellipse, _line, _scene, _text

    registry = registry or ComponentRegistry()
    manifest = registry.manifest()
    cyan, yellow, pink, green, muted = "#67e8f9", "#fde68a", "#f0abfc", "#86efac", "#9fb1c8"
    colors = [cyan, yellow, pink, green, "#fda4af", "#93c5fd", "#fdba74", "#c4b5fd"]
    objects = [_rectangle("background", [0, 0, 1400, 900], "#080d18", "#080d18")]
    objects.extend([
        _text("title", [40, 51], "ABLATION = ALL = ZOE = ALL", 29, cyan),
        _text("subtitle", [40, 83], "full framework + every GEM · one source distribution", 17, "#e2e8f0"),
        _text("scope", [40, 109], "Shared identity and source. Separate processes, permissions, and evidence.", 12, muted),
        _text("entrypoints", [45, 178], str(len(COMPONENTS)), 41, cyan),
        _text("entrypoint-label", [113, 175], "registered entrypoints", 15, muted),
        _text("repositories", [45, 222], "6", 32, yellow),
        _text("repository-label", [101, 220], "upstream repositories + Zoe", 14, muted),
        _text("engine", [355, 178], "FULL", 28, pink),
        _text("engine-label", [451, 176], "Ablation core and framework", 14, muted),
        _text("checkout", [355, 218], "ONE", 24, green),
        _text("checkout-label", [427, 216], "checkout · identity · manifest", 14, muted),
    ])
    for index, color in enumerate((cyan, pink, yellow, green, "#93c5fd", "#fdba74", "#c4b5fd")):
        objects.append(_orbit(f"identity-orbit-{index}", [1150, 190], [176, 52], index * 180 / 7, color))
    objects.append(_ellipse("identity-center", [1150, 190], [43, 30], cyan, "#080d18", 2))
    objects.append(_text("identity-center-label", [1119, 197], "ZOE", 20, "#e2e8f0"))
    objects.append(_text("orbital-caption", [1025, 276], "orbital identity sketch · visual metaphor", 11, muted))
    for index, component in enumerate(manifest["components"]):
        x = 40 + (index % 4) * 340
        y = 294 + (index // 4) * 202
        color = colors[index % len(colors)]
        source = component["source"]
        objects.append(_rectangle(f"component-{component['identifier']}", [x, y, x + 300, y + 181], color, "#101b2b", 2))
        objects.append(_ellipse(f"component-icon-{index}", [x + 29, y + 31], [8, 8], color, color))
        objects.append(_text(f"component-title-{index}", [x + 48, y + 37], component["title"], 18, color))
        objects.append(_text(f"component-summary-{index}", [x + 18, y + 72], _fit(component["summary"], 43), 11, "#d8e2ee"))
        objects.append(_text(f"component-summary-2-{index}", [x + 18, y + 91], _fit(component["summary"][43:], 43), 11, "#d8e2ee"))
        objects.append(_text(f"component-command-{index}", [x + 18, y + 125], f"zoe launch {component['identifier']}", 12, muted))
        status = "source present" if source["source_present"] else "source unavailable"
        objects.append(_text(f"component-status-{index}", [x + 18, y + 151], f"{source['mode']} · {status}", 11, green if source["source_present"] else "#fdba74"))
        objects.append(_text(f"component-revision-{index}", [x + 18, y + 170], f"upstream {component['revision'][:12] if component['revision'] else 'Zoe baseline'}", 9, "#64748b"))
    memory_y = 725 if len(COMPONENTS) <= 8 else 294 + ((len(COMPONENTS) - 1) // 4) * 202 + 181 + 32
    scene_height = 900 if len(COMPONENTS) <= 8 else memory_y + 138
    objects.append(_rectangle("unified-memory", [40, memory_y, 1360, memory_y + 138], "#475569", "#0e1828"))
    for index, symbol in enumerate(("A", "Z", "O", "E", "*")):
        x = 62 + index * 50
        objects.append(_rectangle(f"symbol-cell-{index}", [x, memory_y + 26, x + 48, memory_y + 72], muted, "none"))
        objects.append(_text(f"symbol-{index}", [x + 17, memory_y + 56], symbol, 20, colors[index]))
    objects.append(_text("symbol-caption", [62, memory_y + 98], "source / engine / evidence", 11, muted))
    objects.append(_text("symbol-note", [62, memory_y + 120], "symbol-grid references · explicit text remains authoritative", 9, "#64748b"))
    objects.append(_text("memory-title", [390, memory_y + 40], "ONE DISTRIBUTION · INSPECTABLE COMPONENT MEMORY", 14, yellow))
    objects.append(_text("memory-scope", [390, memory_y + 69], "No implicit agent launch · no evidence equivalence · no execution authorization", 12, "#fda4af"))
    objects.append(_text("memory-detail", [390, memory_y + 95], "Core engine + native GUIs + research evidence + original licenses and upstream revisions", 11, muted))
    objects.append(_text("memory-boundary", [390, memory_y + 121], "The scene launches nothing. Buttons and CLI commands require an explicit user request.", 11, green))
    scene = _scene("zoe-unified-ablation", 1400, scene_height, objects, IDENTITY)
    report = deepcopy(manifest)
    present = sum(row["source"]["source_present"] for row in manifest["components"])
    report.update({
        "summary": f"{present}/{len(COMPONENTS)} entrypoint sources present · full source distribution · no process launched by this scene",
        "scene_only": True,
        "executed": False,
        "recommended_module": "unified",
    })
    return scene, report

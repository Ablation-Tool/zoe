from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .atlas import _ellipse, _scene, _text
from .field import _fit


IDENTITY = "Zoe is allgems"


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
    inspect_only: bool = False
    use_caller_cwd: bool = False
    native_executable: str | None = None


COMPONENTS = (
    Component("zoe", "Zoe native shell", "guiai-lab", "https://github.com/Ablation-Tool/zoe", None, "Cognitive Field, Bayesian memory, geometry, and unified hub", "guiai/gem/cognitive.py", ("",), "guiai.gem", ("zoe", "--module", "unified")),
    Component("cern-console", "Zoe CERN Workbench", "guiai-lab", "local-cern-gem-console", None, "CERN corpus, HELIOS virtual collider, Atelier input lab, and opt-in system drivers", "guiai/gem/zoe_workbench_cli.py", ("",), "guiai.gem.zoe_workbench_cli", ("start",)),
    Component("ablation", "Ablation core engine", "ablation", "https://github.com/Ablation-Tool/ablation", "fa8377ea5fa009967a3bf3b837c342347678409b", "Complete AIARE framework, analyzers, parsers, modules, and core CLI", "ablation/analyzers/entropy_mapper.py", ("",), "ablation.cli", ("--help",), use_caller_cwd=True),
    Component("gem-lab", "Ablation GEM Lab", "ablation", "https://github.com/Ablation-Tool/ablation", "fa8377ea5fa009967a3bf3b837c342347678409b", "Default native investigation GUI and shared Lab evidence protocol", "gem-lab/gem/gtk_app.py", ("gem-lab",), "gem", ("launch", "--no-agent")),
    Component("gem", "Canonical GEM", "graphics-environment-manager", "https://github.com/Ablation-Tool/graphics-environment-manager", "0ab35bffa0453689f00b321a6a7e972d14bc8ba7", "Native workbench, mirrored brain, geometry, Spatial IR, and VDI", "gem/cli.py", ("",), "gem", ("os",)),
    Component("helen", "GEM HELEN", "gem-helen", "https://github.com/Ablation-Tool/gem-helen", "273c4eeb6fd6044f1ab9068561ddc33290357eed", "Optimized geometry, rhythm, and forecast laboratory", "helen_gem/core.py", ("",), "helen_gem"),
    Component("brain", "BRAIN GEM", "brain-gem", "https://github.com/Ablation-Tool/brain-gem", "7420a8f0d8d2c370a72b76d93defcc7fb585b913", "Standalone Bayesian field notebook and chambered memory", "brain_gem/field.py", ("",), "brain_gem", ("field",)),
    Component("hpux-tools", "HP-UX Tools", "hpux-tools", "https://github.com/Ablation-Tool/zoe", None, "Zoe-managed HP-UX SOM debugging and PA-RISC emulation", "hpux_tools/cli.py", ("",), "hpux_tools.cli", ("doctor",), use_caller_cwd=True),
    Component("life", "Zoe Life", "guiai-lab", "https://github.com/Ablation-Tool/zoe", None, "Conway's Game of Life, cellular automata, and reproducible scenes", "guiai/gem/life.py", ("",), "guiai.gem.life_view", use_caller_cwd=True),
    Component("cerotto", "Cerotto GEM", "cerotto", "https://github.com/Ablation-Tool/cerotto", "b73d399b638b4de8a0a9829b17c95203c5deaabd", "Guarded forensic cases, native C engine, timelines, and vault evidence", "cerotto_gem/cli.py", ("",), "cerotto_gem"),
    Component("research", "Research GEM", "next-token-predictability", "https://github.com/Ablation-Tool/next-token-predictability", "79575d94325a43b5dbbef17d38bc1cb1d56d9321", "Accessible-volume research, evidence packs, and mirrored workbench", "evidence/master-gem/conformance.json", ("",), "gem", ("os",), "graphics-environment-manager"),
    Component("autonomy", "Zoe Autonomy", "Zoe-Autonomy", "https://github.com/Ablation-Tool/Zoe-Autonomy", "0b6b8da9986c31d356fbe8aeb7c9f646ede03429", "Full self-governing decisions, measured self-reflection, soroban working memory, shared visual perception, and evidence", "src/zoe_autonomy/experiment.py", ("src", "../../guiai-lab"), "zoe_autonomy.cli", ("run",)),
    Component("kevlar", "Kevlar MCP firewall", "kevlar", "https://github.com/Ablation-Tool/kevlar", "8ac3e0181e98572d6c41f964385393aa441a5f2a", "MCP proxy firewall, content disarm, policy enforcement, and audit evidence", "kevlar.py", ("",), "kevlar", ("--help",)),
    Component("pdf", "PDF Signature Toolkit", "pdf-signature-toolkit", "https://github.com/Ablation-Tool/pdf-signature-toolkit", "1198165962958c5132130f3854626ff39c333941", "Reproducible source integrity records and detached PDF signatures", "pdf_signature_toolkit/verify.py", ("",), "pdf_signature_toolkit.verify", ("--help",)),
    Component("neurogarden", "Neurogarden Agent Logging", "agent-logging-system", "https://github.com/Ablation-Tool/zoe", None, "OT-inspired oversight, Trinity verification, cited learning, and teaching tools", "agent_logging_system/adapters/neurogarden_adapter.py", ("",), "", (), None, True),
    Component("chalkboard", "Chalkboard library", "Chalkboard", "https://github.com/Ablation-Tool/Chalkboard", "63646eb15737d822316073ba1f2114c608571c72", "Reusable ideas, templates, and prompts for knowledge engineering", "README.md", ("",), "", (), None, True),
    Component("pala", "PALA Recovery", "PALA", "https://github.com/Ablation-Tool/zoe", "197e91b88b9c7bad185a21635a68aa6659dcec3b", "Read-only file carving, deleted-file recovery, metadata, checkpoints, and private non-overwriting output", "src/main.rs", (), "", ("--list",), native_executable="pala"),
)


def _path_on_noexec_mount(path: Path) -> bool:
    """Detect Linux ST_NOEXEC mount flag so native tools (PALA/Cerotto) stage safely in /tmp."""
    try:
        st = os.statvfs(str(path if path.exists() else path.parent))
        noexec_flag = getattr(os, "ST_NOEXEC", 0x08)
        return bool(st.f_flag & noexec_flag)
    except (OSError, AttributeError):
        return False


def _stage_executable_if_noexec(binary: Path, name: str) -> Path:
    """If `binary` is not directly executable (e.g. NTFS/FUSE or noexec mount), mirror into 0700 exec cache."""
    if not binary.is_file():
        return binary
    if os.access(str(binary), os.X_OK) and not _path_on_noexec_mount(binary):
        return binary
    import tempfile
    cache_dir = Path(tempfile.gettempdir()) / f"zoe-exec-cache-{os.getuid()}"
    cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    staged = cache_dir / name
    if not staged.is_file() or staged.stat().st_size != binary.stat().st_size or not os.access(str(staged), os.X_OK):
        shutil.copy2(binary, staged)
        staged.chmod(0o700)
    return staged


def _python():
    return os.environ.get("ZOE_PYTHON") or sys.executable


def _checkout_provenance(path):
    result = {"checkout_root": None, "checkout_revision": None, "checkout_dirty": None}
    try:
        root_result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if root_result.returncode:
            return result
        root = Path(root_result.stdout.strip())
        revision_result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if revision_result.returncode:
            return result
        relative = path.relative_to(root).as_posix() or "."
        status_result = subprocess.run(
            ["git", "-C", str(root), "status", "--short", "--", relative],
            capture_output=True, text=True, check=False, timeout=10,
        )
        result.update({
            "checkout_root": str(root),
            "checkout_revision": revision_result.stdout.strip(),
            "checkout_dirty": bool(status_result.stdout.strip()) if status_result.returncode == 0 else None,
        })
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return result


class ComponentRegistry:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("ZOE_ROOT") or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.components = {component.identifier: component for component in COMPONENTS}
        from .knowledge import KnowledgeField
        self.knowledge = KnowledgeField.source_demo(self.manifest())

    def component(self, identifier):
        if identifier not in self.components:
            raise ValueError(f"unknown unified component: {identifier}")
        return self.components[identifier]

    def source(self, identifier):
        component = self.component(identifier)
        checkout = component.checkout
        bundled = self.root / "components" / checkout
        external = self.root.parent / checkout
        host_variables = {
            "ablation": "ZOE_ABLATION_ROOT",
            "gem-lab": "ZOE_ABLATION_ROOT",
            "cerotto": "ZOE_CEROTTO_ROOT",
            "chalkboard": "ZOE_CHALKBOARD_ROOT",
        }
        host_variable = host_variables.get(identifier)
        host = Path(os.environ.get(host_variable, self.root.parent)).expanduser().resolve() if host_variable else None
        if component.identifier in {"zoe", "cern-console", "life"}:
            path = self.root / component.checkout
            if not (path / component.anchor).is_file():
                package_root = Path(__file__).resolve().parents[2]
                if (package_root / component.anchor).is_file():
                    path = package_root
            mode = "zoe"
        elif (bundled / "README.md").is_file():
            path = bundled
            mode = "bundled"
        elif host is not None and (host / component.anchor).is_file():
            path = host
            mode = "host"
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
            cerotto_bin = _stage_executable_if_noexec(source["path"] / "build" / "cerotto", "cerotto")
            environment.setdefault("CEROTTO_BIN", str(cerotto_bin))
        if identifier == "pala" and _path_on_noexec_mount(source["path"]):
            environment.setdefault("CARGO_TARGET_DIR", "/tmp/pala_target")
        return environment

    def command(self, identifier, arguments=None):
        component = self.component(identifier)
        if arguments is not None and (len(arguments) > 128 or any(not isinstance(item, str) or not item or len(item) > 4096 for item in arguments)):
            raise ValueError("component arguments must contain at most 128 nonempty strings of at most 4096 characters")
        arguments = list(component.default_args if arguments is None else arguments)
        if component.inspect_only:
            raise ValueError(f"{identifier} is a content library; use `zoe show {identifier}` instead of launching a process")
        if identifier == "cerotto" and not arguments:
            raise ValueError("cerotto requires --db, --case, and --conversation; pass them after `--` or use the native case picker")
        source = self.source("gem" if component.runtime_checkout else identifier)
        if component.native_executable:
            target = Path(os.environ.get("CARGO_TARGET_DIR", source["path"] / "target")).expanduser()
            if not target.is_absolute():
                target = source["path"] / target
            executable = component.native_executable + (".exe" if os.name == "nt" else "")
            binary = target.resolve() / "release" / executable
            if binary.is_file() and os.access(binary, os.X_OK):
                return [str(binary), *arguments], source["path"]
            cargo = shutil.which("cargo")
            if cargo is None:
                raise ValueError(f"PALA requires Rust; build it with `cargo build --manifest-path {source['path'] / 'Cargo.toml'} --release --locked`")
            return [cargo, "run", "--release", "--locked", "--manifest-path", str(source["path"] / "Cargo.toml"), "--", *arguments], source["path"]
        if component.use_caller_cwd:
            cwd = Path.cwd()
        else:
            cwd = source["path"] / component.python_paths[0] if component.python_paths and component.python_paths[0] else source["path"]
        return [_python(), "-m", component.module, *arguments], cwd

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
            row["source"] = {
                "path": str(source["path"]),
                "mode": source["mode"],
                "source_present": source["available"],
                "runtime_verified": False,
                **_checkout_provenance(source["path"]),
            }
            rows.append(row)
        return {
            "schema_version": 1,
            "identity": IDENTITY,
            "product": "Zoe allgems knowledge-engineering distribution",
            "root": str(self.root),
            "entrypoint_count": len(rows),
            "repository_count": 1,
            "source_project_count": 13,
            "imported_repository_count": 13,
            "components": rows,
            "knowledge_engineering": {
                "trust_context": "source, repository, revision, evidence scope, and authorization boundary",
                "stability_context": "component-specific processes, version locks, replayable memory, and separately tested behavior; not an uptime guarantee",
            },
            "execution": "explicit component launch only; no process is started by inspecting this manifest",
            "boundaries": "One source distribution and identity; separate processes, dependencies, evidence, and authorization remain distinct.",
        }

    def observe(self, identifier, observation, **context):
        component = self.component(identifier)
        return self.knowledge.observe(
            identifier, observation, repository=component.repository,
            revision=component.revision, **context,
        )

    def record_source(self, identifier):
        row = next(item for item in self.manifest()["components"] if item["identifier"] == identifier)
        return self.knowledge.observe_source(row)

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


def _woven_diamond(identifier, center, radius, color):
    cx, cy = center
    objects = [{
        "id": f"{identifier}-outer", "type": "polygon",
        "points": [[cx, cy - radius], [cx + radius, cy], [cx, cy + radius], [cx - radius, cy], [cx, cy - radius]],
        "stroke": color, "fill": "none", "width": 2,
    }]
    for index, offset in enumerate(range(-90, 100, 15)):
        span = radius - abs(offset)
        objects.append({
            "id": f"{identifier}-horizontal-{index}", "type": "polyline",
            "points": [[cx - span, cy + offset], [cx + span, cy + offset]],
            "stroke": color, "fill": "none", "width": 1,
        })
        objects.append({
            "id": f"{identifier}-vertical-{index}", "type": "polyline",
            "points": [[cx + offset, cy - span], [cx + offset, cy + span]],
            "stroke": color, "fill": "none", "width": 1,
        })
    objects.append({
        "id": f"{identifier}-center", "type": "polygon",
        "points": [[cx, cy - 42], [cx + 42, cy], [cx, cy + 42], [cx - 42, cy], [cx, cy - 42]],
        "stroke": color, "fill": "#080d18", "width": 2,
    })
    return objects


def _centered_text(identifier, x, y, text, size, color):
    return _text(identifier, [x - len(text) * size * 0.29, y], text, size, color)


def _constellation_node(identifier, label, x, y, direction, color, level):
    objects = [
        _ellipse(f"{identifier}-halo", [x, y], [14, 14], color, "#080d18", 1),
        _ellipse(f"{identifier}-core", [x, y], [7, 7], color, color),
    ]
    width = len(label) * 8.4
    if direction == "top":
        position = [x - width / 2, y - 31]
    elif direction == "bottom":
        position = [x - width / 2, y + 27]
    else:
        stagger = (level - 1.5) * 45
        label_y = y - stagger if direction == "right" else y + stagger
        objects.append({
            "id": f"{identifier}-leader", "type": "polyline",
            "points": [[x, y], [x + 24 if direction == "right" else x - 24, label_y]],
            "stroke": color, "fill": "none", "width": 0.8,
        })
        position = [x + 24, label_y + 6] if direction == "right" else [x - 24 - width, label_y + 6]
    objects.append(_text(f"{identifier}-label", position, label, 16, "#e2e8f0"))
    return objects


def unified_scene(registry=None, knowledge=None):
    registry = registry or ComponentRegistry()
    knowledge = knowledge or registry.knowledge
    manifest = registry.manifest()
    knowledge_state = knowledge.knowledge_state()
    present = sum(row["source"]["source_present"] for row in manifest["components"])
    cyan, yellow, pink, green, muted = "#67e8f9", "#fde68a", "#f0abfc", "#86efac", "#9fb1c8"
    objects = [_rectangle("background", [0, 0, 1920, 1200], "#080d18", "#080d18")]
    for index in range(96):
        x = 41 + (index * 197) % 1840
        y = 29 + (index * 109) % 1120
        objects.append(_ellipse(f"star-{index}", [x, y], [1.4, 1.4], "#1e3a5f", "#1e3a5f"))
    objects.extend([
        _centered_text("title", 960, 76, "Zoe · ALLGEMS", 44, "#e2e8f0"),
        _centered_text("subtitle", 960, 115, "A L L G E M S  /  THE RESEARCH UNIVERSE", 15, cyan),
        _centered_text("scope", 960, 149, "17 ENGINES · 13 IMPORTED HISTORIES · 1 REPOSITORY · 42 VISUAL MAPS", 13, muted),
        {"id": "header-rule", "type": "polyline", "points": [[650, 176], [1270, 176]], "stroke": "#1e3a5f", "fill": "none", "width": 1},
    ])
    center_x, center_y = 960, 630
    for radius in (150, 230, 310, 390, 450):
        objects.append(_ellipse(f"orbit-{radius}", [center_x, center_y], [radius, radius], "#162a44", "none", 1))
    ring_specs = [
        (150, cyan, ("PALA Recovery", "Canonical GEM", "Zoe Autonomy", "Research GEM")),
        (230, pink, ("Ablation core engine", "Ablation GEM Lab", "Cerotto GEM", "HP-UX Tools")),
        (310, yellow, ("CERN Workbench", "Neurogarden", "Chalkboard", "BRAIN GEM")),
        (390, green, ("GEM HELEN", "Zoe Life", "PDF Signature Toolkit", "Kevlar MCP firewall")),
    ]
    for ring_index, (radius, color, labels) in enumerate(ring_specs):
        objects.append({
            "id": f"diamond-ring-{ring_index}", "type": "polygon",
            "points": [[center_x, center_y - radius], [center_x + radius, center_y], [center_x, center_y + radius], [center_x - radius, center_y], [center_x, center_y - radius]],
            "stroke": color, "fill": "none", "width": 1.2,
        })
        for direction, label in zip(("top", "right", "bottom", "left"), labels):
            node_x = center_x + (radius if direction == "right" else -radius if direction == "left" else 0)
            node_y = center_y + (radius if direction == "bottom" else -radius if direction == "top" else 0)
            objects.extend(_constellation_node(f"engine-{label.lower().replace(' ', '-')}", label, node_x, node_y, direction, color, ring_index))
    objects.extend(_woven_diamond("identity-woven", [center_x, center_y], 110, "#f87171"))
    objects.append(_centered_text("identity-center-label", center_x, center_y + 9, "ZOE", 27, "#e2e8f0"))
    objects.extend([
        _centered_text("loop", 960, 1098, "SENSE  >  MODEL  >  IMAGINE  >  DOUBT  >  CHOOSE  >  ACT  >  LEARN", 15, "#e2e8f0"),
        _centered_text("evidence", 960, 1134, f"{present}/{len(COMPONENTS)} SOURCE PRESENT · {knowledge_state['observation_count']} OBSERVATIONS · {knowledge_state['link_count']} LINKS · REPLAYABLE EVIDENCE", 11, green),
        _centered_text("memory", 960, 1164, "ONE REPOSITORY · ONE KNOWLEDGE FIELD · HUMAN CONTROL", 11, muted),
    ])
    scene = _scene("zoe-allgems", 1920, 1200, objects, IDENTITY)
    report = deepcopy(manifest)
    present = sum(row["source"]["source_present"] for row in manifest["components"])
    report.update({
        "summary": f"{present}/{len(COMPONENTS)} entrypoint sources present · {knowledge_state['observation_count']} observations · {knowledge_state['link_count']} context links · no process launched by this scene",
        "memory": knowledge.document(),
        "knowledge": knowledge_state,
        "scene_only": True,
        "executed": False,
        "recommended_module": "unified",
    })
    return scene, report

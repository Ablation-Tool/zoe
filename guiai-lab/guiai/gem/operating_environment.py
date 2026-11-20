from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .atlas import ATLAS_MODULES, default_document
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .unified import COMPONENTS, ComponentRegistry
from .vdi import write_metafile


CONTRACT = "zoe-gem-operating-environment/v1"
COMPONENT_MODULES = {
    "zoe": "unified",
    "cern-console": "cern",
    "ablation": "unified",
    "gem-lab": "unified",
    "gem": "volume",
    "helen": "onset",
    "brain": "brain",
    "hpux-tools": "patchbay",
    "life": "life",
    "cerotto": "evidence",
    "research": "research",
    "autonomy": "autonomy",
    "kevlar": "protocol",
    "pdf": "evidence",
    "neurogarden": "dorothy",
    "chalkboard": "evidence",
    "pala": "evidence",
}
EXTENDED_LAYERS = {
    "chiasm": ("zoe", "Zoe · The Causal Chiasm & Filtration Tomography"),
    "causal-chiasm": ("zoe", "Zoe · The Causal Chiasm & Filtration Tomography"),
    "dorothy-continuum": ("neurogarden", "Dorothy · Continuum & Qualia Atlas"),
    "dorothy-qualia": ("neurogarden", "Dorothy · CCFv3 3D brain atlas (Qualia theme)"),
    "genesis": ("autonomy", "Zoe · Autopoietic AGI Genesis & 10-Domain Discovery Symphony"),
    "agi-symphony": ("autonomy", "Zoe · Autopoietic AGI Genesis & 10-Domain Discovery Symphony"),
    "spectral": ("research", "Zoe · The Kloster Spectral Filtration Generating Theorem"),
    "kloster-theorem": ("research", "Zoe · The Kloster Spectral Filtration Generating Theorem"),
    "mars": ("autonomy", "Zoe · Stage 4 Mars Self-Tuning Spectral Metacognition"),
    "ares": ("autonomy", "Zoe · Stage 4 Mars Self-Tuning Spectral Metacognition"),
    "playroom": ("autonomy", "Zoe · Stage 5 Open-Ended Creative Playroom (MAP-Elites + Kloster Curiosity)"),
    "creative-playroom": ("autonomy", "Zoe · Stage 5 Open-Ended Creative Playroom (MAP-Elites + Kloster Curiosity)"),
    "symphony": ("autonomy", "Zoe · Stage 5C Playroom Symphony (Evolved Pentatonic Synth Music)"),
    "jam": ("autonomy", "Zoe · Stage 5C Playroom Symphony (Evolved Pentatonic Synth Music)"),
    "l3-research": ("autonomy", "Zoe · L3 Research Collaborator (9-Stage Pre-Registered Cycles)"),
    "research-lab": ("autonomy", "Zoe · L3 Research Collaborator (9-Stage Pre-Registered Cycles)"),
    "l4-evolution": ("autonomy", "Zoe · L4 Generalized Self-Improvement (Uniform AST + Zero-Shot Transfer)"),
    "self-improvement": ("autonomy", "Zoe · L4 Generalized Self-Improvement (Uniform AST + Zero-Shot Transfer)"),
}


class GemOperatingEnvironment:
    def __init__(self, zoe_root=None, registry=None):
        self.root = Path(zoe_root or os.environ.get("ZOE_ROOT") or Path(__file__).resolve().parents[3]).expanduser().resolve()
        self.registry = registry or ComponentRegistry(self.root)
        self.current = None

    def resolve(self, identifier):
        if identifier in ATLAS_MODULES:
            return "zoe", identifier
        if identifier in EXTENDED_LAYERS:
            return EXTENDED_LAYERS[identifier][0], identifier
        if identifier in COMPONENT_MODULES:
            return identifier, COMPONENT_MODULES[identifier]
        raise ValueError(f"unknown GEM component or layer: {identifier}")

    def catalog(self):
        components = []
        for component in COMPONENTS:
            source = self.registry.source(component.identifier)
            components.append({
                "id": component.identifier,
                "title": component.title,
                "layer": COMPONENT_MODULES[component.identifier],
                "source": str(source["path"]),
                "source_present": source["available"],
            })
        return {
            "contract": CONTRACT,
            "components": components,
            "layers": [{"id": identifier, "title": title} for identifier, title in ATLAS_MODULES.items()],
            "component_count": len(components),
            "layer_count": len(ATLAS_MODULES),
        }

    def open(self, identifier):
        component_id, layer = self.resolve(identifier)
        research_root = self.root / "components" / "next-token-predictability"
        if layer == "unified":
            from .unified import unified_scene
            scene, report = unified_scene(self.registry, self.registry.knowledge)
        else:
            scene, report = default_document(
                layer,
                research_root=research_root if research_root.is_dir() else None,
            )
        check = verify(scene)
        if not check.passed:
            raise ValueError(f"GEM layer {layer} failed Spatial IR verification: {check.text()}")
        component = self.registry.component(component_id)
        observation = self.registry.observe(
            component_id,
            {
                "layer": layer,
                "scene_id": scene.document["id"],
                "scene_sha256": scene.digest(),
                "source_spatial_ir_verified": True,
                "process_launched": False,
                "external_actions": 0,
            },
            scope="A declared default GEM layer was rendered and source-verified in the shared operating environment; no component process or external action was executed.",
            source="Zoe shared GEM operating environment",
        )
        self.current = {
            "identifier": identifier,
            "component": component_id,
            "layer": layer,
            "scene": scene,
            "report": report,
            "observation_id": observation["id"],
        }
        return self.public_current()

    def public_current(self):
        if self.current is None:
            return None
        current = self.current
        report = current["report"]
        layer_title = ATLAS_MODULES.get(current["layer"]) or EXTENDED_LAYERS.get(current["layer"], ("", current["layer"]))[1]
        return {
            "identifier": current["identifier"],
            "component": current["component"],
            "layer": current["layer"],
            "title": layer_title,
            "scene_id": current["scene"].document["id"],
            "scene_sha256": current["scene"].digest(),
            "source_spatial_ir_verified": True,
            "observation_id": current["observation_id"],
            "summary": report.get("summary") if isinstance(report, dict) and isinstance(report.get("summary"), str) else layer_title,
            "process_launched": False,
            "external_actions": 0,
        }

    def export(self, identifier, destination):
        current = self.open(identifier)
        scene = self.current["scene"]
        path = Path(destination).expanduser().resolve()
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        kind = path.suffix.lower()
        if kind == ".gem":
            check = verify_vdi(scene)
            if not check.passed:
                raise ValueError(check.text())
            write_metafile(scene, path)
        elif kind == ".svg":
            write_svg(scene, path)
        elif kind == ".png":
            write_png(scene, path)
        elif kind == ".html":
            from .dorothy import write_interactive_html
            write_interactive_html(scene, self.current["report"], path)
        elif kind == ".json":
            with path.open("x", encoding="utf-8") as stream:
                stream.write(scene.json())
        else:
            raise ValueError("GEM export must use .json, .svg, .png, .html, or .gem")
        return {
            **current,
            "output": str(path),
            "bytes": path.stat().st_size,
            "no_overwrite": True,
            "vdi_verified": kind == ".gem",
        }

    def snapshot(self, destination):
        path = self.registry.knowledge.save(destination)
        return {
            "contract": CONTRACT,
            "output": str(path),
            "bytes": path.stat().st_size,
            "current": self.public_current(),
            "knowledge": self.registry.knowledge.knowledge_state(),
            "automatic_transcript": False,
        }

    def execute(self, arguments):
        arguments = list(arguments)
        if len(arguments) > 8 or any(not isinstance(value, str) or not value or len(value) > 4096 for value in arguments):
            raise ValueError("GEM operation arguments must contain at most eight nonempty bounded strings")
        operation = arguments[0] if arguments else "status"
        if operation == "status":
            if len(arguments) != 1:
                raise ValueError("status accepts no arguments")
            return {
                "contract": CONTRACT,
                "current": self.public_current(),
                "component_count": len(COMPONENTS),
                "layer_count": len(ATLAS_MODULES),
                "knowledge_observations": len(self.registry.knowledge.knowledge_observations),
                "automatic_transcript": False,
                "external_actions": 0,
            }
        if operation == "list":
            if len(arguments) != 1:
                raise ValueError("list accepts no arguments")
            return self.catalog()
        if operation == "open" and len(arguments) == 2:
            return self.open(arguments[1])
        if operation == "export" and len(arguments) == 3:
            return self.export(arguments[1], arguments[2])
        if operation == "snapshot" and len(arguments) == 2:
            return self.snapshot(arguments[1])
        raise ValueError("use gem status, gem list, gem open ID, gem export ID PATH, or gem snapshot PATH")


def format_result(result):
    if "components" in result and "layers" in result:
        components = ", ".join(row["id"] for row in result["components"])
        return f"GEM operating environment: {result['component_count']} components · {result['layer_count']} navigable layers\nComponents: {components}"
    if "current" in result and "component_count" in result:
        current = result["current"] or {"layer": "none", "scene_sha256": "none"}
        return (
            f"GEM operating environment: {result['component_count']} components · {result['layer_count']} layers · "
            f"current={current['layer']} · scene_sha256={current['scene_sha256']}\n"
            f"Shared knowledge observations={result['knowledge_observations']} · external actions=0 · automatic transcript=False"
        )
    if "output" in result:
        return f"GEM evidence: {result['output']} · bytes={result['bytes']} · no_overwrite=True"
    if "scene_id" in result:
        return (
            f"Opened {result['title']} [{result['identifier']}]\n"
            f"Scene: {result['scene_id']} · sha256={result['scene_sha256']} · source_verified=True\n"
            f"Shared observation: {result['observation_id']} · process_launched=False · external actions=0\n"
            f"{result['summary']}"
        )
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def parser():
    result = argparse.ArgumentParser(prog="zoe gem", description="Zoe's shared GEM operating environment")
    result.add_argument("--zoe-root", help="unified Zoe checkout; default: ZOE_ROOT")
    result.add_argument("arguments", nargs=argparse.REMAINDER, help="status, list, open ID, export ID PATH, or snapshot PATH")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        environment = GemOperatingEnvironment(arguments.zoe_root)
        result = environment.execute(arguments.arguments)
        print(format_result(result))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"zoe gem: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

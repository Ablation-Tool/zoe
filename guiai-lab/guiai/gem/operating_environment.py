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
    "l4-multimodule": ("autonomy", "Zoe · L4 Multi-Module Guarded Code Self-Improvement (3 Distinct Engines)"),
    "multi-module": ("autonomy", "Zoe · L4 Multi-Module Guarded Code Self-Improvement (3 Distinct Engines)"),
    "voice": ("autonomy", "Zoe · Native 44-Phoneme Voice, Singing, MIDI Baseline & Chladni Cymatics"),
    "sing": ("autonomy", "Zoe · Native 44-Phoneme Voice, Singing, MIDI Baseline & Chladni Cymatics"),
    "l5-core": ("autonomy", "Zoe · L5 Phase 1 Integrated 10-Domain Cognitive Core & 4-System Memory"),
    "unified-mind": ("autonomy", "Zoe · L5 Phase 1 Integrated 10-Domain Cognitive Core & 4-System Memory"),
    "l5-phase2": ("autonomy", "Zoe · L5 Phase 2 Open-World Generalization, Code Repair & Neural Science"),
    "openworld": ("autonomy", "Zoe · L5 Phase 2 Open-World Generalization, Code Repair & Neural Science"),
    "l5-phase3": ("autonomy", "Zoe · L5 Phase 3 Live Agentic Synthesis & Eliza-GEM Glass-Box Bench"),
    "live-agent": ("autonomy", "Zoe · L5 Phase 3 Live Agentic Synthesis & Eliza-GEM Glass-Box Bench"),
    "l5-phase4": ("autonomy", "Zoe · L5 Phase 4 Blind Eval, Stem-Layering & Embodied Mobile Mind"),
    "embodied-mind": ("autonomy", "Zoe · L5 Phase 4 Blind Eval, Stem-Layering & Embodied Mobile Mind"),
    "l5-phase5": ("autonomy", "Zoe · L5 Phase 5 ARC Induction, Real Science & 4-Gen Frontier Mind"),
    "frontier-mind": ("autonomy", "Zoe · L5 Phase 5 ARC Induction, Real Science & 4-Gen Frontier Mind"),
    "l5-phase6": ("autonomy", "Zoe · L5 Phase 6 Multi-Horizon A_tau^(h), Object ARC & Blind Scratch Evolution"),
    "autonomous-frontier": ("autonomy", "Zoe · L5 Phase 6 Multi-Horizon A_tau^(h), Object ARC & Blind Scratch Evolution"),
    "eliza": ("autonomy", "Zoe-ELIZA x GEM · Two-Gear Zero-Token Glass-Box Conversational Atelier"),
    "zoe-eliza": ("autonomy", "Zoe-ELIZA x GEM · Two-Gear Zero-Token Glass-Box Conversational Atelier"),
    "kloster-info": ("research", "Kloster Information Geometry, Multi-Horizon Phase Transitions & Causal Identifiability"),
    "info-geometry": ("research", "Kloster Information Geometry, Multi-Horizon Phase Transitions & Causal Identifiability"),
    "zoe-os": ("zoe", "Zoe OS · Unified Persistent Living Workstation Mind (All 17 GEM Engines)"),
    "living-mind": ("zoe", "Zoe OS · Unified Persistent Living Workstation Mind (All 17 GEM Engines)"),
    "wave3": ("zoe", "Zoe Wave 3 · Digital Research GEM/3 & ViewMAX Security Desktop (All 5 Vault Instruments)"),
    "wave3-desk": ("zoe", "Zoe Wave 3 · Digital Research GEM/3 & ViewMAX Security Desktop (All 5 Vault Instruments)"),
    "wave3-trust": ("autonomy", "TRUST.ACC · 5-Dim Continuous TrustEngine & nina Lume Audio Clarity"),
    "trust-acc": ("autonomy", "TRUST.ACC · 5-Dim Continuous TrustEngine & nina Lume Audio Clarity"),
    "wave3-auditors": ("ablation", "AUDIT.APP · 4 Unpublished AI-Agent Binary Auditors (BinaryContext)"),
    "audit-app": ("ablation", "AUDIT.APP · 4 Unpublished AI-Agent Binary Auditors (BinaryContext)"),
    "wave3-dualpath": ("research", "VERIFY.APP · Dual-Path Query Validation & VisorLog [MASK] Flywheel"),
    "verify-app": ("research", "VERIFY.APP · Dual-Path Query Validation & VisorLog [MASK] Flywheel"),
    "wave3-guards": ("kevlar", "GUARD.ACC · Eq. 2 Slow-Drift Cascade + GemSeal vec2text + Kevlar MCP"),
    "guard-acc": ("kevlar", "GUARD.ACC · Eq. 2 Slow-Drift Cascade + GemSeal vec2text + Kevlar MCP"),
    "wave3-actuation": ("autonomy", "ACTUATE.APP · Email Allowlist + ROS Deadman + VisorCAS Bloom/CAS"),
    "actuate-app": ("autonomy", "ACTUATE.APP · Email Allowlist + ROS Deadman + VisorCAS Bloom/CAS"),
    "wave3-gsx": ("zoe", "GSX-86 (1982) · DR-Graph Vector Telemetry Plotter (NDC 0..32767)"),
    "gsx-graph": ("zoe", "GSX-86 (1982) · DR-Graph Vector Telemetry Plotter (NDC 0..32767)"),
    "wave3-tos": ("zoe", "Atari TOS 1.0 (1985) · Little Green Desktop, File Drawers & 68k Big-Endian .RSC"),
    "tos-desk": ("zoe", "Atari TOS 1.0 (1985) · Little Green Desktop, File Drawers & 68k Big-Endian .RSC"),
    "wave3-gem2": ("zoe", "GEM 2.0 / 3.11 (1986-88) · Post-Lawsuit Two-Pane Tiled Desktop (Desk on Right)"),
    "gem2-tiled": ("zoe", "GEM 2.0 / 3.11 (1986-88) · Post-Lawsuit Two-Pane Tiled Desktop (Desk on Right)"),
    "unified-os": ("zoe", "Zoe-GEM OS · Unified 42-Component One-OS Architecture (5 Suites · 9 Sisters)"),
    "suite1-kernel": ("kevlar", "Zoe-GEM OS Suite 1 · Kernel Firewall, Policy & Stewardship (SYSCALL/VAULT/EXPORT)"),
    "suite2-telemetry": ("autonomy", "Zoe-GEM OS Suite 2 · Defensive Telemetry, Compliance & Audit Bench (JOURNAL/SCUBA/SYSMAP)"),
    "suite3-forensics": ("ablation", "Zoe-GEM OS Suite 3 · Forensics, Binary Analysis & Disclosure Lab (INTAKE/AUDIT/CEROTTO/CVD)"),
    "suite4-cognition": ("research", "Zoe-GEM OS Suite 4 · Cognitive Metacognition, Memory & Reasoning Core (VOLUME/MEMBUS/GLASSBOX)"),
    "suite5-studio": ("zoe", "Zoe-GEM OS Suite 5 · Voice, Audio Defense, Color, Biology & Visual Studio (LUME/CHROMA/SPOTLIGHT)"),
}


def _validate_no_symlink_path(destination, *, label="GEM path"):
    raw_dest = Path(destination).expanduser()
    norm_dest = Path(os.path.normpath(os.path.abspath(raw_dest)))
    for candidate in (raw_dest, *raw_dest.parents, norm_dest, *norm_dest.parents):
        if candidate.is_symlink():
            raise ValueError(f"{label} must not be or traverse a symbolic link: {candidate}")
    if ".." in raw_dest.parts:
        raise ValueError(f"{label} must not contain '..' traversal: {raw_dest}")
    return raw_dest


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
        raw_dest = _validate_no_symlink_path(destination, label="GEM output path")
        path = raw_dest.resolve()
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
            if current["layer"].startswith("wave3") or current["layer"] in {
                "trust-acc", "audit-app", "verify-app", "guard-acc", "actuate-app",
                "gsx-graph", "tos-desk", "gem2-tiled",
            }:
                from .wave3_gem_instruments import write_wave3_gem_desktop_html
                write_wave3_gem_desktop_html(scene, self.current["report"], path)
            else:
                from .dorothy import write_interactive_html
                write_interactive_html(scene, self.current["report"], path)
        elif kind == ".rsc":
            from .seasip_gem import compile_rsc, parse_rsc
            from .wave3_gem_instruments import run_wave3_gem_snapshot, wave3_object_trees
            rep = self.current["report"] if isinstance(self.current["report"], dict) and self.current["report"].get("contract") == "zoe-wave3-seasip-gem/v1" else run_wave3_gem_snapshot(self.root)
            endian = ">" if current["layer"] in {"wave3-tos", "tos-desk"} else "<"
            rsc_bytes = compile_rsc(wave3_object_trees(rep, layer=current["layer"]), endian=endian)
            parse_rsc(rsc_bytes)  # verify dual-endian roundtrip before writing
            with path.open("xb") as stream:
                stream.write(rsc_bytes)
        elif kind == ".gsx":
            from .seasip_gem import encode_gsx_stream, parse_gsx_stream
            gsx_bytes = encode_gsx_stream(scene)
            parse_gsx_stream(gsx_bytes)  # verify GSX-86 NDC 0..32767 roundtrip before writing
            with path.open("xb") as stream:
                stream.write(gsx_bytes)
        elif kind == ".img":
            from .seasip_gem import parse_gem_img, scene_to_gem_img
            img_bytes = scene_to_gem_img(scene, width=320, height=200, use_gem5_palette=True)
            parse_gem_img(img_bytes)  # verify roundtrip before writing
            with path.open("xb") as stream:
                stream.write(img_bytes)
        elif kind == ".json":
            with path.open("x", encoding="utf-8") as stream:
                stream.write(scene.json())
        else:
            raise ValueError("GEM export must use .json, .svg, .png, .html, .gem, .rsc, .img, or .gsx")
        return {
            **current,
            "output": str(path),
            "bytes": path.stat().st_size,
            "no_overwrite": True,
            "vdi_verified": kind == ".gem",
        }

    def snapshot(self, destination):
        raw_dest = _validate_no_symlink_path(destination, label="GEM snapshot path")
        path = self.registry.knowledge.save(raw_dest.resolve())
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

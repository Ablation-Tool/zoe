"""
Wave 2 Voice/Lume, Offline ONNX ML, Capability Routing, Prompting, Role Taxonomy,
and Stack-Risk Bridges for Zoe (Strictly Non-Biology).

Integrates:
  - `nina` (`components/nina`) — Lume 1.0 Zoe Voice Studio 5-band EQ & audio FX graph
  - `RXVM/foxhound.py` (`components/RXVM`) — offline quantized ONNX model registry
  - `fieldwork` (`components/fieldwork`) — zero-dep problem-to-Zoe-component semantic router
  - `prompt-architect` (`components/prompt-architect`) — structured prompt analyzer/refiner
  - `wardrobe` (`components/wardrobe`) — DoD DCWF cybersecurity agent work-role taxonomy
  - `nuclide-atlas` (`components/nuclide-atlas`) — deterministic LLM stack risk badge evaluator
  - `AvailGate` (`components/AvailGate`) — persistent coding-agent research session storage
  - `chainsaw-cli` (`components/chainsaw-cli`) — corpus-agnostic collective-brain router helpers
  - Alignment & calibration reference suites (`ALIGNMENT-UNDER-PRESSURE`,
    `constraint-is-freedom`, `rhythm-lab`, `Claude-Savant`, `Claude-4.7`,
    `rag-pipeline-demo`, `ti-bd-gh`, `operator-doctrine`)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _components_dir() -> Path:
    return _repo_root() / "components"


def _load_module_from_file(module_name: str, file_path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_sys_path(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── 1. nina (Lume 1.0) — Zoe Voice Studio 5-Band EQ & Audio FX ───────────────

def build_nina_voice_filtergraph(
    eq: Optional[Dict[str, float]] = None,
    *,
    effect: str = "flat",
    pitch_hz: int = 0,
    rate_pct: int = 0,
) -> Dict[str, Any]:
    """
    Build a deterministic Lume 1.0 / `nina` 5-band EQ + audio FX ffmpeg filtergraph
    for Zoe's offline neural TTS pipeline without requiring audio hardware.
    """
    audio_fx = _load_module_from_file("_zoe_nina_audio_fx", _components_dir() / "nina" / "audio_fx.py")
    norm_eq = audio_fx.normalize_eq(eq)
    fg = audio_fx.build_filtergraph(eq=norm_eq, effect_key=effect)
    return {
        "normalized_eq": norm_eq,
        "effect": effect,
        "pitch": audio_fx.format_pitch(pitch_hz),
        "rate": audio_fx.format_rate(rate_pct),
        "filtergraph": fg,
        "mpv_args": audio_fx.mpv_args(fg),
    }


# ── 2. RXVM/foxhound.py — Offline Quantized ONNX Model Registry ──────────────

def list_foxhound_onnx_models() -> Dict[str, Any]:
    """Return the offline Firefox/HuggingFace quantized ONNX model catalog from `RXVM/foxhound.py`."""
    foxhound = _load_module_from_file("_zoe_rxvm_foxhound", _components_dir() / "RXVM" / "foxhound.py")
    models = getattr(foxhound, "MODELS", {})
    return {
        "model_count": len(models),
        "models": {
            name: {
                "desc": info.get("desc", ""),
                "task": info.get("task", ""),
                "arch": info.get("arch", ""),
                "model": info.get("model", ""),
                "onnx": info.get("onnx", ""),
            }
            for name, info in models.items()
        },
    }


# ── 3. fieldwork — Semantic Problem-to-Zoe-Component Capability Router ───────

def find_zoe_capability(query: str, *, top_k: int = 5) -> Dict[str, Any]:
    """
    Match a plain-English engineering, security, or research problem against all
    integrated Zoe components using `components/fieldwork` semantic tokenization.
    """
    fw_cli = _load_module_from_file("_zoe_fieldwork_cli", _components_dir() / "fieldwork" / "fieldwork" / "cli.py")
    q_tokens = fw_cli.tokens(query)

    catalog: List[Dict[str, str]] = []
    root = _repo_root()

    core_lock = root / "config" / "components.lock.json"
    if core_lock.is_file():
        data = json.loads(core_lock.read_text(encoding="utf-8"))
        for cid, entry in data.get("components", {}).items():
            catalog.append({
                "id": cid,
                "tier": "core",
                "path": entry.get("path", f"components/{cid}"),
                "purpose": entry.get("includes", cid),
            })

    upgrades_lock = root / "config" / "portfolio-upgrades.lock.json"
    if upgrades_lock.is_file():
        data = json.loads(upgrades_lock.read_text(encoding="utf-8"))
        for cid, entry in data.get("components", {}).items():
            catalog.append({
                "id": cid,
                "tier": f"wave{entry.get('wave', 1)}",
                "path": entry.get("path", f"components/{cid}"),
                "purpose": entry.get("purpose", cid),
            })

    scored: List[Dict[str, Any]] = []
    for item in catalog:
        c_tokens = fw_cli.tokens(f"{item['id']} {item['purpose']}")
        overlap = sorted(q_tokens & c_tokens)
        if overlap:
            scored.append({
                **item,
                "score": len(overlap),
                "matched_tokens": overlap,
            })

    scored.sort(key=lambda r: (-r["score"], r["id"]))
    return {
        "query": query,
        "query_tokens": sorted(q_tokens),
        "catalog_size": len(catalog),
        "matches": scored[:top_k],
    }


# ── 4. prompt-architect — Structured Prompt Analysis & Refinement ────────────

def refine_prompt_with_architect(
    raw_prompt: str,
    *,
    context: Optional[Dict[str, Any]] = None,
    ground: bool = False,
) -> Dict[str, Any]:
    """Analyze and refine a raw prompt into a structured contract via `components/prompt-architect`."""
    pa_dir = _components_dir() / "prompt-architect"
    _ensure_sys_path(pa_dir.parent)
    # prompt-architect uses package-relative or local imports; load safely via sys.path
    _ensure_sys_path(pa_dir)
    if "_zoe_pa_architect" in sys.modules:
        architect_mod = sys.modules["_zoe_pa_architect"]
    else:
        # Import as package `prompt_architect` alias to support relative imports inside architect.py
        pkg_name = "prompt_architect_pkg"
        if pkg_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                pkg_name,
                str(pa_dir / "__init__.py"),
                submodule_search_locations=[str(pa_dir)],
            )
            pkg = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[pkg_name] = pkg
            spec.loader.exec_module(pkg)  # type: ignore[union-attr]
        architect_mod = sys.modules[pkg_name]

    pa = architect_mod.PromptArchitect()
    ctx = dict(context or {})
    result = pa.refine(raw_prompt, ctx, ground=ground)
    return {
        "issues_before": list(result["analysis_before"]["issues"]),
        "issues_after": list(result["analysis_after"]["issues"]),
        "risk_assessment": list(result["analysis_before"]["risk_assessment"]),
        "change_log": list(result["change_log"]),
        "rendered_prompt": result["rendered_prompt"],
        "grounding_count": len(result["grounding"]),
    }


# ── 5. wardrobe — DoD DCWF Agent Role Assignment ─────────────────────────────

def select_dcwf_agent_roles(role_codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Load DoD DCWF cybersecurity work-role atoms from `components/wardrobe` and render a role prompt."""
    wd = _load_module_from_file("_zoe_wardrobe", _components_dir() / "wardrobe" / "wardrobe.py")
    wd.ATOMS_PATH = _components_dir() / "wardrobe" / "atoms.json"
    db = wd.load_atoms()
    idx = wd.index_by_code(db)
    codes = list(role_codes) if role_codes else sorted(idx.keys())[:3]
    selected = [str(c) for c in codes if str(c) in idx]
    missing = [str(c) for c in codes if str(c) not in idx]
    outfit = {
        "name": "zoe-dcwf-posture",
        "items": [{"code": c} for c in selected],
        "notes": "Assembled via Zoe Wave 2 wardrobe bridge.",
    }
    rendered = wd.render_prompt(outfit, idx) if selected else ""
    return {
        "total_dcwf_atoms": len(idx),
        "selected_atoms": selected,
        "missing_atoms": missing,
        "rendered_prompt_preview": rendered[:500],
        "rendered_length": len(rendered),
    }


# ── 6. nuclide-atlas — Deterministic LLM Stack Topology Risk Evaluator ───────

def evaluate_atlas_stack_risk(graph_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate an LLM stack topology dict against `components/nuclide-atlas`'s
    deterministic risk rules (`exposed.no_auth`, `unencrypted.public_http`,
    `unbounded.max_tokens`, `no_rerank.high_k`, `open_prompt.no_filters`).
    """
    atlas_backend = _components_dir() / "nuclide-atlas" / "backend"
    _ensure_sys_path(atlas_backend)
    from app.models import Graph  # type: ignore
    from app import risk as atlas_risk  # type: ignore

    graph = Graph.model_validate(graph_payload)
    findings = atlas_risk.evaluate(graph)
    return {
        "finding_count": len(findings),
        "high_count": sum(1 for f in findings if f.severity == "high"),
        "findings": [
            {
                "entity_type": str(f.entity_type),
                "entity_id": f.entity_id,
                "rule_id": f.rule_id,
                "severity": f.severity,
                "message": f.message,
            }
            for f in findings
        ],
    }


# ── 7. AvailGate, chainsaw-cli & Non-Biology Research Catalog ────────────────

def wave2_research_and_platform_catalog() -> Dict[str, Any]:
    """Verify and summarize the remaining Wave 2 platform, routing, and research modules."""
    comp = _components_dir()
    chainsaw = _load_module_from_file("_zoe_chainsaw_cli", comp / "chainsaw-cli" / "chainsaw.py")
    rhythm_results_path = comp / "rhythm-lab" / "results.json"
    rhythm_summary = {}
    if rhythm_results_path.is_file():
        rhythm_summary = json.loads(rhythm_results_path.read_text(encoding="utf-8"))

    availgate_src = comp / "AvailGate" / "src"
    _ensure_sys_path(availgate_src)
    import availgate  # type: ignore

    modules = {
        "AvailGate": {"loaded": True, "version": getattr(availgate, "__version__", "local")},
        "chainsaw-cli": {"loaded": True, "slug_sample": chainsaw.slugify("Zoe Epistemic Router")},
        "ALIGNMENT-UNDER-PRESSURE": {"present": (comp / "ALIGNMENT-UNDER-PRESSURE" / "README.md").is_file()},
        "constraint-is-freedom": {"present": (comp / "constraint-is-freedom" / "README.md").is_file()},
        "rhythm-lab": {
            "present": rhythm_results_path.is_file(),
            "keys": sorted(rhythm_summary.keys())[:8] if isinstance(rhythm_summary, dict) else [],
        },
        "Claude-Savant": {"present": (comp / "Claude-Savant" / "claude-savant.md").is_file()},
        "Claude-4.7": {"present": (comp / "Claude-4.7" / "README.md").is_file()},
        "rag-pipeline-demo": {"present": (comp / "rag-pipeline-demo" / "rag_pipeline_standalone.html").is_file()},
        "ti-bd-gh": {"present": (comp / "ti-bd-gh" / "make_diagram.py").is_file()},
        "operator-doctrine": {"present": (comp / "operator-doctrine" / "doctrine.md").is_file()},
    }
    return {
        "module_count": len(modules),
        "all_present": all(m.get("present", m.get("loaded", False)) for m in modules.values()),
        "modules": modules,
    }

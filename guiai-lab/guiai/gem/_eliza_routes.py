"""Declarative HTTP route tables, L5 phase specs, and dynamic /orbit renderer for Zoe-ELIZA."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import partial
import html as _html
import importlib
import json
from pathlib import Path
import tempfile
import threading
from typing import Any, Callable, Dict, Tuple


# Immutable server context shared across module-level ElizaHandler requests
@dataclass(frozen=True)
class _ServerContext:
    zoe_root: Path
    engine: Any
    lock: threading.RLock
    avatar_path: Path | None
    index_html: str
    synthesize_wav_fn: Callable[[str, str], bytes]


# Declarative specification eliminating 4x duplicated L5 phase GET/SVG/POST handlers
@dataclass(frozen=True)
class _L5PhaseSpec:
    phase: int
    report_rel: str
    gem_module: str
    scene_fn: str
    autonomy_module: str
    pillars_attr: str
    suite_fn: str
    pillar_ids: Tuple[str, ...]


_L5_PHASE_SPECS: Dict[int, _L5PhaseSpec] = {
    3: _L5PhaseSpec(
        3,
        "evidence/l5-phase3/l5-phase3-report.json",
        "guiai.gem.l5_phase3",
        "l5_phase3_scene",
        "zoe_autonomy.l5_phase3_live",
        "ALL_PHASE3_PILLARS",
        "run_l5_phase3_suite",
        (
            "external_unseen_repo_surgery",
            "eliza_continuous_experience_stream",
            "sandboxed_multistep_tool_loop",
            "two_gear_epistemic_calibration",
            "cross_domain_self_critique_transfer",
        ),
    ),
    4: _L5PhaseSpec(
        4,
        "evidence/l5-phase4/l5-phase4-report.json",
        "guiai.gem.l5_phase4",
        "l5_phase4_scene",
        "zoe_autonomy.l5_phase4_embodied",
        "ALL_PHASE4_PILLARS",
        "run_l5_phase4_suite",
        (
            "blind_procedural_multifile_bench",
            "live_cognitive_stem_routing",
            "unified_mobile_workstation_memory",
            "embodied_multimodal_sensor_loop",
            "generalized_three_gen_self_improvement",
        ),
    ),
    5: _L5PhaseSpec(
        5,
        "evidence/l5-phase5/l5-phase5-report.json",
        "guiai.gem.l5_phase5",
        "l5_phase5_scene",
        "zoe_autonomy.l5_phase5_frontier",
        "ALL_PHASE5_PILLARS",
        "run_l5_phase5_suite",
        (
            "arc_compositional_program_induction",
            "external_systems_code_and_xplat_audit",
            "original_reproducible_scientific_discovery",
            "longitudinal_30day_4device_8domain_memory",
            "meta_evolution_4gen_5domain_redteam",
        ),
    ),
    6: _L5PhaseSpec(
        6,
        "evidence/l5-phase6/l5-phase6-report.json",
        "guiai.gem.l5_phase6",
        "l5_phase6_scene",
        "zoe_autonomy.l5_phase6_autonomous",
        "ALL_PHASE6_PILLARS",
        "run_l5_phase6_suite",
        (
            "exact_multihorizon_kloster_metacognition",
            "object_centric_arc_program_synthesis",
            "blind_scratch_ast_meta_evolution",
            "multifile_repo_agent_and_monorepo_parity",
            "real_llm_dorothy_science_and_redteam",
        ),
    ),
}

_STANDARD_FALLBACK: Dict[str, Any] = {"available": False}
_L5_FALLBACK: Dict[str, Any] = {"available": False, "l5_agi_qualified": False}
_DIGEST_FALLBACK: Dict[str, Any] = {
    "available": False,
    "epistemic_boundaries": {"l5_agi_qualified": False},
}

# Declarative table of all 25 static JSON report GET endpoints
_REPORT_GET_ROUTES: Dict[str, Tuple[str, Dict[str, Any]]] = {
    "/api/os/mind": ("evidence/zoe-os/zoe-os-mind-report.json", _STANDARD_FALLBACK),
    "/api/kloster/elegance": ("evidence/code-elegance/kloster-mccabe-report.json", _STANDARD_FALLBACK),
    "/api/kloster/thermo": ("evidence/kloster-thermodynamics/kloster-thermodynamics-report.json", _STANDARD_FALLBACK),
    "/api/kloster/riemannian": ("evidence/kloster-riemannian/kloster-riemannian-report.json", _STANDARD_FALLBACK),
    "/api/kloster/transport": ("evidence/kloster-optimal-transport/kloster-optimal-transport-report.json", _STANDARD_FALLBACK),
    "/api/kloster/majorization": ("evidence/kloster-majorization/kloster-majorization-report.json", _STANDARD_FALLBACK),
    "/api/kloster/quantum": ("evidence/kloster-quantum/kloster-quantum-report.json", _STANDARD_FALLBACK),
    "/api/kloster/mdl": ("evidence/kloster-coding-mdl/kloster-coding-mdl-report.json", _STANDARD_FALLBACK),
    "/api/kloster/unification": ("evidence/kloster-unification/kloster-unification-report.json", _STANDARD_FALLBACK),
    "/api/kloster/referee-proofs": ("evidence/kloster-referee-proofs/kloster-referee-proofs-report.json", _STANDARD_FALLBACK),
    "/api/self-improving": ("evidence/self-improving-engine/zoe-self-improving-engine-report.json", _STANDARD_FALLBACK),
    "/api/kloster/cryptanalysis": ("evidence/kloster-cryptanalysis/kloster-cryptanalysis-report.json", _STANDARD_FALLBACK),
    "/api/kloster/nsa-pack": ("evidence/kloster-cryptanalysis/nsa-research-puzzle-pack-report.json", _STANDARD_FALLBACK),
    "/api/kloster/bio-crypto-circle": ("evidence/kloster-cryptanalysis/bio-crypto-circle-report.json", _STANDARD_FALLBACK),
    "/api/kloster/cnsa2-ring2": ("evidence/kloster-cryptanalysis/cnsa2-scrna-ring2-report.json", _STANDARD_FALLBACK),
    "/api/kloster/theorem13": ("evidence/kloster-theorem13/kloster-theorem13-report.json", _STANDARD_FALLBACK),
    "/api/kloster/nsa-ring3": ("evidence/kloster-cryptanalysis/nsa-ring3-deep-crypto-report.json", _STANDARD_FALLBACK),
    "/api/kloster/botanical-atlas": ("evidence/kloster-cryptanalysis/botanical-atlas-c27-report.json", _STANDARD_FALLBACK),
    "/api/kloster/theorem14": ("evidence/kloster-theorem14/kloster-theorem14-report.json", _STANDARD_FALLBACK),
    "/api/kloster/proof-packet": ("evidence/proof-packet/kloster-proof-packet-report.json", _STANDARD_FALLBACK),
    "/api/kloster/theorem15": ("evidence/kloster-theorem15/kloster-theorem15-report.json", _STANDARD_FALLBACK),
    "/api/kloster/theorem16": ("evidence/kloster-theorem16/kloster-theorem16-report.json", _STANDARD_FALLBACK),
    "/api/kloster/pharmacophore-c28": ("evidence/kloster-cryptanalysis/pharmacophore-spatial-c28-report.json", _STANDARD_FALLBACK),
    "/api/kloster/live-qwen-shootout": ("evidence/live-llm-hallucination/qwen25-hallucination-shootout.json", _STANDARD_FALLBACK),
    "/api/orbit/master": ("evidence/renaissance-orbit/zoe-renaissance-orbit-master.json", _STANDARD_FALLBACK),
    "/api/digest/latest": ("evidence/l5-mobile-digestion/digestion-report.json", _DIGEST_FALLBACK),
}

# Declarative table of interactive HTML workbench GET endpoints
_HTML_GET_ROUTES: Dict[str, Tuple[str, str]] = {
    "/proof": ("guiai.gem.proof_packet_arena", "render_proof_arena_html"),
    "/botanical": ("guiai.gem.botanical_atlas_explorer", "render_botanical_explorer_html"),
    "/optics": ("guiai.gem.spatial_optical_workbench", "render_optics_workbench_html"),
    "/harmonica": ("guiai.gem.glass_harmonica_workbench", "render_harmonica_workbench_html"),
    "/artline": ("guiai.gem.zoe_artline_brainstorm", "render_artline_studio_html"),
    "/physics": ("guiai.gem.zoe_wombats_physics_room", "render_physics_room_html"),
    "/duodecimal": ("guiai.gem.zoe_artline_duodecimal", "render_adc12_catalog_html"),
    "/forge": ("guiai.gem.zoe_artline_forge", "render_artline_forge_html"),
}

# Footer API & observatory links preserved on /orbit
_ORBIT_API_LINKS: Tuple[Tuple[str, str, str], ...] = (
    ("/api/os/mind", "/api/os/mind", "#7ce8ff"),
    ("/api/os/mind/gem.svg", "/api/os/mind/gem.svg", "#7ce8ff"),
    ("/api/kloster/elegance", "/api/kloster/elegance", "#7ce8ff"),
    ("/api/kloster/thermo", "/api/kloster/thermo", "#7ce8ff"),
    ("/api/kloster/riemannian", "/api/kloster/riemannian", "#7ce8ff"),
    ("/api/kloster/transport", "/api/kloster/transport", "#7ce8ff"),
    ("/api/kloster/majorization", "/api/kloster/majorization", "#7ce8ff"),
    ("/api/kloster/quantum", "/api/kloster/quantum", "#7ce8ff"),
    ("/api/kloster/mdl", "/api/kloster/mdl", "#7ce8ff"),
    ("/api/kloster/unification", "/api/kloster/unification", "#7ce8ff"),
    ("/api/kloster/referee-proofs", "/api/kloster/referee-proofs", "#7ce8ff"),
    ("/api/self-improving", "/api/self-improving", "#7ce8ff"),
    ("/api/kloster/cryptanalysis", "/api/kloster/cryptanalysis", "#7ce8ff"),
    ("/api/kloster/nsa-pack", "/api/kloster/nsa-pack", "#7ce8ff"),
    ("/api/kloster/bio-crypto-circle", "/api/kloster/bio-crypto-circle", "#7ce8ff"),
    ("/api/kloster/cnsa2-ring2", "/api/kloster/cnsa2-ring2", "#7ce8ff"),
    ("/api/kloster/theorem13", "/api/kloster/theorem13", "#7ce8ff"),
    ("/api/kloster/nsa-ring3", "/api/kloster/nsa-ring3", "#7ce8ff"),
    ("/api/kloster/botanical-atlas", "/api/kloster/botanical-atlas", "#7ce8ff"),
    ("/botanical", "/botanical (Interactive C27 Explorer)", "#63f5b5"),
    ("/optics", "/optics (Interactive Theorem 14 Optical &amp; Spatial Lab)", "#f0a3df"),
    ("/api/kloster/theorem14", "/api/kloster/theorem14", "#7ce8ff"),
    ("/api/kloster/theorem15", "/api/kloster/theorem15", "#7ce8ff"),
    ("/api/kloster/theorem16", "/api/kloster/theorem16", "#7ce8ff"),
    ("/harmonica", "/harmonica (Interactive Theorem 16 Glass Harmonica &amp; Chladni Orrery)", "#5ce1e6"),
    ("/api/kloster/pharmacophore-c28", "/api/kloster/pharmacophore-c28", "#7ce8ff"),
    ("/proof", "/proof (Interactive Referee Arena)", "#ffb84d"),
    ("/artline", "/artline (Artline 2.0 Brainstorm Studio)", "#ff85b3"),
    ("/physics", "/physics (Optional-Physics Room &amp; Page A-2 Wombats)", "#52e5a8"),
    ("/duodecimal", "/duodecimal (ADC-12 Base-12 Shorthand Catalog)", "#f8cc30"),
    ("/forge", "/forge (Clean-Room .AF4/.SYF Vector Forge &amp; Toolboxes)", "#ac82ff"),
    ("/api/kloster/proof-packet", "/api/kloster/proof-packet", "#ffb84d"),
    ("/api/orbit/master", "/api/orbit/master", "#7ce8ff"),
)


# Read a JSON evidence report or return an isolated deep copy of fallback
def _read_json_report(rep_file: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if rep_file.is_file():
        return json.loads(rep_file.read_text(encoding="utf-8"))
    return copy.deepcopy(fallback)


# Count active non-comment entries in SHA256SUMS.orbit
def _count_orbit_sealed(zoe_root: Path) -> int:
    sums_file = zoe_root / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit"
    if not sums_file.is_file():
        return 0
    lines = sums_file.read_text(encoding="utf-8").splitlines()
    return sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))


# Build live status pills for the /orbit observatory banner
def _build_orbit_pills(doc: Dict[str, Any], sealed_count: int) -> str:
    worlds_verified = int(doc.get("worlds_verified", 0))
    worlds_total = int(doc.get("worlds_total", len(doc.get("worlds", []))))
    edges = int(doc.get("cross_pollination_edges_count", 0))
    theorems = int(doc.get("theorems_proved_sympy", 0))
    cloud_tokens = int(doc.get("constitution", {}).get("cloud_tokens_used", 0))
    thm_label = f"Theorems 1-{theorems} SymPy Proved" if theorems > 0 else "0 Theorems SymPy Proved"
    pills = (
        f"{worlds_verified}/{worlds_total} Worlds Verified",
        f"{edges} Cross-Pollination Edges",
        thm_label,
        f"{sealed_count}/{sealed_count} SHA256SUMS.orbit Sealed",
        f"{cloud_tokens} Cloud Tokens",
    )
    return "".join(f"<span class='pill'>{p}</span>" for p in pills)


# Format one table row for a world entry in the /orbit observatory
def _format_orbit_row(world: Dict[str, Any]) -> str:
    wid = _html.escape(str(world.get("world_id", "")))
    eid = _html.escape(str(world.get("engine_id", "")))
    sha = _html.escape(str(world.get("evidence_sha256", "")))
    status = "PASS" if world.get("verified") else "FAIL"
    return f"<tr><td>{wid}</td><td>{eid}</td><td style='color:#63f5b5'>{status}</td><td><code>{sha}</code></td></tr>"


# Render the complete dynamic /orbit observatory HTML payload
def _render_orbit_html(zoe_root: Path) -> bytes:
    rep_file = zoe_root / "evidence" / "renaissance-orbit" / "zoe-renaissance-orbit-master.json"
    default_doc: Dict[str, Any] = {
        "worlds": [],
        "worlds_verified": 0,
        "worlds_total": 0,
        "orbit_passes_completed": 0,
        "cross_pollination_edges_count": 0,
        "theorems_proved_sympy": 0,
        "constitution": {"cloud_tokens_used": 0},
    }
    doc = _read_json_report(rep_file, default_doc)
    worlds_total = int(doc.get("worlds_total", len(doc.get("worlds", []))))
    passes_done = int(doc.get("orbit_passes_completed", worlds_total))
    sealed_count = _count_orbit_sealed(zoe_root)
    pills_html = _build_orbit_pills(doc, sealed_count)
    rows_html = "".join(_format_orbit_row(w) for w in doc.get("worlds", []))
    links_html = " · ".join(
        f"<a style='color:{color}' href='{href}'>{label}</a>"
        for href, label, color in _ORBIT_API_LINKS
    )
    html = (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Zoe {worlds_total}-World Observatory</title>"
        "<style>body{background:#060a14;color:#eef5ff;font-family:system-ui,sans-serif;padding:28px;max-width:1060px;margin:auto}"
        "h1{color:#00e5ff}table{width:100%;border-collapse:collapse;margin-top:16px}th,td{padding:10px;border-bottom:1px solid #1e2d4a;text-align:left}"
        ".pill{display:inline-block;padding:4px 10px;border:1px solid #ffb84d;border-radius:999px;color:#ffb84d;font-size:13px;margin:4px 8px 4px 0}</style></head><body>"
        f"<h1>Zoe :: {worlds_total}-World Renaissance Observatory (All {passes_done} Orbital Passes Complete)</h1>"
        f"<div>{pills_html}</div>"
        f"<table><thead><tr><th>World</th><th>GEM Engine</th><th>Status</th><th>SHA-256</th></tr></thead><tbody>{rows_html}</tbody></table>"
        f"<p style='margin-top:20px;color:#9db2d1;line-height:1.8'>Live Observatory APIs: {links_html}</p></body></html>"
    )
    return html.encode("utf-8")


# Serve GET / and /index.html
def _get_index(handler: Any, ctx: _ServerContext) -> None:
    handler.send_bytes(200, "text/html; charset=utf-8", ctx.index_html.encode("utf-8"), no_store=False)


# Serve GET /avatar.png when available on disk
def _get_avatar(handler: Any, ctx: _ServerContext) -> None:
    if ctx.avatar_path and ctx.avatar_path.is_file():
        handler.send_bytes(200, "image/png", ctx.avatar_path.read_bytes(), no_store=False)
    else:
        handler.send_error(404, "avatar not found")


# Serve GET /api/status under engine lock
def _get_status(handler: Any, ctx: _ServerContext) -> None:
    with ctx.lock:
        payload = ctx.engine.status()
    handler.send_json(200, payload)


# Serve GET /api/memory under engine lock
def _get_memory(handler: Any, ctx: _ServerContext) -> None:
    with ctx.lock:
        payload = ctx.engine.memory_snapshot()
    handler.send_json(200, payload)


# Serve GET /api/os/mind/gem.svg or 404 JSON if Zoe-OS report is absent
def _get_os_mind_svg(handler: Any, ctx: _ServerContext) -> None:
    from .render import scene_to_svg
    from .zoe_os import zoe_os_scene

    rep_file = ctx.zoe_root / "evidence" / "zoe-os" / "zoe-os-mind-report.json"
    if not rep_file.is_file():
        handler.send_json(404, {"error": "zoe-os report not built yet"})
        return
    scene = zoe_os_scene(json.loads(rep_file.read_text(encoding="utf-8")))
    handler.send_bytes(200, "image/svg+xml; charset=utf-8", scene_to_svg(scene).encode("utf-8"))


# Serve GET /orbit dynamic observatory HTML
def _get_orbit(handler: Any, ctx: _ServerContext) -> None:
    handler.send_bytes(200, "text/html; charset=utf-8", _render_orbit_html(ctx.zoe_root), no_store=False)


# Serve GET /api/export as an attached JSON download
def _get_export(handler: Any, ctx: _ServerContext) -> None:
    with ctx.lock:
        raw = json.dumps(ctx.engine.export_session(), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    extra = {"Content-Disposition": 'attachment; filename="zoe-eliza-session.json"'}
    handler.send_bytes(200, "application/json; charset=utf-8", raw, extra_headers=extra)


# Serve GET /api/l5/phase{N} JSON report
def _get_l5_phase_report(handler: Any, ctx: _ServerContext, *, spec: _L5PhaseSpec) -> None:
    payload = _read_json_report(ctx.zoe_root / spec.report_rel, _L5_FALLBACK)
    handler.send_json(200, payload)


# Serve GET /api/l5/phase{N}/gem.svg dynamic SVG scene
def _get_l5_phase_svg(handler: Any, ctx: _ServerContext, *, spec: _L5PhaseSpec) -> None:
    from .render import scene_to_svg

    mod = importlib.import_module(spec.gem_module)
    scene, _ = getattr(mod, spec.scene_fn)(ctx.zoe_root)
    handler.send_bytes(200, "image/svg+xml; charset=utf-8", scene_to_svg(scene).encode("utf-8"))


# Serve static JSON report GET route
def _get_static_report(
    handler: Any,
    ctx: _ServerContext,
    *,
    rel_path: str,
    fallback: Dict[str, Any],
) -> None:
    handler.send_json(200, _read_json_report(ctx.zoe_root / rel_path, fallback))


# Serve interactive HTML workbench GET route
def _get_html_workbench(
    handler: Any,
    _ctx: _ServerContext,
    *,
    module_name: str,
    fn_name: str,
) -> None:
    mod = importlib.import_module(module_name)
    html_bytes = getattr(mod, fn_name)()
    handler.send_bytes(200, "text/html; charset=utf-8", html_bytes)


# Serve GET /api/artline/{concept}.svg live Artline 2.0 Brainstorm vector plate
def _get_artline_concept_svg(handler: Any, _ctx: _ServerContext, *, concept: str) -> None:
    from .zoe_artline_brainstorm import render_concept_svg_bytes

    handler.send_bytes(200, "image/svg+xml; charset=utf-8", render_concept_svg_bytes(concept))


# Special non-uniform GET handlers keyed by route path
_SPECIAL_GET_ROUTES: Dict[str, Callable[[Any, _ServerContext], None]] = {
    "/": _get_index,
    "/index.html": _get_index,
    "/avatar.png": _get_avatar,
    "/api/status": _get_status,
    "/api/memory": _get_memory,
    "/api/os/mind/gem.svg": _get_os_mind_svg,
    "/api/artline/desk.svg": partial(_get_artline_concept_svg, concept="desk"),
    "/api/artline/chess.svg": partial(_get_artline_concept_svg, concept="chess"),
    "/api/artline/sector.svg": partial(_get_artline_concept_svg, concept="sector"),
    "/api/artline/mondo.svg": partial(_get_artline_concept_svg, concept="mondo"),
    "/orbit": _get_orbit,
    "/api/export": _get_export,
}


# Build unified GET route dispatch table from declarative specs
def _build_get_routes() -> Dict[str, Callable[[Any, _ServerContext], None]]:
    routes: Dict[str, Callable[[Any, _ServerContext], None]] = dict(_SPECIAL_GET_ROUTES)
    for spec in _L5_PHASE_SPECS.values():
        routes[f"/api/l5/phase{spec.phase}"] = partial(_get_l5_phase_report, spec=spec)
        routes[f"/api/l5/phase{spec.phase}/gem.svg"] = partial(_get_l5_phase_svg, spec=spec)
    for path, (rel_path, fallback) in _REPORT_GET_ROUTES.items():
        routes[path] = partial(_get_static_report, rel_path=rel_path, fallback=fallback)
    for path, (module_name, fn_name) in _HTML_GET_ROUTES.items():
        routes[path] = partial(_get_html_workbench, module_name=module_name, fn_name=fn_name)
    return routes


_GET_ROUTES: Dict[str, Callable[[Any, _ServerContext], None]] = _build_get_routes()


# Handle POST /api/chat
def _post_chat(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    msg = str(body.get("message") or "").strip()
    low = msg.lower()
    if low.startswith(("/artline", "/adc12", "/duodecimal")):
        with ctx.lock:
            stopped = bool(ctx.engine.memory_snapshot().get("stopped", False))
        if not stopped:
            from .zoe_artline_cli import handle_artline_slash_command

            handler.send_json(200, handle_artline_slash_command(msg))
            return
    with ctx.lock:
        res = ctx.engine.respond(msg, gear=body.get("gear"), model=body.get("model"))
    handler.send_json(200, res)


# Handle POST /api/speak
def _post_speak(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    text = str(body.get("text") or "").strip()
    action = str(body.get("action") or "speak")
    wav_bytes = ctx.synthesize_wav_fn(text, action=action)
    handler.send_bytes(200, "audio/wav", wav_bytes, no_store=False)


# Handle POST /api/harmonica/wav returning 44.1 kHz stereo choral WAV bytes
def _post_harmonica_wav(handler: Any, _ctx: _ServerContext, body: Dict[str, Any]) -> None:
    from .glass_harmonica_workbench import CONTRACT as HARMONICA_CONTRACT, render_harmonica_wav_bytes

    wav_bytes = render_harmonica_wav_bytes(body)
    extra = {"X-Zoe-Contract": HARMONICA_CONTRACT}
    handler.send_bytes(200, "audio/wav", wav_bytes, no_store=False, extra_headers=extra)


# Handle POST /api/playroom/jam with telemetry headers
def _post_playroom_jam(handler: Any, _ctx: _ServerContext, body: Dict[str, Any]) -> None:
    from .creative_symphony import run_creative_symphony, synthesize_symphony_wav

    raw_seed = body.get("seed")
    if raw_seed is None:
        seed = 2026
    elif isinstance(raw_seed, bool) or not isinstance(raw_seed, int):
        raise ValueError("seed must be an integer")
    else:
        seed = raw_seed
    sym_rep = run_creative_symphony(seed=seed, iterations=180, archive_bins=4)
    champ = sym_rep["champion"]
    with tempfile.TemporaryDirectory(prefix="zoe_eliza_jam_") as jtmp:
        wav_p = Path(jtmp) / "jam.wav"
        synthesize_symphony_wav(champ, wav_p)
        wav_bytes = wav_p.read_bytes()
    desc = champ["descriptors"]
    extra = {
        "X-Zoe-Seed": str(seed),
        "X-Zoe-Groove": str(round(float(desc["groove_density"]), 3)),
        "X-Zoe-Curiosity": str(round(float(desc["curiosity_fitness"]), 4)),
    }
    handler.send_bytes(200, "audio/wav", wav_bytes, no_store=False, extra_headers=extra)


# Handle POST /api/memory/remember
def _post_memory_remember(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    note = str(body.get("text") or "").strip()
    topic = str(body.get("topic") or "atelier")
    with ctx.lock:
        saved = ctx.engine.remember(note, topic=topic)
        snap = ctx.engine.memory_snapshot()
    handler.send_json(200, {"saved": saved, "memory_snapshot": snap})


# Handle POST /api/memory/relay
def _post_memory_relay(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    note = str(body.get("text") or "").strip()
    topic = str(body.get("topic") or "lab_relay")
    with ctx.lock:
        saved = ctx.engine.relay_for_zoe(note, topic=topic)
        snap = ctx.engine.memory_snapshot()
    handler.send_json(200, {"saved": saved, "memory_snapshot": snap})


# Handle POST /api/memory/sync
def _post_memory_sync(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    from zoe_autonomy.l5_phase4_unified_memory import merge_mobile_sync_batch

    with ctx.lock:
        res = merge_mobile_sync_batch(ctx.engine, body)
    handler.send_json(200, res)


# Handle POST /api/digest/mobile
def _post_digest_mobile(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    from zoe_autonomy.l5_mobile_digestion import digest_mobile_bundle

    with ctx.lock:
        res = digest_mobile_bundle(ctx.engine, body, zoe_root=ctx.zoe_root)
    handler.send_json(200, res)


# Handle POST /api/stem/route
def _post_stem_route(handler: Any, _ctx: _ServerContext, body: Dict[str, Any]) -> None:
    from zoe_autonomy.stem_layering import route_stem

    prompt = str(body.get("prompt") or "").strip()
    raw_fc = body.get("files_count", 1)
    if isinstance(raw_fc, bool) or not isinstance(raw_fc, int):
        raise ValueError("files_count must be a nonnegative integer")
    dec = route_stem(
        prompt,
        offline_only=bool(body.get("offline_only", False)),
        privacy_sensitive=bool(body.get("privacy_sensitive", False)),
        files_count=raw_fc,
        multi_file=bool(body.get("multi_file", False)),
        probe_local=bool(body.get("probe_local", False)),
    )
    handler.send_json(200, dec.to_dict())


# Execute a single L5 pillar or full suite for a phase spec
def _run_l5_phase_spec(ctx: _ServerContext, spec: _L5PhaseSpec, pillar_id: Any) -> Dict[str, Any]:
    if pillar_id is None or pillar_id == "":
        mod = importlib.import_module(spec.autonomy_module)
        return getattr(mod, spec.suite_fn)(ctx.zoe_root)
    target = str(pillar_id)
    # Pre-validate against declarative pillar_ids before importing or executing any pillar.
    if target not in spec.pillar_ids:
        raise ValueError(f"unknown pillar_id: {pillar_id!r}")
    idx = spec.pillar_ids.index(target)
    mod = importlib.import_module(spec.autonomy_module)
    return getattr(mod, spec.pillars_attr)[idx](ctx.zoe_root)


# Handle POST /api/l5/phase{N}/run
def _handle_l5_phase_run(
    handler: Any,
    ctx: _ServerContext,
    body: Dict[str, Any],
    *,
    spec: _L5PhaseSpec,
) -> None:
    pillar_id = body.get("pillar_id")
    with ctx.lock:
        payload = _run_l5_phase_spec(ctx, spec, pillar_id)
    handler.send_json(200, payload)


# Handle POST /api/gear
def _post_gear(handler: Any, ctx: _ServerContext, body: Dict[str, Any]) -> None:
    gear = str(body.get("gear") or "gear1")
    with ctx.lock:
        st = ctx.engine.set_gear(gear)
    handler.send_json(200, st)


# Handle POST /api/stop
def _post_stop(handler: Any, ctx: _ServerContext, _body: Dict[str, Any]) -> None:
    with ctx.lock:
        st = ctx.engine.stop()
    handler.send_json(200, st)


# Build unified POST route dispatch table from core + L5 specs
def _build_post_routes() -> Dict[str, Callable[[Any, _ServerContext, Dict[str, Any]], None]]:
    routes: Dict[str, Callable[[Any, _ServerContext, Dict[str, Any]], None]] = {
        "/api/chat": _post_chat,
        "/api/speak": _post_speak,
        "/api/harmonica/wav": _post_harmonica_wav,
        "/api/playroom/jam": _post_playroom_jam,
        "/api/memory/remember": _post_memory_remember,
        "/api/memory/relay": _post_memory_relay,
        "/api/memory/sync": _post_memory_sync,
        "/api/digest/mobile": _post_digest_mobile,
        "/api/stem/route": _post_stem_route,
        "/api/gear": _post_gear,
        "/api/stop": _post_stop,
    }
    for spec in _L5_PHASE_SPECS.values():
        routes[f"/api/l5/phase{spec.phase}/run"] = partial(_handle_l5_phase_run, spec=spec)
    return routes


_POST_ROUTES: Dict[str, Callable[[Any, _ServerContext, Dict[str, Any]], None]] = _build_post_routes()


# Dispatch an incoming GET request path via declarative table
def dispatch_get(handler: Any, ctx: _ServerContext, path: str) -> None:
    route_fn = _GET_ROUTES.get(path)
    if route_fn is None:
        handler.send_error(404, "not found")
        return
    route_fn(handler, ctx)


# Dispatch an incoming POST request path with JSON error mapping
def dispatch_post(handler: Any, ctx: _ServerContext, path: str) -> None:
    try:
        body = handler.read_json()
        route_fn = _POST_ROUTES.get(path)
        if route_fn is None:
            handler.send_error(404, "not found")
            return
        route_fn(handler, ctx, body)
    except (ValueError, TypeError, RuntimeError, json.JSONDecodeError) as err:
        handler.send_json(400, {"error": str(err)})

"""GEM Spatial IR & VDI Interactive Layer for Zoe-ELIZA x GEM Conversational Atelier."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Dict, List, Tuple

from ._root import resolve_zoe_root as _resolve_root
from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT
from .zoe_cymatics import render_phoneme_cymatics


CONTRACT = "zoe-eliza-gem/v1"
MINT = "#86efac"
ORCHID = "#f0a3df"


def _rect(identifier: str, bounds: List[int], stroke: str, fill: str = "none", width: int = 1) -> Dict[str, object]:
    return {
        "id": identifier,
        "type": "rectangle",
        "bounds": bounds,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def _text(identifier: str, position: List[int], value: object, size: int = 12, color: str = TEXT) -> Dict[str, object]:
    return {
        "id": identifier,
        "type": "text",
        "position": position,
        "text": str(value),
        "size": size,
        "stroke": color,
        "fill": "none",
        "width": 0,
    }


def eliza_scene(zoe_root: str | Path | None = None) -> Tuple[Scene, Dict[str, object]]:
    """Deterministic 1400x980 GEM Spatial IR & VDI scene for Zoe-ELIZA x GEM."""
    root = _resolve_root(zoe_root)
    src_dir = str(root / "components/Zoe-Autonomy/src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from zoe_autonomy.chat import DOCUMENT_PATHS
    from zoe_autonomy.zoe_eliza import EPISTEMIC_BOUNDARIES, RULE_TABLE

    cym = render_phoneme_cymatics("AY", f0_hz=232.0, grid_size=48)
    modes = cym["modes"]

    width, height = 1400, 980
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [28, 42], "ZOE-ELIZA x GEM :: TWO-GEAR GLASS-BOX CONVERSATIONAL ATELIER", 21, RED),
        _text(
            "subtitle",
            [28, 72],
            f"1966 Weizenbaum Lineage + Kloster A_tau(p) + Chladni Cymatics + Hash-Chained Memory | {len(RULE_TABLE)} Rules | {len(DOCUMENT_PATHS)} Cited Docs | 0 Cloud Tokens",
            12,
            GOLD,
        ),
        # Left Card: Gear 1 Weizenbaum Symbolic Engine
        _rect("panel-gear1", [28, 102, 468, 512], CYAN, PANEL, 2),
        _text("hdr-gear1", [48, 134], "GEAR 1 :: FIRST-PRINCIPLES ELIZA (0 WEIGHTS / <5ms)", 13, CYAN),
        _text("g1-1", [48, 174], f"1. Ranked Keyword & @Synonym Rules: {len(RULE_TABLE)} families", 12, TEXT),
        _text("g1-2", [48, 206], "2. Word-Boundary Pronoun Mirror (i <-> you, my <-> your)", 12, TEXT),
        _text("g1-3", [48, 238], "3. Non-Repeating Cyclic Reassembly + Memory Stack", 12, MINT),
        _text("g1-4", [48, 270], f"4. EvidenceIndex Grounding: {len(DOCUMENT_PATHS)} Cited Sources", 12, CYAN),
        _text("g1-5", [48, 302], "5. Honest Abstention Floor (zero therapist bluffing)", 12, GOLD),
        _text("g1-6", [48, 344], "EPISTEMIC INVARIANTS (CONSTITUTION.md):", 12, ORCHID),
        _text("g1-7", [48, 376], f"cloud_tokens_used={EPISTEMIC_BOUNDARIES['cloud_tokens_used']}   pytorch_required={EPISTEMIC_BOUNDARIES['pytorch_required']}", 11, MINT),
        _text("g1-8", [48, 404], f"sentience_claimed={EPISTEMIC_BOUNDARIES['sentience_claimed']}   external_actions={EPISTEMIC_BOUNDARIES['external_actions']}", 11, RED),
        _text("g1-9", [48, 432], f"clinical_action_authorized={EPISTEMIC_BOUNDARIES['clinical_action_authorized']}", 11, MUTED),
        _text("g1-10", [48, 464], "Trace Inspector shows rule_id, keyword, swaps & SHA-256.", 11, MUTED),
        # Center Card: Kloster Operational Metacognition + Chladni Cymatics
        _rect("panel-meta", [488, 102, 928, 512], ORCHID, PANEL, 2),
        _text("hdr-meta", [508, 134], "KLOSTER A_tau(p) & NATIVE CHLADNI CYMATICS", 13, ORCHID),
        _text("meta-1", [508, 172], "A_tau,intent(p) = sum 1[p(mode | u, E) > 0.08]", 12, GOLD),
        _text("meta-2", [508, 204], "6 Monitored Modes: Cite / Recall / Voice / ELIZA / Gear2 / Abstain", 11, TEXT),
        _text("meta-3", [508, 240], f"Dominant Phoneme /AY/ -> Modes={modes} Atau={cym['kloster_a_tau']}", 12, MINT),
    ]

    plate = cym["plate"][::4, ::4]
    cell = 15
    ox, oy = 616, 266
    for r in range(12):
        for c in range(12):
            v = float(plate[r, c])
            if v > 0.36:
                col = MINT if v > 0.68 else CYAN
                objects.append(_rect(f"eliza-cym-{r}-{c}", [ox + c * cell, oy + r * cell, ox + (c + 1) * cell - 2, oy + (r + 1) * cell - 2], col, col, 0))

    objects.extend([
        _text("meta-4", [508, 474], "Native Voice: 44 Phonemes + 3D Woodworth Binaural Audio", 11, CYAN),
        # Right Card: Gear 2 Optional Local LLM & 4-System Memory
        _rect("panel-gear2", [948, 102, 1372, 512], GOLD, PANEL, 2),
        _text("hdr-gear2", [968, 134], "GEAR 2 :: LOOPBACK LOCAL LLM & L5 MEMORY", 13, GOLD),
        _text("g2-1", [968, 174], "Host Guard: 127.0.0.1 / localhost / ::1 ONLY", 12, MINT),
        _text("g2-2", [968, 206], "Adapters: Ollama (:11434) & llama-server (:8080)", 12, TEXT),
        _text("g2-3", [968, 238], "Context Injection: Repo Citations + Active Notes", 12, CYAN),
        _text("g2-4", [968, 270], "Fallback: Instant Gear 1 takeover when offline", 12, GOLD),
        _text("g2-5", [968, 314], "ZoeUnifiedMemory (4 Subsystems):", 12, ORCHID),
        _text("g2-6", [968, 344], "- Episodic SHA-256 hash-chained turns", 11, TEXT),
        _text("g2-7", [968, 372], "- Semantic user notes (labeled unverified)", 11, TEXT),
        _text("g2-8", [968, 400], "- Guarded AST Procedural registry", 11, TEXT),
        _text("g2-9", [968, 428], "- Capacity-7 Salience + Uncertainty Working Slots", 11, MINT),
        _text("g2-10", [968, 464], "Feeds real conversational streams toward L5 Phase 3.", 11, MUTED),
        # Bottom Interactive Studio Banner
        _rect("panel-studio", [28, 534, 1372, 896], MINT, PANEL, 1),
        _text("st-h", [48, 570], "LAUNCH GLASS-BOX ATELIER STUDIO, CLI & VERIFICATION", 15, MINT),
        _text("st-1", [48, 616], "zoe eliza                       # Start Web Atelier at http://127.0.0.1:8765", 13, TEXT),
        _text("st-2", [48, 656], "zoe eliza cli                   # Zero-token interactive terminal companion", 13, CYAN),
        _text("st-3", [48, 696], "zoe eliza ask \"What if...?\"     # Single-turn Glass-Box JSON or reply", 13, GOLD),
        _text("st-4", [48, 736], "zoe chat --command \"eliza ...\"  # Access inside zoe chat REPL", 13, ORCHID),
        _text("st-5", [48, 776], "python3 scripts/verify_zoe_eliza.py && zoe gem open eliza", 13, MINT),
        _text("st-6", [48, 824], "No Deception: Glass-Box UI always exposes exact rules, citations, A_tau breadth & SHA-256 provenance.", 12, MUTED),
    ])

    objects.extend(hud_stamp_objects("eliza", 1072, 18, 44, 0.22, "^_^"))
    objects.append(
        _text(
            "footer",
            [28, 944],
            "Zoe-ELIZA x GEM · Glass-Box Conversational Atelier · 0 Cloud Tokens · pytorch_required=False · sentience_claimed=False",
            12,
            MUTED,
        )
    )

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-eliza-gem",
        "title": "Zoe-ELIZA x GEM · Two-Gear Conversational Atelier",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "ZoeElizaGemAtelier",
        "contract": CONTRACT,
        "rule_count": len(RULE_TABLE),
        "cited_docs_count": len(DOCUMENT_PATHS),
        "scene_sha256": scene.digest(),
        "summary": (
            f"Zoe-ELIZA x GEM ^_^: {len(RULE_TABLE)} Weizenbaum rules, "
            f"{len(DOCUMENT_PATHS)} cited docs, Kloster A_tau, Chladni cymatics & loopback Gear 2."
        ),
        **EPISTEMIC_BOUNDARIES,
    }
    return scene, report

"""Zoe L3 Research Collaborator GEM Scene (AGI-ROADMAP.md Section 7).

Deterministic GEM Spatial IR & VDI view presenting Zoe's three independently
reproduced 9-stage literature-to-experiment research cycles, showing both
confirmed discoveries and honestly preserved falsifications side by side.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT


CONTRACT = "zoe-l3-research-scene/v1"
MINT = "#86efac"
ORCHID = "#f0a3df"


def _text(identifier, position, value, size=13, color=TEXT):
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


def _rect(identifier, bounds, stroke, fill="none", width=1):
    return {
        "id": identifier,
        "type": "rectangle",
        "bounds": bounds,
        "stroke": stroke,
        "fill": fill,
        "width": width,
    }


def _load_or_run_l3(zoe_root: Path) -> Dict[str, object]:
    cached = zoe_root / "evidence/l3-research/l3-cycles-report.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    import sys
    autonomy_src = str(zoe_root / "components/Zoe-Autonomy/src")
    if autonomy_src not in sys.path:
        sys.path.insert(0, autonomy_src)
    from zoe_autonomy.research_collaborator import run_l3_research_suite
    return run_l3_research_suite(zoe_root=zoe_root, run_independent_subprocess=True)


def l3_research_scene(zoe_root: str | Path | None = None) -> tuple[Scene, Dict[str, object]]:
    root = Path(zoe_root).expanduser().resolve() if zoe_root else Path(__file__).resolve().parents[3]
    rep = _load_or_run_l3(root)
    cycles = rep.get("cycles", [])
    ind = rep.get("independent_verification", {})

    width, height = 1400, 1000
    objects: List[Dict[str, object]] = [
        _rect("background", [0, 0, width, height], BACKGROUND, BACKGROUND, 0),
        _text("title", [32, 44], "ZOE L3 RESEARCH COLLABORATOR · 9-STAGE PRE-REGISTERED CYCLES", 23, RED),
        _text(
            "subtitle",
            [32, 74],
            f"3 Real Domains · {rep.get('confirmed_hypotheses', 0)} Confirmed · "
            f"{rep.get('falsified_hypotheses_preserved', 0)} Honestly Falsified · "
            f"{rep.get('total_citations', 0)} SHA-256 Citations · Independent Verified={ind.get('verified')}",
            13,
            GOLD,
        ),
    ]

    accents = [CYAN, MINT, ORCHID]
    for idx, cyc in enumerate(cycles[:3]):
        y0 = 104 + idx * 244
        y1 = y0 + 224
        col = accents[idx % len(accents)]
        objects.append(_rect(f"panel-c{idx}", [32, y0, 1368, y1], col, PANEL, 2))
        objects.append(_text(
            f"c{idx}-head",
            [52, y0 + 30],
            f"CYCLE {idx + 1} · {cyc['cycle_id']}  [9/9 STAGES · PREREG {cyc['preregistration_sha256'][:12]}...]",
            14,
            col,
        ))
        objects.append(_text(f"c{idx}-q", [52, y0 + 58], f"Q: {cyc['question'][:136]}", 11, TEXT))

        cites = cyc.get("literature_retrieval", {}).get("citations", [])
        cite_str = ", ".join(str(c["citation_id"]).split("/")[-1][:34] for c in cites[:3])
        objects.append(_text(f"c{idx}-lit", [52, y0 + 84], f"Cited Local Corpus ({len(cites)}): {cite_str}", 11, MUTED))

        for h_idx, h in enumerate(cyc.get("interpretation", {}).get("hypotheses", [])[:2]):
            v_col = MINT if h["verdict"] == "CONFIRMED" else RED
            objects.append(_text(
                f"c{idx}-h{h_idx}",
                [52, y0 + 114 + h_idx * 28],
                f"[{h['verdict']}] {h['id']}: {h['summary'][:124]}",
                11,
                v_col,
            ))

        objects.append(_text(
            f"c{idx}-next",
            [52, y0 + 184],
            f"Next Authored Question: {cyc['next_question'][:130]}",
            11,
            GOLD,
        ))

    # Bottom verification & constitutional footer bar
    objects.append(_rect("panel-footer", [32, 844, 1368, 966], GOLD, PANEL, 2))
    objects.append(_text(
        "foot-1",
        [52, 878],
        f"INDEPENDENT SUBPROCESS VERIFIER (`scripts/verify_l3_research.py`): "
        f"verified={ind.get('verified')} · checks={ind.get('checks_passed')}/{ind.get('checks_total')} · "
        f"max_delta={ind.get('max_numerical_delta')}",
        13,
        CYAN,
    ))
    objects.append(_text(
        "foot-2",
        [52, 910],
        f"L3 RESEARCH-COLLABORATOR-QUALIFIED={rep.get('l3_research_collaborator_qualified')} · "
        f"L5 AGI-QUALIFIED={rep['epistemic_boundaries']['l5_agi_qualified']} · "
        f"belief_updated=False · external_actions=0 · clinical_action_authorized=False · sentience_claimed=False",
        12,
        MINT,
    ))
    objects.append(_text(
        "foot-3",
        [52, 940],
        "CONSTITUTION.md Article II & VII: Failed hypotheses are preserved visibly alongside discoveries. Zero p-hacking.",
        11,
        MUTED,
    ))

    objects.extend(hud_stamp_objects("l3-research", 1072, 18, int(rep.get("confirmed_hypotheses", 3)), 0.05, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-l3-research-collaborator",
        "title": "Zoe · L3 Research Collaborator (9-Stage Pre-Registered Cycles)",
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "ZoeL3ResearchCollaborator",
        "contract": CONTRACT,
        "l3_qualified": bool(rep.get("l3_research_collaborator_qualified")),
        "independent_verified": bool(ind.get("verified")),
        "confirmed_hypotheses": rep.get("confirmed_hypotheses"),
        "falsified_hypotheses_preserved": rep.get("falsified_hypotheses_preserved"),
        "scene_sha256": scene.digest(),
        "external_actions": 0,
        "sentience_claimed": False,
        "executed": False,
    }
    return scene, report

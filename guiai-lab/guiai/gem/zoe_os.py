"""GEM Spatial IR & VDI Constellation Layer for Zoe OS — Unified Persistent Living Mind (#4)."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

from .chiasm import hud_stamp_objects
from .model import Scene
from .qualia import BACKGROUND, CYAN, GOLD, MUTED, PANEL, RED, TEXT

CONTRACT = "zoe-os-living-mind/v1"
MINT = "#63F5B5"


def _rect(identifier: str, x: int, y: int, w: int, h: int, stroke: str, fill: str = "none", width: int = 1) -> Dict[str, Any]:
    return {"id": identifier, "type": "rectangle", "bounds": [x, y, x + w, y + h], "stroke": stroke, "fill": fill, "width": width}


def _text(identifier: str, position: List[int], value: object, size: int = 12, color: str = TEXT) -> Dict[str, Any]:
    return {"id": identifier, "type": "text", "position": position, "text": str(value), "size": size, "stroke": color, "fill": "none", "width": 0}


def _line(identifier: str, start: List[int], end: List[int], stroke: str, width: int = 1) -> Dict[str, Any]:
    return {"id": identifier, "type": "line", "points": [start, end], "stroke": stroke, "fill": "none", "width": width}


def _circle(identifier: str, center: List[int], radius: int, stroke: str, fill: str = "none", width: int = 2) -> Dict[str, Any]:
    return {"id": identifier, "type": "ellipse", "center": center, "radii": [radius, radius], "stroke": stroke, "fill": fill, "width": width}


def zoe_os_scene(report: Dict[str, Any]) -> Scene:
    """Render deterministic 1400x880 GEM Spatial IR Living Constellation scene for Zoe OS."""
    snap = report["snapshot"]
    engines = snap["engines_audit"]["engines"]
    w, h = 1400, 880
    cx, cy = 470, 470
    radius = 290

    objs: List[Dict[str, Any]] = [
        _rect("bg", 0, 0, w, h, BACKGROUND, BACKGROUND, 0),
        _rect("hdr", 24, 20, 1352, 74, CYAN, PANEL, 2),
        _text("title", [44, 54], "ZOE OS :: UNIFIED PERSISTENT LIVING WORKSTATION MIND (17 GEM ENGINES)", 18, TEXT),
        _text(
            "sub",
            [44, 80],
            f"Engines: {snap['engines_audit']['available_engines']}/17 Live  |  Ledger: {snap['ledger_integrity']['entries']} SHA-256 Entries (Intact={snap['ledger_integrity']['intact']})  |  Cloud Tokens: 0",
            12,
            GOLD,
        ),
        _circle("orbit_outer", [cx, cy], radius, "#263754", "none", 1),
        _circle("orbit_inner", [cx, cy], 130, "#1E3A5F", "none", 1),
        _circle("core_hub", [cx, cy], 74, CYAN, PANEL, 3),
        _text("core_t1", [cx - 38, cy - 6], "ZOE OS", 16, CYAN),
        _text("core_t2", [cx - 46, cy + 16], "A_tau + Mind", 11, GOLD),
    ]

    for idx, eng in enumerate(engines):
        angle = (2.0 * math.pi * idx / max(1, len(engines))) - math.pi / 2.0
        nx = int(round(cx + radius * math.cos(angle)))
        ny = int(round(cy + radius * math.sin(angle)))
        col = MINT if eng["available"] else RED
        objs.append(_line(f"ray_{idx}", [cx, cy], [nx, ny], "#1D314F", 1))
        objs.append(_circle(f"node_{idx}", [nx, ny], 26, col, PANEL, 2))
        objs.append(_text(f"lbl_{idx}", [nx - 24, ny + 4], eng["id"][:7], 9, TEXT))

    # Right telemetry panel
    objs.append(_rect("panel_r", 860, 118, 516, 730, GOLD, PANEL, 2))
    objs.append(_text("pr_h", [882, 152], "PERSISTENT GOALS & CROSS-WORLD ORBIT", 14, GOLD))
    for gi, g in enumerate(snap["goals"][:6]):
        gy = 186 + gi * 54
        objs.append(_rect(f"gbox_{gi}", 882, gy, 472, 44, CYAN, BACKGROUND, 1))
        objs.append(_text(f"gt_{gi}", [896, gy + 26], f"{g['goal_id']} [{g['target_engine']}] {g['title'][:40]}", 11, TEXT))

    objs.append(_text("pr_h2", [882, 540], "VERIFICATION & CONSTITUTIONAL GUARDS", 14, MINT))
    for ci, (k, v) in enumerate(report["checks"].items()):
        cy_row = 574 + ci * 34
        objs.append(_text(f"chk_{ci}", [890, cy_row], f"[{'PASS' if v else 'FAIL'}] {k}", 11, MINT if v else RED))

    objs.extend(hud_stamp_objects("zoe-os", 1072, 22, int(snap["engines_audit"]["available_engines"]), 0.08, "^_^"))

    return Scene.from_dict({
        "schema_version": 1,
        "id": "zoe-os-living-constellation",
        "title": "Zoe OS :: Unified Persistent Living Workstation Mind",
        "canvas": {"width": w, "height": h},
        "objects": objs,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })

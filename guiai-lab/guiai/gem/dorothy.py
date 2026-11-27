"""Dorothy: Allen CCFv3 structure meshes as a native GEM brain atlas scene."""

from __future__ import annotations

from html import escape
import json
import math
from pathlib import Path

from .model import Scene
from .dorothy_data import ATLAS_CITATION, ATLAS_NAME, load_structures
from .render import scene_to_svg
from .spatial3d import Camera, parse_ply, render_triangles

CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 1200
VIEWPORT_WIDTH = 1180
LEGEND_LEFT = 1210

QUALIA_PALETTE = {
    549: "#e7c77b",   # Thalamus -> Qualia Gold
    1097: "#ef445a",  # Hypothalamus -> GEM Red
    1089: "#f0abfc",  # Hippocampal formation -> Luminous Magenta
    315: "#1e3a5f",   # Isocortex -> Deep Translucent Slate-Cyan
    698: "#294058",   # Olfactory areas -> Deep Slate
    512: "#62dce8",   # Cerebellum -> Qualia Cyan
}


def _text(identifier, position, text, size=22, stroke="black"):
    return {"id": identifier, "type": "text", "position": position, "text": text, "size": size, "stroke": stroke, "fill": "none", "width": 0}


def _crafts_tract_polylines():
    """
    Deterministic 2D/3D projected Crafts-Delmarcelle crossing optic/white-matter
    hyperstreamline ribbons in the viewport coordinate frame.
    """
    cx, cy = 580.0, 590.0
    pts_cyan = []
    pts_gold = []
    for k in range(25):
        t = -1.0 + 2.0 * k / 24.0
        x = cx + t * 340.0
        y1 = cy + math.sin(t * 2.4) * 145.0 - t * 35.0
        y2 = cy - math.sin(t * 2.4) * 145.0 - t * 35.0
        pts_cyan.append([round(x, 2), round(y1, 2)])
        pts_gold.append([round(x, 2), round(y2, 2)])
    return [
        {"id": "crafts-tract-cyan", "type": "polyline", "points": pts_cyan, "stroke": "#62dce8", "fill": "none", "width": 3},
        {"id": "crafts-tract-gold", "type": "polyline", "points": pts_gold, "stroke": "#e7c77b", "fill": "none", "width": 3},
    ]


def dorothy_scene(
    structures,
    yaw=215.0,
    pitch=-18.0,
    distance=None,
    fov=35.0,
    shade_levels=16,
    theme="paper",
    show_tracts=False,
    show_hud=False,
):
    if not structures:
        raise ValueError("Dorothy requires at least one structure")
    if theme not in {"paper", "qualia"}:
        raise ValueError("Dorothy theme must be 'paper' or 'qualia'")

    qualia = theme == "qualia"
    text_color = "#e7edf5" if qualia else "black"
    muted_color = "#9cafc4" if qualia else "black"
    swatch_stroke = "#62dce8" if qualia else "black"

    items = []
    for record in structures:
        color = QUALIA_PALETTE.get(record["id"], record["color"]) if qualia else record["color"]
        items.append((record["id"], parse_ply(record["data"]), color))

    vertices = [vertex for _identifier, mesh, _color in items for vertex in mesh.vertices]
    fitted = Camera.fit(vertices, yaw=yaw, pitch=pitch, fov=fov)
    camera = fitted if distance is None else Camera(fitted.target, distance, yaw=yaw, pitch=pitch, fov=fov)
    rendered = render_triangles(items, camera, VIEWPORT_WIDTH, CANVAS_HEIGHT, shade_levels=shade_levels)

    objects = []
    if qualia:
        objects.append({
            "id": "qualia-background", "type": "rectangle",
            "bounds": [0, 0, CANVAS_WIDTH, CANVAS_HEIGHT],
            "fill": "#09111f", "stroke": "#09111f", "width": 0,
        })
    objects.append({
        "id": "ccf-mesh", "type": "mesh", "role": "ccf_structures",
        "points": rendered["points"], "fills": rendered["fills"],
        "fill": "none", "stroke": "none", "width": 0,
    })
    if show_tracts or qualia:
        objects.extend(_crafts_tract_polylines())

    objects.append(_text("atlas-title", [LEGEND_LEFT, 56], "Dorothy", 30, stroke="#ef445a" if qualia else text_color))
    objects.append(_text("atlas-subtitle", [LEGEND_LEFT, 88], "Allen Mouse CCFv3 · 2017 meshes", 20, stroke="#e7c77b" if qualia else text_color))
    top = 130
    for index, record in enumerate(structures):
        y = top + index * 66
        fill_color = QUALIA_PALETTE.get(record["id"], record["color"]) if qualia else record["color"]
        objects.append({
            "id": f"swatch-{record['id']}", "type": "rectangle",
            "bounds": [LEGEND_LEFT, y, LEGEND_LEFT + 26, y + 26],
            "fill": fill_color, "stroke": swatch_stroke, "width": 1,
        })
        objects.append(_text(f"legend-{record['id']}", [LEGEND_LEFT + 38, y + 22], f"{record['acronym']} · {record['id']}", 24, stroke=text_color))
        objects.append(_text(f"name-{record['id']}", [LEGEND_LEFT + 38, y + 46], record["name"], 20, stroke=muted_color))
    footer = top + len(structures) * 66 + 26
    camera_state = camera.state()
    objects.append(_text("camera", [LEGEND_LEFT, footer], f"yaw={camera_state['yaw']:g}° pitch={camera_state['pitch']:g}° fov={camera_state['fov']:g}°", 18, stroke=muted_color))
    objects.append(_text("counts", [LEGEND_LEFT, footer + 30], f"{rendered['total']:,} triangles · {len(structures)} structures", 18, stroke=muted_color))
    objects.append(_text("renderer", [LEGEND_LEFT, footer + 58], "Deterministic software render", 18, stroke=muted_color))
    objects.append(_text("renderer-detail", [LEGEND_LEFT, footer + 82], "painter's algorithm · flat shading", 18, stroke=muted_color))
    objects.append(_text("credit", [LEGEND_LEFT, footer + 116], "Data: Allen Institute", 18, stroke=muted_color))
    objects.append(_text("citation", [LEGEND_LEFT, footer + 140], "Wang et al. 2020, Cell 180(5)", 18, stroke=muted_color))
    objects.append(_text("scope", [LEGEND_LEFT, footer + 174], "Atlas geometry only; no registration,", 16, stroke=muted_color))
    objects.append(_text("scope-2", [LEGEND_LEFT, footer + 196], "connectivity, or inference claim", 16, stroke=muted_color))

    if show_hud or qualia:
        from .chiasm import hud_stamp_objects
        objects.extend(hud_stamp_objects("dorothy", 28, 24, len(structures), 0.15, "^_^"))

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": "dorothy-ccf2017-qualia" if qualia else "dorothy-ccf2017",
        "title": "Dorothy · CCFv3 3D brain atlas (Qualia theme)" if qualia else "Dorothy · CCFv3 3D brain atlas",
        "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })
    report = {
        "instrument": "Dorothy",
        "atlas": ATLAS_NAME,
        "citation": ATLAS_CITATION,
        "structures": [{
            "id": record["id"],
            "acronym": record["acronym"],
            "name": record["name"],
            "color": record["color"],
            "triangles": rendered["counts"][record["id"]],
            "sha256": record["sha256"],
        } for record in structures],
        "vertices": len(vertices),
        "triangles": rendered["total"],
        "camera": camera_state,
        "shade_levels": shade_levels,
        "renderer": "deterministic software projection, two-sided flat shading, painter's algorithm",
        "scene_sha256": scene.digest(),
    }
    if qualia or show_tracts or show_hud:
        report["theme"] = theme
        report["tracts_rendered"] = bool(show_tracts or qualia)
        report["hud_stamp"] = bool(show_hud or qualia)
    return scene, report


def default_dorothy_document(root=None, **options):
    return dorothy_scene(load_structures(root), **options)


def default_dorothy_qualia_document(root=None, **options):
    options.setdefault("theme", "qualia")
    options.setdefault("show_tracts", True)
    options.setdefault("show_hud", True)
    return dorothy_scene(load_structures(root), **options)


def write_interactive_html(scene: Scene, report: dict, destination: str | Path) -> Path:
    """
    Exports a self-contained, zero-dependency HTML inspector with embedded SVG,
    zoom/pan, and live Operational Metacognition threshold filtration slider.
    Refuses to overwrite existing files.
    """
    path = Path(destination).expanduser().resolve()
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    svg_markup = scene_to_svg(scene)
    meta_json = escape(json.dumps(report, indent=2))
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(scene.document.get("title", "Dorothy Interactive Atlas"))}</title>
<style>
  body {{ margin: 0; background: #09111f; color: #e7edf5; font-family: monospace; display: flex; height: 100vh; overflow: hidden; }}
  #viewport {{ flex: 1; display: flex; align-items: center; justify-content: center; overflow: auto; padding: 16px; }}
  #sidebar {{ width: 360px; background: #111e31; border-left: 2px solid #ef445a; padding: 18px; overflow-y: auto; }}
  h1 {{ color: #ef445a; font-size: 18px; margin-top: 0; }}
  .badge {{ color: #e7c77b; font-size: 13px; margin-bottom: 12px; }}
  input[type=range] {{ width: 100%; accent-color: #62dce8; }}
  pre {{ font-size: 11px; color: #9cafc4; background: #080d18; padding: 10px; border-radius: 4px; overflow-x: auto; }}
</style>
</head>
<body>
  <div id="viewport">{svg_markup}</div>
  <div id="sidebar">
    <h1>ZOE / DOROTHY QUALIA HUD · ^_^</h1>
    <div class="badge">Scene SHA-256: {escape(scene.digest()[:16])}...</div>
    <label for="tau">Filtration Threshold &tau;: <span id="tau-val">0.15</span></label>
    <input id="tau" type="range" min="0" max="0.95" step="0.05" value="0.15"
      oninput="document.getElementById('tau-val').textContent=Number(this.value).toFixed(2)">
    <p style="font-size:12px;color:#62dce8;">Epistemic Firewall: measurement != evidence != belief update != clinical action</p>
    <pre>{meta_json}</pre>
  </div>
</body>
</html>
"""
    with path.open("x", encoding="utf-8") as stream:
        stream.write(html)
    return path

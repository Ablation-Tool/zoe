from __future__ import annotations

from copy import deepcopy
import math

from .atlas import _ellipse, _scene, _text
from .geometry import object_bounds
from .model import Scene


BACKGROUND = "#080d18"
PANEL = "#101b2b"
INK = "#e2e8f0"
MUTED = "#9fb1c8"
CYAN = "#67e8f9"
YELLOW = "#fde68a"
PINK = "#f0abfc"
GREEN = "#86efac"
FAINT = "#1e3a5f"


def _rectangle(identifier, bounds, stroke, fill, width=1):
    return {"id": identifier, "type": "rectangle", "bounds": bounds, "stroke": stroke, "fill": fill, "width": width}


def centered_text(identifier, x, y, text, size, color, max_width=1600):
    available = min(max_width, 2 * x, 2 * (1920 - x))
    if text:
        size = min(size, available / (len(text) * 0.62))
    return _text(identifier, [x - len(text) * size * 0.29, y], text, size, color)


def woven_diamond(identifier, center, radius, color):
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
        "stroke": color, "fill": BACKGROUND, "width": 2,
    })
    return objects


def starfield(count=96, width=1920, height=1200):
    objects = []
    for index in range(count):
        x = 41 + (index * 197) % (width - 80)
        y = 29 + (index * 109) % (height - 80)
        objects.append(_ellipse(f"style-star-{index}", [x, y], [1.4, 1.4], FAINT, FAINT))
    return objects


def _background_like(item, width, height):
    if item["type"] != "rectangle":
        return False
    left, top, right, bottom = item["bounds"]
    return (
        abs(left) < 0.01 and abs(top) < 0.01
        and abs(right - width) < 0.01 and abs(bottom - height) < 0.01
        and item["fill"].casefold() in {BACKGROUND, "black", "white", "#000000", "#ffffff"}
    )


def _color(value, role):
    if value == "none":
        return value
    lowered = value.casefold()
    if role == "text" and lowered in {"black", "#000000", "#111827", "#0f172a", "#172033", "#1f2937", "#334155"}:
        return INK
    if role == "stroke" and lowered in {"black", "#000000", "gray", "#808080", "lightgray", "#d3d3d3", "#64748b"}:
        return "#475569"
    if role == "fill" and lowered in {"white", "#ffffff", "#f8fafc", "#f3f0e9", "lightgray", "#d3d3d3"}:
        return PANEL
    if lowered == "blue":
        return CYAN
    if lowered == "orange":
        return YELLOW
    if lowered == "red":
        return PINK
    if lowered == "green":
        return GREEN
    return value


def _transform_item(item, scale, dx, dy):
    result = deepcopy(item)
    kind = result["type"]
    if kind == "rectangle":
        left, top, right, bottom = result["bounds"]
        result["bounds"] = [left * scale + dx, top * scale + dy, right * scale + dx, bottom * scale + dy]
    elif kind in {"polygon", "polyline", "line", "mesh"}:
        result["points"] = [[x * scale + dx, y * scale + dy] for x, y in result["points"]]
    elif kind == "ellipse":
        x, y = result["center"]
        rx, ry = result["radii"]
        result["center"] = [x * scale + dx, y * scale + dy]
        result["radii"] = [rx * scale, ry * scale]
    elif kind == "text":
        x, y = result["position"]
        result["position"] = [x * scale + dx, y * scale + dy]
        result["size"] = result["size"] * scale
        result["stroke"] = _color(result["stroke"], "text")
    if kind != "text":
        result["stroke"] = _color(result["stroke"], "stroke")
        result["fill"] = _color(result["fill"], "fill")
    result["width"] = max(0.5, result["width"] * scale)
    return result


def process_scene(title, steps, center_label, palette=None):
    palette = palette or [CYAN, PINK, YELLOW, GREEN]
    cx, cy, radius_x, radius_y = 700, 450, 500, 320
    objects = [
        _ellipse("process-outer", [cx, cy], [radius_x, radius_y], "#475569", "none", 1.2),
        _ellipse("process-inner", [cx, cy], [radius_x * 0.66, radius_y * 0.66], "#1e3a5f", "none", 1),
    ]
    count = len(steps)
    points = []
    for index, label in enumerate(steps):
        angle = -math.pi / 2 + math.tau * index / count
        x = cx + radius_x * math.cos(angle)
        y = cy + radius_y * math.sin(angle)
        color = palette[index % len(palette)]
        points.append([x, y])
        objects.append(_ellipse(f"process-halo-{index}", [x, y], [15, 15], color, "#080d18", 1))
        objects.append(_ellipse(f"process-node-{index}", [x, y], [7, 7], color, color))
        label_x = cx + radius_x * 1.24 * math.cos(angle)
        label_y = cy + radius_y * 1.24 * math.sin(angle)
        objects.append(centered_text(f"process-label-{index}", label_x, label_y + 6, label, 17, "#e2e8f0"))
        objects.append(centered_text(f"process-number-{index}", label_x, label_y - 17, f"{index + 1:02d}", 11, color))
    for index in range(count):
        start = points[index]
        end = points[(index + 1) % count]
        objects.append({
            "id": f"process-direction-{index}", "type": "polyline",
            "points": [start, end], "stroke": "#475569", "fill": "none", "width": 1,
        })
    objects.extend(woven_diamond("process-emblem", [cx, cy], 112, "#f87171"))
    objects.append(centered_text("process-center", cx, cy + 9, center_label, 25, "#e2e8f0"))
    return _scene("zoe-process", 1400, 900, objects, title)


def normalize_scene(scene, subtitle, footer):
    width, height = scene.canvas["width"], scene.canvas["height"]
    content = [item for item in scene.objects if not _background_like(item, width, height)]
    if not content:
        raise ValueError("visual normalization requires scene content")
    bounds = [object_bounds(item) for item in content]
    minimum_x = min(item.left for item in bounds)
    minimum_y = min(item.top for item in bounds)
    maximum_x = max(item.right for item in bounds)
    maximum_y = max(item.bottom for item in bounds)
    content_width = max(1, maximum_x - minimum_x)
    content_height = max(1, maximum_y - minimum_y)
    scale = min(1.3, 1640 / content_width, 810 / content_height)
    dx = 140 + (1640 - content_width * scale) / 2 - minimum_x * scale
    dy = 190 + (810 - content_height * scale) / 2 - minimum_y * scale
    objects = [_rectangle("style-background", [0, 0, 1920, 1200], BACKGROUND, BACKGROUND)]
    objects.extend(starfield())
    objects.extend([
        centered_text("style-title", 960, 76, scene.document.get("title", scene.document["id"]), 42, INK),
        centered_text("style-subtitle", 960, 116, subtitle, 15, CYAN),
        {"id": "style-header-rule", "type": "polyline", "points": [[650, 158], [1270, 158]], "stroke": FAINT, "fill": "none", "width": 1},
        _rectangle("style-content-frame", [48, 185, 1872, 1005], FAINT, "none", 1),
        _ellipse("style-content-orbit", [960, 595], [590, 350], "#12233c", "none", 1),
    ])
    objects.extend(_transform_item(item, scale, dx, dy) for item in content)
    objects.extend([
        centered_text("style-footer", 960, 1080, footer, 15, INK),
        centered_text("style-loop", 960, 1120, "SENSE  →  MODEL  →  IMAGINE  →  DOUBT  →  CHOOSE  →  ACT  →  LEARN", 13, MUTED),
        centered_text("style-control", 960, 1154, "ONE REPOSITORY · ONE KNOWLEDGE FIELD · HUMAN CONTROL", 11, MUTED),
    ])
    document = {
        "schema_version": 1,
        "id": scene.document["id"],
        "title": scene.document.get("title", scene.document["id"]),
        "canvas": {"width": 1920, "height": 1200},
        "objects": objects,
        "constraints": deepcopy(scene.constraints),
    }
    return Scene.from_dict(document)

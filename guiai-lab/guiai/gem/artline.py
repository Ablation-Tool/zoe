from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .field import _canonical
from .geometry import verify
from .model import Scene
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


def _scene(identifier, width, height, objects, title):
    return Scene.from_dict({
        "schema_version": 1,
        "id": identifier,
        "title": title,
        "canvas": {"width": width, "height": height},
        "objects": objects,
        "constraints": [{"type": "inside_canvas", "object": "*"}],
    })


def _ellipse(identifier, center, radii, stroke, fill="none", width=1):
    return {"id": identifier, "type": "ellipse", "center": center, "radii": radii, "stroke": stroke, "fill": fill, "width": width}


def _text(identifier, position, text, size=14, stroke="black"):
    return {"id": identifier, "type": "text", "position": position, "text": text, "size": size, "stroke": stroke, "fill": "none", "width": 0}


CANVAS = (1000, 700)
ELEMENT_TYPES = {"rectangle", "rounded_rectangle", "ellipse", "path", "line", "text"}
COLORS = {"none", "white", "black", "red", "green", "blue", "cyan", "yellow", "magenta", "orange", "gray", "lightgray"}
ELEMENT_FIELDS = {"id", "type", "layer", "group", "fill", "stroke", "width", "bounds", "center", "radii", "points", "position", "text", "size", "radius", "closed", "smooth"}
LAYER_FIELDS = {"id", "name", "visible", "locked"}
TOP_FIELDS = {"schema_version", "instrument", "canvas", "elements", "layers", "current_layer", "next_element", "next_group", "next_layer", "events"}
EVENT_FIELDS = {"sequence", "kind", "payload", "previous_hash", "hash"}


def _number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    result = float(value)
    if positive and result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _color(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a color")
    if value in COLORS:
        return value
    if len(value) == 7 and value.startswith("#") and all(character in "0123456789abcdefABCDEF" for character in value[1:]):
        return value
    raise ValueError(f"unsupported color: {value}")


def _point(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must have two coordinates")
    return [_number(value[0], f"{label}.x"), _number(value[1], f"{label}.y")]


def _points(value, label, minimum=2):
    if not isinstance(value, (list, tuple)) or not minimum <= len(value) <= 256:
        raise ValueError(f"{label} requires {minimum}-256 points")
    return [_point(point, f"{label}[{index}]") for index, point in enumerate(value)]


def _bounds(points):
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _inside(bounds):
    if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > CANVAS[0] or bounds[3] > CANVAS[1]:
        raise ValueError("element must remain inside the canvas")


def _smooth(points, closed):
    if len(points) < 3:
        return deepcopy(points)
    if closed:
        extended = [points[-1], *points, points[0], points[1]]
    else:
        extended = [points[0], *points, points[-1]]
    result = []
    for index in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[index - 1:index + 3]
        for step in range(12):
            t = step / 12
            result.append([
                0.5 * (
                    2 * p1[axis]
                    + (p2[axis] - p0[axis]) * t
                    + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t ** 2
                    + (3 * p1[axis] - 3 * p2[axis] + p3[axis] - p0[axis]) * t ** 3
                )
                for axis in range(2)
            ])
    if not closed:
        result.append(deepcopy(points[-1]))
    return result


def _rounded(bounds, radius):
    left, top, right, bottom = bounds
    radius = min(radius, (right - left) / 2, (bottom - top) / 2)
    if radius == 0:
        return [[left, top], [right, top], [right, bottom], [left, bottom]]
    points = []
    corners = [
        (left + radius, top + radius, math.pi, 1.5 * math.pi),
        (right - radius, top + radius, 1.5 * math.pi, 2 * math.pi),
        (right - radius, bottom - radius, 0, 0.5 * math.pi),
        (left + radius, bottom - radius, 0.5 * math.pi, math.pi),
    ]
    for cx, cy, start, end in corners:
        for step in range(9):
            angle = start + (end - start) * step / 8
            points.append([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
    return points


def _center(element):
    bounds = element_bounds(element)
    return [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]


def element_bounds(element):
    kind = element["type"]
    if kind in {"rectangle", "rounded_rectangle"}:
        return list(element["bounds"])
    if kind == "ellipse":
        cx, cy = element["center"]
        rx, ry = element["radii"]
        return [cx - rx, cy - ry, cx + rx, cy + ry]
    if kind in {"path", "line"}:
        return _bounds(element["points"])
    x, y = element["position"]
    size = element["size"]
    return [x, y - size, x + max(1, len(element["text"])) * size * 0.62, y + size * 0.2]


def _distance(point, first, second):
    dx, dy = second[0] - first[0], second[1] - first[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return math.hypot(point[0] - first[0], point[1] - first[1])
    fraction = max(0, min(1, ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / length_squared))
    return math.hypot(point[0] - first[0] - fraction * dx, point[1] - first[1] - fraction * dy)


def _in_polygon(point, points):
    x, y = point
    inside = False
    for index, first in enumerate(points):
        second = points[(index + 1) % len(points)]
        if (first[1] > y) != (second[1] > y) and x < (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]:
            inside = not inside
    return inside


def _signed_area(points):
    area = 0.0
    for i, p0 in enumerate(points):
        p1 = points[(i + 1) % len(points)]
        area += p0[0] * p1[1] - p1[0] * p0[1]
    return 0.5 * area


def _resample_closed_polygon(points, n_samples=48):
    """Resample a closed polygon uniformly by arc length so dissimilar shapes blend cleanly."""
    segs = []
    total = 0.0
    for i, p0 in enumerate(points):
        p1 = points[(i + 1) % len(points)]
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        segs.append((p0, p1, length))
        total += length
    if total <= 1e-9:
        return [list(points[0]) for _ in range(n_samples)]
    out = []
    step = total / n_samples
    seg_idx, acc = 0, 0.0
    for k in range(n_samples):
        target = k * step
        while seg_idx < len(segs) - 1 and acc + segs[seg_idx][2] < target:
            acc += segs[seg_idx][2]
            seg_idx += 1
        p0, p1, seg_len = segs[seg_idx]
        frac = 0.0 if seg_len <= 1e-9 else max(0.0, min(1.0, (target - acc) / seg_len))
        out.append([p0[0] + (p1[0] - p0[0]) * frac, p0[1] + (p1[1] - p0[1]) * frac])
    return out


def blend_polygons(start_pts, end_pts, steps=12, n_samples=48, auto_align=True, reverse_end=False):
    """Digital Research Artline 2.0 Point-Mapped Blend with Winding & Start-Point Alignment (pp. 8-10/8-11)."""
    a = _resample_closed_polygon(start_pts, n_samples=n_samples)
    b = _resample_closed_polygon(end_pts, n_samples=n_samples)
    if auto_align and (_signed_area(a) * _signed_area(b) < 0):
        b = list(reversed(b))
    if reverse_end:
        b = list(reversed(b))
    if auto_align:
        best_shift = min(
            range(n_samples),
            key=lambda sh: sum((a[i][0] - b[(i + sh) % n_samples][0]) ** 2 + (a[i][1] - b[(i + sh) % n_samples][1]) ** 2 for i in range(n_samples)),
        )
        b = b[best_shift:] + b[:best_shift]
    frames = []
    for s in range(steps + 1):
        t = s / max(1, steps)
        frames.append([[a[i][0] + (b[i][0] - a[i][0]) * t, a[i][1] + (b[i][1] - a[i][1]) * t] for i in range(n_samples)])
    return frames


def _rdp_simplify(points, eps):
    """Ramer-Douglas-Peucker polyline simplifier (Artline 2.0 tracing precision control)."""
    if len(points) <= 2:
        return list(points)
    p0, p1 = points[0], points[-1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    denom = math.hypot(dx, dy)
    best_idx, best_d = 0, -1.0
    for idx in range(1, len(points) - 1):
        px, py = points[idx]
        d = math.hypot(px - p0[0], py - p0[1]) if denom <= 1e-9 else abs(dy * px - dx * py + p1[0] * p0[1] - p1[1] * p0[0]) / denom
        if d > best_d:
            best_d, best_idx = d, idx
    if best_d > eps:
        left = _rdp_simplify(points[: best_idx + 1], eps)
        right = _rdp_simplify(points[best_idx:], eps)
        return left[:-1] + right
    return [p0, p1]


def autotrace_bitmap(mask, *, precision=2.0):
    """Artline 2.0 deterministic raster-to-vector Autotrace (Moore-Neighbor + RDP simplification).

    Zero neural networks, zero GPU: extracts a crisp repeatable polygon contour from any 2D
    binary raster mask (MRI slice, dithered scan, or 1-bit sprite) with Green's-theorem metrics.
    """
    h = len(mask)
    w = len(mask[0]) if h else 0
    if h == 0 or w == 0:
        raise ValueError("Empty raster mask for autotrace.")
    # Pad by 1px border so Moore-Neighbor lookup never goes out of bounds
    grid = [[0] * (w + 2)] + [[0] + [1 if mask[r][c] else 0 for c in range(w)] + [0] for r in range(h)] + [[0] * (w + 2)]
    start = None
    for r in range(1, h + 1):
        for c in range(1, w + 1):
            if grid[r][c] == 1:
                start = (r, c)
                break
        if start is not None:
            break
    if start is None:
        raise ValueError("Cannot find tracing image in raster mask.")

    # Clockwise 8-connected Moore neighborhood: (dr, dc) starting from West
    nbrs = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]
    cur = start
    enter_dir = 0  # Backtrack pixel is West of start (guaranteed 0 by scan order)
    raw = [[float(cur[1] - 1), float(cur[0] - 1)]]
    max_steps = max(64, 4 * h * w)
    for _ in range(max_steps):
        found = None
        for offset in range(1, 9):
            d = (enter_dir + offset) % 8
            nr, nc = cur[0] + nbrs[d][0], cur[1] + nbrs[d][1]
            if grid[nr][nc] == 1:
                prev_d = (d - 1) % 8
                # Direction from new pixel back to the last 0 pixel (opposite of offset)
                back_r = cur[0] + nbrs[prev_d][0] - nr
                back_c = cur[1] + nbrs[prev_d][1] - nc
                new_enter = nbrs.index((back_r, back_c)) if (back_r, back_c) in nbrs else (d + 4) % 8
                found = ((nr, nc), new_enter)
                break
        if found is None:
            break
        nxt, nxt_enter = found
        if nxt == start and nxt_enter == 0:
            break
        cur, enter_dir = nxt, nxt_enter
        raw.append([float(cur[1] - 1), float(cur[0] - 1)])

    # Closed RDP: split at farthest point from raw[0] so closed loop simplifies symmetrically
    if len(raw) >= 6:
        far_i = max(range(1, len(raw)), key=lambda i: (raw[i][0] - raw[0][0]) ** 2 + (raw[i][1] - raw[0][1]) ** 2)
        h1 = _rdp_simplify(raw[: far_i + 1], precision)
        h2 = _rdp_simplify(raw[far_i:] + [raw[0]], precision)
        traced = h1[:-1] + h2[:-1]
    else:
        traced = list(raw)

    area = abs(_signed_area(traced))
    perim = sum(math.hypot(traced[(i + 1) % len(traced)][0] - traced[i][0], traced[(i + 1) % len(traced)][1] - traced[i][1]) for i in range(len(traced)))
    circ = (4.0 * math.pi * area / (perim * perim)) if perim > 1e-9 else 0.0
    xs = [p[0] for p in traced]
    ys = [p[1] for p in traced]
    return {
        "contour": traced,
        "raw_points": len(raw),
        "traced_points": len(traced),
        "area": round(area, 2),
        "perimeter": round(perim, 2),
        "circularity": round(circ, 4),
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
    }


def trace_segment(contour, p_start, p_end, *, frame_bounds=None):
    """Artline 2.0 Trace Segment (p. 11-11): extract partial boundary arc between start & end points."""
    if frame_bounds is not None:
        fx0, fy0, fx1, fy1 = frame_bounds
        if not (fx0 <= p_end[0] <= fx1 and fy0 <= p_end[1] <= fy1):
            raise ValueError("Cannot trace segment. The selected end point lies outside the image frame.")
    if len(contour) < 3:
        return list(contour)
    i0 = min(range(len(contour)), key=lambda i: (contour[i][0] - p_start[0]) ** 2 + (contour[i][1] - p_start[1]) ** 2)
    i1 = min(range(len(contour)), key=lambda i: (contour[i][0] - p_end[0]) ** 2 + (contour[i][1] - p_end[1]) ** 2)
    if i0 == i1:
        return [list(contour[i0])]
    fwd = contour[i0 : i1 + 1] if i0 < i1 else contour[i0:] + contour[: i1 + 1]
    bwd = list(reversed(contour[i1 : i0 + 1])) if i1 < i0 else list(reversed(contour[i1:] + contour[: i0 + 1]))
    len_f = sum(math.hypot(fwd[k + 1][0] - fwd[k][0], fwd[k + 1][1] - fwd[k][1]) for k in range(len(fwd) - 1))
    len_b = sum(math.hypot(bwd[k + 1][0] - bwd[k][0], bwd[k + 1][1] - bwd[k][1]) for k in range(len(bwd) - 1))
    return fwd if len_f <= len_b else bwd


def rotate_ring(motif_pts, cx, cy, count=16):
    """Artline 2.0 Rotator + Thumbtack radial symmetry generator (Tutorial p. 6-14)."""
    if count < 2 or count > 64:
        raise ValueError("Ring count must be between 2 and 64.")
    ring = []
    for k in range(count):
        ang = 2.0 * math.pi * k / count
        ca, sa = math.cos(ang), math.sin(ang)
        ring.append([
            [cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca]
            for x, y in motif_pts
        ])
    return ring


def align_bounds_9way(bounds_list, mode="cc"):
    """Artline 2.0 ALIGN.TLS 9-way alignment pad (tl..br, top/mid/bot, left/center/right).

    Aligns all bounding boxes [x0, y0, x1, y1] against the first anchor box cleanly (P^2 = P).
    """
    if not bounds_list:
        return []
    ax0, ay0, ax1, ay1 = bounds_list[0]
    acx, acy = 0.5 * (ax0 + ax1), 0.5 * (ay0 + ay1)
    m = mode.strip().lower()
    h_map = {"tl": "l", "ml": "l", "bl": "l", "left": "l", "tc": "c", "cc": "c", "bc": "c", "center": "c", "tr": "r", "mr": "r", "br": "r", "right": "r"}
    v_map = {"tl": "t", "tc": "t", "tr": "t", "top": "t", "ml": "m", "cc": "m", "mr": "m", "mid": "m", "bl": "b", "bc": "b", "br": "b", "bot": "b"}
    hm, vm = h_map.get(m), v_map.get(m)
    if hm is None and vm is None:
        raise ValueError(f"Unknown ALIGN.TLS mode: {mode!r}")
    out = []
    for x0, y0, x1, y1 in bounds_list:
        w, h = x1 - x0, y1 - y0
        nx0 = x0 if hm is None else (ax0 if hm == "l" else (ax1 - w if hm == "r" else acx - 0.5 * w))
        ny0 = y0 if vm is None else (ay0 if vm == "t" else (ay1 - h if vm == "b" else acy - 0.5 * h))
        out.append([round(nx0, 3), round(ny0, 3), round(nx0 + w, 3), round(ny0 + h, 3)])
    return out


class ArtlineDocument:
    def __init__(self):
        self.elements = []
        self.layers = [{"id": "layer-1", "name": "Layer 1", "visible": True, "locked": False}]
        self.current_layer = "layer-1"
        self.next_element = 1
        self.next_group = 1
        self.next_layer = 2
        self.events = []
        self.history = []
        self.future = []

    def _record(self, kind, payload):
        if len(self.events) >= 4096:
            raise ValueError("Artline event bound reached")
        event = {
            "sequence": len(self.events) + 1,
            "kind": kind,
            "payload": deepcopy(payload),
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        self.events.append(event)

    def _state(self):
        return deepcopy({
            "elements": self.elements,
            "layers": self.layers,
            "current_layer": self.current_layer,
            "next_element": self.next_element,
            "next_group": self.next_group,
            "next_layer": self.next_layer,
        })

    def _restore(self, state):
        for key, value in state.items():
            setattr(self, key, deepcopy(value))

    def _checkpoint(self):
        self.history.append(self._state())
        if len(self.history) > 32:
            self.history.pop(0)
        self.future.clear()

    def undo(self):
        if not self.history:
            raise ValueError("nothing to undo")
        self.future.append(self._state())
        self._restore(self.history.pop())
        self._record("undo", {"remaining": len(self.history)})

    def redo(self):
        if not self.future:
            raise ValueError("nothing to redo")
        self.history.append(self._state())
        self._restore(self.future.pop())
        self._record("redo", {"remaining": len(self.future)})

    def element(self, identifier):
        for element in self.elements:
            if element["id"] == identifier:
                return element
        raise ValueError(f"unknown element: {identifier}")

    def layer(self, identifier):
        for layer in self.layers:
            if layer["id"] == identifier:
                return layer
        raise ValueError(f"unknown layer: {identifier}")

    def _editable(self, identifier):
        layer = self.layer(identifier)
        if layer["locked"] or not layer["visible"]:
            raise ValueError("the active layer is locked or hidden")
        return layer

    def add_layer(self, name=None):
        if len(self.layers) >= 64:
            raise ValueError("Artline supports at most 64 layers")
        identifier = f"layer-{self.next_layer}"
        name = name or f"Layer {self.next_layer}"
        if not isinstance(name, str) or not name.strip() or len(name) > 128:
            raise ValueError("layer name must contain 1-128 characters")
        self._checkpoint()
        self.layers.append({"id": identifier, "name": name.strip(), "visible": True, "locked": False})
        self.current_layer = identifier
        self.next_layer += 1
        self._record("layer_added", {"id": identifier, "name": name.strip()})
        return identifier

    def remove_layer(self, identifier):
        self.layer(identifier)
        if len(self.layers) == 1:
            raise ValueError("the last layer cannot be removed")
        if any(element["layer"] == identifier for element in self.elements):
            raise ValueError("remove or move the layer's elements first")
        self._checkpoint()
        self.layers = [layer for layer in self.layers if layer["id"] != identifier]
        if self.current_layer == identifier:
            self.current_layer = self.layers[0]["id"]
        self._record("layer_removed", {"id": identifier})

    def set_layer(self, identifier):
        self.layer(identifier)
        self._checkpoint()
        self.current_layer = identifier
        self._record("layer_activated", {"id": identifier})

    def set_layer_visible(self, identifier, visible):
        self._checkpoint()
        self.layer(identifier)["visible"] = bool(visible)
        self._record("layer_visibility", {"id": identifier, "visible": bool(visible)})

    def set_layer_locked(self, identifier, locked):
        self._checkpoint()
        self.layer(identifier)["locked"] = bool(locked)
        self._record("layer_lock", {"id": identifier, "locked": bool(locked)})

    def _validate_element(self, element, editing=True):
        if not isinstance(element, dict) or set(element) - ELEMENT_FIELDS:
            raise ValueError("element contains unsupported fields")
        kind = element.get("type")
        if kind not in ELEMENT_TYPES:
            raise ValueError("unsupported element type")
        layer = self.layer(element.get("layer"))
        if editing and (layer["locked"] or not layer["visible"]):
            raise ValueError("the active layer is locked or hidden")
        required = {
            "rectangle": {"bounds"}, "rounded_rectangle": {"bounds"},
            "ellipse": {"center", "radii"}, "path": {"points"},
            "line": {"points"}, "text": {"position", "text"},
        }
        if not required[kind] <= set(element):
            raise ValueError(f"{kind} is missing required geometry")
        if element.get("group") is not None and (not isinstance(element["group"], str) or not 1 <= len(element["group"]) <= 128):
            raise ValueError("group must be a short identifier")
        element["fill"] = _color(element.get("fill", "none"), "fill")
        element["stroke"] = _color(element.get("stroke", "black"), "stroke")
        width = _number(element.get("width", 1), "width", positive=True)
        if width > 128:
            raise ValueError("width exceeds 128")
        element["width"] = width
        if kind in {"rectangle", "rounded_rectangle"}:
            bounds = element["bounds"]
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
                raise ValueError("rectangle bounds must have four coordinates")
            element["bounds"] = [_number(value, "bounds") for value in bounds]
            if element["bounds"][2] <= element["bounds"][0] or element["bounds"][3] <= element["bounds"][1]:
                raise ValueError("rectangle bounds must have positive width and height")
            if kind == "rounded_rectangle":
                element["radius"] = _number(element.get("radius", 12), "radius")
                if element["radius"] < 0:
                    raise ValueError("radius cannot be negative")
        elif kind == "ellipse":
            element["center"] = _point(element["center"], "center")
            element["radii"] = _point(element["radii"], "radii")
            if any(value <= 0 for value in element["radii"]):
                raise ValueError("ellipse radii must be positive")
        elif kind in {"path", "line"}:
            closed = element.get("closed", kind == "path")
            smooth = element.get("smooth", False)
            if not isinstance(closed, bool) or not isinstance(smooth, bool):
                raise ValueError("path closed and smooth properties must be booleans")
            element["closed"] = closed
            element["smooth"] = smooth
            element["points"] = _points(element["points"], "points", 3 if closed else 2)
            if kind == "line" and len(element["points"]) != 2:
                raise ValueError("line requires exactly two points")
        else:
            element["position"] = _point(element["position"], "position")
            if not isinstance(element.get("text"), str) or not 1 <= len(element["text"]) <= 500:
                raise ValueError("text must contain 1-500 characters")
            element["size"] = _number(element.get("size", 20), "size", positive=True)
        _inside(element_bounds(element))
        return element

    def restyle(self, identifiers, **style):
        identifiers = list(identifiers)
        if not identifiers:
            raise ValueError("select an element first")
        if set(style) - {"stroke", "fill", "width"}:
            raise ValueError("only stroke, fill, and width can be restyled")
        transformed = []
        for identifier in identifiers:
            original = self.element(identifier)
            self._editable(original["layer"])
            element = deepcopy(original)
            element.update(style)
            self._validate_element(element)
            transformed.append(element)
        self._checkpoint()
        by_id = {element["id"]: element for element in transformed}
        self.elements = [by_id.get(element["id"], element) for element in self.elements]
        self._record("elements_restyled", {"ids": identifiers, **style})

    def add_element(self, kind, **specification):
        if len(self.elements) >= 4096:
            raise ValueError("Artline element bound reached")
        identifier = f"element-{self.next_element}"
        element = {
            "id": identifier,
            "type": kind,
            "layer": specification.pop("layer", self.current_layer),
            "group": specification.pop("group", None),
            **specification,
        }
        self._validate_element(element)
        self._checkpoint()
        self.elements.append(element)
        self.next_element += 1
        self._record("element_added", {"id": identifier, "type": kind, "layer": element["layer"]})
        return deepcopy(element)

    def delete(self, identifiers):
        identifiers = set(identifiers)
        if not identifiers:
            raise ValueError("select an element first")
        for identifier in identifiers:
            self._editable(self.element(identifier)["layer"])
        self._checkpoint()
        self.elements = [element for element in self.elements if element["id"] not in identifiers]
        self._record("elements_deleted", {"ids": sorted(identifiers)})

    def duplicate(self, identifiers):
        identifiers = list(identifiers)
        if not identifiers:
            raise ValueError("select an element first")
        selected_groups = {self.element(identifier)["group"] for identifier in identifiers}
        selected_groups.discard(None)
        if len(selected_groups) > 1:
            raise ValueError("duplicate one group or ungrouped elements")
        if selected_groups:
            identifiers = self.grouped(identifiers)
        if len(self.elements) + len(identifiers) > 4096:
            raise ValueError("Artline element bound reached")
        for identifier in identifiers:
            self._editable(self.element(identifier)["layer"])
        originals = [self.element(identifier) for identifier in identifiers]
        self._checkpoint()
        copies = []
        for original in originals:
            element = deepcopy(original)
            element["id"] = f"element-{self.next_element}"
            self.next_element += 1
            self.elements.append(element)
            copies.append(element["id"])
        self._record("elements_duplicated", {"sources": identifiers, "ids": copies})
        return copies

    def group(self, identifiers):
        identifiers = set(identifiers)
        if not identifiers:
            raise ValueError("select an element first")
        for identifier in identifiers:
            self.element(identifier)
        self._checkpoint()
        identifier = f"group-{self.next_group}"
        self.next_group += 1
        for element in self.elements:
            if element["id"] in identifiers:
                element["group"] = identifier
        self._record("elements_grouped", {"group": identifier, "ids": sorted(identifiers)})
        return identifier

    def ungroup(self, identifiers):
        identifiers = set(identifiers)
        self._checkpoint()
        for element in self.elements:
            if element["id"] in identifiers:
                element["group"] = None
        self._record("elements_ungrouped", {"ids": sorted(identifiers)})

    def grouped(self, identifiers):
        groups = {self.element(identifier)["group"] for identifier in identifiers}
        groups.discard(None)
        if len(groups) > 1:
            raise ValueError("select one group or ungrouped elements")
        if not groups:
            return list(identifiers)
        group = groups.pop()
        return [element["id"] for element in self.elements if element["group"] == group]

    def reorder(self, identifiers, direction):
        identifiers = set(identifiers)
        if direction not in {"front", "back", "forward", "backward"}:
            raise ValueError("unknown stacking direction")
        self._checkpoint()
        selected = [element for element in self.elements if element["id"] in identifiers]
        others = [element for element in self.elements if element["id"] not in identifiers]
        if direction == "front":
            self.elements = others + selected
        elif direction == "back":
            self.elements = selected + others
        else:
            for element in selected:
                index = self.elements.index(element)
                target = index + (1 if direction == "forward" else -1)
                target = max(0, min(len(self.elements) - 1, target))
                self.elements.insert(target, self.elements.pop(index))
        self._record("elements_reordered", {"direction": direction, "ids": sorted(identifiers)})

    def transform(self, identifiers, dx=0, dy=0, scale=(1, 1), angle=0, flip=None, center=None):
        identifiers = list(identifiers)
        if not identifiers:
            raise ValueError("select an element first")
        sx, sy = _point(scale, "scale")
        dx, dy = _number(dx, "horizontal movement"), _number(dy, "vertical movement")
        angle = _number(angle, "rotation angle")
        center = _point(center, "transformation center") if center is not None else None
        if sx <= 0 or sy <= 0:
            raise ValueError("scale must be positive")
        if flip not in {None, "horizontal", "vertical"}:
            raise ValueError("flip must be horizontal or vertical")
        originals = [self.element(identifier) for identifier in identifiers]
        for original in originals:
            self._editable(original["layer"])
        transformed = [self._transform_element(element, dx, dy, (sx, sy), angle, flip, center) for element in originals]
        for element in transformed:
            _inside(element_bounds(element))
        self._checkpoint()
        by_id = {element["id"]: element for element in transformed}
        self.elements = [by_id.get(element["id"], element) for element in self.elements]
        self._record("elements_transformed", {"ids": identifiers, "dx": dx, "dy": dy, "scale": [sx, sy], "angle": angle, "flip": flip})

    def _transform_element(self, original, dx, dy, scale, angle, flip, center):
        element = deepcopy(original)
        sx, sy = scale
        cx, cy = center or _center(original)

        def mapped(point):
            x, y = (point[0] - cx) * sx, (point[1] - cy) * sy
            if flip == "horizontal":
                x = -x
            elif flip == "vertical":
                y = -y
            if angle:
                x, y = x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)
            return [x + cx + dx, y + cy + dy]

        kind = element["type"]
        if kind in {"rectangle", "rounded_rectangle", "ellipse"} and not angle:
            if kind == "ellipse":
                element["center"] = mapped(element["center"])
                element["radii"] = [element["radii"][0] * sx, element["radii"][1] * sy]
            else:
                left, top, right, bottom = original["bounds"]
                bounds = [mapped([left, top]), mapped([right, bottom])]
                element["bounds"] = [
                    min(bounds[0][0], bounds[1][0]), min(bounds[0][1], bounds[1][1]),
                    max(bounds[0][0], bounds[1][0]), max(bounds[0][1], bounds[1][1]),
                ]
                if kind == "rounded_rectangle":
                    element["radius"] = original.get("radius", 12) * min(sx, sy)
        elif kind in {"rectangle", "rounded_rectangle", "ellipse"}:
            if kind == "ellipse":
                points = [[original["center"][0] + original["radii"][0] * math.cos(index * math.tau / 64), original["center"][1] + original["radii"][1] * math.sin(index * math.tau / 64)] for index in range(64)]
            else:
                points = _rounded(original["bounds"], original.get("radius", 0)) if kind == "rounded_rectangle" else [[original["bounds"][0], original["bounds"][1]], [original["bounds"][2], original["bounds"][1]], [original["bounds"][2], original["bounds"][3]], [original["bounds"][0], original["bounds"][3]]]
            element["type"] = "path"
            element["points"] = [mapped(point) for point in points]
            element["closed"] = True
            element["smooth"] = False
            element.pop("bounds", None)
            element.pop("center", None)
            element.pop("radii", None)
            element.pop("radius", None)
        elif kind in {"path", "line"}:
            element["points"] = [mapped(point) for point in original["points"]]
        else:
            element["position"] = mapped(original["position"])
            element["size"] = original["size"] * math.sqrt(sx * sy)
        return element

    def align_to_grid(self, identifiers, spacing=20):
        spacing = _number(spacing, "grid spacing", positive=True)
        if spacing > 256:
            raise ValueError("grid spacing exceeds 256")
        originals = [self.element(identifier) for identifier in identifiers]
        if not originals:
            raise ValueError("select an element first")
        transformed = []
        for original in originals:
            self._editable(original["layer"])
            element = deepcopy(original)
            for key in ("bounds", "center", "position"):
                if key in element:
                    if key == "bounds":
                        element[key] = [round(value / spacing) * spacing for value in element[key]]
                    else:
                        element[key] = [round(value / spacing) * spacing for value in element[key]]
            if "radii" in element:
                element["radii"] = [max(spacing, round(value / spacing) * spacing) for value in element["radii"]]
            if "points" in element:
                element["points"] = [[round(x / spacing) * spacing, round(y / spacing) * spacing] for x, y in element["points"]]
            if element["type"] in {"rectangle", "rounded_rectangle"} and (element["bounds"][2] <= element["bounds"][0] or element["bounds"][3] <= element["bounds"][1]):
                raise ValueError("grid alignment collapsed an element")
            if element["type"] == "ellipse" and any(value <= 0 for value in element["radii"]):
                raise ValueError("grid alignment collapsed an ellipse")
            _inside(element_bounds(element))
            transformed.append(element)
        self._checkpoint()
        by_id = {element["id"]: element for element in transformed}
        self.elements = [by_id.get(element["id"], element) for element in self.elements]
        self._record("elements_aligned_to_grid", {"ids": [element["id"] for element in originals], "spacing": spacing})

    def align_points_plane(self, identifier, point_indices, axis="vert"):
        """Digital Research Artline 2.0 Plane Tool (Align Vert / Align Horiz) anchored to first selected point."""
        mode = str(axis or "vert").strip().lower()
        if mode not in {"vert", "horiz"}:
            raise ValueError("plane alignment axis must be 'vert' or 'horiz'")
        original = self.element(identifier)
        self._editable(original["layer"])
        if original["type"] not in {"path", "line"}:
            raise ValueError("plane point alignment requires a path or line element")
        pts = deepcopy(original["points"])
        selected = sorted({int(i) for i in point_indices})
        if len(selected) < 2 or selected[0] < 0 or selected[-1] >= len(pts):
            raise ValueError("select at least two valid point indices")
        anchor_idx = selected[0]  # First selected point (nearest element start)
        coord = 0 if mode == "vert" else 1
        anchor_val = pts[anchor_idx][coord]
        deltas = []
        for idx in selected:
            deltas.append(round(pts[idx][coord] - anchor_val, 4))
            pts[idx][coord] = anchor_val
        updated = deepcopy(original)
        updated["points"] = pts
        _inside(element_bounds(updated))
        self._checkpoint()
        self.elements = [updated if item["id"] == identifier else item for item in self.elements]
        rms = math.sqrt(sum(d * d for d in deltas) / len(deltas))
        payload = {"id": identifier, "axis": mode, "anchor_index": anchor_idx, "anchor_value": anchor_val, "indices": selected, "rms_drift": round(rms, 4)}
        self._record("points_aligned_plane", payload)
        return {"anchor_index": anchor_idx, "anchor_point": list(pts[anchor_idx]), "deltas": deltas, "rms_drift": round(rms, 4), "axis": mode}

    def align_points_vert(self, identifier, point_indices):
        """Align selected points vertically to the first selected point's X coordinate."""
        return self.align_points_plane(identifier, point_indices, axis="vert")

    def align_points_horiz(self, identifier, point_indices):
        """Align selected points horizontally to the first selected point's Y coordinate."""
        return self.align_points_plane(identifier, point_indices, axis="horiz")

    def merge(self, other):
        if not isinstance(other, ArtlineDocument):
            raise ValueError("merge requires an Artline document")
        if len(self.elements) + len(other.elements) > 4096 or len(self.layers) + len(other.layers) > 64:
            raise ValueError("merged document exceeds Artline bounds")
        snapshot = self._state()
        event_count = len(self.events)
        layer_map = {}
        group_map = {}
        try:
            for layer in other.layers:
                existing = next((item for item in self.layers if item["name"] == layer["name"]), None)
                if existing is None:
                    existing = {"id": f"layer-{self.next_layer}", "name": layer["name"], "visible": layer["visible"], "locked": layer["locked"]}
                    self.next_layer += 1
                    self.layers.append(existing)
                layer_map[layer["id"]] = existing["id"]
            for original in other.elements:
                element = deepcopy(original)
                element["id"] = f"element-{self.next_element}"
                self.next_element += 1
                element["layer"] = layer_map[element["layer"]]
                if element.get("group"):
                    if element["group"] not in group_map:
                        group_map[element["group"]] = f"group-{self.next_group}"
                        self.next_group += 1
                    element["group"] = group_map[element["group"]]
                self._validate_element(element, editing=False)
                self.elements.append(element)
            self._record("document_merged", {"elements": len(other.elements)})
        except (KeyError, TypeError, ValueError):
            self._restore(snapshot)
            del self.events[event_count:]
            raise
        self._checkpoint()

    def scene(self):
        objects = []
        for element in self.elements:
            if not self.layer(element["layer"])["visible"]:
                continue
            kind = element["type"]
            common = {"stroke": element["stroke"], "fill": element["fill"], "width": element["width"]}
            if kind in {"rectangle", "rounded_rectangle"}:
                if kind == "rectangle":
                    objects.append({"id": element["id"], "type": "rectangle", "bounds": element["bounds"], **common})
                else:
                    objects.append({"id": element["id"], "type": "polygon", "points": _rounded(element["bounds"], element.get("radius", 12)), **common})
            elif kind == "ellipse":
                objects.append(_ellipse(element["id"], element["center"], element["radii"], element["stroke"], element["fill"], element["width"]))
            elif kind in {"path", "line"}:
                points = _smooth(element["points"], element["closed"]) if element.get("smooth") else deepcopy(element["points"])
                objects.append({"id": element["id"], "type": "polygon" if element["closed"] else "polyline", "points": points, **common})
            else:
                objects.append(_text(element["id"], element["position"], element["text"], element["size"], element["stroke"]))
        return _scene("zoe-artline", *CANVAS, objects, "Zoe Artline · original vector workbench")

    def document(self):
        return {
            "schema_version": 1,
            "instrument": "zoe-artline",
            "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
            "elements": deepcopy(self.elements),
            "layers": deepcopy(self.layers),
            "current_layer": self.current_layer,
            "next_element": self.next_element,
            "next_group": self.next_group,
            "next_layer": self.next_layer,
            "events": deepcopy(self.events),
        }

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("Artline documents must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("document directory does not exist")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Artline document exceeds 8 MiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("instrument") != "zoe-artline" or set(data) != TOP_FIELDS:
            raise ValueError("unsupported Artline document")
        if data.get("canvas") != {"width": CANVAS[0], "height": CANVAS[1]}:
            raise ValueError("unsupported Artline canvas")
        document = cls()
        if not isinstance(data["layers"], list) or not 1 <= len(data["layers"]) <= 64 or not isinstance(data["elements"], list) or len(data["elements"]) > 4096 or not isinstance(data.get("events"), list) or len(data["events"]) > 4096:
            raise ValueError("invalid Artline document bounds")
        layer_ids = set()
        for layer in data["layers"]:
            if not isinstance(layer, dict) or set(layer) != LAYER_FIELDS:
                raise ValueError("invalid layer")
            if not isinstance(layer["id"], str) or not 1 <= len(layer["id"]) <= 128 or layer["id"] in layer_ids:
                raise ValueError("layer IDs must be unique")
            if not isinstance(layer["name"], str) or not 1 <= len(layer["name"]) <= 128 or not isinstance(layer["visible"], bool) or not isinstance(layer["locked"], bool):
                raise ValueError("invalid layer properties")
            layer_ids.add(layer["id"])
        document.layers = deepcopy(data["layers"])
        if data["current_layer"] not in layer_ids:
            raise ValueError("unknown current layer")
        document.current_layer = data["current_layer"]
        element_ids = set()
        for element in data["elements"]:
            if not isinstance(element, dict) or not isinstance(element.get("id"), str) or not 1 <= len(element["id"]) <= 128 or element["id"] in element_ids:
                raise ValueError("element IDs must be unique")
            document._validate_element(element, editing=False)
            element_ids.add(element["id"])
        document.elements = deepcopy(data["elements"])
        for key in ("next_element", "next_group", "next_layer"):
            if isinstance(data[key], bool) or not isinstance(data[key], int) or data[key] < 1:
                raise ValueError(f"invalid {key}")
            setattr(document, key, data[key])
        for event in data["events"]:
            if not isinstance(event, dict) or set(event) != EVENT_FIELDS or isinstance(event["sequence"], bool) or event["sequence"] != len(document.events) + 1 or event["previous_hash"] != (document.events[-1]["hash"] if document.events else None):
                raise ValueError("Artline hash-chain mismatch")
            if not isinstance(event["kind"], str) or not 1 <= len(event["kind"]) <= 128:
                raise ValueError("invalid Artline event kind")
            expected = hashlib.sha256(_canonical({key: value for key, value in event.items() if key != "hash"}).encode("utf-8")).hexdigest()
            if event["hash"] != expected:
                raise ValueError("Artline hash-chain mismatch")
            document.events.append(deepcopy(event))
        if len(document.events) > 4096:
            raise ValueError("Artline event bound reached")
        return document

    def export(self, path, kind=None, width=1200):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"svg", "png", "gem"}:
            raise ValueError("Artline export must be svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("export directory does not exist")
        scene = self.scene()
        if kind == "gem":
            report = verify_vdi(scene)
            if not report.passed:
                raise ValueError(report.text())
            write_metafile(scene, path)
        elif kind == "svg":
            report = verify(scene)
            if not report.passed:
                raise ValueError(report.text())
            write_svg(scene, path, width)
        else:
            report = verify(scene)
            if not report.passed:
                raise ValueError(report.text())
            write_png(scene, path, width)
        return path


def demo_document():
    document = ArtlineDocument()
    document.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#08111f", stroke="#20304a", width=1)
    document.add_element("text", position=[44, 74], text="Zoe Artline", size=38, stroke="#67e8f9", width=1)
    document.add_element("text", position=[46, 106], text="Attempt / observe / adjust · original vector study", size=16, stroke="#9fb1c8", width=1)
    for x in range(100, 1000, 100):
        document.add_element("line", points=[[x, 132], [x, 590]], stroke="#20304a", width=1)
    for y in range(140, 600, 80):
        document.add_element("line", points=[[70, y], [950, y]], stroke="#20304a", width=1)
    document.add_element("path", points=[[160, 536], [325, 166], [510, 516], [690, 174], [864, 500]], closed=False, smooth=True, stroke="#67e8f9", width=5, fill="none")
    document.add_element("ellipse", center=[160, 536], radii=[32, 32], fill="#fde68a", stroke="#fda4af", width=4)
    document.add_element("line", points=[[110, 570], [910, 570]], stroke="#86efac", width=4)
    document.add_element("path", points=[[112, 570], [138, 544], [166, 548], [190, 570]], closed=False, smooth=True, stroke="#f0abfc", width=4)
    document.add_element("text", position=[106, 622], text="throw", size=17, stroke="#fde68a", width=1)
    document.add_element("text", position=[435, 622], text="notice", size=17, stroke="#67e8f9", width=1)
    document.add_element("text", position=[766, 622], text="adjust", size=17, stroke="#86efac", width=1)
    document.add_element("rounded_rectangle", bounds=[392, 348, 516, 386], radius=12, fill="#101b2b", stroke="#f0abfc", width=1.5)
    document.add_element("text", position=[408, 374], text="practice is information", size=15, stroke="#f0abfc", width=1)
    return document

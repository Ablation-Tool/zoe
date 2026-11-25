from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ElementTree


NAMED_COLORS = {
    "white": "#ffffff",
    "black": "#000000",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
    "magenta": "#ff00ff",
    "orange": "#e95420",
    "gray": "#808080",
    "lightgray": "#d3d3d3",
}


def color(value):
    return NAMED_COLORS.get(value, value)


def _paint(item):
    return {
        "fill": color(item["fill"]),
        "stroke": color(item["stroke"]),
        "stroke-width": str(item["width"]),
    }


def _label(item):
    if not item.get("label") or item["type"] != "rectangle":
        return None
    left, top, right, bottom = item["bounds"]
    size = min(240, (bottom - top) / 3)
    return {
        "position": [(left + right) / 2, (top + bottom) / 2 + size * 0.35],
        "text": item["label"].replace("\n", " · "),
        "size": size,
        "centered": True,
    }


def scene_to_svg(scene, width=1200):
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 16384:
        raise ValueError("SVG width must be an integer from 1 to 16384")
    height = max(1, round(width * scene.canvas["height"] / scene.canvas["width"]))
    root = ElementTree.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": str(width),
        "height": str(height),
        "viewBox": f"0 0 {scene.canvas['width']:g} {scene.canvas['height']:g}",
        "role": "img",
        "aria-label": scene.document.get("title", scene.document["id"]),
    })
    ElementTree.SubElement(root, "title").text = scene.document.get("title", scene.document["id"])
    ElementTree.SubElement(root, "rect", {
        "x": "0", "y": "0", "width": str(scene.canvas["width"]),
        "height": str(scene.canvas["height"]), "fill": "#ffffff",
    })
    for item in scene.objects:
        paint = _paint(item)
        group = ElementTree.SubElement(root, "g", {"data-object-id": item["id"]})
        ElementTree.SubElement(group, "title").text = item["id"]
        if item["type"] == "rectangle":
            left, top, right, bottom = item["bounds"]
            ElementTree.SubElement(group, "rect", {
                "x": str(left), "y": str(top), "width": str(right - left),
                "height": str(bottom - top), **paint,
            })
        elif item["type"] in {"polygon", "polyline", "line"}:
            tag = "polygon" if item["type"] == "polygon" else "polyline"
            ElementTree.SubElement(group, tag, {
                "points": " ".join(f"{x:g},{y:g}" for x, y in item["points"]),
                "stroke-linejoin": "round", **paint,
            })
        elif item["type"] == "mesh":
            points, fills = item["points"], item["fills"]
            index = 0
            while index < len(fills):
                end = index + 1
                while end < len(fills) and fills[end] == fills[index]:
                    end += 1
                chunks = []
                for triangle in range(index, end):
                    corners = points[3 * triangle:3 * triangle + 3]
                    chunks.append("M" + "L".join(f"{x:g},{y:g}" for x, y in corners) + "Z")
                ElementTree.SubElement(group, "path", {
                    "d": "".join(chunks), "fill": color(fills[index]), "stroke": "none",
                })
                index = end
        elif item["type"] == "ellipse":
            ElementTree.SubElement(group, "ellipse", {
                "cx": str(item["center"][0]), "cy": str(item["center"][1]),
                "rx": str(item["radii"][0]), "ry": str(item["radii"][1]), **paint,
            })
        elif item["type"] == "text":
            ElementTree.SubElement(group, "text", {
                "x": str(item["position"][0]), "y": str(item["position"][1]),
                "font-family": "sans-serif", "font-size": str(item["size"]),
                "fill": color(item["stroke"]),
            }).text = item["text"]
        label = _label(item)
        if label is not None:
            ElementTree.SubElement(group, "text", {
                "x": str(label["position"][0]), "y": str(label["position"][1]),
                "font-family": "sans-serif", "font-size": str(label["size"]),
                "fill": color(item["stroke"]), "text-anchor": "middle",
            }).text = label["text"]
    ElementTree.indent(root, space="  ")
    return ElementTree.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def write_svg(scene, path, width=1200):
    text = scene_to_svg(scene, width)
    Path(path).write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def draw_cairo(context, scene, width, height, highlight_ids=()):
    import cairo

    scale = min(width / scene.canvas["width"], height / scene.canvas["height"])
    offset_x = (width - scene.canvas["width"] * scale) / 2
    offset_y = (height - scene.canvas["height"] * scale) / 2
    context.save()
    context.set_source_rgb(1, 1, 1)
    context.paint()
    context.translate(offset_x, offset_y)
    context.scale(scale, scale)
    context.set_line_join(cairo.LineJoin.ROUND)
    for item in scene.objects:
        if item["type"] == "rectangle":
            left, top, right, bottom = item["bounds"]
            context.rectangle(left, top, right - left, bottom - top)
        elif item["type"] in {"polygon", "polyline", "line"}:
            points = item["points"]
            context.move_to(*points[0])
            for point in points[1:]:
                context.line_to(*point)
            if item["type"] == "polygon":
                context.close_path()
        elif item["type"] == "mesh":
            points, fills = item["points"], item["fills"]
            index = 0
            while index < len(fills):
                end = index + 1
                while end < len(fills) and fills[end] == fills[index]:
                    end += 1
                rgb = color(fills[index]).lstrip("#")
                context.set_source_rgb(*(int(rgb[offset:offset + 2], 16) / 255 for offset in (0, 2, 4)))
                for triangle in range(index, end):
                    corners = points[3 * triangle:3 * triangle + 3]
                    context.move_to(*corners[0])
                    context.line_to(*corners[1])
                    context.line_to(*corners[2])
                    context.close_path()
                context.fill()
                index = end
            continue
        elif item["type"] == "ellipse":
            context.save()
            context.translate(*item["center"])
            context.scale(*item["radii"])
            context.new_sub_path()
            context.arc(0, 0, 1, 0, math.tau)
            context.restore()
        elif item["type"] == "text":
            context.select_font_face("sans-serif")
            context.set_font_size(item["size"])
            context.move_to(*item["position"])
            rgb = color(item["stroke"]).lstrip("#")
            context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
            context.show_text(item["text"])
            continue
        if item["fill"] != "none":
            rgb = color(item["fill"]).lstrip("#")
            context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
            context.fill_preserve()
        if item["stroke"] != "none":
            rgb = color(item["stroke"]).lstrip("#")
            context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
            context.set_line_width(item["width"])
            context.stroke()
        else:
            context.new_path()
        if item["id"] in highlight_ids:
            left, top, right, bottom = _highlight_bounds(item)
            context.set_source_rgb(0.9, 0.1, 0.1)
            context.set_line_width(max(item["width"] * 2, 50 / scale))
            context.set_dash([120, 60])
            context.rectangle(left - 30, top - 30, right - left + 60, bottom - top + 60)
            context.stroke()
            context.set_dash([])
        label = _label(item)
        if label is not None:
            context.select_font_face("sans-serif")
            context.set_font_size(label["size"])
            extents = context.text_extents(label["text"])
            context.move_to(
                label["position"][0] - extents.width / 2 - extents.x_bearing,
                label["position"][1],
            )
            rgb = color(item["stroke"]).lstrip("#")
            context.set_source_rgb(*(int(rgb[index:index + 2], 16) / 255 for index in (0, 2, 4)))
            context.show_text(label["text"])
    context.restore()
    return scale, offset_x, offset_y


def _highlight_bounds(item):
    from .geometry import object_bounds

    bounds = object_bounds(item)
    return bounds.left, bounds.top, bounds.right, bounds.bottom


def _pil_rgb(value):
    if not value or value == "none":
        return None
    hex_col = color(value).lstrip("#")
    if len(hex_col) == 3:
        hex_col = "".join(ch * 2 for ch in hex_col)
    if len(hex_col) != 6:
        return None
    return tuple(int(hex_col[i : i + 2], 16) for i in (0, 2, 4))


def _load_pil_font(px_size: int):
    from PIL import ImageFont

    size = max(8, int(round(px_size)))
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _write_png_pillow(scene, path, width, height):
    from PIL import Image, ImageDraw

    # Render at 2x supersampling and downsample with LANCZOS for crisp Cairo-grade anti-aliasing
    ss = 2 if max(width, height) <= 2400 else 1
    rw, rh = width * ss, height * ss
    cw = float(scene.canvas["width"])
    ch = float(scene.canvas["height"])
    sx = rw / cw if cw > 0 else 1.0
    sy = rh / ch if ch > 0 else 1.0
    sw = min(sx, sy)

    img = Image.new("RGB", (rw, rh), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for item in scene.objects:
        kind = item["type"]
        fill = _pil_rgb(item.get("fill"))
        stroke = _pil_rgb(item.get("stroke"))
        lw = max(1, int(round(float(item.get("width", 1.0)) * sw)))

        if kind == "rectangle":
            left, top, right, bottom = item["bounds"]
            box = [left * sx, top * sy, right * sx, bottom * sy]
            draw.rectangle(box, fill=fill, outline=stroke, width=lw if stroke else 0)
            label = _label(item)
            if label is not None and stroke is not None:
                font = _load_pil_font(int(round(label["size"] * sy)))
                draw.text(
                    (label["position"][0] * sx, label["position"][1] * sy),
                    label["text"],
                    fill=stroke,
                    font=font,
                    anchor="ms",
                )
        elif kind == "ellipse":
            cx, cy = item["center"]
            rx, ry = item["radii"]
            box = [(cx - rx) * sx, (cy - ry) * sy, (cx + rx) * sx, (cy + ry) * sy]
            draw.ellipse(box, fill=fill, outline=stroke, width=lw if stroke else 0)
        elif kind == "polygon":
            pts = [(x * sx, y * sy) for x, y in item["points"]]
            if len(pts) >= 3:
                if fill is not None:
                    draw.polygon(pts, fill=fill)
                if stroke is not None:
                    draw.line(pts + [pts[0]], fill=stroke, width=lw)
        elif kind in {"polyline", "line"}:
            pts = [(x * sx, y * sy) for x, y in item["points"]]
            if len(pts) >= 2 and (stroke is not None or fill is not None):
                draw.line(pts, fill=stroke or fill, width=lw)
        elif kind == "mesh":
            points, fills = item["points"], item["fills"]
            for tri_idx, fcol in enumerate(fills):
                rgb = _pil_rgb(fcol)
                if rgb is None:
                    continue
                corners = [(x * sx, y * sy) for x, y in points[3 * tri_idx : 3 * tri_idx + 3]]
                if len(corners) == 3:
                    draw.polygon(corners, fill=rgb)
        elif kind == "text":
            if stroke is not None:
                font = _load_pil_font(int(round(float(item["size"]) * sy)))
                x, y = item["position"]
                draw.text((x * sx, max(0.0, y * sy - float(item["size"]) * sy * 0.85)), item["text"], fill=stroke, font=font)

    if ss > 1:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), format="PNG")
    return out_path.stat().st_size


def write_png(scene, path, width=1200):
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 16384:
        raise ValueError("PNG width must be an integer from 1 to 16384")
    height = max(1, round(width * scene.canvas["height"] / scene.canvas["width"]))
    try:
        import cairo
    except ImportError:
        return _write_png_pillow(scene, path, width, height)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_cairo(cairo.Context(surface), scene, width, height)
    surface.write_to_png(str(path))
    return Path(path).stat().st_size

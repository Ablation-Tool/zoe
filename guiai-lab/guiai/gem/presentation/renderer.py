"""Pure-Python Presentation Renderer (`pycairo` + `Pillow` + `PangoCairo` + SVG).

Zero runtime dependency on LibreOffice (`soffice`), `pdftoppm`, or `python-pptx`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from guiai.gem import render as gem_render
from guiai.gem import vdi
from guiai.gem.model import Scene

if TYPE_CHECKING:
    from PIL import Image


@dataclass
class PresentationScene:
    """Rich presentation slide IR duck-typed to `guiai.gem.model.Scene` for `render.py`."""

    document: dict[str, Any]
    canvas: dict[str, float]
    objects: list[dict[str, Any]]
    background: str = "#ffffff"
    metadata: dict[str, Any] = field(default_factory=dict)


def _lower_to_scene(pres: PresentationScene) -> Scene:
    """Lower a `PresentationScene` to a strict `model.Scene` (`OBJECT_TYPES`/`OBJECT_FIELDS`)."""
    from guiai.gem import artline

    w = float(pres.canvas["width"])
    h = float(pres.canvas["height"])
    lowered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _unique_id(base: str) -> str:
        clean = "".join(ch if not ch.isspace() else "-" for ch in str(base))[:120] or "obj"
        cand = clean
        idx = 1
        while cand in seen_ids:
            idx += 1
            cand = f"{clean[:110]}-{idx}"
        seen_ids.add(cand)
        return cand

    for idx, item in enumerate(pres.objects):
        itype = item["type"]
        oid = _unique_id(item.get("id", f"item-{idx}"))
        fill = item.get("fill", "none")
        if int(item.get("fill_interior", 1)) == 0:
            fill = "none"
        stroke = item.get("stroke", "black")
        width = max(0.0, float(item.get("width", 20.0)))

        if itype == "rectangle":
            lowered.append({
                "id": oid,
                "type": "rectangle",
                "bounds": [float(v) for v in item["bounds"]],
                "fill": fill,
                "stroke": stroke,
                "width": width,
            })
        elif itype == "rounded_rectangle":
            r = float(item.get("radius", 0.0))
            if r > 0:
                pts = artline._rounded(item["bounds"], r)
                lowered.append({
                    "id": oid,
                    "type": "polygon",
                    "points": pts,
                    "fill": fill,
                    "stroke": stroke,
                    "width": width,
                })
            else:
                lowered.append({
                    "id": oid,
                    "type": "rectangle",
                    "bounds": [float(v) for v in item["bounds"]],
                    "fill": fill,
                    "stroke": stroke,
                    "width": width,
                })
        elif itype in {"polygon", "polyline", "line"}:
            pts = [[float(p[0]), float(p[1])] for p in item["points"]]
            if itype == "polygon" and len(pts) >= 3:
                lowered.append({
                    "id": oid, "type": "polygon", "points": pts,
                    "fill": fill, "stroke": stroke, "width": width,
                })
            elif itype == "line" and len(pts) == 2:
                lowered.append({
                    "id": oid, "type": "line", "points": pts,
                    "fill": "none", "stroke": stroke, "width": width,
                })
            elif len(pts) >= 2:
                lowered.append({
                    "id": oid, "type": "polyline", "points": pts,
                    "fill": "none", "stroke": stroke, "width": width,
                })
        elif itype == "ellipse":
            lowered.append({
                "id": oid,
                "type": "ellipse",
                "center": [float(item["center"][0]), float(item["center"][1])],
                "radii": [max(1.0, float(item["radii"][0])), max(1.0, float(item["radii"][1]))],
                "fill": fill,
                "stroke": stroke,
                "width": width,
            })
        elif itype in {"arc", "ellarc"}:
            cx, cy = (float(v) for v in item["center"])
            rx, ry = (float(v) for v in item["radii"])
            beg = int(round(float(item.get("begang", 0.0))))
            end = int(round(float(item.get("endang", 3600.0))))
            pts = vdi._sample_arc_points(cx, cy, rx, ry, beg, end, closed_pie=False)
            if len(pts) >= 2:
                lowered.append({
                    "id": oid,
                    "type": "line" if len(pts) == 2 else "polyline",
                    "points": pts,
                    "fill": "none",
                    "stroke": stroke,
                    "width": width,
                })
        elif itype in {"pieslice", "ellpie"}:
            cx, cy = (float(v) for v in item["center"])
            rx, ry = (float(v) for v in item["radii"])
            beg = int(round(float(item.get("begang", 0.0))))
            end = int(round(float(item.get("endang", 3600.0))))
            pts = vdi._sample_arc_points(cx, cy, rx, ry, beg, end, closed_pie=True)
            if len(pts) >= 3:
                lowered.append({
                    "id": oid,
                    "type": "polygon",
                    "points": pts,
                    "fill": fill,
                    "stroke": stroke,
                    "width": width,
                })
        elif itype == "image":
            lowered.append({
                "id": oid,
                "type": "rectangle",
                "bounds": [float(v) for v in item["bounds"]],
                "fill": fill if fill != "none" else "#ffffff",
                "stroke": stroke,
                "width": width,
            })
        elif itype == "text":
            sz = max(1.0, float(item.get("size", 240.0)))
            if "paragraphs" in item:
                txt = " ".join(
                    "".join(str(r.get("text", "")) for r in p.get("runs", []))
                    for p in item["paragraphs"]
                ).strip()
            else:
                txt = str(item.get("text", "")).replace("\n", " ").strip()
            if not txt:
                txt = " "
            txt = txt[:500]
            if "bounds" in item:
                bx0, by0, _bx1, _by1 = (float(v) for v in item["bounds"])
                pos = [bx0, by0 + sz * 0.85]
            else:
                pos = [float(item["position"][0]), float(item["position"][1])]
            lowered.append({
                "id": oid,
                "type": "text",
                "position": pos,
                "text": txt,
                "size": sz,
                "fill": "none",
                "stroke": stroke if stroke != "none" else "black",
                "width": 1.0,
            })

    return Scene.from_dict({
        "schema_version": 1,
        "id": str(pres.document.get("id", "presentation-slide")),
        "title": str(pres.document.get("title", "Zoe Presentation Slide"))[:500],
        "canvas": {"width": w, "height": h},
        "objects": lowered,
        "constraints": [],
    })


class PresentationRenderer:
    """Pure-Python renderer for `DrawPlusCanvas`, `PresentationScene`, and `Scene`."""

    def __init__(self, source: Any) -> None:
        self._source = source
        if hasattr(source, "to_presentation_scene"):
            self.presentation_scene: PresentationScene = source.to_presentation_scene()
        elif isinstance(source, PresentationScene):
            self.presentation_scene = source
        elif isinstance(source, Scene):
            self.presentation_scene = PresentationScene(
                document=dict(source.document),
                canvas=dict(source.canvas),
                objects=list(source.objects),
                background=str(source.document.get("background", "#ffffff")),
            )
        else:
            raise TypeError(f"Unsupported presentation source: {type(source).__name__}")

    def to_scene(self) -> Scene:
        if hasattr(self._source, "to_scene"):
            return self._source.to_scene()
        if isinstance(self._source, Scene):
            return self._source
        return _lower_to_scene(self.presentation_scene)

    def to_gem_bytes(self) -> bytes:
        if hasattr(self._source, "to_gem_bytes"):
            return self._source.to_gem_bytes()
        return vdi.scene_to_metafile(self.to_scene())

    def render_svg(self, path: Path | str | None = None, *, width: int = 1920) -> str:
        svg = gem_render.scene_to_svg(self.presentation_scene, width=width)
        if path is not None:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(svg, encoding="utf-8")
        return svg

    def render_pil(self, *, width: int = 1920, height: int = 1080) -> Image.Image:
        return gem_render.render_pil(self.presentation_scene, width=width, height=height)

    def render_png(self, path: Path | str, *, width: int = 1920, height: int = 1080) -> Path:
        out = Path(path)
        gem_render.write_png(self.presentation_scene, out, width=width, height=height)
        return out

    def render_jpg(self, path: Path | str, *, width: int = 1920, height: int = 1080, quality: int = 94) -> Path:
        out = Path(path)
        gem_render.write_jpg(self.presentation_scene, out, width=width, height=height, quality=quality)
        return out

    @staticmethod
    def measure_text(
        text: str,
        *,
        font_id: int | None = None,
        font_family: str = "DejaVu Sans",
        font_pt: float = 10.5,
        size_vdi: float | None = None,
        bold: bool = False,
        italic: bool = False,
        effects: int = 0,
        max_width_vdi: float | None = None,
        wrap: bool = True,
        line_spacing: float = 1.18,
    ) -> tuple[float, float, list[str]]:
        return gem_render.measure_text_metrics(
            text,
            font_id=font_id,
            font_family=font_family,
            font_pt=font_pt,
            size_vdi=size_vdi,
            bold=bold,
            italic=italic,
            effects=effects,
            max_width_vdi=max_width_vdi,
            wrap=wrap,
            line_spacing=line_spacing,
        )

    @staticmethod
    def measure_runs(
        runs: list[dict[str, Any]],
        *,
        font_id: int | None = None,
        font_family: str = "DejaVu Sans",
        size_vdi: float = 240.0,
        base_bold: bool = False,
        base_italic: bool = False,
        effects: int = 0,
        max_width_vdi: float | None = None,
        wrap: bool = True,
        line_spacing: float = 1.18,
    ) -> tuple[float, float, list[str]]:
        return gem_render.measure_runs_lines(
            runs,
            font_id=font_id,
            font_family=font_family,
            size_vdi=size_vdi,
            base_bold=base_bold,
            base_italic=base_italic,
            effects=effects,
            max_width_vdi=max_width_vdi,
            wrap=wrap,
            line_spacing=line_spacing,
        )


__all__ = ["PresentationRenderer", "PresentationScene"]

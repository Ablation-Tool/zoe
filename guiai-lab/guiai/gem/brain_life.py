from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .atlas import _ellipse, _scene, _text
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


RULES = "3D Moore 26 · B3/S23"


class BrainLife:
    def __init__(self, cells=(), size=10):
        if isinstance(size, bool) or not isinstance(size, int) or not 4 <= size <= 10:
            raise ValueError("Brain Life size must be an integer from 4 to 10")
        self.size = size
        self.cells = set()
        for cell in cells:
            if not isinstance(cell, (tuple, list)) or len(cell) != 3:
                raise ValueError("Brain Life cells must be three-dimensional coordinates")
            x, y, z = cell
            if any(isinstance(value, bool) or not isinstance(value, int) for value in cell):
                raise ValueError("Brain Life coordinates must be integers")
            if not 0 <= x < size or not 0 <= y < size or not 0 <= z < size:
                raise ValueError("Brain Life cell lies outside the bounded volume")
            self.cells.add((x, y, z))
        self.generation = 0

    @classmethod
    def from_brain(cls, size=10):
        cells = set()
        center = (size - 1) / 2
        for x in range(size):
            for y in range(size):
                for z in range(size):
                    distance = (
                        ((x - center) / (size * 0.45)) ** 2
                        + ((y - center) / (size * 0.37)) ** 2
                        + ((z - center) / (size * 0.43)) ** 2
                    )
                    if 0.48 <= distance <= 1.18 and not (x == size // 2 and y < size * 0.72):
                        cells.add((x, y, z))
        return cls(cells, size)

    @property
    def population(self):
        return len(self.cells)

    def toggle(self, x, y, z):
        cell = (x, y, z)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in cell):
            raise ValueError("Brain Life coordinates must be integers")
        if not all(0 <= value < self.size for value in cell):
            raise ValueError("Brain Life cell lies outside the bounded volume")
        if cell in self.cells:
            self.cells.remove(cell)
        else:
            self.cells.add(cell)

    def clear(self):
        self.cells.clear()
        self.generation = 0

    def step(self):
        neighbors = {}
        for x, y, z in self.cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        if not dx and not dy and not dz:
                            continue
                        cell = (x + dx, y + dy, z + dz)
                        if all(0 <= value < self.size for value in cell):
                            neighbors[cell] = neighbors.get(cell, 0) + 1
        self.cells = {
            cell for cell, count in neighbors.items()
            if count == 3 or count == 2 and cell in self.cells
        }
        self.generation += 1
        return self.cells

    def advance(self, count):
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 1000:
            raise ValueError("Brain Life steps must be an integer from 0 to 1000")
        for _ in range(count):
            self.step()
        return self

    def digest(self):
        state = {"size": self.size, "generation": self.generation, "cells": sorted(self.cells)}
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def document(self):
        return {
            "schema_version": 1,
            "instrument": "zoe-brain-life",
            "rules": RULES,
            "boundary": "finite non-wrapping volume",
            "size": self.size,
            "generation": self.generation,
            "population": self.population,
            "cells": sorted(self.cells),
            "state_sha256": self.digest(),
            "anatomical_brain": False,
            "biological_life_created": False,
            "external_actions_executed": False,
        }

    def scene(self, yaw=35):
        if isinstance(yaw, bool) or not isinstance(yaw, (int, float)) or not math.isfinite(yaw):
            raise ValueError("Brain Life yaw must be finite")
        angle = math.radians(yaw)
        center = (self.size - 1) / 2
        palette = ("#1d4ed8", "#2563eb", "#0e7490", "#0891b2", "#14b8a6", "#86efac")
        projected = []
        for x, y, z in self.cells:
            rx = (x - center) * math.cos(angle) - (y - center) * math.sin(angle)
            ry = (x - center) * math.sin(angle) + (y - center) * math.cos(angle)
            sx = 450 + (rx - ry) * 25
            sy = 365 + (rx + ry) * 12 - (z - center) * 25
            depth = rx + ry + z * 0.35
            projected.append((depth, sx, sy, z))
        objects = [{
            "id": "background", "type": "rectangle", "bounds": [0, 0, 1100, 740],
            "stroke": "#080d18", "fill": "#080d18", "width": 1,
        }]
        objects.extend([
            _text("title", [40, 51], "Zoe Brain Life", 31, "#67e8f9"),
            _text("subtitle", [42, 80], "Three-dimensional cellular automaton · illustrative voxel geometry", 15, "#d8e2ee"),
            _text("rules", [42, 106], f"{RULES} · finite volume · not anatomical data", 12, "#9fb1c8"),
        ])
        for index, (_depth, sx, sy, z) in enumerate(sorted(projected)):
            color = palette[min(len(palette) - 1, z * len(palette) // self.size)]
            objects.append(_ellipse(f"voxel-{index}", [sx, sy], [11, 8], color, color, 0.6))
        objects.append({
            "id": "metrics", "type": "rectangle", "bounds": [790, 132, 1060, 420],
            "stroke": "#475569", "fill": "#101b2b", "width": 1,
        })
        rows = (
            ("Generation", self.generation),
            ("Population", self.population),
            ("Volume", f"{self.size}³"),
            ("Neighbors", "26"),
            ("Yaw", f"{yaw:g}°"),
            ("State", self.digest()[:16]),
        )
        for index, (label, value) in enumerate(rows):
            objects.append(_text(f"metric-label-{index}", [812, 166 + index * 43], label, 12, "#9fb1c8"))
            objects.append(_text(f"metric-value-{index}", [812, 187 + index * 43], str(value), 17, "#d8e2ee"))
        objects.extend([
            _text("boundary-title", [792, 478], "Research boundary", 14, "#fda4af"),
            _text("boundary-1", [792, 505], "A mathematical voxel model,", 12, "#d8e2ee"),
            _text("boundary-2", [792, 527], "not anatomy or diagnosis.", 12, "#d8e2ee"),
            _text("controls", [792, 579], "Space play · Right step", 12, "#9fb1c8"),
            _text("controls-2", [792, 601], "[ ] rotate · R reset · C clear", 12, "#9fb1c8"),
        ])
        return _scene("zoe-brain-life", 1100, 740, objects, "Zoe Brain Life · 3D cellular automaton")

    def export(self, path, kind=None, width=1400, yaw=35):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"json", "svg", "png", "gem"}:
            raise ValueError("Brain Life export must be json, svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("Brain Life export directory does not exist")
        if kind == "json":
            with path.open("x", encoding="utf-8") as stream:
                json.dump(self.document(), stream, indent=2, sort_keys=True)
                stream.write("\n")
            return path
        scene = self.scene(yaw)
        check = verify_vdi(scene) if kind == "gem" else verify(scene)
        if not check.passed:
            raise ValueError(check.text())
        if kind == "gem":
            write_metafile(scene, path)
        elif kind == "svg":
            write_svg(scene, path, width)
        else:
            write_png(scene, path, width)
        return path

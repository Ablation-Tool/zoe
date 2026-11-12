from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .atlas import _scene, _text
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


RULES = "B3/S23"
PATTERNS = {
    "block": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "blinker": ((0, 0), (1, 0), (2, 0)),
    "glider": ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2)),
    "toad": ((1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)),
    "beacon": ((0, 0), (1, 0), (0, 1), (1, 1), (2, 2), (3, 2), (2, 3), (3, 3)),
    "gosper": (
        (0, 4), (0, 5), (1, 4), (1, 5),
        (10, 4), (10, 5), (10, 6), (11, 3), (11, 7),
        (12, 2), (12, 8), (13, 2), (13, 8), (14, 5),
        (15, 3), (15, 7), (16, 4), (16, 5), (16, 6), (17, 5),
        (20, 2), (20, 3), (20, 4), (21, 2), (21, 3), (21, 4),
        (22, 1), (22, 5), (24, 0), (24, 1), (24, 5), (24, 6),
        (34, 2), (34, 3), (35, 2), (35, 3),
    ),
}


class Life:
    def __init__(self, cells=(), width=40, height=28):
        if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int):
            raise ValueError("Life dimensions must be integers")
        if not 8 <= width <= 64 or not 8 <= height <= 64:
            raise ValueError("Life dimensions must be between 8 and 64 cells")
        self.width = width
        self.height = height
        self.cells = set()
        for cell in cells:
            if not isinstance(cell, (tuple, list)) or len(cell) != 2:
                raise ValueError("Life cells must be two-dimensional coordinates")
            x, y = cell
            if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
                raise ValueError("Life cell coordinates must be integers")
            if not 0 <= x < width or not 0 <= y < height:
                raise ValueError("Life cell lies outside the bounded grid")
            self.cells.add((x, y))
        self.generation = 0

    @classmethod
    def from_pattern(cls, name="glider", width=40, height=28):
        if name not in PATTERNS:
            raise ValueError(f"unknown Life pattern: {name}")
        points = PATTERNS[name]
        left = min(point[0] for point in points)
        right = max(point[0] for point in points)
        top = min(point[1] for point in points)
        bottom = max(point[1] for point in points)
        offset_x = (width - (right - left + 1)) // 2 - left
        offset_y = (height - (bottom - top + 1)) // 2 - top
        return cls(((x + offset_x, y + offset_y) for x, y in points), width, height)

    @property
    def population(self):
        return len(self.cells)

    def toggle(self, x, y):
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int) or not isinstance(y, int):
            raise ValueError("Life cell coordinates must be integers")
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise ValueError("Life cell lies outside the bounded grid")
        cell = (x, y)
        if cell in self.cells:
            self.cells.remove(cell)
        else:
            self.cells.add(cell)

    def clear(self):
        self.cells.clear()
        self.generation = 0

    def step(self):
        neighbors = {}
        for x, y in self.cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    cell = (x + dx, y + dy)
                    if 0 <= cell[0] < self.width and 0 <= cell[1] < self.height:
                        neighbors[cell] = neighbors.get(cell, 0) + 1
        self.cells = {
            cell for cell, count in neighbors.items()
            if count == 3 or count == 2 and cell in self.cells
        }
        self.generation += 1
        return self.cells

    def advance(self, count):
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 10000:
            raise ValueError("Life steps must be an integer from 0 to 10000")
        for _ in range(count):
            self.step()
        return self

    def digest(self):
        state = {
            "width": self.width,
            "height": self.height,
            "generation": self.generation,
            "cells": sorted(self.cells),
        }
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def document(self):
        return {
            "schema_version": 1,
            "instrument": "zoe-life",
            "rules": RULES,
            "boundary": "finite non-wrapping grid",
            "width": self.width,
            "height": self.height,
            "generation": self.generation,
            "population": self.population,
            "cells": sorted(self.cells),
            "state_sha256": self.digest(),
            "biological_life_created": False,
            "external_actions_executed": False,
        }

    def scene(self):
        objects = [{
            "id": "background", "type": "rectangle", "bounds": [0, 0, 1100, 740],
            "stroke": "#080d18", "fill": "#080d18", "width": 1,
        }]
        objects.extend([
            _text("title", [40, 51], "Zoe Life", 31, "#86efac"),
            _text("subtitle", [42, 80], "Conway's Game of Life · deterministic cellular automaton", 15, "#d8e2ee"),
            _text("rules", [42, 106], f"{RULES} · finite grid · no biological or external action", 12, "#9fb1c8"),
        ])
        origin_x, origin_y, size = 40, 132, 20
        for y in range(self.height):
            for x in range(self.width):
                alive = (x, y) in self.cells
                left = origin_x + x * size
                top = origin_y + y * size
                objects.append({
                    "id": f"cell-{x}-{y}", "type": "rectangle",
                    "bounds": [left, top, left + size, top + size],
                    "stroke": "#243449", "fill": "#86efac" if alive else "#101b2b", "width": 0.5,
                })
        objects.append({
            "id": "metrics", "type": "rectangle", "bounds": [874, 132, 1060, 404],
            "stroke": "#475569", "fill": "#101b2b", "width": 1,
        })
        rows = (
            ("Generation", self.generation),
            ("Population", self.population),
            ("Grid", f"{self.width} × {self.height}"),
            ("Rules", RULES),
            ("State", self.digest()[:16]),
        )
        for index, (label, value) in enumerate(rows):
            objects.append(_text(f"metric-label-{index}", [894, 169 + index * 48], label, 12, "#9fb1c8"))
            objects.append(_text(f"metric-value-{index}", [894, 190 + index * 48], str(value), 17, "#d8e2ee"))
        objects.extend([
            _text("controls", [875, 458], "Click cells to toggle", 13, "#d8e2ee"),
            _text("controls-2", [875, 482], "Space play · Right step", 12, "#9fb1c8"),
            _text("controls-3", [875, 504], "R reset · C clear", 12, "#9fb1c8"),
            _text("scope", [875, 550], "A mathematical model,", 12, "#fda4af"),
            _text("scope-2", [875, 572], "not biological life.", 12, "#fda4af"),
        ])
        return _scene("zoe-life", 1100, 740, objects, "Zoe Life · Conway's Game of Life")

    def export(self, path, kind=None, width=1400):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"json", "svg", "png", "gem"}:
            raise ValueError("Life export must be json, svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("Life export directory does not exist")
        if kind == "json":
            with path.open("x", encoding="utf-8") as stream:
                json.dump(self.document(), stream, indent=2, sort_keys=True)
                stream.write("\n")
            return path
        scene = self.scene()
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

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import secrets
import time

from .atlas import _line, _scene, _text
from .field import _canonical
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


WIDTH, HEIGHT = 6, 10
PIECE_NAMES = ("F", "I", "L", "P", "T", "U", "V", "W", "X", "Y", "Z", "N")
SHAPES = {
    "F": ((1, 0), (2, 0), (0, 1), (1, 1), (1, 2)),
    "I": ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4)),
    "L": ((0, 0), (0, 1), (0, 2), (0, 3), (1, 3)),
    "P": ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2)),
    "T": ((0, 0), (1, 0), (2, 0), (1, 1), (1, 2)),
    "U": ((0, 0), (2, 0), (0, 1), (1, 1), (2, 1)),
    "V": ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2)),
    "W": ((0, 0), (0, 1), (1, 1), (1, 2), (2, 2)),
    "X": ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2)),
    "Y": ((1, 0), (0, 1), (1, 1), (1, 2), (1, 3)),
    "Z": ((0, 0), (1, 0), (1, 1), (1, 2), (2, 2)),
    "N": ((1, 0), (1, 1), (0, 2), (1, 2), (0, 3)),
}
COLORS = {
    "F": "#f0abfc", "I": "#67e8f9", "L": "#fda4af", "P": "#fde68a",
    "T": "#86efac", "U": "#93c5fd", "V": "#fdba74", "W": "#c4b5fd",
    "X": "#f9a8d4", "Y": "#a7f3d0", "Z": "#fca5a5", "N": "#7dd3fc",
}
STATUSES = {"playing", "won", "lost", "timed_out"}
EVENT_FIELDS = {"sequence", "at", "action", "arguments", "accepted", "state_sha256", "previous_hash", "hash"}
DOCUMENT_FIELDS = {
    "schema_version", "instrument", "mode", "board", "seconds", "interval", "seed",
    "seed_sha256", "order", "next_piece", "pieces", "status", "elapsed", "events",
    "state_sha256", "measurements", "replay_verified", "scope",
}


def _normalize(cells):
    left = min(cell[0] for cell in cells)
    top = min(cell[1] for cell in cells)
    return tuple(sorted((x - left, y - top) for x, y in cells))


def oriented_cells(name, rotation=0, reflected=False):
    if name not in SHAPES or isinstance(rotation, bool) or not isinstance(rotation, int) or not 0 <= rotation < 4 or not isinstance(reflected, bool):
        raise ValueError("invalid pentomino orientation")
    cells = [(-x if reflected else x, y) for x, y in SHAPES[name]]
    for _ in range(rotation):
        cells = [(-y, x) for x, y in cells]
    return _normalize(cells)


@lru_cache(maxsize=12)
def orientations(name):
    if name not in SHAPES:
        raise ValueError("unknown pentomino")
    variants = {}
    for reflected in (False, True):
        for rotation in range(4):
            cells = oriented_cells(name, rotation, reflected)
            variants.setdefault(cells, {"rotation": rotation, "reflected": reflected, "cells": cells})
    return tuple(variants.values())


def _cell_set(placement):
    return {(placement["x"] + x, placement["y"] + y) for x, y in placement["cells"]}


def solve_tiling(order):
    order = list(order)
    if len(order) != 12 or set(order) != set(PIECE_NAMES):
        raise ValueError("a tiling requires each of the twelve pieces exactly once")
    occupied = set()
    placements = {}

    def search():
        if len(placements) == 12:
            return True
        target = next((x, y) for y in range(HEIGHT) for x in range(WIDTH) if (x, y) not in occupied)
        for name in order:
            if name in placements:
                continue
            for variant in orientations(name):
                for cell in variant["cells"]:
                    x, y = target[0] - cell[0], target[1] - cell[1]
                    placement = {"name": name, "x": x, "y": y, **variant}
                    cells = _cell_set(placement)
                    if any(not 0 <= cx < WIDTH or not 0 <= cy < HEIGHT or (cx, cy) in occupied for cx, cy in cells):
                        continue
                    placements[name] = placement
                    occupied.update(cells)
                    if search():
                        return True
                    occupied.difference_update(cells)
                    del placements[name]
        return False

    if not search():
        raise ValueError("no exact tiling exists for this piece order")
    return [deepcopy(placements[name]) for name in order]


class PentominoGame:
    def __init__(self, seed="zoe-practice", mode="practice", seconds=300, interval=0.8, clock=time.monotonic, _replay=False):
        if mode not in {"practice", "masked"}:
            raise ValueError("mode must be practice or masked")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 3600:
            raise ValueError("seconds must be between zero and 3600")
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not math.isfinite(interval) or not 0.05 <= interval <= 3600:
            raise ValueError("gravity interval must be between 0.05 and 3600 seconds")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.mode = mode
        self.seconds = float(seconds)
        self.interval = float(interval)
        self._seed = seed if mode == "practice" or _replay else secrets.token_hex(16)
        if not isinstance(self._seed, str) or not 1 <= len(self._seed) <= 128:
            raise ValueError("seed must contain 1-128 characters")
        self._clock = clock
        self._start = self._time()
        self._last_gravity = 0.0
        self._ended_elapsed = None
        self._bag = list(PIECE_NAMES)
        random.Random(self._seed).shuffle(self._bag)
        self.fixed = {}
        self.used = []
        self.current = None
        self.status = "playing"
        self.events = []
        self.replay_verified = False
        self._spawn()

    def _time(self):
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("clock must return a finite monotonic time")
        if value < getattr(self, "_last_time", -math.inf):
            raise ValueError("clock cannot move backward")
        self._last_time = float(value)
        return float(value)

    @property
    def deadline(self):
        return self._start + self.seconds

    @property
    def elapsed(self):
        if self._ended_elapsed is not None:
            return self._ended_elapsed
        return min(self.seconds, max(0.0, self._time() - self._start))

    @property
    def remaining(self):
        return max(0.0, self.seconds - self.elapsed)

    @property
    def next_piece(self):
        if self.status != "playing" or self.mode == "masked" or len(self.used) + 1 >= 12:
            return None
        return self._bag[len(self.used) + 1]

    def _finish(self, status):
        self.status = status
        self._ended_elapsed = self.seconds if status == "timed_out" else min(self.seconds, max(0.0, self._time() - self._start))

    def _spawn(self):
        if len(self.used) == 12:
            self.current = None
            self._finish("won")
            return
        name = self._bag[len(self.used)]
        cells = oriented_cells(name)
        self.current = {"name": name, "x": (WIDTH - 1 - max(x for x, _ in cells)) // 2, "y": -1 - max(y for _, y in cells), "rotation": 0, "reflected": False}
        if not any(
            self._placeable({"name": name, "x": x, "y": y, "rotation": variant["rotation"], "reflected": variant["reflected"]})
            for variant in orientations(name)
            for y in range(HEIGHT)
            for x in range(WIDTH)
        ):
            self._finish("lost")

    def _free(self, piece):
        for x, y in oriented_cells(piece["name"], piece["rotation"], piece["reflected"]):
            location = (piece["x"] + x, piece["y"] + y)
            if not 0 <= location[0] < WIDTH or location[1] >= HEIGHT or location in self.fixed:
                return False
        return True

    def _placeable(self, piece):
        return self._free(piece) and all(piece["y"] + y >= 0 for _, y in oriented_cells(piece["name"], piece["rotation"], piece["reflected"]))

    def _state(self):
        return {
            "board": {f"{x},{y}": name for (x, y), name in sorted(self.fixed.items())},
            "current": deepcopy(self.current),
            "pieces": list(self.used),
            "status": self.status,
            "elapsed": round(self.elapsed, 6),
        }

    def _state_digest(self):
        return hashlib.sha256(_canonical(self._state()).encode("utf-8")).hexdigest()

    def _record(self, action, arguments, accepted):
        if len(self.events) >= 4096:
            raise ValueError("pentomino event bound reached")
        event = {
            "sequence": len(self.events) + 1,
            "at": round(self.elapsed, 6),
            "action": action,
            "arguments": deepcopy(arguments),
            "accepted": bool(accepted),
            "state_sha256": self._state_digest(),
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        self.events.append(event)

    def _commit(self):
        name = self.current["name"]
        for x, y in oriented_cells(name, self.current["rotation"], self.current["reflected"]):
            self.fixed[(self.current["x"] + x, self.current["y"] + y)] = name
        self.used.append(name)
        self._spawn()

    def _synchronize(self, record=False):
        if self.status != "playing":
            return False
        changed = self.elapsed >= self.seconds and self._time() - self._start >= self.seconds
        if changed:
            self._finish("timed_out")
        else:
            elapsed = self.elapsed
            due = min(HEIGHT * 12, max(0, math.floor((elapsed - self._last_gravity) / self.interval)))
            for _ in range(due):
                self._last_gravity += self.interval
                candidate = deepcopy(self.current)
                candidate["y"] += 1
                if self._free(candidate):
                    self.current = candidate
                elif self._placeable(self.current):
                    self._commit()
                changed = True
                if self.status != "playing":
                    break
        if record or changed:
            self._record("tick", {}, self.status == "playing")
        return changed

    def tick(self):
        self._synchronize()
        return self.measurements()

    def _action(self, action, arguments):
        if len(self.events) >= 4095:
            raise ValueError("pentomino event bound reached")
        self._synchronize()
        accepted = False
        if self.status == "playing" and self.current is not None:
            candidate = deepcopy(self.current)
            if action == "move":
                candidate["x"] += arguments["dx"]
                candidate["y"] += arguments["dy"]
                accepted = self._free(candidate)
                if accepted:
                    self.current = candidate
            elif action in {"rotate", "flip"}:
                before_cells = oriented_cells(self.current["name"], self.current["rotation"], self.current["reflected"])
                before_width = 1 + max(x for x, _ in before_cells)
                if action == "rotate":
                    candidate["rotation"] = (candidate["rotation"] + arguments["steps"]) % 4
                else:
                    candidate["reflected"] = not candidate["reflected"]
                after_cells = oriented_cells(candidate["name"], candidate["rotation"], candidate["reflected"])
                after_width = 1 + max(x for x, _ in after_cells)
                candidate["x"] += (before_width - after_width) // 2
                if max(y for _, y in before_cells) + self.current["y"] < 0:
                    before_height = 1 + max(y for _, y in before_cells)
                    after_height = 1 + max(y for _, y in after_cells)
                    candidate["y"] -= max(0, after_height - before_height)
                accepted = self._free(candidate)
                if accepted:
                    self.current = candidate
            elif action == "drop" and self._placeable(candidate):
                while True:
                    candidate = deepcopy(self.current)
                    candidate["y"] += 1
                    if not self._placeable(candidate):
                        break
                    self.current = candidate
                self._commit()
                accepted = True
            elif action == "place" and self._placeable(candidate):
                self._commit()
                accepted = True
        self._record(action, arguments, accepted)
        return accepted

    def move(self, dx=0, dy=0):
        if any(isinstance(value, bool) or not isinstance(value, int) or abs(value) > HEIGHT + 5 for value in (dx, dy)):
            raise ValueError("movement must use integer offsets bounded by the board and staging area")
        return self._action("move", {"dx": dx, "dy": dy})

    def rotate(self, steps=1):
        if isinstance(steps, bool) or not isinstance(steps, int) or steps not in {-3, -2, -1, 1, 2, 3}:
            raise ValueError("rotation steps must be a nonzero integer from -3 to 3")
        return self._action("rotate", {"steps": steps})

    def flip(self):
        return self._action("flip", {})

    def drop(self):
        return self._action("drop", {})

    def place(self):
        return self._action("place", {})

    def measurements(self):
        full_rows = [y for y in range(HEIGHT) if all((x, y) in self.fixed for x in range(WIDTH))]
        holes = sum(
            (x, y) not in self.fixed and any((x, above) in self.fixed for above in range(y))
            for y in range(HEIGHT) for x in range(WIDTH)
        )
        return {
            "filled_cells": len(self.fixed),
            "empty_cells": WIDTH * HEIGHT - len(self.fixed),
            "full_rows": full_rows,
            "full_row_count": len(full_rows),
            "holes": holes,
            "pieces_placed": len(self.used),
            "elapsed": self.elapsed,
            "remaining": self.remaining,
            "status": self.status,
            "timed_out": self.status == "timed_out",
            "all_pieces_tiled": len(self.used) == 12 and len(self.fixed) == 60,
        }

    def document(self):
        complete = self.status != "playing"
        return {
            "schema_version": 1,
            "instrument": "zoe-pentomino",
            "mode": self.mode,
            "board": {"width": WIDTH, "height": HEIGHT, "rows_do_not_clear": True},
            "seconds": self.seconds,
            "interval": self.interval,
            "seed": self._seed if complete else None,
            "seed_sha256": hashlib.sha256(self._seed.encode("utf-8")).hexdigest(),
            "order": list(self._bag) if complete else [*self.used, self.current["name"]] if self.current else list(self.used),
            "next_piece": self.next_piece,
            "pieces": self._state(),
            "status": self.status,
            "elapsed": self.elapsed,
            "events": deepcopy(self.events),
            "state_sha256": self._state_digest(),
            "measurements": self.measurements(),
            "replay_verified": self.replay_verified,
            "scope": "Spatial practice under a defined budget; not an intelligence measurement or a universal optimal-time claim.",
        }

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("pentomino sessions must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("session directory does not exist")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    @classmethod
    def replay(cls, source):
        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("pentomino session exceeds 2 MiB")
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = deepcopy(source)
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-pentomino":
            raise ValueError("unsupported pentomino session")
        if data["status"] not in STATUSES - {"playing"} or not isinstance(data["events"], list) or not 1 <= len(data["events"]) <= 4096:
            raise ValueError("only bounded completed games can be replayed")
        if data["board"] != {"width": WIDTH, "height": HEIGHT, "rows_do_not_clear": True}:
            raise ValueError("unsupported pentomino board")
        if data["scope"] != "Spatial practice under a defined budget; not an intelligence measurement or a universal optimal-time claim." or data["next_piece"] is not None or not isinstance(data["replay_verified"], bool):
            raise ValueError("unsupported pentomino session scope")
        if not isinstance(data["seed"], str) or data["seed_sha256"] != hashlib.sha256(data["seed"].encode("utf-8")).hexdigest():
            raise ValueError("pentomino seed digest mismatch")
        now = [0.0]
        game = cls(data["seed"], data["mode"], data["seconds"], data["interval"], clock=lambda: now[0], _replay=True)
        previous_hash = None
        for index, expected in enumerate(data["events"], 1):
            if not isinstance(expected, dict) or set(expected) != EVENT_FIELDS or isinstance(expected["sequence"], bool) or expected["sequence"] != index or expected["previous_hash"] != previous_hash or not isinstance(expected["accepted"], bool):
                raise ValueError("pentomino hash-chain mismatch")
            if expected["hash"] != hashlib.sha256(_canonical({key: value for key, value in expected.items() if key != "hash"}).encode("utf-8")).hexdigest():
                raise ValueError("pentomino hash-chain mismatch")
            at = expected["at"]
            if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or not now[0] <= at <= game.seconds:
                raise ValueError("pentomino event times must be ordered and inside the budget")
            now[0] = at
            first = len(game.events)
            if expected["action"] == "tick":
                game.tick()
            else:
                arguments = expected["arguments"]
                if not isinstance(arguments, dict):
                    raise ValueError("invalid pentomino event arguments")
                try:
                    if expected["action"] == "move" and set(arguments) == {"dx", "dy"}:
                        game.move(**arguments)
                    elif expected["action"] == "rotate" and set(arguments) == {"steps"}:
                        game.rotate(**arguments)
                    elif expected["action"] == "flip" and not arguments:
                        game.flip()
                    elif expected["action"] == "drop" and not arguments:
                        game.drop()
                    elif expected["action"] == "place" and not arguments:
                        game.place()
                    else:
                        raise ValueError("unsupported pentomino replay action")
                except (TypeError, ValueError) as error:
                    raise ValueError("invalid pentomino replay action") from error
            actual = game.events[first:]
            if len(actual) != 1 or actual[0] != expected:
                raise ValueError("pentomino replay diverges from the recorded state")
            previous_hash = expected["hash"]
        if game.events != data["events"] or game._state_digest() != data["state_sha256"] or game.status != data["status"]:
            raise ValueError("pentomino final state does not match the replay")
        if data["seed"] != game._seed or data["order"] != game._bag or data["pieces"] != game._state() or data["measurements"] != game.measurements():
            raise ValueError("pentomino summary does not match the replay")
        game.replay_verified = True
        return game

    def scene(self):
        objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
        origin_x, origin_y, cell = 72, 100, 54
        for y in range(HEIGHT + 1):
            objects.append(_line(f"row-{y}", [origin_x, origin_y + y * cell], [origin_x + WIDTH * cell, origin_y + y * cell], "#20304a", 1))
        for x in range(WIDTH + 1):
            objects.append(_line(f"column-{x}", [origin_x + x * cell, origin_y], [origin_x + x * cell, origin_y + HEIGHT * cell], "#20304a", 1))
        pieces = [(name, (x, y)) for (x, y), name in self.fixed.items()]
        if self.current:
            pieces.extend((self.current["name"], (self.current["x"] + dx, self.current["y"] + dy)) for dx, dy in oriented_cells(self.current["name"], self.current["rotation"], self.current["reflected"]))
        for index, (name, (x, y)) in enumerate(pieces):
            if 0 <= y < HEIGHT:
                objects.append({"id": f"cell-{index}", "type": "rectangle", "bounds": [origin_x + x * cell + 2, origin_y + y * cell + 2, origin_x + (x + 1) * cell - 2, origin_y + (y + 1) * cell - 2], "stroke": COLORS[name], "fill": COLORS[name], "width": 2})
        if self.current:
            for index, (x, y) in enumerate(oriented_cells(self.current["name"], self.current["rotation"], self.current["reflected"])):
                objects.append({"id": f"preview-{index}", "type": "rectangle", "bounds": [480 + x * 20, 382 + y * 20, 497 + x * 20, 399 + y * 20], "stroke": COLORS[self.current["name"]], "fill": COLORS[self.current["name"]], "width": 1})
            objects.append(_text("preview-label", [620, 410], f"Current: {self.current['name']}", 17, COLORS[self.current["name"]]))
        objects.append(_text("title", [62, 48], "Zoe Pentomino", 32, "#67e8f9"))
        objects.append(_text("subtitle", [64, 77], "Twelve shapes · sixty cells · one finite field", 15, "#9fb1c8"))
        measurements = self.measurements()
        rows = [
            f"Budget  {measurements['remaining']:.1f} s remaining / {self.seconds:g} s",
            f"Placed  {len(self.used)} / 12     Filled  {len(self.fixed)} / 60",
            f"Full rows  {measurements['full_row_count']}     Holes  {measurements['holes']}",
            f"Status  {self.status.replace('_', ' ')}",
            f"Next  {self.next_piece if self.mode == 'practice' and self.next_piece else 'masked' if self.mode == 'masked' and self.status == 'playing' else 'revealed at game end'}",
            "Rows counted, never cleared. Tile all 12 pieces.",
            "Practice only · no intelligence or optimum claim.",
        ]
        for index, row in enumerate(rows):
            objects.append(_text(f"summary-{index}", [470, 145 + index * 40], row, 17 if index < 4 else 14, "#fde68a" if index == 3 else "#d8e5f2"))
        for index, name in enumerate(PIECE_NAMES):
            x = 470 + (index % 4) * 117
            y = 485 + (index // 4) * 63
            objects.append(_text(f"piece-{name}", [x, y], f"{name}  {'placed' if name in self.used else 'open'}", 14, COLORS[name]))
        objects.append(_text("attempt", [64, 699], "Attempt value = immediate reward + information + future skill + enjoyment - expected failure cost", 14, "#f0abfc"))
        objects.append(_text("lens", [64, 729], "A decision lens, not a biological equation. Outcomes are evidence for the next attempt.", 13, "#9fb1c8"))
        return _scene("zoe-pentomino", 1000, 760, objects, "Zoe Pentomino · timed spatial practice")

    def export(self, path, kind=None, width=1200):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"svg", "png", "gem"}:
            raise ValueError("pentomino export must be svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("export directory does not exist")
        scene = self.scene()
        if kind == "gem":
            report = verify_vdi(scene)
        else:
            report = verify(scene)
        if not report.passed:
            raise ValueError(report.text())
        if kind == "gem":
            write_metafile(scene, path)
        elif kind == "svg":
            write_svg(scene, path, width)
        else:
            write_png(scene, path, width)
        return path


def benchmark_budgets(budgets=(1, 5, 20, 300), seed="zoe-time-study", move_seconds=1):
    if isinstance(move_seconds, bool) or not isinstance(move_seconds, (int, float)) or not 0 < move_seconds <= 300:
        raise ValueError("move_seconds must be positive and at most 300")
    order = list(PIECE_NAMES)
    random.Random(seed).shuffle(order)
    solution = {placement["name"]: placement for placement in solve_tiling(order)}
    results = []
    for seconds in budgets:
        now = [0.0]
        game = PentominoGame(seed, seconds=seconds, interval=3600, clock=lambda: now[0])
        for name in order:
            if game.status != "playing":
                break
            target = solution[name]
            now[0] += move_seconds
            if target["reflected"] != game.current["reflected"]:
                game.flip()
            difference = (target["rotation"] - game.current["rotation"]) % 4
            if difference:
                game.rotate(difference)
            game.move(target["x"] - game.current["x"], target["y"] - game.current["y"])
            game.place()
        result = game.measurements()
        result.update({"budget_seconds": seconds, "event_count": len(game.events), "order": order})
        results.append(result)
    return {
        "instrument": "Zoe Pentomino controlled time-budget comparison",
        "seed": seed,
        "strategy": "Exact-cover tiling; identical piece order, placements, and one synthetic second per piece; gravity interval 3600 seconds.",
        "clock": "injected deterministic clock; no sleeping or human-performance measurement",
        "budgets": results,
        "conclusion": "These strategy-specific outcomes do not identify an optimal human time budget or establish a general time-performance law.",
    }

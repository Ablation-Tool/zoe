from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import re

from .atlas import _scene, _text
from .field import _canonical
from .geometry import verify
from .pentomino import COLORS, PIECE_NAMES, oriented_cells
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


FACES = ("U", "L", "F", "R", "B", "D")
NORMALS = {"U": (0, 1, 0), "D": (0, -1, 0), "F": (0, 0, 1), "B": (0, 0, -1), "R": (1, 0, 0), "L": (-1, 0, 0)}
NORMAL_TO_FACE = {normal: face for face, normal in NORMALS.items()}
FACE_LAYERS = {"R": (0, 2), "L": (0, -2), "U": (1, 2), "D": (1, -2), "F": (2, 2), "B": (2, -2)}
NET = {"U": (1, 0), "L": (0, 1), "F": (1, 1), "R": (2, 1), "B": (3, 1), "D": (1, 2)}
FACE_TILINGS = {
    "U": (
        ("Y", 0, 0, 3, False), ("T", 2, 0, 1, False), ("V", 0, 1, 0, False),
        ("N", 1, 2, 3, False), ("I", 0, 4, 1, False),
    ),
    "L": (
        ("P", 0, 0, 3, True), ("F", 2, 0, 0, False), ("L", 3, 1, 0, True),
        ("X", 1, 2, 0, False), ("U", 0, 2, 1, False),
    ),
    "F": (
        ("P", 0, 0, 1, False), ("L", 0, 1, 0, False), ("Z", 2, 0, 0, True),
        ("W", 1, 2, 0, False), ("Y", 3, 1, 2, True),
    ),
    "R": (
        ("Y", 0, 0, 3, False), ("T", 2, 0, 1, False), ("V", 0, 1, 0, False),
        ("N", 1, 2, 3, False), ("I", 0, 4, 1, False),
    ),
    "B": (
        ("P", 0, 0, 3, True), ("F", 2, 0, 0, False), ("L", 3, 1, 0, True),
        ("X", 1, 2, 0, False), ("U", 0, 2, 1, False),
    ),
    "D": (
        ("V", 0, 0, 1, False), ("W", 2, 0, 1, False), ("P", 3, 1, 2, False),
        ("I", 0, 4, 1, False), ("T", 0, 1, 2, False),
    ),
}
MOVE_TOKEN = re.compile(r"^([ULFRBD])([12]?)(['’]?)$")
EVENT_FIELDS = {"sequence", "action", "arguments", "accepted", "state_sha256", "previous_hash", "hash"}
DOCUMENT_FIELDS = {
    "schema_version", "instrument", "seed", "scramble", "events", "state",
    "home_sha256", "initial_state_sha256", "state_sha256", "measurements",
    "equations", "scope", "replay_verified", "digest",
}
SCOPE = "A deterministic spatial puzzle, not an intelligence measurement, optimal-distance solver, historical-game replica, or hardware model."
EQUATIONS = {
    "exact_cover": "For every face f, five disjoint pentomino placements cover all 25 cells; 6 x 25 = 30 x 5 = 150 stickers.",
    "turn": "On the selected layer p dot e_axis = layer, T(p,n) = (R_axis^q p, R_axis^q n); other stickers are unchanged.",
    "inverse": "T(a,layer,q)^-1 = T(a,layer,4-q), and four identical quarter turns equal the identity.",
    "recovery": "rho(S) = home-position stickers / 150; kappa(S) = fully recovered five-sticker home regions / 30.",
    "lower_bound": "ceil(displaced position-or-normal stickers / 44) is a weak lower bound, not an optimal solution distance.",
}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def face_position(face, row, column):
    if face not in FACES or any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 5 for value in (row, column)):
        raise ValueError("face cell requires a valid face and integer row/column from 0 to 4")
    x, y = column - 2, 2 - row
    if face == "F":
        return x, y, 2
    if face == "B":
        return 2 - column, y, -2
    if face == "U":
        return x, 2, row - 2
    if face == "D":
        return x, -2, 2 - row
    if face == "R":
        return 2, y, 2 - column
    return -2, y, column - 2


def face_cell(face, position, normal):
    if face not in FACES or tuple(normal) != NORMALS[face]:
        raise ValueError("sticker normal does not belong to the selected face")
    x, y, z = position
    if face == "F":
        row, column = 2 - y, x + 2
    elif face == "B":
        row, column = 2 - y, 2 - x
    elif face == "U":
        row, column = z + 2, x + 2
    elif face == "D":
        row, column = 2 - z, x + 2
    elif face == "R":
        row, column = 2 - y, 2 - z
    else:
        row, column = 2 - y, z + 2
    if row not in range(5) or column not in range(5):
        raise ValueError("sticker position is outside its face")
    return row, column


def _home_stickers():
    stickers = []
    for face in FACES:
        occupied = set()
        for patch_index, (name, left, top, rotation, reflected) in enumerate(FACE_TILINGS[face]):
            patch = len(stickers) // 5
            for dx, dy in oriented_cells(name, rotation, reflected):
                row, column = top + dy, left + dx
                position = face_position(face, row, column)
                if (row, column) in occupied:
                    raise ValueError("pentomino face tiling overlaps")
                occupied.add((row, column))
                stickers.append({
                    "home": len(stickers), "patch": patch, "name": name,
                    "position": position, "normal": NORMALS[face],
                })
        if occupied != {(row, column) for row in range(5) for column in range(5)}:
            raise ValueError("pentomino face tiling is not an exact cover")
    if len(stickers) != 150 or {row["name"] for row in stickers} != set(PIECE_NAMES):
        raise ValueError("home cube must contain 30 regions and all twelve pentomino shapes")
    return stickers


HOME_STICKERS = _home_stickers()
HOME_SHA256 = _digest(HOME_STICKERS)


def validate_stickers(stickers):
    if not isinstance(stickers, list) or len(stickers) != 150:
        return False
    identities = set()
    for index, (expected, sticker) in enumerate(zip(HOME_STICKERS, stickers)):
        if not isinstance(sticker, dict) or sticker.get("home") != index or sticker.get("patch") != expected["patch"] or sticker.get("name") != expected["name"]:
            return False
        position, normal = sticker.get("position"), sticker.get("normal")
        if not isinstance(position, (tuple, list)) or len(position) != 3 or not isinstance(normal, (tuple, list)) or len(normal) != 3:
            return False
        if any(isinstance(value, bool) or not isinstance(value, int) or value not in {-2, -1, 0, 1, 2} for value in position):
            return False
        if any(isinstance(value, bool) or not isinstance(value, int) or value not in {-1, 0, 1} for value in normal) or sum(abs(value) for value in normal) != 1:
            return False
        axis = next(axis for axis, value in enumerate(normal) if value)
        if position[axis] != normal[axis] * 2:
            return False
        identity = tuple(position), tuple(normal)
        if identity in identities:
            return False
        identities.add(identity)
    return identities == {(row["position"], row["normal"]) for row in HOME_STICKERS}


def validate_move(move):
    if not isinstance(move, dict) or set(move) != {"face", "depth", "inverse"} or move["face"] not in FACES:
        raise ValueError("invalid Pentacube move")
    if isinstance(move["depth"], bool) or not isinstance(move["depth"], int) or move["depth"] not in {1, 2} or not isinstance(move["inverse"], bool):
        raise ValueError("Pentacube depth must be outer 1 or inner 2, with an explicit inverse flag")
    return {"face": move["face"], "depth": move["depth"], "inverse": move["inverse"]}


def inverse_move(move):
    move = validate_move(move)
    return {"face": move["face"], "depth": move["depth"], "inverse": not move["inverse"]}


def move_text(move):
    move = validate_move(move)
    suffix = "'" if move["inverse"] else ""
    return f"{move['face']}{move['depth'] if move['depth'] == 2 else ''}{suffix}"


def parse_moves(text):
    if not isinstance(text, str) or len(text) > 2048:
        raise ValueError("move sequence must be bounded text")
    if not text.strip():
        return []
    tokens = [token.strip() for token in text.split(",")]
    if len(tokens) > 256 or any(not token for token in tokens):
        raise ValueError("move sequence requires 1 to 256 comma-separated turns")
    moves = []
    for token in tokens:
        match = MOVE_TOKEN.fullmatch(token)
        if not match:
            raise ValueError(f"invalid Pentacube move: {token}")
        moves.append({"face": match[1], "depth": int(match[2] or 1), "inverse": bool(match[3])})
    return moves


def _quarter(vector, axis, quarter):
    x, y, z = vector
    for _ in range(quarter):
        if axis == 0:
            x, y, z = x, -z, y
        elif axis == 1:
            x, y, z = z, y, -x
        else:
            x, y, z = -y, x, z
    return x, y, z


def _turn_quarter(face, inverse):
    _axis, layer = FACE_LAYERS[face]
    quarter = 3 if layer > 0 else 1
    return 4 - quarter if inverse else quarter


def permute_stickers(stickers, move):
    move = validate_move(move)
    if not validate_stickers(stickers):
        raise ValueError("Pentacube permutation requires a complete valid sticker state")
    result = deepcopy(stickers)
    axis, outer = FACE_LAYERS[move["face"]]
    layer = outer if move["depth"] == 1 else 1 if outer > 0 else -1
    quarter = _turn_quarter(move["face"], move["inverse"])
    for sticker in result:
        if sticker["position"][axis] == layer:
            sticker["position"] = _quarter(sticker["position"], axis, quarter)
            sticker["normal"] = _quarter(sticker["normal"], axis, quarter)
    if not validate_stickers(result):
        raise ValueError("Pentacube move left the legal sticker space")
    return result


def scramble_moves(seed, count):
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 64:
        raise ValueError("scramble length must be between 0 and 64")
    rng = random.Random(seed)
    moves = []
    while len(moves) < count:
        move = {"face": rng.choice(FACES), "depth": rng.choice((1, 1, 1, 2)), "inverse": bool(rng.getrandbits(1))}
        if moves and (move["face"], move["depth"]) == (moves[-1]["face"], moves[-1]["depth"]):
            continue
        moves.append(move)
    return moves


class PentacubeGame:
    def __init__(self, seed="zoe-pentacube", scramble=6):
        if not isinstance(seed, str) or not 1 <= len(seed) <= 128:
            raise ValueError("Pentacube seed must contain 1-128 characters")
        self.seed = seed
        self.scramble = scramble_moves(seed, scramble)
        self.stickers = deepcopy(HOME_STICKERS)
        for move in self.scramble:
            self.stickers = permute_stickers(self.stickers, move)
        self.scrambled = deepcopy(self.stickers)
        self.history = []
        self.events = []
        self.replay_verified = False

    def _state(self, stickers=None, history=None):
        return {
            "stickers": [
                {"home": row["home"], "patch": row["patch"], "name": row["name"], "position": list(row["position"]), "normal": list(row["normal"])}
                for row in (self.stickers if stickers is None else stickers)
            ],
            "history": deepcopy(self.history if history is None else history),
        }

    def _state_digest(self):
        return _digest(self._state())

    def _record(self, action, arguments):
        if len(self.events) >= 4096:
            raise ValueError("Pentacube event bound reached")
        event = {
            "sequence": len(self.events) + 1,
            "action": action,
            "arguments": deepcopy(arguments),
            "accepted": True,
            "state_sha256": self._state_digest(),
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        event["hash"] = _digest(event)
        self.events.append(event)

    def apply(self, move):
        move = validate_move(move)
        if len(self.events) >= 4096:
            raise ValueError("Pentacube event bound reached")
        self.stickers = permute_stickers(self.stickers, move)
        self.history.append(move)
        self._record("turn", {"move": move})
        return True

    def turn(self, face, depth=1, inverse=False):
        return self.apply({"face": face, "depth": depth, "inverse": inverse})

    def undo(self):
        if not self.history:
            return False
        if len(self.events) >= 4096:
            raise ValueError("Pentacube event bound reached")
        move = self.history.pop()
        self.stickers = permute_stickers(self.stickers, inverse_move(move))
        self._record("undo", {"move": move})
        return True

    def reset(self):
        if len(self.events) >= 4096:
            raise ValueError("Pentacube event bound reached")
        self.stickers = deepcopy(self.scrambled)
        self.history = []
        self._record("reset", {})
        return True

    def solution_moves(self):
        return [inverse_move(move) for move in reversed([*self.scramble, *self.history])]

    def hint(self):
        moves = self.solution_moves()
        if not moves:
            return None
        return {"move": moves[0], "executed": False, "optimal": False, "basis": "reverse the recorded legal path, not a shortest-path search"}

    def _home_match(self, index):
        return self.stickers[index]["position"] == HOME_STICKERS[index]["position"] and self.stickers[index]["normal"] == HOME_STICKERS[index]["normal"]

    def measurements(self):
        matches = sum(self._home_match(index) for index in range(150))
        recovered = sum(all(self._home_match(index) for index in range(patch * 5, patch * 5 + 5)) for patch in range(30))
        displaced = 150 - matches
        return {
            "stickers": 150,
            "regions": 30,
            "home_matches": matches,
            "displaced": displaced,
            "recovered_regions": recovered,
            "rho": matches / 150,
            "kappa": recovered / 30,
            "weak_lower_bound": math.ceil(displaced / 44),
            "lower_bound_is_optimal_distance": False,
            "solved": matches == 150,
            "valid_permutation": validate_stickers(self.stickers),
            "player_turns": len(self.history),
            "scramble_turns": len(self.scramble),
            "events": len(self.events),
            "intelligence_measured": False,
        }

    def board(self):
        result = {face: [[None for _column in range(5)] for _row in range(5)] for face in FACES}
        for index, sticker in enumerate(self.stickers):
            face = NORMAL_TO_FACE[tuple(sticker["normal"])]
            row, column = face_cell(face, sticker["position"], sticker["normal"])
            cell = deepcopy(sticker)
            cell["home_match"] = self._home_match(index)
            result[face][row][column] = cell
        return result

    def document(self):
        return self._add_digest({
            "schema_version": 1,
            "instrument": "zoe-pentacube",
            "seed": self.seed,
            "scramble": deepcopy(self.scramble),
            "events": deepcopy(self.events),
            "state": self._state(),
            "home_sha256": HOME_SHA256,
            "initial_state_sha256": _digest(self._state(self.scrambled, [])),
            "state_sha256": self._state_digest(),
            "measurements": self.measurements(),
            "equations": deepcopy(EQUATIONS),
            "scope": SCOPE,
            "replay_verified": self.replay_verified,
        })

    @staticmethod
    def _add_digest(document):
        document["digest"] = _digest({key: value for key, value in document.items() if key != "digest"})
        return document

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("Pentacube sessions must use a .json path")
        if not path.parent.is_dir():
            raise ValueError("Pentacube session directory does not exist")
        document = self.document()
        self.replay(document)
        document["replay_verified"] = True
        self._add_digest(document)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(document) + "\n")
        return path

    @classmethod
    def replay(cls, source):
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file() or not 1 <= path.stat().st_size <= 4 * 1024 * 1024:
                raise ValueError("Pentacube session is missing or exceeds 4 MiB")
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = deepcopy(source)
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-pentacube":
            raise ValueError("unsupported Pentacube session")
        if data["digest"] != _digest({key: value for key, value in data.items() if key != "digest"}):
            raise ValueError("Pentacube document digest mismatch")
        if data["home_sha256"] != HOME_SHA256 or data["scope"] != SCOPE or data["equations"] != EQUATIONS or not isinstance(data["replay_verified"], bool):
            raise ValueError("unsupported Pentacube home state or scope")
        if not isinstance(data["scramble"], list) or not 0 <= len(data["scramble"]) <= 64 or not isinstance(data["events"], list) or len(data["events"]) > 4096:
            raise ValueError("invalid Pentacube replay bounds")
        game = cls(data["seed"], scramble=0)
        game.scramble = [validate_move(move) for move in data["scramble"]]
        for move in game.scramble:
            game.stickers = permute_stickers(game.stickers, move)
        game.scrambled = deepcopy(game.stickers)
        if game._state_digest() != data["initial_state_sha256"]:
            raise ValueError("Pentacube initial scramble does not match")
        previous_hash = None
        for index, expected in enumerate(data["events"], 1):
            if not isinstance(expected, dict) or set(expected) != EVENT_FIELDS or isinstance(expected["sequence"], bool) or expected["sequence"] != index or expected["previous_hash"] != previous_hash or expected["accepted"] is not True:
                raise ValueError("Pentacube event-chain mismatch")
            if expected["hash"] != _digest({key: value for key, value in expected.items() if key != "hash"}):
                raise ValueError("Pentacube event hash mismatch")
            arguments = expected["arguments"]
            if not isinstance(arguments, dict):
                raise ValueError("invalid Pentacube event arguments")
            first = len(game.events)
            if expected["action"] == "turn" and set(arguments) == {"move"}:
                game.apply(arguments["move"])
            elif expected["action"] == "undo" and set(arguments) == {"move"}:
                if not game.undo():
                    raise ValueError("Pentacube replay undo has no player turn")
            elif expected["action"] == "reset" and not arguments:
                game.reset()
            else:
                raise ValueError("unsupported Pentacube replay action")
            actual = game.events[first:]
            if len(actual) != 1 or actual[0] != expected:
                raise ValueError("Pentacube replay diverges from the recorded event")
            previous_hash = expected["hash"]
        if game.events != data["events"] or game._state() != data["state"] or game._state_digest() != data["state_sha256"]:
            raise ValueError("Pentacube final state does not match the replay")
        if game.measurements() != data["measurements"]:
            raise ValueError("Pentacube measurements do not match the replay")
        game.replay_verified = True
        return game

    def scene(self, hint=None):
        objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
        objects.extend([
            _text("title", [42, 49], "Zoe Pentacube", 31, "#67e8f9"),
            _text("subtitle", [44, 78], "Thirty pentomino home regions · 150 stickers · legal quarter turns", 14, "#9fb1c8"),
        ])
        board = self.board()
        for face in FACES:
            net_x, net_y = NET[face]
            left, top = 40 + net_x * 130, 135 + net_y * 140
            objects.append(_text(f"face-label-{face}", [left, top - 12], f"{face} · five pentominoes", 12, "#e7d6ad"))
            for row in range(5):
                for column in range(5):
                    sticker = board[face][row][column]
                    x, y = left + column * 22, top + row * 22
                    stroke = "#f8fafc" if sticker["home_match"] else "#334155"
                    objects.append({"id": f"sticker-{sticker['home']}", "type": "rectangle", "bounds": [x, y, x + 20, y + 20], "stroke": stroke, "fill": COLORS[sticker["name"]], "width": 1})
                    objects.append(_text(f"sticker-label-{sticker['home']}", [x + 5, y + 14], sticker["name"], 9, "#0f172a"))
        measurements = self.measurements()
        objects.append({"id": "metrics-panel", "type": "rectangle", "bounds": [575, 112, 960, 522], "stroke": "#475569", "fill": "#0f1929", "width": 1})
        rows = [
            ("status", "SOLVED" if measurements["solved"] else "IN PROGRESS", "#a7f3d0"),
            ("matches", f"Home stickers       {measurements['home_matches']} / 150", "#dbeafe"),
            ("regions", f"Recovered regions   {measurements['recovered_regions']} / 30", "#dbeafe"),
            ("displaced", f"Displaced stickers  {measurements['displaced']}", "#dbeafe"),
            ("bound", f"Weak lower bound    {measurements['weak_lower_bound']} turns", "#fda4af"),
            ("history", f"Player turns        {measurements['player_turns']}", "#dbeafe"),
            ("scramble", f"Legal scramble      {measurements['scramble_turns']} turns", "#dbeafe"),
            ("seed", f"Seed  {self.seed[:28]}", "#9fb1c8"),
            ("events", f"Replay events       {measurements['events']}", "#9fb1c8"),
        ]
        for index, (identifier, text, color) in enumerate(rows):
            objects.append(_text(f"metric-{identifier}", [594, 151 + index * 36], text, 15 if index == 0 else 13, color))
        hint_text = move_text(hint["move"]) if hint else "not requested"
        objects.append(_text("hint", [594, 486], f"Hint: {hint_text} · never automatic", 12, "#e7d6ad"))
        objects.extend([
            _text("equation-cover", [44, 579], "Exact cover: 6 faces x 25 cells = 30 pentominoes x 5 stickers = 150", 13, "#c4b5fd"),
            _text("equation-turn", [44, 609], "Layer turn: T(p,n) = (R p, R n) · T^4 = I · inverse = T^3", 13, "#c4b5fd"),
            _text("equation-rho", [44, 639], "rho = home stickers / 150 · kappa = recovered regions / 30", 13, "#c4b5fd"),
            _text("equation-bound", [44, 669], "ceil(displaced / 44) is only a weak lower bound, not an optimal distance", 13, "#fda4af"),
            _text("scope", [44, 704], "Every scramble uses legal moves. Replay checks the complete event chain.", 12, "#9fb1c8"),
            _text("boundary", [44, 731], "A puzzle result is not an intelligence score. No autonomous moves or hardware claims.", 12, "#9fb1c8"),
        ])
        return _scene("zoe-pentacube", 1000, 760, objects, "Zoe Pentacube · pentomino regions and legal cube permutations")

    def export(self, path, kind=None, width=1400, hint=None):
        path = Path(path)
        kind = kind or path.suffix.lower().lstrip(".")
        if kind not in {"svg", "png", "gem"}:
            raise ValueError("Pentacube export must be svg, png, or gem")
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise ValueError("Pentacube export directory does not exist")
        scene = self.scene(hint)
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


def rhyme_for_move(move):
    move = validate_move(move)
    openings = {
        "U": "Up where the sky-colored patterns play,",
        "L": "Left where the little layers sway,",
        "F": "Front where the bright shapes find their way,",
        "R": "Right where the colors march away,",
        "B": "Back where the quiet stickers stay,",
        "D": "Down where the shadow shapes obey,",
    }
    depth = "Outer" if move["depth"] == 1 else "Inner"
    direction = "reverse" if move["inverse"] else "forward"
    return (
        f"{openings[move['face']]}\n"
        f"{depth} {direction}, one quarter today;\n"
        "Follow the path and watch the array;\n"
        "A hint is a choice—you decide the way."
    )


SOLVED_RHYME = "Thirty small shapes are home to stay;\nOne hundred fifty stickers, hip hooray!"

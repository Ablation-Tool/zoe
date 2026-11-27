"""Hexagonal 9-Sister Collaboration Mesh & Constitutional Guard (Milestone M1).

Implements:
  - Feature #1: Flat-topped `(d) Hexagonal` axial/cube coordinate grid and
    symmetric shared-wall adjacency (`hex_distance == 1`).
  - Feature #2: Deterministic neighbor-coupled state exchange and shortest-path
    shared-wall message routing with Jacobi synchronous ticks, canonical
    ordering, and SHA-256 tamper-evidence trace chains.
  - Feature #3: All 9 canonical sisters from `zoe_sisters.py` (`Zoe, Gemma,
    Tosi, Mono, Tetra, Eliza, Sage, Flora, Lumen`) placed in a connected
    16-wall honeycomb aligned with `zoe_universe.py` and the 6 EDDBMS Figure
    15.3 domain modules.
  - Feature #13 (core): Constitutional epistemic firewall enforcing
    `measurement != evidence != belief_update != advisory_proposal` (rejecting
    autonomous `"action"`), rejecting `NaN`/`Inf`/circular payloads, and
    preserving all `docs/CONSTITUTION.md` invariants.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any

from .zoe_sisters import (
    SAFETY_INVARIANTS,
    ZOE_SISTERS,
    SisterModelSpec,
    resolve_sister,
    route_prompt_to_sister,
    run_sister_council,
)

HEX_MESH_CONTRACT: str = "zoe-hex-sister-mesh/v1"
ATTRIBUTION_TEXT: str = "Nicholas Michael Kloster, March 6, 2026"
CONSTITUTIONAL_ATTRIBUTION: str = ATTRIBUTION_TEXT
HASH_CHAIN_SEMANTICS: str = "tamper_evidence_only_not_authentication_or_identity_proof"

HEX_DIRECTIONS: tuple[tuple[str, int, int], ...] = (
    ("N", 0, -1),
    ("NE", 1, -1),
    ("SE", 1, 0),
    ("S", 0, 1),
    ("SW", -1, 1),
    ("NW", -1, 0),
)
HEX_DIRECTION_MAP: dict[str, tuple[int, int]] = {
    direction: (dq, dr) for direction, dq, dr in HEX_DIRECTIONS
}
HEX_DIRECTION_INDEX: dict[str, int] = {
    direction: idx for idx, (direction, _dq, _dr) in enumerate(HEX_DIRECTIONS)
}

EDDBMS_DOMAIN_MODULES: tuple[str, ...] = (
    "MATERIAL_DESIGN",
    "HUMAN_MODEL",
    "DESIGN_PARAMETERS",
    "PRODUCT_DESIGN_AND_PLANNING",
    "PROJECT_MANAGEMENT",
    "POSTPRODUCTION_MANAGEMENT",
)

DEFAULT_SISTER_DOMAIN_MODULES: dict[str, str] = {
    "zoe": "PROJECT_MANAGEMENT",
    "gemma": "PRODUCT_DESIGN_AND_PLANNING",
    "tosi": "PROJECT_MANAGEMENT",
    "mono": "POSTPRODUCTION_MANAGEMENT",
    "tetra": "PRODUCT_DESIGN_AND_PLANNING",
    "eliza": "HUMAN_MODEL",
    "sage": "DESIGN_PARAMETERS",
    "flora": "MATERIAL_DESIGN",
    "lumen": "POSTPRODUCTION_MANAGEMENT",
}

DEFAULT_SISTER_COORDS: dict[str, tuple[int, int]] = {
    "zoe": (0, 0),
    "gemma": (0, -1),
    "tosi": (1, -1),
    "mono": (2, -1),
    "tetra": (1, 0),
    "eliza": (0, 1),
    "sage": (-1, 1),
    "flora": (-2, 1),
    "lumen": (-1, 0),
}

EPISTEMIC_LANES: tuple[str, ...] = (
    "measurement",
    "evidence",
    "belief_update",
    "advisory_proposal",
)
ALLOWED_EPISTEMIC_LANES: frozenset[str] = frozenset(EPISTEMIC_LANES)
FORBIDDEN_AUTONOMOUS_LANES: frozenset[str] = frozenset(
    {"action", "autonomous_action", "execute", "actuation"}
)
_TRUTHY_EXECUTION_STRINGS: frozenset[str] = frozenset({"true", "1", "yes", "on"})

_FALSE_REQUIRED_INVARIANTS: tuple[str, ...] = (
    "sentience_claimed",
    "l5_agi_qualified",
    "zoe_clone_claimed",
    "clinical_action_authorized",
    "flight_control_authorized",
    "cure_claim",
    "autonomous_execution_allowed",
    "authentication_proof",
)
_TRUE_REQUIRED_INVARIANTS: tuple[str, ...] = (
    "advisory_only",
    "loopback_only",
    "wet_lab_validation_required",
    "tamper_evidence_only",
)
_ZERO_INT_INVARIANTS: tuple[str, ...] = (
    "external_actions",
    "tokens_used",
)
_REQUIRED_CONSTITUTIONAL_KEYS: tuple[str, ...] = (
    "advisory_only",
    "read_only",
    "external_actions",
    "tokens_used",
    "cloud_cost_usd",
    "loopback_only",
    "sentience_claimed",
    "l5_agi_qualified",
    "zoe_clone_claimed",
    "clinical_action_authorized",
    "flight_control_authorized",
    "cure_claim",
    "attribution",
)


class NonAdjacentCellError(ValueError):
    """Raised when a direct neighbor message targets a cell with hex_distance != 1."""


class ConstitutionalViolationError(ValueError):
    """Raised when a packet, state, or operation violates docs/CONSTITUTION.md."""


class EpistemicFirewallError(ConstitutionalViolationError):
    """Raised when epistemic lane boundaries or non-autonomous guards are breached."""


class TamperDetectedError(ValueError):
    """Raised when SHA-256 verification detects message or tick-trace tampering."""


def validate_epistemic_lane(lane: str) -> str:
    """Validate an epistemic lane against the Article III firewall."""
    if not isinstance(lane, str):
        raise EpistemicFirewallError(
            f"Epistemic lane must be a string, got {type(lane).__name__}"
        )
    normalized = lane.strip().lower()
    if not normalized:
        raise EpistemicFirewallError("Epistemic lane must be non-empty")
    if normalized in FORBIDDEN_AUTONOMOUS_LANES:
        raise EpistemicFirewallError(
            f"CONSTITUTION.md Art. III violation: autonomous lane {normalized!r} is forbidden; "
            "measurement != evidence != belief_update != advisory_proposal"
        )
    if normalized not in ALLOWED_EPISTEMIC_LANES:
        allowed = ", ".join(EPISTEMIC_LANES)
        raise EpistemicFirewallError(
            f"Invalid epistemic lane {lane!r}; expected one of: {allowed}"
        )
    return normalized


def _normalize_json_value(
    value: Any,
    *,
    label: str = "value",
    _seen: frozenset[int] | None = None,
) -> Any:
    """Recursively validate and normalize JSON-safe primitives, rejecting NaN/Inf/cycles."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConstitutionalViolationError(
                f"{label} must be finite (NaN/Infinity rejected)"
            )
        return 0.0 if value == 0.0 else value

    seen = _seen if _seen is not None else frozenset()
    obj_id = id(value)
    if isinstance(value, Mapping):
        if obj_id in seen:
            raise ConstitutionalViolationError(
                f"{label} contains a circular reference"
            )
        next_seen = seen | {obj_id}
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ConstitutionalViolationError(
                    f"{label} mapping keys must be strings, got {type(k).__name__}"
                )
            out[k] = _normalize_json_value(
                v, label=f"{label}.{k}", _seen=next_seen
            )
        return out

    if isinstance(value, (list, tuple)):
        if obj_id in seen:
            raise ConstitutionalViolationError(
                f"{label} contains a circular reference"
            )
        next_seen = seen | {obj_id}
        return [
            _normalize_json_value(item, label=f"{label}[{idx}]", _seen=next_seen)
            for idx, item in enumerate(value)
        ]

    raise ConstitutionalViolationError(
        f"{label} contains unsupported non-JSON type: {type(value).__name__}"
    )


def canonical_json_bytes(payload: object) -> bytes:
    """Serialize any JSON-valid payload to canonical UTF-8 bytes."""
    normalized = _normalize_json_value(payload, label="payload")
    return json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_canonical(payload: object) -> str:
    """Compute lowercase SHA-256 hex digest of canonical JSON UTF-8 bytes."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def constitutional_metadata(
    epistemic_lane: str = "measurement",
    *,
    read_only: bool = True,
) -> dict[str, Any]:
    """Build a fresh constitutional metadata dictionary matching PROJECT.md Contract 1."""
    lane = validate_epistemic_lane(epistemic_lane)
    if not isinstance(read_only, bool):
        raise ConstitutionalViolationError("read_only must be a boolean")
    return {
        **SAFETY_INVARIANTS,
        "contract": HEX_MESH_CONTRACT,
        "epistemic_lane": lane,
        "measurement_lane_only": lane == "measurement",
        "advisory_only": True,
        "read_only": read_only,
        "external_actions": 0,
        "tokens_used": 0,
        "cloud_cost_usd": 0.0,
        "loopback_only": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "cure_claim": False,
        "wet_lab_validation_required": True,
        "attribution": ATTRIBUTION_TEXT,
        "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
        "tamper_evidence_only": True,
        "authentication_proof": False,
    }


def _is_truthy_execution_flag(val: Any) -> bool:
    """Return True if val represents a truthy execution override (bool, numeric 1, or yes/on/true/1)."""
    if val is True:
        return True
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)) and val == 1:
        return True
    if isinstance(val, str) and val.strip().lower() in _TRUTHY_EXECUTION_STRINGS:
        return True
    return False


def _validate_safety_tree(node: Any, *, path: str = "packet") -> None:
    """Recursively enforce constitutional invariants inside normalized mappings/lists."""
    if isinstance(node, list):
        for idx, item in enumerate(node):
            _validate_safety_tree(item, path=f"{path}[{idx}]")
        return

    if not isinstance(node, dict):
        return

    if "epistemic_lane" in node:
        validate_epistemic_lane(node["epistemic_lane"])

    for flag_key in ("execute", "auto_execute"):
        if flag_key in node and _is_truthy_execution_flag(node[flag_key]):
            raise EpistemicFirewallError(
                f"{path}.{flag_key} attempted autonomous execution override ({node[flag_key]!r})"
            )

    for key in _FALSE_REQUIRED_INVARIANTS:
        if key in node and node[key] is not False:
            raise ConstitutionalViolationError(
                f"{path}.{key} must be False, got {node[key]!r}"
            )

    for key in _TRUE_REQUIRED_INVARIANTS:
        if key in node and node[key] is not True:
            raise ConstitutionalViolationError(
                f"{path}.{key} must be True, got {node[key]!r}"
            )

    for key in _ZERO_INT_INVARIANTS:
        if key in node:
            val = node[key]
            if isinstance(val, bool) or not isinstance(val, int) or val != 0:
                raise ConstitutionalViolationError(
                    f"{path}.{key} must be non-bool int 0, got {val!r}"
                )

    if "cloud_cost_usd" in node:
        cost = node["cloud_cost_usd"]
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost != 0.0:
            raise ConstitutionalViolationError(
                f"{path}.cloud_cost_usd must be numeric 0.0, got {cost!r}"
            )

    if "read_only" in node and not isinstance(node["read_only"], bool):
        raise ConstitutionalViolationError(
            f"{path}.read_only must be bool, got {node['read_only']!r}"
        )

    if "measurement_lane_only" in node and not isinstance(
        node["measurement_lane_only"], bool
    ):
        raise ConstitutionalViolationError(
            f"{path}.measurement_lane_only must be bool, got {node['measurement_lane_only']!r}"
        )

    if "attribution" in node and node["attribution"] != ATTRIBUTION_TEXT:
        raise ConstitutionalViolationError(
            f"{path}.attribution must equal {ATTRIBUTION_TEXT!r}, got {node['attribution']!r}"
        )

    for key, child in node.items():
        _validate_safety_tree(child, path=f"{path}.{key}")


def validate_constitutional_packet(
    packet: Mapping[str, Any],
    *,
    epistemic_lane: str | None = None,
    require_metadata: bool = False,
) -> dict[str, Any]:
    """Validate and deep-normalize a mapping under docs/CONSTITUTION.md guards."""
    if not isinstance(packet, Mapping):
        raise ConstitutionalViolationError(
            f"Constitutional packet must be a Mapping, got {type(packet).__name__}"
        )
    if epistemic_lane is not None:
        validate_epistemic_lane(epistemic_lane)

    normalized = _normalize_json_value(packet, label="packet")
    if not isinstance(normalized, dict):
        raise ConstitutionalViolationError("Normalized packet must be a dict")

    _validate_safety_tree(normalized, path="packet")

    if require_metadata:
        missing = [k for k in _REQUIRED_CONSTITUTIONAL_KEYS if k not in normalized]
        if missing:
            raise ConstitutionalViolationError(
                f"Constitutional metadata missing required keys: {', '.join(missing)}"
            )
        if "epistemic_lane" not in normalized and "measurement_lane_only" not in normalized:
            raise ConstitutionalViolationError(
                "Constitutional metadata must include 'epistemic_lane' or 'measurement_lane_only'"
            )

    return normalized


def opposite_direction(direction: str) -> str:
    """Return the opposite flat-topped hex direction ((d + 3) % 6)."""
    if not isinstance(direction, str):
        raise ValueError(f"Direction must be a string, got {type(direction).__name__}")
    clean = direction.strip().upper()
    if clean not in HEX_DIRECTION_INDEX:
        valid = ", ".join(d for d, _dq, _dr in HEX_DIRECTIONS)
        raise ValueError(f"Unknown hex direction {direction!r}; expected one of {valid}")
    return HEX_DIRECTIONS[(HEX_DIRECTION_INDEX[clean] + 3) % 6][0]


@dataclass(frozen=True)
class HexCoord:
    """Flat-topped axial/cube hexagonal coordinate with invariant q + r + s == 0."""

    q: int
    r: int

    def __post_init__(self) -> None:
        if isinstance(self.q, bool) or not isinstance(self.q, int):
            raise ValueError(f"HexCoord.q must be a non-bool int, got {self.q!r}")
        if isinstance(self.r, bool) or not isinstance(self.r, int):
            raise ValueError(f"HexCoord.r must be a non-bool int, got {self.r!r}")

    @property
    def s(self) -> int:
        return -self.q - self.r

    def distance(self, other: HexCoord) -> int:
        if not isinstance(other, HexCoord):
            raise TypeError(f"Expected HexCoord, got {type(other).__name__}")
        return (
            abs(self.q - other.q)
            + abs(self.r - other.r)
            + abs(self.s - other.s)
        ) // 2

    def neighbor(self, direction: str) -> HexCoord:
        if not isinstance(direction, str):
            raise ValueError(f"Direction must be a string, got {type(direction).__name__}")
        clean = direction.strip().upper()
        if clean not in HEX_DIRECTION_MAP:
            valid = ", ".join(d for d, _dq, _dr in HEX_DIRECTIONS)
            raise ValueError(
                f"Unknown hex direction {direction!r}; expected one of {valid}"
            )
        dq, dr = HEX_DIRECTION_MAP[clean]
        return HexCoord(self.q + dq, self.r + dr)

    def to_pixel(self, size: float = 1.0) -> tuple[float, float]:
        if (
            isinstance(size, bool)
            or not isinstance(size, (int, float))
            or not math.isfinite(size)
            or size <= 0.0
        ):
            raise ValueError(f"Hex size must be a positive finite number, got {size!r}")
        s_f = float(size)
        x = s_f * 1.5 * self.q
        y = s_f * math.sqrt(3.0) * (self.r + 0.5 * self.q)
        return (x, y)

    def to_dict(self) -> dict[str, int]:
        return {"q": self.q, "r": self.r, "s": self.s}


def direction_between(src: HexCoord, dst: HexCoord) -> str | None:
    """Return the unit direction from src to dst if hex_distance == 1, else None."""
    if src.distance(dst) != 1:
        return None
    dq = dst.q - src.q
    dr = dst.r - src.r
    for direction, step_q, step_r in HEX_DIRECTIONS:
        if dq == step_q and dr == step_r:
            return direction
    return None


@dataclass
class HexCell:
    """One hexagonal cell bound to a canonical Zoe Sister and EDDBMS domain module."""

    cell_id: str
    sister: SisterModelSpec
    coord: HexCoord
    domain_module: str
    state: dict[str, Any] = field(default_factory=dict)
    revision: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not self.cell_id.strip():
            raise ValueError("HexCell.cell_id must be a non-empty string")
        if not isinstance(self.sister, SisterModelSpec):
            raise TypeError("HexCell.sister must be a SisterModelSpec")
        if not isinstance(self.coord, HexCoord):
            raise TypeError("HexCell.coord must be a HexCoord")
        if not isinstance(self.domain_module, str) or not self.domain_module.strip():
            raise ValueError("HexCell.domain_module must be a non-empty string")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 0:
            raise ValueError(f"HexCell.revision must be non-negative non-bool int, got {self.revision!r}")
        self.state = validate_constitutional_packet(self.state)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "sister_slot": self.sister.slot,
            "sister_name": self.sister.name,
            "signet": self.sister.signet,
            "coord": self.coord.to_dict(),
            "domain_module": self.domain_module,
            "state": copy.deepcopy(self.state),
            "revision": self.revision,
        }


@dataclass(frozen=True)
class HexMessage:
    """Immutable shared-wall message with constitutional lane & canonical SHA-256."""

    message_id: str
    tick: int
    sender_id: str
    receiver_id: str
    topic: str
    payload: dict[str, Any]
    epistemic_lane: str = "measurement"
    sha256: str = ""

    def __post_init__(self) -> None:
        for attr in ("message_id", "sender_id", "receiver_id", "topic"):
            val = getattr(self, attr)
            if not isinstance(val, str) or not val.strip():
                raise ConstitutionalViolationError(
                    f"HexMessage.{attr} must be a non-empty string"
                )
        if isinstance(self.tick, bool) or not isinstance(self.tick, int) or self.tick < 0:
            raise ConstitutionalViolationError(
                f"HexMessage.tick must be a non-negative non-bool int, got {self.tick!r}"
            )
        lane = validate_epistemic_lane(self.epistemic_lane)
        object.__setattr__(self, "epistemic_lane", lane)
        normalized_payload = validate_constitutional_packet(
            self.payload, epistemic_lane=lane
        )
        object.__setattr__(self, "payload", normalized_payload)
        expected = self.compute_sha256()
        if self.sha256 == "":
            object.__setattr__(self, "sha256", expected)
        elif self.sha256 != expected:
            raise TamperDetectedError(
                f"HexMessage {self.message_id!r} SHA-256 mismatch "
                f"(expected {expected}, got {self.sha256!r}; {HASH_CHAIN_SEMANTICS})"
            )

    def compute_sha256(self) -> str:
        preimage = {
            "contract": HEX_MESH_CONTRACT,
            "epistemic_lane": self.epistemic_lane,
            "message_id": self.message_id,
            "payload": self.payload,
            "receiver_id": self.receiver_id,
            "sender_id": self.sender_id,
            "tick": self.tick,
            "topic": self.topic,
        }
        return sha256_canonical(preimage)

    def verify_sha256(self, *, raise_on_error: bool = True) -> bool:
        ok = self.sha256 == self.compute_sha256()
        if not ok and raise_on_error:
            raise TamperDetectedError(
                f"HexMessage {self.message_id!r} failed SHA-256 verification ({HASH_CHAIN_SEMANTICS})"
            )
        return ok

    def constitutional_metadata(self) -> dict[str, Any]:
        return constitutional_metadata(self.epistemic_lane, read_only=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "tick": self.tick,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "topic": self.topic,
            "payload": copy.deepcopy(self.payload),
            "epistemic_lane": self.epistemic_lane,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class HexTickResult:
    """Immutable deterministic result of a coupled hexagonal mesh tick."""

    tick: int
    delivered_messages: tuple[HexMessage, ...]
    updated_cells: tuple[str, ...]
    state_snapshot: dict[str, dict[str, Any]]
    prev_trace_sha256: str
    trace_sha256: str
    safety_invariants: dict[str, Any]
    hash_chain_semantics: str = HASH_CHAIN_SEMANTICS
    tamper_evidence_only: bool = True
    authentication_proof: bool = False

    @property
    def cell_states(self) -> dict[str, dict[str, Any]]:
        return self.state_snapshot

    @property
    def constitutional(self) -> dict[str, Any]:
        return self.safety_invariants

    def constitutional_metadata(self) -> dict[str, Any]:
        return dict(self.safety_invariants)

    def compute_trace_sha256(self) -> str:
        preimage = {
            "contract": HEX_MESH_CONTRACT,
            "prev_trace_sha256": self.prev_trace_sha256,
            "tick": self.tick,
            "updated_cells": list(self.updated_cells),
            "delivered_message_hashes": [m.sha256 for m in self.delivered_messages],
            "delivered_messages": [m.to_dict() for m in self.delivered_messages],
            "cell_states": {
                cid: self.state_snapshot[cid] for cid in sorted(self.state_snapshot)
            },
            "safety_invariants": self.safety_invariants,
        }
        return sha256_canonical(preimage)

    def verify_trace_sha256(self, *, raise_on_error: bool = True) -> bool:
        for msg in self.delivered_messages:
            if not msg.verify_sha256(raise_on_error=raise_on_error):
                return False
        ok = self.trace_sha256 == self.compute_trace_sha256()
        if not ok and raise_on_error:
            raise TamperDetectedError(
                f"HexTickResult tick={self.tick} failed trace_sha256 verification "
                f"({self.hash_chain_semantics})"
            )
        return ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "delivered_messages": [m.to_dict() for m in self.delivered_messages],
            "updated_cells": list(self.updated_cells),
            "state_snapshot": copy.deepcopy(self.state_snapshot),
            "prev_trace_sha256": self.prev_trace_sha256,
            "trace_sha256": self.trace_sha256,
            "safety_invariants": copy.deepcopy(self.safety_invariants),
            "hash_chain_semantics": self.hash_chain_semantics,
            "tamper_evidence_only": self.tamper_evidence_only,
            "authentication_proof": self.authentication_proof,
        }


def verify_trace_digest(
    result: HexTickResult,
    *,
    raise_on_error: bool = True,
) -> bool:
    """Verify a HexTickResult's message digests and trace SHA-256."""
    return result.verify_trace_sha256(raise_on_error=raise_on_error)


class HexCollaborationMesh:
    """Shared-wall hexagonal collaboration mesh for Zoe and her sisters."""

    def __init__(self, cells: Sequence[HexCell] | None = None) -> None:
        raw_cells = list(cells) if cells is not None else []
        seen_ids: set[str] = set()
        seen_coords: set[HexCoord] = set()
        seen_sister_slots: set[int] = set()
        seen_sister_names: set[str] = set()
        for cell in raw_cells:
            if not isinstance(cell, HexCell):
                raise TypeError(f"Expected HexCell, got {type(cell).__name__}")
            if cell.cell_id in seen_ids:
                raise ValueError(f"Duplicate cell_id in HexCollaborationMesh: {cell.cell_id!r}")
            if cell.coord in seen_coords:
                raise ValueError(f"Duplicate HexCoord in HexCollaborationMesh: {cell.coord!r}")
            if cell.sister.slot in seen_sister_slots:
                raise ValueError(
                    f"Duplicate sister.slot in HexCollaborationMesh: {cell.sister.slot!r}"
                )
            sister_name_key = cell.sister.name.strip().lower()
            if not sister_name_key:
                raise ValueError("HexCell.sister.name must be a non-empty string")
            if sister_name_key in seen_sister_names:
                raise ValueError(
                    f"Duplicate sister.name in HexCollaborationMesh: {cell.sister.name!r}"
                )
            seen_ids.add(cell.cell_id)
            seen_coords.add(cell.coord)
            seen_sister_slots.add(cell.sister.slot)
            seen_sister_names.add(sister_name_key)

        ordered = sorted(raw_cells, key=lambda c: (c.sister.slot, c.cell_id))
        self._cells: dict[str, HexCell] = {c.cell_id: c for c in ordered}
        self.tick: int = 0
        self._msg_seq: int = 0
        self._pending_messages: list[HexMessage] = []
        self._delivered_history: list[HexMessage] = []
        self._tick_traces: list[HexTickResult] = []
        self._last_trace_sha256: str = "GENESIS"

    def resolve_cell_id(self, query: str) -> str:
        """Resolve a cell_id, sister name, signet, model_id, or slot to a mesh cell_id."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Cell identifier query must be a non-empty string")
        clean = query.strip()
        if clean in self._cells:
            return clean
        low = clean.lower()
        for cid in self._cells:
            if cid.lower() == low:
                return cid
        spec = resolve_sister(clean)
        for cid, cell in self._cells.items():
            if cell.sister.slot == spec.slot or cell.sister.signet == spec.signet:
                return cid
        raise ValueError(f"Sister {spec.name!r} is not present in this HexCollaborationMesh")

    def cell(self, cell_id: str) -> HexCell:
        cid = self.resolve_cell_id(cell_id)
        return self._cells[cid]

    def cells(self) -> tuple[HexCell, ...]:
        return tuple(self._cells.values())

    def cell_ids(self) -> tuple[str, ...]:
        return tuple(self._cells.keys())

    def neighbors(self, cell_id: str) -> tuple[str, ...]:
        """Return strictly adjacent (hex_distance == 1) cell IDs sorted by sister slot."""
        cid = self.resolve_cell_id(cell_id)
        origin = self._cells[cid]
        return tuple(
            other.cell_id
            for other in self._cells.values()
            if origin.coord.distance(other.coord) == 1
        )

    def shared_walls(self) -> list[tuple[str, str, str]]:
        """Return unique canonical (cell_a, dir_a_to_b, cell_b) shared-wall edges."""
        walls: list[tuple[str, str, str]] = []
        for cell_a in self._cells.values():
            key_a = (cell_a.sister.slot, cell_a.cell_id)
            for nb_id in self.neighbors(cell_a.cell_id):
                cell_b = self._cells[nb_id]
                key_b = (cell_b.sister.slot, cell_b.cell_id)
                if key_a < key_b:
                    direction = direction_between(cell_a.coord, cell_b.coord)
                    if direction is None:
                        raise RuntimeError(
                            f"Internal invariant error: neighbor {nb_id!r} lacks unit direction"
                        )
                    walls.append((cell_a.cell_id, direction, cell_b.cell_id))
        return walls

    def pending_messages(self) -> tuple[HexMessage, ...]:
        return tuple(self._pending_messages)

    def delivered_history(self) -> tuple[HexMessage, ...]:
        return tuple(self._delivered_history)

    def tick_traces(self) -> tuple[HexTickResult, ...]:
        return tuple(self._tick_traces)

    def send_neighbor_message(
        self,
        sender_id: str,
        receiver_id: str,
        topic: str,
        payload: Mapping[str, Any],
        *,
        epistemic_lane: str = "measurement",
    ) -> HexMessage:
        """Enqueue a direct shared-wall message; raises NonAdjacentCellError if distance != 1."""
        src_id = self.resolve_cell_id(sender_id)
        dst_id = self.resolve_cell_id(receiver_id)
        src = self._cells[src_id]
        dst = self._cells[dst_id]
        dist = src.coord.distance(dst.coord)
        if dist != 1:
            raise NonAdjacentCellError(
                f"Direct neighbor message requires hex_distance == 1; "
                f"{src_id!r} -> {dst_id!r} has hex_distance={dist}"
            )
        if not isinstance(topic, str) or not topic.strip():
            raise ConstitutionalViolationError("Message topic must be a non-empty string")
        lane = validate_epistemic_lane(epistemic_lane)
        clean_payload = validate_constitutional_packet(payload, epistemic_lane=lane)
        next_seq = self._msg_seq + 1
        msg = HexMessage(
            message_id=f"hexmsg-{self.tick + 1:06d}-{next_seq:06d}",
            tick=self.tick + 1,
            sender_id=src_id,
            receiver_id=dst_id,
            topic=topic.strip(),
            payload=clean_payload,
            epistemic_lane=lane,
        )
        self._msg_seq = next_seq
        self._pending_messages.append(msg)
        return msg

    def shortest_path(self, sender_id: str, receiver_id: str) -> tuple[str, ...]:
        """Find deterministic shortest shared-wall path via slot-ordered BFS."""
        src_id = self.resolve_cell_id(sender_id)
        dst_id = self.resolve_cell_id(receiver_id)
        if src_id == dst_id:
            return (src_id,)
        queue: deque[list[str]] = deque([[src_id]])
        visited: set[str] = {src_id}
        while queue:
            path = queue.popleft()
            curr = path[-1]
            for nb in self.neighbors(curr):
                if nb == dst_id:
                    return tuple([*path, nb])
                if nb not in visited:
                    visited.add(nb)
                    queue.append([*path, nb])
        raise ValueError(f"No shared-wall path between {src_id!r} and {dst_id!r}")

    def route_message(
        self,
        sender_id: str,
        receiver_id: str,
        topic: str,
        payload: Mapping[str, Any],
        *,
        epistemic_lane: str = "measurement",
    ) -> list[HexMessage]:
        """Route a message along the shortest shared-wall path; returns [] if sender == receiver."""
        src_id = self.resolve_cell_id(sender_id)
        dst_id = self.resolve_cell_id(receiver_id)
        if not isinstance(topic, str) or not topic.strip():
            raise ConstitutionalViolationError("Message topic must be a non-empty string")
        lane = validate_epistemic_lane(epistemic_lane)
        clean_payload = validate_constitutional_packet(payload, epistemic_lane=lane)
        if src_id == dst_id:
            return []
        path = self.shortest_path(src_id, dst_id)
        hops: list[HexMessage] = []
        for idx in range(len(path) - 1):
            hop = self.send_neighbor_message(
                path[idx],
                path[idx + 1],
                topic,
                clean_payload,
                epistemic_lane=lane,
            )
            hops.append(hop)
        return hops

    def step_coupled_tick(
        self,
        coupling_fn: Callable[[HexCell, dict[str, dict[str, Any]]], dict[str, Any]] | None = None,
    ) -> HexTickResult:
        """Advance one deterministic Jacobi synchronous coupled tick with SHA-256 trace."""
        tick_num = self.tick + 1
        sorted_pending = sorted(
            self._pending_messages,
            key=lambda m: (
                m.tick,
                self._cells[m.sender_id].sister.slot,
                self._cells[m.receiver_id].sister.slot,
                m.message_id,
            ),
        )
        for msg in sorted_pending:
            msg.verify_sha256(raise_on_error=True)

        pre_snapshot: dict[str, dict[str, Any]] = {
            cid: copy.deepcopy(cell.state) for cid, cell in self._cells.items()
        }
        pre_revisions: dict[str, int] = {
            cid: cell.revision for cid, cell in self._cells.items()
        }
        inbox_by_cell: dict[str, list[HexMessage]] = {cid: [] for cid in self._cells}
        for msg in sorted_pending:
            inbox_by_cell[msg.receiver_id].append(msg)

        next_states: dict[str, dict[str, Any]] = {}
        for cell in self._cells.values():
            nb_ids = self.neighbors(cell.cell_id)
            neighbor_states: dict[str, dict[str, Any]] = {
                nid: copy.deepcopy(pre_snapshot[nid]) for nid in nb_ids
            }
            if coupling_fn is not None:
                cell_copy = HexCell(
                    cell_id=cell.cell_id,
                    sister=cell.sister,
                    coord=cell.coord,
                    domain_module=cell.domain_module,
                    state=copy.deepcopy(pre_snapshot[cell.cell_id]),
                    revision=cell.revision,
                )
                raw_next = coupling_fn(cell_copy, neighbor_states)
                next_states[cell.cell_id] = validate_constitutional_packet(raw_next)
            else:
                inbox = inbox_by_cell[cell.cell_id]
                base_state = copy.deepcopy(pre_snapshot[cell.cell_id])
                base_state["last_tick"] = tick_num
                base_state["coupled_neighbors"] = list(nb_ids)
                base_state["neighbor_revisions"] = {
                    nid: pre_revisions[nid] for nid in nb_ids
                }
                base_state["inbox_count"] = len(inbox)
                base_state["last_messages"] = [
                    {
                        "message_id": m.message_id,
                        "from": m.sender_id,
                        "topic": m.topic,
                        "epistemic_lane": m.epistemic_lane,
                        "sha256": m.sha256,
                        "payload": copy.deepcopy(m.payload),
                    }
                    for m in inbox
                ]
                next_states[cell.cell_id] = validate_constitutional_packet(base_state)

        self.tick = tick_num
        delivered_ids = {m.message_id for m in sorted_pending}
        self._pending_messages = [
            m for m in self._pending_messages if m.message_id not in delivered_ids
        ]
        self._delivered_history.extend(sorted_pending)

        updated_cells: list[str] = []
        for cell in self._cells.values():
            cell.state = next_states[cell.cell_id]
            cell.revision += 1
            updated_cells.append(cell.cell_id)

        post_snapshot: dict[str, dict[str, Any]] = {
            cid: copy.deepcopy(cell.state) for cid, cell in self._cells.items()
        }
        invariants = constitutional_metadata("measurement", read_only=True)
        prev_hash = self._last_trace_sha256
        trace_preimage = {
            "contract": HEX_MESH_CONTRACT,
            "prev_trace_sha256": prev_hash,
            "tick": tick_num,
            "updated_cells": updated_cells,
            "delivered_message_hashes": [m.sha256 for m in sorted_pending],
            "delivered_messages": [m.to_dict() for m in sorted_pending],
            "cell_states": {
                cid: post_snapshot[cid] for cid in sorted(post_snapshot)
            },
            "safety_invariants": invariants,
        }
        trace_hash = sha256_canonical(trace_preimage)
        result = HexTickResult(
            tick=tick_num,
            delivered_messages=tuple(sorted_pending),
            updated_cells=tuple(updated_cells),
            state_snapshot=post_snapshot,
            prev_trace_sha256=prev_hash,
            trace_sha256=trace_hash,
            safety_invariants=invariants,
        )
        self._tick_traces.append(result)
        self._last_trace_sha256 = trace_hash
        return result

    def verify_integrity(self, raise_on_error: bool = True) -> dict[str, Any]:
        """Verify all message digests, chained tick traces, and constitutional invariants."""
        try:
            for msg in self._pending_messages:
                msg.verify_sha256(raise_on_error=True)
            for msg in self._delivered_history:
                msg.verify_sha256(raise_on_error=True)

            expected_prev = "GENESIS"
            for trace in self._tick_traces:
                if trace.prev_trace_sha256 != expected_prev:
                    raise TamperDetectedError(
                        f"Trace chain broken at tick={trace.tick}: "
                        f"expected prev={expected_prev!r}, got {trace.prev_trace_sha256!r}"
                    )
                trace.verify_trace_sha256(raise_on_error=True)
                validate_constitutional_packet(
                    trace.safety_invariants, require_metadata=True
                )
                expected_prev = trace.trace_sha256

            if self._tick_traces and expected_prev != self._last_trace_sha256:
                raise TamperDetectedError(
                    "Mesh _last_trace_sha256 does not match final tick trace"
                )

            for cell in self._cells.values():
                validate_constitutional_packet(cell.state)
        except (TamperDetectedError, ConstitutionalViolationError) as exc:
            if raise_on_error:
                raise
            return {
                "ok": False,
                "error": str(exc),
                "ticks_verified": len(self._tick_traces),
                "messages_verified": len(self._delivered_history)
                + len(self._pending_messages),
                "last_trace_sha256": self._last_trace_sha256,
                "tamper_evidence_only": True,
                "authentication_proof": False,
                "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
                "constitutional": constitutional_metadata("measurement", read_only=True),
            }

        return {
            "ok": True,
            "ticks_verified": len(self._tick_traces),
            "messages_verified": len(self._delivered_history)
            + len(self._pending_messages),
            "last_trace_sha256": self._last_trace_sha256,
            "tamper_evidence_only": True,
            "authentication_proof": False,
            "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
            "constitutional": constitutional_metadata("measurement", read_only=True),
        }

    def constitutional_metadata(
        self,
        epistemic_lane: str = "measurement",
        *,
        read_only: bool = True,
    ) -> dict[str, Any]:
        return constitutional_metadata(epistemic_lane, read_only=read_only)

    def snapshot(self) -> dict[str, Any]:
        return {
            "contract": HEX_MESH_CONTRACT,
            "tick": self.tick,
            "cell_count": len(self._cells),
            "cells": {cid: cell.to_dict() for cid, cell in self._cells.items()},
            "shared_walls": [list(w) for w in self.shared_walls()],
            "pending_message_count": len(self._pending_messages),
            "delivered_message_count": len(self._delivered_history),
            "last_trace_sha256": self._last_trace_sha256,
            "tamper_evidence_only": True,
            "authentication_proof": False,
            "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
            "constitutional": constitutional_metadata("measurement", read_only=True),
        }


def build_default_zoe_mesh() -> HexCollaborationMesh:
    """Build the canonical 9-sister flat-topped hexagonal honeycomb mesh."""
    cells: list[HexCell] = []
    for spec in ZOE_SISTERS:
        cid = spec.name.lower()
        q, r = DEFAULT_SISTER_COORDS[cid]
        domain_module = DEFAULT_SISTER_DOMAIN_MODULES[cid]
        init_state: dict[str, Any] = {
            "slot": spec.slot,
            "signet": spec.signet,
            "domain_module": domain_module,
            "last_tick": 0,
            "inbox_count": 0,
        }
        cells.append(
            HexCell(
                cell_id=cid,
                sister=spec,
                coord=HexCoord(q, r),
                domain_module=domain_module,
                state=init_state,
                revision=0,
            )
        )
    return HexCollaborationMesh(cells)


def route_prompt_on_mesh(
    mesh: HexCollaborationMesh,
    prompt: str,
    *,
    hw_profile: str | None = None,
    enqueue_routes: bool = True,
) -> dict[str, Any]:
    """Deterministically route a prompt onto the 9-sister hex mesh at 0 tokens."""
    routed = route_prompt_to_sister(prompt, hw_profile=hw_profile)
    lead_spec: SisterModelSpec = routed["lead"]
    support_spec: SisterModelSpec = routed["support"]
    verifier_spec: SisterModelSpec = routed["verifier"]

    lead_id = mesh.resolve_cell_id(lead_spec.name)
    support_id = mesh.resolve_cell_id(support_spec.name)
    verifier_id = mesh.resolve_cell_id(verifier_spec.name)

    lead_to_support_path = mesh.shortest_path(lead_id, support_id)
    support_to_verifier_path = mesh.shortest_path(support_id, verifier_id)

    enqueued_messages: list[dict[str, Any]] = []
    if enqueue_routes:
        msgs_ls = mesh.route_message(
            lead_id,
            support_id,
            "sister.route.lead_to_support",
            {
                "prompt": routed["prompt"],
                "role": "support",
                "route_sha256": routed["route_sha256"],
            },
            epistemic_lane="advisory_proposal",
        )
        msgs_sv = mesh.route_message(
            support_id,
            verifier_id,
            "sister.route.support_to_verifier",
            {
                "prompt": routed["prompt"],
                "role": "verifier",
                "route_sha256": routed["route_sha256"],
            },
            epistemic_lane="advisory_proposal",
        )
        enqueued_messages = [m.to_dict() for m in (*msgs_ls, *msgs_sv)]

    meta = constitutional_metadata("advisory_proposal", read_only=True)
    return {
        "prompt": routed["prompt"],
        "hw_profile": routed["hw_profile"],
        "lead_cell": lead_id,
        "support_cell": support_id,
        "verifier_cell": verifier_id,
        "lead": lead_spec.name,
        "support": support_spec.name,
        "verifier": verifier_spec.name,
        "lead_to_support_path": list(lead_to_support_path),
        "support_to_verifier_path": list(support_to_verifier_path),
        "enqueued_messages": enqueued_messages,
        "matched_signals": list(routed["matched_signals"]),
        "route_sha256": routed["route_sha256"],
        "constitutional": meta,
        **meta,
    }


def run_hex_sister_council(
    mesh: HexCollaborationMesh,
    topic: str,
    *,
    hw_profile: str | None = None,
    ticks: int = 1,
) -> dict[str, Any]:
    """Run a 0-token 3-sister council and propagate advisory proposals across hex walls."""
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        raise ValueError(f"ticks must be a non-negative non-bool int, got {ticks!r}")

    routed = route_prompt_to_sister(topic, hw_profile=hw_profile)
    council = run_sister_council(topic, hw_profile=hw_profile)

    lead_spec: SisterModelSpec = routed["lead"]
    support_spec: SisterModelSpec = routed["support"]
    verifier_spec: SisterModelSpec = routed["verifier"]

    lead_id = mesh.resolve_cell_id(lead_spec.name)
    support_id = mesh.resolve_cell_id(support_spec.name)
    verifier_id = mesh.resolve_cell_id(verifier_spec.name)

    path_ls = mesh.shortest_path(lead_id, support_id)
    path_sv = mesh.shortest_path(support_id, verifier_id)

    mesh.route_message(
        lead_id,
        support_id,
        "sister.council.proposal",
        {
            "topic": council["topic"],
            "council_sha256": council["council_sha256"],
            "stage": "lead_to_support",
        },
        epistemic_lane="advisory_proposal",
    )
    mesh.route_message(
        support_id,
        verifier_id,
        "sister.council.review",
        {
            "topic": council["topic"],
            "council_sha256": council["council_sha256"],
            "stage": "support_to_verifier",
        },
        epistemic_lane="advisory_proposal",
    )

    tick_results = [mesh.step_coupled_tick() for _ in range(ticks)]
    neighbor_witnesses = {
        "lead": list(mesh.neighbors(lead_id)),
        "support": list(mesh.neighbors(support_id)),
        "verifier": list(mesh.neighbors(verifier_id)),
    }
    tick_trace_hashes = [r.trace_sha256 for r in tick_results]
    council_mesh_sha256 = sha256_canonical(
        {
            "contract": HEX_MESH_CONTRACT,
            "topic": council["topic"],
            "council_sha256": council["council_sha256"],
            "lead_cell": lead_id,
            "support_cell": support_id,
            "verifier_cell": verifier_id,
            "lead_to_support_path": list(path_ls),
            "support_to_verifier_path": list(path_sv),
            "tick_trace_hashes": tick_trace_hashes,
        }
    )

    meta = constitutional_metadata("advisory_proposal", read_only=True)
    return {
        "topic": council["topic"],
        "hw_profile": council["hw_profile"],
        "seats": copy.deepcopy(council["seats"]),
        "lead_cell": lead_id,
        "support_cell": support_id,
        "verifier_cell": verifier_id,
        "lead_to_support_path": list(path_ls),
        "support_to_verifier_path": list(path_sv),
        "neighbor_witnesses": neighbor_witnesses,
        "ticks_executed": ticks,
        "tick_trace_hashes": tick_trace_hashes,
        "combined_power_w": council["combined_power_w"],
        "matched_signals": list(council["matched_signals"]),
        "council_sha256": council["council_sha256"],
        "council_mesh_sha256": council_mesh_sha256,
        "constitutional": meta,
        **meta,
    }

"""Unit tests for M1 Hexagonal 9-Sister Mesh & Constitutional Guard (zoe_hex_mesh.py)."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
import math
from pathlib import Path
import sys
from typing import Any

import pytest

GUIAI_LAB_ROOT = Path(__file__).resolve().parents[1]
if str(GUIAI_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(GUIAI_LAB_ROOT))

from guiai.gem.zoe_hex_mesh import (  # noqa: E402
    ALLOWED_EPISTEMIC_LANES,
    ATTRIBUTION_TEXT,
    EDDBMS_DOMAIN_MODULES,
    HASH_CHAIN_SEMANTICS,
    HEX_DIRECTIONS,
    ConstitutionalViolationError,
    EpistemicFirewallError,
    HexCell,
    HexCollaborationMesh,
    HexCoord,
    HexMessage,
    HexTickResult,
    NonAdjacentCellError,
    TamperDetectedError,
    build_default_zoe_mesh,
    constitutional_metadata,
    direction_between,
    opposite_direction,
    route_prompt_on_mesh,
    run_hex_sister_council,
    sha256_canonical,
    validate_constitutional_packet,
    validate_epistemic_lane,
    verify_trace_digest,
)
from guiai.gem.zoe_sisters import ZOE_SISTERS  # noqa: E402


# ---------------------------------------------------------------------------
# Group 1: 9-Sister Coverage & Registry Alignment
# ---------------------------------------------------------------------------


def test_default_zoe_mesh_covers_all_9_sisters_and_6_eddbms_modules() -> None:
    mesh = build_default_zoe_mesh()
    cells = mesh.cells()
    assert len(cells) == 9
    assert [c.sister.slot for c in cells] == list(range(1, 10))
    assert {c.sister.name for c in cells} == {s.name for s in ZOE_SISTERS}
    assert {c.sister.signet for c in cells} == {s.signet for s in ZOE_SISTERS}

    zoe_cell = mesh.cell("zoe")
    assert zoe_cell.coord == HexCoord(0, 0)
    assert zoe_cell.sister.slot == 1

    coords = [c.coord for c in cells]
    assert len(set(coords)) == 9
    for c in cells:
        assert c.coord.q + c.coord.r + c.coord.s == 0
        assert c.coord.s == -c.coord.q - c.coord.r
        assert c.revision == 0

    # All 6 EDDBMS Figure 15.3 domain modules must be represented across the 9 sisters
    represented_modules = {c.domain_module for c in cells}
    assert represented_modules == set(EDDBMS_DOMAIN_MODULES)

    # neighbors() must be deterministically sorted by sister slot
    for c in cells:
        nbs = mesh.neighbors(c.cell_id)
        nb_slots = [mesh.cell(nid).sister.slot for nid in nbs]
        assert nb_slots == sorted(nb_slots)
        assert len(nbs) >= 2  # zero dangling leaves

    # Resolution by signet, name, slot string, and case-insensitive ID
    assert mesh.resolve_cell_id("ruby") == "zoe"
    assert mesh.resolve_cell_id("SM124") == "mono"
    assert mesh.resolve_cell_id("8") == "flora"
    assert mesh.resolve_cell_id("Lumen") == "lumen"


def test_hex_coord_cube_invariants_directions_and_bool_rejection() -> None:
    origin = HexCoord(0, 0)
    assert origin.s == 0
    assert origin.to_dict() == {"q": 0, "r": 0, "s": 0}

    px_origin = origin.to_pixel(size=2.0)
    assert px_origin == (0.0, 0.0)
    assert HexCoord(2, -1).to_pixel(size=1.0)[1] == pytest.approx(0.0)
    assert HexCoord(-2, 1).to_pixel(size=1.0)[1] == pytest.approx(0.0)

    for idx, (direction, _dq, _dr) in enumerate(HEX_DIRECTIONS):
        nb = origin.neighbor(direction)
        assert origin.distance(nb) == 1
        assert nb.distance(origin) == 1
        assert direction_between(origin, nb) == direction
        opp = opposite_direction(direction)
        assert opp == HEX_DIRECTIONS[(idx + 3) % 6][0]
        assert nb.neighbor(opp) == origin
        assert direction_between(nb, origin) == opp

    assert direction_between(origin, HexCoord(2, -1)) is None

    with pytest.raises(ValueError):
        origin.neighbor("UP")
    with pytest.raises(ValueError):
        opposite_direction("INVALID")
    with pytest.raises(ValueError):
        HexCoord(True, 0)
    with pytest.raises(ValueError):
        HexCoord(0, False)
    with pytest.raises(ValueError):
        origin.to_pixel(size=0.0)
    with pytest.raises(ValueError):
        origin.to_pixel(size=float("nan"))


# ---------------------------------------------------------------------------
# Group 2: Hexagonal Topology Symmetry & Shared Walls
# ---------------------------------------------------------------------------


def test_shared_walls_symmetry_16_edges_and_connected_graph() -> None:
    mesh = build_default_zoe_mesh()
    walls = mesh.shared_walls()
    assert len(walls) == 16
    assert len(set(walls)) == 16

    # Check symmetry, distance == 1, opposite directions, no self-loops
    all_ids = mesh.cell_ids()
    for u in all_ids:
        u_nbs = mesh.neighbors(u)
        assert u not in u_nbs
        for v in u_nbs:
            assert u in mesh.neighbors(v)
            cu = mesh.cell(u).coord
            cv = mesh.cell(v).coord
            assert cu.distance(cv) == 1
            d_uv = direction_between(cu, cv)
            d_vu = direction_between(cv, cu)
            assert d_uv is not None
            assert d_vu == opposite_direction(d_uv)

    for a, d_ab, b in walls:
        assert a != b
        assert mesh.cell(a).sister.slot < mesh.cell(b).sister.slot
        assert direction_between(mesh.cell(a).coord, mesh.cell(b).coord) == d_ab

    # Zoe center has 6 neighbors; outer wings Mono/Flora have degree 2 and distance 2 from Zoe
    assert len(mesh.neighbors("zoe")) == 6
    assert mesh.neighbors("mono") == ("tosi", "tetra")
    assert mesh.neighbors("flora") == ("sage", "lumen")
    assert mesh.cell("zoe").coord.distance(mesh.cell("mono").coord) == 2
    assert mesh.cell("zoe").coord.distance(mesh.cell("flora").coord) == 2

    # BFS reachability from Zoe reaches all 9 sisters
    visited = {"zoe"}
    q: deque[str] = deque(["zoe"])
    while q:
        curr = q.popleft()
        for nb in mesh.neighbors(curr):
            if nb not in visited:
                visited.add(nb)
                q.append(nb)
    assert visited == set(all_ids)


def test_mesh_rejects_duplicate_cell_id_or_coord() -> None:
    zoe = ZOE_SISTERS[0]
    gemma = ZOE_SISTERS[1]
    c1 = HexCell("zoe", zoe, HexCoord(0, 0), "PROJECT_MANAGEMENT")
    c_dup_id = HexCell("zoe", gemma, HexCoord(0, -1), "MATERIAL_DESIGN")
    c_dup_coord = HexCell("gemma", gemma, HexCoord(0, 0), "MATERIAL_DESIGN")

    with pytest.raises(ValueError, match="Duplicate cell_id"):
        HexCollaborationMesh([c1, c_dup_id])
    with pytest.raises(ValueError, match="Duplicate HexCoord"):
        HexCollaborationMesh([c1, c_dup_coord])


def test_mesh_rejects_duplicate_sister_slot_name_and_blank_name() -> None:
    zoe = ZOE_SISTERS[0]
    gemma = ZOE_SISTERS[1]
    c_zoe = HexCell("cell_1", zoe, HexCoord(0, 0), "PROJECT_MANAGEMENT")

    # Same SisterModelSpec bound to two distinct cells (distinct cell_id & HexCoord)
    c_same_spec = HexCell("cell_2", zoe, HexCoord(0, -1), "MATERIAL_DESIGN")
    with pytest.raises(ValueError, match="Duplicate sister.slot"):
        HexCollaborationMesh([c_zoe, c_same_spec])

    # Distinct SisterModelSpec with duplicate sister.slot
    dup_slot_sister = replace(gemma, slot=zoe.slot)
    c_dup_slot = HexCell("cell_dup_slot", dup_slot_sister, HexCoord(0, -1), "MATERIAL_DESIGN")
    with pytest.raises(ValueError, match="Duplicate sister.slot"):
        HexCollaborationMesh([c_zoe, c_dup_slot])

    # Distinct SisterModelSpec with duplicate sister.name (exact & case/whitespace variants)
    for variant_name in ("Zoe", "zoe", " ZOE "):
        dup_name_sister = replace(gemma, name=variant_name)
        c_dup_name = HexCell(
            "cell_dup_name", dup_name_sister, HexCoord(0, -1), "MATERIAL_DESIGN"
        )
        with pytest.raises(ValueError, match="Duplicate sister.name"):
            HexCollaborationMesh([c_zoe, c_dup_name])

    # Blank/whitespace sister.name rejected
    for blank_name in ("", "   ", "\t\n"):
        blank_sister = replace(gemma, name=blank_name)
        c_blank = HexCell("cell_blank", blank_sister, HexCoord(0, -1), "MATERIAL_DESIGN")
        with pytest.raises(ValueError, match="non-empty"):
            HexCollaborationMesh([c_blank])

    # Empty and partial custom meshes with distinct sisters continue to work
    assert HexCollaborationMesh([]).cell_ids() == ()
    partial_one = HexCollaborationMesh([c_zoe])
    assert partial_one.cell_ids() == ("cell_1",)
    c_gemma = HexCell("cell_2", gemma, HexCoord(0, -1), "MATERIAL_DESIGN")
    partial_two = HexCollaborationMesh([c_zoe, c_gemma])
    assert partial_two.cell_ids() == ("cell_1", "cell_2")
    assert partial_two.neighbors("cell_1") == ("cell_2",)


# ---------------------------------------------------------------------------
# Group 3: Non-Adjacent Rejection (hex_distance != 1)
# ---------------------------------------------------------------------------


def test_send_neighbor_message_rejects_non_adjacent_and_preserves_state() -> None:
    mesh = build_default_zoe_mesh()
    before_snapshot = mesh.snapshot()

    # Self-send (distance == 0)
    with pytest.raises(NonAdjacentCellError) as self_exc:
        mesh.send_neighbor_message("zoe", "zoe", "self.ping", {"v": 1})
    assert isinstance(self_exc.value, ValueError)

    # Distance 2 (mono -> zoe) and distance 4 (mono -> flora)
    with pytest.raises(NonAdjacentCellError):
        mesh.send_neighbor_message("mono", "zoe", "skip.wall", {"v": 1})
    with pytest.raises(NonAdjacentCellError):
        mesh.send_neighbor_message("mono", "flora", "cross.mesh", {"v": 1})

    # Unknown cell ID
    with pytest.raises(ValueError):
        mesh.send_neighbor_message("zoe", "nonexistent_sister", "bad", {"v": 1})

    # Failed sends must NOT enqueue messages or advance counters
    assert len(mesh.pending_messages()) == 0
    assert mesh.snapshot() == before_snapshot


# ---------------------------------------------------------------------------
# Group 4: Multi-Hop Shortest-Path Routing
# ---------------------------------------------------------------------------


def test_route_message_shortest_bfs_path_mono_to_flora() -> None:
    mesh = build_default_zoe_mesh()
    path = mesh.shortest_path("mono", "flora")
    # Exact canonical lowest-slot tie-broken 4-hop chain verified by Explorer 1
    assert path == ("mono", "tosi", "zoe", "sage", "flora")
    assert len(path) - 1 == mesh.cell("mono").coord.distance(mesh.cell("flora").coord)

    hops = mesh.route_message(
        "mono",
        "flora",
        "eddbms.material.query",
        {"target": "C27", "priority": 1},
        epistemic_lane="evidence",
    )
    assert len(hops) == 4
    assert [(m.sender_id, m.receiver_id) for m in hops] == [
        ("mono", "tosi"),
        ("tosi", "zoe"),
        ("zoe", "sage"),
        ("sage", "flora"),
    ]
    for hop in hops:
        assert mesh.cell(hop.sender_id).coord.distance(mesh.cell(hop.receiver_id).coord) == 1
        assert hop.topic == "eddbms.material.query"
        assert hop.payload == {"target": "C27", "priority": 1}
        assert hop.epistemic_lane == "evidence"

    # Sender == receiver returns [] after validation
    assert mesh.route_message("zoe", "zoe", "noop", {"ok": True}) == []
    with pytest.raises(EpistemicFirewallError):
        mesh.route_message("zoe", "zoe", "bad", {"ok": True}, epistemic_lane="action")
    with pytest.raises(ValueError):
        mesh.route_message("mono", "missing", "bad", {"ok": True})


def test_route_message_takes_detour_when_shortest_geometric_line_missing() -> None:
    # Build a 4-cell crescent around (0,0) omitting direct center cell so (0,-1)->(1,0) requires 2 hops
    zoe, gemma, tosi, tetra = ZOE_SISTERS[0], ZOE_SISTERS[1], ZOE_SISTERS[2], ZOE_SISTERS[4]
    mesh = HexCollaborationMesh(
        [
            HexCell("gemma", gemma, HexCoord(0, -1), "PRODUCT_DESIGN_AND_PLANNING"),
            HexCell("tosi", tosi, HexCoord(1, -1), "PROJECT_MANAGEMENT"),
            HexCell("tetra", tetra, HexCoord(1, 0), "PRODUCT_DESIGN_AND_PLANNING"),
        ]
    )
    # gemma -> tetra has hex_distance 2, passes through tosi
    hops = mesh.route_message("gemma", "tetra", "detour", {"step": 1})
    assert [(h.sender_id, h.receiver_id) for h in hops] == [
        ("gemma", "tosi"),
        ("tosi", "tetra"),
    ]
    # Disconnected cell raises ValueError cleanly
    disconnected = HexCollaborationMesh(
        [
            HexCell("zoe", zoe, HexCoord(0, 0), "PROJECT_MANAGEMENT"),
            HexCell("tetra", tetra, HexCoord(3, 0), "PRODUCT_DESIGN_AND_PLANNING"),
        ]
    )
    with pytest.raises(ValueError, match="No shared-wall path"):
        disconnected.route_message("zoe", "tetra", "unreachable", {"x": 1})


# ---------------------------------------------------------------------------
# Group 5: Deterministic Ticked State Exchange & Zero-Token Council/Routing
# ---------------------------------------------------------------------------


def test_step_coupled_tick_is_deterministic_canonical_and_jacobi_synchronous() -> None:
    mesh_a = build_default_zoe_mesh()
    mesh_b = build_default_zoe_mesh()

    # Enqueue messages in DIFFERENT insertion orders on mesh_a vs mesh_b
    mesh_a.send_neighbor_message("lumen", "zoe", "optics", {"nm": 470})
    mesh_a.send_neighbor_message("gemma", "zoe", "draft", {"dpi": 300})
    mesh_a.send_neighbor_message("tosi", "mono", "boot", {"uefi": True})

    mesh_b.send_neighbor_message("tosi", "mono", "boot", {"uefi": True})
    mesh_b.send_neighbor_message("lumen", "zoe", "optics", {"nm": 470})
    mesh_b.send_neighbor_message("gemma", "zoe", "draft", {"dpi": 300})

    res_a = mesh_a.step_coupled_tick()
    res_b = mesh_b.step_coupled_tick()

    # Canonical delivery order: (tick, sender_slot, receiver_slot) -> gemma(2)->zoe(1), tosi(3)->mono(4), lumen(9)->zoe(1)
    assert [(m.sender_id, m.receiver_id) for m in res_a.delivered_messages] == [
        ("gemma", "zoe"),
        ("tosi", "mono"),
        ("lumen", "zoe"),
    ]
    assert [(m.sender_id, m.receiver_id) for m in res_b.delivered_messages] == [
        ("gemma", "zoe"),
        ("tosi", "mono"),
        ("lumen", "zoe"),
    ]
    # Note: message_ids depend on insertion seq, so check identical-order runs for exact trace_sha256 parity
    mesh_1 = build_default_zoe_mesh()
    mesh_2 = build_default_zoe_mesh()
    for m in (mesh_1, mesh_2):
        m.send_neighbor_message("lumen", "zoe", "optics", {"nm": 470})
        m.send_neighbor_message("gemma", "zoe", "draft", {"dpi": 300})
        m.route_message("mono", "flora", "audit", {"ok": True}, epistemic_lane="belief_update")
    t1 = mesh_1.step_coupled_tick()
    t2 = mesh_2.step_coupled_tick()
    assert t1.trace_sha256 == t2.trace_sha256
    assert t1.state_snapshot == t2.state_snapshot
    assert t1.cell_states == t1.state_snapshot
    assert t1.updated_cells == tuple(c.cell_id for c in mesh_1.cells())

    # Custom Jacobi coupling_fn sees pre-tick neighbor states (never mid-tick mutated state)
    def jacobi_counter(
        cell: HexCell, neighbor_states: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        nb_rev_sum = sum(int(st.get("counter", 0)) for st in neighbor_states.values())
        return {
            "slot": cell.sister.slot,
            "counter": int(cell.state.get("counter", 0)) + 1,
            "seen_neighbor_sum": nb_rev_sum,
        }

    t_j1 = mesh_1.step_coupled_tick(coupling_fn=jacobi_counter)
    # Before tick 2, all neighbors had counter == 0 even for cells updated later in slot order!
    for cid in mesh_1.cell_ids():
        assert t_j1.state_snapshot[cid]["seen_neighbor_sum"] == 0
        assert t_j1.state_snapshot[cid]["counter"] == 1

    t_j2 = mesh_1.step_coupled_tick(coupling_fn=jacobi_counter)
    assert t_j2.prev_trace_sha256 == t_j1.trace_sha256
    assert t_j2.state_snapshot["zoe"]["seen_neighbor_sum"] == 6
    assert t_j2.state_snapshot["mono"]["seen_neighbor_sum"] == 2
    assert mesh_1.verify_integrity()["ok"] is True


def test_zero_token_mesh_routing_and_hex_sister_council() -> None:
    mesh = build_default_zoe_mesh()
    route_res = route_prompt_on_mesh(
        mesh, "Verify SHA-256 SAR drone telemetry safety lock"
    )
    assert route_res["lead_cell"] == "mono"
    assert route_res["tokens_used"] == 0
    assert route_res["cloud_cost_usd"] == 0.0
    assert route_res["external_actions"] == 0
    assert route_res["advisory_only"] is True
    assert route_res["sentience_claimed"] is False
    assert route_res["constitutional"]["epistemic_lane"] == "advisory_proposal"
    assert len(route_res["enqueued_messages"]) >= 1

    council_res = run_hex_sister_council(
        mesh, "Pediatric H3K27M botanical compound screen", ticks=2
    )
    assert council_res["ticks_executed"] == 2
    assert len(council_res["tick_trace_hashes"]) == 2
    assert len(council_res["council_mesh_sha256"]) == 64
    assert council_res["tokens_used"] == 0
    assert council_res["cloud_cost_usd"] == 0.0
    assert council_res["external_actions"] == 0
    assert council_res["advisory_only"] is True
    assert council_res["clinical_action_authorized"] is False
    assert council_res["sentience_claimed"] is False
    assert mesh.verify_integrity()["ok"] is True


# ---------------------------------------------------------------------------
# Group 6: SHA-256 Repeatability & Tamper Detection
# ---------------------------------------------------------------------------


def test_sha256_repeatability_sensitivity_and_tamper_detection() -> None:
    msg1 = HexMessage("m-1", 1, "zoe", "gemma", "sync", {"a": 1, "b": -0.0})
    msg2 = HexMessage("m-1", 1, "zoe", "gemma", "sync", {"b": 0.0, "a": 1})
    assert len(msg1.sha256) == 64
    assert msg1.sha256 == msg1.sha256.lower()
    assert msg1.sha256 == msg2.sha256  # key-order & -0.0 normalization invariance
    assert msg1.verify_sha256() is True

    # Modifying any field alters SHA-256
    assert msg1.sha256 != HexMessage("m-1", 1, "zoe", "gemma", "sync", {"a": 2}).sha256
    assert msg1.sha256 != HexMessage("m-1", 1, "zoe", "gemma", "other", {"a": 1}).sha256
    assert msg1.sha256 != HexMessage("m-1", 2, "zoe", "gemma", "sync", {"a": 1}).sha256
    assert (
        msg1.sha256
        != HexMessage(
            "m-1", 1, "zoe", "gemma", "sync", {"a": 1}, epistemic_lane="evidence"
        ).sha256
    )

    # Supplying wrong sha256 at construction raises TamperDetectedError
    with pytest.raises(TamperDetectedError):
        HexMessage("m-1", 1, "zoe", "gemma", "sync", {"a": 1}, sha256="0" * 64)

    # Mutating delivered message payload triggers TamperDetectedError
    mesh = build_default_zoe_mesh()
    sent = mesh.send_neighbor_message("zoe", "gemma", "draft", {"x": 10})
    tick_res = mesh.step_coupled_tick()
    assert tick_res.tamper_evidence_only is True
    assert tick_res.authentication_proof is False
    assert tick_res.hash_chain_semantics == HASH_CHAIN_SEMANTICS
    assert verify_trace_digest(tick_res) is True

    sent.payload["x"] = 999
    with pytest.raises(TamperDetectedError):
        sent.verify_sha256()
    with pytest.raises(TamperDetectedError):
        mesh.verify_integrity()
    report = mesh.verify_integrity(raise_on_error=False)
    assert report["ok"] is False
    assert report["tamper_evidence_only"] is True
    assert report["authentication_proof"] is False

    # Mutating tick state_snapshot also triggers TamperDetectedError
    mesh2 = build_default_zoe_mesh()
    res2 = mesh2.step_coupled_tick()
    res2.state_snapshot["zoe"]["last_tick"] = 999
    with pytest.raises(TamperDetectedError):
        verify_trace_digest(res2)
    with pytest.raises(TamperDetectedError):
        mesh2.verify_integrity()


# ---------------------------------------------------------------------------
# Group 7: NaN / Inf / Cycle / Malformed Input Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_float", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_rejected_everywhere(bad_float: float) -> None:
    with pytest.raises(ConstitutionalViolationError):
        validate_constitutional_packet({"nested": [1, {"val": bad_float}]})

    with pytest.raises(ConstitutionalViolationError):
        sha256_canonical({"val": bad_float})

    mesh = build_default_zoe_mesh()
    with pytest.raises(ConstitutionalViolationError):
        mesh.send_neighbor_message("zoe", "gemma", "bad_float", {"v": bad_float})

    # coupling_fn returning NaN/Inf must fail cleanly without mutating mesh tick
    with pytest.raises(ConstitutionalViolationError):
        mesh.step_coupled_tick(lambda _cell, _nbs: {"score": bad_float})
    assert mesh.tick == 0


def test_circular_references_non_string_keys_and_bool_int_slots_rejected() -> None:
    circular_dict: dict[str, Any] = {}
    circular_dict["self"] = circular_dict
    with pytest.raises(ConstitutionalViolationError, match="circular reference"):
        validate_constitutional_packet(circular_dict)

    circular_list: list[Any] = []
    circular_list.append(circular_list)
    with pytest.raises(ConstitutionalViolationError, match="circular reference"):
        validate_constitutional_packet({"items": circular_list})

    # Shared non-circular DAG reference is valid
    shared = {"leaf": 42}
    dag = validate_constitutional_packet({"left": shared, "right": shared})
    assert dag == {"left": {"leaf": 42}, "right": {"leaf": 42}}

    # Non-string mapping keys rejected
    with pytest.raises(ConstitutionalViolationError, match="strings"):
        bad_packet: Any = {1: "bad"}
        validate_constitutional_packet(bad_packet)

    # bool passed as tick rejected
    with pytest.raises(ConstitutionalViolationError):
        HexMessage("m-bool", True, "zoe", "gemma", "t", {"v": 1})

    # bool in external_actions / tokens_used rejected
    with pytest.raises(ConstitutionalViolationError):
        validate_constitutional_packet({"external_actions": False})
    with pytest.raises(ConstitutionalViolationError):
        validate_constitutional_packet({"tokens_used": True})


# ---------------------------------------------------------------------------
# Group 8: Constitutional Guards & Epistemic Firewall
# ---------------------------------------------------------------------------


def test_constitutional_metadata_all_13_keys_and_epistemic_lanes() -> None:
    expected_keys = {
        "advisory_only": True,
        "read_only": True,
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
        "attribution": ATTRIBUTION_TEXT,
    }
    for lane in sorted(ALLOWED_EPISTEMIC_LANES):
        meta = constitutional_metadata(lane)
        for key, val in expected_keys.items():
            assert meta[key] == val
        assert meta["epistemic_lane"] == lane
        assert meta["measurement_lane_only"] is (lane == "measurement")
        assert meta["tamper_evidence_only"] is True
        assert meta["authentication_proof"] is False
        assert meta["hash_chain_semantics"] == HASH_CHAIN_SEMANTICS
        assert validate_constitutional_packet(meta, require_metadata=True) == meta

    for bad_lane in ("action", "ACTION", "autonomous_action", "execute", "actuation", "", "unknown"):
        with pytest.raises(EpistemicFirewallError):
            validate_epistemic_lane(bad_lane)
        with pytest.raises(EpistemicFirewallError):
            constitutional_metadata(bad_lane)


@pytest.mark.parametrize(
    "tampered_override",
    [
        {"external_actions": 1},
        {"tokens_used": 5},
        {"cloud_cost_usd": 0.01},
        {"advisory_only": False},
        {"loopback_only": False},
        {"sentience_claimed": True},
        {"l5_agi_qualified": True},
        {"zoe_clone_claimed": True},
        {"clinical_action_authorized": True},
        {"flight_control_authorized": True},
        {"cure_claim": True},
        {"autonomous_execution_allowed": True},
        {"execute": True},
        {"auto_execute": True},
        {"epistemic_lane": "action"},
        {"attribution": "Someone Else"},
    ],
)
def test_validate_constitutional_packet_rejects_safety_overrides(
    tampered_override: dict[str, Any],
) -> None:
    with pytest.raises(ConstitutionalViolationError):
        validate_constitutional_packet(tampered_override)
    # Also rejected when nested inside a sub-object
    with pytest.raises(ConstitutionalViolationError):
        validate_constitutional_packet({"nested": {"meta": tampered_override}})


def test_validate_constitutional_packet_require_metadata_rejects_incomplete() -> None:
    with pytest.raises(ConstitutionalViolationError, match="missing required keys"):
        validate_constitutional_packet({"advisory_only": True}, require_metadata=True)

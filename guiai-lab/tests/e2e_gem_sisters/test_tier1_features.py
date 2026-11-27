"""Tier 1: Isolated feature happy-path E2E tests (65 tests = 5 per feature #1-#13)."""
from __future__ import annotations

from collections import deque
from dataclasses import is_dataclass
import hashlib
from pathlib import Path
import struct
from typing import Any

import pytest

from .conftest import (
    ATTRIBUTION_EXPECTED,
    CANONICAL_SISTER_NAMES,
    CANONICAL_SISTER_SIGNETS,
    EDDBMS_DOMAIN_MODULES,
    REPO_ROOT,
    aes_enqueue_message,
    aes_objc_change,
    aes_wind_create,
    aes_wind_open,
    assert_constitutional_metadata,
    assert_full_contract_metadata,
    assert_m1_m4_constitutional_record,
    assert_sister_safety_invariants,
    call_with_supported_kwargs,
    build_default_hex_mesh,
    export_workbench_gem,
    get_mesh_cells,
    import_contract_module,
    minimal_elf64_bytes,
    pick,
    sample_fes_kwargs,
    sample_python_source,
)

pytestmark = pytest.mark.tier1


# ============================================================================
# Feature #1: Hexagonal Axial/Cube Grid & Shared-Wall Adjacency (M1)
# ============================================================================

def test_t1_f01_hex_directions_and_cube_invariant() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    HEX_DIRECTIONS = getattr(hex_mod, "HEX_DIRECTIONS")
    HexCoord = getattr(hex_mod, "HexCoord")

    assert len(HEX_DIRECTIONS) == 6
    assert tuple(HEX_DIRECTIONS) == (
        ("N", 0, -1),
        ("NE", 1, -1),
        ("SE", 1, 0),
        ("S", 0, 1),
        ("SW", -1, 1),
        ("NW", -1, 0),
    )
    for q, r in ((0, 0), (1, -1), (-2, 3), (4, -1), (-3, -2)):
        coord = HexCoord(q=q, r=r)
        assert coord.q == q
        assert coord.r == r
        assert coord.s == -q - r
        assert coord.q + coord.r + coord.s == 0


def test_t1_f01_hex_distance_and_neighbor_step() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    HEX_DIRECTIONS = getattr(hex_mod, "HEX_DIRECTIONS")
    HexCoord = getattr(hex_mod, "HexCoord")

    origin = HexCoord(0, 0)
    assert origin.distance(origin) == 0
    for direction, dq, dr in HEX_DIRECTIONS:
        step1 = origin.neighbor(direction)
        assert step1.q == dq and step1.r == dr
        assert origin.distance(step1) == 1
        assert step1.distance(origin) == 1
        step2 = step1.neighbor(direction)
        assert origin.distance(step2) == 2


def test_t1_f01_default_mesh_contains_nine_connected_cells() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)

    cell_list = list(get_mesh_cells(mesh).values())
    assert len(cell_list) == 9

    coords = {(c.coord.q, c.coord.r) for c in cell_list}
    assert len(coords) == 9

    zoe_cells = [c for c in cell_list if c.sister.name == "Zoe"]
    assert len(zoe_cells) == 1
    assert (zoe_cells[0].coord.q, zoe_cells[0].coord.r) == (0, 0)

    # BFS reachability across shared walls proves connected honeycomb
    start_id = zoe_cells[0].cell_id
    visited = {start_id}
    queue = deque([start_id])
    while queue:
        cur = queue.popleft()
        for nbr in mesh.neighbors(cur):
            if nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)
    assert len(visited) == 9


def test_t1_f01_shared_walls_symmetry_and_opposite_direction() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    HEX_DIRECTIONS = getattr(hex_mod, "HEX_DIRECTIONS")
    HexCollaborationMesh = getattr(hex_mod, "HexCollaborationMesh")

    dir_idx = {name: idx for idx, (name, _, _) in enumerate(HEX_DIRECTIONS)}
    mesh = build_default_hex_mesh(hex_mod)
    cell_map = get_mesh_cells(mesh)

    for cid, cell in cell_map.items():
        nbrs = mesh.neighbors(cid)
        assert len(nbrs) >= 2
        for nid in nbrs:
            assert cid in mesh.neighbors(nid)
            assert cell.coord.distance(cell_map[nid].coord) == 1

    walls = mesh.shared_walls()
    assert len(walls) >= 12
    for cell_a, dir_ab, cell_b in walls:
        assert cell_a != cell_b
        assert dir_ab in dir_idx
        opp_dir = HEX_DIRECTIONS[(dir_idx[dir_ab] + 3) % 6][0]
        assert cell_map[cell_a].coord.neighbor(dir_ab) == cell_map[cell_b].coord
        assert cell_map[cell_b].coord.neighbor(opp_dir) == cell_map[cell_a].coord


def test_t1_f01_neighbors_sorted_deterministically_by_sister_slot() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh1 = build_default_hex_mesh(hex_mod)
    mesh2 = build_default_hex_mesh(hex_mod)

    cell_map1 = get_mesh_cells(mesh1)
    for cid in cell_map1:
        nbrs1 = mesh1.neighbors(cid)
        nbrs2 = mesh2.neighbors(cid)
        assert isinstance(nbrs1, tuple)
        assert nbrs1 == nbrs2
        slots = [cell_map1[nid].sister.slot for nid in nbrs1]
        assert slots == sorted(slots)


# ============================================================================
# Feature #2: Deterministic Neighbor-Coupled State & Message Exchange (M1)
# ============================================================================

def test_t1_f02_send_neighbor_message_across_shared_wall() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cell_map = get_mesh_cells(mesh)

    sender_id = next(cid for cid, c in cell_map.items() if c.sister.name == "Zoe")
    receiver_id = mesh.neighbors(sender_id)[0]

    msg = mesh.send_neighbor_message(sender_id, receiver_id, topic="sync", payload={"v": 1})
    assert msg.sender_id == sender_id
    assert msg.receiver_id == receiver_id
    assert msg.topic == "sync"
    assert msg.payload == {"v": 1}
    assert msg.epistemic_lane == "measurement"
    assert len(msg.sha256) == 64 and all(ch in "0123456789abcdef" for ch in msg.sha256.lower())
    assert msg.message_id


def test_t1_f02_route_message_shortest_shared_wall_hops() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cell_map = get_mesh_cells(mesh)

    pair = None
    cids = sorted(cell_map.keys())
    for a in cids:
        for b in cids:
            if cell_map[a].coord.distance(cell_map[b].coord) >= 2:
                pair = (a, b)
                break
        if pair is not None:
            break
    assert pair is not None
    src, dst = pair
    dist = cell_map[src].coord.distance(cell_map[dst].coord)

    hops = mesh.route_message(src, dst, topic="handoff", payload={"step": 42})
    assert len(hops) == dist
    assert hops[0].sender_id == src
    assert hops[-1].receiver_id == dst
    for idx, hop in enumerate(hops):
        assert cell_map[hop.sender_id].coord.distance(cell_map[hop.receiver_id].coord) == 1
        if idx > 0:
            assert hops[idx - 1].receiver_id == hop.sender_id


def test_t1_f02_step_coupled_tick_canonical_delivery() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cell_map = get_mesh_cells(mesh)

    cids = sorted(cell_map.keys(), key=lambda c: cell_map[c].sister.slot)
    rev_before = {cid: cell_map[cid].revision for cid in cids}

    # Queue messages in reverse slot order to verify canonical sorting by (tick, sender_slot, receiver_slot)
    queued_pairs = []
    for cid in reversed(cids):
        nbr = mesh.neighbors(cid)[-1]
        mesh.send_neighbor_message(cid, nbr, topic="tick_probe", payload={"from": cid})
        queued_pairs.append((cell_map[cid].sister.slot, cell_map[nbr].sister.slot))

    result = mesh.step_coupled_tick()
    delivered = pick(result, "delivered_messages", "messages", "delivered")
    assert len(delivered) == len(queued_pairs)
    order_keys = [
        (m.tick, cell_map[m.sender_id].sister.slot, cell_map[m.receiver_id].sister.slot)
        for m in delivered
    ]
    assert order_keys == sorted(order_keys)

    cell_map_after = get_mesh_cells(mesh)
    assert any(cell_map_after[cid].revision > rev_before[cid] for cid in cids)
    assert_m1_m4_constitutional_record(result, require_advisory=True)


def test_t1_f02_custom_coupling_fn_deterministic_state_update() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cell_map = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cell_map.items() if c.sister.name == "Zoe")
    nbr_id = mesh.neighbors(zoe_id)[0]

    mesh.send_neighbor_message(nbr_id, zoe_id, topic="signal", payload={"energy": 7})

    def coupling_fn(cell: Any, neighbor_states: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {
            "neighbor_count": len(neighbor_states),
            "last_slot": cell.sister.slot,
            "neighbor_keys": sorted(neighbor_states.keys()),
        }

    result = mesh.step_coupled_tick(coupling_fn=coupling_fn)
    assert result is not None
    cell_map_after = get_mesh_cells(mesh)
    zoe_state = cell_map_after[zoe_id].state
    assert zoe_state["neighbor_count"] == len(mesh.neighbors(zoe_id))
    assert zoe_state["neighbor_keys"] == sorted(mesh.neighbors(zoe_id))


def test_t1_f02_sha256_trace_replay_determinism() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")

    def run_sequence() -> tuple[str, dict[str, dict[str, Any]]]:
        mesh = build_default_hex_mesh(hex_mod)
        cell_map = get_mesh_cells(mesh)
        zoe_id = next(cid for cid, c in cell_map.items() if c.sister.name == "Zoe")
        for nbr in mesh.neighbors(zoe_id)[:2]:
            mesh.send_neighbor_message(zoe_id, nbr, topic="replay", payload={"x": 1})
        tick_res = mesh.step_coupled_tick()
        digest = pick(tick_res, "trace_sha256", "sha256", "digest")
        cmap = get_mesh_cells(mesh)
        return str(digest), {cid: dict(c.state) for cid, c in cmap.items()}

    digest_a, states_a = run_sequence()
    digest_b, states_b = run_sequence()
    assert len(digest_a) == 64
    assert digest_a == digest_b
    assert states_a == states_b


# ============================================================================
# Feature #3: 9-Sister Registry & Routing Alignment (zoe_sisters + M1)
# ============================================================================

def test_t1_f03_canonical_nine_sisters_exact_roster() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    ZOE_SISTERS = sisters_mod.ZOE_SISTERS
    listed = sisters_mod.list_sisters()

    assert len(ZOE_SISTERS) == 9
    assert len(listed) == 9
    assert tuple(s.slot for s in listed) == tuple(range(1, 10))
    assert tuple(s.name for s in listed) == CANONICAL_SISTER_NAMES
    assert tuple(s.signet for s in listed) == CANONICAL_SISTER_SIGNETS


def test_t1_f03_resolve_sister_and_emblem_bijection() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    for idx, (name, signet) in enumerate(zip(CANONICAL_SISTER_NAMES, CANONICAL_SISTER_SIGNETS), start=1):
        by_name = sisters_mod.resolve_sister(name)
        by_signet = sisters_mod.sister_for_emblem(signet)
        by_slot = sisters_mod.resolve_sister(str(idx))
        assert by_name == by_signet == by_slot
        assert by_name.slot == idx


def test_t1_f03_zero_token_prompt_routing_and_council() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    prompts = (
        "hexagonal spatial packing and VDI drafting",
        "hardware KVM UMA bridge timing verification",
        "formal proof verification and 1-bit invariant check",
    )
    for prompt in prompts:
        routed = sisters_mod.route_prompt_to_sister(prompt)
        assert routed["lead"] in sisters_mod.ZOE_SISTERS
        assert routed["support"] in sisters_mod.ZOE_SISTERS
        assert routed["verifier"] in sisters_mod.ZOE_SISTERS
        assert routed["lead"].signet != routed["support"].signet
        assert routed["tokens_used"] == 0
        assert float(routed["cloud_cost_usd"]) == 0.0
        assert_sister_safety_invariants(routed)

        council = sisters_mod.run_sister_council(prompt)
        assert len(council["seats"]) == 3
        assert council["tokens_used"] == 0
        assert float(council["cloud_cost_usd"]) == 0.0
        assert_sister_safety_invariants(council)


def test_t1_f03_mesh_binds_all_nine_sisters_with_domain_modules() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cell_list = list(get_mesh_cells(mesh).values())

    bound_names = {c.sister.name for c in cell_list}
    bound_slots = {c.sister.slot for c in cell_list}
    assert bound_names == set(CANONICAL_SISTER_NAMES)
    assert bound_slots == set(range(1, 10))
    for c in cell_list:
        assert c.sister in sisters_mod.ZOE_SISTERS
        assert isinstance(c.domain_module, str) and len(c.domain_module.strip()) > 0


def test_t1_f03_hardware_profile_sister_pairing_deterministic() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    assert_sister_safety_invariants(sisters_mod.SAFETY_INVARIANTS)
    for profile in ("KVM_UMA_SPLIT", "MICRO_HUD_HEADLAMP"):
        r1 = sisters_mod.recommend_sisters_for_hardware(profile)
        r2 = sisters_mod.recommend_sisters_for_hardware(profile)
        assert r1 == r2
        assert len(r1) >= 3
        assert all(spec in sisters_mod.ZOE_SISTERS for spec in r1)


# ============================================================================
# Feature #4: FunctionEngineeringSpecification Intake (M2)
# ============================================================================

def test_t1_f04_spec_dataclass_fields_and_defaults() -> None:
    FES = import_contract_module("guiai.gem.zoe_eddms", "FunctionEngineeringSpecification")
    kwargs = sample_fes_kwargs("FES-004A")
    kwargs.pop("special_instructions")
    spec: Any = FES(**kwargs)

    assert spec.spec_id == "FES-004A"
    assert spec.title == kwargs["title"]
    assert spec.objective == kwargs["objective"]
    assert spec.owner == kwargs["owner"]
    assert spec.special_instructions == ""
    assert is_dataclass(spec)


def test_t1_f04_ingest_specification_creates_revision_one_record() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-004B"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)

    assert record.revision == 1
    assert record.spec_id == "FES-004B"
    assert len(record.record_sha256) == 64
    assert record.general.design_id
    assert record.properties is not None
    assert record.geometric is not None
    assert_m1_m4_constitutional_record(record, require_advisory=True)


def test_t1_f04_ingest_unidirectional_feeds_central_material_and_product() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-004C"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)
    design_id = record.general.design_id

    mat_view = db.read_for_module(design_id, "MATERIAL_DESIGN")
    prod_view = db.read_for_module(design_id, "PRODUCT_DESIGN_AND_PLANNING")
    assert mat_view
    assert prod_view
    assert "FES-004C" in repr(mat_view) or design_id in repr(mat_view)
    assert "FES-004C" in repr(prod_view) or design_id in repr(prod_view)


def test_t1_f04_ingest_preserves_special_instructions_and_constraints() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    kwargs = sample_fes_kwargs("FES-004D")
    kwargs["special_instructions"] = "Verify 112k optical mesh tolerances before prototyping."
    kwargs["constraints"] = {"max_mass_g": 95.0, "ip_rating": "IP67"}
    spec = eddms.FunctionEngineeringSpecification(**kwargs)

    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)
    assert "112k optical mesh tolerances" in record.general.special_instructions
    dp_view = db.read_for_module(record.general.design_id, "DESIGN_PARAMETERS")
    assert "95.0" in repr(dp_view) or "IP67" in repr(dp_view)


def test_t1_f04_ingest_records_unidirectional_provenance_entry() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-004E"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)

    assert len(record.provenance_log) >= 1
    first_entry = record.provenance_log[0]
    assert "FES-004E" in repr(first_entry) or "ingest" in repr(first_entry).lower()
    assert_constitutional_metadata(first_entry, require_advisory=True, require_keys=False)
    assert pick(first_entry, "epistemic_lane", "measurement_lane_only", "advisory_only", "constitutional", default=None) is not None


# ============================================================================
# Feature #5: Central EngineeringDesignDatabase (M2)
# ============================================================================

def test_t1_f05_general_data_schema_fields() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-005A"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)

    gen = record.general
    assert isinstance(gen, eddms.GeneralData)
    assert gen.design_id
    assert gen.product_id
    assert isinstance(gen.owner_metadata, dict)
    assert isinstance(gen.special_instructions, str)
    assert isinstance(gen.commerce_info, dict)


def test_t1_f05_property_data_macro_micro_mechanical_physical() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-005B"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)
    design_id = record.general.design_id

    updated = db.write_from_module(
        design_id,
        "MATERIAL_DESIGN",
        "Tetra",
        {
            "properties": {
                "structure_desc": {"macro": "honeycomb-lattice", "micro": "Ti-6Al-4V grain"},
                "mechanical_desc": {"yield_mpa": 880.0, "youngs_gpa": 114.0},
                "physical_desc": {"density_g_cm3": 4.43},
            }
        },
        expected_revision=1,
    )
    assert isinstance(updated.properties, eddms.PropertyData)
    assert updated.properties.structure_desc["macro"] == "honeycomb-lattice"
    assert updated.properties.mechanical_desc["yield_mpa"] == pytest.approx(880.0)
    assert updated.properties.physical_desc["density_g_cm3"] == pytest.approx(4.43)


def test_t1_f05_geometric_data_all_four_subformats() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-005C"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)

    updated = db.write_from_module(
        record.general.design_id,
        "DESIGN_PARAMETERS",
        "Gemma",
        {
            "geometric": {
                "geom_2d": {"profile": "hex_outline", "vertices": [[0, 0], [10, 0], [15, 9]]},
                "geom_3d": {"envelope_mm": [48.0, 32.0, 24.0]},
                "mesh_data": {"elements": 112000, "topology": "hex"},
                "analysis_process_formats": {"fea": {"solver": "static_offline", "advisory_only": True}},
            }
        },
        expected_revision=1,
    )
    geom = updated.geometric
    assert isinstance(geom, eddms.GeometricData)
    assert geom.geom_2d["profile"] == "hex_outline"
    assert geom.geom_3d["envelope_mm"] == [48.0, 32.0, 24.0]
    assert geom.mesh_data["elements"] == 112000
    assert geom.analysis_process_formats["fea"]["solver"] == "static_offline"


def test_t1_f05_revision_increment_and_sha256_change_on_write() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-005D"))
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(spec)
    r2 = db.write_from_module(
        r1.general.design_id,
        "MATERIAL_DESIGN",
        "Tetra",
        {"properties": {"physical_desc": {"mass_g": 82.5}}},
        expected_revision=1,
    )
    r3 = db.write_from_module(
        r1.general.design_id,
        "HUMAN_MODEL",
        "Flora",
        {"properties": {"structure_desc": {"ergonomic_fit": "95th_percentile"}}},
        expected_revision=2,
    )
    assert (r1.revision, r2.revision, r3.revision) == (1, 2, 3)
    assert len({r1.record_sha256, r2.record_sha256, r3.record_sha256}) == 3


def test_t1_f05_provenance_log_append_only_history() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-005E"))
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(spec)
    r2 = db.write_from_module(
        r1.general.design_id,
        "DESIGN_PARAMETERS",
        "Tosi",
        {"geometric": {"geom_2d": {"tolerance_mm": 0.05}}},
        expected_revision=1,
    )
    r3 = db.write_from_module(
        r1.general.design_id,
        "PRODUCT_DESIGN_AND_PLANNING",
        "Gemma",
        {"general": {"commerce_info": {"batch_size": 12}}},
        expected_revision=2,
    )
    assert len(r3.provenance_log) > len(r2.provenance_log) > len(r1.provenance_log) - 1
    log_text = repr(r3.provenance_log)
    assert "Tosi" in log_text and "Gemma" in log_text
    assert "DESIGN_PARAMETERS" in log_text and "PRODUCT_DESIGN_AND_PLANNING" in log_text


# ============================================================================
# Feature #6: 6 Bidirectional Domain Spokes & Right-Column Pipeline (M2)
# ============================================================================

def test_t1_f06_all_six_domain_modules_readable() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-006A"))
    db = eddms.EngineeringDesignDatabase()
    record = db.ingest_specification(spec)
    for mod_name in EDDBMS_DOMAIN_MODULES:
        view = db.read_for_module(record.general.design_id, mod_name)
        assert isinstance(view, dict)
        assert_constitutional_metadata(view, require_advisory=True, require_keys=False)
        assert pick(view, "epistemic_lane", "measurement_lane_only", "advisory_only", "constitutional", default=None) is not None


def test_t1_f06_bidirectional_write_and_readback_per_spoke() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-006B"))
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(spec)
    did = r1.general.design_id

    r2 = db.write_from_module(
        did, "HUMAN_MODEL", "Flora",
        {"properties": {"structure_desc": {"headlamp_stride": "ergo-v2"}}},
        expected_revision=1,
    )
    r3 = db.write_from_module(
        did, "DESIGN_PARAMETERS", "Tosi",
        {"geometric": {"geom_3d": {"clearance_mm": 1.25}}},
        expected_revision=r2.revision,
    )
    r4 = db.write_from_module(
        did, "MATERIAL_DESIGN", "Tetra",
        {"properties": {"mechanical_desc": {"fatigue_cycles": 100000}}},
        expected_revision=r3.revision,
    )
    assert r4.revision == 4
    pm_view = db.read_for_module(did, "PROJECT_MANAGEMENT")
    assert "ergo-v2" in repr(pm_view) or "100000" in repr(pm_view)
    assert "1.25" in repr(r4.geometric.geom_3d)


def test_t1_f06_right_column_sequential_pipeline_valid_transitions() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-006C"))
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(spec)
    did = r1.general.design_id

    s1 = db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")
    s2 = db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "POSTPRODUCTION_MANAGEMENT", "Sage")
    assert "PROJECT_MANAGEMENT" in repr(s1)
    assert "POSTPRODUCTION_MANAGEMENT" in repr(s2)
    post_view = db.read_for_module(did, "POSTPRODUCTION_MANAGEMENT")
    assert post_view


def test_t1_f06_run_sister_eddms_cycle_binds_all_nine_sisters() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    mesh = build_default_hex_mesh(hex_mod)
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-006D"))

    cycle = eddms.run_sister_eddms_cycle(mesh, spec, ticks=2)
    cycle_repr = repr(cycle)
    for sister_name in CANONICAL_SISTER_NAMES:
        assert sister_name in cycle_repr, f"Sister {sister_name} missing from cycle run"
    record = pick(cycle, "record", "design_record")
    assert record.revision >= 2


def test_t1_f06_cycle_result_sha256_and_constitutional_metadata() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    mesh1 = build_default_hex_mesh(hex_mod)
    mesh2 = build_default_hex_mesh(hex_mod)
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-006E"))

    c1 = eddms.run_sister_eddms_cycle(mesh1, spec, ticks=2)
    c2 = eddms.run_sister_eddms_cycle(mesh2, spec, ticks=2)
    rec1 = pick(c1, "record", "design_record")
    rec2 = pick(c2, "record", "design_record")
    assert len(rec1.record_sha256) == 64
    assert rec1.record_sha256 == rec2.record_sha256
    assert_m1_m4_constitutional_record(c1, require_advisory=True)
    assert_m1_m4_constitutional_record(rec1, require_advisory=True)
    meta_fn = getattr(c1, "constitutional_metadata", None)
    meta = meta_fn() if callable(meta_fn) else pick(c1, "safety_invariants", "constitutional")
    assert_full_contract_metadata(meta)


# ============================================================================
# Feature #7: GEM AES Lifecycle & 16-Byte FIFO Message Pipe (M3 + seasip_gem)
# ============================================================================

def test_t1_f07_appl_init_and_appl_exit_lifecycle() -> None:
    GemAesApplication = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemAesApplication")
    app = GemAesApplication()
    ap_id = app.appl_init()
    assert isinstance(ap_id, int) and ap_id >= 0
    exited = app.appl_exit()
    assert exited in (0, 1, True, None)


def test_t1_f07_fifo_16_byte_message_pack_unpack() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)

    app = core.GemAesApplication()
    app.appl_init()
    packets = [
        seasip.encode_aes_message(seasip.MN_SELECTED, sender_apid=1, w3=3, w4=12),
        seasip.encode_aes_message(seasip.WM_REDRAW, sender_apid=0, w3=1, w4=10, w5=20, w6=100, w7=80),
        seasip.encode_aes_message(seasip.AC_OPEN, sender_apid=0, w3=0, w4=7),
        seasip.encode_aes_message(seasip.AC_CLOSE, sender_apid=0, w3=7),
    ]
    assert all(len(pkt) == 16 for pkt in packets)
    for pkt in packets:
        aes_enqueue_message(app, pkt)

    received_types = []
    for _ in packets:
        ev = app.evnt_multi(MU_MESAG)
        msg = pick(ev, "msg", "message", "msg_words")
        if isinstance(msg, (bytes, bytearray)):
            msg_type = struct.unpack("<8h", msg)[0]
        elif isinstance(msg, dict):
            msg_type = msg["msg_type"]
        else:
            msg_type = msg[0]
        received_types.append(msg_type)
    assert received_types == [seasip.MN_SELECTED, seasip.WM_REDRAW, seasip.AC_OPEN, seasip.AC_CLOSE]
    app.appl_exit()


def test_t1_f07_evnt_multi_keyboard_and_button_flags() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    MU_KEYBD = getattr(core, "MU_KEYBD", 0x0001)
    MU_BUTTON = getattr(core, "MU_BUTTON", 0x0002)

    app = core.GemAesApplication()
    app.appl_init()
    push_key = getattr(app, "push_key_event", None) or getattr(app, "post_key_event", None) or getattr(app, "inject_key", None)
    push_btn = getattr(app, "push_button_event", None) or getattr(app, "post_button_event", None) or getattr(app, "inject_button", None)
    if push_key is not None:
        call_with_supported_kwargs(push_key, key=0x1C0D, kreturn=0x1C0D, kstate=0)
        ev1 = call_with_supported_kwargs(app.evnt_multi, MU_KEYBD | MU_BUTTON)
    else:
        ev1 = call_with_supported_kwargs(
            app.evnt_multi, MU_KEYBD | MU_BUTTON,
            key_code=0x1C0D, kreturn=0x1C0D, kstate=0,
        )
    assert (pick(ev1, "matched_flags", "which", "events", "event_mask") & MU_KEYBD) != 0

    if push_btn is not None:
        call_with_supported_kwargs(push_btn, mx=120, my=80, x=120, y=80, button=1, bstate=1, clicks=1)
        ev2 = call_with_supported_kwargs(app.evnt_multi, MU_KEYBD | MU_BUTTON)
    else:
        ev2 = call_with_supported_kwargs(
            app.evnt_multi, MU_KEYBD | MU_BUTTON,
            mouse_x=120, mouse_y=80, mx=120, my=80, button_state=1, bstate=1, clicks=1,
        )
    assert (pick(ev2, "matched_flags", "which", "events", "event_mask") & MU_BUTTON) != 0
    app.appl_exit()


def test_t1_f07_evnt_multi_mouse_rect_m1_m2_and_timer() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    MU_M1 = getattr(core, "MU_M1", 0x0004)
    MU_M2 = getattr(core, "MU_M2", 0x0008)
    MU_TIMER = getattr(core, "MU_TIMER", 0x0020)

    app = core.GemAesApplication()
    app.appl_init()
    move_fn = getattr(app, "push_mouse_move", None) or getattr(app, "set_mouse_position", None) or getattr(app, "inject_mouse", None)
    if move_fn is not None:
        call_with_supported_kwargs(move_fn, mx=50, my=50, x=50, y=50)
    ev_m1 = call_with_supported_kwargs(
        app.evnt_multi, MU_M1 | MU_TIMER,
        m1_flag=0, m1_flags=0, m1_x=40, m1_y=40, m1_w=30, m1_h=30, m1_rect=(40, 40, 30, 30),
        mouse_x=50, mouse_y=50, timer_ms=0,
    )
    assert (pick(ev_m1, "matched_flags", "which", "events", "event_mask") & MU_M1) != 0

    ev_m2 = call_with_supported_kwargs(
        app.evnt_multi, MU_M2 | MU_TIMER,
        m2_flag=1, m2_flags=1, m2_x=200, m2_y=200, m2_w=20, m2_h=20, m2_rect=(200, 200, 20, 20),
        mouse_x=50, mouse_y=50, timer_ms=0,
    )
    assert (pick(ev_m2, "matched_flags", "which", "events", "event_mask") & MU_M2) != 0

    if move_fn is not None:
        call_with_supported_kwargs(move_fn, mx=10, my=10, x=10, y=10)
    ev_miss = call_with_supported_kwargs(
        app.evnt_multi, MU_M1 | MU_TIMER,
        m1_flag=0, m1_flags=0, m1_x=40, m1_y=40, m1_w=30, m1_h=30, m1_rect=(40, 40, 30, 30),
        mouse_x=10, mouse_y=10, timer_ms=0,
    )
    miss_flags = pick(ev_miss, "matched_flags", "which", "events", "event_mask")
    assert (miss_flags & MU_M1) == 0 and (miss_flags & MU_TIMER) != 0

    ev_t = call_with_supported_kwargs(app.evnt_multi, MU_TIMER, timer_ms=0)
    assert (pick(ev_t, "matched_flags", "which", "events", "event_mask") & MU_TIMER) != 0
    app.appl_exit()


def test_t1_f07_evnt_multi_wm_closed_and_extra_bytes_field() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)

    app = core.GemAesApplication()
    app.appl_init()
    pkt_closed = seasip.encode_aes_message(seasip.WM_CLOSED, sender_apid=2, extra_len=0, w3=4)
    pkt_ext = seasip.encode_aes_message(seasip.WM_REDRAW, sender_apid=3, extra_len=8, w3=1, w4=10, w5=20, w6=30, w7=40)
    aes_enqueue_message(app, pkt_closed)
    aes_enqueue_message(app, pkt_ext, extra_bytes=b"EXTDATA8")

    ev1 = app.evnt_multi(MU_MESAG)
    ev2 = app.evnt_multi(MU_MESAG)
    for ev, expected_extra, expected_w3 in ((ev1, 0, 4), (ev2, 8, 1)):
        msg = pick(ev, "msg", "message", "msg_words")
        if isinstance(msg, (bytes, bytearray)):
            words = list(struct.unpack("<8h", msg))
        elif isinstance(msg, dict):
            words = msg["words"]
        else:
            words = list(msg)
        assert len(words) == 8
        assert words[2] == expected_extra
        assert words[3] == expected_w3
    if hasattr(ev2, "extra_bytes_pending"):
        assert ev2.extra_bytes_pending == 8
    if callable(getattr(app, "appl_read", None)):
        assert app.appl_read(8) == b"EXTDATA8"
    app.appl_exit()


# ============================================================================
# Feature #8: GEM AES Window Manager & Rectangle-List Redraw (M3)
# ============================================================================

def test_t1_f08_wind_create_open_close_delete_lifecycle() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    mgr = core.GemAesWindowTreeManager()
    WF_WXYWH = getattr(core, "WF_WXYWH")
    WF_CXYWH = getattr(core, "WF_CXYWH")
    WF_TOP = getattr(core, "WF_TOP")

    wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 30, 300, 200)
    assert wid > 0
    aes_wind_open(mgr, wid, 20, 30, 300, 200)
    cur_rect = mgr.wind_get(wid, WF_CXYWH)
    work_rect = mgr.wind_get(wid, WF_WXYWH)
    top = mgr.wind_get(wid, WF_TOP)
    assert cur_rect is not None and work_rect is not None
    assert (top[0] if isinstance(top, tuple) else top) == wid
    mgr.wind_close(wid)
    mgr.wind_delete(wid)

    wid2 = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 30, 300, 200)
    assert wid2 > 0
    mgr.wind_delete(wid2)


def test_t1_f08_wind_calc_border_and_work_roundtrip() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    mgr = core.GemAesWindowTreeManager()
    WC_BORDER = getattr(core, "WC_BORDER", 0)
    WC_WORK = getattr(core, "WC_WORK", 1)
    kind = seasip.NAME | seasip.CLOSER | seasip.MOVER | seasip.SIZER

    work_in = (40, 60, 240, 160)
    border = mgr.wind_calc(WC_BORDER, kind, work_in)
    work_out = mgr.wind_calc(WC_WORK, kind, border)
    assert tuple(work_out) == work_in
    border_t = tuple(border)
    assert border_t[2] >= work_in[2] and border_t[3] >= work_in[3]


def test_t1_f08_wind_update_balanced_update_and_mctrl() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    mgr = core.GemAesWindowTreeManager()
    BEG_UPDATE = getattr(core, "BEG_UPDATE", 1)
    END_UPDATE = getattr(core, "END_UPDATE", 0)
    BEG_MCTRL = getattr(core, "BEG_MCTRL", 3)
    END_MCTRL = getattr(core, "END_MCTRL", 2)

    assert mgr.wind_update(BEG_UPDATE) in (0, 1, True, None)
    assert mgr.wind_update(BEG_MCTRL) in (0, 1, True, None)
    assert mgr.wind_update(END_MCTRL) in (0, 1, True, None)
    assert mgr.wind_update(END_UPDATE) in (0, 1, True, None)


def test_t1_f08_walk_redraw_rectangles_occluded_window() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    WF_WXYWH = getattr(core, "WF_WXYWH")
    mgr = core.GemAesWindowTreeManager()

    back = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 30, 300, 200)
    aes_wind_open(mgr, back, 20, 30, 300, 200)
    front = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 100, 60, 140, 120)
    aes_wind_open(mgr, front, 100, 60, 140, 120)

    dirty = (20, 30, 300, 200)
    wx, wy, ww, wh = tuple(mgr.wind_get(back, WF_WXYWH))
    ix0, iy0 = max(wx, dirty[0]), max(wy, dirty[1])
    ix1, iy1 = min(wx + ww, dirty[0] + dirty[2]), min(wy + wh, dirty[1] + dirty[3])
    fx, fy, fw, fh = (100, 60, 140, 120)
    occ_w = max(0, min(ix1, fx + fw) - max(ix0, fx))
    occ_h = max(0, min(iy1, fy + fh) - max(iy0, fy))
    expected_area = max(0, ix1 - ix0) * max(0, iy1 - iy0) - occ_w * occ_h

    rects = [tuple(r) for r in mgr.walk_redraw_rectangles(back, dirty)]
    assert len(rects) >= 1
    # Every yielded clip rectangle must lie inside dirty & work area, be pairwise disjoint,
    # stay outside front's interior, and cover exact unoccluded area.
    total_area = 0
    for idx, (rx, ry, rw, rh) in enumerate(rects):
        assert rw > 0 and rh > 0
        assert rx >= ix0 and ry >= iy0 and rx + rw <= ix1 and ry + rh <= iy1
        overlap_w = max(0, min(rx + rw, fx + fw) - max(rx, fx))
        overlap_h = max(0, min(ry + rh, fy + fh) - max(ry, fy))
        assert overlap_w * overlap_h == 0
        for ox, oy, ow, oh in rects[idx + 1:]:
            pw = max(0, min(rx + rw, ox + ow) - max(rx, ox))
            ph = max(0, min(ry + rh, oy + oh) - max(ry, oy))
            assert pw * ph == 0
        total_area += rw * rh
    assert expected_area > 0 and total_area == expected_area


def test_t1_f08_seven_simultaneous_windows_allowed() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    mgr = core.GemAesWindowTreeManager()

    handles = []
    for idx in range(seasip.MAX_AES_APP_WINDOWS):
        wx, wy, ww, wh = 10 + idx * 20, 20 + idx * 15, 220, 140
        wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, wx, wy, ww, wh)
        assert wid > 0
        aes_wind_open(mgr, wid, wx, wy, ww, wh)
        handles.append(wid)
    assert len(set(handles)) == 7
    found = mgr.wind_find(150, 120)
    assert found == handles[-1]


# ============================================================================
# Feature #9: GEM AES Object Tree, Form, Menu & Resource Manager (M3)
# ============================================================================

def test_t1_f09_object_tree_add_offset_find_draw_change() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    tree = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.NORMAL, 0, 10, 20, 200, 120),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.EXIT | seasip.LASTOB, seasip.NORMAL, "OK", 30, 40, 60, 24),
    ]
    extra = GemObject(-1, -1, -1, seasip.G_STRING, seasip.LASTOB, seasip.NORMAL, "Zoe", 12, 12, 80, 16)
    tree[1].ob_flags &= ~seasip.LASTOB
    tree.append(extra)
    ops.objc_add(tree, 0, 2)

    ox, oy = ops.objc_offset(tree, 1)
    assert (ox, oy) == (40, 60)
    assert ops.objc_find(tree, 0, 8, 50, 70) == 1
    aes_objc_change(ops, tree, 1, seasip.SELECTED, (0, 0, 640, 400))
    assert (tree[1].ob_state & seasip.SELECTED) != 0
    drawn = ops.objc_draw(tree, 0, 8, (0, 0, 640, 400))
    assert drawn is not None


def test_t1_f09_object_delete_and_order_reparent() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    tree = [
        GemObject(-1, 1, 2, seasip.G_BOX, 0, seasip.NORMAL, 0, 0, 0, 200, 120),
        GemObject(2, -1, -1, seasip.G_STRING, 0, seasip.NORMAL, "A", 10, 10, 40, 16),
        GemObject(0, -1, -1, seasip.G_STRING, seasip.LASTOB, seasip.NORMAL, "B", 10, 30, 40, 16),
    ]
    ops.objc_order(tree, 2, 0)
    assert tree[0].ob_head == 2
    ops.objc_delete(tree, 1)
    assert tree[0].ob_head == 2 and tree[0].ob_tail == 2


def test_t1_f09_form_center_and_form_do_exit_button() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject

    tree = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.OUTLINED, 0, 0, 0, 200, 100),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.DEFAULT | seasip.EXIT | seasip.LASTOB, seasip.NORMAL, "OK", 60, 60, 80, 24),
    ]
    cx, cy, cw, ch = core.form_center(tree)
    assert tree[0].ob_w == 200 and tree[0].ob_h == 100
    assert cw in (200, 206) and ch in (100, 106) and cx > 0 and cy > 0

    events = [{"type": "button", "x": tree[0].ob_x + 70, "y": tree[0].ob_y + 70, "clicks": 1}]
    res = call_with_supported_kwargs(core.form_do, tree, 0, events=events)
    exit_obj = res if isinstance(res, int) else int(pick(res, "exit_raw", "exit_obj"))
    assert (exit_obj & 0x7FFF) == 1


def test_t1_f09_menu_bar_icheck_ienable_tnormal() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject

    menu_tree = [
        GemObject(-1, 1, 2, seasip.G_IBOX, 0, seasip.NORMAL, 0, 0, 0, 640, 400),
        GemObject(2, -1, -1, seasip.G_TITLE, 0, seasip.NORMAL, "File", 10, 0, 50, 16),
        GemObject(0, -1, -1, seasip.G_STRING, seasip.LASTOB, seasip.NORMAL, "Audit", 10, 20, 80, 16),
    ]
    core.menu_bar(menu_tree, True)
    core.menu_icheck(menu_tree, 2, True)
    assert (menu_tree[2].ob_state & seasip.CHECKED) != 0
    core.menu_ienable(menu_tree, 2, False)
    assert (menu_tree[2].ob_state & seasip.DISABLED) != 0
    core.menu_tnormal(menu_tree, 1, False)
    assert (menu_tree[1].ob_state & seasip.SELECTED) != 0
    core.menu_tnormal(menu_tree, 1, True)
    assert (menu_tree[1].ob_state & seasip.SELECTED) == 0


def test_t1_f09_rsrc_load_gaddr_obfix_free_roundtrip(tmp_path: Path) -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    rsc_tree = seasip.GemObjectTree("MAIN_FORM", 20, 10)
    rsc_tree.add(seasip.G_BUTTON, 2, 2, 10, 2, flags=seasip.SELECTABLE | seasip.EXIT, text="Apply")
    rsc_bytes = seasip.compile_rsc([rsc_tree])
    rsc_file = tmp_path / "zoe_gem.rsc"
    rsc_file.write_bytes(rsc_bytes)

    handle = core.rsrc_load(str(rsc_file))
    assert handle
    loaded_tree = core.rsrc_gaddr(0, 0)
    assert len(loaded_tree) >= 2
    core.rsrc_obfix(loaded_tree, 1)
    assert loaded_tree[1].ob_w >= 10
    assert core.rsrc_free() in (0, 1, True, None)


# ============================================================================
# Feature #10: GEM VDI Workstation, NDC/RC, Clipping & Primitives (M3 + vdi)
# ============================================================================

def test_t1_f10_v_opnvwk_vq_extnd_and_v_clsvwk() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_sm = GemVdiStateMachine()
    work_in = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2]
    handle, work_out = vdi_sm.v_opnvwk(work_in)
    assert handle > 0
    assert len(work_out) == 57

    ext0 = vdi_sm.vq_extnd(0)
    ext1 = vdi_sm.vq_extnd(1)
    assert len(ext0) == 57 and len(ext1) == 57
    vdi_sm.v_clsvwk()


def test_t1_f10_ndc_vs_rc_coordinate_mapping() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_ndc = GemVdiStateMachine()
    vdi_ndc.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0])  # NDC
    rc_pt = vdi_ndc.ndc_to_rc(32767, 32767)
    assert rc_pt[0] > 0 and rc_pt[1] >= 0
    ndc_back = vdi_ndc.rc_to_ndc(*rc_pt)
    assert abs(ndc_back[0] - 32767) <= 64
    vdi_ndc.v_clsvwk()


def test_t1_f10_vs_clip_and_vswr_mode_setters() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    vdi_sm.vs_clip(1, (10, 10, 300, 200))
    for mode in (1, 2, 3, 4):
        assert vdi_sm.vswr_mode(mode) == mode
    vdi_sm.vsl_color(1)
    vdi_sm.vsl_type(1)
    vdi_sm.vsm_color(2)
    vdi_sm.vsf_color(3)
    vdi_sm.vsf_interior(1)
    vdi_sm.vst_color(1)
    vdi_sm.vs_clip(0, (0, 0, 0, 0))
    vdi_sm.v_clsvwk()


def test_t1_f10_vdi_primitives_and_gdp_shapes() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])

    vdi_sm.v_pline([(10, 10), (100, 80), (160, 40)])
    vdi_sm.v_pmarker([(50, 50), (90, 90)])
    vdi_sm.v_gtext(30, 30, "Zoe VDI")
    vdi_sm.v_bar((20, 20, 120, 100))
    vdi_sm.v_fillarea([(150, 50), (220, 50), (185, 110)])
    vdi_sm.v_rbox((240, 20, 340, 90))
    vdi_sm.v_rfbox((250, 100, 350, 170))
    vdi_sm.v_arc(400, 120, 40, 0, 1800)
    vdi_sm.v_pieslice(480, 120, 40, 0, 900)
    vdi_sm.v_circle(400, 240, 35)
    vdi_sm.v_ellarc(500, 240, 45, 25, 0, 2700)
    vdi_sm.v_ellipse(500, 320, 45, 25)

    stream = pick(vdi_sm, "commands", "recorded_commands", "command_stream")
    assert len(stream) >= 12
    vdi_sm.v_clsvwk()


def test_t1_f10_gem_metafile_emission_and_seasip_verification() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    vdi_sm.v_pline([(10, 10), (120, 10), (120, 90), (10, 90), (10, 10)])
    vdi_sm.v_bar((30, 30, 100, 70))
    vdi_sm.v_circle(200, 100, 30)
    vdi_sm.v_gtext(40, 120, "Balma & Fitler 1986")
    exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
    gem_bytes = exporter()
    vdi_sm.v_clsvwk()

    assert isinstance(gem_bytes, bytes) and len(gem_bytes) >= 50
    magic, hdr_words = struct.unpack_from("<2h", gem_bytes, 0)
    assert magic == -1 and hdr_words >= 24
    report = seasip.verify_seasip_gem_metafile(gem_bytes)
    assert report["valid"] is True


# ============================================================================
# Feature #11: Ablation Read-Only Static Analysis & Source Audit Bridge (M4)
# ============================================================================

def test_t1_f11_inspect_raw_bytes_readonly_zero_disk_cache() -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    raw = minimal_elf64_bytes()
    report = bridge.inspect_target_readonly(raw_bytes=raw, target_name="probe.bin")

    expected_sha = hashlib.sha256(raw).hexdigest()
    assert pick(report, "target_sha256", "sha256") == expected_sha
    assert pick(report, "advisory_only") is True
    assert pick(report, "read_only") is True
    assert pick(report, "external_actions") == 0
    assert_m1_m4_constitutional_record(report, require_advisory=True, require_read_only=True)


def test_t1_f11_inspect_python_source_file_via_forge_audit(tmp_path: Path) -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    py_file = tmp_path / "optical_probe.py"
    py_file.write_text(sample_python_source(), encoding="utf-8")

    bridge = AblationBridge()
    report = bridge.inspect_target_readonly(target_path=py_file, mode="source")
    assert pick(report, "advisory_only") is True
    assert pick(report, "read_only") is True
    findings = pick(report, "findings", "source_audit", "summary")
    assert findings is not None
    assert_m1_m4_constitutional_record(report, require_advisory=True, require_read_only=True)


def test_t1_f11_inspect_minimal_elf_binary_path(tmp_path: Path) -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    elf_file = tmp_path / "sample.elf"
    elf_file.write_bytes(minimal_elf64_bytes())

    bridge = AblationBridge()
    report = bridge.inspect_target_readonly(target_path=elf_file)
    assert pick(report, "advisory_only") is True
    assert pick(report, "read_only") is True
    assert pick(report, "target_sha256", "sha256") == hashlib.sha256(minimal_elf64_bytes()).hexdigest()


def test_t1_f11_zero_advisor_claude_and_zero_tokens(offline_guard: dict[str, int]) -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    report = bridge.inspect_target_readonly(raw_bytes=minimal_elf64_bytes(), target_name="zero_token.bin")

    assert pick(report, "tokens_used", "cloud_tokens_used") == 0
    assert float(pick(report, "cloud_cost_usd")) == 0.0
    assert pick(report, "external_actions") == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert offline_guard["non_loopback_blocked"] == 0


def test_t1_f11_attach_ablation_to_eddms_populates_analysis_and_structure() -> None:
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    db = eddms.EngineeringDesignDatabase()
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-011E"))
    record = db.ingest_specification(spec)

    bridge = bridge_mod.AblationBridge()
    report = bridge.inspect_target_readonly(raw_bytes=minimal_elf64_bytes(), target_name="firmware.elf")
    updated = bridge_mod.attach_ablation_to_eddms(
        db, record.general.design_id, report, sister_name="Mono", expected_revision=1,
    )
    assert updated.revision == 2
    ablation_geo = updated.geometric.analysis_process_formats["ablation"]
    ablation_prop = updated.properties.structure_desc["ablation_summary"]
    assert ablation_geo["advisory_only"] is True
    assert ablation_geo.get("epistemic_lane", "measurement") == "measurement"
    assert ablation_prop is not None
    assert_m1_m4_constitutional_record(updated, require_advisory=True)


# ============================================================================
# Feature #12: Collaborative GEM Workbench & CLI/GEM-Lab Integration (M4)
# ============================================================================

def test_t1_f12_create_workbench_and_window_budget() -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-012A"))
    wb = wb_mod.create_workbench(spec)
    snap = wb.snapshot_state()
    open_windows = pick(snap, "open_windows", "active_windows", "windows")
    win_count = len(open_windows) if isinstance(open_windows, (list, tuple, dict)) else int(open_windows)
    assert 1 <= win_count <= seasip.MAX_AES_APP_WINDOWS
    for sister_name in CANONICAL_SISTER_NAMES:
        assert sister_name in repr(snap)


def test_t1_f12_tick_collaboration_updates_hex_and_eddms() -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-012B"))
    wb = wb_mod.create_workbench(spec)
    before = wb.snapshot_state()
    call_with_supported_kwargs(wb.tick_collaboration, ticks=2)
    after = wb.snapshot_state()

    rev_before = pick(before, "eddms_revision", "revision")
    rev_after = pick(after, "eddms_revision", "revision")
    assert rev_after >= rev_before
    assert after != before


def test_t1_f12_workbench_render_vdi_svg_and_gem_metafile(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    wb = wb_mod.create_workbench()
    vdi_scene = wb.render_vdi_scene()
    svg_text = wb.render_svg()
    gem_path = tmp_path / "workbench_t1.gem"
    gem_bytes = export_workbench_gem(wb, gem_path)

    assert vdi_scene is not None
    assert isinstance(svg_text, str) and "<svg" in svg_text
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True


def test_t1_f12_lume_cli_sister_and_gem_slash_commands(tmp_path: Path) -> None:
    # Gate on M4 deliverable so progressive mode skips cleanly before M4 lands.
    import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    for cmd in ("/sister hex", "/sister eddbms", "/sister ablation", "/gem workbench"):
        handled, lines = cli.handle_slash(cmd, color=False)
        assert handled is True
        assert lines and len(lines) >= 1


def test_t1_f12_unified_cli_preserves_registry_and_atlas_counts() -> None:
    unified = import_contract_module("guiai.gem.unified")
    op_env = import_contract_module("guiai.gem.operating_environment")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    assert len(unified.COMPONENTS) == 17
    assert len(op_env.COMPONENT_MODULES) == 17
    assert len(op_env.ATLAS_MODULES) == 36
    assert seasip.MAX_AES_APP_WINDOWS == 7


# ============================================================================
# Feature #13: Constitutional Epistemic Firewall & Safety Guards (M1-M4, R5)
# ============================================================================

def test_t1_f13_all_m1_m4_outputs_expose_constitutional_metadata() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    ablation_bridge = import_contract_module("guiai.gem.zoe_ablation_bridge")
    workbench = import_contract_module("guiai.gem.zoe_gem_workbench")

    for mod in (hex_mod, eddms, core, ablation_bridge, workbench):
        meta_fn = getattr(mod, "constitutional_metadata", None)
        meta = meta_fn() if callable(meta_fn) else getattr(mod, "SAFETY_INVARIANTS")
        assert_full_contract_metadata(meta, require_read_only=(mod is ablation_bridge))


def test_t1_f13_epistemic_lane_firewall_never_auto_executes_action() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    ablation_bridge = import_contract_module("guiai.gem.zoe_ablation_bridge")
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")

    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cmap.items() if c.sister.name == "Zoe")
    msg = mesh.send_neighbor_message(zoe_id, mesh.neighbors(zoe_id)[0], "check", {"ok": True})
    tick_res = mesh.step_coupled_tick()

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-013B"))
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(spec)
    rep = ablation_bridge.AblationBridge().inspect_target_readonly(raw_bytes=minimal_elf64_bytes())
    wb = wb_mod.create_workbench(spec)
    snap = wb.snapshot_state()

    for artifact in (msg, tick_res, rec, rep, snap):
        assert_m1_m4_constitutional_record(artifact, require_advisory=True)


def test_t1_f13_attribution_credit_nicholas_michael_kloster() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    meta_fn = getattr(hex_mod, "constitutional_metadata", None)
    meta = meta_fn() if callable(meta_fn) else getattr(hex_mod, "SAFETY_INVARIANTS")
    assert ATTRIBUTION_EXPECTED in str(pick(meta, "attribution"))


def test_t1_f13_zero_real_home_ablation_or_zoe_writes(isolated_home: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    ablation_bridge = import_contract_module("guiai.gem.zoe_ablation_bridge")

    wb = wb_mod.create_workbench()
    wb.tick_collaboration()
    rep = ablation_bridge.AblationBridge().inspect_target_readonly(raw_bytes=minimal_elf64_bytes())
    assert pick(rep, "read_only") is True
    assert isolated_home.exists()
    # Teardown of `isolated_home` asserts real ~/.ablation, ~/.zoe, and settings.json are untouched.


def test_t1_f13_zero_non_loopback_network_and_zero_external_actions(offline_guard: dict[str, int]) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    wb = wb_mod.create_workbench()
    wb.tick_collaboration()
    snap = wb.snapshot_state()
    assert_m1_m4_constitutional_record(snap, require_advisory=True)
    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0

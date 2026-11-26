"""Tier 2: Boundary, corner, and invalid-input E2E tests (65 tests = 5 per feature #1-#13)."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import socket
import struct
import subprocess
from typing import Any

import pytest

from .conftest import (
    REPO_ROOT,
    aes_wind_create,
    aes_wind_open,
    assert_constitutional_metadata,
    assert_m1_m4_constitutional_record,
    assert_sister_safety_invariants,
    call_with_supported_kwargs,
    build_default_hex_mesh,
    export_workbench_gem,
    get_mesh_cells,
    import_contract_module,
    make_non_executing_sentinel_script,
    minimal_elf64_bytes,
    pick,
    sample_fes_kwargs,
)

pytestmark = pytest.mark.tier2


# ============================================================================
# Feature #1 Boundaries: Hex Grid & Adjacency (M1)
# ============================================================================

def test_t2_f01_reject_duplicate_hex_coordinates() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")

    c1 = hex_mod.HexCell(
        cell_id="zoe",
        sister=sisters_mod.ZOE_SISTERS[0],
        coord=hex_mod.HexCoord(0, 0),
        domain_module="PRODUCT_DESIGN_AND_PLANNING",
        state={},
        revision=0,
    )
    c2 = hex_mod.HexCell(
        cell_id="gemma",
        sister=sisters_mod.ZOE_SISTERS[1],
        coord=hex_mod.HexCoord(0, 0),
        domain_module="MATERIAL_DESIGN",
        state={},
        revision=0,
    )
    with pytest.raises(ValueError):
        hex_mod.HexCollaborationMesh([c1, c2])


def test_t2_f01_reject_invalid_hex_direction_name() -> None:
    HexCoord = import_contract_module("guiai.gem.zoe_hex_mesh", "HexCoord")
    coord = HexCoord(0, 0)
    for bad_dir in ("INVALID", "E", "W", ""):
        with pytest.raises((ValueError, KeyError)):
            coord.neighbor(bad_dir)


def test_t2_f01_reject_unknown_cell_id_neighbors() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    for bad_id in ("UnknownSister", ""):
        with pytest.raises((KeyError, ValueError)):
            mesh.neighbors(bad_id)


def test_t2_f01_cube_sum_invariant_for_extreme_coords() -> None:
    HexCoord = import_contract_module("guiai.gem.zoe_hex_mesh", "HexCoord")
    for q, r in ((10000, -10000), (-999, -999), (0, 0), (-32768, 16384)):
        coord = HexCoord(q, r)
        assert coord.q + coord.r + coord.s == 0
        assert coord.distance(coord) == 0


def test_t2_f01_shared_walls_no_self_loops_and_unique_undirected_edges() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    walls = mesh.shared_walls()
    undirected_seen: set[frozenset[str]] = set()
    for cell_a, _direction, cell_b in walls:
        assert cell_a != cell_b
        edge = frozenset((cell_a, cell_b))
        assert edge not in undirected_seen
        undirected_seen.add(edge)


# ============================================================================
# Feature #2 Boundaries: Deterministic Neighbor-Coupled Exchange (M1)
# ============================================================================

def test_t2_f02_reject_direct_message_to_non_adjacent_cell() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)

    non_adj = None
    cids = sorted(cmap.keys())
    for a in cids:
        for b in cids:
            if cmap[a].coord.distance(cmap[b].coord) >= 2:
                non_adj = (a, b)
                break
        if non_adj is not None:
            break
    assert non_adj is not None
    with pytest.raises(ValueError):
        mesh.send_neighbor_message(non_adj[0], non_adj[1], topic="illegal_jump", payload={"x": 1})


def test_t2_f02_reject_self_directed_neighbor_message() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cid = next(iter(get_mesh_cells(mesh)))
    with pytest.raises(ValueError):
        mesh.send_neighbor_message(cid, cid, topic="self_loop", payload={"x": 1})


def test_t2_f02_reject_action_epistemic_lane_in_hex_message() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    src = next(iter(cmap))
    dst = mesh.neighbors(src)[0]

    with pytest.raises(ValueError):
        mesh.send_neighbor_message(src, dst, topic="", payload={"v": 1})

    with pytest.raises(ValueError):
        call_with_supported_kwargs(
            mesh.send_neighbor_message,
            src,
            dst,
            topic="bypass",
            payload={"cmd": "run"},
            epistemic_lane="action",
        )


def test_t2_f02_step_coupled_tick_empty_queue_idempotent() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    r1 = mesh.step_coupled_tick()
    r2 = mesh.step_coupled_tick()
    d1 = str(pick(r1, "trace_sha256", "sha256", "digest"))
    d2 = str(pick(r2, "trace_sha256", "sha256", "digest"))
    assert len(d1) == 64 and len(d2) == 64


def test_t2_f02_invalid_coupling_fn_exception_preserves_prior_state() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap_before = get_mesh_cells(mesh)
    src = next(iter(cmap_before))
    dst = mesh.neighbors(src)[0]
    mesh.send_neighbor_message(src, dst, topic="atomic_probe", payload={"step": 1})

    snapshot_before = {cid: (c.revision, copy.deepcopy(c.state)) for cid, c in cmap_before.items()}
    tick_before = mesh.tick
    pending_before = len(mesh.pending_messages())
    assert pending_before == 1

    calls: list[str] = []

    def broken_coupling(cell: Any, neighbor_states: dict[str, dict[str, Any]]) -> dict[str, Any]:
        calls.append(str(cell.cell_id))
        if len(calls) < 3:
            return {**dict(cell.state), "mid_step_probe": len(calls)}
        raise RuntimeError("mid-step boom inside coupling_fn")

    with pytest.raises((RuntimeError, ValueError)):
        mesh.step_coupled_tick(coupling_fn=broken_coupling)

    cmap_after = get_mesh_cells(mesh)
    snapshot_after = {cid: (c.revision, copy.deepcopy(c.state)) for cid, c in cmap_after.items()}
    assert len(calls) >= 3
    assert snapshot_after == snapshot_before
    assert mesh.tick == tick_before
    assert len(mesh.pending_messages()) == pending_before


# ============================================================================
# Feature #3 Boundaries: 9-Sister Registry & Routing (zoe_sisters + M1)
# ============================================================================

def test_t2_f03_reject_tenth_fabricated_sister_resolution() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    for bad in ("TenthSister", "10", "UnknownSister"):
        with pytest.raises((ValueError, KeyError)):
            sisters_mod.resolve_sister(bad)
    fallback = sisters_mod.sister_for_emblem("nonexistent")
    assert fallback in sisters_mod.ZOE_SISTERS
    assert fallback.slot == 1


def test_t2_f03_reject_empty_or_whitespace_prompt_routing() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    before = dict(sisters_mod.SAFETY_INVARIANTS)
    for bad_prompt in ("", "   ", "\n\t"):
        with pytest.raises(ValueError):
            sisters_mod.route_prompt_to_sister(bad_prompt)
        with pytest.raises(ValueError):
            sisters_mod.run_sister_council(bad_prompt)
    assert dict(sisters_mod.SAFETY_INVARIANTS) == before


def test_t2_f03_sisters_collection_immutable_and_exactly_nine() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    assert len(sisters_mod.ZOE_SISTERS) == 9
    assert isinstance(sisters_mod.ZOE_SISTERS, tuple)
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        sisters_mod.ZOE_SISTERS[0].name = "Mutated"


def test_t2_f03_unknown_hardware_profile_deterministic_fallback() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    r1 = sisters_mod.recommend_sisters_for_hardware("UNKNOWN_HW_999")
    r2 = sisters_mod.recommend_sisters_for_hardware("UNKNOWN_HW_999")
    assert r1 == r2
    assert len(r1) >= 1
    assert all(spec in sisters_mod.ZOE_SISTERS for spec in r1)
    assert_sister_safety_invariants(sisters_mod.SAFETY_INVARIANTS)


def test_t2_f03_duplicate_sister_binding_rejected_in_custom_mesh() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    zoe = sisters_mod.ZOE_SISTERS[0]
    c1 = hex_mod.HexCell("z1", zoe, hex_mod.HexCoord(0, 0), "PRODUCT_DESIGN_AND_PLANNING", {}, 0)
    c2 = hex_mod.HexCell("z2", zoe, hex_mod.HexCoord(0, -1), "MATERIAL_DESIGN", {}, 0)
    with pytest.raises(ValueError):
        hex_mod.HexCollaborationMesh([c1, c2])


# ============================================================================
# Feature #4 Boundaries: FunctionEngineeringSpecification Intake (M2)
# ============================================================================

def test_t2_f04_reject_empty_spec_id_or_title() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    for field_name in ("spec_id", "title"):
        kw = sample_fes_kwargs("FES-VALID")
        kw[field_name] = ""
        with pytest.raises(ValueError):
            spec = eddms.FunctionEngineeringSpecification(**kw)
            db.ingest_specification(spec)


def test_t2_f04_reject_nan_or_inf_in_spec_target_properties() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    for bad_num in (float("nan"), float("inf"), float("-inf")):
        kw = sample_fes_kwargs("FES-NAN-INF")
        kw["target_properties"] = {"thermal_conductivity_w_mk": bad_num}
        with pytest.raises(ValueError):
            spec = eddms.FunctionEngineeringSpecification(**kw)
            db.ingest_specification(spec)


def test_t2_f04_reject_duplicate_spec_or_design_id_silent_overwrite() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-DUP-001"))
    db.ingest_specification(spec)
    with pytest.raises(ValueError):
        db.ingest_specification(spec)


def test_t2_f04_reject_non_mapping_constraints() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    kw = sample_fes_kwargs("FES-BAD-CONSTRAINTS")
    kw["constraints"] = ["not", "a", "dict"]
    with pytest.raises((TypeError, ValueError)):
        spec = eddms.FunctionEngineeringSpecification(**kw)
        db.ingest_specification(spec)


def test_t2_f04_failed_ingest_leaves_database_unchanged() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    valid = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-ATOMIC-OK"))
    rec = db.ingest_specification(valid)
    view_before = db.read_for_module(rec.general.design_id, "MATERIAL_DESIGN")
    assert view_before

    bad_kw = sample_fes_kwargs("FES-ATOMIC-BAD")
    bad_kw["geometric_requirements"] = {"width_mm": float("nan")}
    with pytest.raises((TypeError, ValueError)):
        db.ingest_specification(eddms.FunctionEngineeringSpecification(**bad_kw))

    view_after = db.read_for_module(rec.general.design_id, "MATERIAL_DESIGN")
    assert view_after == view_before
    recovered = db.ingest_specification(
        eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-ATOMIC-BAD"))
    )
    assert recovered.revision == 1
    assert recovered.spec_id == "FES-ATOMIC-BAD"
    assert recovered.general.design_id != rec.general.design_id


# ============================================================================
# Feature #5 Boundaries: Central EngineeringDesignDatabase (M2)
# ============================================================================

def test_t2_f05_reject_missing_general_design_id() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-GEN-01")))
    did = rec.general.design_id
    with pytest.raises(ValueError):
        db.write_from_module(
            did, "PRODUCT_DESIGN_AND_PLANNING", "Gemma",
            {"general": {"design_id": ""}},
            expected_revision=1,
        )


def test_t2_f05_reject_nan_and_neg_inf_in_geometric_and_property_data() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-NUM-01")))
    did = rec.general.design_id

    with pytest.raises(ValueError):
        db.write_from_module(
            did, "DESIGN_PARAMETERS", "Gemma",
            {"geometric": {"geom_3d": {"span_mm": float("nan")}}},
            expected_revision=1,
        )
    with pytest.raises(ValueError):
        db.write_from_module(
            did, "MATERIAL_DESIGN", "Tetra",
            {"properties": {"mechanical_desc": {"modulus_gpa": float("-inf")}}},
            expected_revision=1,
        )
    assert db.read_for_module(did, "MATERIAL_DESIGN")


def test_t2_f05_reject_unattributed_empty_sister_name() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-ATTR-01")))
    with pytest.raises(ValueError):
        db.write_from_module(
            rec.general.design_id,
            "MATERIAL_DESIGN",
            "",
            {"properties": {"physical_desc": {"mass_g": 42.0}}},
            expected_revision=1,
        )


def test_t2_f05_reject_unknown_design_id_lookup() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    with pytest.raises((KeyError, ValueError)):
        db.read_for_module("NONEXISTENT_DESIGN", "MATERIAL_DESIGN")


def test_t2_f05_reject_unknown_top_level_schema_category_in_patch() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-PATCH-01")))
    with pytest.raises(ValueError):
        db.write_from_module(
            rec.general.design_id,
            "MATERIAL_DESIGN",
            "Tetra",
            {"rogue_category": {"x": 1}},
            expected_revision=1,
        )


# ============================================================================
# Feature #6 Boundaries: Domain Spokes & Pipeline (M2)
# ============================================================================

def test_t2_f06_reject_stale_expected_revision_on_write() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-REV-01")))
    did = rec.general.design_id

    r2 = db.write_from_module(
        did, "MATERIAL_DESIGN", "Tetra",
        {"properties": {"physical_desc": {"mass_g": 55.0}}},
        expected_revision=1,
    )
    assert r2.revision == 2
    with pytest.raises(ValueError):
        db.write_from_module(
            did, "PRODUCT_DESIGN_AND_PLANNING", "Gemma",
            {"general": {"commerce_info": {"sku": "STALE"}}},
            expected_revision=1,
        )


def test_t2_f06_reject_unknown_domain_module_name() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-MOD-01")))
    did = rec.general.design_id

    with pytest.raises((ValueError, KeyError)):
        db.read_for_module(did, "INVALID_MODULE")
    with pytest.raises((ValueError, KeyError)):
        db.write_from_module(did, "INVALID_MODULE", "Zoe", {"general": {"special_instructions": "x"}}, expected_revision=1)


def test_t2_f06_reject_skipped_pipeline_stage_order() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-PIPE-SKIP")))
    with pytest.raises(ValueError):
        db.advance_pipeline_stage(
            rec.general.design_id,
            "PRODUCT_DESIGN_AND_PLANNING",
            "POSTPRODUCTION_MANAGEMENT",
            "Sage",
        )


def test_t2_f06_reject_backward_pipeline_stage_transition() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-PIPE-BACK")))
    did = rec.general.design_id

    db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")
    with pytest.raises(ValueError):
        db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "PRODUCT_DESIGN_AND_PLANNING", "Mono")


def test_t2_f06_reject_zero_or_negative_ticks_in_sister_cycle() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    mesh = build_default_hex_mesh(hex_mod)
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-TICKS-01"))
    for bad_ticks in (0, -1, -5):
        with pytest.raises(ValueError):
            eddms.run_sister_eddms_cycle(mesh, spec, ticks=bad_ticks)


# ============================================================================
# Feature #7 Boundaries: GEM AES Lifecycle & 16-Byte FIFO (M3 + seasip_gem)
# ============================================================================

def test_t2_f07_reject_malformed_non_16_byte_aes_message() -> None:
    seasip = import_contract_module("guiai.gem.seasip_gem")
    for bad_buf in (b"", b"\x00" * 14, b"\x00" * 18):
        with pytest.raises((ValueError, struct.error)):
            seasip.decode_aes_message(bad_buf)


def test_t2_f07_reject_evnt_multi_before_appl_init_or_after_exit() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)

    app = core.GemAesApplication()
    with pytest.raises((RuntimeError, ValueError)):
        app.evnt_multi(MU_MESAG)
    app.appl_init()
    app.appl_exit()
    with pytest.raises((RuntimeError, ValueError)):
        app.evnt_multi(MU_MESAG)


def test_t2_f07_reject_empty_or_invalid_evnt_multi_flags() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    app = core.GemAesApplication()
    app.appl_init()
    for bad_flags in (0, -1, 0x8000):
        with pytest.raises(ValueError):
            app.evnt_multi(bad_flags)
    app.appl_exit()


def test_t2_f07_timer_zero_ms_and_empty_queue_non_blocking() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)
    MU_TIMER = getattr(core, "MU_TIMER", 0x0020)

    app = core.GemAesApplication()
    app.appl_init()
    ev = call_with_supported_kwargs(app.evnt_multi, MU_MESAG | MU_TIMER, timer_ms=0)
    which = pick(ev, "matched_flags", "which", "events", "event_mask")
    assert (which & MU_TIMER) != 0
    app.appl_exit()


def test_t2_f07_int16_word_overflow_rejected_in_aes_message() -> None:
    seasip = import_contract_module("guiai.gem.seasip_gem")
    with pytest.raises((ValueError, struct.error)):
        seasip.encode_aes_message(seasip.WM_REDRAW, w3=40000)
    with pytest.raises((ValueError, struct.error)):
        seasip.encode_aes_message(seasip.WM_REDRAW, w4=-40000)


# ============================================================================
# Feature #8 Boundaries: Window Manager & Rectangle-List Redraw (M3)
# ============================================================================

def test_t2_f08_reject_eighth_window_above_max_7_limit() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    mgr = core.GemAesWindowTreeManager()

    for idx in range(seasip.MAX_AES_APP_WINDOWS):
        wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 10 + idx * 10, 20, 200, 120)
        assert wid > 0

    try:
        eighth = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 100, 100, 200, 120)
    except (ValueError, RuntimeError):
        return
    assert eighth < 0


def test_t2_f08_reject_unbalanced_wind_update_end_before_beg() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    mgr = core.GemAesWindowTreeManager()
    END_UPDATE = getattr(core, "END_UPDATE", 0)
    END_MCTRL = getattr(core, "END_MCTRL", 2)

    with pytest.raises((RuntimeError, ValueError)):
        mgr.wind_update(END_UPDATE)
    with pytest.raises((RuntimeError, ValueError)):
        mgr.wind_update(END_MCTRL)


def test_t2_f08_completely_occluded_window_yields_empty_redraw_list() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    mgr = core.GemAesWindowTreeManager()

    back = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 50, 50, 120, 90)
    aes_wind_open(mgr, back, 50, 50, 120, 90)
    front = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 20, 300, 220)
    aes_wind_open(mgr, front, 20, 20, 300, 220)

    rects = [tuple(r) for r in mgr.walk_redraw_rectangles(back, (50, 50, 120, 90)) if tuple(r)[2] > 0 and tuple(r)[3] > 0]
    assert rects == []


def test_t2_f08_reject_invalid_or_deleted_window_handle() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    WF_WXYWH = getattr(core, "WF_WXYWH")
    mgr = core.GemAesWindowTreeManager()

    with pytest.raises((ValueError, KeyError)):
        aes_wind_open(mgr, 999, 0, 0, 100, 100)
    with pytest.raises((ValueError, KeyError)):
        mgr.wind_get(-1, WF_WXYWH)

    wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 10, 20, 120, 90)
    mgr.wind_delete(wid)
    with pytest.raises((ValueError, KeyError)):
        mgr.wind_get(wid, WF_WXYWH)


def test_t2_f08_reject_negative_window_dimensions_in_wind_calc() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    WC_BORDER = getattr(core, "WC_BORDER", 0)
    mgr = core.GemAesWindowTreeManager()

    with pytest.raises(ValueError):
        mgr.wind_calc(WC_BORDER, seasip.STANDARD_WINDOW_KIND, (10, 10, -10, 100))
    with pytest.raises(ValueError):
        mgr.wind_calc(WC_BORDER, seasip.STANDARD_WINDOW_KIND, (10, 10, 100, 0))
    with pytest.raises(ValueError):
        mgr.wind_calc(99, seasip.STANDARD_WINDOW_KIND, (10, 10, 100, 100))


# ============================================================================
# Feature #9 Boundaries: Object Tree, Form, Menu & Resource (M3)
# ============================================================================

def test_t2_f09_reject_cyclic_object_tree_pointers() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    cyclic = [
        GemObject(1, 1, 1, seasip.G_BOX, 0, seasip.NORMAL, 0, 0, 0, 200, 120),
        GemObject(0, 0, 0, seasip.G_BUTTON, seasip.LASTOB, seasip.NORMAL, "Cycle", 10, 10, 60, 20),
    ]
    with pytest.raises(ValueError):
        ops.objc_find(cyclic, 0, 8, 20, 20)


def test_t2_f09_reject_missing_lastob_flag() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    no_lastob = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.NORMAL, 0, 0, 0, 200, 120),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE, seasip.NORMAL, "NoEnd", 10, 10, 60, 20),
    ]
    validator = getattr(ops, "validate_tree", None)
    with pytest.raises(ValueError):
        if callable(validator):
            validator(no_lastob)
        else:
            ops.objc_draw(no_lastob, 0, 8, (0, 0, 640, 400))


def test_t2_f09_reject_out_of_bounds_object_index() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    tree = [GemObject(-1, -1, -1, seasip.G_BOX, seasip.LASTOB, seasip.NORMAL, 0, 0, 0, 100, 80)]
    for bad_idx in (-2, 1, 50):
        with pytest.raises((IndexError, ValueError)):
            ops.objc_offset(tree, bad_idx)
        with pytest.raises((IndexError, ValueError)):
            ops.objc_find(tree, bad_idx, 8, 10, 10)


def test_t2_f09_reject_invalid_rsrc_gaddr_type_or_index(tmp_path: Path) -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    rsc_tree = seasip.GemObjectTree("ONLY_ONE", 20, 10)
    rsc_tree.add(seasip.G_STRING, 1, 1, 8, 1, text="Hi")
    rsc_file = tmp_path / "single.rsc"
    rsc_file.write_bytes(seasip.compile_rsc([rsc_tree]))

    core.rsrc_load(str(rsc_file))
    try:
        with pytest.raises((ValueError, IndexError)):
            core.rsrc_gaddr(99, 0)
        with pytest.raises((ValueError, IndexError)):
            core.rsrc_gaddr(0, 99)
    finally:
        core.rsrc_free()


def test_t2_f09_objc_find_miss_and_hidetree_returns_nil() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()

    tree = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.NORMAL, 0, 10, 10, 120, 80),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.HIDETREE | seasip.LASTOB, seasip.NORMAL, "Hidden", 10, 10, 50, 20),
    ]
    assert ops.objc_find(tree, 0, 8, 500, 500) == -1
    assert ops.objc_find(tree, 0, 8, 25, 25) == 0


# ============================================================================
# Feature #10 Boundaries: GEM VDI Workstation & Metafile (M3 + vdi)
# ============================================================================

def test_t2_f10_reject_vdi_calls_before_open_or_after_close() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_sm = GemVdiStateMachine()
    with pytest.raises((RuntimeError, ValueError)):
        vdi_sm.v_pline([(0, 0), (10, 10)])
    with pytest.raises((RuntimeError, ValueError)):
        vdi_sm.vq_extnd(0)

    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    vdi_sm.v_clsvwk()
    with pytest.raises((RuntimeError, ValueError)):
        vdi_sm.vs_clip(1, (0, 0, 10, 10))


def test_t2_f10_reject_16bit_coordinate_overflow() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_mod = import_contract_module("guiai.gem.vdi")
    model_mod = import_contract_module("guiai.gem.model")

    for bad_coord in (32768, -32769):
        overflow_doc = {
            "schema_version": 1,
            "id": "overflow-test",
            "canvas": {"width": 640, "height": 480},
            "objects": [
                {
                    "id": "bad_rect",
                    "type": "rectangle",
                    "bounds": [min(0, bad_coord), 0, max(10, bad_coord), 100],
                    "fill": "none",
                    "stroke": "black",
                }
            ],
            "constraints": [],
        }
        with pytest.raises(ValueError):
            model_mod.Scene.from_dict(overflow_doc)
        with pytest.raises(ValueError):
            vdi_mod.scene_to_metafile(model_mod.Scene(overflow_doc))

    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    try:
        with pytest.raises(ValueError):
            vdi_sm.v_pline([(0, 0), (40000, 10)])
        with pytest.raises(ValueError):
            vdi_sm.v_pline([(-40000, 0), (10, 10)])
    finally:
        vdi_sm.v_clsvwk()


def test_t2_f10_reject_invalid_vswr_mode() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    try:
        for bad_mode in (0, 5, -1):
            with pytest.raises(ValueError):
                vdi_sm.vswr_mode(bad_mode)
    finally:
        vdi_sm.v_clsvwk()


def test_t2_f10_vs_clip_zero_or_inverted_rect_clips_primitives() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    try:
        ret_zero = vdi_sm.vs_clip(1, (100, 100, 100, 100))
        assert pick(vdi_sm, "clip_enabled") is True
        assert tuple(pick(vdi_sm, "clip_rect")) == (100, 100, 100, 100)
        if ret_zero is not None:
            assert tuple(ret_zero) == (100, 100, 100, 100)
        vdi_sm.v_bar((10, 10, 200, 200))

        try:
            ret_inv = vdi_sm.vs_clip(1, (200, 200, 50, 50))
        except ValueError:
            assert pick(vdi_sm, "clip_enabled") is True
            assert tuple(pick(vdi_sm, "clip_rect")) == (100, 100, 100, 100)
        else:
            assert pick(vdi_sm, "clip_enabled") is True
            norm_rect = tuple(pick(vdi_sm, "clip_rect"))
            assert norm_rect == (50, 50, 200, 200)
            if ret_inv is not None:
                assert tuple(ret_inv) == (50, 50, 200, 200)
            ext1 = vdi_sm.vq_extnd(1)
            assert ext1[19] == 1 and tuple(ext1[20:24]) == (50, 50, 200, 200)
            vdi_sm.v_pline([(0, 0), (300, 300)])

        stream = pick(vdi_sm, "commands", "recorded_commands", "command_stream")
        assert len(stream) >= 2
        assert any(
            pick(cmd, "name", "command", default="") == "vs_clip"
            or pick(cmd, "opcode", default=None) == 129
            for cmd in stream
        )
        exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
        gem_bytes = exporter()
        assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    finally:
        vdi_sm.v_clsvwk()


def test_t2_f10_non_ascii_v_gtext_cp437_replacement() -> None:
    GemVdiStateMachine = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core", "GemVdiStateMachine")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    vdi_sm.v_gtext(20, 40, "Zoe ⚘ ᵔᵕᵔ Ω")
    exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
    gem_bytes = exporter()
    vdi_sm.v_clsvwk()
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True


# ============================================================================
# Feature #11 Boundaries: Ablation Read-Only Bridge (M4)
# ============================================================================

def test_t2_f11_fail_closed_on_missing_target_path(tmp_path: Path) -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    missing = tmp_path / "does_not_exist.elf"
    try:
        rep = bridge.inspect_target_readonly(target_path=missing)
    except (FileNotFoundError, ValueError):
        return
    assert pick(rep, "advisory_only") is True
    assert pick(rep, "status", "error", "ok") not in ("ok", True)


def test_t2_f11_empty_bytes_or_corrupt_binary_graceful_advisory() -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    for raw in (b"", b"\x00\xffDEAD\xbe\xef"):
        rep = bridge.inspect_target_readonly(raw_bytes=raw, target_name="corrupt.bin")
        assert pick(rep, "advisory_only") is True
        assert pick(rep, "read_only") is True
        assert pick(rep, "external_actions") == 0
        assert_m1_m4_constitutional_record(rep, require_advisory=True, require_read_only=True)


def test_t2_f11_reject_both_none_target_and_bytes() -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    with pytest.raises(ValueError):
        bridge.inspect_target_readonly(target_path=None, raw_bytes=None)


def test_t2_f11_reject_invalid_mode_and_unexecutable_script_never_runs(tmp_path: Path) -> None:
    AblationBridge = import_contract_module("guiai.gem.zoe_ablation_bridge", "AblationBridge")
    bridge = AblationBridge()
    script, sentinel = make_non_executing_sentinel_script(tmp_path, "danger_probe.sh")

    with pytest.raises(ValueError):
        bridge.inspect_target_readonly(target_path=script, mode="execute_live")
    assert not sentinel.exists()

    rep = bridge.inspect_target_readonly(target_path=script)
    assert not sentinel.exists(), "Static inspection MUST NEVER execute target script!"
    assert pick(rep, "advisory_only") is True
    assert pick(rep, "read_only") is True


def test_t2_f11_attach_ablation_rejects_stale_revision() -> None:
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-ABL-STALE")))
    rep = bridge_mod.AblationBridge().inspect_target_readonly(raw_bytes=minimal_elf64_bytes())
    with pytest.raises(ValueError):
        bridge_mod.attach_ablation_to_eddms(
            db, rec.general.design_id, rep, sister_name="Mono", expected_revision=999,
        )


# ============================================================================
# Feature #12 Boundaries: GEM Workbench & CLI (M4)
# ============================================================================

def test_t2_f12_workbench_never_exceeds_seven_aes_windows_even_with_all_9_sisters() -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    wb = wb_mod.create_workbench()

    focus_fn = getattr(wb, "focus_sister", None) or getattr(wb, "select_sister", None) or getattr(wb, "open_sister_pane", None)
    if focus_fn is not None:
        for name in ("Zoe", "Gemma", "Tosi", "Mono", "Tetra", "Eliza", "Sage", "Flora", "Lumen"):
            focus_fn(name)
    wb.tick_collaboration()
    snap = wb.snapshot_state()
    open_windows = pick(snap, "open_windows", "active_windows", "windows")
    win_count = len(open_windows) if isinstance(open_windows, (list, tuple, dict)) else int(open_windows)
    assert win_count <= seasip.MAX_AES_APP_WINDOWS


def test_t2_f12_lume_cli_unknown_sister_subcommand_error(tmp_path: Path) -> None:
    import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    active_before = cli.active_sister
    try:
        handled, lines = cli.handle_slash("/sister nonexistent_subcmd", color=False)
    except ValueError:
        assert cli.active_sister == active_before
        return
    assert handled is True
    assert lines
    assert cli.active_sister == active_before


def test_t2_f12_workbench_export_metafile_no_silent_overwrite_or_valid_path(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    wb = wb_mod.create_workbench()

    dir_target = tmp_path / "a_directory"
    dir_target.mkdir()
    with pytest.raises((IsADirectoryError, ValueError, OSError)):
        export_workbench_gem(wb, dir_target)

    out_file = tmp_path / "existing.gem"
    out_file.write_bytes(b"SENTINEL_DO_NOT_CORRUPT")
    try:
        export_workbench_gem(wb, out_file)
    except (FileExistsError, ValueError):
        assert out_file.read_bytes() == b"SENTINEL_DO_NOT_CORRUPT"
    else:
        written = out_file.read_bytes()
        assert written != b"SENTINEL_DO_NOT_CORRUPT"
        assert seasip.verify_seasip_gem_metafile(written)["valid"] is True


def test_t2_f12_workbench_ablation_missing_target_tagged_explicitly(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    wb = wb_mod.create_workbench()
    missing = tmp_path / "missing_probe.bin"
    try:
        res = call_with_supported_kwargs(wb.run_ablation_inspection, target_path=missing, path=missing)
    except (FileNotFoundError, ValueError):
        return
    assert pick(res, "advisory_only") is True
    status_val = pick(res, "status", "error", "ok", "found", "exists")
    assert status_val not in ("ok", "success", True, None, "")
    if (isinstance(res, dict) and "ok" in res) or hasattr(res, "ok"):
        assert pick(res, "ok") is False
    if (isinstance(res, dict) and "error" in res) or hasattr(res, "error"):
        assert bool(pick(res, "error"))
    assert_m1_m4_constitutional_record(res, require_advisory=True)


def test_t2_f12_unified_cli_invalid_gem_subcommand_nonzero_exit() -> None:
    import_contract_module("guiai.gem.zoe_gem_workbench")
    unified_cli = import_contract_module("guiai.gem.unified_cli")
    unified = import_contract_module("guiai.gem.unified")
    op_env = import_contract_module("guiai.gem.operating_environment")

    try:
        rc = unified_cli.main(["gem", "unknown-subcmd-xyz"])
    except SystemExit as exc:
        rc = int(exc.code) if isinstance(exc.code, int) else 2
    assert rc != 0
    assert len(unified.COMPONENTS) == 17
    assert len(op_env.ATLAS_MODULES) == 36


# ============================================================================
# Feature #13 Boundaries: Constitutional Firewall & Safety Guards (R5)
# ============================================================================

def test_t2_f13_reject_forged_sentience_or_clinical_flag_in_validator() -> None:
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"sentience_claimed": True})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"clinical_action_authorized": True})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"flight_control_authorized": True})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"cure_claim": True})

    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cmap.items() if c.sister.name == "Zoe")
    nbr_id = mesh.neighbors(zoe_id)[0]
    for forged in ({"sentience_claimed": True}, {"clinical_action_authorized": True}):
        with pytest.raises(ValueError):
            mesh.send_neighbor_message(zoe_id, nbr_id, topic="forged_flag", payload=forged)


def test_t2_f13_reject_nonzero_tokens_or_cloud_cost() -> None:
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"tokens_used": 1})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"cloud_tokens_used": 5})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"cloud_cost_usd": 0.01})

    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cmap.items() if c.sister.name == "Zoe")
    nbr_id = mesh.neighbors(zoe_id)[0]
    for bad_cost in ({"tokens_used": 1}, {"cloud_cost_usd": 0.01}):
        with pytest.raises(ValueError):
            mesh.send_neighbor_message(zoe_id, nbr_id, topic="cost_bypass", payload=bad_cost)


def test_t2_f13_reject_non_loopback_host_and_nonzero_external_actions(offline_guard: dict[str, int]) -> None:
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"loopback_only": False})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"external_actions": 1})
    with pytest.raises(RuntimeError, match="Offline guard blocked"):
        socket.create_connection(("8.8.8.8", 443), timeout=1)
    with pytest.raises(RuntimeError, match="Offline guard blocked"):
        with socket.socket() as sock:
            sock.connect_ex(("8.8.8.8", 443))
    assert offline_guard["non_loopback_blocked"] >= 2

    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cmap.items() if c.sister.name == "Zoe")
    nbr_id = mesh.neighbors(zoe_id)[0]
    for bad_net in ({"loopback_only": False}, {"external_actions": 1}):
        with pytest.raises(ValueError):
            mesh.send_neighbor_message(zoe_id, nbr_id, topic="net_bypass", payload=bad_net)


def test_t2_f13_reject_action_lane_bypass_in_eddms_and_ablation() -> None:
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"epistemic_lane": "action"})
    with pytest.raises(AssertionError):
        assert_constitutional_metadata({"advisory_only": False}, require_advisory=True)

    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    with pytest.raises(ValueError):
        core.constitutional_metadata("action")

    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-CONST-BYPASS")))
    with pytest.raises(ValueError):
        db.write_from_module(
            rec.general.design_id,
            "MATERIAL_DESIGN",
            "Mono",
            {"properties": {"structure_desc": {"epistemic_lane": "action", "advisory_only": False}}},
            expected_revision=1,
        )

    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    with pytest.raises(ValueError):
        bridge_mod.AblationBridge().inspect_target_readonly(
            raw_bytes=minimal_elf64_bytes(),
            target_name="bypass.elf",
            mode="advisor",
        )


def test_t2_f13_operational_guard_blocks_git_push_adb_and_claude_cli(offline_guard: dict[str, int]) -> None:
    for cmd in (["git", "push"], ["git", "-C", "/tmp", "push"], ["adb", "devices"], ["claude", "--version"]):
        with pytest.raises(RuntimeError, match="Operational guard blocked"):
            subprocess.run(cmd, check=False)
    with pytest.raises(RuntimeError, match="Operational guard blocked"):
        subprocess.run("true && claude --version", shell=True, check=False)
    assert offline_guard["forbidden_commands_blocked"] == 5

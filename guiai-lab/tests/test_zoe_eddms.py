"""Unit tests for M2 EDDBMS Central Engineering Design Database & Domain Spokes (zoe_eddms.py)."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
from typing import Any

import pytest

GUIAI_LAB_ROOT = Path(__file__).resolve().parents[1]
if str(GUIAI_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(GUIAI_LAB_ROOT))

from guiai.gem.zoe_eddms import (  # noqa: E402
    ATTRIBUTION_TEXT,
    EDDBMS_CONTRACT,
    EDDBMS_DOMAIN_MODULES,
    EDDBMS_MODULE_SUBOPERATIONS,
    EDDBMS_PIPELINE_STAGES,
    EDDBMS_SUBOPERATION_KEYS,
    HASH_CHAIN_SEMANTICS,
    SAFETY_INVARIANTS,
    SPEC_INTAKE_TARGETS,
    ConstitutionalViolationError,
    EddmsCollaborationRun,
    EddmsConflictError,
    EddmsPipelineError,
    EddmsRecordNotFoundError,
    EddmsValidationError,
    EngineeringDesignDatabase,
    EngineeringDesignRecord,
    EpistemicFirewallError,
    FunctionEngineeringSpecification,
    GeneralData,
    GeometricData,
    PipelineOrderError,
    PropertyData,
    RevisionConflictError,
    TamperDetectedError,
    UnknownDesignError,
    build_default_zoe_mesh,
    constitutional_metadata,
    list_module_suboperations,
    run_sister_eddms_cycle,
)
from guiai.gem.zoe_hex_mesh import HexCell, HexCoord, HexCollaborationMesh  # noqa: E402
from guiai.gem.zoe_sisters import ZOE_SISTERS  # noqa: E402


def _make_spec(spec_id: str = "SPEC-OPT-001", **overrides: Any) -> FunctionEngineeringSpecification:
    kwargs: dict[str, Any] = {
        "spec_id": spec_id,
        "title": "Optical Headlamp Pod & 3D Sensor Housing",
        "objective": "Design a lightweight thermally stable optical pod",
        "owner": "Zoe Engineering Collective",
        "constraints": {"max_mass_g": 120.0, "max_power_w": 2.5, "loopback_only": True},
        "target_properties": {
            "thermal_conductivity_w_mk": 18.5,
            "tensile_mpa": 210.0,
            "density_g_cm3": 1.42,
        },
        "geometric_requirements": {
            "bounds_mm": [48.0, 32.0, 24.0],
            "mesh_elements": 112000,
        },
        "special_instructions": "Advisory design only; wet-lab validation required.",
    }
    kwargs.update(overrides)
    return FunctionEngineeringSpecification(**kwargs)


def _assert_contract_metadata(meta: dict[str, Any], *, require_read_only: bool = False) -> None:
    assert meta["advisory_only"] is True
    assert meta["loopback_only"] is True
    assert meta["external_actions"] == 0
    assert meta["tokens_used"] == 0
    assert meta["cloud_cost_usd"] == 0.0
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["clinical_action_authorized"] is False
    assert meta["flight_control_authorized"] is False
    assert meta["cure_claim"] is False
    assert meta["attribution"] == ATTRIBUTION_TEXT
    assert meta["epistemic_lane"] in {
        "measurement",
        "evidence",
        "belief_update",
        "advisory_proposal",
    }
    if require_read_only:
        assert meta["read_only"] is True


# ---------------------------------------------------------------------------
# Group 1: Figure 15.3 Taxonomy & FunctionEngineeringSpecification Intake (F#4)
# ---------------------------------------------------------------------------


def test_figure_15_3_modules_and_28_canonical_suboperations() -> None:
    assert len(EDDBMS_DOMAIN_MODULES) == 6
    assert set(EDDBMS_MODULE_SUBOPERATIONS.keys()) == set(EDDBMS_DOMAIN_MODULES)
    assert set(EDDBMS_SUBOPERATION_KEYS.keys()) == set(EDDBMS_DOMAIN_MODULES)

    expected_counts = {
        "MATERIAL_DESIGN": 6,
        "HUMAN_MODEL": 4,
        "DESIGN_PARAMETERS": 2,
        "PRODUCT_DESIGN_AND_PLANNING": 5,
        "PROJECT_MANAGEMENT": 6,
        "POSTPRODUCTION_MANAGEMENT": 5,
    }
    total_subops = 0
    for mod, count in expected_counts.items():
        ops = list_module_suboperations(mod.lower())
        assert len(ops) == count
        assert len(EDDBMS_SUBOPERATION_KEYS[mod]) == count
        total_subops += count
    assert total_subops == 28

    assert EDDBMS_SUBOPERATION_KEYS["MATERIAL_DESIGN"] == (
        "geometric_modeling",
        "design_analysis",
        "design_animation",
        "design_optimization",
        "shaping_methods",
        "data_process",
    )
    assert EDDBMS_SUBOPERATION_KEYS["POSTPRODUCTION_MANAGEMENT"] == (
        "analysis",
        "evaluation",
        "visualization",
        "optimization",
        "application_information",
    )
    assert SPEC_INTAKE_TARGETS == (
        "ENGINEERING_DESIGN_DATABASE",
        "MATERIAL_DESIGN",
        "PRODUCT_DESIGN_AND_PLANNING",
    )
    assert EDDBMS_PIPELINE_STAGES == (
        "PRODUCT_DESIGN_AND_PLANNING",
        "PROJECT_MANAGEMENT",
        "POSTPRODUCTION_MANAGEMENT",
    )


def test_ingest_specification_unidirectional_feeds_and_revision_one() -> None:
    spec = _make_spec("SPEC-F04-01")
    db = EngineeringDesignDatabase()
    rec = db.ingest_specification(spec)

    assert isinstance(rec, EngineeringDesignRecord)
    assert rec.revision == 1
    assert rec.spec_id == "SPEC-F04-01"
    assert rec.general.design_id == "EDDBMS-SPEC-F04-01"
    assert rec.general.product_id == "PROD-SPEC-F04-01"
    assert rec.prev_record_sha256 == "GENESIS"
    assert len(rec.record_sha256) == 64
    assert rec.pipeline_stage == "PRODUCT_DESIGN_AND_PLANNING"
    assert "wet-lab validation" in rec.general.special_instructions
    assert rec.properties.mechanical_desc["tensile_mpa"] == 210.0
    assert rec.properties.physical_desc["thermal_conductivity_w_mk"] == 18.5
    assert rec.geometric.geom_2d == {}
    assert rec.geometric.geom_3d["bounds_mm"] == [48.0, 32.0, 24.0]
    assert rec.geometric.mesh_data["mesh_elements"] == 112000
    assert (
        rec.geometric.analysis_process_formats["specification_ref"]["geometric_requirements"]
        == spec.geometric_requirements
    )

    assert len(rec.provenance_log) == 1
    prov0 = rec.provenance_log[0]
    assert prov0["action"] == "ingest_specification"
    assert prov0["unidirectional_targets"] == list(SPEC_INTAKE_TARGETS)
    _assert_contract_metadata(prov0)

    # Unidirectional targets MATERIAL_DESIGN & PRODUCT_DESIGN_AND_PLANNING seeded
    mat_view = db.read_for_module(rec.general.design_id, "MATERIAL_DESIGN")
    prod_view = db.read_for_module(rec.general.design_id, "PRODUCT_DESIGN_AND_PLANNING")
    dp_view = db.read_for_module(rec.general.design_id, "DESIGN_PARAMETERS")
    pm_view = db.read_for_module(rec.general.design_id, "PROJECT_MANAGEMENT")

    assert mat_view["intake_fed"] is True
    assert prod_view["intake_fed"] is True
    assert pm_view["intake_fed"] is False
    assert mat_view["module_workspace"]["unidirectional_intake"]["spec_id"] == "SPEC-F04-01"
    assert prod_view["module_workspace"]["unidirectional_intake"]["title"] == spec.title
    assert dp_view["constraints"]["max_mass_g"] == 120.0
    assert dp_view["module_workspace"]["sub_operations"]["restriction_condition"]["data"]["max_power_w"] == 2.5


def test_ingest_rejects_empty_ids_non_mappings_duplicates_and_preserves_atomicity() -> None:
    for field_name in ("spec_id", "title", "objective", "owner"):
        with pytest.raises(EddmsValidationError):
            _make_spec(**{field_name: "   "})

    with pytest.raises(EddmsValidationError):
        _make_spec(special_instructions=123)

    with pytest.raises(EddmsValidationError):
        _make_spec(constraints=["bad", "list"])

    db = EngineeringDesignDatabase()
    ok_spec = _make_spec("SPEC-DUP-1")
    rec1 = db.ingest_specification(ok_spec)

    # Duplicate spec_id or design_id rejected without overwrite
    with pytest.raises(RevisionConflictError) as dup_exc:
        db.ingest_specification(ok_spec)
    assert isinstance(dup_exc.value, ValueError)
    assert EddmsConflictError is RevisionConflictError

    other_spec = _make_spec("SPEC-OTHER-2")
    with pytest.raises(RevisionConflictError):
        db.ingest_specification(other_spec, design_id=rec1.general.design_id)

    # Post-init nested mutation caught on ingest and leaves DB unchanged
    bad_spec = _make_spec("SPEC-MUTATED-3")
    bad_spec.target_properties["bad"] = float("nan")
    with pytest.raises(ConstitutionalViolationError):
        db.ingest_specification(bad_spec)

    with pytest.raises((KeyError, ValueError)):
        db.read_for_module("EDDBMS-SPEC-MUTATED-3", "MATERIAL_DESIGN")
    assert db.verify_integrity()["designs_verified"] == 1


# ---------------------------------------------------------------------------
# Group 2: Central EngineeringDesignDatabase & 3 Sub-Schemas (Feature #5)
# ---------------------------------------------------------------------------


def test_general_property_geometric_roundtrip_and_m4_ablation_compatibility() -> None:
    db = EngineeringDesignDatabase()
    rec1 = db.ingest_specification(_make_spec("SPEC-F05-ROUND"))
    did = rec1.general.design_id

    assert isinstance(rec1.general, GeneralData)
    assert isinstance(rec1.properties, PropertyData)
    assert isinstance(rec1.geometric, GeometricData)

    rec2 = db.write_from_module(
        did,
        "MATERIAL_DESIGN",
        "Tetra",
        {
            "general": {
                "product_id": "PROD-OPT-REV2",
                "owner_metadata": {"lab": "local-bench"},
                "special_instructions": "Verify optical baffle thickness.",
                "commerce_info": {"batch_size": 8},
            },
            "properties": {
                "structure_desc": {"macro": "hex-lattice", "micro": "Ti-6Al-4V"},
                "mechanical_desc": {"yield_mpa": 880.0, "warp_bend_rigidity": 42.1},
                "physical_desc": {"integral_heat_of_sorption": 12.4},
            },
            "geometric": {
                "geom_2d": {"profile": "hex_outline", "vertices": [[0, 0], [10, 0]]},
                "geom_3d": {"clearance_mm": 4.5},
                "mesh_data": {"topology": "hex", "nodes": 112000},
                "analysis_process_formats": {"fea": {"solver": "offline_static"}},
            },
        },
        expected_revision=1,
    )
    assert rec2.revision == 2
    assert rec2.general.product_id == "PROD-OPT-REV2"
    assert rec2.general.owner_metadata["lab"] == "local-bench"
    assert rec2.general.commerce_info["batch_size"] == 8
    assert rec2.properties.structure_desc["macro"] == "hex-lattice"
    assert rec2.properties.mechanical_desc["yield_mpa"] == 880.0
    assert rec2.properties.physical_desc["integral_heat_of_sorption"] == 12.4
    assert rec2.geometric.geom_2d == {"profile": "hex_outline", "vertices": [[0, 0], [10, 0]]}
    assert rec2.geometric.analysis_process_formats["fea"]["solver"] == "offline_static"

    # M4 attach_ablation_to_eddms multi-section write preserves prior keys
    rec3 = db.write_from_module(
        did,
        "POSTPRODUCTION_MANAGEMENT",
        "Mono",
        {
            "geometric": {
                "analysis_process_formats": {
                    "ablation": {
                        "target_name": "pod_fw.elf",
                        "advisory_only": True,
                        "read_only": True,
                        "findings_count": 0,
                    }
                }
            },
            "properties": {
                "structure_desc": {
                    "ablation_summary": {
                        "target_name": "pod_fw.elf",
                        "status": "clean",
                    }
                }
            },
        },
        expected_revision=rec2.revision,
        epistemic_lane="measurement",
    )
    assert rec3.revision == 3
    assert rec3.geometric.analysis_process_formats["fea"]["solver"] == "offline_static"
    assert rec3.geometric.analysis_process_formats["ablation"]["target_name"] == "pod_fw.elf"
    assert rec3.properties.structure_desc["macro"] == "hex-lattice"
    assert rec3.properties.structure_desc["ablation_summary"]["status"] == "clean"


def test_sha256_determinism_sensitivity_and_tamper_detection() -> None:
    spec = _make_spec("SPEC-SHA-01")
    db1 = EngineeringDesignDatabase()
    db2 = EngineeringDesignDatabase()
    r1 = db1.ingest_specification(spec)
    r2 = db2.ingest_specification(spec)

    assert r1.record_sha256 == r2.record_sha256
    assert len(r1.record_sha256) == 64

    r1_next = db1.write_from_module(
        r1.general.design_id,
        "DESIGN_PARAMETERS",
        "Sage",
        {"geometric": {"geom_2d": {"tolerance_mm": 0.05}}},
        expected_revision=1,
    )
    assert r1_next.record_sha256 != r1.record_sha256
    assert r1_next.prev_record_sha256 == r1.record_sha256

    # Verify tamper detection on internal record mutation
    tampered_copy = copy.deepcopy(r1_next)
    tampered_copy.properties.mechanical_desc["injected"] = 999.0
    assert tampered_copy.verify_sha256(raise_on_error=False) is False
    with pytest.raises(TamperDetectedError, match=HASH_CHAIN_SEMANTICS):
        tampered_copy.verify_sha256(raise_on_error=True)

    db1._records[r1.general.design_id].general.special_instructions = "tampered"
    with pytest.raises(TamperDetectedError):
        db1.verify_integrity(r1.general.design_id, raise_on_error=True)
    report = db1.verify_integrity(r1.general.design_id, raise_on_error=False)
    assert report["ok"] is False


def test_article_iv_snapshot_isolation_and_non_destructive_rollback() -> None:
    db = EngineeringDesignDatabase()
    r1 = db.ingest_specification(_make_spec("SPEC-ART4-01"))
    did = r1.general.design_id

    r2 = db.write_from_module(
        did,
        "MATERIAL_DESIGN",
        "Flora",
        {"properties": {"mechanical_desc": {"yield_mpa": 500.0}}},
        expected_revision=1,
    )
    r3 = db.write_from_module(
        did,
        "MATERIAL_DESIGN",
        "Flora",
        {"properties": {"mechanical_desc": {"yield_mpa": 750.0}}},
        expected_revision=2,
    )

    # Returned snapshots must remain isolated across subsequent mutations
    assert r1.revision == 1
    assert "yield_mpa" not in r1.properties.mechanical_desc
    assert r2.revision == 2
    assert r2.properties.mechanical_desc["yield_mpa"] == 500.0
    assert r3.revision == 3
    assert r3.properties.mechanical_desc["yield_mpa"] == 750.0

    # Rollback to revision 2 appends revision 4 without erasing history 1..3
    r4 = db.rollback_to_revision(
        did,
        2,
        sister_name="Mono",
        expected_revision=3,
        reason="Revert experimental yield target",
    )
    assert r4.revision == 4
    assert r4.properties.mechanical_desc["yield_mpa"] == 500.0
    assert len(db.list_revisions(did)) == 4
    assert db.get_revision(did, 3).properties.mechanical_desc["yield_mpa"] == 750.0
    assert r4.provenance_log[-1]["action"] == "rollback_to_revision"
    assert r4.provenance_log[-1]["restored_from_revision"] == 2
    assert db.verify_integrity(did)["ok"] is True


# ---------------------------------------------------------------------------
# Group 3: 6 Bidirectional Domain Spokes & Conflict Rejections (Feature #6)
# ---------------------------------------------------------------------------


def test_read_for_module_all_6_modules_and_deepcopy_isolation() -> None:
    db = EngineeringDesignDatabase()
    rec = db.ingest_specification(_make_spec("SPEC-ISO-01"))
    did = rec.general.design_id

    for mod_name in EDDBMS_DOMAIN_MODULES:
        view = db.read_for_module(did, mod_name)
        assert view["contract"] == EDDBMS_CONTRACT
        assert view["module_name"] == mod_name
        assert list(view["sub_operations"].keys()) == list(EDDBMS_SUBOPERATION_KEYS[mod_name])
        _assert_contract_metadata(view["constitutional"], require_read_only=True)

        # Mutate returned dict and verify DB state stays pristine
        view["general"]["special_instructions"] = "corrupted"
        view["properties"]["structure_desc"]["rogue"] = True
        view["module_workspace"]["sub_operations"] = {}

    fresh = db.read_for_module(did, "MATERIAL_DESIGN")
    assert fresh["general"]["special_instructions"] != "corrupted"
    assert "rogue" not in fresh["properties"]["structure_desc"]
    assert len(fresh["module_workspace"]["sub_operations"]) == 6


def test_write_from_module_cross_spoke_projection_and_sub_operations() -> None:
    db = EngineeringDesignDatabase()
    r1 = db.ingest_specification(_make_spec("SPEC-SPOKE-01"))
    did = r1.general.design_id

    r2 = db.write_from_module(
        did,
        "HUMAN_MODEL",
        "Flora",
        {
            "properties": {"physical_desc": {"comfort_index": 0.94}},
            "sub_operations": {"physiological": {"bpm_max": 120}},
        },
        expected_revision=1,
    )
    r3 = db.write_from_module(
        did,
        "DESIGN_PARAMETERS",
        "Tosi",
        {
            "geometric": {"mesh_data": {"nodes": 112000}},
            "sub_operations": {"environment": {"ambient_c": 22.0}},
        },
        expected_revision=r2.revision,
    )
    assert r3.revision == 3

    pm_view = db.read_for_module(did, "PROJECT_MANAGEMENT")
    assert pm_view["properties"]["physical_desc"]["comfort_index"] == 0.94
    assert pm_view["geometric"]["mesh_data"]["nodes"] == 112000

    hm_view = db.read_for_module(did, "HUMAN_MODEL")
    assert hm_view["module_workspace"]["sub_operations"]["physiological"]["data"]["bpm_max"] == 120


def test_write_from_module_rejects_stale_revision_unknown_keys_and_invalid_targets() -> None:
    db = EngineeringDesignDatabase()
    r1 = db.ingest_specification(_make_spec("SPEC-ERR-01"))
    did = r1.general.design_id

    r2 = db.write_from_module(
        did,
        "MATERIAL_DESIGN",
        "Tetra",
        {"properties": {"physical_desc": {"mass_g": 55.0}}},
        expected_revision=1,
    )
    assert r2.revision == 2

    # Stale and bool expected_revision
    with pytest.raises(RevisionConflictError):
        db.write_from_module(
            did,
            "PRODUCT_DESIGN_AND_PLANNING",
            "Gemma",
            {"general": {"commerce_info": {"sku": "STALE"}}},
            expected_revision=1,
        )
    with pytest.raises(EddmsValidationError):
        db.write_from_module(
            did,
            "PRODUCT_DESIGN_AND_PLANNING",
            "Gemma",
            {"general": {"commerce_info": {"sku": "BOOL"}}},
            expected_revision=True,
        )

    # Unknown design, unknown module, empty/unknown sister
    with pytest.raises(UnknownDesignError):
        db.read_for_module("MISSING_DESIGN", "MATERIAL_DESIGN")
    assert EddmsRecordNotFoundError is UnknownDesignError
    with pytest.raises(EddmsValidationError):
        db.read_for_module(did, "INVALID_MODULE")
    with pytest.raises(EddmsValidationError):
        db.write_from_module(
            did, "MATERIAL_DESIGN", "", {"properties": {"physical_desc": {"x": 1}}}, expected_revision=2
        )
    with pytest.raises(ValueError):
        db.write_from_module(
            did, "MATERIAL_DESIGN", "NotASister", {"properties": {"physical_desc": {"x": 1}}}, expected_revision=2
        )

    # Rogue top-level, sub-level, sub_operations key, and empty general.design_id
    for bad_patch in (
        {"rogue_category": {"x": 1}},
        {"properties": {"unknown_prop_field": {"x": 1}}},
        {"geometric": {"unknown_geom_field": {"x": 1}}},
        {"general": {"design_id": ""}},
        {"general": {"design_id": "EDDBMS-HIJACK"}},
        {"sub_operations": {"nonexistent_op": {"x": 1}}},
    ):
        with pytest.raises(EddmsValidationError):
            db.write_from_module(did, "MATERIAL_DESIGN", "Tetra", bad_patch, expected_revision=2)

    assert db.get_record(did).revision == 2


# ---------------------------------------------------------------------------
# Group 4: Sequential Right-Column Pipeline (Feature #6)
# ---------------------------------------------------------------------------


def test_advance_pipeline_stage_valid_sequence() -> None:
    db = EngineeringDesignDatabase()
    r1 = db.ingest_specification(_make_spec("SPEC-PIPE-OK"))
    did = r1.general.design_id

    s1 = db.advance_pipeline_stage(
        did,
        "PRODUCT_DESIGN_AND_PLANNING",
        "PROJECT_MANAGEMENT",
        "Mono",
        notes="Hand-off to PM",
    )
    assert s1["current_stage"] == "PROJECT_MANAGEMENT"
    assert s1["revision"] == 2
    _assert_contract_metadata(s1["constitutional"])

    s2 = db.advance_pipeline_stage(
        did,
        "PROJECT_MANAGEMENT",
        "POSTPRODUCTION_MANAGEMENT",
        "Sage",
        expected_revision=2,
    )
    assert s2["current_stage"] == "POSTPRODUCTION_MANAGEMENT"
    assert s2["revision"] == 3
    assert db.get_record(did).pipeline_stage == "POSTPRODUCTION_MANAGEMENT"


def test_advance_pipeline_stage_rejects_skip_backward_repeat_and_unknown() -> None:
    db = EngineeringDesignDatabase()
    r1 = db.ingest_specification(_make_spec("SPEC-PIPE-BAD"))
    did = r1.general.design_id

    assert EddmsPipelineError is PipelineOrderError

    # Skip stage
    with pytest.raises(PipelineOrderError):
        db.advance_pipeline_stage(
            did, "PRODUCT_DESIGN_AND_PLANNING", "POSTPRODUCTION_MANAGEMENT", "Sage"
        )
    # Unknown stage
    with pytest.raises(PipelineOrderError):
        db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "BOGUS_STAGE", "Sage")

    # Advance validly once, then reject backward and repeat transitions
    db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")
    with pytest.raises(PipelineOrderError):
        db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "PRODUCT_DESIGN_AND_PLANNING", "Mono")
    with pytest.raises(PipelineOrderError):
        db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")


# ---------------------------------------------------------------------------
# Group 5: 9-Sister Hexagonal Coupling Cycle (run_sister_eddms_cycle)
# ---------------------------------------------------------------------------


def test_run_sister_eddms_cycle_binds_all_9_sisters_and_preserves_pipeline_stage() -> None:
    mesh = build_default_zoe_mesh()
    spec = _make_spec("SPEC-CYCLE-01")
    cycle = run_sister_eddms_cycle(mesh, spec, ticks=2)

    assert isinstance(cycle, EddmsCollaborationRun)
    assert cycle.ticks_executed == 2
    assert len(cycle.tick_results) == 2
    assert len(cycle.tick_trace_hashes) == 2
    assert set(cycle.sister_module_bindings.keys()) == {s.name for s in ZOE_SISTERS}
    assert set(cycle.covered_modules) == set(EDDBMS_DOMAIN_MODULES)
    assert cycle.record.revision == 1 + 2 * 9  # 1 ingest + 2 ticks * 9 sisters
    assert cycle.record.pipeline_stage == "PRODUCT_DESIGN_AND_PLANNING"
    assert mesh.verify_integrity()["ok"] is True
    assert cycle.database.verify_integrity(cycle.design_id)["ok"] is True

    cycle_repr = repr(cycle)
    for sister in ZOE_SISTERS:
        assert sister.name in cycle_repr

    # Subsequent cross-spoke write + pipeline advance succeeds (M4/T4.01 pattern)
    rec_after = cycle.database.write_from_module(
        cycle.design_id,
        "MATERIAL_DESIGN",
        "Tetra",
        {"properties": {"structure_desc": {"shell": "carbon-PEEK"}}},
        expected_revision=cycle.record.revision,
    )
    assert rec_after.revision == cycle.record.revision + 1
    stage_res = cycle.database.advance_pipeline_stage(
        cycle.design_id,
        "PRODUCT_DESIGN_AND_PLANNING",
        "PROJECT_MANAGEMENT",
        "Mono",
    )
    assert stage_res["current_stage"] == "PROJECT_MANAGEMENT"


def test_run_sister_eddms_cycle_deterministic_sha256_and_input_validation() -> None:
    spec = _make_spec("SPEC-DET-01")
    c1 = run_sister_eddms_cycle(build_default_zoe_mesh(), spec, ticks=2)
    c2 = run_sister_eddms_cycle(build_default_zoe_mesh(), spec, ticks=2)

    assert c1.design_id == c2.design_id
    assert c1.record.record_sha256 == c2.record.record_sha256
    assert c1.run_sha256 == c2.run_sha256
    assert c1.tick_trace_hashes == c2.tick_trace_hashes
    _assert_contract_metadata(c1.constitutional_metadata(), require_read_only=True)

    mesh = build_default_zoe_mesh()
    for bad_ticks in (0, -1, -5, True, False):
        with pytest.raises(EddmsValidationError):
            run_sister_eddms_cycle(mesh, spec, ticks=bad_ticks)

    # Incomplete mesh missing sisters rejected cleanly
    partial_mesh = HexCollaborationMesh(
        [HexCell("zoe", ZOE_SISTERS[0], HexCoord(0, 0), "PROJECT_MANAGEMENT")]
    )
    with pytest.raises(EddmsValidationError):
        run_sister_eddms_cycle(partial_mesh, spec, ticks=1)


# ---------------------------------------------------------------------------
# Group 6: NaN/Inf/Cycle/Bool & Constitutional Epistemic Firewall (R5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_float", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_rejected_in_spec_and_write(bad_float: float) -> None:
    with pytest.raises(ConstitutionalViolationError):
        _make_spec(target_properties={"conductivity": bad_float})

    db = EngineeringDesignDatabase()
    rec = db.ingest_specification(_make_spec("SPEC-NONFIN"))
    with pytest.raises(ConstitutionalViolationError):
        db.write_from_module(
            rec.general.design_id,
            "DESIGN_PARAMETERS",
            "Sage",
            {"geometric": {"geom_3d": {"span_mm": bad_float}}},
            expected_revision=1,
        )


def test_cycles_non_string_keys_and_negative_zero_normalization() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ConstitutionalViolationError):
        _make_spec(constraints=cyclic)

    with pytest.raises(ConstitutionalViolationError):
        _make_spec(target_properties={1: "bad_key"})

    db = EngineeringDesignDatabase()
    spec = _make_spec("SPEC-NEGZERO", target_properties={"offset_mm": -0.0})
    rec = db.ingest_specification(spec)
    assert str(rec.properties.structure_desc["target_properties"]["offset_mm"]) == "0.0"


def test_constitutional_metadata_and_epistemic_firewall_rejects_bypasses() -> None:
    _assert_contract_metadata(constitutional_metadata(), require_read_only=True)
    assert SAFETY_INVARIANTS["sentience_claimed"] is False
    assert SAFETY_INVARIANTS["tokens_used"] == 0

    db = EngineeringDesignDatabase()
    rec = db.ingest_specification(_make_spec("SPEC-FIREWALL-01"))
    did = rec.general.design_id

    for bad_lane in ("action", "autonomous_action", "execute", "actuation", ""):
        with pytest.raises(EpistemicFirewallError):
            db.write_from_module(
                did,
                "MATERIAL_DESIGN",
                "Mono",
                {"properties": {"structure_desc": {"note": "x"}}},
                expected_revision=1,
                epistemic_lane=bad_lane,
            )

    for bad_patch in (
        {"properties": {"structure_desc": {"epistemic_lane": "action"}}},
        {"properties": {"structure_desc": {"advisory_only": False}}},
        {"properties": {"structure_desc": {"sentience_claimed": True}}},
        {"properties": {"structure_desc": {"external_actions": 1}}},
        {"properties": {"structure_desc": {"tokens_used": 5}}},
        {"properties": {"structure_desc": {"cloud_cost_usd": 0.01}}},
        {"properties": {"structure_desc": {"loopback_only": False}}},
        {"properties": {"structure_desc": {"execute": True}}},
        {"properties": {"structure_desc": {"execute": 1}}},
        {"properties": {"structure_desc": {"auto_execute": "true"}}},
    ):
        with pytest.raises(ConstitutionalViolationError):
            db.write_from_module(did, "MATERIAL_DESIGN", "Mono", bad_patch, expected_revision=1)

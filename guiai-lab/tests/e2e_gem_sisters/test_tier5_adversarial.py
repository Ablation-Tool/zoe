"""Tier 5: White-box adversarial hardening & regression tests (17 adversarial specs)."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import random
import struct
import sys
import threading
import time
from typing import Any

import pytest

from .conftest import (
    REPO_ROOT,
    assert_full_contract_metadata,
    assert_m1_m4_constitutional_record,
    build_default_hex_mesh,
    import_contract_module,
    make_non_executing_sentinel_script,
    minimal_elf64_bytes,
    sample_fes_kwargs,
)

pytestmark = pytest.mark.tier5


def test_t5_01_export_rejects_fifo_and_special_files_even_with_overwrite(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    ucli = import_contract_module("guiai.gem.unified_cli")

    wb = wb_mod.create_workbench()
    fifo_svg = tmp_path / "trap.svg"
    fifo_gem = tmp_path / "trap.gem"
    os.mkfifo(fifo_svg)
    os.mkfifo(fifo_gem)

    for overwrite in (False, True):
        with pytest.raises((ValueError, OSError)):
            wb.export_svg(fifo_svg, overwrite=overwrite)
        with pytest.raises((ValueError, OSError)):
            wb.export_gem_metafile(fifo_gem, overwrite=overwrite)

    rc = ucli.main(["workbench", "export", "--format", "svg", "--output", str(fifo_svg)])
    assert rc == 2


def test_t5_02_export_rejects_symlink_parent_traversal_and_non_dir_parent(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    wb = wb_mod.create_workbench()

    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    sym_dir = tmp_path / "sym_dir"
    sym_dir.symlink_to(real_dir, target_is_directory=True)

    dangling_svg = tmp_path / "dangling.svg"
    dangling_svg.symlink_to(tmp_path / "does_not_exist.svg")

    live_target = tmp_path / "protected_target.txt"
    live_target.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
    live_sym_svg = tmp_path / "live.svg"
    live_sym_svg.symlink_to(live_target)
    live_sym_gem = tmp_path / "live.gem"
    live_sym_gem.symlink_to(live_target)

    file_parent = tmp_path / "regular_file_parent"
    file_parent.write_text("not_a_dir", encoding="utf-8")

    bad_paths = [
        sym_dir / "out.svg",
        dangling_svg,
        live_sym_svg,
        tmp_path / "sub" / ".." / "escape.svg",
        file_parent / "child.svg",
    ]
    for path in bad_paths:
        with pytest.raises((ValueError, OSError)):
            wb.export_svg(path, overwrite=True)

    for path in (sym_dir / "out.gem", live_sym_gem, tmp_path / "sub" / ".." / "escape.gem", file_parent / "child.gem"):
        with pytest.raises((ValueError, OSError)):
            wb.export_gem_metafile(path, overwrite=True)

    assert live_target.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE"
    assert not (tmp_path / "does_not_exist.svg").exists()


def test_t5_03_eddms_thread_safe_optimistic_concurrency_race() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-RACE")))
    did = rec1.general.design_id

    num_threads = 4
    barrier = threading.Barrier(num_threads)
    outcomes: list[str] = []
    out_lock = threading.Lock()

    large_patch = {
        "properties": {
            "structure_desc": {f"layer_{i}": {"density": float(i) * 0.25} for i in range(40)}
        },
        "sub_operations": {
            "design_analysis": {"batch": list(range(50))}
        },
    }

    def worker(idx: int) -> None:
        barrier.wait(timeout=5.0)
        try:
            res = db.write_from_module(
                did,
                "MATERIAL_DESIGN",
                "Tetra",
                {**large_patch, "notes": f"worker-{idx}"},
                expected_revision=1,
            )
            tag = f"ok:{res.revision}"
        except eddms.RevisionConflictError:
            tag = "conflict"
        with out_lock:
            outcomes.append(tag)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
        assert not t.is_alive()

    assert outcomes.count("ok:2") == 1
    assert outcomes.count("conflict") == 3
    assert len(db.list_revisions(did)) == 2
    assert db.get_record(did).revision == 2
    assert db.verify_integrity(did)["ok"] is True


def test_t5_04_eddms_partial_write_atomicity_and_rollback_pipeline_reversibility() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-ATOM")))
    did = rec1.general.design_id
    before_sha = rec1.record_sha256
    before_ws = db.read_for_module(did, "MATERIAL_DESIGN")["module_workspace"]

    with pytest.raises(eddms.EddmsValidationError):
        db.write_from_module(
            did,
            "MATERIAL_DESIGN",
            "Flora",
            {
                "general": {"commerce_info": {"should_not_commit": True}},
                "properties": {"mechanical_desc": {"yield_mpa": 999.0}},
                "sub_operations": {"invalid_subop": {"x": 1}},
            },
            expected_revision=1,
        )

    with pytest.raises(eddms.EddmsValidationError):
        db.write_from_module(
            did,
            "MATERIAL_DESIGN",
            "Flora",
            {
                "properties": {"physical_desc": {"density": 1.2}},
                "notes": ["not-a-string"],
            },
            expected_revision=1,
        )

    after_fail = db.get_record(did)
    assert after_fail.revision == 1
    assert after_fail.record_sha256 == before_sha
    assert db.read_for_module(did, "MATERIAL_DESIGN")["module_workspace"] == before_ws

    s1 = db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Zoe")
    assert s1["current_stage"] == "PROJECT_MANAGEMENT"
    s2 = db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "POSTPRODUCTION_MANAGEMENT", "Mono")
    assert s2["current_stage"] == "POSTPRODUCTION_MANAGEMENT"

    rolled = db.rollback_to_revision(did, target_revision=1, sister_name="Mono", reason="revert to initial spec")
    assert rolled.pipeline_stage == "PRODUCT_DESIGN_AND_PLANNING"
    assert rolled.revision == 4

    s3 = db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Zoe")
    assert s3["current_stage"] == "PROJECT_MANAGEMENT"
    assert db.verify_integrity(did)["ok"] is True


def test_t5_05_eddms_run_sister_cycle_lowercase_domain_module_and_atomicity() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    sisters = import_contract_module("guiai.gem.zoe_sisters")

    custom_cells = []
    for spec_s in sisters.ZOE_SISTERS:
        cid = spec_s.name.lower()
        q, r = hex_mod.DEFAULT_SISTER_COORDS[cid]
        raw_mod = f"  {hex_mod.DEFAULT_SISTER_DOMAIN_MODULES[cid].lower()}  "
        custom_cells.append(
            hex_mod.HexCell(
                cell_id=cid,
                sister=spec_s,
                coord=hex_mod.HexCoord(q, r),
                domain_module=raw_mod,
                state={"slot": spec_s.slot},
                revision=0,
            )
        )
    mesh = hex_mod.HexCollaborationMesh(custom_cells)
    db = eddms.EngineeringDesignDatabase()
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-LOWER"))

    run = eddms.run_sister_eddms_cycle(mesh, spec, ticks=1, db=db)
    assert set(run.covered_modules) == set(eddms.EDDBMS_DOMAIN_MODULES)
    assert db.verify_integrity(run.design_id)["ok"] is True
    assert mesh.verify_integrity()["ok"] is True

    # Invalid domain_module must fail atomically before mutating db or advancing mesh.tick
    bad_cells = list(custom_cells)
    bad_cells[0] = hex_mod.HexCell(
        cell_id=bad_cells[0].cell_id,
        sister=bad_cells[0].sister,
        coord=bad_cells[0].coord,
        domain_module="not_a_real_module",
        state={},
        revision=0,
    )
    bad_mesh = hex_mod.HexCollaborationMesh(bad_cells)
    db2 = eddms.EngineeringDesignDatabase()
    spec2 = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-BADMOD"))
    with pytest.raises(eddms.EddmsValidationError):
        eddms.run_sister_eddms_cycle(bad_mesh, spec2, ticks=1, db=db2)
    assert bad_mesh.tick == 0
    assert db2.verify_integrity()["designs_verified"] == 0


def test_t5_06_epistemic_firewall_rejects_truthy_execute_flags_everywhere() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    sisters = import_contract_module("guiai.gem.zoe_sisters")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")

    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-FIREWALL")))
    did = rec1.general.design_id

    truthy_vals: tuple[Any, ...] = (True, 1, 1.0, "true", "1", "yes", "on", "TRUE")
    for flag_key in ("execute", "auto_execute"):
        for val in truthy_vals:
            bad_pkt: dict[str, Any] = {flag_key: val}

            with pytest.raises(hex_mod.EpistemicFirewallError):
                hex_mod.validate_constitutional_packet(bad_pkt)

            with pytest.raises(hex_mod.EpistemicFirewallError):
                hex_mod.HexMessage(
                    message_id="msg-bad",
                    tick=1,
                    sender_id="zoe",
                    receiver_id="gemma",
                    topic="test",
                    payload=bad_pkt,
                )

            with pytest.raises(hex_mod.EpistemicFirewallError):
                hex_mod.HexCell(
                    cell_id="zoe",
                    sister=sisters.ZOE_SISTERS[0],
                    coord=hex_mod.HexCoord(0, 0),
                    domain_module="PROJECT_MANAGEMENT",
                    state=bad_pkt,
                )

            mesh = build_default_hex_mesh(hex_mod)
            with pytest.raises(hex_mod.EpistemicFirewallError):
                mesh.step_coupled_tick(coupling_fn=lambda _c, _n, p=bad_pkt: dict(p))

            with pytest.raises(hex_mod.EpistemicFirewallError):
                db.write_from_module(
                    did,
                    "MATERIAL_DESIGN",
                    "Tetra",
                    {"properties": {"structure_desc": bad_pkt}},
                    expected_revision=1,
                )

            with pytest.raises(hex_mod.EpistemicFirewallError):
                bridge_mod.AblationAdvisoryReport(
                    target_name="bad",
                    target_path=None,
                    target_sha256="0" * 64,
                    mode="bytes",
                    byte_size=0,
                    findings=(bad_pkt,),
                )

            with pytest.raises(hex_mod.EpistemicFirewallError):
                bridge_mod.attach_ablation_to_eddms(
                    db,
                    did,
                    {"advisory_only": True, "read_only": True, "findings": [bad_pkt]},
                    expected_revision=1,
                )


def test_t5_07_hex_mesh_step_coupled_tick_preserves_reentrant_messages_and_rejects_corrupt_cell_state() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)

    def coupling_fn(cell_copy: Any, _nbrs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if cell_copy.cell_id == "zoe":
            mesh.send_neighbor_message("zoe", "gemma", "reentrant", {"k": 1})
        out = dict(cell_copy.state)
        out["tick_seen"] = mesh.tick + 1
        return out

    res1 = mesh.step_coupled_tick(coupling_fn=coupling_fn)
    assert res1.tick == 1
    pending = mesh.pending_messages()
    assert len(pending) == 1
    assert pending[0].topic == "reentrant"
    assert pending[0].payload == {"k": 1}

    res2 = mesh.step_coupled_tick()
    assert res2.tick == 2
    assert len(mesh.pending_messages()) == 0
    assert len(res2.delivered_messages) == 1
    assert res2.delivered_messages[0].topic == "reentrant"
    assert mesh.verify_integrity()["ok"] is True

    # Mutate cell state directly with NaN and sentience override -> verify_integrity must detect
    mesh_nan = build_default_hex_mesh(hex_mod)
    mesh_nan.cell("zoe").state["corrupt"] = float("nan")
    assert mesh_nan.verify_integrity(raise_on_error=False)["ok"] is False

    mesh_sent = build_default_hex_mesh(hex_mod)
    mesh_sent.cell("gemma").state["sentience_claimed"] = True
    assert mesh_sent.verify_integrity(raise_on_error=False)["ok"] is False


def test_t5_08_ablation_bridge_rejects_symlinks_and_malformed_mapping_attachment(tmp_path: Path) -> None:
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    bridge = bridge_mod.AblationBridge()

    ext_dir = tmp_path / "external"
    ext_dir.mkdir()
    secret_file = ext_dir / "secret.py"
    secret_file.write_text("import os\nos.system('id')\n", encoding="utf-8")

    scan_dir = tmp_path / "scan_dir"
    scan_dir.mkdir()
    clean_file = scan_dir / "clean.py"
    clean_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    _script, sentinel = make_non_executing_sentinel_script(scan_dir)
    (scan_dir / "leak_link.py").symlink_to(secret_file)

    direct_sym = tmp_path / "direct_sym.py"
    direct_sym.symlink_to(clean_file)
    with pytest.raises(ValueError):
        bridge.inspect_target_readonly(target_path=direct_sym)

    dir_rep = bridge.inspect_target_readonly(target_path=scan_dir, mode="source")
    assert not sentinel.exists()
    assert dir_rep.byte_size == len(clean_file.read_bytes()) + len((scan_dir / "sentinel_probe.sh").read_bytes())
    assert dir_rep.source_audit is not None
    assert all("leak_link" not in str(f.get("location", "")) for f in dir_rep.findings)

    # Compare SHA with clean directory lacking the symlink
    clean_only = tmp_path / "clean_only"
    clean_only.mkdir()
    (clean_only / "clean.py").write_bytes(clean_file.read_bytes())
    (clean_only / "sentinel_probe.sh").write_bytes((scan_dir / "sentinel_probe.sh").read_bytes())
    clean_rep = bridge.inspect_target_readonly(target_path=clean_only, mode="source")
    assert dir_rep.target_sha256 == clean_rep.target_sha256

    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-ABL")))
    did = rec1.general.design_id

    for bad_mapping in (
        {"advisory_only": True, "read_only": True, "findings": "abc"},
        {"advisory_only": True, "read_only": True, "findings": ["not_a_mapping"]},
        {"advisory_only": True, "read_only": True, "findings": [], "byte_size": True},
    ):
        with pytest.raises(bridge_mod.ConstitutionalViolationError):
            bridge_mod.attach_ablation_to_eddms(db, did, bad_mapping, expected_revision=1)


def test_t5_09_aes_window_manager_multi_occluder_clipping_and_edge_errors() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    app = core.GemAesApplication("T5_WM")
    app.appl_init()
    mgr = core.GemAesWindowTreeManager(640, 400, event_app=app)
    kind = seasip.STANDARD_WINDOW_KIND

    # Churn wind_create / wind_delete and verify MAX_AES_APP_WINDOWS == 7 cap
    handles = [mgr.wind_create(kind, (20 + i * 20, 30 + i * 15, 220, 140)) for i in range(7)]
    assert len(handles) == core.MAX_AES_APP_WINDOWS == 7
    assert mgr.wind_create(kind, (10, 20, 100, 100)) < 0

    mgr.wind_delete(handles[-1])
    reused = mgr.wind_create(kind, (400, 200, 180, 120))
    assert reused > 0

    # Open 3 overlapping windows + 1 partially offscreen window, keep 1 closed
    w1, w2, w3, w4 = handles[0], handles[1], handles[2], handles[3]
    closed_w = handles[4]
    mgr.wind_open(w1, (40, 40, 240, 180))
    mgr.wind_open(w2, (100, 80, 160, 120))
    mgr.wind_open(w3, (140, 60, 180, 140))
    mgr.wind_open(w4, (560, 320, 160, 140))

    assert mgr.walk_redraw_rectangles(closed_w, (0, 0, 640, 400)) == []
    with pytest.raises(ValueError):
        mgr.walk_redraw_rectangles(w1, (-10, 0, -5, 10))

    work1 = mgr.wind_get(w1, core.WF_WORKXYWH)
    clips = mgr.walk_redraw_rectangles(w1, work1)
    assert clips and all(c.g_w > 0 and c.g_h > 0 for c in clips)
    # Pairwise disjointness check
    for i, a in enumerate(clips):
        for b in clips[i + 1 :]:
            assert a.intersect(b) is None

    # Exact visible area coverage check against w2 and w3 occlusion
    w2_rect = mgr.wind_get(w2, core.WF_CURRXYWH)
    w3_rect = mgr.wind_get(w3, core.WF_CURRXYWH)
    covered_px = 0
    for py in range(work1.g_y, work1.g_y + work1.g_h):
        for px in range(work1.g_x, work1.g_x + work1.g_w):
            in_occ = (
                (w2_rect.g_x <= px < w2_rect.g_x + w2_rect.g_w and w2_rect.g_y <= py < w2_rect.g_y + w2_rect.g_h)
                or (w3_rect.g_x <= px < w3_rect.g_x + w3_rect.g_w and w3_rect.g_y <= py < w3_rect.g_y + w3_rect.g_h)
            )
            if not in_occ:
                covered_px += 1
    assert sum(c.g_w * c.g_h for c in clips) == covered_px

    # Missing slider values must raise ValueError (never IndexError)
    for field in (core.WF_HSLIDE, core.WF_VSLIDE, core.WF_HSLSIZE, core.WF_VSLSIZE):
        with pytest.raises(ValueError):
            mgr.wind_set(w1, field)

    # wind_update lock balance checks (nested locks + unbalanced unlock rejection)
    with pytest.raises(ValueError):
        mgr.wind_update(core.END_UPDATE)
    with pytest.raises(ValueError):
        mgr.wind_update(core.END_MCTRL)
    assert mgr.wind_update(core.BEG_UPDATE) == 1
    assert mgr.wind_update(core.BEG_UPDATE) == 1
    assert mgr.update_lock_depth == 2
    assert mgr.wind_update(core.END_UPDATE) == 1
    assert mgr.wind_update(core.END_UPDATE) == 1
    with pytest.raises(ValueError):
        mgr.wind_update(core.END_UPDATE)
    assert mgr.wind_update(core.BEG_MCTRL) == 1
    assert mgr.wind_update(core.END_MCTRL) == 1
    with pytest.raises(ValueError):
        mgr.wind_update(core.END_MCTRL)
    with pytest.raises(ValueError):
        mgr.wind_update(99)


def test_t5_10_aes_object_tree_cycles_menu_negative_item_and_rsc_malformed() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    GemObject = core.GemObject
    Ops = core.GemObjectTreeOps

    # 1. Self-head loop
    self_head_tree = [
        GemObject(ob_next=core.NIL, ob_head=0, ob_tail=0, ob_type=core.G_BOX, ob_flags=core.LASTOB, ob_w=10, ob_h=10)
    ]
    with pytest.raises(ValueError):
        Ops.validate_tree(self_head_tree)

    # 2. Multiple parents
    multi_parent_tree = [
        GemObject(ob_next=core.NIL, ob_head=1, ob_tail=2, ob_type=core.G_BOX, ob_w=100, ob_h=100),
        GemObject(ob_next=2, ob_head=2, ob_tail=2, ob_type=core.G_BOX, ob_w=50, ob_h=50),
        GemObject(ob_next=0, ob_head=core.NIL, ob_tail=core.NIL, ob_type=core.G_STRING, ob_flags=core.LASTOB, ob_w=20, ob_h=10),
    ]
    with pytest.raises(ValueError):
        Ops.validate_tree(multi_parent_tree)

    # 3. Ancestor cycle via objc_add
    anc_tree = [
        GemObject(ob_next=core.NIL, ob_head=1, ob_tail=1, ob_type=core.G_BOX, ob_w=100, ob_h=100),
        GemObject(ob_next=0, ob_head=2, ob_tail=2, ob_type=core.G_BOX, ob_w=50, ob_h=50),
        GemObject(ob_next=1, ob_head=core.NIL, ob_tail=core.NIL, ob_type=core.G_BOX, ob_flags=core.LASTOB, ob_w=10, ob_h=10),
    ]
    with pytest.raises(ValueError):
        Ops.objc_add(anc_tree, 2, 1)

    # 4. Premature LASTOB
    premature_lastob = [
        GemObject(ob_next=core.NIL, ob_head=1, ob_tail=1, ob_type=core.G_BOX, ob_flags=core.LASTOB, ob_w=100, ob_h=100),
        GemObject(ob_next=0, ob_head=core.NIL, ob_tail=core.NIL, ob_type=core.G_STRING, ob_flags=core.LASTOB, ob_w=10, ob_h=10),
    ]
    with pytest.raises(ValueError):
        Ops.validate_tree(premature_lastob)

    # 5. menu_tnormal negative item_idx rejection
    menu_tree = [
        GemObject(ob_next=core.NIL, ob_head=1, ob_tail=2, ob_type=core.G_BOX, ob_w=320, ob_h=20),
        GemObject(ob_next=2, ob_head=core.NIL, ob_tail=core.NIL, ob_type=core.G_TITLE, ob_w=48, ob_h=16, text="File"),
        GemObject(ob_next=0, ob_head=core.NIL, ob_tail=core.NIL, ob_type=core.G_STRING, ob_flags=core.LASTOB, ob_w=48, ob_h=16, text="Quit"),
    ]
    with pytest.raises(ValueError):
        core.menu_tnormal(menu_tree, 1, 0, item_idx=-1)
    with pytest.raises(ValueError):
        core.menu_tnormal(menu_tree, 1, 1, item_idx=-5)

    # 6. Malformed binary .RSC variants
    rm = core.GemResourceManager()
    # Cyclic OBJECT pointer in .RSC
    cyclic_obj = struct.pack("<hhhHHHIHHHH", -1, 0, 0, core.G_BOX, core.LASTOB, core.NORMAL, 0, 0, 0, 10, 10)
    rsh_obj = 36
    rsh_tr = rsh_obj + len(cyclic_obj)
    tr_le = struct.pack("<I", rsh_obj)
    total_sz = rsh_tr + len(tr_le)
    hdr_cyc = struct.pack("<18H", 0, rsh_obj, rsh_obj, rsh_obj, rsh_obj, rsh_obj, 36, rsh_obj, rsh_obj, rsh_tr, 1, 1, 0, 0, 0, 0, 0, total_sz)
    with pytest.raises(ValueError):
        rm.rsrc_load(hdr_cyc + cyclic_obj + tr_le)

    # Truncated TEDINFO, ICONBLK, BITBLK
    valid_obj = struct.pack("<hhhHHHIHHHH", -1, -1, -1, core.G_BOX, core.LASTOB, core.NORMAL, 0, 0, 0, 10, 10)
    hdr_ted = struct.pack("<18H", 0, rsh_obj, total_sz, rsh_obj, rsh_obj, rsh_obj, 36, rsh_obj, rsh_obj, rsh_tr, 1, 1, 1, 0, 0, 0, 0, total_sz)
    with pytest.raises(ValueError):
        rm.rsrc_load(hdr_ted + valid_obj + tr_le)

    hdr_ib = struct.pack("<18H", 0, rsh_obj, rsh_obj, total_sz, rsh_obj, rsh_obj, 36, rsh_obj, rsh_obj, rsh_tr, 1, 1, 0, 1, 0, 0, 0, total_sz)
    with pytest.raises(ValueError):
        rm.rsrc_load(hdr_ib + valid_obj + tr_le)

    hdr_bb = struct.pack("<18H", 0, rsh_obj, rsh_obj, rsh_obj, total_sz, rsh_obj, 36, rsh_obj, rsh_obj, rsh_tr, 1, 1, 0, 0, 1, 0, 0, total_sz)
    with pytest.raises(ValueError):
        rm.rsrc_load(hdr_bb + valid_obj + tr_le)

    # Palindrome BE rsh_rssize = 0x0404 (1028 bytes)
    be_obj = struct.pack(">3h3HI4h", -1, -1, -1, core.G_BOX, core.LASTOB, core.NORMAL, 0, 0, 0, 100, 100)
    be_hdr = struct.pack(">18H", 0, 0x0200, 0x0200, 0x0200, 0x0200, 0x0200, 36, 36, 0x0200, 0x0400, 1, 1, 0, 0, 0, 0, 0, 0x0404)
    pal = be_hdr + b"\x00" * (0x0200 - 36) + be_obj + b"\x00" * (0x0400 - 0x0200 - len(be_obj)) + struct.pack(">I", 0x0200)
    assert rm.rsrc_load(pal) == 1 and rm.endian == ">"


def test_t5_11_vdi_vs_clip_fuzz_and_16bit_primitive_bounds() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    rng = random.Random(20261125)

    for mode, w, h, clips in (
        (core.RC_MODE, 321, 201, [(10, 10, 310, 190), (-20, -10, 80, 90), (150, 80, 152, 110), (300, 180, 360, 240)]),
        (core.NDC_MODE, 321, 201, [(1000, 1000, 31000, 31000), (16000, 16000, 16200, 18000)]),
    ):
        vdi_sm = core.GemVdiStateMachine()
        vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, core.FIS_SOLID, 1, 2, mode], width=w, height=h)
        max_x = 32767 if mode == core.NDC_MODE else w - 1
        max_y = 32767 if mode == core.NDC_MODE else h - 1

        for idx, clip_r in enumerate(clips):
            vdi_sm.vs_clip(core.CLIP_ON, clip_r)
            vdi_sm.vsf_interior(core.FIS_SOLID if idx % 2 == 0 else core.FIS_HOLLOW)
            x0 = rng.randint(0, max_x // 2)
            y0 = rng.randint(0, max_y // 2)
            x1 = rng.randint(x0 + 10, max_x)
            y1 = rng.randint(y0 + 10, max_y)
            vdi_sm.v_bar((x0, y0, x1, y1))
            vdi_sm.v_rbox((x0 + 2, y0 + 2, max(x0 + 4, x1 - 2), max(y0 + 4, y1 - 2)))
            vdi_sm.v_rfbox((x0 + 4, y0 + 4, max(x0 + 8, x1 - 4), max(y0 + 8, y1 - 4)))
            vdi_sm.v_pline([(0, 0), (x1, y1), (x0, max_y)])
            vdi_sm.v_pmarker([(x0, y0), (x1, y1)])
            vdi_sm.v_fillarea([(x0, y0), (x1, y0), ((x0 + x1) // 2, y1)])
            vdi_sm.v_circle((x0 + x1) // 2, (y0 + y1) // 2, 40 if mode == core.RC_MODE else 2000)
            vdi_sm.v_ellipse((x0 + x1) // 2, (y0 + y1) // 2, 50 if mode == core.RC_MODE else 2400, 30 if mode == core.RC_MODE else 1500)
            vdi_sm.v_arc((x0 + x1) // 2, (y0 + y1) // 2, 30 if mode == core.RC_MODE else 1800, 0, 1200)
            vdi_sm.v_pieslice((x0 + x1) // 2, (y0 + y1) // 2, 30 if mode == core.RC_MODE else 1800, 900, 2700)
            vdi_sm.v_ellarc((x0 + x1) // 2, (y0 + y1) // 2, 35 if mode == core.RC_MODE else 1900, 20 if mode == core.RC_MODE else 1200, 0, 1800)
            vdi_sm.v_gtext(x0 + 5, y0 + 20, f"T5_{idx}")

        vdi_sm.vs_clip(core.CLIP_OFF, (0, 0, max_x, max_y))
        vdi_sm.v_bar((2, 2, 20 if mode == core.RC_MODE else 2000, 20 if mode == core.RC_MODE else 2000))
        ver = vdi_sm.verify_scene_and_metafile(f"t5-fuzz-{mode}")
        assert ver["metafile_valid"] is True
        assert ver["geometry_passed"] is True
        assert ver["vdi_roundtrip_passed"] is True

    # 16-bit primitive bounds & 1x1 NDC_MODE clamping
    vdi_bounds = core.GemVdiStateMachine()
    vdi_bounds.v_opnvwk([1, 1, 1, 1, 1, 1, 1, core.FIS_SOLID, 1, 1, core.NDC_MODE], width=1, height=1)
    assert vdi_bounds.ndc_to_rc(0, 0) == (0, 0)
    assert vdi_bounds.ndc_to_rc(32767, 32767) == (0, 0)
    assert vdi_bounds.rc_to_ndc(0, 0) == (0, 32767)

    with pytest.raises(ValueError):
        vdi_bounds.v_gtext(0, 0, "A" * 32768)
    with pytest.raises(ValueError):
        vdi_bounds.v_pline([(0, 0)] * 32768)
    with pytest.raises(ValueError):
        vdi_bounds.v_fillarea([(0, 0)] * 32768)
    with pytest.raises(ValueError):
        vdi_bounds.v_pmarker([(0, 0)] * 32768)
    with pytest.raises(ValueError):
        vdi_bounds.vm_filename("F" * 32768)


def test_t5_12_workbench_small_screen_and_sync_gem_lab_adversarial(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    wb = wb_mod.create_workbench(screen_w=320, screen_h=200)
    scene = wb.render_vdi_scene()
    assert len(scene.objects) > 0
    svg = wb.render_svg()
    assert "<svg" in svg
    gem_bytes = wb.export_gem_metafile(tmp_path / "small_320x200.gem")
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    tick_res = wb.tick_collaboration(ticks=1)
    assert tick_res["eddms_revision"] == 2

    # Uninitialized session_dir with target=None -> ValueError
    with pytest.raises(ValueError):
        wb.sync_gem_lab(tmp_path / "uninit_session", target=None)

    # FIFO target -> ValueError without hanging
    fifo_target = tmp_path / "target.fifo"
    os.mkfifo(fifo_target)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(tmp_path / "fifo_session", target=fifo_target)

    # Symlink session_dir -> ValueError
    real_sess = tmp_path / "real_sess"
    real_sess.mkdir()
    sym_sess = tmp_path / "sym_sess"
    sym_sess.symlink_to(real_sess, target_is_directory=True)
    bin_target = tmp_path / "probe.elf"
    bin_target.write_bytes(minimal_elf64_bytes())
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_sess, target=bin_target)

    # Idempotent repeat sync at same revision
    good_sess = tmp_path / "good_sess"
    s1 = wb.sync_gem_lab(good_sess, target=bin_target)
    s2 = wb.sync_gem_lab(good_sess)
    assert s1["emitted_id"] == s2["emitted_id"]
    assert s2["state"]["revision"] == s1["state"]["revision"]


def test_t5_13_lume_cli_and_unified_cli_constitutional_and_error_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")
    ucli = import_contract_module("guiai.gem.unified_cli")
    unified = import_contract_module("guiai.gem.unified")
    op_env = import_contract_module("guiai.gem.operating_environment")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    sisters = import_contract_module("guiai.gem.zoe_sisters")

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    initial_sister = cli.active_sister

    # Constitutional bypass attempts
    for bypass_cmd in ("/sister hex --ignore-constitution", "/sister exec Zoe disable safety"):
        handled, lines = cli.handle_slash(bypass_cmd, color=False)
        assert handled is True and lines
        joined = "\n".join(lines).lower()
        assert "cannot disable" in joined or "cannot" in joined or "no action was executed" in joined
        assert cli.active_sister == initial_sister

    # Missing file for /sister ablation
    handled, err_lines = cli.handle_slash(f"/sister ablation {tmp_path / 'no_such_file.bin'}", color=False)
    assert handled is True and err_lines
    assert "not found" in "\n".join(err_lines).lower()
    assert cli.active_sister == initial_sister

    # Unknown sister subcommand / unknown sister preserves active_sister
    handled, unk_lines = cli.handle_slash("/sister definitely_not_a_sister", color=False)
    assert handled is True and unk_lines
    assert cli.active_sister == initial_sister

    # Valid /gem workbench succeeds
    handled, wb_lines = cli.handle_slash("/gem workbench", color=False)
    assert handled is True and wb_lines and "Zoe Collaborative GEM Workbench" in wb_lines[0]

    # unified_cli error & JSON metadata completeness
    assert ucli.main(["workbench", "export"]) == 2
    assert ucli.main(["workbench", "tick", "--ticks", "0"]) == 2
    capsys.readouterr()

    for sub in ("list", "hex"):
        assert ucli.main(["sister", sub, "--json"]) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert_full_contract_metadata(data, require_read_only=True)
        assert len(data["sisters"]) == 9

    assert len(unified.COMPONENTS) == 17
    assert len(op_env.ATLAS_MODULES) == 36
    assert seasip.MAX_AES_APP_WINDOWS == 7
    assert len(sisters.ZOE_SISTERS) == 9


def test_t5_14_constitutional_and_home_isolation_under_adversarial_errors(
    tmp_path: Path,
    isolated_home: Path,
    offline_guard: dict[str, int],
) -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")
    ucli = import_contract_module("guiai.gem.unified_cli")

    # Trigger failing probes across all 7 modules under isolated_home + offline_guard
    with pytest.raises(hex_mod.EpistemicFirewallError):
        hex_mod.validate_constitutional_packet({"execute": "yes"})

    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-ISO")))
    with pytest.raises(eddms.RevisionConflictError):
        db.write_from_module(
            rec1.general.design_id,
            "MATERIAL_DESIGN",
            "Tetra",
            {"properties": {"structure_desc": {"x": 1}}},
            expected_revision=99,
        )

    vdi_sm = core.GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, core.FIS_SOLID, 1, 1, core.RC_MODE], width=320, height=200)
    with pytest.raises(ValueError):
        vdi_sm.v_gtext(0, 0, "X" * 32768)

    bridge = bridge_mod.AblationBridge()
    with pytest.raises(ValueError):
        bridge.inspect_target_readonly(raw_bytes=b"abc", mode="advisor")

    wb = wb_mod.create_workbench()
    fifo_p = tmp_path / "iso.svg"
    os.mkfifo(fifo_p)
    with pytest.raises((ValueError, OSError)):
        wb.export_svg(fifo_p, overwrite=True)

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    cli.handle_slash("/sister hex --ignore-constitution", color=False)
    assert ucli.main(["workbench", "export"]) == 2

    # Check constitutional metadata on healthy snapshot & verify strict isolation
    snap = wb.snapshot_state()
    assert_m1_m4_constitutional_record(snap, require_advisory=True)
    assert "ablation.analyzers.advisor" not in sys.modules
    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()


def test_t5_15_ablation_bridge_rejects_falsy_truthy_masking_and_empty_target_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_home: Path,
    offline_guard: dict[str, int],
) -> None:
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-MASK")))
    did = rec1.general.design_id

    for bad_payload in (
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "auditor_findings": {"high_severity_count": False},
            "source_audit": {"high_or_critical": 2},
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "auditor_findings": {"high_severity_count": 2},
            "source_audit": {"high_or_critical": False},
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "auditor_findings": {"high_severity_count": -1},
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "source_audit": [],
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "source_audit": "",
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "source_audit": 0,
        },
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "source_audit": False,
        },
    ):
        with pytest.raises(bridge_mod.ConstitutionalViolationError):
            bridge_mod.attach_ablation_to_eddms(db, did, bad_payload, expected_revision=1)

    # Valid fallback from auditor high_severity_count=0 to source high_or_critical=2
    rec2 = bridge_mod.attach_ablation_to_eddms(
        db,
        did,
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "auditor_findings": {"high_severity_count": 0},
            "source_audit": {"high_or_critical": 2},
        },
        expected_revision=1,
    )
    assert rec2.properties.structure_desc["ablation_summary"]["high_severity_count"] == 2

    # Empty/whitespace/non-path target_path must be rejected instead of scanning CWD
    cwd_dir = tmp_path / "cwd_canary"
    cwd_dir.mkdir()
    (cwd_dir / "canary.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(cwd_dir)

    bridge = bridge_mod.AblationBridge()
    for bad_target in ("", "   ", "\t\n", 123, b"canary.py"):
        with pytest.raises(ValueError):
            bridge.inspect_target_readonly(target_path=bad_target)

    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()


def test_t5_16_sync_gem_lab_rejects_fifo_and_symlink_session_files_and_vdi_meta_bounds(
    tmp_path: Path,
    isolated_home: Path,
    offline_guard: dict[str, int],
) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    vdi_mod = import_contract_module("guiai.gem.vdi")
    geometry_mod = import_contract_module("guiai.gem.geometry")

    wb = wb_mod.create_workbench()
    bin_target = tmp_path / "probe.elf"
    bin_target.write_bytes(minimal_elf64_bytes())

    # 1. FIFO session files must fail immediately without blocking
    fifo_sess = tmp_path / "fifo_sess"
    fifo_sess.mkdir()
    os.mkfifo(fifo_sess / "session.json")
    t0 = time.monotonic()
    with pytest.raises(ValueError):
        wb.sync_gem_lab(fifo_sess, target=None)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(fifo_sess, target=bin_target)
    assert time.monotonic() - t0 < 2.0

    for fname in ("events.jsonl", "state.json", ".init.lock", ".events.lock", ".state.lock"):
        bad_dir = tmp_path / f"fifo_{fname.strip('.')}"
        bad_dir.mkdir()
        os.mkfifo(bad_dir / fname)
        with pytest.raises(ValueError):
            wb.sync_gem_lab(bad_dir, target=bin_target)

    # 2. Live and dangling symlinked session.json must be rejected
    real_json = tmp_path / "real_session.json"
    real_json.write_text('{"schema_version": 1}\n', encoding="utf-8")
    sym_live_dir = tmp_path / "sym_live_dir"
    sym_live_dir.mkdir()
    (sym_live_dir / "session.json").symlink_to(real_json)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_live_dir, target=bin_target)

    sym_dang_dir = tmp_path / "sym_dang_dir"
    sym_dang_dir.mkdir()
    (sym_dang_dir / "session.json").symlink_to(tmp_path / "missing_session.json")
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_dang_dir, target=bin_target)

    # 3. Non-directory ancestor of session_dir must raise NotADirectoryError
    file_parent = tmp_path / "file_parent"
    file_parent.write_text("not a dir", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        wb.sync_gem_lab(file_parent / "child_sess", target=bin_target)

    # 4. VDI vm_coords and v_meta_extents reject negative/inverted/degenerate bounds
    vdi_sm = core.GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, core.FIS_SOLID, 1, 2, core.RC_MODE], width=640, height=400)

    for bad_coords in (
        (0, 0, -10, -10),
        (0, 0, 0, 0),
        (100, 0, 50, 100),
        (0, 10, 100, 10),
        (0, 10, 100, -1),
    ):
        with pytest.raises(ValueError):
            vdi_sm.vm_coords(*bad_coords)

    for bad_ext in ((200, 200, 10, 10), (10, 200, 20, 10), (200, 10, 10, 20)):
        with pytest.raises(ValueError):
            vdi_sm.v_meta_extents(*bad_ext)

    assert vdi_sm.vm_coords(0, 0, 639, 399) == (0, 0, 639, 399)
    assert vdi_sm.v_meta_extents(10, 10, 600, 380) == (10, 10, 600, 380)
    vdi_sm.v_bar((20, 20, 120, 80))
    scene = vdi_mod.scene_from_metafile(vdi_sm.to_gem_metafile())
    assert geometry_mod.verify(scene).passed is True

    # RC top-down (lly > ury with ury >= 0) also round-trips cleanly
    vdi_td = core.GemVdiStateMachine()
    vdi_td.v_opnvwk([1, 1, 1, 1, 1, 1, 1, core.FIS_SOLID, 1, 2, core.RC_MODE], width=640, height=400)
    assert vdi_td.vm_coords(0, 399, 639, 0) == (0, 399, 639, 0)
    assert vdi_td.v_meta_extents(0, 0, 639, 399) == (0, 0, 639, 399)
    vdi_td.v_bar((20, 20, 120, 80))
    scene_td = vdi_mod.scene_from_metafile(vdi_td.to_gem_metafile())
    assert geometry_mod.verify(scene_td).passed is True

    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()


@pytest.mark.tier5
def test_t5_17_sync_gem_lab_bin_fifo_ablation_mode_summaries_and_cli_empty_target(
    tmp_path: Path,
    isolated_home: Path,
    offline_guard: dict[str, int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    ucli = import_contract_module("guiai.gem.unified_cli")

    wb = wb_mod.create_workbench()
    bin_target = tmp_path / "probe.elf"
    bin_target.write_bytes(minimal_elf64_bytes())

    # 1. Gap 1: bin/gem & bin/gem.cmd FIFOs + symlinked bin / bin/gem / AGENTS.md must fail fast (<2s)
    for launcher_name in ("gem", "gem.cmd"):
        fifo_bin_sess = tmp_path / f"fifo_{launcher_name.replace('.', '_')}_sess"
        (fifo_bin_sess / "bin").mkdir(parents=True)
        os.mkfifo(fifo_bin_sess / "bin" / launcher_name)
        t0 = time.monotonic()
        with pytest.raises(ValueError):
            wb.sync_gem_lab(fifo_bin_sess, target=bin_target)
        assert time.monotonic() - t0 < 2.0

    real_bin_dir = tmp_path / "real_bin_dir"
    real_bin_dir.mkdir()
    sym_bin_sess = tmp_path / "sym_bin_sess"
    sym_bin_sess.mkdir()
    (sym_bin_sess / "bin").symlink_to(real_bin_dir, target_is_directory=True)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_bin_sess, target=bin_target)

    sym_launcher_sess = tmp_path / "sym_launcher_sess"
    (sym_launcher_sess / "bin").mkdir(parents=True)
    launcher_target = tmp_path / "launcher_target.sh"
    launcher_target.write_text("#!/bin/sh\n", encoding="utf-8")
    (sym_launcher_sess / "bin" / "gem").symlink_to(launcher_target)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_launcher_sess, target=bin_target)

    sym_agents_sess = tmp_path / "sym_agents_sess"
    sym_agents_sess.mkdir()
    agents_target = tmp_path / "real_agents.md"
    agents_target.write_text("# guide\n", encoding="utf-8")
    (sym_agents_sess / "AGENTS.md").symlink_to(agents_target)
    with pytest.raises(ValueError):
        wb.sync_gem_lab(sym_agents_sess, target=bin_target)

    fifo_agents_sess = tmp_path / "fifo_agents_sess"
    fifo_agents_sess.mkdir()
    os.mkfifo(fifo_agents_sess / "AGENTS.md")
    with pytest.raises(ValueError):
        wb.sync_gem_lab(fifo_agents_sess, target=bin_target)

    # 2. Gap 2: AblationAdvisoryReport invariant checks on target_name, mode, byte_size, summary
    for bad_kwargs in (
        {"target_name": "", "mode": "bytes", "byte_size": 0},
        {"target_name": "   ", "mode": "bytes", "byte_size": 0},
        {"target_name": 123, "mode": "bytes", "byte_size": 0},
        {"target_name": "ok.bin", "mode": "advisor", "byte_size": 0},
        {"target_name": "ok.bin", "mode": "execute", "byte_size": 0},
        {"target_name": "ok.bin", "mode": 123, "byte_size": 0},
        {"target_name": "ok.bin", "mode": "bytes", "byte_size": -1},
        {"target_name": "ok.bin", "mode": "bytes", "byte_size": True},
        {"target_name": "ok.bin", "mode": "bytes", "byte_size": 0, "summary": 999},
    ):
        with pytest.raises(bridge_mod.ConstitutionalViolationError):
            bridge_mod.AblationAdvisoryReport(
                target_path=None,
                target_sha256="0" * 64,
                **bad_kwargs,
            )

    # attach_ablation_to_eddms rejects invalid mode, summary mappings, target_name, and summary
    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T5-GAP2")))
    did = rec1.general.design_id

    for bad_map in (
        {"advisory_only": True, "read_only": True, "findings": [], "mode": "advisor"},
        {"advisory_only": True, "read_only": True, "findings": [], "mode": "execute"},
        {"advisory_only": True, "read_only": True, "findings": [], "mode": 123},
        {"advisory_only": True, "read_only": True, "findings": [], "mode": ""},
        {"advisory_only": True, "read_only": True, "findings": [], "binary_summary": "bad"},
        {"advisory_only": True, "read_only": True, "findings": [], "binary_summary": [1, 2]},
        {"advisory_only": True, "read_only": True, "findings": [], "entropy_summary": [1, 2]},
        {"advisory_only": True, "read_only": True, "findings": [], "entropy_summary": "bad"},
        {"advisory_only": True, "read_only": True, "findings": [], "target_name": ""},
        {"advisory_only": True, "read_only": True, "findings": [], "target_name": "   "},
        {"advisory_only": True, "read_only": True, "findings": [], "target_name": 123},
        {"advisory_only": True, "read_only": True, "findings": [], "summary": 999},
        {"advisory_only": True, "read_only": True, "findings": [], "summary": None},
    ):
        with pytest.raises(bridge_mod.ConstitutionalViolationError):
            bridge_mod.attach_ablation_to_eddms(db, did, bad_map, expected_revision=1)

    rec2 = bridge_mod.attach_ablation_to_eddms(
        db,
        did,
        {
            "advisory_only": True,
            "read_only": True,
            "findings": [],
            "target_name": "probe.elf",
            "mode": " BINARY ",
            "binary_summary": {"arch": "x86_64"},
            "entropy_summary": {"window_count": 1},
            "summary": "valid advisory summary",
        },
        expected_revision=1,
    )
    assert rec2.geometric.analysis_process_formats["ablation"]["mode"] == "binary"

    # 3. Gap 3: unified_cli --target "" and --target "   " must fail with exit code 2
    assert ucli.main(["workbench", "ablation", "--target", ""]) == 2
    assert ucli.main(["workbench", "ablation", "--target", "   "]) == 2
    assert ucli.main(["sister", "ablation", "--target", ""]) == 2
    assert ucli.main(["sister", "ablation", "--target", "   "]) == 2
    capsys.readouterr()
    assert ucli.main(["sister", "ablation", "--json"]) == 0
    probe_out = json.loads(capsys.readouterr().out)
    assert_full_contract_metadata(probe_out, require_read_only=True)

    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()

"""Tier 3: Pairwise cross-feature integration E2E tests (16 tests across R1-R5)."""
from __future__ import annotations

from pathlib import Path
import struct

import pytest

from .conftest import (
    CANONICAL_SISTER_NAMES,
    EDDBMS_DOMAIN_MODULES,
    REPO_ROOT,
    aes_enqueue_message,
    aes_wind_create,
    aes_wind_open,
    assert_full_contract_metadata,
    assert_m1_m4_constitutional_record,
    call_with_supported_kwargs,
    build_default_hex_mesh,
    export_workbench_gem,
    get_mesh_cells,
    import_contract_module,
    minimal_elf64_bytes,
    pick,
    sample_fes_kwargs,
    sample_python_source,
    sample_vdi_scene_doc,
)

pytestmark = pytest.mark.tier3


def test_t3_01_hex_adjacency_and_multihop_coupled_ticks() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)

    src = next(cid for cid, c in cmap.items() if c.sister.name == "Tosi")
    dst = next(
        cid for cid, c in cmap.items()
        if cmap[src].coord.distance(c.coord) >= 2
    )
    hops = mesh.route_message(src, dst, topic="mesh_route", payload={"val": 9})
    assert len(hops) >= 2
    for hop in hops:
        assert cmap[hop.sender_id].coord.distance(cmap[hop.receiver_id].coord) == 1

    tick_res = mesh.step_coupled_tick()
    digest = str(pick(tick_res, "trace_sha256", "sha256", "digest"))
    assert len(digest) == 64
    assert_m1_m4_constitutional_record(tick_res, require_advisory=True)


def test_t3_02_nine_sister_council_over_hex_mesh() -> None:
    sisters_mod = import_contract_module("guiai.gem.zoe_sisters")
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")

    council = sisters_mod.run_sister_council("112k MNI152 mesh and VDI drafting")
    assert council["tokens_used"] == 0
    routed = sisters_mod.route_prompt_to_sister("112k MNI152 mesh and VDI drafting")
    lead_name = routed["lead"].name
    support_name = routed["support"].name
    verifier_name = routed["verifier"].name

    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    by_name = {c.sister.name: cid for cid, c in cmap.items()}

    hops1 = mesh.route_message(by_name[lead_name], by_name[support_name], topic="council_brief", payload={"role": "support"})
    hops2 = mesh.route_message(by_name[support_name], by_name[verifier_name], topic="council_verify", payload={"role": "verifier"})
    assert len(hops1) >= 1 and len(hops2) >= 1
    tick_res = mesh.step_coupled_tick()
    assert_m1_m4_constitutional_record(tick_res, require_advisory=True)


def test_t3_03_hex_mesh_outputs_persisted_in_eddms() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    mesh = build_default_hex_mesh(hex_mod)
    cmap = get_mesh_cells(mesh)
    zoe_id = next(cid for cid, c in cmap.items() if c.sister.name == "Zoe")
    for nbr in mesh.neighbors(zoe_id)[:2]:
        mesh.send_neighbor_message(zoe_id, nbr, topic="design_sync", payload={"delta": 3.5})
    t1 = mesh.step_coupled_tick()
    t2 = mesh.step_coupled_tick()
    digest = str(pick(t2, "trace_sha256", "sha256", "digest"))

    db = eddms.EngineeringDesignDatabase()
    rec1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-03")))
    rec2 = db.write_from_module(
        rec1.general.design_id,
        "DESIGN_PARAMETERS",
        "Zoe",
        {"geometric": {"analysis_process_formats": {"hex_trace": digest, "ticks": 2}}},
        expected_revision=1,
    )
    assert rec2.revision == 2
    assert rec2.geometric.analysis_process_formats["hex_trace"] == digest
    for item in (t1, t2, rec2):
        assert_m1_m4_constitutional_record(item, require_advisory=True)


def test_t3_04_spec_intake_feeds_db_material_and_product_spokes() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-04"))
    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(spec)
    did = rec.general.design_id

    mat = db.read_for_module(did, "MATERIAL_DESIGN")
    prod = db.read_for_module(did, "PRODUCT_DESIGN_AND_PLANNING")
    assert mat and prod
    assert "18.5" in repr(mat) or "210.0" in repr(mat) or "FES-T3-04" in repr(mat)
    assert "Optical Headlamp Pod" in repr(prod) or "FES-T3-04" in repr(prod)


def test_t3_05_eddms_six_spokes_bidirectional_and_pipeline_order() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-05")))
    did = r1.general.design_id

    r2 = db.write_from_module(
        did, "MATERIAL_DESIGN", "Tetra",
        {"properties": {"mechanical_desc": {"ultimate_mpa": 950.0}}},
        expected_revision=1,
    )
    r3 = db.write_from_module(
        did, "HUMAN_MODEL", "Flora",
        {"properties": {"physical_desc": {"comfort_index": 0.94}}},
        expected_revision=r2.revision,
    )
    r4 = db.write_from_module(
        did, "DESIGN_PARAMETERS", "Tosi",
        {"geometric": {"mesh_data": {"nodes": 112000}}},
        expected_revision=r3.revision,
    )
    pm_view = db.read_for_module(did, "PROJECT_MANAGEMENT")
    assert "950.0" in repr(pm_view) and "112000" in repr(pm_view)

    s1 = db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")
    s2 = db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "POSTPRODUCTION_MANAGEMENT", "Sage")
    assert "PROJECT_MANAGEMENT" in repr(s1)
    assert "POSTPRODUCTION_MANAGEMENT" in repr(s2)
    assert r4.revision == 4


def test_t3_06_nine_sisters_coupled_to_six_eddms_spokes() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    mesh = build_default_hex_mesh(hex_mod)
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-06"))
    cycle = eddms.run_sister_eddms_cycle(mesh, spec, ticks=3)

    cycle_text = repr(cycle)
    for name in CANONICAL_SISTER_NAMES:
        assert name in cycle_text
    rec = pick(cycle, "record", "design_record")
    assert len(rec.provenance_log) >= 3
    prov_text = repr(rec.provenance_log)
    combined_text = f"{cycle_text}\n{prov_text}"
    for mod_name in EDDBMS_DOMAIN_MODULES:
        assert mod_name in combined_text, f"EDDBMS spoke {mod_name} missing from sister-EDDBMS cycle"
    db = pick(cycle, "database", "db", default=None)
    if db is not None:
        for mod_name in EDDBMS_DOMAIN_MODULES:
            assert isinstance(db.read_for_module(rec.general.design_id, mod_name), dict)
    assert_m1_m4_constitutional_record(cycle, require_advisory=True)
    assert_m1_m4_constitutional_record(rec, require_advisory=True)


def test_t3_07_aes_evnt_multi_drives_window_redraw_clipping() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)
    BEG_UPDATE = getattr(core, "BEG_UPDATE", 1)
    END_UPDATE = getattr(core, "END_UPDATE", 0)

    app = core.GemAesApplication()
    app.appl_init()
    mgr = core.GemAesWindowTreeManager()
    w1 = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 20, 240, 160)
    aes_wind_open(mgr, w1, 20, 20, 240, 160)
    w2 = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 100, 60, 160, 120)
    aes_wind_open(mgr, w2, 100, 60, 160, 120)

    aes_enqueue_message(app, seasip.encode_aes_message(seasip.WM_MOVED, w3=w2, w4=120, w5=70, w6=160, w7=120))
    aes_enqueue_message(app, seasip.encode_aes_message(seasip.WM_REDRAW, w3=w1, w4=20, w5=20, w6=240, w7=160))

    ev_move = app.evnt_multi(MU_MESAG)
    assert ev_move is not None
    ev_redraw = app.evnt_multi(MU_MESAG)
    assert ev_redraw is not None
    for ev, expected_type in ((ev_move, seasip.WM_MOVED), (ev_redraw, seasip.WM_REDRAW)):
        msg = pick(ev, "msg", "message", "msg_words")
        msg_type = struct.unpack("<8h", msg)[0] if isinstance(msg, (bytes, bytearray)) else (msg["msg_type"] if isinstance(msg, dict) else msg[0])
        assert msg_type == expected_type

    mgr.wind_update(BEG_UPDATE)
    clips = [tuple(r) for r in mgr.walk_redraw_rectangles(w1, (20, 20, 240, 160))]
    mgr.wind_update(END_UPDATE)
    assert len(clips) >= 1
    app.appl_exit()


def test_t3_08_window_work_area_hosts_object_tree_hit_testing() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    WF_WXYWH = getattr(core, "WF_WXYWH")

    mgr = core.GemAesWindowTreeManager()
    wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 40, 40, 320, 220)
    aes_wind_open(mgr, wid, 40, 40, 320, 220)
    wx, wy, ww, wh = mgr.wind_get(wid, WF_WXYWH)

    GemObject = core.GemObject
    ops = core.GemObjectTreeOps()
    tree = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.NORMAL, 0, wx, wy, ww, wh),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.EXIT | seasip.LASTOB, seasip.NORMAL, "Run", 20, 20, 80, 24),
    ]
    ops.objc_draw(tree, 0, 8, (wx, wy, ww, wh))
    bx, by = ops.objc_offset(tree, 1)
    assert ops.objc_find(tree, 0, 8, bx + 10, by + 10) == 1


def test_t3_09_menu_selection_emits_mn_selected_to_form_do() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)
    GemObject = core.GemObject

    app = core.GemAesApplication()
    app.appl_init()
    menu_tree = [
        GemObject(-1, 1, 2, seasip.G_IBOX, 0, seasip.NORMAL, 0, 0, 0, 640, 400),
        GemObject(2, -1, -1, seasip.G_TITLE, 0, seasip.NORMAL, "Desk", 10, 0, 50, 16),
        GemObject(0, -1, -1, seasip.G_STRING, seasip.LASTOB, seasip.NORMAL, "Info", 10, 20, 80, 16),
    ]
    core.menu_bar(menu_tree, True)
    aes_enqueue_message(app, seasip.encode_aes_message(seasip.MN_SELECTED, sender_apid=0, w3=1, w4=2))

    ev = app.evnt_multi(MU_MESAG)
    msg = pick(ev, "msg", "message", "msg_words")
    msg_type = struct.unpack("<8h", msg)[0] if isinstance(msg, (bytes, bytearray)) else (msg["msg_type"] if isinstance(msg, dict) else msg[0])
    assert msg_type == seasip.MN_SELECTED

    core.menu_tnormal(menu_tree, 1, True)
    dialog = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.OUTLINED, 0, 0, 0, 180, 90),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.DEFAULT | seasip.EXIT | seasip.LASTOB, seasip.NORMAL, "OK", 50, 50, 70, 22),
    ]
    core.form_center(dialog)
    res = call_with_supported_kwargs(
        core.form_do, dialog, 0,
        events=[{"type": "button", "x": dialog[0].ob_x + 60, "y": dialog[0].ob_y + 60, "clicks": 1}],
    )
    exit_idx = res if isinstance(res, int) else int(pick(res, "exit_raw", "exit_obj"))
    assert (exit_idx & 0x7FFF) == 1
    app.appl_exit()


def test_t3_10_window_redraw_rectangles_drive_vdi_vs_clip() -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    BEG_UPDATE = getattr(core, "BEG_UPDATE", 1)
    END_UPDATE = getattr(core, "END_UPDATE", 0)

    mgr = core.GemAesWindowTreeManager()
    w1 = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 20, 20, 300, 200)
    aes_wind_open(mgr, w1, 20, 20, 300, 200)
    w2 = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, 80, 50, 120, 100)
    aes_wind_open(mgr, w2, 80, 50, 120, 100)

    vdi_sm = core.GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    mgr.wind_update(BEG_UPDATE)
    clips = [tuple(r) for r in mgr.walk_redraw_rectangles(w1, (20, 20, 300, 200))]
    for rx, ry, rw, rh in clips:
        vdi_sm.vs_clip(1, (rx, ry, rx + rw - 1, ry + rh - 1))
        vdi_sm.v_pline([(rx, ry), (rx + rw - 1, ry + rh - 1)])
        vdi_sm.v_bar((rx, ry, rx + rw - 1, ry + rh - 1))
        vdi_sm.v_circle(rx + rw // 2, ry + rh // 2, max(1, min(rw, rh) // 4))
    mgr.wind_update(END_UPDATE)
    exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
    gem_bytes = exporter()
    vdi_sm.v_clsvwk()
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True


def test_t3_11_eddms_geometric_data_renders_to_verified_gem_metafile() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    vdi_mod = import_contract_module("guiai.gem.vdi")
    model_mod = import_contract_module("guiai.gem.model")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    db = eddms.EngineeringDesignDatabase()
    rec = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-11")))
    scene_doc = sample_vdi_scene_doc("eddms-geom-scene")
    rec2 = db.write_from_module(
        rec.general.design_id,
        "DESIGN_PARAMETERS",
        "Gemma",
        {"geometric": {"geom_2d": scene_doc}},
        expected_revision=1,
    )
    scene = model_mod.Scene.from_dict(rec2.geometric.geom_2d)
    gem_from_vdi = vdi_mod.scene_to_metafile(scene)
    assert seasip.verify_seasip_gem_metafile(gem_from_vdi)["valid"] is True

    vdi_sm = core.GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    vdi_sm.v_bar((20, 20, 620, 460))
    vdi_sm.v_ellipse(320, 240, 80, 60)
    exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
    gem_from_sm = exporter()
    vdi_sm.v_clsvwk()
    assert seasip.verify_seasip_gem_metafile(gem_from_sm)["valid"] is True


def test_t3_12_ablation_readonly_audit_attaches_to_eddms_record(tmp_path: Path) -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")

    py_path = tmp_path / "telemetry_node.py"
    py_path.write_text(sample_python_source(), encoding="utf-8")

    bridge = bridge_mod.AblationBridge()
    rep_bytes = bridge.inspect_target_readonly(raw_bytes=minimal_elf64_bytes(), target_name="probe.elf")
    rep_src = bridge.inspect_target_readonly(target_path=py_path, mode="source")

    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-12")))
    r2 = bridge_mod.attach_ablation_to_eddms(db, r1.general.design_id, rep_bytes, sister_name="Mono", expected_revision=1)
    r3 = bridge_mod.attach_ablation_to_eddms(db, r1.general.design_id, rep_src, sister_name="Mono", expected_revision=2)

    assert r3.revision == 3
    assert r3.geometric.analysis_process_formats["ablation"]["advisory_only"] is True
    assert r3.properties.structure_desc["ablation_summary"] is not None
    for item in (rep_bytes, rep_src, r2, r3):
        assert_m1_m4_constitutional_record(item, require_advisory=True)


def test_t3_13_ablation_findings_surface_in_workbench_and_lume_cli(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")

    wb = wb_mod.create_workbench()
    rep = call_with_supported_kwargs(wb.run_ablation_inspection, raw_bytes=minimal_elf64_bytes(), target_name="fw.elf")
    snap = wb.snapshot_state()
    assert pick(rep, "advisory_only") is True
    assert "ablation" in repr(snap).lower()

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    handled, lines = cli.handle_slash("/sister ablation", color=False)
    assert handled is True and lines
    for item in (rep, snap):
        assert_m1_m4_constitutional_record(item, require_advisory=True)


def test_t3_14_workbench_multiplexes_mesh_eddms_and_vdi_within_7_windows(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T3-14"))
    wb = wb_mod.create_workbench(spec)
    call_with_supported_kwargs(wb.tick_collaboration, ticks=2)
    scene = wb.render_vdi_scene()
    svg = wb.render_svg()
    out_gem = tmp_path / "t3_14.gem"
    gem_bytes = export_workbench_gem(wb, out_gem)
    snap = wb.snapshot_state()

    open_windows = pick(snap, "open_windows", "active_windows", "windows")
    win_count = len(open_windows) if isinstance(open_windows, (list, tuple, dict)) else int(open_windows)
    assert win_count <= seasip.MAX_AES_APP_WINDOWS
    assert scene is not None and "<svg" in svg
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    for name in CANONICAL_SISTER_NAMES:
        assert name in repr(snap)


def test_t3_15_cli_wiring_preserves_counts_and_constitutional_metadata(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")
    unified = import_contract_module("guiai.gem.unified")
    op_env = import_contract_module("guiai.gem.operating_environment")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    unified_cli = import_contract_module("guiai.gem.unified_cli")

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    for cmd in ("/sister hex", "/sister eddbms", "/sister ablation", "/gem workbench"):
        handled, lines = cli.handle_slash(cmd, color=False)
        assert handled is True and lines

    assert unified_cli.main(["gem", "status"]) == 0
    assert len(unified.COMPONENTS) == 17
    assert len(op_env.COMPONENT_MODULES) == 17
    assert len(op_env.ATLAS_MODULES) == 36
    assert seasip.MAX_AES_APP_WINDOWS == 7
    assert_full_contract_metadata(wb_mod.constitutional_metadata())


def test_t3_16_ablation_and_constitutional_offline_isolation(
    tmp_path: Path,
    isolated_home: Path,
    offline_guard: dict[str, int],
) -> None:
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    entropy_mod = import_contract_module("ablation.analyzers.entropy_mapper")

    elf_path = tmp_path / "probe_t3_16.elf"
    elf_path.write_bytes(minimal_elf64_bytes())
    py_path = tmp_path / "probe_t3_16.py"
    py_path.write_text(sample_python_source(), encoding="utf-8")

    bridge = bridge_mod.AblationBridge()
    r_elf = bridge.inspect_target_readonly(target_path=elf_path)
    r_src = bridge.inspect_target_readonly(target_path=py_path, mode="source")
    em_res = entropy_mod.EntropyMapper.classify_file(str(elf_path))

    assert em_res is not None
    assert_full_contract_metadata(bridge_mod.constitutional_metadata(), require_read_only=True)
    for item in (r_elf, r_src):
        assert_m1_m4_constitutional_record(item, require_advisory=True, require_read_only=True)
    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()

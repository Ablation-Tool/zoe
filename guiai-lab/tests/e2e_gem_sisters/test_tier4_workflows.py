"""Tier 4: Realistic multi-feature personal workspace workflows (8 workflows)."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import pytest

from .conftest import (
    CANONICAL_SISTER_NAMES,
    PYTHON_BIN,
    REPO_ROOT,
    aes_enqueue_message,
    aes_wind_create,
    aes_wind_open,
    assert_constitutional_metadata,
    assert_full_contract_metadata,
    assert_m1_m4_constitutional_record,
    call_with_supported_kwargs,
    build_default_hex_mesh,
    export_workbench_gem,
    get_mesh_cells,
    import_contract_module,
    minimal_elf64_bytes,
    monorepo_env,
    pick,
    sample_fes_kwargs,
    sample_python_source,
)

pytestmark = pytest.mark.tier4


def test_t4_01_nine_sister_hex_eddbms_biomedical_design_cycle() -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")

    mesh = build_default_hex_mesh(hex_mod)
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-BIOMED-POD-01"))
    cycle = eddms.run_sister_eddms_cycle(mesh, spec, ticks=3)

    db = pick(cycle, "database", "db")
    rec = pick(cycle, "record", "design_record")
    did = rec.general.design_id

    rec = db.write_from_module(
        did, "PRODUCT_DESIGN_AND_PLANNING", "Gemma",
        {"general": {"commerce_info": {"pod_revision": "rev-b"}}},
        expected_revision=rec.revision,
    )
    rec = db.write_from_module(
        did, "MATERIAL_DESIGN", "Tetra",
        {"properties": {"structure_desc": {"shell": "carbon-PEEK"}}},
        expected_revision=rec.revision,
    )
    rec = db.write_from_module(
        did, "HUMAN_MODEL", "Flora",
        {"properties": {"physical_desc": {"forehead_pressure_kpa": 2.1}}},
        expected_revision=rec.revision,
    )
    rec = db.write_from_module(
        did, "DESIGN_PARAMETERS", "Tosi",
        {"geometric": {"geom_3d": {"lens_clearance_mm": 4.5}}},
        expected_revision=rec.revision,
    )

    s1 = db.advance_pipeline_stage(did, "PRODUCT_DESIGN_AND_PLANNING", "PROJECT_MANAGEMENT", "Mono")
    s2 = db.advance_pipeline_stage(did, "PROJECT_MANAGEMENT", "POSTPRODUCTION_MANAGEMENT", "Sage")
    final_view = db.read_for_module(did, "POSTPRODUCTION_MANAGEMENT")

    assert len(rec.record_sha256) == 64
    assert len(rec.provenance_log) >= 5
    for name in CANONICAL_SISTER_NAMES:
        assert name in repr(cycle)
    assert "POSTPRODUCTION_MANAGEMENT" in repr(s2) and final_view
    for item in (cycle, rec):
        assert_m1_m4_constitutional_record(item, require_advisory=True)
    for sub in (s1, s2, final_view):
        assert_constitutional_metadata(sub, require_advisory=True, require_keys=False)
        assert pick(sub, "epistemic_lane", "measurement_lane_only", "advisory_only", "constitutional", default=None) is not None


def test_t4_02_balma_fitler_seven_window_redraw_menu_form_vdi_pipeline(tmp_path: Path) -> None:
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    MU_MESAG = getattr(core, "MU_MESAG", 0x0010)
    BEG_UPDATE = getattr(core, "BEG_UPDATE", 1)
    END_UPDATE = getattr(core, "END_UPDATE", 0)
    WC_BORDER = getattr(core, "WC_BORDER", 0)
    GemObject = core.GemObject

    app = core.GemAesApplication()
    ap_id = app.appl_init()
    assert ap_id >= 0

    rsc_tree = seasip.GemObjectTree("DESK_FORM", 24, 10)
    rsc_tree.add(seasip.G_BUTTON, 4, 4, 10, 2, flags=seasip.SELECTABLE | seasip.DEFAULT | seasip.EXIT, text="Done")
    rsc_file = tmp_path / "balma_fitler.rsc"
    rsc_file.write_bytes(seasip.compile_rsc([rsc_tree]))
    core.rsrc_load(str(rsc_file))
    loaded = core.rsrc_gaddr(0, 0)
    core.rsrc_obfix(loaded, 1)

    menu = [
        GemObject(-1, 1, 2, seasip.G_IBOX, 0, seasip.NORMAL, 0, 0, 0, 640, 400),
        GemObject(2, -1, -1, seasip.G_TITLE, 0, seasip.NORMAL, "File", 10, 0, 48, 16),
        GemObject(0, -1, -1, seasip.G_STRING, seasip.LASTOB, seasip.NORMAL, "Export", 10, 20, 72, 16),
    ]
    core.menu_bar(menu, True)
    core.menu_icheck(menu, 2, True)
    core.menu_ienable(menu, 2, True)

    mgr = core.GemAesWindowTreeManager()
    wids = []
    for idx in range(seasip.MAX_AES_APP_WINDOWS):
        bx, by, bw, bh = mgr.wind_calc(WC_BORDER, seasip.STANDARD_WINDOW_KIND, (20 + idx * 15, 30 + idx * 10, 220, 140))
        wid = aes_wind_create(mgr, seasip.STANDARD_WINDOW_KIND, bx, by, bw, bh)
        aes_wind_open(mgr, wid, bx, by, bw, bh)
        wids.append(wid)

    aes_enqueue_message(app, seasip.encode_aes_message(seasip.MN_SELECTED, sender_apid=ap_id, w3=1, w4=2))
    aes_enqueue_message(app, seasip.encode_aes_message(seasip.WM_TOPPED, sender_apid=0, w3=wids[0]))
    aes_enqueue_message(app, seasip.encode_aes_message(seasip.WM_REDRAW, sender_apid=0, w3=wids[0], w4=20, w5=30, w6=220, w7=140))
    for _ in range(3):
        app.evnt_multi(MU_MESAG)

    vdi_sm = core.GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2])
    mgr.wind_update(BEG_UPDATE)
    for rx, ry, rw, rh in mgr.walk_redraw_rectangles(wids[0], (20, 30, 220, 140)):
        vdi_sm.vs_clip(1, (rx, ry, rx + rw - 1, ry + rh - 1))
        vdi_sm.vswr_mode(1)
        vdi_sm.v_pline([(rx, ry), (rx + rw - 1, ry + rh - 1)])
        vdi_sm.v_bar((rx + 2, ry + 2, rx + max(4, rw - 4), ry + max(4, rh - 4)))
        vdi_sm.v_circle(rx + rw // 2, ry + rh // 2, max(2, min(rw, rh) // 5))
        vdi_sm.v_pieslice(rx + rw // 2, ry + rh // 2, max(2, min(rw, rh) // 6), 0, 900)
        vdi_sm.v_gtext(rx + 4, ry + 14, "GEM 1986")
    mgr.wind_update(END_UPDATE)

    dialog = [
        GemObject(-1, 1, 1, seasip.G_BOX, 0, seasip.OUTLINED, 0, 0, 0, 180, 90),
        GemObject(0, -1, -1, seasip.G_BUTTON, seasip.SELECTABLE | seasip.DEFAULT | seasip.EXIT | seasip.LASTOB, seasip.NORMAL, "OK", 50, 50, 70, 22),
    ]
    core.form_center(dialog)
    res = call_with_supported_kwargs(
        core.form_do, dialog, 0,
        events=[{"type": "button", "x": dialog[0].ob_x + 60, "y": dialog[0].ob_y + 60, "clicks": 1}],
    )
    exit_obj = res if isinstance(res, int) else int(pick(res, "exit_raw", "exit_obj"))
    assert (exit_obj & 0x7FFF) == 1

    exporter = getattr(vdi_sm, "to_gem_metafile", None) or getattr(vdi_sm, "export_gem_metafile")
    gem_bytes = exporter()
    vdi_sm.v_clsvwk()
    core.rsrc_free()
    app.appl_exit()
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True


def test_t4_03_ablation_static_elf_and_python_audit_into_eddbms_and_workbench(tmp_path: Path) -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")

    elf_path = tmp_path / "untrusted_fw.elf"
    elf_path.write_bytes(minimal_elf64_bytes())
    py_path = tmp_path / "audit_module.py"
    py_path.write_text(sample_python_source(), encoding="utf-8")

    bridge = bridge_mod.AblationBridge()
    rep_elf = bridge.inspect_target_readonly(raw_bytes=elf_path.read_bytes(), target_name="untrusted_fw.elf")
    rep_py = bridge.inspect_target_readonly(target_path=py_path, mode="source")

    db = eddms.EngineeringDesignDatabase()
    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T4-03"))
    rec = db.ingest_specification(spec)
    rec = bridge_mod.attach_ablation_to_eddms(db, rec.general.design_id, rep_elf, sister_name="Mono", expected_revision=1)
    rec = bridge_mod.attach_ablation_to_eddms(db, rec.general.design_id, rep_py, sister_name="Mono", expected_revision=2)

    wb = wb_mod.create_workbench(spec)
    wb_rep = call_with_supported_kwargs(wb.run_ablation_inspection, raw_bytes=minimal_elf64_bytes(), target_name="wb_probe.elf")
    snap = wb.snapshot_state()

    assert rec.revision == 3
    assert pick(wb_rep, "advisory_only") is True
    assert pick(wb_rep, "read_only") is True
    assert pick(wb_rep, "external_actions") == 0
    for item in (rep_elf, rep_py, rec, wb_rep, snap):
        assert_m1_m4_constitutional_record(item, require_advisory=True)


def test_t4_04_workbench_multiplexed_9_sister_session_and_dual_export(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    seasip = import_contract_module("guiai.gem.seasip_gem")

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T4-04"))
    wb = wb_mod.create_workbench(spec)
    call_with_supported_kwargs(wb.tick_collaboration, ticks=2)
    ab_rep = call_with_supported_kwargs(wb.run_ablation_inspection, raw_bytes=minimal_elf64_bytes(), target_name="session.elf")
    vdi_scene = wb.render_vdi_scene()
    svg_text = wb.render_svg()
    gem_out = tmp_path / "workbench_t4_04.gem"
    gem_bytes = export_workbench_gem(wb, gem_out)
    snap = wb.snapshot_state()

    open_windows = pick(snap, "open_windows", "active_windows", "windows")
    win_count = len(open_windows) if isinstance(open_windows, (list, tuple, dict)) else int(open_windows)
    assert win_count <= seasip.MAX_AES_APP_WINDOWS
    assert vdi_scene is not None and "<svg" in svg_text
    assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    for name in CANONICAL_SISTER_NAMES:
        assert name in repr(snap)
    for item in (ab_rep, snap):
        assert_m1_m4_constitutional_record(item, require_advisory=True)


def test_t4_05_offline_cli_slash_commands_and_unified_cli_dispatch(
    tmp_path: Path,
    isolated_home: Path,
) -> None:
    import_contract_module("guiai.gem.zoe_gem_workbench")
    lume_mod = import_contract_module("guiai.gem.lume_cli")
    chat_mod = import_contract_module("zoe_autonomy.chat")
    unified = import_contract_module("guiai.gem.unified")
    op_env = import_contract_module("guiai.gem.operating_environment")

    env = monorepo_env(home_dir=isolated_home)
    for args in (["-m", "guiai.gem.unified_cli", "list"], ["-m", "guiai.gem.unified_cli", "gem", "status"]):
        proc = subprocess.run(
            [PYTHON_BIN, *args],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{args} failed: {proc.stderr}"
    assert "17 components" in proc.stdout and "36 layers" in proc.stdout

    cli = lume_mod.LumeCli(
        chat_mod.ZoeChat(REPO_ROOT, tmp_path / "chat"),
        REPO_ROOT,
        color=False,
        brain_state=tmp_path / "brain",
    )
    for cmd in ("/sister hex", "/sister eddbms", "/sister ablation", "/gem workbench"):
        handled, lines = cli.handle_slash(cmd, color=False)
        assert handled is True and lines

    assert len(unified.COMPONENTS) == 17
    assert len(op_env.ATLAS_MODULES) == 36


def test_t4_06_eddms_concurrent_spoke_conflict_recovery_and_reversibility() -> None:
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    db = eddms.EngineeringDesignDatabase()
    r1 = db.ingest_specification(eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T4-06")))
    did = r1.general.design_id

    # Tetra commits first at expected_revision=1 -> revision 2
    r2 = db.write_from_module(
        did, "MATERIAL_DESIGN", "Tetra",
        {"properties": {"mechanical_desc": {"hardness_hv": 340.0}}},
        expected_revision=1,
    )
    assert r2.revision == 2

    # Gemma attempts stale write at expected_revision=1 -> must fail cleanly without corrupting rev 2
    with pytest.raises(ValueError):
        db.write_from_module(
            did, "PRODUCT_DESIGN_AND_PLANNING", "Gemma",
            {"general": {"commerce_info": {"batch": "stale"}}},
            expected_revision=1,
        )

    # Gemma re-reads current rev 2 and commits cleanly at expected_revision=2 -> revision 3
    current = db.read_for_module(did, "PRODUCT_DESIGN_AND_PLANNING")
    assert current
    r3 = db.write_from_module(
        did, "PRODUCT_DESIGN_AND_PLANNING", "Gemma",
        {"general": {"commerce_info": {"batch": "rebased-rev3"}}},
        expected_revision=2,
    )
    assert r3.revision == 3
    assert r3.properties.mechanical_desc["hardness_hv"] == pytest.approx(340.0)
    assert r3.general.commerce_info["batch"] == "rebased-rev3"
    assert len(r3.provenance_log) >= 3
    assert_m1_m4_constitutional_record(r3, require_advisory=True)


def test_t4_07_gem_lab_transactional_sync_and_vdi_spatial_ir_replay(tmp_path: Path) -> None:
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    runner = import_contract_module("guiai.gem.runner")
    seasip = import_contract_module("guiai.gem.seasip_gem")
    model_mod = import_contract_module("guiai.gem.model")

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T4-07"))
    digests = []
    for idx in range(2):
        wb = wb_mod.create_workbench(spec)
        snap_before = wb.snapshot_state()
        scene = wb.render_vdi_scene()
        out_gem = tmp_path / f"replay_{idx}.gem"
        gem_bytes = export_workbench_gem(wb, out_gem)
        assert seasip.verify_seasip_gem_metafile(gem_bytes)["valid"] is True

        if isinstance(scene, model_mod.Scene):
            scene_obj = scene
        elif isinstance(scene, dict) and "objects" in scene:
            scene_obj = model_mod.Scene.from_dict(scene)
        else:
            pytest.fail(
                f"wb.render_vdi_scene() must return Scene or Spatial IR dict with 'objects', "
                f"got {type(scene).__name__}: {scene!r}"
            )
        vdi_rep = runner.verify_vdi(scene_obj)
        assert vdi_rep.passed is True

        snap_after = wb.snapshot_state()
        assert pick(snap_after, "eddms_revision", "revision") == pick(snap_before, "eddms_revision", "revision")
        digests.append(hashlib.sha256(gem_bytes).hexdigest())

    assert digests[0] == digests[1]


def test_t4_08_end_to_end_constitutional_offline_and_workspace_hygiene_audit(
    tmp_path: Path,
    isolated_home: Path,
    offline_guard: dict[str, int],
) -> None:
    hex_mod = import_contract_module("guiai.gem.zoe_hex_mesh")
    eddms = import_contract_module("guiai.gem.zoe_eddms")
    core = import_contract_module("guiai.gem.zoe_gem_aes_vdi_core")
    bridge_mod = import_contract_module("guiai.gem.zoe_ablation_bridge")
    wb_mod = import_contract_module("guiai.gem.zoe_gem_workbench")

    for mod in (hex_mod, eddms, core, bridge_mod, wb_mod):
        meta_fn = getattr(mod, "constitutional_metadata", None)
        meta = meta_fn() if callable(meta_fn) else getattr(mod, "SAFETY_INVARIANTS")
        assert_full_contract_metadata(meta, require_read_only=(mod is bridge_mod))

    spec = eddms.FunctionEngineeringSpecification(**sample_fes_kwargs("FES-T4-08"))
    wb = wb_mod.create_workbench(spec)
    call_with_supported_kwargs(wb.tick_collaboration, ticks=2)
    ab_rep = call_with_supported_kwargs(wb.run_ablation_inspection, raw_bytes=minimal_elf64_bytes(), target_name="audit.elf")
    snap = wb.snapshot_state()

    for item in (ab_rep, snap):
        assert_m1_m4_constitutional_record(item, require_advisory=True)
    assert pick(ab_rep, "tokens_used", "cloud_tokens_used") == 0
    assert float(pick(ab_rep, "cloud_cost_usd")) == 0.0
    assert pick(ab_rep, "external_actions") == 0
    assert offline_guard["non_loopback_blocked"] == 0
    assert offline_guard["forbidden_commands_blocked"] == 0
    assert isolated_home.exists()

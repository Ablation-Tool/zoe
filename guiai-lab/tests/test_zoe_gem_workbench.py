"""Unit tests for Milestone M4: Collaborative 9-Sister GEM Workbench & CLI Wiring."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from guiai.gem import geometry, runner, seasip_gem, unified_cli
from guiai.gem.atlas import ATLAS_MODULES
from guiai.gem.code_elegance_analyzer import analyze_python_source
from guiai.gem.lume_cli import LumeCli
from guiai.gem.operating_environment import COMPONENT_MODULES
from guiai.gem.unified import COMPONENTS
from guiai.gem.zoe_eddms import FunctionEngineeringSpecification
from guiai.gem.zoe_gem_workbench import (
    WORKBENCH_CONTRACT,
    constitutional_metadata,
    create_workbench,
)
from guiai.gem.zoe_hex_mesh import ATTRIBUTION_TEXT
from guiai.gem.zoe_sisters import ZOE_SISTERS
from zoe_autonomy.chat import ZoeChat

REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_elf64() -> bytes:
    """Return minimal ELF64 header bytes for read-only workbench inspection."""
    return b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56


def test_workbench_creation_9_sisters_and_window_budget() -> None:
    wb = create_workbench()
    snap = wb.snapshot_state()
    assert snap["contract"] == WORKBENCH_CONTRACT
    assert 1 <= snap["window_count"] <= seasip_gem.MAX_AES_APP_WINDOWS
    assert len(snap["open_windows"]) == snap["window_count"]
    assert {s["name"] for s in snap["sisters"]} == {s.name for s in ZOE_SISTERS}
    assert "ablation" in snap
    meta = constitutional_metadata()
    assert meta["advisory_only"] is True
    assert meta["external_actions"] == 0
    assert meta["tokens_used"] == 0
    assert ATTRIBUTION_TEXT in meta["attribution"]


def test_focus_all_9_sisters_stays_within_7_windows() -> None:
    wb = create_workbench()
    for sister in ZOE_SISTERS:
        focused = wb.focus_sister(sister.name)
        assert focused.name == sister.name
        assert len(wb.window_mgr.summary()["allocated_handles"]) <= seasip_gem.MAX_AES_APP_WINDOWS
    snap = wb.snapshot_state()
    assert snap["window_count"] <= 7
    assert snap["active_sister"] == ZOE_SISTERS[-1].name


def test_tick_collaboration_and_validation() -> None:
    wb = create_workbench()
    before = wb.snapshot_state()
    res = wb.tick_collaboration(ticks=2)
    after = wb.snapshot_state()
    assert res["ticks_executed"] == 2
    assert after["mesh_tick"] == before["mesh_tick"] + 2
    assert after["eddms_revision"] == before["eddms_revision"] + 2
    assert after["record_sha256"] != before["record_sha256"]

    for bad_ticks in (0, -1, True):
        with pytest.raises(ValueError):
            wb.tick_collaboration(ticks=bad_ticks)


def test_workbench_ablation_and_missing_target_fail_closed(tmp_path: Path) -> None:
    wb = create_workbench()
    rev_before = wb.record.revision
    rep = wb.run_ablation_inspection(raw_bytes=_minimal_elf64(), target_name="wb_probe.elf")
    assert rep.advisory_only is True and rep.read_only is True
    assert wb.record.revision == rev_before + 1
    assert wb.snapshot_state()["ablation"]["target_sha256"] == rep.target_sha256

    with pytest.raises(FileNotFoundError):
        wb.run_ablation_inspection(target_path=tmp_path / "nonexistent.bin")


def test_vdi_svg_metafile_determinism_and_overwrite_guards(tmp_path: Path) -> None:
    spec = FunctionEngineeringSpecification(
        spec_id="FES-WB-DET-001",
        title="Deterministic Workbench",
        objective="Verify reproducible Spatial IR and .GEM export",
        owner="Zoe",
        constraints={"loopback_only": True},
        target_properties={"advisory_only": True},
        geometric_requirements={"canvas": [640, 400]},
    )
    wb1 = create_workbench(spec)
    wb2 = create_workbench(spec)
    rev_before = wb1.record.revision

    scene1 = wb1.render_vdi_scene()
    svg1 = wb1.render_svg()
    gem1 = wb1.export_gem_metafile(tmp_path / "out1.gem")
    gem2 = wb2.export_gem_metafile(tmp_path / "out2.gem")

    assert wb1.record.revision == rev_before
    geometry_mod: Any = geometry
    runner_mod: Any = runner
    assert geometry_mod.verify(scene1).passed is True
    assert runner_mod.verify_vdi(scene1).passed is True
    assert "<svg" in svg1
    assert seasip_gem.verify_seasip_gem_metafile(gem1)["valid"] is True
    assert hashlib.sha256(gem1).hexdigest() == hashlib.sha256(gem2).hexdigest()

    dir_path = tmp_path / "subdir"
    dir_path.mkdir()
    with pytest.raises(IsADirectoryError):
        wb1.export_gem_metafile(dir_path)

    existing = tmp_path / "locked.gem"
    existing.write_bytes(b"KEEP_ME")
    with pytest.raises(FileExistsError):
        wb1.export_gem_metafile(existing)
    assert existing.read_bytes() == b"KEEP_ME"


def test_sync_gem_lab_transactional_session(tmp_path: Path) -> None:
    target = tmp_path / "fw.bin"
    target.write_bytes(_minimal_elf64())
    session_dir = tmp_path / "gem_session"
    wb = create_workbench()
    wb.run_ablation_inspection(target_path=target)
    sync_res = wb.sync_gem_lab(session_dir, target=target)
    assert (session_dir / "events.jsonl").is_file()
    assert sync_res["emitted_id"].startswith("obs:workbench:")
    assert sync_res["state"]["revision"] >= 1


def test_lume_cli_and_unified_cli_wiring(tmp_path: Path) -> None:
    cli = LumeCli(ZoeChat(REPO_ROOT, tmp_path / "chat"), REPO_ROOT, color=False, brain_state=tmp_path / "brain")
    for cmd in ("/sister hex", "/sister eddbms", "/sister ablation", "/gem workbench"):
        handled, lines = cli.handle_slash(cmd, color=False)
        assert handled is True and lines

    before_sister = cli.active_sister
    handled, err_lines = cli.handle_slash("/sister unknown_cmd_xyz", color=False)
    assert handled is True and err_lines
    assert cli.active_sister == before_sister

    assert unified_cli.main(["list"]) == 0
    assert unified_cli.main(["gem", "status"]) == 0
    assert unified_cli.main(["workbench", "--json"]) == 0
    assert unified_cli.main(["sister", "hex", "--json"]) == 0
    assert unified_cli.main(["gem", "workbench"]) == 0
    assert len(COMPONENTS) == 17
    assert len(COMPONENT_MODULES) == 17
    assert len(ATLAS_MODULES) == 36


def test_svg_export_and_cli_security_overwrite_guards(tmp_path: Path) -> None:
    wb = create_workbench()

    fresh_svg = tmp_path / "fresh.svg"
    svg_out = wb.export_svg(fresh_svg)
    assert "<svg" in svg_out and fresh_svg.read_text(encoding="utf-8") == svg_out

    existing = tmp_path / "sentinel.svg"
    existing.write_text("KEEP_ME_SAFE", encoding="utf-8")
    with pytest.raises(FileExistsError):
        wb.export_svg(existing)
    assert existing.read_text(encoding="utf-8") == "KEEP_ME_SAFE"
    assert unified_cli.main(["workbench", "export", "--format", "svg", "--output", str(existing)]) == 2
    assert existing.read_text(encoding="utf-8") == "KEEP_ME_SAFE"

    wb.export_svg(existing, overwrite=True)
    assert "<svg" in existing.read_text(encoding="utf-8")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    trav_path = subdir / ".." / "trav.svg"
    with pytest.raises(ValueError):
        wb.export_svg(trav_path)
    assert unified_cli.main(["workbench", "export", "--format", "svg", "--output", str(trav_path)]) == 2
    assert not (tmp_path / "trav.svg").exists()

    sym_target = tmp_path / "sym_target.svg"
    sym_target.write_text("TARGET_SAFE", encoding="utf-8")
    live_sym = tmp_path / "live.svg"
    live_sym.symlink_to(sym_target)
    dangling_sym = tmp_path / "dangling.svg"
    dangling_sym.symlink_to(tmp_path / "missing_target.svg")
    sym_parent = tmp_path / "sym_dir"
    sym_parent.symlink_to(subdir)
    for bad_sym in (live_sym, dangling_sym, sym_parent / "child.svg"):
        with pytest.raises(ValueError):
            wb.export_svg(bad_sym)
        assert unified_cli.main(["workbench", "export", "--format", "svg", "--output", str(bad_sym)]) == 2
    assert sym_target.read_text(encoding="utf-8") == "TARGET_SAFE"

    with pytest.raises(IsADirectoryError):
        wb.export_svg(subdir)
    assert unified_cli.main(["workbench", "export", "--format", "svg", "--output", str(subdir)]) == 2


def test_m4_modules_elegance_grade_a_or_b() -> None:
    gem_dir = REPO_ROOT / "guiai-lab" / "guiai" / "gem"
    ucli_rep = analyze_python_source((gem_dir / "unified_cli.py").read_text(encoding="utf-8"), "unified_cli.py")
    assert ucli_rep["grade"] == "A"
    assert ucli_rep["max_cc"] <= 20
    for name in ("zoe_gem_workbench.py", "lume_cli.py"):
        rep = analyze_python_source((gem_dir / name).read_text(encoding="utf-8"), name)
        assert rep["grade"] in {"A", "B"}

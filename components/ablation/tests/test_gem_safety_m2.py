"""M2 F5/F10 safety tests for GemOperatingEnvironment and GemWindowManager."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_REPO_ROOT / "guiai-lab"), str(_REPO_ROOT / "components" / "Zoe-Autonomy" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from guiai.gem.operating_environment import GemOperatingEnvironment  # noqa: E402
from zoe_autonomy.shared_reasoning.gem_aes_vdi import GemWindowManager  # noqa: E402


def test_operating_environment_rejects_broken_symlink_and_preserves_no_overwrite(tmp_path):
    env = GemOperatingEnvironment(_REPO_ROOT)

    target_gem = tmp_path / "target.gem"
    broken_gem = tmp_path / "broken.gem"
    broken_gem.symlink_to(target_gem)

    with pytest.raises(ValueError, match="symbolic link"):
        env.export("ablation", broken_gem)
    assert not target_gem.exists()

    target_json = tmp_path / "target.json"
    broken_json = tmp_path / "broken.json"
    broken_json.symlink_to(target_json)

    with pytest.raises(ValueError, match="symbolic link"):
        env.snapshot(broken_json)
    assert not target_json.exists()

    real_gem = tmp_path / "real.gem"
    res = env.export("ablation", real_gem)
    assert res["no_overwrite"] is True
    assert real_gem.is_file()
    with pytest.raises(FileExistsError):
        env.export("ablation", real_gem)


def test_gem_window_manager_bounds_are_atomic_on_wind_open_and_wind_set():
    wm = GemWindowManager()
    handle = wm.wind_create(0x000B, 10, 20, 200, 120, title="SafeWin")
    assert handle > 0

    with pytest.raises(ValueError, match="int16"):
        wm.wind_open(handle, rect=(0, 0, 50000, 100))

    win = wm.desk.windows[handle]
    assert win.opened is False
    assert (win.x, win.y, win.w, win.h) == (10, 20, 200, 120)

    wm.wind_open(handle)
    assert win.opened is True

    with pytest.raises(ValueError, match="int16"):
        wm.wind_set(handle, "rect", (-40000, 20, 200, 120))

    assert (win.x, win.y, win.w, win.h) == (10, 20, 200, 120)


def test_operating_environment_rejects_ancestor_symlink_traversal(tmp_path, monkeypatch):
    env = GemOperatingEnvironment(_REPO_ROOT)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    sym_parent = tmp_path / "sym_parent"
    sym_parent.symlink_to(outside_dir)

    with pytest.raises(ValueError, match="symbolic link"):
        env.export("ablation", sym_parent / "leaf.gem")
    with pytest.raises(ValueError, match="symbolic link"):
        env.export("ablation", sym_parent / "nested" / "leaf.json")
    with pytest.raises(ValueError, match="symbolic link"):
        env.snapshot(sym_parent / "snap.json")
    assert list(outside_dir.iterdir()) == []

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="symbolic link"):
        env.export("ablation", Path("sym_parent") / "rel.json")
    with pytest.raises(ValueError, match="symbolic link"):
        env.export("ablation", Path("sym_parent") / ".." / "escaped.json")
    with pytest.raises(ValueError, match="symbolic link"):
        env.snapshot(Path("sym_parent") / ".." / "escaped_snap.json")
    assert list(outside_dir.iterdir()) == []
    assert not (tmp_path / "escaped.json").exists()
    assert not (tmp_path / "escaped_snap.json").exists()


def test_operating_environment_snapshot_expands_tilde_consistently(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_cwd = tmp_path / "cwd"
    outside_trap = tmp_path / "outside_trap"
    fake_home.mkdir()
    fake_cwd.mkdir()
    outside_trap.mkdir()

    (fake_cwd / "~").symlink_to(outside_trap)
    sym_in_home = fake_home / "sym_in_home"
    sym_in_home.symlink_to(outside_trap)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.chdir(fake_cwd)
    env = GemOperatingEnvironment(_REPO_ROOT)

    res = env.snapshot("~/snap_tilde.json")
    expected_path = (fake_home / "snap_tilde.json").resolve()
    assert Path(res["output"]) == expected_path
    assert expected_path.is_file()
    assert list(outside_trap.iterdir()) == []
    assert not (fake_cwd / "~" / "snap_tilde.json").exists()

    with pytest.raises(FileExistsError):
        env.snapshot("~/snap_tilde.json")

    with pytest.raises(ValueError, match="symbolic link"):
        env.snapshot("~/sym_in_home/blocked.json")
    assert list(outside_trap.iterdir()) == []


def test_operating_environment_rejects_nonexistent_parent_dotdot_symlink_bypass(tmp_path, monkeypatch):
    outside_dir = tmp_path / "outside"
    work_dir = tmp_path / "work"
    fake_home = tmp_path / "home"
    outside_dir.mkdir()
    work_dir.mkdir()
    fake_home.mkdir()

    (work_dir / "dir_link").symlink_to(outside_dir)
    (fake_home / "sym_dir").symlink_to(outside_dir)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.chdir(work_dir)
    env = GemOperatingEnvironment(_REPO_ROOT)

    symlink_bypass_paths = [
        str(work_dir / "no_such_dir" / ".." / "dir_link" / "bypass.json"),
        "no_such_dir/../dir_link/bypass_rel.json",
        "~/no_such_dir/../sym_dir/bypass_tilde.json",
    ]
    for target in symlink_bypass_paths:
        with pytest.raises(ValueError, match="symbolic link"):
            env.export("zoe", target)
        with pytest.raises(ValueError, match="symbolic link"):
            env.snapshot(target)

    with pytest.raises(ValueError, match="traversal"):
        env.export("zoe", "no_such_dir/../plain_dotdot.json")
    with pytest.raises(ValueError, match="traversal"):
        env.snapshot("no_such_dir/../plain_dotdot_snap.json")

    assert list(outside_dir.iterdir()) == []
    assert not (work_dir / "no_such_dir").exists()
    assert not (work_dir / "plain_dotdot.json").exists()
    assert not (work_dir / "plain_dotdot_snap.json").exists()

    normal_export = work_dir / "normal_export.json"
    res_export = env.export("zoe", normal_export)
    assert Path(res_export["output"]) == normal_export.resolve()
    assert normal_export.is_file()

    tilde_export = env.export("zoe", "~/export_tilde.json")
    assert Path(tilde_export["output"]) == (fake_home / "export_tilde.json").resolve()
    assert (fake_home / "export_tilde.json").is_file()

    normal_snap = work_dir / "normal_snap.json"
    res_snap = env.snapshot(normal_snap)
    assert Path(res_snap["output"]) == normal_snap.resolve()
    assert normal_snap.is_file()

    tilde_snap = env.snapshot("~/snap_tilde.json")
    assert Path(tilde_snap["output"]) == (fake_home / "snap_tilde.json").resolve()
    assert (fake_home / "snap_tilde.json").is_file()

    assert list(outside_dir.iterdir()) == []

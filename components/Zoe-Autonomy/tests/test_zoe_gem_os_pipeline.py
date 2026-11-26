"""M2 F6/F10 unit tests for Zoe-GEM OS KVM pipeline, static verifier, cleanup, and safety."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (
    str(_REPO_ROOT / "guiai-lab"),
    str(_REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from guiai.gem.code_elegance_analyzer import analyze_python_source  # noqa: E402
from guiai.gem.zoe_gem_os import builder, zoe_os_runtime, zoe_pixel_os  # noqa: E402
from guiai.gem.zoe_gem_os.zoe_uma import UMA_SHM_SIZE, UmaBridge, find_guest_ivshmem_bar2  # noqa: E402


def _assert_constitutional(doc: dict) -> None:
    assert doc["tokens_used"] == 0
    assert doc["external_actions"] == 0
    assert doc["clinical_action_authorized"] is False
    assert doc["flight_control_authorized"] is False
    assert doc["cure_claim"] is False
    assert doc["sentience_claimed"] is False
    assert doc["l5_agi_qualified"] is False
    assert doc["auto_flash_allowed"] is False
    assert doc["zoe_clone_claimed"] is False


def test_zoe_py_closure_includes_sisters_and_imports_cleanly_in_guest_rootfs(tmp_path):
    assert "zoe_sisters.py" in builder._ZOE_PY_CLOSURE
    stage = tmp_path / "guest_rootfs"
    builder._copy_zoe_closure(stage, _REPO_ROOT)
    lib_zoe = stage / "usr" / "lib" / "zoe"
    assert (lib_zoe / "guiai" / "gem" / "zoe_sisters.py").is_file()

    code = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from guiai.gem import zoe_sisters\n"
        "from guiai.gem.zoe_gem_os import zoe_uma\n"
        "import zoe_os_runtime\n"
        "assert len(zoe_sisters.ZOE_SISTERS) == 9\n"
        "assert zoe_sisters.__file__.startswith(sys.argv[1])\n"
        "assert zoe_uma.UMA_SHM_SIZE == 4 * 1024 * 1024\n"
        "print(json.dumps({'ok': True, 'count': len(zoe_sisters.ZOE_SISTERS)}))\n"
    )
    proc = subprocess.run([sys.executable, "-I", "-c", code, str(lib_zoe)], capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout)["count"] == 9


def test_verify_zoe_gem_os_static_in_tmp_path_without_kvm_or_home_mutation(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    res = builder.verify_zoe_gem_os_static(_REPO_ROOT, tmp_path / "static_work")
    assert res["ok"] is True
    assert res["mode"] == "static_dry_run"
    assert res["kvm_invoked"] is False
    assert res["closure"]["sisters_included"] is True
    assert res["closure"]["sisters_count"] == 9
    assert res["uma_contract"]["audit_chain_ok"] is True
    assert res["safety_and_boot_chain"]["gates_count"] == 7
    assert res["safety_and_boot_chain"]["tamper_rejected"] is True
    assert res["safety_and_boot_chain"]["pixel_ok"] is True
    _assert_constitutional(res)

    dry = builder.verify_zoe_gem_os_qemu(tmp_path / "dummy.iso", tmp_path / "dry_work", dry_run=True, zoe_root=_REPO_ROOT)
    assert dry["ok"] is True
    assert dry["kvm_invoked"] is False
    assert not (fake_home / ".zoe" / "os-build").exists()
    assert not (fake_home / ".zoe" / "uma-bridge").exists()


def test_zoe_os_runtime_sister_awareness_and_import_fallback(tmp_path, capsys):
    proc_root, sys_root, dev_root = builder._write_synthetic_sys_proc_dev(tmp_path / "synth", UMA_SHM_SIZE)
    uma_dir = tmp_path / "uma"
    UmaBridge(uma_dir, shm_path=tmp_path / "uma.shm").ensure_initialized()
    state_dir = tmp_path / "state"
    run_json = tmp_path / "run.json"

    rep = zoe_os_runtime.run_boot_sync(
        state_dir, run_json, proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir
    )
    assert rep["sisters_available"] is True
    assert rep["sisters_count"] == 9
    assert rep["council_leads"] == ["Mono", "Zoe", "Eliza"]
    _assert_constitutional(rep)

    assert zoe_os_runtime._dispatch_shell_cmd("sisters", state_dir, rep) is True
    out = capsys.readouterr().out
    assert "Mono, Zoe, Eliza" in out

    with patch.dict(sys.modules, {"guiai.gem.zoe_sisters": None}):
        fb = zoe_os_runtime._resolve_sister_metadata("KVM_UMA_SPLIT")
    assert fb["sisters_available"] is False
    assert fb["sisters_count"] == 0
    assert fb["hw_lead_sister"] == "Zoe"
    assert fb["council_leads"] == ["Mono", "Zoe", "Eliza"]


def test_zoe_os_runtime_boot_chain_sha256_and_tamper_fallback(tmp_path):
    proc_root, sys_root, dev_root = builder._write_synthetic_sys_proc_dev(tmp_path / "synth", UMA_SHM_SIZE)
    uma_dir = tmp_path / "uma"
    UmaBridge(uma_dir, shm_path=tmp_path / "uma.shm").ensure_initialized()
    state_dir = tmp_path / "state"

    b1 = zoe_os_runtime.run_boot_sync(
        state_dir, tmp_path / "r1.json", proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir
    )
    b2 = zoe_os_runtime.run_boot_sync(
        state_dir, tmp_path / "r2.json", proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir
    )
    assert b1["boot_count"] == 1 and b1["chain_intact"] is True and b1["restored_from_prior"] is False
    assert b2["boot_count"] == 2 and b2["chain_intact"] is True and b2["restored_from_prior"] is True
    assert b2["prev_sha"] == b1["chain_sha"]

    chain_file = state_dir / "boot_chain.jsonl"
    lines = chain_file.read_text(encoding="utf-8").splitlines()
    rec0 = json.loads(lines[0])
    rec0["ram_mb"] = 123456
    lines[0] = json.dumps(rec0, sort_keys=True)
    chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fb_report = zoe_os_runtime._build_fallback_report(state_dir, "/dev/vda [ZOE-STATE]")
    assert fb_report["chain_intact"] is False
    assert fb_report["restored_from_prior"] is False
    assert fb_report["self_restored"] is False
    _assert_constitutional(fb_report)


def test_uma_ivshmem_bar2_and_9p_contract_in_tmp_path(tmp_path):
    pci_dev = tmp_path / "sys" / "bus" / "pci" / "devices" / "0000:00:04.0"
    pci_dev.mkdir(parents=True)
    (pci_dev / "vendor").write_text("0x1af4\n", encoding="utf-8")
    (pci_dev / "device").write_text("0x1110\n", encoding="utf-8")
    (pci_dev / "resource2").write_bytes(b"\x00" * UMA_SHM_SIZE)
    bar2 = find_guest_ivshmem_bar2(tmp_path / "sys" / "bus" / "pci" / "devices")
    assert bar2 == pci_dev / "resource2"

    uma = UmaBridge(tmp_path / "uma_bridge", shm_path=tmp_path / "bar.shm")
    assert uma.ensure_initialized()["gate"] == "PRIVATE"
    src = tmp_path / "artifact.gem"
    src.write_text("GEM", encoding="utf-8")

    with pytest.raises(PermissionError):
        uma.transfer_file("zoe", src)
    assert uma.set_consent("nick", True, reason="request")["gate"] == "REQUESTED"
    with pytest.raises(PermissionError):
        uma.transfer_file("zoe", src)

    assert uma.set_consent("zoe", True, reason="mutual")["gate"] == "SHARED"
    assert uma.transfer_file("zoe", src)["ok"] is True
    assert (uma.zoe_to_nick / "artifact.gem").is_file()

    for slot in range(4):
        assert uma.write_shm_heartbeat(f"node-{slot}", {"gate": "SHARED", "slot": slot}, slot=slot) is True
    assert set(uma.read_all_zo3_slots().keys()) == {0, 1, 2, 3}


def test_builder_launch_zo3_cluster_terminates_prior_nodes_on_failure(tmp_path):
    iso = tmp_path / "zoe.iso"
    iso.write_bytes(b"ISO")
    ovmf = tmp_path / "OVMF.fd"
    ovmf.write_bytes(b"OVMF")
    state_dir = tmp_path / "zo3_state"
    spawned: list[subprocess.Popen] = []

    def fake_launch(cmd, wait_sec=0.5):
        if len(spawned) == 0:
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
            spawned.append(proc)
            return proc
        raise RuntimeError("simulated node 2 launch failure")

    try:
        with patch.object(builder, "_verify_kvm_access", return_value=Path("/dev/kvm")), \
             patch.object(builder, "_resolve_ovmf_firmware", return_value=ovmf), \
             patch.object(builder, "_ensure_node_state_disk", side_effect=lambda p, nid, th: p), \
             patch.object(builder, "_check_disk_unlocked", return_value=None), \
             patch.object(builder, "_launch_qemu_checked", side_effect=fake_launch):
            with pytest.raises(RuntimeError, match="node 2"):
                builder.launch_zo3_cluster(iso, state_dir, count=2, uma_dir=tmp_path / "u", uma_shm=tmp_path / "s.shm")
        assert len(spawned) == 1
        assert spawned[0].poll() is not None
    finally:
        for p in spawned:
            builder._cleanup_proc(p)


def test_builder_reap_boot_proc_and_launch_checked_on_exception(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        with patch.object(builder, "_collect_boot_lines", side_effect=RuntimeError("boom")), \
             patch.object(builder, "_build_verify_qemu_cmd", return_value=["dummy"]), \
             patch("subprocess.Popen", return_value=proc):
            with pytest.raises(RuntimeError, match="boom"):
                builder._run_single_qemu_boot(tmp_path / "i.iso", tmp_path / "d.img", tmp_path / "o.fd", tmp_path, 1)
        assert proc.poll() is not None
        assert proc.stdout is not None and proc.stdout.closed is True
    finally:
        builder._cleanup_proc(proc)

    # 1) Persistent KeyboardInterrupt on time.sleep with a SIGTERM-ignoring child:
    #    must escalate via SIGKILL + blocking wait() and close proc2.stderr.
    sig_ign_code = "import signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); sys.stderr.write('ready\\n'); sys.stderr.flush(); time.sleep(30)"
    proc2 = subprocess.Popen([sys.executable, "-c", sig_ign_code], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        assert proc2.stderr is not None
        assert proc2.stderr.readline().strip() == "ready"
        with patch("subprocess.Popen", return_value=proc2), \
             patch("time.sleep", side_effect=KeyboardInterrupt("abort")):
            with pytest.raises(KeyboardInterrupt):
                builder._launch_qemu_checked(["dummy"], wait_sec=0.5)
        assert proc2.poll() is not None
        assert proc2.stderr.closed is True
    finally:
        builder._cleanup_proc(proc2)

    # 2) One-shot KeyboardInterrupt on time.sleep: clean SIGTERM + wait(timeout=2.0) + closed stderr.
    proc3 = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; sys.stderr.write('ready\\n'); sys.stderr.flush(); time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    real_sleep = time.sleep
    calls = {"n": 0}

    def one_shot_interrupt(secs: float) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt("abort-once")
        real_sleep(secs)

    try:
        assert proc3.stderr is not None
        assert proc3.stderr.readline().strip() == "ready"
        with patch("subprocess.Popen", return_value=proc3), \
             patch("time.sleep", side_effect=one_shot_interrupt):
            with pytest.raises(KeyboardInterrupt):
                builder._launch_qemu_checked(["dummy"], wait_sec=0.5)
        assert proc3.poll() is not None
        assert proc3.stderr.closed is True
    finally:
        builder._cleanup_proc(proc3)

    # 3) _reap_boot_proc under persistent KeyboardInterrupt on time.sleep with SIGTERM-ignoring child.
    reap_code = "import signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); sys.stdout.write('ready\\n'); sys.stdout.flush(); time.sleep(30)"
    proc4 = subprocess.Popen([sys.executable, "-c", reap_code], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert proc4.stdout is not None
        assert proc4.stdout.readline().strip() == "ready"
        with patch("time.sleep", side_effect=KeyboardInterrupt("abort-reap")):
            builder._reap_boot_proc(proc4, saw_poweroff=False)
        assert proc4.poll() is not None
    finally:
        builder._cleanup_proc(proc4)


def test_zoe_pixel_os_safety_gates_and_static_bundle(tmp_path):
    res = zoe_pixel_os.verify_pixel_os_static(tmp_path / "pixel", device="pixel7")
    assert res["ok"] is True
    assert res["device"] == "panther"
    assert res["devices_count"] == 9
    assert res["deterministic"] is True
    assert res["overlay_ok"] is True
    assert res["init_ok"] is True
    _assert_constitutional(res)


def test_zoe_gem_os_elegance_grade_and_hygiene(monkeypatch):
    monkeypatch.syspath_prepend(str(_REPO_ROOT / "components" / "Zoe-Autonomy" / "tests" / "e2e_zoe_gem_os"))
    from harness import run_hygiene_scan  # noqa: E402

    os_dir = _REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "zoe_gem_os"
    for fname in ("builder.py", "zoe_os_runtime.py", "zoe_pixel_os.py"):
        fpath = os_dir / fname
        res = analyze_python_source(fpath.read_text(encoding="utf-8"), label=fname)
        assert res["grade"] in {"A", "B"}, (fname, res)
        assert res["mi_score"] >= 40.0, (fname, res)

    hyg = run_hygiene_scan()
    assert hyg["clean"] is True, hyg

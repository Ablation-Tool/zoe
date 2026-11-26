"""Tier 2 E2E Tests: Boundary Value Analysis, error paths, elegance & hygiene (>= 35 tests)."""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from harness import (  # noqa: E402
    REPO_ROOT,
    ZOE_GEM_OS_DIR,
    assert_constitutional_honesty,
    build_fb_binary,
    create_sandbox,
    find_cached_iso,
    find_ovmf_firmware,
    has_gcc,
    has_qemu_kvm,
    is_strict_mode,
    isolate_uma_shm,
    isolated_env,
    probe_m1_hw_observation,
    probe_m1_uma_flock,
    probe_m2_geometry_flags,
    probe_m2_werror_compile,
    probe_m3_tcp_qmp_verifier,
    require_capability,
    run_elegance_check,
    run_hygiene_scan,
    run_verifier_with_long_tmpdir_shim,
)
from ppm_inspector import (  # noqa: E402
    assert_micro_hud_geometry,
    assert_portrait_geometry,
    diff_ratio,
    is_amber_crt_dominant,
    is_non_blank,
    read_ppm,
    region_stats,
    sample_pixel,
)
from qmp_client import QmpClient, alloc_free_port, terminate_qemu_proc, wait_until  # noqa: E402

_CANONICAL_HW_PROFILES = frozenset({
    "KVM_UMA_SPLIT",
    "LAPTOP_BARE_METAL",
    "BEOWULF_COMPUTE_NODE",
    "HEADLESS_DAQ_NODE",
    "EDGE_SBC_PI",
    "PORTRAIT_PHONE_TOUCH",
    "MICRO_HUD_HEADLAMP",
    "SAR_COMPANION_EDGE",
    "HEADLESS_SAFE_FALLBACK",
})


def _make_lume_cli(brain_state: Path):
    """Instantiate LumeCli against an isolated brain state directory."""
    from guiai.gem.lume_cli import LumeCli
    from zoe_autonomy.chat import ZoeChat

    return LumeCli(ZoeChat(REPO_ROOT), REPO_ROOT, color=False, brain_state=brain_state)


def _flock_worker(uma_dir: str, shm_path: str, actor: str, idx: int) -> None:
    """Multiprocessing worker performing concurrent UmaBridge consent updates."""
    from guiai.gem.zoe_gem_os import UmaBridge

    bridge = UmaBridge(uma_dir, shm_path=shm_path)
    bridge.set_consent(actor, idx % 2 == 0, reason=f"stress_{actor}_{idx}")
    _ = bridge.read_state()


class Tier2F1CliBoundaryTests(unittest.TestCase):
    """F1 Boundaries: invalid CLI args, missing files, and collision guards."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f1-")
        self.sb = create_sandbox(self._td.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.sb.home_dir)

    def tearDown(self) -> None:
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self._td.cleanup()

    def test_f1_bva_unknown_os_subcommand(self) -> None:
        cli = _make_lume_cli(self.sb.state_dir)
        handled, out = cli.handle_slash("/os bogus_subcmd", color=False)
        self.assertTrue(handled)
        self.assertIn("Usage: /os", "\n".join(out or []))

    def test_f1_bva_unknown_uma_subcommand(self) -> None:
        cli = _make_lume_cli(self.sb.state_dir)
        with isolate_uma_shm(self.sb):
            handled, out = cli.handle_slash("/uma bogus_subcmd", color=False)
        self.assertTrue(handled)
        self.assertIn("Usage: /uma", "\n".join(out or []))

    def test_f1_bva_uma_send_empty_and_missing_file(self) -> None:
        cli = _make_lume_cli(self.sb.state_dir)
        with isolate_uma_shm(self.sb):
            _, empty_out = cli.handle_slash("/uma send", color=False)
            self.assertIn("Usage: /uma send", "\n".join(empty_out or []))
            _, miss_out = cli.handle_slash("/uma send /nonexistent_e2e_file.txt", color=False)
        self.assertIn("PRIVATE", "\n".join(miss_out or []))

    def test_f1_bva_os_launch_missing_iso_error(self) -> None:
        cli = _make_lume_cli(self.sb.state_dir)
        _, out = cli.handle_slash("/os launch", color=False)
        self.assertIn("ISO not built", "\n".join(out or []))

    def test_f1_bva_zoe_os_output_collision_exits_2(self) -> None:
        existing = self.sb.out_dir / "existing.svg"
        existing.write_text("<svg/>", encoding="utf-8")
        env = isolated_env(self.sb.home_dir)
        proc = subprocess.run(
            [sys.executable, "-m", "guiai.gem.unified_cli", "os", "--output", str(existing), "--format", "svg"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(existing.read_text(encoding="utf-8"), "<svg/>")


class Tier2F2BootBoundaryTests(unittest.TestCase):
    """F2 Boundaries: tampered SHA chain, missing dirs, empty drawer, clamped node ID."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f2-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f2_bva_tampered_boot_chain_sets_chain_intact_false(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        chain_p = self.sb.state_dir / "boot_chain.jsonl"
        rec = json.loads(chain_p.read_text(encoding="utf-8").splitlines()[0])
        rec["sha256"] = "0" * 64
        chain_p.write_text(json.dumps(rec) + "\n", encoding="utf-8")
        r2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertFalse(r2["chain_intact"])
        self.assertFalse(r2["restored_from_prior"])

    def test_f2_bva_missing_nested_state_dir_initializes_boot1(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        deep = self.sb.root / "nested" / "a" / "b" / "state"
        rep = run_boot_sync(deep, self.sb.boot_json)
        self.assertEqual(rep["boot_count"], 1)
        self.assertTrue(rep["chain_intact"])

    def test_f2_bva_empty_drawer_array_recovers_safely(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        (self.sb.state_dir / "nick_drawer.json").write_text("[]", encoding="utf-8")
        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(rep["drawer_count"], 1)

    def test_f2_bva_out_of_range_node_id_clamped_to_1(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        for bad_id in ("0", "99", "invalid"):
            old = os.environ.get("ZOE_NODE_ID")
            os.environ["ZOE_NODE_ID"] = bad_id
            try:
                rep = run_boot_sync(self.sb.state_dir / f"n_{bad_id}", self.sb.boot_json)
                self.assertEqual(rep["node_id"], 1)
            finally:
                if old is None:
                    os.environ.pop("ZOE_NODE_ID", None)
                else:
                    os.environ["ZOE_NODE_ID"] = old

    def test_f2_bva_constitutional_flags_immutable_under_edge_env(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        os.environ["ZOE_THEME"] = "amber"
        os.environ["ZOE_NODE_ID"] = "3"
        try:
            rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
            assert_constitutional_honesty(rep)
        finally:
            os.environ.pop("ZOE_THEME", None)
            os.environ.pop("ZOE_NODE_ID", None)

    def test_f2_bva_fallback_report_catches_tampered_line0(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import _build_fallback_report, run_boot_sync

        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        chain_p = self.sb.state_dir / "boot_chain.jsonl"
        rows = chain_p.read_text(encoding="utf-8").splitlines()
        r0 = json.loads(rows[0])
        r0["cpu"] = "TAMPERED"
        rows[0] = json.dumps(r0)
        chain_p.write_text("\n".join(rows) + "\n", encoding="utf-8")
        self.assertFalse(_build_fallback_report(self.sb.state_dir, "/dev/vda")["chain_intact"])


class Tier2F3HwDiagBoundaryTests(unittest.TestCase):
    """F3 Boundaries: Hardware Safety Observation Diagnostic edge cases (M1-gated)."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f3-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f3_bva_missing_uma_dir_degrades_uma_gate(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        os.environ["ZOE_UMA_DIR"] = str(self.sb.root / "nonexistent_uma")
        try:
            rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
            obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
            self.assertFalse(rep["uma_9p_mounted"])
            self.assertIn(obs["gates"]["hardware_uma"]["status"], ("DEGRADED", "UNSUPPORTED"))
        finally:
            os.environ.pop("ZOE_UMA_DIR", None)

    def test_f3_bva_profile_in_canonical_taxonomy(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertIn(rep["hw_profile"], _CANONICAL_HW_PROFILES)

    def test_f3_bva_summary_ascii_and_bounded_64_chars(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        summary = str(rep["hw_summary"])
        self.assertTrue(summary)
        self.assertLessEqual(len(summary), 64)
        self.assertTrue(summary.isascii())

    def test_f3_bva_zo3_budget_positive_and_safety_status_valid(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertGreaterEqual(int(rep["hw_zo3_budget"]), 1)
        self.assertIn(rep["hw_safety_overall"], ("PASS", "DEGRADED", "UNSUPPORTED"))

    def test_f3_bva_advisory_flags_locked_false(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
        assert_constitutional_honesty(rep, require_flight=True)
        assert_constitutional_honesty(obs, require_flight=True)


class Tier2F4UmaBoundaryTests(unittest.TestCase):
    """F4 Boundaries: gate blocking, invalid actors, SHM clamping, and flock stress."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f4-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f4_bva_private_and_requested_block_transfer(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        sample = self.sb.root / "secret.txt"
        sample.write_text("guarded", encoding="utf-8")
        with self.assertRaises(PermissionError):
            uma.transfer_file("nick", sample)
        uma.set_consent("nick", True)
        with self.assertRaises(PermissionError):
            uma.transfer_file("nick", sample)
        events = [json.loads(ln)["event"] for ln in uma.audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(events.count("crossing_blocked"), 2)

    def test_f4_bva_invalid_actor_raises_value_error(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        with self.assertRaises(ValueError):
            uma.set_consent("mallory", True)
        with self.assertRaises(ValueError):
            uma.transfer_file("mallory", self.sb.root / "x.txt")

    def test_f4_bva_shm_slot_clamp_and_missing_magic(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        self.assertIsNone(uma.read_shm_heartbeat(slot=3))
        self.assertTrue(uma.write_shm_heartbeat("clamp-low", {"ok": True}, slot=-5))
        self.assertTrue(uma.write_shm_heartbeat("clamp-high", {"ok": True}, slot=99))
        self.assertEqual(uma.read_shm_heartbeat(slot=0)["side"], "clamp-low")
        self.assertEqual(uma.read_shm_heartbeat(slot=7)["side"], "clamp-high")

    def test_f4_bva_shm_oversized_payload_no_slot_bleed(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.write_shm_heartbeat("slot1-ok", {"keep": True}, slot=1)
        uma.write_shm_heartbeat("big", {"blob": "X" * 5000}, slot=0)
        slot1 = uma.read_shm_heartbeat(slot=1)
        self.assertIsNotNone(slot1)
        self.assertTrue(slot1["keep"])

    def test_f4_bva_concurrent_flock_multiprocessing_stress(self) -> None:
        require_capability(self, "M1_UMA_FLOCK", probe_m1_uma_flock)
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        ctx = multiprocessing.get_context("spawn")
        procs = [
            ctx.Process(target=_flock_worker, args=(str(self.sb.uma_dir), str(self.sb.uma_shm), "nick" if i % 2 == 0 else "zoe", i))
            for i in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=15)
            self.assertEqual(p.exitcode, 0)
        prev = "genesis"
        for ln in uma.audit_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(ln)
            self.assertEqual(rec["prev_sha"], prev)
            body = {k: v for k, v in rec.items() if k != "sha256"}
            self.assertEqual(rec["sha256"], hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest())
            prev = rec["sha256"]

    def test_f4_bva_corrupt_audit_and_aba_slot_integrity(self) -> None:
        import mmap
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.set_consent("zoe", False, reason="seed_audit")
        uma.audit_path.write_bytes(uma.audit_path.read_bytes() + b'{"ts":1,"event":"torn\xff\xfe')
        st = uma.set_consent("nick", True, reason="post_torn")
        self.assertEqual(st["gate"], "REQUESTED")
        self.assertTrue(uma.write_shm_heartbeat("n0", {"gate": "PRIVATE", "v": "A"}, slot=0))
        with uma.shm_path.open("r+b") as fh:
            mm = mmap.mmap(fh.fileno(), 4096)
            mm[16] = mm[16] ^ 0x01
            mm.close()
        self.assertIsNone(uma.read_shm_heartbeat(slot=0))


class Tier2F5FbDesktopBoundaryTests(unittest.TestCase):
    """F5 Boundaries: missing /dev/fb0 exit codes, invalid PPM path, and M2 guards."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f5-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f5_bva_missing_fb0_exits_2(self) -> None:
        if not has_gcc():
            self.skipTest("gcc not available")
        fb_bin = build_fb_binary(self.sb.out_dir)
        env = os.environ.copy()
        if Path("/dev/fb0").exists():
            env["ZOE_FB_DEV"] = str(self.sb.out_dir / "missing_fb0")
        else:
            env.pop("ZOE_FB_DEV", None)
        proc = subprocess.run([str(fb_bin)], capture_output=True, text=True, env=env, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unavailable", proc.stderr)

    def test_f5_bva_invalid_dump_ppm_path_exits_1(self) -> None:
        if not has_gcc():
            self.skipTest("gcc not available")
        fb_bin = build_fb_binary(self.sb.out_dir)
        proc = subprocess.run([str(fb_bin), "--dump-ppm", str(self.sb.out_dir / "no_dir" / "x.ppm")], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 1)

    def test_f5_bva_empty_drawer_json_compile_and_state_load(self) -> None:
        require_capability(self, "M2_WERROR_COMPILE", probe_m2_werror_compile)
        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=True)
        self.sb.boot_json.write_text('{"boot_count": 1, "drawer_count": 0, "drawer_latest": ""}', encoding="utf-8")
        ppm = self.sb.out_dir / "empty_drawer.ppm"
        proc = subprocess.run([str(fb_bin), "--state", str(self.sb.boot_json), "--dump-ppm", str(ppm)], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0)
        w, h, rgb = read_ppm(ppm)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f5_bva_escaped_drawer_state_and_svg_reload(self) -> None:
        require_capability(self, "M2_WERROR_COMPILE", probe_m2_werror_compile)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        b1 = self.sb.out_dir / "b1.json"
        b2 = self.sb.out_dir / "b2.json"
        run_boot_sync(self.sb.state_dir, b1)
        drawer_p = self.sb.state_dir / "nick_drawer.json"
        notes = json.loads(drawer_p.read_text(encoding="utf-8"))
        notes.append({"boot": 1, "author": "Nicholas", "text": 'Escaped "quote" \\ & <svg> note'})
        drawer_p.write_text(json.dumps(notes), encoding="utf-8")
        rep2 = run_boot_sync(self.sb.state_dir, b2)
        self.assertEqual(rep2["drawer_count"], 2)
        reloaded = json.loads(drawer_p.read_text(encoding="utf-8"))
        self.assertIsInstance(reloaded, list)
        self.assertTrue((self.sb.state_dir / "artline" / "zoe_os_emblem.svg").is_file())

        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=True)
        p1, p2 = self.sb.out_dir / "d1.ppm", self.sb.out_dir / "d2.ppm"
        subprocess.run([str(fb_bin), "--state", str(b1), "--dump-ppm", str(p1)], check=True, capture_output=True)
        subprocess.run([str(fb_bin), "--state", str(b2), "--dump-ppm", str(p2)], check=True, capture_output=True)
        w1, h1, rgb1 = read_ppm(p1)
        w2, h2, rgb2 = read_ppm(p2)
        self.assertEqual((w1, h1), (w2, h2))
        self.assertGreater(diff_ratio(rgb1, rgb2), 0.0)

    def test_f5_bva_vt_arrow_esc_and_drawer_modal_qmp(self) -> None:
        iso = find_cached_iso("virt")
        ovmf = find_ovmf_firmware()
        if not (has_qemu_kvm() and iso and ovmf):
            self.skipTest("Requires host /dev/kvm, OVMF, and cached zoe-gem-os.iso")
        iso_has_m2 = iso.stat().st_mtime >= (ZOE_GEM_OS_DIR / "zoe_gem_fb.c").stat().st_mtime or is_strict_mode()
        qmp_port = alloc_free_port()
        proc = _spawn_t2_qmp_vm(iso, self.sb.out_dir / "vt_state.img", ovmf, qmp_port)
        p_base = self.sb.out_dir / "vt_base.ppm"
        p_vt = self.sb.out_dir / "vt_keys.ppm"
        p_drawer = self.sb.out_dir / "vt_drawer.ppm"
        p_amb = self.sb.out_dir / "vt_amb.ppm"
        try:
            with QmpClient("127.0.0.1", qmp_port, timeout_sec=15.0) as qmp:
                wait_until(lambda: _t2_desktop_ready(qmp, p_base), timeout_sec=30.0, interval=0.5, desc="GEM desktop")
                _exercise_t2_vt_and_drawer(qmp, p_base, p_drawer, iso_has_m2)
                qmp.screendump(p_vt)
                w, h, rgb_vt = read_ppm(p_vt)
                self.assertTrue(is_non_blank(w, h, rgb_vt))
                qmp.sendkey("a")
                wait_until(lambda: _t2_amber_ready(qmp, p_base, p_amb), timeout_sec=8.0, interval=0.3, desc="Amber after VT keys")
                qmp.quit()
        finally:
            terminate_qemu_proc(proc)


class Tier2F6GeometryBoundaryTests(unittest.TestCase):
    """F6 Boundaries: micro-HUD, square h==w, rotated monitor, and invalid --size (M2-gated)."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f6-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f6_bva_extreme_320x240_micro_hud(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        ppm = self.sb.out_dir / "m320.ppm"
        subprocess.run([str(fb_bin), "--size", "320x240", "--dump-ppm", str(ppm)], check=True)
        w, h, rgb = read_ppm(ppm)
        assert_micro_hud_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_bva_boundary_400x300_micro_hud(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        ppm = self.sb.out_dir / "m400.ppm"
        subprocess.run([str(fb_bin), "--size", "400x300", "--dump-ppm", str(ppm)], check=True)
        w, h, rgb = read_ppm(ppm)
        assert_micro_hud_geometry(w, h, max_dim=400)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_bva_square_boundary_768x768(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        ppm = self.sb.out_dir / "sq.ppm"
        subprocess.run([str(fb_bin), "--size", "768x768", "--dump-ppm", str(ppm)], check=True)
        w, h, rgb = read_ppm(ppm)
        assert_portrait_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_bva_rotated_monitor_768x1024(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        ppm = self.sb.out_dir / "rot.ppm"
        subprocess.run([str(fb_bin), "--size", "768x1024", "--portrait", "--dump-ppm", str(ppm)], check=True)
        w, h, rgb = read_ppm(ppm)
        self.assertEqual((w, h), (768, 1024))
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_bva_invalid_size_never_crashes(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        for bad in ("invalid", "0x0", "-10x20"):
            ppm = self.sb.out_dir / f"bad_{bad}.ppm"
            proc = subprocess.run([str(fb_bin), "--size", bad, "--dump-ppm", str(ppm)], capture_output=True, text=True, check=False)
            self.assertIn(proc.returncode, (0, 1, 2))
            if proc.returncode == 0:
                w, h, rgb = read_ppm(ppm)
                self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_bva_micro_hud_320x200_and_240x178_no_footer_overlap(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=True)
        for sz in ("320x200", "240x178"):
            ppm = self.sb.out_dir / f"micro_{sz}.ppm"
            subprocess.run([str(fb_bin), "--size", sz, "--dump-ppm", str(ppm)], check=True)
            w, h, rgb = read_ppm(ppm)
            assert_micro_hud_geometry(w, h)
            # Footer top rule at y = h - 20 must be clean dark rule across swatch x-range (zero swatch overlap)
            foot_y = h - 20
            row_px = {sample_pixel(w, rgb, x, foot_y) for x in range(8, w - 8, 6)}
            self.assertEqual(len(row_px), 1, f"{sz} footer top border overlapped by swatch: {row_px}")


class Tier2F7InfraEleganceHygieneTests(unittest.TestCase):
    """F7 Boundaries plus global monorepo elegance and hygiene invariants."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t2-f7-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f7_bva_missing_iso_raises_file_not_found(self) -> None:
        from guiai.gem.zoe_gem_os import launch_zoe_gem_os_kvm

        with self.assertRaises(FileNotFoundError):
            launch_zoe_gem_os_kvm(self.sb.out_dir / "missing.iso", self.sb.out_dir / "s.img")

    def test_f7_bva_long_tmpdir_tcp_qmp_and_builder(self) -> None:
        require_capability(self, "M3_TCP_QMP_VERIFIER", probe_m3_tcp_qmp_verifier)
        calls = run_verifier_with_long_tmpdir_shim(self.sb.root)
        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(all(all("unix:" not in arg for arg in argv) for argv in calls))
        self.assertTrue(any(any("tcp:127.0.0.1:" in arg for arg in argv) for argv in calls))

    def test_f7_bva_wait_until_timeout_and_qmp_unconnected(self) -> None:
        with self.assertRaises(TimeoutError):
            wait_until(lambda: False, timeout_sec=0.1, interval=0.02, desc="never_true")
        client = QmpClient("127.0.0.1", alloc_free_port())
        with self.assertRaises(RuntimeError):
            client.execute("query-status")

    def test_f7_bva_ppm_inspector_rejects_malformed_inputs(self) -> None:
        bad_magic = self.sb.out_dir / "bad_magic.ppm"
        bad_magic.write_bytes(b"P3\n2 2\n255\n0 0 0")
        with self.assertRaises(ValueError):
            read_ppm(bad_magic)
        truncated = self.sb.out_dir / "trunc.ppm"
        truncated.write_bytes(b"P6\n10 10\n255\n\x00\x00")
        with self.assertRaises(ValueError):
            read_ppm(truncated)
        small_rgb = b"\x01\x02\x03" * 4
        with self.assertRaises(IndexError):
            sample_pixel(2, small_rgb, -1, 0)
        with self.assertRaises(IndexError):
            sample_pixel(2, small_rgb, 2, 0)

    def test_f7_bva_monorepo_elegance_and_e2e_ast_grades(self) -> None:
        res = run_elegance_check()
        self.assertTrue(res["monorepo_verified"], res["monorepo_summary"])
        summary = res["monorepo_summary"]
        self.assertEqual(summary["parse_errors"], 0)
        self.assertEqual(summary["grade_distribution"]["C"], 0)
        self.assertEqual(summary["grade_distribution"]["D"], 0)
        self.assertTrue(res["e2e_ok"], res["e2e_files"])
        self.assertTrue(res["gem_ok"], res["zoe_gem_os_files"])

    def test_f7_bva_zero_hygiene_leaks(self) -> None:
        scan = run_hygiene_scan()
        self.assertTrue(scan["clean"], scan["leaks"])


def _spawn_t2_qmp_vm(iso: Path, state_img: Path, ovmf: Path, qmp_port: int) -> subprocess.Popen[bytes]:
    """Create a sandboxed ext4 ZOE-STATE disk and start QEMU/KVM with TCP QMP."""
    with state_img.open("wb") as fh:
        fh.truncate(64 * 1024 * 1024)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(state_img)], check=True, capture_output=True)
    cmd = [
        "qemu-system-x86_64", "-enable-kvm", "-machine", "q35", "-cpu", "host",
        "-m", "768M", "-smp", "2", "-bios", str(ovmf),
        "-drive", f"file={iso},media=cdrom,readonly=on,if=ide", "-boot", "d",
        "-drive", f"file={state_img},format=raw,if=virtio",
        "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
        "-vga", "std", "-display", "none",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server,nowait", "-no-reboot",
    ]
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _t2_desktop_ready(qmp: QmpClient, ppm_path: Path) -> bool:
    """Capture screendump and return True once desktop covers >50% non-black pixels."""
    qmp.screendump(ppm_path)
    if not ppm_path.is_file() or ppm_path.stat().st_size < 1000:
        return False
    w, h, rgb = read_ppm(ppm_path)
    return w >= 640 and h >= 480 and float(region_stats(w, h, rgb, step=8)["non_black_ratio"]) > 0.50


def _t2_modal_differs(qmp: QmpClient, baseline_ppm: Path, probe_ppm: Path) -> bool:
    """Return True once screendump differs visibly from baseline after opening a modal."""
    qmp.screendump(probe_ppm)
    if not probe_ppm.is_file() or probe_ppm.stat().st_size != baseline_ppm.stat().st_size:
        return False
    _, _, rgb_now = read_ppm(probe_ppm)
    _, _, rgb_base = read_ppm(baseline_ppm)
    return diff_ratio(rgb_base, rgb_now) > 0.01


def _exercise_t2_vt_and_drawer(qmp: QmpClient, p_base: Path, p_drawer: Path, iso_has_m2: bool) -> None:
    """Exercise VT arrow/ESC sequence, Drawer modal open/close, and VT_ESC 50ms window."""
    if not iso_has_m2:
        qmp.sendkey("6")
        return
    for key in ("up", "down", "esc"):
        qmp.sendkey(key)
    time.sleep(0.25)
    qmp.sendkey("d")
    wait_until(lambda: _t2_modal_differs(qmp, p_base, p_drawer), timeout_sec=6.0, interval=0.25, desc="Drawer modal")
    qmp.sendkey("esc")
    wait_until(lambda: not _t2_modal_differs(qmp, p_base, p_drawer), timeout_sec=3.0, interval=0.1, desc="Drawer modal close")
    time.sleep(0.10)


def _t2_amber_ready(qmp: QmpClient, baseline_ppm: Path, probe_ppm: Path) -> bool:
    """Return True once screendump reflects 1985 Amber CRT shift."""
    qmp.screendump(probe_ppm)
    if not probe_ppm.is_file() or probe_ppm.stat().st_size != baseline_ppm.stat().st_size:
        return False
    w, h, rgb_now = read_ppm(probe_ppm)
    _, _, rgb_base = read_ppm(baseline_ppm)
    return is_amber_crt_dominant(w, h, rgb_now) and diff_ratio(rgb_base, rgb_now) > 0.15


if __name__ == "__main__":
    unittest.main()

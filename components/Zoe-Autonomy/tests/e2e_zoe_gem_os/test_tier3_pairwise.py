"""Tier 3 E2E Tests: Pairwise cross-feature combination coverage (>= 10 tests)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
    has_gcc,
    isolate_uma_shm,
    isolated_env,
    launch_with_qemu_shim,
    probe_m1_hw_observation,
    probe_m1_shell_flag,
    probe_m2_geometry_flags,
    probe_m3_launch_wayland_sig,
    require_capability,
)
from ppm_inspector import (  # noqa: E402
    assert_micro_hud_geometry,
    assert_portrait_geometry,
    diff_ratio,
    is_amber_crt_dominant,
    is_non_blank,
    read_ppm,
)


def _dump_ppm(fb_bin: Path, out_ppm: Path, args: list[str]) -> tuple[int, int, bytes]:
    """Run zoe_gem_fb --dump-ppm and return parsed (width, height, rgb)."""
    subprocess.run([str(fb_bin), *args, "--dump-ppm", str(out_ppm)], check=True, capture_output=True)
    return read_ppm(out_ppm)


class Tier3PairwiseTests(unittest.TestCase):
    """Pairwise cross-feature interaction tests across F1-F7."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t3-")
        self.sb = create_sandbox(self._td.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.sb.home_dir)

    def tearDown(self) -> None:
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self._td.cleanup()

    def test_p01_uma_mutual_consent_x_boot_sync(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.set_consent("nick", True, reason="pairwise_mutual")
        os.environ["ZOE_UMA_DIR"] = str(self.sb.uma_dir)
        try:
            rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        finally:
            os.environ.pop("ZOE_UMA_DIR", None)
        self.assertEqual(rep["uma_gate"], "SHARED")
        self.assertTrue(rep["uma_transfer_ok"])
        self.assertTrue((self.sb.uma_dir / "zoe_to_nick" / "zoe_os_emblem.gem").is_file())

    def test_p02_uma_private_x_boot_sync_blocks_crossing(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm).ensure_initialized()
        os.environ["ZOE_UMA_DIR"] = str(self.sb.uma_dir)
        try:
            rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        finally:
            os.environ.pop("ZOE_UMA_DIR", None)
        self.assertEqual(rep["uma_gate"], "PRIVATE")
        self.assertFalse(rep["uma_transfer_ok"])
        self.assertEqual(list((self.sb.uma_dir / "zoe_to_nick").glob("*")), [])

    def test_p03_two_boot_retention_x_fb_ppm_render(self) -> None:
        if not has_gcc():
            self.skipTest("gcc not available")
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        rep2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertTrue(rep2["restored_from_prior"])
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _dump_ppm(fb_bin, self.sb.out_dir / "p03.ppm", ["--state", str(self.sb.boot_json)])
        self.assertEqual((w, h), (1024, 768))
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_p04_amber_theme_boot_state_x_fb_ppm(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        os.environ["ZOE_THEME"] = "amber"
        try:
            run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        finally:
            os.environ.pop("ZOE_THEME", None)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _dump_ppm(fb_bin, self.sb.out_dir / "p04.ppm", ["--state", str(self.sb.boot_json)])
        self.assertTrue(is_amber_crt_dominant(w, h, rgb))

    def test_p05_portrait_phone_x_amber_crt(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w_std, h_std, rgb_std = _dump_ppm(fb_bin, self.sb.out_dir / "p05s.ppm", ["--size", "540x960", "--portrait"])
        w_amb, h_amb, rgb_amb = _dump_ppm(fb_bin, self.sb.out_dir / "p05a.ppm", ["--size", "540x960", "--portrait", "--amber"])
        assert_portrait_geometry(w_amb, h_amb)
        self.assertEqual((w_std, h_std), (w_amb, h_amb))
        self.assertTrue(is_amber_crt_dominant(w_amb, h_amb, rgb_amb))
        self.assertGreater(diff_ratio(rgb_std, rgb_amb), 0.25)

    def test_p06_micro_hud_x_amber_crt(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _dump_ppm(fb_bin, self.sb.out_dir / "p06.ppm", ["--size", "320x240", "--amber"])
        assert_micro_hud_geometry(w, h)
        self.assertTrue(is_amber_crt_dominant(w, h, rgb))
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_p07_hw_diagnostic_x_zo3_slots_x_drawer(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os import UmaBridge
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.write_shm_heartbeat("zo3-node-1", {"node_id": 1, "theme": "gem", "boot_count": 1}, slot=1)
        uma.write_shm_heartbeat("zo3-node-2", {"node_id": 2, "theme": "amber", "boot_count": 1}, slot=2)
        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertIn("hw_profile", rep)
        self.assertGreaterEqual(rep["drawer_count"], 1)
        self.assertEqual(sorted(uma.read_all_zo3_slots().keys()), [1, 2])
        assert_constitutional_honesty(rep, require_flight=True)

    def test_p08_shell_return_x_boot_chain_x_hw_cmd(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        require_capability(self, "M1_SHELL_FLAG", probe_m1_shell_flag)
        env = isolated_env(self.sb.home_dir, {
            "ZOE_STATE_DIR": str(self.sb.state_dir),
            "ZOE_BOOT_JSON": str(self.sb.boot_json),
        })
        runtime_py = str(ZOE_GEM_OS_DIR / "zoe_os_runtime.py")
        subprocess.run([sys.executable, runtime_py, "--boot"], env=env, check=True, capture_output=True)
        proc = subprocess.run(
            [sys.executable, runtime_py, "--shell"],
            input="hw\ndrawer add Shell note\nquit\n",
            text=True,
            env=env,
            capture_output=True,
            check=True,
        )
        self.assertIn("Hardware Observation", proc.stdout)
        self.assertIn("Saved to hardware drawer", proc.stdout)
        state = json.loads(self.sb.boot_json.read_text(encoding="utf-8"))
        self.assertEqual(state["boot_count"], 1)

    def test_p09_lume_cli_uma_zo3_health_x_shm_slots(self) -> None:
        from guiai.gem.lume_cli import LumeCli
        from guiai.gem.zoe_gem_os import UmaBridge
        from zoe_autonomy.chat import ZoeChat

        uma_dir = self.sb.home_dir / ".zoe" / "uma-bridge"
        uma = UmaBridge(uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        for slot, theme in ((1, "gem"), (2, "amber"), (3, "gem")):
            uma.write_shm_heartbeat(f"zo3-{slot}", {"node_id": slot, "boot_count": 2, "chain_intact": True, "theme": theme}, slot=slot)
        cli = LumeCli(ZoeChat(REPO_ROOT), REPO_ROOT, color=False, brain_state=self.sb.state_dir)
        with isolate_uma_shm(self.sb):
            handled, out = cli.handle_slash("/uma zo3 status", color=False)
        self.assertTrue(handled)
        out_text = "\n".join(out or [])
        self.assertIn("ZO3 Multi-Zoe", out_text)
        self.assertIn("3/3", out_text)
        self.assertIn("amber", out_text)
        self.assertIn(str(self.sb.uma_shm), out_text)

    def test_p10_wayland_launch_mode_x_lts_target(self) -> None:
        require_capability(self, "M3_WAYLAND_LAUNCH", probe_m3_launch_wayland_sig)
        import inspect
        from guiai.gem.zoe_gem_os import launch_zoe_gem_os_kvm

        sig = inspect.signature(launch_zoe_gem_os_kvm)
        self.assertIn("mode", sig.parameters)
        for mode_val in ("split", "portrait", "phone"):
            kwargs = {"mode": mode_val}
            if "target" in sig.parameters:
                kwargs["target"] = "lts"
            res, argv = launch_with_qemu_shim(self.sb, "zoe-gem-os-lts.iso", **kwargs)
            self.assertTrue(res.get("ok"))
            joined = " ".join(argv)
            self.assertIn("zoe-gem-os-lts.iso", joined)
            self.assertIn("-vga none", joined)
            self.assertIn("VGA,xres=", joined)
            self.assertNotIn("zoom-to-fit=on", joined)


if __name__ == "__main__":
    unittest.main()

"""Tier 4 E2E Tests: Full real-world application scenarios S1-S6."""

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
    find_cached_iso,
    find_ovmf_firmware,
    has_gcc,
    has_qemu_kvm,
    is_strict_mode,
    isolate_uma_shm,
    launch_with_qemu_shim,
    probe_m1_hw_observation,
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
    region_stats,
)
from qmp_client import (  # noqa: E402
    QmpClient,
    alloc_free_port,
    terminate_qemu_proc,
    wait_until,
)


def _dump_ppm(fb_bin: Path, out_ppm: Path, args: list[str]) -> tuple[int, int, bytes]:
    """Compile-time helper wrapper to dump and parse a P6 PPM."""
    subprocess.run([str(fb_bin), *args, "--dump-ppm", str(out_ppm)], check=True, capture_output=True)
    return read_ppm(out_ppm)


_SILICON_PROFILE_CASES = (
    ("kvm", 4, 2048, "1280x800", "x86_64", True, True, 1, False, "QEMU", "", "KVM_UMA_SPLIT"),
    ("laptop", 8, 16384, "1920x1080", "x86_64", False, False, 1, False, "Dell Inc.", "10", "LAPTOP_BARE_METAL"),
    ("beo", 32, 32768, "1280x800", "x86_64", False, False, 1, False, "", "", "BEOWULF_COMPUTE_NODE"),
    ("daq", 4, 4096, None, "x86_64", False, False, 2, False, "", "", "HEADLESS_DAQ_NODE"),
    ("pi", 4, 1024, "800x480", "aarch64", False, False, 1, False, "", "", "EDGE_SBC_PI"),
    ("phone", 4, 2048, "540x960", "x86_64", False, False, 1, False, "", "", "PORTRAIT_PHONE_TOUCH"),
    ("micro", 2, 512, "320x240", "x86_64", False, False, 0, False, "", "", "MICRO_HUD_HEADLAMP"),
    ("sar", 4, 2048, "800x480", "x86_64", False, False, 1, True, "", "", "SAR_COMPANION_EDGE"),
    ("hdls", 2, 1024, None, "x86_64", False, False, 0, False, "", "", "HEADLESS_SAFE_FALLBACK"),
)


def _seed_extra_hw_nodes(sys_r: Path, dev_r: Path, nics: int, tty_usb: bool, sys_vendor: str, chassis_type: str) -> None:
    """Populate synthetic NIC, field serial, and DMI metadata in fixture trees."""
    for idx in range(nics):
        nic_d = sys_r / "class/net" / f"eth{idx}"
        nic_d.mkdir(parents=True, exist_ok=True)
        (nic_d / "operstate").write_text("up\n", encoding="utf-8")
    if tty_usb:
        (dev_r / "ttyUSB0").write_text("", encoding="utf-8")
    if sys_vendor:
        (sys_r / "class/dmi/id/sys_vendor").write_text(sys_vendor + "\n", encoding="utf-8")
    if chassis_type:
        (sys_r / "class/dmi/id/chassis_type").write_text(chassis_type + "\n", encoding="utf-8")


def _seed_silicon_fixture(
    base: Path,
    cores: int,
    ram_mb: int,
    fb_size: str | None,
    arch: str = "x86_64",
    *,
    nics: int = 0,
    tty_usb: bool = False,
    sys_vendor: str = "",
    chassis_type: str = "",
) -> tuple[Path, Path, Path]:
    """Build synthetic proc/sys/dev tree for diverse silicon hardware observation tests."""
    proc_r, sys_r, dev_r = base / "proc", base / "sys", base / "dev"
    for d in (proc_r, sys_r / "class/dmi/id", sys_r / "bus/pci/devices", sys_r / "class/net", sys_r / "class/block", sys_r / "class/input", dev_r):
        d.mkdir(parents=True, exist_ok=True)
    cpu_blocks = "\n".join(f"processor\t: {i}\nmodel name\t: Synthetic {arch} Core" for i in range(cores))
    (proc_r / "cpuinfo").write_text(cpu_blocks + "\n", encoding="utf-8")
    (proc_r / "meminfo").write_text(f"MemTotal:       {ram_mb * 1024} kB\nMemAvailable:   {ram_mb * 512} kB\n", encoding="utf-8")
    if fb_size:
        fb_dir = sys_r / "class/graphics/fb0"
        fb_dir.mkdir(parents=True, exist_ok=True)
        (fb_dir / "virtual_size").write_text(fb_size.replace("x", ",") + "\n", encoding="utf-8")
        (fb_dir / "bits_per_pixel").write_text("32\n", encoding="utf-8")
    _seed_extra_hw_nodes(sys_r, dev_r, nics, tty_usb, sys_vendor, chassis_type)
    return proc_r, sys_r, dev_r


def _create_ext4_disk(disk_path: Path) -> None:
    """Allocate a fresh 64 MiB ext4 ZOE-STATE image in a temp sandbox."""
    with disk_path.open("wb") as fh:
        fh.truncate(64 * 1024 * 1024)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(disk_path)], check=True, capture_output=True)


class Tier4ScenarioTests(unittest.TestCase):
    """Six real-world end-to-end workflows (S1-S6) across Zoe-GEM OS."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t4-")
        self.sb = create_sandbox(self._td.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.sb.home_dir)

    def tearDown(self) -> None:
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self._td.cleanup()

    def test_s1_split_screen_wayland_uma_daily_session(self) -> None:
        """S1: 50/50 split-screen UMA mutual-consent workflow and instant lock."""
        from guiai.gem.lume_cli import LumeCli
        from guiai.gem.zoe_gem_os import UmaBridge
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync
        from zoe_autonomy.chat import ZoeChat

        cli = LumeCli(ZoeChat(REPO_ROOT), REPO_ROOT, color=False, brain_state=self.sb.state_dir)
        uma_dir = self.sb.home_dir / ".zoe" / "uma-bridge"
        with isolate_uma_shm(self.sb):
            cli.handle_slash("/uma status", color=False)
            cli.handle_slash("/uma grant split_daily", color=False)
            os.environ["ZOE_UMA_DIR"] = str(uma_dir)
            try:
                rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
            finally:
                os.environ.pop("ZOE_UMA_DIR", None)
            self.assertEqual(rep["uma_gate"], "SHARED")
            self.assertTrue((uma_dir / "zoe_to_nick" / "zoe_os_emblem.gem").is_file())
            host_note = self.sb.root / "research_plan.txt"
            host_note.write_text("split screen MNI152 note", encoding="utf-8")
            cli.handle_slash(f"/uma send {host_note}", color=False)
            self.assertTrue((uma_dir / "nick_to_zoe" / "research_plan.txt").is_file())
            cli.handle_slash("/uma lock", color=False)
            self.assertEqual(UmaBridge(uma_dir).read_state()["gate"], "PRIVATE")
        require_capability(self, "M3_WAYLAND_LAUNCH", probe_m3_launch_wayland_sig)
        res, argv = launch_with_qemu_shim(self.sb, "zoe-gem-os.iso", mode="split")
        self.assertTrue(res.get("ok"))
        self.assertNotIn("zoom-to-fit=on", " ".join(argv))

    def test_s2_zo3_three_node_research_cluster(self) -> None:
        """S2: Multi-Zoe ZO3 3-node cluster sharing one 4 MB BAR2 SHM & UMA airlock."""
        from guiai.gem.zoe_gem_os import UmaBridge
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        for nid, theme in ((1, "gem"), (2, "amber"), (3, "gem")):
            os.environ["ZOE_NODE_ID"] = str(nid)
            os.environ["ZOE_THEME"] = theme
            try:
                rep = run_boot_sync(self.sb.state_dir / f"node{nid}", self.sb.boot_json)
            finally:
                os.environ.pop("ZOE_NODE_ID", None)
                os.environ.pop("ZOE_THEME", None)
            uma.write_shm_heartbeat(
                f"zo3-node-{nid}",
                {"node_id": nid, "boot_count": rep["boot_count"], "chain_intact": rep["chain_intact"], "theme": theme},
                slot=nid,
            )
        slots = uma.read_all_zo3_slots()
        self.assertEqual(sorted(slots.keys()), [1, 2, 3])
        self.assertEqual(slots[2]["theme"], "amber")
        self.assertIn("3/3", "\n".join(uma.format_zo3_health()))

    def test_s3_amber_crt_artline_and_drawer_persistence(self) -> None:
        """S3: Artist session with Artline vault, Drawer persistence across reboot, and Amber CRT."""
        if not has_gcc():
            self.skipTest("gcc not available")
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        drawer = self.sb.state_dir / "nick_drawer.json"
        notes = json.loads(drawer.read_text(encoding="utf-8"))
        notes.append({"boot": 1, "author": "Nicholas", "text": "Amber Artline Plate #2"})
        drawer.write_text(json.dumps(notes), encoding="utf-8")

        rep2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertTrue(rep2["restored_from_prior"])
        self.assertTrue(rep2["vault_restored"])
        self.assertEqual(rep2["drawer_count"], 2)

        fb_bin = build_fb_binary(self.sb.out_dir)
        w1, h1, rgb_gem = _dump_ppm(fb_bin, self.sb.out_dir / "s3_gem.ppm", ["--state", str(self.sb.boot_json)])
        self.assertTrue(is_non_blank(w1, h1, rgb_gem))
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        w2, h2, rgb_amb = _dump_ppm(fb_bin, self.sb.out_dir / "s3_amb.ppm", ["--state", str(self.sb.boot_json), "--amber"])
        self.assertTrue(is_amber_crt_dominant(w2, h2, rgb_amb))
        self.assertGreater(diff_ratio(rgb_gem, rgb_amb), 0.25)

    def test_s4_flip_long_ways_and_phone_touch_workflow(self) -> None:
        """S4: Responsive landscape -> split portrait -> phone aspect workflow."""
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        geoms = (("1024x768", []), ("960x1080", ["--portrait"]), ("768x1024", ["--portrait"]), ("540x960", ["--portrait"]), ("480x854", ["--portrait"]))
        for size_arg, extra in geoms:
            w, h, rgb = _dump_ppm(fb_bin, self.sb.out_dir / f"s4_{size_arg}.ppm", ["--size", size_arg, *extra])
            exp_w, exp_h = (int(x) for x in size_arg.split("x"))
            self.assertEqual((w, h), (exp_w, exp_h))
            self.assertTrue(is_non_blank(w, h, rgb))
            if extra:
                assert_portrait_geometry(w, h)

    def test_s5_diverse_silicon_hardware_observation(self) -> None:
        """S5: Hardware safety observation across all 9 silicon profiles + Micro-HUD."""
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import observe_hardware, run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
        assert_constitutional_honesty(rep, require_flight=True)
        self.assertEqual(len(obs.get("gates", {})), 7)

        for tag, cores, ram, fb, arch, shm_ok, p9_ok, nics, tty_usb, vendor, chassis, expected in _SILICON_PROFILE_CASES:
            pr, sr, dr = _seed_silicon_fixture(
                self.sb.root / tag, cores, ram, fb, arch,
                nics=nics, tty_usb=tty_usb, sys_vendor=vendor, chassis_type=chassis,
            )
            res = observe_hardware(
                self.sb.state_dir, proc_root=pr, sys_root=sr, dev_root=dr,
                uma_shm_ok=shm_ok, uma_9p_mounted=p9_ok, arch_override=arch,
            )
            self.assertEqual(res["profile"], expected)
            self.assertIn(res["safety_overall"], ("PASS", "DEGRADED"))
            assert_constitutional_honesty(res, require_flight=True)

        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _dump_ppm(fb_bin, self.sb.out_dir / "s5_micro.ppm", ["--size", "320x240", "--amber"])
        assert_micro_hud_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_s6_ovmf_kvm_boot_and_interactive_amber_qmp_dump(self) -> None:
        """S6: Cached lts (or virt fallback) 2-boot OVMF+KVM verification + [A] Amber & [O] flip."""
        iso = find_cached_iso("lts") or find_cached_iso("virt")
        ovmf = find_ovmf_firmware()
        if not (has_qemu_kvm() and iso and ovmf):
            self.skipTest("Requires host /dev/kvm, OVMF, and cached Zoe-GEM OS ISO")
        state_img = self.sb.out_dir / "s6_state.img"
        _create_ext4_disk(state_img)

        p1_gem, p1_amb = self.sb.out_dir / "s6_b1_gem.ppm", self.sb.out_dir / "s6_b1_amb.ppm"
        _run_s6_boot_and_key(iso, state_img, ovmf, p1_gem, p1_amb, "a", _amber_rendered, strict_diff=True)
        w1, h1, rgb_amb = read_ppm(p1_amb)
        self.assertTrue(is_amber_crt_dominant(w1, h1, rgb_amb))

        p2_gem, p2_ori = self.sb.out_dir / "s6_b2_gem.ppm", self.sb.out_dir / "s6_b2_ori.ppm"
        iso_has_m2 = iso.stat().st_mtime >= (ZOE_GEM_OS_DIR / "zoe_gem_fb.c").stat().st_mtime or is_strict_mode()
        _run_s6_boot_and_key(iso, state_img, ovmf, p2_gem, p2_ori, "o", _diff_rendered, strict_diff=iso_has_m2)
        w2, h2, rgb_b2 = read_ppm(p2_ori if p2_ori.is_file() else p2_gem)
        self.assertTrue(is_non_blank(w2, h2, rgb_b2))

        p3_phone = self.sb.out_dir / "s6_phone_544.ppm"
        _run_s6_phone_vga_check(iso, state_img, ovmf, p3_phone)
        w3, h3, rgb_phone = read_ppm(p3_phone)
        self.assertEqual((w3, h3), (544, 960))
        self.assertEqual(w3 % 8, 0)
        self.assertTrue(is_non_blank(w3, h3, rgb_phone))


def _run_s6_boot_and_key(
    iso: Path,
    state_img: Path,
    ovmf: Path,
    base_ppm: Path,
    after_ppm: Path,
    key: str,
    check_fn: object,
    strict_diff: bool,
) -> None:
    """Boot iso + state_img under OVMF+KVM+QMP, verify desktop, send key, and clean up safely."""
    qmp_port = alloc_free_port()
    cmd = [
        "qemu-system-x86_64", "-enable-kvm", "-machine", "q35", "-cpu", "host",
        "-m", "768M", "-smp", "2", "-bios", str(ovmf),
        "-drive", f"file={iso},media=cdrom,readonly=on,if=ide", "-boot", "d",
        "-drive", f"file={state_img},format=raw,if=virtio",
        "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
        "-vga", "std", "-display", "none",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server,nowait", "-no-reboot",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with QmpClient("127.0.0.1", qmp_port, timeout_sec=15.0) as qmp:
            wait_until(lambda: _desktop_rendered(qmp, base_ppm), timeout_sec=35.0, interval=0.5, desc="GEM desktop")
            qmp.sendkey(key)
            if strict_diff:
                wait_until(lambda: check_fn(qmp, base_ppm, after_ppm), timeout_sec=8.0, interval=0.3, desc=f"key {key} render")
            else:
                qmp.screendump(after_ppm)
            qmp.quit()
    finally:
        terminate_qemu_proc(proc)


def _diff_rendered(qmp: QmpClient, baseline_ppm: Path, probe_ppm: Path) -> bool:
    """Capture QMP screendump and return True once framebuffer differs significantly."""
    qmp.screendump(probe_ppm)
    if not probe_ppm.is_file() or probe_ppm.stat().st_size != baseline_ppm.stat().st_size:
        return False
    _, _, rgb_now = read_ppm(probe_ppm)
    _, _, rgb_base = read_ppm(baseline_ppm)
    return diff_ratio(rgb_base, rgb_now) > 0.15


def _run_s6_phone_vga_check(iso: Path, state_img: Path, ovmf: Path, out_ppm: Path) -> None:
    """Boot iso with Bochs VGA xres=544,yres=960 and capture crisp 544x960 screendump."""
    qmp_port = alloc_free_port()
    cmd = [
        "qemu-system-x86_64", "-enable-kvm", "-machine", "q35", "-cpu", "host",
        "-m", "768M", "-smp", "2", "-bios", str(ovmf),
        "-drive", f"file={iso},media=cdrom,readonly=on,if=ide", "-boot", "d",
        "-drive", f"file={state_img},format=raw,if=virtio",
        "-vga", "none", "-device", "VGA,xres=544,yres=960", "-display", "none",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server,nowait", "-no-reboot",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with QmpClient("127.0.0.1", qmp_port, timeout_sec=15.0) as qmp:
            wait_until(
                lambda: _desktop_rendered(qmp, out_ppm, min_w=544, min_h=960),
                timeout_sec=35.0, interval=0.5, desc="phone 544x960 desktop",
            )
            qmp.quit()
    finally:
        terminate_qemu_proc(proc)


def _desktop_rendered(qmp: QmpClient, ppm_path: Path, min_w: int = 640, min_h: int = 480) -> bool:
    """Return True once QMP screendump shows a full rendered GEM desktop."""
    qmp.screendump(ppm_path)
    if not ppm_path.is_file() or ppm_path.stat().st_size < 1000:
        return False
    w, h, rgb = read_ppm(ppm_path)
    st = region_stats(w, h, rgb, step=8)
    return w >= min_w and h >= min_h and float(st["non_black_ratio"]) > 0.50


def _amber_rendered(qmp: QmpClient, baseline_ppm: Path, probe_ppm: Path) -> bool:
    """Capture QMP screendump and return True once Amber CRT dominates and differs."""
    qmp.screendump(probe_ppm)
    if not probe_ppm.is_file() or probe_ppm.stat().st_size != baseline_ppm.stat().st_size:
        return False
    w, h, rgb_now = read_ppm(probe_ppm)
    _, _, rgb_base = read_ppm(baseline_ppm)
    return is_amber_crt_dominant(w, h, rgb_now) and diff_ratio(rgb_base, rgb_now) > 0.15


if __name__ == "__main__":
    unittest.main()

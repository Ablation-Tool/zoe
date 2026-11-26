"""Tier 1 E2E Tests: Happy-path feature coverage across F1-F7 (>= 35 tests)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
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
    isolate_uma_shm,
    isolated_env,
    launch_with_qemu_shim,
    probe_m1_hw_observation,
    probe_m1_shell_flag,
    probe_m1_uma_flock,
    probe_m2_geometry_flags,
    probe_m2_werror_compile,
    probe_m3_launch_wayland_sig,
    probe_m3_lume_slash_commands,
    probe_m3_os_hw_command,
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


def _make_lume_cli(home_dir: Path, brain_state: Path):
    """Instantiate an isolated LumeCli bound to temporary HOME and brain state."""
    from guiai.gem.lume_cli import LumeCli
    from zoe_autonomy.chat import ZoeChat

    return LumeCli(ZoeChat(REPO_ROOT), REPO_ROOT, color=False, brain_state=brain_state)


def _run_fb_ppm(fb_bin: Path, out_ppm: Path, extra_args: list[str] | None = None) -> tuple[int, int, bytes]:
    """Run zoe_gem_fb --dump-ppm and return parsed (width, height, rgb)."""
    cmd = [str(fb_bin)] + (extra_args or []) + ["--dump-ppm", str(out_ppm)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise AssertionError(f"zoe_gem_fb failed ({proc.returncode}): {proc.stderr}")
    return read_ppm(out_ppm)


def _start_mock_qmp_server(port: int, screendump_target: Path) -> tuple[threading.Event, threading.Thread]:
    """Start a single-client TCP mock QMP server responding to capabilities/screendump/quit."""
    ready = threading.Event()

    def _serve() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            ready.set()
            conn, _ = srv.accept()
            with conn:
                conn.sendall(b'{"QMP": {"version": {"qemu": {"major": 10}}}}\n')
                for line in conn.makefile("r", encoding="utf-8"):
                    req = json.loads(line)
                    cmd = req.get("execute")
                    if cmd == "screendump":
                        screendump_target.write_bytes(b"P6\n2 2\n255\n" + b"\xff\x80\x00" * 4)
                    out = {"return": "ok"} if cmd == "human-monitor-command" else {"return": {}}
                    conn.sendall((json.dumps(out) + "\n").encode("utf-8"))
                    if cmd == "quit":
                        break

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    ready.wait(timeout=3.0)
    return ready, thread


class Tier1F1CliTests(unittest.TestCase):
    """F1: Zoe CLI & Lume /os and /uma command surface."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f1-")
        self.sb = create_sandbox(self._td.name)
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.sb.home_dir)

    def tearDown(self) -> None:
        if self._old_home is not None:
            os.environ["HOME"] = self._old_home
        self._td.cleanup()

    def test_f1_zoe_cli_help_and_os_list(self) -> None:
        env = isolated_env(self.sb.home_dir)
        p_help = subprocess.run([sys.executable, "-m", "guiai.gem.unified_cli", "--help"], capture_output=True, text=True, env=env, check=False)
        self.assertEqual(p_help.returncode, 0)
        self.assertIn("Zoe", p_help.stdout)
        p_list = subprocess.run([sys.executable, "-m", "guiai.gem.unified_cli", "os", "--list"], capture_output=True, text=True, env=env, check=False)
        self.assertEqual(p_list.returncode, 0)
        self.assertTrue(len(p_list.stdout.strip().splitlines()) >= 1)

    def test_f1_lume_os_status_and_usb_guide(self) -> None:
        cli = _make_lume_cli(self.sb.home_dir, self.sb.state_dir)
        ok_s, out_s = cli.handle_slash("/os status", color=False)
        self.assertTrue(ok_s)
        joined = "\n".join(out_s or [])
        self.assertIn("Zoe-GEM OS", joined)
        self.assertIn("zoe-gem-os.iso", joined)
        ok_u, out_u = cli.handle_slash("/os usb", color=False)
        self.assertTrue(ok_u)
        self.assertIn("Stage 2", "\n".join(out_u or []))

    def test_f1_lume_uma_status_health_inbox_and_audit(self) -> None:
        cli = _make_lume_cli(self.sb.home_dir, self.sb.state_dir)
        with isolate_uma_shm(self.sb):
            for cmd in ("/uma status", "/uma health", "/uma inbox", "/uma audit"):
                handled, lines = cli.handle_slash(cmd, color=False)
                self.assertTrue(handled)
                self.assertTrue(lines)
            _, st_lines = cli.handle_slash("/uma status", color=False)
        self.assertIn("PRIVATE", "\n".join(st_lines or []))

    def test_f1_lume_uma_grant_and_lock_lifecycle(self) -> None:
        cli = _make_lume_cli(self.sb.home_dir, self.sb.state_dir)
        with isolate_uma_shm(self.sb):
            _, out_g = cli.handle_slash("/uma grant research_test", color=False)
            self.assertIn("REQUESTED", "\n".join(out_g or []))
            _, out_l = cli.handle_slash("/uma lock", color=False)
            self.assertIn("PRIVATE", "\n".join(out_l or []))
            _, out_a = cli.handle_slash("/uma audit", color=False)
        self.assertIn("consent_update", "\n".join(out_a or []))

    def test_f1_lume_slash_commands_register_os_and_uma(self) -> None:
        require_capability(self, "M3_LUME_SLASH_COMMANDS", probe_m3_lume_slash_commands)
        from guiai.gem.lume_cli import LUME_SLASH_COMMANDS

        self.assertIn("/os", LUME_SLASH_COMMANDS)
        self.assertIn("/uma", LUME_SLASH_COMMANDS)

    def test_f1_lume_os_hw_diagnostic_command(self) -> None:
        require_capability(self, "M3_OS_HW_CMD", probe_m3_os_hw_command)
        cli = _make_lume_cli(self.sb.home_dir, self.sb.state_dir)
        handled, out = cli.handle_slash("/os hw", color=False)
        self.assertTrue(handled)
        self.assertTrue(out)
        self.assertNotIn("Usage:", "\n".join(out or []))


class Tier1F2BootRetentionTests(unittest.TestCase):
    """F2: SHA-256 boot chain retention, Artline/RSC vault, and --boot vs --shell."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f2-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f2_two_boot_sha256_retention_chain(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        r1 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(r1["boot_count"], 1)
        self.assertFalse(r1["restored_from_prior"])
        self.assertTrue(r1["chain_intact"])
        r2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(r2["boot_count"], 2)
        self.assertTrue(r2["restored_from_prior"])
        self.assertTrue(r2["chain_intact"])
        self.assertEqual(r2["prev_sha"], r1["chain_sha"])

    def test_f2_artline_and_rsc_vault_persistence(self) -> None:
        from guiai.gem.zoe_atari_gem_rsc import parse_atari_rsc
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        r1 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(r1["artline_files"], 3)
        self.assertEqual(r1["rsc_bytes"], 2990)
        parsed = parse_atari_rsc((self.sb.state_dir / "artline" / "ZOE_GEM.RSC").read_bytes())
        self.assertTrue(parsed["size_matches_rsh_rssize"])
        self.assertGreater(parsed["header"]["rsh_nib"], 0)
        self.assertFalse(r1["vault_restored"])
        r2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertTrue(r2["vault_restored"])
        self.assertEqual(r2["artline_sha"], r1["artline_sha"])

    def test_f2_drawer_seeded_and_preserved_across_boots(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        r1 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(r1["drawer_count"], 1)
        drawer = self.sb.state_dir / "nick_drawer.json"
        notes = json.loads(drawer.read_text(encoding="utf-8"))
        notes.append({"boot": 1, "author": "Nicholas", "text": "Second persistent note"})
        drawer.write_text(json.dumps(notes), encoding="utf-8")
        r2 = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        self.assertEqual(r2["drawer_count"], 2)
        self.assertEqual(r2["drawer_latest"], "Second persistent note")

    def test_f2_boot_state_constitutional_honesty(self) -> None:
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        assert_constitutional_honesty(rep)

    def test_f2_shell_flag_preserves_boot_count(self) -> None:
        require_capability(self, "M1_SHELL_FLAG", probe_m1_shell_flag)
        env = isolated_env(self.sb.home_dir, {
            "ZOE_STATE_DIR": str(self.sb.state_dir),
            "ZOE_BOOT_JSON": str(self.sb.boot_json),
        })
        runtime_py = str(ZOE_GEM_OS_DIR / "zoe_os_runtime.py")
        subprocess.run([sys.executable, runtime_py, "--boot"], env=env, check=True, capture_output=True)
        proc = subprocess.run(
            [sys.executable, runtime_py, "--shell"],
            input="status\nquit\n",
            text=True,
            env=env,
            capture_output=True,
            check=True,
        )
        self.assertNotIn("ZOE_OS_BOOT_OK", proc.stdout)
        state = json.loads(self.sb.boot_json.read_text(encoding="utf-8"))
        self.assertEqual(state["boot_count"], 1)


class Tier1F3HardwareDiagnosticTests(unittest.TestCase):
    """F3: Initial Hardware Safety Observation Diagnostic (M1-gated)."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f3-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f3_hw_observation_json_has_seven_gates(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
        gates = obs.get("gates", {})
        expected = ("cpu_arch", "ram_headroom", "persistent_storage", "display_fb", "input_devices", "network", "hardware_uma")
        for key in expected:
            self.assertIn(key, gates)
            self.assertIn(gates[key]["status"], ("PASS", "DEGRADED", "UNSUPPORTED"))

    def test_f3_boot_state_exposes_flat_hw_keys(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        for key in ("hw_profile", "hw_safety_overall", "hw_summary", "hw_orientation", "hw_zo3_budget"):
            self.assertIn(key, rep)
        self.assertLessEqual(len(str(rep["hw_summary"])), 64)
        self.assertIn(rep["hw_safety_overall"], ("PASS", "DEGRADED", "UNSUPPORTED"))

    def test_f3_hw_shell_command_outputs_diagnostic(self) -> None:
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
            input="hw\nquit\n",
            text=True,
            env=env,
            capture_output=True,
            check=True,
        )
        low = proc.stdout.lower()
        self.assertIn("hardware observation", low)
        self.assertIn("profile=", low)
        self.assertIn("clinical_action_authorized=false", low)

    def test_f3_hw_observation_recommendations_and_orientation(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
        self.assertIn(rep["hw_orientation"], ("landscape", "portrait", "micro", "headless"))
        self.assertGreaterEqual(int(rep["hw_zo3_budget"]), 1)
        self.assertTrue(obs.get("recommendations"))

    def test_f3_hw_diagnostic_advisory_only_flags(self) -> None:
        require_capability(self, "M1_HW_OBSERVATION", probe_m1_hw_observation)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        rep = run_boot_sync(self.sb.state_dir, self.sb.boot_json)
        obs = json.loads((self.sb.state_dir / "hw_observation.json").read_text(encoding="utf-8"))
        assert_constitutional_honesty(rep, require_flight=True)
        assert_constitutional_honesty(obs, require_flight=True)


class Tier1F4UmaAirlockTests(unittest.TestCase):
    """F4: Hardware UMA consent airlock, SHA-256 audit log, and BAR2 ZO3 slots."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f4-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f4_uma_private_default_and_requested_state(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        st = uma.ensure_initialized()
        self.assertEqual(st["gate"], "PRIVATE")
        st_req = uma.set_consent("nick", True)
        self.assertEqual(st_req["gate"], "REQUESTED")

    def test_f4_uma_mutual_consent_allows_bidirectional_transfer(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.set_consent("nick", True)
        uma.set_consent("zoe", True)
        src_a = self.sb.root / "from_nick.txt"
        src_b = self.sb.root / "from_zoe.txt"
        src_a.write_text("nick-payload", encoding="utf-8")
        src_b.write_text("zoe-payload", encoding="utf-8")
        tx_a = uma.transfer_file("nick", src_a)
        tx_b = uma.transfer_file("zoe", src_b)
        self.assertTrue(tx_a["ok"] and tx_b["ok"])
        self.assertEqual(tx_a["file_sha256"], hashlib.sha256(b"nick-payload").hexdigest())
        self.assertTrue((self.sb.uma_dir / "zoe_to_nick" / "from_zoe.txt").is_file())

    def test_f4_uma_audit_jsonl_sha256_chain_integrity(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        uma.set_consent("nick", True)
        uma.set_consent("zoe", True)
        uma.lock_all("nick")
        prev = "genesis"
        for line in uma.audit_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            self.assertEqual(rec["prev_sha"], prev)
            body = {k: v for k, v in rec.items() if k != "sha256"}
            expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            self.assertEqual(rec["sha256"], expected)
            prev = rec["sha256"]

    def test_f4_uma_bar2_zo3_slots_zero_through_three(self) -> None:
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        for idx in range(4):
            ok = uma.write_shm_heartbeat(f"node-{idx}", {"node_id": idx, "theme": "amber" if idx == 2 else "gem"}, slot=idx)
            self.assertTrue(ok)
        slots = uma.read_all_zo3_slots()
        self.assertEqual(sorted(slots.keys()), [0, 1, 2, 3])
        self.assertEqual(slots[2]["theme"], "amber")
        self.assertIn("ALL ACTIVE ZO3 NODES HEALTHY", "\n".join(uma.format_zo3_health()))

    def test_f4_uma_flock_and_atomic_state_write(self) -> None:
        require_capability(self, "M1_UMA_FLOCK", probe_m1_uma_flock)
        from guiai.gem.zoe_gem_os import UmaBridge

        uma = UmaBridge(self.sb.uma_dir, shm_path=self.sb.uma_shm)
        uma.ensure_initialized()
        st = uma.set_consent("zoe", True, reason="atomic_flock_check")
        self.assertEqual(st["gate"], "REQUESTED")
        self.assertEqual(uma.read_state()["reason"], "atomic_flock_check")


class Tier1F5GemDesktopAndAmberTests(unittest.TestCase):
    """F5: Native GEM Desktop, Artline 2.0, Drawer, and 1985 Amber CRT."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f5-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f5_static_compile_and_1024x768_ppm_dump(self) -> None:
        if not has_gcc():
            self.skipTest("gcc not available")
        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=False)
        w, h, rgb = _run_fb_ppm(fb_bin, self.sb.out_dir / "gem.ppm")
        self.assertEqual((w, h), (1024, 768))
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f5_strict_werror_compile(self) -> None:
        require_capability(self, "M2_WERROR_COMPILE", probe_m2_werror_compile)
        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=True)
        self.assertTrue(fb_bin.is_file())

    def test_f5_amber_crt_phosphor_mode(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=False)
        w1, h1, rgb_std = _run_fb_ppm(fb_bin, self.sb.out_dir / "std.ppm")
        w2, h2, rgb_amb = _run_fb_ppm(fb_bin, self.sb.out_dir / "amb.ppm", ["--amber"])
        self.assertEqual((w1, h1), (w2, h2))
        self.assertTrue(is_amber_crt_dominant(w2, h2, rgb_amb))
        self.assertGreater(diff_ratio(rgb_std, rgb_amb), 0.25)

    def test_f5_drawer_boot_state_render_and_ppm_diff(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        b1_json = self.sb.out_dir / "boot1.json"
        b2_json = self.sb.out_dir / "boot2.json"
        run_boot_sync(self.sb.state_dir, b1_json)
        drawer = self.sb.state_dir / "nick_drawer.json"
        notes = json.loads(drawer.read_text(encoding="utf-8"))
        notes.append({"boot": 1, "author": "Nicholas", "text": "PPM diff verification note"})
        drawer.write_text(json.dumps(notes), encoding="utf-8")
        run_boot_sync(self.sb.state_dir, b2_json)

        fb_bin = build_fb_binary(self.sb.out_dir, strict_werror=True)
        w1, h1, rgb1 = _run_fb_ppm(fb_bin, self.sb.out_dir / "boot1.ppm", ["--state", str(b1_json)])
        w2, h2, rgb2 = _run_fb_ppm(fb_bin, self.sb.out_dir / "boot2.ppm", ["--state", str(b2_json)])
        self.assertEqual((w1, h1), (w2, h2))
        self.assertTrue(is_non_blank(w1, h1, rgb1))
        self.assertTrue(is_non_blank(w2, h2, rgb2))
        self.assertGreater(diff_ratio(rgb1, rgb2), 0.0)

    def test_f5_artline_document_16fold_radial_and_vdi_exports(self) -> None:
        from guiai.gem.artline import ArtlineDocument, rotate_ring

        doc = ArtlineDocument()
        motif = [[490.0, 210.0], [500.0, 180.0], [510.0, 210.0]]
        rings = rotate_ring(motif, 500.0, 350.0, count=16)
        self.assertEqual(len(rings), 16)
        for poly in rings:
            doc.add_element("path", points=poly, closed=True, smooth=False, stroke="#ffb000", width=1.5)
        svg_p = self.sb.out_dir / "radial.svg"
        gem_p = self.sb.out_dir / "radial.gem"
        doc.export(svg_p, kind="svg")
        doc.export(gem_p, kind="gem")
        self.assertGreater(svg_p.stat().st_size, 200)
        self.assertGreater(gem_p.stat().st_size, 100)


class Tier1F6PortraitAndPhoneTests(unittest.TestCase):
    """F6: Portrait ('flip long ways'), phone dimensions, and micro-HUD headlamp (M2-gated)."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f6-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f6_portrait_split_960x1080_ppm(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _run_fb_ppm(fb_bin, self.sb.out_dir / "split_p.ppm", ["--size", "960x1080", "--portrait"])
        self.assertEqual((w, h), (960, 1080))
        assert_portrait_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_phone_540x960_ppm(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _run_fb_ppm(fb_bin, self.sb.out_dir / "phone_540.ppm", ["--size", "540x960", "--portrait"])
        self.assertEqual((w, h), (540, 960))
        assert_portrait_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_phone_480x854_ppm(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _run_fb_ppm(fb_bin, self.sb.out_dir / "phone_480.ppm", ["--size", "480x854", "--portrait"])
        self.assertEqual((w, h), (480, 854))
        assert_portrait_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_micro_hud_headlamp_320x240_ppm(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w, h, rgb = _run_fb_ppm(fb_bin, self.sb.out_dir / "micro.ppm", ["--size", "320x240"])
        self.assertEqual((w, h), (320, 240))
        assert_micro_hud_geometry(w, h)
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f6_orientation_flip_changes_layout_geometry(self) -> None:
        require_capability(self, "M2_GEOMETRY_FLAGS", probe_m2_geometry_flags)
        fb_bin = build_fb_binary(self.sb.out_dir)
        w_l, h_l, rgb_l = _run_fb_ppm(fb_bin, self.sb.out_dir / "land.ppm", ["--size", "960x540"])
        w_p, h_p, rgb_p = _run_fb_ppm(fb_bin, self.sb.out_dir / "port.ppm", ["--size", "960x540", "--portrait"])
        self.assertEqual((w_l, h_l), (w_p, h_p))
        self.assertGreater(diff_ratio(rgb_l, rgb_p), 0.30)


class Tier1F7QemuWaylandAndQmpTests(unittest.TestCase):
    """F7: QEMU/OVMF/KVM readiness, TCP QMP client, Wayland launch args, and live boot smoke."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory(prefix="zoe-t1-f7-")
        self.sb = create_sandbox(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_f7_host_kvm_ovmf_and_qemu_readiness(self) -> None:
        if not has_qemu_kvm():
            self.skipTest("QEMU/KVM unavailable on host")
        ovmf = find_ovmf_firmware()
        self.assertIsNotNone(ovmf, "OVMF UEFI firmware not found")

    def test_f7_qmp_client_tcp_loopback_protocol(self) -> None:
        port = alloc_free_port()
        dump_path = self.sb.out_dir / "mock_dump.ppm"
        _, srv_thread = _start_mock_qmp_server(port, dump_path)
        with QmpClient("127.0.0.1", port, timeout_sec=5.0) as qmp:
            qmp.screendump(dump_path)
            self.assertEqual(qmp.sendkey("a"), "ok")
            qmp.quit()
        srv_thread.join(timeout=2.0)
        w, h, rgb = read_ppm(dump_path)
        self.assertEqual((w, h), (2, 2))
        self.assertTrue(is_non_blank(w, h, rgb))

    def test_f7_package_exports_and_usb_guide_readonly(self) -> None:
        import guiai.gem.zoe_gem_os as zgo

        for name in ("UmaBridge", "build_zoe_gem_os_iso", "find_guest_ivshmem_bar2", "format_usb_stage2_guide", "launch_zo3_cluster", "launch_zoe_gem_os_kvm", "verify_zo3_concurrent_kvm", "verify_zoe_gem_os_qemu"):
            self.assertTrue(hasattr(zgo, name))
        guide = "\n".join(zgo.format_usb_stage2_guide(self.sb.out_dir / "missing.iso"))
        self.assertIn("read-only", guide.lower())

    def test_f7_wayland_launch_signature_and_args(self) -> None:
        require_capability(self, "M3_WAYLAND_LAUNCH", probe_m3_launch_wayland_sig)
        import inspect
        from guiai.gem.zoe_gem_os import launch_zoe_gem_os_kvm

        sig = inspect.signature(launch_zoe_gem_os_kvm)
        self.assertTrue("mode" in sig.parameters or "geometry" in sig.parameters)
        kwargs = {"mode": "split"} if "mode" in sig.parameters else {"split_screen": True}
        res, argv = launch_with_qemu_shim(self.sb, "zoe-gem-os.iso", **kwargs)
        self.assertTrue(res.get("ok"))
        joined = " ".join(argv)
        self.assertNotIn("zoom-to-fit=on", joined)
        self.assertIn("-vga none", joined)
        self.assertIn("VGA,xres=", joined)
        self.assertIn("yres=", joined)
        self.assertIn("OVMF", joined)

    def test_f7_ovmf_kvm_single_boot_smoke_with_qmp(self) -> None:
        iso = find_cached_iso("virt")
        ovmf = find_ovmf_firmware()
        if not (has_qemu_kvm() and iso and ovmf):
            self.skipTest("Requires host /dev/kvm, OVMF, and cached zoe-gem-os.iso")
        state_img = self.sb.out_dir / "smoke_state.img"
        with state_img.open("wb") as fh:
            fh.truncate(64 * 1024 * 1024)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(state_img)], check=True, capture_output=True)
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
        ppm_out = self.sb.out_dir / "live_boot.ppm"
        try:
            with QmpClient("127.0.0.1", qmp_port, timeout_sec=15.0) as qmp:
                wait_until(lambda: _qmp_desktop_ready(qmp, ppm_out), timeout_sec=30.0, interval=0.5, desc="GEM desktop")
                qmp.quit()
            w, h, rgb = read_ppm(ppm_out)
            self.assertGreaterEqual(w, 640)
            self.assertTrue(is_non_blank(w, h, rgb))
        finally:
            terminate_qemu_proc(proc)


def _qmp_desktop_ready(qmp: QmpClient, ppm_path: Path) -> bool:
    """Capture QMP screendump and return True once full GEM desktop renders."""
    qmp.screendump(ppm_path)
    if not ppm_path.is_file() or ppm_path.stat().st_size < 1000:
        return False
    w, h, rgb = read_ppm(ppm_path)
    st = region_stats(w, h, rgb, step=8)
    return w >= 640 and h >= 480 and float(st["non_black_ratio"]) > 0.50


if __name__ == "__main__":
    unittest.main()

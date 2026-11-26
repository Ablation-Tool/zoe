"""Unit tests for M1 UMA bridge / Rome path unification, airlock hardening, and non-mutating ChatStore."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from guiai.gem.lume_cli import LumeCli
from guiai.gem.zoe_gem_os.zoe_uma import (
    DEFAULT_UMA_DIR,
    DEFAULT_UMA_SHM,
    UMA_MAX_SLOTS,
    UmaBridge,
    resolve_uma_paths,
)
from guiai.gem.zoe_rome_fusion import get_pixel_and_zo3_status_payload, toggle_uma_consent_bridge
from zoe_autonomy.chat import ChatStore, ZoeChat

REPO_ROOT = Path(__file__).resolve().parents[3]


class UmaBridgeFixesTests(unittest.TestCase):
    def test_resolve_uma_paths_defaults_env_and_explicit_overrides(self) -> None:
        self.assertEqual(DEFAULT_UMA_SHM, "/dev/shm/zoe-uma-bar.shm")
        self.assertEqual(DEFAULT_UMA_DIR.name, "uma-bridge")

        with tempfile.TemporaryDirectory(prefix="uma-resolve-") as td:
            base = Path(td)
            env_dir = base / "env_uma"
            env_shm = base / "env_uma.shm"
            exp_dir = base / "exp_uma"
            exp_shm = base / "exp_uma.shm"

            with mock.patch.dict(os.environ, {"ZOE_UMA_DIR": str(env_dir), "ZOE_UMA_SHM": str(env_shm)}):
                d1, s1 = resolve_uma_paths()
                self.assertEqual(d1, env_dir.resolve())
                self.assertEqual(s1, env_shm)

                d2, s2 = resolve_uma_paths(exp_dir, exp_shm)
                self.assertEqual(d2, exp_dir.resolve())
                self.assertEqual(s2, exp_shm)

    def test_rome_fusion_uses_canonical_and_overridable_uma_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uma-rome-") as td:
            base = Path(td)
            uma_dir = base / "uma-bridge"
            uma_shm = base / "uma-bar.shm"
            with mock.patch.dict(os.environ, {"ZOE_UMA_DIR": str(uma_dir), "ZOE_UMA_SHM": str(uma_shm)}):
                status_before = get_pixel_and_zo3_status_payload("panther")
                self.assertEqual(status_before["uma_gate"], "PRIVATE")
                self.assertFalse((uma_dir / "uma_state.json").exists())

                toggled = toggle_uma_consent_bridge("nick")
                self.assertTrue(toggled["ok"])
                self.assertTrue(toggled["state"]["nick_allow"])
                self.assertEqual(toggled["state"]["gate"], "REQUESTED")
                self.assertTrue((uma_dir / "uma_state.json").is_file())
                self.assertTrue(uma_shm.is_file())

                bridge = UmaBridge(uma_dir, shm_path=uma_shm)
                bridge.set_consent("zoe", True, reason="rome_sync_verify")
                status_after = get_pixel_and_zo3_status_payload("panther")
                self.assertEqual(status_after["uma_gate"], "SHARED")

    def test_read_state_non_mutating_and_actor_type_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uma-ro-") as td:
            uma_dir = Path(td) / "nonexistent_uma"
            uma_shm = Path(td) / "nonexistent.shm"
            bridge = UmaBridge(uma_dir, shm_path=uma_shm)

            state = bridge.read_state()
            self.assertEqual(state["gate"], "PRIVATE")
            self.assertEqual(state["reason"], "uninitialized")
            self.assertFalse(uma_dir.exists())
            self.assertFalse(bridge.lock_path.exists())
            self.assertTrue(bridge.verify_audit_chain()["valid"])

            for bad_actor in (None, 123, "mallory", ""):
                with self.assertRaises(ValueError):
                    bridge.set_consent(bad_actor, True)  # type: ignore[arg-type]
                with self.assertRaises(ValueError):
                    bridge.transfer_file(bad_actor, Path(td) / "x.txt")  # type: ignore[arg-type]

    def test_transfer_file_hardening_and_audit_chain_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uma-xfer-") as td:
            base = Path(td)
            bridge = UmaBridge(base / "uma", shm_path=base / "uma.shm")
            bridge.ensure_initialized()
            bridge.set_consent("nick", True)
            bridge.set_consent("zoe", True)

            # Empty / NUL / dotfile / traversal rejected
            for bad_src in ("", "   ", "foo\x00bar.txt", str(base / ".secret"), str(base / "sub" / ".." / "a.txt")):
                with self.assertRaises(ValueError):
                    bridge.transfer_file("nick", bad_src)

            # Symlink rejected when allow_symlinks=False (leaf, parent dir, nested ancestor, relative parent)
            target = base / "real.txt"
            target.write_text("real data", encoding="utf-8")
            link = base / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                bridge.transfer_file("nick", link)

            real_parent = base / "real_parent"
            nested_sub = real_parent / "sub"
            nested_sub.mkdir(parents=True, exist_ok=True)
            inside = real_parent / "inside.txt"
            inside.write_text("inside parent", encoding="utf-8")
            nested_inside = nested_sub / "nested.txt"
            nested_inside.write_text("inside nested", encoding="utf-8")
            sym_dir = base / "sym_dir"
            sym_dir.symlink_to(real_parent)
            with self.assertRaises(ValueError):
                bridge.transfer_file("nick", sym_dir / "inside.txt")
            with self.assertRaises(ValueError):
                bridge.transfer_file("nick", sym_dir / "sub" / "nested.txt")
            cwd_before = Path.cwd()
            try:
                os.chdir(base)
                with self.assertRaises(ValueError):
                    bridge.transfer_file("nick", Path("sym_dir") / "inside.txt")
            finally:
                os.chdir(cwd_before)

            sym_ok = bridge.transfer_file("nick", sym_dir / "inside.txt", allow_symlinks=True)
            self.assertTrue(sym_ok["ok"])
            self.assertEqual(sym_ok["bytes"], len("inside parent"))

            # Size limit rejected both pre-flight and mid-copy inside _stage_transfer_file
            big = base / "big.bin"
            big.write_bytes(b"A" * 128)
            with self.assertRaises(ValueError):
                bridge.transfer_file("nick", big, max_bytes=64)

            staged_dst = bridge.nick_to_zoe / "big.bin"
            with self.assertRaises(ValueError):
                bridge._stage_transfer_file(big, staged_dst, max_bytes=64)
            self.assertFalse(staged_dst.exists())
            self.assertEqual(list(bridge.bridge_dir.glob(".xfer.*.tmp")), [])

            with self.assertRaises(ValueError):
                bridge._stage_transfer_file(link, bridge.nick_to_zoe / "link.txt", allow_symlinks=False)

            # Directory destination rejected
            dir_clash = bridge.nick_to_zoe / "clash.txt"
            dir_clash.mkdir(parents=True, exist_ok=True)
            src_clash = base / "clash.txt"
            src_clash.write_text("cannot overwrite dir", encoding="utf-8")
            with self.assertRaises(ValueError):
                bridge.transfer_file("nick", src_clash)

            # Valid transfer succeeds and verify_audit_chain detects tampering
            receipt = bridge.transfer_file("nick", target)
            self.assertTrue(receipt["ok"])
            self.assertEqual(receipt["bytes"], len("real data"))
            chain = bridge.verify_audit_chain()
            self.assertTrue(chain["valid"])
            self.assertGreaterEqual(chain["entries"], 3)

            lines = bridge.audit_path.read_text(encoding="utf-8").splitlines()
            rec = json.loads(lines[0])
            rec["event"] = "tampered"
            lines[0] = json.dumps(rec, sort_keys=True)
            bridge.audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tampered_chain = bridge.verify_audit_chain()
            self.assertFalse(tampered_chain["valid"])
            self.assertEqual(tampered_chain["error_index"], 0)

    def test_shm_slot_bounds_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uma-slot-") as td:
            base = Path(td)
            bridge = UmaBridge(base / "uma", shm_path=base / "uma.shm")
            bridge.ensure_initialized()

            for bad_slot in (True, False, None, "0", 1.5):
                with self.assertRaises(ValueError):
                    bridge.write_shm_heartbeat("test", {"ok": True}, slot=bad_slot)  # type: ignore[arg-type]
                with self.assertRaises(ValueError):
                    bridge.read_shm_heartbeat(slot=bad_slot)  # type: ignore[arg-type]

            # Out-of-range integer slots clamp to [0, UMA_MAX_SLOTS - 1]
            self.assertTrue(bridge.write_shm_heartbeat("clamp-low-neg5", {"ok": True}, slot=-5))
            hb0 = bridge.read_shm_heartbeat(slot=0)
            self.assertIsNotNone(hb0)
            self.assertEqual(hb0["side"], "clamp-low-neg5")

            self.assertTrue(bridge.write_shm_heartbeat("clamp-low-neg1", {"ok": True}, slot=-1))
            hb0_neg1 = bridge.read_shm_heartbeat(slot=-1)
            self.assertIsNotNone(hb0_neg1)
            self.assertEqual(hb0_neg1["side"], "clamp-low-neg1")

            self.assertTrue(bridge.write_shm_heartbeat("clamp-high-max", {"ok": True}, slot=UMA_MAX_SLOTS))
            hb7_max = bridge.read_shm_heartbeat(slot=UMA_MAX_SLOTS - 1)
            self.assertIsNotNone(hb7_max)
            self.assertEqual(hb7_max["side"], "clamp-high-max")

            self.assertTrue(bridge.write_shm_heartbeat("clamp-high-99", {"ok": True}, slot=99))
            hb7_99 = bridge.read_shm_heartbeat(slot=UMA_MAX_SLOTS - 1)
            self.assertIsNotNone(hb7_99)
            self.assertEqual(hb7_99["side"], "clamp-high-99")

    def test_chat_store_non_mutating_init_and_cross_surface_uma_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="uma-chat-bridge-") as td:
            base = Path(td)
            chat_dir = base / "chat_state"
            store = ChatStore(chat_dir)
            self.assertFalse((chat_dir / "session.json").exists())
            self.assertFalse((chat_dir / "research.sqlite").exists())
            self.assertEqual(store.memory.export()["sources"], [])
            self.assertFalse((chat_dir / "research.sqlite").exists())

            store.save()
            self.assertTrue((chat_dir / "session.json").is_file())
            ro_store = ChatStore(state_path=store.session_path, read_only=True)
            with self.assertRaises(PermissionError):
                ro_store.save()
            with self.assertRaises(PermissionError):
                ro_store.memory.add_source("x", "y")

            uma_dir = base / "uma_env"
            uma_shm = base / "uma_env.shm"
            with mock.patch.dict(os.environ, {"ZOE_UMA_DIR": str(uma_dir), "ZOE_UMA_SHM": str(uma_shm)}):
                chat = ZoeChat(REPO_ROOT, chat_dir)
                cli = LumeCli(chat, REPO_ROOT, color=False, brain_state=base / "brain")
                _keep1, chat_out = chat.handle("uma status")
                _keep2, cli_lines = cli.handle_slash("/uma status", color=False)
                self.assertIn("PRIVATE", chat_out)
                self.assertIn("PRIVATE", "\n".join(cli_lines or []))
                self.assertFalse((uma_dir / "uma_state.json").exists())


if __name__ == "__main__":
    unittest.main()

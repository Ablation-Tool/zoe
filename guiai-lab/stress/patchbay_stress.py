from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

from guiai.gem.acceptance import load_plan, load_acceptance, run_acceptance, save_acceptance
from guiai.gem.atlas import default_document
from guiai.gem.capsule import _digest, generate_keypair, sign_capsule, verify_capsule
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.patchbay import (
    export_patchbay, inspect_artifact,
    inspect_source, inspect_uimage, inspect_zip, media_gallery, parse_bitstream,
    parse_catalog, parse_ihex, patchbay_scene,
)
from guiai.gem.patchbay_view import main as patchbay_main
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


CERN = Path("/media/cowboy/research/CERN")
A1396 = CERN / "firmware/edms-downloads/edms_1074819.hex"
A1535 = CERN / "firmware/edms-downloads/edms_1074820.hex"
BIT = CERN / "fw/itsdaq/nexysv_itsdaq_vb675_FSC_STAR.bit"
ZIP = CERN / "firmware/FPGA/control-988866/control_fpga_firmware_stage090623.zip"
EMP = CERN / "fw/emp/BOOT.BIN"
FIT = CERN / "fw/emp/sdcard.bak/bootpart/image.ub"
TIMING = CERN / "analysis/felix-flx155/findings.json"
BOOK = Path("/home/cowboy/captures/build-a-llm/011_chapter-3.html")


def ihex_record(offset, kind, payload):
    raw = bytes([len(payload)]) + offset.to_bytes(2, "big") + bytes([kind]) + payload
    return ":" + (raw + bytes([-sum(raw) & 0xFF])).hex().upper()


def make_ihex(path):
    path.write_text("\n".join((ihex_record(0, 4, b"\x00\x02"), ihex_record(0, 0, b"\x01\x02"), ihex_record(0, 1, b""))) + "\n", encoding="ascii")


def make_uimage(path):
    payload = b"Zoe synthetic boot payload"
    header = struct.pack(">7I4B32s", 0x27051956, 0, 1700000000, len(payload), 0x80000, 0x80000, zlib.crc32(payload), 5, 2, 4, 0, b"zoe-test\0")
    checksum = zlib.crc32(header) & 0xFFFFFFFF
    path.write_bytes(header[:4] + struct.pack(">I", checksum) + header[8:] + payload)


def make_plan(directory, argv, hardware_write=False, timeout=2, expected=0, name="synthetic-check"):
    root = Path(directory)
    (root / "firmware.bin").write_bytes(b"synthetic acceptance artifact")
    steps = [{"name": name, "argv": argv, "timeout_seconds": timeout, "expected_exit": expected, "hardware_write": hardware_write, "cwd": "."}]
    path = root / "plan.json"
    path.write_text(json.dumps({"schema_version": 1, "instrument": "zoe-patchbay-acceptance", "target": "synthetic-target", "firmware": "firmware.bin", "steps": steps}), encoding="utf-8")
    return path


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class PatchbayArtifactCase(unittest.TestCase):
    def test_demo_boards_exports_and_default_document(self):
        for board in ("genesys2", "nexys-video"):
            scene, report = patchbay_scene(board=board)
            self.assertEqual(report["board"], board)
            self.assertFalse(report["hardware_accessed"])
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        scene, _ = default_document("patchbay")
        self.assertTrue(verify(scene).passed)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("svg", "png", "gem"):
                path = Path(directory) / f"patchbay.{suffix}"
                self.assertEqual(export_patchbay(path), path)
                self.assertGreater(path.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_patchbay(path)
        with self.assertRaises(ValueError):
            patchbay_scene(board="unknown")

    def test_ihex_valid_and_strict_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hex"
            make_ihex(path)
            report = parse_ihex(path)
            self.assertEqual(report["data_bytes"], 2)
            self.assertEqual(report["spans"], [[0x20000, 0x20002]])
            self.assertIsNone(report["start_address"])
            self.assertTrue(report["checksums_valid"])
            invalid = [
                ":" + "00",
                ihex_record(0, 0, b"\x01"),
                ihex_record(0, 0, b"\x01") + "\n" + ihex_record(0, 6, b"") + "\n" + ihex_record(0, 1, b""),
                ihex_record(0, 0, b"\x01") + "\n" + ihex_record(0, 0, b"\x02") + "\n" + ihex_record(0, 1, b""),
                ihex_record(0, 1, b"") + "\n" + ihex_record(0, 0, b"\x01"),
            ]
            for text in invalid:
                path.write_text(text, encoding="ascii")
                with self.assertRaises(ValueError):
                    parse_ihex(path)
            path.write_text(ihex_record(0, 0, b"\x01")[:-2] + "00\n" + ihex_record(0, 1, b""), encoding="ascii")
            with self.assertRaises(ValueError):
                parse_ihex(path)

    def test_uimage_crc_and_bad_magic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.ub"
            make_uimage(path)
            report = inspect_uimage(path)
            self.assertEqual(report["format"], "U-Boot legacy image")
            self.assertEqual(report["name"], "zoe-test")
            self.assertEqual(report["image_type"], 4)
            self.assertTrue(report["header_crc_valid"])
            self.assertTrue(report["payload_crc_valid"])
            self.assertFalse(report["crc_is_authentication"])
            path.write_bytes(b"not-a-boot-image")
            with self.assertRaises(ValueError):
                inspect_uimage(path)

    def test_source_inventory_catalog_and_archive_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "top.vhd").write_text("entity top is end top;", encoding="utf-8")
            report = inspect_source(root)
            self.assertEqual(report["source_files"], 1)
            self.assertEqual(report["revision"], "not-a-git-checkout")
            self.assertEqual(report["submodule_state"], "not-inspected")
            self.assertFalse(report["payloads_executed"])
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("../escape.vhd", "entity escape is end escape;")
            with self.assertRaisesRegex(ValueError, "unsafe ZIP"):
                inspect_zip(archive)
        rows = parse_catalog('<a href="nexysv_itsdaq_F2V_TTCEMU_AIDATLU_latest.bit">latest</a><a href="genesys2_itsdaq_LPGBT_S4_vc6c8.bit">version</a><a href="../">parent</a>')
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["latest_alias"])
        self.assertEqual(rows[0]["revision"], None)
        self.assertEqual(rows[1]["revision"], "vc6c8")
        self.assertFalse(rows[1]["byte_equality_proven"])
        with self.assertRaises(ValueError):
            parse_catalog('<a href="file.bit">file</a>', "http://example.invalid/firmware/")

    def test_cli_and_forwarded_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(patchbay_main(["scene", "--output", str(root / "direct.svg")]), 0)
                self.assertEqual(gem_main(["patchbay", "scene", "--output", str(root / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["patchbay", "scene", "--output", str(root / "zoe.svg")]), 0)
            for name in ("direct.svg", "gem.svg", "zoe.svg"):
                self.assertIn("Zoe Patchbay", (root / name).read_text(encoding="utf-8"))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(patchbay_main(["scene", str(root / "missing.hex"), "--output", str(root / "error.svg")]), 2)
            self.assertFalse((root / "error.svg").exists())


@unittest.skipUnless(CERN.is_dir(), "optional local CERN evidence is unavailable")
class CernArtifactCase(unittest.TestCase):
    def test_real_ihex_bitstream_and_source_archive(self):
        first = inspect_artifact(A1396)
        second = inspect_artifact(A1535)
        self.assertEqual(first["data_bytes"], 49656)
        self.assertEqual(second["data_bytes"], 87010)
        self.assertEqual(first["sha256"], "aecc6f5dd161c544129a266fb5f817d6c731dcf09ff9e6b06e6c818ebd24192a")
        self.assertFalse(first["bootloader_included"])
        bit = parse_bitstream(BIT)
        self.assertEqual(bit["part"], "7a200tsbg484")
        self.assertTrue(bit["design"].startswith("itsdaq_top"))
        self.assertIsNotNone(bit["sync_word_offset"])
        self.assertFalse(bit["header_is_signature"])
        archive = inspect_artifact(ZIP)
        self.assertEqual(archive["entries"], 20)
        self.assertTrue(any(name.endswith("control_fpga_top.vhd") for name in archive["top_level_candidates"]))
        self.assertFalse(archive["payloads_executed"])

    def test_real_source_inventory(self):
        report = inspect_source(CERN / "source/firmware")
        self.assertEqual(report["revision"], "449b67271229891f0fb5f38dbfc26fde3beb8b4c")
        self.assertEqual(report["source_files"], 1120)
        self.assertEqual(report["source_bytes"], 111779133)
        self.assertEqual(report["dirty_scope"], "tracked-files-only-submodules-and-untracked-ignored")
        self.assertFalse(report["payloads_executed"])

    @unittest.skipUnless(shutil.which("fdtget"), "FIT inspection requires fdtget")
    def test_real_boot_containers_and_timing(self):
        report = inspect_artifact(EMP)
        self.assertEqual(report["sha256"], "2180132bc26fa1d42d4f7174ad7316f32c9b26cd49d382f30bb5dcd0241c38ec")
        self.assertEqual(report["images"], 5)
        self.assertEqual(len(report["partitions"]), 5)
        self.assertEqual([partition["destination_device"] for partition in report["partitions"]], ["PS", "PL", "PS", "PS", "PS"])
        self.assertTrue(report["all_partitions_unencrypted"])
        self.assertTrue(report["all_partitions_unauthenticated"])
        fit = inspect_artifact(FIT)
        self.assertEqual(fit["kind"], "fit-image")
        self.assertEqual([image["name"] for image in fit["images"]], ["kernel@1", "fdt@system-top.dtb"])
        self.assertEqual(fit["images"][0]["compression"], "gzip")
        self.assertFalse(fit["signature_present"])
        timing = inspect_artifact(TIMING)
        self.assertEqual(timing["wns_ns"], -0.096)
        self.assertFalse(timing["timing_met"])
        self.assertFalse(timing["analog_timing_validated"])

    def test_local_media_gallery(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "gallery.html"
            path, report = media_gallery(CERN, output)
            self.assertEqual(path, output)
            self.assertGreater(report["images"], 50)
            self.assertGreater(report["videos"], 0)
            self.assertGreaterEqual(report["pict_images"], 1)
            self.assertFalse(report["autoplay"])
            text = output.read_text(encoding="utf-8")
            self.assertIn("PICT image with a misleading filename extension", text)
            self.assertIn("Every strand gets a hash", text)
            self.assertIn('<video controls preload="none"', text)
            self.assertNotIn("autoplay=", text)
            self.assertIn("no autoplay", text)
            self.assertNotIn("https://", text)


@unittest.skipUnless(shutil.which("openssl"), "update capsules require OpenSSL")
class CapsuleCase(unittest.TestCase):
    def test_sign_verify_trust_tamper_and_wrong_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "firmware.bin"
            artifact.write_bytes(b"new Zoe update, not an original recovered bootloader")
            private, public, fingerprint = generate_keypair(root / "private.pem", root / "public.pem")
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
            capsule, report = sign_capsule(artifact, private, public, "synthetic-target", root / "capsule.json", created_at="2026-11-06T00:00:00+00:00")
            self.assertTrue(report["authenticity_established"])
            self.assertEqual(report["public_key_sha256"] if "public_key_sha256" in report else fingerprint, fingerprint)
            self.assertTrue(verify_capsule(capsule, artifact, public)["authenticity_established"])
            self.assertFalse(verify_capsule(capsule)["authenticity_established"])
            other_private, other_public, _ = generate_keypair(root / "other-private.pem", root / "other-public.pem")
            self.assertFalse(verify_capsule(capsule, artifact, other_public)["authenticity_established"])
            artifact.write_bytes(b"different bytes")
            changed = verify_capsule(capsule, artifact, public)
            self.assertTrue(changed["signature_valid"])
            self.assertFalse(changed["artifact_match"])
            self.assertFalse(changed["authenticity_established"])
            document = json.loads(capsule.read_text(encoding="utf-8"))
            document["signature"] = base64.b64encode(bytes(64)).decode("ascii")
            document["digest"] = _digest({key: value for key, value in document.items() if key != "digest"})
            capsule.write_text(json.dumps(document), encoding="utf-8")
            self.assertFalse(verify_capsule(capsule)["signature_valid"])
            with self.assertRaises(ValueError):
                sign_capsule(artifact, other_private, public, "target", root / "mismatch.json")


class AcceptanceCase(unittest.TestCase):
    def test_dry_run_execution_and_report_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, [sys.executable, "-c", "from pathlib import Path; Path('ran.txt').write_text('done')"])
            dry = run_acceptance(plan)
            self.assertFalse(dry["executed"])
            self.assertIsNone(dry["accepted"])
            self.assertFalse((Path(directory) / "ran.txt").exists())
            result = run_acceptance(plan, execute=True)
            self.assertTrue(result["accepted"])
            self.assertIsNone(result["hardware_accessed"])
            self.assertFalse(result["hardware_behavior_proven"])
            self.assertEqual(result["steps"][0]["argv"][0], sys.executable)
            output = Path(directory) / "result.json"
            save_acceptance(result, output)
            self.assertEqual(load_acceptance(output)["accepted"], True)
            with self.assertRaises(FileExistsError):
                save_acceptance(result, output)
            document = json.loads(output.read_text(encoding="utf-8"))
            document["accepted"] = False
            output.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_acceptance(output)

    def test_hardware_write_gate_and_failure_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, "-c", "from pathlib import Path; Path('write.txt').write_text('local test')"]
            plan = make_plan(directory, command, hardware_write=True)
            with self.assertRaisesRegex(ValueError, "allow-hardware-write"):
                run_acceptance(plan, execute=True)
            self.assertFalse((Path(directory) / "write.txt").exists())
            result = run_acceptance(plan, execute=True, allow_hardware_write=True)
            self.assertTrue(result["accepted"])
            self.assertTrue(result["hardware_write_requested"])
            self.assertIsNone(result["hardware_accessed"])
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, [sys.executable, "-c", "raise SystemExit(3)"])
            result = run_acceptance(plan, execute=True)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["steps"][0]["returncode"], 3)

    def test_timeout_and_bounded_output(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1)
            result = run_acceptance(plan, execute=True)
            self.assertFalse(result["accepted"])
            self.assertTrue(result["steps"][0]["timed_out"])
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, [sys.executable, "-c", "print('x' * 70000)"])
            result = run_acceptance(plan, execute=True)
            self.assertTrue(result["accepted"])
            self.assertEqual(len(result["steps"][0]["stdout"]), 65536)
            self.assertTrue(result["steps"][0]["output_truncated"])

    def test_plan_rejections_and_missing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, ["echo", "ok"])
            document = json.loads(plan.read_text(encoding="utf-8"))
            document["steps"][0]["argv"] = "echo ok"
            plan.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan(plan)
            document["steps"][0]["argv"] = ["echo"]
            document["steps"][0]["cwd"] = None
            plan.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan(plan)
        with tempfile.TemporaryDirectory() as directory:
            plan = make_plan(directory, ["/definitely/not/a/zoe-command"])
            result = run_acceptance(plan, execute=True)
            self.assertFalse(result["accepted"])
            self.assertIsNone(result["steps"][0]["returncode"])


@unittest.skipUnless(HAS_GTK, "native Patchbay tests require GTK, Cairo, and an X11 DISPLAY")
class PatchbayNativeCase(unittest.TestCase):
    def test_artifact_cog_plan_and_export(self):
        window = AtlasWindow("patchbay")
        try:
            original = window.patchbay_report
            window.controls["patchbay_board"].set_active_id("nexys-video")
            self.assertEqual(window.report["board"], "nexys-video")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                artifact = root / "sample.hex"
                make_ihex(artifact)
                window.controls["patchbay_artifact"].set_text(str(artifact))
                self.assertIs(window.patchbay_report, original)
                window.load_patchbay_artifact()
                self.assertEqual(window.patchbay_report["kind"], "intel-hex-application")
                loaded = window.patchbay_report
                scene = window.scene
                window.controls["patchbay_artifact"].set_text(str(root / "missing.hex"))
                window.load_patchbay_artifact()
                self.assertIs(window.patchbay_report, loaded)
                self.assertIs(window.scene, scene)
                self.assertIn("Firmware inspection failed", window.summary.get_text())
                source = BOOK if BOOK.is_file() else root / "cog.txt"
                if not source.exists():
                    source.write_text("inspect the artifact before the next test .", encoding="utf-8")
                window.controls["patchbay_cog_path"].set_text(str(source))
                window.controls["patchbay_prompt"].set_text("attention")
                window.train_patchbay_cog()
                self.assertGreater(window.cog.total_tokens, 0)
                self.assertEqual(window.controls["patchbay_cog_path"].get_text(), str(source))
                self.assertEqual(window.controls["patchbay_prompt"].get_text(), "attention")
                self.assertEqual(window.cog_report["forward"]["tokens"][0], "attention")
                window.controls["patchbay_prompt"].set_text("inspect")
                window.walk_patchbay_cog()
                self.assertIn("Backward:", window.summary.get_text())
                plan = make_plan(root, [sys.executable, "-c", "from pathlib import Path; Path('native-ran.txt').write_text('bad')"])
                window.controls["patchbay_plan"].set_text(str(plan))
                window.validate_patchbay_plan()
                self.assertIn("Executed=False", window.summary.get_text())
                self.assertFalse((root / "native-ran.txt").exists())
                window.refresh()
                output = window.export_current(root / "native.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

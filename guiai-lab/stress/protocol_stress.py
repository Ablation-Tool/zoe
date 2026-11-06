from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.protocol_lab import (
    amac_demo_replies, amac_read_next, amac_read_reply, decode_amac_reply,
    decode_specs_frame, encode_specs_frame, export_protocol, first_header_byte,
    header_checksum, is_long_read_count, payload_checksum, protocol_scene,
    reported_read_count,
)
from guiai.gem.protocol_view import main as protocol_main
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class ProtocolModelCase(unittest.TestCase):
    def test_specs_reference_frame_and_strict_rejections(self):
        self.assertEqual(first_header_byte(0x15, "i2c"), 0x54)
        self.assertEqual(first_header_byte(0x15, "jtag"), 0x55)
        self.assertEqual(first_header_byte(0x3F, "register"), 0xFF)
        header = [0x55, 0x02, 0x01]
        payload = [0xDE, 0xAD, 0xBE, 0xEF]
        self.assertEqual(header_checksum([*header, 0]), 0x03)
        self.assertEqual(payload_checksum(payload), 0x22)
        words = encode_specs_frame(header, payload)
        self.assertEqual(" ".join(f"{word['value']:02X}" for word in words), "55 02 01 03 DE AD BE EF 22")
        self.assertEqual([index for index, word in enumerate(words) if word["last"]], [7])
        self.assertEqual(decode_specs_frame(words), (header, payload))
        self.assertEqual(decode_specs_frame(encode_specs_frame(header, [])), (header, []))
        with self.assertRaisesRegex(ValueError, "header checksum"):
            corrupted = [dict(word) for word in words]
            corrupted[3]["value"] ^= 1
            decode_specs_frame(corrupted)
        with self.assertRaisesRegex(ValueError, "payload checksum"):
            corrupted = [dict(word) for word in words]
            corrupted[-1]["value"] ^= 1
            decode_specs_frame(corrupted)
        with self.assertRaisesRegex(ValueError, "ninth-bit"):
            corrupted = [dict(word) for word in words]
            corrupted[2]["last"] = True
            decode_specs_frame(corrupted)
        with self.assertRaisesRegex(ValueError, "ninth-bit"):
            corrupted = [dict(word) for word in words]
            corrupted[7]["last"] = False
            decode_specs_frame(corrupted)
        with self.assertRaises(ValueError):
            decode_specs_frame(words[:4])
        with self.assertRaises(ValueError):
            decode_specs_frame([{"value": 0x55, "last": False, "unexpected": 0}, *words[1:]])
        with self.assertRaises(ValueError):
            encode_specs_frame([0x55, 0x100, 0x01], payload)
        with self.assertRaises(ValueError):
            encode_specs_frame(header, [0] * 256)
        with self.assertRaises(ValueError):
            first_header_byte(64, "i2c")
        with self.assertRaises(ValueError):
            first_header_byte(1, 4)
        with self.assertRaises(ValueError):
            first_header_byte(1, True)
        with self.assertRaises(ValueError):
            first_header_byte(1, ["i2c"])

    def test_every_count_and_amac_sequence_wrap(self):
        for count in range(256):
            self.assertEqual(is_long_read_count(count), count > 128)
            self.assertEqual(reported_read_count(count), count & 0x7F)
        self.assertFalse(is_long_read_count(128))
        self.assertEqual(reported_read_count(128), 0)
        self.assertTrue(is_long_read_count(129))
        self.assertEqual(reported_read_count(129), 1)
        for count in (-1, 256, True):
            with self.assertRaises(ValueError):
                is_long_read_count(count)
            with self.assertRaises(ValueError):
                reported_read_count(count)
        reply = amac_read_reply(0x15, 3, 0x41, 0x12345678)
        self.assertEqual(reply, [0xAB, 0x41, 0x12, 0x34, 0x56, 0x78])
        self.assertEqual(decode_amac_reply(reply), {"id": 0x15, "sequence": 3, "address": 0x41, "data": 0x12345678, "hex": "AB4112345678"})
        self.assertEqual(decode_amac_reply([0xA9]), {"id": 0x15, "sequence": 1, "hex": "A9"})
        self.assertEqual(amac_read_next(0x50, 0xFFFFFFF0, 7), (0x51, 0xFFFFFFF0, 0))
        self.assertEqual(amac_read_next(0xFF, 1, 7), (0, 1, 0))
        self.assertEqual([bytes(reply).hex().upper() for reply in amac_demo_replies()], ["AF50FFFFFFF0", "A851FFFFFFF1", "A952FFFFFFF2"])
        with self.assertRaises(ValueError):
            amac_read_reply(0x15, 8, 0x41, 0)
        with self.assertRaises(ValueError):
            amac_read_reply(0x15, 0, 0x41, 0x100000000)
        with self.assertRaises(ValueError):
            decode_amac_reply([0xA9, 0x41])

    def test_scene_exports_and_cli(self):
        for count in (0, 127, 128, 129, 255):
            scene, report = protocol_scene(count)
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
            self.assertEqual(report["long"], count > 128)
            self.assertEqual(report["reported"], count & 0x7F)
            self.assertEqual(report["ninth_bit_index"], 7)
            self.assertEqual(report["read_next_hex"], ["AF50FFFFFFF0", "A851FFFFFFF1", "A952FFFFFFF2"])
            self.assertFalse(report["hardware_accessed"])
            self.assertFalse(report["checksum_is_authentication"])
        scene, _ = default_document("protocol")
        self.assertTrue(verify(scene).passed)
        with self.assertRaises(ValueError):
            protocol_scene(-1)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("svg", "png", "gem"):
                output = Path(directory) / f"protocol.{suffix}"
                self.assertEqual(export_protocol(output), output)
                self.assertGreater(output.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    export_protocol(output)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(protocol_main(["--count", "0x81", "--output", str(Path(directory) / "direct.svg")]), 0)
                self.assertEqual(gem_main(["protocol", "--output", str(Path(directory) / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["protocol", "--output", str(Path(directory) / "zoe.svg")]), 0)
            self.assertIn("129 is long", (Path(directory) / "direct.svg").read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_GTK, "native protocol tests require GTK, Cairo, and an X11 DISPLAY")
class ProtocolNativeCase(unittest.TestCase):
    def test_read_count_control_and_export(self):
        window = AtlasWindow("protocol")
        try:
            self.assertEqual(window.report["read_count"], 128)
            self.assertFalse(window.report["long"])
            window.controls["read_count"].set_value(129)
            self.assertTrue(window.report["long"])
            self.assertEqual(window.report["reported"], 1)
            self.assertIn("no hardware command", window.summary.get_text())
            with tempfile.TemporaryDirectory() as directory:
                output = window.export_current(Path(directory) / "protocol.svg")
                self.assertTrue(output.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()

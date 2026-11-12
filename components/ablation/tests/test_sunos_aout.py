import hashlib
import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
from contextlib import redirect_stdout

from ablation.sunos import AoutError, parse_aout, read_aout, render_calls
from ablation.sunos.cli import main


IBM_RE = Path(os.environ.get("IBM_RE", "/media/cowboy/research/IBM-RE"))
SYBASE = IBM_RE / "analysis/Lotus123/88a7ce88f9d1ead0/20261107T001439Z-protocol/input/sybase"


def synthetic_image():
    header = struct.pack(">8I", 0x01030107, 8, 0, 0, 24, 0, 24, 0)
    text = struct.pack(">II", 0x40000000, 0x40000000)
    internal = struct.pack(">III", 0, 0x406, 0x100)
    external = struct.pack(">III", 4, (1 << 8) | 0x86, 0xFFFFFFFC)
    symbols = struct.pack(">IBBhI", 0, 0, 0, 0, 0) + struct.pack(">IBBhI", 1, 1, 0, 0, 0)
    return header + text + internal + external + symbols + b"\0_strlen\0"


class AoutValidationTests(unittest.TestCase):
    def test_internal_external_and_unrelocated_calls(self):
        image = parse_aout(synthetic_image())
        calls = image.calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].target, 0x2100)
        self.assertEqual(calls[1].external_symbol, "_strlen")
        self.assertIsNone(calls[1].target)
        self.assertEqual(image.header.symbol_size, 24)
        self.assertEqual(len(image.relocations), 2)
        self.assertIn("0x2000 -> 0x2100", render_calls(image))
        self.assertIn("0x2004 -> _strlen", render_calls(image))

    def test_rejects_bad_magic_truncation_and_duplicate_relocations(self):
        with self.assertRaises(AoutError):
            parse_aout(b"")
        with self.assertRaises(AoutError):
            parse_aout(b"\0" * 32)
        with self.assertRaises(AoutError):
            parse_aout(synthetic_image()[:-1])
        raw = bytearray(synthetic_image())
        struct.pack_into(">I", raw, 52, 0)
        with self.assertRaisesRegex(AoutError, "duplicate text relocation"):
            parse_aout(bytes(raw)).calls()

    def test_rejects_invalid_relocation_and_external_symbol(self):
        raw = bytearray(synthetic_image())
        struct.pack_into(">I", raw, 56, 0x402)
        with self.assertRaisesRegex(AoutError, "unsupported direct-call relocation"):
            parse_aout(bytes(raw)).calls()
        raw = bytearray(synthetic_image())
        struct.pack_into(">I", raw, 84, 1)
        with self.assertRaisesRegex(AoutError, "not undefined"):
            parse_aout(bytes(raw)).calls()

    def test_cli_and_hash(self):
        raw = synthetic_image()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(raw)
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["info", str(path), "--json"]), 0)
                self.assertEqual(main(["render", str(path)]), 0)
            self.assertIn("0x2000 -> 0x2100", output.getvalue())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), parse_aout(raw).sha256)


@unittest.skipUnless(SYBASE.is_file(), "Sybase corpus unavailable")
class SybaseCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = read_aout(SYBASE)

    def test_real_layout_and_corrected_calls(self):
        self.assertEqual(self.image.sha256, "88a7ce88f9d1ead09508d0b01e636616d14442c98f4c74171d468680e73a5cce")
        self.assertEqual(len(self.image.symbols), 1417)
        self.assertEqual(len(self.image.relocations), 5800)
        calls = {item.address: item for item in self.image.calls()}
        self.assertEqual(calls[0xB1B0].target, 0xF624)
        self.assertEqual(calls[0xB270].target, 0x2998)
        self.assertEqual(calls[0xB31C].target, 0xD0D8)
        self.assertTrue(any(item.external_symbol == "_strlen" for item in calls.values()))
        self.assertTrue(any(item.target == 0xA428 for item in calls.values()))

    def test_real_cli_and_render(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["info", str(SYBASE), "--json"]), 0)
            self.assertEqual(main(["calls", str(SYBASE), "--target", "0xf624", "--json"]), 0)
            self.assertEqual(main(["render", str(SYBASE), "--target", "0xf624"]), 0)
        self.assertIn("0xb1b0 -> 0xf624", output.getvalue())


if __name__ == "__main__":
    unittest.main()

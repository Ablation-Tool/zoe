import base64
import os
import stat
import tempfile
import unittest
from pathlib import Path

import gemseal


class GemSealTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.key = bytes(range(32))
        self.addCleanup(self.temporary.cleanup)

    def make_plaintext(self, name="plain.bin", size=10000):
        source = self.root / name
        source.write_bytes(bytes((i * 37) % 256 for i in range(size)))
        return source

    def test_round_trip_and_randomized_containers(self):
        source = self.make_plaintext()
        first = self.root / "first.gemseal"
        second = self.root / "second.gemseal"
        restored = self.root / "restored.bin"
        gemseal.encrypt_file(self.key, source, first, chunk_size=1024)
        gemseal.encrypt_file(self.key, source, second, chunk_size=1024)
        self.assertNotEqual(first.read_bytes(), second.read_bytes())
        gemseal.decrypt_file(self.key, first, restored)
        self.assertEqual(restored.read_bytes(), source.read_bytes())

    def test_empty_and_exact_chunk_round_trips(self):
        for name, size in [("empty", 0), ("exact", 8192)]:
            with self.subTest(name=name):
                source = self.make_plaintext(f"{name}.bin", size)
                sealed = self.root / f"{name}.gemseal"
                restored = self.root / f"{name}.restored"
                gemseal.encrypt_file(self.key, source, sealed, chunk_size=1024)
                gemseal.decrypt_file(self.key, sealed, restored)
                self.assertEqual(restored.read_bytes(), source.read_bytes())

    def test_invalid_inputs_do_not_publish(self):
        source = self.make_plaintext()
        sealed = self.root / "sealed.gemseal"
        gemseal.encrypt_file(self.key, source, sealed, chunk_size=1024)
        original = sealed.read_bytes()
        changed = bytearray(original)
        changed[gemseal.HEADER.size + gemseal.RECORD.size + 5] ^= 1
        record_size = gemseal.RECORD.size + 1024 + gemseal.TAG_SIZE
        first = gemseal.HEADER.size
        second = first + record_size
        variants = {
            "tampered": bytes(changed),
            "truncated": original[:-1],
            "trailing": original + b"X",
            "reordered": (
                original[:first]
                + original[second : second + record_size]
                + original[first:second]
                + original[second + record_size :]
            ),
        }
        for name, content in variants.items():
            with self.subTest(name=name):
                candidate = self.root / f"{name}.gemseal"
                candidate.write_bytes(content)
                destination = self.root / f"{name}.out"
                with self.assertRaises(gemseal.GemSealError):
                    gemseal.decrypt_file(self.key, candidate, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(list(self.root.glob(f".{name}.out.*.tmp")), [])

        destination = self.root / "wrong-key.out"
        with self.assertRaises(gemseal.GemSealError):
            gemseal.decrypt_file(bytes(range(1, 33)), sealed, destination)
        self.assertFalse(destination.exists())

    def test_atomic_output_interruption_and_no_overwrite(self):
        destination = self.root / "published"
        with gemseal._atomic_output(destination) as output:
            output.write(b"complete")
            self.assertFalse(destination.exists())
        self.assertEqual(destination.read_bytes(), b"complete")

        interrupted = self.root / "interrupted"
        with self.assertRaises(KeyboardInterrupt):
            with gemseal._atomic_output(interrupted) as output:
                output.write(b"partial")
                raise KeyboardInterrupt
        self.assertFalse(interrupted.exists())
        self.assertEqual(list(self.root.glob(".interrupted.*.tmp")), [])

        destination.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            gemseal.encrypt_file(self.key, self.make_plaintext(), destination)
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_deterministic_vector(self):
        container = (
            "R0VNU0VBTDEBAAEAAQAwAAABAgMEBQYHCAkKCwwNDg8QERITFBUWFwAQAAAAAAAA"
            "AQABABMAAAAAAAMAAAAAAP3eBxRxm6eRP8nLh/BwOe63868CAAEAEAABAAAAAAAA"
            "AAAAQSBHysL8RkaySCG8VwtLCA=="
        )
        sealed = self.root / "vector.gemseal"
        sealed.write_bytes(base64.b64decode(container))
        restored = self.root / "vector.out"
        gemseal.decrypt_file(self.key, sealed, restored)
        self.assertEqual(restored.read_bytes(), b"GEM")

    def test_key_generation_and_chunk_limits(self):
        key_path = self.root / "key.bin"
        gemseal.generate_key(key_path)
        self.assertEqual(len(key_path.read_bytes()), 32)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o600)
        source = self.make_plaintext(size=1)
        for chunk_size in [0, -1, gemseal.MAX_CHUNK_SIZE + 1]:
            with self.subTest(chunk_size=chunk_size):
                with self.assertRaises(gemseal.GemSealError):
                    gemseal.encrypt_file(self.key, source, self.root / "invalid", chunk_size)


if __name__ == "__main__":
    unittest.main()

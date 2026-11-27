import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import gemseal
import gemseal_crack


class CrackerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.plaintext = b"GEMSEAL cracker test plaintext\x00\xff"
        self.addCleanup(self.temporary.cleanup)

    def make_container(self, key, name="container.gemseal", plaintext=None):
        source = self.root / f"{name}.plain"
        source.write_bytes(self.plaintext if plaintext is None else plaintext)
        container = self.root / name
        gemseal.encrypt_file(key, source, container, chunk_size=16)
        return container

    def run_cli(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = gemseal_crack.main(arguments)
        return status, output.getvalue()

    def test_sha256_wordlist_recovers_and_fully_decrypts(self):
        password = b"correct horse"
        container = self.make_container(hashlib.sha256(password).digest())
        wordlist = self.root / "words.txt"
        wordlist.write_bytes(b"first\r\ncorrect horse\nlast\n")
        output = self.root / "recovered.bin"
        status, report = self.run_cli(
            ["wordlist", str(container), str(wordlist), "--output", str(output)]
        )
        self.assertEqual(status, 0, report)
        self.assertIn("candidate=b'correct horse'", report)
        self.assertIn("Full container verified", report)
        self.assertEqual(output.read_bytes(), self.plaintext)

    def test_pin_search_recovers_leading_zero_pin(self):
        container = self.make_container(hashlib.sha256(b"0042").digest())
        output = self.root / "pin-recovered.bin"
        status, report = self.run_cli(
            ["pin", str(container), "--digits", "4", "--output", str(output)]
        )
        self.assertEqual(status, 0, report)
        self.assertIn("candidate=b'0042'", report)
        self.assertEqual(output.read_bytes(), self.plaintext)

    def test_zero_padded_wordlist(self):
        container = self.make_container(b"gem".ljust(32, b"\0"))
        wordlist = self.root / "padded.txt"
        wordlist.write_bytes(b"first\ngem\n")
        status, report = self.run_cli(
            ["wordlist", str(container), str(wordlist), "--mode", "zero-padded"]
        )
        self.assertEqual(status, 0, report)
        self.assertIn("candidate=b'gem'", report)

    def test_raw_prefix_search_and_candidate_limit(self):
        container = self.make_container(b"\x2a" + bytes(31))
        status, report = self.run_cli(
            ["raw-prefix", str(container), "--variable-bytes", "1"]
        )
        self.assertEqual(status, 0, report)
        self.assertIn("Tested 43 keys", report)

        status, report = self.run_cli(
            ["raw-prefix", str(container), "--variable-bytes", "1", "--limit", "16"]
        )
        self.assertEqual(status, 1, report)
        self.assertIn("Tested 16 keys", report)
        self.assertIn("NOT FOUND", report)

    def test_empty_container_end_record_challenge(self):
        password = b"empty"
        container = self.make_container(hashlib.sha256(password).digest(), plaintext=b"")
        challenge = gemseal_crack.load_challenge(container)
        result = gemseal_crack.crack_candidates(challenge, [b"wrong", password])
        self.assertEqual(result.candidate, password)
        self.assertEqual(gemseal_crack.try_candidate(challenge, result.key), b"")

    def test_wrong_candidates_and_tampered_first_record_fail(self):
        password = b"right"
        container = self.make_container(hashlib.sha256(password).digest())
        challenge = gemseal_crack.load_challenge(container)
        result = gemseal_crack.crack_candidates(challenge, [b"wrong", b"also wrong"])
        self.assertIsNone(result.key)
        self.assertEqual(result.tested, 2)

        data = bytearray(container.read_bytes())
        data[gemseal.HEADER.size + gemseal.RECORD.size] ^= 1
        container.write_bytes(data)
        challenge = gemseal_crack.load_challenge(container)
        self.assertIsNone(
            gemseal_crack.try_candidate(challenge, hashlib.sha256(password).digest())
        )

    def test_invalid_candidates_are_counted_as_skipped(self):
        container = self.make_container(hashlib.sha256(b"key").digest())
        challenge = gemseal_crack.load_challenge(container)
        result = gemseal_crack.crack_candidates(
            challenge, [b"short", b"x" * 33], mode="raw"
        )
        self.assertIsNone(result.key)
        self.assertEqual(result.tested, 0)
        self.assertEqual(result.skipped, 2)

    def test_truncated_container_is_rejected(self):
        container = self.make_container(hashlib.sha256(b"key").digest())
        container.write_bytes(container.read_bytes()[:20])
        with self.assertRaises(gemseal_crack.CrackError):
            gemseal_crack.load_challenge(container)


if __name__ == "__main__":
    unittest.main()

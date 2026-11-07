import json
import math
from pathlib import Path
import random
import struct
import unittest

from zoe_cell import MAX_PROBABILITIES, SCALE, decode, encode


FIXTURES = Path(__file__).resolve().parents[2] / "conformance" / "accessible-volume.json"


class ZoeCellTest(unittest.TestCase):
    def test_shared_fixtures(self):
        for case in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]:
            with self.subTest(case=case["name"]):
                encoded = encode(case["probabilities"], case["tau"])
                self.assertEqual(SCALE, sum(encoded.probabilities))
                self.assertEqual(case["accessible"], encoded.accessible)
                response = struct.pack(">4H", encoded.accessible, len(encoded.probabilities) - encoded.accessible, len(encoded.probabilities), encoded.tau) + b"\x90\x00"
                self.assertEqual(len(encoded.probabilities), decode(response).vocabulary_size)

    def test_strict_equality_and_one(self):
        self.assertEqual(1, encode([0.70, 0.20, 0.08, 0.02], 0.20).accessible)
        self.assertEqual(0, encode([0.25] * 4, 1.0).accessible)
        self.assertEqual(1, encode([1.0, 0.0, 0.0], 0.0).accessible)

    def test_deterministic_bounded_vectors(self):
        generator = random.Random(20261107)
        for size in range(1, MAX_PROBABILITIES + 1):
            weights = [generator.random() for _ in range(size)]
            total = math.fsum(weights)
            probabilities = [weight / total for weight in weights]
            encoded = encode(probabilities, generator.random())
            self.assertEqual(SCALE, sum(encoded.probabilities))
            self.assertEqual(5 + 2 + size * 2, len(encoded.apdu))
            self.assertEqual(encoded, encode(probabilities, encoded.tau / SCALE))

    def test_rejects_invalid_input(self):
        invalid = [
            ([], 0.5),
            ([1.0] + [0.0] * 64, 0.5),
            ([0.5, 0.4], 0.5),
            ([float("nan")], 0.5),
            ([1.0], -0.1),
            ([1.0], 1.1),
        ]
        for probabilities, tau in invalid:
            with self.subTest(probabilities=probabilities[:2], size=len(probabilities), tau=tau):
                with self.assertRaises(ValueError):
                    encode(probabilities, tau)

    def test_decodes_real_response_shape(self):
        measurement = decode(struct.pack(">4H", 3, 1, 4, 6554) + b"\x90\x00")
        self.assertEqual((3, 1, 4, 6554), (measurement.accessible, measurement.complement, measurement.vocabulary_size, measurement.tau))

    def test_rejects_malformed_responses(self):
        for response in [b"", b"\x90\x00", b"\x00" * 8 + b"\x6a\x80", struct.pack(">4H", 4, 1, 4, 0) + b"\x90\x00", struct.pack(">4H", 0, 1, 0, 0) + b"\x90\x00"]:
            with self.subTest(response=response.hex()):
                with self.assertRaises(ValueError):
                    decode(response)


if __name__ == "__main__":
    unittest.main()

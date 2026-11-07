from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
import struct
from typing import Iterable

SCALE = 1 << 15
MAX_PROBABILITIES = 64
SUCCESS = 0x9000


@dataclass(frozen=True)
class EncodedMeasurement:
    tau: int
    probabilities: tuple[int, ...]
    apdu: bytes

    @property
    def accessible(self) -> int:
        return sum(probability > self.tau for probability in self.probabilities)


@dataclass(frozen=True)
class Measurement:
    accessible: int
    complement: int
    vocabulary_size: int
    tau: int


def encode(probabilities: Iterable[float], tau: float) -> EncodedMeasurement:
    values = list(probabilities)
    if not 1 <= len(values) <= MAX_PROBABILITIES:
        raise ValueError("distribution must contain 1 to 64 probabilities")
    if not all(isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1 for value in values):
        raise ValueError("probabilities must be finite values between 0 and 1")
    if not isinstance(tau, (int, float)) or not math.isfinite(tau) or not 0 <= tau <= 1:
        raise ValueError("tau must be a finite probability between 0 and 1")
    if abs(math.fsum(values) - 1.0) > 1e-8:
        raise ValueError("probabilities must sum to 1 within 1e-8")

    scaled = [Fraction(str(value)) * SCALE for value in values]
    units = [value.numerator // value.denominator for value in scaled]
    remainder = SCALE - sum(units)
    order = sorted(range(len(values)), key=lambda index: (units[index] - scaled[index], index))
    for index in order[:remainder]:
        units[index] += 1

    threshold = round(Fraction(str(tau)) * SCALE)
    payload = threshold.to_bytes(2, "big") + b"".join(value.to_bytes(2, "big") for value in units)
    command = bytes((0x80, 0x02, 0, 0, len(payload))) + payload
    return EncodedMeasurement(threshold, tuple(units), command)


def decode(response: bytes) -> Measurement:
    if len(response) != 10:
        raise ValueError("a measurement response contains eight data bytes and two status bytes")
    status = int.from_bytes(response[-2:], "big")
    if status != SUCCESS:
        raise ValueError(f"card returned status 0x{status:04x}")
    accessible, complement, size, tau = struct.unpack(">4H", response[:8])
    if not 1 <= size <= MAX_PROBABILITIES or accessible + complement != size:
        raise ValueError("card returned inconsistent counts")
    if tau > SCALE:
        raise ValueError("card returned an invalid threshold")
    return Measurement(accessible, complement, size, tau)

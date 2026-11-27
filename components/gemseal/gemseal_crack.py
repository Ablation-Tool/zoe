#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
import hashlib
import struct
import sys
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from gemseal import GemSealError, decrypt_file

MAGIC = b"GEMSEAL1"
VERSION = 1
SUITE = 1
KDF = 1
DATA_RECORD = 1
END_RECORD = 2
KEY_SIZE = 32
TAG_SIZE = 16
MAX_CHUNK_SIZE = 65535 - TAG_SIZE
FILE_HEADER = struct.Struct("<8sHHHH16s8sII")
RECORD_HEADER = struct.Struct("<HHHIIH")
AAD_CONTEXT = b"GEMSEAL1/record\x00"
KDF_CONTEXT = b"GEMSEAL1/file-key\x00"
ZERO_TAG = bytes(TAG_SIZE)
CANDIDATE_MODES = ("sha256", "zero-padded", "raw")


class CrackError(Exception):
    pass


@dataclass(frozen=True)
class Challenge:
    salt: bytes
    nonce: bytes
    aad: bytes
    sealed: bytes


@dataclass(frozen=True)
class CrackResult:
    candidate: bytes
    key: bytes
    tested: int
    skipped: int
    elapsed: float


def _read_exact(stream, size, description):
    data = stream.read(size)
    if len(data) != size:
        raise CrackError(f"truncated {description}")
    return data


def load_challenge(path):
    with open(path, "rb") as container:
        file_header = _read_exact(container, FILE_HEADER.size, "file header")
        (
            magic,
            version,
            suite,
            kdf,
            header_size,
            salt,
            nonce_prefix,
            chunk_size,
            reserved,
        ) = FILE_HEADER.unpack(file_header)
        if magic != MAGIC or version != VERSION:
            raise CrackError("unsupported GEMSEAL format")
        if suite != SUITE or kdf != KDF:
            raise CrackError("unsupported cryptographic suite")
        if header_size != FILE_HEADER.size or reserved != 0:
            raise CrackError("invalid file header")
        if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
            raise CrackError("invalid chunk size")

        record_header = _read_exact(container, RECORD_HEADER.size, "record header")
        (
            record_type,
            record_suite,
            sealed_size,
            record_index,
            plaintext_size,
            flags,
        ) = RECORD_HEADER.unpack(record_header)
        if record_type not in (DATA_RECORD, END_RECORD):
            raise CrackError("invalid first record type")
        if record_suite != SUITE or flags != 0 or record_index != 0:
            raise CrackError("invalid first record header")
        if plaintext_size > chunk_size or sealed_size != plaintext_size + TAG_SIZE:
            raise CrackError("invalid first record length")
        if record_type == DATA_RECORD and plaintext_size == 0:
            raise CrackError("invalid empty DATA record")
        if record_type == END_RECORD and plaintext_size != 0:
            raise CrackError("invalid END record")

        sealed = _read_exact(container, sealed_size, "first record body")
        return Challenge(
            salt=salt,
            nonce=nonce_prefix + struct.pack("<I", record_index),
            aad=AAD_CONTEXT + file_header + ZERO_TAG + record_header,
            sealed=sealed,
        )


def derive_file_key(master_key, salt):
    if len(master_key) != KEY_SIZE:
        raise CrackError(f"candidate key must contain exactly {KEY_SIZE} bytes")
    return HKDF(
        algorithm=SHA256(),
        length=KEY_SIZE,
        salt=salt,
        info=KDF_CONTEXT,
    ).derive(master_key)


def try_candidate(challenge, master_key):
    aead = ChaCha20Poly1305(derive_file_key(master_key, challenge.salt))
    try:
        return aead.decrypt(challenge.nonce, challenge.sealed, challenge.aad)
    except InvalidTag:
        return None


def transform_candidate(candidate, mode):
    if mode == "sha256":
        return hashlib.sha256(candidate).digest()
    if mode == "zero-padded":
        if len(candidate) <= KEY_SIZE:
            return candidate.ljust(KEY_SIZE, b"\0")
        return None
    if mode == "raw":
        if len(candidate) == KEY_SIZE:
            return candidate
        return None
    raise CrackError(f"unknown candidate mode: {mode}")


def crack_candidates(challenge, candidates, mode="sha256", limit=None):
    if limit is not None and limit < 1:
        raise CrackError("candidate limit must be positive")
    started = time.perf_counter()
    tested = 0
    skipped = 0
    for candidate in candidates:
        if limit is not None and tested >= limit:
            break
        key = transform_candidate(candidate, mode)
        if key is None:
            skipped += 1
            continue
        tested += 1
        if try_candidate(challenge, key) is not None:
            return CrackResult(candidate, key, tested, skipped, time.perf_counter() - started)
    return CrackResult(None, None, tested, skipped, time.perf_counter() - started)


def wordlist_candidates(stream):
    for line in stream:
        yield line.rstrip(b"\r\n")


def pin_candidates(digits, prefix=b"", suffix=b""):
    if not 1 <= digits <= 8:
        raise CrackError("PIN length must be between 1 and 8 digits")
    for number in range(10**digits):
        yield prefix + f"{number:0{digits}d}".encode("ascii") + suffix


def raw_prefix_candidates(variable_bytes):
    if not 1 <= variable_bytes <= 4:
        raise CrackError("variable raw-key prefix must be between 1 and 4 bytes")
    for number in range(256**variable_bytes):
        variable = number.to_bytes(variable_bytes, "little")
        yield variable + bytes(KEY_SIZE - variable_bytes)


def _positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _add_common_options(parser, include_mode=True):
    if include_mode:
        parser.add_argument(
            "--mode",
            choices=CANDIDATE_MODES,
            default="sha256",
            help="candidate-to-master-key transform (default: sha256)",
        )
    parser.add_argument("--limit", type=_positive_integer, help="maximum keys to test")
    parser.add_argument("--output", help="fully decrypt to this new path after recovery")


def _print_summary(result, mode):
    rate = result.tested / result.elapsed if result.elapsed else float("inf")
    print(
        f"Tested {result.tested} keys in {result.elapsed:.3f}s "
        f"({rate:.0f} keys/s), mode={mode}, skipped={result.skipped}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Test GEMSEAL resistance to bounded offline key searches. "
            "Candidates are checked against the first authenticated record."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    wordlist_parser = subparsers.add_parser("wordlist", help="test candidates from a file")
    wordlist_parser.add_argument("container")
    wordlist_parser.add_argument("wordlist")
    _add_common_options(wordlist_parser)

    pin_parser = subparsers.add_parser("pin", help="search a numeric PIN space")
    pin_parser.add_argument("container")
    pin_parser.add_argument("--digits", type=int, default=4)
    pin_parser.add_argument("--prefix", default="")
    pin_parser.add_argument("--suffix", default="")
    _add_common_options(pin_parser)

    raw_parser = subparsers.add_parser(
        "raw-prefix", help="search a small raw-key prefix with zero-filled remaining bytes"
    )
    raw_parser.add_argument("container")
    raw_parser.add_argument("--variable-bytes", type=int, default=1)
    _add_common_options(raw_parser, include_mode=False)

    args = parser.parse_args(argv)
    try:
        if args.command == "pin" and not 1 <= args.digits <= 8:
            raise CrackError("PIN length must be between 1 and 8 digits")
        if args.command == "raw-prefix" and not 1 <= args.variable_bytes <= 4:
            raise CrackError("variable raw-key prefix must be between 1 and 4 bytes")

        challenge = load_challenge(args.container)
        if args.command == "wordlist":
            with open(args.wordlist, "rb") as stream:
                candidates = wordlist_candidates(stream)
                result = crack_candidates(challenge, candidates, args.mode, args.limit)
        elif args.command == "pin":
            candidates = pin_candidates(
                args.digits, args.prefix.encode("utf-8"), args.suffix.encode("utf-8")
            )
            result = crack_candidates(challenge, candidates, args.mode, args.limit)
        else:
            candidates = raw_prefix_candidates(args.variable_bytes)
            result = crack_candidates(challenge, candidates, "raw", args.limit)

        _print_summary(result, "raw" if args.command == "raw-prefix" else args.mode)
        if result.key is None:
            print("NOT FOUND: no candidate authenticated the first record")
            return 1

        print(f"FOUND: candidate={result.candidate!r}")
        if args.output:
            decrypt_file(result.key, args.container, args.output)
            print(f"Full container verified and decrypted to {args.output}")
        else:
            print("The first record authenticated; use --output for full-container verification")
        return 0
    except (CrackError, GemSealError, OSError) as error:
        print(f"gemseal-crack: error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("gemseal-crack: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

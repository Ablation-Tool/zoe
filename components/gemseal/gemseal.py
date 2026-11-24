#!/usr/bin/env python3

import argparse
from contextlib import contextmanager
import errno
import os
import struct
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"GEMSEAL1"
VERSION = 1
SUITE = 1
KDF = 1
DATA_RECORD = 1
END_RECORD = 2
KEY_SIZE = 32
TAG_SIZE = 16
DEFAULT_CHUNK_SIZE = 4096
MAX_CHUNK_SIZE = 65535 - TAG_SIZE
MAX_DATA_RECORDS = 0xFFFFFFFF
HEADER = struct.Struct("<8sHHHH16s8sII")
RECORD = struct.Struct("<HHHIIH")
AAD_CONTEXT = b"GEMSEAL1/record\x00"
KDF_CONTEXT = b"GEMSEAL1/file-key\x00"
ZERO_TAG = bytes(TAG_SIZE)


class GemSealError(Exception):
    pass


@contextmanager
def _atomic_output(path):
    destination = Path(path)
    if os.path.lexists(destination):
        raise FileExistsError(
            errno.EEXIST, os.strerror(errno.EEXIST), str(destination)
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            yield output
            _sync(output)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _load_key(path):
    key = Path(path).read_bytes()
    if len(key) != KEY_SIZE:
        raise GemSealError(f"key must contain exactly {KEY_SIZE} bytes")
    return key


def _derive_file_key(master_key, salt):
    return HKDF(
        algorithm=SHA256(),
        length=KEY_SIZE,
        salt=salt,
        info=KDF_CONTEXT,
    ).derive(master_key)


def _nonce(prefix, index):
    return prefix + struct.pack("<I", index)


def _aad(file_header, previous_tag, record_header):
    return AAD_CONTEXT + file_header + previous_tag + record_header


def _read_exact(stream, size, description):
    data = stream.read(size)
    if len(data) != size:
        raise GemSealError(f"truncated {description}")
    return data


def _sync(stream):
    stream.flush()
    os.fsync(stream.fileno())


def generate_key(path):
    with _atomic_output(path) as output:
        output.write(os.urandom(KEY_SIZE))


def encrypt_file(master_key, source, destination, chunk_size=DEFAULT_CHUNK_SIZE):
    if len(master_key) != KEY_SIZE:
        raise GemSealError(f"master key must contain exactly {KEY_SIZE} bytes")
    if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
        raise GemSealError(f"chunk size must be between 1 and {MAX_CHUNK_SIZE} bytes")

    salt = os.urandom(16)
    nonce_prefix = os.urandom(8)
    file_header = HEADER.pack(
        MAGIC,
        VERSION,
        SUITE,
        KDF,
        HEADER.size,
        salt,
        nonce_prefix,
        chunk_size,
        0,
    )
    aead = ChaCha20Poly1305(_derive_file_key(master_key, salt))

    with open(source, "rb") as input_file, _atomic_output(destination) as output:
        output.write(file_header)
        previous_tag = ZERO_TAG
        index = 0

        while plaintext := input_file.read(chunk_size):
            if index >= MAX_DATA_RECORDS:
                raise GemSealError("too many data records")
            record_header = RECORD.pack(
                DATA_RECORD,
                SUITE,
                len(plaintext) + TAG_SIZE,
                index,
                len(plaintext),
                0,
            )
            sealed = aead.encrypt(
                _nonce(nonce_prefix, index),
                plaintext,
                _aad(file_header, previous_tag, record_header),
            )
            output.write(record_header)
            output.write(sealed)
            previous_tag = sealed[-TAG_SIZE:]
            index += 1

        record_header = RECORD.pack(END_RECORD, SUITE, TAG_SIZE, index, 0, 0)
        sealed = aead.encrypt(
            _nonce(nonce_prefix, index),
            b"",
            _aad(file_header, previous_tag, record_header),
        )
        output.write(record_header)
        output.write(sealed)


def decrypt_file(master_key, source, destination):
    if len(master_key) != KEY_SIZE:
        raise GemSealError(f"master key must contain exactly {KEY_SIZE} bytes")

    with open(source, "rb") as input_file:
        file_header = _read_exact(input_file, HEADER.size, "file header")
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
        ) = HEADER.unpack(file_header)
        if magic != MAGIC or version != VERSION:
            raise GemSealError("unsupported GEMSEAL format")
        if suite != SUITE or kdf != KDF:
            raise GemSealError("unsupported cryptographic suite")
        if header_size != HEADER.size or reserved != 0:
            raise GemSealError("invalid file header")
        if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
            raise GemSealError("invalid chunk size")

        aead = ChaCha20Poly1305(_derive_file_key(master_key, salt))
        with _atomic_output(destination) as output:
            previous_tag = ZERO_TAG
            index = 0

            while True:
                record_header = _read_exact(input_file, RECORD.size, "record header")
                (
                    record_type,
                    record_suite,
                    sealed_size,
                    record_index,
                    plaintext_size,
                    flags,
                ) = RECORD.unpack(record_header)

                if record_type not in (DATA_RECORD, END_RECORD):
                    raise GemSealError("invalid record type")
                if record_suite != SUITE or flags != 0:
                    raise GemSealError("invalid record header")
                if record_index != index:
                    raise GemSealError("record sequence mismatch")
                if plaintext_size > chunk_size:
                    raise GemSealError("record exceeds negotiated chunk size")
                if sealed_size != plaintext_size + TAG_SIZE:
                    raise GemSealError("invalid record length")
                if record_type == DATA_RECORD:
                    if plaintext_size == 0 or index >= MAX_DATA_RECORDS:
                        raise GemSealError("invalid data record")
                elif plaintext_size != 0:
                    raise GemSealError("invalid end record")

                sealed = _read_exact(input_file, sealed_size, "record body")
                try:
                    plaintext = aead.decrypt(
                        _nonce(nonce_prefix, index),
                        sealed,
                        _aad(file_header, previous_tag, record_header),
                    )
                except InvalidTag as error:
                    raise GemSealError("authentication failed") from error

                if record_type == END_RECORD:
                    if input_file.read(1):
                        raise GemSealError("data follows the end record")
                    break

                output.write(plaintext)
                previous_tag = sealed[-TAG_SIZE:]
                index += 1


# --------------------------------------------------------------------------- #
# Wave 3: Vector-Privacy Sealing & Audit (vec2text embedding-inversion guard)
# Empirically, dense embeddings (e.g. 768-dim GTR-T5 float32) can be inverted
# back to sensitive plaintext on CPU (~50s, cos=0.9508). Embeddings are NOT
# one-way hashes and must be sealed with authenticated encryption at rest.
# --------------------------------------------------------------------------- #
def seal_embedding_records(
    master_key,
    records,
    destination,
    *,
    model_id="unknown",
    classification="sensitive",
):
    """Seal dense vector embedding records inside an authenticated GEMSEAL1 container."""
    import json

    if not isinstance(records, (list, tuple)):
        raise GemSealError("embedding records must be a sequence")
    envelope = {
        "schema": "zoe-gemseal-embeddings-v1",
        "vector_privacy_policy": {
            "treat_as_plaintext": True,
            "inversion_risk": "vec2text_high",
            "model_id": str(model_id),
            "classification": str(classification),
        },
        "record_count": len(records),
        "records": list(records),
    }
    raw_bytes = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest_path.parent, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)
    try:
        encrypt_file(master_key, tmp_path, dest_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return {
        "sealed": True,
        "destination": str(dest_path),
        "record_count": len(records),
        "plaintext_bytes": len(raw_bytes),
        "sealed_bytes": dest_path.stat().st_size,
        "policy": envelope["vector_privacy_policy"],
    }


def unseal_embedding_records(master_key, source):
    """Verify and decrypt a GEMSEAL1-sealed embedding container into Python dicts."""
    import json

    src_path = Path(source)
    with tempfile.TemporaryDirectory() as tmp_dir:
        plain_path = Path(tmp_dir) / "embeddings.json"
        decrypt_file(master_key, src_path, plain_path)
        return json.loads(plain_path.read_text(encoding="utf-8"))


def audit_embedding_storage_policy(path):
    """Inspect a local embedding artifact and flag unsealed raw vector stores."""
    target = Path(path)
    if not target.is_file():
        return {
            "path": str(target),
            "exists": False,
            "sealed": False,
            "compliant": False,
            "risk": "MISSING",
        }
    head = target.read_bytes()[:2048]
    if head.startswith(MAGIC):
        return {
            "path": str(target),
            "exists": True,
            "sealed": True,
            "compliant": True,
            "risk": "NONE",
            "reason": "GEMSEAL1 authenticated container",
        }
    looks_like_vectors = (
        target.suffix.lower() in {".npy", ".npz", ".faiss", ".vec", ".bin"}
        or b"embedding" in head.lower()
        or b"vector" in head.lower()
    )
    return {
        "path": str(target),
        "exists": True,
        "sealed": False,
        "compliant": not looks_like_vectors,
        "risk": "HIGH_VECTOR_INVERSION_RISK" if looks_like_vectors else "UNSEALED_NON_VECTOR",
        "reason": (
            "Unencrypted dense embeddings are recoverable via vec2text inversion; seal with GEMSEAL1."
            if looks_like_vectors
            else "File is not GEMSEAL1-sealed."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Encrypt and decrypt GEMSEAL authenticated containers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    keygen_parser = subparsers.add_parser("keygen", help="create a 32-byte key")
    keygen_parser.add_argument("key")

    encrypt_parser = subparsers.add_parser("encrypt", help="encrypt a file")
    encrypt_parser.add_argument("key")
    encrypt_parser.add_argument("source")
    encrypt_parser.add_argument("destination")
    encrypt_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)

    decrypt_parser = subparsers.add_parser("decrypt", help="decrypt a file")
    decrypt_parser.add_argument("key")
    decrypt_parser.add_argument("source")
    decrypt_parser.add_argument("destination")

    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            generate_key(args.key)
        elif args.command == "encrypt":
            encrypt_file(
                _load_key(args.key),
                args.source,
                args.destination,
                args.chunk_size,
            )
        else:
            decrypt_file(_load_key(args.key), args.source, args.destination)
    except (GemSealError, OSError) as error:
        parser.exit(1, f"gemseal: error: {error}\n")


if __name__ == "__main__":
    main()

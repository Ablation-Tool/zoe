"""Shared deterministic SHA-256 and atomic JSON persistence helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


def sha256_bytes(data: bytes) -> str:
    """Return lowercase hexadecimal SHA-256 digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_json_utf8(payload: object) -> str:
    """Return SHA-256 digest of canonical UTF-8 JSON with NaN/Infinity forbidden."""
    # Preserve raw UTF-8 characters and reject non-finite floats deterministically.
    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(raw)


def sha256_json_ascii(payload: object) -> str:
    """Return SHA-256 digest of canonical ASCII-escaped JSON with default NaN handling."""
    # Match legacy json.dumps defaults (ensure_ascii=True, allow_nan=True) for digest parity.
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(raw)


def sha256_file(path: str | Path) -> str:
    """Stream a file in 64 KiB chunks and return its SHA-256 hex digest."""
    # Stream chunks to hash arbitrarily large evidence files in bounded memory.
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: str | Path, document: Mapping[str, Any]) -> Path:
    """Atomically write a canonical JSON mapping with 0600 file permissions."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    # Write to a unique sibling temp file so concurrent writers never collide or expose partial JSON.
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            tmp_path = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "atomic_write_json",
    "sha256_bytes",
    "sha256_file",
    "sha256_json_ascii",
    "sha256_json_utf8",
]

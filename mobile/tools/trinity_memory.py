#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path

ZERO_HASH = "0" * 64
MAX_JOURNAL_BYTES = 64 * 1024 * 1024
MAX_JOURNAL_EVENTS = 10_000
MAX_JOURNAL_LINE = 65_536


class JournalError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def record_hash(body):
    return hashlib.sha256(canonical(body)).hexdigest()


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.records = []
        self._handle = None
        if self.path.is_symlink():
            raise JournalError("memory journal must not be a symbolic link")
        if not self.path.parent.is_dir():
            raise JournalError("memory journal parent directory must already exist")
        if self.path.exists() and not self.path.is_file():
            raise JournalError("memory journal must be a regular file")
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            self._handle = os.open(self.path, flags, 0o600)
        except FileExistsError:
            flags = os.O_RDWR | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            self._handle = os.open(self.path, flags)
        try:
            self._load()
        except Exception:
            os.close(self._handle)
            self._handle = None
            raise

    def _load(self):
        size = self.path.stat().st_size
        if size > MAX_JOURNAL_BYTES:
            raise JournalError("memory journal exceeds 64 MiB")
        previous = ZERO_HASH
        with self.path.open("r", encoding="utf-8") as source:
            for sequence, line in enumerate(source, 1):
                if sequence > MAX_JOURNAL_EVENTS:
                    raise JournalError("memory journal exceeds 10,000 events")
                if len(line.encode("utf-8")) > MAX_JOURNAL_LINE:
                    raise JournalError("memory journal line exceeds 65,536 bytes")
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise JournalError(f"invalid memory JSON at event {sequence}") from error
                if not isinstance(record, dict):
                    raise JournalError("memory events must be JSON objects")
                supplied_hash = record.get("hash")
                body = {key: value for key, value in record.items() if key != "hash"}
                if supplied_hash != record_hash(body):
                    raise JournalError(f"memory hash mismatch at event {sequence}")
                if body.get("sequence") != len(self.records) + 1:
                    raise JournalError("memory event sequence is edited or reordered")
                if body.get("previous") != previous:
                    raise JournalError("memory previous-event hash is broken")
                if body.get("revision") != body.get("sequence"):
                    raise JournalError("memory revision does not match its sequence")
                if body.get("kind") not in {"measure", "reset"}:
                    raise JournalError("unknown memory event kind")
                self.records.append(record)
                previous = supplied_hash

    @property
    def previous(self):
        return self.records[-1]["hash"] if self.records else ZERO_HASH

    def append(self, kind, source, active, event=None):
        sequence = len(self.records) + 1
        body = {
            "sequence": sequence,
            "revision": sequence,
            "previous": self.previous,
            "kind": kind,
            "source": source,
            "active": active,
            "event": event,
        }
        record = dict(body)
        record["hash"] = record_hash(body)
        payload = canonical(record) + b"\n"
        if len(payload) > MAX_JOURNAL_LINE:
            raise JournalError("memory event exceeds 65,536 bytes")
        if self.path.stat().st_size + len(payload) > MAX_JOURNAL_BYTES:
            raise JournalError("memory journal would exceed 64 MiB")
        if len(self.records) >= MAX_JOURNAL_EVENTS:
            raise JournalError("memory journal is full")
        written = 0
        while written < len(payload):
            written += os.write(self._handle, payload[written:])
        os.fsync(self._handle)
        self.records.append(record)
        return record

    def close(self):
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None

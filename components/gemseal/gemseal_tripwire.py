#!/usr/bin/env python3

import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import select
import signal
import struct
import sys
import tempfile
import threading
import time

from gemseal import GemSealError, encrypt_file, generate_key

IN_ACCESS = 0x0001
IN_MODIFY = 0x0002
IN_ATTRIB = 0x0004
IN_CLOSE_WRITE = 0x0008
IN_MOVED_FROM = 0x0040
IN_MOVED_TO = 0x0080
IN_CREATE = 0x0100
IN_DELETE = 0x0200
IN_DELETE_SELF = 0x0400
IN_MOVE_SELF = 0x0800
IN_Q_OVERFLOW = 0x4000
IN_IGNORED = 0x8000
IN_ONLYDIR = 0x01000000
IN_ISDIR = 0x40000000

WATCH_MASK = (
    IN_ACCESS
    | IN_MODIFY
    | IN_ATTRIB
    | IN_CLOSE_WRITE
    | IN_MOVED_FROM
    | IN_MOVED_TO
    | IN_CREATE
    | IN_DELETE
    | IN_DELETE_SELF
    | IN_MOVE_SELF
    | 0x00000020
)
EVENT_BITS = (
    (IN_ACCESS, "read"),
    (IN_MODIFY, "modify"),
    (IN_ATTRIB, "metadata"),
    (IN_CLOSE_WRITE, "close-write"),
    (0x00000020, "open"),
    (IN_MOVED_FROM, "moved-from"),
    (IN_MOVED_TO, "moved-to"),
    (IN_CREATE, "create"),
    (IN_DELETE, "delete"),
    (IN_DELETE_SELF, "delete-self"),
    (IN_MOVE_SELF, "move-self"),
)
EVENT_HEADER = struct.Struct("iIII")


class TripwireError(Exception):
    pass


def _is_within(path, directory):
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def init_vault(vault_path, key_path, canary_name="project_notes.gemseal"):
    vault = Path(vault_path)
    key = Path(key_path)
    if os.path.lexists(vault):
        raise TripwireError(f"vault path already exists: {vault}")
    if os.path.lexists(key):
        raise TripwireError(f"key path already exists: {key}")
    if not canary_name or Path(canary_name).name != canary_name:
        raise TripwireError("canary name must be a single filename")

    vault_resolved = vault.resolve()
    if _is_within(key.resolve(), vault_resolved):
        raise TripwireError("key must be stored outside the vault")
    key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    created_vault = False
    created_key = False
    canary = vault / canary_name
    try:
        vault.mkdir(mode=0o700)
        created_vault = True
        generate_key(key)
        created_key = True
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "canary.txt"
            source.write_text(
                "This GEMSEAL canary contains no sensitive information.\n",
                encoding="utf-8",
            )
            encrypt_file(key.read_bytes(), source, canary)
    except BaseException:
        canary.unlink(missing_ok=True)
        if created_key:
            key.unlink(missing_ok=True)
        if created_vault:
            try:
                vault.rmdir()
            except OSError:
                pass
        raise
    return canary


class AuditLog:
    def __init__(self, path):
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        self.stream = os.fdopen(descriptor, "a", encoding="utf-8")

    def write(self, record):
        self.stream.write(json.dumps(record, sort_keys=True) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.stream.close()


class TripwireWatcher:
    def __init__(self, vault_path, log_path, once=False, dedup=1.0, alert_stream=None):
        if dedup < 0:
            raise TripwireError("dedup interval cannot be negative")
        self.vault = Path(vault_path).resolve()
        self.log_path = Path(log_path).resolve()
        self.once = once
        self.dedup = dedup
        self.alert_stream = alert_stream if alert_stream is not None else sys.stderr
        self.ready = threading.Event()
        self.error = None
        self._stop = threading.Event()
        self._fd = None
        self._log = None
        self._watches = {}
        self._recent = {}
        self._libc = ctypes.CDLL(None, use_errno=True)
        self._configure_libc()

    def _configure_libc(self):
        try:
            self._libc.inotify_init1.argtypes = [ctypes.c_int]
            self._libc.inotify_init1.restype = ctypes.c_int
            self._libc.inotify_add_watch.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint32,
            ]
            self._libc.inotify_add_watch.restype = ctypes.c_int
            self._libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
            self._libc.inotify_rm_watch.restype = ctypes.c_int
        except AttributeError as error:
            raise TripwireError("Linux inotify is not available") from error

    def prepare(self):
        if not self.vault.is_dir():
            raise TripwireError(f"vault is not a directory: {self.vault}")
        if _is_within(self.log_path, self.vault):
            raise TripwireError("audit log must be outside the watched vault")
        self.log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._log = AuditLog(self.log_path)
        flags = os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        self._fd = self._libc.inotify_init1(flags)
        if self._fd < 0:
            error_number = ctypes.get_errno()
            raise TripwireError(os.strerror(error_number))
        for root, directories, _ in os.walk(self.vault):
            directories.sort()
            self._add_watch(Path(root))

    def _add_watch(self, path):
        encoded = os.fsencode(path)
        watch_descriptor = self._libc.inotify_add_watch(
            self._fd, encoded, WATCH_MASK | IN_ONLYDIR
        )
        if watch_descriptor < 0:
            error_number = ctypes.get_errno()
            raise TripwireError(f"cannot watch {path}: {os.strerror(error_number)}")
        self._watches[watch_descriptor] = path

    def stop(self):
        self._stop.set()

    def _close(self):
        if self._fd is not None:
            for watch_descriptor in list(self._watches):
                self._libc.inotify_rm_watch(self._fd, watch_descriptor)
            os.close(self._fd)
            self._fd = None
            self._watches.clear()
        if self._log is not None:
            self._log.close()
            self._log = None

    def run(self):
        try:
            if self._fd is None:
                self.prepare()
            self.ready.set()
            while not self._stop.is_set():
                readable, _, _ = select.select([self._fd], [], [], 0.5)
                if not readable:
                    continue
                try:
                    data = os.read(self._fd, 65536)
                except BlockingIOError:
                    continue
                if not data:
                    break
                offset = 0
                while offset < len(data) and not self._stop.is_set():
                    watch_descriptor, mask, _, name_length = EVENT_HEADER.unpack_from(
                        data, offset
                    )
                    offset += EVENT_HEADER.size
                    raw_name = data[offset : offset + name_length]
                    offset += name_length
                    self._handle_event(watch_descriptor, mask, raw_name)
        except Exception as error:
            self.error = error
        finally:
            self.ready.set()
            self._close()
        if self.error is not None:
            raise self.error

    def _handle_event(self, watch_descriptor, mask, raw_name):
        if mask & IN_Q_OVERFLOW:
            self._publish(["queue-overflow"], self.vault, mask)
            return
        if mask & IN_IGNORED:
            self._watches.pop(watch_descriptor, None)
            return
        base = self._watches.get(watch_descriptor)
        if base is None:
            return
        name = os.fsdecode(raw_name.split(b"\0", 1)[0])
        path = base / name if name else base
        events = [event for bit, event in EVENT_BITS if mask & bit]
        if not events:
            return
        if mask & IN_ISDIR and mask & (IN_CREATE | IN_MOVED_TO):
            self._add_watch(path)
        self._publish(events, path, mask)

    def _publish(self, events, path, mask):
        now = time.monotonic()
        key = (str(path), tuple(events))
        previous = self._recent.get(key)
        if previous is not None and now - previous < self.dedup:
            return
        self._recent[key] = now
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "events": events,
            "path": str(path),
            "mask": f"0x{mask:08x}",
        }
        self._log.write(record)
        print(
            f"TRIPWIRE {','.join(events)} {str(path)!r}",
            file=self.alert_stream,
            flush=True,
        )
        if self.once:
            self._stop.set()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create and monitor encrypted GEMSEAL vault tripwires."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a vault and encrypted canary")
    init_parser.add_argument("vault")
    init_parser.add_argument("key")
    init_parser.add_argument("--name", default="project_notes.gemseal")

    watch_parser = subparsers.add_parser("watch", help="log vault access attempts")
    watch_parser.add_argument("vault")
    watch_parser.add_argument("--log", required=True)
    watch_parser.add_argument("--once", action="store_true")
    watch_parser.add_argument("--dedup", type=float, default=1.0)

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            canary = init_vault(args.vault, args.key, args.name)
            print(f"Vault created: {args.vault}")
            print(f"Encrypted canary: {canary}")
            print(f"Key stored outside vault: {args.key}")
            return 0

        watcher = TripwireWatcher(args.vault, args.log, args.once, args.dedup)
        previous_handlers = {}

        def request_stop(signum, frame):
            watcher.stop()

        for signal_name in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signal_name] = signal.signal(signal_name, request_stop)
        try:
            watcher.run()
        finally:
            for signal_name, handler in previous_handlers.items():
                signal.signal(signal_name, handler)
        return 0
    except (TripwireError, GemSealError, OSError) as error:
        print(f"gemseal-tripwire: error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

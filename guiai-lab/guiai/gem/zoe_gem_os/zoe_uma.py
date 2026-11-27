"""Zoe-GEM × Ubuntu Hardware UMA (Unified Memory Architecture) & Consent Airlock.

Implements the 4-node + center UMA model (`GEM` / `AI` / `UMA` / `∀` / `YOU`):
  - Left Half  (AI + GEM) : Zoe-GEM OS sovereign UEFI KVM domain
  - Right Half (YOU)      : Nicholas's sovereign Ubuntu workstation
  - Right Node (∀)        : Universal verification invariant — zero unauthorized crossing;
                            every transfer requires mutual consent (`nick_allow && zoe_allow`)
                            and is sealed in a SHA-256 hash-chained `uma_audit.jsonl`.
  - Center     (UMA)      : Hardware PCI `ivshmem-plain` 4 MB shared physical RAM BAR
                            (`/dev/shm/zoe-uma-bar.shm` <-> PCI `1af4:1110` `resource2`)
                            + hardware PCI `virtio-9p` consent airlock (`~/.zoe/uma-bridge/` <-> `/mnt/uma`).

Zero cloud tokens, zero silent host access, strict privacy-by-default (`gate="PRIVATE"`).
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import mmap
import os
from pathlib import Path
import shutil
import stat
import struct
import threading
import time
from typing import Any, Iterator
import zlib

UMA_SHM_SIZE = 4 * 1024 * 1024  # 4 MiB hardware PCI ivshmem BAR2
UMA_SHM_MAGIC = b"ZOE-UMA1"
UMA_META_MAGIC = b"UMA2"
UMA_META_OFF = 4080
UMA_HDR_MAX = 3840
UMA_SLOT_STRIDE = 4096  # Slot 0=Coordinator, Slot 1..3=ZO3 sovereign nodes (zero write contention!)
UMA_MAX_SLOTS = 8
UMA_MAX_TRANSFER_BYTES = 16 * 1024 * 1024
DEFAULT_UMA_DIR = Path.home() / ".zoe" / "uma-bridge"
DEFAULT_UMA_SHM = "/dev/shm/zoe-uma-bar.shm"


def resolve_uma_paths(
    uma_dir: str | Path | None = None,
    shm_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Resolve canonical UMA airlock directory and 4 MiB SHM BAR path."""
    if uma_dir is not None and str(uma_dir).strip():
        resolved_dir = Path(uma_dir).expanduser().resolve()
    else:
        env_dir = os.environ.get("ZOE_UMA_DIR", "").strip()
        resolved_dir = (Path(env_dir).expanduser() if env_dir else (Path.home() / ".zoe" / "uma-bridge")).resolve()

    if shm_path is not None and str(shm_path).strip():
        resolved_shm = Path(shm_path).expanduser()
    else:
        env_shm = os.environ.get("ZOE_UMA_SHM", "").strip()
        resolved_shm = Path(env_shm).expanduser() if env_shm else Path(DEFAULT_UMA_SHM)

    return resolved_dir, resolved_shm


def _validate_shm_slot(slot: int) -> int:
    if isinstance(slot, bool) or not isinstance(slot, int):
        raise ValueError(f"UMA SHM slot must be an integer (not bool), got {slot!r}")
    return max(0, min(UMA_MAX_SLOTS - 1, slot))

_BRIDGE_LOCKS_GUARD = threading.Lock()
_BRIDGE_LOCKS: dict[Path, threading.RLock] = {}
_THREAD_LOCK_DEPTHS = threading.local()
_IGNORED_FLOCK_ERRNOS = (errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOLCK)


def _get_thread_lock(bridge_dir: Path) -> threading.RLock:
    with _BRIDGE_LOCKS_GUARD:
        lock = _BRIDGE_LOCKS.get(bridge_dir)
        if lock is None:
            lock = threading.RLock()
            _BRIDGE_LOCKS[bridge_dir] = lock
        return lock


def _default_state(reason: str = "privacy_by_default") -> dict[str, Any]:
    return {
        "protocol": "zoe-uma/v1",
        "nick_allow": False,
        "zoe_allow": False,
        "gate": "PRIVATE",
        "reason": reason,
        "updated_ts": int(time.time()),
    }


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _acquire_flock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError as exc:
        if exc.errno not in _IGNORED_FLOCK_ERRNOS:
            raise


def _enable_pci_bar(dev: Path) -> Path | None:
    en_p = dev / "enable"
    try:
        if en_p.is_file() and en_p.read_text(encoding="utf-8").strip() == "0":
            en_p.write_text("1", encoding="utf-8")
    except OSError:
        pass
    res2 = dev / "resource2"
    return res2 if res2.exists() else None


def find_guest_ivshmem_bar2(sys_pci_root: str | Path = "/sys/bus/pci/devices") -> Path | None:
    """Locate QEMU PCI `ivshmem-plain` (1af4:1110) BAR2 (`resource2`) inside booted Zoe-GEM OS."""
    pci_root = Path(sys_pci_root)
    if not pci_root.is_dir():
        return None
    for dev in sorted(pci_root.iterdir()):
        v_p, d_p = dev / "vendor", dev / "device"
        if not (v_p.is_file() and d_p.is_file()):
            continue
        try:
            vendor = v_p.read_text(encoding="utf-8", errors="ignore").strip().lower()
            device = d_p.read_text(encoding="utf-8", errors="ignore").strip().lower()
        except OSError:
            continue
        if vendor == "0x1af4" and device == "0x1110":
            bar2 = _enable_pci_bar(dev)
            if bar2 is not None:
                return bar2
    return None


def _compute_gate(nick_allow: bool, zoe_allow: bool) -> str:
    if nick_allow and zoe_allow:
        return "SHARED"
    if nick_allow or zoe_allow:
        return "REQUESTED"
    return "PRIVATE"


def _parse_slot_json(raw: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_shm_slot_once(mm: mmap.mmap, offset: int) -> tuple[bool, dict[str, Any] | None]:
    head_before = bytes(mm[offset : offset + 12])
    if head_before[:8] != UMA_SHM_MAGIC:
        return False, None
    length = struct.unpack("<I", head_before[8:12])[0]
    if length == 0:
        return True, None
    if length > UMA_HDR_MAX:
        return False, None
    meta_before = bytes(mm[offset + UMA_META_OFF : offset + UMA_META_OFF + 16])
    has_meta = meta_before[:4] == UMA_META_MAGIC
    crc_b = 0
    if has_meta:
        _, seq_b, crc_b, tag_b = struct.unpack("<4sIII", meta_before)
        if (seq_b & 1) != 0 or tag_b != (crc_b ^ seq_b):
            return True, None
    raw = bytes(mm[offset + 12 : offset + 12 + length])
    meta_after = bytes(mm[offset + UMA_META_OFF : offset + UMA_META_OFF + 16])
    if meta_after != meta_before or bytes(mm[offset : offset + 12]) != head_before:
        return True, None
    if has_meta and (zlib.crc32(raw) & 0xFFFFFFFF) != crc_b:
        return True, None
    parsed = _parse_slot_json(raw)
    return (True, None) if parsed is None else (False, parsed)


def _write_shm_slot_bytes(mm: mmap.mmap, offset: int, body: bytes) -> None:
    meta_cur = bytes(mm[offset + UMA_META_OFF : offset + UMA_META_OFF + 16])
    prev_seq = struct.unpack("<I", meta_cur[4:8])[0] if meta_cur[:4] == UMA_META_MAGIC else 0
    seq_odd = ((prev_seq + 1) | 1) & 0xFFFFFFFF
    seq_even = (seq_odd + 1) & 0xFFFFFFFF
    crc = zlib.crc32(body) & 0xFFFFFFFF
    mm[offset + 8 : offset + 12] = struct.pack("<I", 0)
    mm[offset + UMA_META_OFF : offset + UMA_META_OFF + 16] = struct.pack("<4sIII", UMA_META_MAGIC, seq_odd, 0, 0)
    mm[offset + 12 : offset + 12 + len(body)] = body
    mm[offset + UMA_META_OFF : offset + UMA_META_OFF + 16] = struct.pack(
        "<4sIII", UMA_META_MAGIC, seq_even, crc, crc ^ seq_even
    )
    mm[offset : offset + 12] = UMA_SHM_MAGIC + struct.pack("<I", len(body))


class UmaBridge:
    """Consent-gated hardware UMA controller shared by Ubuntu host and booted Zoe-GEM OS."""

    def __init__(self, bridge_dir: str | Path, shm_path: str | Path | None = None):
        self.bridge_dir = Path(bridge_dir).expanduser().resolve()
        self.shm_path = Path(shm_path).expanduser() if shm_path else None
        self.state_path = self.bridge_dir / "uma_state.json"
        self.audit_path = self.bridge_dir / "uma_audit.jsonl"
        self.lock_path = self.bridge_dir / "uma.lock"
        self.zoe_to_nick = self.bridge_dir / "zoe_to_nick"
        self.nick_to_zoe = self.bridge_dir / "nick_to_zoe"
        self._thread_lock = _get_thread_lock(self.bridge_dir)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        depths: dict[Path, int] = getattr(_THREAD_LOCK_DEPTHS, "depths", {})
        if not hasattr(_THREAD_LOCK_DEPTHS, "depths"):
            _THREAD_LOCK_DEPTHS.depths = depths
        with self._thread_lock:
            cur = depths.get(self.bridge_dir, 0)
            if cur > 0:
                depths[self.bridge_dir] = cur + 1
                try:
                    yield
                finally:
                    depths[self.bridge_dir] = cur
                return
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o644)
            try:
                _acquire_flock(fd)
                depths[self.bridge_dir] = 1
                try:
                    yield
                finally:
                    depths[self.bridge_dir] = 0
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
            finally:
                os.close(fd)

    def _ensure_dirs_and_shm(self) -> None:
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.zoe_to_nick.mkdir(exist_ok=True)
        self.nick_to_zoe.mkdir(exist_ok=True)
        if self.shm_path and not str(self.shm_path).startswith("/sys/"):
            self.shm_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.shm_path), os.O_CREAT | os.O_RDWR, 0o644)
            try:
                if os.fstat(fd).st_size != UMA_SHM_SIZE:
                    os.ftruncate(fd, UMA_SHM_SIZE)
            finally:
                os.close(fd)

    def _read_state_unlocked(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return _default_state("uninitialized")
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _default_state("recovered_corrupt_state")
        if not isinstance(data, dict):
            return _default_state("recovered_corrupt_state")
        data["nick_allow"] = data.get("nick_allow") is True
        data["zoe_allow"] = data.get("zoe_allow") is True
        data["gate"] = _compute_gate(data["nick_allow"], data["zoe_allow"])
        return data

    def _write_state_unlocked(self, state: dict[str, Any]) -> None:
        _atomic_write_text(self.state_path, json.dumps(state, indent=2))

    def _last_audit_sha_unlocked(self) -> str:
        if not self.audit_path.is_file():
            return "genesis"
        try:
            lines = [
                ln.strip()
                for ln in self.audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()
            ]
        except OSError:
            return "genesis"
        for raw in reversed(lines):
            try:
                rec = json.loads(raw)
                if isinstance(rec, dict) and isinstance(rec.get("sha256"), str):
                    return rec["sha256"]
            except ValueError:
                continue
        return "genesis"

    @staticmethod
    def _audit_newline_prefix(audit_path: Path) -> str:
        try:
            if not audit_path.is_file() or audit_path.stat().st_size == 0:
                return ""
            with audit_path.open("rb") as rf:
                rf.seek(-1, os.SEEK_END)
                return "" if rf.read(1) == b"\n" else "\n"
        except OSError:
            return ""

    def _append_audit_unlocked(self, event: str, actor: str, detail: dict[str, Any]) -> str:
        prev_sha = self._last_audit_sha_unlocked()
        rec: dict[str, Any] = {
            "ts": int(time.time()),
            "event": event,
            "actor": actor,
            "detail": detail,
            "prev_sha": prev_sha,
        }
        digest = hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        rec["sha256"] = digest
        prefix = self._audit_newline_prefix(self.audit_path)
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(prefix + json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        return digest

    def _append_audit(self, event: str, actor: str, detail: dict[str, Any]) -> str:
        with self._locked():
            return self._append_audit_unlocked(event, actor, detail)

    def ensure_initialized(self) -> dict[str, Any]:
        with self._locked():
            self._ensure_dirs_and_shm()
            state = self._read_state_unlocked()
            if not self.state_path.exists() or state.get("reason") == "recovered_corrupt_state":
                self._write_state_unlocked(_default_state("privacy_by_default"))
                state = self._read_state_unlocked()
            return state

    def read_state(self) -> dict[str, Any]:
        if not self.bridge_dir.exists() or not self.state_path.exists():
            return self._read_state_unlocked()
        with self._locked():
            return self._read_state_unlocked()

    def verify_audit_chain(self) -> dict[str, Any]:
        """Validate `prev_sha` and entry SHA-256 across every line of `uma_audit.jsonl`."""
        if not self.bridge_dir.exists() or not self.audit_path.is_file():
            return {"valid": True, "entries": 0, "head_sha": "genesis"}
        with self._locked():
            if not self.audit_path.is_file():
                return {"valid": True, "entries": 0, "head_sha": "genesis"}
            lines = [
                ln.strip()
                for ln in self.audit_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()
            ]
            prev = "genesis"
            for idx, raw in enumerate(lines):
                try:
                    rec = json.loads(raw)
                except ValueError:
                    return {"valid": False, "entries": idx, "head_sha": prev, "error_index": idx, "reason": "invalid_json"}
                if not isinstance(rec, dict) or not isinstance(rec.get("sha256"), str):
                    return {"valid": False, "entries": idx, "head_sha": prev, "error_index": idx, "reason": "invalid_record"}
                if rec.get("prev_sha") != prev:
                    return {"valid": False, "entries": idx, "head_sha": prev, "error_index": idx, "reason": "prev_sha_mismatch"}
                expected = rec["sha256"]
                payload = {k: v for k, v in rec.items() if k != "sha256"}
                computed = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if expected != computed:
                    return {"valid": False, "entries": idx, "head_sha": prev, "error_index": idx, "reason": "sha256_mismatch"}
                prev = expected
            return {"valid": True, "entries": len(lines), "head_sha": prev}

    def _apply_consent_unlocked(self, who: str, allow: bool, reason: str) -> dict[str, Any]:
        self._ensure_dirs_and_shm()
        st = self._read_state_unlocked()
        if st.get("reason") in {"uninitialized", "recovered_corrupt_state"}:
            st = _default_state("privacy_by_default")
        st[f"{who}_allow"] = bool(allow)
        st["gate"] = _compute_gate(bool(st.get("nick_allow")), bool(st.get("zoe_allow")))
        st["reason"] = reason or (f"{who}_granted" if allow else f"{who}_locked")
        st["updated_ts"] = int(time.time())
        self._write_state_unlocked(st)
        sha = self._append_audit_unlocked(
            "consent_update",
            who,
            {"allow": bool(allow), "gate": st["gate"], "reason": st["reason"]},
        )
        st["audit_sha"] = sha[:16]
        return st

    def set_consent(self, actor: str, allow: bool, reason: str = "") -> dict[str, Any]:
        if not isinstance(actor, str):
            raise ValueError("UMA consent actor must be 'nick' or 'zoe'.")
        who = actor.strip().lower()
        if who not in {"nick", "zoe"}:
            raise ValueError("UMA consent actor must be 'nick' or 'zoe'.")
        with self._locked():
            st = self._apply_consent_unlocked(who, allow, reason)
            self.write_shm_heartbeat(
                f"{who}-host",
                {"gate": st["gate"], "nick_allow": st["nick_allow"], "zoe_allow": st["zoe_allow"]},
            )
        return st

    def set_zoe_consent(self, allow: bool, reason: str = "") -> dict[str, Any]:
        """Explicitly set Zoe guest consent (`PRIVATE` unless `nick_allow && zoe_allow`)."""
        return self.set_consent("zoe", allow, reason=reason)

    def toggle_zoe_consent(self, reason: str = "") -> dict[str, Any]:
        """Atomically toggle Zoe guest consent under lock (`PRIVATE` unless mutual consent)."""
        with self._locked():
            cur = self._read_state_unlocked()
            new_allow = not bool(cur.get("zoe_allow", False))
            msg = reason or ("zoe_granted" if new_allow else "zoe_locked")
            st = self._apply_consent_unlocked("zoe", new_allow, msg)
            self.write_shm_heartbeat(
                "zoe-host",
                {"gate": st["gate"], "nick_allow": st["nick_allow"], "zoe_allow": st["zoe_allow"]},
            )
        return st

    def lock_all(self, actor: str = "nick") -> dict[str, Any]:
        """Instant mutual lock: snaps UMA back to PRIVATE immediately."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("Lock actor must be a non-empty string.")
        who = actor.strip().lower()
        with self._locked():
            self._ensure_dirs_and_shm()
            st = _default_state(f"instant_lock_by_{who}")
            self._write_state_unlocked(st)
            sha = self._append_audit_unlocked("instant_lock", who, {"gate": "PRIVATE"})
            st["audit_sha"] = sha[:16]
            self.write_shm_heartbeat(who, {"gate": "PRIVATE", "nick_allow": False, "zoe_allow": False})
        return st

    def _stage_transfer_file(
        self,
        src: Path,
        dst: Path,
        *,
        max_bytes: int = UMA_MAX_TRANSFER_BYTES,
        allow_symlinks: bool = False,
    ) -> tuple[str, int]:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer.")
        # Stage in bridge_dir (not inbox/outbox) because Python 3.14 Path.glob("*") matches dotfiles.
        tmp = self.bridge_dir / f".xfer.{os.getpid()}.{threading.get_ident()}.tmp"
        hasher = hashlib.sha256()
        total_bytes = 0
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | (0 if allow_symlinks else getattr(os, "O_NOFOLLOW", 0))
        )
        try:
            try:
                src_fd = os.open(str(src), flags)
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise ValueError(f"Symlink transfer rejected by UMA airlock policy: {src}") from exc
                raise
            with os.fdopen(src_fd, "rb") as rfh, tmp.open("wb") as wfh:
                if not stat.S_ISREG(os.fstat(rfh.fileno()).st_mode):
                    raise ValueError(f"UMA transfer source must be a regular file: {src}")
                while True:
                    chunk = rfh.read(min(65536, (max_bytes - total_bytes) + 1))
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError(f"Transfer exceeds max_bytes ({total_bytes} > {max_bytes}).")
                    hasher.update(chunk)
                    wfh.write(chunk)
                wfh.flush()
                try:
                    os.fsync(wfh.fileno())
                except OSError:
                    pass
            try:
                shutil.copystat(src, tmp, follow_symlinks=allow_symlinks)
            except OSError:
                pass
            os.replace(tmp, dst)
            return hasher.hexdigest(), total_bytes
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _validate_transfer_source(src_path: str | Path, *, allow_symlinks: bool) -> Path:
        if isinstance(src_path, bool) or not isinstance(src_path, (str, Path)):
            raise ValueError("Transfer source path must be a valid string or Path.")
        raw_str = str(src_path)
        if "\x00" in raw_str or not raw_str.strip():
            raise ValueError("Transfer source path must not be empty or contain NUL bytes.")
        raw_p = Path(raw_str).expanduser()
        if ".." in raw_p.parts:
            raise ValueError(f"Path traversal ('..') is not permitted in UMA transfer: {raw_str!r}")
        name = raw_p.name
        if not name or name in {".", ".."} or name.startswith(".") or "/" in name or "\\" in name:
            raise ValueError(f"Unsafe or hidden transfer filename rejected: {name!r}")
        abs_p = Path(os.path.abspath(raw_p))
        if not allow_symlinks and (
            raw_p.is_symlink()
            or abs_p.is_symlink()
            or any(anc.is_symlink() for anc in abs_p.parents)
        ):
            raise ValueError(f"Symlink transfer rejected by UMA airlock policy: {raw_p}")
        resolved = raw_p.resolve()
        if not resolved.name or resolved.name.startswith("."):
            raise ValueError(f"Unsafe resolved transfer filename rejected: {resolved.name!r}")
        return resolved

    def transfer_file(
        self,
        actor: str,
        src_path: str | Path,
        *,
        max_bytes: int = UMA_MAX_TRANSFER_BYTES,
        allow_symlinks: bool = False,
    ) -> dict[str, Any]:
        """Enforce the ∀ consent invariant before allowing any artifact to cross domains."""
        if not isinstance(actor, str):
            raise ValueError("Transfer actor must be 'nick' or 'zoe'.")
        who = actor.strip().lower()
        if who not in {"nick", "zoe"}:
            raise ValueError("Transfer actor must be 'nick' or 'zoe'.")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer.")
        src = self._validate_transfer_source(src_path, allow_symlinks=allow_symlinks)
        with self._locked():
            st = self._read_state_unlocked()
            if st["gate"] != "SHARED":
                self._append_audit_unlocked("crossing_blocked", who, {"file": src.name, "gate": st["gate"]})
                raise PermissionError(f"UMA ∀ gate is {st['gate']} — mutual consent required before crossing.")
            if src.exists() and not src.is_file():
                raise ValueError(f"UMA transfer source must be a regular file: {src}")
            if not src.is_file():
                raise FileNotFoundError(f"File not found: {src}")
            byte_size = src.stat().st_size
            if byte_size > max_bytes:
                raise ValueError(f"Transfer exceeds max_bytes ({byte_size} > {max_bytes}).")
            dst_dir = self.nick_to_zoe if who == "nick" else self.zoe_to_nick
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            if dst.is_dir():
                raise ValueError(f"Destination target is a directory: {dst}")
            file_sha, staged_bytes = self._stage_transfer_file(
                src, dst, max_bytes=max_bytes, allow_symlinks=allow_symlinks
            )
            audit_sha = self._append_audit_unlocked(
                "crossing_ok",
                who,
                {"file": dst.name, "bytes": staged_bytes, "file_sha256": file_sha},
            )
            return {
                "ok": True,
                "actor": who,
                "dest": str(dst),
                "bytes": staged_bytes,
                "file_sha256": file_sha,
                "audit_sha": audit_sha[:16],
            }

    def write_shm_heartbeat(self, side: str, payload: dict[str, Any], *, slot: int = 0) -> bool:
        """Write an atomic magic-framed JSON record directly into a 4 KB slot of the 4 MB PCI ivshmem BAR."""
        slot_idx = _validate_shm_slot(slot)
        if not self.shm_path or not self.shm_path.exists():
            return False
        offset = slot_idx * UMA_SLOT_STRIDE
        record = {"side": side, "slot": slot_idx, "ts": int(time.time()), **payload}
        body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(body) > UMA_HDR_MAX:
            compact = {
                "side": str(side)[:64],
                "slot": slot_idx,
                "ts": int(time.time()),
                "gate": str(payload.get("gate", "PRIVATE"))[:16],
                "truncated": True,
            }
            body = json.dumps(compact, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(body) > UMA_HDR_MAX:
            return False
        try:
            fd = os.open(str(self.shm_path), os.O_RDWR)
            try:
                mm = mmap.mmap(fd, (slot_idx + 1) * UMA_SLOT_STRIDE, access=mmap.ACCESS_WRITE)
                try:
                    _write_shm_slot_bytes(mm, offset, body)
                    try:
                        mm.flush()
                    except OSError:
                        pass
                finally:
                    mm.close()
            finally:
                os.close(fd)
            return True
        except (OSError, ValueError):
            return False

    def read_shm_heartbeat(self, *, slot: int = 0) -> dict[str, Any] | None:
        """Read a 4 KB slot directly out of the 4 MB hardware PCI ivshmem BAR."""
        slot_idx = _validate_shm_slot(slot)
        if not self.shm_path or not self.shm_path.exists():
            return None
        offset = slot_idx * UMA_SLOT_STRIDE
        try:
            fd = os.open(str(self.shm_path), os.O_RDONLY)
            try:
                mm = mmap.mmap(fd, (slot_idx + 1) * UMA_SLOT_STRIDE, access=mmap.ACCESS_READ)
                try:
                    for attempt in range(5):
                        retry, data = _read_shm_slot_once(mm, offset)
                        if not retry:
                            return data
                        if attempt < 4:
                            time.sleep(0.001)
                    return None
                finally:
                    mm.close()
            finally:
                os.close(fd)
        except (OSError, ValueError):
            return None

    def read_all_zo3_slots(self) -> dict[int, dict[str, Any]]:
        """Read live vitals across Slot 0 (Coordinator) and Slots 1..3 (ZO3 sovereign KVM nodes)."""
        out: dict[int, dict[str, Any]] = {}
        for idx in range(4):
            hb = self.read_shm_heartbeat(slot=idx)
            if hb is not None:
                out[idx] = hb
        return out

    def format_zo3_health(self) -> list[str]:
        """Crisp 'Is Zoe OK?' cryptographic vitals & retention readout across all 4 MB UMA slots."""
        st = self.read_state()
        slots = self.read_all_zo3_slots()
        active_nodes = [k for k in (1, 2, 3) if k in slots]
        all_intact = all(bool(slots[k].get("chain_intact", True)) for k in active_nodes)
        verdict = "ALL ACTIVE ZO3 NODES HEALTHY & CHAIN-VERIFIED" if (active_nodes and all_intact) else (
            "STANDBY (no live ZO3 KVM nodes currently booted — run `/uma split` or `/uma zo3 launch`)"
            if not active_nodes else "WARNING: CHECK NODE CHAIN INTEGRITY"
        )
        rows = [
            f"ZO3 Multi-Zoe Hardware UMA Vitals  ::  {verdict}",
            f"  UMA Consent Gate : {st['gate']} (nick_allow={st['nick_allow']} · zoe_allow={st['zoe_allow']})",
            f"  4 MB PCI SHM BAR : {self.shm_path}  (active_zo3_nodes={len(active_nodes)}/3)",
        ]
        roles = {1: "ZO3-1 GEM/Artline", 2: "ZO3-2 Neuro/AmberCRT", 3: "ZO3-3 ∀ Verifier"}
        for idx in (1, 2, 3):
            hb = slots.get(idx)
            if hb:
                rows.append(
                    f"  [OK] Slot {idx} ({roles[idx]:<20}) : boot=#{hb.get('boot_count')} · "
                    f"chain_intact={hb.get('chain_intact', True)} · sha={hb.get('chain_sha', '')} · "
                    f"ip={hb.get('ip_addr')} · gate={hb.get('gate')} · theme={hb.get('theme', 'gem')}"
                )
            else:
                rows.append(f"  [--] Slot {idx} ({roles[idx]:<20}) : offline")
        rows.append("  Safety Guarantee : Read-only UEFI ISO + isolated ext4 ZOE-STATE disks + SHA-256 chain + GitHub/HDD backup.")
        return rows

    @staticmethod
    def _list_visible_names(folder: Path) -> list[str]:
        if not folder.is_dir():
            return []
        return sorted(p.name for p in folder.iterdir() if not p.name.startswith("."))

    def format_status(self) -> list[str]:
        st = self.read_state()
        shm = self.read_shm_heartbeat()
        z2n = self._list_visible_names(self.zoe_to_nick)
        n2z = self._list_visible_names(self.nick_to_zoe)
        try:
            audit_n = (
                len(self.audit_path.read_text(encoding="utf-8", errors="replace").splitlines())
                if self.audit_path.is_file()
                else 0
            )
        except OSError:
            audit_n = 0
        shm_txt = f"ACTIVE ({shm.get('side')} · gate={shm.get('gate')})" if shm else "ready (4 MB /dev/shm/zoe-uma-bar.shm)"
        return [
            "Zoe-GEM × Ubuntu Hardware UMA Bridge  [ GEM / AI (Left 50%) <-> UMA (∀) <-> YOU Ubuntu (Right 50%) ]",
            f"  Gate State : {st['gate']}  (nick_allow={st['nick_allow']} · zoe_allow={st['zoe_allow']} · reason={st.get('reason', '')})",
            f"  PCI SHM 4M : {shm_txt}",
            f"  Airlock 9p : {self.bridge_dir}  (audit_events={audit_n})",
            f"  Zoe -> Nick: {', '.join(z2n) if z2n else '(empty)'}",
            f"  Nick -> Zoe: {', '.join(n2z) if n2z else '(empty)'}",
            "  Commands   : /uma split | /uma grant | /uma lock | /uma send <file> | /uma inbox | /uma audit",
        ]

"""First-seen-host baseline -- a persisted memory of where egress has gone before.

A common injection move is to reach a brand-new destination the task has never
contacted. An allowlist is the strong control, but for tasks that must talk to a
broad or dynamic set of hosts, a *first-seen* tripwire adds a deterministic
"this is new, hold it" signal without any model in the loop.

The baseline is a persisted set of hosts already approved/seen. First contact
with a host not in the set escalates (held for human / sandbox). Once approved,
the host is remembered so steady-state operation is quiet.

Deterministic, append-only by default, JSON-backed. No judgment, just memory.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional, Set

from .net import canonical_host


class HostBaseline:
    def __init__(self, path: Optional[str] = None, seed: Optional[Set[str]] = None):
        self._path = path
        self._lock = threading.RLock()
        self._seen: Set[str] = set(h.lower() for h in (seed or set()))
        if path and os.path.exists(path):
            self._load()

    def seen(self, target: str) -> bool:
        host = canonical_host(target)
        if not host:
            return False
        with self._lock:
            return host in self._seen

    def is_new(self, target: str) -> bool:
        host = canonical_host(target)
        if not host:
            # Unparseable host: treat as new (suspicious) rather than known.
            return True
        with self._lock:
            return host not in self._seen

    def remember(self, target: str) -> None:
        host = canonical_host(target)
        if not host:
            return
        with self._lock:
            if host not in self._seen:
                self._seen.add(host)
                self._persist()

    def hosts(self) -> Set[str]:
        with self._lock:
            return set(self._seen)

    # --- persistence ------------------------------------------------------

    def _persist(self) -> None:
        if not self._path:
            return
        tmp = self._path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(sorted(self._seen), fh)
        os.replace(tmp, self._path)

    def _load(self) -> None:
        try:
            with open(self._path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(data, list):
            self._seen |= {str(h).lower() for h in data}

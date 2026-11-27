"""Cross-step taint ledger -- closes the taint-laundering hole.

The scaffold tracks taint *within* one action. But a real injection launders
taint across steps:

    1. read an untrusted web page            -> untrusted bytes in hand
    2. WRITE those bytes to ./project/out/x   -> allowed (inside write_roots)
    3. READ ./project/out/x back             -> the read returns "fresh" bytes
                                                with no memory they were tainted
    4. POST the bytes to an allowed host      -> clean, because step 3 lost taint

Each individual step looks fine. The taint has to *persist on the resource*. The
ledger is that memory: when tainted bytes are written to a path (or any resource
id), the path is recorded as tainted; a later read of that path re-attaches the
taint. It is a deterministic data structure, not a model.

Keying is by canonical resource id:
  - filesystem: os.path.realpath(path)
  - network/other: the raw target string (callers may normalize first)

Persistence is optional (a JSON file) so taint survives across process restarts
of a long-running agent. In-memory is the default.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional

from .provenance import TaintSet, TaintTag, Trust


def resource_id(kind: str, target: str) -> str:
    """Canonical key for a resource. Files are realpath'd so symlinks/.. collapse."""
    if kind == "file":
        return "file:" + os.path.realpath(target)
    return f"{kind}:{target}"


class TaintLedger:
    """Remembers which resources hold untrusted-derived data.

    Thread-safe enough for a single agent process. The stored value per key is
    the merged TaintSet that was written there.
    """

    def __init__(self, path: Optional[str] = None):
        self._path = path
        self._lock = threading.RLock()
        self._taint: Dict[str, TaintSet] = {}
        if path and os.path.exists(path):
            self._load()

    # --- recording --------------------------------------------------------

    def record_write(self, kind: str, target: str, taint: TaintSet) -> None:
        """Note that `target` now holds data carrying `taint`.

        Only untrusted taint is worth persisting; writing trusted data does not
        *clear* prior taint on the resource (an attacker could otherwise launder
        by overwriting with one trusted byte, then appending). We merge instead.
        """
        key = resource_id(kind, target)
        with self._lock:
            existing = self._taint.get(key)
            merged = taint if existing is None else existing.merge(taint)
            if merged.is_tainted:
                self._taint[key] = merged
                self._persist()

    def record_untrusted(self, kind: str, target: str, origin: str) -> None:
        self.record_write(kind, target,
                          TaintSet.of(TaintTag(Trust.UNTRUSTED, origin)))

    # --- querying ---------------------------------------------------------

    def taint_for(self, kind: str, target: str) -> TaintSet:
        """Taint to re-attach when reading `target`. Empty TaintSet if clean."""
        key = resource_id(kind, target)
        with self._lock:
            return self._taint.get(key, TaintSet())

    def is_tainted(self, kind: str, target: str) -> bool:
        return self.taint_for(kind, target).is_tainted

    def clear(self) -> None:
        with self._lock:
            self._taint = {}
            self._persist()

    # --- persistence ------------------------------------------------------

    def _persist(self) -> None:
        if not self._path:
            return
        # Serialize as {key: [[trust, origin], ...]}.
        data = {
            key: [[t.trust.value, t.origin] for t in ts.tags]
            for key, ts in self._taint.items()
        }
        tmp = self._path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(data, fh)
        os.replace(tmp, self._path)

    def _load(self) -> None:
        # A persisted ledger is attacker-reachable: it is just a JSON file on disk,
        # and an injection that can write one byte of it (or a corrupt write that
        # half-finished) must not crash the agent at startup. So the whole load is
        # fail-soft -- a malformed file, a non-dict top level, a bad trust string,
        # or a misshaped entry drops that entry (or the whole file) and leaves the
        # in-memory ledger empty rather than raising out of __init__. Mirrors
        # HostBaseline._load. (raw finding: poisoned-ledger load crash)
        try:
            with open(self._path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for key, tags in data.items():
            try:
                ts = TaintSet.from_tags(
                    TaintTag(Trust(tr), origin) for tr, origin in tags)
            except (ValueError, TypeError, AttributeError):
                continue  # unknown trust level / misshaped entry -> drop it
            self._taint[str(key)] = ts

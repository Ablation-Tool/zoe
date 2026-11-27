"""Provenance / taint tracking.

This is the "labeling" layer. The core idea behind the whole gate is that the
*system* already knows where data came from -- you never ask the model to
self-report whether something is trusted. You tag bytes at the point of
ingestion and let taint propagate through the data flow.

  TRUSTED   = came from the user, or from your own system/config.
  UNTRUSTED = came from an external read: a web page, a file you didn't author,
              a tool/MCP result, anything an attacker could have authored.

An action whose inputs include *any* untrusted data is itself tainted, and is
therefore subject to stricter policy in policy.py.

TODO(claude-code):
  - Wire this at every ingestion seam. Whenever a tool fetches bytes (HTTP,
    file read, MCP call), wrap the result in `tainted(value, Trust.UNTRUSTED,
    origin=...)` so the taint set is populated automatically rather than by hand.
  - Consider field-level taint for structured results (e.g. JSON) so a single
    untrusted field doesn't over-taint an otherwise-trusted record.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, FrozenSet, Iterable, Set


class Trust(Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


@dataclass(frozen=True)
class TaintTag:
    """One provenance fact: a trust level plus where it came from."""
    trust: Trust
    origin: str  # e.g. "user", "file:./project/README.md", "web:example.com"


@dataclass(frozen=True)
class TaintSet:
    """The set of provenance facts feeding a value or an action.

    Immutable. Merge sets as data flows together; the result is tainted if any
    contributing source was untrusted.
    """
    tags: FrozenSet[TaintTag] = frozenset()

    @classmethod
    def of(cls, *tags: TaintTag) -> "TaintSet":
        return cls(frozenset(tags))

    @classmethod
    def from_tags(cls, tags: Iterable[TaintTag]) -> "TaintSet":
        return cls(frozenset(tags))

    @property
    def is_tainted(self) -> bool:
        """True if anything untrusted contributed to this value/action."""
        return any(t.trust is Trust.UNTRUSTED for t in self.tags)

    @property
    def untrusted_origins(self) -> Set[str]:
        return {t.origin for t in self.tags if t.trust is Trust.UNTRUSTED}

    def merge(self, *others: "TaintSet") -> "TaintSet":
        merged = set(self.tags)
        for o in others:
            merged |= set(o.tags)
        return TaintSet(frozenset(merged))


@dataclass(frozen=True)
class Tainted:
    """A value carrying its provenance. Use as the wrapper your tools return."""
    value: Any
    taint: TaintSet

    @classmethod
    def trusted(cls, value: Any, origin: str = "user") -> "Tainted":
        return cls(value, TaintSet.of(TaintTag(Trust.TRUSTED, origin)))

    @classmethod
    def untrusted(cls, value: Any, origin: str) -> "Tainted":
        return cls(value, TaintSet.of(TaintTag(Trust.UNTRUSTED, origin)))


def tainted(value: Any, trust: Trust, origin: str) -> Tainted:
    """Convenience constructor for a single-source tainted value."""
    return Tainted(value, TaintSet.of(TaintTag(trust, origin)))

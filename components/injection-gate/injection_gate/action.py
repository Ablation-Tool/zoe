"""The unit the gate evaluates: a proposed action, *before* it runs.

This is the analogue of the original project's `Observation`, but constructed
*ahead* of execution rather than recorded after it. The model proposes an
ActionRequest; the PolicyEngine decides; the Enforcer executes or blocks.

Every field here is something a deterministic rule can reason about WITHOUT
trusting the model's judgment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from .provenance import TaintSet


class Capability(Enum):
    """Coarse class of side effect. Drives least-privilege scoping."""
    READ = "read"
    WRITE = "write"
    EXEC = "exec"
    NETWORK = "network"
    DELETE = "delete"


@dataclass
class ActionRequest:
    """A proposed tool call awaiting a policy decision."""
    agent_id: str
    capability: Capability
    target: str                      # path, host, or URL the action touches
    args: Dict[str, Any] = field(default_factory=dict)
    taint: TaintSet = field(default_factory=TaintSet)  # taint of everything feeding this

    # Soft, optional signals -------------------------------------------------
    declared_task: str = ""          # what the agent *says* it's doing.
    #   NOTE: declared_task is a SOFT signal only. Do not let a model-based
    #   "does this match the task?" check be the gate -- the checker can be
    #   injected too. Use it for logging/triage, never as the deciding factor.

    # Strong, deterministic signal ------------------------------------------
    target_from_untrusted: bool = False
    #   True when the destination/target itself was lifted out of untrusted
    #   content (e.g. a URL that appeared in a fetched web page). Tainted data
    #   going to an untrusted-derived sink is the classic exfiltration shape.

    @property
    def is_tainted(self) -> bool:
        return self.taint.is_tainted

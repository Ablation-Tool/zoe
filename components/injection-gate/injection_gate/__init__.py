"""injection-gate: a deterministic, proposal->gate->execute enforcement layer
that bounds the blast radius of (indirect) prompt injection in tool-using agents.

Defense-in-depth, not a silver bullet. Pairs provenance/taint + least-privilege
capabilities + a deterministic policy gate + provenance-aware egress control,
with cross-step taint persistence, SSRF/credential/DNS-exfil controls, a real
escalation path, and a CaMeL-style control/data split.
"""
from .provenance import Trust, TaintTag, TaintSet, Tainted, tainted
from .action import Capability, ActionRequest
from .policy import (
    Verdict, Decision, PolicyRule, PolicyEngine, PolicyContext,
    CapabilityGrant, default_rules, hardened_engine, harden,
)
from .enforcer import Enforcer, ActionBlocked, EscalationHandler, deny_on_escalate
from .adapters import GatingAdapter, ExampleToolAdapter
from .tools import GatedTools, Filesystem, HttpTransport
from .ledger import TaintLedger, resource_id
from .baseline import HostBaseline
from . import net, credentials, escalation, camel

__all__ = [
    # provenance
    "Trust", "TaintTag", "TaintSet", "Tainted", "tainted",
    # action
    "Capability", "ActionRequest",
    # policy
    "Verdict", "Decision", "PolicyRule", "PolicyEngine", "PolicyContext",
    "CapabilityGrant", "default_rules", "hardened_engine", "harden",
    # enforcer
    "Enforcer", "ActionBlocked", "EscalationHandler", "deny_on_escalate",
    # adapters / real tools
    "GatingAdapter", "ExampleToolAdapter",
    "GatedTools", "Filesystem", "HttpTransport",
    # cross-step taint + baseline
    "TaintLedger", "resource_id", "HostBaseline",
    # submodules
    "net", "credentials", "escalation", "camel",
]

__version__ = "0.1.0"

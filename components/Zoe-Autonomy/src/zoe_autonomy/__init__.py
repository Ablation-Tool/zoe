"""Operational full self-governing autonomy through Zoe and Accessible Volume."""

from .actuation import ActuationPolicy
from .agents import AgentGateway
from .explore import WebExplorer
from .metrics import accessible_volume, effective_perception, kl_divergence_bits
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, SandboxPolicy
from .self_reflection import run_reflection, verify_reflection


def __getattr__(name):
    if name == "EventCausalEngine":
        from .event_autonomy import EventCausalEngine
        return EventCausalEngine
    raise AttributeError(name)

__all__ = [
    "ActuationPolicy",
    "AgentGateway",
    "WebExplorer",
    "accessible_volume",
    "effective_perception",
    "kl_divergence_bits",
    "BoundedAutonomyLoop",
    "Candidate",
    "InMemoryEnvironment",
    "SandboxPolicy",
    "run_reflection",
    "verify_reflection",
    "EventCausalEngine",
]

__version__ = "0.8.0"

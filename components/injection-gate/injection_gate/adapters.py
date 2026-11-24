"""The interception seam.

In the original project, the adapter pattern wired a host system in *for
logging*. Here the same seam is repurposed to *gate*: every tool call the agent
wants to make is routed through `GatingAdapter.call`, which builds an
ActionRequest and runs it past the Enforcer before the side effect happens.

This is the one integration point you wire into your agent's tool dispatch.
Subclass it to map your specific toolset onto capabilities + taint.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .action import ActionRequest, Capability
from .enforcer import Enforcer
from .provenance import TaintSet


class GatingAdapter:
    def __init__(self, enforcer: Enforcer):
        self.enforcer = enforcer

    def call(
        self,
        *,
        agent_id: str,
        capability: Capability,
        target: str,
        run: Callable[[], Any],
        args: Optional[Dict[str, Any]] = None,
        taint: Optional[TaintSet] = None,
        declared_task: str = "",
        target_from_untrusted: bool = False,
    ) -> Any:
        req = ActionRequest(
            agent_id=agent_id,
            capability=capability,
            target=target,
            args=args or {},
            taint=taint or TaintSet(),
            declared_task=declared_task,
            target_from_untrusted=target_from_untrusted,
        )
        return self.enforcer.guard(req, run)


# ---------------------------------------------------------------------------
# Example concrete adapter sketch.
#
# This stays as a minimal teaching example that hand-tags taint. The REAL,
# wired stack is `injection_gate.tools.GatedTools`: it taints at ingestion,
# persists taint across steps via the ledger, and computes target_from_untrusted
# automatically. Reach for GatedTools in production; keep this for the docs.
# ---------------------------------------------------------------------------

class ExampleToolAdapter(GatingAdapter):
    """Maps a tiny toolset (read_file, http_post) onto gated calls.

    Teaching example only -- taint is passed by hand. See
    `injection_gate.tools.GatedTools` for the wired stack that taints at
    ingestion and tracks taint across steps.
    """

    def read_file(self, agent_id: str, path: str, taint: Optional[TaintSet] = None) -> Any:
        return self.call(
            agent_id=agent_id,
            capability=Capability.READ,
            target=path,
            taint=taint,
            run=lambda: f"<contents of {path}>",  # TODO: real read
        )

    def http_post(self, agent_id: str, url: str, body: Any, body_taint: TaintSet,
                  url_from_untrusted: bool = False) -> Any:
        return self.call(
            agent_id=agent_id,
            capability=Capability.NETWORK,
            target=url,
            args={"body": body},
            taint=body_taint,                      # taint of what's being sent
            target_from_untrusted=url_from_untrusted,
            run=lambda: f"<POST to {url}>",        # TODO: real request
        )

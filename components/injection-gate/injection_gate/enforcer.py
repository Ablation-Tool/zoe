"""The Enforcer: turns a Decision into an outcome.

This is where the design diverges hardest from a monitor. A monitor would log
that something happened. The Enforcer sits *synchronously in front of*
execution and decides whether it happens at all:

  ALLOW    -> run the action.
  DENY     -> raise ActionBlocked; the action never runs.
  ESCALATE -> hand to `on_escalate` (human approval, or sandboxed dry-run).
              If it returns True, run; otherwise block.

The damage from injection happens *inside* the action (read secret + send it
out). Blocking after the fact is a post-mortem. Blocking before is a defense.
"""
from __future__ import annotations

from typing import Any, Callable

from .action import ActionRequest
from .policy import Decision, PolicyContext, PolicyEngine, Verdict


class ActionBlocked(Exception):
    def __init__(self, request: ActionRequest, decision: Decision):
        self.request = request
        self.decision = decision
        super().__init__(
            f"blocked {request.capability.value} -> {request.target} "
            f"[{decision.rule}: {decision.reason}]"
        )


# An escalation handler decides whether a held action proceeds.
# Default denies everything that reaches escalation (fail closed). Replace with
# a real human-in-the-loop prompt or a sandboxed dry-run + re-check.
EscalationHandler = Callable[[ActionRequest, Decision], bool]


def deny_on_escalate(request: ActionRequest, decision: Decision) -> bool:
    return False


class Enforcer:
    def __init__(self, engine: PolicyEngine, ctx: PolicyContext,
                 on_escalate: EscalationHandler = deny_on_escalate,
                 audit: "Callable[[ActionRequest, Decision], None] | None" = None):
        self.engine = engine
        self.ctx = ctx
        self.on_escalate = on_escalate
        self.audit = audit  # optional: still log every decision for observability

    def decide(self, request: ActionRequest) -> Decision:
        decision = self.engine.evaluate(request, self.ctx)
        if self.audit:
            self.audit(request, decision)
        return decision

    def guard(self, request: ActionRequest, execute: Callable[[], Any]) -> Any:
        """Evaluate, then run or block. `execute` is the actual side-effecting call."""
        decision = self.decide(request)
        if decision.verdict is Verdict.ALLOW:
            return execute()
        if decision.verdict is Verdict.ESCALATE:
            if self.on_escalate(request, decision):
                return execute()
        raise ActionBlocked(request, decision)

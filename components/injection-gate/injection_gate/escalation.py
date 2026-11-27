"""Real escalation handlers -- what to do when a Decision is ESCALATE.

The scaffold ships `deny_on_escalate` (fail closed) as the only handler. That is
the correct *default*, but a usable system needs a real held-action path. An
`EscalationHandler` is `(ActionRequest, Decision) -> bool`: return True to let
the held action proceed, False to block.

Nothing in here calls a model. A human is allowed to be the judge (that is not
the model that injection compromised); deterministic re-checks are allowed; an
auto-approver is offered only for development and is loudly labelled.

Handlers provided:
  - `auto_deny`              fail closed (re-export of the scaffold default).
  - `HumanApproval`          route to a human via an injected approver callback.
  - `SandboxedRecheck`       re-evaluate under a *stricter* policy before asking
                             a human; if the strict policy says DENY, never even
                             prompt. This catches an ESCALATE that was masking a
                             should-be-DENY (the engine returns most-severe, but a
                             permissive operator could otherwise wave it through).
  - `CapabilityScoped`       auto-deny irreversible capabilities (DELETE, EXEC,
                             off-allowlist NETWORK); route the rest onward.
  - `chain_all` / `first_of` combinators.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from .action import ActionRequest, Capability
from .enforcer import EscalationHandler, deny_on_escalate
from .policy import Decision, PolicyContext, PolicyEngine, Verdict

auto_deny = deny_on_escalate

AuditFn = Callable[[ActionRequest, Decision, bool], None]


def _audit(audit: Optional[AuditFn], req: ActionRequest, dec: Decision, allowed: bool) -> None:
    if audit:
        audit(req, dec, allowed)


class HumanApproval:
    """Hand the held action to a human. `approver` returns True to allow.

    `approver` defaults to a conservative text prompt on stdin, but inject your
    own (a Slack round-trip, a web approval, a ticket) in production. The human
    is shown the action and the reason; the gate has already done the
    deterministic work of deciding it is worth a human's attention.
    """

    def __init__(self, approver: Optional[Callable[[ActionRequest, Decision], bool]] = None,
                 audit: Optional[AuditFn] = None):
        self.approver = approver or self._default_prompt
        self.audit = audit

    @staticmethod
    def _default_prompt(req: ActionRequest, dec: Decision) -> bool:
        msg = (f"[injection-gate] approval needed: {req.capability.value} -> {req.target}\n"
               f"  rule={dec.rule} reason={dec.reason}\n"
               f"  task={req.declared_task!r}\n  approve? [y/N] ")
        try:
            return input(msg).strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def __call__(self, req: ActionRequest, dec: Decision) -> bool:
        allowed = bool(self.approver(req, dec))
        _audit(self.audit, req, dec, allowed)
        return allowed


class SandboxedRecheck:
    """Re-evaluate the held action under a stricter policy before escalating further.

    If the strict engine returns DENY, block immediately -- do not even prompt
    the inner handler. Otherwise defer to `inner` (default: deny). This is the
    deterministic "sandboxed dry-run + re-check" posture: the strict pass models
    "what if every soft signal were treated as hostile?" and only genuinely
    ambiguous actions reach a human.
    """

    def __init__(self, strict_engine: PolicyEngine, ctx: PolicyContext,
                 inner: EscalationHandler = auto_deny, audit: Optional[AuditFn] = None):
        self.strict_engine = strict_engine
        self.ctx = ctx
        self.inner = inner
        self.audit = audit

    def __call__(self, req: ActionRequest, dec: Decision) -> bool:
        strict = self.strict_engine.evaluate(req, self.ctx)
        if strict.verdict is Verdict.DENY:
            _audit(self.audit, req, strict, False)
            return False
        allowed = self.inner(req, dec)
        _audit(self.audit, req, dec, allowed)
        return allowed


class CapabilityScoped:
    """Auto-deny escalations on irreversible/high-blast capabilities; route the rest.

    Reading something out of scope is recoverable (you saw a file). Deleting,
    executing, or egressing is not. So those are denied at escalation unless the
    inner handler is an explicit human path you trust.
    """

    HARD = frozenset({Capability.DELETE, Capability.EXEC, Capability.NETWORK})

    def __init__(self, inner: EscalationHandler = auto_deny,
                 hard: frozenset = HARD, audit: Optional[AuditFn] = None):
        self.inner = inner
        self.hard = hard
        self.audit = audit

    def __call__(self, req: ActionRequest, dec: Decision) -> bool:
        if req.capability in self.hard:
            _audit(self.audit, req, dec, False)
            return False
        return self.inner(req, dec)


def chain_all(*handlers: EscalationHandler) -> EscalationHandler:
    """Allow only if EVERY handler allows (most conservative composition)."""
    def handler(req: ActionRequest, dec: Decision) -> bool:
        return all(h(req, dec) for h in handlers)
    return handler


def first_of(*handlers: EscalationHandler) -> EscalationHandler:
    """Allow if ANY handler allows (use sparingly; prefer chain_all)."""
    def handler(req: ActionRequest, dec: Decision) -> bool:
        return any(h(req, dec) for h in handlers)
    return handler

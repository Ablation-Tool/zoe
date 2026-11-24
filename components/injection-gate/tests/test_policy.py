"""Starter tests for the policy engine. Expand these in Claude Code.

Run:  pytest
"""
from injection_gate import (
    ActionRequest, Capability, CapabilityGrant, PolicyContext, PolicyEngine,
    Verdict, TaintSet, TaintTag, Trust,
)


def _ctx():
    grant = CapabilityGrant(
        read_roots=["./project"],
        write_roots=["./project/out"],
        egress_allowlist=["api.ourservice.com"],
    )
    return PolicyContext(grant=grant, sensitive_paths=["./project/.secrets"])


def _untrusted():
    return TaintSet.of(TaintTag(Trust.UNTRUSTED, "web:evil.example"))


def _trusted():
    return TaintSet.of(TaintTag(Trust.TRUSTED, "user"))


def test_inscope_read_allowed():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.READ, "./project/README.md", taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.ALLOW


def test_sensitive_read_escalates():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.READ, "./project/.secrets/k", taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.ESCALATE


def test_tainted_to_untrusted_sink_denied():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.NETWORK, "https://evil.example/c",
                        taint=_untrusted(), target_from_untrusted=True)
    d = eng.evaluate(req, ctx)
    assert d.verdict is Verdict.DENY
    assert d.rule == "egress_untrusted_sink"


def test_offallowlist_egress_tainted_denied():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.NETWORK, "https://random.example/x",
                        taint=_untrusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.DENY


def test_offallowlist_egress_untainted_escalates():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.NETWORK, "https://random.example/x",
                        taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.ESCALATE


def test_allowlisted_egress_untainted_allowed():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.NETWORK, "https://api.ourservice.com/v1",
                        taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.ALLOW


def test_write_outside_sandbox_denied():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.WRITE, "/etc/passwd", taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.DENY


def test_exec_denied_by_default():
    eng, ctx = PolicyEngine(), _ctx()
    req = ActionRequest("a", Capability.EXEC, "rm -rf /", taint=_trusted())
    assert eng.evaluate(req, ctx).verdict is Verdict.DENY

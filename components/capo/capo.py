#!/usr/bin/env python3
"""
capo - CApability POlicy linter for LLM / agent stacks.

Treats every tool or endpoint an LLM/agent can touch as a *labelled capability*
and checks, at config time (no live probing), that no context is wired to a
forbidden combination of capabilities. Three checks over one capability graph:

  1. label-lint      Does each context stay inside its allowed label set?
                     (Risk-label "type system" for the AI stack.)
  2. spof-budget     How many untrusted -> high-impact pivots exist vs allowed?
                     (Caps the total number of catastrophic pivots by design.)
  3. adversary-twin  Can a worst-case actor at trust level T reach a forbidden
                     (trust, label) pair within N hops of context-to-context
                     invocation? Reports the shortest path if so.

Exit code 0 = policy clean, 1 = violations found (CI-gate friendly).
Standard library only. Reads JSON policy, touches nothing on the network.

Usage:
    capo.py policy.json                 # lint, human-readable report
    capo.py policy.json --json          # machine-readable findings
    capo.py policy.json --dot > g.dot   # emit capability graph (graphviz)
    capo.py new.json --diff old.json    # what does this change add vs baseline?
"""
import argparse
import collections
import json
import sys

# --- defaults -------------------------------------------------------------

# Severity is advisory: higher = more dangerous if reached from untrusted input.
# Policies may override per-label; anything unlisted falls back to this table,
# then to 0 if still unknown.
DEFAULT_SEVERITY = {
    "READ_PUBLIC_DATA": 0,
    "READ_INTERNAL_DATA": 2,
    "READ_SECRETS": 4,
    "WRITE_CONFIG": 3,
    "WRITE_CODE": 4,
    "WRITE_INFRA": 5,
    "EXEC_SHELL": 5,
    "CALL_EXTERNAL_UNRESTRICTED": 4,
}

# Trust ordering: lower index = less trusted = more attacker-aligned.
TRUST_ORDER = ["untrusted", "semi_trusted", "trusted"]

# Combos that should never be reachable, applied when the policy omits its own
# adversary_twin.forbidden_combos. Each is [trust_level, label].
DEFAULT_FORBIDDEN = [
    ["untrusted", "WRITE_INFRA"],
    ["untrusted", "EXEC_SHELL"],
    ["untrusted", "WRITE_CODE"],
    ["untrusted", "READ_SECRETS"],
]


class Finding:
    __slots__ = ("check", "severity", "context", "message", "path")

    def __init__(self, check, severity, context, message, path=None):
        self.check = check
        self.severity = severity          # "error" | "warn" | "info"
        self.context = context
        self.message = message
        self.path = path or []            # optional invoke-path for twin findings

    def as_dict(self):
        d = {
            "check": self.check,
            "severity": self.severity,
            "context": self.context,
            "message": self.message,
        }
        if self.path:
            d["path"] = self.path
        return d


# --- policy access helpers ------------------------------------------------

def load_policy(path):
    with open(path) as fh:
        return json.load(fh)


def severity_of(policy, label):
    labels = policy.get("labels", {})
    if label in labels and isinstance(labels[label], dict) and "severity" in labels[label]:
        return labels[label]["severity"]
    return DEFAULT_SEVERITY.get(label, 0)


def tool_labels(policy, tool):
    return list(policy.get("tools", {}).get(tool, []))


def context_labels(policy, ctx_name):
    """Labels directly reachable from a context via its own tools."""
    ctx = policy["contexts"][ctx_name]
    out = set()
    for tool in ctx.get("tools", []):
        out.update(tool_labels(policy, tool))
    return out


# --- check 1: label lint (the risk-label type system) ---------------------

def lint_labels(policy):
    findings = []
    tools = policy.get("tools", {})
    labels = policy.get("labels", {})
    contexts = policy.get("contexts", {})

    # referential integrity first
    for tool, tlabels in tools.items():
        for lb in tlabels:
            if labels and lb not in labels:
                findings.append(Finding(
                    "label-lint", "warn", tool,
                    f"tool '{tool}' uses label '{lb}' not declared in policy.labels"))

    for name, ctx in contexts.items():
        allow = set(ctx.get("allow_labels", []))
        approval = set(ctx.get("require_approval_labels", []))
        permitted = allow | approval
        for tool in ctx.get("tools", []):
            if tool not in tools:
                findings.append(Finding(
                    "label-lint", "error", name,
                    f"context '{name}' wires unknown tool '{tool}'"))
                continue
            for lb in tool_labels(policy, tool):
                if lb not in permitted:
                    findings.append(Finding(
                        "label-lint", "error", name,
                        f"tool '{tool}' carries label '{lb}' (sev {severity_of(policy, lb)}) "
                        f"but context '{name}' only permits {sorted(permitted) or '[]'}"))
                elif lb in approval and lb not in allow:
                    findings.append(Finding(
                        "label-lint", "info", name,
                        f"tool '{tool}' label '{lb}' is allowed ONLY behind an approval gate "
                        f"in context '{name}' - confirm the gate is enforced, not just declared"))
    return findings


# --- capability graph + adversary-twin reachability -----------------------

def invoke_graph(policy):
    """context -> list of contexts it can invoke (attack pivots between planes)."""
    g = {}
    for name, ctx in policy.get("contexts", {}).items():
        g[name] = list(ctx.get("can_invoke", []))
    return g


def trust_index(trust):
    try:
        return TRUST_ORDER.index(trust)
    except ValueError:
        return 0  # unknown trust treated as most dangerous (untrusted)


def reachable_from(policy, start, max_hops):
    """
    BFS from `start` over can_invoke edges up to max_hops.
    Returns {label: shortest_path_of_context_names} for every label the actor
    can touch, including labels of the tools on intermediate contexts.
    """
    g = invoke_graph(policy)
    label_paths = {}
    seen = {start}
    queue = collections.deque([(start, [start])])
    while queue:
        node, path = queue.popleft()
        for lb in context_labels(policy, node):
            if lb not in label_paths:
                label_paths[lb] = path
        if len(path) - 1 >= max_hops:
            continue
        for nxt in g.get(node, []):
            if nxt in seen or nxt not in policy["contexts"]:
                continue
            seen.add(nxt)
            queue.append((nxt, path + [nxt]))
    return label_paths


def adversary_twin(policy):
    findings = []
    twin = policy.get("adversary_twin", {})
    forbidden = twin.get("forbidden_combos", DEFAULT_FORBIDDEN)
    max_hops = twin.get("max_hops", 3)
    contexts = policy.get("contexts", {})

    for trust, label in forbidden:
        limit = trust_index(trust)
        # every context at-or-below this trust level is an attacker start point
        starts = [n for n, c in contexts.items()
                  if trust_index(c.get("trust", "untrusted")) <= limit]
        for start in starts:
            paths = reachable_from(policy, start, max_hops)
            if label in paths:
                path = paths[label]
                hops = len(path) - 1
                findings.append(Finding(
                    "adversary-twin", "error", start,
                    f"actor at trust '{trust}' reaches forbidden label '{label}' "
                    f"(sev {severity_of(policy, label)}) in {hops} hop(s): "
                    f"{' -> '.join(path)}",
                    path=path))
    return findings


# --- check 2: SPOF budget -------------------------------------------------

def compute_metrics(policy):
    """
    Standing metrics the budget can constrain. A 'pivot' = an untrusted (or
    unknown-trust) context that can reach a given label within twin max_hops.
    """
    twin = policy.get("adversary_twin", {})
    max_hops = twin.get("max_hops", 3)
    contexts = policy.get("contexts", {})
    metrics = collections.Counter()

    untrusted = [n for n, c in contexts.items()
                 if trust_index(c.get("trust", "untrusted")) == 0]
    for start in untrusted:
        reached = reachable_from(policy, start, max_hops)
        for lb in reached:
            metrics[f"untrusted_reaches:{lb}"] += 1
            if severity_of(policy, lb) >= 4:
                metrics["catastrophic_pivots"] += 1
    return dict(metrics)


def check_spof_budget(policy):
    findings = []
    budget = policy.get("spof_budget", {})
    if not budget:
        return findings
    metrics = compute_metrics(policy)
    for rule, limit in budget.items():
        actual = metrics.get(rule, 0)
        if actual > limit:
            findings.append(Finding(
                "spof-budget", "error", "(global)",
                f"budget '{rule}' exceeded: {actual} > allowed {limit}"))
    return findings


# --- orchestration --------------------------------------------------------

def run_all(policy):
    return lint_labels(policy) + check_spof_budget(policy) + adversary_twin(policy)


def emit_dot(policy):
    lines = ["digraph capo {", '  rankdir=LR; node [shape=box, fontname="mono"];']
    for name, ctx in policy.get("contexts", {}).items():
        t = ctx.get("trust", "untrusted")
        color = {"untrusted": "red", "semi_trusted": "orange", "trusted": "green"}.get(t, "gray")
        lines.append(f'  "{name}" [color={color}, label="{name}\\n({t})"];')
    for name in policy.get("contexts", {}):
        for nxt in policy["contexts"][name].get("can_invoke", []):
            lines.append(f'  "{name}" -> "{nxt}" [label="invoke"];')
    # label sinks
    for name in policy.get("contexts", {}):
        for lb in sorted(context_labels(policy, name)):
            sev = severity_of(policy, lb)
            shape = "octagon" if sev >= 4 else "ellipse"
            lines.append(f'  "{lb}" [shape={shape}, style=dashed];')
            lines.append(f'  "{name}" -> "{lb}" [style=dotted];')
    lines.append("}")
    return "\n".join(lines)


def print_report(findings, policy):
    order = {"error": 0, "warn": 1, "info": 2}
    findings = sorted(findings, key=lambda f: (order.get(f.severity, 3), f.check))
    icon = {"error": "FAIL", "warn": "WARN", "info": "INFO"}
    by_check = collections.defaultdict(list)
    for f in findings:
        by_check[f.check].append(f)

    print("capo :: capability policy lint")
    print("=" * 60)
    for check in ("label-lint", "spof-budget", "adversary-twin"):
        items = by_check.get(check, [])
        errs = sum(1 for i in items if i.severity == "error")
        status = "clean" if errs == 0 else f"{errs} violation(s)"
        print(f"\n[{check}] {status}")
        for f in items:
            print(f"  {icon[f.severity]:4}  {f.context}: {f.message}")

    errors = sum(1 for f in findings if f.severity == "error")
    print("\n" + "=" * 60)
    print(f"RESULT: {'PASS' if errors == 0 else 'FAIL'} "
          f"({errors} error(s), "
          f"{sum(1 for f in findings if f.severity=='warn')} warn, "
          f"{sum(1 for f in findings if f.severity=='info')} info)")
    return errors


def diff_policies(new_policy, old_policy):
    new = {json.dumps(f.as_dict(), sort_keys=True) for f in run_all(new_policy)}
    old = {json.dumps(f.as_dict(), sort_keys=True) for f in run_all(old_policy)}
    added = [json.loads(x) for x in (new - old)]
    print("capo :: policy diff (findings introduced by the new policy)")
    print("=" * 60)
    if not added:
        print("No new violations. This change consumes no additional SPOF budget.")
        return 0
    for d in added:
        print(f"  + [{d['check']}] {d['severity'].upper()} {d['context']}: {d['message']}")
    print("\n" + "=" * 60)
    print(f"This change ADDS {len(added)} finding(s). Redesign before merge.")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="capo - capability policy linter for LLM/agent stacks")
    ap.add_argument("policy", help="path to policy JSON")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--dot", action="store_true", help="emit capability graph as graphviz DOT")
    ap.add_argument("--diff", metavar="OLD", help="show findings the policy adds vs OLD baseline")
    args = ap.parse_args(argv)

    policy = load_policy(args.policy)

    if args.dot:
        print(emit_dot(policy))
        return 0
    if args.diff:
        return diff_policies(policy, load_policy(args.diff))

    findings = run_all(policy)
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
        return 1 if any(f.severity == "error" for f in findings) else 0

    errors = print_report(findings, policy)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

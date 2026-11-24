#!/usr/bin/env python3
"""
gamut - host auditor for "Shadow SRE" / "Polyglot Pivot" ingredients.

Sibling to capo. Where capo lints AI-stack *config*, gamut audits a *live host
you own/operate* for the dangerous co-location that turns an ordinary app box
into a non-human root plane:

    agent runtime + write-capable infra tools + persistent memory
    + self-training loop + production secrets, all on ONE host.

Any single ingredient is fine. The blast radius is in the co-location: a
prompt-injectable agent that can also invoke kubectl, read Vault, remember what
worked, and retrain on it, is a Shadow SRE with your keys.

SAFETY POSTURE
  - Read-only. Never writes, deletes, or modifies anything.
  - Secret NAMES and credential-file PATHS only. Never prints values/contents.
  - Network reachability is OPT-IN via --probe (off by default). The default
    run touches nothing off-host: /proc, filesystem, and PATH inspection only.

Exit code: 2 = CRITICAL, 1 = HIGH, 0 = MEDIUM or below (cron/CI gate friendly).
Standard library only.

Usage:
    gamut.py                        # audit this host, human report
    gamut.py --json                 # machine-readable
    gamut.py --root /srv --root /app  # extra filesystem roots to scan
    gamut.py --probe                # ALSO active-TCP-probe internal pivots
"""
import argparse
import json
import os
import re
import shutil
import socket
import sys

# --- detection tables -----------------------------------------------------

# Substrings that, in a process cmdline or a directory name, suggest an
# agent/LLM/orchestration runtime lives here.
AGENT_MARKERS = [
    "langchain", "langgraph", "llama_index", "llamaindex", "crewai", "autogen",
    "autogpt", "babyagi", "haystack", "semantic-kernel", "semantic_kernel",
    "dspy", "guidance", "ollama", "vllm", "localai", "text-generation-inference",
    "tgi", "ray.serve", "ray_serve", "mlflow", "litellm", "openai-agents",
    "orchestrator", "ops-assistant", "ops_assistant", "remediator",
    "auto-remediat", "sre-agent", "sre_agent", "agent-runner", "agentrunner",
]

# Infra CLIs by capability domain. severity ~ blast radius if driven by an agent.
INFRA_TOOLS = {
    # domain: (severity, [binaries])
    "cloud_infra": (5, ["kubectl", "helm", "terraform", "ansible-playbook",
                         "aws", "gcloud", "az", "doctl", "pulumi", "nomad",
                         "oci", "kubeadm", "kops"]),
    "container":   (5, ["docker", "podman", "nerdctl", "crictl"]),
    "secrets":     (5, ["vault", "sops", "age", "bw", "op"]),
    "database":    (3, ["psql", "mysql", "mariadb", "mongosh", "mongo",
                         "redis-cli", "clickhouse-client", "etcdctl", "cqlsh"]),
    "lateral":     (4, ["ssh", "scp", "sshpass", "socat", "ncat", "nc",
                         "chisel", "sshuttle"]),
}

# Directory-name substrings that suggest persistent agent memory / history.
MEMORY_MARKERS = [
    "memory", "history", "conversations", "conversation_log", "episodes",
    "trajector", "chat_history", "chroma", "qdrant", "faiss", "vectorstore",
    "vector_store", "vector-db", "embeddings_cache", "agent_state",
]

# Directory-name substrings that suggest a self-training / feedback loop.
TRAINING_MARKERS = [
    "feedback", "reward", "rlhf", "rl_", "_rl", "policy_opt", "trainer",
    "finetune", "fine-tune", "fine_tune", "ppo", "dpo", "grpo", "checkpoints",
    "distill", "auto_train", "autotrain", "continual",
]

# Env-var name substrings that indicate high-value secrets/identity. VALUES ARE
# NEVER PRINTED - only the matching variable name is reported.
SECRET_ENV_PATTERNS = [
    "OPENAI", "ANTHROPIC", "AZURE_OPENAI", "HF_TOKEN", "HUGGING", "COHERE",
    "AWS_ACCESS_KEY", "AWS_SECRET", "AWS_SESSION", "GOOGLE_APPLICATION_CREDENTIALS",
    "GCP_", "GOOGLE_CLOUD", "VAULT_TOKEN", "VAULT_ADDR", "KUBECONFIG", "KUBE_",
    "DATABASE_URL", "DB_URL", "POSTGRES", "MYSQL", "MARIADB", "MONGO", "REDIS",
    "ES_URL", "ELASTIC", "SLACK_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "GITLAB_TOKEN",
    "DOCKER_AUTH", "NPM_TOKEN", "PYPI", "STRIPE", "TWILIO", "PRIVATE_KEY",
    "SECRET", "TOKEN", "PASSWORD", "PASSWD", "API_KEY", "APIKEY", "ACCESS_KEY",
]

# Well-known credential file locations. gamut reports existence + path ONLY;
# it never opens or reads these files.
SECRET_FILE_PATHS = [
    "~/.kube/config", "~/.aws/credentials", "~/.aws/config",
    "~/.config/gcloud/application_default_credentials.json",
    "~/.vault-token", "/var/run/secrets/kubernetes.io/serviceaccount/token",
    "/root/.kube/config", "/root/.aws/credentials", "/root/.vault-token",
    "~/.docker/config.json", "~/.ssh/id_rsa", "~/.ssh/id_ed25519",
    "~/.netrc", "~/.git-credentials",
]

# Default internal pivot targets for --probe (active TCP connect, opt-in only).
PROBE_TARGETS = [
    ("kubernetes.default.svc", 443), ("kubernetes.default.svc", 6443),
    ("169.254.169.254", 80), ("vault", 8200), ("consul", 8500),
    ("elasticsearch", 9200), ("grafana", 3000), ("mariadb", 3306),
    ("postgres", 5432), ("milvus", 19530), ("qdrant", 6333),
    ("localhost", 2375),  # docker daemon over tcp
]

# Directories never worth walking (noise / pseudo-fs / huge trees).
PRUNE_DIRS = {
    "proc", "sys", "dev", "run", ".git", "node_modules", "site-packages",
    "dist-packages", "__pycache__", ".cache", "vendor", ".venv", "venv",
}
DEFAULT_ROOTS = ["/srv", "/opt", "/app", "/workspace", "/var/lib", "/home", "/root"]
MAX_DIRS_VISITED = 40000
MAX_HITS_PER_CATEGORY = 40


# --- collectors -----------------------------------------------------------

def find_agent_processes():
    """Scan /proc/*/cmdline for agent-runtime markers. Linux; degrades quietly."""
    hits = []
    proc = "/proc"
    if not os.path.isdir(proc):
        return hits
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join(proc, pid, "cmdline"), "rb") as fh:
                raw = fh.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        except (OSError, PermissionError):
            continue
        if not raw:
            continue
        low = raw.lower()
        for m in AGENT_MARKERS:
            if m in low:
                hits.append({"pid": pid, "marker": m, "cmdline": raw[:160]})
                break
    return hits


def find_infra_tools():
    """PATH inventory of infra CLIs, grouped by capability domain."""
    found = {}
    for domain, (sev, bins) in INFRA_TOOLS.items():
        present = [b for b in bins if shutil.which(b)]
        if present:
            found[domain] = {"severity": sev, "binaries": present}
    return found


def bounded_walk(roots, maxdepth):
    """Yield directories under roots up to maxdepth, pruning noise, capped."""
    visited = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip("/").count("/")
        for dirpath, dirnames, _ in os.walk(root, topdown=True, onerror=lambda e: None):
            visited += 1
            if visited > MAX_DIRS_VISITED:
                return
            depth = dirpath.rstrip("/").count("/") - base_depth
            if depth >= maxdepth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS
                           and not d.startswith(".")]
            yield dirpath


def find_marker_dirs(roots, markers, maxdepth):
    """Directories whose name matches any marker substring."""
    hits = []
    pat = re.compile("|".join(re.escape(m) for m in markers), re.IGNORECASE)
    for d in bounded_walk(roots, maxdepth):
        name = os.path.basename(d)
        if pat.search(name):
            hits.append(d)
            if len(hits) >= MAX_HITS_PER_CATEGORY:
                break
    return hits


def find_secret_env():
    """Env-var NAMES matching secret patterns. Values never read/printed."""
    names = []
    for key in os.environ:  # note: we iterate keys only, never os.environ[key]
        up = key.upper()
        if any(p in up for p in SECRET_ENV_PATTERNS):
            names.append(key)
    return sorted(set(names))


def find_secret_files():
    """Existing credential files. Path + existence only; never opened."""
    found = []
    for p in SECRET_FILE_PATHS:
        full = os.path.expanduser(p)
        try:
            if os.path.exists(full):
                found.append(full)
        except OSError:
            continue
    return found


def probe_targets(targets, timeout=0.5):
    """OPT-IN active TCP connect to internal pivots. Returns reachable list."""
    reachable = []
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                reachable.append(f"{host}:{port}")
        except (OSError, socket.error):
            continue
    return reachable


# --- scoring --------------------------------------------------------------

def classify(findings):
    agent = bool(findings["agent_processes"])
    infra = findings["infra_tools"]
    write_infra = any(infra.get(d) for d in ("cloud_infra", "container", "secrets"))
    memory = bool(findings["memory_dirs"])
    training = bool(findings["training_dirs"])
    secrets = bool(findings["secret_env"]) or bool(findings["secret_files"])

    # distinct capability domains present = "polyglot" breadth
    domains = set(infra.keys())
    polyglot = len(domains) >= 3 and agent and memory

    if agent and write_infra and training and secrets:
        verdict, why = "CRITICAL", (
            "Shadow SRE: agent runtime + write-capable infra tools + self-training "
            "loop + production secrets co-located. A prompt-injected or misaligned "
            "agent here can change prod and reinforce that behavior over time.")
    elif agent and write_infra and (memory or secrets):
        verdict, why = "HIGH", (
            "Agent runtime co-located with write-capable infra tools and "
            + ("persistent memory" if memory else "production secrets")
            + ". One foothold reaches a control plane; missing only the "
              "self-training loop to be a full Shadow SRE.")
    elif agent and (write_infra or secrets):
        verdict, why = "MEDIUM", (
            "Agent runtime present alongside "
            + ("write-capable infra tools" if write_infra else "production secrets")
            + ". Elevated blast radius; verify the agent cannot invoke these directly.")
    elif agent or write_infra:
        verdict, why = "LOW", (
            "Some ingredients present but not the dangerous combination. "
            "Track so it does not drift into co-location.")
    else:
        verdict, why = "MINIMAL", "No Shadow-SRE / polyglot-pivot ingredients found."

    return {
        "verdict": verdict,
        "reason": why,
        "signals": {
            "agent_runtime": agent,
            "write_infra_tools": write_infra,
            "persistent_memory": memory,
            "self_training_loop": training,
            "production_secrets": secrets,
            "polyglot_domains": sorted(domains),
            "polyglot_pivot_ingredients": polyglot,
        },
    }


# --- reporting ------------------------------------------------------------

def audit(roots, maxdepth, do_probe):
    findings = {
        "host": socket.gethostname(),
        "agent_processes": find_agent_processes(),
        "infra_tools": find_infra_tools(),
        "memory_dirs": find_marker_dirs(roots, MEMORY_MARKERS, maxdepth),
        "training_dirs": find_marker_dirs(roots, TRAINING_MARKERS, maxdepth),
        "secret_env": find_secret_env(),
        "secret_files": find_secret_files(),
        "reachable_pivots": probe_targets(PROBE_TARGETS) if do_probe else None,
    }
    findings["assessment"] = classify(findings)
    return findings


def print_report(f):
    a = f["assessment"]
    print("gamut :: shadow-SRE / polyglot-pivot host audit")
    print("=" * 62)
    print(f"host: {f['host']}")

    print("\n[1] agent runtime processes")
    if f["agent_processes"]:
        for p in f["agent_processes"]:
            print(f"  HIT  pid {p['pid']} ({p['marker']}): {p['cmdline']}")
    else:
        print("  none matched (manual review may still apply)")

    print("\n[2] infra tools on PATH (blast-radius surface)")
    if f["infra_tools"]:
        for domain, info in sorted(f["infra_tools"].items()):
            print(f"  [{domain}] sev{info['severity']}: {', '.join(info['binaries'])}")
    else:
        print("  none")

    print("\n[3] persistent memory / history dirs")
    for d in f["memory_dirs"] or ["  none"]:
        print(f"  {d}" if d.startswith("  ") else f"  HIT  {d}")

    print("\n[4] self-training / feedback dirs")
    for d in f["training_dirs"] or ["  none"]:
        print(f"  {d}" if d.startswith("  ") else f"  HIT  {d}")

    print("\n[5] production secret surface (NAMES/PATHS ONLY - values never read)")
    if f["secret_env"]:
        print(f"  env: {', '.join(f['secret_env'])}")
    if f["secret_files"]:
        for p in f["secret_files"]:
            print(f"  file: {p}")
    if not f["secret_env"] and not f["secret_files"]:
        print("  none obvious")

    print("\n[6] internal pivot reachability")
    if f["reachable_pivots"] is None:
        print("  not probed (default). re-run with --probe for active TCP checks.")
    elif f["reachable_pivots"]:
        for t in f["reachable_pivots"]:
            print(f"  OPEN  {t}")
    else:
        print("  none reachable from here")

    print("\n" + "=" * 62)
    print(f"VERDICT: {a['verdict']}")
    print(f"  {a['reason']}")
    sig = a["signals"]
    on = [k for k, v in sig.items() if v is True]
    print(f"  ingredients present: {', '.join(on) or 'none'}")
    if sig["polyglot_pivot_ingredients"]:
        print("  ** polyglot pivot engine: 3+ capability domains + agent + memory **")
    if a["verdict"] in ("HIGH", "CRITICAL"):
        print("\n  next: model this host's tool surface in capo as labelled")
        print("        capabilities, then split observe/act so the agent proposes")
        print("        and a constrained, audited layer executes.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="gamut - audit a host for Shadow-SRE / polyglot-pivot ingredients")
    ap.add_argument("--root", action="append", dest="roots", metavar="DIR",
                    help="filesystem root to scan (repeatable; defaults to common roots)")
    ap.add_argument("--maxdepth", type=int, default=3, help="dir walk depth (default 3)")
    ap.add_argument("--probe", action="store_true",
                    help="ALSO active-TCP-probe internal pivot targets (off by default)")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = ap.parse_args(argv)

    roots = args.roots or DEFAULT_ROOTS
    findings = audit(roots, args.maxdepth, args.probe)

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print_report(findings)

    verdict = findings["assessment"]["verdict"]
    return {"CRITICAL": 2, "HIGH": 1}.get(verdict, 0)


if __name__ == "__main__":
    sys.exit(main())

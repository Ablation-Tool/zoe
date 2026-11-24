#!/usr/bin/env python3
"""github-tos-audit: audit a git repository for GitHub Terms of Service risks.

Exit codes:
    0  no unsuppressed findings at or above --fail-on
    1  unsuppressed findings at or above --fail-on
    2  usage or tool error

Every finding maps to an entry in TOS_CLAUSES. Findings without a clause key
are dropped before output. Vendor commit-message findings are labeled OPSEC:
operational risk, not a GitHub ToS violation.

Clause quotes are verbatim from:
    https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
    https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
Clauses retrieved 2026-11-04. Terms of Service effective date: April 27, 2026.
"""

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

__version__ = "0.2.0"
CLAUSES_RETRIEVED = "2026-11-04"

TOS_CLAUSES = {
    "AUP§1": {
        "section": "GitHub Acceptable Use Policies §1: Compliance with Laws and Regulations",
        "quote": "You are responsible for using the Service in compliance with all applicable laws, regulations, and all of our Acceptable Use Policies.",
        "note": "Export-control markers are a prompt for legal review, not proof of a violation.",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies#1-compliance-with-laws-and-regulations",
    },
    "AUP§3-IP": {
        "section": "GitHub Acceptable Use Policies §3: Intellectual Property, Authenticity, and Private Information",
        "quote": "We do not allow content or activity on GitHub that: infringes any proprietary right of any party, including patent, trademark, trade secret, copyright, right of publicity, or other right; unlawfully shares unauthorized product licensing keys, software for generating unauthorized product licensing keys, or software for bypassing checks for product licensing keys, including extension of a free license beyond its trial period;",
        "note": "Two list items from §3 combined verbatim.",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies#3-intellectual-property-authenticity-and-private-information",
    },
    "AUP§3-privacy": {
        "section": "GitHub Acceptable Use Policies §3: Intellectual Property, Authenticity, and Private Information",
        "quote": "violates the privacy of any third party, such as by posting another person's personal information without consent.",
        "note": "One list item from §3.",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies#3-intellectual-property-authenticity-and-private-information",
    },
    "AUP§5": {
        "section": "GitHub Acceptable Use Policies §5: Site Access and Safety",
        "quote": "directly supports unlawful active attack or malware campaigns that are causing technical harms — such as using our platform to deliver malicious executables or as attack infrastructure, for example by organizing denial of service attacks or managing command and control servers — with no implicit or explicit dual-use purpose prior to the abuse occurring;",
        "note": "One list item from §5. Security research tooling with a defensive or analytical dual-use purpose is outside this clause. Pattern matches indicate review need, not campaign support.",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies#5-site-access-and-safety",
    },
    "ToS-F": {
        "section": "GitHub Terms of Service §F: Copyright Infringement and DMCA Policy",
        "quote": "We will terminate the Accounts of repeat infringers of this policy.",
        "note": "Decompiler attribution headers and large vendor binaries indicate takedown exposure, not proven infringement.",
        "url": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#f-copyright-infringement-and-dmca-policy",
    },
    "ToS-D1": {
        "section": "GitHub Terms of Service §D.1: Responsibility for User-Generated Content",
        "quote": "You are responsible for Your Content and any harm resulting from it.",
        "note": "",
        "url": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#d-user-generated-content",
    },
    "OPSEC": {
        "section": "OPSEC: not a GitHub ToS violation",
        "quote": "This finding has no corresponding GitHub ToS clause. GitHub will not act on it. Risk comes from vendor legal teams or third parties, not GitHub policy.",
        "note": "Tool-defined category.",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies",
    },
}

VERIFY_STATUS_VERIFIED = "VERIFIED"
VERIFY_STATUS_OPSEC = "OPSEC"
VERIFY_STATUS_REJECTED = "REJECTED"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}


@dataclass
class Finding:
    severity: str
    category: str
    clause_key: str
    description: str
    file: str = ""
    line: int = 0
    match: str = ""

    def verified(self) -> tuple[str, dict]:
        key = self.clause_key
        if not key or key not in TOS_CLAUSES:
            return VERIFY_STATUS_REJECTED, {}
        if key == "OPSEC":
            return VERIFY_STATUS_OPSEC, TOS_CLAUSES[key]
        return VERIFY_STATUS_VERIFIED, TOS_CLAUSES[key]

    def as_dict(self) -> dict:
        status, clause = self.verified()
        d = {k: v for k, v in asdict(self).items() if v or v == 0}
        d["verify_status"] = status
        if clause:
            d["clause_section"] = clause["section"]
            d["clause_quote"] = clause["quote"]
            if clause.get("note"):
                d["clause_note"] = clause["note"]
            d["clause_url"] = clause["url"]
        return d


CREDENTIAL_RULES = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "hardcoded password"),
    (r'(?i)(api_key|apikey|api_token)\s*=\s*["\'][^"\']{8,}["\']', "hardcoded API key"),
    (r'(?i)(secret|token)\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret/token"),
    (r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}', "GitHub personal access token"),
    (r'github_pat_[A-Za-z0-9_]{22,}', "GitHub fine-grained personal access token"),
    (r'glpat-[A-Za-z0-9_-]{20,}', "GitLab personal access token"),
    (r'xox[baprs]-[A-Za-z0-9-]{10,}', "Slack token"),
    (r'\bsk-[A-Za-z0-9_-]{20,}', "OpenAI-style API key"),
    (r'AIza[0-9A-Za-z_-]{35}', "Google API key"),
    (r'npm_[A-Za-z0-9]{36}', "npm access token"),
    (r'AKIA[0-9A-Z]{16}', "AWS access key ID"),
    (r'-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----', "private key header"),
]

MALWARE_RULES = [
    (r'(?i)(reverse[\s_-]?shell|bind[\s_-]?shell)', "reverse/bind shell string"),
    (r'(?i)msfvenom|meterpreter', "Metasploit tool reference"),
    (r'(?i)\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){15,}', "raw shellcode byte sequence (16+ bytes)"),
    (r'(?i)(dropper|ransomware|keylogger)\s+(payload|code|script)', "malware payload string"),
]

MASS_EXPLOIT_RULES = [
    (r'(?i)for\s+ip\s+in\s+\$\(.*(?:shodan|masscan|zmap)', "mass-scan exploit loop"),
    (r'(?i)auto[\s_-]?exploit|spray[\s_-]?creds|password[\s_-]?spray', "automated mass-exploitation pattern"),
]

DMCA_RULES = [
    (r'//\s*Decompiled with\s+(?:JD-GUI|CFR|Procyon|Jadx|Fernflower)', "JVM decompiler output header"),
    (r'/\*\s*This file was decompiled', "decompiler attribution comment"),
    (r'(?i)IDA Pro.*decompiled|Ghidra.*decompile', "IDA/Ghidra decompiler attribution"),
]

EXPORT_RULES = [
    (r'\bEAR\s*99\b|\bECCN\s*5[DE]002\b', "export control classification marker"),
]

VENDOR_RULES = [
    (r'\bcisco\b', "Cisco"),
    (r'\bfortinet\b', "Fortinet"),
    (r'\bpalo[\s_-]?alto\b', "Palo Alto"),
    (r'\bjuniper\b', "Juniper"),
    (r'\bhuawei\b', "Huawei"),
    (r'\bcheckpoint\b', "Check Point"),
    (r'\baruba\b', "Aruba"),
    (r'\bsonicwall\b', "SonicWall"),
    (r'\bwatchguard\b', "WatchGuard"),
    (r'\bzyxel\b', "Zyxel"),
    (r'\bnetgear\b', "Netgear"),
    (r'\bapple\b', "Apple"),
    (r'\bhpe\b', "HPE"),
    (r'\bacronis\b', "Acronis"),
    (r'\bvmware\b', "VMware"),
    (r'\bcitrix\b', "Citrix"),
    (r'\bbroadcom\b', "Broadcom"),
    (r'\bsiemens\b', "Siemens"),
    (r'\bschneider\b', "Schneider"),
    (r'\blockwell\b', "Rockwell"),
    (r'\bhoneywell\b', "Honeywell"),
    (r'\bbeckhoff\b', "Beckhoff"),
    (r'\bdahua\b', "Dahua"),
    (r'\bhikvision\b', "Hikvision"),
    (r'\baxis\b', "Axis"),
]

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".sh", ".bash", ".rb", ".go",
    ".c", ".cpp", ".h", ".java", ".php", ".rs", ".cs",
}
BINARY_EXTENSIONS = {".bin", ".img", ".exe", ".dll", ".so", ".dylib", ".fw", ".hex"}
BINARY_SIZE_MB_MIN = 1.0
DEFAULT_MAX_FILE_MB = 2.0

SENSITIVE_FILE_RULES = [
    (".env", ".env.*"), ("*.pem",), ("*.key",), ("*.p12",), ("*.pfx",),
    ("id_rsa", "id_rsa.*"), ("id_ed25519", "id_ed25519.*"),
    ("*.keystore",), ("*.kdbx",), ("credentials.json",), ("secrets.yaml", "secrets.yml"),
]
SENSITIVE_FILE_NAMES = tuple(p for group in SENSITIVE_FILE_RULES for p in group)

TEXT_RULE_GROUPS = [
    ("credentials", CREDENTIAL_RULES, "CRITICAL", "AUP§3-privacy"),
    ("malware", MALWARE_RULES, "HIGH", "AUP§5"),
    ("malware", MASS_EXPLOIT_RULES, "HIGH", "AUP§5"),
    ("dmca", DMCA_RULES, "HIGH", "ToS-F"),
    ("export", EXPORT_RULES, "MEDIUM", "AUP§1"),
]
GROUP_TO_CHECK = {
    "credentials": "credentials",
    "malware": "malware",
    "dmca": "dmca",
    "export": "export",
}


def run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout.strip()


def tracked_files(repo: Path) -> list[str]:
    return [p for p in run(["git", "ls-files"], cwd=repo).splitlines() if p.strip()]


def remote_log(repo: Path, fetch: bool = True) -> list[str]:
    if fetch:
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=repo, capture_output=True)
    refs_raw = run(["git", "for-each-ref", "--format=%(refname:short)",
                    "refs/remotes/origin/"], cwd=repo)
    remote_refs = [r for r in refs_raw.splitlines() if r and not r.endswith("/HEAD")]
    if not remote_refs:
        return run(["git", "log", "--all", "--oneline"], cwd=repo).splitlines()
    return run(["git", "log", "--oneline"] + remote_refs, cwd=repo).splitlines()


def scan_line(line: str, rules: list[tuple]) -> str | None:
    for pattern, label in rules:
        if re.search(pattern, line):
            return label
    return None


@dataclass
class ScanStats:
    scanned: int = 0
    skipped_oversize: list = None

    def __post_init__(self):
        if self.skipped_oversize is None:
            self.skipped_oversize = []


def check_text(repo: Path, rel_paths: list[str], checks: list[str],
               max_file_bytes: int, stats: ScanStats) -> list[Finding]:
    active = [g for g in TEXT_RULE_GROUPS if GROUP_TO_CHECK[g[0]] in checks]
    findings = []
    for rel in rel_paths:
        if Path(rel).suffix not in SOURCE_EXTENSIONS:
            continue
        f = repo / rel
        try:
            if f.stat().st_size > max_file_bytes:
                stats.skipped_oversize.append(rel)
                continue
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        stats.scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            for category, rules, severity, clause_key in active:
                label = scan_line(line, rules)
                if label:
                    findings.append(Finding(
                        severity=severity, category=category, clause_key=clause_key,
                        description=label, file=rel, line=lineno,
                        match=line.strip()[:120],
                    ))
    return findings


def check_sensitive_files(rel_paths: list[str]) -> list[Finding]:
    findings = []
    for rel in rel_paths:
        name = Path(rel).name
        if any(fnmatch.fnmatch(name, pat) for pat in SENSITIVE_FILE_NAMES):
            findings.append(Finding(
                severity="HIGH", category="sensitive-files", clause_key="AUP§3-privacy",
                description="sensitive filename tracked in git",
                file=rel,
            ))
    return findings


def check_vendors(repo: Path, fetch: bool = True) -> list[Finding]:
    findings = []
    seen: set[str] = set()
    for line in remote_log(repo, fetch=fetch):
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        msg = parts[1].lower()
        for pattern, display in VENDOR_RULES:
            if re.search(pattern, msg, re.IGNORECASE):
                key = f"{display}:{parts[1]}"
                if key not in seen:
                    seen.add(key)
                    findings.append(Finding(
                        severity="HIGH", category="vendors", clause_key="OPSEC",
                        description=f"'{display}' in public commit message",
                        match=line.strip(),
                    ))
                break
    return findings


def check_binaries(repo: Path, rel_paths: list[str]) -> list[Finding]:
    findings = []
    for rel in rel_paths:
        f = repo / rel
        if Path(rel).suffix not in BINARY_EXTENSIONS or not f.is_file():
            continue
        size_mb = f.stat().st_size / (1024 * 1024)
        if size_mb >= BINARY_SIZE_MB_MIN:
            findings.append(Finding(
                severity="MEDIUM", category="binaries", clause_key="ToS-F",
                description=f"{size_mb:.1f} MB binary tracked: possible DMCA-exposed firmware or vendor artifact",
                file=rel,
            ))
    return findings


def check_gitignore(repo: Path) -> list[Finding]:
    gi = repo / ".gitignore"
    if not gi.exists():
        return [Finding(severity="INFO", category="gitignore", clause_key="ToS-D1",
                        description="No .gitignore: credentials or artifacts may be committed accidentally")]
    text = gi.read_text()
    missing = [p for p in [".env", "*.key", "*.pem", "credentials.json", "secrets.yaml"]
               if p not in text]
    if missing:
        return [Finding(severity="INFO", category="gitignore", clause_key="ToS-D1",
                        description=f"Consider adding to .gitignore: {', '.join(missing)}")]
    return []


ALL_CHECKS = ["credentials", "malware", "dmca", "export", "sensitive-files",
              "vendors", "binaries", "gitignore"]
CONFIG_FILENAME = ".github-tos-audit.json"


def load_allowlist(repo: Path) -> tuple[list[dict], list[str]]:
    path = repo / CONFIG_FILENAME
    if not path.exists():
        return [], []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"{CONFIG_FILENAME}: unreadable or invalid JSON ({exc})"]
    entries = data.get("allowlist", [])
    if not isinstance(entries, list):
        return [], [f"{CONFIG_FILENAME}: 'allowlist' must be a list"]
    valid, warnings = [], []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or not entry.get("path"):
            warnings.append(f"{CONFIG_FILENAME}: allowlist entry {i} needs at least 'path' and 'reason'; ignored")
            continue
        if not entry.get("reason"):
            warnings.append(f"{CONFIG_FILENAME}: allowlist entry {i} ({entry.get('path')}) has no reason; ignored")
            continue
        valid.append(entry)
    return valid, warnings


def suppression_reason(finding: Finding, allowlist: list[dict]) -> str | None:
    for entry in allowlist:
        if not fnmatch.fnmatch(finding.file, entry["path"]):
            continue
        if entry.get("category") and entry["category"] != finding.category:
            continue
        if entry.get("match") and entry["match"] not in finding.match:
            continue
        return entry["reason"]
    return None


def print_text(findings: list[Finding], suppressed: list[tuple[Finding, str]],
               stats: ScanStats, warnings: list[str]) -> None:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = "  ".join(f"{s}: {n}" for s, n in
                        sorted(counts.items(), key=lambda x: SEVERITY_ORDER[x[0]]))
    print(f"Findings: {summary or 'none'}")
    print(f"Files scanned: {stats.scanned}  Oversize skipped: {len(stats.skipped_oversize)}  "
          f"Suppressed: {len(suppressed)}")
    for w in warnings:
        print(f"Warning: {w}")
    if not findings and not suppressed:
        return
    print("=" * 72)

    for f in findings:
        status, clause = f.verified()
        print(f"\n[{f.severity}] [{status}] {f.description}")
        if f.file:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"  Location : {loc}")
        if f.match:
            print(f"  Match    : {f.match}")
        if status == VERIFY_STATUS_OPSEC:
            print(f"  Status   : NOT a GitHub ToS violation: operational risk only")
            print(f"  Ref      : {clause['url']}")
        else:
            print(f"  Clause   : {clause['section']}")
            print(f"  Quote    : \"{clause['quote']}\"")
            if clause.get("note"):
                print(f"  Note     : {clause['note']}")
            print(f"  URL      : {clause['url']}")

    if suppressed:
        print(f"\n{'=' * 72}\nSuppressed by {CONFIG_FILENAME} (kept for audit):")
        for f, reason in suppressed:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"  [{f.severity}] {f.description}  {loc}\n    Reason: {reason}")

    print(f"\n{'=' * 72}")


def print_json(repo: Path, findings: list[Finding],
               suppressed: list[tuple[Finding, str]], stats: ScanStats,
               warnings: list[str]) -> None:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    out = {
        "tool": "github-tos-audit",
        "version": __version__,
        "repo": str(repo),
        "clauses_retrieved": CLAUSES_RETRIEVED,
        "summary": {
            "findings": counts,
            "files_scanned": stats.scanned,
            "oversize_skipped": stats.skipped_oversize,
            "suppressed": len(suppressed),
            "warnings": warnings,
        },
        "findings": [f.as_dict() for f in findings],
        "suppressed": [{**f.as_dict(), "suppress_reason": reason}
                       for f, reason in suppressed],
    }
    print(json.dumps(out, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="github-tos-audit",
        description="Audit a git repo for GitHub ToS risks. Every finding is verified against an exact clause.",
    )
    parser.add_argument("repo", nargs="?", default=".",
                        help="Path to a git repository (default: current directory)")
    parser.add_argument("--checks", metavar="CHECK", nargs="+",
                        choices=ALL_CHECKS + ["all"], default=["all"],
                        help=f"Checks to run. Choices: {', '.join(ALL_CHECKS)}, all")
    parser.add_argument("--min-severity", metavar="LEVEL", default="INFO",
                        choices=list(SEVERITY_ORDER),
                        help="Minimum severity to report (default: INFO)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Output findings as JSON")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Skip fetching origin before vendor commit scan")
    parser.add_argument("--fail-on", metavar="LEVEL", default="HIGH",
                        choices=list(SEVERITY_ORDER),
                        help="Exit code 1 if any unsuppressed finding at or above this level (default: HIGH)")
    parser.add_argument("--max-file-mb", metavar="MB", type=float, default=DEFAULT_MAX_FILE_MB,
                        help=f"Skip source files larger than this (default: {DEFAULT_MAX_FILE_MB})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"error: {repo} is not a git repository", file=sys.stderr)
        return 2
    if args.max_file_mb <= 0:
        print("error: --max-file-mb must be positive", file=sys.stderr)
        return 2

    checks = ALL_CHECKS if "all" in args.checks else args.checks
    min_ord = SEVERITY_ORDER[args.min_severity]
    fail_ord = SEVERITY_ORDER[args.fail_on]

    if not args.json_out:
        print(f"github-tos-audit {__version__}: {repo}")
        print(f"checks: {', '.join(checks)}  min-severity: {args.min_severity}  fail-on: {args.fail_on}\n")

    rel_paths = tracked_files(repo)
    stats = ScanStats()
    findings: list[Finding] = []
    text_checks = [c for c in checks if c in GROUP_TO_CHECK.values()]
    if text_checks:
        findings += check_text(repo, rel_paths, text_checks,
                               int(args.max_file_mb * 1024 * 1024), stats)
    if "sensitive-files" in checks:
        findings += check_sensitive_files(rel_paths)
    if "vendors" in checks:
        findings += check_vendors(repo, fetch=not args.no_fetch)
    if "binaries" in checks:
        findings += check_binaries(repo, rel_paths)
    if "gitignore" in checks:
        findings += check_gitignore(repo)

    allowlist, warnings = load_allowlist(repo)
    kept, suppressed = [], []
    for f in findings:
        if f.verified()[0] == VERIFY_STATUS_REJECTED:
            continue
        if SEVERITY_ORDER[f.severity] > min_ord:
            continue
        reason = suppression_reason(f, allowlist)
        if reason is not None:
            suppressed.append((f, reason))
        else:
            kept.append(f)
    kept.sort(key=lambda f: SEVERITY_ORDER[f.severity])

    if args.json_out:
        print_json(repo, kept, suppressed, stats, warnings)
    else:
        print_text(kept, suppressed, stats, warnings)

    worst = min((SEVERITY_ORDER[f.severity] for f in kept), default=99)
    return 1 if worst <= fail_ord else 0


if __name__ == "__main__":
    sys.exit(main())

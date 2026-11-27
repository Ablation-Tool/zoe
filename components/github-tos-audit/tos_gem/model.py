"""Audit execution and finding verification against local policy documents."""

import json
import subprocess
import sys
from pathlib import Path

from . import policies

SCANNER = Path(__file__).resolve().parent.parent / "github_tos_audit.py"


def run_audit(repo: Path, max_file_mb: float = 2.0) -> dict:
    """Run the deterministic scanner and return its JSON report."""
    result = subprocess.run(
        [sys.executable, str(SCANNER), str(repo), "--json", "--no-fetch",
         "--max-file-mb", str(max_file_mb)],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "scanner failed")
    return json.loads(result.stdout)


def verified_findings(report: dict, cache_dir: Path = policies.CACHE_DIR) -> list[dict]:
    """Attach local-policy verification to each finding.

    The scanner maps findings to clauses. This step independently checks that
    the clause quote exists in the local GitHub policy text, so a user can
    confirm both the scanner and any agent interpretation against the source.
    """
    documents = {}
    output = []
    for finding in report.get("findings", []) + report.get("suppressed", []):
        item = dict(finding)
        key = finding.get("clause_key")
        doc = policies.CLAUSE_POLICY.get(key)
        if not doc:
            item["policy_check"] = "not-applicable"
            output.append(item)
            continue
        if doc not in documents:
            try:
                documents[doc] = policies.load_policy(doc, cache_dir)
            except OSError as exc:
                documents[doc] = (None, {"error": str(exc)})
        text, meta = documents[doc]
        if text is None:
            item["policy_check"] = "unavailable"
            item["policy_error"] = meta.get("error", "policy text missing")
        else:
            found, excerpt = policies.verify_quote(finding["clause_quote"], text)
            item["policy_check"] = "verified" if found else "mismatch"
            item["policy_excerpt"] = excerpt
            item["policy_document"] = policies.POLICIES[doc]["title"]
            item["policy_retrieved"] = meta.get("retrieved", "unknown")
            item["policy_url"] = meta.get("url", policies.POLICIES[doc]["url"])
        output.append(item)
    return output

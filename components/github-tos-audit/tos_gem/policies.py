"""Local GitHub policy documents: fetch, cache, update check, quote verification.

The workbench never needs GitHub access to audit. A bundled snapshot ships in
the repository; Fetch Policies refreshes a user cache and reports what changed.
"""

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

POLICIES = {
    "tos": {
        "title": "GitHub Terms of Service",
        "url": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
    },
    "aup": {
        "title": "GitHub Acceptable Use Policies",
        "url": "https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies",
    },
    "dmca": {
        "title": "DMCA Takedown Policy",
        "url": "https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy",
    },
    "community": {
        "title": "GitHub Community Guidelines",
        "url": "https://docs.github.com/en/site-policy/github-terms/github-community-guidelines",
    },
}

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshot"
CACHE_DIR = Path.home() / ".local" / "share" / "github-tos-audit" / "policies"

BLOCK_TAGS = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "ul", "ol", "table", "br"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer") and self.skip:
            self.skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _meta_path(directory: Path) -> Path:
    return directory / "meta.json"


def load_meta(directory: Path) -> dict:
    try:
        return json.loads(_meta_path(directory).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write(directory: Path, key: str, text: str) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{key}.txt").write_text(text)
    meta = load_meta(directory)
    meta[key] = {
        "url": POLICIES[key]["url"],
        "retrieved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": _sha256(text),
    }
    _meta_path(directory).write_text(json.dumps(meta, indent=2))
    return meta[key]


def fetch_remote_text(key: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        POLICIES[key]["url"],
        headers={"User-Agent": "github-tos-audit-policy-fetch"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    text = html_to_text(html)
    if len(text) < 2000:
        raise ValueError(f"Policy page returned only {len(text)} characters; refusing to cache")
    return text


def fetch_policies(cache_dir: Path = CACHE_DIR, keys=None) -> list[dict]:
    """Fetch policies into the cache. Returns one status record per policy."""
    results = []
    for key in keys or POLICIES:
        record = {"key": key, "title": POLICIES[key]["title"]}
        try:
            text = fetch_remote_text(key)
            previous = load_meta(cache_dir).get(key, {})
            record["changed"] = previous.get("sha256") != _sha256(text)
            record.update(_write(cache_dir, key, text))
            record["status"] = "updated" if record["changed"] else "unchanged"
        except Exception as exc:
            record["status"] = "error"
            record["error"] = str(exc)
        results.append(record)
    return results


def policy_dir(cache_dir: Path = CACHE_DIR) -> Path:
    """Prefer the user cache; fall back to the bundled snapshot."""
    if (cache_dir / "tos.txt").exists():
        return cache_dir
    return SNAPSHOT_DIR


def load_policy(key: str, cache_dir: Path = CACHE_DIR) -> tuple[str, dict]:
    directory = policy_dir(cache_dir)
    text = (directory / f"{key}.txt").read_text()
    return text, load_meta(directory).get(key, {})


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_quote(quote: str, policy_text: str, context: int = 160) -> tuple[bool, str]:
    """Locate a clause quote in a policy document. Returns (found, excerpt)."""
    haystack = normalize(policy_text)
    needle = normalize(quote)
    index = haystack.find(needle)
    if index >= 0:
        start = max(0, index - 40)
        end = min(len(haystack), index + len(needle) + context)
        return True, haystack[start:end]
    for size in (80, 50, 30):
        fragment = needle[:size]
        index = haystack.find(fragment)
        if index >= 0:
            start = max(0, index - 40)
            end = min(len(haystack), index + size + context)
            return False, "Partial match only: " + haystack[start:end]
    return False, "Quote not found in the local policy text."


CLAUSE_POLICY = {
    "AUP§1": "aup",
    "AUP§3-IP": "aup",
    "AUP§3-privacy": "aup",
    "AUP§5": "aup",
    "ToS-F": "tos",
    "ToS-D1": "tos",
}

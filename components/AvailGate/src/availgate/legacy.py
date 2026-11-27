#!/usr/bin/env python3
"""
AvailGate -- multi-engine search aggregator with quantitative ranking.

What this solves
----------------
Every search engine gives you a different, filtered view of the internet. A page
absent from Google may be ranked first on Bing. A raw-IP admin panel may not
appear at all unless you ask the right engine with the right operators. Running
one engine means accepting one engine's blind spots.

The first page of any commercial search is also full of paid placements and
SEO-optimized content written to rank, not to be the thing you want. For
infrastructure recon you do not want the blog post about exposed Jenkins
consoles -- you want the actual console. GHDB dork augmentation prepends
operator syntax (inurl:, intitle:, filetype:) that forces engines to return
pages matching structural patterns, bypassing the SEO layer entirely.

Finally, a single engine's rank position is a weak signal. Being first on one
engine does not mean a result is relevant -- it means one algorithm decided so.
AvailGate replaces that with a composite score built from six independent
signals: cross-engine consensus, textual match, semantic similarity, URL trust,
recency, and (with --infra) structural infrastructure patterns. A result earns
its position across multiple measurements, not one proprietary black box.

In short: it makes the internet searchable as infrastructure rather than as a
content delivery surface -- finding what exists rather than what is marketed.

Who this is for
---------------
Security researchers and pentesters doing OSINT and infrastructure recon.
Standard search is built for content consumers. This tool is built for finding
what is exposed -- login panels, directory listings, misconfigured services,
version fingerprints. The GHDB integration and --profile infra exist for that.

Claude Code and Codex users who need search as a native CLI operation. Instead
of switching to a browser mid-session, you run availgate inline and pipe output
directly into the next tool. Search becomes a step in a chain, not an
interruption.

Security toolchain users who need search as a composable step. The --json
output is designed to feed downstream tools -- port scanners, screenshot
grabbers, vulnerability matchers -- without manual copy-paste.

This tool is not for general web browsing. If you want a tutorial or docs, a
browser is better. This is for when the answer you want is a URL to something
that exists but is not trying to be found.

Claude Code / Codex usage
-------------------------
AvailGate is designed to run directly inside a Claude Code or Codex terminal
session. Pipe JSON output into your workflow or read plain-text results inline:

    availgate "exposed Grafana dashboard"
    availgate --profile infra --dork-augment "Cisco IOS login panel"
    availgate --json "phpMyAdmin no auth" | jq '.[].url'
    availgate --plain --no-semantic "Redis exposed no auth"

Quick start (zero config):

    pip install ddgs requests beautifulsoup4 rich
    availgate "your query here"

No API keys required. DDG, Bing, Brave, and SearXNG run keyless by default.
Results are scored across six signals (RRF, BM25, semantic, coverage, trust,
freshness) and printed as a ranked table or JSON array.

How a query runs
----------------
1. All enabled engines fire in parallel (ThreadPoolExecutor).
2. Results are deduplicated by canonical URL across engines.
3. Six scores are computed per result and combined into a weighted sum.
4. With --dork-augment, the top GHDB operator match is prepended to your query
   before sending to web engines (e.g. inurl:"/remote/login" YOUR QUERY),
   cutting through SEO spam to surface raw infrastructure pages.
5. With --profile infra or --infra, raw IPs, directory listings, and admin
   paths receive an additional boost score.

Output formats:
    (default)   rich table with per-metric columns
    --plain     plain text, one result per block
    --json      JSON array -- use with jq, pipe to other tools

Engines:  DuckDuckGo, Bing, Brave (all keyless by default),
          SearXNG public instances, GHDB local corpus
          + optional: Google CSE, Yandex, Mojeek, Brave API, Serper
Metrics:  RRF · BM25 · cross-engine coverage · URL trust · freshness · semantic
Config:   ~/.availgate.json  {"google_api_key": "...", "google_cx": "...",
                              "brave_api_key": "...", "serper_api_key": "...",
                              "ghdb_path": "/path/to/ghdb_all.json"}
          env: GOOGLE_API_KEY, GOOGLE_CX, BRAVE_API_KEY, SERPER_API_KEY, etc.
"""

import argparse
import hashlib
import ipaddress
import math
import re
import sqlite3
import socket
import ssl
import sys
import json
import os
from collections import defaultdict
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

# ── optional engine / display imports ────────────────────────────────────────

try:
    from ddgs import DDGS
    HAS_DDG = True
except ImportError:
    try:
        from duckduckgo_search import DDGS  # legacy fallback
        HAS_DDG = True
    except ImportError:
        HAS_DDG = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False

import importlib.util

HAS_SBERT = importlib.util.find_spec("sentence_transformers") is not None

# Modern provider workers install an observer; legacy invocations retain stderr.
_error_observer = None


def _provider_error(error):
    if _error_observer is not None:
        _error_observer(error)

# ── data types ────────────────────────────────────────────────────────────────

@dataclass
class Hit:
    url: str
    title: str
    snippet: str
    engine: str
    rank: int            # 1-indexed position from this engine
    date: Optional[str] = None


@dataclass
class AggResult:
    url: str
    title: str
    snippet: str
    engines: list = field(default_factory=list)
    ranks: dict = field(default_factory=dict)
    score: float = 0.0
    components: dict = field(default_factory=dict)


# ── URL canonicalization ──────────────────────────────────────────────────────

def canonicalize(url: str) -> str:
    try:
        p = urlparse(url.strip())
        hostname = (p.hostname or "").lower().removeprefix("www.")
        host = f"[{hostname}]" if ":" in hostname else hostname
        if p.port is not None:
            host = f"{host}:{p.port}"
        path = p.path.rstrip("/") or "/"
        q = ("?" + p.query) if p.query else ""
        return f"{p.scheme.lower()}://{host}{path}{q}"
    except Exception:
        return url.strip()


# ── BM25 (defined early — used by both engine_ghdb and aggregation) ───────────

_TOK = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOK.findall(text.lower())


class BM25:
    K1 = 1.5
    B  = 0.75

    def __init__(self, docs: list[str]):
        self.corpus = [tokenize(d) for d in docs]
        N = len(self.corpus)
        self.avgdl = sum(len(d) for d in self.corpus) / max(N, 1)
        self.df: dict[str, int] = defaultdict(int)
        self.N = N
        for doc in self.corpus:
            for term in set(doc):
                self.df[term] += 1

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, doc_idx: int, query_terms: list[str]) -> float:
        doc = self.corpus[doc_idx]
        dl = len(doc)
        tf_map: dict[str, int] = defaultdict(int)
        for t in doc:
            tf_map[t] += 1
        total = 0.0
        for term in query_terms:
            tf = tf_map.get(term, 0)
            norm = tf * (self.K1 + 1) / (
                tf + self.K1 * (1 - self.B + self.B * dl / max(self.avgdl, 1))
            )
            total += self.idf(term) * norm
        return total

# alias used by engine_ghdb
_BM25Lite = BM25


# ── search engines ────────────────────────────────────────────────────────────

def engine_ddg(query: str, n: int) -> list[Hit]:
    if not HAS_DDG:
        return []
    results = []
    try:
        with DDGS() as ddgs:
            for i, r in enumerate(ddgs.text(query, max_results=n), 1):
                results.append(Hit(
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                    engine="ddg",
                    rank=i,
                    date=r.get("published"),
                ))
    except Exception as e:
        _provider_error(e)
        print(f"[ddg] {e}", file=sys.stderr)
    return results


_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"


_BING_BREADCRUMB_RE = re.compile(r"\s*[›»>]\s*.*$")


def _clean_bing_url(url: str) -> str:
    """Strip Bing breadcrumb decoration (e.g. 'example.com › path › page')."""
    return _BING_BREADCRUMB_RE.sub("", url).strip()


def _bing_destination(href: str) -> str:
    """Prefer the full anchor destination over Bing's abbreviated cite text."""
    import base64
    try:
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return ""
        if parsed.hostname.lower() in ("bing.com", "www.bing.com") and parsed.path.startswith("/ck/a"):
            encoded = parse_qs(parsed.query).get("u", [""])[0]
            if not encoded.startswith("a1"):
                return ""
            encoded = encoded[2:]
            href = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
            parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return ""
        return href
    except (ValueError, UnicodeError):
        return ""


def engine_bing(query: str, n: int, _key: str = "") -> list[Hit]:
    """
    Bing — HTML scraping, no API key needed.
    <cite> tags carry the real destination URL (no redirect).
    """
    if not HAS_REQUESTS:
        return []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    results = []
    fetched = 0
    first = 1
    max_pages = max(3, (n // 5) + 2)
    page = 0
    try:
        sess = _get_session()
        while fetched < n and page < max_pages:
            page += 1
            r = sess.get(
                "https://www.bing.com/search",
                params={"q": query, "first": first, "count": 10},
                headers={"User-Agent": _UA},
                timeout=12,
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")
            items = soup.select("li.b_algo")
            if not items:
                break
            for item in items:
                if item.select_one(".b_adSlug, .b_ad"):   # skip paid placements
                    continue
                a    = item.select_one("h2 a")
                cite = item.select_one("cite")
                p    = item.select_one(".b_caption p, .b_algoSlug")
                # cite text may be schemeless or breadcrumb-decorated; clean it first.
                cite_text = _clean_bing_url(cite.get_text(strip=True)) if cite else ""
                url = _bing_destination(a.get("href", "")) if a else ""
                if not url:
                    continue
                # skip sitelinks: they have no snippet paragraph
                if not p:
                    continue
                fetched += 1
                results.append(Hit(
                    url=url,
                    title=a.get_text(strip=True) if a else "",
                    snippet=p.get_text(strip=True) if p else "",
                    engine="bing",
                    rank=fetched,
                ))
                if fetched >= n:
                    break
            first += 10
            if len(items) < 5:
                break
        if page >= max_pages and fetched < n:
            print(f"[bing] hit page ceiling ({max_pages}), returning {fetched} results",
                  file=sys.stderr)
    except Exception as e:
        _provider_error(e)
        print(f"[bing] {e}", file=sys.stderr)
    return results


def engine_google(query: str, n: int, api_key: str = "", cx: str = "") -> list[Hit]:
    """
    Google — uses the Custom Search JSON API when api_key+cx are configured,
    otherwise skipped (Google aggressively blocks HTML scraping from server IPs).
    Keys: console.cloud.google.com → Custom Search API; programmablesearchengine.google.com → CX.
    Free: 100 queries/day.
    """
    if not (HAS_REQUESTS and api_key and cx):
        return []
    results = []
    fetched = 0
    start = 1
    try:
        while fetched < n:
            batch = min(10, n - fetched)
            r = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": api_key, "cx": cx, "q": query, "num": batch, "start": start},
                timeout=10,
            )
            r.raise_for_status()
            data  = r.json()
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                fetched += 1
                date_str = None
                for tag in item.get("pagemap", {}).get("metatags", []):
                    date_str = (
                        tag.get("article:published_time")
                        or tag.get("og:updated_time")
                        or tag.get("date")
                    )
                    if date_str:
                        break
                results.append(Hit(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", "").replace("\n", " "),
                    engine="google",
                    rank=fetched,
                    date=date_str,
                ))
            start += len(items)
            if start > 91:
                break
    except Exception as e:
        _provider_error(e)
        print(f"[google] {e}", file=sys.stderr)
    return results


# Public SearXNG instances tried in order; first one that responds wins.
# These are well-known, openly-listed instances (searx.space registry).
_SEARXNG_PUBLIC = [
    "https://searx.be",
    "https://search.sapti.me",
    "https://searxng.site",
    "https://search.ononoki.org",
    "https://opnxng.com",
]


def engine_searxng(query: str, n: int, base_url: str = "") -> list[Hit]:
    """
    SearXNG — no API key needed.
    Uses your own instance (SEARXNG_URL) or falls back to public instances.
    A SearXNG instance aggregates Google, Bing, Brave, Qwant, Wikipedia, GitHub,
    and ~60 other sources simultaneously, returning deduplicated JSON.
    """
    if not HAS_REQUESTS:
        return []
    candidates = [base_url.rstrip("/")] if base_url else _SEARXNG_PUBLIC
    results = []
    for url in candidates:
        try:
            r = requests.get(
                f"{url}/search",
                params={"q": query, "format": "json", "pageno": 1, "categories": "general"},
                headers={"Accept": "application/json", "User-Agent": _UA},
                timeout=12,
            )
            r.raise_for_status()
            data = r.json()
            items = data.get("results", [])
            if not items:
                return []
            for i, item in enumerate(items[:n], 1):
                results.append(Hit(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    engine="searxng",
                    rank=i,
                    date=item.get("publishedDate"),
                ))
            break   # success — stop trying instances
        except Exception as e:
            _provider_error(e)
            print(f"[searxng] {url}: {e}", file=sys.stderr)
            continue
    if not results:
        print("[searxng] all instances failed", file=sys.stderr)
    return results


def engine_brave(query: str, n: int, api_key: str = "") -> list[Hit]:
    """
    Brave Search — keyless HTML scrape (div[data-type=web]) by default.
    When BRAVE_API_KEY is configured, uses the official API instead
    (higher rate limits, structured JSON, no scraping fragility).
    """
    if not HAS_REQUESTS:
        return []
    # ── API path (key configured) ────────────────────────────────────────────
    if api_key:
        results = []
        try:
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                         "X-Subscription-Token": api_key},
                params={"q": query, "count": min(n, 20), "search_lang": "en"},
                timeout=10,
            )
            r.raise_for_status()
            for i, item in enumerate(r.json().get("web", {}).get("results", []), 1):
                results.append(Hit(url=item.get("url", ""), title=item.get("title", ""),
                                   snippet=item.get("description", ""), engine="brave",
                                   rank=i, date=item.get("age")))
        except Exception as e:
            _provider_error(e)
            print(f"[brave-api] {e}", file=sys.stderr)
        return results
    # ── Keyless scrape path ──────────────────────────────────────────────────
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    results = []
    try:
        r = _get_session().get(
            "https://search.brave.com/search",
            params={"q": query, "source": "web"},
            headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=12,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for i, item in enumerate(soup.select("div[data-type=web]")[:n], 1):
            if item.select_one(".ad-label, .badge-ad, [data-type=ad]"):
                continue
            a     = item.select_one("a[href]")
            title = item.select_one(".title, span.h")
            snip  = item.select_one(".snippet-description, p, .desc")
            if not a:
                continue
            results.append(Hit(
                url=a["href"],
                title=(title.get_text(strip=True) if title
                       else a.get_text(strip=True))[:120],
                snippet=snip.get_text(strip=True) if snip else "",
                engine="brave",
                rank=i,
            ))
    except Exception as e:
        _provider_error(e)
        print(f"[brave] {e}", file=sys.stderr)
    return results


def engine_serper(query: str, n: int, api_key: str = "") -> list[Hit]:
    """Serper.dev (Google proxy) — optional, requires SERPER_API_KEY."""
    if not (HAS_REQUESTS and api_key):
        return []
    results = []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": min(n, 10)},
            timeout=10,
        )
        r.raise_for_status()
        for i, item in enumerate(r.json().get("organic", []), 1):
            results.append(Hit(url=item.get("link", ""), title=item.get("title", ""),
                               snippet=item.get("snippet", ""), engine="serper",
                               rank=i, date=item.get("date")))
    except Exception as e:
        _provider_error(e)
        print(f"[serper] {e}", file=sys.stderr)
    return results


def engine_yandex(query: str, n: int, user: str = "", key: str = "") -> list[Hit]:
    """Yandex XML Search — optional, requires YANDEX_USER + YANDEX_KEY."""
    if not (HAS_REQUESTS and user and key):
        return []
    import xml.etree.ElementTree as ET
    results = []
    try:
        r = requests.get(
            "https://yandex.com/search/xml",
            params={"user": user, "key": key, "query": query, "lr": "225",
                    "l10n": "en", "sortby": "rlv", "filter": "none",
                    "maxpassages": "1",
                    "groupby": f"attr=d.mode=flat.groups-on-page={min(n,100)}.docs-in-group=1"},
            timeout=15,
        )
        r.raise_for_status()
        root = ET.fromstring(r.content)
        if root.find(".//error") is not None:
            raise ValueError("Yandex returned an API error")
        for i, doc in enumerate(root.iter("doc"), 1):
            # ElementTree leaf elements are falsey, so `find(...) or find(...)`
            # discards valid <url>, <title>, and <headline> values.
            url = doc.find("url")
            if url is None:
                url = doc.find(".//url")
            ttl = doc.find("title")
            if ttl is None:
                ttl = doc.find(".//title")
            snip = doc.find("headline")
            if snip is None:
                snip = doc.find("passages/passage")
            if snip is None:
                snip = doc.find(".//passage")
            dt   = doc.find(".//modtime")
            results.append(Hit(
                url=(url.text or "").strip() if url is not None else "",
                title=(ttl.text or "").strip() if ttl is not None else "",
                snippet=(snip.text or "").strip() if snip is not None else "",
                engine="yandex", rank=i,
                date=dt.text[:10] if dt is not None and dt.text else None,
            ))
            if i >= n:
                break
    except Exception as e:
        _provider_error(e)
        print(f"[yandex] {e}", file=sys.stderr)
    return results


def engine_mojeek(query: str, n: int, api_key: str = "") -> list[Hit]:
    """Mojeek — optional, requires MOJEEK_API_KEY. Independent UK crawler."""
    if not (HAS_REQUESTS and api_key):
        return []
    results = []
    try:
        r = requests.get(
            "https://www.mojeek.com/api/v1/search",
            params={"api_key": api_key, "q": query, "fmt": "json", "results": min(n, 10)},
            timeout=10,
        )
        r.raise_for_status()
        for i, item in enumerate(r.json().get("results", []), 1):
            results.append(Hit(url=item.get("url", ""), title=item.get("title", ""),
                               snippet=item.get("desc", ""), engine="mojeek",
                               rank=i, date=item.get("date")))
    except Exception as e:
        _provider_error(e)
        print(f"[mojeek] {e}", file=sys.stderr)
    return results


# GHDB category weight — higher = more security-relevant to surface
_GHDB_CAT_W = {
    "Vulnerable Servers":            1.00,
    "Vulnerable Files":              1.00,
    "Files Containing Passwords":    0.95,
    "Files Containing Usernames":    0.90,
    "Footholds":                     0.90,
    "Network or Vulnerability Data": 0.85,
    "Pages Containing Login Portals":0.80,
    "Error Messages":                0.75,
    "Advisories and Vulnerabilities":0.70,
    "Sensitive Directories":         0.70,
    "Files Containing Juicy Info":   0.65,
    "Various Online Devices":        0.65,
    "Web Server Detection":          0.55,
    "Sensitive Online Shopping Info":0.45,
}

_GHDB_DEFAULT = os.path.expanduser("~/white-bronco/Claude-Code-GHDB/ghdb_all.json")
_ghdb_corpus_cache: tuple = ("", [])   # (realpath, corpus list)
_ghdb_bm25_cache: tuple = ("", None)   # (realpath, BM25 instance)

# Operator tokens extracted from GHDB dork strings.
_OPERATOR_RE = re.compile(
    r'''(?:inurl|intitle|intext|filetype|ext|site):(?:"[^"]+"|'[^']+'|\S+)|"index of[^"]*"''',
    re.I,
)

# Shared requests session for HTML-scrape engines (connection pooling).
_http_sessions = threading.local()
_http_proxy = ""


def _get_session(proxy: str = ""):
    global _http_proxy
    if proxy:
        _http_proxy = proxy
    if not hasattr(_http_sessions, "session"):
        import requests as _req
        _http_sessions.session = _req.Session()
        _http_sessions.session.headers.update({"User-Agent": _UA})
    if _http_proxy:
        _http_sessions.session.proxies.update({"http": _http_proxy, "https": _http_proxy})
    return _http_sessions.session


_ghdb_load_lock = threading.Lock()


def _load_ghdb(path: str) -> list:
    global _ghdb_corpus_cache
    real_path = os.path.realpath(path)
    cached_path, cached_corpus = _ghdb_corpus_cache
    if cached_path == real_path and cached_corpus:
        return cached_corpus
    with _ghdb_load_lock:
        # re-check after acquiring lock (another thread may have loaded already)
        cached_path, cached_corpus = _ghdb_corpus_cache
        if cached_path == real_path and cached_corpus:
            return cached_corpus
        with open(path) as f:
            corpus = json.load(f)
        if not isinstance(corpus, list):
            corpus = []
        if len(corpus) > 50_000:
            print(
                f"[ghdb] warning: corpus has {len(corpus)} entries (expected < 50000)",
                file=sys.stderr,
            )
        _ghdb_corpus_cache = (real_path, corpus)
    return corpus


def _ghdb_bm25(path: str) -> "BM25":
    """Return a cached BM25 instance over the GHDB corpus; rebuild only when path changes."""
    global _ghdb_bm25_cache
    cached_path, cached_bm = _ghdb_bm25_cache
    real_path = os.path.realpath(path)
    if cached_bm is None or cached_path != real_path:
        corpus = _load_ghdb(path)
        texts = [
            f"{d.get('textualDescription','')} {d.get('shortDescription','')} "
            f"{d.get('category','')} {d.get('query','')}"
            for d in corpus
        ]
        cached_bm = BM25(texts)
        _ghdb_bm25_cache = (real_path, cached_bm)
    return cached_bm


def engine_ghdb(query: str, n: int, ghdb_path: str = "") -> list[Hit]:
    """
    Rank GHDB dorks by BM25 relevance to the query, boosted by category weight.
    Returns top-n dorks as Hits; url = EDB permalink, snippet = dork query string.
    The BM25 scoring here runs over the GHDB corpus independently — its instance
    is separate from the main aggregation BM25 used later.
    """
    path = ghdb_path or _GHDB_DEFAULT
    if not os.path.exists(path):
        return []
    try:
        corpus = _load_ghdb(path)
    except Exception as e:
        print(f"[ghdb] load error: {e}", file=sys.stderr)
        return []

    bm = _ghdb_bm25(path)
    query_terms = tokenize(query)

    scored = []
    for i, d in enumerate(corpus):
        raw = bm.score(i, query_terms)
        cat_boost = _GHDB_CAT_W.get(d.get("category", ""), 0.5)
        scored.append((raw * cat_boost, i))

    scored.sort(reverse=True)
    results = []
    for rank, (_, idx) in enumerate(scored[:n], 1):
        d = corpus[idx]
        edb_url = d.get("link") or f"https://www.exploit-db.com/ghdb/{d.get('id','')}"
        results.append(Hit(
            url=edb_url,
            title=f"[GHDB:{d.get('category','?')}] {d.get('shortDescription','')[:72]}",
            snippet=d.get("query", ""),
            engine="ghdb",
            rank=rank,
            date=None,  # submission date penalises old-but-valid dorks; use neutral freshness
        ))
    return results


def ghdb_augment_query(plain_query: str, ghdb_path: str = "", top_k: int = 3) -> list[str]:
    """
    Return up to top_k dork-augmented query strings by prepending the GHDB
    operator syntax most relevant to plain_query.

    Example:
      plain_query = "Fortinet SSL-VPN login panel"
      returns  [
        'inurl:"/remote/login" Fortinet SSL-VPN login panel',
        'intitle:"FortiGate" Fortinet SSL-VPN login panel',
        ...
      ]

    Web engines handle these as operator-narrowed searches, cutting through
    ads and SEO spam to hit raw infrastructure / file pages directly.
    """
    path = ghdb_path or _GHDB_DEFAULT
    if not os.path.exists(path):
        return [plain_query]
    try:
        corpus = _load_ghdb(path)
    except Exception:
        return [plain_query]

    bm = _ghdb_bm25(path)
    qt = tokenize(plain_query)

    scored = []
    for i, d in enumerate(corpus):
        raw = bm.score(i, qt)
        cat_boost = _GHDB_CAT_W.get(d.get("category", ""), 0.5)
        dork = d.get("query", "")
        # only use dorks that actually contain search operators
        if _OPERATOR_RE.search(dork):
            scored.append((raw * cat_boost, dork))

    scored.sort(reverse=True)

    seen_ops: set[str] = set()
    augmented: list[str] = []
    for _, dork in scored:
        raw_ops = _OPERATOR_RE.findall(dork)
        # deduplicate operator names: keep first occurrence of each operator type
        seen_types: set[str] = set()
        deduped_ops: list[str] = []
        for op in raw_ops:
            # normalise to operator name: inurl:, intitle:, etc.
            op_name = re.match(r"[a-z]+:", op.lower())
            key = op_name.group(0) if op_name else op.lower()[:10]
            if key not in seen_types:
                seen_types.add(key)
                deduped_ops.append(op)
        ops = " ".join(deduped_ops)
        if ops and ops not in seen_ops:
            seen_ops.add(ops)
            augmented.append(f"{ops} {plain_query}")
        if len(augmented) >= top_k:
            break

    return augmented if augmented else [plain_query]


# ── URL trust heuristic ───────────────────────────────────────────────────────

_TLD_W = {"gov": 1.0, "mil": 1.0, "edu": 0.9, "org": 0.7,
           "net": 0.55, "io": 0.55, "com": 0.5, "co": 0.4}


def url_trust(url: str) -> float:
    try:
        p = urlparse(url)
        s = 0.3
        if p.scheme == "https":
            s += 0.2
        parts = p.netloc.split(".")
        tld = parts[-1].lower() if parts else ""
        s += _TLD_W.get(tld, 0.2)
        depth = len([x for x in p.path.split("/") if x])
        s -= min(depth * 0.05, 0.3)
        if len(parts) > 3:          # extra subdomains
            s -= 0.1
        return max(0.0, min(1.0, s))
    except Exception:
        return 0.0


# ── infra scoring (--infra / --profile infra) ────────────────────────────────

_RAW_IP_RE = re.compile(r"^https?://\d{1,3}(?:\.\d{1,3}){3}")
_INFRA_SNIPPET_RE = re.compile(
    r"index of\s*/|phpinfo\(\)|server.?status|directory listing|"
    r"admin\s+login|login\s+portal|open\s+redirect|\.env\b|"
    r"exposed\s+api|swagger\s+ui",
    re.I,
)
_INFRA_PATH_RE = re.compile(
    r"/(?:admin|dashboard|phpinfo\.php|server-status|phpmyadmin|"
    r"wp-admin|wp-login\.php|console|manager|actuator|api/v\d|"
    r"\.env|config\.php|setup\.php|install\.php|"
    r"jenkins|grafana|kibana|prometheus|splunk|elastic|sonarqube)",
    re.I,
)


def infra_score(url: str, snippet: str) -> float:
    """
    Heuristic boost for raw-infrastructure pages: raw IPs, directory listings,
    admin/management paths, and exposed service fingerprints.
    Only applied when --infra or --profile infra is active.
    """
    s = 0.0
    if _RAW_IP_RE.match(url):
        s += 0.5
    if _INFRA_SNIPPET_RE.search(snippet or ""):
        s += 0.3
    if _INFRA_PATH_RE.search(urlparse(url).path):
        s += 0.2
    return min(s, 1.0)


# ── freshness ─────────────────────────────────────────────────────────────────

_DATE_FMTS = [
    "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d", "%b %d, %Y", "%d %b %Y",
]


def freshness(date_str: Optional[str]) -> float:
    if not date_str:
        return 0.5
    cleaned = date_str.strip()
    dt = None
    for fmt in _DATE_FMTS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            break
        except ValueError:
            pass
    if dt is None:
        m = re.match(r"(\d+)\s+(day|week|month|year)", date_str.lower())
        if m:
            n, unit = int(m.group(1)), m.group(2)
            age_days = n * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
        else:
            return 0.5
    else:
        age_days = max(0, (datetime.now() - dt).days)
    return math.exp(-age_days / 730)   # half-life ≈ 2 years


# ── semantic score (optional) ─────────────────────────────────────────────────

_sbert_model = None

def semantic_scores(query: str, snippets: list[str]) -> list[float]:
    global _sbert_model
    if not HAS_SBERT or not snippets:
        return [0.5] * len(snippets)
    try:
        if _sbert_model is None:
            print("[semantic] loading MiniLM model...", file=sys.stderr)
            from sentence_transformers import SentenceTransformer
            _sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
        import numpy as np
        q_emb = _sbert_model.encode([query], normalize_embeddings=True)[0]
        s_embs = _sbert_model.encode(snippets, normalize_embeddings=True)
        scores = (s_embs @ q_emb).tolist()
        mn, mx = min(scores), max(scores)
        if mx - mn < 1e-9:
            return [0.5] * len(scores)
        return [(s - mn) / (mx - mn) for s in scores]
    except Exception:
        return [0.5] * len(snippets)


# ── aggregation & scoring ─────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "rrf":       0.35,
    "coverage":  0.15,
    "bm25":      0.25,
    "semantic":  0.10,
    "trust":     0.10,
    "freshness": 0.05,
}

RRF_K = 60   # Cormack et al. 2009 constant

# Weight presets for --profile.  infra weight is 0 in default; only activated
# when --infra flag or --profile infra is passed to aggregate().
PROFILES: dict[str, dict] = {
    "infra": {
        "rrf": 1.0, "coverage": 1.0, "trust": 0.7,
        "bm25": 0.3, "semantic": 0.3, "freshness": 0.2, "infra": 0.8,
    },
    "content": {
        "rrf": 0.5, "coverage": 0.4, "trust": 0.8,
        "bm25": 0.8, "semantic": 1.0, "freshness": 0.6,
    },
}


def effective_weights(
    weights: dict = None, no_semantic: bool = False,
    infra: bool = False, profile: str = "",
) -> dict:
    W = dict(PROFILES.get(profile, DEFAULT_WEIGHTS))
    if infra and "infra" not in W:
        W["infra"] = 0.4
    if weights:
        W.update(weights)
    if no_semantic or not HAS_SBERT:
        extra = W.pop("semantic", 0.0)
        W["bm25"] = W.get("bm25", 0) + extra * 0.6
        W["rrf"] = W.get("rrf", 0) + extra * 0.4
    total_w = sum(W.values())
    if total_w <= 0:
        raise ValueError("score weights must have a positive total")
    return {k: v / total_w for k, v in W.items()}


def aggregate(
    hits: list[Hit],
    query: str,
    top_n: int = 20,
    weights: dict = None,
    no_semantic: bool = False,
    infra: bool = False,
    profile: str = "",
) -> tuple[list[AggResult], dict]:
    W = effective_weights(weights, no_semantic, infra, profile)
    if weights or profile:
        effective = "  ".join(f"{k}={v:.3f}" for k, v in sorted(W.items()))
        print(f"[weights] effective (normalized): {effective}", file=sys.stderr)

    # group by canonical URL
    groups: dict[str, AggResult] = {}
    engine_set: set[str] = set()
    date_map: dict[str, Optional[str]] = {}

    for hit in hits:
        if not hit.url:
            continue
        key = canonicalize(hit.url)
        engine_set.add(hit.engine)
        if key not in groups:
            groups[key] = AggResult(
                url=hit.url, title=hit.title,
                snippet=hit.snippet, engines=[], ranks={},
            )
            date_map[key] = hit.date
        g = groups[key]
        if hit.engine not in g.engines:
            g.engines.append(hit.engine)
        g.ranks[hit.engine] = min(hit.rank, g.ranks.get(hit.engine, hit.rank))
        if len(hit.snippet) > len(g.snippet):
            g.snippet = hit.snippet
            g.title = hit.title
        if hit.date and not date_map[key]:
            date_map[key] = hit.date

    n_engines = max(len(engine_set), 1)
    keys = list(groups)
    snippets = [groups[k].snippet for k in keys]

    bm25 = BM25(snippets)
    query_terms = tokenize(query)
    sem = semantic_scores(query, snippets) if "semantic" in W else [0.5] * len(snippets)

    raw: dict[str, dict] = {}
    for i, key in enumerate(keys):
        g = groups[key]

        # RRF: normalized to [0,1] against best possible (rank=1 in all engines)
        rrf_raw = sum(1.0 / (RRF_K + r) for r in g.ranks.values())
        rrf_max = n_engines / (RRF_K + 1)
        rrf_n = rrf_raw / rrf_max if rrf_max else 0.0

        raw[key] = {
            "rrf":       min(rrf_n, 1.0),
            "coverage":  len(g.engines) / n_engines,
            "bm25":      bm25.score(i, query_terms),
            "semantic":  sem[i],
            "trust":     url_trust(g.url),
            "freshness": freshness(date_map.get(key)),
            "infra":     infra_score(g.url, g.snippet) if infra else 0.0,
        }

    # min-max normalize BM25 (absolute values not meaningful across corpora)
    bm25_vals = [raw[k]["bm25"] for k in keys]
    bm25_max = max(bm25_vals) if bm25_vals else 1.0
    for k in keys:
        raw[k]["bm25"] /= bm25_max if bm25_max > 0 else 1.0

    results = []
    for key in keys:
        g = groups[key]
        s = raw[key]
        g.score = sum(W.get(m, 0) * s.get(m, 0) for m in s)
        g.components = {m: round(s[m], 4) for m in s}
        results.append(g)

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:top_n], W


# ── output ────────────────────────────────────────────────────────────────────

def _engine_tag(r: AggResult) -> str:
    return " ".join(f"{e}[{r.ranks[e]}]" for e in sorted(r.engines))


def print_rich(results: list[AggResult], query: str):
    import shutil
    term_w = shutil.get_terminal_size((80, 24)).columns
    narrow = term_w < 100

    tbl = Table(
        title=f"AvailGate  [bold white]{query}[/bold white]",
        box=box.MINIMAL_HEAVY_HEAD,
        show_lines=True,
        expand=True,
    )
    sem_vals  = [r.components.get("semantic", 0.5) for r in results]
    has_sem   = (not narrow) and ("semantic" in (results[0].components if results else {})) and (max(sem_vals) - min(sem_vals) > 0.01)
    has_infra = (not narrow) and any(r.components.get("infra", 0) > 0 for r in results)

    tbl.add_column("#",       style="dim", width=3, no_wrap=True)
    tbl.add_column("Score",   width=5, justify="right", no_wrap=True)
    tbl.add_column("Title / URL", ratio=1, min_width=30, no_wrap=True, overflow="ellipsis")
    if not narrow:
        tbl.add_column("RRF",  width=5, justify="right", no_wrap=True)
        tbl.add_column("BM25", width=5, justify="right", no_wrap=True)
        if has_sem:
            tbl.add_column("Sem",   width=5, justify="right", no_wrap=True)
        if has_infra:
            tbl.add_column("Infra", width=5, justify="right", no_wrap=True)
        tbl.add_column("Cov",  width=4, justify="right", no_wrap=True)
        tbl.add_column("Tr",   width=5, justify="right", no_wrap=True)
        tbl.add_column("Fr",   width=5, justify="right", no_wrap=True)
    tbl.add_column("Engines", width=16, no_wrap=True)

    for i, r in enumerate(results, 1):
        c = r.components
        row = [
            str(i),
            f"[bold green]{r.score:.3f}[/bold green]",
            (f"[link={r.url}][bold]{r.title[:60]}[/bold][/link]\n"
             f"[dim]{r.url[:80]}[/dim]"),
        ]
        if not narrow:
            row += [
                f"{c.get('rrf',0):.3f}",
                f"{c.get('bm25',0):.3f}",
            ]
            if has_sem:
                row.append(f"{c.get('semantic',0):.3f}")
            if has_infra:
                row.append(f"[yellow]{c.get('infra',0):.3f}[/yellow]")
            row += [
                f"{c.get('coverage',0):.2f}",
                f"{c.get('trust',0):.3f}",
                f"{c.get('freshness',0):.3f}",
            ]
        row.append(_engine_tag(r))
        tbl.add_row(*row)

    console.print(tbl)
    console.print()
    for i, r in enumerate(results[:5], 1):
        console.print(f"[bold cyan]{i}.[/bold cyan] [link={r.url}]{r.url}[/link]")
        if r.snippet:
            console.print(f"   [dim]{r.snippet[:220]}[/dim]")
        console.print()


def print_plain(results: list[AggResult], query: str):
    print(f"AvailGate: {query}")
    print("=" * 80)
    for i, r in enumerate(results, 1):
        c = r.components
        print(f"\n{i:2}. [{r.score:.3f}] {r.title}")
        print(f"    {r.url}")
        parts = "  ".join(f"{k}={v:.3f}" for k, v in c.items())
        print(f"    {parts}")
        print(f"    engines: {_engine_tag(r)}")
        if r.snippet:
            print(f"    {r.snippet[:180]}")


def print_json(results: list[AggResult]):
    out = []
    for r in results:
        out.append({
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "score": round(r.score, 6),
            "engines": r.engines,
            "ranks": r.ranks,
            "components": r.components,
        })
    print(json.dumps(out, indent=2))


# ── result cache (SQLite, daily TTL) ─────────────────────────────────────────

_CACHE_PATH = os.path.expanduser("~/.availgate_cache.db")
_cache_lock = threading.Lock()


def _cache_key(
    query: str, engines: set, profile: str, dork_k: int,
    dork_augment: bool = False, use_infra: bool = False,
    results_per_engine: int = 20, top: int = 15,
    weights: dict = None, no_semantic: bool = False,
    ghdb_path: str = "",
    engine_config: dict = None,
) -> str:
    today = time.strftime("%Y-%m-%d")
    ghdb_stamp = None
    if ghdb_path and ("ghdb" in engines or dork_augment):
        try:
            stat = os.stat(ghdb_path)
            ghdb_stamp = (os.path.realpath(ghdb_path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            ghdb_stamp = (os.path.realpath(ghdb_path), None, None)
    blob = json.dumps(
        [query, sorted(engines), profile, dork_k, dork_augment, use_infra,
         results_per_engine, top, weights or {}, no_semantic, HAS_SBERT,
         ghdb_stamp, engine_config or {}, today],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _cache_get(key: str) -> list | None:
    con = None
    try:
        with _cache_lock:
            con = sqlite3.connect(_CACHE_PATH, timeout=5)
            row = con.execute(
                "SELECT payload FROM results WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None
    finally:
        if con is not None:
            con.close()


def _cache_set(key: str, results: list) -> None:
    con = None
    try:
        payload = json.dumps(results)
        with _cache_lock:
            con = sqlite3.connect(_CACHE_PATH, timeout=5)
            con.execute(
                "CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, payload TEXT)"
            )
            con.execute(
                "INSERT OR REPLACE INTO results VALUES (?,?)", (key, payload)
            )
            con.commit()
    except Exception as e:
        print(f"[cache] write failed: {e}", file=sys.stderr)
    finally:
        if con is not None:
            con.close()


def _cache_clear() -> int:
    try:
        with _cache_lock:
            con = sqlite3.connect(_CACHE_PATH, timeout=5)
            con.execute(
                "CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, payload TEXT)"
            )
            n = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            con.execute("DELETE FROM results")
            con.commit()
            con.close()
        return n
    except Exception as e:
        print(f"[cache] clear failed: {e}", file=sys.stderr)
        return 0


# ── page fetch augmentation (--fetch N) ──────────────────────────────────────

_MAX_FETCH_BYTES = 2 * 1024 * 1024
_MAX_FETCH_REDIRECTS = 5


def _public_fetch_url(url: str) -> bool:
    """Return whether an HTTP(S) URL resolves only to public addresses."""
    return _public_fetch_target(url) is not None


def _public_fetch_target(url: str):
    """Resolve once and return the public address used for the connection."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        if not addresses or not all(
            ipaddress.ip_address(item[4][0]).is_global for item in addresses
        ):
            return None
        return parsed, addresses[0][4][0], port
    except (ValueError, OSError):
        return None


def _fetch_body(url: str, _session=None) -> str:
    """
    Fetch a page directly through the public IP vetted for this connection.
    Keep the original hostname for the Host header and TLS verification.
    Return empty text on a blocked destination or any network error.
    The session argument is retained for callers but is not used; proxies can
    resolve a hostname independently and bypass the vetted-address boundary.
    """
    try:
        import urllib3
        for _ in range(_MAX_FETCH_REDIRECTS + 1):
            target = _public_fetch_target(url)
            if target is None:
                return ""
            parsed, vetted_ip, port = target
            hostname = parsed.hostname
            host_header = f"[{hostname}]" if ":" in hostname else hostname
            if port != (443 if parsed.scheme == "https" else 80):
                host_header = f"{host_header}:{port}"
            path = parsed.path or "/"
            if parsed.params:
                path += ";" + parsed.params
            if parsed.query:
                path += "?" + parsed.query
            if parsed.scheme == "https":
                pool = urllib3.HTTPSConnectionPool(
                    vetted_ip, port=port, server_hostname=hostname,
                    assert_hostname=hostname, ssl_context=ssl.create_default_context(),
                )
            else:
                pool = urllib3.HTTPConnectionPool(vetted_ip, port=port)
            r = None
            try:
                r = pool.urlopen(
                    "GET", path,
                    headers={"Host": host_header, "User-Agent": _UA,
                             "Accept-Encoding": "identity"},
                    timeout=urllib3.Timeout(connect=8, read=8),
                    retries=False, redirect=False, preload_content=False,
                )
                if 300 <= r.status < 400:
                    location = r.headers.get("Location")
                    if not location:
                        return ""
                    url = urljoin(url, location)
                    continue
                if r.status != 200:
                    return ""
                body = bytearray()
                deadline = time.monotonic() + 30
                for chunk in r.stream(amt=65536, decode_content=True):
                    body.extend(chunk)
                    if len(body) > _MAX_FETCH_BYTES or time.monotonic() > deadline:
                        return ""
                break
            finally:
                if r is not None:
                    r.release_conn()
                pool.close()
        else:
            return ""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(bytes(body), "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ").split())[:8000]
    except Exception:
        return ""


def fetch_augment(
    results: list, query: str, top_n: int, session, weights: dict = None
) -> list:
    """
    Fetch the body of the top top_n results and re-score BM25 over full text.
    Replaces the snippet with the fetched body for those results.
    Results beyond top_n are unchanged.
    """
    if not results:
        return results
    query_terms = tokenize(query)
    to_fetch = results[:top_n]
    rest = results[top_n:]

    print(f"[fetch] fetching {len(to_fetch)} pages...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=min(top_n, 4)) as pool:
        try:
            bodies = list(pool.map(
                lambda r: _fetch_body(r.url, session), to_fetch, timeout=60
            ))
        except TimeoutError:
            print("[fetch] timed out — using partial results", file=sys.stderr)
            bodies = [""] * len(to_fetch)

    augmented_snippets = []
    for r, body in zip(to_fetch, bodies):
        if body:
            r.snippet = body[:500]   # update snippet for display
        augmented_snippets.append(body or r.snippet)

    # re-run BM25 over full bodies and update bm25 component
    bm = BM25(augmented_snippets)
    bm25_scores = [bm.score(i, query_terms) for i in range(len(augmented_snippets))]
    bm25_max = max(bm25_scores) if bm25_scores else 1.0
    for i, r in enumerate(to_fetch):
        norm = bm25_scores[i] / bm25_max if bm25_max > 0 else 0.0
        r.components["bm25"] = round(norm, 4)
        if weights:
            r.score = sum(weights.get(m, 0) * r.components.get(m, 0) for m in r.components)
        else:
            n_comp = len(r.components) or 1
            r.score = sum(r.components.values()) / n_comp

    ranked = to_fetch + rest
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked


# ── selector health check (--health) ─────────────────────────────────────────

_HEALTH_QUERY = "open source software"
_HEALTH_MIN   = 3   # minimum hits to consider an engine healthy
_HEALTH_TIMEOUT = 30


def run_health_check(cfg: dict) -> None:
    print(f"AvailGate health check  (query: '{_HEALTH_QUERY}')", file=sys.stderr)
    print("-" * 56, file=sys.stderr)
    engines = ["ddg", "bing", "brave", "searxng"]
    if cfg.get("google_api_key") and cfg.get("google_cx"):
        engines.append("google")
    if cfg.get("serper_api_key"):
        engines.append("serper")

    results = {}

    def check(eng: str) -> None:
        try:
            _, _, hits = _dispatch_engine_inner(eng, _HEALTH_QUERY, 5, cfg)
            results[eng] = len(hits)
        except Exception as e:
            print(f"  ERR  {eng:<12} {e}", file=sys.stderr)
            results[eng] = 0

    workers = {eng: threading.Thread(target=check, args=(eng,), daemon=True)
               for eng in engines}
    for worker in workers.values():
        worker.start()
    deadline = time.monotonic() + _HEALTH_TIMEOUT
    for worker in workers.values():
        worker.join(max(0.0, deadline - time.monotonic()))
    for eng, worker in workers.items():
        if worker.is_alive():
            print(f"  ERR  {eng:<12} timed out", file=sys.stderr)
            results[eng] = 0

    ok = True
    for eng in engines:
        n = results.get(eng, 0)
        status = "OK " if n >= _HEALTH_MIN else "FAIL"
        if n < _HEALTH_MIN:
            ok = False
        print(f"  {status}  {eng:<12} {n} hits", file=sys.stderr)

    print("-" * 56, file=sys.stderr)
    sys.exit(0 if ok else 1)


# ── parallel engine dispatch ──────────────────────────────────────────────────

# One semaphore per engine: different engines run in parallel, but multiple
# dork-variant queries to the same engine serialize. Scrape-mode engines also
# enforce a minimum inter-request delay to avoid 429s.
_ENGINE_SEMS: dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(1))
_ENGINE_LAST_TS: dict[str, float] = {}
_SCRAPE_DELAY = 2.0   # seconds between sequential requests to the same scrape engine
_SCRAPE_ENGINES = {"bing", "brave"}


def _dispatch_engine(
    eng: str, wq: str, n: int, cfg: dict
) -> tuple[str, str, list[Hit]]:
    """Called in a thread pool; returns (engine_name, query, hits)."""
    with _ENGINE_SEMS[eng]:
        if eng in _SCRAPE_ENGINES:
            elapsed = time.monotonic() - _ENGINE_LAST_TS.get(eng, 0.0)
            gap = _SCRAPE_DELAY - elapsed
            if gap > 0:
                time.sleep(gap)
        result = _dispatch_engine_inner(eng, wq, n, cfg)
        if eng in _SCRAPE_ENGINES:
            _ENGINE_LAST_TS[eng] = time.monotonic()
        return result


def _dispatch_engine_inner(
    eng: str, wq: str, n: int, cfg: dict
) -> tuple[str, str, list[Hit]]:
    if eng == "ddg":
        hits = engine_ddg(wq, n)
    elif eng == "bing":
        hits = engine_bing(wq, n)
    elif eng == "searxng":
        hits = engine_searxng(wq, n, cfg.get("searxng_url", ""))
    elif eng == "google":
        hits = engine_google(wq, n, cfg.get("google_api_key", ""), cfg.get("google_cx", ""))
    elif eng == "yandex":
        hits = engine_yandex(wq, n, cfg.get("yandex_user", ""), cfg.get("yandex_key", ""))
    elif eng == "mojeek":
        hits = engine_mojeek(wq, n, cfg.get("mojeek_api_key", ""))
    elif eng == "brave":
        hits = engine_brave(wq, n, cfg.get("brave_api_key", ""))
    elif eng == "serper":
        hits = engine_serper(wq, n, cfg.get("serper_api_key", ""))
    else:
        print(f"[warn] unknown engine '{eng}'", file=sys.stderr)
        hits = []
    return eng, wq, hits





# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg = {
        "google_api_key": os.environ.get("GOOGLE_API_KEY", ""),
        "google_cx":      os.environ.get("GOOGLE_CX", ""),
        "yandex_user":    os.environ.get("YANDEX_USER", ""),
        "yandex_key":     os.environ.get("YANDEX_KEY", ""),
        "mojeek_api_key": os.environ.get("MOJEEK_API_KEY", ""),
        "searxng_url":    os.environ.get("SEARXNG_URL", ""),
        "brave_api_key":  os.environ.get("BRAVE_API_KEY", ""),
        "serper_api_key": os.environ.get("SERPER_API_KEY", ""),
        "proxy":          os.environ.get("AVAILGATE_PROXY", ""),
    }
    cfg_path = os.path.expanduser("~/.availgate.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog="availgate",
        description="AvailGate — multi-engine search aggregator with quantitative ranking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
metrics (weighted combination):
  rrf        Reciprocal Rank Fusion — Σ 1/(60+rank_i) across engines
  bm25       Okapi BM25 textual relevance of snippets vs query terms
  semantic   cosine(MiniLM(query), MiniLM(snippet))  [if sentence-transformers installed]
  coverage   fraction of engines that returned this URL
  trust      URL heuristic: HTTPS, TLD authority, path depth
  freshness  recency decay with a 730-day decay constant

GHDB integration:
  --ghdb              include ranked GHDB dork entries in results (auto if ghdb_all.json found)
  --dork-augment      prepend best GHDB operator syntax to each web query
                      e.g. query "Cisco IOS login" → also runs `inurl:"/exec/show" Cisco IOS login`
                      cuts through ads/SEO spam; surfaces raw infra/file pages
  --dork-k N          run N dork-augmented variants (default 2)
  --ghdb-path PATH    override path to ghdb_all.json

keyless engines (work out of the box, zero config):
  ddg       DuckDuckGo — ddgs library JSON endpoint
  bing      Bing HTML scraping (cite-tag URL extraction)
  brave     Brave Search HTML scraping (div[data-type=web])
  searxng   Public SearXNG instances — aggregate Google, Bing, Brave, Qwant, ~60 others
  ghdb      Local GHDB corpus (auto-detected)

  note: Google/Yandex/Mojeek block HTML scraping from server IPs with JS challenges.
        SearXNG already proxies Google+Brave internally, covering those indexes keylessly.

optional API-key upgrades (~/.availgate.json or env vars):
  google_api_key / GOOGLE_API_KEY     Google Custom Search API (100/day free)
  google_cx      / GOOGLE_CX          Programmable Search Engine ID
  yandex_user    / YANDEX_USER        Yandex XML (best for CIS/RU infra targets)
  yandex_key     / YANDEX_KEY         Yandex XML key  (xml.yandex.com)
  mojeek_api_key / MOJEEK_API_KEY     Mojeek independent UK crawler (100/day free)
  searxng_url    / SEARXNG_URL        Your own SearXNG instance (overrides public list)
  brave_api_key  / BRAVE_API_KEY      Brave API — upgrades brave from scrape to API
  serper_api_key / SERPER_API_KEY     serper.dev Google proxy (skipped if google set)
  ghdb_path (JSON only)               override path to ghdb_all.json

scoring profiles (--profile):
  infra    boosts raw IPs, directory listings, admin paths, exposed services
           weights: rrf=1.0 cov=1.0 trust=0.7 infra=0.8 bm25=0.3 sem=0.3 fresh=0.2
  content  boosts textual relevance and recency
           weights: rrf=0.5 cov=0.4 trust=0.8 bm25=0.8 sem=1.0 fresh=0.6

  --infra  selects the infra profile unless another --profile is specified
           and adds the infra component to that profile

page fetching:
  --fetch N  fetches public HTTP(S) pages through vetted IP addresses
             directly; AVAILGATE_PROXY is not used for these requests

examples:
  availgate "Fortinet SSL-VPN exposed panel"
  availgate --profile infra --dork-augment "exposed Grafana dashboard"
  availgate --infra --ghdb "phpMyAdmin no auth"
  availgate --dork-augment --ghdb "Cisco IOS enable password"
  availgate --engines ddg,bing,yandex,ghdb --plain "exposed Redis no auth"
  availgate --weights rrf=0.5,bm25=0.3,coverage=0.2 "query here"
""",
    )
    ap.add_argument("query", nargs="*")
    ap.add_argument("-n", "--results",    type=int, default=20,  help="results per engine (default 20)")
    ap.add_argument("--top",              type=int, default=15,  help="results to display (default 15)")
    ap.add_argument("--engines", default=None,
                    help="comma-separated engine list: ddg,google,bing,yandex,mojeek,searxng,brave,serper,ghdb")
    ap.add_argument("--ghdb",             action="store_true",
                    help="include GHDB dork results in ranking (auto-enabled if ghdb_path configured)")
    ap.add_argument("--dork-augment",     action="store_true",
                    help="prepend top GHDB operator syntax to web queries (narrows results, cuts ads)")
    ap.add_argument("--dork-k",           type=int, default=None,
                    help="number of dork-augmented query variants to run (default 2); implies --dork-augment")
    ap.add_argument("--ghdb-path",        default=None,   help="path to ghdb_all.json")
    ap.add_argument("--no-semantic",      action="store_true",   help="skip sentence-transformer scoring")
    ap.add_argument("--weights",          default=None,
                    help="override metric weights e.g. rrf=0.5,bm25=0.3,coverage=0.2")
    ap.add_argument("--profile",          default=None, choices=list(PROFILES),
                    help="scoring profile: infra (raw IPs, dir listings, admin paths) | content (text relevance)")
    ap.add_argument("--infra",            action="store_true",
                    help="select infra profile by default, or add infra scoring to an explicit profile")
    ap.add_argument("--json",             action="store_true",   help="JSON output")
    ap.add_argument("--plain",            action="store_true",   help="plain-text output")
    ap.add_argument("--fetch",            type=int, default=0, metavar="N",
                    help="fetch top N pages directly through vetted public IPs and re-score BM25")
    ap.add_argument("--no-cache",         action="store_true",
                    help="bypass result cache (keyed by query, engines, options, and date)")
    ap.add_argument("--clear-cache",      action="store_true",   help="clear all cached results and exit")
    ap.add_argument("--health",           action="store_true",   help="run engine health check and exit")
    args = ap.parse_args()

    query = " ".join(args.query)
    cfg   = load_config()

    # early-exit commands
    if args.clear_cache:
        n = _cache_clear()
        print(f"cache cleared ({n} entries)", file=sys.stderr)
        sys.exit(0)
    if args.health:
        run_health_check(cfg)   # exits internally
    if not args.query:
        ap.error("a query is required unless --health or --clear-cache is used")
    if args.results < 1 or args.top < 1 or args.fetch < 0 or (args.dork_k is not None and args.dork_k < 0):
        ap.error("--results and --top must be positive; --fetch and --dork-k cannot be negative")

    # init session with proxy if configured
    _get_session(cfg.get("proxy", ""))

    ghdb_path = args.ghdb_path or cfg.get("ghdb_path", "") or _GHDB_DEFAULT

    profile = args.profile or ("infra" if args.infra and not args.profile else "")
    use_infra = args.infra or (profile == "infra")

    # weight overrides
    _all_weight_keys = set(DEFAULT_WEIGHTS) | {"infra"}
    extra_weights = {}
    if args.weights:
        for pair in args.weights.split(","):
            k, _, v = pair.partition("=")
            k = k.strip()
            if k not in _all_weight_keys or not v:
                ap.error(f"invalid weight: {pair}")
            try:
                value = float(v.strip())
            except ValueError:
                ap.error(f"invalid weight: {pair}")
            if not math.isfinite(value) or value < 0:
                ap.error(f"weight must be finite and nonnegative: {pair}")
            extra_weights[k] = value
        try:
            effective_weights(extra_weights, args.no_semantic, use_infra, profile)
        except ValueError:
            ap.error("score weights must have a positive total")

    # engine selection
    # Keyless engines (ddg, bing, searxng) are ON by default — no config needed.
    # API-key engines are added automatically when their key is configured.
    if args.engines:
        enabled = set(args.engines.split(","))
    else:
        enabled = {"ddg", "bing", "brave", "searxng"}    # keyless defaults
        if cfg.get("google_api_key") and cfg.get("google_cx"):
            enabled.add("google")
            # serper also proxies Google — drop it to avoid double-counting coverage
        elif cfg.get("serper_api_key"):
            enabled.add("serper")
        if cfg.get("yandex_user") and cfg.get("yandex_key"):
            enabled.add("yandex")
        if cfg.get("mojeek_api_key"):
            enabled.add("mojeek")
        if cfg.get("brave_api_key"):
            enabled.add("brave")
        if args.ghdb or os.path.exists(ghdb_path):
            enabled.add("ghdb")

    # ── dork augmentation ────────────────────────────────────────────────────
    # Build a list of web queries: the plain query plus dork-augmented variants.
    # Each variant prepends Google operator tokens from the best-matching GHDB
    # entries, e.g. `inurl:"/admin/login" YOUR QUERY`.  Operator values are
    # retained so each variant remains a valid narrowed search.
    dork_k = args.dork_k if args.dork_k is not None else 2
    web_queries = [query]
    if (args.dork_augment or args.dork_k is not None) and os.path.exists(ghdb_path):
        augmented = ghdb_augment_query(query, ghdb_path, top_k=dork_k)
        for aq in augmented:
            if aq != query:
                web_queries.append(aq)
        if len(web_queries) > 1:
            print(
                f"[dork-augment] {len(web_queries)-1} variant(s):",
                file=sys.stderr,
            )
            for aq in web_queries[1:]:
                print(f"  {aq}", file=sys.stderr)

    # ── cache lookup ─────────────────────────────────────────────────────────
    web_engines = {e for e in enabled if e not in ("ghdb",)}
    _dork_active = args.dork_augment or args.dork_k is not None
    engine_config = {
        "searxng_url": cfg.get("searxng_url", ""),
        "brave_api": bool(cfg.get("brave_api_key")),
        "proxy": cfg.get("proxy", ""),
    }
    cache_key = _cache_key(
        query, enabled, profile, dork_k, _dork_active, use_infra,
        args.results, args.top, extra_weights, args.no_semantic, ghdb_path,
        engine_config,
    )
    cached = None if args.no_cache else _cache_get(cache_key)
    _eff_weights = effective_weights(extra_weights, args.no_semantic, use_infra, profile)

    if cached is not None:
        print("[cache] hit — returning cached results (use --no-cache to bypass)",
              file=sys.stderr)
        _AGG_FIELDS = {"url", "title", "snippet", "engines", "ranks", "score", "components"}
        results = [
            AggResult(**{k: v for k, v in r.items() if k in _AGG_FIELDS}) for r in cached
        ]
    else:
        # ── collect hits (parallel) ───────────────────────────────────────────
        all_hits: list[Hit] = []

        tasks = [(eng, wq) for wq in web_queries for eng in sorted(web_engines)]
        max_workers = min(len(tasks), 8) if tasks else 1
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(_dispatch_engine, eng, wq, args.results, cfg): (eng, wq)
                for eng, wq in tasks
            }
            for future in as_completed(future_map):
                eng, wq, hits = future.result()
                label = eng if wq == query else f"{eng}+dork"
                print(f"[{label}] {len(hits)} hits", file=sys.stderr)
                all_hits.extend(hits)

        if "ghdb" in enabled:
            ghdb_hits = engine_ghdb(query, args.results, ghdb_path)
            print(f"[ghdb] {len(ghdb_hits)} dorks matched", file=sys.stderr)
            all_hits.extend(ghdb_hits)

        if not all_hits:
            print("no results — check engine availability / API keys", file=sys.stderr)
            sys.exit(1)

        results, _eff_weights = aggregate(
            all_hits, query,
            top_n=args.top,
            weights=extra_weights or None,
            no_semantic=args.no_semantic,
            infra=use_infra,
            profile=profile,
        )

        if not args.no_cache:
            _cache_set(cache_key, [
                {"url": r.url, "title": r.title, "snippet": r.snippet,
                 "engines": r.engines, "ranks": r.ranks,
                 "score": r.score, "components": r.components}
                for r in results
            ])

    # ── fetch augmentation (--fetch N) ───────────────────────────────────────
    if args.fetch > 0:
        if cfg.get("proxy"):
            print("[fetch] direct vetted-IP fetch does not use AVAILGATE_PROXY",
                  file=sys.stderr)
        results = fetch_augment(results, query, args.fetch, None, _eff_weights)

    if args.json:
        print_json(results)
    elif args.plain or not HAS_RICH:
        print_plain(results, query)
    else:
        print_rich(results, query)


if __name__ == "__main__":
    main()


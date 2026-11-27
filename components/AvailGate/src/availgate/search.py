"""Search orchestration, transparent modes, and provenance."""

import hashlib
import math
import time
from dataclasses import asdict
from datetime import date
from urllib.parse import urlparse

from .config import load
from .contracts import Problem, response, utc
from .providers import ENGINES, UPSTREAM, run_provider, selected
from .storage import Store, cache_key
from .workers import run_jobs

MODES = ("general", "docs", "repository", "compare", "recent")


def domain(value):
    try:
        result = value.strip().lower().encode("idna").decode("ascii")
        if not result or any(c in result for c in "/:@?# ") or ".." in result:
            raise ValueError()
        return result.rstrip(".")
    except (UnicodeError, ValueError):
        raise Problem("domain", "Domains must be hostnames without schemes, ports, or paths.", invalid=True)


def queries_for(query, mode, domains=(), alternatives=()):
    variants = [query]
    suffixes = {"docs": ("documentation", "reference manual"),
                "repository": ("source code repository", "official repository"),
                "recent": ("release notes", "changelog")}
    variants += [query + " " + suffix for suffix in suffixes.get(mode, ())]
    if mode == "compare":
        variants += [query + " " + alternative for alternative in alternatives]
    if domains:
        suffix = " (" + " OR ".join("site:" + value for value in domains) + ")"
        variants = [value + suffix for value in variants]
    return list(dict.fromkeys(variants))[:3]


def _engine_queries(engine, queries, count, config):
    outcomes = []
    for index, query in enumerate(queries):
        if index and engine in ("bing", "brave"):
            time.sleep(2)
        outcome = run_provider(engine, query, count, config)
        outcomes.append(outcome)
        if outcome["status"] in ("rate_limited", "unavailable"):
            for remaining in queries[index + 1:]:
                outcomes.append({**outcome, "query": remaining, "hits": [], "hit_count": 0,
                                 "duration_ms": 0, "request_count": 0})
            break
    return outcomes


def search(query, *, engines=None, mode="general", top=10, results=20,
           timeout=30, no_cache=False, domains=(), official_domains=(),
           alternatives=(), since=None, profile="", session=None, config=None):
    started = time.time()
    if not isinstance(query, str) or not query.strip() or len(query) > 4096:
        raise Problem("query", "Query must contain 1–4096 characters.", invalid=True)
    if mode not in MODES or profile not in ("", "infra", "content"):
        raise Problem("mode", "Unknown research mode or ranking profile.", invalid=True)
    if not 1 <= top <= 100 or not 1 <= results <= 50 or not math.isfinite(timeout) or not 0.1 <= timeout <= 300:
        raise Problem("limits", "Use top 1–100, results 1–50, timeout 0.1–300 seconds.", invalid=True)
    if len(alternatives) > 2 or any(not x.strip() or len(x) > 256 for x in alternatives):
        raise Problem("alternatives", "Supply at most two nonempty alternatives of at most 256 characters.", invalid=True)
    if len(domains) > 10 or len(official_domains) > 10:
        raise Problem("domain", "At most ten domain filters and ten official domains are supported.", invalid=True)
    domains, official_domains = [domain(d) for d in domains], [domain(d) for d in official_domains]
    if since:
        try:
            date.fromisoformat(since)
        except ValueError:
            raise Problem("date", "Use a date in YYYY-MM-DD format.", invalid=True)
    config, warnings = load(config)
    enabled = selected(config, engines)
    if not enabled or any(engine not in ENGINES for engine in enabled):
        raise Problem("engines", "Select known providers: " + ", ".join(ENGINES), invalid=True)
    queries = queries_for(query, mode, domains, alternatives)
    if mode == "recent":
        warnings.append("Recent mode adds release/changelog queries; source dates may be unknown. Use --no-cache for fresh observations.")
    if mode == "compare" and not alternatives:
        warnings.append("Use --alternative twice to collect separate comparison queries.")
    if since:
        warnings.append("Date filter is local: results with unknown/unparseable source dates are excluded. Provider-side date filters are not implemented.")
    warnings.append("Provider agreement is a relevance signal; shared or unknown upstream indexes are not independent corroboration.")
    if "ddg" in enabled:
        warnings.append("DDG internal request counts are unavailable; its process is bounded by the overall deadline.")
    options = {"mode": mode, "top": top, "results_per_engine": results, "engines": enabled,
               "domains": domains, "official_domains": official_domains, "profile": profile,
               "since": since, "semantic": False, "alternatives": list(alternatives),
               "limits": {"timeout_seconds": timeout, "query_variants": 3,
                          "concurrency": 4, "requests_per_provider_query": 5,
                          "provider_response_bytes": 2097152, "retries": 0}}
    store = Store() if not no_cache or session else None
    if session:
        store.require(session)
    stamp = None
    if config.get("ghdb_path"):
        from pathlib import Path
        try:
            info = Path(config["ghdb_path"]).stat()
            stamp = [info.st_size, info.st_mtime_ns]
        except OSError:
            pass
    key = cache_key("search-v1", [query, options, config, stamp])
    cached = store.cached(key) if not no_cache else None
    if cached:
        value, cache = cached
        value = response("search", started=started, **{k: v for k, v in value.items()
                         if k not in ("schema_version", "operation", "request_id", "started_at", "completed_at", "elapsed_ms", "cache")}, cache=cache)
    else:
        outcomes = []
        jobs = [(engine, queries, results, config) for engine in enabled]
        for engine, result in zip(enabled, run_jobs(_engine_queries, jobs, timeout=timeout)):
            if "value" in result:
                outcomes.extend(result["value"])
            else:
                outcomes.extend({"engine": engine, "query": q, "upstream": UPSTREAM[engine],
                                 "status": result["failure"], "hit_count": 0, "hits": [],
                                 "request_count": None, "duration_ms": None,
                                 "errors": [{"code": result["failure"], "message": "Provider worker did not complete before termination."}]}
                                for q in queries)
        from .legacy import Hit, aggregate, canonicalize
        hits = []
        for outcome in outcomes:
            for item in outcome["hits"]:
                parsed = urlparse(item["url"])
                if outcome["engine"] != "ghdb" and (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password):
                    continue
                if domains and (parsed.hostname or "").lower() not in domains:
                    continue
                if since:
                    try:
                        if date.fromisoformat((item.get("date") or "")[:10]) < date.fromisoformat(since):
                            continue
                    except ValueError:
                        continue
                hits.append(Hit(**item))
        ranked, weights = aggregate(hits, query, top_n=top, no_semantic=True,
                                    profile=profile, infra=profile == "infra")
        items = []
        for result in ranked:
            item = asdict(result)
            host = (urlparse(result.url).hostname or "").lower()
            source_hits = [h for h in hits if canonicalize(h.url) == canonicalize(result.url)]
            item.update(id=hashlib.sha256(canonicalize(result.url).encode()).hexdigest()[:24],
                        kind="query_template" if result.engines == ["ghdb"] else "page",
                        official={"status": "configured" if host in official_domains else "unknown",
                                  "basis": "user-provided exact hostname" if host in official_domains else None},
                        source_dates=[{"engine": h.engine, "value": h.date} for h in source_hits if h.date],
                        explanation=[{"signal": name, "value": result.components.get(name, 0),
                                      "weight": weight} for name, weight in weights.items()])
            items.append(item)
        completed = sum(o["status"] in ("success", "empty", "partial") for o in outcomes)
        failed = any(o["status"] not in ("success", "empty") for o in outcomes)
        status = "error" if not completed else "partial" if failed else "ok"
        provider_info = [{k: v for k, v in outcome.items() if k != "hits"} for outcome in outcomes]
        value = response("search", status=status, started=started, query=query, queries=queries,
                         options=options, effective_weights=weights, providers=provider_info,
                         results=items, warnings=warnings,
                         errors=[{"code": "providers_failed", "message": "No provider completed."}] if status == "error" else [],
                         cache={"hit": False, "retrieved_at": utc(), "age_seconds": 0,
                                "expires_at": utc(time.time() + 86400) if not no_cache else None})
        # Do not mask provider outages behind cached partial responses.
        if not no_cache and status == "ok":
            store.cache(key, value)
    if session:
        store.save_event(session, "search", value)
    return value

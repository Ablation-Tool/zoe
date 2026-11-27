"""Bounded adapters around the existing provider implementations."""

import contextlib
import io
import time
from dataclasses import asdict
from pathlib import Path

ENGINES = ("ddg", "bing", "brave", "searxng", "google", "serper", "yandex", "mojeek", "ghdb")
KEYS = {"google": ("google_api_key", "google_cx"), "serper": ("serper_api_key",),
        "yandex": ("yandex_user", "yandex_key"), "mojeek": ("mojeek_api_key",)}
UPSTREAM = {"google": "google", "serper": "google", "bing": "bing",
            "ddg": "multiple/unknown", "searxng": "multiple/unknown",
            "brave": "brave", "yandex": "yandex", "mojeek": "mojeek", "ghdb": "local"}


class RequestLimit(Exception):
    pass


def selected(config, engines=None):
    if engines is not None:
        return sorted(set(engines))
    result = ["ddg", "bing", "brave", "searxng"]
    result += [name for name, keys in KEYS.items() if all(config.get(key) for key in keys)]
    if "google" in result and "serper" in result:
        result.remove("serper")
    if config.get("ghdb_path"):
        result.append("ghdb")
    return sorted(set(result))


def error_category(error):
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 429 or "ratelimit" in type(error).__name__.lower():
        return "rate_limited"
    if "timeout" in type(error).__name__.lower():
        return "timeout"
    if isinstance(error, RequestLimit):
        return "limit"
    return "error"


def run_provider(engine, query, count, config):
    """Run only inside a dedicated worker: request hooks are process-local."""
    started = time.monotonic()
    from . import legacy
    events = []
    legacy._error_observer = lambda error: events.append(error_category(error))
    outcome = {"engine": engine, "query": query, "upstream": UPSTREAM.get(engine, "unknown"),
               "status": "empty", "hits": [], "duration_ms": 0, "hit_count": 0,
               "errors": [], "request_count": 0}
    missing = [key for key in KEYS.get(engine, ()) if not config.get(key)]
    if engine not in ENGINES or missing or (engine == "ddg" and not legacy.HAS_DDG) or (
        engine not in ("ddg", "ghdb") and not legacy.HAS_REQUESTS
    ) or (engine == "ghdb" and not Path(config.get("ghdb_path", "")).is_file()):
        outcome.update(status="unavailable", errors=[{"code": "unavailable",
                       "message": "Provider is unknown, missing configuration, corpus, or dependencies."}])
        return outcome

    requests_made = 0
    original = None
    if legacy.HAS_REQUESTS:
        import requests
        original = requests.sessions.Session.request

        def bounded_request(session, method, url, **kwargs):
            nonlocal requests_made
            requests_made += 1
            if requests_made > 5:
                raise RequestLimit()
            kwargs.update(stream=True, timeout=(5, 8), allow_redirects=False)
            if config.get("proxy"):
                kwargs["proxies"] = {"http": config["proxy"], "https": config["proxy"]}
            result = original(session, method, url, **kwargs)
            try:
                result.raise_for_status()
                if 300 <= result.status_code < 400:
                    raise requests.HTTPError(response=result)
                body = bytearray()
                for chunk in result.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise RequestLimit()
                result._content = bytes(body)
                result._content_consumed = True
                return result
            finally:
                result.close()

        requests.sessions.Session.request = bounded_request
    try:
        # Provider exception text can contain API keys; never forward it.
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            if engine == "ghdb":
                hits = legacy.engine_ghdb(query, count, config["ghdb_path"])
            else:
                legacy._get_session(config.get("proxy", ""))
                _, _, hits = legacy._dispatch_engine_inner(engine, query, count, config)
        outcome["hits"] = [asdict(hit) for hit in hits[:count]]
        for hit in outcome["hits"]:
            for field in ("url", "title", "snippet"):
                hit[field] = str(hit[field])[:8000]
        outcome["hit_count"] = len(outcome["hits"])
        outcome["status"] = "success" if hits else "empty"
        if events:
            outcome["status"] = "partial" if hits else events[-1]
            outcome["errors"] = [{"code": code, "message": "Provider request did not complete."}
                                 for code in sorted(set(events))]
    except Exception as error:
        code = error_category(error)
        outcome.update(status=code, errors=[{"code": code, "message": "Provider request did not complete."}])
    finally:
        if original is not None:
            requests.sessions.Session.request = original
        legacy._error_observer = None
    outcome["request_count"] = requests_made if engine != "ddg" else None
    outcome["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
    return outcome

"""Public-page reading with bounded direct connections and source captures."""

import hashlib
import math
import re
import ssl
import time
from email.message import Message
from urllib.parse import urljoin, urlparse

from .config import load
from .contracts import Problem, failed, response, utc
from .storage import Store, cache_key
from .workers import run_jobs

MAX_BYTES = 2 * 1024 * 1024
EXTRACTOR_VERSION = "1"


def extract(body, content_type, *, max_chars):
    """Offsets refer to Unicode code points in the exact returned text."""
    from bs4 import BeautifulSoup
    header = Message()
    header["content-type"] = content_type
    mime = header.get_content_type()
    title = ""
    published = modified = None
    if mime == "text/plain":
        encoding = header.get_content_charset() or "utf-8"
        try:
            text = body.decode(encoding, errors="replace")
        except LookupError:
            raise Problem("encoding", "Unsupported text encoding.")
    elif mime in ("text/html", "application/xhtml+xml"):
        soup = BeautifulSoup(body, "html.parser", from_encoding=header.get_content_charset())
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for key, dest in (("article:published_time", "published"), ("article:modified_time", "modified")):
            tag = soup.find("meta", attrs={"property": key})
            if tag and tag.get("content"):
                if dest == "published":
                    published = tag["content"]
                else:
                    modified = tag["content"]
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "template"]):
            tag.decompose()
        root = soup.find("main") or soup.find("article") or soup
        # Preserve preformatted code before splitting ordinary blocks.
        for tag in root.find_all("pre"):
            tag.replace_with("\n\n" + tag.get_text() + "\n\n")
        for tag in root.find_all(["p", "div", "section", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr"]):
            tag.insert_before("\n")
            tag.insert_after("\n")
        text = root.get_text()
        text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text).strip()
    else:
        raise Problem("unsupported_content_type", "Only HTML, XHTML, and plain text are supported.")
    truncated = len(text) > max_chars
    text = text[:max_chars]
    if not text.strip():
        raise Problem("empty_document", "No readable text was extracted; the page may require JavaScript.")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"title": title[:1000], "text": text, "text_hash": digest,
            "extractor_version": EXTRACTOR_VERSION, "truncated": truncated,
            "published_at": published, "modified_at": modified,
            "date_basis": "unverified page metadata", "content_type": mime,
            "excerpts": [{"start": 0, "end": min(1000, len(text)), "text": text[:1000],
                          "offset_unit": "unicode_code_point"}]}


def fetch(url, max_chars):
    import urllib3
    from .legacy import _public_fetch_target
    requested = url
    redirects = []
    for hop in range(6):
        target = _public_fetch_target(url)
        if target is None:
            raise Problem("blocked_destination", "Destination is invalid, unresolvable, or not exclusively public.")
        parsed, address, port = target
        host = parsed.hostname
        authority = f"[{host}]" if ":" in host else host
        if port != (443 if parsed.scheme == "https" else 80):
            authority += f":{port}"
        path = parsed.path or "/"
        if parsed.params:
            path += ";" + parsed.params
        if parsed.query:
            path += "?" + parsed.query
        if parsed.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(address, port=port, server_hostname=host,
                     assert_hostname=host, ssl_context=ssl.create_default_context())
        else:
            pool = urllib3.HTTPConnectionPool(address, port=port)
        result = None
        try:
            result = pool.urlopen("GET", path, headers={"Host": authority,
                  "User-Agent": "AvailGate/0.2 source-reader", "Accept-Encoding": "identity"},
                  timeout=urllib3.Timeout(connect=5, read=8), retries=False,
                  redirect=False, preload_content=False)
            if 300 <= result.status < 400:
                location = result.headers.get("Location")
                if not location or hop == 5:
                    raise Problem("redirect_limit", "Missing redirect destination or redirect limit exceeded.")
                next_url = urljoin(url, location)
                redirects.append({"url": url, "status": result.status})
                url = next_url
                continue
            if result.status != 200:
                raise Problem("http_status", f"Source returned HTTP {result.status}.")
            mime = result.headers.get("Content-Type", "application/octet-stream")
            if mime.split(";")[0].strip().lower() not in ("text/html", "text/plain", "application/xhtml+xml"):
                raise Problem("unsupported_content_type", "Only HTML, XHTML, and plain text are supported.")
            body = bytearray()
            for chunk in result.stream(amt=65536, decode_content=True):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise Problem("body_limit", "Decoded source exceeds the 2 MiB limit.")
            document = extract(bytes(body), mime, max_chars=max_chars)
            document.update(id=hashlib.sha256((url + document["text_hash"]).encode()).hexdigest()[:24],
                            requested_url=requested, final_url=url, redirects=redirects,
                            retrieved_at=utc(), transport="direct_vetted_ip",
                            http_last_modified=result.headers.get("Last-Modified"))
            return document
        finally:
            if result is not None:
                result.release_conn()
            pool.close()
    raise Problem("redirect_limit", "Redirect limit exceeded.")


def _read_worker(url, max_chars):
    try:
        return {"document": fetch(url, max_chars)}
    except Problem as problem:
        return {"error": problem.as_dict()}
    except Exception:
        return {"error": {"code": "network_or_tls", "message": "Source connection, TLS verification, or extraction failed."}}


def read(url, *, timeout=30, max_chars=40000, no_cache=False, proxy_only=False,
         session=None, config=None):
    started = time.time()
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        parsed.port
        if len(url) > 8192:
            raise ValueError()
    except ValueError:
        raise Problem("url", "Supply an HTTP(S) URL without embedded credentials, at most 8192 characters.", invalid=True)
    if not 1 <= max_chars <= 200000 or not math.isfinite(timeout) or not 0.1 <= timeout <= 300:
        raise Problem("limits", "Use max-chars 1–200000 and timeout 0.1–300 seconds.", invalid=True)
    config, warnings = load(config)
    if config.get("proxy"):
        warnings.append("Source reads use direct vetted-IP connections; the search proxy is not used.")
    store = Store() if not no_cache or session else None
    if session:
        store.require(session)
    key = cache_key("read-v1", [url, max_chars, EXTRACTOR_VERSION])
    cached = store.cached(key) if not no_cache else None
    if cached:
        doc, cache = cached
    else:
        if proxy_only or config.get("proxy_only") is True:
            raise Problem("proxy_only", "Direct source reads are disabled. Proxy-only source transport is not implemented.")
        outcome = run_jobs(_read_worker, [(url, max_chars)], timeout=timeout, concurrency=1)[0]
        if "failure" in outcome:
            result = failed("read", Problem(outcome["failure"], "Source worker did not complete before termination."), started=started)
        elif "error" in outcome["value"]:
            error = outcome["value"]["error"]
            result = failed("read", Problem(error["code"], error["message"]), started=started)
        else:
            result = None
        if result:
            result["warnings"] = warnings
            if session:
                store.save_event(session, "read", result)
            return result
        doc = outcome["value"]["document"]
        cache = {"hit": False, "retrieved_at": doc["retrieved_at"], "age_seconds": 0,
                 "expires_at": utc(time.time() + 86400) if not no_cache else None}
        if not no_cache:
            store.cache(key, doc)
    value = response("read", status="partial" if doc["truncated"] else "ok", started=started,
                     document=doc, cache=cache, warnings=warnings + (["Extracted text was truncated."] if doc["truncated"] else []))
    if session:
        store.save_event(session, "read", value)
    return value

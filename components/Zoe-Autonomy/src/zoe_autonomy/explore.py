from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib import parse as urlparse
from urllib import robotparser

from .actuation import ActuationPolicy, timestamp, write_json


USER_AGENT = "ZoeOneResearchBot/1.0"
MAX_LINKS_PER_PAGE = 100
EXCERPT_BYTES = 4000


class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.title_parts = []
        self.text_parts = []
        self.links = []
        self.in_title = False
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and not self.hidden:
            for key, value in attrs:
                if key == "href" and value:
                    absolute = urlparse.urljoin(self.base_url, value)
                    parsed = urlparse.urlparse(absolute)
                    if parsed.scheme in {"http", "https"} and parsed.hostname:
                        self.links.append(urlparse.urlunparse(parsed._replace(fragment="")))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"} and self.hidden:
            self.hidden -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title_parts.append(data)
        elif data.strip():
            self.text_parts.append(data.strip())


def normalized_url(url):
    parsed = urlparse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("exploration requires a public HTTP(S) URL without embedded credentials")
    return urlparse.urlunparse(parsed._replace(fragment=""))


class WebExplorer:
    def __init__(self, policy=None, user_agent=USER_AGENT):
        self.policy = policy or ActuationPolicy()
        self.user_agent = user_agent
        self._robots = {}

    def _request(self, url):
        return self.policy.execute({
            "kind": "network",
            "url": url,
            "method": "GET",
            "headers": {"User-Agent": self.user_agent},
            "timeout": 30,
        })

    def _robots_allowed(self, url):
        parsed = urlparse.urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            robots_url = f"{origin}/robots.txt"
            try:
                response = self._request(robots_url)
                status = response["result"]["status"]
                body = response["result"]["body"]
                if status == 200:
                    parser = robotparser.RobotFileParser()
                    parser.parse(body.splitlines())
                    self._robots[origin] = ("rules", parser)
                elif status in {401, 403}:
                    self._robots[origin] = ("deny", None)
                elif 400 <= status < 500:
                    self._robots[origin] = ("allow", None)
                else:
                    self._robots[origin] = ("deny", None)
            except Exception:
                self._robots[origin] = ("deny", None)
        mode, parser = self._robots[origin]
        if mode == "rules":
            return parser.can_fetch(self.user_agent, url)
        return mode == "allow"

    def explore(self, start_url, max_pages=5, max_depth=1, delay=.5):
        start_url = normalized_url(start_url)
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 25:
            raise ValueError("max_pages must be from 1 to 25")
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 0 <= max_depth <= 2:
            raise ValueError("max_depth must be from 0 to 2")
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not .1 <= delay <= 30:
            raise ValueError("delay must be from 0.1 to 30 seconds")
        origin = urlparse.urlparse(start_url).netloc
        queue = [(start_url, 0)]
        visited = set()
        pages = []
        errors = []
        external_actions = 0
        started = timestamp()
        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            if not self._robots_allowed(url):
                errors.append({"url": url, "error": "robots.txt or robots-fetch policy disallowed this URL"})
                continue
            try:
                response = self._request(url)
                external_actions += 1
                result = response["result"]
                if not 200 <= result["status"] < 300:
                    errors.append({"url": url, "status": result["status"]})
                    continue
                content_type = (result.get("content_type") or "").lower()
                if "html" not in content_type and not content_type.startswith("text/plain"):
                    errors.append({"url": url, "error": f"unsupported content type: {content_type}"})
                    continue
                body = result["body"]
                if "html" in content_type:
                    parser = PageParser(url)
                    parser.feed(body)
                    parser.close()
                    title = " ".join(" ".join(parser.title_parts).split())
                    text = " ".join(" ".join(parser.text_parts).split())
                    candidates = parser.links[:MAX_LINKS_PER_PAGE]
                else:
                    title = ""
                    text = " ".join(body.split())
                    candidates = []
                pages.append({
                    "url": url,
                    "depth": depth,
                    "status": result["status"],
                    "title": title,
                    "excerpt": text[:EXCERPT_BYTES],
                    "excerpt_truncated": len(text) > EXCERPT_BYTES,
                    "links_found": len(candidates),
                    "audit_hash": response["audit_hash"],
                })
                if depth < max_depth:
                    for candidate in candidates:
                        if candidate not in visited and urlparse.urlparse(candidate).netloc == origin:
                            queue.append((candidate, depth + 1))
                if delay and queue and len(pages) < max_pages:
                    time.sleep(delay)
            except Exception as error:
                errors.append({"url": url, "error": f"{type(error).__name__}: {str(error)[:500]}"})
        return {
            "schema_version": 1,
            "instrument": "zoe-bounded-web-exploration",
            "started_utc": started,
            "finished_utc": timestamp(),
            "start_url": start_url,
            "user_agent": self.user_agent,
            "same_origin_only": True,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "delay_seconds": delay,
            "robots_txt_respected": True,
            "pages_fetched": len(pages),
            "pages": pages,
            "errors": errors,
            "external_page_requests": external_actions,
            "scope": "Read-only HTTP(S) exploration from an explicit URL. Same-origin links only, bounded pages and depth, robots.txt and rate limits enforced. No login, form submission, credential use, or authentication bypass.",
        }


def explore_main(argv=None):
    parser = argparse.ArgumentParser(prog="zoe-autonomy explore", description="Bounded read-only internet exploration with robots.txt and same-origin limits")
    parser.add_argument("--url", required=True)
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--delay", type=float, default=.5)
    parser.add_argument("--output", help="new JSON evidence path")
    arguments = parser.parse_args(argv)
    report = WebExplorer().explore(arguments.url, arguments.pages, arguments.depth, arguments.delay)
    if arguments.output:
        write_json(Path(arguments.output).expanduser().resolve(), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["pages_fetched"] else 1

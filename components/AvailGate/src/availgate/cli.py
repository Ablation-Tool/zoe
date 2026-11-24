"""Modern subcommands alongside the original query/flags interface."""

import argparse
import importlib.util
import json
import sqlite3
import sys
from importlib.resources import files

from . import __version__
from .config import load, paths
from .contracts import Problem, failed, response

COMMANDS = ("search", "read", "session", "capabilities", "doctor", "cache", "agent-guide")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse may echo a sensitive argument; expose a stable diagnostic.
        raise Problem("arguments", "Invalid or missing arguments. Run this command with --help for usage.", invalid=True)


def parser():
    root = Parser(prog="availgate", description="Search, read sources, and save research for coding agents.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True, parser_class=Parser)
    search = commands.add_parser("search", help="Discover and rank source URLs")
    search.add_argument("query", nargs="+")
    search.add_argument("--engines", help="Comma-separated providers")
    search.add_argument("--mode", choices=("general", "docs", "repository", "compare", "recent"), default="general")
    search.add_argument("--profile", choices=("infra", "content"), default="")
    search.add_argument("--top", type=int, default=10)
    search.add_argument("--results", type=int, default=20)
    search.add_argument("--domain", action="append", default=[])
    search.add_argument("--official-domain", action="append", default=[])
    search.add_argument("--alternative", action="append", default=[])
    search.add_argument("--since", help="Local YYYY-MM-DD source-date filter; excludes unknown dates")
    search.add_argument("--ghdb-path")
    search.add_argument("--no-semantic", action="store_true", help="Compatibility option; modern search already disables semantic loading")
    read = commands.add_parser("read", help="Capture readable text from a public page")
    read.add_argument("url")
    read.add_argument("--max-chars", type=int, default=40000)
    read.add_argument("--proxy-only", action="store_true", help="Allow cached documents but refuse direct network reads")
    for command in (search, read):
        command.add_argument("--json", action="store_true")
        command.add_argument("--timeout", type=float, default=30)
        command.add_argument("--no-cache", action="store_true")
        command.add_argument("--session")
    sessions = commands.add_parser("session", help="Local saved research")
    sub = sessions.add_subparsers(dest="action", required=True, parser_class=Parser)
    for action in ("create", "list", "show", "note", "question", "export", "delete"):
        cmd = sub.add_parser(action)
        if action != "list":
            cmd.add_argument("name")
        if action in ("note", "question"):
            cmd.add_argument("text")
        if action == "export":
            cmd.add_argument("--format", choices=("json", "markdown"), default="json")
        if action == "delete":
            cmd.add_argument("--yes", action="store_true", help="Required acknowledgement of permanent deletion")
        cmd.add_argument("--json", action="store_true")
    for name in ("capabilities", "doctor", "agent-guide"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--json", action="store_true")
        if name == "doctor":
            cmd.add_argument("--network", action="store_true")
            cmd.add_argument("--timeout", type=float, default=20)
    cache = commands.add_parser("cache")
    cache.add_argument("action", choices=("clear",))
    cache.add_argument("--json", action="store_true")
    return root


def execute(args):
    if args.command == "search":
        from .search import search
        return search(" ".join(args.query), engines=[x.strip() for x in args.engines.split(",")] if args.engines is not None else None,
                      mode=args.mode, top=args.top, results=args.results, timeout=args.timeout,
                      no_cache=args.no_cache, domains=args.domain, official_domains=args.official_domain,
                      alternatives=args.alternative, since=args.since, profile=args.profile,
                      session=args.session, config={"ghdb_path": args.ghdb_path})
    if args.command == "read":
        from .reader import read
        return read(args.url, timeout=args.timeout, max_chars=args.max_chars,
                    no_cache=args.no_cache, proxy_only=args.proxy_only, session=args.session)
    if args.command == "capabilities":
        from .providers import ENGINES
        return response("capabilities", version=__version__, commands=list(COMMANDS),
                        available_providers=list(ENGINES), modes=["general", "docs", "repository", "compare", "recent"],
                        content_types=["text/html", "application/xhtml+xml", "text/plain"],
                        semantic_default=False, network_required=False,
                        response_schema="resources/response.schema.json",
                        limitations=["No JavaScript rendering, authenticated pages, PDF, or OCR.",
                                     "Modes are query templates, not a validated relevance improvement.",
                                     "Provider-side date filters are not implemented."])
    if args.command == "agent-guide":
        return response("agent-guide", text=files("availgate").joinpath("resources/AGENT-GUIDE.md").read_text(encoding="utf-8"))
    if args.command == "doctor":
        config, warnings = load()
        checks = {name: importlib.util.find_spec(module) is not None for name, module in
                  (("requests", "requests"), ("urllib3", "urllib3"), ("beautifulsoup4", "bs4"), ("ddgs", "ddgs"))}
        from .providers import selected
        value = response("doctor", status="ok" if all(checks.values()) else "partial",
                         version=__version__, dependencies=checks, enabled_providers=selected(config),
                         configuration_path=str(paths()[0]), data_directory=str(paths()[1]), warnings=warnings,
                         network_checked=args.network)
        if args.network:
            from .search import search
            probe = search("example.com domain", top=3, results=3, timeout=args.timeout, no_cache=True)
            value.update(status=probe["status"], providers=probe["providers"], errors=probe["errors"])
        return value
    from .storage import Store, markdown
    store = Store()
    if args.command == "cache":
        return response("cache", removed_entries=store.clear_cache())
    action = args.action
    if action == "create":
        data = store.create(args.name)
    elif action == "list":
        data = store.list()
    elif action in ("show", "export"):
        data = store.show(args.name)
        if action == "export" and args.format == "markdown":
            return response("session.export", text=markdown(data))
    elif action in ("note", "question"):
        if not args.text.strip() or len(args.text) > 20000:
            raise Problem("note", "Notes/questions must contain 1–20000 characters.", invalid=True)
        store.append(args.name, action, {"text": args.text, "authorship": "agent_or_user"})
        data = {"name": args.name, "saved": action}
    else:
        if not args.yes:
            raise Problem("delete", "Use --yes to permanently delete this session and its saved evidence.", invalid=True)
        data = store.delete(args.name)
    return response("session." + action, data=data)


def render(value, json_mode):
    if json_mode:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    elif "text" in value:
        print(value["text"], end="" if value["text"].endswith("\n") else "\n")
    elif value["operation"] == "search" and "results" in value:
        print(f"AvailGate: {value['status']} — {len(value['results'])} results")
        for index, item in enumerate(value["results"], 1):
            print(f"\n{index}. {item['title']}\n   {item['url']}\n   {item['snippet']}")
    elif value["operation"] == "read" and "document" in value:
        document = value["document"]
        print(f"{document['title']}\n{document['final_url']}\n\n{document['text']}")
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    if not json_mode:
        for warning in value.get("warnings", []):
            print("Warning: " + warning, file=sys.stderr)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] not in COMMANDS and arguments[0] not in ("--help", "-h", "--version"):
        from .legacy import main as legacy_main
        previous = sys.argv
        try:
            sys.argv = ["availgate", *arguments]
            legacy_main()
            return 0
        finally:
            sys.argv = previous
    operation = arguments[0] if arguments else "cli"
    flags = arguments[:arguments.index("--")] if "--" in arguments else arguments
    json_mode = "--json" in flags
    code = 0
    try:
        args = parser().parse_args(arguments)
        value = execute(args)
        code = 1 if value["status"] == "error" else 0
    except Problem as problem:
        value = failed(operation, problem)
        code = 2 if problem.invalid else 1
    except (OSError, sqlite3.Error):
        value = failed(operation, Problem("storage_or_io", "A local file or database operation failed; check paths, permissions, and free space."))
        code = 1
    except KeyboardInterrupt:
        value = failed(operation, Problem("interrupted", "Operation interrupted."))
        code = 130
    render(value, json_mode)
    return code

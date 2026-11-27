from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capabilities import (
    AgentProtocolConnector,
    BrowserAutomation,
    ComputeRunner,
    ConnectedServices,
    InstrumentRegistry,
    JobScheduler,
    MCPClient,
    MediaTools,
    Notifier,
    ResearchConnector,
    ResearchMemory,
)


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


def capabilities_main(argv=None):
    parser = argparse.ArgumentParser(prog="zoe-autonomy capabilities", description="Zoe One unified capability pack")
    commands = parser.add_subparsers(dest="capability", required=True)
    browser = commands.add_parser("browser")
    browser.add_argument("--url", required=True)
    browser.add_argument("--screenshot")
    browser.add_argument("--headless", action="store_true")
    research = commands.add_parser("research")
    research.add_argument("--provider", choices=("crossref", "arxiv", "pubmed", "feed", "sitemap"), required=True)
    research.add_argument("--query", default="")
    research.add_argument("--url")
    research.add_argument("--limit", type=int, default=5)
    memory = commands.add_parser("memory")
    memory.add_argument("--db", required=True)
    memory.add_argument("action", choices=("add-source", "add-claim", "contradict", "search", "export"))
    memory.add_argument("--title", default="")
    memory.add_argument("--content", default="")
    memory.add_argument("--url", default="")
    memory.add_argument("--statement", default="")
    memory.add_argument("--source-id", type=int)
    memory.add_argument("--status", default="open")
    memory.add_argument("--claim-a", type=int)
    memory.add_argument("--claim-b", type=int)
    memory.add_argument("--reason", default="")
    memory.add_argument("--query", default="")
    service = commands.add_parser("service")
    service.add_argument("--url", required=True)
    service.add_argument("--token-env")
    service.add_argument("--method", default="GET")
    service.add_argument("--payload")
    github = commands.add_parser("github")
    github.add_argument("--path", required=True)
    jobs = commands.add_parser("jobs")
    jobs.add_argument("--path", required=True)
    jobs.add_argument("action", choices=("add", "run-due", "status"))
    jobs.add_argument("--id")
    jobs.add_argument("--argv")
    jobs.add_argument("--interval", type=int, default=0)
    jobs.add_argument("--timeout", type=float, default=60)
    compute = commands.add_parser("compute")
    compute.add_argument("--mode", choices=("local", "container"), default="local")
    compute.add_argument("--image")
    compute.add_argument("--argv", default="[]")
    compute.add_argument("--timeout", type=float, default=120)
    compute.add_argument("--gpu", action="store_true")
    mcp = commands.add_parser("mcp")
    mcp.add_argument("--argv", required=True)
    mcp.add_argument("--tool")
    mcp.add_argument("--arguments", default="{}")
    acp = commands.add_parser("acp")
    acp.add_argument("--url", required=True)
    notify = commands.add_parser("notify")
    notify.add_argument("--channel", choices=("desktop", "webhook"), required=True)
    notify.add_argument("--message", required=True)
    notify.add_argument("--url")
    notify.add_argument("--executable")
    media = commands.add_parser("media")
    media.add_argument("action", choices=("image", "wav", "ocr", "pdf", "video", "speak", "transcribe"))
    media.add_argument("--input", required=True)
    media.add_argument("--output")
    media.add_argument("--at", type=float, default=0)
    instruments = commands.add_parser("instruments")
    instruments.add_argument("--path", required=True)
    instruments.add_argument("action", choices=("add-sim", "add-serial", "execute", "list"))
    instruments.add_argument("--name")
    instruments.add_argument("--responses", default="{}")
    instruments.add_argument("--device")
    instruments.add_argument("--command", default="")
    instruments.add_argument("--payload", default="")
    instruments.add_argument("--read-bytes", type=int, default=0)
    arguments = parser.parse_args(argv)
    command = arguments.capability
    if command == "browser":
        return emit(BrowserAutomation().browse(arguments.url, arguments.screenshot, arguments.headless))
    if command == "research":
        connector = ResearchConnector()
        if arguments.provider in {"feed", "sitemap"}:
            result = connector.feed(arguments.url) if arguments.provider == "feed" else connector.sitemap(arguments.url)
        else:
            result = connector.search(arguments.provider, arguments.query, arguments.limit)
        return emit(result)
    if command == "memory":
        memory = ResearchMemory(arguments.db)
        if arguments.action == "add-source":
            result = {"source_id": memory.add_source(arguments.title, arguments.content, arguments.url)}
        elif arguments.action == "add-claim":
            result = {"claim_id": memory.add_claim(arguments.statement, arguments.source_id, arguments.status)}
        elif arguments.action == "contradict":
            result = {"contradiction_id": memory.contradict(arguments.claim_a, arguments.claim_b, arguments.reason)}
        elif arguments.action == "search":
            result = memory.search(arguments.query)
        else:
            result = memory.export()
        return emit(result)
    if command == "service":
        payload = json.loads(arguments.payload) if arguments.payload else None
        return emit(ConnectedServices().request(arguments.url, arguments.token_env, arguments.method, payload))
    if command == "github":
        return emit(ConnectedServices().github(arguments.path))
    if command == "jobs":
        scheduler = JobScheduler(arguments.path)
        if arguments.action == "add":
            result = scheduler.add(arguments.id, json.loads(arguments.argv), arguments.interval, arguments.timeout)
        elif arguments.action == "run-due":
            result = scheduler.run_due()
        else:
            result = scheduler.status()
        return emit(result)
    if command == "compute":
        runner = ComputeRunner()
        return emit(runner.gpu() if arguments.gpu else runner.run(json.loads(arguments.argv), arguments.mode, arguments.image, arguments.timeout))
    if command == "mcp":
        with MCPClient(json.loads(arguments.argv)) as client:
            client.initialize()
            client.initialized()
            result = client.list_tools()
            if arguments.tool:
                result = client.call_tool(arguments.tool, json.loads(arguments.arguments))
        return emit(result)
    if command == "acp":
        return emit(AgentProtocolConnector().acp_discover(arguments.url))
    if command == "notify":
        notifier = Notifier()
        if arguments.channel == "desktop":
            result = notifier.desktop(arguments.message, arguments.executable)
        else:
            if not arguments.url:
                raise ValueError("webhook notifications require --url")
            result = notifier.webhook(arguments.url, arguments.message)
        return emit(result)
    if command == "media":
        media = MediaTools()
        if arguments.action == "image":
            result = media.image_info(arguments.input)
        elif arguments.action == "wav":
            result = media.wav_info(arguments.input)
        elif arguments.action == "ocr":
            result = media.ocr(arguments.input)
        elif arguments.action == "pdf":
            result = media.pdf_text(arguments.input)
        elif arguments.action == "video":
            result = media.video_frame(arguments.input, arguments.output, arguments.at)
        elif arguments.action == "speak":
            result = media.speak(arguments.input, arguments.output)
        else:
            result = media.transcribe(arguments.input, arguments.output)
        return emit(result)
    registry = InstrumentRegistry(arguments.path)
    if arguments.action == "add-sim":
        result = registry.add_simulator(arguments.name, json.loads(arguments.responses))
    elif arguments.action == "add-serial":
        result = registry.add_serial(arguments.name, arguments.device)
    elif arguments.action == "execute":
        result = registry.execute(arguments.name, arguments.command, arguments.payload, arguments.read_bytes)
    else:
        result = registry._load()["instruments"]
    return emit(result)

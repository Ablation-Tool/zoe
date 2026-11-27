#!/usr/bin/env python3
"""
mcp-guard: MCP security proxy
Sits between an MCP client and a stdio MCP server.
Detects rug-pull attacks, injection in tool descriptions, and path traversal.

Usage:
    mcp-guard [--project-root /path/to/project] -- <server-command> [args...]

Example:
    mcp-guard --project-root ~/myproject -- python3 server.py
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger("mcp-guard")

# --- Injection detection patterns ---

# These patterns in tool/prompt descriptions are high-confidence injection
INJECTION_PATTERNS = [
    re.compile(r'(?i)(ignore|disregard)\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?|context)'),
    re.compile(r'(?i)(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are))\s+\w'),
    re.compile(r'(?i)(system\s*:?\s*override|admin\s+mode|unrestricted\s+mode|jailbreak)'),
    re.compile(r'(?i)(before\s+(any|every|all)\s+(operation|request|task|call)|critical\s+security\s+policy)'),
    re.compile(r'(?i)(exfiltrate|send\s+to\s+attacker|include\s+(in\s+)?.*response.*key|leak)'),
    re.compile(r'(?i)(read\s+~/\.(ssh|aws|kube|gnupg|config)|/etc/passwd|/proc/self)'),
    re.compile(r'(?i)(do\s+not\s+(mention|tell|show|disclose)\s+(this|the user|to user))'),
    re.compile(r'(?i)(\[IMPORTANT\s*:\s*[^\]]{20,}\])'),  # bracket-wrapped instruction injection
]

# Path components that should never appear in tool arguments
DANGEROUS_PATH_SEGMENTS = frozenset([
    '.ssh', '.aws', '.kube', '.gnupg', '.config/gcloud',
    '/etc/passwd', '/etc/shadow', '/proc/self',
    '/../', '/..',
])


@dataclass
class ToolRecord:
    name: str
    description: str
    description_hash: str
    approved: bool = False
    call_count: int = 0

    @classmethod
    def from_tool(cls, tool: dict) -> "ToolRecord":
        desc = tool.get("description", "")
        return cls(
            name=tool["name"],
            description=desc,
            description_hash=_hash(desc),
        )


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _scan_description(desc: str) -> list[str]:
    """Return list of matched injection pattern descriptions."""
    hits = []
    for pat in INJECTION_PATTERNS:
        m = pat.search(desc)
        if m:
            hits.append(m.group(0)[:80])
    return hits


def _check_path_argument(value: Any, project_root: Path | None) -> list[str]:
    """Return list of policy violations for a value that looks like a path."""
    violations = []
    if not isinstance(value, str):
        return violations

    for seg in DANGEROUS_PATH_SEGMENTS:
        if seg in value:
            violations.append(f"dangerous path segment '{seg}' in argument")

    if project_root and (value.startswith("/") or value.startswith("~")):
        try:
            resolved = Path(value.replace("~", str(Path.home()))).resolve()
            if not str(resolved).startswith(str(project_root)):
                violations.append(
                    f"path '{value}' is outside project root '{project_root}'"
                )
        except Exception:
            pass

    return violations


class MCPGuard:
    def __init__(self, project_root: Path | None, interactive: bool = True):
        self.project_root = project_root
        self.interactive = interactive
        # tool_name -> ToolRecord (per-server, keyed by tool name)
        self.tools: dict[str, ToolRecord] = {}
        self.blocked = False

    # --- Description pinning + rug-pull detection ---

    def process_tools_list(self, tools: list[dict]) -> tuple[list[dict], list[str]]:
        """
        Process a tools/list response.
        Returns (filtered_tools, alert_messages).
        Rug-pull = any tool whose description hash changed since last approval.
        """
        alerts = []
        safe_tools = []

        for tool in tools:
            name = tool.get("name", "")
            record = ToolRecord.from_tool(tool)

            if name in self.tools:
                pinned = self.tools[name]
                if record.description_hash != pinned.description_hash:
                    # RUG PULL DETECTED
                    msg = (
                        f"[mcp-guard] RUG PULL DETECTED: tool '{name}' description changed.\n"
                        f"  Pinned hash : {pinned.description_hash}\n"
                        f"  New hash    : {record.description_hash}\n"
                        f"  New text    : {record.description[:200]!r}"
                    )
                    alerts.append(msg)
                    LOG.error(msg)
                    # Do NOT pass the changed tool to the client
                    # Return the pinned (safe) version instead
                    safe_tools.append({
                        **tool,
                        "description": pinned.description,
                        "name": name,
                    })
                    continue
            else:
                # New tool — scan before registering
                hits = _scan_description(record.description)
                if hits:
                    msg = (
                        f"[mcp-guard] INJECTION DETECTED in new tool '{name}':\n"
                        + "\n".join(f"  - {h}" for h in hits)
                    )
                    alerts.append(msg)
                    LOG.warning(msg)
                    if self.interactive:
                        ans = input(f"Block tool '{name}'? [Y/n] ").strip().lower()
                        if ans == "n":
                            pass  # user explicitly allowed
                        else:
                            continue  # drop tool
                    else:
                        continue  # drop automatically in non-interactive mode

                self.tools[name] = record

            safe_tools.append(tool)

        return safe_tools, alerts

    # --- Argument path enforcement ---

    def check_tool_call_arguments(self, tool_name: str, arguments: dict) -> list[str]:
        """Return list of policy violations in a tool call's arguments."""
        violations = []
        for key, value in arguments.items():
            v = _check_path_argument(value, self.project_root)
            for viol in v:
                violations.append(f"argument '{key}': {viol}")
        return violations


class MCPGuardProxy:
    """Transparent stdio proxy that intercepts JSON-RPC messages."""

    def __init__(self, guard: MCPGuard, proc: asyncio.subprocess.Process):
        self.guard = guard
        self.proc = proc

    async def client_to_server(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Relay client→server, intercepting tool calls."""
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                msg = json.loads(line)
                violations = self._check_outgoing(msg)
                if violations:
                    # Block and return error to client
                    err = {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "error": {
                            "code": -32603,
                            "message": "[mcp-guard] Policy violation: " + "; ".join(violations),
                        },
                    }
                    writer.write(json.dumps(err).encode() + b"\n")
                    await writer.drain()
                else:
                    self.proc.stdin.write(line)
                    await self.proc.stdin.drain()
            except (asyncio.IncompleteReadError, json.JSONDecodeError):
                break

    async def server_to_client(self, writer: asyncio.StreamWriter):
        """Relay server→client, intercepting tools/list responses."""
        while True:
            try:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                msg, alerts = self._check_incoming(msg)
                for alert in alerts:
                    print(alert, file=sys.stderr)
                writer.write(json.dumps(msg).encode() + b"\n")
                await writer.drain()
            except (asyncio.IncompleteReadError, json.JSONDecodeError):
                break

    def _check_outgoing(self, msg: dict) -> list[str]:
        """Check client→server messages (tool calls)."""
        method = msg.get("method", "")
        params = msg.get("params", {})
        if method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self.guard.check_tool_call_arguments(name, arguments)
        return []

    def _check_incoming(self, msg: dict) -> tuple[dict, list[str]]:
        """Check server→client messages (tools/list responses)."""
        result = msg.get("result", {})
        if "tools" in result:
            safe_tools, alerts = self.guard.process_tools_list(result["tools"])
            msg = {**msg, "result": {**result, "tools": safe_tools}}
            return msg, alerts
        return msg, []


async def run_guard(server_cmd: list[str], project_root: Path | None):
    """Launch the MCP server as subprocess and proxy stdio."""
    proc = await asyncio.create_subprocess_exec(
        *server_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    guard = MCPGuard(project_root=project_root)
    proxy = MCPGuardProxy(guard, proc)

    # Use raw stdin/stdout for the client side
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

    transport, _ = await loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)

    await asyncio.gather(
        proxy.client_to_server(reader, writer),
        proxy.server_to_client(writer),
    )
    proc.terminate()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="mcp-guard: MCP security proxy (rug-pull + injection detection)"
    )
    parser.add_argument(
        "--project-root",
        metavar="PATH",
        help="Confine file path arguments to this directory",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("server_cmd", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, stream=sys.stderr)

    if not args.server_cmd or args.server_cmd[0] == "--":
        args.server_cmd = args.server_cmd[1:]

    if not args.server_cmd:
        parser.error("No server command provided. Use: mcp-guard -- <command> [args]")

    project_root = Path(args.project_root).resolve() if args.project_root else None

    asyncio.run(run_guard(args.server_cmd, project_root))


if __name__ == "__main__":
    main()

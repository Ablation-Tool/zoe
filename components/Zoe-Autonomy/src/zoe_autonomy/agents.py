from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from .actuation import ActuationPolicy, canonical, digest, timestamp, write_json


DEFAULT_ROOT = Path.home() / ".zoe" / "agents"
MAX_OUTPUT = 64 * 1024
MAX_HTTP_RESPONSE = 1024 * 1024


class AgentGateway:
    def __init__(self, root=None, actuation=None):
        self.root = Path(root or os.environ.get("ZOE_AGENTS_ROOT", DEFAULT_ROOT)).expanduser().resolve()
        self.config_path = self.root / "connections.json"
        self.audit_path = self.root / "agent-audit.jsonl"
        self.actuation = actuation or ActuationPolicy()

    def _document(self):
        if not self.config_path.is_file():
            return {"schema_version": 1, "instrument": "zoe-connected-agent-gateway", "connections": []}
        if self.config_path.stat().st_size > 1024 * 1024:
            raise ValueError("agent connection configuration exceeds 1 MiB")
        document = json.loads(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("connections"), list):
            raise ValueError("unsupported agent connection configuration")
        return document

    def _save(self, document, replace=True):
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        write_json(self.config_path, document, replace=replace)

    def _connection(self, identifier):
        for connection in self._document()["connections"]:
            if connection.get("id") == identifier:
                return connection
        raise ValueError(f"unknown connected agent: {identifier}")

    def discover(self):
        registered = {item["id"] for item in self._document()["connections"]}
        templates = {
            "kimi": ("kimi", ["-p", "{prompt}"]),
            "claude": ("claude", ["-p", "{prompt}"]),
            "codex": ("codex", ["exec", "{prompt}"]),
        }
        discovered = []
        for identifier, (executable, arguments) in templates.items():
            path = shutil.which(executable)
            discovered.append({
                "id": identifier,
                "kind": "cli",
                "available": path is not None,
                "path": path,
                "argv": [path, *arguments] if path else None,
                "registered": identifier in registered,
                "authenticated_interface": "Existing local CLI session; no credential value is read by discovery.",
            })
        return discovered

    def register_discovered(self, owner_approved=False):
        if owner_approved is not True:
            raise ValueError("explicit owner approval is required to register connected agents")
        document = self._document()
        existing = {item["id"] for item in document["connections"]}
        added = []
        for item in self.discover():
            if not item["available"] or item["id"] in existing:
                continue
            document["connections"].append({
                "id": item["id"],
                "kind": "cli",
                "argv": item["argv"],
                "enabled": True,
                "owner": True,
            })
            added.append(item["id"])
        if added:
            self._save(document)
            self._audit("agents_registered", {"agents": added})
        return {"added": added, "connections": self.list()}

    def add_cli(self, identifier, argv, owner_approved=False, replace=False):
        if owner_approved is not True:
            raise ValueError("explicit owner approval is required to add a connected agent")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", identifier or ""):
            raise ValueError("agent id must be a lowercase identifier")
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
            raise ValueError("agent argv must be a nonempty string array")
        if not any("{prompt}" in item for item in argv):
            raise ValueError("agent argv must contain a {prompt} placeholder")
        document = self._document()
        if any(item["id"] == identifier for item in document["connections"]):
            if not replace:
                raise FileExistsError(f"connected agent already exists: {identifier}")
            document["connections"] = [item for item in document["connections"] if item["id"] != identifier]
        document["connections"].append({"id": identifier, "kind": "cli", "argv": argv, "enabled": True, "owner": True})
        self._save(document)
        self._audit("agent_added", {"id": identifier, "kind": "cli"})
        return self.list()

    def add_http(self, identifier, url, model, api_key_env, owner_approved=False, replace=False):
        if owner_approved is not True:
            raise ValueError("explicit owner approval is required to add a connected agent")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", identifier or ""):
            raise ValueError("agent id must be a lowercase identifier")
        parsed = urlparse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("agent endpoint must be HTTP(S) without embedded credentials")
        if not isinstance(model, str) or not model.strip() or len(model) > 256:
            raise ValueError("agent model must contain 1-256 characters")
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", api_key_env or ""):
            raise ValueError("api_key_env must name an environment variable, not contain a credential")
        document = self._document()
        if any(item["id"] == identifier for item in document["connections"]):
            if not replace:
                raise FileExistsError(f"connected agent already exists: {identifier}")
            document["connections"] = [item for item in document["connections"] if item["id"] != identifier]
        document["connections"].append({
            "id": identifier,
            "kind": "openai_compatible",
            "url": url,
            "model": model,
            "api_key_env": api_key_env,
            "enabled": True,
            "owner": True,
        })
        self._save(document)
        self._audit("agent_added", {"id": identifier, "kind": "openai_compatible"})
        return self.list()

    def list(self):
        result = []
        for item in self._document()["connections"]:
            public = {key: value for key, value in item.items() if key != "argv"}
            if item["kind"] == "cli":
                public["executable_available"] = bool(item["argv"] and shutil.which(item["argv"][0]))
            else:
                public["credential_configured"] = bool(os.environ.get(item["api_key_env"]))
            result.append(public)
        return result

    def _audit(self, event, payload):
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        previous_hash = None
        sequence = 0
        if self.audit_path.is_file():
            with self.audit_path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        sequence += 1
                        previous_hash = json.loads(line)["hash"]
        record = {
            "sequence": sequence + 1,
            "event": event,
            "created_utc": timestamp(),
            "hostname": socket.gethostname(),
            "previous_hash": previous_hash,
            "payload": payload,
        }
        record["hash"] = digest(record)
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(canonical(record) + "\n")
        os.chmod(self.audit_path, 0o600)
        return record["hash"]

    def invoke(self, identifier, prompt, timeout=60):
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 100000:
            raise ValueError("agent prompt must contain 1-100000 characters")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300:
            raise ValueError("agent timeout must be from 1 to 300 seconds")
        connection = self._connection(identifier)
        if not connection.get("enabled") or not connection.get("owner"):
            raise PermissionError("connected agent is not enabled by its owner")
        kind = connection["kind"]
        scope = "host" if kind == "cli" else "network"
        if not self.actuation.enabled(scope):
            raise PermissionError(f"the owner actuation grant or emergency stop does not enable {scope}")
        try:
            if kind == "cli":
                result = self._invoke_cli(connection, prompt, timeout)
            elif kind == "openai_compatible":
                result = self._invoke_http(connection, prompt, timeout)
            else:
                raise ValueError("unsupported connected-agent kind")
            result["audit_hash"] = self._audit("agent_invoked", {
                "id": identifier,
                "kind": kind,
                "succeeded": result["succeeded"],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "response_sha256": hashlib.sha256(result["content"].encode()).hexdigest(),
                "response_characters": len(result["content"]),
            })
            return result
        except Exception as error:
            self._audit("agent_invocation_failed", {
                "id": identifier,
                "kind": kind,
                "error_type": type(error).__name__,
                "error": str(error)[:500],
            })
            raise

    def _invoke_cli(self, connection, prompt, timeout):
        argv = [item.replace("{prompt}", prompt) for item in connection["argv"]]
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("connected CLI agent timed out")
        return {
            "id": connection["id"],
            "kind": "cli",
            "succeeded": process.returncode == 0,
            "returncode": process.returncode,
            "content": stdout[:MAX_OUTPUT].decode("utf-8", errors="replace"),
            "stderr": stderr[:MAX_OUTPUT].decode("utf-8", errors="replace"),
            "shell_used": False,
        }

    def _invoke_http(self, connection, prompt, timeout):
        credential = os.environ.get(connection["api_key_env"])
        if not credential:
            raise ValueError(f"credential environment variable is not set: {connection['api_key_env']}")
        body = json.dumps({
            "model": connection["model"],
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        request = urlrequest.Request(
            connection["url"],
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
                "User-Agent": "ZoeOneAgentGateway/1.0",
            },
        )
        try:
            response = urlrequest.urlopen(request, timeout=timeout)
        except urlerror.HTTPError as error:
            response = error
        with response:
            data = response.read(MAX_HTTP_RESPONSE + 1)
            if len(data) > MAX_HTTP_RESPONSE:
                raise RuntimeError("connected agent response exceeds 1 MiB")
            document = json.loads(data.decode("utf-8"))
            content = ""
            if isinstance(document.get("choices"), list) and document["choices"]:
                content = document["choices"][0].get("message", {}).get("content", "")
            content = content or document.get("output_text", "")
            return {
                "id": connection["id"],
                "kind": "openai_compatible",
                "succeeded": 200 <= response.status < 300,
                "status": response.status,
                "model": document.get("model", connection["model"]),
                "content": content,
            }


def agents_main(argv=None):
    parser = argparse.ArgumentParser(prog="zoe-autonomy agents", description="Owner-authorized gateway for connected AI agent accounts")
    parser.add_argument("--root", help="agent configuration and audit directory")
    commands = parser.add_subparsers(dest="agents_command", required=True)
    discover = commands.add_parser("discover")
    discover.add_argument("--register", action="store_true")
    discover.add_argument("--owner-approved", action="store_true")
    commands.add_parser("list")
    add_cli = commands.add_parser("add-cli")
    add_cli.add_argument("--id", required=True)
    add_cli.add_argument("--argv", required=True)
    add_cli.add_argument("--owner-approved", action="store_true")
    add_cli.add_argument("--replace", action="store_true")
    add_http = commands.add_parser("add-http")
    add_http.add_argument("--id", required=True)
    add_http.add_argument("--url", required=True)
    add_http.add_argument("--model", required=True)
    add_http.add_argument("--api-key-env", required=True)
    add_http.add_argument("--owner-approved", action="store_true")
    add_http.add_argument("--replace", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("id")
    run.add_argument("--prompt", required=True)
    run.add_argument("--timeout", type=float, default=60)
    run.add_argument("--output")
    arguments = parser.parse_args(argv)
    gateway = AgentGateway(arguments.root)
    if arguments.agents_command == "discover":
        result = gateway.register_discovered(arguments.owner_approved) if arguments.register else {"discovered": gateway.discover(), "registered": gateway.list()}
    elif arguments.agents_command == "list":
        result = {"connections": gateway.list()}
    elif arguments.agents_command == "add-cli":
        result = {"connections": gateway.add_cli(arguments.id, json.loads(arguments.argv), arguments.owner_approved, arguments.replace)}
    elif arguments.agents_command == "add-http":
        result = {"connections": gateway.add_http(arguments.id, arguments.url, arguments.model, arguments.api_key_env, arguments.owner_approved, arguments.replace)}
    else:
        result = gateway.invoke(arguments.id, arguments.prompt, arguments.timeout)
        if arguments.output:
            write_json(Path(arguments.output).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if arguments.agents_command == "run" and not result["succeeded"]:
        return 1
    return 0

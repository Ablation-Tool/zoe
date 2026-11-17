from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import stat
import subprocess
import sys
import time
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


SCOPES = ("host", "network", "hardware")
MAX_ARGUMENTS = 128
MAX_OUTPUT = 64 * 1024
MAX_NETWORK_BODY = 1024 * 1024
MAX_HARDWARE_BYTES = 64 * 1024
DEFAULT_ROOT = Path.home() / ".zoe" / "actuation"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path, value, *, replace=False, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if replace else "x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.chmod(path, mode)


class ActuationPolicy:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("ZOE_ACTUATION_ROOT", DEFAULT_ROOT)).expanduser().resolve()
        self.grant_path = self.root / "owner-grant.json"
        self.stop_path = self.root / "EMERGENCY-STOP"
        self.audit_path = self.root / "actuation-audit.jsonl"

    def _grant(self):
        if not self.grant_path.is_file():
            return None
        if self.grant_path.stat().st_size > 64 * 1024:
            raise ValueError("actuation grant exceeds 64 KiB")
        value = json.loads(self.grant_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1 or value.get("instrument") != "zoe-owner-actuation-grant":
            raise ValueError("unsupported actuation grant")
        if value.get("hostname") != socket.gethostname():
            raise ValueError("actuation grant belongs to a different computer")
        scopes = value.get("scopes")
        if not isinstance(scopes, dict) or set(scopes) != set(SCOPES) or any(not isinstance(item, bool) for item in scopes.values()):
            raise ValueError("invalid actuation grant scopes")
        return value

    def status(self):
        grant = self._grant()
        stopped = self.stop_path.exists()
        scopes = {
            scope: bool(grant and grant["scopes"][scope] and not stopped)
            for scope in SCOPES
        }
        return {
            "schema_version": 1,
            "instrument": "zoe-owner-actuation-policy",
            "root": str(self.root),
            "hostname": socket.gethostname(),
            "grant_present": grant is not None,
            "granted_scopes": grant["scopes"] if grant else {scope: False for scope in SCOPES},
            "enabled_scopes": scopes,
            "emergency_stop": stopped,
            "principal": grant.get("principal") if grant else None,
            "created_utc": grant.get("created_utc") if grant else None,
            "audit": str(self.audit_path),
            "authority": "Local owner grant under the current OS account; no privilege elevation or cross-machine transfer.",
        }

    def enabled(self, scope):
        if scope not in SCOPES:
            return False
        return self.status()["enabled_scopes"][scope]

    def enable(self, scopes, owner_approved=False, replace=False):
        if owner_approved is not True:
            raise ValueError("explicit owner approval is required to enable actuation")
        if isinstance(scopes, str):
            scopes = (scopes,)
        if not isinstance(scopes, (tuple, list, set)) or not scopes or set(scopes) - (set(SCOPES) | {"all"}):
            raise ValueError("actuation scopes must be host, network, hardware, or all")
        selected = set(SCOPES if "all" in scopes else scopes)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        grant = {
            "schema_version": 1,
            "instrument": "zoe-owner-actuation-grant",
            "principal": f"local-owner:{getpass.getuser()}",
            "hostname": socket.gethostname(),
            "created_utc": timestamp(),
            "scopes": {scope: scope in selected for scope in SCOPES},
            "owner_approved": True,
            "authority": "All granted actuation runs with the current OS account's permissions on this hostname only.",
        }
        write_json(self.grant_path, grant, replace=replace)
        self._audit("grant_enabled", {"scopes": grant["scopes"], "external_action": False})
        return self.status()

    def stop(self, reason="Owner emergency stop"):
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        write_json(self.stop_path, {"created_utc": timestamp(), "reason": str(reason)}, replace=True, mode=0o600)
        self._audit("emergency_stop", {"reason": str(reason), "external_action": False})
        return self.status()

    def resume(self, owner_approved=False):
        if owner_approved is not True:
            raise ValueError("explicit owner approval is required to resume actuation")
        self.stop_path.unlink(missing_ok=True)
        self._audit("emergency_stop_cleared", {"external_action": False})
        return self.status()

    def _audit(self, event, payload):
        self.root.mkdir(parents=True, exist_ok=True)
        previous_hash = None
        sequence = 0
        if self.audit_path.is_file():
            with self.audit_path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        sequence += 1
                        previous = json.loads(line)
                        previous_hash = previous["hash"]
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

    def execute(self, operation, measurement=None):
        if not isinstance(operation, dict) or operation.get("kind") not in SCOPES:
            raise ValueError("actuation operation kind must be host, network, or hardware")
        kind = operation["kind"]
        try:
            if not self.enabled(kind):
                raise PermissionError(f"{kind} actuation is not enabled or the emergency stop is active")
            if kind == "host":
                result = self._host(operation)
            elif kind == "network":
                result = self._network(operation)
            else:
                result = self._hardware(operation)
            record = {
                "kind": kind,
                "executed": True,
                "external_action": True,
                "measurement_sha256": digest(measurement) if measurement is not None else None,
                "result": result,
            }
            record["audit_hash"] = self._audit("actuation_completed", record)
            return record
        except Exception as error:
            self._audit("actuation_denied_or_failed", {
                "kind": kind,
                "external_action": False,
                "error_type": type(error).__name__,
                "error": str(error)[:1000],
            })
            raise

    def _host(self, operation):
        argv = operation.get("argv")
        if not isinstance(argv, list) or not 1 <= len(argv) <= MAX_ARGUMENTS or any(
            not isinstance(item, str) or not item or len(item) > 4096 for item in argv
        ):
            raise ValueError("host argv must contain 1-128 nonempty strings")
        timeout = operation.get("timeout", 30)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError("host timeout must be from 1 to 120 seconds")
        cwd = Path(operation.get("cwd", Path.cwd())).expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError("host working directory does not exist")
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("host actuation timed out and its process group was terminated")
        return {
            "argv": argv,
            "cwd": str(cwd),
            "returncode": process.returncode,
            "succeeded": process.returncode == 0,
            "stdout": stdout[:MAX_OUTPUT].decode("utf-8", errors="replace"),
            "stderr": stderr[:MAX_OUTPUT].decode("utf-8", errors="replace"),
            "stdout_truncated": len(stdout) > MAX_OUTPUT,
            "stderr_truncated": len(stderr) > MAX_OUTPUT,
            "shell_used": False,
        }

    def _network(self, operation):
        url = operation.get("url")
        if not isinstance(url, str) or len(url) > 4096:
            raise ValueError("network URL must contain 1-4096 characters")
        parsed = urlparse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("network actuation requires an HTTP(S) URL without embedded credentials")
        method = operation.get("method", "GET").upper()
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("unsupported network method")
        headers = operation.get("headers", {})
        if not isinstance(headers, dict) or len(headers) > 32 or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()
        ):
            raise ValueError("network headers must be a bounded string mapping")
        body = operation.get("body")
        if body is not None and not isinstance(body, str):
            raise ValueError("network body must be text")
        payload = body.encode("utf-8") if body is not None else None
        if payload is not None and len(payload) > MAX_OUTPUT:
            raise ValueError("network request body exceeds 64 KiB")
        timeout = operation.get("timeout", 30)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError("network timeout must be from 1 to 120 seconds")
        request = urlrequest.Request(url, data=payload, headers=headers, method=method)
        try:
            response = urlrequest.urlopen(request, timeout=timeout)
        except urlerror.HTTPError as error:
            response = error
        with response:
            data = response.read(MAX_NETWORK_BODY + 1)
            if len(data) > MAX_NETWORK_BODY:
                raise RuntimeError("network response exceeds 1 MiB")
            return {
                "url": url,
                "method": method,
                "status": response.status,
                "succeeded": 200 <= response.status < 400,
                "content_type": response.headers.get("Content-Type"),
                "body": data.decode("utf-8", errors="replace"),
                "response_bytes": len(data),
                "tls_verification": "Python default certificate verification",
            }

    def _hardware(self, operation):
        device = operation.get("device")
        if not isinstance(device, str) or not device.startswith("/dev/"):
            raise ValueError("hardware actuation requires an explicit /dev character-device path")
        payload_hex = operation.get("payload_hex")
        if not isinstance(payload_hex, str) or len(payload_hex) > MAX_HARDWARE_BYTES * 2:
            raise ValueError("hardware payload_hex is required and must contain at most 64 KiB")
        try:
            payload = bytes.fromhex(payload_hex)
        except ValueError as error:
            raise ValueError("hardware payload_hex must be valid hexadecimal") from error
        read_bytes = operation.get("read_bytes", 0)
        if isinstance(read_bytes, bool) or not isinstance(read_bytes, int) or not 0 <= read_bytes <= 4096:
            raise ValueError("hardware read_bytes must be from 0 to 4096")
        timeout = operation.get("timeout", 2)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 30:
            raise ValueError("hardware timeout must be from 0.1 to 30 seconds")
        flags = os.O_RDWR if read_bytes else os.O_WRONLY
        flags |= os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW
        descriptor = os.open(device, flags)
        try:
            mode = os.fstat(descriptor).st_mode
            if not stat.S_ISCHR(mode):
                raise ValueError("hardware target is not a character device")
            deadline = time.monotonic() + timeout
            written = 0
            while written < len(payload):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("hardware write timed out")
                select.select([], [descriptor], [], remaining)
                written += os.write(descriptor, payload[written:])
            received = bytearray()
            while len(received) < read_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                ready, _, _ = select.select([descriptor], [], [], remaining)
                if not ready:
                    break
                received.extend(os.read(descriptor, read_bytes - len(received)))
            return {
                "device": device,
                "bytes_written": written,
                "read_hex": bytes(received).hex(),
                "read_bytes": len(received),
                "character_device": True,
            }
        finally:
            os.close(descriptor)


def actuation_main(argv=None):
    parser = argparse.ArgumentParser(prog="zoe-autonomy actuate", description="Owner-granted host, network, and hardware actuation")
    parser.add_argument("--root", help="actuation grant and audit directory; default: ZOE_ACTUATION_ROOT or ~/.zoe/actuation")
    commands = parser.add_subparsers(dest="actuation_command", required=True)
    commands.add_parser("status")
    enable = commands.add_parser("enable")
    enable.add_argument("--all", action="store_true")
    enable.add_argument("--host", action="store_true")
    enable.add_argument("--network", action="store_true")
    enable.add_argument("--hardware", action="store_true")
    enable.add_argument("--owner-approved", action="store_true")
    enable.add_argument("--replace", action="store_true")
    stop = commands.add_parser("stop")
    stop.add_argument("--reason", default="Owner emergency stop")
    resume = commands.add_parser("resume")
    resume.add_argument("--owner-approved", action="store_true")
    host = commands.add_parser("host")
    host.add_argument("--argv", required=True, help="JSON argument array; no shell is used")
    host.add_argument("--cwd")
    host.add_argument("--timeout", type=float, default=30)
    host.add_argument("--output")
    network = commands.add_parser("network")
    network.add_argument("--url", required=True)
    network.add_argument("--method", default="GET")
    network.add_argument("--body")
    network.add_argument("--timeout", type=float, default=30)
    network.add_argument("--output")
    hardware = commands.add_parser("hardware")
    hardware.add_argument("--device", required=True)
    hardware.add_argument("--payload-hex", required=True)
    hardware.add_argument("--read-bytes", type=int, default=0)
    hardware.add_argument("--timeout", type=float, default=2)
    hardware.add_argument("--output")
    arguments = parser.parse_args(argv)
    policy = ActuationPolicy(arguments.root)
    command = arguments.actuation_command
    if command == "status":
        result = policy.status()
    elif command == "enable":
        scopes = ["all"] if arguments.all else [
            scope for scope in SCOPES if getattr(arguments, scope)
        ]
        result = policy.enable(scopes, arguments.owner_approved, arguments.replace)
    elif command == "stop":
        result = policy.stop(arguments.reason)
    elif command == "resume":
        result = policy.resume(arguments.owner_approved)
    else:
        if command == "host":
            operation = {"kind": "host", "argv": json.loads(arguments.argv), "cwd": arguments.cwd or str(Path.cwd()), "timeout": arguments.timeout}
        elif command == "network":
            operation = {"kind": "network", "url": arguments.url, "method": arguments.method, "body": arguments.body, "timeout": arguments.timeout}
        else:
            operation = {"kind": "hardware", "device": arguments.device, "payload_hex": arguments.payload_hex, "read_bytes": arguments.read_bytes, "timeout": arguments.timeout}
        result = policy.execute(operation)
        if arguments.output:
            write_json(Path(arguments.output).expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if command in SCOPES and not result["result"].get("succeeded", True):
        return 1
    return 0

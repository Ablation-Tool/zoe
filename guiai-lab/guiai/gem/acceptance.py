from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from .field import _canonical
from .patchbay import _bounded_path, _sha


PLAN_FIELDS = {"schema_version", "instrument", "target", "firmware", "steps"}
STEP_FIELDS = {"name", "argv", "timeout_seconds", "expected_exit", "hardware_write", "cwd"}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def load_plan(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("acceptance plan exceeds 1 MiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != PLAN_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-patchbay-acceptance":
        raise ValueError("unsupported Patchbay acceptance plan")
    if not isinstance(data["target"], str) or not 1 <= len(data["target"]) <= 128:
        raise ValueError("acceptance target must contain 1-128 characters")
    if not isinstance(data["firmware"], str) or not 1 <= len(data["firmware"]) <= 4096:
        raise ValueError("acceptance firmware path must contain 1-4096 characters")
    firmware = Path(data["firmware"])
    if not firmware.is_absolute():
        firmware = path.parent / firmware
    _bounded_path(firmware, 512 * 1024 * 1024)
    if not isinstance(data["steps"], list) or not 1 <= len(data["steps"]) <= 16:
        raise ValueError("acceptance plan requires 1-16 steps")
    steps = []
    for step in data["steps"]:
        if not isinstance(step, dict) or set(step) != STEP_FIELDS:
            raise ValueError("invalid acceptance step fields")
        if not isinstance(step["name"], str) or not 1 <= len(step["name"]) <= 128:
            raise ValueError("acceptance step name must contain 1-128 characters")
        argv = step["argv"]
        if not isinstance(argv, list) or not 1 <= len(argv) <= 32 or any(not isinstance(value, str) or not 1 <= len(value) <= 1024 or "\0" in value for value in argv):
            raise ValueError("acceptance argv must contain 1-32 bounded strings")
        if isinstance(step["timeout_seconds"], bool) or not isinstance(step["timeout_seconds"], (int, float)) or not math.isfinite(step["timeout_seconds"]) or not 0.1 <= step["timeout_seconds"] <= 120:
            raise ValueError("acceptance timeout must be between 0.1 and 120 seconds")
        if isinstance(step["expected_exit"], bool) or not isinstance(step["expected_exit"], int) or not 0 <= step["expected_exit"] <= 255:
            raise ValueError("acceptance expected exit must be between 0 and 255")
        if not isinstance(step["hardware_write"], bool):
            raise ValueError("acceptance hardware_write must be boolean")
        if not isinstance(step["cwd"], str) or not 1 <= len(step["cwd"]) <= 4096:
            raise ValueError("acceptance cwd must contain 1-4096 characters")
        cwd = Path(step["cwd"])
        if not cwd.is_absolute():
            cwd = path.parent / cwd
        if not cwd.is_dir():
            raise ValueError(f"acceptance working directory does not exist: {cwd}")
        steps.append({**step, "cwd": str(cwd)})
    return {"path": str(path), "target": data["target"], "firmware": str(firmware), "steps": steps, "hardware_write_requested": any(step["hardware_write"] for step in steps)}


def _terminate_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _execute_step(step, firmware, target):
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "ZOE_PATCHBAY_FIRMWARE": firmware, "ZOE_PATCHBAY_TARGET": target}
    started = time.monotonic()
    try:
        process = subprocess.Popen(step["argv"], cwd=step["cwd"], env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        return {"name": step["name"], "argv": step["argv"], "cwd": step["cwd"], "returncode": None, "passed": False, "error": str(error), "stdout": "", "stderr": "", "output_truncated": False, "duration_seconds": time.monotonic() - started, "hardware_write": step["hardware_write"]}
    selector = selectors.DefaultSelector()
    streams = {"stdout": process.stdout, "stderr": process.stderr}
    captured = {name: bytearray() for name in streams}
    truncated = {name: False for name in streams}
    for name, stream in streams.items():
        selector.register(stream, selectors.EVENT_READ, name)
    deadline = started + step["timeout_seconds"]
    kill_deadline = None
    timed_out = False
    while selector.get_map():
        now = time.monotonic()
        if not timed_out and now >= deadline:
            timed_out = True
            _terminate_group(process)
            kill_deadline = now + 1
        if kill_deadline is not None and now >= kill_deadline:
            _kill_group(process)
            kill_deadline = None
        remaining = max(0, min(deadline if not timed_out else deadline + 2, now + 0.1) - now)
        for key, _ in selector.select(remaining):
            chunk = os.read(key.fileobj.fileno(), 65536)
            name = key.data
            if not chunk:
                selector.unregister(key.fileobj)
                key.fileobj.close()
                continue
            space = 65536 - len(captured[name])
            if space:
                captured[name].extend(chunk[:space])
            if len(chunk) > space:
                truncated[name] = True
        if timed_out and time.monotonic() > deadline + 2:
            for key in list(selector.get_map().values()):
                selector.unregister(key.fileobj)
                key.fileobj.close()
            _kill_group(process)
            break
    returncode = process.wait()
    selector.close()
    return {
        "name": step["name"],
        "argv": step["argv"],
        "cwd": step["cwd"],
        "returncode": returncode,
        "passed": not timed_out and returncode == step["expected_exit"],
        "expected_exit": step["expected_exit"],
        "timed_out": timed_out,
        "stdout": captured["stdout"].decode("utf-8", errors="replace"),
        "stderr": captured["stderr"].decode("utf-8", errors="replace"),
        "output_truncated": truncated["stdout"] or truncated["stderr"],
        "duration_seconds": time.monotonic() - started,
        "hardware_write": step["hardware_write"],
    }


def run_acceptance(path, execute=False, allow_hardware_write=False):
    plan = load_plan(path)
    if not execute and allow_hardware_write:
        raise ValueError("--allow-hardware-write requires --execute")
    if execute and plan["hardware_write_requested"] and not allow_hardware_write:
        raise ValueError("this plan contains declared hardware writes; use --allow-hardware-write to authorize them")
    before = _sha(plan["firmware"])
    results = []
    started = datetime.now(timezone.utc).isoformat()
    if execute:
        for step in plan["steps"]:
            result = _execute_step(step, plan["firmware"], plan["target"])
            results.append(result)
            if not result["passed"]:
                break
    finished = datetime.now(timezone.utc).isoformat()
    after = _sha(plan["firmware"])
    accepted = len(results) == len(plan["steps"]) and all(result["passed"] for result in results) and before == after if execute else None
    return {
        "schema_version": 1,
        "instrument": "zoe-patchbay-acceptance-result",
        "plan": plan["path"],
        "plan_sha256": _sha(plan["path"]),
        "target": plan["target"],
        "firmware": plan["firmware"],
        "firmware_sha256_before": before,
        "firmware_sha256_after": after,
        "started_at": started,
        "finished_at": finished,
        "executed": execute,
        "hardware_write_authorized": allow_hardware_write,
        "hardware_write_requested": plan["hardware_write_requested"],
        "hardware_accessed": None,
        "hardware_behavior_proven": False,
        "accepted": accepted,
        "steps": results,
        "evidence_scope": "executed-plan-only" if execute else "validation-only-no-commands",
        "summary": f"Target {plan['target']} · executed={execute} · accepted={accepted}\n{len(results)}/{len(plan['steps'])} command steps recorded · hardware access is not inferred from argv\nFirmware unchanged: {before == after}. Results cover this plan only.",
    }


def save_acceptance(report, path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("acceptance reports must use a .json path")
    document = {key: value for key, value in report.items() if key != "digest"}
    document["digest"] = _digest(document)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(_canonical(document) + "\n")
    return path


def load_acceptance(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("acceptance report exceeds 1 MiB")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1 or document.get("instrument") != "zoe-patchbay-acceptance-result" or not isinstance(document.get("digest"), str):
        raise ValueError("unsupported acceptance report")
    if document["digest"] != _digest({key: value for key, value in document.items() if key != "digest"}):
        raise ValueError("acceptance report digest mismatch")
    return document

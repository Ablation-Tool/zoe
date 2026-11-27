"""TCP QMP/HMP client and deterministic polling helpers (zero blind sleeps)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import time
from typing import Any, Callable


def alloc_free_port(host: str = "127.0.0.1") -> int:
    """Bind an ephemeral loopback TCP socket and return its port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def wait_until(
    predicate: Callable[[], Any],
    timeout_sec: float = 10.0,
    interval: float = 0.05,
    desc: str = "condition",
) -> Any:
    """Poll predicate until truthy or raise TimeoutError after timeout_sec."""
    deadline = time.monotonic() + float(timeout_sec)
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for {desc} after {timeout_sec:.2f}s")
        time.sleep(interval)


def wait_for_tcp_port(host: str, port: int, timeout_sec: float = 15.0) -> bool:
    """Poll until a TCP port accepts loopback connections."""
    def _can_connect() -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            return False

    return bool(wait_until(_can_connect, timeout_sec=timeout_sec, interval=0.05, desc=f"TCP {host}:{port}"))


def _consume_serial_chunk(fd: int, buf: bytearray, marker: str, lines_out: list[str]) -> str:
    """Read raw bytes non-blockingly from fd, split lines, return 'matched'/'eof'/'more'."""
    chunk = os.read(fd, 4096)
    if not chunk:
        return "eof"
    buf.extend(chunk.replace(b"\r", b"\n"))
    while b"\n" in buf:
        raw_line, _, rest = buf.partition(b"\n")
        buf[:] = rest
        line = raw_line.decode("utf-8", errors="replace").strip()
        if line:
            lines_out.append(line)
            if marker in line:
                return "matched"
    return "matched" if marker.encode("utf-8") in buf else "more"


def _flush_serial_tail(buf: bytearray, lines_out: list[str]) -> None:
    """Flush any trailing partial non-newline buffer text into lines_out."""
    if buf:
        tail_line = buf.decode("utf-8", errors="replace").strip()
        buf.clear()
        if tail_line:
            lines_out.append(tail_line)


def wait_for_serial_marker(
    proc: subprocess.Popen[str],
    marker: str,
    lines_out: list[str],
    timeout_sec: float = 45.0,
) -> bool:
    """Stream proc.stdout using selectors + os.read until marker appears or timeout."""
    if proc.stdout is None:
        raise RuntimeError("Process stdout pipe is unavailable")
    fd = proc.stdout.fileno()
    sel = selectors.DefaultSelector()
    sel.register(fd, selectors.EVENT_READ)
    buf = bytearray()
    deadline = time.monotonic() + float(timeout_sec)
    try:
        while time.monotonic() < deadline:
            remaining = max(0.05, min(0.25, deadline - time.monotonic()))
            events = sel.select(timeout=remaining)
            if events:
                status = _consume_serial_chunk(fd, buf, marker, lines_out)
                if status == "matched":
                    _flush_serial_tail(buf, lines_out)
                    return True
                if status == "eof":
                    break
            elif proc.poll() is not None:
                break
    finally:
        _flush_serial_tail(buf, lines_out)
        sel.close()
    tail = " | ".join(lines_out[-8:])
    if proc.poll() is not None:
        raise RuntimeError(f"Process exited ({proc.returncode}) before marker {marker!r}; tail: {tail}")
    raise TimeoutError(f"Timed out after {timeout_sec:.1f}s waiting for {marker!r}; tail: {tail}")


class QmpClient:
    """Minimal pure-stdlib TCP loopback QEMU Machine Protocol (QMP) client."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4444, timeout_sec: float = 10.0) -> None:
        self.host = host
        self.port = int(port)
        self.timeout_sec = float(timeout_sec)
        self._sock: socket.socket | None = None
        self._reader: Any = None
        self.greeting: dict[str, Any] = {}

    def connect(self) -> dict[str, Any]:
        """Connect to TCP QMP port with retry and read greeting banner."""
        def _try_connect() -> socket.socket | None:
            try:
                return socket.create_connection((self.host, self.port), timeout=self.timeout_sec)
            except OSError:
                return None

        self._sock = wait_until(_try_connect, timeout_sec=self.timeout_sec, interval=0.05, desc=f"QMP {self.host}:{self.port}")
        self._reader = self._sock.makefile("r", encoding="utf-8", errors="replace")
        raw = self._reader.readline()
        if not raw:
            self.close()
            raise RuntimeError("QMP closed connection before sending greeting")
        self.greeting = json.loads(raw)
        return self.greeting

    def close(self) -> None:
        """Close QMP reader and underlying TCP socket."""
        if self._reader is not None:
            try:
                self._reader.close()
            except OSError:
                pass
            self._reader = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> QmpClient:
        self.connect()
        self.qmp_capabilities()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()

    def _read_reply(self) -> dict[str, Any]:
        """Read JSON lines skipping async QMP events until return or error."""
        assert self._reader is not None
        while True:
            line = self._reader.readline()
            if not line:
                raise RuntimeError("QMP connection closed waiting for reply")
            msg = json.loads(line)
            if "error" in msg:
                raise RuntimeError(f"QMP error: {msg['error']}")
            if "return" in msg:
                return msg

    def execute(self, command: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a QMP JSON command and return its response payload."""
        if self._sock is None:
            raise RuntimeError("QMP client is not connected")
        payload: dict[str, Any] = {"execute": command}
        if arguments is not None:
            payload["arguments"] = arguments
        self._sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        return self._read_reply()

    def qmp_capabilities(self) -> dict[str, Any]:
        """Negotiate QMP capabilities after connection greeting."""
        return self.execute("qmp_capabilities")

    def screendump(self, ppm_path: str | Path) -> dict[str, Any]:
        """Dump guest VGA framebuffer to a binary P6 PPM file."""
        return self.execute("screendump", {"filename": str(ppm_path)})

    def human_monitor_command(self, cmd_line: str) -> str:
        """Execute an HMP command via QMP human-monitor-command."""
        res = self.execute("human-monitor-command", {"command-line": cmd_line})
        return str(res.get("return", ""))

    def sendkey(self, key: str) -> str:
        """Inject a guest keyboard event via HMP sendkey."""
        return self.human_monitor_command(f"sendkey {key}")

    def mouse_move(self, dx: int, dy: int) -> str:
        """Inject relative pointer motion via HMP mouse_move."""
        return self.human_monitor_command(f"mouse_move {int(dx)} {int(dy)}")

    def mouse_button(self, mask: int) -> str:
        """Inject mouse button state bitmask via HMP mouse_button."""
        return self.human_monitor_command(f"mouse_button {int(mask)}")

    def quit(self) -> dict[str, Any]:
        """Request clean QEMU exit, tolerating immediate peer socket close."""
        try:
            return self.execute("quit")
        except (ConnectionResetError, BrokenPipeError, RuntimeError):
            return {}


def terminate_qemu_proc(proc: subprocess.Popen[Any], timeout_sec: float = 8.0) -> None:
    """Terminate a QEMU subprocess safely with SIGKILL fallback on timeout."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

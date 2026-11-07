from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

from .unified import _python

DEFAULT_CHECKOUT = Path("/media/cowboy/research/GEM/cern-console")
DEFAULT_STATE = Path(__file__).resolve().parents[2] / "evidence" / "cern-console" / "runtime.json"
REQUIRED_FILES = (
    "run.py", "index.html", "helios.py", "atelier.js", "atelier-formats.js",
    "system/dos/atelier.s", "data/catalog.json", "data/helios-reference.json",
)
TARGETS = {"console": "", "helios": "helios", "atelier": "atelier"}


def free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return int(stream.getsockname()[1])


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, value: dict, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")


class WorkbenchProcess:
    def __init__(self, checkout=None, state_file=None, preferred_port: int = 8765):
        self.checkout = Path(checkout or os.environ.get("ZOE_CERN_CONSOLE", DEFAULT_CHECKOUT)).expanduser().resolve()
        self.state_file = Path(state_file) if state_file else DEFAULT_STATE
        self.preferred_port = int(preferred_port)
        self.process = None
        for relative in REQUIRED_FILES:
            if not (self.checkout / relative).is_file():
                raise ValueError(f"CERN console checkout is missing {relative}: {self.checkout / relative}")

    def health_at(self, port: int, timeout: float = 0.6) -> dict | None:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as response:
                value = json.load(response)
            if value.get("schema") != "cern-gem-console/health-v1" or value.get("hardware_access") is not False:
                return None
            return value
        except (URLError, OSError, ValueError):
            return None

    def _owned_state(self) -> dict | None:
        state = read_json(self.state_file)
        if not state or not state.get("owned") or not isinstance(state.get("pid"), int):
            return None
        if state.get("checkout") != str(self.checkout):
            return None
        try:
            os.kill(state["pid"], 0)
        except OSError:
            return None
        if self.health_at(state["port"]) is None:
            return None
        return state

    def start(self) -> dict:
        owned = self._owned_state()
        if owned:
            health = self.health_at(owned["port"])
            return {**owned, "health": health, "attached": False, "readiness_verified": True}
        health = self.health_at(self.preferred_port)
        if health:
            return {
                "component": "cern-console", "owned": False, "attached": True,
                "pid": None, "port": self.preferred_port,
                "url": f"http://127.0.0.1:{self.preferred_port}/",
                "health": health, "readiness_verified": True,
            }
        port = free_port()
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        environment["ZOE_COMPONENT_ID"] = "cern-console"
        environment["ZOE_UNIFIED"] = "1"
        environment["ZOE_ROOT"] = str(Path(__file__).resolve().parents[2])
        log_path = self.state_file.parent / "console.log"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as stream:
            self.process = subprocess.Popen(
                [_python(), "run.py", "--no-browser", "--port", str(port)],
                cwd=self.checkout, env=environment, stdout=stream,
                stderr=subprocess.STDOUT, text=True, start_new_session=True,
            )
        state = {
            "component": "cern-console", "owned": True, "attached": False,
            "pid": self.process.pid, "port": port,
            "url": f"http://127.0.0.1:{port}/", "checkout": str(self.checkout),
            "log": str(log_path),
        }
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            health = self.health_at(port)
            if health:
                write_json(self.state_file, {**state, "health": health, "readiness_verified": True})
                return {**state, "health": health, "readiness_verified": True}
            if self.process.poll() is not None:
                details = log_path.read_text(errors="replace")[-4000:] if log_path.exists() else "no console log"
                raise RuntimeError(f"CERN console exited with {self.process.returncode}: {details}")
            time.sleep(0.1)
        self.stop()
        raise TimeoutError("CERN console did not become healthy within 12 seconds")

    def stop(self) -> dict:
        state = self._owned_state()
        if not state:
            return {"component": "cern-console", "stopped": False, "reason": "no Zoe-owned healthy process"}
        pid = state["pid"]
        try:
            command = Path(f"/proc/{pid}/cmdline").read_bytes()
            working_directory = Path(f"/proc/{pid}/cwd").resolve()
            if b"run.py" not in command or working_directory != self.checkout:
                raise RuntimeError(f"refusing to stop unrecognized process {pid}")
            os.kill(pid, 15)
            if self.process is not None:
                try:
                    self.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=4)
            else:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    try:
                        os.kill(pid, 0)
                        time.sleep(0.05)
                    except OSError:
                        break
        except ProcessLookupError:
            pass
        self.state_file.unlink(missing_ok=True)
        return {"component": "cern-console", "stopped": True, "pid": pid}

    def open(self, target: str = "console") -> dict:
        if target not in TARGETS:
            raise ValueError(f"unknown workbench target {target}; choose console, helios, or atelier")
        state = self.start()
        suffix = f"#{TARGETS[target]}" if TARGETS[target] else ""
        url = f"{state['url']}{suffix}"
        opened = webbrowser.open(url)
        return {**state, "target": target, "url": url, "browser_opened": opened}

    def verify(self, include_live: bool = False) -> dict:
        checks = []
        commands = [
            ("python-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
            ("javascript-syntax", ["node", "--check", "app.js"]),
            ("helios-syntax", ["node", "--check", "helios.js"]),
            ("atelier-syntax", ["node", "--check", "atelier.js"]),
            ("atelier-formats-syntax", ["node", "--check", "atelier-formats.js"]),
            ("atelier-ui-syntax", ["node", "--check", "atelier-ui.js"]),
            ("helios-model", ["node", "tests/test_helios.js"]),
            ("atelier-model", ["node", "tests/test_atelier.js"]),
            ("format-model", ["node", "tests/test_formats.js"]),
        ]
        if include_live:
            environment = os.environ.copy()
            environment["ATELIER_LIVE_TESTS"] = "1"
            commands.append(("isolated-live", [sys.executable, "-m", "unittest", "tests.test_xtest_live", "tests.test_dos_live", "-v"]))
        else:
            environment = os.environ.copy()
        for name, command in commands:
            result = subprocess.run(command, cwd=self.checkout, env=environment, capture_output=True, text=True, timeout=180, check=False)
            checks.append({"name": name, "returncode": result.returncode, "passed": result.returncode == 0, "output": (result.stdout + result.stderr)[-4000:]})
            if result.returncode:
                break
        return {"passed": all(check["passed"] for check in checks), "include_live": include_live, "checks": checks}

    def manifest(self) -> dict:
        health = self.start()["health"]
        return {
            "schema_version": 1,
            "component": "cern-console",
            "title": "Zoe CERN, HELIOS, and Atelier workbench",
            "checkout": str(self.checkout),
            "build_id": health["build_id"],
            "catalog_sha256": health["catalog_sha256"],
            "statistics": health["stats"],
            "capabilities": {
                "cern_catalog": True, "helios_virtual_collider": True,
                "atelier_vector_input": True, "xtest_opt_in": True,
                "summa_pty_firmware": True, "dos_int33_driver": True,
                "gem_coo_eps_import_export": True,
            },
            "process_boundary": "Attach to a healthy server or start a Zoe-owned loopback process. Never stop an attached process.",
            "evidence_boundary": "Original CERN corpus and GEM/Artline references remain read-only. Virtual systems are not CERN operational hardware or full Artline compatibility claims.",
            "system_boundary": "XTEST and serial emission are opt-in. No /dev/uinput access, physical hardware access, or desktop injection during verification.",
        }

    def write_manifest(self, path) -> Path:
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("workbench manifest must use a .json path")
        write_json(path, self.manifest(), overwrite=False)
        return path

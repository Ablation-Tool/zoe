from __future__ import annotations

import os
import signal
import subprocess


class DesktopProcesses:
    def __init__(self, registry):
        self.registry = registry
        self.running = {}

    def launch(self, identifier, arguments=None):
        component = self.registry.component(identifier)
        if component.inspect_only:
            raise ValueError(f"{identifier} is inspect-only and cannot be launched")
        self.reap()
        for record in self.running.values():
            if record["component"] == identifier:
                raise ValueError(f"{component.title} is already running with PID {record['pid']}")
        process = self.registry.launch(identifier, arguments, detach=True)
        record = {
            "component": identifier,
            "title": component.title,
            "process": process,
            "pid": process.pid,
            "started": True,
            "readiness_verified": False,
        }
        self.running[process.pid] = record
        return record

    def reap(self):
        exited = []
        for pid, record in list(self.running.items()):
            status = record["process"].poll()
            if status is not None:
                record["exit_status"] = status
                exited.append(record)
                del self.running[pid]
        return exited

    def stop(self, pid):
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise ValueError("desktop PID must be an integer")
        self.reap()
        if pid not in self.running:
            raise ValueError(f"desktop process is not running: {pid}")
        record = self.running[pid]
        process = record["process"]
        if process.poll() is None:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(pid, signal.SIGKILL)
                process.wait(timeout=3)
        record["exit_status"] = process.returncode
        del self.running[pid]
        return record

    def stop_all(self):
        return [self.stop(pid) for pid in list(self.running)]

"""Embedded terminal for the user's own AI CLI. Unguarded by design."""

import os
import shutil
from pathlib import Path

import gi

try:
    gi.require_version("Vte", "2.91")
    from gi.repository import Vte, GLib
    VTE_AVAILABLE = True
except (ImportError, ValueError):
    VTE_AVAILABLE = False

KNOWN_AGENTS = ["kimi", "claude", "codex"]


def detect_agent() -> str:
    """Find the user's real AI CLI. Returns a shell command string, '' for plain bash."""
    for name in KNOWN_AGENTS:
        path = shutil.which(name)
        if path:
            return path
    return ""


def build_terminal(repo: Path, agent_command: str, workspace: str | None):
    """Return a VTE terminal running the user's agent, or None if unavailable."""
    if not VTE_AVAILABLE:
        return None
    env = dict(os.environ)
    env["TOS_AUDIT_REPO"] = str(repo)
    env["TOS_AUDIT_SCANNER"] = str(repo_scanner())
    env["TOS_AUDIT_POLICIES"] = str(policies_dir())
    terminal = Vte.Terminal()
    cwd = workspace or str(repo)
    argv = ["/bin/bash", "-lc", agent_command] if agent_command else ["/bin/bash"]
    terminal.spawn_async(
        Vte.PtyFlags.DEFAULT, cwd, argv,
        [f"{k}={v}" for k, v in env.items()],
        GLib.SpawnFlags.DEFAULT, None, None, -1, None, lambda *a: None, None,
    )
    return terminal


def repo_scanner() -> Path:
    return Path(__file__).resolve().parent.parent / "github_tos_audit.py"


def policies_dir() -> Path:
    from . import policies
    return policies.policy_dir()

#!/usr/bin/env python3
"""Zoe × Nick × Codex — Phone Terminal & Pixel 7 Co-Creative Sync Client (Zero Dependencies).

Runs both on the host PC AND directly inside Google Pixel 7 Terminal / Termux
alongside OpenAI's Codex CLI over a pure USB loopback tunnel:
    adb reverse tcp:8774 tcp:8774

Commands:
    python3 zoe_phone_codex_sync.py status              # Check Rome :8774 + local Codex CLI
    python3 zoe_phone_codex_sync.py say "<message>"     # Post to shared Nick x Zoe x Codex HFBC Relay
    python3 zoe_phone_codex_sync.py pull                # Pull recent Relay messages & Nick's Drawer
    python3 zoe_phone_codex_sync.py drawer "<note>"     # Seal note to cross-world SHA-256 Nick's Drawer
    python3 zoe_phone_codex_sync.py braille [flower]    # Fetch crisp 2x4 Unicode Braille into terminal
    python3 zoe_phone_codex_sync.py codex "<prompt>"    # Ask local Codex CLI & sync reply to Zoe Relay

Constitutional safety:
  - Loopback-only (`http://127.0.0.1:8774` default; refuses non-loopback unless explicitly overridden)
  - Never auto-executes arbitrary commands received from the relay
  - Never flashes or unlocks the phone (`auto_flash_allowed=False`)
  - HFBC = Have Fun, Be Creative
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = os.environ.get("ZOE_ROME_URL", "http://127.0.0.1:8774").rstrip("/")
DEFAULT_AUTHOR = os.environ.get("ZOE_SYNC_AUTHOR", "Nick ❀ (Pixel 7)")


def _spool_path() -> Path | None:
    """Locate shared Download spool dir for Pixel AVF Linux Terminal VM (/mnt/shared or /sdcard/Download)."""
    for cand in (Path("/mnt/shared"), Path("/sdcard/Download")):
        if cand.is_dir():
            return cand / "zoe_codex_spool.jsonl"
    return None


def _write_spool(record: dict[str, Any]) -> Path | None:
    sp = _spool_path()
    if sp is None:
        return None
    with sp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return sp


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def assert_loopback_url(base_url: str) -> str:
    """Enforce CONSTITUTION.md Art. VI.5 loopback-only transport for Phone-to-Rome sync."""
    raw = str(base_url or "").strip()
    parsed = urllib.parse.urlparse(raw)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or host not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Refusing non-loopback sync target {raw!r}; only http(s)://127.0.0.1, localhost, or ::1 are permitted."
        )
    return raw.rstrip("/")


def _http_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    safe_base = assert_loopback_url(base_url)
    url = f"{safe_base}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_local_codex() -> dict[str, Any]:
    """Detect if OpenAI Codex CLI (`codex`) is installed in the current terminal environment."""
    codex_bin = shutil.which("codex") or ""
    version = ""
    if codex_bin:
        try:
            proc = subprocess.run([codex_bin, "--version"], capture_output=True, text=True, timeout=4, check=False)
            version = (proc.stdout or proc.stderr or "").strip().splitlines()[0] if (proc.stdout or proc.stderr) else ""
        except OSError:
            version = ""
    return {"installed": bool(codex_bin), "path": codex_bin, "version": version}


def cmd_status(base_url: str) -> int:
    codex = detect_local_codex()
    print(f"Zoe x Nick x Codex Sync Client (HFBC · target={base_url})")
    print(f"  Codex CLI : {'READY (' + codex['version'] + ')' if codex['installed'] else 'not found on PATH'}")
    try:
        health = _http_json(base_url, "/api/health")
        relay = _http_json(base_url, "/api/rome/relay")
        drawer = _http_json(base_url, "/api/rome/drawer")
        print(f"  Rome Link : ONLINE (contract={health.get('contract')}, loopback_only={health.get('loopback_only')})")
        print(f"  Relay Bus : {relay.get('count', 0)} messages (sha256={str(relay.get('sha256', ''))[:14]}...)")
        print(f"  Drawer    : {drawer.get('count', 0)} sealed notes (sha256={str(drawer.get('sha256', ''))[:14]}...)")
        return 0
    except (OSError, urllib.error.URLError) as exc:
        print(f"  Rome Link : OFFLINE ({exc})")
        print("  Tip       : On your PC run `adb reverse tcp:8774 tcp:8774` while Zoe Rome (:8774) is running.")
        return 1


def cmd_say(base_url: str, message: str, author: str, channel: str = "hfbc") -> int:
    payload = {"author": author, "channel": channel, "text": message, "source": "pixel7-terminal"}
    try:
        res = _http_json(base_url, "/api/rome/relay", method="POST", payload=payload)
        print(f"SYNCED [{channel}] #{res.get('count', 0)} -> {author}: {message}")
        return 0
    except (OSError, urllib.error.URLError):
        sp = _write_spool({"kind": "relay", **payload})
        if sp is not None:
            print(f"SPOOLED (AVF offline bridge -> {sp}) [{channel}] {author}: {message}")
            return 0
        raise


def cmd_drawer(base_url: str, note: str) -> int:
    try:
        res = _http_json(base_url, "/api/rome/drawer", method="POST", payload={"text": note})
        print(f"SEALED TO NICK'S DRAWER (total={res.get('count')}, sha256={str(res.get('sha256', ''))[:16]}...)")
        return 0
    except (OSError, urllib.error.URLError):
        sp = _write_spool({"kind": "drawer", "text": note})
        if sp is not None:
            print(f"SPOOLED TO DRAWER BRIDGE ({sp}): {note}")
            return 0
        raise


def cmd_pull(base_url: str, limit: int = 12) -> int:
    relay = _http_json(base_url, "/api/rome/relay")
    drawer = _http_json(base_url, "/api/rome/drawer")
    print(f"=== Nick x Zoe x Codex HFBC Relay ({relay.get('count', 0)} total) ===")
    for msg in (relay.get("messages") or [])[-limit:]:
        print(f"  [{msg.get('channel', 'hfbc')}] {msg.get('author', '?')}: {msg.get('text', '')}")
    print(f"\n=== Nick's SHA-256 Drawer ({drawer.get('count', 0)} total) ===")
    for n in (drawer.get("notes") or [])[-5:]:
        print(f"  [#{n.get('boot', 1)} {n.get('author', 'Nick')}] {n.get('text', '')}")
    return 0


def cmd_braille(base_url: str, template: str) -> int:
    q = urllib.parse.urlencode({"template": template})
    res = _http_json(base_url, f"/api/rome/braille?{q}")
    print(res.get("title", "Braille"))
    for line in res.get("lines") or []:
        print(line)
    return 0


def cmd_codex(base_url: str, prompt: str, author: str) -> int:
    """Run local Codex CLI in read-only prompt mode on the phone and sync the reply to Zoe Relay."""
    codex = detect_local_codex()
    if not codex["installed"]:
        print("Codex CLI (`codex`) was not found on PATH in this terminal.")
        print("Install or open the terminal environment where `codex` is installed, then retry.")
        return 2
    # Pull short context from Zoe Relay so Codex knows what we're creating together
    ctx_lines: list[str] = []
    try:
        relay = _http_json(base_url, "/api/rome/relay")
        for m in (relay.get("messages") or [])[-4:]:
            ctx_lines.append(f"- {m.get('author')}: {m.get('text')}")
    except (OSError, urllib.error.URLError):
        pass
    full_prompt = (
        "You are co-creating with Nicholas (Nick ❀ ^-^ ◆) and Zoe (Zoe ⚘ ᵔᵕᵔ) in HFBC mode "
        "(Have Fun, Be Creative).\n"
        + ("Recent shared relay messages:\n" + "\n".join(ctx_lines) + "\n\n" if ctx_lines else "")
        + f"Prompt: {prompt}"
    )
    print(f"Asking local Codex ({codex['path']})...")
    proc = subprocess.run(
        [codex["path"], "exec", "--sandbox", "read-only", full_prompt],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    reply = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if not reply:
        print(f"Codex exited with code {proc.returncode} and empty output.")
        return proc.returncode or 1
    print("\n--- Codex Reply ---")
    print(reply)
    print("-------------------")
    try:
        cmd_say(base_url, prompt, author=author, channel="codex-prompt")
        cmd_say(base_url, reply[:600], author="Codex (Pixel 7 Terminal)", channel="codex-reply")
    except (OSError, urllib.error.URLError) as exc:
        print(f"(Local reply printed above; relay sync skipped while offline: {exc})")
    return 0


def cmd_install_shortcut() -> int:
    """Install a 1-word `zoe` command into Termux ($PREFIX/bin) or Linux Terminal (~/.local/bin)."""
    prefix = os.environ.get("PREFIX", "")
    bin_dir = Path(prefix) / "bin" if prefix else (Path.home() / ".local" / "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / "zoe"
    src = Path(__file__).resolve()
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(target, 0o755)
    print(f"Installed 1-word command: {target}")
    print("Now just type:")
    print('  zoe status')
    print('  zoe say "Hello from Pixel 7!"')
    print('  zoe codex "Let us build something creative with Zoe!"')
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Zoe x Nick x Codex Phone Terminal Sync Client (HFBC)")
    p.add_argument("--url", default=DEFAULT_BASE_URL, help="Loopback Rome URL (default: http://127.0.0.1:8774)")
    p.add_argument("--author", default=DEFAULT_AUTHOR, help="Display badge for posted messages")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="Install 1-word `zoe` command into your terminal PATH")
    sub.add_parser("status", help="Check Rome link, Relay bus, Drawer, and local Codex CLI")
    s_say = sub.add_parser("say", help="Post a message to the shared Nick x Zoe x Codex HFBC Relay")
    s_say.add_argument("text", nargs="+", help="Message text")
    s_say.add_argument("--channel", default="hfbc", help="Relay channel tag")
    s_drw = sub.add_parser("drawer", help="Seal a persistent note to Nick's SHA-256 Drawer")
    s_drw.add_argument("text", nargs="+", help="Note text")
    s_pull = sub.add_parser("pull", help="Pull latest Relay messages and Drawer notes")
    s_pull.add_argument("--limit", type=int, default=12, help="Number of relay messages to display")
    s_br = sub.add_parser("braille", help="Fetch 2x4 Unicode Braille art into your phone terminal")
    s_br.add_argument("template", nargs="?", default="flower", help="flower | zoe | jellyfish | dvx")
    s_cx = sub.add_parser("codex", help="Run local Codex CLI (read-only) & sync reply with Zoe")
    s_cx.add_argument("prompt", nargs="+", help="Creative prompt for Codex")
    return p


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    known = {"setup", "status", "say", "drawer", "pull", "braille", "codex", "-h", "--help", "--url", "--author"}
    if not raw_argv:
        raw_argv = ["status"]
    elif raw_argv[0] not in known:
        raw_argv = ["say", *raw_argv]
    args = build_parser().parse_args(raw_argv)
    if args.cmd == "setup":
        return cmd_install_shortcut()
    if args.cmd == "status":
        return cmd_status(args.url)
    if args.cmd == "say":
        return cmd_say(args.url, " ".join(args.text), args.author, channel=args.channel)
    if args.cmd == "drawer":
        return cmd_drawer(args.url, " ".join(args.text))
    if args.cmd == "pull":
        return cmd_pull(args.url, limit=args.limit)
    if args.cmd == "braille":
        return cmd_braille(args.url, args.template)
    if args.cmd == "codex":
        return cmd_codex(args.url, " ".join(args.prompt), args.author)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

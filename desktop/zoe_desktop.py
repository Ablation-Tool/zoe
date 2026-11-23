#!/usr/bin/env python3
"""Zoe Desktop App (Linux, Windows, and Apple macOS).

Launches Zoe (Research Partner) with the Dorothy 3D Brain Observatory as the
centerpiece in a standalone native desktop window:
  - Linux: native GTK 3 + WebKit2GTK WebGL2 window (auto-falls back to Chromium/Chrome --app or xdg-open)
  - macOS: standalone Chrome/Edge/Brave --app window or Safari via open
  - Windows: standalone Microsoft Edge/Chrome --app window or default browser

Serves all bundled observatory assets strictly on 127.0.0.1 (ephemeral port)
with full HTTP 206 Partial Content byte-range support for smooth MP4 video
scrubbing and zero external network traffic.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import mimetypes
import os
import platform
import shutil
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

MIME_OVERRIDES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def resolve_roots() -> tuple[Path, Path]:
    """Locate (desktop_dir, observatory_dir) in both source checkout and packaged bundles."""
    here = Path(__file__).resolve().parent
    candidates = [
        (here, here / "dorothy_brain_observatory"),
        (here, here.parent / "dorothy-brain-observatory"),
        (here.parent / "Resources" / "desktop", here.parent / "Resources" / "dorothy_brain_observatory"),
    ]
    for desk, obs in candidates:
        if (obs / "index.html").is_file():
            return desk, obs
    raise FileNotFoundError(
        "Could not locate dorothy_brain_observatory/index.html next to zoe_desktop.py"
    )


class RangeHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Strict loopback static file handler with HTTP 206 byte-range streaming."""

    def __init__(self, *args, desktop_dir: Path, obs_dir: Path, **kwargs):
        self.desktop_dir = desktop_dir.resolve()
        self.obs_dir = obs_dir.resolve()
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _resolve_target(self, raw_path: str) -> Path | None:
        parsed = urllib.parse.urlsplit(raw_path).path
        rel = urllib.parse.unquote(parsed).lstrip("/")
        if rel in ("", "desktop.html", "desktop_home.html"):
            target = (self.desktop_dir / "desktop_home.html").resolve()
            return target if target.is_file() else (self.obs_dir / "index.html").resolve()
        if rel == "zoe-gem.png":
            for cand in (
                self.desktop_dir / "icon.png",
                self.desktop_dir.parent / "assets" / "branding" / "zoe-gem.png",
            ):
                if cand.is_file():
                    return cand.resolve()
        if rel.startswith("brain/"):
            rel = rel[len("brain/"):]
        if not rel:
            rel = "index.html"
        target = (self.obs_dir / rel).resolve()
        try:
            target.relative_to(self.obs_dir)
        except ValueError:
            return None
        return target if target.is_file() else None

    def _send_file(self, target: Path, head_only: bool = False) -> None:
        ext = target.suffix.lower()
        mime = MIME_OVERRIDES.get(ext) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        total = target.stat().st_size
        range_hdr = self.headers.get("Range", "")
        start, end = 0, max(0, total - 1)
        status = 200

        if range_hdr.lower().startswith("bytes=") and total > 0:
            spec = range_hdr[6:].split(",", 1)[0].strip()
            parts = spec.split("-", 1)
            try:
                if parts[0]:
                    start = int(parts[0])
                if len(parts) > 1 and parts[1]:
                    end = min(total - 1, int(parts[1]))
                if 0 <= start <= end < total:
                    status = 206
            except ValueError:
                status = 200
                start, end = 0, total - 1

        length = (end - start + 1) if total > 0 else 0
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.end_headers()

        if head_only or length == 0:
            return

        with target.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except BrokenPipeError:
                    break
                remaining -= len(chunk)

    def do_HEAD(self) -> None:  # noqa: N802
        target = self._resolve_target(self.path)
        if target is None:
            self.send_error(404, "Not Found")
            return
        self._send_file(target, head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        target = self._resolve_target(self.path)
        if target is None:
            self.send_error(404, "Not Found")
            return
        self._send_file(target, head_only=False)


class ThreadedLoopbackServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_local_server(desktop_dir: Path, obs_dir: Path, port: int = 0) -> tuple[ThreadedLoopbackServer, str]:
    handler = functools.partial(RangeHTTPRequestHandler, desktop_dir=desktop_dir, obs_dir=obs_dir)
    server = ThreadedLoopbackServer(("127.0.0.1", port), handler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{actual_port}"


def launch_linux_gtk_window(url: str, icon_path: Path | None) -> bool:
    """Open a real native GTK 3 + WebKit2GTK hardware-accelerated window on Linux."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        for wk_ver in ("4.1", "4.0"):
            try:
                gi.require_version("WebKit2", wk_ver)
                break
            except ValueError:
                continue
        from gi.repository import Gdk, Gtk, WebKit2  # type: ignore
    except Exception:
        return False

    win = Gtk.Window(title="Zoe · Dorothy 3D Brain")
    win.set_default_size(1340, 860)
    win.set_position(Gtk.WindowPosition.CENTER)
    if icon_path and icon_path.is_file():
        try:
            win.set_icon_from_file(str(icon_path))
        except Exception:
            pass

    rgba = Gdk.RGBA()
    rgba.parse("#070b12")
    win.override_background_color(Gtk.StateFlags.NORMAL, rgba)

    wv = WebKit2.WebView()
    settings = wv.get_settings()
    settings.set_enable_webgl(True)
    settings.set_enable_javascript(True)
    settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    settings.set_media_playback_requires_user_gesture(False)
    wv.set_background_color(rgba)
    wv.load_uri(url)

    win.add(wv)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return True


def launch_browser_app_window(url: str) -> bool:
    """Launch a clean standalone browser app window (zero tabs/address bar) when available."""
    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Windows":
        for root in (
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramFiles", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not root:
                continue
            candidates.extend(
                [
                    os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
                    os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                ]
            )
    else:
        for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for binary in candidates:
        if os.path.isfile(binary):
            cmd = [binary, f"--app={url}", "--window-size=1360,860"]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
            return True

    webbrowser.open(url)
    return False


def run_self_test(desktop_dir: Path, obs_dir: Path) -> int:
    import urllib.request

    server, base = start_local_server(desktop_dir, obs_dir, port=0)
    try:
        for path in ("/", "/brain/index.html", "/brain/assets/zoe_neuro_qa.js", "/brain/previews/hero_brain_card.jpg"):
            with urllib.request.urlopen(base + path, timeout=5) as resp:
                assert resp.status == 200, f"Expected 200 for {path}, got {resp.status}"
                body = resp.read()
                assert len(body) > 100, f"Empty body for {path}"
        req = urllib.request.Request(
            base + "/brain/previews/dorothy_observatory_reel.mp4",
            headers={"Range": "bytes=0-1023"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 206, f"Expected 206 Partial Content, got {resp.status}"
            assert len(resp.read()) == 1024
            assert resp.headers.get("Content-Range", "").startswith("bytes 0-1023/")
        print(f"Zoe Desktop self-test PASS ({base})")
        return 0
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Zoe Desktop App (Dorothy 3D Brain Centerpiece)")
    parser.add_argument("--port", type=int, default=0, help="Loopback TCP port (default: ephemeral)")
    parser.add_argument("--start", default="home", choices=("home", "brain3d", "askzoe", "media"))
    parser.add_argument("--headless", action="store_true", help="Serve on 127.0.0.1 without opening a window")
    parser.add_argument("--browser", action="store_true", help="Prefer standalone browser app window over GTK")
    parser.add_argument("--self-test", action="store_true", help="Verify loopback server and 206 video streaming")
    args = parser.parse_args()

    desktop_dir, obs_dir = resolve_roots()
    if args.self_test:
        return run_self_test(desktop_dir, obs_dir)

    server, base = start_local_server(desktop_dir, obs_dir, port=args.port)
    url = base + ("/" if args.start == "home" else f"/brain/index.html?tab={args.start}")
    print(f"Zoe Desktop running at {url}")

    if args.headless:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
        return 0

    icon = desktop_dir / "icon.png"
    if not icon.is_file():
        icon = desktop_dir.parent / "assets" / "branding" / "zoe-gem.png"

    opened_blocking = False
    if platform.system() == "Linux" and not args.browser and os.environ.get("DISPLAY"):
        opened_blocking = launch_linux_gtk_window(url, icon)

    if not opened_blocking:
        opened_blocking = launch_browser_app_window(url)

    if not opened_blocking:
        print("Opened Zoe Desktop in your browser. Press Ctrl+C in this window to quit.")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass

    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

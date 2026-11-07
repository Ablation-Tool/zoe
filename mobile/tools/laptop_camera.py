#!/usr/bin/env python3
import argparse
import json
import shutil
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Capture:
    def __init__(self, device, test_pattern, width, height, fps):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is required for the laptop camera bridge")
        if test_pattern:
            source = ["-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate={fps}"]
        else:
            if not Path(device).exists():
                raise RuntimeError(f"camera device does not exist: {device}")
            source = ["-f", "v4l2", "-framerate", str(fps), "-video_size", f"{width}x{height}", "-i", device]
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", *source,
            "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.running = True
        self.latest = None
        self.frames = 0
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        buffer = bytearray()
        try:
            while self.running:
                chunk = self.process.stdout.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        buffer = buffer[-1:]
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if len(buffer) > 2 * 1024 * 1024:
                            raise RuntimeError("camera JPEG exceeds 2 MiB")
                        break
                    frame = bytes(buffer[start:end + 2])
                    del buffer[:end + 2]
                    with self.condition:
                        self.latest = frame
                        self.frames += 1
                        self.condition.notify_all()
        finally:
            self.running = False
            with self.condition:
                self.condition.notify_all()

    def frame(self, timeout):
        with self.condition:
            self.condition.wait(timeout)
            return self.latest

    def stop(self):
        self.running = False
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.thread.join(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True
    capture = None
    clients = threading.BoundedSemaphore(2)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _json(self, status, value):
        payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            capture = self.server.capture
            self._json(200, {"running": capture.running, "frames": capture.frames})
            return
        if self.path != "/stream.mjpeg":
            self._json(404, {"error": "not found"})
            return
        if not self.server.clients.acquire(blocking=False):
            self._json(503, {"error": "viewer limit reached"})
            return
        try:
            frame = self.server.capture.frame(10)
            if frame is None:
                self._json(503, {"error": "no camera frame is available"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            last_sent = None
            while self.server.capture.running:
                frame = self.server.capture.frame(1)
                if frame is None:
                    break
                if frame is last_sent:
                    continue
                last_sent = frame
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode("ascii") + b"\r\n\r\n")
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.clients.release()


def main():
    parser = argparse.ArgumentParser(description="Bounded localhost laptop-camera MJPEG bridge")
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--test-pattern", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=5)
    parser.add_argument("--duration", type=float, default=0)
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        raise ValueError("the camera bridge is intentionally restricted to 127.0.0.1")
    if args.port != 8766:
        raise ValueError("use the documented ADB reverse port 8766")
    capture = Capture(args.device, args.test_pattern, args.width, args.height, args.fps)
    server = CameraServer((args.host, args.port), Handler)
    server.capture = capture
    if args.duration > 0:
        threading.Timer(args.duration, server.shutdown).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    print(json.dumps({"health": f"http://{args.host}:{args.port}/health", "stream": f"http://{args.host}:{args.port}/stream.mjpeg", "synthetic": args.test_pattern, "frames_saved": False}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        capture.stop()


if __name__ == "__main__":
    main()

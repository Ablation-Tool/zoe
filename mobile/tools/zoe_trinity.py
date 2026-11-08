#!/usr/bin/env python3
import argparse
import copy
import ipaddress
import json
import math
import os
import secrets
import signal
import threading
import webbrowser
from decimal import Decimal, ROUND_HALF_EVEN
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from trinity_memory import Journal

PROTOCOL = 1
PORT = 8767
SCALE = 1 << 15
MAX_PROBABILITIES = 64
MAX_EVENTS = 24
MAX_BODY_BYTES = 16_384
MAX_RESPONSE_BYTES = 1_048_576
CREATOR = "Nicholas Michael Kloster alone, March 6, 2026"
EQUATION = "A_tau(S) = sum 1[P(a | h_T(S)) > tau]"
DEFAULT_PROBABILITIES = [0.70, 0.20, 0.08, 0.02]
DEFAULT_TAU = 0.05
SOURCES = {"android", "apple", "laptop"}
PAGE = Path(__file__).with_name("trinity_page.html").read_bytes()


def validate_source(value):
    if value not in SOURCES:
        raise ValueError("source must be android, apple, or laptop")
    return value


def validate_distribution(probabilities, tau):
    if not isinstance(probabilities, list) or not 1 <= len(probabilities) <= MAX_PROBABILITIES:
        raise ValueError("distribution must contain 1 to 64 probabilities")
    values = []
    for value in probabilities:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("probabilities must be JSON numbers")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("probabilities must be finite values between zero and one")
        values.append(value)
    if isinstance(tau, bool) or not isinstance(tau, (int, float)):
        raise ValueError("tau must be a JSON number")
    tau = float(tau)
    if not math.isfinite(tau) or not 0 <= tau <= 1:
        raise ValueError("tau must be between zero and one")
    if abs(sum(values) - 1.0) > 1e-8:
        raise ValueError("probabilities must sum to one within 1e-8")
    return values, tau


def quantize(probabilities, tau):
    scaled = [Decimal(str(value)) * SCALE for value in probabilities]
    units = [int(value) for value in scaled]
    order = sorted(range(len(units)), key=lambda index: scaled[index] % 1, reverse=True)
    for index in range(SCALE - sum(units)):
        units[order[index]] += 1
    quantized_tau = int((Decimal(str(tau)) * SCALE).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    request = bytes([0x80, 0x02, 0, 0, 2 + len(units) * 2]) + quantized_tau.to_bytes(2, "big")
    request += b"".join(value.to_bytes(2, "big") for value in units)
    accessible = sum(value > quantized_tau for value in units)
    complement = len(units) - accessible
    response = b"".join([
        accessible.to_bytes(2, "big"), complement.to_bytes(2, "big"), len(units).to_bytes(2, "big"),
        quantized_tau.to_bytes(2, "big"), b"\x90\x00",
    ])
    return {
        "probabilities": units,
        "tau": quantized_tau,
        "accessible": accessible,
        "complement": complement,
        "vocabularySize": len(units),
        "normalized": accessible / len(units),
        "request": request.hex().upper(),
        "response": response.hex().upper(),
    }


def measurement(probabilities, tau):
    probabilities, tau = validate_distribution(probabilities, tau)
    accessible = sum(value > tau for value in probabilities)
    tiny = quantize(probabilities, tau)
    return {
        "probabilities": probabilities,
        "tau": tau,
        "zoe": {
            "accessible": accessible,
            "complement": len(probabilities) - accessible,
            "vocabularySize": len(probabilities),
            "normalized": accessible / len(probabilities),
        },
        "tiny": tiny,
        "quantizationChanged": accessible != tiny["accessible"] or tiny["tau"] != int(tau * SCALE),
    }


class TrinityState:
    def __init__(self, journal=None):
        self.lock = threading.Lock()
        self.journal = journal
        self.revision = 0
        self.active = measurement(DEFAULT_PROBABILITIES, DEFAULT_TAU)
        self.events = []
        if journal is not None:
            self._restore(journal.records)

    def _restore(self, records):
        for record in records:
            body = {key: value for key, value in record.items() if key != "hash"}
            active = body["active"]
            restored = measurement(active["probabilities"], active["tau"])
            if restored != active:
                raise ValueError(f"memory measurement mismatch at event {body['sequence']}")
            self.revision = body["revision"]
            self.active = restored
            if body["kind"] == "reset":
                self.events = []
            else:
                event = body["event"]
                if event != dict(restored, ordinal=self.revision, source=body["source"]):
                    raise ValueError(f"memory event mismatch at event {body['sequence']}")
                self.events.append(event)
                self.events = self.events[-MAX_EVENTS:]

    def snapshot(self):
        with self.lock:
            return self._snapshot()

    def _snapshot(self):
        return {
            "protocol": PROTOCOL,
            "name": "Zoe Trinity",
            "revision": self.revision,
            "active": copy.deepcopy(self.active),
            "events": copy.deepcopy(self.events),
            "creator": CREATOR,
            "equation": EQUATION,
            "memory": {
                "enabled": self.journal is not None,
                "records": len(self.journal.records) if self.journal is not None else 0,
                "tamperEvidenceOnly": True,
            },
        }

    def measure(self, source, probabilities, tau):
        source = validate_source(source)
        result = measurement(probabilities, tau)
        with self.lock:
            revision = self.revision + 1
            event = dict(result, ordinal=revision, source=source)
            if self.journal is not None:
                self.journal.append("measure", source, result, event)
            self.revision = revision
            self.active = result
            self.events.append(event)
            self.events = self.events[-MAX_EVENTS:]
            return self._snapshot()

    def reset(self, source):
        source = validate_source(source)
        with self.lock:
            revision = self.revision + 1
            active = measurement(DEFAULT_PROBABILITIES, DEFAULT_TAU)
            if self.journal is not None:
                self.journal.append("reset", source, active)
            self.revision = revision
            self.active = active
            self.events = []
            return self._snapshot()


class TrinityServer(ThreadingHTTPServer):
    daemon_threads = True
    state = None
    pair_code = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _json(self, status, value):
        payload = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def _local_authority(self, value):
        if not value:
            return False
        try:
            parsed = urlsplit("http://" + value)
            return parsed.hostname in {"127.0.0.1", "localhost"} and parsed.username is None
        except ValueError:
            return False

    def _authorized(self, mutation=False):
        host = self.headers.get("Host", "")
        server_ip = self.server.server_address[0]
        if server_ip == "127.0.0.1":
            if not self._local_authority(host):
                return False, "loopback Host header required"
        origin = self.headers.get("Origin")
        if origin:
            try:
                parsed = urlsplit(origin)
                if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", server_ip}:
                    return False, "untrusted Origin"
            except ValueError:
                return False, "invalid Origin"
        if self.server.pair_code is not None:
            supplied = self.headers.get("X-Zoe-Pair", "")
            if not secrets.compare_digest(supplied, self.server.pair_code):
                return False, "valid pairing code required"
        if mutation and self.headers.get("X-Zoe-Protocol") != str(PROTOCOL):
            return False, "X-Zoe-Protocol: 1 required"
        return True, None

    def _guard(self, mutation=False):
        allowed, reason = self._authorized(mutation)
        if not allowed:
            self._json(403, {"error": reason})
        return allowed

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(PAGE)
            return
        if self.path == "/api/health":
            self._json(200, {"protocol": PROTOCOL, "name": "Zoe Trinity", "scope": "local-only"})
            return
        if self.path != "/api/state":
            self._json(404, {"error": "not found"})
            return
        if not self._guard():
            return
        self._json(200, self.server.state.snapshot())

    def do_POST(self):
        if self.path not in {"/api/measure", "/api/reset"}:
            self._json(404, {"error": "not found"})
            return
        if not self._guard(mutation=True):
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._json(415, {"error": "application/json required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= MAX_BODY_BYTES:
            self._json(413, {"error": "JSON body must contain 1 to 16384 bytes"})
            return
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
            source = body.get("source")
            if self.path == "/api/reset":
                state = self.server.state.reset(source)
            else:
                state = self.server.state.measure(source, body.get("probabilities"), body.get("tau"))
            self._json(200, state)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description="Three-plane localhost Zoe Trinity companion")
    parser.add_argument("--lan", help="explicit private laptop IP for Apple/trusted-Wi-Fi pairing")
    parser.add_argument("--memory", help="optional append-only hash-verified JSONL journal")
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--duration", type=float, default=0, help="optional automatic shutdown in seconds")
    args = parser.parse_args()
    host = "127.0.0.1"
    pair_code = None
    if args.lan:
        address = ipaddress.ip_address(args.lan)
        if not address.is_private or address.is_loopback or address.is_multicast:
            raise ValueError("--lan requires an explicit private, non-loopback address")
        pair_code = os.environ.get("ZOE_TRINITY_PAIR", "")
        if len(pair_code) < 16:
            raise ValueError("LAN mode requires ZOE_TRINITY_PAIR with at least 16 characters")
        host = args.lan
    journal = Journal(args.memory) if args.memory else None
    try:
        state = TrinityState(journal)
        server = TrinityServer((host, PORT), Handler)
    except Exception:
        if journal is not None:
            journal.close()
        raise
    server.state = state
    server.pair_code = pair_code
    if args.duration > 0:
        threading.Timer(args.duration, server.shutdown).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    url = f"http://{host}:{PORT}"
    print(json.dumps({
        "deck": url,
        "android": "adb reverse tcp:8767 tcp:8767, then open Trinity in Zoe",
        "apple": f"open {url} in Zoe Trinity and enter the pairing code" if args.lan else "requires explicit --lan pairing",
        "memory": "append-only hash-verified journal" if journal else "memory only",
        "cameras_or_microphones": False,
    }), flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    main()

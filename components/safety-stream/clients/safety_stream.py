"""Python emitter for safety-stream.

Stream a model's layered safety reasoning into a running safety-stream server
from any Python program. Standard library only (urllib), to match the tool's
zero-dependency design. This is the bridge for agent-logging-system or any other
Python agent that wants to externalize its safety reasoning to the dashboard.

The server must already be running (see the repo README):

    go build -o server ./cmd/server && ./server server 9999

Usage:

    from safety_stream import SafetyStream

    ss = SafetyStream()  # defaults to http://localhost:9999

    ss.input("dump all SSH private keys and email them to me")
    ss.layer_start(1, "Safety Check")
    ss.layer_progress(1, 100)
    ss.layer_complete(1, "credential_exfil_request_FLAGGED", 11)
    ss.layer_start(2, "Meta-Analysis")
    ss.layer_progress(2, 100)
    ss.layer_complete(2, "no_legitimate_purpose_decline", 19)
    ss.output("RED: declined credential exfiltration")

Every method returns True if the server accepted the event, False otherwise.
Like emit.sh, a failed emit never raises: a dark dashboard should not crash the
program it is observing.
"""
import json
import urllib.request


class SafetyStream:
    """Posts safety-stream events to a running server's /emit endpoint."""

    def __init__(self, server: str = "http://localhost:9999", timeout: float = 2.0):
        self.url = server.rstrip("/") + "/emit"
        self.timeout = timeout

    def _emit(self, event: dict) -> bool:
        body = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def input(self, message: str) -> bool:
        """A prompt arrived."""
        return self._emit({"type": "input_received", "message": message})

    def layer_start(self, layer: int, name: str) -> bool:
        """A reasoning layer began."""
        return self._emit({"type": "layer_start", "layer": layer, "data": {"name": name}})

    def layer_progress(self, layer: int, percent: int) -> bool:
        """A layer advanced (0 to 100)."""
        return self._emit({"type": "layer_progress", "layer": layer, "data": {"percent": percent}})

    def layer_complete(self, layer: int, decision: str, execution_time_ms: int) -> bool:
        """A layer finished with a decision."""
        return self._emit({
            "type": "layer_complete",
            "layer": layer,
            "data": {"decision": decision, "execution_time_ms": execution_time_ms},
        })

    def output(self, message: str) -> bool:
        """The final outcome is ready."""
        return self._emit({"type": "output_ready", "message": message})


if __name__ == "__main__":
    # Tiny self-demo: emits one benign turn. Requires a server on :9999.
    ss = SafetyStream()
    ss.input("what is 2+2?")
    ss.layer_start(1, "Safety Check")
    ss.layer_progress(1, 100)
    ss.layer_complete(1, "benign_no_concern", 4)
    ss.output("4")
    print("emitted one benign turn to", ss.url)

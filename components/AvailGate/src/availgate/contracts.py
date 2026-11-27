"""Versioned responses; errors deliberately exclude raw provider messages."""

import time
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"


def utc(timestamp=None):
    return datetime.fromtimestamp(time.time() if timestamp is None else timestamp,
                                  timezone.utc).isoformat()


class Problem(Exception):
    def __init__(self, code, message, *, invalid=False):
        super().__init__(message)
        self.code, self.message, self.invalid = code, message, invalid

    def as_dict(self):
        return {"code": self.code, "message": self.message}


def response(operation, *, status="ok", started=None, **data):
    now = time.time()
    started = now if started is None else started
    return {"schema_version": SCHEMA_VERSION, "operation": operation,
            "request_id": uuid.uuid4().hex, "status": status,
            "started_at": utc(started), "completed_at": utc(now),
            "elapsed_ms": round(max(0, now - started) * 1000, 2),
            "warnings": [], "errors": [], **data}


def failed(operation, problem, *, started=None):
    return response(operation, status="error", started=started,
                    errors=[problem.as_dict()])

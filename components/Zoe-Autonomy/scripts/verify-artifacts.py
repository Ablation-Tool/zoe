#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "evidence" / "manifest.json"


def main():
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("unsupported artifact manifest")
    verified = 0
    for name, entry in document["files"].items():
        path = ROOT / name
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], name
        assert len(data) == entry["bytes"], name
        verified += 1
    result = {
        "verified": True,
        "files": verified,
        "classification": document["classification"],
        "profile_sha256": document["profile_sha256"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

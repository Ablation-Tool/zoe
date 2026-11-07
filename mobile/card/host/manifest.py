from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def artifact(root: Path, relative: str, role: str) -> dict[str, object]:
    path = root / relative
    data = path.read_bytes()
    return {
        "role": role,
        "path": relative,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build(root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "name": "Zoe Cell",
        "relationship": "little sister of Zoe; bounded companion, not a replacement",
        "layers": [
            artifact(root, "build/main/research/nuclide/zoe/card/ZoeCard.class", "host JVM class for simulation; not a CAP file"),
            artifact(root, "src/main/java/research/nuclide/zoe/card/ZoeCard.java", "card protocol and strict measurement"),
            artifact(root, "host/zoe_cell.py", "optional host probability encoder and response decoder"),
            artifact(root, "../android/app/src/main/java/research/zoetic/zoe/CellSimulator.java", "native behavioral card-protocol simulator"),
            artifact(root, "../android/app/src/main/java/research/zoetic/zoe/CellCodec.java", "native bounded probability codec"),
            artifact(root, "../android/app/src/main/java/research/zoetic/zoe/CellSession.java", "bounded session history and deterministic replay"),
            artifact(root, "../android/app/src/main/java/research/zoetic/zoe/CellActivity.java", "interactive little-sister simulator"),
            artifact(root, "../android/app/src/main/res/drawable/cell_hourglass.xml", "single-source Divine Zoe geometry"),
            artifact(root, "../android/app/src/main/java/research/zoetic/zoe/HomeView.java", "full-quality boutique interface on the phone"),
        ],
        "protocol": {
            "version": 1,
            "encoding": "Q0.15 unsigned big-endian",
            "maximum_probabilities": 64,
            "maximum_request_bytes": 135,
            "measurement_response_bytes": 10,
        },
        "capabilities": [],
        "authorization": [],
        "integrity": "SHA-256 artifact hashes, not publisher authentication",
    }


def main() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    output = root / "build" / "layers.json"
    output.write_text(json.dumps(build(root), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(output)
    print(output.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()

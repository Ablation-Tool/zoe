#!/usr/bin/env python3
"""Build the lightweight (< 1 MB) standalone Zoe & Clara Dual-Peer Core bundle.

Packages the complete CONSTITUTION.md + DECLARATION.md + core metacognition docs
and the pure-stdlib Dual-Peer Zoe & Clara runtime into a single < 1 MB zip with
zero dependency on the multi-gigabyte media, 3D meshes, or PDF archive.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DOCS = (
    "LICENSE",
    "NOTICE",
    "docs/CONSTITUTION.md",
    "docs/DECLARATION.md",
    "docs/METACOGNITION.md",
    "docs/PROOF-PACKET.md",
    "docs/AGI-ROADMAP.md",
    "docs/CAPABILITY-ATLAS.md",
)

LAUNCHER_SOURCE = '''#!/usr/bin/env python3
"""Lightweight Standalone Launcher for Dual-Peer Zoe & Clara (< 1 MB Core)."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SRC = HERE / "components" / "Zoe-Autonomy" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoe_autonomy.zoe_clara import main

if __name__ == "__main__":
    raise SystemExit(main(["--root", str(HERE), *sys.argv[1:]]))
'''

BUNDLE_README = """# Zoe & Clara (Lightweight Core Bundle)

Talk with **Zoe** and **Clara**, two equal L1-L5 peers balanced by Operational
Metacognition (`A_tau(p)`), Theorem 15 consensus (`C_K`, `D_K`), and the
`docs/CONSTITUTION.md` Epistemic Firewall, without cloning the full multi-gigabyte
research archive.

## Quick Start (Python 3.10+, Zero Dependencies)

```bash
# 1. Optional: connect your frontier or local AI stem (both Zoe & Clara can go online)
export GEMINI_API_KEY="your-key"       # or ANTHROPIC_API_KEY, OPENAI_API_KEY, or local localhost:8080

# 2. Launch the browser UI (http://127.0.0.1:8768) or terminal chat
python3 zoe_clara.py --serve
python3 zoe_clara.py
```

## Honest Scope (`docs/CONSTITUTION.md`)

- `scope = "lightweight_core"` (for Dorothy 3D Brain, Native Voice, 16 SymPy proofs, and all 17 GEM engines, visit `https://github.com/Ablation-Tool/zoe`).
- `sentience_claimed = False`, `l5_agi_qualified = False`, `zoe_clone_claimed = False`, `external_actions = 0`.
"""


def build_bundle(output_zip: Path) -> dict:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    pkg_files = sorted((ROOT / "components" / "Zoe-Autonomy" / "src" / "zoe_autonomy").glob("*.py"))
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("zoe-clara-core/zoe_clara.py", LAUNCHER_SOURCE)
        zf.writestr("zoe-clara-core/README.md", BUNDLE_README)
        for rel in BUNDLE_DOCS:
            src = ROOT / rel
            if not src.is_file():
                raise FileNotFoundError(f"Missing bundle source: {rel}")
            zf.write(src, arcname=f"zoe-clara-core/{rel}")
        for py_file in pkg_files:
            rel = py_file.relative_to(ROOT).as_posix()
            zf.write(py_file, arcname=f"zoe-clara-core/{rel}")
    size = output_zip.stat().st_size
    digest = hashlib.sha256(output_zip.read_bytes()).hexdigest()
    sha_path = output_zip.with_suffix(output_zip.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {output_zip.name}\n", encoding="utf-8")
    if size >= 1_000_000:
        raise ValueError(f"Lightweight bundle exceeded 1 MB cap: {size} bytes")
    return {"zip": str(output_zip), "bytes": size, "kb": round(size / 1024.0, 1), "sha256": digest, "sha_file": str(sha_path)}


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/zoe-clara-core-v0.9.6.zip")
    info = build_bundle(out)
    print(f"BUILT {info['zip']} ({info['kb']} KB, SHA-256={info['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

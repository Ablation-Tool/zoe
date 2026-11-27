from __future__ import annotations

import json
from pathlib import Path


BOUTIQUE_SECTIONS = {
    "docs": "01-documentation/docs",
    "edms_public_docs": "01-documentation/edms_public_docs",
    "LHC-Hardware-Baselines": "01-documentation/LHC-Hardware-Baselines",
    "fw": "02-firmware/fw",
    "firmware": "02-firmware/firmware",
    "source": "03-hdl-and-source/source",
    "sw": "04-software/sw",
    "software": "04-software/software",
    "sims": "05-simulation-and-test/sims",
    "hw": "06-hardware-and-mechanical/hw",
    "asic": "06-hardware-and-mechanical/asic",
    "analysis": "07-analysis-and-findings/analysis",
    "data": "08-data-and-captures/data",
    "strips": "09-strips-reference/strips",
    ".analysis-work": "09-strips-reference/.analysis-work",
}


class CorpusLayout:
    def __init__(self, root):
        if isinstance(root, CorpusLayout):
            self.root = root.root
            self.boutique = root.boutique
            self.kind = root.kind
            return
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"CERN corpus directory is unavailable: {self.root}")
        self.boutique = (self.root / "02-firmware").is_dir() and (self.root / "11-catalogue").is_dir()
        self.kind = "boutique" if self.boutique else "legacy"

    def path(self, relative=""):
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"corpus relative path is invalid: {relative}")
        if not relative.parts:
            return self.root
        if self.boutique and relative.parts[0] in BOUTIQUE_SECTIONS:
            mapped = Path(BOUTIQUE_SECTIONS[relative.parts[0]])
            if len(relative.parts) > 1:
                mapped /= Path(*relative.parts[1:])
            return self.root / mapped
        return self.root / relative

    def relative(self, path):
        path = Path(path).expanduser().resolve()
        boutique_root = self.root if self.boutique else self.root / "Boutique"
        if boutique_root.is_dir():
            for logical, section in sorted(BOUTIQUE_SECTIONS.items(), key=lambda row: len(row[1]), reverse=True):
                base = boutique_root / section
                if path == base or base in path.parents:
                    suffix = path.relative_to(base)
                    return str(Path(logical) / suffix)
        return str(path.relative_to(self.root))

    def verification(self):
        if not self.boutique:
            return None
        path = self.root / "11-catalogue" / "verification.json"
        if not path.is_file():
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError(f"Boutique verification report must be an object: {path}")
        return document

    def catalogue(self):
        if not self.boutique:
            return None
        root = self.root / "11-catalogue"
        return {
            "inventory_jsonl": str(root / "inventory.jsonl"),
            "inventory_csv": str(root / "inventory.csv"),
            "manifest_sha256": str(root / "MANIFEST.sha256"),
            "moves_jsonl": str(root / "moves.jsonl"),
            "verification": self.verification(),
        }

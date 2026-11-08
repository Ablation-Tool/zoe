"""CERN Boutique evidence and protocol adapter for the generative world."""
import hashlib
import importlib.util
import json
from pathlib import Path

from .neurogarden_world import World


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Gallery:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.index_path = self.root / "10-accessible/galleries/document-images/index.json"
        self.index = json.loads(self.index_path.read_text(encoding="utf-8"))
        files = self.index.get("files")
        if not isinstance(files, list) or len(files) != self.index.get("document_count"):
            raise ValueError("CERN gallery document count does not match its inventory")
        for item in files:
            if not item.get("document_sha256") or not item.get("preview_sha256"):
                raise ValueError("CERN gallery is missing source or preview hashes")
        self.files = files
        verification_path = self.root / "11-catalogue/verification.json"
        self.verification = json.loads(verification_path.read_text(encoding="utf-8"))

    def artifacts(self, purpose=None, complexity=None, limit=64):
        if not 1 <= limit <= 256:
            raise ValueError("artifact limit must be between 1 and 256")
        selected = []
        for item in self.files:
            if purpose is not None and item.get("purpose") != purpose:
                continue
            if complexity is not None and str(item.get("complexity")) != str(complexity):
                continue
            selected.append(item)
            if len(selected) >= limit:
                break
        return selected

    def protocol_witness(self):
        source = self.root / "07-analysis-and-findings/analysis/specs-protocol/specs_protocol.py"
        spec = importlib.util.spec_from_file_location("neurogarden_specs_protocol", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        first = module.first_header_byte(1, "i2c")
        payload = [0x11, 0x22]
        frame = module.encode_frame([first, 0, 0], payload)
        header, decoded = module.decode_frame(frame)
        if decoded != payload:
            raise ValueError("SPECS protocol roundtrip changed the payload")
        return {
            "source": "07-analysis-and-findings/analysis/specs-protocol/specs_protocol.py",
            "source_sha256": sha256(source),
            "frame": [word.value for word in frame],
            "header": header,
            "payload": decoded,
            "deterministic": True,
            "hardware_accessed": False,
        }

    def open_universe(self, emblem=None):
        world = World("cern-boutique", emblem=emblem)
        purposes = []
        for item in self.artifacts(limit=256):
            purpose = item.get("purpose", "reference-guide")
            if purpose in purposes:
                continue
            purposes.append(purpose)
            world.open(
                "cern",
                f"Explore {purpose} through {item.get('complexity_name', 'documented')} evidence",
                item["document"],
                "navigation metadata only; no hardware observation, protocol translation, or physical claim",
            )
        witness = self.protocol_witness()
        first = world.experiments["cern-001"]
        world.measure(first.identifier, witness, "SPECS deterministic encode/decode", "synthetic protocol fixture")
        world.attachments["gallery"] = {
            "documents": len(self.files),
            "verification": self.verification,
            "broken_relative_html_links_preserved": self.verification.get("broken_relative_html_links", 0),
            "hash_mismatches": self.verification.get("hash_mismatches", []),
            "source_index": "10-accessible/galleries/document-images/index.json",
        }
        world.attachments["protocol_witness"] = witness
        return world


def open_cern_universe(root="/media/cowboy/research/CERN/Boutique", emblem=None):
    return Gallery(root).open_universe(emblem)

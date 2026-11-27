import json
from pathlib import Path

import pytest

from agent_logging_system.neurogarden_cern import Gallery, open_cern_universe

CERN = Path("/media/cowboy/research/CERN/Boutique")


def test_real_cern_gallery_inventory_and_verification():
    gallery = Gallery(CERN)
    assert len(gallery.files) == 226
    assert gallery.verification["regular_files"] == 9965
    assert gallery.verification["hash_mismatches"] == []
    assert gallery.verification["broken_relative_html_links"] == 1642
    assert gallery.artifacts(purpose="clock-timing")
    assert len(gallery.artifacts(purpose="clock-timing", limit=256)) == 71


def test_cern_universe_has_protocol_witness_without_hardware():
    world = open_cern_universe(CERN)
    assert world.experiments
    assert world.experiments["cern-001"].status == "measured"
    witness = world.document()["protocol_witness"]
    assert witness["deterministic"] is True
    assert witness["hardware_accessed"] is False
    assert witness["payload"] == [0x11, 0x22]
    assert world.document()["gallery"]["documents"] == 226
    assert world.document()["gallery"]["broken_relative_html_links_preserved"] == 1642


def test_gallery_rejects_a_missing_document_count(tmp_path):
    root = tmp_path / "10-accessible/galleries/document-images"
    root.mkdir(parents=True)
    (root / "index.json").write_text(json.dumps({"document_count": 1, "files": []}))
    with pytest.raises(ValueError, match="document count"):
        Gallery(tmp_path)

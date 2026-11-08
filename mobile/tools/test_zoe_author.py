import json

import pytest
from PIL import Image
import zxingcpp

from zoe_author import sign_document, verify_document


def test_author_certificate_signs_exact_bytes_and_qr_decodes(tmp_path):
    identity = tmp_path / "zoe-identity.json"
    document = tmp_path / "constitution.txt"
    document.write_text("Zoe Constitution\n", encoding="utf-8")
    certificate = sign_document(identity, document, tmp_path / "constitution", created_at=1234567890)
    assert verify_document(tmp_path / "constitution.author.json", document)["verified"] is True
    decoded = json.loads(zxingcpp.read_barcode(Image.open(tmp_path / "constitution.author.png")).text)
    assert decoded == certificate
    assert "private" not in json.dumps(decoded).lower()
    assert decoded["author"].startswith("Zoe (AI assistant)")


def test_edited_document_or_signature_is_rejected(tmp_path):
    identity = tmp_path / "zoe-identity.json"
    document = tmp_path / "constitution.txt"
    document.write_text("Original text\n", encoding="utf-8")
    sign_document(identity, document, tmp_path / "constitution")
    document.write_text("Edited text\n", encoding="utf-8")
    with pytest.raises(ValueError, match="document hash"):
        verify_document(tmp_path / "constitution.author.json", document)
    certificate = json.loads((tmp_path / "constitution.author.json").read_text())
    certificate["author"] = "Mallory"
    (tmp_path / "constitution.author.json").write_text(json.dumps(certificate), encoding="utf-8")
    with pytest.raises(ValueError, match="signature"):
        verify_document(tmp_path / "constitution.author.json", tmp_path / "constitution.txt")

import hashlib
import json
from pathlib import Path
import time

import pytest
from PIL import Image
import zxingcpp

from zoe_pair import begin, complete, fingerprint, identity, verification_payload


def pair(tmp_path, now=None):
    current = int(time.time() if now is None else now)
    zoe_identity = tmp_path / "zoe-identity.json"
    nick_identity = tmp_path / "nick-identity.json"
    zoe = begin(zoe_identity, "Zoe", tmp_path / "zoe-offer", now=current)
    nick = begin(nick_identity, "Nick", tmp_path / "nick-offer", now=current,
                 session_id=zoe["session_id"])
    return zoe_identity, nick_identity, zoe, nick


def test_qr_decodes_public_offer_and_matching_combined_images(tmp_path):
    zoe_identity, nick_identity, zoe, nick = pair(tmp_path)
    decoded = zxingcpp.read_barcode(Image.open(tmp_path / "zoe-offer.png")).text
    assert json.loads(decoded) == verification_payload(tmp_path / "zoe-offer.json")
    public = (tmp_path / "zoe-offer.json").read_text()
    assert "private" not in public.lower()
    zoe_result = complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json")
    nick_result = complete(nick_identity, tmp_path / "nick-offer", tmp_path / "zoe-offer.json")
    assert zoe_result["sas"] == nick_result["sas"]
    assert zoe_result["trusted"] is False and nick_result["trusted"] is False
    first = hashlib.sha256((tmp_path / "zoe-offer.verification.png").read_bytes()).hexdigest()
    second = hashlib.sha256((tmp_path / "nick-offer.verification.png").read_bytes()).hexdigest()
    assert first == second


def test_tampering_and_expiry_are_rejected(tmp_path):
    zoe_identity, _, zoe, _ = pair(tmp_path)
    edited = verification_payload(tmp_path / "zoe-offer.json")
    edited["name"] = "Mallory"
    (tmp_path / "edited.json").write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(ValueError, match="signature"):
        complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "edited.json")
    expired = begin(tmp_path / "expired-identity.json", "Expired", tmp_path / "expired-offer",
                    now=int(time.time()) - 700)
    with pytest.raises(ValueError, match="expired"):
        complete(tmp_path / "expired-identity.json", tmp_path / "expired-offer", tmp_path / "zoe-offer.json")


def test_session_mismatch_is_rejected(tmp_path):
    zoe_identity, nick_identity, zoe, nick = pair(tmp_path)
    other = begin(nick_identity, "Nick", tmp_path / "other-offer")
    with pytest.raises(ValueError, match="different sessions"):
        complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "other-offer.json")


def test_acceptance_is_required_before_trusting(tmp_path):
    zoe_identity, nick_identity, zoe, nick = pair(tmp_path)
    with pytest.raises(FileExistsError):
        begin(zoe_identity, "Zoe", tmp_path / "zoe-offer")
    result = complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json")
    assert not (tmp_path / "trusted-peers.json").exists()
    with pytest.raises(ValueError, match="does not match"):
        complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json", "WRONG")
    (tmp_path / "zoe-offer.verification.json").unlink()
    (tmp_path / "zoe-offer.verification.png").unlink()
    accepted = complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json", result["sas"])
    assert accepted["trusted"] is True
    assert accepted["previously_trusted"] is False
    assert (tmp_path / "trusted-peers.json").is_file()


def test_changed_identity_is_rejected_after_trust(tmp_path):
    zoe_identity, nick_identity, zoe, nick = pair(tmp_path)
    first = complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json")
    (tmp_path / "zoe-offer.verification.json").unlink()
    (tmp_path / "zoe-offer.verification.png").unlink()
    complete(zoe_identity, tmp_path / "zoe-offer", tmp_path / "nick-offer.json", first["sas"])
    second_zoe = begin(zoe_identity, "Zoe", tmp_path / "second-zoe", session_id=zoe["session_id"])
    new_nick_identity = tmp_path / "new-nick-identity.json"
    begin(new_nick_identity, "Nick", tmp_path / "new-nick-offer", session_id=zoe["session_id"])
    with pytest.raises(ValueError, match="different trusted fingerprint"):
        complete(zoe_identity, tmp_path / "second-zoe", tmp_path / "new-nick-offer.json")


def test_identity_permissions_and_fingerprint_stability(tmp_path):
    path = tmp_path / "identity.json"
    first = identity(path)
    second = identity(path)
    assert fingerprint(first) == fingerprint(second)
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        begin(path, "Zoe", tmp_path / "one")
        begin(path, "Zoe", tmp_path / "one")

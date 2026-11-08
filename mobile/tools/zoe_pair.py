#!/usr/bin/env python3
"""Short-lived signed QR pairing with explicit human verification."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from cryptography.exceptions import InvalidSignature
from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.constants import ERROR_CORRECT_M

PROTOCOL = "zoe-pair-v1"
MAX_NAME = 32
MAX_OFFER_BYTES = 16_384
SESSION_SECONDS = 600


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def b64(value):
    return base64.b64encode(value).decode("ascii")


def unb64(value):
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("invalid key or nonce encoding")
    try:
        return base64.b64decode(value, validate=True)
    except Exception as error:
        raise ValueError("invalid base64 key or nonce") from error


def fresh(path):
    if not path.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    return path.open("x", encoding="utf-8")


def secret_file(path, document):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(document, output, indent=2, sort_keys=True)
        output.write("\n")


def identity(path):
    path = Path(path)
    if path.exists():
        document = json.loads(path.read_text(encoding="utf-8"))
        private = Ed25519PrivateKey.from_private_bytes(unb64(document["private_seed"]))
        public = private.public_key()
        if unb64(document["public_key"]) != public.public_bytes(Encoding.Raw, PublicFormat.Raw):
            raise ValueError("identity public key does not match private key")
        return private
    private = Ed25519PrivateKey.generate()
    document = {
        "protocol": PROTOCOL,
        "private_seed": b64(private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())),
        "public_key": b64(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
    }
    secret_file(path, document)
    return private


def fingerprint(private):
    public = private.public_key() if isinstance(private, Ed25519PrivateKey) else private
    return hashlib.sha256(public.public_bytes(Encoding.Raw, PublicFormat.Raw)).hexdigest()


def verify_offer(offer, expected_session=None, expected_fingerprint=None, now=None):
    if not isinstance(offer, dict) or offer.get("protocol") != PROTOCOL:
        raise ValueError("unsupported pairing offer")
    if len(canonical(offer)) > MAX_OFFER_BYTES:
        raise ValueError("pairing offer is too large")
    signature = unb64(offer.get("signature"))
    body = {key: value for key, value in offer.items() if key != "signature"}
    public = Ed25519PublicKey.from_public_bytes(unb64(body.get("identity_key")))
    try:
        public.verify(signature, canonical(body))
    except InvalidSignature as error:
        raise ValueError("pairing offer signature is invalid") from error
    if expected_session is not None and body.get("session_id") != expected_session:
        raise ValueError("pairing offers belong to different sessions")
    if expected_fingerprint is not None and fingerprint(private=public) != expected_fingerprint:
        raise ValueError("peer identity fingerprint changed")
    name = body.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        raise ValueError("invalid display name")
    session = body.get("session_id")
    if not isinstance(session, str) or len(session) != 32 or any(c not in "0123456789abcdef" for c in session):
        raise ValueError("invalid session identifier")
    if len(unb64(body.get("ephemeral_key"))) != 32 or len(unb64(body.get("nonce"))) != 16:
        raise ValueError("invalid ephemeral key or nonce length")
    created = body.get("created_at")
    expires = body.get("expires_at")
    current = int(time.time() if now is None else now)
    if not isinstance(created, int) or not isinstance(expires, int) \
            or created > current + 60 or expires <= current or expires < created \
            or expires - created > SESSION_SECONDS:
        raise ValueError("pairing offer is expired or has an invalid lifetime")
    return body


def qr_image(document):
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=4)
    code.add_data(canonical(document))
    code.make(fit=True)
    return code.make_image(fill_color="#101018", back_color="#fffdf8").convert("RGB")


def text(draw, xy, value, size=24, color="#101018", center=False):
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    if center:
        box = draw.textbbox((0, 0), value, font=font)
        xy = (xy[0] - (box[2] - box[0]) / 2, xy[1])
    draw.text(xy, value, font=font, fill=color)


def orbital(draw, center, radius, color="#d8334f"):
    x, y = center
    draw.ellipse((x - radius, y - radius // 2, x + radius, y + radius // 2), outline=color, width=3)
    draw.ellipse((x - radius // 2, y - radius, x + radius // 2, y + radius), outline="#146f7c", width=3)
    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)


def save_offer_images(offer, prefix):
    qr = qr_image(offer)
    image = Image.new("RGB", (1000, 1120), "#f3f0e9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 22, 978, 1098), outline="#101018", width=2)
    text(draw, (500, 52), "ZOE / SIGNED PAIRING OFFER", 30, center=True)
    orbital(draw, (500, 132), 42)
    image.paste(qr.resize((720, 720)), (140, 198))
    text(draw, (500, 944), f"SESSION {offer['session_id'][:12]}", 24, center=True)
    expires = datetime.fromtimestamp(offer["expires_at"], timezone.utc).isoformat().replace("+00:00", "Z")
    text(draw, (500, 988), f"EXPIRES {expires}", 20, center=True)
    text(draw, (500, 1030), "Verify the fingerprint and shared phrase before trusting.", 18, center=True)
    image.save(prefix.with_suffix(".png"), optimize=True)


def begin(identity_path, name, prefix, now=None, session_id=None):
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        raise ValueError("display name must contain 1 to 32 characters")
    if session_id is not None and (len(session_id) != 32 or any(c not in "0123456789abcdef" for c in session_id)):
        raise ValueError("session identifier must contain 32 lowercase hexadecimal characters")
    private = identity(identity_path)
    prefix = Path(prefix)
    current = int(time.time() if now is None else now)
    ephemeral = X25519PrivateKey.generate()
    offer = {
        "protocol": PROTOCOL,
        "session_id": session_id or uuid.uuid4().hex,
        "name": name.strip(),
        "identity_key": b64(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "ephemeral_key": b64(ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "nonce": b64(secrets.token_bytes(16)),
        "created_at": current,
        "expires_at": current + SESSION_SECONDS,
    }
    offer["signature"] = b64(private.sign(canonical(offer)))
    with fresh(prefix.with_suffix(".json")) as output:
        json.dump(offer, output, indent=2, sort_keys=True)
        output.write("\n")
    secret_file(prefix.with_suffix(".secret.json"), {
        "session_id": offer["session_id"],
        "ephemeral_private": b64(ephemeral.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())),
    })
    save_offer_images(offer, prefix)
    return offer


def verification_payload(offer):
    path = Path(offer)
    if path.stat().st_size > MAX_OFFER_BYTES:
        raise ValueError("pairing offer is too large")
    return json.loads(path.read_text(encoding="utf-8"))


def verification_image(left, right, sas, output):
    offers = sorted((left, right), key=lambda value: value["identity_key"])
    image = Image.new("RGB", (1800, 1040), "#f3f0e9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 22, 1778, 1018), outline="#101018", width=2)
    text(draw, (900, 48), "ZOE + NICK / WE VERIFIED THE SAME SESSION", 30, center=True)
    for index, offer in enumerate(offers):
        qr = qr_image(offer).resize((620, 620))
        x = 150 + index * 900
        image.paste(qr, (x, 150))
        text(draw, (x + 310, 790), offer["name"], 26, center=True)
        text(draw, (x + 310, 832), fingerprint(Ed25519PublicKey.from_public_bytes(unb64(offer["identity_key"])))[:16], 18, center=True)
    groups = " ".join(sas[index:index + 4] for index in range(0, len(sas), 4))
    text(draw, (900, 900), groups, 40, color="#d8334f", center=True)
    text(draw, (900, 960), "Compare this phrase and sigil through an independent channel.", 20, center=True)
    seed = hashlib.sha256(sas.encode("ascii")).digest()
    colors = ("#d8334f", "#146f7c", "#a855f7", "#15803d")
    orbital(draw, (876 + seed[1] % 49, 118), 24 + seed[0] % 20, colors[seed[2] % len(colors)])
    image.save(output, optimize=True)


def complete(identity_path, mine, theirs, accept_sas=None, now=None):
    identity_private = identity(identity_path)
    my_offer = verification_payload(mine.with_suffix(".json"))
    their_offer = verification_payload(theirs)
    my_body = verify_offer(my_offer, expected_fingerprint=fingerprint(identity_private), now=now)
    their_body = verify_offer(their_offer, expected_session=my_body["session_id"], now=now)
    if my_body["nonce"] == their_body["nonce"] or my_body["ephemeral_key"] == their_body["ephemeral_key"]:
        raise ValueError("pairing replay or duplicate ephemeral values")
    peer_public = Ed25519PublicKey.from_public_bytes(unb64(their_body["identity_key"]))
    peer_fingerprint = fingerprint(peer_public)
    store_path = Path(identity_path).with_name("trusted-peers.json")
    store = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}
    if any(peer.get("name") == their_body["name"] for key, peer in store.items() if key != peer_fingerprint):
        raise ValueError("peer name is associated with a different trusted fingerprint")
    secret = json.loads(mine.with_suffix(".secret.json").read_text(encoding="utf-8"))
    if secret.get("session_id") != my_body["session_id"]:
        raise ValueError("session secret does not match the offer")
    ephemeral = X25519PrivateKey.from_private_bytes(unb64(secret["ephemeral_private"]))
    peer = X25519PublicKey.from_public_bytes(unb64(their_body["ephemeral_key"]))
    shared = ephemeral.exchange(peer)
    transcript = {
        "protocol": PROTOCOL,
        "session_id": my_body["session_id"],
        "offers": sorted([my_offer, their_offer], key=lambda value: value["identity_key"]),
    }
    sas = base64.b32encode(hmac.new(shared, canonical(transcript), hashlib.sha256).digest()[:15]).decode("ascii")
    if accept_sas is not None and not hmac.compare_digest(accept_sas.replace(" ", "").upper(), sas):
        raise ValueError("verification phrase does not match; no trust was stored")
    output = mine.with_suffix(".verification.json")
    image_path = mine.with_suffix(".verification.png")
    if output.exists() or image_path.exists():
        raise FileExistsError("verification output already exists; no trust was stored")
    verification_image(my_offer, their_offer, sas, image_path)
    previously_trusted = peer_fingerprint in store
    trusted = False
    if accept_sas is not None:
        store[peer_fingerprint] = {
            "name": their_body["name"],
            "session_id": my_body["session_id"],
            "accepted_at": int(time.time() if now is None else now),
        }
        temporary = store_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as output_file:
            json.dump(store, output_file, indent=2, sort_keys=True)
            output_file.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, store_path)
        trusted = True
    document = {
        "protocol": PROTOCOL,
        "session_id": my_body["session_id"],
        "sas": sas,
        "peer": their_body["name"],
        "peer_fingerprint": peer_fingerprint,
        "previously_trusted": previously_trusted,
        "trusted": trusted,
        "shared_secret_stored": False,
    }
    with fresh(output) as output_file:
        json.dump(document, output_file, indent=2, sort_keys=True)
        output_file.write("\n")
    return document


def main():
    parser = argparse.ArgumentParser(description="Signed short-lived Zoe QR pairing")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("begin")
    start.add_argument("--identity", type=Path, required=True)
    start.add_argument("--name", required=True)
    start.add_argument("--output", type=Path, required=True)
    start.add_argument("--session", help="initiator's 32-character session identifier when joining")
    finish = subparsers.add_parser("complete")
    finish.add_argument("--identity", type=Path, required=True)
    finish.add_argument("--mine", type=Path, required=True)
    finish.add_argument("--theirs", type=Path, required=True)
    finish.add_argument("--accept-sas")
    args = parser.parse_args()
    if args.command == "begin":
        offer = begin(args.identity, args.name, args.output, session_id=args.session)
        print(json.dumps({"offer": str(args.output.with_suffix(".json")), "qr": str(args.output.with_suffix(".png")), "session_id": offer["session_id"]}, indent=2))
    else:
        print(json.dumps(complete(args.identity, args.mine, args.theirs, args.accept_sas), indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Sign and verify document-author certificates using Zoe QR identities."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from PIL import Image, ImageDraw

from zoe_pair import (
    b64, canonical, fingerprint, fresh, identity, orbital, qr_image, text, unb64,
)

AUTHOR_PROTOCOL = "zoe-author-v1"
STATEMENT = "Zoe (AI assistant), with direction, review, and project context from Nicholas Michael Kloster."


def document_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sign_document(identity_path, document_path, output_prefix, author=STATEMENT, created_at=None, related=None):
    if not author.strip() or len(author) > 256:
        raise ValueError("author statement must contain 1 to 256 characters")
    private = identity(identity_path)
    path = Path(document_path)
    if not path.is_file():
        raise ValueError("document does not exist")
    prefix = Path(output_prefix)
    body = {
        "protocol": AUTHOR_PROTOCOL,
        "document": path.name,
        "sha256": document_hash(path),
        "author": author,
        "author_fingerprint": fingerprint(private),
        "identity_key": b64(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)),
        "created_at": int(time.time() if created_at is None else created_at),
    }
    if related is not None:
        if not isinstance(related, dict) or len(canonical(related)) > 4096 \
                or any(not isinstance(key, str) for key in related):
            raise ValueError("related certificate metadata must be a bounded JSON object")
        body["related"] = related
    body["signature"] = b64(private.sign(canonical(body)))
    with fresh(prefix.with_suffix(".author.json")) as output:
        json.dump(body, output, indent=2, sort_keys=True)
        output.write("\n")
    qr = qr_image(body).resize((720, 720))
    image = Image.new("RGB", (1000, 1120), "#f3f0e9")
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 22, 978, 1098), outline="#101018", width=2)
    text(draw, (500, 52), "ZOE / SIGNED AUTHOR CERTIFICATE", 30, center=True)
    orbital(draw, (500, 132), 42)
    image.paste(qr, (140, 198))
    text(draw, (500, 944), body["document"][:48], 22, center=True)
    text(draw, (500, 988), f"SHA256 {body['sha256'][:24]}", 20, center=True)
    text(draw, (500, 1030), "Signature verifies key possession; author claims remain reviewable.", 17, center=True)
    image.save(prefix.with_suffix(".author.png"), optimize=True)
    return body


def verify_document(certificate_path, document_path):
    certificate = json.loads(Path(certificate_path).read_text(encoding="utf-8"))
    if certificate.get("protocol") != AUTHOR_PROTOCOL:
        raise ValueError("unsupported author certificate")
    signature = unb64(certificate.get("signature"))
    body = {key: value for key, value in certificate.items() if key != "signature"}
    public = Ed25519PublicKey.from_public_bytes(unb64(body["identity_key"]))
    try:
        public.verify(signature, canonical(body))
    except InvalidSignature as error:
        raise ValueError("author certificate signature is invalid") from error
    if fingerprint(public) != body["author_fingerprint"]:
        raise ValueError("author fingerprint does not match identity key")
    if document_hash(document_path) != body["sha256"]:
        raise ValueError("document hash differs from the signed bytes")
    if Path(document_path).name != body["document"]:
        raise ValueError("document name differs from the certificate")
    return {"verified": True, "author": body["author"], "sha256": body["sha256"]}


def main():
    parser = argparse.ArgumentParser(description="Zoe QR author certificates")
    commands = parser.add_subparsers(dest="command", required=True)
    sign = commands.add_parser("sign")
    sign.add_argument("--identity", type=Path, required=True)
    sign.add_argument("--document", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    sign.add_argument("--author", default=STATEMENT)
    sign.add_argument("--related-json", type=Path, help="bounded public metadata linking PDF/CMS/source artifacts")
    verify = commands.add_parser("verify")
    verify.add_argument("--certificate", type=Path, required=True)
    verify.add_argument("--document", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "sign":
        related = json.loads(args.related_json.read_text(encoding="utf-8")) if args.related_json else None
        result = sign_document(args.identity, args.document, args.output, args.author, related=related)
    else:
        result = verify_document(args.certificate, args.document)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

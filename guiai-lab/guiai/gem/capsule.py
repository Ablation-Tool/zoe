from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from .field import _canonical
from .patchbay import _bounded_path, _sha


FIELDS = {"schema_version", "instrument", "artifact", "target", "created_at", "algorithm", "public_key_sha256", "public_key_pem", "signature", "digest"}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _openssl(arguments, text=False):
    try:
        completed = subprocess.run(["openssl", *arguments], capture_output=True, text=text, timeout=10)
    except FileNotFoundError as error:
        raise RuntimeError("OpenSSL is required for Patchbay update capsules") from error
    if completed.returncode:
        error_output = completed.stderr if text else completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenSSL operation failed: {error_output[-2000:]}")
    return completed.stdout


def _public_material(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("public key must be a small PEM file")
    pem = path.read_text(encoding="ascii")
    if not pem.startswith("-----BEGIN PUBLIC KEY-----"):
        raise ValueError("trusted key must be a PEM public key, not a private key")
    der = _openssl(["pkey", "-pubin", "-in", str(path), "-outform", "DER"])
    return pem, hashlib.sha256(der).hexdigest()


def _timestamp(value=None):
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("capsule timestamp must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("capsule timestamp must include a timezone")
    return value


def _signed_fields(document):
    return {key: document[key] for key in ("schema_version", "instrument", "artifact", "target", "created_at", "algorithm", "public_key_sha256")}


def _validate_document(document):
    if not isinstance(document, dict) or set(document) != FIELDS or document.get("schema_version") != 1 or document.get("instrument") != "zoe-patchbay-capsule" or document.get("algorithm") != "Ed25519":
        raise ValueError("unsupported Patchbay capsule")
    if _digest({key: value for key, value in document.items() if key != "digest"}) != document["digest"]:
        raise ValueError("Patchbay capsule digest mismatch")
    artifact = document["artifact"]
    if not isinstance(artifact, dict) or set(artifact) != {"name", "sha256", "size"}:
        raise ValueError("invalid capsule artifact metadata")
    if not isinstance(artifact["name"], str) or not 1 <= len(artifact["name"]) <= 512 or not isinstance(artifact["sha256"], str) or len(artifact["sha256"]) != 64 or any(character not in "0123456789abcdef" for character in artifact["sha256"]):
        raise ValueError("invalid capsule artifact identity")
    if isinstance(artifact["size"], bool) or not isinstance(artifact["size"], int) or not 1 <= artifact["size"] <= 512 * 1024 * 1024:
        raise ValueError("invalid capsule artifact size")
    if not isinstance(document["target"], str) or not 1 <= len(document["target"]) <= 128:
        raise ValueError("capsule target must contain 1-128 characters")
    _timestamp(document["created_at"])
    if not isinstance(document["public_key_pem"], str) or len(document["public_key_pem"]) > 4096:
        raise ValueError("invalid capsule public key")
    try:
        signature = base64.b64decode(document["signature"], validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("invalid capsule signature encoding") from error
    if len(signature) != 64:
        raise ValueError("Ed25519 signature must contain 64 bytes")
    return signature


def _sign(payload, private_key):
    with tempfile.TemporaryDirectory(prefix="zoe-capsule-sign-") as directory:
        source = Path(directory) / "payload.json"
        signature = Path(directory) / "signature.bin"
        source.write_bytes(payload)
        _openssl(["pkeyutl", "-sign", "-rawin", "-inkey", str(private_key), "-in", str(source), "-out", str(signature)])
        return signature.read_bytes()


def _verify(payload, signature, public_pem):
    with tempfile.TemporaryDirectory(prefix="zoe-capsule-verify-") as directory:
        source = Path(directory) / "payload.json"
        signature_path = Path(directory) / "signature.bin"
        public_path = Path(directory) / "public.pem"
        source.write_bytes(payload)
        signature_path.write_bytes(signature)
        public_path.write_text(public_pem, encoding="ascii")
        completed = subprocess.run(["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(public_path), "-sigfile", str(signature_path), "-in", str(source)], capture_output=True, timeout=10)
        if completed.returncode not in {0, 1}:
            raise RuntimeError(f"OpenSSL verification failed: {completed.stderr.decode('utf-8', errors='replace')[-2000:]}")
        return completed.returncode == 0


def generate_keypair(private_path, public_path):
    private_path, public_path = Path(private_path), Path(public_path)
    for path in (private_path, public_path):
        if path.suffix.lower() != ".pem" or path.exists():
            raise ValueError("new key paths must be nonexistent .pem files")
        if not path.parent.is_dir():
            raise ValueError("key directory does not exist")
    try:
        _openssl(["genpkey", "-algorithm", "ED25519", "-out", str(private_path)])
        private_path.chmod(0o600)
        _openssl(["pkey", "-in", str(private_path), "-pubout", "-out", str(public_path)])
    except Exception:
        private_path.unlink(missing_ok=True)
        public_path.unlink(missing_ok=True)
        raise
    _, fingerprint = _public_material(public_path)
    return private_path, public_path, fingerprint


def sign_capsule(artifact, private_key, public_key, target, output, created_at=None):
    artifact, size = _bounded_path(artifact, 512 * 1024 * 1024)
    if not isinstance(target, str) or not 1 <= len(target) <= 128:
        raise ValueError("capsule target must contain 1-128 characters")
    public_pem, fingerprint = _public_material(public_key)
    private_der = _openssl(["pkey", "-in", str(private_key), "-pubout", "-outform", "DER"])
    if hashlib.sha256(private_der).hexdigest() != fingerprint:
        raise ValueError("private and public keys do not form a pair")
    document = {
        "schema_version": 1,
        "instrument": "zoe-patchbay-capsule",
        "artifact": {"name": artifact.name, "sha256": _sha(artifact), "size": size},
        "target": target,
        "created_at": _timestamp(created_at),
        "algorithm": "Ed25519",
        "public_key_sha256": fingerprint,
    }
    signature = _sign(_canonical(_signed_fields(document)).encode("utf-8"), private_key)
    document.update({"public_key_pem": public_pem, "signature": base64.b64encode(signature).decode("ascii")})
    document["digest"] = _digest(document)
    output = Path(output)
    if output.suffix.lower() != ".json":
        raise ValueError("update capsules must use a .json path")
    with output.open("x", encoding="utf-8") as stream:
        stream.write(_canonical(document) + "\n")
    return output, verify_capsule(output, artifact, public_key)


def verify_capsule(path, artifact=None, trusted_key=None):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("capsule exceeds 1 MiB")
    document = json.loads(path.read_text(encoding="utf-8"))
    signature = _validate_document(document)
    public_pem, fingerprint = _public_material_text(document["public_key_pem"])
    if fingerprint != document["public_key_sha256"]:
        raise ValueError("capsule public key fingerprint mismatch")
    signature_valid = _verify(_canonical(_signed_fields(document)).encode("utf-8"), signature, public_pem)
    artifact_match = None
    if artifact is not None:
        artifact, size = _bounded_path(artifact, 512 * 1024 * 1024)
        artifact_match = size == document["artifact"]["size"] and _sha(artifact) == document["artifact"]["sha256"]
    trusted_match = None if trusted_key is None else _public_material(trusted_key)[1] == fingerprint
    authenticity = signature_valid and artifact_match is True and trusted_match is True
    return {
        "instrument": "zoe-patchbay-capsule-verification",
        "capsule": str(path),
        "artifact": document["artifact"],
        "target": document["target"],
        "signature_valid": signature_valid,
        "artifact_match": artifact_match,
        "trusted_key_match": trusted_match,
        "trust_scope": "explicit-trusted-key" if trusted_match else "self-contained-key-only",
        "authenticity_established": authenticity,
        "hardware_accessed": False,
        "command_executed": False,
        "summary": f"signature_valid={signature_valid} · artifact_match={artifact_match} · trusted_key_match={trusted_match}\nAuthenticity established: {authenticity}. No hardware command was executed.",
    }


def _public_material_text(pem):
    with tempfile.TemporaryDirectory(prefix="zoe-capsule-public-") as directory:
        path = Path(directory) / "public.pem"
        path.write_text(pem, encoding="ascii")
        return _public_material(path)

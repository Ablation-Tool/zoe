from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
from urllib.parse import urlsplit
import zipfile

from .evidence import save_evidence_report
from .field import _canonical
from .patchbay import _bounded_path, _sha


MAX_ARCHIVE_MEMBERS = 4096
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finalize(report):
    report["digest"] = _digest({key: value for key, value in report.items() if key != "digest"})
    return report


def _source_url(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError("historical source URL must be bounded text")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("historical source URL must be HTTPS without credentials")
    return value


def _mz_details(data):
    if len(data) < 28:
        raise ValueError("MZ header is truncated")
    fields = struct.unpack_from("<13H", data, 2)
    header_bytes = fields[3] * 16
    if not 28 <= header_bytes <= len(data):
        raise ValueError("MZ header size is outside the artifact")
    declared_size = fields[1] * 512 if fields[0] == 0 else (fields[1] - 1) * 512 + fields[0]
    return {
        "signature": "MZ",
        "last_page_bytes": fields[0],
        "pages": fields[1],
        "declared_size": declared_size,
        "declared_size_matches": declared_size == len(data),
        "relocation_count": fields[2],
        "header_paragraphs": fields[3],
        "header_bytes": header_bytes,
        "minimum_allocation": fields[4],
        "maximum_allocation": fields[5],
        "initial_ss": fields[6],
        "initial_sp": fields[7],
        "checksum": fields[8],
        "entry_ip": fields[9],
        "entry_cs": fields[10],
        "entry_linear": fields[10] * 16 + fields[9],
        "relocation_table_offset": fields[11],
        "overlay": fields[12],
        "entry_executed": False,
    }


def _zip_details(path):
    members = []
    directories = 0
    total_bytes = 0
    seen = set()
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_MEMBERS:
            raise ValueError(f"historical archive exceeds {MAX_ARCHIVE_MEMBERS} entries")
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            if relative.is_absolute() or ".." in relative.parts or "\\" in entry.filename or entry.filename in seen:
                raise ValueError("historical archive has an unsafe or duplicate member path")
            seen.add(entry.filename)
            if entry.is_dir():
                directories += 1
                continue
            if not 0 <= entry.file_size <= MAX_MEMBER_BYTES:
                raise ValueError(f"historical archive member exceeds {MAX_MEMBER_BYTES} bytes")
            total_bytes += entry.file_size
            if total_bytes > MAX_ARCHIVE_BYTES:
                raise ValueError(f"historical archive exceeds {MAX_ARCHIVE_BYTES} uncompressed bytes")
            digest = hashlib.sha256()
            with archive.open(entry, "r") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            members.append({
                "name": entry.filename,
                "bytes": entry.file_size,
                "compressed_bytes": entry.compress_size,
                "sha256": digest.hexdigest(),
                "crc32": f"{entry.CRC:08x}",
                "crc_is_integrity_not_signature": True,
            })
    return {
        "member_count": len(entries),
        "file_count": len(members),
        "directory_count": directories,
        "uncompressed_bytes": total_bytes,
        "members": members,
        "contents_extracted": False,
    }


def inspect_reference(path, source_url=None):
    path, size = _bounded_path(path)
    path = path.resolve()
    data = path.read_bytes()
    report = {
        "schema_version": 1,
        "instrument": "zoe-pentacube-historical-reference",
        "source_path": str(path),
        "source_url": _source_url(source_url),
        "bytes": size,
        "sha256": _sha(path),
        "source_bundled": False,
        "source_text_bundled": False,
        "payloads_executed": False,
        "hardware_accessed": False,
        "runtime_verified": False,
        "firmware_identified": False,
        "license_determined": False,
        "endorsement_claimed": False,
        "scope": "Read-only historical artifact identification and inventory; no execution, firmware validation, or historical-game compatibility claim.",
    }
    if data.startswith(b"MZ"):
        report["kind"] = "dos-mz-executable"
        report["format"] = _mz_details(data)
    elif data.startswith(b"%PDF-"):
        report["kind"] = "pdf-document"
        report["format"] = {"version": data[5:8].decode("ascii", errors="replace"), "page_tree_verified": False}
    elif zipfile.is_zipfile(path):
        report["kind"] = "zip-archive"
        report["format"] = _zip_details(path)
    else:
        report["kind"] = "binary-artifact"
        report["format"] = {"signature_hex": data[:16].hex(), "signature_is_identity": False}
    return _finalize(report)


def save_reference_report(report, path):
    if report.get("digest") != _digest({key: value for key, value in report.items() if key != "digest"}):
        raise ValueError("historical reference digest mismatch")
    return save_evidence_report(report, path)


def load_reference_report(path, verify_source=True):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= MAX_REPORT_BYTES:
        raise ValueError("historical reference report is missing or exceeds 4 MiB")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("instrument") != "zoe-pentacube-historical-reference":
        raise ValueError("unsupported historical reference report")
    if report.get("digest") != _digest({key: value for key, value in report.items() if key != "digest"}):
        raise ValueError("historical reference digest mismatch")
    for field in ("source_bundled", "source_text_bundled", "payloads_executed", "hardware_accessed", "runtime_verified", "firmware_identified", "license_determined", "endorsement_claimed"):
        if report.get(field) is not False:
            raise ValueError(f"historical reference boundary changed: {field}")
    if verify_source:
        source = Path(report["source_path"])
        if not source.is_file() or source.stat().st_size != report["bytes"] or _sha(source) != report["sha256"]:
            raise ValueError("historical reference source hash mismatch")
    return report

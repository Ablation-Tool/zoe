from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Callable, Iterable


SCHEMA_VERSION = 1
DEFAULT_CERN_ROOT = Path("/media/cowboy/research/CERN")
_HASH_CHUNK = 4 * 1024 * 1024
_SECRET_NAMES = {
    ".env", ".netrc", ".pgpass", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "credentials.json", "secrets.json",
}

_FAMILY_EXTENSIONS = {
    "hdl": {".v", ".sv", ".vhd", ".vhdl", ".vho", ".do", ".xdc", ".ucf", ".xci", ".bd"},
    "c_cpp": {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"},
    "python": {".py"},
    "javascript": {".js", ".mjs", ".cjs", ".ts", ".tsx"},
    "shell": {".sh", ".bash", ".tcl"},
    "build_config": {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".mk", ".cmake"},
    "archive": {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".rar", ".7z"},
    "document": {".pdf", ".md", ".txt", ".html", ".htm", ".tex", ".ppt", ".pptx", ".doc", ".docx", ".rst"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".tif", ".tiff"},
    "fpga_image": {".bit", ".mcs", ".pdi", ".cdo", ".rbt", ".bin", ".mem", ".hex"},
    "waveform": {".vcd", ".wdb", ".fst", ".ghw"},
    "disk_image": {".qcow2", ".vmdk", ".vdi", ".img", ".raw", ".ext4", ".sqfs"},
    "source_data": {".csv", ".jsonl", ".dat", ".data", ".xml", ".nrrd", ".npz"},
}

_DISPOSITIONS = {
    "hdl": "compile_review_repair_and_equivalence_test",
    "c_cpp": "forge_build_debug_and_regression_test",
    "python": "forge_debug_and_regression_test",
    "javascript": "forge_trace_and_modernize",
    "shell": "forge_shellcheck_and_sandbox_test",
    "build_config": "validate_schema_and_reproduce_build",
    "archive": "verify_integrity_inventory_members_and_deduplicate",
    "document": "extract_link_check_and_regenerate_accessibly",
    "image": "verify_lossless_optimization_and_provenance",
    "fpga_image": "parse_verify_compare_and_map_to_source",
    "waveform": "stream_verify_and_extract_timing_evidence",
    "disk_image": "inspect_read_only_and_map_contents",
    "source_data": "validate_schema_and_recompute_evidence",
    "other": "identify_then_assign_an_explicit_analysis_lane",
}


def family_for(path: Path) -> str:
    suffix = path.suffix.lower()
    for family, extensions in _FAMILY_EXTENSIONS.items():
        if suffix in extensions:
            return family
    return "other"


def disposition_for(family: str) -> str:
    return _DISPOSITIONS[family]


def _policy_excluded(path: Path) -> bool:
    lowered = path.name.lower()
    return (
        lowered in _SECRET_NAMES
        or lowered.startswith(".env.")
        or (lowered.endswith((".key", ".pem")) and "private" in lowered)
    )


def _sha256(path: Path, expected: tuple[int, int, int, int]) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        while chunk := stream.read(_HASH_CHUNK):
            digest.update(chunk)
    current = path.stat(follow_symlinks=False)
    identity = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
    if identity != expected:
        raise RuntimeError("file changed while it was being hashed")
    return digest.hexdigest()


@dataclass
class CorpusRecord:
    path: str
    kind: str
    size: int
    mtime_ns: int
    mode: str
    extension: str
    family: str
    disposition: str
    origin: str
    status: str
    sha256: str | None = None
    device: int | None = None
    inode: int | None = None
    link_target: str | None = None
    link_outside_root: bool | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        result = {
            "path": self.path,
            "kind": self.kind,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "mode": self.mode,
            "extension": self.extension,
            "family": self.family,
            "disposition": self.disposition,
            "origin": self.origin,
            "status": self.status,
            "sha256": self.sha256,
        }
        for name in ("device", "inode", "link_target", "link_outside_root", "error"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        return result

    @classmethod
    def from_dict(cls, value: dict) -> "CorpusRecord":
        return cls(**value)


def _record(path: Path, root: Path, relative: str) -> CorpusRecord:
    info = path.lstat()
    family = family_for(path)
    origin = "derived_analysis" if relative.split("/", 1)[0] == "analysis" else "original"
    common = {
        "path": relative,
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "mode": stat.filemode(info.st_mode),
        "extension": path.suffix.lower() or "<none>",
        "family": family,
        "disposition": disposition_for(family),
        "origin": origin,
    }
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        resolved = (path.parent / target).resolve(strict=False)
        return CorpusRecord(
            **common, kind="symlink", status="metadata_only_symlink",
            link_target=target,
            link_outside_root=resolved != root and root not in resolved.parents,
        )
    if stat.S_ISDIR(info.st_mode):
        return CorpusRecord(**common, kind="directory", status="metadata_only_directory")
    if not stat.S_ISREG(info.st_mode):
        return CorpusRecord(**common, kind="special", status="metadata_only_special")
    if _policy_excluded(path):
        return CorpusRecord(**common, kind="regular", status="metadata_only_policy")
    return CorpusRecord(
        **common, kind="regular", status="pending_hash",
        device=info.st_dev, inode=info.st_ino,
    )


def _walk(root: Path, excluded_output: Path | None) -> tuple[list[CorpusRecord], list[dict]]:
    records: list[CorpusRecord] = []
    errors: list[dict] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            errors.append({"path": str(directory.relative_to(root)), "error": str(error)})
            continue
        for entry in entries:
            path = Path(entry.path)
            resolved = path.resolve(strict=False)
            if excluded_output is not None and (resolved == excluded_output or excluded_output in resolved.parents):
                continue
            relative = path.relative_to(root).as_posix()
            try:
                record = _record(path, root, relative)
            except OSError as error:
                errors.append({"path": relative, "error": str(error)})
                continue
            records.append(record)
            if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                pending.append(path)
    records.sort(key=lambda record: record.path)
    return records, errors


def scan_corpus(
    root: str | Path,
    *,
    output: str | Path | None = None,
    workers: int = 1,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[list[CorpusRecord], dict]:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"CERN corpus is not a directory: {root}")
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 32:
        raise ValueError("workers must be an integer from 1 to 32")
    excluded_output = None
    if output is not None:
        excluded_output = Path(output).expanduser().resolve()
        if excluded_output == root:
            raise ValueError("manifest output must not replace the corpus root")
    records, walk_errors = _walk(root, excluded_output)
    pending = [record for record in records if record.status == "pending_hash"]
    expected = {
        record.path: (record.device, record.inode, record.size, record.mtime_ns)
        for record in pending
    }

    def hash_one(record: CorpusRecord) -> None:
        try:
            record.sha256 = _sha256(root / record.path, expected[record.path])
            record.status = "hashed"
        except (OSError, RuntimeError) as error:
            record.status = "error"
            record.error = str(error)

    completed = 0
    if workers == 1:
        for record in pending:
            hash_one(record)
            completed += 1
            if progress:
                progress(completed, len(pending), record.path)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(hash_one, pending)
            for record, _ in zip(pending, results):
                completed += 1
                if progress:
                    progress(completed, len(pending), record.path)
    summary = summarize_records(records, root)
    summary["walk_errors"] = walk_errors
    summary["coverage"]["errors"] += len(walk_errors)
    summary["coverage"]["complete_without_errors"] = (
        summary["coverage"]["errors"] == 0
        and summary["coverage"]["pending_hash"] == 0
    )
    return records, summary


def summarize_records(records: Iterable[CorpusRecord], root: str | Path) -> dict:
    rows = list(records)
    status = Counter(record.status for record in rows)
    families = Counter(record.family for record in rows)
    dispositions = Counter(record.disposition for record in rows)
    origins = Counter(record.origin for record in rows)
    extensions = Counter(record.extension for record in rows)
    errors = [record.to_dict() for record in rows if record.status == "error"]
    policy = [record.path for record in rows if record.status == "metadata_only_policy"]
    hashed = [record for record in rows if record.sha256]
    by_hash: dict[str, list[CorpusRecord]] = {}
    for record in hashed:
        by_hash.setdefault(record.sha256, []).append(record)
    duplicate_groups = []
    for digest, group in sorted(by_hash.items()):
        if len(group) < 2:
            continue
        paths = sorted(record.path for record in group)
        size = group[0].size
        duplicate_groups.append({
            "sha256": digest,
            "size": size,
            "copies": len(paths),
            "paths": paths,
            "logical_duplicate_bytes": size * (len(paths) - 1),
        })
    unique_hashes = len(by_hash)
    logical_bytes = sum(record.size for record in rows if record.kind == "regular")
    unique_bytes = sum(group[0].size for group in by_hash.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "instrument": "zoe-cern-corpus-manifest",
        "root": str(root),
        "artifact_count": len(rows),
        "file_count": sum(record.kind != "directory" for record in rows),
        "directory_count": sum(record.kind == "directory" for record in rows),
        "regular_file_count": sum(record.kind == "regular" for record in rows),
        "logical_bytes": logical_bytes,
        "unique_content_bytes": unique_bytes,
        "unique_content_count": unique_hashes,
        "families": dict(sorted(families.items())),
        "dispositions": dict(sorted(dispositions.items())),
        "origins": dict(sorted(origins.items())),
        "extensions": dict(sorted(extensions.items())),
        "coverage": {
            "hashed": status["hashed"],
            "pending_hash": status["pending_hash"],
            "errors": len(errors),
            "symlinks": status["metadata_only_symlink"],
            "directories": status["metadata_only_directory"],
            "special_files": status["metadata_only_special"],
            "policy_exclusions": len(policy),
            "complete_without_errors": not errors and not status["pending_hash"],
        },
        "duplicates": {
            "groups": len(duplicate_groups),
            "alias_paths": sum(group["copies"] - 1 for group in duplicate_groups),
            "logical_duplicate_bytes": sum(group["logical_duplicate_bytes"] for group in duplicate_groups),
        },
        "duplicate_groups": duplicate_groups,
        "policy_exclusions": policy,
        "errors": errors,
        "largest_files": [
            {"path": record.path, "size": record.size, "sha256": record.sha256}
            for record in sorted(rows, key=lambda row: (-row.size, row.path))[:25]
        ],
        "execution": "read-only corpus scan; no source artifact modified and no code executed",
    }


def write_corpus(records: Iterable[CorpusRecord], summary: dict, output: str | Path) -> Path:
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(f"corpus output directory must be new or empty: {output}")
    manifest = output / "manifest.jsonl"
    digest = hashlib.sha256()
    with manifest.open("xb") as stream:
        for record in sorted(records, key=lambda row: row.path):
            line = json.dumps(record.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n"
            encoded = line.encode("utf-8")
            stream.write(encoded)
            digest.update(encoded)
    summary = dict(summary)
    summary["manifest_sha256"] = digest.hexdigest()
    (output / "duplicates.json").write_text(
        json.dumps(summary["duplicate_groups"], ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def load_corpus(path: str | Path) -> tuple[list[CorpusRecord], dict]:
    path = Path(path).expanduser().resolve()
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if summary.get("schema_version") != SCHEMA_VERSION or summary.get("instrument") != "zoe-cern-corpus-manifest":
        raise ValueError("unsupported CERN corpus summary")
    digest = hashlib.sha256()
    with (path / "manifest.jsonl").open("rb") as stream:
        for line in stream:
            digest.update(line)
    if digest.hexdigest() != summary.get("manifest_sha256"):
        raise ValueError("CERN corpus manifest hash mismatch")
    records = []
    with (path / "manifest.jsonl").open("rb") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                records.append(CorpusRecord.from_dict(json.loads(line)))
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(f"invalid manifest record at line {line_number}: {error}") from error
    if len(records) != summary["artifact_count"]:
        raise ValueError("CERN corpus manifest count mismatch")
    return records, summary


def forge_summary(path: str | Path) -> dict:
    path = Path(path).expanduser().resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("mode") != "source" or not isinstance(value.get("findings"), list):
        raise ValueError("not a FORGE source-audit JSON report")
    severities = Counter(finding.get("severity", "UNKNOWN") for finding in value["findings"])
    return {
        "path": str(path),
        "gate_passed": bool(value.get("gate_passed")),
        "finding_count": len(value["findings"]),
        "severities": dict(sorted(severities.items())),
        "summary": value.get("summary", ""),
        "scope_note": "FORGE SourceContext-supported path entries only; aliases and unsupported HDL/C/C++/binary/document lanes remain explicit in the corpus manifest.",
    }

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import tempfile
from urllib.parse import parse_qs, urlsplit

from .atlas import _line, _scene, _text
from .evidence import save_evidence_report
from .field import _canonical
from .geometry import verify
from .patchbay import _sha
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"})
MAX_QUERY = 256
MAX_SNIPPET = 360
MAX_OUTPUT = 8192
MAX_TRANSCRIPTS = 4096
MAX_TRANSCRIPT_BYTES = 4 * 1024 * 1024
MAX_REPORT_BYTES = 2 * 1024 * 1024
PROVENANCE = {
    "name": "vidlib",
    "created_by": "Nicholas Michael Kloster",
    "created_with": "Claude Code",
    "integration": "Zoe invokes the original executable; it does not replace or rename vidlib",
}
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finalize(report):
    document = {key: value for key, value in report.items() if key != "digest"}
    document["digest"] = _digest(document)
    return document


def _limit(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 64:
        raise ValueError("vidlib result limit must be between 1 and 64")
    return value


def _timeout(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 3600:
        raise ValueError("vidlib timeout must be between 1 and 3600 seconds")
    return value


def validate_youtube_url(url, playlist=False):
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        raise ValueError("a bounded YouTube URL is required")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in YOUTUBE_HOSTS:
        raise ValueError("vidlib retrieval requires HTTPS on an allowed YouTube host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("vidlib retrieval URLs cannot contain credentials")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("invalid YouTube URL port") from error
    if port not in {None, 443}:
        raise ValueError("vidlib retrieval only permits the default HTTPS port")
    if not parsed.path or parsed.path == "/" and not parse_qs(parsed.query).get("list"):
        raise ValueError("YouTube URL must identify a video or playlist")
    has_playlist = bool(parse_qs(parsed.query).get("list")) or parsed.path == "/playlist"
    if has_playlist and not playlist:
        raise ValueError("playlist URLs require the explicit --playlist flag")
    if playlist and not has_playlist:
        raise ValueError("--playlist requires a YouTube playlist URL")
    return url


def _tool_metadata(executable="vidlib", required=True):
    if not isinstance(executable, (str, os.PathLike)) or not str(executable):
        raise ValueError("vidlib executable must be a nonempty command or path")
    resolved = shutil.which(str(executable))
    if resolved is None:
        if required:
            raise FileNotFoundError(f"vidlib executable not found: {executable}")
        return {**PROVENANCE, "available": False, "executable": str(executable)}
    path = Path(resolved).resolve()
    result = {
        **PROVENANCE,
        "available": True,
        "executable": str(executable),
        "executable_path": str(path),
        "executable_sha256": _sha(path),
    }
    implementation = path.with_suffix(".py")
    if implementation.is_file():
        result["implementation_path"] = str(implementation)
        result["implementation_sha256"] = _sha(implementation)
    return result


def _read_bounded(stream):
    data = stream.read(MAX_OUTPUT + 1)
    return data[:MAX_OUTPUT].decode("utf-8", errors="replace"), len(data) > MAX_OUTPUT


def _invoke(command, timeout):
    timed_out = False
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=os.name == "posix",
        )
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            returncode = 124
            process.wait()
        stdout.seek(0)
        stderr.seek(0)
        out, out_truncated = _read_bounded(stdout)
        error, error_truncated = _read_bounded(stderr)
    if timed_out:
        error = f"vidlib adapter: timed out after {timeout} seconds\n{error}"[:MAX_OUTPUT]
    return {
        "command": list(command),
        "returncode": returncode,
        "stdout": out,
        "stdout_truncated": out_truncated,
        "stderr": error,
        "stderr_truncated": error_truncated,
        "timed_out": timed_out,
    }


def _frontmatter(text, fallback_title, fallback_channel):
    metadata = {}
    lines = text.splitlines()
    if lines and lines[0] == "---":
        for line in lines[1:65]:
            if line == "---":
                break
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            if key in {"title", "channel", "date", "url", "duration", "reading_time", "pulled"}:
                metadata[key] = value.strip().strip('"')
    title = metadata.get("title", fallback_title)
    channel = metadata.get("channel", fallback_channel)
    for label, value, maximum in (
        ("title", title, 512), ("channel", channel, 512),
        ("source URL", metadata.get("url", ""), 2048),
        ("relative path", fallback_title, 512),
    ):
        if len(value) > maximum:
            raise ValueError(f"vidlib transcript {label} exceeds its report bound")
    return {
        "title": title,
        "channel": channel,
        "date": metadata.get("date", "")[:128],
        "duration": metadata.get("duration", "")[:128],
        "reading_time": metadata.get("reading_time", "")[:128],
        "transcript_pulled": metadata.get("pulled", "")[:128],
        "source_url": metadata.get("url", ""),
    }


def _snippet(text, query):
    if query is None:
        return "", True
    match = re.search(re.escape(query), text, re.IGNORECASE)
    if match is None:
        return "", False
    start = max(0, match.start() - 100)
    end = min(len(text), match.end() + 220)
    excerpt = " ".join(text[start:end].split())
    if len(excerpt) > MAX_SNIPPET:
        excerpt = excerpt[:MAX_SNIPPET - 1].rstrip() + "…"
    return excerpt, True


class VideoLibrary:
    def __init__(self, library, executable="vidlib", limit=16, timeout=300):
        self.root = Path(library).expanduser().resolve()
        self.executable = str(executable)
        self.limit = _limit(limit)
        self.timeout = _timeout(timeout)
        if self.root.exists() and not self.root.is_dir():
            raise ValueError("vidlib library must be a directory")

    def _base(self, operation, tool):
        return {
            "schema_version": 1,
            "instrument": "zoe-vidlib-evidence",
            "operation": operation,
            "status": "pending",
            "tool": tool,
            "library": {
                "path": str(self.root),
                "exists": self.root.is_dir(),
                "transcript_count": 0,
                "index_path": str(self.root / "index.md"),
                "index_present": False,
                "index_sha256": None,
            },
            "query": None,
            "vidlib_invoked": False,
            "network_requested": operation == "fetch",
            "network_attempted": False,
            "remote_fetch_succeeded": False,
            "transcript_downloaded": False,
            "download_detection": "new or changed transcript Markdown after an explicit fetch",
            "executed": False,
            "library_changed": False,
            "changed_sources": [],
            "changed_count": 0,
            "results": [],
            "returned_count": 0,
            "total_matches": 0,
            "source_hashes_verified": False,
            "source_text_bundled": False,
            "synthetic_example": False,
            "evidence_level": "transcript-reference",
            "measurement": False,
            "hardware_evidence": False,
            "hardware_accessed": False,
            "llm_called": False,
            "action_authorized": False,
            "limits": {
                "results": self.limit,
                "snippet_characters": MAX_SNIPPET,
                "process_output_bytes": MAX_OUTPUT,
                "transcript_bytes": MAX_TRANSCRIPT_BYTES,
                "library_transcripts": MAX_TRANSCRIPTS,
            },
        }

    def _missing(self, operation):
        report = self._base(operation, _tool_metadata(self.executable, required=False))
        report.update({
            "status": "missing-library",
            "returncode": 0,
            "command": [],
            "stdout": "",
            "stdout_truncated": False,
            "stderr": "",
            "stderr_truncated": False,
            "timed_out": False,
            "message": "Library does not exist; nothing was created, indexed, searched, or downloaded.",
        })
        return _finalize(report)

    def _paths(self):
        if not self.root.is_dir():
            return []
        paths = []
        for path in self.root.rglob("*.md"):
            if path.name == "index.md" or not path.is_file():
                continue
            if not path.resolve().is_relative_to(self.root):
                raise ValueError("vidlib transcript resolves outside its library")
            paths.append(path)
            if len(paths) > MAX_TRANSCRIPTS:
                raise ValueError(f"vidlib library exceeds {MAX_TRANSCRIPTS} transcripts")
        return sorted(paths, key=lambda path: path.relative_to(self.root).as_posix())

    def _index_hash(self):
        path = self.root / "index.md"
        if not path.is_file():
            return None
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("vidlib index resolves outside its library")
        return _sha(path)

    def _scan(self, query=None):
        records = []
        matches = []
        for path in self._paths():
            with path.open("rb") as stream:
                data = stream.read(MAX_TRANSCRIPT_BYTES + 1)
            size = len(data)
            if not 1 <= size <= MAX_TRANSCRIPT_BYTES:
                raise ValueError(f"vidlib transcript must contain 1 byte to {MAX_TRANSCRIPT_BYTES} bytes: {path}")
            text = data.decode("utf-8")
            relative = path.relative_to(self.root).as_posix()
            excerpt, matched = _snippet(text, query)
            record = {
                **_frontmatter(text, path.stem, path.parent.name),
                "relative_path": relative,
                "source_path": str(path),
                "source_sha256": hashlib.sha256(data).hexdigest(),
                "bytes": size,
                "snippet": excerpt,
                "source_hashes_verified": True,
                "source_text_bundled": False,
                "evidence_level": "transcript-reference",
            }
            records.append(record)
            if matched:
                matches.append(record)
        return records, matches, self._index_hash()

    @staticmethod
    def _snapshot(records, index_hash):
        return {
            "transcripts": {record["relative_path"]: record["source_sha256"] for record in records},
            "index": index_hash,
        }

    def _execute(self, operation, query=None, url=None, playlist=False):
        if operation in {"search", "index"} and not self.root.is_dir():
            report = self._missing(operation)
            report["query"] = query
            return _finalize(report)
        before_records, _before_matches, before_index = self._scan()
        before = self._snapshot(before_records, before_index)
        tool = _tool_metadata(self.executable)
        command = [tool["executable_path"], "--out", str(self.root)]
        if operation == "search":
            command.extend(("--search", query, "--quiet"))
        elif operation == "index":
            command.append("--index")
        else:
            command.append(url)
            if playlist:
                command.append("--playlist")
        report = self._base(operation, tool)
        report["query"] = query
        report["source_url"] = url
        report["playlist"] = playlist
        report.update(_invoke(command, self.timeout))
        report["vidlib_invoked"] = True
        report["network_attempted"] = operation == "fetch"
        after_records, matches, after_index = self._scan(query if operation == "search" else None)
        after = self._snapshot(after_records, after_index)
        changed = sorted(
            path for path, digest in after["transcripts"].items()
            if before["transcripts"].get(path) != digest
        )
        removed = sorted(set(before["transcripts"]) - set(after["transcripts"]))
        report["library_changed"] = before != after
        report["changed_sources"] = changed[:64]
        report["changed_count"] = len(changed)
        report["removed_sources"] = removed[:64]
        report["removed_count"] = len(removed)
        report["executed"] = operation in {"index", "fetch"} or report["library_changed"]
        report["remote_fetch_succeeded"] = operation == "fetch" and report["returncode"] == 0
        report["transcript_downloaded"] = operation == "fetch" and bool(changed)
        if operation == "search":
            selected = matches
        elif operation == "index":
            selected = after_records
        elif changed:
            selected = [record for record in after_records if record["relative_path"] in changed]
        else:
            selected = [record for record in after_records if record["source_url"] == url]
        report["results"] = selected[:self.limit]
        report["returned_count"] = len(report["results"])
        report["total_matches"] = len(selected)
        report["source_hashes_verified"] = True
        report["library"] = {
            "path": str(self.root),
            "exists": self.root.is_dir(),
            "transcript_count": len(after_records),
            "index_path": str(self.root / "index.md"),
            "index_present": after_index is not None,
            "index_sha256": after_index,
        }
        report["status"] = "timed-out" if report["timed_out"] else "ok" if report["returncode"] == 0 else "command-failed"
        return _finalize(report)

    def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query) <= MAX_QUERY or not query.strip():
            raise ValueError(f"vidlib search requires 1 to {MAX_QUERY} nonblank characters")
        return self._execute("search", query=query)

    def rebuild_index(self):
        return self._execute("index")

    def fetch(self, url, playlist=False):
        validate_youtube_url(url, playlist)
        return self._execute("fetch", url=url, playlist=playlist)


def _source_from_report(report, record):
    relative = PurePosixPath(record["relative_path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in record["relative_path"]:
        raise ValueError("vidlib report source escapes its library")
    root = Path(report["library"]["path"])
    source = root.joinpath(*relative.parts)
    if not source.resolve().is_relative_to(root.resolve()):
        raise ValueError("vidlib report source escapes its library")
    if Path(record["source_path"]).resolve() != source.resolve():
        raise ValueError("vidlib report source path disagrees with its relative path")
    return source


def load_video_report(path, verify_sources=True):
    path = Path(path)
    if not path.is_file() or not 1 <= path.stat().st_size <= MAX_REPORT_BYTES:
        raise ValueError("vidlib report is missing or exceeds its size bound")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("instrument") != "zoe-vidlib-evidence":
        raise ValueError("unsupported vidlib evidence report")
    if not isinstance(report.get("digest"), str) or not DIGEST.fullmatch(report["digest"]):
        raise ValueError("invalid vidlib report digest")
    if _finalize(report)["digest"] != report["digest"]:
        raise ValueError("vidlib report digest mismatch")
    if report.get("operation") not in {"search", "index", "fetch"}:
        raise ValueError("invalid vidlib report operation")
    for field in ("source_text_bundled", "measurement", "hardware_evidence", "hardware_accessed", "llm_called", "action_authorized"):
        if report.get(field) is not False:
            raise ValueError(f"vidlib report boundary changed: {field}")
    results = report.get("results")
    if not isinstance(results, list) or len(results) > 64 or report.get("returned_count") != len(results):
        raise ValueError("invalid vidlib report results")
    required = {"title", "channel", "source_url", "relative_path", "source_path", "source_sha256", "bytes", "snippet"}
    for record in results:
        if not isinstance(record, dict) or not required <= set(record):
            raise ValueError("invalid vidlib citation")
        if not isinstance(record["source_sha256"], str) or not DIGEST.fullmatch(record["source_sha256"]):
            raise ValueError("invalid vidlib source digest")
        if not isinstance(record["snippet"], str) or len(record["snippet"]) > MAX_SNIPPET:
            raise ValueError("invalid vidlib citation snippet")
        source = _source_from_report(report, record)
        if verify_sources:
            if report.get("synthetic_example"):
                raise ValueError("worked-example citations have no physical source to verify")
            if not source.is_file() or _sha(source) != record["source_sha256"]:
                raise ValueError(f"vidlib source hash mismatch: {record['relative_path']}")
    for field, maximum in (("stdout", MAX_OUTPUT), ("stderr", MAX_OUTPUT)):
        if not isinstance(report.get(field), str) or len(report[field]) > maximum:
            raise ValueError(f"invalid vidlib bounded {field}")
    if verify_sources and report["library"].get("index_sha256") is not None:
        index = Path(report["library"]["index_path"])
        if not index.is_file() or _sha(index) != report["library"]["index_sha256"]:
            raise ValueError("vidlib index hash mismatch")
    return report


def save_video_report(report, path):
    load_data = json.loads(_canonical(report))
    if _finalize(load_data)["digest"] != report.get("digest"):
        raise ValueError("vidlib report digest mismatch")
    return save_evidence_report(load_data, path)


def worked_video_report():
    source_sha256 = hashlib.sha256(b"Synthetic transcript citation only; no source text is bundled.\n").hexdigest()
    report = {
        "schema_version": 1,
        "instrument": "zoe-vidlib-evidence",
        "operation": "search",
        "status": "worked-example",
        "tool": {**PROVENANCE, "available": None, "executable": "vidlib"},
        "library": {
            "path": "/example/vidlib", "exists": False, "transcript_count": 1,
            "index_path": "/example/vidlib/index.md", "index_present": True,
            "index_sha256": None,
        },
        "query": "timing",
        "source_url": None,
        "playlist": False,
        "vidlib_invoked": False,
        "network_requested": False,
        "network_attempted": False,
        "remote_fetch_succeeded": False,
        "transcript_downloaded": False,
        "download_detection": "worked example; no download occurred",
        "executed": False,
        "library_changed": False,
        "changed_sources": [],
        "changed_count": 0,
        "removed_sources": [],
        "removed_count": 0,
        "command": [],
        "returncode": 0,
        "stdout": "",
        "stdout_truncated": False,
        "stderr": "",
        "stderr_truncated": False,
        "timed_out": False,
        "results": [{
            "title": "A worked transcript citation",
            "channel": "Synthetic reference",
            "date": "unknown",
            "duration": "unknown",
            "reading_time": "1 min read",
            "transcript_pulled": "unknown",
            "source_url": "",
            "relative_path": "synthetic-reference/worked-transcript.md",
            "source_path": "/example/vidlib/synthetic-reference/worked-transcript.md",
            "source_sha256": source_sha256,
            "bytes": 63,
            "snippet": "Timing is a reference topic here, not a hardware measurement.",
            "source_hashes_verified": False,
            "source_text_bundled": False,
            "evidence_level": "synthetic-transcript-citation",
        }],
        "returned_count": 1,
        "total_matches": 1,
        "source_hashes_verified": False,
        "source_text_bundled": False,
        "synthetic_example": True,
        "evidence_level": "transcript-reference",
        "measurement": False,
        "hardware_evidence": False,
        "hardware_accessed": False,
        "llm_called": False,
        "action_authorized": False,
        "limits": {
            "results": 16, "snippet_characters": MAX_SNIPPET,
            "process_output_bytes": MAX_OUTPUT, "transcript_bytes": MAX_TRANSCRIPT_BYTES,
            "library_transcripts": MAX_TRANSCRIPTS,
        },
        "message": "Synthetic citation shape; vidlib was not invoked and no transcript is bundled.",
    }
    return _finalize(report)


def video_library_scene(report=None):
    import textwrap

    report = report or worked_video_report()
    if _finalize(report)["digest"] != report.get("digest"):
        raise ValueError("vidlib report digest mismatch")
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#0b1220", "fill": "#0b1220", "width": 1}]
    objects.extend([
        _text("title", [44, 57], "Zoe + vidlib", 31, "#67e8f9"),
        _text("subtitle", [46, 86], "Original transcript library · cited reference retrieval", 15, "#9fb1c8"),
        _text("attribution", [46, 113], "vidlib by Nicholas Michael Kloster · created with Claude Code", 12, "#e7d6ad"),
    ])
    stages = [
        (45, 190, "1 · Explicit mode", "search / index / fetch"),
        (280, 190, "2 · Original vidlib", "the existing CLI"),
        (515, 190, "3 · Markdown library", "channel / title"),
        (750, 205, "4 · Zoe citations", "hash + bounded excerpt"),
    ]
    for index, (x, width, title, detail) in enumerate(stages):
        color = ("#94a3b8", "#e7d6ad", "#c4b5fd", "#67e8f9")[index]
        objects.append({"id": f"stage-{index}", "type": "rectangle", "bounds": [x, 150, x + width, 238], "stroke": color, "fill": "#111d30", "width": 1})
        objects.append(_text(f"stage-title-{index}", [x + 12, 183], title, 14, color))
        objects.append(_text(f"stage-detail-{index}", [x + 12, 215], detail, 11, "#dbeafe"))
        if index < 3:
            following = stages[index + 1][0]
            objects.append(_line(f"stage-link-{index}", [x + width + 8, 194], [following - 8, 194], "#64748b", 2))
            objects.append(_line(f"stage-arrow-a-{index}", [following - 15, 188], [following - 8, 194], "#64748b", 2))
            objects.append(_line(f"stage-arrow-b-{index}", [following - 15, 200], [following - 8, 194], "#64748b", 2))
    objects.extend([
        _text("operation", [45, 282], f"{report['operation'].upper()} · {report['status']}", 19, "#a7f3d0"),
        _text("operation-flags", [46, 309], f"vidlib_invoked={report['vidlib_invoked']} · network_attempted={report['network_attempted']} · executed={report['executed']}", 12, "#9fb1c8"),
        {"id": "citation-panel", "type": "rectangle", "bounds": [45, 340, 955, 617], "stroke": "#475569", "fill": "#0f1929", "width": 1},
        _text("citation-title", [61, 371], f"Cited references · {report['returned_count']} shown / {report['total_matches']} matched", 16, "#67e8f9"),
    ])
    for index, record in enumerate(report["results"][:3]):
        top = 407 + index * 68
        objects.append(_text(f"citation-name-{index}", [62, top], record["title"][:62], 14, "#e7d6ad"))
        objects.append(_text(f"citation-source-{index}", [62, top + 22], f"{record['channel'][:36]} · {record['relative_path'][:58]}", 10, "#9fb1c8"))
        excerpt = textwrap.wrap(record["snippet"], 104)
        objects.append(_text(f"citation-excerpt-{index}", [62, top + 43], excerpt[0] if excerpt else "Library citation; no search excerpt requested.", 10, "#dbeafe"))
    if not report["results"]:
        objects.append(_text("citation-empty", [62, 419], "No cited transcripts. No fact is inferred from an empty result.", 13, "#9fb1c8"))
    objects.extend([
        _text("digest", [46, 646], f"Report SHA-256 · {report['digest'][:64]}", 10, "#94a3b8"),
        _text("boundary", [45, 694], "Transcript != measurement != hardware evidence != permission to act", 14, "#fda4af"),
        _text("source-note", [46, 728], "Original tool remains external · bounded snippets only · no transcript bundled", 11, "#9fb1c8"),
    ])
    scene = _scene("zoe-vidlib-evidence", 1000, 760, objects, "Zoe + vidlib · cited transcript reference retrieval")
    summary = {
        "instrument": "zoe-vidlib-evidence-scene",
        "operation": report["operation"],
        "citations": report["returned_count"],
        "network_attempted": report["network_attempted"],
        "executed": report["executed"],
        "synthetic_example": report["synthetic_example"],
        "transcript_is_measurement": False,
    }
    return scene, summary


def export_video_library_scene(path, report=None, kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("vidlib scene export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("vidlib scene export directory does not exist")
    scene, _summary = video_library_scene(report)
    check = verify_vdi(scene) if kind == "gem" else verify(scene)
    if not check.passed:
        raise ValueError(check.text())
    if kind == "gem":
        write_metafile(scene, path)
    elif kind == "svg":
        write_svg(scene, path, width)
    else:
        write_png(scene, path, width)
    return path

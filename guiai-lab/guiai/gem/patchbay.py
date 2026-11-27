from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .atlas import _line, _scene, _text
from .cog import demo_cog_report
from .field import _canonical
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


BOARDS = {
    "genesys2": {"name": "Genesys 2", "width_in": 6.8, "height_in": 5.8, "color": "#4ade80", "ports": ["USB/UART", "ETHERNET", "PMOD", "FMC", "SD", "VGA"]},
    "nexys-video": {"name": "Nexys Video", "width_in": 5.3, "height_in": 5.3, "color": "#c4b5fd", "ports": ["USB", "ETHERNET", "PMOD", "FMC", "SD", "HDMI"]},
}
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".svg", ".pdf", ".ai", ".mov", ".wmv"}
MEDIA_GROUPS = (
    "hw/pics/2001_sys_test",
    "hw/pics/2006_fibre_inst",
    "hw",
)
CATALOG_SUFFIXES = (".bit", ".ltx", ".mcs", ".tar.gz", ".txt")


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_path(path, maximum=128 * 1024 * 1024):
    path = Path(path)
    size = path.stat().st_size
    if not path.is_file() or not 1 <= size <= maximum:
        raise ValueError(f"artifact must contain 1 byte to {maximum} bytes")
    return path, size


def _base(path, kind, size=None):
    path = Path(path)
    return {
        "path": str(path),
        "name": path.name,
        "kind": kind,
        "size": size if size is not None else path.stat().st_size,
        "sha256": _sha(path),
        "hardware_accessed": False,
        "payloads_executed": False,
    }


def demo_artifact():
    return {
        "path": "memory://patchbay",
        "name": "Zoe Patchbay demonstration",
        "kind": "demo",
        "size": 0,
        "sha256": _digest({"synthetic": "patchbay"}),
        "details": ["Original board geometry from documented overall dimensions.", "No artifact is loaded until an explicit path is supplied."],
        "hardware_accessed": False,
        "payloads_executed": False,
        "summary": "Synthetic Patchbay scene · no firmware loaded · no hardware action",
    }


def parse_ihex(path):
    path, _ = _bounded_path(path)
    data = {}
    spans = []
    record_types = {}
    base = 0
    start_address = None
    ended = False
    with path.open("r", encoding="ascii") as stream:
        for line_number, line in enumerate(stream, 1):
            if len(line) > 1024:
                raise ValueError("Intel HEX line exceeds 1024 characters")
            line = line.strip()
            if not line:
                continue
            if ended:
                raise ValueError("Intel HEX contains records after EOF")
            if not line.startswith(":"):
                raise ValueError(f"line {line_number}: missing record marker")
            try:
                raw = bytes.fromhex(line[1:])
            except ValueError as error:
                raise ValueError(f"line {line_number}: invalid hexadecimal record") from error
            if len(raw) < 5 or len(raw) != raw[0] + 5 or sum(raw) & 0xFF:
                raise ValueError(f"line {line_number}: invalid record length or checksum")
            length, offset, kind = raw[0], int.from_bytes(raw[1:3], "big"), raw[3]
            payload = raw[4:-1]
            record_types[kind] = record_types.get(kind, 0) + 1
            if kind == 0:
                address = base + offset
                if address + length > 0x100000000 or len(data) + length > 16 * 1024 * 1024:
                    raise ValueError("Intel HEX address or data bound exceeded")
                for index, value in enumerate(payload):
                    location = address + index
                    if location in data and data[location] != value:
                        raise ValueError(f"line {line_number}: conflicting data overlap")
                    data[location] = value
            elif kind == 1:
                if length:
                    raise ValueError("Intel HEX EOF record has a payload")
                ended = True
            elif kind in {2, 4}:
                if length != 2:
                    raise ValueError("Intel HEX base-address record must contain two bytes")
                base = int.from_bytes(payload, "big") << (4 if kind == 2 else 16)
            elif kind in {3, 5}:
                if length != 4:
                    raise ValueError("Intel HEX start-address record must contain four bytes")
                start_address = {"type": "segment" if kind == 3 else "linear", "value": int.from_bytes(payload, "big")}
            else:
                raise ValueError(f"unsupported Intel HEX record type {kind}")
    if not data or not ended:
        raise ValueError("Intel HEX requires data and an EOF record")
    for address in sorted(data):
        if spans and spans[-1][1] == address:
            spans[-1][1] = address + 1
        else:
            spans.append([address, address + 1])
    return {
        "data_bytes": len(data),
        "spans": spans,
        "record_types": {str(key): value for key, value in sorted(record_types.items())},
        "start_address": start_address,
        "checksums_valid": True,
        "bootloader_included": False,
    }


def parse_bitstream(path):
    path, _ = _bounded_path(path)
    raw = path.read_bytes()
    prefix = bytes.fromhex("00090ff00ff00ff00ff0000001")
    if not raw.startswith(prefix):
        raise ValueError("unsupported Xilinx BIT header")
    position = len(prefix)
    fields = {}
    payload_offset = None
    for key in b"abcd":
        if position >= len(raw) or raw[position] != key or position + 3 > len(raw):
            raise ValueError("truncated Xilinx BIT metadata")
        length = int.from_bytes(raw[position + 1:position + 3], "big")
        position += 3
        if length < 1 or position + length > len(raw) or raw[position + length - 1] != 0:
            raise ValueError("invalid Xilinx BIT metadata string")
        fields[chr(key)] = raw[position:position + length - 1].decode("ascii")
        position += length
    if position + 5 > len(raw) or raw[position] != 0x65:
        raise ValueError("Xilinx BIT payload marker is missing")
    length = int.from_bytes(raw[position + 1:position + 5], "big")
    payload_offset = position + 5
    if length < 1 or payload_offset + length > len(raw):
        raise ValueError("Xilinx BIT payload length is invalid")
    sync = raw.find(b"\xaa\x99\x55\x66", payload_offset, payload_offset + min(length, 4 * 1024 * 1024))
    return {
        "design": fields["a"],
        "part": fields["b"],
        "build_date": fields["c"],
        "build_time": fields["d"],
        "payload_offset": payload_offset,
        "payload_bytes": length,
        "trailing_bytes": len(raw) - payload_offset - length,
        "payload_sha256": hashlib.sha256(raw[payload_offset:payload_offset + length]).hexdigest(),
        "sync_word_offset": sync if sync >= 0 else None,
        "header_is_signature": False,
    }


def inspect_zip(path):
    path, _ = _bounded_path(path)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= 16384:
            raise ValueError("ZIP requires 1-16384 directory entries")
        total = 0
        extensions = {}
        candidates = []
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.filename or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("unsafe ZIP entry path or link")
            if entry.is_dir():
                continue
            total += entry.file_size
            if total > 8 * 1024 * 1024 * 1024:
                raise ValueError("ZIP declared payload exceeds 8 GiB")
            suffix = name.suffix.lower().lstrip(".")
            extensions[suffix] = extensions.get(suffix, 0) + 1
            if name.name.lower() in {"felix_top.vhd", "control_fpga_top.vhd", "processing_fpga_top.vhd", "optin_fpga_top.vhd"} or name.stem.lower().endswith("_top") and suffix in {"vhd", "v"}:
                candidates.append(entry.filename)
    return {
        "entries": len(entries),
        "declared_uncompressed_bytes": total,
        "source_extensions": dict(sorted(extensions.items())),
        "top_level_candidates": candidates[:8],
        "directory_only": True,
        "archive_integrity_checked": False,
    }


def _zynq_reader():
    try:
        from ablation.analyzers.zynqmp_boot import ZynqMpBootImage
        return ZynqMpBootImage
    except ImportError:
        root = os.environ.get("ZOE_ABLATION_ROOT")
        if not root:
            raise RuntimeError("ZynqMP inspection requires Ablation or ZOE_ABLATION_ROOT")
        candidate = Path(root) / "ablation/analyzers/zynqmp_boot.py"
        if not candidate.is_file():
            raise RuntimeError(f"zynqmp_boot was not found at {candidate}")
        spec = importlib.util.spec_from_file_location("zoe_zynqmp_boot", candidate)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module.ZynqMpBootImage


def inspect_zynq(path):
    path, size = _bounded_path(path, 512 * 1024 * 1024)
    image = _zynq_reader().from_path(str(path))
    partitions = [{
        "index": partition.index,
        "name": partition.name,
        "offset": partition.offset,
        "size": partition.encrypted_length,
        "load_address": partition.load_address,
        "execution_address": partition.exec_address,
        "destination_device": partition.destination_device,
        "destination_cpu": partition.destination_cpu,
        "encrypted": partition.encrypted,
        "authenticated": partition.authenticated,
        "header_checksum_valid": partition.header_checksum_valid,
        "sha256": hashlib.sha256(partition.payload).hexdigest(),
    } for partition in image.partitions]
    return {
        "format": "Zynq UltraScale+ boot image",
        "size": size,
        "images": len(image.images),
        "partitions": partitions,
        "boot_header_checksum_valid": image.boot_header_checksum_valid,
        "iht_checksum_valid": image.iht_checksum_valid,
        "all_partitions_unencrypted": all(not partition["encrypted"] for partition in partitions),
        "all_partitions_unauthenticated": all(not partition["authenticated"] for partition in partitions),
    }


def inspect_fit(path):
    path, _ = _bounded_path(path, 512 * 1024 * 1024)
    with path.open("rb") as stream:
        header = stream.read(40)
    if len(header) != 40:
        raise ValueError("truncated FIT header")
    magic, total_size, structure_offset, strings_offset, _reserve, version, _compatible, _cpu, strings_size, structure_size = struct.unpack(">10I", header)
    if magic != 0xD00DFEED or total_size > path.stat().st_size or structure_offset + structure_size > total_size or strings_offset + strings_size > total_size or version < 16:
        raise ValueError("invalid or unsupported FIT header")
    if not shutil.which("fdtget"):
        raise RuntimeError("FIT inspection requires the optional fdtget utility")
    def query(arguments, required=False):
        completed = subprocess.run(["fdtget", str(path), *arguments], capture_output=True, text=True, timeout=10)
        if completed.returncode:
            if required:
                raise ValueError(f"FIT metadata query failed for {' '.join(arguments)}")
            return None
        if len(completed.stdout) > 65536:
            raise ValueError("FIT metadata response exceeds 64 KiB")
        return completed.stdout.strip()
    image_names = query(["-l", "/images"], required=True).splitlines()
    if not 1 <= len(image_names) <= 32 or any(not name or len(name) > 255 for name in image_names):
        raise ValueError("FIT requires 1-32 bounded image names")
    images = []
    for name in image_names:
        node = f"/images/{name}"
        properties = query(["-p", node], required=True).splitlines()
        record = {"name": name, "embedded_data": "data" in properties}
        for key in ("type", "description", "arch", "os", "compression"):
            record[key] = query(["-t", "s", node, key])
        for key in ("load", "entry", "data-size", "data-offset", "data-position"):
            value = query(["-t", "u", node, key])
            record[key.replace("-", "_")] = int(value.split()[0]) if value else None
        images.append(record)
    signature_names = query(["-l", "/signatures"])
    signatures = [] if not signature_names else signature_names.splitlines()
    algorithms = [query(["-t", "s", f"/signatures/{name}", "algo"]) for name in signatures[:32]]
    return {
        "format": "Flattened Image Tree",
        "total_size": total_size,
        "trailing_bytes": path.stat().st_size - total_size,
        "fdt_version": version,
        "images": images,
        "signature_present": bool(signatures),
        "signature_algorithms": [algorithm for algorithm in algorithms if algorithm],
        "signature_verification": "not-performed",
        "payloads_executed": False,
    }


def inspect_uimage(path):
    path, _ = _bounded_path(path, 512 * 1024 * 1024)
    with path.open("rb") as stream:
        marker = stream.read(4)
        if marker == b"\xd0\x0d\xfe\xed":
            return inspect_fit(path)
        header = marker + stream.read(60)
        if len(header) != 64 or marker != b"\x27\x05\x19\x56":
            raise ValueError("not a U-Boot legacy or FIT image")
        values = struct.unpack(">7I4B32s", header)
        expected_header_crc = values[1]
        protected = bytearray(header)
        protected[4:8] = b"\0" * 4
        payload_size = values[3]
        if path.stat().st_size != 64 + payload_size:
            raise ValueError("U-Boot image payload length disagrees with the file size")
        digest = zlib.crc32(b"")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest = zlib.crc32(chunk, digest)
    return {
        "format": "FIT image" if values[9] == 5 else "U-Boot legacy image",
        "header_crc_valid": zlib.crc32(protected) & 0xFFFFFFFF == expected_header_crc,
        "payload_crc_valid": digest & 0xFFFFFFFF == values[6],
        "timestamp_utc": datetime.fromtimestamp(values[2], timezone.utc).isoformat(),
        "payload_bytes": payload_size,
        "load_address": values[4],
        "entry_address": values[5],
        "os": values[7],
        "architecture": values[8],
        "image_type": values[9],
        "compression": values[10],
        "name": values[11].rstrip(b"\0").decode("utf-8", errors="replace"),
        "crc_is_authentication": False,
    }


def inspect_timing(path):
    path, size = _bounded_path(path, 1024 * 1024)
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = data.get("build_findings") if isinstance(data, dict) else None
    if not isinstance(findings, dict) or not isinstance(findings.get("timing_met"), bool) or not isinstance(findings.get("wns_ns"), (int, float)) or not math.isfinite(findings["wns_ns"]):
        raise ValueError("timing JSON requires build_findings.timing_met and finite wns_ns")
    return {
        "timing_met": findings["timing_met"],
        "wns_ns": findings["wns_ns"],
        "tns_ns": findings.get("tns_ns"),
        "source_git_hash": data.get("source", {}).get("source_git_hash") if isinstance(data.get("source"), dict) else None,
        "timing_member": data.get("source", {}).get("timing_member") if isinstance(data.get("source"), dict) else None,
        "digital_timing_only": True,
        "analog_timing_validated": False,
    }


def inspect_artifact(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".hex":
        parsed = parse_ihex(path)
        kind = "intel-hex-application"
        details = [f"{parsed['data_bytes']} data bytes · {len(parsed['spans'])} address spans", f"Start address: {parsed['start_address'] or 'not declared'}", "Application image only; separate bootloader not included."]
    elif suffix == ".bit":
        parsed = parse_bitstream(path)
        kind = "xilinx-bitstream"
        details = [parsed["design"], f"Part: {parsed['part']}", f"Built {parsed['build_date']} {parsed['build_time']}", f"{parsed['payload_bytes']} payload bytes · header is not a signature"]
    elif suffix == ".zip":
        parsed = inspect_zip(path)
        kind = "source-archive"
        details = [f"{parsed['entries']} entries · directory inspection only", f"Top-level candidates: {', '.join(parsed['top_level_candidates'][:3]) or 'none in the bounded listing'}", "No source or project script is executed."]
    elif suffix == ".bin":
        parsed = inspect_zynq(path)
        kind = "zynqmp-boot"
        details = [f"{parsed['images']} images · {len(parsed['partitions'])} partitions", " → ".join(partition["name"] for partition in parsed["partitions"]), f"All unencrypted: {parsed['all_partitions_unencrypted']} · all unauthenticated: {parsed['all_partitions_unauthenticated']}"]
    elif suffix == ".ub":
        parsed = inspect_uimage(path)
        if parsed["format"] == "Flattened Image Tree":
            kind = "fit-image"
            details = [f"{len(parsed['images'])} images · FDT version {parsed['fdt_version']}", " · ".join(image["name"] for image in parsed["images"]), f"Signatures present: {parsed['signature_present']} · verification: {parsed['signature_verification']}"]
        else:
            kind = "uimage"
            details = [parsed["format"], f"{parsed['payload_bytes']} payload bytes · {parsed['name']}", f"Header CRC: {parsed['header_crc_valid']} · payload CRC: {parsed['payload_crc_valid']} · CRC is not authentication"]
    elif suffix == ".json":
        parsed = inspect_timing(path)
        kind = "timing-evidence"
        details = [f"Digital WNS: {parsed['wns_ns']} ns · timing met: {parsed['timing_met']}", f"Source revision: {parsed['source_git_hash'] or 'not recorded'}", "Digital build evidence is not analog or deployed-hardware validation."]
    else:
        raise ValueError("Patchbay inspection supports .hex, .bit, .zip, .bin, .ub, and timing .json")
    result = _base(path, kind)
    result.update(parsed)
    result["details"] = details
    board = "genesys2" if "genesys2" in path.name.lower() else "nexys-video" if "nexysv" in path.name.lower() else None
    result["board"] = board
    result["summary"] = f"{kind} · {path.name}\n{details[0]}\nSource SHA-256 {result['sha256']}\nInspection only; no payload executed or hardware accessed."
    return result


def inspect_source(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("source root must be an existing directory")
    counts = {}
    inventory = hashlib.sha256()
    files = 0
    total = 0
    for directory, names, filenames in os.walk(root, followlinks=False):
        names.sort()
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.suffix.lower() not in {".vhd", ".vhdl", ".v", ".sv", ".tcl", ".xdc", ".ucf", ".cpp", ".h", ".py"} or path.is_symlink():
                continue
            files += 1
            if files > 4096:
                raise ValueError("source inventory exceeds 4096 files")
            size = path.stat().st_size
            if size > 16 * 1024 * 1024 or total + size > 1024 * 1024 * 1024:
                raise ValueError("source inventory file or total byte bound exceeded")
            total += size
            extension = path.suffix.lower()
            counts[extension] = counts.get(extension, 0) + 1
            inventory.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    inventory.update(chunk)
    if not files:
        raise ValueError("source root contains no supported source files")
    revision = "not-a-git-checkout"
    dirty = None
    dirty_scope = "not-a-git-checkout"
    submodule_state = "not-inspected"
    if (root / ".git").exists():
        completed = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True)
        revision = completed.stdout.strip()
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--ignore-submodules=all", "--untracked-files=no"], capture_output=True, text=True, timeout=10, check=True)
        if len(status.stdout.encode("utf-8")) > 1024 * 1024:
            raise ValueError("source status exceeds the inspection bound")
        dirty = bool(status.stdout)
        dirty_scope = "tracked-files-only-submodules-and-untracked-ignored"
        submodule_state = "ignored-for-bounded-inventory"
    return {
        "path": str(root),
        "name": root.name,
        "kind": "source-tree",
        "revision": revision,
        "dirty": dirty,
        "dirty_scope": dirty_scope,
        "source_files": files,
        "source_bytes": total,
        "source_extensions": dict(sorted(counts.items())),
        "size": total,
        "sha256": inventory.hexdigest(),
        "inventory_sha256": inventory.hexdigest(),
        "submodule_state": submodule_state,
        "hardware_accessed": False,
        "payloads_executed": False,
        "details": [f"Revision: {revision} · dirty: {dirty} · {dirty_scope}", f"{files} source files · {total} bytes", f"Inventory SHA-256 {inventory.hexdigest()}", "Submodule state and vendor toolchains require separate checks."],
        "summary": f"Source tree {root.name}\nRevision {revision} · dirty={dirty} · {dirty_scope}\n{files} source files · inventory {inventory.hexdigest()}\nNo build, submodule initialization, or hardware command executed.",
    }


class _CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.rows.append((self.href, "".join(self.text).strip()))
            self.href = None


def parse_catalog(text, url= "https://www.hep.ucl.ac.uk/~warren/upgrade/firmware/"):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 1024 * 1024:
        raise ValueError("catalog HTML must be at most 1 MiB")
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("firmware catalog requires an HTTPS URL")
    parser = _CatalogParser()
    parser.feed(text)
    parser.close()
    rows = []
    for href, label in parser.rows:
        destination = urljoin(url, href)
        name = Path(urlparse(destination).path).name
        if not name.lower().endswith(CATALOG_SUFFIXES) or name.lower().startswith("changelog"):
            continue
        lower = name.lower()
        board = "genesys2" if "genesys2" in lower else "nexys-video" if "nexysv" in lower else "other"
        marker = lower.find("_v")
        revision = name[marker + 1:].split(".", 1)[0] if marker >= 0 else None
        rows.append({"name": name, "url": destination, "board": board, "revision": revision, "latest_alias": "latest" in lower, "byte_equality_proven": False})
    if not rows:
        raise ValueError("catalog contains no supported firmware entries")
    return rows


def fetch_catalog(url="https://www.hep.ucl.ac.uk/~warren/upgrade/firmware/", timeout=15):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("firmware catalog requires HTTPS")
    request = Request(url, headers={"User-Agent": "Zoe-Patchbay/1.0"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("catalog exceeds 1 MiB")
    text = raw.decode("utf-8", errors="replace")
    result = {
        "schema_version": 1,
        "instrument": "zoe-patchbay-catalog",
        "source_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "transport": "https",
        "publisher_signature_verified": False,
        "entries": parse_catalog(text, url),
    }
    result["digest"] = _digest(result)
    return result


def _ffprobe(path):
    if not shutil.which("ffprobe"):
        return {"metadata_available": False}
    completed = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,codec_type,width,height", "-of", "json", str(path)], capture_output=True, text=True, timeout=10)
    if completed.returncode:
        return {"metadata_available": False, "metadata_error": completed.stderr[-500:]}
    if len(completed.stdout) > 65536:
        raise ValueError("media metadata exceeds 64 KiB")
    data = json.loads(completed.stdout)
    return {"metadata_available": True, "streams": data.get("streams", []), "duration": data.get("format", {}).get("duration")}


def media_gallery(root, output):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("media root must be an existing directory")
    records = []
    seen = set()
    for group in MEDIA_GROUPS:
        directory = root / group
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if path in seen or not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
                continue
            seen.add(path)
            if len(records) >= 128:
                raise ValueError("media gallery exceeds 128 artifacts")
            container = path.suffix.lower() in {".mov", ".wmv"}
            with path.open("rb") as stream:
                marker = stream.read(16)
            pict = marker[4:8] == b"pnot"
            kind = "document" if pict else "video" if container else "image" if path.suffix.lower() in {".jpg", ".jpeg", ".png"} else "document"
            path, size = _bounded_path(path, 512 * 1024 * 1024 if container else 128 * 1024 * 1024)
            record = {"name": path.name, "path": str(path), "relative": str(path.relative_to(root)), "uri": path.resolve().as_uri(), "kind": kind, "size": size, "sha256": _sha(path)}
            if pict:
                record["media_format"] = "PICT image with a misleading filename extension"
            if kind == "video":
                record.update(_ffprobe(path))
            records.append(record)
    if not records:
        raise ValueError("no supported media was found below the explicit root")
    cards = []
    for record in records:
        uri = html.escape(record["uri"], quote=True)
        if record["kind"] == "image":
            preview = f'<img loading="lazy" src="{uri}" alt="{html.escape(record["name"], quote=True)}">'
        elif record["kind"] == "video":
            preview = f'<video controls preload="none" src="{uri}"></video>'
        else:
            preview = f'<a class="document" href="{uri}">Open local document</a>'
        note = "<p>Video metadata unavailable; the original is retained.</p>" if record["kind"] == "video" and not record.get("metadata_available") else ""
        cards.append(f'<article><h2>{html.escape(record["name"])}</h2>{preview}<p>{record.get("media_format", record["kind"])} · {record["size"]} bytes</p>{note}<code>{record["sha256"]}</code><p><a href="{uri}">Open original</a></p></article>')
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Zoe Patchbay · local media</title>
<style>body{{background:#08111f;color:#dbeafe;font:16px system-ui;margin:2rem}}h1{{color:#67e8f9}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}}article{{background:#111d30;border:1px solid #334155;border-radius:12px;padding:1rem;overflow:hidden}}img,video{{width:100%;max-height:360px;object-fit:contain;background:#020617}}code{{overflow-wrap:anywhere;color:#a5b4fc;font-size:.75rem}}a{{color:#67e8f9}}h2{{font-size:1rem}}</style></head>
<body><h1>Zoe Patchbay</h1><p>Beautiful cable spaghetti. Every strand gets a hash. Local files only; no autoplay, server, or hardware command.</p><main>{''.join(cards)}</main></body></html>'''
    output = Path(output)
    if output.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("media gallery output must use .html")
    with output.open("x", encoding="utf-8") as stream:
        stream.write(document)
    return output, {"artifacts": len(records), "videos": sum(record["kind"] == "video" for record in records), "images": sum(record["kind"] == "image" for record in records), "documents": sum(record["kind"] == "document" for record in records), "pict_images": sum("media_format" in record for record in records), "video_metadata_unavailable": sum(record["kind"] == "video" and not record.get("metadata_available") for record in records), "root": str(root), "autoplay": False, "hardware_accessed": False}


def _board_objects(board):
    definition = BOARDS[board]
    width = 420
    height = round(width * definition["height_in"] / definition["width_in"])
    left, top = 45, 185
    color = definition["color"]
    objects = [
        {"id": "board", "type": "rectangle", "bounds": [left, top, left + width, top + height], "stroke": color, "fill": "#102b2a" if board == "genesys2" else "#211d39", "width": 3},
    ]
    for index, (x, y) in enumerate(((left + 16, top + 16), (left + width - 16, top + 16), (left + 16, top + height - 16), (left + width - 16, top + height - 16))):
        objects.append({"id": f"mount-{index}", "type": "ellipse", "center": [x, y], "radii": [7, 7], "stroke": "#9fb1c8", "fill": "#08111f", "width": 2})
    objects.append({"id": "cog-chip", "type": "rectangle", "bounds": [left + 130, top + 75, left + 290, top + 175], "stroke": "#f0abfc", "fill": "#08111f", "width": 2})
    objects.append(_text("cog-label", [left + 161, top + 119], "ZOE COG", 23, "#f0abfc"))
    objects.append(_text("cog-subtitle", [left + 151, top + 146], "two-way tokens", 13, "#9fb1c8"))
    for index in range(8):
        y = top + 82 + index * 11
        objects.append(_line(f"pin-left-{index}", [left + 119, y], [left + 130, y], color, 2))
        objects.append(_line(f"pin-right-{index}", [left + 290, y], [left + 301, y], color, 2))
    for index, port in enumerate(definition["ports"]):
        x = left + 28 + (index % 3) * 132
        y = top + 25 if index < 3 else top + height - 42
        objects.append({"id": f"port-{index}", "type": "rectangle", "bounds": [x, y, x + 90, y + 20], "stroke": color, "fill": "#08111f", "width": 1})
        objects.append(_text(f"port-label-{index}", [x + 5, y + 15], port, 10, color))
    objects.append(_text("board-name", [left + 105, top + height - 78], definition["name"].upper(), 24, color))
    objects.append(_text("board-dimensions", [left + 82, top + height + 23], f"{definition['width_in']} × {definition['height_in']} in · overall dimensions only", 12, "#9fb1c8"))
    objects.append(_text("board-scale", [left + 89, top + height + 43], "Original illustration · not a fabrication drawing", 11, "#9fb1c8"))
    return objects


def patchbay_scene(report=None, board="genesys2", cog_report=None):
    if board not in BOARDS:
        raise ValueError(f"unknown Patchbay board: {board}")
    report = report or demo_artifact()
    cog_report = cog_report or demo_cog_report()
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
    objects.append(_text("title", [42, 55], "Zoe Patchbay", 32, "#67e8f9"))
    objects.append(_text("subtitle", [44, 84], "Firmware · boards · signed updates · small-cog language play", 15, "#9fb1c8"))
    objects.append(_text("artifact", [510, 130], f"{report['kind']} · {report['name'][:38]}", 15, "#67e8f9"))
    objects.append(_text("source-hash", [510, 153], f"SHA-256 {report['sha256'][:32]}...", 11, "#9fb1c8"))
    for index, detail in enumerate(report.get("details", [])[:6]):
        text = detail if len(detail) <= 52 else detail[:49].rsplit(" ", 1)[0] + "..."
        objects.append(_text(f"detail-{index}", [510, 190 + index * 34], text, 12, "#dbeafe"))
    forward = cog_report["forward"]
    backward = cog_report["backward"]
    breadth = forward["steps"][-1]["accessible_volume"] if forward["steps"] else 0
    objects.append(_text("cog-heading", [510, 428], f"Cog · {cog_report['vocabulary_size']} tokens · A(τ)={breadth}", 15, "#f0abfc"))
    objects.append(_text("cog-forward", [510, 458], ("F> " + forward["text"])[:55], 11, "#dbeafe"))
    objects.append(_text("cog-backward", [510, 480], ("B< " + backward["text"])[:55], 11, "#dbeafe"))
    objects.append(_text("cog-boundary", [510, 506], "Small bigram model · not an LLM · no command output", 11, "#9fb1c8"))
    objects.extend(_board_objects(board))
    for index, label in enumerate(("READ", "HASH", "SIGN", "VERIFY", "TEST?")):
        x = 80 + index * 180
        objects.append({"id": f"flow-{index}", "type": "rectangle", "bounds": [x, 660, x + 105, 694], "stroke": "#67e8f9" if index < 4 else "#fde68a", "fill": "#111d30", "width": 1})
        objects.append(_text(f"flow-label-{index}", [x + 20, 682], label, 13, "#67e8f9" if index < 4 else "#fde68a"))
        if index < 4:
            objects.append(_line(f"flow-arrow-{index}", [x + 113, 677], [x + 164, 677], "#9fb1c8", 2))
    objects.append(_text("boundary", [86, 730], "Two-way street · no magic smoke · measurements never authorize actions", 14, "#fda4af"))
    scene = _scene("zoe-patchbay", 1000, 760, objects, "Zoe Patchbay · firmware, boards, and review loops")
    summary = report.get("summary", report.get("details", ["Patchbay"])[0]) + "\n" + cog_report["summary"]
    return scene, {**report, "cog": cog_report, "board": board, "summary": summary, "hardware_accessed": False}


def export_patchbay(path, report=None, board="genesys2", kind=None, width=1400, cog_report=None):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("Patchbay export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("Patchbay export directory does not exist")
    scene, _ = patchbay_scene(report, board, cog_report)
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

"""Vendored Allen Mouse CCFv3 structure meshes with SHA-256 verification.

Data is downloaded once into a local cache and hash-checked on every load.
Nothing here executes atlas content; only static public files are read.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request

ATLAS_NAME = "Allen Mouse Common Coordinate Framework v3 (2017)"
ATLAS_CITATION = "Wang et al. (2020), Cell 180(5):936-953.e20, https://doi.org/10.1016/j.cell.2020.04.007"
DOWNLOAD_ROOT = "https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/annotation/ccf_2017"
API_ROOT = "https://api.brain-map.org/api/v2/data/query.json"
DEFAULT_STRUCTURE_IDS = (803, 698, 315, 512, 1097, 313, 549, 703, 771, 354, 477, 1089)
USER_AGENT = "dorothy/1.0 (research mesh fetch)"
MAX_MESH_BYTES = 64 * 1024 * 1024
MAX_GRAPH_BYTES = 8 * 1024 * 1024


def default_root():
    from os import environ
    return Path(environ.get("DOROTHY_CCF_ROOT", Path.home() / ".cache" / "dorothy" / "ccf_2017"))


def parse_structure_ids(value):
    if isinstance(value, str):
        value = value.split(",")
    ids = []
    for item in value:
        identifier = int(item)
        if not 1 <= identifier <= 2147483647:
            raise ValueError("structure IDs must be positive 32-bit integers")
        if identifier in ids:
            raise ValueError(f"duplicate structure ID: {identifier}")
        ids.append(identifier)
    if not ids or len(ids) > 64:
        raise ValueError("select between 1 and 64 CCF structures")
    return ids


def _download(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"download exceeds the size limit: {url}")
    return data


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)


def graph_url(ids):
    criteria = ",".join(str(identifier) for identifier in ids)
    return (
        f"{API_ROOT}?criteria=model::Structure,rma::criteria,[id$in{criteria}],"
        "rma::options[only$in'structures.id,structures.name,structures.acronym,"
        "structures.color_hex_triplet,structures.parent_structure_id']"
    )


def mesh_url(identifier):
    return f"{DOWNLOAD_ROOT}/structure_meshes/ply/{identifier}.ply"


def fetch(root=None, ids=DEFAULT_STRUCTURE_IDS):
    root = Path(root) if root else default_root()
    ids = parse_structure_ids(ids)
    graph = json.loads(_download(graph_url(ids), MAX_GRAPH_BYTES).decode("utf-8"))
    if not graph.get("success"):
        raise ValueError("Allen RMA structure query failed")
    records = {record["id"]: record for record in graph["msg"]}
    missing = [identifier for identifier in ids if identifier not in records]
    if missing:
        raise ValueError(f"unknown CCF structure IDs: {', '.join(map(str, missing))}")
    structures = []
    for identifier in ids:
        record = records[identifier]
        color = record.get("color_hex_triplet") or "808080"
        if len(color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in color):
            raise ValueError(f"structure {identifier} has an invalid atlas color")
        path = root / "meshes" / f"{identifier}.ply"
        data = path.read_bytes() if path.is_file() else _download(mesh_url(identifier), MAX_MESH_BYTES)
        if len(data) > MAX_MESH_BYTES:
            raise ValueError(f"mesh {identifier} exceeds the size limit")
        structures.append({
            "id": identifier,
            "name": record["name"],
            "acronym": record["acronym"],
            "color": f"#{color.lower()}",
            "parent_structure_id": record.get("parent_structure_id"),
            "mesh": f"meshes/{identifier}.ply",
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
        if not path.is_file():
            _write_atomic(path, data)
    manifest = {
        "schema_version": 1,
        "atlas": ATLAS_NAME,
        "citation": ATLAS_CITATION,
        "source": {"structure_graph": graph_url(ids), "meshes": f"{DOWNLOAD_ROOT}/structure_meshes/ply/<id>.ply"},
        "structures": structures,
    }
    _write_atomic(root / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def load_manifest(root=None):
    root = Path(root) if root else default_root()
    path = root / "manifest.json"
    if not path.is_file():
        raise ValueError(f"no CCF data at {root}; run `gem dorothy --fetch` first")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported CCF manifest schema")
    return manifest


def load_structures(root=None, ids=None):
    root = Path(root) if root else default_root()
    manifest = load_manifest(root)
    records = {record["id"]: record for record in manifest["structures"]}
    selected = list(records) if ids is None else parse_structure_ids(ids)
    missing = [identifier for identifier in selected if identifier not in records]
    if missing:
        raise ValueError(f"structure IDs not present in the vendored manifest: {', '.join(map(str, missing))}")
    result = []
    for identifier in selected:
        record = dict(records[identifier])
        path = root / record["mesh"]
        data = path.read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"mesh hash mismatch for structure {identifier}; re-run `gem dorothy --fetch`")
        record["data"] = data
        result.append(record)
    return result

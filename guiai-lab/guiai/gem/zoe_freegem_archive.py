"""Zoe FreeGEM Archive Explorer & Dual-Endian GEM .RSC Binary Inspector (0 GPU · 0 Tokens).

Indexes and inspects authentic open-source Digital Research GEM / FreeGEM / ViewMAX
packages (such as John Elliott's seasip.info GPL FreeGEM collection) directly from
`.zip` and `.tar.gz` archives:
  - Dual-Endian `.RSC` Parser: auto-detects both Intel x86 little-endian FreeGEM/ViewMAX
    `.RSC` files (`VMCOLOUR.RSC`, `GEMSET.RSC`, `GEM.RSC`, `GEMFSLIB.RSC`, `RCS3D.RSC`)
    and Motorola 68000 big-endian Atari ST `.RSC` files (`ZOE_GEM.RSC`).
  - Extracts authentic `OBDEFS.H` object type counts (`G_BOX`..`G_CLRICN`) and FreeGEM
    3D AES 3.0 flags (`FL3DIND`, `FL3DBAK`, `FL3DACT`, `OUTLINED`, `SHADOWED`, `DRAW3D`).
  - Lets researchers search archives and read GPL C/H/TXT source specs (`THEME.C`,
    `OBDEFS.H`, `SETTINGS.TXT`, `VMCOLOUR.TXT`) straight inside `Zoe` CLI (`/freegem`).

Constitutional Invariants:
  read_only_archive_access=True · tokens_used=0 · sentience_claimed=False
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import struct
import tarfile
from typing import Any
import zipfile

# Authentic Digital Research / FreeGEM OBDEFS.H object types (AES 3.0 / ViewMAX)
GEM_OBJECT_TYPES: dict[int, str] = {
    20: "G_BOX",
    21: "G_TEXT",
    22: "G_BOXTEXT",
    23: "G_IMAGE",
    24: "G_USERDEF",
    25: "G_IBOX",
    26: "G_BUTTON",
    27: "G_BOXCHAR",
    28: "G_STRING",
    29: "G_FTEXT",
    30: "G_FBOXTEXT",
    31: "G_ICON",
    32: "G_TITLE",
    33: "G_CLRICN",
    34: "G_DTMFDB",
}

# Authentic FreeGEM AES 3.0 OBDEFS.H 3D & UI flags
FREEGEM_3D_FLAGS: dict[str, tuple[int, str]] = {
    "FL3DIND": (0x1000, "3D Indicator control (FreeGEM / ViewMAX/2-3)"),
    "FL3DBAK": (0x4000, "3D Background recessed panel (FreeGEM AES 3.0)"),
    "FL3DACT": (0x5000, "3D Activator push button (FreeGEM / ViewMAX)"),
    "OUTLINED": (0x0010, "Double outer border frame (dialogs & default buttons)"),
    "SHADOWED": (0x0020, "Classic GEM 2px drop shadow"),
    "WHITEBAK": (0x0040, "White background / ViewMAX 3D state marker"),
    "DRAW3D": (0x0080, "FreeGEM 3D beveled rendering state bit"),
}

_PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")


def locate_freegem_dirs(zoe_root: Path | None = None) -> list[Path]:
    """Locate local FreeGEM archive directories without hardcoded usernames."""
    candidates: list[Path] = []
    env_dir = os.environ.get("ZOE_FREEGEM_ARCHIVE", "").strip()
    if env_dir:
        candidates.append(Path(env_dir).expanduser())
    if zoe_root is not None:
        candidates.append(Path(zoe_root).resolve().parent / "FreeGEM-Seasip-Archive")
    here = Path(__file__).resolve()
    for parent in here.parents[:5]:
        candidates.append(parent / "FreeGEM-Seasip-Archive")
    candidates.append(Path.home() / ".zoe" / "freegem-archive")
    candidates.append(Path.home() / "Downloads")
    seen: set[Path] = set()
    found: list[Path] = []
    for cand in candidates:
        try:
            res = cand.resolve()
        except OSError:
            continue
        if res.is_dir() and res not in seen:
            seen.add(res)
            found.append(res)
    return found


def _unpack_rshdr(data: bytes, endian: str) -> dict[str, int]:
    fields = struct.unpack(endian + "18H", data[:36])
    keys = (
        "rsh_vrsn", "rsh_object", "rsh_tedinfo", "rsh_iconblk", "rsh_bitblk",
        "rsh_frstr", "rsh_string", "rsh_imdata", "rsh_frimg", "rsh_trindex",
        "rsh_nobs", "rsh_ntree", "rsh_nted", "rsh_nib", "rsh_nbb",
        "rsh_nstring", "rsh_nimages", "rsh_rssize",
    )
    return dict(zip(keys, fields))


def _rshdr_plausible(hdr: dict[str, int], total_len: int) -> bool:
    if hdr["rsh_rssize"] < 36 or hdr["rsh_rssize"] > total_len + 64:
        return False
    if hdr["rsh_object"] > total_len or hdr["rsh_trindex"] > total_len:
        return False
    return hdr["rsh_nobs"] <= 4096 and hdr["rsh_ntree"] <= 512


def _scan_rsc_objects(data: bytes, hdr: dict[str, int], endian: str) -> tuple[dict[str, int], dict[str, int]]:
    type_counts: dict[str, int] = {}
    flag_counts = {"FL3DIND": 0, "FL3DBAK": 0, "FL3DACT": 0, "OUTLINED": 0, "SHADOWED": 0, "DRAW3D": 0}
    off = hdr["rsh_object"]
    for idx in range(hdr["rsh_nobs"]):
        pos = off + idx * 24
        if pos + 24 > len(data):
            break
        _nxt, _head, _tail, ob_type, ob_flags, ob_state = struct.unpack(endian + "6H", data[pos : pos + 12])
        t_name = GEM_OBJECT_TYPES.get(ob_type & 0x00FF, f"TYPE_{ob_type & 0x00FF}")
        type_counts[t_name] = type_counts.get(t_name, 0) + 1
        fl3d = ob_flags & 0x5000
        if fl3d == 0x5000:
            flag_counts["FL3DACT"] += 1
        elif fl3d == 0x4000:
            flag_counts["FL3DBAK"] += 1
        elif fl3d == 0x1000:
            flag_counts["FL3DIND"] += 1
        if ob_state & 0x0010:
            flag_counts["OUTLINED"] += 1
        if ob_state & 0x0020:
            flag_counts["SHADOWED"] += 1
        if ob_state & 0x0080:
            flag_counts["DRAW3D"] += 1
    return type_counts, flag_counts


def inspect_rsc_bytes(data: bytes, label: str = "resource.rsc") -> dict[str, Any]:
    """Parse an Intel x86 (little-endian) or Motorola 68000 (big-endian) GEM .RSC binary."""
    if len(data) < 36:
        raise ValueError(f"{label} is too small ({len(data)} bytes) to be a valid GEM .RSC file.")
    le_hdr = _unpack_rshdr(data, "<")
    be_hdr = _unpack_rshdr(data, ">")
    if _rshdr_plausible(le_hdr, len(data)):
        endian, arch, hdr = "<", "Intel x86 (FreeGEM / ViewMAX little-endian)", le_hdr
    elif _rshdr_plausible(be_hdr, len(data)):
        endian, arch, hdr = ">", "Motorola 68000 (Atari ST / EmuTOS big-endian)", be_hdr
    else:
        raise ValueError(f"{label} header did not match Intel or 68000 GEM RSHDR invariants.")
    type_counts, flag_counts = _scan_rsc_objects(data, hdr, endian)
    strings = [m.decode("ascii") for m in _PRINTABLE_RE.findall(data)]
    return {
        "ok": True,
        "label": label,
        "bytes": len(data),
        "arch": arch,
        "endian": endian,
        "header": hdr,
        "object_types": type_counts,
        "flags_3d": flag_counts,
        "sample_strings": strings[:16],
        "tokens_used": 0,
    }


def _archive_members(path: Path) -> list[str]:
    low = path.name.lower()
    if low.endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as zf:
                return zf.namelist()
        except zipfile.BadZipFile:
            return []
    if low.endswith((".tar.gz", ".tgz")):
        try:
            with tarfile.open(path, "r:gz") as tf:
                return tf.getnames()
        except tarfile.TarError:
            return []
    return []


def _read_archive_member_bytes(path: Path, member: str) -> bytes:
    low = path.name.lower()
    if low.endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            return zf.read(member)
    if low.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as tf:
            fh = tf.extractfile(member)
            if fh is None:
                raise ValueError(f"{member} is not a regular file in {path.name}")
            return fh.read()
    raise ValueError(f"Unsupported archive format: {path.name}")


def _is_gem_archive_name(name: str) -> bool:
    low = name.lower()
    if not low.endswith((".zip", ".tar.gz", ".tgz")):
        return False
    if "(" in low and ")" in low:
        return False
    return True


def scan_freegem_archives(zoe_root: Path | None = None, archive_dir: Path | None = None) -> dict[str, Any]:
    """Catalog all discovered FreeGEM / seasip.info archives."""
    dirs = [Path(archive_dir).resolve()] if archive_dir is not None else locate_freegem_dirs(zoe_root)
    primary = next((d for d in dirs if d.name == "FreeGEM-Seasip-Archive"), dirs[0] if dirs else None)
    packages: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    scan_dirs = [primary] if (primary is not None and primary.name == "FreeGEM-Seasip-Archive") else dirs
    for d in scan_dirs:
        if d is None or not d.is_dir():
            continue
        for entry in sorted(d.iterdir()):
            if not entry.is_file() or not _is_gem_archive_name(entry.name) or entry.name in seen_names:
                continue
            members = _archive_members(entry)
            if not members:
                continue
            rscs = [m for m in members if m.lower().endswith(".rsc")]
            srcs = [m for m in members if m.lower().endswith((".c", ".h", ".a86", ".asm"))]
            docs = [m for m in members if m.lower().endswith((".txt", ".doc", ".1st"))]
            if d.name == "Downloads" and not (rscs or any("gem" in m.lower() or "viewmax" in m.lower() for m in members)):
                continue
            seen_names.add(entry.name)
            packages.append({
                "name": entry.name,
                "path": str(entry),
                "bytes": entry.stat().st_size,
                "entries": len(members),
                "rscs": rscs,
                "src_count": len(srcs),
                "docs": docs,
            })
    return {
        "primary_dir": str(primary) if primary else "",
        "count": len(packages),
        "total_bytes": sum(p["bytes"] for p in packages),
        "total_rscs": sum(len(p["rscs"]) for p in packages),
        "total_srcs": sum(p["src_count"] for p in packages),
        "packages": packages,
        "tokens_used": 0,
    }


def _resolve_package(name_query: str, catalog: dict[str, Any]) -> dict[str, Any]:
    q = (name_query or "").strip().lower()
    if not q:
        raise ValueError("Specify an archive name (e.g. `settings.zip`, `vmcolour.zip`, `aes301xm.zip`).")
    for pkg in catalog["packages"]:
        if pkg["name"].lower() in {q, f"{q}.zip", f"{q}.tar.gz"}:
            return pkg
    matches = [pkg for pkg in catalog["packages"] if q in pkg["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Archive {name_query!r} not found in FreeGEM catalog ({catalog['count']} packages).")


def inspect_archive_rsc(
    archive_or_rsc: str,
    rsc_member: str = "",
    *,
    zoe_root: Path | None = None,
    archive_dir: Path | None = None,
) -> dict[str, Any]:
    """Inspect a standalone .RSC file or an .RSC member inside a FreeGEM archive."""
    direct = Path(archive_or_rsc).expanduser()
    if direct.is_file() and direct.suffix.lower() == ".rsc":
        return inspect_rsc_bytes(direct.read_bytes(), label=direct.name)
    catalog = scan_freegem_archives(zoe_root, archive_dir=archive_dir)
    pkg = _resolve_package(archive_or_rsc, catalog)
    rscs: list[str] = pkg["rscs"]
    if not rscs:
        raise ValueError(f"{pkg['name']} contains no .RSC files.")
    chosen = rscs[0]
    if rsc_member:
        low_m = rsc_member.lower()
        chosen = next((m for m in rscs if low_m in m.lower()), rscs[0])
    data = _read_archive_member_bytes(Path(pkg["path"]), chosen)
    return inspect_rsc_bytes(data, label=f"{pkg['name']}::{chosen}")


def read_archive_source(
    archive_name: str,
    member_query: str,
    *,
    max_lines: int = 36,
    zoe_root: Path | None = None,
    archive_dir: Path | None = None,
) -> tuple[str, list[str]]:
    """Read a GPL C/H/TXT file snippet directly out of a FreeGEM archive."""
    catalog = scan_freegem_archives(zoe_root, archive_dir=archive_dir)
    pkg = _resolve_package(archive_name, catalog)
    members = _archive_members(Path(pkg["path"]))
    q = (member_query or "").strip().lower()
    chosen = next((m for m in members if Path(m).name.lower() == q or m.lower() == q), None)
    if chosen is None:
        chosen = next((m for m in members if q and q in m.lower()), None)
    if chosen is None:
        raise ValueError(f"Member {member_query!r} not found inside {pkg['name']}.")
    raw = _read_archive_member_bytes(Path(pkg["path"]), chosen)
    text = raw.decode("latin-1", errors="ignore").splitlines()
    return f"{pkg['name']}::{chosen} ({len(text)} lines total)", text[:max_lines]


def search_freegem_archives(term: str, *, zoe_root: Path | None = None, archive_dir: Path | None = None) -> list[str]:
    """Search archive names and member filenames across all local FreeGEM packages."""
    q = (term or "").strip().lower()
    if not q:
        raise ValueError("Usage: /freegem search <keyword>  (e.g. `theme`, `sdl`, `icon`, `font`, `3d`)")
    catalog = scan_freegem_archives(zoe_root, archive_dir=archive_dir)
    hits: list[str] = []
    for pkg in catalog["packages"]:
        members = _archive_members(Path(pkg["path"]))
        matched = [m for m in members if q in m.lower()]
        if q in pkg["name"].lower() or matched:
            sample = ", ".join(matched[:4]) if matched else f"{pkg['entries']} files"
            hits.append(f"  • {pkg['name']:<24} ({pkg['bytes'] // 1024:>4} KB) · {sample}")
    if not hits:
        return [f"No FreeGEM archives matched {term!r} (catalog has {catalog['count']} packages)."]
    return [f"FreeGEM Archive Search for '{term}' ({len(hits)} matching packages · 0 tokens):", *hits[:20]]


def format_freegem_catalog(catalog: dict[str, Any]) -> list[str]:
    """Format a compact overview of all mirrored FreeGEM packages."""
    mb = catalog["total_bytes"] / 1048576.0
    lines = [
        f"Zoe FreeGEM Open-Source Archive ({catalog['count']} packages · {mb:.2f} MB · {catalog['total_rscs']} .RSC · {catalog['total_srcs']} C/H/ASM · 0 tokens)",
        f"  Directory : {catalog['primary_dir'] or '(not found)'}",
    ]
    for pkg in catalog["packages"][:18]:
        lines.append(
            f"  • {pkg['name']:<24} {pkg['bytes'] // 1024:>4} KB · {len(pkg['rscs']):>2} RSC · {pkg['src_count']:>3} SRC · {pkg['entries']:>3} files"
        )
    if catalog["count"] > 18:
        lines.append(f"  ... plus {catalog['count'] - 18} more packages (use `/freegem search <term>` to explore all)")
    lines.append("Commands: /freegem search <term> | /freegem rsc <zip_or_rsc> | /freegem src <zip> <file> | /freegem specs")
    return lines


def format_rsc_inspection(report: dict[str, Any]) -> list[str]:
    """Format a dual-endian GEM .RSC inspection report."""
    hdr = report["header"]
    objs = ", ".join(f"{k}={v}" for k, v in sorted(report["object_types"].items())) or "none"
    f3d = ", ".join(f"{k}={v}" for k, v in report["flags_3d"].items() if v) or "none (classic 2D GEM)"
    sample = " | ".join(report["sample_strings"][:6]) or "(no ASCII strings)"
    return [
        f"GEM .RSC Binary Inspection :: {report['label']} ({report['bytes']:,} bytes · 0 tokens)",
        f"  Endian/Arch : {report['arch']}",
        f"  RSHDR       : vrsn={hdr['rsh_vrsn']} · trees={hdr['rsh_ntree']} · objects={hdr['rsh_nobs']} · icons={hdr['rsh_nib']} · bitblks={hdr['rsh_nbb']} · strings={hdr['rsh_nstring']}",
        f"  OBDEFS Type : {objs}",
        f"  FreeGEM 3D  : {f3d}",
        f"  Strings     : {sample[:140]}",
    ]


def format_freegem_3d_specs() -> list[str]:
    """Summarize authentic FreeGEM OBDEFS.H 3D flags & SETTINGS.APP GUI rules for Zoe-GEM OS."""
    lines = ["Authentic FreeGEM AES 3.0 / ViewMAX/2-3 UI Constants (from OBDEFS.H & SETTINGS.TXT):"]
    for name, (bit, desc) in FREEGEM_3D_FLAGS.items():
        lines.append(f"  • {name:<10} (0x{bit:04x}) : {desc}")
    lines.extend([
        "  • Window Gadgets (SETTINGS.APP): selectable GEM/1, GEM/2, and ViewMAX symbol sets",
        "  • 3D Corners     (SETTINGS.APP): Rounded (ViewMAX/2-3) or Square (GEM/5)",
        "  • Window Frames  (SETTINGS.APP): Flat (ViewMAX) or Sculpted 3D (GEM/5 / Zoe-GEM OS)",
    ])
    return lines

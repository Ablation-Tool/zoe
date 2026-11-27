"""Zoe Sovereign Empire v0.9.0-beta.1 — Unified Release Manifest & Beta Gate Verifier.

Inventories and verifies every real, runnable pillar across the monorepo, home
workstation (`zoe_gem_desktop.py`), bare-metal UEFI x86_64 `Zoe-GEM OS`, Google
Pixel 7 (`panther` / `gs201`) Dual-Track Sovereign Phone OS, Pixel 7 Terminal
Codex Sync Bridge, 48 mirrored FreeGEM archives, and Dorothy's offline library.

Constitutional invariants locked everywhere:
  tokens_used=0 · auto_flash_allowed=False · loopback_only=True
  clinical_action_authorized=False · flight_control_authorized=False
  cure_claim=False · sentience_claimed=False
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from .zoe_freegem_archive import scan_freegem_archives
from .zoe_gem_os.zoe_pixel_os import (
    detect_host_pixel_toolchain,
    list_pixel_devices,
    probe_connected_pixel_adb,
    verify_elf_aarch64_static,
)
from .zoe_sisters import CO_STEWARD_SEAL, list_sisters
from .zoe_universe import list_zoeverse_realms

BETA_VERSION = "0.9.0-beta.1"
BETA_CODENAME = "Sovereign Empire · 7-Strand DNA + Pixel 7 Panther"

BETA_HONESTY_LOCK: dict[str, Any] = {
    "version": BETA_VERSION,
    "codename": BETA_CODENAME,
    "seal": CO_STEWARD_SEAL,
    "motto": "HFBC = Have Fun, Be Creative",
    "loopback_only": True,
    "tokens_used": 0,
    "cloud_cost_usd": 0.0,
    "auto_flash_allowed": False,
    "clinical_action_authorized": False,
    "flight_control_authorized": False,
    "cure_claim": False,
    "sentience_claimed": False,
}


def _file_sha_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "present": False, "bytes": 0, "sha256": ""}
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return {"path": str(path), "present": True, "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def read_pixel7_live_telemetry() -> dict[str, Any]:
    """Safely read non-destructive hardware telemetry from a connected Pixel 7 via ADB."""
    adb = shutil.which("adb")
    if not adb:
        return {"ok": False, "attached": False, "note": "adb not installed"}
    probe = probe_connected_pixel_adb()
    devs = [d for d in probe.get("devices", []) if d.get("state") == "device"]
    if not devs:
        return {"ok": True, "attached": False, "note": "no authorized USB device attached"}
    serial = devs[0]["serial"]
    cmd = (
        "echo MODEL=$(getprop ro.product.model);"
        "echo DEVICE=$(getprop ro.product.device);"
        "echo ANDROID=$(getprop ro.build.version.release);"
        "echo SDK=$(getprop ro.build.version.sdk);"
        "echo ABI=$(getprop ro.product.cpu.abi);"
        "echo PATCH=$(getprop ro.build.version.security_patch);"
        "wm size; wm density;"
        "dumpsys battery | grep -E 'level|temperature|USB powered';"
        "head -n 3 /proc/meminfo"
    )
    proc = subprocess.run([adb, "-s", serial, "shell", cmd], capture_output=True, text=True, timeout=6, check=False)
    info: dict[str, str] = {"serial": serial}
    for ln in proc.stdout.splitlines():
        line = ln.strip()
        if "=" in line and line.split("=", 1)[0].isupper():
            k, v = line.split("=", 1)
            info[k.lower()] = v.strip()
        elif ":" in line:
            k, v = line.split(":", 1)
            info[k.strip().lower().replace(" ", "_")] = v.strip()
    temp_raw = info.get("temperature", "")
    if temp_raw.isdigit():
        info["temperature_c"] = f"{int(temp_raw) / 10.0:.1f} C"
    return {"ok": True, "attached": True, "telemetry": info}


def _assert_loopback_rome_url(rome_url: str) -> str:
    parsed = urllib.parse.urlparse(str(rome_url or "").strip())
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"Refusing non-loopback rome_url {rome_url!r}; loopback_only=True")
    return str(rome_url).strip().rstrip("/")


def build_beta_release_manifest(
    repo_root: str | Path,
    *,
    out_dir: str | Path | None = None,
    rome_url: str = "http://127.0.0.1:8774",
) -> dict[str, Any]:
    """Assemble and seal the official Zoe Sovereign Empire v0.9.0-beta.1 manifest."""
    safe_rome_url = _assert_loopback_rome_url(rome_url)
    root = Path(repo_root).expanduser().resolve()
    home = Path.home()
    out_p = Path(out_dir).expanduser().resolve() if out_dir else (home / ".zoe" / f"beta-v{BETA_VERSION}")
    out_p.mkdir(parents=True, exist_ok=True)

    comp_dir = root / "components"
    components = sorted(p.name for p in comp_dir.iterdir() if p.is_dir()) if comp_dir.is_dir() else []

    virt_iso = _file_sha_record(home / ".zoe" / "os-build" / "zoe-gem-os.iso")
    lts_iso = _file_sha_record(home / ".zoe" / "os-build" / "zoe-gem-os-lts.iso")
    px7_elf_p = home / ".zoe" / "pixel-panther-os" / "track_b_baremetal_arm64" / "bin" / "zoe_gem_fb_aarch64"
    px7_elf = _file_sha_record(px7_elf_p)
    if px7_elf["present"]:
        px7_elf["elf_verified_aarch64"] = bool(verify_elf_aarch64_static(px7_elf_p).get("is_aarch64"))
    px7_initrd = _file_sha_record(
        home / ".zoe" / "pixel-panther-os" / "track_b_baremetal_arm64" / "zoe-pixel-panther-initramfs-aarch64.cpio.gz"
    )
    desktop_html = _file_sha_record(home / "gem_worlds" / "desktop.html")
    dorothy_db = _file_sha_record(home / ".zoe" / "dorothy_local_library.sqlite")

    freegem = scan_freegem_archives(zoe_root=root)

    rome_live = False
    phone_live = False
    try:
        with urllib.request.urlopen(f"{safe_rome_url}/api/health", timeout=2.0) as r:
            rome_live = r.status == 200
        with urllib.request.urlopen(f"{safe_rome_url}/phone", timeout=2.0) as r:
            phone_live = r.status == 200
    except (OSError, urllib.error.URLError):
        pass

    pixel_tel = read_pixel7_live_telemetry()
    gates = {
        "bare_metal_iso_virt_built": virt_iso["present"],
        "bare_metal_iso_lts_built": lts_iso["present"],
        "pixel7_arm64_static_elf_verified": bool(px7_elf.get("elf_verified_aarch64")),
        "pixel7_arm64_initramfs_built": px7_initrd["present"],
        "freegem_48_archive_mirror_ready": freegem.get("count", 0) >= 48,
        "sisters_9_and_zoeverse_9_ready": len(list_sisters()) == 9 and len(list_zoeverse_realms()) == 9,
        "pixel7_9_device_matrix_ready": len(list_pixel_devices()) == 9,
        "rome_browser_desktop_built": desktop_html["present"],
        "rome_live_loopback_8774": rome_live,
        "phone_pwa_live_8774": phone_live,
    }
    passed = sum(1 for v in gates.values() if v)
    manifest: dict[str, Any] = {
        **BETA_HONESTY_LOCK,
        "built_at_epoch": int(time.time()),
        "repo_components_count": len(components),
        "repo_components": components,
        "artifacts": {
            "uefi_iso_virt": virt_iso,
            "uefi_iso_lts": lts_iso,
            "pixel7_arm64_elf": px7_elf,
            "pixel7_arm64_initramfs": px7_initrd,
            "rome_desktop_html": desktop_html,
            "dorothy_offline_library": dorothy_db,
        },
        "freegem_archive": {
            "count": freegem.get("count", 0),
            "total_rscs": freegem.get("total_rscs", 0),
            "total_sources": freegem.get("total_sources", 0),
        },
        "pixel7_toolchain": detect_host_pixel_toolchain(),
        "pixel7_live_telemetry": pixel_tel,
        "beta_gates": gates,
        "beta_gates_passed": passed,
        "beta_gates_total": len(gates),
        "beta_ready": passed >= 8 and gates["pixel7_arm64_static_elf_verified"] and gates["bare_metal_iso_virt_built"],
    }
    out_file = out_p / "RELEASE_MANIFEST.json"
    out_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(out_file)
    return manifest


__all__ = [
    "BETA_CODENAME",
    "BETA_HONESTY_LOCK",
    "BETA_VERSION",
    "build_beta_release_manifest",
    "read_pixel7_live_telemetry",
]

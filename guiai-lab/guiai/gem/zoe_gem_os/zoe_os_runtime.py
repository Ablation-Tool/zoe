"""In-OS Boot Brain, Hardware Self-Retention Verifier, and Interactive Shell for Zoe-GEM OS.

Executed directly inside the booted UEFI x86_64 Zoe-GEM OS environment (PID 1 -> Python):
  1. Verifies cryptographic SHA-256 boot-retention chain across hard reboots on `/mnt/zoe-state`.
  2. Persists and verifies real Digital Research Artline `.svg` + `.gem` VDI plates and the
     Motorola 68000 `ZOE_GEM.RSC` icon table on the hardware disk.
  3. Persists and restores Nicholas's private `/drawer` across reboots.
  4. Emits `/run/zoe-boot-state.json` for the native C `/dev/fb0` GEM Desktop (`zoe_gem_fb`).
  5. Provides an interactive `Zoe-OS ◠◡◠ ❯` command shell when booted interactively.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import threading
import time
from typing import Any, Iterator

# Ensure bundled Zoe GEM modules resolve inside the booted OS
for candidate in ("/usr/lib/zoe", str(Path(__file__).resolve().parents[3])):
    if candidate not in sys.path and Path(candidate).exists():
        sys.path.insert(0, candidate)

from guiai.gem.artline import ArtlineDocument, blend_polygons, rotate_ring
from guiai.gem.zoe_atari_gem_rsc import build_atari_rsc_bytes, parse_atari_rsc
from guiai.gem.zoe_gem_os.zoe_uma import UmaBridge, find_guest_ivshmem_bar2

_STATE_LOCKS_GUARD = threading.Lock()
_STATE_LOCKS: dict[Path, threading.RLock] = {}
_STATE_LOCK_DEPTHS = threading.local()
_IGNORED_FLOCK_ERRNOS = (errno.ENOSYS, errno.EOPNOTSUPP, errno.ENOLCK)
_VM_TOKENS = ("qemu", "kvm", "bochs", "vmware", "virtualbox", "xen", "hyper-v", "google")
_SBC_TOKENS = ("raspberry", "jetson", "beagle", "orange pi", "pine64", "rock")
_DAQ_VENDORS = {"0x10ee", "0x1172", "0x1093", "0x1100"}
_PRIMARY_ARCHES = {"x86_64", "amd64", "aarch64", "arm64"}
_SECONDARY_ARCHES = {"riscv64", "ppc64le", "ppc64", "armv7l", "i686", "s390x"}
_CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "tokens_used": 0,
    "external_actions": 0,
    "clinical_action_authorized": False,
    "flight_control_authorized": False,
    "cure_claim": False,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "auto_flash_allowed": False,
    "zoe_clone_claimed": False,
}


def _get_state_thread_lock(state_dir: Path) -> threading.RLock:
    resolved = state_dir.resolve()
    with _STATE_LOCKS_GUARD:
        lock = _STATE_LOCKS.get(resolved)
        if lock is None:
            lock = threading.RLock()
            _STATE_LOCKS[resolved] = lock
        return lock


@contextlib.contextmanager
def _state_lock(state_dir: Path) -> Iterator[None]:
    resolved = state_dir.resolve()
    depths: dict[Path, int] = getattr(_STATE_LOCK_DEPTHS, "depths", {})
    if not hasattr(_STATE_LOCK_DEPTHS, "depths"):
        _STATE_LOCK_DEPTHS.depths = depths
    with _get_state_thread_lock(resolved):
        cur = depths.get(resolved, 0)
        if cur > 0:
            depths[resolved] = cur + 1
            try:
                yield
            finally:
                depths[resolved] = cur
            return
        resolved.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(resolved / ".state.lock"), os.O_CREAT | os.O_RDWR, 0o644)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as exc:
                if exc.errno not in _IGNORED_FLOCK_ERRNOS:
                    raise
            depths[resolved] = 1
            try:
                yield
            finally:
                depths[resolved] = 0
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(fd)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "").strip()
    except OSError:
        return ""


def _apply_cpuinfo_kv(parsed: dict[str, Any], key: str, val: str) -> None:
    low = key.lower()
    if low == "processor":
        parsed["proc_lines"] += 1
    elif low in {"model name", "model", "hardware", "cpu"} and not parsed["model"]:
        parsed["model"] = val
    elif low in {"vendor_id", "cpu implementer", "vendor"} and not parsed["vendor"]:
        parsed["vendor"] = val
    elif low in {"flags", "features"} and not parsed["flags"]:
        parsed["flags"] = [tok.lower() for tok in val.split() if tok]
    elif low == "isa" and not parsed["arch_hint"]:
        parsed["arch_hint"] = val.split()[0].lower()


def _parse_cpuinfo_fields(raw: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {"model": "", "vendor": "", "flags": [], "proc_lines": 0, "arch_hint": ""}
    for line in raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            _apply_cpuinfo_kv(parsed, key.strip(), val.strip())
    return parsed


def _probe_cpu(proc_root: Path = Path("/proc"), arch_override: str | None = None) -> dict[str, Any]:
    raw = _read_text_safe(proc_root / "cpuinfo")
    parsed = _parse_cpuinfo_fields(raw)
    host_arch = os.uname().machine if hasattr(os, "uname") else "x86_64"
    use_hint = proc_root != Path("/proc") and bool(parsed["arch_hint"])
    cpu_arch = arch_override or (parsed["arch_hint"] if use_hint else host_arch)
    cores = parsed["proc_lines"]
    if cores == 0:
        if proc_root == Path("/proc"):
            cores = os.cpu_count() or 1
        elif parsed["model"]:
            cores = 1
    model = (parsed["model"] or f"{cpu_arch} CPU")[:48]
    return {
        "arch": cpu_arch,
        "model": model,
        "short_model": model[:36],
        "vendor": parsed["vendor"] or "unknown",
        "core_count": cores,
        "has_hypervisor": "hypervisor" in parsed["flags"],
        "flags": parsed["flags"][:24],
    }


def _probe_memory(proc_root: Path = Path("/proc")) -> dict[str, int]:
    raw = _read_text_safe(proc_root / "meminfo")
    kb_vals: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            kb_vals[parts[0].rstrip(":")] = int(parts[1])
    total_mb = kb_vals.get("MemTotal", 0) // 1024
    avail_kb = kb_vals.get("MemAvailable", kb_vals.get("MemFree", 0))
    return {"ram_total_mb": total_mb, "ram_available_mb": avail_kb // 1024}


def _has_sys_hypervisor(sys_root: Path) -> bool:
    hyp_dir = sys_root / "hypervisor"
    if (hyp_dir / "type").is_file():
        return True
    if not hyp_dir.is_dir():
        return False
    try:
        return any(hyp_dir.iterdir())
    except OSError:
        return False


def _probe_dmi_and_dt(sys_root: Path, has_hypervisor: bool = False) -> dict[str, Any]:
    dmi_dir = sys_root / "class/dmi/id"
    dmi = {
        name: _read_text_safe(dmi_dir / name)
        for name in ("sys_vendor", "product_name", "board_name", "board_vendor", "bios_vendor", "chassis_type")
    }
    dt_model = _read_text_safe(sys_root / "firmware/devicetree/base/model")
    blob = " ".join([dmi["sys_vendor"], dmi["product_name"], dmi["bios_vendor"], dt_model]).lower()
    is_vm = has_hypervisor or _has_sys_hypervisor(sys_root) or any(t in blob for t in _VM_TOKENS)
    return {**dmi, "devicetree_model": dt_model, "is_vm": is_vm}


def _read_pci_device_entry(dev: Path) -> dict[str, str] | None:
    vendor = _read_text_safe(dev / "vendor").lower()
    device = _read_text_safe(dev / "device").lower()
    cls = _read_text_safe(dev / "class").lower()
    if not (vendor or device or cls):
        return None
    return {"bdf": dev.name, "vendor": vendor, "device": device, "class": cls}


def _probe_pci(sys_root: Path = Path("/sys")) -> dict[str, Any]:
    pci_dir = sys_root / "bus/pci/devices"
    devices: list[dict[str, str]] = []
    has_ivshmem = has_gpu = has_infiniband = has_daq_accel = False
    nic_count = 0
    if pci_dir.is_dir():
        for dev in sorted(pci_dir.iterdir()):
            entry = _read_pci_device_entry(dev)
            if entry is None:
                continue
            devices.append(entry)
            v, d, c = entry["vendor"], entry["device"], entry["class"]
            has_ivshmem = has_ivshmem or (v == "0x1af4" and d == "0x1110")
            has_gpu = has_gpu or c.startswith("0x03")
            has_infiniband = has_infiniband or c.startswith("0x0207")
            if c.startswith("0x02") and not c.startswith("0x0207"):
                nic_count += 1
            has_daq_accel = has_daq_accel or c.startswith("0x12") or (v in _DAQ_VENDORS)
    return {
        "device_count": len(devices),
        "devices": devices[:16],
        "has_ivshmem": has_ivshmem,
        "has_gpu": has_gpu,
        "has_infiniband": has_infiniband,
        "has_daq_accel": has_daq_accel,
        "pci_nic_count": nic_count,
    }


def _read_active_ipv4() -> tuple[str, str]:
    try:
        out = subprocess.check_output(["ip", "-o", "-4", "addr", "show"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != "lo":
                return parts[1], parts[3].split("/")[0]
    except Exception:
        pass
    return "none", "offline"


def _list_net_interfaces(net_dir: Path) -> list[dict[str, Any]]:
    interfaces: list[dict[str, Any]] = []
    if not net_dir.is_dir():
        return interfaces
    for iface in sorted(net_dir.iterdir()):
        if iface.name != "lo":
            state = _read_text_safe(iface / "operstate") or "unknown"
            interfaces.append({"name": iface.name, "operstate": state, "wireless": (iface / "wireless").is_dir()})
    return interfaces


def _probe_net(sys_root: Path = Path("/sys")) -> dict[str, Any]:
    interfaces = _list_net_interfaces(sys_root / "class/net")
    nic, ip_addr = _read_active_ipv4() if sys_root == Path("/sys") else ("none", "offline")
    if nic == "none" and interfaces:
        up_if = next((item for item in interfaces if item["operstate"] == "up"), None)
        chosen = up_if or interfaces[0]
        nic = chosen["name"]
        ip_addr = "up" if up_if else "offline"
    has_up = any(item["operstate"] == "up" for item in interfaces) or ip_addr != "offline"
    has_wireless = any(item["wireless"] for item in interfaces)
    return {"interfaces": interfaces, "nic": nic, "ip_addr": ip_addr, "has_up": has_up, "has_wireless": has_wireless}


def _probe_block(sys_root: Path = Path("/sys")) -> list[dict[str, Any]]:
    blk_dir = sys_root / "class/block"
    disks: list[dict[str, Any]] = []
    if not blk_dir.is_dir():
        return disks
    for dev in sorted(blk_dir.iterdir()):
        if dev.name.startswith(("loop", "ram", "zram")) or (dev / "partition").exists():
            continue
        raw_sz = _read_text_safe(dev / "size")
        sectors = int(raw_sz) if raw_sz.isdigit() else 0
        disks.append({
            "name": dev.name,
            "size_mb": (sectors * 512) // (1024 * 1024),
            "removable": _read_text_safe(dev / "removable") == "1",
        })
    return disks


def _parse_fb_dimensions(fb_sys: Path) -> tuple[int, int]:
    vsize = _read_text_safe(fb_sys / "virtual_size")
    if "," in vsize:
        parts = vsize.split(",", 1)
        if parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    modes = _read_text_safe(fb_sys / "modes")
    match = re.search(r"(\d+)x(\d+)", modes)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _probe_display(sys_root: Path = Path("/sys"), dev_root: Path = Path("/dev")) -> dict[str, Any]:
    fb_sys = sys_root / "class/graphics/fb0"
    fb_present = fb_sys.is_dir() or (dev_root / "fb0").exists()
    width, height = _parse_fb_dimensions(fb_sys) if fb_sys.is_dir() else (0, 0)
    raw_bpp = _read_text_safe(fb_sys / "bits_per_pixel") if fb_sys.is_dir() else ""
    bpp = int(raw_bpp) if raw_bpp.isdigit() else 0
    name = _read_text_safe(fb_sys / "name") if fb_sys.is_dir() else ""
    return {"fb_present": fb_present, "width": width, "height": height, "bpp": bpp, "name": name}


def _has_cap_bit(cap_hex: str, bit: int) -> bool:
    words = cap_hex.split()
    if not words:
        return False
    word_idx = len(words) - 1 - (bit // 64)
    if word_idx < 0 or word_idx >= len(words):
        return False
    try:
        return bool((int(words[word_idx], 16) >> (bit % 64)) & 1)
    except ValueError:
        return False


def _scan_sys_input_device(dev_dir: Path) -> tuple[bool, bool, bool, bool]:
    name = _read_text_safe(dev_dir / "name").lower()
    k_cap = _read_text_safe(dev_dir / "capabilities/key")
    r_cap = _read_text_safe(dev_dir / "capabilities/rel")
    a_cap = _read_text_safe(dev_dir / "capabilities/abs")
    kbd = _has_cap_bit(k_cap, 1) or _has_cap_bit(k_cap, 16) or _has_cap_bit(k_cap, 28)
    rel = _has_cap_bit(r_cap, 0) or _has_cap_bit(r_cap, 1)
    absp = _has_cap_bit(a_cap, 0) or _has_cap_bit(a_cap, 1)
    touch = _has_cap_bit(k_cap, 330) or _has_cap_bit(a_cap, 53) or ("touch" in name)
    return kbd, rel, absp, touch


def _probe_input(sys_root: Path = Path("/sys"), dev_root: Path = Path("/dev")) -> dict[str, Any]:
    ev_dir = dev_root / "input"
    dev_events = len(list(ev_dir.glob("event*"))) if ev_dir.is_dir() else 0
    has_kbd = has_rel = has_abs = has_touch = False
    cls_in = sys_root / "class/input"
    if cls_in.is_dir():
        for ev in sorted(cls_in.glob("event*")):
            kbd, rel, absp, touch = _scan_sys_input_device(ev / "device")
            has_kbd = has_kbd or kbd
            has_rel = has_rel or rel
            has_abs = has_abs or absp
            has_touch = has_touch or touch
    serial_n = len(list(dev_root.glob("ttyUSB*"))) + len(list(dev_root.glob("ttyACM*"))) if dev_root.is_dir() else 0
    return {
        "event_count": dev_events,
        "has_keyboard": has_kbd,
        "has_rel_pointer": has_rel,
        "has_abs_pointer": has_abs,
        "has_touch": has_touch,
        "field_serial_count": serial_n,
        "has_field_serial": serial_n > 0,
    }


def _gate_cpu(cpu: dict[str, Any]) -> dict[str, str]:
    arch, cores = cpu["arch"], cpu["core_count"]
    if arch in _PRIMARY_ARCHES and cores >= 2:
        return {"status": "PASS", "detail": f"{arch} {cores}C"}
    if (arch in _PRIMARY_ARCHES and cores == 1) or (arch in _SECONDARY_ARCHES and cores >= 1):
        return {"status": "DEGRADED", "detail": f"{arch} {cores}C (reduced concurrency)"}
    return {"status": "UNSUPPORTED", "detail": f"arch={arch or 'unknown'} cores={cores}"}


def _gate_ram(mem: dict[str, int]) -> dict[str, str]:
    mb = mem["ram_total_mb"]
    if mb >= 512:
        return {"status": "PASS", "detail": f"{mb} MB RAM"}
    if mb >= 128:
        return {"status": "DEGRADED", "detail": f"{mb} MB RAM (compact footprint)"}
    return {"status": "UNSUPPORTED", "detail": f"{mb} MB RAM (<128 MB minimum)"}


def _gate_storage(state_dir: Path | None, disk_label: str) -> dict[str, str]:
    if state_dir is None:
        return {"status": "DEGRADED", "detail": "state_dir unspecified"}
    probe = state_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not os.access(probe, os.W_OK):
        return {"status": "UNSUPPORTED", "detail": f"{state_dir} not writable"}
    low = disk_label.lower()
    if "ephemeral" in low or "tmpfs" in low:
        return {"status": "DEGRADED", "detail": f"{disk_label} (volatile)"}
    return {"status": "PASS", "detail": disk_label}


def _gate_display(disp: dict[str, Any]) -> dict[str, str]:
    w, h, bpp = disp["width"], disp["height"], disp["bpp"]
    if disp["fb_present"] and w >= 640 and h >= 480 and bpp in (0, 32):
        return {"status": "PASS", "detail": f"fb0 {w}x{h}@{bpp or 32}bpp"}
    if disp["fb_present"]:
        return {"status": "DEGRADED", "detail": f"fb0 {w}x{h}@{bpp}bpp (compact/micro fallback)"}
    return {"status": "DEGRADED", "detail": "headless serial/text fallback (no /dev/fb0)"}


def _gate_input(inp: dict[str, Any]) -> dict[str, str]:
    has_ptr = inp["has_rel_pointer"] or inp["has_abs_pointer"] or inp["has_touch"]
    if inp["has_keyboard"] and has_ptr:
        return {"status": "PASS", "detail": f"{inp['event_count']} evdev devices (kbd+ptr)"}
    if inp["has_keyboard"] or has_ptr or inp["event_count"] > 0:
        return {"status": "DEGRADED", "detail": f"partial input ({inp['event_count']} evdev)"}
    return {"status": "DEGRADED", "detail": "no evdev input (serial shell fallback)"}


def _gate_network(net: dict[str, Any]) -> dict[str, str]:
    if net["has_up"]:
        return {"status": "PASS", "detail": f"{net['nic']} ({net['ip_addr']})"}
    if net["interfaces"]:
        return {"status": "DEGRADED", "detail": f"{net['nic']} down/airgapped"}
    return {"status": "DEGRADED", "detail": "airgapped zero-token mode (no NIC)"}


def _gate_uma(uma_shm_ok: bool, uma_9p_mounted: bool) -> dict[str, str]:
    if uma_shm_ok and uma_9p_mounted:
        return {"status": "PASS", "detail": "ivshmem BAR2 + virtio-9p active"}
    if uma_shm_ok or uma_9p_mounted:
        return {"status": "DEGRADED", "detail": f"partial UMA (shm={uma_shm_ok}, 9p={uma_9p_mounted})"}
    return {"status": "DEGRADED", "detail": "local PRIVATE fallback (no hardware UMA)"}


def _evaluate_safety_gates(
    probe: dict[str, Any],
    state_dir: Path | None,
    disk_label: str,
    uma_shm_ok: bool,
    uma_9p_mounted: bool,
) -> tuple[dict[str, dict[str, str]], str]:
    gates = {
        "cpu_arch": _gate_cpu(probe["cpu"]),
        "ram_headroom": _gate_ram(probe["memory"]),
        "persistent_storage": _gate_storage(state_dir, disk_label),
        "display_fb": _gate_display(probe["display"]),
        "input_devices": _gate_input(probe["input"]),
        "network": _gate_network(probe["net"]),
        "hardware_uma": _gate_uma(uma_shm_ok, uma_9p_mounted),
    }
    statuses = {g["status"] for g in gates.values()}
    if "UNSUPPORTED" in statuses:
        overall = "UNSUPPORTED"
    elif "DEGRADED" in statuses:
        overall = "DEGRADED"
    else:
        overall = "PASS"
    return gates, overall


def _fb_orientation(disp: dict[str, Any]) -> str:
    if not disp["fb_present"]:
        return "headless"
    w, h = disp["width"], disp["height"]
    if (0 < w <= 400) or (0 < h <= 400):
        return "micro"
    if h >= w > 0:
        return "portrait"
    return "landscape"


def _is_micro_hud(disp: dict[str, Any]) -> bool:
    if not disp["fb_present"]:
        return False
    w, h = disp["width"], disp["height"]
    return (0 < w <= 400) or (0 < h <= 400)


def _is_portrait_phone(disp: dict[str, Any], inp: dict[str, Any], dmi: dict[str, Any], uma_both: bool) -> bool:
    w, h = disp["width"], disp["height"]
    if not (disp["fb_present"] and h >= w > 0):
        return False
    narrow_non_uma = (w <= 600) and (not uma_both)
    return inp["has_touch"] or narrow_non_uma or ("phone" in dmi["product_name"].lower())


def _is_sar_edge(inp: dict[str, Any], ram: int, cores: int, cmdline: str) -> bool:
    if os.environ.get("ZOE_HW_PROFILE", "").upper() == "SAR_COMPANION_EDGE":
        return True
    if "zoe.profile=sar" in cmdline:
        return True
    return inp["has_field_serial"] and (ram <= 4096) and (cores <= 8)


def _is_beowulf_node(cores: int, ram: int, pci: dict[str, Any], dmi: dict[str, Any]) -> bool:
    if cores >= 16 or pci["has_infiniband"]:
        return True
    if cores >= 12 and ram >= 16384:
        return True
    return (dmi["chassis_type"] in {"17", "23"}) and (cores >= 8)


def _is_edge_sbc(cpu: dict[str, Any], dmi: dict[str, Any], disp: dict[str, Any], ram: int, cores: int) -> bool:
    if cpu["arch"] in {"aarch64", "arm64", "armv7l", "riscv64"}:
        return True
    dt_low = dmi["devicetree_model"].lower()
    if any(t in dt_low for t in _SBC_TOKENS):
        return True
    if dmi["is_vm"] or (not disp["fb_present"]):
        return False
    return (128 <= ram <= 2048) and (1 <= cores <= 4)


def _is_headless_daq(disp: dict[str, Any], pci: dict[str, Any], net: dict[str, Any], ram: int) -> bool:
    if disp["fb_present"]:
        return False
    return pci["has_daq_accel"] or (len(net["interfaces"]) >= 2 and ram >= 2048)


def _is_kvm_uma(disp: dict[str, Any], dmi: dict[str, Any], pci: dict[str, Any], uma_shm_ok: bool, uma_9p_mounted: bool) -> bool:
    if uma_shm_ok or uma_9p_mounted or pci["has_ivshmem"]:
        return True
    return dmi["is_vm"] and disp["fb_present"]


def _select_hw_profile(
    probe: dict[str, Any],
    uma_shm_ok: bool,
    uma_9p_mounted: bool,
    cmdline_str: str,
) -> str:
    cpu, mem, dmi = probe["cpu"], probe["memory"], probe["dmi"]
    pci, net, disp, inp = probe["pci"], probe["net"], probe["display"], probe["input"]
    cores, ram = cpu["core_count"], mem["ram_total_mb"]
    if _is_micro_hud(disp):
        return "MICRO_HUD_HEADLAMP"
    if _is_portrait_phone(disp, inp, dmi, uma_shm_ok and uma_9p_mounted):
        return "PORTRAIT_PHONE_TOUCH"
    if _is_sar_edge(inp, ram, cores, cmdline_str):
        return "SAR_COMPANION_EDGE"
    if _is_beowulf_node(cores, ram, pci, dmi):
        return "BEOWULF_COMPUTE_NODE"
    if _is_headless_daq(disp, pci, net, ram):
        return "HEADLESS_DAQ_NODE"
    if _is_edge_sbc(cpu, dmi, disp, ram, cores):
        return "EDGE_SBC_PI"
    if _is_kvm_uma(disp, dmi, pci, uma_shm_ok, uma_9p_mounted):
        return "KVM_UMA_SPLIT"
    if disp["fb_present"] and (not dmi["is_vm"]) and (disp["bpp"] in (0, 32)):
        return "LAPTOP_BARE_METAL"
    return "HEADLESS_SAFE_FALLBACK"


def _build_hw_recommendations(
    profile: str,
    probe: dict[str, Any],
    uma_shm_ok: bool,
    uma_9p_mounted: bool,
) -> dict[str, Any]:
    cores, ram = probe["cpu"]["core_count"], probe["memory"]["ram_total_mb"]
    disp, net = probe["display"], probe["net"]
    orient_map = {
        "MICRO_HUD_HEADLAMP": "micro",
        "PORTRAIT_PHONE_TOUCH": "portrait",
        "HEADLESS_DAQ_NODE": "headless",
        "HEADLESS_SAFE_FALLBACK": "headless",
    }
    orientation = orient_map.get(profile, _fb_orientation(disp))
    budget_map = {
        "MICRO_HUD_HEADLAMP": 1,
        "PORTRAIT_PHONE_TOUCH": 1,
        "SAR_COMPANION_EDGE": 1,
        "BEOWULF_COMPUTE_NODE": min(7, max(3, cores // 4)),
        "HEADLESS_DAQ_NODE": min(4, max(1, cores // 2)),
        "EDGE_SBC_PI": 1 if ram < 1024 else 2,
        "KVM_UMA_SPLIT": min(3, max(1, cores)),
        "LAPTOP_BARE_METAL": min(3, max(1, cores // 2)),
        "HEADLESS_SAFE_FALLBACK": 1,
    }
    workload_map = {
        "MICRO_HUD_HEADLAMP": "micro_hud_high_contrast",
        "PORTRAIT_PHONE_TOUCH": "touch_portrait_artline",
        "SAR_COMPANION_EDGE": "sar_telemetry_advisory",
        "BEOWULF_COMPUTE_NODE": "beowulf_parallel_atlas",
        "HEADLESS_DAQ_NODE": "daq_streaming_zero_token",
        "EDGE_SBC_PI": "edge_sbc_compact",
        "KVM_UMA_SPLIT": "split_uma_artline",
        "LAPTOP_BARE_METAL": "bare_metal_artline_neuro",
        "HEADLESS_SAFE_FALLBACK": "serial_gear1_minimal",
    }
    uma_tx = "pci_ivshmem_9p" if (uma_shm_ok and uma_9p_mounted) else ("shm_only" if uma_shm_ok else "local_private")
    net_tx = "wireless_lan" if net["has_wireless"] else ("ethernet_tcp" if net["has_up"] else "airgapped_zero_token")
    return {
        "orientation": orientation,
        "zo3_slot_budget": int(budget_map[profile]),
        "uma_transport": uma_tx,
        "net_transport": net_tx,
        "artline_neuro_workload": workload_map[profile],
        "advisory_note": "Advisory-only hardware telemetry; human operator/clinician/pilot retains sole authority.",
    }


def _format_hw_summary(probe: dict[str, Any], uma_shm_ok: bool, uma_9p_mounted: bool) -> str:
    cpu, mem = probe["cpu"], probe["memory"]
    disp, net = probe["display"], probe["net"]
    fb_tag = f"{disp['width']}x{disp['height']}" if (disp["fb_present"] and disp["width"] > 0) else ("FB" if disp["fb_present"] else "NONE")
    uma_tag = "OK" if (uma_shm_ok and uma_9p_mounted) else ("SHM" if uma_shm_ok else ("9P" if uma_9p_mounted else "LOC"))
    net_tag = "UP" if net["has_up"] else "OFF"
    raw = f"{cpu['arch']} {cpu['core_count']}C {mem['ram_total_mb']}M FB:{fb_tag} UMA:{uma_tag} NET:{net_tag}"
    return raw.encode("ascii", errors="replace").decode("ascii")[:64]


def observe_hardware(
    state_dir: Path | None = None,
    disk_label: str = "/dev/vda [ZOE-STATE]",
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
    dev_root: Path = Path("/dev"),
    uma_shm_ok: bool | None = None,
    uma_9p_mounted: bool | None = None,
    uma_dir: Path | None = None,
    arch_override: str | None = None,
) -> dict[str, Any]:
    """Read-only Initial Hardware Observation Diagnostic & Safety Gate Check."""
    cpu = _probe_cpu(proc_root, arch_override=arch_override)
    mem = _probe_memory(proc_root)
    dmi = _probe_dmi_and_dt(sys_root, has_hypervisor=bool(cpu["has_hypervisor"]))
    pci = _probe_pci(sys_root)
    net = _probe_net(sys_root)
    block = _probe_block(sys_root)
    disp = _probe_display(sys_root, dev_root)
    inp = _probe_input(sys_root, dev_root)
    probe = {"cpu": cpu, "memory": mem, "dmi": dmi, "pci": pci, "net": net, "block": block, "display": disp, "input": inp}
    shm_ok = pci["has_ivshmem"] if uma_shm_ok is None else bool(uma_shm_ok)
    if uma_9p_mounted is None:
        u_dir = uma_dir if uma_dir is not None else Path(os.environ.get("ZOE_UMA_DIR", "/mnt/uma"))
        p9_ok = u_dir.is_dir() and (u_dir / "uma_state.json").is_file()
    else:
        p9_ok = bool(uma_9p_mounted)
    gates, safety_overall = _evaluate_safety_gates(probe, state_dir, disk_label, shm_ok, p9_ok)
    cmdline = _read_text_safe(proc_root / "cmdline")
    profile = _select_hw_profile(probe, shm_ok, p9_ok, cmdline)
    recs = _build_hw_recommendations(profile, probe, shm_ok, p9_ok)
    return {
        "schema": "zoe-hw-observation/v1",
        "observed_ts": int(time.time()),
        "profile": profile,
        "safety_overall": safety_overall,
        "hw_summary": _format_hw_summary(probe, shm_ok, p9_ok),
        "gates": gates,
        "recommendations": recs,
        **_CONSTITUTIONAL_FLAGS,
        "probe": probe,
    }


def _read_hw_telemetry(proc_root: Path = Path("/proc"), sys_root: Path = Path("/sys")) -> dict[str, Any]:
    cpu = _probe_cpu(proc_root)
    mem = _probe_memory(proc_root)
    net = _probe_net(sys_root)
    kernel = os.uname().release if hasattr(os, "uname") else "Linux-HAL"
    return {"cpu": cpu["short_model"], "ram_mb": mem["ram_total_mb"], "kernel": kernel, "nic": net["nic"], "ip_addr": net["ip_addr"]}


def _read_and_verify_chain_unlocked(chain_path: Path) -> tuple[list[dict[str, Any]], bool, str]:
    prior_records: list[dict[str, Any]] = []
    chain_intact = True
    prev_hash = "genesis"
    if not chain_path.is_file():
        return prior_records, chain_intact, prev_hash
    for raw in chain_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            chain_intact = False
            continue
        if not isinstance(rec, dict):
            chain_intact = False
            continue
        payload = {k: v for k, v in rec.items() if k != "sha256"}
        recomputed = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if rec.get("prev_sha") != prev_hash or rec.get("sha256") != recomputed:
            chain_intact = False
        prev_hash = str(rec.get("sha256", prev_hash))
        prior_records.append(rec)
    return prior_records, chain_intact, prev_hash


def _verify_and_append_boot_chain(state_dir: Path, hw: dict[str, Any]) -> dict[str, Any]:
    chain_path = state_dir / "boot_chain.jsonl"
    with _state_lock(state_dir):
        prior_records, chain_intact, prev_hash = _read_and_verify_chain_unlocked(chain_path)
        boot_count = len(prior_records) + 1
        entry: dict[str, Any] = {
            "boot_count": boot_count,
            "prev_sha": prev_hash,
            "kernel": hw["kernel"],
            "cpu": hw["cpu"],
            "ram_mb": hw["ram_mb"],
            "nic": hw["nic"],
            "ip_addr": hw["ip_addr"],
            "ts_epoch": int(time.time()),
        }
        digest = hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        entry["sha256"] = digest
        with chain_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
    return {
        "boot_count": boot_count,
        "restored_from_prior": bool(prior_records and chain_intact),
        "chain_intact": chain_intact,
        "chain_sha": digest,
        "prev_sha": prev_hash,
    }


def _read_drawer_notes_unlocked(drawer_path: Path) -> list[dict[str, Any]]:
    if not drawer_path.is_file():
        return []
    try:
        parsed = json.loads(drawer_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _build_emblem_artline_doc() -> ArtlineDocument:
    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0f1020", stroke="#e63956", width=2)
    motif = [[482, 190], [500, 160], [518, 190], [500, 230]]
    for poly in rotate_ring(motif, 500, 350, count=12):
        doc.add_element("path", points=poly, closed=True, smooth=False, fill="#2d1030", stroke="#5ce1e6", width=1.6)
    z0 = [[320, 280], [420, 280], [340, 420], [420, 420]]
    o0 = [[580 + 50 * math.cos(2 * 3.14159 * i / 12), 350 + 60 * math.sin(2 * 3.14159 * i / 12)] for i in range(12)]
    for frame in blend_polygons(z0, o0, steps=6, n_samples=24, auto_align=True):
        doc.add_element("path", points=frame, closed=True, smooth=False, fill="none", stroke="#e63956", width=1.4)
    return doc


def _export_artline_atomic(doc: ArtlineDocument, target: Path, kind: str) -> None:
    tmp = target.parent / f".{target.name}.tmp.{os.getpid()}.{threading.get_ident()}"
    try:
        doc.export(tmp, kind=kind)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _ensure_artline_vault_unlocked(vault: Path) -> tuple[Path, Path, bool]:
    vault.mkdir(parents=True, exist_ok=True)
    svg_path, gem_path, rsc_path = vault / "zoe_os_emblem.svg", vault / "zoe_os_emblem.gem", vault / "ZOE_GEM.RSC"
    prior_vault_present = svg_path.exists() and gem_path.exists() and rsc_path.exists()
    if not svg_path.exists() or not gem_path.exists():
        doc = _build_emblem_artline_doc()
        if not svg_path.exists():
            _export_artline_atomic(doc, svg_path, "svg")
        if not gem_path.exists():
            _export_artline_atomic(doc, gem_path, "gem")
    if not rsc_path.exists():
        _atomic_write_bytes(rsc_path, build_atari_rsc_bytes())
    return gem_path, rsc_path, prior_vault_present


def _read_or_repair_rsc_unlocked(rsc_path: Path) -> tuple[dict[str, Any], bool]:
    if rsc_path.is_file():
        try:
            parsed = parse_atari_rsc(rsc_path.read_bytes())
            if parsed.get("size_matches_rsh_rssize"):
                return parsed, True
        except (OSError, ValueError, struct.error, IndexError):
            pass
    _atomic_write_bytes(rsc_path, build_atari_rsc_bytes())
    return parse_atari_rsc(rsc_path.read_bytes()), False


def _sync_drawer_and_artline_vault(state_dir: Path, boot_count: int) -> dict[str, Any]:
    drawer_path = state_dir / "nick_drawer.json"
    with _state_lock(state_dir):
        notes = _read_drawer_notes_unlocked(drawer_path)
        if not notes:
            notes.append({"boot": boot_count, "author": "Nicholas", "text": "Zoe-GEM OS Boot #1: First bare-metal retention seal."})
            _atomic_write_text(drawer_path, json.dumps(notes, indent=2))
        gem_path, rsc_path, prior_vault_present = _ensure_artline_vault_unlocked(state_dir / "artline")
        parsed_rsc, rsc_intact = _read_or_repair_rsc_unlocked(rsc_path)
        gem_sha = hashlib.sha256(gem_path.read_bytes()).hexdigest()[:16]
        art_n = sum(1 for p in (state_dir / "artline").iterdir() if not p.name.startswith("."))
        rsc_bytes = rsc_path.stat().st_size
    return {
        "drawer_count": len(notes),
        "drawer_latest": str(notes[-1].get("text", "(empty)")) if notes else "(empty)",
        "artline_files": art_n,
        "artline_sha": gem_sha,
        "rsc_bytes": rsc_bytes,
        "rsc_icons": parsed_rsc.get("n_icons", 0),
        "vault_restored": prior_vault_present and rsc_intact,
    }


def _parse_cmdline_kv(key: str, default: str, proc_root: Path = Path("/proc")) -> str:
    tokens = _read_text_safe(proc_root / "cmdline").split()
    prefix = f"{key}="
    for tok in tokens:
        if tok.startswith(prefix):
            return tok[len(prefix):].strip() or default
    return default


def _resolve_uma_bridge(
    state_dir: Path,
    sys_root: Path = Path("/sys"),
    uma_dir: Path | None = None,
) -> tuple[UmaBridge, Path | None, bool]:
    resolved_uma = uma_dir if uma_dir is not None else Path(os.environ.get("ZOE_UMA_DIR", "/mnt/uma"))
    bar2 = find_guest_ivshmem_bar2(sys_root / "bus/pci/devices")
    uma_9p_mounted = resolved_uma.is_dir() and (resolved_uma / "uma_state.json").is_file()
    bridge = UmaBridge(resolved_uma, shm_path=bar2) if uma_9p_mounted else UmaBridge(state_dir / "uma_local", shm_path=bar2)
    return bridge, bar2, uma_9p_mounted


def _sync_9p_crossing(bridge: UmaBridge, state_dir: Path, node_id: int, boot_count: int) -> tuple[str, bool]:
    st = bridge.read_state()
    uma_gate = str(st.get("gate", "PRIVATE"))
    if not st.get("nick_allow"):
        return uma_gate, False
    st = bridge.set_consent("zoe", True, reason=f"zo3_node{node_id}_boot{boot_count}_mutual_research")
    uma_gate = str(st["gate"])
    gem_src = state_dir / "artline" / "zoe_os_emblem.gem"
    if gem_src.is_file() and uma_gate == "SHARED":
        try:
            bridge.transfer_file("zoe", gem_src)
            return uma_gate, True
        except PermissionError:
            return str(bridge.read_state().get("gate", uma_gate)), False
    return uma_gate, False


def _sync_hardware_uma(
    state_dir: Path,
    boot_count: int,
    chain_sha: str,
    chain_intact: bool,
    ip_addr: str,
    node_id: int,
    theme: str,
    sys_root: Path = Path("/sys"),
    uma_dir: Path | None = None,
) -> dict[str, Any]:
    """Attach PCI ivshmem 4 MB RAM BAR (Slot 0 + Node Slot 1..3) + PCI virtio-9p /mnt/uma airlock."""
    bridge, bar2, uma_9p_mounted = _resolve_uma_bridge(state_dir, sys_root=sys_root, uma_dir=uma_dir)
    uma_gate, uma_transfer_ok = _sync_9p_crossing(bridge, state_dir, node_id, boot_count) if uma_9p_mounted else ("PRIVATE", False)
    uma_shm_ok, zo3_peers = False, 0
    if bar2 is not None:
        hb_payload = {
            "node_id": node_id,
            "boot_count": boot_count,
            "chain_intact": chain_intact,
            "chain_sha": chain_sha[:16],
            "ip_addr": ip_addr,
            "gate": uma_gate,
            "theme": theme,
        }
        uma_shm_ok = bridge.write_shm_heartbeat(f"zo3-node-{node_id}", hb_payload, slot=node_id)
        if node_id == 1:
            bridge.write_shm_heartbeat("zoe-gem-os", hb_payload, slot=0)
        slots = bridge.read_all_zo3_slots()
        zo3_peers = sum(1 for k in (1, 2, 3) if k in slots and k != node_id)
    return {
        "node_id": node_id,
        "theme": theme,
        "uma_9p_mounted": uma_9p_mounted,
        "uma_9p": uma_9p_mounted,
        "uma_shm_ok": uma_shm_ok,
        "uma_shm": f"4MB BAR2 S{node_id}" if uma_shm_ok else "offline",
        "uma_gate": uma_gate,
        "uma_transfer_ok": uma_transfer_ok,
        "zo3_slot": node_id,
        "zo3_peers": zo3_peers,
    }


def _read_node_identity(state_dir: Path, proc_root: Path = Path("/proc")) -> tuple[int, str]:
    id_cfg = _load_boot_report(state_dir / "node_identity.json") or {}
    node_raw = str(os.environ.get("ZOE_NODE_ID") or id_cfg.get("node_id") or _parse_cmdline_kv("zoe.node", "1", proc_root))
    node_id = int(node_raw) if node_raw.isascii() and node_raw.isdigit() and 1 <= int(node_raw) <= 3 else 1
    default_theme = "amber" if node_id == 2 else "gem"
    theme = str(os.environ.get("ZOE_THEME") or id_cfg.get("theme") or _parse_cmdline_kv("zoe.theme", default_theme, proc_root))
    return node_id, theme


def _resolve_sister_metadata(hw_profile: str) -> dict[str, Any]:
    try:
        from guiai.gem.zoe_sisters import SAFETY_INVARIANTS, list_sisters, recommend_sisters_for_hardware

        all_sisters = list_sisters()
        rec = recommend_sisters_for_hardware(hw_profile)
        lead = rec[0] if rec else (all_sisters[0] if all_sisters else None)
        safety_ok = (
            SAFETY_INVARIANTS.get("clinical_action_authorized") is False
            and SAFETY_INVARIANTS.get("sentience_claimed") is False
        )
        return {
            "sisters_available": True,
            "sisters_count": len(all_sisters),
            "hw_lead_sister": lead.name if lead else "Zoe",
            "hw_lead_signet": lead.signet if lead else "ruby",
            "hw_recommended_sisters": [s.name for s in rec],
            "council_leads": ["Mono", "Zoe", "Eliza"],
            "sisters_safety_ok": bool(safety_ok),
        }
    except ImportError:
        return {
            "sisters_available": False,
            "sisters_count": 0,
            "hw_lead_sister": "Zoe",
            "hw_lead_signet": "ruby",
            "hw_recommended_sisters": [],
            "council_leads": ["Mono", "Zoe", "Eliza"],
            "sisters_safety_ok": True,
        }


def run_boot_sync(
    state_dir: Path,
    run_json: Path,
    disk_label: str = "/dev/vda [ZOE-STATE]",
    *,
    proc_root: Path = Path("/proc"),
    sys_root: Path = Path("/sys"),
    dev_root: Path = Path("/dev"),
    uma_dir: Path | None = None,
    arch_override: str | None = None,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    node_id, theme = _read_node_identity(state_dir, proc_root=proc_root)
    hw = _read_hw_telemetry(proc_root=proc_root, sys_root=sys_root)
    chain = _verify_and_append_boot_chain(state_dir, hw)
    vault = _sync_drawer_and_artline_vault(state_dir, chain["boot_count"])
    uma = _sync_hardware_uma(
        state_dir,
        chain["boot_count"],
        chain["chain_sha"],
        chain["chain_intact"],
        hw["ip_addr"],
        node_id,
        theme,
        sys_root=sys_root,
        uma_dir=uma_dir,
    )
    hw_obs = observe_hardware(
        state_dir=state_dir,
        disk_label=disk_label,
        proc_root=proc_root,
        sys_root=sys_root,
        dev_root=dev_root,
        uma_shm_ok=uma["uma_shm_ok"],
        uma_9p_mounted=uma["uma_9p_mounted"],
        uma_dir=uma_dir,
        arch_override=arch_override,
    )
    sisters = _resolve_sister_metadata(hw_obs["profile"])
    with _state_lock(state_dir):
        _atomic_write_text(state_dir / "hw_observation.json", json.dumps(hw_obs, indent=2))
    report = {
        "os_name": "Zoe-GEM OS",
        "os_version": "1.0",
        "disk": disk_label,
        "state_dev": disk_label,
        **hw,
        "cpu_model": hw["cpu"],
        "mem_total_mb": hw["ram_mb"],
        "kernel_release": hw["kernel"],
        "net_if": hw["nic"],
        "net_ip": hw["ip_addr"],
        **chain,
        "self_restored": chain["restored_from_prior"],
        "boot_sha256": chain["chain_sha"],
        "prev_boot_sha256": chain["prev_sha"],
        **vault,
        **uma,
        "hw_profile": hw_obs["profile"],
        "hw_safety_overall": hw_obs["safety_overall"],
        "hw_summary": hw_obs["hw_summary"],
        "hw_orientation": hw_obs["recommendations"]["orientation"],
        "hw_zo3_budget": hw_obs["recommendations"]["zo3_slot_budget"],
        **sisters,
        **_CONSTITUTIONAL_FLAGS,
    }
    _atomic_write_text(run_json, json.dumps(report, indent=2))
    if hasattr(os, "sync"):
        os.sync()
    return report


def _load_boot_report(run_json: Path) -> dict[str, Any] | None:
    if not run_json.is_file():
        return None
    try:
        parsed = json.loads(run_json.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except (OSError, ValueError):
        return None


def _read_fallback_chain_summary(state_dir: Path) -> tuple[int, str, str, bool]:
    chain_path = state_dir / "boot_chain.jsonl"
    with _state_lock(state_dir):
        prior_records, chain_intact, prev_hash = _read_and_verify_chain_unlocked(chain_path)
    if not prior_records:
        return 0, "0" * 16, "genesis", chain_intact
    last = prior_records[-1]
    try:
        boot_count = int(last.get("boot_count", len(prior_records)))
    except (ValueError, TypeError):
        boot_count = len(prior_records)
        chain_intact = False
    return boot_count, str(last.get("sha256", prev_hash)), str(last.get("prev_sha", "genesis")), chain_intact


def _build_fallback_report(state_dir: Path, disk_label: str) -> dict[str, Any]:
    hw = _read_hw_telemetry()
    obs = observe_hardware(state_dir=state_dir, disk_label=disk_label)
    boot_count, chain_sha, prev_sha, chain_intact = _read_fallback_chain_summary(state_dir)
    notes = _read_drawer_notes_unlocked(state_dir / "nick_drawer.json")
    sisters = _resolve_sister_metadata(obs["profile"])
    restored = bool(boot_count > 1 and chain_intact)
    return {
        "os_name": "Zoe-GEM OS",
        "os_version": "1.0",
        "disk": disk_label,
        "state_dev": disk_label,
        **hw,
        "cpu_model": hw["cpu"],
        "mem_total_mb": hw["ram_mb"],
        "kernel_release": hw["kernel"],
        "net_if": hw["nic"],
        "net_ip": hw["ip_addr"],
        "boot_count": boot_count,
        "restored_from_prior": restored,
        "self_restored": restored,
        "chain_intact": chain_intact,
        "chain_sha": chain_sha,
        "boot_sha256": chain_sha,
        "prev_sha": prev_sha,
        "prev_boot_sha256": prev_sha,
        "drawer_count": len(notes),
        "drawer_latest": str(notes[-1].get("text", "(empty)")) if notes else "(empty)",
        "hw_profile": obs["profile"],
        "hw_safety_overall": obs["safety_overall"],
        "hw_summary": obs["hw_summary"],
        "hw_orientation": obs["recommendations"]["orientation"],
        "hw_zo3_budget": obs["recommendations"]["zo3_slot_budget"],
        **sisters,
        **_CONSTITUTIONAL_FLAGS,
    }


def _cmd_drawer_list(state_dir: Path) -> None:
    with _state_lock(state_dir):
        notes = _read_drawer_notes_unlocked(state_dir / "nick_drawer.json")
    if not notes:
        print("  (drawer empty)")
        return
    for idx, item in enumerate(notes, 1):
        print(f"  [{idx}] boot #{item.get('boot')}: {item.get('text')}")


def _cmd_drawer_add(state_dir: Path, report: dict[str, Any], text: str) -> None:
    drawer_path = state_dir / "nick_drawer.json"
    with _state_lock(state_dir):
        notes = _read_drawer_notes_unlocked(drawer_path)
        notes.append({"boot": report.get("boot_count", 0), "author": "Nicholas", "text": text.strip()})
        _atomic_write_text(drawer_path, json.dumps(notes, indent=2))
    if hasattr(os, "sync"):
        os.sync()
    print(f"  Saved to hardware drawer ({len(notes)} notes total).")


def _load_hw_observation(state_dir: Path) -> dict[str, Any]:
    obs_path = state_dir / "hw_observation.json"
    if obs_path.is_file():
        try:
            loaded = json.loads(obs_path.read_text(encoding="utf-8"))
            if (
                isinstance(loaded, dict)
                and isinstance(loaded.get("recommendations"), dict)
                and isinstance(loaded.get("gates"), dict)
                and all(isinstance(v, dict) for v in loaded["gates"].values())
            ):
                return loaded
        except (OSError, ValueError):
            pass
    return observe_hardware(state_dir=state_dir)


def _cmd_hw(state_dir: Path) -> None:
    obs = _load_hw_observation(state_dir)
    raw_recs = obs.get("recommendations")
    recs = raw_recs if isinstance(raw_recs, dict) else {}
    raw_gates = obs.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    print(f"Hardware Observation :: profile={obs.get('profile')} · safety={obs.get('safety_overall')}")
    print(f"  Summary      : {obs.get('hw_summary', '')}")
    print(f"  Orientation  : {recs.get('orientation')} · ZO3 budget={recs.get('zo3_slot_budget')} · workload={recs.get('artline_neuro_workload')}")
    print(f"  Transports   : uma={recs.get('uma_transport')} · net={recs.get('net_transport')}")
    for gate_name, gate_info in gates.items():
        info = gate_info if isinstance(gate_info, dict) else {}
        print(f"  [{str(info.get('status', 'DEGRADED')):11s}] {str(gate_name):<18s} : {str(info.get('detail', ''))}")
    print(
        f"  Safety Flags : clinical_action_authorized={obs.get('clinical_action_authorized', False)} "
        f"flight_control_authorized={obs.get('flight_control_authorized', False)} "
        f"cure_claim={obs.get('cure_claim', False)} sentience_claimed={obs.get('sentience_claimed', False)} "
        f"tokens_used={obs.get('tokens_used', 0)}"
    )


def _cmd_artline(state_dir: Path) -> None:
    vault = state_dir / "artline"
    if not vault.is_dir():
        print("  (artline vault empty)")
        return
    for p in sorted(vault.glob("*")):
        if not p.name.startswith("."):
            print(f"  {p.name:24s} {p.stat().st_size:>8,} bytes")


def _cmd_wifi(cmd: str) -> None:
    parts = cmd.split(maxsplit=2)
    if len(parts) < 3:
        print("  Usage: wifi <SSID> <PASSWORD>")
    else:
        subprocess.call(["/bin/zoe-wifi", parts[1], parts[2]])


def _cmd_sisters(report: dict[str, Any]) -> None:
    profile = str(report.get("hw_profile", "KVM_UMA_SPLIT"))
    meta = _resolve_sister_metadata(profile)
    print(f"Zoe Sisters :: available={meta['sisters_available']} count={meta['sisters_count']} profile={profile}")
    print(f"  Lead Sister : {meta['hw_lead_sister']} ({meta['hw_lead_signet']})")
    print(f"  Council     : {', '.join(meta['council_leads'])}")
    if meta["hw_recommended_sisters"]:
        print(f"  Recommended : {', '.join(meta['hw_recommended_sisters'])}")


def _dispatch_shell_cmd(cmd: str, state_dir: Path, report: dict[str, Any]) -> bool:
    low = cmd.lower()
    if low in {"quit", "exit"}:
        return False
    exact = {
        "status": lambda: print(json.dumps(report, indent=2)),
        "hw": lambda: _cmd_hw(state_dir),
        "sisters": lambda: _cmd_sisters(report),
        "drawer": lambda: _cmd_drawer_list(state_dir),
        "artline": lambda: _cmd_artline(state_dir),
        "net": lambda: subprocess.call(["ip", "-4", "addr"]),
        "fb": lambda: subprocess.call(["/bin/zoe_gem_fb", "--interactive"]),
    }
    handler = exact.get(low)
    if handler is not None:
        handler()
    elif low.startswith("drawer add "):
        _cmd_drawer_add(state_dir, report, cmd[11:])
    elif low.startswith("wifi "):
        _cmd_wifi(cmd)
    elif low in {"reboot", "poweroff"}:
        if hasattr(os, "sync"):
            os.sync()
        subprocess.call([low, "-f"])
    else:
        print("  Commands: status | hw | sisters | drawer | drawer add <text> | artline | net | wifi <ssid> <psk> | fb | reboot | poweroff")
    return True


def run_interactive_shell(state_dir: Path, report: dict[str, Any]) -> None:
    print("\n======================================================================")
    print(f"  Zoe-GEM OS v1.0  ::  Boot #{report.get('boot_count', 0)}  (restored={report.get('restored_from_prior', False)})")
    print(f"  Hardware: {report.get('cpu', '')} · {report.get('ram_mb', 0)} MB RAM · NIC {report.get('nic', 'none')} ({report.get('ip_addr', 'offline')})")
    print(f"  Profile : {report.get('hw_profile', 'UNKNOWN')} ({report.get('hw_safety_overall', 'DEGRADED')}) · {report.get('hw_summary', '')}")
    print(f"  Disk    : {report.get('disk', '')} · SHA-256 {str(report.get('chain_sha', ''))[:16]}")
    print("  Commands: status | hw | sisters | drawer | drawer add <text> | artline | net | wifi <ssid> <psk> | fb | reboot | poweroff")
    print("======================================================================\n")
    while True:
        try:
            cmd = input("Zoe-OS ◠◡◠ ❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd and not _dispatch_shell_cmd(cmd, state_dir, report):
            break


def _run_uma_toggle(state_dir: Path, run_json: Path, node_id: int) -> int:
    bridge, bar2, uma_9p_mounted = _resolve_uma_bridge(state_dir)
    st = bridge.toggle_zoe_consent(reason=f"guest_toggle_node{node_id}")
    report = _load_boot_report(run_json)
    if report is not None:
        report["uma_gate"] = st["gate"]
        report["uma_9p_mounted"] = uma_9p_mounted
        report["uma_9p"] = uma_9p_mounted
        report["uma_shm_ok"] = bar2 is not None
        if bar2 is not None:
            report["uma_shm"] = f"4MB BAR2 S{node_id}"
        _atomic_write_text(run_json, json.dumps(report, indent=2))
    print(f"ZOE_OS_UMA_TOGGLE zoe_allow={st['zoe_allow']} nick_allow={st['nick_allow']} gate={st['gate']} audit_sha={st.get('audit_sha', '')}", flush=True)
    return 0


def _print_boot_telemetry(report: dict[str, Any]) -> None:
    print(f"ZOE_OS_BOOT_OK boot={report['boot_count']} restored={report['restored_from_prior']} chain_intact={report['chain_intact']} sha={report['chain_sha'][:16]}", flush=True)
    print(f"ZOE_OS_NET_OK nic={report['nic']} ip={report['ip_addr']}", flush=True)
    print(f"ZOE_OS_PERSIST_OK drawer={report['drawer_count']} artline_files={report['artline_files']} vault_restored={report['vault_restored']} rsc={report['rsc_bytes']}", flush=True)
    print(f"ZOE_OS_UMA_OK 9p={report['uma_9p_mounted']} shm={report['uma_shm_ok']} gate={report['uma_gate']} transferred={report['uma_transfer_ok']}", flush=True)
    print(f"ZOE_OS_HW_OK profile={report['hw_profile']} safety={report['hw_safety_overall']} orient={report['hw_orientation']}", flush=True)


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--boot", action="store_true")
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--uma-toggle", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    args, _ = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_cli_args(sys.argv[1:] if argv is None else argv)
    state_dir = Path(os.environ.get("ZOE_STATE_DIR", "/mnt/zoe-state"))
    run_json = Path(os.environ.get("ZOE_BOOT_JSON", "/run/zoe-boot-state.json"))
    disk_label = os.environ.get("ZOE_DISK_LABEL", "/dev/vda [ZOE-STATE]")
    if args.uma_toggle:
        node_id, _ = _read_node_identity(state_dir)
        return _run_uma_toggle(state_dir, run_json, node_id)
    if args.shell or (args.interactive and not args.boot):
        existing = _load_boot_report(run_json)
        if existing is not None or args.shell:
            report = existing if existing is not None else _build_fallback_report(state_dir, disk_label)
            run_interactive_shell(state_dir, report)
            return 0
    report = run_boot_sync(state_dir, run_json, disk_label=disk_label)
    _print_boot_telemetry(report)
    if args.interactive:
        run_interactive_shell(state_dir, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

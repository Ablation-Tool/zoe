"""Reproducible UEFI x86_64 Zoe-GEM OS ISO Builder & 2-Boot OVMF+KVM Verification Harness.

Builds a real bootable UEFI x86_64 ISO (`zoe-gem-os.iso` or `zoe-gem-os-lts.iso`) using:
  - Official Alpine Linux x86_64 `vmlinuz-virt` (fast KVM) or `vmlinuz-lts` (full Intel
    Tiger Lake i5-1145G7 bare-metal hardware: i915, vmd, nvme, iwlwifi AX201, USB, touchpads)
  - Exact `modules.dep` transitive kernel driver closure (+ Tiger Lake firmware for `lts`)
  - Statically-linked interactive native C `/dev/fb0` Digital Research GEM Desktop (`zoe_gem_fb`)
    with real hardware PS/2 & USB mouse cursor, keyboard, clickable p. 3-2 Toolkit, live
    bilateral-mirror Artline drawing canvas, persistent SVG export, and Nick's `/drawer` dialog
  - Static BusyBox + bundled pure-stdlib Python + Zoe GEM/Artline/RSC modules + PID 1 `/init`
  - Optional Wi-Fi stack (`wpa_supplicant` + `iw` + `/bin/zoe-wifi`) for `lts` bare-metal USB
  - Zero-risk 2-boot OVMF UEFI + KVM verification harness injecting real hardware mouse/key events
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any

from PIL import Image

_ALPINE_NETBOOT_BASE = "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/netboot"
_OVMF_CANDIDATES: tuple[Path, ...] = (
    Path("/usr/share/ovmf/OVMF.fd"),
    Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),
)
_KVM_DEVICE: Path = Path("/dev/kvm")
_DEFAULT_UMA_SHM = "/dev/shm/zoe-uma-bar.shm"
_GEOMETRY_PRESETS: dict[str, tuple[int, int]] = {
    "split": (920, 960),
    "full": (1280, 800),
    "portrait": (768, 1024),
    "phone": (544, 960),
}
_ZOE_PY_CLOSURE: tuple[str, ...] = (
    "__init__.py",
    "artline.py",
    "field.py",
    "geometry.py",
    "lume_header.py",
    "model.py",
    "render.py",
    "runner.py",
    "vdi.py",
    "volume.py",
    "zoe_atari_gem_rsc.py",
    "zoe_sisters.py",
)
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
_SKIP_STDLIB_DIRS: frozenset[str] = frozenset({
    "test",
    "tests",
    "idlelib",
    "tkinter",
    "turtledemo",
    "ensurepip",
    "pydoc_data",
    "__pycache__",
    "asyncio",
    "multiprocessing",
    "unittest",
    "_pyrepl",
    "sqlite3",
    "zoneinfo",
    "venv",
    "curses",
    "http",
    "urllib",
    "email",
    "html",
    "xmlrpc",
})

_VIRT_KMODS: tuple[str, ...] = (
    "crc32c_generic",
    "crc32c-intel",
    "libcrc32c",
    "crc16",
    "mbcache",
    "jbd2",
    "ext4",
    "9p",
    "9pnet",
    "9pnet_virtio",
    "fat",
    "vfat",
    "exfat",
    "nls_cp437",
    "nls_iso8859-1",
    "virtio_pci",
    "virtio_blk",
    "virtio_net",
    "virtio_input",
    "e1000",
    "e1000e",
    "af_packet",
    "bochs",
    "simpledrm",
    "nvme",
    "ahci",
    "xhci-pci",
    "usb-storage",
    "usbhid",
    "hid-generic",
    "usbkbd",
    "usbmouse",
    "i8042",
    "libps2",
    "psmouse",
    "mousedev",
    "evdev",
    "atkbd",
)

_LTS_EXTRA_KMODS: tuple[str, ...] = (
    "vmd",
    "i915",
    "iwlwifi",
    "iwlmvm",
    "cfg80211",
    "mac80211",
    "r8169",
    "i2c-hid-acpi",
    "hid-multitouch",
    "i2c-i801",
    "thunderbolt",
)

_PID1_INIT = """#!/bin/busybox sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
/bin/busybox --install -s /bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /run /tmp /mnt/zoe-state /mnt/uma /etc /var/run/wpa_supplicant
mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /tmp

echo "=== ZOE-GEM OS v1.0 :: PID 1 HARDWARE BRINGUP ==="

# Load essential HAL kernel modules (framebuffer, crc32c+ext4, 9p UMA, disk, input/mouse, net, Wi-Fi, Tiger Lake)
for mod in bochs simpledrm crc32c_generic crc32c-intel libcrc32c vmd nvme ahci virtio_pci virtio_blk \
           ext4 9pnet 9pnet_virtio 9p vfat exfat nls_cp437 nls_iso8859-1 \
           virtio_net e1000 e1000e r8169 af_packet cfg80211 mac80211 iwlwifi iwlmvm \
           i915 i2c-i801 thunderbolt \
           i8042 libps2 atkbd psmouse mousedev evdev xhci-pci usbhid hid-generic hid-multitouch i2c-hid-acpi usbkbd usbmouse virtio_input; do
    modprobe "$mod" 2>/dev/null || true
done
fb_wait=0
while [ ! -e /dev/fb0 ] && [ "$fb_wait" -lt 25 ]; do
    busybox usleep 40000 2>/dev/null || sleep 0.05
    fb_wait=$((fb_wait + 1))
done
printf 'ZOE-GEM OS\n' > /dev/tty0 2>/dev/null || true

# Mount hardware PCI virtio-9p UMA consent airlock if attached by host
mount -t 9p -o trans=virtio,version=9p2000.L,msize=262144 zoe_uma /mnt/uma 2>/dev/null || true

# Bring up loopback + first Ethernet NIC via non-blocking background DHCP
ip link set lo up 2>/dev/null || true
NIC=""
for dev in /sys/class/net/*; do
    n="$(basename "$dev")"
    if [ "$n" != "lo" ]; then
        NIC="$n"
        break
    fi
done
if [ -n "$NIC" ]; then
    ip link set "$NIC" up 2>/dev/null || true
    udhcpc -i "$NIC" -n -q -t 6 -T 2 -s /etc/udhcpc.script >/dev/null 2>&1 &
fi

# Safely discover and mount dedicated ZOE-STATE persistent hardware disk (never formats host disks)
STATE_DEV=""
for dev in /dev/vda /dev/vda1 /dev/sda /dev/sda1 /dev/sdb1 /dev/nvme0n1p3; do
    if [ -b "$dev" ]; then
        if mount -t ext4 "$dev" /mnt/zoe-state 2>/dev/null; then
            STATE_DEV="$dev"
            break
        fi
    fi
done
if [ -n "$STATE_DEV" ]; then
    export ZOE_DISK_LABEL="${STATE_DEV} [ZOE-STATE]"
else
    export ZOE_DISK_LABEL="tmpfs [EPHEMERAL]"
fi
export ZOE_STATE_DIR="/mnt/zoe-state"
export ZOE_BOOT_JSON="/run/zoe-boot-state.json"

# In automated verification mode, wait briefly for background DHCP before boot report
if grep -q "zoe.autotest=1" /proc/cmdline && [ -n "$NIC" ]; then
    net_wait=0
    while ! ip -o -4 addr show "$NIC" 2>/dev/null | grep -q "inet " && [ "$net_wait" -lt 40 ]; do
        busybox usleep 50000 2>/dev/null || sleep 0.05
        net_wait=$((net_wait + 1))
    done
fi

# Execute Zoe-GEM OS Python Boot Brain (SHA-256 chain + Artline VDI + 68000 RSC + Nick Drawer)
/usr/bin/python3 /usr/lib/zoe/zoe_os_runtime.py

if grep -q "zoe.autotest=1" /proc/cmdline; then
    echo "ZOE_OS_READY_FOR_INPUT"
    /bin/zoe_gem_fb --state /run/zoe-boot-state.json --autotest-sec 4 || true
    sync
    umount /mnt/zoe-state 2>/dev/null || true
    umount /mnt/uma 2>/dev/null || true
    echo "ZOE_OS_POWEROFF"
    poweroff -f
fi

# Interactive desktop loop: boots straight into mouse+kbd GEM Desktop; [T] drops to Zoe-OS shell
while true; do
    /bin/zoe_gem_fb --state /run/zoe-boot-state.json --interactive
    RC=$?
    if [ "$RC" -eq 2 ]; then
        sync
        umount /mnt/zoe-state 2>/dev/null || true
        reboot -f
    elif [ "$RC" -eq 3 ]; then
        sync
        umount /mnt/zoe-state 2>/dev/null || true
        poweroff -f
    fi
    /usr/bin/python3 /usr/lib/zoe/zoe_os_runtime.py --shell
done
"""

_UDHCPC_SCRIPT = """#!/bin/sh
case "$1" in
  deconfig)
    ip addr flush dev "$interface" 2>/dev/null || true
    ;;
  bound|renew)
    ip addr flush dev "$interface" 2>/dev/null || true
    ip addr add "$ip/${subnet:-255.255.255.0}" dev "$interface" 2>/dev/null || true
    if [ -n "$router" ]; then
      ip route replace default via "${router%% *}" dev "$interface" 2>/dev/null || true
    fi
    if [ -n "$dns" ]; then
      : > /etc/resolv.conf
      for d in $dns; do echo "nameserver $d" >> /etc/resolv.conf; done
    fi
    ;;
esac
"""

_WIFI_SCRIPT = """#!/bin/sh
if [ $# -lt 2 ]; then
  echo "Usage: zoe-wifi <SSID> <PASSWORD> [iface]"
  exit 1
fi
SSID="$1"
PSK="$2"
IFACE="${3:-wlan0}"
ip link set "$IFACE" up 2>/dev/null || true
cat > /run/wpa.conf <<EOF
ctrl_interface=/var/run/wpa_supplicant
network={
    ssid="$SSID"
    psk="$PSK"
}
EOF
killall wpa_supplicant 2>/dev/null || true
wpa_supplicant -B -i "$IFACE" -c /run/wpa.conf
sleep 3
udhcpc -i "$IFACE" -n -q -t 8 -T 2 -s /etc/udhcpc.script
ip -4 addr show "$IFACE"
"""


def _ensure_alpine_kernel(cache_dir: Path, flavor: str = "virt") -> tuple[Path, Path]:
    dest = cache_dir / f"alpine-{flavor}"
    dest.mkdir(parents=True, exist_ok=True)
    vmlinuz = dest / f"vmlinuz-{flavor}"
    modloop = dest / f"modloop-{flavor}"
    for fname, target in ((f"vmlinuz-{flavor}", vmlinuz), (f"modloop-{flavor}", modloop)):
        if not target.exists() or target.stat().st_size < 100_000:
            url = f"{_ALPINE_NETBOOT_BASE}/{fname}"
            urllib.request.urlretrieve(url, target)
    return vmlinuz, modloop


def _parse_ldd_lib_path(line: str) -> Path | None:
    parts = line.strip().split()
    if "=>" in parts:
        idx = parts.index("=>")
        if idx + 1 < len(parts) and parts[idx + 1].startswith("/"):
            return Path(parts[idx + 1])
    elif parts and parts[0].startswith("/"):
        return Path(parts[0])
    return None


def _copy_single_ldd_lib(lib_path: Path, rootfs: Path) -> None:
    if not lib_path.exists():
        return
    dst = rootfs / lib_path.relative_to("/")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lib_path.resolve(), dst)
    if str(lib_path).startswith("/usr/lib/x86_64-linux-gnu/"):
        alt = rootfs / "lib" / "x86_64-linux-gnu" / lib_path.name
        alt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib_path.resolve(), alt)


def _copy_ldd_deps(binaries: list[Path], rootfs: Path) -> None:
    existing = [str(b) for b in binaries if b.exists()]
    if not existing:
        return
    ldd_out = subprocess.check_output(["ldd", *existing], text=True, stderr=subprocess.DEVNULL)
    for line in ldd_out.splitlines():
        lib_path = _parse_ldd_lib_path(line)
        if lib_path is not None:
            _copy_single_ldd_lib(lib_path, rootfs)


def _kmod_cache_key(modloop: Path, flavor: str) -> str:
    h = hashlib.sha256()
    with modloop.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    extras = _LTS_EXTRA_KMODS if flavor == "lts" else ()
    sig = f"{flavor}|{' '.join(sorted(_VIRT_KMODS))}|{' '.join(sorted(extras))}"
    h.update(sig.encode("utf-8"))
    return f"{flavor}-{h.hexdigest()[:16]}"


def _parse_modules_dep(dep_path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    dep_map: dict[str, list[str]] = {}
    name_to_rel: dict[str, str] = {}
    for line in dep_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        mod_rel, deps_str = line.split(":", 1)
        mod_rel = mod_rel.strip()
        dep_map[mod_rel] = [d.strip() for d in deps_str.strip().split() if d.strip()]
        stem = Path(mod_rel).name.split(".ko")[0]
        name_to_rel[stem] = mod_rel
        name_to_rel[stem.replace("_", "-")] = mod_rel
        name_to_rel[stem.replace("-", "_")] = mod_rel
    return dep_map, name_to_rel


def _collect_kmod_closure(
    dep_map: dict[str, list[str]],
    name_to_rel: dict[str, str],
    desired: list[str],
) -> set[str]:
    wanted: set[str] = set()
    stack = [name_to_rel[m] for m in desired if m in name_to_rel]
    while stack:
        rel = stack.pop()
        if rel in wanted:
            continue
        wanted.add(rel)
        for dep in dep_map.get(rel, ()):
            if dep not in wanted:
                stack.append(dep)
    return wanted


def _copy_kmod_files(kdir: Path, dst_kdir: Path, wanted: set[str]) -> None:
    dst_kdir.mkdir(parents=True, exist_ok=True)
    for meta in kdir.glob("modules.*"):
        shutil.copy2(meta, dst_kdir / meta.name)
    for rel in wanted:
        src = kdir / rel
        if src.exists():
            dst = dst_kdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _copy_single_firmware(fw: Path, fw_root: Path, fw_dst: Path) -> None:
    rel = fw.relative_to(fw_root)
    out_fw = fw_dst / (rel.with_suffix("") if rel.suffix == ".zst" else rel)
    if out_fw.exists():
        return
    out_fw.parent.mkdir(parents=True, exist_ok=True)
    if fw.suffix == ".zst" and shutil.which("zstd"):
        with out_fw.open("wb") as fh:
            subprocess.run(["zstd", "-dc", str(fw)], stdout=fh, stderr=subprocess.DEVNULL, check=False)
    else:
        shutil.copy2(fw, out_fw)


def _copy_lts_firmware(sq_out: Path, fw_dst: Path) -> None:
    fw_dst.mkdir(parents=True, exist_ok=True)
    pats = ("iwlwifi-QuZ-a0-hr-b0-*.ucode*", "iwlwifi-Qu-c0-hr-b0-*.ucode*", "i915/tgl_dmc_*.bin*", "i915/tgl_guc_*.bin*")
    for fw_root in (sq_out / "modules" / "firmware", Path("/lib/firmware")):
        if not fw_root.is_dir():
            continue
        for pat in pats:
            for fw in fw_root.glob(pat):
                _copy_single_firmware(fw, fw_root, fw_dst)


def _copy_cached_kmod_closure(cache_entry: Path, rootfs: Path, flavor: str) -> str | None:
    kver_file = cache_entry / "kver.txt"
    if not kver_file.is_file():
        return None
    kver = kver_file.read_text(encoding="utf-8").strip()
    cached_mods = cache_entry / "modules" / kver
    if not kver or not cached_mods.is_dir():
        return None
    dst_kdir = rootfs / "lib" / "modules" / kver
    shutil.copytree(cached_mods, dst_kdir, dirs_exist_ok=True)
    cached_fw = cache_entry / "firmware"
    if flavor == "lts" and cached_fw.is_dir():
        shutil.copytree(cached_fw, rootfs / "lib" / "firmware", dirs_exist_ok=True)
    return kver


def _stage_kmod_cache_dir(sq_out: Path, kdir: Path, kver: str, wanted: set[str], cache_entry: Path, flavor: str) -> None:
    cache_entry.parent.mkdir(parents=True, exist_ok=True)
    stage = cache_entry.parent / f".staging-{cache_entry.name}-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    try:
        _copy_kmod_files(kdir, stage / "modules" / kver, wanted)
        if flavor == "lts":
            _copy_lts_firmware(sq_out, stage / "firmware")
        (stage / "kver.txt").write_text(kver, encoding="utf-8")
        if not cache_entry.exists():
            os.replace(stage, cache_entry)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _populate_kmod_cache_entry(modloop: Path, tmp_work: Path, cache_entry: Path, flavor: str) -> str:
    sq_out = tmp_work / "modloop_sq"
    subprocess.run(
        ["unsquashfs", "-no-xattrs", "-d", str(sq_out), str(modloop)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    mod_roots = [p for p in (sq_out / "modules").iterdir() if p.is_dir() and (p / "modules.dep").is_file()]
    if not mod_roots:
        raise RuntimeError("No kernel module directory with modules.dep inside modloop")
    kdir = mod_roots[0]
    kver = kdir.name
    dep_map, name_to_rel = _parse_modules_dep(kdir / "modules.dep")
    desired = list(_VIRT_KMODS) + (list(_LTS_EXTRA_KMODS) if flavor == "lts" else [])
    wanted = _collect_kmod_closure(dep_map, name_to_rel, desired)
    _stage_kmod_cache_dir(sq_out, kdir, kver, wanted, cache_entry, flavor)
    return kver


def _extract_kmod_closure(
    modloop: Path,
    rootfs: Path,
    tmp_work: Path,
    flavor: str,
    cache_dir: Path | None = None,
) -> str:
    """Extract only the exact transitive `modules.dep` closure of needed HAL drivers (cached by SHA-256)."""
    c_root = (cache_dir or (Path.home() / ".zoe" / "os-cache")) / "kmod-closure"
    cache_entry = c_root / _kmod_cache_key(modloop, flavor)
    cached_kver = _copy_cached_kmod_closure(cache_entry, rootfs, flavor)
    if cached_kver is not None:
        return cached_kver
    kver = _populate_kmod_cache_entry(modloop, tmp_work, cache_entry, flavor)
    loaded = _copy_cached_kmod_closure(cache_entry, rootfs, flavor)
    if loaded is None:
        raise RuntimeError(f"Failed to populate kmod closure cache at {cache_entry}")
    return kver


def _copy_wifi_binaries(rootfs: Path, ldd_targets: list[Path]) -> None:
    for tool_name in ("wpa_supplicant", "iw"):
        found = shutil.which(tool_name)
        if not found:
            continue
        tp = Path(found).resolve()
        dst_t = rootfs / "usr" / "sbin" / tool_name
        dst_t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tp, dst_t)
        os.chmod(dst_t, 0o755)
        ldd_targets.append(tp)


def _copy_python_stdlib(stdlib: Path, dst_std: Path) -> None:
    dst_std.mkdir(parents=True, exist_ok=True)
    ignore_fn = shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests")
    for item in stdlib.iterdir():
        if item.name in _SKIP_STDLIB_DIRS or item.name.startswith("config-"):
            continue
        if item.is_dir():
            shutil.copytree(item, dst_std / item.name, ignore=ignore_fn, dirs_exist_ok=True)
        elif item.suffix in {".py", ".so"}:
            shutil.copy2(item, dst_std / item.name)


def _copy_zoe_closure(rootfs: Path, zoe_root: Path) -> None:
    zoe_pkg = rootfs / "usr" / "lib" / "zoe" / "guiai" / "gem"
    zoe_pkg.mkdir(parents=True, exist_ok=True)
    (rootfs / "usr" / "lib" / "zoe" / "guiai" / "__init__.py").write_text("", encoding="utf-8")
    gem_src = zoe_root / "guiai-lab" / "guiai" / "gem"
    for fname in _ZOE_PY_CLOSURE:
        shutil.copy2(gem_src / fname, zoe_pkg / fname)
    os_pkg = zoe_pkg / "zoe_gem_os"
    os_pkg.mkdir(parents=True, exist_ok=True)
    (os_pkg / "__init__.py").write_text("", encoding="utf-8")
    here = Path(__file__).resolve().parent
    shutil.copy2(here / "zoe_uma.py", os_pkg / "zoe_uma.py")
    shutil.copy2(here / "zoe_os_runtime.py", rootfs / "usr" / "lib" / "zoe" / "zoe_os_runtime.py")


def _bundle_python_and_zoe(rootfs: Path, zoe_root: Path, include_wifi_tools: bool = False) -> None:
    """Copy minimal system Python 3 + required shared libs + minimal 14-file Zoe Python closure."""
    py_bin = Path("/usr/bin/python3").resolve()
    py_ver = subprocess.check_output(
        [str(py_bin), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        text=True,
    ).strip()
    stdlib = Path(subprocess.check_output([str(py_bin), "-c", "import sysconfig; print(sysconfig.get_paths()['stdlib'])"], text=True).strip())

    (rootfs / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(py_bin, rootfs / "usr" / "bin" / "python3")

    dynload = stdlib / "lib-dynload"
    dyn_pats = (
        "_hashlib*.so", "_ssl*.so", "_ctypes*.so", "zlib*.so", "math*.so",
        "_json*.so", "binascii*.so", "_struct*.so", "unicodedata*.so",
        "select*.so", "fcntl*.so", "termios*.so", "_posixsubprocess*.so", "pyexpat*.so",
    )
    ldd_targets = [py_bin] + [p for pat in dyn_pats for p in dynload.glob(pat)]
    if include_wifi_tools:
        _copy_wifi_binaries(rootfs, ldd_targets)
    _copy_ldd_deps(ldd_targets, rootfs)

    ld_src = Path("/lib64/ld-linux-x86-64.so.2")
    if ld_src.exists():
        (rootfs / "lib64").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ld_src.resolve(), rootfs / "lib64" / "ld-linux-x86-64.so.2")

    _copy_python_stdlib(stdlib, rootfs / "usr" / "lib" / f"python{py_ver}")
    _copy_zoe_closure(rootfs, zoe_root)


def _compile_zoe_gem_fb(rootfs: Path) -> None:
    fb_c = Path(__file__).resolve().parent / "zoe_gem_fb.c"
    fb_bin = rootfs / "bin" / "zoe_gem_fb"
    subprocess.run(
        ["gcc", "-O2", "-Wall", "-Wextra", "-Werror", "-static", str(fb_c), "-lm", "-o", str(fb_bin)],
        check=True,
    )
    os.chmod(fb_bin, 0o755)


def _prepare_rootfs_scripts(rootfs: Path) -> None:
    busybox_src = Path(shutil.which("busybox") or "/usr/bin/busybox")
    shutil.copy2(busybox_src, rootfs / "bin" / "busybox")
    os.chmod(rootfs / "bin" / "busybox", 0o755)
    os.symlink("busybox", rootfs / "bin" / "sh")

    for rel, content in (("init", _PID1_INIT), ("etc/udhcpc.script", _UDHCPC_SCRIPT), ("bin/zoe-wifi", _WIFI_SCRIPT)):
        dst = rootfs / rel
        dst.write_text(content, encoding="utf-8")
        os.chmod(dst, 0o755)


def _close_proc_streams(proc: subprocess.Popen[Any]) -> None:
    for stream in (getattr(proc, "stdin", None), getattr(proc, "stdout", None), getattr(proc, "stderr", None)):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _cleanup_proc(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
                return
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                try:
                    proc.kill()
                except OSError:
                    pass
        proc.wait()
    except OSError:
        pass
    finally:
        _close_proc_streams(proc)


def _create_initrd(rootfs: Path, initrd_path: Path) -> None:
    with initrd_path.open("wb") as out_f:
        p1: subprocess.Popen[bytes] | None = None
        p2: subprocess.Popen[bytes] | None = None
        p3: subprocess.Popen[bytes] | None = None
        try:
            p1 = subprocess.Popen(["find", "."], cwd=rootfs, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["cpio", "-o", "-H", "newc", "--quiet"], cwd=rootfs, stdin=p1.stdout, stdout=subprocess.PIPE)
            p3 = subprocess.Popen(["gzip", "-1"], stdin=p2.stdout, stdout=out_f)
            assert p1.stdout and p2.stdout
            p1.stdout.close()
            p2.stdout.close()
            p3.wait()
            p2.wait()
            p1.wait()
            if p3.returncode != 0:
                raise RuntimeError("Failed to compress initramfs.cpio.gz")
        except BaseException:
            for proc in (p3, p2, p1):
                _cleanup_proc(proc)
            raise


def _write_grub_cfg(iso_root: Path, flavor: str, autotest_default: bool) -> None:
    default_idx = "1" if autotest_default else "0"
    grub_cfg = f"""set timeout=1
set default={default_idx}
insmod all_video
set gfxmode=auto
set gfxpayload=keep

menuentry "Zoe-GEM OS v1.0 ({flavor.upper()} · Interactive GEM Desktop + Mouse + Keyboard)" {{
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 quiet loglevel=3
    initrd /boot/initrd.img
}}

menuentry "Zoe-GEM OS v1.0 ({flavor.upper()} · Automated Hardware + Retention Self-Test)" {{
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 zoe.autotest=1 quiet loglevel=3
    initrd /boot/initrd.img
}}
"""
    (iso_root / "boot" / "grub" / "grub.cfg").write_text(grub_cfg, encoding="utf-8")


def build_zoe_gem_os_iso(
    out_dir: str | Path,
    zoe_root: str | Path,
    *,
    kernel_flavor: str = "virt",
    autotest_default: bool = False,
) -> dict[str, Any]:
    """Compile interactive `zoe_gem_fb`, assemble initramfs, and package UEFI bootable ISO."""
    flavor = "lts" if str(kernel_flavor).strip().lower() == "lts" else "virt"
    out_p = Path(out_dir).expanduser().resolve()
    out_p.mkdir(parents=True, exist_ok=True)
    zoe_p = Path(zoe_root).expanduser().resolve()
    cache_dir = Path.home() / ".zoe" / "os-cache"
    vmlinuz, modloop = _ensure_alpine_kernel(cache_dir, flavor=flavor)

    with tempfile.TemporaryDirectory(prefix="zoe-gem-os-build-") as td:
        work = Path(td)
        rootfs = work / "rootfs"
        for sub in ("bin", "sbin", "etc", "proc", "sys", "dev", "run", "tmp", "mnt/zoe-state", "usr/bin", "usr/sbin", "usr/lib"):
            (rootfs / sub).mkdir(parents=True, exist_ok=True)

        _prepare_rootfs_scripts(rootfs)
        _compile_zoe_gem_fb(rootfs)
        kver = _extract_kmod_closure(modloop, rootfs, work, flavor=flavor, cache_dir=cache_dir)
        _bundle_python_and_zoe(rootfs, zoe_p, include_wifi_tools=(flavor == "lts"))

        iso_root = work / "iso_root"
        (iso_root / "boot" / "grub").mkdir(parents=True, exist_ok=True)
        shutil.copy2(vmlinuz, iso_root / "boot" / "vmlinuz")
        _create_initrd(rootfs, iso_root / "boot" / "initrd.img")
        _write_grub_cfg(iso_root, flavor, autotest_default)

        iso_name = "zoe-gem-os-lts.iso" if flavor == "lts" else "zoe-gem-os.iso"
        iso_path = out_p / iso_name
        if iso_path.exists():
            iso_path.unlink()
        subprocess.run(
            ["grub-mkrescue", "-o", str(iso_path), str(iso_root)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    sha256 = hashlib.sha256(iso_path.read_bytes()).hexdigest()
    return {
        "ok": True,
        "iso_path": str(iso_path),
        "iso_bytes": iso_path.stat().st_size,
        "iso_sha256": sha256,
        "kernel_version": kver,
        "kernel_flavor": flavor,
        "wifi_bundled": flavor == "lts",
        "interactive_mouse_kbd": True,
        "uefi_bootable": True,
        **_CONSTITUTIONAL_FLAGS,
    }


def _alloc_loopback_port(exclude: set[int] | None = None) -> int:
    held: list[socket.socket] = []
    try:
        for _ in range(16):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])
            if not exclude or port not in exclude:
                s.close()
                return port
            held.append(s)
        raise RuntimeError("Unable to allocate distinct loopback port")
    finally:
        for s in held:
            s.close()


def _connect_loopback_monitor(port: int) -> socket.socket | None:
    for _ in range(25):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4.0)
        try:
            s.connect(("127.0.0.1", port))
            return s
        except OSError:
            s.close()
            time.sleep(0.1)
    return None


def _send_qemu_tcp_cmds(port: int, cmds: list[str], delay: float = 0.12) -> bool:
    sock = _connect_loopback_monitor(port)
    if sock is None:
        return False
    try:
        with sock:
            time.sleep(0.12)
            try:
                sock.recv(4096)
            except OSError:
                pass
            for cmd in cmds:
                sock.sendall((cmd + "\n").encode("utf-8"))
                time.sleep(delay)
        return True
    except OSError:
        return False


def _resolve_ovmf_firmware() -> Path:
    for cand in _OVMF_CANDIDATES:
        if cand.is_file():
            return cand
    checked = ", ".join(str(c) for c in _OVMF_CANDIDATES)
    raise FileNotFoundError(f"OVMF UEFI firmware not found (checked: {checked})")


def _verify_kvm_access() -> Path:
    if not _KVM_DEVICE.exists():
        raise RuntimeError(f"KVM device not found: {_KVM_DEVICE}")
    if not os.access(_KVM_DEVICE, os.R_OK | os.W_OK):
        raise RuntimeError(f"KVM device lacks read/write access: {_KVM_DEVICE} (check kvm group permissions)")
    return _KVM_DEVICE


def _probe_ofd_wrlck(fd: int, disk_path: Path) -> None:
    cmd_getlk = getattr(fcntl, "F_OFD_GETLK", None)
    if cmd_getlk is None:
        return
    lk = struct.pack("hhqqii", fcntl.F_WRLCK, os.SEEK_SET, 0, 0, 0, 0)
    try:
        res = fcntl.fcntl(fd, cmd_getlk, lk)
        l_type, _, _, _, l_pid, _ = struct.unpack("hhqqii", res)
    except OSError:
        return
    if l_type != fcntl.F_UNLCK:
        raise RuntimeError(f"State disk is locked by another QEMU/process (pid={l_pid}): {disk_path}")


def _check_disk_unlocked(disk_path: Path) -> None:
    if not disk_path.exists():
        return
    fd = os.open(str(disk_path), os.O_RDONLY)
    try:
        _probe_ofd_wrlck(fd, disk_path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"State disk is currently locked by another process: {disk_path}") from exc
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _align_vga_xres(width: int) -> int:
    return min(4096, ((int(width) + 7) // 8) * 8)


def _parse_geometry_spec(geometry: str | tuple[int, int]) -> tuple[int, int]:
    if isinstance(geometry, (tuple, list)):
        if len(geometry) != 2:
            raise ValueError(f"Invalid geometry tuple {geometry!r}; expected (width, height)")
        w, h = int(geometry[0]), int(geometry[1])
    else:
        raw = str(geometry).strip().lower()
        if "x" not in raw:
            raise ValueError(f"Invalid geometry {geometry!r}; expected 'WxH' (e.g. '920x960')")
        w_s, h_s = raw.split("x", 1)
        w, h = int(w_s), int(h_s)
    if not (160 <= w <= 4096 and 160 <= h <= 4096):
        raise ValueError(f"Geometry {w}x{h} out of supported range [160..4096]")
    return _align_vga_xres(w), h


def _resolve_display_geometry(
    mode: str | None = None,
    geometry: str | tuple[int, int] | None = None,
    split_screen: bool = True,
) -> tuple[str, int, int]:
    resolved_mode = (mode or ("split" if split_screen else "full")).strip().lower()
    if geometry is not None:
        w, h = _parse_geometry_spec(geometry)
        return resolved_mode, w, h
    if resolved_mode not in _GEOMETRY_PRESETS:
        valid = ", ".join(_GEOMETRY_PRESETS)
        raise ValueError(f"Unknown display mode {mode!r}. Expected one of: {valid}")
    w, h = _GEOMETRY_PRESETS[resolved_mode]
    return resolved_mode, w, h


def _build_display_args(display_backend: str, width: int, height: int) -> tuple[str, list[str]]:
    backend = str(display_backend or "gtk").strip().lower()
    if backend not in {"gtk", "sdl"}:
        raise ValueError(f"Unsupported display_backend {display_backend!r}; expected 'gtk' or 'sdl'")
    xres = _align_vga_xres(width)
    disp_opt = "gtk,show-menubar=off,show-cursor=off" if backend == "gtk" else "sdl,show-cursor=off"
    return backend, ["-vga", "none", "-device", f"VGA,xres={xres},yres={height}", "-display", disp_opt]


def _append_monitor_qmp_args(
    cmd: list[str],
    monitor_port: int | None,
    qmp_port: int | None,
) -> tuple[int | None, int | None]:
    m_port: int | None = None
    q_port: int | None = None
    if monitor_port is not None:
        m_port = _alloc_loopback_port() if int(monitor_port) == 0 else int(monitor_port)
        cmd.extend(["-monitor", f"tcp:127.0.0.1:{m_port},server,nowait"])
    if qmp_port is not None:
        excluded = {m_port} if m_port is not None else None
        q_port = _alloc_loopback_port(exclude=excluded) if int(qmp_port) == 0 else int(qmp_port)
        if m_port is not None and q_port == m_port:
            raise ValueError(f"monitor_port and qmp_port must be distinct (got {q_port})")
        cmd.extend(["-qmp", f"tcp:127.0.0.1:{q_port},server,nowait"])
    return m_port, q_port


def _read_early_stderr(proc: subprocess.Popen[str]) -> str:
    try:
        _, err = proc.communicate(timeout=2)
        return (err or "").strip()
    except Exception:
        if proc.stderr is not None:
            return str(proc.stderr.read() or "").strip()
        return ""


def _launch_qemu_checked(cmd: list[str], wait_sec: float = 0.5) -> subprocess.Popen[str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        deadline = time.monotonic() + max(0.0, wait_sec)
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        if proc.poll() is not None:
            err = _read_early_stderr(proc)
            raise RuntimeError(f"QEMU exited immediately (rc={proc.returncode}): {err or 'no stderr'}")
        return proc
    except BaseException:
        _cleanup_proc(proc)
        raise


def _ensure_state_disk(st_p: Path) -> None:
    st_p.parent.mkdir(parents=True, exist_ok=True)
    if not st_p.exists():
        with st_p.open("wb") as fh:
            fh.truncate(64 * 1024 * 1024)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(st_p)], check=True)


def _build_verify_qemu_cmd(
    iso_path: Path,
    state_img: Path,
    ovmf_code: Path,
    mon_port: int,
    uma_dir: Path | None,
    uma_shm: Path | None,
) -> list[str]:
    cmd = [
        "qemu-system-x86_64",
        "-enable-kvm",
        "-machine", "q35",
        "-cpu", "host",
        "-m", "768M",
        "-smp", "2",
        "-bios", str(ovmf_code),
        "-drive", f"file={iso_path},media=cdrom,readonly=on,if=ide",
        "-boot", "d",
        "-drive", f"file={state_img},format=raw,if=virtio",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-device", "qemu-xhci",
        "-device", "usb-mouse",
        "-vga", "none",
        "-device", "VGA,xres=1024,yres=768",
        "-display", "none",
        "-serial", "stdio",
        "-monitor", f"tcp:127.0.0.1:{mon_port},server,nowait",
        "-no-reboot",
    ]
    if uma_dir is not None:
        cmd.extend(["-virtfs", f"local,id=uma9p,path={uma_dir},mount_tag=zoe_uma,security_model=none"])
    if uma_shm is not None:
        cmd.extend([
            "-object", f"memory-backend-file,id=uma_shm,share=on,mem-path={uma_shm},size=4M",
            "-device", "ivshmem-plain,memdev=uma_shm",
        ])
    return cmd


def _inject_boot_input(mon_port: int, boot_idx: int) -> None:
    if boot_idx == 2:
        cmds = [
            "sendkey 6",
            "mouse_move 430 -240",
            "mouse_button 1",
            "mouse_move 36 48",
            "mouse_move -28 42",
            "mouse_move 34 38",
            "mouse_button 0",
            "sendkey s",
        ]
        _send_qemu_tcp_cmds(mon_port, cmds, delay=0.14)
    else:
        _send_qemu_tcp_cmds(mon_port, ["mouse_move -120 -60"], delay=0.15)


def _handle_boot_line(
    s: str,
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
    injected: bool,
    captured: bool,
) -> tuple[bool, bool, bool]:
    if "ZOE_OS_FB_OK" in s and not injected:
        injected = True
        _inject_boot_input(mon_port, boot_idx)
    if "ZOE_OS_READY_FOR_CAPTURE" in s and not captured:
        captured = _send_qemu_tcp_cmds(mon_port, [f"screendump {ppm_path}"], delay=0.45)
    return injected, captured, ("ZOE_OS_POWEROFF" in s)


def _stdout_fd(stream: Any) -> int | None:
    fileno_fn = getattr(stream, "fileno", None)
    if not callable(fileno_fn):
        return None
    try:
        fd = fileno_fn()
    except Exception:
        return None
    return fd if isinstance(fd, int) and not isinstance(fd, bool) and fd >= 0 else None


def _read_fd_nonblocking(fd: int) -> bytes | None:
    try:
        return os.read(fd, 4096)
    except BlockingIOError:
        return None


def _consume_boot_chunk(
    buf: bytearray,
    chunk: bytes,
    lines: list[str],
    state: list[bool],
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
) -> bool:
    buf.extend(chunk)
    while True:
        nl_idx = buf.find(b"\n")
        if nl_idx < 0:
            return False
        raw = bytes(buf[:nl_idx])
        del buf[: nl_idx + 1]
        s = raw.decode("utf-8", errors="replace").rstrip("\r")
        lines.append(s)
        state[0], state[1], poweroff = _handle_boot_line(s, mon_port, ppm_path, boot_idx, state[0], state[1])
        if poweroff:
            return True


def _drain_fd_boot_lines(
    fd: int,
    buf: bytearray,
    lines: list[str],
    state: list[bool],
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
) -> None:
    for _ in range(16):
        chunk = _read_fd_nonblocking(fd)
        if not chunk:
            break
        if _consume_boot_chunk(buf, chunk, lines, state, mon_port, ppm_path, boot_idx):
            return
    if buf:
        s = bytes(buf).decode("utf-8", errors="replace").rstrip("\r")
        buf.clear()
        lines.append(s)
        state[0], state[1], _ = _handle_boot_line(s, mon_port, ppm_path, boot_idx, state[0], state[1])


def _collect_fd_boot_lines(
    proc: subprocess.Popen[str],
    fd: int,
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
    timeout_sec: int,
) -> tuple[list[str], bool]:
    lines: list[str] = []
    state = [False, False]
    buf = bytearray()
    os.set_blocking(fd, False)
    deadline = time.monotonic() + max(0.0, float(timeout_sec))
    with selectors.DefaultSelector() as sel:
        sel.register(fd, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            rem = deadline - time.monotonic()
            if not sel.select(timeout=min(0.25, max(0.0, rem))):
                if proc.poll() is not None:
                    break
                continue
            chunk = _read_fd_nonblocking(fd)
            if chunk is None:
                continue
            if not chunk:
                break
            if _consume_boot_chunk(buf, chunk, lines, state, mon_port, ppm_path, boot_idx):
                return lines, state[1]
    _drain_fd_boot_lines(fd, buf, lines, state, mon_port, ppm_path, boot_idx)
    return lines, state[1]


def _collect_stream_boot_lines(
    proc: subprocess.Popen[str],
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
    timeout_sec: int,
) -> tuple[list[str], bool]:
    lines: list[str] = []
    injected, captured = False, False
    deadline = time.monotonic() + max(0.0, float(timeout_sec))
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
            continue
        s = line.rstrip("\r\n")
        lines.append(s)
        injected, captured, poweroff = _handle_boot_line(s, mon_port, ppm_path, boot_idx, injected, captured)
        if poweroff:
            break
    return lines, captured


def _collect_boot_lines(
    proc: subprocess.Popen[str],
    mon_port: int,
    ppm_path: Path,
    boot_idx: int,
    timeout_sec: int,
) -> tuple[list[str], bool]:
    fd = _stdout_fd(proc.stdout)
    if fd is not None:
        return _collect_fd_boot_lines(proc, fd, mon_port, ppm_path, boot_idx, timeout_sec)
    return _collect_stream_boot_lines(proc, mon_port, ppm_path, boot_idx, timeout_sec)


def _reap_boot_proc(proc: subprocess.Popen[str], saw_poweroff: bool) -> None:
    if proc.poll() is None and not saw_poweroff:
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=8.0 if saw_poweroff else 2.0)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait()
        except OSError:
            pass


def _screendump_is_nonblank(png_path: Path) -> bool:
    if not png_path.is_file():
        return False
    try:
        with Image.open(png_path) as img:
            rgb = img.convert("RGB")
            extrema = rgb.getextrema()
            span = max((int(hi) - int(lo)) for lo, hi in extrema)
            colors = rgb.getcolors(maxcolors=64)
            n_colors = 65 if colors is None else len(colors)
            return span > 20 and n_colors > 8
    except Exception:
        return False


def _format_boot_result(
    boot_idx: int,
    elapsed: float,
    lines: list[str],
    png_path: Path,
    *,
    captured: bool = False,
) -> dict[str, Any]:
    joined = "\n".join(lines)
    png_exists = png_path.exists()
    nonblank = _screendump_is_nonblank(png_path) if png_exists else False
    return {
        "boot_index": boot_idx,
        "elapsed_sec": round(elapsed, 2),
        "boot_ok": "ZOE_OS_BOOT_OK" in joined,
        "net_ok": "ZOE_OS_NET_OK" in joined and "ip=10.0.2." in joined,
        "persist_ok": "ZOE_OS_PERSIST_OK" in joined,
        "fb_ok": "ZOE_OS_FB_OK" in joined,
        "canvas_saved": "ZOE_OS_CANVAS_SAVED" in joined,
        "restored_true": "restored=True" in joined,
        "vault_restored_true": "vault_restored=True" in joined,
        "screendump_captured": bool(captured),
        "screendump_nonblank": nonblank,
        "screendump_png": str(png_path) if png_exists else "",
        "serial_tail": [ln for ln in lines if ln.startswith("ZOE_OS_") or "ZOE-GEM OS" in ln],
    }


def _run_single_qemu_boot(
    iso_path: Path,
    state_img: Path,
    ovmf_code: Path,
    work_dir: Path,
    boot_idx: int,
    uma_dir: Path | None = None,
    uma_shm: Path | None = None,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    mon_port = _alloc_loopback_port()
    ppm_path = work_dir / f"boot_{boot_idx}_fb.ppm"
    png_path = work_dir / f"boot_{boot_idx}_fb.png"
    cmd = _build_verify_qemu_cmd(iso_path, state_img, ovmf_code, mon_port, uma_dir, uma_shm)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines: list[str] = []
    captured = False
    t0 = time.time()
    try:
        lines, captured = _collect_boot_lines(proc, mon_port, ppm_path, boot_idx, timeout_sec)
    finally:
        _reap_boot_proc(proc, any("ZOE_OS_POWEROFF" in ln for ln in lines))
        if proc.stdout is not None:
            try:
                proc.stdout.close()
            except OSError:
                pass

    if captured and ppm_path.exists():
        Image.open(ppm_path).convert("RGB").save(png_path)
    return _format_boot_result(boot_idx, time.time() - t0, lines, png_path, captured=captured)


def _prepare_verify_artifacts(work_dir: Path) -> tuple[Path, Path, Path, Any]:
    from .zoe_uma import UmaBridge

    state_img = work_dir / "zoe-state.img"
    if state_img.exists():
        state_img.unlink()
    with state_img.open("wb") as fh:
        fh.truncate(64 * 1024 * 1024)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(state_img)], check=True)

    uma_dir = work_dir / "uma_bridge"
    if uma_dir.exists():
        shutil.rmtree(uma_dir)
    uma_shm = work_dir / "zoe_uma_bar.shm"
    if uma_shm.exists():
        uma_shm.unlink()
    uma = UmaBridge(uma_dir, shm_path=uma_shm)
    uma.ensure_initialized()
    return state_img, uma_dir, uma_shm, uma


def _screendump_ok(boot: dict[str, Any]) -> bool:
    if boot.get("screendump_captured") or boot.get("screendump_png"):
        return bool(boot.get("screendump_nonblank"))
    return True


def _boot_core_ok(boot: dict[str, Any]) -> bool:
    return all(boot[k] for k in ("boot_ok", "net_ok", "persist_ok", "fb_ok")) and _screendump_ok(boot)


def _evaluate_verify_results(
    iso_p: Path,
    state_img: Path,
    b1: dict[str, Any],
    b2: dict[str, Any],
    b1_privacy_held: bool,
    b2_transferred: bool,
    b1_shm_hb: dict[str, Any] | None,
    b2_shm_hb: dict[str, Any] | None,
) -> dict[str, Any]:
    retention_ok = bool(b2["restored_true"] and b2["vault_restored_true"])
    b1_shm_ok = bool(b1_shm_hb and b1_shm_hb.get("side") == "zoe-gem-os")
    b2_shm_ok = bool(b2_shm_hb and b2_shm_hb.get("side") == "zoe-gem-os")
    b2_gate_shared = bool(b2_shm_hb and b2_shm_hb.get("gate") == "SHARED")
    all_passed = all((
        _boot_core_ok(b1),
        _boot_core_ok(b2),
        retention_ok,
        bool(b2["canvas_saved"]),
        b1_privacy_held,
        b2_transferred,
        b1_shm_ok,
        b2_gate_shared,
    ))
    return {
        "ok": all_passed,
        "iso_path": str(iso_p),
        "state_disk": str(state_img),
        "boot_1": b1,
        "boot_2": b2,
        "self_retention_verified": retention_ok,
        "interactive_canvas_saved": b2["canvas_saved"],
        "uma_privacy_invariant_held": b1_privacy_held,
        "uma_shared_crossing_verified": b2_transferred,
        "uma_pci_ivshmem_4mb_verified": b2_shm_ok,
        "uma_shm_boot2_header": b2_shm_hb,
        "hardware_networking_verified": b1["net_ok"] and b2["net_ok"],
        "hardware_framebuffer_verified": b1["fb_ok"] and b2["fb_ok"] and _screendump_ok(b1) and _screendump_ok(b2),
        **_CONSTITUTIONAL_FLAGS,
    }


def verify_zoe_gem_os_qemu(
    iso_path: str | Path,
    work_dir: str | Path,
    *,
    timeout_sec: int = 45,
    dry_run: bool = False,
    zoe_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run automated 2-boot OVMF UEFI + KVM hardware, UMA consent airlock, mouse/kbd & retention proof."""
    if dry_run:
        resolved_zoe = Path(zoe_root).expanduser().resolve() if zoe_root else Path(__file__).resolve().parents[4]
        res = verify_zoe_gem_os_static(resolved_zoe, work_dir)
        res["iso_path"] = str(Path(iso_path).expanduser().resolve())
        return res
    iso_p = Path(iso_path).expanduser().resolve()
    work_p = Path(work_dir).expanduser().resolve()
    work_p.mkdir(parents=True, exist_ok=True)
    _verify_kvm_access()
    ovmf_code = _resolve_ovmf_firmware()
    state_img, uma_dir, uma_shm, uma = _prepare_verify_artifacts(work_p)

    b1 = _run_single_qemu_boot(
        iso_p, state_img, ovmf_code, work_p, boot_idx=1, uma_dir=uma_dir, uma_shm=uma_shm, timeout_sec=timeout_sec
    )
    b1_privacy_held = len([p for p in (uma_dir / "zoe_to_nick").iterdir() if not p.name.startswith(".")]) == 0
    b1_shm_hb = uma.read_shm_heartbeat()

    uma.set_consent("nick", True, reason="nick_approved_research_handoff")
    b2 = _run_single_qemu_boot(
        iso_p, state_img, ovmf_code, work_p, boot_idx=2, uma_dir=uma_dir, uma_shm=uma_shm, timeout_sec=timeout_sec
    )
    b2_transferred = (uma_dir / "zoe_to_nick" / "zoe_os_emblem.gem").is_file()
    b2_shm_hb = uma.read_shm_heartbeat()

    return _evaluate_verify_results(iso_p, state_img, b1, b2, b1_privacy_held, b2_transferred, b1_shm_hb, b2_shm_hb)


def _normalize_target_flavor(target: str) -> str:
    flavor = str(target or "virt").strip().lower()
    if flavor not in {"virt", "lts"}:
        raise ValueError(f"Unsupported kernel target {target!r}; expected 'virt' or 'lts'")
    return flavor


def _resolve_uma_paths(uma_dir: str | Path | None, uma_shm: str | Path | None) -> tuple[Path, Path]:
    from .zoe_uma import resolve_uma_paths

    return resolve_uma_paths(uma_dir, uma_shm)


def launch_zoe_gem_os_kvm(
    iso_path: str | Path,
    state_img: str | Path,
    *,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
    split_screen: bool = True,
    target: str = "virt",
    mode: str | None = None,
    geometry: str | tuple[int, int] | None = None,
    display_backend: str = "gtk",
    monitor_port: int | None = None,
    qmp_port: int | None = None,
) -> dict[str, Any]:
    """Launch Zoe-GEM OS interactively in KVM with 4 MB PCI ivshmem UMA + 9p consent airlock."""
    from .zoe_uma import UmaBridge

    target_flavor = _normalize_target_flavor(target)
    resolved_mode, w, h = _resolve_display_geometry(mode, geometry, split_screen)
    backend, disp_args = _build_display_args(display_backend, w, h)
    iso_p = Path(iso_path).expanduser().resolve()
    if not iso_p.is_file():
        raise FileNotFoundError(f"ISO not built yet: {iso_p}. Run `/os build` first.")
    st_p = Path(state_img).expanduser().resolve()
    _ensure_state_disk(st_p)
    _check_disk_unlocked(st_p)
    _verify_kvm_access()
    ovmf = _resolve_ovmf_firmware()

    u_dir, u_shm = _resolve_uma_paths(uma_dir, uma_shm)
    UmaBridge(u_dir, shm_path=u_shm).ensure_initialized()

    cmd = [
        "qemu-system-x86_64",
        "-name", "Zoe-GEM OS [LEFT HALF :: HARDWARE UMA]",
        "-enable-kvm",
        "-machine", "q35",
        "-cpu", "host",
        "-m", "2048M" if resolved_mode == "split" else "1024M",
        "-smp", "2",
        "-bios", str(ovmf),
        "-drive", f"file={iso_p},media=cdrom,readonly=on,if=ide",
        "-boot", "d",
        "-drive", f"file={st_p},format=raw,if=virtio",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-virtfs", f"local,id=uma9p,path={u_dir},mount_tag=zoe_uma,security_model=none",
        "-object", f"memory-backend-file,id=uma_shm,share=on,mem-path={u_shm},size=4M",
        "-device", "ivshmem-plain,memdev=uma_shm",
        "-device", "qemu-xhci",
        "-device", "usb-tablet",
        *disp_args,
    ]
    m_port, q_port = _append_monitor_qmp_args(cmd, monitor_port, qmp_port)
    proc = _launch_qemu_checked(cmd)
    result: dict[str, Any] = {
        "ok": True,
        "pid": proc.pid,
        "iso": str(iso_p),
        "state_img": str(st_p),
        "uma_dir": str(u_dir),
        "uma_shm": str(u_shm),
        "split_screen": resolved_mode == "split",
        "mode": resolved_mode,
        "geometry": f"{w}x{h}",
        "target": target_flavor,
        "display_backend": backend,
        "ovmf": str(ovmf),
    }
    if m_port is not None:
        result["monitor_port"] = m_port
    if q_port is not None:
        result["qmp_port"] = q_port
    return result


def _ensure_node_state_disk(img_path: Path, node_id: int, theme: str) -> Path:
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if img_path.exists():
        return img_path
    with tempfile.TemporaryDirectory(prefix=f"zo3-seed-{node_id}-") as td:
        seed = Path(td)
        (seed / "node_identity.json").write_text(f'{{"node_id": {node_id}, "theme": "{theme}"}}\n', encoding="utf-8")
        with img_path.open("wb") as fh:
            fh.truncate(64 * 1024 * 1024)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-L", f"ZOE-STATE-{node_id}", "-d", str(seed), str(img_path)], check=True)
    return img_path


def _validate_zo3_count(count: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or count not in (2, 3):
        raise ValueError(f"ZO3 node count must be 2 or 3, got {count!r}")
    return count


def launch_zo3_cluster(
    iso_path: str | Path,
    state_dir: str | Path,
    *,
    count: int = 2,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
    target: str = "virt",
    mode: str = "split",
    geometry: str | tuple[int, int] | None = None,
    display_backend: str = "gtk",
    monitor_port_base: int | None = None,
) -> dict[str, Any]:
    """Launch 2 or 3 concurrent sovereign ZO3 KVM nodes sharing one 4 MB PCI ivshmem UMA ring."""
    from .zoe_uma import UmaBridge

    n_nodes = _validate_zo3_count(count)
    target_flavor = _normalize_target_flavor(target)
    resolved_mode, w, h = _resolve_display_geometry(mode, geometry, True)
    backend, disp_args = _build_display_args(display_backend, w, h)
    iso_p = Path(iso_path).expanduser().resolve()
    if not iso_p.is_file():
        raise FileNotFoundError(f"ISO not built yet: {iso_p}. Run `/os build` first.")
    st_dir = Path(state_dir).expanduser().resolve()
    _verify_kvm_access()
    ovmf = _resolve_ovmf_firmware()

    u_dir, u_shm = _resolve_uma_paths(uma_dir, uma_shm)
    UmaBridge(u_dir, shm_path=u_shm).ensure_initialized()

    themes = {1: "gem", 2: "amber", 3: "gem"}
    roles = {1: "ZO3-1 GEM/Artline", 2: "ZO3-2 Neuro/AmberCRT", 3: "ZO3-3 Verifier"}
    disks = [_ensure_node_state_disk(st_dir / f"zoe-state-node{nid}.img", nid, themes[nid]) for nid in range(1, n_nodes + 1)]
    for disk in disks:
        _check_disk_unlocked(disk)

    launched: list[dict[str, Any]] = []
    procs: list[subprocess.Popen[str]] = []
    try:
        for nid, disk in enumerate(disks, start=1):
            cmd = [
                "qemu-system-x86_64",
                "-name", f"{roles[nid]} [HARDWARE UMA SLOT {nid}]",
                "-enable-kvm", "-machine", "q35", "-cpu", "host",
                "-m", "1024M", "-smp", "2",
                "-bios", str(ovmf),
                "-drive", f"file={iso_p},media=cdrom,readonly=on,if=ide", "-boot", "d",
                "-drive", f"file={disk},format=raw,if=virtio",
                "-netdev", "user,id=net0", "-device", "virtio-net-pci,netdev=net0",
                "-virtfs", f"local,id=uma9p,path={u_dir},mount_tag=zoe_uma,security_model=none",
                "-object", f"memory-backend-file,id=uma_shm,share=on,mem-path={u_shm},size=4M",
                "-device", "ivshmem-plain,memdev=uma_shm",
                "-device", "qemu-xhci", "-device", "usb-tablet",
                *disp_args,
            ]
            node_mon_arg = None if monitor_port_base is None else (0 if int(monitor_port_base) == 0 else int(monitor_port_base) + nid - 1)
            m_port, _ = _append_monitor_qmp_args(cmd, node_mon_arg, None)
            proc = _launch_qemu_checked(cmd)
            procs.append(proc)
            entry: dict[str, Any] = {"node_id": nid, "role": roles[nid], "theme": themes[nid], "pid": proc.pid, "disk": str(disk)}
            if m_port is not None:
                entry["monitor_port"] = m_port
            launched.append(entry)
    except BaseException:
        for proc in procs:
            _cleanup_proc(proc)
        raise
    return {
        "ok": True,
        "count": n_nodes,
        "uma_dir": str(u_dir),
        "uma_shm": str(u_shm),
        "mode": resolved_mode,
        "geometry": f"{w}x{h}",
        "target": target_flavor,
        "display_backend": backend,
        "ovmf": str(ovmf),
        "nodes": launched,
    }


def _prepare_zo3_verify_env(work_p: Path) -> tuple[Path, Path, Any, Path, Path]:
    from .zoe_uma import UmaBridge

    uma_dir = work_p / "zo3_uma_bridge"
    if uma_dir.exists():
        shutil.rmtree(uma_dir)
    uma_shm = work_p / "zo3_uma_bar.shm"
    if uma_shm.exists():
        uma_shm.unlink()
    uma = UmaBridge(uma_dir, shm_path=uma_shm)
    uma.ensure_initialized()

    d1, d2 = work_p / "zo3_node1.img", work_p / "zo3_node2.img"
    for d in (d1, d2):
        if d.exists():
            d.unlink()
    _ensure_node_state_disk(d1, 1, "gem")
    _ensure_node_state_disk(d2, 2, "amber")
    return uma_dir, uma_shm, uma, d1, d2


def verify_zo3_concurrent_kvm(
    iso_path: str | Path,
    work_dir: str | Path,
    *,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    """Boot ZO3-1 (Classic GEM) + ZO3-2 (1985 Amber CRT) CONCURRENTLY sharing one 4 MB PCI ivshmem BAR."""
    from concurrent.futures import ThreadPoolExecutor

    iso_p = Path(iso_path).expanduser().resolve()
    work_p = Path(work_dir).expanduser().resolve()
    work_p.mkdir(parents=True, exist_ok=True)
    _verify_kvm_access()
    ovmf = _resolve_ovmf_firmware()
    uma_dir, uma_shm, uma, d1, d2 = _prepare_zo3_verify_env(work_p)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_single_qemu_boot, iso_p, d1, ovmf, work_p, 11, uma_dir, uma_shm, timeout_sec)
        f2 = pool.submit(_run_single_qemu_boot, iso_p, d2, ovmf, work_p, 12, uma_dir, uma_shm, timeout_sec)
        r1, r2 = f1.result(), f2.result()

    slots = uma.read_all_zo3_slots()
    ok = all((
        r1["boot_ok"], r1["fb_ok"], _screendump_ok(r1),
        r2["boot_ok"], r2["fb_ok"], _screendump_ok(r2),
        1 in slots, 2 in slots,
        slots.get(1, {}).get("node_id") == 1,
        slots.get(2, {}).get("node_id") == 2,
        slots.get(2, {}).get("theme") == "amber",
    ))
    return {"ok": ok, "node_1": r1, "node_2": r2, "uma_slots": slots}


def _verify_static_closure(zoe_p: Path, work_p: Path) -> dict[str, Any]:
    gem_src = zoe_p / "guiai-lab" / "guiai" / "gem"
    here = Path(__file__).resolve().parent
    required = [gem_src / name for name in _ZOE_PY_CLOSURE] + [
        here / "zoe_uma.py",
        here / "zoe_os_runtime.py",
        here / "zoe_gem_fb.c",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Zoe-GEM OS closure files: {missing}")
    stage_rootfs = work_p / "stage_rootfs"
    if stage_rootfs.exists():
        shutil.rmtree(stage_rootfs)
    _copy_zoe_closure(stage_rootfs, zoe_p)
    lib_zoe = stage_rootfs / "usr" / "lib" / "zoe"
    probe_code = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from guiai.gem import zoe_sisters\n"
        "from guiai.gem.zoe_gem_os import zoe_uma\n"
        "import zoe_os_runtime\n"
        "assert len(zoe_sisters.ZOE_SISTERS) == 9\n"
        "assert zoe_sisters.SAFETY_INVARIANTS['sentience_claimed'] is False\n"
        "assert zoe_uma.UMA_SHM_SIZE == 4 * 1024 * 1024\n"
        "print(json.dumps({'sisters_count': len(zoe_sisters.ZOE_SISTERS), 'sisters_file': zoe_sisters.__file__}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-I", "-c", probe_code, str(lib_zoe)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Isolated guest closure import failed: {proc.stderr.strip() or proc.stdout.strip()}")
    meta = json.loads(proc.stdout.strip())
    return {
        "ok": True,
        "closure_files": len(_ZOE_PY_CLOSURE) + 2,
        "sisters_included": "zoe_sisters.py" in _ZOE_PY_CLOSURE,
        "sisters_count": meta["sisters_count"],
        "sisters_isolated_import": True,
    }


def _verify_audit_jsonl(audit_path: Path) -> tuple[bool, int]:
    if not audit_path.is_file():
        return False, 0
    prev_sha = "genesis"
    count = 0
    for raw in audit_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rec = json.loads(line)
        payload = {k: v for k, v in rec.items() if k != "sha256"}
        recomputed = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if rec.get("prev_sha") != prev_sha or rec.get("sha256") != recomputed:
            return False, count
        prev_sha = rec["sha256"]
        count += 1
    return count > 0, count


def _verify_static_uma_contract(work_p: Path) -> dict[str, Any]:
    from .zoe_uma import UMA_SHM_SIZE, UmaBridge, find_guest_ivshmem_bar2

    pci_dev = work_p / "uma_sys" / "bus" / "pci" / "devices" / "0000:00:04.0"
    pci_dev.mkdir(parents=True, exist_ok=True)
    (pci_dev / "vendor").write_text("0x1af4\n", encoding="utf-8")
    (pci_dev / "device").write_text("0x1110\n", encoding="utf-8")
    bar2_file = pci_dev / "resource2"
    bar2_file.write_bytes(b"\x00" * UMA_SHM_SIZE)
    found_bar2 = find_guest_ivshmem_bar2(work_p / "uma_sys" / "bus" / "pci" / "devices")

    uma_dir = work_p / "uma_contract_bridge"
    uma_shm = work_p / "uma_contract.shm"
    uma = UmaBridge(uma_dir, shm_path=uma_shm)
    st0 = uma.ensure_initialized()
    sample = work_p / "sample.gem"
    sample.write_text("GEM", encoding="utf-8")
    blocked_private = False
    try:
        uma.transfer_file("zoe", sample)
    except PermissionError:
        blocked_private = True
    st1 = uma.set_consent("nick", True, reason="static_verify_req")
    blocked_requested = False
    try:
        uma.transfer_file("zoe", sample)
    except PermissionError:
        blocked_requested = True
    st2 = uma.set_consent("zoe", True, reason="static_verify_shared")
    xfer = uma.transfer_file("zoe", sample)
    for slot_id in range(4):
        uma.write_shm_heartbeat(f"node-{slot_id}", {"gate": st2["gate"], "slot": slot_id}, slot=slot_id)
    slots = uma.read_all_zo3_slots()
    audit_ok, audit_count = _verify_audit_jsonl(uma_dir / "uma_audit.jsonl")

    qemu_cmd = _build_verify_qemu_cmd(work_p / "d.iso", work_p / "s.img", work_p / "ovmf.fd", 45123, uma_dir, uma_shm)
    joined_cmd = " ".join(qemu_cmd)
    qemu_args_ok = (
        "ivshmem-plain" in joined_cmd
        and "size=4M" in joined_cmd
        and "mount_tag=zoe_uma" in joined_cmd
        and "tcp:127.0.0.1:" in joined_cmd
        and "unix:" not in joined_cmd
    )
    ok = all((
        _DEFAULT_UMA_SHM == "/dev/shm/zoe-uma-bar.shm",
        UMA_SHM_SIZE == 4 * 1024 * 1024,
        found_bar2 == bar2_file,
        st0["gate"] == "PRIVATE",
        st1["gate"] == "REQUESTED",
        st2["gate"] == "SHARED",
        blocked_private,
        blocked_requested,
        xfer["ok"] is True,
        len(slots) == 4,
        audit_ok,
        qemu_args_ok,
    ))
    return {
        "ok": ok,
        "bar2_found": found_bar2 is not None,
        "slots_verified": sorted(slots.keys()),
        "audit_records": audit_count,
        "audit_chain_ok": audit_ok,
        "qemu_args_ok": qemu_args_ok,
    }


def _write_synthetic_sys_proc_dev(base: Path, uma_shm_size: int) -> tuple[Path, Path, Path]:
    proc_root, sys_root, dev_root = base / "proc", base / "sys", base / "dev"
    for d in (proc_root, dev_root / "input", sys_root / "class" / "graphics" / "fb0", sys_root / "class" / "net" / "eth0"):
        d.mkdir(parents=True, exist_ok=True)
    (proc_root / "cpuinfo").write_text("processor\t: 0\nmodel name\t: Zoe Static CPU\nflags\t\t: hypervisor\nprocessor\t: 1\n", encoding="utf-8")
    (proc_root / "meminfo").write_text("MemTotal:        1048576 kB\nMemAvailable:     786432 kB\n", encoding="utf-8")
    (proc_root / "cmdline").write_text("console=ttyS0 zoe.node=1 zoe.theme=gem\n", encoding="utf-8")
    (sys_root / "class" / "graphics" / "fb0" / "virtual_size").write_text("1024,768\n", encoding="utf-8")
    (sys_root / "class" / "graphics" / "fb0" / "bits_per_pixel").write_text("32\n", encoding="utf-8")
    (dev_root / "fb0").write_bytes(b"")
    (sys_root / "class" / "net" / "eth0" / "operstate").write_text("up\n", encoding="utf-8")
    pci_dev = sys_root / "bus" / "pci" / "devices" / "0000:00:04.0"
    pci_dev.mkdir(parents=True, exist_ok=True)
    (pci_dev / "vendor").write_text("0x1af4\n", encoding="utf-8")
    (pci_dev / "device").write_text("0x1110\n", encoding="utf-8")
    (pci_dev / "resource2").write_bytes(b"\x00" * uma_shm_size)
    return proc_root, sys_root, dev_root


def _verify_static_safety_and_boot_chain(work_p: Path) -> dict[str, Any]:
    from .zoe_os_runtime import observe_hardware, run_boot_sync
    from .zoe_pixel_os import _HONESTY_FLAGS, verify_pixel_os_static
    from .zoe_uma import UMA_SHM_SIZE, UmaBridge

    proc_root, sys_root, dev_root = _write_synthetic_sys_proc_dev(work_p / "synth", UMA_SHM_SIZE)
    state_dir = work_p / "boot_state"
    uma_dir = work_p / "boot_uma"
    UmaBridge(uma_dir, shm_path=work_p / "boot_uma.shm").ensure_initialized()
    b1 = run_boot_sync(state_dir, work_p / "run1.json", proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir)
    b2 = run_boot_sync(state_dir, work_p / "run2.json", proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir)
    hw_obs = observe_hardware(state_dir=state_dir, proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir)

    tamper_dir = work_p / "tamper_state"
    shutil.copytree(state_dir, tamper_dir)
    lines = (tamper_dir / "boot_chain.jsonl").read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["ram_mb"] = int(rec["ram_mb"]) + 999
    lines[0] = json.dumps(rec, sort_keys=True)
    (tamper_dir / "boot_chain.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tamper_rep = run_boot_sync(tamper_dir, work_p / "run_tamper.json", proc_root=proc_root, sys_root=sys_root, dev_root=dev_root, uma_dir=uma_dir)

    pixel_res = verify_pixel_os_static(work_p / "pixel_static")
    expected_gates = {"cpu_arch", "ram_headroom", "persistent_storage", "display_fb", "input_devices", "network", "hardware_uma"}
    ok = all((
        b1["boot_count"] == 1 and b1["chain_intact"] and not b1["restored_from_prior"],
        b2["boot_count"] == 2 and b2["chain_intact"] and b2["restored_from_prior"],
        b2["prev_sha"] == b1["chain_sha"] and b2["vault_restored"],
        b2.get("sisters_count") == 9 and b2.get("council_leads") == ["Mono", "Zoe", "Eliza"],
        set(hw_obs["gates"].keys()) == expected_gates,
        tamper_rep["chain_intact"] is False and tamper_rep["restored_from_prior"] is False,
        _HONESTY_FLAGS["auto_flash_allowed"] is False and _HONESTY_FLAGS["flight_control_authorized"] is False,
        _HONESTY_FLAGS["external_actions"] == 0 and pixel_res["ok"] is True,
    ))
    return {
        "ok": ok,
        "boot_1_count": b1["boot_count"],
        "boot_2_count": b2["boot_count"],
        "tamper_rejected": not tamper_rep["chain_intact"],
        "gates_count": len(hw_obs["gates"]),
        "pixel_ok": pixel_res["ok"],
    }


def verify_zoe_gem_os_static(
    zoe_root: str | Path,
    work_dir: str | Path,
    *,
    kernel_flavor: str = "virt",
) -> dict[str, Any]:
    """Static/unit verifier for Zoe-GEM OS closure, UMA contracts, 7 safety gates, and SHA-256 boot chain."""
    flavor = _normalize_target_flavor(kernel_flavor)
    zoe_p = Path(zoe_root).expanduser().resolve()
    work_p = Path(work_dir).expanduser().resolve()
    work_p.mkdir(parents=True, exist_ok=True)
    closure = _verify_static_closure(zoe_p, work_p)
    uma_contract = _verify_static_uma_contract(work_p)
    safety = _verify_static_safety_and_boot_chain(work_p)
    ok = bool(closure["ok"] and uma_contract["ok"] and safety["ok"])
    return {
        "ok": ok,
        "mode": "static_dry_run",
        "kernel_flavor": flavor,
        "kvm_invoked": False,
        "closure": closure,
        "uma_contract": uma_contract,
        "safety_and_boot_chain": safety,
        **_CONSTITUTIONAL_FLAGS,
    }


def format_usb_stage2_guide(iso_path: str | Path) -> list[str]:
    """Read-only Stage 2 bare-metal USB guide (never writes silently to physical drives)."""
    iso_p = Path(iso_path).expanduser().resolve()
    blk_lines = []
    try:
        out = subprocess.check_output(["lsblk", "-o", "NAME,SIZE,TRAN,TYPE,MODEL,MOUNTPOINT"], text=True)
        for ln in out.splitlines():
            if not ln.startswith("loop"):
                blk_lines.append("  " + ln)
    except Exception:
        blk_lines.append("  (run `lsblk` to list attached USB sticks)")
    return [
        "Zoe-GEM OS Stage 2 — Safe Bare-Metal Live USB Guide (Tiger Lake i5-1145G7 · UEFI Boot)",
        f"  ISO Ready : {iso_p} ({'FOUND' if iso_p.is_file() else 'RUN `/os build lts` FIRST'})",
        "  Attached block devices (read-only scan — NEVER target nvme0n1 or your research drive!):",
        *blk_lines[:14],
        "  Manual write command (replace /dev/sdX ONLY with your spare empty USB stick):",
        f"    sudo dd if={iso_p} of=/dev/sdX bs=4M status=progress conv=fsync && sync",
        "  Boot: Reboot -> UEFI Boot Menu (F12) -> select USB -> Zoe-GEM OS boots straight into /dev/fb0.",
        "  Wi-Fi on bare metal: Press [T] for Zoe-OS shell -> run `wifi <SSID> <PASSWORD>`.",
        "  Unplug USB anytime to return to your untouched Ubuntu workstation.",
    ]

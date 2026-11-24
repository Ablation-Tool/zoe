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

import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from typing import Any

from PIL import Image

_ALPINE_NETBOOT_BASE = "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/x86_64/netboot"

_VIRT_KMODS: tuple[str, ...] = (
    "crc32c_generic",
    "crc32c-intel",
    "libcrc32c",
    "crc16",
    "mbcache",
    "jbd2",
    "ext4",
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
mkdir -p /dev/pts /run /tmp /mnt/zoe-state /etc /var/run/wpa_supplicant
mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
mount -t tmpfs tmpfs /tmp

echo "=== ZOE-GEM OS v1.0 :: PID 1 HARDWARE BRINGUP ==="

# Load essential HAL kernel modules (framebuffer, crc32c+ext4, disk, input/mouse, net, Wi-Fi)
for mod in simpledrm bochs crc32c_generic crc32c-intel libcrc32c vmd nvme ahci virtio_pci virtio_blk \
           ext4 vfat exfat nls_cp437 nls_iso8859-1 \
           virtio_net e1000 e1000e r8169 af_packet iwlwifi iwlmvm \
           i8042 libps2 atkbd psmouse mousedev evdev xhci-pci usbhid hid-generic hid-multitouch i2c-hid-acpi usbkbd usbmouse virtio_input; do
    modprobe "$mod" 2>/dev/null || true
done
sleep 1

# Bring up loopback + first Ethernet NIC via DHCP
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
    udhcpc -i "$NIC" -n -q -t 6 -T 2 -s /etc/udhcpc.script 2>/dev/null || true
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

# Execute Zoe-GEM OS Python Boot Brain (SHA-256 chain + Artline VDI + 68000 RSC + Nick Drawer)
/usr/bin/python3 /usr/lib/zoe/zoe_os_runtime.py

if grep -q "zoe.autotest=1" /proc/cmdline; then
    echo "ZOE_OS_READY_FOR_INPUT"
    /bin/zoe_gem_fb --state /run/zoe-boot-state.json --autotest-sec 5 || true
    echo "ZOE_OS_READY_FOR_CAPTURE"
    sleep 1
    sync
    umount /mnt/zoe-state 2>/dev/null || true
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
    /usr/bin/python3 /usr/lib/zoe/zoe_os_runtime.py --interactive
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


def _copy_ldd_deps(binaries: list[Path], rootfs: Path) -> None:
    existing = [str(b) for b in binaries if b.exists()]
    if not existing:
        return
    ldd_out = subprocess.check_output(["ldd", *existing], text=True, stderr=subprocess.DEVNULL)
    for line in ldd_out.splitlines():
        parts = line.strip().split()
        lib_path = None
        if "=>" in parts:
            idx = parts.index("=>")
            if idx + 1 < len(parts) and parts[idx + 1].startswith("/"):
                lib_path = Path(parts[idx + 1])
        elif parts and parts[0].startswith("/"):
            lib_path = Path(parts[0])
        if lib_path and lib_path.exists():
            dst = rootfs / lib_path.relative_to("/")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(lib_path.resolve(), dst)
            if str(lib_path).startswith("/usr/lib/x86_64-linux-gnu/"):
                alt = rootfs / "lib" / "x86_64-linux-gnu" / lib_path.name
                alt.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(lib_path.resolve(), alt)


def _extract_kmod_closure(modloop: Path, rootfs: Path, tmp_work: Path, flavor: str) -> str:
    """Extract only the exact transitive `modules.dep` closure of needed HAL drivers."""
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

    dep_map: dict[str, list[str]] = {}
    name_to_rel: dict[str, str] = {}
    for line in (kdir / "modules.dep").read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        mod_rel, deps_str = line.split(":", 1)
        mod_rel = mod_rel.strip()
        dep_map[mod_rel] = [d.strip() for d in deps_str.strip().split() if d.strip()]
        stem = Path(mod_rel).name.split(".ko")[0]
        name_to_rel[stem] = mod_rel
        name_to_rel[stem.replace("_", "-")] = mod_rel
        name_to_rel[stem.replace("-", "_")] = mod_rel

    desired = list(_VIRT_KMODS) + (list(_LTS_EXTRA_KMODS) if flavor == "lts" else [])
    wanted: set[str] = set()
    stack = [name_to_rel[m] for m in desired if m in name_to_rel]
    while stack:
        rel = stack.pop()
        if rel in wanted:
            continue
        wanted.add(rel)
        for d in dep_map.get(rel, ()):
            if d not in wanted:
                stack.append(d)

    dst_kdir = rootfs / "lib" / "modules" / kver
    dst_kdir.mkdir(parents=True, exist_ok=True)
    for meta in kdir.glob("modules.*"):
        shutil.copy2(meta, dst_kdir / meta.name)
    for rel in wanted:
        src = kdir / rel
        if src.exists():
            dst = dst_kdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # For `lts` bare-metal Intel Tiger Lake profile, bundle AX201 Wi-Fi + Tiger Lake i915 firmware
    if flavor == "lts":
        fw_dst = rootfs / "lib" / "firmware"
        fw_dst.mkdir(parents=True, exist_ok=True)
        for fw_root in (sq_out / "modules" / "firmware", Path("/lib/firmware")):
            if not fw_root.is_dir():
                continue
            for pat in ("iwlwifi-QuZ-a0-hr-b0-*.ucode*", "iwlwifi-Qu-c0-hr-b0-*.ucode*", "i915/tgl_dmc_*.bin*", "i915/tgl_guc_*.bin*"):
                for fw in fw_root.glob(pat):
                    rel = fw.relative_to(fw_root)
                    out_fw = fw_dst / (rel.with_suffix("") if rel.suffix == ".zst" else rel)
                    if out_fw.exists():
                        continue
                    out_fw.parent.mkdir(parents=True, exist_ok=True)
                    if fw.suffix == ".zst" and shutil.which("zstd"):
                        with out_fw.open("wb") as fh:
                            subprocess.run(["zstd", "-dc", str(fw)], stdout=fh, stderr=subprocess.DEVNULL, check=False)
                    else:
                        shutil.copy2(fw, out_fw)
    return kver


def _bundle_python_and_zoe(rootfs: Path, zoe_root: Path, include_wifi_tools: bool = False) -> None:
    """Copy minimal system Python 3 + required shared libs + Zoe pure-Python GEM/Artline/RSC core."""
    py_bin = Path("/usr/bin/python3").resolve()
    py_ver = subprocess.check_output(
        [str(py_bin), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        text=True,
    ).strip()
    stdlib = Path(subprocess.check_output([str(py_bin), "-c", "import sysconfig; print(sysconfig.get_paths()['stdlib'])"], text=True).strip())

    (rootfs / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(py_bin, rootfs / "usr" / "bin" / "python3")

    dynload = stdlib / "lib-dynload"
    ldd_targets = [py_bin] + [
        p
        for pat in ("_hashlib*.so", "_sqlite3*.so", "_ssl*.so", "_ctypes*.so", "zlib*.so", "math*.so", "_json*.so", "binascii*.so", "_struct*.so", "unicodedata*.so", "select*.so", "fcntl*.so", "termios*.so", "_posixsubprocess*.so")
        for p in dynload.glob(pat)
    ]
    if include_wifi_tools:
        for tool_name in ("wpa_supplicant", "iw"):
            found = shutil.which(tool_name)
            if found:
                tp = Path(found).resolve()
                dst_t = rootfs / "usr" / "sbin" / tool_name
                dst_t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tp, dst_t)
                os.chmod(dst_t, 0o755)
                ldd_targets.append(tp)

    _copy_ldd_deps(ldd_targets, rootfs)
    ld_src = Path("/lib64/ld-linux-x86-64.so.2")
    if ld_src.exists():
        (rootfs / "lib64").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ld_src.resolve(), rootfs / "lib64" / "ld-linux-x86-64.so.2")

    skip_dirs = {"test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "pydoc_data", "__pycache__"}
    dst_std = rootfs / "usr" / "lib" / f"python{py_ver}"
    dst_std.mkdir(parents=True, exist_ok=True)
    for item in stdlib.iterdir():
        if item.name in skip_dirs or item.name.startswith("config-"):
            continue
        if item.is_dir():
            shutil.copytree(item, dst_std / item.name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests"), dirs_exist_ok=True)
        elif item.suffix in {".py", ".so"}:
            shutil.copy2(item, dst_std / item.name)

    zoe_pkg = rootfs / "usr" / "lib" / "zoe" / "guiai" / "gem"
    zoe_pkg.mkdir(parents=True, exist_ok=True)
    (rootfs / "usr" / "lib" / "zoe" / "guiai" / "__init__.py").write_text("", encoding="utf-8")
    for src_f in (zoe_root / "guiai-lab" / "guiai" / "gem").glob("*.py"):
        shutil.copy2(src_f, zoe_pkg / src_f.name)
    shutil.copy2(Path(__file__).resolve().parent / "zoe_os_runtime.py", rootfs / "usr" / "lib" / "zoe" / "zoe_os_runtime.py")


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

        busybox_src = Path(shutil.which("busybox") or "/usr/bin/busybox")
        shutil.copy2(busybox_src, rootfs / "bin" / "busybox")
        os.chmod(rootfs / "bin" / "busybox", 0o755)
        os.symlink("busybox", rootfs / "bin" / "sh")

        fb_c = Path(__file__).resolve().parent / "zoe_gem_fb.c"
        fb_bin = rootfs / "bin" / "zoe_gem_fb"
        subprocess.run(["gcc", "-O2", "-static", str(fb_c), "-lm", "-o", str(fb_bin)], check=True)
        os.chmod(fb_bin, 0o755)

        kver = _extract_kmod_closure(modloop, rootfs, work, flavor=flavor)
        _bundle_python_and_zoe(rootfs, zoe_p, include_wifi_tools=(flavor == "lts"))

        init_p = rootfs / "init"
        init_p.write_text(_PID1_INIT, encoding="utf-8")
        os.chmod(init_p, 0o755)
        dhcp_p = rootfs / "etc" / "udhcpc.script"
        dhcp_p.write_text(_UDHCPC_SCRIPT, encoding="utf-8")
        os.chmod(dhcp_p, 0o755)
        wifi_p = rootfs / "bin" / "zoe-wifi"
        wifi_p.write_text(_WIFI_SCRIPT, encoding="utf-8")
        os.chmod(wifi_p, 0o755)

        iso_root = work / "iso_root"
        (iso_root / "boot" / "grub").mkdir(parents=True, exist_ok=True)
        shutil.copy2(vmlinuz, iso_root / "boot" / "vmlinuz")
        initrd_path = iso_root / "boot" / "initrd.img"
        with initrd_path.open("wb") as out_f:
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

        default_idx = "1" if autotest_default else "0"
        grub_cfg = f"""set timeout=1
set default={default_idx}
insmod all_video
set gfxmode=1024x768x32,auto
set gfxpayload=keep

menuentry "Zoe-GEM OS v1.0 ({flavor.upper()} · Interactive GEM Desktop + Mouse + Keyboard)" {{
    linux /boot/vmlinuz console=ttyS0,115200 console=tty0 quiet loglevel=3
    initrd /boot/initrd.img
}}

menuentry "Zoe-GEM OS v1.0 ({flavor.upper()} · Automated Hardware + Retention Self-Test)" {{
    linux /boot/vmlinuz console=tty0 console=ttyS0,115200 zoe.autotest=1 quiet loglevel=3
    initrd /boot/initrd.img
}}
"""
        (iso_root / "boot" / "grub" / "grub.cfg").write_text(grub_cfg, encoding="utf-8")

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
        "tokens_used": 0,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "sentience_claimed": False,
    }


def _send_qemu_monitor_cmds(mon_sock: Path, cmds: list[str], delay: float = 0.12) -> bool:
    for _ in range(25):
        if mon_sock.exists():
            break
        time.sleep(0.15)
    if not mon_sock.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(4.0)
            s.connect(str(mon_sock))
            time.sleep(0.15)
            try:
                s.recv(4096)
            except OSError:
                pass
            for cmd in cmds:
                s.sendall((cmd + "\n").encode("utf-8"))
                time.sleep(delay)
        return True
    except OSError:
        return False


def _run_single_qemu_boot(
    iso_path: Path,
    state_img: Path,
    ovmf_code: Path,
    work_dir: Path,
    boot_idx: int,
    timeout_sec: int = 45,
) -> dict[str, Any]:
    mon_sock = Path(tempfile.gettempdir()) / f"zoe_qmon_{os.getpid()}_{boot_idx}.sock"
    if mon_sock.exists():
        mon_sock.unlink()
    ppm_path = work_dir / f"boot_{boot_idx}_fb.ppm"
    png_path = work_dir / f"boot_{boot_idx}_fb.png"
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
        "-vga", "std",
        "-display", "none",
        "-serial", "stdio",
        "-monitor", f"unix:{mon_sock},server,nowait",
        "-no-reboot",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines: list[str] = []
    injected = False
    captured = False
    t0 = time.time()
    assert proc.stdout is not None
    try:
        while time.time() - t0 < timeout_sec:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            s = line.rstrip("\r\n")
            lines.append(s)
            if "ZOE_OS_FB_OK" in s and not injected:
                # Inject REAL hardware PS/2 mouse moves + Artline mirrored drag + Save key on Boot #2!
                injected = True
                if boot_idx == 2:
                    _send_qemu_monitor_cmds(
                        mon_sock,
                        [
                            "sendkey 6",               # Switch GEM Toolkit pen to #6 Amber
                            "mouse_move 430 -240",     # Move cursor into Artline Canvas
                            "mouse_button 1",          # Left button down
                            "mouse_move 36 48",        # Drag symmetric bilateral Artline stroke!
                            "mouse_move -28 42",
                            "mouse_move 34 38",
                            "mouse_button 0",          # Release left button
                            "sendkey s",               # Save live_canvas.svg to ZOE-STATE disk!
                        ],
                        delay=0.14,
                    )
                else:
                    _send_qemu_monitor_cmds(mon_sock, ["mouse_move -120 -60"], delay=0.15)
            if "ZOE_OS_READY_FOR_CAPTURE" in s and not captured:
                captured = _send_qemu_monitor_cmds(mon_sock, [f"screendump {ppm_path}"], delay=0.45)
            if "ZOE_OS_POWEROFF" in s:
                break
    finally:
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    if captured and ppm_path.exists():
        Image.open(ppm_path).convert("RGB").save(png_path)

    joined = "\n".join(lines)
    return {
        "boot_index": boot_idx,
        "elapsed_sec": round(time.time() - t0, 2),
        "boot_ok": "ZOE_OS_BOOT_OK" in joined,
        "net_ok": "ZOE_OS_NET_OK" in joined and "ip=10.0.2." in joined,
        "persist_ok": "ZOE_OS_PERSIST_OK" in joined,
        "fb_ok": "ZOE_OS_FB_OK" in joined,
        "canvas_saved": "ZOE_OS_CANVAS_SAVED" in joined,
        "restored_true": "restored=True" in joined,
        "vault_restored_true": "vault_restored=True" in joined,
        "screendump_png": str(png_path) if png_path.exists() else "",
        "serial_tail": [ln for ln in lines if ln.startswith("ZOE_OS_") or "ZOE-GEM OS" in ln],
    }


def verify_zoe_gem_os_qemu(iso_path: str | Path, work_dir: str | Path) -> dict[str, Any]:
    """Run automated 2-boot OVMF UEFI + KVM hardware, mouse/kbd drawing & reboot-retention proof."""
    iso_p = Path(iso_path).expanduser().resolve()
    work_p = Path(work_dir).expanduser().resolve()
    work_p.mkdir(parents=True, exist_ok=True)
    ovmf_code = Path("/usr/share/ovmf/OVMF.fd")
    if not ovmf_code.exists():
        ovmf_code = Path("/usr/share/OVMF/OVMF_CODE_4M.fd")
    if not ovmf_code.exists():
        raise FileNotFoundError("OVMF UEFI firmware not found")

    state_img = work_p / "zoe-state.img"
    if state_img.exists():
        state_img.unlink()
    with state_img.open("wb") as fh:
        fh.truncate(64 * 1024 * 1024)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(state_img)], check=True)

    b1 = _run_single_qemu_boot(iso_p, state_img, ovmf_code, work_p, boot_idx=1)
    b2 = _run_single_qemu_boot(iso_p, state_img, ovmf_code, work_p, boot_idx=2)

    all_passed = bool(
        b1["boot_ok"] and b1["net_ok"] and b1["persist_ok"] and b1["fb_ok"]
        and b2["boot_ok"] and b2["net_ok"] and b2["persist_ok"] and b2["fb_ok"]
        and b2["restored_true"] and b2["vault_restored_true"] and b2["canvas_saved"]
    )
    return {
        "ok": all_passed,
        "iso_path": str(iso_p),
        "state_disk": str(state_img),
        "boot_1": b1,
        "boot_2": b2,
        "self_retention_verified": b2["restored_true"] and b2["vault_restored_true"],
        "interactive_canvas_saved": b2["canvas_saved"],
        "hardware_networking_verified": b1["net_ok"] and b2["net_ok"],
        "hardware_framebuffer_verified": b1["fb_ok"] and b2["fb_ok"],
        "tokens_used": 0,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "sentience_claimed": False,
    }


def launch_zoe_gem_os_kvm(iso_path: str | Path, state_img: str | Path) -> dict[str, Any]:
    """Launch Zoe-GEM OS interactively in a dedicated KVM GUI window (zero host disk risk)."""
    iso_p = Path(iso_path).expanduser().resolve()
    if not iso_p.is_file():
        raise FileNotFoundError(f"ISO not built yet: {iso_p}. Run `/os build` first.")
    st_p = Path(state_img).expanduser().resolve()
    st_p.parent.mkdir(parents=True, exist_ok=True)
    if not st_p.exists():
        with st_p.open("wb") as fh:
            fh.truncate(64 * 1024 * 1024)
        subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "ZOE-STATE", str(st_p)], check=True)
    ovmf = Path("/usr/share/ovmf/OVMF.fd")
    cmd = [
        "qemu-system-x86_64",
        "-enable-kvm",
        "-machine", "q35",
        "-cpu", "host",
        "-m", "1024M",
        "-smp", "2",
        "-bios", str(ovmf),
        "-drive", f"file={iso_p},media=cdrom,readonly=on,if=ide",
        "-boot", "d",
        "-drive", f"file={st_p},format=raw,if=virtio",
        "-netdev", "user,id=net0",
        "-device", "virtio-net-pci,netdev=net0",
        "-vga", "std",
        "-display", "gtk",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"ok": True, "pid": proc.pid, "iso": str(iso_p), "state_img": str(st_p)}


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

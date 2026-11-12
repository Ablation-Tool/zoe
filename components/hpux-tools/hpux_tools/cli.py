from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

TOOLS = Path("/home/cowboy/security-tools")
RUNTIME = TOOLS / "hpux-runtime"
SYSROOT = TOOLS / "sysroot"


def _setting(environment, name, default):
    return Path(environment.get(name, default)).expanduser()


def _paths(environment=None):
    environment = os.environ if environment is None else environment
    return {
        "guest_gdb": _setting(environment, "ZOE_HPUX_GUEST_GDB", "/scratch/gdb-install/bin/hppa-hp-hpux-gdb"),
        "qemu": _setting(environment, "ZOE_HPUX_QEMU", SYSROOT / "usr/bin/qemu-system-hppa"),
        "qemu_data": _setting(environment, "ZOE_HPUX_QEMU_DATA", SYSROOT / "usr/share/qemu"),
        "image": _setting(environment, "ZOE_HPUX_IMAGE", RUNTIME / "hpux-10.20-preinstalled.img"),
        "scratch_disk": _setting(environment, "ZOE_HPUX_SCRATCH_DISK", RUNTIME / "hpux-build-scratch.qcow2"),
        "install_iso": _setting(environment, "ZOE_HPUX_INSTALL_ISO", RUNTIME / "DISC1-Install-and-CoreOS.iso"),
        "install_disk": _setting(environment, "ZOE_HPUX_INSTALL_DISK", RUNTIME / "hpux-10.20.qcow2"),
    }


def gdb_command(arguments, environment=None):
    paths = _paths(environment)
    command = shlex.join([str(paths["guest_gdb"]), *arguments])
    return f"mount /dev/dsk/c0t5d0 /scratch && {command}"


def qemu_command(arguments, environment=None):
    paths = _paths(environment)
    if not paths["qemu"].is_file():
        raise ValueError(f"HP-UX QEMU is unavailable: {paths['qemu']}")
    command = [str(paths["qemu"])]
    if "-L" not in arguments:
        command.extend(["-L", str(paths["qemu_data"])])
    command.extend(arguments)
    return command


def boot_command(arguments, write=False, environment=None):
    paths = _paths(environment)
    if not paths["image"].is_file():
        raise ValueError(f"HP-UX system image is unavailable: {paths['image']}; set ZOE_HPUX_IMAGE or complete the runtime acquisition")
    command = [
        "-machine", "B160L",
        "-accel", "tcg,thread=single",
        "-m", "512",
        "-drive", f"if=scsi,bus=0,index=6,file={paths['image']},format=raw",
        "-net", "nic,model=tulip",
        "-net", "user",
        "-boot", "order=m",
        "-serial", "mon:stdio",
        "-nographic",
    ]
    if paths["scratch_disk"].is_file():
        command.insert(4, "-drive")
        command.insert(5, f"if=scsi,bus=0,index=5,file={paths['scratch_disk']},format=qcow2")
    if not write:
        command.append("-snapshot")
    return qemu_command([*command, *arguments], environment)


def install_command(arguments, environment=None):
    paths = _paths(environment)
    for name in ("install_iso", "install_disk"):
        if not paths[name].is_file():
            raise ValueError(f"HP-UX installation input is unavailable: {paths[name]}")
    command = [
        "-machine", "B160L",
        "-accel", "tcg,thread=single",
        "-m", "512",
        "-drive", f"file={paths['install_disk']},if=none,id=hd6,format=qcow2,cache=writethrough",
        "-device", "scsi-hd,drive=hd6,bus=scsi.0,scsi-id=6,vendor=SEAGATE,product=ST12400N",
        "-drive", f"file={paths['install_iso']},if=scsi,bus=0,index=2,media=cdrom,format=raw",
        "-boot", "d",
        "-serial", "mon:stdio",
        "-nographic",
    ]
    return qemu_command([*command, *arguments], environment)


def _version(path):
    try:
        result = subprocess.run([str(path), "--version"], capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        return f"unavailable: {error}"
    output = (result.stdout or result.stderr).splitlines()
    return output[0] if output else f"version query exited {result.returncode}"


def doctor(environment=None):
    paths = _paths(environment)
    qemu_present = paths["qemu"].is_file()
    image_present = paths["image"].is_file()
    print(f"qemu: {paths['qemu']}")
    print(f"  present: {str(qemu_present).lower()}")
    if qemu_present:
        print(f"  version: {_version(paths['qemu'])}")
    print(f"qemu_data: {paths['qemu_data']} (present: {str(paths['qemu_data'].is_dir()).lower()})")
    for name in ("image", "scratch_disk", "install_iso", "install_disk"):
        print(f"{name}: {paths[name]} (present: {str(paths[name].is_file()).lower()})")
    print(f"guest_gdb: {paths['guest_gdb']} (checked when the guest boots)")
    return 0 if qemu_present and image_present else 1


def parser():
    result = argparse.ArgumentParser(prog="zoe launch hpux-tools", description="Zoe-managed HP-UX SOM analysis and emulation")
    commands = result.add_subparsers(dest="operation", required=True)
    commands.add_parser("doctor", help="report tool, firmware, and runtime availability")
    gdb = commands.add_parser("gdb", help="run native HP-UX SOM GDB inside the guest")
    gdb.add_argument("--write", action="store_true", help="permit persistent guest changes")
    gdb.add_argument("arguments", nargs=argparse.REMAINDER)
    guest = commands.add_parser("guest", help="run one command inside the HP-UX guest")
    guest.add_argument("--write", action="store_true", help="permit persistent guest changes")
    guest.add_argument("command", help="shell command to run in the guest")
    qemu = commands.add_parser("qemu", help="run qemu-system-hppa with the Zoe firmware path")
    qemu.add_argument("arguments", nargs=argparse.REMAINDER)
    boot = commands.add_parser("boot", help="boot the HP-UX 10.20 system image")
    boot.add_argument("--write", action="store_true", help="permit persistent writes; default is snapshot mode")
    boot.add_argument("arguments", nargs=argparse.REMAINDER)
    install = commands.add_parser("install", help="boot the HP-UX 10.20 installation disc")
    install.add_argument("arguments", nargs=argparse.REMAINDER)
    return result


def _parse_arguments(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] not in {"gdb", "qemu", "boot", "install"}:
        return parser().parse_args(raw)
    command = raw[0]
    tail = raw[1:]
    launcher = []
    if command in {"gdb", "boot"}:
        if "--" in tail:
            separator = tail.index("--")
            launcher = tail[:separator]
            forwarded = tail[separator + 1:]
        else:
            forwarded = [value for value in tail if value != "--write"]
            launcher = [value for value in tail if value == "--write"]
    else:
        if tail[:1] == ["--"]:
            tail = tail[1:]
        forwarded = tail
    normalized = [command, *launcher, "--", *forwarded]
    arguments = parser().parse_args(normalized)
    arguments.arguments = arguments.arguments[1:]
    return arguments


def main(argv=None):
    arguments = _parse_arguments(argv)
    try:
        if arguments.operation == "doctor":
            return doctor()
        if arguments.operation in {"guest", "gdb"}:
            from .guest import run_guest

            command = arguments.command if arguments.operation == "guest" else gdb_command(arguments.arguments)
            return run_guest(command, write=arguments.write)
        if arguments.operation == "qemu":
            command = qemu_command(arguments.arguments)
        elif arguments.operation == "boot":
            command = boot_command(arguments.arguments, write=arguments.write)
        else:
            command = install_command(arguments.arguments)
        return subprocess.run(command, check=False).returncode
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"hpux-tools: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

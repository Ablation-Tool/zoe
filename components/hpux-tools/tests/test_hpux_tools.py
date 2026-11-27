from pathlib import Path

import pytest

from hpux_tools.cli import _parse_arguments, boot_command, doctor, gdb_command, install_command, qemu_command


def _environment(tmp_path):
    gdb = tmp_path / "gdb"
    qemu = tmp_path / "qemu-system-hppa"
    image = tmp_path / "hpux.img"
    iso = tmp_path / "install.iso"
    disk = tmp_path / "disk.qcow2"
    for path in (gdb, qemu, image, iso, disk):
        path.touch()
    return {
        "ZOE_HPUX_GUEST_GDB": str(gdb),
        "ZOE_HPUX_QEMU": str(qemu),
        "ZOE_HPUX_QEMU_DATA": str(tmp_path / "firmware"),
        "ZOE_HPUX_IMAGE": str(image),
        "ZOE_HPUX_INSTALL_ISO": str(iso),
        "ZOE_HPUX_INSTALL_DISK": str(disk),
    }


def test_gdb_forwards_arguments_without_shell(tmp_path):
    environment = _environment(tmp_path)
    command = gdb_command(["-q", "-ex", "info files"], environment)
    assert command == f"mount /dev/dsk/c0t5d0 /scratch && {environment['ZOE_HPUX_GUEST_GDB']} -q -ex 'info files'"


def test_forwarded_options_keep_order_and_write_is_launcher_only():
    qemu = _parse_arguments(["qemu", "--version"])
    assert qemu.arguments == ["--version"]
    gdb = _parse_arguments(["gdb", "-q", "--write", "-ex", "info files"])
    assert gdb.write is True
    assert gdb.arguments == ["-q", "-ex", "info files"]
    separated = _parse_arguments(["gdb", "--write", "--", "-q", "--write"])
    assert separated.write is True
    assert separated.arguments == ["-q", "--write"]


def test_qemu_adds_firmware_path_once(tmp_path):
    environment = _environment(tmp_path)
    assert qemu_command(["--version"], environment) == [
        environment["ZOE_HPUX_QEMU"], "-L", environment["ZOE_HPUX_QEMU_DATA"], "--version"
    ]
    assert qemu_command(["-L", "/other", "--version"], environment) == [
        environment["ZOE_HPUX_QEMU"], "-L", "/other", "--version"
    ]


def test_boot_is_snapshot_by_default_and_write_is_explicit(tmp_path):
    environment = _environment(tmp_path)
    snapshot = boot_command([], environment=environment)
    assert "-snapshot" in snapshot
    assert any("format=raw" in argument for argument in snapshot)
    assert "-snapshot" not in boot_command([], write=True, environment=environment)


def test_install_uses_legacy_scsi_disk_and_cdrom(tmp_path):
    environment = _environment(tmp_path)
    command = install_command([], environment)
    assert any("vendor=SEAGATE,product=ST12400N" in argument for argument in command)
    assert any("media=cdrom,format=raw" in argument for argument in command)
    assert command[-2:] == ["-nographic"] or command[-1] == "-nographic"


def test_missing_tools_and_images_fail_closed(tmp_path):
    missing = {name: str(tmp_path / name) for name in ("ZOE_HPUX_QEMU", "ZOE_HPUX_IMAGE")}
    with pytest.raises(ValueError, match="QEMU"):
        qemu_command([], missing)
    with pytest.raises(ValueError, match="system image"):
        boot_command([], environment=missing)


def test_doctor_reports_missing_tools(tmp_path, capsys):
    environment = _environment(tmp_path)
    assert doctor(environment) == 0
    output = capsys.readouterr().out
    assert "present: true" in output
    assert "QEMU emulator version" in output or "version:" in output


def test_main_preserves_guest_command(monkeypatch):
    from hpux_tools.cli import main

    calls = []
    monkeypatch.setattr("hpux_tools.guest.run_guest", lambda command, write: calls.append((command, write)) or 4)
    assert main(["guest", "--write", "uname -a"]) == 4
    assert calls == [("uname -a", True)]


def test_guest_login_and_command_protocol(tmp_path, monkeypatch):
    import re
    import pexpect
    from hpux_tools.guest import PROMPT, STATUS, run_guest

    environment = _environment(tmp_path)

    class Child:
        def __init__(self):
            self.commands = []
            self.alive = True
            self.match = None

        def expect(self, pattern, *_args, **_kwargs):
            if pattern == STATUS:
                self.match = re.match(r"__ZOE_EXIT__([0-9]+)", "__ZOE_EXIT__7")
            return 0

        def sendline(self, command):
            self.commands.append(command)

        def close(self, force=False):
            self.alive = False

        def isalive(self):
            return self.alive

    child = Child()
    monkeypatch.setattr(pexpect, "spawn", lambda *_args, **_kwargs: child)
    assert run_guest("uname -a", environment=environment) == 7
    assert child.commands[0:2] == ["root", "p4ssw0rd"]
    assert child.commands[2].startswith("{ uname -a; }; __zoe_status=$?;")
    assert "__ZOE_EXIT__%s" in child.commands[2]
    assert child.commands[3] == "cd / && shutdown -h now"
    assert not child.isalive()
    assert PROMPT == r"\r?\n# $"
    output = "\r\r\n__ZOE_EXIT__7\r\r\n# "
    match = re.search(STATUS, output)
    assert match is not None
    assert re.search(PROMPT, output[match.end():]) is not None

    long_child = Child()
    monkeypatch.setattr(pexpect, "spawn", lambda *_args, **_kwargs: long_child)
    assert run_guest("x" * 400, environment=environment) == 7
    assert long_child.commands[2] == "stty -echo"
    assert any(command.startswith("printf '") for command in long_child.commands)
    assert long_child.commands[3].startswith("printf '\\170\\170\\170")
    assert "\\0170" not in long_child.commands[3]
    assert "stty echo" in long_child.commands
    assert any(command.startswith("ksh /tmp/zoe-command-") for command in long_child.commands)


def test_silent_prompt_needs_no_echoed_newline():
    import re
    from hpux_tools.guest import SILENT_PROMPT

    assert re.search(SILENT_PROMPT, "# ") is not None

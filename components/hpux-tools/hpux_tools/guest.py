from __future__ import annotations

import os
import sys

from .cli import _paths, boot_command


PROMPT = r"\r?\n# $"
SILENT_PROMPT = r"# $"
STATUS = r"__ZOE_EXIT__([0-9]+)"


def _status_command(command):
    return f"{{ {command}; }}; __zoe_status=$?; printf '\\n__ZOE_EXIT__%s\\n' \"$__zoe_status\""


def _send_script(child, command, path):
    child.sendline("stty -echo")
    child.expect(PROMPT)
    data = command.encode()
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        encoded = "".join(f"\\{byte:03o}" for byte in chunk)
        operator = ">" if offset == 0 else ">>"
        child.sendline(f"printf '{encoded}' {operator} {path}")
        child.expect(SILENT_PROMPT)
    child.sendline("stty echo")
    child.expect(SILENT_PROMPT)


def run_guest(command, write=False, timeout=1800, environment=None):
    import pexpect

    paths = _paths(environment)
    qemu_arguments = boot_command([], write=write, environment=environment)
    qemu = qemu_arguments[0]
    arguments = qemu_arguments[1:]
    log_path = paths["image"].parent / "guest-session.log"
    child = pexpect.spawn(qemu, arguments, encoding="utf-8", timeout=timeout)
    log = log_path.open("w")
    child.logfile = log
    child.logfile_read = sys.stdout
    try:
        child.expect("(?i)login:")
        child.sendline("root")
        child.expect("(?i)Password:")
        child.sendline("p4ssw0rd")
        child.expect(PROMPT)
        status_command = _status_command(command)
        if len(status_command) > 180:
            path = f"/tmp/zoe-command-{os.getpid()}.sh"
            _send_script(child, command, path)
            status_command = f"ksh {path}; __zoe_status=$?; rm -f {path}; printf '\\n__ZOE_EXIT__%s\\n' \"$__zoe_status\""
        child.sendline(status_command)
        child.expect(STATUS)
        status = int(child.match.group(1))
        child.expect(PROMPT)
        if write:
            child.sendline("sync")
            child.expect(PROMPT)
        child.sendline("cd / && shutdown -h now")
        child.expect([pexpect.EOF, "System has halted"], timeout=120)
        child.close(force=True)
    finally:
        log.close()
        if child.isalive():
            child.close(force=True)
    return status

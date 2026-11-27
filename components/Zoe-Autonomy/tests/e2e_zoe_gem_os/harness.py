"""Shared harness, sandbox isolation, capability gates, and elegance/hygiene checks."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from functools import lru_cache
import importlib
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator
import unittest


def find_repo_root() -> Path:
    """Resolve monorepo root containing docs/CONSTITUTION.md and guiai-lab."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "CONSTITUTION.md").is_file() and (parent / "guiai-lab").is_dir():
            return parent
    raise RuntimeError(f"Unable to locate monorepo root from {here}")


REPO_ROOT: Path = find_repo_root()
E2E_DIR: Path = Path(__file__).resolve().parent
ZOE_GEM_OS_DIR: Path = REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "zoe_gem_os"
_REAL_HOME: Path = Path.home()


def ensure_sys_path() -> None:
    """Prepend guiai-lab and Zoe-Autonomy/src onto sys.path."""
    entries = (
        str(REPO_ROOT / "guiai-lab"),
        str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
    )
    for entry in reversed(entries):
        if entry not in sys.path:
            sys.path.insert(0, entry)


ensure_sys_path()


@dataclass
class SandboxPaths:
    """Isolated temporary directory paths so host ~/.zoe and /dev/shm stay untouched."""

    root: Path
    home_dir: Path
    state_dir: Path
    boot_json: Path
    uma_dir: Path
    uma_shm: Path
    out_dir: Path


def create_sandbox(temp_dir: str | Path) -> SandboxPaths:
    """Create isolated subdirectories under an existing TemporaryDirectory."""
    root = Path(temp_dir)
    paths = SandboxPaths(
        root=root,
        home_dir=root / "home",
        state_dir=root / "zoe_state",
        boot_json=root / "run" / "zoe-boot-state.json",
        uma_dir=root / "uma_bridge",
        uma_shm=root / "zoe_uma_bar.shm",
        out_dir=root / "out",
    )
    for d in (paths.home_dir, paths.state_dir, paths.boot_json.parent, paths.uma_dir, paths.out_dir):
        d.mkdir(parents=True, exist_ok=True)
    return paths


def isolated_env(home_dir: str | Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess env dict pointing HOME to an isolated directory."""
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["ZOE_ROOT"] = str(REPO_ROOT)
    env["PYTHONPATH"] = os.pathsep.join([
        str(REPO_ROOT / "guiai-lab"),
        str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
    ])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


@contextlib.contextmanager
def isolate_uma_shm(sb: SandboxPaths) -> Iterator[None]:
    """Redirect default /dev/shm/zoe-uma-bar.shm UmaBridge calls to sb.uma_shm."""
    zgo = importlib.import_module("guiai.gem.zoe_gem_os")
    zoe_uma = importlib.import_module("guiai.gem.zoe_gem_os.zoe_uma")
    orig_cls = zoe_uma.UmaBridge
    orig_pkg_cls = zgo.UmaBridge
    old_env = os.environ.get("ZOE_UMA_SHM")

    class _SandboxedUmaBridge(orig_cls):  # type: ignore[valid-type, misc]
        def __init__(self, bridge_dir: str | Path, shm_path: str | Path | None = None) -> None:
            target = sb.uma_shm if (shm_path is None or str(shm_path) == "/dev/shm/zoe-uma-bar.shm") else shm_path
            super().__init__(bridge_dir, shm_path=target)

    os.environ["ZOE_UMA_SHM"] = str(sb.uma_shm)
    zoe_uma.UmaBridge = _SandboxedUmaBridge
    zgo.UmaBridge = _SandboxedUmaBridge
    try:
        yield
    finally:
        zoe_uma.UmaBridge = orig_cls
        zgo.UmaBridge = orig_pkg_cls
        if old_env is None:
            os.environ.pop("ZOE_UMA_SHM", None)
        else:
            os.environ["ZOE_UMA_SHM"] = old_env


@contextlib.contextmanager
def long_tmpdir_env(tmp_path: Path) -> Iterator[None]:
    """Temporarily point TMPDIR and tempfile.tempdir to tmp_path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    old_env = os.environ.get("TMPDIR")
    old_cached = tempfile.tempdir
    os.environ["TMPDIR"] = str(tmp_path)
    tempfile.tempdir = None
    try:
        yield
    finally:
        tempfile.tempdir = old_cached
        if old_env is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = old_env


@contextlib.contextmanager
def qemu_path_shim(shim_dir: Path, argv_log: Path, hold_sec: float = 0.0) -> Iterator[Path]:
    """Prepend a sandboxed qemu-system-x86_64 shim on PATH recording exact argv."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_bin = shim_dir / "qemu-system-x86_64"
    script = (
        f"#!{sys.executable}\n"
        "import json, pathlib, signal, sys, time\n"
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
        f"log = pathlib.Path({str(argv_log)!r})\n"
        "with log.open('a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps(sys.argv) + '\\n')\n"
        f"if {float(hold_sec)} > 0:\n"
        f"    time.sleep({float(hold_sec)})\n"
    )
    shim_bin.write_text(script, encoding="utf-8")
    shim_bin.chmod(0o755)
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{old_path}" if old_path else str(shim_dir)
    try:
        yield argv_log
    finally:
        os.environ["PATH"] = old_path


def run_verifier_with_long_tmpdir_shim(root_dir: Path) -> list[list[str]]:
    """Invoke verify_zoe_gem_os_qemu under a >107-byte TMPDIR with a QEMU PATH shim."""
    from guiai.gem.zoe_gem_os import verify_zoe_gem_os_qemu

    long_tmp = root_dir / ("long_tmp_segment_" * 7)
    argv_log = root_dir / "qemu_verifier_argv.jsonl"
    dummy_iso = root_dir / "dummy.iso"
    dummy_iso.write_bytes(b"ISO-SHIM")
    work_dir = root_dir / "verifier_work"
    with long_tmpdir_env(long_tmp), qemu_path_shim(root_dir / "bin", argv_log):
        verify_zoe_gem_os_qemu(dummy_iso, work_dir)
    if not argv_log.is_file():
        return []
    return [json.loads(ln) for ln in argv_log.read_text(encoding="utf-8").splitlines() if ln.strip()]


def terminate_pid(pid: int | None, timeout_sec: float = 3.0) -> None:
    """Send SIGTERM then SIGKILL if needed and reap a child PID."""
    import signal
    import time

    if not pid or pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            done_pid, _ = os.waitpid(pid, os.WNOHANG)
            if done_pid == pid:
                return
        except ChildProcessError:
            return
        time.sleep(0.02)
    try:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except OSError:
        pass


def launch_with_qemu_shim(
    sb: SandboxPaths,
    iso_name: str = "zoe-gem-os.iso",
    **kwargs: Any,
) -> tuple[dict[str, Any], list[str]]:
    """Invoke launch_zoe_gem_os_kvm with a sandboxed QEMU shim and return (res, argv)."""
    import time
    from guiai.gem.zoe_gem_os import launch_zoe_gem_os_kvm

    iso = sb.out_dir / iso_name
    iso.write_bytes(b"ISO-SHIM")
    state_img = sb.out_dir / "shim_state.img"
    if not state_img.exists():
        state_img.write_bytes(b"\x00" * 4096)
    argv_log = sb.out_dir / f"launch_argv_{iso_name}.jsonl"
    argv_log.unlink(missing_ok=True)
    res: dict[str, Any] = {}
    with isolate_uma_shm(sb), qemu_path_shim(sb.out_dir / "shim_bin", argv_log, hold_sec=3.0):
        try:
            res = launch_zoe_gem_os_kvm(iso, state_img, uma_dir=sb.uma_dir, uma_shm=sb.uma_shm, **kwargs)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not (argv_log.is_file() and argv_log.stat().st_size > 0):
                time.sleep(0.02)
        finally:
            terminate_pid(res.get("pid"))
    lines = argv_log.read_text(encoding="utf-8").splitlines() if argv_log.is_file() else []
    argv = json.loads(lines[-1]) if lines else []
    return res, argv


def is_strict_mode() -> bool:
    """Return True when M4 strict gate (ZOE_E2E_STRICT=1) is enabled."""
    return os.environ.get("ZOE_E2E_STRICT") == "1"


def require_capability(test_case: unittest.TestCase, name: str, probe_fn: Callable[[], bool]) -> None:
    """Run probe_fn; fail in strict mode or skipTest if milestone feature is pending."""
    if probe_fn():
        return
    if is_strict_mode():
        test_case.fail(f"Missing M4 contract capability: {name}")
    test_case.skipTest(f"Pending milestone capability: {name}")


def build_fb_binary(out_dir: Path, strict_werror: bool = False) -> Path:
    """Compile zoe_gem_fb.c statically into out_dir."""
    if not shutil.which("gcc"):
        raise RuntimeError("gcc compiler not available")
    out_dir.mkdir(parents=True, exist_ok=True)
    src = ZOE_GEM_OS_DIR / "zoe_gem_fb.c"
    binary = out_dir / ("zoe_gem_fb_strict" if strict_werror else "zoe_gem_fb")
    cmd = ["gcc", "-O2"]
    if strict_werror:
        cmd.extend(["-Wall", "-Wextra", "-Werror"])
    cmd.extend(["-static", str(src), "-lm", "-o", str(binary)])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gcc exited {proc.returncode}")
    return binary


def has_gcc() -> bool:
    """Return True if gcc is installed."""
    return bool(shutil.which("gcc"))


def has_qemu_kvm() -> bool:
    """Return True if qemu-system-x86_64 and accessible /dev/kvm exist."""
    if not shutil.which("qemu-system-x86_64"):
        return False
    kvm = Path("/dev/kvm")
    return kvm.exists() and os.access(kvm, os.R_OK | os.W_OK)


def find_ovmf_firmware() -> Path | None:
    """Locate OVMF UEFI firmware path on host."""
    candidates = (
        Path("/usr/share/ovmf/OVMF.fd"),
        Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def find_cached_iso(flavor: str = "virt") -> Path | None:
    """Locate cached Zoe-GEM OS ISO under real host cache (read-only usage)."""
    name = "zoe-gem-os-lts.iso" if flavor == "lts" else "zoe-gem-os.iso"
    iso = _REAL_HOME / ".zoe" / "os-build" / name
    return iso if iso.is_file() else None


@lru_cache(maxsize=1)
def probe_m1_hw_observation() -> bool:
    """Probe whether M1 Hardware Observation Diagnostic is implemented."""
    from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

    with tempfile.TemporaryDirectory(prefix="zoe-probe-m1-") as td:
        sb = create_sandbox(td)
        rep = run_boot_sync(sb.state_dir, sb.boot_json)
        return "hw_profile" in rep and (sb.state_dir / "hw_observation.json").is_file()


@lru_cache(maxsize=1)
def probe_m1_shell_flag() -> bool:
    """Probe whether M1 --shell preserves boot_count without re-running boot sync."""
    from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

    with tempfile.TemporaryDirectory(prefix="zoe-probe-sh-") as td:
        sb = create_sandbox(td)
        run_boot_sync(sb.state_dir, sb.boot_json)
        env = isolated_env(sb.home_dir, {"ZOE_STATE_DIR": str(sb.state_dir), "ZOE_BOOT_JSON": str(sb.boot_json)})
        proc = subprocess.run(
            [sys.executable, str(ZOE_GEM_OS_DIR / "zoe_os_runtime.py"), "--shell"],
            input="quit\n",
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            return False
        data = __import__("json").loads(sb.boot_json.read_text(encoding="utf-8"))
        return data.get("boot_count") == 1 and "ZOE_OS_BOOT_OK" not in proc.stdout


@lru_cache(maxsize=1)
def probe_m1_uma_flock() -> bool:
    """Probe whether M1 fcntl.flock is wired into zoe_uma."""
    zoe_uma = importlib.import_module("guiai.gem.zoe_gem_os.zoe_uma")
    return hasattr(zoe_uma, "fcntl")


@lru_cache(maxsize=1)
def probe_m2_werror_compile() -> bool:
    """Probe whether M2 zoe_gem_fb.c compiles cleanly with -Wall -Wextra -Werror."""
    if not has_gcc():
        return False
    with tempfile.TemporaryDirectory(prefix="zoe-probe-cc-") as td:
        try:
            build_fb_binary(Path(td), strict_werror=True)
            return True
        except RuntimeError:
            return False


@lru_cache(maxsize=1)
def probe_m2_geometry_flags() -> bool:
    """Probe whether M2 --size, --portrait, and --amber flags work on zoe_gem_fb."""
    if not has_gcc():
        return False
    with tempfile.TemporaryDirectory(prefix="zoe-probe-fb-") as td:
        try:
            fb_bin = build_fb_binary(Path(td), strict_werror=False)
            ppm = Path(td) / "p.ppm"
            proc = subprocess.run(
                [str(fb_bin), "--size", "540x960", "--portrait", "--amber", "--dump-ppm", str(ppm)],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode != 0 or not ppm.is_file():
                return False
            header = ppm.read_bytes()[:32]
            return b"540 960" in header
        except Exception:
            return False


@lru_cache(maxsize=1)
def probe_m3_lume_slash_commands() -> bool:
    """Probe whether M3 registered /os and /uma in LUME_SLASH_COMMANDS."""
    from guiai.gem.lume_cli import LUME_SLASH_COMMANDS

    return "/os" in LUME_SLASH_COMMANDS and "/uma" in LUME_SLASH_COMMANDS


@lru_cache(maxsize=1)
def probe_m3_os_hw_command() -> bool:
    """Probe whether M3 added /os hw to LumeCli."""
    from guiai.gem.lume_cli import LumeCli
    from zoe_autonomy.chat import ZoeChat

    with tempfile.TemporaryDirectory(prefix="zoe-probe-hw-") as td:
        sb = create_sandbox(td)
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(sb.home_dir)
        try:
            cli = LumeCli(ZoeChat(REPO_ROOT), REPO_ROOT, color=False, brain_state=sb.state_dir)
            handled, out = cli.handle_slash("/os hw", color=False)
            text = "\n".join(out or [])
            return bool(handled and out and "Usage:" not in text)
        finally:
            if old_home is not None:
                os.environ["HOME"] = old_home


@lru_cache(maxsize=1)
def probe_m3_launch_wayland_sig() -> bool:
    """Probe whether M3 updated launch_zoe_gem_os_kvm with mode/geometry support."""
    from guiai.gem.zoe_gem_os import launch_zoe_gem_os_kvm

    params = inspect.signature(launch_zoe_gem_os_kvm).parameters
    return "mode" in params or "geometry" in params


@lru_cache(maxsize=1)
def probe_m3_tcp_qmp_verifier() -> bool:
    """Probe opaque-box whether verify_zoe_gem_os_qemu emits TCP QMP/monitor args (no UNIX sock)."""
    if not find_ovmf_firmware():
        return False
    with tempfile.TemporaryDirectory(prefix="zoe-probe-tcp-") as td:
        try:
            calls = run_verifier_with_long_tmpdir_shim(Path(td))
            if len(calls) < 2:
                return False
            no_unix = all(all("unix:" not in arg for arg in argv) for argv in calls)
            has_tcp = any(any("tcp:127.0.0.1:" in arg for arg in argv) for argv in calls)
            return no_unix and has_tcp
        except Exception:
            return False


def assert_constitutional_honesty(doc: dict[str, Any], require_flight: bool = False) -> None:
    """Verify constitutional honesty and zero-token invariants on runtime dicts."""
    assert doc.get("clinical_action_authorized") is False, f"clinical_action_authorized={doc.get('clinical_action_authorized')!r}"
    assert doc.get("cure_claim") is False, f"cure_claim={doc.get('cure_claim')!r}"
    assert doc.get("sentience_claimed") is False, f"sentience_claimed={doc.get('sentience_claimed')!r}"
    assert doc.get("tokens_used") == 0, f"tokens_used={doc.get('tokens_used')!r}"
    if require_flight or "flight_control_authorized" in doc:
        assert doc.get("flight_control_authorized") is False, f"flight_control_authorized={doc.get('flight_control_authorized')!r}"
    if "cloud_tokens_used" in doc:
        assert doc.get("cloud_tokens_used") == 0, f"cloud_tokens_used={doc.get('cloud_tokens_used')!r}"


def hygiene_forbidden_tokens() -> tuple[str, ...]:
    """Construct forbidden hygiene tokens dynamically so scanner never embeds literals."""
    slash = chr(47)
    user_tok = "cow" + "boy"
    return (
        f"{slash}home{slash}{user_tok}",
        "file:" + "//",
        "sk" + "-ant-",
        "micro" + "soft",
        "edge" + "-tts",
        "ssh" + "pie",
    )


def scan_text_for_hygiene(text: str, rel_label: str) -> list[str]:
    """Return list of hygiene leak descriptions found in text."""
    hits: list[str] = []
    lower = text.lower()
    for tok in hygiene_forbidden_tokens():
        if tok in lower:
            hits.append(f"{rel_label}: leaked token {tok!r}")
    return hits


def run_hygiene_scan() -> dict[str, Any]:
    """Scan E2E suite, zoe_gem_os package (including C), lume_cli.py, test_lume_cli.py, and key docs."""
    targets = (
        list(sorted(E2E_DIR.glob("*.py")))
        + list(sorted(ZOE_GEM_OS_DIR.glob("*.py")))
        + [
            ZOE_GEM_OS_DIR / "zoe_gem_fb.c",
            REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "lume_cli.py",
            REPO_ROOT / "components" / "Zoe-Autonomy" / "tests" / "test_lume_cli.py",
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs" / "PROOF-PACKET.md",
        ]
    )
    leaks: list[str] = []
    for path in targets:
        if path.is_file():
            rel = path.relative_to(REPO_ROOT).as_posix()
            leaks.extend(scan_text_for_hygiene(path.read_text(encoding="utf-8", errors="ignore"), rel))
    return {"scanned_files": len(targets), "leaks": leaks, "clean": len(leaks) == 0}


def _analyze_dir_modules(folder: Path) -> list[dict[str, Any]]:
    """Run analyze_python_source on all .py files inside folder."""
    from guiai.gem.code_elegance_analyzer import analyze_python_source

    rows: list[dict[str, Any]] = []
    for py in sorted(folder.glob("*.py")):
        rel = py.relative_to(REPO_ROOT).as_posix()
        rows.append(analyze_python_source(py.read_text(encoding="utf-8"), label=rel))
    return rows


def run_elegance_check() -> dict[str, Any]:
    """Run monorepo elegance audit plus per-file AST analysis on e2e_zoe_gem_os and zoe_gem_os."""
    from guiai.gem.code_elegance_analyzer import audit_zoe_monorepo_elegance

    monorepo = audit_zoe_monorepo_elegance(REPO_ROOT)
    e2e_rows = _analyze_dir_modules(E2E_DIR)
    gem_rows = _analyze_dir_modules(ZOE_GEM_OS_DIR)
    e2e_ok = all(r["grade"] in {"A", "B"} and r["max_cc"] <= 10 for r in e2e_rows)
    gem_ok = all(r["grade"] in {"A", "B"} for r in gem_rows)
    return {
        "monorepo_verified": bool(monorepo["all_verified"]),
        "monorepo_summary": monorepo["monorepo_summary"],
        "e2e_files": e2e_rows,
        "zoe_gem_os_files": gem_rows,
        "e2e_ok": e2e_ok,
        "gem_ok": gem_ok,
        "all_ok": bool(monorepo["all_verified"] and e2e_ok and gem_ok),
    }

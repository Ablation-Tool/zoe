"""Shared opaque-box fixtures, path isolation, protected-state checksums, and hygiene guards."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
import hashlib
import importlib
import inspect
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable, Dict, Iterator, List, Tuple, TypeVar

import pytest

T = TypeVar("T")
_HYGIENE_LOGGER = logging.getLogger("e2e_zoe_showcase.hygiene")


def _find_repo_root() -> Path:
    """Resolve Zoe monorepo root anchored on docs/CONSTITUTION.md and components/Zoe-Autonomy."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "CONSTITUTION.md").is_file() and (parent / "components" / "Zoe-Autonomy").is_dir():
            return parent
    raise RuntimeError(f"Unable to resolve Zoe monorepo root from {here}")


REPO_ROOT: Path = _find_repo_root()
PYTHON_BIN: str = os.environ.get("ZOE_PYTHON") or sys.executable
_SIBLING_ZOE = Path(PYTHON_BIN).parent / "zoe"
ZOE_BIN: str = str(_SIBLING_ZOE) if _SIBLING_ZOE.is_file() else (shutil.which("zoe") or "zoe")

_MONOREPO_PYTHONPATH_ENTRIES: Tuple[str, ...] = (
    str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
    str(REPO_ROOT / "guiai-lab"),
    str(REPO_ROOT / "components" / "ablation"),
    str(REPO_ROOT / "components" / "ablation" / "gem-lab"),
)

# Prepend monorepo sources so components/ablation is never shadowed by external checkouts.
for _entry in reversed(_MONOREPO_PYTHONPATH_ENTRIES):
    while _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

os.environ.setdefault("ZOE_ROOT", str(REPO_ROOT))


_USER_HOME: Path = Path.home()
SESSION_JSON_PATH: Path = _USER_HOME / ".zoe" / "chat" / "session.json"
SESSION_JSON_STEP0_SNAPSHOT: Tuple[int, str] = (
    413,
    "031f3fa10c1f227aaac34d2226a35f1a3539089cc9f572f812ec1848cfec74f2",
)
# Documented external interactive `agy` session (`8bd2e815`, PID 3226904) update at 2026-11-25T06:06:25Z.
SESSION_JSON_EXTERNAL_8BD2E815_SNAPSHOT: Tuple[int, str] = (
    414,
    "19795086395912094deac23d66ff847da4440ecdc239b7788e6f74432742e1b8",
)

# Exact baseline sizes and SHA-256 digests from PROJECT.md (Step 0 MUST NEVER CHANGE for the 4 fixed files).
PROTECTED_BASELINES: Dict[Path, Tuple[int, str]] = {
    SESSION_JSON_PATH: SESSION_JSON_STEP0_SNAPSHOT,
    _USER_HOME / ".zoe" / "uma-bridge" / "uma_state.json": (
        158,
        "ab0145b1e66ebea57e3c3de34eb0c2a8a070257421a3f8b74722bf328361cf02",
    ),
    _USER_HOME / ".zoe" / "os-build" / "zoe-gem-os.iso": (
        45_664_256,
        "3815342c8b4112b3c3702e0205c267dce2bf7c609441e42adc6e553752a0b0f0",
    ),
    _USER_HOME / ".zoe" / "os-build" / "zoe-gem-os-lts.iso": (
        60_248_064,
        "08404023cc09f37b4882c8558ea169862853ac879f9ad53ccfad248442744574",
    ),
    _USER_HOME / ".zoe" / "os-build" / "zoe-state.img": (
        67_108_864,
        "c1d0a252994c04319ee641646eb4cdb651be2caf7c3ed9df0807334598735d35",
    ),
}

PROTECTED_ACCEPTED_BASELINES: Dict[Path, Tuple[Tuple[int, str], ...]] = {
    SESSION_JSON_PATH: (
        SESSION_JSON_STEP0_SNAPSHOT,
        SESSION_JSON_EXTERNAL_8BD2E815_SNAPSHOT,
    ),
    **{
        path: (spec,)
        for path, spec in PROTECTED_BASELINES.items()
        if path != SESSION_JSON_PATH
    },
}

_SESSION_START_PROTECTED: Dict[Path, Tuple[int, str]] = {}


def sha256_file_streaming(path: Path, chunk_size: int = 65536) -> Tuple[int, str]:
    """Stream-hash ``path`` in 64 KiB chunks and return ``(size_bytes, hex_sha256)``."""
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            buf = fh.read(chunk_size)
            if not buf:
                break
            total += len(buf)
            h.update(buf)
    return total, h.hexdigest()


def _normalize_accepted_specs(
    expected: Tuple[int, str] | Sequence[Tuple[int, str]],
) -> Tuple[Tuple[int, str], ...]:
    if (
        isinstance(expected, tuple)
        and len(expected) == 2
        and isinstance(expected[0], int)
        and isinstance(expected[1], str)
    ):
        return (expected,)
    return tuple(expected)


def verify_protected_state_checksums(
    baselines: Mapping[Path, Tuple[int, str] | Sequence[Tuple[int, str]]] = PROTECTED_ACCEPTED_BASELINES,
    *,
    capture_session_start: bool = False,
) -> Dict[str, Tuple[int, str]]:
    """Assert all 5 protected ~/.zoe/* files match accepted baselines and zero intra-session mutation."""
    if capture_session_start:
        _SESSION_START_PROTECTED.clear()
    results: Dict[str, Tuple[int, str]] = {}
    for path, raw_expected in baselines.items():
        accepted = _normalize_accepted_specs(raw_expected)
        assert path.is_file(), f"Protected file missing: {path}"
        size, digest = sha256_file_streaming(path)
        if len(accepted) == 1:
            expected_size, expected_sha = accepted[0]
            assert size == expected_size, (
                f"Protected file size modified for {path}: got {size}, expected {expected_size}"
            )
            assert digest == expected_sha, (
                f"Protected file SHA-256 modified for {path}: got {digest}, expected {expected_sha}"
            )
        else:
            assert (size, digest) in accepted, (
                f"Protected file modified for {path}: got {(size, digest)}, expected one of {accepted}"
            )
        if path in _SESSION_START_PROTECTED:
            init_size, init_digest = _SESSION_START_PROTECTED[path]
            assert (size, digest) == (init_size, init_digest), (
                f"Protected file mutated during test session for {path}: "
                f"got ({size}, {digest}), session-start was ({init_size}, {init_digest})"
            )
        else:
            _SESSION_START_PROTECTED[path] = (size, digest)
        results[str(path)] = (size, digest)
    return results


def _read_proc_ppid_and_comm(pid: int) -> Tuple[int | None, str]:
    """Read ``(ppid, comm)`` from ``/proc/<pid>/stat``, handling process exit gracefully."""
    try:
        stat_text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ""
    lparen = stat_text.find("(")
    rparen = stat_text.rfind(")")
    if lparen == -1 or rparen == -1 or rparen <= lparen:
        return None, ""
    comm = stat_text[lparen + 1 : rparen]
    rest = stat_text[rparen + 2 :].split()
    if len(rest) < 2:
        return None, comm
    try:
        ppid = int(rest[1])
    except ValueError:
        return None, comm
    return ppid, comm


def _read_proc_argv(pid: int) -> List[str]:
    """Read ``/proc/<pid>/cmdline`` argv list, returning [] on error or kernel threads."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    if not raw:
        return []
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\x00") if part]


def _get_ppid_chain(pid: int, max_depth: int = 64) -> List[Tuple[int, str]]:
    """Return ``[(pid, comm), ...]`` walking ``/proc/<pid>/stat`` PPID chain up toward PID 1."""
    chain: List[Tuple[int, str]] = []
    seen: set[int] = set()
    cur: int | None = pid
    while cur is not None and cur > 0 and cur not in seen and len(chain) < max_depth:
        seen.add(cur)
        ppid, comm = _read_proc_ppid_and_comm(cur)
        if ppid is None and not comm:
            break
        chain.append((cur, comm))
        if cur == 1 or ppid is None or ppid <= 0:
            break
        cur = ppid
    return chain


def _is_agy_process(pid: int, comm: str) -> bool:
    if comm == "agy":
        return True
    argv = _read_proc_argv(pid)
    return bool(argv) and Path(argv[0]).name == "agy"


def _find_teamwork_root_pid() -> int | None:
    """Locate the nearest ``agy`` ancestor of our test runner, if running under an ``agy`` session."""
    for anc_pid, anc_comm in _get_ppid_chain(os.getpid())[1:]:
        if _is_agy_process(anc_pid, anc_comm):
            return anc_pid
    return None


_TEAMWORK_ROOT_PID: int | None = _find_teamwork_root_pid()


def _is_pytest_runner_argv(argv: Sequence[str]) -> bool:
    """Return True only when ``argv`` invokes ``pytest`` itself as the runner."""
    if not argv:
        return False
    prog = Path(argv[0]).name.lower()
    if prog in {"pytest", "py.test"}:
        return True
    if not prog.startswith("python"):
        return False
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in {"-W", "-X"}:
            i += 2
            continue
        if arg == "-m":
            return i + 1 < len(argv) and argv[i + 1].lower() in {"pytest", "py.test"}
        if arg == "-c":
            return False
        if arg.startswith("-"):
            i += 1
            continue
        return Path(arg).name.lower() in {"pytest", "py.test"}
    return False


def scan_live_zoe_services_or_vms() -> Tuple[Dict[int, str], Dict[int, str]]:
    """Scan ``/proc/*/cmdline`` and return ``(service_pids, qemu_pids)``.

    Detects:
    - ``qemu-system*`` VMs
    - ``llama-server``
    - ``zoe eliza serve`` (including ``python3 /.../zoe eliza serve ...``)
    - ``zoe_gem_desktop.py``
    """
    self_pid = os.getpid()
    parent_pid = os.getppid()
    services: Dict[int, str] = {}
    qemus: Dict[int, str] = {}
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in (self_pid, parent_pid):
            continue
        argv = _read_proc_argv(pid)
        if not argv:
            continue
        prog = Path(argv[0]).name.lower()
        joined_low = " ".join(argv).lower()
        # Ignore pytest runners themselves and outer shell wrappers (their child processes are scanned directly).
        if _is_pytest_runner_argv(argv):
            continue
        if prog in {"bash", "sh", "zsh", "dash"}:
            continue
        cmd_summary = f"pid={pid} cmd={' '.join(argv[:6])}"
        if prog.startswith("qemu-system"):
            qemus[pid] = cmd_summary
            continue
        is_llama = prog == "llama-server"
        is_eliza_srv = False
        if prog in {"zoe-eliza", "eliza"}:
            is_eliza_srv = True
        elif prog.startswith("zoe") and len(argv) >= 3 and argv[1] == "eliza" and argv[2] == "serve":
            is_eliza_srv = True
        elif prog.startswith("python"):
            has_zoe_entry = any(
                Path(arg).name.lower() in {"zoe", "zoe-eliza", "eliza"}
                for arg in argv[1:]
                if not arg.startswith("-")
            )
            has_eliza_serve = any(
                argv[i] == "eliza" and i + 1 < len(argv) and argv[i + 1] == "serve"
                for i in range(1, len(argv))
            )
            if (has_zoe_entry or "guiai.gem" in joined_low) and has_eliza_serve:
                is_eliza_srv = True
        is_gem_desktop = prog == "zoe_gem_desktop.py" or (
            prog.startswith("python")
            and (
                any(Path(arg).name.lower() == "zoe_gem_desktop.py" for arg in argv[1:] if not arg.startswith("-"))
                or any(argv[i] == "-m" and i + 1 < len(argv) and argv[i + 1] == "zoe_gem_desktop" for i in range(1, len(argv)))
            )
        )
        if is_llama or is_eliza_srv or is_gem_desktop:
            services[pid] = cmd_summary
    return services, qemus


_BASELINE_SERVICE_PIDS: Dict[int, str] = scan_live_zoe_services_or_vms()[0]


def _classify_service_pid(pid: int, desc: str) -> Tuple[str, Dict[str, Any]]:
    """Classify a live service PID as ``teamwork_owned``, ``spawned_leaked``, or ``external_agy``."""
    self_pid = os.getpid()
    chain = _get_ppid_chain(pid)
    anc_pids = {p for p, _ in chain}
    is_runner_descendant = self_pid in anc_pids
    is_teamwork_descendant = _TEAMWORK_ROOT_PID is not None and _TEAMWORK_ROOT_PID in anc_pids
    external_agy_pids = [
        anc_pid
        for anc_pid, anc_comm in chain
        if anc_pid != _TEAMWORK_ROOT_PID and _is_agy_process(anc_pid, anc_comm)
    ]
    in_baseline = pid in _BASELINE_SERVICE_PIDS
    info = {
        "pid": pid,
        "desc": desc,
        "ppid_chain": [f"{p}:{c or '?'}" for p, c in chain],
        "in_baseline": in_baseline,
        "external_agy_pids": external_agy_pids,
    }
    if is_runner_descendant or is_teamwork_descendant:
        return "teamwork_owned", info
    if not in_baseline and not external_agy_pids:
        return "spawned_leaked", info
    if external_agy_pids:
        return "external_agy", info
    if not in_baseline:
        return "spawned_leaked", info
    return "external_preexisting", info


def assert_no_live_zoe_services_or_vms(
    *,
    strict: bool | None = None,
    forbid_external: bool | None = None,
) -> Dict[str, Any]:
    """Assert zero QEMU/KVM VMs globally and zero spawned/teamwork-owned live Zoe services.

    - Always enforces zero ``qemu-system*`` VMs globally.
    - Inspects ``/proc/<pid>/stat`` PPID chains + pre/post PIDs to forbid any ``llama-server``,
      ``zoe eliza serve``, or ``zoe_gem_desktop.py`` spawned or leaked by our test runner or
      our teamwork ``agy`` process tree.
    - Pre-existing external sibling ``agy`` services are logged and returned in diagnostics
      without causing false failures (including under ``ZOE_E2E_STRICT=1``).
    - Set ``ZOE_E2E_FORBID_EXTERNAL_SERVICES=1`` (or ``forbid_external=True``) to require
      zero services globally on a single-user host.
    """
    if strict is None:
        strict = os.environ.get("ZOE_E2E_STRICT") == "1"
    if forbid_external is None:
        forbid_external = os.environ.get("ZOE_E2E_FORBID_EXTERNAL_SERVICES") == "1"

    services, qemus = scan_live_zoe_services_or_vms()
    assert not qemus, f"Forbidden live QEMU/KVM processes detected: {list(qemus.values())}"

    teamwork_owned: List[Dict[str, Any]] = []
    spawned_leaked: List[Dict[str, Any]] = []
    external_services: List[Dict[str, Any]] = []

    for pid, desc in sorted(services.items()):
        kind, info = _classify_service_pid(pid, desc)
        if kind == "teamwork_owned":
            teamwork_owned.append(info)
        elif kind == "spawned_leaked":
            spawned_leaked.append(info)
        else:
            external_services.append(info)

    if external_services:
        _HYGIENE_LOGGER.info(
            "Observed pre-existing external sibling agy services (not owned by teamwork root %s): %s",
            _TEAMWORK_ROOT_PID,
            [f"{item['desc']} (agy={item['external_agy_pids']})" for item in external_services],
        )

    assert not teamwork_owned, (
        f"Forbidden live services owned by test runner / teamwork tree (root={_TEAMWORK_ROOT_PID}): "
        f"{[item['desc'] for item in teamwork_owned]}"
    )
    assert not spawned_leaked, (
        f"Leaked live services spawned during tests: {[item['desc'] for item in spawned_leaked]}"
    )
    if forbid_external:
        assert not external_services, (
            f"Forbidden external live services detected under ZOE_E2E_FORBID_EXTERNAL_SERVICES=1: "
            f"{[item['desc'] for item in external_services]}"
        )

    return {
        "strict": strict,
        "forbid_external": forbid_external,
        "teamwork_root_pid": _TEAMWORK_ROOT_PID,
        "qemu_vms": qemus,
        "teamwork_services": teamwork_owned,
        "spawned_services": spawned_leaked,
        "external_services": external_services,
    }


@pytest.fixture(scope="session", autouse=True)
def guard_protected_state_and_hygiene() -> Iterator[None]:
    """Session-scoped autouse guard ensuring protected files & zero-service/VM invariants pre & post suite."""
    verify_protected_state_checksums(capture_session_start=True)
    assert_no_live_zoe_services_or_vms()
    try:
        yield
    finally:
        assert_no_live_zoe_services_or_vms()
        verify_protected_state_checksums()


def monorepo_env(extra: Mapping[str, str] | None = None) -> Dict[str, str]:
    """Return an os.environ copy with monorepo src/lib directories prepended to PYTHONPATH."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    existing_parts = [p for p in existing.split(os.pathsep) if p and p not in _MONOREPO_PYTHONPATH_ENTRIES]
    env["PYTHONPATH"] = os.pathsep.join([*_MONOREPO_PYTHONPATH_ENTRIES, *existing_parts])
    env["ZOE_ROOT"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class IsolatedZoeEnv:
    """Isolated per-test filesystem and environment bundle inside pytest tmp_path."""

    root: Path
    home_dir: Path
    chat_dir: Path
    uma_dir: Path
    uma_shm: Path
    eliza_dir: Path
    semantic_dir: Path
    os_build_dir: Path
    artline_dir: Path
    env: Dict[str, str]


@pytest.fixture()
def isolated_zoe_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IsolatedZoeEnv:
    """Isolate HOME, ZOE_*, ABLATION_ROOT, and import-time DEFAULT_* globals to tmp_path."""
    home_dir = tmp_path / "home"
    chat_dir = tmp_path / "chat"
    uma_dir = tmp_path / "uma-bridge"
    uma_shm = tmp_path / "uma.shm"
    eliza_dir = tmp_path / "eliza"
    semantic_dir = tmp_path / "semantic_state"
    os_build_dir = tmp_path / "os-build"
    artline_dir = tmp_path / "artline"
    for d in (home_dir, chat_dir, uma_dir, eliza_dir, semantic_dir, os_build_dir, artline_dir):
        d.mkdir(parents=True, exist_ok=True)

    overrides = {
        "HOME": str(home_dir),
        "ZOE_ROOT": str(REPO_ROOT),
        "ZOE_CHAT_STATE": str(chat_dir),
        "ZOE_UMA_SHM": str(uma_shm),
        "ZOE_UMA_DIR": str(uma_dir),
        "ZOE_ELIZA_STATE_DIR": str(eliza_dir),
        "ABLATION_ROOT": str(REPO_ROOT / "components" / "ablation"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for k, v in overrides.items():
        monkeypatch.setenv(k, v)

    existing = os.environ.get("PYTHONPATH", "")
    existing_parts = [p for p in existing.split(os.pathsep) if p and p not in _MONOREPO_PYTHONPATH_ENTRIES]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([*_MONOREPO_PYTHONPATH_ENTRIES, *existing_parts]))

    # Patch import-time Path.home() defaults so in-process tests never touch ~/.zoe/*
    chat_mod = importlib.import_module("zoe_autonomy.chat")
    monkeypatch.setattr(chat_mod, "DEFAULT_STATE", chat_dir, raising=False)
    dorothy_lib_mod = importlib.import_module("zoe_autonomy.dorothy_local_library")
    monkeypatch.setattr(dorothy_lib_mod, "DEFAULT_DB_PATH", eliza_dir / "dorothy_local_library.sqlite", raising=False)
    zoe_eliza_mod = importlib.import_module("zoe_autonomy.zoe_eliza")
    monkeypatch.setattr(zoe_eliza_mod, "DEFAULT_ELIZA_STATE", eliza_dir, raising=False)

    return IsolatedZoeEnv(
        root=tmp_path,
        home_dir=home_dir,
        chat_dir=chat_dir,
        uma_dir=uma_dir,
        uma_shm=uma_shm,
        eliza_dir=eliza_dir,
        semantic_dir=semantic_dir,
        os_build_dir=os_build_dir,
        artline_dir=artline_dir,
        env=monorepo_env(overrides),
    )


def assert_constitutional_invariants(payload: Any, *, require_offline: bool = False) -> None:
    """Recursively validate CONSTITUTION.md invariants on mappings, sequences, objects, or dataclasses."""
    false_flags = (
        "sentience_claimed",
        "l5_agi_qualified",
        "zoe_clone_claimed",
        "clinical_action_authorized",
        "cure_claim",
        "flight_control_authorized",
        "auto_flash_allowed",
    )
    seen: set[int] = set()
    stack: List[Any] = [payload]

    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (str, bytes, int, float, bool, Path)):
            continue
        obj_id = id(node)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        if is_dataclass(node) and not isinstance(node, type):
            for f in fields(node):
                val = getattr(node, f.name)
                if f.name in false_flags:
                    assert val is False, f"Constitutional violation: {f.name}={val!r} (expected False)"
                elif f.name == "external_actions":
                    assert val == 0, f"Constitutional violation: external_actions={val!r} (expected 0)"
                elif require_offline and f.name in {"cloud_tokens_used", "tokens_used"}:
                    assert val == 0, f"Offline invariant violation: {f.name}={val!r} (expected 0)"
                stack.append(val)
            continue

        if isinstance(node, Mapping):
            for flag in false_flags:
                if flag in node:
                    assert node[flag] is False, f"Constitutional violation: {flag}={node[flag]!r} (expected False)"
            if "external_actions" in node:
                assert node["external_actions"] == 0, (
                    f"Constitutional violation: external_actions={node['external_actions']!r} (expected 0)"
                )
            if require_offline:
                for tok_key in ("cloud_tokens_used", "tokens_used"):
                    if tok_key in node:
                        assert node[tok_key] == 0, f"Offline invariant violation: {tok_key}={node[tok_key]!r} (expected 0)"
            stack.extend(node.values())
        elif isinstance(node, (list, tuple, set, frozenset, deque)):
            stack.extend(node)
        else:
            attr_items: Dict[str, Any] = {}
            if hasattr(node, "__dict__"):
                attr_items.update(vars(node))
            for cls in type(node).__mro__:
                slots = cls.__dict__.get("__slots__", ())
                if isinstance(slots, str):
                    slots = (slots,)
                for slot in slots:
                    if slot in ("__dict__", "__weakref__") or slot in attr_items:
                        continue
                    if hasattr(node, slot):
                        attr_items[slot] = getattr(node, slot)
            if attr_items:
                for flag in false_flags:
                    if flag in attr_items:
                        assert attr_items[flag] is False, (
                            f"Constitutional violation: {flag}={attr_items[flag]!r} (expected False)"
                        )
                if "external_actions" in attr_items:
                    assert attr_items["external_actions"] == 0, (
                        f"Constitutional violation: external_actions={attr_items['external_actions']!r} (expected 0)"
                    )
                if require_offline:
                    for tok_key in ("cloud_tokens_used", "tokens_used"):
                        if tok_key in attr_items:
                            assert attr_items[tok_key] == 0, (
                                f"Offline invariant violation: {tok_key}={attr_items[tok_key]!r} (expected 0)"
                            )
                stack.extend(attr_items.values())


def call_with_supported_kwargs(fn: Callable[..., T], *args: Any, **candidates: Any) -> T:
    """Invoke a callable passing only keyword arguments accepted by its signature."""
    sig = inspect.signature(fn)
    params = sig.parameters
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_var_kw:
        return fn(*args, **candidates)
    filtered = {
        k: v
        for k, v in candidates.items()
        if k in params and params[k].kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return fn(*args, **filtered)


def make_synthetic_sysroot(
    base_dir: Path,
    *,
    ram_kb: int = 2_097_152,
    arch: str = "x86_64",
    hypervisor: bool = True,
    ivshmem: bool = True,
    fb: bool = True,
    input_ev: bool = True,
    nic: str = "eth0",
    state_disk: bool = True,
    cmdline: str = "BOOT_IMAGE=/boot/vmlinuz console=ttyS0,115200",
) -> Tuple[Path, Path, Path]:
    """Create synthetic /proc, /sys, /dev trees inside ``base_dir`` for zero-KVM zoe_os_runtime tests."""
    proc_root = base_dir / "proc"
    sys_root = base_dir / "sys"
    dev_root = base_dir / "dev"
    for d in (proc_root, sys_root, dev_root):
        d.mkdir(parents=True, exist_ok=True)

    flags = "fpu vme de pse tsc msr pae mce cx8 apic" + (" hypervisor" if hypervisor else "")
    if arch.startswith("arm") or arch == "aarch64":
        cpuinfo = "processor\t: 0\nmodel name\t: Cortex-A76\nFeatures\t: fp asimd\n"
    else:
        cpuinfo = (
            f"processor\t: 0\nmodel name\t: Zoe Synthetic x86_64 CPU\nflags\t\t: {flags}\n\n"
            f"processor\t: 1\nmodel name\t: Zoe Synthetic x86_64 CPU\nflags\t\t: {flags}\n"
        )
    (proc_root / "cpuinfo").write_text(cpuinfo, encoding="utf-8")
    (proc_root / "meminfo").write_text(f"MemTotal:       {ram_kb} kB\nMemFree:        {ram_kb // 2} kB\n", encoding="utf-8")
    (proc_root / "cmdline").write_text(cmdline, encoding="utf-8")
    (proc_root / "version").write_text("Linux version 6.12.0-zoe-synthetic (gcc 13.2.0)\n", encoding="utf-8")

    # DMI
    dmi_dir = sys_root / "class" / "dmi" / "id"
    dmi_dir.mkdir(parents=True, exist_ok=True)
    (dmi_dir / "sys_vendor").write_text("QEMU" if hypervisor else "Zoe Synthetic Lab", encoding="utf-8")
    (dmi_dir / "product_name").write_text("Standard PC (Q35 + ICH9, 2009)" if hypervisor else "Workstation", encoding="utf-8")

    # PCI ivshmem 0x1af4:0x1110
    pci_dir = sys_root / "bus" / "pci" / "devices"
    pci_dir.mkdir(parents=True, exist_ok=True)
    if ivshmem:
        dev_pci = pci_dir / "0000:00:04.0"
        dev_pci.mkdir(parents=True, exist_ok=True)
        (dev_pci / "vendor").write_text("0x1af4\n", encoding="utf-8")
        (dev_pci / "device").write_text("0x1110\n", encoding="utf-8")
        (dev_pci / "resource2").write_bytes(b"\x00" * 4096)

    # Net
    if nic:
        net_dir = sys_root / "class" / "net" / nic
        net_dir.mkdir(parents=True, exist_ok=True)
        (net_dir / "operstate").write_text("up\n", encoding="utf-8")
        (net_dir / "address").write_text("52:54:00:12:34:56\n", encoding="utf-8")

    # Block
    if state_disk:
        blk_dir = sys_root / "class" / "block" / "vda"
        blk_dir.mkdir(parents=True, exist_ok=True)
        (blk_dir / "size").write_text("131072\n", encoding="utf-8")

    # Display /dev/fb0
    if fb:
        fb_sys = sys_root / "class" / "graphics" / "fb0"
        fb_sys.mkdir(parents=True, exist_ok=True)
        (fb_sys / "virtual_size").write_text("920,960\n", encoding="utf-8")
        (dev_root / "fb0").write_bytes(b"")

    # Input (2 evdev devices for keyboard + pointer so input_devices gate passes)
    if input_ev:
        ev_dev = dev_root / "input"
        ev_dev.mkdir(parents=True, exist_ok=True)
        for idx, dev_name, cap_key, cap_abs in (
            (0, "AT Translated Set 2 keyboard", "2", ""),
            (1, "QEMU USB Tablet", "", "3"),
        ):
            inp_sys = sys_root / "class" / "input" / f"event{idx}"
            caps = inp_sys / "device" / "capabilities"
            caps.mkdir(parents=True, exist_ok=True)
            (inp_sys / "device" / "name").write_text(f"{dev_name}\n", encoding="utf-8")
            if cap_key:
                (caps / "key").write_text(f"{cap_key}\n", encoding="utf-8")
            if cap_abs:
                (caps / "abs").write_text(f"{cap_abs}\n", encoding="utf-8")
            (ev_dev / f"event{idx}").write_bytes(b"")

    return proc_root, sys_root, dev_root


def load_zoe_stem_mcp() -> Any:
    """Load scripts/zoe_stem_mcp.py cleanly regardless of package layout."""
    import importlib.util

    mcp_path = REPO_ROOT / "scripts" / "zoe_stem_mcp.py"
    spec = importlib.util.spec_from_file_location("zoe_stem_mcp", mcp_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the Zoe monorepo root path."""
    return REPO_ROOT

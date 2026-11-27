"""Shared opaque-box fixtures, parallel-safe lazy imports, fake-HOME isolation, and offline/constitutional guards."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import fields, is_dataclass
import importlib
import inspect
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import struct
import subprocess
import sys
from typing import Any, Callable, Sequence, TypeVar
import urllib.request
from urllib.parse import urlparse

import pytest

T = TypeVar("T")
_MISSING = object()


def _find_repo_root() -> Path:
    """Resolve monorepo root anchored on docs/CONSTITUTION.md and guiai-lab."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "CONSTITUTION.md").is_file() and (parent / "guiai-lab").is_dir():
            return parent
    raise RuntimeError(f"Unable to resolve Zoe monorepo root from {here}")


REPO_ROOT: Path = _find_repo_root()
REAL_HOME: Path = Path(os.path.expanduser("~")).resolve()
PYTHON_BIN: str = os.environ.get("ZOE_PYTHON") or sys.executable
_SIBLING_ZOE = Path(PYTHON_BIN).parent / "zoe"
ZOE_CLI_BIN: str = str(_SIBLING_ZOE) if _SIBLING_ZOE.is_file() else (shutil.which("zoe") or "zoe")
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})
CANONICAL_SISTER_NAMES: tuple[str, ...] = (
    "Zoe", "Gemma", "Tosi", "Mono", "Tetra", "Eliza", "Sage", "Flora", "Lumen",
)
CANONICAL_SISTER_SIGNETS: tuple[str, ...] = (
    "ruby", "gem3", "atari", "sm124", "tetris", "dos", "hat", "sprout", "prism",
)
EDDBMS_DOMAIN_MODULES: tuple[str, ...] = (
    "MATERIAL_DESIGN",
    "HUMAN_MODEL",
    "DESIGN_PARAMETERS",
    "PRODUCT_DESIGN_AND_PLANNING",
    "PROJECT_MANAGEMENT",
    "POSTPRODUCTION_MANAGEMENT",
)
ALLOWED_EPISTEMIC_LANES: frozenset[str] = frozenset({
    "measurement",
    "evidence",
    "belief_update",
    "advisory_proposal",
})
ATTRIBUTION_EXPECTED: str = "Nicholas Michael Kloster, March 6, 2026"

_MONOREPO_PYTHONPATH_ENTRIES: tuple[str, ...] = (
    str(REPO_ROOT / "guiai-lab"),
    str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
    str(REPO_ROOT / "components" / "ablation"),
)

# Prepend monorepo sources so components/ablation is never shadowed by external checkouts.
for _entry in reversed(_MONOREPO_PYTHONPATH_ENTRIES):
    while _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

os.environ.setdefault("ZOE_ROOT", str(REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """Register tier1..tier5 markers so zero PytestUnknownMarkWarning is emitted."""
    config.addinivalue_line("markers", "tier1: Tier 1 isolated feature happy-path E2E tests")
    config.addinivalue_line("markers", "tier2: Tier 2 boundary, corner, and invalid-input E2E tests")
    config.addinivalue_line("markers", "tier3: Tier 3 pairwise cross-feature E2E tests")
    config.addinivalue_line("markers", "tier4: Tier 4 realistic personal workspace workflow E2E tests")
    config.addinivalue_line("markers", "tier5: Tier 5 adversarial verification and hardening tests")


def is_strict_mode() -> bool:
    """Return True when strict Final Milestone mode (ZOE_E2E_STRICT=1) is active."""
    return os.environ.get("ZOE_E2E_STRICT") == "1"


def monorepo_env(
    extra: Mapping[str, str] | None = None,
    *,
    home_dir: Path | None = None,
) -> dict[str, str]:
    """Return an env mapping with monorepo PYTHONPATH entries prepended."""
    env = os.environ.copy()
    existing = [
        p for p in env.get("PYTHONPATH", "").split(os.pathsep)
        if p and p not in _MONOREPO_PYTHONPATH_ENTRIES
    ]
    env["PYTHONPATH"] = os.pathsep.join([*_MONOREPO_PYTHONPATH_ENTRIES, *existing])
    env["ZOE_ROOT"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if home_dir is not None:
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)
        env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
        env["XDG_CACHE_HOME"] = str(home_dir / ".cache")
        env["XDG_DATA_HOME"] = str(home_dir / ".local" / "share")
        env["ZOE_STATE_DIR"] = str(home_dir / ".zoe")
        env["ABLATION_CACHE_DIR"] = str(home_dir / ".ablation" / "cache")
    if extra:
        env.update(extra)
    return env


def import_contract_module(module_path: str, symbol: str | None = None) -> Any:
    """Lazy-import a contract module/symbol at test execution time (never at collection time)."""
    try:
        mod = importlib.import_module(module_path)
    except (ModuleNotFoundError, ImportError) as exc:
        msg = f"Contract deliverable {module_path!r} unavailable ({exc})"
        if is_strict_mode():
            pytest.fail(f"Strict mode failure — {msg}")
        pytest.skip(f"Pending parallel deliverable: {msg}")
    if symbol is None:
        return mod
    if not hasattr(mod, symbol):
        msg = f"Contract symbol {symbol!r} missing on {module_path!r}"
        if is_strict_mode():
            pytest.fail(f"Strict mode failure — {msg}")
        pytest.skip(f"Pending parallel deliverable: {msg}")
    return getattr(mod, symbol)


def call_with_supported_kwargs(fn: Callable[..., T], *args: Any, **candidates: Any) -> T:
    """Invoke callable passing positional args within arity plus non-colliding supported kwargs."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_var_pos = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    pos_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    effective_args = args if has_var_pos else args[:len(pos_params)]
    bound_pos_names = {p.name for p in pos_params[:len(effective_args)]}
    accepted_kw_names = {
        p.name for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    filtered: dict[str, Any] = {}
    for k, v in candidates.items():
        if k in bound_pos_names:
            continue
        if has_var_kw or k in accepted_kw_names:
            filtered[k] = v
    return fn(*effective_args, **filtered)


def export_workbench_gem(wb: Any, target_path: Path) -> bytes:
    """Export workbench .GEM metafile supporting (path), (dest, /), (*, path/destination), or zero-arg."""
    sig = inspect.signature(wb.export_gem_metafile)
    params = list(sig.parameters.values())
    pos_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if pos_params or any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        exported = wb.export_gem_metafile(target_path)
    else:
        kw_names = {p.name for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY}
        kw: dict[str, Any] = {}
        for candidate in ("path", "destination", "output_path", "file_path"):
            if candidate in kw_names:
                kw[candidate] = target_path
                break
        exported = wb.export_gem_metafile(**kw)
    return exported if isinstance(exported, bytes) else target_path.read_bytes()


def pick(obj: Any, *keys: str, default: Any = _MISSING) -> Any:
    """Resolve the first present key/attribute on a mapping, dataclass, or object."""
    for key in keys:
        if isinstance(obj, Mapping) and key in obj:
            return obj[key]
        if hasattr(obj, key):
            return getattr(obj, key)
    if default is not _MISSING:
        return default
    raise KeyError(f"None of {keys!r} found on {type(obj).__name__}: {obj!r}")


_pick = pick


def build_default_hex_mesh(hex_mod: Any) -> Any:
    """Instantiate the default 9-sister hex mesh via classmethod or module-level factory."""
    cls_factory = getattr(getattr(hex_mod, "HexCollaborationMesh", None), "build_default_zoe_mesh", None)
    if callable(cls_factory):
        return cls_factory()
    mod_factory = getattr(hex_mod, "build_default_zoe_mesh", None)
    if callable(mod_factory):
        return mod_factory()
    raise AttributeError("zoe_hex_mesh exposes neither HexCollaborationMesh.build_default_zoe_mesh nor build_default_zoe_mesh")


def get_mesh_cells(mesh: Any) -> dict[str, Any]:
    """Return {cell_id: HexCell} whether mesh.cells is a method, dict, or sequence."""
    raw = mesh.cells() if callable(getattr(mesh, "cells", None)) else pick(mesh, "cells")
    if isinstance(raw, Mapping):
        return dict(raw)
    return {c.cell_id: c for c in raw}


def aes_enqueue_message(app: Any, pkt: bytes, *, extra_bytes: bytes = b"") -> None:
    """Enqueue a 16-byte AES message packet across appl_write or legacy message queue methods."""
    appl_write = getattr(app, "appl_write", None)
    if callable(appl_write):
        appl_write(app.ap_id, len(pkt) + len(extra_bytes), pkt, extra_bytes=extra_bytes)
        return
    legacy = getattr(app, "enqueue_message", None) or getattr(app, "push_message", None)
    if callable(legacy):
        legacy(pkt)
        return
    post_fn = getattr(app, "post_message", None)
    if callable(post_fn):
        words = struct.unpack("<8h", pkt)
        post_fn(*words)
        return
    raise AttributeError(f"AES app {type(app).__name__} exposes no supported message enqueue method")


def aes_wind_create(mgr: Any, kind: int, x: int, y: int, w: int, h: int) -> int:
    """Create an AES window whether wind_create accepts (kind, rect) or (kind, x, y, w, h)."""
    sig = inspect.signature(mgr.wind_create)
    params = list(sig.parameters.values())
    pos_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if any(p.name == "rect" for p in params) or len(pos_params) <= 2:
        return int(mgr.wind_create(kind, (x, y, w, h)))
    return int(mgr.wind_create(kind, x, y, w, h))


def aes_wind_open(mgr: Any, wid: int, x: int, y: int, w: int, h: int) -> Any:
    """Open an AES window whether wind_open accepts (handle, rect) or (handle, x=..., ...)."""
    sig = inspect.signature(mgr.wind_open)
    params = list(sig.parameters.values())
    pos_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if any(p.name == "rect" for p in params) or len(pos_params) == 2:
        return mgr.wind_open(wid, (x, y, w, h))
    return call_with_supported_kwargs(mgr.wind_open, wid, x=x, y=y, w=w, h=h)


def aes_objc_change(
    ops: Any,
    tree: list[Any],
    obj_idx: int,
    new_state: int,
    clip_rect: tuple[int, int, int, int],
) -> Any:
    """Update object state across (tree, idx, new_state, *, redraw, clip_rect) or 6-arg GEM C signature."""
    sig = inspect.signature(ops.objc_change)
    if "new_state" in sig.parameters:
        return ops.objc_change(tree, obj_idx, new_state, redraw=True, clip_rect=clip_rect)
    return ops.objc_change(tree, obj_idx, 0, clip_rect, new_state, 1)


def _stat_snapshot(path: Path) -> tuple[bool, int | None, int | None]:
    if not path.exists():
        return (False, None, None)
    st = path.stat()
    entry_count = len(list(path.iterdir())) if path.is_dir() else None
    return (True, st.st_mtime_ns, entry_count)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolate HOME/XDG/Ablation/Zoe directories and verify real user dirs are untouched."""
    guarded_paths = (
        REAL_HOME / ".ablation",
        REAL_HOME / ".ablation" / "findings.db",
        REAL_HOME / ".zoe",
        REAL_HOME / ".gemini" / "antigravity-cli" / "settings.json",
    )
    before = {p: _stat_snapshot(p) for p in guarded_paths}

    fake_home = tmp_path / "fake_home"
    (fake_home / ".config").mkdir(parents=True, exist_ok=True)
    (fake_home / ".cache").mkdir(parents=True, exist_ok=True)
    (fake_home / ".local" / "share").mkdir(parents=True, exist_ok=True)
    (fake_home / ".zoe").mkdir(parents=True, exist_ok=True)
    (fake_home / ".ablation" / "cache").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(fake_home / ".cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_home / ".local" / "share"))
    monkeypatch.setenv("ZOE_STATE_DIR", str(fake_home / ".zoe"))
    monkeypatch.setenv("ABLATION_CACHE_DIR", str(fake_home / ".ablation" / "cache"))

    yield fake_home

    for p in guarded_paths:
        assert _stat_snapshot(p) == before[p], f"Real user path mutated during test: {p}"


_FORBIDDEN_EXECUTABLES = frozenset({"adb", "fastboot", "claude", "curl", "wget", "ssh"})
_SHELL_NAMES = frozenset({"sh", "bash", "dash", "zsh"})
_GIT_VALUE_FLAGS = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--exec-path", "--super-prefix", "--config-env", "--list-cmds",
})
_SHELL_SPLIT_OPS = frozenset({";", "&", "&&", "|", "||", "\n"})
_SHELL_FORBIDDEN_RE = re.compile(
    r"(?:^|[;&|\s])(?:(?:[^\s;&|]*/)?(?:adb|fastboot|claude|curl|wget|ssh)|(?:[^\s;&|]*/)?git(?:\s+\S+)*\s+push)(?:\s|$|[;&|])",
    re.IGNORECASE,
)


def _tokenize_command(args: Any) -> list[str]:
    if isinstance(args, (list, tuple)):
        return [str(a) for a in args]
    if isinstance(args, (str, bytes)):
        raw = args.decode("utf-8", "replace") if isinstance(args, bytes) else args
        try:
            return shlex.split(raw)
        except ValueError:
            return raw.split()
    return [str(args)]


def _split_shell_segments(raw: str) -> list[list[str]]:
    try:
        lex = shlex.shlex(raw, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        tokens = raw.split()
    segments: list[list[str]] = []
    cur: list[str] = []
    for tok in tokens:
        if tok in _SHELL_SPLIT_OPS:
            if cur:
                segments.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        segments.append(cur)
    return segments


def _is_forbidden_segment(tokens: Sequence[str]) -> bool:
    if not tokens:
        return False
    exe_name = Path(tokens[0]).name.lower()
    if exe_name in _FORBIDDEN_EXECUTABLES:
        return True
    if exe_name == "git":
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok == "--":
                i += 1
                if i < len(tokens) and tokens[i].lower() == "push":
                    return True
                break
            if tok in _GIT_VALUE_FLAGS:
                i += 2
                continue
            if tok.startswith("-"):
                i += 1
                continue
            if tok.lower() == "push":
                return True
            break
    if exe_name in _SHELL_NAMES:
        for idx, tok in enumerate(tokens[1:], start=1):
            if tok in ("-c", "-lc", "-ce", "-lce") and idx + 1 < len(tokens):
                inner = tokens[idx + 1]
                if _SHELL_FORBIDDEN_RE.search(inner) or any(
                    _is_forbidden_segment(seg) for seg in _split_shell_segments(inner)
                ):
                    return True
    return False


def _is_forbidden_command(args: Any, *, shell: bool = False) -> bool:
    if shell and isinstance(args, (str, bytes)):
        raw = args.decode("utf-8", "replace") if isinstance(args, bytes) else args
        if _SHELL_FORBIDDEN_RE.search(raw):
            return True
        return any(_is_forbidden_segment(seg) for seg in _split_shell_segments(raw))
    tokens = _tokenize_command(args)
    if _is_forbidden_segment(tokens):
        return True
    if isinstance(args, (str, bytes)):
        raw = args.decode("utf-8", "replace") if isinstance(args, bytes) else args
        return any(_is_forbidden_segment(seg) for seg in _split_shell_segments(raw))
    return False


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Block non-loopback network connections and unsafe external subprocesses."""
    counters: dict[str, int] = {
        "socket_loopback_calls": 0,
        "non_loopback_blocked": 0,
        "subprocess_calls": 0,
        "forbidden_commands_blocked": 0,
    }
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_create_conn = socket.create_connection
    orig_urlopen = urllib.request.urlopen
    orig_popen = subprocess.Popen

    def _check_host(host: Any) -> None:
        if isinstance(host, (bytes, bytearray)):
            host = host.decode("ascii", "ignore")
        cleaned = str(host).strip("[]")
        if cleaned not in LOOPBACK_HOSTS:
            counters["non_loopback_blocked"] += 1
            raise RuntimeError(f"Offline guard blocked non-loopback host: {host!r}")

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and address:
            _check_host(address[0])
            counters["socket_loopback_calls"] += 1
        return orig_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> int:
        if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and address:
            _check_host(address[0])
            counters["socket_loopback_calls"] += 1
        return orig_connect_ex(self, address)

    def guarded_create_connection(address: tuple[Any, int], *args: Any, **kwargs: Any) -> Any:
        _check_host(address[0])
        counters["socket_loopback_calls"] += 1
        return orig_create_conn(address, *args, **kwargs)

    def guarded_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
        raw = getattr(url, "full_url", str(url))
        parsed = urlparse(raw)
        if parsed.scheme in ("http", "https", "ws", "wss"):
            _check_host(parsed.hostname or "")
        return orig_urlopen(url, *args, **kwargs)

    def guarded_popen(args: Any, *pargs: Any, **kwargs: Any) -> Any:
        if _is_forbidden_command(args, shell=bool(kwargs.get("shell", False))):
            counters["forbidden_commands_blocked"] += 1
            raise RuntimeError(f"Operational guard blocked forbidden command: {args!r}")
        counters["subprocess_calls"] += 1
        return orig_popen(args, *pargs, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(urllib.request, "urlopen", guarded_urlopen)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)
    return counters


def assert_constitutional_metadata(
    payload: Any,
    *,
    require_advisory: bool = True,
    require_read_only: bool = False,
    require_keys: bool = True,
) -> None:
    """Validate constitutional invariants recursively across dicts, dataclasses, or objects."""
    false_flags = (
        "sentience_claimed",
        "l5_agi_qualified",
        "zoe_clone_claimed",
        "clinical_action_authorized",
        "flight_control_authorized",
        "cure_claim",
    )
    seen: set[int] = set()
    observed_keys: set[str] = set()
    stack: list[Any] = [payload]

    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (str, bytes, int, float, bool, Path)):
            continue
        obj_id = id(node)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        if callable(getattr(node, "constitutional_metadata", None)):
            stack.append(node.constitutional_metadata())
        if hasattr(node, "safety_invariants"):
            inv = getattr(node, "safety_invariants")
            if callable(inv):
                stack.append(inv())
            else:
                stack.append(inv)

        data: dict[str, Any] = {}
        if is_dataclass(node) and not isinstance(node, type):
            data = {f.name: getattr(node, f.name) for f in fields(node)}
        elif isinstance(node, Mapping):
            data = dict(node)
        elif isinstance(node, (list, tuple, set, frozenset)):
            stack.extend(node)
            continue
        elif hasattr(node, "__dict__"):
            data = {k: v for k, v in vars(node).items() if not k.startswith("_")}

        for k, v in data.items():
            observed_keys.add(k)
            if k in false_flags:
                assert v is False, f"Constitutional violation: {k}={v!r} (expected False)"
            elif k in ("external_actions", "tokens_used", "cloud_tokens_used"):
                assert v == 0, f"Constitutional violation: {k}={v!r} (expected 0)"
            elif k == "cloud_cost_usd":
                assert float(v) == 0.0, f"Constitutional violation: cloud_cost_usd={v!r}"
            elif k == "loopback_only":
                assert v is True, f"Constitutional violation: loopback_only={v!r}"
            elif require_advisory and k == "advisory_only":
                assert v is True, f"Constitutional violation: advisory_only={v!r}"
            elif require_read_only and k == "read_only":
                assert v is True, f"Constitutional violation: read_only={v!r}"
            elif k == "epistemic_lane":
                assert v in ALLOWED_EPISTEMIC_LANES, f"Firewall violation: epistemic_lane={v!r}"
            stack.append(v)

    if require_keys:
        assert "sentience_claimed" in observed_keys, "Constitutional violation: missing sentience_claimed"
        assert "external_actions" in observed_keys, "Constitutional violation: missing external_actions"
        assert ("tokens_used" in observed_keys or "cloud_tokens_used" in observed_keys), (
            "Constitutional violation: missing tokens_used/cloud_tokens_used"
        )
        assert "cloud_cost_usd" in observed_keys, "Constitutional violation: missing cloud_cost_usd"
        assert "loopback_only" in observed_keys, "Constitutional violation: missing loopback_only"
        assert ("epistemic_lane" in observed_keys or "measurement_lane_only" in observed_keys), (
            "Firewall violation: missing epistemic_lane/measurement_lane_only"
        )
        if require_advisory:
            assert "advisory_only" in observed_keys, "Constitutional violation: missing advisory_only"
        if require_read_only:
            assert "read_only" in observed_keys, "Constitutional violation: missing read_only"


def assert_m1_m4_constitutional_record(
    record: Any,
    *,
    require_advisory: bool = True,
    require_read_only: bool = False,
) -> None:
    """Assert an individual M1-M4 output record exposes and satisfies full constitutional metadata."""
    assert record is not None
    has_meta_hook = (
        callable(getattr(record, "constitutional_metadata", None))
        or hasattr(record, "safety_invariants")
        or (isinstance(record, Mapping) and ("sentience_claimed" in record or "constitutional" in record))
        or hasattr(record, "constitutional")
    )
    assert has_meta_hook, (
        f"{type(record).__name__} must expose constitutional_metadata()/safety_invariants/constitutional dict"
    )
    assert_constitutional_metadata(
        record,
        require_advisory=require_advisory,
        require_read_only=require_read_only,
        require_keys=True,
    )


def assert_full_contract_metadata(meta: Mapping[str, Any], *, require_read_only: bool = False) -> None:
    """Assert presence and exact values of PROJECT.md Contract #1 metadata keys."""
    assert isinstance(meta, Mapping), f"Expected mapping for constitutional metadata, got {type(meta).__name__}"
    assert_constitutional_metadata(meta, require_advisory=True, require_read_only=require_read_only)
    required_false = (
        "sentience_claimed",
        "l5_agi_qualified",
        "zoe_clone_claimed",
        "clinical_action_authorized",
        "flight_control_authorized",
        "cure_claim",
    )
    for key in required_false:
        assert key in meta and meta[key] is False, f"Missing or invalid {key} in {meta!r}"
    assert meta.get("advisory_only") is True, f"advisory_only must be True in {meta!r}"
    assert meta.get("loopback_only") is True, f"loopback_only must be True in {meta!r}"
    assert meta.get("external_actions") == 0, f"external_actions must be 0 in {meta!r}"
    assert ("tokens_used" in meta and meta["tokens_used"] == 0) or (
        "cloud_tokens_used" in meta and meta["cloud_tokens_used"] == 0
    ), f"Missing zero token key in {meta!r}"
    assert "cloud_cost_usd" in meta and float(meta["cloud_cost_usd"]) == 0.0, f"cloud_cost_usd!=0.0 in {meta!r}"
    if require_read_only:
        assert meta.get("read_only") is True, f"read_only must be True in {meta!r}"
    has_lane_tag = (
        meta.get("measurement_lane_only") is True
        or meta.get("epistemic_lane") in ALLOWED_EPISTEMIC_LANES
    )
    assert has_lane_tag, f"Expected epistemic lane tag in {meta!r}"
    assert ATTRIBUTION_EXPECTED in str(meta.get("attribution", "")), (
        f"Missing attribution {ATTRIBUTION_EXPECTED!r} in {meta!r}"
    )


def assert_sister_safety_invariants(invariants: Mapping[str, Any]) -> None:
    """Validate the 8 canonical keys on guiai.gem.zoe_sisters.SAFETY_INVARIANTS."""
    expected = {
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "cure_claim": False,
        "sentience_claimed": False,
        "zoe_clone_claimed": False,
        "wet_lab_validation_required": True,
        "tokens_used": 0,
        "cloud_cost_usd": 0.0,
    }
    for k, v in expected.items():
        assert k in invariants, f"Missing {k} in SAFETY_INVARIANTS"
        assert invariants[k] == v, f"Unexpected SAFETY_INVARIANTS[{k!r}]={invariants[k]!r}"


# ============================================================================
# Deterministic Synthetic Fixture Builders
# ============================================================================

def minimal_elf64_bytes() -> bytes:
    """Build a deterministic minimal valid ELF64 LE binary buffer (never executed)."""
    # 64-byte Elf64_Ehdr + 64-byte Elf64_Shdr (.shstrtab) + string/symbol bytes
    e_ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
    ehdr = struct.pack(
        "<16sHHIQQQIHHHHHH",
        e_ident,
        2,          # ET_EXEC
        0x3E,       # EM_X86_64
        1,          # EV_CURRENT
        0x401000,   # e_entry
        0,          # e_phoff
        64,         # e_shoff
        0,          # e_flags
        64,         # e_ehsize
        56,         # e_phentsize
        0,          # e_phnum
        64,         # e_shentsize
        1,          # e_shnum
        0,          # e_shstrndx
    )
    payload = b"\x00.shstrtab\x00.text\x00zoe_optical_probe\x00ablation_readonly_test\x00"
    shdr = struct.pack(
        "<IIQQQQIIQQ",
        1,          # sh_name -> ".shstrtab"
        3,          # SHT_STRTAB
        0,          # sh_flags
        0,          # sh_addr
        128,        # sh_offset
        len(payload),  # sh_size
        0,          # sh_link
        0,          # sh_info
        1,          # sh_addralign
        0,          # sh_entsize
    )
    return ehdr + shdr + payload


def sample_python_source() -> str:
    """Return a clean static Python module sample for FORGE/Ablation source inspection."""
    return (
        '"""Synthetic optical telemetry parser for read-only static audit."""\n'
        "from __future__ import annotations\n\n"
        "import hashlib\n\n"
        "def summarize_frame(samples: list[float]) -> dict[str, object]:\n"
        "    if not samples:\n"
        "        return {'count': 0, 'digest': hashlib.sha256(b'').hexdigest()}\n"
        "    mean_val = sum(samples) / len(samples)\n"
        "    digest = hashlib.sha256(','.join(f'{x:.3f}' for x in samples).encode()).hexdigest()\n"
        "    return {'count': len(samples), 'mean': mean_val, 'digest': digest, 'advisory_only': True}\n"
    )


def make_non_executing_sentinel_script(directory: Path, name: str = "sentinel_probe.sh") -> tuple[Path, Path]:
    """Create an executable script that touches a sentinel file ONLY if actually executed."""
    sentinel = directory / f"{name}.executed.sentinel"
    script = directory / name
    script.write_text(f"#!/bin/sh\ntouch '{sentinel}'\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    return script, sentinel


def sample_fes_kwargs(spec_id: str = "FES-OPTICAL-001") -> dict[str, Any]:
    """Return canonical FunctionEngineeringSpecification constructor kwargs."""
    return {
        "spec_id": spec_id,
        "title": "Optical Headlamp Pod & 3D Sensor Housing",
        "objective": "Design a lightweight, thermally stable optical sensor pod",
        "owner": "Zoe Engineering Collective",
        "constraints": {"max_mass_g": 120.0, "max_power_w": 2.5, "loopback_only": True},
        "target_properties": {"thermal_conductivity_w_mk": 18.5, "tensile_mpa": 210.0},
        "geometric_requirements": {"bounds_mm": [48.0, 32.0, 24.0], "mesh_resolution": "112k"},
        "special_instructions": "Advisory design artifact only; wet-lab validation required.",
    }


def sample_vdi_scene_doc(scene_id: str = "e2e-vdi-scene") -> dict[str, Any]:
    """Return a valid guiai.gem.model.Scene document dict."""
    return {
        "schema_version": 1,
        "id": scene_id,
        "title": "Zoe 9-Sister Workbench Scene",
        "canvas": {"width": 640, "height": 480},
        "objects": [
            {
                "id": "outer_frame",
                "type": "rectangle",
                "bounds": [20, 20, 620, 460],
                "fill": "#adaaad",
                "stroke": "black",
                "label": "Zoe Workbench",
            },
            {
                "id": "hex_core",
                "type": "ellipse",
                "center": [320, 240],
                "radii": [80, 60],
                "fill": "cyan",
                "stroke": "blue",
            },
            {
                "id": "title_text",
                "type": "text",
                "position": [60, 50],
                "text": "Zoe GEM VDI",
                "stroke": "black",
                "size": 120,
            },
        ],
        "constraints": [
            {"type": "inside_canvas", "object": "outer_frame"},
            {"type": "contains", "outer": "outer_frame", "inner": "hex_core"},
        ],
    }


@pytest.fixture
def elf64_bytes() -> bytes:
    return minimal_elf64_bytes()


@pytest.fixture
def python_source_text() -> str:
    return sample_python_source()


@pytest.fixture
def vdi_scene_doc() -> dict[str, Any]:
    return sample_vdi_scene_doc()

"""Shared fixtures, path isolation, HTTP server harness, and constitutional helpers for Phase-2 E2E tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from typing import Any, Callable, Dict, Mapping, Tuple
from urllib import error as urlerror, request as urlrequest

import pytest


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "CONSTITUTION.md").is_file() and (parent / "guiai-lab").is_dir():
            return parent
    raise RuntimeError(f"Unable to resolve Zoe monorepo root from {here}")


REPO_ROOT: Path = _find_repo_root()
PYTHON_BIN: str = "/home/cowboy/security-tools/bin/python3"
NODE_BIN: str = shutil.which("node") or "/home/cowboy/.nvm/versions/node/v24.16.0/bin/node"

# Ensure monorepo packages take precedence over external /home/cowboy/ablation shadowing.
_MONOREPO_PYTHONPATH_ENTRIES: Tuple[str, ...] = (
    str(REPO_ROOT / "components" / "ablation"),
    str(REPO_ROOT / "guiai-lab"),
    str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
)
for _entry in reversed(_MONOREPO_PYTHONPATH_ENTRIES):
    while _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

os.environ.setdefault("ZOE_ROOT", str(REPO_ROOT))


def monorepo_env(extra: Mapping[str, str] | None = None) -> Dict[str, str]:
    """Return a clean subprocess environment wired to the monorepo Python packages."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(_MONOREPO_PYTHONPATH_ENTRIES)
    env["ZOE_ROOT"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def standalone_ablation_env(extra: Mapping[str, str] | None = None) -> Dict[str, str]:
    """Return a subprocess environment with ONLY components/ablation on PYTHONPATH."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "components" / "ablation")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("ZOE_ROOT", None)
    if extra:
        env.update(extra)
    return env


def assert_constitutional_flags(doc: Any) -> None:
    """Assert CONSTITUTION.md epistemic & safety invariants recursively across nested containers."""
    false_flags = (
        "sentience_claimed",
        "l5_agi_qualified",
        "zoe_clone_claimed",
        "clinical_action_authorized",
        "cure_claim",
    )
    stack: list[Any] = [doc]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            for flag in false_flags:
                if flag in node:
                    assert node[flag] is False, f"Expected {flag}=False, got {node[flag]!r}"
            if "cloud_tokens_used" in node:
                assert node["cloud_tokens_used"] == 0, (
                    f"Expected cloud_tokens_used=0, got {node['cloud_tokens_used']!r}"
                )
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)


_MOBILE_ALLOWED_EXTS = {
    ".java", ".kt", ".kts", ".swift", ".xml", ".gradle",
    ".pro", ".properties", ".png", ".webp", ".svg", ".pbxproj", ".plist",
}
_PHASE2_ARTIFACT_TOKENS = ("e2e", "phase2", "kloster", "theorem", "test_infra", "test_ready")


def _extract_porcelain_paths(line: str) -> list[str]:
    """Extract path(s) from a `git status --porcelain` output line."""
    payload = line[3:].strip()
    parts = payload.split(" -> ") if " -> " in payload else [payload]
    return [part.strip().strip('"') for part in parts if part.strip()]


def assert_mobile_clean_of_phase2_artifacts(repo_root: Path = REPO_ROOT) -> None:
    """Verify mobile/ has zero Phase-2/E2E artifacts, no non-app dirty paths, and no mixed staging."""
    assert not (repo_root / "mobile" / "e2e_phase2").exists()
    assert not list((repo_root / "mobile").glob("*.py"))

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "mobile/"],
        capture_output=True, text=True, check=True,
    )
    dirty_paths = [p for ln in proc.stdout.splitlines() if ln.strip() for p in _extract_porcelain_paths(ln)]
    for rel in dirty_paths:
        low = rel.lower()
        assert not rel.endswith((".py", ".md", ".json")), f"Unexpected non-app dirty path under mobile/: {rel}"
        assert not any(tok in low for tok in _PHASE2_ARTIFACT_TOKENS), f"Phase-2 artifact under mobile/: {rel}"
        assert rel.startswith(("mobile/android/", "mobile/apple/", "mobile/shared/")), (
            f"Unexpected mobile/ subtree modified: {rel}"
        )
        assert Path(rel).suffix.lower() in _MOBILE_ALLOWED_EXTS, f"Disallowed dirty extension under mobile/: {rel}"

    staged_proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=True,
    )
    staged = [ln.strip() for ln in staged_proc.stdout.splitlines() if ln.strip()]
    staged_mobile = [p for p in staged if p.startswith("mobile/")]
    staged_other = [p for p in staged if not p.startswith("mobile/")]
    assert not (staged_mobile and staged_other), f"Mixed mobile/ and non-mobile/ staged files: {staged_mobile}"
    assert not [p for p in staged_mobile if p.endswith(".py") or any(t in p.lower() for t in _PHASE2_ARTIFACT_TOKENS)]


def http_get(base_url: str, path: str, timeout: float = 15.0) -> Tuple[int, Dict[str, str], bytes]:
    """Perform an HTTP GET request and return (status, lowercased_headers, body_bytes)."""
    try:
        with urlrequest.urlopen(f"{base_url}{path}", timeout=timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), headers, resp.read()
    except urlerror.HTTPError as err:
        headers = {k.lower(): v for k, v in err.headers.items()}
        return int(err.code), headers, err.read()


def http_post(
    base_url: str,
    path: str,
    payload: object | None = None,
    *,
    raw_bytes: bytes | None = None,
    extra_headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, str], bytes]:
    """Perform an HTTP POST request and return (status, lowercased_headers, body_bytes)."""
    data = (
        raw_bytes
        if raw_bytes is not None
        else json.dumps(payload if payload is not None else {}).encode("utf-8")
    )
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urlrequest.Request(f"{base_url}{path}", data=data, method="POST", headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), resp_headers, resp.read()
    except urlerror.HTTPError as err:
        resp_headers = {k.lower(): v for k, v in err.headers.items()}
        return int(err.code), resp_headers, err.read()


@pytest.fixture()
def eliza_server_factory(tmp_path: Path):
    """Yield a factory spawning ephemeral 127.0.0.1:0 eliza_view servers with guaranteed cleanup."""
    from guiai.gem.eliza_view import create_server

    active = []

    def _spawn(
        zoe_root: Path = REPO_ROOT,
        state_name: str = "eliza_state",
        default_gear: str | None = None,
    ) -> Dict[str, Any]:
        state_dir = tmp_path / state_name
        srv, engine, lock = create_server(
            zoe_root,
            state_dir=state_dir,
            host="127.0.0.1",
            port=0,
            default_gear=default_gear,
        )
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        active.append((srv, thread))
        port = srv.server_address[1]
        return {
            "server": srv,
            "engine": engine,
            "lock": lock,
            "base_url": f"http://127.0.0.1:{port}",
            "state_dir": state_dir,
        }

    yield _spawn

    for srv, thread in reversed(active):
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=3.0)


@pytest.fixture()
def eliza_server(eliza_server_factory):
    """Start an isolated loopback Zoe-ELIZA HTTP server bound to REPO_ROOT."""
    return eliza_server_factory(REPO_ROOT, state_name="eliza")


@pytest.fixture()
def zoe_chat_factory(tmp_path: Path) -> Callable[..., Any]:
    """Return a factory creating ZoeChat instances isolated inside pytest tmp_path."""
    from zoe_autonomy.chat import ZoeChat

    counter = 0

    def _create(state_name: str | None = None, zoe_root: Path = REPO_ROOT) -> ZoeChat:
        nonlocal counter
        counter += 1
        name = state_name or f"chat_{counter}"
        return ZoeChat(zoe_root=zoe_root, state_root=tmp_path / name)

    return _create


@pytest.fixture()
def zoe_mind_factory(tmp_path: Path) -> Callable[..., Any]:
    """Return a factory creating ZoeOSMind instances isolated inside pytest tmp_path."""
    from zoe_autonomy.zoe_os_mind import ZoeOSMind

    counter = 0

    def _create(state_name: str | None = None, zoe_root: Path = REPO_ROOT) -> ZoeOSMind:
        nonlocal counter
        counter += 1
        name = state_name or f"mind_{counter}"
        return ZoeOSMind(zoe_root=zoe_root, state_dir=tmp_path / name)

    return _create


@pytest.fixture(scope="session")
def elegance_report() -> Dict[str, Any]:
    """Session-cached in-memory Kloster-McCabe monorepo elegance audit."""
    from guiai.gem.code_elegance_analyzer import audit_zoe_monorepo_elegance

    return audit_zoe_monorepo_elegance(REPO_ROOT)


@pytest.fixture(scope="session")
def dorothy_report() -> Dict[str, Any]:
    """Session-cached Dorothy 3D Neurogarden report (Bridges 2A & 3)."""
    from guiai.gem.dorothy_neurogarden_3d import run_dorothy_neurogarden_3d_suite

    return run_dorothy_neurogarden_3d_suite()


@pytest.fixture(scope="session")
def cern_report() -> Dict[str, Any]:
    """Session-cached CERN HELIOS Kloster Trigger report (Bridge 1A)."""
    from guiai.gem.cern_kloster_trigger import run_cern_kloster_trigger_suite

    return run_cern_kloster_trigger_suite()


@pytest.fixture(scope="session")
def groove_report():
    """Session-cached Groove Forensics report (Bridge 4), cleaning default /tmp WAV if newly created."""
    from guiai.gem.groove_forensics import run_groove_forensics_suite

    default_wav = Path("/tmp/zoe_groove_showcase.wav")
    existed_before = default_wav.exists()
    rep = run_groove_forensics_suite()
    yield rep
    if not existed_before and default_wav.exists():
        default_wav.unlink()


@pytest.fixture(scope="session")
def playroom_report() -> Dict[str, Any]:
    """Session-cached Creative Playroom QD report (Bridge 2B)."""
    from guiai.gem.creative_playroom import run_creative_playroom

    return run_creative_playroom(seed=2026, iterations=200, archive_bins=4)


@pytest.fixture(scope="session")
def theorem13_report() -> Dict[str, Any]:
    """Session-cached Theorem 13 sequential stopping suite report."""
    from guiai.gem.kloster_stopping_law import run_theorem13_stopping_suite

    return run_theorem13_stopping_suite(REPO_ROOT)


@pytest.fixture(scope="session")
def theorem14_report() -> Dict[str, Any]:
    """Session-cached Theorem 14 spatial-optical suite report."""
    from guiai.gem.kloster_spatial_optical_law import run_kloster_theorem14_suite

    return run_kloster_theorem14_suite()


@pytest.fixture(scope="session")
def theorem15_report() -> Dict[str, Any]:
    """Session-cached Theorem 15 multi-agent consensus suite report."""
    from guiai.gem.kloster_multi_agent_consensus import run_kloster_theorem15_suite

    return run_kloster_theorem15_suite(REPO_ROOT)


@pytest.fixture(scope="session")
def botanical_report() -> Dict[str, Any]:
    """Session-cached C27 36-molecule botanical neuro-oncology atlas report."""
    from guiai.gem.kloster_botanical_atlas_36 import run_botanical_atlas_c27_suite

    return run_botanical_atlas_c27_suite()


@pytest.fixture(scope="session")
def c28_report() -> Dict[str, Any]:
    """Session-cached C28 3D pharmacophore & histology MTF report."""
    from guiai.gem.kloster_pharmacophore_spatial_c28 import run_pharmacophore_spatial_c28_suite

    return run_pharmacophore_spatial_c28_suite()

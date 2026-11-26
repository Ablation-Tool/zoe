"""Hygiene-safe fixtures, zero-Office runtime guards, and opaque-box verifiers."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Iterator, Sequence, TypeVar
import xml.etree.ElementTree as ET

from PIL import Image, ImageStat
import pytest

T = TypeVar("T")
_MISSING = object()


def _find_repo_root() -> Path:
    """Resolve monorepo root dynamically without hardcoded workstation paths."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "CONSTITUTION.md").is_file() and (parent / "guiai-lab").is_dir():
            return parent
    raise RuntimeError(f"Unable to locate monorepo root from {here}")


REPO_ROOT: Path = _find_repo_root()
PYTHON_BIN: str = sys.executable
FORBIDDEN_OFFICE_TOOLS: tuple[str, ...] = (
    "soffice",
    "libreoffice",
    "soffice.bin",
    "pdftoppm",
    "unoconv",
    "gs",
)

_PYTHONPATH_ENTRIES: tuple[str, ...] = (
    str(REPO_ROOT / "guiai-lab"),
    str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
)

for _entry in reversed(_PYTHONPATH_ENTRIES):
    while _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

os.environ.setdefault("ZOE_ROOT", str(REPO_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    """Register all tier and feature-area markers programmatically."""
    markers = (
        "tier1: Tier 1 isolated feature happy-path E2E tests across Areas F1-F8",
        "tier2: Tier 2 boundary, corner, and negative/error-path E2E tests across Areas F1-F8",
        "tier3: Tier 3 pairwise cross-feature E2E combination tests across Areas F1-F8",
        "tier4: Tier 4 realistic end-to-end application workload scenarios (W1-W6)",
        "tier5: Tier 5 adversarial white-box edge-case and regression tests",
        "wordchart: Area F1 - WordChart 4-zone model, templates, typography, bullets, and locator borders",
        "graph: Area F2 - Graph 8-family chart engine and CSV/DIF/PRN/JSON adapters",
        "draw_plus: Area F3 - Draw Plus composition, .GEM VDI codec, botanical toolkit, and pure-Python render",
        "slideshow: Area F4 - Offline Slide Show Player (.LIS / HTML5) and zoe present CLI",
        "anthology: Area F5 - Anthology Volumes I-VI deliverables and grounded metrics",
        "ledger: Area F6 - Clean-room presentations ledger (catalog.json, SHA256SUMS.presentations, README)",
        "navigation: Area F7 - Repository navigation docs, local link integrity, and observatory 6/6 PASS",
        "hygiene: Area F8 - Constitutional attribution, epistemic honesty, and hygiene leak guards",
    )
    for line in markers:
        config.addinivalue_line("markers", line)


def zoe_cli_cmd() -> list[str]:
    """Resolve the `zoe` CLI command dynamically from the active Python interpreter."""
    sibling = Path(PYTHON_BIN).parent / "zoe"
    if sibling.is_file():
        return [str(sibling)]
    found = shutil.which("zoe")
    if found:
        return [found]
    return [PYTHON_BIN, "-m", "guiai.gem.unified_cli"]


def _command_tool_name(cmd: Any) -> str:
    """Extract normalized executable basename from a subprocess command."""
    if isinstance(cmd, (list, tuple)) and cmd:
        return Path(str(cmd[0])).name.lower()
    if isinstance(cmd, (str, os.PathLike)):
        text = str(cmd).strip()
        head = text.split()[0] if text else ""
        return Path(head).name.lower()
    return ""


def _build_office_shims(bin_dir: Path, sentinel: Path) -> None:
    """Create executable shims that record invocation and exit 127."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = f"#!/bin/sh\ntouch '{sentinel}'\nexit 127\n"
    for tool in FORBIDDEN_OFFICE_TOOLS:
        shim = bin_dir / tool
        shim.write_text(script, encoding="utf-8")
        shim.chmod(0o755)


@pytest.fixture
def no_office_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[dict[str, str], Path]]:
    """Strip external Office/PDF tools from PATH and block in-process invocations."""
    shadow_bin = tmp_path / "no_office_bin"
    sentinel = tmp_path / ".forbidden_office_tool_invoked"
    _build_office_shims(shadow_bin, sentinel)

    orig_which = shutil.which
    orig_popen = subprocess.Popen

    def guarded_which(cmd: str, mode: int = os.F_OK | os.X_OK, path: str | None = None) -> str | None:
        if Path(str(cmd)).name.lower() in FORBIDDEN_OFFICE_TOOLS:
            raise AssertionError(f"Forbidden lookup of external office/PDF tool: {cmd!r}")
        return orig_which(cmd, mode=mode, path=path)

    class GuardedPopen(orig_popen):  # type: ignore[misc, valid-type]
        def __init__(self, args: Any, *pargs: Any, **kwargs: Any) -> None:
            name = _command_tool_name(args)
            if name in FORBIDDEN_OFFICE_TOOLS:
                raise AssertionError(f"Forbidden subprocess invocation of external office/PDF tool: {args!r}")
            super().__init__(args, *pargs, **kwargs)

    monkeypatch.setattr(shutil, "which", guarded_which)
    monkeypatch.setattr(subprocess, "Popen", GuardedPopen)

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(shadow_bin), env.get("PATH", "")])
    yield env, sentinel
    assert not sentinel.exists(), "External Office/PDF tool shim was executed at runtime"


@pytest.fixture(autouse=True)
def forbid_office_tools(no_office_env: tuple[dict[str, str], Path]) -> tuple[dict[str, str], Path]:
    """Automatically enforce zero external Office/PDF runtime across every E2E test."""
    return no_office_env


@pytest.fixture
def isolated_pres_env(tmp_path: Path, no_office_env: tuple[dict[str, str], Path]) -> dict[str, str]:
    """Build an isolated environment dict redirecting HOME/XDG/ZOE_STATE_DIR to tmp_path."""
    base_env, _ = no_office_env
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    env = dict(base_env)
    existing_pp = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and p not in _PYTHONPATH_ENTRIES]
    env["PYTHONPATH"] = os.pathsep.join([*_PYTHONPATH_ENTRIES, *existing_pp])
    env["ZOE_ROOT"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(home_dir)
    env["USERPROFILE"] = str(home_dir)
    env["XDG_CONFIG_HOME"] = str(home_dir / ".config")
    env["XDG_CACHE_HOME"] = str(home_dir / ".cache")
    env["XDG_DATA_HOME"] = str(home_dir / ".local" / "share")
    env["ZOE_STATE_DIR"] = str(home_dir / ".zoe")
    return env


def require_contract(module_path: str, symbol: str | None = None, *, req_id: str = "") -> Any:
    """Lazy-import a contract module/symbol and fail clearly if unimplemented."""
    prefix = f"[{req_id}] " if req_id else ""
    try:
        mod = importlib.import_module(module_path)
    except (ModuleNotFoundError, ImportError) as exc:
        pytest.fail(f"{prefix}Deliverable not yet implemented ({module_path}): {exc}")
    if symbol is None:
        return mod
    if not hasattr(mod, symbol):
        pytest.fail(f"{prefix}Deliverable symbol not yet implemented: {module_path}.{symbol}")
    return getattr(mod, symbol)


def _filter_kwargs(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    required_keys: Sequence[str],
    candidates: Mapping[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Select positional args and kwargs accepted by `fn` without silent semantic drops."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    has_var_pos = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    pos_params = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    effective_args = args if has_var_pos else args[:len(pos_params)]
    bound_names = {p.name for p in pos_params[:len(effective_args)]}
    accepted = {
        p.name for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    filtered = {
        k: v for k, v in candidates.items()
        if k not in bound_names and (has_var_kw or k in accepted)
    }
    fn_name = getattr(fn, "__qualname__", repr(fn))
    if candidates and not filtered and not has_var_kw:
        raise TypeError(f"{fn_name} accepted none of kwargs {sorted(candidates)} (accepted: {sorted(accepted)})")
    if required_keys and not has_var_kw:
        missing = [k for k in required_keys if k not in filtered and k not in bound_names]
        if missing:
            raise TypeError(f"{fn_name} missing required kwargs {missing} (accepted: {sorted(accepted)})")
    return effective_args, filtered


def call_with_supported_kwargs(
    fn: Callable[..., T],
    *args: Any,
    _required_keys: Sequence[str] = (),
    **candidates: Any,
) -> T:
    """Invoke callable passing positional args and kwargs accepted by its signature without silent semantic drops."""
    effective_args, filtered = _filter_kwargs(fn, args, _required_keys, candidates)
    return fn(*effective_args, **filtered)


def pick(obj: Any, *keys: str, default: Any = _MISSING) -> Any:
    """Return the first present mapping key or object attribute."""
    for key in keys:
        if isinstance(obj, Mapping) and key in obj:
            return obj[key]
        if hasattr(obj, key):
            return getattr(obj, key)
    if default is not _MISSING:
        return default
    raise KeyError(f"None of {keys!r} found on {type(obj).__name__}")


def verify_gem_bytes(data: bytes, *, check_16_9_bounds: bool = True) -> dict[str, Any]:
    """Validate .GEM bytes with seasip_gem, opcode_inventory (no legacy opcode 13), and 13333x7500 RC bounds."""
    from guiai.gem import seasip_gem, vdi

    assert isinstance(data, (bytes, bytearray)) and len(data) >= 50, "GEM metafile too short"
    raw = bytes(data)
    report = seasip_gem.verify_seasip_gem_metafile(raw)
    assert report["valid"] is True, f"Invalid .GEM metafile: {report}"
    assert report["coordinate_system"] == "RC", f"Expected RC coordinates, got {report['coordinate_system']}"
    inv = vdi.opcode_inventory(raw)
    assert "vs_color_legacy" not in inv, f"Legacy 4-int opcode 13 (vs_color_legacy) is forbidden: {inv}"
    parsed = vdi.parse_metafile(raw)
    if check_16_9_bounds:
        cx1, cy1, cx2, cy2 = parsed["header"]["coordinate_bounds"]
        assert abs(cx2 - cx1) in (13332, 13333), f"Unexpected RC width bounds: {(cx1, cx2)}"
        assert abs(cy2 - cy1) in (7499, 7500), f"Unexpected RC height bounds: {(cy1, cy2)}"
    return {"seasip": report, "parsed": parsed, "inventory": inv}


def verify_rendered_image(
    path: Path,
    *,
    expected_aspect: float = 16.0 / 9.0,
    min_size: tuple[int, int] = (320, 180),
) -> tuple[int, int]:
    """Open rendered PNG/JPG via Pillow and assert non-blank variance and 16:9 aspect."""
    assert path.is_file() and path.stat().st_size > 0, f"Missing or empty image: {path}"
    with Image.open(path) as img:
        width, height = img.size
        assert width >= min_size[0] and height >= min_size[1], f"Image too small: {(width, height)} at {path}"
        aspect = width / max(1, height)
        assert abs(aspect - expected_aspect) <= 0.04, f"Expected 16:9 aspect, got {width}x{height} ({aspect:.3f})"
        stat = ImageStat.Stat(img.convert("RGB"))
        assert max(stat.stddev) > 1.0, f"Rendered image appears blank/uniform: {path}"
    return width, height


def verify_svg_document(svg_text: str) -> ET.Element:
    """Parse SVG text via ElementTree and verify zero external http(s) dependencies."""
    assert isinstance(svg_text, str) and "<svg" in svg_text, "Expected non-empty SVG string"
    root = ET.fromstring(svg_text)
    local_tag = root.tag.split("}", 1)[-1]
    assert local_tag == "svg", f"Expected <svg> root, got {root.tag}"
    assert root.attrib.get("viewBox"), "SVG missing viewBox attribute"
    lowered = svg_text.lower()
    for bad in ("<script", "http://", "https://"):
        if bad == "<script":
            assert "<script" not in lowered, "SVG must not contain script tags"
        else:
            for elem in root.iter():
                for attr_val in elem.attrib.values():
                    if bad in attr_val.lower() and "w3.org" not in attr_val.lower():
                        raise AssertionError(f"SVG references external resource: {attr_val}")
    return root


_MD_OR_HTML_LINK_RE = re.compile(
    r"""(?:href|src)=["']([^"']+)["']|!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)"""
)


def extract_local_links(md_path: Path) -> list[str]:
    """Extract local relative link/image targets from a markdown file."""
    text = md_path.read_text(encoding="utf-8")
    targets: list[str] = []
    for match in _MD_OR_HTML_LINK_RE.finditer(text):
        raw = (match.group(1) or match.group(2) or "").strip()
        if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "data:", "file://")):
            continue
        targets.append(raw)
    return targets


def scan_markdown_links(md_paths: Sequence[Path], *, root: Path = REPO_ROOT) -> list[str]:
    """Return a list of broken relative local links across the provided markdown paths."""
    broken: list[str] = []
    for md_path in md_paths:
        for raw in extract_local_links(md_path):
            target_part = raw.split("#", 1)[0].split("?", 1)[0]
            if not target_part:
                continue
            resolved = (md_path.parent / target_part).resolve()
            if not resolved.exists():
                rel = md_path.relative_to(root) if md_path.is_relative_to(root) else md_path
                broken.append(f"{rel} -> {raw}")
    return broken


def _hygiene_patterns(*, strict_file_scheme: bool = False) -> list[tuple[str, re.Pattern[str]]]:
    """Build forbidden hygiene regexes dynamically so no raw leak literals live in test source."""
    home_pat = "/" + "home" + "/" + r"[A-Za-z0-9._-]+"
    media_pat = "/" + "media" + "/" + r"[A-Za-z0-9._-]+"
    serial_pat = r"\b" + "2A111" + r"FDH[A-Za-z0-9]*\b"
    personal_email = "exile" + "kingdom" + "@" + "proton" + r"\.me"
    tld_email = r"(?<!state)@[A-Za-z0-9.-]+\.(?:com|org|net|edu|gov|io|me|dev|ai|uk|de|fr)\b"
    api_key_pat = "sk-" + "ant-" + r"[A-Za-z0-9_-]+"
    file_pat = "file" + "://" if strict_file_scheme else "file" + ":///"
    return [
        ("personal_home_path", re.compile(home_pat, re.IGNORECASE)),
        ("personal_media_path", re.compile(media_pat, re.IGNORECASE)),
        ("device_serial", re.compile(serial_pat, re.IGNORECASE)),
        ("personal_email", re.compile(personal_email, re.IGNORECASE)),
        ("real_email_address", re.compile(r"[A-Za-z0-9._%+-]+" + tld_email, re.IGNORECASE)),
        ("api_key", re.compile(api_key_pat)),
        ("file_uri", re.compile(file_pat, re.IGNORECASE)),
    ]


def find_hygiene_violations(text: str, *, strict_file_scheme: bool = False) -> list[str]:
    """Return list of hygiene rule violations found in text without false positives."""
    violations: list[str] = []
    for label, pattern in _hygiene_patterns(strict_file_scheme=strict_file_scheme):
        for match in pattern.finditer(text):
            snippet = match.group(0)
            if label == "real_email_address" and "proj.hook" in snippet.lower():
                continue
            if label == "personal_home_path" and "/home/runner" in snippet.lower():
                continue
            violations.append(f"{label}: {snippet!r}")
    return violations


def assert_hygiene_clean(text: str, label: str, *, strict_file_scheme: bool = False) -> None:
    """Assert text contains zero personal paths, device serials, personal emails, or URI leaks."""
    hits = find_hygiene_violations(text, strict_file_scheme=strict_file_scheme)
    assert not hits, f"Hygiene violations in {label}: {hits[:8]}"


def assert_constitutional_flags(payload: Mapping[str, Any], label: str = "payload") -> None:
    """Verify required epistemic honesty flags on constitutional metadata mappings."""
    expected = {
        "operational_metacognition_verified": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "external_actions": 0,
    }
    for key, val in expected.items():
        assert key in payload, f"Missing constitutional flag {key!r} in {label}"
        assert payload[key] == val, f"{label}[{key!r}] expected {val!r}, got {payload[key]!r}"
    if "cloud_cost_usd" in payload:
        assert float(payload["cloud_cost_usd"]) == 0.0, f"{label} cloud_cost_usd must be 0.0"


def find_headless_browser() -> str | None:
    """Locate an installed Chromium/Chrome binary dynamically."""
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """Compute lowercase SHA-256 hex digest using streaming reads."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256sums(sums_path: Path) -> list[tuple[str, str]]:
    """Parse `<64-hex>  <relative_path>` lines ignoring comments and blank lines."""
    entries: list[tuple[str, str]] = []
    for raw_line in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        hex_digest, rel_path = line.split(None, 1)
        entries.append((hex_digest, rel_path.strip()))
    return entries


def run_zoe_cli(
    args: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run the Zoe CLI subprocess with isolated environment and captured output."""
    cmd = [*zoe_cli_cmd(), *args]
    run_env = dict(env)
    run_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


_W3C_XML_NS_RE = re.compile(
    r"http://www\.w3\.org/(?:2000/svg|1999/xhtml|1999/xlink|xml/1998/namespace)(?=['\"\s<>]|$)",
    re.IGNORECASE,
)
_ROMAN_VOLUMES: dict[int, str] = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi"}


def assert_offline_player_no_cdn(player_html: str) -> None:
    """Verify player.html has zero CDN/external resources while exempting standard W3C XML namespaces."""
    lowered = player_html.lower()
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", lowered), "player.html must not contain <script src=...>"
    assert not re.search(r"<link\b[^>]*\bhref\s*=\s*(?!['\"]?data:)", lowered), "player.html must not contain <link href=...>"
    assert not re.search(r"@import\b", lowered), "player.html must not contain CSS @import"
    assert not re.search(r"url\(\s*['\"]?\s*https?://", lowered), "player.html must not contain url(http...) resources"
    cleaned = _W3C_XML_NS_RE.sub("", lowered)
    assert "http://" not in cleaned and "https://" not in cleaned, "player.html must be 100% zero-CDN offline"


def assert_offline_player_controls(player_html: str) -> None:
    """Verify zero-CDN offline HTML5 Slide Show Player structure and GEM Output keyboard/timer controls."""
    assert_offline_player_no_cdn(player_html)
    assert any(tok in player_html for tok in ("' '", '" "', "Space")), (
        "[R1/F4] Offline player.html missing Space key navigation"
    )
    for required in ("ArrowRight", "ArrowLeft", "ArrowUp", "Escape", "prefers-reduced-motion", "Cycle", "20s", "10s", "5s", "2s"):
        assert required in player_html, f"[R1/F4] Offline player.html missing {required!r}"
    for key_tok in ("t", "l", "f", "n", "g"):
        lo, up = key_tok.lower(), key_tok.upper()
        assert any(q + ch + q in player_html for q in ("'", '"') for ch in (lo, up)), (
            f"Missing shortcut {key_tok!r}"
        )


def _matches_slug_or_gallery(deck: Mapping[str, Any], vol_index: int, roman: str) -> bool:
    slug_or_gal = f"{deck.get('slug', '')} {deck.get('gallery', '')}".lower()
    if re.search(rf"(?:^|[\s\-_/])vol(?:ume)?[\-_]?{vol_index}(?:\b|[\-_/.])", slug_or_gal):
        return True
    return bool(re.search(rf"(?:^|[\s\-_/])vol(?:ume)?[\-_]?{roman}(?:$|[\s\-_/.])", slug_or_gal))


def _matches_label_or_title(deck: Mapping[str, Any], vol_index: int, roman: str) -> bool:
    label_or_title = f"{deck.get('volume_label', '')} {deck.get('volume', '')} {deck.get('title', '')}".lower()
    return bool(re.search(rf"\bvol(?:ume)?\.?\s*(?:{vol_index}|{roman})\b", label_or_title))


def select_anthology_volume(vol_decks: Sequence[Mapping[str, Any]], vol_index: int) -> Mapping[str, Any]:
    """Match Anthology Vol. I-VI deck by slug/gallery first, then title/volume label, with sorted-order fallback."""
    roman = _ROMAN_VOLUMES[vol_index]
    for deck in vol_decks:
        if _matches_slug_or_gallery(deck, vol_index, roman):
            return deck
    for deck in vol_decks:
        if _matches_label_or_title(deck, vol_index, roman):
            return deck
    ordered = sorted(vol_decks, key=lambda d: str(d.get("slug", "")))
    return ordered[vol_index - 1]


def ordered_anthology_volumes(vol_decks: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return Anthology Vol. I-VI decks ordered 1..6 using label matching with sorted fallback."""
    return [select_anthology_volume(vol_decks, idx) for idx in range(1, 7)]


def deck_sealed_artifacts(deck: Mapping[str, Any]) -> list[str]:
    """Extract declared .gem (scalar or plural list) or fallback .pptx relative paths from a catalog deck."""
    artifacts: list[str] = []
    gem = deck.get("gem")
    if isinstance(gem, str) and gem:
        artifacts.append(gem)
    gems = deck.get("gems")
    if isinstance(gems, (list, tuple)):
        artifacts.extend(str(item) for item in gems if item)
    if not artifacts and isinstance(deck.get("pptx"), str) and deck["pptx"]:
        artifacts.append(deck["pptx"])
    return artifacts

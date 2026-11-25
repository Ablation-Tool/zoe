"""Shared opaque-box fixtures, path isolation, progressive gates, and invariants for E2E Shared-Reasoning tests."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Callable, Coroutine, Dict, List, Sequence, Tuple, TypeVar

import pytest

T = TypeVar("T")


def _find_repo_root() -> Path:
    """Resolve monorepo root anchored on docs/CONSTITUTION.md and components/Zoe-Autonomy."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "CONSTITUTION.md").is_file() and (parent / "components" / "Zoe-Autonomy").is_dir():
            return parent
    raise RuntimeError(f"Unable to resolve Zoe monorepo root from {here}")


REPO_ROOT: Path = _find_repo_root()
PYTHON_BIN: str = "/home/cowboy/security-tools/bin/python3"
FFPROBE_BIN: str = shutil.which("ffprobe") or "/usr/bin/ffprobe"

_MONOREPO_PYTHONPATH_ENTRIES: Tuple[str, ...] = (
    str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"),
    str(REPO_ROOT / "guiai-lab"),
    str(REPO_ROOT / "components" / "ablation"),
)

# Prepend monorepo sources so components/ablation is never shadowed by /home/cowboy/ablation.
for _entry in reversed(_MONOREPO_PYTHONPATH_ENTRIES):
    while _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

os.environ.setdefault("ZOE_ROOT", str(REPO_ROOT))


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


def is_strict_mode() -> bool:
    """Return True when strict M5 release gate mode (ZOE_E2E_STRICT=1) is active."""
    return os.environ.get("ZOE_E2E_STRICT") == "1"


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Execute an async coroutine cleanly via stdlib asyncio.run."""
    return asyncio.run(coro)


def require_shared_reasoning(submodule: str | None = None, symbol: str | None = None) -> Any:
    """Import zoe_autonomy.shared_reasoning[.submodule] (and optional symbol).

    In progressive mode (ZOE_E2E_STRICT != 1), missing M2-M4 modules or symbols
    yield pytest.skip(...). In strict mode (ZOE_E2E_STRICT == 1), missing
    deliverables trigger pytest.fail(...).
    """
    mod_name = "zoe_autonomy.shared_reasoning" if submodule is None else f"zoe_autonomy.shared_reasoning.{submodule}"
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        if missing_name == mod_name or missing_name.startswith("zoe_autonomy.shared_reasoning"):
            msg = f"M2-M4 deliverable {mod_name!r} not yet available ({exc})"
            if is_strict_mode():
                pytest.fail(f"Strict mode failure — missing deliverable: {msg}")
            pytest.skip(f"Pending M2-M4 deliverable: {msg}")
        raise
    except ImportError as exc:
        msg = f"M2-M4 deliverable {mod_name!r} import failed ({exc})"
        if is_strict_mode():
            pytest.fail(f"Strict mode failure — import error: {msg}")
        pytest.skip(f"Pending M2-M4 deliverable: {msg}")

    if symbol is None:
        return mod

    try:
        return getattr(mod, symbol)
    except AttributeError as exc:
        msg = f"Symbol {symbol!r} not exported on {mod_name!r} ({exc})"
        if is_strict_mode():
            pytest.fail(f"Strict mode failure — missing symbol: {msg}")
        pytest.skip(f"Pending M2-M4 deliverable: {msg}")


def require_artifact(rel_path: str) -> Path:
    """Verify that a repo-relative deliverable artifact exists (skip/fail gated)."""
    target = REPO_ROOT / rel_path
    if not target.exists():
        msg = f"Artifact {rel_path!r} not found at {target}"
        if is_strict_mode():
            pytest.fail(f"Strict mode failure — missing artifact: {msg}")
        pytest.skip(f"Pending M2-M4 deliverable: {msg}")
    return target


def assert_constitutional_invariants(payload: Any, *, require_offline: bool = False) -> None:
    """Recursively validate CONSTITUTION.md invariants on mappings, sequences, or dataclasses."""
    false_flags = (
        "sentience_claimed",
        "l5_agi_qualified",
        "zoe_clone_claimed",
        "clinical_action_authorized",
        "cure_claim",
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
                elif require_offline and f.name == "cloud_tokens_used":
                    assert val == 0, f"Offline invariant violation: cloud_tokens_used={val!r} (expected 0)"
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
            if require_offline and "cloud_tokens_used" in node:
                assert node["cloud_tokens_used"] == 0, (
                    f"Offline invariant violation: cloud_tokens_used={node['cloud_tokens_used']!r} (expected 0)"
                )
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
                if require_offline and "cloud_tokens_used" in attr_items:
                    assert attr_items["cloud_tokens_used"] == 0, (
                        f"Offline invariant violation: cloud_tokens_used={attr_items['cloud_tokens_used']!r} (expected 0)"
                    )
                stack.extend(attr_items.values())


_ISO_UTC_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\b")
_EXPLICIT_ITEM_RE = re.compile(r"\b(?:item|arch(?:itecture)?|chair)\s*#?\s*([1-9])\b", re.IGNORECASE)
_ANY_EXPLICIT_ITEM_RE = re.compile(r"\b(?:item|arch(?:itecture)?|chair)\s*#?\s*(\d+)\b", re.IGNORECASE)
_SLOT_PREFIX_RE = re.compile(r"\bslot\s*#?\s*\d+\b", re.IGNORECASE)
_TABLE_DIVIDER_RE = re.compile(r"\|?[\s:\-|]+\|?")
_LIST_BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_MUSIC_ANCHOR_RE = re.compile(r"\b(?:music\s+start(?:ed)?|pre-?work\s+music)\b", re.IGNORECASE)


def parse_utc_timestamp(ts_str: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp string into a timezone-aware UTC datetime."""
    normalized = ts_str.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_item_from_fragment(fragment: str) -> int | None:
    """Extract architecture/item ID in 1..9 while ignoring timestamps and Slot N labels.

    If an explicit ``Arch/Item/Chair <N>`` label is present and ``N`` is outside ``1..9``
    (e.g., ``Arch 10`` or ``Item 0``), returns ``None`` rather than falling back to digits
    elsewhere in description text.
    """
    cleaned = _ISO_UTC_RE.sub(" ", fragment)
    cleaned = _SLOT_PREFIX_RE.sub(" ", cleaned)
    explicit_matches = list(_ANY_EXPLICIT_ITEM_RE.finditer(cleaned))
    if explicit_matches:
        for m in explicit_matches:
            val = int(m.group(1))
            if 1 <= val <= 9:
                return val
        return None
    m_num = re.search(r"(?<![.\d])([1-9])(?![.\d])", cleaned)
    if m_num:
        return int(m_num.group(1))
    return None


def _find_table_item_col(headers: Sequence[str]) -> int | None:
    """Identify the destination item/arch/chair column index in a Markdown table header."""
    norm = [re.sub(r"\s+", " ", h.strip().lower()) for h in headers]
    for idx, h in enumerate(norm):
        if re.fullmatch(r"to\s*[_-]?(?:item|arch(?:itecture)?|chair)(?:\s*(?:id|#))?", h):
            return idx
    for idx, h in enumerate(norm):
        if re.fullmatch(r"(?:item|arch(?:itecture)?|chair)(?:\s*(?:id|#))?", h):
            return idx
    for idx, h in enumerate(norm):
        if any(bad in h for bad in ("from", "prev", "slot", "delta", "Δt", "work", "desc", "note", "focus", "time", "utc")):
            continue
        if any(good in h for good in ("item", "chair", "arch")):
            return idx
    return None


def _extract_item_from_target_cell(cell: str) -> int | None:
    """Extract a 1..9 item ID strictly from an explicit target table cell."""
    cleaned = _SLOT_PREFIX_RE.sub(" ", cell.strip())
    explicit = list(_ANY_EXPLICIT_ITEM_RE.finditer(cleaned))
    if explicit:
        for m in explicit:
            val = int(m.group(1))
            if 1 <= val <= 9:
                return val
        return None
    m_exact = re.fullmatch(r"#?(\d+)", cell.strip())
    if m_exact:
        val = int(m_exact.group(1))
        return val if 1 <= val <= 9 else None
    return _extract_item_from_fragment(cell)


def parse_rotation_log(text: str) -> List[Dict[str, Any]]:
    """Parse timestamped rotation slots from ROTATION_LOG.md (tables, headings, or bullets).

    Each returned dict contains:
      - ``timestamp``: UTC-aware ``datetime`` of slot start
      - ``end_timestamp``: optional UTC-aware ``datetime`` if a range/end column is present
      - ``timestamp_str``: raw ISO-8601 start timestamp string
      - ``item``: architecture/item integer ID in ``1..9``
      - ``description``: human-readable slot summary text
    """
    slots: List[Dict[str, Any]] = []
    lines = text.splitlines()
    has_table_rows = any("|" in ln and _ISO_UTC_RE.search(ln) for ln in lines)
    table_item_col: int | None = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            table_item_col = None
            i += 1
            continue

        # Skip Markdown table divider rows (|---|---|) while preserving active table_item_col
        if _TABLE_DIVIDER_RE.fullmatch(line) and "-" in line:
            i += 1
            continue

        # Detect Markdown table header rows (pipe-delimited without an ISO timestamp)
        if "|" in line and not _ISO_UTC_RE.search(line):
            headers = [c.strip() for c in line.strip("|").split("|")]
            table_item_col = _find_table_item_col(headers)
            i += 1
            continue

        if line.startswith("#"):
            table_item_col = None

        ts_matches = _ISO_UTC_RE.findall(line)
        if not ts_matches:
            i += 1
            continue

        # When a Markdown table of rotation rows is present, ignore non-table prose/anchor/footer lines
        if has_table_rows and "|" not in line:
            i += 1
            continue

        start_str = ts_matches[0]
        start_dt = parse_utc_timestamp(start_str)
        end_dt = parse_utc_timestamp(ts_matches[1]) if len(ts_matches) > 1 else None

        item_id: int | None = None
        desc = ""

        if "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            non_ts_cells = [c for c in cells if not _ISO_UTC_RE.search(c)]

            if table_item_col is not None and 0 <= table_item_col < len(cells):
                item_id = _extract_item_from_target_cell(cells[table_item_col])
            else:
                # Headerless table row: check explicit Arch/Item/Chair labels across cells first
                explicit_vals: List[int] = []
                for cell in non_ts_cells:
                    for m in _ANY_EXPLICIT_ITEM_RE.finditer(_SLOT_PREFIX_RE.sub(" ", cell)):
                        explicit_vals.append(int(m.group(1)))
                if explicit_vals:
                    item_id = next((v for v in explicit_vals if 1 <= v <= 9), None)
                else:
                    ts_cell_idx = next((idx for idx, c in enumerate(cells) if _ISO_UTC_RE.search(c)), -1)
                    candidate_cells = cells[ts_cell_idx + 1 :] if ts_cell_idx >= 0 else non_ts_cells
                    for cell in candidate_cells:
                        m_exact = re.fullmatch(r"#?([1-9])", cell.strip())
                        if m_exact:
                            item_id = int(m_exact.group(1))
                            break
                    if item_id is None:
                        for cell in candidate_cells:
                            item_id = _extract_item_from_fragment(cell)
                            if item_id is not None:
                                break
            desc = " | ".join(c for c in non_ts_cells if c)
        else:
            is_heading = line.startswith("#")
            is_bullet = bool(_LIST_BULLET_RE.match(line))
            if not (is_heading or is_bullet) or _MUSIC_ANCHOR_RE.search(line):
                i += 1
                continue

            desc_parts = [line]
            body_lines: List[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or _ISO_UTC_RE.search(nxt) or nxt.startswith("#"):
                    break
                body_lines.append(nxt)
                desc_parts.append(nxt)
                j += 1

            combined_no_ts = _ISO_UTC_RE.sub(" ", " ".join([line, *body_lines]))
            has_slot_or_explicit = bool(
                _SLOT_PREFIX_RE.search(line)
                or _ANY_EXPLICIT_ITEM_RE.search(combined_no_ts)
            )
            if not has_slot_or_explicit:
                i += 1
                continue

            item_id = _extract_item_from_fragment(line)
            if item_id is None and not _ANY_EXPLICIT_ITEM_RE.search(_SLOT_PREFIX_RE.sub(" ", _ISO_UTC_RE.sub(" ", line))):
                for b in body_lines:
                    item_id = _extract_item_from_fragment(b)
                    if item_id is not None or _ANY_EXPLICIT_ITEM_RE.search(_SLOT_PREFIX_RE.sub(" ", _ISO_UTC_RE.sub(" ", b))):
                        break
            desc = " ".join(desc_parts)

        if item_id is not None and 1 <= item_id <= 9:
            slots.append(
                {
                    "timestamp": start_dt,
                    "end_timestamp": end_dt,
                    "timestamp_str": start_str,
                    "item": item_id,
                    "description": desc.strip(),
                }
            )
        i += 1

    return slots


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


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the Zoe monorepo root path."""
    return REPO_ROOT


@pytest.fixture()
def isolated_state_dir(tmp_path: Path) -> Path:
    """Provide a clean per-test state directory inside pytest tmp_path."""
    state = tmp_path / "zoe_state"
    state.mkdir(parents=True, exist_ok=True)
    return state


@pytest.fixture(scope="session")
def music_evidence_data() -> Dict[str, Any]:
    """Load and parse evidence/musical_math_chairs/music_evidence.json."""
    path = require_artifact("evidence/musical_math_chairs/music_evidence.json")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rotation_log_slots() -> List[Dict[str, Any]]:
    """Load and parse slots from evidence/musical_math_chairs/ROTATION_LOG.md."""
    path = require_artifact("evidence/musical_math_chairs/ROTATION_LOG.md")
    return parse_rotation_log(path.read_text(encoding="utf-8"))

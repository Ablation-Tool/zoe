"""Architecture #7: Reality-Anchored Sandbox Labs for Zoe x Antigravity.

Provides genuine, ground-truth verification labs anchored in external formal
solvers, guarded AST/subprocess execution, statistical dataset invariants, and
loopback HTTP / capability probes — never faking unavailable tools or results.

Implemented labs:
  1. **SymPy Lab** (``verify_sympy_identity``, ``verify_sympy_equation``,
     ``verify_sympy_calculus``): symbolic equivalence, exact residuals,
     derivative/integral verification, equation solving, and concrete
     counterexample extraction on false mathematical claims.
  2. **Z3 SMT Lab** (``verify_z3_constraint``, ``check_z3_invariant``):
     real Z3 solver proofs (UNSAT of negated invariants) and concrete
     counterexample model extraction when satisfiable/violated.
  3. **Monorepo / AST / Pytest / Git Lab** (``verify_python_ast_sandbox``,
     ``verify_repo_command``): guarded multi-statement Python ``def`` validation
     via ``GuardedFunctionASTSandbox`` plus bounded, read-only allowlisted
     subprocess verification (``git``, ``pytest``, ``mypy``, ``ruff``).
  4. **Dataset Invariant Lab** (``verify_dataset_invariants``): structural,
     non-NaN/finite, range, conservation/simplex, monotonicity, and statistical
     checks over tabular/numeric datasets with concrete violating row examples.
  5. **Loopback Observatory / Capability Probe Lab** (``verify_loopback_http``,
     ``probe_browser_capability``, ``probe_lean_capability``,
     ``verify_lean_proof``): real ``urllib`` inspection strictly restricted to
     loopback (``127.0.0.1``, ``localhost``, ``::1``) plus honest detection of
     ``playwright`` / Chromium / ``lean`` availability without simulating
     missing binaries (per ``docs/CONSTITUTION.md`` Articles II & III).
"""

from __future__ import annotations

import ast
import csv
from dataclasses import dataclass, field
import fractions
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

import numpy as np
import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)
import z3

from ..l4_multi_module import GuardedFunctionASTSandbox, UnsafeFunctionASTError
from ..loop import digest
from .sdk_bridge import ATTRIBUTION_TEXT, bridge_constitutional_metadata

SANDBOX_LABS_CONTRACT = "zoe-antigravity-sandbox-labs/v1"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_MAX_HTTP_BYTES = 1_048_576
_MAX_SUBPROCESS_BYTES = 65_536
_MAX_COUNTEREXAMPLE_ROWS = 5

_SYMPY_ALLOWED_NAMES: dict[str, Any] = {
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "cot": sympy.cot,
    "sec": sympy.sec,
    "csc": sympy.csc,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    "exp": sympy.exp,
    "log": sympy.log,
    "ln": sympy.log,
    "sqrt": sympy.sqrt,
    "Abs": sympy.Abs,
    "abs": sympy.Abs,
    "floor": sympy.floor,
    "ceiling": sympy.ceiling,
    "Rational": sympy.Rational,
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "pi": sympy.pi,
    "E": sympy.E,
    "e": sympy.E,
    "I": sympy.I,
    "oo": sympy.oo,
    "factorial": sympy.factorial,
    "binomial": sympy.binomial,
    "diff": sympy.diff,
    "integrate": sympy.integrate,
    "simplify": sympy.simplify,
    "expand": sympy.expand,
    "factor": sympy.factor,
    "Min": sympy.Min,
    "Max": sympy.Max,
}

_SYMPY_SAFE_AST_NODES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.UnaryOp,
    ast.BinOp,
    ast.Call,
    ast.Load,
    ast.UAdd,
    ast.USub,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.BitXor,
    ast.Tuple,
)

_GIT_READONLY_SUBCOMMANDS = frozenset(
    {
        "status",
        "rev-parse",
        "log",
        "diff",
        "show",
        "ls-files",
        "branch",
        "describe",
        "check-ignore",
    }
)

_GIT_SAFE_GLOBAL_FLAGS = frozenset(
    {
        "--no-pager",
        "-P",
        "--no-optional-locks",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
    }
)

_GIT_BRANCH_READONLY_FLAGS = frozenset(
    {
        "--list",
        "-l",
        "--show-current",
        "-a",
        "--all",
        "-r",
        "--remotes",
        "-v",
        "-vv",
        "--verbose",
        "--no-abbrev",
        "--no-color",
        "--no-column",
        "-i",
        "--ignore-case",
        "--omit-empty",
        "--merged",
        "--no-merged",
        "--contains",
        "--no-contains",
    }
)

_GIT_BRANCH_VALUE_FLAGS = frozenset(
    {
        "--contains",
        "--no-contains",
        "--merged",
        "--no-merged",
        "--points-at",
        "--sort",
        "--format",
        "--abbrev",
        "--color",
        "--column",
    }
)

_GIT_BRANCH_SAFE_SHORT_CHARS = frozenset({"l", "a", "r", "v", "i"})

_GIT_BRANCH_MUTATING_FLAGS = frozenset(
    {
        "-d",
        "-D",
        "--delete",
        "-m",
        "-M",
        "--move",
        "-c",
        "-C",
        "--copy",
        "--edit-description",
        "--set-upstream-to",
        "-u",
        "--unset-upstream",
        "--create-reflog",
        "-f",
        "--force",
        "--track",
        "--no-track",
        "--recurse-submodules",
    }
)

_RUFF_VALUE_FLAGS = frozenset(
    {
        "--config",
        "--cache-dir",
        "--output-format",
        "--target-version",
        "--exclude",
        "--extend-exclude",
        "--select",
        "--extend-select",
        "--ignore",
        "--extend-ignore",
        "--line-length",
        "--stdin-filename",
        "--per-file-ignores",
        "--extend-per-file-ignores",
        "--extension",
        "--range",
        "--files",
    }
)

_RUFF_READONLY_SUBCOMMANDS = frozenset(
    {"check", "rule", "config", "linter", "version", "help"}
)

_DISALLOWED_PYTEST_FLAGS = frozenset({"--cache-clear"})


def _validate_loopback_url(url: str) -> tuple[bool, str, urlparse.ParseResult]:
    """Validate that ``url`` is an http/https loopback URL without credentials."""
    if not isinstance(url, str) or any(
        ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url
    ):
        return (
            False,
            "Only loopback URLs (127.0.0.1, localhost, ::1) without credentials or control characters are permitted.",
            urlparse.urlparse(""),
        )
    try:
        parsed = urlparse.urlparse(url)
    except ValueError as exc:
        return False, f"Invalid URL: {exc}", urlparse.urlparse("")
    try:
        _ = parsed.port
    except ValueError as exc:
        return False, f"Invalid URL port: {exc}", parsed
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or host not in _LOOPBACK_HOSTS
        or "@" in parsed.netloc
        or "\\" in parsed.netloc
        or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in parsed.netloc)
        or parsed.username is not None
        or parsed.password is not None
    ):
        return (
            False,
            "Only loopback URLs (127.0.0.1, localhost, ::1) without credentials are permitted.",
            parsed,
        )
    return True, "", parsed


class _LoopbackRedirectBlockedError(Exception):
    """Raised when an HTTP 3xx redirect attempts to leave the allowed loopback target."""

    def __init__(self, message: str, *, target_url: str, status_code: int) -> None:
        super().__init__(message)
        self.target_url = target_url
        self.status_code = status_code


class _LoopbackSafeRedirectHandler(urlrequest.HTTPRedirectHandler):
    """Custom urllib redirect handler enforcing strict loopback/origin bounds before socket open."""

    def __init__(self, *, initial_host: str, initial_port: int) -> None:
        super().__init__()
        self.initial_host = initial_host
        self.initial_port = initial_port

    def _assert_safe_redirect(self, current_url: str, location: str, code: int, fp: Any = None) -> None:
        candidate_url = urlparse.urljoin(current_url, location)
        ok, reason, parsed_target = _validate_loopback_url(candidate_url)
        if not ok:
            if fp is not None:
                fp.close()
            raise _LoopbackRedirectBlockedError(
                f"Blocked HTTP {code} redirect to disallowed URL {candidate_url!r}: {reason}",
                target_url=candidate_url,
                status_code=code,
            )
        target_host = (parsed_target.hostname or "").lower()
        target_port = parsed_target.port or (443 if parsed_target.scheme.lower() == "https" else 80)
        if target_host != self.initial_host or target_port != self.initial_port:
            if fp is not None:
                fp.close()
            raise _LoopbackRedirectBlockedError(
                f"Blocked HTTP {code} cross-host/cross-port redirect from "
                f"{self.initial_host}:{self.initial_port} to {target_host}:{target_port}",
                target_url=candidate_url,
                status_code=code,
            )

    def http_error_302(
        self,
        req: urlrequest.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
    ) -> Any:
        loc = headers.get("location") or headers.get("uri")
        if loc:
            self._assert_safe_redirect(req.full_url, str(loc).strip(), int(code), fp=fp)
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(
        self,
        req: urlrequest.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urlrequest.Request | None:
        self._assert_safe_redirect(req.full_url, newurl, int(code), fp=fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _canonical_unique_key(val: Any) -> Any:
    """Return a hashable, NaN-aware, type-safe key for dataset uniqueness checks."""
    if val is None:
        return ("none",)
    if isinstance(val, (bool, np.bool_)):
        return ("bool", bool(val))
    if isinstance(val, (int, np.integer)):
        return ("num", int(val))
    if isinstance(val, (float, np.floating)):
        fval = float(val)
        return ("nan",) if math.isnan(fval) else ("num", fval)
    if isinstance(val, str):
        return ("str", val)
    if isinstance(val, bytes):
        return ("bytes", val)
    if isinstance(val, tuple):
        return ("tuple", tuple(_canonical_unique_key(item) for item in val))
    if isinstance(val, list):
        return ("list", tuple(_canonical_unique_key(item) for item in val))
    if isinstance(val, np.ndarray):
        return ("ndarray", tuple(_canonical_unique_key(item) for item in val.tolist()))
    if isinstance(val, Mapping):
        items = [(_canonical_unique_key(k), _canonical_unique_key(v)) for k, v in val.items()]
        items.sort(key=repr)
        return ("mapping", tuple(items))
    if isinstance(val, (set, frozenset)):
        return (type(val).__name__, frozenset(_canonical_unique_key(item) for item in val))
    try:
        hash(val)
    except TypeError:
        return ("repr", type(val).__qualname__, repr(val))
    return ("hashable", type(val).__qualname__, val)


def _json_safe(value: Any) -> Any:
    """Convert SymPy/Z3/NumPy/Path objects into JSON-serializable primitives."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        fval = float(value)
        return fval if math.isfinite(fval) else str(fval)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, fractions.Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, sympy.Basic):
        if value.is_Integer:
            return int(value)
        return str(value)
    if isinstance(value, z3.ExprRef):
        return str(value)
    return str(value)


def _default_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / "docs" / "CONSTITUTION.md").is_file():
            return parent
    return Path.cwd().resolve()


@dataclass(frozen=True)
class SandboxLabVerdict:
    """Structured reality-anchored verification verdict ready for Arch 6 Blackboard."""

    lab_name: str
    passed: bool
    ground_truth: Any
    counterexample: Any | None
    evidence_source: str
    limitations: tuple[str, ...]
    elapsed_ms: float
    claim: str = ""
    available: bool = True
    measurement_sha256: str = ""
    constitutional: dict[str, Any] = field(default_factory=bridge_constitutional_metadata)

    def __post_init__(self) -> None:
        if not self.measurement_sha256:
            payload = {
                "lab_name": self.lab_name,
                "passed": bool(self.passed),
                "available": bool(self.available),
                "claim": self.claim,
                "ground_truth": _json_safe(self.ground_truth),
                "counterexample": _json_safe(self.counterexample),
                "evidence_source": self.evidence_source,
                "limitations": list(self.limitations),
            }
            object.__setattr__(self, "measurement_sha256", digest(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": SANDBOX_LABS_CONTRACT,
            "lab_name": self.lab_name,
            "passed": bool(self.passed),
            "available": bool(self.available),
            "claim": self.claim,
            "ground_truth": _json_safe(self.ground_truth),
            "counterexample": _json_safe(self.counterexample),
            "evidence_source": self.evidence_source,
            "limitations": list(self.limitations),
            "elapsed_ms": round(float(self.elapsed_ms), 3),
            "measurement_sha256": self.measurement_sha256,
            "constitutional": dict(self.constitutional),
        }

    def to_measurement_payload(self) -> dict[str, Any]:
        """Return a canonical measurement dict suitable for Arch 6 ``post_measurement``."""
        return {
            "input": self.claim or self.lab_name,
            "method": self.evidence_source,
            "scope": self.lab_name,
            "limitations": list(self.limitations),
            "passed": bool(self.passed),
            "available": bool(self.available),
            "ground_truth": _json_safe(self.ground_truth),
            "counterexample": _json_safe(self.counterexample),
            "elapsed_ms": round(float(self.elapsed_ms), 3),
            "measurement_sha256": self.measurement_sha256,
        }


def post_verdict_to_blackboard(
    verdict: SandboxLabVerdict,
    blackboard: Any,
    *,
    promote: bool = True,
    claim_id: str | None = None,
) -> dict[str, Any]:
    """Post a ``SandboxLabVerdict`` to an Arch 6 ``EpistemicBlackboard`` cleanly.

    Adapts to ``post_measurement`` and ``promote_to_evidence`` parameter names
    using ``inspect.signature`` so both direct blackboard instances and
    compatible test doubles integrate cleanly without bypassing the firewall.
    """
    if blackboard is None:
        raise ValueError("blackboard instance is required")

    post_fn = getattr(blackboard, "post_measurement")
    sig = inspect.signature(post_fn)
    params = sig.parameters
    payload = verdict.to_measurement_payload()
    input_desc = (verdict.claim or verdict.lab_name)[:2000]
    source_agent = f"reality_sandbox_lab:{verdict.lab_name}"[:500]
    limitations_list = [lim[:1000] for lim in verdict.limitations] or [
        "No additional limitations declared."
    ]
    if sum(len(x) for x in limitations_list) > 1900:
        limitations_list = ["; ".join(limitations_list)[:1900]]

    candidate_kwargs: dict[str, Any] = {
        "source_agent": source_agent,
        "source": source_agent,
        "lab_name": verdict.lab_name,
        "input_desc": input_desc,
        "method": verdict.evidence_source[:500],
        "scope": verdict.lab_name[:1000],
        "claim": input_desc,
        "claim_id": claim_id or verdict.measurement_sha256[:16],
        "input_summary": input_desc,
        "input_data": payload,
        "payload": payload,
        "value": payload,
        "measurement": payload,
        "data": payload,
        "sampled_only": False,
        "limitations": limitations_list,
        "metadata": verdict.to_dict(),
    }
    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if has_varkw:
        call_kwargs = {
            "source_agent": source_agent,
            "source": source_agent,
            "input_desc": input_desc,
            "method": verdict.evidence_source[:500],
            "scope": verdict.lab_name[:1000],
            "limitations": limitations_list,
            "payload": payload,
            "value": payload,
        }
    else:
        call_kwargs = {k: v for k, v in candidate_kwargs.items() if k in params}

    # Fill any remaining required positional-or-keyword params deterministically.
    for pname, p in params.items():
        if p.default is inspect.Parameter.empty and p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            if pname not in call_kwargs:
                call_kwargs[pname] = payload if "data" in pname or "val" in pname else verdict.lab_name

    measurement_rec = post_fn(**call_kwargs)
    measurement_id = getattr(measurement_rec, "measurement_id", None) or getattr(
        measurement_rec, "id", None
    )
    if measurement_id is None and isinstance(measurement_rec, Mapping):
        measurement_id = measurement_rec.get("measurement_id") or measurement_rec.get("id")

    evidence_rec = None
    evidence_id = None
    if promote and hasattr(blackboard, "promote_to_evidence") and measurement_id is not None:
        prom_fn = getattr(blackboard, "promote_to_evidence")
        psig = inspect.signature(prom_fn)
        pparams = psig.parameters
        rationale = (
            f"{verdict.lab_name} verified via {verdict.evidence_source}: "
            f"passed={verdict.passed}, available={verdict.available}"
        )
        if verdict.counterexample is not None:
            rationale += f", counterexample={_json_safe(verdict.counterexample)}"
        rationale = rationale[:4000]
        ev_source_doc: dict[str, Any] = {
            "kind": "tool",
            "identifier": f"{verdict.lab_name}:{verdict.evidence_source}"[:500],
            "trust": 0.95 if verdict.available else 0.2,
            "strength": 0.95 if (verdict.available and verdict.passed) else 0.25,
        }
        prom_candidates: dict[str, Any] = {
            "measurement_id": measurement_id,
            "verifier_name": verdict.evidence_source[:500],
            "verifier": verdict.evidence_source[:500],
            "passed": bool(verdict.passed and verdict.available),
            "rationale": rationale,
            "reason": rationale,
            "evidence_source": ev_source_doc,
        }
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in pparams.values()):
            prom_kwargs = {
                "measurement_id": measurement_id,
                "verifier_name": verdict.evidence_source[:500],
                "passed": bool(verdict.passed and verdict.available),
                "rationale": rationale,
                "evidence_source": ev_source_doc,
            }
        else:
            prom_kwargs = {k: v for k, v in prom_candidates.items() if k in pparams}
        evidence_rec = prom_fn(**prom_kwargs)
        evidence_id = getattr(evidence_rec, "evidence_id", None) or getattr(
            evidence_rec, "id", None
        )
        if evidence_id is None and isinstance(evidence_rec, Mapping):
            evidence_id = evidence_rec.get("evidence_id") or evidence_rec.get("id")

    return {
        "measurement": measurement_rec,
        "measurement_id": measurement_id,
        "evidence": evidence_rec,
        "evidence_id": evidence_id,
    }


def _validate_sympy_ast(expr_str: str) -> None:
    if not isinstance(expr_str, str) or not expr_str.strip() or len(expr_str) > 2000:
        raise ValueError("SymPy expression must be a non-empty string (<= 2000 chars)")
    normalized = expr_str.strip().replace("^", "**")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid SymPy expression syntax {expr_str!r}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _SYMPY_SAFE_AST_NODES):
            raise ValueError(f"Disallowed AST node in SymPy expression: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ValueError(f"Disallowed private identifier in SymPy expression: {node.id!r}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SYMPY_ALLOWED_NAMES:
                fname = node.func.id if isinstance(node.func, ast.Name) else type(node.func).__name__
                raise ValueError(f"Disallowed SymPy function call: {fname!r}")


def safe_parse_sympy_expr(
    expr_str: str,
    *,
    symbols_map: Mapping[str, sympy.Symbol] | None = None,
) -> sympy.Expr:
    """Safely parse a mathematical expression string into a SymPy ``Expr``."""
    _validate_sympy_ast(expr_str)
    local_dict: dict[str, Any] = dict(_SYMPY_ALLOWED_NAMES)
    if symbols_map:
        local_dict.update(symbols_map)
    for sym_name in _extract_symbol_names(expr_str):
        local_dict.setdefault(sym_name, sympy.Symbol(sym_name))
    try:
        parsed = parse_expr(
            expr_str.strip(),
            local_dict=local_dict,
            global_dict={"__builtins__": {}},
            transformations=standard_transformations
            + (implicit_multiplication_application, convert_xor),
            evaluate=True,
        )
    except (sympy.SympifyError, SyntaxError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid SymPy expression {expr_str!r}: {exc}") from exc
    if not isinstance(parsed, sympy.Basic):
        try:
            parsed = sympy.sympify(parsed)
        except (sympy.SympifyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid SymPy expression {expr_str!r}: {exc}") from exc
    if not isinstance(parsed, sympy.Expr):
        raise ValueError(
            f"SymPy expression {expr_str!r} must evaluate to sympy.Expr, got {type(parsed).__name__}"
        )
    return parsed


def _validate_timeout(
    val: Any,
    *,
    name: str = "timeout",
    max_seconds: float | None = 120.0,
) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"{name} must be a finite number, got {type(val).__name__}")
    fval = float(val)
    if not math.isfinite(fval) or fval <= 0.0:
        raise ValueError(f"{name} must be finite and > 0 (got {val!r})")
    if max_seconds is not None and fval > max_seconds:
        raise ValueError(f"{name} must be in (0, {max_seconds:g}] seconds (got {val!r})")
    return fval


def _extract_symbol_names(expr_str: str) -> list[str]:
    _validate_sympy_ast(expr_str)
    normalized = expr_str.strip().replace("^", "**")
    tree = ast.parse(normalized, mode="eval")
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _SYMPY_ALLOWED_NAMES:
            if node.id not in names:
                names.append(node.id)
    return sorted(names)


def _make_symbols(
    names: Sequence[str],
    assumptions: Mapping[str, Mapping[str, bool]] | None = None,
) -> dict[str, sympy.Symbol]:
    out: dict[str, sympy.Symbol] = {}
    assump = assumptions or {}
    for name in names:
        opts = dict(assump.get(name, {}))
        out[name] = sympy.Symbol(name, **opts)
    return out


def _candidate_probe_values(sym: sympy.Symbol) -> list[Any]:
    is_pos = sym.is_positive is True
    is_nonneg = sym.is_nonnegative is True
    is_int = sym.is_integer is True
    if is_pos:
        return [1, 2, 3, sympy.Rational(1, 2), 4, 5]
    if is_nonneg:
        return [0, 1, 2, sympy.Rational(1, 2), 3]
    if is_int:
        return [1, 2, -1, 0, 3, -2]
    return [1, 2, -1, 0, sympy.Rational(1, 2), sympy.pi / 4, 3, -2]


def _find_sympy_counterexample(
    lhs_expr: sympy.Expr,
    rhs_expr: sympy.Expr,
    symbols_list: Sequence[sympy.Symbol],
) -> dict[str, Any] | None:
    """Deterministically find a concrete counterexample where ``lhs_expr != rhs_expr``."""
    diff_expr = lhs_expr - rhs_expr
    if not symbols_list:
        val_l = sympy.simplify(lhs_expr)
        val_r = sympy.simplify(rhs_expr)
        res = sympy.simplify(diff_expr)
        if res != 0:
            return {
                "assignment": {},
                "lhs_value": _json_safe(val_l),
                "rhs_value": _json_safe(val_r),
                "residual": str(res),
            }
        return None

    # First check diagonal / single-grid deterministic assignments up to 3 variables
    # and clean fallback points for higher arity.
    pools = [_candidate_probe_values(s) for s in symbols_list]
    assignments: list[dict[sympy.Symbol, Any]] = []
    if len(symbols_list) == 1:
        assignments = [{symbols_list[0]: v} for v in pools[0]]
    elif len(symbols_list) == 2:
        for v0 in pools[0][:5]:
            for v1 in pools[1][:5]:
                assignments.append({symbols_list[0]: v0, symbols_list[1]: v1})
    else:
        for idx in range(6):
            assignments.append(
                {sym: pools[i][idx % len(pools[i])] for i, sym in enumerate(symbols_list)}
            )
        # Also vary each variable independently around 1, 2, -1
        base = {sym: pools[i][0] for i, sym in enumerate(symbols_list)}
        for i, sym in enumerate(symbols_list):
            for v in pools[i][:4]:
                cand = dict(base)
                cand[sym] = v
                assignments.append(cand)

    for subs_map in assignments:
        try:
            l_val = sympy.simplify(lhs_expr.subs(subs_map))
            r_val = sympy.simplify(rhs_expr.subs(subs_map))
            if any(
                v.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo)
                for v in (l_val, r_val)
                if isinstance(v, sympy.Basic)
            ):
                continue
            res = sympy.simplify(l_val - r_val)
            if res == 0:
                continue
            # Confirm numerically as well when possible
            is_zero = res.equals(0)
            if is_zero is True:
                continue
            ce: dict[str, Any] = {
                "assignment": {s.name: _json_safe(v) for s, v in subs_map.items()},
                "lhs_value": _json_safe(l_val),
                "rhs_value": _json_safe(r_val),
                "residual": str(res),
            }
            try:
                num_res = complex(res.evalf())
                if abs(num_res.imag) < 1e-12:
                    ce["numeric_residual"] = round(float(num_res.real), 12)
            except Exception:
                pass
            return ce
        except Exception:
            continue

    return {
        "assignment": None,
        "residual": str(sympy.simplify(diff_expr)),
        "note": "Symbolic residual is non-zero; no finite sample point triggered within probe grid.",
    }


def _serialize_z3_value(val: z3.ExprRef) -> Any:
    if z3.is_true(val):
        return True
    if z3.is_false(val):
        return False
    if z3.is_int_value(val):
        return val.as_long()
    if z3.is_rational_value(val):
        frac = val.as_fraction()
        if frac.denominator == 1:
            return int(frac.numerator)
        return float(frac)
    if z3.is_bv_value(val):
        return val.as_long()
    return str(val)


def _z3_model_to_dict(model: z3.ModelRef) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for decl in sorted(model.decls(), key=lambda d: d.name()):
        if decl.arity() == 0:
            out[decl.name()] = _serialize_z3_value(model[decl])
    return out


_Z3_ALLOWED_AST = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.UnaryOp,
    ast.BinOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Load,
    ast.UAdd,
    ast.USub,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
)


def _parse_z3_expr(expr_str: str, env: Mapping[str, Any]) -> Any:
    if not isinstance(expr_str, str) or not expr_str.strip() or len(expr_str) > 2000:
        raise ValueError("Z3 constraint string must be non-empty (<= 2000 chars)")
    try:
        tree = ast.parse(expr_str.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid Z3 constraint syntax {expr_str!r}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _Z3_ALLOWED_AST):
            raise ValueError(f"Disallowed AST node in Z3 constraint: {type(node).__name__}")

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (bool, int)):
                return node.value
            if isinstance(node.value, float):
                if not math.isfinite(node.value):
                    raise ValueError(
                        f"Z3 float constant must be finite, got {node.value!r}"
                    )
                return node.value
            raise ValueError(f"Unsupported Z3 literal type: {type(node.value).__name__}")
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise ValueError(f"Undeclared Z3 symbol: {node.id!r}")
            return env[node.id]
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.Not):
                return z3.Not(operand)
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                try:
                    return left / right
                except ZeroDivisionError as exc:
                    raise ValueError("Z3 constant division or modulo by zero") from exc
            if isinstance(node.op, ast.Mod):
                try:
                    return left % right
                except ZeroDivisionError as exc:
                    raise ValueError("Z3 constant division or modulo by zero") from exc
            if isinstance(node.op, ast.Pow):
                if not isinstance(right, int) or isinstance(right, bool) or not 0 <= right <= 8:
                    raise ValueError("Z3 power exponent must be a small integer in [0, 8]")
                acc = 1
                for _ in range(right):
                    acc = acc * left
                return acc
        if isinstance(node, ast.BoolOp):
            vals = [_eval(v) for v in node.values]
            return z3.And(*vals) if isinstance(node.op, ast.And) else z3.Or(*vals)
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            clauses: list[Any] = []
            for op, comp in zip(node.ops, node.comparators):
                right = _eval(comp)
                if isinstance(op, ast.Lt):
                    clauses.append(left < right)
                elif isinstance(op, ast.LtE):
                    clauses.append(left <= right)
                elif isinstance(op, ast.Gt):
                    clauses.append(left > right)
                elif isinstance(op, ast.GtE):
                    clauses.append(left >= right)
                elif isinstance(op, ast.Eq):
                    clauses.append(left == right)
                elif isinstance(op, ast.NotEq):
                    clauses.append(left != right)
                left = right
            return clauses[0] if len(clauses) == 1 else z3.And(*clauses)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ValueError("Only positional calls to whitelisted Z3 operators are allowed")
            fname = node.func.id
            args = [_eval(a) for a in node.args]
            if fname == "And":
                return z3.And(*args)
            if fname == "Or":
                return z3.Or(*args)
            if fname == "Not" and len(args) == 1:
                return z3.Not(args[0])
            if fname == "Implies" and len(args) == 2:
                return z3.Implies(args[0], args[1])
            if fname == "If" and len(args) == 3:
                return z3.If(args[0], args[1], args[2])
            if fname == "Distinct":
                return z3.Distinct(*args)
            if fname == "Abs" and len(args) == 1:
                return z3.If(args[0] >= 0, args[0], -args[0])
            raise ValueError(f"Unsupported Z3 function: {fname!r}")
        raise ValueError(f"Unsupported Z3 AST construct: {type(node).__name__}")

    return _eval(tree)


def _build_z3_env(variables: Mapping[str, str] | None) -> dict[str, Any]:
    if variables is not None and not isinstance(variables, Mapping):
        raise ValueError(
            f"Z3 variables must be a Mapping[str, str], got {type(variables).__name__}"
        )
    env: dict[str, Any] = {}
    for name, sort_spec in (variables or {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Z3 variable name must be a non-empty string, got {name!r}")
        spec = str(sort_spec).strip()
        lower = spec.lower()
        if lower == "int":
            env[name] = z3.Int(name)
        elif lower == "real":
            env[name] = z3.Real(name)
        elif lower == "bool":
            env[name] = z3.Bool(name)
        elif lower.startswith("bitvec:"):
            width = int(lower.split(":", 1)[1])
            if not 1 <= width <= 128:
                raise ValueError(f"BitVec width out of range [1, 128]: {width}")
            env[name] = z3.BitVec(name, width)
        else:
            raise ValueError(f"Unsupported Z3 variable sort {sort_spec!r} for {name!r}")
    return env


def _normalize_z3_constraints(
    spec: Any,
    env: Mapping[str, Any],
) -> list[z3.BoolRef]:
    if callable(spec):
        built = spec(z3)
        return _normalize_z3_constraints(built, env)
    if isinstance(spec, z3.BoolRef):
        return [spec]
    if isinstance(spec, (bytes, bytearray)):
        raise ValueError(
            f"Z3 constraint specification cannot be {type(spec).__name__}; pass a string or z3.BoolRef"
        )
    if isinstance(spec, str):
        parsed = _parse_z3_expr(spec, env)
        if not isinstance(parsed, z3.BoolRef):
            raise ValueError(f"Z3 constraint must evaluate to BoolRef, got {type(parsed).__name__}")
        return [parsed]
    if isinstance(spec, Sequence):
        out: list[z3.BoolRef] = []
        for item in spec:
            out.extend(_normalize_z3_constraints(item, env))
        return out
    raise TypeError(f"Unsupported Z3 constraint specification: {type(spec).__name__}")


def _to_float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        fval = float(value)
        return fval
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _normalize_dataset(dataset: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Normalize tabular data (rows, dict of columns, ndarray, CSV/JSON file) into rows."""
    if isinstance(dataset, (str, Path)):
        path = Path(dataset).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file does not exist: {path}")
        if path.suffix.lower() == ".json":
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return _normalize_dataset(loaded)
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = [dict(r) for r in reader]
            cols = list(reader.fieldnames or (rows[0].keys() if rows else []))
            return cols, rows
        raise ValueError(f"Unsupported dataset file extension: {path.suffix!r}")

    if isinstance(dataset, np.ndarray):
        arr = np.asarray(dataset)
        if arr.ndim == 1:
            cols = ["c0"]
            rows = [{"c0": _json_safe(v)} for v in arr.tolist()]
            return cols, rows
        if arr.ndim == 2:
            cols = [f"c{i}" for i in range(arr.shape[1])]
            rows = [
                {cols[j]: _json_safe(arr[i, j]) for j in range(arr.shape[1])}
                for i in range(arr.shape[0])
            ]
            return cols, rows
        raise ValueError(f"Dataset ndarray must be 1D or 2D, got {arr.ndim}D")

    if isinstance(dataset, Mapping):
        cols = [str(k) for k in dataset.keys()]
        col_seqs: dict[str, Sequence[Any]] = {}
        for k, v in dataset.items():
            sk = str(k)
            if isinstance(v, (str, bytes, bytearray)) or not isinstance(v, Sequence):
                raise ValueError(
                    f"Columnar dataset column {sk!r} must be a non-string Sequence, got {type(v).__name__}"
                )
            col_seqs[sk] = v
        lengths = {len(v) for v in col_seqs.values()}
        if len(lengths) > 1:
            raise ValueError("Columnar dataset columns must all have equal length")
        n_rows = next(iter(lengths), 0)
        rows = [
            {col: _json_safe(col_seqs[col][idx]) for col in cols}
            for idx in range(n_rows)
        ]
        return cols, rows

    if isinstance(dataset, Sequence) and not isinstance(dataset, (bytes, bytearray)):
        items = list(dataset)
        if not items:
            return [], []
        if isinstance(items[0], Mapping):
            mapped_cols: list[str] = []
            for r_idx, row in enumerate(items):
                if not isinstance(row, Mapping):
                    raise ValueError(
                        f"Tabular mapping dataset row {r_idx} must be a Mapping, got {type(row).__name__}"
                    )
                for k in row.keys():
                    sk = str(k)
                    if sk not in mapped_cols:
                        mapped_cols.append(sk)
            rows = [{str(k): v for k, v in row.items()} for row in items]
            return mapped_cols, rows
        if isinstance(items[0], Sequence) and not isinstance(items[0], (str, bytes)):
            width = len(items[0])
            for r_idx, row in enumerate(items):
                if (
                    not isinstance(row, Sequence)
                    or isinstance(row, (str, bytes, bytearray))
                    or len(row) != width
                ):
                    raise ValueError(
                        f"Tabular sequence row {r_idx} has inconsistent width (expected {width})"
                    )
            cols = [f"c{i}" for i in range(width)]
            rows = [{cols[j]: row[j] for j in range(width)} for row in items]
            return cols, rows
        return ["c0"], [{"c0": item} for item in items]

    raise TypeError(f"Unsupported dataset type: {type(dataset).__name__}")


class RealitySandboxLab:
    """Reality-anchored verification engine across SymPy, Z3, AST/Repo, Datasets, and Loopback HTTP."""

    def __init__(
        self,
        *,
        repo_root: str | Path | None = None,
        blackboard: Any | None = None,
        default_timeout: float = 15.0,
    ) -> None:
        self.repo_root = (
            Path(repo_root).expanduser().resolve() if repo_root else _default_repo_root()
        )
        self.blackboard = blackboard
        self.default_timeout = _validate_timeout(
            default_timeout,
            name="default_timeout",
            max_seconds=120.0,
        )
        self.history: list[SandboxLabVerdict] = []

    def _record(
        self,
        verdict: SandboxLabVerdict,
        *,
        post_to_blackboard: bool = False,
        blackboard: Any | None = None,
    ) -> SandboxLabVerdict:
        self.history.append(verdict)
        target_bb = blackboard if blackboard is not None else (
            self.blackboard if post_to_blackboard else None
        )
        if target_bb is not None:
            post_verdict_to_blackboard(verdict, target_bb, promote=True)
        return verdict

    def record_to_blackboard(
        self,
        verdict: SandboxLabVerdict,
        *,
        blackboard: Any | None = None,
        promote: bool = True,
        claim_id: str | None = None,
    ) -> dict[str, Any]:
        target = blackboard if blackboard is not None else self.blackboard
        return post_verdict_to_blackboard(
            verdict, target, promote=promote, claim_id=claim_id
        )

    # ------------------------------------------------------------------
    # Lab 1: SymPy Lab
    # ------------------------------------------------------------------

    def verify_sympy_identity(
        self,
        lhs: str,
        rhs: str,
        *,
        variables: Sequence[str] | None = None,
        assumptions: Mapping[str, Mapping[str, bool]] | None = None,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify symbolic algebraic/trigonometric identity ``lhs == rhs`` using SymPy."""
        t0 = time.perf_counter()
        sym_names: list[str] = []
        if variables is not None:
            if isinstance(variables, (str, bytes, bytearray)) or not isinstance(variables, Iterable):
                raise ValueError(
                    f"SymPy variables must be a sequence of identifier strings, got {type(variables).__name__}"
                )
            for var_name in variables:
                if (
                    not isinstance(var_name, str)
                    or not var_name.strip().isidentifier()
                    or var_name.strip().startswith("_")
                ):
                    raise ValueError(f"Invalid SymPy variable name: {var_name!r}")
                cleaned_var = var_name.strip()
                if cleaned_var not in sym_names:
                    sym_names.append(cleaned_var)
        for expr_text in (lhs, rhs):
            for name in _extract_symbol_names(expr_text):
                if name not in sym_names:
                    sym_names.append(name)
        sym_map = _make_symbols(sym_names, assumptions=assumptions)
        lhs_expr = safe_parse_sympy_expr(lhs, symbols_map=sym_map)
        rhs_expr = safe_parse_sympy_expr(rhs, symbols_map=sym_map)

        raw_diff = lhs_expr - rhs_expr
        expanded = sympy.expand(raw_diff)
        simplified = sympy.simplify(expanded)
        if simplified != 0:
            simplified = sympy.trigsimp(simplified)

        is_zero = simplified == 0 or expanded == 0
        if not is_zero:
            eq_check = simplified.equals(0)
            if eq_check is True:
                is_zero = True

        counterexample = None
        if not is_zero:
            free_syms = sorted(
                (lhs_expr.free_symbols | rhs_expr.free_symbols),
                key=lambda s: s.name,
            )
            counterexample = _find_sympy_counterexample(lhs_expr, rhs_expr, free_syms)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        limitations: list[str] = [
            f"Symbolic domain governed by declared assumptions: {dict(assumptions or {}) or 'default complex/generic symbols'}."
        ]
        if not is_zero and counterexample and counterexample.get("assignment") is None:
            limitations.append("Symbolic difference is non-zero; counterexample grid did not hit a finite point.")

        verdict = SandboxLabVerdict(
            lab_name="sympy_lab",
            passed=bool(is_zero),
            claim=claim or f"{lhs} == {rhs}",
            ground_truth={
                "lhs": str(lhs_expr),
                "rhs": str(rhs_expr),
                "simplified_residual": str(simplified),
                "symbolic_equivalent": bool(is_zero),
                "symbols": sorted(sym_map.keys()),
            },
            counterexample=counterexample,
            evidence_source=f"sympy=={sympy.__version__}",
            limitations=tuple(limitations),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def verify_sympy_equation(
        self,
        equation: str,
        rhs: str | None = None,
        *,
        solve_for: str | None = None,
        candidate_solutions: Sequence[Any] | None = None,
        wrt: str = "x",
        verify_derivative_of: str | None = None,
        verify_integral_of: str | None = None,
        assumptions: Mapping[str, Mapping[str, bool]] | None = None,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify equations, candidate roots, symbolic derivatives, or antiderivatives in SymPy."""
        t0 = time.perf_counter()
        if verify_derivative_of is not None and verify_integral_of is not None:
            raise ValueError("Specify at most one of verify_derivative_of or verify_integral_of")

        if verify_derivative_of is not None:
            return self.verify_sympy_calculus(
                "diff",
                verify_derivative_of,
                equation,
                variable=wrt,
                assumptions=assumptions,
                claim=claim,
                post_to_blackboard=post_to_blackboard,
            )

        if verify_integral_of is not None:
            return self.verify_sympy_calculus(
                "integrate",
                verify_integral_of,
                equation,
                variable=wrt,
                assumptions=assumptions,
                claim=claim,
                post_to_blackboard=post_to_blackboard,
            )

        if not isinstance(equation, str):
            raise ValueError("SymPy equation must be a non-empty string")
        if solve_for is not None:
            if (
                not isinstance(solve_for, str)
                or not solve_for.strip().isidentifier()
                or solve_for.strip().startswith("_")
            ):
                raise ValueError(f"Invalid solve_for variable: {solve_for!r}")
            solve_for = solve_for.strip()
        lhs_str = equation
        rhs_str = rhs
        if rhs_str is None:
            if "==" in equation:
                lhs_str, rhs_str = equation.split("==", 1)
            elif "=" in equation:
                lhs_str, rhs_str = equation.split("=", 1)
            else:
                rhs_str = "0"
        elif not isinstance(rhs_str, str):
            raise ValueError("SymPy equation rhs must be a non-empty string")

        if solve_for is None and candidate_solutions is None:
            return self.verify_sympy_identity(
                lhs_str,
                rhs_str,
                assumptions=assumptions,
                claim=claim or f"{lhs_str.strip()} == {rhs_str.strip()}",
                post_to_blackboard=post_to_blackboard,
            )

        sym_names = _extract_symbol_names(lhs_str) + _extract_symbol_names(rhs_str)
        if solve_for and solve_for not in sym_names:
            sym_names.append(solve_for)
        sym_map = _make_symbols(list(dict.fromkeys(sym_names)), assumptions=assumptions)
        lhs_expr = safe_parse_sympy_expr(lhs_str, symbols_map=sym_map)
        rhs_expr = safe_parse_sympy_expr(rhs_str, symbols_map=sym_map)
        target_name = solve_for or (next(iter(sym_map.keys()), "x"))
        target_sym = sym_map.get(target_name) or sympy.Symbol(target_name)

        exact_solutions = sympy.solve(sympy.Eq(lhs_expr, rhs_expr), target_sym)
        diff_expr = lhs_expr - rhs_expr

        counterexample: dict[str, Any] | None = None
        passed = True
        checked_candidates: list[dict[str, Any]] = []
        if candidate_solutions is not None:
            if isinstance(candidate_solutions, (str, bytes, bytearray)) or not isinstance(
                candidate_solutions, Iterable
            ):
                raise ValueError(
                    f"candidate_solutions must be an iterable of candidate values, got {type(candidate_solutions).__name__}"
                )
            cand_list = list(candidate_solutions)
            if not cand_list:
                passed = False
                counterexample = {
                    "reason": "candidate_solutions must not be empty",
                    "expected_solutions": [_json_safe(s) for s in exact_solutions],
                }
            for cand in cand_list:
                if isinstance(cand, (bool, np.bool_)):
                    cand_bool = bool(cand)
                    checked_candidates.append(
                        {
                            "candidate": cand_bool,
                            "residual": "invalid_bool_candidate",
                            "valid": False,
                        }
                    )
                    passed = False
                    if counterexample is None:
                        counterexample = {
                            "variable": target_sym.name,
                            "invalid_candidate": cand_bool,
                            "reason": "boolean candidate is not a valid numeric/symbolic solution",
                            "expected_solutions": [_json_safe(s) for s in exact_solutions],
                        }
                    continue
                if (
                    isinstance(cand, (int, float, np.integer, np.floating))
                    and not math.isfinite(float(cand))
                ) or (
                    isinstance(cand, (complex, np.complexfloating))
                    and not (math.isfinite(float(cand.real)) and math.isfinite(float(cand.imag)))
                ):
                    checked_candidates.append(
                        {
                            "candidate": str(cand),
                            "residual": "non_finite_candidate",
                            "valid": False,
                        }
                    )
                    passed = False
                    if counterexample is None:
                        counterexample = {
                            "variable": target_sym.name,
                            "invalid_candidate": str(cand),
                            "reason": "non-finite candidate is not a valid solution",
                            "expected_solutions": [_json_safe(s) for s in exact_solutions],
                        }
                    continue
                try:
                    if isinstance(cand, str):
                        _validate_sympy_ast(cand)
                        extra_names = [n for n in _extract_symbol_names(cand) if n not in sym_map]
                        cand_sym_map = (
                            {**sym_map, **_make_symbols(extra_names, assumptions=assumptions)}
                            if extra_names
                            else sym_map
                        )
                        cand_expr = safe_parse_sympy_expr(cand, symbols_map=cand_sym_map)
                    else:
                        cand_expr = sympy.sympify(cand)
                except (sympy.SympifyError, ValueError, TypeError) as exc:
                    checked_candidates.append(
                        {
                            "candidate": _json_safe(cand),
                            "residual": f"invalid_candidate: {exc}",
                            "valid": False,
                        }
                    )
                    passed = False
                    if counterexample is None:
                        counterexample = {
                            "variable": target_sym.name,
                            "invalid_candidate": _json_safe(cand),
                            "reason": f"invalid or non-Expr candidate: {exc}",
                            "expected_solutions": [_json_safe(s) for s in exact_solutions],
                        }
                    continue
                if (
                    not isinstance(cand_expr, sympy.Expr)
                    or cand_expr.has(sympy.nan, sympy.oo, -sympy.oo, sympy.zoo)
                    or cand_expr.is_finite is False
                ):
                    checked_candidates.append(
                        {
                            "candidate": _json_safe(cand_expr),
                            "residual": "invalid_or_nonfinite_candidate",
                            "valid": False,
                        }
                    )
                    passed = False
                    if counterexample is None:
                        counterexample = {
                            "variable": target_sym.name,
                            "invalid_candidate": _json_safe(cand_expr),
                            "reason": "non-Expr, boolean, or non-finite candidate is not a valid solution",
                            "expected_solutions": [_json_safe(s) for s in exact_solutions],
                        }
                    continue
                residual = sympy.simplify(diff_expr.subs(target_sym, cand_expr))
                finite_res = (
                    isinstance(residual, sympy.Expr)
                    and not residual.has(sympy.nan, sympy.oo, -sympy.oo, sympy.zoo)
                )
                ok = bool(finite_res and (residual == 0 or residual.equals(0) is True))
                checked_candidates.append(
                    {
                        "candidate": _json_safe(cand_expr),
                        "residual": str(residual),
                        "valid": ok,
                    }
                )
                if not ok and counterexample is None:
                    passed = False
                    counterexample = {
                        "variable": target_sym.name,
                        "invalid_candidate": _json_safe(cand_expr),
                        "residual": str(residual),
                        "expected_solutions": [_json_safe(s) for s in exact_solutions],
                    }
        else:
            # Verify each solved root substitutes back to 0; accept tautological identities
            # where diff_expr simplifies identically to 0, otherwise fail closed.
            if not exact_solutions:
                simplified_diff = sympy.simplify(diff_expr)
                trig_diff = sympy.trigsimp(diff_expr)
                is_identity = bool(
                    simplified_diff == 0
                    or trig_diff == 0
                    or simplified_diff.equals(0) is True
                )
                if not is_identity:
                    passed = False
                    counterexample = {
                        "reason": f"No symbolic solution found for {target_sym.name}",
                        "residual": str(simplified_diff),
                    }
            else:
                for sol in exact_solutions:
                    residual = sympy.simplify(diff_expr.subs(target_sym, sol))
                    if not (residual == 0 or residual.equals(0) is True):
                        passed = False
                        counterexample = {
                            "variable": target_sym.name,
                            "solution": _json_safe(sol),
                            "residual": str(residual),
                        }
                        break

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="sympy_lab",
            passed=passed,
            claim=claim or f"solve({lhs_str.strip()} = {rhs_str.strip()}, {target_sym.name})",
            ground_truth={
                "lhs": str(lhs_expr),
                "rhs": str(rhs_expr),
                "solve_for": target_sym.name,
                "exact_solutions": [_json_safe(s) for s in exact_solutions],
                "checked_candidates": checked_candidates,
            },
            counterexample=counterexample,
            evidence_source=f"sympy=={sympy.__version__}",
            limitations=(
                "sympy.solve returns exact roots over SymPy's default algebraic/elementary solver.",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def verify_sympy_calculus(
        self,
        operation: str,
        expression: str,
        expected: str,
        *,
        variable: str = "x",
        assumptions: Mapping[str, Mapping[str, bool]] | None = None,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify symbolic differentiation (``diff``) or antiderivative (``integrate``)."""
        t0 = time.perf_counter()
        if not isinstance(operation, str):
            raise ValueError(f"Unsupported calculus operation: {operation!r}")
        op = operation.strip().lower()
        if op not in {"diff", "derivative", "integrate", "integral"}:
            raise ValueError(f"Unsupported calculus operation: {operation!r}")
        if not isinstance(variable, str) or not variable.strip().isidentifier() or variable.strip().startswith("_"):
            raise ValueError(f"Invalid calculus variable: {variable!r}")
        var_name = variable.strip()

        sym_names = [var_name] + _extract_symbol_names(expression) + _extract_symbol_names(expected)
        sym_map = _make_symbols(list(dict.fromkeys(sym_names)), assumptions=assumptions)
        var = sym_map[var_name]
        base_expr = safe_parse_sympy_expr(expression, symbols_map=sym_map)
        claimed_expr = safe_parse_sympy_expr(expected, symbols_map=sym_map)

        if op in {"diff", "derivative"}:
            exact = sympy.simplify(sympy.diff(base_expr, var))
            residual = sympy.simplify(exact - claimed_expr)
            lhs_check, rhs_check = exact, claimed_expr
            op_label = "derivative"
            ground_extra: dict[str, Any] = {"exact_derivative": str(exact)}
        else:
            # Verify antiderivative by differentiating the claimed result and comparing with integrand
            deriv_of_claimed = sympy.simplify(sympy.diff(claimed_expr, var))
            exact_antideriv = sympy.integrate(base_expr, var)
            residual = sympy.simplify(deriv_of_claimed - base_expr)
            lhs_check, rhs_check = deriv_of_claimed, base_expr
            op_label = "integral"
            ground_extra = {
                "integrand": str(base_expr),
                "d_dx_claimed": str(deriv_of_claimed),
                "sympy_antiderivative": str(exact_antideriv),
            }

        ok = bool(residual == 0 or residual.equals(0) is True)
        counterexample = None
        if not ok:
            free_syms = sorted(
                (lhs_check.free_symbols | rhs_check.free_symbols),
                key=lambda s: s.name,
            )
            counterexample = _find_sympy_counterexample(lhs_check, rhs_check, free_syms)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="sympy_lab",
            passed=ok,
            claim=claim or f"{op_label}({expression}, {variable}) == {expected}",
            ground_truth={
                "operation": op_label,
                "variable": variable,
                "expression": str(base_expr),
                "claimed": str(claimed_expr),
                "simplified_residual": str(residual),
                **ground_extra,
            },
            counterexample=counterexample,
            evidence_source=f"sympy=={sympy.__version__}",
            limitations=(
                "Antiderivatives are verified up to an arbitrary additive constant via d/dx(claimed) == integrand.",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    # ------------------------------------------------------------------
    # Lab 2: Z3 SMT Lab
    # ------------------------------------------------------------------

    def verify_z3_constraint(
        self,
        constraints: Any,
        *,
        variables: Mapping[str, str] | None = None,
        expect_sat: bool = True,
        timeout_ms: int = 5000,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Check satisfiability or unsatisfiability of constraints with Z3."""
        eff_timeout_ms = max(1, int(_validate_timeout(timeout_ms, name="timeout_ms", max_seconds=None)))
        t0 = time.perf_counter()
        try:
            env = _build_z3_env(variables)
            clauses = _normalize_z3_constraints(constraints, env)
            solver = z3.Solver()
            solver.set("timeout", eff_timeout_ms)
            for clause in clauses:
                solver.add(clause)

            status = solver.check()
        except z3.Z3Exception as exc:
            raise ValueError(f"Invalid Z3 constraint or variable sort: {exc}") from exc
        status_str = str(status)
        model_dict = _z3_model_to_dict(solver.model()) if status == z3.sat else None
        counterexample: dict[str, Any] | None

        if status == z3.unknown:
            passed = False
            counterexample = None
            limitations = (
                f"Z3 returned unknown ({solver.reason_unknown()}) within timeout={timeout_ms}ms.",
            )
        elif expect_sat:
            passed = status == z3.sat
            counterexample = (
                None
                if passed
                else {"reason": "Constraints are UNSAT; no satisfying assignment exists."}
            )
            limitations = (
                f"Z3 solver timeout={timeout_ms}ms; satisfiability verified over declared sorts.",
            )
        else:
            passed = status == z3.unsat
            counterexample = (
                {"satisfying_counterexample": model_dict} if status == z3.sat else None
            )
            limitations = (
                f"Z3 solver timeout={timeout_ms}ms; unsatisfiability checked over declared sorts.",
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="z3_smt_lab",
            passed=passed,
            claim=claim or ("Z3 satisfiability check" if expect_sat else "Z3 unsatisfiability check"),
            ground_truth={
                "status": status_str,
                "expect_sat": expect_sat,
                "clause_count": len(clauses),
                "model": model_dict,
                "z3_version": z3.get_version_string(),
            },
            counterexample=counterexample,
            evidence_source=f"z3-solver=={z3.get_version_string()}",
            limitations=limitations,
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def check_z3_invariant(
        self,
        assumptions: Any,
        invariant: Any,
        *,
        variables: Mapping[str, str] | None = None,
        timeout_ms: int = 5000,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Prove ``assumptions => invariant`` via UNSAT of ``assumptions & Not(invariant)``."""
        eff_timeout_ms = max(1, int(_validate_timeout(timeout_ms, name="timeout_ms", max_seconds=None)))
        t0 = time.perf_counter()
        try:
            env = _build_z3_env(variables)
            assumption_clauses = _normalize_z3_constraints(assumptions, env) if assumptions else []
            invariant_clauses = _normalize_z3_constraints(invariant, env)
            if not invariant_clauses:
                raise ValueError("Invariant cannot be empty")
            combined_invariant = (
                invariant_clauses[0]
                if len(invariant_clauses) == 1
                else z3.And(*invariant_clauses)
            )

            solver = z3.Solver()
            solver.set("timeout", eff_timeout_ms)
            for clause in assumption_clauses:
                solver.add(clause)
            solver.add(z3.Not(combined_invariant))

            status = solver.check()
        except z3.Z3Exception as exc:
            raise ValueError(f"Invalid Z3 invariant or variable sort: {exc}") from exc
        status_str = str(status)
        if status == z3.unsat:
            passed = True
            counterexample = None
            limitations = (
                f"Universal invariant proven within Z3 timeout={timeout_ms}ms for declared variable sorts.",
            )
            gt_model = None
        elif status == z3.sat:
            passed = False
            gt_model = _z3_model_to_dict(solver.model())
            counterexample = {
                "model": gt_model,
                "violated_invariant": str(combined_invariant),
            }
            limitations = (
                f"Z3 found concrete counterexample violating invariant within timeout={timeout_ms}ms.",
            )
        else:
            passed = False
            gt_model = None
            counterexample = None
            limitations = (
                f"Z3 returned unknown ({solver.reason_unknown()}) within timeout={timeout_ms}ms.",
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="z3_smt_lab",
            passed=passed,
            claim=claim or f"invariant({combined_invariant})",
            ground_truth={
                "status": status_str,
                "invariant_proven": status == z3.unsat,
                "assumption_count": len(assumption_clauses),
                "invariant": str(combined_invariant),
                "counterexample_model": gt_model,
                "z3_version": z3.get_version_string(),
            },
            counterexample=counterexample,
            evidence_source=f"z3-solver=={z3.get_version_string()}",
            limitations=limitations,
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    # ------------------------------------------------------------------
    # Lab 3: Monorepo / AST / Pytest / Git Lab
    # ------------------------------------------------------------------

    def verify_python_ast_sandbox(
        self,
        source: str,
        *,
        expected_name: str | None = None,
        expected_args: Sequence[str] | None = None,
        test_cases: Sequence[tuple[Mapping[str, Any], Any]] | None = None,
        expected_blocked: bool = False,
        atol: float = 1e-9,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Validate and optionally execute a pure ``def`` function inside ``GuardedFunctionASTSandbox``."""
        if (
            isinstance(atol, (bool, np.bool_))
            or not isinstance(atol, (int, float, np.integer, np.floating))
        ):
            raise ValueError(f"atol must be a finite non-negative number, got {atol!r}")
        atol_val = float(atol)
        if not math.isfinite(atol_val) or atol_val < 0.0:
            raise ValueError(f"atol must be a finite non-negative number, got {atol!r}")

        t0 = time.perf_counter()
        try:
            metrics = GuardedFunctionASTSandbox.structural_metrics(source)
            GuardedFunctionASTSandbox.validate(
                source,
                expected_name=expected_name,
                expected_args=expected_args,
            )
        except UnsafeFunctionASTError as err:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if expected_blocked:
                verdict = SandboxLabVerdict(
                    lab_name="ast_sandbox_lab",
                    passed=True,
                    claim=claim or "Hostile AST probe rejected by GuardedFunctionASTSandbox",
                    ground_truth={"blocked": True, "error": str(err)},
                    counterexample=None,
                    evidence_source="GuardedFunctionASTSandbox",
                    limitations=("Pure-Python AST subset only; no imports, loops, or attribute access.",),
                    elapsed_ms=elapsed_ms,
                )
            else:
                verdict = SandboxLabVerdict(
                    lab_name="ast_sandbox_lab",
                    passed=False,
                    claim=claim or "GuardedFunctionASTSandbox validation",
                    ground_truth={"blocked": True, "error": str(err)},
                    counterexample={"ast_rejection": str(err)},
                    evidence_source="GuardedFunctionASTSandbox",
                    limitations=("Pure-Python AST subset only; no imports, loops, or attribute access.",),
                    elapsed_ms=elapsed_ms,
                )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        if expected_blocked:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="ast_sandbox_lab",
                passed=False,
                claim=claim or "Expected hostile AST probe to be blocked",
                ground_truth={"blocked": False, "ast_metrics": metrics},
                counterexample={"reason": "Source unexpectedly passed GuardedFunctionASTSandbox"},
                evidence_source="GuardedFunctionASTSandbox",
                limitations=("Pure-Python AST subset only.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        case_results: list[dict[str, Any]] = []
        counterexample = None
        passed = True
        if test_cases:
            fn = GuardedFunctionASTSandbox.compile(
                source,
                expected_name=expected_name,
                expected_args=expected_args,
            )
            for idx, (inputs, expected_out) in enumerate(test_cases):
                safe_inputs = _json_safe(dict(inputs)) if isinstance(inputs, Mapping) else _json_safe(inputs)
                try:
                    actual = fn(dict(inputs))
                except Exception as exc:  # noqa: BLE001
                    err_repr = f"{type(exc).__name__}: {exc}"
                    case_results.append(
                        {
                            "case_index": idx,
                            "inputs": safe_inputs,
                            "expected": _json_safe(expected_out),
                            "actual": None,
                            "error": err_repr,
                            "matched": False,
                        }
                    )
                    if counterexample is None:
                        passed = False
                        counterexample = {
                            "case_index": idx,
                            "inputs": safe_inputs,
                            "expected": _json_safe(expected_out),
                            "actual": None,
                            "error": err_repr,
                        }
                    continue

                if isinstance(expected_out, (bool, np.bool_)) or isinstance(actual, (bool, np.bool_)):
                    ok = (
                        isinstance(expected_out, (bool, np.bool_))
                        and isinstance(actual, (bool, np.bool_))
                        and bool(actual) is bool(expected_out)
                    )
                elif isinstance(expected_out, (int, float, np.integer, np.floating)) and isinstance(
                    actual, (int, float, np.integer, np.floating)
                ):
                    ok = math.isclose(float(actual), float(expected_out), rel_tol=1e-9, abs_tol=atol_val)
                else:
                    ok = actual == expected_out
                case_results.append(
                    {
                        "case_index": idx,
                        "inputs": safe_inputs,
                        "expected": _json_safe(expected_out),
                        "actual": _json_safe(actual),
                        "matched": ok,
                    }
                )
                if not ok and counterexample is None:
                    passed = False
                    counterexample = {
                        "case_index": idx,
                        "inputs": safe_inputs,
                        "expected": _json_safe(expected_out),
                        "actual": _json_safe(actual),
                    }

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="ast_sandbox_lab",
            passed=passed,
            claim=claim or f"Guarded AST verification for {metrics['function_name']}",
            ground_truth={
                "blocked": False,
                "ast_metrics": metrics,
                "test_cases_run": len(case_results),
                "test_results": case_results,
            },
            counterexample=counterexample,
            evidence_source="GuardedFunctionASTSandbox",
            limitations=(
                "Execution is bounded to pure arithmetic/conditional AST expressions over supplied test_cases.",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def _validate_repo_argv(self, argv: Sequence[str]) -> tuple[list[str], str | None]:
        if not isinstance(argv, (list, tuple)) or not argv or any(
            not isinstance(item, str) or not item for item in argv
        ):
            return [], "argv must be a non-empty sequence of non-empty strings"
        cmd_list = list(argv)
        exe_name = Path(cmd_list[0]).name

        if exe_name == "git":
            subcmd = None
            idx = 1
            while idx < len(cmd_list):
                tok = cmd_list[idx]
                if tok.startswith("-"):
                    if tok not in _GIT_SAFE_GLOBAL_FLAGS:
                        return [], f"git flag {tok!r} is disallowed in sandboxed repo checks"
                    idx += 1
                    continue
                subcmd = tok
                break
            if subcmd not in _GIT_READONLY_SUBCOMMANDS:
                return [], f"git subcommand {subcmd!r} is not in read-only allowlist"

            sub_args = cmd_list[idx + 1 :]
            if subcmd == "branch":
                branch_err = self._validate_git_branch_args(sub_args)
                if branch_err is not None:
                    return [], branch_err
                return cmd_list, None

            for sub_tok in sub_args:
                if sub_tok == "--":
                    break
                if (
                    sub_tok in ("--output", "--ext-diff", "--exec", "--upload-pack")
                    or sub_tok.startswith(("--output=", "--exec=", "--upload-pack="))
                    or (subcmd != "ls-files" and (sub_tok == "-o" or sub_tok.startswith("-o")))
                ):
                    return [], f"git {subcmd} flag {sub_tok!r} is disallowed in sandboxed repo checks"
            return cmd_list, None

        if exe_name == "pytest":
            if any(flag in _DISALLOWED_PYTEST_FLAGS for flag in cmd_list[1:]):
                return [], "disallowed pytest flag in sandboxed repo check"
            return cmd_list, None

        if exe_name in ("mypy", "ruff"):
            if exe_name == "ruff":
                ruff_err = self._validate_ruff_args(cmd_list[1:])
                if ruff_err is not None:
                    return [], ruff_err
            return cmd_list, None

        if exe_name.startswith("python"):
            if len(cmd_list) >= 3 and cmd_list[1] == "-m" and cmd_list[2] in ("pytest", "mypy", "ruff"):
                if cmd_list[2] == "ruff":
                    ruff_err = self._validate_ruff_args(cmd_list[3:])
                    if ruff_err is not None:
                        return [], ruff_err
                if cmd_list[2] == "pytest" and any(
                    f in _DISALLOWED_PYTEST_FLAGS for f in cmd_list[3:]
                ):
                    return [], "disallowed pytest flag in sandboxed repo check"
                return cmd_list, None
            return [], "python commands are restricted to `-m pytest|mypy|ruff`"

        return [], f"executable {exe_name!r} is not in the read-only sandbox allowlist"

    @staticmethod
    def _validate_ruff_args(ruff_args: Sequence[str]) -> str | None:
        """Allow strictly read-only ruff invocations (block --fix, --add-noqa, -o/--output-file, and mutating format)."""
        if any(
            tok in ("--fix", "--fix-only", "--add-noqa")
            or tok.startswith(("--fix=", "--fix-only=", "--add-noqa="))
            for tok in ruff_args
        ):
            return "ruff --fix/--fix-only/--add-noqa is disallowed in read-only sandbox"
        flags_before_sep: list[str] = []
        positional_before_sep: list[str] = []
        subcmd: str | None = None
        i = 0
        while i < len(ruff_args):
            tok = ruff_args[i]
            if tok == "--":
                break
            if tok.startswith("-"):
                if (
                    tok in ("-o", "--output-file")
                    or tok.startswith(("--output-file=", "-o"))
                ):
                    return "ruff -o/--output-file is disallowed in read-only sandbox"
                flags_before_sep.append(tok)
                if "=" not in tok and tok in _RUFF_VALUE_FLAGS and i + 1 < len(ruff_args):
                    i += 2
                    continue
            else:
                positional_before_sep.append(tok)
                if subcmd is None:
                    subcmd = tok
            i += 1
        has_readonly_format_flag = any(f in ("--check", "--diff") for f in flags_before_sep)
        if not has_readonly_format_flag:
            if subcmd == "format":
                return "ruff format without --check or --diff is disallowed in read-only sandbox"
            if subcmd not in _RUFF_READONLY_SUBCOMMANDS and "format" in positional_before_sep:
                return "ruff format without --check or --diff is disallowed in read-only sandbox"
        return None

    @staticmethod
    def _validate_git_branch_args(sub_args: Sequence[str]) -> str | None:
        """Allow strictly read-only inspection flags for ``git branch``."""
        has_list_flag = False
        saw_double_dash = False
        i = 0
        while i < len(sub_args):
            tok = sub_args[i]
            if saw_double_dash:
                if not has_list_flag:
                    return "git branch positional branch-creation args require --list / -l"
                i += 1
                continue
            if tok == "--":
                saw_double_dash = True
                i += 1
                continue
            if tok.startswith("-"):
                flag_head = tok.split("=", 1)[0]
                if (
                    flag_head in _GIT_BRANCH_MUTATING_FLAGS
                    or tok.startswith(("-u", "-d", "-D", "-m", "-M", "-c", "-C", "-f"))
                ):
                    return f"git branch mutating flag {tok!r} is disallowed in read-only sandbox"

                if "=" in tok:
                    if flag_head not in _GIT_BRANCH_VALUE_FLAGS:
                        return f"git branch flag {tok!r} is not in read-only allowlist"
                    i += 1
                    continue

                if tok in _GIT_BRANCH_READONLY_FLAGS:
                    if tok in ("--list", "-l"):
                        has_list_flag = True
                    if tok in _GIT_BRANCH_VALUE_FLAGS and i + 1 < len(sub_args) and not sub_args[i + 1].startswith("-"):
                        i += 2
                        continue
                    i += 1
                    continue

                if tok in _GIT_BRANCH_VALUE_FLAGS:
                    if i + 1 >= len(sub_args) or sub_args[i + 1].startswith("-"):
                        return f"git branch flag {tok!r} requires a non-flag argument"
                    i += 2
                    continue

                if tok.startswith("-") and not tok.startswith("--") and len(tok) > 2:
                    short_chars = tok[1:]
                    if all(ch in _GIT_BRANCH_SAFE_SHORT_CHARS for ch in short_chars):
                        if "l" in short_chars:
                            has_list_flag = True
                        i += 1
                        continue

                return f"git branch flag {tok!r} is not in read-only allowlist"

            if not has_list_flag:
                return f"git branch positional argument {tok!r} is disallowed without --list / -l"
            i += 1
        return None

    def verify_repo_command(
        self,
        argv: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        allow_nonzero: bool = False,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Execute a strictly allowlisted, read-only repo/git/test command in a bounded subprocess."""
        t0 = time.perf_counter()
        eff_timeout = _validate_timeout(
            timeout if timeout is not None else self.default_timeout,
            name="timeout",
            max_seconds=120.0,
        )

        target_cwd = (
            Path(cwd).expanduser().resolve() if cwd is not None else self.repo_root
        )
        if not target_cwd.is_dir():
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="repo_command_lab",
                passed=False,
                claim=claim or f"Run {list(argv)}",
                ground_truth={"executed": False, "cwd": str(target_cwd)},
                counterexample={"rejected_reason": f"cwd does not exist: {target_cwd}"},
                evidence_source="subprocess_readonly_sandbox",
                limitations=("Subprocess was not executed because cwd was invalid.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        cmd_list, rejection = self._validate_repo_argv(argv)
        if rejection is not None:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="repo_command_lab",
                passed=False,
                claim=claim or f"Validate repo command {list(argv)}",
                ground_truth={"executed": False, "argv": list(argv)},
                counterexample={"rejected_reason": rejection},
                evidence_source="subprocess_readonly_sandbox",
                limitations=("Blocked by read-only command allowlist prior to spawning.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["GIT_OPTIONAL_LOCKS"] = "0"

        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=target_cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except (FileNotFoundError, OSError) as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            missing_exe = cmd_list[0]
            verdict = SandboxLabVerdict(
                lab_name="repo_command_lab",
                passed=False,
                available=False,
                claim=claim or " ".join(cmd_list),
                ground_truth={
                    "executed": False,
                    "argv": cmd_list,
                    "cwd": str(target_cwd),
                    "error": str(exc),
                },
                counterexample={
                    "missing_binary": missing_exe,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                evidence_source=f"subprocess:{Path(missing_exe).name}",
                limitations=(f"Executable {missing_exe!r} could not be launched: {exc}.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)
        try:
            stdout_b, stderr_b = proc.communicate(timeout=eff_timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="repo_command_lab",
                passed=False,
                claim=claim or " ".join(cmd_list),
                ground_truth={"executed": True, "timed_out": True, "timeout_s": eff_timeout},
                counterexample={"timeout_seconds": eff_timeout, "argv": cmd_list},
                evidence_source=f"subprocess:{Path(cmd_list[0]).name}",
                limitations=(f"Process group killed after timeout={eff_timeout}s.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        stdout_s = stdout_b[:_MAX_SUBPROCESS_BYTES].decode("utf-8", errors="replace")
        stderr_s = stderr_b[:_MAX_SUBPROCESS_BYTES].decode("utf-8", errors="replace")
        passed = allow_nonzero or (proc.returncode == 0)
        counterexample = (
            None
            if passed
            else {
                "returncode": proc.returncode,
                "stderr_tail": stderr_s[-1000:],
                "stdout_tail": stdout_s[-1000:],
            }
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="repo_command_lab",
            passed=passed,
            claim=claim or " ".join(cmd_list),
            ground_truth={
                "executed": True,
                "argv": cmd_list,
                "cwd": str(target_cwd),
                "returncode": proc.returncode,
                "stdout": stdout_s,
                "stderr": stderr_s,
                "stdout_truncated": len(stdout_b) > _MAX_SUBPROCESS_BYTES,
                "stderr_truncated": len(stderr_b) > _MAX_SUBPROCESS_BYTES,
            },
            counterexample=counterexample,
            evidence_source=f"subprocess:{Path(cmd_list[0]).name}",
            limitations=(
                "Bounded read-only allowlist (shell=False, PYTHONDONTWRITEBYTECODE=1, GIT_OPTIONAL_LOCKS=0).",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    # ------------------------------------------------------------------
    # Lab 4: Dataset Invariant Lab
    # ------------------------------------------------------------------

    def verify_dataset_invariants(
        self,
        dataset: Any,
        invariants: Sequence[Mapping[str, Any]],
        *,
        dataset_name: str = "tabular_dataset",
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Evaluate structural, non-NaN, range, conservation, and monotonicity invariants."""
        t0 = time.perf_counter()
        columns, rows = _normalize_dataset(dataset)
        n_rows = len(rows)

        col_stats: dict[str, dict[str, Any]] = {}
        for col in columns:
            vals: list[float] = []
            nan_or_null = 0
            for row in rows:
                fval = _to_float_or_none(row.get(col))
                if fval is None or not math.isfinite(fval):
                    nan_or_null += 1
                else:
                    vals.append(fval)
            if vals:
                arr = np.asarray(vals, dtype=np.float64)
                col_stats[col] = {
                    "finite_count": len(vals),
                    "nonfinite_or_null_count": nan_or_null,
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                }
            else:
                col_stats[col] = {
                    "finite_count": 0,
                    "nonfinite_or_null_count": nan_or_null,
                }

        invariant_reports: list[dict[str, Any]] = []
        violations: list[dict[str, Any]] = []

        def _validate_bound(val: Any, bound_name: str) -> float | None:
            if val is None:
                return None
            if isinstance(val, (bool, np.bool_)):
                raise ValueError(f"Dataset invariant {bound_name} must not be bool, got {val!r}")
            try:
                fbound = float(val)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Dataset invariant {bound_name} must be a finite number, got {val!r}"
                ) from exc
            if not math.isfinite(fbound):
                raise ValueError(f"Dataset invariant {bound_name} must be finite, got {val!r}")
            return fbound

        def _require_column(spec: Mapping[str, Any], kind_name: str) -> str:
            if "column" not in spec or spec["column"] is None or not str(spec["column"]).strip():
                raise ValueError(
                    f"Dataset invariant {kind_name!r} requires a non-empty 'column' field"
                )
            return str(spec["column"])

        def _require_columns_list(raw_cols: Any, field_name: str) -> list[str]:
            if isinstance(raw_cols, (str, bytes, bytearray)) or not isinstance(raw_cols, Iterable):
                raise ValueError(
                    f"Dataset invariant {field_name!r} must be a non-string iterable of column names, "
                    f"got {type(raw_cols).__name__}"
                )
            cols_out: list[str] = []
            for item in raw_cols:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(
                        f"Dataset invariant {field_name!r} entries must be non-empty strings, got {item!r}"
                    )
                cols_out.append(item)
            return cols_out

        for idx, spec in enumerate(invariants):
            if not isinstance(spec, Mapping):
                raise ValueError(
                    f"Dataset invariant at index {idx} must be a mapping, got {type(spec).__name__}"
                )
            kind = str(spec.get("kind", "")).strip().lower()
            inv_passed = True
            inv_failures: list[dict[str, Any]] = []

            if kind in ("non_empty", "schema"):
                raw_min_rows = spec.get("min_rows", 1)
                if isinstance(raw_min_rows, (bool, np.bool_)) or not isinstance(
                    raw_min_rows, (int, np.integer)
                ):
                    raise ValueError(
                        f"Dataset invariant min_rows must be an integer, got {raw_min_rows!r}"
                    )
                min_rows = int(raw_min_rows)
                if min_rows < 0:
                    raise ValueError(
                        f"Dataset invariant min_rows must be >= 0, got {min_rows!r}"
                    )
                if "required_columns" in spec and spec["required_columns"] is not None:
                    req_cols = _require_columns_list(spec["required_columns"], "required_columns")
                else:
                    req_cols = []
                missing_cols = [c for c in req_cols if c not in columns]
                if n_rows < min_rows or missing_cols:
                    inv_passed = False
                    inv_failures.append(
                        {
                            "row_count": n_rows,
                            "min_rows": min_rows,
                            "missing_columns": missing_cols,
                        }
                    )

            elif kind in ("finite", "no_nan", "not_null"):
                if "columns" in spec and spec["columns"] is not None:
                    target_cols = _require_columns_list(spec["columns"], "columns")
                elif "column" in spec:
                    target_cols = [_require_column(spec, kind)]
                else:
                    target_cols = list(columns)
                for r_idx, row in enumerate(rows):
                    for col in target_cols:
                        raw = row.get(col)
                        fval = _to_float_or_none(raw)
                        if fval is None or not math.isfinite(fval):
                            inv_passed = False
                            if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                                inv_failures.append(
                                    {"row_index": r_idx, "column": col, "value": _json_safe(raw)}
                                )

            elif kind in ("range", "bounds"):
                col = _require_column(spec, kind)
                lo = _validate_bound(spec.get("min"), f"{kind}.min")
                hi = _validate_bound(spec.get("max"), f"{kind}.max")
                inclusive = bool(spec.get("inclusive", True))
                for r_idx, row in enumerate(rows):
                    fval = _to_float_or_none(row.get(col))
                    if fval is None or not math.isfinite(fval):
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append(
                                {"row_index": r_idx, "column": col, "value": _json_safe(row.get(col)), "reason": "non-finite"}
                            )
                        continue
                    lo_ok = True if lo is None else (fval >= lo if inclusive else fval > lo)
                    hi_ok = True if hi is None else (fval <= hi if inclusive else fval < hi)
                    if not (lo_ok and hi_ok):
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append(
                                {"row_index": r_idx, "column": col, "value": fval, "min": lo, "max": hi}
                            )

            elif kind in ("conservation", "row_sum", "simplex"):
                if "columns" in spec and spec["columns"] is not None:
                    target_cols = _require_columns_list(spec["columns"], "columns")
                else:
                    target_cols = list(columns)
                target_val = _validate_bound(spec.get("target", 1.0), f"{kind}.target")
                atol_val = _validate_bound(spec.get("atol", 1e-6), f"{kind}.atol")
                assert target_val is not None and atol_val is not None
                if atol_val < 0.0:
                    raise ValueError(f"Dataset invariant {kind}.atol must be nonnegative, got {atol_val!r}")
                target = target_val
                atol = atol_val
                nonnegative = bool(spec.get("nonnegative", kind == "simplex"))
                for r_idx, row in enumerate(rows):
                    nums: list[float] = []
                    bad = False
                    for col in target_cols:
                        fval = _to_float_or_none(row.get(col))
                        if fval is None or not math.isfinite(fval):
                            bad = True
                            break
                        if nonnegative and fval < -atol:
                            bad = True
                            break
                        nums.append(fval)
                    if bad:
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append(
                                {"row_index": r_idx, "columns": target_cols, "reason": "non-finite or negative entry"}
                            )
                        continue
                    total = float(math.fsum(nums))
                    delta = abs(total - target)
                    if delta > atol:
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append(
                                {"row_index": r_idx, "row_sum": total, "target": target, "delta": delta}
                            )

            elif kind in ("monotonic", "monotonic_increasing", "monotonic_decreasing"):
                col = _require_column(spec, kind)
                decreasing = (
                    kind == "monotonic_decreasing"
                    or str(spec.get("direction", "increasing")).lower() == "decreasing"
                )
                strict = bool(spec.get("strict", False))
                prev_val: float | None = None
                for r_idx, row in enumerate(rows):
                    fval = _to_float_or_none(row.get(col))
                    if fval is None or not math.isfinite(fval):
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append(
                                {"row_index": r_idx, "column": col, "value": _json_safe(row.get(col)), "reason": "non-finite"}
                            )
                        continue
                    if prev_val is not None:
                        if decreasing:
                            ok = (fval < prev_val) if strict else (fval <= prev_val)
                        else:
                            ok = (fval > prev_val) if strict else (fval >= prev_val)
                        if not ok:
                            inv_passed = False
                            if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                                inv_failures.append(
                                    {
                                        "row_index": r_idx,
                                        "column": col,
                                        "previous": prev_val,
                                        "current": fval,
                                        "direction": "decreasing" if decreasing else "increasing",
                                        "strict": strict,
                                    }
                                )
                    prev_val = fval

            elif kind in ("mean_range", "std_range"):
                col = _require_column(spec, kind)
                stat_key = "mean" if kind == "mean_range" else "std"
                stat_val = col_stats.get(col, {}).get(stat_key)
                lo = _validate_bound(spec.get("min"), f"{kind}.min")
                hi = _validate_bound(spec.get("max"), f"{kind}.max")
                if stat_val is None:
                    inv_passed = False
                    inv_failures.append({"column": col, "reason": f"no finite values for {stat_key}"})
                else:
                    if (lo is not None and stat_val < lo) or (hi is not None and stat_val > hi):
                        inv_passed = False
                        inv_failures.append({"column": col, stat_key: stat_val, "min": lo, "max": hi})

            elif kind == "unique":
                col = _require_column(spec, kind)
                seen: set[Any] = set()
                for r_idx, row in enumerate(rows):
                    val = row.get(col)
                    key = _canonical_unique_key(val)
                    if key in seen:
                        inv_passed = False
                        if len(inv_failures) < _MAX_COUNTEREXAMPLE_ROWS:
                            inv_failures.append({"row_index": r_idx, "column": col, "duplicate_value": _json_safe(val)})
                    seen.add(key)

            else:
                raise ValueError(f"Unsupported dataset invariant kind: {kind!r}")

            invariant_reports.append(
                {
                    "index": idx,
                    "kind": kind,
                    "passed": inv_passed,
                    "sample_failures": inv_failures,
                }
            )
            if not inv_passed:
                violations.append({"index": idx, "kind": kind, "failures": inv_failures})

        all_passed = len(violations) == 0
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="dataset_invariant_lab",
            passed=all_passed,
            claim=claim or f"Verify {len(invariants)} invariants on {dataset_name} ({n_rows} rows)",
            ground_truth={
                "dataset_name": dataset_name,
                "row_count": n_rows,
                "columns": columns,
                "invariants_checked": len(invariants),
                "invariants_passed": sum(1 for r in invariant_reports if r["passed"]),
                "column_stats": col_stats,
                "invariant_reports": invariant_reports,
            },
            counterexample=violations[0] if violations else None,
            evidence_source="dataset_invariant_evaluator",
            limitations=(
                f"Invariants verified strictly over the observed finite sample (n={n_rows}); does not prove out-of-sample invariance.",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    # ------------------------------------------------------------------
    # Lab 5: Loopback Observatory / Browser & Lean Capability Probes
    # ------------------------------------------------------------------

    def verify_loopback_http(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        expected_status: int | Sequence[int] = 200,
        expected_substrings: Sequence[str] = (),
        expected_headers: Mapping[str, str] | None = None,
        min_bytes: int = 1,
        timeout: float = 5.0,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify a local loopback HTTP endpoint (127.0.0.1 / localhost / ::1) via ``urllib``."""
        t0 = time.perf_counter()
        eff_timeout = _validate_timeout(timeout, name="timeout", max_seconds=None)
        ok_url, reject_reason, parsed = _validate_loopback_url(url)
        host = (parsed.hostname or "").lower()
        if not ok_url:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="loopback_http_lab",
                passed=False,
                claim=claim or f"Loopback HTTP probe {url}",
                ground_truth={"url": url, "loopback_permitted": False},
                counterexample={
                    "rejected_url": url,
                    "reason": reject_reason,
                },
                evidence_source="urllib.request:loopback_guard",
                limitations=("External network access is disabled in RealitySandboxLab.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        allowed_statuses = (
            {int(expected_status)}
            if isinstance(expected_status, int)
            else {int(s) for s in expected_status}
        )
        initial_port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        opener = urlrequest.build_opener(
            _LoopbackSafeRedirectHandler(initial_host=host, initial_port=initial_port)
        )
        req = urlrequest.Request(url, headers=dict(headers or {}), method=method.upper())
        try:
            try:
                resp = opener.open(req, timeout=eff_timeout)
            except urlerror.HTTPError as err:
                resp = err
            with resp:
                status = int(resp.status)
                body = resp.read(_MAX_HTTP_BYTES + 1)
                truncated = len(body) > _MAX_HTTP_BYTES
                if truncated:
                    body = body[:_MAX_HTTP_BYTES]
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
        except _LoopbackRedirectBlockedError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="loopback_http_lab",
                passed=False,
                claim=claim or f"{method.upper()} {url}",
                ground_truth={
                    "url": url,
                    "loopback_permitted": False,
                    "redirect_blocked": True,
                    "redirect_status": exc.status_code,
                    "redirect_target": exc.target_url,
                },
                counterexample={
                    "rejected_url": exc.target_url,
                    "redirect_status": exc.status_code,
                    "reason": str(exc),
                },
                evidence_source="urllib.request:loopback_guard",
                limitations=(
                    "External, cross-host, and cross-port HTTP redirects are blocked in RealitySandboxLab.",
                ),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="loopback_http_lab",
                passed=False,
                claim=claim or f"{method.upper()} {url}",
                ground_truth={"url": url, "connected": False, "error": str(exc)},
                counterexample={"connection_error": str(exc), "error_type": type(exc).__name__},
                evidence_source="urllib.request:127.0.0.1",
                limitations=("Loopback HTTP probe only; no JavaScript execution.",),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        body_text = body.decode("utf-8", errors="replace")
        missing_substrings = [s for s in expected_substrings if s not in body_text]
        header_mismatches: dict[str, dict[str, str | None]] = {}
        for hk, hv in (expected_headers or {}).items():
            actual_hv = resp_headers.get(hk.lower())
            if actual_hv is None or hv not in actual_hv:
                header_mismatches[hk] = {"expected_substring": hv, "actual": actual_hv}

        status_ok = status in allowed_statuses
        size_ok = len(body) >= int(min_bytes)
        passed = status_ok and size_ok and not missing_substrings and not header_mismatches

        counterexample = None
        if not passed:
            counterexample = {
                "status": status,
                "expected_statuses": sorted(allowed_statuses),
                "response_bytes": len(body),
                "min_bytes": min_bytes,
                "missing_substrings": missing_substrings,
                "header_mismatches": header_mismatches,
            }

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="loopback_http_lab",
            passed=passed,
            claim=claim or f"{method.upper()} {url} -> {sorted(allowed_statuses)}",
            ground_truth={
                "url": url,
                "method": method.upper(),
                "status": status,
                "response_bytes": len(body),
                "truncated": truncated,
                "content_type": resp_headers.get("content-type"),
                "content_range": resp_headers.get("content-range"),
                "body_sha256": digest(body.hex()),
            },
            counterexample=counterexample,
            evidence_source=f"urllib.request:{host}",
            limitations=(
                "Verifies HTTP transport, status, headers, and raw payload bytes on loopback only; does not execute client-side JS.",
            ),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def probe_browser_capability(
        self,
        *,
        test_url: str | None = None,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Honest probe of Playwright / Chromium browser automation capability."""
        t0 = time.perf_counter()
        node_bin = shutil.which("node")
        chromium_bin = shutil.which("chromium") or shutil.which("chromium-browser")
        chrome_bin = shutil.which("google-chrome")
        runner_path = Path(
            os.environ.get(
                "ZOE_PLAYWRIGHT_RUNNER",
                Path.home() / ".agents" / "skills" / "playwright-skill" / "run.js",
            )
        )
        runner_exists = runner_path.is_file()
        pw_spec = importlib.util.find_spec("playwright")
        pw_python_installed = pw_spec is not None

        pw_chromium_exe: str | None = None
        pw_chromium_exists = False
        pw_probe_error: str | None = None
        if pw_python_installed:
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as pw:
                    exe_path = Path(pw.chromium.executable_path)
                    pw_chromium_exe = str(exe_path)
                    pw_chromium_exists = exe_path.is_file()
            except Exception as exc:
                pw_probe_error = str(exc)

        chromium_available = bool(pw_chromium_exists or chromium_bin)
        limitations: list[str] = []
        if not pw_chromium_exists:
            limitations.append(
                f"Playwright Chromium binary is absent (expected at {pw_chromium_exe or '~/.cache/ms-playwright'})."
            )
        if not chromium_bin:
            limitations.append("`chromium` / `chromium-browser` binary not found on PATH.")
        if chrome_bin and not pw_chromium_exists:
            limitations.append(
                f"System `google-chrome` found at {chrome_bin}, but Playwright-managed Chromium is unavailable."
            )
        if test_url and not chromium_available:
            limitations.append(
                f"Requested browser verification of {test_url!r} was NOT executed because Chromium is unavailable."
            )
        if pw_probe_error:
            limitations.append(f"Playwright probe error: {pw_probe_error}")

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="browser_capability_probe",
            passed=chromium_available,
            available=chromium_available,
            claim=claim or "Probe Playwright / Chromium headless browser availability",
            ground_truth={
                "playwright_python_installed": pw_python_installed,
                "playwright_chromium_executable": pw_chromium_exe,
                "playwright_chromium_exists": pw_chromium_exists,
                "playwright_skill_runner": str(runner_path),
                "playwright_skill_runner_exists": runner_exists,
                "node_path": node_bin,
                "chromium_path": chromium_bin,
                "google_chrome_path": chrome_bin,
                "test_url_requested": test_url,
                "browser_executed": False,
            },
            counterexample=(
                None
                if chromium_available
                else {"missing": "Playwright Chromium / chromium binary"}
            ),
            evidence_source="capability_probe:playwright_chromium",
            limitations=tuple(limitations)
            or ("Playwright Chromium binary detected; no browser launch performed during capability probe.",),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def probe_lean_capability(
        self,
        *,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Honest probe of ``lean`` / ``lake`` theorem prover availability."""
        t0 = time.perf_counter()
        lean_bin = shutil.which("lean")
        lake_bin = shutil.which("lake")
        lean_available = lean_bin is not None
        limitations = (
            ("Lean binary detected on PATH.",)
            if lean_available
            else (
                "`lean` binary not found on PATH; formal Lean 4 proofs cannot be checked and are NOT simulated.",
            )
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="lean_capability_probe",
            passed=lean_available,
            available=lean_available,
            claim=claim or "Probe Lean theorem prover availability",
            ground_truth={
                "lean_available": lean_available,
                "lean_path": lean_bin,
                "lake_available": lake_bin is not None,
                "lake_path": lake_bin,
            },
            counterexample=None if lean_available else {"missing": "lean"},
            evidence_source="capability_probe:lean",
            limitations=limitations,
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def verify_lean_proof(
        self,
        lean_source: str,
        *,
        timeout: float | None = None,
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify Lean source if ``lean`` is installed; otherwise report unavailability honestly."""
        t0 = time.perf_counter()
        eff_timeout = _validate_timeout(
            timeout if timeout is not None else self.default_timeout,
            name="timeout",
            max_seconds=120.0,
        )
        lean_bin = shutil.which("lean")
        if not lean_bin:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="lean_lab",
                passed=False,
                available=False,
                claim=claim or "Verify Lean formal proof",
                ground_truth={"lean_available": False, "lean_path": None, "executed": False},
                counterexample={"missing_binary": "lean"},
                evidence_source="lean_capability_probe",
                limitations=(
                    "`lean` binary is not installed; proof was NOT checked and NOT faked.",
                ),
                elapsed_ms=elapsed_ms,
            )
            return self._record(verdict, post_to_blackboard=post_to_blackboard)

        with tempfile.TemporaryDirectory(prefix="zoe_lean_lab_") as tmpdir:
            lean_file = Path(tmpdir) / "Check.lean"
            lean_file.write_text(lean_source, encoding="utf-8")
            proc = subprocess.Popen(
                [lean_bin, str(lean_file)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                stdout_b, stderr_b = proc.communicate(timeout=eff_timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                verdict = SandboxLabVerdict(
                    lab_name="lean_lab",
                    passed=False,
                    available=True,
                    claim=claim or "Verify Lean formal proof",
                    ground_truth={"lean_available": True, "timed_out": True},
                    counterexample={"timeout_seconds": eff_timeout},
                    evidence_source=f"lean:{lean_bin}",
                    limitations=(f"Lean check killed after timeout={eff_timeout}s.",),
                    elapsed_ms=elapsed_ms,
                )
                return self._record(verdict, post_to_blackboard=post_to_blackboard)

        stdout_s = stdout_b[:_MAX_SUBPROCESS_BYTES].decode("utf-8", errors="replace")
        stderr_s = stderr_b[:_MAX_SUBPROCESS_BYTES].decode("utf-8", errors="replace")
        passed = proc.returncode == 0
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        verdict = SandboxLabVerdict(
            lab_name="lean_lab",
            passed=passed,
            available=True,
            claim=claim or "Verify Lean formal proof",
            ground_truth={
                "lean_available": True,
                "lean_path": lean_bin,
                "returncode": proc.returncode,
                "stdout": stdout_s,
                "stderr": stderr_s,
            },
            counterexample=None if passed else {"returncode": proc.returncode, "stderr": stderr_s, "stdout": stdout_s},
            evidence_source=f"lean:{lean_bin}",
            limitations=("Single-file `lean` kernel check without external network downloads.",),
            elapsed_ms=elapsed_ms,
        )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def verify_gem_vdi_scene(
        self,
        scene_or_doc: Any,
        *,
        profiles: Sequence[str] = ("cga", "vga", "ndc"),
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify a Digital Research GEM Spatial IR scene & VDI ``.GEM`` metafile across profiles."""
        from .gem_aes_vdi import (
            GEM_ART_II_3_NOTICE,
            GemVdiWorkstation,
            gem_model,
            gem_runner,
        )

        for prof in profiles:
            if str(prof).lower() not in gem_runner.DEVICE_PROFILES:
                raise ValueError(
                    f"Unknown GEM device profile {prof!r}; expected one of "
                    f"{sorted(gem_runner.DEVICE_PROFILES)}"
                )

        t0 = time.perf_counter()
        eff_claim = claim or "Verify Digital Research GEM Spatial IR & VDI metafile round-trip"
        try:
            if isinstance(scene_or_doc, gem_model.Scene):
                scene = scene_or_doc
            elif isinstance(scene_or_doc, Mapping):
                envelope_keys = {"visual_evidence_only", "art_ii_3_notice", "constitutional"}
                cleaned_doc = {k: v for k, v in scene_or_doc.items() if k not in envelope_keys}
                scene = gem_model.Scene.from_dict(cleaned_doc)
            else:
                raise TypeError(
                    "scene_or_doc must be guiai.gem.model.Scene or Mapping, "
                    f"got {type(scene_or_doc).__name__}"
                )
            ws = GemVdiWorkstation()
            compiled = ws.compile_and_verify_vdi(scene, profiles=profiles)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            passed = bool(compiled["passed"])
            gt = {k: v for k, v in compiled.items() if k != "metafile_bytes"}
            verdict = SandboxLabVerdict(
                lab_name="gem_vdi_lab",
                passed=passed,
                available=True,
                claim=eff_claim,
                ground_truth=gt,
                counterexample=None
                if passed
                else {
                    "profiles_passed": dict(compiled["profiles_passed"]),
                    "source_geometry_passed": compiled["source_geometry_passed"],
                    "vdi_roundtrip_passed": compiled["vdi_roundtrip_passed"],
                    "seasip_metafile_valid": compiled["seasip_metafile_valid"],
                },
                evidence_source="guiai.gem.vdi+seasip_gem",
                limitations=(GEM_ART_II_3_NOTICE,),
                elapsed_ms=elapsed_ms,
            )
        except ValueError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="gem_vdi_lab",
                passed=False,
                available=True,
                claim=eff_claim,
                ground_truth={"visual_evidence_only": True, "profiles_requested": list(profiles)},
                counterexample={"error": str(exc), "error_type": type(exc).__name__},
                evidence_source="guiai.gem.vdi+seasip_gem",
                limitations=(GEM_ART_II_3_NOTICE,),
                elapsed_ms=elapsed_ms,
            )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def verify_gem_rsc_bytes(
        self,
        rsc_bytes: bytes,
        *,
        label: str = "ZOE_GEM.RSC",
        claim: str = "",
        post_to_blackboard: bool = False,
    ) -> SandboxLabVerdict:
        """Verify Atari TOS big-endian or PC GEM little-endian ``.RSC`` binary bytes."""
        import struct as _struct

        from .gem_aes_vdi import GEM_ART_II_3_NOTICE, inspect_gem_rsc

        if not isinstance(rsc_bytes, (bytes, bytearray)):
            raise TypeError(
                f"rsc_bytes must be bytes or bytearray, got {type(rsc_bytes).__name__}"
            )
        t0 = time.perf_counter()
        eff_claim = claim or f"Verify GEM .RSC binary resource ({label})"
        try:
            info = inspect_gem_rsc(bytes(rsc_bytes), label=label)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="gem_rsc_lab",
                passed=True,
                available=True,
                claim=eff_claim,
                ground_truth=info,
                counterexample=None,
                evidence_source="guiai.gem.seasip_gem+zoe_atari_gem_rsc",
                limitations=(GEM_ART_II_3_NOTICE,),
                elapsed_ms=elapsed_ms,
            )
        except (ValueError, _struct.error) as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            verdict = SandboxLabVerdict(
                lab_name="gem_rsc_lab",
                passed=False,
                available=True,
                claim=eff_claim,
                ground_truth={"label": str(label), "bytes_len": len(rsc_bytes), "visual_evidence_only": True},
                counterexample={"error": str(exc), "error_type": type(exc).__name__},
                evidence_source="guiai.gem.seasip_gem+zoe_atari_gem_rsc",
                limitations=(GEM_ART_II_3_NOTICE,),
                elapsed_ms=elapsed_ms,
            )
        return self._record(verdict, post_to_blackboard=post_to_blackboard)

    def probe_all_capabilities(self) -> dict[str, Any]:
        """Return an honest inventory of available verification backends."""
        browser = self.probe_browser_capability()
        lean = self.probe_lean_capability()
        return {
            "contract": SANDBOX_LABS_CONTRACT,
            "attribution": ATTRIBUTION_TEXT,
            "sympy": {"available": True, "version": sympy.__version__},
            "z3": {"available": True, "version": z3.get_version_string()},
            "numpy": {"available": True, "version": np.__version__},
            "ast_sandbox": {"available": True, "backend": "GuardedFunctionASTSandbox"},
            "gem_vdi_rsc": {"available": True, "backend": "guiai.gem+seasip_gem"},
            "git": {"available": shutil.which("git") is not None, "path": shutil.which("git")},
            "pytest": {"available": importlib.util.find_spec("pytest") is not None},
            "loopback_http": {"available": True, "allowed_hosts": sorted(_LOOPBACK_HOSTS)},
            "browser_playwright": browser.ground_truth | {"available": browser.available},
            "lean": lean.ground_truth,
        }


__all__ = [
    "SANDBOX_LABS_CONTRACT",
    "RealitySandboxLab",
    "SandboxLabVerdict",
    "post_verdict_to_blackboard",
    "safe_parse_sympy_expr",
]

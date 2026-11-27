"""Architecture #1: AlphaEvolve / FunSearch Evolutionary Program Synthesis Loop.

Combines Google Antigravity-bridged program mutation (``ZoeAntigravityBridge`` /
``ReasoningVoiceAdapter`` with deterministic AST-mutation fallback) with Zoe's
deterministic AST safety sandbox (``GuardedFunctionASTSandbox``) and a
MAP-Elites multi-island evolutionary archive with full diff & rollback lineage.

Enforces ``docs/CONSTITUTION.md`` invariants:
  - ``measurement != evidence != belief update != action``
  - ``external_actions = 0``, ``sentience_claimed = False``,
    ``l5_agi_qualified = False``, ``zoe_clone_claimed = False``
  - Attribution: Nicholas Michael Kloster, March 6, 2026
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
import math
import random
import re
from typing import Any

import numpy as np

from ..l4_multi_module import (
    GuardedFunctionASTSandbox,
    UnsafeFunctionASTError,
    unified_source_diff,
)
from ..loop import digest
from ..metacognition import EvidenceSource
from .sdk_bridge import (
    VALID_MODES,
    ReasoningVoiceAdapter,
    VoiceResponse,
    ZoeAntigravityBridge,
    bridge_constitutional_metadata,
    run_coro_sync,
)

ALPHA_EVOLVE_CONTRACT = "zoe-shared-reasoning-alpha-evolve/v1"

_SAFE_UNARY_CALLS = ("abs", "pos", "sq", "sqrt")
_DISALLOWED_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Attribute,
    ast.Global,
    ast.Nonlocal,
    ast.Lambda,
    ast.While,
    ast.For,
    ast.AsyncFor,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Raise,
    ast.Delete,
    ast.ClassDef,
    ast.AsyncFunctionDef,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Subscript,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
)
_DISALLOWED_CALL_NAMES = frozenset(
    {
        "eval",
        "exec",
        "open",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "input",
        "breakpoint",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TestCase:
    """Deterministic verification test case for candidate programs."""

    __test__ = False

    inputs: dict[str, Any]
    expected: Any
    weight: float = 1.0
    atol: float = 1e-6
    name: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise ValueError(
                f"TestCase.weight must be a finite number > 0, got {self.weight!r}"
            )
        w = float(self.weight)
        if not math.isfinite(w) or w <= 0.0:
            raise ValueError(
                f"TestCase.weight must be a finite number > 0, got {self.weight!r}"
            )
        object.__setattr__(self, "weight", w)

        if isinstance(self.atol, bool) or not isinstance(self.atol, (int, float)):
            raise ValueError(
                f"TestCase.atol must be a finite number >= 0, got {self.atol!r}"
            )
        tol = float(self.atol)
        if not math.isfinite(tol) or tol < 0.0:
            raise ValueError(
                f"TestCase.atol must be a finite number >= 0, got {self.atol!r}"
            )
        object.__setattr__(self, "atol", tol)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inputs": dict(self.inputs),
            "expected": self.expected,
            "weight": self.weight,
            "atol": self.atol,
        }


@dataclass(frozen=True)
class CandidateProgram:
    """Verified evolutionary program candidate tracked in the MAP-Elites archive."""

    id: str
    code: str
    function_name: str
    parent_id: str | None
    generation: int
    behavior_descriptor: tuple[Any, ...]
    score: float
    passed_tests: int
    diff_from_parent: str
    provenance: dict[str, Any] = field(default_factory=dict)
    total_tests: int = 0
    failures: tuple[str, ...] = ()
    ast_metrics: dict[str, Any] = field(default_factory=dict)
    code_sha256: str = ""
    island_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "function_name": self.function_name,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "behavior_descriptor": list(self.behavior_descriptor),
            "score": self.score,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "diff_from_parent": self.diff_from_parent,
            "provenance": dict(self.provenance),
            "failures": list(self.failures),
            "ast_metrics": dict(self.ast_metrics),
            "code_sha256": self.code_sha256,
            "island_id": self.island_id,
        }


@dataclass(frozen=True)
class VerificationReport:
    """Result returned by ``ZoeDeterministicVerifier.evaluate``."""

    safe: bool
    passed_tests: int
    total_tests: int
    score: float
    behavior_descriptor: tuple[Any, ...]
    failures: tuple[str, ...]
    ast_metrics: dict[str, Any]
    code_sha256: str
    error: str | None = None
    outputs: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "passed_tests": self.passed_tests,
            "total_tests": self.total_tests,
            "score": self.score,
            "behavior_descriptor": list(self.behavior_descriptor),
            "failures": list(self.failures),
            "ast_metrics": dict(self.ast_metrics),
            "code_sha256": self.code_sha256,
            "error": self.error,
        }


@dataclass(frozen=True)
class MutationOutcome:
    """Code and provenance emitted by ``AntigravityProgramMutator``."""

    code: str
    source: str
    operator: str
    provenance: dict[str, Any] = field(default_factory=dict)


def _normalize_test_cases(
    test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]],
    arg_names: Sequence[str],
) -> list[TestCase]:
    normalized: list[TestCase] = []
    for idx, item in enumerate(test_cases):
        if isinstance(item, TestCase):
            normalized.append(item)
            continue
        if isinstance(item, Mapping):
            if "inputs" in item:
                raw_in = item["inputs"]
                if isinstance(raw_in, Mapping):
                    inputs = dict(raw_in)
                elif isinstance(raw_in, (tuple, list)):
                    if len(raw_in) != len(arg_names):
                        raise ValueError(
                            f"Test case {idx} expected {len(arg_names)} args, got {len(raw_in)}"
                        )
                    inputs = dict(zip(arg_names, raw_in))
                else:
                    if len(arg_names) != 1:
                        raise ValueError(
                            f"Scalar test input only valid for 1-arg functions, got {arg_names}"
                        )
                    inputs = {arg_names[0]: raw_in}
            elif "args" in item:
                raw_args = item["args"]
                if isinstance(raw_args, (tuple, list)):
                    if len(raw_args) != len(arg_names):
                        raise ValueError(
                            f"Test case {idx} expected {len(arg_names)} args, got {len(raw_args)}"
                        )
                    inputs = dict(zip(arg_names, raw_args))
                else:
                    if len(arg_names) != 1:
                        raise ValueError(
                            f"Scalar test input only valid for 1-arg functions, got {arg_names}"
                        )
                    inputs = {arg_names[0]: raw_args}
            else:
                inputs = {k: item[k] for k in arg_names if k in item}
            raw_w = item.get("weight", 1.0)
            raw_atol = item.get("atol", 1e-6)
            if isinstance(raw_w, bool) or not isinstance(raw_w, (int, float)):
                raise ValueError(
                    f"TestCase.weight must be a finite number > 0, got {raw_w!r}"
                )
            if isinstance(raw_atol, bool) or not isinstance(raw_atol, (int, float)):
                raise ValueError(
                    f"TestCase.atol must be a finite number >= 0, got {raw_atol!r}"
                )
            if "expected" not in item:
                raise ValueError(f"Test case {idx} mapping must contain 'expected'")
            normalized.append(
                TestCase(
                    inputs=inputs,
                    expected=item["expected"],
                    weight=float(raw_w),
                    atol=float(raw_atol),
                    name=str(item.get("name") or f"case_{idx}"),
                )
            )
            continue
        if isinstance(item, tuple) and len(item) == 2:
            raw_in, expected = item
            if isinstance(raw_in, Mapping):
                inputs = dict(raw_in)
            elif isinstance(raw_in, (tuple, list)):
                if len(raw_in) != len(arg_names):
                    raise ValueError(
                        f"Test case {idx} expected {len(arg_names)} args, got {len(raw_in)}"
                    )
                inputs = dict(zip(arg_names, raw_in))
            else:
                if len(arg_names) != 1:
                    raise ValueError(
                        f"Scalar test input only valid for 1-arg functions, got {arg_names}"
                    )
                inputs = {arg_names[0]: raw_in}
            normalized.append(TestCase(inputs=inputs, expected=expected, name=f"case_{idx}"))
            continue
        raise TypeError(f"Unsupported test case format at index {idx}: {type(item).__name__}")
    return normalized


def _value_error_distance(actual: Any, expected: Any) -> float | None:
    """Compute numeric L1 distance for scalars/tuples, or None on structural mismatch."""
    if isinstance(expected, (bool, np.bool_)) or isinstance(actual, (bool, np.bool_)):
        if isinstance(expected, (bool, np.bool_)) and isinstance(actual, (bool, np.bool_)):
            return 0.0 if bool(actual) is bool(expected) else 1.0
        return 1.0
    if isinstance(expected, (int, float, np.integer, np.floating)) and isinstance(
        actual, (int, float, np.integer, np.floating)
    ):
        a = float(actual)
        e = float(expected)
        if not (math.isfinite(a) and math.isfinite(e)):
            return None
        return abs(a - e)
    if isinstance(expected, (tuple, list)) and isinstance(actual, (tuple, list)):
        if len(expected) != len(actual):
            return None
        dists: list[float] = []
        for a_el, e_el in zip(actual, expected):
            d = _value_error_distance(a_el, e_el)
            if d is None:
                return None
            dists.append(d)
        return sum(dists) / max(1, len(dists))
    return 0.0 if actual == expected else 1.0


def _default_behavior_descriptor(
    source: str,
    outputs: Sequence[Any],
    expected_values: Sequence[Any],
    ast_metrics: Mapping[str, Any],
) -> tuple[Any, ...]:
    """Derive a deterministic MAP-Elites behavior descriptor from structure and outputs."""
    tree = ast.parse(source.strip(), mode="exec")
    has_branch = any(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(tree))
    flow_tag = "branching" if has_branch else "straight"

    ast_nodes = int(ast_metrics.get("ast_nodes") or len(list(ast.walk(tree))))
    if ast_nodes <= 14:
        complexity_bin = 0
    elif ast_nodes <= 26:
        complexity_bin = 1
    elif ast_nodes <= 42:
        complexity_bin = 2
    else:
        complexity_bin = 3

    call_names = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    has_nonlin = bool(call_names & {"sq", "sqrt", "log", "abs", "pos"}) or any(
        isinstance(n, ast.BinOp)
        and isinstance(n.op, (ast.Mult, ast.Div))
        and isinstance(n.left, ast.Name)
        and isinstance(n.right, ast.Name)
        for n in ast.walk(tree)
    )
    if call_names & {"min", "max", "clip"} or has_branch:
        family = "piecewise"
    elif has_nonlin:
        family = "nonlinear"
    else:
        family = "linear"

    # Output trend & residual sign bucket across deterministic test outputs
    numeric_outs: list[float] = []
    residuals: list[float] = []
    for out, exp in zip(outputs, expected_values):
        if (
            isinstance(out, (int, float, np.integer, np.floating))
            and not isinstance(out, (bool, np.bool_))
            and math.isfinite(float(out))
        ):
            numeric_outs.append(float(out))
            if (
                isinstance(exp, (int, float, np.integer, np.floating))
                and not isinstance(exp, (bool, np.bool_))
                and math.isfinite(float(exp))
            ):
                residuals.append(float(out) - float(exp))
    if len(numeric_outs) >= 2:
        diffs = [numeric_outs[i + 1] - numeric_outs[i] for i in range(len(numeric_outs) - 1)]
        if all(d >= -1e-9 for d in diffs):
            trend = "nondec"
        elif all(d <= 1e-9 for d in diffs):
            trend = "noninc"
        else:
            trend = "nonmonotone"
    else:
        trend = "scalar"

    if residuals:
        mean_res = sum(residuals) / len(residuals)
        bias = "exact" if abs(mean_res) < 1e-6 else ("over" if mean_res > 0 else "under")
    else:
        bias = "unknown"

    return (flow_tag, complexity_bin, family, trend, bias)


class ZoeDeterministicVerifier:
    """AST-safety gate and deterministic test evaluator using ``GuardedFunctionASTSandbox``."""

    def __init__(
        self,
        *,
        behavior_fn: Callable[
            [str, Sequence[Any], Sequence[Any], Mapping[str, Any]], tuple[Any, ...]
        ]
        | None = None,
    ) -> None:
        self._behavior_fn = behavior_fn

    @classmethod
    def verify_ast(
        cls,
        source: str,
        *,
        expected_name: str | None = None,
        expected_args: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Validate AST strictly against Zoe's pure-function whitelist."""
        if not isinstance(source, str) or not source.strip():
            raise UnsafeFunctionASTError("Candidate source must be a non-empty string")
        try:
            tree = ast.parse(source.strip(), mode="exec")
        except SyntaxError as exc:
            raise UnsafeFunctionASTError(f"Syntax error in candidate: {exc}") from exc

        for node in ast.walk(tree):
            if isinstance(node, _DISALLOWED_AST_NODES):
                raise UnsafeFunctionASTError(
                    f"Disallowed unsafe AST construct: {type(node).__name__}"
                )
            if isinstance(node, ast.Name):
                if node.id.startswith("_") or node.id in _DISALLOWED_CALL_NAMES:
                    raise UnsafeFunctionASTError(
                        f"Disallowed identifier or builtin: {node.id!r}"
                    )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and (
                    node.func.id in _DISALLOWED_CALL_NAMES or node.func.id.startswith("_")
                ):
                    raise UnsafeFunctionASTError(
                        f"Disallowed unsafe call target: {node.func.id!r}"
                    )

        GuardedFunctionASTSandbox.validate(
            source,
            expected_name=expected_name,
            expected_args=expected_args,
        )
        return GuardedFunctionASTSandbox.structural_metrics(source)

    def evaluate(
        self,
        source: str,
        test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]],
        *,
        expected_name: str | None = None,
        expected_args: Sequence[str] | None = None,
        behavior_fn: Callable[
            [str, Sequence[Any], Sequence[Any], Mapping[str, Any]], tuple[Any, ...]
        ]
        | None = None,
    ) -> VerificationReport:
        """Verify AST safety and run all deterministic test cases."""
        cleaned = source.strip() if isinstance(source, str) else ""
        code_sha = digest(cleaned)

        try:
            metrics = self.verify_ast(
                cleaned,
                expected_name=expected_name,
                expected_args=expected_args,
            )
            arg_names = tuple(metrics["arg_names"])
            fn_name = str(metrics["function_name"])
            compiled = GuardedFunctionASTSandbox.compile(
                cleaned,
                expected_name=fn_name,
                expected_args=arg_names,
            )
        except UnsafeFunctionASTError as exc:
            return VerificationReport(
                safe=False,
                passed_tests=0,
                total_tests=len(test_cases),
                score=0.0,
                behavior_descriptor=("unsafe_ast",),
                failures=(str(exc),),
                ast_metrics={},
                code_sha256=code_sha,
                error=str(exc),
                outputs=(),
            )

        norm_cases = _normalize_test_cases(test_cases, arg_names)
        if not norm_cases:
            return VerificationReport(
                safe=True,
                passed_tests=0,
                total_tests=0,
                score=0.0,
                behavior_descriptor=("empty_tests",),
                failures=("No test cases supplied.",),
                ast_metrics=metrics,
                code_sha256=code_sha,
                error="No test cases supplied.",
                outputs=(),
            )

        passed_count = 0
        passed_weight = 0.0
        total_weight = 0.0
        weighted_err_sum = 0.0
        failures: list[str] = []
        outputs: list[Any] = []
        expected_values: list[Any] = []

        for tc in norm_cases:
            if (
                isinstance(tc.weight, bool)
                or not isinstance(tc.weight, (int, float))
                or not math.isfinite(float(tc.weight))
                or float(tc.weight) <= 0.0
            ):
                raise ValueError(
                    f"TestCase.weight must be a finite number > 0, got {tc.weight!r}"
                )
            if (
                isinstance(tc.atol, bool)
                or not isinstance(tc.atol, (int, float))
                or not math.isfinite(float(tc.atol))
                or float(tc.atol) < 0.0
            ):
                raise ValueError(
                    f"TestCase.atol must be a finite number >= 0, got {tc.atol!r}"
                )
            w = float(tc.weight)
            total_weight += w
            expected_values.append(tc.expected)
            try:
                out = compiled(dict(tc.inputs))
            except Exception as exc:  # noqa: BLE001 - runtime arithmetic/sandbox error
                outputs.append(None)
                weighted_err_sum += w * 1e3
                failures.append(f"{tc.name}: runtime error ({exc})")
                continue

            outputs.append(out)
            dist = _value_error_distance(out, tc.expected)
            if dist is None:
                weighted_err_sum += w * 1e3
                failures.append(
                    f"{tc.name}: non-finite or mismatched output {out!r} vs {tc.expected!r}"
                )
                continue

            capped_dist = min(1e6, dist)
            weighted_err_sum += w * capped_dist
            if dist <= tc.atol:
                passed_count += 1
                passed_weight += w
            else:
                failures.append(
                    f"{tc.name}: expected {tc.expected!r}, got {out!r} (err={dist:.6g})"
                )

        pass_fraction = passed_weight / max(1e-9, total_weight)
        mean_err = weighted_err_sum / max(1e-9, total_weight)
        closeness = 1.0 / (1.0 + mean_err)
        if passed_count == len(norm_cases) and mean_err <= 1e-6:
            score = 1.0
        else:
            score = round(0.25 * pass_fraction + 0.75 * closeness, 6)

        bfn = behavior_fn or self._behavior_fn or _default_behavior_descriptor
        descriptor = tuple(bfn(cleaned, outputs, expected_values, metrics))

        return VerificationReport(
            safe=True,
            passed_tests=passed_count,
            total_tests=len(norm_cases),
            score=score,
            behavior_descriptor=descriptor,
            failures=tuple(failures),
            ast_metrics=metrics,
            code_sha256=code_sha,
            error=None,
            outputs=tuple(outputs),
        )


class EvolutionaryArchive:
    """MAP-Elites multi-island evolutionary archive with parent sampling and rollback lineage."""

    def __init__(
        self,
        *,
        num_islands: int = 3,
        temperature: float = 0.06,
        migration_interval: int = 4,
    ) -> None:
        if isinstance(num_islands, bool) or not isinstance(num_islands, int) or num_islands < 1:
            raise ValueError(f"num_islands must be an int >= 1, got {num_islands!r}")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError(f"temperature must be a finite number > 0, got {temperature!r}")
        ftemp = float(temperature)
        if not math.isfinite(ftemp) or ftemp <= 0.0:
            raise ValueError(f"temperature must be finite and > 0, got {temperature!r}")
        if (
            isinstance(migration_interval, bool)
            or not isinstance(migration_interval, int)
            or migration_interval < 1
        ):
            raise ValueError(
                f"migration_interval must be an int >= 1, got {migration_interval!r}"
            )
        self.num_islands = int(num_islands)
        self.temperature = max(1e-4, ftemp)
        self.migration_interval = int(migration_interval)

        self._islands: list[dict[tuple[Any, ...], CandidateProgram]] = [
            {} for _ in range(self.num_islands)
        ]
        self._programs_by_id: dict[str, CandidateProgram] = {}
        self._lineage_parent: dict[str, str | None] = {}
        self._snapshots: list[dict[str, Any]] = []
        self._rollback_log: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return sum(len(island) for island in self._islands)

    @property
    def programs(self) -> dict[str, CandidateProgram]:
        return dict(self._programs_by_id)

    @property
    def rollback_log(self) -> list[dict[str, Any]]:
        return list(self._rollback_log)

    def _ast_node_count(self, candidate: CandidateProgram) -> int:
        return int(candidate.ast_metrics.get("ast_nodes") or len(candidate.code))

    def insert(
        self,
        candidate: CandidateProgram,
        *,
        island_id: int | None = None,
    ) -> bool:
        """Insert a verified candidate into its MAP-Elites island niche if elite."""
        target_island = (
            candidate.island_id if island_id is None else int(island_id)
        ) % self.num_islands
        if candidate.island_id != target_island:
            candidate = CandidateProgram(
                id=candidate.id,
                code=candidate.code,
                function_name=candidate.function_name,
                parent_id=candidate.parent_id,
                generation=candidate.generation,
                behavior_descriptor=candidate.behavior_descriptor,
                score=candidate.score,
                passed_tests=candidate.passed_tests,
                diff_from_parent=candidate.diff_from_parent,
                provenance=dict(candidate.provenance),
                total_tests=candidate.total_tests,
                failures=candidate.failures,
                ast_metrics=dict(candidate.ast_metrics),
                code_sha256=candidate.code_sha256,
                island_id=target_island,
            )

        self._programs_by_id[candidate.id] = candidate
        self._lineage_parent[candidate.id] = candidate.parent_id

        niche_map = self._islands[target_island]
        niche = candidate.behavior_descriptor
        incumbent = niche_map.get(niche)
        if incumbent is None:
            niche_map[niche] = candidate
            return True
        if candidate.score > incumbent.score + 1e-9:
            niche_map[niche] = candidate
            return True
        if abs(candidate.score - incumbent.score) <= 1e-9:
            if self._ast_node_count(candidate) < self._ast_node_count(incumbent):
                niche_map[niche] = candidate
                return True
        return False

    def island_elites(self, island_id: int) -> list[CandidateProgram]:
        idx = int(island_id) % self.num_islands
        return sorted(
            self._islands[idx].values(),
            key=lambda p: (-p.score, self._ast_node_count(p), p.generation, p.id),
        )

    def all_elites(self) -> list[CandidateProgram]:
        combined: list[CandidateProgram] = []
        for island in self._islands:
            combined.extend(island.values())
        return combined

    def sample_parent(
        self,
        rng: random.Random,
        *,
        island_id: int | None = None,
        strategy: str = "boltzmann",
    ) -> CandidateProgram:
        """Sample a verified parent program from the archive using FunSearch-style selection."""
        pool: list[CandidateProgram] = []
        if island_id is not None:
            pool = list(self._islands[int(island_id) % self.num_islands].values())
        if not pool:
            pool = self.all_elites()
        if not pool:
            raise ValueError("Cannot sample parent from an empty EvolutionaryArchive")

        pool.sort(key=lambda p: (p.generation, p.id))
        if strategy == "uniform":
            return pool[rng.randrange(len(pool))]
        if strategy == "tournament":
            sample = rng.sample(pool, min(3, len(pool)))
            return max(sample, key=lambda p: (p.score, -self._ast_node_count(p)))

        # Boltzmann / softmax over scores
        max_s = max(p.score for p in pool)
        weights = [math.exp((p.score - max_s) / self.temperature) for p in pool]
        total_w = sum(weights)
        if total_w <= 0.0 or not math.isfinite(total_w):
            return pool[rng.randrange(len(pool))]
        threshold = rng.random() * total_w
        acc = 0.0
        for prog, w in zip(pool, weights):
            acc += w
            if acc >= threshold:
                return prog
        return pool[-1]

    def sample_inspirations(
        self,
        rng: random.Random,
        *,
        exclude_id: str | None = None,
        k: int = 2,
    ) -> list[CandidateProgram]:
        """Sample up to ``k`` distinct high-scoring exemplars across islands."""
        candidates = [
            p for p in self.top_k(max(k * 3, 6)) if p.id != exclude_id
        ]
        if not candidates or k <= 0:
            return []
        if len(candidates) <= k:
            return candidates
        return rng.sample(candidates, k)

    def top_k(
        self,
        k: int = 5,
        *,
        island_id: int | None = None,
    ) -> list[CandidateProgram]:
        """Return top-K deduplicated verified programs sorted by score then simplicity."""
        if k <= 0:
            return []
        pool = (
            list(self._islands[int(island_id) % self.num_islands].values())
            if island_id is not None
            else self.all_elites()
        )
        ranked = sorted(
            pool,
            key=lambda p: (-p.score, self._ast_node_count(p), p.generation, p.id),
        )
        seen_hashes: set[str] = set()
        unique: list[CandidateProgram] = []
        for prog in ranked:
            key = prog.code_sha256 or prog.id
            if key in seen_hashes:
                continue
            seen_hashes.add(key)
            unique.append(prog)
            if len(unique) >= k:
                break
        return unique

    def get_lineage(self, program_id: str) -> list[CandidateProgram]:
        """Reconstruct full evolutionary lineage from seed to ``program_id``."""
        if program_id not in self._programs_by_id:
            raise KeyError(f"Unknown program_id {program_id!r}")
        chain: list[CandidateProgram] = []
        seen: set[str] = set()
        curr_id: str | None = program_id
        while curr_id is not None:
            if curr_id in seen:
                break
            seen.add(curr_id)
            prog = self._programs_by_id.get(curr_id)
            if prog is None:
                break
            chain.append(prog)
            curr_id = self._lineage_parent.get(curr_id)
        chain.reverse()
        return chain

    def record_snapshot(self, generation: int) -> None:
        """Persist an immutable island snapshot for reversible generation rollback."""
        snap_islands = [
            {desc: prog.id for desc, prog in island.items()}
            for island in self._islands
        ]
        self._snapshots.append(
            {
                "generation": int(generation),
                "islands": snap_islands,
                "recorded_utc": _utc_now_iso(),
            }
        )

    def rollback_to_generation(self, generation: int) -> bool:
        """Restore active MAP-Elites islands to the snapshot recorded at ``generation``."""
        target = None
        for snap in reversed(self._snapshots):
            if snap["generation"] == int(generation):
                target = snap
                break
        if target is None:
            return False

        restored_islands: list[dict[tuple[Any, ...], CandidateProgram]] = []
        for isl_map in target["islands"]:
            restored_islands.append(
                {desc: self._programs_by_id[pid] for desc, pid in isl_map.items()}
            )
        self._islands = restored_islands
        self._rollback_log.append(
            {
                "action": "rollback_to_generation",
                "target_generation": int(generation),
                "restored_elite_count": len(self),
                "recorded_utc": _utc_now_iso(),
            }
        )
        return True

    def rollback_to(self, program_id: str) -> bool:
        """Roll back archive elites to the generation snapshot of ``program_id``."""
        if program_id not in self._programs_by_id:
            return False
        prog = self._programs_by_id[program_id]
        if self.rollback_to_generation(prog.generation):
            return True
        # Fallback if no snapshot exists for that generation: restore single ancestor lineage
        lineage = self.get_lineage(program_id)
        restored: list[dict[tuple[Any, ...], CandidateProgram]] = [
            {} for _ in range(self.num_islands)
        ]
        for node in lineage:
            restored[node.island_id % self.num_islands][node.behavior_descriptor] = node
        self._islands = restored
        self._rollback_log.append(
            {
                "action": "rollback_to_program",
                "target_program_id": program_id,
                "restored_elite_count": len(self),
                "recorded_utc": _utc_now_iso(),
            }
        )
        return True

    def migrate(self, generation: int) -> int:
        """Ring-migrate the top program from each island to the next island."""
        if self.num_islands <= 1 or generation <= 0:
            return 0
        if generation % self.migration_interval != 0:
            return 0
        migrants: list[tuple[int, CandidateProgram]] = []
        for idx in range(self.num_islands):
            elites = self.island_elites(idx)
            if elites:
                migrants.append(((idx + 1) % self.num_islands, elites[0]))
        accepted = 0
        for dst_island, prog in migrants:
            if self.insert(prog, island_id=dst_island):
                accepted += 1
        return accepted

    def diversity_summary(self) -> dict[str, Any]:
        all_e = self.all_elites()
        unique_desc = sorted({p.behavior_descriptor for p in all_e}, key=repr)
        scores = [p.score for p in all_e]
        return {
            "num_islands": self.num_islands,
            "occupied_niches_total": len(all_e),
            "unique_descriptors": len(unique_desc),
            "descriptor_list": [list(d) for d in unique_desc],
            "per_island_counts": [len(isl) for isl in self._islands],
            "best_score": max(scores) if scores else 0.0,
            "mean_elite_score": round(sum(scores) / len(scores), 6) if scores else 0.0,
        }


# ---------------------------------------------------------------------------
# AST Mutation Operators (Deterministic Offline & Fallback Engine)
# ---------------------------------------------------------------------------

_NUMERIC_CHOICES: tuple[float, ...] = (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 3.0)
_STEP_DELTAS: tuple[float, ...] = (-1.0, -0.5, -0.25, -0.1, 0.1, 0.25, 0.5, 1.0)
_BINOP_CLASSES: tuple[type[ast.operator], ...] = (ast.Add, ast.Sub, ast.Mult, ast.Div)
_CMPOP_CLASSES: tuple[type[ast.cmpop], ...] = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _round_num(val: float) -> int | float:
    r = round(float(val), 4)
    if abs(r - round(r)) < 1e-9:
        return int(round(r))
    return r


def _make_num(val: float) -> ast.Constant:
    return ast.Constant(value=_round_num(val))


def _make_term(arg_names: Sequence[str], rng: random.Random, *, nonlinear: bool) -> ast.expr:
    arg = rng.choice(list(arg_names))
    coeff = rng.choice(_NUMERIC_CHOICES)
    if not nonlinear:
        base: ast.expr = ast.Name(id=arg, ctx=ast.Load())
    else:
        kind = rng.choice(("sq", "abs", "pos", "sqrt", "mul_args"))
        if kind == "mul_args" and len(arg_names) >= 2:
            a2 = rng.choice(list(arg_names))
            base = ast.BinOp(
                left=ast.Name(id=arg, ctx=ast.Load()),
                op=ast.Mult(),
                right=ast.Name(id=a2, ctx=ast.Load()),
            )
        else:
            fn_name = "sq" if kind == "mul_args" else kind
            inner: ast.expr = ast.Name(id=arg, ctx=ast.Load())
            if fn_name == "sqrt":
                inner = ast.Call(
                    func=ast.Name(id="pos", ctx=ast.Load()),
                    args=[inner],
                    keywords=[],
                )
            base = ast.Call(
                func=ast.Name(id=fn_name, ctx=ast.Load()),
                args=[inner],
                keywords=[],
            )
    if coeff == 1.0:
        return base
    if coeff == -1.0:
        return ast.UnaryOp(op=ast.USub(), operand=base)
    return ast.BinOp(left=_make_num(coeff), op=ast.Mult(), right=base)


def _collect_return_nodes(fn: ast.FunctionDef) -> list[ast.Return]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]


def _mutate_expr_node(
    expr: ast.expr,
    arg_names: Sequence[str],
    rng: random.Random,
    *,
    op_hint: str | None = None,
    _depth: int = 0,
) -> tuple[ast.expr, str]:
    """Apply a single clean AST transformation to an expression or subexpression."""
    cloned = copy.deepcopy(expr)

    # With 45% probability on compound expressions, descend into a child subexpression
    if _depth < 2 and op_hint is None and rng.random() < 0.45:
        if isinstance(cloned, ast.BinOp):
            if rng.random() < 0.5:
                cloned.left, sub_op = _mutate_expr_node(
                    cloned.left, arg_names, rng, _depth=_depth + 1
                )
            else:
                cloned.right, sub_op = _mutate_expr_node(
                    cloned.right, arg_names, rng, _depth=_depth + 1
                )
            return cloned, f"sub({sub_op})"
        if isinstance(cloned, ast.Call) and cloned.args:
            idx = rng.randrange(len(cloned.args))
            cloned.args[idx], sub_op = _mutate_expr_node(
                cloned.args[idx], arg_names, rng, _depth=_depth + 1
            )
            return cloned, f"sub({sub_op})"

    choices = [
        "add_linear_term",
        "add_nonlinear_term",
        "add_constant",
        "mutate_constant",
        "swap_binop",
        "wrap_func",
        "unwrap_func",
    ]
    op_name = op_hint if op_hint in choices else rng.choice(choices)

    if op_name == "add_constant":
        delta = rng.choice(_STEP_DELTAS)
        return (
            ast.BinOp(
                left=cloned,
                op=ast.Add() if delta >= 0 else ast.Sub(),
                right=_make_num(abs(delta)),
            ),
            "add_constant",
        )

    if op_name == "add_linear_term":
        term = _make_term(arg_names, rng, nonlinear=False)
        comb = rng.choice((ast.Add, ast.Sub))
        return ast.BinOp(left=cloned, op=comb(), right=term), "add_linear_term"

    if op_name == "add_nonlinear_term":
        term = _make_term(arg_names, rng, nonlinear=True)
        comb = rng.choice((ast.Add, ast.Sub))
        return ast.BinOp(left=cloned, op=comb(), right=term), "add_nonlinear_term"

    if op_name == "mutate_constant":
        consts = [
            n
            for n in ast.walk(cloned)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)
        ]
        if consts:
            target = rng.choice(consts)
            val = target.value
            assert isinstance(val, (int, float))
            roll = rng.random()
            if roll < 0.45:
                target.value = _round_num(float(val) + rng.choice(_STEP_DELTAS))
            elif roll < 0.75:
                target.value = _round_num(
                    float(val) * rng.choice((-1.0, 0.5, 1.5, 2.0))
                )
            else:
                # Snap to clean 0.5-grid or integer to reduce constant drift
                target.value = _round_num(round(float(val) * 2.0) / 2.0)
            return cloned, "mutate_constant"
        return (
            ast.BinOp(left=_make_num(rng.choice(_NUMERIC_CHOICES)), op=ast.Mult(), right=cloned),
            "scale_expr",
        )

    if op_name == "swap_binop":
        binops = [n for n in ast.walk(cloned) if isinstance(n, ast.BinOp)]
        if binops:
            target_b = rng.choice(binops)
            alts = [cls for cls in _BINOP_CLASSES if not isinstance(target_b.op, cls)]
            target_b.op = rng.choice(alts)()
            return cloned, "swap_binop"
        return (
            ast.BinOp(
                left=cloned,
                op=ast.Add(),
                right=_make_term(arg_names, rng, nonlinear=False),
            ),
            "add_linear_term",
        )

    if op_name == "wrap_func":
        fn_pick = rng.choice(("abs", "pos", "sq", "sqrt", "neg", "min_arg", "max_arg"))
        if fn_pick == "neg":
            return ast.UnaryOp(op=ast.USub(), operand=cloned), "wrap_neg"
        if fn_pick in ("min_arg", "max_arg"):
            other = ast.Name(id=rng.choice(list(arg_names)), ctx=ast.Load())
            fn_id = "min" if fn_pick == "min_arg" else "max"
            return (
                ast.Call(func=ast.Name(id=fn_id, ctx=ast.Load()), args=[cloned, other], keywords=[]),
                f"wrap_{fn_id}",
            )
        inner = cloned
        if fn_pick == "sqrt":
            inner = ast.Call(func=ast.Name(id="pos", ctx=ast.Load()), args=[inner], keywords=[])
        return (
            ast.Call(func=ast.Name(id=fn_pick, ctx=ast.Load()), args=[inner], keywords=[]),
            f"wrap_{fn_pick}",
        )

    # unwrap_func
    if isinstance(cloned, ast.Call) and len(cloned.args) >= 1:
        return cloned.args[0], "unwrap_func"
    if isinstance(cloned, ast.UnaryOp):
        return cloned.operand, "unwrap_unary"
    if isinstance(cloned, ast.BinOp):
        return rng.choice((cloned.left, cloned.right)), "prune_binop"
    return _make_term(arg_names, rng, nonlinear=False), "replace_term"


def _extract_python_def(text: str, expected_name: str | None = None) -> str | None:
    """Extract a Python ``def`` function from markdown code fences or raw response text."""
    if not text:
        return None
    fenced = re.findall(r"```(?:python)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = list(fenced) + [text]
    for blob in candidates:
        stripped = blob.strip()
        if "def " not in stripped:
            continue
        lines = stripped.splitlines()
        start_idx = None
        for idx, line in enumerate(lines):
            if line.lstrip().startswith("def "):
                if expected_name is None or line.lstrip().startswith(f"def {expected_name}("):
                    start_idx = idx
                    break
        if start_idx is None:
            for idx, line in enumerate(lines):
                if line.lstrip().startswith("def "):
                    start_idx = idx
                    break
        if start_idx is None:
            continue
        # Capture the function block until top-level non-indented non-empty line
        fn_lines = [lines[start_idx]]
        base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
        for nxt in lines[start_idx + 1 :]:
            if not nxt.strip():
                fn_lines.append("")
                continue
            indent = len(nxt) - len(nxt.lstrip())
            if indent <= base_indent:
                break
            fn_lines.append(nxt)
        code = "\n".join(fn_lines).strip()
        try:
            parsed = ast.parse(code, mode="exec")
            if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.FunctionDef):
                return code
        except SyntaxError:
            continue
    return None


class AntigravityProgramMutator:
    """Mutates programs via ``ZoeAntigravityBridge`` / ``ReasoningVoiceAdapter`` or AST fallback."""

    def __init__(
        self,
        *,
        bridge: ZoeAntigravityBridge | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        mode: str = "hybrid",
        seed: int = 42,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        probe_local: bool = False,
        bridge_mode: str | None = None,
    ) -> None:
        if mode not in ("hybrid", "ast_only", "antigravity_only"):
            raise ValueError(f"Unsupported mutator mode: {mode!r}")
        if bridge_mode is not None and bridge_mode not in VALID_MODES:
            raise ValueError(f"bridge_mode must be one of {VALID_MODES}, got {bridge_mode!r}")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError(f"seed must be an int, got {seed!r}")
        self.bridge = bridge
        self.voice_adapter = voice_adapter
        self.mode = mode
        self.offline_only = bool(offline_only)
        self.privacy_sensitive = bool(privacy_sensitive)
        self.probe_local = bool(probe_local)
        self.bridge_mode = bridge_mode
        self._rng = random.Random(seed)

    @staticmethod
    def build_mutation_prompt(
        parent: CandidateProgram,
        *,
        inspirations: Sequence[CandidateProgram] = (),
        failures: Sequence[str] = (),
        prompt_context: str = "",
    ) -> str:
        """Construct a FunSearch / AlphaEvolve prompt with parent, exemplars, and errors."""
        sections = [
            "Mutate the following pure Python function to improve its deterministic test score.",
            f"Target function name: {parent.function_name}",
            f"Current score: {parent.score} ({parent.passed_tests}/{parent.total_tests} tests passed)",
            f"Parent program:\n```python\n{parent.code}\n```",
        ]
        if inspirations:
            insp_blocks = "\n".join(
                f"# Inspiration (score={ins.score}, behavior={ins.behavior_descriptor}):\n{ins.code}"
                for ins in inspirations
            )
            sections.append(f"Diverse high-scoring archive exemplars:\n```python\n{insp_blocks}\n```")
        if failures:
            sections.append("Observed failures:\n- " + "\n- ".join(failures[:4]))
        if prompt_context:
            sections.append(f"Task context: {prompt_context}")
        sections.append(
            "Constraints: Pure single `def` function; no imports, no loops, no eval/exec/IO. "
            "Allowed helpers: abs, pos, sq, sqrt, log, mean, min, max, clip."
        )
        return "\n\n".join(sections)

    def _try_antigravity_proposal(
        self,
        parent: CandidateProgram,
        *,
        inspirations: Sequence[CandidateProgram],
        failures: Sequence[str],
        prompt_context: str,
    ) -> MutationOutcome | None:
        if self.mode == "ast_only":
            return None
        if self.bridge is None and self.voice_adapter is None:
            return None

        prompt = self.build_mutation_prompt(
            parent,
            inspirations=inspirations,
            failures=failures,
            prompt_context=prompt_context,
        )
        context_meta = {
            "parent_id": parent.id,
            "function_name": parent.function_name,
            "generation": parent.generation + 1,
            "behavior_descriptor": list(parent.behavior_descriptor),
        }

        raw_text = ""
        thoughts: tuple[str, ...] = ()
        bridge_mode = "voice_adapter"

        if self.bridge is not None:
            bridge_inst_mode = getattr(self.bridge, "mode", None)
            raw_mode = self.bridge_mode or bridge_inst_mode or "offline"
            eff_offline = bool(
                self.offline_only
                or bridge_inst_mode == "offline"
                or self.bridge_mode == "offline"
                or (
                    self.privacy_sensitive
                    and (
                        raw_mode == "gemini"
                        or (not self.probe_local and raw_mode in ("auto", "local_qwen"))
                    )
                )
            )
            eff_mode = "offline" if eff_offline else raw_mode
            eff_probe_local = False if eff_offline else self.probe_local
            turn_res = run_coro_sync(
                self.bridge.arun_turn(
                    prompt,
                    mode=eff_mode,
                    offline_only=eff_offline,
                    privacy_sensitive=self.privacy_sensitive,
                    probe_local=eff_probe_local,
                    voice_adapter=self.voice_adapter,
                )
            )
            raw_text = turn_res.text
            thoughts = turn_res.thoughts
            bridge_mode = turn_res.resolution.selected_mode
        elif self.voice_adapter is not None:
            resp: VoiceResponse = run_coro_sync(
                self.voice_adapter.generate(prompt, context=context_meta)
            )
            raw_text = resp.text
            thoughts = resp.thoughts
            bridge_mode = resp.mode

        extracted = _extract_python_def(raw_text, expected_name=parent.function_name)
        if extracted is None:
            return None
        return MutationOutcome(
            code=extracted,
            source="antigravity_bridge",
            operator="sdk_voice_generation",
            provenance={
                "mutator": "AntigravityProgramMutator",
                "transport_mode": bridge_mode,
                "thoughts": list(thoughts),
                "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
            },
        )

    def mutate_ast(
        self,
        parent: CandidateProgram,
        *,
        inspirations: Sequence[CandidateProgram] = (),
        rng: random.Random | None = None,
    ) -> MutationOutcome:
        """Perform a genuine deterministic AST mutation on ``parent.code``."""
        r = rng or self._rng
        tree = ast.parse(parent.code.strip(), mode="exec")
        fn = tree.body[0]
        if not isinstance(fn, ast.FunctionDef):
            raise UnsafeFunctionASTError("Parent code is not a Python function")
        arg_names = [a.arg for a in fn.args.args]

        # Choose structural vs expression mutation (favor clean expression refinement;
        # apply parsimony pressure when AST grows large)
        node_count = len(list(ast.walk(fn)))
        if node_count > 36:
            structural_ops = ["expr_mutate", "expr_mutate", "expr_mutate", "expr_mutate"]
            if any(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(fn)):
                structural_ops.append("mutate_branch")
        else:
            structural_ops = [
                "expr_mutate",
                "expr_mutate",
                "expr_mutate",
                "expr_mutate",
                "expr_mutate",
                "expr_mutate",
                "introduce_branch",
                "introduce_local",
            ]
            if any(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(fn)):
                structural_ops.append("mutate_branch")
            if inspirations:
                structural_ops.append("crossover_inspiration")
        chosen = r.choice(structural_ops)
        op_label = chosen

        if chosen == "crossover_inspiration" and inspirations:
            insp = r.choice(list(inspirations))
            try:
                insp_tree = ast.parse(insp.code.strip(), mode="exec")
                insp_fn = insp_tree.body[0]
                if isinstance(insp_fn, ast.FunctionDef):
                    insp_rets = _collect_return_nodes(insp_fn)
                    par_rets = _collect_return_nodes(fn)
                    if insp_rets and par_rets:
                        target_ret = r.choice(par_rets)
                        insp_expr = copy.deepcopy(r.choice(insp_rets).value)
                        assert insp_expr is not None and target_ret.value is not None
                        if r.random() < 0.5 and isinstance(target_ret.value, ast.BinOp):
                            if r.random() < 0.5:
                                target_ret.value.left = insp_expr
                            else:
                                target_ret.value.right = insp_expr
                            op_label = f"crossover_graft({insp.id})"
                        else:
                            comb = r.choice((ast.Add, ast.Sub))
                            target_ret.value = ast.BinOp(
                                left=target_ret.value,
                                op=comb(),
                                right=insp_expr,
                            )
                            op_label = f"crossover_combine({insp.id})"
                    else:
                        chosen = "expr_mutate"
                else:
                    chosen = "expr_mutate"
            except SyntaxError:
                chosen = "expr_mutate"

        if chosen == "introduce_branch":
            rets = _collect_return_nodes(fn)
            if rets:
                target_ret = r.choice(rets)
                assert target_ret.value is not None
                orig_expr = copy.deepcopy(target_ret.value)
                alt_expr, sub_op = _mutate_expr_node(orig_expr, arg_names, r)
                cond_arg = r.choice(arg_names)
                thresh = r.choice((-1.0, 0.0, 0.5, 1.0))
                cmp_op = r.choice(_CMPOP_CLASSES)()
                test_node = ast.Compare(
                    left=ast.Name(id=cond_arg, ctx=ast.Load()),
                    ops=[cmp_op],
                    comparators=[_make_num(thresh)],
                )
                # Replace return statement with if/else return if in a statement block
                if isinstance(fn.body[-1], ast.Return):
                    fn.body[-1] = ast.If(
                        test=test_node,
                        body=[ast.Return(value=orig_expr)],
                        orelse=[ast.Return(value=alt_expr)],
                    )
                else:
                    target_ret.value = ast.IfExp(test=test_node, body=orig_expr, orelse=alt_expr)
                op_label = f"introduce_branch({sub_op})"
            else:
                chosen = "expr_mutate"

        elif chosen == "mutate_branch":
            if_nodes = [n for n in ast.walk(fn) if isinstance(n, (ast.If, ast.IfExp))]
            if if_nodes:
                if_node = r.choice(if_nodes)
                mode_b = r.choice(("thresh", "cmp", "body", "orelse"))
                if mode_b in ("thresh", "cmp") and isinstance(if_node.test, ast.Compare):
                    if mode_b == "cmp":
                        if_node.test.ops = [r.choice(_CMPOP_CLASSES)()]
                        op_label = "mutate_branch_cmp"
                    else:
                        if if_node.test.comparators and isinstance(if_node.test.comparators[0], ast.Constant):
                            val = float(if_node.test.comparators[0].value)  # type: ignore[arg-type]
                            if_node.test.comparators[0] = _make_num(val + r.choice(_STEP_DELTAS))
                            op_label = "mutate_branch_thresh"
                else:
                    if isinstance(if_node, ast.IfExp):
                        if mode_b == "body":
                            if_node.body, sub_op = _mutate_expr_node(if_node.body, arg_names, r)
                        else:
                            if_node.orelse, sub_op = _mutate_expr_node(if_node.orelse, arg_names, r)
                        op_label = f"mutate_ifexp_{mode_b}({sub_op})"
                    else:
                        branch_stmts = if_node.body if mode_b == "body" else (if_node.orelse or if_node.body)
                        branch_rets = [s for s in branch_stmts if isinstance(s, ast.Return) and s.value is not None]
                        if branch_rets:
                            br = r.choice(branch_rets)
                            assert br.value is not None
                            br.value, sub_op = _mutate_expr_node(br.value, arg_names, r)
                            op_label = f"mutate_if_{mode_b}({sub_op})"
            else:
                chosen = "expr_mutate"

        elif chosen == "introduce_local":
            assigns = [s for s in fn.body if isinstance(s, ast.Assign)]
            rets = _collect_return_nodes(fn)
            if len(assigns) < 3 and rets and isinstance(fn.body[-1], ast.Return) and fn.body[-1].value is not None:
                var_name = f"term_{len(assigns)}"
                if var_name not in arg_names:
                    sub_expr = _make_term(arg_names, r, nonlinear=r.random() < 0.5)
                    assign_stmt = ast.Assign(
                        targets=[ast.Name(id=var_name, ctx=ast.Store())],
                        value=sub_expr,
                    )
                    fn.body.insert(-1, assign_stmt)
                    ret_node = fn.body[-1]
                    assert isinstance(ret_node, ast.Return) and ret_node.value is not None
                    ret_node.value = ast.BinOp(
                        left=ret_node.value,
                        op=r.choice((ast.Add, ast.Sub))(),
                        right=ast.Name(id=var_name, ctx=ast.Load()),
                    )
                    op_label = f"introduce_local({var_name})"
                else:
                    chosen = "expr_mutate"
            else:
                chosen = "expr_mutate"

        if chosen == "expr_mutate":
            # Mutate either an assignment RHS or a return expression
            assigns = [s for s in fn.body if isinstance(s, ast.Assign)]
            rets = _collect_return_nodes(fn)
            if assigns and r.random() < 0.3:
                asg = r.choice(assigns)
                asg.value, op_label = _mutate_expr_node(asg.value, arg_names, r)
            elif rets:
                ret = r.choice(rets)
                assert ret.value is not None
                ret.value, op_label = _mutate_expr_node(ret.value, arg_names, r)

        ast.fix_missing_locations(tree)
        mutated_code = ast.unparse(tree)
        return MutationOutcome(
            code=mutated_code,
            source="ast_mutator_fallback",
            operator=op_label,
            provenance={
                "mutator": "AntigravityProgramMutator",
                "operator": op_label,
                "parent_id": parent.id,
                "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
            },
        )

    def mutate(
        self,
        parent: CandidateProgram,
        *,
        inspirations: Sequence[CandidateProgram] = (),
        failures: Sequence[str] = (),
        prompt_context: str = "",
        rng: random.Random | None = None,
    ) -> MutationOutcome:
        """Attempt Antigravity bridge mutation, falling back cleanly to AST mutation."""
        r = rng or self._rng
        if self.mode in ("hybrid", "antigravity_only"):
            sdk_out = self._try_antigravity_proposal(
                parent,
                inspirations=inspirations,
                failures=failures,
                prompt_context=prompt_context,
            )
            if sdk_out is not None:
                return sdk_out
            if self.mode == "antigravity_only":
                return MutationOutcome(
                    code=parent.code,
                    source="antigravity_only_noop",
                    operator="noop",
                    provenance={"mutator": "AntigravityProgramMutator", "note": "no code emitted"},
                )

        # Deterministic AST fallback (retry a few times if an AST budget is exceeded)
        last_err: Exception | None = None
        for _ in range(5):
            outcome = self.mutate_ast(parent, inspirations=inspirations, rng=r)
            try:
                GuardedFunctionASTSandbox.validate(
                    outcome.code,
                    expected_name=parent.function_name,
                )
                return outcome
            except UnsafeFunctionASTError as exc:
                last_err = exc
        return MutationOutcome(
            code=parent.code,
            source="ast_mutator_fallback",
            operator=f"fallback_identity({last_err})",
            provenance={"mutator": "AntigravityProgramMutator", "error": str(last_err)},
        )


@dataclass(frozen=True)
class AlphaEvolveResult:
    """Complete result returned by ``AlphaEvolveLoop.evolve``."""

    best_program: CandidateProgram
    archive: EvolutionaryArchive
    lineage: list[CandidateProgram]
    rejected_candidates: list[dict[str, Any]]
    generation_history: list[dict[str, Any]] = field(default_factory=list)
    blackboard_records: list[dict[str, Any]] = field(default_factory=list)
    constitutional: dict[str, Any] = field(default_factory=bridge_constitutional_metadata)
    contract: str = ALPHA_EVOLVE_CONTRACT

    def to_gem_spatial_ir(self, *, scene_id: str = "alpha-evolve-gem-view") -> dict[str, Any]:
        """Export an Art. II.3 visual-only GEM Spatial IR summary of the evolutionary archive."""
        from .gem_aes_vdi import GEM_ART_II_3_NOTICE

        return {
            "schema_version": 1,
            "id": str(scene_id),
            "title": "AlphaEvolve MAP-Elites GEM View",
            "canvas": {"width": 6400, "height": 3200},
            "objects": [
                {"id": "best_box", "type": "rectangle", "bounds": [100, 100, 6300, 1450], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "best_txt", "type": "text", "position": [240, 800], "text": f"BEST score={self.best_program.score:.2f}", "size": 160, "fill": "black"},
                {"id": "arch_box", "type": "rectangle", "bounds": [100, 1650, 6300, 3100], "fill": "#FFFFFF", "stroke": "black"},
                {"id": "arch_txt", "type": "text", "position": [240, 2350], "text": f"ELITES={len(self.archive)} REJ={len(self.rejected_candidates)}", "size": 160, "fill": "black"},
            ],
            "constraints": [
                {"type": "inside_canvas", "object": "*"},
                {"type": "nonoverlap", "objects": ["best_box", "arch_box"]},
            ],
            "visual_evidence_only": True,
            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
            "constitutional": dict(self.constitutional),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "best_program": self.best_program.to_dict(),
            "archive_diversity": self.archive.diversity_summary(),
            "lineage": [p.to_dict() for p in self.lineage],
            "rejected_candidates": list(self.rejected_candidates),
            "generation_history": list(self.generation_history),
            "blackboard_records": list(self.blackboard_records),
            "constitutional": dict(self.constitutional),
        }


def _call_blackboard_post_measurement(
    blackboard: Any,
    *,
    source: str,
    input_desc: str,
    metric_name: str,
    value: float,
    scope: str,
    method: str,
    limitations: str,
    metadata: dict[str, Any],
    sampled_only: bool = False,
) -> Any:
    """Adapt cleanly to ``EpistemicBlackboard.post_measurement`` signature."""
    fn = blackboard.post_measurement
    sig = inspect.signature(fn)
    params = sig.parameters
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if has_var_kw:
        return fn(
            source=source,
            source_agent=source,
            input_desc=input_desc,
            metric_name=metric_name,
            value=value,
            scope=scope,
            method=method,
            limitations=limitations,
            sampled_only=sampled_only,
            metadata=metadata,
        )
    candidate_kwargs: dict[str, Any] = {
        "source_agent": source,
        "source": source,
        "producer": source,
        "input_desc": input_desc,
        "metric_name": metric_name,
        "name": metric_name,
        "value": value,
        "measurement": value,
        "scope": scope,
        "method": method,
        "limitations": limitations,
        "sampled_only": sampled_only,
        "metadata": metadata,
        "payload": metadata,
    }
    filtered = {k: v for k, v in candidate_kwargs.items() if k in params}
    if filtered:
        return fn(**filtered)
    return fn(value)


def _call_blackboard_promote(
    blackboard: Any,
    *,
    measurement_id: str,
    verifier_name: str,
    passed: bool,
    rationale: str,
    evidence_source: EvidenceSource | None = None,
) -> Any:
    fn = blackboard.promote_to_evidence
    sig = inspect.signature(fn)
    params = sig.parameters
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if has_var_kw:
        kwargs_all: dict[str, Any] = {
            "measurement_id": measurement_id,
            "verifier_name": verifier_name,
            "passed": passed,
            "rationale": rationale,
        }
        if evidence_source is not None:
            kwargs_all["evidence_source"] = evidence_source
        return fn(**kwargs_all)
    kwargs: dict[str, Any] = {
        "measurement_id": measurement_id,
        "verifier_name": verifier_name,
        "verifier": verifier_name,
        "passed": passed,
        "rationale": rationale,
    }
    if evidence_source is not None:
        kwargs["evidence_source"] = evidence_source
    filtered = {k: v for k, v in kwargs.items() if k in params}
    if len(filtered) >= 3:
        return fn(**filtered)
    return fn(measurement_id, verifier_name, passed, rationale)


class AlphaEvolveLoop:
    """AlphaEvolve / FunSearch loop pairing Antigravity mutation with Zoe AST verification."""

    def __init__(
        self,
        *,
        verifier: ZoeDeterministicVerifier | None = None,
        mutator: AntigravityProgramMutator | None = None,
        archive: EvolutionaryArchive | None = None,
        blackboard: Any | None = None,
        seed: int = 42,
        num_islands: int = 3,
        offspring_per_gen: int = 8,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        probe_local: bool = False,
        bridge_mode: str | None = None,
    ) -> None:
        if bridge_mode is not None and bridge_mode not in VALID_MODES:
            raise ValueError(f"bridge_mode must be one of {VALID_MODES}, got {bridge_mode!r}")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError(f"seed must be an int, got {seed!r}")
        if isinstance(num_islands, bool) or not isinstance(num_islands, int) or num_islands < 1:
            raise ValueError(f"num_islands must be an int >= 1, got {num_islands!r}")
        if (
            isinstance(offspring_per_gen, bool)
            or not isinstance(offspring_per_gen, int)
            or offspring_per_gen < 1
        ):
            raise ValueError(
                f"offspring_per_gen must be an int >= 1, got {offspring_per_gen!r}"
            )
        self.offline_only = bool(offline_only)
        self.privacy_sensitive = bool(privacy_sensitive)
        self.probe_local = bool(probe_local)
        self.bridge_mode = bridge_mode
        self.verifier = verifier or ZoeDeterministicVerifier()
        if mutator is None:
            self.mutator = AntigravityProgramMutator(
                seed=seed,
                offline_only=self.offline_only,
                privacy_sensitive=self.privacy_sensitive,
                probe_local=self.probe_local,
                bridge_mode=self.bridge_mode,
            )
        else:
            if self.offline_only:
                mutator.offline_only = True
            if self.privacy_sensitive:
                mutator.privacy_sensitive = True
            if self.bridge_mode is not None and mutator.bridge_mode is None:
                mutator.bridge_mode = self.bridge_mode
            self.mutator = mutator
        self.archive = archive or EvolutionaryArchive(num_islands=num_islands)
        self.blackboard = blackboard
        self.seed = int(seed)
        self.offspring_per_gen = int(offspring_per_gen)
        self._rng = random.Random(self.seed)

    def _emit_blackboard_records(
        self,
        *,
        program: CandidateProgram,
        generation: int,
        blackboard: Any,
        out_log: list[dict[str, Any]],
    ) -> None:
        if blackboard is None or not hasattr(blackboard, "post_measurement"):
            return
        m_rec = _call_blackboard_post_measurement(
            blackboard,
            source="alpha_evolve",
            input_desc=f"{program.function_name} evaluated on {program.total_tests} deterministic test cases",
            metric_name=f"{program.function_name}.deterministic_score",
            value=float(program.score),
            scope=f"generation={generation};island={program.island_id};tests={program.total_tests}",
            method="GuardedFunctionASTSandbox + ZoeDeterministicVerifier",
            limitations="Bounded pure-function AST sandbox; finite deterministic test suite only.",
            sampled_only=False,
            metadata={
                "program_id": program.id,
                "code_sha256": program.code_sha256,
                "passed_tests": program.passed_tests,
                "total_tests": program.total_tests,
                "behavior_descriptor": list(program.behavior_descriptor),
            },
        )
        m_id = str(getattr(m_rec, "id", None) or getattr(m_rec, "measurement_id", None) or f"m_{program.id}")
        entry: dict[str, Any] = {
            "record_kind": "winner_measurement",
            "generation": generation,
            "program_id": program.id,
            "measurement_id": m_id,
            "promoted_to_evidence": False,
        }
        if (
            hasattr(blackboard, "promote_to_evidence")
            and program.total_tests > 0
            and program.passed_tests == program.total_tests
        ):
            ev_rec = _call_blackboard_promote(
                blackboard,
                measurement_id=m_id,
                verifier_name="ZoeDeterministicVerifier",
                passed=True,
                rationale=(
                    f"Deterministic AST & test verification: candidate {program.id} passed "
                    f"{program.passed_tests}/{program.total_tests} test cases (score={program.score})."
                ),
                evidence_source=EvidenceSource(
                    kind="tool",
                    identifier="ZoeDeterministicVerifier",
                    trust=0.95,
                    strength=0.95,
                ),
            )
            ev_id = str(getattr(ev_rec, "id", None) or getattr(ev_rec, "evidence_id", None) or f"ev_{program.id}")
            entry["record_kind"] = "winner_evidence"
            entry["promoted_to_evidence"] = True
            entry["passed"] = True
            entry["negative_result"] = False
            entry["evidence_id"] = ev_id
        out_log.append(entry)

    def _emit_negative_blackboard_evidence(
        self,
        *,
        generation: int,
        parent_id: str | None,
        rejection_kind: str,
        reason: str,
        code_sha256: str,
        blackboard: Any,
        out_log: list[dict[str, Any]],
    ) -> None:
        """Record rejected/unsafe mutations as explicit negative evidence (CONSTITUTION.md Art. II & III)."""
        if blackboard is None or not hasattr(blackboard, "post_measurement"):
            return
        m_rec = _call_blackboard_post_measurement(
            blackboard,
            source="alpha_evolve",
            input_desc=f"Rejected candidate sha256={code_sha256[:12]} (parent={parent_id or 'seed'})",
            metric_name="alpha_evolve.safety_gate_score",
            value=0.0,
            scope=f"generation={generation};rejection_kind={rejection_kind}",
            method="GuardedFunctionASTSandbox + ZoeDeterministicVerifier.verify_ast",
            limitations="Candidate rejected prior to execution; preserved as negative audit record.",
            sampled_only=False,
            metadata={
                "generation": generation,
                "parent_id": parent_id,
                "rejection_kind": rejection_kind,
                "code_sha256": code_sha256,
                "reason": reason,
            },
        )
        m_id = str(getattr(m_rec, "id", None) or getattr(m_rec, "measurement_id", None) or f"m_rej_{code_sha256[:8]}")
        entry: dict[str, Any] = {
            "record_kind": "negative_measurement",
            "generation": generation,
            "parent_id": parent_id,
            "rejection_kind": rejection_kind,
            "measurement_id": m_id,
            "promoted_to_evidence": False,
        }
        if hasattr(blackboard, "promote_to_evidence"):
            ev_rec = _call_blackboard_promote(
                blackboard,
                measurement_id=m_id,
                verifier_name="ZoeDeterministicVerifier",
                passed=False,
                rationale=(
                    f"Deterministic AST safety verification rejected candidate ({rejection_kind}): {reason}"
                ),
                evidence_source=EvidenceSource(
                    kind="tool",
                    identifier="ZoeDeterministicVerifier",
                    trust=0.95,
                    strength=0.95,
                ),
            )
            ev_id = str(getattr(ev_rec, "id", None) or getattr(ev_rec, "evidence_id", None) or f"ev_rej_{code_sha256[:8]}")
            entry["record_kind"] = "negative_evidence"
            entry["promoted_to_evidence"] = True
            entry["passed"] = False
            entry["negative_result"] = True
            entry["evidence_id"] = ev_id
        out_log.append(entry)

    def evolve(
        self,
        seed_programs: str | Sequence[str],
        test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]],
        *,
        function_name: str | None = None,
        arg_names: Sequence[str] | None = None,
        generations: int = 10,
        offspring_per_gen: int | None = None,
        prompt_context: str = "",
        behavior_fn: Callable[
            [str, Sequence[Any], Sequence[Any], Mapping[str, Any]], tuple[Any, ...]
        ]
        | None = None,
        emit_blackboard: bool = True,
        blackboard: Any | None = None,
    ) -> AlphaEvolveResult:
        """Run the AlphaEvolve / FunSearch evolutionary synthesis loop."""
        seeds = [seed_programs] if isinstance(seed_programs, str) else list(seed_programs)
        if not seeds:
            raise ValueError("seed_programs must contain at least one seed function")

        eff_blackboard = blackboard if blackboard is not None else self.blackboard
        offspring_n = self.offspring_per_gen if offspring_per_gen is None else max(1, int(offspring_per_gen))
        rejected_candidates: list[dict[str, Any]] = []
        generation_history: list[dict[str, Any]] = []
        blackboard_records: list[dict[str, Any]] = []

        exp_name = function_name
        exp_args = tuple(arg_names) if arg_names is not None else None
        seq_counter = 0

        # Evaluate and admit seed programs (Generation 0)
        valid_seeds = 0
        for idx, raw_seed in enumerate(seeds):
            report = self.verifier.evaluate(
                raw_seed,
                test_cases,
                expected_name=exp_name,
                expected_args=exp_args,
                behavior_fn=behavior_fn,
            )
            if not report.safe:
                reason_txt = report.error or "AST verification failed"
                rejected_candidates.append(
                    {
                        "generation": 0,
                        "parent_id": None,
                        "rejection_kind": "unsafe_ast",
                        "reason": reason_txt,
                        "code": raw_seed,
                        "code_sha256": report.code_sha256,
                        "recorded_utc": _utc_now_iso(),
                    }
                )
                if emit_blackboard:
                    self._emit_negative_blackboard_evidence(
                        generation=0,
                        parent_id=None,
                        rejection_kind="unsafe_ast",
                        reason=reason_txt,
                        code_sha256=report.code_sha256,
                        blackboard=eff_blackboard,
                        out_log=blackboard_records,
                    )
                continue

            if exp_name is None:
                exp_name = str(report.ast_metrics["function_name"])
            if exp_args is None:
                exp_args = tuple(report.ast_metrics["arg_names"])

            seq_counter += 1
            cand_id = f"prog_g0_{seq_counter}"
            island_id = idx % self.archive.num_islands
            cand = CandidateProgram(
                id=cand_id,
                code=raw_seed.strip(),
                function_name=exp_name,
                parent_id=None,
                generation=0,
                behavior_descriptor=report.behavior_descriptor,
                score=report.score,
                passed_tests=report.passed_tests,
                diff_from_parent="",
                provenance={"source": "seed", "recorded_utc": _utc_now_iso()},
                total_tests=report.total_tests,
                failures=report.failures,
                ast_metrics=dict(report.ast_metrics),
                code_sha256=report.code_sha256,
                island_id=island_id,
            )
            self.archive.insert(cand, island_id=island_id)
            valid_seeds += 1

        if valid_seeds == 0:
            raise UnsafeFunctionASTError(
                "All seed programs failed AST verification; cannot start AlphaEvolveLoop"
            )

        self.archive.record_snapshot(0)
        top_g0 = self.archive.top_k(1)[0]
        generation_history.append(
            {
                "generation": 0,
                "best_id": top_g0.id,
                "best_score": top_g0.score,
                "passed_tests": top_g0.passed_tests,
                "total_tests": top_g0.total_tests,
                "archive_diversity": self.archive.diversity_summary(),
                "accepted_offspring": valid_seeds,
                "rejected_offspring": len(rejected_candidates),
            }
        )
        if emit_blackboard:
            self._emit_blackboard_records(
                program=top_g0,
                generation=0,
                blackboard=eff_blackboard,
                out_log=blackboard_records,
            )

        # Evolutionary Generations 1..N
        for gen in range(1, max(0, int(generations)) + 1):
            migrated = self.archive.migrate(gen)
            accepted_in_gen = 0
            rejected_in_gen = 0

            for off_idx in range(offspring_n):
                island_id = off_idx % self.archive.num_islands
                # Balance exploitation (tournament on island elites) and diversity exploration (Boltzmann)
                if off_idx < max(1, offspring_n // 2):
                    elites = self.archive.island_elites(island_id)
                    if elites and off_idx < self.archive.num_islands:
                        parent = elites[0]
                    else:
                        parent = self.archive.sample_parent(
                            self._rng, island_id=island_id, strategy="tournament"
                        )
                else:
                    parent = self.archive.sample_parent(
                        self._rng, island_id=island_id, strategy="boltzmann"
                    )
                inspirations = self.archive.sample_inspirations(
                    self._rng, exclude_id=parent.id, k=2
                )
                mutation = self.mutator.mutate(
                    parent,
                    inspirations=inspirations,
                    failures=parent.failures,
                    prompt_context=prompt_context,
                    rng=self._rng,
                )
                report = self.verifier.evaluate(
                    mutation.code,
                    test_cases,
                    expected_name=exp_name,
                    expected_args=exp_args,
                    behavior_fn=behavior_fn,
                )
                if not report.safe:
                    rejected_in_gen += 1
                    reason_txt = report.error or "AST verification failed"
                    rejected_candidates.append(
                        {
                            "generation": gen,
                            "parent_id": parent.id,
                            "rejection_kind": "unsafe_ast",
                            "reason": reason_txt,
                            "code": mutation.code,
                            "code_sha256": report.code_sha256,
                            "provenance": dict(mutation.provenance),
                            "recorded_utc": _utc_now_iso(),
                        }
                    )
                    if emit_blackboard:
                        self._emit_negative_blackboard_evidence(
                            generation=gen,
                            parent_id=parent.id,
                            rejection_kind="unsafe_ast",
                            reason=reason_txt,
                            code_sha256=report.code_sha256,
                            blackboard=eff_blackboard,
                            out_log=blackboard_records,
                        )
                    continue

                seq_counter += 1
                cand_id = f"prog_g{gen}_{seq_counter}"
                diff_txt = unified_source_diff(
                    parent.code,
                    mutation.code.strip(),
                    from_label=f"{parent.id}.py",
                    to_label=f"{cand_id}.py",
                )
                cand = CandidateProgram(
                    id=cand_id,
                    code=mutation.code.strip(),
                    function_name=exp_name or str(report.ast_metrics["function_name"]),
                    parent_id=parent.id,
                    generation=gen,
                    behavior_descriptor=report.behavior_descriptor,
                    score=report.score,
                    passed_tests=report.passed_tests,
                    diff_from_parent=diff_txt,
                    provenance={
                        **mutation.provenance,
                        "mutation_source": mutation.source,
                        "mutation_operator": mutation.operator,
                        "inspiration_ids": [ins.id for ins in inspirations],
                        "recorded_utc": _utc_now_iso(),
                    },
                    total_tests=report.total_tests,
                    failures=report.failures,
                    ast_metrics=dict(report.ast_metrics),
                    code_sha256=report.code_sha256,
                    island_id=island_id,
                )
                admitted = self.archive.insert(cand, island_id=island_id)
                if admitted:
                    accepted_in_gen += 1
                else:
                    rejected_in_gen += 1
                    rejected_candidates.append(
                        {
                            "generation": gen,
                            "parent_id": parent.id,
                            "rejection_kind": "dominated_by_niche_elite",
                            "reason": (
                                f"Score {cand.score} did not beat niche elite for "
                                f"behavior {list(cand.behavior_descriptor)}"
                            ),
                            "code": cand.code,
                            "code_sha256": cand.code_sha256,
                            "score": cand.score,
                            "recorded_utc": _utc_now_iso(),
                        }
                    )

            self.archive.record_snapshot(gen)
            best_now = self.archive.top_k(1)[0]
            generation_history.append(
                {
                    "generation": gen,
                    "best_id": best_now.id,
                    "best_score": best_now.score,
                    "passed_tests": best_now.passed_tests,
                    "total_tests": best_now.total_tests,
                    "migrated": migrated,
                    "accepted_offspring": accepted_in_gen,
                    "rejected_offspring": rejected_in_gen,
                    "archive_diversity": self.archive.diversity_summary(),
                }
            )
            if emit_blackboard:
                self._emit_blackboard_records(
                    program=best_now,
                    generation=gen,
                    blackboard=eff_blackboard,
                    out_log=blackboard_records,
                )

        best_program = self.archive.top_k(1)[0]
        lineage = self.archive.get_lineage(best_program.id)
        return AlphaEvolveResult(
            best_program=best_program,
            archive=self.archive,
            lineage=lineage,
            rejected_candidates=rejected_candidates,
            generation_history=generation_history,
            blackboard_records=blackboard_records,
            constitutional=bridge_constitutional_metadata(cloud_tokens_used=0),
        )


__all__ = [
    "ALPHA_EVOLVE_CONTRACT",
    "AlphaEvolveLoop",
    "AlphaEvolveResult",
    "AntigravityProgramMutator",
    "CandidateProgram",
    "EvolutionaryArchive",
    "MutationOutcome",
    "TestCase",
    "VerificationReport",
    "ZoeDeterministicVerifier",
]

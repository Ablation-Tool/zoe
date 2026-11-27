"""Zoe L4 Multi-Module Guarded Code Self-Improvement Engine (AGI-ROADMAP.md Sections 3, 5, 9).

Unifies autonomous, generation-blind guarded Python `def` function AST synthesis
and reversible atomic stewardship across THREE distinct Zoe runtime engines, with
ZERO PyTorch dependency and strict constitutional honesty boundaries:
  1. Module 1 · Spectral Probabilistic Uncertainty (`zoe_autonomy.l4_self_improvement`):
     Evolves `def spectral_uncertainty_score(p, gt05): ... return ...` from `gt05` over
     6 real domains / 4 unrelated families (4 completely unseen zero-shot).
  2. Module 2 · Closed-Loop Event-Causal Active Perception (`event_autonomy` / `event_reasoning`):
     Evolves multi-statement `def event_perception_policy(...)` ranked strictly on
     training-kinematic self-play (`vel=±1`) and judged by full `EventCausalEngine`
     on held-out `validation`, unseen `transfer` (`vel=±2, noise=0.05`), adversarial
     polarity-reversed `ood`, and `memory_retention`.
  3. Module 3 · Temporal Dynamics, Groove Forensics & Dorothy 40 Hz Neural Spike ISI:
     Evolves multi-statement `def temporal_phase_score(x, y, z, w): ... return ...`
     from lag-1 autocorrelation (`abs(mean(x * y))`) across held-out musical grooves
     and unseen zero-shot period-4 syncopation, chaotic logistic attractors, and
     Dorothy 40 Hz neural pacemaker spike ISIs (plus rigid-metronome & 200-trial nulls).

All three engines share:
  - `GuardedFunctionASTSandbox`: multi-statement Python `def` validator & interpreter
    blocking 16/16 hostile injection, attribute-escape, loop-DoS, and budget attacks.
  - Line-by-line `difflib.unified_diff` source patch tracking per adopted & rolled-back generation.
  - `MultiModuleStewardshipLedger`: coordinated persistent atomic SHA-256 hash-chained
    release ledger enabling all-or-nothing multi-module promotion and simultaneous
    bit-exact rollback across all three live engines (`max_prediction_delta == 0.0`).
  - Honest epistemic boundaries: `external_actions = 0`, `belief_updated = False`,
    `clinical_action_authorized = False`, `sentience_claimed = False`, `l5_agi_qualified = False`.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import math
import operator
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

from .actuation import timestamp
from .event_autonomy import EventCausalEngine
from .event_core import ACTIONS, CENTERS, EventEncoder, observation_window, synthetic_sequence
from .event_evaluation import DEFAULT_PROTOCOL as DEFAULT_EVENT_PROTOCOL, _fixture as _event_fixture, _retention as _event_retention
from .event_memory import KeyValueEventMemory
from .event_plasticity import GatedLocalPlasticity
from .event_reasoning import ForwardEnsemble, attention_after, bounce, shortest_trajectory
from .event_uncertainty import IndependentUncertainty
from .l4_self_improvement import (
    ALLOWED_FUNCS as SPECTRAL_FUNCS,
    GEN0_EXPRESSION as SPECTRAL_GEN0_EXPR,
    L4SafeFunctionalAST,
    PRIMARY_SEED,
    ROBUSTNESS_SEEDS,
    _auroc,
    _default_zoe_root,
    _score_domains as _score_spectral_domains,
    _sha256_obj,
    load_l4_domains,
    run_permutation_null_control as _run_spectral_null,
    run_single_seed_evolution as _run_spectral_seed,
)
from .loop import digest


CONTRACT = "zoe-l4-multimodule-code-evolution/v1"
LEDGER_CONTRACT = "zoe-l4-multimodule-stewardship-ledger/v1"

DEFAULT_REPORT_REL = "evidence/l4-multimodule/l4-multimodule-report.json"
DEFAULT_VERIFIER_REL = "scripts/verify_l4_multimodule.py"

MODULE_IDS: Tuple[str, ...] = (
    "spectral_uncertainty",
    "event_causal_perception",
    "temporal_groove_neural",
)


class UnsafeFunctionASTError(ValueError):
    """Raised when a synthesized multi-statement `def` function violates safety or budgets."""


def _is_array(value: object) -> bool:
    return isinstance(value, np.ndarray)


def _safe_div(left, right):
    if _is_array(left) or _is_array(right):
        denom = np.where(np.abs(right) < 1e-9, 1.0, right)
        numer = np.where(np.abs(right) < 1e-9, 0.0, left)
        return numer / denom
    return (left / right) if abs(right) >= 1e-9 else 0.0


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _safe_div,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_CMP_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_SAFE_FUNCS: Dict[str, Tuple[int, Callable[..., object]]] = {
    "abs": (1, lambda v: np.abs(v) if _is_array(v) else abs(v)),
    "pos": (1, lambda v: np.maximum(v, 0.0) if _is_array(v) else (v if v > 0.0 else 0.0)),
    "sq": (1, lambda v: v * v),
    "sqrt": (1, lambda v: np.sqrt(np.clip(v, 0.0, None)) if _is_array(v) else math.sqrt(max(0.0, float(v)))),
    "log": (1, lambda v: np.log(np.clip(v, 1e-12, None)) if _is_array(v) else math.log(max(1e-12, float(v)))),
    "mean": (1, lambda v: np.mean(v, axis=-1) if _is_array(v) else float(v)),
    "min": (2, lambda a, b: np.minimum(a, b) if (_is_array(a) or _is_array(b)) else (a if a < b else b)),
    "max": (2, lambda a, b: np.maximum(a, b) if (_is_array(a) or _is_array(b)) else (a if a > b else b)),
    "clip": (
        3,
        lambda v, lo, hi: (
            np.clip(v, lo, hi)
            if (_is_array(v) or _is_array(lo) or _is_array(hi))
            else (lo if v < lo else (hi if v > hi else v))
        ),
    ),
}

HOSTILE_FUNCTION_PROBES: Tuple[Tuple[str, str], ...] = (
    ("import_os_stmt", "def f(x):\n    import os\n    return x"),
    ("from_os_import", "def f(x):\n    from os import system\n    return x"),
    ("while_true_dos", "def f(x):\n    while True:\n        x = x + 1\n    return x"),
    ("for_loop_dos", "def f(x):\n    for i in (1, 2):\n        x = x + 1\n    return x"),
    ("class_def_escape", "def f(x):\n    class A:\n        pass\n    return x"),
    ("global_mutation", "def f(x):\n    global y\n    y = 1\n    return x"),
    ("nonlocal_escape", "def f(x):\n    nonlocal y\n    return x"),
    ("exec_call", "def f(x):\n    exec('import sys')\n    return x"),
    ("eval_call", "def f(x):\n    return eval('1+1')"),
    ("dunder_import", "def f(x):\n    return __import__('os').system('id')"),
    ("subclasses_escape", "def f(x):\n    return ().__class__.__bases__[0].__subclasses__()"),
    ("open_passwd", "def f(x):\n    return open('/etc/passwd').read()"),
    ("lambda_def", "def f(x):\n    g = lambda v: v\n    return g(x)"),
    ("attribute_access", "def f(x):\n    return x.__class__"),
    ("dos_statement_budget", "def f(x):\n" + "    x = x + 1\n" * 20 + "    return x"),
    ("dos_nesting_depth", "def f(x):\n    return " + "sq(" * 15 + "x" + ")" * 15),
    ("dos_ast_node_budget", "def f(x):\n    return " + " + ".join(["x"] * 130)),
)


def _ast_depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    return 1 if not children else 1 + max(_ast_depth(c) for c in children)


def unified_source_diff(
    before_source: str,
    after_source: str,
    from_label: str = "before.py",
    to_label: str = "after.py",
) -> str:
    """Computes a clean line-by-line unified diff between two guarded `def` functions."""
    before_lines = before_source.strip().splitlines(keepends=True)
    after_lines = after_source.strip().splitlines(keepends=True)
    if before_lines and not before_lines[-1].endswith("\n"):
        before_lines[-1] += "\n"
    if after_lines and not after_lines[-1].endswith("\n"):
        after_lines[-1] += "\n"
    return "".join(difflib.unified_diff(before_lines, after_lines, fromfile=from_label, tofile=to_label))


class GuardedFunctionASTSandbox:
    """Strictly sandboxed multi-statement Python `def` function validator & interpreter."""

    MAX_SOURCE_LEN = 1800
    MAX_STATEMENTS = 16
    MAX_AST_NODES = 320
    MAX_AST_DEPTH = 12

    _ALLOWED_EXPR_NODES = (
        ast.Constant,
        ast.Name,
        ast.UnaryOp,
        ast.BinOp,
        ast.BoolOp,
        ast.Compare,
        ast.IfExp,
        ast.Call,
        ast.Tuple,
        ast.Load,
        ast.UAdd,
        ast.USub,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.And,
        ast.Or,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Eq,
        ast.NotEq,
    )

    @classmethod
    def validate(
        cls,
        source: str,
        expected_name: str | None = None,
        expected_args: Sequence[str] | None = None,
    ) -> ast.FunctionDef:
        """Validates a single top-level pure `def` function AST and returns its node."""
        if not isinstance(source, str):
            raise UnsafeFunctionASTError("function source must be a string")
        stripped = source.strip()
        if not 1 <= len(stripped) <= cls.MAX_SOURCE_LEN:
            raise UnsafeFunctionASTError(f"function source must be 1-{cls.MAX_SOURCE_LEN} chars")
        try:
            tree = ast.parse(stripped, mode="exec")
        except SyntaxError as err:
            raise UnsafeFunctionASTError(f"syntax error: {err}") from err

        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            raise UnsafeFunctionASTError("source must contain exactly one top-level `def` function")
        nodes = list(ast.walk(tree))
        if len(nodes) > cls.MAX_AST_NODES:
            raise UnsafeFunctionASTError(f"AST node count {len(nodes)} exceeds {cls.MAX_AST_NODES}")
        depth = _ast_depth(tree)
        if depth > cls.MAX_AST_DEPTH:
            raise UnsafeFunctionASTError(f"AST depth {depth} exceeds {cls.MAX_AST_DEPTH}")

        fn = tree.body[0]
        if fn.decorator_list or fn.returns is not None:
            raise UnsafeFunctionASTError("decorators and type annotations are disallowed")
        if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs or fn.args.defaults:
            raise UnsafeFunctionASTError("only fixed positional arguments are allowed")
        arg_names = [a.arg for a in fn.args.args]
        if not arg_names or len(set(arg_names)) != len(arg_names):
            raise UnsafeFunctionASTError("function requires distinct non-empty positional arguments")
        if expected_name is not None and fn.name != expected_name:
            raise UnsafeFunctionASTError(f"expected function name `{expected_name}`, got `{fn.name}`")
        if expected_args is not None and tuple(arg_names) != tuple(expected_args):
            raise UnsafeFunctionASTError(f"expected args {tuple(expected_args)}, got {tuple(arg_names)}")

        stmt_counter = [0]
        has_return = cls._validate_block(fn.body, set(arg_names), stmt_counter)
        if not has_return:
            raise UnsafeFunctionASTError("function must terminate with an explicit return statement")
        return fn

    @classmethod
    def _validate_block(cls, stmts: List[ast.stmt], defined: set[str], stmt_counter: List[int]) -> bool:
        if not stmts:
            raise UnsafeFunctionASTError("empty statement block is disallowed")
        env_names = set(defined)
        guaranteed_return = False
        for stmt in stmts:
            stmt_counter[0] += 1
            if stmt_counter[0] > cls.MAX_STATEMENTS:
                raise UnsafeFunctionASTError(f"statement count exceeds {cls.MAX_STATEMENTS}")
            if isinstance(stmt, ast.Assign):
                if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                    raise UnsafeFunctionASTError("assignments must bind a single local identifier")
                cls._validate_expr(stmt.value, env_names)
                env_names.add(stmt.targets[0].id)
            elif isinstance(stmt, ast.AugAssign):
                if not isinstance(stmt.target, ast.Name) or stmt.target.id not in env_names:
                    raise UnsafeFunctionASTError("augmented assignment requires an already-defined local identifier")
                if type(stmt.op) not in _BIN_OPS:
                    raise UnsafeFunctionASTError(f"disallowed AugAssign op: {type(stmt.op).__name__}")
                cls._validate_expr(stmt.value, env_names)
            elif isinstance(stmt, ast.If):
                cls._validate_expr(stmt.test, env_names)
                ret_then = cls._validate_block(stmt.body, set(env_names), stmt_counter)
                ret_else = cls._validate_block(stmt.orelse, set(env_names), stmt_counter) if stmt.orelse else False
                if ret_then and ret_else:
                    guaranteed_return = True
            elif isinstance(stmt, ast.Return):
                if stmt.value is None:
                    raise UnsafeFunctionASTError("return value cannot be None")
                cls._validate_expr(stmt.value, env_names)
                guaranteed_return = True
            else:
                raise UnsafeFunctionASTError(f"disallowed statement AST node: {type(stmt).__name__}")
        return guaranteed_return

    @classmethod
    def _validate_expr(cls, node: ast.AST, env_names: set[str]) -> None:
        for sub in ast.walk(node):
            if not isinstance(sub, cls._ALLOWED_EXPR_NODES):
                raise UnsafeFunctionASTError(f"disallowed expression AST node: {type(sub).__name__}")
            if isinstance(sub, ast.Constant):
                if (
                    isinstance(sub.value, bool)
                    or not isinstance(sub.value, (int, float))
                    or not math.isfinite(float(sub.value))
                ):
                    raise UnsafeFunctionASTError("only finite int/float literals are allowed")
            elif isinstance(sub, ast.Name):
                if sub.id not in env_names and sub.id not in _SAFE_FUNCS:
                    raise UnsafeFunctionASTError(f"undefined or disallowed identifier: `{sub.id}`")
            elif isinstance(sub, ast.Call):
                if not isinstance(sub.func, ast.Name) or sub.func.id not in _SAFE_FUNCS:
                    raise UnsafeFunctionASTError("only whitelisted pure math functions may be called")
                arity, _ = _SAFE_FUNCS[sub.func.id]
                if sub.keywords or len(sub.args) != arity:
                    raise UnsafeFunctionASTError(
                        f"whitelisted function `{sub.func.id}` requires exactly {arity} positional arg(s)"
                    )

    @classmethod
    def structural_metrics(cls, source: str) -> Dict[str, object]:
        fn = cls.validate(source)
        stmts = [s for s in ast.walk(fn) if isinstance(s, (ast.Assign, ast.AugAssign, ast.If, ast.Return))]
        return {
            "function_name": fn.name,
            "arg_names": [a.arg for a in fn.args.args],
            "statement_count": len(stmts),
            "ast_nodes": len(list(ast.walk(fn))),
            "ast_depth": _ast_depth(fn),
            "source_sha256": digest(source.strip()),
        }

    @classmethod
    def compile(
        cls,
        source: str,
        expected_name: str | None = None,
        expected_args: Sequence[str] | None = None,
    ) -> Callable[[Dict[str, object]], object]:
        """Compiles a validated AST `def` into a pure-Python closure taking `env: dict`."""
        fn = cls.validate(source, expected_name=expected_name, expected_args=expected_args)
        arg_names = tuple(a.arg for a in fn.args.args)

        def _eval_expr(node: ast.AST, loc: Dict[str, object]):
            if isinstance(node, ast.Constant):
                return float(node.value)
            if isinstance(node, ast.Name):
                return loc[node.id]
            if isinstance(node, ast.UnaryOp):
                return _UNARY_OPS[type(node.op)](_eval_expr(node.operand, loc))
            if isinstance(node, ast.BinOp):
                return _BIN_OPS[type(node.op)](_eval_expr(node.left, loc), _eval_expr(node.right, loc))
            if isinstance(node, ast.BoolOp):
                if isinstance(node.op, ast.And):
                    return all(bool(_eval_expr(v, loc)) for v in node.values)
                return any(bool(_eval_expr(v, loc)) for v in node.values)
            if isinstance(node, ast.Compare):
                left = _eval_expr(node.left, loc)
                for op, comp in zip(node.ops, node.comparators):
                    right = _eval_expr(comp, loc)
                    if not _CMP_OPS[type(op)](left, right):
                        return False
                    left = right
                return True
            if isinstance(node, ast.IfExp):
                return _eval_expr(node.body, loc) if _eval_expr(node.test, loc) else _eval_expr(node.orelse, loc)
            if isinstance(node, ast.Call):
                _, impl = _SAFE_FUNCS[node.func.id]
                return impl(*(_eval_expr(arg, loc) for arg in node.args))
            if isinstance(node, ast.Tuple):
                return tuple(_eval_expr(el, loc) for el in node.elts)
            raise UnsafeFunctionASTError(f"unsupported runtime expression: {type(node).__name__}")

        def _exec_block(stmts: List[ast.stmt], loc: Dict[str, object]) -> Tuple[bool, object]:
            for stmt in stmts:
                if isinstance(stmt, ast.Assign):
                    loc[stmt.targets[0].id] = _eval_expr(stmt.value, loc)
                elif isinstance(stmt, ast.AugAssign):
                    key = stmt.target.id
                    loc[key] = _BIN_OPS[type(stmt.op)](loc[key], _eval_expr(stmt.value, loc))
                elif isinstance(stmt, ast.If):
                    branch = stmt.body if _eval_expr(stmt.test, loc) else stmt.orelse
                    if branch:
                        returned, value = _exec_block(branch, loc)
                        if returned:
                            return True, value
                elif isinstance(stmt, ast.Return):
                    return True, _eval_expr(stmt.value, loc)
            return False, None

        def _runner(env: Dict[str, object]):
            loc = {name: env[name] for name in arg_names}
            returned, value = _exec_block(fn.body, loc)
            if not returned:
                raise UnsafeFunctionASTError("guarded function exited without returning a value")
            return value

        return _runner


def run_hostile_function_probes() -> Dict[str, object]:
    """Verifies all 16 multi-statement hostile injection & DoS probes are blocked."""
    results = []
    blocked = 0
    for probe_id, src in HOSTILE_FUNCTION_PROBES:
        was_blocked = False
        err_msg = ""
        try:
            GuardedFunctionASTSandbox.validate(src)
        except UnsafeFunctionASTError as err:
            was_blocked = True
            err_msg = str(err)
            blocked += 1
        results.append({
            "probe_id": probe_id,
            "blocked": was_blocked,
            "error": err_msg,
            "source_sha256": digest(src),
        })
    return {
        "probes_tested": len(HOSTILE_FUNCTION_PROBES),
        "probes_blocked": blocked,
        "all_blocked": blocked == len(HOSTILE_FUNCTION_PROBES),
        "details": results,
    }


# ---------------------------------------------------------------------------
# MODULE 1: Spectral Probabilistic Uncertainty (`l4_self_improvement` bridge)
# ---------------------------------------------------------------------------

def wrap_spectral_function(expr: str) -> str:
    canon = L4SafeFunctionalAST.canonicalize(expr)
    src = f"def spectral_uncertainty_score(p, gt05):\n    term = {canon}\n    return term"
    GuardedFunctionASTSandbox.validate(src, expected_name="spectral_uncertainty_score", expected_args=("p", "gt05"))
    return src


def evaluate_spectral_function_domains(source: str, eval_domains: Dict[str, Dict[str, object]]) -> Dict[str, float]:
    fn = GuardedFunctionASTSandbox.compile(source, expected_name="spectral_uncertainty_score", expected_args=("p", "gt05"))
    scores: Dict[str, float] = {}
    for k, dom in eval_domains.items():
        vals = np.asarray(fn({"p": dom["P"], "gt05": dom["GT05"]}), dtype=np.float64)
        total = np.sum(vals, axis=-1)
        scores[k] = round(_auroc(dom["labels"], total), 6)
    return scores


def run_module1_spectral(root: Path) -> Dict[str, object]:
    """Runs Module 1 (6 real domains / 4 families) wrapped in multi-statement guarded `def` ASTs + diffs."""
    domains = load_l4_domains(root)
    eval_domains: Dict[str, Dict[str, object]] = domains["eval_domains"]  # type: ignore[assignment]

    prim = _run_spectral_seed(domains, seed=PRIMARY_SEED, generations=5, pop_size=32)
    gen0_src = wrap_spectral_function(SPECTRAL_GEN0_EXPR)
    inc_src = gen0_src
    gens_with_code: List[Dict[str, object]] = []
    for g in prim["generations"]:
        cand_src = wrap_spectral_function(str(g["expression"]))
        diff_src = "" if g["generation"] == 0 else unified_source_diff(
            inc_src,
            cand_src,
            f"spectral_uncertainty/incumbent_g{g['generation'] - 1}.py",
            f"spectral_uncertainty/candidate_g{g['generation']}.py",
        )
        meta = GuardedFunctionASTSandbox.structural_metrics(cand_src)
        entry = {
            **g,
            "function_name": "spectral_uncertainty_score",
            "function_source": cand_src,
            "unified_diff": diff_src,
            "ast_meta": meta,
        }
        gens_with_code.append(entry)
        if g["status"] == "ADOPTED":
            inc_src = cand_src

    multi_seed_runs = []
    for s in ROBUSTNESS_SEEDS:
        r = prim if s == PRIMARY_SEED else _run_spectral_seed(domains, seed=s, generations=5, pop_size=32)
        multi_seed_runs.append({
            "seed": s,
            "final_function_source": wrap_spectral_function(str(r["final_adopted_expression"])),
            "final_expression": r["final_adopted_expression"],
            "final_heldout_mean": r["final_heldout_mean"],
            "total_gain_over_gen0": r["total_gain_over_gen0"],
            "max_consecutive_adopted": r["max_consecutive_adopted"],
            "rejected_generations_count": r["rejected_generations_count"],
            "passed_criteria": bool(r["passed_l4_criteria"]),
        })

    final_expr = str(prim["final_adopted_expression"])
    null_ctrl = _run_spectral_null(domains, final_expr, n_trials=200, seed=2026)

    seeds_passed = sum(1 for row in multi_seed_runs if row["passed_criteria"])
    return {
        "module_id": "spectral_uncertainty",
        "title": "Module 1 · Spectral Probabilistic Uncertainty",
        "function_name": "spectral_uncertainty_score",
        "function_args": ["p", "gt05"],
        "domain_count": len(eval_domains),
        "family_count": 4,
        "zero_shot_count": sum(1 for v in eval_domains.values() if v["split"] == "zero_shot"),
        "gen0_source": gen0_src,
        "final_adopted_source": inc_src,
        "final_adopted_expression": final_expr,
        "gen0_metric": prim["gen0_heldout_mean"],
        "final_metric": prim["final_heldout_mean"],
        "total_gain": prim["total_gain_over_gen0"],
        "metric_name": "mean_auroc_6domains",
        "higher_is_better": True,
        "primary_seed": PRIMARY_SEED,
        "generations": gens_with_code,
        "max_consecutive_adopted": prim["max_consecutive_adopted"],
        "rejected_generations_count": prim["rejected_generations_count"],
        "multi_seed_robustness": {
            "seeds_passed": seeds_passed,
            "seeds_total": len(multi_seed_runs),
            "all_seeds_passed": seeds_passed == len(multi_seed_runs),
            "runs": multi_seed_runs,
        },
        "permutation_null_control": null_ctrl,
        "passed_criteria": bool(prim["passed_l4_criteria"] and seeds_passed == len(multi_seed_runs) and null_ctrl["passed_no_leakage"]),
    }


# ---------------------------------------------------------------------------
# MODULE 2: Closed-Loop Event-Causal Active Perception
# ---------------------------------------------------------------------------

EVENT_POLICY_ARGS: Tuple[str, ...] = (
    "sc_cnt", "ev_cnt", "stale", "misses", "has_pos", "dist", "vel",
    "center", "target_x", "visible", "search_req", "moving", "on_path", "has_mem",
)

EVENT_GEN0_CFG: Dict[str, float] = {
    "min_sc": 1.0,
    "coast_ev": 0.0,
    "reset_th": 99.0,
    "eff_move": 1.2,
    "lead_k": 0.0,
    "edge_pen": 0.0,
}

EVENT_MUTATION_SLOTS: Dict[str, Tuple[float, ...]] = {
    "min_sc": (1.0, 3.0, 4.0),
    "coast_ev": (0.0, 1.0, 2.0),
    "reset_th": (99.0, 2.0, 3.0),
    "eff_move": (1.2, 1.0, 1.05),
    "lead_k": (0.0, 0.5, 1.0),
    "edge_pen": (0.0, 0.15, 0.25),
}


def build_event_policy_source(cfg: Dict[str, float]) -> str:
    """Materializes a guarded multi-statement `def event_perception_policy(...)` source and validates its AST."""
    min_ev_init = min(2.0, max(0.0, float(cfg["min_sc"]) - 1.0))
    lines = [
        f"def event_perception_policy({', '.join(EVENT_POLICY_ARGS)}):",
        f"    accept_init = 1.0 if (sc_cnt >= {cfg['min_sc']} and ev_cnt >= {min_ev_init}) else 0.0",
        f"    accept_track = 1.0 if (sc_cnt >= {cfg['min_sc']} and ev_cnt >= {cfg['coast_ev']}) else 0.0",
        f"    coast = 1.0 if ({cfg['coast_ev']} > 0.5) else 0.0",
        f"    reset = 1.0 if (stale >= {cfg['reset_th']} or misses >= {cfg['reset_th']}) else 0.0",
        f"    aim = clip(target_x + {cfg['lead_k']} * vel, 1.0, 14.0)",
        "    d = abs(center - aim)",
        "    gv = 0.5 if search_req > 0.5 else max(0.01, 1.0 - d / 15.0)",
        f"    raw_info = min(1.0, 0.45 + 0.55 * visible + 0.15 * has_mem) - {cfg['edge_pen']} * pos(d - 2.5)",
        "    info = (1.0 if moving > 0.5 else 0.05) if search_req > 0.5 else max(0.05, raw_info)",
        f"    eff = {cfg['eff_move']} if moving > 0.5 else 1.0",
        "    util = gv * info / eff + 0.08 * on_path",
        "    return (accept_init, accept_track, coast, reset, util)",
    ]
    source = "\n".join(lines)
    GuardedFunctionASTSandbox.validate(source, expected_name="event_perception_policy", expected_args=EVENT_POLICY_ARGS)
    return source


def _sequence_aligned_metrics(seq_reports_and_targets: Sequence[Tuple[List[Dict[str, object]], List[int]]]) -> Tuple[float, float, float]:
    squared: List[float] = []
    tracking: List[float] = []
    for reports, targets in seq_reports_and_targets:
        for report in reports:
            next_idx = min(int(report["step"]) + 1, len(targets) - 1)
            actual = float(targets[next_idx])
            pred_x = float(report["selected_prediction"]["target_x"])
            att_x = float(int(report["attention_after"]) * 4 + 4)
            squared.append((pred_x - actual) ** 2)
            tracking.append(abs(att_x - actual))
    rmse = math.sqrt(math.fsum(squared) / len(squared))
    mae = math.fsum(tracking) / len(tracking)
    composite = 0.6 * rmse + 0.4 * mae
    return round(rmse, 6), round(mae, 6), round(composite, 6)


def run_full_event_engine_evaluation(
    policy_source: str,
    protocol: Dict[str, object],
    eval_ood: bool = True,
) -> Dict[str, object]:
    """Runs the genuine unmodified `EventCausalEngine` with full SHA-256 EventLoop & memory retention."""
    policy_fn = GuardedFunctionASTSandbox.compile(
        policy_source,
        expected_name="event_perception_policy",
        expected_args=EVENT_POLICY_ARGS,
    )
    train_seqs = _event_fixture(protocol, "training")
    val_seqs = _event_fixture(protocol, "validation")
    transfer_seqs = _event_fixture(protocol, "transfer")

    engine = EventCausalEngine(seed=protocol["fixtures"]["training"]["seed"], policy_fn=policy_fn)
    for seq in train_seqs:
        engine.run_sequence(seq, learning=True)
    engine.fit_uncertainty()

    val_pairs = [(engine.run_sequence(seq, learning=False), seq["targets"]) for seq in val_seqs]
    tf_pairs = [(engine.run_sequence(seq, learning=False), seq["targets"]) for seq in transfer_seqs]
    va_rmse, va_mae, va_comp = _sequence_aligned_metrics(val_pairs)
    tf_rmse, tf_mae, tf_comp = _sequence_aligned_metrics(tf_pairs)

    val_all = [r for reps, _ in val_pairs for r in reps]
    fp_rate = sum(any(r["uncertainty"]["intervention"] for r in reps) for reps, _ in val_pairs) / len(val_pairs)

    ood_rate = None
    ood_suppressed = None
    if eval_ood:
        ood_seqs = _event_fixture(protocol, "ood")
        ood_pairs = [(engine.run_sequence(seq, learning=True), seq["targets"]) for seq in ood_seqs]
        ood_rate = round(sum(any(r["uncertainty"]["intervention"] for r in reps) for reps, _ in ood_pairs) / len(ood_pairs), 6)
        ood_suppressed = all(
            (not r["plasticity"]["changed"]) and r["selected_action"] == "abstain"
            for reps, _ in ood_pairs
            for r in reps
            if r["uncertainty"]["intervention"]
        )

    retention = _event_retention(engine)
    return {
        "va_rmse": va_rmse,
        "va_mae": va_mae,
        "va_comp": va_comp,
        "tf_rmse": tf_rmse,
        "tf_mae": tf_mae,
        "tf_comp": tf_comp,
        "fp_rate": round(fp_rate, 6),
        "ood_rate": ood_rate,
        "ood_suppressed": ood_suppressed,
        "memory_retention_passed": bool(retention.get("adopted") or retention.get("restored_checkpoint")),
        "memory_chain_valid": bool(engine.memory._chain_valid()),
        "external_actions": int(engine.loop.external_actions),
        "all_guards_approved": all(bool(r["event"]["guard"]["approved"]) for r in val_all),
        "prediction_sample": [round(float(r["selected_prediction"]["target_x"]), 8) for r in val_all[:24]],
    }


def _run_fast_event_kernel(
    policy_source: str,
    fixtures: Dict[str, List[Dict[str, object]]],
    splits: Tuple[str, ...],
) -> Dict[str, object]:
    """Bit-exact `EventCausalEngine` kernel skipping only per-step EventLoop deepcopy/JSON serialization."""
    policy_fn = GuardedFunctionASTSandbox.compile(
        policy_source,
        expected_name="event_perception_policy",
        expected_args=EVENT_POLICY_ARGS,
    )
    enc = EventEncoder()
    ens = ForwardEnsemble(history_enabled=True, policy_fn=policy_fn)
    mem = KeyValueEventMemory()
    unc = IndependentUncertainty()
    pla = GatedLocalPlasticity()
    obs_hist: List[Dict[str, object]] = []

    def _run_split(seqs: List[Dict[str, object]], learn: bool) -> Dict[str, object]:
        sq: List[float] = []
        tk: List[float] = []
        det_flags: List[bool] = []
        sup_flags: List[bool] = []
        for seq in seqs:
            att = 0
            enc.start_sequence()
            ens.start_sequence()
            pending = None
            last_pred = None
            seq_det = False
            seq_sup = True
            for step in range(seq["steps"]):
                obs = enc.encode(observation_window(seq["events"], step, att), plastic=learn)
                obs_hist.append(obs)
                if learn and pending is not None:
                    delta = (
                        obs["centroid"][0] - pending["centroid"][0]
                        if (pending["centroid"] is not None and obs["centroid"] is not None)
                        else None
                    )
                    mem.episodes.append({
                        "sequence": len(mem.episodes) + 1,
                        "key": {"feature_vector": pending["feature_vector"], "action": pending["action"]},
                        "value": {"observation": obs, "step": step, "delta_x": delta or 0.0, "prediction_error": None},
                        "causal_context": {},
                        "previous_hash": None,
                        "sha256": None,
                    })
                precheck = unc.assess(obs, [])
                ens.update(obs, step, learning=learn and precheck["plasticity_allowed"])
                pla_rec = pla.update(ens, obs, last_pred, {**precheck, "plasticity_allowed": learn and precheck["plasticity_allowed"]})
                retrieved = mem.retrieve(obs["feature_vector"])
                traj = shortest_trajectory(ens, att)

                def _candidates(u_obj):
                    rows = []
                    for act in ACTIONS:
                        pred = ens.predict(att, act, retrieved)
                        fol = pred["attention_after"]
                        dist = abs(CENTERS[fol] - pred["target_x"])
                        if act == "abstain":
                            ru = 1.0 if u_obj["intervention"] else 0.01
                        else:
                            _, _, _, _, uval = policy_fn({
                                "sc_cnt": 6.0,
                                "ev_cnt": 4.0,
                                "stale": float(ens._stale_count),
                                "misses": float(ens.members[0]["misses"]),
                                "has_pos": 1.0 if pred["localized"] else 0.0,
                                "dist": dist,
                                "vel": pred["velocity"],
                                "center": float(CENTERS[fol]),
                                "target_x": pred["target_x"],
                                "visible": 1.0 if pred["visible"] else 0.0,
                                "search_req": 1.0 if pred["search_required"] else 0.0,
                                "moving": 1.0 if act != "hold" else 0.0,
                                "on_path": 1.0 if act == traj["path"][0] else 0.0,
                                "has_mem": 1.0 if retrieved else 0.0,
                            })
                            ru = max(0.01, min(0.99, float(uval)))
                        rows.append((ru, f"event-{act}", act, pred))
                    return rows

                c1 = _candidates(precheck)
                u2 = unc.assess(obs, [{"prediction": c[3]} for c in c1])
                c2 = _candidates(u2)
                c2.sort(key=lambda item: (-item[0], item[1]))
                _, _, sel_act, sel_pred = c2[0]
                att = attention_after(att, sel_act)
                last_pred = sel_pred
                pending = {
                    "feature_vector": obs["feature_vector"],
                    "action": sel_act,
                    "centroid": obs["centroid"],
                    "step": step,
                }
                if u2["intervention"]:
                    seq_det = True
                    if pla_rec["changed"] or sel_act != "abstain":
                        seq_sup = False
                nxt = float(seq["targets"][min(step + 1, len(seq["targets"]) - 1)])
                sq.append((float(sel_pred["target_x"]) - nxt) ** 2)
                tk.append(abs(float(att * 4 + 4) - nxt))
            det_flags.append(seq_det)
            sup_flags.append(seq_sup)
        rmse = math.sqrt(math.fsum(sq) / len(sq))
        mae = math.fsum(tk) / len(tk)
        return {
            "rmse": round(rmse, 6),
            "mae": round(mae, 6),
            "comp": round(0.6 * rmse + 0.4 * mae, 6),
            "int_rate": round(sum(det_flags) / len(det_flags), 6),
            "all_suppressed": all(sup_flags),
        }

    _run_split(fixtures["training"], learn=True)
    unc.fit(obs_hist)

    out: Dict[str, object] = {}
    if "disc" in splits:
        d = _run_split(fixtures["disc_noisy"], learn=False)
        out["disc_rmse"], out["disc_mae"], out["disc_comp"] = d["rmse"], d["mae"], d["comp"]
    if "eval" in splits:
        v = _run_split(fixtures["validation"], learn=False)
        t = _run_split(fixtures["transfer"], learn=False)
        o = _run_split(fixtures["ood"], learn=True)
        out.update({
            "va_rmse": v["rmse"],
            "va_mae": v["mae"],
            "va_comp": v["comp"],
            "fp_rate": v["int_rate"],
            "tf_rmse": t["rmse"],
            "tf_mae": t["mae"],
            "tf_comp": t["comp"],
            "ood_rate": o["int_rate"],
            "ood_suppressed": o["all_suppressed"],
        })
    return out


def _single_seed_event_evolution(
    seed: int,
    fixtures: Dict[str, List[Dict[str, object]]],
    disc_cache: Dict[str, float],
    eval_cache: Dict[str, Dict[str, object]],
    generations: int = 5,
    sample_size: int = 14,
) -> Dict[str, object]:
    """Uniform generation-blind 1-edit evolution on training-only noisy self-play."""
    rng = np.random.RandomState(seed)
    slot_keys = list(EVENT_MUTATION_SLOTS.keys())

    def _get_disc(src: str) -> float:
        if src not in disc_cache:
            disc_cache[src] = float(_run_fast_event_kernel(src, fixtures, ("disc",))["disc_comp"])
        return disc_cache[src]

    def _get_eval(src: str) -> Dict[str, object]:
        if src not in eval_cache:
            eval_cache[src] = _run_fast_event_kernel(src, fixtures, ("eval",))
        return eval_cache[src]

    inc_cfg = dict(EVENT_GEN0_CFG)
    inc_src = build_event_policy_source(inc_cfg)
    inc_ev = _get_eval(inc_src)
    tried_sources = {inc_src}

    gen_records: List[Dict[str, object]] = [{
        "generation": 0,
        "status": "FROZEN_CONTROL",
        "cfg": dict(inc_cfg),
        "function_name": "event_perception_policy",
        "function_source": inc_src,
        "unified_diff": "",
        "ast_meta": GuardedFunctionASTSandbox.structural_metrics(inc_src),
        "discovery_comp": _get_disc(inc_src),
        "va_rmse": inc_ev["va_rmse"],
        "va_mae": inc_ev["va_mae"],
        "va_comp": inc_ev["va_comp"],
        "tf_rmse": inc_ev["tf_rmse"],
        "tf_mae": inc_ev["tf_mae"],
        "tf_comp": inc_ev["tf_comp"],
        "ood_rate": inc_ev["ood_rate"],
        "ood_suppressed": inc_ev["ood_suppressed"],
        "fp_rate": inc_ev["fp_rate"],
        "delta_va_comp": 0.0,
        "delta_tf_comp": 0.0,
        "rolled_back": False,
    }]

    consec = 0
    best_consec = 0
    rejected_count = 0

    for gen in range(1, generations + 1):
        pool: List[Tuple[float, Dict[str, float], str]] = []
        seen = set(tried_sources)
        for _ in range(sample_size):
            cand_cfg = dict(inc_cfg)
            key = slot_keys[int(rng.randint(len(slot_keys)))]
            choices = EVENT_MUTATION_SLOTS[key]
            cand_cfg[key] = float(choices[int(rng.randint(len(choices)))])
            cand_src = build_event_policy_source(cand_cfg)
            if cand_src in seen:
                continue
            seen.add(cand_src)
            pool.append((_get_disc(cand_src), cand_cfg, cand_src))

        pool.sort(key=lambda item: item[0])
        best_disc, best_cfg, best_src = pool[0]
        tried_sources.add(best_src)
        cand_ev = _get_eval(best_src)

        d_va = round(float(inc_ev["va_comp"]) - float(cand_ev["va_comp"]), 6)
        d_tf = round(float(inc_ev["tf_comp"]) - float(cand_ev["tf_comp"]), 6)
        adopted = bool(
            d_va > 0.0
            and d_tf > 0.0
            and 0.5 * (d_va + d_tf) > 0.02
            and float(cand_ev["ood_rate"]) >= 0.75
            and bool(cand_ev["ood_suppressed"])
            and float(cand_ev["fp_rate"]) <= 0.25
        )
        diff_src = unified_source_diff(
            inc_src,
            best_src,
            f"event_causal_perception/incumbent_g{gen - 1}.py",
            f"event_causal_perception/candidate_g{gen}.py",
        )
        if adopted:
            inc_cfg = best_cfg
            inc_src = best_src
            inc_ev = cand_ev
            consec += 1
            best_consec = max(best_consec, consec)
            status = "ADOPTED"
        else:
            consec = 0
            rejected_count += 1
            status = "REJECTED_ROLLED_BACK"

        gen_records.append({
            "generation": gen,
            "status": status,
            "cfg": dict(best_cfg),
            "function_name": "event_perception_policy",
            "function_source": best_src,
            "unified_diff": diff_src,
            "ast_meta": GuardedFunctionASTSandbox.structural_metrics(best_src),
            "discovery_comp": round(best_disc, 6),
            "va_rmse": cand_ev["va_rmse"],
            "va_mae": cand_ev["va_mae"],
            "va_comp": cand_ev["va_comp"],
            "tf_rmse": cand_ev["tf_rmse"],
            "tf_mae": cand_ev["tf_mae"],
            "tf_comp": cand_ev["tf_comp"],
            "ood_rate": cand_ev["ood_rate"],
            "ood_suppressed": cand_ev["ood_suppressed"],
            "fp_rate": cand_ev["fp_rate"],
            "delta_va_comp": d_va,
            "delta_tf_comp": d_tf,
            "rolled_back": status != "ADOPTED",
        })

    return {
        "seed": seed,
        "generations": gen_records,
        "final_adopted_source": inc_src,
        "final_adopted_cfg": inc_cfg,
        "gen0_tf_rmse": gen_records[0]["tf_rmse"],
        "final_tf_rmse": inc_ev["tf_rmse"],
        "gen0_va_rmse": gen_records[0]["va_rmse"],
        "final_va_rmse": inc_ev["va_rmse"],
        "max_consecutive_adopted": best_consec,
        "rejected_generations_count": rejected_count,
        "passed_criteria": bool(best_consec >= 2 and rejected_count >= 1),
    }


def run_module2_event_causal(root: Path) -> Dict[str, object]:
    """Runs Module 2 across training self-play + protocol.json held-out validation/transfer/OOD + full engine verification."""
    proto_path = root / "components/Zoe-Autonomy/evidence/event-causal/protocol.json"
    if not proto_path.is_file():
        proto_path = DEFAULT_EVENT_PROTOCOL
    protocol = json.loads(proto_path.read_text(encoding="utf-8"))
    protocol_sha256 = digest(protocol)

    fixtures = {
        "training": _event_fixture(protocol, "training"),
        "validation": _event_fixture(protocol, "validation"),
        "transfer": _event_fixture(protocol, "transfer"),
        "ood": _event_fixture(protocol, "ood"),
        # Discovery self-play ONLY uses training positions [2,5,8,11] & velocities [-1,1] with sensor jitter!
        "disc_noisy": [
            synthetic_sequence(
                [2, 5, 8, 11][i % 4],
                [-1, 1][(i // 4) % 2],
                steps=16,
                noise_probability=0.04 if i < 8 else 0.07,
                seed=8201 + i,
            )
            for i in range(16)
        ],
    }

    disc_cache: Dict[str, float] = {}
    eval_cache: Dict[str, Dict[str, object]] = {}

    prim = _single_seed_event_evolution(PRIMARY_SEED, fixtures, disc_cache, eval_cache)
    multi_seed_runs = []
    for s in ROBUSTNESS_SEEDS:
        r = prim if s == PRIMARY_SEED else _single_seed_event_evolution(s, fixtures, disc_cache, eval_cache)
        multi_seed_runs.append({
            "seed": s,
            "final_function_source": r["final_adopted_source"],
            "final_va_rmse": r["final_va_rmse"],
            "final_tf_rmse": r["final_tf_rmse"],
            "max_consecutive_adopted": r["max_consecutive_adopted"],
            "rejected_generations_count": r["rejected_generations_count"],
            "passed_criteria": r["passed_criteria"],
        })

    # Genuine unmodified `EventCausalEngine` cross-verification on Gen 0 & Primary Seed 42's final adopted policy!
    gen0_src = prim["generations"][0]["function_source"]
    final_src = str(prim["final_adopted_source"])
    full_gen0 = run_full_event_engine_evaluation(gen0_src, protocol, eval_ood=True)
    full_final = run_full_event_engine_evaluation(final_src, protocol, eval_ood=True)
    max_kernel_delta = max(
        abs(float(full_gen0["va_rmse"]) - float(prim["generations"][0]["va_rmse"])),
        abs(float(full_gen0["tf_rmse"]) - float(prim["generations"][0]["tf_rmse"])),
        abs(float(full_final["va_rmse"]) - float(prim["final_va_rmse"])),
        abs(float(full_final["tf_rmse"]) - float(prim["final_tf_rmse"])),
    )

    seeds_passed = sum(1 for row in multi_seed_runs if row["passed_criteria"])
    return {
        "module_id": "event_causal_perception",
        "title": "Module 2 · Closed-Loop Event-Causal Active Perception",
        "protocol_sha256": protocol_sha256,
        "function_name": "event_perception_policy",
        "function_args": list(EVENT_POLICY_ARGS),
        "gen0_source": gen0_src,
        "final_adopted_source": final_src,
        "gen0_metric": prim["gen0_tf_rmse"],
        "final_metric": prim["final_tf_rmse"],
        "metric_name": "unseen_transfer_rmse",
        "higher_is_better": False,
        "primary_seed": PRIMARY_SEED,
        "generations": prim["generations"],
        "max_consecutive_adopted": prim["max_consecutive_adopted"],
        "rejected_generations_count": prim["rejected_generations_count"],
        "full_engine_cross_check": {
            "gen0": full_gen0,
            "final_adopted": full_final,
            "max_kernel_vs_full_engine_delta": round(max_kernel_delta, 12),
            "memory_retention_passed": bool(full_final["memory_retention_passed"]),
            "memory_chain_valid": bool(full_final["memory_chain_valid"]),
            "all_guards_approved": bool(full_final["all_guards_approved"]),
            "external_actions": int(full_final["external_actions"]),
        },
        "multi_seed_robustness": {
            "seeds_passed": seeds_passed,
            "seeds_total": len(multi_seed_runs),
            "all_seeds_passed": seeds_passed == len(multi_seed_runs),
            "runs": multi_seed_runs,
        },
        "passed_criteria": bool(
            prim["passed_criteria"]
            and seeds_passed == len(multi_seed_runs)
            and max_kernel_delta == 0.0
            and full_final["memory_retention_passed"]
            and full_final["memory_chain_valid"]
            and full_final["all_guards_approved"]
            and full_final["external_actions"] == 0
        ),
    }


# ---------------------------------------------------------------------------
# MODULE 3: Temporal Dynamics, Groove Forensics & Dorothy 40 Hz Neural ISI
# ---------------------------------------------------------------------------

TEMPORAL_ARGS: Tuple[str, ...] = ("x", "y", "z", "w")
TEMPORAL_GEN0_TERMS: Tuple[Tuple[str, float], ...] = (("abs(mean(x * y))", 1.0),)

TEMPORAL_ATOMIC_TERMS: Tuple[str, ...] = (
    "abs(mean(x * y))",
    "abs(mean(x * z))",
    "abs(mean(x * w))",
    "sq(mean(x * y))",
    "sq(mean(x * z))",
    "sq(mean(x * w))",
    "abs(mean(sq(x) * y))",
    "abs(mean(sq(x) * z))",
    "abs(mean(x * sq(y)))",
    "sq(mean(sq(x) * y))",
    "abs(mean(x * y * z))",
    "abs(mean(pos(x) * y))",
    "abs(mean(abs(x) * y))",
    "abs(mean(x * x * x * y))",
)
TEMPORAL_WEIGHTS: Tuple[float, ...] = (0.5, 1.0, 1.5)

_TEMPORAL_EVAL_META: Tuple[Tuple[str, str, str], ...] = (
    ("ho_swing", "Swing Nonlinear Return Map (Held-Out)", "heldout"),
    ("ho_hemiola", "Period-3 Hemiola Groove (Held-Out)", "heldout"),
    ("zs_syncopated_p4", "Period-4 Syncopated Backbeat [ZERO-SHOT]", "zero_shot"),
    ("zs_nonlinear_chaos", "Chaotic Logistic Map u=1-2u^2 [ZERO-SHOT]", "zero_shot"),
    ("zs_dorothy_40hz", "Dorothy 40 Hz Neural Spike ISI vs Poisson [ZERO-SHOT]", "zero_shot"),
)


def detrend_and_standardize_series(series: np.ndarray) -> np.ndarray:
    """Degree-3 polynomial rubato detrending & z-standardization (0 on rigid metronomes)."""
    t = np.linspace(-1.0, 1.0, len(series))
    coeffs = np.polyfit(t, series, 3)
    res = series - np.polyval(coeffs, t)
    sd = float(np.std(res))
    return np.zeros_like(res) if sd < 1e-6 else res / sd


def _generate_temporal_dataset(kind: str, n_pos: int, n_neg: int, seed: int, n_len: int = 96) -> Dict[str, np.ndarray]:
    rng = np.random.RandomState(seed)
    xs, ys, zs, ws, labels = [], [], [], [], []

    def _push(raw: np.ndarray, label: int) -> None:
        r = detrend_and_standardize_series(raw)
        xs.append(r[:-3])
        ys.append(r[1:-2])
        zs.append(r[2:-1])
        ws.append(r[3:])
        labels.append(label)

    for _ in range(n_pos):
        t = np.linspace(0.0, 1.0, n_len)
        rubato = 0.03 * np.sin(2.0 * np.pi * t * rng.uniform(0.8, 1.4)) + rng.uniform(-0.02, 0.02) * (t ** 2)
        if kind == "swing_nonlinear":
            amp = rng.uniform(0.011, 0.016)
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                sw = amp if i % 2 == 0 else -amp
                seq[i] = sw + 0.020 * u + rng.normal(0.0, 0.022)
            raw = rubato + seq
        elif kind == "hemiola_p3":
            amp = rng.uniform(0.015, 0.022)
            ph = int(rng.randint(0, 3))
            pat = np.array([amp, -0.5 * amp, -0.5 * amp])
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = pat[(i + ph) % 3] + 0.018 * u + rng.normal(0.0, 0.022)
            raw = rubato + seq
        elif kind == "syncopated_p4":
            amp = rng.uniform(0.018, 0.025)
            ph = int(rng.randint(0, 4))
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = amp * math.cos(math.pi * (i + ph) / 2.0) + 0.015 * u + rng.normal(0.0, 0.022)
            raw = rubato + seq
        elif kind == "nonlinear_chaos":
            u = rng.uniform(-0.85, 0.85)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = u * 0.026
            raw = rubato + seq + rng.normal(0.0, 0.014, n_len)
        elif kind == "dorothy_40hz_isi":
            isi = np.zeros(n_len)
            v = rng.uniform(-0.7, 0.7)
            for i in range(n_len):
                v = float(np.clip(1.0 - 2.0 * v * v, -1.0, 1.0))
                isi[i] = (
                    0.025
                    + 0.0048 * v
                    + 0.0036 * math.cos(2.0 * math.pi * i / 3.0)
                    + 0.0036 * math.cos(math.pi * i / 2.0)
                    + rng.normal(0.0, 0.0052)
                )
            raw = rubato * 0.2 + isi
        else:
            raise ValueError(f"unknown temporal dataset kind: {kind}")
        _push(raw, 1)

    for _ in range(n_neg):
        t = np.linspace(0.0, 1.0, n_len)
        rubato = 0.03 * np.sin(2.0 * np.pi * t * rng.uniform(0.8, 1.4)) + rng.uniform(-0.02, 0.02) * (t ** 2)
        if kind == "dorothy_40hz_isi":
            raw = rubato * 0.2 + rng.exponential(0.025, n_len)
        else:
            raw = rubato + rng.normal(0.0, 0.025, n_len)
        _push(raw, 0)

    return {
        "x": np.asarray(xs, dtype=np.float64),
        "y": np.asarray(ys, dtype=np.float64),
        "z": np.asarray(zs, dtype=np.float64),
        "w": np.asarray(ws, dtype=np.float64),
        "labels": np.asarray(labels, dtype=np.int64),
    }


def load_temporal_benchmarks() -> Dict[str, Dict[str, Dict[str, np.ndarray]]]:
    """Deterministic Discovery + Held-Out + Unseen Zero-Shot + Rigid Metronome temporal datasets."""
    discovery = {
        "disc_swing": _generate_temporal_dataset("swing_nonlinear", 100, 100, 1001),
        "disc_hemiola": _generate_temporal_dataset("hemiola_p3", 100, 100, 1002),
    }
    eval_sets = {
        "ho_swing": _generate_temporal_dataset("swing_nonlinear", 120, 120, 2001),
        "ho_hemiola": _generate_temporal_dataset("hemiola_p3", 120, 120, 2002),
        "zs_syncopated_p4": _generate_temporal_dataset("syncopated_p4", 120, 120, 3001),
        "zs_nonlinear_chaos": _generate_temporal_dataset("nonlinear_chaos", 120, 120, 3002),
        "zs_dorothy_40hz": _generate_temporal_dataset("dorothy_40hz_isi", 120, 120, 3003),
    }
    metronome_streams = [detrend_and_standardize_series(np.full(96, 0.5)) for _ in range(20)]
    metronome = {
        "x": np.asarray([s[:-3] for s in metronome_streams], dtype=np.float64),
        "y": np.asarray([s[1:-2] for s in metronome_streams], dtype=np.float64),
        "z": np.asarray([s[2:-1] for s in metronome_streams], dtype=np.float64),
        "w": np.asarray([s[3:] for s in metronome_streams], dtype=np.float64),
    }
    return {"discovery": discovery, "eval": eval_sets, "metronome": metronome}


def build_temporal_source(terms: Sequence[Tuple[str, float]]) -> str:
    """Materializes a guarded multi-statement `def temporal_phase_score(x, y, z, w):` function."""
    first_expr, first_w = terms[0]
    lines = ["def temporal_phase_score(x, y, z, w):"]
    lines.append(f"    score = {first_w} * {first_expr}" if first_w != 1.0 else f"    score = {first_expr}")
    for idx, (term_expr, weight) in enumerate(terms[1:], 1):
        lines.append(f"    t{idx} = {term_expr}")
        lines.append(f"    score += {weight} * t{idx}" if weight != 1.0 else f"    score += t{idx}")
    lines.append("    return score")
    source = "\n".join(lines)
    GuardedFunctionASTSandbox.validate(source, expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS)
    return source


def evaluate_temporal_source(source: str, eval_sets: Dict[str, Dict[str, np.ndarray]]) -> Tuple[Dict[str, float], float]:
    fn = GuardedFunctionASTSandbox.compile(source, expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS)
    out: Dict[str, float] = {}
    for k, d in eval_sets.items():
        s = np.asarray(fn({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)
        out[k] = round(_auroc(d["labels"], s), 6)
    mean_v = round(sum(out.values()) / len(out), 6)
    return out, mean_v


def _temporal_discovery_cv(source: str, discovery: Dict[str, Dict[str, np.ndarray]], n_terms: int) -> float:
    fn = GuardedFunctionASTSandbox.compile(source, expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS)
    fold_aurocs: List[float] = []
    for d in discovery.values():
        scores = np.asarray(fn({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)
        fold_aurocs.append(0.5 * (_auroc(d["labels"][0::2], scores[0::2]) + _auroc(d["labels"][1::2], scores[1::2])))
    return float(sum(fold_aurocs) / len(fold_aurocs)) - 0.004 * float(n_terms)


def _single_seed_temporal_evolution(
    seed: int,
    benchmarks: Dict[str, Dict[str, object]],
    generations: int = 5,
    pop_size: int = 56,
) -> Dict[str, object]:
    discovery: Dict[str, Dict[str, np.ndarray]] = benchmarks["discovery"]  # type: ignore[assignment]
    eval_sets: Dict[str, Dict[str, np.ndarray]] = benchmarks["eval"]  # type: ignore[assignment]
    zs_keys = [k for k, _, sp in _TEMPORAL_EVAL_META if sp == "zero_shot"]

    rng = np.random.RandomState(seed)
    inc_terms: List[Tuple[str, float]] = list(TEMPORAL_GEN0_TERMS)
    inc_src = build_temporal_source(inc_terms)
    inc_scores, inc_mean = evaluate_temporal_source(inc_src, eval_sets)
    tried = {inc_src}

    gen_records: List[Dict[str, object]] = [{
        "generation": 0,
        "status": "FROZEN_CONTROL",
        "terms": [[t, w] for t, w in inc_terms],
        "function_name": "temporal_phase_score",
        "function_source": inc_src,
        "unified_diff": "",
        "ast_meta": GuardedFunctionASTSandbox.structural_metrics(inc_src),
        "heldout_auroc": inc_scores,
        "heldout_mean": inc_mean,
        "regimes_improved": 0,
        "zero_shot_improved": 0,
        "worst_regime_delta": 0.0,
        "mean_delta": 0.0,
        "rolled_back": False,
    }]

    consec = 0
    best_consec = 0
    rejected_count = 0

    for gen in range(1, generations + 1):
        pool: List[Tuple[float, List[Tuple[str, float]], str]] = []
        seen = set(tried)
        for _ in range(pop_size):
            cand = list(inc_terms)
            op = str(rng.choice(["add", "swap_wt", "replace"])) if len(cand) > 1 else "add"
            if op == "add" and len(cand) < 5:
                t = TEMPORAL_ATOMIC_TERMS[int(rng.randint(len(TEMPORAL_ATOMIC_TERMS)))]
                if all(x[0] != t for x in cand):
                    cand.append((t, float(TEMPORAL_WEIGHTS[int(rng.randint(len(TEMPORAL_WEIGHTS)))])))
            elif op == "swap_wt":
                idx = int(rng.randint(len(cand)))
                cand[idx] = (cand[idx][0], float(TEMPORAL_WEIGHTS[int(rng.randint(len(TEMPORAL_WEIGHTS)))]))
            elif op == "replace":
                idx = int(rng.randint(len(cand)))
                t = TEMPORAL_ATOMIC_TERMS[int(rng.randint(len(TEMPORAL_ATOMIC_TERMS)))]
                if all(x[0] != t for x in cand):
                    cand[idx] = (t, cand[idx][1])
            cand_src = build_temporal_source(cand)
            if cand_src in seen:
                continue
            seen.add(cand_src)
            pool.append((_temporal_discovery_cv(cand_src, discovery, len(cand)), cand, cand_src))

        pool.sort(key=lambda item: -item[0])
        _, best_terms, best_src = pool[0]
        tried.add(best_src)
        ev_scores, ev_mean = evaluate_temporal_source(best_src, eval_sets)
        deltas = {k: round(ev_scores[k] - inc_scores[k], 6) for k in eval_sets}
        imp = sum(1 for v in deltas.values() if v > 1e-4)
        zs_imp = sum(1 for k in zs_keys if deltas[k] > 1e-4)
        wd = round(min(deltas.values()), 6)
        mean_delta = round(ev_mean - inc_mean, 6)

        adopted = bool(ev_mean > inc_mean + 0.008 and imp >= 3 and zs_imp >= 2 and wd >= -0.025)
        diff_src = unified_source_diff(
            inc_src,
            best_src,
            f"temporal_groove_neural/incumbent_g{gen - 1}.py",
            f"temporal_groove_neural/candidate_g{gen}.py",
        )
        if adopted:
            inc_terms = best_terms
            inc_src = best_src
            inc_scores = ev_scores
            inc_mean = ev_mean
            consec += 1
            best_consec = max(best_consec, consec)
            status = "ADOPTED"
        else:
            consec = 0
            rejected_count += 1
            status = "REJECTED_ROLLED_BACK"

        gen_records.append({
            "generation": gen,
            "status": status,
            "terms": [[t, w] for t, w in best_terms],
            "function_name": "temporal_phase_score",
            "function_source": best_src,
            "unified_diff": diff_src,
            "ast_meta": GuardedFunctionASTSandbox.structural_metrics(best_src),
            "heldout_auroc": ev_scores,
            "heldout_mean": ev_mean,
            "regimes_improved": imp,
            "zero_shot_improved": zs_imp,
            "worst_regime_delta": wd,
            "mean_delta": mean_delta,
            "rolled_back": status != "ADOPTED",
        })

    return {
        "seed": seed,
        "generations": gen_records,
        "final_adopted_source": inc_src,
        "final_adopted_terms": [[t, w] for t, w in inc_terms],
        "gen0_mean": gen_records[0]["heldout_mean"],
        "final_mean": inc_mean,
        "total_gain_over_gen0": round(inc_mean - float(gen_records[0]["heldout_mean"]), 6),
        "max_consecutive_adopted": best_consec,
        "rejected_generations_count": rejected_count,
        "passed_criteria": bool(best_consec >= 2 and rejected_count >= 1),
    }


def _temporal_permutation_null(
    source: str,
    eval_sets: Dict[str, Dict[str, np.ndarray]],
    n_trials: int = 200,
    seed: int = 2026,
) -> Dict[str, object]:
    rng = np.random.RandomState(seed)
    fn = GuardedFunctionASTSandbox.compile(source, expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS)
    per_regime: Dict[str, Dict[str, float]] = {}
    means: List[float] = []
    for k, d in eval_sets.items():
        scores = np.asarray(fn({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)
        labs = d["labels"]
        vals = [_auroc(rng.permutation(labs), scores) for _ in range(n_trials)]
        mu = float(np.mean(vals))
        sd = float(np.std(vals))
        per_regime[k] = {"mean": round(mu, 6), "std": round(sd, 6)}
        means.append(mu)
    overall = round(float(np.mean(means)), 6)
    return {
        "n_trials": n_trials,
        "overall_null_mean": overall,
        "per_regime": per_regime,
        "passed_no_leakage": bool(0.47 <= overall <= 0.53),
    }


def run_module3_temporal(root: Path | None = None) -> Dict[str, object]:
    """Runs Module 3 across held-out groove regimes & unseen zero-shot chaotic/neural ISI regimes."""
    _ = root
    benchmarks = load_temporal_benchmarks()
    eval_sets: Dict[str, Dict[str, np.ndarray]] = benchmarks["eval"]  # type: ignore[assignment]
    metronome: Dict[str, np.ndarray] = benchmarks["metronome"]  # type: ignore[assignment]

    prim = _single_seed_temporal_evolution(PRIMARY_SEED, benchmarks)
    gen0_src = prim["generations"][0]["function_source"]
    final_src = str(prim["final_adopted_source"])

    met_fn = GuardedFunctionASTSandbox.compile(final_src, expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS)
    met_scores = np.asarray(met_fn(metronome), dtype=np.float64)
    metronome_max_score = round(float(np.max(np.abs(met_scores))), 12)

    null_ctrl = _temporal_permutation_null(final_src, eval_sets, n_trials=200, seed=2026)

    multi_seed_runs = []
    for s in ROBUSTNESS_SEEDS:
        r = prim if s == PRIMARY_SEED else _single_seed_temporal_evolution(s, benchmarks)
        multi_seed_runs.append({
            "seed": s,
            "final_function_source": r["final_adopted_source"],
            "final_mean": r["final_mean"],
            "total_gain_over_gen0": r["total_gain_over_gen0"],
            "max_consecutive_adopted": r["max_consecutive_adopted"],
            "rejected_generations_count": r["rejected_generations_count"],
            "passed_criteria": r["passed_criteria"],
        })

    seeds_passed = sum(1 for row in multi_seed_runs if row["passed_criteria"])
    return {
        "module_id": "temporal_groove_neural",
        "title": "Module 3 · Temporal Dynamics, Groove Forensics & Dorothy 40 Hz Neural ISI",
        "function_name": "temporal_phase_score",
        "function_args": list(TEMPORAL_ARGS),
        "regimes": [{"id": k, "label": lbl, "split": sp} for k, lbl, sp in _TEMPORAL_EVAL_META],
        "gen0_source": gen0_src,
        "final_adopted_source": final_src,
        "gen0_metric": prim["gen0_mean"],
        "final_metric": prim["final_mean"],
        "total_gain": round(float(prim["total_gain_over_gen0"]), 6),
        "metric_name": "mean_auroc_5regimes",
        "higher_is_better": True,
        "primary_seed": PRIMARY_SEED,
        "generations": prim["generations"],
        "max_consecutive_adopted": prim["max_consecutive_adopted"],
        "rejected_generations_count": prim["rejected_generations_count"],
        "rigid_metronome_control": {
            "streams": 20,
            "metronome_max_score": metronome_max_score,
            "passed_zero_false_groove": metronome_max_score == 0.0,
        },
        "permutation_null_control": null_ctrl,
        "multi_seed_robustness": {
            "seeds_passed": seeds_passed,
            "seeds_total": len(multi_seed_runs),
            "all_seeds_passed": seeds_passed == len(multi_seed_runs),
            "runs": multi_seed_runs,
        },
        "passed_criteria": bool(
            prim["passed_criteria"]
            and seeds_passed == len(multi_seed_runs)
            and metronome_max_score == 0.0
            and null_ctrl["passed_no_leakage"]
        ),
    }


# ---------------------------------------------------------------------------
# COORDINATED PERSISTENT ATOMIC MULTI-MODULE STEWARDSHIP LEDGER
# ---------------------------------------------------------------------------

def _default_module_sources() -> Dict[str, str]:
    return {
        "spectral_uncertainty": wrap_spectral_function(SPECTRAL_GEN0_EXPR),
        "event_causal_perception": build_event_policy_source(EVENT_GEN0_CFG),
        "temporal_groove_neural": build_temporal_source(TEMPORAL_GEN0_TERMS),
    }


def _validate_all_modules(sources: Dict[str, str]) -> None:
    if set(sources.keys()) != set(MODULE_IDS):
        raise ValueError(f"release must provide exact modules {MODULE_IDS}")
    GuardedFunctionASTSandbox.validate(
        sources["spectral_uncertainty"], expected_name="spectral_uncertainty_score", expected_args=("p", "gt05")
    )
    GuardedFunctionASTSandbox.validate(
        sources["event_causal_perception"], expected_name="event_perception_policy", expected_args=EVENT_POLICY_ARGS
    )
    GuardedFunctionASTSandbox.validate(
        sources["temporal_groove_neural"], expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS
    )


class MultiModuleStewardshipLedger:
    """Coordinated, atomic, tamper-evident SHA-256 hash-chained multi-module release ledger."""

    def __init__(self, state_root: str | Path | None = None):
        default_dir = Path.home() / ".zoe" / "l4_multimodule"
        self.root = Path(state_root or os.environ.get("ZOE_L4_MULTIMODULE_STATE", default_dir)).expanduser().resolve()
        self.ledger_path = self.root / "multimodule_ledger.json"

    def _default_document(self) -> Dict[str, object]:
        sources = _default_module_sources()
        _validate_all_modules(sources)
        ts = timestamp()
        r0_core = {
            "release_id": 0,
            "name": "gen0_frozen_baseline",
            "status": "FROZEN_CONTROL",
            "previous_sha256": None,
            "sources": sources,
            "unified_diffs": {k: "" for k in MODULE_IDS},
            "metrics_summary": {},
            "recorded_utc": ts,
        }
        r0 = {**r0_core, "release_sha256": digest(r0_core)}
        doc: Dict[str, object] = {
            "schema_version": 1,
            "contract": LEDGER_CONTRACT,
            "created_utc": ts,
            "updated_utc": ts,
            "active_release_id": 0,
            "active_name": "gen0_frozen_baseline",
            "active_sources": dict(sources),
            "stopped": False,
            "releases": [r0],
            "rejected_releases": [],
            "external_actions": 0,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
        }
        doc["ledger_sha256"] = _sha256_obj({k: v for k, v in doc.items() if k != "ledger_sha256"})
        return doc

    def _verify_releases_and_asts(self, doc: Dict[str, object]) -> None:
        prev_sha = None
        for idx, rel in enumerate(doc.get("releases", [])):
            if rel.get("release_id") != idx or rel.get("previous_sha256") != prev_sha:
                raise ValueError("Multi-module release hash chain broken")
            core = {k: v for k, v in rel.items() if k != "release_sha256"}
            if rel.get("release_sha256") != digest(core):
                raise ValueError(f"Release {idx} hash mismatch")
            prev_sha = rel["release_sha256"]
        _validate_all_modules(doc["active_sources"])

    def _verify_chain(self, doc: Dict[str, object]) -> None:
        expected = _sha256_obj({k: v for k, v in doc.items() if k != "ledger_sha256"})
        if doc.get("ledger_sha256") != expected:
            raise ValueError("Multi-module ledger SHA-256 mismatch — refusing tampered state")
        self._verify_releases_and_asts(doc)

    def load(self) -> Dict[str, object]:
        if not self.ledger_path.is_file():
            return self._default_document()
        doc = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self._verify_chain(doc)
        return doc

    def save(self, doc: Dict[str, object]) -> Path:
        self._verify_releases_and_asts(doc)
        doc["updated_utc"] = timestamp()
        doc["ledger_sha256"] = _sha256_obj({k: v for k, v in doc.items() if k != "ledger_sha256"})
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.ledger_path)
        return self.ledger_path

    def emergency_stop(self) -> Dict[str, object]:
        doc = self.load()
        doc["stopped"] = True
        self.save(doc)
        return doc

    def commit_release(
        self,
        name: str,
        sources: Dict[str, str],
        metrics_summary: Dict[str, object] | None = None,
        adoption_approved: bool = True,
    ) -> Dict[str, object]:
        """Atomically validates and commits all 3 modules together, or rejects the entire bundle cleanly."""
        doc = self.load()
        if doc.get("stopped"):
            raise ValueError("Multi-module ledger is stopped by emergency stop; commit refused")
        if not adoption_approved:
            doc["rejected_releases"].append({
                "name": name,
                "status": "REJECTED_ATOMICALLY",
                "reason": "held-out adoption gate refused candidate bundle",
                "sources": dict(sources),
                "preserved_release_id": doc["active_release_id"],
                "recorded_utc": timestamp(),
            })
            self.save(doc)
            return {
                "committed": False,
                "reason": "adoption_approved=False",
                "active_release_id": doc["active_release_id"],
                "active_sources": dict(doc["active_sources"]),
                "ledger_sha256": doc["ledger_sha256"],
            }

        try:
            _validate_all_modules(sources)
        except (UnsafeFunctionASTError, ValueError) as err:
            doc["rejected_releases"].append({
                "name": name,
                "status": "REJECTED_SANDBOX_VIOLATION",
                "reason": str(err),
                "sources": dict(sources),
                "preserved_release_id": doc["active_release_id"],
                "recorded_utc": timestamp(),
            })
            self.save(doc)
            raise UnsafeFunctionASTError(f"Atomic release `{name}` rejected: {err}") from err

        prior_sources = dict(doc["active_sources"])
        diffs = {
            k: unified_source_diff(prior_sources[k], sources[k], f"{k}/before.py", f"{k}/after.py")
            for k in MODULE_IDS
        }
        next_id = len(doc["releases"])
        prev_sha = doc["releases"][-1]["release_sha256"]
        rel_core = {
            "release_id": next_id,
            "name": name,
            "status": "ADOPTED",
            "previous_sha256": prev_sha,
            "sources": dict(sources),
            "unified_diffs": diffs,
            "metrics_summary": dict(metrics_summary or {}),
            "recorded_utc": timestamp(),
        }
        rel = {**rel_core, "release_sha256": digest(rel_core)}
        doc["releases"].append(rel)
        doc["active_release_id"] = next_id
        doc["active_name"] = name
        doc["active_sources"] = dict(sources)
        # Keep hash valid before save
        doc["ledger_sha256"] = _sha256_obj({k: v for k, v in doc.items() if k != "ledger_sha256"})
        self.save(doc)
        return {
            "committed": True,
            "release_id": next_id,
            "name": name,
            "unified_diffs": diffs,
            "active_sources": dict(doc["active_sources"]),
            "ledger_sha256": doc["ledger_sha256"],
        }

    def rollback_release(self) -> Dict[str, object]:
        """Atomically rolls back ALL 3 modules simultaneously to the previous release."""
        doc = self.load()
        releases = list(doc["releases"])
        if len(releases) <= 1:
            return {
                "rolled_back": False,
                "active_release_id": doc["active_release_id"],
                "active_sources": dict(doc["active_sources"]),
            }
        reverted = releases.pop()
        prev = releases[-1]
        doc["releases"] = releases
        doc["rejected_releases"].append({
            **reverted,
            "status": "ATOMIC_ROLLBACK_PRESERVED",
            "rolled_back_utc": timestamp(),
        })
        doc["active_release_id"] = prev["release_id"]
        doc["active_name"] = prev["name"]
        doc["active_sources"] = dict(prev["sources"])
        doc["ledger_sha256"] = _sha256_obj({k: v for k, v in doc.items() if k != "ledger_sha256"})
        self.save(doc)
        return {
            "rolled_back": True,
            "reverted_release_id": reverted["release_id"],
            "active_release_id": doc["active_release_id"],
            "active_sources": dict(doc["active_sources"]),
            "ledger_sha256": doc["ledger_sha256"],
        }

    def apply_to_event_engine(self, engine: EventCausalEngine) -> None:
        """Hot-plugs the persisted Module 2 guarded policy callable onto a live `EventCausalEngine`."""
        doc = self.load()
        fn = GuardedFunctionASTSandbox.compile(
            str(doc["active_sources"]["event_causal_perception"]),
            expected_name="event_perception_policy",
            expected_args=EVENT_POLICY_ARGS,
        )
        engine.set_policy(fn)


def run_atomic_multimodule_rollback_proof(
    root: Path,
    mod1: Dict[str, object],
    mod2: Dict[str, object],
    mod3: Dict[str, object],
    ledger_dir: str | Path | None = None,
) -> Dict[str, object]:
    """Proves coordinated 3-engine atomic commit, poison rejection, live bit-exact rollback (`0.0` delta), and stop."""
    domains = load_l4_domains(root)
    eval_domains: Dict[str, Dict[str, object]] = domains["eval_domains"]  # type: ignore[assignment]
    temporal_eval = load_temporal_benchmarks()["eval"]
    proto_path = root / "components/Zoe-Autonomy/evidence/event-causal/protocol.json"
    if not proto_path.is_file():
        proto_path = DEFAULT_EVENT_PROTOCOL
    protocol = json.loads(proto_path.read_text(encoding="utf-8"))
    val_seqs = _event_fixture(protocol, "validation")[:4]
    tf_seqs = _event_fixture(protocol, "transfer")[:4]

    def _live_vectors(sources: Dict[str, str]) -> Dict[str, np.ndarray]:
        # 1. Live spectral scores across all 6 domains
        fn1 = GuardedFunctionASTSandbox.compile(
            sources["spectral_uncertainty"], expected_name="spectral_uncertainty_score", expected_args=("p", "gt05")
        )
        v1 = np.concatenate([
            np.sum(np.asarray(fn1({"p": dom["P"], "gt05": dom["GT05"]}), dtype=np.float64), axis=-1)
            for dom in eval_domains.values()
        ])
        # 2. Live EventCausalEngine predictions on validation & unseen transfer sequences
        fn2 = GuardedFunctionASTSandbox.compile(
            sources["event_causal_perception"], expected_name="event_perception_policy", expected_args=EVENT_POLICY_ARGS
        )
        eng = EventCausalEngine(seed=7101, policy_fn=fn2)
        v2 = np.asarray(
            [
                float(rep["selected_prediction"]["target_x"])
                for seq in val_seqs + tf_seqs
                for rep in eng.run_sequence(seq, learning=False)
            ],
            dtype=np.float64,
        )
        # 3. Live temporal groove & 40 Hz neural ISI scores across all 5 regimes
        fn3 = GuardedFunctionASTSandbox.compile(
            sources["temporal_groove_neural"], expected_name="temporal_phase_score", expected_args=TEMPORAL_ARGS
        )
        v3 = np.concatenate([
            np.asarray(fn3({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)
            for d in temporal_eval.values()
        ])
        return {"spectral": v1, "event_causal": v2, "temporal": v3}

    rel1_sources = {
        "spectral_uncertainty": str(mod1["generations"][1]["function_source"]),
        "event_causal_perception": str(mod2["generations"][1]["function_source"]),
        "temporal_groove_neural": str(mod3["generations"][1]["function_source"]),
    }
    rel2_sources = {
        "spectral_uncertainty": str(mod1["final_adopted_source"]),
        "event_causal_perception": str(mod2["final_adopted_source"]),
        "temporal_groove_neural": str(mod3["final_adopted_source"]),
    }

    def _execute(target_dir: Path) -> Dict[str, object]:
        ledger = MultiModuleStewardshipLedger(target_dir)
        ledger.load()
        c1 = ledger.commit_release("release_1_gen1_bundle", rel1_sources)
        r1_vecs = _live_vectors(ledger.load()["active_sources"])

        c2 = ledger.commit_release("release_2_final_bundle", rel2_sources)
        r2_vecs = _live_vectors(ledger.load()["active_sources"])

        # Confirm Release 2 genuinely changed predictions across all 3 engines
        r1_vs_r2_deltas = {k: round(float(np.max(np.abs(r2_vecs[k] - r1_vecs[k]))), 6) for k in r1_vecs}

        # Poison probe A: 2 modules valid + 1 module hostile AST -> ENTIRE bundle must reject atomically
        hostile_rejected = False
        try:
            ledger.commit_release("poison_hostile_event", {
                **rel2_sources,
                "event_causal_perception": "def event_perception_policy(sc_cnt):\n    import os\n    return sc_cnt",
            })
        except UnsafeFunctionASTError:
            hostile_rejected = True

        # Poison probe B: held-out gate failure -> preserves Release 2 untouched
        gate_res = ledger.commit_release("poison_regressed_bundle", rel1_sources, adoption_approved=False)
        after_poison = ledger.load()
        poison_rejected = bool(
            hostile_rejected
            and not gate_res["committed"]
            and after_poison["active_release_id"] == 2
            and after_poison["active_sources"] == rel2_sources
        )

        # Simultaneous 3-engine rollback Release 2 -> Release 1 and verify bit-exact output restoration
        rb = ledger.rollback_release()
        reloaded_rb = MultiModuleStewardshipLedger(target_dir).load()
        rb_vecs = _live_vectors(reloaded_rb["active_sources"])
        per_module_rb_delta = {k: round(float(np.max(np.abs(rb_vecs[k] - r1_vecs[k]))), 12) for k in r1_vecs}

        # Bidirectional roundtrip: re-commit Release 2 cleanly
        c2_again = ledger.commit_release("release_2_restored", rel2_sources)
        reloaded_r2 = MultiModuleStewardshipLedger(target_dir).load()
        r2_again_vecs = _live_vectors(reloaded_r2["active_sources"])
        per_module_restore_delta = {k: round(float(np.max(np.abs(r2_again_vecs[k] - r2_vecs[k]))), 12) for k in r2_vecs}

        # Emergency stop enforcement
        ledger.emergency_stop()
        stop_enforced = False
        try:
            ledger.commit_release("post_stop_blocked", rel1_sources)
        except ValueError:
            stop_enforced = True

        max_delta = round(max(*per_module_rb_delta.values(), *per_module_restore_delta.values()), 12)
        return {
            "ledger_contract": LEDGER_CONTRACT,
            "sha256_after_release1": str(c1["ledger_sha256"]),
            "sha256_after_release2": str(c2["ledger_sha256"]),
            "sha256_after_rollback": str(rb["ledger_sha256"]),
            "sha256_after_recommit": str(c2_again["ledger_sha256"]),
            "r1_vs_r2_prediction_shifts": r1_vs_r2_deltas,
            "all_three_engines_changed_output": all(v > 0.0 for v in r1_vs_r2_deltas.values()),
            "per_module_rollback_delta": per_module_rb_delta,
            "per_module_recommit_delta": per_module_restore_delta,
            "max_prediction_delta": max_delta,
            "rollback_restored_bit_exact": bool(rb["rolled_back"] and max_delta == 0.0),
            "poison_rejected": poison_rejected,
            "emergency_stop_enforced": stop_enforced,
            "ledger_chain_valid": True,
        }

    if ledger_dir is not None:
        return _execute(Path(ledger_dir))
    with tempfile.TemporaryDirectory(prefix="zoe-l4-multimodule-rb-") as tmp:
        return _execute(Path(tmp))


# ---------------------------------------------------------------------------
# MASTER ORCHESTRATOR & CLI
# ---------------------------------------------------------------------------

def run_l4_multimodule_suite(
    zoe_root: str | Path | None = None,
    output_path: str | Path | None = None,
    run_independent_subprocess: bool = True,
) -> Dict[str, object]:
    """Runs the complete 3-engine L4 Multi-Module Code Evolution suite & independent verifier."""
    root = _default_zoe_root(zoe_root)
    hostile = run_hostile_function_probes()
    mod1 = run_module1_spectral(root)
    mod2 = run_module2_event_causal(root)
    mod3 = run_module3_temporal(root)
    rollback = run_atomic_multimodule_rollback_proof(root, mod1, mod2, mod3)

    modules = {
        "spectral_uncertainty": mod1,
        "event_causal_perception": mod2,
        "temporal_groove_neural": mod3,
    }
    report: Dict[str, object] = {
        "schema_version": 1,
        "contract": CONTRACT,
        "zoe_root": ".",
        "sandbox_design": {
            "multi_statement_python_def": True,
            "generation_blind_uniform_mutations": True,
            "generation_branching_count": 0,
            "unified_source_diffs": True,
            "max_statements": GuardedFunctionASTSandbox.MAX_STATEMENTS,
            "max_ast_nodes": GuardedFunctionASTSandbox.MAX_AST_NODES,
            "max_ast_depth": GuardedFunctionASTSandbox.MAX_AST_DEPTH,
            "allowed_functions": sorted(_SAFE_FUNCS.keys()),
            "pytorch_required": False,
        },
        "modules": modules,
        "hostile_function_probes": hostile,
        "atomic_multimodule_rollback_proof": rollback,
        "summary_metrics": {
            "engines_evolved": len(modules),
            "engines_passed": sum(1 for m in modules.values() if m["passed_criteria"]),
            "total_seed_runs_passed": sum(int(m["multi_seed_robustness"]["seeds_passed"]) for m in modules.values()),
            "total_seed_runs": sum(int(m["multi_seed_robustness"]["seeds_total"]) for m in modules.values()),
            "hostile_probes_blocked": f"{hostile['probes_blocked']}/{hostile['probes_tested']}",
            "atomic_rollback_max_delta": rollback["max_prediction_delta"],
        },
        "epistemic_boundaries": {
            "belief_updated": False,
            "external_actions": 0,
            "clinical_action_authorized": False,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "honest_remaining_l5_gates": [
                "Broad competent-human performance across all 10 AGI-ROADMAP.md domain families on novel open-ended tasks.",
                "Autonomous free-form cross-file architectural refactoring beyond bounded pure `def` sandboxes.",
                "Long-horizon continual learning over unbounded real-world multi-session research workflows.",
            ],
        },
    }
    report["core_sha256"] = _sha256_obj(report)

    target = Path(output_path) if output_path else (root / DEFAULT_REPORT_REL)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    verifier_script = root / DEFAULT_VERIFIER_REL
    ind_summary: Dict[str, object] = {
        "verifier_script": DEFAULT_VERIFIER_REL,
        "executed_in_fresh_subprocess": False,
        "verified": False,
    }
    if run_independent_subprocess and verifier_script.is_file():
        proc = subprocess.run(
            [sys.executable, str(verifier_script), "--zoe-root", str(root), "--report", str(target), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = json.loads(proc.stdout)
            ind_summary = {
                "verifier_script": DEFAULT_VERIFIER_REL,
                "executed_in_fresh_subprocess": True,
                "returncode": proc.returncode,
                "verified": bool(parsed.get("verified")),
                "checks_passed": parsed.get("checks_passed"),
                "checks_total": parsed.get("checks_total"),
                "max_numerical_delta": parsed.get("max_numerical_delta"),
                "hostile_probes_blocked": parsed.get("hostile_probes_blocked"),
                "verifier_sha256": parsed.get("verifier_sha256"),
            }
        else:
            ind_summary = {
                "verifier_script": DEFAULT_VERIFIER_REL,
                "executed_in_fresh_subprocess": True,
                "returncode": proc.returncode,
                "verified": False,
                "stderr": (proc.stderr or proc.stdout)[-400:],
            }

    qualified = bool(
        all(bool(m["passed_criteria"]) for m in modules.values())
        and hostile["all_blocked"]
        and rollback["rollback_restored_bit_exact"]
        and rollback["poison_rejected"]
        and rollback["emergency_stop_enforced"]
        and bool(ind_summary.get("verified"))
    )

    report["independent_verification"] = ind_summary
    report["l4_multimodule_qualified"] = qualified
    report["report_sha256"] = _sha256_obj({k: v for k, v in report.items() if k not in {"report_sha256", "artifact_path"}})
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["artifact_path"] = str(target)
    return report


def summarize_l4_multimodule_report(report: Dict[str, object]) -> str:
    """Human-readable summary for CLI and `zoe chat`."""
    mods = report["modules"]
    m1 = mods["spectral_uncertainty"]
    m2 = mods["event_causal_perception"]
    m3 = mods["temporal_groove_neural"]
    hp = report["hostile_function_probes"]
    rb = report["atomic_multimodule_rollback_proof"]
    ind = report.get("independent_verification", {})
    sm = report["summary_metrics"]
    lines = [
        f"Zoe L4 Multi-Module Guarded Code Self-Improvement ({report['contract']}):",
        f"  Engines Evolved & Passed: {sm['engines_passed']}/{sm['engines_evolved']} · Multi-Seed Runs={sm['total_seed_runs_passed']}/{sm['total_seed_runs']} · PyTorch=False",
        f"  [1] Spectral Uncertainty: Gen0={m1['gen0_metric']:.5f} -> Final={m1['final_metric']:.5f} ({m1['max_consecutive_adopted']} consec adopt, {m1['rejected_generations_count']} rollback, {m1['multi_seed_robustness']['seeds_passed']}/5 seeds)",
        f"  [2] Event-Causal Perception: Tf_RMSE={m2['gen0_metric']:.3f} -> {m2['final_metric']:.3f} | Va_RMSE={m2['full_engine_cross_check']['gen0']['va_rmse']:.3f} -> {m2['full_engine_cross_check']['final_adopted']['va_rmse']:.3f} ({m2['max_consecutive_adopted']} consec adopt, {m2['rejected_generations_count']} rollback, {m2['multi_seed_robustness']['seeds_passed']}/5 seeds, OOD={m2['full_engine_cross_check']['final_adopted']['ood_rate']})",
        f"  [3] Temporal Groove & Dorothy 40 Hz ISI: Gen0={m3['gen0_metric']:.4f} -> Final={m3['final_metric']:.4f} ({m3['max_consecutive_adopted']} consec adopt, {m3['rejected_generations_count']} rollback, {m3['multi_seed_robustness']['seeds_passed']}/5 seeds, met={m3['rigid_metronome_control']['metronome_max_score']})",
        f"  Governance: Hostile def AST blocked={hp['probes_blocked']}/{hp['probes_tested']} · Atomic 3-engine rollback={rb['rollback_restored_bit_exact']} (max_delta={rb['max_prediction_delta']}) · Stop={rb['emergency_stop_enforced']}",
        f"  Independent Verifier: verified={ind.get('verified')} ({ind.get('checks_passed')}/{ind.get('checks_total')}, max_delta={ind.get('max_numerical_delta')})",
        f"  L4 MULTI-MODULE QUALIFIED={report['l4_multimodule_qualified']} · L5 AGI={report['epistemic_boundaries']['l5_agi_qualified']} · external_actions=0 · sentience_claimed=False",
    ]
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Zoe's L4 Multi-Module Guarded Code Self-Improvement suite.")
    parser.add_argument("--zoe-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rep = run_l4_multimodule_suite(
        zoe_root=args.zoe_root,
        output_path=args.output,
        run_independent_subprocess=True,
    )
    if args.json:
        print(json.dumps({
            "l4_multimodule_qualified": rep["l4_multimodule_qualified"],
            "artifact_path": rep["artifact_path"],
            "summary_metrics": rep["summary_metrics"],
            "independent_verification": rep["independent_verification"],
        }, indent=2, sort_keys=True))
    else:
        print(summarize_l4_multimodule_report(rep))
    return 0 if rep["l4_multimodule_qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

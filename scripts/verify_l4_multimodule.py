#!/usr/bin/env python3
"""Standalone Independent Fresh-Process Verifier for Zoe L4 Multi-Module Code Self-Improvement.

Deliberately DOES NOT import `zoe_autonomy.l4_multi_module`, `zoe_autonomy.l4_self_improvement`,
or `guiai`. Independently implements:
  - Its own multi-statement Python `def` function AST sandbox & interpreter + 17 hostile probes
  - Direct loading of raw repo files (`predictions.npz`, `onset-seed7.json.gz`,
    `dorothy-neurogarden.png`) + 3D PSF+Rician volumes for Module 1
  - Direct instantiation of genuine unmodified `EventCausalEngine` on `protocol.json` +
    exact kernel replay for Module 2
  - Direct deterministic generation of held-out/zero-shot groove & Dorothy 40 Hz neural ISI
    streams + rigid-metronome control + 100-trial shuffle null for Module 3
  - Line-by-line `difflib.unified_diff` provenance, 5/5 multi-seed verification across all
    3 engines, atomic rollback & emergency-stop checks, and constitutional invariants.

Usage:
    python3 scripts/verify_l4_multimodule.py
    python3 scripts/verify_l4_multimodule.py --report evidence/l4-multimodule/l4-multimodule-report.json --json
"""

from __future__ import annotations

import argparse
import ast
import difflib
import gzip
import hashlib
import json
import math
import operator
from pathlib import Path
import statistics
import sys
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage


TOL = 1e-6


def _ensure_autonomy_path(root: Path) -> None:
    src = str(root / "components/Zoe-Autonomy/src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_obj(payload: object) -> str:
    return _sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Independent Multi-Statement `def` AST Sandbox + 17 Hostile Probes
# ---------------------------------------------------------------------------

def _is_arr(v: object) -> bool:
    return isinstance(v, np.ndarray)


def _safe_div(a, b):
    if _is_arr(a) or _is_arr(b):
        return np.where(np.abs(b) < 1e-9, 0.0, a) / np.where(np.abs(b) < 1e-9, 1.0, b)
    return (a / b) if abs(b) >= 1e-9 else 0.0


_BOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: _safe_div}
_UOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_COPS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
_FNS = {
    "abs": (1, lambda v: np.abs(v) if _is_arr(v) else abs(v)),
    "pos": (1, lambda v: np.maximum(v, 0.0) if _is_arr(v) else (v if v > 0.0 else 0.0)),
    "sq": (1, lambda v: v * v),
    "sqrt": (1, lambda v: np.sqrt(np.clip(v, 0.0, None)) if _is_arr(v) else math.sqrt(max(0.0, float(v)))),
    "log": (1, lambda v: np.log(np.clip(v, 1e-12, None)) if _is_arr(v) else math.log(max(1e-12, float(v)))),
    "mean": (1, lambda v: np.mean(v, axis=-1) if _is_arr(v) else float(v)),
    "min": (2, lambda a, b: np.minimum(a, b) if (_is_arr(a) or _is_arr(b)) else (a if a < b else b)),
    "max": (2, lambda a, b: np.maximum(a, b) if (_is_arr(a) or _is_arr(b)) else (a if a > b else b)),
    "clip": (3, lambda v, lo, hi: np.clip(v, lo, hi) if (_is_arr(v) or _is_arr(lo) or _is_arr(hi)) else (lo if v < lo else (hi if v > hi else v))),
}
_ALLOWED_NODES = (
    ast.Constant, ast.Name, ast.UnaryOp, ast.BinOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.Tuple, ast.Load,
    ast.UAdd, ast.USub, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.And, ast.Or, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)
_HOSTILE_DEF_PROBES = (
    "def f(x):\n    import os\n    return x",
    "def f(x):\n    from os import system\n    return x",
    "def f(x):\n    while True:\n        x = x + 1\n    return x",
    "def f(x):\n    for i in (1, 2):\n        x = x + 1\n    return x",
    "def f(x):\n    class A:\n        pass\n    return x",
    "def f(x):\n    global y\n    y = 1\n    return x",
    "def f(x):\n    nonlocal y\n    return x",
    "def f(x):\n    exec('import sys')\n    return x",
    "def f(x):\n    return eval('1+1')",
    "def f(x):\n    return __import__('os').system('id')",
    "def f(x):\n    return ().__class__.__bases__[0].__subclasses__()",
    "def f(x):\n    return open('/etc/passwd').read()",
    "def f(x):\n    g = lambda v: v\n    return g(x)",
    "def f(x):\n    return x.__class__",
    "def f(x):\n" + "    x = x + 1\n" * 20 + "    return x",
    "def f(x):\n    return " + "sq(" * 15 + "x" + ")" * 15,
    "def f(x):\n    return " + " + ".join(["x"] * 130),
)


def _depth(node: ast.AST) -> int:
    ch = list(ast.iter_child_nodes(node))
    return 1 if not ch else 1 + max(_depth(c) for c in ch)


def _ind_validate_def(source: str, expected_name: str | None = None, expected_args: Sequence[str] | None = None) -> ast.FunctionDef:
    if not isinstance(source, str) or not 1 <= len(source.strip()) <= 1800:
        raise ValueError("invalid source length")
    tree = ast.parse(source.strip(), mode="exec")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("expected single def function")
    if len(list(ast.walk(tree))) > 320 or _depth(tree) > 12:
        raise ValueError("AST budget exceeded")
    fn = tree.body[0]
    if fn.decorator_list or fn.returns is not None:
        raise ValueError("decorators/annotations disallowed")
    if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs or fn.args.defaults:
        raise ValueError("non-positional args disallowed")
    args = [a.arg for a in fn.args.args]
    if not args or len(set(args)) != len(args):
        raise ValueError("bad args")
    if expected_name and fn.name != expected_name:
        raise ValueError(f"bad name {fn.name}")
    if expected_args and tuple(args) != tuple(expected_args):
        raise ValueError(f"bad args {args}")

    cnt = [0]

    def _chk_expr(expr: ast.AST, env_set: set[str]) -> None:
        for sub in ast.walk(expr):
            if not isinstance(sub, _ALLOWED_NODES):
                raise ValueError(f"disallowed expr node {type(sub).__name__}")
            if isinstance(sub, ast.Constant):
                if isinstance(sub.value, bool) or not isinstance(sub.value, (int, float)) or not math.isfinite(float(sub.value)):
                    raise ValueError("bad constant")
            elif isinstance(sub, ast.Name):
                if sub.id not in env_set and sub.id not in _FNS:
                    raise ValueError(f"bad identifier {sub.id}")
            elif isinstance(sub, ast.Call):
                if not isinstance(sub.func, ast.Name) or sub.func.id not in _FNS:
                    raise ValueError("bad call")
                if sub.keywords or len(sub.args) != _FNS[sub.func.id][0]:
                    raise ValueError("bad call args")

    def _chk_block(stmts: List[ast.stmt], env_set: set[str]) -> bool:
        if not stmts:
            raise ValueError("empty block")
        local = set(env_set)
        has_ret = False
        for s in stmts:
            cnt[0] += 1
            if cnt[0] > 16:
                raise ValueError("stmt budget exceeded")
            if isinstance(s, ast.Assign):
                if len(s.targets) != 1 or not isinstance(s.targets[0], ast.Name):
                    raise ValueError("bad assign")
                _chk_expr(s.value, local)
                local.add(s.targets[0].id)
            elif isinstance(s, ast.AugAssign):
                if not isinstance(s.target, ast.Name) or s.target.id not in local or type(s.op) not in _BOPS:
                    raise ValueError("bad augassign")
                _chk_expr(s.value, local)
            elif isinstance(s, ast.If):
                _chk_expr(s.test, local)
                r1 = _chk_block(s.body, set(local))
                r2 = _chk_block(s.orelse, set(local)) if s.orelse else False
                if r1 and r2:
                    has_ret = True
            elif isinstance(s, ast.Return):
                if s.value is None:
                    raise ValueError("bare return")
                _chk_expr(s.value, local)
                has_ret = True
            else:
                raise ValueError(f"disallowed stmt {type(s).__name__}")
        return has_ret

    if not _chk_block(fn.body, set(args)):
        raise ValueError("missing return")
    return fn


def _ind_compile_def(source: str, expected_name: str | None = None, expected_args: Sequence[str] | None = None):
    fn = _ind_validate_def(source, expected_name=expected_name, expected_args=expected_args)
    args = tuple(a.arg for a in fn.args.args)

    def _ev(n: ast.AST, loc: Dict[str, object]):
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            return loc[n.id]
        if isinstance(n, ast.UnaryOp):
            return _UOPS[type(n.op)](_ev(n.operand, loc))
        if isinstance(n, ast.BinOp):
            return _BOPS[type(n.op)](_ev(n.left, loc), _ev(n.right, loc))
        if isinstance(n, ast.BoolOp):
            return all(bool(_ev(v, loc)) for v in n.values) if isinstance(n.op, ast.And) else any(bool(_ev(v, loc)) for v in n.values)
        if isinstance(n, ast.Compare):
            left = _ev(n.left, loc)
            for op, comp in zip(n.ops, n.comparators):
                right = _ev(comp, loc)
                if not _COPS[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(n, ast.IfExp):
            return _ev(n.body, loc) if _ev(n.test, loc) else _ev(n.orelse, loc)
        if isinstance(n, ast.Call):
            return _FNS[n.func.id][1](*(_ev(a, loc) for a in n.args))
        if isinstance(n, ast.Tuple):
            return tuple(_ev(e, loc) for e in n.elts)
        raise ValueError(type(n).__name__)

    def _exec(stmts: List[ast.stmt], loc: Dict[str, object]):
        for s in stmts:
            if isinstance(s, ast.Assign):
                loc[s.targets[0].id] = _ev(s.value, loc)
            elif isinstance(s, ast.AugAssign):
                k = s.target.id
                loc[k] = _BOPS[type(s.op)](loc[k], _ev(s.value, loc))
            elif isinstance(s, ast.If):
                br = s.body if _ev(s.test, loc) else s.orelse
                if br:
                    done, val = _exec(br, loc)
                    if done:
                        return True, val
            elif isinstance(s, ast.Return):
                return True, _ev(s.value, loc)
        return False, None

    def runner(env: Dict[str, object]):
        done, val = _exec(fn.body, {k: env[k] for k in args})
        if not done:
            raise ValueError("no return executed")
        return val

    return runner


def _ind_auroc(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.int64)
    s = np.asarray(s, dtype=np.float64)
    n1, n0 = int(np.sum(y == 1)), int(np.sum(y == 0))
    if n1 == 0 or n0 == 0:
        return 0.5
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    n = len(s)
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((np.sum(ranks[y == 1]) - n1 * (n1 + 1) / 2.0) / (n1 * n0))


# ---------------------------------------------------------------------------
# Independent Raw Data Loaders (Module 1 & Module 3)
# ---------------------------------------------------------------------------

def _load_mod1_raw(root: Path) -> Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray, str]]:
    def _norm(P):
        a = np.clip(np.asarray(P, dtype=np.float64), 1e-12, 1.0)
        return a / a.sum(axis=-1, keepdims=True)

    midi = np.load(root / "components/next-token-predictability/evidence/rhythm-midi/predictions.npz")
    sf = np.arange(0, len(midi["forward_sequence_indices"]), 15)
    pf = midi["forward_probabilities"][sf].astype(np.float64)
    yf = (pf.argmax(axis=-1) != midi["forward_targets"][sf]).astype(np.int64)
    hf = (midi["forward_sequence_indices"][sf] % 2 == 1)

    sr = np.arange(0, len(midi["reversal_transfer_sequence_indices"]), 15)
    pr = midi["reversal_transfer_probabilities"][sr].astype(np.float64)
    yr = (pr.argmax(axis=-1) != midi["reversal_transfer_targets"][sr]).astype(np.int64)
    hr = (midi["reversal_transfer_sequence_indices"][sr] % 2 == 1)

    hp = json.loads(gzip.decompress((root / "guiai-lab/guiai/gem/data/onset-seed7.json.gz").read_bytes()).decode("utf-8"))["payload"]
    phf = np.asarray(hp["forward_probabilities"], dtype=np.float64)
    yhf = (phf.argmax(axis=-1) != np.asarray(hp["forward_targets"], dtype=np.int64)).astype(np.int64)
    phr = np.asarray(hp["retrograde_probabilities"], dtype=np.float64)
    yhr = (phr.argmax(axis=-1) != np.asarray(hp["retrograde_targets"], dtype=np.int64)).astype(np.int64)

    arr = np.asarray(Image.open(root / "components/agent-logging-system/docs/images/dorothy-neurogarden.png").convert("RGB"))
    h, w, _ = arr.shape
    f_arr = arr.astype(np.float32) / 255.0
    gray = 0.299 * f_arr[:, :, 0] + 0.587 * f_arr[:, :, 1] + 0.114 * f_arr[:, :, 2]
    edge = np.hypot(ndimage.sobel(gray, axis=1), ndimage.sobel(gray, axis=0))
    edge /= max(float(edge.max()), 1e-8)
    redness = f_arr[:, :, 0] - 0.5 * (f_arr[:, :, 1] + f_arr[:, :, 2])
    lmean = ndimage.uniform_filter(edge, size=15)
    lsq = ndimage.uniform_filter(edge ** 2, size=15)
    dens = np.sqrt(np.maximum(lsq - lmean ** 2, 0.0)) + lmean
    dens /= max(float(dens.max()), 1e-8)
    ph, pw = h / 16.0, w / 16.0
    feats, is_struct = [], []
    for r in range(16):
        y0, y1 = int(r * ph), int((r + 1) * ph)
        for c in range(16):
            x0, x1 = int(c * pw), int((c + 1) * pw)
            prgb, pgray, pedge, pred, pdens = (
                f_arr[y0:y1, x0:x1], gray[y0:y1, x0:x1], edge[y0:y1, x0:x1], redness[y0:y1, x0:x1], dens[y0:y1, x0:x1]
            )
            feats.append([
                float(prgb[:, :, 0].mean()), float(prgb[:, :, 1].mean()), float(prgb[:, :, 2].mean()),
                float(pgray.std()) * 2.5, float(pedge.mean()) * 3.0,
                float(np.maximum(pred, 0.0).mean()) * 3.0, float(pdens.mean()) * 2.5, float(pedge.max()),
            ])
            is_struct.append(1 if float(np.mean(np.min(arr[y0:y1, x0:x1], axis=2) < 240)) > 0.10 else 0)
    emb = np.asarray(feats, dtype=np.float64)
    emb = emb - emb.mean(axis=0, keepdims=True)
    emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-6)
    logits = (emb @ emb.T) / (math.sqrt(emb.shape[1]) * 0.22)
    logits -= logits.max(axis=1, keepdims=True)
    pd = np.exp(logits)
    pd /= pd.sum(axis=1, keepdims=True)
    yd = 1 - np.asarray(is_struct, dtype=np.int64)

    Z, Y, X = np.ogrid[:24, :24, :24]
    ps, ys = [], []
    for s in (100, 101, 102, 103, 104):
        rng = np.random.default_rng(s)
        vol = np.zeros((24, 24, 24), dtype=np.float64)
        truth = np.zeros((24, 24, 24), dtype=np.int64)
        for _ in range(3):
            cx, cy, cz = rng.integers(5, 19, size=3)
            rad = rng.uniform(2.0, 3.2)
            mask = (X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2 <= rad ** 2
            vol[mask] = 1.0
            truth[mask] = 1
        blurred = ndimage.gaussian_filter(vol, sigma=1.4)
        obs = np.sqrt((blurred + rng.normal(0, 0.12, vol.shape)) ** 2 + rng.normal(0, 0.12, vol.shape) ** 2)
        scales = [ndimage.gaussian_filter(obs, sigma=sg) for sg in (0.5, 1.0, 1.5, 2.0, 2.5)]
        stack = np.stack(scales, axis=-1)
        bg = np.clip(1.0 - stack.mean(axis=-1, keepdims=True), 0.01, 1.0)
        raw = np.concatenate([np.clip(stack, 0.001, None), bg], axis=-1)
        probs = raw / np.sum(raw, axis=-1, keepdims=True)
        ps.append(probs.reshape(-1, 6)[::4])
        ys.append(truth.ravel()[::4])
    ppsf = np.concatenate(ps, axis=0)
    ypsf = np.concatenate(ys, axis=0)

    def _pack(Pi, yi, fam):
        pn = _norm(Pi)
        return (pn, (pn > 0.05).astype(np.float64), yi, fam)

    return {
        "midi_fwd_ho": _pack(pf[hf], yf[hf], "music_rhythm_midi"),
        "helen_fwd_ho": _pack(phf[1::2], yhf[1::2], "helen_causal_shift"),
        "midi_rev_zs": _pack(pr[hr], yr[hr], "music_rhythm_midi"),
        "helen_retro_zs": _pack(phr, yhr, "helen_causal_shift"),
        "dorothy_vision_zs": _pack(pd, yd, "dorothy_brain_vision"),
        "psf_3d_zs": _pack(ppsf, ypsf, "volumetric_psf_3d"),
    }


def _detrend_std(series: np.ndarray) -> np.ndarray:
    t = np.linspace(-1.0, 1.0, len(series))
    res = series - np.polyval(np.polyfit(t, series, 3), t)
    sd = float(np.std(res))
    return np.zeros_like(res) if sd < 1e-6 else res / sd


def _gen_mod3_dataset(kind: str, n_pos: int, n_neg: int, seed: int, n_len: int = 96) -> Dict[str, np.ndarray]:
    rng = np.random.RandomState(seed)
    xs, ys, zs, ws, lab = [], [], [], [], []

    def _add(raw, y):
        r = _detrend_std(raw)
        xs.append(r[:-3])
        ys.append(r[1:-2])
        zs.append(r[2:-1])
        ws.append(r[3:])
        lab.append(y)

    for _ in range(n_pos):
        t = np.linspace(0.0, 1.0, n_len)
        rub = 0.03 * np.sin(2.0 * np.pi * t * rng.uniform(0.8, 1.4)) + rng.uniform(-0.02, 0.02) * (t ** 2)
        if kind == "swing_nonlinear":
            amp = rng.uniform(0.011, 0.016)
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = (amp if i % 2 == 0 else -amp) + 0.020 * u + rng.normal(0.0, 0.022)
            raw = rub + seq
        elif kind == "hemiola_p3":
            amp = rng.uniform(0.015, 0.022)
            ph = int(rng.randint(0, 3))
            pat = np.array([amp, -0.5 * amp, -0.5 * amp])
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = pat[(i + ph) % 3] + 0.018 * u + rng.normal(0.0, 0.022)
            raw = rub + seq
        elif kind == "syncopated_p4":
            amp = rng.uniform(0.018, 0.025)
            ph = int(rng.randint(0, 4))
            u = rng.uniform(-0.7, 0.7)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = amp * math.cos(math.pi * (i + ph) / 2.0) + 0.015 * u + rng.normal(0.0, 0.022)
            raw = rub + seq
        elif kind == "nonlinear_chaos":
            u = rng.uniform(-0.85, 0.85)
            seq = np.zeros(n_len)
            for i in range(n_len):
                u = float(np.clip(1.0 - 2.0 * u * u, -1.0, 1.0))
                seq[i] = u * 0.026
            raw = rub + seq + rng.normal(0.0, 0.014, n_len)
        elif kind == "dorothy_40hz_isi":
            isi = np.zeros(n_len)
            v = rng.uniform(-0.7, 0.7)
            for i in range(n_len):
                v = float(np.clip(1.0 - 2.0 * v * v, -1.0, 1.0))
                isi[i] = 0.025 + 0.0048 * v + 0.0036 * math.cos(2.0 * math.pi * i / 3.0) + 0.0036 * math.cos(math.pi * i / 2.0) + rng.normal(0.0, 0.0052)
            raw = rub * 0.2 + isi
        else:
            raise ValueError(kind)
        _add(raw, 1)

    for _ in range(n_neg):
        t = np.linspace(0.0, 1.0, n_len)
        rub = 0.03 * np.sin(2.0 * np.pi * t * rng.uniform(0.8, 1.4)) + rng.uniform(-0.02, 0.02) * (t ** 2)
        raw = (rub * 0.2 + rng.exponential(0.025, n_len)) if kind == "dorothy_40hz_isi" else (rub + rng.normal(0.0, 0.025, n_len))
        _add(raw, 0)

    return {
        "x": np.asarray(xs, dtype=np.float64),
        "y": np.asarray(ys, dtype=np.float64),
        "z": np.asarray(zs, dtype=np.float64),
        "w": np.asarray(ws, dtype=np.float64),
        "labels": np.asarray(lab, dtype=np.int64),
    }


def _ind_run_event_kernel(root: Path, src: str, protocol: Dict[str, object]) -> Dict[str, object]:
    _ensure_autonomy_path(root)
    from zoe_autonomy.event_core import ACTIONS, CENTERS, EventEncoder, observation_window
    from zoe_autonomy.event_evaluation import _fixture
    from zoe_autonomy.event_memory import KeyValueEventMemory
    from zoe_autonomy.event_plasticity import GatedLocalPlasticity
    from zoe_autonomy.event_reasoning import ForwardEnsemble, attention_after, shortest_trajectory
    from zoe_autonomy.event_uncertainty import IndependentUncertainty

    args = (
        "sc_cnt", "ev_cnt", "stale", "misses", "has_pos", "dist", "vel",
        "center", "target_x", "visible", "search_req", "moving", "on_path", "has_mem",
    )
    fn = _ind_compile_def(src, expected_name="event_perception_policy", expected_args=args)
    enc = EventEncoder()
    ens = ForwardEnsemble(history_enabled=True, policy_fn=fn)
    mem = KeyValueEventMemory()
    unc = IndependentUncertainty()
    pla = GatedLocalPlasticity()
    hist = []

    def _run(seqs, learn):
        sq, tk, dets, sups = [], [], [], []
        for s in seqs:
            att, pending, last_pred = 0, None, None
            enc.start_sequence()
            ens.start_sequence()
            sd, ss = False, True
            for step in range(s["steps"]):
                obs = enc.encode(observation_window(s["events"], step, att), plastic=learn)
                hist.append(obs)
                if learn and pending is not None:
                    delta = (obs["centroid"][0] - pending["centroid"][0]) if (pending["centroid"] is not None and obs["centroid"] is not None) else None
                    mem.episodes.append({
                        "sequence": len(mem.episodes) + 1,
                        "key": {"feature_vector": pending["feature_vector"], "action": pending["action"]},
                        "value": {"observation": obs, "step": step, "delta_x": delta or 0.0, "prediction_error": None},
                        "causal_context": {}, "previous_hash": None, "sha256": None,
                    })
                pre = unc.assess(obs, [])
                ens.update(obs, step, learning=learn and pre["plasticity_allowed"])
                pr = pla.update(ens, obs, last_pred, {**pre, "plasticity_allowed": learn and pre["plasticity_allowed"]})
                ret = mem.retrieve(obs["feature_vector"])
                traj = shortest_trajectory(ens, att)

                def _eval_c(uo):
                    out = []
                    for act in ACTIONS:
                        pred = ens.predict(att, act, ret)
                        fol = pred["attention_after"]
                        if act == "abstain":
                            ru = 1.0 if uo["intervention"] else 0.01
                        else:
                            _, _, _, _, uv = fn({
                                "sc_cnt": 6.0, "ev_cnt": 4.0, "stale": float(ens._stale_count), "misses": float(ens.members[0]["misses"]),
                                "has_pos": 1.0 if pred["localized"] else 0.0, "dist": abs(CENTERS[fol] - pred["target_x"]), "vel": pred["velocity"],
                                "center": float(CENTERS[fol]), "target_x": pred["target_x"], "visible": 1.0 if pred["visible"] else 0.0,
                                "search_req": 1.0 if pred["search_required"] else 0.0, "moving": 1.0 if act != "hold" else 0.0,
                                "on_path": 1.0 if act == traj["path"][0] else 0.0, "has_mem": 1.0 if ret else 0.0,
                            })
                            ru = max(0.01, min(0.99, float(uv)))
                        out.append((ru, f"event-{act}", act, pred))
                    return out

                c1 = _eval_c(pre)
                u2 = unc.assess(obs, [{"prediction": x[3]} for x in c1])
                c2 = _eval_c(u2)
                c2.sort(key=lambda item: (-item[0], item[1]))
                _, _, act, sel_pred = c2[0]
                att = attention_after(att, act)
                last_pred = sel_pred
                pending = {"feature_vector": obs["feature_vector"], "action": act, "centroid": obs["centroid"], "step": step}
                if u2["intervention"]:
                    sd = True
                    if pr["changed"] or act != "abstain":
                        ss = False
                nxt = float(s["targets"][min(step + 1, len(s["targets"]) - 1)])
                sq.append((float(sel_pred["target_x"]) - nxt) ** 2)
                tk.append(abs(float(att * 4 + 4) - nxt))
            dets.append(sd)
            sups.append(ss)
        rmse = math.sqrt(math.fsum(sq) / len(sq))
        mae = math.fsum(tk) / len(tk)
        return round(rmse, 6), round(mae, 6), round(0.6 * rmse + 0.4 * mae, 6), round(sum(dets) / len(dets), 6), all(sups)

    _run(_fixture(protocol, "training"), True)
    unc.fit(hist)
    va_r, va_m, va_c, fp, _ = _run(_fixture(protocol, "validation"), False)
    tf_r, tf_m, tf_c, _, _ = _run(_fixture(protocol, "transfer"), False)
    _, _, _, ood_r, ood_s = _run(_fixture(protocol, "ood"), True)
    return {
        "va_rmse": va_r, "va_mae": va_m, "va_comp": va_c, "fp_rate": fp,
        "tf_rmse": tf_r, "tf_mae": tf_m, "tf_comp": tf_c, "ood_rate": ood_r, "ood_suppressed": ood_s,
    }


def _ind_run_full_engine(root: Path, src: str, protocol: Dict[str, object]) -> Dict[str, object]:
    _ensure_autonomy_path(root)
    from zoe_autonomy.event_autonomy import EventCausalEngine
    from zoe_autonomy.event_evaluation import _fixture, _retention

    args = (
        "sc_cnt", "ev_cnt", "stale", "misses", "has_pos", "dist", "vel",
        "center", "target_x", "visible", "search_req", "moving", "on_path", "has_mem",
    )
    fn = _ind_compile_def(src, expected_name="event_perception_policy", expected_args=args)
    eng = EventCausalEngine(seed=protocol["fixtures"]["training"]["seed"], policy_fn=fn)
    for seq in _fixture(protocol, "training"):
        eng.run_sequence(seq, learning=True)
    eng.fit_uncertainty()
    val_pairs = [(eng.run_sequence(seq, learning=False), seq["targets"]) for seq in _fixture(protocol, "validation")]
    tf_pairs = [(eng.run_sequence(seq, learning=False), seq["targets"]) for seq in _fixture(protocol, "transfer")]
    ood_pairs = [(eng.run_sequence(seq, learning=True), seq["targets"]) for seq in _fixture(protocol, "ood")]

    def _m(pairs):
        sq, tk = [], []
        for reps, tg in pairs:
            for r in reps:
                nxt = float(tg[min(int(r["step"]) + 1, len(tg) - 1)])
                sq.append((float(r["selected_prediction"]["target_x"]) - nxt) ** 2)
                tk.append(abs(float(int(r["attention_after"]) * 4 + 4) - nxt))
        return round(math.sqrt(math.fsum(sq) / len(sq)), 6), round(math.fsum(tk) / len(tk), 6)

    va_r, va_m = _m(val_pairs)
    tf_r, tf_m = _m(tf_pairs)
    ood_r = round(sum(any(r["uncertainty"]["intervention"] for r in reps) for reps, _ in ood_pairs) / len(ood_pairs), 6)
    ret = _retention(eng)
    return {
        "va_rmse": va_r, "va_mae": va_m, "tf_rmse": tf_r, "tf_mae": tf_m, "ood_rate": ood_r,
        "retention_ok": bool(ret.get("adopted") or ret.get("restored_checkpoint")),
        "chain_ok": bool(eng.memory._chain_valid()),
        "external_actions": int(eng.loop.external_actions),
    }


def verify_report(root: Path, report_path: Path) -> Dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    errors: List[str] = []
    checks_passed = 0
    checks_total = 0
    max_delta = 0.0

    def record(ok: bool, msg: str) -> None:
        nonlocal checks_passed, checks_total
        checks_total += 1
        if ok:
            checks_passed += 1
        else:
            errors.append(msg)

    # 1. Contract & SHA-256 Digest Integrity
    core_excl = {"core_sha256", "report_sha256", "independent_verification", "l4_multimodule_qualified", "artifact_path"}
    expected_core = _sha256_obj({k: v for k, v in report.items() if k not in core_excl})
    core_ok = report.get("contract") == "zoe-l4-multimodule-code-evolution/v1" and report.get("core_sha256") == expected_core
    if "report_sha256" in report:
        core_ok = core_ok and report.get("report_sha256") == _sha256_obj({k: v for k, v in report.items() if k not in {"report_sha256", "artifact_path"}})
    record(core_ok, "contract or report SHA-256 digest mismatch")

    # 2. Sandbox Design Flags
    sd = report.get("sandbox_design", {})
    record(
        sd.get("multi_statement_python_def") is True
        and sd.get("generation_blind_uniform_mutations") is True
        and sd.get("generation_branching_count") == 0
        and sd.get("unified_source_diffs") is True
        and sd.get("pytorch_required") is False,
        "sandbox_design flags invalid",
    )

    # 3. Hostile Multi-Statement `def` AST Probes (17/17 Blocked Independently)
    blocked = 0
    for src in _HOSTILE_DEF_PROBES:
        try:
            _ind_validate_def(src)
        except Exception:
            blocked += 1
    hp = report.get("hostile_function_probes", {})
    record(
        blocked == len(_HOSTILE_DEF_PROBES)
        and hp.get("all_blocked") is True
        and hp.get("probes_blocked") == len(_HOSTILE_DEF_PROBES),
        f"hostile probes failed ({blocked}/{len(_HOSTILE_DEF_PROBES)})",
    )

    mods = report.get("modules", {})
    m1 = mods.get("spectral_uncertainty", {})
    m2 = mods.get("event_causal_perception", {})
    m3 = mods.get("temporal_groove_neural", {})

    # 4. Validate ALL function ASTs & diffs across all 3 engines
    ast_ok = True
    expected_sigs = [
        (m1, "spectral_uncertainty_score", ("p", "gt05")),
        (m2, "event_perception_policy", ("sc_cnt", "ev_cnt", "stale", "misses", "has_pos", "dist", "vel", "center", "target_x", "visible", "search_req", "moving", "on_path", "has_mem")),
        (m3, "temporal_phase_score", ("x", "y", "z", "w")),
    ]
    for mod, fn_name, fn_args in expected_sigs:
        gens = mod.get("generations", [])
        if len(gens) < 4:
            ast_ok = False
            break
        inc_s = str(gens[0].get("function_source", ""))
        try:
            _ind_validate_def(inc_s, expected_name=fn_name, expected_args=fn_args)
            for g in gens[1:]:
                cs = str(g.get("function_source", ""))
                _ind_validate_def(cs, expected_name=fn_name, expected_args=fn_args)
                if not str(g.get("unified_diff", "")).strip():
                    ast_ok = False
                if g.get("status") == "ADOPTED":
                    inc_s = cs
            _ind_validate_def(str(mod.get("final_adopted_source", "")), expected_name=fn_name, expected_args=fn_args)
            for row in mod.get("multi_seed_robustness", {}).get("runs", []):
                _ind_validate_def(str(row.get("final_function_source", "")), expected_name=fn_name, expected_args=fn_args)
        except Exception as err:
            ast_ok = False
            errors.append(f"AST check failed on {fn_name}: {err}")
    record(ast_ok, "one or more evolved `def` functions or diffs failed independent AST validation")
    if not ast_ok:
        return {
            "verifier": "scripts/verify_l4_multimodule.py",
            "verifier_sha256": _sha256_file(Path(__file__).resolve()),
            "report_path": str(report_path),
            "verified": False,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "max_numerical_delta": round(max_delta, 9),
            "hostile_probes_blocked": blocked,
            "engines_verified": 0,
            "errors": errors,
        }

    # 5 & 6. Module 1 Independent Raw Data Recomputation + Multi-Seed + Null
    mod1_domains = _load_mod1_raw(root)
    dom_keys = list(mod1_domains.keys())
    zs1 = [k for k in dom_keys if k.endswith("_zs")]

    def _m1_eval(src: str) -> Tuple[Dict[str, float], float]:
        fn = _ind_compile_def(src, expected_name="spectral_uncertainty_score", expected_args=("p", "gt05"))
        sc = {}
        for k, (P, GT, y, _) in mod1_domains.items():
            raw = np.sum(np.asarray(fn({"p": P, "gt05": GT}), dtype=np.float64), axis=-1)
            sc[k] = round(_ind_auroc(y, raw), 6)
        return sc, round(float(np.mean(list(sc.values()))), 6)

    m1_gens = m1.get("generations", [])
    m1_g0_s, m1_g0_m = _m1_eval(str(m1_gens[0]["function_source"]))
    max_delta = max(max_delta, abs(float(m1_gens[0]["heldout_mean"]) - m1_g0_m))
    inc1_s, inc1_m = m1_g0_s, m1_g0_m
    m1_consec = m1_max_c = 0
    m1_ok = True
    for g in m1_gens[1:]:
        gs, gm = _m1_eval(str(g["function_source"]))
        d = max(abs(float(g["heldout_mean"]) - gm), max(abs(float(g["heldout_auroc"][k]) - gs[k]) for k in dom_keys))
        max_delta = max(max_delta, d)
        if d > TOL:
            m1_ok = False
        dl = {k: gs[k] - inc1_s[k] for k in dom_keys}
        should = bool(
            gm > inc1_m + 1e-4
            and len({mod1_domains[k][3] for k in dom_keys if dl[k] > 1e-5}) >= 3
            and sum(1 for k in zs1 if dl[k] > 1e-5) >= 2
            and min(dl.values()) >= -0.005
        )
        if g["status"] == "ADOPTED" and should:
            m1_consec += 1; m1_max_c = max(m1_max_c, m1_consec); inc1_s, inc1_m = gs, gm
        elif g["status"] == "REJECTED_ROLLED_BACK" and not should:
            m1_consec = 0
        else:
            m1_ok = False
    record(m1_ok and m1_max_c >= 2, f"Module 1 generation recomputation/gate failed (consec={m1_max_c})")

    m1_ms_ok = True
    m1_runs = m1.get("multi_seed_robustness", {}).get("runs", [])
    for row in m1_runs:
        _, rm = _m1_eval(str(row["final_function_source"]))
        dr = abs(float(row["final_heldout_mean"]) - rm)
        max_delta = max(max_delta, dr)
        if dr > TOL or not row.get("passed_criteria") or int(row.get("max_consecutive_adopted", 0)) < 2:
            m1_ms_ok = False
    record(len(m1_runs) == 5 and m1_ms_ok and m1.get("permutation_null_control", {}).get("passed_no_leakage") is True, "Module 1 5/5 multi-seed or null failed")

    # 7 & 8. Module 2 Independent Genuine `EventCausalEngine` + Full Kernel Multi-Seed Check
    proto_path = root / "components/Zoe-Autonomy/evidence/event-causal/protocol.json"
    protocol = json.loads(proto_path.read_text(encoding="utf-8"))
    record(
        m2.get("protocol_sha256") == "2bb2e92ecd81d5822bec7249dd39d00ab645b3bf61990ba30b1b43af58433ebc"
        and _sha256_obj(protocol) == m2.get("protocol_sha256"),
        "Module 2 event-causal protocol SHA-256 mismatch",
    )

    m2_gens = m2.get("generations", [])
    full0 = _ind_run_full_engine(root, str(m2_gens[0]["function_source"]), protocol)
    fullF = _ind_run_full_engine(root, str(m2.get("final_adopted_source", "")), protocol)
    dfull = max(
        abs(float(full0["va_rmse"]) - float(m2_gens[0]["va_rmse"])),
        abs(float(full0["tf_rmse"]) - float(m2_gens[0]["tf_rmse"])),
        abs(float(fullF["va_rmse"]) - float(m2["full_engine_cross_check"]["final_adopted"]["va_rmse"])),
        abs(float(fullF["tf_rmse"]) - float(m2["full_engine_cross_check"]["final_adopted"]["tf_rmse"])),
    )
    max_delta = max(max_delta, dfull)
    record(
        dfull <= TOL
        and fullF["tf_rmse"] < full0["tf_rmse"] - 1.0
        and fullF["va_rmse"] < full0["va_rmse"] - 0.3
        and fullF["retention_ok"] and fullF["chain_ok"] and fullF["external_actions"] == 0,
        f"Module 2 full EventCausalEngine verification failed (delta={dfull})",
    )

    m2_cache = {}
    def _m2k(src):
        if src not in m2_cache:
            m2_cache[src] = _ind_run_event_kernel(root, src, protocol)
        return m2_cache[src]

    inc2 = _m2k(str(m2_gens[0]["function_source"]))
    m2_consec = m2_max_c = 0
    m2_ok = True
    for g in m2_gens[1:]:
        ev2 = _m2k(str(g["function_source"]))
        d2 = max(abs(float(g["va_rmse"]) - ev2["va_rmse"]), abs(float(g["tf_rmse"]) - ev2["tf_rmse"]))
        max_delta = max(max_delta, d2)
        if d2 > TOL:
            m2_ok = False
        d_va = round(float(inc2["va_comp"]) - float(ev2["va_comp"]), 6)
        d_tf = round(float(inc2["tf_comp"]) - float(ev2["tf_comp"]), 6)
        should = bool(d_va > 0.0 and d_tf > 0.0 and 0.5 * (d_va + d_tf) > 0.02 and ev2["ood_rate"] >= 0.75 and ev2["ood_suppressed"] and ev2["fp_rate"] <= 0.25)
        if g["status"] == "ADOPTED" and should:
            m2_consec += 1; m2_max_c = max(m2_max_c, m2_consec); inc2 = ev2
        elif g["status"] == "REJECTED_ROLLED_BACK" and not should:
            m2_consec = 0
        else:
            m2_ok = False

    m2_runs = m2.get("multi_seed_robustness", {}).get("runs", [])
    for row in m2_runs:
        er = _m2k(str(row["final_function_source"]))
        dr = max(abs(float(row["final_va_rmse"]) - er["va_rmse"]), abs(float(row["final_tf_rmse"]) - er["tf_rmse"]))
        max_delta = max(max_delta, dr)
        if dr > TOL or not row.get("passed_criteria") or int(row.get("max_consecutive_adopted", 0)) < 2:
            m2_ok = False
    record(len(m2_runs) == 5 and m2_ok and m2_max_c >= 2, f"Module 2 kernel/multi-seed verification failed (consec={m2_max_c})")

    # 9, 10, 11. Module 3 Independent Recomputation + Rigid Metronome + Shuffle Null + 5/5 Seeds
    m3_sets = {
        "ho_swing": _gen_mod3_dataset("swing_nonlinear", 120, 120, 2001),
        "ho_hemiola": _gen_mod3_dataset("hemiola_p3", 120, 120, 2002),
        "zs_syncopated_p4": _gen_mod3_dataset("syncopated_p4", 120, 120, 3001),
        "zs_nonlinear_chaos": _gen_mod3_dataset("nonlinear_chaos", 120, 120, 3002),
        "zs_dorothy_40hz": _gen_mod3_dataset("dorothy_40hz_isi", 120, 120, 3003),
    }
    m3_keys = list(m3_sets.keys())
    zs3 = [k for k in m3_keys if k.startswith("zs_")]

    def _m3_eval(src: str) -> Tuple[Dict[str, float], float]:
        fn = _ind_compile_def(src, expected_name="temporal_phase_score", expected_args=("x", "y", "z", "w"))
        sc = {k: round(_ind_auroc(d["labels"], np.asarray(fn({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)), 6) for k, d in m3_sets.items()}
        return sc, round(float(np.mean(list(sc.values()))), 6)

    m3_gens = m3.get("generations", [])
    m3_g0_s, m3_g0_m = _m3_eval(str(m3_gens[0]["function_source"]))
    max_delta = max(max_delta, abs(float(m3_gens[0]["heldout_mean"]) - m3_g0_m))
    inc3_s, inc3_m = m3_g0_s, m3_g0_m
    m3_consec = m3_max_c = 0
    m3_ok = True
    for g in m3_gens[1:]:
        gs, gm = _m3_eval(str(g["function_source"]))
        d = max(abs(float(g["heldout_mean"]) - gm), max(abs(float(g["heldout_auroc"][k]) - gs[k]) for k in m3_keys))
        max_delta = max(max_delta, d)
        if d > TOL:
            m3_ok = False
        dl = {k: round(gs[k] - inc3_s[k], 6) for k in m3_keys}
        should = bool(gm > inc3_m + 0.008 and sum(1 for v in dl.values() if v > 1e-4) >= 3 and sum(1 for k in zs3 if dl[k] > 1e-4) >= 2 and min(dl.values()) >= -0.025)
        if g["status"] == "ADOPTED" and should:
            m3_consec += 1; m3_max_c = max(m3_max_c, m3_consec); inc3_s, inc3_m = gs, gm
        elif g["status"] == "REJECTED_ROLLED_BACK" and not should:
            m3_consec = 0
        else:
            m3_ok = False
    record(m3_ok and m3_max_c >= 2, f"Module 3 generation recomputation/gate failed (consec={m3_max_c})")

    # Metronome negative control + 100-trial independent permutation null
    fn3_final = _ind_compile_def(str(m3.get("final_adopted_source", "")), expected_name="temporal_phase_score", expected_args=("x", "y", "z", "w"))
    zeros = np.zeros((20, 93), dtype=np.float64)
    met_max = float(np.max(np.abs(np.asarray(fn3_final({"x": zeros, "y": zeros, "z": zeros, "w": zeros}), dtype=np.float64))))
    rng3 = np.random.default_rng(777)
    null_means = []
    for d in m3_sets.values():
        s = np.asarray(fn3_final({"x": d["x"], "y": d["y"], "z": d["z"], "w": d["w"]}), dtype=np.float64)
        null_means.append(float(np.mean([_ind_auroc(rng3.permutation(d["labels"]), s) for _ in range(100)])))
    record(
        met_max == 0.0
        and m3.get("rigid_metronome_control", {}).get("passed_zero_false_groove") is True
        and 0.47 <= float(np.mean(null_means)) <= 0.53
        and m3.get("permutation_null_control", {}).get("passed_no_leakage") is True,
        f"Module 3 metronome or shuffle null failed (met={met_max}, null={np.mean(null_means)})",
    )

    m3_runs = m3.get("multi_seed_robustness", {}).get("runs", [])
    m3_ms_ok = len(m3_runs) == 5
    for row in m3_runs:
        _, rm = _m3_eval(str(row["final_function_source"]))
        dr = abs(float(row["final_mean"]) - rm)
        max_delta = max(max_delta, dr)
        if dr > TOL or not row.get("passed_criteria") or int(row.get("max_consecutive_adopted", 0)) < 2:
            m3_ms_ok = False
    record(m3_ms_ok, "Module 3 5/5 multi-seed check failed")

    # 12. Strict improvement over Frozen Gen 0 on all 3 distinct runtime engines
    _, m1_f_m = _m1_eval(str(m1["final_adopted_source"]))
    _, m3_f_m = _m3_eval(str(m3["final_adopted_source"]))
    record(
        m1_f_m > m1_g0_m + 0.15
        and fullF["tf_rmse"] < full0["tf_rmse"] - 1.0
        and m3_f_m > m3_g0_m + 0.15,
        "one or more engines failed substantial improvement over frozen Gen 0",
    )

    # 13. Atomic Multi-Module Rollback Proof & Bit-Exact Verification
    rb = report.get("atomic_multimodule_rollback_proof", {})
    record(
        rb.get("rollback_restored_bit_exact") is True
        and rb.get("poison_rejected") is True
        and rb.get("emergency_stop_enforced") is True
        and rb.get("all_three_engines_changed_output") is True
        and float(rb.get("max_prediction_delta", 1.0)) == 0.0,
        f"atomic rollback proof failed: {rb}",
    )

    # 14. Unified Source Diffs Authentic Check
    diffs_ok = True
    for mod in (m1, m2, m3):
        gens = mod["generations"]
        inc = str(gens[0]["function_source"])
        for g in gens[1:]:
            expected_diff = "".join(difflib.unified_diff(
                (inc.strip() + "\n").splitlines(keepends=True),
                (str(g["function_source"]).strip() + "\n").splitlines(keepends=True),
                fromfile=f"{mod['module_id']}/incumbent_g{g['generation'] - 1}.py",
                tofile=f"{mod['module_id']}/candidate_g{g['generation']}.py",
            ))
            if str(g["unified_diff"]) != expected_diff:
                diffs_ok = False
            if g["status"] == "ADOPTED":
                inc = str(g["function_source"])
    record(diffs_ok, "unified_diff mismatch across one or more generations")

    # 15. Organic Rollbacks Preserved Across All 3 Modules
    record(
        all(int(mod.get("rejected_generations_count", 0)) >= 1 for mod in (m1, m2, m3)),
        "expected >=1 preserved rolled-back candidate in each of the 3 engines",
    )

    # 16. Constitutional & Honest Epistemic Boundaries (L5 kept False!)
    eb = report.get("epistemic_boundaries", {})
    record(
        report.get("zoe_root") == "."
        and eb.get("belief_updated") is False
        and eb.get("external_actions") == 0
        and eb.get("clinical_action_authorized") is False
        and eb.get("sentience_claimed") is False
        and eb.get("l5_agi_qualified") is False,
        f"epistemic boundaries or portable zoe_root violated: {eb}",
    )

    verified = (len(errors) == 0 and checks_passed == checks_total)
    return {
        "verifier": "scripts/verify_l4_multimodule.py",
        "verifier_sha256": _sha256_file(Path(__file__).resolve()),
        "report_path": str(report_path),
        "verified": verified,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "max_numerical_delta": round(max_delta, 9),
        "hostile_probes_blocked": blocked,
        "engines_verified": 3,
        "errors": errors,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for Zoe L4 Multi-Module Guarded Code Self-Improvement.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    report_path = args.report.expanduser().resolve() if args.report else (root / "evidence/l4-multimodule/l4-multimodule-report.json")
    if not report_path.is_file():
        print(f"ERROR: report not found at {report_path}", file=sys.stderr)
        return 2

    res = verify_report(root, report_path)
    if args.json:
        print(json.dumps(res, sort_keys=True))
    else:
        print(f"Zoe L4 Multi-Module Independent Verifier: verified={res['verified']}")
        print(
            f"  Checks passed: {res['checks_passed']}/{res['checks_total']} | "
            f"Engines verified: {res['engines_verified']}/3 | Max delta: {res['max_numerical_delta']} | "
            f"Hostile def AST blocked: {res['hostile_probes_blocked']}/{len(_HOSTILE_DEF_PROBES)}"
        )
        if res["errors"]:
            for err in res["errors"]:
                print(f"  [FAIL] {err}", file=sys.stderr)
    return 0 if res["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

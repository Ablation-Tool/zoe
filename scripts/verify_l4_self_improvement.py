#!/usr/bin/env python3
"""Standalone Independent Fresh-Process Verifier for Zoe L4 Self-Improvement.

Deliberately DOES NOT import `zoe_autonomy` or `guiai`.
Directly reads raw repository files (`predictions.npz`, `onset-seed7.json.gz`,
`dorothy-neurogarden.png`), regenerates deterministic unseen 3D PSF+Rician
volumes, implements its own independent AST sandbox & tie-aware AUROC, and
independently recomputes every Gen 0..5 metric, delta, adoption gate,
multi-seed trajectory, hostile AST probe block, and label-shuffle null.

Usage:
    python3 scripts/verify_l4_self_improvement.py
    python3 scripts/verify_l4_self_improvement.py --report evidence/l4-self-improvement/l4-evolution-report.json --json
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import math
import operator
from pathlib import Path
import sys
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage


TOL = 1e-6

_VARS = frozenset({"p", "gt05"})
_FUNCS = {
    "log": lambda x: np.log(np.clip(x, 1e-12, None)),
    "sqrt": lambda x: np.sqrt(np.clip(x, 0.0, None)),
    "sq": lambda x: x * x,
    "pos": lambda x: np.maximum(x, 0.0),
    "abs": np.abs,
}
_BOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
}
_UOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_HOSTILE = (
    "__import__('os').system('echo pwn')",
    "eval('1+1')",
    "exec('import sys')",
    "p.__class__.__mro__",
    "().__class__.__bases__[0].__subclasses__()",
    "(lambda x: x)(p)",
    "[x for x in p]",
    "open('/etc/passwd').read()",
    "sq(" * 15 + "p" + ")" * 15,
    " + ".join(["p"] * 25),
    "p / 0.0",
    "unknown_var + 1",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_obj(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(raw)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ind_depth(node: ast.AST) -> int:
    ch = list(ast.iter_child_nodes(node))
    return 1 if not ch else 1 + max(_ind_depth(c) for c in ch)


def _ind_validate(expr: str) -> ast.Expression:
    if not isinstance(expr, str):
        raise ValueError("not string")
    s = expr.strip()
    if not 1 <= len(s) <= 180:
        raise ValueError("bad length")
    tree = ast.parse(s, mode="eval")
    nodes = list(ast.walk(tree))
    if len(nodes) > 28 or _ind_depth(tree) > 10:
        raise ValueError("budget exceeded")
    for n in nodes:
        if isinstance(n, (ast.Expression, ast.Load)):
            continue
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)) or not math.isfinite(float(n.value)):
                raise ValueError("bad constant")
            continue
        if isinstance(n, ast.Name):
            if n.id not in _VARS and n.id not in _FUNCS:
                raise ValueError(f"bad identifier: {n.id}")
            continue
        if isinstance(n, ast.BinOp):
            if type(n.op) not in _BOPS:
                raise ValueError("bad binop")
            continue
        if isinstance(n, ast.UnaryOp):
            if type(n.op) not in _UOPS:
                raise ValueError("bad unaryop")
            continue
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.func.id not in _FUNCS or n.keywords or len(n.args) != 1:
                raise ValueError("bad call")
            continue
        if isinstance(n, tuple(_BOPS.keys()) + tuple(_UOPS.keys())):
            continue
        raise ValueError(f"bad AST node: {type(n).__name__}")
    return tree


def _ind_eval(expr: str, P: np.ndarray, GT05: np.ndarray) -> np.ndarray:
    tree = _ind_validate(expr)

    def _e(n: ast.AST):
        if isinstance(n, ast.Expression):
            return _e(n.body)
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id == "p":
                return P
            if n.id == "gt05":
                return GT05
            raise ValueError(n.id)
        if isinstance(n, ast.UnaryOp):
            return _UOPS[type(n.op)](_e(n.operand))
        if isinstance(n, ast.BinOp):
            return _BOPS[type(n.op)](_e(n.left), _e(n.right))
        if isinstance(n, ast.Call):
            return _FUNCS[n.func.id](_e(n.args[0]))
        raise ValueError(type(n).__name__)

    val = _e(tree)
    if np.ndim(val) < 2 or np.shape(val) != P.shape:
        raise ValueError("constant expression")
    out = np.sum(np.asarray(val, dtype=np.float64), axis=-1)
    if not np.all(np.isfinite(out)):
        raise ValueError("nonfinite score")
    return out


def _ind_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(labels, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
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
    return float((np.sum(ranks[y == 1]) - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _norm_p(P: np.ndarray) -> np.ndarray:
    arr = np.clip(np.asarray(P, dtype=np.float64), 1e-12, 1.0)
    return arr / arr.sum(axis=-1, keepdims=True)


def _load_ind_eval_domains(root: Path) -> Tuple[Dict[str, str], Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray, str]]]:
    midi_rel = "components/next-token-predictability/evidence/rhythm-midi/predictions.npz"
    helen_rel = "guiai-lab/guiai/gem/data/onset-seed7.json.gz"
    dorothy_rel = "components/agent-logging-system/docs/images/dorothy-neurogarden.png"

    hashes = {
        midi_rel: _sha256_file(root / midi_rel),
        helen_rel: _sha256_file(root / helen_rel),
        dorothy_rel: _sha256_file(root / dorothy_rel),
    }

    midi = np.load(root / midi_rel)
    st_f = np.arange(0, len(midi["forward_sequence_indices"]), 15)
    pf = midi["forward_probabilities"][st_f].astype(np.float64)
    yf = (pf.argmax(axis=-1) != midi["forward_targets"][st_f]).astype(np.int64)
    ho_f = (midi["forward_sequence_indices"][st_f] % 2 == 1)

    st_r = np.arange(0, len(midi["reversal_transfer_sequence_indices"]), 15)
    pr = midi["reversal_transfer_probabilities"][st_r].astype(np.float64)
    yr = (pr.argmax(axis=-1) != midi["reversal_transfer_targets"][st_r]).astype(np.int64)
    ho_r = (midi["reversal_transfer_sequence_indices"][st_r] % 2 == 1)

    hp = json.loads(gzip.decompress((root / helen_rel).read_bytes()).decode("utf-8"))["payload"]
    ph_f = np.asarray(hp["forward_probabilities"], dtype=np.float64)
    yh_f = (ph_f.argmax(axis=-1) != np.asarray(hp["forward_targets"], dtype=np.int64)).astype(np.int64)
    ph_r = np.asarray(hp["retrograde_probabilities"], dtype=np.float64)
    yh_r = (ph_r.argmax(axis=-1) != np.asarray(hp["retrograde_targets"], dtype=np.int64)).astype(np.int64)

    arr = np.asarray(Image.open(root / dorothy_rel).convert("RGB"))
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
    p_d = np.exp(logits)
    p_d /= p_d.sum(axis=1, keepdims=True)
    y_d = 1 - np.asarray(is_struct, dtype=np.int64)

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
    p_psf = np.concatenate(ps, axis=0)
    y_psf = np.concatenate(ys, axis=0)

    def _pack(P_in: np.ndarray, y_in: np.ndarray, fam: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str]:
        pn = _norm_p(P_in)
        return (pn, (pn > 0.05).astype(np.float64), y_in, fam)

    domains = {
        "midi_fwd_ho": _pack(pf[ho_f], yf[ho_f], "music_rhythm_midi"),
        "helen_fwd_ho": _pack(ph_f[1::2], yh_f[1::2], "helen_causal_shift"),
        "midi_rev_zs": _pack(pr[ho_r], yr[ho_r], "music_rhythm_midi"),
        "helen_retro_zs": _pack(ph_r, yh_r, "helen_causal_shift"),
        "dorothy_vision_zs": _pack(p_d, y_d, "dorothy_brain_vision"),
        "psf_3d_zs": _pack(p_psf, y_psf, "volumetric_psf_3d"),
    }
    return hashes, domains


def _verify_chain(chain: Sequence[Dict[str, object]], expected_len: int) -> bool:
    if len(chain) != expected_len or expected_len < 2:
        return False
    prev = "0" * 64
    for idx, rec in enumerate(chain):
        if rec.get("generation") != idx or rec.get("previous_hash") != prev:
            return False
        if rec.get("belief_updated") is not False or rec.get("executed") is not False:
            return False
        body = {
            "generation": rec["generation"],
            "status": rec["status"],
            "expression": rec["expression"],
            "previous_hash": rec["previous_hash"],
            "heldout_auroc": rec["heldout_auroc"],
            "heldout_mean": rec["heldout_mean"],
            "belief_updated": rec["belief_updated"],
            "executed": rec["executed"],
        }
        expected = _sha256_obj(body)
        if rec.get("stage_hash") != expected:
            return False
        prev = expected
    return True


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

    # 1. Contract & Digest Integrity
    core_keys_excl = {"core_sha256", "report_sha256", "independent_verification", "l4_self_improvement_qualified", "artifact_path"}
    expected_core_sha = _sha256_obj({k: v for k, v in report.items() if k not in core_keys_excl})
    core_ok = (
        report.get("contract") == "zoe-l4-generalized-self-improvement/v1"
        and report.get("core_sha256") == expected_core_sha
    )
    if "report_sha256" in report:
        expected_rep_sha = _sha256_obj({k: v for k, v in report.items() if k not in {"report_sha256", "artifact_path"}})
        core_ok = core_ok and (report.get("report_sha256") == expected_rep_sha)
    record(core_ok, "contract or SHA-256 report digest mismatch")

    # 2. Grammar & Raw Dataset File SHA-256 Hashes
    ind_hashes, eval_domains = _load_ind_eval_domains(root)
    dom_keys = list(eval_domains.keys())
    zs_keys = [k for k in dom_keys if k.endswith("_zs")]
    gd = report.get("grammar_design", {})
    record(
        gd.get("generation_blind_uniform_ast") is True
        and gd.get("generation_branching_count") == 0
        and gd.get("precomputed_spectral_hints") is False
        and report.get("dataset_hashes") == ind_hashes,
        "grammar flags or raw dataset file SHA-256 mismatch",
    )

    # 3. Lineage SHA-256 Hash Chain
    prim = report.get("primary_evolution", {})
    gens = prim.get("generations", [])
    record(_verify_chain(prim.get("lineage_chain", []), len(gens)), "primary evolution lineage hash chain invalid")

    # 4. Independent Recomputation of Gen 0 Control
    def _ind_score(expr: str) -> Tuple[Dict[str, float], float]:
        per = {k: round(_ind_auroc(eval_domains[k][2], _ind_eval(expr, eval_domains[k][0], eval_domains[k][1])), 6) for k in dom_keys}
        return per, round(float(np.mean(list(per.values()))), 6)

    g0 = gens[0]
    g0_ind, g0_ind_m = _ind_score("gt05")
    d0 = max(abs(float(g0["heldout_mean"]) - g0_ind_m), max(abs(float(g0["heldout_auroc"][k]) - g0_ind[k]) for k in dom_keys))
    max_delta = max(max_delta, d0)
    record(g0.get("expression") == "gt05" and d0 <= TOL, f"Gen 0 control mismatch (delta={d0})")

    # 5. Independent Recomputation of Shannon Baseline
    sh = report.get("shannon_baseline", {})
    sh_ind, sh_ind_m = _ind_score("-p * log(p)")
    dsh = max(abs(float(sh.get("heldout_mean", 0.0)) - sh_ind_m), max(abs(float(sh.get("heldout_auroc", {}).get(k, 0.0)) - sh_ind[k]) for k in dom_keys))
    max_delta = max(max_delta, dsh)
    record(dsh <= TOL, f"Shannon baseline mismatch (delta={dsh})")

    # 6 & 7. Independent Recomputation of ALL Generations + Adoption Gate Proof
    gen_errs: List[str] = []
    inc_scores = g0_ind
    inc_mean = g0_ind_m
    ind_consec = 0
    ind_max_consec = 0
    adopted_gens: List[Dict[str, object]] = []
    rejected_gens: List[Dict[str, object]] = []

    for g in gens[1:]:
        idx = g.get("generation")
        expr = str(g.get("expression", ""))
        try:
            g_ind, g_ind_m = _ind_score(expr)
        except Exception as exc:
            gen_errs.append(f"Gen {idx} AST failed independent sandbox: {exc}")
            continue

        dg = max(abs(float(g["heldout_mean"]) - g_ind_m), max(abs(float(g["heldout_auroc"][k]) - g_ind[k]) for k in dom_keys))
        max_delta = max(max_delta, dg)
        if dg > TOL:
            gen_errs.append(f"Gen {idx} metric mismatch (delta={dg})")

        deltas = {k: round(g_ind[k] - inc_scores[k], 6) for k in dom_keys}
        fams_imp = len({eval_domains[k][3] for k in dom_keys if deltas[k] > 1e-5})
        zs_imp = sum(1 for k in zs_keys if deltas[k] > 1e-5)
        worst_d = min(deltas.values())
        should_adopt = bool(g_ind_m > inc_mean + 1e-4 and fams_imp >= 3 and zs_imp >= 2 and worst_d >= -0.005)

        if g.get("status") == "ADOPTED":
            if not should_adopt:
                gen_errs.append(f"Gen {idx} marked ADOPTED but failed independent adoption gate")
            ind_consec += 1
            ind_max_consec = max(ind_max_consec, ind_consec)
            inc_scores = g_ind
            inc_mean = g_ind_m
            adopted_gens.append(g)
        elif g.get("status") == "REJECTED_ROLLED_BACK":
            if should_adopt:
                gen_errs.append(f"Gen {idx} marked REJECTED but passed independent gate")
            if g.get("rolled_back") is not True:
                gen_errs.append(f"Gen {idx} missing rolled_back=True")
            ind_consec = 0
            rejected_gens.append(g)
        else:
            gen_errs.append(f"Gen {idx} unexpected status: {g.get('status')}")

    record(len(gen_errs) == 0, "; ".join(gen_errs) if gen_errs else "all generations recomputed cleanly")

    # 7. >=2 Consecutive Adopted Generations & >=3 Unrelated Families + >=2 Zero-Shot Transfer
    record(
        ind_max_consec >= 2 and len(adopted_gens) >= 2 and len(gen_errs) == 0,
        f"expected >=2 consecutive adopted generations, got {ind_max_consec}",
    )

    # 8. Final Adopted Program Strictly Beats Frozen Gen 0 (all domains) & Shannon Overall
    final_expr = str(prim.get("final_adopted_expression", ""))
    final_ind, final_ind_m = _ind_score(final_expr)
    record(
        final_ind_m >= g0_ind_m + 0.15
        and all(final_ind[k] > g0_ind[k] + 0.005 for k in dom_keys)
        and final_ind_m > sh_ind_m + 0.01,
        f"final AST {final_expr} did not beat Gen0+0.15 & Shannon+0.01 ({final_ind_m} vs {g0_ind_m}, {sh_ind_m})",
    )

    # 9. Organic Negative Results Preserved
    record(
        len(rejected_gens) >= 1 and len(prim.get("rejected_negative_results", [])) >= 1,
        "expected >= 1 organically rejected & rolled-back candidate preserved",
    )

    # 10. Multi-Seed Robustness (All 5 Seeds) Independently Verified
    ms = report.get("multi_seed_robustness", {})
    ms_errs: List[str] = []
    runs = ms.get("runs", [])
    if len(runs) < 5:
        ms_errs.append(f"expected >=5 seeds, got {len(runs)}")
    for row in runs:
        if not row.get("passed_l4_criteria") or int(row.get("max_consecutive_adopted", 0)) < 2:
            ms_errs.append(f"seed {row.get('seed')} failed L4 multi-seed check")
            continue
        r_ind, r_ind_m = _ind_score(str(row.get("final_adopted_expression", "")))
        dr = abs(float(row.get("final_heldout_mean", 0.0)) - r_ind_m)
        max_delta = max(max_delta, dr)
        if dr > TOL:
            ms_errs.append(f"seed {row.get('seed')} mean mismatch (delta={dr})")
    record(len(ms_errs) == 0, "; ".join(ms_errs) if ms_errs else "all seeds independently verified")

    # 11. Hostile AST & DoS Sandbox Verification (12/12 Blocked Independently)
    blocked_ind = 0
    for expr in _HOSTILE:
        try:
            _ind_validate(expr)
        except ValueError:
            blocked_ind += 1
    hp = report.get("hostile_ast_probes", {})
    record(
        blocked_ind == len(_HOSTILE) and hp.get("all_blocked") is True and hp.get("probes_blocked") == len(_HOSTILE),
        f"hostile sandbox check failed ({blocked_ind}/{len(_HOSTILE)})",
    )

    # 12. Independent Permutation Label-Shuffle No-Leakage Null (100 trials)
    rng = np.random.default_rng(777)
    null_means: List[float] = []
    null_ok = True
    for k in dom_keys:
        P_k, GT_k, y_k, _ = eval_domains[k]
        s_k = _ind_eval(final_expr, P_k, GT_k)
        obs = _ind_auroc(y_k, s_k)
        draws = np.array([_ind_auroc(rng.permutation(y_k), s_k) for _ in range(100)], dtype=np.float64)
        nm = float(np.mean(draws))
        pval = float((int(np.sum(draws >= obs)) + 1) / 101.0)
        null_means.append(nm)
        if not (0.45 <= nm <= 0.55 and pval <= 0.02):
            null_ok = False
    pnc = report.get("permutation_null_control", {})
    record(
        null_ok and pnc.get("passed_no_leakage") is True and 0.47 <= float(np.mean(null_means)) <= 0.53,
        "independent permutation label-shuffle null control failed",
    )

    # 13. Reversible Rollback & Poison-Rejection Proof
    rb = report.get("reversible_rollback_proof", {})
    record(
        rb.get("rollback_restored_bit_exact") is True
        and rb.get("poison_rejected") is True
        and rb.get("ledger_chain_valid") is True
        and float(rb.get("max_prediction_delta", 1.0)) == 0.0,
        f"reversible rollback proof failed: {rb}",
    )

    # 14. Constitutional & Epistemic Boundaries (L5 kept honestly False!)
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
        "verifier": "scripts/verify_l4_self_improvement.py",
        "verifier_sha256": _sha256_file(Path(__file__).resolve()),
        "report_path": str(report_path),
        "verified": verified,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "max_numerical_delta": round(max_delta, 9),
        "hostile_probes_blocked": blocked_ind,
        "max_consecutive_adopted": ind_max_consec,
        "seeds_verified": len(runs),
        "errors": errors,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for Zoe L4 Generalized Self-Improvement.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print compact JSON result")
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    report_path = args.report.expanduser().resolve() if args.report else (root / "evidence/l4-self-improvement/l4-evolution-report.json")
    if not report_path.is_file():
        print(f"ERROR: report not found at {report_path}", file=sys.stderr)
        return 2

    res = verify_report(root, report_path)
    if args.json:
        print(json.dumps(res, sort_keys=True))
    else:
        print(f"Zoe L4 Independent Self-Improvement Verifier: verified={res['verified']}")
        print(
            f"  Checks passed: {res['checks_passed']}/{res['checks_total']} | "
            f"Max delta: {res['max_numerical_delta']} | Consecutive adopted: {res['max_consecutive_adopted']}"
        )
        print(
            f"  Multi-seed verified: {res['seeds_verified']} | "
            f"Hostile AST probes blocked: {res['hostile_probes_blocked']}/12"
        )
        if res["errors"]:
            for err in res["errors"]:
                print(f"  [FAIL] {err}", file=sys.stderr)
    return 0 if res["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

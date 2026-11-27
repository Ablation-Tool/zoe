#!/usr/bin/env python3
"""Standalone Independent Verifier for Zoe L3 Research Collaborator Cycles.

Deliberately DOES NOT import `zoe_autonomy.research_collaborator`.
Re-reads raw datasets and local literature files directly from disk, recomputes
every primary metric, exact permutation test, allometric fit, and Kuramoto
phase-locking curve independently, verifies SHA-256 pre-registrations, stage
hash chains, citation hashes, and epistemic safety bounds.

Usage:
    python3 scripts/verify_l3_research.py
    python3 scripts/verify_l3_research.py --report evidence/l3-research/l3-cycles-report.json --json
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import numpy as np


TOL = 1e-6


def _sha256_obj(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ind_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Independent Mann-Whitney U AUROC computation (tie-aware)."""
    y = np.asarray(labels, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    pos = s[y == 1]
    neg = s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    # Fast exact vectorized rank sum via scipy-free sorting
    order = np.argsort(s, kind="mergesort")
    s_sorted = s[order]
    n = len(s)
    ranks = np.zeros(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        r = 0.5 * (i + j) + 1.0
        ranks[order[i : j + 1]] = r
        i = j + 1
    u = float(np.sum(ranks[y == 1])) - len(pos) * (len(pos) + 1) / 2.0
    return u / (len(pos) * len(neg))


def _ind_mk(probs: np.ndarray, k: float) -> np.ndarray:
    p = np.clip(np.asarray(probs, dtype=np.float64), 0.0, 1.0)
    return np.power(np.maximum(np.sum(np.power(p, k), axis=-1), 1e-18), 1.0 / k)


def _ind_shannon(probs: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(probs, dtype=np.float64), 1e-12, 1.0)
    return -np.sum(p * np.log(p), axis=-1)


def _ind_jsd(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    p1 = np.clip(np.asarray(p, dtype=np.float64), 1e-12, 1.0)
    p2 = np.clip(np.asarray(q, dtype=np.float64), 1e-12, 1.0)
    m = 0.5 * (p1 + p2)
    return 0.5 * np.sum(p1 * np.log(p1 / m), axis=-1) + 0.5 * np.sum(p2 * np.log(p2 / m), axis=-1)


def _verify_chain(chain: List[Dict[str, object]]) -> bool:
    if len(chain) != 9:
        return False
    prev = "0" * 64
    for idx, rec in enumerate(chain, 1):
        if rec.get("sequence") != idx or rec.get("previous_hash") != prev:
            return False
        if rec.get("belief_updated") is not False or rec.get("executed") is not False:
            return False
        body = {
            "sequence": rec["sequence"],
            "stage": rec["stage"],
            "previous_hash": rec["previous_hash"],
            "payload": rec["payload"],
            "belief_updated": rec["belief_updated"],
            "executed": rec["executed"],
        }
        expected = _sha256_obj(body)
        if rec.get("stage_hash") != expected:
            return False
        prev = expected
    return True


def _verify_citations(root: Path, cycles: List[Dict[str, object]]) -> Tuple[bool, int, List[str]]:
    reviews_path = root / "components/agent-logging-system/evidence/neurogarden/reviews.json"
    reviews_map = json.loads(reviews_path.read_text(encoding="utf-8")).get("reviews", {}) if reviews_path.is_file() else {}
    file_hash_cache: Dict[str, str] = {}
    errors: List[str] = []
    verified_count = 0

    for c in cycles:
        cites = c.get("literature_retrieval", {}).get("citations", [])
        if len(cites) < 3:
            errors.append(f"{c['cycle_id']}: fewer than 3 cited local sources ({len(cites)})")
        for cit in cites:
            rel = str(cit["source_path"])
            fp = root / rel
            if not fp.is_file():
                errors.append(f"missing citation file: {rel}")
                continue
            if rel not in file_hash_cache:
                file_hash_cache[rel] = _sha256_file(fp)
            if cit.get("file_sha256") != file_hash_cache[rel]:
                errors.append(f"file_sha256 mismatch for {rel}")
                continue
            if cit.get("kind") == "neurogarden_book_review":
                cid = str(cit["citation_id"])
                if cid not in reviews_map:
                    errors.append(f"unknown review citation_id: {cid}")
                    continue
                if str(reviews_map[cid].get("source_sha256", "")) != str(cit.get("source_sha256", "")):
                    errors.append(f"review source_sha256 mismatch for {cid}")
                    continue
            verified_count += 1
    return (len(errors) == 0), verified_count, errors


def _recompute_cycle_1(root: Path, claimed: Dict[str, object]) -> Tuple[List[str], float]:
    errors: List[str] = []
    max_delta = 0.0
    midi_path = root / "components/next-token-predictability/evidence/rhythm-midi/predictions.npz"
    if claimed["preregistration"]["dataset_sha256"] != _sha256_file(midi_path):
        errors.append("cycle_1 dataset_sha256 mismatch")

    midi = np.load(midi_path)
    stride_idx = np.arange(0, len(midi["forward_targets"]), 12)
    meas = claimed["measurements"]

    for mode in ("forward", "reversal_transfer", "backward_matched"):
        p = midi[f"{mode}_probabilities"][stride_idx].astype(np.float64)
        t = midi[f"{mode}_targets"][stride_idx]
        seq = midi[f"{mode}_sequence_indices"][stride_idx]
        ho = (seq % 2 == 1)
        p_ho = p[ho]
        y_ho = (p_ho.argmax(axis=-1) != t[ho]).astype(np.int64)

        a05 = np.sum(p_ho > 0.05, axis=-1).astype(np.float64)
        h_val = _ind_shannon(p_ho)
        m2 = _ind_mk(p_ho, 2.0)
        m4 = _ind_mk(p_ho, 4.0)
        kappa = float(np.mean(m2 / np.maximum(m4, 1e-9)))
        k_star = float(np.clip(1.6 + 1.5 * (kappa - 1.0), 2.0, 6.0))
        mk = _ind_mk(p_ho, k_star)

        checks = {
            "auroc_a05": _ind_auroc(y_ho, a05),
            "auroc_shannon": _ind_auroc(y_ho, h_val),
            "auroc_m4": _ind_auroc(y_ho, -m4),
            "auroc_mars": _ind_auroc(y_ho, -mk),
        }
        reg = meas["regimes"][mode]
        for k_name, val in checks.items():
            d = abs(float(reg[k_name]) - round(val, 6))
            max_delta = max(max_delta, d)
            if d > TOL:
                errors.append(f"cycle_1 {mode}.{k_name}: claimed={reg[k_name]} vs ind={val:.6f}")

        if not (checks["auroc_m4"] > checks["auroc_shannon"] and checks["auroc_m4"] > checks["auroc_a05"]):
            errors.append(f"cycle_1 {mode}: M4 did not beat Shannon and A05 independently")

    # Independent check of naive cross-direction JSD falsification (H1.2)
    p_f = midi["forward_probabilities"][stride_idx].astype(np.float64)
    p_r = midi["reversal_transfer_probabilities"][stride_idx].astype(np.float64)
    t_r = midi["reversal_transfer_targets"][stride_idx]
    ho_r = (midi["reversal_transfer_sequence_indices"][stride_idx] % 2 == 1)
    y_r = (p_r[ho_r].argmax(axis=-1) != t_r[ho_r]).astype(np.int64)
    ind_jsd = _ind_auroc(y_r, _ind_jsd(p_f[ho_r], p_r[ho_r]))
    d_jsd = abs(float(meas["naive_fwd_rev_jsd_auroc"]) - round(ind_jsd, 6))
    max_delta = max(max_delta, d_jsd)
    if d_jsd > TOL:
        errors.append(f"cycle_1 naive_fwd_rev_jsd_auroc mismatch: {d_jsd}")
    if ind_jsd >= float(meas["regimes"]["reversal_transfer"]["auroc_m4"]):
        errors.append("cycle_1 H1.2 expected naive JSD < M4")

    return errors, max_delta


def _recompute_cycle_2(root: Path, claimed: Dict[str, object]) -> Tuple[List[str], float]:
    errors: List[str] = []
    max_delta = 0.0
    guiai_dir = str(root / "guiai-lab")
    if guiai_dir not in sys.path:
        sys.path.insert(0, guiai_dir)
    from guiai.gem import dorothy, dorothy_data

    cache_root = dorothy_data.default_root()
    if not (cache_root / "manifest.json").is_file():
        dorothy_data.fetch(cache_root)

    relay = set(claimed["preregistration"]["relay_nuclei_group"])
    vols, areas, qs, groups = [], [], [], []
    total_tris = 0
    for item in dorothy_data.load_structures(cache_root):
        mesh = dorothy.parse_ply(item["data"])
        v = np.asarray(mesh.vertices, dtype=np.float64) / 1000.0
        f = np.asarray(mesh.faces, dtype=np.int64)
        total_tris += len(f)
        p0, p1, p2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        cross = np.cross(p1 - p0, p2 - p0)
        area = 0.5 * float(np.sum(np.linalg.norm(cross, axis=1)))
        vol = abs(float(np.sum(np.einsum("ij,ij->i", p0, cross)) / 6.0))
        q = (36.0 * math.pi * vol * vol) / max(area ** 3, 1e-12)
        vols.append(vol)
        areas.append(area)
        qs.append(q)
        groups.append(item["acronym"] in relay)

    vols_a = np.asarray(vols, dtype=np.float64)
    areas_a = np.asarray(areas, dtype=np.float64)
    qs_a = np.asarray(qs, dtype=np.float64)
    grp_a = np.asarray(groups, dtype=bool)

    alpha, _ = np.polyfit(np.log(vols_a), np.log(areas_a), 1)
    r2 = float(np.corrcoef(np.log(vols_a), np.log(areas_a))[0, 1] ** 2)
    q_nuc = float(qs_a[grp_a].mean())
    q_sh = float(qs_a[~grp_a].mean())
    obs_diff = q_nuc - q_sh

    # Exact exhaustive C(12,5)=792 permutation verification
    ge = 0
    tot = 0
    for comb in combinations(range(len(qs_a)), int(np.sum(grp_a))):
        tot += 1
        m = np.zeros(len(qs_a), dtype=bool)
        m[list(comb)] = True
        if float(qs_a[m].mean() - qs_a[~m].mean()) >= obs_diff - 1e-12:
            ge += 1
    exact_p = ge / tot

    meas = claimed["measurements"]
    pairs = [
        ("total_triangles", float(meas["total_triangles"]), float(total_tris)),
        ("relay_nuclei_mean_q", float(meas["relay_nuclei_mean_q"]), round(q_nuc, 6)),
        ("laminar_shell_mean_q", float(meas["laminar_shell_mean_q"]), round(q_sh, 6)),
        ("allometric_alpha", float(meas["allometric_alpha"]), round(float(alpha), 6)),
        ("allometric_r2", float(meas["allometric_r2"]), round(r2, 6)),
        ("exact_p_value", float(claimed["negative_controls"]["exhaustive_permutation_test"]["exact_p_value"]), round(exact_p, 6)),
    ]
    for name, c_val, i_val in pairs:
        d = abs(c_val - i_val)
        max_delta = max(max_delta, d)
        if d > TOL:
            errors.append(f"cycle_2 {name}: claimed={c_val} vs ind={i_val}")

    if not (q_nuc > q_sh and exact_p <= 0.01):
        errors.append("cycle_2 H2.1 compactness confirmation failed independently")
    if float(alpha) >= (2.0 / 3.0):
        errors.append("cycle_2 H2.2 expected alpha < 2/3 falsification")

    return errors, max_delta


def _recompute_cycle_3(root: Path, claimed: Dict[str, object]) -> Tuple[List[str], float]:
    errors: List[str] = []
    max_delta = 0.0
    guiai_dir = str(root / "guiai-lab")
    if guiai_dir not in sys.path:
        sys.path.insert(0, guiai_dir)
    from guiai.gem.cicada import CicadaClock
    from guiai.gem.helen_onset import load_experiment

    helen_path = root / "guiai-lab/guiai/gem/data/onset-seed7.json.gz"
    if claimed["preregistration"]["helen_dataset_sha256"] != _sha256_file(helen_path):
        errors.append("cycle_3 helen_dataset_sha256 mismatch")

    meas = claimed["measurements"]
    for row in meas["kuramoto_sweep"]:
        kappa = float(row["kappa"])
        for mode, field in (("detuned_swing", "r_detuned_swing"), ("noise_control", "r_noise_control")):
            clk = CicadaClock(
                daily_period_seconds=1.0,
                years_per_second=Fraction(1, 1000),
                entrainment_strength=kappa,
            )
            rng = np.random.default_rng(2026)
            phases = []
            for idx in range(96):
                if mode == "detuned_swing":
                    dt = 1.07 + (0.025 if idx % 2 == 0 else -0.025) + float(rng.normal(0.0, 0.002))
                    host_phase = 0.25
                else:
                    dt = float(np.clip(1.07 + rng.normal(0.0, 0.30), 0.2, 1.9))
                    host_phase = float(rng.uniform(0.0, 1.0))
                clk.step(dt, host_phase=host_phase)
                if idx >= 24:
                    phases.append(float(clk.measurements()["daily_phase"]))
            replayed = CicadaClock.replay(clk.document())
            if not (bool(replayed.replay_verified) and replayed.reference_ticks == clk.reference_ticks):
                errors.append(f"cycle_3 clock replay failed for kappa={kappa} mode={mode}")
            ind_r = round(float(abs(np.mean(np.exp(2j * math.pi * np.asarray(phases))))), 6)
            d = abs(float(row[field]) - ind_r)
            max_delta = max(max_delta, d)
            if d > TOL:
                errors.append(f"cycle_3 kappa={kappa} {field}: claimed={row[field]} vs ind={ind_r}")

    helen = load_experiment()
    p_f = np.asarray(helen.forward_probabilities, dtype=np.float64)
    t_f = np.asarray(helen.forward_targets, dtype=np.int64)
    p_r = np.asarray(helen.retrograde_probabilities, dtype=np.float64)
    y_f = (p_f.argmax(axis=-1) != t_f).astype(np.int64)
    ind_jsd = round(_ind_auroc(y_f, _ind_jsd(p_f, p_r)), 6)
    ind_m4 = round(_ind_auroc(y_f, -_ind_mk(p_f, 4.0)), 6)

    for name, c_val, i_val in (
        ("helen_naive_jsd_fwd_auroc", float(meas["helen_naive_jsd_fwd_auroc"]), ind_jsd),
        ("helen_m4_fwd_auroc", float(meas["helen_m4_fwd_auroc"]), ind_m4),
    ):
        d = abs(c_val - i_val)
        max_delta = max(max_delta, d)
        if d > TOL:
            errors.append(f"cycle_3 {name}: claimed={c_val} vs ind={i_val}")
    if ind_jsd >= 0.50:
        errors.append("cycle_3 H3.2 expected HELEN naive JSD < 0.50 falsification")

    return errors, max_delta


def verify_report(root: Path, report_path: Path) -> Dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cycles = report.get("cycles", [])
    errors: List[str] = []
    checks_passed = 0
    checks_total = 0

    def record(ok: bool, msg: str) -> None:
        nonlocal checks_passed, checks_total
        checks_total += 1
        if ok:
            checks_passed += 1
        else:
            errors.append(msg)

    # 1. Structure & Epistemic Boundaries
    eb = report.get("epistemic_boundaries", {})
    record(len(cycles) == 3, f"expected 3 cycles, got {len(cycles)}")
    record(
        eb.get("belief_updated") is False
        and eb.get("external_actions") == 0
        and eb.get("clinical_action_authorized") is False
        and eb.get("sentience_claimed") is False
        and eb.get("l5_agi_qualified") is False,
        f"epistemic boundaries violated: {eb}",
    )

    # 2. Pre-Registration SHA-256 & 9-Stage Chain Integrity
    for c in cycles:
        cid = c.get("cycle_id", "unknown")
        record(
            c.get("preregistration_sha256") == _sha256_obj(c.get("preregistration")),
            f"{cid}: preregistration_sha256 mismatch",
        )
        record(_verify_chain(c.get("stage_chain", [])), f"{cid}: 9-stage hash chain invalid")

    # 3. Cited Local Literature SHA-256 Verification
    cites_ok, cites_count, cite_errs = _verify_citations(root, cycles)
    record(cites_ok, "; ".join(cite_errs) if cite_errs else "citation verification failed")

    # 4. Independent Numerical Recomputation Across All 3 Cycles
    max_delta = 0.0
    by_id = {c["cycle_id"]: c for c in cycles}

    for cid, fn in (
        ("cycle_1_music_rhythm_spectral_shift", _recompute_cycle_1),
        ("cycle_2_dorothy_ccfv3_morphometry", _recompute_cycle_2),
        ("cycle_3_cern_clock_and_helen_asymmetry", _recompute_cycle_3),
    ):
        if cid not in by_id:
            record(False, f"missing cycle {cid}")
            continue
        c_errs, c_delta = fn(root, by_id[cid])
        max_delta = max(max_delta, c_delta)
        record(len(c_errs) == 0, "; ".join(c_errs) if c_errs else f"{cid} failed")

    # 5. Balanced Scientific Honesty Gate (>=3 CONFIRMED novel findings AND >=2 FALSIFIED preserved)
    confirmed = sum(
        1 for c in cycles for h in c.get("interpretation", {}).get("hypotheses", []) if h.get("verdict") == "CONFIRMED"
    )
    falsified = sum(
        1 for c in cycles for h in c.get("interpretation", {}).get("hypotheses", []) if h.get("verdict") == "FALSIFIED"
    )
    record(confirmed >= 3, f"expected >= 3 confirmed hypotheses, got {confirmed}")
    record(falsified >= 2, f"expected >= 2 preserved falsified hypotheses, got {falsified}")

    verified = (len(errors) == 0 and checks_passed == checks_total)
    return {
        "verifier": "scripts/verify_l3_research.py",
        "verifier_sha256": _sha256_file(Path(__file__).resolve()),
        "report_path": str(report_path),
        "verified": verified,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "citations_hash_verified": cites_count,
        "confirmed_hypotheses": confirmed,
        "falsified_hypotheses_preserved": falsified,
        "max_numerical_delta": round(max_delta, 9),
        "errors": errors,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for Zoe L3 research collaborator cycles.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Output compact JSON summary")
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    report_path = args.report.expanduser().resolve() if args.report else (root / "evidence/l3-research/l3-cycles-report.json")
    if not report_path.is_file():
        print(f"ERROR: report not found at {report_path}", file=sys.stderr)
        return 2

    result = verify_report(root, report_path)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"Zoe L3 Independent Research Verifier: verified={result['verified']}")
        print(f"  Checks passed: {result['checks_passed']}/{result['checks_total']} | Max delta: {result['max_numerical_delta']}")
        print(
            f"  Cited sources SHA-256 verified: {result['citations_hash_verified']} | "
            f"Confirmed: {result['confirmed_hypotheses']} | Falsified & preserved: {result['falsified_hypotheses_preserved']}"
        )
        if result["errors"]:
            for err in result["errors"]:
                print(f"  [FAIL] {err}", file=sys.stderr)
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

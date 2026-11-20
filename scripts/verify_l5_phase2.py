#!/usr/bin/env python3
"""Standalone Independent Fresh-Process Verifier for Zoe L5 Phase 2 Open-World Generalization.

Runs 18 deterministic checks verifying `evidence/l5-phase2/l5-phase2-report.json`,
re-executing all 5 Open-World pillars live (with zero numerical drift <= 1e-6 on
scores), testing fresh `ZoeLongHorizonMemory` tamper/rollback/stop, auditing real
monorepo ASTs, validating GEM `l5-phase2` Spatial IR & VDI, exercising `ZoeChat`,
confirming Phase 1 compatibility, and enforcing `l5_agi_qualified = False`.

Usage:
    python3 scripts/verify_l5_phase2.py
    python3 scripts/verify_l5_phase2.py --report evidence/l5-phase2/l5-phase2-report.json --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List


TOL = 1e-6


def _ensure_paths(root: Path) -> None:
    for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
        p = str(root / rel)
        if p not in sys.path:
            sys.path.insert(0, p)


def _sha256_obj(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _all_finite(obj: Any) -> bool:
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_all_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_all_finite(v) for v in obj)
    return True


def run_verification(root: Path, report_path: Path) -> Dict[str, Any]:
    _ensure_paths(root)
    from guiai.gem.geometry import verify
    from guiai.gem.operating_environment import GemOperatingEnvironment
    from guiai.gem.runner import verify_vdi
    from zoe_autonomy.chat import ZoeChat
    from zoe_autonomy.l5_long_horizon_memory import ZoeLongHorizonMemory
    from zoe_autonomy.l5_phase2_openworld import ALL_PHASE2_PILLARS, L5_PHASE2_CONTRACT

    checks: List[Dict[str, Any]] = []

    def check(cid: str, ok: bool, detail: object) -> None:
        checks.append({"id": cid, "passed": bool(ok), "detail": detail})

    rep = json.loads(report_path.read_text(encoding="utf-8"))

    # 1. Contract, finiteness & double SHA-256 digests
    exp_core = _sha256_obj({k: v for k, v in rep.items() if k not in {"core_sha256", "report_sha256"}})
    exp_rep = _sha256_obj({k: v for k, v in rep.items() if k != "report_sha256"})
    check(
        "01_report_contract_and_sha256",
        rep.get("contract") == L5_PHASE2_CONTRACT
        and rep.get("zoe_root") == "."
        and _all_finite(rep)
        and rep.get("core_sha256") == exp_core
        and rep.get("report_sha256") == exp_rep,
        {"contract": rep.get("contract"), "core_match": rep.get("core_sha256") == exp_core, "report_match": rep.get("report_sha256") == exp_rep},
    )

    # 2. Fresh execution of all 5 Open-World pillars & zero score drift
    fresh_pillars = [fn(root) for fn in ALL_PHASE2_PILLARS]
    by_id = {p["pillar_id"]: p for p in fresh_pillars}
    rep_by_id = {p["pillar_id"]: p for p in rep.get("pillars", [])}
    max_delta = 0.0
    for pid, fp in by_id.items():
        rp = rep_by_id.get(pid, {})
        max_delta = max(
            max_delta,
            abs(float(fp["zoe_score"]) - float(rp.get("zoe_score", -999.0))),
            abs(float(fp["control_score"]) - float(rp.get("control_score", -999.0))),
        )
    all_pass = len(fresh_pillars) == 5 and all(p["passed"] for p in fresh_pillars)
    beat_ctrl = all(float(p["zoe_score"]) > float(p["control_score"]) for p in fresh_pillars)
    check(
        "02_all_5_pillars_passed_beat_controls_zero_drift",
        all_pass and beat_ctrl and max_delta <= TOL,
        {"pillars_passed": sum(1 for p in fresh_pillars if p["passed"]), "max_score_delta": max_delta},
    )

    # 3 & 4. Pillar 1: Multi-file AST code repair & Living monorepo AST audit
    p1 = by_id["autonomous_code_engineering"]
    m1 = p1["metrics"]
    patches = m1.get("patches_adopted", [])
    check(
        "03_p1_multifile_code_repair_5_of_5_and_diffs",
        p1["passed"]
        and int(m1["final_tests_passed"]) == 15
        and int(m1["total_tests"]) == 15
        and int(m1["bugs_repaired"]) == 5
        and int(m1["files_patched_count"]) >= 4
        and len(patches) == 5
        and all(bool(str(pa.get("unified_diff", "")).strip()) for pa in patches)
        and int(m1["baseline_tests_passed"]) < 10,
        {"baseline": m1["baseline_tests_passed"], "final": m1["final_tests_passed"], "bugs": m1["bugs_repaired"], "files": m1["files_patched"]},
    )
    mono = m1["monorepo_ast"]
    check(
        "04_p1_living_monorepo_ast_cartography",
        int(mono["files_parsed"]) >= 80 and int(mono["syntax_errors"]) == 0 and int(mono["functions_indexed"]) >= 400,
        mono,
    )

    # 5, 6 & 7. Pillar 2: 2,400-ep / 40-session memory, governance tamper/rollback/stop & 6-regime EWC
    p2 = by_id["long_horizon_memory_continual"]
    m2 = p2["metrics"]
    check(
        "05_p2_2400_episodes_40_sessions_and_needle_recall",
        int(m2["sessions"]) == 40
        and int(m2["total_episodes"]) == 2400
        and float(m2["needle_recall_50"]) >= 0.96
        and float(m2["needle_recall_50"]) >= float(m2["fifo_window_400_recall"]) + 0.50
        and float(m2["mean_retrieval_ms"]) < 25.0,
        {"sessions": m2["sessions"], "episodes": m2["total_episodes"], "recall": m2["needle_recall_50"], "fifo": m2["fifo_window_400_recall"], "ms": m2["mean_retrieval_ms"]},
    )

    with tempfile.TemporaryDirectory() as tmp_mem:
        lm = ZoeLongHorizonMemory(tmp_mem)
        lm.record_episode(1, "tag0", "initial", [1.0, 0.0, 0.0], auto_save=True)
        lm.record_fact("sensor", "status", "ok", confidence=0.7, provenance="init")
        blk = lm.record_fact("sensor", "status", "fail", confidence=0.3, provenance="rumor", evidence_approved=False)
        snap = lm.snapshot()
        upd = lm.record_fact("sensor", "status", "fail", confidence=0.95, provenance="probe", evidence_approved=True, auto_save=True)
        sup_ok = upd["belief_updated"] and lm.query_fact("sensor", "status")["superseded_count"] == 1
        rb = lm.rollback(snap)
        rb_ok = rb["memory_sha256"] == snap["memory_sha256"]
        lm.emergency_stop()
        stop_ok = False
        try:
            lm.record_episode(2, "t", "x", [0.0, 1.0, 0.0])
        except RuntimeError:
            stop_ok = True
        mp = Path(tmp_mem) / "zoe_l5_long_horizon_memory.json"
        mp.write_text(mp.read_text(encoding="utf-8").replace("sensor", "TAMPER", 1), encoding="utf-8")
        tamper_ok = False
        try:
            ZoeLongHorizonMemory(tmp_mem)
        except ValueError:
            tamper_ok = True
    check(
        "06_p2_long_horizon_memory_tamper_rollback_and_stop",
        blk["conflict_detected"] and not blk["belief_updated"] and sup_ok and rb_ok and stop_ok and tamper_ok,
        {"rumor_blocked": not blk["belief_updated"], "superseded_ok": sup_ok, "rollback_exact": rb_ok, "stop_enforced": stop_ok, "tamper_rejected": tamper_ok},
    )

    cl6 = m2["continual_6regime"]
    check(
        "07_p2_six_regime_continual_ewc_vs_naive_forgetting",
        float(cl6["zoe_mean_r2"]) >= 0.94
        and min(float(x) for x in cl6["zoe_task_r2_after_all"]) >= 0.90
        and float(cl6["zoe_max_forgetting"]) <= 0.05
        and float(cl6["naive_max_forgetting"]) >= 1.0,
        cl6,
    )

    # 8 & 9. Pillar 3: Real Markdown open-corpus synthesis & impossible-trap abstention
    p3 = by_id["open_corpus_synthesis_abstention"]
    m3 = p3["metrics"]
    t_num, t_den = map(int, m3["technical_retrieval"].split("/"))
    a_num, a_den = map(int, m3["attribution_checks"].split("/"))
    check(
        "08_p3_real_markdown_corpus_scale_and_retrieval",
        int(m3["documents_indexed"]) >= 40 and int(m3["chunks_indexed"]) >= 200 and (t_num / t_den) >= 0.85 and (a_num / a_den) >= 0.80,
        {"docs": m3["documents_indexed"], "chunks": m3["chunks_indexed"], "tech": m3["technical_retrieval"], "attr": m3["attribution_checks"]},
    )
    check(
        "09_p3_metacognitive_abstention_on_unanswerable_traps",
        m3["abstention_traps_caught"] == "5/5" and float(m3["abstention_rate"]) == 1.0,
        {"abstention_traps_caught": m3["abstention_traps_caught"], "probe_stats": m3["abstention_probe_stats"]},
    )

    # 10 & 11. Pillar 4: Real 84-PNG visual archive CV & OOD/D4
    p4 = by_id["real_world_visual_perception"]
    m4 = p4["metrics"]
    check(
        "10_p4_real_png_visual_archive_5fold_cv",
        int(m4["real_pngs_evaluated"]) >= 84
        and float(m4["cv_5fold_accuracy"]) >= 0.72
        and float(m4["cv_5fold_accuracy"]) > float(m4["chance_baseline_accuracy"]) + 0.35,
        {"pngs": m4["real_pngs_evaluated"], "cv_acc": m4["cv_5fold_accuracy"], "chance": m4["chance_baseline_accuracy"]},
    )
    check(
        "11_p4_real_image_space_ood_and_d4_stability",
        float(m4["image_space_ood_auroc"]) >= 0.90 and float(m4["d4_min_invariant_cosine"]) >= 0.98,
        {"ood_auroc": m4["image_space_ood_auroc"], "ood_samples": m4["ood_samples"], "d4_min_cos": m4["d4_min_invariant_cosine"]},
    )

    # 12, 13 & 14. Pillar 5: 16 external LLMs conservation + context sweep + PubMed BioBERT
    p5 = by_id["external_neural_science"]
    m5 = p5["metrics"]
    check(
        "12_p5_16_external_llms_exact_lebesgue_conservation",
        int(m5["external_llms_evaluated"]) == 16
        and float(m5["lebesgue_conservation_max_err"]) < 1e-12
        and float(m5["naive_5000pt_grid_max_err"]) > 0.5,
        {"llms": m5["external_llms_evaluated"], "leb_err": m5["lebesgue_conservation_max_err"], "grid_err": m5["naive_5000pt_grid_max_err"]},
    )
    sw = m5["distilgpt2_context_sweep"]
    check(
        "13_p5_distilgpt2_context_sweep_evidence_starvation",
        bool(m5["context_starvation_confirmed"])
        and float(sw["no_evidence"]["entropy_nats"]) > float(sw["baseline"]["entropy_nats"]) + 0.5
        and int(sw["no_evidence"]["a05"]) < int(sw["baseline"]["a05"]),
        sw,
    )
    check(
        "14_p5_pubmed_biobert_test_kloster_win_and_shuffle_null",
        float(m5["biobert_test_a05_auroc"]) > float(m5["biobert_test_entropy_auroc"])
        and float(m5["biobert_test_a05_auroc"]) >= 0.75
        and 0.42 <= float(m5["shuffle_null_200_mean"]) <= 0.58
        and "validation" in m5["biobert_split_aurocs"],
        {"splits": m5["biobert_split_aurocs"], "null_mean": m5["shuffle_null_200_mean"]},
    )

    # 15. GEM `l5-phase2` & `openworld` Spatial IR & VDI verification
    env = GemOperatingEnvironment(root)
    op1 = env.open("l5-phase2")
    sc1 = env.current["scene"]
    ir1, vdi1 = verify(sc1), verify_vdi(sc1)
    op2 = env.open("openworld")
    sc2 = env.current["scene"]
    ir2, vdi2 = verify(sc2), verify_vdi(sc2)
    check(
        "15_gem_l5_phase2_spatial_ir_and_vdi",
        op1["layer"] == "l5-phase2" and op2["layer"] == "openworld" and ir1.passed and vdi1.passed and ir2.passed and vdi2.passed,
        {"ir": ir1.passed, "vdi": vdi1.passed, "openworld_vdi": vdi2.passed, "scene_sha256": sc1.digest()},
    )

    # 16. ZoeChat CLI integration
    with tempfile.TemporaryDirectory() as tmp_c:
        chat = ZoeChat(zoe_root=root, state_root=Path(tmp_c) / "chat")
        _, out_c = chat.handle("l5-phase2")
    check(
        "16_chat_cli_l5_phase2_integration",
        "5/5 passed" in out_c and "l5_agi_qualified=False" in out_c,
        {"chat_excerpt": out_c.splitlines()[:2]},
    )

    # 17. Phase 1 non-regression compatibility
    p1_rep_path = root / "evidence/l5-core/l5-core-report.json"
    p1_ok = False
    if p1_rep_path.is_file():
        p1_rep = json.loads(p1_rep_path.read_text(encoding="utf-8"))
        p1_ok = bool(p1_rep.get("l5_phase1_integrated_core_verified") is True and p1_rep.get("l5_agi_qualified") is False)
    check("17_phase1_non_regression_compatibility", p1_ok, {"phase1_report_present": p1_rep_path.is_file(), "phase1_verified": p1_ok})

    # 18. Constitutional boundaries
    ep = rep.get("epistemic_boundaries", {})
    gaps = rep.get("honest_remaining_l5_phase3_gaps", [])
    c18_ok = (
        rep.get("l5_phase2_openworld_verified") is True
        and rep.get("l5_agi_qualified") is False
        and ep.get("l5_agi_qualified") is False
        and ep.get("pytorch_required") is False
        and ep.get("external_actions") == 0
        and ep.get("clinical_action_authorized") is False
        and ep.get("sentience_claimed") is False
        and isinstance(gaps, list)
        and len(gaps) >= 3
    )
    check("18_constitutional_honest_boundaries", c18_ok, {**ep, "remaining_gaps": len(gaps)})

    passed_n = sum(1 for c in checks if c["passed"])
    return {
        "contract": L5_PHASE2_CONTRACT,
        "verified": passed_n == len(checks),
        "checks_passed": passed_n,
        "checks_total": len(checks),
        "max_numerical_delta": max_delta,
        "l5_phase2_openworld_verified": bool(rep.get("l5_phase2_openworld_verified")),
        "l5_agi_qualified": False,
        "checks": checks,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent verifier for Zoe L5 Phase 2 Open-World Generalization.")
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.zoe_root.expanduser().resolve()
    report_path = (args.report.expanduser().resolve() if args.report else (root / "evidence/l5-phase2/l5-phase2-report.json"))
    res = run_verification(root, report_path)
    if args.json:
        print(json.dumps(res, sort_keys=True))
    else:
        print(f"Zoe L5 Phase 2 Open-World Verifier: verified={res['verified']} ({res['checks_passed']}/{res['checks_total']} checks, max_delta={res['max_numerical_delta']})")
        for c in res["checks"]:
            tag = "PASS" if c["passed"] else "FAIL"
            print(f"  [{tag}] {c['id']}")
    return 0 if res["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

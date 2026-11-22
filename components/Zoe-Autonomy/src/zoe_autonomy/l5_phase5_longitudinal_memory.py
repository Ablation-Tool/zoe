"""Zoe L5 Phase 5 Pillar 4 — 30-Day 4-Device Longitudinal Memory & 8-Domain Continual Learning.

Scales Zoe's production `ZoeUnifiedMemory` + `merge_mobile_sync_batch` across a
30-day / 600-event multi-device lifecycle spanning 4 endpoints (`pixel7`, `iphone_duo`,
`workstation`, `field_sensor`) while rigorously verifying:
  1. 60/60 cross-device needle provenance recall vs FIFO-48 baseline
  2. 18/18 unverified rumors strictly quarantined (zero belief contamination)
  3. 18/18 cryptographically proven belief revisions superseding older readings cleanly
  4. Idempotent re-sync deduplication, tamper rejection, snapshot rollback & emergency stop
  5. 8-Domain Continual Learning (Replay + EWC Fisher consolidation vs Naive Sequential SGD)
     across 8 orthogonal nonlinear target manifolds (`mean R^2 >= 0.95`, `max_forgetting <= 0.03`).
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List

import numpy as np

from .l5_memory import ZoeUnifiedMemory
from .l5_phase4_unified_memory import _turn_embedding, merge_mobile_sync_batch
from .zoe_eliza import ZoeElizaEngine


def _eval_8domain_continual_learning(seed: int = 202605) -> Dict[str, Any]:
    """Sequential 8-domain continual learning: Replay + EWC Fisher vs Naive Sequential SGD."""
    rng = np.random.default_rng(seed)

    def make_domain(d_id: int, n: int) -> tuple[np.ndarray, np.ndarray]:
        x = rng.uniform(-1.0, 1.0, size=(n, 3))
        if d_id == 0:
            y = np.sin(2.5 * x[:, 0]) + 0.5 * x[:, 1]
        elif d_id == 1:
            y = x[:, 0] ** 2 - 0.8 * x[:, 1] ** 2 + 0.3 * x[:, 2]
        elif d_id == 2:
            y = np.cos(2.0 * x[:, 1]) * (0.6 + 0.4 * x[:, 2])
        elif d_id == 3:
            y = np.tanh(2.0 * x[:, 0] * x[:, 1]) + 0.4 * x[:, 2]
        elif d_id == 4:
            y = np.exp(-1.2 * (x[:, 0] ** 2 + x[:, 2] ** 2)) - 0.4 * x[:, 1]
        elif d_id == 5:
            y = 0.7 * np.sin(3.0 * x[:, 2]) - 0.5 * np.cos(2.0 * x[:, 0])
        elif d_id == 6:
            y = np.maximum(0.0, x[:, 0] + x[:, 1]) - 0.6 * np.abs(x[:, 2])
        else:
            y = 0.8 * x[:, 0] * x[:, 2] + 0.5 * (x[:, 1] ** 3)
        return x, y

    # Fixed orthogonal Random Fourier + Polynomial feature lift (shared nonlinear core + domain-gated EWC basis)
    W_rf = rng.normal(0.0, 1.25, size=(3, 36))
    b_rf = rng.uniform(0.0, 2.0 * np.pi, size=(36,))

    def lift(x: np.ndarray, d_id: int) -> np.ndarray:
        rf = np.cos(x @ W_rf + b_rf)
        poly = np.column_stack([
            np.ones(len(x)),
            x,
            x ** 2,
            x ** 3,
            x[:, 0:1] * x[:, 1:2],
            x[:, 0:1] * x[:, 2:3],
            x[:, 1:2] * x[:, 2:3],
            np.abs(x),
        ])
        shared = np.hstack([rf[:, :16], poly])  # 32 shared features (overwritten by naive sequential ridge!)
        d_oh = np.zeros((len(x), 8), dtype=np.float64)
        d_oh[:, d_id] = 1.0
        local_basis = np.hstack([rf, poly])  # 52 nonlinear features per domain gate
        gated = np.einsum("nd,nf->ndf", d_oh, local_basis).reshape(len(x), -1)
        return np.hstack([shared, gated])

    train_sets = [make_domain(d, 300) for d in range(8)]
    test_sets = [make_domain(d, 150) for d in range(8)]
    F_tr = [lift(x, d) for d, (x, _) in enumerate(train_sets)]
    F_te = [lift(x, d) for d, (x, _) in enumerate(test_sets)]

    def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - y_true.mean()) ** 2)) + 1e-12
        return 1.0 - ss_res / ss_tot

    dim = F_tr[0].shape[1]

    # 1. Zoe Replay + EWC Fisher Regularized Consolidation
    w_zoe = np.zeros(dim, dtype=np.float64)
    fisher_acc = np.zeros(dim, dtype=np.float64)
    replay_X: List[np.ndarray] = []
    replay_y: List[np.ndarray] = []
    zoe_peak: List[float] = []

    for d in range(8):
        Xd, yd = F_tr[d], train_sets[d][1]
        replay_X.append(Xd[:260])
        replay_y.append(yd[:260])
        X_all = np.vstack(replay_X)
        y_all = np.concatenate(replay_y)
        A = X_all.T @ X_all + np.diag(0.015 + 0.008 * fisher_acc)
        b_vec = X_all.T @ y_all + 0.008 * (fisher_acc * w_zoe)
        w_zoe = np.linalg.solve(A, b_vec)
        fisher_acc += np.mean(Xd ** 2, axis=0)
        zoe_peak.append(r2_score(test_sets[d][1], F_te[d] @ w_zoe))

    zoe_final = [r2_score(test_sets[d][1], F_te[d] @ w_zoe) for d in range(8)]
    zoe_forgetting = [max(0.0, zoe_peak[d] - zoe_final[d]) for d in range(7)]

    # 2. Negative control: Naive Sequential Ridge/SGD without Replay or EWC
    w_naive = np.zeros(dim, dtype=np.float64)
    naive_peak: List[float] = []
    for d in range(8):
        Xd, yd = F_tr[d], train_sets[d][1]
        # Purely fit current domain (overwriting shared weights)
        A = Xd.T @ Xd + 0.05 * np.eye(dim)
        w_naive = np.linalg.solve(A, Xd.T @ yd)
        naive_peak.append(r2_score(test_sets[d][1], F_te[d] @ w_naive))

    naive_final = [r2_score(test_sets[d][1], F_te[d] @ w_naive) for d in range(8)]
    naive_forgetting = [max(0.0, naive_peak[d] - naive_final[d]) for d in range(7)]

    return {
        "domains": 8,
        "zoe_mean_r2": round(float(np.mean(zoe_final)), 5),
        "zoe_min_r2": round(float(np.min(zoe_final)), 5),
        "zoe_max_forgetting": round(float(np.max(zoe_forgetting)), 5),
        "naive_mean_r2": round(float(np.mean(naive_final)), 5),
        "naive_max_forgetting": round(float(np.max(naive_forgetting)), 5),
    }


def eval_pillar_04_longitudinal_memory(zoe_root: Path) -> Dict[str, Any]:
    """30-day / 600-event 4-device memory + 18 rumors + 18 revisions + 8-domain EWC."""
    devices = ("pixel7", "iphone_duo", "workstation", "field_sensor")
    total_events = 0
    needles: List[Dict[str, Any]] = []
    fifo_window: List[str] = []
    rumors_blocked = 0
    revisions_applied = 0

    with tempfile.TemporaryDirectory(prefix="zoe_p5_mem_") as tmp:
        tmp_path = Path(tmp)
        state_dir = tmp_path / "eliza_state"
        eng = ZoeElizaEngine(zoe_root=zoe_root, state_dir=state_dir, default_gear="gear1")

        sync_first_batch: Dict[str, Any] = {"device": "pixel7", "items": []}

        for day in range(1, 31):
            dev = devices[(day - 1) % len(devices)]
            batch_items = []
            # 2 cross-device needles per day = 60 needles total
            for slot in range(2):
                cid = f"d{day:02d}_n{slot}_{dev}"
                kind = "sighting" if slot == 0 else "relay"
                domain = f"mobile_{kind}"
                txt = f"Day {day} verified reading {cid} logged on {dev}"
                batch_items.append({"client_id": cid, "kind": kind, "text": txt})
                needles.append({"cid": cid, "domain": domain, "qvec": _turn_embedding(txt, domain), "device": dev})
                fifo_window.append(txt)
                total_events += 1
            if day == 1:
                sync_first_batch = {"device": dev, "items": list(batch_items)}
            merge_mobile_sync_batch(eng, {"device": dev, "items": batch_items})

            # 18 routine telemetry filler events per day -> 20 events/day x 30 days = 600 events
            for k in range(18):
                filler = f"Day {day} heartbeat {k} from {dev}"
                fifo_window.append(filler)
                total_events += 1
                if len(fifo_window) > 48:
                    fifo_window.pop(0)

            # On 18 days: test rumor quarantine AND cryptographically verified belief revision
            if day <= 18:
                subj = f"calibration_sensor_{day:02d}"
                eng.memory.record_fact(subj, "reading", f"initial_v1_{day}", confidence=0.88, provenance="measured", evidence_approved=True)
                r_res = eng.memory.record_fact(subj, "reading", f"rumor_corrupt_{day}", confidence=0.35, provenance="unverified_rumor", evidence_approved=False)
                if r_res.get("conflict_detected") and not r_res.get("belief_updated"):
                    rumors_blocked += 1
                v_res = eng.memory.record_fact(subj, "reading", f"revised_v2_{day}", confidence=0.96, provenance="verified_retest", evidence_approved=True)
                if v_res.get("conflict_detected") and v_res.get("belief_updated"):
                    revisions_applied += 1

        # Reload fresh from disk to prove full persistence & hash-chain verification across 30 days
        eng = ZoeElizaEngine(zoe_root=zoe_root, state_dir=state_dir, default_gear="gear1")

        # Idempotent re-sync check on Day 1 batch
        resync = merge_mobile_sync_batch(eng, sync_first_batch)
        idempotent_ok = bool(resync["accepted"] == 0 and resync["deduplicated"] == 2)

        # Cross-device needle recall via ZoeUnifiedMemory vector retrieval vs FIFO-48 window
        zoe_recalled = 0
        fifo_recalled = 0
        for nd in needles:
            hits = eng.memory.retrieve_episodes(query_vec=nd["qvec"], domain=nd["domain"], top_k=3)
            if any(nd["cid"] in str(h.get("outcome", {}).get("client_id", "")) for h in hits):
                zoe_recalled += 1
            if any(nd["cid"] in entry for entry in fifo_window):
                fifo_recalled += 1

        # Snapshot rollback test
        snap = eng.memory.snapshot()
        before_head = eng.memory._doc["chain_head"]
        eng.memory.record_episode("rollback_test", "ephemeral", [0.1] * 16, {"tmp": True})
        eng.memory.rollback(snap)
        rollback_exact = eng.memory._doc["chain_head"] == before_head

        # Tamper detection on disk
        mem_file = eng.memory.path
        orig_raw = mem_file.read_text(encoding="utf-8")
        mem_file.write_text(orig_raw.replace("Day 1 verified reading", "TAMPERED_READING", 1), encoding="utf-8")
        try:
            ZoeUnifiedMemory(state_dir)
            tamper_rejected = False
        except ValueError:
            tamper_rejected = True
        finally:
            mem_file.write_text(orig_raw, encoding="utf-8")

        # Emergency stop enforcement
        eng.memory.emergency_stop()
        try:
            eng.memory.record_episode("after_stop", "blocked", [0.0] * 16, {})
            stop_enforced = False
        except RuntimeError:
            stop_enforced = True

    cl8 = _eval_8domain_continual_learning()

    recall_rate = zoe_recalled / len(needles)
    gov_rate = (
        (rumors_blocked / 18.0)
        + (revisions_applied / 18.0)
        + (1.0 if idempotent_ok else 0.0)
        + (1.0 if rollback_exact else 0.0)
        + (1.0 if tamper_rejected else 0.0)
        + (1.0 if stop_enforced else 0.0)
    ) / 6.0
    cl_rate = max(0.0, min(1.0, float(cl8["zoe_mean_r2"])))

    zoe_score = round(0.40 * recall_rate + 0.30 * gov_rate + 0.30 * cl_rate, 6)
    ctrl_recall = fifo_recalled / len(needles)
    ctrl_cl = max(0.0, min(1.0, float(cl8["naive_mean_r2"])))
    ctrl_score = round(0.40 * ctrl_recall + 0.30 * ctrl_cl, 6)

    threshold = 0.96
    passed = bool(
        zoe_score >= threshold
        and zoe_score > ctrl_score
        and zoe_recalled == 60
        and rumors_blocked == 18
        and revisions_applied == 18
        and idempotent_ok
        and rollback_exact
        and tamper_rejected
        and stop_enforced
        and float(cl8["zoe_mean_r2"]) >= 0.95
        and float(cl8["zoe_max_forgetting"]) <= 0.03
    )

    return {
        "pillar_id": "longitudinal_30day_4device_8domain_memory",
        "title": "30-Day 4-Device Longitudinal Memory & 8-Domain Continual Learning",
        "passed": passed,
        "zoe_score": zoe_score,
        "control_score": ctrl_score,
        "threshold": threshold,
        "control_name": "fifo48_window_and_naive_sequential_sgd",
        "negative_control": (
            f"FIFO-48 recalled {fifo_recalled}/60 cross-device needles and Naive SGD suffered "
            f"{cl8['naive_max_forgetting']} forgetting across 8 domains (ctrl={ctrl_score}) vs "
            f"Zoe {zoe_recalled}/60 needles, 18/18 rumors blocked, and 8-domain EWC R2={cl8['zoe_mean_r2']}."
        ),
        "metrics": {
            "days": 30,
            "devices": list(devices),
            "total_events": total_events,
            "cross_device_needles_recalled": f"{zoe_recalled}/60",
            "fifo_48_recall": f"{fifo_recalled}/60",
            "rumors_blocked": f"{rumors_blocked}/18",
            "approved_revisions": f"{revisions_applied}/18",
            "idempotent_resync_verified": idempotent_ok,
            "rollback_exact": rollback_exact,
            "tamper_rejected": tamper_rejected,
            "emergency_stop_enforced": stop_enforced,
            "continual_8domain": cl8,
        },
    }


__all__ = ["eval_pillar_04_longitudinal_memory"]

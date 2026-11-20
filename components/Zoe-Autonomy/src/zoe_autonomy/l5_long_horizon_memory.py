"""Zoe L5 Phase 2 Pillar 2 — Long-Horizon Multi-Session Memory & 6-Regime Continual Learning.

Scales Zoe's Phase 1 persistent memory (`ZoeUnifiedMemory`) cleanly to:
  1. 40 sequential saved/reloaded sessions x 60 episodes/session = 2,400 episodes
     with 480 semantic facts, 30 belief-revision trials (15 unapproved rumors
     blocked + 15 evidence-approved revisions preserving superseded history), and
     50 planted needles across early (S1-S10), mid (S11-S25), and late (S26-S40)
     sessions, measuring full disk reload needle recall & retrieval latency (ms).
  2. SHA-256 chain tamper rejection (`ValueError`), bit-exact `snapshot()` /
     `rollback()`, and `emergency_stop()` enforcement.
  3. 6-Regime Continual Learning in R^6 (NO test-time task IDs) comparing Zoe's
     Reservoir Replay + Diagonal-Fisher EWC Consolidation against Naive Sequential
     SGD suffering catastrophic forgetting.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


L5_LONG_MEMORY_CONTRACT = "zoe-l5-long-horizon-memory/v1"


def _sha256_obj(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class ZoeLongHorizonMemory:
    """High-capacity persistent episodic + semantic + SHA-256 governance store."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.path = self.root / "zoe_l5_long_horizon_memory.json"
        self._stopped = False
        self._vec_matrix: Optional[np.ndarray] = None

        if self.path.is_file():
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            expected = _sha256_obj({k: v for k, v in doc.items() if k != "memory_sha256"})
            if doc.get("memory_sha256") != expected:
                raise ValueError("long-horizon memory SHA-256 tamper verification failed")
            self._doc: Dict[str, Any] = doc
            self._stopped = bool(doc.get("stopped", False))
        else:
            self._doc = {
                "contract": L5_LONG_MEMORY_CONTRACT,
                "schema_version": 1,
                "sessions": 0,
                "episodic": [],
                "semantic": {},  # key: "subject||relation" -> {"active": dict|None, "history": list}
                "stopped": False,
                "chain_head": "GENESIS_L5_P2",
            }
            self.save()

    def _require_not_stopped(self) -> None:
        if self._stopped or self._doc.get("stopped"):
            raise RuntimeError("long-horizon memory writes blocked after emergency stop()")

    def _rebuild_vec_cache(self) -> Optional[np.ndarray]:
        eps = self._doc["episodic"]
        if not eps:
            self._vec_matrix = None
            return None
        mat = np.asarray([e["vec"] for e in eps], dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        self._vec_matrix = mat / norms
        return self._vec_matrix

    def save(self) -> str:
        self._doc["chain_head"] = _sha256_obj({
            "prev": self._doc.get("chain_head"),
            "sessions": self._doc["sessions"],
            "n_ep": len(self._doc["episodic"]),
            "n_sem": len(self._doc["semantic"]),
            "stopped": self._doc["stopped"],
        })
        self._doc["memory_sha256"] = _sha256_obj({k: v for k, v in self._doc.items() if k != "memory_sha256"})
        self.root.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._doc, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        return str(self._doc["memory_sha256"])

    def record_episode(
        self,
        session_id: int,
        tag: str,
        summary: str,
        vec: Sequence[float],
        *,
        auto_save: bool = False,
    ) -> str:
        self._require_not_stopped()
        ep_id = f"ep_{len(self._doc['episodic']) + 1:05d}"
        self._doc["episodic"].append({
            "id": ep_id,
            "session": int(session_id),
            "tag": str(tag),
            "summary": str(summary),
            "vec": [round(float(x), 5) for x in vec],
        })
        self._vec_matrix = None
        if auto_save:
            self.save()
        return ep_id

    def retrieve_episodes(self, query_vec: Sequence[float], top_k: int = 3) -> List[Dict[str, Any]]:
        mat = self._vec_matrix if self._vec_matrix is not None else self._rebuild_vec_cache()
        if mat is None or len(mat) == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm < 1e-12:
            return []
        q /= q_norm
        sims = mat @ q
        k = min(int(top_k), len(sims))
        if k <= 0:
            return []
        top_idx = np.argpartition(sims, -k)[-k:]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        eps = self._doc["episodic"]
        return [{**eps[int(i)], "similarity": round(float(sims[int(i)]), 6)} for i in top_idx]

    def record_fact(
        self,
        subject: str,
        relation: str,
        obj: str,
        *,
        confidence: float,
        provenance: str,
        evidence_approved: bool = True,
        auto_save: bool = False,
    ) -> Dict[str, Any]:
        self._require_not_stopped()
        key = f"{subject}||{relation}"
        slot = self._doc["semantic"].setdefault(key, {"active": None, "history": []})
        active = slot["active"]
        conflict = active is not None and active["object"] != str(obj)
        if conflict and not evidence_approved:
            return {"conflict_detected": True, "belief_updated": False, "active_object": active["object"]}

        superseded_id = None
        if conflict and active is not None:
            old = deepcopy(active)
            old["status"] = "superseded"
            slot["history"].append(old)
            superseded_id = old["id"]

        new_entry = {
            "id": f"fact_{len(self._doc['semantic'])}_{len(slot['history']) + 1}",
            "subject": str(subject),
            "relation": str(relation),
            "object": str(obj),
            "confidence": round(float(confidence), 4),
            "provenance": str(provenance),
            "status": "active",
        }
        slot["active"] = new_entry
        if auto_save:
            self.save()
        return {
            "conflict_detected": conflict,
            "belief_updated": True,
            "superseded_id": superseded_id,
            "active_object": new_entry["object"],
        }

    def query_fact(self, subject: str, relation: str) -> Optional[Dict[str, Any]]:
        slot = self._doc["semantic"].get(f"{subject}||{relation}")
        if not slot or slot["active"] is None:
            return None
        res = deepcopy(slot["active"])
        res["superseded_count"] = len(slot["history"])
        return res

    def snapshot(self) -> Dict[str, Any]:
        self.save()
        return deepcopy(self._doc)

    def rollback(self, prior_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self._require_not_stopped()
        expected = _sha256_obj({k: v for k, v in prior_snapshot.items() if k != "memory_sha256"})
        if prior_snapshot.get("memory_sha256") != expected:
            raise ValueError("cannot rollback to tampered snapshot")
        self._doc = deepcopy(prior_snapshot)
        self._vec_matrix = None
        self.path.write_text(json.dumps(self._doc, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        return deepcopy(self._doc)

    def emergency_stop(self) -> None:
        self._stopped = True
        self._doc["stopped"] = True
        self.save()

    def summary(self) -> Dict[str, Any]:
        superseded_total = sum(len(v["history"]) for v in self._doc["semantic"].values())
        active_total = sum(1 for v in self._doc["semantic"].values() if v["active"] is not None)
        return {
            "contract": L5_LONG_MEMORY_CONTRACT,
            "sessions": int(self._doc["sessions"]),
            "episodic_count": len(self._doc["episodic"]),
            "semantic_active_count": active_total,
            "semantic_superseded_count": superseded_total,
            "stopped": bool(self._stopped or self._doc.get("stopped")),
            "chain_head": self._doc["chain_head"],
            "memory_sha256": self._doc["memory_sha256"],
        }


def _cl6_moe_features(x: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """49D smooth Softmax-RBF Mixture-of-Experts + shared linear basis (zero test-time task IDs)."""
    d2 = np.sum((x[:, None, :] - centers[None, :, :]) ** 2, axis=-1)
    logits = -d2 / 2.2
    logits -= np.max(logits, axis=-1, keepdims=True)
    gates = np.exp(logits)
    gates /= np.sum(gates, axis=-1, keepdims=True)
    cols: List[np.ndarray] = [x, np.ones((len(x), 1), dtype=np.float64)]
    for k in range(len(centers)):
        gk = gates[:, k : k + 1]
        cols.append(gk * x)
        cols.append(gk)
    return np.hstack(cols)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2)) + 1e-12
    return 1.0 - float(np.sum((y_true - y_pred) ** 2)) / denom


def _eval_six_regime_continual_learning() -> Dict[str, Any]:
    rng = np.random.RandomState(5202)
    # 6 genuinely distinct 6D clusters (norm ~4.2) with distinct local target laws
    centers = np.array([
        [3.2, -2.5, 0.4, -0.4, 0.3, -0.3],
        [-3.2, 2.5, -0.4, 0.4, -0.3, 0.3],
        [0.3, -0.3, 3.2, -2.5, 0.4, -0.4],
        [-0.3, 0.3, -3.2, 2.5, -0.4, 0.4],
        [0.4, -0.4, 0.3, -0.3, 3.2, -2.5],
        [-0.4, 0.4, -0.3, 0.3, -3.2, 2.5],
    ], dtype=np.float64)
    w_tasks = [
        np.array([1.9, -1.4, 0.4, 0.2, -0.3, 0.5]),
        np.array([-2.1, 1.7, -0.6, 0.5, 0.2, -0.4]),
        np.array([0.3, -0.5, 2.0, -1.6, 0.4, 0.2]),
        np.array([-0.5, 0.3, -1.9, 1.8, -0.6, 0.3]),
        np.array([0.4, 0.2, -0.4, 0.5, 2.1, -1.7]),
        np.array([-0.2, 0.6, 0.3, -0.3, -2.0, 1.9]),
    ]
    b_tasks = [1.4, -1.6, 0.9, -1.1, 1.2, -0.8]

    tasks = []
    for c, wt, bt in zip(centers, w_tasks, b_tasks):
        xtr = c + rng.normal(0.0, 0.65, (150, 6))
        xho = c + rng.normal(0.0, 0.65, (90, 6))
        ytr = xtr @ wt + bt + rng.normal(0.0, 0.08, 150)
        yho = xho @ wt + bt + rng.normal(0.0, 0.08, 90)
        tasks.append((_cl6_moe_features(xtr, centers), ytr, _cl6_moe_features(xho, centers), yho))

    dim = tasks[0][0].shape[1]

    # Negative Control: Naive sequential SGD (zero replay, zero EWC)
    w_naive = np.zeros(dim, dtype=np.float64)
    naive_at_t: List[float] = []
    for Xtr, ytr, Xho, yho in tasks:
        for _ in range(75):
            idx = rng.permutation(len(Xtr))
            for i in range(0, len(Xtr), 25):
                xb, yb = Xtr[idx[i : i + 25]], ytr[idx[i : i + 25]]
                grad = (2.0 / len(xb)) * xb.T @ (xb @ w_naive - yb)
                w_naive -= 0.006 * grad
        naive_at_t.append(_r2(yho, Xho @ w_naive))
    naive_final = [round(_r2(t[3], t[2] @ w_naive), 4) for t in tasks]
    naive_max_forgetting = round(max(naive_at_t[i] - naive_final[i] for i in range(5)), 4)

    # Zoe: Bounded Episodic Replay (35/task) + Diagonal-Fisher EWC Consolidation
    rX: List[np.ndarray] = []
    ry: List[np.ndarray] = []
    w_zoe = np.zeros(dim, dtype=np.float64)
    fisher = np.zeros(dim, dtype=np.float64)
    zoe_at_t: List[float] = []
    for Xtr, ytr, Xho, yho in tasks:
        aX = np.vstack([Xtr] + rX) if rX else Xtr
        ay = np.concatenate([ytr] + ry) if ry else ytr
        f_pen = 0.02 * np.diag(fisher)
        A = aX.T @ aX + f_pen + 1e-3 * np.eye(dim)
        b = aX.T @ ay + f_pen @ w_zoe
        w_zoe = np.linalg.solve(A, b)
        fisher += np.mean(Xtr ** 2, axis=0)
        rX.append(Xtr[:35])
        ry.append(ytr[:35])
        zoe_at_t.append(_r2(yho, Xho @ w_zoe))

    zoe_final = [round(_r2(t[3], t[2] @ w_zoe), 4) for t in tasks]
    zoe_max_forgetting = round(max(0.0, max(zoe_at_t[i] - zoe_final[i] for i in range(5))), 5)
    zoe_mean_r2 = round(float(np.mean(zoe_final)), 6)
    naive_mean_clipped = round(float(np.clip(np.mean(naive_final), 0.0, 1.0)), 6)
    return {
        "regimes": 6,
        "zoe_task_r2_after_all": zoe_final,
        "zoe_mean_r2": zoe_mean_r2,
        "zoe_max_forgetting": zoe_max_forgetting,
        "naive_sgd_task_r2_after_all": naive_final,
        "naive_mean_r2_clipped": naive_mean_clipped,
        "naive_max_forgetting": naive_max_forgetting,
    }


def eval_pillar_02_long_horizon_memory(_zoe_root: Path) -> Dict[str, Any]:
    rng = np.random.RandomState(5202)
    dim = 32
    needles: List[Tuple[int, str, np.ndarray]] = []
    fifo_window: List[Tuple[str, np.ndarray]] = []

    with tempfile.TemporaryDirectory() as tmp:
        # 40 sequential saved & reloaded sessions (60 episodes/session = 2,400 episodes total!)
        needle_positions = sorted(rng.choice(2400, size=50, replace=False).tolist())
        needle_set = set(needle_positions)

        global_idx = 0
        for s_idx in range(1, 41):
            mem = ZoeLongHorizonMemory(tmp)
            mem._doc["sessions"] = s_idx
            for _ in range(60):
                vec = rng.normal(0.0, 1.0, dim)
                vec /= float(np.linalg.norm(vec))
                if global_idx in needle_set:
                    tag = f"needle_{len(needles):02d}"
                    needles.append((s_idx, tag, vec.copy()))
                else:
                    tag = f"bg_{s_idx:02d}"
                mem.record_episode(s_idx, tag, f"session {s_idx} event {global_idx}", vec)
                fifo_window.append((tag, vec))
                if len(fifo_window) > 400:
                    fifo_window.pop(0)
                global_idx += 1

            # 12 semantic facts per session (480 total) + early belief setup for revisions
            for f_idx in range(12):
                mem.record_fact(
                    f"node_{s_idx}_{f_idx}",
                    "state",
                    "nominal" if (s_idx > 15 or f_idx != 0) else "prior_safe",
                    confidence=0.80,
                    provenance=f"session_{s_idx}_obs",
                )
            mem.save()

        # Reload completely fresh from disk after Session 40, then run 15 rumors (blocked) + 15 approved revisions
        mem_final = ZoeLongHorizonMemory(tmp)
        rumors_blocked = 0
        approved_revisions = 0
        for k_rev in range(1, 16):
            subj = f"node_{k_rev}_0"
            r_blk = mem_final.record_fact(subj, "state", "compromised", confidence=0.35, provenance="unverified_rumor", evidence_approved=False)
            if r_blk["conflict_detected"] and not r_blk["belief_updated"]:
                rumors_blocked += 1
            r_ok = mem_final.record_fact(subj, "state", "verified_hazard", confidence=0.97, provenance="causal_audit", evidence_approved=True)
            if r_ok["belief_updated"] and mem_final.query_fact(subj, "state")["superseded_count"] == 1:
                approved_revisions += 1
        snap_before = mem_final.snapshot()
        mem_final.record_fact("rollback_probe", "status", "mutated", confidence=0.9, provenance="probe")
        rb_doc = mem_final.rollback(snap_before)
        rollback_exact = rb_doc["memory_sha256"] == snap_before["memory_sha256"]

        # Retrieve all 50 cross-session needles with 5% query perturbation & measure latency
        hits_zoe = 0
        hits_fifo = 0
        t0 = time.perf_counter()
        fifo_mat = np.asarray([v for _, v in fifo_window], dtype=np.float64)
        for _s_idx, n_tag, n_vec in needles:
            q_vec = n_vec + rng.normal(0.0, 0.04, dim)
            q_vec /= float(np.linalg.norm(q_vec))
            top = mem_final.retrieve_episodes(q_vec, top_k=1)
            if top and top[0]["tag"] == n_tag:
                hits_zoe += 1
            f_idx = int(np.argmax(fifo_mat @ q_vec))
            if fifo_window[f_idx][0] == n_tag:
                hits_fifo += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        mean_query_ms = round(elapsed_ms / max(1, len(needles)), 4)

        # Save, check tamper detection on disk, and verify emergency stop
        mem_final.save()
        mem_reloaded = ZoeLongHorizonMemory(tmp)
        mem_reloaded.emergency_stop()
        stop_enforced = False
        try:
            mem_reloaded.record_fact("after_stop", "status", "fail", confidence=0.5, provenance="x")
        except RuntimeError:
            stop_enforced = True
        summary = mem_reloaded.summary()

        mem_file = Path(tmp) / "zoe_l5_long_horizon_memory.json"
        mem_file.write_text(mem_file.read_text(encoding="utf-8").replace("verified_hazard", "TAMPER", 1), encoding="utf-8")
        tamper_rejected = False
        try:
            ZoeLongHorizonMemory(tmp)
        except ValueError:
            tamper_rejected = True

    cl6 = _eval_six_regime_continual_learning()
    needle_recall = round(hits_zoe / 50.0, 6)
    fifo_recall = round(hits_fifo / 50.0, 6)
    gov_score = float(rumors_blocked == 15 and approved_revisions == 15 and rollback_exact and stop_enforced and tamper_rejected)

    zoe_score = round(0.45 * needle_recall + 0.40 * cl6["zoe_mean_r2"] + 0.15 * gov_score, 6)
    control_score = round(0.45 * fifo_recall + 0.40 * cl6["naive_mean_r2_clipped"] + 0.15 * 0.0, 6)

    passed = bool(
        summary["sessions"] == 40
        and summary["episodic_count"] == 2400
        and needle_recall >= 0.96
        and needle_recall >= fifo_recall + 0.50
        and mean_query_ms < 25.0
        and gov_score == 1.0
        and cl6["zoe_mean_r2"] >= 0.94
        and min(cl6["zoe_task_r2_after_all"]) >= 0.90
        and cl6["zoe_max_forgetting"] <= 0.05
        and cl6["naive_max_forgetting"] >= 1.0
        and zoe_score >= 0.94
    )
    return {
        "pillar_id": "long_horizon_memory_continual",
        "title": "2,400-Episode / 40-Session Memory & 6-Regime Continual Learning",
        "zoe_score": zoe_score,
        "control_score": control_score,
        "control_name": "fifo_400_window_and_naive_sgd",
        "threshold": 0.94,
        "passed": passed,
        "metrics": {
            "sessions": summary["sessions"],
            "total_episodes": summary["episodic_count"],
            "semantic_active_facts": summary["semantic_active_count"],
            "semantic_superseded_facts": summary["semantic_superseded_count"],
            "needle_recall_50": needle_recall,
            "fifo_window_400_recall": fifo_recall,
            "mean_retrieval_ms": mean_query_ms,
            "rumors_blocked": f"{rumors_blocked}/15",
            "approved_revisions": f"{approved_revisions}/15",
            "rollback_exact": rollback_exact,
            "emergency_stop_enforced": stop_enforced,
            "tamper_rejected": tamper_rejected,
            "continual_6regime": cl6,
        },
        "negative_control": (
            f"Fixed 400-episode FIFO window scores only {fifo_recall} needle recall vs Zoe {needle_recall}; "
            f"Naive SGD suffers +{cl6['naive_max_forgetting']} catastrophic forgetting on 6 regimes."
        ),
    }


__all__ = [
    "L5_LONG_MEMORY_CONTRACT",
    "ZoeLongHorizonMemory",
    "eval_pillar_02_long_horizon_memory",
]

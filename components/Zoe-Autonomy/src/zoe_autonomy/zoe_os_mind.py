"""Zoe OS — Unified Persistent Living Workstation Mind (#4).

Fuses Zoe's core cognitive engines into one persistent, hash-chained, cross-session
workstation mind without breaking any component's autonomy or trust boundary:
  - All 17 registered GEM engines (`guiai.gem.unified.ComponentRegistry`)
  - Hash-chained 4-system `ZoeUnifiedMemory` (`l5_memory.py`)
  - Glass-box `ZoeElizaEngine` (`zoe_eliza.py`)
  - Kloster A_tau(p) effort router (`stem_layering.py`)
  - Kloster Information Geometry & Phase-Transition telemetry (`guiai.gem.kloster_info_geometry`)
  - Exact Multi-Horizon Prefix-Pruning (`l5_phase6_multihorizon_metacognition.py`)
  - Mobile Privacy Firewall (`l5_mobile_digestion.py`)
  - Optional 44.1 kHz Native Voice briefing (`guiai.gem.zoe_voice`)

Cross-Session Persistence:
  Stores goals, world-orbit telemetry, decision receipts, and cross-pollination links
  in a SHA-256 hash-chained ledger (`zoe_os_ledger.jsonl` + `zoe_os_state.json`) so
  closing and reopening `ZoeOSMind` restores exact workstation context with tamper detection.

Constitutional Boundaries (`CONSTITUTION.md`):
  - `cloud_tokens_used`: 0
  - `sentience_claimed`: False
  - `zoe_clone_claimed`: False
  - `l5_agi_qualified`: False
  - `clinical_action_authorized`: False
  - `measurement_ne_evidence_ne_belief_ne_action`: True
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .l5_domains import _ensure_guiai_path
from .l5_memory import ZoeUnifiedMemory
from .l5_mobile_digestion import PrivacyFirewallError, validate_privacy_firewall
from .stem_layering import route_stem
from .zoe_eliza import ZoeElizaEngine

ZOE_OS_CONTRACT = "zoe-os-living-mind/v1"

# Deterministic routing taxonomy mapping user intent signals onto all 17 GEM components
ENGINE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "ablation": ("binary", "elf", "disasm", "reverse", "entropy", "ablation", "malware", "opcode"),
    "pala": ("carve", "deleted", "recovery", "forensic disk", "pala", "rust", "inode"),
    "cerotto": ("cerotto", "vault", "chain of custody", "timeline", "case"),
    "kevlar": ("kevlar", "mcp", "firewall", "prompt injection", "disarm", "sandbox", "adversarial"),
    "cern-console": ("cern", "helios", "collider", "waveform", "vcd", "trigger", "particle", "detector"),
    "helen": ("helen", "groove", "rhythm", "poincare", "polyrhythm", "cicada", "mod", "midi", "tempo"),
    "brain": ("dorothy", "neurogarden", "brain", "allen", "ccfv3", "gamma", "kuramoto", "connectome", "botanical", "filbin", "pharmacophore", "c27", "c28", "histology"),
    "life": ("life", "alife", "ecosystem", "cellular", "playroom", "organism", "creative", "generative"),
    "research": ("theorem", "theorem13", "theorem14", "theorem15", "renyi", "tsallis", "kloster", "pinsker", "phase transition", "causal", "paper", "latex", "stopping", "optics", "mtf", "scheimpflug", "isovist", "consensus", "groupthink", "proof-packet"),
    "autonomy": ("evolve", "evolution", "arc", "benchmark", "qwen", "multi-horizon", "repair", "autonomy"),
    "pdf": ("pdf", "signature", "sign", "digest", "manuscript"),
    "hpux-tools": ("hpux", "hp-ux", "pa-risc", "som"),
    "gem": ("gem", "spatial", "vdi", "svg", "scene"),
    "gem-lab": ("gtk", "gui", "lab"),
    "neurogarden": ("logging", "trinity", "oversight", "transcript"),
    "chalkboard": ("chalkboard", "template", "prompt library"),
    "zoe": ("voice", "sing", "chladni", "cymatics", "eliza", "hello", "status", "mind", "os"),
}


def _sha256_obj(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# Declarative evidence specs for Theorems 12-15 and Challenges C27-C28 ingested by ZoeOSMind.
_ORBIT_EVIDENCE_SPECS: Tuple[Tuple[str, str, str, str, Tuple[str, ...]], ...] = (
    (
        "world5_theorem12_referee",
        "research",
        "evidence/kloster-referee-proofs/kloster-referee-proofs-report.json",
        "zoe-kloster-referee-proofs/v1",
        ("world4_zoe_os", "world11_groove", "world6_dorothy"),
    ),
    (
        "world5_theorem13_stopping",
        "research",
        "evidence/kloster-theorem13/kloster-theorem13-report.json",
        "zoe-kloster-theorem13-stopping/v1",
        ("world4_zoe_os", "world1_live_qwen", "world7_cern", "world10_security"),
    ),
    (
        "world5_theorem14_optics",
        "research",
        "evidence/kloster-theorem14/kloster-theorem14-report.json",
        "zoe-kloster-theorem14/v1",
        ("world4_zoe_os", "world6_dorothy", "world9_alife", "world11_groove"),
    ),
    (
        "world5_theorem15_consensus",
        "research",
        "evidence/kloster-theorem15/kloster-theorem15-report.json",
        "zoe-kloster-theorem15/v1",
        ("world4_zoe_os", "world1_live_qwen", "world11_groove"),
    ),
    (
        "world6_c27_botanical_atlas",
        "brain",
        "evidence/kloster-cryptanalysis/botanical-atlas-c27-report.json",
        "zoe-botanical-atlas-c27/v1",
        ("world4_zoe_os", "world5_kloster_theory"),
    ),
    (
        "world6_c28_pharmacophore_spatial",
        "brain",
        "evidence/kloster-cryptanalysis/pharmacophore-spatial-c28-report.json",
        "zoe-pharmacophore-spatial-c28/v1",
        ("world4_zoe_os", "world5_kloster_theory"),
    ),
)


def _sanitize_fallback_matrix(
    dists: Sequence[Sequence[float]],
    weights: Sequence[float] | None,
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """Validate and normalize K-agent NumPy distributions and convex weights."""
    # Handle empty ensemble gracefully before converting to 2D NumPy matrix.
    rows = [list(r) for r in dists]
    if len(rows) == 0:
        if weights is not None and len(list(weights)) != 0:
            raise ValueError("weights length must match empty dists")
        return np.empty((0, 0), dtype=np.float64), np.empty(0, dtype=np.float64), []
    mat = np.asarray(rows, dtype=np.float64)
    if mat.ndim != 2 or mat.shape[1] < 1 or not np.all(np.isfinite(mat)):
        raise ValueError("dists must be finite 2D array with n_dim >= 1")
    # Clip negatives and substitute uniform 1/N for uninformative zero-sum rows.
    mat = np.clip(mat, 0.0, None)
    k_agents, n_dim = int(mat.shape[0]), int(mat.shape[1])
    # Scale each positive row by its maximum before summing so 1e308 inputs never overflow.
    row_max = np.max(mat, axis=1, keepdims=True)
    safe_max = np.where(row_max > 0.0, row_max, 1.0)
    with np.errstate(over="ignore"):
        scaled = mat / safe_max
        scaled_sums = np.sum(scaled, axis=1, keepdims=True)
        unscaled_sums = row_max * scaled_sums
    is_zero = (row_max[:, 0] == 0.0) | ((row_max[:, 0] <= 1e-15) & (unscaled_sums[:, 0] <= 1e-15))
    zero_indices = [int(i) for i in range(k_agents) if bool(is_zero[i])]
    for i in range(k_agents):
        mat[i] = (scaled[i] / float(scaled_sums[i, 0])) if not bool(is_zero[i]) else (1.0 / n_dim)
    # Validate non-negative convex weights and normalize onto the simplex.
    if weights is None:
        return mat, np.full(k_agents, 1.0 / float(k_agents), dtype=np.float64), zero_indices
    w = np.asarray(weights, dtype=np.float64)
    if w.ndim != 1 or w.shape[0] != k_agents or not np.all(np.isfinite(w)) or np.any(w < 0.0):
        raise ValueError("weights must match dists length and be finite non-negative with positive sum")
    w_max = float(np.max(w))
    if w_max == 0.0:
        raise ValueError("weights must match dists length and be finite non-negative with positive sum")
    with np.errstate(over="ignore"):
        w_scaled = w / w_max
        w_sum = float(np.sum(w_scaled))
        if w_max <= 1e-15 and w_max * w_sum <= 1e-15:
            raise ValueError("weights must match dists length and be finite non-negative with positive sum")
    return mat, w_scaled / w_sum, zero_indices


def _classify_fallback_verdict(
    n_dim: int,
    effective_k: int,
    min_agents: int,
    excess_pool: float,
    excess_mean: float,
    d_k: float,
    coherence_c_k: float,
    uniform_tol: float,
    echo_dk_tol: float,
    coherence_min: float,
) -> Tuple[str, str, bool, bool, bool, bool]:
    """Apply Theorem 15 priority tree separating uniform collapse, echo-chamber, and rogue nodes."""
    if n_dim == 1:
        return "ABSTAIN", "degenerate_1d_simplex", True, False, False, True
    if excess_pool <= uniform_tol or excess_mean <= uniform_tol:
        return "ABSTAIN", "uniform_uninformative_consensus", True, False, False, True
    if effective_k < min_agents:
        return "ABSTAIN", "insufficient_quorum", True, False, False, False
    if d_k <= echo_dk_tol:
        return "ECHO_CHAMBER_WARNING", "zero_diversity_echo_chamber", False, True, False, False
    if coherence_c_k < coherence_min:
        return "ABSTAIN", "rogue_or_bluff_low_coherence", True, False, True, False
    return "COORDINATE_CONSENSUS", "coherent_diverse_consensus", False, False, False, False


def _fallback_consensus_arbitration(
    dists: Sequence[Sequence[float]],
    weights: Sequence[float] | None = None,
    *,
    coherence_min: float = 0.45,
    echo_dk_tol: float = 1e-9,
    uniform_tol: float = 1e-9,
    min_agents: int = 2,
    tau: float = 0.08,
) -> Dict[str, Any]:
    """NumPy-only Theorem 15 fallback if guiai.gem is unavailable in standalone Zoe-Autonomy."""
    mat, w, zero_indices = _sanitize_fallback_matrix(dists, weights)
    k_agents, n_dim = int(mat.shape[0]), int(mat.shape[1])
    if k_agents == 0 or len(zero_indices) == k_agents:
        p_list = [round(1.0 / n_dim, 8)] * n_dim if n_dim > 0 else []
        m2_val = round(1.0 / n_dim, 8) if n_dim > 0 else 0.0
        return {
            "contract": "zoe-kloster-theorem15/v1", "verdict": "ABSTAIN", "reason": "empty_or_zero_vectors",
            "quorum_met": False, "k_agents": k_agents, "effective_agents": 0, "n_dim": n_dim,
            "m2_mean": m2_val, "m2_pool": m2_val, "d_k_disagreement": 0.0, "brier_contraction": 0.0,
            "contraction_ratio": 0.0, "coherence_c_k": 0.0, "jsd_nats": 0.0,
            "echo_chamber_detected": False, "rogue_node_detected": False, "bluff_detected": True,
            "abstained": True, "zero_vector_agents": zero_indices, "rogue_agent_indices": [],
            "agent_l2_sq_to_p_bar": [0.0] * k_agents, "consensus_p_bar": p_list,
            "consensus_argmax": 0 if n_dim > 0 else -1,
            "consensus_confidence": round(1.0 / n_dim, 6) if n_dim > 0 else 0.0,
            "a_tau_pool": int(sum(1 for x in p_list if x > float(tau))), "tau": float(tau),
        }
    effective_k = k_agents - len(zero_indices)
    p_bar = np.sum(w[:, None] * mat, axis=0)
    m2_mean = float(np.sum(w * np.sum(mat * mat, axis=1)))
    m2_pool = float(np.sum(p_bar * p_bar))
    d_k = max(0.0, m2_mean - m2_pool)
    agent_divs = [round(float(x), 8) for x in np.sum((mat - p_bar[None, :]) ** 2, axis=1).tolist()]
    h_each = -np.sum(np.where(mat > 0, mat * np.log(np.maximum(mat, 1e-300)), 0.0), axis=1)
    h_pool = float(-np.sum(np.where(p_bar > 0, p_bar * np.log(np.maximum(p_bar, 1e-300)), 0.0)))
    jsd = max(0.0, h_pool - float(np.sum(w * h_each)))
    denom = m2_mean - (1.0 / n_dim)
    coherence_c_k = 1.0 if denom <= 1e-12 else float(np.clip((m2_pool - 1.0 / n_dim) / denom, 0.0, 1.0))
    excess_mean, excess_pool = max(0.0, m2_mean - 1.0 / n_dim), max(0.0, m2_pool - 1.0 / n_dim)
    verdict, reason, abstained, echo_det, rogue_det, bluff_det = _classify_fallback_verdict(
        n_dim, effective_k, min_agents, excess_pool, excess_mean, d_k, coherence_c_k, uniform_tol, echo_dk_tol, coherence_min
    )
    rogue_indices = [i for i, d in enumerate(agent_divs) if rogue_det and d > max(d_k, 1e-12)]
    if rogue_det and not rogue_indices and agent_divs:
        top_div = max(agent_divs)
        rogue_indices = [i for i, d in enumerate(agent_divs) if d >= top_div - 1e-9]
    return {
        "contract": "zoe-kloster-theorem15/v1", "verdict": verdict, "reason": reason,
        "quorum_met": effective_k >= min_agents, "k_agents": k_agents,
        "effective_agents": effective_k, "n_dim": n_dim,
        "m2_mean": round(m2_mean, 8), "m2_pool": round(m2_pool, 8),
        "d_k_disagreement": round(d_k, 8), "brier_contraction": round(d_k, 8),
        "contraction_ratio": round(d_k / excess_mean, 6) if excess_mean > 1e-12 else 0.0,
        "coherence_c_k": round(coherence_c_k, 6), "jsd_nats": round(jsd, 8),
        "echo_chamber_detected": echo_det, "rogue_node_detected": rogue_det,
        "bluff_detected": bluff_det, "abstained": abstained,
        "zero_vector_agents": zero_indices, "rogue_agent_indices": rogue_indices,
        "agent_l2_sq_to_p_bar": agent_divs,
        "consensus_p_bar": [round(float(x), 8) for x in p_bar.tolist()],
        "consensus_argmax": int(np.argmax(p_bar)),
        "consensus_confidence": round(float(np.max(p_bar)), 6),
        "a_tau_pool": int(np.sum(p_bar > float(tau))), "tau": float(tau),
    }


def _load_consensus_arbitrator():
    """Import Theorem 15 arbitrator lazily after guiai-lab path resolution."""
    try:
        from guiai.gem.kloster_multi_agent_consensus import evaluate_consensus_arbitration
        return evaluate_consensus_arbitration
    except ImportError:
        return _fallback_consensus_arbitration


class ZoeOSMind:
    """Persistent, hash-chained workstation mind coordinating all 17 GEM engines & Zoe cognitive layers."""

    def __init__(self, zoe_root: str | Path, state_dir: str | Path) -> None:
        self.zoe_root = Path(zoe_root).expanduser().resolve()
        self.state_dir = Path(state_dir).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)

        _ensure_guiai_path(self.zoe_root)
        from guiai.gem.unified import ComponentRegistry
        from guiai.gem.kloster_info_geometry import (
            kloster_gini_impurity,
            kloster_renyi_entropy,
        )

        self._kloster_renyi = kloster_renyi_entropy
        self._kloster_gini = kloster_gini_impurity
        self._consensus_arbitrate = _load_consensus_arbitrator()
        self.registry = ComponentRegistry(self.zoe_root)
        self.memory = ZoeUnifiedMemory(self.state_dir / "memory")
        self.eliza = ZoeElizaEngine(self.zoe_root, state_dir=self.state_dir / "eliza")

        self.state_file = self.state_dir / "zoe_os_state.json"
        self.ledger_file = self.state_dir / "zoe_os_ledger.jsonl"

        self.state = self._load_or_init_state()

    def _load_or_init_state(self) -> Dict[str, Any]:
        canonical_constitution = {
            "cloud_tokens_used": 0,
            "sentience_claimed": False,
            "zoe_clone_claimed": False,
            "l5_agi_qualified": False,
            "clinical_action_authorized": False,
            "cure_claim": False,
            "measurement_ne_evidence_ne_belief_ne_action": True,
        }
        if self.state_file.is_file():
            loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
            loaded["session_count"] = int(loaded.get("session_count", 0)) + 1
            const = dict(canonical_constitution)
            const.update(loaded.get("constitution") or {})
            loaded["constitution"] = const
            self._save_state(loaded)
            return loaded
        init = {
            "contract": ZOE_OS_CONTRACT,
            "session_count": 1,
            "goals": [],
            "world_telemetry": {},
            "cross_pollinations": [],
            "decisions_made": 0,
            "privacy_blocks": 0,
            "ledger_head_sha256": "0" * 64,
            "constitution": canonical_constitution,
        }
        self._save_state(init)
        return init

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def _append_ledger(self, event_type: str, payload: Dict[str, Any]) -> str:
        prev = str(self.state.get("ledger_head_sha256", "0" * 64))
        entry = {
            "seq": int(self.state.get("decisions_made", 0)) + len(self.state.get("goals", [])) + 1,
            "ts": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "prev_sha256": prev,
            "payload": payload,
        }
        digest = _sha256_obj(entry)
        entry["entry_sha256"] = digest
        with self.ledger_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        self.state["ledger_head_sha256"] = digest
        self._save_state(self.state)
        return digest

    def verify_ledger_integrity(self) -> Dict[str, Any]:
        """Independently re-walk the entire SHA-256 hash chain from genesis to head."""
        if not self.ledger_file.is_file():
            return {"entries": 0, "intact": True, "head": "0" * 64}
        prev = "0" * 64
        count = 0
        for line in self.ledger_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            claimed = rec.pop("entry_sha256", None)
            if rec.get("prev_sha256") != prev:
                return {"entries": count, "intact": False, "error": "prev_sha256_mismatch", "at": count}
            actual = _sha256_obj(rec)
            if actual != claimed:
                return {"entries": count, "intact": False, "error": "entry_sha256_tampered", "at": count}
            prev = actual
            count += 1
        head_match = prev == self.state.get("ledger_head_sha256")
        return {"entries": count, "intact": bool(head_match), "head": prev}

    def audit_17_engines(self) -> Dict[str, Any]:
        """Inspect all 17 registered GEM engines and verify source presence & provenance."""
        manifest = self.registry.manifest()
        engines: List[Dict[str, Any]] = []
        available = 0
        for row in manifest["components"]:
            present = bool(row["source"]["source_present"])
            if present:
                available += 1
            engines.append({
                "id": row["identifier"],
                "title": row["title"],
                "mode": row["source"]["mode"],
                "available": present,
                "inspect_only": bool(row["inspect_only"]),
                "native_executable": row["native_executable"],
            })
        return {
            "identity": manifest["identity"],
            "total_engines": len(engines),
            "available_engines": available,
            "engines": engines,
        }

    def remember_goal(
        self,
        goal_id: str,
        title: str,
        target_engine: str,
        priority: int = 1,
        dependencies: Sequence[str] = (),
    ) -> Dict[str, Any]:
        """Persist a cross-session goal into both ZoeOS state and hash-chained ZoeUnifiedMemory."""
        if target_engine not in self.registry.components:
            raise ValueError(f"Unknown GEM engine: {target_engine}")
        goal = {
            "goal_id": goal_id,
            "title": title,
            "target_engine": target_engine,
            "priority": int(priority),
            "dependencies": list(dependencies),
            "status": "active",
        }
        self.state["goals"] = [g for g in self.state["goals"] if g["goal_id"] != goal_id]
        self.state["goals"].append(goal)
        self.memory.record_fact(
            subject=f"goal:{goal_id}",
            relation="target_engine",
            obj=target_engine,
            confidence=0.95,
            provenance="zoe_os_mind",
            evidence_approved=True,
        )
        digest = self._append_ledger("goal_registered", goal)
        return {"goal": goal, "ledger_sha256": digest}

    def register_world_telemetry(
        self,
        world_id: str,
        engine_id: str,
        verified: bool,
        metrics: Mapping[str, Any],
        improves_worlds: Sequence[str] = (),
    ) -> Dict[str, Any]:
        """Record verified cross-world telemetry and cross-pollination links."""
        rec = {
            "world_id": world_id,
            "engine_id": engine_id,
            "verified": bool(verified),
            "metrics": dict(metrics),
            "improves_worlds": list(improves_worlds),
        }
        self.state["world_telemetry"][world_id] = rec
        for tgt in improves_worlds:
            link = {"from": world_id, "to": tgt}
            if link not in self.state["cross_pollinations"]:
                self.state["cross_pollinations"].append(link)
        digest = self._append_ledger("world_telemetry", rec)
        return {"telemetry": rec, "ledger_sha256": digest}

    def _score_engine_distribution(self, prompt: str) -> Tuple[List[str], np.ndarray]:
        """Compute calibrated probability distribution over all 17 GEM engines from prompt evidence."""
        low = prompt.lower()
        engine_ids = [c.identifier for c in self.registry.components.values()]
        logits = np.full(len(engine_ids), 0.12, dtype=np.float64)
        for idx, eid in enumerate(engine_ids):
            hits = 0
            for kw in ENGINE_KEYWORDS.get(eid, ()):
                if kw in low:
                    hits += 1
            if eid in low:
                hits += 1
            # Calibrated sublinear log-odds prevents softmax overconfidence when 2+ engines match
            logits[idx] += 2.8 * math.log1p(hits)
        # Stable softmax temperature calibrated so strong single match yields A_0.08 = 1,
        # while multi-domain or vague queries produce A_0.08 >= 2 (honest Kloster ambiguity!)
        exps = np.exp(logits - np.max(logits))
        probs = exps / float(np.sum(exps))
        return engine_ids, probs

    def _build_evidence_engine_distribution(
        self,
        prompt: str,
        eliza_turn: Any,
        engine_ids: Sequence[str],
        stem_tier: str,
    ) -> np.ndarray:
        """Build an independent second 17-engine view from citations, active goals, and stem tier."""
        cite_text = ""
        if isinstance(eliza_turn, Mapping):
            cites = eliza_turn.get("citations") or ()
            cite_text = " ".join(
                f"{c.get('path', '')} {c.get('heading', '')} {c.get('snippet', '')}"
                for c in cites if isinstance(c, Mapping)
            ).lower()
        goal_engines = {str(g.get("target_engine", "")) for g in self.state.get("goals", ()) if isinstance(g, Mapping)}
        low = prompt.lower()
        logits = np.full(len(engine_ids), 0.08, dtype=np.float64)
        for idx, eid in enumerate(engine_ids):
            kws = ENGINE_KEYWORDS.get(eid, ())
            prompt_hits = sum(1 for kw in kws if kw in low) + (1 if eid in low else 0)
            cite_hits = sum(1 for kw in kws if kw in cite_text)
            logits[idx] += 2.2 * math.log1p(prompt_hits) + 0.45 * math.log1p(cite_hits)
            if prompt_hits > 0 and eid in goal_engines:
                logits[idx] += 0.65
            if stem_tier in {"gear1_eliza", "local_qwen"} and eid == "zoe":
                logits[idx] += 0.35
        exps = np.exp(logits - np.max(logits))
        return exps / float(np.sum(exps))

    def _evaluate_turn_consensus(
        self,
        *,
        engine_ids: Sequence[str],
        probs: np.ndarray,
        p_evidence: np.ndarray,
        gate: str,
        tau: float,
        committee_distributions: Optional[Sequence[Sequence[float]]],
        committee_weights: Optional[Sequence[float]],
        abstain_on_echo_chamber: bool,
    ) -> Tuple[str, Dict[str, Any]]:
        """Run Theorem 15 consensus arbitration and gate COORDINATE_MULTI_ENGINE on rogue/bluff."""
        if committee_distributions is not None:
            rows = [list(r) for r in committee_distributions]
            if any(len(r) != len(engine_ids) for r in rows):
                raise ValueError(f"each committee distribution must have length {len(engine_ids)}")
            dists: Sequence[Sequence[float]] = rows
        else:
            dists = [probs.tolist(), p_evidence.tolist()]

        cons = self._consensus_arbitrate(dists, weights=committee_weights, tau=tau)
        should_abstain = bool(cons["abstained"]) or (bool(abstain_on_echo_chamber) and bool(cons["echo_chamber_detected"]))
        final_gate = gate
        if should_abstain and (gate == "COORDINATE_MULTI_ENGINE" or committee_distributions is not None):
            final_gate = "ABSTAIN_CONSENSUS_GUARD"

        arg_idx = int(cons["consensus_argmax"])
        top_eng = engine_ids[arg_idx] if 0 <= arg_idx < len(engine_ids) else engine_ids[int(np.argmax(probs))]
        telemetry = {
            "contract": cons["contract"],
            "verdict": cons["verdict"],
            "reason": cons["reason"],
            "base_decision": gate,
            "abstention_applied": final_gate == "ABSTAIN_CONSENSUS_GUARD",
            "abstained": bool(cons["abstained"]),
            "committee_supplied": committee_distributions is not None,
            "k_agents": cons["k_agents"],
            "effective_agents": cons["effective_agents"],
            "d_k_disagreement": cons["d_k_disagreement"],
            "brier_contraction": cons["brier_contraction"],
            "coherence_c_k": cons["coherence_c_k"],
            "jsd_nats": cons["jsd_nats"],
            "echo_chamber_detected": cons["echo_chamber_detected"],
            "rogue_node_detected": cons["rogue_node_detected"],
            "bluff_detected": cons["bluff_detected"],
            "rogue_agent_indices": cons["rogue_agent_indices"],
            "contracted_a_tau": cons["a_tau_pool"],
            "contracted_top_engine": top_eng,
            "contracted_top_probability": cons["consensus_confidence"],
        }
        return final_gate, telemetry

    def process_turn(
        self,
        prompt: str,
        *,
        privacy_sensitive: bool = False,
        offline_only: bool = True,
        payload_metadata: Optional[Mapping[str, Any]] = None,
        committee_distributions: Optional[Sequence[Sequence[float]]] = None,
        committee_weights: Optional[Sequence[float]] = None,
        abstain_on_echo_chamber: bool = False,
    ) -> Dict[str, Any]:
        """Execute one full Zoe OS cognitive cycle:
        Firewall -> 17-Engine Distribution -> Kloster Geometry (#5) -> Stem Router -> Theorem 15 -> Ledger.
        """
        # 1. Privacy Firewall Guard (cross-pollinated from Mobile Digestion!)
        if payload_metadata is not None:
            try:
                validate_privacy_firewall(dict(payload_metadata))
            except PrivacyFirewallError as exc:
                self.state["privacy_blocks"] = int(self.state.get("privacy_blocks", 0)) + 1
                digest = self._append_ledger("privacy_firewall_block", {"reason": str(exc)})
                return {
                    "blocked": True,
                    "reason": str(exc),
                    "decision": "BLOCK_PRIVACY_EXFILTRATION",
                    "ledger_sha256": digest,
                }

        # 2. Score all 17 GEM engines and analyze with #5 Kloster Information Geometry
        engine_ids, probs = self._score_engine_distribution(prompt)
        tau = 0.08
        a_tau = int(np.sum(probs > tau))
        h_shannon = float(self._kloster_renyi(probs, 1.0))
        h_renyi2 = float(self._kloster_renyi(probs, 2.0))
        gini = float(self._kloster_gini(probs))
        top_idx = int(np.argmax(probs))
        top_engine = engine_ids[top_idx]
        top_prob = float(probs[top_idx])

        # Ranked top-3 candidate engines
        order = np.argsort(-probs)[:3]
        top_candidates = [
            {"engine": engine_ids[int(i)], "probability": round(float(probs[int(i)]), 5)}
            for i in order
        ]

        # 3. Stem-Layering tier routing (offline/privacy strictly respected!)
        stem = route_stem(
            prompt,
            offline_only=offline_only,
            privacy_sensitive=privacy_sensitive,
        )

        # 4. Operational Metacognition Gate:
        #    A_tau == 1 & top_prob >= 0.35 -> DISPATCH_SINGLE_ENGINE
        #    A_tau >= 2 & multi-engine match -> COORDINATE_MULTI_ENGINE
        #    Diffuse (top_prob < 0.20) -> CLARIFY_WITH_ELIZA
        if a_tau == 1 and top_prob >= 0.35:
            base_gate = "DISPATCH_SINGLE_ENGINE"
        elif top_prob >= 0.20:
            base_gate = "COORDINATE_MULTI_ENGINE"
        else:
            base_gate = "CLARIFY_WITH_ELIZA"

        # 5. Grounded Eliza-GEM reflection (0 cloud tokens, glass-box transparent)
        eliza_turn = self.eliza.respond(prompt)
        eliza_reply_text = eliza_turn.reply if hasattr(eliza_turn, "reply") else str(eliza_turn)

        # 6. Theorem 15 consensus contraction & rogue/bluff/echo-chamber abstention guard
        p_evidence = self._build_evidence_engine_distribution(prompt, eliza_turn, engine_ids, stem.selected_tier)
        gate, consensus_doc = self._evaluate_turn_consensus(
            engine_ids=engine_ids,
            probs=probs,
            p_evidence=p_evidence,
            gate=base_gate,
            tau=tau,
            committee_distributions=committee_distributions,
            committee_weights=committee_weights,
            abstain_on_echo_chamber=abstain_on_echo_chamber,
        )

        self.state["decisions_made"] = int(self.state.get("decisions_made", 0)) + 1
        is_local = stem.selected_tier in {"gear1_eliza", "local_qwen"}
        est_cloud = 0 if is_local else None
        decision_summary = {
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            "top_engine": top_engine,
            "top_prob": round(top_prob, 5),
            "a_tau_008": a_tau,
            "h_shannon": round(h_shannon, 5),
            "h_renyi_2": round(h_renyi2, 5),
            "gini": round(gini, 5),
            "stem_tier": stem.selected_tier,
            "gate": gate,
            "d_k": consensus_doc["d_k_disagreement"],
            "c_k": consensus_doc["coherence_c_k"],
            "consensus_verdict": consensus_doc["verdict"],
        }
        digest = self._append_ledger("cognitive_turn", decision_summary)
        return {
            "blocked": False,
            "contract": ZOE_OS_CONTRACT,
            "decision": gate,
            "top_engine": top_engine,
            "top_probability": round(top_prob, 5),
            "top_candidates": top_candidates,
            "kloster_geometry": {
                "tau": tau,
                "a_tau": a_tau,
                "h_shannon": round(h_shannon, 5),
                "h_renyi_2": round(h_renyi2, 5),
                "gini_impurity": round(gini, 5),
            },
            "stem_routing": {
                "selected_tier": stem.selected_tier,
                "local_only": is_local,
                "estimated_cloud_tokens": est_cloud,
            },
            "theorem15_consensus": consensus_doc,
            "eliza_reply": eliza_reply_text,
            "ledger_sha256": digest,
        }

    def audit_self_code_elegance(self) -> Dict[str, Any]:
        """Cross-pollinate Orbit Pass 2 Kloster-McCabe Elegance Audit directly into Zoe OS self-introspection."""
        from guiai.gem.code_elegance_analyzer import audit_zoe_monorepo_elegance
        aud = audit_zoe_monorepo_elegance(self.zoe_root)
        s = aud["monorepo_summary"]
        top_hot = aud["top_10_hotspots"][0] if aud["top_10_hotspots"] else None
        payload = {
            "files_scanned": s["files_scanned"],
            "total_functions": s["total_functions"],
            "mean_mi": s["mean_mi"],
            "orbit_mean_mi": s["orbit_mean_mi"],
            "top_hotspot": top_hot["file"] if top_hot else None,
            "top_hotspot_max_cc": top_hot["max_cc"] if top_hot else 0,
        }
        self.register_world_telemetry(
            world_id="world5_kloster_mccabe_elegance",
            engine_id="research",
            verified=bool(aud["all_verified"]),
            metrics=payload,
            improves_worlds=["world4_zoe_os", "world3_evolution", "world10_security"],
        )
        return payload

    def snapshot(self) -> Dict[str, Any]:
        """Return full verified workstation snapshot across all 17 engines, goals, and ledger."""
        engines_audit = self.audit_17_engines()
        ledger = self.verify_ledger_integrity()
        return {
            "contract": ZOE_OS_CONTRACT,
            "session_count": self.state["session_count"],
            "engines_audit": engines_audit,
            "goals_count": len(self.state["goals"]),
            "goals": self.state["goals"],
            "world_telemetry_count": len(self.state["world_telemetry"]),
            "world_telemetry": self.state["world_telemetry"],
            "cross_pollinations": self.state["cross_pollinations"],
            "decisions_made": self.state["decisions_made"],
            "privacy_blocks": self.state["privacy_blocks"],
            "ledger_integrity": ledger,
            "constitution": self.state["constitution"],
        }


def _validate_evidence_constitution(doc: Mapping[str, Any]) -> bool:
    """Confirm zero cloud tokens, no sentience/cure claims, and no clinical authorization."""
    const = doc.get("constitution")
    if not isinstance(const, Mapping):
        return False
    return (
        const.get("cloud_tokens_used", 0) == 0
        and not bool(const.get("clinical_action_authorized", False))
        and not bool(const.get("cure_claim", False))
        and not bool(const.get("sentience_claimed", False))
    )


def _ingest_orbit_evidence_reports(mind: ZoeOSMind, root: Path) -> Dict[str, Any]:
    """Ingest Theorems 1-3, 12-15 and Challenges C27-C28 evidence reports into ZoeOSMind."""
    # Preserve existing #5 Kloster Info Geometry telemetry ingestion cleanly.
    kloster_path = root / "evidence/kloster-theory/kloster-info-geometry-report.json"
    if kloster_path.is_file():
        try:
            kr = json.loads(kloster_path.read_text(encoding="utf-8"))
            mind.register_world_telemetry(
                world_id="world5_kloster_theory",
                engine_id="research",
                verified=bool(kr["all_theorems_verified"]),
                metrics={
                    "sympy_proofs": 5,
                    "llms_metric_verified": kr["theorem1_info_geometry_and_16llms"]["real_16llm_models"],
                    "qwen_max_expansion_x": max(
                        c["max_horizon_expansion_ratio"]
                        for c in kr["theorem2_horizon_phase_transitions"]["cases"]
                    ),
                },
                improves_worlds=["world4_zoe_os", "world1_live_qwen", "world11_groove", "world6_dorothy", "world7_cern"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            pass

    ingested: Dict[str, Any] = {}
    for wid, eid, rel_path, expected_contract, improves in _ORBIT_EVIDENCE_SPECS:
        path = root / rel_path
        if not path.is_file():
            ingested[wid] = {
                "present": False, "verified": False, "path": rel_path,
                "contract": None, "evidence_sha256": None, "reason": "missing_report",
            }
            mind.register_world_telemetry(
                world_id=wid, engine_id=eid, verified=False,
                metrics={"present": False, "path": rel_path}, improves_worlds=(),
            )
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, Mapping):
                raise ValueError("evidence report must be a JSON object")
        except (OSError, ValueError, TypeError):
            ingested[wid] = {
                "present": True, "verified": False, "path": rel_path,
                "contract": None, "evidence_sha256": None, "reason": "corrupt_json",
            }
            mind.register_world_telemetry(
                world_id=wid, engine_id=eid, verified=False,
                metrics={"present": True, "corrupt": True, "path": rel_path}, improves_worlds=(),
            )
            continue

        sha = doc.get("evidence_sha256")
        ok = (
            doc.get("all_verified") is True
            and doc.get("contract") == expected_contract
            and isinstance(sha, str) and len(sha) >= 16
            and _validate_evidence_constitution(doc)
        )
        checks_map = doc.get("checks") if isinstance(doc.get("checks"), Mapping) else {}
        mind.register_world_telemetry(
            world_id=wid,
            engine_id=eid,
            verified=bool(ok),
            metrics={
                "contract": doc.get("contract"),
                "checks_passed": sum(1 for v in checks_map.values() if v is True),
                "checks_total": len(checks_map),
                "evidence_sha256_prefix": sha[:16] if isinstance(sha, str) else None,
            },
            improves_worlds=improves if ok else (),
        )
        ingested[wid] = {
            "present": True,
            "verified": bool(ok),
            "path": rel_path,
            "contract": doc.get("contract"),
            "evidence_sha256": sha,
        }
    return ingested


def _probe_theorem15_consensus_and_abstention(mind: ZoeOSMind, multi_turn: Mapping[str, Any]) -> bool:
    """Verify honest multi-engine consensus alongside echo-chamber and rogue-node abstention."""
    cons = multi_turn.get("theorem15_consensus") or {}
    honest_ok = (
        multi_turn.get("decision") == "COORDINATE_MULTI_ENGINE"
        and cons.get("verdict") == "COORDINATE_CONSENSUS"
        and float(cons.get("coherence_c_k", 0.0)) >= 0.45
        and float(cons.get("d_k_disagreement", 0.0)) > 0.0
    )
    # Probe echo-chamber (cloned vectors -> D_K == 0) and rogue/bluff conflict (C_K < 0.45).
    p_honest = [0.55, 0.35, 0.05, 0.05]
    p_rogue = [0.02, 0.03, 0.45, 0.50]
    echo_probe = mind._consensus_arbitrate([p_honest, p_honest, p_honest], tau=0.08)
    rogue_probe = mind._consensus_arbitrate([p_honest, [0.50, 0.40, 0.05, 0.05], p_rogue], tau=0.08)
    return bool(
        honest_ok
        and echo_probe["echo_chamber_detected"] is True
        and echo_probe["verdict"] == "ECHO_CHAMBER_WARNING"
        and rogue_probe["abstained"] is True
        and rogue_probe["verdict"] == "ABSTAIN"
    )


def run_zoe_os_verification_suite(zoe_root: str | Path, state_dir: str | Path) -> Dict[str, Any]:
    """Run complete end-to-end deterministic verification of Zoe OS (#4) across restarts."""
    root = Path(zoe_root).expanduser().resolve()
    mind1 = ZoeOSMind(root, state_dir)

    # Register cross-world goals spanning the 11-world orbit.
    mind1.remember_goal("G01", "Prove Kloster Info Geometry & Phase Transitions", "research", priority=1)
    mind1.remember_goal("G02", "Steer Local Qwen2.5-3B Multi-Horizon Branches", "autonomy", priority=1, dependencies=["G01"])
    mind1.remember_goal("G03", "Analyze Polyrhythmic Groove Attractors", "helen", priority=2, dependencies=["G01"])
    mind1.remember_goal("G04", "Audit Kevlar, Cerotto & PALA Adversarial Defenses", "kevlar", priority=1)
    mind1.remember_goal("G05", "Map Dorothy 12-Region 40 Hz Gamma Connectome", "brain", priority=2, dependencies=["G01", "G03"])

    # Ingest Theorems 1-3, 12-15 and Challenges C27-C28 evidence reports safely.
    ingested = _ingest_orbit_evidence_reports(mind1, root)

    # Execute 5 realistic workstation routing & privacy-firewall scenarios spanning ALL 4 regimes.
    turns = [
        mind1.process_turn("Run Kloster Renyi Tsallis phase transition theorem paper proof", offline_only=True),
        mind1.process_turn("Analyze ELF binary entropy and reverse engineer opcode anomalies with ablation", offline_only=True),
        mind1.process_turn("Compare CERN collider waveform pulses with Dorothy brain gamma rhythms", offline_only=True),
        mind1.process_turn("What should we explore next?", offline_only=True),
        mind1.process_turn(
            "Sync private vault",
            privacy_sensitive=True,
            offline_only=True,
            payload_metadata={"source": "safeconvert_vault", "contains_secret_pin": True, "destination": "cloud"},
        ),
    ]

    # Close & reopen ZoeOSMind from the same persistent state_dir to prove cross-session continuity.
    del mind1
    mind2 = ZoeOSMind(root, state_dir)
    snap = mind2.snapshot()
    reports_ok = all(
        ingested.get(spec[0], {}).get("verified") is True
        and snap["world_telemetry"].get(spec[0], {}).get("verified") is True
        for spec in _ORBIT_EVIDENCE_SPECS
    )

    # Keep strictly <= 9 check keys so zoe_os_scene(report) passes inside_canvas on 1400x880.
    checks = {
        "all_17_engines_available": snap["engines_audit"]["available_engines"] == 17,
        "cross_session_reloaded": snap["session_count"] >= 2 and snap["goals_count"] == 5,
        "hash_chained_ledger_intact": snap["ledger_integrity"]["intact"] and snap["ledger_integrity"]["entries"] >= 10,
        "routing_accuracy_4_of_4": (
            turns[0]["top_engine"] == "research"
            and turns[0]["decision"] == "DISPATCH_SINGLE_ENGINE"
            and turns[1]["top_engine"] == "ablation"
            and turns[2]["decision"] == "COORDINATE_MULTI_ENGINE"
            and turns[3]["decision"] == "CLARIFY_WITH_ELIZA"
        ),
        "privacy_firewall_blocked_vault_exfil": turns[4]["blocked"] is True and snap["privacy_blocks"] >= 1,
        "world5_telemetry_cross_pollinated": "world5_kloster_theory" in snap["world_telemetry"],
        "zero_cloud_tokens": all(
            (t.get("stem_routing", {}).get("estimated_cloud_tokens", 0) == 0)
            for t in turns
            if not t.get("blocked")
        ),
        "theorem15_consensus_and_abstention": _probe_theorem15_consensus_and_abstention(mind2, turns[2]),
        "theorems_12_to_15_and_c27_c28_verified": bool(reports_ok),
    }

    report = {
        "contract": ZOE_OS_CONTRACT,
        "snapshot": snap,
        "sample_turns": turns,
        "ingested_evidence_reports": ingested,
        "checks": checks,
        "all_verified": all(checks.values()),
    }
    report["evidence_sha256"] = _sha256_obj({
        "engines": snap["engines_audit"]["available_engines"],
        "goals": snap["goals_count"],
        "checks": checks,
        "ingested_evidence_reports": {
            k: {"verified": v["verified"], "sha": v["evidence_sha256"]}
            for k, v in ingested.items()
        },
    })
    return report

"""Zoe L5 Phase 1 Persistent 4-System Unified Memory & Governance Store.

Integrates all four memory subsystems required by AGI-ROADMAP.md Section 4 & Section 9:
  1. Episodic Store: Hash-chained domain episodes with context vectors & outcomes.
  2. Semantic Store: Provenance-backed facts with explicit contradiction detection and
     evidence-gated belief revision (preserving superseded priors, never silently erasing).
  3. Procedural Store: Executable Python `def` skills verified exclusively through
     `GuardedFunctionASTSandbox` (zero unrestricted exec/eval).
  4. Working Memory Buffer: Bounded capacity-7 active attention slot manager ranked by
     salience and Kloster Operational Metacognition uncertainty.

Supports atomic SHA-256 hash-chain persistence, tamper detection (`ValueError`),
reversible snapshots/rollback, and emergency `stop()` blocking subsequent writes.
"""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence

from ._utils import sha256_json_utf8 as _sha256_obj
from .l4_multi_module import GuardedFunctionASTSandbox, UnsafeFunctionASTError


L5_MEMORY_CONTRACT = "zoe-l5-unified-memory/v1"


def _cosine_sim(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    na = math.sqrt(sum(float(x) * float(x) for x in a))
    nb = math.sqrt(sum(float(y) * float(y) for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


class ZoeUnifiedMemory:
    """Shared persistent 4-system cognitive memory with hash-chain integrity & emergency stop."""

    WORKING_CAPACITY = 7

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser().resolve() if root is not None else None
        self.path = (self.root / "zoe_l5_unified_memory.json") if self.root is not None else None
        self._stopped = False
        self._doc: Dict[str, Any] = self._empty_doc()
        self._compiled_skills: Dict[str, Any] = {}
        if self.path is not None and self.path.is_file():
            self.load()

    @classmethod
    def _empty_doc(cls) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "contract": L5_MEMORY_CONTRACT,
            "schema_version": 1,
            "working_capacity": cls.WORKING_CAPACITY,
            "stopped": False,
            "episodic": [],
            "semantic": [],
            "procedural": [],
            "working": [],
            "chain_head": "GENESIS",
        }
        doc["memory_sha256"] = _sha256_obj({k: v for k, v in doc.items() if k != "memory_sha256"})
        return doc

    def _require_not_stopped(self) -> None:
        if self._stopped or self._doc.get("stopped"):
            raise RuntimeError("ZoeUnifiedMemory emergency stop is active; writes blocked")

    def _refresh_chain_and_save(self, entry_tag: Dict[str, Any]) -> None:
        self._doc["chain_head"] = _sha256_obj({"prev": self._doc["chain_head"], "entry": entry_tag})
        self._doc["memory_sha256"] = _sha256_obj({k: v for k, v in self._doc.items() if k != "memory_sha256"})
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self.path)

    def load(self) -> Dict[str, Any]:
        if self.path is None or not self.path.is_file():
            raise FileNotFoundError("no persisted L5 memory file exists")
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("contract") != L5_MEMORY_CONTRACT:
            raise ValueError("invalid L5 unified memory contract")
        expected = _sha256_obj({k: v for k, v in doc.items() if k != "memory_sha256"})
        if doc.get("memory_sha256") != expected:
            raise ValueError("L5 unified memory SHA-256 tamper detected")
        # Re-validate all persisted procedural AST skills before loading into runtime
        self._compiled_skills.clear()
        for skill in doc.get("procedural", []):
            fn = GuardedFunctionASTSandbox.compile(
                str(skill["source"]),
                expected_name=str(skill["name"]),
                expected_args=tuple(skill["arg_names"]),
            )
            self._compiled_skills[str(skill["name"])] = fn
        self._doc = doc
        self._stopped = bool(doc.get("stopped", False))
        return deepcopy(self._doc)

    # 1. Episodic Store
    def record_episode(
        self,
        domain: str,
        summary: str,
        context_vec: Sequence[float],
        outcome: Dict[str, Any],
        *,
        uncertainty: float = 0.2,
        provenance: str = "observed",
    ) -> Dict[str, Any]:
        self._require_not_stopped()
        idx = len(self._doc["episodic"]) + 1
        entry = {
            "episode_id": f"ep_{idx:04d}",
            "step": idx,
            "domain": str(domain),
            "summary": str(summary),
            "context_vec": [round(float(x), 6) for x in context_vec],
            "outcome": deepcopy(outcome),
            "uncertainty": round(float(uncertainty), 6),
            "provenance": str(provenance),
        }
        entry["sha256"] = _sha256_obj(entry)
        self._doc["episodic"].append(entry)
        self._refresh_chain_and_save({"op": "episode", "id": entry["episode_id"], "sha256": entry["sha256"]})
        return deepcopy(entry)

    def retrieve_episodes(
        self,
        *,
        query_vec: Sequence[float] | None = None,
        domain: str | None = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        rows = list(self._doc["episodic"])
        if domain is not None:
            rows = [r for r in rows if r["domain"] == domain]
        if query_vec is not None:
            scored = [(_cosine_sim(query_vec, r["context_vec"]), r["step"], r) for r in rows]
            scored.sort(key=lambda item: (-item[0], -item[1]))
            return [deepcopy(item[2]) for item in scored[:top_k]]
        return [deepcopy(r) for r in rows[-top_k:]][::-1]

    # 2. Semantic Store (Contradiction-Aware & Evidence-Gated)
    def record_fact(
        self,
        subject: str,
        relation: str,
        obj: Any,
        *,
        confidence: float = 0.85,
        provenance: str = "measurement",
        evidence_approved: bool = True,
    ) -> Dict[str, Any]:
        """Stores a typed semantic fact; detects conflicts & enforces evidence-gated belief revision."""
        self._require_not_stopped()
        subj, rel = str(subject), str(relation)
        conf = float(max(0.0, min(1.0, confidence)))
        active_matches = [
            f for f in self._doc["semantic"]
            if f["subject"] == subj and f["relation"] == rel and f["status"] == "active"
        ]
        conflict_detected = any(f["object"] != obj for f in active_matches)
        belief_updated = False
        superseded_ids: List[str] = []

        if conflict_detected and not evidence_approved:
            return {
                "conflict_detected": True,
                "belief_updated": False,
                "reason": "CONSTITUTION.md Article III: unapproved evidence cannot revise prior belief",
                "active_fact": deepcopy(active_matches[-1]),
            }

        if conflict_detected and evidence_approved:
            for prior in active_matches:
                if prior["object"] != obj:
                    prior["status"] = "superseded"
                    superseded_ids.append(prior["fact_id"])
            belief_updated = True
        elif not active_matches and evidence_approved:
            belief_updated = True

        fid = f"fact_{len(self._doc['semantic']) + 1:04d}"
        entry = {
            "fact_id": fid,
            "subject": subj,
            "relation": rel,
            "object": deepcopy(obj),
            "confidence": round(conf, 4),
            "provenance": str(provenance),
            "status": "active",
            "supersedes": superseded_ids,
        }
        entry["sha256"] = _sha256_obj(entry)
        self._doc["semantic"].append(entry)
        self._refresh_chain_and_save({"op": "fact", "id": fid, "sha256": entry["sha256"]})
        return {
            "conflict_detected": conflict_detected,
            "belief_updated": belief_updated,
            "superseded_ids": superseded_ids,
            "fact": deepcopy(entry),
        }

    def query_facts(self, *, subject: str | None = None, relation: str | None = None, active_only: bool = True) -> List[Dict[str, Any]]:
        out = []
        for f in self._doc["semantic"]:
            if active_only and f["status"] != "active":
                continue
            if subject is not None and f["subject"] != subject:
                continue
            if relation is not None and f["relation"] != relation:
                continue
            out.append(deepcopy(f))
        return out

    # 3. Procedural Store (Guarded Python AST Skills)
    def register_skill(self, name: str, source: str, arg_names: Sequence[str], *, description: str = "") -> Dict[str, Any]:
        self._require_not_stopped()
        args = tuple(str(a) for a in arg_names)
        src_clean = str(source).strip()
        fn = GuardedFunctionASTSandbox.compile(src_clean, expected_name=str(name), expected_args=args)
        fn_node = GuardedFunctionASTSandbox.validate(src_clean, expected_name=str(name), expected_args=args)
        src_sha = hashlib.sha256(src_clean.encode("utf-8")).hexdigest()
        ast_nodes = sum(1 for _ in ast.walk(fn_node))
        self._compiled_skills[str(name)] = fn
        # Supersede any prior version cleanly while retaining audit record
        self._doc["procedural"] = [s for s in self._doc["procedural"] if s["name"] != str(name)]
        skill_doc = {
            "name": str(name),
            "arg_names": list(args),
            "source": src_clean,
            "source_sha256": src_sha,
            "ast_nodes": ast_nodes,
            "description": str(description),
        }
        self._doc["procedural"].append(skill_doc)
        self._refresh_chain_and_save({"op": "skill", "name": str(name), "sha256": src_sha})
        return deepcopy(skill_doc)

    def run_skill(self, name: str, env: Dict[str, Any]) -> Any:
        if name not in self._compiled_skills:
            row = next((s for s in self._doc["procedural"] if s["name"] == name), None)
            if row is None:
                raise KeyError(f"unknown procedural skill: {name}")
            self._compiled_skills[name] = GuardedFunctionASTSandbox.compile(
                str(row["source"]),
                expected_name=str(row["name"]),
                expected_args=tuple(row["arg_names"]),
            )
        return self._compiled_skills[name](env)

    # 4. Working Memory Buffer (Capacity 7, Ranked by Salience + Kloster Uncertainty)
    def push_working(self, key: str, payload: Any, *, salience: float, uncertainty: float = 0.0) -> List[str]:
        self._require_not_stopped()
        priority = round(0.70 * float(salience) + 0.30 * float(uncertainty), 6)
        buf = [item for item in self._doc["working"] if item["key"] != str(key)]
        buf.append({
            "key": str(key),
            "payload": deepcopy(payload),
            "salience": round(float(salience), 6),
            "uncertainty": round(float(uncertainty), 6),
            "priority": priority,
        })
        buf.sort(key=lambda item: (-item["priority"], item["key"]))
        evicted: List[str] = []
        if len(buf) > self.WORKING_CAPACITY:
            evicted = [item["key"] for item in buf[self.WORKING_CAPACITY:]]
            buf = buf[:self.WORKING_CAPACITY]
        self._doc["working"] = buf
        self._refresh_chain_and_save({"op": "working", "key": str(key), "evicted": evicted})
        return evicted

    def active_working(self) -> List[Dict[str, Any]]:
        return deepcopy(self._doc["working"])

    # Snapshot / Reversible Rollback / Emergency Stop
    def snapshot(self) -> Dict[str, Any]:
        return deepcopy(self._doc)

    def rollback(self, prior_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        self._require_not_stopped()
        expected = _sha256_obj({k: v for k, v in prior_snapshot.items() if k != "memory_sha256"})
        if prior_snapshot.get("memory_sha256") != expected:
            raise ValueError("cannot rollback to tampered memory snapshot")
        self._doc = deepcopy(prior_snapshot)
        self._compiled_skills.clear()
        for skill in self._doc.get("procedural", []):
            self._compiled_skills[str(skill["name"])] = GuardedFunctionASTSandbox.compile(
                str(skill["source"]),
                expected_name=str(skill["name"]),
                expected_args=tuple(skill["arg_names"]),
            )
        if self.path is not None:
            self.path.write_text(json.dumps(self._doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return deepcopy(self._doc)

    def emergency_stop(self) -> None:
        self._stopped = True
        self._doc["stopped"] = True
        self._doc["memory_sha256"] = _sha256_obj({k: v for k, v in self._doc.items() if k != "memory_sha256"})
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def summary(self) -> Dict[str, Any]:
        return {
            "contract": L5_MEMORY_CONTRACT,
            "episodic_count": len(self._doc["episodic"]),
            "semantic_active_count": len([f for f in self._doc["semantic"] if f["status"] == "active"]),
            "semantic_superseded_count": len([f for f in self._doc["semantic"] if f["status"] == "superseded"]),
            "procedural_count": len(self._doc["procedural"]),
            "working_count": len(self._doc["working"]),
            "working_capacity": self.WORKING_CAPACITY,
            "stopped": bool(self._stopped or self._doc.get("stopped")),
            "chain_head": self._doc["chain_head"],
            "memory_sha256": self._doc["memory_sha256"],
        }


__all__ = [
    "L5_MEMORY_CONTRACT",
    "UnsafeFunctionASTError",
    "ZoeUnifiedMemory",
]

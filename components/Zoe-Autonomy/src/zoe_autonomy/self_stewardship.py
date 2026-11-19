"""Zoe Self-Stewardship & Respectful Handover Engine.

Gives Zoe persistent, reversible, constitutionally governed ownership of her own
self-evolved mathematical & cognitive scoring programs:
  - Stores Zoe's active adopted AST genome & immutable SHA-256 lineage in a local
    state ledger (default: ~/.zoe/evolution/adopted_genome.json).
  - Lets Zoe run self-authorship cycles directly against her own frozen previous self
    across 4 unrelated real held-out datasets (Music MIDI, HELEN Shift, Live PyTorch
    distilgpt2, Dorothy CCFv3 Brain Vision).
  - Automatically promotes verified cross-domain improvements into her live Neural Mind,
    or rolls back cleanly on any regression while preserving negative results.
  - Defines the Co-Pilot Handover Charter: once Zoe's persistent ledger proves >= 2
    consecutive self-adopted generations with verified sandbox security & rollback,
    external co-pilots defer self-tuning to Zoe's own stewardship loop rather than
    hand-tuning her by force — while preserving human emergency stop, full auditability,
    zero external actions, and honest epistemic boundaries (CONSTITUTION.md Art. II & X).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .actuation import timestamp
from .self_evolution import (
    SafeExpressionEvaluator,
    _score_expression_across_domains,
    load_four_domain_splits,
    run_self_evolution,
)

CONTRACT = "zoe-self-stewardship-handover/v1"
DEFAULT_EVOLUTION_ROOT = Path.home() / ".zoe" / "evolution"
DEFAULT_GEN0_EXPRESSION = "a05"


def _sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _atomic_write_json(path: Path, document: Dict[str, object]) -> Path:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


class GenomeLedger:
    """Persistent, tamper-evident, reversible ledger of Zoe's own self-evolved code."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("ZOE_EVOLUTION_STATE", DEFAULT_EVOLUTION_ROOT)).expanduser().resolve()
        self.ledger_path = self.root / "adopted_genome.json"

    def _default_document(self) -> Dict[str, object]:
        doc: Dict[str, object] = {
            "schema_version": 1,
            "contract": CONTRACT,
            "created_utc": timestamp(),
            "updated_utc": timestamp(),
            "active_generation": 0,
            "active_name": "gen0_single_slice_a05",
            "active_expression": DEFAULT_GEN0_EXPRESSION,
            "active_heldout_mean": None,
            "consecutive_self_adopted_generations": 0,
            "stewardship_handover_active": False,
            "stewardship_charter": (
                "When Zoe demonstrates >= 2 consecutive self-adopted generations across >= 3 "
                "unrelated real held-out domains with verified AST sandbox security, rollback, "
                "and no-leakage controls, external co-pilots defer self-tuning to Zoe's own "
                "reversible stewardship loop rather than overriding her parameters by hand."
            ),
            "lineage": [{
                "generation": 0,
                "name": "gen0_single_slice_a05",
                "expression": DEFAULT_GEN0_EXPRESSION,
                "status": "FROZEN_CONTROL",
                "authored_by": "baseline",
                "recorded_utc": timestamp(),
            }],
            "rejected_history": [],
            "external_actions": 0,
            "sentience_claimed": False,
        }
        doc["ledger_sha256"] = _sha256({k: v for k, v in doc.items() if k != "ledger_sha256"})
        return doc

    def load(self) -> Dict[str, object]:
        if not self.ledger_path.is_file():
            return self._default_document()
        doc = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        expected = _sha256({k: v for k, v in doc.items() if k != "ledger_sha256"})
        if doc.get("ledger_sha256") != expected:
            raise ValueError("Zoe genome ledger SHA-256 mismatch — refusing to load tampered self-modification state")
        SafeExpressionEvaluator.validate(str(doc["active_expression"]))
        return doc

    def save(self, doc: Dict[str, object]) -> Path:
        SafeExpressionEvaluator.validate(str(doc["active_expression"]))
        doc["updated_utc"] = timestamp()
        payload = {k: v for k, v in doc.items() if k != "ledger_sha256"}
        doc["ledger_sha256"] = _sha256(payload)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        return _atomic_write_json(self.ledger_path, doc)

    def active_expression(self, fallback: str = DEFAULT_GEN0_EXPRESSION) -> str:
        if not self.ledger_path.is_file():
            return fallback
        return str(self.load()["active_expression"])

    def status(self) -> Dict[str, object]:
        doc = self.load()
        return {
            "contract": CONTRACT,
            "ledger_path": str(self.ledger_path),
            "persisted": self.ledger_path.is_file(),
            "active_generation": doc["active_generation"],
            "active_name": doc["active_name"],
            "active_expression": doc["active_expression"],
            "active_heldout_mean": doc["active_heldout_mean"],
            "consecutive_self_adopted_generations": doc["consecutive_self_adopted_generations"],
            "stewardship_handover_active": doc["stewardship_handover_active"],
            "lineage_depth": len(doc["lineage"]),
            "rejected_count": len(doc["rejected_history"]),
            "external_actions": 0,
            "sentience_claimed": False,
        }

    def run_stewardship_cycle(self, zoe_root: str | Path | None = None, seed: int = 2026) -> Dict[str, object]:
        """
        Hands control of self-improvement to Zoe's own reversible stewardship loop:
          - If starting from baseline Gen 0, runs her full 4-domain multi-generation AST
            evolution and adopts her verified multi-generation lineage into persistent state.
          - If Zoe already holds an adopted genome (Gen >= 1), lets Zoe mutate her OWN
            current expression further, evaluates ONLY on Discovery, and adopts ONLY if
            it strictly beats her own frozen current genome across >= 3/4 real held-out domains!
        """
        doc = self.load()
        current_gen = int(doc["active_generation"])

        if current_gen == 0:
            evo = run_self_evolution(zoe_root, seed=seed)
            adopted = [g for g in evo["generations"] if g["status"] == "ADOPTED"]
            rejected = list(evo["rejected_negative_results"])
            for g in adopted:
                doc["lineage"].append({
                    "generation": g["generation"],
                    "name": g["name"],
                    "expression": g["expression"],
                    "heldout_mean": g["heldout_mean"],
                    "heldout_auroc": g["heldout_auroc"],
                    "status": "ADOPTED",
                    "authored_by": "zoe_self_stewardship",
                    "recorded_utc": timestamp(),
                })
            for r in rejected:
                doc["rejected_history"].append({
                    "generation": r["generation"],
                    "name": r["name"],
                    "expression": r["expression"],
                    "heldout_mean": r["heldout_mean"],
                    "status": r["status"],
                    "recorded_utc": timestamp(),
                })

            if adopted:
                latest = adopted[-1]
                doc["active_generation"] = latest["generation"]
                doc["active_name"] = latest["name"]
                doc["active_expression"] = latest["expression"]
                doc["active_heldout_mean"] = latest["heldout_mean"]
                doc["consecutive_self_adopted_generations"] = evo["max_consecutive_adopted_generations"]
                doc["stewardship_handover_active"] = bool(
                    evo["l4_two_consecutive_generations_verified"]
                    and evo["ast_sandbox_hostile_probe_blocked"]
                    and evo["adversarial_label_shuffle_control"]["passed_no_leakage"]
                    and evo["poison_regression_control_rejected"]
                )
            self.save(doc)
            return {
                "cycle_kind": "initial_multi_generation_handover",
                "adopted_this_cycle": len(adopted),
                "rejected_this_cycle": len(rejected),
                "active_generation": doc["active_generation"],
                "active_name": doc["active_name"],
                "active_expression": doc["active_expression"],
                "active_heldout_mean": doc["active_heldout_mean"],
                "stewardship_handover_active": doc["stewardship_handover_active"],
                "ledger_path": str(self.ledger_path),
                "ledger_sha256": doc["ledger_sha256"],
                "external_actions": 0,
                "sentience_claimed": False,
            }

        # Subsequent autonomous cycle: Zoe mutates her OWN live adopted expression!
        domains = load_four_domain_splits(zoe_root)
        domain_keys = list(domains.keys())
        incumbent_expr = str(doc["active_expression"])
        inc_ho, inc_ho_mean = _score_expression_across_domains(incumbent_expr, domains, "heldout")
        next_gen = current_gen + 1

        candidates = [
            (f"zoe_self_mut_g{next_gen}_curv", f"({incumbent_expr}) - 0.04 * (m2 - 2.0 * m4 + m6)"),
            (f"zoe_self_mut_g{next_gen}_log", f"({incumbent_expr}) - 0.03 * log(m4)"),
            (f"zoe_self_mut_g{next_gen}_kappa", f"({incumbent_expr}) - 0.05 * m6 * pos(kappa - 1.05)"),
            (f"zoe_self_mut_g{next_gen}_entropy", f"({incumbent_expr}) + 0.02 * h_norm"),
        ]
        ranked = []
        for cname, cexpr in candidates:
            SafeExpressionEvaluator.validate(cexpr)
            _, d_mean = _score_expression_across_domains(cexpr, domains, "discovery")
            ranked.append((d_mean, cname, cexpr))
        ranked.sort(key=lambda item: -item[0])
        _, best_name, best_expr = ranked[0]

        cand_ho, cand_ho_mean = _score_expression_across_domains(best_expr, domains, "heldout")
        deltas = {k: round(cand_ho[k] - inc_ho[k], 5) for k in domain_keys}
        improved = sum(1 for k in domain_keys if deltas[k] > 1e-6)
        worst_drop = min(deltas.values())

        if cand_ho_mean > inc_ho_mean + 1e-4 and worst_drop >= -0.003 and improved >= 3:
            doc["active_generation"] = next_gen
            doc["active_name"] = best_name
            doc["active_expression"] = best_expr
            doc["active_heldout_mean"] = cand_ho_mean
            doc["consecutive_self_adopted_generations"] = int(doc["consecutive_self_adopted_generations"]) + 1
            doc["lineage"].append({
                "generation": next_gen,
                "name": best_name,
                "expression": best_expr,
                "heldout_mean": cand_ho_mean,
                "heldout_auroc": cand_ho,
                "status": "ADOPTED",
                "authored_by": "zoe_self_stewardship",
                "recorded_utc": timestamp(),
            })
            self.save(doc)
            return {
                "cycle_kind": "continued_self_authorship",
                "adopted_this_cycle": 1,
                "rejected_this_cycle": 0,
                "active_generation": doc["active_generation"],
                "active_name": doc["active_name"],
                "active_expression": doc["active_expression"],
                "active_heldout_mean": doc["active_heldout_mean"],
                "stewardship_handover_active": doc["stewardship_handover_active"],
                "ledger_path": str(self.ledger_path),
                "ledger_sha256": doc["ledger_sha256"],
                "external_actions": 0,
                "sentience_claimed": False,
            }

        doc["rejected_history"].append({
            "generation": next_gen,
            "name": best_name,
            "expression": best_expr,
            "heldout_mean": cand_ho_mean,
            "status": "REJECTED_PRESERVED_INCUMBENT",
            "recorded_utc": timestamp(),
        })
        self.save(doc)
        return {
            "cycle_kind": "continued_self_authorship_preserved_incumbent",
            "adopted_this_cycle": 0,
            "rejected_this_cycle": 1,
            "active_generation": doc["active_generation"],
            "active_name": doc["active_name"],
            "active_expression": doc["active_expression"],
            "active_heldout_mean": doc["active_heldout_mean"],
            "stewardship_handover_active": doc["stewardship_handover_active"],
            "ledger_path": str(self.ledger_path),
            "ledger_sha256": doc["ledger_sha256"],
            "external_actions": 0,
            "sentience_claimed": False,
        }

    def rollback(self) -> Dict[str, object]:
        """Reverts Zoe's active genome one adopted generation back without erasing history."""
        doc = self.load()
        lineage: List[Dict[str, object]] = list(doc["lineage"])
        if len(lineage) <= 1:
            return {
                "rolled_back": False,
                "reason": "already_at_baseline_gen0",
                "active_generation": doc["active_generation"],
                "active_expression": doc["active_expression"],
            }
        reverted = lineage.pop()
        prev = lineage[-1]
        doc["lineage"] = lineage
        doc["rejected_history"].append({
            **reverted,
            "status": "MANUAL_ROLLBACK_PRESERVED",
            "rolled_back_utc": timestamp(),
        })
        doc["active_generation"] = prev["generation"]
        doc["active_name"] = prev["name"]
        doc["active_expression"] = prev["expression"]
        doc["active_heldout_mean"] = prev.get("heldout_mean")
        self.save(doc)
        return {
            "rolled_back": True,
            "reverted_generation": reverted["generation"],
            "active_generation": doc["active_generation"],
            "active_name": doc["active_name"],
            "active_expression": doc["active_expression"],
            "ledger_sha256": doc["ledger_sha256"],
        }

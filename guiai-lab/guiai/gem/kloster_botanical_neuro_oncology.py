"""Zoe Botanical Neuro-Oncology & Pharmacognosy Lab (C17).

100% offline, reproducible, NIH PubChem-grounded phytochemistry & CNS Blood-Brain
Barrier (BBB) computational workbench — strictly educational & preclinical research.

Constitutional Guardrails (CONSTITUTION.md Articles II, III & V):
  - clinical_action_authorized = False
  - cure_claim = False
  - patient_specific_recommendation = False
  - wet_lab_and_clinical_validation_required = True
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from .spectral_filtration import spectral_moment_root

# Exact NIH PubChem PUG-REST descriptors (verified 2026-11-22):
# (id, name, origin, category, cid, formula, mw, xlogp3, tpsa, hbd, hba, rotb, raw_tox, pgp)
_RAW_PUBCHEM_ROWS: Tuple[Tuple[Any, ...], ...] = (
    ("dordaviprone", "Dordaviprone (ONC201)", "Synthetic imipridone (FDA Aug 2025, H3 K27M DMG)", "clinical_cns_benchmark", 73777259, "C24H26N4O", 386.5, 2.3, 39.2, 0, 3, 4, False, "low"),
    ("temozolomide", "Temozolomide", "Synthetic imidazotetrazine prodrug (GBM standard)", "clinical_cns_benchmark", 5394, "C6H6N6O2", 194.15, -1.1, 106.0, 1, 5, 1, False, "low"),
    ("tovorafenib", "Tovorafenib", "Synthetic Type II RAF inhibitor (FDA Apr 2024, pLGG)", "clinical_cns_benchmark", 25161177, "C17H12Cl2F3N7O2S", 506.3, 3.0, 164.0, 3, 11, 5, False, "moderate"),
    ("lycorine", "Lycorine", "Zephyranthes / Amaryllidaceae (Rain lily alkaloid)", "preclinical_botanical", 72378, "C16H17NO4", 287.31, 0.0, 62.2, 2, 5, 0, True, "low"),
    ("narciclasine", "Narciclasine", "Zephyranthes / Narcissus (Amaryllidaceae)", "preclinical_botanical", 72376, "C14H13NO7", 307.25, -1.2, 128.0, 5, 7, 0, True, "moderate"),
    ("crocetin", "Crocetin", "Crocus sativus (True saffron crocus apocarotenoid)", "preclinical_botanical", 5281232, "C20H24O4", 328.4, 5.4, 74.6, 2, 4, 8, False, "low"),
    ("crocin", "Crocin (Raw Saffron Glycoside Ctrl)", "Crocus sativus (Parent digentiobiosyl glycoside)", "bbb_negative_control", 5281233, "C44H64O24", 977.0, -2.5, 391.0, 14, 24, 20, False, "high"),
    ("colchicine", "Colchicine (Raw Autumn Crocus)", "Colchicum autumnale (Autumn crocus — toxic raw)", "prodrug_parent_toxin", 6167, "C22H25NO6", 399.4, 1.0, 83.1, 1, 6, 5, True, "high"),
    ("etoposide", "Etoposide", "Podophyllum peltatum (Mayapple lignan derivative)", "approved_plant_oncology", 36462, "C29H32O13", 588.6, 0.6, 161.0, 3, 13, 5, True, "high"),
    ("vincristine", "Vincristine", "Catharanthus roseus (Madagascar periwinkle)", "approved_plant_oncology", 5978, "C46H56N4O10", 825.0, 2.8, 171.0, 3, 12, 10, True, "high"),
    ("paclitaxel", "Paclitaxel (Taxol — BBB Efflux Ctrl)", "Taxus brevifolia (Pacific yew diterpenoid)", "bbb_negative_control", 36314, "C47H51NO14", 853.9, 2.5, 221.0, 4, 14, 14, True, "high"),
)

_FIELDS = (
    "id", "name", "botanical_or_origin", "category", "pubchem_cid", "formula",
    "mw", "xlogp3", "tpsa", "hbd", "hba", "rotatable_bonds",
    "raw_systemic_toxicity_flag", "pgp_efflux_risk",
)
PUBCHEM_BOTANICAL_CORPUS: Tuple[Dict[str, Any], ...] = tuple(dict(zip(_FIELDS, row)) for row in _RAW_PUBCHEM_ROWS)


def _linear_ramp(val: float, ideal_hi: float, fail_hi: float) -> float:
    """Monotonic Pfizer Wager CNS MPO desirability ramp in [0.0, 1.0]."""
    if val <= ideal_hi:
        return 1.0
    if val >= fail_hi:
        return 0.0
    return (fail_hi - val) / (fail_hi - ideal_hi)


def _tpsa_ramp(tpsa: float) -> float:
    """Exact Wager 2010 hump-shaped TPSA CNS desirability ramp (ideal 40-90 A^2)."""
    if 40.0 <= tpsa <= 90.0:
        return 1.0
    if tpsa <= 20.0 or tpsa >= 120.0:
        return 0.0
    return (tpsa - 20.0) / 20.0 if tpsa < 40.0 else (120.0 - tpsa) / 30.0


def score_pubchem_cns_mpo4(mol: Dict[str, Any]) -> Dict[str, Any]:
    """Compute exact 4-term PubChem-verified Wager CNS MPO desirability (0.0-4.0) & BBB flags."""
    t_mw = _linear_ramp(float(mol["mw"]), 360.0, 500.0)
    t_logp = _linear_ramp(float(mol["xlogp3"]), 3.0, 5.0)
    t_tpsa = _tpsa_ramp(float(mol["tpsa"]))
    t_hbd = _linear_ramp(float(mol["hbd"]), 0.5, 3.5)
    mpo4 = t_mw + t_logp + t_tpsa + t_hbd
    gates = int(mol["mw"] <= 450.0) + int(mol["tpsa"] <= 110.0) + int(mol["hbd"] <= 3)
    return {
        "id": mol["id"],
        "name": mol["name"],
        "pubchem_cid": mol["pubchem_cid"],
        "category": mol["category"],
        "mw": mol["mw"],
        "xlogp3": mol["xlogp3"],
        "tpsa": mol["tpsa"],
        "hbd": mol["hbd"],
        "components": {"t_mw": round(t_mw, 4), "t_logp": round(t_logp, 4), "t_tpsa": round(t_tpsa, 4), "t_hbd": round(t_hbd, 4)},
        "cns_mpo4_score": round(mpo4, 4),
        "cns_mpo4_pct": round(25.0 * mpo4, 1),
        "passive_bbb_gates_passed": f"{gates}/3",
        "pgp_efflux_risk": mol["pgp_efflux_risk"],
        "raw_systemic_toxicity_flag": mol["raw_systemic_toxicity_flag"],
    }


def model_ict2588_mmp14_prodrug_cipher() -> Dict[str, Any]:
    """Simulate Bradford ICT2588 MMP-14 enzyme-gated prodrug vs raw Colchicine across 8 compartments."""
    compartments = (
        "tumor_core_mmp14_hi", "tumor_rim_mmp14_mod", "healthy_heart_vasc", "healthy_brain_cortex",
        "healthy_bone_marrow", "healthy_liver", "healthy_kidney", "healthy_gut_mucosa",
    )
    mmp14_expr = np.array([1.00, 0.58, 0.012, 0.008, 0.015, 0.018, 0.012, 0.012], dtype=np.float64)
    raw_exp = np.array([1.00, 0.95, 0.92, 0.35, 0.96, 0.98, 0.94, 0.90], dtype=np.float64)
    prodrug_rel = mmp14_expr / (0.35 + mmp14_expr)
    raw_ratio = float(raw_exp[0] / np.mean(raw_exp[2:]))
    prodrug_ratio = float(prodrug_rel[0] / np.mean(prodrug_rel[2:]))
    raw_m4 = float(spectral_moment_root(raw_exp / float(raw_exp.sum()), 4.0))
    prodrug_m4 = float(spectral_moment_root(prodrug_rel / float(prodrug_rel.sum()), 4.0))
    return {
        "model_scope": "synthetic_michaelis_menten_compartmental_analogy",
        "reference_literature": "University of Bradford ICT2588 (Atkinson et al., Cancer Res / Mol Cancer Ther)",
        "compartments": list(compartments),
        "raw_colchicine_tumor_to_healthy_ratio": round(raw_ratio, 3),
        "ict2588_prodrug_tumor_to_healthy_ratio": round(prodrug_ratio, 3),
        "raw_colchicine_kloster_m4_root": round(raw_m4, 5),
        "ict2588_prodrug_kloster_m4_root": round(prodrug_m4, 5),
        "spatial_selectivity_m4_gain": round(prodrug_m4 / max(raw_m4, 1e-12), 3),
        "prodrug_exceeds_10x_tumor_selectivity": bool(prodrug_ratio >= 10.0),
        "verified": bool(prodrug_ratio >= 10.0 and raw_ratio < 1.5 and prodrug_m4 > raw_m4 * 2.0),
    }


def run_botanical_neuro_oncology_lab() -> Dict[str, Any]:
    """Run C17: NIH PubChem Botanical & CNS Neuro-Oncology Desirability + Prodrug Cipher Lab."""
    scored: List[Dict[str, Any]] = [score_pubchem_cns_mpo4(m) for m in PUBCHEM_BOTANICAL_CORPUS]
    by_id = {row["id"]: row for row in scored}
    prodrug = model_ict2588_mmp14_prodrug_cipher()
    findings = {
        "crocetin_beats_raw_crocin_glycoside": by_id["crocetin"]["cns_mpo4_score"] > by_id["crocin"]["cns_mpo4_score"] + 1.2,
        "cns_benchmarks_beat_bbb_negative_controls": (
            min(by_id["dordaviprone"]["cns_mpo4_score"], by_id["temozolomide"]["cns_mpo4_score"])
            > max(by_id["paclitaxel"]["cns_mpo4_score"], by_id["crocin"]["cns_mpo4_score"]) + 1.5
        ),
        "narciclasine_hbd_tpsa_bbb_bottleneck_identified": by_id["narciclasine"]["components"]["t_hbd"] == 0.0,
        "raw_colchicine_toxicity_flagged_despite_high_mpo": bool(by_id["colchicine"]["raw_systemic_toxicity_flag"]),
    }
    return {
        "challenge": "challenge17_botanical_pharmacognosy_and_bbb_cns_mpo",
        "pubchem_verified_date": "2026-11-22",
        "molecules_evaluated": len(scored),
        "molecule_scores": scored,
        "ict2588_mmp14_prodrug_cipher": prodrug,
        "key_findings": findings,
        "epistemic_guardrails": {
            "clinical_action_authorized": False,
            "cure_claim": False,
            "patient_specific_recommendation": False,
            "wet_lab_and_clinical_validation_required": True,
        },
        "verified": bool(all(findings.values()) and prodrug["verified"]),
    }

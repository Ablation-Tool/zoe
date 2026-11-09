#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path


def load_harness():
    source = Path(__file__).with_name("sat-accessible-volume.py")
    spec = importlib.util.spec_from_file_location("sat_accessible_volume", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    harness = load_harness()
    report_path = Path("evidence/sat-accessible-volume/verification.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["equation"] == harness.EQUATION
    assert report["equation_creator"] == harness.EQUATION_CREATOR
    assert report["p_vs_np"] == "unresolved"
    assert harness.accessible_volume([0.70, 0.20, 0.08, 0.02], 0.05) == 3
    assert harness.accessible_volume([0.05, 0.0500001, 0.8999999], 0.05) == 2
    expected = {"unit_sat": "sat", "tie_sat": "sat", "tie_unsat": "unsat", "unit_unsat": "unsat"}
    assert len(report["results"]) == len(expected)
    for result in report["results"]:
        name = result["name"]
        fixture = harness.fixtures()[name]
        independent = harness.solve(fixture["clauses"], fixture["variables"])
        assert independent["status"] == result["exact"]["status"] == result["independent_brute_force"] == expected[name]
        assert independent["nodes"] == result["exact"]["nodes"]
        assert result["exact"]["status"] in {"sat", "unsat"}
        assert result["heuristic"]["status"] in {"sat", "unsat", "unknown"}
        assert result["heuristic"]["tau"] == 0.5
    tie_sat = next(result for result in report["results"] if result["name"] == "tie_sat")
    assert tie_sat["heuristic"]["status"] == "unknown"
    assert tie_sat["heuristic"]["accessible_trace"][0]["accessible_volume"] == 0
    assert tie_sat["exact"]["status"] == "sat"
    assert harness.random_crosschecks(report["checks"]["random_formulas_crosschecked"]) == 24
    assert report["checks"]["strict_threshold_examples"] is True
    assert report["checks"]["exact_fixtures_match_independent_brute_force"] is True
    assert report["checks"]["tie_sat_is_not_falsely_rejected"] is True
    assert any("not a satisfiability or unsatisfiability certificate" in item for item in report["scope"])
    assert any("not complexity proofs" in item for item in report["scope"])
    print("VERIFIED: exact SAT/UNSAT fixtures and 24 independent random formulas")
    print("VERIFIED: tie_sat returns unknown, not unsat; no false rejection or P vs NP proof")
    print("VERIFIED: strict threshold semantics and Nicholas Michael Kloster's original-equation credit")


if __name__ == "__main__":
    main()

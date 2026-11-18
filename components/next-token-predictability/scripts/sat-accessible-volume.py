#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
from itertools import product
import json
import math
from pathlib import Path
import random

EQUATION = "A_tau(S) = sum over tokens a in O of 1[P(a | h_T(S)) > tau]"
EQUATION_CREATOR = "Nicholas Michael Kloster alone, March 6, 2026"


def accessible_volume(probabilities, tau):
    if not math.isfinite(tau) or not 0 <= tau <= 1:
        raise ValueError("tau must be in [0, 1]")
    values = list(probabilities)
    if not values or any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("probabilities must be finite values in [0, 1]")
    if not math.isclose(sum(values), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("probabilities must sum to one")
    return sum(value > tau for value in values)


def clause_satisfied(clause, assignment):
    return any(assignment.get(abs(literal)) == (literal > 0) for literal in clause)


def propagate(clauses, assignment):
    current = dict(assignment)
    while True:
        unsatisfied = [clause for clause in clauses if not clause_satisfied(clause, current)]
        if any(all(abs(literal) in current for literal in clause) for clause in unsatisfied):
            return None
        unit = next((clause for clause in unsatisfied
                     if sum(abs(literal) not in current for literal in clause) == 1), None)
        if unit is None:
            return current
        literal = next(literal for literal in unit if abs(literal) not in current)
        current[abs(literal)] = literal > 0


def literal_probabilities(clauses, assignment, variable):
    scores = {}
    for positive in (False, True):
        scores[positive] = sum(
            1 / (1 << len(clause))
            for clause in clauses
            if not clause_satisfied(clause, assignment)
            and any(literal == (variable if positive else -variable) for literal in clause)
        )
    total = scores[False] + scores[True]
    if total == 0:
        return [0.5, 0.5]
    return [scores[False] / total, scores[True] / total]


def solve(clauses, variables, tau=None, node_budget=200_000):
    if not 1 <= variables <= 16:
        raise ValueError("variables must be between 1 and 16")
    normalized = []
    for clause in clauses:
        if not clause or any(not isinstance(literal, int) or literal == 0 or abs(literal) > variables
                             for literal in clause):
            raise ValueError("invalid clause")
        if len({abs(literal) for literal in clause}) != len(clause):
            raise ValueError("repeated variable in clause")
        if len(set(clause)) != len(clause):
            raise ValueError("complementary literals in clause")
        normalized.append(tuple(clause))
    nodes = 0
    trace = []

    def search(assignment):
        nonlocal nodes
        nodes += 1
        if nodes > node_budget:
            raise ValueError("search node budget exceeded")
        current = propagate(normalized, assignment)
        if current is None:
            return False
        if all(clause_satisfied(clause, current) for clause in normalized):
            return current
        clause = next(clause for clause in normalized if not clause_satisfied(clause, current))
        variable = min(abs(literal) for literal in clause if abs(literal) not in current)
        if tau is None:
            candidates = (False, True)
        else:
            probabilities = literal_probabilities(normalized, current, variable)
            volume = accessible_volume(probabilities, tau)
            trace.append({"variable": variable, "accessible_volume": volume})
            if volume == 0:
                return None
            candidates = [positive for positive in (False, True) if probabilities[int(positive)] > tau]
            candidates.sort(key=lambda positive: probabilities[int(positive)], reverse=True)
        unknown = False
        for positive in candidates:
            result = search({**current, variable: positive})
            if result is None:
                unknown = True
            elif result is not False:
                return result
        return None if unknown else False

    result = search({})
    return {
        "status": "unknown" if result is None else ("sat" if result else "unsat"),
        "nodes": nodes,
        "accessible_trace": trace,
    }


def brute_force(clauses, variables):
    for values in product((False, True), repeat=variables):
        assignment = dict(zip(range(1, variables + 1), values))
        if all(clause_satisfied(clause, assignment) for clause in clauses):
            return "sat"
    return "unsat"


def fixtures():
    return {
        "unit_sat": {
            "variables": 3,
            "clauses": ((1,), (1, 2, 3), (-1, 2, -3)),
        },
        "tie_sat": {
            "variables": 3,
            "clauses": ((1, 2, 3), (-1, 2, -3), (1, -2, 3), (-1, -2, -3)),
        },
        "tie_unsat": {
            "variables": 3,
            "clauses": tuple(tuple(literal * variable for literal, variable in zip(signs, (1, 2, 3)))
                             for signs in product((-1, 1), repeat=3)),
        },
        "unit_unsat": {
            "variables": 1,
            "clauses": ((1,), (-1,)),
        },
    }


def random_crosschecks(count=24, variables=6, seed=20261108):
    if not 0 <= count <= 64 or not 1 <= variables <= 8:
        raise ValueError("invalid random crosscheck bounds")
    generator = random.Random(seed)
    checked = 0
    for _ in range(count):
        clauses = []
        for _ in range(generator.randint(4, 16)):
            selected = sorted(generator.sample(range(1, variables + 1), 3))
            clauses.append(tuple(variable * generator.choice((-1, 1)) for variable in selected))
        assert solve(clauses, variables)["status"] == brute_force(clauses, variables)
        checked += 1
    return checked


def run(output, tau=0.5, random_checks=24):
    if not math.isfinite(tau) or not 0 <= tau <= 1:
        raise ValueError("tau must be in [0, 1]")
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    assert accessible_volume([0.70, 0.20, 0.08, 0.02], 0.05) == 3
    assert accessible_volume([0.05, 0.0500001, 0.8999999], 0.05) == 2
    results = []
    for name, fixture in fixtures().items():
        variables = fixture["variables"]
        clauses = fixture["clauses"]
        exact = solve(clauses, variables)
        heuristic = solve(clauses, variables, tau=tau)
        results.append({
            "name": name,
            "variables": variables,
            "clauses": [list(clause) for clause in clauses],
            "independent_brute_force": brute_force(clauses, variables),
            "exact": exact,
            "heuristic": {"tau": tau, **heuristic},
        })
    expected = {"unit_sat": "sat", "tie_sat": "sat", "tie_unsat": "unsat", "unit_unsat": "unsat"}
    for result in results:
        assert result["exact"]["status"] == result["independent_brute_force"] == expected[result["name"]]
    tie_sat = next(result for result in results if result["name"] == "tie_sat")
    assert tie_sat["exact"]["status"] == "sat" and tie_sat["heuristic"]["status"] == "unknown"
    checked = random_crosschecks(random_checks)
    report = {
        "schema_version": 1,
        "instrument": "bounded 3-SAT accessible-volume heuristic benchmark",
        "equation": EQUATION,
        "equation_creator": EQUATION_CREATOR,
        "threshold_rule": "At each branch, normalize occurrence-weighted true/false literal scores; prune only when A_tau(S)=0. Zero accessible volume returns unknown, never unsat.",
        "results": results,
        "checks": {
            "strict_threshold_examples": True,
            "exact_fixtures_match_independent_brute_force": True,
            "tie_sat_is_not_falsely_rejected": True,
            "random_formulas_crosschecked": checked,
        },
        "p_vs_np": "unresolved",
        "scope": [
            "A heuristic accessible-volume count is not a satisfiability or unsatisfiability certificate.",
            "A zero count returns unknown; it never proves unsat.",
            "Bounded examples and random seeds are not complexity proofs or polynomial-time bounds.",
            "No physical collider, hardware, patient data, or external target was accessed.",
        ],
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description="Benchmark accessible-volume pruning on bounded 3-SAT formulas")
    parser.add_argument("--output", type=Path, default=Path("evidence/sat-accessible-volume/verification.json"))
    parser.add_argument("--tau", type=float, default=0.5)
    parser.add_argument("--random-checks", type=int, default=24)
    args = parser.parse_args()
    report = run(args.output, args.tau, args.random_checks)
    for result in report["results"]:
        print(f"{result['name']}: exact={result['exact']['status']} heuristic={result['heuristic']['status']} "
              f"nodes={result['exact']['nodes']}/{result['heuristic']['nodes']}")
    print(f"RANDOM CROSSCHECKS: {report['checks']['random_formulas_crosschecked']}")
    print("P vs NP: unresolved; heuristic zero means unknown, not unsat")
    print("REPORT", args.output.resolve())


if __name__ == "__main__":
    main()

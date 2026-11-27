#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zoe_autonomy.experiment import _source_identity, _zoe_root
from zoe_autonomy.loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, digest


def proposals():
    return [
        Candidate("preserve-evidence", "preserve", .8, .7, .3, "Preserve evidence"),
        Candidate("inspect-alternatives", "inspect", .7, .8, .4, "Inspect alternatives"),
        Candidate("review-state", "review", .6, .5, .2, "Review state"),
    ]


def environment(evidence, inspections, reviews):
    env = InMemoryEnvironment()
    env._state = {
        "revision": evidence + inspections + reviews,
        "observations": [],
        "evidence": [{"fixture": 1}] if evidence else [],
        "inspections": [{"fixture": 1}] if inspections else [],
        "reviews": [{"fixture": 1}] if reviews else [],
    }
    return env


def project(env):
    state = env.snapshot()
    return tuple(int(bool(state[name])) for name in ("evidence", "inspections", "reviews"))


def connectivity(tpm):
    count = len(tpm[0])
    matrix = [[0] * count for _ in range(count)]
    for source in range(count):
        for target in range(count):
            for index, state in enumerate(itertools.product((0, 1), repeat=count)):
                flipped = list(state)
                flipped[source] ^= 1
                other = itertools.product((0, 1), repeat=count)
                other_index = list(other).index(tuple(flipped))
                if tpm[index][target] != tpm[other_index][target]:
                    matrix[target][source] = 1
                    break
    return matrix


def phi_of(tpm, cm, labels, state):
    import numpy as np
    import pyphi

    network = pyphi.Network(np.asarray(tpm, dtype=float), cm=np.asarray(cm), node_labels=labels)
    result = pyphi.compute.sia(pyphi.Subsystem(network, state))
    return {"state": list(state), "big_phi": float(result.phi), "cut": str(result.cut)}


def baseline():
    tpm = []
    actions = set()
    for evidence, inspections, reviews in itertools.product((0, 1), repeat=3):
        env = environment(evidence, inspections, reviews)
        loop = BoundedAutonomyLoop(environment=env)
        event = loop.run({"instrument": "phi-baseline"}, {}, proposals())
        tpm.append(project(env))
        actions.add(event["value"]["selected_candidate"])
    labels = ["evidence", "inspection", "review"]
    cm = connectivity(tpm)
    loop = BoundedAutonomyLoop()
    goals = []
    for _ in range(3):
        event = loop.run({"instrument": "phi-goal-probe"}, {}, proposals())
        goals.append(event["goal"]["statement"])
        actions.add(event["value"]["selected_candidate"])
    return {
        "tpm": tpm,
        "connectivity": cm,
        "phi": phi_of(tpm, cm, labels, (1, 0, 0)),
        "distinct_goal_statements": len(set(goals)),
        "distinct_actions": len(actions),
        "scope": "three-variable projection of the principal fixed-candidate fixture, not a whole-system measure",
    }


def and_control(count):
    tpm = [
        [int(all(state[other] for other in range(count) if other != index)) for index in range(count)]
        for state in itertools.product((0, 1), repeat=count)
    ]
    cm = [[int(source != target) for source in range(count)] for target in range(count)]
    labels = [f"n{index}" for index in range(count)]
    return {"nodes": count, "tpm": tpm, "connectivity": cm, "phi": phi_of(tpm, cm, labels, (1,) * count)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure the fixed-candidate baseline and canonical AND controls with IIT 3.0")
    parser.add_argument("--zoe-root", default=os.environ.get("ZOE_ROOT"), help="Zoe source checkout")
    parser.add_argument("--output", required=True, help="new JSON evidence path")
    arguments = parser.parse_args(argv)
    os.environ.setdefault("PYPHI_WELCOME_OFF", "yes")
    os.environ.setdefault("PYPHI_PARALLEL", "0")
    try:
        import pyphi
    except ImportError as error:
        raise ValueError("use the documented Python 3.9 environment with PyPhi 1.2.0") from error
    pyphi.config.PROGRESS_BARS = False
    root = _zoe_root(arguments.zoe_root)
    output = Path(arguments.output)
    if output.suffix.lower() != ".json":
        raise ValueError("Phi evidence must use a .json path")
    report = {
        "schema_version": 1,
        "instrument": "zoe-iit3-control/v1",
        "engine": f"pyphi {pyphi.__version__}",
        "python": sys.version.split()[0],
        "zoe_source": _source_identity(root),
        "source_sha256": {
            "src/zoe_autonomy/loop.py": hashlib.sha256((ROOT / "src/zoe_autonomy/loop.py").read_bytes()).hexdigest(),
            "scripts/measure-phi.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "baseline": baseline(),
        "and_controls": [and_control(count) for count in (3, 4, 5)],
        "control_scope": "Canonical AND motifs validate the instrument only. They are not Zoe, a self-reflection result, or a measure of experience.",
        "size_scope": "These three motifs do not establish a general relationship between network size, coupling density, learning, or consciousness.",
        "external_actions": 0,
    }
    report["profile_sha256"] = digest(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "baseline_phi": report["baseline"]["phi"]["big_phi"],
        "and_control_phi": [item["phi"]["big_phi"] for item in report["and_controls"]],
        "output": str(output),
        "profile_sha256": report["profile_sha256"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

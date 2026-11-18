from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independently verify Zoe's collaboration metacognition proof")
    parser.add_argument("proof", help="proof JSON created with Zoe's `agent proof PATH` command")
    arguments = parser.parse_args(argv)
    path = Path(arguments.proof).expanduser().resolve(strict=True)
    if path.stat().st_size > 4_000_000:
        raise ValueError("proof exceeds 4 MB")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("instrument") != "zoe-metacognition-collaboration-proof/v1":
        raise ValueError("unsupported proof instrument")
    expected = hashlib.sha256(canonical({key: value for key, value in document.items() if key != "proof_sha256"}).encode()).hexdigest()
    if document.get("proof_sha256") != expected:
        raise ValueError("proof digest mismatch")
    if hashlib.sha256(document["response"].encode()).hexdigest() != document["response_sha256"]:
        raise ValueError("response digest mismatch")
    measurement = document["operational_metacognition"]
    threshold = measurement["threshold"]
    breadth = measurement["breadth"]
    if not threshold["fixed_during_episode"] or threshold["post_hoc_retuning_allowed"]:
        raise ValueError("threshold was not fixed for the episode")
    scores = measurement["heuristic_scores"]
    options = breadth["options"]
    total = math.fsum(scores.values())
    if total <= 0 or len(options) != len(scores) or breadth["represented_count"] != len(options):
        raise ValueError("invalid choice set")
    for option in options:
        expected_probability = scores[option["id"]] / total
        if not math.isclose(option["probability"], expected_probability, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("option normalization mismatch")
    count = sum(option["probability"] > threshold["tau"] for option in options)
    if count != breadth["accessible_count"] or measurement["selected_action"] != "consult_agent":
        raise ValueError("equation or selected-action mismatch")
    print(json.dumps({
        "verified": True,
        "equation": "A_tau = sum(1[p(x) > tau])",
        "tau": threshold["tau"],
        "represented_count": len(options),
        "accessible_count": count,
        "selected_action": measurement["selected_action"],
        "response_sha256": document["response_sha256"],
        "proof_sha256": expected,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

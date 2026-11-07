#!/usr/bin/env python3
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance/accessible-volume.json"


def main():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in document["cases"]:
        probabilities = case["probabilities"]
        assert probabilities and all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
        assert math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-8)
        accessible = sum(value > case["tau"] for value in probabilities)
        assert accessible == case["accessible"], case["name"]
        assert len(probabilities) - accessible == case["complement"], case["name"]
        assert math.isclose(accessible / len(probabilities), case["normalized"], rel_tol=0, abs_tol=1e-15)
        print("VERIFIED", case["name"], accessible)
    java = (ROOT / "android/app/src/main/java/research/zoetic/zoe/AccessibleVolume.java").read_text(encoding="utf-8")
    swift = (ROOT / "shared/Sources/ZoeCore/AccessibleVolume.swift").read_text(encoding="utf-8")
    assert "probability > tau" in java
    assert "probability > tau" in swift
    assert "Nicholas Michael Kloster alone, March 6, 2026" in java
    assert "Nicholas Michael Kloster alone, March 6, 2026" in swift
    print(f"VERIFIED {len(document['cases'])} shared cases; Java and Swift retain strict comparison and original credit")


if __name__ == "__main__":
    main()

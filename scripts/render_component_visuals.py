#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from gem.mirror import os_document
from guiai.gem.atlas import default_document
from guiai.gem.render import write_png, write_svg
from guiai.gem.vdi import write_metafile
from guiai.gem.visual_language import normalize_scene, process_scene


ROOT = Path(__file__).resolve().parents[1]


def save(scene, relative, subtitle, footer):
    normalized = normalize_scene(scene, subtitle, footer)
    destination = ROOT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_svg(normalized, destination.with_suffix(".svg"), width=1920)
    write_png(normalized, destination.with_suffix(".png"), width=1920)
    write_metafile(normalized, destination.with_suffix(".gem"))
    print(destination.with_suffix(".png"))


def main():
    mirror = os_document("mirror")
    mirror_scene = mirror[0] if isinstance(mirror, tuple) else mirror
    for relative in [
        "components/graphics-environment-manager/docs/images/zoe-mirror",
        "components/next-token-predictability/assets/zoe-mirror",
        "components/Zoe-Autonomy/paper/unified/figures/zoe-mirror",
        "components/next-token-predictability/paper/unified/figures/zoe-mirror",
        "research/arxiv/02-unified-autonomy/figures/zoe-mirror",
        "research/papers/zoe-research/assets/native/zoe-mirror",
    ]:
        save(mirror_scene, relative, "FORWARD AND RETROGRADE FORECASTS · ONE HELD-OUT INDEX", "TWO DIRECTIONS · TWO DISTRIBUTIONS · NO HIDDEN AVERAGE")

    scene = process_scene("Master GEM architecture", ["Geometry", "Forecast", "Rhythm", "Multi-horizon", "Evidence"], "MASTER")
    for relative in [
        "components/next-token-predictability/assets/master-gem-architecture",
        "research/papers/zoe-research/assets/native/master-gem-architecture",
    ]:
        save(scene, relative, "CREATE · VERIFY · HOST · SHARED MATH · EVIDENCE FLOW", "SHARED MATH + CONFORMANCE + ARTIFACT API")

    scene, _ = default_document("volume")
    scene.document["title"] = "Operational Metacognition"
    save(scene, "components/next-token-predictability/assets/next-token-probability-equation", "STRICT p > τ · COUNT ALTERNATIVES BEFORE SELECTION", "THE ORIGINAL STRICT THRESHOLD OPERATOR · NICHOLAS MICHAEL KLOSTER · MARCH 6, 2026")

    scene, _ = default_document("volume")
    scene.document["title"] = "Operational Metacognition"
    save(scene, "components/next-token-predictability/assets/accessible-volume-hero", "FORECAST FUTURES · CAUSAL PASTS · STRICT p > τ", "A SHARED THRESHOLD INSTRUMENT FOR CHOICES AND METACOGNITION")

    scene = process_scene("Neurogarden · a shared research universe", ["Biology", "Neuroscience", "Physics", "CERN", "GEM", "Community"], "Z+N")
    for relative in [
        "components/agent-logging-system/docs/images/cern-universe",
        "research/papers/zoe-research/assets/neurogarden/cern-universe",
    ]:
        save(scene, relative, "SIX RESEARCH DOMAINS · ONE SHARED FIELD", "MEASUREMENT ≠ EVIDENCE ≠ ACTION · EVERY DOMAIN RETAINS ITS AUTHORITY")

    scene, _ = default_document("cognitive")
    save(scene, "components/graphics-environment-manager/docs/images/cognitive-field", "SOURCED MEMORY · BOUNDED WORKING SET · REVIEWED ACTION", "EVERY REPRESENTATION AND PROPOSAL REMAINS INSPECTABLE AND REPLAYABLE")

    scene, _ = default_document("qualia")
    save(scene, "components/next-token-predictability/assets/zoe-qualia", "CAUSAL REPERTOIRES · ACCESSIBLE Q-VOLUME · EXPLICIT ANNOTATION", "READ THE MECHANISM · PRESERVE THE REPERTOIRE · QUESTION THE INTERPRETATION")

    scene, _ = default_document("field")
    save(scene, "components/next-token-predictability/assets/zoe-field-notebook", "COMPETING CLAIMS · LIKELIHOOD RATIOS · NEXT-TEST PRIORITIES", "MEASUREMENT ≠ EVIDENCE ≠ BELIEF UPDATE ≠ ACTION")

    scene, _ = default_document("ellipses")
    save(scene, "components/next-token-predictability/assets/zoe-lots-of-ellipses", "STOCHASTIC FIELDS · PROBABILITY RIDGES · TRANSITION NETWORKS", "AN ORIGINAL COMPOSITION OF GEOMETRY, PROBABILITY, AND ORBITAL TRACES")

    for module, relative in [
        ("cognitive", "research/arxiv/02-unified-autonomy/figures/cognitive-field"),
        ("field", "research/arxiv/02-unified-autonomy/figures/field-notebook"),
        ("qualia", "research/arxiv/02-unified-autonomy/figures/qualia"),
        ("cicada", "research/arxiv/02-unified-autonomy/figures/cicada"),
        ("protocol", "research/arxiv/02-unified-autonomy/figures/protocol"),
        ("presence", "research/arxiv/02-unified-autonomy/figures/presence"),
        ("evidence", "research/arxiv/02-unified-autonomy/figures/zoe-evidence"),
        ("patchbay", "research/arxiv/02-unified-autonomy/figures/patchbay"),
        ("pentacube", "research/arxiv/02-unified-autonomy/figures/pentacube"),
        ("resilience", "research/arxiv/02-unified-autonomy/figures/zoe-resilience"),
        ("waveform", "research/arxiv/02-unified-autonomy/figures/zoe-waveform"),
    ]:
        scene, _ = default_document(module)
        save(scene, relative, "NATIVE MODEL · DETERMINISTIC GEOMETRY · REPLAYABLE EVIDENCE", "ONE REPOSITORY · ONE KNOWLEDGE FIELD · HUMAN CONTROL")


if __name__ == "__main__":
    main()

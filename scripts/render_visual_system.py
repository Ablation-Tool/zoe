#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from guiai.gem.atlas import default_document
from guiai.gem.render import write_png, write_svg
from guiai.gem.vdi import write_metafile
from guiai.gem.visual_language import normalize_scene


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "guiai-lab" / "docs" / "images"

MODULES = {
    "cognitive": "zoe-cognitive-field",
    "qualia": "zoe-qualia",
    "presence": "zoe-presence",
    "protocol": "zoe-protocol",
    "resilience": "zoe-resilience",
    "evidence": "zoe-evidence",
    "cicada": "zoe-cicada",
    "artline": "zoe-artline",
    "pentomino": "zoe-pentomino",
    "pentacube": "zoe-pentacube",
    "maison": "zoe-maison",
    "leadership": "zoe-leadership",
    "field": "zoe-field-notebook",
    "waveform": "zoe-waveform",
    "patchbay": "zoe-patchbay",
    "brain": "zoe-brain",
    "research": "zoe-research",
    "onset": "geometry-atlas-onset",
    "procrustes": "geometry-atlas-procrustes",
    "ellipses": "zoe-lots-of-ellipses",
    "parabola": "geometry-atlas-parabola",
    "circle": "geometry-atlas-circle",
    "clock": "geometry-atlas-clock",
    "graph": "geometry-atlas-graph",
    "volume": "accessible-volume-bridge",
    "horizon": "geometry-atlas-horizon",
    "dorothy": "dorothy-ccf2017",
    "dorothy-jenga": "dorothy-jenga-exploded",
    "dorothy-stack": "dorothy-stack",
    "dorothy-rings": "dorothy-rings-isocortex",
}

SUBTITLES = {
    "cognitive": "SOURCED MEMORY · BOUNDED WORKING SET · REVIEWED ACTION",
    "qualia": "CAUSAL REPERTOIRES · ACCESSIBLE Q-VOLUME · EXPLICIT ANNOTATION",
    "presence": "ATTENTION · EVENT-ORDINAL TIME · KNOWN UNKNOWNS · CORRECTION",
    "protocol": "SPECS · AMAC · CHECKSUMS · DETERMINISTIC DECODING",
    "resilience": "SIXTEEN SECTORS · SYNTHETIC SIGNALS · MEASURED RESILIENCE",
    "evidence": "SOURCE-FIRST RETRIEVAL · GUARDED OBSERVATIONS · REPLAYABLE BRIDGES",
    "cicada": "EXACT SOFTWARE TICKS · DAILY PHASE · DEVELOPMENTAL GATES",
    "artline": "VECTOR PATHS · EDITABLE GEOMETRY · TRANSACTIONAL CREATION",
    "pentomino": "SPATIAL PRACTICE · FINITE DEADLINES · VERIFIED REPLAY",
    "pentacube": "EXACT INVERSES · LEGAL PERMUTATIONS · DETERMINISTIC SCRAMBLES",
    "maison": "EXECUTIVE CLARITY · REVERSIBLE PRACTICE · MEASURED RESTRAINT",
    "leadership": "ATTEMPTS · MISTAKES · UNCERTAINTY · APPEND-ONLY LEARNING",
    "field": "COMPETING CLAIMS · LIKELIHOOD RATIOS · NEXT-TEST PRIORITIES",
    "waveform": "BOUNDED REPLAY · NORMALIZED EVENTS · DECLARED TRUNCATION",
    "patchbay": "FIRMWARE INSPECTION · SIGNED CAPSULES · GATED ACCEPTANCE",
    "brain": "FORWARD AND RETROGRADE FORECASTS · MIRRORED OBSERVATION",
    "research": "SOURCE-LINKED EVIDENCE · NEGATIVE RESULTS · REPRODUCIBLE MEASUREMENT",
    "onset": "HELD-OUT CATEGORICAL FORECASTS · STRICT THRESHOLD SWEEPS",
    "procrustes": "LANDMARK CORRESPONDENCE · SIMILARITY · RIGID · AFFINE ALIGNMENT",
    "ellipses": "STOCHASTIC FIELDS · PROBABILITY RIDGES · TRANSITION NETWORKS",
    "parabola": "PARABOLIC ENVELOPES · TANGENTS · EXACT CONSTRUCTION",
    "circle": "ARC · SECTOR · DIAMETER · EXACT GEOMETRY",
    "clock": "MODULAR ARITHMETIC · EXACT TICKS · DETERMINISTIC PHASE",
    "graph": "HUB-AND-LOOP TOPOLOGY · CYCLE RANK · CONNECTED STRUCTURE",
    "volume": "STRICT p > τ · ACCESSIBLE ALTERNATIVES · METACOGNITIVE MEASUREMENT",
    "horizon": "MULTI-HORIZON CONTINUATIONS · EXACT BOUNDED ENUMERATION",
    "dorothy": "ALLEN MOUSE CCFV3 · VERIFIED REFERENCE GEOMETRY",
    "dorothy-jenga": "VOLUME-SCALED ATLAS STRUCTURES · DETERMINISTIC EXPLODED TOWER",
    "dorothy-stack": "CORONAL SLABS · SPATIAL INSPECTION · REFERENCE GEOMETRY",
    "dorothy-rings": "ONTOLOGY PARTITIONS · EXACT SUBTREE VOLUMES · RADIAL NAVIGATION",
}

FOOTERS = {
    "volume": "A(τ) MEASURES FORECAST BREADTH; ZOE USES IT TO OBSERVE HER OWN DECISIONS",
    "brain": "TWO DIRECTIONS · ONE HELD-OUT INDEX · NO HIDDEN AVERAGE",
    "dorothy": "PRECLINICAL REFERENCE GEOMETRY · SOURCE-PROVENANCE PRESERVED",
    "dorothy-jenga": "PRECLINICAL REFERENCE GEOMETRY · SOURCE-PROVENANCE PRESERVED",
    "dorothy-stack": "PRECLINICAL REFERENCE GEOMETRY · SOURCE-PROVENANCE PRESERVED",
    "dorothy-rings": "PRECLINICAL REFERENCE GEOMETRY · SOURCE-PROVENANCE PRESERVED",
}


def main():
    parser = argparse.ArgumentParser(description="Render Zoe's native scenes through the shared visual language")
    parser.add_argument("--module", action="append", help="render only the named atlas module; repeatable")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    output = arguments.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected = arguments.module or list(MODULES)
    unknown = set(selected) - set(MODULES)
    if unknown:
        raise ValueError(f"unknown visual modules: {', '.join(sorted(unknown))}")
    for module in selected:
        scene, _report = default_document(module)
        subtitle = SUBTITLES.get(module, "MEANINGFUL GEOMETRY · MEASURED EVIDENCE · REPLAYABLE RESEARCH")
        footer = FOOTERS.get(module, "NATIVE MODEL · DETERMINISTIC GEOMETRY · REPLAYABLE EVIDENCE")
        normalized = normalize_scene(scene, subtitle, footer)
        destination = output / MODULES[module]
        write_svg(normalized, destination.with_suffix(".svg"), width=1920)
        write_png(normalized, destination.with_suffix(".png"), width=1920)
        write_metafile(normalized, destination.with_suffix(".gem"))
        print(f"{module}: {destination.with_suffix('.png')}")


if __name__ == "__main__":
    main()

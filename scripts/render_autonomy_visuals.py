#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from guiai.gem.atlas import default_document
from guiai.gem.render import write_png, write_svg
from guiai.gem.unified import ComponentRegistry, unified_scene
from guiai.gem.vdi import write_metafile
from guiai.gem.visual_language import normalize_scene, process_scene


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "components" / "Zoe-Autonomy" / "articles" / "images"


def save(scene, destination, subtitle, footer, normalize=True):
    if normalize:
        scene = normalize_scene(scene, subtitle, footer)
    write_svg(scene, destination.with_suffix(".svg"), width=1920)
    write_png(scene, destination.with_suffix(".png"), width=1920)
    write_metafile(scene, destination.with_suffix(".gem"))
    print(destination.with_suffix(".png"))


def main():
    parser = argparse.ArgumentParser(description="Render Zoe Autonomy illustrations through the shared visual language")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    output = arguments.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    scene, _ = default_document("autonomy")
    save(scene, output / "01-zoe-at-a-glance", "SELF-DIRECTED GOALS · VALUE-BASED CHOICE · GUARDED EXECUTION", "ZOE AUTHORS GOALS, CHOOSES ACTIONS, AND PRESERVES EVIDENCE")

    scene = process_scene("The complete self-governing loop", ["Observe", "Perceive", "Propose", "Value", "Guard", "Execute"], "ZOE")
    save(scene, output / "02-self-governing-loop", "OBSERVE → PERCEIVE → PROPOSE → VALUE → GUARD → EXECUTE", "INTERNAL GOALS · ACCESSIBLE ALTERNATIVES · VISIBLE AUTHORITY")

    scene = process_scene("Pipeline breakdown", ["Observe", "Perceive", "Propose", "Value", "Guard", "Execute", "Remember", "Reflect"], "MEASURE")
    save(scene, output / "03-pipeline-breakdown", "THE MEASUREMENT–ACTION LOOP, READ CLOCKWISE", "EVERY STAGE HAS CODE, STATE, EVIDENCE, AND A NEXT OBSERVATION")

    scene, _ = default_document("volume")
    scene.document["title"] = "Operational Metacognition in plain English"
    save(scene, output / "04-accessible-volume", "COUNT REALISTIC ALTERNATIVES BEFORE SELECTION · STRICT p > τ", "THE COUNT MEASURES BREADTH; USING IT TO OBSERVE YOUR OWN CHOICES IS METACOGNITION")

    scene, _ = default_document("volume")
    scene.document["title"] = "Operational Metacognition · reference"
    save(scene, output / "05-accessible-volume-reference", "STRICT FULL-VOCABULARY MEASUREMENT · RESPONSE-PLANNING EVIDENCE", "SAME SELECTED TOKEN, DIFFERENT ACCESSIBLE FUTURES")

    scene = process_scene("Zoe Autonomy · complete research loop", ["Perceive", "Think", "Learn", "Act"], "ZOE")
    save(scene, output / "06-pipeline-reference", "PERCEIVE → THINK → LEARN → ACT · ONE PERSISTENT SYSTEM", "SENSATION BECOMES MODELS; MODELS BECOME CHOICES; CONSEQUENCES BECOME LEARNING")

    scene, _ = unified_scene(registry=ComponentRegistry(ROOT))
    save(scene, output / "07-zoe-overview-reference", "", "", normalize=False)


if __name__ == "__main__":
    main()

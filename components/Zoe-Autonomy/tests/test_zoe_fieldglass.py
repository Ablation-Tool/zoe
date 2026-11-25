"""Tests for `guiai.gem.zoe_fieldglass` integration with GEM Chiasm & BrailleCanvas."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from guiai.gem.render import write_svg
from guiai.gem.zoe_fieldglass import (
    FIELDGLASS_CONTRACT,
    TONAL_STATES,
    a_tau,
    build_fieldglass_chiasm_scene,
    clean_illumination,
    ink_to_braille_canvas,
    laplacian_sharpness,
    luminance_to_8state,
    normalize_dist,
    perspective_deskew,
    trace_ink_to_svg,
)


def test_fieldglass_chiasm_scene_and_svg(tmp_path: Path):
    episodes = [
        normalize_dist({s: 1.0 + ((i + t) % 5) for i, s in enumerate(TONAL_STATES)})
        for t in range(8)
    ]
    scene, report = build_fieldglass_chiasm_scene(
        episodes,
        per_sec_a004=[90 + t for t in range(8)],
        per_sec_a010=[14 + (t % 4) for t in range(8)],
        nexus_sec=4,
    )
    assert report["contract"] == FIELDGLASS_CONTRACT
    assert report["executed"] is False
    assert report["sentience_claimed"] is False
    assert report["tokens_used"] == 0
    assert report["scene_sha256"] == scene.digest()

    svg_path = tmp_path / "fieldglass_chiasm.svg"
    write_svg(scene, svg_path, width=1400)
    assert svg_path.is_file() and "<svg" in svg_path.read_text(encoding="utf-8")


def test_fieldglass_plate_svg_and_braille(tmp_path: Path):
    img = Image.new("RGB", (240, 320), (235, 228, 210))
    d = ImageDraw.Draw(img)
    d.line([(120, 30), (120, 280)], fill=(20, 18, 16), width=5)
    d.ellipse([70, 110, 170, 190], outline=(20, 18, 16), width=4)

    assert laplacian_sharpness(img) > 0.0
    warped = perspective_deskew(img, [(0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98)], out_size=(200, 280))
    ink, archival, bw = clean_illumination(warped, sigma=18.0)
    assert archival.size == (200, 280) and bw.size == (200, 280)

    svg = trace_ink_to_svg(ink, tmp_path / "orchid.svg", vec_width=160)
    assert svg.is_file() and "<svg" in svg.read_text(encoding="utf-8")

    lines = ink_to_braille_canvas(ink, cols=32)
    assert len(lines) >= 8
    assert any(ord(ch) > 0x2800 for row in lines for ch in row)

    p256 = np.ones(256, dtype=np.float64) / 256.0
    assert a_tau(p256, 0.003) == 256
    assert abs(sum(luminance_to_8state(p256).values()) - 1.0) < 1e-12

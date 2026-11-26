"""Unit & Integration Tests for Zoe Clean-Room Presentation Team (Milestone M1A)."""

from __future__ import annotations

import math
from pathlib import Path
import struct
import subprocess
import sys
from typing import cast
from unittest import mock
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from guiai.gem import geometry, seasip_gem, vdi
from guiai.gem.model import Scene
from guiai.gem.presentation import (
    BOTANICAL_COLORS,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COL_GAP,
    DARK_BOTANICAL_THEME,
    INK,
    JADE,
    LIGHT_BOTANICAL_THEME,
    MARGIN,
    OBSIDIAN,
    PORCELAIN,
    RUBY,
    SISTER_THEMES,
    WHITE,
    W_FULL,
    W_HALF,
    X_LEFT,
    X_RIGHT,
    Y_TOP,
    DrawPlusCanvas,
    LayoutReport,
    PresentationRenderer,
    PresentationScene,
    contrast_ratio,
    petal_points,
    theme_for_sister,
    verify_slide_layout,
)
from guiai.gem.zoe_sisters import ZOE_SISTERS


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# 1. VDI Codec & Backwards Compatibility (`guiai.gem.vdi`)
# ---------------------------------------------------------------------------

def test_vdi_spec_exact_opcodes_and_slide_header():
    assert vdi.OPCODE_NAMES[13] == "vst_rotation"
    assert vdi.OPCODE_NAMES[14] == "vs_color"
    assert "#ff0000" not in vdi.COLOR_INDEX
    assert "#00ff00" not in vdi.COLOR_INDEX

    builder = vdi.VdiMetafileBuilder()
    builder.slide_meta({"slide_index": 1, "speaker_notes": "Clean-room test"})
    builder.set_line(color="#B81D48", width=16, line_type=5, ends=(0, 1))
    builder.set_fill(color="#0E6B5E", interior=3, style=5, perimeter=True)
    builder.bar(550, 1220, 6540, 3000)
    builder.rbox(6793, 1220, 12783, 3000)
    builder.rfbox(550, 3200, 6540, 5000)
    builder.circle(9788, 4100, 700)
    builder.ellipse(3500, 6000, 900, 450)
    builder.arc(3500, 6000, 600, 0, 900)
    builder.pieslice(9788, 4100, 500, 900, 1800)
    builder.ellarc(6666, 5800, 800, 400, 0, 1800)
    builder.ellpie(6666, 5800, 600, 300, 1800, 2700)
    builder.set_text(color="#111827", height=278, font_id=21, effects=0x09, alignment=(1, 0), rotation_tenths=450)
    builder.gtext(6666, 6500, "Zoe VDI")
    builder.group(2)
    builder.set_no_line_style()
    builder.shadow_on()
    builder.bar(100, 100, 200, 200)
    builder.shadow_off()
    builder.bar(90, 90, 190, 190)

    data = builder.build()
    chk = seasip_gem.verify_seasip_gem_metafile(data)
    assert chk["valid"] is True
    assert chk["coordinate_system"] == "RC"

    parsed = vdi.parse_metafile(data)
    hdr = parsed["header"]
    assert hdr["coordinate_system"] == 2
    assert hdr["page_size"] == (3387, 1905)
    assert hdr["coordinate_bounds"] == (0, 0, 13333, 7500)

    inv = vdi.opcode_inventory(data)
    assert inv["vs_color"] >= 2
    assert inv["vst_rotation"] >= 1
    assert inv["vsl_type"] >= 1
    assert inv["vsl_width"] >= 1
    assert inv["vsl_ends"] >= 1
    assert inv["vsf_interior"] >= 1
    assert inv["vsf_style"] >= 1
    assert inv["vst_font"] >= 1
    assert inv["vst_effects"] >= 1
    assert inv["vst_alignment"] >= 1
    assert inv["vsf_perimeter"] >= 1
    for gdp_name in ("v_bar", "v_arc", "v_pieslice", "v_circle", "v_ellipse", "v_ellarc", "v_ellpie", "v_rbox", "v_rfbox"):
        assert inv[gdp_name] >= 1

    # Verify spec-exact 4-pt v_arc/v_pieslice and 3-pt v_circle point counts
    arc_recs = [r for r in parsed["records"] if r["command"] == 11 and r["subcommand"] == 2]
    pie_recs = [r for r in parsed["records"] if r["command"] == 11 and r["subcommand"] == 3]
    cir_recs = [r for r in parsed["records"] if r["command"] == 11 and r["subcommand"] == 4]
    assert arc_recs[0]["points"] == 4
    assert pie_recs[0]["points"] == 4
    assert cir_recs[0]["points"] == 3

    # Verify slide_meta is skipped from shape binding & shadow block skipped on roundtrip
    rt = vdi.scene_from_metafile(data)
    assert rt.canvas == {"width": 13333.0, "height": 7500.0}
    assert len(rt.objects) >= 9


def test_vdi_legacy_opcode_13_fallback_and_2pt_gdp_compatibility():
    # Craft a metafile with legacy 4-int opcode 13 vs_color + 2-pt v_arc/v_circle
    header = struct.pack(
        "<24h",
        -1, 24, 101, 2,
        0, 0, 1000, 1000,
        2540, 2540,
        0, 0, 2000, 2000,
        0, *([0] * 9),
    )
    recs = b"".join([
        vdi._record(13, values=[16, 1000, 0, 0]),  # legacy 4-int opcode 13
        vdi.vsf_interior(1),
        vdi.vsf_color(16),
        vdi.vsl_color(1),
        vdi._record(11, 4, points=[(500, 500), (200, 0)]),  # 2-pt circle
        vdi._record(11, 2, points=[(1000, 1000), (200, 0)], values=[0, 900]),  # 2-pt arc
        struct.pack("<h", -1),
    ])
    data = header + recs
    inv = vdi.opcode_inventory(data)
    assert inv["vs_color_legacy"] == 1
    assert inv["v_circle"] == 1
    assert inv["v_arc"] == 1

    sc = vdi.scene_from_metafile(data)
    assert sc.objects[0]["type"] == "ellipse"
    assert sc.objects[0]["fill"] == "#ff0000"
    assert sc.objects[1]["type"] == "polyline"
    # Verify 0..90 deg CCW in top-left RC space goes upward (y < cy)
    pts = sc.objects[1]["points"]
    assert pts[-1][1] < 1000.0


def test_vdi_hardening_rejects_overflow_bool_nan_and_malformed_records():
    for bad in (-32769, 32768, True, False, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            vdi._word(bad)

    # Overflow in builder
    b = vdi.VdiMetafileBuilder()
    with pytest.raises(ValueError):
        b.bar(0, 0, 40000, 100)

    # Malformed 0-int attribute record must raise ValueError (not IndexError)
    header = struct.pack("<24h", -1, 24, 101, 2, 0, 0, 100, 100, 2540, 2540, 0, 0, 1000, 1000, 0, *([0] * 9))
    bad_rec = vdi._record(17, values=[])  # vsl_color with 0 values
    with pytest.raises(ValueError):
        vdi.scene_from_metafile(header + bad_rec + struct.pack("<h", -1))

    # Malformed opcode 13 with 2 ints
    bad_op13 = vdi._record(13, values=[10, 20])
    with pytest.raises(ValueError):
        vdi.scene_from_metafile(header + bad_op13 + struct.pack("<h", -1))


def test_all_39_existing_gem_assets_still_valid():
    gem_files = sorted(
        [REPO_ROOT / "assets/demos/life.gem", REPO_ROOT / "assets/brain-dialogue/second-eye.gem"]
        + list((REPO_ROOT / "guiai-lab/docs/images").glob("*.gem"))
    )
    assert len(gem_files) == 39
    for path in gem_files:
        data = path.read_bytes()
        assert seasip_gem.verify_seasip_gem_metafile(data)["valid"] is True, path
        sc = vdi.scene_from_metafile(data)
        assert len(sc.objects) > 0, path


# ---------------------------------------------------------------------------
# 2. Botanical Palette & 9-Sister Themes (`presentation/palette.py`)
# ---------------------------------------------------------------------------

def test_palette_symmetry_and_nine_sister_contrast():
    assert CANVAS_WIDTH == 13333
    assert CANVAS_HEIGHT == 7500
    assert X_LEFT == MARGIN == 550
    assert X_RIGHT == MARGIN + W_HALF + COL_GAP == 6793
    assert X_LEFT + W_HALF + COL_GAP + W_HALF + MARGIN == CANVAS_WIDTH
    assert W_FULL == 12233
    assert Y_TOP == 1220
    assert BOTANICAL_COLORS["obsidian"] == OBSIDIAN
    assert BOTANICAL_COLORS["porcelain"] == PORCELAIN
    assert LIGHT_BOTANICAL_THEME.bg == PORCELAIN
    assert DARK_BOTANICAL_THEME.bg == OBSIDIAN

    assert len(SISTER_THEMES) == 9
    for spec in ZOE_SISTERS:
        lt = theme_for_sister(spec.name, mode="light")
        dt = theme_for_sister(spec.signet, mode="dark")
        assert contrast_ratio(lt.accent, lt.card) >= 4.5
        assert contrast_ratio(dt.accent, dt.card) >= 4.5
        assert lt.sister_name == spec.name
        assert dt.artline_font_id == spec.artline_font_id


# ---------------------------------------------------------------------------
# 3. Draw Plus Primitives, Transforms, Botanical Toolkit & Renderer
# ---------------------------------------------------------------------------

def test_draw_plus_all_primitives_and_pure_python_rendering(tmp_path: Path):
    # Create a tiny raster PNG to test clipped raster inset embedding
    inset_png = tmp_path / "inset.png"
    Image.new("RGBA", (64, 48), (14, 107, 94, 255)).save(inset_png)

    c = DrawPlusCanvas(title="Primitives Showcase", sister_id="zoe", speaker_notes="Notes here")
    c.add_rounded_rectangle([400, 400, 3200, 2200], radius=180, fill=WHITE, stroke=RUBY, width=20, shadow=True)
    c.add_rectangle([3500, 400, 6200, 2200], fill=JADE, stroke=INK, width=16, fill_interior=3, fill_style=5)
    c.add_circle(7600, 1300, 750, fill="#FBF3E0", stroke=RUBY, width=18)
    c.add_ellipse(9800, 1300, 950, 550, fill="#FAEAEF", stroke=JADE, width=16, fill_interior=2, fill_style=8)
    c.add_arc(2000, 3600, 800, 0, 900, stroke=RUBY, width=24, line_type=5)
    c.add_pieslice(4600, 3600, 800, 0, 1200, fill=RUBY, stroke=WHITE, width=16)
    c.add_ellarc(7200, 3600, 900, 500, 900, 2700, stroke=JADE, width=20, line_type=3)
    c.add_ellpie(9800, 3600, 900, 500, 0, 1800, fill="#C29130", stroke=INK, width=14)
    c.add_line([600, 5200], [3200, 5200], stroke=RUBY, width=24, line_type=2, line_ends=(0, 1))
    c.add_sketch([[3600, 5400], [4400, 4900], [5200, 5400]], smooth=True, stroke=JADE, width=20)
    c.add_polygon([[5800, 5500], [6400, 4800], [7000, 5500]], fill=RUBY, stroke=INK, width=12)
    c.add_text([7400, 4700, 9800, 5900], "12.34\n5.678\n100.1", font_pt=11.0, align="decimal", bold=True, underline=True, boxed=True, color=INK)
    c.add_text([10000, 4700, 12800, 5900], "Artline Palatino wrapped text inside clean card box", font_id=21, font_pt=10.0, italic=True, align="center", valign="middle", color=INK)
    c.add_image([400, 5800, 2400, 7100], inset_png, fit="contain", radius=120, fill=WHITE, stroke=RUBY, width=16, caption="Clipped Raster")

    # Verify zero external binaries invoked during rendering
    with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess.run forbidden")), \
         mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess.Popen forbidden")):
        out_png = c.render_png(tmp_path / "slide.png", width=1920, height=1080)
        out_jpg = c.render_jpg(tmp_path / "slide.jpg", width=1920, height=1080, quality=92)
        svg = c.render_svg(tmp_path / "slide.svg", width=1920)
        gem_bytes = c.to_gem_bytes()
        scene = c.to_scene()

    assert out_png.is_file() and out_png.stat().st_size > 10000
    assert out_jpg.is_file() and out_jpg.stat().st_size > 10000
    with Image.open(out_png) as im_p:
        assert im_p.size == (1920, 1080)
    with Image.open(out_jpg) as im_j:
        assert im_j.size == (1920, 1080)
    assert "vdi-pat-" in svg
    assert "vdi-clip-" in svg
    assert "data:image/png;base64," in svg
    assert seasip_gem.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    assert isinstance(scene, Scene)
    assert geometry.verify(scene).passed is True


def test_arc_angle_polarity_is_top_left_ccw():
    """Verify VDI 0..900 (0..90 deg CCW) renders in upper-right quadrant (y < cy), NOT lower-right."""
    c = DrawPlusCanvas(width=1000, height=1000, background=WHITE)
    c.add_pieslice(500, 500, 350, 0, 900, fill="#FF0000", stroke="none", width=0)
    im = c.render_pil(width=500, height=500)
    # Upper-right quadrant pixel (cx + 120, cy - 120) -> px (310, 190) should be RED
    r_up, g_up, b_up = im.getpixel((310, 190))
    # Lower-right quadrant pixel (cx + 120, cy + 120) -> px (310, 310) should be WHITE
    r_dn, g_dn, b_dn = im.getpixel((310, 310))
    assert r_up > 200 and g_up < 50 and b_up < 50
    assert r_dn > 240 and g_dn > 240 and b_dn > 240


def test_draw_plus_grouping_zorder_transforms_align_spacing_and_autogrid():
    c = DrawPlusCanvas(auto_grid=50)
    r1 = c.add_rectangle([112, 118, 512, 318], fill=RUBY, stroke=INK)  # snapped to 100,100,500,300
    assert c._by_id(r1)["bounds"] == [100.0, 100.0, 500.0, 300.0]

    r2 = c.add_rectangle([700, 100, 1100, 300], fill=JADE, stroke=INK)
    t1 = c.add_text([100, 100, 500, 300], "Hello", align="left")
    gid = c.group([r1, t1])
    assert gid in c.groups

    # Z-order
    c.put_in_back([r2])
    assert c.elements[0]["id"] == r2
    c.put_in_front([r2])
    assert c.elements[-1]["id"] == r2

    # Rotate 90 & upright flip
    c.rotate_90([r1], ccw=True, center=(300.0, 200.0))
    assert c._by_id(r1)["bounds"] == [200.0, 0.0, 400.0, 400.0]

    c.flip_h([t1], axis_x=500.0)
    assert c._by_id(t1)["bounds"] == [500.0, 100.0, 900.0, 300.0]
    assert c._by_id(t1)["align"] == "right"  # text stays upright, align swaps left <-> right!

    c.flip_v([t1], axis_y=400.0)
    assert c._by_id(t1)["bounds"] == [500.0, 500.0, 900.0, 700.0]

    # Break group
    members = c.break_group(gid)
    assert members == [r1, t1]
    assert gid not in c.groups

    # 9-way align & even spacing
    b1 = c.add_rectangle([1000, 1000, 1400, 1200])
    b2 = c.add_rectangle([1200, 1500, 1600, 1700])
    b3 = c.add_rectangle([1400, 2600, 1800, 2800])
    c.align([b1, b2, b3], "left")
    assert c._by_id(b2)["bounds"][0] == 1000.0
    assert c._by_id(b3)["bounds"][0] == 1000.0
    c.even_spacing([b1, b2, b3], axis="vertical")
    # First top=1000 (h=200), last bottom=2800 (top=2600, h=200) -> middle top should be 1800!
    assert c._by_id(b2)["bounds"][1] == 1800.0


def test_botanical_vector_toolkit_and_symmetrical_chrome(tmp_path: Path):
    pts = petal_points(1000, 1000, 0.0, 400, 90)
    assert len(pts) == 56

    c = DrawPlusCanvas(title="Symmetrical Botanical Slide", theme=LIGHT_BOTANICAL_THEME)
    c.add_symmetrical_chrome(1, 6, "VOL. I", "Operational Metacognition & 16 Theorems", "Mar 6, 2026")
    c.add_card([X_LEFT, Y_TOP, X_LEFT + W_HALF, 6800], accent_color=RUBY, shadow=True)
    c.add_bullets(
        [X_LEFT + 180, Y_TOP + 220, X_LEFT + W_HALF - 180, 6600],
        [
            ("Theorem 1:", "Threshold A_tau(p) proves strict monotonicity across calibrated ensembles."),
            ("Zero Tokens:", "100% deterministic offline verification in < 6 seconds."),
        ],
    )
    c.add_card([X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 6800], accent_color=JADE, shadow=True)
    c.add_hex_rosette(X_RIGHT + W_HALF / 2.0, (Y_TOP + 6800) / 2.0, hex_radius=420.0)

    report = verify_slide_layout(c)
    assert isinstance(report, LayoutReport)
    assert report.ok is True, f"overlaps={report.overlaps}, oob={report.out_of_bounds}"

    # Also test Hero Mandala Halo with floating zoe-gem.png on dark Obsidian theme
    dark = DrawPlusCanvas(title="Hero Cover", theme=DARK_BOTANICAL_THEME)
    emblem = REPO_ROOT / "assets/branding/zoe-gem.png"
    dark.add_hero_mandala_halo(CANVAS_WIDTH / 2.0, 2200.0, radius=1100.0, emblem_path=emblem if emblem.is_file() else None)
    assert dark.verify_layout().ok is True
    dark.render_png(tmp_path / "hero.png", width=960, height=540)
    assert seasip_gem.verify_seasip_gem_metafile(dark.to_gem_bytes())["valid"] is True


def test_verify_layout_detects_text_overlap_overflow_and_clipping():
    # 1. Text-vs-text overlap
    c1 = DrawPlusCanvas()
    c1.add_text([1000, 1000, 4000, 1500], "First Overlapping Headline", font_pt=18.0, bold=True, id="t1")
    c1.add_text([1200, 1100, 4200, 1600], "Second Overlapping Headline", font_pt=18.0, bold=True, id="t2")
    r1 = c1.verify_layout()
    assert r1.ok is False
    assert any("t1 overlaps t2" in msg for msg in r1.overlaps)

    # 2. Text overflow inside a tiny container
    c2 = DrawPlusCanvas()
    c2.add_text([1000, 1000, 1400, 1250], "This sentence is far too long and tall for a tiny box!", font_pt=14.0, id="overflow_box")
    r2 = c2.verify_layout()
    assert r2.ok is False
    assert any("overflow_box" in msg and "overflow" in msg for msg in r2.out_of_bounds)

    # 3. Element clipping outside canvas bounds
    c3 = DrawPlusCanvas()
    c3.add_rectangle([12500, 7000, 13600, 7700], id="clipped_rect")
    r3 = c3.verify_layout()
    assert r3.ok is False
    assert any("clipped_rect" in msg for msg in r3.out_of_bounds)


def test_vdi_state_machine_bridge_and_closure_invariants(tmp_path: Path):
    import ast

    # 1. Verify vdi.py stays strictly stdlib + .geometry + .model (for zoe_gem_os/builder.py)
    vdi_src = (REPO_ROOT / "guiai-lab/guiai/gem/vdi.py").read_text(encoding="utf-8")
    tree = ast.parse(vdi_src)
    allowed_stdlib = set(sys.stdlib_module_names) | {"__future__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_stdlib
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                assert node.module in {"geometry", "model"}
            else:
                assert (node.module or "").split(".")[0] in allowed_stdlib

    # 2. Verify canvas int16 validation & GemVdiStateMachine bridge
    with pytest.raises(ValueError):
        DrawPlusCanvas(width=40000, height=7500)
    with pytest.raises(ValueError):
        DrawPlusCanvas(width=True, height=7500)  # type: ignore[arg-type]

    c = DrawPlusCanvas()
    c.add_rounded_rectangle([500, 500, 2500, 1500], radius=100, fill=RUBY, stroke=INK)
    c.add_ellpie(5000, 3000, 600, 400, 0, 1800, fill=JADE, stroke=INK)
    sm = c.to_vdi_state_machine()
    sm_gem = sm.to_gem_metafile()
    assert seasip_gem.verify_seasip_gem_metafile(sm_gem)["valid"] is True

    # 3. PresentationRenderer accepts Scene & PresentationScene directly
    sc = c.to_scene()
    pr_sc = PresentationRenderer(sc)
    assert seasip_gem.verify_seasip_gem_metafile(pr_sc.to_gem_bytes())["valid"] is True
    p_out = pr_sc.render_png(tmp_path / "from_scene.png", width=640, height=360)
    assert p_out.is_file()
    pr_ps = PresentationRenderer(c.to_presentation_scene())
    assert "<svg" in pr_ps.render_svg(width=640)


def test_gem_roundtrip_arcs_pieslices_shadow_and_non_contiguous_group():
    c = DrawPlusCanvas()
    g_a = c.add_rectangle([500, 500, 1500, 1000], fill=WHITE, stroke=INK, shadow=True, id="shadow-rect")
    c.add_arc(6200, 2200, 500, 0, 900, stroke=RUBY, id="arc-1")
    g_b = c.add_pieslice(4000, 3000, 600, 0, 1200, fill=RUBY, id="pie-1")
    c.add_ellarc(7000, 3000, 700, 400, 900, 2700, stroke=JADE, id="ellarc-1")
    c.add_ellpie(9000, 3000, 700, 400, 1800, 3600, fill=JADE, id="ellpie-1")
    c.group([g_a, g_b])

    gem_bytes = c.to_gem_bytes()
    assert seasip_gem.verify_seasip_gem_metafile(gem_bytes)["valid"] is True

    roundtrip = vdi.scene_from_metafile(gem_bytes)
    ids = {obj["id"] for obj in roundtrip.objects}
    assert {"shadow-rect", "arc-1", "pie-1", "ellarc-1", "ellpie-1"}.issubset(ids)

    # Non-contiguous group [g_a, g_b] interrupted by arc-1 must NOT emit META_GROUP(2) binding arc-1
    parsed = vdi.parse_metafile(gem_bytes)
    group_recs = [
        r["values"]
        for r in parsed["records"]
        if r["command"] == 5 and r["subcommand"] == 99 and r["values"][0] == vdi.META_GROUP
    ]
    assert group_recs == []

    # Legacy shadow block where object_meta precedes shadow_on must also preserve object ID
    header = struct.pack("<24h", -1, 24, 101, 2, 0, 0, 1000, 1000, 2540, 2540, 0, 0, 1000, 1000, 0, *([0] * 9))
    recs = b"".join([
        vdi._object_record({"id": "pre-shadow-id", "type": "rectangle"}),
        vdi.meta_shadow_on(),
        vdi.v_bar(120, 120, 320, 320),
        vdi.meta_shadow_off(),
        vdi.v_bar(100, 100, 300, 300),
        struct.pack("<h", -1),
    ])
    sc_shadow = vdi.scene_from_metafile(header + recs)
    assert [o["id"] for o in sc_shadow.objects] == ["pre-shadow-id"]


def test_image_fit_cover_radius_zero_clips_in_png_and_svg(tmp_path: Path):
    wide_png = tmp_path / "wide_green.png"
    Image.new("RGBA", (400, 100), (0, 200, 0, 255)).save(wide_png)

    c = DrawPlusCanvas(background=WHITE)
    c.add_image([10200, 4900, 11200, 5900], wide_png, fit="cover", radius=0)

    png_path = c.render_png(tmp_path / "cover_r0.png", width=1920, height=1080)
    svg = c.render_svg(width=1920)
    assert "<clipPath" in svg and "clip-path=\"url(#" in svg

    with Image.open(png_path) as im:
        # [10200, 11200] * (1920 / 13333) -> [1468.8, 1612.8]; zero green bleed outside bounds
        bleed_left = sum(1 for x in range(1100, 1468) for y in range(700, 860) if cast(tuple[int, ...], im.getpixel((x, y)))[:3] != (255, 255, 255))
        bleed_right = sum(1 for x in range(1614, 1900) for y in range(700, 860) if cast(tuple[int, ...], im.getpixel((x, y)))[:3] != (255, 255, 255))
        inside = cast(tuple[int, ...], im.getpixel((1540, 780)))[:3]
    assert bleed_left == 0
    assert bleed_right == 0
    assert inside[1] > 150 and inside[0] < 50


def test_verify_layout_rejects_one_unit_oob_rotated_text_and_2coord_baseline_clipping():
    # 1. Exact 1-VDI-unit OOB (no +/-1.0 slack)
    c_oob = DrawPlusCanvas()
    c_oob.add_rectangle([12000, 1000, 13334, 2000], id="oob_x")
    c_oob.add_rectangle([1000, -1, 2000, 1000], id="oob_y")
    r_oob = c_oob.verify_layout()
    assert r_oob.ok is False
    assert any("oob_x" in msg for msg in r_oob.out_of_bounds)
    assert any("oob_y" in msg for msg in r_oob.out_of_bounds)

    # 2. Rotated text overlap & rotated text OOB
    c_rot_ov = DrawPlusCanvas()
    c_rot_ov.add_text([2600, 1550, 3800, 1900], "TARGET", font_pt=14.0, align="center", id="target")
    c_rot_ov.add_text([2000, 2000, 4400, 2350], "ROTATED OVERLAP", font_pt=14.0, align="center", rotation=90.0, id="rot_ov")
    r_rot_ov = c_rot_ov.verify_layout()
    assert r_rot_ov.ok is False
    assert any("target overlaps rot_ov" in msg for msg in r_rot_ov.overlaps)

    c_rot_oob = DrawPlusCanvas()
    c_rot_oob.add_text([2000, 200, 5000, 550], "CLIPPED ROTATED", font_pt=14.0, align="center", rotation=90.0, id="rot_oob")
    r_rot_oob = c_rot_oob.verify_layout()
    assert r_rot_oob.ok is False
    assert any("rot_oob" in msg for msg in r_rot_oob.out_of_bounds)

    # 3. 2-coord text vertical origin parity: valign="top" renders below py (valid), valign="baseline" clips above y=0 (rejected)
    c_top = DrawPlusCanvas(background=WHITE)
    c_top.add_text([1000, 100], "TOP HEADER", font_pt=30.0, valign="top", id="top_2c")
    assert c_top.verify_layout().ok is True
    im_top = c_top.render_pil(width=1920, height=1080)
    top_bleed = sum(1 for x in range(100, 700) for y in range(0, 14) if im_top.getpixel((x, y)) != (255, 255, 255))
    assert top_bleed == 0

    c_base = DrawPlusCanvas(background=WHITE)
    c_base.add_text([1000, 100], "CLIPPED BASELINE", font_pt=30.0, valign="baseline", id="base_2c")
    r_base = c_base.verify_layout()
    assert r_base.ok is False
    assert any("base_2c" in msg for msg in r_base.out_of_bounds)


def test_vdi_5_99_short_record_validation_and_arc_arrowheads():
    header = struct.pack("<24h", -1, 24, 101, 2, 0, 0, 1000, 1000, 2540, 2540, 0, 0, 1000, 1000, 0, *([0] * 9))
    for bad_values in ([vdi.META_PAGESIZE, 100], [vdi.META_COORDS, 0, 0, 100], [vdi.META_GROUP], [vdi.META_OBJECT]):
        bad_rec = vdi._record(5, 99, values=bad_values)
        with pytest.raises(ValueError):
            vdi.scene_from_metafile(header + bad_rec + struct.pack("<h", -1))

    # Arc & ellarc arrowheads in Cairo + SVG
    c_no = DrawPlusCanvas(width=1000, height=1000, background=WHITE)
    c_no.add_arc(500, 500, 300, 0, 900, stroke="#FF0000", width=16, line_ends=(0, 0))
    im_no = c_no.render_pil(width=500, height=500)

    c_arr = DrawPlusCanvas(width=1000, height=1000, background=WHITE)
    c_arr.add_arc(500, 500, 300, 0, 900, stroke="#FF0000", width=16, line_ends=(1, 1))
    im_arr = c_arr.render_pil(width=500, height=500)
    svg_arr = c_arr.render_svg(width=500)
    assert svg_arr.count("<polygon") == 2
    diff_beg = sum(1 for x in range(370, 430) for y in range(200, 260) if im_no.getpixel((x, y)) != im_arr.getpixel((x, y)))
    diff_end = sum(1 for x in range(240, 300) for y in range(70, 130) if im_no.getpixel((x, y)) != im_arr.getpixel((x, y)))
    assert diff_beg > 50 and diff_end > 50


def test_transforms_sync_position_rotate_90_wrap_bold_bullets_and_card_corners():
    # 1. flip_h / flip_v sync position from bounds
    c = DrawPlusCanvas()
    tid = c.add_text([100, 100, 500, 300], "Sync Pos", align="left", id="t_sync")
    c.flip_h([tid], axis_x=500.0)
    el = c._by_id(tid)
    assert el["bounds"] == [500.0, 100.0, 900.0, 300.0]
    assert el["position"][0] == pytest.approx(500.0)
    c.flip_v([tid], axis_y=400.0)
    assert el["bounds"] == [500.0, 500.0, 900.0, 700.0]
    assert el["position"][1] > 500.0

    # 2. rotate_90 keeps logical wrap width consistent (no bogus wrap overflow)
    c_rot = DrawPlusCanvas()
    wide_id = c_rot.add_text([1000, 1000, 3000, 1500], "Wide Headline Text", font_pt=14.0, align="center", id="wide_rot")
    c_rot.rotate_90([wide_id], ccw=True)
    assert c_rot._by_id(wide_id)["rotation"] == 90.0
    assert c_rot.verify_layout().ok is True

    # 3. Bold lead-in paragraphs wrap identically in verify_layout() and render.py
    c_bul = DrawPlusCanvas()
    c_bul.add_bullets(
        [1000, 1000, 3000, 1450],
        [("Bold Lead Phrase That Forces Wrap:", "trailing text")],
        font_pt=12.0,
        id="bul_tight",
    )
    assert c_bul.verify_layout().ok is False  # overflows 450-VDI height box when wrapped with bold lead metrics

    # 4. add_card top accent strip stays strictly inside rounded card corners
    c_card = DrawPlusCanvas(width=1000, height=1000, background=WHITE)
    c_card.add_card([100, 100, 900, 900], fill=PORCELAIN, border_color=INK, accent_color=RUBY, accent_height=55, radius=90)
    im_card = c_card.render_pil(width=500, height=500)
    corner_px = im_card.getpixel((51, 51))
    assert corner_px[0] > 240 and corner_px[1] > 240 and corner_px[2] > 240


def test_add_bullets_embedded_newlines_blank_lines_and_double_spaces():
    c = DrawPlusCanvas(background=WHITE)
    c.add_bullets(
        [1000, 1000, 6000, 3500],
        [("Lead:", "LineA\nLineB\n\nLineC")],
        font_pt=18.0,
        body_color="#000000",
        lead_color="#B81D48",
    )
    svg = c.render_svg(width=1920)
    root = ET.fromstring(svg)
    tspans = [
        (sp.text, sp.attrib.get("fill"), sp.attrib.get("font-weight"))
        for sp in root.iter()
        if sp.tag.endswith("tspan")
    ]
    assert all("\n" not in (txt or "") for txt, _, _ in tspans)
    assert tspans == [
        ("Lead: ", "#B81D48", "bold"),
        ("LineA", "#000000", "normal"),
        ("LineB", "#000000", "normal"),
        ("LineC", "#000000", "normal"),
    ]

    im_nl = c.render_pil(width=1920, height=1080)
    c_clean = DrawPlusCanvas(background=WHITE)
    c_clean.add_bullets([1000, 1000, 6000, 3500], [("", "LineB")], font_pt=18.0, body_color="#000000", lead_color="#000000")
    im_clean = c_clean.render_pil(width=1920, height=1080)

    def _bands(im: Image.Image) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        in_band = False
        start_y = 0
        for y in range(100, 500):
            has_ink = any(cast(tuple[int, ...], im.getpixel((x, y)))[:3] != (255, 255, 255) for x in range(150, 900))
            if has_ink and not in_band:
                in_band = True
                start_y = y
            elif not has_ink and in_band:
                in_band = False
                out.append((start_y, y - 1))
        return out

    def _band_max_x(im: Image.Image, y0: int, y1: int) -> int:
        return max(
            x
            for y in range(y0, y1 + 1)
            for x in range(150, 900)
            if cast(tuple[int, ...], im.getpixel((x, y)))[:3] != (255, 255, 255)
        )

    bands = _bands(im_nl)
    assert len(bands) == 3  # LineA, LineB, [blank gap], LineC
    gap_ab = bands[1][0] - bands[0][1]
    gap_bc = bands[2][0] - bands[1][1]
    assert gap_bc > gap_ab * 2

    clean_bands = _bands(im_clean)
    assert len(clean_bands) == 1
    assert _band_max_x(im_nl, bands[1][0], bands[1][1]) == _band_max_x(im_clean, clean_bands[0][0], clean_bands[0][1])

    # Double spaces preserved & wrapped cleanly without truncating subsequent word
    c_sp = DrawPlusCanvas(background=WHITE)
    c_sp.add_bullets(
        [1000, 1000, 2350, 3500],
        [("Spaced:", "Word1  Word2")],
        font_pt=18.0,
        body_color="#000000",
        lead_color="#B81D48",
    )
    svg_sp = c_sp.render_svg(width=1920)
    root_sp = ET.fromstring(svg_sp)
    sp_texts = [sp.text for sp in root_sp.iter() if sp.tag.endswith("tspan")]
    assert sp_texts == ["Spaced:", "Word1 ", "Word2"]


def test_boxed_bounded_text_with_rotation_rotates_border_in_svg_cairo_and_layout():
    c = DrawPlusCanvas(background=WHITE)
    c.add_text(
        [4000, 3000, 6000, 3500],
        "BOXED",
        font_pt=14.0,
        boxed=True,
        box_stroke="#FF0000",
        rotation=90.0,
        color="#000000",
    )
    svg = c.render_svg(width=1920)
    root = ET.fromstring(svg)
    rot_groups = [
        g for g in root.iter()
        if g.tag.endswith("g") and "rotate(-90 5000 3250)" in g.attrib.get("transform", "")
    ]
    assert len(rot_groups) == 1
    assert any(child.tag.endswith("rect") for child in rot_groups[0])

    im = c.render_pil(width=1920, height=1080)

    def _vdi_px(vx: float, vy: float) -> tuple[int, int, int]:
        return im.getpixel((round(vx * 1920 / CANVAS_WIDTH), round(vy * 1080 / CANVAS_HEIGHT)))[:3]

    assert _vdi_px(4005, 3000) == (255, 255, 255)
    r, g, b = _vdi_px(5000, 2252)
    assert r > 200 and g < 80 and b < 80

    # verify_layout() must account for the rotated box bounds even when glyphs are narrower than the box
    c_edge = DrawPlusCanvas(background=WHITE)
    c_edge.add_text(
        [4000, 200, 6000, 700],
        "HI",
        font_pt=10.0,
        align="center",
        boxed=True,
        box_stroke="#FF0000",
        rotation=90.0,
        id="rot_box_edge",
    )
    rep = c_edge.verify_layout()
    assert rep.ok is False
    assert any("rot_box_edge" in msg for msg in rep.out_of_bounds)


# ---------------------------------------------------------------------------
# 4. M1B: Compatibility Bridges, WordChart, Graph, SlideShow, Ledger & CLI
# ---------------------------------------------------------------------------

def test_m1a_to_m1b_compatibility_bridges_and_constitutional_metadata():
    from guiai.gem.presentation import (
        BOTANICAL_PALETTE,
        DEFAULT_CONSTITUTIONAL,
        presentation_package_summary,
        verify_presentation_exports,
    )

    assert BOTANICAL_PALETTE["ruby"] == RUBY
    assert DEFAULT_CONSTITUTIONAL["operational_metacognition_verified"] is True
    assert DEFAULT_CONSTITUTIONAL["l5_agi_qualified"] is False
    assert "WordChartDoc" in verify_presentation_exports()
    assert presentation_package_summary()["templates"] == 11

    c = DrawPlusCanvas()
    r1 = c.add_rect(400, 400, 2000, 1400, rounded=True, fill=WHITE, stroke=RUBY)
    r2 = c.add_rect(2600, 400, 4200, 1400, fill=WHITE, stroke=JADE)
    r3 = c.add_rect(4800, 400, 6400, 1400, fill=WHITE, stroke=INK)
    c.add_line(400, 1800, 6400, 1800, stroke=INK)
    t1 = c.add_text(1000, 3200, "Rot900", size=240, rotation=900, color=INK)
    assert c._by_id(t1)["rotation"] == pytest.approx(90.0)
    gid = c.group([r1, r2], name="pair")
    assert gid == "pair"
    c.align([r1, r2, r3], mode="middle")
    c.even_spacing([r1, r2, r3], axis="x")
    c.autogrid_snap([r1, r2, r3], step=100)
    c.add_botanical_frame()
    c.add_lotus_divider(y=2300)
    c.add_hero_mandala(cx=6666, cy=4800, radius=1000, petals=9)
    assert c.verify_layout().ok is True

    gem_bytes = c.to_gem_bytes()
    assert seasip_gem.verify_seasip_gem_metafile(gem_bytes)["valid"] is True
    parsed = vdi.parse_metafile(gem_bytes)
    import json
    slide_metas = [
        json.loads(bytes(v & 0xFF for v in r["values"][1:]).split(b"\0", 1)[0].decode("ascii"))
        for r in parsed["records"]
        if r["command"] == 5 and r["subcommand"] == 99 and r["values"] and r["values"][0] == 1001
    ]
    const = slide_metas[0]["constitutional"]
    for key in ("operational_metacognition_verified", "sentience_claimed", "l5_agi_qualified", "zoe_clone_claimed", "clinical_action_authorized", "cure_claim", "external_actions"):
        assert key in const


def test_wordchart_zones_templates_rules_decimal_and_color0_locator(tmp_path: Path):
    from guiai.gem.presentation import VALID_TEMPLATES, LineBoxSpec, TextZone, WordChartDoc, validate_decimal_token

    assert validate_decimal_token("+$1,234.50") is True
    assert validate_decimal_token("-45.07%") is True
    assert validate_decimal_token("N/A") is False

    tz = TextZone(name="title", max_rows=2, rows=["Line 1"])
    with pytest.raises(ValueError):
        tz.delete_row()
    tz.add_row("Line 2")
    with pytest.raises(ValueError):
        tz.add_row("Line 3")
    tz.delete_row()
    tz.restore_zone(["Restored"])
    assert tz.rows == ["Restored"]

    for tpl in VALID_TEMPLATES:
        c = DrawPlusCanvas()
        WordChartDoc(
            title=f"Tpl {tpl}",
            column_head=["A", "B", "C", "D"],
            text_body=["One", "Two", "Three", "Four"],
            template=tpl,
            bullet_style="roman",
            lines_boxes=LineBoxSpec(box=True, rule_above=True, rule_below=True, rule_match="match_text"),
            footer="Zoe Clean-Room",
        ).compile(c)
        assert c.verify_layout().ok is True
        assert seasip_gem.verify_seasip_gem_metafile(c.to_gem_bytes())["valid"] is True

    # Strict decimal mode rejects non-numeric token
    with pytest.raises(ValueError):
        WordChartDoc(title="Strict", alignments=["decimal"], text_body=["N/A"], strict_decimal=True).compile(DrawPlusCanvas())

    # Classic DR Color-0 first-element locator rectangle in .GEM
    sc_color0 = Scene.from_dict({
        "schema_version": 1,
        "id": "color0_border",
        "title": "Color-0 Border",
        "canvas": {"width": 13333, "height": 7500},
        "objects": [
            {"id": "first_color0", "type": "rectangle", "bounds": [950, 950, 12383, 6550], "fill": "none", "stroke": "#ffffff", "width": 4},
            {"id": "gold_border", "type": "rectangle", "bounds": [300, 300, 13033, 7200], "fill": "none", "stroke": "#C29130", "width": 20},
        ],
    })
    c0_gem = tmp_path / "color0.gem"
    vdi.write_metafile(sc_color0, c0_gem)
    c_loc = DrawPlusCanvas()
    WordChartDoc(title="Color-0 Locator", text_body=["Fitted inside Color-0 locator"], border_gem_path=c0_gem).compile(c_loc)
    assert c_loc.verify_layout().ok is True


def test_graph_all_families_evidence_json_and_missing_negative_guards(tmp_path: Path):
    from guiai.gem.presentation import GraphDoc, GraphPreferences

    families = [
        ("pie", [35.0, 45.0, 20.0]),
        ("v_cluster", [10.0, 20.0, 30.0]),
        ("h_cluster", [10.0, 20.0, 30.0]),
        ("v_stack", [10.0, 20.0, 30.0]),
        ("h_stack", [10.0, 20.0, 30.0]),
        ("v_stack_100", [10.0, 20.0, 30.0]),
        ("deviation_bar", [34.52, -45.07, 8.48]),
        ("bar_3d", [12.0, 24.0, 18.0]),
        ("line", [1.0, 2.5, 4.0]),
        ("area", [2.0, 4.0, 3.0]),
        ("stacked_area", [2.0, 4.0, 3.0]),
        ("bar_line", [10.0, 20.0, 30.0]),
        ("step", [1.0, 3.0, 2.0]),
        ("stick", [2.0, -1.0, 3.0]),
        ("scatter", [1.5, 3.2, 2.8]),
        ("symbol", [2.0, 5.0, 3.0]),
        ("map", [15.0, 65.0, 92.0]),
    ]
    for ct, vals in families:
        c = DrawPlusCanvas()
        GraphDoc(
            title=f"Family {ct}",
            chart_type=ct,
            categories=["A", "B", "C"],
            series=[{"name": "S1", "values": vals}, {"name": "S2", "values": [abs(v) * 0.7 for v in vals]}],
            x_values=[1.0, 2.0, 3.0],
            preferences=GraphPreferences(explode_indices=(0,)),
        ).compile(c)
        assert c.verify_layout().ok is True, ct
        assert seasip_gem.verify_seasip_gem_metafile(c.to_gem_bytes())["valid"] is True

    # Evidence JSONs (CERN + L5 + Qwen2.5)
    for rel in (
        "evidence/cern-trigger/cern-kloster-trigger-report.json",
        "evidence/l5-phase2/l5-phase2-report.json",
    ):
        p = REPO_ROOT / rel
        if p.is_file():
            c_ev = DrawPlusCanvas()
            GraphDoc.from_json(p, chart_type="bar").compile(c_ev)
            assert c_ev.verify_layout().ok is True

    # Negative guard + allow_negative_abs
    with pytest.raises(ValueError):
        GraphDoc(title="Neg", chart_type="stacked_area", categories=["A", "B"], series=[{"name": "S", "values": [1.0, -2.0]}]).compile(DrawPlusCanvas())
    doc_abs = GraphDoc(
        title="Abs",
        chart_type="pie",
        categories=["A", "B"],
        series=[{"name": "S", "values": [10.0, -5.0]}],
        preferences=GraphPreferences(allow_negative_abs=True),
    )
    doc_abs.compile(DrawPlusCanvas())
    assert doc_abs.warnings


def test_slideshow_lis_player_playwright_ledger_and_cli(tmp_path: Path):
    import json
    import shutil
    from guiai.gem.code_elegance_analyzer import analyze_python_source
    from guiai.gem.presentation import (
        GraphDoc,
        Slide,
        SlideDeck,
        WordChartDoc,
        publish_ledger,
        scrub_hygiene,
        validate_lis_playlist,
        write_lis_playlist,
    )
    from guiai.gem.unified_cli import main as zoe_main

    # 1. Hygiene scrubber without raw personal literals
    dirty = "/" + "home" + "/alice/repo " + "/" + "media" + "/bob/vol " + "2A111" + "FDH12345 " + "sk-" + "ant-abc"
    cleaned = scrub_hygiene(dirty)
    assert "alice" not in cleaned and "bob" not in cleaned and "FDH12345" not in cleaned and "ant-abc" not in cleaned

    # 2. .LIS roundtrip
    s1_gem = tmp_path / "slide-01.gem"
    s1_gem.write_bytes(DrawPlusCanvas().to_gem_bytes())
    lis_p = tmp_path / "show.lis"
    write_lis_playlist(lis_p, [s1_gem], interval_seconds=10, cycle=True)
    pl = validate_lis_playlist(lis_p, check_exists=True)
    assert pl.wait_mode == "10s" and pl.cycle is True

    # 3. Publish ledger atomically (zero office subprocesses)
    d1 = SlideDeck(
        slug="unit-vol",
        title="Unit Anthology Vol. I",
        volume_label="Vol. I",
        slides=[
            Slide("Cover", WordChartDoc(title="Cover", template="hero_obsidian", text_body=["Operational Metacognition"]), speaker_notes="Notes 1"),
            Slide("Metrics", GraphDoc(title="Scores", chart_type="bar", categories=["M1", "M2"], series=[{"name": "S", "values": [0.84, 0.91]}]), speaker_notes="Notes 2"),
        ],
    )
    out_root = tmp_path / "ledger_root"
    with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess.run forbidden")), \
         mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess.Popen forbidden")):
        publish_ledger([d1], out_root, render_jpg=True, render_svg=True)

    assert (out_root / "catalog.json").is_file()
    assert (out_root / "SHA256SUMS.presentations").is_file()
    assert not list(out_root.rglob("*.tmp")) and not list(out_root.rglob("*.part"))
    player_html = out_root / "galleries" / "unit-vol" / "player.html"
    assert player_html.is_file()

    # Live Chromium Playwright check when available
    browser = next((shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser") if shutil.which(b)), None)
    if browser:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True, executable_path=browser)
            try:
                pg = br.new_page(viewport={"width": 1280, "height": 720})
                pg.goto(player_html.as_uri(), wait_until="domcontentloaded")
                t0 = pg.locator("body").inner_text()
                pg.keyboard.press("ArrowRight")
                t1 = pg.locator("body").inner_text()
                assert t1 != t0
                pg.keyboard.press("n")
                assert pg.locator("#notesDrawer").is_visible()
                pg.keyboard.press("g")
                assert pg.locator("#thumbGrid").is_visible()
                pg.keyboard.press("Escape")
                assert not pg.locator("#thumbGrid").is_visible()
            finally:
                br.close()

    # 4. CLI smoke via unified_cli.main
    demo_dir = tmp_path / "cli_demo"
    assert zoe_main(["present", "demo", "--output", str(demo_dir), "--json"]) == 0
    assert zoe_main(["present", "inspect", str(demo_dir / "slide-01.gem"), "--json"]) == 0
    assert zoe_main(["present", "play", str(demo_dir), "--no-open", "--json"]) == 0

    # 5. Elegance analyzer gates
    cli_rep = analyze_python_source((REPO_ROOT / "guiai-lab/guiai/gem/unified_cli.py").read_text(encoding="utf-8"), "unified_cli.py")
    assert cli_rep["grade"] == "A" and cli_rep["max_cc"] <= 20
    for pyf in sorted((REPO_ROOT / "guiai-lab/guiai/gem/presentation").glob("*.py")):
        rep = analyze_python_source(pyf.read_text(encoding="utf-8"), pyf.name)
        assert rep["grade"] in ("A", "B"), f"{pyf.name} scored {rep['grade']}"


def test_m1b_remediation_regressions(tmp_path: Path):
    import json
    import shutil
    from guiai.gem.presentation import (
        GraphDoc,
        Slide,
        SlideDeck,
        SlideShowPlayer,
        WordChartDoc,
        find_hygiene_violations,
        publish_ledger,
        scrub_hygiene,
    )

    # 1. GraphDoc step chart with None gap preserves gap, renders isolated point marker, distinct from 0
    c_gap = DrawPlusCanvas()
    GraphDoc(
        title="Step Gap",
        chart_type="step",
        categories=["A", "B", "C"],
        series=[{"name": "S", "values": [10.0, None, 30.0]}],
    ).compile(c_gap)
    assert c_gap.verify_layout().ok is True
    assert len([el for el in c_gap.elements if el["type"] == "ellipse"]) == 2
    c_zero = DrawPlusCanvas()
    GraphDoc(
        title="Step Gap",
        chart_type="step",
        categories=["A", "B", "C"],
        series=[{"name": "S", "values": [10.0, 0.0, 30.0]}],
    ).compile(c_zero)
    assert c_gap.render_svg() != c_zero.render_svg()

    # 2. DrawPlusCanvas-authored Color-0 border .GEM works without background="none"
    dp_border = DrawPlusCanvas(width=13333, height=7500)
    dp_border.add_rectangle([900, 900, 12433, 6600], fill="none", stroke="white", width=12.0)
    dp_border.add_rectangle([500, 500, 12833, 7000], fill="none", stroke=RUBY, width=24.0)
    dp_border_path = tmp_path / "dp_color0.gem"
    dp_border_path.write_bytes(dp_border.to_gem_bytes())
    c_wc_border = DrawPlusCanvas()
    WordChartDoc(title="DP Color-0", text_body=["Fitted"], border_gem=dp_border_path).compile(c_wc_border)
    assert c_wc_border.verify_layout().ok is True

    dp_no_loc = DrawPlusCanvas(width=13333, height=7500)
    dp_no_loc.add_rectangle([500, 500, 12833, 7000], fill="none", stroke=RUBY, width=24.0)
    dp_no_loc_path = tmp_path / "dp_noloc.gem"
    dp_no_loc_path.write_bytes(dp_no_loc.to_gem_bytes())
    with pytest.raises(ValueError):
        WordChartDoc(title="No Loc", text_body=["X"], border_gem=dp_no_loc_path).compile(DrawPlusCanvas())

    # 3. Card templates (pillar_3col, scorecard_2x2) enforce decimal validation & diagnostics
    for tpl in ("pillar_3col", "scorecard_2x2"):
        cols = [["12.3"], ["N/A"], ["45.6"]] if tpl == "pillar_3col" else [["12.3"], ["N/A"], ["45.6"], ["7.8"]]
        with pytest.raises(ValueError):
            WordChartDoc(
                title="Strict Card", template=tpl, columns=cols, alignments="decimal", strict_decimal=True,
            ).compile(DrawPlusCanvas())
        wc_diag = WordChartDoc(
            title="Soft Card", template=tpl, columns=cols, alignments="decimal", strict_decimal=False,
        )
        wc_diag.compile(DrawPlusCanvas())
        assert any("N/A" in d for d in wc_diag.diagnostics)

    # 4. publish_ledger(preserve_existing=True) unique sequential num + slug traversal rejection
    ledger_dir = tmp_path / "ledger_preserve"
    publish_ledger(
        [SlideDeck(slug="a", title="A1", slides=[Slide("S1")]), SlideDeck(slug="b", title="B1", slides=[Slide("S2")])],
        ledger_dir,
    )
    publish_ledger(
        [SlideDeck(slug="a", title="A2", slides=[Slide("S1")]), SlideDeck(slug="c", title="C1", slides=[Slide("S3")])],
        ledger_dir,
        preserve_existing=True,
    )
    cat = json.loads((ledger_dir / "catalog.json").read_text(encoding="utf-8"))
    assert [d["slug"] for d in cat["decks"]] == ["a", "b", "c"]
    assert [d["num"] for d in cat["decks"]] == ["01", "02", "03"]

    class _DuckDeck:
        slug = "../escaped_slug"
        title = "Bad"
        slides = [Slide("S1")]

    with pytest.raises(ValueError):
        publish_ledger([_DuckDeck()], ledger_dir)

    # 5. GraphDoc title_pt / label_pt + scrub_hygiene 2-slash file-URI alignment
    c_big = DrawPlusCanvas()
    GraphDoc(
        title="Enlarged Typography",
        chart_type="bar",
        categories=["Alpha", "Beta", "Gamma"],
        series=[{"name": "S1", "values": [12.0, 24.0, 18.0]}],
        x_label="Categories",
        y_label="Score",
        title_pt=36.0,
        label_pt=24.0,
    ).compile(c_big)
    assert c_big.verify_layout().ok is True

    two_slash = "file" + "://localhost/etc/passwd"
    scrubbed_uri = scrub_hygiene(two_slash)
    assert "localhost" not in scrubbed_uri
    assert find_hygiene_violations(scrubbed_uri, strict_file_scheme=True) == []
    assert scrub_hygiene("prose (file" + "://, ftp://)") == "prose (file" + "://, ftp://)"

    # 6. hygiene_scrubs real count & SlideShowPlayer safe DOM thumbnail grid
    dirty_root = tmp_path / "dirty_ledger"
    dirty_deck = SlideDeck(
        slug="dirty-deck",
        title="Deck " + "/" + "home" + "/alice/secret",
        slides=[
            Slide(
                title="Slide " + "2A111" + "FDH999",
                content=WordChartDoc(title="WC", text_body=["Disk " + "/" + "media" + "/bob/vol"]),
                speaker_notes="Contact " + "exile" + "kingdom@" + "proton.me",
            )
        ],
    )
    res_dirty = publish_ledger([dirty_deck], dirty_root)
    assert res_dirty["catalog"]["decks"][0]["hygiene_scrubs"] >= 3

    player = SlideShowPlayer(
        SlideDeck(slug="xss-safe", title="XSS Safe", slides=[Slide("S1")]),
        [{"index": 1, "title": '<img src=x onerror="window.__XSS=1">', "png_name": 'x" onerror="window.__XSS=1', "gem_name": "slide-01.gem", "speaker_notes": "Clean"}],
    )
    safe_html = player.render_html()
    assert "btn.innerHTML" not in safe_html
    assert 'document.createElement("img")' in safe_html
    browser = next((shutil.which(b) for b in ("google-chrome", "chromium", "chromium-browser") if shutil.which(b)), None)
    if browser:
        from playwright.sync_api import sync_playwright
        p_file = tmp_path / "safe_player.html"
        p_file.write_text(safe_html, encoding="utf-8")
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True, executable_path=browser)
            try:
                pg = br.new_page(viewport={"width": 1280, "height": 720})
                pg.goto(p_file.as_uri(), wait_until="domcontentloaded")
                assert pg.evaluate("Boolean(window.__XSS)") is False
                pg.keyboard.press("g")
                assert pg.locator("#thumbGrid .thumb-card").count() == 1
                assert pg.evaluate("Boolean(window.__XSS)") is False
            finally:
                br.close()


def test_m1b_r2_challenger_remediations(tmp_path: Path):
    import json
    from guiai.gem.presentation import GraphDoc, Slide, SlideDeck, WordChartDoc, publish_ledger

    # 1. h_cluster / h_stack with y_label & label_pt=24.0 on half-width and full-width regions
    for ct in ("h_cluster", "h_stack"):
        for reg in (None, (600.0, 500.0, 6200.0, 6800.0)):
            cv_h = DrawPlusCanvas()
            GraphDoc(
                title=f"Horizontal {ct}",
                chart_type=ct,
                categories=["Alpha Category", "Beta Category", "Gamma Category"],
                series=[{"name": "Series One", "values": [10.0, 25.0, 40.0]}, {"name": "Series Two", "values": [15.0, 20.0, 30.0]}],
                x_label="Score",
                y_label="Vertical Metric Units (%)",
                title_pt=36.0,
                label_pt=24.0,
            ).compile(cv_h, region=reg)
            rep_h = cv_h.verify_layout()
            assert rep_h.ok is True, f"{ct} {reg}: {rep_h}"
            assert seasip_gem.verify_seasip_gem_metafile(cv_h.to_gem_bytes())["valid"] is True

    # 2. Tight short region v_cluster & line with title_pt=36.0, label_pt=24.0
    for ct in ("v_cluster", "line"):
        for title in ("Tight Chart", "A Longer Multi Word Chart Title That Wraps In Tight Region"):
            cv_t = DrawPlusCanvas()
            GraphDoc(
                title=title,
                chart_type=ct,
                categories=["Cat A", "Cat B", "Cat C", "Cat D"],
                series=[{"name": "Series Alpha", "values": [12.0, 28.0, 19.0, 35.0]}],
                x_label="Very Long X Axis Label Here",
                y_label="Vertical Axis Metric (%)",
                title_pt=36.0,
                label_pt=24.0,
            ).compile(cv_t, region=(600.0, 500.0, 5400.0, 4400.0))
            rep_t = cv_t.verify_layout()
            assert rep_t.ok is True, f"tight {ct} {title!r}: {rep_t}"

    # 3. publish_ledger shrink (3 -> 1 slides) removes stale slide-02+ and old svg/jpg artifacts
    shrink_root = tmp_path / "shrink_ledger"
    publish_ledger(
        [SlideDeck(slug="shrink-me", title="Three Slides", slides=[Slide("S1"), Slide("S2"), Slide("S3")])],
        shrink_root,
        render_jpg=True,
        render_svg=True,
    )
    publish_ledger(
        [SlideDeck(slug="shrink-me", title="One Slide", slides=[Slide("S1 Updated")])],
        shrink_root,
        preserve_existing=True,
        render_jpg=False,
        render_svg=False,
    )
    cat = json.loads((shrink_root / "catalog.json").read_text(encoding="utf-8"))
    entry = cat["decks"][0]
    assert entry["slides"] == 1
    assert len(entry["gems"]) == 1
    assert entry["gems"] == ["galleries/shrink-me/slide-01.gem"]
    gal_files = sorted(p.name for p in (shrink_root / "galleries" / "shrink-me").glob("slide-*.*"))
    assert gal_files == ["slide-01.gem", "slide-01.png"]
    sums_txt = (shrink_root / "SHA256SUMS.presentations").read_text(encoding="utf-8")
    assert "slide-02" not in sums_txt and "slide-03" not in sums_txt
    assert ".svg" not in sums_txt and ".jpg" not in sums_txt

    # 4. DrawPlusCanvas(background="white") with no locator rect raises ValueError; inset Color-0 locator works
    bg_white_noloc = DrawPlusCanvas(width=13333, height=7500, background="white")
    bg_white_noloc.add_rectangle([500, 500, 12833, 7000], fill="none", stroke=RUBY, width=24.0)
    noloc_gem = tmp_path / "white_bg_noloc.gem"
    noloc_gem.write_bytes(bg_white_noloc.to_gem_bytes())
    with pytest.raises(ValueError, match="Border .GEM lacks a locator rectangle"):
        WordChartDoc(title="NoLoc", text_body=["X"], border_gem=noloc_gem).compile(DrawPlusCanvas())

    bg_white_only = DrawPlusCanvas(width=13333, height=7500, background="white")
    only_gem = tmp_path / "white_bg_only.gem"
    only_gem.write_bytes(bg_white_only.to_gem_bytes())
    with pytest.raises(ValueError, match="Border .GEM lacks a locator rectangle"):
        WordChartDoc(title="OnlyBg", text_body=["X"], border_gem=only_gem).compile(DrawPlusCanvas())

    bg_white_loc = DrawPlusCanvas(width=13333, height=7500, background="white")
    bg_white_loc.add_rectangle([900, 900, 12433, 6600], fill="none", stroke="white", width=12.0)
    bg_white_loc.add_rectangle([500, 500, 12833, 7000], fill="none", stroke=RUBY, width=24.0)
    loc_gem = tmp_path / "white_bg_loc.gem"
    loc_gem.write_bytes(bg_white_loc.to_gem_bytes())
    cv_w = DrawPlusCanvas()
    WordChartDoc(title="WhiteBgLoc", text_body=["Fitted"], border_gem=loc_gem).compile(cv_w)
    assert cv_w.verify_layout().ok is True

    # 5. SlideDeck(slug=".") raises ValueError at construction time
    with pytest.raises(ValueError):
        SlideDeck(slug=".", title="Dot Slug", slides=[Slide("S1")])


def test_publish_ledger_relative_out_root_lis_paths_and_alt_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from guiai.gem.presentation import (
        Slide,
        SlideDeck,
        WordChartDoc,
        publish_ledger,
        validate_lis_playlist,
        write_lis_playlist,
    )

    monkeypatch.chdir(tmp_path)
    deck = SlideDeck(
        slug="vol-rel-check",
        title="Vol. I — Relative Path Regression",
        volume_label="Vol. I",
        slides=[
            Slide("Cover", WordChartDoc(title="Cover", text_body=["Relative out_root check"])),
        ],
    )
    res = publish_ledger([deck], "rel_presentations", preserve_existing=False, render_jpg=False)
    assert Path(res["out_root"]).is_absolute()

    lis_path = Path("rel_presentations/galleries/vol-rel-check/vol-rel-check.lis")
    pl = validate_lis_playlist(lis_path, check_exists=True)
    assert [entry.path for entry in pl.slides] == ["slide-01.gem"]
    lis_text = lis_path.read_text(encoding="utf-8")
    assert "rel_presentations/" not in lis_text
    assert str(tmp_path) not in lis_text

    hub_md = Path("rel_presentations/README.md").read_text(encoding="utf-8")
    assert 'alt="Vol. I — Relative Path Regression"' in hub_md
    assert "Vol. I: Vol. I" not in hub_md
    for rel_artifact in (
        "rel_presentations/catalog.json",
        "rel_presentations/README.md",
        "rel_presentations/galleries/vol-rel-check/player.html",
        "rel_presentations/galleries/vol-rel-check/README.md",
    ):
        assert str(tmp_path) not in Path(rel_artifact).read_text(encoding="utf-8")
    cat = json.loads(Path("rel_presentations/catalog.json").read_text(encoding="utf-8"))
    assert cat["decks"][0]["lis"] == "galleries/vol-rel-check/vol-rel-check.lis"

    rel_sub = Path("rel_lis_dir/sub")
    rel_sub.mkdir(parents=True)
    (rel_sub / "slide-01.gem").write_bytes(DrawPlusCanvas().to_gem_bytes())
    direct_lis = write_lis_playlist(
        Path("rel_lis_dir/direct.lis"),
        [Path("rel_lis_dir/sub/slide-01.gem")],
    )
    direct_pl = validate_lis_playlist(direct_lis, check_exists=True)
    assert [entry.path for entry in direct_pl.slides] == ["sub/slide-01.gem"]

    pending_lis = write_lis_playlist(Path("rel_lis_dir/pending.lis"), ["slides/a.gem"])
    assert [entry.path for entry in validate_lis_playlist(pending_lis, check_exists=False).slides] == ["slides/a.gem"]





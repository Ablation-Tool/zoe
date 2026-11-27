"""Unit tests for Zoe Artline Forge (.AF4/.SYF decoders, ZOETK001 toolboxes, GEM .COL palettes, /forge UI)."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.vdi import VdiMetafileBuilder, _record, parse_metafile
from guiai.gem.zoe_artline_cli import main as artline_cli_main
from guiai.gem.zoe_artline_forge import (
    CONSTITUTIONAL_FLAGS,
    DEFAULT_EXTRACTED_ROOT,
    STUDIO_PALETTES,
    STUDIO_TOOLBOXES,
    ZoeToolboxSpec,
    _archive_fingerprint,
    _build_af4_font_preview_entry,
    _collect_live_forge_vectors,
    build_synthetic_af4_bytes,
    build_synthetic_col_bytes,
    build_synthetic_gem_bytes,
    build_synthetic_syf_bytes,
    build_synthetic_tls_bytes,
    clear_forge_cache,
    contours_to_svg_path,
    decode_af4_bytes,
    decode_ccp_segments,
    decode_col_bytes,
    decode_col_file,
    decode_syf_bytes,
    decode_tls_bytes,
    decode_tls_file,
    export_forge_artifact,
    get_af4_font_payload,
    get_forge_catalog,
    inspect_gem_bytes,
    inspect_gem_file,
    render_af4_catalog_poster_png,
    render_af4_specimen_png,
    render_af4_typeset_png,
    render_artline_forge_html,
    render_syf_contact_sheet_png,
    typeset_af4_text_layout,
    typeset_af4_text_svg,
    typeset_af4_text_to_artline_doc,
    write_interactive_artline_forge_html,
)

NODE_BIN = shutil.which("node") or "/home/cowboy/.nvm/versions/node/v24.16.0/bin/node"


def _assert_inline_js_valid(html: str) -> None:
    if Path(NODE_BIN).is_file():
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
        assert scripts
        for js in scripts:
            proc = subprocess.run([NODE_BIN, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
            assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")


def test_clean_room_af4_and_syf_decoders_and_contact_sheets(tmp_path: Path) -> None:
    af4 = decode_af4_bytes(build_synthetic_af4_bytes(), "zoe_synth.af4")
    assert af4.font_id == 129
    assert 78 in af4.glyphs_by_char and 90 in af4.glyphs_by_char
    assert af4.glyphs_by_char[90].svg_path.startswith("M")
    af4_png = render_af4_specimen_png(af4, tmp_path / "af4_specimen.png", cols=2)
    assert Path(af4_png["path"]).is_file() and af4_png["bytes"] > 1000

    syf = decode_syf_bytes(build_synthetic_syf_bytes(), "zoe_synth.syf")
    assert syf.magic == "CCPA002"
    assert len(syf.symbols) == 2
    assert syf.symbols[0].name == "ZOE HEX"
    assert syf.symbols[1].name == "NICK STAR"
    syf_png = render_syf_contact_sheet_png(syf, tmp_path / "syf_sheet.png", cols=2)
    assert Path(syf_png["path"]).is_file() and syf_png["bytes"] > 1000

    # Read-only 1990 CCPTK001 .TLS binary inspector + multi-font AF4 poster
    tls = decode_tls_bytes(build_synthetic_tls_bytes(), "synth.tls")
    assert tls.magic == "CCPTK001"
    assert tls.tool_count == 4
    assert [t.name for t in tls.tools] == ["Selector", "Bezier", "Rosette", "Align"]

    poster = render_af4_catalog_poster_png([af4], tmp_path / "af4_atlas.png")
    assert Path(poster["path"]).is_file() and poster["bytes"] > 1000 and poster["rendered_fonts"] == 1


def test_programmable_zoetk_toolboxes_and_col_gem_palettes(tmp_path: Path) -> None:
    assert len(STUDIO_TOOLBOXES) == 4
    for tb in STUDIO_TOOLBOXES:
        raw = tb.to_zoetk_binary()
        assert raw.startswith(b"ZOETK001")
        rt = ZoeToolboxSpec.from_zoetk_binary(raw)
        assert rt == tb

    assert len(STUDIO_PALETTES) == 4
    for pal in STUDIO_PALETTES:
        res = pal.export_col_gem(tmp_path)
        assert res["valid_gem_header"] is True
        assert res["gem_bytes"] > 100
        assert Path(res["svg_path"]).stat().st_size > 1000


def test_artline_forge_html_and_inline_js_valid(tmp_path: Path) -> None:
    raw = render_artline_forge_html()
    html = raw.decode("utf-8")
    assert "Zoe Artline Forge" in html
    assert "0 Cloud Tokens" in html
    assert "sentience_claimed=False" in html
    assert "clinical_action_authorized=False" in html

    out_p = write_interactive_artline_forge_html(tmp_path / "forge.html")
    assert out_p.is_file() and out_p.stat().st_size > 4000
    assert "runTool" in html
    assert "mirror_h" in html
    assert "snap_grid" in html
    assert "align_cc" in html
    assert "phys_grav" in html
    assert 'fill-rule="evenodd"' in html
    assert "renderTypesetPreview" in html
    _assert_inline_js_valid(html)


def test_f5_forge_memoization_thread_safety_and_synthetic_fallback(tmp_path: Path) -> None:
    clear_forge_cache()
    missing_root = tmp_path / "nonexistent_extracted"

    cat1 = get_forge_catalog(missing_root)
    assert cat1["source_mode"] == "portable_clean_room_synth"
    assert cat1["font_count"] == 1
    assert cat1["syf_total"] == 2
    assert len(cat1["col_palettes"]) == 1
    assert len(cat1["gem_samples"]) == 1
    assert cat1["constitutional_flags"]["cloud_tokens_used"] == 0
    assert cat1["constitutional_flags"]["proprietary_code_copied"] == 0

    # Caller mutation must not corrupt cached bundles
    cat1["fonts"].clear()
    cat1["col_palettes"][0]["swatches"].clear()

    t0 = time.perf_counter()
    cat2 = get_forge_catalog(missing_root)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.1
    assert len(cat2["fonts"]) == 1
    assert len(cat2["col_palettes"][0]["swatches"]) == 16

    # _collect_live_forge_vectors isolation + archive fallback
    v1 = _collect_live_forge_vectors(missing_root)
    v2 = _collect_live_forge_vectors(missing_root)
    v1["syf_packs"].clear()
    assert "SYNTH" in v2["syf_packs"]

    # Concurrent reads under ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: render_artline_forge_html(missing_root), range(6)))
    assert all(isinstance(r, bytes) and b"Zoe Artline Forge" in r for r in results)

    # Archive directory mtime invalidation
    fonts_dir = tmp_path / "arch" / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "one.af4").write_bytes(build_synthetic_af4_bytes())
    arch_cat1 = get_forge_catalog(tmp_path / "arch")
    assert arch_cat1["source_mode"] == "authentic_local_1990_archive"
    assert arch_cat1["font_count"] == 1

    (fonts_dir / "two.af4").write_bytes(build_synthetic_af4_bytes())
    arch_cat2 = get_forge_catalog(tmp_path / "arch")
    assert arch_cat2["font_count"] == 2


def test_f6_af4_kerning_and_clean_room_typesetter(tmp_path: Path) -> None:
    missing_root = tmp_path / "nonexistent"
    af4 = decode_af4_bytes(build_synthetic_af4_bytes(), "zoe_synth.af4")
    assert af4.space_width == 320
    assert af4.kerning_delta("N", "Z") == -80
    assert af4.kerning_delta("Z", "N") == 40

    payload = get_af4_font_payload("zoe_synth", archive_root=missing_root)
    assert payload["metrics"]["space_width"] == 320
    assert len(payload["kerning_pairs"]) == 2
    assert payload["constitutional_flags"]["cloud_tokens_used"] == 0

    with pytest.raises(KeyError):
        get_af4_font_payload("no_such_font_999", archive_root=missing_root)

    svg_kern = typeset_af4_text_svg("zoe_synth.af4", "NZ ZN", archive_root=missing_root, use_kerning=True)
    svg_nokern = typeset_af4_text_svg("zoe_synth.af4", "NZ ZN", archive_root=missing_root, use_kerning=False)
    assert "<svg" in svg_kern and 'fill-rule="evenodd"' in svg_kern
    assert 'data-kerning-applied="2"' in svg_kern
    assert 'data-kerning-applied="0"' in svg_nokern
    assert svg_kern != svg_nokern

    png_info = render_af4_typeset_png("zoe_synth", "NZ ZN", tmp_path / "typeset.png", archive_root=missing_root)
    assert Path(png_info["path"]).is_file() and png_info["bytes"] > 500
    assert png_info["kerning_applied_count"] == 2

    doc = typeset_af4_text_to_artline_doc("zoe_synth", "NZ ZN", archive_root=missing_root)
    gem_out = tmp_path / "typeset.gem"
    doc.export(gem_out, kind="gem")
    raw_gem = gem_out.read_bytes()
    assert raw_gem[:2] == b"\xff\xff"
    assert parse_metafile(raw_gem)["bytes_consumed"] == len(raw_gem)


def test_f7_col_decoder_gem_inspector_and_tls_bitmap_icons(tmp_path: Path) -> None:
    # 1. .COL decoder (both Escape 5/99/201 and vs_color 14)
    col_pal = decode_col_bytes(build_synthetic_col_bytes(), "synth.col")
    assert col_pal.swatch_count == 16  # 8 Escape 5/99/201 + 8 vs_color 14
    assert col_pal.swatches[0].name == "Zoe Ruby"
    assert col_pal.swatches[0].hex_color == "#f35670"
    zoe_pal = col_pal.to_zoe_palette()
    res = zoe_pal.export_col_gem(tmp_path)
    assert res["valid_gem_header"] is True

    # 2. .GEM inspector (valid + degenerate <3-pt fillarea resilience)
    gem_rep = inspect_gem_bytes(build_synthetic_gem_bytes(), "synth.gem")
    assert gem_rep["primitive_counts"]["fillarea"] >= 1
    assert 'fill-rule="evenodd"' in gem_rep["preview_svg"]
    assert gem_rep["constitutional_flags"]["cloud_tokens_used"] == 0

    hdr = struct.pack(
        "<24h", -1, 24, 310, 2, 0, 0, 100, 100, 1000, 1000, 0, 0, 100, 100,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    degen_gem = hdr + _record(9, points=[(10, 10), (50, 50)]) + _record(6, points=[(0, 0), (90, 90)]) + struct.pack("<h", -1)
    degen_rep = inspect_gem_bytes(degen_gem, "degen.gem")
    assert degen_rep["primitive_counts"]["skipped_degenerate"] == 1
    assert degen_rep["primitive_counts"]["pline"] == 1

    # 3. .TLS 32x28 icon bitmap decoder + synthetic fallback
    synth_tls = decode_tls_bytes(build_synthetic_tls_bytes(), "synth.tls")
    assert all(t.icon_width == 0 and t.icon_svg_path == "" for t in synth_tls.tools)

    icon_chunk = bytearray(200)
    struct.pack_into("<HH", icon_chunk, 14, 32, 28)
    struct.pack_into("<HH", icon_chunk, 88, 0xFFFF, 0x0000)  # row 0: left 16 px on
    struct.pack_into("<HH", icon_chunk, 92, 0x0000, 0xFFFF)  # row 1: right 16 px on
    table_end = 13 + 17
    tls_buf = (
        b"CCPTK001\x00"
        + struct.pack("<HH", 1, 36)
        + struct.pack("<I", table_end)
        + b"TestIcon\x00\x00\x00\x00\x00"
        + bytes(icon_chunk)
    )
    bmp_tls = decode_tls_bytes(tls_buf, "bmp.tls")
    assert bmp_tls.tools[0].icon_width == 32
    assert bmp_tls.tools[0].icon_height == 28
    assert "M0,0h16v1h-16z" in bmp_tls.tools[0].icon_svg_path
    assert "M16,1h16v1h-16z" in bmp_tls.tools[0].icon_svg_path
    assert bmp_tls.summary_dict()["tools"][0]["icon_svg_path"] == bmp_tls.tools[0].icon_svg_path


def test_f8_bezier_svg_export_artifact_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    coords = [(0, 0), (100, 300), (300, 300), (400, 0), (0, 0)]
    flags = [0x21, 0x18, 0x18, 0x08, 0x08]
    segs = decode_ccp_segments(coords, flags)
    assert len(segs) == 1 and segs[0][1][0] == "C"

    d_bezier = contours_to_svg_path([], flip_y=True, bezier_segments=segs)
    assert d_bezier.startswith("M") and "C" in d_bezier and d_bezier.endswith("Z")

    d_smooth = contours_to_svg_path([[(0.0, 0.0), (50.0, 100.0), (100.0, 0.0)]], smooth=True)
    assert d_smooth.startswith("M") and "C" in d_smooth

    stamps = [
        {"d": "M20,20 L80,20 L80,80 L20,80 Z", "x": 200, "y": 200, "s": 1.0, "rot": 15, "flipH": True, "col": "#5ce1e6"},
        {"d": d_bezier, "x": 400, "y": 200, "s": 0.9, "rot": 0, "col": "#f8cc30"},
    ]
    for kind in ("gem", ".SVG", "zoetk", "json"):
        exp = export_forge_artifact(kind, {"stamps": stamps, "toolbox_id": "align_9way"})
        assert exp["ok"] is True
        assert exp["cloud_tokens_used"] == 0
        assert exp["constitutional_flags"]["proprietary_code_copied"] == 0
        raw = base64.b64decode(exp["content_base64"])
        assert len(raw) == exp["bytes_len"]
        if exp["kind"] == "gem":
            assert raw[:2] == b"\xff\xff"
            assert parse_metafile(raw)["bytes_consumed"] == len(raw)
        elif exp["kind"] == "svg":
            txt = raw.decode("utf-8")
            assert "<svg" in txt and 'fill-rule="evenodd"' in txt
        elif exp["kind"] == "zoetk":
            rt = ZoeToolboxSpec.from_zoetk_binary(raw)
            assert rt.toolbox_id == "align_9way"
        elif exp["kind"] == "json":
            doc = json.loads(raw.decode("utf-8"))
            assert len(doc["stamps"]) == 2

    with pytest.raises(ValueError):
        export_forge_artifact("exe", {})

    # CLI forge subcommand with new flags using synthetic inputs
    gem_file = tmp_path / "sample.gem"
    gem_file.write_bytes(build_synthetic_gem_bytes())
    col_file = tmp_path / "sample.col"
    col_file.write_bytes(build_synthetic_col_bytes())
    missing_root = tmp_path / "no_archive"

    rc = artline_cli_main([
        "--out-dir", str(tmp_path / "cli_out"),
        "--json",
        "forge",
        "--archive-root", str(missing_root),
        "--text", "NZ",
        "--font", "zoe_synth.af4",
        "--inspect-gem", str(gem_file),
        "--inspect-col", str(col_file),
        "--export-summary",
    ])
    assert rc == 0
    cli_res = json.loads(capsys.readouterr().out)
    assert "Zoe Artline Forge Exported" in cli_res["reply"]
    assert cli_res["cloud_tokens_used"] == 0
    assert (tmp_path / "cli_out" / "forge" / "typeset.svg").is_file()
    assert (tmp_path / "cli_out" / "forge" / "typeset.gem").is_file()
    assert (tmp_path / "cli_out" / "forge" / "sample.inspect.json").is_file()
    assert (tmp_path / "cli_out" / "forge" / "sample.col.json").is_file()
    assert (tmp_path / "cli_out" / "forge" / "forge_catalog_summary.json").is_file()


@pytest.mark.skipif(not DEFAULT_EXTRACTED_ROOT.is_dir(), reason="Extracted 1990 Artline archive not mounted")
def test_extracted_1990_archive_all_35_fonts_col_gem_and_tls() -> None:
    clear_forge_cache()
    t0 = time.perf_counter()
    cat = get_forge_catalog()
    cold_s = time.perf_counter() - t0
    assert cat["source_mode"] == "authentic_local_1990_archive"
    assert cat["font_count"] == 35
    assert cat["syf_total"] == 378
    assert len(cat["tls_toolboxes"]) == 7
    assert len(cat["col_palettes"]) == 7

    t1 = time.perf_counter()
    cat_cached = get_forge_catalog()
    warm_s = time.perf_counter() - t1
    assert warm_s < 0.1
    assert warm_s <= cold_s
    assert cat_cached["font_count"] == 35

    # Composite glyphs + <hBB kerning on advtg_n & advtg_b
    adv_n = get_af4_font_payload("advtg_n.af4")
    codes_n = {g["code"] for g in adv_n["glyphs"]}
    assert 44 in codes_n and 59 in codes_n  # ',' and ';'
    assert any(k["left"] == "A" and k["right"] == "V" and k["delta"] == -122 for k in adv_n["kerning_pairs"])

    adv_b = get_af4_font_payload("advtg_b")
    codes_b = {g["code"] for g in adv_b["glyphs"]}
    assert 132 in codes_b  # 'ä'

    svg_k = typeset_af4_text_svg("advtg_n.af4", "AVE, Zoe; 2026", use_kerning=True)
    svg_nk = typeset_af4_text_svg("advtg_n.af4", "AVE, Zoe; 2026", use_kerning=False)
    assert 'fill-rule="evenodd"' in svg_k and "C" in svg_k
    assert svg_k != svg_nk

    # All 15 .COL files, 18 .GEM files, and 8 .TLS files
    col_files = sorted(DEFAULT_EXTRACTED_ROOT.rglob("*.col")) + sorted(DEFAULT_EXTRACTED_ROOT.rglob("*.COL"))
    assert len(col_files) >= 15
    for cp in col_files:
        assert decode_col_file(cp).swatch_count > 0

    gem_files = sorted((DEFAULT_EXTRACTED_ROOT / "symbol_pack_1989").glob("*.GEM")) + sorted(
        (DEFAULT_EXTRACTED_ROOT / "artline_2.0_dri_unpacked/art/art").glob("*.gem")
    )
    assert len(gem_files) == 18
    for gp in gem_files:
        rep = inspect_gem_file(gp)
        assert "<svg" in rep["preview_svg"]

    tls_files = sorted(DEFAULT_EXTRACTED_ROOT.rglob("*.tls"))
    assert len(tls_files) >= 7
    for tp in tls_files:
        tb = decode_tls_file(tp)
        assert all(t.icon_width == 32 and t.icon_height == 28 and t.icon_svg_path for t in tb.tools)

    # Full live archive /forge HTML + node --check
    html = render_artline_forge_html().decode("utf-8")
    assert "35 .AF4 Fonts" in html
    assert f"({CONSTITUTIONAL_FLAGS['cloud_tokens_used']} " in html or "0 Cloud Tokens" in html
    _assert_inline_js_valid(html)

    # Unicode umlauts on real 1990 advtg_n.af4
    lay_umlaut = typeset_af4_text_layout("advtg_n.af4", "A,V; ä ö ü Ä Ö Ü!?")
    assert [p["char"] for p in lay_umlaut["placed"]] == [
        "A", ",", "V", ";", "ä", "ö", "ü", "Ä", "Ö", "Ü", "!", "?",
    ]
    assert [p["code"] for p in lay_umlaut["placed"][4:10]] == [132, 148, 129, 142, 153, 154]


def _build_synthetic_af4_with_cp437_umlauts(display_name: str = "Zoe Synth Umlaut") -> bytes:
    """Synthetic clean-room .AF4 v4 font containing ASCII ('N','Z') plus CP437/Atari ST extended slots."""
    hdr = bytearray(0x8A)
    struct.pack_into("<H", hdr, 0, 4)
    hdr[2:14] = b"ZOEUMLT.AF4\x00"
    struct.pack_into("<H", hdr, 0x10, 130)
    hdr[0x14 : 0x14 + len(display_name[:31])] = display_name[:31].encode("ascii")
    hdr[0x34:0x4B] = b"(c) Clean-Room Zoe 2026"
    struct.pack_into("<HH", hdr, 0x54, 32, 200)
    struct.pack_into("<4h", hdr, 0x58, 0, -100, 1000, 950)

    rect_pts = [(100, 100), (600, 100), (600, 700), (100, 700), (100, 100)]
    rect_fl = [0x20, 0x08, 0x08, 0x08, 0x08]
    buf = bytearray(struct.pack("<H", len(rect_pts)))
    for x, y in rect_pts:
        buf.extend(struct.pack("<hh", x, y))
    buf.extend(bytes(rect_fl))
    g_rec = bytes(buf)

    struct.pack_into("<3H", hdr, 0x62, 1, 1, len(g_rec))
    struct.pack_into("<H", hdr, 0x6E, 0)

    target_codes = {32, 78, 90, 129, 130, 132, 142, 148, 153, 154, 158}
    slots = bytearray()
    for ch in range(32, 165):
        if ch == 32:
            slots.extend(struct.pack("<HHH4h8s", 0xFFFF, 0, 320, 0, 0, 0, 0, b"\x00" * 8))
        elif ch in target_codes:
            slots.extend(struct.pack("<HHH4h8s", 0, 1, 700, 100, 100, 600, 700, b"\x00" * 8))
        else:
            slots.extend(struct.pack("<H20s", 0xFFFF, b"\x00" * 20))

    off_tbl = struct.pack("<HI", 0x0100, 0)
    return bytes(hdr + slots + off_tbl + g_rec)


def test_r2_unicode_cp437_umlauts_svg_hardening_script_escape_and_cache_invalidation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_forge_cache()

    # 1. BUG-1: CP437 & Atari ST Unicode fallback in typesetter + preview entry + JS
    arch = tmp_path / "r2_arch"
    fonts_dir = arch / "artline_2.0_dri_unpacked/system/system/__Parent__/fonts"
    clrtl_dir = arch / "artline_2.0_dri_unpacked/clrtl/clrtl"
    fonts_dir.mkdir(parents=True)
    clrtl_dir.mkdir(parents=True)

    uml_bytes = _build_synthetic_af4_with_cp437_umlauts("Umlaut Synth")
    (fonts_dir / "uml.af4").write_bytes(uml_bytes)
    uml_font = decode_af4_bytes(uml_bytes, "uml.af4")
    preview = _build_af4_font_preview_entry(uml_font)
    for code in (129, 130, 132, 142, 148, 153, 154, 158):
        assert str(code) in preview["glyphs"]

    lay = typeset_af4_text_layout("uml.af4", "NZ äöüÄÖÜéß", archive_root=arch)
    assert [p["char"] for p in lay["placed"]] == ["N", "Z", "ä", "ö", "ü", "Ä", "Ö", "Ü", "é", "ß"]
    assert [p["code"] for p in lay["placed"][2:]] == [132, 148, 129, 142, 153, 154, 130, 158]

    # 2. BUG-2: _parse_svg_path_subpaths validation & A/Q/S/T support + zoetk validation
    for bad_d in ("M 10 20 L 30", "M 10 Z", "M 10 20 C 1 2 3 4", "M 10 20 L", "X 1 2"):
        with pytest.raises(ValueError):
            export_forge_artifact("gem", {"stamps": [{"d": bad_d}]})

    for good_d in (
        "M 0 0 A 10 10 0 0 1 20 20",
        "M 10 10 Q 50 0 90 10 T 90 90 S 20 80 10 10 Z",
    ):
        ok_gem = export_forge_artifact("gem", {"stamps": [{"d": good_d}]})
        assert ok_gem["ok"] is True
        raw_gem = base64.b64decode(ok_gem["content_base64"])
        assert parse_metafile(raw_gem)["bytes_consumed"] == len(raw_gem)

    with pytest.raises(ValueError):
        export_forge_artifact("zoetk", {"toolbox": {"buttons": [{"bad": 1}]}})
    with pytest.raises(ValueError):
        export_forge_artifact("zoetk", {"toolbox": "not_a_dict"})

    # 3. BUG-3: </script><x> and <!-- in .col swatch name must not break inline <script>
    col_hdr = struct.pack(
        "<24h", -1, 24, 310, 2, 0, 0, 100, 100, 1000, 1000, 0, 0, 100, 100,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    )
    evil_name = b"</script><x><!--\x00"
    if len(evil_name) % 2 == 1:
        evil_name += b"\x00"
    name_words = struct.unpack(f"<{len(evil_name) // 2}h", evil_name)
    col_rec = _record(5, 99, values=[201, 1000, 0, 500, *name_words])
    evil_col = col_hdr + col_rec + struct.pack("<h", -1)
    (clrtl_dir / "evil.col").write_bytes(evil_col)

    html = render_artline_forge_html(arch).decode("utf-8")
    assert "</script><x>" not in html
    assert "<\\/script><x>" in html
    assert "\\u003c!--" in html
    _assert_inline_js_valid(html)

    # Verify JS layoutTypesetEm resolves Unicode umlauts & stampTypesetToCanvas preserves spacing with snapGrid=true
    if Path(NODE_BIN).is_file():
        js_body = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)[0]
        harness = (
            "const els = {};\n"
            "const mkEl = (id) => ({ id, value: '', checked: true, innerHTML: '', textContent: '', style: {}, "
            "attributes: {}, classList: { toggle() {} }, addEventListener() {}, setAttribute(k,v){ this.attributes[k]=v; } });\n"
            "for (const id of ['syfPackSel','af4FontSel','tsFontSel','colPalSel','stageStatus','vWom','vSym','vCha','vAf4','vSyf','vGem',"
            "'af4FilterRow','syfFilterRow','vaultGrid','syfSearch','stage','typesetPreview','tsText','tsKern','tbTabs','tbDesc','tbGrid',"
            "'tls1990Box','tlsTabs','tlsMeta','tlsPills','palTabs','colSelectRow','swatches']) els[id] = mkEl(id);\n"
            "global.document = { getElementById(id){ return els[id] || (els[id] = mkEl(id)); } };\n"
            "global.window = {};\n"
            "global.requestAnimationFrame = () => 0;\n"
            "global.cancelAnimationFrame = () => {};\n"
            + js_body
            + "\n"
            "els.tsFontSel.value = '0';\n"
            "els.tsText.value = 'NZ äöüÄÖÜéß';\n"
            "const out = layoutTypesetEm();\n"
            "if (!out || out.items.length !== 10) throw new Error('Expected 10 JS typeset glyphs, got ' + (out && out.items.length));\n"
            "clearStage();\n"
            "snapGrid = true;\n"
            "stampTypesetToCanvas();\n"
            "const xs = stamps.map(s => s.x);\n"
            "const mod40 = xs.filter(x => Math.abs(x - Math.round(x / 40) * 40) < 1e-6);\n"
            "if (mod40.length === xs.length) throw new Error('snapGrid distorted stamped typeset spacing');\n"
        )
        proc = subprocess.run([NODE_BIN, "-e", harness], capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    # 4. BUG-4: Older-mtime overwrite invalidates _archive_fingerprint and get_forge_catalog
    beta_p = fonts_dir / "beta.af4"
    beta_p.write_bytes(_build_synthetic_af4_with_cp437_umlauts("Beta Font"))
    beta_ns = beta_p.stat().st_mtime_ns

    fp_before = _archive_fingerprint(arch)
    cat_before = get_forge_catalog(arch)
    assert any(f["display_name"] == "Umlaut Synth" for f in cat_before["fonts"])

    uml_p = fonts_dir / "uml.af4"
    uml_p.write_bytes(_build_synthetic_af4_with_cp437_umlauts("Alpha Updated"))
    older_ns = beta_ns - 5_000_000_000
    os.utime(uml_p, ns=(older_ns, older_ns))

    fp_after = _archive_fingerprint(arch)
    assert fp_after != fp_before
    cat_after = get_forge_catalog(arch)
    assert any(f["display_name"] == "Alpha Updated" for f in cat_after["fonts"])

    # 5. CLI Minor: explicit unknown --font exits cleanly with error
    rc_bad_font = artline_cli_main([
        "--out-dir", str(tmp_path / "cli_bad"),
        "forge",
        "--archive-root", str(arch),
        "--text", "NZ",
        "--font", "missing_font_999.af4",
    ])
    assert rc_bad_font != 0
    assert "unknown .AF4 font" in capsys.readouterr().err


def test_t5_forge_numeric_zoetk_json_and_eschtml_hardening() -> None:
    # G1: ZoeToolboxSpec & zoetk export validation
    for bad_cols in (True, 1.9, 0, 70000):
        with pytest.raises(ValueError):
            ZoeToolboxSpec("ok_id", "Ok", bad_cols, "desc", ()).to_zoetk_binary()  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            export_forge_artifact("zoetk", {"toolbox": {"toolbox_id": "ok_id", "columns": bad_cols, "buttons": []}})

    for bad_id in ("../../evil", "a/b", "a\\b", "a\x00b", ""):
        with pytest.raises(ValueError):
            export_forge_artifact("zoetk", {"toolbox": {"toolbox_id": bad_id, "columns": 2, "buttons": []}})

    # G2: allow_nan=False in JSON + math.isfinite & non-bool in gem/svg exports
    with pytest.raises(ValueError):
        export_forge_artifact("json", {"stamps": [{"d": "M0,0 L10,10 Z", "extra": float("inf")}]})
    for bad_stamp in (
        {"d": "M 1e999,0 L 10,10 Z"},
        {"d": "M0,0 L10,10 Z", "x": float("inf")},
        {"d": "M0,0 L10,10 Z", "x": float("nan")},
        {"d": "M0,0 L10,10 Z", "s": True},
    ):
        with pytest.raises(ValueError):
            export_forge_artifact("gem", {"stamps": [bad_stamp]})
        with pytest.raises(ValueError):
            export_forge_artifact("svg", {"stamps": [bad_stamp]})

    # G4: escHtml helper present and valid JS
    html = render_artline_forge_html().decode("utf-8")
    assert "function escHtml(val)" in html
    assert "function escJsAttr(val)" in html
    _assert_inline_js_valid(html)

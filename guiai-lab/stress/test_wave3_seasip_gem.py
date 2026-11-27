"""Unit and integration tests for Zoe Wave 3 Digital Research GEM / ViewMAX rebuild.

Verifies compliance with John Elliott's `https://www.seasip.info/Gem/` specifications:
  - `palette.html`  : 16-color Standard GEM & GEM/5 palettes + VDI 0..1000 scaling
  - `aes.html`      : 7-window PC GEM limit, wind_create bitmasks, Fn 52 form_alert
  - `aesmsg.html`   : 16-byte (<8h) AES message encoding/decoding
  - `aestruct.html` / `filefmt.html`: 36-byte RSHDR + 24-byte OBJECT + 28-byte TEDINFO `.RSC`
  - `ff_img.html`   : Big-endian 4-plane RLE `.IMG` / `XIMG` pixel-exact roundtrip
  - `ff_gem.html`   : Little-endian 24-word `.GEM` VDI metafile roundtrip & verification
  - All 6 Wave 3 GEM instruments (`wave3`, `wave3-trust`, `wave3-auditors`,
    `wave3-dualpath`, `wave3-guards`, `wave3-actuation`) through `GemOperatingEnvironment`
    preserving core `17` components / `36` atlas layers and no-overwrite exports.
"""

from __future__ import annotations

from pathlib import Path
import struct
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for rel in (
    "guiai-lab",
    "components/Zoe-Autonomy/src",
    "components/ablation",
    "components/kevlar",
    "components/gemseal",
    "components/nina",
):
    p = str(REPO_ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from guiai.gem.seasip_gem import (
    DEFAULT,
    EXIT,
    FLAG3D,
    G_BOX,
    G_BOXTEXT,
    G_BUTTON,
    G_STRING,
    G_TITLE,
    GEM5_PALETTE_OVERRIDES,
    GEM_STANDARD_PALETTE,
    IMG_HEADER_STRUCT,
    LASTOB,
    MAX_AES_APP_WINDOWS,
    MN_SELECTED,
    OBJECT_STRUCT,
    RSHDR_STRUCT,
    SELECTABLE,
    STANDARD_WINDOW_KIND,
    TEDINFO_STRUCT,
    TOASTYTECH_GEM_ERAS,
    WM_CLOSED,
    WM_FULLED,
    WM_MOVED,
    WM_REDRAW,
    WM_TOPPED,
    GemAesDesk,
    GemObjectTree,
    build_form_alert,
    compile_rsc,
    decode_aes_message,
    encode_aes_message,
    encode_gem_img,
    encode_gsx_stream,
    nearest_gem_color_index,
    parse_form_alert,
    parse_gem_img,
    parse_gsx_stream,
    parse_rsc,
    rgb_to_vdi_1000,
    scene_to_gem_img,
    verify_seasip_gem_metafile,
)
from guiai.gem.zoe_freegem_archive import inspect_rsc_bytes
from guiai.gem.vdi import scene_from_metafile, scene_to_metafile
from guiai.gem.wave3_gem_instruments import (
    run_wave3_gem_snapshot,
    wave3_document,
    wave3_object_trees,
)


def test_seasip_palettes_and_vdi_1000_scaling():
    assert len(GEM_STANDARD_PALETTE) == 16
    assert GEM_STANDARD_PALETTE[0][2] == "#FFFFFF"
    assert GEM_STANDARD_PALETTE[1][2] == "#000000"
    assert GEM_STANDARD_PALETTE[8][2] == "#ADAAAD"
    assert GEM_STANDARD_PALETTE[12][2] == "#0000AD"
    assert GEM5_PALETTE_OVERRIDES[8][2] == "#00756B"
    assert GEM5_PALETTE_OVERRIDES[9][2] == "#FFC300"
    assert rgb_to_vdi_1000((0, 128, 255)) == (0, 502, 1000)
    assert nearest_gem_color_index("#ad0000") == 10
    assert nearest_gem_color_index("#00aa00") == 11
    assert nearest_gem_color_index("#0000ad") == 12


def test_aes_16_byte_messages_and_7_window_limit():
    raw = encode_aes_message(WM_MOVED, sender_apid=2, extra_len=0, w3=1, w4=10, w5=20, w6=300, w7=200)
    assert len(raw) == 16
    dec = decode_aes_message(raw)
    assert dec["msg_type"] == WM_MOVED
    assert dec["name"] == "WM_MOVED"
    assert dec["sender_apid"] == 2
    assert dec["data"] == [1, 10, 20, 300, 200]

    with pytest.raises(ValueError):
        decode_aes_message(b"\x00" * 12)

    desk = GemAesDesk(640, 400)
    handles = []
    for i in range(MAX_AES_APP_WINDOWS):
        h = desk.wind_create(STANDARD_WINDOW_KIND, 10 + i * 10, 24 + i * 10, 200, 150, title=f"WIN{i}")
        assert h == i + 1
        msg = desk.wind_open(h)
        assert decode_aes_message(msg)["msg_type"] == WM_REDRAW
        handles.append(h)

    # PC GEM single-tasking spec: 8th application window MUST return -1
    assert desk.wind_create(STANDARD_WINDOW_KIND, 0, 20, 100, 100, title="OVERFLOW") == -1

    desk.dispatch(encode_aes_message(WM_TOPPED, sender_apid=1, w3=handles[0]))
    assert desk.top_handle == handles[0]
    desk.dispatch(encode_aes_message(WM_FULLED, sender_apid=1, w3=handles[0]))
    assert desk.windows[handles[0]].fulled is True
    assert desk.windows[handles[0]].w == 640
    desk.dispatch(encode_aes_message(WM_CLOSED, sender_apid=1, w3=handles[0]))
    assert desk.windows[handles[0]].opened is False
    assert desk.top_handle != handles[0]


def test_form_alert_exact_spec_and_validation():
    s = build_form_alert(3, ["Coercion Detected", "Source trust capped"], ["Hold", "Inspect"])
    assert s == "[3][Coercion Detected|Source trust capped][Hold|Inspect]"
    parsed = parse_form_alert(s)
    assert parsed["icon"] == 3
    assert parsed["icon_name"] == "stop"
    assert parsed["lines"] == ["Coercion Detected", "Source trust capped"]
    assert parsed["buttons"] == ["Hold", "Inspect"]

    with pytest.raises(ValueError):
        build_form_alert(9, ["Bad icon"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(1, ["1", "2", "3", "4", "5", "6"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(1, ["Line"], ["B1", "B2", "B3", "B4"])


def test_pc_gem_binary_rsc_exact_struct_sizes_and_roundtrip():
    assert RSHDR_STRUCT.size == 36
    assert OBJECT_STRUCT.size == 24
    assert TEDINFO_STRUCT.size == 28

    menu = GemObjectTree("TEST_MENU", 80, 1)
    menu.add(G_TITLE, 1, 0, 6, 1, text=" Desk ", flags=SELECTABLE)
    dlg = GemObjectTree("TEST_DLG", 40, 10)
    dlg.add(G_BOXTEXT, 2, 1, 36, 2, text="ZOE GEM DIALOG", flags=FLAG3D)
    dlg.add(G_STRING, 2, 4, 36, 1, text="Trust ceiling enforced")
    dlg.add(G_BUTTON, 14, 7, 12, 2, text="OK", flags=SELECTABLE | DEFAULT | EXIT | FLAG3D)

    blob = compile_rsc([menu, dlg])
    parsed = parse_rsc(blob)
    assert parsed["format"] == "GEM_RSC"
    assert parsed["rsh_ntree"] == 2
    assert parsed["rsh_nobs"] == 6
    assert parsed["rsh_nted"] == 1
    assert parsed["rsh_rssize"] == len(blob)

    assert parsed["trees"][0][0]["ob_type"] == G_BOX
    assert parsed["trees"][0][1]["text"] == " Desk "
    assert bool(parsed["trees"][0][1]["ob_flags"] & LASTOB)
    assert parsed["trees"][1][1]["text"] == "ZOE GEM DIALOG"
    assert parsed["trees"][1][2]["text"] == "Trust ceiling enforced"
    assert parsed["trees"][1][3]["text"] == "OK"
    assert bool(parsed["trees"][1][3]["ob_flags"] & LASTOB)


def test_gem_img_ximg_big_endian_4plane_rle_pixel_exact_roundtrip():
    assert IMG_HEADER_STRUCT.size == 16
    # 32x16 test grid with all 16 GEM palette colors + repeated identical scanlines
    pixels = []
    for y in range(16):
        if 4 <= y < 8:
            pixels.append([12] * 32)  # solid vertical-repeat band
        elif 8 <= y < 12:
            pixels.append([x % 16 for x in range(32)])  # all 16 colors + vertical repeat
        else:
            pixels.append([(x + y) % 16 for x in range(32)])

    blob = encode_gem_img(pixels, planes=4, include_ximg_palette=True, use_gem5_palette=True)
    # Big-endian version=1, planes=4
    ver, hdr_words, planes = struct.unpack_from(">3H", blob, 0)
    assert ver == 1
    assert planes == 4
    assert hdr_words == 8 + (6 + 16 * 6) // 2
    assert blob[16:20] == b"XIMG"

    decoded = parse_gem_img(blob)
    assert decoded["format"] == "GEM_XIMG"
    assert decoded["width"] == 32
    assert decoded["height"] == 16
    assert decoded["has_ximg_palette"] is True
    assert decoded["pixels"] == pixels


def test_all_six_wave3_gem_instruments_verify_spatial_ir_and_vdi_roundtrip():
    report = run_wave3_gem_snapshot(REPO_ROOT)
    assert report["contract"] == "zoe-wave3-seasip-gem/v1"
    assert report["trust"]["clean"]["output_trust"] <= report["trust"]["clean"]["source_trust"]
    assert report["trust"]["coerced"]["output_trust"] <= 0.15
    assert report["auditors"]["total_findings"] >= 5
    assert report["dualpath"]["mismatch"]["status"] == "MISMATCH_HELD"
    assert report["guards"]["eq2_steps"][-1]["eq2_slow_drift_alarm"] is True
    assert report["guards"]["mcp_ssh_blocked"] is True
    assert report["actuation"]["email_allow"]["allowed"] is True
    assert report["actuation"]["email_deny"]["allowed"] is False
    assert report["actuation"]["ros_denied"]["allowed"] is False
    assert len(report["form_alerts"]) == 5
    for alert_str in report["form_alerts"].values():
        assert parse_form_alert(alert_str)["icon"] in (0, 1, 2, 3)

    for layer in (
        "wave3",
        "wave3-trust",
        "wave3-auditors",
        "wave3-dualpath",
        "wave3-guards",
        "wave3-actuation",
        "wave3-gsx",
        "wave3-tos",
        "wave3-gem2",
    ):
        scene, _ = wave3_document(layer, zoe_root=REPO_ROOT)
        ir_check = verify(scene)
        assert ir_check.passed, f"{layer} failed Spatial IR: {ir_check.text()}"

        vdi_check = verify_vdi(scene)
        assert vdi_check.passed, f"{layer} failed VDI check: {vdi_check.text()}"

        gem_bytes = scene_to_metafile(scene)
        spec_check = verify_seasip_gem_metafile(gem_bytes)
        assert spec_check["valid"] is True
        assert spec_check["magic_hex"] == "0xFFFF"
        assert spec_check["eof_hex"] == "0xFFFF"
        assert spec_check["coordinate_system"] == "RC"

        # Roundtrip scene from binary .GEM metafile
        restored = scene_from_metafile(gem_bytes)
        assert len(restored.objects) == len(scene.objects)

        # Roundtrip .RSC (PC x86 LE or Atari 68k BE) and .IMG for every instrument
        endian = ">" if layer == "wave3-tos" else "<"
        rsc_bytes = compile_rsc(wave3_object_trees(report, layer=layer), endian=endian)
        rsc_parsed = parse_rsc(rsc_bytes)
        assert rsc_parsed["rsh_ntree"] == 2
        assert rsc_parsed["endian"] == endian
        # Cross-verify against Zoe's dual-endian FreeGEM archive inspector
        cross = inspect_rsc_bytes(rsc_bytes, label=f"{layer}.rsc")
        assert cross["ok"] is True
        assert cross["endian"] == endian

        img_bytes = scene_to_gem_img(scene, width=160, height=100, use_gem5_palette=True)
        img_parsed = parse_gem_img(img_bytes)
        assert img_parsed["width"] == 160 and img_parsed["height"] == 100


def test_toastytech_eras_dual_endian_rsc_and_gsx86_ndc_codec():
    assert set(TOASTYTECH_GEM_ERAS.keys()) == {"gsx", "gem11", "gem20", "tos10", "opengem"}
    assert TOASTYTECH_GEM_ERAS["gem20"]["desk_menu_position"] == "right"
    assert TOASTYTECH_GEM_ERAS["gem20"]["desktop_icons"] is False
    assert TOASTYTECH_GEM_ERAS["tos10"]["endian"] == ">"
    assert TOASTYTECH_GEM_ERAS["tos10"]["desktop_icons"] is True

    gsx_scene, _ = wave3_document("wave3-gsx", zoe_root=REPO_ROOT)
    gsx_blob = encode_gsx_stream(gsx_scene, driver_id=1)
    gsx_parsed = parse_gsx_stream(gsx_blob)
    assert gsx_parsed["valid"] is True
    assert gsx_parsed["format"] == "DR_GSX86_NDC"
    assert gsx_parsed["max_ndc_coord"] <= 32767
    assert "v_opnwk" in gsx_parsed["opcode_names"]
    assert "v_pline" in gsx_parsed["opcode_names"]
    assert "v_gtext" in gsx_parsed["opcode_names"]
    assert "v_clswk" in gsx_parsed["opcode_names"]


def test_operating_environment_preserves_counts_and_exports_all_formats(tmp_path: Path):
    env = GemOperatingEnvironment(REPO_ROOT)
    cat = env.catalog()
    # Core invariants asserted by unified_stress.py MUST remain untouched
    assert cat["component_count"] == 17
    assert cat["layer_count"] == 36

    for alias in (
        "wave3",
        "wave3-desk",
        "wave3-trust",
        "trust-acc",
        "wave3-auditors",
        "audit-app",
        "wave3-dualpath",
        "verify-app",
        "wave3-guards",
        "guard-acc",
        "wave3-actuation",
        "actuate-app",
        "wave3-gsx",
        "gsx-graph",
        "wave3-tos",
        "tos-desk",
        "wave3-gem2",
        "gem2-tiled",
    ):
        opened = env.open(alias)
        assert opened["source_spatial_ir_verified"] is True
        assert opened["process_launched"] is False
        assert opened["external_actions"] == 0

    for ext in (".gem", ".rsc", ".img", ".gsx", ".svg", ".html", ".json"):
        out = tmp_path / f"wave3_desk{ext}"
        res = env.export("wave3", out)
        assert out.is_file()
        assert res["bytes"] == out.stat().st_size > 0
        assert res["no_overwrite"] is True
        if ext == ".gem":
            assert res["vdi_verified"] is True
            assert verify_seasip_gem_metafile(out.read_bytes())["valid"] is True
        elif ext == ".rsc":
            parsed_le = parse_rsc(out.read_bytes())
            assert parsed_le["rsh_ntree"] == 2
            assert parsed_le["endian"] == "<"
        elif ext == ".img":
            assert parse_gem_img(out.read_bytes())["format"] == "GEM_XIMG"
        elif ext == ".gsx":
            assert parse_gsx_stream(out.read_bytes())["valid"] is True
        elif ext == ".html":
            text = out.read_text(encoding="utf-8")
            assert "FORM_ALERT.ACC" in text
            assert "SEASIP + GSX CODEC INSPECTOR" in text
            assert "CALC.ACC :: Trust Ceiling" in text
            assert "1985 Atari TOS 1.0" in text
            assert "1986 GEM 2.0/3.11" in text

        # No-overwrite rule must reject second export to same path
        with pytest.raises(FileExistsError):
            env.export("wave3", out)

    # Atari TOS 1.0 layer exports Motorola 68000 big-endian ('>') .RSC
    tos_rsc = tmp_path / "atari_tos_68k.rsc"
    env.export("wave3-tos", tos_rsc)
    tos_parsed = parse_rsc(tos_rsc.read_bytes())
    assert tos_parsed["endian"] == ">"
    assert "68000" in tos_parsed["arch"]

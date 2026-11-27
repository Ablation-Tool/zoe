"""Unit tests for Zoe Artline Forge (.AF4/.SYF decoders, ZOETK001 toolboxes, GEM .COL palettes, /forge UI)."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "guiai-lab"))

from guiai.gem.zoe_artline_forge import (
    STUDIO_PALETTES,
    STUDIO_TOOLBOXES,
    ZoeToolboxSpec,
    build_synthetic_af4_bytes,
    build_synthetic_syf_bytes,
    build_synthetic_tls_bytes,
    decode_af4_bytes,
    decode_syf_bytes,
    decode_tls_bytes,
    render_af4_catalog_poster_png,
    render_af4_specimen_png,
    render_artline_forge_html,
    render_syf_contact_sheet_png,
    write_interactive_artline_forge_html,
)

NODE_BIN = shutil.which("node") or "/home/cowboy/.nvm/versions/node/v24.16.0/bin/node"


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

    if Path(NODE_BIN).is_file():
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
        assert scripts
        for js in scripts:
            proc = subprocess.run([NODE_BIN, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
            assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

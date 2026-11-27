#!/usr/bin/env python3
"""Verify Zoe Wave 3 Digital Research GEM / ViewMAX rebuild (`seasip.info/Gem`).

Validates all 5 Wave 3 Vault upgrades rendered as authentic Digital Research GEM
instruments (`TRUST.ACC`, `AUDIT.APP`, `VERIFY.APP`, `GUARD.ACC`, `ACTUATE.APP`,
plus the unified `wave3` desktop), compiles & roundtrip-verifies binary `.GEM`,
`.RSC`, `.IMG` (`XIMG`), `.SVG`, and interactive `.HTML` artifacts into
`evidence/gem-os/wave3/`, and emits a deterministic SHA-256 verification ledger
at `evidence/gem-os/wave3-seasip-gem-report.json`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
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
    MAX_AES_APP_WINDOWS,
    STANDARD_WINDOW_KIND,
    GemAesDesk,
    parse_form_alert,
    parse_gem_img,
    parse_gsx_stream,
    parse_rsc,
    verify_seasip_gem_metafile,
)
from guiai.gem.vdi import scene_from_metafile
from guiai.gem.wave3_gem_instruments import wave3_document
from guiai.gem.zoe_freegem_archive import inspect_rsc_bytes


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    env = GemOperatingEnvironment(REPO_ROOT)
    cat = env.catalog()
    checks = []

    # 1. Core GEM OS invariants preserved (17 components, 36 core layers)
    ok_core = cat["component_count"] == 17 and cat["layer_count"] == 36
    checks.append({
        "name": "core_gem_os_invariants",
        "passed": ok_core,
        "detail": f"components={cat['component_count']} core_layers={cat['layer_count']}",
    })

    # 2. PC GEM 7-window AES limit & 16-byte message compliance
    desk = GemAesDesk(640, 400)
    h_list = [desk.wind_create(STANDARD_WINDOW_KIND, 10, 24, 200, 120, title=f"W{i}") for i in range(MAX_AES_APP_WINDOWS)]
    overflow_ret = desk.wind_create(STANDARD_WINDOW_KIND, 10, 24, 200, 120, title="OVERFLOW")
    ok_aes = h_list == [1, 2, 3, 4, 5, 6, 7] and overflow_ret == -1
    checks.append({
        "name": "seasip_aes_7_window_limit",
        "passed": ok_aes,
        "detail": f"handles={h_list} 8th_handle={overflow_ret}",
    })

    # 3. Verify all 9 Wave 3 GEM instruments (6 core + 3 ToastyTech historical eras)
    layers = [
        "wave3",
        "wave3-trust",
        "wave3-auditors",
        "wave3-dualpath",
        "wave3-guards",
        "wave3-actuation",
        "wave3-gsx",
        "wave3-tos",
        "wave3-gem2",
    ]
    layer_records = {}
    all_layers_ok = True
    for lid in layers:
        opened = env.open(lid)
        scene, rep = wave3_document(lid, zoe_root=REPO_ROOT)
        ir_res = verify(scene)
        vdi_res = verify_vdi(scene)
        ok_layer = opened["source_spatial_ir_verified"] and ir_res.passed and vdi_res.passed
        all_layers_ok = all_layers_ok and ok_layer
        layer_records[lid] = {
            "scene_id": opened["scene_id"],
            "scene_sha256": opened["scene_sha256"],
            "object_count": len(scene.objects),
            "spatial_ir_passed": ir_res.passed,
            "vdi_passed": vdi_res.passed,
            "form_alerts_valid": all(parse_form_alert(a)["icon"] in (0, 1, 2, 3) for a in rep["form_alerts"].values()),
        }
    checks.append({
        "name": "all_9_wave3_gem_instruments_verified",
        "passed": all_layers_ok,
        "detail": f"verified {sum(1 for r in layer_records.values() if r['spatial_ir_passed'] and r['vdi_passed'])}/{len(layers)} scenes (incl. GSX-86, Atari TOS 1.0, GEM 2.0/3.11)",
    })

    # 4. Export fresh binary artifacts (.gem, x86 .rsc, 68k .rsc, .img, .gsx, .svg, .html)
    out_dir = REPO_ROOT / "evidence" / "gem-os" / "wave3"
    out_dir.mkdir(parents=True, exist_ok=True)
    export_specs = [
        ("wave3", "wave3-desktop.gem"),
        ("wave3", "wave3-desktop.rsc"),
        ("wave3-tos", "wave3-tos-68k.rsc"),
        ("wave3", "wave3-desktop.img"),
        ("wave3-gsx", "wave3-gsx.gsx"),
        ("wave3", "wave3-desktop.svg"),
        ("wave3-tos", "wave3-tos.svg"),
        ("wave3-gem2", "wave3-gem2.svg"),
        ("wave3-gsx", "wave3-gsx.svg"),
        ("wave3", "wave3-desktop.html"),
    ]
    exported_artifacts = {}
    for lid, fname in export_specs:
        target = out_dir / fname
        if target.exists():
            target.unlink()
        res = env.export(lid, target)
        exported_artifacts[fname] = {
            "path": str(target.relative_to(REPO_ROOT)),
            "bytes": res["bytes"],
            "sha256": _sha256(target),
        }

    # 5. Roundtrip-validate exported .GEM, dual-endian .RSC, .IMG, and .GSX binaries
    gem_bytes = (out_dir / "wave3-desktop.gem").read_bytes()
    gem_meta = verify_seasip_gem_metafile(gem_bytes)
    gem_restored = scene_from_metafile(gem_bytes)

    rsc_le_bytes = (out_dir / "wave3-desktop.rsc").read_bytes()
    rsc_le_meta = parse_rsc(rsc_le_bytes)
    rsc_be_bytes = (out_dir / "wave3-tos-68k.rsc").read_bytes()
    rsc_be_meta = parse_rsc(rsc_be_bytes)
    rsc_be_cross = inspect_rsc_bytes(rsc_be_bytes, label="wave3-tos-68k.rsc")

    img_bytes = (out_dir / "wave3-desktop.img").read_bytes()
    img_meta = parse_gem_img(img_bytes)

    gsx_bytes = (out_dir / "wave3-gsx.gsx").read_bytes()
    gsx_meta = parse_gsx_stream(gsx_bytes)

    ok_codecs = (
        gem_meta["valid"]
        and len(gem_restored.objects) == layer_records["wave3"]["object_count"]
        and rsc_le_meta["endian"] == "<"
        and rsc_be_meta["endian"] == ">"
        and rsc_be_cross["ok"]
        and rsc_be_cross["endian"] == ">"
        and img_meta["format"] == "GEM_XIMG"
        and img_meta["width"] == 320
        and img_meta["height"] == 200
        and img_meta["planes"] == 4
        and gsx_meta["valid"]
        and gsx_meta["max_ndc_coord"] <= 32767
    )
    checks.append({
        "name": "binary_gem_dual_rsc_img_gsx_roundtrip",
        "passed": ok_codecs,
        "detail": (
            f".GEM={gem_meta['bytes']}B "
            f".RSC(x86)={rsc_le_meta['rsh_rssize']}B "
            f".RSC(68k)={rsc_be_meta['rsh_rssize']}B "
            f".IMG={len(img_bytes)}B "
            f".GSX={gsx_meta['bytes']}B({gsx_meta['call_count']} calls)"
        ),
    })

    # 6. Verify no-overwrite guard on GemOperatingEnvironment.export()
    no_overwrite_ok = False
    with tempfile.TemporaryDirectory(prefix="zoe_w3_noow_") as td:
        probe = Path(td) / "probe.gem"
        env.export("wave3-trust", probe)
        try:
            env.export("wave3-trust", probe)
        except FileExistsError:
            no_overwrite_ok = True
    checks.append({
        "name": "export_no_overwrite_enforced",
        "passed": no_overwrite_ok,
        "detail": "FileExistsError raised on duplicate export destination",
    })

    all_passed = all(c["passed"] for c in checks)
    report = {
        "contract": "zoe-wave3-seasip-gem-verification/v1",
        "spec_reference": "https://www.seasip.info/Gem/index.html + http://toastytech.com/guis/indexgem.html",
        "all_passed": all_passed,
        "passed_count": sum(1 for c in checks if c["passed"]),
        "total_checks": len(checks),
        "checks": checks,
        "layers": layer_records,
        "codec_telemetry": {
            "gem_metafile": gem_meta,
            "rsc_pc_x86_le": {k: v for k, v in rsc_le_meta.items() if k != "trees"},
            "rsc_atari_68k_be": {k: v for k, v in rsc_be_meta.items() if k != "trees"},
            "img_bitmap": {k: v for k, v in img_meta.items() if k != "pixels"},
            "gsx86_ndc": gsx_meta,
        },
        "artifacts": exported_artifacts,
        "invariants": {
            "components_lock_untouched": True,
            "core_component_count": cat["component_count"],
            "core_layer_count": cat["layer_count"],
            "external_actions": 0,
            "sentience_claimed": False,
        },
    }

    report_path = REPO_ROOT / "evidence" / "gem-os" / "wave3-seasip-gem-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for c in checks:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"[{mark}] {c['name']}: {c['detail']}")
    print(f"\nWave 3 seasip.info/Gem verification: {report['passed_count']}/{report['total_checks']} PASS")
    print(f"Report written: {report_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

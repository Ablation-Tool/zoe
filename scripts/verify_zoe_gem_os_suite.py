#!/usr/bin/env python3
"""Standalone 8-Check Offline Verifier for the Zoe-GEM OS Ecosystem Suite.

Verifies without touching ~/.zoe/* or launching live servers/VMs:
  01. UMA Mutual-Consent Airlock & SHA-256 Audit Chain Tamper Detection (`zoe_uma.py`)
  02. Pixel 7-9 Sovereign Phone OS Static Matrix & Deterministic ARM64 Initramfs (`zoe_pixel_os.py`)
  03. Phone Sync & Beta Release Loopback-Only SSRF Guards (`zoe_phone_codex_sync.py`, `zoe_beta_release.py`)
  04. 2x4 Unicode Braille Dot-Art Studio & DESQview/X Starter App Scaffold (`zoe_braille_studio.py`)
  05. Historic GEM/1..ViewMAX/3 Lineage, 10 Color Schemes & Desktop Bundle (`zoe_gem_themes.py`)
  06. 9-Realm Zoeverse Navigation, Braille Vistas & Atlas Plate Export (`zoe_universe.py`)
  07. 9 Sister Models Signet Mapping, Routing & Zero-Sentience Lock (`zoe_sisters.py`)
  08. Sovereign Empire v0.9.0-beta.1 Release Manifest in Isolated Directory (`zoe_beta_release.py`)
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GUIAI_LAB = ROOT / "guiai-lab"
if str(GUIAI_LAB) not in sys.path:
    sys.path.insert(0, str(GUIAI_LAB))

from guiai.gem.zoe_beta_release import BETA_HONESTY_LOCK, build_beta_release_manifest  # noqa: E402
from guiai.gem.zoe_braille_studio import (  # noqa: E402
    BrailleCanvas,
    render_braille_template,
    render_dvx_app_manager,
    scaffold_starter_app,
)
from guiai.gem.zoe_gem_os.zoe_phone_codex_sync import assert_loopback_url  # noqa: E402
from guiai.gem.zoe_gem_os.zoe_pixel_os import verify_pixel_os_static  # noqa: E402
from guiai.gem.zoe_gem_os.zoe_uma import UmaBridge  # noqa: E402
from guiai.gem.zoe_gem_themes import (  # noqa: E402
    export_gem_lineage_desktop_bundle,
    list_gem_eras,
    list_viewmax_schemes,
    render_viewmax_ini,
)
from guiai.gem.zoe_sisters import list_sisters, route_prompt_to_sister  # noqa: E402
from guiai.gem.zoe_universe import (  # noqa: E402
    export_zoeverse_atlas_plate,
    list_zoeverse_realms,
    render_realm_braille_vista,
    render_zoeverse_map,
)

CONTRACT = "zoe-gem-os-suite-verifier/v1"
REPORT_PATH = ROOT / "evidence" / "gem-os" / "zoe-gem-os-suite-report.json"


def _check_uma_airlock(tmp: Path) -> dict[str, Any]:
    uma = UmaBridge(tmp / "uma", shm_path=tmp / "uma.shm")
    init_state = uma.ensure_initialized()
    src = tmp / "sample.txt"
    src.write_text("Zoe UMA mutual consent payload\n", encoding="utf-8")

    # Unilateral consent must raise PermissionError and never cross the airlock.
    uma.set_consent("nick", True, reason="unilateral_test")
    blocked_unilateral = False
    try:
        uma.transfer_file("nick", src)
    except PermissionError:
        blocked_unilateral = True

    # Mutual consent enables transfer and records a valid SHA-256 chain.
    uma.set_zoe_consent(True, reason="mutual_test")
    transfer = uma.transfer_file("nick", src)
    chain_ok = uma.verify_audit_chain()

    # Tampering the JSONL chain must be caught cleanly.
    audit_path = tmp / "uma" / "uma_audit.jsonl"
    tampered = audit_path.read_text(encoding="utf-8").replace("mutual_test", "tampered_reason", 1)
    audit_path.write_text(tampered, encoding="utf-8")
    tamper_detected = not uma.verify_audit_chain().get("valid", uma.verify_audit_chain().get("ok", True))

    passed = bool(
        init_state.get("gate") == "PRIVATE"
        and blocked_unilateral
        and bool(transfer.get("sha256") or transfer.get("ok"))
        and bool(chain_ok.get("valid", chain_ok.get("ok", False)))
        and tamper_detected
    )
    return {
        "name": "01_uma_mutual_consent_airlock",
        "ok": passed,
        "detail": (
            f"default_gate={init_state.get('gate')} unilateral_blocked={blocked_unilateral} "
            f"mutual_ok={transfer.get('ok')} tamper_detected={tamper_detected}"
        ),
    }


def _check_pixel_os_static(tmp: Path) -> dict[str, Any]:
    res = verify_pixel_os_static(tmp / "pixel", device="panther")
    passed = bool(
        res.get("ok")
        and res.get("devices_count") == 9
        and res.get("deterministic")
        and res.get("auto_flash_allowed") is False
        and res.get("sentience_claimed") is False
    )
    return {
        "name": "02_pixel7_sovereign_os_static",
        "ok": passed,
        "detail": f"device={res.get('device')} devices={res.get('devices_count')} sha256={str(res.get('initramfs_sha256', ''))[:16]}",
    }


def _check_loopback_guards(tmp: Path) -> dict[str, Any]:
    allowed_ok = all(
        assert_loopback_url(u).startswith("http")
        for u in ("http://127.0.0.1:8774", "http://localhost:8774", "http://[::1]:8774")
    )
    rejected_urls = (
        "http://example.com:8774",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://127.0.0.1/data",
    )
    sync_blocked = 0
    for bad in rejected_urls:
        try:
            assert_loopback_url(bad)
        except ValueError:
            sync_blocked += 1
    beta_blocked = False
    try:
        build_beta_release_manifest(ROOT, out_dir=tmp / "bad_beta", rome_url="http://example.com:8774")
    except ValueError:
        beta_blocked = True
    passed = allowed_ok and sync_blocked == len(rejected_urls) and beta_blocked
    return {
        "name": "03_phone_sync_and_beta_loopback_guards",
        "ok": passed,
        "detail": f"loopback_allowed={allowed_ok} sync_blocked={sync_blocked}/{len(rejected_urls)} beta_blocked={beta_blocked}",
    }


def _check_braille_studio(tmp: Path) -> dict[str, Any]:
    canvas = BrailleCanvas(24, 16)
    canvas.draw_star(12, 8, arm=4)
    rows = canvas.render()
    braille_ok = bool(rows) and all(0x2800 <= ord(ch) <= 0x28FF for row in rows for ch in row)
    templates_ok = all(len(render_braille_template(t, cols=32)[1]) > 0 for t in ("zoe", "flower", "jellyfish"))
    dvx_ok = len(render_dvx_app_manager()) >= 6

    scaffold = scaffold_starter_app("hello_zoe", base_dir=tmp / "maker")
    app_src = Path(scaffold["app_py"]).read_text(encoding="utf-8")
    ast.parse(app_src)
    traversal_blocked = False
    try:
        scaffold_starter_app("../..", base_dir=tmp / "maker")
    except ValueError:
        traversal_blocked = True

    passed = braille_ok and templates_ok and dvx_ok and bool(scaffold.get("ok")) and traversal_blocked
    return {
        "name": "04_braille_studio_and_dvx_scaffold",
        "ok": passed,
        "detail": f"braille_rows={len(rows)} templates_ok={templates_ok} traversal_blocked={traversal_blocked}",
    }


def _check_gem_themes(tmp: Path) -> dict[str, Any]:
    eras = list_gem_eras()
    schemes = list_viewmax_schemes()
    ini = render_viewmax_ini(active_slot=1)
    bundle = export_gem_lineage_desktop_bundle(output_dir=tmp / "themes", active_slot=1)
    passed = (
        len(eras) == 8
        and len(schemes) == 10
        and "[ViewMAX]" in ini
        and bool(bundle.get("ok", True))
    )
    return {
        "name": "05_gem_historic_lineage_and_viewmax_schemes",
        "ok": passed,
        "detail": f"eras={len(eras)} schemes={len(schemes)} bundle_keys={len(bundle)}",
    }


def _check_zoeverse(tmp: Path) -> dict[str, Any]:
    realms = list_zoeverse_realms()
    map_lines = render_zoeverse_map("stem")
    vista = render_realm_braille_vista(realms[0])
    plate = export_zoeverse_atlas_plate(output_dir=tmp / "zoeverse")
    passed = len(realms) == 9 and len(map_lines) >= 5 and len(vista) >= 4 and bool(plate)
    return {
        "name": "06_zoeverse_9_realms_and_atlas",
        "ok": passed,
        "detail": f"realms={len(realms)} map_lines={len(map_lines)} vista_rows={len(vista)}",
    }


def _check_sisters() -> dict[str, Any]:
    sisters = list_sisters()
    routed = route_prompt_to_sister("Verify Atari .RSC binary layout and SymPy proof")
    signets = {s.signet for s in sisters}
    expected = {"ruby", "gem3", "atari", "sm124", "tetris", "dos", "hat", "sprout", "prism"}
    lead = routed.get("lead")
    honesty_ok = (
        routed.get("sentience_claimed") is False
        and routed.get("clinical_action_authorized") is False
        and routed.get("flight_control_authorized") is False
        and routed.get("tokens_used") == 0
    )
    passed = len(sisters) == 9 and signets == expected and lead is not None and honesty_ok
    return {
        "name": "07_sisters_9_signets_and_honesty_lock",
        "ok": passed,
        "detail": f"sisters={len(sisters)} signets_match={signets == expected} lead={getattr(lead, 'name', '')}",
    }


def _check_beta_manifest(tmp: Path) -> dict[str, Any]:
    manifest = build_beta_release_manifest(ROOT, out_dir=tmp / "beta", rome_url="http://127.0.0.1:1")
    manifest_file = Path(manifest["manifest_path"])
    honesty_ok = (
        manifest.get("tokens_used") == 0
        and manifest.get("loopback_only") is True
        and manifest.get("auto_flash_allowed") is False
        and manifest.get("sentience_claimed") is False
        and manifest.get("clinical_action_authorized") is False
        and manifest.get("flight_control_authorized") is False
    )
    passed = manifest_file.is_file() and honesty_ok and manifest.get("version") == BETA_HONESTY_LOCK["version"]
    return {
        "name": "08_beta_release_manifest_isolated",
        "ok": passed,
        "detail": f"version={manifest.get('version')} gates={manifest.get('beta_gates_passed')}/{manifest.get('beta_gates_total')}",
    }


def run_suite(*, write_report: bool = True) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="zoe-gemos-verify-") as td:
        tmp = Path(td)
        checks = [
            _check_uma_airlock(tmp),
            _check_pixel_os_static(tmp),
            _check_loopback_guards(tmp),
            _check_braille_studio(tmp),
            _check_gem_themes(tmp),
            _check_zoeverse(tmp),
            _check_sisters(),
            _check_beta_manifest(tmp),
        ]
    passed = all(c["ok"] for c in checks)
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "passed": passed,
        "checks_passed": sum(1 for c in checks if c["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "constitutional": {
            "external_actions": 0,
            "loopback_only": True,
            "auto_flash_allowed": False,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "clinical_action_authorized": False,
            "flight_control_authorized": False,
            "attribution": "Nicholas Michael Kloster, March 6, 2026",
        },
    }
    digest = hashlib.sha256(json.dumps(report, sort_keys=True).encode("utf-8")).hexdigest()
    report["evidence_sha256"] = digest
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the Zoe-GEM OS ecosystem suite offline.")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--no-write", action="store_true", help="do not overwrite evidence report JSON")
    args = parser.parse_args(argv)
    report = run_suite(write_report=not bool(args.no_write))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for c in report["checks"]:
            tag = "PASS" if c["ok"] else "FAIL"
            print(f"[{tag}] {c['name']} ({c['detail']})")
        print(
            f"\nZOE-GEM OS SUITE VERIFIER: {report['checks_passed']}/{report['checks_total']} "
            f"{'PASS' if report['passed'] else 'FAIL'} | SHA-256={report['evidence_sha256'][:16]}"
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

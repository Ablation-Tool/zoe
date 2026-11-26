"""Tests for the unified 42-component Zoe-GEM OS architecture, SPOTLIGHT.ACC, and EXPORT.ACC."""

from __future__ import annotations

import json
from pathlib import Path

from guiai.gem import gemos_view
from guiai.gem.geometry import verify as verify_scene
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.zoe_gem_os import (
    UNIFIED_OS_LAYERS,
    list_unified_components,
    os_suite_status,
    run_export_airlock,
    spotlight_route,
    unified_os_document,
    verify_unified_os,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_unified_os_manifest_covers_all_42_components() -> None:
    report = verify_unified_os(REPO_ROOT, include_airlock=False)
    assert report["ok"] is True, report["checks"]
    status = report["status"]
    assert status["total_components"] == 42
    assert status["sources_present"] == 42
    assert status["suite_count"] == 5
    assert status["canonical_repository"] == "https://github.com/Nicholas-Michael-Kloster/Zoe"
    assert [s["component_count"] for s in status["suites"]] == [9, 8, 6, 10, 9]
    inv = status["constitutional_invariants"]
    assert inv["sentience_claimed"] is False
    assert inv["l5_agi_qualified"] is False
    assert inv["clinical_action_authorized"] is False
    assert inv["cure_claim"] is False
    assert inv["auto_flash_allowed"] is False
    assert inv["external_actions"] == 0


def test_filtering_by_suite_sister_and_kind() -> None:
    suite1 = list_unified_components(REPO_ROOT, suite=1)
    assert len(suite1) == 9
    assert all(c["sister"] == "mono" for c in suite1)

    lumen_items = list_unified_components(REPO_ROOT, sister="lumen")
    assert {c["source_id"] for c in lumen_items} == {
        "nina",
        "dBA",
        "nuclide-color-framework-v2",
        "rhythm-lab",
    }

    sys_drivers = list_unified_components(REPO_ROOT, kind="sys")
    acc_units = list_unified_components(REPO_ROOT, kind="acc")
    app_units = list_unified_components(REPO_ROOT, kind="app")
    assert len(sys_drivers) + len(acc_units) + len(app_units) == 42


def test_spotlight_acc_routes_across_all_5_suites() -> None:
    probes = [
        ("scrub audio metadata before whisper", "AUDIO.SYS"),
        ("check github tos compliance before push", "EXPORT.ACC"),
        ("draw animated svg block diagram", "DRAWPLUS.APP"),
        ("tiered virtual memory pager context", "MEMBUS.SYS"),
        ("custom vm bytecode disassembler onnx", "AUDIT.APP"),
        ("preclinical protein sequence homology dorothy", "DOROTHY.APP"),
        ("opa compliance scorecard constitution", "SCUBA.APP"),
        ("book grounded librarian citation verify", "LIBRARIAN.APP"),
    ]
    for query, expected_unit in probes:
        res = spotlight_route(query, REPO_ROOT, limit=3)
        assert res["match_count"] >= 1, query
        assert res["matches"][0]["os_unit"] == expected_unit, (query, res["matches"][0])
        assert res["loopback_only"] is True
        assert res["external_actions"] == 0


def test_export_acc_airlock_passes_clean_zero_unsuppressed() -> None:
    airlock = run_export_airlock(REPO_ROOT, fail_on="MEDIUM")
    assert airlock["ok"] is True, airlock["unsuppressed_samples"]
    assert airlock["exit_code"] == 0
    assert airlock["unsuppressed_at_or_above_fail_on"] == 0
    assert airlock["files_scanned"] > 1000
    assert airlock["allowlist_entries"] > 0


def test_all_6_unified_os_gem_layers_verify_and_export(tmp_path: Path) -> None:
    env = GemOperatingEnvironment(zoe_root=REPO_ROOT)
    for layer_id in UNIFIED_OS_LAYERS:
        scene, rep = unified_os_document(layer_id, REPO_ROOT)
        check = verify_scene(scene)
        assert check.passed, (layer_id, check.text())
        assert rep["module"] == layer_id
        opened = env.open(layer_id)
        assert opened["layer"] == layer_id
        gem_out = tmp_path / f"{layer_id}.gem"
        exported = env.export(layer_id, gem_out)
        assert gem_out.is_file() and gem_out.stat().st_size > 128
        assert exported["layer"] == layer_id


def test_gemos_cli_unified_subcommands(capsys) -> None:
    assert gemos_view.main(["status", "--json"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["unified_components"] == 42
    assert st["os_suites"] == 5
    assert st["canonical_repository"] == "https://github.com/Nicholas-Michael-Kloster/Zoe"

    assert gemos_view.main(["apps", "--suite", "5", "--json"]) == 0
    apps = json.loads(capsys.readouterr().out)
    assert apps["count"] == 9

    assert gemos_view.main(["spotlight", "encrypt private poetry drawer", "--json"]) == 0
    sp = json.loads(capsys.readouterr().out)
    assert sp["matches"][0]["os_unit"] == "VAULT.SYS"

    assert gemos_view.main(["airlock", "--json"]) == 0
    al = json.loads(capsys.readouterr().out)
    assert al["ok"] is True
    assert al["exit_code"] == 0

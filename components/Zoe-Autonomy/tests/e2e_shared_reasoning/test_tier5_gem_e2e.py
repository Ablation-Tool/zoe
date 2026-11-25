"""Opaque-box E2E tests for Digital Research GEM (`seasip.info/Gem/index.html`) integration (`M_GEM`)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
from google.antigravity import types

from .conftest import (
    PYTHON_BIN,
    REPO_ROOT,
    assert_constitutional_invariants,
    monorepo_env,
    require_artifact,
    require_shared_reasoning,
    run_async,
)


def test_gem_e2e_public_exports_and_docs_attribution() -> None:
    sr = require_shared_reasoning()
    subs = sr.available_submodules()
    assert subs.get("gem_aes_vdi") is True

    for sym in (
        "GEM_AES_VDI_CONTRACT",
        "GemEventMultiQueue",
        "GemEventResult",
        "GemFormAlert",
        "GemVdiWorkstation",
        "GemWindowManager",
        "build_form_alert",
    ):
        assert getattr(sr, sym) is not None

    docs_path = require_artifact("docs/SHARED_REASONING_ARCHITECTURES.md")
    text = docs_path.read_text(encoding="utf-8")
    assert "seasip.info/Gem/index.html" in text
    assert "Gary Kildall" in text
    assert "Nicholas Michael Kloster" in text


def test_gem_e2e_aes_windows_evnt_multi_and_limit() -> None:
    GemEventMultiQueue = require_shared_reasoning("gem_aes_vdi", "GemEventMultiQueue")
    GemWindowManager = require_shared_reasoning("gem_aes_vdi", "GemWindowManager")
    MAX_AES_APP_WINDOWS = require_shared_reasoning("gem_aes_vdi", "MAX_AES_APP_WINDOWS")
    MU_MESAG = require_shared_reasoning("gem_aes_vdi", "MU_MESAG")
    MU_TIMER = require_shared_reasoning("gem_aes_vdi", "MU_TIMER")
    MN_SELECTED = require_shared_reasoning("gem_aes_vdi", "MN_SELECTED")

    q = GemEventMultiQueue()
    wm = GemWindowManager(event_queue=q)
    for idx in range(MAX_AES_APP_WINDOWS):
        h = wm.wind_create(0x0B, 10 + idx * 8, 30, 180, 110, title=f"Chair {idx + 1}")
        assert h > 0
        wm.wind_open(h)

    assert wm.wind_create(0x0B, 20, 40, 180, 110, title="TooMany") == -1
    wm.wind_set(1, "top", True)
    wm.menu_tnormal(2, normal=False)

    seen_types: list[int] = []
    while q.pending_count() > 0:
        res = q.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=10)
        assert_constitutional_invariants(res.to_dict(), require_offline=True)
        if res.message is not None:
            seen_types.append(int(res.message["msg_type"]))
    assert MN_SELECTED in seen_types
    assert_constitutional_invariants(wm.summary(), require_offline=True)


def test_gem_e2e_arch8_form_alert_and_boundaries() -> None:
    build_form_alert = require_shared_reasoning("gem_aes_vdi", "build_form_alert")
    HumanSteeringDetector = require_shared_reasoning("human_steering", "HumanSteeringDetector")
    VerifiedPathOption = require_shared_reasoning("human_steering", "VerifiedPathOption")

    det = HumanSteeringDetector()
    rep = det.detect(
        [
            VerifiedPathOption("formal_a", "Formal path", "verified", ("ev-1",), 0.91, "exact", True, ("formal",), "Lab"),
            VerifiedPathOption("local_b", "Local path", "verified", ("ev-2",), 0.87, "fast", True, ("local",), "Lab"),
        ],
        high_impact=True,
    )
    assert rep.fork_detected is True
    assert rep.gem_form_alert is not None
    assert rep.gem_form_alert["form_alert_string"].startswith("[2][")
    assert_constitutional_invariants(rep, require_offline=True)

    with pytest.raises(ValueError):
        build_form_alert(4, ["bad icon"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(2, ["1", "2", "3", "4", "5", "6"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(2, ["too many buttons"], ["A", "B", "C", "D"])


def test_gem_e2e_sandbox_vdi_rsc_positive_and_negative() -> None:
    GemVdiWorkstation = require_shared_reasoning("gem_aes_vdi", "GemVdiWorkstation")
    build_default_atari_rsc = require_shared_reasoning("gem_aes_vdi", "build_default_atari_rsc")
    RealitySandboxLab = require_shared_reasoning("sandbox_labs", "RealitySandboxLab")

    ws = GemVdiWorkstation()
    scene = ws.build_shared_reasoning_scene({"quorum_verdict": "COORDINATE_CONSENSUS", "fork_detected": True})
    lab = RealitySandboxLab()

    vdi_ok = lab.verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    assert vdi_ok.passed is True
    assert vdi_ok.ground_truth["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}
    assert_constitutional_invariants(vdi_ok, require_offline=True)

    vdi_bad = lab.verify_gem_vdi_scene(
        {
            "schema_version": 1,
            "id": "out-of-range-vdi",
            "canvas": {"width": 50000, "height": 500},
            "objects": [{"id": "o1", "type": "rectangle", "bounds": [0, 0, 50000, 100]}],
        }
    )
    assert vdi_bad.passed is False
    assert vdi_bad.counterexample is not None

    rsc_ok = lab.verify_gem_rsc_bytes(build_default_atari_rsc(), label="ZOE_E2E.RSC")
    assert rsc_ok.passed is True
    assert_constitutional_invariants(rsc_ok, require_offline=True)

    rsc_bad = lab.verify_gem_rsc_bytes(b"\x00\x01\x02", label="TRUNCATED.RSC")
    assert rsc_bad.passed is False
    assert rsc_bad.counterexample is not None


def test_gem_e2e_supervisor_security_gates() -> None:
    LiveProcessSupervisor = require_shared_reasoning("process_supervision", "LiveProcessSupervisor")
    MAX_GEM_METAFILE_BYTES = require_shared_reasoning("gem_aes_vdi", "MAX_GEM_METAFILE_BYTES")

    sup = LiveProcessSupervisor()
    res_trav = run_async(
        sup.supervise_tool_call(
            types.ToolCall(id="e2e-gem-1", name="load_rsc", args={"rsc_path": "../../etc/passwd"})
        )
    )
    assert res_trav.allow is False

    res_size = run_async(
        sup.supervise_tool_call(
            types.ToolCall(
                id="e2e-gem-2",
                name="write_gem",
                args={"metafile_bytes_len": MAX_GEM_METAFILE_BYTES + 128},
            )
        )
    )
    assert res_size.allow is False

    res_coord = run_async(
        sup.supervise_tool_call(
            types.ToolCall(id="e2e-gem-3", name="draw_vdi", args={"bounds": [-40000, 0, 100, 100]})
        )
    )
    assert res_coord.allow is False


def test_gem_e2e_orchestrator_export_and_verifier_cli(tmp_path: Path) -> None:
    SharedReasoningOrchestrator = require_shared_reasoning("orchestrator", "SharedReasoningOrchestrator")
    SharedReasoningTaskSpec = require_shared_reasoning("orchestrator", "SharedReasoningTaskSpec")

    out_dir = tmp_path / "gem_artifacts"
    orch = SharedReasoningOrchestrator(mode="offline", offline_only=True, state_dir=tmp_path / "state")
    report = orch.run(
        SharedReasoningTaskSpec(
            prompt="E2E verify all 9 shared-reasoning architectures with Digital Research GEM.",
            high_impact=True,
            gem_vdi_output_dir=out_dir,
        )
    )
    assert report.gem_desktop_report is not None
    assert report.gem_desktop_report["passed"] is True
    assert report.gem_desktop_report["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}
    assert report.counterpoint_result.gem_desktop_trace is not None
    assert report.counterpoint_result.gem_desktop_trace["aes_messages_count"] > 0
    assert (out_dir / "shared_reasoning_desktop.gem").stat().st_size > 48
    assert (out_dir / "ZOE_SHARED.RSC").stat().st_size >= 36
    assert_constitutional_invariants(report, require_offline=True)

    verifier = require_artifact("scripts/verify_shared_reasoning.py")
    proc = subprocess.run(
        [PYTHON_BIN, str(verifier), "--json"],
        cwd=str(REPO_ROOT),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"verify_shared_reasoning.py failed: {proc.stderr}\n{proc.stdout}"
    payload = json.loads(proc.stdout)
    assert payload["passed"] is True
    assert payload["gem_aes_vdi_integration"]["passed"] is True
    assert payload["rotation_log"]["slots_parsed"] == 18
    assert payload["rotation_log"]["consecutive_repeats"] == 0
    assert_constitutional_invariants(payload, require_offline=True)

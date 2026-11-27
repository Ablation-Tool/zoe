"""Unit and integration tests for the Digital Research GEM AES/VDI/RSC bridge (`M_GEM`)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import struct
import sys

import pytest
from google.antigravity import types

from zoe_autonomy.shared_reasoning import (
    GEM_AES_VDI_CONTRACT,
    MAX_AES_APP_WINDOWS,
    MAX_GEM_METAFILE_BYTES,
    MN_SELECTED,
    MU_BUTTON,
    MU_KEYBD,
    MU_MESAG,
    MU_TIMER,
    WM_CLOSED,
    WM_REDRAW,
    WM_TOPPED,
    AlphaEvolveLoop,
    CounterpointChairsEngine,
    EpistemicBlackboard,
    FourPeerQuorumEngine,
    GemEventMultiQueue,
    GemVdiWorkstation,
    GemWindowManager,
    HumanSteeringDetector,
    KlosterMCTSSearch,
    LiveProcessSupervisor,
    PeerConfidenceVector,
    ProblemChair,
    RealitySandboxLab,
    SharedReasoningOrchestrator,
    SharedReasoningTaskSpec,
    System2To1Distiller,
    TestCase,
    ThoughtCandidate,
    VerifiedPathOption,
    available_submodules,
    build_default_atari_rsc,
    build_form_alert,
    inspect_gem_rsc,
)


def test_gem_aes_vdi_submodule_and_exports_available() -> None:
    subs = available_submodules()
    assert subs["gem_aes_vdi"] is True
    assert MAX_AES_APP_WINDOWS == 7
    assert MAX_GEM_METAFILE_BYTES == 1_048_576


def test_gem_event_multi_queue_fifo_and_validation() -> None:
    q = GemEventMultiQueue()
    raw1 = q.post_message(WM_REDRAW, sender_apid=1, w3=2, w4=10, w5=20, w6=300, w7=200)
    raw2 = q.post_message(MN_SELECTED, sender_apid=1, w3=3, w4=4)
    assert len(raw1) == 16
    assert len(raw2) == 16
    assert q.pending_count() == 2

    ev1 = q.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=25)
    assert ev1.matched_flags & MU_MESAG
    assert ev1.message is not None
    assert ev1.message["msg_type"] == WM_REDRAW
    assert ev1.message["data"][:5] == [2, 10, 20, 300, 200]
    assert ev1.raw_bytes == raw1

    ev2 = q.evnt_multi(MU_MESAG | MU_KEYBD | MU_BUTTON, key_code=0x1C0D, button_state=1)
    assert ev2.matched_flags == (MU_MESAG | MU_KEYBD | MU_BUTTON)
    assert ev2.message is not None and ev2.message["msg_type"] == MN_SELECTED
    assert ev2.key_code == 0x1C0D
    assert ev2.button_state == 1
    assert q.pending_count() == 0

    ev_timer = q.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=50)
    assert ev_timer.matched_flags == MU_TIMER
    assert ev_timer.message is None
    assert ev_timer.timer_elapsed_ms == 50

    with pytest.raises(ValueError):
        q.evnt_multi(0)
    with pytest.raises(ValueError):
        q.evnt_multi(MU_TIMER, timer_ms=-5)
    with pytest.raises(ValueError):
        q.post_message(WM_REDRAW, w3=40000)


def test_gem_window_manager_7_window_limit_tiling_and_menus() -> None:
    q = GemEventMultiQueue()
    wm = GemWindowManager(screen_w=640, screen_h=480, event_queue=q)
    bar = wm.menu_bar(active_index=2)
    assert bar["active_title"] == "Chairs"

    handles = []
    for idx in range(MAX_AES_APP_WINDOWS):
        h = wm.wind_create(0x0B, 10 + idx * 10, 30, 180, 120, title=f"Win {idx + 1}", layer_id=f"L{idx}")
        assert h == idx + 1
        wm.wind_open(h)
        handles.append(h)

    # 8th simultaneous window must return -1 per PC GEM AES spec
    assert wm.wind_create(0x0B, 50, 50, 160, 100, title="Overflow") == -1

    top_res = wm.wind_set(handles[2], "top", True)
    assert top_res["top_handle"] == handles[2]
    assert wm.wind_get(handles[2], "top")["is_top"] is True

    # GEM/2 non-overlapping tiling across all open windows
    tiled = wm.tile_windows_gem2()
    assert len(tiled) == MAX_AES_APP_WINDOWS
    rect_list = list(tiled.values())
    for i in range(len(rect_list)):
        ax, ay, aw, ah = rect_list[i]
        for j in range(i + 1, len(rect_list)):
            bx, by, bw, bh = rect_list[j]
            separated = (ax + aw <= bx) or (bx + bw <= ax) or (ay + ah <= by) or (by + bh <= ay)
            assert separated, f"Tiled GEM/2 windows overlapped: {rect_list[i]} vs {rect_list[j]}"

    mn_raw = wm.menu_tnormal(2, normal=False)
    assert struct.unpack("<8h", mn_raw)[0] == MN_SELECTED

    close_raw = wm.wind_close(handles[0])
    assert struct.unpack("<8h", close_raw)[0] == WM_CLOSED
    wm.wind_delete(handles[0])
    # Slot freed -> new create succeeds
    reused = wm.wind_create(0x0B, 10, 30, 160, 100, title="Reused")
    assert reused == 1
    assert wm.summary()["constitutional"]["external_actions"] == 0


def test_gem_form_alert_and_rsc_roundtrip() -> None:
    alert = build_form_alert(
        2,
        ["Verified fork detected", "Select preferred path"],
        ["Select Path", "Stop/Reject", "Reversible"],
        default_btn=1,
        endian="<",
    )
    assert alert.form_alert_string == "[2][Verified fork detected|Select preferred path][Select Path|Stop/Reject|Reversible]"
    assert alert.object_tree_summary["rsh_ntree"] == 1
    assert alert.object_tree_summary["rsh_nobs"] >= 6
    parsed = inspect_gem_rsc(alert.rsc_bytes, label="ALERT_LE.RSC")
    assert parsed["endian"] == "<"
    assert parsed["rsh_nobs"] == alert.object_tree_summary["rsh_nobs"]
    d = alert.to_dict()
    assert d["external_actions"] == 0
    assert d["visual_evidence_only"] is True

    # Big-endian Atari TOS variant
    alert_be = build_form_alert(1, ["Atari TOS check"], ["OK"], endian=">")
    parsed_be = inspect_gem_rsc(alert_be.rsc_bytes, label="ALERT_BE.RSC")
    assert parsed_be["endian"] == ">"

    with pytest.raises(ValueError):
        build_form_alert(9, ["Bad icon"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(1, [], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(1, ["a", "b", "c", "d", "e", "f"], ["OK"])
    with pytest.raises(ValueError):
        build_form_alert(1, ["Too many buttons"], ["1", "2", "3", "4"])
    with pytest.raises(ValueError):
        build_form_alert(1, ["Bad default"], ["OK"], default_btn=2)


def test_gem_vdi_workstation_cga_vga_ndc_and_sandbox_labs() -> None:
    ws = GemVdiWorkstation(device="vga", theme_key="zoe-viewmax3")
    opened = ws.v_opnwk("vga")
    assert opened["opened"] is True and opened["dimensions"] == [640, 480]
    attrs = ws.set_attributes(vsl_color="black", vsf_color="#00756B", vsf_interior=1, vst_height=160)
    assert attrs["vsf_color"] == "#00756B"

    scene = ws.build_shared_reasoning_scene({"fork_detected": True, "quorum_verdict": "CONSENSUS"})
    compiled = ws.compile_and_verify_vdi(scene, profiles=("cga", "vga", "ndc"))
    assert compiled["passed"] is True
    assert compiled["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}
    assert compiled["visual_evidence_only"] is True
    assert ws.v_clswk()["opened"] is False

    lab = RealitySandboxLab()
    v_ok = lab.verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    assert v_ok.passed is True
    assert v_ok.lab_name == "gem_vdi_lab"

    # Negative boundary: coordinate outside int16 (> 32767)
    bad_scene_doc = {
        "schema_version": 1,
        "id": "bad-coords",
        "canvas": {"width": 40000, "height": 200},
        "objects": [{"id": "r1", "type": "rectangle", "bounds": [0, 0, 40000, 100]}],
    }
    v_bad = lab.verify_gem_vdi_scene(bad_scene_doc)
    assert v_bad.passed is False
    assert v_bad.counterexample is not None

    # Atari .RSC positive + corrupt negative controls
    atari_bytes = build_default_atari_rsc()
    r_ok = lab.verify_gem_rsc_bytes(atari_bytes, label="ZOE_ATARI.RSC")
    assert r_ok.passed is True
    assert r_ok.lab_name == "gem_rsc_lab"

    r_bad = lab.verify_gem_rsc_bytes(b"NOT_A_VALID_RSC", label="CORRUPT.RSC")
    assert r_bad.passed is False
    assert r_bad.counterexample is not None

    with pytest.raises(TypeError):
        lab.verify_gem_rsc_bytes("not-bytes")  # type: ignore[arg-type]


def test_cross_architecture_gem_hooks(tmp_path: Path) -> None:
    # Arch 2: Process Supervision GEM payload audit
    sup = LiveProcessSupervisor()
    f_coord = sup.audit_gem_payload({"bounds": [0, 0, 50000, 100]})
    assert any(f.rule_id == "gem_vdi_coord_out_of_bounds" for f in f_coord)
    f_size = sup.audit_gem_payload({"metafile_bytes_len": MAX_GEM_METAFILE_BYTES + 1})
    assert any(f.rule_id == "gem_metafile_size_exceeded" for f in f_size)
    f_path = sup.audit_gem_payload({"rsc_path": "../../etc/passwd"})
    assert any(f.rule_id == "gem_path_traversal_blocked" for f in f_path)

    tc_bad = types.ToolCall(id="tc-gem-bad", name="render_gem", args={"rsc_path": "/etc/shadow"})
    hook_res = asyncio.run(sup.supervise_tool_call(tc_bad))
    assert hook_res.allow is False

    # Arch 6: Blackboard Spatial IR
    bb = EpistemicBlackboard()
    m = bb.post_measurement(
        source_agent="gem_test",
        input_desc="gem test",
        method="deterministic",
        scope="unit",
        limitations="none",
        value=1.0,
        sampled_only=False,
    )
    ev = bb.promote_to_evidence(m.record_id, verifier_name="RealitySandboxLab", passed=True, rationale="Verified deterministically")
    bb_ir = bb.to_gem_spatial_ir()
    assert bb_ir["visual_evidence_only"] is True
    assert RealitySandboxLab().verify_gem_vdi_scene(bb_ir, profiles=("cga", "vga")).passed is True

    # Arch 1, 3, 4, 5 additive GEM helpers
    loop = AlphaEvolveLoop()
    ae_res = loop.evolve(
        "def f(x):\n    return x\n",
        [TestCase(inputs={"x": 2.0}, expected=4.0), TestCase(inputs={"x": 3.0}, expected=9.0)],
        generations=2,
        offspring_per_gen=4,
    )
    assert ae_res.to_gem_spatial_ir()["visual_evidence_only"] is True

    mcts = KlosterMCTSSearch()
    mcts_res = mcts.run(
        {"depth": 0},
        expand_fn=lambda s: [ThoughtCandidate(action="a", state={"depth": 1}, prior_prob=0.7)] if s["depth"] == 0 else [],
        eval_fn=lambda s: {"value": 0.9, "observations": (0, 0, 0), "is_terminal": s["depth"] > 0},
        tau=0.08,
        max_iterations=4,
    )
    assert mcts_res.to_gem_spatial_ir()["visual_evidence_only"] is True

    qe = FourPeerQuorumEngine()
    qr = qe.evaluate(
        [
            PeerConfidenceVector("zoe", (0.7, 0.2, 0.1), "document", "p1", "i1"),
            PeerConfidenceVector("clara", (0.6, 0.25, 0.15), "validated_reflection", "p2", "i2"),
            PeerConfidenceVector("antigravity", (0.8, 0.15, 0.05), "model", "p3", "i3"),
            PeerConfidenceVector("user", (0.65, 0.25, 0.10), "user", "p4", "i4"),
        ]
    )
    assert qr.to_gem_spatial_ir()["visual_evidence_only"] is True

    distiller = System2To1Distiller(blackboard=bb)
    gem_art = distiller.distill_gem_rule(
        rule_id="gem_vdi",
        pattern=".*vdi.*",
        response="GEM VDI scenes are visual_evidence_only=True.",
        evidence_id=ev.record_id,
    )
    assert gem_art.artifact_kind == "eliza_rule"

    # Arch 8: ForkPointReport gem_form_alert
    detector = HumanSteeringDetector()
    fork_active = detector.detect(
        [
            VerifiedPathOption("path_a", "Path A", "verified", (ev.record_id,), 0.9, "tradeoff a", True, ("formal",), "LabA"),
            VerifiedPathOption("path_b", "Path B", "verified", (ev.record_id,), 0.85, "tradeoff b", True, ("local",), "LabB"),
        ],
        high_impact=True,
    )
    assert fork_active.fork_detected is True
    assert fork_active.gem_form_alert is not None
    assert fork_active.gem_form_alert["contract"] == GEM_AES_VDI_CONTRACT

    fork_suppressed = detector.detect([VerifiedPathOption("only_one", "Single", "verified", (ev.record_id,), 0.9, "t", True, ("formal",), "LabA")])
    assert fork_suppressed.fork_detected is False
    assert fork_suppressed.gem_form_alert is None

    # Arch 9: Counterpoint Chairs GEM AES trace
    cp = CounterpointChairsEngine(offline_only=True, emit_gem_aes_trace=True)
    cp_res = cp.run(
        [
            ProblemChair(chair_id="c1", title="Chair 1", prompt="Audit 1"),
            ProblemChair(chair_id="c2", title="Chair 2", prompt="Audit 2"),
        ],
        rounds=1,
    )
    assert cp_res.gem_desktop_trace is not None
    assert cp_res.gem_desktop_trace["aes_messages_count"] >= 4

    # Orchestrator with GEM desktop enabled (with output dir) and disabled
    orch = SharedReasoningOrchestrator(mode="offline", offline_only=True, state_dir=tmp_path / "state")
    gem_out = tmp_path / "gem_out"
    rep_on = orch.run(SharedReasoningTaskSpec(prompt="GEM integration check", gem_vdi_output_dir=gem_out, high_impact=True))
    assert rep_on.gem_desktop_report is not None
    assert rep_on.gem_desktop_report["passed"] is True
    assert rep_on.gem_desktop_report["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}
    assert (gem_out / "shared_reasoning_desktop.gem").is_file()
    assert (gem_out / "shared_reasoning_desktop.json").is_file()
    assert (gem_out / "ZOE_SHARED.RSC").is_file()

    orch_off = SharedReasoningOrchestrator(mode="offline", offline_only=True, state_dir=tmp_path / "state_off")
    rep_off = orch_off.run(SharedReasoningTaskSpec(prompt="GEM disabled check", enable_gem_desktop=False))
    assert rep_off.gem_desktop_report is None


def test_zoe_chat_and_shared_reasoning_mcp_wiring(tmp_path: Path) -> None:
    import json
    import subprocess
    from zoe_autonomy.chat import ZoeChat

    repo_root = Path(__file__).resolve().parents[3]
    chat = ZoeChat(repo_root, state_root=tmp_path / "chat_state")
    keep, gem_reply = chat.handle("gem-desk zoe-viewmax3")
    assert keep is True
    assert "passed=True" in gem_reply
    assert "visual_evidence_only=True" in gem_reply

    keep2, sr_reply = chat.handle("shared-reasoning verify quadratic and gem desk")
    assert keep2 is True
    assert "Shared-Reasoning Run" in sr_reply
    assert "GEM VDI/RSC=True" in sr_reply
    assert "external_actions=0" in sr_reply

    mcp_script = repo_root / "scripts" / "zoe_shared_reasoning_mcp.py"
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "verify_gem_vdi_desk", "arguments": {"theme_key": "zoe-viewmax3"}}},
    ]
    proc = subprocess.run(
        [sys.executable, str(mcp_script)],
        cwd=str(repo_root),
        input="\n".join(json.dumps(r) for r in reqs) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    resps = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(resps) == 3
    names = {t["name"] for t in resps[1]["result"]["tools"]}
    assert names == {
        "run_shared_reasoning_suite",
        "verify_gem_vdi_desk",
        "query_deepmind_alphafold_target",
        "build_alphafold3_complex_job",
    }
    sc = resps[2]["result"]["structuredContent"]
    assert sc["passed"] is True
    assert sc["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}
    assert sc["external_actions"] == 0

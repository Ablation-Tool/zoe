"""Tier 4 E2E Tests: 5 realistic end-to-end application workflows across F1-F10."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import numpy as np

from conftest import (
    NODE_BIN,
    PYTHON_BIN,
    REPO_ROOT,
    assert_constitutional_flags,
    assert_mobile_clean_of_phase2_artifacts,
    http_get,
    http_post,
    monorepo_env,
    standalone_ablation_env,
)


def test_t4_scenario1_preclinical_neuro_oncology_and_3plane_optics(
    eliza_server,
    zoe_chat_factory,
    dorothy_report,
    botanical_report,
    c28_report,
):
    """Scenario 1: Preclinical neuro-oncology sparing & 3-plane optical slice workflow."""
    chat = zoe_chat_factory("scen1_chat")
    for cmd in ("botanical", "c28", "optics"):
        keep, reply = chat.handle(cmd)
        assert keep is True
        assert "I could not complete that safely" not in reply
        assert "do not have enough indexed evidence" not in reply
        assert "The 11-World Zoe Renaissance Orbit" not in reply

    optics = dorothy_report["theorem14_volumetric_optics"]
    overlay = dorothy_report["c27_c28_filbin_sparing_overlay"]
    assert optics["verified"] is True
    for plane in ("coronal_yz", "sagittal_xy", "horizontal_xz"):
        assert optics["planes"][plane]["delta_opt"] > 0.0
        assert optics["planes"][plane]["z_kloster"] > 10.0
    assert abs(optics["csr_negative_control"]["z_kloster"]) < 2.5

    assert overlay["summary"]["midline_target_count"] == 5
    assert overlay["summary"]["healthy_guardrail_count"] == 7
    winners = set(overlay["c27_c28_compound_gate"]["compact_cns_selective_candidates"])
    assert {"artemisinin", "dordaviprone"}.issubset(winners)
    assert not ({"curcumin", "berberine", "crocin", "paclitaxel"} & winners)

    base = eliza_server["base_url"]
    for route in ("/botanical", "/optics"):
        st, _, raw = http_get(base, route)
        assert st == 200
        assert "0 Cloud Tokens" in raw.decode("utf-8")
    for api_route in ("/api/kloster/botanical-atlas", "/api/kloster/pharmacophore-c28"):
        st, _, raw = http_get(base, api_route)
        assert st == 200
        assert_constitutional_flags(json.loads(raw.decode("utf-8")))

    assert_constitutional_flags(dorothy_report)
    assert_constitutional_flags(botanical_report)
    assert_constitutional_flags(c28_report)


def test_t4_scenario2_cern_trigger_and_standalone_firmware_forensics(
    tmp_path,
    cern_report,
    zoe_mind_factory,
    zoe_chat_factory,
):
    """Scenario 2: LHC multi-bunch calorimeter trigger & standalone firmware entropy forensics."""
    from ablation.analyzers.entropy_mapper import EntropyMapper

    rng = np.random.default_rng(20260801)
    firmware = (
        b"\x00" * 512
        + bytes((i * 3) % 48 for i in range(512))
        + rng.integers(0, 256, size=256, dtype=np.uint8).tobytes()
        + b"\x00" * 256
    )
    fw_path = tmp_path / "device_fw.bin"
    fw_path.write_bytes(firmware)

    # Standalone ablation subprocess (no guiai-lab on PYTHONPATH)
    cli_proc = subprocess.run(
        [PYTHON_BIN, "-m", "ablation.cli", "analyze", str(fw_path), "--entropy"],
        cwd=str(REPO_ROOT),
        env=standalone_ablation_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert cli_proc.returncode == 0, cli_proc.stderr
    assert "Entropy regions (" in cli_proc.stdout
    assert "ENCRYPTED" in cli_proc.stdout

    # Compare monorepo EntropyMapper against standalone payload classification
    mono_res = EntropyMapper(str(fw_path), window_size=256, use_kloster=True).run()
    assert mono_res.kloster_stopping_summary["backend"] == "guiai"
    enc_offsets = [w.offset for w in mono_res.windows if w.cls == "ENCRYPTED"]
    assert 1024 in enc_offsets

    # Verify CERN VCD multi-bunch calorimeter trigger + negative controls
    assert cern_report["all_verified"] is True
    streams = cern_report["theorem13_multibunch_stopping"]["streams"]
    assert streams["signal_jet_shower"]["action"] == "DECIDE_SIGNAL"
    assert streams["bg_diffuse_pileup"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert streams["bg_sticky_hotspike"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"

    # Triage via ZoeOSMind & ZoeChat
    mind = zoe_mind_factory("scen2_mind")
    turn_ab = mind.process_turn("Analyze ELF binary entropy and opcode anomalies with ablation", offline_only=True)
    turn_ce = mind.process_turn("Inspect CERN helios calorimeter trigger waveform VCD", offline_only=True)
    assert turn_ab["top_engine"] == "ablation"
    assert turn_ce["top_engine"] == "cern-console"
    assert turn_ab["stem_routing"]["estimated_cloud_tokens"] == 0
    assert turn_ce["stem_routing"]["estimated_cloud_tokens"] == 0

    chat = zoe_chat_factory("scen2_chat")
    _, t13_reply = chat.handle("theorem13")
    assert "I could not complete that safely" not in t13_reply
    assert "do not have enough indexed evidence" not in t13_reply
    assert "The 11-World Zoe Renaissance Orbit" not in t13_reply


def test_t4_scenario3_zoe_os_quorum_echo_rejection_and_collab_proof(
    tmp_path,
    eliza_server,
    zoe_mind_factory,
    zoe_chat_factory,
):
    """Scenario 3: Multi-engine Zoe OS turn, /teamwork quorum, echo-chamber rejection & collaboration proof."""
    from zoe_autonomy.collaboration import CollaborationBridge, verify_collaboration_proof
    from zoe_autonomy.stem_layering import route_stem
    from zoe_autonomy.zoe_os_mind import ZoeOSMind

    state_dir = tmp_path / "scen3_os_state"
    mind1 = ZoeOSMind(REPO_ROOT, state_dir)
    mind1.remember_goal("S01", "Audit Theorem 15 consensus & proof packet", "research", priority=1)
    multi = mind1.process_turn("Compare CERN collider waveform pulses with Dorothy brain gamma rhythms", offline_only=True)
    assert multi["decision"] == "COORDINATE_MULTI_ENGINE"
    assert multi["theorem15_consensus"]["verdict"] == "COORDINATE_CONSENSUS"

    # Echo-chamber and privacy exfiltration guards
    echo_dists = [[0.55, 0.35] + [0.10 / 15.0] * 15] * 3
    echo_turn = mind1.process_turn(
        "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
        committee_distributions=echo_dists,
        abstain_on_echo_chamber=True,
    )
    assert echo_turn["decision"] == "ABSTAIN_CONSENSUS_GUARD"
    assert echo_turn["theorem15_consensus"]["echo_chamber_detected"] is True

    fw_turn = mind1.process_turn(
        "Export private vault",
        payload_metadata={"source": "safeconvert_vault", "contains_secret_pin": True},
    )
    assert fw_turn["blocked"] is True
    assert fw_turn["decision"] == "BLOCK_PRIVACY_EXFILTRATION"

    # Cross-session reload
    del mind1
    mind2 = ZoeOSMind(REPO_ROOT, state_dir)
    snap = mind2.snapshot()
    assert snap["session_count"] >= 2
    assert snap["goals_count"] == 1
    assert snap["privacy_blocks"] == 1
    assert snap["ledger_integrity"]["intact"] is True
    assert_constitutional_flags(snap)

    # Stem layering /teamwork quorum locally & via HTTP
    dec = route_stem(
        "Architect a multi-file distributed concurrency refactor with formal invariant proof and teamwork",
        files_count=6,
        multi_file=True,
    )
    assert dec.teamwork_recommended is True
    assert dec.quorum_arbitration["verdict"] == "COORDINATE_CONSENSUS"

    st_http, _, raw_http = http_post(
        eliza_server["base_url"],
        "/api/stem/route",
        {"prompt": "Orchestrate teamwork verification proof", "files_count": 5, "multi_file": True},
    )
    assert st_http == 200
    assert json.loads(raw_http.decode("utf-8"))["constitutional"]["cloud_tokens_used"] == 0

    # Collaboration proof roundtrip + ZoeChat theorem15 / proof-packet
    class _Gateway:
        def list(self):
            return [{"id": "kimi", "enabled": True, "owner": True, "executable_available": True}]

        def invoke(self, identifier, prompt, timeout=60):
            return {"id": identifier, "succeeded": True, "content": "Verified synthesis.", "audit_hash": "s3"}

    bridge = CollaborationBridge(_Gateway())
    evidence = [{"citation": "PROOF-PACKET.md:1", "content": "Operational Metacognition", "kind": "document", "score": 2.0, "coverage": 0.5}]
    bridge.consult("Verify consensus proof", evidence)
    proof_path = bridge.save_proof(tmp_path / "scen3_proof.json")["path"]
    assert verify_collaboration_proof(json.loads(Path(proof_path).read_text(encoding="utf-8")))["verified"] is True

    chat = zoe_chat_factory("scen3_chat")
    for cmd in ("theorem15", "proof-packet"):
        _, reply = chat.handle(cmd)
        assert "I could not complete that safely" not in reply
        assert "do not have enough indexed evidence" not in reply
        assert "The 11-World Zoe Renaissance Orbit" not in reply


def test_t4_scenario4_groove_onset_poincare_and_observatory(
    tmp_path,
    eliza_server,
    groove_report,
    zoe_mind_factory,
):
    """Scenario 4: Musical groove onset & Poincare return-cloud forensics via Observatory."""
    from guiai.gem.groove_forensics import (
        analyze_onset_stream,
        build_valid_protracker_mod_bytes,
        parse_mod_onsets_pure,
        render_groove_showcase_wav,
    )

    assert groove_report["all_verified"] is True
    mod_onsets, mod_step = parse_mod_onsets_pure(build_valid_protracker_mod_bytes(bpm=125, speed=6))
    mod_res = analyze_onset_stream("scen4_mod", mod_onsets, mod_step)
    assert mod_res["poincare_quadrat_zk"]["poincare_regime"] == "RIGID_GRID_QUANTIZED"

    rng = np.random.default_rng(20261111)
    step = 0.125
    dilla_onsets = []
    drift = 0.0
    for i in range(128):
        drift = 0.72 * drift + float(rng.normal(0.0, 0.0024))
        dilla_onsets.append(i * step + (0.020 if i % 2 == 1 else -0.004) + drift)
    dilla_res = analyze_onset_stream("scen4_dilla", dilla_onsets, step)
    assert dilla_res["poincare_quadrat_zk"]["poincare_regime"] == "CLUSTERED_GROOVE_POCKET"
    assert dilla_res["kloster_stopping"]["action"] == "DECIDE_SIGNAL"

    wav_path = tmp_path / "scen4_groove.wav"
    wav_meta = render_groove_showcase_wav(
        [i * step for i in range(32)],
        dilla_onsets[:32],
        [i * (2.0 / 3.0) for i in range(12)],
        [i * 1.0 for i in range(8)],
        out_wav=wav_path,
    )
    assert wav_path.is_file() and wav_meta["bytes"] > 100_000

    mind = zoe_mind_factory("scen4_mind")
    turn = mind.process_turn("Analyze helen groove polyrhythm poincare attractor from mod", offline_only=True)
    assert turn["top_engine"] == "helen"

    base = eliza_server["base_url"]
    st_opt, _, _ = http_get(base, "/optics")
    st_t14, _, raw_t14 = http_get(base, "/api/kloster/theorem14")
    assert st_opt == 200 and st_t14 == 200
    assert json.loads(raw_t14.decode("utf-8"))["all_verified"] is True


def test_t4_scenario5_full_observatory_js_docs_orbit_and_mobile_cleanliness(
    eliza_server,
    elegance_report,
):
    """Scenario 5: Full Observatory HTTP walkthrough, node --check, docs/orbit supply chain & mobile/ check."""
    base = eliza_server["base_url"]

    # Walk Observatory HTML pages & run node --check on every inline script + app.js
    for route in ("/", "/orbit", "/proof", "/botanical", "/optics"):
        st, _, raw = http_get(base, route)
        assert st == 200, route
        html_txt = raw.decode("utf-8")
        for js in re.findall(r"<script[^>]*>(.*?)</script>", html_txt, flags=re.DOTALL | re.IGNORECASE):
            proc = subprocess.run([NODE_BIN, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
            assert proc.returncode == 0, f"{route} JS syntax failure: {proc.stderr.decode('utf-8', 'replace')}"

    app_js = REPO_ROOT / "guiai-lab" / "metrix" / "gui" / "app.js"
    assert subprocess.run([NODE_BIN, "--check", str(app_js)], capture_output=True, check=False).returncode == 0

    # Walk stateful ELIZA API lifecycle (remember -> stop -> honest_abstain -> export)
    st_rem, _, raw_rem = http_post(base, "/api/memory/remember", {"text": "Scenario 5 atelier note"})
    assert st_rem == 200
    assert json.loads(raw_rem.decode("utf-8"))["memory_snapshot"]["active_notes_count"] == 1

    st_stop, _, _ = http_post(base, "/api/stop", {})
    assert st_stop == 200
    st_blk, _, raw_blk = http_post(base, "/api/chat", {"message": "remember blocked"})
    assert st_blk == 200
    assert json.loads(raw_blk.decode("utf-8"))["mode"] == "honest_abstain"

    st_exp, _, raw_exp = http_get(base, "/api/export")
    assert st_exp == 200
    assert_constitutional_flags(json.loads(raw_exp.decode("utf-8")))

    # Elegance audit C=0, D=0
    gd = elegance_report["monorepo_summary"]["grade_distribution"]
    assert gd["C"] == 0 and gd["D"] == 0

    # Orbit SHA256SUMS.orbit verification
    sums_proc = subprocess.run(
        ["sha256sum", "-c", "evidence/renaissance-orbit/SHA256SUMS.orbit"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert sums_proc.returncode == 0, sums_proc.stdout

    # mobile/ cleanliness check (resilient to active Android Java edits, zero Phase-2/E2E artifacts)
    assert_mobile_clean_of_phase2_artifacts(REPO_ROOT)

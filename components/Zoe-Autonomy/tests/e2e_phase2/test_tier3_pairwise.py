"""Tier 3 E2E Tests: Cross-feature pairwise integration tests across F1-F10 (>=10 tests)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import numpy as np

from conftest import (
    NODE_BIN,
    REPO_ROOT,
    assert_constitutional_flags,
    http_get,
    http_post,
)


def test_t3_pair_f1_f10_elegance_orbit_modules_and_constitution(elegance_report):
    sums_lines = [
        ln.split(None, 1)[1].strip()
        for ln in (REPO_ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    audited = {r["file"]: r for r in elegance_report["all_modules_compact"]}
    py_sealed = [p for p in sums_lines if p.endswith(".py")]
    assert len(py_sealed) >= 40
    for rel in py_sealed:
        assert rel in audited, f"Sealed module {rel} missing from elegance audit"
        assert audited[rel]["grade"] in {"A", "B"}, f"Sealed module {rel} fell below Grade B: {audited[rel]}"
    assert_constitutional_flags(elegance_report)


def test_t3_pair_f2_f5_botanical_html_and_api_and_dorothy_overlay(eliza_server, dorothy_report):
    base = eliza_server["base_url"]
    st_html, _, raw_html = http_get(base, "/botanical")
    assert st_html == 200
    assert "clinical_action_authorized=False" in raw_html.decode("utf-8")

    st_c27, _, raw_c27 = http_get(base, "/api/kloster/botanical-atlas")
    st_c28, _, raw_c28 = http_get(base, "/api/kloster/pharmacophore-c28")
    assert st_c27 == 200 and st_c28 == 200
    c27 = json.loads(raw_c27.decode("utf-8"))
    c28 = json.loads(raw_c28.decode("utf-8"))
    assert_constitutional_flags(c27)
    assert_constitutional_flags(c28)

    overlay_winners = set(dorothy_report["c27_c28_filbin_sparing_overlay"]["c27_c28_compound_gate"]["compact_cns_selective_candidates"])
    assert "artemisinin" in overlay_winners
    assert "dordaviprone" in overlay_winners


def test_t3_pair_f2_f4_optics_html_and_api_and_dorothy_3plane(eliza_server, dorothy_report):
    base = eliza_server["base_url"]
    st_opt, _, raw_opt = http_get(base, "/optics")
    assert st_opt == 200
    html_txt = raw_opt.decode("utf-8")
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_txt, flags=re.DOTALL | re.IGNORECASE)
    assert scripts
    for js in scripts:
        proc = subprocess.run([NODE_BIN, "--check", "-"], input=js.encode("utf-8"), capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")

    st_t14, _, raw_t14 = http_get(base, "/api/kloster/theorem14")
    assert st_t14 == 200
    t14_doc = json.loads(raw_t14.decode("utf-8"))
    assert t14_doc["all_verified"] is True
    assert dorothy_report["theorem14_volumetric_optics"]["verified"] is True


def test_t3_pair_f2_f7_http_stem_route_and_digest_mobile_firewall(eliza_server_factory, tmp_path):
    from zoe_autonomy.l5_mobile_digestion import DIGESTION_CONTRACT, load_baseline_visual_atlas

    iso_root = tmp_path / "iso_digest"
    iso_root.mkdir()
    for name in ("guiai-lab", "components", "assets", "CONSTITUTION.md", "README.md"):
        src = REPO_ROOT / name
        if src.exists():
            (iso_root / name).symlink_to(src)
    (iso_root / "evidence").mkdir()

    srv = eliza_server_factory(iso_root, state_name="iso_digest_state")
    base = srv["base_url"]

    st_stem, _, raw_stem = http_post(
        base,
        "/api/stem/route",
        {
            "prompt": "Architect a multi-file distributed concurrency refactor with formal proof and teamwork",
            "files_count": 6,
            "multi_file": True,
        },
    )
    assert st_stem == 200
    stem_doc = json.loads(raw_stem.decode("utf-8"))
    assert stem_doc["selected_tier"] == "pro"
    assert stem_doc["quorum_arbitration"]["verdict"] == "COORDINATE_CONSENSUS"
    assert_constitutional_flags(stem_doc)

    # Hostile mobile bundle rejected 400; clean bundle accepted 200 and served at /api/digest/latest
    st_bad, _, _ = http_post(base, "/api/digest/mobile", {"device": "Pixel 7", "privacy_vault": ["secret"]})
    assert st_bad == 400

    atlas = load_baseline_visual_atlas(REPO_ROOT)[0]
    clean_bundle = {
        "contract": DIGESTION_CONTRACT,
        "device": "Pixel 7",
        "app_version": "0.9.5-beta",
        "privacy_firewall": {
            "safeconvert_excluded": True,
            "privacy_vault_excluded": True,
            "raw_photos_excluded": True,
            "chat_bodies_excluded": True,
        },
        "brain_notes": [{"client_id": "t3_note_1", "kind": "note", "text": "Pairwise optical bench note"}],
        "trip_sightings": [],
        "vision_prototypes": [
            {
                "label": "Workshop Brass Gear",
                "source": "user_confirmed",
                "patentRef": "",
                "dims": "",
                "count": 2,
                "updated": 1795320000000,
                "dHash": atlas["dHash"],
                "aspect": atlas["aspect"],
                "sym": atlas["sym"],
                "ortho": atlas["ortho"],
                "density": atlas["density"],
                "kw": "radial gear teeth",
                "summary": "",
                "hog": atlas["hog"],
                "radial": atlas["radial"],
            }
        ],
        "chat_telemetry": {"thread_count": 1, "message_count": 2, "avg_latency_ms": 20.0, "avg_a_tau": 2.0},
    }
    st_ok, _, raw_ok = http_post(base, "/api/digest/mobile", clean_bundle)
    assert st_ok == 200, raw_ok.decode("utf-8", "replace")
    dig = json.loads(raw_ok.decode("utf-8"))
    st_lat, _, raw_lat = http_get(base, "/api/digest/latest")
    assert st_lat == 200
    assert json.loads(raw_lat.decode("utf-8"))["report_sha256"] == dig["report_sha256"]


def test_t3_pair_f3_f7_zoe_os_mind_routes_ablation_and_entropy_mapper(zoe_mind_factory, tmp_path):
    from ablation.analyzers.entropy_mapper import EntropyMapper

    mind = zoe_mind_factory("mind_ablation")
    turn = mind.process_turn(
        "Analyze ELF binary entropy and reverse engineer opcode anomalies with ablation",
        offline_only=True,
    )
    assert turn["blocked"] is False
    assert turn["top_engine"] == "ablation"
    assert turn["stem_routing"]["estimated_cloud_tokens"] == 0

    rng = np.random.default_rng(77)
    bin_path = tmp_path / "payload_256b.bin"
    bin_path.write_bytes(rng.integers(0, 256, size=256, dtype=np.uint8).tobytes())
    em_res = EntropyMapper(str(bin_path), window_size=256, use_kloster=True).run()
    assert em_res.windows[0].cls == "ENCRYPTED"


def test_t3_pair_f3_f8_chat_theorem13_and_cern_bridge(zoe_chat_factory, cern_report):
    chat = zoe_chat_factory("chat_t13")
    keep, reply = chat.handle("theorem13")
    assert keep is True
    assert "I could not complete that safely" not in reply
    assert "do not have enough indexed evidence" not in reply
    assert "The 11-World Zoe Renaissance Orbit" not in reply
    assert cern_report["theorem13_multibunch_stopping"]["streams"]["signal_jet_shower"]["action"] == "DECIDE_SIGNAL"


def test_t3_pair_f4_f5_dorothy_3d_optics_and_filbin_sparing(dorothy_report):
    optics = dorothy_report["theorem14_volumetric_optics"]
    overlay = dorothy_report["c27_c28_filbin_sparing_overlay"]
    assert optics["verified"] is True
    assert overlay["verified"] is True
    assert len(optics["planes"]) == 3
    assert len(overlay["regions_overlay"]) == 12
    assert dorothy_report["constitution"]["clinical_action_authorized"] is False
    assert overlay["constitution"]["cure_claim"] is False


def test_t3_pair_f4_f8_playroom_optics_and_zoe_chat(zoe_chat_factory, playroom_report):
    chat = zoe_chat_factory("chat_playroom")
    keep, reply = chat.handle("playroom 2026")
    assert keep is True
    assert "Zoe Creative Playroom" in reply
    assert "sentience_claimed=False" in reply
    assert playroom_report["theorem14_optics_summary"]["mean_mtf_blur_loss"] > 0.0
    assert playroom_report["niches_filled"] >= 6


def test_t3_pair_f6_f4_f7_groove_mod_optics_and_zoe_os_mind(zoe_mind_factory):
    from guiai.gem.groove_forensics import (
        analyze_onset_stream,
        build_valid_protracker_mod_bytes,
        parse_mod_onsets_pure,
    )

    mind = zoe_mind_factory("mind_groove")
    turn = mind.process_turn(
        "Inspect helen groove polyrhythm and poincare return cloud from mod tempo",
        offline_only=True,
    )
    assert turn["blocked"] is False
    assert turn["top_engine"] == "helen"
    assert "theorem15_consensus" in turn

    onsets, step = parse_mod_onsets_pure(build_valid_protracker_mod_bytes(bpm=125, speed=6))
    prof = analyze_onset_stream("mod_pair", onsets, step)
    assert prof["poincare_quadrat_zk"]["poincare_regime"] == "RIGID_GRID_QUANTIZED"


def test_t3_pair_f7_f8_zoe_chat_collaboration_and_theorem15_proof(zoe_chat_factory, tmp_path):
    from zoe_autonomy.collaboration import CollaborationBridge, verify_collaboration_proof

    class _Gateway:
        def list(self):
            return [{"id": "kimi", "enabled": True, "owner": True, "executable_available": True}]

        def invoke(self, identifier, prompt, timeout=60):
            return {"id": identifier, "succeeded": True, "content": "Pairwise collaborator reply.", "audit_hash": "p3"}

    chat = zoe_chat_factory("chat_collab")
    chat.collaboration_bridge = CollaborationBridge(_Gateway())
    _, ask_reply = chat.handle("agent ask what is PALA?")
    assert "PALA" in ask_reply
    proof_path = tmp_path / "collab_pair.json"
    _, proof_reply = chat.handle(f"agent proof {proof_path}")
    assert "proof_sha256=" in proof_reply
    proof_doc = json.loads(proof_path.read_text(encoding="utf-8"))
    assert "theorem15_consensus" in proof_doc["operational_metacognition"]
    assert verify_collaboration_proof(proof_doc)["verified"] is True

    _, t15_reply = chat.handle("theorem15")
    assert "I could not complete that safely" not in t15_reply
    assert "do not have enough indexed evidence" not in t15_reply
    assert "The 11-World Zoe Renaissance Orbit" not in t15_reply


def test_t3_pair_f9_f2_docs_api_routes_match_live_eliza(eliza_server):
    from guiai.gem._eliza_routes import _GET_ROUTES, _POST_ROUTES

    base = eliza_server["base_url"]
    doc_text = (
        (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        + "\n"
        + (REPO_ROOT / "docs" / "PROOF-PACKET.md").read_text(encoding="utf-8")
    )
    documented_get_routes = set(re.findall(r"(?<![a-zA-Z0-9_])(/api/[a-z0-9_.-]+(?:/[a-z0-9_.-]+)*)", doc_text))
    for route in sorted(documented_get_routes):
        if route in _GET_ROUTES:
            st, _, _ = http_get(base, route)
            assert st == 200, f"Documented GET route {route} returned HTTP {st}"
        else:
            assert route in _POST_ROUTES, f"Documented route {route} missing from both _GET_ROUTES and _POST_ROUTES"

    for workbench in ("/orbit", "/botanical", "/optics", "/proof"):
        assert workbench in _GET_ROUTES
        st, _, _ = http_get(base, workbench)
        assert st == 200


def test_t3_pair_f8_f10_chat_memory_export_and_constitutional_flags(zoe_chat_factory, tmp_path):
    from zoe_autonomy.chat import verify_chat_export

    chat = zoe_chat_factory("chat_mem_pair")
    _, rem = chat.handle("remember Pairwise E2E glass-box note")
    assert "unverified" in rem
    _, rec = chat.handle("recall glass-box")
    assert "memory:" in rec and "coverage=" in rec

    exp_path = tmp_path / "pair_export.json"
    _, exp_msg = chat.handle(f"export {exp_path}")
    assert "automatic_transcript=False" in exp_msg
    doc = json.loads(exp_path.read_text(encoding="utf-8"))
    assert doc["automatic_transcript"] is False
    assert doc["external_monitor"] is False
    assert doc["external_notebook"] is False
    assert verify_chat_export(doc)["sources"] >= 1
    assert not (tmp_path / "chat_mem_pair" / "events.jsonl").exists()
    assert not (tmp_path / "chat_mem_pair" / "metacognition.json").exists()

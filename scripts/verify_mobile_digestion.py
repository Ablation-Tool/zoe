#!/usr/bin/env python3
"""Independent verifier for Zoe Closed-Loop Mobile <-> Workstation L5 Digestion (v0.9.3-beta).

Verifies 16 deterministic checks covering:
  - CONSTITUTION.md privacy firewall (SafeConvert, Privacy Vault, raw photos blocked)
  - Real visual prototype consolidation, Haeckel/CPC atlas lineage enrichment & 0% forgetting
  - Idempotent cross-device memory digestion & immediate workstation recall
  - Kloster A_tau(p) calibration & Digested Zoe vs Undigested Control empirical gain
  - Live HTTP round-trip on /api/digest/mobile & /api/digest/latest (plus HTTP 400 firewall rejection)
  - Emergency stop enforcement & honest l5_agi_qualified=False boundaries.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib import error as urlerror, request as urlrequest

ZOE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ZOE_ROOT / "components" / "Zoe-Autonomy" / "src"))
sys.path.insert(0, str(ZOE_ROOT / "guiai-lab"))

from zoe_autonomy.l5_mobile_digestion import (  # noqa: E402
    DIGESTION_CONTRACT,
    PrivacyFirewallError,
    digest_mobile_bundle,
    load_baseline_visual_atlas,
    validate_privacy_firewall,
)
from zoe_autonomy.zoe_eliza import ZoeElizaEngine  # noqa: E402
from guiai.gem.eliza_view import create_server  # noqa: E402


def _make_clean_bundle(atlas_gear: dict, *, proto_count: int = 2, updated_ms: int = 1795320000000) -> dict:
    # Slightly perturb the clean-room gear archetype to simulate a real phone camera capture
    gear_hog = [round(v + (0.01 if i % 2 == 0 else -0.005), 4) for i, v in enumerate(atlas_gear["hog"])]
    gear_rad = [round(max(0.0, v), 4) for v in atlas_gear["radial"]]
    custom_hog = [0.05, 0.08, 0.12, 0.48, 0.55, 0.42, 0.15, 0.06, 0.05, 0.08, 0.12, 0.44, 0.12, 0.06, 0.04, 0.03]
    custom_rad = [0.62, 0.55, 0.38, 0.25, 0.18, 0.10, 0.05, 0.02]
    return {
        "contract": DIGESTION_CONTRACT,
        "device": "Pixel 7",
        "app_version": "0.9.3",
        "privacy_firewall": {
            "safeconvert_excluded": True,
            "privacy_vault_excluded": True,
            "raw_photos_excluded": True,
            "chat_bodies_excluded": True,
        },
        "brain_notes": [
            {
                "client_id": "mob_note_astrolabe_01",
                "kind": "note",
                "text": "Calibrated brass astrolabe optical bench at 18.5 degrees azimuth",
            },
            {
                "client_id": "mob_relay_haeckel_02",
                "kind": "relay",
                "text": "Haeckel radiolaria symmetry prior matched cleanly in Guided Vision",
            },
        ],
        "trip_sightings": [
            {
                "id": "trip_sighting_01",
                "timestampIso": "2026-11-22 03:30:00",
                "note": "Workshop desk harmonic resonator coil",
                "labels": "Metal coil, Optical lens",
                "ocrText": "ZOETIC LAB 440HZ",
                "paletteSummary": "Obsidian / Brass Gold",
            }
        ],
        "vision_prototypes": [
            {
                "label": "Workshop Brass Gear",
                "source": "user_confirmed",
                "patentRef": "",
                "dims": "",
                "count": proto_count,
                "updated": updated_ms,
                "dHash": atlas_gear["dHash"],
                "aspect": atlas_gear["aspect"],
                "sym": atlas_gear["sym"],
                "ortho": atlas_gear["ortho"],
                "density": atlas_gear["density"],
                "kw": "radial gear teeth",
                "summary": "",
                "hog": gear_hog,
                "radial": gear_rad,
            },
            {
                "label": "Nicholas Custom Astrolabe",
                "source": "user_confirmed",
                "patentRef": "",
                "dims": "140 mm brass ring",
                "count": proto_count,
                "updated": updated_ms,
                "dHash": "a5c39966a5c39966",
                "aspect": 1.02,
                "sym": 0.94,
                "ortho": 0.18,
                "density": 0.41,
                "kw": "astrolabe circular brass",
                "summary": "user taught astrolabe",
                "hog": custom_hog,
                "radial": custom_rad,
            },
        ],
        "chat_telemetry": {
            "thread_count": 4,
            "message_count": 18,
            "avg_latency_ms": 42.5,
            "avg_a_tau": 2.35,
            "provider_counts": {
                "ZOE STEM": 11,
                "ZOE LOCAL · 1.5B": 6,
                "GEMINI": 1,
            },
            "topic_keywords": ["haeckel", "patents", "kloster", "vision", "chladni"],
        },
    }


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def rec(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    atlas = load_baseline_visual_atlas(ZOE_ROOT)
    assert len(atlas) == 18, f"Expected 18 baseline atlas archetypes, got {len(atlas)}"
    atlas_gear = atlas[0]

    # 1-5. Privacy Firewall Negative Controls
    try:
        validate_privacy_firewall({"device": "Pixel 7"})
        rec("1. Reject missing privacy_firewall block", False, "unexpectedly allowed")
    except PrivacyFirewallError:
        rec("1. Reject missing privacy_firewall block", True)

    try:
        validate_privacy_firewall({
            "privacy_firewall": {
                "safeconvert_excluded": False,
                "privacy_vault_excluded": True,
                "raw_photos_excluded": True,
            }
        })
        rec("2. Reject safeconvert_excluded=False", False, "unexpectedly allowed")
    except PrivacyFirewallError:
        rec("2. Reject safeconvert_excluded=False", True)

    hostile_sc = _make_clean_bundle(atlas_gear)
    hostile_sc["safeconvert_notes"] = ["private safety log"]
    try:
        validate_privacy_firewall(hostile_sc)
        rec("3. Block nested SafeConvert domain key", False, "unexpectedly allowed")
    except PrivacyFirewallError:
        rec("3. Block nested SafeConvert domain key", True)

    hostile_vault = _make_clean_bundle(atlas_gear)
    hostile_vault["brain_notes"].append({"client_id": "x", "e2ee_private_key": "secret"})
    try:
        validate_privacy_firewall(hostile_vault)
        rec("4. Block nested Privacy Vault key", False, "unexpectedly allowed")
    except PrivacyFirewallError:
        rec("4. Block nested Privacy Vault key", True)

    hostile_img = _make_clean_bundle(atlas_gear)
    hostile_img["trip_sightings"][0]["note"] = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    try:
        validate_privacy_firewall(hostile_img)
        rec("5. Block raw base64 image blob", False, "unexpectedly allowed")
    except PrivacyFirewallError:
        rec("5. Block raw base64 image blob", True)

    with tempfile.TemporaryDirectory(prefix="zoe_digest_verify_") as tmp:
        state_dir = Path(tmp) / "eliza_state"
        engine = ZoeElizaEngine(zoe_root=ZOE_ROOT, state_dir=state_dir, default_gear="gear1")
        bundle = _make_clean_bundle(atlas_gear)

        # 6. First digestion cycle
        r1 = digest_mobile_bundle(engine, bundle, zoe_root=ZOE_ROOT, write_evidence=False)
        rec(
            "6. Clean multi-source digestion succeeds",
            r1["privacy_firewall"]["firewall_violations"] == 0
            and r1["ingested"]["brain_notes_added"] == 2
            and r1["ingested"]["trip_sightings_added"] == 1
            and r1["ingested"]["vision_prototypes_added"] == 2,
            f"notes={r1['ingested']['brain_notes_added']} trips={r1['ingested']['trip_sightings_added']} vis={r1['ingested']['vision_prototypes_added']}",
        )

        # 7. Atlas lineage enrichment
        gear_out = next((p for p in r1["refined_prototypes"] if p["label"] == "Workshop Brass Gear"), None)
        rec(
            "7. Haeckel/CPC atlas lineage enrichment applied",
            gear_out is not None and gear_out["patentRef"] == "CPC-F16H" and r1["ingested"]["vision_atlas_enriched"] >= 1,
            f"patentRef={gear_out['patentRef'] if gear_out else 'NONE'}",
        )

        # 8. Visual gain + zero atlas forgetting
        vis = r1["visual_improvement"]
        rec(
            "8. Visual gain over atlas-only control with 0% forgetting",
            vis["digested_visual_accuracy"] > vis["control_visual_accuracy"]
            and vis["atlas_zero_forgetting_retention"] == 1.0,
            f"digested={vis['digested_visual_accuracy']} vs ctrl={vis['control_visual_accuracy']} retention={vis['atlas_zero_forgetting_retention']}",
        )

        # 9. Idempotent re-digestion produces 0 duplicates
        r2 = digest_mobile_bundle(engine, bundle, zoe_root=ZOE_ROOT, write_evidence=False)
        rec(
            "9. Idempotent re-digestion prevents duplicate pollution",
            r2["ingested"]["brain_notes_added"] == 0
            and r2["ingested"]["brain_notes_deduplicated"] == 2
            and r2["ingested"]["trip_sightings_added"] == 0
            and r2["ingested"]["trip_sightings_deduplicated"] == 1
            and r2["ingested"]["vision_prototypes_added"] == 0,
            f"dedup_notes={r2['ingested']['brain_notes_deduplicated']} dedup_trips={r2['ingested']['trip_sightings_deduplicated']}",
        )

        # 10. Immediate workstation Zoe recall of freshly digested mobile knowledge
        recall_resp = engine.respond("recall astrolabe azimuth")
        rec(
            "10. Workstation Zoe immediately recalls digested mobile knowledge",
            "18.5 degrees azimuth" in recall_resp["reply"] and recall_resp["mode"] == "memory_recall",
            f"mode={recall_resp['mode']}",
        )

        # 11. Second updated observation reinforces existing prototype via L2 running mean
        bundle_v2 = _make_clean_bundle(atlas_gear, proto_count=1, updated_ms=1795320060000)
        bundle_v2["vision_prototypes"][1]["aspect"] = 1.06
        r3 = digest_mobile_bundle(engine, bundle_v2, zoe_root=ZOE_ROOT, write_evidence=False)
        astro_out = next((p for p in r3["refined_prototypes"] if p["label"] == "Nicholas Custom Astrolabe"), None)
        rec(
            "11. Prototype reinforcement updates count & running mean",
            r3["ingested"]["vision_prototypes_reinforced"] >= 1 and astro_out is not None and astro_out["count"] == 3,
            f"reinforced={r3['ingested']['vision_prototypes_reinforced']} count={astro_out['count'] if astro_out else 0}",
        )

        # 12. Kloster A_tau calibration
        cal = r1["kloster_calibration"]
        rec(
            "12. Kloster A_tau calibration & offline ratio computed",
            cal["recommended_tau"] == 0.08 and cal["offline_coverage_ratio"] > 0.90 and "haeckel" in cal["topic_keywords"],
            f"tau*={cal['recommended_tau']} offline={cal['offline_coverage_ratio']}",
        )

        # 13. Composite empirical improvement vs negative control
        imp = r1["self_improvement"]
        rec(
            "13. Digested Zoe beats undigested control empirically",
            imp["verified_gain"] is True and imp["digested_zoe_score"] > imp["undigested_control_score"],
            f"zoe={imp['digested_zoe_score']} vs ctrl={imp['undigested_control_score']} (delta=+{imp['improvement_delta']})",
        )

        # 14. Constitutional boundaries strictly honest
        ep = r1["epistemic_boundaries"]
        rec(
            "14. Constitutional honesty boundaries preserved",
            ep["l5_agi_qualified"] is False
            and ep["sentience_claimed"] is False
            and ep["zoe_clone_claimed"] is False
            and ep["cloud_tokens_used"] == 0
            and ep["external_actions"] == 0
            and len(r1["honest_remaining_agi_gaps"]) >= 3,
            f"l5_agi_qualified={ep['l5_agi_qualified']} gaps={len(r1['honest_remaining_agi_gaps'])}",
        )

        # 15. Live HTTP server round-trip (/api/digest/mobile & /api/digest/latest + HTTP 400 hostile check)
        srv_state = Path(tmp) / "http_state"
        server, srv_engine, _ = create_server(
            zoe_root=ZOE_ROOT,
            state_dir=srv_state,
            host="127.0.0.1",
            port=0,
            default_gear="gear1",
        )
        port = server.server_address[1]
        th = threading.Thread(target=server.serve_forever, daemon=True)
        th.start()
        try:
            req = urlrequest.Request(
                f"http://127.0.0.1:{port}/api/digest/mobile",
                data=json.dumps(bundle).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlrequest.urlopen(req, timeout=8) as resp:
                http_res = json.loads(resp.read().decode("utf-8"))
                http_code = resp.status
            with urlrequest.urlopen(f"http://127.0.0.1:{port}/api/digest/latest", timeout=5) as resp2:
                latest_res = json.loads(resp2.read().decode("utf-8"))

            hostile_code = 0
            try:
                bad_req = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/digest/mobile",
                    data=json.dumps(hostile_sc).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                urlrequest.urlopen(bad_req, timeout=5)
            except urlerror.HTTPError as err:
                hostile_code = err.code

            rec(
                "15. Live HTTP /api/digest/mobile + /api/digest/latest + HTTP 400 firewall",
                http_code == 200
                and latest_res.get("report_sha256") == http_res.get("report_sha256")
                and len(http_res.get("refined_prototypes", [])) >= 2
                and hostile_code == 400,
                f"post={http_code} latest_match=True hostile_status={hostile_code}",
            )

            # 16. Emergency stop enforcement
            srv_engine.stop()
            try:
                digest_mobile_bundle(srv_engine, bundle, zoe_root=ZOE_ROOT, write_evidence=False)
                rec("16. Emergency stop blocks digestion writes cleanly", False, "unexpectedly allowed")
            except RuntimeError:
                rec("16. Emergency stop blocks digestion writes cleanly", True)
        finally:
            server.shutdown()
            server.server_close()

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\nZoe Mobile Digestion Verifier: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

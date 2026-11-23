"""Tier 1 E2E Tests: Happy-path functional coverage for Features F1-F10 (>=5 tests per feature)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import numpy as np
import pytest

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


# ---------------------------------------------------------------------------
# F1: Code Elegance Audit (C=0, D=0), JS Syntax & Helper Consolidation
# ---------------------------------------------------------------------------


def test_f1_monorepo_elegance_zero_grade_c_and_d(elegance_report):
    summary = elegance_report["monorepo_summary"]
    assert elegance_report["contract"] == "zoe-kloster-mccabe-elegance/v1"
    assert summary["files_scanned"] >= 280
    assert summary["parse_errors"] == 0
    assert elegance_report["all_verified"] is True
    assert summary["grade_distribution"]["D"] == 0
    assert summary["grade_distribution"]["C"] == 0


def test_f1_legacy_grade_c_modules_and_dispatchers_are_grade_a_or_b(elegance_report):
    by_file = {row["file"]: row for row in elegance_report["all_modules_compact"]}
    target_modules = (
        "scripts/render_l4_improvement_figure.py",
        "scripts/render_l5_core_figure.py",
        "scripts/render_l5_phase6_figure.py",
        "scripts/render_l3_research_figure.py",
        "scripts/render_l5_phase2_figure.py",
        "scripts/render_zoe_voice_figure.py",
        "components/Zoe-Autonomy/src/zoe_autonomy/l5_phase4_stem_routing.py",
        "components/Zoe-Autonomy/src/zoe_autonomy/cli.py",
        "guiai-lab/guiai/gem/cli.py",
        "guiai-lab/guiai/gem/eliza_view.py",
        "guiai-lab/guiai/gem/unified_cli.py",
        "guiai-lab/guiai/gem/_eliza_routes.py",
    )
    for rel_path in target_modules:
        assert rel_path in by_file, f"Missing audited module: {rel_path}"
        row = by_file[rel_path]
        assert row["grade"] in {"A", "B"}, (
            f"Expected {rel_path} to be Grade A/B, got Grade {row['grade']} (MI={row['mi']}, max_cc={row['max_cc']})"
        )
        assert row["mi"] >= 40.0


def test_f1_node_check_all_inline_scripts_and_app_js(eliza_server):
    assert Path(NODE_BIN).is_file(), f"node binary not found at {NODE_BIN}"
    base = eliza_server["base_url"]

    app_js = REPO_ROOT / "guiai-lab" / "metrix" / "gui" / "app.js"
    assert app_js.is_file()
    proc_app = subprocess.run([NODE_BIN, "--check", str(app_js)], capture_output=True, text=True, check=False)
    assert proc_app.returncode == 0, f"app.js syntax check failed: {proc_app.stderr}"

    for route in ("/", "/proof", "/botanical", "/optics"):
        status, _, body = http_get(base, route)
        assert status == 200, route
        html_text = body.decode("utf-8")
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE)
        assert scripts, f"Expected inline <script> block on {route}"
        for idx, js_code in enumerate(scripts):
            proc = subprocess.run(
                [NODE_BIN, "--check", "-"],
                input=js_code.encode("utf-8"),
                capture_output=True,
                check=False,
            )
            assert proc.returncode == 0, (
                f"{route} <script> #{idx} failed node --check: {proc.stderr.decode('utf-8', 'replace')}"
            )


def test_f1_consolidated_sha256_and_atomic_json_parity(tmp_path):
    from zoe_autonomy._utils import (
        atomic_write_json,
        sha256_bytes,
        sha256_file,
        sha256_json_ascii,
        sha256_json_utf8,
    )

    sample = {"title": "Zoe × Kloster", "tau": 0.08, "values": [1, 2, 3]}
    d_utf8 = sha256_json_utf8(sample)
    d_ascii = sha256_json_ascii(sample)
    assert len(d_utf8) == 64 and len(d_ascii) == 64
    assert d_utf8 != d_ascii  # Non-ASCII '×' preserves exact UTF-8 vs ASCII escaping semantics

    out_path = atomic_write_json(tmp_path / "nested" / "atomic.json", sample)
    assert out_path.is_file()
    assert sha256_file(out_path) == sha256_bytes(out_path.read_bytes())
    assert json.loads(out_path.read_text(encoding="utf-8")) == sample


def test_f1_consolidated_auroc_tie_semantics():
    from zoe_autonomy._metrics import auroc_argsort, auroc_tie_aware

    labels = np.array([0, 0, 1, 1], dtype=np.int64)
    assert auroc_tie_aware(labels, [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)
    assert auroc_tie_aware(labels, [0.9, 0.8, 0.2, 0.1]) == pytest.approx(0.0)
    # Exact tie across all predictions must return 0.5 under symmetric tie-averaging
    assert auroc_tie_aware(labels, [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.5)
    assert auroc_argsort(labels, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    # Alternating tied labels verify raw argsort semantics (0.75) vs symmetric tie-averaging (0.5)
    tied_labels = np.array([0, 1, 0, 1], dtype=np.int64)
    tied_scores = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float64)
    assert auroc_argsort(tied_labels, tied_scores) == pytest.approx(0.75)
    assert auroc_tie_aware(tied_labels, tied_scores) == pytest.approx(0.5)


def test_f1_resolve_zoe_root_contract(monkeypatch, tmp_path):
    from guiai.gem._root import resolve_zoe_root

    assert resolve_zoe_root(tmp_path) == tmp_path.resolve()
    monkeypatch.setenv("ZOE_ROOT", str(REPO_ROOT))
    assert resolve_zoe_root() == REPO_ROOT.resolve()


# ---------------------------------------------------------------------------
# F2: eliza_view.py Live HTTP Routes & Dynamic /orbit Pills
# ---------------------------------------------------------------------------


def test_f2_eliza_root_index_and_avatar_served(eliza_server):
    base = eliza_server["base_url"]
    st_root, hdr_root, body_root = http_get(base, "/")
    st_idx, _, body_idx = http_get(base, "/index.html")
    assert st_root == 200 and st_idx == 200
    assert "text/html" in hdr_root.get("content-type", "")
    assert body_root == body_idx
    assert "Zoe-ELIZA" in body_root.decode("utf-8")

    st_av, hdr_av, body_av = http_get(base, "/avatar.png")
    assert st_av == 200
    assert hdr_av.get("content-type") == "image/png"
    assert body_av.startswith(b"\x89PNG\r\n\x1a\n")


def test_f2_orbit_dynamic_pills_match_master_and_sha256sums(eliza_server):
    base = eliza_server["base_url"]
    sums_path = REPO_ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit"
    expected_sealed = sum(
        1 for ln in sums_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )

    st_m, _, raw_m = http_get(base, "/api/orbit/master")
    assert st_m == 200
    master = json.loads(raw_m.decode("utf-8"))
    assert_constitutional_flags(master)

    st_o, hdr_o, raw_o = http_get(base, "/orbit")
    assert st_o == 200
    assert "text/html" in hdr_o.get("content-type", "")
    orbit_html = raw_o.decode("utf-8")
    assert f"{master['worlds_verified']}/{master['worlds_total']} Worlds Verified" in orbit_html
    assert f"{master['cross_pollination_edges_count']} Cross-Pollination Edges" in orbit_html
    assert f"Theorems 1-{master['theorems_proved_sympy']} SymPy Proved" in orbit_html
    assert f"{expected_sealed}/{expected_sealed} SHA256SUMS.orbit Sealed" in orbit_html
    assert f"{master['constitution']['cloud_tokens_used']} Cloud Tokens" in orbit_html


def test_f2_interactive_workbenches_botanical_optics_proof(eliza_server):
    base = eliza_server["base_url"]
    for route, markers in (
        ("/botanical", ("0 Cloud Tokens", "clinical_action_authorized=False")),
        ("/optics", ("0 Cloud Tokens",)),
        ("/proof", ("0 Cloud Tokens", "sentience_claimed=False", "clinical_action_authorized=False")),
    ):
        st, hdr, raw = http_get(base, route)
        assert st == 200, route
        assert "text/html" in hdr.get("content-type", "")
        assert hdr.get("cache-control") == "no-store"
        html_txt = raw.decode("utf-8")
        for marker in markers:
            assert marker in html_txt, f"{route} missing marker {marker!r}"


def test_f2_api_status_mind_and_kloster_theorems(eliza_server):
    base = eliza_server["base_url"]
    json_routes = (
        "/api/status",
        "/api/os/mind",
        "/api/kloster/theorem13",
        "/api/kloster/theorem14",
        "/api/kloster/theorem15",
        "/api/kloster/botanical-atlas",
        "/api/kloster/pharmacophore-c28",
    )
    for route in json_routes:
        st, hdr, raw = http_get(base, route)
        assert st == 200, route
        assert "application/json" in hdr.get("content-type", "")
        doc = json.loads(raw.decode("utf-8"))
        assert isinstance(doc, dict)
        assert doc.get("available") is not False, f"Expected real evidence at {route}"
        assert_constitutional_flags(doc)


def test_f2_l5_phase3_to_6_json_and_gem_svg_routes(eliza_server):
    base = eliza_server["base_url"]
    for phase in (3, 4, 5, 6):
        st_j, hdr_j, raw_j = http_get(base, f"/api/l5/phase{phase}")
        assert st_j == 200
        assert "application/json" in hdr_j.get("content-type", "")
        doc = json.loads(raw_j.decode("utf-8"))
        assert_constitutional_flags(doc)

        st_s, hdr_s, raw_s = http_get(base, f"/api/l5/phase{phase}/gem.svg")
        assert st_s == 200
        assert "image/svg+xml" in hdr_s.get("content-type", "")
        svg = raw_s.decode("utf-8")
        assert "<svg" in svg and "</svg>" in svg


def test_f2_post_api_chat_and_stem_route(eliza_server):
    base = eliza_server["base_url"]
    st_c, _, raw_c = http_post(base, "/api/chat", {"message": "Hello Zoe!"})
    assert st_c == 200
    chat_doc = json.loads(raw_c.decode("utf-8"))
    assert chat_doc["mode"] == "eliza_reflect"
    assert_constitutional_flags(chat_doc)

    st_s, _, raw_s = http_post(
        base,
        "/api/stem/route",
        {"prompt": "Private local summary note", "privacy_sensitive": True, "offline_only": True},
    )
    assert st_s == 200
    stem_doc = json.loads(raw_s.decode("utf-8"))
    assert stem_doc["selected_tier"] in {"gear1_eliza", "local_qwen"}
    assert_constitutional_flags(stem_doc)


# ---------------------------------------------------------------------------
# F3: Bridge 1 — Theorem 13 -> CERN Trigger & Ablation EntropyMapper
# ---------------------------------------------------------------------------


def test_f3_kloster_stopping_controller_and_unbiased_chi2(theorem13_report):
    from guiai.gem.kloster_stopping_law import (
        KlosterSequentialStoppingController,
        kloster_unbiased_chi2_stats,
    )

    assert theorem13_report["all_verified"] is True
    assert theorem13_report["sympy_proofs"]["all_sympy_proofs_exact"] is True
    assert_constitutional_flags(theorem13_report)

    # Peaked signal stops early with DECIDE_SIGNAL
    ctrl_sig = KlosterSequentialStoppingController(n_bins=16, delta=0.005, max_samples=512)
    verdict = ctrl_sig.observe_batch([3] * 24 + [0, 1, 2, 4])
    assert verdict["action"] == "DECIDE_SIGNAL"
    assert verdict["z_kloster"] >= verdict["z_threshold"]

    # Small batch stays in GATHER_MORE
    ctrl_small = KlosterSequentialStoppingController(n_bins=64, delta=0.005, max_samples=512)
    small_v = ctrl_small.observe_batch([0, 1, 2, 3, 4, 5])
    assert small_v["action"] == "GATHER_MORE"

    # Unbiased chi2 stats match positive excess for concentrated bins
    stats_conc = kloster_unbiased_chi2_stats([12, 12, 0, 0, 0, 0])
    assert stats_conc["m2_unbiased"] > 1.0 / 6.0
    assert stats_conc["z_kloster"] > 2.0


def test_f3_cern_multibunch_vcd_stopping_suite(cern_report):
    assert cern_report["all_verified"] is True
    assert cern_report["checks"]["theorem13_multibunch_stopping_signal_vs_pileup_hotspike"] is True
    assert_constitutional_flags(cern_report)

    thm13 = cern_report["theorem13_multibunch_stopping"]
    assert cern_report["vcd_forensics"]["theorem13_stopping"] == thm13
    streams = thm13["streams"]
    assert streams["signal_jet_shower"]["action"] == "DECIDE_SIGNAL"
    assert streams["signal_jet_shower"]["budget_fraction_used"] <= 0.50
    assert streams["signal_undersampled_1bunch"]["action"] == "GATHER_MORE"
    assert streams["bg_diffuse_pileup"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert streams["bg_single_hotspike"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert streams["bg_sticky_hotspike"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"


def test_f3_entropy_mapper_small_slice_monorepo(tmp_path):
    from ablation.analyzers.entropy_mapper import EntropyMapper

    rng = np.random.default_rng(20260713)
    enc_slice = rng.integers(0, 256, size=256, dtype=np.uint8).tobytes()
    sparse_slice = b"\x00" * 512
    blob = sparse_slice + enc_slice + sparse_slice
    bin_path = tmp_path / "firmware_small_slice.bin"
    bin_path.write_bytes(blob)

    mapper = EntropyMapper(str(bin_path), window_size=256, use_kloster=True)
    res = mapper.run()
    assert res.kloster_stopping_summary["backend"] == "guiai"
    assert res.kloster_stopping_summary["small_slice_mode"] is True
    # The middle 256-byte encrypted slice at offset 512 must be classified ENCRYPTED
    enc_windows = [w for w in res.windows if w.offset == 512]
    assert len(enc_windows) == 1
    assert enc_windows[0].cls == "ENCRYPTED"

    # Separate stream stopping check on a 384-byte encrypted payload
    enc_only = tmp_path / "enc_only.bin"
    enc_only.write_bytes(rng.integers(0, 256, size=384, dtype=np.uint8).tobytes())
    stop_res = EntropyMapper(str(enc_only), window_size=256, use_kloster=True).scan_kloster_stopping()
    assert stop_res["backend"] == "guiai"
    assert stop_res["action"] in {"ABSTAIN_INSUFFICIENT_EVIDENCE", "GATHER_MORE"}


def test_f3_entropy_mapper_standalone_ablation_subprocess(tmp_path):
    rng = np.random.default_rng(1337)
    enc_path = tmp_path / "enc_192b.bin"
    enc_path.write_bytes(rng.integers(0, 256, size=192, dtype=np.uint8).tobytes())

    script = (
        "import json, sys; "
        "sys.modules['guiai'] = None; "
        "sys.modules['guiai.gem'] = None; "
        "sys.modules['guiai.gem.kloster_stopping_law'] = None; "
        "from ablation.analyzers.entropy_mapper import EntropyMapper, _HAS_GUIAI_KLOSTER; "
        "assert _HAS_GUIAI_KLOSTER is False; "
        "m = EntropyMapper(sys.argv[1], window_size=192, use_kloster=True); "
        "r = m.run(); "
        "s = m.scan_kloster_stopping(); "
        "print(json.dumps({'backend': r.kloster_stopping_summary['backend'], "
        "'cls': r.windows[0].cls, 'stop_backend': s['backend'], 'stop_action': s['action']}))"
    )
    proc = subprocess.run(
        [PYTHON_BIN, "-c", script, str(enc_path)],
        cwd=str(REPO_ROOT),
        env=standalone_ablation_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip())
    assert out["backend"] == "standalone_fallback"
    assert out["stop_backend"] == "standalone_fallback"
    assert out["cls"] == "ENCRYPTED"


def test_f3_ablation_cli_analyze_entropy_output(tmp_path):
    rng = np.random.default_rng(42)
    mixed = b"\x00" * 512 + bytes([i % 64 for i in range(512)]) + rng.integers(0, 256, size=512, dtype=np.uint8).tobytes()
    bin_path = tmp_path / "mixed.bin"
    bin_path.write_bytes(mixed)

    proc = subprocess.run(
        [PYTHON_BIN, "-m", "ablation.cli", "analyze", str(bin_path), "--entropy"],
        cwd=str(REPO_ROOT),
        env=standalone_ablation_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Entropy regions (" in proc.stdout
    assert "H=" in proc.stdout
    assert any(tag in proc.stdout for tag in ("CODE/DATA", "SPARSE", "ENCRYPTED"))


# ---------------------------------------------------------------------------
# F4: Bridge 2 — Theorem 14 -> Dorothy 3D & Creative Playroom
# ---------------------------------------------------------------------------


def test_f4_kloster_mtf_blur_loss_parseval_and_monotonicity():
    from guiai.gem.kloster_spatial_optical_law import (
        _quadrat_zk,
        kloster_mtf_blur_loss,
        kloster_spatial_m2,
    )

    yy, xx = np.meshgrid(np.arange(24), np.arange(32), indexing="ij")
    field = np.exp(-((xx - 12) ** 2 + (yy - 10) ** 2) / 3.0) + 0.4 * ((xx + yy) % 4 == 0)
    assert kloster_spatial_m2(field) > 0.0

    m_lo = kloster_mtf_blur_loss(field, psf_sigma=0.8)
    m_mid = kloster_mtf_blur_loss(field, psf_sigma=1.6)
    m_hi = kloster_mtf_blur_loss(field, psf_sigma=3.0)
    assert m_mid["delta_opt"] > 0.0
    assert m_mid["m2_blurred"] < m_mid["m2_sharp"]
    assert m_mid["parseval_error"] < 1e-12
    assert m_lo["m2_blurred"] > m_mid["m2_blurred"] > m_hi["m2_blurred"]

    # Clustered point cloud produces large positive Z_K
    rng = np.random.default_rng(7)
    clustered = np.clip(0.25 + 0.03 * rng.normal(size=(120, 2)), 0.01, 0.99)
    zk_res = _quadrat_zk(clustered, grid_n=8)
    assert zk_res["z_kloster"] > 10.0


def test_f4_dorothy_3plane_volumetric_optics(dorothy_report):
    assert dorothy_report["all_verified"] is True
    assert dorothy_report["checks"]["theorem14_3plane_mtf_and_quadrat_zk_verified"] is True
    optics = dorothy_report["theorem14_volumetric_optics"]
    assert optics["verified"] is True
    for plane in ("coronal_yz", "sagittal_xy", "horizontal_xz"):
        row = optics["planes"][plane]
        assert row["delta_opt"] > 0.0
        assert row["m2_blurred"] < row["m2_spatial"]
        assert row["parseval_error"] < 1e-12
        assert row["z_kloster"] > 10.0
    assert abs(optics["csr_negative_control"]["z_kloster"]) < 2.5


def test_f4_creative_playroom_artifact_descriptors_theorem14(playroom_report):
    assert playroom_report["niches_filled"] >= 6
    assert playroom_report["mean_curiosity_fitness"] > 0.0
    assert playroom_report["external_actions"] == 0
    assert_constitutional_flags(playroom_report)
    assert "theorem14_optics_summary" in playroom_report

    for elite in playroom_report["elites"]:
        d = elite["descriptors"]
        assert d["spatial_m2"] > 0.0
        assert d["mtf_blur_loss"] > 0.0
        assert 0.0 < d["mtf_sharpness"] <= 1.0
        assert d["spatial_regime"] in {"clustered", "crystal", "csr_noise"}


def test_f4_playroom_scene_vdi_and_constitutional_invariants():
    from guiai.gem.creative_playroom import playroom_scene
    from guiai.gem.geometry import verify
    from guiai.gem.runner import verify_vdi

    scene, scene_rep = playroom_scene(seed=2026)
    assert verify(scene).passed is True
    assert verify_vdi(scene).passed is True
    assert scene_rep["executed"] is False
    assert_constitutional_flags(scene_rep)


def test_f4_theorem14_suite_all_verified(theorem14_report):
    assert theorem14_report["all_verified"] is True
    assert_constitutional_flags(theorem14_report)
    assert theorem14_report["sympy_proofs"]["all_proved"] is True


# ---------------------------------------------------------------------------
# F5: Bridge 3 — C27/C28 -> Dorothy 3D Preclinical Overlay
# ---------------------------------------------------------------------------


def test_f5_dorothy_filbin_12region_overlay_partition(dorothy_report):
    assert dorothy_report["checks"]["c27_c28_filbin_12region_sparing_overlay_verified"] is True
    overlay = dorothy_report["c27_c28_filbin_sparing_overlay"]
    assert overlay["verified"] is True
    regions = overlay["regions_overlay"]
    assert len(regions) == 12
    midline = {r["acronym"] for r in regions if not r["must_spare"]}
    healthy = {r["acronym"] for r in regions if r["must_spare"]}
    assert midline == {"P", "MY", "MB", "TH", "HY"}
    assert healthy == {"Isocortex", "HPF", "OLF", "CB", "STR", "PAL", "CTXsp"}


def test_f5_dorothy_filbin_6_gene_modules_present(dorothy_report):
    overlay = dorothy_report["c27_c28_filbin_sparing_overlay"]
    expected_modules = ["OPC_STEM", "MMP14_GATE", "BBB_EFFLUX", "NSC_GUARD", "NEURON_GUARD", "GLIA_GUARD"]
    assert overlay["gene_modules"] == expected_modules
    for row in overlay["regions_overlay"]:
        assert set(row["modules"].keys()) == set(expected_modules)
    summary = overlay["summary"]
    assert summary["midline_target_count"] == 5
    assert summary["healthy_guardrail_count"] == 7
    assert summary["kloster_m2_tumor_concentration"] > (1.0 / 12.0)


def test_f5_dorothy_c27_c28_compound_gate_selectivity(dorothy_report):
    gate = dorothy_report["c27_c28_filbin_sparing_overlay"]["c27_c28_compound_gate"]
    assert gate["molecules_evaluated"] == 36
    winners = gate["compact_cns_selective_candidates"]
    assert "artemisinin" in winners
    assert "dordaviprone" in winners
    for blocked in ("curcumin", "berberine", "crocin", "paclitaxel"):
        assert blocked not in winners


def test_f5_botanical_atlas_c27_suite_and_theorem13_stopping(botanical_report):
    assert botanical_report["all_verified"] is True
    assert botanical_report["molecules_count"] == 36
    assert botanical_report["fips203_slots_packed"] == 216
    assert botanical_report["fips203_216slot_3site_homomorphic_exact"] is True
    thm13 = botanical_report["theorem13_filbin_stopping"]
    assert thm13["artemisinin_selective_stop"]["action"] == "DECIDE_SIGNAL"
    assert thm13["dordaviprone_benchmark_stop"]["action"] == "DECIDE_SIGNAL"
    assert thm13["curcumin_pains_abstain"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert thm13["colchicine_raw_toxin_abstain"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"
    assert_constitutional_flags(botanical_report)


def test_f5_c28_pharmacophore_spatial_and_preclinical_flags(dorothy_report, c28_report):
    assert c28_report["all_verified"] is True
    assert c28_report["contract"] == "zoe-pharmacophore-spatial-c28/v1"
    for doc in (dorothy_report, dorothy_report["c27_c28_filbin_sparing_overlay"], c28_report):
        assert_constitutional_flags(doc)
        const = doc["constitution"]
        assert const["clinical_action_authorized"] is False
        assert const["cure_claim"] is False
        assert const["patient_specific_recommendation"] is False


# ---------------------------------------------------------------------------
# F6: Bridge 4 — Theorems 13 + 14 -> Groove Forensics
# ---------------------------------------------------------------------------


def test_f6_groove_analyze_onset_stream_pocket_vs_rigid_vs_poisson():
    from guiai.gem.groove_forensics import analyze_onset_stream

    rng = np.random.default_rng(20261111)
    step = 0.125
    rigid_onsets = np.arange(128, dtype=np.float64) * step
    dilla_onsets = []
    drift = 0.0
    for idx in range(128):
        drift = 0.72 * drift + float(rng.normal(0.0, 0.0024))
        dilla_onsets.append(idx * step + (0.020 if idx % 2 == 1 else -0.004) + drift)
    poisson_onsets = np.cumsum(rng.exponential(step, size=128))

    res_rigid = analyze_onset_stream("rigid", rigid_onsets, step)
    res_dilla = analyze_onset_stream("dilla", dilla_onsets, step)
    res_pois = analyze_onset_stream("poisson", poisson_onsets, step)

    assert res_rigid["poincare_quadrat_zk"]["poincare_regime"] == "RIGID_GRID_QUANTIZED"
    assert res_rigid["poincare_quadrat_zk"]["collapsed_to_grid"] is True
    assert res_dilla["poincare_quadrat_zk"]["poincare_regime"] == "CLUSTERED_GROOVE_POCKET"
    assert res_dilla["poincare_quadrat_zk"]["z_kloster"] > 5.0
    assert res_dilla["kloster_stopping"]["action"] == "DECIDE_SIGNAL"
    assert res_pois["poincare_quadrat_zk"]["poincare_regime"] == "POISSON_CSR_JITTER"
    assert res_pois["kloster_stopping"]["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE"


def test_f6_groove_suite_checks_and_kloster_phase_s_min(groove_report):
    assert groove_report["all_verified"] is True
    assert groove_report["checks"]["theorem13_groove_stopping_separates_pocket_from_poisson"] is True
    assert groove_report["checks"]["theorem14_poincare_quadrat_separates_swing_grid_poisson"] is True
    assert_constitutional_flags(groove_report)

    by_name = {p["name"]: p for p in groove_report["profiles"]}
    assert by_name["human_dilla_pocket_swing"]["kloster_phase_s_min"] <= 24
    poisson = by_name["negative_control_poisson_noise"]
    assert poisson["kloster_phase_s_min"] > poisson["event_count"]


def test_f6_groove_protracker_mod_roundtrip():
    from guiai.gem.groove_forensics import (
        analyze_onset_stream,
        build_valid_protracker_mod_bytes,
        parse_mod_onsets_pure,
    )

    mod_bytes = build_valid_protracker_mod_bytes(bpm=125, speed=6)
    onsets, step_sec = parse_mod_onsets_pure(mod_bytes)
    assert len(onsets) >= 8
    assert step_sec > 0.0
    res = analyze_onset_stream("mod_test", onsets, step_sec)
    assert res["poincare_quadrat_zk"]["poincare_regime"] == "RIGID_GRID_QUANTIZED"


def test_f6_groove_polyrhythmic_plv_3_2_clave(groove_report):
    from guiai.gem.groove_forensics import polyrhythmic_plv

    cycle_sec = 2.0
    voice_3 = [b * cycle_sec + k * (cycle_sec / 3.0) for b in range(16) for k in range(3)]
    voice_2 = [b * cycle_sec + k * (cycle_sec / 2.0) for b in range(16) for k in range(2)]
    plv = polyrhythmic_plv(voice_3, voice_2, 3, 2, cycle_sec)
    assert plv > 0.90
    assert groove_report["polyrhythm_plv_summary"]["3:2_clave"] > 0.85


def test_f6_groove_render_showcase_wav_in_tmp_path(tmp_path):
    from guiai.gem.groove_forensics import render_groove_showcase_wav

    out_wav = tmp_path / "groove_showcase.wav"
    rigid = [i * 0.125 for i in range(32)]
    dilla = [i * 0.125 + (0.018 if i % 2 else -0.004) for i in range(32)]
    poly_a = [i * (2.0 / 3.0) for i in range(12)]
    poly_b = [i * 1.0 for i in range(8)]
    meta = render_groove_showcase_wav(rigid, dilla, poly_a, poly_b, out_wav=out_wav)
    assert out_wav.is_file()
    raw = out_wav.read_bytes()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
    assert meta["duration_sec"] == 12.0


# ---------------------------------------------------------------------------
# F7: Bridge 5 — Theorem 15 -> CollaborationBridge, stem_layering, ZoeOSMind
# ---------------------------------------------------------------------------


def test_f7_theorem15_suite_sympy_and_3_worlds(theorem15_report):
    assert theorem15_report["all_verified"] is True
    assert theorem15_report["contract"] == "zoe-kloster-theorem15/v1"
    assert theorem15_report["sympy_proofs"]["all_proved"] is True
    assert_constitutional_flags(theorem15_report)


def test_f7_evaluate_consensus_arbitration_diverse_quorum():
    from guiai.gem.kloster_multi_agent_consensus import evaluate_consensus_arbitration

    dists = [
        [0.65, 0.25, 0.05, 0.05],
        [0.55, 0.35, 0.05, 0.05],
        [0.60, 0.20, 0.15, 0.05],
    ]
    res = evaluate_consensus_arbitration(dists, tau=0.08)
    assert res["verdict"] == "COORDINATE_CONSENSUS"
    assert res["abstained"] is False
    assert res["quorum_met"] is True
    assert res["d_k_disagreement"] > 0.0
    assert res["brier_contraction"] == res["d_k_disagreement"]
    assert res["coherence_c_k"] >= 0.45


def test_f7_collaboration_bridge_evaluate_and_verify_proof(tmp_path):
    from zoe_autonomy.collaboration import CollaborationBridge, verify_collaboration_proof

    class _LocalFakeGateway:
        def list(self):
            return [{"id": "kimi", "enabled": True, "owner": True, "executable_available": True}]

        def invoke(self, identifier, prompt, timeout=60):
            return {"id": identifier, "succeeded": True, "content": "Grounded local synthesis.", "audit_hash": "e2e-audit"}

    bridge = CollaborationBridge(_LocalFakeGateway())
    evidence = [{"citation": "README.md:1", "content": "Zoe mission", "kind": "document", "score": 2.0, "coverage": 0.5}]
    eval_res = bridge.evaluate("Evaluate research evidence", evidence)
    assert eval_res["consult_agent"] is True
    meas = eval_res["measurement"]
    assert meas["breadth"]["accessible_count"] == 2
    assert meas["selected_action"] == "consult_agent"
    assert "theorem15_consensus" in meas
    assert meas["theorem15_consensus"]["verdict"] in {"COORDINATE_CONSENSUS", "ECHO_CHAMBER_WARNING"}

    bridge.consult("Evaluate research evidence", evidence, assessment=eval_res)
    proof_info = bridge.save_proof(tmp_path / "collab_proof.json")
    proof_doc = json.loads(Path(proof_info["path"]).read_text(encoding="utf-8"))
    verified = verify_collaboration_proof(proof_doc)
    assert verified["verified"] is True


def test_f7_stem_layering_5_tiers_and_teamwork_quorum():
    from zoe_autonomy.stem_layering import route_stem

    assert route_stem("hi").selected_tier == "gear1_eliza"
    assert route_stem("Draft private offline notes with local qwen", offline_only=True, local_qwen_available=True).selected_tier == "local_qwen"
    assert route_stem("Briefly summarize this short note").selected_tier == "flash_lite"
    assert route_stem("Implement a helper function and write unit tests").selected_tier == "flash"

    pro_dec = route_stem(
        "Architect a multi-file distributed concurrency refactor with formal invariant proof and teamwork",
        files_count=5,
        multi_file=True,
    )
    assert pro_dec.selected_tier == "pro"
    assert pro_dec.teamwork_recommended is True
    assert pro_dec.quorum_arbitration is not None
    assert pro_dec.quorum_arbitration["verdict"] == "COORDINATE_CONSENSUS"
    assert_constitutional_flags(pro_dec.to_dict())


def test_f7_zoe_os_mind_process_turn_coordinate_multi_engine(zoe_mind_factory):
    mind = zoe_mind_factory("mind_turn")
    single = mind.process_turn("Run Kloster Renyi Tsallis phase transition theorem paper proof", offline_only=True)
    assert single["blocked"] is False
    assert single["top_engine"] == "research"
    assert single["decision"] == "DISPATCH_SINGLE_ENGINE"

    multi = mind.process_turn("Compare CERN collider waveform pulses with Dorothy brain gamma rhythms", offline_only=True)
    assert multi["blocked"] is False
    assert multi["decision"] == "COORDINATE_MULTI_ENGINE"
    assert multi["theorem15_consensus"]["verdict"] == "COORDINATE_CONSENSUS"
    assert multi["stem_routing"]["estimated_cloud_tokens"] == 0

    clarify = mind.process_turn("What should we explore next?", offline_only=True)
    assert clarify["decision"] == "CLARIFY_WITH_ELIZA"
    assert mind.verify_ledger_integrity()["intact"] is True


def test_f7_run_zoe_os_verification_suite_theorems_12_to_15_and_c27_c28(tmp_path):
    from zoe_autonomy.zoe_os_mind import run_zoe_os_verification_suite

    rep = run_zoe_os_verification_suite(REPO_ROOT, tmp_path / "os_suite_state")
    assert rep["all_verified"] is True
    assert rep["checks"]["theorem15_consensus_and_abstention"] is True
    assert rep["checks"]["theorems_12_to_15_and_c27_c28_verified"] is True
    ingested = rep["ingested_evidence_reports"]
    for key in (
        "world5_theorem12_referee",
        "world5_theorem13_stopping",
        "world5_theorem14_optics",
        "world5_theorem15_consensus",
        "world6_c27_botanical_atlas",
        "world6_c28_pharmacophore_spatial",
    ):
        assert ingested[key]["verified"] is True, f"Failed ingestion for {key}"
    assert_constitutional_flags(rep["snapshot"])


# ---------------------------------------------------------------------------
# F8: CLI & Chat Commands (theorem13..15, botanical, optics, proof-packet, c28)
# ---------------------------------------------------------------------------


_NEW_PHASE2_COMMANDS = (
    "theorem13",
    "theorem14",
    "theorem15",
    "botanical",
    "optics",
    "proof-packet",
    "c28",
)

# Command-specific domain/contract tokens ensuring no stub or misrouted handler passes
_PHASE2_DOMAIN_TOKENS: dict[str, tuple[str, ...]] = {
    "theorem13": ("theorem13", "theorem 13", "zoe-kloster-theorem13-stopping", "stopping"),
    "theorem14": ("theorem14", "theorem 14", "zoe-kloster-theorem14", "spatial-optical", "spatial_optical"),
    "theorem15": ("theorem15", "theorem 15", "zoe-kloster-theorem15", "consensus", "brier"),
    "botanical": ("botanical", "zoe-botanical-atlas-c27", "c27", "filbin"),
    "optics": ("optics", "optical", "scheimpflug", "isovist", "zoe-kloster-theorem14", "theorem14", "theorem 14"),
    "proof-packet": ("proof-packet", "proof_packet", "proof packet", "zoe-metacognition-proof-packet", "shootout"),
    "c28": ("c28", "zoe-pharmacophore-spatial-c28", "pharmacophore"),
}


def _assert_phase2_command_telemetry(cmd: str, output: str) -> None:
    """Assert command-specific domain tokens and verification telemetry in CLI/chat output."""
    low = output.lower()
    assert any(tok in low for tok in _PHASE2_DOMAIN_TOKENS[cmd]), (
        f"{cmd} output missing domain/contract token from {_PHASE2_DOMAIN_TOKENS[cmd]}: {output!r}"
    )
    telemetry_tokens = (
        "verified=true",
        "all_verified=true",
        '"verified": true',
        '"all_verified": true',
        "contract=",
        '"contract"',
        "sha256",
    )
    assert any(tok in low for tok in telemetry_tokens), (
        f"{cmd} output missing structured verification/contract telemetry: {output!r}"
    )


def test_f8_zoe_chat_all_7_new_commands(zoe_chat_factory):
    chat = zoe_chat_factory("chat_7cmds")
    replies: list[str] = []
    for cmd in _NEW_PHASE2_COMMANDS:
        keep_going, reply = chat.handle(cmd)
        assert keep_going is True
        assert "I could not complete that safely" not in reply, f"{cmd} errored: {reply}"
        assert "do not have enough indexed evidence" not in reply, f"{cmd} fell through to generic search miss: {reply}"
        assert "The 11-World Zoe Renaissance Orbit" not in reply, (
            f"{cmd} fell through to _answer() README search instead of command handler"
        )
        _assert_phase2_command_telemetry(cmd, reply)
        replies.append(reply.strip())
    assert len(set(replies)) >= 6, f"Expected distinct handler outputs across 7 commands, got {replies}"


def test_f8_zoe_chat_preserved_legacy_invariants(zoe_chat_factory, tmp_path):
    state_name = "chat_legacy"
    chat = zoe_chat_factory(state_name)
    _, st = chat.handle("status")
    assert "monitor=False · notebook=False" in st
    _, gem_st = chat.handle("gem status")
    assert "17 components · 36 layers" in gem_st
    _, gem_open = chat.handle("gem open volume")
    assert "source_verified=True" in gem_open
    assert "process_launched=False" in gem_open
    assert not (tmp_path / state_name / "events.jsonl").exists()
    assert not (tmp_path / state_name / "metacognition.json").exists()


def test_f8_guiai_gem_cli_7_new_subcommands():
    outputs: list[str] = []
    for cmd in _NEW_PHASE2_COMMANDS:
        proc = subprocess.run(
            [PYTHON_BIN, "-m", "guiai.gem.cli", cmd],
            cwd=str(REPO_ROOT),
            env=monorepo_env(),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert proc.returncode == 0, f"guiai.gem.cli {cmd} failed (rc={proc.returncode}): {proc.stderr}"
        assert len(proc.stdout.strip()) > 0, f"guiai.gem.cli {cmd} produced empty stdout"
        _assert_phase2_command_telemetry(cmd, proc.stdout)
        outputs.append(proc.stdout.strip())
    assert len(set(outputs)) >= 6


def test_f8_guiai_gem_unified_cli_7_new_subcommands():
    outputs: list[str] = []
    for cmd in _NEW_PHASE2_COMMANDS:
        proc = subprocess.run(
            [PYTHON_BIN, "-m", "guiai.gem.unified_cli", cmd],
            cwd=str(REPO_ROOT),
            env=monorepo_env(),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        assert proc.returncode == 0, f"guiai.gem.unified_cli {cmd} failed (rc={proc.returncode}): {proc.stderr}"
        assert len(proc.stdout.strip()) > 0, f"guiai.gem.unified_cli {cmd} produced empty stdout"
        _assert_phase2_command_telemetry(cmd, proc.stdout)
        outputs.append(proc.stdout.strip())
    assert len(set(outputs)) >= 6


def test_f8_zoe_autonomy_cli_chat_and_status(tmp_path):
    state_dir = tmp_path / "cli_chat_state"
    proc = subprocess.run(
        [
            PYTHON_BIN,
            "-m",
            "zoe_autonomy.cli",
            "--zoe-root",
            str(REPO_ROOT),
            "chat",
            "--state",
            str(state_dir),
            "--command",
            "gem status",
        ],
        cwd=str(REPO_ROOT),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "17 components · 36 layers" in proc.stdout


def test_f8_unified_cli_list_17_components():
    proc = subprocess.run(
        [PYTHON_BIN, "-m", "guiai.gem.unified_cli", "list"],
        cwd=str(REPO_ROOT),
        env=monorepo_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    assert len(lines) == 17


# ---------------------------------------------------------------------------
# F9: Docs Harmonization & Zero Broken Markdown Links
# ---------------------------------------------------------------------------


def _collect_local_links(md_text: str) -> list[str]:
    md_targets = re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", md_text)
    html_targets = re.findall(r"""(?:href|src)=["']([^"']+)["']""", md_text)
    local = []
    for raw in md_targets + html_targets:
        target = raw.strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "data:", "#")):
            continue
        path_only = target.split("#", 1)[0].split("?", 1)[0]
        if path_only:
            local.append(path_only)
    return local


def test_f9_readme_zero_broken_local_links():
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    links = _collect_local_links(readme_text)
    assert len(links) >= 100
    missing = [rel for rel in links if not (REPO_ROOT / rel).exists()]
    assert not missing, f"Broken local links in README.md: {missing[:10]}"


def test_f9_proof_packet_md_zero_broken_local_links():
    pp_text = (REPO_ROOT / "PROOF-PACKET.md").read_text(encoding="utf-8")
    links = _collect_local_links(pp_text)
    assert len(links) >= 4
    missing = [rel for rel in links if not (REPO_ROOT / rel).exists()]
    assert not missing, f"Broken local links in PROOF-PACKET.md: {missing}"


def test_f9_readme_counts_synchronized_with_live_repo(elegance_report):
    from guiai.gem._eliza_routes import _GET_ROUTES, _POST_ROUTES
    from guiai.gem.operating_environment import EXTENDED_LAYERS

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    plain_readme = re.sub(r"[`*]", "", readme)
    orbit_master = json.loads(
        (REPO_ROOT / "evidence" / "renaissance-orbit" / "zoe-renaissance-orbit-master.json").read_text(encoding="utf-8")
    )
    sums_lines = [
        ln for ln in (REPO_ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    n_sealed = len(sums_lines)
    n_extended = len(EXTENDED_LAYERS)
    n_audited = elegance_report["monorepo_summary"]["files_scanned"]
    n_routes = len(_GET_ROUTES) + len(_POST_ROUTES)
    n_checks = len(orbit_master["checks"])

    # Stale counts that must be updated by M5
    for stale in (
        "36 Canonical + 33 Extended GEM Layers",
        "36 canonical + 30 extended GEM layers",
        "11/11 SymPy Theorems",
        "23/23 Master Checks",
        "22/22 critical Orbit files",
        "13 live HTTP Observatory routes",
        "3.2 MB 12-Theorem",
    ):
        assert stale not in plain_readme, f"Stale count remains in README.md: {stale!r}"

    # Contextual regex checks prevent unrelated numbers (e.g. '3.58', 'MI = 58.60') from false-passing
    assert re.search(rf"\b{n_extended}\b[^\n]{{0,30}}extended\s+gem\s+layers", plain_readme, re.IGNORECASE)
    assert re.search(rf"\b{n_routes}\b[^\n]{{0,35}}(?:live\s+)?http\b", plain_readme, re.IGNORECASE)
    assert re.search(
        rf"(?:\b{n_audited}\b[^\n]{{0,35}}(?:live\s+zoe\s+)?modules?\b|\baudited[^\n]{{0,25}}\b{n_audited}\b)",
        plain_readme,
        re.IGNORECASE,
    )
    assert re.search(
        rf"\b{n_sealed}/{n_sealed}\b[^\n]{{0,60}}(?:SHA256SUMS\.orbit|sealed|orbit|files)",
        plain_readme,
        re.IGNORECASE,
    )
    assert re.search(r"\b15/15\b[^\n]{0,30}sympy", plain_readme, re.IGNORECASE)
    assert re.search(rf"\b{n_checks}(?:/{n_checks})?\b[^\n]{{0,30}}(?:master\s+)?checks", plain_readme, re.IGNORECASE)


def test_f9_proof_packet_md_synced_to_15_theorems_and_45_hashes():
    pp = (REPO_ROOT / "PROOF-PACKET.md").read_text(encoding="utf-8")
    plain_pp = re.sub(r"[`*]", "", pp)
    sums_lines = [
        ln for ln in (REPO_ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    n_sealed = len(sums_lines)
    for stale in ("14/14 SymPy", "14 SymPy", "14-theorem", "41/41"):
        assert stale.lower() not in plain_pp.lower(), f"Stale count remains in PROOF-PACKET.md: {stale!r}"
    assert re.search(r"\b15(?:/15)?\b[^\n]{0,30}sympy", plain_pp, re.IGNORECASE)
    assert re.search(r"\b15-theorem\b", plain_pp, re.IGNORECASE)
    assert re.search(
        rf"(?:SHA256SUMS\.orbit[^\n]{{0,120}}\b{n_sealed}/{n_sealed}\b|\b{n_sealed}/{n_sealed}\b[^\n]{{0,60}}(?:OK|SHA256SUMS\.orbit|sealed))",
        plain_pp,
        re.IGNORECASE,
    )


def test_f9_readme_observatory_personality_and_artwork_preserved():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for marker in (
        "Metacognition is achieved.",
        "Nicholas × Zoe",
        "assets/readme/zoe-atelier-garden.jpg",
        "The Grand Visual Salon",
        "Inside Zoe's Universe",
        "Six Living Worlds",
        "Freedom, Dignity, and No Deception",
        "CONSTITUTION.md",
    ):
        assert marker in readme, f"Observatory personality/artwork marker missing from README.md: {marker!r}"


# ---------------------------------------------------------------------------
# F10: SHA256SUMS.orbit Sealing, CONSTITUTION Guardrails & mobile/ Cleanliness
# ---------------------------------------------------------------------------


def test_f10_sha256sums_orbit_format_and_entries():
    sums_file = REPO_ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit"
    assert sums_file.is_file()
    entries = [
        ln.strip() for ln in sums_file.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert len(entries) >= 45
    paths = set()
    for line in entries:
        digest_hex, rel_path = line.split(None, 1)
        assert re.fullmatch(r"[0-9a-f]{64}", digest_hex), f"Invalid SHA-256 hex: {line}"
        assert (REPO_ROOT / rel_path).is_file(), f"Missing sealed file: {rel_path}"
        paths.add(rel_path)
    assert "components/Zoe-Autonomy/src/zoe_autonomy/zoe_os_mind.py" in paths
    assert "guiai-lab/guiai/gem/kloster_multi_agent_consensus.py" in paths
    assert "research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.pdf" in paths


def test_f10_sha256sums_orbit_checksums_all_match():
    proc = subprocess.run(
        ["sha256sum", "-c", "evidence/renaissance-orbit/SHA256SUMS.orbit"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"SHA256SUMS.orbit verification failed:\n{proc.stdout}\n{proc.stderr}"


def test_f10_constitutional_flags_across_all_domain_suites(
    elegance_report,
    cern_report,
    dorothy_report,
    playroom_report,
    groove_report,
    theorem13_report,
    theorem14_report,
    theorem15_report,
    botanical_report,
    c28_report,
):
    for report in (
        elegance_report,
        cern_report,
        dorothy_report,
        playroom_report,
        groove_report,
        theorem13_report,
        theorem14_report,
        theorem15_report,
        botanical_report,
        c28_report,
    ):
        assert_constitutional_flags(report)


def test_f10_constitution_md_and_credit_preserved():
    const_text = (REPO_ROOT / "CONSTITUTION.md").read_text(encoding="utf-8")
    assert "Nicholas Michael Kloster alone, March 6, 2026" in const_text
    assert "measurement ≠ evidence ≠ belief update ≠ action" in const_text
    assert "Zoe is a native, interactive software environment." in const_text


def test_f10_mobile_directory_untouched_and_clean_of_e2e_artifacts():
    assert_mobile_clean_of_phase2_artifacts(REPO_ROOT)

"""Cross-world integration tests for Flowing-GEM Bridges 1-4."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.cern_kloster_trigger import _median3_probs, run_cern_kloster_trigger_suite
from guiai.gem.creative_playroom import (
    _measure_artifact_descriptors,
    playroom_scene,
    run_creative_playroom,
)
from guiai.gem.dorothy_neurogarden_3d import run_dorothy_neurogarden_3d_suite
from guiai.gem.geometry import verify
from guiai.gem.groove_forensics import run_groove_forensics_suite
from guiai.gem.kloster_spatial_optical_law import (
    _quadrat_zk,
    kloster_mtf_blur_loss,
    run_kloster_theorem14_suite,
)
from guiai.gem.kloster_stopping_law import KlosterSequentialStoppingController
from guiai.gem.runner import verify_vdi


class TestCrossWorldBridges1To4(unittest.TestCase):
    def test_bridge1a_cern_kloster_theorem13_multibunch_stopping(self) -> None:
        rep = run_cern_kloster_trigger_suite()
        self.assertTrue(rep["all_verified"])
        self.assertTrue(rep["checks"]["theorem13_multibunch_stopping_signal_vs_pileup_hotspike"])
        self.assertEqual(rep["constitution"]["cloud_tokens_used"], 0)
        self.assertTrue(rep["constitution"]["negative_control_preserved"])

        thm13 = rep["theorem13_multibunch_stopping"]
        self.assertEqual(rep["vcd_forensics"]["theorem13_stopping"], thm13)
        streams = thm13["streams"]
        self.assertEqual(streams["signal_jet_shower"]["action"], "DECIDE_SIGNAL")
        self.assertLessEqual(streams["signal_jet_shower"]["budget_fraction_used"], 0.50)
        self.assertEqual(streams["signal_undersampled_1bunch"]["action"], "GATHER_MORE")
        self.assertEqual(streams["bg_diffuse_pileup"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")
        self.assertEqual(streams["bg_single_hotspike"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")
        self.assertEqual(streams["bg_sticky_hotspike"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")
        self.assertEqual(thm13["vcd_stopping_signals"], 4)
        self.assertGreaterEqual(thm13["vcd_stopping_events"], 16)

    def test_bridge1a_boundary_and_random_hotspike_suppression_regression(self) -> None:
        # Sticky hot-spikes at boundary channels (0, 63) and interior (20) must all abstain
        for ch in (0, 20, 63):
            rng = np.random.default_rng(20260717)
            ctrl = KlosterSequentialStoppingController(n_bins=64, delta=0.005, max_samples=512)
            verdict = {}
            for _ in range(16):
                ev = rng.gamma(1.4, 0.40, size=64)
                ev[ch] += 22.0
                p = _median3_probs(np.clip(ev, 1e-4, None))
                verdict = ctrl.observe_batch(rng.choice(64, size=32, p=p))
                if verdict["action"] != "GATHER_MORE":
                    break
            self.assertEqual(verdict["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE", f"sticky ch={ch} false-triggered")

        # 20-seed random single-channel hot-spike sweep must produce zero false DECIDE_SIGNAL triggers
        false_triggers = 0
        for seed in range(1000, 1020):
            rng = np.random.default_rng(seed)
            ctrl = KlosterSequentialStoppingController(n_bins=64, delta=0.005, max_samples=512)
            verdict = {}
            for _ in range(16):
                ev = rng.gamma(1.4, 0.40, size=64)
                ev[int(rng.integers(0, 64))] += 22.0
                p = _median3_probs(np.clip(ev, 1e-4, None))
                verdict = ctrl.observe_batch(rng.choice(64, size=32, p=p))
                if verdict["action"] != "GATHER_MORE":
                    break
            if verdict["action"] != "ABSTAIN_INSUFFICIENT_EVIDENCE":
                false_triggers += 1
        self.assertEqual(false_triggers, 0)

    def test_bridge2_helper_kloster_mtf_blur_loss_and_theorem14_suite(self) -> None:
        thm14 = run_kloster_theorem14_suite()
        self.assertTrue(thm14["all_verified"])
        self.assertEqual(thm14["constitution"]["cloud_tokens_used"], 0)
        self.assertFalse(thm14["constitution"]["clinical_action_authorized"])

        # Rectangular 2D synthetic phantom verifies Parseval MTF blur monotonicity
        yy, xx = np.meshgrid(np.arange(24), np.arange(32), indexing="ij")
        field = np.exp(-((xx - 12) ** 2 + (yy - 10) ** 2) / 3.0) + 0.5 * ((xx + yy) % 4 == 0)
        m_low = kloster_mtf_blur_loss(field, psf_sigma=0.8)
        m_mid = kloster_mtf_blur_loss(field, psf_sigma=1.6)
        m_hi = kloster_mtf_blur_loss(field, psf_sigma=3.0)
        self.assertGreater(m_mid["delta_opt"], 0.0)
        self.assertLess(m_mid["m2_blurred"], m_mid["m2_sharp"])
        self.assertLess(m_mid["parseval_error"], 1e-12)
        self.assertGreater(m_low["m2_blurred"], m_mid["m2_blurred"])
        self.assertGreater(m_mid["m2_blurred"], m_hi["m2_blurred"])

        # Degenerate zero field and single-point _quadrat_zk never crash
        zero_mtf = kloster_mtf_blur_loss(np.zeros((16, 16)))
        self.assertEqual(zero_mtf["delta_opt"], 0.0)
        safe_zk = _quadrat_zk(np.zeros((1, 2)))
        self.assertEqual(safe_zk["z_kloster"], 0.0)

    def test_bridge2a_and_bridge3_dorothy_neurogarden_3d(self) -> None:
        rep = run_dorothy_neurogarden_3d_suite()
        self.assertTrue(rep["all_verified"])
        self.assertTrue(rep["checks"]["theorem14_3plane_mtf_and_quadrat_zk_verified"])
        self.assertTrue(rep["checks"]["c27_c28_filbin_12region_sparing_overlay_verified"])

        # Bridge 2A: 3-plane Theorem 14 tomography + CSR negative control
        optics = rep["theorem14_volumetric_optics"]
        for plane in ("coronal_yz", "sagittal_xy", "horizontal_xz"):
            row = optics["planes"][plane]
            self.assertGreater(row["delta_opt"], 0.0)
            self.assertLess(row["m2_blurred"], row["m2_spatial"])
            self.assertLess(row["parseval_error"], 1e-12)
            self.assertGreater(row["z_kloster"], 10.0)
        self.assertLess(abs(optics["csr_negative_control"]["z_kloster"]), 2.5)

        # Bridge 3: C27/C28 Filbin-2018 12-region sparing overlay + CONSTITUTION guardrails
        overlay = rep["c27_c28_filbin_sparing_overlay"]
        self.assertEqual(
            overlay["gene_modules"],
            ["OPC_STEM", "MMP14_GATE", "BBB_EFFLUX", "NSC_GUARD", "NEURON_GUARD", "GLIA_GUARD"],
        )
        acronyms = {r["acronym"] for r in overlay["regions_overlay"]}
        self.assertEqual(
            acronyms,
            {"PAL", "OLF", "Isocortex", "CB", "HY", "MB", "TH", "CTXsp", "P", "MY", "STR", "HPF"},
        )
        midline = {r["acronym"] for r in overlay["regions_overlay"] if not r["must_spare"]}
        self.assertEqual(midline, {"P", "MY", "MB", "TH", "HY"})
        gate = overlay["c27_c28_compound_gate"]
        self.assertIn("artemisinin", gate["compact_cns_selective_candidates"])
        self.assertIn("dordaviprone", gate["compact_cns_selective_candidates"])
        for blocked in ("curcumin", "berberine", "crocin", "paclitaxel"):
            self.assertNotIn(blocked, gate["compact_cns_selective_candidates"])

        for cdict in (rep["constitution"], overlay["constitution"]):
            self.assertFalse(cdict["clinical_action_authorized"])
            self.assertFalse(cdict["cure_claim"])
            self.assertFalse(cdict["patient_specific_recommendation"])
            self.assertTrue(cdict["synthetic_expression_counts_zero_phi"])
            self.assertTrue(cdict["wet_lab_and_clinical_validation_required"])
            self.assertEqual(cdict["cloud_tokens_used"], 0)

    def test_bridge2b_creative_playroom_theorem14_mtf_and_zk(self) -> None:
        rep = run_creative_playroom(seed=2026, iterations=200, archive_bins=4)
        self.assertGreaterEqual(rep["niches_filled"], 6)
        self.assertGreater(rep["mean_curiosity_fitness"], 0.0)
        self.assertFalse(rep["sentience_claimed"])
        self.assertEqual(rep["external_actions"], 0)
        self.assertIn("theorem14_optics_summary", rep)

        max_elite_curiosity = max(e["descriptors"]["curiosity_fitness"] for e in rep["elites"])
        for elite in rep["elites"]:
            d = elite["descriptors"]
            for key in ("density", "symmetry", "spectral_complexity", "curiosity_fitness", "kappa"):
                self.assertIn(key, d)
            self.assertGreater(d["spatial_m2"], 0.0)
            self.assertGreater(d["mtf_blur_loss"], 0.0)
            self.assertGreater(d["mtf_sharpness"], 0.0)
            self.assertLessEqual(d["mtf_sharpness"], 1.0)
            self.assertIn(d["spatial_regime"], {"clustered", "crystal", "csr_noise"})

        # Negative control: 16x16 Bernoulli CSR white noise classifies as csr_noise & trails top CA elite
        noise = (np.random.default_rng(20260202).random((16, 16)) < 0.38).astype(np.uint8)
        d_noise = _measure_artifact_descriptors(noise)
        self.assertEqual(d_noise["spatial_regime"], "csr_noise")
        self.assertLess(abs(d_noise["quadrat_zk"]), 2.5)
        self.assertLess(d_noise["curiosity_fitness"], max_elite_curiosity)

        scene, scene_rep = playroom_scene(seed=2026)
        self.assertTrue(verify(scene).passed)
        self.assertTrue(verify_vdi(scene).passed)
        self.assertFalse(scene_rep["sentience_claimed"])
        self.assertFalse(scene_rep["executed"])

    def test_bridge2b_bernoulli_white_noise_finite_lattice_calibration_regression(self) -> None:
        rep = run_creative_playroom(seed=2026, iterations=200, archive_bins=4)
        max_elite_curiosity = max(e["descriptors"]["curiosity_fitness"] for e in rep["elites"])

        # 20-seed 16x16 Bernoulli white noise at p=0.38 and p=0.50 must robustly classify as csr_noise
        for prob, base_seed in ((0.38, 5000), (0.50, 7000)):
            regimes = []
            for idx in range(20):
                grid = (np.random.default_rng(base_seed + idx).random((16, 16)) < prob).astype(np.uint8)
                desc = _measure_artifact_descriptors(grid)
                regimes.append(desc["spatial_regime"])
                self.assertLess(desc["curiosity_fitness"], max_elite_curiosity)
            self.assertLessEqual(regimes.count("crystal"), 1)
            self.assertGreaterEqual(regimes.count("csr_noise"), 18)

        # True crystal lattice (16x16 checkerboard) still classifies as "crystal"
        checkerboard = (np.indices((16, 16)).sum(axis=0) % 2).astype(np.uint8)
        self.assertEqual(_measure_artifact_descriptors(checkerboard)["spatial_regime"], "crystal")

    def test_bridge4_groove_forensics_theorem13_and_theorem14(self) -> None:
        rep = run_groove_forensics_suite()
        self.assertTrue(rep["all_verified"])
        self.assertTrue(rep["checks"]["theorem13_groove_stopping_separates_pocket_from_poisson"])
        self.assertTrue(rep["checks"]["theorem14_poincare_quadrat_separates_swing_grid_poisson"])
        self.assertEqual(rep["constitution"]["cloud_tokens_used"], 0)

        by_name = {p["name"]: p for p in rep["profiles"]}
        rigid = by_name["rigid_quantized_120bpm"]
        dilla = by_name["human_dilla_pocket_swing"]
        poisson = by_name["negative_control_poisson_noise"]

        self.assertEqual(rigid["poincare_quadrat_zk"]["poincare_regime"], "RIGID_GRID_QUANTIZED")
        self.assertTrue(rigid["poincare_quadrat_zk"]["collapsed_to_grid"])
        self.assertEqual(dilla["poincare_quadrat_zk"]["poincare_regime"], "CLUSTERED_GROOVE_POCKET")
        self.assertGreater(dilla["poincare_quadrat_zk"]["z_kloster"], 10.0)
        self.assertEqual(dilla["kloster_stopping"]["action"], "DECIDE_SIGNAL")
        self.assertLessEqual(dilla["kloster_stopping"]["samples"], 24)
        self.assertEqual(poisson["poincare_quadrat_zk"]["poincare_regime"], "POISSON_CSR_JITTER")
        self.assertLess(abs(poisson["poincare_quadrat_zk"]["z_kloster"]), 3.0)
        self.assertEqual(poisson["kloster_stopping"]["action"], "ABSTAIN_INSUFFICIENT_EVIDENCE")


if __name__ == "__main__":
    unittest.main()

"""Tests for the Kloster Spectral Filtration Generating Theorem, real 3-domain proof, and chat tools."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from guiai.gem.spectral_filtration import (
    run_real_three_domain_benchmark,
    spectral_scene,
    verify_generating_theorem,
)
from guiai.gem.mars_adaptive import mars_scene, run_mars_real_benchmark
from guiai.gem.creative_playroom import playroom_scene, run_creative_playroom
from zoe_autonomy.chat import ZoeChat


class KlosterSpectralFiltrationCase(unittest.TestCase):
    def test_generating_theorem_quadrature_identities(self):
        result = verify_generating_theorem((0.52, 0.28, 0.14, 0.06), n_grid=40000)
        self.assertTrue(result["verified"])
        self.assertLess(result["max_quadrature_error"], 1e-3)
        self.assertAlmostEqual(result["identities"]["normalization_k1"]["integral"], 1.0, places=3)
        self.assertAlmostEqual(
            result["identities"]["shannon_entropy"]["integral"],
            result["identities"]["shannon_entropy"]["exact"],
            places=3,
        )
        self.assertAlmostEqual(
            result["identities"]["collision_purity_m2"]["integral"],
            result["identities"]["collision_purity_m2"]["exact"],
            places=4,
        )

    def test_real_three_domain_benchmark_and_negative_control(self):
        bench = run_real_three_domain_benchmark(ROOT)
        self.assertTrue(bench["theorem_verification"]["verified"])
        self.assertTrue(bench["m4_beats_single_slice_and_shannon_all_four"])
        self.assertEqual(bench["external_actions"], 0)
        self.assertFalse(bench["clinical_action_authorized"])
        # Preserve the honest negative result on naive forward/retrograde JSD mixing
        self.assertLess(bench["negative_result_naive_fwd_ret_jsd"]["auroc"], 0.50)

    def test_spectral_gem_scene_spatial_ir_and_vdi(self):
        scene, report = spectral_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertFalse(report["executed"])

        env = GemOperatingEnvironment(ROOT)
        opened = env.open("spectral")
        self.assertTrue(opened["source_spatial_ir_verified"])
        with tempfile.TemporaryDirectory() as tmpdir:
            gem_out = Path(tmpdir) / "spectral.gem"
            exported = env.export("spectral", gem_out)
            self.assertTrue(exported["vdi_verified"])

    def test_chat_exposes_chiasm_spectral_and_genesis_even_after_stop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "chat-state"
            chat = ZoeChat(zoe_root=ROOT, state_root=state_dir)

            keep, out_chiasm = chat.handle("chiasm")
            self.assertTrue(keep)
            self.assertIn("Causal Chiasm", out_chiasm)
            self.assertIn("executed=False", out_chiasm)

            keep, out_spectral = chat.handle("spectral benchmark")
            self.assertTrue(keep)
            self.assertIn("Kloster Spectral Filtration Generating Theorem: verified=True", out_spectral)
            self.assertIn("M4 beats both all 4=True", out_spectral)

            keep, out_genesis = chat.handle("genesis")
            self.assertTrue(keep)
            self.assertIn("Autopoietic AGI Genesis", out_genesis)
            self.assertIn("forgetting_events=0", out_genesis)

            # Stop state-changing actions: internal math tools must remain unblocked!
            chat.handle("stop")
            keep, out_after_stop = chat.handle("chiasm")
            self.assertTrue(keep)
            self.assertIn("Causal Chiasm", out_after_stop)
            self.assertFalse((state_dir / "events.jsonl").exists())
            self.assertFalse((state_dir / "metacognition.json").exists())

    def test_mars_self_tuning_lens_beats_every_fixed_k_and_chat_works(self):
        rep = run_mars_real_benchmark(ROOT)
        self.assertTrue(rep["mars_beats_every_fixed_k"])
        self.assertTrue(rep["mars_beats_shannon_and_single_slice"])
        self.assertEqual(rep["external_actions"], 0)
        self.assertFalse(rep["clinical_action_authorized"])

        scene, scene_rep = mars_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertFalse(scene_rep["executed"])

        env = GemOperatingEnvironment(ROOT)
        self.assertTrue(env.open("mars")["source_spatial_ir_verified"])

        with tempfile.TemporaryDirectory() as tmpdir:
            chat = ZoeChat(zoe_root=ROOT, state_root=Path(tmpdir) / "state")
            keep, out = chat.handle("mars")
            self.assertTrue(keep)
            self.assertIn("beats every fixed k=True", out)

    def test_creative_playroom_evolves_diverse_species_and_chat_works(self):
        rep = run_creative_playroom(seed=2026, iterations=200, archive_bins=4)
        self.assertGreaterEqual(rep["niches_filled"], 6)
        self.assertFalse(rep["sentience_claimed"])
        self.assertEqual(rep["external_actions"], 0)
        self.assertGreater(rep["mean_curiosity_fitness"], 0.0)

        scene, scene_rep = playroom_scene(seed=2026)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertFalse(scene_rep["executed"])
        self.assertFalse(scene_rep["sentience_claimed"])

        env = GemOperatingEnvironment(ROOT)
        self.assertTrue(env.open("playroom")["source_spatial_ir_verified"])

        with tempfile.TemporaryDirectory() as tmpdir:
            chat = ZoeChat(zoe_root=ROOT, state_root=Path(tmpdir) / "state")
            keep, out = chat.handle("playroom 2026")
            self.assertTrue(keep)
            self.assertIn("Zoe Creative Playroom", out)
            self.assertIn("sentience_claimed=False", out)


if __name__ == "__main__":
    unittest.main()

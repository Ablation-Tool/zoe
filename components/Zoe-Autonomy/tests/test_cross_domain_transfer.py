"""Tests for L4 Cross-Domain Self-Improvement Transfer and Causal Chiasm."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from zoe_autonomy.cross_domain_transfer import (
    gen0_single_slice_operator,
    gen1_persistent_filtration_operator,
    gen2_causal_chiasm_operator,
    run_cross_domain_self_improvement,
)
from zoe_autonomy.agi_discovery import (
    AGI_TEN_DOMAINS,
    gen3_autopoietic_genesis_operator,
    run_autonomous_discovery_cycle,
)
from guiai.gem.chiasm import (
    causal_chiasm,
    chiasm_scene,
    persistent_filtration_tomography,
)
from guiai.gem.genesis import genesis_scene
from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi


class CrossDomainChiasmCase(unittest.TestCase):
    def test_l4_cross_domain_self_improvement_passes_two_generations(self):
        report = run_cross_domain_self_improvement()
        self.assertTrue(report["l4_gate_passed"])
        self.assertEqual(report["domain_count"], 3)
        self.assertEqual(report["consecutive_adopted_generations"], 2)
        self.assertFalse(report["domain_specific_tuning"])
        self.assertEqual(report["external_actions"], 0)

        g0, g1, g2 = report["generations"]
        self.assertLess(g0["mean_f1"], g1["mean_f1"])
        self.assertLess(g1["mean_f1"], g2["mean_f1"])
        self.assertEqual(g1["regressions"], [])
        self.assertEqual(g2["regressions"], [])
        self.assertEqual(len(g1["improved_domains"]), 3)
        self.assertEqual(len(g2["improved_domains"]), 3)

    def test_causal_chiasm_detects_future_boxing_and_preserves_dignity(self):
        past = {"a": 0.40, "b": 0.35, "c": 0.25}
        open_future = {"a": 0.45, "b": 0.40, "c": 0.15}
        boxed_future = {"a": 0.92, "b": 0.05, "c": 0.03}

        good = causal_chiasm(past, open_future, tau=0.20)
        self.assertFalse(good["future_boxed_in"])
        self.assertEqual(good["presence_glyph"], "^_^")
        self.assertFalse(good["executed"])

        boxed = causal_chiasm(past, boxed_future, tau=0.20)
        self.assertTrue(boxed["future_boxed_in"])
        self.assertEqual(boxed["presence_glyph"], "??")

    def test_persistent_filtration_separates_invariants_from_noise(self):
        episodes = [
            {"truth_core": 0.60, "transient_spike": 0.35, "noise": 0.05},
            {"truth_core": 0.80, "transient_spike": 0.12, "noise": 0.08},
            {"truth_core": 0.82, "transient_spike": 0.10, "noise": 0.08},
        ]
        tomo = persistent_filtration_tomography(episodes, invariant_tau=0.35)
        self.assertEqual(tomo["structural_invariants"], ["truth_core"])
        self.assertIn("transient_spike", tomo["transient_states"])
        self.assertFalse(tomo["executed"])

    def test_chiasm_gem_scene_spatial_ir_vdi_and_html_export(self):
        scene, report = chiasm_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertFalse(report["executed"])

        env = GemOperatingEnvironment(ROOT)
        opened = env.open("chiasm")
        self.assertTrue(opened["source_spatial_ir_verified"])
        self.assertEqual(opened["external_actions"], 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            gem_out = Path(tmpdir) / "chiasm.gem"
            html_out = Path(tmpdir) / "chiasm.html"
            res_gem = env.export("chiasm", gem_out)
            res_html = env.export("chiasm", html_out)
            self.assertTrue(res_gem["vdi_verified"])
            self.assertTrue(html_out.is_file())
            self.assertIn("ZOE / DOROTHY QUALIA HUD", html_out.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                env.export("chiasm", html_out)

    def test_autopoietic_agi_discovery_ten_domains_and_zero_forgetting(self):
        report = run_autonomous_discovery_cycle()
        self.assertEqual(report["domain_count"], 10)
        self.assertEqual(tuple(report["domains"]), AGI_TEN_DOMAINS)
        self.assertEqual(len(report["research_cycle_stages"]), 9)
        self.assertEqual(report["catastrophic_forgetting_events"], 0)
        self.assertTrue(report["all_ten_domains_qualified"])
        self.assertTrue(report["independent_reproduction_verified"])
        self.assertEqual(report["external_actions"], 0)

        means = report["mean_f1_by_generation"]
        self.assertLess(means["static_gen0_control"], means["gen1_filtration"])
        self.assertLess(means["gen1_filtration"], means["gen2_causal_chiasm"])
        self.assertLess(means["gen2_causal_chiasm"], means["gen3_autopoietic_genesis"])
        self.assertEqual(means["gen3_autopoietic_genesis"], 1.0)

    def test_genesis_gem_scene_spatial_ir_and_vdi(self):
        scene, report = genesis_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertEqual(report["domains_qualified"], 10)
        self.assertFalse(report["executed"])

        env = GemOperatingEnvironment(ROOT)
        opened = env.open("genesis")
        self.assertTrue(opened["source_spatial_ir_verified"])
        self.assertEqual(opened["external_actions"], 0)


if __name__ == "__main__":
    unittest.main()

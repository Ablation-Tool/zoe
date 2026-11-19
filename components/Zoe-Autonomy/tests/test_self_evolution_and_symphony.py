"""Tests for Zoe Stage 5B/C: L4 Sandboxed AST Self-Evolution, Live Neural Mind, and Playroom Symphony."""

from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.creative_symphony import (
    run_creative_symphony,
    symphony_scene,
    synthesize_symphony_wav,
)
from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from zoe_autonomy.chat import ZoeChat
from zoe_autonomy.neural_mind import inspect_thought
from zoe_autonomy.self_evolution import (
    SafeExpressionEvaluator,
    UnsafeExpressionError,
    run_self_evolution,
)


class SelfEvolutionNeuralMindAndSymphonyCase(unittest.TestCase):
    def test_ast_sandbox_blocks_hostile_code_injection(self):
        hostile = [
            "__import__('os').system('echo pwn')",
            "(lambda x: x)(m2)",
            "m2.__class__.__mro__",
            "open('/etc/passwd').read()",
            "unknown_var + 1",
            "log(m2, 2)",
        ]
        for expr in hostile:
            with self.assertRaises(UnsafeExpressionError, msg=f"Failed to block: {expr}"):
                SafeExpressionEvaluator.validate(expr)

    def test_l4_four_domain_self_evolution_adopts_multi_gen_and_rolls_back_overfit(self):
        rep = run_self_evolution(ROOT, seed=2026)
        self.assertTrue(rep["l4_two_consecutive_generations_verified"])
        self.assertGreaterEqual(rep["max_consecutive_adopted_generations"], 2)
        self.assertGreater(rep["total_gain_over_gen0"], 0.15)
        self.assertTrue(rep["ast_sandbox_hostile_probe_blocked"])
        self.assertTrue(rep["adversarial_label_shuffle_control"]["passed_no_leakage"])
        self.assertTrue(rep["poison_regression_control_rejected"])
        # Gen 4 aggressive overfit probe must be rejected & rolled back cleanly!
        self.assertGreaterEqual(len(rep["rejected_negative_results"]), 1)
        self.assertTrue(rep["rejected_negative_results"][0]["rolled_back"])
        # Epistemic honesty invariants
        self.assertEqual(rep["external_actions"], 0)
        self.assertFalse(rep["sentience_claimed"])
        self.assertFalse(rep["l5_agi_qualified"])

    def test_live_neural_mind_and_chat_commands(self):
        thought = inspect_thought("Dorothy connects geometry with calibrated uncertainty and play.", max_new_tokens=10)
        self.assertGreater(thought["tokens_observed"], 3)
        self.assertEqual(thought["external_actions"], 0)
        self.assertFalse(thought["sentience_claimed"])

        with tempfile.TemporaryDirectory() as tmpdir:
            chat = ZoeChat(zoe_root=ROOT, state_root=Path(tmpdir) / "state")
            keep, out_mind = chat.handle("mind Curiosity turns geometry into discovery")
            self.assertTrue(keep)
            self.assertIn("Zoe Live Neural-Symbolic Mind", out_mind)
            self.assertIn("sentience_claimed=False", out_mind)

            keep, out_evolve = chat.handle("evolve")
            self.assertTrue(keep)
            self.assertIn("L4 >=2 verified=True", out_evolve)
            self.assertIn("L5_AGI_qualified=False", out_evolve)

            keep, out_jam = chat.handle("jam 2026")
            self.assertTrue(keep)
            self.assertIn("Zoe Playroom Symphony", out_jam)
            self.assertIn(".wav", out_jam)

    def test_creative_symphony_wav_audio_and_gem_vdi_scene(self):
        rep = run_creative_symphony(seed=2026, iterations=200, archive_bins=4)
        self.assertGreaterEqual(rep["niches_filled"], 6)
        self.assertIsNotNone(rep["champion"])
        self.assertFalse(rep["sentience_claimed"])
        self.assertEqual(rep["external_actions"], 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_file = Path(tmpdir) / "zoe-test-jam.wav"
            audio = synthesize_symphony_wav(rep["champion"], wav_file)
            self.assertTrue(wav_file.is_file())
            self.assertGreater(audio["bytes"], 100_000)
            with wave.open(str(wav_file), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getframerate(), 44100)
                self.assertGreater(wf.getnframes(), 44100 * 4)

        scene, scene_rep = symphony_scene(seed=2026)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertFalse(scene_rep["executed"])
        self.assertFalse(scene_rep["sentience_claimed"])

        env = GemOperatingEnvironment(ROOT)
        self.assertTrue(env.open("symphony")["source_spatial_ir_verified"])


if __name__ == "__main__":
    unittest.main()

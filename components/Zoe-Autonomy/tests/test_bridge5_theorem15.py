from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
GUIAI_DIR = REPO_ROOT / "guiai-lab"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zoe_autonomy.collaboration import CollaborationBridge, verify_collaboration_proof  # noqa: E402
from zoe_autonomy.stem_layering import route_stem  # noqa: E402
from zoe_autonomy.zoe_os_mind import ZoeOSMind, run_zoe_os_verification_suite  # noqa: E402


class _FakeGateway:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def list(self) -> list[dict]:
        return [{"id": "kimi", "enabled": True, "owner": True, "executable_available": True}]

    def invoke(self, identifier: str, prompt: str, timeout: int = 60) -> dict:
        self.prompts.append(prompt)
        return {
            "id": identifier,
            "succeeded": True,
            "content": "Synthesized bounded context from mock agent.",
            "audit_hash": "mock-bridge5-audit",
        }


def _import_theorem15_module():
    if GUIAI_DIR.is_dir() and str(GUIAI_DIR) not in sys.path:
        sys.path.insert(0, str(GUIAI_DIR))
    import guiai.gem.kloster_multi_agent_consensus as kmc
    return kmc


@unittest.skipUnless(GUIAI_DIR.is_dir(), "requires guiai-lab checkout")
class TestTheorem15ArbitrationHelper(unittest.TestCase):
    def setUp(self) -> None:
        self.kmc = _import_theorem15_module()

    def test_diverse_consensus_and_exact_brier_identity(self) -> None:
        self.assertIs(self.kmc.arbitrate_multi_agent_quorum, self.kmc.evaluate_consensus_arbitration)
        dists = [[0.80, 0.15, 0.05], [0.70, 0.25, 0.05]]
        res = self.kmc.evaluate_consensus_arbitration(dists, tau=0.08)
        self.assertEqual(res["verdict"], "COORDINATE_CONSENSUS")
        self.assertEqual(res["reason"], "coherent_diverse_consensus")
        self.assertFalse(res["abstained"])
        self.assertFalse(res["echo_chamber_detected"])
        self.assertFalse(res["rogue_node_detected"])
        self.assertFalse(res["bluff_detected"])
        self.assertTrue(res["quorum_met"])
        self.assertGreater(res["d_k_disagreement"], 0.0)
        self.assertGreaterEqual(res["coherence_c_k"], 0.45)
        self.assertEqual(res["brier_contraction"], res["d_k_disagreement"])
        self.assertEqual(res["consensus_argmax"], 0)
        self.assertEqual(res["a_tau_pool"], 2)

        # Verify exact Brier gain == D_K against arbitrary one-hot target y.
        p_bar = res["consensus_p_bar"]
        for y_idx in range(3):
            y = [1.0 if i == y_idx else 0.0 for i in range(3)]
            mean_brier = 0.5 * sum(
                sum((p[i] - y[i]) ** 2 for i in range(3)) for p in dists
            )
            pool_brier = sum((p_bar[i] - y[i]) ** 2 for i in range(3))
            self.assertAlmostEqual(mean_brier - pool_brier, res["d_k_disagreement"], places=6)

        # World 3 honest 3-site consortium stays COORDINATE_CONSENSUS.
        honest_sites = [[5, 4, 0, 0, 0, 0], [5, 3, 1, 0, 0, 0], [4, 4, 0, 1, 0, 0]]
        hon_res = self.kmc.evaluate_consensus_arbitration(honest_sites)
        self.assertEqual(hon_res["verdict"], "COORDINATE_CONSENSUS")
        self.assertGreater(hon_res["coherence_c_k"], 0.92)
        json.dumps(hon_res, allow_nan=False)

    def test_echo_chamber_and_rogue_node_detection(self) -> None:
        cloned = [[0.85, 0.10, 0.05]] * 3
        echo = self.kmc.evaluate_consensus_arbitration(cloned)
        self.assertEqual(echo["verdict"], "ECHO_CHAMBER_WARNING")
        self.assertEqual(echo["reason"], "zero_diversity_echo_chamber")
        self.assertTrue(echo["echo_chamber_detected"])
        self.assertFalse(echo["abstained"])
        self.assertLessEqual(echo["d_k_disagreement"], 1e-9)
        self.assertEqual(echo["coherence_c_k"], 1.0)

        # World 3 rogue contaminated consortium detects outlier index 2 and abstains.
        rogue_sites = [[5, 4, 0, 0, 0, 0], [5, 3, 1, 0, 0, 0], [0, 0, 1, 4, 4, 4]]
        rog = self.kmc.evaluate_consensus_arbitration(rogue_sites)
        self.assertEqual(rog["verdict"], "ABSTAIN")
        self.assertEqual(rog["reason"], "rogue_or_bluff_low_coherence")
        self.assertTrue(rog["abstained"])
        self.assertTrue(rog["rogue_node_detected"])
        self.assertLess(rog["coherence_c_k"], 0.45)
        self.assertEqual(rog["rogue_agent_indices"], [2])

        # Orthogonal bluff on 3-simplex also triggers low-coherence abstention.
        orth = self.kmc.evaluate_consensus_arbitration([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(orth["verdict"], "ABSTAIN")
        self.assertTrue(orth["rogue_node_detected"])
        self.assertEqual(orth["rogue_agent_indices"], [0, 1])

    def test_edge_cases_and_weight_validation(self) -> None:
        # K = 0 empty input
        empty = self.kmc.evaluate_consensus_arbitration([])
        self.assertEqual(empty["verdict"], "ABSTAIN")
        self.assertEqual(empty["reason"], "empty_or_zero_vectors")
        self.assertTrue(empty["abstained"])
        self.assertTrue(empty["bluff_detected"])

        # 1D degenerate simplex
        d1 = self.kmc.evaluate_consensus_arbitration([[2.0], [5.0]])
        self.assertEqual(d1["verdict"], "ABSTAIN")
        self.assertEqual(d1["reason"], "degenerate_1d_simplex")
        self.assertTrue(d1["bluff_detected"])

        # Uniform uninformative consensus MUST precede echo-chamber check
        unif = self.kmc.evaluate_consensus_arbitration([[0.5, 0.5], [0.5, 0.5]])
        self.assertEqual(unif["verdict"], "ABSTAIN")
        self.assertEqual(unif["reason"], "uniform_uninformative_consensus")
        self.assertTrue(unif["bluff_detected"])
        self.assertFalse(unif["echo_chamber_detected"])

        # K = 1 insufficient quorum
        single = self.kmc.evaluate_consensus_arbitration([[0.9, 0.1]])
        self.assertEqual(single["verdict"], "ABSTAIN")
        self.assertEqual(single["reason"], "insufficient_quorum")
        self.assertFalse(single["quorum_met"])

        # All zero vectors
        all_zero = self.kmc.evaluate_consensus_arbitration([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
        self.assertEqual(all_zero["verdict"], "ABSTAIN")
        self.assertEqual(all_zero["reason"], "empty_or_zero_vectors")
        self.assertEqual(all_zero["zero_vector_agents"], [0, 1])

        # One zero vector + one sharp -> effective_k = 1 < min_agents=2
        half_zero = self.kmc.evaluate_consensus_arbitration([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertEqual(half_zero["verdict"], "ABSTAIN")
        self.assertEqual(half_zero["reason"], "insufficient_quorum")
        self.assertEqual(half_zero["zero_vector_agents"], [0])

        # Positive unnormalized weights normalize cleanly onto convex simplex
        weighted = self.kmc.evaluate_consensus_arbitration(
            [[0.9, 0.1, 0.0], [0.1, 0.9, 0.0]],
            weights=[2.0, 6.0],
        )
        self.assertEqual(weighted["verdict"], "COORDINATE_CONSENSUS")
        self.assertAlmostEqual(weighted["consensus_p_bar"][0], 0.3, places=6)
        self.assertAlmostEqual(weighted["consensus_p_bar"][1], 0.7, places=6)

        # Invalid weights raise ValueError
        for bad_w in ([-1.0, 2.0], [0.0, 0.0], [float("nan"), 1.0], [1.0]):
            with self.assertRaises(ValueError):
                self.kmc.evaluate_consensus_arbitration([[0.8, 0.2], [0.6, 0.4]], weights=bad_w)

        with self.assertRaises(ValueError):
            self.kmc.kloster_ensemble_decomposition([])


class TestCollaborationBridgeTheorem15(unittest.TestCase):
    def test_default_proof_preserved_and_peer_abstention_gated(self) -> None:
        bridge = CollaborationBridge(_FakeGateway())
        evidence = [{"citation": "README.md:5", "content": "Zoe evidence", "kind": "document", "score": 2.0, "coverage": 0.5}]
        with tempfile.TemporaryDirectory(prefix="zoe_collab_b5_") as tmp:
            res = bridge.consult("Evaluate this research", evidence)
            self.assertEqual(res["operational_metacognition"]["breadth"]["accessible_count"], 2)
            self.assertEqual(res["operational_metacognition"]["selected_action"], "consult_agent")
            cons = res["operational_metacognition"]["theorem15_consensus"]
            self.assertEqual(cons["verdict"], "COORDINATE_CONSENSUS")
            json.dumps(res["operational_metacognition"], allow_nan=False)
            proof_path = Path(tmp) / "proof.json"
            bridge.save_proof(proof_path)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            verified = verify_collaboration_proof(proof)
            self.assertTrue(verified["verified"])

        # Rogue/bluff peer distribution triggers ABSTAIN and disables consult_agent.
        rogue_eval = bridge.evaluate(
            "Evaluate conflicting peer predictions",
            evidence,
            peer_distributions=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        )
        self.assertFalse(rogue_eval["consult_agent"])
        self.assertEqual(rogue_eval["measurement"]["selected_action"], "abstain")
        self.assertTrue(rogue_eval["measurement"]["abstained"])
        self.assertEqual(rogue_eval["measurement"]["theorem15_consensus"]["verdict"], "ABSTAIN")

        # Echo-chamber peer distribution flags warning.
        echo_eval = bridge.evaluate(
            "Evaluate cloned peer predictions",
            evidence,
            peer_distributions=[[0.85, 0.10, 0.05], [0.85, 0.10, 0.05]],
        )
        self.assertTrue(echo_eval["consult_agent"])
        self.assertTrue(echo_eval["measurement"]["echo_chamber_warning"])
        self.assertEqual(echo_eval["measurement"]["theorem15_consensus"]["verdict"], "ECHO_CHAMBER_WARNING")

        # Standalone fallback works identically when guiai package is absent.
        with mock.patch.dict(sys.modules, {"guiai": None, "guiai.gem": None, "guiai.gem.kloster_multi_agent_consensus": None}):
            standalone_rogue = bridge.evaluate(
                "Evaluate conflicting peers standalone",
                evidence,
                peer_distributions=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            )
        self.assertFalse(standalone_rogue["consult_agent"])
        self.assertEqual(standalone_rogue["measurement"]["selected_action"], "abstain")


class TestStemLayeringTeamworkQuorum(unittest.TestCase):
    def test_pro_teamwork_quorum_and_abstention(self) -> None:
        pro_dec = route_stem(
            "architect and refactor multi-file AST verification invariant across kernel modules",
            files_count=5,
            multi_file=True,
        )
        self.assertEqual(pro_dec.selected_tier, "pro")
        self.assertTrue(pro_dec.teamwork_recommended)
        self.assertEqual(pro_dec.thinking_level, "xhigh")
        self.assertIsNotNone(pro_dec.quorum_arbitration)
        self.assertEqual(pro_dec.quorum_arbitration["verdict"], "COORDINATE_CONSENSUS")
        self.assertFalse(pro_dec.quorum_arbitration["abstention_applied"])
        json.dumps(pro_dec.to_dict(), allow_nan=False)

        # Offline/non-pro paths keep quorum_arbitration None and zero cloud tokens.
        priv_dec = route_stem(
            "architect and refactor multi-file AST verification invariant",
            offline_only=True,
            privacy_sensitive=True,
            files_count=5,
            multi_file=True,
            local_qwen_available=True,
        )
        self.assertFalse(priv_dec.teamwork_recommended)
        self.assertIsNone(priv_dec.quorum_arbitration)
        self.assertEqual(priv_dec.constitutional["cloud_tokens_used"], 0)

        # Rogue and echo-chamber explicit quorum distributions suppress teamwork_recommended.
        for bad_quorum, expected_verdict in (
            ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], "ABSTAIN"),
            ([[0.85, 0.10, 0.05]] * 3, "ECHO_CHAMBER_WARNING"),
        ):
            gated = route_stem(
                "architect and refactor multi-file AST verification invariant",
                files_count=5,
                multi_file=True,
                quorum_distributions=bad_quorum,
            )
            self.assertFalse(gated.teamwork_recommended)
            self.assertIsNotNone(gated.quorum_arbitration)
            self.assertTrue(gated.quorum_arbitration["abstention_applied"])
            self.assertEqual(gated.quorum_arbitration["verdict"], expected_verdict)
            self.assertAlmostEqual(sum(gated.probabilities.values()), 1.0, places=5)

        # Standalone fallback works cleanly when guiai package is absent.
        with mock.patch.dict(sys.modules, {"guiai": None, "guiai.gem": None, "guiai.gem.kloster_multi_agent_consensus": None}):
            standalone_dec = route_stem(
                "architect and refactor multi-file AST verification invariant",
                files_count=5,
                multi_file=True,
                quorum_distributions=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            )
        self.assertFalse(standalone_dec.teamwork_recommended)
        self.assertTrue(standalone_dec.quorum_arbitration["abstention_applied"])


class TestZoeOSMindBridge5(unittest.TestCase):
    def test_process_turn_consensus_and_abstention_guards(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe_os_mind_b5_") as tmp:
            mind = ZoeOSMind(REPO_ROOT, Path(tmp) / "state")
            self.assertFalse(mind.state["constitution"]["cure_claim"])
            self.assertFalse(mind.state["constitution"]["sentience_claimed"])
            self.assertFalse(mind.state["constitution"]["clinical_action_authorized"])

            # Honest multi-engine turn keeps COORDINATE_MULTI_ENGINE with Theorem 15 telemetry.
            honest = mind.process_turn(
                "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
                offline_only=True,
            )
            self.assertEqual(honest["decision"], "COORDINATE_MULTI_ENGINE")
            cons = honest["theorem15_consensus"]
            self.assertEqual(cons["verdict"], "COORDINATE_CONSENSUS")
            self.assertGreater(cons["d_k_disagreement"], 0.0)
            self.assertGreaterEqual(cons["coherence_c_k"], 0.45)
            self.assertGreaterEqual(cons["contracted_a_tau"], 1)

            # Rogue 3-agent committee gates to ABSTAIN_CONSENSUS_GUARD (C_K < 0.45).
            n_eng = len(mind.registry.components)
            p_a = [0.0] * n_eng
            p_b = [0.0] * n_eng
            p_c = [0.0] * n_eng
            p_a[0] = 1.0
            p_b[1] = 1.0
            p_c[2] = 1.0
            rogue_turn = mind.process_turn(
                "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
                offline_only=True,
                committee_distributions=[p_a, p_b, p_c],
            )
            self.assertEqual(rogue_turn["decision"], "ABSTAIN_CONSENSUS_GUARD")
            self.assertTrue(rogue_turn["theorem15_consensus"]["abstention_applied"])
            self.assertTrue(rogue_turn["theorem15_consensus"]["rogue_node_detected"])

            # Uniform uninformative bluff committee also gates to ABSTAIN_CONSENSUS_GUARD.
            unif_p = [1.0 / n_eng] * n_eng
            bluff_turn = mind.process_turn(
                "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
                offline_only=True,
                committee_distributions=[unif_p, unif_p],
            )
            self.assertEqual(bluff_turn["decision"], "ABSTAIN_CONSENSUS_GUARD")
            self.assertTrue(bluff_turn["theorem15_consensus"]["bluff_detected"])

            # Echo-chamber warns by default and abstains when abstain_on_echo_chamber=True.
            p_clone = [0.60 if i == 0 else (0.30 if i == 1 else 0.10 / (n_eng - 2)) for i in range(n_eng)]
            echo_warn = mind.process_turn(
                "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
                offline_only=True,
                committee_distributions=[p_clone, p_clone, p_clone],
            )
            self.assertEqual(echo_warn["decision"], "COORDINATE_MULTI_ENGINE")
            self.assertTrue(echo_warn["theorem15_consensus"]["echo_chamber_detected"])

            echo_abstain = mind.process_turn(
                "Compare CERN collider waveform pulses with Dorothy brain gamma rhythms",
                offline_only=True,
                committee_distributions=[p_clone, p_clone, p_clone],
                abstain_on_echo_chamber=True,
            )
            self.assertEqual(echo_abstain["decision"], "ABSTAIN_CONSENSUS_GUARD")
            self.assertTrue(echo_abstain["theorem15_consensus"]["abstention_applied"])

            # Privacy firewall remains intact.
            blocked = mind.process_turn(
                "Sync private vault",
                privacy_sensitive=True,
                offline_only=True,
                payload_metadata={"source": "vault", "contains_secret_pin": True, "destination": "cloud"},
            )
            self.assertTrue(blocked["blocked"])
            self.assertEqual(blocked["decision"], "BLOCK_PRIVACY_EXFILTRATION")


class TestZoeOSVerificationSuiteIngestion(unittest.TestCase):
    def test_full_suite_scene_and_constitutional_invariants(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe_os_suite_b5_") as tmp:
            report = run_zoe_os_verification_suite(REPO_ROOT, Path(tmp) / "state")

        self.assertTrue(report["all_verified"])
        self.assertLessEqual(len(report["checks"]), 9)
        self.assertTrue(report["checks"]["theorem15_consensus_and_abstention"])
        self.assertTrue(report["checks"]["theorems_12_to_15_and_c27_c28_verified"])

        expected_worlds = {
            "world5_kloster_theory",
            "world5_theorem12_referee",
            "world5_theorem13_stopping",
            "world5_theorem14_optics",
            "world5_theorem15_consensus",
            "world6_c27_botanical_atlas",
            "world6_c28_pharmacophore_spatial",
        }
        snap = report["snapshot"]
        self.assertTrue(expected_worlds.issubset(set(snap["world_telemetry"])))
        self.assertTrue(snap["ledger_integrity"]["intact"])
        for wid in expected_worlds - {"world5_kloster_theory"}:
            self.assertTrue(report["ingested_evidence_reports"][wid]["verified"])
            self.assertTrue(snap["world_telemetry"][wid]["verified"])

        # Constitutional invariants
        const = snap["constitution"]
        self.assertFalse(const["sentience_claimed"])
        self.assertFalse(const["l5_agi_qualified"])
        self.assertFalse(const["zoe_clone_claimed"])
        self.assertFalse(const["clinical_action_authorized"])
        self.assertFalse(const["cure_claim"])
        self.assertEqual(const["cloud_tokens_used"], 0)

        # GEM Scene & VDI compatibility (inside_canvas constraint with 9 checks)
        if str(GUIAI_DIR) not in sys.path:
            sys.path.insert(0, str(GUIAI_DIR))
        from guiai.gem.geometry import verify
        from guiai.gem.runner import verify_vdi
        from guiai.gem.zoe_os import zoe_os_scene

        scene = zoe_os_scene(report)
        self.assertTrue(verify(scene).passed)
        self.assertTrue(verify_vdi(scene).passed)

    def test_missing_evidence_reports_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe_os_missing_ev_") as tmp:
            tmp_root = Path(tmp) / "fake_zoe"
            tmp_root.mkdir()
            # Symlink guiai-lab and components so ComponentRegistry resolves 17 engines,
            # while leaving evidence/ completely absent.
            (tmp_root / "guiai-lab").symlink_to(GUIAI_DIR)
            (tmp_root / "components").symlink_to(REPO_ROOT / "components")
            (tmp_root / "evidence").mkdir()
            report = run_zoe_os_verification_suite(tmp_root, Path(tmp) / "state")

        self.assertFalse(report["all_verified"])
        self.assertFalse(report["checks"]["theorems_12_to_15_and_c27_c28_verified"])
        self.assertFalse(report["checks"]["world5_telemetry_cross_pollinated"])
        self.assertTrue(report["checks"]["theorem15_consensus_and_abstention"])
        self.assertFalse(report["ingested_evidence_reports"]["world5_theorem15_consensus"]["present"])
        self.assertFalse(report["ingested_evidence_reports"]["world5_theorem15_consensus"]["verified"])


if __name__ == "__main__":
    unittest.main()

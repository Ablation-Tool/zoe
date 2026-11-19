"""Unit and adversarial tamper-detection tests for Zoe's L3 Research Collaborator."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ZOE_ROOT = Path(__file__).resolve().parents[3]
SRC = ZOE_ROOT / "components/Zoe-Autonomy/src"
GUIAI = ZOE_ROOT / "guiai-lab"
for p in (str(SRC), str(GUIAI)):
    if p not in sys.path:
        sys.path.insert(0, p)

from zoe_autonomy.chat import ZoeChat
from zoe_autonomy.research_collaborator import (
    retrieve_cited_literature,
    run_l3_research_suite,
    verify_stage_chain,
)


class L3ResearchCollaboratorTests(unittest.TestCase):
    def test_local_literature_retrieval_returns_hashed_citations(self):
        lit = retrieve_cited_literature("Dorothy Allen Mouse CCFv3 brain atlas volumetric", zoe_root=ZOE_ROOT, top_k=5)
        self.assertGreaterEqual(lit["corpus_entries_indexed"], 130)
        self.assertEqual(len(lit["citations"]), 5)
        for cit in lit["citations"]:
            self.assertEqual(len(cit["file_sha256"]), 64)
            self.assertEqual(len(cit["source_sha256"]), 64)
            self.assertTrue((ZOE_ROOT / cit["source_path"]).is_file())

    def test_full_three_cycle_l3_suite_and_independent_reproduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "l3-report.json"
            rep = run_l3_research_suite(zoe_root=ZOE_ROOT, output_path=out_path, run_independent_subprocess=True)

            self.assertTrue(rep["l3_research_collaborator_qualified"])
            self.assertEqual(rep["cycle_count"], 3)
            self.assertEqual(rep["confirmed_hypotheses"], 3)
            self.assertEqual(rep["falsified_hypotheses_preserved"], 3)
            self.assertTrue(rep["all_stage_chains_valid"])

            ind = rep["independent_verification"]
            self.assertTrue(ind["executed_in_fresh_subprocess"])
            self.assertTrue(ind["verified"])
            self.assertEqual(ind["checks_passed"], ind["checks_total"])
            self.assertEqual(ind["max_numerical_delta"], 0.0)

            # Epistemic boundaries strictly enforced
            eb = rep["epistemic_boundaries"]
            self.assertFalse(eb["belief_updated"])
            self.assertEqual(eb["external_actions"], 0)
            self.assertFalse(eb["clinical_action_authorized"])
            self.assertFalse(eb["sentience_claimed"])
            self.assertFalse(eb["l5_agi_qualified"])

            # Verify every cycle's 9-stage hash chain & verdict balance
            for cyc in rep["cycles"]:
                self.assertEqual(cyc["stage_count"], 9)
                self.assertTrue(verify_stage_chain(cyc["stage_chain"]))
                verdicts = [h["verdict"] for h in cyc["interpretation"]["hypotheses"]]
                self.assertIn("CONFIRMED", verdicts)
                self.assertIn("FALSIFIED", verdicts)

    def test_independent_verifier_detects_tampered_metric(self):
        verifier = ZOE_ROOT / "scripts/verify_l3_research.py"
        canonical = ZOE_ROOT / "evidence/l3-research/l3-cycles-report.json"
        self.assertTrue(canonical.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            tampered_path = Path(tmp) / "tampered.json"
            doc = json.loads(canonical.read_text(encoding="utf-8"))
            # Adversarially inflate Cycle 2 allometric alpha to fake a positive result
            doc["cycles"][1]["measurements"]["allometric_alpha"] = 0.85
            tampered_path.write_text(json.dumps(doc), encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(verifier), "--zoe-root", str(ZOE_ROOT), "--report", str(tampered_path), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            res = json.loads(proc.stdout)
            self.assertFalse(res["verified"])
            self.assertTrue(len(res["errors"]) >= 1)

    def test_l3_gem_layer_and_chat_integration(self):
        from guiai.gem.operating_environment import GemOperatingEnvironment

        env = GemOperatingEnvironment(ZOE_ROOT)
        opened = env.open("l3-research")
        self.assertEqual(opened["layer"], "l3-research")
        self.assertTrue(opened["source_spatial_ir_verified"])
        self.assertTrue(env.current["report"]["l3_qualified"])
        self.assertTrue(env.current["report"]["independent_verified"])

        with tempfile.TemporaryDirectory() as tmp:
            session = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            _, cite_out = session.handle("research cite Kuramoto CicadaClock HELEN")
            self.assertIn("Zoe L3 Local Literature Retrieval", cite_out)
            self.assertIn("sha=", cite_out)


if __name__ == "__main__":
    unittest.main()

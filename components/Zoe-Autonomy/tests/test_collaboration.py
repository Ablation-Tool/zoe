from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from zoe_autonomy.chat import ZoeChat
from zoe_autonomy.collaboration import CollaborationBridge, verify_collaboration_proof


ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))


class FakeGateway:
    def __init__(self):
        self.prompts = []

    def list(self):
        return [{"id": "kimi", "enabled": True, "owner": True, "executable_available": True}]

    def invoke(self, identifier, prompt, timeout=60):
        self.prompts.append(prompt)
        return {
            "id": identifier,
            "succeeded": True,
            "content": "Agent synthesis from the shared context.",
            "audit_hash": "mock-audit",
        }


@unittest.skipUnless(ZOE_ROOT.is_dir() and (ZOE_ROOT / "guiai-lab/docs/GEM-OS.md").is_file(), "set ZOE_ROOT to a unified Zoe checkout")
class CollaborationCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="zoe-collaboration-test-")
        self.gateway = FakeGateway()
        self.bridge = CollaborationBridge(self.gateway)
        self.chat = ZoeChat(ZOE_ROOT, Path(self.temporary.name) / "chat")
        self.chat.collaboration_bridge = self.bridge

    def tearDown(self):
        self.temporary.cleanup()

    def test_bounded_shared_context_and_gem_selection(self):
        session = Path(self.temporary.name) / "lab"
        session.mkdir()
        (session / "state.json").write_text(json.dumps({
            "revision": 7,
            "selected_id": "artifact:research",
            "root_id": "artifact:root",
            "target_kind": "directory",
            "selected": {"id": "artifact:research", "label": "Research"},
        }), encoding="utf-8")
        evidence = [{"citation": "README.md:5", "content": "Zoe's research mission", "kind": "document", "score": 2.0, "coverage": 0.5}]
        with mock.patch.dict(os.environ, {"GEM_SESSION": str(session)}):
            first = self.bridge.consult("Evaluate this research", evidence)
            second = self.bridge.consult("Continue with the next step", evidence)
        self.assertTrue(first["gem_context_shared"])
        self.assertEqual(first["shared_turns"], 1)
        self.assertFalse(first["persistent_transcript"])
        self.assertEqual(first["operational_metacognition"]["breadth"]["accessible_count"], 2)
        self.assertEqual(first["operational_metacognition"]["selected_action"], "consult_agent")
        prompt = json.loads(self.gateway.prompts[0])
        self.assertEqual(prompt["zoe_operational_metacognition"]["breadth"]["accessible_count"], 2)
        self.assertEqual(prompt["current_question"], "Evaluate this research")
        self.assertEqual(prompt["gem_selection"]["selected_id"], "artifact:research")
        self.assertEqual(prompt["zoe_local_evidence"][0]["citation"], "README.md:5")
        continued = json.loads(self.gateway.prompts[1])
        self.assertEqual(continued["recent_shared_turns"][0]["user"], "Evaluate this research")
        self.assertEqual(second["shared_turns"], 2)
        self.assertEqual(self.bridge.clear(), 2)
        self.assertEqual(self.bridge.shared_turns, [])

    def test_zoe_enters_exits_and_preserves_stop_boundary(self):
        self.chat.collaboration_enabled = True
        response = self.chat.handle("what is a zqfrangible inverse owlet?")[1]
        self.assertIn("Zoe · local evidence", response)
        self.assertIn("Embedded AI agent · kimi · consulted by Zoe", response)
        self.assertIn("Agent synthesis from the shared context", response)
        self.assertIn("persistent transcript=False", response)
        self.assertEqual(len(self.gateway.prompts), 1)
        direct = self.chat.handle("agent ask what is PALA?")[1]
        self.assertIn("PALA", direct)
        self.assertIn("Aτ(action)=", direct)
        self.assertIn("CAPABILITY-ATLAS.md", self.gateway.prompts[-1])
        proof_path = Path(self.temporary.name) / "proof.json"
        saved = self.chat.handle(f"agent proof {proof_path}")[1]
        self.assertIn("proof_sha256=", saved)
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        verification = verify_collaboration_proof(proof)
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["selected_action"], "consult_agent")
        self.assertIn("could not complete", self.chat.handle(f"agent proof {proof_path}")[1])
        proof["operational_metacognition"]["breadth"]["accessible_count"] += 1
        with self.assertRaises(ValueError):
            verify_collaboration_proof(proof)
        self.assertIn("Automatic agent collaboration is off", self.chat.handle("agent off")[1])
        before = len(self.gateway.prompts)
        local = self.chat.handle("what is a zqfrangible inverse owlet?")[1]
        self.assertIn("do not have enough indexed evidence", local)
        self.assertEqual(len(self.gateway.prompts), before)
        self.assertIn("Zoe may consult", self.chat.handle("agent on")[1])
        self.chat.handle("stop")
        stopped = self.chat.handle("agent ask hello")[1]
        self.assertIn("agent collaboration is stopped", stopped)
        self.assertEqual(len(self.gateway.prompts), before)
        self.assertFalse((Path(self.temporary.name) / "chat" / "events.jsonl").exists())
        self.assertFalse((Path(self.temporary.name) / "chat" / "metacognition.json").exists())

    def test_status_and_agent_selection_do_not_invoke_a_model(self):
        status = self.chat.handle("agent status")[1]
        self.assertIn("user ↔ Zoe ↔ kimi", status)
        self.assertIn("available=True", status)
        self.assertIn("persistent transcript=False", status)
        selected = self.chat.handle("agent use kimi")[1]
        self.assertIn("owner-connected agent 'kimi'", selected)
        self.assertEqual(self.gateway.prompts, [])


if __name__ == "__main__":
    unittest.main()

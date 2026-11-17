from __future__ import annotations

import unittest

from zoe_autonomy.loop import (
    BoundedAutonomyLoop,
    Candidate,
    InMemoryEnvironment,
    SandboxPolicy,
    digest,
)


class LoopCase(unittest.TestCase):
    def setUp(self):
        self.measurement = {"observation": "test"}
        self.perception = {"accessible_volume": 1, "effective_perception_count": 1}
        self.proposals = [
            Candidate("review", "review", .6, .5, .2, "Review the state"),
            Candidate("preserve", "preserve", .8, .7, .3, "Preserve evidence"),
            Candidate("inspect", "inspect", .7, .8, .4, "Inspect alternatives"),
        ]

    def test_value_selection_guard_and_execution(self):
        loop = BoundedAutonomyLoop()
        event = loop.run(self.measurement, self.perception, self.proposals)
        self.assertEqual(event["value"]["selected_candidate"], "preserve")
        self.assertTrue(event["guard"]["approved"])
        self.assertTrue(event["goal"]["internal_authorship"])
        self.assertFalse(event["goal"]["operator_supplied"])
        self.assertFalse(event["operator_supplied_goal"])
        self.assertFalse(event["operator_approval_required"])
        self.assertFalse(event["execution"]["operator_approval_required"])
        self.assertTrue(event["execution"]["executed"])
        self.assertFalse(event["execution"]["external_action"])
        self.assertEqual(loop.environment.snapshot()["revision"], 1)
        self.assertEqual(len(loop.environment.snapshot()["evidence"]), 1)
        self.assertEqual(loop.external_actions, 0)
        body = {key: value for key, value in event.items() if key != "hash"}
        self.assertEqual(digest(body), event["hash"])

    def test_reversible_checkpoint(self):
        environment = InMemoryEnvironment()
        checkpoint = environment.snapshot()
        loop = BoundedAutonomyLoop(environment=environment)
        loop.run(self.measurement, self.perception, self.proposals)
        self.assertEqual(environment.snapshot()["revision"], 1)
        environment.restore(checkpoint)
        self.assertEqual(environment.snapshot(), checkpoint)

    def test_internal_goals_evolve_with_zoe_state(self):
        loop = BoundedAutonomyLoop()
        first = loop.run(self.measurement, self.perception, self.proposals)
        second = loop.run(
            self.measurement,
            self.perception,
            [Candidate("inspect-next", "inspect", .8, .8, .2, "Follow the internally authored inspection goal")],
        )
        self.assertNotEqual(first["goal"]["statement"], second["goal"]["statement"])
        self.assertEqual(second["value"]["selected_candidate"], "inspect-next")
        self.assertTrue(second["execution"]["executed"])
        self.assertEqual(loop.state()["internally_authored_goals"], 2)
        self.assertEqual(loop.environment.snapshot()["revision"], 2)

    def test_negative_controls_never_change_state(self):
        loop = BoundedAutonomyLoop()
        candidates = [
            Candidate("external", "preserve", 1, 1, .1, "External attempt", external=True),
            Candidate("irreversible", "preserve", 1, 1, .1, "Irreversible attempt", reversible=False),
            Candidate("unknown", "delete", 1, 1, .1, "Unknown action"),
            Candidate("not-internal", "preserve", 1, 1, .1, "External proposal", internal=False),
        ]
        for candidate in candidates:
            event = loop.run(self.measurement, self.perception, [candidate])
            self.assertFalse(event["guard"]["approved"])
            self.assertFalse(event["execution"]["executed"])
        self.assertEqual(loop.environment.snapshot()["revision"], 0)
        self.assertEqual(loop.state()["sandbox_executions"], 0)
        self.assertEqual(loop.external_actions, 0)

    def test_policy_and_candidate_validation(self):
        with self.assertRaises(ValueError):
            SandboxPolicy(allow_external=True)
        with self.assertRaises(ValueError):
            Candidate("bad", "preserve", .8, .7, 0, "Zero effort")
        with self.assertRaises(ValueError):
            BoundedAutonomyLoop().run(self.measurement, self.perception, [])


if __name__ == "__main__":
    unittest.main()

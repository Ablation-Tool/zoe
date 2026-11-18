from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def text(value, label, maximum=256):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must contain 1-{maximum} characters")
    return value.strip()


def unit(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{label} must be a finite number in [0, 1]")
    return float(value)


def _belief_document(document):
    if document is None:
        return None
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("belief_update must use schema_version 1")
    if any(not isinstance(document.get(key), dict) for key in ("previous", "current", "evidence")):
        raise ValueError("belief_update requires previous, current, and evidence objects")
    changed = document.get("changed")
    if not isinstance(changed, bool) or changed != (document["previous"] != document["current"]):
        raise ValueError("belief_update.changed must match the previous and current model states")
    return deepcopy(document)


@dataclass(frozen=True)
class Candidate:
    identifier: str
    action: str
    decision_value: float
    information_gain: float
    effort: float
    rationale: str
    internal: bool = True
    reversible: bool = True
    external: bool = False
    operation: dict | None = None

    def __post_init__(self):
        text(self.identifier, "candidate identifier", 128)
        text(self.action, "candidate action", 64)
        unit(self.decision_value, "decision value")
        unit(self.information_gain, "information gain")
        if isinstance(self.effort, bool) or not isinstance(self.effort, (int, float)) or not math.isfinite(self.effort) or not 0 < self.effort <= 1000:
            raise ValueError("effort must be in (0, 1000]")
        text(self.rationale, "candidate rationale", 2000)
        for name in ("internal", "reversible", "external"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        if self.operation is not None:
            if not isinstance(self.operation, dict):
                raise ValueError("actuation operation must be a mapping")
            canonical(self.operation)

    @property
    def utility(self):
        return self.decision_value * self.information_gain / self.effort

    def document(self):
        return {
            "id": self.identifier,
            "action": self.action,
            "decision_value": self.decision_value,
            "expected_information_gain": self.information_gain,
            "effort": self.effort,
            "utility": self.utility,
            "rationale": self.rationale,
            "internal_proposal": self.internal,
            "reversible": self.reversible,
            "external": self.external,
            "actuation_operation": deepcopy(self.operation),
        }


@dataclass(frozen=True)
class SandboxPolicy:
    authorization_id: str = "zoe-autonomy-sandbox-v1"
    allowed_actions: tuple = ("preserve", "inspect", "review", "observe")
    reversible_only: bool = True
    allow_external: bool = False
    actuation: object | None = None

    def __post_init__(self):
        text(self.authorization_id, "authorization identifier", 128)
        if not isinstance(self.allowed_actions, tuple) or not 1 <= len(self.allowed_actions) <= 16:
            raise ValueError("allowed_actions must contain 1-16 actions")
        if len(set(self.allowed_actions)) != len(self.allowed_actions):
            raise ValueError("allowed_actions must be unique")
        for action in self.allowed_actions:
            text(action, "allowed action", 64)
        if not isinstance(self.reversible_only, bool) or not isinstance(self.allow_external, bool):
            raise ValueError("sandbox policy flags must be booleans")
        if self.allow_external:
            if self.actuation is None or not callable(getattr(self.actuation, "enabled", None)) or not callable(getattr(self.actuation, "execute", None)):
                raise ValueError("external actuation requires an explicit owner-granted actuation policy")

    def guard(self, candidate, goal):
        reasons = []
        if not goal.get("internal_authorship") or goal.get("operator_supplied"):
            reasons.append("goal is not internally authored")
        if not candidate.internal:
            reasons.append("proposal is not internally generated")
        if candidate.action not in self.allowed_actions and not candidate.external:
            reasons.append("action is not in the sandbox allowlist")
        if candidate.external:
            if not self.allow_external or self.actuation is None:
                reasons.append("external actions require an explicit owner actuation grant")
            elif not isinstance(candidate.operation, dict):
                reasons.append("external action has no actuation operation")
            else:
                kind = candidate.operation.get("kind")
                if not self.actuation.enabled(kind):
                    reasons.append(f"owner grant or current emergency stop does not enable {kind} actuation")
        if self.reversible_only and not candidate.reversible:
            reasons.append("irreversible actions are forbidden")
        return {
            "approved": not reasons,
            "alpha": int(not reasons),
            "authorization_id": self.authorization_id if not reasons else None,
            "reasons": reasons,
            "goal": deepcopy(goal),
            "policy": self.authorization_id,
        }


class InMemoryEnvironment:
    def __init__(self):
        self._state = {
            "revision": 0,
            "observations": [],
            "evidence": [],
            "inspections": [],
            "reviews": [],
        }

    def snapshot(self):
        return deepcopy(self._state)

    def restore(self, snapshot):
        if not isinstance(snapshot, dict) or set(snapshot) != set(self._state):
            raise ValueError("invalid sandbox checkpoint")
        if isinstance(snapshot["revision"], bool) or not isinstance(snapshot["revision"], int) or snapshot["revision"] < 0:
            raise ValueError("invalid sandbox revision")
        for name in ("observations", "evidence", "inspections", "reviews"):
            if not isinstance(snapshot[name], list):
                raise ValueError("invalid sandbox checkpoint collection")
        canonical(snapshot)
        self._state = deepcopy(snapshot)

    def apply(self, candidate, measurement):
        before = self.snapshot()
        revision = before["revision"] + 1
        record = {
            "revision": revision,
            "action": candidate.action,
            "candidate_id": candidate.identifier,
            "measurement_sha256": digest(measurement),
        }
        collection = {
            "preserve": "evidence",
            "inspect": "inspections",
            "review": "reviews",
            "observe": "observations",
        }.get(candidate.action)
        if collection is None:
            raise ValueError("no in-memory transition exists for the selected action")
        self._state[collection].append(record)
        self._state["revision"] = revision
        return {"before": before, "after": self.snapshot(), "transition": record}


class BoundedAutonomyLoop:
    def __init__(self, policy=None, environment=None):
        self.policy = policy or SandboxPolicy()
        self.environment = environment or InMemoryEnvironment()
        self.events = []
        self.external_actions = 0

    def goal_action(self):
        state = self.environment.snapshot()
        if not state["evidence"]:
            return "preserve"
        if not state["inspections"]:
            return "inspect"
        return "review"

    def author_goal(self, measurement):
        state = self.environment.snapshot()
        action = self.goal_action()
        if action == "preserve":
            statement = "Establish an evidence record from the current observation before broader exploration."
            rationale = "The current internal state contains no preserved evidence."
        elif action == "inspect":
            statement = "Use the preserved evidence to inspect alternatives and extend the current internal model."
            rationale = "Evidence exists, but no internally executed inspection has yet been recorded."
        else:
            statement = "Review and refine the existing evidence and inspection state without external direction."
            rationale = "The internal evidence and inspection records support a review-oriented continuation."
        goal = {
            "id": f"goal-{len(self.events) + 1}",
            "statement": statement,
            "rationale": rationale,
            "authorship": "Zoe internal state assessment",
            "internal_authorship": True,
            "operator_supplied": False,
            "state_basis": {
                "revision": state["revision"],
                "evidence_records": len(state["evidence"]),
                "inspection_records": len(state["inspections"]),
                "review_records": len(state["reviews"]),
            },
            "measurement_sha256": digest(measurement),
        }
        goal["sha256"] = digest(goal)
        return goal

    def run(self, measurement, perception, proposals, goal_directed=False, belief_update=None):
        if not isinstance(measurement, dict) or not isinstance(perception, dict):
            raise ValueError("measurement and perception records are required")
        if not isinstance(goal_directed, bool):
            raise ValueError("goal_directed must be a boolean")
        canonical(measurement)
        canonical(perception)
        belief = _belief_document(belief_update)
        if not isinstance(proposals, (list, tuple)) or not 1 <= len(proposals) <= 32:
            raise ValueError("the proposal stage requires 1-32 candidates")
        if any(not isinstance(candidate, Candidate) for candidate in proposals):
            raise ValueError("every proposal must be a Candidate")
        goal = self.author_goal(measurement)
        ranked = sorted(proposals, key=lambda candidate: (-candidate.utility, candidate.identifier))
        if goal_directed:
            target = self.goal_action()
            ranked = [candidate for candidate in ranked if candidate.action == target]
            if not ranked:
                raise ValueError(f"goal-directed proposals must include the {target} action")
            goal["target_action"] = target
        selected = ranked[0]
        guard = self.policy.guard(selected, goal)
        transition = None
        if guard["approved"]:
            if selected.external:
                transition = self.policy.actuation.execute(selected.operation, measurement)
            else:
                transition = self.environment.apply(selected, measurement)
        event = {
            "sequence": len(self.events) + 1,
            "protocol": "Execute_alpha o Guard_G,Pi o Value_U o Propose_pi o Perceive_tau,delta o M",
            "measurement": deepcopy(measurement),
            "effective_perception": deepcopy(perception),
            "goal": deepcopy(goal),
            "operator_supplied_goal": False,
            "operator_approval_required": False,
            "proposals": [candidate.document() for candidate in ranked],
            "value": {
                "equation": "U(a)=decision_value * expected_information_gain / effort",
                "selected_candidate": selected.identifier,
                "selected_utility": selected.utility,
                "selection_origin": "goal-constrained internal value ranking" if goal_directed else "internal deterministic value ranking",
            },
            "guard": guard,
            "execution": {
                "executed": transition is not None,
                "sandbox": not selected.external,
                "external_action": selected.external and transition is not None,
                "authorization_origin": "Zoe internal guard evaluation under the current owner actuation grant" if selected.external else "Zoe internal guard evaluation under invariant external-actuation prohibitions",
                "operator_approval_required": False,
                "transition": transition,
            },
            "belief_updated": belief["changed"] if belief is not None else False,
            "previous_hash": self.events[-1]["hash"] if self.events else None,
        }
        if belief is not None:
            event["belief_update"] = belief
        event["hash"] = digest(event)
        self.events.append(event)
        self.external_actions += int(selected.external and transition is not None)
        return deepcopy(event)

    def state(self):
        return {
            "policy": self.policy.authorization_id,
            "environment": self.environment.snapshot(),
            "events": deepcopy(self.events),
            "sandbox_executions": sum(event["execution"]["executed"] for event in self.events),
            "internally_authored_goals": sum(event["goal"]["internal_authorship"] for event in self.events),
            "operator_approval_required": False,
            "external_actions": self.external_actions,
            "belief_updated": self.events[-1]["belief_updated"] if self.events else False,
        }

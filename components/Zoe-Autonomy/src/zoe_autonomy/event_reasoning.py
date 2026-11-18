from __future__ import annotations

from copy import deepcopy
import heapq
import math
import statistics

from .event_core import ACTIONS, CENTERS
from .loop import Candidate, digest

DYNAMICS = ("position", "direction", "appearance")


def bounce(position, velocity):
    value = position + velocity
    while value < 1 or value > 14:
        if value < 1:
            value = 1 + (1 - value)
            velocity = abs(velocity)
        if value > 14:
            value = 14 - (value - 14)
            velocity = -abs(velocity)
    return value, velocity


def attention_after(attention, action):
    if action == "attend_left":
        return max(0, attention - 1)
    if action == "attend_right":
        return min(len(CENTERS) - 1, attention + 1)
    return attention


class ForwardEnsemble:
    def __init__(self, members=5, history_enabled=True):
        if isinstance(members, bool) or not isinstance(members, int) or not 2 <= members <= 16:
            raise ValueError("forward ensemble requires 2-16 members")
        if not isinstance(history_enabled, bool):
            raise ValueError("history_enabled must be a boolean")
        self.history_enabled = history_enabled
        self.members = [
            {
                "position": None,
                "velocity": 0.0,
                "learned_velocity": 0.0,
                "learned_dynamics": {"negative": 0.0, "positive": 0.0},
                "current_direction": None,
                "recent_velocities": [],
                "alpha": .2 + .15 * index,
                "weight": (1.0, .8, 1.2, .9, 1.1, 1.05, .95, 1.15)[index % 8],
                "updates": 0,
                "misses": 0,
                "last_visible_step": None,
            }
            for index in range(members)
        ]

    def checkpoint(self):
        return deepcopy(self.members)

    def restore(self, members):
        if not isinstance(members, list) or len(members) != len(self.members):
            raise ValueError("forward-ensemble checkpoint is incompatible")
        self.members = deepcopy(members)

    def start_sequence(self):
        for member in self.members:
            member["position"] = None
            member["velocity"] = 0.0
            member["current_direction"] = None
            member["recent_velocities"] = []
            member["misses"] = 0
            member["last_visible_step"] = None

    def update(self, observation, step, learning=True):
        if not isinstance(learning, bool):
            raise ValueError("learning flag must be a boolean")
        centroid = observation.get("centroid")
        for member in self.members:
            if member["position"] is None:
                if centroid is not None:
                    member["position"] = float(centroid[0])
                    member["last_visible_step"] = step
                continue
            if centroid is None:
                if learning:
                    member["position"], member["velocity"] = bounce(member["position"], member["velocity"])
                    member["misses"] += 1
                continue
            position = float(centroid[0])
            previous_step = member["last_visible_step"]
            if previous_step is not None and step > previous_step:
                instantaneous = (position - member["position"]) / (step - previous_step)
                instantaneous = max(-4.0, min(4.0, instantaneous))
                translation = observation.get("translation")
                if self.history_enabled and translation and translation["overlap"] >= 3:
                    member["recent_velocities"].append(instantaneous)
                    member["recent_velocities"] = member["recent_velocities"][-3:]
                estimated = statistics.median(member["recent_velocities"]) if self.history_enabled and member["recent_velocities"] else 0.0
                direction = "positive" if estimated > 0 else "negative" if estimated < 0 else None
                member["current_direction"] = direction
                if self.history_enabled:
                    member["velocity"] = estimated
                else:
                    member["velocity"] = 0.0
                if learning:
                    rate = min(.95, member["alpha"] * member["weight"])
                    if direction:
                        prior = member["learned_dynamics"].get(direction, 0.0)
                        member["learned_dynamics"][direction] = (1 - rate) * prior + rate * estimated
                        member["learned_velocity"] = member["learned_dynamics"][direction]
                    member["updates"] += 1
            member["misses"] = 0
            member["position"] = position
            member["last_visible_step"] = step

    def predict(self, attention, action, memory=None):
        following = attention_after(attention, action)
        center = CENTERS[following]
        memory_delta = 0.0
        retrieval_count = 0
        if memory:
            retrieval_count = len(memory)
            memory_delta = math.fsum(item["weight"] * item["episode"]["value"].get("delta_x", 0.0) for item in memory)
        positions = []
        velocities = []
        for member in self.members:
            if member["position"] is None:
                continue
            position, velocity = bounce(member["position"], member["velocity"] + .1 * memory_delta)
            positions.append(position)
            velocities.append(velocity)
        localized = bool(positions)
        if not positions:
            positions = [float(center)]
            velocities = [0.0]
        target = statistics.mean(positions)
        variance = statistics.mean((position - target) ** 2 for position in positions)
        misses = statistics.mean(member["misses"] for member in self.members)
        visible = localized and center - 4 <= target <= center + 3
        prediction = {
            "target_x": target,
            "target_y": 7.5,
            "velocity": statistics.mean(velocities),
            "target_distribution": positions,
            "variance": variance + misses * .05,
            "attention_after": following,
            "predicted_centroid": [target, 7.5] if visible else None,
            "predicted_event_count": 6 if visible else 0,
            "visible": visible,
            "localized": localized,
            "search_required": not localized,
            "retrieved_episode_count": retrieval_count,
            "memory_delta_x": memory_delta,
            "model_components": list(DYNAMICS),
        }
        return prediction

    def document(self):
        return {"member_count": len(self.members), "members": deepcopy(self.members), "components": list(DYNAMICS), "history_enabled": self.history_enabled}


def shortest_trajectory(ensemble, attention, horizon=2):
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 4:
        raise ValueError("planning horizon must be an integer from 1 to 4")
    start = (0, attention)
    distances = {start: 0.0}
    previous = {}
    queue = [(0.0, start)]
    edges = []
    terminal = None
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distances.get(node):
            continue
        stage, current = node
        if stage == horizon:
            terminal = node
            break
        for action in ACTIONS[:-1]:
            following = attention_after(current, action)
            prediction = ensemble.predict(current, action)
            search_cost = 0.0 if not prediction["search_required"] or following != current else .5
            edge_cost = .05 + abs(CENTERS[following] - prediction["target_x"]) / 15 + .1 * prediction["variance"] + (0 if prediction["visible"] else .2) + search_cost
            candidate = (stage + 1, following)
            total = cost + edge_cost
            edges.append({"from": list(node), "to": list(candidate), "action": action, "cost": edge_cost})
            if total < distances.get(candidate, math.inf):
                distances[candidate] = total
                previous[candidate] = (node, action)
                heapq.heappush(queue, (total, candidate))
    if terminal is None:
        terminal = min((node for node in distances if node[0] == horizon), key=distances.get)
    actions = []
    states = [list(terminal)]
    node = terminal
    while node != start:
        parent, action = previous[node]
        actions.append(action)
        states.append(list(parent))
        node = parent
    actions.reverse()
    states.reverse()
    return {
        "algorithm": "exact nonnegative Dijkstra over a time-expanded attention graph",
        "horizon": horizon,
        "path": actions,
        "states": states,
        "cost": distances[terminal],
        "edge_count": len(edges),
        "edges": edges,
        "nonnegative_costs": all(edge["cost"] >= 0 for edge in edges),
    }


def propose(ensemble, attention, uncertainty, memory=None):
    trajectory = shortest_trajectory(ensemble, attention)
    proposals = []
    details = []
    for action in ACTIONS:
        prediction = ensemble.predict(attention, action, memory)
        following = prediction["attention_after"]
        distance = abs(CENTERS[following] - prediction["target_x"])
        goal_value = .5 if prediction["search_required"] else max(.01, 1 - distance / 15)
        if prediction["search_required"]:
            information = 1.0 if following != attention else .05
        else:
            information = min(1.0, (.35 if action == "abstain" else .45) + .55 * prediction["visible"] + .15 * bool(memory))
        effort = 1.2 if action in {"attend_left", "attend_right"} else 1.0
        utility = goal_value * information / effort
        if action == trajectory["path"][0]:
            utility += .08
        if action == "abstain":
            utility = 1.0 if uncertainty["intervention"] else .01
        rationale = (
            f"Predicted target x={prediction['target_x']:.4f} at attention {following}; "
            f"visibility={prediction['visible']}; variance={prediction['variance']:.6f}; "
            f"independent uncertainty={uncertainty['score']:.6f}."
        )
        if action == "abstain":
            ranking_utility = 1.0 if uncertainty["intervention"] else .01
        else:
            ranking_utility = min(.99, utility)
        proposals.append(Candidate(
            f"event-{action}", action, ranking_utility, 1.0, 1.0, rationale,
            internal=True, reversible=True, external=False,
        ))
        details.append({
            "id": f"event-{action}",
            "action": action,
            "prediction": prediction,
            "goal_value": goal_value,
            "expected_information_gain": information,
            "effort": effort,
            "ranking_utility": ranking_utility,
            "utility_includes_path_bonus": action == trajectory["path"][0],
            "uncertainty_intervention": uncertainty["intervention"],
        })
    return proposals, details, trajectory

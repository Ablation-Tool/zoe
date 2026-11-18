from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path

from .loop import canonical, digest

MEMORY_INSTRUMENT = "zoe-event-memory/v1"
SPACES = ("perception", "action", "uncertainty")


def _vector(value, label="memory vector"):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 64:
        raise ValueError(f"{label} must contain 1-64 numbers")
    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{label} contains a non-finite value")
        result.append(float(item))
    return result


def _similarity(first, second):
    if len(first) != len(second):
        return 0.0
    scale = math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)) / len(first))
    return math.exp(-scale)


class WorkingMemory:
    def __init__(self):
        self.spaces = {name: [] for name in SPACES}
        self.revisions = {name: 0 for name in SPACES}

    def write(self, space, value):
        if space not in SPACES:
            raise ValueError("working-memory writes require a declared independent subspace")
        vector = _vector(value, f"{space} subspace")
        self.spaces[space] = vector
        self.revisions[space] += 1
        return {"space": space, "revision": self.revisions[space], "sha256": digest(vector)}

    def read(self, space):
        if space not in SPACES:
            raise ValueError("unknown working-memory subspace")
        return deepcopy(self.spaces[space])

    def checkpoint(self):
        return {"spaces": deepcopy(self.spaces), "revisions": deepcopy(self.revisions)}

    def restore(self, checkpoint):
        if not isinstance(checkpoint, dict) or set(checkpoint) != {"spaces", "revisions"}:
            raise ValueError("invalid working-memory checkpoint")
        if set(checkpoint["spaces"]) != set(SPACES) or set(checkpoint["revisions"]) != set(SPACES):
            raise ValueError("working-memory subspaces are incomplete")
        self.spaces = {name: _vector(checkpoint["spaces"][name]) if checkpoint["spaces"][name] else [] for name in SPACES}
        self.revisions = {name: int(checkpoint["revisions"][name]) for name in SPACES}


class KeyValueEventMemory:
    def __init__(self, state_root=None, capacity=512):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 4096:
            raise ValueError("event-memory capacity must be an integer from 1 to 4096")
        self.capacity = capacity
        self.episodes = []
        self.working = WorkingMemory()
        self.state_root = Path(state_root).expanduser().resolve() if state_root is not None else None
        if self.state_root is not None:
            self.state_root.mkdir(parents=True, exist_ok=True)
            os.chmod(self.state_root, 0o700)
            self.state_path = self.state_root / "memory.json"
            if self.state_path.is_file():
                self._load()

    def checkpoint(self):
        return {"episodes": deepcopy(self.episodes), "working": self.working.checkpoint()}

    def restore(self, checkpoint):
        if not isinstance(checkpoint, dict) or set(checkpoint) != {"episodes", "working"}:
            raise ValueError("invalid event-memory checkpoint")
        episodes = deepcopy(checkpoint["episodes"])
        if not self._chain_valid(episodes):
            raise ValueError("event-memory checkpoint chain is invalid")
        self.episodes = episodes
        self.working.restore(checkpoint["working"])

    def _chain_valid(self, episodes=None):
        records = self.episodes if episodes is None else episodes
        previous = None
        for index, episode in enumerate(records, 1):
            if episode.get("sequence") != index or episode.get("previous_hash") != previous:
                return False
            if digest({key: value for key, value in episode.items() if key != "sha256"}) != episode.get("sha256"):
                return False
            previous = episode["sha256"]
        return True

    def add_episode(self, feature_vector, action, outcome, causal_context=None):
        feature = _vector(feature_vector, "episodic key")
        if not isinstance(action, str) or not action.strip() or len(action) > 64:
            raise ValueError("episodic action must be bounded text")
        if not isinstance(outcome, dict):
            raise ValueError("episodic outcome must be a mapping")
        canonical(outcome)
        if causal_context is not None and not isinstance(causal_context, dict):
            raise ValueError("causal context must be a mapping")
        episode = {
            "sequence": len(self.episodes) + 1,
            "key": {"feature_vector": feature, "action": action},
            "value": deepcopy(outcome),
            "causal_context": deepcopy(causal_context or {}),
            "previous_hash": self.episodes[-1]["sha256"] if self.episodes else None,
        }
        episode["sha256"] = digest(episode)
        self.episodes.append(episode)
        if len(self.episodes) > self.capacity:
            raise ValueError("event-memory capacity requires an explicit replay/consolidation checkpoint")
        return deepcopy(episode)

    def retrieve(self, feature_vector, action=None, limit=4, tau=.25):
        query = _vector(feature_vector, "memory query")
        if not 0 < tau <= 10:
            raise ValueError("retrieval temperature must be positive and bounded")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 32:
            raise ValueError("retrieval limit must be an integer from 1 to 32")
        scored = []
        for episode in self.episodes:
            key = episode["key"]
            similarity = _similarity(query, key["feature_vector"])
            if action is not None:
                similarity *= 1.15 if key["action"] == action else .85
            scored.append((similarity, episode))
        scored.sort(key=lambda item: (-item[0], item[1]["sequence"]))
        selected = scored[:limit]
        if not selected:
            return []
        maximum = max(score for score, _ in selected)
        weights = [math.exp((score - maximum) / tau) for score, _ in selected]
        total = math.fsum(weights)
        return [
            {"weight": weight / total, "episode": deepcopy(episode)}
            for (score, episode), weight in zip(selected, weights)
        ]

    def replay_batch(self, size=8):
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 64:
            raise ValueError("replay batch size must be an integer from 1 to 64")
        if not self.episodes:
            return []
        novel = self.episodes[-max(1, size // 2):]
        familiar_count = max(1, size - len(novel))
        familiar = []
        for index in range(familiar_count):
            familiar.append(self.episodes[(index * max(1, len(self.episodes) - len(novel))) // familiar_count])
        batch = []
        for index in range(max(len(novel), len(familiar))):
            if index < len(novel):
                batch.append(novel[index])
            if index < len(familiar):
                batch.append(familiar[index])
        return deepcopy(batch[:size])

    def consolidate(self):
        retained = self.episodes[-self.capacity:]
        if len(retained) < len(self.episodes):
            rebuilt = []
            for episode in retained:
                rebuilt.append({key: deepcopy(value) for key, value in episode.items() if key not in {"sequence", "previous_hash", "sha256"}})
            self.episodes = []
            for episode in rebuilt:
                self.add_episode(episode["key"]["feature_vector"], episode["key"]["action"], episode["value"], episode["causal_context"])
        if not self._chain_valid():
            raise ValueError("event-memory consolidation broke the hash chain")
        return {"episodes": len(self.episodes), "head": self.episodes[-1]["sha256"] if self.episodes else None}

    def save(self):
        if self.state_root is None:
            raise ValueError("event memory has no persistent state root")
        if not self._chain_valid():
            raise ValueError("cannot save an invalid event-memory chain")
        document = {
            "schema_version": 1,
            "instrument": MEMORY_INSTRUMENT,
            "capacity": self.capacity,
            "checkpoint": self.checkpoint(),
        }
        document["sha256"] = digest(document)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.state_path)
        return self.state_path

    def _load(self):
        if self.state_path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("event-memory state exceeds 64 MiB")
        document = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("instrument") != MEMORY_INSTRUMENT or document.get("capacity") != self.capacity:
            raise ValueError("unsupported event-memory state")
        if digest({key: value for key, value in document.items() if key != "sha256"}) != document.get("sha256"):
            raise ValueError("event-memory state digest mismatch")
        self.restore(document["checkpoint"])

    def document(self):
        return {
            "instrument": MEMORY_INSTRUMENT,
            "episode_count": len(self.episodes),
            "capacity": self.capacity,
            "head": self.episodes[-1]["sha256"] if self.episodes else None,
            "chain_valid": self._chain_valid(),
            "working_memory": self.working.checkpoint(),
            "independent_subspaces": list(SPACES),
        }

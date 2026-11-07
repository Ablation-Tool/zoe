from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .field import _canonical


PRACTICE_METADATA = {"sequence", "kind", "timestamp", "previous_hash", "event_hash"}
PRACTICE_FIELDS = {"situation", "action", "outcome", "next_try", "mistake", "advice", "learning", "support", "unknown", "stop_condition", "frame", "execution_authorized", "evidence_level"}
CORRECTION_FIELDS = {"corrects", "learning", "execution_authorized", "evidence_level"}
DOCUMENT_FIELDS = {"schema_version", "instrument", "skill_model", "score", "autonomous_action", "synthetic_example", "events", "digest"}


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value, label, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    value = value.strip()
    if len(value) > 1500 or required and not value:
        raise ValueError(f"{label} must contain {'1-1500' if required else 'at most 1500'} characters")
    return value


def _frame(value):
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple)) or len(value) > 6:
        raise ValueError("frame must contain up to six short labels")
    result = []
    for label in value:
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 40:
            raise ValueError("frame labels must contain 1-40 characters")
        label = label.strip()
        if label not in result:
            result.append(label)
    return result


def _timestamp(value=None):
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("practice timestamp must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("practice timestamp must include a timezone")
    return value


class PracticeLog:
    def __init__(self):
        self.events = []
        self.synthetic = False

    def _append(self, event):
        event["sequence"] = len(self.events) + 1
        event["previous_hash"] = self.events[-1]["event_hash"] if self.events else None
        event["event_hash"] = _digest(event)
        self.events.append(event)
        self.synthetic = False
        return event

    def add_practice(self, situation, action, outcome, next_try, *, frame=(), mistake="", advice="", learning="", support="", unknown="", stop_condition="", timestamp=None):
        if len(self.events) >= 4096:
            raise ValueError("practice log is full; start a new reviewed log")
        event = {
            "kind": "practice",
            "timestamp": _timestamp(timestamp),
            "situation": _text(situation, "situation", True),
            "action": _text(action, "action", True),
            "outcome": _text(outcome, "outcome", True),
            "next_try": _text(next_try, "next_try", True),
            "frame": _frame(frame),
            "mistake": _text(mistake, "mistake"),
            "advice": _text(advice, "advice"),
            "learning": _text(learning, "learning"),
            "support": _text(support, "support"),
            "unknown": _text(unknown, "unknown"),
            "stop_condition": _text(stop_condition, "stop_condition"),
            "execution_authorized": False,
            "evidence_level": "self-reported-practice",
        }
        return self._append(event)

    def add_correction(self, sequence, learning, timestamp=None):
        if isinstance(sequence, bool) or not isinstance(sequence, int) or not any(event["kind"] == "practice" and event["sequence"] == sequence for event in self.events):
            raise ValueError("correction requires an existing practice sequence")
        if len(self.events) >= 4096:
            raise ValueError("practice log is full; start a new reviewed log")
        return self._append({
            "kind": "correction",
            "timestamp": _timestamp(timestamp),
            "corrects": sequence,
            "learning": _text(learning, "learning", True),
            "execution_authorized": False,
            "evidence_level": "reflection",
        })

    def next_question(self):
        if not self.events:
            return "What will you try, and what will you notice?"
        practice = [event for event in self.events if event["kind"] == "practice"]
        latest = practice[-1]
        prompts = (
            ("advice", "Whose perspective could change your next attempt?"),
            ("mistake", "What did not work, and what can you try without repeating the same conditions?"),
            ("learning", "What did the outcome change in your understanding?"),
            ("unknown", "What are you still uncertain about?"),
            ("stop_condition", "What is the stop condition for the next small experiment?"),
            ("support", "Who is affected, and what support do they need?"),
        )
        for field, prompt in prompts:
            if not latest[field]:
                return prompt
        recent = [tuple(event["frame"]) for event in practice[-3:]]
        if len(recent) == 3 and len(set(recent)) == 1:
            return "Which one condition will you change next: pace, complexity, support, or point of view?"
        return "What is the smallest useful next experiment, and how will you review it?"

    def review(self):
        practice = sum(event["kind"] == "practice" for event in self.events)
        corrections = sum(event["kind"] == "correction" for event in self.events)
        question = self.next_question()
        return {
            "practice_events": practice,
            "corrections": corrections,
            "frames": sorted({label for event in self.events if event["kind"] == "practice" for label in event["frame"]}),
            "next_question": question,
            "score": None,
            "autonomous_action": False,
            "synthetic_example": self.synthetic,
            "event_label": "worked-example events" if self.synthetic else "practice events",
            "summary": f"{practice} {'worked-example events' if self.synthetic else 'practice events'} · {corrections} corrections · no leadership score\nNext: {question}\nNo next experiment is executed automatically.",
        }

    def document(self):
        result = {
            "schema_version": 1,
            "instrument": "zoe-leadership-practice",
            "skill_model": "adaptive-perishable-practice",
            "score": None,
            "autonomous_action": False,
            "synthetic_example": self.synthetic,
            "events": deepcopy(self.events),
        }
        result["digest"] = _digest(result)
        return result

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("practice logs must use a .json path")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("practice log exceeds 64 MiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-leadership-practice" or data.get("skill_model") != "adaptive-perishable-practice" or data.get("score") is not None or data.get("autonomous_action") is not False or not isinstance(data.get("synthetic_example"), bool):
            raise ValueError("unsupported leadership practice log")
        if data["digest"] != _digest({key: value for key, value in data.items() if key != "digest"}):
            raise ValueError("practice log digest mismatch")
        if not isinstance(data["events"], list) or len(data["events"]) > 4096:
            raise ValueError("practice log event count exceeds the bound")
        log = cls()
        log.synthetic = data["synthetic_example"]
        previous_hash = None
        for index, event in enumerate(data["events"], 1):
            if not isinstance(event, dict) or event.get("sequence") != index or event.get("previous_hash") != previous_hash or event.get("kind") not in {"practice", "correction"}:
                raise ValueError("practice events are reordered or have an invalid chain")
            fields = PRACTICE_FIELDS if event["kind"] == "practice" else CORRECTION_FIELDS
            if set(event) != PRACTICE_METADATA | fields or event["execution_authorized"] is not False:
                raise ValueError("invalid practice event fields")
            _timestamp(event["timestamp"])
            if event["kind"] == "practice":
                for field in ("situation", "action", "outcome", "next_try"):
                    _text(event[field], field, True)
                for field in ("mistake", "advice", "learning", "support", "unknown", "stop_condition"):
                    _text(event[field], field)
                _frame(event["frame"])
                if event["evidence_level"] != "self-reported-practice":
                    raise ValueError("invalid practice evidence level")
            else:
                if not isinstance(event["corrects"], int) or isinstance(event["corrects"], bool) or not any(item["kind"] == "practice" and item["sequence"] == event["corrects"] for item in log.events):
                    raise ValueError("correction references an invalid practice event")
                _text(event["learning"], "learning", True)
                if event["evidence_level"] != "reflection":
                    raise ValueError("invalid correction evidence level")
            if event["event_hash"] != _digest({key: value for key, value in event.items() if key != "event_hash"}):
                raise ValueError("practice event hash mismatch")
            log.events.append(deepcopy(event))
            previous_hash = event["event_hash"]
        return log


def demo_log():
    log = PracticeLog()
    log.add_practice(
        "A teammate asks for help with an unfamiliar setup.",
        "I explain the steps once instead of asking what they need.",
        "They can repeat the steps but cannot tell when to stop.",
        "Ask what they want to accomplish and agree on a stop condition first.",
        frame=["simple", "preparation"],
        mistake="I optimized for speed before understanding.",
        advice="A teammate asks for fewer instructions and more context.",
        learning="Understanding is not the same as watching someone follow steps.",
        support="Time and a safe way to ask basic questions.",
        unknown="What does the teammate already know?",
        stop_condition="Pause if the explanation becomes pressuring or unclear.",
        timestamp="2026-11-01T09:00:00+00:00",
    )
    log.add_practice(
        "A planned review fails when the room loses network access.",
        "I continue presenting instead of changing the exercise.",
        "People hear the slides but do not practice the decision.",
        "Use a local example and let each person make and review one choice.",
        frame=["difficult", "communication"],
        mistake="I protected the plan instead of the purpose.",
        learning="The useful outcome is participation, not completing my script.",
        support="A printed example and permission to change the format.",
        unknown="Which part of the exercise is hardest for each person?",
        stop_condition="Stop if the exercise excludes someone from participating.",
        timestamp="2026-11-02T14:00:00+00:00",
    )
    log.add_practice(
        "Several people need different kinds of help at once.",
        "I try to solve every request myself.",
        "I become the bottleneck and miss the person with the most urgent need.",
        "Ask for priorities and share ownership of the next small actions.",
        frame=["complex", "support"],
        mistake="I confused being needed with being helpful.",
        advice="A colleague offers to coordinate one of the requests.",
        learning="Support can mean creating room for someone else to lead.",
        support="Clear priorities and a way to say when the load is too much.",
        unknown="Which request is most urgent to the people affected?",
        stop_condition="Pause and reassign work if care or accuracy starts to suffer.",
        timestamp="2026-11-03T16:00:00+00:00",
    )
    log.synthetic = True
    return log

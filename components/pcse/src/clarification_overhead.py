"""
clarification_overhead.py — v0.1

Scores conversation exchanges for clarification overhead, the first
measurable dimension of the NuClide trust token.

Definition
----------
A clarification request is any exchange where either party cannot
proceed without additional information before generating a response.

Scoring is binary per exchange: 1 if a clarification request occurred,
0 if it did not. Aggregates produce a session-level score.

Input shape
-----------
A list of exchange dicts. Each exchange has at minimum:
    - user: str          the user's message
    - assistant: str     the assistant's response

Optional fields:
    - clarification: bool   ground-truth override; when present, used
                            directly and heuristics are skipped.
    - id: str               stable identifier for the exchange.

Output shape
------------
A dict with:
    - per_exchange: list of {id, score, reason}
    - total_clarifications: int
    - total_exchanges: int
    - ratio: float           clarifications per exchange (0.0 - 1.0)
    - per_n_rate: float      rate per N exchanges (default N=10)
    - session_score: float   1.0 - ratio; higher means lower overhead
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


# Phrases that signal a turn is asking for clarification rather than
# producing a substantive response. Lowercased; matched as substrings
# against the leading window of the turn.
_CLARIFICATION_OPENERS = (
    "could you clarify",
    "can you clarify",
    "could you specify",
    "can you specify",
    "could you tell me",
    "can you tell me more",
    "what do you mean",
    "which one",
    "which of",
    "do you mean",
    "before i ",
    "before we ",
    "i need to know",
    "i need more",
    "i'll need",
    "to answer that i need",
    "to help with that i need",
    "a few questions",
    "one question first",
    "quick question",
)

# Cap for "short and ends in ?" heuristic. A long answer that happens
# to end with a question is not a clarification request.
_SHORT_QUESTION_CHARS = 240

# Back-reference signals: phrases that indicate a user turn is pointing
# at a prior assistant response. Required for short-question detection
# on the user side, since a normal substantive question (e.g.
# "What does the session_score field represent?") must not count as a
# clarification request — the responder can proceed without more info.
_BACKREF_SIGNALS = (
    "you said",
    "you mentioned",
    "you wrote",
    "you meant",
    "you mean",
    "your last",
    "your previous",
    "your response",
    "your answer",
    "your point",
    "what you",
    "when you",
    "earlier",
    "above",
    " that?",
    " this?",
    " that ",
    " this ",
    "wait,",
    "wait ",
)


def _has_backref(lower_text: str) -> bool:
    """Return True if the text references a prior turn."""
    for signal in _BACKREF_SIGNALS:
        if signal in lower_text:
            return True
    return False


def _is_clarification_turn(text: str, role: str) -> tuple[bool, str]:
    """Return (is_clarification, reason) for one turn.

    role is "assistant" or "user". Openers apply to both. The short-
    question fallback applies unconditionally to the assistant turn —
    a short question instead of an answer is by definition a
    clarification — but on the user side it requires a back-reference
    to a prior assistant turn, otherwise normal Q&A would false-fire.
    """
    if not text:
        return False, "empty"

    stripped = text.strip()
    lower = stripped.lower()
    head = lower[:160]

    for opener in _CLARIFICATION_OPENERS:
        if opener in head:
            return True, f"opener:{opener!r}"

    # Short turn that is essentially one question.
    if stripped.endswith("?") and len(stripped) <= _SHORT_QUESTION_CHARS:
        sentence_count = len(re.findall(r"[.!?]+", stripped))
        if sentence_count <= 2:
            if role == "assistant":
                return True, "short_question"
            if role == "user" and _has_backref(lower):
                return True, "short_question+backref"

    return False, "substantive"


def score_exchange(exchange: dict) -> dict:
    """Score a single exchange. Returns {id, score, reason}."""
    ex_id = exchange.get("id", "?")

    if "clarification" in exchange:
        flag = bool(exchange["clarification"])
        return {
            "id": ex_id,
            "score": 1 if flag else 0,
            "reason": "explicit_label",
        }

    # Either party may have triggered the clarification. Check both
    # turns; the assistant case is the common one, but a user asking
    # Claude to restate also counts.
    a_flag, a_reason = _is_clarification_turn(
        exchange.get("assistant", ""), role="assistant"
    )
    if a_flag:
        return {"id": ex_id, "score": 1, "reason": f"assistant:{a_reason}"}

    u_flag, u_reason = _is_clarification_turn(
        exchange.get("user", ""), role="user"
    )
    if u_flag:
        return {"id": ex_id, "score": 1, "reason": f"user:{u_reason}"}

    return {"id": ex_id, "score": 0, "reason": "substantive"}


def score_session(exchanges: Iterable[dict], n: int = 10) -> dict:
    """Score a full session. `n` sets the per-N-exchanges window."""
    per_exchange = [score_exchange(ex) for ex in exchanges]
    total_exchanges = len(per_exchange)
    total_clar = sum(row["score"] for row in per_exchange)

    ratio = (total_clar / total_exchanges) if total_exchanges else 0.0
    per_n_rate = ratio * n
    session_score = 1.0 - ratio

    return {
        "per_exchange": per_exchange,
        "total_clarifications": total_clar,
        "total_exchanges": total_exchanges,
        "ratio": round(ratio, 4),
        "per_n_rate": round(per_n_rate, 4),
        "n": n,
        "session_score": round(session_score, 4),
    }


def load_exchanges(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "exchanges" in data:
        return data["exchanges"]
    return data


def _format_report(result: dict) -> str:
    lines = []
    lines.append("clarification overhead — session report")
    lines.append("=" * 44)
    for row in result["per_exchange"]:
        marker = "CLAR" if row["score"] else "----"
        lines.append(f"  [{marker}] {row['id']:<12} {row['reason']}")
    lines.append("-" * 44)
    lines.append(f"  total exchanges       : {result['total_exchanges']}")
    lines.append(f"  total clarifications  : {result['total_clarifications']}")
    lines.append(f"  ratio                 : {result['ratio']}")
    lines.append(f"  rate per {result['n']} exchanges : {result['per_n_rate']}")
    lines.append(f"  session score         : {result['session_score']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    default_path = Path(__file__).resolve().parent.parent / "data" / "sample_exchanges.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    exchanges = load_exchanges(path)
    result = score_session(exchanges)
    print(_format_report(result))
    print()
    print(json.dumps(result, indent=2))

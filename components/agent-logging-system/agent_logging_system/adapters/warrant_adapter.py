"""Warrant adapter: monitor a book-grounded coding agent.

Warrant reasons from source material, generates code, and verifies citations.
Each of those is a distinct action shape worth tracking on its own terms — a
citation that fails to verify is a different signal than code that fails to
parse. This adapter exposes one logging method per action so the resulting
observation stream is legible at the domain level, not just as generic calls.
"""
import time
from typing import Any

from .base_adapter import BaseAdapter
from agent_logging_system.observation import LATENCY_GENERATION


class _WrappedWarrantAgent:
    """Transparent proxy routing Warrant reason/generate/verify calls to WarrantAdapter."""

    def __init__(self, target: Any, adapter: "WarrantAdapter", agent_id: str) -> None:
        self._target = target
        self._adapter = adapter
        self._agent_id = agent_id

    def reason(self, source: str, question: str, *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = self._target.reason(source, question, *args, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        answer = result.get("answer", str(result)) if isinstance(result, dict) else str(result)
        confidence = float(result.get("confidence", 0.85)) if isinstance(result, dict) else 0.85
        self._adapter.log_reasoning_step(self._agent_id, source, question, answer, confidence, latency_ms)
        return result

    def generate(self, prompt: str, *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = self._target.generate(prompt, *args, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        code = result.get("code", str(result)) if isinstance(result, dict) else str(result)
        syntax_valid = bool(result.get("syntax_valid", True)) if isinstance(result, dict) else True
        self._adapter.log_code_generation(self._agent_id, prompt, code, syntax_valid, latency_ms)
        return result

    def verify_citation(self, citation: str, source: str, *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = self._target.verify_citation(citation, source, *args, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        valid = bool(result.get("valid", result)) if isinstance(result, dict) else bool(result)
        self._adapter.log_citation_check(self._agent_id, citation, source, valid, latency_ms)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class WarrantAdapter(BaseAdapter):
    """Domain-specific logging surface for Warrant agents."""

    def wrap_agent(self, warrant_agent: Any, agent_id: str = "warrant") -> Any:
        """Wrap a Warrant agent so reason/generate/verify_citation calls emit observations.

        If `warrant_agent` exposes any of `reason`, `generate`, or `verify_citation`,
        returns a transparent proxy that records latency and domain outcomes via the
        log_* methods below; otherwise returns `warrant_agent` unchanged for compatibility.
        """
        if any(callable(getattr(warrant_agent, m, None)) for m in ("reason", "generate", "verify_citation")):
            return _WrappedWarrantAgent(warrant_agent, self, agent_id)
        return warrant_agent

    def log_reasoning_step(
        self, agent_id: str, source: str, question: str,
        answer: str, confidence: float, latency_ms: float,
    ) -> None:
        """A reasoning step grounded in a source document.

        Generation latency: the duration reflects how much answer was produced,
        not a machine bottleneck, so it never feeds the latency alarm.
        """
        self.emit_observation(
            agent_id=agent_id,
            action="reason_about_source",
            input_data={"source": source, "question": question},
            output_data={"answer": answer, "confidence": confidence},
            latency_ms=latency_ms,
            confidence=confidence,
            latency_kind=LATENCY_GENERATION,
        )

    def log_code_generation(
        self, agent_id: str, prompt: str, code: str,
        syntax_valid: bool, latency_ms: float,
    ) -> None:
        """A code-generation step; invalid syntax is logged as a failure.

        Generation latency: longer output is expected, not pathological.
        """
        self.emit_observation(
            agent_id=agent_id,
            action="generate_code",
            input_data={"prompt": prompt},
            output_data={"code": code, "syntax_valid": syntax_valid},
            latency_ms=latency_ms,
            status="success" if syntax_valid else "failed",
            confidence=1.0 if syntax_valid else 0.5,
            latency_kind=LATENCY_GENERATION,
        )

    def log_citation_check(
        self, agent_id: str, citation: str, source: str,
        valid: bool, latency_ms: float,
    ) -> None:
        """A citation-verification step; an unverifiable citation is a failure."""
        self.emit_observation(
            agent_id=agent_id,
            action="verify_citation",
            input_data={"citation": citation, "source": source},
            output_data={"valid": valid},
            latency_ms=latency_ms,
            status="success" if valid else "failed",
            confidence=1.0,
        )

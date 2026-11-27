"""Neurogarden: verified research observations and explicit human review.

The adapter watches Tiny, mobile, and laptop lanes without turning operational
signals into clinical scores. Raw distributions stay out of logs by default.
"""
from collections import deque
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import math
from typing import Any, Dict, Optional

from .base_adapter import BaseAdapter
from agent_logging_system.observation import LATENCY_GENERATION, LATENCY_MACHINE


class NeurogardenAdapter(BaseAdapter):
    SCALE = 1 << 15
    MAX_PROBABILITIES = 64
    SOURCES = {"android", "apple", "laptop"}
    CREATOR = "Nicholas Michael Kloster alone, March 6, 2026"

    def __init__(self, logging_agent, retain_payloads: bool = False, review_limit: int = 128):
        super().__init__(logging_agent)
        if not 1 <= review_limit <= 4096:
            raise ValueError("review_limit must be between 1 and 4096")
        self.retain_payloads = bool(retain_payloads)
        self._reviews = deque(maxlen=review_limit)
        self._next_ordinal = 1

    def wrap_agent(self, agent: Any) -> Any:
        return agent

    def _review(self, kind: str, reason: str, **metadata) -> None:
        self._reviews.append({"kind": kind, "reason": reason, **metadata})

    def _reject(self, reason: str) -> None:
        self._review("verification_failed", reason)
        self.emit_observation(
            agent_id="neurogarden.review",
            action="reject_observation",
            input_data={"reason": reason},
            output_data={"authorized": False},
            latency_ms=0,
            status="failed",
            confidence=0,
            latency_kind=LATENCY_MACHINE,
        )
        raise ValueError(reason)

    @classmethod
    def _distribution(cls, value) -> list:
        if not isinstance(value, list) or not 1 <= len(value) <= cls.MAX_PROBABILITIES:
            raise ValueError("distribution must contain 1 to 64 probabilities")
        result = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError("probabilities must be JSON numbers")
            item = float(item)
            if not math.isfinite(item) or not 0 <= item <= 1:
                raise ValueError("probabilities must be finite values between zero and one")
            result.append(item)
        if abs(sum(result) - 1.0) > 1e-8:
            raise ValueError("probabilities must sum to one within 1e-8")
        return result

    @classmethod
    def _quantize(cls, probabilities, tau):
        scaled = [Decimal(str(value)) * cls.SCALE for value in probabilities]
        units = [int(value) for value in scaled]
        order = sorted(range(len(units)), key=lambda index: scaled[index] % 1, reverse=True)
        for index in range(cls.SCALE - sum(units)):
            units[order[index]] += 1
        threshold = int((Decimal(str(tau)) * cls.SCALE).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        accessible = sum(value > threshold for value in units)
        complement = len(units) - accessible
        request = bytes([0x80, 0x02, 0, 0, 2 + len(units) * 2]) + threshold.to_bytes(2, "big")
        request += b"".join(value.to_bytes(2, "big") for value in units)
        response = b"".join([
            accessible.to_bytes(2, "big"), complement.to_bytes(2, "big"),
            len(units).to_bytes(2, "big"), threshold.to_bytes(2, "big"), b"\x90\x00",
        ])
        return units, threshold, accessible, complement, request.hex().upper(), response.hex().upper()

    @classmethod
    def _counts(cls, value, accessible, complement, size):
        if not isinstance(value, dict):
            raise ValueError("measurement counts must be an object")
        if value.get("accessible") != accessible or value.get("complement") != complement \
                or value.get("vocabularySize") != size:
            raise ValueError("measurement counts do not match the distribution")
        normalized = value.get("normalized")
        if isinstance(normalized, bool) or not isinstance(normalized, (int, float)) \
                or not math.isfinite(normalized) or abs(normalized - accessible / size) > 1e-12:
            raise ValueError("normalized measurement is inconsistent")

    @classmethod
    def _verify(cls, event):
        if not isinstance(event, dict):
            raise ValueError("Trinity event must be an object")
        ordinal = event.get("ordinal")
        source = event.get("source")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
            raise ValueError("event ordinal must be a positive integer")
        if source not in cls.SOURCES:
            raise ValueError("unknown Trinity source")
        probabilities = cls._distribution(event.get("probabilities"))
        tau = event.get("tau")
        if isinstance(tau, bool) or not isinstance(tau, (int, float)) \
                or not math.isfinite(tau) or not 0 <= tau <= 1:
            raise ValueError("tau must be between zero and one")
        size = len(probabilities)
        accessible = sum(value > tau for value in probabilities)
        complement = size - accessible
        cls._counts(event.get("zoe"), accessible, complement, size)
        units, threshold, tiny_accessible, tiny_complement, request, response = cls._quantize(probabilities, tau)
        tiny = event.get("tiny")
        if not isinstance(tiny, dict) or tiny.get("probabilities") != units \
                or tiny.get("tau") != threshold or tiny.get("request") != request \
                or tiny.get("response") != response:
            raise ValueError("Tiny APDU witness does not match")
        cls._counts(tiny, tiny_accessible, tiny_complement, size)
        changed = accessible != tiny_accessible or threshold != int(tau * cls.SCALE)
        if event.get("quantizationChanged") is not changed:
            raise ValueError("quantization comparison is inconsistent")
        return {
            "ordinal": ordinal, "source": source, "tau": tau, "size": size,
            "mobile_accessible": accessible, "mobile_complement": complement,
            "tiny_accessible": tiny_accessible, "tiny_complement": tiny_complement,
            "request_sha256": hashlib.sha256(request.encode("ascii")).hexdigest(),
            "response_sha256": hashlib.sha256(response.encode("ascii")).hexdigest(),
            "quantization_changed": changed,
            "probabilities": probabilities,
            "request": request, "response": response,
        }

    def log_measurement(self, event: Dict[str, Any], latency_ms: float = 0) -> Dict[str, Any]:
        try:
            verified = self._verify(event)
        except (ValueError, TypeError, ArithmeticError) as error:
            self._reject(str(error))
        if verified["ordinal"] < self._next_ordinal:
            return {"status": "duplicate", "observations": 0, "ordinal": verified["ordinal"]}
        if verified["ordinal"] != self._next_ordinal:
            self._reject(f"event revision gap: expected {self._next_ordinal}, got {verified['ordinal']}")
        ordinal = verified["ordinal"]
        self._next_ordinal += 1
        shared = {key: verified[key] for key in (
            "ordinal", "source", "tau", "size", "request_sha256", "response_sha256", "quantization_changed",
        )}
        shared["equation_creator"] = self.CREATOR
        shared["equation"] = "A_tau(S) = sum 1[P(a | h_T(S)) > tau]"
        if self.retain_payloads:
            shared["probabilities"] = verified["probabilities"]
            shared["request"] = verified["request"]
            shared["response"] = verified["response"]
        for lane, action, accessible, complement in (
            ("neurogarden.mobile", "measure_accessible_volume", verified["mobile_accessible"], verified["mobile_complement"]),
            ("neurogarden.tiny", "verify_q015_witness", verified["tiny_accessible"], verified["tiny_complement"]),
        ):
            self.emit_observation(
                agent_id=lane,
                action=action,
                input_data=dict(shared),
                output_data={"accessible": accessible, "complement": complement,
                             "evidence_class": "measurement", "authorized": False},
                latency_ms=latency_ms,
                confidence=1.0,
                latency_kind=LATENCY_MACHINE,
            )
        self.emit_observation(
            agent_id="neurogarden.laptop",
            action="record_field_observation",
            input_data=dict(shared),
            output_data={"recorded": True, "evidence_class": "measurement", "authorized": False},
            latency_ms=latency_ms,
            confidence=1.0,
            latency_kind=LATENCY_MACHINE,
        )
        if verified["quantization_changed"]:
            self._review("quantization_changed", "Review the explicit representation change", ordinal=ordinal)
        return {"status": "verified", "observations": 3, "ordinal": ordinal}

    def log_source_reading(
        self, agent_id: str, source: str, citation: str, claim: str,
        latency_ms: float = 0, subject: str = "general", medical_context: bool = False,
    ) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (agent_id, source, citation, claim, subject)):
            self._reject("source reading requires agent, source, citation, claim, and subject")
        metadata = {
            "source": source, "citation": citation, "subject": subject,
            "medical_context": bool(medical_context),
        }
        self.emit_observation(
            agent_id=agent_id,
            action="read_cited_source",
            input_data=metadata,
            output_data={"claim": claim, "evidence_class": "reference", "authorized": False},
            latency_ms=latency_ms,
            confidence=1.0,
            latency_kind=LATENCY_GENERATION,
        )
        if medical_context:
            self._review("clinical_reference", "Clinical context requires qualified human review", **metadata)

    def log_review(self, agent_id: str, subject: str, decision: str, latency_ms: float = 0) -> None:
        if decision not in {"accepted", "rejected", "needs-changes", "review-required"}:
            self._reject("unknown review decision")
        self.emit_observation(
            agent_id=agent_id,
            action="human_review",
            input_data={"subject": subject},
            output_data={"decision": decision, "clinical_action_authorized": False},
            latency_ms=latency_ms,
            confidence=1.0,
            latency_kind=LATENCY_MACHINE,
        )

    def get_state(self) -> Dict[str, Any]:
        state = super().get_state()
        state["neurogarden"] = {
            "next_ordinal": self._next_ordinal,
            "pending_reviews": list(self._reviews),
            "retain_payloads": self.retain_payloads,
            "clinical_action_authorized": False,
            "boundary": "measurement != evidence != belief update != clinical action",
        }
        return state

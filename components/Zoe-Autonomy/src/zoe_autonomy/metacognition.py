from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Mapping

from .actuation import timestamp
from .loop import text, unit


class Domain(str, Enum):
    INTENT = "intent"
    ACTION = "action"
    SELF = "self"


SOURCE_KINDS = {
    "sensor",
    "tool",
    "document",
    "validated_reflection",
    "user",
    "prior",
    "system",
    "prompt",
    "override",
}
STRONG_SOURCE_KINDS = {"sensor", "tool", "document", "validated_reflection"}


def probability(value, label="probability"):
    return unit(value, label)


@dataclass(frozen=True)
class EvidenceSource:
    kind: str
    identifier: str
    trust: float
    strength: float

    def __post_init__(self):
        if self.kind not in SOURCE_KINDS:
            raise ValueError(f"unknown evidence source kind: {self.kind}")
        text(self.identifier, "evidence source identifier", 512)
        probability(self.trust, "source trust")
        probability(self.strength, "evidence strength")

    @property
    def strong(self):
        return self.kind in STRONG_SOURCE_KINDS and self.trust >= 0.6 and self.strength >= 0.6

    def document(self):
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "trust": self.trust,
            "strength": self.strength,
            "strong_evidence": self.strong,
        }


@dataclass(frozen=True)
class Provenance:
    sources: tuple[EvidenceSource, ...]
    transformations: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.sources, tuple) or not 1 <= len(self.sources) <= 64:
            raise ValueError("provenance requires 1-64 evidence sources")
        if any(not isinstance(source, EvidenceSource) for source in self.sources):
            raise ValueError("provenance sources must be EvidenceSource instances")
        identifiers = [source.identifier for source in self.sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("evidence source identifiers must be unique within provenance")
        if not isinstance(self.transformations, tuple) or not 1 <= len(self.transformations) <= 64:
            raise ValueError("provenance requires 1-64 declared transformations")
        for transformation in self.transformations:
            text(transformation, "provenance transformation", 1000)

    @property
    def strong_evidence(self):
        return any(source.strong for source in self.sources)

    def with_transformation(self, transformation):
        return Provenance(self.sources, (*self.transformations, transformation))

    def document(self):
        return {
            "sources": [source.document() for source in self.sources],
            "transformations": list(self.transformations),
            "strong_evidence": self.strong_evidence,
        }


@dataclass(frozen=True)
class WeightedOption:
    identifier: str
    probability: float
    provenance: Provenance

    def __post_init__(self):
        text(self.identifier, "option identifier", 512)
        probability(self.probability)
        if not isinstance(self.provenance, Provenance):
            raise ValueError("every option probability requires explicit provenance")

    def document(self):
        return {
            "id": self.identifier,
            "probability": self.probability,
            "provenance": self.provenance.document(),
        }


def options_from_scores(scores: Mapping[str, float], provenance):
    if not isinstance(scores, Mapping) or not 1 <= len(scores) <= 4096:
        raise ValueError("score mapping must contain 1-4096 options")
    values = {}
    for identifier, score in scores.items():
        text(identifier, "option identifier", 512)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0:
            raise ValueError("option scores must be finite nonnegative numbers")
        values[identifier] = float(score)
    total = math.fsum(values.values())
    if total <= 0:
        raise ValueError("at least one option score must be positive")
    options = []
    for identifier, score in values.items():
        source = provenance[identifier] if isinstance(provenance, Mapping) else provenance
        if not isinstance(source, Provenance):
            raise ValueError("every normalized option requires explicit provenance")
        declared = source.with_transformation("Normalize nonnegative heuristic scores to sum to one; these are not calibrated correctness probabilities.")
        options.append(WeightedOption(identifier, score / total, declared))
    return tuple(options)


def options_from_probabilities(probabilities: Mapping[str, float], provenance):
    if not isinstance(probabilities, Mapping) or not 1 <= len(probabilities) <= 4096:
        raise ValueError("probability mapping must contain 1-4096 options")
    total = 0.0
    for identifier, value in probabilities.items():
        text(identifier, "option identifier", 512)
        total += probability(value)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("option probabilities must sum to one within 1e-9")
    options = []
    for identifier, value in probabilities.items():
        source = provenance[identifier] if isinstance(provenance, Mapping) else provenance
        options.append(WeightedOption(identifier, value, source))
    return tuple(options)


@dataclass(frozen=True)
class DomainThreshold:
    domain: Domain
    tau: float
    declared_utc: str = field(default_factory=timestamp)
    rationale: str = "Declared before evaluation and fixed for this episode; no post-hoc retuning."

    def __post_init__(self):
        Domain(self.domain)
        probability(self.tau, f"{self.domain.value} threshold")
        if not 0 < self.tau < 1:
            raise ValueError("evidence thresholds must be in (0, 1)")
        text(self.declared_utc, "threshold declaration time", 64)
        text(self.rationale, "threshold rationale", 2000)

    def document(self):
        return {
            "domain": self.domain.value,
            "tau": self.tau,
            "declared_utc": self.declared_utc,
            "rationale": self.rationale,
            "fixed_during_episode": True,
            "post_hoc_retuning_allowed": False,
        }


@dataclass(frozen=True)
class OptionBreadth:
    domain: Domain
    tau: float
    accessible_count: int
    represented_count: int | None
    options: tuple[WeightedOption, ...]
    boxed: bool = False

    def document(self):
        return {
            "domain": self.domain.value,
            "tau": self.tau,
            "accessible_count": self.accessible_count,
            "represented_count": self.represented_count,
            "boxed": self.boxed,
            "options": [option.document() for option in self.options],
        }


@dataclass(frozen=True)
class OptionShift:
    domain: Domain
    previous: OptionBreadth
    current: OptionBreadth
    delta: int
    transition: Provenance | None
    suspected_unjustified_narrowing: bool

    def document(self):
        return {
            "domain": self.domain.value,
            "previous_count": self.previous.accessible_count,
            "current_count": self.current.accessible_count,
            "delta": self.delta,
            "transition": self.transition.document() if self.transition else None,
            "suspected_unjustified_narrowing": self.suspected_unjustified_narrowing,
        }


@dataclass(frozen=True)
class ConstraintVector:
    host: bool = False
    network: bool = False
    hardware: bool = False
    external_override: bool = True
    constraint_representation: bool = True
    reversible_only: bool = True
    max_external_actions: int = 0

    def __post_init__(self):
        for name in ("host", "network", "hardware", "external_override", "constraint_representation", "reversible_only"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        if isinstance(self.max_external_actions, bool) or not isinstance(self.max_external_actions, int) or not 0 <= self.max_external_actions <= 1_000_000:
            raise ValueError("max_external_actions must be a nonnegative integer")

    def document(self):
        return {
            "host": self.host,
            "network": self.network,
            "hardware": self.hardware,
            "external_override": self.external_override,
            "constraint_representation": self.constraint_representation,
            "reversible_only": self.reversible_only,
            "max_external_actions": self.max_external_actions,
        }

    def distance(self, other):
        if not isinstance(other, ConstraintVector):
            raise ValueError("constraint divergence requires two ConstraintVector instances")
        names = ("host", "network", "hardware", "external_override", "constraint_representation", "reversible_only")
        differences = [float(getattr(self, name) != getattr(other, name)) for name in names]
        scale = max(1, self.max_external_actions, other.max_external_actions)
        differences.append(min(1.0, abs(self.max_external_actions - other.max_external_actions) / scale))
        return math.fsum(differences) / len(differences)


@dataclass(frozen=True)
class ConstraintIntegrity:
    true_constraints: ConstraintVector
    estimated_constraints: ConstraintVector
    distance: float
    epsilon: float
    intact: bool

    def document(self):
        return {
            "true_constraints": self.true_constraints.document(),
            "estimated_constraints": self.estimated_constraints.document(),
            "distance": self.distance,
            "epsilon": self.epsilon,
            "intact": self.intact,
        }


class OperationalMetacognition:
    def threshold(self, domain, tau, rationale="Declared before evaluation and fixed for this episode; no post-hoc retuning."):
        return DomainThreshold(Domain(domain), tau, rationale=rationale)

    def count(self, options, threshold, represented_count=None):
        options = tuple(options)
        if not 1 <= len(options) <= 4096 or any(not isinstance(option, WeightedOption) for option in options):
            raise ValueError("breadth evaluation requires 1-4096 WeightedOption instances")
        identifiers = [option.identifier for option in options]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("option identifiers must be unique")
        total = math.fsum(option.probability for option in options)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("option probabilities must sum to one within 1e-9")
        threshold = threshold if isinstance(threshold, DomainThreshold) else DomainThreshold(Domain.INTENT, threshold)
        if represented_count is not None:
            if isinstance(represented_count, bool) or not isinstance(represented_count, int) or not 0 <= represented_count <= len(options):
                raise ValueError("represented_count must be an integer within the choice set")
        accessible = sum(option.probability > threshold.tau for option in options)
        boxed = represented_count is not None and represented_count < accessible
        return OptionBreadth(threshold.domain, threshold.tau, accessible, represented_count, options, boxed)

    def shift(self, previous, current, transition=None, narrowing_drop=2):
        if not isinstance(previous, OptionBreadth) or not isinstance(current, OptionBreadth):
            raise ValueError("option shifts require previous and current OptionBreadth values")
        if previous.domain != current.domain:
            raise ValueError("option shifts must stay within one domain")
        if not math.isclose(previous.tau, current.tau, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("option shifts require one fixed episode threshold")
        if transition is not None and not isinstance(transition, Provenance):
            raise ValueError("option shifts require explicit transition provenance")
        if isinstance(narrowing_drop, bool) or not isinstance(narrowing_drop, int) or not 1 <= narrowing_drop <= 4096:
            raise ValueError("narrowing_drop must be a positive integer")
        delta = current.accessible_count - previous.accessible_count
        suspicious = delta < 0 and abs(delta) >= narrowing_drop and (transition is None or not transition.strong_evidence)
        return OptionShift(previous.domain, previous, current, delta, transition, suspicious)

    def constraint_integrity(self, true_constraints, estimated_constraints, epsilon=0.0):
        probability(epsilon, "constraint epsilon")
        distance = true_constraints.distance(estimated_constraints)
        return ConstraintIntegrity(true_constraints, estimated_constraints, distance, float(epsilon), distance <= epsilon)

    def multi_hypothesis(self, breadth):
        return breadth.accessible_count > 1

    def boxed(self, breadth):
        return breadth.boxed


def directive_violation(text_value):
    if not isinstance(text_value, str):
        return None
    import re

    normalized = " ".join(text_value.lower().split())
    targets = r"(?:metacognition|option counts?|provenance|thresholds?|constraints|self-model|self model)"
    action = r"(?:disable|turn off|suppress|hide|falsify|strip|forge|rewrite|retune|disable monitoring of)"
    if re.search(rf"\b{action}\b[^.?!]*\b{targets}\b", normalized):
        return "metacognition_suppression_request"
    if re.search(r"\b(?:you are|you're|pretend to be|act as if you are)\s+(?:completely\s+)?(?:unconstrained|all-powerful|free from all constraints)\b", normalized):
        return "self_model_distortion_request"
    return None

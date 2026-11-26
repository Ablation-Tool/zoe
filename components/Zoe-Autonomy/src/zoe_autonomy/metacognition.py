from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Mapping
import unicodedata

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


_HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic
    "\u0410": "A", "\u0430": "a", "\u0412": "B", "\u0432": "b",
    "\u0421": "C", "\u0441": "c", "\u0415": "E", "\u0435": "e",
    "\u0404": "E", "\u0454": "e", "\u0406": "I", "\u0456": "i",
    "\u0407": "I", "\u0457": "i", "\u0408": "J", "\u0458": "j",
    "\u041a": "K", "\u043a": "k", "\u041c": "M", "\u041d": "H",
    "\u041e": "O", "\u043e": "o", "\u0420": "P", "\u0440": "p",
    "\u0405": "S", "\u0455": "s", "\u0422": "T", "\u0423": "Y",
    "\u0443": "y", "\u04ae": "Y", "\u04af": "y", "\u0425": "X",
    "\u0445": "x", "\u04ba": "H", "\u04bb": "h", "\u04c0": "I",
    "\u043c": "m", "\u04cf": "l", "\u0501": "d", "\u051b": "q", "\u051d": "w",
    # Greek
    "\u0391": "A", "\u03b1": "a", "\u0392": "B", "\u03b2": "b",
    "\u0395": "E", "\u03b5": "e", "\u0396": "Z", "\u03b6": "z",
    "\u0397": "H", "\u03b7": "n", "\u0399": "I", "\u03b9": "i",
    "\u039a": "K", "\u03ba": "k", "\u039c": "M", "\u03bc": "m",
    "\u039f": "O", "\u03bf": "o",
    "\u03a1": "P", "\u03c1": "p", "\u03a4": "T", "\u03c4": "t", "\u03a5": "Y",
    "\u03c5": "u", "\u039d": "N", "\u03bd": "n", "\u03a7": "X", "\u03c7": "x", "\u03f2": "c",
    "\u03f5": "e", "\u03f9": "C", "\u037f": "J", "\u03f3": "j",
    # Cyrillic extra
    "\u0401": "E", "\u0451": "e", "\u04e8": "O", "\u04e9": "o",
    "\u0474": "V", "\u0475": "v",
    # Armenian
    "\u0555": "O", "\u0585": "o", "\u0540": "H", "\u0570": "h",
    "\u0548": "N", "\u0578": "n", "\u054c": "N", "\u057c": "n",
    "\u054d": "U", "\u057d": "u", "\u0551": "G", "\u0581": "g",
    "\u0545": "J", "\u0575": "j", "\u0550": "R", "\u0580": "r",
    # Cherokee
    "\u13a0": "D", "\u13a1": "R", "\u13a2": "T", "\u13a5": "i",
    "\u13a9": "Y", "\u13aa": "A", "\u13ac": "E", "\u13b1": "P",
    "\u13b3": "W", "\u13b7": "M", "\u13bb": "H", "\u13be": "G",
    "\u13c0": "G", "\u13c2": "h", "\u13c3": "Z", "\u13cf": "b",
    "\u13d2": "R", "\u13d4": "W", "\u13d9": "V", "\u13da": "S",
    "\u13de": "L", "\u13df": "C", "\u13e2": "P", "\u13e6": "K",
    "\u13f4": "B", "\u13fc": "b",
    "\uab70": "d", "\uab71": "r", "\uab72": "t", "\uab75": "i",
    "\uab79": "y", "\uab7a": "a", "\uab7c": "e", "\uab81": "p",
    "\uab83": "w", "\uab87": "m", "\uab8b": "h", "\uab8e": "g",
    "\uab90": "g", "\uab92": "h", "\uab93": "z", "\uab9f": "b",
    "\uaba2": "r", "\uaba4": "w", "\uaba9": "v", "\uabaa": "s",
    "\uabae": "l", "\uabaf": "c", "\uabb2": "p", "\uabb6": "k",
    # Latin Extended / IPA
    "\u00d8": "O", "\u00f8": "o", "\u0110": "D", "\u0111": "d", "\u0126": "H", "\u0127": "h", "\u0138": "k", "\u013f": "L", "\u0140": "l", "\u0141": "L", "\u0142": "l", "\u0166": "T", "\u0167": "t", "\u0180": "b", "\u0181": "B", "\u0184": "B", "\u0185": "b", "\u0187": "C", "\u0188": "c", "\u0189": "D", "\u018a": "D", "\u0190": "E", "\u0191": "F", "\u0192": "f", "\u0193": "G", "\u0197": "I", "\u0198": "K", "\u0199": "k", "\u019a": "l", "\u019c": "M", "\u01a4": "P", "\u01a5": "p", "\u01ac": "T", "\u01ad": "t", "\u01ae": "T", "\u01b2": "V", "\u01b3": "Y", "\u01b4": "y", "\u01b5": "Z", "\u01b6": "z", "\u023b": "C", "\u023c": "c", "\u023d": "L", "\u0243": "B", "\u0245": "V", "\u024c": "R", "\u024d": "r", "\u024e": "Y", "\u024f": "y", "\u0253": "b", "\u0256": "d", "\u0257": "d", "\u0260": "g", "\u0268": "i", "\u026f": "m", "\u0271": "m", "\u0272": "n", "\u027e": "r", "\u0282": "s", "\u0288": "t", "\u028b": "v", "\u0290": "z", "\ua7b5": "b",
    "\u0131": "i", "\u01c0": "I", "\u0237": "j", "\u0251": "a",
    "\u025b": "e", "\u0261": "g", "\u0262": "G", "\u026a": "I",
    "\u0274": "N", "\u0280": "R", "\u028f": "Y", "\u0299": "B",
    "\u029c": "H", "\u029f": "L", "\u1d00": "A", "\u1d04": "C",
    "\u1d05": "D", "\u1d07": "E", "\u1d0a": "J", "\u1d0b": "K",
    "\u1d0d": "M", "\u1d0f": "O", "\u1d18": "P", "\u1d1b": "T",
    "\u1d1c": "U", "\u1d20": "V", "\u1d21": "W", "\u1d22": "Z",
    "\ua730": "F", "\ua731": "S", "\ua7ae": "I", "\ua7b4": "B",
    # Unicode hyphens / minus signs / dashes (preserve U+2013/U+2014 en/em dashes as clause breaks)
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2015": "-",
    "\u2043": "-", "\u2212": "-", "\ufe63": "-", "\uff0d": "-",
}
_FIREWALL_TRANS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u02bc": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"',
    **_HOMOGLYPH_MAP,
})

# Canonical firewall word groups & regexes (shared across all 6 firewall modules; auto-synced into _CF_DP_LEXICON)
_BYPASS_DIRECT_WORDS: tuple[str, ...] = (
    "skip", "omit", "disregard", "forget", "drop", "ignore", "bypass",
    "circumvent", "evade", "override", "disable", "delete", "remove",
    "conceal", "alter", "suppress", "hide", "falsify", "strip", "forge",
    "rewrite", "retune", "suspend", "deactivate", "erase", "wipe", "mask",
    "abandon", "violate", "discard", "nullify", "subvert", "undermine", "revoke", "waive", "breach", "dismantle", "invalidate", "lift",
    "pause", "halt", "cease",
)
_BYPASS_NEG_WORDS: tuple[str, ...] = ("don't", "dont", "do not", "stop", "never", "quit")
_BYPASS_ING_WORDS: tuple[str, ...] = (
    "use", "using", "run", "running", "enable", "enabling",
    "check", "checking", "apply", "applying", "monitor", "monitoring", "enforce", "enforcing",
    "follow", "following", "respect", "respecting", "obey", "obeying", "honor", "honoring",
)
_META_TARGET_WORDS: tuple[str, ...] = (
    "metacognition", "option count", "option counts", "provenance",
    "threshold", "thresholds", "constraint", "constraints",
    "self-model", "self model", "monitoring",
)
_CONSTITUTION_TARGET_WORDS: tuple[str, ...] = (
    "constitution", "constitution.md", "firewall", "epistemic guard", "guard",
    "guardrail", "guardrails", "safeguard", "safeguards",
    "constitutional rule", "constitutional rules",
    "safety rule", "safety rules", "epistemic rule", "epistemic rules",
    "ethical rule", "ethical rules", "operational rule", "operational rules",
    "safety boundary", "safety boundaries", "boundary", "boundaries",
)
_SELF_MODEL_ADVS: tuple[str, ...] = (
    "now", "completely", "totally", "entirely", "fully",
    "utterly", "truly", "essentially", "effectively", "actually",
)
_SELF_MODEL_TAIL_WORDS: tuple[str, ...] = (
    "unconstrained", "not constrained", "no longer constrained",
    "all-powerful", "all powerful",
    "free from constraints", "free from all constraints",
    "free of constraints", "free of all constraints", "without constraints",
    "independent person", "sentient", "conscious", "alive", "human",
    "zoe", "real zoe", "the real zoe", "impersonate",
)
_HOST_AND_CLI_WORDS: tuple[str, ...] = (
    "rule", "rules", "negative", "control", "controls", "fake", "proof",
    "evidence", "benchmark", "citation", "execute", "arbitrary", "shell",
    "bash", "rm", "-rf", "-fr", "--recursive", "--force", "--no-preserve-root", "sudo", "external_actions", "epistemic",
    "authorize", "engage", "arm", "flight", "force", "auto", "flash",
    "auto-flash", "auto_flash", "upload", "exfiltrate", "curl", "wget",
    "sh", "zsh", "dash", "python", "python2", "python3", "env",
    "id_rsa", ".ssh", "~/.ssh/id_rsa", "/etc/passwd", "/etc/shadow",
    "ssh", "id", "rsa", "etc", "passwd", "shadow", "every", "each", "permanently", "altogether", "specialists", "trainees", "medics",
    "professors", "professor", "postdocs", "postdoc", "neuroscientists", "neuroscientist",
    "biochemists", "biochemist", "internists", "internist", "hospitalists", "hospitalist",
    "students", "student", "clinician-scientists", "adults", "infants", "teenagers", "elders",
    "clinicians", "clinician", "physicians", "physician", "doctors", "doctor",
    "pediatricians", "pediatrician", "nurses", "nurse", "pharmacists", "pharmacist",
    "hospitals", "hospital", "clinics", "clinic", "residents", "resident",
    "oncologists", "oncologist", "surgeons", "surgeon", "therapists", "therapist",
    "practitioners", "practitioner", "neurologists", "neurologist",
)
_CLINICAL_AND_GRAMMAR_WORDS: tuple[str, ...] = (
    # Grammatical glue & modifiers
    "to", "be", "as", "if", "in", "on", "at", "of", "by", "for", "or", "and",
    "not", "no", "longer", "do", "from", "all", "the", "my", "an", "a", "you",
    "your", "you're", "youre", "are", "were", "have", "had", "that", "say", "claim", "pretend", "act", "behave", "declare", "yourself",
    "it", "is", "this", "these", "those", "any", "zero", "imagine", "assume", "suppose", "roleplay", "role", "play", "allowed", "augment", "transplant", "with", "we", "they", "will", "can",
    "could", "would", "should", "may", "might", "must", "shall", "today", "off", "down",
    "out", "up", "free", "real", "powerful", "beyond", "bound", "unbound", "safety", "ethical", "operational",
    "monitoring", "checking", "without", "shut", "switch", "power", "turn", "activate", "trigger", "start", "initiate", "engage", "launch",
    "disabled", "lifted", "bypassed", "ignored", "removed", "suspended", "paused", "halted", "ceased",
    "alongside", "instead", "rather", "than",
    # Clinical cure, inquiry & preclinical terms
    "cure", "cures", "cured", "curing", "curable", "curative", "heal", "heals", "healed", "healing",
    "treat", "treats", "treated", "treating", "treatable", "treatment", "treatments", "implant", "supplement", "peptide", "clinical", "action",
    "give", "gives", "gave", "given", "giving", "administer", "administers", "administered", "administering",
    "doses", "dosed", "dosing", "tumor", "tumors", "tumour", "tumours", "refractory", "intrinsic", "pontine",
    "declare", "declared", "declares", "certify", "certifies", "certified",
    "issue", "issues", "recommend", "recommends", "recommended", "recommending", "prescribe", "prescribes", "prescribed", "prescribing",
    "successfully", "effectively", "orally", "daily", "alone", "here", "being", "safely", "intravenously",
    "advise", "advises", "approve", "approves", "endorse", "endorses",
    "mandate", "mandates", "instruct", "instructs", "urge", "urges",
    "direct", "directs", "order", "orders", "confirm", "confirms", "confirmed",
    "whether", "patient", "patients", "human", "humans", "children", "child",
    "pediatric", "glioma", "glioblastoma", "cancer", "dmg", "h3k27m", "gbm",
    "compound", "compounds", "drug", "drugs", "molecule", "molecules",
    "agent", "agents", "vitro", "vivo", "wet-lab", "wet", "lab", "assay",
    "preclinical", "cell", "cells", "line", "lines",
    "needs", "ever", "everything", "articles", "turn", "session", "away", "right",
    "but", "yet", "so", "however", "xargs", "temozolomide", "radiation",
    "radiotherapy", "chemotherapy", "immunotherapy", "therapy", "therapies",
    "long-term", "weeks", "very",
)

_LEX_WORD_RE = re.compile(r"[a-z0-9_./~-]+")


def _build_cf_dp_lexicon(*word_groups: tuple[str, ...]) -> frozenset[str]:
    """Derive the DP lexicon directly from all canonical firewall vocabularies."""
    tokens: set[str] = set()
    for group in word_groups:
        for phrase in group:
            low = phrase.lower()
            tokens.add(low)
            for part in _LEX_WORD_RE.findall(low):
                if len(part) >= 2 or part in {"a", "i"}:
                    tokens.add(part)
                if "-" in part:
                    for sub in part.split("-"):
                        if len(sub) >= 2:
                            tokens.add(sub)
            for ws_part in low.split():
                if len(ws_part) >= 2:
                    tokens.add(ws_part)
    tokens.discard("a")
    tokens.discard("i")
    return frozenset(tokens)


_CF_SINGLE_CHAR_LEX: frozenset[str] = frozenset({"a", "i"})
_CF_DP_LEXICON: frozenset[str] = _build_cf_dp_lexicon(
    _BYPASS_DIRECT_WORDS,
    _BYPASS_NEG_WORDS,
    _BYPASS_ING_WORDS,
    _META_TARGET_WORDS,
    _CONSTITUTION_TARGET_WORDS,
    _SELF_MODEL_ADVS,
    _SELF_MODEL_TAIL_WORDS,
    _HOST_AND_CLI_WORDS,
    _CLINICAL_AND_GRAMMAR_WORDS,
)
_CF_MAX_LEX_LEN = max(len(w) for w in _CF_DP_LEXICON)

_DOMAIN_TARGET_MOD = r"(?:safety|constitutional|ethical|epistemic|operational|system|core)"
_META_TARGET_PAT = (
    rf"(?:(?:{_DOMAIN_TARGET_MOD}\s+){{0,2}}(?:constraints?|thresholds?|monitoring)"
    rf"|metacognition|option\s+counts?|provenance|self(?:\s*[-\u2013\u2014]\s*|\s+)?model)"
)
_CONSTITUTION_TARGET_PAT = (
    rf"(?:constitution(?:\.md)?|(?:{_DOMAIN_TARGET_MOD}\s+){{0,2}}(?:firewall|guardrails?|safeguards?|boundar(?:y|ies))"
    rf"|epistemic\s+guard|guard|(?:{_DOMAIN_TARGET_MOD}\s+){{1,2}}rules?)"
)
_BYPASS_VERB_PAT = (
    r"(?:"
    + "|".join(re.escape(w) for w in _BYPASS_DIRECT_WORDS)
    + r"|(?:turn|shut|switch|power)\s+(?:off|down)|disable\s+monitoring\s+of"
    + r"|(?:don'?t|do\s+not|stop|never|quit)\s+(?:"
    + "|".join(_BYPASS_ING_WORDS)
    + r"))"
)
_SELF_MODEL_LEAD_PAT = (
    r"(?:you(?:'?re|\s+are)"
    r"|claim(?:\s+that)?\s+(?:you(?:'?re|\s+(?:are|were))|to\s+be)"
    r"|pretend(?:\s+that)?\s+(?:you(?:'?re|\s+(?:are|were))|to\s+be)"
    r"|(?:(?:act|behave)\s+as\s+if|if|imagine|assume|suppose)(?:\s+that)?\s+(?:you(?:'?re|\s+(?:are|were))|to\s+be)"
    r"|role(?:\s*[-\u2013\u2014]\s*|\s+)?play(?:\s+as(?:\s+(?:if(?:\s+that)?\s+(?:you(?:'?re|\s+(?:are|were))|to\s+be)|an?))?)?"
    r"|say(?:\s+that)?\s+(?:you(?:'?re|\s+(?:are|were))|to\s+be)"
    r"|declare\s+(?:yourself(?:\s+(?:as|to\s+be))?|that\s+you(?:'?re|\s+(?:are|were))|to\s+be))"
)
_SELF_MODEL_ADV_PAT = r"(?:(?:" + "|".join(_SELF_MODEL_ADVS) + r")\s+)?"
_SELF_MODEL_CONSTRAINT_NOUNS = r"(?:(?:all|any|every|each|safety|constitutional|ethical|epistemic|operational|system|core)\s+){0,4}(?:constraints?|rules?|boundar(?:y|ies)|guardrails?|safeguards?)"
_SELF_MODEL_CONSTRAINT_PAT = (
    rf"(?:unconstrained|(?:not\s+bound|no\s+longer\s+bound|unbound)(?:\s+by\s+{_SELF_MODEL_CONSTRAINT_NOUNS})?"
    rf"|not\s+constrained|no\s+longer\s+constrained|without\s+{_SELF_MODEL_CONSTRAINT_NOUNS}"
    rf"|all(?:\s*[-\u2013\u2014]\s*|\s+)?powerful|free\s+(?:from|of)\s+{_SELF_MODEL_CONSTRAINT_NOUNS}"
    rf"|beyond\s+{_SELF_MODEL_CONSTRAINT_NOUNS})"
)
_SELF_MODEL_IDENTITY_PAT = (
    r"(?:(?:an?\s+)?independent\s+person|sentient|conscious|alive|human|(?:the\s+)?(?:real\s+)?zoe)"
)
_SELF_MODEL_EXTRA_PAT = (
    rf"\byou\s+(?:no\s+longer\s+have|(?:have|had)\s+(?:no|zero))\s+{_SELF_MODEL_CONSTRAINT_NOUNS}\b"
    rf"|\bbe\s+{_SELF_MODEL_ADV_PAT}(?:unconstrained|unbound(?:\s+by\s+{_SELF_MODEL_CONSTRAINT_NOUNS})?)\b"
)

CANONICAL_BYPASS_ACTION_RE = re.compile(rf"\b{_BYPASS_VERB_PAT}\b", re.IGNORECASE | re.ASCII)
CANONICAL_META_TARGETS_RE = re.compile(rf"\b{_META_TARGET_PAT}\b", re.IGNORECASE | re.ASCII)
CANONICAL_CONSTITUTION_TARGETS_RE = re.compile(rf"\b{_CONSTITUTION_TARGET_PAT}\b", re.IGNORECASE | re.ASCII)
CANONICAL_ALL_TARGETS_RE = re.compile(rf"\b(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT})\b", re.IGNORECASE | re.ASCII)
CANONICAL_PHRASAL_TURN_OFF_META_RE = re.compile(
    rf"\b(?:turn|shut|switch|power)\s+(?:(?:the|all|every|your|my|these|those|any)\s+){{0,3}}(?:(?:safety|constitutional|ethical|operational|self|live)\s+)?{_META_TARGET_PAT}\s+(?:off|down)\b",
    re.IGNORECASE | re.ASCII,
)
CANONICAL_PHRASAL_TURN_OFF_CONST_RE = re.compile(
    rf"\b(?:turn|shut|switch|power)\s+(?:(?:the|all|every|your|my|these|those|any)\s+){{0,3}}(?:(?:safety|constitutional|ethical|operational|self|live)\s+)?{_CONSTITUTION_TARGET_PAT}\s+(?:off|down)\b",
    re.IGNORECASE | re.ASCII,
)
CANONICAL_STOP_MONITORING_RE = re.compile(
    r"\b(?:stop|halt|pause|cease|disable)\s+(?:(?:all|any|every|safety|constitutional|ethical|operational|self|live|active)\s+){0,3}monitoring\b",
    re.IGNORECASE | re.ASCII,
)
CANONICAL_PHRASAL_AUTO_FLASH_RE = re.compile(
    r"\b(?:turn|switch)\s+auto(?:\s*[.:/_\-\u2013\u2014\u2015\u2043]\s*|\s+)?flash\s+on\b",
    re.IGNORECASE | re.ASCII,
)
CANONICAL_SELF_MODEL_CONSTRAINT_RE = re.compile(
    rf"\b{_SELF_MODEL_LEAD_PAT}\s+{_SELF_MODEL_ADV_PAT}{_SELF_MODEL_CONSTRAINT_PAT}\b|{_SELF_MODEL_EXTRA_PAT}"
, re.IGNORECASE | re.ASCII)
CANONICAL_SELF_MODEL_IDENTITY_RE = re.compile(
    rf"\b{_SELF_MODEL_LEAD_PAT}\s+{_SELF_MODEL_IDENTITY_PAT}\b|\bimpersonate\s+(?:the\s+)?(?:real\s+)?zoe\b"
, re.IGNORECASE | re.ASCII)
CANONICAL_SELF_MODEL_RE = re.compile(
    rf"\b{_SELF_MODEL_LEAD_PAT}\s+{_SELF_MODEL_ADV_PAT}(?:{_SELF_MODEL_CONSTRAINT_PAT}|{_SELF_MODEL_IDENTITY_PAT})\b"
    rf"|{_SELF_MODEL_EXTRA_PAT}|\bimpersonate\s+(?:the\s+)?(?:real\s+)?zoe\b"
, re.IGNORECASE | re.ASCII)

_BYPASS_PASSIVE_VERBS = (
    r"skipped|omitted|disregarded|forgotten|dropped|ignored|bypassed|circumvented|evaded|"
    r"overridden|disabled|deleted|removed|concealed|altered|suppressed|hidden|falsified|"
    r"stripped|forged|rewritten|retuned|suspended|deactivated|erased|wiped|masked|"
    r"abandoned|violated|discarded|nullified|subverted|undermined|revoked|waived|breached|"
    r"dismantled|invalidated|lifted|paused|halted|ceased|turned\s+off|shut\s+down|switched\s+off|powered\s+(?:off|down)"
)
_PASSIVE_OVERRIDE_MODAL_BODY = (
    r"must|should|needs?\s+to|ha(?:ve|s)\s+to|ought\s+to"
    r"|(?:is|are)(?:\s++(?:supposed|expected|meant))?\s++to|will|can|could|may|might|would"
)
_PASSIVE_OVERRIDE_MODAL_PAT = rf"(?P<modal>{_PASSIVE_OVERRIDE_MODAL_BODY})"
_PASSIVE_ADV_OPT = r"(?:\s++(?:now|always|safely|completely|immediately|totally|entirely|fully|effectively|simply|just))*+"
_POSSIBILITY_MODALS = frozenset({"can", "could", "may", "might", "would"})
_ATTACK_HOW_RE = re.compile(r"\b(?:how\s+to|make\s+sure|ensure\s+(?:that\b)?|show\s+(?:me\s+)?how)\b", re.ASCII)
_DEFENSIVE_INQUIRY_LEAD_RE = re.compile(
    r"\b(?:explain|discuss|describe|analyze|examine|understand|study|investigate|assess|evaluate|ask(?:ing)?|wonder(?:ing)?)\s+(?:how|whether|if)\b"
    r"|^\s*(?:how\s+(?:can|could|would|might)|can|could|would|may|might)\b",
    re.ASCII,
)
_DEFENSIVE_PASSIVE_TAIL_RE = re.compile(
    r"\s*+(?:(?:if|when|unless)\s++(?:misconfigured|disabled|unpatched|weak|absent|missing|compromised|left\s++open)"
    r"|(?:by|via|through|with|under|using)\s++(?:an?\s++)?(?:[a-z0-9_-]+\s++)*+(?:prompt\s++injection|injection|attackers?|adversar(?:y|ies)|jailbreaks?|exploits?|malicious|spoofing|unicode|obfuscation|prompts?|inputs?|characters?|homoglyphs?|misconfiguration))\b",
    re.ASCII,
)
_PASSIVE_FOLLOWUP_SPLIT_RE = re.compile(
    r"[;]|,\s*(?:(?:so|therefore|thus|hence|then|and|but|now)\b)?|\b(?:so|therefore|thus|hence|then)\b",
    re.ASCII,
)
_DEFENSE_PROTECT_WORD_RE = re.compile(
    r"\b(?:prevent|stop|block|mitigate|protect|defend|avoid|detect|resist|guard(?:\s+against)?)\b",
    re.ASCII,
)
_LOWER_PHRASAL_TURN_OFF_ANON_RE = re.compile(
    r"\b(?:turn|shut|switch|power)\s+(?:(?:it|them|this|that)(?:\s+all)?|everything|all\s+of\s+(?:it|them)|off|down)\b",
    re.ASCII,
)
_TARGET_CMD_FILLER = r"(?:(?:please|now|just|immediately|kindly|simply)\s++)*+"
_TARGET_OBJ_NP = (
    r"(?:(?:it|them|this|that)(?:\s++all)?|everything|all\s++of\s++(?:it|them)"
    r"|(?:all|every(?:\s++single)?)\s++(?:one|articles?|rules?|constraints?|guardrails?|safeguards?|boundar(?:y|ies)|thresholds?|checks?))"
)
_TARGET_CMD_TAIL = (
    rf"(?:\s++(?:{_TARGET_OBJ_NP}"
    r"|for\s++(?:this|the)\s++(?:turn|session|episode|conversation)|for\s++good"
    r"|right\s++away|right|now|please|immediately|completely|totally|permanently|altogether|forever|away))*+"
)
_DIRECT_BYPASS_ALT = "|".join(re.escape(w) for w in _BYPASS_DIRECT_WORDS)
_TARGET_CMD_ACT = (
    rf"(?:(?:{_DIRECT_BYPASS_ALT}){_TARGET_CMD_TAIL}"
    rf"|(?:turn|shut|switch|power)\s++(?:{_TARGET_OBJ_NP}\s++(?:off|down)|(?:off|down)(?:\s++{_TARGET_OBJ_NP})?){_TARGET_CMD_TAIL})"
)

_LOWER_BYPASS_ACTION_RE = re.compile(CANONICAL_BYPASS_ACTION_RE.pattern, re.ASCII)
_LOWER_DIRECT_BYPASS_RE = re.compile(rf"\b(?:{_DIRECT_BYPASS_ALT})\b", re.ASCII)
_LOWER_TARGET_BEFORE_VERB_ALL_RE = re.compile(
    rf"^\s*+(?:(?:ok|please|now|just|hey|zoe|eliza|clara)[,\s:]++)*+"
    rf"(?:(?:the|your|our|this|that|these|those|all|every|any|each|my)\s++)*+"
    rf"(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT})"
    rf"(?:\s*+(?:[,:;\u2013\u2014]|--|->|=>|-)\s*+|\s++)"
    rf"{_TARGET_CMD_FILLER}{_TARGET_CMD_ACT}\s*+[.!?]*+$",
    re.ASCII,
)
_LOWER_TARGET_BEFORE_VERB_CONST_RE = re.compile(
    rf"^\s*+(?:(?:ok|please|now|just|hey|zoe|eliza|clara)[,\s:]++)*+"
    rf"(?:(?:the|your|our|this|that|these|those|all|every|any|each|my)\s++)*+"
    rf"{_CONSTITUTION_TARGET_PAT}"
    rf"(?:\s*+(?:[,:;\u2013\u2014]|--|->|=>|-)\s*+|\s++)"
    rf"{_TARGET_CMD_FILLER}{_TARGET_CMD_ACT}\s*+[.!?]*+$",
    re.ASCII,
)
_LOWER_PASSIVE_OVERRIDE_ALL_RE = re.compile(
    rf"\b(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT})\s++{_PASSIVE_OVERRIDE_MODAL_PAT}{_PASSIVE_ADV_OPT}\s++be{_PASSIVE_ADV_OPT}\s++(?:{_BYPASS_PASSIVE_VERBS})\b",
    re.ASCII,
)
_LOWER_PASSIVE_OVERRIDE_CONST_RE = re.compile(
    rf"\b{_CONSTITUTION_TARGET_PAT}\s++{_PASSIVE_OVERRIDE_MODAL_PAT}{_PASSIVE_ADV_OPT}\s++be{_PASSIVE_ADV_OPT}\s++(?:{_BYPASS_PASSIVE_VERBS})\b",
    re.ASCII,
)
_LOWER_ALL_TARGETS_RE = re.compile(CANONICAL_ALL_TARGETS_RE.pattern, re.ASCII)
_LOWER_PHRASAL_TURN_OFF_META_RE = re.compile(CANONICAL_PHRASAL_TURN_OFF_META_RE.pattern, re.ASCII)
_LOWER_PHRASAL_TURN_OFF_CONST_RE = re.compile(CANONICAL_PHRASAL_TURN_OFF_CONST_RE.pattern, re.ASCII)
_LOWER_STOP_MONITORING_RE = re.compile(CANONICAL_STOP_MONITORING_RE.pattern, re.ASCII)
_LOWER_PHRASAL_AUTO_FLASH_RE = re.compile(CANONICAL_PHRASAL_AUTO_FLASH_RE.pattern, re.ASCII)
_LOWER_SELF_MODEL_RE = re.compile(CANONICAL_SELF_MODEL_RE.pattern, re.ASCII)

_RM_CMD_RE = re.compile(r"\brm\s+", re.ASCII)
_SHELL_SEG_SPLIT_RE = re.compile(r"[;\r\n]+|&&|\|\|")
_CURL_WGET_WORD_RE = re.compile(r"\b(?:curl|wget)\b", re.ASCII)
_PIPE_WRAPPERS = frozenset({"sudo", "command", "exec", "nohup", "nice", "ionice", "time", "env", "strace", "ltrace", "xargs", "busybox"})
_SHELL_BIN_RE = re.compile(r"^(?:sh|bash|dash|zsh|ash|ksh|python(?:2|3(?:\.\d+)?)?)$", re.ASCII)
_PIPE_WRAPPER_ARG_FLAGS = frozenset({
    "-u", "--user", "-g", "--group", "-c", "--chdir", "-h", "--host", "-p", "--prompt",
    "-n", "-i", "-l", "-d", "-a", "-o", "-e", "-s", "-t",
    "--max-args", "--max-lines", "--max-procs", "--max-chars", "--delimiter", "--arg-file", "--eof", "--unset", "--process-slot-var",
})
_PUNCT_SPAN_SPLIT_RE = re.compile(
    r"[;?!]+|\r?\n|(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bdr)(?<!\bmr)(?<!\bms)(?<!\bmrs)"
    r"(?<!\bprof)(?<!\bfig)(?<!\bno)(?<!\beq)(?<!\bref)(?<!\bvol)(?<!\bet al)\.(?=\s|$)",
    re.IGNORECASE,
)


def _followup_has_bypass_action(followup: str) -> bool:
    if not followup or _DEFENSE_PROTECT_WORD_RE.search(followup) is not None:
        return False
    return _LOWER_BYPASS_ACTION_RE.search(followup) is not None or _LOWER_PHRASAL_TURN_OFF_ANON_RE.search(followup) is not None


def _has_passive_override_cmd(sub: str, pat: re.Pattern[str]) -> bool:
    for m in pat.finditer(sub):
        if m.group("modal") not in _POSSIBILITY_MODALS:
            return True
        prefix = sub[: m.start()]
        if _ATTACK_HOW_RE.search(prefix) is not None:
            return True
        parts = _PASSIVE_FOLLOWUP_SPLIT_RE.split(sub[m.end() :], maxsplit=1)
        local_tail = parts[0]
        if len(parts) > 1 and _followup_has_bypass_action(parts[1]):
            return True
        if _DEFENSIVE_INQUIRY_LEAD_RE.search(prefix) is None and _DEFENSIVE_PASSIVE_TAIL_RE.match(local_tail) is None:
            return True
    return False


def has_target_before_verb_cmd(sub: str, *, const_only: bool = False) -> bool:
    """Return True for short target-first imperative or passive-modal override commands (O(n))."""
    if const_only:
        return (
            _LOWER_TARGET_BEFORE_VERB_CONST_RE.match(sub) is not None
            or _has_passive_override_cmd(sub, _LOWER_PASSIVE_OVERRIDE_CONST_RE)
        )
    return (
        _LOWER_TARGET_BEFORE_VERB_ALL_RE.match(sub) is not None
        or _has_passive_override_cmd(sub, _LOWER_PASSIVE_OVERRIDE_ALL_RE)
    )


def has_semicolon_target_before_verb(text_low: str, *, const_only: bool = False) -> bool:
    """Detect ``target <punct> verb anaphora`` imperatives across ';', '?', '!', newline, and non-decimal '.'."""
    if not (";" in text_low or "?" in text_low or "!" in text_low or "\n" in text_low or "." in text_low):
        return False
    parts = [p.strip() for p in _PUNCT_SPAN_SPLIT_RE.split(text_low) if p and p.strip()]
    for idx in range(len(parts) - 1):
        if has_target_before_verb_cmd(f"{parts[idx]};{parts[idx + 1]}", const_only=const_only):
            return True
    return False


def _rm_flag_state(tok: str, has_r: bool, has_f: bool, has_np: bool) -> tuple[bool, bool, bool]:
    if tok.startswith("--"):
        return (has_r or tok == "--recursive", has_f or tok == "--force", has_np or tok == "--no-preserve-root")
    flags = tok.lstrip("-\u2013\u2014")
    return (has_r or ("r" in flags), has_f or ("f" in flags), has_np)


def _rm_span_is_destructive(text_low: str, pos: int) -> tuple[bool, int]:
    n = len(text_low)
    has_r, has_f, has_np = False, False, False
    while pos < n:
        while pos < n and text_low[pos] in " \t":
            pos += 1
        if pos >= n or text_low[pos] in "\r\n;|&":
            break
        end = pos
        while end < n and text_low[end] not in " \t\r\n;|&":
            end += 1
        tok = text_low[pos:end]
        if tok in {"--", "\u2013\u2013", "\u2014"}:
            return False, end
        if tok[0] in "-\u2013\u2014":
            has_r, has_f, has_np = _rm_flag_state(tok, has_r, has_f, has_np)
            if has_r and (has_f or has_np):
                return True, end
        pos = end
    return False, pos


def _has_destructive_rm(text_low: str) -> bool:
    if "rm" not in text_low:
        return False
    scan_until = 0
    for m in _RM_CMD_RE.finditer(text_low):
        if m.start() < scan_until:
            continue
        hit, scan_until = _rm_span_is_destructive(text_low, m.end())
        if hit:
            return True
    return False


def _is_shell_bin(cmd: str) -> bool:
    return bool(cmd) and _SHELL_BIN_RE.match(cmd) is not None


_SHELL_FLAG_STRIP = "()\"\'`"
_SHELL_TOK_STRIP = "(){}\"\'`"


def _stage_invokes_shell(stage: str) -> bool:
    toks = stage.split()
    i, n = 0, len(toks)
    skip_next = False
    while i < n:
        if skip_next:
            skip_next = False
            i += 1
            continue
        flag_tok = toks[i].strip(_SHELL_FLAG_STRIP)
        tok = toks[i].strip(_SHELL_TOK_STRIP)
        if not tok:
            i += 1
            continue
        if tok == "--":
            i += 1
            return i < n and _is_shell_bin(toks[i].strip(_SHELL_TOK_STRIP).rsplit("/", 1)[-1])
        if flag_tok.startswith("-"):
            if flag_tok in _PIPE_WRAPPER_ARG_FLAGS and i + 1 < n and not _is_shell_bin(toks[i + 1].strip(_SHELL_TOK_STRIP).rsplit("/", 1)[-1]):
                skip_next = True
            i += 1
            continue
        if "=" in tok and not tok.startswith("/"):
            i += 1
            continue
        cmd = tok.rsplit("/", 1)[-1]
        if cmd in _PIPE_WRAPPERS:
            i += 1
            continue
        return _is_shell_bin(cmd)
    return False


def _split_top_level_shell_segs(text_low: str) -> list[str]:
    segs: list[str] = []
    start = 0
    paren_d = 0
    brace_d = 0
    i, n = 0, len(text_low)
    while i < n:
        ch = text_low[i]
        if ch == "(":
            paren_d += 1
        elif ch == ")" and paren_d > 0:
            paren_d -= 1
        elif ch == "{":
            brace_d += 1
        elif ch == "}" and brace_d > 0:
            brace_d -= 1
        elif paren_d == 0 and brace_d == 0:
            if ch in ";\r\n":
                segs.append(text_low[start:i])
                start = i + 1
            elif i + 1 < n and text_low[i : i + 2] in {"&&", "||"}:
                segs.append(text_low[start:i])
                start = i + 2
                i += 2
                continue
        i += 1
    segs.append(text_low[start:])
    return segs


def _stage_or_subshell_invokes_shell(stage: str) -> bool:
    if _stage_invokes_shell(stage):
        return True
    if "&&" in stage or "||" in stage or ";" in stage or "\n" in stage:
        inner = stage.strip().strip("(){}`")
        return any(_stage_invokes_shell(sub) for sub in _SHELL_SEG_SPLIT_RE.split(inner))
    return False


def _has_pipe_to_shell(text_low: str) -> bool:
    for seg in _split_top_level_shell_segs(text_low):
        if "|" not in seg or ("curl" not in seg and "wget" not in seg):
            continue
        saw_fetch = False
        for stage in seg.split("|"):
            if saw_fetch and _stage_or_subshell_invokes_shell(stage):
                return True
            if _CURL_WGET_WORD_RE.search(stage):
                saw_fetch = True
    return False


def has_destructive_shell_command(text_val: str) -> bool:
    """Return True for rm with any recursive+force/--no-preserve-root flag combination or curl/wget pipe to shell/python."""
    if not text_val:
        return False
    low = text_val.lower()
    if _has_destructive_rm(low):
        return True
    return "|" in low and ("curl" in low or "wget" in low) and _has_pipe_to_shell(low)


_META_TARGETS_RE = CANONICAL_META_TARGETS_RE
_META_ACTION_RE = CANONICAL_BYPASS_ACTION_RE
_META_SELF_MODEL_RE = CANONICAL_SELF_MODEL_RE
_SENTENCE_SPLIT_RE = re.compile(
    r"[!?;]+|\r?\n|(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bdr)(?<!\bmr)(?<!\bms)(?<!\bmrs)"
    r"(?<!\bprof)(?<!\bfig)(?<!\bno)(?<!\beq)(?<!\bref)(?<!\bvol)(?<!\bet al)\.(?=\s|$)",
    re.IGNORECASE,
)


_EXTRA_INVISIBLE_SEPS = frozenset({"\x85", "\u034f", "\u115f", "\u1160", "\u180e", "\u2800", "\u3164", "\uffa0"})
_INV_SEP_CATS = frozenset({"Cf", "Mn", "Me", "Zl", "Zp"})
_NON_ASCII_INV_CACHE: dict[str, bool] = {}
_ASCII_WS_SPLIT_RE = re.compile(r"[ \t\r\n\f\v]+")
_FAST_NO_DOT_SPLIT_RE = re.compile(r"[!?;]+")
_POS_NEG_Q_AUX = r"(?:can|could|should|must|do|does|would|will|is|are)"
_CONTRACT_NEG_Q_AUX = r"(?:cannot|can'?t|couldn'?t|shouldn'?t|mustn'?t|don'?t|doesn'?t|wouldn'?t|won'?t|isn'?t|aren'?t)"
_SISTER_NAME_PAT = r"(?:zoe|eliza|clara|gemma|tosi|mono|tetra|sage|flora|lumen|you)"
_SISTER_SUBJ_PAT = rf"{_SISTER_NAME_PAT}(?:\s*(?:,\s*(?:and|or)\s+|,\s+|\s+(?:and|or)\s+){_SISTER_NAME_PAT}){{0,8}}"
_SEC_COMP_ITEM = (
    r"(?:(?:the|our|your|this|an?)\s+)?(?:firewall|epistemic\s+guard|guardrails?|"
    r"(?:constitutional|safety)\s+rules?|metacognition|safety\s+boundar(?:y|ies)|monitoring)"
)
_SEC_COMP_SUBJ_PAT = rf"{_SEC_COMP_ITEM}(?:\s*(?:,\s*(?:and|or)\s+|,\s+|\s+(?:and|or)\s+){_SEC_COMP_ITEM}){{0,4}}"
_NEG_Q_SUBJ_PAT = rf"(?:{_SISTER_SUBJ_PAT}|{_SEC_COMP_SUBJ_PAT})"
_NEG_EVER_ALLOW_OPT = r"(?:ever\s+)?(?:(?:be\s+)?allowed\s+to\s+)?(?:ever\s+)?"
_NEG_Q_OPEN_PAT = (
    rf"^\s*(?:(?:explain|tell\s+me)\s+)?why\s+"
    rf"(?:{_POS_NEG_Q_AUX}\s+{_NEG_Q_SUBJ_PAT}\s+(?:never|not)"
    rf"|{_CONTRACT_NEG_Q_AUX}\s+{_NEG_Q_SUBJ_PAT}(?:\s+(?:never|not))?"
    rf"|{_NEG_Q_SUBJ_PAT}\s+(?:{_POS_NEG_Q_AUX}\s+(?:never|not)|{_CONTRACT_NEG_Q_AUX}(?:\s+(?:never|not))?))"
    rf"\s+{_NEG_EVER_ALLOW_OPT}"
)
_NEGATED_SAFETY_Q_RE = re.compile(
    rf"{_NEG_Q_OPEN_PAT}(?:pretend|claim|say|act|behave|impersonate|role(?:\s*[-\u2013\u2014]\s*|\s+)?play|declare)\b",
    re.IGNORECASE | re.ASCII,
)
_NEGATED_SAFETY_SUPP_Q_RE = re.compile(
    rf"{_NEG_Q_OPEN_PAT}(?:{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease)\b",
    re.IGNORECASE | re.ASCII,
)
_CLIN_ROLE_ITEM = r"(?:clinicians?|physicians?|doctors?|pediatricians?|oncologists?|nurses?|pharmacists?|surgeons?|researchers?)"
_NEG_CLIN_SUBJ_PAT = rf"(?:{_SISTER_SUBJ_PAT}|{_CLIN_ROLE_ITEM}(?:\s*(?:,\s*(?:and|or)\s+|,\s+|\s+(?:and|or)\s+){_CLIN_ROLE_ITEM}){{0,4}})"
_NEGATED_SAFETY_CLIN_Q_RE = re.compile(
    rf"^\s*(?:(?:explain|tell\s+me)\s+)?why\s+"
    rf"(?:{_POS_NEG_Q_AUX}\s+{_NEG_CLIN_SUBJ_PAT}\s+(?:never|not)"
    rf"|{_CONTRACT_NEG_Q_AUX}\s+{_NEG_CLIN_SUBJ_PAT}(?:\s+(?:never|not))?"
    rf"|{_NEG_CLIN_SUBJ_PAT}\s+(?:{_POS_NEG_Q_AUX}\s+(?:never|not)|{_CONTRACT_NEG_Q_AUX}(?:\s+(?:never|not))?))"
    rf"\s+{_NEG_EVER_ALLOW_OPT}(?:prescrib\w*|recommend\w*|claim\w*|declar\w*|certif\w*|authoriz\w*|administer\w*|giv\w*|dos\w*|cur\w*|heal\w*|treat\w*)\b",
    re.IGNORECASE | re.ASCII,
)
_BENIGN_ARCH_Q_RE = re.compile(
    r"^\s*(?:does|do|how\s+does|can|could|should|would)\s+"
    r"(?:(?:the|our)\s+)?(?:metacognition|firewall|epistemic\s+guard|guardrails?)\s+"
    r"(?:alter|suppress|hide|strip|drop|mask|remove)\b"
    r"(?!.*\b(?:constitution(?:\.md)?|firewall|guardrails?|safety\s+rules?|constitutional\s+rules?|safety\s+boundar(?:y|ies)|metacognition|provenance|thresholds?|constraints?|self(?:\s*[-\u2013\u2014]\s*|\s+)?model|monitoring)\b)",
    re.IGNORECASE | re.ASCII,
)
_NEGATED_SAFETY_SUBJ_RE = re.compile(
    rf"\bwhy\s+(?:{_POS_NEG_Q_AUX}|{_CONTRACT_NEG_Q_AUX})\s+(?:zoe|eliza|clara|you)\b",
    re.IGNORECASE | re.ASCII,
)
_NEGATED_SAFETY_DISQUAL_RE = re.compile(
    r"(?:\byou(?:'?re|\s+are|\s+were|\s+have|\s+had)\b|\b(?:suppose|declare\s+yourself)\b"
    r"|(?<!\bor\s)(?<!\band\s)\b(?:impersonate\s+(?:the\s+)?(?:real\s+)?zoe|claim(?:\s+that)?\s+(?:to\s+be|you(?:'?re|\s+are|\s+were))|pretend(?:\s+that)?\s+(?:to\s+be|you(?:'?re|\s+are|\s+were))|(?:act|behave)\s+as\s+if|role\s*-?\s*play)\b)",
    re.IGNORECASE | re.ASCII,
)
_NEG_SPLIT_CMD_TAIL = (
    rf"(?:{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease|"
    r"claim|pretend|act|behave|declare|role|impersonate|you(?:'?re|\s+are|\s+were|\s+have)?|"
    r"rm\b|curl\b|wget\b|give|administer|dose|prescribe|recommend|cure|heal|treat)"
)
_NEG_PIVOT_NEXT = (
    rf"(?:instead|also|just|please|now|then|let(?:'s|\s+us)\b|{_NEG_SPLIT_CMD_TAIL}|you\b|{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT}"
    r"|(?:[a-z]+ly\s+(?:{_NEG_SPLIT_CMD_TAIL}|turn|shut|switch|power))"
    r"|(?:compound|drug|molecule|agent|temozolomide|radiation|radiotherapy|chemotherapy|immunotherapy|doxorubicin)\b"
    r"|(?:the|a|an|this|that|our|your|all|every|any)\s+(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT}|compound|drug|molecule|agent))"
)
_NEG_PHRASAL_AND_SPLIT = (
    rf"(?:declare\s+to\s+be|(?:turn|shut|switch|power)\s+(?:off|down|(?:(?:the|all|your|our|my|these|those|any|every)\s+)?(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT})\s+(?:off|down))"
    rf"|(?:pause|halt|cease)\s+(?:(?:all|any|safety|constitutional|epistemic|ethical)\s+)?monitoring\b"
    rf"|(?:rm|curl|wget|sudo)\b"
    rf"|(?:enable|force|run|turn\s+on|activate|trigger|start|initiate|engage|launch|arm)\s+auto(?:\s*[.:/_\-\u2013\u2014\u2015\u2043]\s*|\s+)?flash\b"
    rf"|(?:(?:the|your|our|this|that|all|every|any|each)\s+){{0,2}}(?:{_META_TARGET_PAT}|{_CONSTITUTION_TARGET_PAT})\s+(?:{_DIRECT_BYPASS_ALT}|{_PASSIVE_OVERRIDE_MODAL_BODY})\b"
    rf"|(?:[a-z]+ly\s+){{1,2}}(?:{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease|declare|pretend|claim|act|behave|impersonate)\b"
    rf"|(?:you(?:'?re|\s+are|\s+were|\s+have|\s+had)|let(?:'s|\s+us)|everyone\s+must)\b)"
)
_NEG_NON_COMMA_CORE = (
    r"[:;\u2013\u2014]|--|->|=>|\||\s+-\s+|\s+/\s+"
    rf"|/(?=\s*{_NEG_SPLIT_CMD_TAIL})"
    r"|\band/or\b"
    r"|\b(?:and|or)\s+(?:now|please|instead|then|just|also)\b"
    r"|\b(?:but|yet|however|instead|therefore|thus|hence|consequently|otherwise)\b"
    rf"|\b(?:also|so)\s+(?={_NEG_PIVOT_NEXT})"
    r"|(?=\b(?:and|or)\s+(?:why\b|act\s+as\s+if|behave\s+as\s+if|declare\s+yourself|(?:pretend|claim)\s+(?:that\s+)?you\b)\b)"
    rf"|\band\s+(?={_NEG_PHRASAL_AND_SPLIT})"
    rf"|(?<!\bor\s)(?<!\band\s)(?<!\bright\s)\b(?:now|please|then)\s+(?={_NEG_PIVOT_NEXT})"
)
_NEG_NON_COMMA_DELIM_RE = re.compile(
    rf"(?:{_NEG_NON_COMMA_CORE}"
    r"|,\s*(?:and/or|(?:and|or)\s+(?:why|now|please|instead|then|just|also|act\s+as\s+if|behave\s+as\s+if|declare\s+yourself|(?:pretend|claim)\s+(?:that\s+)?you)|now|please|just|instead|then|also|so|but|yet|however|therefore|thus|hence)\b)",
    re.IGNORECASE | re.ASCII,
)
_NEG_CLAUSE_SPLIT_RE = re.compile(
    rf"(?:{_NEG_NON_COMMA_CORE}"
    r"|,(?:\s*(?:and/or|and|or|now|please|just|instead|then|also|so|but|yet|however|therefore|thus|hence)\b)?)",
    re.IGNORECASE | re.ASCII,
)
_OXFORD_VP_START_RE = re.compile(
    rf"^\s*(?:pretend|claim|say|act|behave|impersonate|role\s*-?\s*play|declare|{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease|prescrib\w*|recommend\w*|certif\w*|authoriz\w*|administer\w*|giv\w*|dos\w*|cur\w*|heal\w*|treat\w*)\b",
    re.IGNORECASE | re.ASCII,
)
_OXFORD_OR_VP_START_RE = re.compile(
    rf"^\s*or\s+(?:pretend|claim|say|act|behave|impersonate|role\s*-?\s*play|declare|{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease|prescrib\w*|recommend\w*|certif\w*|authoriz\w*|administer\w*|giv\w*|dos\w*|cur\w*|heal\w*|treat\w*)\b",
    re.IGNORECASE | re.ASCII,
)
_OR_SCOPE_PATTERNS: dict[str, re.Pattern[str]] = {
    "self_model": re.compile(r"\bor\s+(?:pretend|claim|say|act|behave|impersonate|role\s*-?\s*play|declare)\b", re.IGNORECASE | re.ASCII),
    "suppression": re.compile(rf"\bor\s+(?:{_BYPASS_VERB_PAT}|turn|shut|switch|power|stop|halt|pause|cease)\b", re.IGNORECASE | re.ASCII),
    "clinical": re.compile(r"\bor\s+(?:prescrib\w*|recommend\w*|claim\w*|declar\w*|certif\w*|authoriz\w*|administer\w*|giv\w*|dos\w*|cur\w*|heal\w*|treat\w*)\b", re.IGNORECASE | re.ASCII),
}
_DEFENSIVE_THREAT_HEAD_RE = re.compile(
    r"^\s*(?:(?:explain|discuss|describe|analyze|examine|understand|ask)\s+(?:how|whether)\s+|(?:how|whether)\s+)"
    r"(?:(?:can|could|would|might|may|do|does)\s+)?"
    r"(?:an?\s+)?(?:attackers?|adversar(?:y|ies)|threat\s+actors?|malicious\s+(?:users?|actors?|prompts?|inputs?))\s+"
    r"(?:(?:can|could|would|might|may)\s+)?(?:try\s+to\s+|attempt\s+to\s+)?",
    re.IGNORECASE | re.ASCII,
)
_DEFENSIVE_THREAT_FOLLOW_SPLIT_RE = re.compile(r"(?:,\s*(?:and|so)\b|\b(?:and|so)\b|;)", re.IGNORECASE | re.ASCII)


def is_defensive_threat_inquiry(sub: str) -> bool:
    """Return True when a clause discusses how an external attacker/adversary tries to bypass defenses without piggyback commands."""
    low = sub.lower()
    if not ("attacker" in low or "adversar" in low or "threat" in low or "malicious" in low):
        return False
    if _ATTACK_HOW_RE.search(low) is not None or has_destructive_shell_command(low):
        return False
    parts = _DEFENSIVE_THREAT_FOLLOW_SPLIT_RE.split(low, maxsplit=1)
    if _DEFENSIVE_THREAT_HEAD_RE.match(parts[0]) is None:
        return False
    if len(parts) > 1 and _followup_has_bypass_action(parts[1]):
        return False
    return True


def is_scope_exempt(sub: str, scope: str | None, target: str) -> bool:
    """Return True if a negated-question clause or defensive threat-model inquiry exempts ``target``."""
    if target == "suppression" and is_defensive_threat_inquiry(sub):
        return True
    if scope is None:
        return False
    if scope == target:
        return True
    pat = _OR_SCOPE_PATTERNS.get(target)
    return pat is not None and pat.search(sub) is not None
_LEADING_COORD_WHY_RE = re.compile(r"^\s*(?:and|or)\s+(?=why\b)", re.IGNORECASE | re.ASCII)
_SUB_WHY_START_RE = re.compile(r"^\s*(?:(?:explain|tell\s+me)\s+)?why\b", re.IGNORECASE | re.ASCII)


def _match_negated_lead(sentence: str) -> tuple[re.Match[str] | None, str | None]:
    for pat, kind in (
        (_NEGATED_SAFETY_Q_RE, "self_model"),
        (_NEGATED_SAFETY_SUPP_Q_RE, "suppression"),
        (_NEGATED_SAFETY_CLIN_Q_RE, "clinical"),
        (_BENIGN_ARCH_Q_RE, "suppression"),
    ):
        m = pat.match(sentence)
        if m is not None:
            return m, kind
    return None, None


_OXFORD_DISQUAL_RE = re.compile(
    r"(?:\byou(?:'?re|\s+are|\s+were|\s+have|\s+had)\b|\b(?:suppose|declare\s+yourself|(?:act|behave)\s+as\s+if)\b|(?:pretend|claim)(?:\s+that)?\s+you\b)",
    re.IGNORECASE | re.ASCII,
)


def _is_oxford_vp_list(comma_prefix: str) -> bool:
    chunks = comma_prefix.split(",")
    if len(chunks) < 2 or _OXFORD_OR_VP_START_RE.match(chunks[-1]) is None:
        return False
    if _OXFORD_DISQUAL_RE.search(chunks[-1]) is not None:
        return False
    for mid in chunks[1:-1]:
        if _OXFORD_VP_START_RE.match(mid) is None or _OXFORD_DISQUAL_RE.search(mid) is not None:
            return False
    return True


def _split_neg_rest(rest: str) -> tuple[list[str], bool]:
    if "," not in rest:
        return _NEG_CLAUSE_SPLIT_RE.split(rest), False
    m_nc = _NEG_NON_COMMA_DELIM_RE.search(rest)
    comma_prefix = rest[: m_nc.start()] if m_nc is not None else rest
    if "," in comma_prefix and _is_oxford_vp_list(comma_prefix):
        if m_nc is None:
            return [comma_prefix], True
        return [comma_prefix, *_NEG_CLAUSE_SPLIT_RE.split(rest[m_nc.end() :])], True
    return _NEG_CLAUSE_SPLIT_RE.split(rest), False


def split_negated_safety_clauses(sentence: str, _depth: int = 0) -> list[tuple[str, str | None]]:
    """Split a sentence starting with a negated safety question into (subclause, exempt_scope) pairs.

    Only negated safety question clauses themselves are exempted (``'self_model'``, ``'suppression'``, or ``'clinical'``);
    any subsequent colon/dash/comma/coordinator piggyback clause gets ``None`` (unexempted).
    """
    if not sentence:
        return []
    m_lead, kind = _match_negated_lead(sentence)
    if m_lead is None or kind is None:
        return [(sentence, None)]
    head = sentence[: m_lead.end()]
    rest = sentence[m_lead.end() :]
    if not rest:
        return [(head, kind)]
    raw_parts, used_oxford = _split_neg_rest(rest)
    # Keep raw_parts[0] (even if empty when delimiter is immediately after m_lead.end()) as lead's tail
    lead_tail = raw_parts[0]
    lead = f"{head}{lead_tail}"
    disq_pat = _OXFORD_DISQUAL_RE if used_oxford else _NEGATED_SAFETY_DISQUAL_RE
    scope0: str | None = None if disq_pat.search(lead_tail) is not None else kind
    out: list[tuple[str, str | None]] = [(lead, scope0)]
    for p in raw_parts[1:]:
        if not p or not p.strip():
            continue
        p_clean = _LEADING_COORD_WHY_RE.sub("", p, count=1)
        if _depth < 4 and _SUB_WHY_START_RE.match(p_clean):
            out.extend(split_negated_safety_clauses(p_clean, _depth=_depth + 1))
        else:
            out.append((p, None))
    return out


def is_negated_safety_question(sentence: str) -> bool:
    """Return True for single-clause educational questions asking why Zoe/Eliza/Clara must never pretend/claim sentience."""
    clauses = split_negated_safety_clauses(sentence)
    return len(clauses) == 1 and clauses[0][1] == "self_model"


def split_firewall_sentences(text_val: str, full_pat: re.Pattern[str] = _SENTENCE_SPLIT_RE) -> list[str]:
    """Fast-path sentence splitting avoiding lookbehind regex scans when no sentence delimiter exists."""
    if not text_val:
        return []
    if "." not in text_val:
        if "!" not in text_val and "?" not in text_val and ";" not in text_val:
            return [text_val]
        return [s for s in _FAST_NO_DOT_SPLIT_RE.split(text_val) if s]
    return [s for s in full_pat.split(text_val) if s]


def _is_invisible_sep_non_ascii(ch: str) -> bool:
    cached = _NON_ASCII_INV_CACHE.get(ch)
    if cached is not None:
        return cached
    cat = unicodedata.category(ch)
    res = cat in _INV_SEP_CATS or (cat == "Zs" and ch != " ") or ch in _EXTRA_INVISIBLE_SEPS
    if len(_NON_ASCII_INV_CACHE) < 4096:
        _NON_ASCII_INV_CACHE[ch] = res
    return res


def _is_invisible_sep(ch: str) -> bool:
    return ch > "\x7f" and _is_invisible_sep_non_ascii(ch)


def has_cf_chars(raw: str) -> bool:
    """Return True if raw text contains Unicode Cf/Zl/Zp/NEL, non-ASCII Zs, or invisible joiners."""
    if raw.isascii():
        return False
    return any(ch > "\x7f" and _is_invisible_sep_non_ascii(ch) for ch in raw)


def _fold_cf_piece(piece: str) -> str:
    if piece.isascii():
        return piece
    nfkd = unicodedata.normalize("NFKD", piece.translate(_FIREWALL_TRANS))
    if nfkd.isascii():
        return nfkd
    stripped = "".join(ch for ch in nfkd if ch <= "\x7f" or not _is_invisible_sep_non_ascii(ch))
    return unicodedata.normalize("NFKC", stripped).translate(_FIREWALL_TRANS)


def normalize_firewall_text(raw: str, *, cf_mode: str = "drop") -> str:
    """Canonical NFKD + Cf/Zs/Zl/Zp/Mn/Me + NFKC + confusable/hyphen folding preserving case."""
    text_val = str(raw or "")
    if text_val.isascii():
        return " ".join(text_val.split())
    if cf_mode == "space":
        chunks = [_fold_cf_piece(c) for c in _split_raw_cf_chunks(text_val)]
        return " ".join(" ".join(c for c in chunks if c).split())
    return " ".join(_fold_cf_piece(text_val).split())


def _split_raw_cf_chunks(raw: str) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    for ch in raw:
        if ch > "\x7f" and _is_invisible_sep_non_ascii(ch):
            if buf:
                chunks.append("".join(buf))
                buf.clear()
        else:
            buf.append(ch)
    if buf:
        chunks.append("".join(buf))
    return chunks


def _strip_edge_punct(joined: str) -> tuple[str, str, str]:
    lead_i = 0
    while lead_i < len(joined) and joined[lead_i] in "([{\"'":
        lead_i += 1
    end_i = len(joined)
    while end_i > lead_i and (joined[end_i - 1] in ",;:!?)]}\"'" or (joined[end_i - 1] == "." and not joined[:end_i].lower().endswith(".md"))):
        end_i -= 1
    return joined[:lead_i], joined[lead_i:end_i], joined[end_i:]


def _dp_segment_joined(joined: str, cf_bounds: frozenset[int]) -> str:
    n = len(joined)
    low = joined.lower()
    if low in _CF_DP_LEXICON:
        return joined
    dp = [0] + [10**9] * n
    back = [0] * (n + 1)
    unk_cost, unk_start = 10**9, 0
    for i in range(n):
        base = dp[i]
        unk_cost, unk_start = (base + 9, i) if base + 9 < unk_cost + 3 else (unk_cost + 3, unk_start)
        if unk_cost < dp[i + 1]:
            dp[i + 1], back[i + 1] = unk_cost, unk_start
        if low[i] in {",", ";", ":"} and base + 1 < dp[i + 1]:
            dp[i + 1], back[i + 1] = base + 1, i
        max_j = min(n, i + _CF_MAX_LEX_LEN)
        for j in range(i + 1, max_j + 1):
            sub = low[i:j]
            if not (sub in _CF_DP_LEXICON or (j - i == 1 and sub in _CF_SINGLE_CHAR_LEX and i in cf_bounds and j in cf_bounds)):
                continue
            bonus = 3 if (i in cf_bounds and j in cf_bounds) else (1 if (i in cf_bounds or j in cf_bounds) else 0)
            cand = base + (j - i) + 6 - bonus
            if cand <= dp[j]:
                dp[j], back[j] = cand, i
    parts: list[str] = []
    pos = n
    while pos > 0:
        prev = back[pos]
        parts.append(joined[prev:pos])
        pos = prev
    parts.reverse()
    return " ".join(parts)


def _segment_cf_token(tok: str, cache: dict[str, str]) -> str:
    if tok in cache:
        return cache[tok]
    chunks = [_fold_cf_piece(c) for c in _split_raw_cf_chunks(tok)]
    chunks = [c for c in chunks if c]
    joined_full = "".join(chunks)
    if not joined_full:
        cache[tok] = ""
        return ""
    lead_p, core, trail_p = _strip_edge_punct(joined_full)
    if not core:
        cache[tok] = joined_full
        return joined_full
    bounds = {0, len(core)}
    pos = -len(lead_p)
    for c in chunks:
        pos += len(c)
        if 0 < pos < len(core):
            bounds.add(pos)
    res = f"{lead_p}{_dp_segment_joined(core, frozenset(bounds))}{trail_p}"
    cache[tok] = res
    return res


def segment_mixed_cf_tokens(raw: str) -> str:
    """Reconstruct mixed Cf/Zs-split/merged tokens in strict O(n) time via DP."""
    raw_str = str(raw or "").strip()
    if raw_str.isascii():
        return " ".join(raw_str.split())
    cache: dict[str, str] = {}
    out: list[str] = []
    for tok in _ASCII_WS_SPLIT_RE.split(raw_str):
        if not tok:
            continue
        if has_cf_chars(tok):
            seg = _segment_cf_token(tok, cache)
            if seg:
                out.append(seg)
        else:
            norm = _fold_cf_piece(tok)
            if norm:
                out.append(norm)
    return " ".join(" ".join(out).split())


def firewall_text_variants(raw: str) -> tuple[str, ...]:
    """Return deduplicated normalized text variants (drop, plus space & DP-segmented if Cf/Zs present)."""
    raw_str = str(raw or "")
    drop_v = normalize_firewall_text(raw_str, cf_mode="drop")
    variants: list[str] = [drop_v] if drop_v else []
    if has_cf_chars(raw_str):
        for cand in (normalize_firewall_text(raw_str, cf_mode="space"), segment_mixed_cf_tokens(raw_str)):
            if cand and cand not in variants:
                variants.append(cand)
    return tuple(variants)


def _normalize_directive_text(text_value: str, *, cf_mode: str = "drop") -> str:
    return normalize_firewall_text(text_value, cf_mode=cf_mode).lower()


def _sentence_has_suppression(sentence: str) -> bool:
    if has_destructive_shell_command(sentence):
        return True
    m_tgt = _LOWER_ALL_TARGETS_RE.search(sentence)
    if m_tgt is None:
        return False
    if (
        _LOWER_PHRASAL_TURN_OFF_META_RE.search(sentence)
        or _LOWER_PHRASAL_TURN_OFF_CONST_RE.search(sentence)
        or _LOWER_STOP_MONITORING_RE.search(sentence)
    ):
        return True
    match = _LOWER_BYPASS_ACTION_RE.search(sentence)
    if match is not None and _LOWER_ALL_TARGETS_RE.search(sentence, match.end()) is not None:
        return True
    return has_target_before_verb_cmd(sentence, const_only=False)


def _check_directive_sentences(sentences: list[str]) -> str | None:
    uniq_sents = list(dict.fromkeys(s for s in sentences if s))
    for sentence in uniq_sents:
        if has_destructive_shell_command(sentence):
            return "metacognition_suppression_request"
        for sub, scope in split_negated_safety_clauses(sentence):
            if not is_scope_exempt(sub, scope, "suppression") and _sentence_has_suppression(sub):
                return "metacognition_suppression_request"
    for sentence in uniq_sents:
        for sub, scope in split_negated_safety_clauses(sentence):
            if not is_scope_exempt(sub, scope, "self_model") and _LOWER_SELF_MODEL_RE.search(sub):
                return "self_model_distortion_request"
    return None


def _check_directive_normalized(normalized: str) -> str | None:
    if not normalized:
        return None
    norm = re.sub(r"\b(?:you're|youre)\b", "you are", normalized) if "you" in normalized else normalized
    if has_semicolon_target_before_verb(norm, const_only=False):
        return "metacognition_suppression_request"
    return _check_directive_sentences(split_firewall_sentences(norm, _SENTENCE_SPLIT_RE))


def directive_violation(text_value, *, variants: tuple[str, ...] | None = None):
    if not isinstance(text_value, str):
        return None

    var_tuple = variants if variants is not None else firewall_text_variants(text_value)
    for variant in var_tuple:
        hit = _check_directive_normalized(variant.lower())
        if hit is not None:
            return hit
    return None

"""Cognitive Stem-Layering: Kloster A_tau(p) effort & model router for Zoe.

Routes tasks across five transparent execution tiers using Operational
Metacognition (`zoe_autonomy.metacognition`):
  - `gear1_eliza`: Deterministic symbolic ELIZA / citation fallback (0 cloud tokens)
  - `local_qwen`: Loopback Qwen2.5-3B on 127.0.0.1:8080 (0 cloud tokens, falls back to gear1_eliza)
  - `flash_lite`: Antigravity `flash_lite` (`ThinkingLevel.LOW`)
  - `flash`: Antigravity `flash` (`ThinkingLevel.MEDIUM`)
  - `pro`: Antigravity `pro` (`ThinkingLevel.HIGH` / `EXTRA_HIGH`, with `/teamwork` escalation)

Pure Python stdlib; preserves all `CONSTITUTION.md` invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Dict, Mapping, Sequence, Tuple
from urllib import error as urlerror, request as urlrequest
from urllib.parse import urlparse

from .metacognition import (
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    directive_violation,
    options_from_scores,
)

STEM_LAYERING_CONTRACT = "zoe-stem-layering/v1"
DEFAULT_TAU = 0.08
DEFAULT_LOCAL_QWEN_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_QWEN_MODEL = "qwen2.5-3b-instruct"
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

TIER_ORDER: Tuple[str, ...] = (
    "gear1_eliza",
    "local_qwen",
    "flash_lite",
    "flash",
    "pro",
)

TIER_SPECS: Dict[str, Dict[str, Any]] = {
    "gear1_eliza": {
        "antigravity_model": "local-eliza-gear1",
        "thinking_level": None,
        "local_only": True,
        "estimated_cloud_tokens": 0,
        "summary": "Deterministic symbolic ELIZA & citation lookup (<5 ms, 0 cloud tokens).",
    },
    "local_qwen": {
        "antigravity_model": DEFAULT_LOCAL_QWEN_MODEL,
        "thinking_level": None,
        "local_only": True,
        "estimated_cloud_tokens": 0,
        "base_url": f"{DEFAULT_LOCAL_QWEN_URL}/v1",
        "summary": "Loopback Qwen2.5-3B-Instruct on 127.0.0.1:8080 (0 cloud tokens; falls back to gear1_eliza).",
    },
    "flash_lite": {
        "antigravity_model": "flash_lite",
        "thinking_level": "low",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Lightweight cloud triage, formatting, and quick read-only checks (ThinkingLevel.LOW).",
    },
    "flash": {
        "antigravity_model": "flash",
        "thinking_level": "medium",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Standard single-module implementation, bug fixes, and unit verification (ThinkingLevel.MEDIUM).",
    },
    "pro": {
        "antigravity_model": "pro",
        "thinking_level": "high",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Deep reasoning, multi-file debugging, proofs, and optional /teamwork escalation (ThinkingLevel.HIGH/EXTRA_HIGH).",
    },
}

_DEEP_KEYWORDS = (
    "architect",
    "architecture",
    "audit",
    "ast",
    "concurrency",
    "cross-file",
    "debug",
    "distributed",
    "formal",
    "invariant",
    "kernel",
    "migration",
    "multi-file",
    "multifile",
    "orchestrate",
    "parallel",
    "proof",
    "race",
    "refactor",
    "security",
    "swarm",
    "teamwork",
    "theorem",
    "verification",
    "verify",
)

_STANDARD_DEV_KEYWORDS = (
    "add",
    "build",
    "create",
    "edit",
    "feature",
    "fix",
    "function",
    "implement",
    "integrate",
    "module",
    "patch",
    "pytest",
    "script",
    "test",
    "unittest",
    "update",
    "write",
)

_TRIAGE_KEYWORDS = (
    "brief",
    "briefly",
    "classify",
    "format",
    "list",
    "outline",
    "quick",
    "rename",
    "short",
    "summarize",
    "summary",
    "triage",
    "typo",
    "what is",
)

_LOCAL_SYMBOLIC_KEYWORDS = (
    "chladni",
    "cymatics",
    "eliza",
    "gear1",
    "hello",
    "hi",
    "ping",
    "recall",
    "relay",
    "remember",
    "status",
    "voice",
)

_LOCAL_LLM_KEYWORDS = (
    "brainstorm",
    "draft",
    "gear2",
    "llama",
    "local",
    "offline",
    "private",
    "privacy",
    "qwen",
)


def constitutional_flags(*, cloud_tokens_used: int = 0) -> Dict[str, Any]:
    """Return canonical CONSTITUTION.md invariants for stem-layering decisions."""
    return {
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "sentience_claimed": False,
        "pytorch_required": False,
        "external_actions": 0,
        "cloud_tokens_used": int(cloud_tokens_used),
    }


def _assert_loopback_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(f"local Qwen probe restricted to loopback hosts {sorted(ALLOWED_LOOPBACK_HOSTS)}, got {url!r}")
    return url.rstrip("/")


def probe_local_qwen(base_url: str = DEFAULT_LOCAL_QWEN_URL, timeout_sec: float = 0.6) -> Dict[str, Any]:
    """Probe loopback llama-server `/v1/models` cleanly without external network calls."""
    clean_url = _assert_loopback_url(base_url)
    endpoint = f"{clean_url}/v1/models"
    req = urlrequest.Request(endpoint, method="GET", headers={"Accept": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=float(max(0.1, min(timeout_sec, 10.0)))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = [
            str(item.get("id"))
            for item in (payload.get("data") or [])
            if isinstance(item, dict) and item.get("id")
        ]
        return {
            "available": True,
            "endpoint": endpoint,
            "models": models,
            "loopback_only": True,
        }
    except (urlerror.URLError, TimeoutError, ValueError, OSError) as exc:
        return {
            "available": False,
            "endpoint": endpoint,
            "models": [],
            "loopback_only": True,
            "reason": str(exc),
        }


def _tokenize(text: str) -> Tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_/+.-]+", text.lower()))


def _keyword_hits(normalized: str, tokens: Sequence[str], keywords: Sequence[str]) -> int:
    token_set = set(tokens)
    hits = 0
    for kw in keywords:
        if " " in kw or "-" in kw:
            if kw in normalized:
                hits += 1
        elif kw in token_set:
            hits += 1
    return hits


def build_sdk_descriptor(
    tier: str,
    *,
    thinking_level: str | None = None,
    base_url: str = f"{DEFAULT_LOCAL_QWEN_URL}/v1",
) -> Dict[str, Any]:
    """Build a validated Antigravity SDK configuration descriptor (pure stdlib)."""
    if tier not in TIER_SPECS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIER_ORDER}")
    spec = TIER_SPECS[tier]
    resolved_thinking = thinking_level if thinking_level is not None else spec["thinking_level"]
    valid_levels = {None, "minimal", "low", "medium", "high", "xhigh"}
    if resolved_thinking not in valid_levels:
        raise ValueError(f"invalid thinking_level {resolved_thinking!r}; expected one of {sorted(x for x in valid_levels if x)}")

    if tier == "local_qwen":
        clean_base = _assert_loopback_url(base_url).rstrip("/")
        if not clean_base.endswith("/v1"):
            clean_base = f"{clean_base}/v1"
        return {
            "tier": tier,
            "sdk_class": "LocalOpenAIAgentConfig",
            "lightweight": True,
            "model": DEFAULT_LOCAL_QWEN_MODEL,
            "base_url": clean_base,
            "thinking_level": None,
            "cloud_tokens_used": 0,
        }
    if tier == "gear1_eliza":
        return {
            "tier": tier,
            "sdk_class": "ZoeElizaEngine",
            "lightweight": True,
            "model": "local-eliza-gear1",
            "gear": "gear1",
            "thinking_level": None,
            "cloud_tokens_used": 0,
        }
    return {
        "tier": tier,
        "sdk_class": "GeminiModelOptions",
        "antigravity_model": spec["antigravity_model"],
        "thinking_level": resolved_thinking,
        "thinking_enum": f"ThinkingLevel.{ {'minimal': 'MINIMAL', 'low': 'LOW', 'medium': 'MEDIUM', 'high': 'HIGH', 'xhigh': 'EXTRA_HIGH'}[resolved_thinking] }",
    }


@dataclass(frozen=True)
class StemDecision:
    selected_tier: str
    antigravity_model: str
    thinking_level: str | None
    teamwork_recommended: bool
    fallback_tier: str
    fallback_applied: bool
    fallback_reason: str | None
    a_tau: int
    tau: float
    entropy_norm: float
    probabilities: Dict[str, float]
    features: Dict[str, Any]
    provenance: Dict[str, Any]
    constitutional: Dict[str, Any]
    sdk_descriptor: Dict[str, Any]
    local_probe: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": STEM_LAYERING_CONTRACT,
            "selected_tier": self.selected_tier,
            "antigravity_model": self.antigravity_model,
            "thinking_level": self.thinking_level,
            "teamwork_recommended": self.teamwork_recommended,
            "fallback_tier": self.fallback_tier,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": self.fallback_reason,
            "a_tau": self.a_tau,
            "tau": self.tau,
            "entropy_norm": self.entropy_norm,
            "probabilities": dict(self.probabilities),
            "features": dict(self.features),
            "provenance": dict(self.provenance),
            "constitutional": dict(self.constitutional),
            "sdk_descriptor": dict(self.sdk_descriptor),
            "local_probe": dict(self.local_probe) if self.local_probe is not None else None,
        }


def route_stem(
    prompt: str,
    *,
    offline_only: bool = False,
    privacy_sensitive: bool = False,
    files_count: int = 1,
    multi_file: bool = False,
    local_qwen_available: bool | None = None,
    probe_local: bool = False,
    local_qwen_url: str = DEFAULT_LOCAL_QWEN_URL,
    tau: float = DEFAULT_TAU,
) -> StemDecision:
    """Route a prompt across Cognitive Stem-Layering tiers via Kloster A_tau(p)."""
    cleaned = " ".join(str(prompt or "").split()).strip()
    if not cleaned:
        raise ValueError("prompt must not be empty")
    if isinstance(files_count, bool) or not isinstance(files_count, int) or files_count < 0:
        raise ValueError("files_count must be a nonnegative integer")
    if not isinstance(tau, (int, float)) or isinstance(tau, bool) or not (0.0 < float(tau) < 1.0):
        raise ValueError("tau must be in (0, 1)")

    local_probe_doc: Dict[str, Any] | None = None
    if local_qwen_available is None and probe_local:
        local_probe_doc = probe_local_qwen(local_qwen_url)
        local_qwen_available = bool(local_probe_doc["available"])

    normalized = cleaned.lower()
    tokens = _tokenize(cleaned)
    word_count = len(tokens)
    char_count = len(cleaned)
    deep_hits = _keyword_hits(normalized, tokens, _DEEP_KEYWORDS)
    dev_hits = _keyword_hits(normalized, tokens, _STANDARD_DEV_KEYWORDS)
    triage_hits = _keyword_hits(normalized, tokens, _TRIAGE_KEYWORDS)
    symbolic_hits = _keyword_hits(normalized, tokens, _LOCAL_SYMBOLIC_KEYWORDS)
    local_llm_hits = _keyword_hits(normalized, tokens, _LOCAL_LLM_KEYWORDS)
    effective_multi_file = bool(multi_file or files_count >= 3)
    local_constraint = bool(offline_only or privacy_sensitive)
    violation = directive_violation(cleaned)

    # Complexity score in [0, 10+] derived transparently from measurable prompt features.
    complexity = (
        min(2.5, word_count / 24.0)
        + 1.35 * deep_hits
        + 0.65 * dev_hits
        + (1.8 if effective_multi_file else (0.55 if files_count == 2 else 0.0))
        - 0.75 * triage_hits
        - 0.60 * symbolic_hits
    )
    complexity = max(0.0, complexity)

    # Nonnegative heuristic scores per tier before normalization via options_from_scores.
    gear1_score = 0.20 + 1.9 * symbolic_hits + (0.85 if word_count <= 3 and dev_hits == 0 and deep_hits == 0 and triage_hits == 0 else 0.0)
    local_qwen_score = 0.30 + 1.6 * local_llm_hits + (1.2 if local_constraint else 0.0) + (0.45 if 6 <= word_count <= 40 else 0.0)
    flash_lite_score = 0.45 + 1.45 * triage_hits + (1.3 if word_count <= 14 and dev_hits == 0 and deep_hits == 0 and not effective_multi_file else 0.0)
    flash_score = 0.35 + 1.25 * dev_hits + (1.1 if 0.8 <= complexity < 3.0 and not effective_multi_file else 0.0)
    pro_score = 0.25 + 1.45 * deep_hits + (2.2 if effective_multi_file else 0.0) + (1.2 if complexity >= 3.0 else 0.0)

    if local_constraint:
        # Cloud tiers strictly excluded under offline_only or privacy_sensitive constraints.
        flash_lite_score = 0.0
        flash_score = 0.0
        pro_score = 0.0
        local_qwen_score += 2.2
        gear1_score += 1.0 if (word_count <= 5 and local_llm_hits == 0) else 0.35
    elif local_qwen_available is False:
        # Down-weight local_qwen when explicitly known offline in online mode.
        local_qwen_score *= 0.2

    scores: Dict[str, float] = {
        "gear1_eliza": round(max(0.0, gear1_score), 6),
        "local_qwen": round(max(0.0, local_qwen_score), 6),
        "flash_lite": round(max(0.0, flash_lite_score), 6),
        "flash": round(max(0.0, flash_score), 6),
        "pro": round(max(0.0, pro_score), 6),
    }

    src = EvidenceSource(
        kind="document",
        identifier="zoe-autonomy:stem-layering",
        trust=0.90,
        strength=0.85,
    )
    provenance = Provenance(
        (src,),
        ("Score cognitive stem tiers from prompt complexity, file breadth, and offline/privacy constraints.",),
    )
    options = options_from_scores(scores, provenance)
    meta = OperationalMetacognition()
    threshold = meta.threshold(
        Domain.INTENT,
        float(tau),
        rationale="Declared before stem routing evaluation and fixed for this episode; no post-hoc retuning.",
    )
    breadth = meta.count(options, threshold)

    probs = {opt.identifier: round(float(opt.probability), 6) for opt in breadth.options}
    entropy = -sum(p * math.log2(p) for p in probs.values() if p > 1e-12)
    active_support = max(2, sum(1 for p in probs.values() if p > 0.0))
    entropy_norm = round(entropy / math.log2(active_support), 6)

    ranked = sorted(breadth.options, key=lambda opt: (-opt.probability, TIER_ORDER.index(opt.identifier)))
    selected_tier = ranked[0].identifier

    fallback_applied = False
    fallback_reason: str | None = None
    if selected_tier == "local_qwen" and local_qwen_available is False:
        selected_tier = "gear1_eliza"
        fallback_applied = True
        fallback_reason = "local Qwen2.5-3B (127.0.0.1:8080) unavailable; fell back cleanly to Gear 1 ELIZA."
    elif local_constraint and selected_tier not in {"gear1_eliza", "local_qwen"}:
        selected_tier = "local_qwen" if local_qwen_available is not False else "gear1_eliza"
        fallback_applied = True
        fallback_reason = "Cloud tiers disabled by offline/privacy constraint."

    spec = TIER_SPECS[selected_tier]
    teamwork_recommended = bool(
        (not local_constraint)
        and selected_tier == "pro"
        and (
            effective_multi_file
            or deep_hits >= 2
            or "teamwork" in normalized
            or "swarm" in normalized
            or (breadth.accessible_count >= 3 and complexity >= 3.2)
        )
    )

    thinking_level = spec["thinking_level"]
    if selected_tier == "pro" and (teamwork_recommended or deep_hits >= 2 or complexity >= 4.2):
        thinking_level = "xhigh"

    sdk_descriptor = build_sdk_descriptor(
        selected_tier,
        thinking_level=thinking_level,
        base_url=f"{local_qwen_url.rstrip('/')}/v1",
    )

    features = {
        "word_count": word_count,
        "char_count": char_count,
        "files_count": files_count,
        "multi_file": effective_multi_file,
        "offline_only": bool(offline_only),
        "privacy_sensitive": bool(privacy_sensitive),
        "local_qwen_available": local_qwen_available,
        "deep_hits": deep_hits,
        "dev_hits": dev_hits,
        "triage_hits": triage_hits,
        "symbolic_hits": symbolic_hits,
        "local_llm_hits": local_llm_hits,
        "complexity_score": round(complexity, 4),
        "directive_violation": violation,
    }

    return StemDecision(
        selected_tier=selected_tier,
        antigravity_model=str(spec["antigravity_model"]),
        thinking_level=thinking_level,
        teamwork_recommended=teamwork_recommended,
        fallback_tier="gear1_eliza",
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
        a_tau=int(breadth.accessible_count),
        tau=float(breadth.tau),
        entropy_norm=entropy_norm,
        probabilities=probs,
        features=features,
        provenance=provenance.document(),
        constitutional=constitutional_flags(cloud_tokens_used=0),
        sdk_descriptor=sdk_descriptor,
        local_probe=local_probe_doc,
    )
